import unittest

from app.signals.risk import DailyLossGuard, atr_stop_loss, position_size, risk_reward_target


class TestAtrStopLoss(unittest.TestCase):
    def test_matches_hand_calculation(self):
        self.assertAlmostEqual(atr_stop_loss(100, 2.0, 1.5), 97.0)

    def test_rejects_non_positive_multiple(self):
        with self.assertRaises(ValueError):
            atr_stop_loss(100, 2.0, 0)


class TestRiskRewardTarget(unittest.TestCase):
    def test_matches_hand_calculation(self):
        # risk = 100-97 = 3; target = 100 + 2*3 = 106
        self.assertAlmostEqual(risk_reward_target(100, 97, 2.0), 106.0)

    def test_rejects_stop_at_or_above_entry(self):
        with self.assertRaises(ValueError):
            risk_reward_target(100, 100, 2.0)
        with self.assertRaises(ValueError):
            risk_reward_target(100, 101, 2.0)


class TestPositionSize(unittest.TestCase):
    def test_matches_roadmap_worked_example(self):
        # ROADMAP.md Abschnitt 13: 50000 account, 0.5% risk, entry 100, stop 98 -> 125 shares
        self.assertAlmostEqual(position_size(50000, 0.005, 100, 98), 125.0)

    def test_rejects_risk_pct_out_of_range(self):
        with self.assertRaises(ValueError):
            position_size(50000, 0.0, 100, 98)
        with self.assertRaises(ValueError):
            position_size(50000, 1.0, 100, 98)

    def test_rejects_stop_at_or_above_entry(self):
        with self.assertRaises(ValueError):
            position_size(50000, 0.005, 100, 100)


class TestDailyLossGuard(unittest.TestCase):
    def test_blocks_trading_once_limit_is_breached(self):
        guard = DailyLossGuard(max_daily_loss=250)
        self.assertTrue(guard.can_trade())

        guard.record_pnl(-100)
        self.assertTrue(guard.can_trade())

        guard.record_pnl(-151)  # cumulative -251, past the 250 limit
        self.assertFalse(guard.can_trade())

    def test_exactly_at_the_limit_trips(self):
        guard = DailyLossGuard(max_daily_loss=250)
        guard.record_pnl(-250)
        self.assertFalse(guard.can_trade())

    def test_just_short_of_the_limit_does_not_trip(self):
        guard = DailyLossGuard(max_daily_loss=250)
        guard.record_pnl(-249)
        self.assertTrue(guard.can_trade())

    def test_reset_clears_the_block(self):
        guard = DailyLossGuard(max_daily_loss=100)
        guard.record_pnl(-150)
        self.assertFalse(guard.can_trade())
        guard.reset()
        self.assertTrue(guard.can_trade())
        self.assertEqual(guard.cumulative_pnl, 0.0)

    def test_a_subsequent_win_does_not_silently_undo_a_trip(self):
        # this is the whole point of the guard being "sticky": once tripped,
        # a big win recorded afterwards must NOT re-enable trading on its
        # own - only an explicit reset() may do that (found and fixed
        # during Phase 6 development - the first version recomputed
        # can_trade() live from cumulative_pnl each call, which let a
        # large enough win quietly cancel a trip).
        guard = DailyLossGuard(max_daily_loss=100)
        guard.record_pnl(-150)
        self.assertFalse(guard.can_trade())

        guard.record_pnl(1000)
        self.assertFalse(guard.can_trade())  # still tripped despite the win

    def test_rejects_non_positive_limit(self):
        with self.assertRaises(ValueError):
            DailyLossGuard(max_daily_loss=0)


if __name__ == "__main__":
    unittest.main()
