import unittest

from app.signals.scoring import CalibratedModel, fit_logistic_regression


class TestFitLogisticRegression(unittest.TestCase):
    def test_separates_a_linearly_separable_dataset(self):
        # clear gap between the two classes (0.0-0.3 vs 0.7-1.0). With the
        # default L2 regularization the model is deliberately not
        # ultra-confident (see test_regularization_prevents_weight_blowup
        # below for why) - it just has to land on the correct side of 0.5.
        features = [[0.0], [0.1], [0.2], [0.3], [0.7], [0.8], [0.9], [1.0]]
        outcomes = [0, 0, 0, 0, 1, 1, 1, 1]

        model = fit_logistic_regression(features, outcomes, learning_rate=0.5, iterations=3000)

        self.assertLess(model.predict_probability([0.0]), 0.5)
        self.assertGreater(model.predict_probability([1.0]), 0.5)
        # the decision boundary should land in the gap between the classes
        self.assertLess(model.predict_probability([0.3]), 0.5)
        self.assertGreater(model.predict_probability([0.7]), 0.5)

    def test_regularization_prevents_weight_blowup_on_a_separable_sample(self):
        # Found during the Phase 5/6 critical re-review: on a small,
        # perfectly separable sample (the realistic scale this system
        # calibrates on), unregularized gradient descent never converges -
        # the fitted weight kept growing indefinitely with more
        # iterations (13.8 after 5000, 17.4 after 20000). With the
        # default l2_penalty, weights must instead converge to the same
        # values regardless of how long training runs.
        features = [[0.0], [0.1], [0.2], [0.9], [1.0], [1.1]]
        outcomes = [0, 0, 0, 1, 1, 1]

        short_run = fit_logistic_regression(features, outcomes, learning_rate=0.5, iterations=2000)
        long_run = fit_logistic_regression(features, outcomes, learning_rate=0.5, iterations=20000)

        for w_short, w_long in zip(short_run.weights, long_run.weights):
            self.assertAlmostEqual(w_short, w_long, places=4)

    def test_l2_penalty_zero_reproduces_the_unregularized_blowup(self):
        # confirms l2_penalty is actually wired into the gradient step,
        # not just accepted and ignored
        features = [[0.0], [0.1], [0.2], [0.9], [1.0], [1.1]]
        outcomes = [0, 0, 0, 1, 1, 1]

        short_run = fit_logistic_regression(features, outcomes, learning_rate=0.5, iterations=2000, l2_penalty=0.0)
        long_run = fit_logistic_regression(features, outcomes, learning_rate=0.5, iterations=20000, l2_penalty=0.0)

        # unregularized: the weight keeps growing rather than converging
        self.assertGreater(long_run.weights[1], short_run.weights[1] + 1.0)

    def test_rejects_negative_l2_penalty(self):
        with self.assertRaises(ValueError):
            fit_logistic_regression([[1.0]], [1], l2_penalty=-0.1)

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
