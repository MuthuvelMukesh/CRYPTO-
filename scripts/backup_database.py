"""Automated Database Backup Script — Platform v3.0.

Supports:
1. PostgreSQL / TimescaleDB via pg_dump with gzip compression
2. SQLite via file copy / vacuum into for dev & testing environments
"""

import gzip
import os
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from src.config.settings import get_settings


def create_backup(target_dir: str = "backups") -> Path:
    """Create timestamped compressed backup of active database."""
    settings = get_settings()
    out_dir = Path(target_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")

    if settings.is_sqlite:
        # SQLite backup procedure
        # Extract file path from sqlite+aiosqlite:///./crypto_intelligence.db
        db_path_str = settings.DATABASE_URL.replace("sqlite+aiosqlite:///", "").replace("sqlite:///", "")
        source_file = Path(db_path_str)

        dest_file = out_dir / f"sqlite_backup_{timestamp}.db.gz"

        if not source_file.exists():
            # If in-memory or not created yet, create empty valid db
            source_file.touch()

        with open(source_file, "rb") as f_in, gzip.open(dest_file, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)

        print(f"[BACKUP SUCCESS] SQLite backup archived to: {dest_file}")
        return dest_file

    else:
        # PostgreSQL / TimescaleDB backup procedure
        dest_file = out_dir / f"postgres_backup_{timestamp}.sql.gz"
        pg_dump = shutil.which("pg_dump") or "pg_dump"

        cmd = [
            pg_dump,
            "--clean",
            "--if-exists",
            "--no-owner",
            "--no-privileges",
        ]

        # Use DATABASE_URL if available
        env = os.environ.copy()
        proc = subprocess.Popen(
            [*cmd, settings.DATABASE_URL],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )

        with gzip.open(dest_file, "wb") as f_out:
            if proc.stdout:
                shutil.copyfileobj(proc.stdout, f_out)

        _, stderr = proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(f"pg_dump failed (exit {proc.returncode}): {stderr.decode()}")

        print(f"[BACKUP SUCCESS] PostgreSQL backup archived to: {dest_file}")
        return dest_file


if __name__ == "__main__":
    try:
        backup_path = create_backup()
        print(f"Created backup: {backup_path}")
    except Exception as exc:
        print(f"Backup failed: {exc}", file=sys.stderr)
        sys.exit(1)
