"""Demonstrates ForwardTestSession (app/forward_test/session.py) fed
day-by-day, the way a real forward test actually has to run - one
`ingest()` call per real-world data pull, not one big batch.

    cd backend && PYTHONPATH=. python3 scripts/phase10_forward_test_demo.py

IMPORTANT — what this script does NOT demonstrate: this compresses many
simulated days into a fast loop over synthetic (NOT real market) data.
That proves the *tracking/readiness-check code* is correct - it is not,
and cannot be, a real forward test. ROADMAP.md Abschnitt 14's "several
weeks to months" requirement is about real calendar time elapsing against
real market data; no amount of code changes that. See PHASE10_NOTES.md.

Reuses `scripts/phase7_synthetic_gate_run.py`'s exact synthetic-data
generator and RelativeVolumeMomentumStrategy - PHASE7_NOTES.md already
documents that strategy's OOS result (expectancy +0.1867 over 21 trades,
but FAILED the overall gate on walk-forward instability). This script
recomputes that same OOS metric from the same reproducible seed (rather
than re-typing the number from the notes, which would risk a transcription
error) and then runs a *separate*, later, differently-seeded synthetic
period through ForwardTestSession, to show `compare_to_oos()` in use.
"""

from __future__ import annotations

from datetime import date

from app.backtest.reference_engine import run_reference_backtest
from app.forward_test.session import ForwardTestCriteria, ForwardTestSession, compare_to_oos
from app.strategies.relative_volume_momentum import RelativeVolumeMomentumStrategy
from app.validation.metrics import compute_metrics, trades_from_fills
from app.validation.oos import OosSplit

from scripts.phase7_synthetic_gate_run import SYMBOL, generate_synthetic_bars

STRATEGY_NAME = "relative_volume_momentum"
FEE_PER_SHARE = 0.01  # matches phase7_synthetic_gate_run.py's own illustrative value
RISK_PCT = 0.0025  # DECISIONS.md #5
STARTING_EQUITY = 50_000.0  # DECISIONS.md #7


def _strategy_factory():
    return RelativeVolumeMomentumStrategy(ema_period=20, volume_lookback=20, volume_multiple=2.0)


def _recompute_oos_metrics():
    """Same data/split as PHASE7_NOTES.md's documented result for this
    strategy - recomputed here rather than hand-copied from the notes."""
    all_bars = generate_synthetic_bars(date(2024, 1, 2), num_trading_days=120)
    split_index = int(len(all_bars) * 0.7)
    cutoff = all_bars[split_index].timestamp.date()
    oos_split = OosSplit(all_bars, cutoff=cutoff)
    oos_split.unlock()
    oos_result = run_reference_backtest(oos_split.out_of_sample, _strategy_factory(), fee_per_share=FEE_PER_SHARE)
    return compute_metrics(trades_from_fills(oos_result.fills)), all_bars[-1].timestamp.date()


def _daily_batches(bars):
    batches: dict[date, list] = {}
    for b in bars:
        batches.setdefault(b.timestamp.date(), []).append(b)
    return [batches[d] for d in sorted(batches)]


def main() -> None:
    oos_metrics, oos_data_end = _recompute_oos_metrics()
    print(f"Recomputed OOS metrics (same as PHASE7_NOTES.md): {oos_metrics}")
    print(f"OOS synthetic data ended {oos_data_end} - forward test below starts well after that.\n")

    # A separate, later, differently-seeded synthetic period: stands in for
    # "new data that arrives after strategy development is done" - the
    # whole point of a forward test, per ROADMAP.md Abschnitt 14.
    forward_bars = generate_synthetic_bars(date(2024, 7, 1), num_trading_days=95, seed=99991)

    session = ForwardTestSession(
        symbols=[SYMBOL],
        strategy_factory=_strategy_factory,
        strategy_name=STRATEGY_NAME,
        starting_equity=STARTING_EQUITY,
        risk_pct=RISK_PCT,
        fee_per_share=FEE_PER_SHARE,
        max_daily_loss=STARTING_EQUITY * 0.03,
        criteria=ForwardTestCriteria(),  # ROADMAP defaults: 20 trades or ~90 days
    )

    for day_index, batch in enumerate(_daily_batches(forward_bars), start=1):
        session.ingest(batch)
        if day_index % 10 == 0 or day_index == len(_daily_batches(forward_bars)):
            status = session.status()
            print(
                f"day {day_index:3d}: elapsed={status.elapsed_days:6.1f}d "
                f"trades={status.metrics.trade_count:3d} ready_for_review={status.ready_for_review}"
            )

    final = session.status()
    print(f"\nFinal status after {final.elapsed_days:.1f} simulated days:")
    print(f"  trades={final.metrics.trade_count} (>= {session.criteria.min_trades}? {final.trades_criterion_met})")
    print(f"  days={final.elapsed_days:.1f} (>= {session.criteria.min_days}? {final.days_criterion_met})")
    print(f"  ready_for_review={final.ready_for_review}")

    comparison = compare_to_oos(oos_metrics, final.metrics)
    print(f"\nOOS vs forward-test comparison: {comparison}")


if __name__ == "__main__":
    main()
