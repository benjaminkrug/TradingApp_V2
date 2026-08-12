# Backend

Python/FastAPI-Backend — siehe `../ROADMAP.md` Abschnitt 9 und `../DECISIONS.md`.

Tests ausführen (reine Standardbibliothek, kein `pip install` nötig):

```
cd backend && python3 -m unittest discover -s tests -v
```

Struktur (✅ = angelegt und getestet, ⏳ = geplant, wird in der genannten Phase befüllt):

- ✅ `app/data/point_in_time.py` — Point-in-Time-Datenzugriff / Look-Ahead-Schutz (Phase 2)
- ✅ `app/backtest/reference_engine.py` — Korrektheits-Referenz-Engine, nicht die produktive Engine (Phase 2)
- ⏳ Produktive Backtest-Engine-Integration (Nautilus Trader oder Alternative) — offen, siehe `../PHASE2_NOTES.md`
- ⏳ `app/strategies/` — Strategy-Definitionen (Phase 4)
- ⏳ `app/validation/` — OOS/Walk-Forward/Monte-Carlo-Gates (Phase 5)
- ⏳ `app/signals/` — Signal Engine & Scoring (Phase 6)
- ⏳ `app/api/` — FastAPI-Routen (Phase 8)
