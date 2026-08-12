import unittest
from datetime import date, datetime, timedelta, timezone

from app.data.point_in_time import Bar
from app.validation.walk_forward import walk_forward_windows


def make_bars(n_days: int) -> list[Bar]:
    start = datetime(2026, 1, 1, 14, 30, tzinfo=timezone.utc)
    return [
        Bar(symbol="TEST", timestamp=start + timedelta(days=i), open=100, high=101, low=99, close=100, volume=1000)
        for i in range(n_days)
    ]


class TestWalkForwardWindows(unittest.TestCase):
    def test_matches_hand_derived_windows(self):
        bars = make_bars(10)  # 2026-01-01 .. 2026-01-10
        windows = walk_forward_windows(bars, train_days=4, test_days=2, step_days=2)

        self.assertEqual(len(windows), 3)

        expected = [
            (date(2026, 1, 1), date(2026, 1, 4), date(2026, 1, 5), date(2026, 1, 6)),
            (date(2026, 1, 3), date(2026, 1, 6), date(2026, 1, 7), date(2026, 1, 8)),
            (date(2026, 1, 5), date(2026, 1, 8), date(2026, 1, 9), date(2026, 1, 10)),
        ]
        for window, (train_start, train_end, test_start, test_end) in zip(windows, expected):
            train_dates = sorted({b.timestamp.date() for b in window.train})
            test_dates = sorted({b.timestamp.date() for b in window.test})
            self.assertEqual((train_dates[0], train_dates[-1]), (train_start, train_end))
            self.assertEqual((test_dates[0], test_dates[-1]), (test_start, test_end))

    def test_train_and_test_never_overlap(self):
        bars = make_bars(10)
        windows = walk_forward_windows(bars, train_days=4, test_days=2, step_days=2)
        for window in windows:
            train_dates = {b.timestamp.date() for b in window.train}
            test_dates = {b.timestamp.date() for b in window.test}
            self.assertEqual(train_dates & test_dates, set())

    def test_too_little_data_produces_no_windows(self):
        bars = make_bars(3)
        windows = walk_forward_windows(bars, train_days=4, test_days=2, step_days=2)
        self.assertEqual(windows, [])

    def test_rejects_non_positive_parameters(self):
        bars = make_bars(10)
        with self.assertRaises(ValueError):
            walk_forward_windows(bars, train_days=0, test_days=2, step_days=1)


if __name__ == "__main__":
    unittest.main()
