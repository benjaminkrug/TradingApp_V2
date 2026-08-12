# Phase 5 — Validation Engine: Status & offene Punkte

Referenz: `ROADMAP.md` Abschnitt 10 und 15 ("die 12-Punkte-Checkliste wird als automatisierte CI-Gate-Pipeline implementiert, nicht als Dokument, das ein Mensch/eine AI manuell durchgeht").

## Was fertig ist und getestet wurde (37 neue Tests, 108 insgesamt)

- **`app/validation/metrics.py`** — Fills zu Trades paaren, Kennzahlen (Win Rate, Profit Factor, Expectancy, Consecutive Losses) gegen Handrechnung geprüft.
- **`app/validation/oos.py`** — `OosSplit`: technisch erzwungene Sperre, kein Zugriff auf Out-of-Sample-Daten vor explizitem `unlock()`. Direkte Umsetzung der Regel aus Abschnitt 8 ("Claude darf OOS-Daten nicht zur Optimierung verwenden") als Code statt als Konvention.
- **`app/validation/walk_forward.py`** — Rollierende Train/Test-Fenster über echte Kalendertage, getestet gegen von Hand abgeleitete Fenstergrenzen.
- **`app/validation/monte_carlo.py`** — Bootstrap-Resampling realisierter Trade-PnLs zur Drawdown-Verteilung, reine Standardbibliothek (`random`, kein NumPy nötig). Reproduzierbarkeit über festen Seed getestet.
- **`app/validation/leakage.py`** — empirischer Look-Ahead-/Leakage-Detektor: Backtest einmal auf der vollen Serie, einmal auf einem abgeschnittenen Präfix, Vergleich der Fills vor der Schnittgrenze. Getestet an allen drei echten Strategien (sauber) **und** an einer absichtlich schummelnden Test-Strategie (wird zuverlässig erkannt) — siehe unten.
- **`app/validation/gate.py`** — die 12-Punkte-Checkliste als `evaluate_candidate(...)`, mit ehrlichem `NOT_AUTOMATED`-Status für die Punkte, die der aktuelle Stand nicht prüfen kann (siehe nächster Abschnitt), statt sie als "bestanden" vorzutäuschen.

## Wichtiger Fund während der Entwicklung: mein erster Entwurf des Leakage-Detektors war selbst unzureichend

Der ursprüngliche Ansatz verglich nur "jeder Fill im Präfix-Lauf muss zum entsprechenden Fill im Vollständig-Lauf passen". Beim Testen mit einer absichtlich schummelnden Strategie stellte sich heraus: Wenn die Schummelei dazu führt, dass der Präfix-Lauf **weniger** Fills erzeugt (statt falscher), erkennt dieser Vergleich nichts — die Schleife über die (leere) Präfix-Fill-Liste läuft einfach nie. Korrigiert auf einen Mengenvergleich vor einer Schnittgrenze (mit kleinem Puffer für den erwarteten, harmlosen Trunkierungseffekt am Rand), der sowohl zusätzliche als auch fehlende als auch falsche Fills erkennt. Ohne diesen Fix hätte der Detektor in genau der Konstellation versagt, in der es am wichtigsten gewesen wäre.

## Die 12 Punkte — ehrlicher Status

| # | Punkt | Status |
|---|---|---|
| 1+2 | Kein Look-Ahead / keine Leakage | ✅ automatisiert (`leakage.py`) |
| 3 | Keine Survivorship Bias | ⏳ nicht automatisierbar — Herkunftsfrage des Universums, nicht aus einem einzelnen Backtest-Ergebnis ableitbar |
| 4 | Realistische Gebühren | ✅ automatisiert (prüft `fee_per_share > 0`) |
| 5 | Realistische Slippage | ⏳ nicht automatisierbar — kein Slippage-Modell existiert |
| 6 | Realistische Ausführung | ⏳ nicht automatisierbar — `reference_engine.py` ist explizit eine Korrektheits-Referenz, keine Ausführungs-Realitätsprüfung |
| 7 | Ausreichend Trades | ✅ automatisiert (konfigurierbarer Mindestwert) |
| 8 | OOS positiv | ✅ automatisiert, wenn `oos_bars` übergeben werden |
| 9 | Walk-Forward stabil | ✅ automatisiert, wenn `walk_forward_test_windows` übergeben werden |
| 10 | Monte-Carlo akzeptabel | ✅ automatisiert, wenn ein Drawdown-Schwellenwert übergeben wird |
| 11 | Verschiedene Marktregime getestet | ⏳ nicht automatisierbar — keine Regime-Erkennung existiert (Phase 6+) |
| 12 | Paper Trading bestätigt | ⏳ nicht automatisierbar — Paper Trading existiert nicht (Phase 9) |

**7 von 12 Punkten sind jetzt echt automatisiert**, 5 bleiben bewusst als `NOT_AUTOMATED` mit Begründung markiert statt stillschweigend übersprungen oder als "bestanden" simuliert zu werden. `GateReport.passed` prüft nur die automatisierbaren Punkte; `GateReport.fully_automated` macht explizit sichtbar, dass die Abdeckung noch unvollständig ist.

## Was noch offen ist

1. Punkte 3, 5, 6, 11, 12 werden automatisierbar, sobald die jeweiligen Bausteine existieren (Slippage-Modell, produktive Engine, Regime-Erkennung, Paper Trading) — kein Nachholbedarf an sich, sondern folgerichtig erst nach den jeweiligen Phasen möglich.
2. `walk_forward_windows()` (Phase 5) und `evaluate_candidate()`s `walk_forward_test_windows`-Parameter sind noch nicht direkt verzahnt in einem Convenience-Aufruf (aktuell muss man die Fenster selbst erzeugen und übergeben) — bewusst nicht zusammengeführt, um die Utility unabhängig testbar zu halten.
3. Kein CI-Job wurde neu hinzugefügt — die neuen Tests laufen automatisch im bestehenden `pytest -q`-Schritt mit. Der in Phase 1 angekündigte "separate Job" war unnötig, das ist in `.github/workflows/ci.yml` jetzt entsprechend korrigiert dokumentiert.

## Update 12.08.2026: kritische Nachprüfung — drei weitere Funde, behoben

Auf Wunsch des Nutzers wurden Phase 5 und 6 noch einmal sehr genau durchgesehen. Dabei gefunden und behoben:

1. **`trades_from_fills` vertraute seiner Eingabe blind**, anders als der Rest der Codebase (`PointInTimeSeries` prüft z. B. aktiv Symbol-Konsistenz und Reihenfolge). Bei zwei aufeinanderfolgenden BUYs ohne dazwischenliegendes SELL wäre die erste Position stillschweigend verworfen worden; bei versehentlich vermischten Symbolen hätte ein BUY auf Symbol A mit einem SELL auf Symbol B gepaart werden können. Jetzt wirft die Funktion in beiden Fällen einen Fehler statt falsch zu rechnen.
2. **`walk_forward.py` und `oos.py` nutzten `.date()` direkt auf UTC-Zeitstempeln**, statt wie `indicators.py`'s `current_session_bars` nach NY-Ortszeit zu konvertieren. Für reguläre Handelssitzungen (9:30–16:00 ET) fällt das nicht auf, weil die Sitzung die UTC-Mitternacht nie überschreitet — reiner Zufall der Handelszeiten, kein Entwurfsprinzip. Mit einem konkreten Zeitstempel-Beispiel (2026-01-03 02:00 UTC = 2026-01-02 21:00 EST) nachgewiesen und auf die NY-lokale Konvention umgestellt, konsistent mit dem Rest der Codebase.
3. **Der Default `boundary_buffer=1` im Leakage-Detektor war zu konservativ** und hat dadurch Fills ausgeschlossen, die eigentlich vergleichbar gewesen wären — genau dort, wo ein Leck am ehesten unentdeckt bliebe. Mit einer eigens konstruierten "Near-Boundary"-Cheat-Strategie nachgewiesen: Bei `boundary_buffer=1` wurde der Leak übersehen (`clean=True`, falsch!), bei `boundary_buffer=0` (neuer Default) korrekt erkannt. Als Regressionstest festgehalten, der beide Varianten gegenüberstellt.

Außerdem: Die `realistic_fees`-Meldung im Gate behauptete implizit mehr, als sie prüft (nur "ungleich null", nicht "Höhe realistisch") — Formulierung präzisiert.

8 neue Tests für diese Funde, alle 148 Tests der Gesamt-Suite laufen weiterhin grün.
