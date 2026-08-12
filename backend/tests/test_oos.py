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


if __name__ == "__main__":
    unittest.main()
