import unittest
from datetime import datetime, timedelta, timezone

from app.data.point_in_time import Bar
from app.features.indicators import atr, atr_on_horizon, resample_tail

# 09:30 New York in UTC (EST = UTC-5 in January).
NY_OPEN_UTC = 14


def bar(day: int, minute_offset: int, o: float, h: float, l: float, c: float, v: float) -> Bar:
    start = datetime(2026, 1, day, NY_OPEN_UTC, 30, tzinfo=timezone.utc)
    return Bar(
        symbol="TEST",
        timestamp=start + timedelta(minutes=minute_offset),
        open=o,
        high=h,
        low=l,
        close=c,
        volume=v,
    )


class TestResampleTail(unittest.TestCase):
    def three_days(self):
        return [
            bar(2, 0, 10, 12, 9, 11, 100),
            bar(2, 5, 11, 13, 10, 12, 200),
            bar(5, 0, 20, 22, 19, 21, 100),
            bar(5, 5, 21, 23, 20, 22, 200),
            bar(6, 0, 30, 32, 29, 31, 100),
            bar(6, 5, 31, 33, 30, 32, 200),
        ]

    def test_daily_aggregation_matches_hand_calculation(self):
        result = resample_tail(self.three_days(), "day", 2)

        # The newest (still-forming) day is dropped, leaving Jan 2 and Jan 5.
        self.assertEqual(len(result), 2)

        day1, day2 = result
        # Jan 2: open from the first bar (10), close from the last (12),
        # high = max(12, 13) = 13, low = min(9, 10) = 9, volume = 300
        self.assertEqual((day1.open, day1.high, day1.low, day1.close, day1.volume), (10, 13, 9, 12, 300))
        # Jan 5: open 20, close 22, high = max(22, 23) = 23, low = min(19, 20) = 19
        self.assertEqual((day2.open, day2.high, day2.low, day2.close, day2.volume), (20, 23, 19, 22, 300))

    def test_drops_only_the_newest_bucket(self):
        """Sizing a stop off a half-finished day would understate the range,
        which means a tighter stop and therefore a *larger* position - the
        error would point in the dangerous direction."""
        closes = [b.close for b in resample_tail(self.three_days(), "day", 3)]
        self.assertNotIn(32, closes)  # Jan 6's close must not appear

    def test_hourly_buckets_split_within_a_session(self):
        bars = [bar(2, offset, 10, 11, 9, 10, 100) for offset in (0, 30, 60, 90, 120)]
        # offsets 0/30 -> 14:30,15:00 (hours 14,15 UTC -> 09,10 NY)... bucket
        # boundaries follow NY local hours, so expect one bucket per hour.
        result = resample_tail(bars, "hour", 5)
        self.assertGreaterEqual(len(result), 1)
        self.assertLessEqual(len(result), 3)

    def test_bar_horizon_is_a_plain_tail(self):
        bars = self.three_days()
        self.assertEqual(resample_tail(bars, "bar", 2), bars[-2:])

    def test_empty_and_zero_count(self):
        self.assertEqual(resample_tail([], "day", 3), [])
        self.assertEqual(resample_tail(self.three_days(), "day", 0), [])

    def test_unknown_horizon_raises(self):
        with self.assertRaises(ValueError):
            resample_tail(self.three_days(), "week", 2)


class TestAtrOnHorizon(unittest.TestCase):
    def test_bar_horizon_is_identical_to_plain_atr(self):
        bars = [bar(2, i * 5, 10 + i, 11 + i, 9 + i, 10 + i, 100) for i in range(20)]
        self.assertEqual(atr_on_horizon(bars, 14, "bar"), atr(bars, 14))

    def test_daily_horizon_measures_a_much_larger_range(self):
        """The whole point of K2a: an ATR over intraday bars measures minutes
        of volatility, a daily ATR measures whole days. On a series that
        trends within each session, the daily figure must be far larger -
        that difference is what drove positions to 83-136% of the account."""
        bars = []
        for day in (2, 5, 6, 7, 8, 9, 12, 13, 14, 15, 16, 19, 20, 21, 22, 23):
            base = day * 2.0
            for step in range(12):
                price = base + step  # a steady intraday climb, small per bar
                bars.append(bar(day, step * 5, price, price + 0.5, price - 0.5, price + 0.4, 100))

        per_bar = atr_on_horizon(bars, 5, "bar")
        per_day = atr_on_horizon(bars, 5, "day")

        self.assertIsNotNone(per_bar)
        self.assertIsNotNone(per_day)
        self.assertGreater(per_day, per_bar * 5)

    def test_none_when_not_enough_history(self):
        self.assertIsNone(atr_on_horizon([bar(2, 0, 10, 11, 9, 10, 100)], 14, "day"))


if __name__ == "__main__":
    unittest.main()
