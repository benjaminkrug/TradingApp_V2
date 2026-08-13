"""Registry of implemented strategies for the API layer.

One place that enumerates app/strategies/* instead of duplicating the
list (and drifting out of sync) between the API and the frontend.

`validated`/`gate_note` reflect what scripts/phase7_synthetic_gate_run.py
actually found (PHASE7_NOTES.md), not a guess — both Phase 7 strategies
were run through the full 12-point gate on synthetic data and both
FAILED it. The three Phase 4 strategies have never been run through the
gate at all. None of the five are marked `validated=True`: doing so
without a passing gate result would misrepresent them as recommended,
which ROADMAP.md Abschnitt 15 exists specifically to prevent.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from app.data.point_in_time import SimulationCursor
from app.strategies.ema_pullback import EmaPullbackStrategy
from app.strategies.mean_reversion import MeanReversionStrategy
from app.strategies.opening_range_breakout import OpeningRangeBreakoutStrategy
from app.strategies.relative_volume_momentum import RelativeVolumeMomentumStrategy
from app.strategies.vwap_momentum import VwapMomentumStrategy

StrategyFactory = Callable[[], Callable[[SimulationCursor], str]]


@dataclass(frozen=True)
class StrategyInfo:
    name: str
    description: str
    factory: StrategyFactory
    validated: bool
    gate_note: str


STRATEGY_REGISTRY: dict[str, StrategyInfo] = {
    "vwap_momentum": StrategyInfo(
        name="vwap_momentum",
        description="Buys momentum above session VWAP with a rising fast EMA above a slow EMA.",
        factory=lambda: VwapMomentumStrategy(),
        validated=False,
        gate_note="Not yet run through the full validation gate (only Mean Reversion and "
        "Relative Volume Momentum have been, see PHASE7_NOTES.md).",
    ),
    "ema_pullback": StrategyInfo(
        name="ema_pullback",
        description="Buys a pullback to the fast EMA within an established uptrend.",
        factory=lambda: EmaPullbackStrategy(),
        validated=False,
        gate_note="Not yet run through the full validation gate.",
    ),
    "opening_range_breakout": StrategyInfo(
        name="opening_range_breakout",
        description="Buys a volume-confirmed breakout above the opening range high.",
        factory=lambda: OpeningRangeBreakoutStrategy(),
        validated=False,
        gate_note="Not yet run through the full validation gate.",
    ),
    "mean_reversion": StrategyInfo(
        name="mean_reversion",
        description="Buys an oversold bounce at least N ATRs below the EMA (Phase 7).",
        factory=lambda: MeanReversionStrategy(),
        validated=False,
        gate_note="Ran through the full gate on synthetic data and FAILED (negative OOS "
        "expectancy, unstable walk-forward) - see PHASE7_NOTES.md. Shown for completeness, "
        "not as a recommendation.",
    ),
    "relative_volume_momentum": StrategyInfo(
        name="relative_volume_momentum",
        description="Buys a volume spike with same-direction price and trend confirmation (Phase 7).",
        factory=lambda: RelativeVolumeMomentumStrategy(),
        validated=False,
        gate_note="Ran through the full gate on synthetic data: OOS-positive but FAILED "
        "walk-forward stability - see PHASE7_NOTES.md. Shown for completeness, not as a "
        "recommendation.",
    ),
}
