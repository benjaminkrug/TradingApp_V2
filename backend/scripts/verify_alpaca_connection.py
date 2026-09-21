"""One-time, real-network check that AlpacaProvider.get_bars() actually
works against your Alpaca paper-trading keys.

Why this has to be run by you, not by Claude in a chat session: Claude
Code's tool sandbox structurally cannot read real secret values out of
`.env` (a sourced ALPACA_API_KEY came back empty even though the file has
real content) - see PHASE3_NOTES.md "Alpaca-Anbindung". This script must be
run in your own terminal, outside Claude Code's tools, so it can actually
see your real keys.

Usage:

    cd backend
    PYTHONPATH=. python scripts/verify_alpaca_connection.py

Reads ALPACA_API_KEY / ALPACA_SECRET_KEY from `.env` in the repo root (or
from the real environment, if already exported - env vars win). Prints
whether the request succeeded and how many bars came back. Never prints
the key values themselves.
"""

from __future__ import annotations

import os
import sys
from datetime import date, timedelta
from pathlib import Path

from app.data.providers.alpaca import AlpacaProvider


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if key and key not in os.environ:
            os.environ[key] = value


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    _load_dotenv(repo_root / ".env")

    api_key = os.environ.get("ALPACA_API_KEY", "")
    api_secret = os.environ.get("ALPACA_SECRET_KEY", "")
    if not api_key or not api_secret:
        print("ALPACA_API_KEY / ALPACA_SECRET_KEY not set (checked .env and the real "
              "environment). Fill them into .env in the repo root, then re-run this script.")
        return 1

    print(f"Using key ID ending in ...{api_key[-4:]} (never printing the full key/secret).")

    provider = AlpacaProvider(api_key=api_key, api_secret=api_secret)
    end = date.today()
    start = end - timedelta(days=10)
    symbol = "AAPL"

    print(f"Requesting {symbol} daily bars from {start} to {end} ...")
    try:
        bars = provider.get_bars(symbol, start=start, end=end, timeframe="1Day")
    except PermissionError as exc:
        print(f"FAILED - Alpaca rejected the credentials: {exc}")
        return 1
    except Exception as exc:  # noqa: BLE001 - this script's whole job is to report the outcome
        print(f"FAILED - unexpected error: {exc!r}")
        return 1

    if not bars:
        print(
            "Request succeeded but returned zero bars. That can be normal for the last "
            "10 days on a fresh paper account with the free IEX feed if today's session "
            "hasn't fully settled yet - try widening the date range before assuming it's broken."
        )
        return 0

    print(f"SUCCESS - got {len(bars)} bars.")
    print(f"  first: {bars[0]}")
    print(f"  last:  {bars[-1]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
