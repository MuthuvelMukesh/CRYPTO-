"""Quantitative Machine Learning, Walk-Forward Validation, and Feature Importance Engine."""

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
import pandas as pd

try:
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.linear_model import LogisticRegression, RidgeClassifier
    from sklearn.metrics import (
        accuracy_score,
        f1_score,
        precision_score,
        recall_score,
        roc_auc_score,
    )
except ImportError:
    RandomForestClassifier = None  # type: ignore[assignment,misc]
    LogisticRegression = None  # type: ignore[assignment,misc]
    RidgeClassifier = None  # type: ignore[assignment,misc]
    accuracy_score = None  # type: ignore[assignment]
    f1_score = None  # type: ignore[assignment]
    precision_score = None  # type: ignore[assignment]
    recall_score = None  # type: ignore[assignment]
    roc_auc_score = None  # type: ignore[assignment]


def _require_sklearn() -> None:
    """Ensure scikit-learn is installed for research ML models."""
    try:
        import sklearn  # noqa: F401
    except ImportError as e:
        raise ImportError(
            "scikit-learn is required for research ML models. "
            "Install it via: pip install 'crypto-intelligence[research]' or pip install scikit-learn"
        ) from e


@dataclass
class ModelEvaluationReport:
    """Quantitative performance report for a machine learning model."""

    accuracy: float
    precision: float
    recall: float
    f1: float
    roc_auc: float
    information_coefficient: float
    rank_ic: float
    feature_importances: dict[str, float]
    n_samples_train: int
    n_samples_test: int


class QuantitativeMLModel:
    """Trainable quantitative machine learning model for asset return prediction."""

    def __init__(
        self,
        model_type: str = "logistic_regression",
        penalty_c: float = 1.0,
        random_state: int = 42,
    ) -> None:
        _require_sklearn()
        self.model_type = model_type
        self.random_state = random_state

        if model_type == "random_forest":
            self._model = RandomForestClassifier(
                n_estimators=50,
                max_depth=5,
                random_state=random_state,
                n_jobs=-1,
            )
        elif model_type == "ridge":
            self._model = RidgeClassifier(alpha=1.0 / penalty_c, random_state=random_state)
        else:
            self._model = LogisticRegression(
                C=penalty_c,
                max_iter=1000,
                random_state=random_state,
            )

        self.feature_names: list[str] = []
        self.is_fitted: bool = False

    def fit(self, X: pd.DataFrame | np.ndarray, y: pd.Series | np.ndarray, feature_names: list[str] | None = None) -> "QuantitativeMLModel":
        """Fit model on feature matrix and target labels."""
        if isinstance(X, pd.DataFrame):
            self.feature_names = list(X.columns)
            X_arr = X.to_numpy()
        else:
            self.feature_names = feature_names or [f"f_{i}" for i in range(X.shape[1])]
            X_arr = np.asarray(X)

        y_arr = np.asarray(y)

        # Handle NaNs
        X_clean = np.nan_to_num(X_arr, nan=0.0, posinf=0.0, neginf=0.0)
        self._model.fit(X_clean, y_arr)
        self.is_fitted = True
        return self

    def predict(self, X: pd.DataFrame | np.ndarray) -> np.ndarray:
        """Predict binary direction classes (0 or 1)."""
        if not self.is_fitted:
            raise ValueError("Model is not fitted yet.")
        X_arr = X.to_numpy() if isinstance(X, pd.DataFrame) else np.asarray(X)
        X_clean = np.nan_to_num(X_arr, nan=0.0, posinf=0.0, neginf=0.0)
        return self._model.predict(X_clean)

    def predict_proba(self, X: pd.DataFrame | np.ndarray) -> np.ndarray:
        """Predict class probabilities."""
        if not self.is_fitted:
            raise ValueError("Model is not fitted yet.")
        X_arr = X.to_numpy() if isinstance(X, pd.DataFrame) else np.asarray(X)
        X_clean = np.nan_to_num(X_arr, nan=0.0, posinf=0.0, neginf=0.0)

        if hasattr(self._model, "predict_proba"):
            return self._model.predict_proba(X_clean)
        elif hasattr(self._model, "decision_function"):
            df = self._model.decision_function(X_clean)
            # Sigmoid approximation for Ridge
            prob_1 = 1.0 / (1.0 + np.exp(-df))
            return np.vstack([1.0 - prob_1, prob_1]).T
        else:
            preds = self.predict(X_clean)
            return np.vstack([1.0 - preds, preds]).T

    def get_feature_importances(self) -> dict[str, float]:
        """Extract and normalize feature importance weights."""
        if not self.is_fitted:
            return {}

        if hasattr(self._model, "feature_importances_"):
            raw_weights = np.abs(self._model.feature_importances_)
        elif hasattr(self._model, "coef_"):
            raw_weights = np.abs(self._model.coef_[0])
        else:
            raw_weights = np.ones(len(self.feature_names))

        total = np.sum(raw_weights)
        norm_weights = raw_weights / (total if total > 0 else 1.0)
        return {
            name: round(float(w), 4)
            for name, w in zip(self.feature_names, norm_weights, strict=False)
        }


def compute_information_coefficient(
    predictions: np.ndarray | pd.Series,
    actual_returns: np.ndarray | pd.Series,
) -> tuple[float, float]:
    """Compute Pearson IC and Spearman Rank IC between predictions and actual forward returns."""
    p = np.asarray(predictions, dtype=np.float64)
    a = np.asarray(actual_returns, dtype=np.float64)

    # Filter out NaNs
    valid = ~(np.isnan(p) | np.isnan(a))
    if np.sum(valid) < 5:
        return 0.0, 0.0

    p_clean = p[valid]
    a_clean = a[valid]

    # Pearson IC
    std_p = np.std(p_clean)
    std_a = np.std(a_clean)
    if std_p == 0.0 or std_a == 0.0:
        return 0.0, 0.0

    pearson_ic = float(np.corrcoef(p_clean, a_clean)[0, 1])

    # Spearman Rank IC
    rank_p = pd.Series(p_clean).rank().to_numpy()
    rank_a = pd.Series(a_clean).rank().to_numpy()
    rank_ic = float(np.corrcoef(rank_p, rank_a)[0, 1])

    return round(pearson_ic, 4), round(rank_ic, 4)


def create_forward_labels(
    df: pd.DataFrame,
    horizon_bars: int = 24,
    price_col: str = "close",
    target_col: str = "forward_return",
) -> pd.DataFrame:
    """Generate forward return and binary outperformance classification targets."""
    df_out = df.copy()
    forward_price = df_out[price_col].shift(-horizon_bars)
    df_out[target_col] = (forward_price / df_out[price_col]) - 1.0
    df_out["target_direction"] = (df_out[target_col] > 0.0).astype(int)
    return df_out.dropna(subset=[target_col])


def walk_forward_train_evaluate(
    df: pd.DataFrame,
    feature_cols: list[str],
    target_return_col: str = "forward_return",
    target_binary_col: str = "target_direction",
    train_pct: float = 0.70,
    embargo_bars: int = 24,
    model_type: str = "logistic_regression",
    scaler_type: str | None = None,
) -> ModelEvaluationReport:
    """Split dataset temporally with an embargo barrier, train model, and evaluate out-of-sample metrics.

    Enforces research integrity:
    1. Asserts target variables are NOT in feature matrix.
    2. Scalers are fit strictly on in-sample data and applied to out-of-sample data.
    """
    _require_sklearn()

    # Research integrity audit: target must never leak into features
    assert target_return_col not in feature_cols, (
        f"DATA LEAKAGE DETECTED: Target return column '{target_return_col}' found in feature matrix!"
    )
    assert target_binary_col not in feature_cols, (
        f"DATA LEAKAGE DETECTED: Target binary column '{target_binary_col}' found in feature matrix!"
    )

    n = len(df)
    train_end = int(n * train_pct)
    test_start = train_end + embargo_bars

    if test_start >= n:
        raise ValueError("Dataset is too small for the specified train_pct and embargo window.")

    train_df = df.iloc[:train_end]
    test_df = df.iloc[test_start:]

    X_train = train_df[feature_cols].copy()
    y_train = train_df[target_binary_col]

    X_test = test_df[feature_cols].copy()
    y_test = test_df[target_binary_col]
    actual_returns_test = test_df[target_return_col]

    # In-sample scaler separation
    if scaler_type == "standard":
        from sklearn.preprocessing import StandardScaler
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)
        X_train = pd.DataFrame(X_train_scaled, columns=feature_cols, index=train_df.index)
        X_test = pd.DataFrame(X_test_scaled, columns=feature_cols, index=test_df.index)
    elif scaler_type == "minmax":
        from sklearn.preprocessing import MinMaxScaler
        scaler = MinMaxScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)
        X_train = pd.DataFrame(X_train_scaled, columns=feature_cols, index=train_df.index)
        X_test = pd.DataFrame(X_test_scaled, columns=feature_cols, index=test_df.index)

    # Fit model
    model = QuantitativeMLModel(model_type=model_type)
    model.fit(X_train, y_train)

    # Predict
    preds = model.predict(X_test)
    probs = model.predict_proba(X_test)[:, 1]

    # Metrics
    acc = float(accuracy_score(y_test, preds))
    prec = float(precision_score(y_test, preds, zero_division=0))
    rec = float(recall_score(y_test, preds, zero_division=0))
    f1 = float(f1_score(y_test, preds, zero_division=0))

    try:
        auc = float(roc_auc_score(y_test, probs))
    except Exception:
        auc = 0.50

    ic, rank_ic = compute_information_coefficient(probs, actual_returns_test)

    return ModelEvaluationReport(
        accuracy=round(acc, 4),
        precision=round(prec, 4),
        recall=round(rec, 4),
        f1=round(f1, 4),
        roc_auc=round(auc, 4),
        information_coefficient=ic,
        rank_ic=rank_ic,
        feature_importances=model.get_feature_importances(),
        n_samples_train=len(train_df),
        n_samples_test=len(test_df),
    )


@dataclass
class ProductionGateResult:
    """Result of evaluating whether an experimental ML model passes the production ranking gate."""

    passed: bool
    model_rank_ic: float
    baseline_rank_ic: float
    ic_delta: float
    p_value: float
    message: str
    evaluated_at: str


def evaluate_production_gate(
    model_predictions: Sequence[float],
    baseline_predictions: Sequence[float],
    actual_returns: Sequence[float],
    min_ic_improvement: float = 0.02,
) -> ProductionGateResult:
    """Evaluate whether an experimental ML model score is permitted to feed production ranking.

    Strict Invariant: No ML model feeds production ranking until it beats the baseline out-of-sample
    in the attribution report by at least min_ic_improvement with a positive rank correlation.
    """

    from src.research.attribution import compute_spearman_correlation
    from src.utils.time import utc_now

    m_preds = np.asarray(model_predictions, dtype=np.float64)
    b_preds = np.asarray(baseline_predictions, dtype=np.float64)
    rets = np.asarray(actual_returns, dtype=np.float64)

    mask = (~np.isnan(m_preds)) & (~np.isnan(b_preds)) & (~np.isnan(rets))
    m_clean = m_preds[mask]
    b_clean = b_preds[mask]
    rets_clean = rets[mask]

    if len(m_clean) < 10:
        return ProductionGateResult(
            passed=False,
            model_rank_ic=0.0,
            baseline_rank_ic=0.0,
            ic_delta=0.0,
            p_value=1.0,
            message="Insufficient out-of-sample data points to evaluate production gate (N < 10)",
            evaluated_at=utc_now().isoformat(),
        )

    model_ic, _, model_p = compute_spearman_correlation(m_clean, rets_clean)
    baseline_ic, _, _ = compute_spearman_correlation(b_clean, rets_clean)
    delta = model_ic - baseline_ic

    passed = bool(model_ic > 0 and delta >= min_ic_improvement and model_p < 0.05)
    if passed:
        msg = (
            f"Production Gate PASSED: Model OOS Rank IC ({model_ic:+.3f}) beats baseline ({baseline_ic:+.3f}) "
            f"by {delta:+.3f} (threshold >= {min_ic_improvement:+.3f}, p={model_p:.3f})"
        )
    else:
        msg = (
            f"Production Gate REJECTED: Model OOS Rank IC ({model_ic:+.3f}) failed to demonstrate required "
            f"statistically significant superiority over baseline ({baseline_ic:+.3f}, delta={delta:+.3f}, p={model_p:.3f})"
        )

    return ProductionGateResult(
        passed=passed,
        model_rank_ic=round(model_ic, 4),
        baseline_rank_ic=round(baseline_ic, 4),
        ic_delta=round(delta, 4),
        p_value=round(model_p, 4),
        message=msg,
        evaluated_at=utc_now().isoformat(),
    )
