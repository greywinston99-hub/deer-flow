"""Event schema for the Event Bus hybrid architecture.

Defines Event types, Event model, and validation for all events flowing
through the LangGraph + Event Bus system.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class EventType(str, Enum):
    """All event types in the CER Authoring Event Bus.

    REQUESTED events are published by LangGraph nodes (coordinators).
    COMPLETED events are published by workers after processing.
    WORKER_* events are internal lifecycle events.
    """

    # ── Coordinator → Event Bus (task requests) ──
    SOTA_SEARCH_REQUESTED = "sota_search.requested"
    EVIDENCE_BATCH_REQUESTED = "evidence_batch.requested"
    VIGILANCE_SEARCH_REQUESTED = "vigilance_search.requested"
    FULLTEXT_REQUESTED = "fulltext.requested"

    # ── Worker → Event Bus (task completions) ──
    SOTA_SEARCH_COMPLETED = "sota_search.completed"
    EVIDENCE_BATCH_COMPLETED = "evidence_batch.completed"
    VIGILANCE_SEARCH_COMPLETED = "vigilance_search.completed"
    FULLTEXT_COMPLETED = "fulltext.completed"

    # ── Worker lifecycle ──
    WORKER_STARTED = "worker.started"
    WORKER_COMPLETED = "worker.completed"
    WORKER_FAILED = "worker.failed"
    WORKER_CACHED = "worker.cached"

    # ── Progress streaming ──
    WORKER_PROGRESS = "worker.progress"


# Event types that are prohibited in advisory-only mode
# (Gate decisions, automatic triggers, state overwrites)
FORBIDDEN_EVENT_TYPES: set[str] = {
    "gate.decision.rework",
    "gate.decision.pass",
    "pipeline.trigger_restart",
    "feedback.apply_automatic",
    "state.overwrite_final",
}


@dataclass
class Event:
    """A single event in the CER Authoring Event Bus.

    All events carry advisory_only=true as a mandatory safety field.
    The correlation_id links events back to their originating LangGraph thread.
    """

    event_type: EventType
    payload: dict[str, Any]
    correlation_id: str = ""
    stage_id: str = ""
    spiral_round: int = 1
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    advisory_only: bool = True
    worker_id: str | None = None
    batch_id: int | None = None
    cache_key: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for storage/transmission."""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "correlation_id": self.correlation_id,
            "stage_id": self.stage_id,
            "spiral_round": self.spiral_round,
            "payload": self.payload,
            "timestamp": self.timestamp.isoformat(),
            "advisory_only": self.advisory_only,
            "worker_id": self.worker_id,
            "batch_id": self.batch_id,
            "cache_key": self.cache_key,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Event:
        """Deserialize from dict."""
        return cls(
            event_type=EventType(data["event_type"]),
            payload=data.get("payload", {}),
            correlation_id=data.get("correlation_id", ""),
            stage_id=data.get("stage_id", ""),
            spiral_round=data.get("spiral_round", 1),
            event_id=data.get("event_id", str(uuid.uuid4())),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            advisory_only=data.get("advisory_only", True),
            worker_id=data.get("worker_id"),
            batch_id=data.get("batch_id"),
            cache_key=data.get("cache_key"),
        )


# Convenience constructors for common event patterns

def evidence_batch_requested(
    batch_id: int,
    articles: list[dict[str, Any]],
    state_snapshot: dict[str, Any],
    correlation_id: str = "",
    stage_id: str = "evidence_appraisal",
    spiral_round: int = 1,
) -> Event:
    """Create an EVIDENCE_BATCH_REQUESTED event."""
    return Event(
        event_type=EventType.EVIDENCE_BATCH_REQUESTED,
        payload={
            "batch_id": batch_id,
            "articles": articles,
            "state_snapshot": state_snapshot,
        },
        correlation_id=correlation_id,
        stage_id=stage_id,
        spiral_round=spiral_round,
        batch_id=batch_id,
    )


def evidence_batch_completed(
    batch_id: int,
    evidence: list[dict[str, Any]],
    appraisals: list[dict[str, Any]],
    correlation_id: str = "",
    stage_id: str = "evidence_appraisal",
    spiral_round: int = 1,
    worker_id: str | None = None,
    cache_hits: int = 0,
    cache_misses: int = 0,
) -> Event:
    """Create an EVIDENCE_BATCH_COMPLETED event."""
    return Event(
        event_type=EventType.EVIDENCE_BATCH_COMPLETED,
        payload={
            "batch_id": batch_id,
            "evidence": evidence,
            "appraisals": appraisals,
            "cache_hits": cache_hits,
            "cache_misses": cache_misses,
        },
        correlation_id=correlation_id,
        stage_id=stage_id,
        spiral_round=spiral_round,
        batch_id=batch_id,
        worker_id=worker_id,
    )


def worker_progress(
    stage_id: str,
    completed: int,
    total: int,
    correlation_id: str = "",
) -> Event:
    """Create a WORKER_PROGRESS event for SSE streaming."""
    return Event(
        event_type=EventType.WORKER_PROGRESS,
        payload={"completed": completed, "total": total, "stage_id": stage_id},
        correlation_id=correlation_id,
        stage_id=stage_id,
    )
