# Echte-Daten-Validierung der Phase-4-Strategien — Status & offene Punkte

Referenz: `ROADMAP.md` Abschnitt 8 (Pipeline-Reihenfolge: In-Sample → Validation → Out-of-Sample → Forward Test) und Abschnitt 14 (Forward Test soll OOS-Ergebnisse *bestätigen*, nicht selbst validieren).

## Warum dieser Schritt existiert

Alle bisherigen Gate-Läufe (Phase 5/6/7) liefen ausschließlich gegen synthetische Zufallsdaten, weil `AlpacaProvider` bis 21.09.2026 nur ein Stub war (siehe `PHASE3_NOTES.md`). Das hat bewiesen, dass die Validierungs-Pipeline selbst korrekt funktioniert — aber nie, ob irgendeine Strategie auf echten Marktdaten tatsächlich funktioniert. Ein Forward-Test (Wochen/Monate über echte Zeit) einer Strategie, die nie auf echten Daten validiert wurde, hätte nichts zu bestätigen. Deshalb: erst dieser Schritt, dann erst Phase C (Forward-Test-Cronjob).

## Was gemacht wurde

`backend/scripts/real_data_gate_run.py` — analog zu `scripts/phase7_synthetic_gate_run.py`, aber mit echten Bars von `AlpacaProvider` statt einem synthetischen Random Walk. Lädt `.env`, holt 5-Minuten-Bars für ein Symbol über ~200 Kalendertage, teilt 70/30 in In-Sample/OOS (`OosSplit`), bildet Walk-Forward-Fenster (Train 40 / Test 10 / Step 10 Tage), lässt alle drei Phase-4-Strategien durch `evaluate_candidate()` laufen.

**Lauf 1, 21.09.2026, Symbol AAPL, 05.03.2026–21.09.2026, 11.459 echte 5-Min-Bars:**

| Strategie | Leakage | Ausreichend Trades | OOS positiv | Walk-Forward stabil | Gate bestanden |
|---|---|---|---|---|---|
| VWAP Momentum | ✅ sauber | ✅ 245 Trades | ✅ Expectancy +0,089 über 123 Trades | ❌ nur 2/5 Fenster profitabel | ❌ **FAIL** |
| EMA Pullback | ✅ sauber | ✅ 216 Trades | ✅ Expectancy +0,181 über 95 Trades | ✅ 3/5 Fenster profitabel | ✅ **PASS** (aller automatisierbaren Punkte) |
| Opening Range Breakout | ✅ sauber | ✅ 116 Trades | ✅ Expectancy +0,254 über 44 Trades | ✅ 3/5 Fenster profitabel | ✅ **PASS** (aller automatisierbaren Punkte) |

**Lauf 2+3, noch am 21.09.2026, MSFT und NVDA, gleicher Zeitraum (05.03.–21.09.2026), um genau die Frage zu beantworten, ob Lauf 1 generalisiert:**

| Strategie | AAPL | MSFT | NVDA |
|---|---|---|---|
| VWAP Momentum | ❌ FAIL (WF 2/5) | ❌ FAIL (WF 2/5) | ❌ FAIL (OOS **negativ** −0,110, WF 2/5) |
| EMA Pullback | ✅ PASS | ❌ FAIL (WF 2/5) | ❌ FAIL (OOS **negativ** −0,041, WF 2/5) |
| Opening Range Breakout | ✅ PASS | ❌ FAIL (WF nur 1/5) | ✅ PASS (WF 4/5) |

**Ehrliches Gesamtfazit: Keine der drei Strategien besteht konsistent über alle drei getesteten Symbole.** VWAP Momentum fällt überall durch (0/3). EMA Pullback besteht nur auf AAPL (1/3) — der ursprüngliche AAPL-PASS war also zu einem guten Teil Stichproben-Zufall, kein robuster Fund. Opening Range Breakout ist mit 2/3 (AAPL, NVDA) am stärksten, fällt aber auf MSFT ebenfalls durch — reicht nicht, um sie als "validiert" zu bezeichnen, nur um sie als **einzigen noch nicht widerlegten Kandidaten** für weitere Tests zu behandeln.

Monte Carlo bewusst **NOT_AUTOMATED** gelassen (kein `monte_carlo_drawdown_threshold` übergeben) — welcher maximale Drawdown "akzeptabel" ist, ist eine Risikotoleranz-Entscheidung, die bisher niemand getroffen hat (kein DECISIONS.md-Eintrag dafür). Das wäre sonst dieselbe Art unbestätigter Geschäftsentscheidung, vor der `compare_to_oos()`s eigener Docstring schon warnt.

**Wichtig, damit dieses Ergebnis nicht überinterpretiert wird:**
- Nur **drei** Symbole, nur **ein** Zeitraum (~6,5 Monate, alle drei Läufe überlappen fast komplett zeitlich — kein Test über unterschiedliche Marktphasen). Kein Beleg, dass Opening Range Breakout auf weiteren Symbolen oder in anderen Zeiträumen ebenso abschneiden würde.
- `sufficient_trades`, `oos_positive`, `walk_forward_stable` sind PASS/FAIL — aber `no_survivorship_bias`, `realistic_slippage`, `realistic_execution`, `multiple_regimes_tested`, `paper_trading_confirmed` bleiben weiterhin `NOT_AUTOMATED`. "Gate bestanden" heißt hier: alle *automatisierbaren* Punkte bestanden, nicht alle 12 Punkte der Roadmap-Checkliste.
- `reference_engine.py` (verwendet in `evaluate_candidate`) handelt immer exakt 1 Einheit pro Trade, keine risikobasierte Positionsgröße wie später im echten Paper-Trading (`app/signals/risk.py`) — Expectancy-Werte sind auf dieser Skala zu lesen, nicht direkt auf Dollar-Ergebnisse übertragbar (gleicher Hinweis wie in `app/forward_test/session.py`s `_MAGNITUDE_CAVEAT`).

## Wichtige Korrektur zur Umgebung (siehe auch `PHASE3_NOTES.md`)

Beim ersten "Smoke-Test" dieses Skripts mit angeblich synthetischen Daten lief versehentlich ein echter Alpaca-Call — Claude kann `.env`-Secrets in dieser Umgebung tatsächlich lesen, sobald die Datei gespeichert ist (keine Sandbox-Sperre, wie zuvor fälschlich dokumentiert). Der Call war harmlos (nur Kursdaten lesen, keine Order), aber ungeplant. Für künftige Arbeit mit echten Zugangsdaten: bewusst vorsichtig bleiben, nicht auf eine technische Bremse verlassen, die es nicht gibt.

## Nachtrag 21.09.2026 — vollständiges Gate nach `VALIDATION_PROTOCOL.md`

Messapparat repariert (K2, K2a, K3–K7 implementiert, 270 Tests grün), dann alle 27 Konfigurationen (3 Strategien × 3 Symbole × 3 Stop-Horizonte) auf der Out-of-Sample-Hälfte durchlaufen lassen.

**Ergebnis: 0 von 27 Konfigurationen bestehen.**

Das allein wäre bei diesem Datenumfang zu erwarten gewesen. Entscheidend ist *woran* sie scheitern:

| Kriterium | Ergebnis über alle 27 Läufe |
|---|---|
| K1 Datenlecks | überall sauber |
| K3 Netto nach 2 bp Kosten | 17 von 27 positiv, Break-even teils 8–24 bp — **wirtschaftlich unproblematisch** |
| K4 Signifikanz (Tagesblock-Bootstrap) | t-Median **+0,04**, Maximum +1,16, **keiner erreicht 2,0** |
| K5 Stichprobengröße | überall zu klein (OOS-Fenster ist nur ~41 Handelstage) |
| K6 Marktphasen | nicht anwendbar — die Daten enthalten nur eine Phase |
| K7 Permutationstest | p-Median **0,799**, Minimum 0,156, **keiner unter 0,05** |

**K7 ist der eigentliche Befund.** Unter einer echten Nullhypothese wären die p-Werte gleichverteilt, also im Median 0,50. Beobachtet: **0,799.** Das heißt, zufällig gewürfelte Einstiegszeitpunkte — bei gleicher Anzahl Trades, gleichen Handelstagen und gleicher Haltedauer — schlagen unsere Strategien in typischerweise rund 80 % der Ziehungen. Das Einstiegs-Timing trägt nicht nur keine Information, es ist tendenziell **schlechter als Zufall**.

Plausible Erklärung, ohne sie überzustrapazieren: Alle drei Strategien steigen ein, *nachdem* eine Bewegung begonnen hat (Ausbruch, Momentum, Pullback-Ende). Wenn auf 5-Minuten-Ebene leichte Rückkehr zum Mittelwert herrscht, ist ein Einstieg nach der Bewegung systematisch ungünstiger als ein beliebiger Zeitpunkt.

**Bekannte Schwäche dieses Tests, die nicht nachträglich wegdefiniert wird:** Der Permutationstest zieht Einstiege gleichverteilt über die Handelssession, während die echten Strategien nur zu bestimmten Tageszeiten handeln (ORB z. B. erst nach den ersten 30 Minuten). Falls die Tagesrendite ungleich über die Session verteilt ist, verzerrt das den Vergleich — in unbekannter Richtung. Die Testkonstruktion stand so vorab in `VALIDATION_PROTOCOL.md` und wird **nicht** nach Kenntnis des Ergebnisses geändert; eine zeitfenster-gematchte Variante wäre eine eigene, erneut vorab zu registrierende Verfeinerung.

**Was das für die „mehr Daten"-Hypothese bedeutet:** Das Gate weist pro Konfiguration aus, wie viel Historie nötig wäre, um bei unverändertem Effekt t = 2 zu erreichen — die Spanne reicht von ~0,5 Jahren bis zu mehreren Jahrhunderten, bei 8 Konfigurationen lautet die Antwort „nie, der Netto-Edge ist nicht positiv". Diese Rechnung unterstellt aber, dass der gemessene Effekt echt ist. K7 sagt genau das Gegenteil. **Mehr Daten für dieselben Strategien zu kaufen, wäre daher voraussichtlich verschwendetes Geld** — die Evidenz spricht nicht für „noch nicht nachweisbar", sondern für „kein Effekt vorhanden".

## Was noch offen ist

1. **Keine der drei Strategien ist ein Forward-Test-Kandidat.** Weitere Symbole oder Zeiträume für *diese* Strategien zu testen, ist laut K7 voraussichtlich vergeudet — das Einstiegs-Timing trägt keine Information.
2. **Der belegte Hebel liegt in der Titelauswahl, nicht im Einstiegsmuster.** Die Literatur ist hier eindeutig: ungefiltertes ORB über ein festes Universum bringt 3,2 % p. a. (Sharpe 0,48), mit Filter auf *Opening Relative Volume* dagegen 41,6 % p. a. (Sharpe 2,81) — „opening relative volume did almost all the work". Unser System handelt stur dieselben Large Caps jeden Tag und besitzt diese Auswahlschicht überhaupt nicht. Das ist die nächste sinnvolle Baustelle, falls weitergebaut wird.
3. **Zeitfenster-gematchte Variante von K7** wäre eine sinnvolle methodische Verfeinerung (siehe Schwäche oben) — muss vorab registriert werden, bevor sie gerechnet wird.
4. **Monte-Carlo-Drawdown-Schwelle** bleibt eine offene Geschäftsentscheidung (wie DECISIONS.md #5/#6).
5. **Nicht mehr offen, sondern beantwortet:** Der Messapparat funktioniert. Er hat die zunächst vielversprechend aussehenden Kandidaten korrekt als Rauschen eingeordnet, und seine beiden statistischen Kernbausteine sind gegen analytisch bekannte Fälle verifiziert (Bootstrap-Korrektur folgt exakt √k über k = 1…25; Permutationstest erkennt echtes Timing mit p < 0,01 und beliebiges Timing mit p > 0,05).
