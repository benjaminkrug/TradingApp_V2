# Frontend

Vue 3 + TypeScript + Vite — see `../ROADMAP.md` Abschnitt 19 and `../DECISIONS.md`.

**Not verified locally.** The dev sandbox this was built in cannot reach the
npm registry (`registry.npmjs.org` returns `403 host_not_allowed` — the same
network policy that blocks PyPI/Alpaca/Polygon, see `../PHASE2_NOTES.md` and
`../PHASE8_NOTES.md`), so `npm install` could never be run here. Verified
instead by the `frontend-build` job in `../.github/workflows/ci.yml`
(`npm install && npm run type-check && npm run build`), which runs on GitHub
Actions where the registry is reachable.

Local development (once installable):

```
cd frontend
cp .env.example .env   # only needed if the backend isn't on localhost:8000
npm install
npm run dev             # http://localhost:5173
```

Run the backend API alongside it (`cd backend && pip install -e .[dev] && uvicorn app.api.main:app --reload`)
so the dashboard has something to call — see `../backend/README.md`.

Structure:

- `src/api/client.ts` — fetch wrapper around `backend/app/api/`
- `src/types.ts` — hand-kept mirror of `backend/app/api/schemas.py`'s Pydantic models
- `src/views/DashboardView.vue` — market overview panel
- `src/views/SignalsView.vue` — scanner results per strategy
- `src/views/TradeDetailView.vue` — entry/stop/target/rationale + candlestick chart (`src/components/PriceChart.vue`, TradingView Lightweight Charts per `../DECISIONS.md`)
- `src/views/JournalView.vue` — trade journal (currently always empty — no paper trading yet, Phase 9)

All data shown is clearly labeled `data_source: "synthetic_demo"` — see `../PHASE8_NOTES.md` for why.
