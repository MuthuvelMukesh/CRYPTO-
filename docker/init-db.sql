-- ============================================================================
-- TimescaleDB Initialization, Hypertables, Compression & Retention — Platform v3.0
-- ============================================================================

-- 1. Initialize TimescaleDB Extension
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- 2. Ensure UTC timezone is strictly enforced
SET timezone = 'UTC';

-- 3. Hypertables Creation Helper Procedure
-- Converts tables to hypertables once created by Alembic migrations or SQLAlchemy
DO $$
BEGIN
    -- ohlcv hypertable partitioned by time
    IF EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'ohlcv') THEN
        PERFORM create_hypertable('ohlcv', 'time', if_not_exists => TRUE, migrate_data => TRUE);
        
        -- Enable compression on ohlcv (segmented by market_id and timeframe)
        ALTER TABLE ohlcv SET (
            timescaledb.compress,
            timescaledb.compress_segmentby = 'market_id, timeframe',
            timescaledb.compress_orderby = 'time DESC'
        );
        PERFORM add_compression_policy('ohlcv', INTERVAL '7 days', if_not_exists => TRUE);
    END IF;

    -- trades hypertable partitioned by time
    IF EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'trades') THEN
        PERFORM create_hypertable('trades', 'time', if_not_exists => TRUE, migrate_data => TRUE);
        
        -- Enable compression on trades (segmented by market_id)
        ALTER TABLE trades SET (
            timescaledb.compress,
            timescaledb.compress_segmentby = 'market_id',
            timescaledb.compress_orderby = 'time DESC'
        );
        PERFORM add_compression_policy('trades', INTERVAL '3 days', if_not_exists => TRUE);
        
        -- Retention policy: retain tick trades for 90 days
        PERFORM add_retention_policy('trades', INTERVAL '90 days', if_not_exists => TRUE);
    END IF;

    -- orderbook_snapshots hypertable partitioned by time
    IF EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'orderbook_snapshots') THEN
        PERFORM create_hypertable('orderbook_snapshots', 'time', if_not_exists => TRUE, migrate_data => TRUE);
        
        -- Enable compression on orderbook_snapshots
        ALTER TABLE orderbook_snapshots SET (
            timescaledb.compress,
            timescaledb.compress_segmentby = 'market_id',
            timescaledb.compress_orderby = 'time DESC'
        );
        PERFORM add_compression_policy('orderbook_snapshots', INTERVAL '2 days', if_not_exists => TRUE);
        
        -- Retention policy: retain level 2 orderbooks for 30 days
        PERFORM add_retention_policy('orderbook_snapshots', INTERVAL '30 days', if_not_exists => TRUE);
    END IF;
END $$;
