"""Prometheus Metrics Collection and Exposition — Platform v3.0.

Provides standard Prometheus metric collectors for:
- Market data ingestion lag per exchange
- Quantitative factor scanner execution duration
- HTTP API request latency distribution
- Backtest async job queue depth
- Paper trading ledger reconciliation status
"""

import time
from collections.abc import Callable

from fastapi import Request, Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)
from starlette.middleware.base import BaseHTTPMiddleware

# 1. Ingestion lag per exchange in seconds
INGESTION_LAG_SECONDS = Gauge(
    "crypto_ingestion_lag_seconds",
    "Current market data ingestion lag per exchange venue in seconds",
    ["exchange"],
)

# 2. Scanner run duration
SCAN_DURATION_SECONDS = Histogram(
    "crypto_scan_duration_seconds",
    "Time taken to execute multi-factor quantitative ranking in seconds",
    buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0],
)

# 3. HTTP API request latency
API_REQUEST_LATENCY_SECONDS = Histogram(
    "crypto_api_request_latency_seconds",
    "HTTP API request duration in seconds",
    ["method", "endpoint", "status_code"],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
)

# 4. Job queue depth
JOB_QUEUE_DEPTH = Gauge(
    "crypto_job_queue_depth",
    "Number of asynchronous backtest or processing jobs by status",
    ["status"],
)

# 5. Ledger reconciliation status (1.0 = balanced, 0.0 = discrepancy detected)
LEDGER_RECONCILIATION_STATUS = Gauge(
    "crypto_ledger_reconciliation_status",
    "Paper trading accounting ledger reconciliation health (1=balanced, 0=tampered/discrepancy)",
    ["account_id"],
)

# Request counter
API_REQUESTS_TOTAL = Counter(
    "crypto_api_requests_total",
    "Total count of HTTP API requests processed",
    ["method", "endpoint", "status_code"],
)


class PrometheusMetricsMiddleware(BaseHTTPMiddleware):
    """Measures API request latency and counts requests for Prometheus observability."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Do not instrument metrics endpoint itself
        if request.url.path == "/metrics":
            return await call_next(request)

        start_time = time.time()
        response = await call_next(request)
        duration = time.time() - start_time

        # Normalize endpoint path for low-cardinality metric labels
        endpoint = request.url.path
        if endpoint.startswith("/api/v1/backtests/jobs/"):
            endpoint = "/api/v1/backtests/jobs/{job_id}"
        elif endpoint.startswith("/api/v1/assets/"):
            endpoint = "/api/v1/assets/{symbol}"

        status_str = str(response.status_code)
        method = request.method

        API_REQUEST_LATENCY_SECONDS.labels(
            method=method,
            endpoint=endpoint,
            status_code=status_str,
        ).observe(duration)

        API_REQUESTS_TOTAL.labels(
            method=method,
            endpoint=endpoint,
            status_code=status_str,
        ).inc()

        return response


def get_prometheus_metrics_response() -> Response:
    """Render Prometheus plaintext metrics format."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
