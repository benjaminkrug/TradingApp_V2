"""Minimal reference backtest loop — a correctness oracle, not the product.

ROADMAP.md Abschnitt 9 calls for building on an established event-driven
framework (Nautilus Trader is the current candidate) instead of writing a
backtest engine from scratch, because that component is the most bug-prone
part of the whole system. This module is deliberately NOT that engine — its
job is narrower: implement the simplest possible correct bar-by-bar
simulation whose output for a hand-picked scenario can be checked by hand,
so there is *something* to cross-validate a heavier framework against later.

Execution model: `signal_fn` decides using data available up to and
including the bar just processed (never future bars — enforced by
SimulationCursor, see point_in_time.py). The resulting BUY/SELL is *not*
filled at that same bar's close. It is queued and filled at the *next*
bar's open. This mirrors "trade the following candle's open", the
convention documented in ROADMAP.md Abschnitt 2 based on the DaviddTech
transcripts, and avoids the zero-latency same-bar-close fill assumption
flagged there as one driver of unrealistically good backtests (see also
Abschnitt 13: acting on a bar's own close using that bar's own data,
combined with a tight trailing stop, was a concrete contributor to the
2,000,000%-return, obviously-broken backtest in that reference material).

This is an execution-*realism* concern, distinct from the look-ahead
guarantee: the strategy still never sees future bars when deciding: only
the engine's execution timing (which the strategy does not control) uses
the next bar's open. A signal generated on the final bar of the series has
no next bar to fill at and is therefore never executed — intentional,
covered by tests below, not a bug.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Literal, Optional

from app.data.point_in_time import Bar, PointInTimeSeries, SimulationCursor

Action = Literal["BUY", "SELL", "HOLD"]
SignalFn = Callable[[SimulationCursor], Action]


@dataclass
class Fill:
    timestamp: datetime
    side: Literal["BUY", "SELL"]
    price: float
    quantity: float
    fee: float


@dataclass
class BacktestResult:
    fills: list[Fill] = field(default_factory=list)
    realized_pnl: float = 0.0


def run_reference_backtest(
    bars: list[Bar],
    signal_fn: SignalFn,
    fee_per_share: float = 0.0,
) -> BacktestResult:
    """Long-only, single-unit, next-bar-open-fill reference simulation.

    No pyramiding (a BUY signal while already long is ignored) and no
    shorting (a SELL signal while flat is ignored) — both deliberate scope
    limits for a correctness oracle, not yet a statement about the
    production risk/position-sizing model (ROADMAP.md Abschnitt 12/17).
    """
    series = PointInTimeSeries(bars)
    cursor = series.new_cursor()
    result = BacktestResult()

    position = 0.0
    entry_price = 0.0
    pending_action: Optional[Action] = None

    for bar in cursor:
        if pending_action == "BUY" and position == 0:
            position = 1.0
            entry_price = bar.open
            result.fills.append(Fill(bar.timestamp, "BUY", bar.open, position, fee_per_share))
        elif pending_action == "SELL" and position > 0:
            pnl = (bar.open - entry_price) * position - 2 * fee_per_share
            result.realized_pnl += pnl
            result.fills.append(Fill(bar.timestamp, "SELL", bar.open, position, fee_per_share))
            position = 0.0

        pending_action = signal_fn(cursor)

    # A pending_action decided on the final bar has no next bar to fill at
    # and is deliberately dropped here, not executed at, say, that bar's own
    # close — see module docstring.
    return result
