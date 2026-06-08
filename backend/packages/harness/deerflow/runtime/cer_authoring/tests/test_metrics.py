"""Tests for the metrics collector."""

from __future__ import annotations

from deerflow.runtime.cer_authoring.event_bus.metrics import MetricsCollector


class TestMetricsCollector:
    """Test in-memory metrics collection."""

    def test_counter(self) -> None:
        mc = MetricsCollector()
        mc.inc("test.counter", labels={"a": "1"})
        mc.inc("test.counter", value=3, labels={"a": "1"})
        assert mc.get_counter("test.counter", labels={"a": "1"}) == 4

    def test_gauge(self) -> None:
        mc = MetricsCollector()
        mc.set_gauge("test.gauge", 42.0, labels={"b": "2"})
        assert mc.get_gauge("test.gauge", labels={"b": "2"}) == 42.0

    def test_histogram(self) -> None:
        mc = MetricsCollector()
        mc.observe("test.hist", 10.0)
        mc.observe("test.hist", 20.0)
        stats = mc.get_histogram_stats("test.hist")
        assert stats["count"] == 2
        assert stats["sum"] == 30.0
        assert stats["avg"] == 15.0

    def test_snapshot(self) -> None:
        mc = MetricsCollector()
        mc.inc("c1", labels={"x": "y"})
        mc.set_gauge("g1", 1.0)
        snapshot = mc.snapshot()
        assert "counters" in snapshot
        assert "gauges" in snapshot
        assert "histograms" in snapshot
        assert "uptime_seconds" in snapshot

    def test_reset(self) -> None:
        mc = MetricsCollector()
        mc.inc("c1")
        mc.reset()
        assert mc.get_counter("c1") == 0
