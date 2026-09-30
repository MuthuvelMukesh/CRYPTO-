"""Quantitative systematic trading strategies for backtesting and paper trading."""

from src.backtesting.strategies.base import BaseStrategy
from src.backtesting.strategies.factor_rank import FactorRankStrategy
from src.backtesting.strategies.momentum import MomentumBreakoutStrategy
from src.backtesting.strategies.relative_strength import RelativeStrengthRotationStrategy
from src.backtesting.strategies.trend_regime import TrendRegimeStrategy

STRATEGY_REGISTRY: dict[str, type[BaseStrategy]] = {
    "MomentumBreakout": MomentumBreakoutStrategy,
    "TrendRegimeFilter": TrendRegimeStrategy,
    "RelativeStrengthRotation": RelativeStrengthRotationStrategy,
    "FactorRankModel": FactorRankStrategy,
}


def get_strategy(name: str, parameters: dict | None = None) -> BaseStrategy:
    """Instantiate a strategy by name from the registry."""
    strategy_cls = STRATEGY_REGISTRY.get(name)
    if not strategy_cls:
        available = ", ".join(STRATEGY_REGISTRY.keys())
        raise ValueError(f"Unknown strategy '{name}'. Available strategies: {available}")
    return strategy_cls(parameters=parameters)


__all__ = [
    "BaseStrategy",
    "FactorRankStrategy",
    "MomentumBreakoutStrategy",
    "RelativeStrengthRotationStrategy",
    "STRATEGY_REGISTRY",
    "TrendRegimeStrategy",
    "get_strategy",
]
