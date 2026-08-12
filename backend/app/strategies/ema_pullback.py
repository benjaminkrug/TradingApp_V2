"""EMA Pullback — ROADMAP.md Abschnitt 8, Strategie C.

BUY: uptrend (fast EMA above slow EMA), the previous bar's close was at or
below the fast EMA (a pullback touched it), and the current close has
moved back above the fast EMA (momentum resuming).
SELL: close drops below the slow EMA (trend broken).
"""

from __future__ import annotations

from app.data.point_in_time import SimulationCursor
from app.features.indicators import ema_series


class EmaPullbackStrategy:
    def __init__(self, fast_period: int = 9, slow_period: int = 20):
        self.fast_period = fast_period
        self.slow_period = slow_period

    def __call__(self, cursor: SimulationCursor) -> str:
        history = cursor.history
        closes = [b.close for b in history]
        fast = ema_series(closes, self.fast_period)
        slow = ema_series(closes, self.slow_period)

        if len(closes) < 2 or not fast or not slow:
            return "HOLD"
        if fast[-1] is None or fast[-2] is None or slow[-1] is None:
            return "HOLD"

        uptrend = fast[-1] > slow[-1]
        prev_close = closes[-2]
        current_close = closes[-1]
        pulled_back = prev_close <= fast[-2]
        resumed = current_close > fast[-1]

        if uptrend and pulled_back and resumed:
            return "BUY"
        if current_close < slow[-1]:
            return "SELL"
        return "HOLD"
