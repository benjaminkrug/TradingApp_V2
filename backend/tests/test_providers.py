import unittest
from datetime import date, datetime, timedelta, timezone

from app.data.point_in_time import Bar
from app.data.providers.alpaca import AlpacaProvider
from app.data.providers.fake import FakeProvider
from app.data.providers.polygon import PolygonProvider


def make_bars(n: int, symbol: str) -> list[Bar]:
    start = datetime(2026, 1, 2, 9, 30, tzinfo=timezone.utc)
    return [
        Bar(
            symbol=symbol,
            timestamp=start + timedelta(days=i),
            open=100,
            high=101,
            low=99,
            close=100,
            volume=1000,
        )
        for i in range(n)
    ]


class TestFakeProvider(unittest.TestCase):
    def test_filters_by_symbol_and_date_range(self):
        provider = FakeProvider(
            {
                "AAA": make_bars(5, "AAA"),
                "BBB": make_bars(5, "BBB"),
            }
        )

        bars = provider.get_bars("AAA", start=date(2026, 1, 2), end=date(2026, 1, 3), timeframe="1Day")

        self.assertEqual(len(bars), 2)
        self.assertTrue(all(b.symbol == "AAA" for b in bars))

    def test_unknown_symbol_returns_empty(self):
        provider = FakeProvider({"AAA": make_bars(3, "AAA")})
        bars = provider.get_bars("ZZZ", start=date(2026, 1, 1), end=date(2026, 1, 31), timeframe="1Day")
        self.assertEqual(bars, [])


class TestUnverifiedProviderStubs(unittest.TestCase):
    """These providers are deliberately not implemented yet (no network
    access to verify against in this environment, no API keys configured -
    see PHASE3_NOTES.md). Asserting they fail loudly and informatively
    (rather than e.g. returning an empty list, which would look like
    'no data available' instead of 'not implemented') is itself the
    contract worth testing."""

    def test_alpaca_provider_raises_not_implemented(self):
        provider = AlpacaProvider(api_key="x", api_secret="y")
        with self.assertRaises(NotImplementedError):
            provider.get_bars("AAPL", date(2026, 1, 1), date(2026, 1, 31), "1Day")

    def test_polygon_provider_raises_not_implemented(self):
        provider = PolygonProvider(api_key="x")
        with self.assertRaises(NotImplementedError):
            provider.get_bars("AAPL", date(2026, 1, 1), date(2026, 1, 31), "1Day")


if __name__ == "__main__":
    unittest.main()
