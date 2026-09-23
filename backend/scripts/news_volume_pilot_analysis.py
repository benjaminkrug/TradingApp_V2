"""NEWS_VOLUME_PILOT_PROTOCOL.md — the comparison test.

For the days each pilot symbol was already in the volume-selected top-20
basket, splits that day's pilot symbols into an above-median and
below-median half by relative GDELT news-article volume ("Volume
Intensity"), and compares their overnight returns with the same
day-block bootstrap used everywhere else in this project.

Deliberately near-identical to news_sentiment_pilot_analysis.py - same
selection basket, same statistics, only the GDELT series differs (volume
instead of tone). relative_tone_by_day() (app/validation/news_sentiment.py)
is reused unchanged for the volume series too - the function is generic
(day's value minus trailing baseline), only its name is tone-specific
from when it was first written.

Needs scripts/fetch_sp500_daily_bars.py and scripts/fetch_gdelt_volume_pilot.py
to have both run first.

Usage:
    cd backend
    PYTHONPATH=. python scripts/news_volume_pilot_analysis.py
"""

from __future__ import annotations

import json
import statistics
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

from app.data.point_in_time import Bar
from app.validation.criteria import REFERENCE_FRICTION_BP, cluster_bootstrap, net_mean_bp
from app.validation.news_sentiment import relative_tone_by_day
from app.validation.overnight_selection import DailyBars, select_top_by_relative_volume
from app.validation.results_store import RunRecord, record_run

REPO_ROOT = Path(__file__).resolve().parents[2]
PRICE_CACHE = REPO_ROOT / "backend" / "data_cache" / "daily_bars_split_adjusted"
VOLUME_CACHE = REPO_ROOT / "backend" / "data_cache" / "gdelt_volume"

# Must match NEWS_VOLUME_PILOT_PROTOCOL.md and fetch_gdelt_volume_pilot.py exactly.
PILOT_SYMBOLS = [
    "ECHO", "NWS", "APP", "COO", "STZ", "PCG", "TKO", "STT", "CRH", "HPE",
    "BF.B", "FDX", "JKHY", "FERG", "DLTR", "FDS", "CPAY", "TPL", "CIEN",
    "IBKR", "WDAY", "KEYS", "DELL", "NVR",
]
VOLUME_LOOKBACK = 20
NEWS_VOLUME_LOOKBACK = 20  # calendar days, per the protocol
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


def load_news_volume(symbol: str) -> dict[date, float]:
    path = VOLUME_CACHE / f"{symbol}.json"
    if not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {date.fromisoformat(r["date"]): r["volume"] for r in raw}


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
    if not VOLUME_CACHE.exists() or not any(VOLUME_CACHE.glob("*.json")):
        print(f"No GDELT volume data cached in {VOLUME_CACHE} - run scripts/fetch_gdelt_volume_pilot.py first.")
        return 1

    all_price_bars = load_price_bars()
    missing_price = [s for s in PILOT_SYMBOLS if s not in all_price_bars]
    if missing_price:
        print(f"WARNING: no price data cached for {missing_price}")

    selected_by_day = select_top_by_relative_volume(all_price_bars, lookback=VOLUME_LOOKBACK, top_n=20, min_price=MIN_PRICE)

    relative_news_volume_by_symbol = {}
    for sym in PILOT_SYMBOLS:
        vol = load_news_volume(sym)
        if not vol:
            print(f"WARNING: no GDELT volume data cached for {sym}")
            continue
        relative_news_volume_by_symbol[sym] = relative_tone_by_day(vol, lookback=NEWS_VOLUME_LOOKBACK)

    print(f"{len(relative_news_volume_by_symbol)}/{len(PILOT_SYMBOLS)} pilot symbols have GDELT volume data.")

    pilot_symbol_set = set(relative_news_volume_by_symbol)
    upper_trades: list[tuple[float, date]] = []  # (overnight_bp, day)
    lower_trades: list[tuple[float, date]] = []

    days_considered = 0
    for day, selected in selected_by_day.items():
        if day < PILOT_START:
            continue
        candidates = []
        for sym in selected:
            if sym not in pilot_symbol_set:
                continue
            rel_vol = relative_news_volume_by_symbol[sym].get(day)
            if rel_vol is None:
                continue
            bp = overnight_bp(all_price_bars[sym], day)
            if bp is None:
                continue
            candidates.append((sym, rel_vol, bp))
        if len(candidates) < 2:
            continue
        days_considered += 1
        candidates.sort(key=lambda c: c[1])  # ascending relative news volume
        mid = len(candidates) // 2
        for sym, rel_vol, bp in candidates[:mid]:
            lower_trades.append((bp, day))
        for sym, rel_vol, bp in candidates[mid:]:
            upper_trades.append((bp, day))

    print(f"{days_considered} days had >=2 pilot symbols selected with news-volume data.")
    print(f"upper (more news volume) half: {len(upper_trades)} observations")
    print(f"lower (less news volume) half: {len(lower_trades)} observations")

    if len(upper_trades) < 10 or len(lower_trades) < 10:
        print("Too few observations for a meaningful comparison - pilot universe/window too small.")
        return 0

    def summarize(label: str, trades: list[tuple[float, date]]):
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

    upper_stats = summarize("Hohes Nachrichten-Volumen (obere Haelfte)", upper_trades)
    lower_stats = summarize("Niedriges Nachrichten-Volumen (untere Haelfte)", lower_trades)

    record_run(RunRecord(
        strategy="NewsVolumePilot",
        strategy_params={"pilot_symbols": PILOT_SYMBOLS, "news_volume_lookback_days": NEWS_VOLUME_LOOKBACK, "volume_lookback": VOLUME_LOOKBACK},
        symbols=PILOT_SYMBOLS,
        data_start=str(PILOT_START),
        data_end=str(date.today()),
        timeframe="1Day",
        data_source="gdelt+alpaca/iex",
        engine="news_volume_pilot",
        metrics={
            "days_considered": days_considered,
            "upper_n": len(upper_trades), "upper_gross_bp": upper_stats[0], "upper_net_bp": upper_stats[1],
            "upper_bootstrap_t": upper_stats[2].t_stat, "upper_p": upper_stats[2].p_value,
            "lower_n": len(lower_trades), "lower_gross_bp": lower_stats[0], "lower_net_bp": lower_stats[1],
            "lower_bootstrap_t": lower_stats[2].t_stat, "lower_p": lower_stats[2].p_value,
        },
        verdict=None,
        note="NEWS_VOLUME_PILOT_PROTOCOL.md first run, 24-symbol pilot, 2-year window",
    ))

    return 0


if __name__ == "__main__":
    sys.exit(main())
