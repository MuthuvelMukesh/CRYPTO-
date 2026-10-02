"""TimescaleDB hypertable, compression, and retention automation — Platform v3.0."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.settings import get_settings
from src.utils.logging import get_logger

logger = get_logger("database.timescale")


async def setup_timescaledb(session: AsyncSession) -> dict[str, bool]:
    """Configure TimescaleDB hypertables, compression, and retention if running on PostgreSQL/Timescale.

    Safe no-op when executing against SQLite in test/dev.
    """
    settings = get_settings()
    if settings.is_sqlite:
        logger.debug("timescaledb_setup_skipped_sqlite")
        return {"timescaledb_active": False, "reason": "sqlite_backend"}

    status: dict[str, bool] = {"timescaledb_active": False}

    try:
        # Check if TimescaleDB extension is installed
        ext_check = await session.execute(
            text("SELECT count(*) FROM pg_extension WHERE extname = 'timescaledb';")
        )
        has_ext = ext_check.scalar_one_or_none() or 0
        if not has_ext:
            logger.info("timescaledb_extension_not_installed")
            return {"timescaledb_active": False, "reason": "extension_not_found"}

        status["timescaledb_active"] = True

        # 1. Create hypertables if not already configured
        hypertables = [
            ("ohlcv", "time"),
            ("trades", "time"),
            ("orderbook_snapshots", "time"),
        ]

        for table, time_col in hypertables:
            try:
                await session.execute(
                    text(f"SELECT create_hypertable('{table}', '{time_col}', if_not_exists => TRUE, migrate_data => TRUE);")
                )
                status[f"{table}_hypertable"] = True
                logger.info("hypertable_configured", table=table)
            except Exception as e:
                logger.warning("hypertable_creation_warning", table=table, error=str(e))
                status[f"{table}_hypertable"] = False

        # 2. Add compression policies
        compression_configs = [
            ("ohlcv", "market_id, timeframe", "7 days"),
            ("trades", "market_id", "3 days"),
            ("orderbook_snapshots", "market_id", "2 days"),
        ]

        for table, segment_by, interval in compression_configs:
            try:
                await session.execute(
                    text(f"""
                        ALTER TABLE {table} SET (
                            timescaledb.compress,
                            timescaledb.compress_segmentby = '{segment_by}',
                            timescaledb.compress_orderby = 'time DESC'
                        );
                    """)
                )
                await session.execute(
                    text(f"SELECT add_compression_policy('{table}', INTERVAL '{interval}', if_not_exists => TRUE);")
                )
                status[f"{table}_compression"] = True
                logger.info("compression_policy_configured", table=table, interval=interval)
            except Exception as e:
                logger.warning("compression_policy_warning", table=table, error=str(e))
                status[f"{table}_compression"] = False

        # 3. Add retention policies
        retention_configs = [
            ("trades", "90 days"),
            ("orderbook_snapshots", "30 days"),
        ]

        for table, interval in retention_configs:
            try:
                await session.execute(
                    text(f"SELECT add_retention_policy('{table}', INTERVAL '{interval}', if_not_exists => TRUE);")
                )
                status[f"{table}_retention"] = True
                logger.info("retention_policy_configured", table=table, interval=interval)
            except Exception as e:
                logger.warning("retention_policy_warning", table=table, error=str(e))
                status[f"{table}_retention"] = False

        await session.commit()

    except Exception as e:
        logger.error("timescaledb_setup_failed", error=str(e))
        status["error"] = str(e)

    return status
