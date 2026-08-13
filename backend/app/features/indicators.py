"""Causal technical indicators.

"Causal" here means every function operates on a history that already
stops at "now" — the caller is expected to pass `cursor.history` (see
point_in_time.py), not a full pre-computed series. There is no rolling
window computed once over an entire series and then indexed into, which is
exactly the kind of thing that can silently leak a few bars of future data
if a window boundary is sliced wrong. Every function here recomputes from
exactly the history it was given, nothing more.

Performance note: `ema_series` recomputes the whole series from scratch on
every call, which is O(n) per call and O(n^2) if called once per bar over
a backtest of n bars. Fine for the small, hand-verifiable scenarios these
strategies are tested against here; would need incremental/stateful
indicator updates before running this against a real multi-thousand-bar
backtest — left as a known limitation rather than optimized prematurely.

Only the indicators actually used by the strategies in app/strategies/
are implemented here (EMA, session VWAP, ATR, opening range, relative
volume, distance-in-ATR) — not a general TA library. More get added when
a strategy actually needs them (see PHASE4_NOTES.md/PHASE7_NOTES.md).

Session-scoping note: `session_vwap` and `opening_range` deliberately
reset every session (via `current_session_bars`) because VWAP and an
opening range are inherently session-cumulative concepts by definition -
"today's volume-weighted average price" has no meaning carried over from
yesterday. `ema_series`, `atr`, `relative_volume`, and `distance_in_atr`
deliberately do NOT reset at session boundaries: they are rolling-window
concepts with no inherent daily reset convention, and carrying them
across days is standard practice (a 20-period EMA spanning multiple
sessions is the normal way to compute one). One practical consequence
worth knowing: at the very first bar of a new session, `MeanReversionStrategy`'s
"did price just turn up" check compares that bar's close against the
previous session's last close - an overnight gap can look like a same-day
"turn" even though no intraday reversal happened. Not fixed here because
"close every position by end of day" (ROADMAP.md's actual intraday
constraint) isn't enforced by any layer yet - that belongs to a future
Risk/Exit Engine, not to this indicator module.
"""

from __future__ import annotations

from typing import Optional

from app.data.calendar import NY_TZ
from app.data.point_in_time import Bar


def sma(values: list[float], period: int) -> Optional[float]:
    if len(values) < period:
        return None
    return sum(values[-period:]) / period


def ema_series(values: list[float], period: int) -> list[Optional[float]]:
    """EMA at every index, seeded with the SMA of the first `period`
    values (classic seeding convention). `None` for indices before enough
    data exists to seed it."""
    if period <= 0:
        raise ValueError("period must be positive")
    result: list[Optional[float]] = [None] * len(values)
    if len(values) < period:
        return result
    k = 2 / (period + 1)
    seed = sum(values[:period]) / period
    result[period - 1] = seed
    prev = seed
    for i in range(period, len(values)):
        prev = values[i] * k + prev * (1 - k)
        result[i] = prev
    return result


def atr(bars: list[Bar], period: int) -> Optional[float]:
    """Simple (non-Wilder) moving average of True Range over the last
    `period` bars. Deliberately the simpler variant, not Wilder's
    exponential smoothing — documented so nobody assumes the more common
    Wilder's ATR is what this returns."""
    if len(bars) < period + 1:
        return None
    true_ranges = []
    for i in range(1, len(bars)):
        high, low, prev_close = bars[i].high, bars[i].low, bars[i - 1].close
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        true_ranges.append(tr)
    if len(true_ranges) < period:
        return None
    return sum(true_ranges[-period:]) / period


def current_session_bars(bars: list[Bar]) -> list[Bar]:
    """Bars in `bars` belonging to the same exchange-local (America/New_York)
    calendar date as the last bar — i.e. "today's bars so far"."""
    if not bars:
        return []
    session_date = bars[-1].timestamp.astimezone(NY_TZ).date()
    return [b for b in bars if b.timestamp.astimezone(NY_TZ).date() == session_date]


def session_vwap(bars: list[Bar]) -> Optional[float]:
    """Volume-weighted average price over the current session's bars so
    far (resets every session, per standard practice)."""
    session_bars = current_session_bars(bars)
    total_volume = sum(b.volume for b in session_bars)
    if total_volume == 0:
        return None
    weighted = sum(((b.high + b.low + b.close) / 3) * b.volume for b in session_bars)
    return weighted / total_volume


def opening_range(bars: list[Bar], num_bars: int) -> Optional[tuple[float, float]]:
    """(low, high) of the first `num_bars` bars of the current session.
    `None` if the current session does not yet have `num_bars` bars in the
    given history."""
    session_bars = current_session_bars(bars)
    if len(session_bars) < num_bars:
        return None
    opening = session_bars[:num_bars]
    return min(b.low for b in opening), max(b.high for b in opening)


def relative_volume(bars: list[Bar], lookback: int) -> Optional[float]:
    """The last bar's volume divided by the average volume of the
    `lookback` bars immediately before it (excluding the last bar itself -
    otherwise every bar would trivially be "relative volume ~1x its own
    contribution to its own average"). `None` if there isn't enough prior
    history, or if the prior average volume is zero."""
    if len(bars) < lookback + 1:
        return None
    current = bars[-1]
    prior = bars[-(lookback + 1) : -1]
    avg_volume = sum(b.volume for b in prior) / lookback
    if avg_volume == 0:
        return None
    return current.volume / avg_volume


def distance_in_atr(bars: list[Bar], ema_period: int, atr_period: int) -> Optional[float]:
    """(last close - EMA) expressed in units of ATR: a simple normalized
    measure of how far price has stretched from its short-term mean,
    scaled by recent volatility. Positive means price is above the EMA,
    negative below. Used by mean-reversion strategies (Phase 7) - trend
    strategies compare price to the EMA directly, but "how many ATRs
    away" is what tells a reversion strategy whether a move is unusually
    stretched rather than just normal noise. `None` if either underlying
    indicator isn't computable yet, or ATR is zero."""
    closes = [b.close for b in bars]
    ema = ema_series(closes, ema_period)
    atr_value = atr(bars, atr_period)
    if not ema or ema[-1] is None or atr_value is None or atr_value == 0:
        return None
    return (bars[-1].close - ema[-1]) / atr_value
