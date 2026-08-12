import unittest
from datetime import date, datetime, timedelta, timezone

from app.data.point_in_time import Bar
from app.validation.oos import OosLockedError, OosSplit


def make_bars(n_days: int, symbol: str = "TEST") -> list[Bar]:
    start = datetime(2026, 1, 1, 14, 30, tzinfo=timezone.utc)
    return [
        Bar(symbol=symbol, timestamp=start + timedelta(days=i), open=100, high=101, low=99, close=100, volume=1000)
        for i in range(n_days)
    ]


class TestOosSplit(unittest.TestCase):
    def test_splits_by_cutoff_date(self):
        bars = make_bars(10)  # 2026-01-01 .. 2026-01-10
        split = OosSplit(bars, cutoff=date(2026, 1, 6))

        self.assertEqual(len(split.in_sample), 5)  # Jan 1-5
        self.assertTrue(all(b.timestamp.date() < date(2026, 1, 6) for b in split.in_sample))

    def test_out_of_sample_raises_before_unlock(self):
        bars = make_bars(10)
        split = OosSplit(bars, cutoff=date(2026, 1, 6))
        with self.assertRaises(OosLockedError):
            _ = split.out_of_sample

    def test_out_of_sample_accessible_after_unlock(self):
        bars = make_bars(10)
        split = OosSplit(bars, cutoff=date(2026, 1, 6))
        self.assertFalse(split.is_unlocked)

        split.unlock()

        self.assertTrue(split.is_unlocked)
        oos = split.out_of_sample
        self.assertEqual(len(oos), 5)  # Jan 6-10
        self.assertTrue(all(b.timestamp.date() >= date(2026, 1, 6) for b in oos))

    def test_in_sample_never_locked(self):
        bars = make_bars(10)
        split = OosSplit(bars, cutoff=date(2026, 1, 6))
        # accessible without unlock() - only out_of_sample is guarded
        self.assertEqual(len(split.in_sample), 5)

    def test_uses_ny_local_date_not_naive_utc_date(self):
        # 2026-01-06 02:00 UTC is 2026-01-05 21:00 EST in New York (winter,
        # UTC-5) - under a naive UTC .date() this bar would wrongly land in
        # out_of_sample instead of in_sample for a Jan-6 cutoff.
        bars = [
            Bar(symbol="TEST", timestamp=datetime(2026, 1, 5, 15, 0, tzinfo=timezone.utc), open=1, high=1, low=1, close=1, volume=1000),
            Bar(symbol="TEST", timestamp=datetime(2026, 1, 6, 2, 0, tzinfo=timezone.utc), open=1, high=1, low=1, close=1, volume=1000),
            Bar(symbol="TEST", timestamp=datetime(2026, 1, 6, 15, 0, tzinfo=timezone.utc), open=1, high=1, low=1, close=1, volume=1000),
        ]
        split = OosSplit(bars, cutoff=date(2026, 1, 6))
        self.assertEqual(len(split.in_sample), 2)  # both the Jan-5 15:00 UTC and Jan-6 02:00 UTC bars


if __name__ == "__main__":
    unittest.main()
