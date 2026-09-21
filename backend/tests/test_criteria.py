import math
import statistics
import unittest
from datetime import datetime, timedelta, timezone

from app.data.point_in_time import Bar
from app.validation.criteria import (
    breakeven_friction_bp,
    cluster_bootstrap,
    evaluate_criteria,
    net_mean_bp,
    permutation_test_entry_timing,
    split_into_periods,
)
from app.validation.metrics import Trade

# 09:30 New York, in UTC (EST = UTC-5 in January).
DAY_ONE = datetime(2026, 1, 5, 14, 30, tzinfo=timezone.utc)


def trade_with_bp(bp: float, day_offset: int = 0, minute: int = 0) -> Trade:
    """A trade whose return is exactly `bp` basis points: notional is fixed
    at 100 (price 100 x 1 share), so pnl = bp/100."""
    entry = DAY_ONE + timedelta(days=day_offset, minutes=minute)
    return Trade(
        symbol="AAA",
        entry_time=entry,
        exit_time=entry + timedelta(minutes=5),
        entry_price=100.0,
        exit_price=100.0 + bp / 100,
        quantity=1.0,
        pnl=bp / 100,
    )


class TestK3Friction(unittest.TestCase):
    def test_net_mean_matches_hand_calculation(self):
        trades = [trade_with_bp(100), trade_with_bp(200), trade_with_bp(300)]
        self.assertAlmostEqual(net_mean_bp(trades, 0.0), 200.0, places=6)
        self.assertAlmostEqual(net_mean_bp(trades, 50.0), 150.0, places=6)

    def test_breakeven_is_the_gross_mean(self):
        trades = [trade_with_bp(10), trade_with_bp(30)]
        breakeven = breakeven_friction_bp(trades)
        self.assertAlmostEqual(breakeven, 20.0, places=6)
        # by definition, charging exactly the break-even leaves nothing
        self.assertAlmostEqual(net_mean_bp(trades, breakeven), 0.0, places=6)

    def test_empty(self):
        self.assertEqual(net_mean_bp([], 2.0), 0.0)


class TestK4ClusterBootstrap(unittest.TestCase):
    """The claim being verified: resampling whole days, rather than single
    trades, corrects the standard error for clustering. Both cases below
    have an analytically known answer, so these test correctness and not
    merely that the code runs."""

    @staticmethod
    def naive_se(trades):
        from app.validation.evaluate import trade_return_bp

        values = [trade_return_bp(t) for t in trades]
        return statistics.stdev(values) / math.sqrt(len(values))

    def test_independent_trades_match_the_naive_standard_error(self):
        """One trade per day means there is no clustering to correct for, so
        the day-block standard error must reproduce the naive one."""
        trades = [trade_with_bp(bp, day_offset=i) for i, bp in enumerate([10, -5, 20, -15, 30, 0, -10, 25, 5, -20] * 5)]
        result = cluster_bootstrap(trades, samples=4000, seed=7)

        ratio = result.standard_error / self.naive_se(trades)
        self.assertAlmostEqual(ratio, 1.0, delta=0.12)
        self.assertEqual(result.day_count, len(trades))

    def test_perfectly_clustered_trades_inflate_the_naive_t_by_sqrt_k(self):
        """With k identical trades on each day, the naive standard error is
        sd/sqrt(k*D) while the honest one is sd/sqrt(D) - so the naive
        t-statistic is too large by exactly sqrt(k). Here k=10, so the
        day-block standard error must come out about 3.16x the naive one."""
        k = 10
        day_values = [10, -5, 20, -15, 30, 0, -10, 25, 5, -20] * 3
        trades = []
        for day, value in enumerate(day_values):
            for copy in range(k):
                trades.append(trade_with_bp(value, day_offset=day, minute=copy))

        result = cluster_bootstrap(trades, samples=4000, seed=7)

        ratio = result.standard_error / self.naive_se(trades)
        self.assertAlmostEqual(ratio, math.sqrt(k), delta=0.45)
        self.assertEqual(result.day_count, len(day_values))

    def test_friction_shifts_the_mean_but_not_the_standard_error(self):
        trades = [trade_with_bp(bp, day_offset=i) for i, bp in enumerate([10, 20, 30, 40, 50] * 6)]
        plain = cluster_bootstrap(trades, friction_bp=0.0, samples=2000, seed=3)
        charged = cluster_bootstrap(trades, friction_bp=5.0, samples=2000, seed=3)

        self.assertAlmostEqual(charged.mean_bp, plain.mean_bp - 5.0, places=6)
        self.assertAlmostEqual(charged.standard_error, plain.standard_error, places=6)

    def test_no_trades(self):
        result = cluster_bootstrap([], samples=100)
        self.assertEqual(result.t_stat, 0.0)
        self.assertEqual(result.p_value, 1.0)


class TestK6PeriodSplit(unittest.TestCase):
    def test_splits_by_calendar_span_not_trade_count(self):
        # 30 calendar days, 3 periods -> 10 days each; deliberately lopsided
        # trade counts so an equal-count split would give a different answer.
        trades = [trade_with_bp(1, day_offset=d) for d in [0, 1, 2, 3, 4, 15, 29]]
        periods = split_into_periods(trades, 3)

        self.assertEqual([len(p) for p in periods], [5, 1, 1])

    def test_too_short_a_span_yields_nothing(self):
        trades = [trade_with_bp(1, day_offset=0), trade_with_bp(1, day_offset=1)]
        self.assertEqual(split_into_periods(trades, 3), [])


class TestK7PermutationTest(unittest.TestCase):
    """Two cases with known answers: timing that is genuinely informative
    must come out significant, and timing that is arbitrary must not."""

    def _session_bars(self, day: int, closes: list[float]) -> list[Bar]:
        start = datetime(2026, 1, day, 14, 30, tzinfo=timezone.utc)
        bars = []
        for i, close in enumerate(closes):
            bars.append(
                Bar(
                    symbol="AAA",
                    timestamp=start + timedelta(minutes=5 * i),
                    open=close,
                    high=close + 0.1,
                    low=close - 0.1,
                    close=close,
                    volume=100,
                )
            )
        return bars

    def _v_shaped_days(self, day_count: int):
        """Each session dips to its low at bar 4, then climbs. Entering at
        the dip is the best possible entry for a fixed holding length."""
        bars: list[Bar] = []
        for d in range(day_count):
            closes = [100, 99, 98, 97, 96, 99, 102, 105, 108, 111]
            bars.extend(self._session_bars(5 + d, closes))
        return bars

    def test_informative_timing_is_significant(self):
        bars = self._v_shaped_days(12)
        by_ts = {b.timestamp: i for i, b in enumerate(bars)}

        trades = []
        for day_start in range(0, len(bars), 10):
            entry_bar = bars[day_start + 4]  # the dip
            exit_bar = bars[day_start + 8]
            trades.append(
                Trade(
                    symbol="AAA",
                    entry_time=entry_bar.timestamp,
                    exit_time=exit_bar.timestamp,
                    entry_price=entry_bar.open,
                    exit_price=exit_bar.close,
                    quantity=1.0,
                    pnl=exit_bar.close - entry_bar.open,
                )
            )
        self.assertEqual(len(trades), 12)
        self.assertTrue(all(t.entry_time in by_ts for t in trades))

        result = permutation_test_entry_timing(trades, {"AAA": bars}, permutations=2000, seed=11)

        self.assertLess(result.p_value, 0.01)
        self.assertGreater(result.observed_bp, 0)

    def test_arbitrary_timing_is_not_significant(self):
        """Same sessions, but entries sit at the *first* bar of each day -
        no information about the dip. Random entries should match it often."""
        bars = self._v_shaped_days(12)
        trades = []
        for day_start in range(0, len(bars), 10):
            entry_bar = bars[day_start]
            exit_bar = bars[day_start + 4]
            trades.append(
                Trade(
                    symbol="AAA",
                    entry_time=entry_bar.timestamp,
                    exit_time=exit_bar.timestamp,
                    entry_price=entry_bar.open,
                    exit_price=exit_bar.close,
                    quantity=1.0,
                    pnl=exit_bar.close - entry_bar.open,
                )
            )

        result = permutation_test_entry_timing(trades, {"AAA": bars}, permutations=2000, seed=11)

        self.assertGreater(result.p_value, 0.05)

    def test_p_value_is_never_zero(self):
        bars = self._v_shaped_days(6)
        trades = [
            Trade(
                symbol="AAA",
                entry_time=bars[4].timestamp,
                exit_time=bars[8].timestamp,
                entry_price=bars[4].open,
                exit_price=bars[8].close,
                quantity=1.0,
                pnl=bars[8].close - bars[4].open,
            )
        ]
        result = permutation_test_entry_timing(trades, {"AAA": bars}, permutations=100, seed=5)
        self.assertGreater(result.p_value, 0.0)


class TestVerdictComposition(unittest.TestCase):
    def _bars(self):
        start = datetime(2026, 1, 5, 14, 30, tzinfo=timezone.utc)
        return [
            Bar(
                symbol="AAA",
                timestamp=start + timedelta(minutes=5 * i),
                open=100,
                high=101,
                low=99,
                close=100,
                volume=100,
            )
            for i in range(50)
        ]

    def test_strict_and_not_applicable_also_blocks(self):
        trades = [trade_with_bp(50, day_offset=i % 30) for i in range(240)]
        verdict = evaluate_criteria(
            trades,
            {"AAA": self._bars()},
            leakage_clean=True,
            bootstrap_samples=200,
            permutations=200,
        )
        # K6 cannot be established from a trade list alone, so it must not
        # silently pass - and a non-PASS has to block the whole verdict.
        k6 = next(r for r in verdict.results if r.key == "K6")
        self.assertEqual(k6.status, "NOT_APPLICABLE")
        self.assertFalse(verdict.passed)

    def test_leakage_fails_immediately(self):
        verdict = evaluate_criteria(
            [trade_with_bp(50, day_offset=i) for i in range(10)],
            {"AAA": self._bars()},
            leakage_clean=False,
            bootstrap_samples=100,
            permutations=100,
        )
        self.assertEqual(next(r for r in verdict.results if r.key == "K1").status, "FAIL")
        self.assertFalse(verdict.passed)

    def test_small_sample_fails_k5(self):
        verdict = evaluate_criteria(
            [trade_with_bp(50, day_offset=i) for i in range(10)],
            {"AAA": self._bars()},
            leakage_clean=True,
            bootstrap_samples=100,
            permutations=100,
        )
        self.assertEqual(next(r for r in verdict.results if r.key == "K5").status, "FAIL")


if __name__ == "__main__":
    unittest.main()
