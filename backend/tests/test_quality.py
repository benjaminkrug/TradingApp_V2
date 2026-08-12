import unittest
from datetime import datetime, timedelta, timezone

from app.data.point_in_time import Bar
from app.data.quality import check_bars


def clean_bars(n: int, symbol: str = "TEST") -> list[Bar]:
    start = datetime(2026, 1, 2, 9, 30, tzinfo=timezone.utc)
    return [
        Bar(
            symbol=symbol,
            timestamp=start + timedelta(minutes=5 * i),
            open=100 + i,
            high=100.5 + i,
            low=99.5 + i,
            close=100 + i,
            volume=1000,
        )
        for i in range(n)
    ]


class TestCheckBars(unittest.TestCase):
    def test_clean_series_has_no_issues(self):
        bars = clean_bars(5)
        issues = check_bars(bars, expected_interval=timedelta(minutes=5))
        self.assertEqual(issues, [])

    def test_duplicate_timestamp_is_flagged(self):
        bars = clean_bars(3)
        dup = Bar(
            symbol="TEST",
            timestamp=bars[1].timestamp,
            open=1,
            high=1,
            low=1,
            close=1,
            volume=1,
        )
        bars_with_dup = bars[:2] + [dup] + bars[2:]
        issues = check_bars(bars_with_dup, expected_interval=timedelta(minutes=5))
        kinds = {i.kind for i in issues}
        self.assertIn("duplicate_timestamp", kinds)

    def test_gap_is_flagged(self):
        bars = clean_bars(3)
        # blow a 20-minute hole where a 5-minute bar was expected
        bars[2] = Bar(
            symbol="TEST",
            timestamp=bars[1].timestamp + timedelta(minutes=20),
            open=bars[2].open,
            high=bars[2].high,
            low=bars[2].low,
            close=bars[2].close,
            volume=bars[2].volume,
        )
        issues = check_bars(bars, expected_interval=timedelta(minutes=5))
        kinds = {i.kind for i in issues}
        self.assertIn("gap", kinds)

    def test_invalid_high_is_flagged(self):
        bars = clean_bars(1)
        bad = Bar(symbol="TEST", timestamp=bars[0].timestamp, open=100, high=99, low=98, close=99.5, volume=1000)
        issues = check_bars([bad], expected_interval=timedelta(minutes=5))
        kinds = {i.kind for i in issues}
        self.assertIn("invalid_ohlc", kinds)

    def test_negative_volume_is_flagged(self):
        bars = clean_bars(1)
        bad = Bar(symbol="TEST", timestamp=bars[0].timestamp, open=100, high=101, low=99, close=100, volume=-5)
        issues = check_bars([bad], expected_interval=timedelta(minutes=5))
        kinds = {i.kind for i in issues}
        self.assertIn("negative_volume", kinds)

    def test_non_positive_price_is_flagged(self):
        bars = clean_bars(1)
        bad = Bar(symbol="TEST", timestamp=bars[0].timestamp, open=0, high=1, low=0, close=0.5, volume=1000)
        issues = check_bars([bad], expected_interval=timedelta(minutes=5))
        kinds = {i.kind for i in issues}
        self.assertIn("non_positive_price", kinds)

    def test_issue_carries_bar_index(self):
        bars = clean_bars(3)
        bars[2] = Bar(symbol="TEST", timestamp=bars[2].timestamp, open=100, high=99, low=98, close=99, volume=1000)
        issues = check_bars(bars, expected_interval=timedelta(minutes=5))
        self.assertTrue(any(i.bar_index == 2 for i in issues))


if __name__ == "__main__":
    unittest.main()
