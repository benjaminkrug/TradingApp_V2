import unittest
from datetime import date, timedelta

from app.validation.news_sentiment import relative_tone_by_day

DAY0 = date(2026, 1, 1)


def days(*offsets_and_values):
    return {DAY0 + timedelta(days=o): v for o, v in offsets_and_values}


class TestRelativeToneByDay(unittest.TestCase):
    def test_matches_hand_calculation(self):
        # baseline days 0-4 = mean(1,2,3,4,5) = 3.0; day 5's tone 9.0 -> relative = 9.0 - 3.0 = 6.0
        data = days((0, 1.0), (1, 2.0), (2, 3.0), (3, 4.0), (4, 5.0), (5, 9.0))
        rel = relative_tone_by_day(data, lookback=5)
        self.assertAlmostEqual(rel[DAY0 + timedelta(days=5)], 6.0)

    def test_no_prior_data_is_none(self):
        data = days((0, 1.0))
        rel = relative_tone_by_day(data, lookback=5)
        self.assertIsNone(rel[DAY0])

    def test_gap_in_coverage_shortens_the_window_rather_than_reaching_further_back(self):
        """Day 10 with lookback=10 should only see days 0-9 (calendar), and
        only day 0 actually has data - day -5 (further back) must NOT be
        pulled in to compensate for the gap."""
        data = days((-5, 100.0), (0, 2.0), (10, 8.0))
        rel = relative_tone_by_day(data, lookback=10)
        # window for day 10 is [day0, day10) calendar-wise -> only day0's 2.0 counts
        self.assertAlmostEqual(rel[DAY0 + timedelta(days=10)], 8.0 - 2.0)

    def test_negative_relative_tone_when_below_baseline(self):
        data = days((0, 5.0), (1, 5.0), (2, -1.0))
        rel = relative_tone_by_day(data, lookback=2)
        self.assertAlmostEqual(rel[DAY0 + timedelta(days=2)], -1.0 - 5.0)

    def test_empty_input(self):
        self.assertEqual(relative_tone_by_day({}, lookback=5), {})


if __name__ == "__main__":
    unittest.main()
