"""Monte Carlo robustness — ROADMAP.md Abschnitt 10/17.

Bootstrap-resamples a strategy's realized trade PnLs (with replacement) to
estimate the distribution of possible drawdowns the *same* edge could have
produced under a different trade ordering/luck, rather than trusting the
single historical sequence that happened to occur. Uses stdlib `random`
only (no numpy — unavailable in this sandbox, see PHASE2_NOTES.md; not
needed for this anyway).
"""

from __future__ import annotations

import random
from typing import Optional


def max_drawdown(pnls: list[float]) -> float:
    """Largest peak-to-trough drop in the cumulative equity curve built
    from `pnls` in the given order, starting at 0. Returned as a
    non-positive number (0.0 if the curve never dips below a prior peak)."""
    equity = 0.0
    peak = 0.0
    worst = 0.0
    for pnl in pnls:
        equity += pnl
        peak = max(peak, equity)
        worst = min(worst, equity - peak)
    return worst


def bootstrap_max_drawdowns(
    trade_pnls: list[float],
    num_samples: int,
    sample_size: Optional[int] = None,
    seed: Optional[int] = None,
) -> list[float]:
    """Resamples `trade_pnls` with replacement `num_samples` times (each
    resample of length `sample_size`, defaulting to len(trade_pnls)) and
    returns the max drawdown of each resampled sequence. `seed` makes the
    result reproducible — pass one in tests, leave it unset for a real
    robustness check where you want the full random range."""
    if not trade_pnls:
        return []
    sample_size = sample_size or len(trade_pnls)
    rng = random.Random(seed)
    return [max_drawdown([rng.choice(trade_pnls) for _ in range(sample_size)]) for _ in range(num_samples)]


def percentile(values: list[float], p: float) -> float:
    """Linear-interpolation percentile (0 <= p <= 100), stdlib-only
    (no numpy). `values` need not be pre-sorted."""
    if not values:
        raise ValueError("cannot compute a percentile of an empty list")
    if not 0 <= p <= 100:
        raise ValueError("p must be between 0 and 100")
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (p / 100) * (len(ordered) - 1)
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = rank - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction
