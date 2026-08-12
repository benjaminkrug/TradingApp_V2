import unittest
from datetime import datetime, timedelta, timezone

from app.data.point_in_time import Bar, SimulationCursor
from app.validation.gate import evaluate_candidate
from app.validation.walk_forward import WalkForwardWindow

START = datetime(2026, 1, 2, 14, 30, tzinfo=timezone.utc)


class ToyStrategy:
    """Deterministic period-4 BUY/HOLD/SELL toggle - not a real trading
    idea, just something with a controllable, predictable trade count for
    exercising the gate's wiring rather than strategy quality."""

    def __call__(self, cursor: SimulationCursor) -> str:
        m = len(cursor.history) % 4
        if m == 1:
            return "BUY"
        if m == 3:
            return "SELL"
        return "HOLD"


def make_bars(closes: list[float], start=START) -> list[Bar]:
    return [
        Bar(symbol="TEST", timestamp=start + timedelta(minutes=5 * i), open=c, high=c + 0.1, low=c - 0.1, close=c, volume=1000)
        for i, c in enumerate(closes)
    ]


class TestEvaluateCandidate(unittest.TestCase):
    def setUp(self):
        self.bars = make_bars([100 + i * 0.05 for i in range(80)])  # mild uptrend, 20 round trips

    def test_unsupplied_optional_checks_are_not_automated(self):
        report = evaluate_candidate(
            bars=self.bars,
            strategy_factory=ToyStrategy,
            fee_per_share=0.001,
            leakage_cut_index=40,
            min_trades=5,
        )
        not_automated = {r.name for r in report.results if r.status == "NOT_AUTOMATED"}
        self.assertEqual(
            not_automated,
            {
                "no_survivorship_bias",
                "realistic_slippage",
                "realistic_execution",
                "oos_positive",
                "walk_forward_stable",
                "monte_carlo_acceptable",
                "multiple_regimes_tested",
                "paper_trading_confirmed",
            },
        )
        self.assertFalse(report.fully_automated)

    def test_passes_on_a_clean_profitable_setup(self):
        oos_bars = make_bars([100 + i * 0.05 for i in range(40)], start=START + timedelta(days=1))
        report = evaluate_candidate(
            bars=self.bars,
            strategy_factory=ToyStrategy,
            fee_per_share=0.001,
            leakage_cut_index=40,
            min_trades=5,
            oos_bars=oos_bars,
            monte_carlo_drawdown_threshold=-1000,
            monte_carlo_seed=1,
        )
        self.assertTrue(report.passed, msg=[r for r in report.results if r.status == "FAIL"])

    def test_zero_fee_fails_the_fee_check(self):
        report = evaluate_candidate(
            bars=self.bars, strategy_factory=ToyStrategy, fee_per_share=0.0, leakage_cut_index=40, min_trades=5
        )
        fee_check = next(r for r in report.results if r.name == "realistic_fees")
        self.assertEqual(fee_check.status, "FAIL")
        self.assertFalse(report.passed)

    def test_unreachable_min_trades_fails_that_check(self):
        report = evaluate_candidate(
            bars=self.bars, strategy_factory=ToyStrategy, fee_per_share=0.001, leakage_cut_index=40, min_trades=1000
        )
        trade_check = next(r for r in report.results if r.name == "sufficient_trades")
        self.assertEqual(trade_check.status, "FAIL")

    def test_losing_oos_fails_that_check(self):
        losing_oos = make_bars([100 - i * 0.05 for i in range(40)], start=START + timedelta(days=1))
        report = evaluate_candidate(
            bars=self.bars,
            strategy_factory=ToyStrategy,
            fee_per_share=0.001,
            leakage_cut_index=40,
            min_trades=5,
            oos_bars=losing_oos,
        )
        oos_check = next(r for r in report.results if r.name == "oos_positive")
        self.assertEqual(oos_check.status, "FAIL")

    def test_walk_forward_windows_are_evaluated(self):
        profitable_window = WalkForwardWindow(train=[], test=make_bars([100 + i * 0.05 for i in range(30)]))
        losing_window = WalkForwardWindow(
            train=[], test=make_bars([100 - i * 0.05 for i in range(30)], start=START + timedelta(days=1))
        )

        report = evaluate_candidate(
            bars=self.bars,
            strategy_factory=ToyStrategy,
            fee_per_share=0.001,
            leakage_cut_index=40,
            min_trades=5,
            walk_forward_test_windows=[profitable_window, losing_window],
        )
        wf_check = next(r for r in report.results if r.name == "walk_forward_stable")
        self.assertEqual(wf_check.status, "PASS")  # 1/2 profitable meets the 50% bar
        self.assertIn("1/2", wf_check.detail)

    def test_impossible_monte_carlo_threshold_fails(self):
        report = evaluate_candidate(
            bars=self.bars,
            strategy_factory=ToyStrategy,
            fee_per_share=0.001,
            leakage_cut_index=40,
            min_trades=5,
            monte_carlo_drawdown_threshold=100.0,  # nothing satisfies "drawdown >= +100"
            monte_carlo_seed=1,
        )
        mc_check = next(r for r in report.results if r.name == "monte_carlo_acceptable")
        self.assertEqual(mc_check.status, "FAIL")


if __name__ == "__main__":
    unittest.main()
