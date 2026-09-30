"""Abstract base strategy specification for the quantitative backtesting engine."""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from src.backtesting.models import StrategySignal


class BaseStrategy(ABC):
    """Abstract base class for all systematic trading strategies.

    Guarantees strict point-in-time execution: strategies receive solely
    features and price observations known up to the exact evaluation timestamp.
    """

    def __init__(self, name: str, version: str = "1.0.0", parameters: dict[str, Any] | None = None) -> None:
        self.name = name
        self.version = version
        self.parameters = parameters or {}

    @abstractmethod
    def generate_signals(
        self,
        current_time: datetime,
        universe_snapshot: dict[str, dict[str, Any]],
        current_positions: dict[str, dict[str, Any]],
        cash: float,
        total_equity: float,
    ) -> list[StrategySignal]:
        """Generate point-in-time portfolio rebalance signals.

        Args:
            current_time: Point-in-time evaluation timestamp (UTC).
            universe_snapshot: Dictionary mapping asset_id to its latest feature dictionary
                               (including price, return_30d, ema20_ratio, etc.).
            current_positions: Dictionary of active open positions mapping asset_id to position dict:
                               {'quantity': float, 'entry_price': float, 'current_price': float,
                                'unrealized_pnl': float, 'weight': float}.
            cash: Free available cash in USD.
            total_equity: Total marked-to-market portfolio value.

        Returns:
            List of StrategySignal instances to be executed by the portfolio manager.
        """
        pass
