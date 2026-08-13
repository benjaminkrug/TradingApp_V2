"""GET /api/signals, GET /api/signals/{symbol} — scanner + Trade Detail View
backing endpoints (ROADMAP.md Abschnitt 19, Phase 8).

`account_equity`/`risk_pct` default to illustrative placeholder values
only — DECISIONS.md marks the risk-per-trade figure as provisional (never
individually confirmed by the user), and app/signals/risk.py deliberately
never defaults it either. Query params let a caller override both; the
defaults here exist only so the endpoint is usable without every caller
having to pass them, not as a confirmed recommendation.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.api.demo_data import generate_demo_bars
from app.api.registry import STRATEGY_REGISTRY
from app.api.schemas import BarOut, SignalOut
from app.data.point_in_time import SimulationCursor
from app.signals.scanner import STATIC_UNIVERSE
from app.signals.signal import build_signal

router = APIRouter(prefix="/api/signals", tags=["signals"])

DEMO_ACCOUNT_EQUITY = 50_000.0
DEMO_RISK_PCT = 0.005


def _signal_for_symbol(
    symbol: str, strategy_name: str, account_equity: float, risk_pct: float
) -> Optional[SignalOut]:
    info = STRATEGY_REGISTRY.get(strategy_name)
    if info is None:
        raise HTTPException(status_code=404, detail=f"unknown strategy '{strategy_name}'")

    bars = generate_demo_bars(symbol)
    if not bars:
        return None

    strategy = info.factory()
    cursor = SimulationCursor(bars)
    last_signal = None
    for _ in cursor:
        action = strategy(cursor)
        sig = build_signal(
            cursor,
            action,
            strategy_name=info.name,
            account_equity=account_equity,
            risk_pct=risk_pct,
        )
        if sig is not None:
            last_signal = sig

    if last_signal is None:
        return None

    return SignalOut(
        symbol=last_signal.symbol,
        strategy_name=last_signal.strategy_name,
        entry=last_signal.entry,
        stop=last_signal.stop,
        target=last_signal.target,
        risk_reward=last_signal.risk_reward,
        shares=last_signal.shares,
        score=last_signal.score,
        confidence=last_signal.confidence,
        relative_volume=last_signal.relative_volume,
        rationale=last_signal.rationale,
        data_source="synthetic_demo",
        account_equity=account_equity,
        risk_pct=risk_pct,
    )


@router.get("", response_model=list[SignalOut])
def list_signals(
    strategy: str = Query(default="vwap_momentum"),
    limit: int = Query(default=10, ge=1, le=len(STATIC_UNIVERSE)),
    account_equity: float = Query(default=DEMO_ACCOUNT_EQUITY, gt=0),
    risk_pct: float = Query(default=DEMO_RISK_PCT, gt=0, lt=1),
) -> list[SignalOut]:
    """Scans the static universe (DECISIONS.md #1) against synthetic demo
    data (app/api/demo_data.py) and returns the most recent BUY signal per
    symbol, if any. NOT real market data or a real trading recommendation
    - see each response's `data_source` field."""
    results: list[SignalOut] = []
    for symbol in STATIC_UNIVERSE[:limit]:
        sig = _signal_for_symbol(symbol, strategy, account_equity, risk_pct)
        if sig is not None:
            results.append(sig)
    return results


@router.get("/{symbol}", response_model=SignalOut)
def get_signal(
    symbol: str,
    strategy: str = Query(default="vwap_momentum"),
    account_equity: float = Query(default=DEMO_ACCOUNT_EQUITY, gt=0),
    risk_pct: float = Query(default=DEMO_RISK_PCT, gt=0, lt=1),
) -> SignalOut:
    """Trade Detail View backing endpoint — full entry/stop/target/rationale
    for one symbol."""
    symbol = symbol.upper()
    sig = _signal_for_symbol(symbol, strategy, account_equity, risk_pct)
    if sig is None:
        raise HTTPException(
            status_code=404,
            detail=f"no current BUY signal for '{symbol}' under strategy '{strategy}'",
        )
    return sig


@router.get("/{symbol}/bars", response_model=list[BarOut])
def get_bars(symbol: str, num_trading_days: int = Query(default=10, ge=1, le=60)) -> list[BarOut]:
    """Backs the Trade Detail View's chart. Same synthetic demo data as
    the signal endpoints - see app/api/demo_data.py."""
    symbol = symbol.upper()
    bars = generate_demo_bars(symbol, num_trading_days=num_trading_days)
    return [
        BarOut(timestamp=b.timestamp.isoformat(), open=b.open, high=b.high, low=b.low, close=b.close, volume=b.volume)
        for b in bars
    ]
