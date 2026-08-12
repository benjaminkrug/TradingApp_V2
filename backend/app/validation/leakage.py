"""Leakage detection — empirically verify a strategy only used data that
was actually available at each decision.

point_in_time.py is honest that its look-ahead guard "holds as long as
calling code only uses the public API" — nothing stops a strategy from
capturing a bar list via closure or reaching into `cursor._bars` directly.
This module checks empirically, treating the strategy as a black box: run
it once on the full series and once on a truncated prefix, and compare
the fills produced strictly before the truncation boundary (with a small
buffer — see `boundary_buffer` below). A strategy whose decisions only
ever depend on `cursor.history` must produce byte-for-byte identical
fills in that shared region, because at every position before the
boundary both runs are looking at literally the same bars. Any
difference — extra fills, missing fills, or a fill with a different
price/side — means the strategy's decision at some point depended on data
that would not have existed if the series had actually ended at
`cut_index`.

The `boundary_buffer` exists because of a legitimate, non-leaky edge
effect: reference_engine fills a signal at the *next* bar's open, so a
signal generated on the last bar or two of the prefix may simply have no
next bar to fill at there, while the full run (which keeps going) does
fill it. That is truncation, not leakage, and is excluded from the
comparison rather than mistaken for a bug.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Optional

from app.backtest.reference_engine import Fill, run_reference_backtest
from app.data.point_in_time import Bar, SimulationCursor

StrategyFactory = Callable[[], Callable[[SimulationCursor], str]]


@dataclass(frozen=True)
class LeakageMismatch:
    index: int
    prefix_fill: Optional[Fill]
    full_run_fill: Optional[Fill]


@dataclass(frozen=True)
class LeakageReport:
    mismatches: list[LeakageMismatch]

    @property
    def clean(self) -> bool:
        return len(self.mismatches) == 0


def _fill_key(fill: Fill) -> tuple[str, str, float, datetime]:
    return (fill.symbol, fill.side, fill.price, fill.timestamp)


def detect_leakage(
    bars: list[Bar],
    strategy_factory: StrategyFactory,
    cut_index: int,
    fee_per_share: float = 0.0,
    boundary_buffer: int = 1,
) -> LeakageReport:
    if not (0 < cut_index < len(bars)):
        raise ValueError("cut_index must be strictly between 0 and len(bars)")

    full_result = run_reference_backtest(bars, strategy_factory(), fee_per_share=fee_per_share)
    prefix_result = run_reference_backtest(bars[:cut_index], strategy_factory(), fee_per_share=fee_per_share)

    boundary_bar_index = max(cut_index - 1 - boundary_buffer, 0)
    boundary_time = bars[boundary_bar_index].timestamp

    full_before = [f for f in full_result.fills if f.timestamp <= boundary_time]
    prefix_before = [f for f in prefix_result.fills if f.timestamp <= boundary_time]

    mismatches: list[LeakageMismatch] = []
    for i in range(max(len(full_before), len(prefix_before))):
        f = full_before[i] if i < len(full_before) else None
        p = prefix_before[i] if i < len(prefix_before) else None
        if f is None or p is None or _fill_key(f) != _fill_key(p):
            mismatches.append(LeakageMismatch(index=i, prefix_fill=p, full_run_fill=f))

    return LeakageReport(mismatches=mismatches)
