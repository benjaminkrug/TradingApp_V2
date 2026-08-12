import unittest
from datetime import datetime, timedelta, timezone

from app.data.point_in_time import Bar
from app.features.indicators import (
    atr,
    current_session_bars,
    ema_series,
    opening_range,
    session_vwap,
    sma,
)


def bar(i: int, o: float, h: float, l: float, c: float, v: float, start=None) -> Bar:
    start = start or datetime(2026, 1, 2, 9, 30, tzinfo=timezone.utc)
    return Bar(symbol="TEST", timestamp=start + timedelta(minutes=5 * i), open=o, high=h, low=l, close=c, volume=v)


class TestSma(unittest.TestCase):
    def test_matches_hand_calculation(self):
        self.assertAlmostEqual(sma([1, 2, 3, 4, 5], 3), 4.0)

    def test_none_when_insufficient_data(self):
        self.assertIsNone(sma([1, 2], 3))


class TestEmaSeries(unittest.TestCase):
    def test_matches_hand_calculation(self):
        # SMA(3) seed = (1+2+3)/3 = 2.0; k = 2/4 = 0.5
        # ema[3] = 4*0.5 + 2.0*0.5 = 3.0; ema[4] = 5*0.5 + 3.0*0.5 = 4.0
        result = ema_series([1, 2, 3, 4, 5], 3)
        self.assertEqual(result, [None, None, 2.0, 3.0, 4.0])

    def test_all_none_when_insufficient_data(self):
        self.assertEqual(ema_series([1, 2], 3), [None, None])


class TestAtr(unittest.TestCase):
    def setUp(self):
        self.bars = [
            bar(0, 9, 10, 8, 9, 100),
            bar(1, 9.5, 11, 9, 10.5, 100),  # TR = max(2, |11-9|=2, |9-9|=0) = 2
            bar(2, 10, 10, 7, 8, 100),  # TR = max(3, |10-10.5|=0.5, |7-10.5|=3.5) = 3.5
            bar(3, 8, 9, 8, 8.5, 100),  # TR = max(1, |9-8|=1, |8-8|=0) = 1
        ]

    def test_matches_hand_calculation_period_3(self):
        # true ranges [2, 3.5, 1] -> avg = 6.5/3
        self.assertAlmostEqual(atr(self.bars, 3), 6.5 / 3)

    def test_matches_hand_calculation_period_2(self):
        # last 2 true ranges [3.5, 1] -> avg = 2.25
        self.assertAlmostEqual(atr(self.bars, 2), 2.25)

    def test_none_when_insufficient_data(self):
        self.assertIsNone(atr(self.bars[:2], 3))


class TestSessionVwap(unittest.TestCase):
    def test_matches_hand_calculation(self):
        bars = [bar(0, 9, 10, 8, 9, 100), bar(1, 9.5, 11, 9, 10, 200)]
        # typical prices: (10+8+9)/3=9.0, (11+9+10)/3=10.0
        # vwap = (9*100 + 10*200) / 300 = 2900/300
        self.assertAlmostEqual(session_vwap(bars), 2900 / 300)

    def test_resets_across_session_boundary(self):
        day1 = datetime(2026, 1, 2, 15, 0, tzinfo=timezone.utc)  # ~10am NY
        day2 = datetime(2026, 1, 3, 15, 0, tzinfo=timezone.utc)  # next NY session
        bars = [
            bar(0, 100, 100, 100, 100, 1000, start=day1),
            bar(0, 10, 10, 10, 10, 1000, start=day2),
        ]
        # if yesterday's bar leaked in, this would be nowhere near 10
        self.assertAlmostEqual(session_vwap(bars), 10.0)

    def test_empty_history_returns_none(self):
        self.assertIsNone(session_vwap([]))


class TestCurrentSessionBars(unittest.TestCase):
    def test_excludes_prior_session(self):
        day1 = datetime(2026, 1, 2, 15, 0, tzinfo=timezone.utc)
        day2 = datetime(2026, 1, 3, 15, 0, tzinfo=timezone.utc)
        bars = [bar(0, 1, 1, 1, 1, 1, start=day1), bar(0, 2, 2, 2, 2, 2, start=day2)]
        result = current_session_bars(bars)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].close, 2)


class TestOpeningRange(unittest.TestCase):
    def test_matches_hand_calculation(self):
        bars = [bar(0, 9, 10, 8, 9, 100), bar(1, 9.5, 11, 9, 10, 100)]
        self.assertEqual(opening_range(bars, 2), (8, 11))

    def test_none_when_session_has_fewer_bars_than_requested(self):
        bars = [bar(0, 9, 10, 8, 9, 100), bar(1, 9.5, 11, 9, 10, 100)]
        self.assertIsNone(opening_range(bars, 3))


if __name__ == "__main__":
    unittest.main()
