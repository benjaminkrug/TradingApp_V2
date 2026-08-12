"""Polygon.io market data adapter — documented stub, NOT verified.

Same situation as alpaca.py: api.polygon.io is also blocked in this
sandbox (403, host_not_allowed), and there is no API key configured. See
that module's docstring for why this raises NotImplementedError instead
of shipping an unverified HTTP client, and PHASE3_NOTES.md for status.
"""

from __future__ import annotations

from datetime import date

from app.data.point_in_time import Bar
from app.data.providers.base import MarketDataProvider

_NOT_VERIFIED = (
    "PolygonProvider is a documented stub, not a verified implementation — "
    "see PHASE3_NOTES.md. Needs a real API key, network access to "
    "api.polygon.io (blocked in the dev sandbox), and a first verification "
    "run before this can be trusted to return real data."
)


class PolygonProvider(MarketDataProvider):
    def __init__(self, api_key: str):
        self._api_key = api_key

    def get_bars(self, symbol: str, start: date, end: date, timeframe: str) -> list[Bar]:
        raise NotImplementedError(_NOT_VERIFIED)
