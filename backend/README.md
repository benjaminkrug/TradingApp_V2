# Backend

Python/FastAPI-Backend — siehe `../ROADMAP.md` Abschnitt 9 und `../DECISIONS.md`.

Tests ausführen (reine Standardbibliothek, kein `pip install` nötig):

```
cd backend && python3 -m unittest discover -s tests -v
```

Struktur (✅ = angelegt und getestet, 🟡 = angelegt, aber unverifiziert/Stub, ⏳ = geplant, wird in der genannten Phase befüllt):

- ✅ `app/data/point_in_time.py` — Point-in-Time-Datenzugriff / Look-Ahead-Schutz (Phase 2)
- ✅ `app/backtest/reference_engine.py` — Korrektheits-Referenz-Engine, nicht die produktive Engine (Phase 2)
- ✅ `app/data/calendar.py` — NYSE-Handelskalender, DST-bewusst (Phase 3)
- ✅ `app/data/corporate_actions.py` — Split-Rückrechnung (Phase 3)
- ✅ `app/data/universe.py` — Survivorship-bias-sicheres Punkt-in-Zeit-Universum, Mechanismus ohne echte Indexdaten (Phase 3)
- ✅ `app/data/quality.py` — Data-Quality-Checks (Phase 3)
- ✅ `app/data/providers/fake.py` — In-Memory-Provider für Tests (Phase 3)
- 🟡 `app/data/providers/alpaca.py`, `polygon.py` — dokumentierte Stubs, `NotImplementedError`; keine Netzwerk-/Key-Verifikation in dieser Sandbox möglich, siehe `../PHASE3_NOTES.md`
- ⏳ Produktive Backtest-Engine-Integration (Nautilus Trader oder Alternative) — offen, siehe `../PHASE2_NOTES.md`
- ✅ `app/features/indicators.py` — kausale Indikatoren: SMA, EMA, ATR, Session-VWAP, Opening Range, Relative Volume, Distance-in-ATR (Phase 4/6/7)
- ✅ `app/strategies/` — VWAP Momentum, EMA Pullback, Opening Range Breakout (Phase 4); Mean Reversion, Relative Volume Momentum (Phase 7) — alle end-to-end gegen synthetische Daten getestet
- ✅ `app/validation/` — Metrics, OOS-Sperre, Walk-Forward, Monte Carlo, Leakage-Detection, 12-Punkte-Gate (7/12 Punkte automatisiert, Rest ehrlich als `NOT_AUTOMATED` markiert, siehe `../PHASE5_NOTES.md`) (Phase 5)
- ✅ `app/signals/` — Scanner (statische Liste), Risk/Exit-Berechnung, Kill-Switch, Score-Kalibrierung (uncalibrated ohne echte Daten statt erfundener Werte), Signal-Zusammenstellung mit Begründung, siehe `../PHASE6_NOTES.md` (Phase 6)
- ✅ `scripts/phase7_synthetic_gate_run.py` — führt beide Phase-7-Strategien durch die volle Pipeline auf synthetischen Daten; beide fallen ehrlich durch (siehe `../PHASE7_NOTES.md`) (Phase 7)
- ✅ `app/api/` — FastAPI-Routen für Dashboard/Signals/Trade-Detail/Journal, gegen synthetische Demo-Daten (kein `pip install` in dieser Sandbox möglich, per CI verifiziert, siehe `../PHASE8_NOTES.md`) (Phase 8)
- ✅ `../frontend/` — Vue 3 + TypeScript + Vite Web-App (kein `npm install` in dieser Sandbox möglich, per CI verifiziert, siehe `../PHASE8_NOTES.md`) (Phase 8)
- ✅ `app/paper/` — Paper-Trading-Engine: Portfolio/Order-State, Stop/Target-Durchsetzung, Handelsende-Flatten, Kauf­kraft-Prüfung; nutzt dieselben Strategien/`build_signal()`/Fills wie Backtest und Phase-8-API (Phase 9)
- ✅ `scripts/phase9_paper_trading_demo.py` — Paper-Trading-Lauf gegen synthetische Demo-Daten über mehrere Symbole (siehe `../PHASE9_NOTES.md`) (Phase 9)
- ✅ `app/forward_test/` — Forward-Test-Tracking (`ingest()` pro echtem Datenabruf, Bereitschaftsprüfung gegen ROADMAP's 20-Trades/90-Tage-Kriterium, OOS-Vergleichsbericht); liefert Infrastruktur, kein abgeschlossenes Testergebnis, siehe `../PHASE10_NOTES.md` (Phase 10)
- ✅ `scripts/phase10_forward_test_demo.py` — tageweise gefütterter Forward-Test-Lauf gegen synthetische Daten (siehe `../PHASE10_NOTES.md`) (Phase 10)
- ✅ `app/signals/news_filter.py` — Pre-Trade-Gate (Earnings-Blackout, Volatilitätsexpansion [echt berechnet], News-Relevanz [ehrlich `NOT_AUTOMATED`]); optional in `PaperTradingEngine`/`ForwardTestSession` verdrahtet (Phase 11)
- ✅ `app/live_readiness/` — Go/No-Go-Checkliste vor echtem Kapitaleinsatz (PDT-sicheres Konto, Kill-Switch, News-Filter, Forward-Test-Bereitschaft; Broker-Anbindung und menschliche Freigabe bleiben ehrlich `NOT_AUTOMATED`) — **keine Order-Ausführung**, siehe `../PHASE11_NOTES.md` (Phase 11)
- ✅ `scripts/phase11_live_readiness_demo.py` — Forward-Test + Readiness-Report end-to-end auf synthetischen Daten (siehe `../PHASE11_NOTES.md`) (Phase 11)
