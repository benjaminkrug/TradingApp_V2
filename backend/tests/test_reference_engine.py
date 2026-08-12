import unittest
from datetime import datetime, timedelta, timezone

from app.backtest.reference_engine import run_reference_backtest
from app.data.point_in_time import Bar, SimulationCursor


def make_bars(ohlc: list[tuple[float, float]], symbol: str = "TEST") -> list[Bar]:
    """ohlc: (open, close) pairs. Deliberately distinct per bar so a test
    would fail if the engine used close instead of open for fills — see
    reference_engine.py's execution-timing model."""
    start = datetime(2026, 1, 2, 9, 30, tzinfo=timezone.utc)
    bars = []
    for i, (o, c) in enumerate(ohlc):
        bars.append(
            Bar(
                symbol=symbol,
                timestamp=start + timedelta(minutes=5 * i),
                open=o,
                high=max(o, c),
                low=min(o, c),
                close=c,
                volume=1000,
            )
        )
    return bars


class TestReferenceEngineKnownOutcome(unittest.TestCase):
    """Hand-computed scenarios per ROADMAP.md Abschnitt 9: verify the engine
    against an expected result we can check with pen and paper, before
    trusting it (or a heavier framework built on the same assumptions) with
    anything else."""

    def test_single_round_trip_fills_at_next_bar_open_not_signal_bar_close(self):
        # bar index:  0            1              2              3              4
        # (open,close): (100,100.5) (100.5,102)   (102.2,105)    (104.8,103)    (103.1,108)
        bars = make_bars([(100, 100.5), (100.5, 102), (102.2, 105), (104.8, 103), (103.1, 108)])

        def signal_fn(cursor: SimulationCursor):
            n = len(cursor.history)
            if n == 2:  # decided after bar index 1 -> fills at bar index 2's open
                return "BUY"
            if n == 4:  # decided after bar index 3 -> fills at bar index 4's open
                return "SELL"
            return "HOLD"

        result = run_reference_backtest(bars, signal_fn, fee_per_share=0.01)

        # BUY at bar2.open=102.2, SELL at bar4.open=103.1
        # expected: (103.1 - 102.2) * 1 - 2 * 0.01 = 0.9 - 0.02 = 0.88
        # (NOT 0.98, which is what same-bar-close fills at 102/103 would give -
        # that mismatch is exactly what this test is designed to catch.)
        self.assertAlmostEqual(result.realized_pnl, 0.88, places=6)
        self.assertEqual(len(result.fills), 2)
        self.assertEqual(result.fills[0].side, "BUY")
        self.assertAlmostEqual(result.fills[0].price, 102.2, places=6)
        self.assertEqual(result.fills[1].side, "SELL")
        self.assertAlmostEqual(result.fills[1].price, 103.1, places=6)
        self.assertEqual(result.fills[0].symbol, "TEST")
        self.assertEqual(result.fills[1].symbol, "TEST")

    def test_losing_trade_matches_hand_calculation(self):
        # opens used for fills: bar1.open=48 (BUY), bar3.open=43 (SELL)
        bars = make_bars([(50, 49), (48, 47), (46, 44), (43, 42)])

        def signal_fn(cursor: SimulationCursor):
            n = len(cursor.history)
            if n == 1:  # fills at bar1.open
                return "BUY"
            if n == 3:  # fills at bar3.open
                return "SELL"
            return "HOLD"

        result = run_reference_backtest(bars, signal_fn, fee_per_share=0.0)

        # expected: (43 - 48) * 1 = -5.0
        self.assertAlmostEqual(result.realized_pnl, -5.0, places=6)

    def test_multiple_sequential_round_trips(self):
        opens = [10, 11, 12, 13, 14, 15, 16, 17, 18]
        bars = make_bars([(o, o + 0.3) for o in opens])

        def signal_fn(cursor: SimulationCursor):
            n = len(cursor.history)
            if n in (1, 5):
                return "BUY"
            if n in (3, 7):
                return "SELL"
            return "HOLD"

        result = run_reference_backtest(bars, signal_fn, fee_per_share=0.0)

        # round trip 1: BUY @ bar1.open=11, SELL @ bar3.open=13 -> +2.0
        # round trip 2: BUY @ bar5.open=15, SELL @ bar7.open=17 -> +2.0
        self.assertEqual(len(result.fills), 4)
        self.assertAlmostEqual(result.realized_pnl, 4.0, places=6)

    def test_second_buy_signal_while_in_position_is_ignored(self):
        bars = make_bars([(10, 10.1), (11, 11.1), (12, 12.1), (13, 13.1)])

        def signal_fn(cursor: SimulationCursor):
            return "BUY"  # keeps firing, never sells

        result = run_reference_backtest(bars, signal_fn, fee_per_share=0.0)

        # only the first BUY (at bar1.open) should ever fill - no pyramiding
        self.assertEqual(len(result.fills), 1)
        self.assertAlmostEqual(result.fills[0].price, 11, places=6)
        self.assertEqual(result.realized_pnl, 0.0)  # never sold, nothing realized

    def test_sell_without_open_position_is_ignored(self):
        bars = make_bars([(100, 100.5), (101, 101.5), (102, 102.5)])

        def signal_fn(cursor: SimulationCursor):
            return "SELL"  # never actually bought anything

        result = run_reference_backtest(bars, signal_fn, fee_per_share=0.0)

        self.assertEqual(result.fills, [])
        self.assertEqual(result.realized_pnl, 0.0)

    def test_signal_on_final_bar_is_never_filled(self):
        # only 3 bars; signal fires exactly when history covers all of them,
        # i.e. on the last bar - there is no next bar left to fill it at.
        bars = make_bars([(10, 10.1), (11, 11.1), (12, 12.1)])

        def signal_fn(cursor: SimulationCursor):
            return "BUY" if len(cursor.history) == len(bars) else "HOLD"

        result = run_reference_backtest(bars, signal_fn, fee_per_share=0.0)

        self.assertEqual(result.fills, [])
        self.assertEqual(result.realized_pnl, 0.0)

    def test_no_signal_produces_no_trades(self):
        bars = make_bars([(100, 100), (100, 100), (100, 100), (100, 100)])

        def signal_fn(cursor: SimulationCursor):
            return "HOLD"

        result = run_reference_backtest(bars, signal_fn)

        self.assertEqual(result.fills, [])
        self.assertEqual(result.realized_pnl, 0.0)


if __name__ == "__main__":
    unittest.main()
