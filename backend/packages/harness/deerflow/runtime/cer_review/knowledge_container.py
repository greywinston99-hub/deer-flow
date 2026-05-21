"""Knowledge Container Publication.

Dual container system:
- Human Knowledge Container: Obsidian markdown cards at knowledge_store/human/
- Machine Knowledge Container: JSON/YAML assets at knowledge_store/machine_assets/

Publication rules:
- All candidates must pass human knowledge gate before publication
- Published candidates are immutable (append-only)
- Source chain is preserved for traceability
"""

from __future__ import annotations

import json
import yaml
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


class KnowledgeContainer:
    """Manages dual knowledge container publication."""

    def __init__(self, project_id: str, artifact_root: Path | None = None):
        """Initialize container for project.

        Args:
            project_id: CER project identifier
            artifact_root: Root path (defaults to CER_ARTIFACTS_ROOT)
        """
        self.project_id = project_id
        self.artifact_root = artifact_root or CER_ARTIFACTS_ROOT / project_id
        self.human_root = CER_ARTIFACTS_ROOT / "knowledge_store" / "human"
        self.machine_root = CER_ARTIFACTS_ROOT / "knowledge_store" / "machine_assets"
        self._ensure_directories()

    def _ensure_directories(self) -> None:
        """Create container directories if they don't exist."""
        for root in [self.human_root, self.machine_root]:
            for asset_type in AssetType:
                (root / asset_type.value / self.project_id).mkdir(
                    parents=True, exist_ok=True
                )

    def publish(
        self, candidate: KnowledgeCandidate, reviewer: str | None = None
    ) -> bool:
        """Publish candidate to dual container.

        Args:
            candidate: Knowledge candidate to publish
            reviewer: Reviewer identifier (for audit)

        Returns:
            True if published successfully

        Raises:
            ValueError: If candidate is not in APPROVED state
        """
        if candidate.state != CandidateState.APPROVED:
            raise ValueError(
                f"Cannot publish candidate in state {candidate.state.value}. "
                "Must be in APPROVED state."
            )

        # Update publication timestamp
        candidate.published_at = datetime.now(timezone.utc).isoformat()
        candidate.state = CandidateState.PUBLISHED

        # Publish to both containers
        self._publish_human(candidate)
        self._publish_machine(candidate)

        return True

    def _publish_human(self, candidate: KnowledgeCandidate) -> None:
        """Publish to Human Knowledge Container (Obsidian markdown)."""
        asset_dir = (
            self.human_root / candidate.asset_type.value / self.project_id
        )
        file_path = asset_dir / f"{candidate.candidate_id}.md"

        # Build Obsidian frontmatter
        frontmatter = {
            "id": candidate.candidate_id,
            "type": candidate.asset_type.value,
            "project_id": candidate.project_id,
            "state": candidate.state.value,
            "confidence": candidate.confidence,
            "source_artifact": candidate.source_artifact,
            "source_chain": candidate.source_chain,
            "extracted_at": candidate.extracted_at,
            "published_at": candidate.published_at,
            "reviewed_at": candidate.reviewed_at,
            "reviewed_by": candidate.reviewed_by,
        }

        # Build markdown content
        content = self._build_obsidian_content(candidate)

        # Write file with frontmatter
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("---\n")
            yaml.dump(frontmatter, f, allow_unicode=True, sort_keys=False)
            f.write("---\n\n")
            f.write(content)

    def _build_obsidian_content(self, candidate: KnowledgeCandidate) -> str:
        """Build Obsidian markdown content from candidate."""
        lines = [
            f"# {candidate.asset_type.value}: {candidate.candidate_id}",
            "",
            f"**Description:** {ASSET_TYPE_DESCRIPTIONS.get(candidate.asset_type, 'N/A')}",
            "",
            "## Source Information",
            "",
        ]

        # Source chain
        lines.append("### Source Chain")
        for i, link in enumerate(candidate.source_chain):
            lines.append(f"{i + 1}. `{link}`")
        lines.append("")

        # Payload as structured content
        lines.append("## Extracted Knowledge")
        lines.append("")
        lines.append("```json")
        lines.append(json.dumps(candidate.payload, indent=2, ensure_ascii=False))
        lines.append("```")
        lines.append("")

        # Review information
        if candidate.review_decision:
            lines.append("## Review")
            lines.append("")
            lines.append(f"- **Decision:** {candidate.review_decision}")
            lines.append(f"- **Reviewer:** {candidate.reviewed_by or 'N/A'}")
            lines.append(f"- **Reviewed:** {candidate.reviewed_at or 'N/A'}")
            if candidate.review_notes:
                lines.append(f"- **Notes:** {candidate.review_notes}")
            lines.append("")

        # Metadata footer
        lines.append("---")
        lines.append(f"_Extracted: {candidate.extracted_at}_")
        if candidate.published_at:
            lines.append(f"_Published: {candidate.published_at}_")

        return "\n".join(lines)

    def _publish_machine(self, candidate: KnowledgeCandidate) -> None:
        """Publish to Machine Knowledge Container (JSON/YAML)."""
        asset_dir = (
            self.machine_root / candidate.asset_type.value / self.project_id
        )
        file_path = asset_dir / f"{candidate.candidate_id}.json"

        # Build machine-readable asset
        asset = {
            "$schema": "cer_knowledge_asset.schema.json",
            "schema_version": "v1",
            "asset_id": candidate.candidate_id,
            "asset_type": candidate.asset_type.value,
            "project_id": candidate.project_id,
            "state": candidate.state.value,
            "confidence": candidate.confidence,
            "source_artifact": candidate.source_artifact,
            "source_chain": candidate.source_chain,
            "payload": candidate.payload,
            "metadata": {
                "extracted_at": candidate.extracted_at,
                "published_at": candidate.published_at,
                "reviewed_at": candidate.reviewed_at,
                "reviewed_by": candidate.reviewed_by,
                "review_decision": candidate.review_decision,
                "review_notes": candidate.review_notes,
            },
        }

        # Write JSON
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(asset, f, indent=2, ensure_ascii=False)

    def list_published(
        self, asset_type: AssetType | None = None
    ) -> list[KnowledgeCandidate]:
        """List published knowledge assets.

        Args:
            asset_type: Filter by asset type (optional)

        Returns:
            List of published knowledge candidates
        """
        candidates = []
        search_root = (
            self.machine_root / asset_type.value / self.project_id
            if asset_type
            else self.machine_root / self.project_id
        )

        if not search_root.exists():
            return candidates

        for type_dir in search_root.iterdir():
            if type_dir.is_dir() and not type_dir.name.startswith("."):
                for file_path in type_dir.glob("*.json"):
                    try:
                        with open(file_path, encoding="utf-8") as f:
                            data = json.load(f)
                        candidates.append(KnowledgeCandidate.from_dict(data))
                    except (json.JSONDecodeError, IOError, KeyError):
                        continue

        return candidates

    def get_container_index(self) -> dict[str, Any]:
        """Get index of all published knowledge for this project.

        Returns:
            Dictionary with counts by asset type
        """
        index: dict[str, Any] = {
            "project_id": self.project_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "asset_types": {},
            "total_published": 0,
        }

        for asset_type in AssetType:
            type_dir = self.machine_root / asset_type.value / self.project_id
            if type_dir.exists():
                count = len(list(type_dir.glob("*.json")))
                if count > 0:
                    index["asset_types"][asset_type.value] = {
                        "count": count,
                        "description": ASSET_TYPE_DESCRIPTIONS.get(asset_type, ""),
                    }
                    index["total_published"] += count

        return index


def publish_candidate(
    candidate: KnowledgeCandidate,
    project_id: str,
    reviewer: str | None = None,
) -> bool:
    """Convenience function to publish a single candidate.

    Args:
        candidate: Candidate to publish
        project_id: Project identifier
        reviewer: Reviewer identifier

    Returns:
        True if successful
    """
    container = KnowledgeContainer(project_id)
    return container.publish(candidate, reviewer)


def get_project_knowledge_index(project_id: str) -> dict[str, Any]:
    """Get knowledge index for a project.

    Args:
        project_id: Project identifier

    Returns:
        Index dictionary
    """
    container = KnowledgeContainer(project_id)
    return container.get_container_index()
