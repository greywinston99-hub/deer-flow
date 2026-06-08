"""SQLite-backed persistent Event Store for the CER Authoring Event Bus.

Replaces the in-memory event list with durable SQLite storage, enabling:
- Cross-process event sharing
- Cross-restart Spiral Cache persistence
- Complete audit trail retention
- Queryable event history

Auto-purge: Events are automatically purged when the database exceeds
a configured size threshold, preventing unbounded disk growth.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import tempfile
from pathlib import Path
from typing import Any

from deerflow.runtime.cer_authoring.event_bus.schema import Event, EventType

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = str(Path.home() / ".deerflow" / "event_store.db")
_READONLY_SQLITE_MARKERS = (
    "readonly database",
    "unable to open database file",
    "attempt to write a readonly database",
)

# Auto-purge configuration
_AUTO_PURGE_ENABLED = os.getenv("CER_AUTHORING_EVENT_STORE_AUTO_PURGE", "1") == "1"
_MAX_DB_SIZE_MB = int(os.getenv("CER_AUTHORING_EVENT_STORE_MAX_MB", "500"))
_PURGE_TARGET_MB = int(os.getenv("CER_AUTHORING_EVENT_STORE_PURGE_TARGET_MB", "300"))
_INSERT_CHECK_INTERVAL = int(os.getenv("CER_AUTHORING_EVENT_STORE_CHECK_INTERVAL", "100"))


class EventStore:
    """Persistent SQLite store for Event Bus events.

    Each event is stored as a row with full payload JSON, enabling:
    - Audit queries by correlation_id, stage_id, event_type
    - Spiral Cache lookups by cache_key + spiral_round
    - Time-range queries for reporting

    Auto-purge is triggered when the database file exceeds
    CER_AUTHORING_EVENT_STORE_MAX_MB (default 500 MB). The oldest
    20% of events are deleted until the database falls below
    CER_AUTHORING_EVENT_STORE_PURGE_TARGET_MB (default 300 MB).
    """

    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = db_path or DEFAULT_DB_PATH
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._insert_count = 0
        try:
            self._init_db()
        except sqlite3.OperationalError as exc:
            if not _is_sqlite_writable_path_error(exc) or db_path:
                raise
            fallback = _fallback_event_store_path()
            logger.warning(
                "EventStore default path %s is not writable (%s); falling back to %s",
                self.db_path,
                exc,
                fallback,
            )
            self.db_path = fallback
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
            self._init_db()

    def _init_db(self) -> None:
        """Create tables and indexes if they don't exist."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS events (
                    event_id TEXT PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    correlation_id TEXT,
                    stage_id TEXT,
                    spiral_round INTEGER DEFAULT 1,
                    payload_json TEXT,
                    timestamp_iso TEXT,
                    advisory_only INTEGER DEFAULT 1,
                    worker_id TEXT,
                    batch_id INTEGER,
                    cache_key TEXT
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_events_correlation ON events(correlation_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_events_stage ON events(stage_id, correlation_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_events_cache ON events(cache_key, spiral_round)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp_iso)"
            )
            conn.commit()
        logger.debug("EventStore initialized at %s", self.db_path)

    def insert(self, event: Event) -> None:
        """Persist a single event.

        Triggers automatic size-based purge every N inserts if enabled.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO events
                    (event_id, event_type, correlation_id, stage_id, spiral_round,
                     payload_json, timestamp_iso, advisory_only, worker_id, batch_id, cache_key)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event.event_id,
                        event.event_type.value,
                        event.correlation_id,
                        event.stage_id,
                        event.spiral_round,
                        json.dumps(event.payload, ensure_ascii=False, default=str),
                        event.timestamp.isoformat(),
                        1 if event.advisory_only else 0,
                        event.worker_id,
                        event.batch_id,
                        event.cache_key,
                    ),
                )
                conn.commit()
        except sqlite3.OperationalError as exc:
            self._fallback_after_writable_path_error(exc)
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO events
                    (event_id, event_type, correlation_id, stage_id, spiral_round,
                     payload_json, timestamp_iso, advisory_only, worker_id, batch_id, cache_key)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event.event_id,
                        event.event_type.value,
                        event.correlation_id,
                        event.stage_id,
                        event.spiral_round,
                        json.dumps(event.payload, ensure_ascii=False, default=str),
                        event.timestamp.isoformat(),
                        1 if event.advisory_only else 0,
                        event.worker_id,
                        event.batch_id,
                        event.cache_key,
                    ),
                )
                conn.commit()

        # Auto-purge check
        if _AUTO_PURGE_ENABLED:
            self._insert_count += 1
            if self._insert_count % _INSERT_CHECK_INTERVAL == 0:
                self._maybe_purge()

    def get_db_size_mb(self) -> float:
        """Return the current database file size in megabytes."""
        try:
            size_bytes = Path(self.db_path).stat().st_size
            return size_bytes / (1024 * 1024)
        except OSError:
            return 0.0

    def _maybe_purge(self) -> int:
        """Check size and purge oldest events if over threshold.

        Returns the number of events deleted.
        """
        size_mb = self.get_db_size_mb()
        if size_mb <= _MAX_DB_SIZE_MB:
            return 0

        logger.warning(
            "EventStore size %.1f MB exceeds threshold %d MB; purging oldest events",
            size_mb, _MAX_DB_SIZE_MB,
        )

        deleted = self._purge_oldest_events()
        new_size_mb = self.get_db_size_mb()
        logger.info(
            "EventStore purged %d events; new size %.1f MB",
            deleted, new_size_mb,
        )
        return deleted

    def _purge_oldest_events(self) -> int:
        """Delete the oldest 20% of events until DB is below target size.

        Uses a batched approach to avoid locking the DB for too long.
        """
        total_deleted = 0
        max_iterations = 10
        for _ in range(max_iterations):
            size_mb = self.get_db_size_mb()
            if size_mb <= _PURGE_TARGET_MB:
                break

            with sqlite3.connect(self.db_path) as conn:
                # Count total events
                row = conn.execute("SELECT COUNT(*) FROM events").fetchone()
                total = row[0] if row else 0
                if total == 0:
                    break

                # Delete oldest 20%
                to_delete = max(1, total // 5)
                cursor = conn.execute(
                    """
                    DELETE FROM events
                    WHERE event_id IN (
                        SELECT event_id FROM events
                        ORDER BY timestamp_iso ASC
                        LIMIT ?
                    )
                    """,
                    (to_delete,),
                )
                conn.commit()
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("VACUUM")
            total_deleted += cursor.rowcount

        return total_deleted

    def query(
        self,
        event_type: EventType | None = None,
        correlation_id: str | None = None,
        stage_id: str | None = None,
        cache_key: str | None = None,
        spiral_round_lt: int | None = None,
        spiral_round_eq: int | None = None,
        limit: int = 1000,
    ) -> list[Event]:
        """Query events with flexible filters.

        Args:
            event_type: Filter by event type.
            correlation_id: Filter by LangGraph thread_id.
            stage_id: Filter by node name.
            cache_key: Filter by cache key (for Spiral Cache lookups).
            spiral_round_lt: Only rounds strictly less than this value.
            spiral_round_eq: Exact spiral round match.
            limit: Max rows to return.

        Returns:
            List of Event objects ordered by timestamp (newest first).
        """
        conditions: list[str] = []
        params: list[Any] = []

        if event_type is not None:
            conditions.append("event_type = ?")
            params.append(event_type.value)
        if correlation_id is not None:
            conditions.append("correlation_id = ?")
            params.append(correlation_id)
        if stage_id is not None:
            conditions.append("stage_id = ?")
            params.append(stage_id)
        if cache_key is not None:
            conditions.append("cache_key = ?")
            params.append(cache_key)
        if spiral_round_lt is not None:
            conditions.append("spiral_round < ?")
            params.append(spiral_round_lt)
        if spiral_round_eq is not None:
            conditions.append("spiral_round = ?")
            params.append(spiral_round_eq)

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        sql = f"""
            SELECT event_id, event_type, correlation_id, stage_id, spiral_round,
                   payload_json, timestamp_iso, advisory_only, worker_id, batch_id, cache_key
            FROM events
            {where_clause}
            ORDER BY timestamp_iso DESC
            LIMIT ?
        """
        params.append(limit)

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(sql, params).fetchall()

        return [_row_to_event(dict(row)) for row in rows]

    def get_by_event_id(self, event_id: str) -> Event | None:
        """Fetch a single event by its ID."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM events WHERE event_id = ?", (event_id,)
            ).fetchone()
        return _row_to_event(dict(row)) if row else None

    def delete_old_events(self, days: int = 30) -> int:
        """Delete events older than N days. Returns count deleted."""
        from datetime import datetime, timezone, timedelta

        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("DELETE FROM events WHERE timestamp_iso < ?", (cutoff,))
            conn.commit()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("VACUUM")
            deleted = cursor.rowcount
        logger.info("EventStore purged %d events older than %d days", deleted, days)
        return deleted

    def count(self) -> int:
        """Return total number of events in store."""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute("SELECT COUNT(*) FROM events").fetchone()
        return row[0] if row else 0

    def clear(self) -> None:
        """Delete all events. Use with caution (mainly for tests)."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM events")
                conn.commit()
        except sqlite3.OperationalError as exc:
            self._fallback_after_writable_path_error(exc)
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM events")
                conn.commit()
        logger.warning("EventStore cleared all events")

    def _fallback_after_writable_path_error(self, exc: sqlite3.OperationalError) -> None:
        if not _is_sqlite_writable_path_error(exc):
            raise exc
        fallback = _fallback_event_store_path()
        if self.db_path == fallback:
            raise exc
        logger.warning(
            "EventStore path %s became unwritable (%s); falling back to %s",
            self.db_path,
            exc,
            fallback,
        )
        self.db_path = fallback
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()


def _row_to_event(row: dict[str, Any]) -> Event:
    """Convert a SQLite row dict to an Event object."""
    from datetime import datetime

    return Event(
        event_id=row["event_id"],
        event_type=EventType(row["event_type"]),
        correlation_id=row["correlation_id"] or "",
        stage_id=row["stage_id"] or "",
        spiral_round=row["spiral_round"] or 1,
        payload=json.loads(row["payload_json"] or "{}"),
        timestamp=datetime.fromisoformat(row["timestamp_iso"]),
        advisory_only=bool(row["advisory_only"]),
        worker_id=row["worker_id"],
        batch_id=row["batch_id"],
        cache_key=row["cache_key"],
    )


def _is_sqlite_writable_path_error(exc: sqlite3.OperationalError) -> bool:
    message = str(exc).lower()
    return any(marker in message for marker in _READONLY_SQLITE_MARKERS)


def _fallback_event_store_path() -> str:
    base = Path(os.getenv("CER_AUTHORING_EVENT_STORE_FALLBACK_DIR") or tempfile.gettempdir())
    uid = os.getuid() if hasattr(os, "getuid") else "user"
    return str(base / "deerflow" / f"event_store_{uid}.db")
