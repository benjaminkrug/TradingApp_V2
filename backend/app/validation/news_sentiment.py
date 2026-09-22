"""Relative news tone — NEWS_SENTIMENT_PILOT_PROTOCOL.md.

Mirrors `overnight_selection.relative_volume_by_day` deliberately: same
"never look at today or later, drop missing days from the trailing
baseline" shape, applied to GDELT tone instead of trading volume. Kept as
a separate function (not a generic "relative_by_day" reused by both)
because the two have a real difference worth keeping visible: volume is
never missing for a real trading day, while a tone series can have gaps
(GDELT simply has no coverage that day) - here, a gap breaks the
consecutive trailing window rather than being silently skipped, since
"20 real trading days" and "20 calendar days with any GDELT coverage" are
not obviously the same lookback in spirit, and conflating them silently
would be exactly the kind of choice this project's conventions say to
make explicitly, not by accident.
"""

from __future__ import annotations

import statistics
from datetime import date, timedelta
from typing import Optional


def relative_tone_by_day(tone_by_date: dict[date, float], lookback: int) -> dict[date, Optional[float]]:
    """Day N's tone relative to the mean tone of the `lookback` calendar
    days strictly before it (not `lookback` prior *entries* - a gap in
    GDELT's coverage shortens the window's real data rather than reaching
    further back to compensate, so the baseline never uses information
    from further in the past than `lookback` days ago).

    `None` where there is no tone value for day N itself, or no tone data
    at all in the `lookback`-day window before it.
    """
    result: dict[date, Optional[float]] = {}
    for day, tone in tone_by_date.items():
        window_start = day - timedelta(days=lookback)
        prior_values = [t for d, t in tone_by_date.items() if window_start <= d < day]
        if not prior_values:
            result[day] = None
            continue
        baseline = statistics.fmean(prior_values)
        result[day] = tone - baseline
    return result
