"""Concrete trade signal assembly — ROADMAP.md Abschnitt 12/16/23.

Combines a strategy's BUY decision with an ATR-based stop/target
(risk.py), position sizing, relative volume, and an *optional* calibrated
score — never a fabricated one. Without a `CalibratedModel`, `score` is
explicitly `None` and `confidence` is `"UNCALIBRATED"` rather than a
made-up number, because there is no real historical, OOS-validated trade
data yet to calibrate against (no live market data — see
PHASE3_NOTES.md). Assigning a plausible-looking score anyway would be
exactly the "hand-picked weights that look objective" mistake
ROADMAP.md Abschnitt 16 exists to correct.

`rationale` is a plain-language, strategy-agnostic explanation (price vs
VWAP, trend direction, relative volume) — ROADMAP.md Abschnitt 23: never
show a confidence number without explaining how it came to be.

A note on `entry`, because it is easy to mistake for reference_engine's
fill price and they are deliberately not the same thing: `entry` here is
the current bar's close, used as a real-time reference price for a human
about to place an order on a live/prospective signal - by definition
there is no "next bar" yet to fill at, unlike in a backtest. This is NOT
a regression back to the same-bar-close fill assumption that
reference_engine.py fixed (ROADMAP.md Abschnitt 2/13): that fix was about
a *backtest* silently pretending it could fill at a price only known
after the fact. A live signal showing "last price" as a reference is
standard practice precisely because nothing later is knowable yet.
The two must not be conflated, though: backtesting a strategy that
consumes `Signal` objects has to still go through reference_engine's own
next-bar-open convention to stay comparable to every other backtest in
this codebase - `build_signal()` is for live signal presentation, not a
second, competing execution model.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.data.point_in_time import SimulationCursor
from app.features.indicators import atr_on_horizon
from app.features.indicators import ema_series
from app.features.indicators import relative_volume as relative_volume_indicator
from app.features.indicators import session_vwap
from app.signals.risk import atr_stop_loss, position_size, risk_reward_target
from app.signals.scoring import CalibratedModel


@dataclass(frozen=True)
class Signal:
    symbol: str
    strategy_name: str
    entry: float
    stop: float
    target: float
    risk_reward: float
    shares: float
    score: Optional[float]  # 0-100, or None if no calibrated model was supplied
    confidence: str  # "HIGH" / "MEDIUM" / "LOW" / "UNCALIBRATED"
    relative_volume: Optional[float]
    rationale: list[str]


def _confidence_label(score: Optional[float]) -> str:
    if score is None:
        return "UNCALIBRATED"
    if score >= 80:
        return "HIGH"
    if score >= 60:
        return "MEDIUM"
    return "LOW"


def build_signal(
    cursor: SimulationCursor,
    strategy_action: str,
    strategy_name: str,
    account_equity: float,
    risk_pct: float,
    atr_period: int = 14,
    atr_multiple: float = 1.5,
    risk_reward: float = 2.0,
    relative_volume_lookback: int = 20,
    calibrated_model: Optional[CalibratedModel] = None,
    atr_horizon: str = "bar",
    max_position_pct: Optional[float] = None,
) -> Optional[Signal]:
    """`None` if `strategy_action` isn't "BUY", or if there isn't yet
    enough history to compute ATR.

    `atr_horizon` selects the volatility horizon the stop is sized from
    ('bar' = the strategy's own bars, or 'hour'/'day'), and
    `max_position_pct` caps how much equity one position may tie up. Both
    default to the previous behavior; see VALIDATION_PROTOCOL.md K2a for
    why the horizon is a declared test grid rather than a tuned value.
    """
    if strategy_action != "BUY":
        return None

    history = cursor.history
    entry = history[-1].close

    atr_value = atr_on_horizon(history, atr_period, atr_horizon)
    if atr_value is None:
        return None

    stop = atr_stop_loss(entry, atr_value, atr_multiple)
    target = risk_reward_target(entry, stop, risk_reward)
    shares = position_size(account_equity, risk_pct, entry, stop, max_position_pct=max_position_pct)
    rel_vol = relative_volume_indicator(history, relative_volume_lookback)

    closes = [b.close for b in history]
    fast = ema_series(closes, 9)
    slow = ema_series(closes, 20)
    vwap = session_vwap(history)
    uptrend = bool(fast and slow and fast[-1] is not None and slow[-1] is not None and fast[-1] > slow[-1])

    rationale = [f"Strategy: {strategy_name}"]
    if vwap is not None:
        rationale.append(f"{'Price above VWAP' if entry > vwap else 'Price below VWAP'} ({entry:.2f} vs {vwap:.2f})")
    if fast and slow and fast[-1] is not None and slow[-1] is not None:
        rationale.append(f"{'Uptrend' if uptrend else 'Downtrend/flat'} (EMA9={fast[-1]:.2f}, EMA20={slow[-1]:.2f})")
    if rel_vol is not None:
        rationale.append(f"Relative volume {rel_vol:.2f}x the {relative_volume_lookback}-bar average")

    score = None
    if calibrated_model is not None:
        features = [
            1.0 if (vwap is not None and entry > vwap) else 0.0,
            1.0 if uptrend else 0.0,
            rel_vol if rel_vol is not None else 0.0,
        ]
        score = calibrated_model.predict_probability(features) * 100

    return Signal(
        symbol=history[-1].symbol,
        strategy_name=strategy_name,
        entry=entry,
        stop=stop,
        target=target,
        risk_reward=risk_reward,
        shares=shares,
        score=score,
        confidence=_confidence_label(score),
        relative_volume=rel_vol,
        rationale=rationale,
    )
