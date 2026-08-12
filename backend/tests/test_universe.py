import unittest
from datetime import date

from app.data.universe import MembershipChange, PointInTimeUniverse


class TestPointInTimeUniverse(unittest.TestCase):
    def setUp(self):
        self.universe = PointInTimeUniverse(
            [
                # delisted/removed before "today" - the classic survivorship trap
                MembershipChange(symbol="DELISTED", added=date(2020, 1, 1), removed=date(2023, 6, 1)),
                # still an active member
                MembershipChange(symbol="SURVIVOR", added=date(2020, 1, 1), removed=None),
                # not yet added at some earlier query date
                MembershipChange(symbol="LATEADD", added=date(2024, 1, 1), removed=None),
            ]
        )

    def test_delisted_symbol_is_included_for_dates_it_was_actually_a_member(self):
        # this is the whole point: querying the PAST must include stocks
        # that have SINCE been removed, or the backtest is survivorship-biased
        members = self.universe.as_of(date(2022, 1, 1))
        self.assertIn("DELISTED", members)
        self.assertIn("SURVIVOR", members)
        self.assertNotIn("LATEADD", members)  # not added yet at this date

    def test_delisted_symbol_is_excluded_after_its_removal_date(self):
        members = self.universe.as_of(date(2024, 1, 1))
        self.assertNotIn("DELISTED", members)
        self.assertIn("SURVIVOR", members)
        self.assertIn("LATEADD", members)

    def test_exactly_on_removal_date_is_excluded(self):
        # removed=2023-06-01 means "no longer a member as of that date"
        members = self.universe.as_of(date(2023, 6, 1))
        self.assertNotIn("DELISTED", members)

    def test_exactly_on_added_date_is_included(self):
        members = self.universe.as_of(date(2020, 1, 1))
        self.assertIn("DELISTED", members)
        self.assertIn("SURVIVOR", members)

    def test_before_any_membership_returns_empty(self):
        members = self.universe.as_of(date(2019, 1, 1))
        self.assertEqual(members, set())


if __name__ == "__main__":
    unittest.main()
