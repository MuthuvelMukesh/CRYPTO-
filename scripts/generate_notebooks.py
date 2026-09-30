"""Script to generate all 11 quantitative research and backtesting Jupyter notebooks."""

import json
from pathlib import Path


def make_notebook(title: str, cells_data: list[tuple[str, str]]) -> dict:
    """Construct a Jupyter notebook dictionary structure."""
    cells = []
    for cell_type, content in cells_data:
        cell = {
            "cell_type": cell_type,
            "metadata": {},
            "source": [line + "\n" for line in content.split("\n")],
        }
        if cell_type == "code":
            cell["execution_count"] = None
            cell["outputs"] = []
        cells.append(cell)

    return {
        "cells": cells,
        "metadata": {
            "language_info": {
                "name": "python",
                "version": "3.12",
            },
            "kernelspec": {
                "display_name": "Python 3 (ipykernel)",
                "language": "python",
                "name": "python3",
            },
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }


def generate_all_notebooks() -> None:
    notebooks_dir = Path("notebooks")
    notebooks_dir.mkdir(parents=True, exist_ok=True)

    notebooks = {
        "01_market_data_ingestion.ipynb": [
            ("markdown", "# 01 - Market Data Ingestion & OHLCV Validation Pipeline\n\nThis research notebook demonstrates the multi-exchange data ingestion pipeline, CCXT / CoinGecko connector interfaces, and data hygiene validation protocols."),
            ("code", "import asyncio\nimport polars as pl\nimport pandas as pd\nfrom src.database.session import init_db, get_session_factory\nfrom src.ingestion.pipeline import seed_default_universe\nfrom src.validation.ohlcv_validator import OHLCVCandleValidator\n\nprint('Platform ingestion libraries loaded successfully.')"),
            ("code", "validator = OHLCVCandleValidator(min_volume=1.0)\n\n# Sample raw candle verification\nvalid_candle = {\n    'time': 1710000000000,\n    'open': 64000.0,\n    'high': 64500.0,\n    'low': 63800.0,\n    'close': 64200.0,\n    'volume': 1500.0,\n}\nreport = validator.validate_candle(valid_candle)\nprint(f'Candle validation status: {report.status}')\nprint(f'Passed checks: {report.is_valid}')"),
            ("code", "async def inspect_universe():\n    await init_db()\n    factory = get_session_factory()\n    async with factory() as session:\n        await seed_default_universe(session)\n        print('Database initialized and universe seeded.')\n\nasyncio.run(inspect_universe())"),
        ],

        "02_feature_engineering_momentum.ipynb": [
            ("markdown", "# 02 - Multi-Timeframe Momentum & RVOL Feature Engineering\n\nThis notebook computes momentum returns across multiple horizons (1D, 7D, 14D, 30D, 90D), rolling relative volume (RVOL 20-day baseline), and realized volatility using Polars and NumPy."),
            ("code", "import numpy as np\nimport polars as pl\nimport pandas as pd\nfrom src.features.momentum import calculate_momentum_features\nfrom src.features.volume import calculate_volume_features\nfrom src.features.volatility import calculate_volatility_features\n\nprint('Feature engineering modules imported.')"),
            ("code", "# Generate synthetic price series for demonstration\nnp.random.seed(42)\nn_bars = 200\nreturns = np.random.normal(0.001, 0.02, n_bars)\nprices = 100.0 * np.cumprod(1.0 + returns)\nvolumes = np.random.exponential(5000, n_bars)\n\ndf_market = pl.DataFrame({\n    'close': prices,\n    'high': prices * 1.01,\n    'low': prices * 0.99,\n    'volume': volumes,\n})\nprint(f'Generated {len(df_market)} synthetic bars.')"),
            ("code", "mom_feats = calculate_momentum_features(df_market['close'].to_numpy())\nvol_feats = calculate_volume_features(df_market['volume'].to_numpy())\nvolat_feats = calculate_volatility_features(df_market['high'].to_numpy(), df_market['low'].to_numpy(), df_market['close'].to_numpy())\n\nprint('Momentum 1D return:', mom_feats.get('return_1d', 0.0))\nprint('Momentum 7D return:', mom_feats.get('return_7d', 0.0))\nprint('RVOL 20:', vol_feats.get('rvol_20', 1.0))\nprint('Realized Volatility 30D:', volat_feats.get('volatility_30d', 0.0))"),
        ],

        "03_relative_strength_analysis.ipynb": [
            ("markdown", "# 03 - Relative Strength Matrix vs Bitcoin & Ethereum\n\nAnalysis of crypto cross-sectional leadership, relative strength ratio expansion against benchmark assets (BTC/ETH), rolling beta, and benchmark alpha."),
            ("code", "import numpy as np\nimport pandas as pd\nfrom src.features.relative_strength import calculate_relative_strength_ratio\n\nprint('Relative strength analysis ready.')"),
            ("code", "# Simulate Altcoin vs BTC price paths\nnp.random.seed(101)\nn = 150\nbtc_ret = np.random.normal(0.0005, 0.015, n)\nsol_ret = np.random.normal(0.0015, 0.025, n)\n\nbtc_prices = 60000.0 * np.cumprod(1.0 + btc_ret)\nsol_prices = 140.0 * np.cumprod(1.0 + sol_ret)\n\nrs_ratio, rs_ema, rs_percentile = calculate_relative_strength_ratio(sol_prices, btc_prices)\nprint(f'Latest SOL/BTC RS Ratio: {rs_ratio[-1]:.6f}')\nprint(f'Latest RS 50 EMA: {rs_ema[-1]:.6f}')\nprint(f'Relative Strength Percentile: {rs_percentile:.1f}%')"),
        ],

        "04_trend_and_regime_classification.ipynb": [
            ("markdown", "# 04 - Trend Structure & Macro Market Regime Classification\n\nIdentification of macro market regimes: Bull Trend, Bear Trend, High-Volatility Chop, and Low-Volatility Compression using moving average ribbons and trend strength indicators (ADX/MACD)."),
            ("code", "import numpy as np\nimport pandas as pd\nfrom src.features.trend import calculate_trend_features\nfrom src.features.market_regime import classify_market_regime\n\nprint('Trend and regime modules loaded.')"),
            ("code", "# Create upward trending market data\nn = 250\ntrend_ret = np.random.normal(0.002, 0.01, n)\ncloses = 100.0 * np.cumprod(1.0 + trend_ret)\nhighs = closes * 1.015\nlows = closes * 0.985\n\ntrend_res = calculate_trend_features(highs, lows, closes)\nregime = classify_market_regime(highs, lows, closes)\n\nprint('ADX Trend Strength:', trend_res.get('adx', 0.0))\nprint('EMA 20 > EMA 50:', trend_res.get('ema_20_above_50', False))\nprint('Macro Regime Classification:', regime.regime.value)\nprint('Regime Confidence:', regime.confidence)"),
        ],

        "05_scoring_models_and_explainability.ipynb": [
            ("markdown", "# 05 - Multi-Factor Scoring Models & Explainability Cards\n\nImplementation of composite factor scoring models (Core, Altcoin, SmallCap, Meme) with transparent additive factor contributions and risk penalty deductions."),
            ("code", "from src.scoring.composite import MultiFactorScoringEngine\nfrom src.scoring.models import CoreAssetScoringModel, AltcoinScoringModel\n\nengine = MultiFactorScoringEngine()\nprint('Scoring engine initialized.')"),
            ("code", "sample_features = {\n    'return_1d': 0.045,\n    'return_7d': 0.142,\n    'return_30d': 0.280,\n    'rs_btc_30d': 18.5,\n    'adx': 32.0,\n    'ema_alignment_score': 85.0,\n    'rvol_20': 2.4,\n    'volatility_30d': 0.45,\n    'spread_bps': 8.5,\n    'circulating_pct': 0.85,\n}\n\nscore_card = engine.evaluate_asset('SOL', sample_features, model_type='altcoin')\nprint(f'Symbol: {score_card.asset_id}')\nprint(f'Composite Opportunity Score: {score_card.opportunity_score:.1f} / 100')\nprint('Factor Breakdown:')\nfor f_name, f_val in score_card.breakdown.items():\n    print(f'  - {f_name}: {f_val:.1f}')\nprint('Risk Flags:', score_card.risk_flags)"),
        ],

        "06_backtest_momentum_breakout.ipynb": [
            ("markdown", "# 06 - Quantitative Backtesting: Momentum Breakout Strategy\n\nEvent-driven backtesting of the Momentum Breakout strategy with execution slippage modeling (Corwin-Schultz spread proxy and square-root market impact)."),
            ("code", "import asyncio\nfrom src.backtesting.engine import BacktestEngine, BacktestConfig\nfrom src.backtesting.strategies.momentum_breakout import MomentumBreakoutStrategy\nfrom src.database.session import init_db, get_session_factory\n\nprint('Backtesting engine ready.')"),
            ("code", "async def run_sample_backtest():\n    await init_db()\n    config = BacktestConfig(\n        strategy_name='MomentumBreakout',\n        symbols=['SOL', 'NEAR', 'RENDER'],\n        initial_capital=100000.0,\n        commission_rate=0.001,\n        slippage_model='square_root',\n    )\n    engine = BacktestEngine(config)\n    factory = get_session_factory()\n    async with factory() as session:\n        results = await engine.run(session)\n        print('Backtest execution completed.')\n        print(f'Total Return: {results.metrics.total_return_pct:.2f}%')\n        print(f'Sharpe Ratio: {results.metrics.sharpe_ratio:.2f}')\n        print(f'Max Drawdown: {results.metrics.max_drawdown_pct:.2f}%')\n\nasyncio.run(run_sample_backtest())"),
        ],

        "07_backtest_trend_regime.ipynb": [
            ("markdown", "# 07 - Quantitative Backtesting: Trend Regime Filter Strategy\n\nBacktesting the Trend Regime Filter strategy across bull, bear, and high-volatility chop regimes with dynamic cash de-risking."),
            ("code", "import asyncio\nfrom src.backtesting.engine import BacktestEngine, BacktestConfig\nfrom src.backtesting.strategies.trend_regime import TrendRegimeFilterStrategy\nfrom src.database.session import init_db, get_session_factory\n\nprint('Trend Regime strategy module ready.')"),
            ("code", "async def run_regime_backtest():\n    await init_db()\n    config = BacktestConfig(\n        strategy_name='TrendRegimeFilter',\n        symbols=['BTC', 'ETH', 'SOL'],\n        initial_capital=100000.0,\n        commission_rate=0.001,\n    )\n    engine = BacktestEngine(config)\n    factory = get_session_factory()\n    async with factory() as session:\n        res = await engine.run(session)\n        print(f'Strategy Total Return: {res.metrics.total_return_pct:.2f}%')\n        print(f'Benchmark Return: {res.metrics.benchmark_return_pct:.2f}%')\n        print(f'Alpha: {res.metrics.alpha_pct:+.2f}%')\n\nasyncio.run(run_regime_backtest())"),
        ],

        "08_walk_forward_validation.ipynb": [
            ("markdown", "# 08 - Walk-Forward Validation & Machine Learning Signal Lab\n\nTemporal train/test splitting with embargo buffers to eliminate lookahead bias, out-of-sample prediction evaluations, and Information Coefficient (IC) tracking."),
            ("code", "import numpy as np\nimport pandas as pd\nfrom src.research.ml_models import (\n    QuantitativeMLModel,\n    create_forward_labels,\n    walk_forward_train_evaluate,\n)\n\nprint('Research ML lab initialized.')"),
            ("code", "# Generate sample dataset with momentum and relative strength features\nnp.random.seed(42)\nn = 400\ndf = pd.DataFrame({\n    'close': 100.0 * np.exp(np.cumsum(np.random.normal(0.0005, 0.015, n))),\n    'feat_mom_1d': np.random.normal(0, 1, n),\n    'feat_rs_btc': np.random.normal(0, 1, n),\n    'feat_rvol': np.random.exponential(1.5, n),\n})\n\nlabeled_df = create_forward_labels(df, horizon_bars=24, price_col='close')\nreport = walk_forward_train_evaluate(\n    labeled_df,\n    feature_cols=['feat_mom_1d', 'feat_rs_btc', 'feat_rvol'],\n    train_pct=0.70,\n    embargo_bars=24,\n    model_type='logistic_regression',\n)\n\nprint(f'Out-of-sample Accuracy: {report.accuracy:.2%}')\nprint(f'Information Coefficient (IC): {report.information_coefficient:.4f}')\nprint(f'Spearman Rank IC: {report.rank_ic:.4f}')\nprint('Learned Feature Weights:', report.feature_importances)"),
        ],

        "09_paper_trading_execution.ipynb": [
            ("markdown", "# 09 - Virtual Paper Brokerage & Portfolio Risk Engine\n\nSimulating live execution in paper trading mode: market and limit order lifecycle, position tracking, cash margin, and risk engine constraint enforcement."),
            ("code", "import asyncio\nfrom src.paper.broker import PaperBroker\nfrom src.paper.models import OrderSubmitRequest, PaperOrderSide, PaperOrderType\nfrom src.database.session import init_db, get_session_factory\n\nprint('Paper trading broker ready.')"),
            ("code", "async def execute_paper_trades():\n    await init_db()\n    broker = PaperBroker()\n    factory = get_session_factory()\n    async with factory() as session:\n        # Reset virtual account\n        acc = await broker.reset_account(session, account_id='research_account', starting_balance=100000.0)\n        print(f'Account initialized with ${acc.cash_balance:,.2f}')\n\n        # Submit BUY order for SOL\n        order = await broker.submit_order(\n            session,\n            OrderSubmitRequest(\n                account_id='research_account',\n                symbol='SOL',\n                side=PaperOrderSide.BUY,\n                order_type=PaperOrderType.MARKET,\n                quantity=50.0,\n            )\n        )\n        print(f'Order {order.id} status: {order.status.value}')\n        if order.fills:\n            print(f'Filled at ${order.fills[0].fill_price:.2f}')\n\n        port = await broker.get_portfolio(session, account_id='research_account')\n        print(f'Current Equity: ${port.total_equity:,.2f}')\n        print(f'Open Positions: {[p.symbol for p in port.positions]}')\n\nasyncio.run(execute_paper_trades())"),
        ],

        "10_meme_coin_radar.ipynb": [
            ("markdown", "# 10 - Meme Coin Radar & DEX Liquidity Intelligence\n\nReal-time DEX liquidity auditing, DexScreener token discovery, buy/sell transaction ratios, holder concentration penalties, and rug-pull risk scoring."),
            ("code", "import asyncio\nfrom src.ingestion.providers.dexscreener_provider import DexScreenerProvider\nfrom src.scoring.meme_radar import MemeRadarEngine\n\nprint('Meme Coin Radar loaded.')"),
            ("code", "async def scan_meme_tokens():\n    engine = MemeRadarEngine()\n    audits = await engine.scan_meme_tokens()\n    print(f'Scanned {len(audits)} meme tokens on DEXes.\\n')\n    for a in audits[:5]:\n        print(f'{a.symbol} ({a.token_name}):')\n        print(f'  - Score: {a.opportunity_score:.1f} / 100')\n        print(f'  - Liquidity: ${a.liquidity_usd:,.0f}')\n        print(f'  - Buy/Sell Ratio: {a.buy_pressure_ratio:.2f}')\n        print(f'  - Risk Penalties: {a.risk_penalties}')\n        print(f'  - Active Flags: {a.risk_flags}\\n')\n\nasyncio.run(scan_meme_tokens())"),
        ],

        "11_sector_rotation_and_alerts.ipynb": [
            ("markdown", "# 11 - Crypto Sector Rotation & Real-Time Alert Engine\n\nSector momentum aggregation, market breadth calculations, rotation quadrant classification (Leading, Accelerating, Weakening, Declining), and automated signal alert broadcasting."),
            ("code", "import asyncio\nfrom src.features.sector import get_all_sector_performances\nfrom src.alerts.engine import AlertEngine\nfrom src.alerts.models import AlertSeverity, AlertType\nfrom src.database.session import init_db, get_session_factory\n\nprint('Sector rotation and alert modules loaded.')"),
            ("code", "async def analyze_sectors_and_alerts():\n    await init_db()\n    factory = get_session_factory()\n    async with factory() as session:\n        sectors = await get_all_sector_performances(session)\n        print('=== SECTOR ROTATION MATRIX ===')\n        for s in sectors:\n            print(f'{s.sector_name:<16} | 7D: {s.return_7d*100:+.1f}% | Breadth: {s.breadth_pct:4.1f}% | {s.rotation_status}')\n\n    # Test alert dispatching\n    alert_engine = AlertEngine(cooldown_minutes=15)\n    alert = await alert_engine.emit(\n        alert_type=AlertType.MOMENTUM_BREAKOUT,\n        severity=AlertSeverity.INFO,\n        symbol='SOL',\n        message='SOL 24h momentum breakout triggered from sector rotation leader.',\n    )\n    if alert:\n        print(f'\\nDispatched alert: [{alert.severity.value}] {alert.message}')\n\nasyncio.run(analyze_sectors_and_alerts())"),
        ],
    }

    for filename, cells_data in notebooks.items():
        nb_json = make_notebook(filename, cells_data)
        file_path = notebooks_dir / filename
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(nb_json, f, indent=1)
        print(f"Generated {file_path}")


if __name__ == "__main__":
    generate_all_notebooks()
