"""Quantitative research and machine learning framework namespace."""

from src.research.ml_models import (
    ModelEvaluationReport,
    QuantitativeMLModel,
    compute_information_coefficient,
    create_forward_labels,
    walk_forward_train_evaluate,
)
from src.research.statistics import (
    compute_deflated_sharpe_ratio,
    compute_expected_max_sharpe,
    compute_probabilistic_sharpe_ratio,
)

__all__ = [
    "ModelEvaluationReport",
    "QuantitativeMLModel",
    "compute_deflated_sharpe_ratio",
    "compute_expected_max_sharpe",
    "compute_information_coefficient",
    "compute_probabilistic_sharpe_ratio",
    "create_forward_labels",
    "walk_forward_train_evaluate",
]

