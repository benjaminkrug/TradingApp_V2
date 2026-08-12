"""Point-in-time index/universe membership — the survivorship-bias fix.

ROADMAP.md Abschnitt 7: backtesting the *current* S&P 500 (or any static,
today's-membership list) against several years of history silently drops
every stock that has since been delisted, gone bankrupt, or been removed
from the index, biasing results upward. Querying "who was actually in the
universe on date X" needs membership as it stood on date X.

This module only provides the mechanism. It ships with no real historical
membership data — sourcing accurate historical S&P 500 (or other index)
constituent history is typically a paid dataset and is an open acquisition
task, not something to fake with a plausible-looking fixture. See
PHASE3_NOTES.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional


@dataclass(frozen=True)
class MembershipChange:
    symbol: str
    added: date
    removed: Optional[date] = None  # None = still a member as of the data's cutoff


class PointInTimeUniverse:
    def __init__(self, changes: list[MembershipChange]):
        self._changes = list(changes)

    def as_of(self, d: date) -> set[str]:
        """Symbols that were actual members of the universe on `d` —
        including symbols since removed, as long as they were members on
        `d` itself."""
        return {
            c.symbol
            for c in self._changes
            if c.added <= d and (c.removed is None or d < c.removed)
        }
