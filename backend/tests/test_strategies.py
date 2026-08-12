import unittest
from datetime import datetime, timedelta, timezone

from app.backtest.reference_engine import run_reference_backtest
from app.data.point_in_time import Bar, PointInTimeSeries
from app.strategies.ema_pullback import EmaPullbackStrategy
from app.strategies.opening_range_breakout import OpeningRangeBreakoutStrategy
from app.strategies.vwap_momentum import VwapMomentumStrategy

SESSION_START = datetime(2026, 1, 2, 14, 30, tzinfo=timezone.utc)  # 9:30 NY


def make_bars(closes: list[float], volumes: list[float] = None, start=SESSION_START) -> list[Bar]:
    volumes = volumes or [1000] * len(closes)
    return [
        Bar(
            symbol="TEST",
            timestamp=start + timedelta(minutes=5 * i),
            open=c,
            high=c + 0.2,
            low=c - 0.2,
            close=c,
            volume=v,
        )
        for i, (c, v) in enumerate(zip(closes, volumes))
    ]


def run_actions(strategy, bars: list[Bar]) -> list[str]:
    cursor = PointInTimeSeries(bars).new_cursor()
    return [strategy(cursor) for _ in cursor]


class TestVwapMomentumStrategy(unittest.TestCase):
    def test_holds_until_indicators_warm_up_then_buys_in_a_steady_uptrend(self):
        closes = [100 + i * 0.5 for i in range(10)]
        bars = make_bars(closes)
        actions = run_actions(VwapMomentumStrategy(fast_period=3, slow_period=5), bars)

        # fast/slow EMA need index >= slow_period-1 = 4 to both be defined
        self.assertEqual(actions[:4], ["HOLD"] * 4)
        self.assertTrue(all(a == "BUY" for a in actions[4:]))

    def test_sells_on_a_sharp_drop_below_vwap(self):
        closes = [100 + i * 0.5 for i in range(10)] + [95, 90, 85]
        bars = make_bars(closes)
        actions = run_actions(VwapMomentumStrategy(fast_period=3, slow_period=5), bars)

        self.assertEqual(actions[10:], ["SELL", "SELL", "SELL"])

    def test_end_to_end_backtest_matches_hand_calculation(self):
        closes = [100 + i * 0.5 for i in range(10)] + [95, 90, 85]
        bars = make_bars(closes)
        strategy = VwapMomentumStrategy(fast_period=3, slow_period=5)

        result = run_reference_backtest(bars, strategy, fee_per_share=0.0)

        # BUY signal fires after bar index 4 (open=close=102.5 in this
        # synthetic data) -> fills at bar5's open = 102.5.
        # SELL signal doesn't fire until after bar index 10 (close=95) -
        # VWAP is a cumulative, lagging average, so it takes the crash a
        # few bars to pull it down far enough to cross - fills at bar11's
        # open = 90. This is a real, worth-noting lesson, not a test bug:
        # a lagging-indicator exit can let a strategy give back the entire
        # gain (and then some) once the move reverses hard, even though
        # the entry itself was "obviously" well-timed in an uptrend.
        self.assertEqual(len(result.fills), 2)
        self.assertEqual(result.fills[0].side, "BUY")
        self.assertAlmostEqual(result.fills[0].price, 102.5)
        self.assertEqual(result.fills[1].side, "SELL")
        self.assertAlmostEqual(result.fills[1].price, 90)
        self.assertAlmostEqual(result.realized_pnl, 90 - 102.5)


class TestEmaPullbackStrategy(unittest.TestCase):
    def test_sells_on_trend_break_then_buys_on_pullback_resumption(self):
        # strong uptrend, one-bar dip below the slow EMA, then resumption
        closes = [100 + i * 1.0 for i in range(8)] + [104.0, 107.0]
        bars = make_bars(closes)

        actions = run_actions(EmaPullbackStrategy(fast_period=3, slow_period=6), bars)

        self.assertEqual(actions[8], "SELL")  # 104.0 dips below the slow EMA
        self.assertEqual(actions[9], "BUY")  # 107.0 resumes above the fast EMA

    def test_holds_during_a_flat_series(self):
        bars = make_bars([100.0] * 10)
        actions = run_actions(EmaPullbackStrategy(fast_period=3, slow_period=6), bars)
        self.assertTrue(all(a == "HOLD" for a in actions))


class TestOpeningRangeBreakoutStrategy(unittest.TestCase):
    def _scenario_bars(self) -> list[Bar]:
        def bar(i, o, h, l, c, v):
            return Bar(
                symbol="TEST",
                timestamp=SESSION_START + timedelta(minutes=5 * i),
                open=o,
                high=h,
                low=l,
                close=c,
                volume=v,
            )

        return [
            bar(0, 100, 100.5, 99.5, 100, 500),
            bar(1, 100, 101, 99.8, 100.5, 500),
            bar(2, 100.5, 101, 100, 100.8, 500),  # opening range: low=99.5, high=101
            bar(3, 100.8, 102, 100.8, 101.5, 800),  # breaks above 101, volume confirmed
            bar(4, 101.5, 101.6, 100.5, 100.9, 400),  # falls back below range high -> SELL
        ]

    def test_holds_while_range_is_forming_then_breaks_out_then_fails(self):
        bars = self._scenario_bars()
        actions = run_actions(OpeningRangeBreakoutStrategy(range_bars=3), bars)
        self.assertEqual(actions, ["HOLD", "HOLD", "HOLD", "BUY", "SELL"])

    def test_no_buy_without_volume_confirmation(self):
        bars = self._scenario_bars()
        # crank the confirmation bar way up so the same breakout no longer qualifies
        strategy = OpeningRangeBreakoutStrategy(range_bars=3, volume_confirmation_multiple=10.0)
        actions = run_actions(strategy, bars)
        self.assertNotIn("BUY", actions)

    def test_end_to_end_backtest(self):
        bars = self._scenario_bars()
        strategy = OpeningRangeBreakoutStrategy(range_bars=3)

        result = run_reference_backtest(bars, strategy, fee_per_share=0.0)

        # BUY signal on bar3 fills at bar4's open (101.5); SELL signal on
        # bar4 has no next bar to fill at (see reference_engine.py) and is
        # dropped - so this scenario deliberately ends with an open,
        # unrealized position rather than a closed round trip.
        self.assertEqual(len(result.fills), 1)
        self.assertEqual(result.fills[0].side, "BUY")
        self.assertAlmostEqual(result.fills[0].price, 101.5)
        self.assertEqual(result.realized_pnl, 0.0)


if __name__ == "__main__":
    unittest.main()
