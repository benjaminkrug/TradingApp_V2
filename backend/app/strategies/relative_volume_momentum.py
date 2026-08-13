"""Relative Volume Momentum — Phase 7 AI-generated strategy hypothesis.

ROADMAP.md Abschnitt 4/6 lists relative volume as a core scanner/signal
factor, but none of the Phase 4 strategies actually trade off it directly
- VWAP Momentum and EMA Pullback trigger on price/EMA relationships,
Opening Range Breakout on a price level. This strategy's primary signal
is an unusual-activity anomaly (a volume spike), with price action only
used as directional confirmation and an EMA as a trend filter - a
different kind of bet on "something changed" rather than "the existing
trend continues" or "price stretched too far."

BUY: relative volume is at least `volume_multiple`x the recent average
(app/features/indicators.py's relative_volume), the bar closed higher
than it opened (the spike came with buying, not just noisy activity),
and price is above its EMA (only take volume spikes in the direction of
the prevailing trend).
SELL: relative volume has fallen back below the spike threshold and
price has closed below its EMA - both the anomaly and the trend support
that justified the entry are gone.
"""

from __future__ import annotations

from app.data.point_in_time import SimulationCursor
from app.features.indicators import ema_series, relative_volume


class RelativeVolumeMomentumStrategy:
    def __init__(self, ema_period: int = 20, volume_lookback: int = 20, volume_multiple: float = 2.0):
        self.ema_period = ema_period
        self.volume_lookback = volume_lookback
        self.volume_multiple = volume_multiple

    def __call__(self, cursor: SimulationCursor) -> str:
        history = cursor.history
        rv = relative_volume(history, self.volume_lookback)
        if rv is None:
            return "HOLD"

        closes = [b.close for b in history]
        fast = ema_series(closes, self.ema_period)
        if not fast or fast[-1] is None:
            return "HOLD"

        current = history[-1]
        above_ema = current.close > fast[-1]
        positive_bar = current.close > current.open
        volume_spike = rv >= self.volume_multiple

        if volume_spike and positive_bar and above_ema:
            return "BUY"
        if rv < self.volume_multiple and not above_ema:
            return "SELL"
        return "HOLD"
