import unittest
from datetime import date, timezone

from app.data.calendar import is_trading_day, nyse_holidays, session_bounds


class TestNyseHolidays2026(unittest.TestCase):
    """Cross-checked by construction (see calendar.py's deterministic
    nth-weekday/last-weekday helpers) and independently sanity-checked
    against the weekday each rule should always land on."""

    def setUp(self):
        self.holidays = nyse_holidays(2026)

    def test_new_years_day(self):
        self.assertIn(date(2026, 1, 1), self.holidays)

    def test_mlk_day_is_third_monday_of_january(self):
        d = date(2026, 1, 19)
        self.assertEqual(d.weekday(), 0)  # Monday
        self.assertIn(d, self.holidays)

    def test_good_friday_is_always_a_friday(self):
        good_friday = date(2026, 4, 3)
        self.assertEqual(good_friday.weekday(), 4)  # Friday
        self.assertIn(good_friday, self.holidays)

    def test_juneteenth_included_from_2022_onward(self):
        self.assertIn(date(2026, 6, 19), nyse_holidays(2026))
        self.assertNotIn(date(2021, 6, 19), nyse_holidays(2021))

    def test_july_4th_on_saturday_observed_preceding_friday(self):
        # July 4, 2026 falls on a Saturday
        self.assertEqual(date(2026, 7, 4).weekday(), 5)
        self.assertNotIn(date(2026, 7, 4), self.holidays)
        self.assertIn(date(2026, 7, 3), self.holidays)

    def test_christmas(self):
        self.assertIn(date(2026, 12, 25), self.holidays)


class TestIsTradingDay(unittest.TestCase):
    def test_weekend_is_not_a_trading_day(self):
        self.assertFalse(is_trading_day(date(2026, 8, 15)))  # Saturday

    def test_ordinary_weekday_is_a_trading_day(self):
        self.assertTrue(is_trading_day(date(2026, 8, 12)))  # Wednesday

    def test_holiday_is_not_a_trading_day(self):
        self.assertFalse(is_trading_day(date(2026, 12, 25)))


class TestSessionBounds(unittest.TestCase):
    def test_raises_on_non_trading_day(self):
        with self.assertRaises(ValueError):
            session_bounds(date(2026, 12, 25))

    def test_open_close_are_utc_and_6_5_hours_apart(self):
        open_, close_ = session_bounds(date(2026, 8, 12))
        self.assertEqual(open_.tzinfo, timezone.utc)
        self.assertEqual(close_.tzinfo, timezone.utc)
        self.assertEqual((close_ - open_).total_seconds() / 3600, 6.5)

    def test_dst_is_handled_summer_vs_winter_open_differs_by_one_hour_utc(self):
        summer_open, _ = session_bounds(date(2026, 7, 15))  # EDT, UTC-4
        winter_open, _ = session_bounds(date(2026, 1, 15))  # EST, UTC-5
        self.assertEqual(summer_open.hour, 13)  # 9:30 EDT -> 13:30 UTC
        self.assertEqual(winter_open.hour, 14)  # 9:30 EST -> 14:30 UTC


if __name__ == "__main__":
    unittest.main()
