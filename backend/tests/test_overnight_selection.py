import unittest
from datetime import date, datetime, timedelta, timezone

from app.data.point_in_time import Bar
from app.validation.overnight_selection import (
    DailyBars,
    eligible_symbols_by_day,
    overnight_returns_by_day,
    relative_volume_by_day,
    select_top_by_relative_volume,
    selection_vs_random_permutation_test,
)

DAY0 = date(2026, 1, 5)


def daily_bar(symbol: str, day_offset: int, close: float, volume: float, open_: float = None) -> Bar:
    ts = datetime.combine(DAY0 + timedelta(days=day_offset), datetime.min.time(), tzinfo=timezone.utc)
    o = open_ if open_ is not None else close
    return Bar(symbol=symbol, timestamp=ts, open=o, high=max(o, close) + 0.1, low=min(o, close) - 0.1,
               close=close, volume=volume)


class TestRelativeVolumeByDay(unittest.TestCase):
    def test_matches_hand_calculation(self):
        # 5 warm-up days at volume 100, then a day at 500 -> rel vol = 500/100 = 5.0
        bars = [daily_bar("X", i, close=10.0, volume=100) for i in range(5)]
        bars.append(daily_bar("X", 5, close=10.0, volume=500))
        rv = relative_volume_by_day(DailyBars("X", bars), lookback=5)

        self.assertIsNone(rv[DAY0])  # day 0: no prior history at all
        self.assertAlmostEqual(rv[DAY0 + timedelta(days=5)], 5.0)

    def test_never_uses_the_day_itself_or_later(self):
        """The whole point: day N's ranking must not see day N's own volume
        beyond what it's being divided into, nor any future day."""
        bars = [daily_bar("X", i, close=10.0, volume=100) for i in range(3)]
        bars.append(daily_bar("X", 3, close=10.0, volume=100_000))  # huge spike
        bars.append(daily_bar("X", 4, close=10.0, volume=100))

        rv = relative_volume_by_day(DailyBars("X", bars), lookback=3)
        # day 3's ratio must be computed from days 0-2 only (100,100,100 -> 100),
        # not contaminated by its own spike or day 4's normal volume.
        self.assertAlmostEqual(rv[DAY0 + timedelta(days=3)], 100_000 / 100)


class TestSelectTopByRelativeVolume(unittest.TestCase):
    def test_ranks_and_truncates_to_top_n(self):
        warmup = 3
        bars_a = [daily_bar("AAA", i, 10.0, 100) for i in range(warmup)] + [daily_bar("AAA", warmup, 10.0, 300)]
        bars_b = [daily_bar("BBB", i, 10.0, 100) for i in range(warmup)] + [daily_bar("BBB", warmup, 10.0, 900)]
        bars_c = [daily_bar("CCC", i, 10.0, 100) for i in range(warmup)] + [daily_bar("CCC", warmup, 10.0, 150)]

        selections = select_top_by_relative_volume(
            {"AAA": DailyBars("AAA", bars_a), "BBB": DailyBars("BBB", bars_b), "CCC": DailyBars("CCC", bars_c)},
            lookback=warmup, top_n=2, min_price=0.0,
        )
        target_day = DAY0 + timedelta(days=warmup)
        # relative volumes: BBB=9.0, AAA=3.0, CCC=1.5 -> top 2 = BBB, AAA
        self.assertEqual(selections[target_day], ["BBB", "AAA"])

    def test_excludes_symbols_below_min_price(self):
        warmup = 2
        cheap = [daily_bar("PENNY", i, 1.0, 100) for i in range(warmup)] + [daily_bar("PENNY", warmup, 1.0, 900)]
        ok = [daily_bar("OK", i, 10.0, 100) for i in range(warmup)] + [daily_bar("OK", warmup, 10.0, 200)]

        selections = select_top_by_relative_volume(
            {"PENNY": DailyBars("PENNY", cheap), "OK": DailyBars("OK", ok)},
            lookback=warmup, top_n=5, min_price=5.0,
        )
        target_day = DAY0 + timedelta(days=warmup)
        self.assertEqual(selections[target_day], ["OK"])


class TestOvernightReturnsByDay(unittest.TestCase):
    def test_matches_hand_calculation(self):
        bars = [
            daily_bar("X", 0, close=100.0, volume=100),
            daily_bar("X", 1, close=110.0, volume=100, open_=102.0),
        ]
        returns = overnight_returns_by_day({"X": DailyBars("X", bars)})
        # entry close=100 (day0) -> exit open=102 (day1): (102-100)/100 * 10000 = 200 bp
        self.assertAlmostEqual(returns[DAY0]["X"], 200.0)
        self.assertNotIn(DAY0 + timedelta(days=1), returns)  # no day 2 to exit into


class TestSelectionVsRandomPermutation(unittest.TestCase):
    """The claim being verified: this test must find real selection skill
    significant, and no-skill (random-equivalent) selection not significant.
    Both cases have a knowable answer, unlike just checking the code runs.
    """

    def _make_day_returns(self, day_count, symbol_count, best_symbol_bonus_bp):
        """`symbol_count` symbols per day; one designated symbol always
        returns `best_symbol_bonus_bp` more than the rest (which are 0)."""
        eligible = {}
        returns = {}
        for d in range(day_count):
            day = DAY0 + timedelta(days=d)
            symbols = [f"S{i}" for i in range(symbol_count)]
            eligible[day] = symbols
            returns[day] = {s: 0.0 for s in symbols}
            returns[day]["S0"] = best_symbol_bonus_bp
        return eligible, returns

    def test_always_picking_the_genuinely_best_symbol_is_significant(self):
        eligible, returns = self._make_day_returns(day_count=40, symbol_count=20, best_symbol_bonus_bp=50.0)
        selected = {day: ["S0"] for day in eligible}  # always picks the one symbol with real edge

        result = selection_vs_random_permutation_test(selected, eligible, returns, permutations=3000, seed=1)

        self.assertLess(result.p_value, 0.01)
        self.assertAlmostEqual(result.observed_mean_bp, 50.0)

    def test_picking_a_fixed_mediocre_symbol_is_not_significant(self):
        eligible, returns = self._make_day_returns(day_count=40, symbol_count=20, best_symbol_bonus_bp=50.0)
        selected = {day: ["S7"] for day in eligible}  # a symbol with no edge (return 0.0 every day)

        result = selection_vs_random_permutation_test(selected, eligible, returns, permutations=3000, seed=1)

        self.assertGreater(result.p_value, 0.10)
        self.assertAlmostEqual(result.observed_mean_bp, 0.0)

    def test_larger_selection_size_is_handled_and_still_detects_skill(self):
        """Selecting top-3 of 20, where the top 3 by construction always
        outperform the rest, must also come out significant."""
        day_count, symbol_count = 30, 20
        eligible, returns = {}, {}
        for d in range(day_count):
            day = DAY0 + timedelta(days=d)
            symbols = [f"S{i}" for i in range(symbol_count)]
            eligible[day] = symbols
            returns[day] = {s: 0.0 for s in symbols}
            for top in ("S0", "S1", "S2"):
                returns[day][top] = 30.0
        selected = {day: ["S0", "S1", "S2"] for day in eligible}

        result = selection_vs_random_permutation_test(selected, eligible, returns, permutations=3000, seed=2)

        self.assertLess(result.p_value, 0.01)

    def test_empty_input(self):
        result = selection_vs_random_permutation_test({}, {}, {}, permutations=100)
        self.assertEqual(result.p_value, 1.0)
        self.assertEqual(result.trade_count, 0)

    def test_p_value_is_never_zero(self):
        eligible, returns = self._make_day_returns(day_count=10, symbol_count=5, best_symbol_bonus_bp=1000.0)
        selected = {day: ["S0"] for day in eligible}
        result = selection_vs_random_permutation_test(selected, eligible, returns, permutations=50, seed=1)
        self.assertGreater(result.p_value, 0.0)


if __name__ == "__main__":
    unittest.main()
