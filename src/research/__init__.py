"""Quantitative research and machine learning framework namespace."""

from src.research.ml_models import (
    ModelEvaluationReport,
    QuantitativeMLModel,
    compute_information_coefficient,
    create_forward_labels,
    walk_forward_train_evaluate,
)

__all__ = [
    "ModelEvaluationReport",
    "QuantitativeMLModel",
    "compute_information_coefficient",
    "create_forward_labels",
    "walk_forward_train_evaluate",
]
