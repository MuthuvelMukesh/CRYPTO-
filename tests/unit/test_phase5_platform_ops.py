"""Tests for Phase 5 Platform & Operations.

Covers:
- /system operational summary endpoint
- /metrics Prometheus exposition endpoint
- Database backup and restore drill execution
- TimescaleDB configuration safety
- Docker security invariants (non-root users, unexposed internal ports, pinned images)
"""

from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from scripts.backup_database import create_backup
from scripts.restore_database import restore_backup
from src.database.timescale import setup_timescaledb


@pytest.mark.asyncio
async def test_system_endpoint_returns_operational_summary(client: AsyncClient) -> None:
    """GET /system must return full operational infrastructure summary."""
    res = await client.get("/system")
    assert res.status_code == 200
    data = res.json()

    assert data["status"] in ("UP", "DOWN")
    assert "uptime_seconds" in data
    assert "database" in data
    assert "cache" in data
    assert "market_data_freshness" in data
    assert "ingestion_lag_seconds" in data
    assert "job_queue" in data
    assert "active_exchanges" in data
    assert isinstance(data["active_exchanges"], list)
    assert len(data["active_exchanges"]) >= 1


@pytest.mark.asyncio
async def test_prometheus_metrics_exposition(client: AsyncClient) -> None:
    """GET /metrics must expose Prometheus metrics in standard exposition format."""
    # Issue a dummy request to generate metric observations
    await client.get("/health")

    res = await client.get("/metrics")
    assert res.status_code == 200
    content = res.text

    assert "crypto_ingestion_lag_seconds" in content
    assert "crypto_scan_duration_seconds" in content
    assert "crypto_api_request_latency_seconds" in content
    assert "crypto_job_queue_depth" in content
    assert "crypto_ledger_reconciliation_status" in content


@pytest.mark.asyncio
async def test_backup_and_restore_drill(tmp_path: Path) -> None:
    """Execute end-to-end database backup and restore drill."""
    # 1. Create backup archive in temporary directory
    backup_file = create_backup(target_dir=str(tmp_path / "backups"))
    assert backup_file.exists()
    assert backup_file.stat().st_size > 0

    # 2. Execute restore drill to target location
    target_restored_db = tmp_path / "restored.db"
    target_url = f"sqlite+aiosqlite:///{target_restored_db}"

    success = restore_backup(backup_file, target_db_url=target_url)
    assert success is True
    assert target_restored_db.exists()
    assert target_restored_db.stat().st_size > 0


@pytest.mark.asyncio
async def test_timescaledb_sqlite_noop(db_session: AsyncSession) -> None:
    """TimescaleDB automation must safely no-op when executing against SQLite in test/dev."""
    result = await setup_timescaledb(db_session)
    assert result["timescaledb_active"] is False
    assert result["reason"] == "sqlite_backend"


def test_docker_security_invariants() -> None:
    """Validate platform Dockerfiles and compose security invariants."""
    # 1. Dockerfiles must execute as unprivileged appuser (non-root)
    dockerfiles = [
        Path("docker/Dockerfile.api"),
        Path("docker/Dockerfile.worker"),
        Path("docker/Dockerfile.dashboard"),
    ]

    for df in dockerfiles:
        assert df.exists(), f"Missing dockerfile: {df}"
        content = df.read_text(encoding="utf-8")
        assert "USER appuser" in content, f"{df} is missing non-root 'USER appuser' directive!"
        assert "10001" in content, f"{df} does not declare unprivileged uid/gid 10001!"

    # 2. docker-compose.yml must not expose raw database ports to host by default
    compose_path = Path("docker-compose.yml")
    assert compose_path.exists()
    compose_text = compose_path.read_text(encoding="utf-8")

    # Ensure raw 5432:5432 and 6379:6379 are not active uncommented port mappings in timescaledb or redis
    lines = compose_text.splitlines()
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("- \"5432:5432\"") or stripped.startswith("- '5432:5432'"):
            pytest.fail(f"docker-compose.yml publishes Postgres port 5432 to host at line {idx+1}!")
        if stripped.startswith("- \"6379:6379\"") or stripped.startswith("- '6379:6379'"):
            pytest.fail(f"docker-compose.yml publishes Redis port 6379 to host at line {idx+1}!")

    # Ensure Caddy reverse proxy service is declared with pinned version
    assert "caddy:2.8.4-alpine" in compose_text
    assert "timescale/timescaledb:2.16.1-pg16" in compose_text
    assert "redis:7.4.1-alpine" in compose_text
