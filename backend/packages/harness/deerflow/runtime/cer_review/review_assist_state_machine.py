"""CER Review Assist — State Machine.

Implements:
- 9-state review-assist pipeline
- State persistence to review_state.json
- Append-only audit log (review_session_log.jsonl)
- Transition validation
- Blocked state handling

Follows the same pattern as IntakeStateMachine.
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ── State Definitions ────────────────────────────────────────────────────────────


class ReviewAssistState(Enum):
    PROJECT_LOADED = "project_loaded"
    EVIDENCE_INVENTORY_DONE = "evidence_inventory_done"
    GAP_ANALYSIS_DONE = "gap_analysis_done"
    SEVERITY_SYNTHESIS_DONE = "severity_synthesis_done"
    HUMAN_GATE_PENDING = "human_gate_pending"
    HUMAN_GATE_APPROVED = "human_gate_approved"
    HUMAN_GATE_REJECTED = "human_gate_rejected"
    REVIEW_PACKAGE_LOCKED = "review_package_locked"
    READY_FOR_HUMAN_REVIEW = "ready_for_human_review"
    BLOCKED = "blocked"


# ── Valid Transitions ───────────────────────────────────────────────────────────


VALID_TRANSITIONS: dict[ReviewAssistState, list[ReviewAssistState]] = {
    ReviewAssistState.PROJECT_LOADED: [
        ReviewAssistState.EVIDENCE_INVENTORY_DONE,
        ReviewAssistState.BLOCKED,
    ],
    ReviewAssistState.EVIDENCE_INVENTORY_DONE: [
        ReviewAssistState.GAP_ANALYSIS_DONE,
        ReviewAssistState.BLOCKED,
    ],
    ReviewAssistState.GAP_ANALYSIS_DONE: [
        ReviewAssistState.SEVERITY_SYNTHESIS_DONE,
        ReviewAssistState.BLOCKED,
    ],
    ReviewAssistState.SEVERITY_SYNTHESIS_DONE: [
        ReviewAssistState.HUMAN_GATE_PENDING,
        ReviewAssistState.BLOCKED,
    ],
    ReviewAssistState.HUMAN_GATE_PENDING: [
        ReviewAssistState.HUMAN_GATE_APPROVED,
        ReviewAssistState.HUMAN_GATE_REJECTED,
    ],
    ReviewAssistState.HUMAN_GATE_APPROVED: [
        ReviewAssistState.REVIEW_PACKAGE_LOCKED,
    ],
    ReviewAssistState.REVIEW_PACKAGE_LOCKED: [
        ReviewAssistState.READY_FOR_HUMAN_REVIEW,
        ReviewAssistState.BLOCKED,
    ],
    ReviewAssistState.READY_FOR_HUMAN_REVIEW: [],
    ReviewAssistState.HUMAN_GATE_REJECTED: [
        ReviewAssistState.EVIDENCE_INVENTORY_DONE,
        ReviewAssistState.GAP_ANALYSIS_DONE,
    ],
    ReviewAssistState.BLOCKED: [
        ReviewAssistState.PROJECT_LOADED,
        ReviewAssistState.EVIDENCE_INVENTORY_DONE,
        ReviewAssistState.GAP_ANALYSIS_DONE,
    ],
}


# ── State Machine ────────────────────────────────────────────────────────────────


@dataclass
class ReviewAssistStateMachine:
    """CER Review Assist State Machine.

    Manages 9-state review-assist pipeline with persistence and audit logging.
    """

    project_id: str
    review_session_id: str
    artifact_root: Path
    _current_state: ReviewAssistState = field(default=ReviewAssistState.PROJECT_LOADED)
    _history: list[dict[str, Any]] = field(default_factory=list)
    _artifacts: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_artifacts(
        cls,
        project_id: str,
        artifact_root: Path,
        review_session_id: str | None = None,
    ) -> ReviewAssistStateMachine:
        """Load existing state machine from artifact root, or create new one."""
        state_file = artifact_root / "review_state.json"
        if state_file.exists():
            data = json.loads(state_file.read_text())
            if review_session_id is None or data.get("review_session_id") == review_session_id:
                return cls.from_dict(project_id, artifact_root, data)

        session_id = review_session_id or _make_session_id()
        machine = cls(
            project_id=project_id,
            review_session_id=session_id,
            artifact_root=artifact_root,
        )
        return machine

    @classmethod
    def from_dict(
        cls,
        project_id: str,
        artifact_root: Path,
        data: dict[str, Any],
    ) -> ReviewAssistStateMachine:
        """Deserialize from a plain dict (used by LangGraph checkpointer)."""
        return cls(
            project_id=project_id,
            review_session_id=data.get("review_session_id", _make_session_id()),
            artifact_root=artifact_root,
            _current_state=ReviewAssistState(data.get("current_state", "project_loaded")),
            _history=data.get("history", []),
            _artifacts=data.get("artifacts", {}),
        )

    @property
    def current_state(self) -> ReviewAssistState:
        return self._current_state

    @property
    def history(self) -> list[dict[str, Any]]:
        return self._history

    @property
    def artifacts(self) -> dict[str, str]:
        return self._artifacts

    def transition(self, to_state: ReviewAssistState, *, reason: str = "") -> None:
        """Transition to a new state with validation."""
        valid_next = VALID_TRANSITIONS.get(self._current_state, [])
        if to_state not in valid_next:
            raise InvalidTransitionError(
                f"Cannot transition from {self._current_state.value} to {to_state.value}. "
                f"Valid transitions: {[s.value for s in valid_next]}"
            )

        timestamp = datetime.now(timezone.utc).isoformat()
        entry = {
            "from_state": self._current_state.value,
            "to_state": to_state.value,
            "reason": reason,
            "timestamp": timestamp,
        }
        self._history.append(entry)
        self._current_state = to_state
        logger.info(
            "[%s] State transition: %s -> %s (%s)",
            self.review_session_id,
            entry["from_state"],
            entry["to_state"],
            reason,
        )
        self._persist()

    def record_artifact(self, artifact_key: str, artifact_path: str) -> None:
        """Record an artifact path produced by a stage."""
        self._artifacts[artifact_key] = artifact_path
        self._persist()

    def is_blocked(self) -> bool:
        return self._current_state == ReviewAssistState.BLOCKED

    def is_human_gate_waiting(self) -> bool:
        return self._current_state == ReviewAssistState.HUMAN_GATE_PENDING

    def can_proceed_to_human_review(self) -> bool:
        return self._current_state == ReviewAssistState.READY_FOR_HUMAN_REVIEW

    def _persist(self) -> None:
        """Write state to review_state.json atomically."""
        self.artifact_root.mkdir(parents=True, exist_ok=True)
        state_file = self.artifact_root / "review_state.json"
        data = {
            "project_id": self.project_id,
            "review_session_id": self.review_session_id,
            "current_state": self._current_state.value,
            "artifacts": self._artifacts,
            "history": self._history,
            "persisted_at": datetime.now(timezone.utc).isoformat(),
        }
        temp_path = state_file.with_suffix(".json.tmp")
        temp_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        temp_path.replace(state_file)

    def append_log(self, entry: dict[str, Any]) -> None:
        """Append an entry to the append-only session log."""
        self.artifact_root.mkdir(parents=True, exist_ok=True)
        log_file = self.artifact_root / "review_session_log.jsonl"
        entry["timestamp"] = datetime.now(timezone.utc).isoformat()
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "review_session_id": self.review_session_id,
            "current_state": self._current_state.value,
            "artifacts": self._artifacts,
            "history": self._history,
        }


# ── Exceptions ──────────────────────────────────────────────────────────────────


class ReviewAssistStateError(Exception):
    """Base exception for review assist state machine errors."""
    pass


class InvalidTransitionError(ReviewAssistStateError):
    """Raised when an invalid state transition is attempted."""
    pass


# ── Helpers ─────────────────────────────────────────────────────────────────────


def _make_session_id() -> str:
    return f"ra-{uuid.uuid4().hex[:8].upper()}"
