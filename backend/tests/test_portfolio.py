import unittest
from datetime import datetime, timezone

from app.paper.portfolio import InsufficientCashError, Portfolio
from app.validation.metrics import trades_from_fills

T0 = datetime(2026, 1, 2, 9, 30, tzinfo=timezone.utc)
T1 = datetime(2026, 1, 2, 9, 35, tzinfo=timezone.utc)


class TestPortfolio(unittest.TestCase):
    def test_open_position_deducts_cash_price_plus_fee_scaled_by_quantity(self):
        portfolio = Portfolio(starting_cash=10_000.0)
        portfolio.open_position(
            "AAPL", T0, entry_price=100.0, quantity=10.0, stop=98.0, target=104.0, fee_per_share=1.0
        )
        # fee is per-share, scaled by quantity: 10000 - (100*10 + 1.0*10) = 8990
        self.assertAlmostEqual(portfolio.cash, 8990.0)
        self.assertAlmostEqual(portfolio.fills[0].fee, 10.0)
        self.assertIn("AAPL", portfolio.positions)
        self.assertEqual(len(portfolio.fills), 1)
        self.assertEqual(portfolio.fills[0].side, "BUY")

    def test_open_position_rejects_pyramiding(self):
        portfolio = Portfolio(starting_cash=10_000.0)
        portfolio.open_position("AAPL", T0, 100.0, 10.0, 98.0, 104.0, fee_per_share=1.0)
        with self.assertRaises(ValueError):
            portfolio.open_position("AAPL", T1, 101.0, 5.0, 99.0, 105.0, fee_per_share=1.0)

    def test_close_position_computes_hand_verified_pnl(self):
        portfolio = Portfolio(starting_cash=10_000.0)
        portfolio.open_position(
            "AAPL", T0, entry_price=100.0, quantity=10.0, stop=98.0, target=104.0, fee_per_share=1.0
        )
        fill, pnl = portfolio.close_position("AAPL", T1, exit_price=110.0, fee_per_share=1.0)

        # entry fee = 1.0*10 = 10, exit fee = 1.0*10 = 10
        # pnl = (110-100)*10 - entry_fee(10) - exit_fee(10) = 80
        self.assertAlmostEqual(pnl, 80.0)
        self.assertAlmostEqual(fill.fee, 10.0)
        self.assertEqual(fill.side, "SELL")
        self.assertNotIn("AAPL", portfolio.positions)
        # cash: 8990 + (110*10 - 10) = 8990 + 1090 = 10080 = starting(10000) + pnl(80)
        self.assertAlmostEqual(portfolio.cash, 10_080.0)
        self.assertAlmostEqual(portfolio.cash, portfolio.starting_cash + pnl)

    def test_close_position_pnl_matches_trades_from_fills(self):
        portfolio = Portfolio(starting_cash=10_000.0)
        portfolio.open_position("AAPL", T0, 100.0, 10.0, 98.0, 104.0, fee_per_share=1.0)
        _, pnl = portfolio.close_position("AAPL", T1, 110.0, fee_per_share=1.0)

        trades = trades_from_fills(portfolio.fills)
        self.assertEqual(len(trades), 1)
        self.assertAlmostEqual(trades[0].pnl, pnl)

    def test_close_position_without_open_position_raises(self):
        portfolio = Portfolio(starting_cash=10_000.0)
        with self.assertRaises(ValueError):
            portfolio.close_position("AAPL", T0, 100.0, fee_per_share=1.0)

    def test_equity_marks_open_positions_to_last_known_price(self):
        portfolio = Portfolio(starting_cash=10_000.0)
        portfolio.open_position("AAPL", T0, 100.0, 10.0, 98.0, 104.0, fee_per_share=1.0)
        # before any mark(), equity falls back to entry_price
        self.assertAlmostEqual(portfolio.equity(), 8990.0 + 10.0 * 100.0)

        portfolio.mark("AAPL", 105.0)
        self.assertAlmostEqual(portfolio.equity(), 8990.0 + 10.0 * 105.0)

    def test_equity_with_no_positions_is_just_cash(self):
        portfolio = Portfolio(starting_cash=10_000.0)
        self.assertAlmostEqual(portfolio.equity(), 10_000.0)

    def test_rejects_non_positive_starting_cash(self):
        with self.assertRaises(ValueError):
            Portfolio(starting_cash=0.0)

    def test_fee_scales_with_quantity_not_flat_per_fill(self):
        # Regression test for a bug caught during development: an earlier
        # version applied `fee` as a flat per-fill amount (copying
        # reference_engine.py's convention, which only works there because
        # it always trades a single unit). Two otherwise-identical trades
        # with different quantities must incur proportionally different
        # fees, not the same flat fee.
        small = Portfolio(starting_cash=100_000.0)
        small.open_position("AAPL", T0, 100.0, 1.0, 98.0, 104.0, fee_per_share=0.01)
        _, small_pnl = small.close_position("AAPL", T1, 100.0, fee_per_share=0.01)  # flat price, fee-only pnl

        large = Portfolio(starting_cash=100_000.0)
        large.open_position("AAPL", T0, 100.0, 125.0, 98.0, 104.0, fee_per_share=0.01)
        _, large_pnl = large.close_position("AAPL", T1, 100.0, fee_per_share=0.01)

        self.assertAlmostEqual(small_pnl, -0.02)  # 1 share * $0.01 fee, twice (entry+exit)
        self.assertAlmostEqual(large_pnl, -2.5)  # 125 shares * $0.01 fee, twice

    def test_open_position_rejects_order_exceeding_available_cash(self):
        # 100 shares at $100 = $10,000 cost, but only $5,000 cash available -
        # must be rejected, not silently filled on margin (regression test
        # for the negative-cash bug found via scripts/phase9_paper_trading_demo.py).
        portfolio = Portfolio(starting_cash=5_000.0)
        with self.assertRaises(InsufficientCashError):
            portfolio.open_position("AAPL", T0, entry_price=100.0, quantity=100.0, stop=98.0, target=104.0, fee_per_share=0.0)
        self.assertAlmostEqual(portfolio.cash, 5_000.0)  # unchanged - the rejected order must not touch cash
        self.assertNotIn("AAPL", portfolio.positions)
        self.assertEqual(portfolio.fills, [])

    def test_rejected_orders_counter_increments_on_insufficient_cash(self):
        portfolio = Portfolio(starting_cash=5_000.0)
        self.assertEqual(portfolio.rejected_orders, 0)
        with self.assertRaises(InsufficientCashError):
            portfolio.open_position("AAPL", T0, 100.0, 100.0, 98.0, 104.0, fee_per_share=0.0)
        self.assertEqual(portfolio.rejected_orders, 1)
        with self.assertRaises(InsufficientCashError):
            portfolio.open_position("MSFT", T0, 100.0, 100.0, 98.0, 104.0, fee_per_share=0.0)
        self.assertEqual(portfolio.rejected_orders, 2)

    def test_open_position_allows_order_exactly_at_available_cash(self):
        portfolio = Portfolio(starting_cash=1_000.0)
        portfolio.open_position("AAPL", T0, entry_price=100.0, quantity=10.0, stop=98.0, target=104.0, fee_per_share=0.0)
        self.assertAlmostEqual(portfolio.cash, 0.0)


if __name__ == "__main__":
    unittest.main()
