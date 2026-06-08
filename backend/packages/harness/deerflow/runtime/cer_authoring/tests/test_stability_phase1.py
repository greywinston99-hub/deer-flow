"""Tests for Phase 1 stability improvements:
- EventStore auto-purge
- Health check aggregation
"""

from __future__ import annotations

import os
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from deerflow.runtime.cer_authoring.event_bus.event_store import EventStore
from deerflow.runtime.cer_authoring.event_bus.health import health_report, _disk_usage_percent
from deerflow.runtime.cer_authoring.event_bus.schema import Event, EventType


class TestEventStoreAutoPurge:
    """Test automatic size-based event purging."""

    def test_get_db_size_mb_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            store = EventStore(str(db_path))
            assert store.get_db_size_mb() < 1.0

    def test_get_db_size_mb_after_inserts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            store = EventStore(str(db_path))
            for i in range(100):
                event = Event(
                    event_type=EventType.EVIDENCE_BATCH_COMPLETED,
                    payload={"test": "x" * 1000},
                    correlation_id="test-thread",
                )
                store.insert(event)
            assert store.count() == 100
            size = store.get_db_size_mb()
            assert size > 0

    def test_auto_purge_triggered_when_over_threshold(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            store = EventStore(str(db_path))

            # Insert many events to grow the DB
            for i in range(500):
                event = Event(
                    event_type=EventType.EVIDENCE_BATCH_COMPLETED,
                    payload={"test": "x" * 2000, "index": i},
                    correlation_id="test-thread",
                )
                store.insert(event)

            count_before = store.count()
            assert count_before == 500

            # Force a purge by setting a very low max threshold
            with patch(
                "deerflow.runtime.cer_authoring.event_bus.event_store._MAX_DB_SIZE_MB",
                0,
            ):
                with patch(
                    "deerflow.runtime.cer_authoring.event_bus.event_store._PURGE_TARGET_MB",
                    0,
                ):
                    deleted = store._maybe_purge()

            assert deleted > 0
            assert store.count() < count_before

    def test_delete_old_events_vacuum(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            store = EventStore(str(db_path))

            # Insert old and new events
            from datetime import datetime, timezone, timedelta

            old_time = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()
            new_time = datetime.now(timezone.utc).isoformat()

            with sqlite3.connect(str(db_path)) as conn:
                conn.execute(
                    "INSERT INTO events (event_id, event_type, timestamp_iso) VALUES (?, ?, ?)",
                    ("old-1", EventType.EVIDENCE_BATCH_COMPLETED.value, old_time),
                )
                conn.execute(
                    "INSERT INTO events (event_id, event_type, timestamp_iso) VALUES (?, ?, ?)",
                    ("new-1", EventType.EVIDENCE_BATCH_COMPLETED.value, new_time),
                )
                conn.commit()

            assert store.count() == 2
            deleted = store.delete_old_events(days=30)
            assert deleted == 1
            assert store.count() == 1


class TestHealthReport:
    """Test health check aggregation."""

    def test_health_report_structure(self) -> None:
        report = health_report()
        assert "status" in report
        assert "event_bus" in report
        assert "event_store" in report
        assert "mcp_pool" in report
        assert "disk" in report

    def test_disk_usage_percent(self) -> None:
        # Should return a value between 0 and 100 for the root filesystem
        pct = _disk_usage_percent("/")
        assert 0 <= pct <= 100

    def test_event_store_health_healthy(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            store = EventStore(str(db_path))
            size_mb = store.get_db_size_mb()
            assert size_mb < 500  # Should be healthy

    def test_event_store_health_warning(self) -> None:
        # Mock a large DB size
        with patch.object(EventStore, "get_db_size_mb", return_value=600.0):
            with patch.object(EventStore, "count", return_value=1000):
                from deerflow.runtime.cer_authoring.event_bus.health import _event_store_health

                health = _event_store_health()
                assert health["status"] == "warning"
