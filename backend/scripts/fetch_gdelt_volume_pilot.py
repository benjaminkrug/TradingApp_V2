"""Fetches GDELT news-volume timelines for the NEWS_VOLUME_PILOT_PROTOCOL.md
pilot universe (same 24 stocks, same 2-year window as the sentiment
pilot) into backend/data_cache/gdelt_volume/.

One JSON file per symbol, resumes without re-fetching already-cached
symbols - same pattern as fetch_gdelt_pilot.py (the sentiment version).
Deliberately a separate script/cache dir rather than reusing
fetch_gdelt_pilot.py, so the two GDELT modes (tone vs. volume) never get
mixed up in a single cache directory.

Usage:
    cd backend
    PYTHONPATH=. python scripts/fetch_gdelt_volume_pilot.py
"""

from __future__ import annotations

import csv
import json
import sys
from datetime import date, timedelta
from pathlib import Path

from app.data.providers.gdelt import fetch_volume_timeline

REPO_ROOT = Path(__file__).resolve().parents[2]
CONSTITUENTS_CSV = REPO_ROOT / "backend" / "data_cache" / "sp500_constituents.csv"
OUT_DIR = REPO_ROOT / "backend" / "data_cache" / "gdelt_volume"

# Must match NEWS_VOLUME_PILOT_PROTOCOL.md and fetch_gdelt_pilot.py exactly
# - same pilot universe as the sentiment pilot, deliberately unchanged.
PILOT_SYMBOLS = [
    "ECHO", "NWS", "APP", "COO", "STZ", "PCG", "TKO", "STT", "CRH", "HPE",
    "BF.B", "FDX", "JKHY", "FERG", "DLTR", "FDS", "CPAY", "TPL", "CIEN",
    "IBKR", "WDAY", "KEYS", "DELL", "NVR",
]

END = date.today()
START = END - timedelta(days=365 * 2)
PACE_SECONDS = 12.0


def load_names() -> dict[str, str]:
    with CONSTITUENTS_CSV.open(encoding="utf-8") as fh:
        return {row["Symbol"]: row["Security"] for row in csv.DictReader(fh)}


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    names = load_names()

    missing = [s for s in PILOT_SYMBOLS if s not in names]
    if missing:
        print(f"WARNING: no name mapping for {missing}, skipping them.")

    for i, symbol in enumerate(PILOT_SYMBOLS, 1):
        out_path = OUT_DIR / f"{symbol}.json"
        if out_path.exists():
            print(f"[{i}/{len(PILOT_SYMBOLS)}] {symbol}: already cached, skipping")
            continue
        company_name = names.get(symbol)
        if not company_name:
            continue

        print(f"[{i}/{len(PILOT_SYMBOLS)}] {symbol} ({company_name}) ...")
        timeline = fetch_volume_timeline(company_name, START, END, pace_seconds=PACE_SECONDS)
        payload = [{"date": t.day.isoformat(), "volume": t.volume} for t in timeline]
        out_path.write_text(json.dumps(payload), encoding="utf-8")
        print(f"    -> {len(timeline)} days written")

    print("\nDone.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
