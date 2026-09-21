# Echte-Daten-Validierung der Phase-4-Strategien — Status & offene Punkte

Referenz: `ROADMAP.md` Abschnitt 8 (Pipeline-Reihenfolge: In-Sample → Validation → Out-of-Sample → Forward Test) und Abschnitt 14 (Forward Test soll OOS-Ergebnisse *bestätigen*, nicht selbst validieren).

## Warum dieser Schritt existiert

Alle bisherigen Gate-Läufe (Phase 5/6/7) liefen ausschließlich gegen synthetische Zufallsdaten, weil `AlpacaProvider` bis 21.09.2026 nur ein Stub war (siehe `PHASE3_NOTES.md`). Das hat bewiesen, dass die Validierungs-Pipeline selbst korrekt funktioniert — aber nie, ob irgendeine Strategie auf echten Marktdaten tatsächlich funktioniert. Ein Forward-Test (Wochen/Monate über echte Zeit) einer Strategie, die nie auf echten Daten validiert wurde, hätte nichts zu bestätigen. Deshalb: erst dieser Schritt, dann erst Phase C (Forward-Test-Cronjob).

## Was gemacht wurde

`backend/scripts/real_data_gate_run.py` — analog zu `scripts/phase7_synthetic_gate_run.py`, aber mit echten Bars von `AlpacaProvider` statt einem synthetischen Random Walk. Lädt `.env`, holt 5-Minuten-Bars für ein Symbol über ~200 Kalendertage, teilt 70/30 in In-Sample/OOS (`OosSplit`), bildet Walk-Forward-Fenster (Train 40 / Test 10 / Step 10 Tage), lässt alle drei Phase-4-Strategien durch `evaluate_candidate()` laufen.

**Erster echter Lauf, 21.09.2026, Symbol AAPL, 05.03.2026–21.09.2026, 11.459 echte 5-Min-Bars:**

| Strategie | Leakage | Ausreichend Trades | OOS positiv | Walk-Forward stabil | Gate bestanden |
|---|---|---|---|---|---|
| VWAP Momentum | ✅ sauber | ✅ 245 Trades | ✅ Expectancy +0,089 über 123 Trades | ❌ nur 2/5 Fenster profitabel | ❌ **FAIL** |
| EMA Pullback | ✅ sauber | ✅ 216 Trades | ✅ Expectancy +0,181 über 95 Trades | ✅ 3/5 Fenster profitabel | ✅ **PASS** (aller automatisierbaren Punkte) |
| Opening Range Breakout | ✅ sauber | ✅ 116 Trades | ✅ Expectancy +0,254 über 44 Trades | ✅ 3/5 Fenster profitabel | ✅ **PASS** (aller automatisierbaren Punkte) |

Monte Carlo bewusst **NOT_AUTOMATED** gelassen (kein `monte_carlo_drawdown_threshold` übergeben) — welcher maximale Drawdown "akzeptabel" ist, ist eine Risikotoleranz-Entscheidung, die bisher niemand getroffen hat (kein DECISIONS.md-Eintrag dafür). Das wäre sonst dieselbe Art unbestätigter Geschäftsentscheidung, vor der `compare_to_oos()`s eigener Docstring schon warnt.

**Wichtig, damit dieses Ergebnis nicht überinterpretiert wird:**
- Nur **ein** Symbol (AAPL), nur **ein** Zeitraum (~6,5 Monate). Kein Beleg, dass EMA Pullback oder Opening Range Breakout auf anderen Symbolen oder Zeiträumen ebenso abschneiden würden.
- `sufficient_trades`, `oos_positive`, `walk_forward_stable` sind PASS/FAIL — aber `no_survivorship_bias`, `realistic_slippage`, `realistic_execution`, `multiple_regimes_tested`, `paper_trading_confirmed` bleiben weiterhin `NOT_AUTOMATED`. "Gate bestanden" heißt hier: alle *automatisierbaren* Punkte bestanden, nicht alle 12 Punkte der Roadmap-Checkliste.
- `reference_engine.py` (verwendet in `evaluate_candidate`) handelt immer exakt 1 Einheit pro Trade, keine risikobasierte Positionsgröße wie später im echten Paper-Trading (`app/signals/risk.py`) — Expectancy-Werte sind auf dieser Skala zu lesen, nicht direkt auf Dollar-Ergebnisse übertragbar (gleicher Hinweis wie in `app/forward_test/session.py`s `_MAGNITUDE_CAVEAT`).

## Wichtige Korrektur zur Umgebung (siehe auch `PHASE3_NOTES.md`)

Beim ersten "Smoke-Test" dieses Skripts mit angeblich synthetischen Daten lief versehentlich ein echter Alpaca-Call — Claude kann `.env`-Secrets in dieser Umgebung tatsächlich lesen, sobald die Datei gespeichert ist (keine Sandbox-Sperre, wie zuvor fälschlich dokumentiert). Der Call war harmlos (nur Kursdaten lesen, keine Order), aber ungeplant. Für künftige Arbeit mit echten Zugangsdaten: bewusst vorsichtig bleiben, nicht auf eine technische Bremse verlassen, die es nicht gibt.

## Was noch offen ist

1. **Mehr Symbole/Zeiträume testen**, bevor EMA Pullback oder Opening Range Breakout als "validiert" gelten — ein Symbol/ein Zeitraum ist eine erste Stichprobe, kein Beweis.
2. **Monte-Carlo-Drawdown-Schwelle** ist eine offene Geschäftsentscheidung (wie DECISIONS.md #5/#6) — mit dem Nutzer klären, falls gewünscht, bevor eine Strategie als vollständig automatisiert-geprüft gilt.
3. **Erst danach:** Eine der beiden PASS-Strategien (EMA Pullback oder Opening Range Breakout) als Kandidat für den echten Forward-Test (Phase C, `ForwardTestSession`) auswählen — das ist der nächste sinnvolle Schritt laut Roadmap-Reihenfolge.
