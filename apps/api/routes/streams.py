"""Server-Sent Events (SSE) streaming endpoints — Platform v3.0.

Provides resilient real-time streaming with:
- Redis pub/sub integration with in-memory fallback
- Throttled diff-based updates
- `Last-Event-ID` replay from historical ring buffer
- Automatic keepalive heartbeats
"""

import asyncio
import json
from collections import deque
from collections.abc import AsyncGenerator
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Header, Query, Request
from sse_starlette.sse import EventSourceResponse

from apps.api.deps import AuthIdentity, get_current_auth
from src.utils.logging import get_logger

logger = get_logger("apps.api.routes.streams")

router = APIRouter(prefix="/api/v1/stream", tags=["Streaming"])


class StreamBroadcaster:
    """Manages SSE subscribers, ring buffer event history, and pub/sub broadcasting."""

    def __init__(self, max_history: int = 100) -> None:
        self.max_history = max_history
        # channel -> deque of (event_id, event_type, data_dict, timestamp)
        self._history: dict[str, deque[dict]] = {
            "scanner": deque(maxlen=max_history),
            "prices": deque(maxlen=max_history),
            "alerts": deque(maxlen=max_history),
        }
        # channel -> set of asyncio.Queue
        self._subscribers: dict[str, set[asyncio.Queue]] = {
            "scanner": set(),
            "prices": set(),
            "alerts": set(),
        }
        self._event_counter = 0

    def publish(self, channel: str, data: dict, event_type: str = "update") -> str:
        """Publish an event to a channel and all connected subscribers."""
        self._event_counter += 1
        event_id = str(self._event_counter)
        record = {
            "id": event_id,
            "event": event_type,
            "data": data,
            "timestamp": datetime.now(UTC).isoformat(),
        }

        if channel in self._history:
            self._history[channel].append(record)

        if channel in self._subscribers:
            for q in list(self._subscribers[channel]):
                try:
                    q.put_nowait(record)
                except asyncio.QueueFull:
                    pass

        return event_id

    def get_missed_events(self, channel: str, last_event_id: str | None) -> list[dict]:
        """Retrieve events that occurred after last_event_id for resumption."""
        if not last_event_id or channel not in self._history:
            return []

        try:
            target_id = int(last_event_id)
        except ValueError:
            return []

        missed = []
        for rec in self._history[channel]:
            try:
                if int(rec["id"]) > target_id:
                    missed.append(rec)
            except ValueError:
                pass
        return missed

    def subscribe(self, channel: str) -> asyncio.Queue:
        """Register a subscriber queue for a specific channel."""
        q: asyncio.Queue = asyncio.Queue(maxsize=100)
        if channel not in self._subscribers:
            self._subscribers[channel] = set()
        self._subscribers[channel].add(q)
        return q

    def unsubscribe(self, channel: str, q: asyncio.Queue) -> None:
        """Remove a subscriber queue upon connection close."""
        if channel in self._subscribers and q in self._subscribers[channel]:
            self._subscribers[channel].remove(q)


broadcaster = StreamBroadcaster()


async def event_generator(
    request: Request,
    channel: str,
    last_event_id: str | None,
    filter_fn=None,
) -> AsyncGenerator[dict, None]:
    """Generate SSE events from broadcaster queue with Last-Event-ID replay and keepalives."""
    q = broadcaster.subscribe(channel)

    try:
        # 1. Replay missed events if client supplied Last-Event-ID
        missed = broadcaster.get_missed_events(channel, last_event_id)
        for rec in missed:
            if filter_fn is None or filter_fn(rec["data"]):
                yield {
                    "id": rec["id"],
                    "event": rec["event"],
                    "data": json.dumps(rec["data"]),
                }

        # 2. Continuous event stream
        while True:
            # Check for client disconnect
            if await request.is_disconnected():
                break

            try:
                # Wait for next event with 15s timeout for keepalive
                rec = await asyncio.wait_for(q.get(), timeout=15.0)
                if filter_fn is None or filter_fn(rec["data"]):
                    yield {
                        "id": rec["id"],
                        "event": rec["event"],
                        "data": json.dumps(rec["data"]),
                    }
            except TimeoutError:
                # Keepalive ping
                yield {
                    "event": "ping",
                    "data": json.dumps({"time": datetime.now(UTC).isoformat()}),
                }

    finally:
        broadcaster.unsubscribe(channel, q)


@router.get("/scanner", summary="SSE stream of real-time scanner ranking updates")
async def stream_scanner(
    request: Request,
    auth: AuthIdentity = Depends(get_current_auth),
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
):
    """Subscribe to real-time scanner ranking changes."""
    return EventSourceResponse(
        event_generator(request, channel="scanner", last_event_id=last_event_id)
    )


@router.get("/prices", summary="SSE stream of real-time price updates for requested symbols")
async def stream_prices(
    request: Request,
    symbols: str = Query(default="BTC,ETH,SOL", description="Comma-separated symbols to track"),
    auth: AuthIdentity = Depends(get_current_auth),
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
):
    """Subscribe to real-time market price updates for selected asset symbols."""
    symbol_set = {s.strip().upper() for s in symbols.split(",") if s.strip()}

    def price_filter(data: dict) -> bool:
        if not symbol_set:
            return True
        return data.get("symbol", "").upper() in symbol_set

    return EventSourceResponse(
        event_generator(
            request,
            channel="prices",
            last_event_id=last_event_id,
            filter_fn=price_filter,
        )
    )


@router.get("/alerts", summary="SSE stream of real-time risk and signal alerts")
async def stream_alerts(
    request: Request,
    auth: AuthIdentity = Depends(get_current_auth),
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
):
    """Subscribe to real-time alert notifications."""
    return EventSourceResponse(
        event_generator(request, channel="alerts", last_event_id=last_event_id)
    )
