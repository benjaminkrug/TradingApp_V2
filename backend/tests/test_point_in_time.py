import unittest
from datetime import datetime, timedelta

from app.data.point_in_time import Bar, LookAheadError, PointInTimeSeries


def make_bars(closes: list[float]) -> list[Bar]:
    start = datetime(2026, 1, 2, 9, 30)
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

        with self.assertRaises(LookAheadError):
            # not yet advanced past this point in a *fresh* cursor
            fresh_cursor = PointInTimeSeries(bars).new_cursor()
            _ = fresh_cursor.current

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


if __name__ == "__main__":
    unittest.main()
