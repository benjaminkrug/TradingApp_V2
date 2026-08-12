"""Opening Range Breakout — ROADMAP.md Abschnitt 8, Strategie B.

BUY: close breaks above the opening range high (the first `range_bars`
bars of the session), with volume at or above the opening range's average
volume (confirmation).
SELL: close falls back below the opening range high (failed breakout).

Only evaluated on bars strictly *after* the opening range has finished
forming. Evaluating it on the range-forming bars themselves would be a
subtle bug, not a look-ahead one: the range high for bar `range_bars - 1`
is computed *including that same bar's own high*, so its own close would
almost always sit at or below a range high partly derived from itself,
firing a meaningless SELL on the very bar that just defined the range.
"""

from __future__ import annotations

from app.data.point_in_time import SimulationCursor
from app.features.indicators import current_session_bars, opening_range


class OpeningRangeBreakoutStrategy:
    def __init__(self, range_bars: int = 6, volume_confirmation_multiple: float = 1.0):
        self.range_bars = range_bars
        self.volume_confirmation_multiple = volume_confirmation_multiple

    def __call__(self, cursor: SimulationCursor) -> str:
        history = cursor.history
        session_bars = current_session_bars(history)
        if len(session_bars) <= self.range_bars:
            return "HOLD"  # still forming (or exactly finishing) the range

        rng = opening_range(history, self.range_bars)
        assert rng is not None  # guaranteed by the length check above
        _, range_high = rng

        opening_bars = session_bars[: self.range_bars]
        avg_opening_volume = sum(b.volume for b in opening_bars) / len(opening_bars)

        current = history[-1]
        breakout = current.close > range_high
        volume_confirmed = current.volume >= avg_opening_volume * self.volume_confirmation_multiple

        if breakout and volume_confirmed:
            return "BUY"
        if current.close < range_high:
            return "SELL"
        return "HOLD"
