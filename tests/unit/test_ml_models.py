"""Unit tests for quantitative machine learning models and walk-forward evaluations."""

import numpy as np
import pandas as pd

from src.research.ml_models import (
    QuantitativeMLModel,
    compute_information_coefficient,
    create_forward_labels,
    walk_forward_train_evaluate,
)


def test_quantitative_ml_model_train_and_predict() -> None:
    np.random.seed(42)
    n = 200
    X = pd.DataFrame({
        "momentum_1d": np.random.randn(n),
        "relative_strength": np.random.randn(n),
        "rvol_20": np.random.exponential(1.5, n),
    })
    # Target correlated with features
    y = ((X["momentum_1d"] * 0.6 + X["relative_strength"] * 0.4 + np.random.randn(n) * 0.5) > 0).astype(int)

    model = QuantitativeMLModel(model_type="logistic_regression")
    model.fit(X, y)

    assert model.is_fitted is True
    preds = model.predict(X)
    assert len(preds) == n
    assert set(np.unique(preds)).issubset({0, 1})

    probs = model.predict_proba(X)
    assert probs.shape == (n, 2)
    assert np.allclose(probs[:, 0] + probs[:, 1], 1.0)

    importances = model.get_feature_importances()
    assert "momentum_1d" in importances
    assert "relative_strength" in importances
    assert "rvol_20" in importances
    assert np.isclose(sum(importances.values()), 1.0)


def test_compute_information_coefficient() -> None:
    np.random.seed(42)
    actual = np.random.randn(100)
    # Perfect positive correlation
    perfect_pred = actual * 2.0
    p_ic, rank_ic = compute_information_coefficient(perfect_pred, actual)
    assert p_ic > 0.99
    assert rank_ic > 0.99

    # Uncorrelated noise
    noise_pred = np.random.randn(100)
    p_noise, rank_noise = compute_information_coefficient(noise_pred, actual)
    assert abs(p_noise) < 0.3
    assert abs(rank_noise) < 0.3


def test_create_forward_labels() -> None:
    prices = [100.0, 102.0, 105.0, 103.0, 110.0, 115.0]
    df = pd.DataFrame({"close": prices})
    labeled = create_forward_labels(df, horizon_bars=2, price_col="close")

    assert "forward_return" in labeled.columns
    assert "target_direction" in labeled.columns
    assert len(labeled) == len(prices) - 2
    # At index 0, price is 100, price at +2 is 105 -> return is 0.05
    assert np.isclose(labeled.iloc[0]["forward_return"], 0.05)
    assert labeled.iloc[0]["target_direction"] == 1


def test_walk_forward_train_evaluate() -> None:
    np.random.seed(42)
    n = 300
    df = pd.DataFrame({
        "close": 100.0 * np.exp(np.cumsum(np.random.randn(n) * 0.01)),
        "feat_mom": np.random.randn(n),
        "feat_rs": np.random.randn(n),
    })
    labeled = create_forward_labels(df, horizon_bars=12, price_col="close")

    report = walk_forward_train_evaluate(
        labeled,
        feature_cols=["feat_mom", "feat_rs"],
        target_return_col="forward_return",
        target_binary_col="target_direction",
        train_pct=0.6,
        embargo_bars=12,
        model_type="logistic_regression",
    )

    assert report.n_samples_train > 0
    assert report.n_samples_test > 0
    assert 0.0 <= report.accuracy <= 1.0
    assert -1.0 <= report.rank_ic <= 1.0
    assert "feat_mom" in report.feature_importances
