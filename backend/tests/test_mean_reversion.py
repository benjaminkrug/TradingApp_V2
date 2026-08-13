import unittest
from datetime import datetime, timedelta, timezone

from app.backtest.reference_engine import run_reference_backtest
from app.data.point_in_time import Bar, PointInTimeSeries
from app.strategies.mean_reversion import MeanReversionStrategy

START = datetime(2026, 1, 2, 14, 30, tzinfo=timezone.utc)


def make_bars(closes: list[float]) -> list[Bar]:
    return [
        Bar(symbol="TEST", timestamp=START + timedelta(minutes=5 * i), open=c, high=c + 0.3, low=c - 0.3, close=c, volume=1000)
        for i, c in enumerate(closes)
    ]


def run_actions(strategy, bars: list[Bar]) -> list[str]:
    cursor = PointInTimeSeries(bars).new_cursor()
    return [strategy(cursor) for _ in cursor]


class TestMeanReversionStrategy(unittest.TestCase):
    def test_buys_a_confirmed_bounce_from_an_oversold_extreme(self):
        # flat baseline (EMA/ATR warm-up), a decline deep enough to push
        # distance_in_atr past -2.0, then a small uptick while still deeply
        # oversold - this is the "confirmed bounce, not catching the exact
        # bottom" entry condition
        closes = [100] * 15 + [90, 80, 70, 65, 66, 67]
        bars = make_bars(closes)
        strategy = MeanReversionStrategy(ema_period=10, atr_period=5, oversold_atr_multiple=2.0)

        actions = run_actions(strategy, bars)

        self.assertEqual(actions[19], "BUY")  # close=66, up from 65, still <= -2.0 ATRs below EMA
        # the strictly declining bars before it must never buy - none of
        # them are a confirmed upward turn yet
        self.assertNotIn("BUY", actions[15:19])

    def test_sells_once_price_reverts_back_to_the_ema(self):
        closes = [100] * 15 + [90, 80, 70, 65, 66, 67, 75, 85, 95, 100]
        bars = make_bars(closes)
        strategy = MeanReversionStrategy(ema_period=10, atr_period=5, oversold_atr_multiple=2.0)

        actions = run_actions(strategy, bars)

        self.assertEqual(actions[19], "BUY")
        self.assertEqual(actions[22], "SELL")  # close=85, distance_in_atr back to >= 0

    def test_never_buys_on_a_flat_series(self):
        # on a perfectly flat series, distance_in_atr is exactly 0.0 once
        # the EMA/ATR warm up - that satisfies the SELL condition (z >= 0,
        # "already at the mean"), which is correct, not a bug: there is
        # nothing oversold to buy here. Those SELL signals are no-ops
        # against a position that was never opened (reference_engine's own
        # "SELL without a position is ignored" rule, Phase 2) - confirmed
        # below via a zero-fill backtest rather than asserted blindly.
        bars = make_bars([100.0] * 20)
        strategy = MeanReversionStrategy(ema_period=10, atr_period=5)
        actions = run_actions(strategy, bars)
        self.assertNotIn("BUY", actions)

        result = run_reference_backtest(bars, strategy, fee_per_share=0.0)
        self.assertEqual(result.fills, [])

    def test_end_to_end_backtest_matches_hand_calculation(self):
        closes = [100] * 15 + [90, 80, 70, 65, 66, 67, 75, 85, 95, 100]
        bars = make_bars(closes)
        strategy = MeanReversionStrategy(ema_period=10, atr_period=5, oversold_atr_multiple=2.0)

        result = run_reference_backtest(bars, strategy, fee_per_share=0.0)

        # BUY signal after bar 19 (close=66) fills at bar 20's open = 67
        # SELL signal after bar 22 (close=85) fills at bar 23's open = 95
        self.assertEqual(len(result.fills), 2)
        self.assertEqual(result.fills[0].side, "BUY")
        self.assertAlmostEqual(result.fills[0].price, 67)
        self.assertEqual(result.fills[1].side, "SELL")
        self.assertAlmostEqual(result.fills[1].price, 95)
        self.assertAlmostEqual(result.realized_pnl, 95 - 67)


if __name__ == "__main__":
    unittest.main()
