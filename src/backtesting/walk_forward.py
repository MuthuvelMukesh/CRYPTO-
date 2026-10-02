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
    selected_parameters: dict[str, Any]
    train_result: BacktestResult
    test_result: BacktestResult
    cagr_efficiency: float  # Test CAGR / Train CAGR
    sharpe_efficiency: float  # Test Sharpe / Train Sharpe
    drawdown_ratio: float  # Test Max Drawdown / Train Max Drawdown
    efficiency_ratio: float  # Alias for cagr_efficiency for backwards-compatibility


class WalkForwardReport(BaseModel):
    """Aggregate walk-forward optimization report across multiple rolling out-of-sample folds."""

    model_config = ConfigDict(protected_namespaces=())

    strategy_name: str
    windows_count: int
    mean_train_cagr: float
    mean_test_cagr: float
    mean_efficiency_ratio: float  # Backwards compatibility alias
    mean_cagr_efficiency: float
    mean_train_sharpe: float
    mean_test_sharpe: float
    mean_sharpe_efficiency: float
    mean_train_max_drawdown: float
    mean_test_max_drawdown: float
    mean_drawdown_ratio: float
    is_overfit_suspected: bool
    windows: list[dict[str, Any]] = Field(default_factory=list)


class WalkForwardAnalyzer:
    """Orchestrates rolling in-sample / out-of-sample backtesting across historical timeline."""

    def __init__(
        self,
        base_config: BacktestConfig,
        windows_count: int = 3,
        train_ratio: float = 0.65,
        parameter_grid: list[dict[str, Any]] | None = None,
        optimization_metric: str = "sharpe_ratio",
    ) -> None:
        self.base_config = base_config
        self.windows_count = max(2, windows_count)
        self.train_ratio = max(0.4, min(0.8, train_ratio))
        self.parameter_grid = parameter_grid
        self.optimization_metric = optimization_metric

    def run_analysis(
        self,
        historical_candles: dict[str, list[dict[str, Any]]],
        historical_features: dict[str, list[dict[str, Any]]] | None = None,
        strategy_parameters: dict[str, Any] | None = None,
        delisted_dates: dict[str, datetime] | None = None,
    ) -> WalkForwardReport:
        """Run rolling walk-forward validation across chronological folds with in-sample parameter search."""
        start = self.base_config.start_date
        end = self.base_config.end_date
        total_duration = end - start

        logger.info(
            "Starting walk-forward analysis",
            strategy=self.base_config.strategy_name,
            total_days=total_duration.days,
            folds=self.windows_count,
            has_param_grid=bool(self.parameter_grid),
        )

        window_duration = total_duration / self.windows_count
        step_delta = (
            (total_duration - window_duration) / (self.windows_count - 1)
            if self.windows_count > 1
            else timedelta(days=1)
        )

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

            # In-Sample Parameter Search
            best_params: dict[str, Any] = strategy_parameters or self.base_config.parameters or {}
            best_train_res: BacktestResult | None = None

            if self.parameter_grid:
                best_score = float("-inf")
                for candidate_params in self.parameter_grid:
                    train_cfg = self.base_config.model_copy(
                        update={"start_date": train_start, "end_date": train_end, "parameters": candidate_params}
                    )
                    strat_candidate = get_strategy(self.base_config.strategy_name, parameters=candidate_params)
                    candidate_engine = BacktestEngine(train_cfg, strat_candidate)
                    cand_res = candidate_engine.run(
                        historical_candles=historical_candles,
                        historical_features=historical_features,
                        delisted_dates=delisted_dates,
                    )
                    score = float(cand_res.metrics.get(self.optimization_metric, 0.0))
                    if score > best_score or best_train_res is None:
                        best_score = score
                        best_params = candidate_params
                        best_train_res = cand_res
            else:
                train_config = self.base_config.model_copy(
                    update={"start_date": train_start, "end_date": train_end, "parameters": best_params}
                )
                strat_train = get_strategy(self.base_config.strategy_name, parameters=best_params)
                engine_train = BacktestEngine(train_config, strat_train)
                best_train_res = engine_train.run(
                    historical_candles=historical_candles,
                    historical_features=historical_features,
                    delisted_dates=delisted_dates,
                )

            assert best_train_res is not None

            # Test (Out-of-Sample) Run with the selected parameters
            test_config = self.base_config.model_copy(
                update={"start_date": test_start, "end_date": test_end, "parameters": best_params}
            )
            strat_test = get_strategy(self.base_config.strategy_name, parameters=best_params)
            engine_test = BacktestEngine(test_config, strat_test)
            test_res = engine_test.run(
                historical_candles=historical_candles,
                historical_features=historical_features,
                delisted_dates=delisted_dates,
            )

            train_cagr = best_train_res.metrics.get("cagr", 0.0)
            test_cagr = test_res.metrics.get("cagr", 0.0)
            train_sharpe = best_train_res.metrics.get("sharpe_ratio", 0.0)
            test_sharpe = test_res.metrics.get("sharpe_ratio", 0.0)
            train_dd = best_train_res.metrics.get("max_drawdown_pct", 0.0)
            test_dd = test_res.metrics.get("max_drawdown_pct", 0.0)

            # Efficiency ratios
            if train_cagr > 0.0:
                cagr_eff = test_cagr / train_cagr
            else:
                cagr_eff = 1.0 if test_cagr >= 0 else 0.0

            if train_sharpe > 0.0:
                sharpe_eff = test_sharpe / train_sharpe
            else:
                sharpe_eff = 1.0 if test_sharpe >= 0 else 0.0

            dd_ratio = (test_dd / train_dd) if train_dd > 0 else (1.0 if test_dd == 0 else 2.0)

            completed_windows.append(
                WalkForwardWindow(
                    window_index=i + 1,
                    train_start=train_start,
                    train_end=train_end,
                    test_start=test_start,
                    test_end=test_end,
                    selected_parameters=best_params,
                    train_result=best_train_res,
                    test_result=test_res,
                    cagr_efficiency=round(cagr_eff, 3),
                    sharpe_efficiency=round(sharpe_eff, 3),
                    drawdown_ratio=round(dd_ratio, 3),
                    efficiency_ratio=round(cagr_eff, 3),
                )
            )

        # Aggregate Statistics
        train_cagrs = [w.train_result.metrics.get("cagr", 0.0) for w in completed_windows]
        test_cagrs = [w.test_result.metrics.get("cagr", 0.0) for w in completed_windows]
        train_sharpes = [w.train_result.metrics.get("sharpe_ratio", 0.0) for w in completed_windows]
        test_sharpes = [w.test_result.metrics.get("sharpe_ratio", 0.0) for w in completed_windows]
        train_dds = [w.train_result.metrics.get("max_drawdown_pct", 0.0) for w in completed_windows]
        test_dds = [w.test_result.metrics.get("max_drawdown_pct", 0.0) for w in completed_windows]

        cagr_effs = [w.cagr_efficiency for w in completed_windows]
        sharpe_effs = [w.sharpe_efficiency for w in completed_windows]
        dd_ratios = [w.drawdown_ratio for w in completed_windows]

        mean_train_cagr = sum(train_cagrs) / len(train_cagrs) if train_cagrs else 0.0
        mean_test_cagr = sum(test_cagrs) / len(test_cagrs) if test_cagrs else 0.0
        mean_cagr_eff = sum(cagr_effs) / len(cagr_effs) if cagr_effs else 0.0

        mean_train_sharpe = sum(train_sharpes) / len(train_sharpes) if train_sharpes else 0.0
        mean_test_sharpe = sum(test_sharpes) / len(test_sharpes) if test_sharpes else 0.0
        mean_sharpe_eff = sum(sharpe_effs) / len(sharpe_effs) if sharpe_effs else 0.0

        mean_train_dd = sum(train_dds) / len(train_dds) if train_dds else 0.0
        mean_test_dd = sum(test_dds) / len(test_dds) if test_dds else 0.0
        mean_dd_ratio = sum(dd_ratios) / len(dd_ratios) if dd_ratios else 0.0

        # Suspect overfitting if out-of-sample CAGR or Sharpe efficiency drops below 0.35, or returns invert
        is_overfit = (
            (mean_cagr_eff < 0.35)
            or (mean_sharpe_eff < 0.35)
            or (mean_test_cagr < 0.0 and mean_train_cagr > 15.0)
        )

        serialized_windows = [
            {
                "window": w.window_index,
                "train_dates": f"{w.train_start.date()} to {w.train_end.date()}",
                "test_dates": f"{w.test_start.date()} to {w.test_end.date()}",
                "selected_parameters": w.selected_parameters,
                "train_cagr": w.train_result.metrics.get("cagr", 0.0),
                "test_cagr": w.test_result.metrics.get("cagr", 0.0),
                "cagr_efficiency": w.cagr_efficiency,
                "efficiency_ratio": w.efficiency_ratio,
                "train_sharpe": w.train_result.metrics.get("sharpe_ratio", 0.0),
                "test_sharpe": w.test_result.metrics.get("sharpe_ratio", 0.0),
                "sharpe_efficiency": w.sharpe_efficiency,
                "train_max_drawdown": w.train_result.metrics.get("max_drawdown_pct", 0.0),
                "test_max_drawdown": w.test_result.metrics.get("max_drawdown_pct", 0.0),
                "drawdown_ratio": w.drawdown_ratio,
            }
            for w in completed_windows
        ]

        return WalkForwardReport(
            strategy_name=self.base_config.strategy_name,
            windows_count=len(completed_windows),
            mean_train_cagr=round(mean_train_cagr, 2),
            mean_test_cagr=round(mean_test_cagr, 2),
            mean_efficiency_ratio=round(mean_cagr_eff, 3),
            mean_cagr_efficiency=round(mean_cagr_eff, 3),
            mean_train_sharpe=round(mean_train_sharpe, 2),
            mean_test_sharpe=round(mean_test_sharpe, 2),
            mean_sharpe_efficiency=round(mean_sharpe_eff, 3),
            mean_train_max_drawdown=round(mean_train_dd, 2),
            mean_test_max_drawdown=round(mean_test_dd, 2),
            mean_drawdown_ratio=round(mean_dd_ratio, 3),
            is_overfit_suspected=is_overfit,
            windows=serialized_windows,
        )
