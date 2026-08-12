"""Static example universe — DECISIONS.md #1: "Statische Liste ~30
liquide US-Large-Caps für MVP, kein Live-Scanner in v1".

This is an illustrative, common-knowledge list of well-known, highly
liquid large-cap US equities. It has NOT been individually reviewed or
confirmed by the user — treat it as a placeholder to edit, not an
authoritative or recommended selection, and not investment advice. A
real dynamic scanner (liquidity/relative-volume/momentum filters over
the full market) is explicitly out of scope for the MVP per DECISIONS.md
and would need real market data (still stubbed, see PHASE3_NOTES.md).
"""

from __future__ import annotations

STATIC_UNIVERSE: list[str] = [
    "AAPL", "MSFT", "AMZN", "GOOGL", "META", "NVDA", "TSLA", "JPM", "V", "UNH",
    "HD", "PG", "MA", "XOM", "JNJ", "WMT", "CVX", "MRK", "ABBV", "KO",
    "PEP", "BAC", "COST", "DIS", "ADBE", "CRM", "NFLX", "AMD", "INTC", "CSCO",
]  # fmt: skip


def scan() -> list[str]:
    """Returns the static MVP universe. No filtering logic yet — see
    module docstring."""
    return list(STATIC_UNIVERSE)
