# 🏛️ Legacy Streamlit Dashboard (Retired in v3.0)

As specified in Phase 9 of the Platform v3.0 Quantitative Intelligence upgrade roadmap, `apps/dashboard` has been retired in favor of the production Next.js 15 quantitative intelligence workstation (`apps/web`).

### Migration Summary:
- **Container Infrastructure**: `docker/Dockerfile.dashboard` removed from repo; replaced with multi-stage production `docker/Dockerfile.web`.
- **Service Orchestration**: `docker-compose.yml` replaced the `dashboard` service with `web` (Next.js container exposing port 3000) and wired behind the Caddy reverse proxy.
- **Reverse Proxy**: `docker/Caddyfile` routes all non-API traffic to `web:3000` with WebSocket and SSE relay headers.
- **Frontend Architecture**: Modernized to Next.js App Router, TypeScript, TanStack Virtual tables (500+ assets at 60fps), TradingView Lightweight Charts, Apache ECharts, SSE reactive event streaming, and strict zero-fake-data invariants.
- **Archival Purpose**: This directory and its `data_layer.py` are preserved solely for legacy audit reference and historical regression test compliance.
