"""Split adjustment for historical OHLCV bars.

Why this is not a look-ahead violation, despite touching "past" bars using
a "future" corporate action: a split ratio is a static, already-known fact
by the time each bar's *signal* is evaluated in a real backtest (nobody
disputes that AAPL split 4-for-1 in 2020 — that's not new information, it's
a bookkeeping adjustment). What this module produces is a continuous,
comparable price series to feed into the point-in-time layers, not a
prediction or a piece of information about what will happen next. The
distinction is easy to blur, so it is worth stating explicitly rather than
assuming it is obvious.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.data.point_in_time import Bar


@dataclass(frozen=True)
class Split:
    symbol: str
    effective_date: date
    ratio: float  # e.g. 2.0 for a 2-for-1 split, 0.1 for a 1-for-10 reverse split


def adjust_for_splits(bars: list[Bar], splits: list[Split]) -> list[Bar]:
    """Back-adjusted bars: for each bar strictly before a split's effective
    date, price fields are divided and volume is multiplied by the
    cumulative ratio of all such splits, so the whole series is expressed
    in terms of today's share count. `bars` must all share one symbol
    (same precondition as `PointInTimeSeries`) and `splits` must match
    that symbol.
    """
    if not bars:
        return []

    symbol = bars[0].symbol
    if any(b.symbol != symbol for b in bars):
        raise ValueError("adjust_for_splits requires all bars to share one symbol")

    relevant_splits = sorted(
        (s for s in splits if s.symbol == symbol),
        key=lambda s: s.effective_date,
    )
    if not relevant_splits:
        return list(bars)

    adjusted: list[Bar] = []
    for bar in bars:
        bar_date = bar.timestamp.date()
        cumulative_ratio = 1.0
        for split in relevant_splits:
            if bar_date < split.effective_date:
                cumulative_ratio *= split.ratio
        if cumulative_ratio == 1.0:
            adjusted.append(bar)
        else:
            adjusted.append(
                Bar(
                    symbol=bar.symbol,
                    timestamp=bar.timestamp,
                    open=bar.open / cumulative_ratio,
                    high=bar.high / cumulative_ratio,
                    low=bar.low / cumulative_ratio,
                    close=bar.close / cumulative_ratio,
                    volume=bar.volume * cumulative_ratio,
                )
            )
    return adjusted
