"""Quantitative Machine Learning, Walk-Forward Validation, and Feature Importance Engine."""

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression, RidgeClassifier
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score, roc_auc_score


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
) -> ModelEvaluationReport:
    """Split dataset temporally with an embargo barrier, train model, and evaluate out-of-sample metrics."""
    n = len(df)
    train_end = int(n * train_pct)
    test_start = train_end + embargo_bars

    if test_start >= n:
        raise ValueError("Dataset is too small for the specified train_pct and embargo window.")

    train_df = df.iloc[:train_end]
    test_df = df.iloc[test_start:]

    X_train = train_df[feature_cols]
    y_train = train_df[target_binary_col]

    X_test = test_df[feature_cols]
    y_test = test_df[target_binary_col]
    actual_returns_test = test_df[target_return_col]

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
