"""GDELT DOC 2.0 API client — NEWS_SENTIMENT_PILOT_PROTOCOL.md.

Free, no API key, but with two real constraints confirmed against the
live API on 22.09.2026 (not just from documentation):

1. A single query spans at most ~3 months (STARTDATETIME/ENDDATETIME).
   Longer ranges are fetched here as sequential chunks.
2. The published "one request per 5 seconds" limit understates reality -
   one test needed ~25s between attempts, another succeeded immediately.
   `_get_with_backoff` retries on HTTP 429 with an increasing wait
   instead of assuming a fixed interval is safe.

Queries use an exact-phrase company name (e.g. `"Apple Inc"`), which
reduces but does not eliminate false matches from ambiguous names - see
the protocol's data-quality section.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

_BASE_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
_MAX_QUERY_SPAN_DAYS = 90  # GDELT's per-request limit is ~3 months
_USER_AGENT = "TradingApp_V2-research-pilot/1.0"


@dataclass(frozen=True)
class ToneDay:
    day: date
    tone: float


def _chunk_date_range(start: date, end: date, max_span_days: int = _MAX_QUERY_SPAN_DAYS) -> list[tuple[date, date]]:
    chunks: list[tuple[date, date]] = []
    chunk_start = start
    while chunk_start <= end:
        chunk_end = min(end, chunk_start + timedelta(days=max_span_days - 1))
        chunks.append((chunk_start, chunk_end))
        chunk_start = chunk_end + timedelta(days=1)
    return chunks


def _get_with_backoff(
    url: str, max_attempts: int = 6, base_wait: float = 10.0, sleep_fn=time.sleep
) -> Optional[str]:
    """Retries on HTTP 429 with linearly increasing waits (10s, 20s, 30s,
    ...). Returns None (not an exception) after exhausting attempts, so a
    single stubborn chunk cannot abort an entire multi-symbol fetch run -
    callers treat a None chunk as "no data for this window", the same as
    GDELT returning an empty result.
    """
    for attempt in range(1, max_attempts + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            if exc.code != 429 or attempt == max_attempts:
                if exc.code == 429:
                    return None
                raise
            sleep_fn(base_wait * attempt)
    return None


def fetch_tone_timeline(
    company_name: str, start: date, end: date, sleep_fn=time.sleep, pace_seconds: float = 12.0
) -> list[ToneDay]:
    """Daily average tone for `company_name` (used as an exact-phrase
    query) across [start, end], stitched from as many ~3-month chunks as
    needed. `pace_seconds` is a courtesy delay between chunk requests on
    top of the retry backoff in `_get_with_backoff`.
    """
    results: list[ToneDay] = []
    chunks = _chunk_date_range(start, end)
    for i, (chunk_start, chunk_end) in enumerate(chunks):
        params = {
            "query": f'"{company_name}"',
            "mode": "timelinetone",
            "startdatetime": chunk_start.strftime("%Y%m%d000000"),
            "enddatetime": chunk_end.strftime("%Y%m%d000000"),
            "format": "json",
        }
        url = f"{_BASE_URL}?{urllib.parse.urlencode(params)}"
        body = _get_with_backoff(url, sleep_fn=sleep_fn)
        if body:
            results.extend(_parse_timeline(body))
        if i < len(chunks) - 1:
            sleep_fn(pace_seconds)
    return results


def _parse_timeline(body: str) -> list[ToneDay]:
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return []
    timeline = payload.get("timeline") or []
    if not timeline:
        return []
    series = timeline[0].get("data") or []
    out = []
    for point in series:
        try:
            day = date.fromisoformat(point["date"][:10])
            out.append(ToneDay(day=day, tone=float(point["value"])))
        except (KeyError, ValueError):
            continue
    return out
