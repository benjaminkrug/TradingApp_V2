import unittest
from datetime import datetime, timedelta, timezone

from app.data.point_in_time import Bar, CursorNotStartedError, PointInTimeSeries


def make_bars(closes: list[float]) -> list[Bar]:
    start = datetime(2026, 1, 2, 9, 30, tzinfo=timezone.utc)
    return [
        Bar(
            timestamp=start + timedelta(minutes=5 * i),
            open=c,
            high=c,
            low=c,
            close=c,
            volume=1000,
        )
        for i, c in enumerate(closes)
    ]


class TestBar(unittest.TestCase):
    def test_rejects_naive_datetime(self):
        with self.assertRaises(ValueError):
            Bar(
                timestamp=datetime(2026, 1, 2, 9, 30),  # no tzinfo
                open=100,
                high=100,
                low=100,
                close=100,
                volume=1000,
            )


class TestPointInTimeSeries(unittest.TestCase):
    def test_rejects_out_of_order_bars(self):
        bars = make_bars([100, 101, 102])
        bars[0], bars[1] = bars[1], bars[0]  # shuffle
        with self.assertRaises(ValueError):
            PointInTimeSeries(bars)

    def test_as_of_excludes_future_bars(self):
        bars = make_bars([100, 101, 102, 103])
        series = PointInTimeSeries(bars)
        visible = series.as_of(bars[1].timestamp)
        self.assertEqual([b.close for b in visible], [100, 101])


class TestSimulationCursor(unittest.TestCase):
    def test_cursor_advances_forward_only(self):
        bars = make_bars([100, 101, 102])
        cursor = PointInTimeSeries(bars).new_cursor()

        first = cursor.advance()
        self.assertEqual(first.close, 100)
        self.assertEqual([b.close for b in cursor.history], [100])

        second = cursor.advance()
        self.assertEqual(second.close, 101)
        self.assertEqual([b.close for b in cursor.history], [100, 101])

    def test_current_before_advance_raises(self):
        bars = make_bars([100, 101, 102])
        cursor = PointInTimeSeries(bars).new_cursor()
        with self.assertRaises(CursorNotStartedError):
            _ = cursor.current

    def test_cursor_cannot_see_beyond_current_bar(self):
        bars = make_bars([100, 101, 102, 103, 104])
        cursor = PointInTimeSeries(bars).new_cursor()
        cursor.advance()
        cursor.advance()  # now at index 1, close=101

        # history must never contain bars beyond the current index,
        # regardless of how many bars actually exist in the underlying series
        self.assertEqual(len(cursor.history), 2)
        self.assertEqual(cursor.history[-1].close, 101)

    def test_cursor_stops_at_end_of_series(self):
        bars = make_bars([100, 101])
        cursor = PointInTimeSeries(bars).new_cursor()
        cursor.advance()
        cursor.advance()
        with self.assertRaises(StopIteration):
            cursor.advance()

    def test_has_next_reflects_remaining_bars(self):
        bars = make_bars([100, 101])
        cursor = PointInTimeSeries(bars).new_cursor()
        self.assertTrue(cursor.has_next)
        cursor.advance()
        self.assertTrue(cursor.has_next)
        cursor.advance()
        self.assertFalse(cursor.has_next)

    def test_supports_for_loop_iteration(self):
        bars = make_bars([100, 101, 102])
        cursor = PointInTimeSeries(bars).new_cursor()
        seen = [bar.close for bar in cursor]
        self.assertEqual(seen, [100, 101, 102])


if __name__ == "__main__":
    unittest.main()
