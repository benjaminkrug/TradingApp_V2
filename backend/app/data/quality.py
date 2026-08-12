"""Data quality checks for ingested bar series.

Returns a structured report rather than silently fixing or dropping
anything — ROADMAP.md Abschnitt 15's checklist treats data quality as
something that must be provably checked, not assumed. Operates on a plain
`list[Bar]`, deliberately *before* it is wrapped in `PointInTimeSeries`
(which would just raise on the first ordering problem it finds rather than
producing a full report of everything wrong with the batch).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Optional

from app.data.point_in_time import Bar


@dataclass(frozen=True)
class QualityIssue:
    kind: str
    detail: str
    bar_index: Optional[int] = None


def check_bars(bars: list[Bar], expected_interval: timedelta) -> list[QualityIssue]:
    issues: list[QualityIssue] = []
    seen_timestamps: set = set()

    for i, bar in enumerate(bars):
        if bar.timestamp in seen_timestamps:
            issues.append(QualityIssue("duplicate_timestamp", str(bar.timestamp), i))
        seen_timestamps.add(bar.timestamp)

        if bar.open <= 0 or bar.close <= 0 or bar.high <= 0 or bar.low <= 0:
            issues.append(
                QualityIssue(
                    "non_positive_price",
                    f"open={bar.open} high={bar.high} low={bar.low} close={bar.close}",
                    i,
                )
            )

        if bar.high < bar.open or bar.high < bar.close or bar.high < bar.low:
            issues.append(QualityIssue("invalid_ohlc", f"high={bar.high} is not the bar's max", i))
        if bar.low > bar.open or bar.low > bar.close or bar.low > bar.high:
            issues.append(QualityIssue("invalid_ohlc", f"low={bar.low} is not the bar's min", i))

        if bar.volume < 0:
            issues.append(QualityIssue("negative_volume", str(bar.volume), i))

        if i > 0:
            gap = bar.timestamp - bars[i - 1].timestamp
            if gap > expected_interval:
                issues.append(QualityIssue("gap", f"{gap} between bar {i - 1} and {i}", i))
            elif gap < expected_interval:
                issues.append(
                    QualityIssue("overlap_or_out_of_order", f"{gap} between bar {i - 1} and {i}", i)
                )

    return issues
