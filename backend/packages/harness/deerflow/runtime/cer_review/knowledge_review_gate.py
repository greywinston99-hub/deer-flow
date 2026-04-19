"""Knowledge Review Gate.

Human knowledge gate for reviewing and approving/rejecting/parking knowledge candidates.

Key principle: No machine asset may become approved without human knowledge gate pass.

API:
- GET /api/cer-review/{project_id}/knowledge/review-packet -> Generate review packet
- POST /api/cer-review/{project_id}/knowledge/candidates/{id}/review -> Submit decision
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from deerflow.runtime.cer_review.knowledge_candidate_state import (
    AssetType,
    CandidateState,
    KnowledgeCandidate,
    ASSET_TYPE_DESCRIPTIONS,
)

CER_ARTIFACTS_ROOT = Path("/Users/winstonwei/Documents/Playground/deer-flow/artifacts/cer")
KNOWLEDGE_STORE_ROOT = CER_ARTIFACTS_ROOT / "knowledge_store"


class KnowledgeReviewGate:
    """Human knowledge gate for candidate review."""

    def __init__(self, project_id: str, artifact_root: Path | None = None):
        """Initialize review gate for project.

        Args:
            project_id: CER project identifier
            artifact_root: Root path (defaults to project artifact root)
        """
        self.project_id = project_id
        self.artifact_root = artifact_root or CER_ARTIFACTS_ROOT / project_id
        self.candidates_file = self.artifact_root / "knowledge_candidates.json"
        self.review_packet_file = (
            KNOWLEDGE_STORE_ROOT / "review_packets" / f"{project_id}_review_packet.md"
        )
        self._ensure_directories()

    def _ensure_directories(self) -> None:
        """Create necessary directories."""
        self.review_packet_file.parent.mkdir(parents=True, exist_ok=True)

    def save_candidates(self, candidates: list[KnowledgeCandidate]) -> None:
        """Save candidates to persistent storage.

        Args:
            candidates: List of candidates to save
        """
        data = [c.to_dict() for c in candidates]
        with open(self.candidates_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def load_candidates(self) -> list[KnowledgeCandidate]:
        """Load candidates from persistent storage.

        Returns:
            List of saved candidates
        """
        if not self.candidates_file.exists():
            return []

        with open(self.candidates_file, encoding="utf-8") as f:
            data = json.load(f)
        return [KnowledgeCandidate.from_dict(d) for d in data]

    def get_pending_review(self) -> list[KnowledgeCandidate]:
        """Get candidates awaiting human review.

        Returns:
            List of candidates in NEEDS_HUMAN_REVIEW state
        """
        candidates = self.load_candidates()
        return [c for c in candidates if c.state == CandidateState.NEEDS_HUMAN_REVIEW]

    def generate_review_packet(self) -> str:
        """Generate markdown review packet for human review.

        Returns:
            Path to generated review packet file
        """
        pending = self.get_pending_review()

        # Always write to file, even if empty
        if not pending:
            content = "# Knowledge Review Packet\n\nNo candidates pending review.\n"
        else:
            # Sort by asset type and confidence
            pending.sort(key=lambda c: (c.asset_type.value, -c.confidence))

            lines = [
                "# Knowledge Review Packet",
                "",
                f"**Project:** {self.project_id}",
                f"**Generated:** {datetime.now(timezone.utc).isoformat()}",
                f"**Pending Count:** {len(pending)}",
                "",
                "---",
                "",
                "## Candidates for Review",
                "",
                "| ID | Type | Confidence | Source | Preview |",
                "|----|------|------------|--------|---------|",
            ]

            for c in pending:
                preview = self._get_preview(c)
                source = Path(c.source_artifact).name
                lines.append(
                    f"| [{c.candidate_id}](#{c.candidate_id.lower()}) "
                    f"| {c.asset_type.value} | {c.confidence:.2f} "
                    f"| {source} | {preview[:50]}... |"
                )

            lines.append("")
            lines.append("---")
            lines.append("")
            lines.append("## Detailed Candidates")
            lines.append("")

            for c in pending:
                lines.append(f"### {c.candidate_id}")
                lines.append("")
                lines.append(f"**Type:** {c.asset_type.value}")
                lines.append(f"**Description:** {ASSET_TYPE_DESCRIPTIONS.get(c.asset_type, 'N/A')}")
                lines.append(f"**Confidence:** {c.confidence:.2f}")
                lines.append(f"**Source:** `{c.source_artifact}`")
                lines.append("")
                lines.append("**Source Chain:**")
                for i, link in enumerate(c.source_chain):
                    lines.append(f"  {i + 1}. `{link}`")
                lines.append("")
                lines.append("**Payload:**")
                lines.append("```json")
                lines.append(json.dumps(c.payload, indent=2, ensure_ascii=False))
                lines.append("```")
                lines.append("")
                lines.append("**Review Actions:**")
                lines.append("- [ ] **APPROVE** - Publish to knowledge container")
                lines.append("- [ ] **REJECT** - Discard candidate")
                lines.append("- [ ] **PARK** - Defer for later review")
                lines.append("")
                lines.append("**Notes:**")
                lines.append("_[Add review notes here]_")
                lines.append("")
                lines.append("---")
                lines.append("")

            content = "\n".join(lines)

        # Write packet to file
        self.review_packet_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.review_packet_file, "w", encoding="utf-8") as f:
            f.write(content)

        return str(self.review_packet_file)

    def _get_preview(self, candidate: KnowledgeCandidate) -> str:
        """Get short preview text from candidate payload."""
        payload = candidate.payload

        # Try common preview fields
        for field in ["label", "description", "pattern_type", "lesson_type", "rule_type"]:
            if field in payload and payload[field]:
                return str(payload[field])

        # Fall back to first string value
        for value in payload.values():
            if isinstance(value, str) and value:
                return value[:100]

        return str(list(payload.values())[0])[:100] if payload else "N/A"

    def submit_review(
        self,
        candidate_id: str,
        decision: str,
        reviewer: str,
        notes: str | None = None,
    ) -> KnowledgeCandidate:
        """Submit review decision for a candidate.

        Args:
            candidate_id: Candidate ID
            decision: APPROVE, REJECT, or PARK
            reviewer: Reviewer identifier
            notes: Optional review notes

        Returns:
            Updated candidate

        Raises:
            ValueError: If candidate not found or decision invalid
        """
        candidates = self.load_candidates()

        # Find candidate
        candidate = None
        for c in candidates:
            if c.candidate_id == candidate_id:
                candidate = c
                break

        if not candidate:
            raise ValueError(f"Candidate {candidate_id} not found")

        if candidate.state != CandidateState.NEEDS_HUMAN_REVIEW:
            raise ValueError(
                f"Candidate {candidate_id} is in state {candidate.state.value}, "
                "cannot review"
            )

        # Map decision to state
        decision_map = {
            "APPROVE": CandidateState.APPROVED,
            "REJECT": CandidateState.REJECTED,
            "PARK": CandidateState.PARKED,
        }

        if decision not in decision_map:
            raise ValueError(
                f"Invalid decision: {decision}. Must be APPROVE, REJECT, or PARK"
            )

        target_state = decision_map[decision]

        # Update candidate
        candidate.transition(
            target_state,
            reviewed_at=datetime.now(timezone.utc).isoformat(),
            review_decision=decision,
            review_notes=notes,
            reviewed_by=reviewer,
        )

        # Save updated candidates
        self.save_candidates(candidates)

        return candidate

    def get_candidate(self, candidate_id: str) -> KnowledgeCandidate | None:
        """Get a specific candidate by ID.

        Args:
            candidate_id: Candidate ID

        Returns:
            Candidate or None if not found
        """
        candidates = self.load_candidates()
        for c in candidates:
            if c.candidate_id == candidate_id:
                return c
        return None

    def get_all_candidates(self) -> list[KnowledgeCandidate]:
        """Get all candidates for project.

        Returns:
            All candidates
        """
        return self.load_candidates()

    def get_candidates_by_state(
        self, state: CandidateState
    ) -> list[KnowledgeCandidate]:
        """Get candidates filtered by state.

        Args:
            state: Target state

        Returns:
            Candidates in specified state
        """
        candidates = self.load_candidates()
        return [c for c in candidates if c.state == state]

    def get_candidates_by_type(
        self, asset_type: AssetType
    ) -> list[KnowledgeCandidate]:
        """Get candidates filtered by asset type.

        Args:
            asset_type: Target asset type

        Returns:
            Candidates of specified type
        """
        candidates = self.load_candidates()
        return [c for c in candidates if c.asset_type == asset_type]


def create_review_gate(project_id: str) -> KnowledgeReviewGate:
    """Factory function to create review gate.

    Args:
        project_id: Project identifier

    Returns:
        KnowledgeReviewGate instance
    """
    return KnowledgeReviewGate(project_id)
