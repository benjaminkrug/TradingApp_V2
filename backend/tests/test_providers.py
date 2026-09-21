import unittest
from datetime import date, datetime, timedelta, timezone

import httpx

from app.data.point_in_time import Bar
from app.data.providers.alpaca import DATA_BASE_URL, AlpacaProvider
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
    """PolygonProvider is deliberately not implemented yet (DECISIONS.md
    marks Polygon as optional/later, not the Phase-B priority - see
    PHASE3_NOTES.md). Asserting it fails loudly and informatively (rather
    than e.g. returning an empty list, which would look like 'no data
    available' instead of 'not implemented') is itself the contract worth
    testing. AlpacaProvider has its own real tests below."""

    def test_polygon_provider_raises_not_implemented(self):
        provider = PolygonProvider(api_key="x")
        with self.assertRaises(NotImplementedError):
            provider.get_bars("AAPL", date(2026, 1, 1), date(2026, 1, 31), "1Day")


def make_transport(handler):
    return httpx.MockTransport(handler)


class TestAlpacaProvider(unittest.TestCase):
    """No real network access here on purpose - httpx.MockTransport lets us
    hand-verify exact request construction (URL/headers/params) and response
    parsing without depending on live credentials or Alpaca's availability.
    The one real-network check (does this actually reach Alpaca) was done
    manually via curl and by running this provider with dummy credentials -
    see PHASE3_NOTES.md 'Alpaca-Anbindung'."""

    def test_rejects_empty_credentials(self):
        with self.assertRaises(ValueError):
            AlpacaProvider(api_key="", api_secret="y")
        with self.assertRaises(ValueError):
            AlpacaProvider(api_key="x", api_secret="")

    def test_sends_correct_url_headers_and_params(self):
        captured: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["url"] = str(request.url).split("?")[0]
            captured["headers"] = request.headers
            captured["params"] = dict(request.url.params)
            return httpx.Response(200, json={"bars": [], "next_page_token": None})

        provider = AlpacaProvider(
            api_key="KEY123",
            api_secret="SECRET456",
            client=httpx.Client(transport=make_transport(handler)),
        )
        provider.get_bars("AAPL", date(2026, 1, 1), date(2026, 1, 31), "1Day")

        self.assertEqual(captured["url"], f"{DATA_BASE_URL}/v2/stocks/AAPL/bars")
        self.assertEqual(captured["headers"]["APCA-API-KEY-ID"], "KEY123")
        self.assertEqual(captured["headers"]["APCA-API-SECRET-KEY"], "SECRET456")
        self.assertEqual(captured["params"]["timeframe"], "1Day")
        self.assertEqual(captured["params"]["start"], "2026-01-01")
        self.assertEqual(captured["params"]["end"], "2026-01-31")
        self.assertEqual(captured["params"]["feed"], "iex")
        self.assertEqual(captured["params"]["adjustment"], "raw")

    def test_adjustment_defaults_to_raw_but_is_overridable(self):
        """21.09.2026: 'raw' leaves stock splits in as a fake price
        discontinuity (NVDA's 10:1 split reads as a fake -90% overnight
        move) - any caller doing a multi-year backtest must be able to ask
        for 'split'-adjusted data instead."""
        captured: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["adjustment"] = dict(request.url.params)["adjustment"]
            return httpx.Response(200, json={"bars": [], "next_page_token": None})

        provider = AlpacaProvider(
            api_key="x", api_secret="y", adjustment="split",
            client=httpx.Client(transport=make_transport(handler)),
        )
        provider.get_bars("NVDA", date(2024, 1, 1), date(2024, 12, 31), "1Day")

        self.assertEqual(captured["adjustment"], "split")

    def test_parses_bars_from_a_single_page_response(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "bars": [
                        {"t": "2026-01-02T14:30:00Z", "o": 100.0, "h": 101.5, "l": 99.5, "c": 101.0, "v": 1000},
                        {"t": "2026-01-05T14:30:00Z", "o": 101.0, "h": 103.0, "l": 100.5, "c": 102.5, "v": 1500},
                    ],
                    "next_page_token": None,
                },
            )

        provider = AlpacaProvider(
            api_key="x", api_secret="y", client=httpx.Client(transport=make_transport(handler))
        )
        bars = provider.get_bars("AAPL", date(2026, 1, 1), date(2026, 1, 31), "1Day")

        self.assertEqual(len(bars), 2)
        self.assertEqual(bars[0], Bar(
            symbol="AAPL",
            timestamp=datetime(2026, 1, 2, 14, 30, tzinfo=timezone.utc),
            open=100.0, high=101.5, low=99.5, close=101.0, volume=1000,
        ))
        self.assertEqual(bars[1].close, 102.5)

    def test_follows_pagination_until_next_page_token_is_absent(self):
        pages = [
            {
                "bars": [{"t": "2026-01-02T14:30:00Z", "o": 1, "h": 1, "l": 1, "c": 1, "v": 1}],
                "next_page_token": "page2",
            },
            {
                "bars": [{"t": "2026-01-03T14:30:00Z", "o": 2, "h": 2, "l": 2, "c": 2, "v": 2}],
                "next_page_token": None,
            },
        ]
        seen_page_tokens = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen_page_tokens.append(request.url.params.get("page_token"))
            return httpx.Response(200, json=pages.pop(0))

        provider = AlpacaProvider(
            api_key="x", api_secret="y", client=httpx.Client(transport=make_transport(handler))
        )
        bars = provider.get_bars("AAPL", date(2026, 1, 1), date(2026, 1, 31), "1Day")

        self.assertEqual(len(bars), 2)
        self.assertEqual(seen_page_tokens, [None, "page2"])
        self.assertEqual([b.close for b in bars], [1, 2])

    def test_raises_permission_error_on_401(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(401, text="Unauthorized")

        provider = AlpacaProvider(
            api_key="wrong", api_secret="wrong", client=httpx.Client(transport=make_transport(handler))
        )
        with self.assertRaises(PermissionError):
            provider.get_bars("AAPL", date(2026, 1, 1), date(2026, 1, 31), "1Day")

    def test_raises_for_other_http_errors(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, text="server error")

        provider = AlpacaProvider(
            api_key="x", api_secret="y", client=httpx.Client(transport=make_transport(handler))
        )
        with self.assertRaises(httpx.HTTPStatusError):
            provider.get_bars("AAPL", date(2026, 1, 1), date(2026, 1, 31), "1Day")


if __name__ == "__main__":
    unittest.main()
