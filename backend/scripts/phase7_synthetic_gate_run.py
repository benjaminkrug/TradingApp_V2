"""Runs the two Phase 7 strategies through the full validation pipeline
on synthetic (NOT real market) data, and prints the resulting gate
reports. This is what PHASE7_NOTES.md's numbers come from - run it
yourself to reproduce them exactly (fixed seed):

    cd backend && python3 scripts/phase7_synthetic_gate_run.py

ROADMAP.md Abschnitt 8: a strategy is never accepted on a single
backtest. This script does not decide whether either strategy is "good" -
it only demonstrates that both can be pushed through leakage detection,
an OOS split, walk-forward windows, and the 12-point gate, and reports
whatever comes out, honestly, including a FAIL.

The synthetic data is a seeded random walk with occasional volume
spikes - not fit to make either strategy look good. See the module
docstring in each strategy for why that would defeat the entire point of
this exercise.
"""

from __future__ import annotations

import random
from datetime import date, timedelta

from app.data.calendar import is_trading_day, session_bounds
from app.data.point_in_time import Bar
from app.strategies.mean_reversion import MeanReversionStrategy
from app.strategies.relative_volume_momentum import RelativeVolumeMomentumStrategy
from app.validation.gate import evaluate_candidate
from app.validation.leakage import detect_leakage
from app.validation.oos import OosSplit
from app.validation.walk_forward import walk_forward_windows

SEED = 20260812
BAR_MINUTES = 5
SYMBOL = "SYNTH"


def generate_synthetic_bars(start: date, num_trading_days: int, seed: int = SEED) -> list[Bar]:
    rng = random.Random(seed)
    bars: list[Bar] = []
    price = 100.0
    d = start

    days_done = 0
    while days_done < num_trading_days:
        if not is_trading_day(d):
            d += timedelta(days=1)
            continue

        open_utc, close_utc = session_bounds(d)
        t = open_utc
        # each trading day gets its own mild drift, so the series alternates
        # between trending and choppy/mean-reverting stretches
        day_drift = rng.uniform(-0.03, 0.03)

        while t < close_utc:
            drift = day_drift + rng.gauss(0, 0.15)
            price = max(1.0, price + drift)
            open_ = price
            close = max(1.0, price + rng.gauss(0, 0.1))
            high = max(open_, close) + abs(rng.gauss(0, 0.05))
            low = min(open_, close) - abs(rng.gauss(0, 0.05))
            volume = max(100, int(rng.gauss(1000, 150)))
            if rng.random() < 0.03:  # occasional volume spike, ~3% of bars
                volume = int(volume * rng.uniform(2.5, 5.0))

            bars.append(Bar(symbol=SYMBOL, timestamp=t, open=open_, high=high, low=low, close=close, volume=volume))
            price = close
            t += timedelta(minutes=BAR_MINUTES)

        days_done += 1
        d += timedelta(days=1)

    return bars


def _print_gate(name: str, report) -> None:
    print(f"\n=== {name} ===")
    for r in report.results:
        print(f"  [{r.status:13s}] {r.name}: {r.detail}")
    print(f"  passed={report.passed} fully_automated={report.fully_automated}")


def run_for_strategy(name: str, strategy_factory) -> None:
    all_bars = generate_synthetic_bars(date(2024, 1, 2), num_trading_days=120)
    split_index = int(len(all_bars) * 0.7)
    cutoff = all_bars[split_index].timestamp.date()

    # Standalone check on the full series (its own, independently valid
    # midpoint - not reused below, see the note on evaluate_candidate's
    # leakage_cut_index).
    leakage_report = detect_leakage(all_bars, strategy_factory, cut_index=len(all_bars) // 2, fee_per_share=0.01)
    print(f"\n{name}: leakage clean={leakage_report.clean} ({len(leakage_report.mismatches)} mismatches)")

    oos_split = OosSplit(all_bars, cutoff=cutoff)
    in_sample_bars = oos_split.in_sample
    oos_split.unlock()  # only after in-sample development is "done" for this demo run
    oos_bars = oos_split.out_of_sample

    wf_windows = walk_forward_windows(in_sample_bars, train_days=40, test_days=10, step_days=10)

    # Found during the Phase 7 critical re-review: evaluate_candidate's
    # leakage_cut_index must be relative to `bars` (in_sample_bars here),
    # not to all_bars - reusing len(all_bars) // 2 happened to still be
    # in-bounds (in_sample_bars is longer than half of all_bars) but
    # landed at ~71% through in_sample_bars by accident, not by choice.
    report = evaluate_candidate(
        bars=in_sample_bars,
        strategy_factory=strategy_factory,
        fee_per_share=0.01,
        leakage_cut_index=len(in_sample_bars) // 2,
        min_trades=10,
        oos_bars=oos_bars,
        walk_forward_test_windows=wf_windows,
        monte_carlo_drawdown_threshold=-500.0,
        monte_carlo_samples=2000,
        monte_carlo_seed=SEED,
    )
    _print_gate(name, report)


if __name__ == "__main__":
    run_for_strategy("MeanReversionStrategy", lambda: MeanReversionStrategy(ema_period=20, atr_period=14, oversold_atr_multiple=2.0))
    run_for_strategy(
        "RelativeVolumeMomentumStrategy",
        lambda: RelativeVolumeMomentumStrategy(ema_period=20, volume_lookback=20, volume_multiple=2.0),
    )
