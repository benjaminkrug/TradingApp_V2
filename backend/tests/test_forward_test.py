import unittest
from datetime import date, timedelta

from app.data.calendar import session_bounds
from app.data.point_in_time import Bar
from app.forward_test.session import ForwardTestCriteria, ForwardTestSession, compare_to_oos
from app.validation.metrics import Metrics

SYMBOL = "TEST"


def bar(symbol, t, o, h, l, c, v=1000.0):
    return Bar(symbol=symbol, timestamp=t, open=o, high=h, low=l, close=c, volume=v)


class ScriptedStrategy:
    def __init__(self, actions: list[str]):
        self._actions = list(actions)

    def __call__(self, cursor) -> str:
        if not self._actions:
            return "HOLD"
        return self._actions.pop(0)


def make_metrics(trade_count=0, win_rate=0.0, expectancy=0.0) -> Metrics:
    return Metrics(
        trade_count=trade_count,
        win_rate=win_rate,
        profit_factor=None,
        total_pnl=expectancy * trade_count,
        average_trade=expectancy,
        expectancy=expectancy,
        max_consecutive_losses=0,
    )


class TestForwardTestSessionIngest(unittest.TestCase):
    def test_ingest_called_multiple_times_accumulates_state(self):
        session = ForwardTestSession(
            symbols=[SYMBOL],
            strategy_factory=lambda: ScriptedStrategy([]),
            strategy_name="scripted",
            starting_equity=50_000.0,
            risk_pct=0.0025,
            fee_per_share=0.0,
            max_daily_loss=10_000.0,
        )
        base = session_bounds(date(2026, 1, 6))[0]

        status0 = session.status()
        self.assertIsNone(status0.started_at)
        self.assertEqual(status0.elapsed_days, 0.0)

        session.ingest([bar(SYMBOL, base, 100, 100, 100, 100)])
        status1 = session.status()
        self.assertEqual(status1.started_at, base)
        self.assertEqual(status1.last_bar_at, base)
        self.assertEqual(status1.elapsed_days, 0.0)

        later = base + timedelta(days=5)
        session.ingest([bar(SYMBOL, later, 101, 101, 101, 101)])
        status2 = session.status()
        self.assertEqual(status2.started_at, base)  # start does not move on later ingests
        self.assertEqual(status2.last_bar_at, later)
        self.assertAlmostEqual(status2.elapsed_days, 5.0)

    def test_ingest_rejects_bar_for_unconfigured_symbol(self):
        session = ForwardTestSession(
            symbols=[SYMBOL],
            strategy_factory=lambda: ScriptedStrategy([]),
            strategy_name="scripted",
            starting_equity=50_000.0,
            risk_pct=0.0025,
            fee_per_share=0.0,
            max_daily_loss=10_000.0,
        )
        base = session_bounds(date(2026, 1, 6))[0]
        with self.assertRaises(ValueError):
            session.ingest([bar("OTHER", base, 100, 100, 100, 100)])

    def test_multi_symbol_bars_dispatch_to_the_right_engine(self):
        session = ForwardTestSession(
            symbols=["AAA", "BBB"],
            strategy_factory=lambda: ScriptedStrategy([]),
            strategy_name="scripted",
            starting_equity=50_000.0,
            risk_pct=0.0025,
            fee_per_share=0.0,
            max_daily_loss=10_000.0,
        )
        base = session_bounds(date(2026, 1, 6))[0]
        session.ingest([bar("AAA", base, 100, 100, 100, 100), bar("BBB", base, 50, 50, 50, 50)])
        self.assertEqual(session.engines["AAA"].cursor.current.close, 100)
        self.assertEqual(session.engines["BBB"].cursor.current.close, 50)


class TestForwardTestSessionReadiness(unittest.TestCase):
    def _run_one_full_trade(self, session, base):
        # Same hand-verified scenario as Phase 9's engine tests: BUY decided
        # on bar2 (flat closes 100,101,102), fills at bar3's open (103),
        # target (104) hit on bar4.
        flat = [bar(SYMBOL, base + timedelta(minutes=5 * i), c, c, c, c) for i, c in enumerate([100, 101, 102])]
        session.ingest(flat)
        session.ingest([bar(SYMBOL, base + timedelta(minutes=15), 103, 103, 103, 103)])
        session.ingest([bar(SYMBOL, base + timedelta(minutes=20), 103.5, 104.5, 103.0, 104.0)])

    def test_not_ready_before_either_threshold_is_met(self):
        session = ForwardTestSession(
            symbols=[SYMBOL],
            strategy_factory=lambda: ScriptedStrategy(["HOLD", "HOLD", "BUY", "HOLD", "HOLD"]),
            strategy_name="scripted",
            starting_equity=50_000.0,
            risk_pct=0.0025,
            fee_per_share=0.0,
            max_daily_loss=10_000.0,
            criteria=ForwardTestCriteria(min_trades=20, min_days=90.0),
            atr_period=2,
            atr_multiple=1.0,
            risk_reward=2.0,
        )
        base = session_bounds(date(2026, 1, 6))[0]
        self._run_one_full_trade(session, base)

        status = session.status()
        self.assertEqual(status.metrics.trade_count, 1)
        self.assertFalse(status.trades_criterion_met)
        self.assertFalse(status.days_criterion_met)
        self.assertFalse(status.ready_for_review)

    def test_ready_when_trade_count_threshold_met_even_with_few_days(self):
        session = ForwardTestSession(
            symbols=[SYMBOL],
            strategy_factory=lambda: ScriptedStrategy(["HOLD", "HOLD", "BUY", "HOLD", "HOLD"]),
            strategy_name="scripted",
            starting_equity=50_000.0,
            risk_pct=0.0025,
            fee_per_share=0.0,
            max_daily_loss=10_000.0,
            criteria=ForwardTestCriteria(min_trades=1, min_days=90.0),
            atr_period=2,
            atr_multiple=1.0,
            risk_reward=2.0,
        )
        base = session_bounds(date(2026, 1, 6))[0]
        self._run_one_full_trade(session, base)

        status = session.status()
        self.assertTrue(status.trades_criterion_met)
        self.assertFalse(status.days_criterion_met)
        self.assertTrue(status.ready_for_review)  # "bzw." = either is sufficient

    def test_ready_when_days_threshold_met_even_with_zero_trades(self):
        session = ForwardTestSession(
            symbols=[SYMBOL],
            strategy_factory=lambda: ScriptedStrategy([]),  # never trades
            strategy_name="scripted",
            starting_equity=50_000.0,
            risk_pct=0.0025,
            fee_per_share=0.0,
            max_daily_loss=10_000.0,
            criteria=ForwardTestCriteria(min_trades=20, min_days=5.0),
        )
        base = session_bounds(date(2026, 1, 6))[0]
        session.ingest([bar(SYMBOL, base, 100, 100, 100, 100)])
        session.ingest([bar(SYMBOL, base + timedelta(days=6), 100, 100, 100, 100)])

        status = session.status()
        self.assertEqual(status.metrics.trade_count, 0)
        self.assertFalse(status.trades_criterion_met)
        self.assertTrue(status.days_criterion_met)
        self.assertTrue(status.ready_for_review)


class TestCompareToOos(unittest.TestCase):
    def test_same_sign_expectancy_is_flagged_consistent(self):
        oos = make_metrics(trade_count=30, win_rate=0.5, expectancy=1.5)
        forward = make_metrics(trade_count=20, win_rate=0.45, expectancy=0.8)
        report = compare_to_oos(oos, forward)
        self.assertTrue(report.same_sign_expectancy)
        self.assertIn("same sign", report.note)

    def test_opposite_sign_expectancy_is_flagged_not_confirmed(self):
        oos = make_metrics(trade_count=30, win_rate=0.5, expectancy=1.5)
        forward = make_metrics(trade_count=20, win_rate=0.3, expectancy=-0.8)
        report = compare_to_oos(oos, forward)
        self.assertFalse(report.same_sign_expectancy)
        self.assertIn("OPPOSITE", report.note)

    def test_zero_forward_trades_reports_nothing_to_compare(self):
        oos = make_metrics(trade_count=30, win_rate=0.5, expectancy=1.5)
        forward = make_metrics(trade_count=0)
        report = compare_to_oos(oos, forward)
        self.assertFalse(report.same_sign_expectancy)
        self.assertIn("nothing to compare", report.note)


if __name__ == "__main__":
    unittest.main()
