"""Minimal reference backtest loop — a correctness oracle, not the product.

ROADMAP.md Abschnitt 9 calls for building on an established event-driven
framework (Nautilus Trader is the current candidate) instead of writing a
backtest engine from scratch, because that component is the most
bug-prone part of the whole system. This module is deliberately NOT that
engine.

Its job is narrower: implement the simplest possible bar-by-bar simulation,
whose output for a hand-picked scenario can be computed by hand and checked
against. Once Nautilus Trader (or whichever framework is chosen) is
integrated, its output on the same synthetic scenario must match this
reference within tolerance before it is trusted for anything else — see
PHASE2_NOTES.md for why that verification could not be completed yet.

signal_fn only ever receives a SimulationCursor (see point_in_time.py), so a
strategy plugged in here has no code path to future data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Literal

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
    """Long-only, single-unit, fill-at-close reference simulation.

    Fill-at-close (not intra-bar) is a deliberate simplification here: it
    sidesteps the exact TradingView limitation flagged in ROADMAP.md
    Abschnitt 2 (OHLC-only bars make intra-bar fills, e.g. with tight
    trailing stops, unverifiable). The production engine will need a more
    realistic execution model — this reference only has to be *correct*,
    not *realistic*.
    """
    series = PointInTimeSeries(bars)
    cursor = series.new_cursor()
    result = BacktestResult()

    position = 0.0
    entry_price = 0.0

    while True:
        try:
            bar = cursor.advance()
        except StopIteration:
            break

        action = signal_fn(cursor)

        if action == "BUY" and position == 0:
            position = 1.0
            entry_price = bar.close
            result.fills.append(Fill(bar.timestamp, "BUY", bar.close, position, fee_per_share))
        elif action == "SELL" and position > 0:
            pnl = (bar.close - entry_price) * position - 2 * fee_per_share
            result.realized_pnl += pnl
            result.fills.append(Fill(bar.timestamp, "SELL", bar.close, position, fee_per_share))
            position = 0.0

    return result
