import unittest
from datetime import datetime, timezone

from app.forward_test.session import ForwardTestStatus
from app.live_readiness.readiness import LiveTestConstraints, evaluate_live_readiness
from app.signals.risk import DailyLossGuard
from app.validation.metrics import Metrics

READY_STATUS = ForwardTestStatus(
    started_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    last_bar_at=datetime(2026, 4, 15, tzinfo=timezone.utc),
    elapsed_days=104.0,
    metrics=Metrics(
        trade_count=25,
        win_rate=0.4,
        profit_factor=1.5,
        total_pnl=100.0,
        average_trade=4.0,
        expectancy=4.0,
        max_consecutive_losses=3,
    ),
    trades_criterion_met=True,
    days_criterion_met=True,
)

NOT_READY_STATUS = ForwardTestStatus(
    started_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    last_bar_at=datetime(2026, 1, 10, tzinfo=timezone.utc),
    elapsed_days=9.0,
    metrics=Metrics(
        trade_count=2,
        win_rate=0.5,
        profit_factor=None,
        total_pnl=1.0,
        average_trade=0.5,
        expectancy=0.5,
        max_consecutive_losses=1,
    ),
    trades_criterion_met=False,
    days_criterion_met=False,
)


class TestEvaluateLiveReadiness(unittest.TestCase):
    def test_all_criteria_met_passes_everything_automatable(self):
        report = evaluate_live_readiness(
            forward_test_status=READY_STATUS,
            daily_loss_guard=DailyLossGuard(max_daily_loss=100.0),
            news_filter_wired=True,
            constraints=LiveTestConstraints(account_type="cash", max_capital=750.0),
        )
        by_name = {c.name: c for c in report.checks}
        self.assertEqual(by_name["forward_test_confirmed"].status, "PASS")
        self.assertEqual(by_name["pdt_safe_account"].status, "PASS")
        self.assertEqual(by_name["daily_loss_kill_switch_configured"].status, "PASS")
        self.assertEqual(by_name["news_earnings_filter_wired"].status, "PASS")
        # broker connectivity and human sign-off can never auto-pass
        self.assertEqual(by_name["broker_connectivity_verified"].status, "NOT_AUTOMATED")
        self.assertEqual(by_name["human_sign_off"].status, "NOT_AUTOMATED")
        self.assertTrue(report.passed)  # no FAILs
        self.assertFalse(report.fully_automated)  # two NOT_AUTOMATED checks remain

    def test_missing_forward_test_fails(self):
        report = evaluate_live_readiness(
            forward_test_status=None,
            daily_loss_guard=DailyLossGuard(max_daily_loss=100.0),
            news_filter_wired=True,
            constraints=LiveTestConstraints(),
        )
        by_name = {c.name: c for c in report.checks}
        self.assertEqual(by_name["forward_test_confirmed"].status, "FAIL")
        self.assertFalse(report.passed)

    def test_forward_test_not_yet_ready_fails(self):
        report = evaluate_live_readiness(
            forward_test_status=NOT_READY_STATUS,
            daily_loss_guard=DailyLossGuard(max_daily_loss=100.0),
            news_filter_wired=True,
            constraints=LiveTestConstraints(),
        )
        by_name = {c.name: c for c in report.checks}
        self.assertEqual(by_name["forward_test_confirmed"].status, "FAIL")
        self.assertFalse(report.passed)

    def test_margin_account_under_pdt_threshold_fails(self):
        report = evaluate_live_readiness(
            forward_test_status=READY_STATUS,
            daily_loss_guard=DailyLossGuard(max_daily_loss=100.0),
            news_filter_wired=True,
            constraints=LiveTestConstraints(account_type="margin", max_capital=750.0),
        )
        by_name = {c.name: c for c in report.checks}
        self.assertEqual(by_name["pdt_safe_account"].status, "FAIL")
        self.assertFalse(report.passed)

    def test_margin_account_at_or_above_pdt_threshold_passes(self):
        report = evaluate_live_readiness(
            forward_test_status=READY_STATUS,
            daily_loss_guard=DailyLossGuard(max_daily_loss=100.0),
            news_filter_wired=True,
            constraints=LiveTestConstraints(account_type="margin", max_capital=25_000.0),
        )
        by_name = {c.name: c for c in report.checks}
        self.assertEqual(by_name["pdt_safe_account"].status, "PASS")

    def test_missing_kill_switch_fails(self):
        report = evaluate_live_readiness(
            forward_test_status=READY_STATUS,
            daily_loss_guard=None,
            news_filter_wired=True,
            constraints=LiveTestConstraints(),
        )
        by_name = {c.name: c for c in report.checks}
        self.assertEqual(by_name["daily_loss_kill_switch_configured"].status, "FAIL")
        self.assertFalse(report.passed)

    def test_missing_news_filter_fails(self):
        report = evaluate_live_readiness(
            forward_test_status=READY_STATUS,
            daily_loss_guard=DailyLossGuard(max_daily_loss=100.0),
            news_filter_wired=False,
            constraints=LiveTestConstraints(),
        )
        by_name = {c.name: c for c in report.checks}
        self.assertEqual(by_name["news_earnings_filter_wired"].status, "FAIL")
        self.assertFalse(report.passed)

    def test_broker_connectivity_verified_flag_is_reflected(self):
        report = evaluate_live_readiness(
            forward_test_status=READY_STATUS,
            daily_loss_guard=DailyLossGuard(max_daily_loss=100.0),
            news_filter_wired=True,
            constraints=LiveTestConstraints(),
            broker_connectivity_verified=True,
        )
        by_name = {c.name: c for c in report.checks}
        self.assertEqual(by_name["broker_connectivity_verified"].status, "PASS")
        # human sign-off is NEVER automatable, regardless of any flag passed in
        self.assertEqual(by_name["human_sign_off"].status, "NOT_AUTOMATED")


if __name__ == "__main__":
    unittest.main()
