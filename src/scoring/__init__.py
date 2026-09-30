"""Scoring package exports."""

from src.scoring.altcoin import AltcoinScorer
from src.scoring.base import BaseScorer, FactorContribution, PenaltyDeduction, ScoreCard
from src.scoring.core import CoreScorer
from src.scoring.engine import get_scorer_for_asset, score_single_asset, score_universe
from src.scoring.meme import MemeScorer
from src.scoring.smallcap import SmallCapScorer

__all__ = [
    "AltcoinScorer",
    "BaseScorer",
    "CoreScorer",
    "FactorContribution",
    "MemeScorer",
    "PenaltyDeduction",
    "ScoreCard",
    "SmallCapScorer",
    "get_scorer_for_asset",
    "score_single_asset",
    "score_universe",
]
