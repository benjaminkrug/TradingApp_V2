import unittest
from datetime import datetime, timedelta, timezone

from app.backtest.reference_engine import Fill
from app.validation.metrics import Trade, compute_metrics, trades_from_fills


def make_fill(side: str, price: float, i: int, fee: float = 0.0) -> Fill:
    start = datetime(2026, 1, 2, 9, 30, tzinfo=timezone.utc)
    return Fill(symbol="TEST", timestamp=start + timedelta(minutes=5 * i), side=side, price=price, quantity=1.0, fee=fee)


class TestTradesFromFills(unittest.TestCase):
    def test_pairs_buy_and_sell(self):
        fills = [make_fill("BUY", 100, 0), make_fill("SELL", 110, 1)]
        trades = trades_from_fills(fills)
        self.assertEqual(len(trades), 1)
        self.assertAlmostEqual(trades[0].pnl, 10.0)

    def test_trailing_unmatched_buy_produces_no_trade(self):
        fills = [make_fill("BUY", 100, 0), make_fill("SELL", 110, 1), make_fill("BUY", 120, 2)]
        trades = trades_from_fills(fills)
        self.assertEqual(len(trades), 1)  # the trailing BUY has no matching SELL

    def test_fees_are_subtracted_from_both_legs(self):
        fills = [make_fill("BUY", 100, 0, fee=0.5), make_fill("SELL", 110, 1, fee=0.5)]
        trades = trades_from_fills(fills)
        # (110-100)*1 - 0.5 - 0.5 = 9.0
        self.assertAlmostEqual(trades[0].pnl, 9.0)

    def test_rejects_a_second_buy_while_a_position_is_open(self):
        fills = [make_fill("BUY", 100, 0), make_fill("BUY", 105, 1)]
        with self.assertRaises(ValueError):
            trades_from_fills(fills)

    def test_rejects_a_sell_for_a_different_symbol_than_the_open_position(self):
        start = datetime(2026, 1, 2, 9, 30, tzinfo=timezone.utc)
        fills = [
            Fill(symbol="AAA", timestamp=start, side="BUY", price=100, quantity=1.0, fee=0.0),
            Fill(symbol="BBB", timestamp=start + timedelta(minutes=5), side="SELL", price=110, quantity=1.0, fee=0.0),
        ]
        with self.assertRaises(ValueError):
            trades_from_fills(fills)


class TestComputeMetrics(unittest.TestCase):
    def test_matches_hand_calculation(self):
        # pnls: 10, -5, -5, 20, -1, -1, -1
        trades = [
            Trade(symbol="TEST", entry_time=None, exit_time=None, entry_price=0, exit_price=0, quantity=1, pnl=pnl)
            for pnl in [10, -5, -5, 20, -1, -1, -1]
        ]

        m = compute_metrics(trades)

        self.assertEqual(m.trade_count, 7)
        self.assertAlmostEqual(m.win_rate, 2 / 7)
        # gross profit = 10+20=30, gross loss = 5+5+1+1+1=13
        self.assertAlmostEqual(m.profit_factor, 30 / 13)
        self.assertAlmostEqual(m.total_pnl, 17)
        self.assertAlmostEqual(m.average_trade, 17 / 7)
        self.assertEqual(m.max_consecutive_losses, 3)

    def test_empty_trades_returns_zeroed_metrics(self):
        m = compute_metrics([])
        self.assertEqual(m.trade_count, 0)
        self.assertIsNone(m.profit_factor)
        self.assertEqual(m.total_pnl, 0.0)

    def test_profit_factor_is_none_without_any_losses(self):
        trades = [
            Trade(symbol="TEST", entry_time=None, exit_time=None, entry_price=0, exit_price=0, quantity=1, pnl=pnl)
            for pnl in [5, 10]
        ]
        m = compute_metrics(trades)
        self.assertIsNone(m.profit_factor)


if __name__ == "__main__":
    unittest.main()
