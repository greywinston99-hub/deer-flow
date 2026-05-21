"""CER Knowledge Container API — Knowledge Candidate Extraction, Review, and Publication.

Provides endpoints for:
  - POST /api/cer-review/{project_id}/knowledge/extract       -> extract candidates from artifacts
  - GET  /api/cer-review/{project_id}/knowledge/candidates    -> list all candidates
  - GET  /api/cer-review/{project_id}/knowledge/candidates/{id} -> get candidate detail
  - POST /api/cer-review/{project_id}/knowledge/candidates/{id}/review -> submit review decision
  - GET  /api/cer-review/{project_id}/knowledge/review-packet  -> generate review packet
  - GET  /api/cer-review/{project_id}/knowledge/container      -> list published knowledge
  - GET  /api/cer-review/{project_id}/knowledge/index         -> knowledge index

This module implements the dual knowledge container system:
  - Human Knowledge Container: Obsidian markdown cards
  - Machine Knowledge Container: JSON/YAML assets

Key constraint: No machine asset may become approved without human knowledge gate pass.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel, Field

from deerflow.runtime.cer_review.auth import (
    CERAuthContext,
    CERRole,
)
from deerflow.runtime.cer_review.auth.rbac_context import (
    get_cer_auth_with_gate_role,
)
from deerflow.runtime.cer_review.knowledge_candidate_extractor import (
    KnowledgeCandidateExtractor,
)
from deerflow.runtime.cer_review.knowledge_candidate_state import (
    AssetType,
    CandidateState,
    KnowledgeCandidate,
)
from deerflow.runtime.cer_review.knowledge_container import (
    KnowledgeContainer,
)
from deerflow.runtime.cer_review.knowledge_review_gate import (
    KnowledgeReviewGate,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/cer-review", tags=["cer-knowledge"])

CER_ARTIFACTS_ROOT = Path("/Users/winstonwei/Documents/Playground/deer-flow/artifacts/cer")


# ── Pydantic Models ───────────────────────────────────────────────────────────


class ExtractResponse(BaseModel):
    """Response for knowledge extraction."""

    project_id: str
    candidates_extracted: int
    by_type: dict[str, int]
    by_state: dict[str, int]


class CandidateListResponse(BaseModel):
    """Response for listing candidates."""

    project_id: str
    total: int
    candidates: list[dict[str, Any]]


class CandidateDetailResponse(BaseModel):
    """Response for single candidate."""

    candidate: dict[str, Any]


class ReviewRequest(BaseModel):
    """Request for submitting review decision."""

    decision: str = Field(
        ..., pattern="^(APPROVE|REJECT|PARK)$",
        description="Review decision: APPROVE, REJECT, or PARK"
    )
    notes: str | None = Field(None, description="Optional review notes")


class ReviewResponse(BaseModel):
    """Response for review submission."""

    candidate_id: str
    decision: str
    new_state: str
    reviewed_at: str


class ContainerIndexResponse(BaseModel):
    """Response for container index."""

    project_id: str
    generated_at: str
    asset_types: dict[str, dict[str, Any]]
    total_published: int


# ── RBAC Check ────────────────────────────────────────────────────────────────


def _require_reviewer_role(auth: CERAuthContext) -> CERAuthContext:
    """Require SENIOR_REVIEWER or ADMIN for knowledge operations."""
    if auth.role not in {CERRole.SENIOR_REVIEWER, CERRole.ADMIN}:
        raise HTTPException(
            status_code=403,
            detail=f"Permission denied: {auth.role.value} cannot manage knowledge. Requires SENIOR_REVIEWER or ADMIN.",
        )
    return auth


# ── Knowledge API Endpoints ────────────────────────────────────────────────────


@router.post("/{project_id}/knowledge/extract", response_model=ExtractResponse)
async def extract_knowledge(project_id: str) -> ExtractResponse:
    """Extract knowledge candidates from CER artifacts.

    Extracts from 7 source types:
    1. Intake Classification (classification_output.json, evidence_classification_final.json)
    2. Human Gate Decision (human_intake_gate_decision.json)
    3. CER Route Decision (route_decision_draft.json)
    4. HF Check Findings (layer1_findings.json)
    5. Lane Findings (03_lanes/*.json)
    6. Gate Decisions (governance/decision_ledger_entry.json)
    7. Findings Register (*_FINDINGS_REGISTER.json)
    """
    artifact_root = CER_ARTIFACTS_ROOT / project_id
    if not artifact_root.exists():
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    # Extract candidates
    extractor = KnowledgeCandidateExtractor(project_id, artifact_root)
    candidates = extractor.extract_all()

    # Save to review gate
    gate = KnowledgeReviewGate(project_id, artifact_root)
    gate.save_candidates(candidates)

    # Aggregate stats
    by_type: dict[str, int] = {}
    by_state: dict[str, int] = {}
    for c in candidates:
        by_type[c.asset_type.value] = by_type.get(c.asset_type.value, 0) + 1
        by_state[c.state.value] = by_state.get(c.state.value, 0) + 1

    return ExtractResponse(
        project_id=project_id,
        candidates_extracted=len(candidates),
        by_type=by_type,
        by_state=by_state,
    )


@router.get("/{project_id}/knowledge/candidates", response_model=CandidateListResponse)
async def list_candidates(project_id: str) -> CandidateListResponse:
    """List all knowledge candidates for project."""
    gate = KnowledgeReviewGate(project_id)
    candidates = gate.get_all_candidates()

    return CandidateListResponse(
        project_id=project_id,
        total=len(candidates),
        candidates=[c.to_dict() for c in candidates],
    )


@router.get("/{project_id}/knowledge/candidates/{candidate_id}", response_model=CandidateDetailResponse)
async def get_candidate(project_id: str, candidate_id: str) -> CandidateDetailResponse:
    """Get a specific knowledge candidate by ID."""
    gate = KnowledgeReviewGate(project_id)
    candidate = gate.get_candidate(candidate_id)

    if not candidate:
        raise HTTPException(status_code=404, detail=f"Candidate {candidate_id} not found")

    return CandidateDetailResponse(candidate=candidate.to_dict())


@router.post("/{project_id}/knowledge/candidates/{candidate_id}/review", response_model=ReviewResponse)
async def submit_review(
    project_id: str,
    candidate_id: str,
    review_request: ReviewRequest = Body(...),
    auth: CERAuthContext = Depends(get_cer_auth_with_gate_role),
) -> ReviewResponse:
    """Submit review decision for a candidate.

    Transitions candidate to APPROVED, REJECTED, or PARKED state.
    If APPROVED, also publishes to dual knowledge container.
    """
    gate = KnowledgeReviewGate(project_id)
    reviewer = getattr(auth, "user_id", str(auth.role.value))

    try:
        candidate = gate.submit_review(
            candidate_id=candidate_id,
            decision=review_request.decision,
            reviewer=reviewer,
            notes=review_request.notes,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # If approved, publish to container
    if review_request.decision == "APPROVE":
        try:
            container = KnowledgeContainer(project_id)
            container.publish(candidate, reviewer)
        except Exception as e:
            logger.error(f"Failed to publish candidate {candidate_id}: {e}")
            # Don't fail the review if publication fails

    return ReviewResponse(
        candidate_id=candidate.candidate_id,
        decision=review_request.decision,
        new_state=candidate.state.value,
        reviewed_at=candidate.reviewed_at or "",
    )


@router.get("/{project_id}/knowledge/review-packet")
async def get_review_packet(project_id: str) -> dict[str, Any]:
    """Generate and return knowledge review packet.

    Returns markdown-formatted review packet for human review.
    """
    gate = KnowledgeReviewGate(project_id)
    packet_path = gate.generate_review_packet()

    with open(packet_path, encoding="utf-8") as f:
        content = f.read()

    return {
        "project_id": project_id,
        "packet_path": packet_path,
        "content": content,
    }


@router.get("/{project_id}/knowledge/container", response_model=ContainerIndexResponse)
async def get_container_index(project_id: str) -> ContainerIndexResponse:
    """Get index of published knowledge assets."""
    container = KnowledgeContainer(project_id)
    index = container.get_container_index()

    return ContainerIndexResponse(**index)


@router.get("/{project_id}/knowledge/pending", response_model=CandidateListResponse)
async def list_pending_review(project_id: str) -> CandidateListResponse:
    """List candidates pending human review."""
    gate = KnowledgeReviewGate(project_id)
    candidates = gate.get_pending_review()

    return CandidateListResponse(
        project_id=project_id,
        total=len(candidates),
        candidates=[c.to_dict() for c in candidates],
    )


@router.get("/{project_id}/knowledge/by-state/{state}", response_model=CandidateListResponse)
async def get_candidates_by_state(
    project_id: str,
    state: str,
) -> CandidateListResponse:
    """Get candidates filtered by state."""
    try:
        target_state = CandidateState(state)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid state: {state}. Valid states: {[s.value for s in CandidateState]}",
        )

    gate = KnowledgeReviewGate(project_id)
    candidates = gate.get_candidates_by_state(target_state)

    return CandidateListResponse(
        project_id=project_id,
        total=len(candidates),
        candidates=[c.to_dict() for c in candidates],
    )


@router.get("/{project_id}/knowledge/by-type/{asset_type}", response_model=CandidateListResponse)
async def get_candidates_by_type(
    project_id: str,
    asset_type: str,
) -> CandidateListResponse:
    """Get candidates filtered by asset type."""
    try:
        target_type = AssetType(asset_type)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid asset type: {asset_type}. Valid types: {[t.value for t in AssetType]}",
        )

    gate = KnowledgeReviewGate(project_id)
    candidates = gate.get_candidates_by_type(target_type)

    return CandidateListResponse(
        project_id=project_id,
        total=len(candidates),
        candidates=[c.to_dict() for c in candidates],
    )
