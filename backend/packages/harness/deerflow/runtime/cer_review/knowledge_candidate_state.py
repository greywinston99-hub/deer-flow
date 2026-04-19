"""Knowledge Candidate State Machine and Data Models.

This module defines the 8-state knowledge candidate state machine and the
KnowledgeCandidate data model for the CER Knowledge Container system.

State Machine:
    extracted -> normalized -> needs_human_review -> approved
                                                   -> rejected
                                                   -> parked
                 -> published (auto for machine-only, future)

Key constraint: No machine asset may become approved without human knowledge gate pass.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class AssetType(str, Enum):
    """Knowledge Asset Taxonomy - 11 types."""

    RULE_UNIT = "RuleUnit"  # Regulatory rule or GSPR requirement
    METHOD_UNIT = "MethodUnit"  # Testing/evaluation method or procedure
    FAILURE_PATTERN = "FailurePattern"  # Known failure mode or deficiency pattern
    CHECKLIST_UNIT = "ChecklistUnit"  # Completeness checklist item
    BOUNDARY_CONDITION = "BoundaryCondition"  # Boundary condition triggering special handling
    CROSS_DOCUMENT_MAPPING = "CrossDocumentMapping"  # Cross-document consistency rule
    TERMINOLOGY_UNIT = "TerminologyUnit"  # Standardized term or definition
    EVIDENCE_REQUIREMENT = "EvidenceRequirement"  # Evidence sufficiency threshold
    REVIEW_HEURISTIC = "ReviewHeuristic"  # Review decision logic or guideline
    CASE_LESSON = "CaseLesson"  # Lesson learned from specific case
    WORKFLOW_IMPROVEMENT = "WorkflowImprovement"  # Process improvement recommendation


class CandidateState(str, Enum):
    """Knowledge Candidate State - 8 states."""

    EXTRACTED = "extracted"  # Raw candidate from CER artifact
    NORMALIZED = "normalized"  # Structured into canonical taxonomy format
    NEEDS_HUMAN_REVIEW = "needs_human_review"  # Queued for human knowledge gate
    APPROVED = "approved"  # Passed human review -> publication candidate
    REJECTED = "rejected"  # Failed human review -> discarded
    PARKED = "parked"  # Deferred for later review
    PUBLISHED = "published"  # In knowledge container


# Valid state transitions
STATE_TRANSITIONS: dict[CandidateState, list[CandidateState]] = {
    CandidateState.EXTRACTED: [CandidateState.NORMALIZED],
    # HARDENING: Removed NORMALIZED -> PUBLISHED direct transition.
    # All machine asset publication requires explicit human review approval.
    # Candidate must go: EXTRACTED -> NORMALIZED -> NEEDS_HUMAN_REVIEW -> APPROVED -> PUBLISHED
    CandidateState.NORMALIZED: [CandidateState.NEEDS_HUMAN_REVIEW],
    CandidateState.NEEDS_HUMAN_REVIEW: [
        CandidateState.APPROVED,
        CandidateState.REJECTED,
        CandidateState.PARKED,
    ],
    CandidateState.APPROVED: [CandidateState.PUBLISHED],
    CandidateState.REJECTED: [],  # Terminal state
    CandidateState.PARKED: [CandidateState.NEEDS_HUMAN_REVIEW],  # Can re-queue
    CandidateState.PUBLISHED: [],  # Terminal state
}


@dataclass
class KnowledgeCandidate:
    """Knowledge Candidate data model.

    Attributes:
        candidate_id: Unique identifier (e.g., "KC-20260419-001")
        asset_type: One of 11 taxonomy types
        source_artifact: Path to source artifact file
        source_chain: Provenance chain [project_id, run_id, round_id, artifact_path, ...]
        state: Current state in the candidate state machine
        payload: Type-specific structured data
        confidence: Extraction confidence (0.0-1.0)
        extracted_at: ISO8601 extraction timestamp
        reviewed_at: ISO8601 review timestamp (None if not reviewed)
        published_at: ISO8601 publication timestamp (None if not published)
        review_decision: Review decision (APPROVED/REJECTED/PARKED) if reviewed
        review_notes: Review notes if reviewed
        reviewed_by: Reviewer identifier if reviewed
    """

    asset_type: AssetType
    source_artifact: str
    source_chain: list[str]
    payload: dict[str, Any]
    confidence: float
    project_id: str
    candidate_id: str = field(default_factory=lambda: _generate_candidate_id())
    state: CandidateState = CandidateState.EXTRACTED
    extracted_at: str = field(default_factory=lambda: _utc_now())
    reviewed_at: str | None = None
    published_at: str | None = None
    review_decision: str | None = None
    review_notes: str | None = None
    reviewed_by: str | None = None

    def can_transition(self, to_state: CandidateState) -> bool:
        """Check if transition to to_state is valid."""
        return to_state in STATE_TRANSITIONS.get(self.state, [])

    def transition(self, to_state: CandidateState, **kwargs: Any) -> None:
        """Transition to new state if valid.

        Args:
            to_state: Target state
            kwargs: Additional fields to update (reviewed_at, review_decision, etc.)

        Raises:
            ValueError: If transition is not valid
        """
        if not self.can_transition(to_state):
            raise ValueError(
                f"Invalid transition: {self.state.value} -> {to_state.value}"
            )
        self.state = to_state
        if kwargs:
            for key, value in kwargs.items():
                if hasattr(self, key):
                    setattr(self, key, value)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "candidate_id": self.candidate_id,
            "asset_type": self.asset_type.value,
            "source_artifact": self.source_artifact,
            "source_chain": self.source_chain,
            "state": self.state.value,
            "payload": self.payload,
            "confidence": self.confidence,
            "project_id": self.project_id,
            "extracted_at": self.extracted_at,
            "reviewed_at": self.reviewed_at,
            "published_at": self.published_at,
            "review_decision": self.review_decision,
            "review_notes": self.review_notes,
            "reviewed_by": self.reviewed_by,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> KnowledgeCandidate:
        """Deserialize from dictionary."""
        return cls(
            candidate_id=data["candidate_id"],
            asset_type=AssetType(data["asset_type"]),
            source_artifact=data["source_artifact"],
            source_chain=data["source_chain"],
            state=CandidateState(data["state"]),
            payload=data["payload"],
            confidence=data["confidence"],
            project_id=data["project_id"],
            extracted_at=data["extracted_at"],
            reviewed_at=data.get("reviewed_at"),
            published_at=data.get("published_at"),
            review_decision=data.get("review_decision"),
            review_notes=data.get("review_notes"),
            reviewed_by=data.get("reviewed_by"),
        )


def _generate_candidate_id() -> str:
    """Generate unique candidate ID."""
    date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    uid = uuid.uuid4().hex[:8].upper()
    return f"KC-{date_str}-{uid}"


def _utc_now() -> str:
    """Get current UTC time as ISO8601 string."""
    return datetime.now(timezone.utc).isoformat()


# Asset type to human-readable description
ASSET_TYPE_DESCRIPTIONS: dict[AssetType, str] = {
    AssetType.RULE_UNIT: "Regulatory rule or GSPR requirement",
    AssetType.METHOD_UNIT: "Testing/evaluation method or procedure",
    AssetType.FAILURE_PATTERN: "Known failure mode or deficiency pattern",
    AssetType.CHECKLIST_UNIT: "Completeness checklist item",
    AssetType.BOUNDARY_CONDITION: "Boundary condition triggering special handling",
    AssetType.CROSS_DOCUMENT_MAPPING: "Cross-document consistency rule",
    AssetType.TERMINOLOGY_UNIT: "Standardized term or definition",
    AssetType.EVIDENCE_REQUIREMENT: "Evidence sufficiency threshold",
    AssetType.REVIEW_HEURISTIC: "Review decision logic or guideline",
    AssetType.CASE_LESSON: "Lesson learned from specific case",
    AssetType.WORKFLOW_IMPROVEMENT: "Process improvement recommendation",
}


# Source artifact patterns to asset type mapping
SOURCE_TYPE_MAPPINGS: dict[str, AssetType] = {
    # Intake sources
    "classification_output.json": AssetType.TERMINOLOGY_UNIT,
    "evidence_classification_final.json": AssetType.EVIDENCE_REQUIREMENT,
    "human_intake_gate_decision.json": AssetType.CASE_LESSON,
    # Route sources
    "route_decision_draft.json": AssetType.BOUNDARY_CONDITION,
    "special_procedure_flags.json": AssetType.RULE_UNIT,
    # Layer1/HF sources
    "layer1_findings.json": AssetType.FAILURE_PATTERN,
    "completeness_status.json": AssetType.CHECKLIST_UNIT,
    "hf_check_report.json": AssetType.RULE_UNIT,
    # Lane sources
    "claim_consistency_matrix.json": AssetType.CROSS_DOCUMENT_MAPPING,
    "difference_impact_assessment.json": AssetType.METHOD_UNIT,
    "sota_findings.json": AssetType.EVIDENCE_REQUIREMENT,
    "consistency_delta_matrix.json": AssetType.CROSS_DOCUMENT_MAPPING,
    "gspr_evidence_mapping.json": AssetType.CHECKLIST_UNIT,
    "pmcf_adequacy_assessment.json": AssetType.METHOD_UNIT,
    "pmcf_need_statement.json": AssetType.METHOD_UNIT,
    "access_verification_findings.json": AssetType.EVIDENCE_REQUIREMENT,
    "risk_coverage_matrix.json": AssetType.CHECKLIST_UNIT,
    # Governance sources
    "decision_ledger_entry.json": AssetType.CASE_LESSON,
    "gate_audit.json": AssetType.REVIEW_HEURISTIC,
    "state_transition_log.jsonl": AssetType.WORKFLOW_IMPROVEMENT,
    # Conclusion sources
    "deficiency_register.json": AssetType.FAILURE_PATTERN,
    "overall_conclusion_draft.json": AssetType.REVIEW_HEURISTIC,
    "route_decision_note.json": AssetType.REVIEW_HEURISTIC,
    # Review package
    "review_package.json": AssetType.CASE_LESSON,
    "human_review_queue.json": AssetType.REVIEW_HEURISTIC,
}
