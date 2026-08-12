import unittest
from datetime import datetime, timedelta, timezone

from app.data.point_in_time import Bar
from app.features.indicators import relative_volume


def bar(i: int, volume: float, start=None) -> Bar:
    start = start or datetime(2026, 1, 2, 14, 30, tzinfo=timezone.utc)
    return Bar(symbol="TEST", timestamp=start + timedelta(minutes=5 * i), open=100, high=101, low=99, close=100, volume=volume)


class TestRelativeVolume(unittest.TestCase):
    def test_matches_hand_calculation(self):
        bars = [bar(i, 100) for i in range(5)] + [bar(5, 300)]
        self.assertAlmostEqual(relative_volume(bars, lookback=5), 3.0)

    def test_none_when_insufficient_history(self):
        bars = [bar(i, 100) for i in range(3)]
        self.assertIsNone(relative_volume(bars, lookback=5))

    def test_none_when_prior_average_is_zero(self):
        bars = [bar(i, 0) for i in range(5)] + [bar(5, 100)]
        self.assertIsNone(relative_volume(bars, lookback=5))

    def test_excludes_the_current_bar_from_its_own_average(self):
        # if the current bar were included in the average, a single huge
        # spike would understate its own relative volume
        bars = [bar(i, 100) for i in range(5)] + [bar(5, 1000)]
        rv = relative_volume(bars, lookback=5)
        self.assertAlmostEqual(rv, 10.0)  # not ~1.96 (1000 / ((5*100+1000)/6))


if __name__ == "__main__":
    unittest.main()
