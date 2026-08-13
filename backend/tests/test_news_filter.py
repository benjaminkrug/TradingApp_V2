import unittest
from datetime import date, timedelta, timezone, datetime

from app.data.point_in_time import Bar
from app.signals.news_filter import (
    FakeEarningsCalendarProvider,
    check_earnings_blackout,
    check_relevant_news,
    check_unusual_volatility,
    run_pretrade_gate,
)

SYMBOL = "TEST"


def flat_bars(closes: list[float]) -> list[Bar]:
    start = datetime(2026, 1, 6, 14, 30, tzinfo=timezone.utc)
    return [
        Bar(symbol=SYMBOL, timestamp=start + timedelta(minutes=5 * i), open=c, high=c, low=c, close=c, volume=1000)
        for i, c in enumerate(closes)
    ]


class TestFakeEarningsCalendarProvider(unittest.TestCase):
    def test_returns_next_upcoming_date(self):
        provider = FakeEarningsCalendarProvider({SYMBOL: [date(2026, 1, 10), date(2026, 4, 10)]})
        self.assertEqual(provider.next_earnings_date(SYMBOL, date(2026, 1, 1)), date(2026, 1, 10))
        self.assertEqual(provider.next_earnings_date(SYMBOL, date(2026, 1, 10)), date(2026, 1, 10))  # inclusive
        self.assertEqual(provider.next_earnings_date(SYMBOL, date(2026, 1, 11)), date(2026, 4, 10))

    def test_returns_none_when_no_upcoming_dates(self):
        provider = FakeEarningsCalendarProvider({SYMBOL: [date(2026, 1, 10)]})
        self.assertIsNone(provider.next_earnings_date(SYMBOL, date(2026, 2, 1)))

    def test_returns_none_for_unknown_symbol(self):
        provider = FakeEarningsCalendarProvider({})
        self.assertIsNone(provider.next_earnings_date(SYMBOL, date(2026, 1, 1)))


class TestCheckEarningsBlackout(unittest.TestCase):
    def test_passes_when_no_known_earnings(self):
        provider = FakeEarningsCalendarProvider({})
        result = check_earnings_blackout(SYMBOL, date(2026, 1, 6), provider)
        self.assertEqual(result.status, "PASS")

    def test_passes_when_earnings_beyond_blackout_window(self):
        provider = FakeEarningsCalendarProvider({SYMBOL: [date(2026, 1, 9)]})  # 3 days out
        result = check_earnings_blackout(SYMBOL, date(2026, 1, 6), provider, blackout_days=2)
        self.assertEqual(result.status, "PASS")

    def test_blocks_at_exact_blackout_boundary(self):
        provider = FakeEarningsCalendarProvider({SYMBOL: [date(2026, 1, 8)]})  # exactly 2 days out
        result = check_earnings_blackout(SYMBOL, date(2026, 1, 6), provider, blackout_days=2)
        self.assertEqual(result.status, "BLOCK")

    def test_blocks_on_the_earnings_day_itself(self):
        provider = FakeEarningsCalendarProvider({SYMBOL: [date(2026, 1, 6)]})
        result = check_earnings_blackout(SYMBOL, date(2026, 1, 6), provider, blackout_days=2)
        self.assertEqual(result.status, "BLOCK")


class TestCheckUnusualVolatility(unittest.TestCase):
    def test_not_automated_with_insufficient_history(self):
        result = check_unusual_volatility(flat_bars([100, 101, 102]), short_period=5, baseline_period=20)
        self.assertEqual(result.status, "NOT_AUTOMATED")

    def test_passes_on_stable_volatility(self):
        # 21 flat bars, +1 each transition -> every true range is 1, ratio=1.0
        closes = [100 + i for i in range(21)]
        result = check_unusual_volatility(flat_bars(closes), short_period=5, baseline_period=20)
        self.assertEqual(result.status, "PASS")

    def test_blocks_on_expanded_volatility(self):
        # 15 small transitions (+1 each) then 5 big ones (+20 each): 21 bars, 20 transitions.
        # baseline atr (last 20 TRs) = (15*1 + 5*20)/20 = 5.75
        # short atr (last 5 TRs) = 20.0 -> ratio = 20/5.75 = 3.478x, threshold 2.5x
        closes = [100 + i for i in range(16)]  # 100..115, 15 transitions of 1
        price = closes[-1]
        for _ in range(5):
            price += 20
            closes.append(price)
        result = check_unusual_volatility(
            flat_bars(closes), short_period=5, baseline_period=20, expansion_multiple=2.5
        )
        self.assertEqual(result.status, "BLOCK")
        self.assertIn("3.48", result.detail)


class TestCheckRelevantNews(unittest.TestCase):
    def test_always_not_automated(self):
        self.assertEqual(check_relevant_news().status, "NOT_AUTOMATED")


class TestRunPretradeGate(unittest.TestCase):
    def test_blocked_reflects_any_block(self):
        provider = FakeEarningsCalendarProvider({SYMBOL: [date(2026, 1, 6)]})  # earnings today
        report = run_pretrade_gate(SYMBOL, date(2026, 1, 6), flat_bars([100, 101, 102]), provider)
        self.assertTrue(report.blocked)
        names = {r.name for r in report.results}
        self.assertEqual(names, {"earnings_blackout", "unusual_volatility", "relevant_news"})

    def test_not_blocked_when_nothing_blocks(self):
        provider = FakeEarningsCalendarProvider({})
        report = run_pretrade_gate(SYMBOL, date(2026, 1, 6), flat_bars([100, 101, 102]), provider)
        self.assertFalse(report.blocked)  # NOT_AUTOMATED (volatility, news) never counts as blocked


if __name__ == "__main__":
    unittest.main()
