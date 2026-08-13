import unittest
from datetime import date, timedelta

from app.data.calendar import is_trading_day, session_bounds
from app.data.point_in_time import Bar
from app.data.providers.fake import FakeProvider
from app.paper.engine import PaperTradingEngine, run_paper_trading
from app.paper.portfolio import Portfolio
from app.signals.news_filter import FakeEarningsCalendarProvider
from app.signals.risk import DailyLossGuard

SYMBOL = "TEST"


def bar(t, o, h, l, c, v=1000.0):
    return Bar(symbol=SYMBOL, timestamp=t, open=o, high=h, low=l, close=c, volume=v)


class ScriptedStrategy:
    """Returns a fixed, pre-programmed sequence of actions regardless of
    cursor content - lets tests control exactly when a BUY/SELL/HOLD is
    decided without needing a real strategy's indicator math to line up."""

    def __init__(self, actions: list[str]):
        self._actions = list(actions)

    def __call__(self, cursor) -> str:
        if not self._actions:
            return "HOLD"
        return self._actions.pop(0)


def new_engine(strategy, portfolio=None, daily_loss_guard=None, risk_pct=0.0025, fee_per_share=0.0, earnings_provider=None):
    return PaperTradingEngine(
        symbol=SYMBOL,
        strategy=strategy,
        strategy_name="scripted",
        portfolio=portfolio or Portfolio(starting_cash=50_000.0),
        daily_loss_guard=daily_loss_guard or DailyLossGuard(max_daily_loss=10_000.0),
        risk_pct=risk_pct,
        fee_per_share=fee_per_share,
        atr_period=2,
        atr_multiple=1.0,
        risk_reward=2.0,
        earnings_provider=earnings_provider,
    )


class TestPaperTradingEngineEntry(unittest.TestCase):
    """Bars 0-2 are flat (open=high=low=close) so True Range at each step
    equals the close-to-close move: TR(bar1)=1, TR(bar2)=1, so
    atr(bars, period=2) = 1.0 exactly at bar2 - hand-verifiable ATR without
    needing 15 bars for the default period."""

    def setUp(self):
        base = session_bounds(date(2026, 1, 6))[0]  # a real trading day's open
        self.t = [base + timedelta(minutes=5 * i) for i in range(6)]
        self.flat_bars = [bar(self.t[0], 100, 100, 100, 100), bar(self.t[1], 101, 101, 101, 101), bar(self.t[2], 102, 102, 102, 102)]

    def test_buy_signal_sizes_and_stops_via_build_signal_then_fills_next_bar_open(self):
        strategy = ScriptedStrategy(["HOLD", "HOLD", "BUY", "HOLD"])
        portfolio = Portfolio(starting_cash=50_000.0)
        engine = new_engine(strategy, portfolio=portfolio)

        for b in self.flat_bars:
            engine.on_bar(b)
        # No fill yet - a BUY decided on bar2's close only queues an order,
        # per reference_engine.py's next-bar-open convention.
        self.assertNotIn(SYMBOL, portfolio.positions)

        # entry_ref=102, atr=1.0, stop=102-1.0*1.0=101, target=102+2.0*(102-101)=104
        # max_loss = 0.25% * 50000 = 125; risk_per_share=1 -> shares=125
        fill_bar = bar(self.t[3], 103, 103, 103, 103)
        engine.on_bar(fill_bar)

        self.assertIn(SYMBOL, portfolio.positions)
        position = portfolio.positions[SYMBOL]
        self.assertAlmostEqual(position.entry_price, 103.0)  # filled at next bar's OPEN
        self.assertAlmostEqual(position.quantity, 125.0)
        self.assertAlmostEqual(position.stop, 101.0)
        self.assertAlmostEqual(position.target, 104.0)

    def test_target_hit_closes_position_at_target_price(self):
        strategy = ScriptedStrategy(["HOLD", "HOLD", "BUY", "HOLD", "HOLD"])
        portfolio = Portfolio(starting_cash=50_000.0)
        guard = DailyLossGuard(max_daily_loss=10_000.0)
        engine = new_engine(strategy, portfolio=portfolio, daily_loss_guard=guard)

        for b in self.flat_bars:
            engine.on_bar(b)
        engine.on_bar(bar(self.t[3], 103, 103, 103, 103))  # fills BUY at 103, stop=101/target=104

        # high breaches target(104), low stays above stop(101)
        engine.on_bar(bar(self.t[4], 103.5, 104.5, 103.0, 104.0))

        self.assertNotIn(SYMBOL, portfolio.positions)
        self.assertEqual(len(portfolio.fills), 2)
        self.assertAlmostEqual(portfolio.fills[-1].price, 104.0)  # exits at target, not bar high
        # pnl = (104-103)*125 = 125, no fees
        self.assertAlmostEqual(guard.cumulative_pnl, 125.0)
        self.assertAlmostEqual(portfolio.cash, 50_000.0 + 125.0)

    def test_stop_hit_closes_position_at_stop_price(self):
        strategy = ScriptedStrategy(["HOLD", "HOLD", "BUY", "HOLD", "HOLD"])
        portfolio = Portfolio(starting_cash=50_000.0)
        guard = DailyLossGuard(max_daily_loss=10_000.0)
        engine = new_engine(strategy, portfolio=portfolio, daily_loss_guard=guard)

        for b in self.flat_bars:
            engine.on_bar(b)
        engine.on_bar(bar(self.t[3], 103, 103, 103, 103))  # fills BUY at 103, stop=101/target=104

        # low breaches stop(101), high stays below target(104)
        engine.on_bar(bar(self.t[4], 102.5, 102.8, 100.5, 101.5))

        self.assertNotIn(SYMBOL, portfolio.positions)
        self.assertAlmostEqual(portfolio.fills[-1].price, 101.0)  # exits at stop, not bar low
        # pnl = (101-103)*125 = -250
        self.assertAlmostEqual(guard.cumulative_pnl, -250.0)

    def test_both_stop_and_target_breached_same_bar_assumes_stop_first(self):
        strategy = ScriptedStrategy(["HOLD", "HOLD", "BUY", "HOLD", "HOLD"])
        portfolio = Portfolio(starting_cash=50_000.0)
        engine = new_engine(strategy, portfolio=portfolio)

        for b in self.flat_bars:
            engine.on_bar(b)
        engine.on_bar(bar(self.t[3], 103, 103, 103, 103))

        # wide bar: low below stop(101) AND high above target(104)
        engine.on_bar(bar(self.t[4], 103, 105, 100, 102))

        self.assertAlmostEqual(portfolio.fills[-1].price, 101.0)  # stop wins the ambiguity, documented in engine.py


class TestPaperTradingEngineBuyingPower(unittest.TestCase):
    def test_order_exceeding_cash_by_fill_time_is_dropped_not_filled_on_margin(self):
        # Sized at decision time (bar2) off equity=50,000 -> affordable then.
        # Between the decision and the next bar's fill, cash is drained -
        # simulating another symbol's engine (sharing the same Portfolio in
        # run_paper_trading, see engine.py) having spent it in the
        # meantime. The order must be dropped at fill time, not crash and
        # not silently go negative (regression test for the negative-cash
        # bug found via scripts/phase9_paper_trading_demo.py).
        strategy = ScriptedStrategy(["HOLD", "HOLD", "BUY", "HOLD"])
        portfolio = Portfolio(starting_cash=50_000.0)
        engine = new_engine(strategy, portfolio=portfolio)

        base = session_bounds(date(2026, 1, 6))[0]
        t = [base + timedelta(minutes=5 * i) for i in range(4)]
        flat_bars = [bar(t[0], 100, 100, 100, 100), bar(t[1], 101, 101, 101, 101), bar(t[2], 102, 102, 102, 102)]
        for b in flat_bars:
            engine.on_bar(b)  # bar2 decides BUY: shares=125 (see TestPaperTradingEngineEntry), affordable at $50,000

        portfolio.cash = 50.0  # another symbol's fill (not modeled here) spent the rest
        engine.on_bar(bar(t[3], 103, 103, 103, 103))  # would cost 125*103=12,875 - can no longer afford it

        self.assertNotIn(SYMBOL, portfolio.positions)
        self.assertEqual(portfolio.fills, [])
        self.assertAlmostEqual(portfolio.cash, 50.0)  # untouched by the rejected order


class TestPaperTradingEngineDailyLossGuard(unittest.TestCase):
    def test_tripped_guard_blocks_new_entries_but_not_existing_exits(self):
        base = session_bounds(date(2026, 1, 6))[0]
        t = [base + timedelta(minutes=5 * i) for i in range(6)]
        flat_bars = [bar(t[0], 100, 100, 100, 100), bar(t[1], 101, 101, 101, 101), bar(t[2], 102, 102, 102, 102)]

        strategy = ScriptedStrategy(["HOLD", "HOLD", "BUY", "HOLD", "HOLD", "BUY"])
        portfolio = Portfolio(starting_cash=50_000.0)
        guard = DailyLossGuard(max_daily_loss=200.0)  # trips on the stop-loss below (-250)
        engine = new_engine(strategy, portfolio=portfolio, daily_loss_guard=guard)

        for b in flat_bars:
            engine.on_bar(b)
        engine.on_bar(bar(t[3], 103, 103, 103, 103))  # fills BUY at 103, stop=101/target=104
        engine.on_bar(bar(t[4], 102.5, 102.8, 100.5, 101.5))  # stop hit: pnl=-250, trips the guard

        self.assertFalse(guard.can_trade())
        self.assertNotIn(SYMBOL, portfolio.positions)

        # scripted action[5] = "BUY" again, but the guard is tripped - must not open a new position
        engine.on_bar(bar(t[5], 102, 102, 102, 102))
        self.assertNotIn(SYMBOL, portfolio.positions)


class TestPaperTradingEngineSessionRollover(unittest.TestCase):
    def test_open_position_is_force_flattened_at_session_boundary_and_guard_resets(self):
        day1 = date(2026, 1, 6)
        day2 = date(2026, 1, 7)
        self.assertTrue(is_trading_day(day1) and is_trading_day(day2))

        day1_open = session_bounds(day1)[0]
        t = [day1_open + timedelta(minutes=5 * i) for i in range(4)]
        day2_open = session_bounds(day2)[0]

        strategy = ScriptedStrategy(["HOLD", "HOLD", "BUY", "HOLD"])
        portfolio = Portfolio(starting_cash=50_000.0)
        guard = DailyLossGuard(max_daily_loss=10_000.0)
        engine = new_engine(strategy, portfolio=portfolio, daily_loss_guard=guard)

        engine.on_bar(bar(t[0], 100, 100, 100, 100))
        engine.on_bar(bar(t[1], 101, 101, 101, 101))
        engine.on_bar(bar(t[2], 102, 102, 102, 102))  # decides BUY (stop=101, target=104)
        last_bar_of_day1 = bar(t[3], 103, 103.2, 102.8, 103.1)  # fills BUY at 103; neither stop nor target hit
        engine.on_bar(last_bar_of_day1)
        self.assertIn(SYMBOL, portfolio.positions)

        guard.record_pnl(-10_001.0)  # simulate an unrelated loss that trips the guard, to prove reset() clears it
        self.assertFalse(guard.can_trade())

        first_bar_of_day2 = bar(day2_open, 103.5, 103.5, 103.5, 103.5)
        engine.on_bar(first_bar_of_day2)

        # forced flatten at the LAST bar of the ending session's close (103.1), not day2's open
        self.assertNotIn(SYMBOL, portfolio.positions)
        self.assertAlmostEqual(portfolio.fills[-1].price, 103.1)
        self.assertAlmostEqual(portfolio.fills[-1].timestamp, last_bar_of_day1.timestamp)

        # new day: daily loss guard must have been reset
        self.assertTrue(guard.can_trade())
        self.assertAlmostEqual(guard.cumulative_pnl, 0.0)


class TestRunPaperTrading(unittest.TestCase):
    def test_multi_symbol_driver_dispatches_bars_to_the_right_engine(self):
        base = session_bounds(date(2026, 1, 6))[0]
        t = [base + timedelta(minutes=5 * i) for i in range(4)]

        def bars_for(symbol, closes):
            return [
                Bar(symbol=symbol, timestamp=ts, open=c, high=c, low=c, close=c, volume=1000.0)
                for ts, c in zip(t, closes)
            ]

        # AAPL: flat then a jump - triggers ScriptedStrategy's BUY on the 3rd bar
        # MSFT: stays flat the whole time - never trades
        provider = FakeProvider(
            {
                "AAPL": bars_for("AAPL", [100, 101, 102, 103]),
                "MSFT": bars_for("MSFT", [50, 50, 50, 50]),
            }
        )

        actions_by_symbol = {"AAPL": ["HOLD", "HOLD", "BUY", "HOLD"], "MSFT": ["HOLD", "HOLD", "HOLD", "HOLD"]}
        call_count = {"n": 0}

        def strategy_factory():
            # run_paper_trading calls this once per symbol - hand out the
            # right scripted sequence based on call order (AAPL then MSFT,
            # matching the `symbols` list passed below).
            symbol = ["AAPL", "MSFT"][call_count["n"]]
            call_count["n"] += 1
            return ScriptedStrategy(actions_by_symbol[symbol])

        result = run_paper_trading(
            provider=provider,
            symbols=["AAPL", "MSFT"],
            strategy_factory=strategy_factory,
            strategy_name="scripted",
            start=date(2026, 1, 6),
            end=date(2026, 1, 6),
            timeframe="5Min",
            starting_equity=50_000.0,
            risk_pct=0.0025,
            fee_per_share=0.0,
            max_daily_loss=10_000.0,
            atr_period=2,
            atr_multiple=1.0,
            risk_reward=2.0,
        )

        # AAPL's BUY on bar index 2 has no bar index 3... wait it does (4
        # bars, index 3 exists) so it fills; MSFT never signals.
        self.assertIn("AAPL", result.portfolio.positions)
        self.assertNotIn("MSFT", result.portfolio.positions)
        self.assertEqual({f.symbol for f in result.portfolio.fills}, {"AAPL"})


class TestPaperTradingEnginePretradeGate(unittest.TestCase):
    """Bars 0-2 are the same flat 100/101/102 scenario used throughout this
    file: BUY decided on bar2 (entry_ref=102, stop=101, target=104,
    shares=125), would normally fill at bar3's open (103)."""

    def setUp(self):
        self.base = session_bounds(date(2026, 1, 6))[0]
        self.t = [self.base + timedelta(minutes=5 * i) for i in range(4)]
        self.flat_bars = [bar(self.t[0], 100, 100, 100, 100), bar(self.t[1], 101, 101, 101, 101), bar(self.t[2], 102, 102, 102, 102)]

    def test_earnings_blackout_blocks_the_entry(self):
        session_date = self.t[2].date()  # NY-local date coincides with UTC here (January, EST)
        provider = FakeEarningsCalendarProvider({SYMBOL: [session_date]})  # earnings the same day as the decision
        strategy = ScriptedStrategy(["HOLD", "HOLD", "BUY", "HOLD"])
        portfolio = Portfolio(starting_cash=50_000.0)
        engine = new_engine(strategy, portfolio=portfolio, earnings_provider=provider)

        for b in self.flat_bars:
            engine.on_bar(b)
        engine.on_bar(bar(self.t[3], 103, 103, 103, 103))  # would fill here if not blocked

        self.assertNotIn(SYMBOL, portfolio.positions)
        self.assertEqual(portfolio.fills, [])
        self.assertIsNotNone(engine.last_pretrade_gate_report)
        self.assertTrue(engine.last_pretrade_gate_report.blocked)

    def test_no_upcoming_earnings_allows_the_entry(self):
        provider = FakeEarningsCalendarProvider({})  # nothing scheduled - gate should not block
        strategy = ScriptedStrategy(["HOLD", "HOLD", "BUY", "HOLD"])
        portfolio = Portfolio(starting_cash=50_000.0)
        engine = new_engine(strategy, portfolio=portfolio, earnings_provider=provider)

        for b in self.flat_bars:
            engine.on_bar(b)
        engine.on_bar(bar(self.t[3], 103, 103, 103, 103))

        self.assertIn(SYMBOL, portfolio.positions)
        self.assertFalse(engine.last_pretrade_gate_report.blocked)

    def test_without_earnings_provider_gate_is_never_run(self):
        strategy = ScriptedStrategy(["HOLD", "HOLD", "BUY", "HOLD"])
        portfolio = Portfolio(starting_cash=50_000.0)
        engine = new_engine(strategy, portfolio=portfolio)  # earnings_provider=None (default)

        for b in self.flat_bars:
            engine.on_bar(b)
        engine.on_bar(bar(self.t[3], 103, 103, 103, 103))

        self.assertIn(SYMBOL, portfolio.positions)  # unaffected - same as every pre-Phase-11 test in this file
        self.assertIsNone(engine.last_pretrade_gate_report)


if __name__ == "__main__":
    unittest.main()
