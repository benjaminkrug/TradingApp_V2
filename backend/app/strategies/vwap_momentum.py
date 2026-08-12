"""VWAP Momentum — ROADMAP.md Abschnitt 8, Strategie A.

BUY: close above session VWAP, fast EMA above slow EMA (uptrend), and the
fast EMA is still rising (momentum positive).
SELL: close drops back below session VWAP (lost the level).

Purely reactive to price action — see base.py for why no internal
position-tracking state is kept.
"""

from __future__ import annotations

from app.data.point_in_time import SimulationCursor
from app.features.indicators import ema_series, session_vwap


class VwapMomentumStrategy:
    def __init__(self, fast_period: int = 9, slow_period: int = 20):
        self.fast_period = fast_period
        self.slow_period = slow_period

    def __call__(self, cursor: SimulationCursor) -> str:
        history = cursor.history
        closes = [b.close for b in history]
        vwap = session_vwap(history)
        fast = ema_series(closes, self.fast_period)
        slow = ema_series(closes, self.slow_period)

        if vwap is None or not fast or not slow or fast[-1] is None or slow[-1] is None:
            return "HOLD"
        if len(fast) < 2 or fast[-2] is None:
            return "HOLD"

        current_close = closes[-1]
        uptrend = fast[-1] > slow[-1]
        momentum_positive = fast[-1] > fast[-2]

        if current_close > vwap and uptrend and momentum_positive:
            return "BUY"
        if current_close < vwap:
            return "SELL"
        return "HOLD"
