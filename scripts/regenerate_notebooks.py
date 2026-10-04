"""Regenerate and modernize research notebooks to use v3.0 APIs."""

import json


def update_nb(filename: str, cells_dict: dict[int, str]) -> None:
    path = f"notebooks/{filename}"
    with open(path, encoding="utf-8") as f:
        nb = json.load(f)
    code_idx = 0
    for cell in nb["cells"]:
        if cell["cell_type"] == "code":
            if code_idx in cells_dict:
                lines = [line + "\n" for line in cells_dict[code_idx].split("\n")]
                if lines and lines[-1] == "\n":
                    lines.pop()
                cell["source"] = lines
            code_idx += 1
    with open(path, "w", encoding="utf-8") as f:
        json.dump(nb, f, indent=1)
    print("Successfully modernized", filename)


# 01 - Market Data Ingestion
update_nb(
    "01_market_data_ingestion.ipynb",
    {
        0: """import asyncio

from src.database.session import get_session_factory, init_db
from src.ingestion.pipeline import seed_default_universe
from src.ingestion.providers.base import RawCandle
from src.validation.ohlcv_validator import OHLCVValidator

print('Platform ingestion libraries loaded successfully.')""",
        1: """validator = OHLCVValidator()

# Sample raw candle verification
valid_candle = RawCandle(
    timestamp_ms=1710000000000,
    open=64000.0,
    high=64500.0,
    low=63800.0,
    close=64200.0,
    volume=1500.0,
)
report = OHLCVValidator.validate_candle(valid_candle)
print(f'Candle validation status: {report.status.value}')
print(f'Passed checks: {report.is_valid}')""",
        2: """async def inspect_universe():
    await init_db()
    factory = get_session_factory()
    async with factory() as session:
        await seed_default_universe(session)
        print('Database initialized and universe seeded.')

asyncio.run(inspect_universe())""",
    },
)

# 02 - Feature Engineering Momentum
update_nb(
    "02_feature_engineering_momentum.ipynb",
    {
        0: """import numpy as np
import pandas as pd

from src.features.momentum import calculate_momentum_features
from src.features.volume import calculate_volume_features

print('Feature engineering modules imported.')""",
        1: """np.random.seed(42)
n = 200
returns = np.random.normal(0.001, 0.02, n)
prices = 100.0 * np.cumprod(1.0 + returns)
volumes = np.random.uniform(500, 2000, n)

df_market = pd.DataFrame({'close': prices, 'volume': volumes})
print(f'Generated {len(df_market)} synthetic bars.')""",
        2: """mom_feats = calculate_momentum_features(df_market['close'].to_numpy())
vol_feats = calculate_volume_features(df_market['volume'].to_numpy(), df_market['close'].to_numpy())

print('Calculated Momentum Factors:')
print(f"  - Return 1D: {mom_feats.return_1d:+.2%}" if mom_feats.return_1d is not None else "  - Return 1D: N/A")
print(f"  - Return 7D: {mom_feats.return_7d:+.2%}" if mom_feats.return_7d is not None else "  - Return 7D: N/A")
print(f"  - Return 30D: {mom_feats.return_30d:+.2%}" if mom_feats.return_30d is not None else "  - Return 30D: N/A")
print(f"  - RVOL 20: {vol_feats.volume_to_20_avg:.2f}" if vol_feats.volume_to_20_avg is not None else "  - RVOL 20: N/A")""",
    },
)

# 03 - Relative Strength Analysis
update_nb(
    "03_relative_strength_analysis.ipynb",
    {
        0: """import numpy as np

from src.features.relative_strength import calculate_relative_strength

print('Relative strength analysis module loaded.')""",
        1: """np.random.seed(42)
n = 100
btc_ret = np.random.normal(0.0005, 0.015, n)
alt_ret = np.random.normal(0.0015, 0.025, n)

btc_prices = 60000.0 * np.cumprod(1.0 + btc_ret)
alt_prices = 150.0 * np.cumprod(1.0 + alt_ret)

rs_metrics = calculate_relative_strength(
    asset_prices=alt_prices,
    btc_prices=btc_prices,
    candles_per_day=24,
)

print('Relative Strength vs BTC:')
print(f"  - RS 1D: {rs_metrics.rs_btc_1d:+.2%}" if rs_metrics.rs_btc_1d is not None else "  - RS 1D: N/A")
print(f"  - RS 7D: {rs_metrics.rs_btc_7d:+.2%}" if rs_metrics.rs_btc_7d is not None else "  - RS 7D: N/A")
print(f"  - RS 30D: {rs_metrics.rs_btc_30d:+.2%}" if rs_metrics.rs_btc_30d is not None else "  - RS 30D: N/A")""",
    },
)

# 04 - Trend and Regime Classification
update_nb(
    "04_trend_and_regime_classification.ipynb",
    {
        0: """import numpy as np

from src.features.market_regime import classify_market_regime
from src.features.trend import calculate_trend_features

print('Trend and regime modules loaded.')""",
        1: """np.random.seed(42)
n = 250
trend_ret = np.random.normal(0.002, 0.01, n)
closes = 100.0 * np.cumprod(1.0 + trend_ret)
highs = closes * 1.015
lows = closes * 0.985

trend_res = calculate_trend_features(highs, lows, closes)
regime = classify_market_regime(closes)

print('ADX 14:', trend_res.adx_14 if trend_res.adx_14 is not None else "N/A")
print('Trend Alignment Score:', trend_res.trend_alignment_score)
print('Macro Regime Classification:', regime.regime.value)
print('Regime Confidence:', f'{regime.confidence:.2f}')""",
    },
)

# 05 - Scoring Models and Explainability
update_nb(
    "05_scoring_models_and_explainability.ipynb",
    {
        0: """from types import SimpleNamespace

from src.scoring.altcoin import AltcoinScorer
from src.scoring.core import CoreScorer

alt_scorer = AltcoinScorer()
core_scorer = CoreScorer()
print('Scoring models loaded successfully.')""",
        1: """sample_features = SimpleNamespace(
    return_7d=0.142,
    return_30d=0.280,
    momentum_acceleration=0.05,
    rs_btc_7d=0.08,
    rs_btc_30d=0.18,
    rs_eth_30d=0.12,
    adx_14=32.0,
    trend_alignment_score=3,
    rvol_20=2.4,
    dollar_volume_24h=85000000.0,
    spread_est_bps=8.5,
    market_cap_usd=2500000000.0,
)

score_card = alt_scorer.calculate_score('SOL', sample_features)
print(f'Symbol: {score_card.asset_id}')
print(f'Composite Opportunity Score: {score_card.opportunity_score:.1f} / 100')
print('Factor Breakdown:')
for _f_name, comp in score_card.components.items():
    print(f'  - {comp.name}: weight={comp.weight:.2f}, score={comp.score:.1f}, contrib={comp.contribution:.1f}')
print('Risk Flags:', score_card.risk_flags)""",
    },
)

# 06 - Backtest Momentum Breakout via API
update_nb(
    "06_backtest_momentum_breakout.ipynb",
    {
        0: """import asyncio
from datetime import timedelta

from httpx import ASGITransport, AsyncClient

from apps.api.main import create_app
from src.utils.time import utc_now

print('Backtesting API client ready.')""",
        1: """async def run_sample_backtest():
    app = create_app()
    transport = ASGITransport(app=app)
    headers = {"X-API-Key": "dev-api-key-researcher-1"}
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "strategy_name": "MomentumBreakout",
            "symbols": ["SOL", "NEAR", "RENDER"],
            "start_date": (utc_now() - timedelta(days=90)).isoformat(),
            "end_date": utc_now().isoformat(),
            "initial_capital": 100000.0,
            "maker_fee_bps": 2.0,
            "taker_fee_bps": 5.0,
            "slippage_model": "market_impact",
        }
        resp = await client.post("/api/v1/backtests/run", json=payload, headers=headers)
        assert resp.status_code == 200, f"Error: {resp.text}"
        data = resp.json()
        print('Backtest execution completed via API.')
        print(f"Run ID: {data['id']}")
        print(f"Strategy: {data['strategy_name']}")
        print(f"Total Return: {data['total_return_pct']:+.2f}%")
        print(f"Sharpe Ratio: {data['sharpe_ratio']:.2f}")
        print(f"Max Drawdown: {data['max_drawdown_pct']:.2f}%")
        print(f"Total Trades: {len(data.get('trades') or [])}")

asyncio.run(run_sample_backtest())""",
    },
)

# 07 - Backtest Trend Regime via API
update_nb(
    "07_backtest_trend_regime.ipynb",
    {
        0: """import asyncio
from datetime import timedelta

from httpx import ASGITransport, AsyncClient

from apps.api.main import create_app
from src.utils.time import utc_now

print('Trend Regime strategy module ready.')""",
        1: """async def run_regime_backtest():
    app = create_app()
    transport = ASGITransport(app=app)
    headers = {"X-API-Key": "dev-api-key-researcher-1"}
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "strategy_name": "TrendRegimeFilter",
            "symbols": ["BTC", "ETH", "SOL"],
            "start_date": (utc_now() - timedelta(days=90)).isoformat(),
            "end_date": utc_now().isoformat(),
            "initial_capital": 100000.0,
            "maker_fee_bps": 2.0,
            "taker_fee_bps": 5.0,
        }
        resp = await client.post("/api/v1/backtests/run", json=payload, headers=headers)
        assert resp.status_code == 200, f"Error: {resp.text}"
        data = resp.json()
        print('Trend Regime Backtest via API completed.')
        print(f"Run ID: {data['id']}")
        print(f"Strategy Total Return: {data['total_return_pct']:+.2f}%")
        print(f"Benchmark Return: {data['benchmark_return_pct']:+.2f}%")
        print(f"Win Rate: {data['win_rate']*100:.1f}%")

asyncio.run(run_regime_backtest())""",
    },
)

# 09 - Paper Trading Execution
update_nb(
    "09_paper_trading_execution.ipynb",
    {
        0: """import asyncio
import uuid

from src.database.models import OHLCV
from src.database.session import get_session_factory, init_db
from src.paper.broker import PaperBroker
from src.paper.models import OrderSubmitRequest, PaperOrderSide, PaperOrderType
from src.utils.time import utc_now

print('Paper trading broker ready.')""",
        1: """async def execute_paper_trades():
    await init_db()
    factory = get_session_factory()

    # Ensure fresh price candle for SOL in canonical Market ID
    async with factory() as session:
        candle = OHLCV(
            time=utc_now(),
            market_id="binance:SOL/USDT",
            timeframe="1h",
            open=150.0,
            high=155.0,
            low=149.0,
            close=152.0,
            volume=50000.0,
            validation_status="GOOD",
        )
        await session.merge(candle)
        await session.commit()

    broker = PaperBroker()
    async with factory() as session:
        # Reset virtual account
        acc = await broker.reset_account(session, account_id="research_account", starting_balance=100000.0)
        print(f'Account initialized with ${acc.cash_balance:,.2f}')

        # Submit BUY order for SOL
        order = await broker.submit_order(
            session,
            OrderSubmitRequest(
                account_id="research_account",
                symbol="SOL",
                side=PaperOrderSide.BUY,
                order_type=PaperOrderType.MARKET,
                quantity=50.0,
                idempotency_key=str(uuid.uuid4()),
            )
        )
        print(f'Order {order.id} status: {order.status}')
        if order.fills:
            print(f'Filled at ${order.fills[0].fill_price:.2f}')

        port = await broker.get_portfolio_summary(session, account_id="research_account")
        print(f'Current Equity: ${port.total_equity:,.2f}')
        print(f'Open Positions: {[p.symbol for p in port.open_positions]}')

asyncio.run(execute_paper_trades())""",
    },
)

# 10 - Meme Coin Radar
update_nb(
    "10_meme_coin_radar.ipynb",
    {
        0: """import asyncio

from src.scoring.meme_radar import MemeRadarEngine

print('Meme Coin Radar loaded.')""",
        1: """async def scan_meme_tokens():
    engine = MemeRadarEngine()
    audits = await engine.scan_meme_tokens()
    print(f'Scanned {len(audits)} meme tokens on DEXes.\\n')
    for a in audits[:5]:
        print(f'{a.symbol} ({a.name}):')
        print(f'  - Score: {a.opportunity_score:.1f} / 100')
        print(f'  - Liquidity: ${a.liquidity_usd:,.0f}')
        print(f'  - Buy/Sell Ratio: {a.buy_pressure_ratio:.2f}')
        print(f'  - Risk Penalties: {a.total_penalties:.1f}')
        print(f'  - Active Flags: {a.risk_flags}\\n')

asyncio.run(scan_meme_tokens())""",
    },
)

print("All notebooks modernized successfully!")
