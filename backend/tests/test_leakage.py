import unittest
from datetime import datetime, timedelta, timezone

from app.data.point_in_time import Bar, SimulationCursor
from app.strategies.ema_pullback import EmaPullbackStrategy
from app.strategies.vwap_momentum import VwapMomentumStrategy
from app.validation.leakage import detect_leakage

START = datetime(2026, 1, 2, 14, 30, tzinfo=timezone.utc)  # 9:30 NY


def make_bars(closes: list[float], start=START) -> list[Bar]:
    return [
        Bar(symbol="TEST", timestamp=start + timedelta(minutes=5 * i), open=c, high=c + 0.2, low=c - 0.2, close=c, volume=1000)
        for i, c in enumerate(closes)
    ]


class CheatingStrategy:
    """Deliberately reaches into `cursor._bars` (bypassing the intended
    cursor.history-only contract — see point_in_time.py's own caveat about
    this) to peek at the last bar of whichever series it is currently
    part of. Exists only to prove detect_leakage() catches something real;
    not a strategy anyone should write."""

    def __call__(self, cursor: SimulationCursor) -> str:
        last_known_close = cursor._bars[-1].close
        current_close = cursor.current.close
        return "BUY" if last_known_close > current_close else "HOLD"


class TestDetectLeakageOnHonestStrategies(unittest.TestCase):
    """Our real strategies only ever read `cursor.history` - proving they
    come back clean is itself a useful regression test, not just a demo."""

    def test_vwap_momentum_is_clean(self):
        closes = [100 + i * 0.3 for i in range(15)] + [95, 90, 85, 80, 75]
        bars = make_bars(closes)
        report = detect_leakage(bars, lambda: VwapMomentumStrategy(fast_period=3, slow_period=5), cut_index=12)
        self.assertTrue(report.clean, msg=report.mismatches)

    def test_ema_pullback_is_clean(self):
        closes = [100 + i * 1.0 for i in range(8)] + [104.0, 107.0, 110.0, 108.0, 106.0]
        bars = make_bars(closes)
        report = detect_leakage(bars, lambda: EmaPullbackStrategy(fast_period=3, slow_period=6), cut_index=9)
        self.assertTrue(report.clean, msg=report.mismatches)

    def test_rejects_out_of_range_cut_index(self):
        bars = make_bars([100, 101, 102])
        with self.assertRaises(ValueError):
            detect_leakage(bars, lambda: VwapMomentumStrategy(), cut_index=0)
        with self.assertRaises(ValueError):
            detect_leakage(bars, lambda: VwapMomentumStrategy(), cut_index=3)


class TestDetectLeakageCatchesACheat(unittest.TestCase):
    def test_cheating_strategy_is_flagged(self):
        # only the FULL series' final bar is a huge spike (200); the
        # prefix's own final bar is flat (100). A strategy peeking at
        # "the last bar of my series" will decide differently in the two
        # runs at every earlier position.
        closes = [100.0] * 19 + [200.0]
        bars = make_bars(closes)

        report = detect_leakage(bars, lambda: CheatingStrategy(), cut_index=10)

        self.assertFalse(report.clean)
        self.assertGreater(len(report.mismatches), 0)

    def test_clean_when_the_peeked_value_happens_to_match(self):
        # sanity check: the same cheat is NOT flagged if there's nothing
        # to leak (the prefix's own last bar already equals the true
        # final bar) - confirms the detector isn't just always failing on
        # this strategy class regardless of the data.
        closes = [100.0] * 20
        bars = make_bars(closes)
        report = detect_leakage(bars, lambda: CheatingStrategy(), cut_index=10)
        self.assertTrue(report.clean, msg=report.mismatches)


if __name__ == "__main__":
    unittest.main()
