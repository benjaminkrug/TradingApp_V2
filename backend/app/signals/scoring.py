"""Signal score calibration — ROADMAP.md Abschnitt 16.

Weights must be *calibrated* from historical, OOS-validated trade
outcomes, not hand-picked. An earlier draft of this roadmap proposed a
fixed point table (Market Regime 20, Trend 15, Momentum 15, ...) that
looked objective but was really just guessed constants — exactly the kind
of overfitting-by-hand this module exists to avoid. See ROADMAP.md
Abschnitt 12 for that correction.

Pure-Python logistic regression (batch gradient descent) — no numpy or
scikit-learn available in this sandbox (PyPI is blocked, see
PHASE2_NOTES.md). The feature counts and trade sample sizes this system
deals with make a hand-rolled implementation entirely adequate; this is
not meant to become a general ML library.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


def _sigmoid(z: float) -> float:
    # numerically stable form - avoids overflow in math.exp for large |z|
    if z >= 0:
        return 1.0 / (1.0 + math.exp(-z))
    ez = math.exp(z)
    return ez / (1.0 + ez)


@dataclass(frozen=True)
class CalibratedModel:
    weights: list[float]  # weights[0] is the bias term, weights[1:] align with feature order

    def predict_probability(self, features: list[float]) -> float:
        if len(features) != len(self.weights) - 1:
            raise ValueError(f"expected {len(self.weights) - 1} features, got {len(features)}")
        z = self.weights[0] + sum(w * f for w, f in zip(self.weights[1:], features))
        return _sigmoid(z)


def fit_logistic_regression(
    features: list[list[float]],
    outcomes: list[int],
    learning_rate: float = 0.1,
    iterations: int = 2000,
) -> CalibratedModel:
    """`outcomes` are 0 (losing trade) or 1 (winning trade), same order as
    `features`. Fits by full-batch gradient descent on log loss."""
    if len(features) != len(outcomes):
        raise ValueError("features and outcomes must be the same length")
    if not features:
        raise ValueError("cannot fit a model on zero examples")
    if any(o not in (0, 1) for o in outcomes):
        raise ValueError("outcomes must be 0 or 1")

    n_features = len(features[0])
    if any(len(f) != n_features for f in features):
        raise ValueError("all feature vectors must have the same length")

    weights = [0.0] * (n_features + 1)
    n = len(features)

    for _ in range(iterations):
        gradients = [0.0] * (n_features + 1)
        for x, y in zip(features, outcomes):
            z = weights[0] + sum(w * f for w, f in zip(weights[1:], x))
            error = _sigmoid(z) - y
            gradients[0] += error
            for j, f in enumerate(x):
                gradients[j + 1] += error * f
        for j in range(len(weights)):
            weights[j] -= learning_rate * gradients[j] / n

    return CalibratedModel(weights=weights)
