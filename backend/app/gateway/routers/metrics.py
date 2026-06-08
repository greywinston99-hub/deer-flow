"""Metrics router for the DeerFlow API Gateway.

Exposes in-memory metrics collected by the Event Bus metrics subsystem.
No external dependencies (Prometheus/statsd not required).
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/metrics", tags=["metrics"])


@router.get("", summary="Event Bus metrics snapshot")
async def metrics_snapshot() -> dict[str, Any]:
    """Return a snapshot of all Event Bus metrics.

    Includes counters, gauges, and histograms for:
    - event_bus.events_published_total
    - worker.processing_duration_ms
    - spiral_cache.hits_total / misses_total
    - mcp_pool.calls_total / call_duration_ms
    """
    try:
        from deerflow.runtime.cer_authoring.event_bus.metrics import metrics_collector

        return metrics_collector.snapshot()
    except Exception as exc:
        logger.exception("Failed to collect metrics")
        return {"error": str(exc)}


@router.post("/reset", summary="Reset all metrics", include_in_schema=False)
async def reset_metrics() -> dict[str, str]:
    """Reset all metrics counters. Used in tests."""
    try:
        from deerflow.runtime.cer_authoring.event_bus.metrics import metrics_collector

        metrics_collector.reset()
        return {"status": "reset"}
    except Exception as exc:
        logger.exception("Failed to reset metrics")
        return {"error": str(exc)}
