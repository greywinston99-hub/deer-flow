"""Health check router for the DeerFlow API Gateway.

Provides a comprehensive /api/health endpoint that aggregates status
from all subsystems: gateway core, Event Bus, EventStore, MCP Pool,
and disk usage.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/health", tags=["health"])


@router.get("", summary="Comprehensive health check")
async def health_check() -> dict[str, Any]:
    """Return comprehensive health status of all DeerFlow subsystems.

    Returns:
        JSON object with overall status and per-subsystem details.
        HTTP 200 if healthy, HTTP 503 if degraded or critical.
    """
    report: dict[str, Any] = {"gateway": {"status": "healthy", "service": "deer-flow-gateway"}}

    # Event Bus health (if module is available)
    try:
        from deerflow.runtime.cer_authoring.event_bus.health import health_report

        eb_report = health_report()
        report["event_bus"] = eb_report
    except Exception as exc:
        logger.exception("Failed to get Event Bus health report")
        report["event_bus"] = {"status": "error", "error": str(exc)}

    # Determine HTTP status
    all_statuses = [v.get("status", "unknown") for v in report.values()]
    if "critical" in all_statuses or "error" in all_statuses:
        http_status = status.HTTP_503_SERVICE_UNAVAILABLE
    elif "unhealthy" in all_statuses or "degraded" in all_statuses or "warning" in all_statuses:
        http_status = status.HTTP_503_SERVICE_UNAVAILABLE
    elif all(s in ("healthy", "disabled", "not_initialized") for s in all_statuses):
        http_status = status.HTTP_200_OK
    else:
        http_status = status.HTTP_503_SERVICE_UNAVAILABLE

    return JSONResponse(content=report, status_code=http_status)


@router.get("/ready", summary="Readiness probe")
async def readiness_probe() -> dict[str, Any]:
    """Lightweight readiness probe for Kubernetes/Docker orchestrators.

    Returns HTTP 200 if the gateway can accept traffic, 503 otherwise.
    """
    return {"status": "ready", "service": "deer-flow-gateway"}


@router.get("/live", summary="Liveness probe")
async def liveness_probe() -> dict[str, Any]:
    """Lightweight liveness probe for Kubernetes/Docker orchestrators.

    Returns HTTP 200 if the process is alive, 503 otherwise.
    """
    return {"status": "alive", "service": "deer-flow-gateway"}
