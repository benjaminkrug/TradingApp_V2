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
    ranking free of look-ahead."""
    bars = daily.bars
    result: dict[date, Optional[float]] = {}
    for i, bar in enumerate(bars):
        if i < lookback:
            result[bar.timestamp.date()] = None
            continue
        prior = bars[i - lookback : i]
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


def overnight_returns_by_day(daily_bars_by_symbol: dict[str, DailyBars]) -> dict[date, dict[str, float]]:
    """Close of day N -> open of day N+1, in basis points, keyed by day N
    (the day the position would be entered)."""
    out: dict[date, dict[str, float]] = {}
    for sym, daily in daily_bars_by_symbol.items():
        bars = daily.bars
        for i in range(len(bars) - 1):
            entry_bar, exit_bar = bars[i], bars[i + 1]
            if entry_bar.close <= 0:
                continue
            bp = (exit_bar.open - entry_bar.close) / entry_bar.close * 10_000
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
