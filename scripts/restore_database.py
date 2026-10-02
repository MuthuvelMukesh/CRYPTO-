"""Automated Database Restore Drill Script — Platform v3.0.

Restores a compressed database backup and validates integrity.
"""

import gzip
import os
import shutil
import subprocess
import sys
from pathlib import Path

from src.config.settings import get_settings


def restore_backup(backup_path: str | Path, target_db_url: str | None = None) -> bool:
    """Restore database from compressed archive and verify integrity."""
    settings = get_settings()
    source = Path(backup_path)
    if not source.exists():
        raise FileNotFoundError(f"Backup file not found: {source}")

    db_url = target_db_url or settings.DATABASE_URL
    is_sqlite = "sqlite" in db_url.lower()

    if is_sqlite:
        # SQLite restore
        target_path_str = db_url.replace("sqlite+aiosqlite:///", "").replace("sqlite:///", "")
        target_file = Path(target_path_str)

        target_file.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(source, "rb") as f_in, open(target_file, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)

        # Quick validation check: file size > 0
        if not target_file.exists() or target_file.stat().st_size == 0:
            raise RuntimeError("Restored SQLite file is empty or corrupted.")

        print(f"[RESTORE SUCCESS] SQLite database restored to: {target_file}")
        return True

    else:
        # PostgreSQL / TimescaleDB restore
        psql = shutil.which("psql") or "psql"
        cmd = [psql, db_url]

        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=os.environ.copy(),
        )

        with gzip.open(source, "rb") as f_in:
            stdout, stderr = proc.communicate(input=f_in.read())

        if proc.returncode != 0:
            raise RuntimeError(f"psql restore failed (exit {proc.returncode}): {stderr.decode()}")

        print(f"[RESTORE SUCCESS] PostgreSQL database restored from: {source}")
        return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m scripts.restore_database <path_to_backup.gz>", file=sys.stderr)
        sys.exit(1)

    try:
        restore_backup(sys.argv[1])
        print("Restore completed successfully.")
    except Exception as exc:
        print(f"Restore failed: {exc}", file=sys.stderr)
        sys.exit(1)
