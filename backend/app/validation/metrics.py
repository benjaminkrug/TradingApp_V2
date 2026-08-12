"""Backtest performance metrics — ROADMAP.md Abschnitt 9's metrics list.

Operates on `Trade` objects (paired BUY/SELL fills), not raw `Fill`s,
because most metrics (win rate, profit factor, expectancy) are properties
of round trips, not of individual fills.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from app.backtest.reference_engine import Fill


@dataclass(frozen=True)
class Trade:
    symbol: str
    entry_time: datetime
    exit_time: datetime
    entry_price: float
    exit_price: float
    quantity: float
    pnl: float  # net of both fill fees - matches reference_engine's own realized_pnl accounting


def trades_from_fills(fills: list[Fill]) -> list[Trade]:
    """Pairs each BUY with the SELL that closes it. Expects `fills` to have
    come from a single symbol's backtest in chronological order
    (reference_engine guarantees this: no pyramiding, no shorting - see its
    own docstring) - an unmatched trailing BUY (position still open at the
    end of the data) is simply not turned into a Trade, matching
    reference_engine leaving it unrealized.

    That expectation is checked, not just assumed: a second BUY while a
    position is already open, or a SELL for a different symbol than the
    open position, raises rather than silently mispairing fills (e.g.
    dropping a position, or pairing a BUY on one symbol with a SELL on
    another if fills from multiple runs were ever merged together)."""
    trades: list[Trade] = []
    open_fill: Optional[Fill] = None
    for fill in fills:
        if fill.side == "BUY":
            if open_fill is not None:
                raise ValueError(
                    f"trades_from_fills: BUY for {fill.symbol} at {fill.timestamp} arrived while a "
                    f"position opened at {open_fill.timestamp} ({open_fill.symbol}) was still open. "
                    "This violates reference_engine's no-pyramiding guarantee - likely fills from "
                    "multiple symbols or multiple runs were merged together."
                )
            open_fill = fill
        elif fill.side == "SELL":
            if open_fill is None:
                continue  # matches reference_engine: a SELL with no open position is a no-op
            if fill.symbol != open_fill.symbol:
                raise ValueError(
                    f"trades_from_fills: SELL for {fill.symbol} at {fill.timestamp} does not match "
                    f"the open position's symbol {open_fill.symbol} - fills from different symbols "
                    "were likely merged together."
                )
            pnl = (fill.price - open_fill.price) * open_fill.quantity - open_fill.fee - fill.fee
            trades.append(
                Trade(
                    symbol=fill.symbol,
                    entry_time=open_fill.timestamp,
                    exit_time=fill.timestamp,
                    entry_price=open_fill.price,
                    exit_price=fill.price,
                    quantity=open_fill.quantity,
                    pnl=pnl,
                )
            )
            open_fill = None
    return trades


@dataclass(frozen=True)
class Metrics:
    trade_count: int
    win_rate: float  # 0..1
    profit_factor: Optional[float]  # gross profit / gross loss; None if there were no losing trades
    total_pnl: float
    average_trade: float
    expectancy: float  # identical to average_trade in this per-trade model
    max_consecutive_losses: int


def compute_metrics(trades: list[Trade]) -> Metrics:
    if not trades:
        return Metrics(
            trade_count=0,
            win_rate=0.0,
            profit_factor=None,
            total_pnl=0.0,
            average_trade=0.0,
            expectancy=0.0,
            max_consecutive_losses=0,
        )

    wins = [t for t in trades if t.pnl > 0]
    losses = [t for t in trades if t.pnl < 0]
    gross_profit = sum(t.pnl for t in wins)
    gross_loss = -sum(t.pnl for t in losses)  # positive number
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else None
    total_pnl = sum(t.pnl for t in trades)
    average_trade = total_pnl / len(trades)

    max_streak = 0
    current_streak = 0
    for t in trades:
        if t.pnl < 0:
            current_streak += 1
            max_streak = max(max_streak, current_streak)
        else:
            current_streak = 0

    return Metrics(
        trade_count=len(trades),
        win_rate=len(wins) / len(trades),
        profit_factor=profit_factor,
        total_pnl=total_pnl,
        average_trade=average_trade,
        expectancy=average_trade,
        max_consecutive_losses=max_streak,
    )
