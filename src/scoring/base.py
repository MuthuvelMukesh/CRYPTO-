"""Base multi-factor scoring classes, schemas, and explainability models."""

from abc import ABC, abstractmethod
from typing import Any

import numpy as np
from pydantic import BaseModel, ConfigDict, Field


class FactorContribution(BaseModel):
    """Individual factor score and its weighted contribution to the opportunity score."""
    name: str
    score: float = Field(..., ge=0.0, le=100.0, description="Raw factor score from 0 to 100")
    weight: float = Field(..., ge=0.0, le=1.0, description="Factor weight in model")
    contribution: float = Field(..., description="score * weight")


class PenaltyDeduction(BaseModel):
    """Transparent risk penalty deducted from the gross opportunity score."""
    flag: str
    deduction: float  # e.g., -15.0
    reason: str


class ScoreCard(BaseModel):
    """Comprehensive, explainable multi-factor score report for an asset."""
    model_config = ConfigDict(protected_namespaces=())

    asset_id: str
    model_type: str  # CORE, ALTCOIN, SMALL_CAP, MEME
    opportunity_score: float = Field(..., ge=0.0, le=100.0)
    quality_score: float = Field(..., ge=0.0, le=100.0)
    risk_score: float = Field(..., ge=0.0, le=100.0)
    trend_score: float = Field(..., ge=0.0, le=100.0)
    momentum_score: float = Field(..., ge=0.0, le=100.0)
    relative_strength_score: float = Field(..., ge=0.0, le=100.0)
    liquidity_score: float = Field(..., ge=0.0, le=100.0)
    volume_score: float = Field(..., ge=0.0, le=100.0)
    components: dict[str, FactorContribution]
    penalties: list[PenaltyDeduction] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    explainability_summary: str = ""

    def generate_summary(self) -> str:
        """Generate human-readable explainability text."""
        parts = [f"Opportunity Score: {self.opportunity_score:.1f}/100 [{self.model_type}]"]
        contrib_strs = []
        for _name, comp in self.components.items():
            contrib_strs.append(f"{comp.name.title()} +{comp.contribution:.1f}pts ({comp.score:.0f}/100)")
        parts.append("Factors: " + ", ".join(contrib_strs))

        if self.penalties:
            penalty_strs = [f"{p.flag} ({p.deduction:+.1f}pts: {p.reason})" for p in self.penalties]
            parts.append("Risk Adjustments: " + ", ".join(penalty_strs))
        else:
            parts.append("Risk Adjustments: None")

        return " | ".join(parts)


def clamp(val: float, min_val: float = 0.0, max_val: float = 100.0) -> float:
    """Clamp numeric value to bounded range."""
    return float(max(min_val, min(max_val, val)))


def normalize_linear(
    val: float | None,
    min_bound: float,
    max_bound: float,
    default: float = 50.0,
    inverted: bool = False,
) -> float:
    """
    Map raw metric into a normalized 0 to 100 score.
    If value is None, returns neutral default (50.0).
    """
    if val is None or np.isnan(val):
        return default

    if max_bound == min_bound:
        return 50.0

    norm = (val - min_bound) / (max_bound - min_bound)
    norm = max(0.0, min(1.0, norm))

    if inverted:
        norm = 1.0 - norm

    return float(norm * 100.0)


def normalize_ratio(
    ratio: float | None,
    neutral_val: float = 1.0,
    half_scale: float = 0.15,
    default: float = 50.0,
) -> float:
    """
    Convert price/indicator ratio into 0-100 score centered at neutral_val.
    e.g. Price/EMA20 = 1.0 -> 50.0; 1.15 -> 75.0; 0.85 -> 25.0
    """
    if ratio is None or np.isnan(ratio):
        return default

    diff = ratio - neutral_val
    scaled = 50.0 + (diff / half_scale) * 25.0
    return clamp(scaled)


class BaseScorer(ABC):
    """Abstract base class for asset-class specific multi-factor scoring models."""

    @property
    @abstractmethod
    def model_type(self) -> str:
        """Model identifier."""
        pass

    @abstractmethod
    def calculate_score(
        self,
        asset_id: str,
        features: Any,
        tokenomics: Any | None = None,
        onchain: Any | None = None,
        holder_metrics: Any | None = None,
        weights: dict[str, float] | None = None,
    ) -> ScoreCard:
        """Compute transparent multi-factor scorecard for asset."""
        pass
