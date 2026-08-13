"""FastAPI app entrypoint. Run locally with:

    cd backend && uvicorn app.api.main:app --reload

(requires `pip install -e .[dev]` - see PHASE8_NOTES.md for why this
could not be verified in the dev sandbox and how it was verified instead)
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import dashboard, signals, strategies, trades

app = FastAPI(
    title="TradingApp Backend API",
    description=(
        "Serves the Phase 8 web dashboard. All signal/dashboard data is "
        "computed against synthetic demo bars (app/api/demo_data.py), not "
        "real market data - see PHASE3_NOTES.md/PHASE8_NOTES.md."
    ),
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite dev server default port
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(strategies.router)
app.include_router(signals.router)
app.include_router(dashboard.router)
app.include_router(trades.router)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
