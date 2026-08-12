import unittest

from app.validation.monte_carlo import bootstrap_max_drawdowns, max_drawdown, percentile


class TestMaxDrawdown(unittest.TestCase):
    def test_matches_hand_calculation(self):
        # equity: 10 (peak 10) -> -10 (drawdown -20) -> 0 (drawdown -10)
        self.assertAlmostEqual(max_drawdown([10, -20, 10]), -20.0)

    def test_monotonically_increasing_equity_has_zero_drawdown(self):
        self.assertEqual(max_drawdown([10, 10, 10]), 0.0)

    def test_empty_sequence_has_zero_drawdown(self):
        self.assertEqual(max_drawdown([]), 0.0)


class TestPercentile(unittest.TestCase):
    def test_matches_hand_calculation(self):
        values = [10, 20, 30, 40]
        self.assertAlmostEqual(percentile(values, 0), 10.0)
        self.assertAlmostEqual(percentile(values, 50), 25.0)
        self.assertAlmostEqual(percentile(values, 100), 40.0)

    def test_unsorted_input_is_handled(self):
        self.assertAlmostEqual(percentile([40, 10, 30, 20], 50), 25.0)

    def test_rejects_out_of_range_p(self):
        with self.assertRaises(ValueError):
            percentile([1, 2, 3], 150)

    def test_rejects_empty_values(self):
        with self.assertRaises(ValueError):
            percentile([], 50)


class TestBootstrapMaxDrawdowns(unittest.TestCase):
    def test_reproducible_with_a_seed(self):
        a = bootstrap_max_drawdowns([10, -5, 3, -8, 6], num_samples=20, seed=42)
        b = bootstrap_max_drawdowns([10, -5, 3, -8, 6], num_samples=20, seed=42)
        self.assertEqual(a, b)

    def test_returns_requested_sample_count(self):
        result = bootstrap_max_drawdowns([10, -5, 3], num_samples=15, seed=1)
        self.assertEqual(len(result), 15)

    def test_all_winning_trades_never_produce_a_drawdown_regardless_of_resample_order(self):
        result = bootstrap_max_drawdowns([10, 10, 10], num_samples=50, seed=1)
        self.assertTrue(all(x == 0.0 for x in result))

    def test_empty_trade_list_returns_empty(self):
        self.assertEqual(bootstrap_max_drawdowns([], num_samples=10), [])


if __name__ == "__main__":
    unittest.main()
