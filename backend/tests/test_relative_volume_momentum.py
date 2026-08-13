import unittest
from datetime import datetime, timedelta, timezone

from app.backtest.reference_engine import run_reference_backtest
from app.data.point_in_time import Bar, PointInTimeSeries
from app.strategies.relative_volume_momentum import RelativeVolumeMomentumStrategy

START = datetime(2026, 1, 2, 14, 30, tzinfo=timezone.utc)


def bar(i: int, o: float, h: float, l: float, c: float, v: float) -> Bar:
    return Bar(symbol="TEST", timestamp=START + timedelta(minutes=5 * i), open=o, high=h, low=l, close=c, volume=v)


def _scenario_bars() -> list[Bar]:
    # mild uptrend with normal volume (EMA/relative-volume warm-up), then
    # a volume spike (3.5x average) on a positive bar, a quiet follow-up
    # bar still above the EMA, then a crash with normal volume
    bars = []
    closes = [100 + i * 0.2 for i in range(20)]
    for i, c in enumerate(closes):
        bars.append(bar(i, c - 0.1, c + 0.2, c - 0.3, c, 1000))
    spike_close = closes[-1] + 2
    bars.append(bar(20, closes[-1], spike_close + 0.3, closes[-1] - 0.1, spike_close, 3500))
    bars.append(bar(21, spike_close, spike_close + 0.5, spike_close - 0.2, spike_close + 0.3, 1000))
    bars.append(bar(22, spike_close + 0.3, spike_close + 0.3, 90, 90, 900))
    return bars


def run_actions(strategy, bars: list[Bar]) -> list[str]:
    cursor = PointInTimeSeries(bars).new_cursor()
    return [strategy(cursor) for _ in cursor]


class TestRelativeVolumeMomentumStrategy(unittest.TestCase):
    def test_buys_on_a_volume_spike_with_a_positive_bar_above_the_ema(self):
        bars = _scenario_bars()
        strategy = RelativeVolumeMomentumStrategy(ema_period=10, volume_lookback=15, volume_multiple=2.0)

        actions = run_actions(strategy, bars)

        self.assertEqual(actions[20], "BUY")  # the 3.5x volume spike bar
        self.assertNotIn("BUY", actions[:20])  # nothing before it qualifies

    def test_sells_once_volume_normalizes_and_price_drops_below_the_ema(self):
        bars = _scenario_bars()
        strategy = RelativeVolumeMomentumStrategy(ema_period=10, volume_lookback=15, volume_multiple=2.0)

        actions = run_actions(strategy, bars)

        self.assertEqual(actions[22], "SELL")  # the crash bar: rv back to normal AND below EMA

    def test_no_buy_without_a_volume_spike(self):
        bars = _scenario_bars()
        # crank the threshold far above what this data ever reaches
        strategy = RelativeVolumeMomentumStrategy(ema_period=10, volume_lookback=15, volume_multiple=100.0)
        actions = run_actions(strategy, bars)
        self.assertNotIn("BUY", actions)

    def test_end_to_end_backtest_matches_hand_calculation(self):
        bars = _scenario_bars()
        strategy = RelativeVolumeMomentumStrategy(ema_period=10, volume_lookback=15, volume_multiple=2.0)

        result = run_reference_backtest(bars, strategy, fee_per_share=0.0)

        # BUY decided after bar 20 -> fills at bar 21's open
        # SELL decided after bar 22 -> no bar 23 exists, signal expires unfilled
        self.assertEqual(len(result.fills), 1)
        self.assertEqual(result.fills[0].side, "BUY")
        self.assertAlmostEqual(result.fills[0].price, bars[21].open)
        self.assertEqual(result.realized_pnl, 0.0)  # position still open, nothing realized


if __name__ == "__main__":
    unittest.main()
