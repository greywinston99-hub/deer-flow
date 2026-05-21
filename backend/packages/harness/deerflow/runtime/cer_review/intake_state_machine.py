"""CER Raw Project Intake — State Machine

Implements:
- 15-state intake pipeline
- State persistence to intake_state.json
- Append-only audit log (intake_session_log.jsonl)
- Transition validation
- Blocked state handling

Frozen baseline: CER_RAW_PROJECT_INTAKE_WORKFLOW_STATE_MACHINE.md
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ── State Definitions ────────────────────────────────────────────────────────────


class IntakeState(str, Enum):
    RAW_UPLOADED = "raw_uploaded"
    INVENTORY_CREATED = "inventory_created"
    DEDUPE_COMPLETED = "dedupe_completed"
    PARSE_COMPLETED = "parse_completed"
    PDF_CHECKED = "pdf_checked"
    TYPE_DETECTION_DONE = "type_detection_done"
    CLASSIFICATION_COMPLETED = "classification_completed"
    COMPLETENESS_EVALUATED = "completeness_evaluated"
    CITATIONS_TRACED = "citations_traced"
    HUMAN_GATE_PENDING = "human_gate_pending"
    HUMAN_GATE_APPROVED = "human_gate_approved"
    HUMAN_GATE_REJECTED = "human_gate_rejected"
    EVIDENCE_PACK_LOCKED = "evidence_pack_locked"
    READY_FOR_CER_REVIEW = "ready_for_cer_review"
    BLOCKED = "blocked"


# ── Valid Transitions ───────────────────────────────────────────────────────────


VALID_TRANSITIONS: dict[IntakeState, list[IntakeState]] = {
    IntakeState.RAW_UPLOADED: [IntakeState.INVENTORY_CREATED, IntakeState.BLOCKED],
    IntakeState.INVENTORY_CREATED: [
        IntakeState.DEDUPE_COMPLETED,
        IntakeState.PARSE_COMPLETED,
        IntakeState.PDF_CHECKED,
        IntakeState.BLOCKED,
    ],
    IntakeState.DEDUPE_COMPLETED: [IntakeState.PARSE_COMPLETED, IntakeState.TYPE_DETECTION_DONE],
    IntakeState.PARSE_COMPLETED: [IntakeState.PDF_CHECKED, IntakeState.TYPE_DETECTION_DONE],
    IntakeState.PDF_CHECKED: [IntakeState.TYPE_DETECTION_DONE],
    IntakeState.TYPE_DETECTION_DONE: [IntakeState.CLASSIFICATION_COMPLETED],
    IntakeState.CLASSIFICATION_COMPLETED: [IntakeState.COMPLETENESS_EVALUATED],
    IntakeState.COMPLETENESS_EVALUATED: [IntakeState.CITATIONS_TRACED],
    IntakeState.CITATIONS_TRACED: [IntakeState.HUMAN_GATE_PENDING],
    IntakeState.HUMAN_GATE_PENDING: [
        IntakeState.HUMAN_GATE_APPROVED,
        IntakeState.HUMAN_GATE_REJECTED,
    ],
    IntakeState.HUMAN_GATE_APPROVED: [IntakeState.EVIDENCE_PACK_LOCKED],
    IntakeState.EVIDENCE_PACK_LOCKED: [IntakeState.READY_FOR_CER_REVIEW, IntakeState.BLOCKED],
    IntakeState.READY_FOR_CER_REVIEW: [],
    IntakeState.HUMAN_GATE_REJECTED: [IntakeState.RAW_UPLOADED],
    IntakeState.BLOCKED: [IntakeState.RAW_UPLOADED, IntakeState.INVENTORY_CREATED],
}


# ── State Machine ────────────────────────────────────────────────────────────────


@dataclass
class IntakeStateMachine:
    """CER Raw Project Intake State Machine.

    Manages 15-state intake pipeline with persistence and audit logging.
    """

    project_id: str
    intake_session_id: str
    artifact_root: Path
    _current_state: IntakeState = field(default=IntakeState.RAW_UPLOADED)
    _history: list[dict[str, Any]] = field(default_factory=list)
    _artifacts: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_artifacts(
        cls,
        project_id: str,
        artifact_root: Path,
        intake_session_id: str | None = None,
    ) -> IntakeStateMachine:
        """Load existing state machine from artifact root, or create new one."""
        state_file = artifact_root / "intake" / "intake_state.json"
        if state_file.exists():
            data = json.loads(state_file.read_text())
            machine = cls(
                project_id=project_id,
                intake_session_id=data["intake_session_id"],
                artifact_root=artifact_root,
                _current_state=IntakeState(data["current_state"]),
                _history=data.get("history", []),
                _artifacts=data.get("artifacts", {}),
            )
            return machine
        session_id = intake_session_id or _make_session_id()
        machine = cls(
            project_id=project_id,
            intake_session_id=session_id,
            artifact_root=artifact_root,
        )
        return machine

    @property
    def current_state(self) -> IntakeState:
        return self._current_state

    @property
    def history(self) -> list[dict[str, Any]]:
        return self._history

    @property
    def artifacts(self) -> dict[str, str]:
        return self._artifacts

    def transition(self, to_state: IntakeState, *, reason: str = "") -> None:
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
            f"[{self.intake_session_id}] State transition: {entry['from_state']} "
            f"→ {entry['to_state']} ({reason})"
        )
        self._persist()

    def record_artifact(self, artifact_key: str, artifact_path: str) -> None:
        """Record an artifact path produced by an agent."""
        self._artifacts[artifact_key] = artifact_path
        self._persist()

    def is_blocked(self) -> bool:
        return self._current_state == IntakeState.BLOCKED

    def is_human_gate_waiting(self) -> bool:
        return self._current_state == IntakeState.HUMAN_GATE_PENDING

    def can_proceed_to_cer_review(self) -> bool:
        return self._current_state == IntakeState.READY_FOR_CER_REVIEW

    def _persist(self) -> None:
        """Write state to intake_state.json atomically."""
        intake_dir = self.artifact_root / "intake"
        intake_dir.mkdir(parents=True, exist_ok=True)
        state_file = intake_dir / "intake_state.json"
        data = {
            "project_id": self.project_id,
            "intake_session_id": self.intake_session_id,
            "current_state": self._current_state.value,
            "artifacts": self._artifacts,
            "history": self._history,
            "persisted_at": datetime.now(timezone.utc).isoformat(),
        }
        # Atomic write
        temp_path = state_file.with_suffix(".json.tmp")
        temp_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        temp_path.replace(state_file)

    def append_log(self, entry: dict[str, Any]) -> None:
        """Append an entry to the append-only session log."""
        intake_dir = self.artifact_root / "intake"
        intake_dir.mkdir(parents=True, exist_ok=True)
        log_file = intake_dir / "intake_session_log.jsonl"
        entry["timestamp"] = datetime.now(timezone.utc).isoformat()
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "intake_session_id": self.intake_session_id,
            "current_state": self._current_state.value,
            "artifacts": self._artifacts,
            "history": self._history,
        }


# ── Exceptions ──────────────────────────────────────────────────────────────────


class IntakeStateError(Exception):
    """Base exception for intake state machine errors."""
    pass


class InvalidTransitionError(IntakeStateError):
    """Raised when an invalid state transition is attempted."""
    pass


# ── Helpers ─────────────────────────────────────────────────────────────────────


def _make_session_id() -> str:
    import uuid
    return f"intake-{uuid.uuid4().hex[:8].upper()}"
