import unittest
from datetime import datetime, timedelta, timezone

from app.data.point_in_time import Bar
from app.validation.evaluate import compute_trade_stats, evaluate, trade_return_bp
from app.validation.metrics import Trade

# 09:30 New York on a regular trading day, expressed in UTC (EDT = UTC-4).
SESSION_OPEN = datetime(2026, 3, 9, 13, 30, tzinfo=timezone.utc)


def make_trade(entry_price, quantity, pnl, entry_time=SESSION_OPEN, exit_time=None):
    return Trade(
        symbol="AAA",
        entry_time=entry_time,
        exit_time=exit_time or entry_time + timedelta(minutes=30),
        entry_price=entry_price,
        exit_price=entry_price + pnl / quantity,
        quantity=quantity,
        pnl=pnl,
    )


class TestTradeReturnBp(unittest.TestCase):
    def test_matches_hand_calculation(self):
        # notional = 100 * 10 = 1000; 25 / 1000 = 0.025 = 250 basis points
        self.assertAlmostEqual(trade_return_bp(make_trade(100.0, 10, 25.0)), 250.0)

    def test_is_scale_free_across_position_sizes(self):
        """The whole reason for using basis points instead of dollars: two
        trades with the same percentage outcome must score identically even
        if risk-based sizing gave them very different position sizes."""
        small = trade_return_bp(make_trade(100.0, 1, 1.0))
        large = trade_return_bp(make_trade(100.0, 500, 500.0))
        self.assertAlmostEqual(small, large)
        self.assertAlmostEqual(small, 100.0)

    def test_zero_notional_does_not_divide_by_zero(self):
        self.assertEqual(trade_return_bp(make_trade(0.0, 10, 5.0)), 0.0)


class TestComputeTradeStats(unittest.TestCase):
    def test_matches_hand_calculation(self):
        # returns in bp: +250, -100, +50  (each notional deliberately 1000)
        trades = [
            make_trade(100.0, 10, 25.0),
            make_trade(200.0, 5, -10.0),
            make_trade(50.0, 20, 5.0),
        ]
        stats = compute_trade_stats(trades)

        self.assertEqual(stats.trade_count, 3)
        # mean = (250 - 100 + 50) / 3 = 66.667
        self.assertAlmostEqual(stats.mean_bp, 200.0 / 3, places=4)
        # sample stdev: deviations 183.333, -166.667, -16.667
        # -> sum of squares 61666.67, / 2 = 30833.33, sqrt = 175.5943
        self.assertAlmostEqual(stats.stdev_bp, 175.5943, places=3)
        # t = 66.6667 / (175.5943 / sqrt(3)) = 0.6576
        self.assertAlmostEqual(stats.t_stat_naive, 0.6576, places=3)
        self.assertAlmostEqual(stats.win_rate, 2 / 3)
        self.assertAlmostEqual(stats.total_pnl, 20.0)

    def test_empty_input(self):
        stats = compute_trade_stats([])
        self.assertTrue(stats.is_empty)
        self.assertEqual(stats.t_stat_naive, 0.0)

    def test_overnight_share_counts_session_crossings_not_elapsed_hours(self):
        """A trade can last 20 hours and stay inside one session date only if
        the session spans it; what matters for DECISIONS.md #2 is whether the
        New-York session date changed, not raw duration."""
        same_session = make_trade(100.0, 10, 1.0, exit_time=SESSION_OPEN + timedelta(hours=2))
        crosses = make_trade(100.0, 10, 1.0, exit_time=SESSION_OPEN + timedelta(days=1))
        stats = compute_trade_stats([same_session, crosses])
        self.assertAlmostEqual(stats.overnight_share, 0.5)
        self.assertAlmostEqual(stats.max_holding_days, 1.0)


class TestEvaluateWiring(unittest.TestCase):
    """End-to-end smoke test on a trivially rising series: confirms the paper
    engine and the reference-engine cross-check both run off the same bars
    and that buy-and-hold is measured over the same window."""

    def _rising_bars(self, count=120):
        bars = []
        price = 100.0
        for i in range(count):
            bars.append(
                Bar(
                    symbol="AAA",
                    timestamp=SESSION_OPEN + timedelta(minutes=5 * i),
                    open=price,
                    high=price + 0.5,
                    low=price - 0.5,
                    close=price + 0.2,
                    volume=1000,
                )
            )
            price += 0.2
        return bars

    def test_runs_both_engines_and_measures_buy_and_hold(self):
        bars = self._rising_bars()

        def always_buy(_cursor):
            return "BUY"

        ev = evaluate(
            bars=bars,
            strategy_factory=lambda: always_buy,
            strategy_name="AlwaysBuy",
            starting_equity=50_000.0,
            risk_pct=0.0025,
            fee_per_share=0.005,
            max_daily_loss=1_500.0,
            flatten_at_session_end=False,
        )

        # buy-and-hold = (last close - first open) / first open, in bp
        expected_bh = (bars[-1].close - bars[0].open) / bars[0].open * 10_000
        self.assertAlmostEqual(ev.buy_and_hold_bp["AAA"], expected_bh, places=6)
        self.assertEqual(ev.session_count, 1)
        self.assertGreaterEqual(ev.reference_stats.trade_count, 0)


if __name__ == "__main__":
    unittest.main()
