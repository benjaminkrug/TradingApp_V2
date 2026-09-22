"""Fetches GDELT tone timelines for the NEWS_SENTIMENT_PILOT_PROTOCOL.md
pilot universe (24 stocks, last 2 years) into backend/data_cache/gdelt_tone/.

One JSON file per symbol, so an interrupted run resumes without
re-fetching already-cached symbols - same pattern as
fetch_sp500_daily_bars.py. Expect this to take on the order of an hour:
~8 chunks/symbol x 24 symbols, each chunk paced at 12s plus occasional
429 backoff (see app/data/providers/gdelt.py).

Usage:
    cd backend
    PYTHONPATH=. python scripts/fetch_gdelt_pilot.py
"""

from __future__ import annotations

import csv
import json
import sys
from datetime import date, timedelta
from pathlib import Path

from app.data.providers.gdelt import fetch_tone_timeline

REPO_ROOT = Path(__file__).resolve().parents[2]
CONSTITUENTS_CSV = REPO_ROOT / "backend" / "data_cache" / "sp500_constituents.csv"
OUT_DIR = REPO_ROOT / "backend" / "data_cache" / "gdelt_tone"

# NEWS_SENTIMENT_PILOT_PROTOCOL.md's fixed pilot universe - the 24 most
# frequently volume-selected symbols, "P" excluded (bad name mapping in
# the source CSV, see the protocol's data-quality section).
PILOT_SYMBOLS = [
    "ECHO", "NWS", "APP", "COO", "STZ", "PCG", "TKO", "STT", "CRH", "HPE",
    "BF.B", "FDX", "JKHY", "FERG", "DLTR", "FDS", "CPAY", "TPL", "CIEN",
    "IBKR", "WDAY", "KEYS", "DELL", "NVR",
]

END = date.today()
START = END - timedelta(days=365 * 2)  # protocol's 2-year pilot window
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
        timeline = fetch_tone_timeline(company_name, START, END, pace_seconds=PACE_SECONDS)
        payload = [{"date": t.day.isoformat(), "tone": t.tone} for t in timeline]
        out_path.write_text(json.dumps(payload), encoding="utf-8")
        print(f"    -> {len(timeline)} days written")

    print("\nDone.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
