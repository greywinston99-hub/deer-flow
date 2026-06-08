"""Health check utilities for the CER Authoring Event Bus.

Aggregates health status from all Event Bus subsystems:
- EventBus core (running state, queue depth)
- EventStore (DB size, event count)
- MCP Process Pool (alive processes, queue depth)
- Disk space monitoring

Usage:
    from deerflow.runtime.cer_authoring.event_bus.health import health_report

    report = health_report()
    if report["status"] != "healthy":
        alert_ops_team(report)
"""

from __future__ import annotations

import logging
import os
import shutil
from typing import Any

logger = logging.getLogger(__name__)

_DISK_ALERT_THRESHOLD = int(os.getenv("CER_AUTHORING_DISK_ALERT_THRESHOLD", "80"))


def _disk_usage_percent(path: str = "/") -> float:
    """Return disk usage percentage for the given path."""
    try:
        usage = shutil.disk_usage(path)
        return (usage.used / usage.total) * 100
    except OSError:
        return 0.0


def _event_bus_health() -> dict[str, Any]:
    """Check EventBus core health."""
    try:
        from deerflow.runtime.cer_authoring.event_bus.core import _event_bus_instance

        if _event_bus_instance is None:
            return {"status": "not_initialized", "running": False}

        bus = _event_bus_instance
        queue_size = bus._queue.qsize() if hasattr(bus._queue, "qsize") else -1
        return {
            "status": "healthy" if bus._running else "stopped",
            "running": bus._running,
            "queue_size": queue_size,
            "dispatch_task_alive": bus._dispatch_task is not None and not bus._dispatch_task.done(),
        }
    except Exception as exc:
        logger.exception("EventBus health check failed")
        return {"status": "error", "error": str(exc)}


def _event_store_health() -> dict[str, Any]:
    """Check EventStore (SQLite) health."""
    try:
        from deerflow.runtime.cer_authoring.event_bus.event_store import EventStore

        store = EventStore()
        size_mb = store.get_db_size_mb()
        event_count = store.count()
        size_status = "healthy"
        if size_mb > 1000:
            size_status = "critical"
        elif size_mb > 500:
            size_status = "warning"

        return {
            "status": size_status,
            "db_path": store.db_path,
            "size_mb": round(size_mb, 2),
            "event_count": event_count,
        }
    except Exception as exc:
        logger.exception("EventStore health check failed")
        return {"status": "error", "error": str(exc)}


def _mcp_pool_health() -> dict[str, Any]:
    """Check MCP Process Pool health."""
    try:
        from deerflow.runtime.cer_authoring.mcp_pool import _pools, _MCP_POOL_ENABLED

        if not _MCP_POOL_ENABLED:
            return {"status": "disabled", "enabled": False}

        pools_status: dict[str, Any] = {}
        total_alive = 0
        total_size = 0
        for server, pool in _pools.items():
            # Snapshot queue state without consuming items
            queue_items: list[Any] = []
            alive = 0
            try:
                while True:
                    queue_items.append(pool._q.get_nowait())
            except Exception:
                pass
            for proc in queue_items:
                if proc.is_alive():
                    alive += 1
            # Return items to queue
            for proc in queue_items:
                pool._q.put_nowait(proc)

            size = pool.size
            total_alive += alive
            total_size += size
            pools_status[server] = {
                "alive": alive,
                "size": size,
                "status": "healthy" if alive > 0 else "degraded",
            }

        overall = "healthy" if total_alive == total_size else "degraded" if total_alive > 0 else "unhealthy"
        return {
            "status": overall,
            "enabled": True,
            "total_alive": total_alive,
            "total_size": total_size,
            "pools": pools_status,
        }
    except Exception as exc:
        logger.exception("MCP Pool health check failed")
        return {"status": "error", "error": str(exc)}


def _disk_health() -> dict[str, Any]:
    """Check disk space health."""
    try:
        from deerflow.runtime.cer_authoring.event_bus.event_store import DEFAULT_DB_PATH

        db_path = DEFAULT_DB_PATH
        disk_path = os.path.dirname(db_path) or "/"
        usage_pct = _disk_usage_percent(disk_path)
        status = "healthy"
        if usage_pct >= _DISK_ALERT_THRESHOLD + 10:
            status = "critical"
        elif usage_pct >= _DISK_ALERT_THRESHOLD:
            status = "warning"

        return {
            "status": status,
            "path": disk_path,
            "usage_percent": round(usage_pct, 1),
            "threshold_percent": _DISK_ALERT_THRESHOLD,
        }
    except Exception as exc:
        logger.exception("Disk health check failed")
        return {"status": "error", "error": str(exc)}


def health_report() -> dict[str, Any]:
    """Generate a comprehensive health report for all Event Bus subsystems.

    Returns:
        Dict with keys: status, event_bus, event_store, mcp_pool, disk.
        Top-level "status" is "healthy" only if all subsystems are healthy.
    """
    event_bus = _event_bus_health()
    event_store = _event_store_health()
    mcp_pool = _mcp_pool_health()
    disk = _disk_health()

    # Overall status: critical if any critical, warning if any warning/degraded,
    # healthy only if all healthy
    statuses = [
        event_bus.get("status", "unknown"),
        event_store.get("status", "unknown"),
        mcp_pool.get("status", "unknown"),
        disk.get("status", "unknown"),
    ]

    if "critical" in statuses or "error" in statuses:
        overall = "critical"
    elif "unhealthy" in statuses or "warning" in statuses or "degraded" in statuses:
        overall = "degraded"
    elif all(s == "healthy" for s in statuses):
        overall = "healthy"
    elif all(s in ("healthy", "disabled", "not_initialized") for s in statuses):
        overall = "healthy"
    else:
        overall = "unknown"

    return {
        "status": overall,
        "event_bus": event_bus,
        "event_store": event_store,
        "mcp_pool": mcp_pool,
        "disk": disk,
    }
