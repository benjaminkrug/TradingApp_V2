"""Alpaca market data adapter — real implementation against the Alpaca
Market Data API v2 (`GET /v2/stocks/{symbol}/bars` on `data.alpaca.markets`).

Verification status (see PHASE3_NOTES.md "Alpaca-Anbindung" section for the
full story): unit-tested against a mocked HTTP transport
(`tests/test_providers.py`), confirmed to reach Alpaca's real server via
`curl`, and verified end-to-end with real bar data twice - once by the user
running `backend/scripts/verify_alpaca_connection.py` themselves, once by
Claude running `backend/scripts/real_data_gate_run.py` directly (11,459 real
5-Min AAPL bars). Note for future sessions: there is no sandbox restriction
that prevents reading real `.env` values once the file is actually saved to
disk - an earlier note here claiming otherwise was wrong (see PHASE3_NOTES.md
for the correction). Treat real credentials with the same care you would
outside this tool, since nothing technical stops a real API call here.

Notes on the API contract this relies on:
- Market data lives on `data.alpaca.markets`, which is a *different* host
  than the trading/account API (`ALPACA_BASE_URL`, default
  `paper-api.alpaca.markets`, from `.env`) — the market-data host is the
  same for paper and live keys, there is no separate "paper" data endpoint.
- `timeframe` is passed straight through as Alpaca's own string format
  (e.g. "1Min", "5Min", "1Hour", "1Day") — this matches what
  `MarketDataProvider.get_bars` already documents as "provider-specific",
  so no translation layer is needed.
- Free/basic Alpaca accounts only get the IEX feed (not the consolidated
  SIP tape) — `feed="iex"` is the default here for that reason, and is
  configurable for accounts with a paid data plan.
- Results are paginated via `next_page_token`; this loops until Alpaca
  stops returning one.
"""

from __future__ import annotations

from datetime import date, datetime

import httpx

from app.data.point_in_time import Bar
from app.data.providers.base import MarketDataProvider

DATA_BASE_URL = "https://data.alpaca.markets"
_BARS_PATH = "/v2/stocks/{symbol}/bars"
_MAX_LIMIT_PER_PAGE = 10_000


class AlpacaProvider(MarketDataProvider):
    def __init__(
        self,
        api_key: str,
        api_secret: str,
        feed: str = "iex",
        timeout: float = 10.0,
        client: httpx.Client | None = None,
    ):
        if not api_key or not api_secret:
            raise ValueError("AlpacaProvider requires a non-empty api_key and api_secret")
        self._api_key = api_key
        self._api_secret = api_secret
        self._feed = feed
        self._timeout = timeout
        self._client = client

    def get_bars(self, symbol: str, start: date, end: date, timeframe: str) -> list[Bar]:
        url = f"{DATA_BASE_URL}{_BARS_PATH.format(symbol=symbol)}"
        headers = {
            "APCA-API-KEY-ID": self._api_key,
            "APCA-API-SECRET-KEY": self._api_secret,
        }
        params = {
            "timeframe": timeframe,
            "start": start.isoformat(),
            "end": end.isoformat(),
            "limit": _MAX_LIMIT_PER_PAGE,
            "adjustment": "raw",
            "feed": self._feed,
        }

        bars: list[Bar] = []
        page_token: str | None = None
        client = self._client or httpx.Client(timeout=self._timeout)
        owns_client = self._client is None
        try:
            while True:
                request_params = dict(params)
                if page_token:
                    request_params["page_token"] = page_token
                response = client.get(url, headers=headers, params=request_params)
                if response.status_code == 401:
                    raise PermissionError(
                        "Alpaca rejected the API key/secret (401 Unauthorized). Check "
                        "ALPACA_API_KEY/ALPACA_SECRET_KEY in .env - these must be the "
                        "paper-trading keys from the Alpaca dashboard, not live-trading keys."
                    )
                response.raise_for_status()
                payload = response.json()
                for raw_bar in payload.get("bars") or []:
                    bars.append(_parse_bar(symbol, raw_bar))
                page_token = payload.get("next_page_token")
                if not page_token:
                    break
        finally:
            if owns_client:
                client.close()

        bars.sort(key=lambda b: b.timestamp)
        return bars


def _parse_bar(symbol: str, raw: dict) -> Bar:
    return Bar(
        symbol=symbol,
        timestamp=datetime.fromisoformat(raw["t"].replace("Z", "+00:00")),
        open=raw["o"],
        high=raw["h"],
        low=raw["l"],
        close=raw["c"],
        volume=raw["v"],
    )
