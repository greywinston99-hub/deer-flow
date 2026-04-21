"""BackflowRegistry — CER Evidence Backflow Candidate Lifecycle Management

This module implements the BackflowRegistry for managing evidence events
that flow back into running CER reviews.

SKELETON implementation per D1 Phase 1 scaffolding requirements.
NOT production code.

D0C Contract: CER_D0C_BACKFLOW_ASSET_LIFECYCLE_CLOSURE.md
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class CandidateState(str, Enum):
    """Backflow candidate state machine states."""

    NEW = "new"  # Raw event received, raw validation passed
    UNDER_REVIEW = "under_review"  # Runner acknowledged, awaiting assessment
    APPROVED = "approved"  # Evidence accepted, routes to relevant lane/step
    REJECTED = "rejected"  # Evidence not relevant, logged, no review impact
    SUPERSEDED = "superseded"  # Newer event replaced this


class BackflowEventType(str, Enum):
    """Types of backflow events."""

    LITERATURE_PUBLISHED = "literature_published"
    ADVERSE_EVENT = "adverse_event"
    PMCF_UPDATE = "pmcf_update"
    EQUIVALENCE_CHANGE = "equivalence_change"
    RMF_UPDATE = "rmf_update"


# Valid state transitions
VALID_TRANSITIONS: dict[CandidateState, list[CandidateState]] = {
    CandidateState.NEW: [CandidateState.UNDER_REVIEW],
    CandidateState.UNDER_REVIEW: [CandidateState.APPROVED, CandidateState.REJECTED, CandidateState.SUPERSEDED],
    CandidateState.APPROVED: [CandidateState.SUPERSEDED],
    CandidateState.REJECTED: [],
    CandidateState.SUPERSEDED: [],
}


@dataclass
class BackflowEvent:
    """A backflow event from an external evidence source."""

    event_id: str
    event_type: BackflowEventType
    source_system: str
    source_ref: str
    detected_at: str
    candidate_state: CandidateState = CandidateState.NEW
    candidate_ref: str = ""
    linked_dimensions: list[str] = field(default_factory=list)
    linked_ep_packs: list[str] = field(default_factory=list)
    workflow_action: str = ""  # route_to_cep|route_to_route_screen|flag_for_human
    processed_at: str | None = None
    processing_notes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "source_system": self.source_system,
            "source_ref": self.source_ref,
            "detected_at": self.detected_at,
            "candidate_state": self.candidate_state.value,
            "candidate_ref": self.candidate_ref,
            "linked_dimensions": self.linked_dimensions,
            "linked_ep_packs": self.linked_ep_packs,
            "workflow_action": self.workflow_action,
            "processed_at": self.processed_at,
            "processing_notes": self.processing_notes,
        }


@dataclass
class BackflowRegistry:
    """Registry for backflow events and candidate lifecycle management.

    SKELETON implementation per D1 Phase 1 scaffolding.

    D0C Contract: CER_D0C_BACKFLOW_ASSET_LIFECYCLE_CLOSURE.md
    """

    schema_name: str = "cer_backflow_registry"
    schema_version: str = "v1"
    project_id: str = ""
    cer_run_id: str = ""
    backflow_events: list[BackflowEvent] = field(default_factory=list)

    def add_event(self, event: BackflowEvent) -> None:
        """Add a new backflow event."""
        self.backflow_events.append(event)

    def transition_state(
        self,
        event_id: str,
        new_state: CandidateState,
        notes: str | None = None,
    ) -> bool:
        """Transition an event to a new state.

        Returns:
            True if transition was valid and applied.
            False if transition is invalid.
        """
        for event in self.backflow_events:
            if event.event_id == event_id:
                current = event.candidate_state
                if new_state in VALID_TRANSITIONS.get(current, []):
                    event.candidate_state = new_state
                    event.processed_at = datetime.now(timezone.utc).isoformat()
                    if notes:
                        event.processing_notes = notes
                    return True
                return False
        return False

    def get_events_by_state(self, state: CandidateState) -> list[BackflowEvent]:
        """Get all events in a given state."""
        return [e for e in self.backflow_events if e.candidate_state == state]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_name": self.schema_name,
            "schema_version": self.schema_version,
            "project_id": self.project_id,
            "cer_run_id": self.cer_run_id,
            "backflow_events": [e.to_dict() for e in self.backflow_events],
        }


def route_backflow_event(event: BackflowEvent) -> str:
    """Determine the workflow action for a backflow event.

    Returns:
        workflow_action: route_to_cep|route_to_route_screen|flag_for_human
    """
    if event.event_type == BackflowEventType.LITERATURE_PUBLISHED:
        return "route_to_cep"
    elif event.event_type == BackflowEventType.ADVERSE_EVENT:
        return "flag_for_human"
    elif event.event_type == BackflowEventType.PMCF_UPDATE:
        return "route_to_cep"
    elif event.event_type == BackflowEventType.EQUIVALENCE_CHANGE:
        return "route_to_route_screen"
    elif event.event_type == BackflowEventType.RMF_UPDATE:
        return "route_to_cep"
    return "flag_for_human"
