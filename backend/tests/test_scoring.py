import unittest

from app.signals.scoring import CalibratedModel, fit_logistic_regression


class TestFitLogisticRegression(unittest.TestCase):
    def test_separates_a_linearly_separable_dataset(self):
        # clear gap between the two classes (0.0-0.3 vs 0.7-1.0)
        features = [[0.0], [0.1], [0.2], [0.3], [0.7], [0.8], [0.9], [1.0]]
        outcomes = [0, 0, 0, 0, 1, 1, 1, 1]

        model = fit_logistic_regression(features, outcomes, learning_rate=0.5, iterations=3000)

        self.assertLess(model.predict_probability([0.0]), 0.1)
        self.assertGreater(model.predict_probability([1.0]), 0.9)
        # the decision boundary should land in the gap between the classes
        self.assertLess(model.predict_probability([0.3]), 0.5)
        self.assertGreater(model.predict_probability([0.7]), 0.5)

    def test_rejects_mismatched_lengths(self):
        with self.assertRaises(ValueError):
            fit_logistic_regression([[1.0], [2.0]], [0])

    def test_rejects_empty_input(self):
        with self.assertRaises(ValueError):
            fit_logistic_regression([], [])

    def test_rejects_non_binary_outcomes(self):
        with self.assertRaises(ValueError):
            fit_logistic_regression([[1.0]], [2])

    def test_rejects_inconsistent_feature_vector_lengths(self):
        with self.assertRaises(ValueError):
            fit_logistic_regression([[1.0], [1.0, 2.0]], [0, 1])


class TestCalibratedModel(unittest.TestCase):
    def test_rejects_wrong_feature_count(self):
        model = CalibratedModel(weights=[0.0, 1.0, 1.0])  # bias + 2 features
        with self.assertRaises(ValueError):
            model.predict_probability([1.0])  # only 1 feature given

    def test_zero_weights_predict_50_percent(self):
        model = CalibratedModel(weights=[0.0, 0.0])
        self.assertAlmostEqual(model.predict_probability([5.0]), 0.5)


if __name__ == "__main__":
    unittest.main()
