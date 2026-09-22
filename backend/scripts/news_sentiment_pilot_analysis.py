"""NEWS_SENTIMENT_PILOT_PROTOCOL.md — the comparison test.

For the days each pilot symbol was already in the volume-selected top-20
basket (from scripts/overnight_selection_analysis.py's own selection
logic, recomputed here from cached price data), splits that day's pilot
symbols into an above-median and below-median half by relative GDELT
tone, and compares their overnight returns with the same day-block
bootstrap used everywhere else in this project.

Needs scripts/fetch_sp500_daily_bars.py and scripts/fetch_gdelt_pilot.py
to have both run first.

Usage:
    cd backend
    PYTHONPATH=. python scripts/news_sentiment_pilot_analysis.py
"""

from __future__ import annotations

import json
import statistics
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

from app.data.point_in_time import Bar
from app.validation.criteria import REFERENCE_FRICTION_BP, cluster_bootstrap, net_mean_bp
from app.validation.evaluate import trade_return_bp
from app.validation.news_sentiment import relative_tone_by_day
from app.validation.overnight_selection import DailyBars, select_top_by_relative_volume
from app.validation.results_store import RunRecord, record_run

REPO_ROOT = Path(__file__).resolve().parents[2]
PRICE_CACHE = REPO_ROOT / "backend" / "data_cache" / "daily_bars_split_adjusted"
TONE_CACHE = REPO_ROOT / "backend" / "data_cache" / "gdelt_tone"

# Must match NEWS_SENTIMENT_PILOT_PROTOCOL.md and fetch_gdelt_pilot.py exactly.
PILOT_SYMBOLS = [
    "ECHO", "NWS", "APP", "COO", "STZ", "PCG", "TKO", "STT", "CRH", "HPE",
    "BF.B", "FDX", "JKHY", "FERG", "DLTR", "FDS", "CPAY", "TPL", "CIEN",
    "IBKR", "WDAY", "KEYS", "DELL", "NVR",
]
VOLUME_LOOKBACK = 20
TONE_LOOKBACK = 20  # calendar days, per the protocol
MIN_PRICE = 5.0
PILOT_START = date.today() - timedelta(days=365 * 2)


def load_price_bars() -> dict[str, DailyBars]:
    out = {}
    for path in sorted(PRICE_CACHE.glob("*.json")):
        sym = path.stem
        raw = json.loads(path.read_text(encoding="utf-8"))
        if len(raw) < 25:
            continue
        bars = [
            Bar(symbol=r["symbol"], timestamp=datetime.fromisoformat(r["t"]), open=r["o"], high=r["h"],
                low=r["l"], close=r["c"], volume=r["v"])
            for r in raw
        ]
        out[sym] = DailyBars(sym, bars)
    return out


def load_tone(symbol: str) -> dict[date, float]:
    path = TONE_CACHE / f"{symbol}.json"
    if not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {date.fromisoformat(r["date"]): r["tone"] for r in raw}


def overnight_bp(daily: DailyBars, day: date) -> float | None:
    bars = daily.bars
    for i, bar in enumerate(bars):
        if bar.timestamp.date() == day:
            if i + 1 >= len(bars) or bar.volume <= 0 or bars[i + 1].volume <= 0:
                return None
            entry, exit_ = bar, bars[i + 1]
            if entry.close <= 0:
                return None
            bp = (exit_.open - entry.close) / entry.close * 10_000
            return bp if abs(bp) <= 3_000 else None  # same magnitude cap as overnight_selection.py
    return None


def main() -> int:
    if not TONE_CACHE.exists() or not any(TONE_CACHE.glob("*.json")):
        print(f"No GDELT data cached in {TONE_CACHE} - run scripts/fetch_gdelt_pilot.py first.")
        return 1

    all_price_bars = load_price_bars()
    missing_price = [s for s in PILOT_SYMBOLS if s not in all_price_bars]
    if missing_price:
        print(f"WARNING: no price data cached for {missing_price}")

    selected_by_day = select_top_by_relative_volume(all_price_bars, lookback=VOLUME_LOOKBACK, top_n=20, min_price=MIN_PRICE)

    relative_tone_by_symbol = {}
    for sym in PILOT_SYMBOLS:
        tone = load_tone(sym)
        if not tone:
            print(f"WARNING: no GDELT data cached for {sym}")
            continue
        relative_tone_by_symbol[sym] = relative_tone_by_day(tone, lookback=TONE_LOOKBACK)

    print(f"{len(relative_tone_by_symbol)}/{len(PILOT_SYMBOLS)} pilot symbols have GDELT data.")

    # For each day in the pilot window where the volume-selection actually
    # ran, restrict to the pilot symbols that were selected that day AND
    # have a relative-tone value that day, then split by the day's median.
    pilot_symbol_set = set(relative_tone_by_symbol)
    upper_trades: list[tuple[float, date]] = []  # (overnight_bp, day) - kept minimal, not full Trade objects
    lower_trades: list[tuple[float, date]] = []

    days_considered = 0
    for day, selected in selected_by_day.items():
        if day < PILOT_START:
            continue
        candidates = []
        for sym in selected:
            if sym not in pilot_symbol_set:
                continue
            rel_tone = relative_tone_by_symbol[sym].get(day)
            if rel_tone is None:
                continue
            bp = overnight_bp(all_price_bars[sym], day)
            if bp is None:
                continue
            candidates.append((sym, rel_tone, bp))
        if len(candidates) < 2:
            continue  # need at least 2 to split into two non-empty halves
        days_considered += 1
        candidates.sort(key=lambda c: c[1])  # ascending relative tone
        mid = len(candidates) // 2
        for sym, rel_tone, bp in candidates[:mid]:
            lower_trades.append((bp, day))
        for sym, rel_tone, bp in candidates[mid:]:
            upper_trades.append((bp, day))

    print(f"{days_considered} days had >=2 pilot symbols selected with tone data.")
    print(f"upper (more positive tone) half: {len(upper_trades)} observations")
    print(f"lower (more negative tone) half: {len(lower_trades)} observations")

    if len(upper_trades) < 10 or len(lower_trades) < 10:
        print("Too few observations for a meaningful comparison - pilot universe/window too small.")
        return 0

    def summarize(label: str, trades: list[tuple[float, date]]):
        # Build minimal Trade-like objects for the existing, verified bootstrap
        from app.validation.metrics import Trade
        fake_trades = [
            Trade(symbol="PILOT", entry_time=datetime.combine(day, datetime.min.time()),
                  exit_time=datetime.combine(day, datetime.min.time()) + timedelta(hours=1),
                  entry_price=100.0, exit_price=100.0 + bp / 100, quantity=1.0, pnl=bp / 100)
            for bp, day in trades
        ]
        gross = statistics.fmean(bp for bp, _ in trades)
        net = net_mean_bp(fake_trades, REFERENCE_FRICTION_BP)
        boot = cluster_bootstrap(fake_trades, friction_bp=REFERENCE_FRICTION_BP, samples=10_000, seed=12345)
        print(f"\n{label}: n={len(trades)}  gross={gross:+.2f}bp  net@2bp={net:+.2f}bp  "
              f"bootstrap_t={boot.t_stat:+.2f}  p={boot.p_value:.4f}  over {boot.day_count} days")
        return gross, net, boot

    upper_stats = summarize("Positivere Stimmung (obere Haelfte)", upper_trades)
    lower_stats = summarize("Negativere Stimmung (untere Haelfte)", lower_trades)

    record_run(RunRecord(
        strategy="NewsSentimentPilot",
        strategy_params={"pilot_symbols": PILOT_SYMBOLS, "tone_lookback_days": TONE_LOOKBACK, "volume_lookback": VOLUME_LOOKBACK},
        symbols=PILOT_SYMBOLS,
        data_start=str(PILOT_START),
        data_end=str(date.today()),
        timeframe="1Day",
        data_source="gdelt+alpaca/iex",
        engine="news_sentiment_pilot",
        metrics={
            "days_considered": days_considered,
            "upper_n": len(upper_trades), "upper_gross_bp": upper_stats[0], "upper_net_bp": upper_stats[1],
            "upper_bootstrap_t": upper_stats[2].t_stat, "upper_p": upper_stats[2].p_value,
            "lower_n": len(lower_trades), "lower_gross_bp": lower_stats[0], "lower_net_bp": lower_stats[1],
            "lower_bootstrap_t": lower_stats[2].t_stat, "lower_p": lower_stats[2].p_value,
        },
        verdict=None,
        note="NEWS_SENTIMENT_PILOT_PROTOCOL.md first run, 24-symbol pilot, 2-year window",
    ))

    return 0


if __name__ == "__main__":
    sys.exit(main())
