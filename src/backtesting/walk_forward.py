"""Walk-forward validation framework for parameter stability and anti-overfitting evaluation."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from src.backtesting.engine import BacktestEngine
from src.backtesting.models import BacktestConfig, BacktestResult
from src.backtesting.strategies import get_strategy
from src.utils.logging import get_logger

logger = get_logger("walk_forward")


@dataclass
class WalkForwardWindow:
    """Individual rolling walk-forward evaluation window."""

    window_index: int
    train_start: datetime
    train_end: datetime
    test_start: datetime
    test_end: datetime
    train_result: BacktestResult
    test_result: BacktestResult
    efficiency_ratio: float  # Test CAGR / Train CAGR


class WalkForwardReport(BaseModel):
    """Aggregate walk-forward optimization report across multiple rolling out-of-sample folds."""

    model_config = ConfigDict(protected_namespaces=())

    strategy_name: str
    windows_count: int
    mean_train_cagr: float
    mean_test_cagr: float
    mean_efficiency_ratio: float  # > 0.5 indicates robust out-of-sample persistence
    mean_test_sharpe: float
    mean_test_max_drawdown: float
    is_overfit_suspected: bool
    windows: list[dict[str, Any]] = Field(default_factory=list)


class WalkForwardAnalyzer:
    """Orchestrates rolling in-sample / out-of-sample backtesting across historical timeline."""

    def __init__(
        self,
        base_config: BacktestConfig,
        windows_count: int = 3,
        train_ratio: float = 0.65,
    ) -> None:
        self.base_config = base_config
        self.windows_count = max(2, windows_count)
        self.train_ratio = max(0.4, min(0.8, train_ratio))

    def run_analysis(
        self,
        historical_candles: dict[str, list[dict[str, Any]]],
        historical_features: dict[str, list[dict[str, Any]]] | None = None,
        strategy_parameters: dict[str, Any] | None = None,
    ) -> WalkForwardReport:
        """Run rolling walk-forward validation across chronological folds."""
        start = self.base_config.start_date
        end = self.base_config.end_date
        total_duration = end - start

        logger.info(
            "Starting walk-forward analysis",
            strategy=self.base_config.strategy_name,
            total_days=total_duration.days,
            folds=self.windows_count,
        )

        window_duration = total_duration / self.windows_count
        step_delta = (total_duration - window_duration) / (self.windows_count - 1) if self.windows_count > 1 else timedelta(days=1)

        completed_windows: list[WalkForwardWindow] = []

        for i in range(self.windows_count):
            w_start = start + (step_delta * i)
            w_end = min(end, w_start + window_duration)
            w_span = w_end - w_start

            train_span = w_span * self.train_ratio
            train_start = w_start
            train_end = train_start + train_span
            test_start = train_end
            test_end = w_end

            # Train (In-Sample) Run
            train_config = self.base_config.model_copy(
                update={"start_date": train_start, "end_date": train_end}
            )
            strat_train = get_strategy(self.base_config.strategy_name, parameters=strategy_parameters)
            engine_train = BacktestEngine(train_config, strat_train)
            train_res = engine_train.run(
                historical_candles=historical_candles,
                historical_features=historical_features,
            )

            # Test (Out-of-Sample) Run
            test_config = self.base_config.model_copy(
                update={"start_date": test_start, "end_date": test_end}
            )
            strat_test = get_strategy(self.base_config.strategy_name, parameters=strategy_parameters)
            engine_test = BacktestEngine(test_config, strat_test)
            test_res = engine_test.run(
                historical_candles=historical_candles,
                historical_features=historical_features,
            )

            train_cagr = train_res.metrics.get("cagr", 0.0)
            test_cagr = test_res.metrics.get("cagr", 0.0)

            # Efficiency Ratio = Test CAGR / Train CAGR
            if train_cagr > 0.0:
                eff = test_cagr / train_cagr
            else:
                eff = 1.0 if test_cagr >= 0 else 0.0

            completed_windows.append(
                WalkForwardWindow(
                    window_index=i + 1,
                    train_start=train_start,
                    train_end=train_end,
                    test_start=test_start,
                    test_end=test_end,
                    train_result=train_res,
                    test_result=test_res,
                    efficiency_ratio=round(eff, 3),
                )
            )

        # Aggregate Statistics
        train_cagrs = [w.train_result.metrics.get("cagr", 0.0) for w in completed_windows]
        test_cagrs = [w.test_result.metrics.get("cagr", 0.0) for w in completed_windows]
        eff_ratios = [w.efficiency_ratio for w in completed_windows]
        test_sharpes = [w.test_result.metrics.get("sharpe_ratio", 0.0) for w in completed_windows]
        test_dds = [w.test_result.metrics.get("max_drawdown_pct", 0.0) for w in completed_windows]

        mean_train = sum(train_cagrs) / len(train_cagrs) if train_cagrs else 0.0
        mean_test = sum(test_cagrs) / len(test_cagrs) if test_cagrs else 0.0
        mean_eff = sum(eff_ratios) / len(eff_ratios) if eff_ratios else 0.0
        mean_sharpe = sum(test_sharpes) / len(test_sharpes) if test_sharpes else 0.0
        mean_dd = sum(test_dds) / len(test_dds) if test_dds else 0.0

        # Suspect overfitting if out-of-sample efficiency is below 0.35
        is_overfit = (mean_eff < 0.35) or (mean_test < 0.0 and mean_train > 20.0)

        serialized_windows = [
            {
                "window": w.window_index,
                "train_dates": f"{w.train_start.date()} to {w.train_end.date()}",
                "test_dates": f"{w.test_start.date()} to {w.test_end.date()}",
                "train_cagr": w.train_result.metrics.get("cagr", 0.0),
                "test_cagr": w.test_result.metrics.get("cagr", 0.0),
                "efficiency_ratio": w.efficiency_ratio,
                "test_sharpe": w.test_result.metrics.get("sharpe_ratio", 0.0),
                "test_max_drawdown": w.test_result.metrics.get("max_drawdown_pct", 0.0),
            }
            for w in completed_windows
        ]

        return WalkForwardReport(
            strategy_name=self.base_config.strategy_name,
            windows_count=len(completed_windows),
            mean_train_cagr=round(mean_train, 2),
            mean_test_cagr=round(mean_test, 2),
            mean_efficiency_ratio=round(mean_eff, 3),
            mean_test_sharpe=round(mean_sharpe, 2),
            mean_test_max_drawdown=round(mean_dd, 2),
            is_overfit_suspected=is_overfit,
            windows=serialized_windows,
        )
