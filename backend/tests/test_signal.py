import unittest
from datetime import datetime, timedelta, timezone

from app.data.point_in_time import Bar, PointInTimeSeries
from app.signals.scoring import CalibratedModel
from app.signals.signal import build_signal

START = datetime(2026, 1, 2, 14, 30, tzinfo=timezone.utc)


def make_bars(closes: list[float], symbol: str = "AAPL") -> list[Bar]:
    return [
        Bar(symbol=symbol, timestamp=START + timedelta(minutes=5 * i), open=c, high=c + 0.2, low=c - 0.2, close=c, volume=1000)
        for i, c in enumerate(closes)
    ]


class TestBuildSignal(unittest.TestCase):
    def test_returns_none_for_non_buy_actions(self):
        bars = make_bars([100] * 20)
        cursor = PointInTimeSeries(bars).new_cursor()
        for _ in range(20):
            cursor.advance()
        for action in ("SELL", "HOLD"):
            self.assertIsNone(build_signal(cursor, action, "test", account_equity=50000, risk_pct=0.005))

    def test_returns_none_before_atr_can_be_computed(self):
        bars = make_bars([100, 101, 102])  # far fewer than the default atr_period=14
        cursor = PointInTimeSeries(bars).new_cursor()
        cursor.advance()
        self.assertIsNone(build_signal(cursor, "BUY", "test", account_equity=50000, risk_pct=0.005))

    def test_builds_a_complete_signal_with_correct_risk_numbers(self):
        # enough history for a 5-period ATR; distinct O/H/L/C per bar
        closes = [100 + i * 0.5 for i in range(10)]
        bars = make_bars(closes)
        cursor = PointInTimeSeries(bars).new_cursor()
        for _ in range(10):
            cursor.advance()

        signal = build_signal(
            cursor,
            "BUY",
            "VWAP Momentum",
            account_equity=50000,
            risk_pct=0.005,
            atr_period=5,
            atr_multiple=1.5,
            risk_reward=2.0,
        )

        self.assertIsNotNone(signal)
        self.assertEqual(signal.symbol, "AAPL")
        self.assertEqual(signal.entry, bars[9].close)
        self.assertLess(signal.stop, signal.entry)  # long-only stop below entry
        self.assertGreater(signal.target, signal.entry)  # target above entry
        # position sizing must match risk.py's own formula, independently recomputed here
        expected_shares = (50000 * 0.005) / (signal.entry - signal.stop)
        self.assertAlmostEqual(signal.shares, expected_shares)
        self.assertIsNone(signal.score)
        self.assertEqual(signal.confidence, "UNCALIBRATED")
        self.assertIn("Strategy: VWAP Momentum", signal.rationale)

    def test_uncalibrated_without_a_model_calibrated_with_one(self):
        closes = [100 + i * 0.5 for i in range(10)]
        bars = make_bars(closes)
        cursor = PointInTimeSeries(bars).new_cursor()
        for _ in range(10):
            cursor.advance()

        uncalibrated = build_signal(cursor, "BUY", "test", account_equity=50000, risk_pct=0.005, atr_period=5)
        self.assertIsNone(uncalibrated.score)
        self.assertEqual(uncalibrated.confidence, "UNCALIBRATED")

        model = CalibratedModel(weights=[10.0, 0.0, 0.0, 0.0])  # heavily biased toward "yes" regardless of features
        calibrated = build_signal(
            cursor, "BUY", "test", account_equity=50000, risk_pct=0.005, atr_period=5, calibrated_model=model
        )
        self.assertIsNotNone(calibrated.score)
        self.assertGreater(calibrated.score, 99)  # sigmoid(10) is very close to 100
        self.assertEqual(calibrated.confidence, "HIGH")


if __name__ == "__main__":
    unittest.main()
