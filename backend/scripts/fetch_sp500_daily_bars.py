"""Fetches and caches daily bars for the S&P 500 (backend/data_cache/sp500_constituents.csv)
from 2021-01-01 to today, for OVERNIGHT_SELECTION_PROTOCOL.md.

One JSON file per symbol under backend/data_cache/daily_bars/, so re-runs
skip symbols already cached rather than re-hitting the API. Failures
(delisted-since-list-was-built, renamed tickers, etc.) are logged and
skipped, not fatal - a few missing names out of 503 does not change the
answer to the statistical question this protocol asks.

Usage:
    cd backend
    PYTHONPATH=. python scripts/fetch_sp500_daily_bars.py
"""

from __future__ import annotations

import csv
import json
import os
import sys
from datetime import date
from pathlib import Path

from app.data.providers.alpaca import AlpacaProvider

START = date(2021, 1, 1)
END = date.today()
TIMEFRAME = "1Day"

REPO_ROOT = Path(__file__).resolve().parents[2]
CONSTITUENTS_CSV = REPO_ROOT / "backend" / "data_cache" / "sp500_constituents.csv"
OUT_DIR = REPO_ROOT / "backend" / "data_cache" / "daily_bars"


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        if key.strip() and key.strip() not in os.environ:
            os.environ[key.strip()] = value.strip()


def load_symbols() -> list[str]:
    with CONSTITUENTS_CSV.open(encoding="utf-8") as fh:
        return [row["Symbol"] for row in csv.DictReader(fh)]


def main() -> int:
    _load_dotenv(REPO_ROOT / ".env")
    api_key = os.environ.get("ALPACA_API_KEY", "")
    api_secret = os.environ.get("ALPACA_SECRET_KEY", "")
    if not api_key or not api_secret:
        print("ALPACA_API_KEY / ALPACA_SECRET_KEY not set.")
        return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    symbols = load_symbols()
    provider = AlpacaProvider(api_key=api_key, api_secret=api_secret, timeout=30.0)

    fetched, cached, failed = 0, 0, []
    for i, symbol in enumerate(symbols, 1):
        out_path = OUT_DIR / f"{symbol}.json"
        if out_path.exists():
            cached += 1
            continue
        try:
            bars = provider.get_bars(symbol, start=START, end=END, timeframe=TIMEFRAME)
        except Exception as exc:  # noqa: BLE001 - log and continue, one bad symbol shouldn't kill 500 others
            print(f"[{i}/{len(symbols)}] {symbol}: FAILED - {exc!r}")
            failed.append(symbol)
            continue
        payload = [
            {"symbol": b.symbol, "t": b.timestamp.isoformat(), "o": b.open, "h": b.high, "l": b.low, "c": b.close, "v": b.volume}
            for b in bars
        ]
        out_path.write_text(json.dumps(payload), encoding="utf-8")
        fetched += 1
        if i % 25 == 0:
            print(f"[{i}/{len(symbols)}] ... {fetched} fetched, {cached} already cached, {len(failed)} failed")

    print(f"\nDone. fetched={fetched} cached_already={cached} failed={len(failed)}")
    if failed:
        print("failed symbols:", failed)
    return 0


if __name__ == "__main__":
    sys.exit(main())
