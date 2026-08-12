import unittest
from datetime import datetime, timedelta

from app.backtest.reference_engine import run_reference_backtest
from app.data.point_in_time import Bar, SimulationCursor


def make_bars(closes: list[float]) -> list[Bar]:
    start = datetime(2026, 1, 2, 9, 30)
    return [
        Bar(
            timestamp=start + timedelta(minutes=5 * i),
            open=c,
            high=c,
            low=c,
            close=c,
            volume=1000,
        )
        for i, c in enumerate(closes)
    ]


class TestReferenceEngineKnownOutcome(unittest.TestCase):
    """Hand-computed scenario per ROADMAP.md Abschnitt 9: verify the engine
    against an expected result we can check with pen and paper, before
    trusting it (or a heavier framework built on the same assumptions) with
    anything else."""

    def test_single_round_trip_matches_hand_calculation(self):
        # closes: 100, 102, 105, 103, 108 (bar indices 0..4)
        bars = make_bars([100, 102, 105, 103, 108])

        def signal_fn(cursor: SimulationCursor):
            n = len(cursor.history)
            if n == 2:  # buy at bar index 1, close=102
                return "BUY"
            if n == 4:  # sell at bar index 3, close=103
                return "SELL"
            return "HOLD"

        result = run_reference_backtest(bars, signal_fn, fee_per_share=0.01)

        # expected: (103 - 102) * 1 share - 2 * 0.01 fee = 0.98
        self.assertAlmostEqual(result.realized_pnl, 0.98, places=6)
        self.assertEqual(len(result.fills), 2)
        self.assertEqual(result.fills[0].side, "BUY")
        self.assertEqual(result.fills[0].price, 102)
        self.assertEqual(result.fills[1].side, "SELL")
        self.assertEqual(result.fills[1].price, 103)

    def test_losing_trade_matches_hand_calculation(self):
        # closes: 50, 48, 45 — buy at bar 0 (close=50), sell at bar 2 (close=45)
        bars = make_bars([50, 48, 45])

        def signal_fn(cursor: SimulationCursor):
            n = len(cursor.history)
            if n == 1:
                return "BUY"
            if n == 3:
                return "SELL"
            return "HOLD"

        result = run_reference_backtest(bars, signal_fn, fee_per_share=0.0)

        # expected: (45 - 50) * 1 share = -5.0
        self.assertAlmostEqual(result.realized_pnl, -5.0, places=6)

    def test_sell_without_open_position_is_ignored(self):
        bars = make_bars([100, 101, 102])

        def signal_fn(cursor: SimulationCursor):
            return "SELL"  # never actually bought anything

        result = run_reference_backtest(bars, signal_fn, fee_per_share=0.0)

        self.assertEqual(result.fills, [])
        self.assertEqual(result.realized_pnl, 0.0)

    def test_no_signal_produces_no_trades(self):
        bars = make_bars([100, 100, 100, 100])

        def signal_fn(cursor: SimulationCursor):
            return "HOLD"

        result = run_reference_backtest(bars, signal_fn)

        self.assertEqual(result.fills, [])
        self.assertEqual(result.realized_pnl, 0.0)


if __name__ == "__main__":
    unittest.main()
