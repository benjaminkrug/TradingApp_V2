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

    def test_uses_ny_local_date_not_naive_utc_date(self):
        # 2026-01-03 02:00 UTC is 2026-01-02 21:00 EST in New York (winter,
        # UTC-5) - under a naive UTC .date() this bar would be misfiled as
        # a third distinct calendar day instead of merging into Jan 2nd.
        bars = [
            Bar(symbol="TEST", timestamp=datetime(2026, 1, 1, 15, 0, tzinfo=timezone.utc), open=1, high=1, low=1, close=1, volume=1000),
            Bar(symbol="TEST", timestamp=datetime(2026, 1, 2, 15, 0, tzinfo=timezone.utc), open=1, high=1, low=1, close=1, volume=1000),
            Bar(symbol="TEST", timestamp=datetime(2026, 1, 3, 2, 0, tzinfo=timezone.utc), open=1, high=1, low=1, close=1, volume=1000),
        ]
        # 1 train day + 1 test day, requesting exactly the 2 true NY dates
        windows = walk_forward_windows(bars, train_days=1, test_days=1, step_days=1)
        self.assertEqual(len(windows), 1)
        self.assertEqual(len(windows[0].train), 1)
        # the Jan-1 bar trains; both later bars (true NY date Jan 2) test together
        self.assertEqual(len(windows[0].test), 2)


if __name__ == "__main__":
    unittest.main()
