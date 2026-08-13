# Phase 7 — AI Strategy Generator: Status & offene Punkte

Referenz: `ROADMAP.md` Abschnitt 8, 19 ("Claude generiert weitere Strategien gegen die verifizierte Pipeline. Erst nach Abschluss Phase 4+5.").

## Was fertig ist und getestet wurde (11 neue Tests, 159 insgesamt)

Zwei neue Strategie-Hypothesen, mechanistisch eigenständig, nicht nur Parametervarianten der drei aus Phase 4:

- **`app/strategies/mean_reversion.py`** — Gegenentwurf zu den drei bestehenden (trendfolgenden) Strategien: kauft Schwäche statt Stärke, wettet auf Rückkehr zum Mittelwert. ROADMAP.md Abschnitt 8 verlangt das explizit als separate Behandlung ("Strategie E — wird separat behandelt, da andere Marktregime benötigt werden"). Nutzt einen neuen Indikator, `distance_in_atr` (Abstand vom EMA in ATR-Einheiten), ebenfalls gegen Handrechnung geprüft.
- **`app/strategies/relative_volume_momentum.py`** — nutzt Relative Volume (aus Phase 6, bisher von keiner Strategie als Haupttrigger verwendet) als primäres Signal statt nur als Bestätigungsfaktor.

Beide: isolierte Signal-Tests mit konstruierten Szenarien, End-to-End-Backtest mit exakt nachgerechnetem Fill-Preis/PnL — gleiches Vorgehen wie in Phase 4.

## Der eigentliche Phase-7-Test: beide Strategien durch die volle Pipeline

`backend/scripts/phase7_synthetic_gate_run.py` (reproduzierbar, fester Seed) erzeugt einen synthetischen Random-Walk-Kursverlauf über 120 Handelstage (5-Minuten-Bars, echter NYSE-Kalender), teilt ihn in In-Sample/Out-of-Sample (`OosSplit`, technisch gesperrt bis `unlock()`), bildet Walk-Forward-Fenster und lässt beide Strategien durch `evaluate_candidate()` laufen.

**Ergebnis — beide Strategien fallen durch das Gate:**

| Strategie | Leakage | Ausreichend Trades | OOS positiv | Walk-Forward stabil | Monte Carlo |
|---|---|---|---|---|---|
| Mean Reversion | ✅ sauber | ✅ 51 Trades | ❌ Expectancy −0,35 über 32 Trades | ❌ nur 1/4 Fenster profitabel | ✅ |
| Relative Volume Momentum | ✅ sauber | ✅ 45 Trades | ✅ Expectancy +0,19 über 21 Trades | ❌ nur 1/4 Fenster profitabel | ✅ |

`GateReport.passed = False` für beide.

## Warum das ein gutes Ergebnis ist, kein gescheitertes Experiment

Die synthetischen Daten sind ein reiner Random Walk (unabhängiges Tages-Drift + Gauß-Rauschen, keine absichtlich eingebaute ausnutzbare Struktur) — anders als die handkonstruierten, deterministischen Szenarien aus Phase 4, die gezielt eine bestimmte Strategie-Logik auslösen sollten. Auf echtem Zufall **sollte** eine ehrliche Validierungs-Pipeline eine Strategie nicht durchwinken, nur weil sie zufällig im In-Sample-Zeitraum ein paar profitable Trades hatte. Genau das ist hier passiert: Beide Strategien zeigten im In-Sample-Backtest genug Trades, um überhaupt bewertbar zu sein, aber keine der beiden hält der Out-of-Sample- und Walk-Forward-Prüfung stand. Das bestätigt, dass das Gate tut, was es soll — es akzeptiert keine Strategie allein aufgrund eines einzelnen guten Backtests (ROADMAP.md Abschnitt 8).

**Was hier ausdrücklich nicht gemacht wurde:** An den Strategie-Parametern drehen, bis eine PASS-Ampel erscheint. Das wäre exakt das Overfitting-durch-Iteration-Problem, das ROADMAP.md Abschnitt 10 anhand des DaviddTech-Transkripts kritisiert (OOS-Disziplin durch iteratives menschliches Feedback statt sauberer Trennung). Die Ergebnisse stehen so, wie sie beim ersten Durchlauf herauskamen.

## Was noch offen ist

1. **Kein echter Test der Strategie-Qualität.** Weder Mean Reversion noch Relative Volume Momentum wurden gegen echte Marktdaten geprüft — Alpaca/Polygon sind weiterhin unverifizierte Stubs (Phase 3). Der obige Lauf zeigt nur: Die Pipeline funktioniert und verhält sich auf strukturlosen Daten korrekt zurückhaltend. Er zeigt nicht, ob die Strategien auf echten Märkten eine Kante haben.
2. **Der synthetische Datengenerator ist ein Demonstrationsskript**, kein Teil der Produktionsbibliothek — bewusst unter `scripts/`, nicht unter `app/`, um keine ungenutzte Infrastruktur vorzuhalten.
3. **Nur 2 neue Strategien**, wie angefragt — ROADMAP Abschnitt 8 nennt weitere Beispiele (z. B. reine Momentum-Breakout-Variante ohne Opening-Range-Bezug), die bei Bedarf später ergänzt werden können.
4. **Die Guardrails aus ROADMAP Abschnitt 8** wurden eingehalten: keine Aktivierung aufgrund eines einzelnen Backtests, `OosSplit.unlock()` erst nach Abschluss der In-Sample-Entwicklung aufgerufen, keine automatische Kapitalzuweisung.
