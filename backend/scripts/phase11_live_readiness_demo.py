"""Runs a synthetic forward test with the Phase 11 pre-trade filter wired
in, then evaluates it against `evaluate_live_readiness()` - the full
chain a strategy would need to pass before a human even considers
authorizing real capital.

    cd backend && PYTHONPATH=. python3 scripts/phase11_live_readiness_demo.py

Like scripts/phase10_forward_test_demo.py, this proves the *tracking and
readiness-check code* is correct on synthetic (NOT real market) data
compressed into a fast loop - it is not, and cannot be, evidence that any
strategy is actually ready to trade real money. See PHASE11_NOTES.md.
"""

from __future__ import annotations

from datetime import date

from app.forward_test.session import ForwardTestCriteria, ForwardTestSession
from app.live_readiness.readiness import LiveTestConstraints, evaluate_live_readiness
from app.signals.news_filter import FakeEarningsCalendarProvider
from app.strategies.relative_volume_momentum import RelativeVolumeMomentumStrategy

from scripts.phase7_synthetic_gate_run import SYMBOL, generate_synthetic_bars

STRATEGY_NAME = "relative_volume_momentum"
FEE_PER_SHARE = 0.01
RISK_PCT = 0.0025  # DECISIONS.md #5
STARTING_EQUITY = 750.0  # DECISIONS.md #6 default (no user preference stated - see PHASE11_NOTES.md)


def _strategy_factory():
    return RelativeVolumeMomentumStrategy(ema_period=20, volume_lookback=20, volume_multiple=2.0)


def _daily_batches(bars):
    batches: dict[date, list] = {}
    for b in bars:
        batches.setdefault(b.timestamp.date(), []).append(b)
    return [batches[d] for d in sorted(batches)]


def main() -> None:
    # No known earnings dates in this fake calendar - a real one would need
    # a verified earnings-calendar data source (see app/signals/news_filter.py).
    earnings_provider = FakeEarningsCalendarProvider({})

    session = ForwardTestSession(
        symbols=[SYMBOL],
        strategy_factory=_strategy_factory,
        strategy_name=STRATEGY_NAME,
        starting_equity=STARTING_EQUITY,
        risk_pct=RISK_PCT,
        fee_per_share=FEE_PER_SHARE,
        max_daily_loss=STARTING_EQUITY * 0.03,
        criteria=ForwardTestCriteria(),
        earnings_provider=earnings_provider,
    )

    forward_bars = generate_synthetic_bars(date(2024, 7, 1), num_trading_days=95, seed=99991)
    for batch in _daily_batches(forward_bars):
        session.ingest(batch)

    status = session.status()
    print(f"Forward test status: trades={status.metrics.trade_count}, elapsed_days={status.elapsed_days:.1f}")
    print(f"  trades_criterion_met={status.trades_criterion_met}, days_criterion_met={status.days_criterion_met}")
    print(f"  ready_for_review={status.ready_for_review}\n")

    report = evaluate_live_readiness(
        forward_test_status=status,
        daily_loss_guard=session.daily_loss_guard,
        news_filter_wired=True,
        constraints=LiveTestConstraints(),
        broker_connectivity_verified=False,  # honestly never verified in this sandbox - see PHASE3_NOTES.md
    )
    print("Live readiness report:")
    for check in report.checks:
        print(f"  [{check.status:13s}] {check.name}: {check.detail}")
    print(f"\npassed={report.passed} fully_automated={report.fully_automated}")
    print(
        "\nNOTE: passed=True here means only that the automatable checks are satisfied on "
        "SYNTHETIC data. It is explicitly NOT authorization to trade real money - "
        "broker_connectivity_verified and human_sign_off are NOT_AUTOMATED by design and "
        "must be resolved by a human outside this codebase. See PHASE11_NOTES.md."
    )


if __name__ == "__main__":
    main()
