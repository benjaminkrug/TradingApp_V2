"""The pass criteria from VALIDATION_PROTOCOL.md (K3-K7).

Kept separate from `evaluate.py` (which produces trades) so the statistics
can be tested against cases whose answer is known analytically, without
running a backtest. See tests/test_criteria.py - every routine here has at
least one test where the correct output can be derived by hand rather than
just observed.
"""

from __future__ import annotations

import math
import random
import statistics
from dataclasses import dataclass
from datetime import date
from typing import Callable, Optional, Sequence

from app.data.calendar import NY_TZ
from app.data.point_in_time import Bar
from app.validation.evaluate import trade_return_bp
from app.validation.metrics import Trade

REFERENCE_FRICTION_BP = 2.0  # VALIDATION_PROTOCOL.md K3
MIN_TRADES_TOTAL = 200  # K5
MIN_TRADES_PER_FOLD = 30  # K5
MIN_T_STAT = 2.0  # K4
MAX_P_VALUE = 0.05  # K7
MIN_OOS_PERIODS = 3  # K6


def _session_date(when) -> date:
    return when.astimezone(NY_TZ).date()


# --------------------------------------------------------------------------
# K3 - net of friction
# --------------------------------------------------------------------------


def net_mean_bp(trades: Sequence[Trade], friction_bp: float) -> float:
    """Mean per-trade return in basis points after a round-trip friction
    charge. Friction is subtracted per trade, so it shifts the mean by
    exactly `friction_bp` and leaves the spread untouched."""
    if not trades:
        return 0.0
    return statistics.fmean(trade_return_bp(t) for t in trades) - friction_bp


def breakeven_friction_bp(trades: Sequence[Trade]) -> float:
    """The round-trip cost at which this edge disappears. Equal to the gross
    mean, since friction enters linearly - reported on every run because a
    single assumed cost number would be an arbitrary judgment call
    (DECISIONS.md #9)."""
    return net_mean_bp(trades, 0.0)


# --------------------------------------------------------------------------
# K4 - significance with clustering taken seriously
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class BootstrapResult:
    mean_bp: float
    standard_error: float
    t_stat: float
    p_value: float
    samples: int
    day_count: int


def cluster_bootstrap(
    trades: Sequence[Trade],
    friction_bp: float = 0.0,
    samples: int = 10_000,
    seed: Optional[int] = 12345,
) -> BootstrapResult:
    """Day-block bootstrap: resamples whole trading days with replacement,
    not individual trades.

    Trades are not independent draws. Several fire on the same day, often
    on the same move, and across symbols they correlate through the market
    itself. A naive t-test treats each one as a fresh observation and so
    understates the standard error - the more trades cluster, the more it
    overstates significance. Resampling at the day level keeps whatever
    correlation exists inside a day intact.

    The limiting case makes the size of the effect concrete: with k
    identical trades on each of D days, the naive standard error is
    sd/sqrt(k*D) while the true one is sd/sqrt(D) - the naive t-statistic
    is inflated by a factor of sqrt(k). That relationship is asserted
    directly in the tests.
    """
    if not trades:
        return BootstrapResult(0.0, 0.0, 0.0, 1.0, 0, 0)

    by_day: dict[date, list[float]] = {}
    for trade in trades:
        by_day.setdefault(_session_date(trade.entry_time), []).append(trade_return_bp(trade) - friction_bp)

    days = list(by_day.values())
    observed = statistics.fmean([r for returns in days for r in returns])

    rng = random.Random(seed)
    means: list[float] = []
    for _ in range(samples):
        pooled: list[float] = []
        for _ in range(len(days)):
            pooled.extend(days[rng.randrange(len(days))])
        if pooled:
            means.append(statistics.fmean(pooled))

    if len(means) < 2:
        return BootstrapResult(observed, 0.0, 0.0, 1.0, len(means), len(days))

    se = statistics.stdev(means)
    t_stat = observed / se if se > 0 else 0.0
    # Share of resamples at or below zero, doubled for a two-sided test:
    # how often could this mean have come out non-positive by chance?
    tail = sum(1 for m in means if m <= 0) / len(means)
    p_value = min(1.0, 2 * min(tail, 1 - tail))

    return BootstrapResult(observed, se, t_stat, p_value, len(means), len(days))


# --------------------------------------------------------------------------
# K5 - sample size
# --------------------------------------------------------------------------


def trades_per_fold(trades: Sequence[Trade], folds: Sequence[tuple[date, date]]) -> list[int]:
    counts = []
    for start, end in folds:
        counts.append(sum(1 for t in trades if start <= _session_date(t.entry_time) <= end))
    return counts


# --------------------------------------------------------------------------
# K6 - direction consistency across periods
# --------------------------------------------------------------------------


def split_into_periods(trades: Sequence[Trade], period_count: int) -> list[list[Trade]]:
    """Splits trades into `period_count` consecutive, equal-length calendar
    slices of the covered date range (not equal trade counts - an equal-count
    split would hide the fact that activity itself varies over time)."""
    if not trades or period_count < 1:
        return []
    ordered = sorted(trades, key=lambda t: t.entry_time)
    first = _session_date(ordered[0].entry_time)
    last = _session_date(ordered[-1].entry_time)
    span_days = (last - first).days + 1
    if span_days < period_count:
        return []

    buckets: list[list[Trade]] = [[] for _ in range(period_count)]
    for trade in ordered:
        offset = (_session_date(trade.entry_time) - first).days
        index = min(period_count - 1, offset * period_count // span_days)
        buckets[index].append(trade)
    return buckets


# --------------------------------------------------------------------------
# K7 - permutation test on entry timing
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class PermutationResult:
    observed_bp: float
    p_value: float
    permutations: int
    better_or_equal: int


def permutation_test_entry_timing(
    trades: Sequence[Trade],
    bars_by_symbol: dict[str, list[Bar]],
    permutations: int = 10_000,
    seed: Optional[int] = 12345,
) -> PermutationResult:
    """Is the entry timing better than random timing with the same market
    exposure?

    Null model: keep the number of trades, the session each one happened in,
    and how many bars it was held - only move the entry to a random bar
    within that same session. Because the replacement entries sit in the
    same days and hold for the same length of time, they collect the same
    market drift, which is what makes this test immune to a rising market
    masquerading as skill (the beta problem introduced by allowing
    multi-day holds, DECISIONS.md #2).

    To keep the comparison honest, the observed statistic is measured
    exactly as the permuted ones are: entry at the entry bar's open, exit at
    the close of the bar `duration` later. That deliberately ignores the
    stop/target that actually ended the real trade, so what this tests is
    **entry timing alone**, with exits held constant across both sides.
    Friction is not applied: it would shift the observed and every permuted
    mean by the same constant and so cannot change the p-value. Costs are
    K3's job, chance-versus-skill is this one's.
    """
    if not trades or not bars_by_symbol:
        return PermutationResult(0.0, 1.0, 0, 0)

    index_by_ts: dict[str, dict] = {}
    session_indices: dict[str, dict[date, list[int]]] = {}
    for symbol, bars in bars_by_symbol.items():
        index_by_ts[symbol] = {bar.timestamp: i for i, bar in enumerate(bars)}
        sessions: dict[date, list[int]] = {}
        for i, bar in enumerate(bars):
            sessions.setdefault(_session_date(bar.timestamp), []).append(i)
        session_indices[symbol] = sessions

    # (symbol, session, duration in bars) for every trade we can locate
    specs: list[tuple[str, date, int]] = []
    for trade in trades:
        symbol = trade.symbol
        if symbol not in index_by_ts:
            continue
        entry_i = index_by_ts[symbol].get(trade.entry_time)
        exit_i = index_by_ts[symbol].get(trade.exit_time)
        if entry_i is None or exit_i is None or exit_i <= entry_i:
            continue
        specs.append((symbol, _session_date(trade.entry_time), exit_i - entry_i))

    if not specs:
        return PermutationResult(0.0, 1.0, 0, 0)

    def bp_return(symbol: str, entry_i: int, duration: int) -> float:
        bars = bars_by_symbol[symbol]
        exit_i = min(entry_i + duration, len(bars) - 1)
        entry_price = bars[entry_i].open
        if entry_price <= 0:
            return 0.0
        return (bars[exit_i].close - entry_price) / entry_price * 10_000

    observed_values = []
    for trade in trades:
        symbol = trade.symbol
        if symbol not in index_by_ts:
            continue
        entry_i = index_by_ts[symbol].get(trade.entry_time)
        exit_i = index_by_ts[symbol].get(trade.exit_time)
        if entry_i is None or exit_i is None or exit_i <= entry_i:
            continue
        observed_values.append(bp_return(symbol, entry_i, exit_i - entry_i))
    observed = statistics.fmean(observed_values)

    rng = random.Random(seed)
    better_or_equal = 0
    for _ in range(permutations):
        total = 0.0
        for symbol, session, duration in specs:
            candidates = session_indices[symbol].get(session)
            if not candidates:
                continue
            total += bp_return(symbol, candidates[rng.randrange(len(candidates))], duration)
        if total / len(specs) >= observed:
            better_or_equal += 1

    # +1 in numerator and denominator: the observed arrangement is itself one
    # of the possible ones, and this keeps the p-value from ever being 0.
    p_value = (better_or_equal + 1) / (permutations + 1)
    return PermutationResult(observed, p_value, permutations, better_or_equal)


# --------------------------------------------------------------------------
# Composing the verdict
# --------------------------------------------------------------------------

Status = str  # "PASS" | "FAIL" | "NOT_APPLICABLE"


@dataclass(frozen=True)
class CriterionResult:
    key: str
    status: Status
    detail: str


@dataclass(frozen=True)
class GateVerdict:
    results: list[CriterionResult]

    @property
    def passed(self) -> bool:
        """Strict (DECISIONS.md #8): anything not an outright PASS blocks.
        NOT_APPLICABLE also blocks - a criterion we could not evaluate is
        not a criterion that was met."""
        return bool(self.results) and all(r.status == "PASS" for r in self.results)

    @property
    def failures(self) -> list[CriterionResult]:
        return [r for r in self.results if r.status != "PASS"]


def evaluate_criteria(
    trades: Sequence[Trade],
    bars_by_symbol: dict[str, list[Bar]],
    leakage_clean: bool,
    friction_bp: float = REFERENCE_FRICTION_BP,
    bootstrap_samples: int = 10_000,
    permutations: int = 10_000,
    period_count: int = MIN_OOS_PERIODS,
    seed: Optional[int] = 12345,
    regimes_documented: bool = False,
) -> GateVerdict:
    """Applies K1 and K3-K7. K2/K2a are properties of *how* `trades` were
    produced (real execution rules, declared stop-horizon grid) and are
    enforced by the caller, not checkable from the trade list alone."""
    results: list[CriterionResult] = [
        CriterionResult(
            "K1", "PASS" if leakage_clean else "FAIL", "no leakage detected" if leakage_clean else "leakage detected"
        )
    ]

    net = net_mean_bp(trades, friction_bp)
    breakeven = breakeven_friction_bp(trades)
    results.append(
        CriterionResult(
            "K3",
            "PASS" if net > 0 else "FAIL",
            f"net {net:+.2f} bp/trade at {friction_bp:.1f} bp friction; break-even at {breakeven:+.2f} bp"
            + ("; FRAGILE (break-even under 4 bp)" if 0 < breakeven < 4 else ""),
        )
    )

    boot = cluster_bootstrap(trades, friction_bp=friction_bp, samples=bootstrap_samples, seed=seed)
    results.append(
        CriterionResult(
            "K4",
            "PASS" if boot.t_stat >= MIN_T_STAT else "FAIL",
            f"day-block bootstrap t={boot.t_stat:+.2f} (need >={MIN_T_STAT}), "
            f"p={boot.p_value:.3f}, over {boot.day_count} trading days",
        )
    )

    periods = split_into_periods(trades, period_count)
    per_period_counts = [len(p) for p in periods]
    enough_total = len(trades) >= MIN_TRADES_TOTAL
    enough_per_fold = bool(periods) and all(c >= MIN_TRADES_PER_FOLD for c in per_period_counts)
    results.append(
        CriterionResult(
            "K5",
            "PASS" if enough_total and enough_per_fold else "FAIL",
            f"{len(trades)} trades total (need >={MIN_TRADES_TOTAL}), "
            f"per period {per_period_counts} (need >={MIN_TRADES_PER_FOLD} each)",
        )
    )

    if not periods:
        results.append(CriterionResult("K6", "NOT_APPLICABLE", "not enough calendar span to split into periods"))
    elif not regimes_documented:
        period_means = [net_mean_bp(p, friction_bp) for p in periods]
        all_positive = all(m > 0 for m in period_means)
        results.append(
            CriterionResult(
                "K6",
                "NOT_APPLICABLE",
                f"net by period {[round(m, 2) for m in period_means]} "
                f"({'all positive' if all_positive else 'not all positive'}), but the periods have not been "
                "shown to cover different market regimes - K6 requires that, and it cannot be "
                "established from the trade list",
            )
        )
    else:
        period_means = [net_mean_bp(p, friction_bp) for p in periods]
        all_positive = all(m > 0 for m in period_means)
        results.append(
            CriterionResult(
                "K6",
                "PASS" if all_positive else "FAIL",
                f"net by period {[round(m, 2) for m in period_means]}",
            )
        )

    perm = permutation_test_entry_timing(trades, bars_by_symbol, permutations=permutations, seed=seed)
    results.append(
        CriterionResult(
            "K7",
            "PASS" if perm.p_value < MAX_P_VALUE else "FAIL",
            f"permutation p={perm.p_value:.4f} (need <{MAX_P_VALUE}); random entry timing matched or beat "
            f"the real one in {perm.better_or_equal}/{perm.permutations} draws",
        )
    )

    return GateVerdict(results=results)
