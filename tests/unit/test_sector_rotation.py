"""Unit tests for Sector Performance, Breadth, and Rotation Analysis."""

from src.features.sector import calculate_sector_metrics


def test_calculate_sector_metrics_accelerating() -> None:
    # 24 candles per day * 7 days = 168 candles
    # Generate prices that grew > 5% over 7 days and > 1% in last 24h
    candles_count = 200
    # Base price 100, climbing to 120
    closes_1 = [100.0 + (i * 0.1) for i in range(candles_count)]
    closes_2 = [50.0 + (i * 0.06) for i in range(candles_count)]

    asset_closes = {
        "SOL": closes_1,
        "AVAX": closes_2,
    }
    asset_volumes = {
        "SOL": [1000.0 for _ in range(candles_count)],
        "AVAX": [500.0 for _ in range(candles_count)],
    }

    perf = calculate_sector_metrics(
        sector_name="Layer 1",
        asset_closes=asset_closes,
        asset_volumes=asset_volumes,
        candles_per_day=24,
    )

    assert perf is not None
    assert perf.sector_name == "Layer 1"
    assert perf.asset_count == 2
    assert perf.return_7d > 0.05
    assert perf.return_1d > 0.01
    assert perf.breadth_pct == 100.0
    assert perf.rotation_status == "ACCELERATING"


def test_calculate_sector_metrics_declining() -> None:
    candles_count = 200
    # Declining prices
    closes_1 = [150.0 - (i * 0.2) for i in range(candles_count)]
    closes_2 = [80.0 - (i * 0.1) for i in range(candles_count)]

    asset_closes = {
        "GALA": closes_1,
        "SAND": closes_2,
    }

    perf = calculate_sector_metrics(
        sector_name="Gaming",
        asset_closes=asset_closes,
        candles_per_day=24,
    )

    assert perf is not None
    assert perf.sector_name == "Gaming"
    assert perf.return_7d < 0.0
    assert perf.breadth_pct == 0.0
    assert perf.rotation_status == "DECLINING"


def test_calculate_sector_metrics_empty() -> None:
    perf = calculate_sector_metrics("EmptySector", {})
    assert perf is None
