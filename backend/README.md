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
