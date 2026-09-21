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

## Was noch offen ist

1. **Weitere Symbole gegen Opening Range Breakout testen** (`PYTHONPATH=. python scripts/real_data_gate_run.py SYMBOL`) — 2/3 ist eine schwache Basis, keine Validierung. VWAP Momentum und EMA Pullback nicht mehr priorisieren, solange sie mehrheitlich durchfallen.
2. **Andere Zeiträume testen**, nicht nur überlappende ~6,5-Monats-Fenster — aktuell keine Aussage über unterschiedliche Marktphasen (z. B. Bär- vs. Bullenmarkt) möglich.
3. **Monte-Carlo-Drawdown-Schwelle** ist eine offene Geschäftsentscheidung (wie DECISIONS.md #5/#6) — mit dem Nutzer klären, falls gewünscht, bevor eine Strategie als vollständig automatisiert-geprüft gilt.
4. **Erst danach:** Falls Opening Range Breakout auf weiteren Symbolen/Zeiträumen mehrheitlich besteht, als Kandidat für den echten Forward-Test (Phase C, `ForwardTestSession`) auswählen. Aktuell (Stand 21.09.2026) ist noch keine Strategie so weit — das ist ein ehrliches Zwischenergebnis, kein Fehler in der Pipeline.
