"""Alpaca market data adapter — documented stub, NOT verified.

This sandbox has no network access to api.alpaca.markets (403,
x-deny-reason: host_not_allowed — the same organizational network policy
that blocks PyPI, see PHASE2_NOTES.md), and no API key is configured
(DECISIONS.md marks Alpaca as a provisional, not yet individually
confirmed choice). Writing a plausible-looking HTTP client from memory
here — exact endpoint paths, parameter names, pagination, rate-limit
handling — would create false confidence rather than a verified
integration; those details are easy to get subtly wrong with no way to
check them in this environment. This class documents the intended shape
and deliberately raises NotImplementedError until it has actually been
exercised against the real API, either locally or via a CI job holding a
real credential (as a secret, never committed).
"""

from __future__ import annotations

from datetime import date

from app.data.point_in_time import Bar
from app.data.providers.base import MarketDataProvider

_NOT_VERIFIED = (
    "AlpacaProvider is a documented stub, not a verified implementation — "
    "see PHASE3_NOTES.md. Needs a real API key/secret, network access to "
    "api.alpaca.markets (blocked in the dev sandbox), and a first "
    "verification run before this can be trusted to return real data."
)


class AlpacaProvider(MarketDataProvider):
    def __init__(self, api_key: str, api_secret: str):
        self._api_key = api_key
        self._api_secret = api_secret

    def get_bars(self, symbol: str, start: date, end: date, timeframe: str) -> list[Bar]:
        raise NotImplementedError(_NOT_VERIFIED)
