"""Volume-selection + overnight-hold — OVERNIGHT_SELECTION_PROTOCOL.md.

Two pieces that don't exist elsewhere in the codebase:

1. `select_top_by_relative_volume` — the daily ranking step (K1-style
   look-ahead concern: only uses volume up to and including day N to rank
   for day N, never later data).
2. `selection_vs_random_permutation_test` — the "K-neu" significance test
   from the protocol. Deliberately NOT a reuse of
   `criteria.permutation_test_entry_timing`: that function permutes *when*
   a trade enters, by bar count, which silently breaks for an overnight
   trade (close-to-open is "1 bar" apart in daily data regardless of real
   elapsed time - this was tried on real overnight trades earlier and
   produced a nonsense result, see OVERNIGHT_SELECTION_PROTOCOL.md). This
   test instead permutes *which stocks* get selected each day, holding the
   trade shape fixed - the right question for a selection strategy.
"""

from __future__ import annotations

import random
import statistics
from dataclasses import dataclass
from datetime import date
from typing import Optional, Sequence

from app.data.point_in_time import Bar

# Found scanning the real S&P 500 cache (22.09.2026, see OVERNIGHT_SELECTION_
# PROTOCOL.md's change log): a handful of symbols have phantom daily bars
# where open == close and volume == 0 - a stale placeholder quote for a day
# the feed had no real trade data, not a real price (TPL showed three of
# these in May 2023, each one creating a fake ~70% round-trip). Any bar with
# zero volume is treated as "no real data that day" everywhere in this
# module: excluded from relative-volume baselines (it would otherwise drag
# a rolling average toward zero) and never used as an overnight trade's
# entry or exit.
_MIN_REAL_VOLUME = 1

# A second, independent safety net for moves real filtering above cannot
# catch: single-day price changes far too large to be genuine tradeable
# overnight moves for a liquid stock - in practice, corporate actions
# (spin-offs, primarily) that Alpaca's split-adjustment does not cover,
# since a spin-off is not a split. HON and DD both show >45% single-day
# moves on real, large volume in this dataset, consistent with their 2025/26
# corporate breakups. Excluding them is a conscious, conservative trade-off:
# it also throws out any genuine, very large news-driven overnight move
# (extremely rare for S&P 500 constituents, but not impossible) rather than
# trying to distinguish the two without real corporate-actions data - the
# same K8 gap noted throughout this protocol.
MAX_PLAUSIBLE_OVERNIGHT_BP = 3_000.0  # 30%


def _has_real_volume(bar: Bar) -> bool:
    return bar.volume >= _MIN_REAL_VOLUME


@dataclass(frozen=True)
class DailyBars:
    """One symbol's daily bars, oldest first. A thin wrapper (rather than
    passing raw `list[Bar]` around) so callers can't accidentally mix up
    the by-symbol dict this module expects."""

    symbol: str
    bars: list[Bar]


def relative_volume_by_day(daily: DailyBars, lookback: int) -> dict[date, Optional[float]]:
    """Day N's volume divided by the mean volume of the `lookback` days
    strictly before it. `None` where there isn't enough prior history -
    never computed using day N or later, which is what keeps the daily
    ranking free of look-ahead.

    A zero-volume day (`_has_real_volume`) is treated as "not real data":
    it can never itself be ranked (there was no real trade to rank), and it
    is dropped from the baseline window rather than dragging the average
    toward zero and inflating every other day's ratio.
    """
    bars = daily.bars
    result: dict[date, Optional[float]] = {}
    for i, bar in enumerate(bars):
        if i < lookback or not _has_real_volume(bar):
            result[bar.timestamp.date()] = None
            continue
        prior = [b for b in bars[i - lookback : i] if _has_real_volume(b)]
        if not prior:
            result[bar.timestamp.date()] = None
            continue
        baseline = statistics.fmean(b.volume for b in prior)
        result[bar.timestamp.date()] = (bar.volume / baseline) if baseline > 0 else None
    return result


def select_top_by_relative_volume(
    daily_bars_by_symbol: dict[str, DailyBars],
    lookback: int,
    top_n: int,
    min_price: float,
) -> dict[date, list[str]]:
    """For each day that appears in the input, the top `top_n` symbols by
    relative volume among those eligible that day (price > min_price,
    enough history for the lookback window). Returns only days where at
    least one symbol was eligible.
    """
    rel_vol_by_symbol = {sym: relative_volume_by_day(d, lookback) for sym, d in daily_bars_by_symbol.items()}
    price_by_symbol_day: dict[str, dict[date, float]] = {
        sym: {b.timestamp.date(): b.close for b in d.bars} for sym, d in daily_bars_by_symbol.items()
    }

    all_days: set[date] = set()
    for d in daily_bars_by_symbol.values():
        all_days.update(b.timestamp.date() for b in d.bars)

    selections: dict[date, list[str]] = {}
    for day in sorted(all_days):
        candidates = []
        for sym, rel_vol_map in rel_vol_by_symbol.items():
            rel_vol = rel_vol_map.get(day)
            price = price_by_symbol_day[sym].get(day)
            if rel_vol is None or price is None or price <= min_price:
                continue
            candidates.append((rel_vol, sym))
        if not candidates:
            continue
        candidates.sort(reverse=True)
        selections[day] = [sym for _, sym in candidates[:top_n]]
    return selections


def eligible_symbols_by_day(
    daily_bars_by_symbol: dict[str, DailyBars], lookback: int, min_price: float
) -> dict[date, list[str]]:
    """Every symbol eligible on each day (not just the selected top-N) -
    the pool the permutation test draws random alternatives from."""
    rel_vol_by_symbol = {sym: relative_volume_by_day(d, lookback) for sym, d in daily_bars_by_symbol.items()}
    price_by_symbol_day: dict[str, dict[date, float]] = {
        sym: {b.timestamp.date(): b.close for b in d.bars} for sym, d in daily_bars_by_symbol.items()
    }
    all_days: set[date] = set()
    for d in daily_bars_by_symbol.values():
        all_days.update(b.timestamp.date() for b in d.bars)

    out: dict[date, list[str]] = {}
    for day in sorted(all_days):
        out[day] = [
            sym
            for sym, rel_vol_map in rel_vol_by_symbol.items()
            if rel_vol_map.get(day) is not None
            and price_by_symbol_day[sym].get(day) is not None
            and price_by_symbol_day[sym][day] > min_price
        ]
    return out


def overnight_returns_by_day(
    daily_bars_by_symbol: dict[str, DailyBars], max_plausible_bp: Optional[float] = MAX_PLAUSIBLE_OVERNIGHT_BP
) -> dict[date, dict[str, float]]:
    """Close of day N -> open of day N+1, in basis points, keyed by day N
    (the day the position would be entered).

    A transition is skipped entirely (not clipped) if either bar has zero
    volume (phantom data, see module docstring) or if the move exceeds
    `max_plausible_bp` in magnitude (likely an uncaptured corporate action,
    e.g. a spin-off - see MAX_PLAUSIBLE_OVERNIGHT_BP). Pass `None` to
    disable the magnitude filter, e.g. for a test that wants to see the raw
    number.
    """
    out: dict[date, dict[str, float]] = {}
    for sym, daily in daily_bars_by_symbol.items():
        bars = daily.bars
        for i in range(len(bars) - 1):
            entry_bar, exit_bar = bars[i], bars[i + 1]
            if entry_bar.close <= 0 or not _has_real_volume(entry_bar) or not _has_real_volume(exit_bar):
                continue
            bp = (exit_bar.open - entry_bar.close) / entry_bar.close * 10_000
            if max_plausible_bp is not None and abs(bp) > max_plausible_bp:
                continue
            out.setdefault(entry_bar.timestamp.date(), {})[sym] = bp
    return out


@dataclass(frozen=True)
class SelectionPermutationResult:
    observed_mean_bp: float
    p_value: float
    permutations: int
    better_or_equal: int
    day_count: int
    trade_count: int


def selection_vs_random_permutation_test(
    selected_by_day: dict[date, list[str]],
    eligible_by_day: dict[date, list[str]],
    returns_by_day: dict[date, dict[str, float]],
    permutations: int = 10_000,
    seed: Optional[int] = 12345,
) -> SelectionPermutationResult:
    """Is volume-based selection better than picking the same number of
    stocks at random from the same day's eligible pool?

    Both the real selection and every permuted draw use the exact same
    trade (close of day N -> open of day N+1), the same days, and the same
    number of names per day - so both sides collect the same overnight
    market drift. What differs is only which names get picked, which is
    what isolates a selection effect from general overnight market beta.
    """
    observed_values: list[float] = []
    for day, selected in selected_by_day.items():
        day_returns = returns_by_day.get(day, {})
        observed_values.extend(day_returns[s] for s in selected if s in day_returns)

    if not observed_values:
        return SelectionPermutationResult(0.0, 1.0, 0, 0, 0, 0)

    observed_mean = statistics.fmean(observed_values)

    rng = random.Random(seed)
    better_or_equal = 0
    for _ in range(permutations):
        pooled: list[float] = []
        for day, selected in selected_by_day.items():
            day_returns = returns_by_day.get(day, {})
            pool = [s for s in eligible_by_day.get(day, []) if s in day_returns]
            n = min(len(selected), len(pool))
            if n == 0:
                continue
            random_symbols = rng.sample(pool, n)
            pooled.extend(day_returns[s] for s in random_symbols)
        if pooled and statistics.fmean(pooled) >= observed_mean:
            better_or_equal += 1

    p_value = (better_or_equal + 1) / (permutations + 1)
    return SelectionPermutationResult(
        observed_mean_bp=observed_mean,
        p_value=p_value,
        permutations=permutations,
        better_or_equal=better_or_equal,
        day_count=len(selected_by_day),
        trade_count=len(observed_values),
    )
