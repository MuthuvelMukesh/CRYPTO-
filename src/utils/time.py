"""Time and date utilities enforcing strict UTC normalization."""

from datetime import UTC, datetime


def utc_now() -> datetime:
    """Return current timezone-aware UTC datetime."""
    return datetime.now(UTC)


def to_utc_datetime(ts: int | float | str | datetime) -> datetime:
    """
    Convert any valid timestamp representation to a timezone-aware UTC datetime.
    Supports Unix timestamps in seconds or milliseconds, ISO strings, and datetime objects.
    """
    if isinstance(ts, datetime):
        if ts.tzinfo is None:
            return ts.replace(tzinfo=UTC)
        return ts.astimezone(UTC)

    if isinstance(ts, (int, float)):
        # Millisecond timestamp (> 1e11 is in milliseconds)
        if ts > 1e11:
            return datetime.fromtimestamp(ts / 1000.0, tz=UTC)
        return datetime.fromtimestamp(ts, tz=UTC)

    if isinstance(ts, str):
        # Parse ISO string
        clean_str = ts.replace("Z", "+00:00")
        dt = datetime.fromisoformat(clean_str)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=UTC)
        return dt.astimezone(UTC)

    raise ValueError(f"Unsupported timestamp format: {ts} (type {type(ts)})")


def to_utc_ms(dt: datetime | str | int | float) -> int:
    """Convert timestamp to UTC Unix millisecond timestamp."""
    utc_dt = to_utc_datetime(dt)
    return int(utc_dt.timestamp() * 1000)


def to_utc_iso(dt: datetime | str | int | float) -> str:
    """Convert timestamp to UTC ISO 8601 formatted string."""
    utc_dt = to_utc_datetime(dt)
    return utc_dt.isoformat()
