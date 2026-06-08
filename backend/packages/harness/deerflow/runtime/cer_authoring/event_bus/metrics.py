"""Lightweight in-memory metrics for CER Authoring Event Bus.

No external dependencies (no Prometheus/statsd). Metrics are stored in
thread-safe counters and exposed via a simple /metrics endpoint.

Collected metrics:
- event_bus.events_published_total (by event_type)
- event_bus.events_processed_total (by event_type, worker_id)
- event_bus.queue_size (gauge)
- spiral_cache.hits_total
- spiral_cache.misses_total
- mcp_pool.calls_total (by server, status)
- mcp_pool.call_duration_ms (by server, status)
- worker.processing_duration_ms (by worker_type, event_type)
- circuit_breaker.state (by name)
- disk.usage_percent (gauge)

Usage:
    from deerflow.runtime.cer_authoring.event_bus.metrics import metrics_collector

    metrics_collector.inc("spiral_cache.hits_total")
    metrics_collector.observe("mcp_pool.call_duration_ms", 123.0, labels={"server": "nb-check"})
"""

from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict
from typing import Any

logger = logging.getLogger(__name__)


class MetricsCollector:
    """Thread-safe in-memory metrics collector."""

    def __init__(self) -> None:
        self._counters: dict[str, dict[frozenset, int]] = defaultdict(lambda: defaultdict(int))
        self._gauges: dict[str, dict[frozenset, float]] = defaultdict(lambda: defaultdict(float))
        self._histograms: dict[str, dict[frozenset, list[float]]] = defaultdict(lambda: defaultdict(list))
        self._lock = threading.Lock()
        self._start_time = time.time()

    def _labels_key(self, labels: dict[str, str] | None) -> frozenset:
        return frozenset((labels or {}).items())

    def inc(self, name: str, value: int = 1, labels: dict[str, str] | None = None) -> None:
        """Increment a counter."""
        with self._lock:
            self._counters[name][self._labels_key(labels)] += value

    def set_gauge(self, name: str, value: float, labels: dict[str, str] | None = None) -> None:
        """Set a gauge value."""
        with self._lock:
            self._gauges[name][self._labels_key(labels)] = value

    def observe(self, name: str, value: float, labels: dict[str, str] | None = None) -> None:
        """Observe a value in a histogram."""
        with self._lock:
            self._histograms[name][self._labels_key(labels)].append(value)

    def get_counter(self, name: str, labels: dict[str, str] | None = None) -> int:
        with self._lock:
            return self._counters[name][self._labels_key(labels)]

    def get_gauge(self, name: str, labels: dict[str, str] | None = None) -> float:
        with self._lock:
            return self._gauges[name][self._labels_key(labels)]

    def get_histogram_stats(self, name: str, labels: dict[str, str] | None = None) -> dict[str, float]:
        """Return count, sum, min, max, avg for a histogram."""
        with self._lock:
            values = self._histograms[name][self._labels_key(labels)]
        if not values:
            return {"count": 0, "sum": 0.0, "min": 0.0, "max": 0.0, "avg": 0.0}
        return {
            "count": len(values),
            "sum": sum(values),
            "min": min(values),
            "max": max(values),
            "avg": sum(values) / len(values),
        }

    def snapshot(self) -> dict[str, Any]:
        """Return a snapshot of all metrics."""
        with self._lock:
            counters = {
                name: {str(dict(k)): v for k, v in labels.items()}
                for name, labels in self._counters.items()
            }
            gauges = {
                name: {str(dict(k)): v for k, v in labels.items()}
                for name, labels in self._gauges.items()
            }
            histograms: dict[str, Any] = {}
            for name, labels in self._histograms.items():
                histograms[name] = {}
                for key, values in labels.items():
                    if not values:
                        stats = {"count": 0, "sum": 0.0, "min": 0.0, "max": 0.0, "avg": 0.0}
                    else:
                        stats = {
                            "count": len(values),
                            "sum": sum(values),
                            "min": min(values),
                            "max": max(values),
                            "avg": sum(values) / len(values),
                        }
                    histograms[name][str(dict(key))] = stats

        return {
            "uptime_seconds": round(time.time() - self._start_time, 2),
            "counters": counters,
            "gauges": gauges,
            "histograms": histograms,
        }

    def reset(self) -> None:
        """Clear all metrics. Useful in tests."""
        with self._lock:
            self._counters.clear()
            self._gauges.clear()
            self._histograms.clear()
            self._start_time = time.time()


# Global singleton
metrics_collector = MetricsCollector()
