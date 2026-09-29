-- Initialize TimescaleDB Extension if available
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- Ensure UTC timezone is set for all sessions
SET timezone = 'UTC';
