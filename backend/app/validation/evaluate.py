"""Evaluating a strategy under the rules it would actually be traded with.

VALIDATION_PROTOCOL.md K2: the gate has to grade the real execution logic
(`app/paper/` - ATR stop, target, risk-based position sizing, optional
session-end flattening), not `reference_engine.py`. The reference engine
stays in the picture as a cross-check, which is the job it was built for:
a minimal, hand-verifiable correctness oracle. If the two disagree in ways
nobody can explain, that is a bug signal and no result from that run should
be trusted.

Per-trade results are reported in **basis points of notional**, not dollars.
Under risk-based sizing the position size varies from trade to trade, so raw
dollar P&L is not comparable across trades and its standard deviation (and
therefore any t-statistic built on it) would be dominated by position size
rather than by the strategy. Basis points are also the unit transaction
costs are quoted in, which is what K3 needs.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from datetime import date
from typing import Optional

from app.backtest.reference_engine import run_reference_backtest
from app.data.calendar import NY_TZ
from app.data.point_in_time import Bar
from app.paper.engine import StrategyFactory, run_paper_trading_on_bars
from app.validation.metrics import Trade, trades_from_fills


def _session_date(when) -> date:
    return when.astimezone(NY_TZ).date()


def trade_return_bp(trade: Trade) -> float:
    """Net P&L as basis points of the position's entry notional."""
    notional = trade.entry_price * trade.quantity
    if notional <= 0:
        return 0.0
    return trade.pnl / notional * 10_000


@dataclass(frozen=True)
class TradeStats:
    trade_count: int
    mean_bp: float
    stdev_bp: float
    t_stat_naive: float
    win_rate: float
    total_pnl: float
    overnight_share: float
    max_holding_days: float
    median_holding_hours: float

    @property
    def is_empty(self) -> bool:
        return self.trade_count == 0


def compute_trade_stats(trades: list[Trade]) -> TradeStats:
    """`t_stat_naive` is deliberately named: it treats every trade as an
    independent observation, which they are not - trades cluster in time and
    correlate across symbols on the same day, so this overstates
    significance. VALIDATION_PROTOCOL.md K4 requires a day-block bootstrap
    instead. This value is a cheap screening number, not a verdict.
    """
    if not trades:
        return TradeStats(0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

    returns_bp = [trade_return_bp(t) for t in trades]
    mean_bp = statistics.fmean(returns_bp)
    stdev_bp = statistics.stdev(returns_bp) if len(returns_bp) > 1 else 0.0
    t_stat = mean_bp / (stdev_bp / math.sqrt(len(returns_bp))) if stdev_bp > 0 else 0.0

    holding_days = [(t.exit_time - t.entry_time).total_seconds() / 86_400 for t in trades]
    overnight = sum(1 for t in trades if _session_date(t.exit_time) != _session_date(t.entry_time))

    return TradeStats(
        trade_count=len(trades),
        mean_bp=mean_bp,
        stdev_bp=stdev_bp,
        t_stat_naive=t_stat,
        win_rate=sum(1 for t in trades if t.pnl > 0) / len(trades),
        total_pnl=sum(t.pnl for t in trades),
        overnight_share=overnight / len(trades),
        max_holding_days=max(holding_days),
        median_holding_hours=statistics.median(holding_days) * 24,
    )


@dataclass(frozen=True)
class Evaluation:
    """One strategy on one bar set, under both engines."""

    paper_trades: list[Trade]
    paper_stats: TradeStats
    reference_stats: TradeStats
    buy_and_hold_bp: dict[str, float]
    session_count: int


def _trades_by_symbol(fills: list) -> list[Trade]:
    """`portfolio.fills` interleaves symbols; `trades_from_fills` expects one
    symbol at a time (it raises rather than silently mispairing, see its own
    docstring), so group first."""
    by_symbol: dict[str, list] = {}
    for fill in fills:
        by_symbol.setdefault(fill.symbol, []).append(fill)
    trades: list[Trade] = []
    for symbol_fills in by_symbol.values():
        trades.extend(trades_from_fills(symbol_fills))
    return sorted(trades, key=lambda t: t.entry_time)


def evaluate(
    bars: list[Bar],
    strategy_factory: StrategyFactory,
    strategy_name: str,
    starting_equity: float,
    risk_pct: float,
    fee_per_share: float,
    max_daily_loss: float,
    flatten_at_session_end: bool,
    atr_period: int = 14,
    atr_multiple: float = 1.5,
    risk_reward: float = 2.0,
    atr_horizon: str = "bar",
    max_position_pct: Optional[float] = None,
) -> Evaluation:
    symbols = sorted({b.symbol for b in bars})

    result = run_paper_trading_on_bars(
        bars=bars,
        symbols=symbols,
        strategy_factory=strategy_factory,
        strategy_name=strategy_name,
        starting_equity=starting_equity,
        risk_pct=risk_pct,
        fee_per_share=fee_per_share,
        max_daily_loss=max_daily_loss,
        atr_period=atr_period,
        atr_multiple=atr_multiple,
        risk_reward=risk_reward,
        atr_horizon=atr_horizon,
        max_position_pct=max_position_pct,
        flatten_at_session_end=flatten_at_session_end,
    )
    paper_trades = _trades_by_symbol(result.portfolio.fills)

    # Cross-check: the reference engine is single-symbol by construction
    # (PointInTimeSeries rejects mixed symbols), so run it per symbol.
    reference_trades: list[Trade] = []
    buy_and_hold_bp: dict[str, float] = {}
    for symbol in symbols:
        symbol_bars = [b for b in bars if b.symbol == symbol]
        if not symbol_bars:
            continue
        ref = run_reference_backtest(symbol_bars, strategy_factory(), fee_per_share=fee_per_share)
        reference_trades.extend(trades_from_fills(ref.fills))
        first, last = symbol_bars[0], symbol_bars[-1]
        buy_and_hold_bp[symbol] = (last.close - first.open) / first.open * 10_000

    return Evaluation(
        paper_trades=paper_trades,
        paper_stats=compute_trade_stats(paper_trades),
        reference_stats=compute_trade_stats(reference_trades),
        buy_and_hold_bp=buy_and_hold_bp,
        session_count=len({_session_date(b.timestamp) for b in bars}),
    )
