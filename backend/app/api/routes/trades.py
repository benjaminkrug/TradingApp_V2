"""GET /api/trades — Trade Journal (ROADMAP.md Abschnitt 19)."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.schemas import TradeJournalOut

router = APIRouter(prefix="/api/trades", tags=["trades"])


@router.get("", response_model=TradeJournalOut)
def get_trade_journal() -> TradeJournalOut:
    """Deliberately returns an empty list: there is no paper-trading engine
    yet (Phase 9) to produce real trade history, and inventing example
    trade records here would misrepresent this as live/demo trading
    activity rather than what it actually is - a UI shell waiting for
    Phase 9's real data source."""
    return TradeJournalOut(
        entries=[], note="No trades recorded yet - paper trading is not implemented (Phase 9)."
    )
