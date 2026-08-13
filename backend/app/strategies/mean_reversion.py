"""Mean Reversion (ATR Z-Score) — Phase 7 AI-generated strategy hypothesis.

ROADMAP.md Abschnitt 8, "Strategie E – Mean Reversion": explicitly called
out as needing separate treatment from the trend/momentum strategies,
because it needs a different market regime (choppy/range-bound, not
trending). This is not a parameter variation of VwapMomentumStrategy,
EmaPullbackStrategy, or OpeningRangeBreakoutStrategy — those all buy
strength and bet on continuation; this buys weakness and bets on
reversion. It is expected to lose money in a strongly trending market and
is not claimed to be profitable — see PHASE7_NOTES.md for the (synthetic,
not real-market) gate results.

BUY: price has stretched at least `oversold_atr_multiple` ATRs below its
EMA (unusually far, not just normal noise - see
app/features/indicators.py's distance_in_atr), and the current bar closes
above the previous bar's close (a confirmed turn, not an attempt to catch
the exact bottom).
SELL: price has reverted back to at or above the EMA (distance_in_atr >=
0) - the reversion this strategy bets on has completed.
"""

from __future__ import annotations

from app.data.point_in_time import SimulationCursor
from app.features.indicators import distance_in_atr


class MeanReversionStrategy:
    def __init__(self, ema_period: int = 20, atr_period: int = 14, oversold_atr_multiple: float = 2.0):
        self.ema_period = ema_period
        self.atr_period = atr_period
        self.oversold_atr_multiple = oversold_atr_multiple

    def __call__(self, cursor: SimulationCursor) -> str:
        history = cursor.history
        if len(history) < 2:
            return "HOLD"

        z = distance_in_atr(history, self.ema_period, self.atr_period)
        if z is None:
            return "HOLD"

        current_close = history[-1].close
        prev_close = history[-2].close
        oversold = z <= -self.oversold_atr_multiple
        turned_up = current_close > prev_close

        if oversold and turned_up:
            return "BUY"
        if z >= 0:
            return "SELL"
        return "HOLD"
