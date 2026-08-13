"""GET /api/dashboard — market overview panel (ROADMAP.md Abschnitt 19)."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.api.registry import STRATEGY_REGISTRY
from app.api.routes.signals import DEMO_ACCOUNT_EQUITY, DEMO_RISK_PCT, _signal_for_symbol
from app.api.schemas import DashboardOut
from app.signals.scanner import STATIC_UNIVERSE

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardOut)
def get_dashboard(
    strategy: str = Query(default="vwap_momentum"),
    scan_limit: int = Query(default=10, ge=1, le=len(STATIC_UNIVERSE)),
) -> DashboardOut:
    """Portfolio-level metrics (equity curve, open positions, realized PnL)
    are intentionally NOT included here - there is no paper-trading engine
    yet to produce them (Phase 9), and fabricating placeholder numbers for
    them would violate this project's own honesty rule (see
    app/validation/gate.py's docstring for the same principle applied
    elsewhere)."""
    signal_count = sum(
        1
        for symbol in STATIC_UNIVERSE[:scan_limit]
        if _signal_for_symbol(symbol, strategy, DEMO_ACCOUNT_EQUITY, DEMO_RISK_PCT) is not None
    )
    validated_count = sum(1 for info in STRATEGY_REGISTRY.values() if info.validated)
    return DashboardOut(
        universe_size=len(STATIC_UNIVERSE),
        strategy_count=len(STRATEGY_REGISTRY),
        validated_strategy_count=validated_count,
        signal_count=signal_count,
        data_source="synthetic_demo",
        notes=[
            "Portfolio metrics (equity, open positions, realized PnL) require paper trading "
            "(Phase 9) - not shown.",
            "Signals are computed against synthetic demo data, not real market data - see "
            "PHASE3_NOTES.md.",
            f"{validated_count} of {len(STRATEGY_REGISTRY)} strategies have passed the full "
            "validation gate on synthetic data (see PHASE7_NOTES.md); none are recommended "
            "for use.",
        ],
    )
