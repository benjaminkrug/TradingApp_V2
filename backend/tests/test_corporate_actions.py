import unittest
from datetime import date, datetime, timedelta, timezone

from app.data.corporate_actions import Split, adjust_for_splits
from app.data.point_in_time import Bar


def make_bars(closes: list[float], symbol: str = "TEST") -> list[Bar]:
    start = datetime(2026, 1, 2, 9, 30, tzinfo=timezone.utc)
    return [
        Bar(
            symbol=symbol,
            timestamp=start + timedelta(days=i),
            open=c,
            high=c,
            low=c,
            close=c,
            volume=1000,
        )
        for i, c in enumerate(closes)
    ]


class TestAdjustForSplits(unittest.TestCase):
    def test_no_splits_returns_bars_unchanged(self):
        bars = make_bars([100, 101, 102])
        adjusted = adjust_for_splits(bars, [])
        self.assertEqual(adjusted, bars)

    def test_2_for_1_split_halves_pre_split_prices_and_doubles_volume(self):
        # bars on days 0,1,2,3; split effective on day 2
        bars = make_bars([100, 100, 200, 202])  # day2 close jumps to 200 post-split
        split = Split(symbol="TEST", effective_date=date(2026, 1, 4), ratio=2.0)

        adjusted = adjust_for_splits(bars, [split])

        # days 0,1 (before effective_date) are back-adjusted: /2 price, *2 volume
        self.assertAlmostEqual(adjusted[0].close, 50.0)
        self.assertAlmostEqual(adjusted[0].volume, 2000.0)
        self.assertAlmostEqual(adjusted[1].close, 50.0)
        # days 2,3 (on/after effective_date) are untouched
        self.assertAlmostEqual(adjusted[2].close, 200.0)
        self.assertAlmostEqual(adjusted[2].volume, 1000.0)
        self.assertAlmostEqual(adjusted[3].close, 202.0)

    def test_multiple_splits_compound(self):
        # two 2-for-1 splits -> bars before both are divided by 4
        bars = make_bars([100, 100, 100])
        splits = [
            Split(symbol="TEST", effective_date=date(2026, 1, 3), ratio=2.0),
            Split(symbol="TEST", effective_date=date(2026, 1, 4), ratio=2.0),
        ]

        adjusted = adjust_for_splits(bars, splits)

        # day 0: before both splits -> /4
        self.assertAlmostEqual(adjusted[0].close, 25.0)
        # day 1 (2026-01-03): before the second split only -> /2
        self.assertAlmostEqual(adjusted[1].close, 50.0)
        # day 2 (2026-01-04): on/after both -> unchanged
        self.assertAlmostEqual(adjusted[2].close, 100.0)

    def test_splits_for_other_symbols_are_ignored(self):
        bars = make_bars([100, 100], symbol="AAA")
        split = Split(symbol="BBB", effective_date=date(2026, 1, 3), ratio=2.0)

        adjusted = adjust_for_splits(bars, [split])

        self.assertEqual(adjusted, bars)

    def test_rejects_mixed_symbol_input(self):
        bars = make_bars([100], symbol="AAA") + make_bars([50], symbol="BBB")
        with self.assertRaises(ValueError):
            adjust_for_splits(bars, [])


if __name__ == "__main__":
    unittest.main()
