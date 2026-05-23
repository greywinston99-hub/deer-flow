"""CER Review → Authoring Feedback Writer.

Transforms Review pipeline findings into structured advisory feedback
conforming to schemas/cer_review_feedback.schema.json.

Design principles (weak-coupling):
- Advisory-only: never triggers automatic rework
- File-system bridge: writes to review_feedback/latest.json
- Schema-guarded: validates against cer_review_feedback.schema.json
- Read-only for Authoring: Authoring loads but never modifies
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Mapping from Review finding category to Authoring rework node suggestions
# These are advisory — human decides whether to act on them.
_CATEGORY_TO_REWORK_NODE: dict[str, str | None] = {
    "cross_doc_inconsistency": "claim_decomposition",
    "regulatory_boundary_violation": "risk_gspr_mapping",
    "evidence_quality_gap": "evidence_appraisal",
    "claim_evidence_mismatch": "claim_decomposition",
    "terminology_non_standard": "writer_synthesis",
    "format_degradation": "cer_writing",
    "missing_evidence": "sota_search",
    "orphan_requirement": "device_profile",
    "metadata_inconsistency": "device_profile",
}

# Mapping from Review severity to evidence depth requirement
_SEVERITY_TO_REQUIRED_DEPTH: dict[str, str] = {
    "CRITICAL": "PRIMARY_VERBATIM",
    "HIGH": "PRIMARY_DERIVED",
    "MEDIUM": "PRIMARY_DERIVED",
    "LOW": "SECONDARY_SUMMARY",
    "INFORMATIONAL": "SECONDARY_SUMMARY",
}


class ReviewFeedbackWriter:
    """Write Review findings as advisory feedback for Authoring pipeline."""

    def __init__(self, artifact_root: Path | str):
        self.artifact_root = Path(artifact_root)
        self._feedback_dir = self.artifact_root / "review_feedback"

    # ── Public API ──────────────────────────────────────────────────────────────

    def write_feedback(
        self,
        findings: list[dict[str, Any]],
        source: str = "cer_review_assist_sandbox_v2_0",
        source_project_id: str | None = None,
    ) -> Path:
        """Write findings as structured feedback.

        Returns the path to the written feedback file.
        """
        deduped = self._deduplicate_findings(findings)
        feedback = self._build_feedback(deduped, source, source_project_id)
        return self._atomic_write(feedback)

    def write_feedback_from_review_package(
        self,
        review_package_path: Path | str,
        source_project_id: str | None = None,
    ) -> Path | None:
        """Extract findings from a review_package.json and write feedback.

        This is the primary entry point for the Review Runner.
        """
        path = Path(review_package_path)
        if not path.exists():
            logger.warning("Review package not found: %s", path)
            return None

        try:
            with open(path, encoding="utf-8") as fh:
                package = json.load(fh)
        except Exception as exc:
            logger.warning("Failed to parse review package: %s", exc)
            return None

        findings = self._extract_findings_from_package(package)
        return self.write_feedback(findings, source="cer_review_v1", source_project_id=source_project_id)

    def write_feedback_from_assist_state(
        self,
        stage_data: dict[str, Any],
        source_project_id: str | None = None,
    ) -> Path:
        """Extract findings from Review Assist Lead Agent stage_data.

        This is the primary entry point for the Review Assist 3-stage graph.
        """
        findings = self._extract_findings_from_assist(stage_data)
        return self.write_feedback(findings, source="cer_review_assist_sandbox_v2_0", source_project_id=source_project_id)

    # ── Builders ────────────────────────────────────────────────────────────────

    def _build_feedback(
        self,
        findings: list[dict[str, Any]],
        source: str,
        source_project_id: str | None,
    ) -> dict[str, Any]:
        """Build feedback document conforming to cer_review_feedback.schema.json."""
        now = datetime.now(timezone.utc).isoformat()
        feedback_id = f"RF-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"

        normalized_findings = [self._normalize_finding(f) for f in findings]

        return {
            "feedback_id": feedback_id,
            "source": source,
            "source_project_id": source_project_id,
            "advisory_only": True,
            "generated_at": now,
            "findings": normalized_findings,
            "prohibited_actions": [
                "auto_modify_claim_ledger",
                "auto_delete_evidence",
                "trigger_rework_without_human_confirm",
                "override_gate_decision",
            ],
        }

    def _normalize_finding(self, raw: dict[str, Any]) -> dict[str, Any]:
        """Normalize a raw finding into schema-conformant format."""
        severity = str(raw.get("severity") or raw.get("level") or "MEDIUM").upper()
        category = str(raw.get("category") or raw.get("type") or "cross_doc_inconsistency")

        # Derive evidence_depth from severity if not explicitly provided
        explicit_depth = str(raw.get("evidence_depth") or "").upper()
        if explicit_depth in {"PRIMARY_VERBATIM", "PRIMARY_DERIVED", "SECONDARY_SUMMARY", "MISSING_PRIMARY"}:
            evidence_depth = explicit_depth
        else:
            evidence_depth = _SEVERITY_TO_REQUIRED_DEPTH.get(severity, "SECONDARY_SUMMARY")

        # Suggest rework node based on category (advisory only)
        suggested_node = raw.get("suggested_rework_node") or _CATEGORY_TO_REWORK_NODE.get(category)

        return {
            "finding_id": str(raw.get("finding_id") or raw.get("id") or f"F-{uuid.uuid4().hex[:8]}"),
            "severity": severity,
            "evidence_depth": evidence_depth,
            "category": category,
            "target_claim_id": raw.get("target_claim_id") or raw.get("claim_id"),
            "target_evidence_id": raw.get("target_evidence_id") or raw.get("evidence_id"),
            "description": str(raw.get("description") or raw.get("message") or "")[:2000],
            "source_artifact": raw.get("source_artifact"),
            "suggested_rework_node": suggested_node,
            "rationale": str(raw.get("rationale") or raw.get("reasoning") or "")[:1000],
        }

    # ── Extractors ──────────────────────────────────────────────────────────────

    @staticmethod
    def _extract_findings_from_package(package: dict[str, Any]) -> list[dict[str, Any]]:
        """Extract findings from Review Runner review_package.json."""
        findings: list[dict[str, Any]] = []

        # Try multiple known locations for findings
        for key in ("findings", "gaps", "flags", "observations", "issues"):
            items = package.get(key)
            if isinstance(items, list):
                findings.extend(items)

        # Extract from nested structures
        components = package.get("components") or {}
        if isinstance(components, dict):
            for comp in components.values():
                if isinstance(comp, dict):
                    for key in ("findings", "gaps", "flags"):
                        items = comp.get(key)
                        if isinstance(items, list):
                            findings.extend(items)

        return ReviewFeedbackWriter._deduplicate_findings(findings)

    @staticmethod
    def _extract_findings_from_assist(stage_data: dict[str, Any]) -> list[dict[str, Any]]:
        """Extract findings from Review Assist Lead Agent stage_data."""
        findings: list[dict[str, Any]] = []

        # Stage data keys from review_assist_state_machine
        gap_doc = stage_data.get("gap_analysis_done")
        if isinstance(gap_doc, dict):
            for key in ("finding_clusters", "candidate_findings", "atomic_observations", "g_points"):
                items = gap_doc.get(key)
                if isinstance(items, list):
                    findings.extend(items)

        severity_doc = stage_data.get("severity_synthesis_done")
        if isinstance(severity_doc, dict):
            for key in ("synthesized_findings", "flagged_items", "severity_signals", "human_gate_items"):
                items = severity_doc.get(key)
                if isinstance(items, list):
                    findings.extend(items)

        return ReviewFeedbackWriter._deduplicate_findings(findings)

    @staticmethod
    def _deduplicate_findings(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Deduplicate findings by ID first, then by semantic signature.

        Semantic signature = (target_claim_id, category, severity).
        When duplicates are found, keep the one with longer description
        (assumed to be more detailed / higher quality).
        """
        # Pass 1: Deduplicate by finding_id
        by_id: dict[str, dict[str, Any]] = {}
        for f in findings:
            fid = str(f.get("finding_id") or f.get("id") or "")
            if fid:
                if fid not in by_id:
                    by_id[fid] = f
                else:
                    # Keep the longer description
                    existing_len = len(str(by_id[fid].get("description") or by_id[fid].get("message") or ""))
                    new_len = len(str(f.get("description") or f.get("message") or ""))
                    if new_len > existing_len:
                        by_id[fid] = f
            # findings without id are collected separately

        id_deduped = list(by_id.values())
        no_id = [f for f in findings if not str(f.get("finding_id") or f.get("id") or "")]

        # Pass 2: Semantic deduplication by (target_claim_id, category, severity)
        seen_semantic: dict[tuple[str, str, str], dict[str, Any]] = {}
        for f in id_deduped + no_id:
            claim_id = str(f.get("target_claim_id") or f.get("claim_id") or "__none__")
            category = str(f.get("category") or f.get("type") or "unknown")
            severity = str(f.get("severity") or f.get("level") or "MEDIUM").upper()
            sig = (claim_id, category, severity)

            if sig not in seen_semantic:
                seen_semantic[sig] = f
            else:
                existing = seen_semantic[sig]
                existing_len = len(str(existing.get("description") or existing.get("message") or ""))
                new_len = len(str(f.get("description") or f.get("message") or ""))
                if new_len > existing_len:
                    seen_semantic[sig] = f

        return list(seen_semantic.values())

    # ── Persistence ─────────────────────────────────────────────────────────────

    def _atomic_write(self, feedback: dict[str, Any]) -> Path:
        """Atomically write feedback with versioning.

        Writes:
        1. A versioned file: review_feedback/RF-{timestamp}.json
        2. Updates versions.json index
        3. Atomically replaces latest.json symlink/copy
        """
        self._feedback_dir.mkdir(parents=True, exist_ok=True)

        feedback_id = feedback.get("feedback_id", f"RF-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}")
        versioned_path = self._feedback_dir / f"{feedback_id}.json"
        temp = self._feedback_dir / f".latest.json.tmp.{uuid.uuid4().hex}"

        try:
            # 1. Write versioned file
            with open(versioned_path, "w", encoding="utf-8") as fh:
                json.dump(feedback, fh, indent=2, ensure_ascii=False)

            # 2. Update versions index
            self._update_versions_index(feedback_id, versioned_path.name)

            # 3. Atomic write of latest.json
            with open(temp, "w", encoding="utf-8") as fh:
                json.dump(feedback, fh, indent=2, ensure_ascii=False)

            if temp.stat().st_size == 0:
                temp.unlink(missing_ok=True)
                raise RuntimeError("Feedback write resulted in empty file")

            temp.replace(self._feedback_dir / "latest.json")

        except Exception:
            temp.unlink(missing_ok=True)
            raise

        logger.info(
            "Wrote Review feedback: %s findings → %s (latest: %s)",
            len(feedback.get("findings", [])),
            versioned_path,
            self._feedback_dir / "latest.json",
        )
        return versioned_path

    def _update_versions_index(self, feedback_id: str, filename: str) -> None:
        """Append to versions.json audit trail."""
        index_path = self._feedback_dir / "versions.json"
        index: dict[str, Any] = {"versions": [], "latest": None}
        if index_path.exists():
            try:
                with open(index_path, encoding="utf-8") as fh:
                    index = json.load(fh)
            except Exception:
                pass

        versions = index.get("versions", [])
        versions.append({
            "feedback_id": feedback_id,
            "filename": filename,
            "written_at": datetime.now(timezone.utc).isoformat(),
        })
        # Keep last 50 versions
        index["versions"] = versions[-50:]
        index["latest"] = feedback_id

        temp = self._feedback_dir / f".versions.json.tmp.{uuid.uuid4().hex}"
        try:
            with open(temp, "w", encoding="utf-8") as fh:
                json.dump(index, fh, indent=2, ensure_ascii=False)
            temp.replace(index_path)
        except Exception:
            temp.unlink(missing_ok=True)
            raise

    def generate_kb_update_candidates(self, findings: list[dict[str, Any]], project_id: str) -> Path | None:
        """P1-3: Generate knowledge-base update candidates from feedback findings.

        Does NOT modify device_knowledge_base.json directly.
        Writes candidates to kb_update_candidates.json for human review.
        """
        if not findings:
            return None

        kb_path = self._feedback_dir / "kb_update_candidates.json"
        candidates: list[dict[str, Any]] = []
        for f in findings:
            severity = str(f.get("severity") or "MEDIUM").upper()
            if severity not in {"CRITICAL", "HIGH"}:
                continue  # Only high-confidence findings become KB candidates
            candidates.append({
                "project_id": project_id,
                "finding_id": f.get("finding_id"),
                "category": f.get("category"),
                "concern": str(f.get("description", ""))[:200],
                "severity": severity,
                "evidence_depth": f.get("evidence_depth"),
                "confidence": 0.70 if severity == "HIGH" else 0.85,
                "knowledge_maturity": "OBSERVED_ONCE",
                "source_projects": [project_id],
                "suggested_rework_node": f.get("suggested_rework_node"),
                "generated_at": datetime.now(timezone.utc).isoformat(),
            })

        if not candidates:
            return None

        try:
            with open(kb_path, "w", encoding="utf-8") as fh:
                json.dump({
                    "schema": "kb_update_candidates_v1",
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "project_id": project_id,
                    "candidate_count": len(candidates),
                    "candidates": candidates,
                    "note": "These are candidates for device_knowledge_base.json update. "
                            "Review and run: python tools/knowledge_extractor.py --mode update ...",
                }, fh, indent=2, ensure_ascii=False)
            logger.info("Generated %d KB update candidates → %s", len(candidates), kb_path)
            return kb_path
        except Exception as exc:
            logger.warning("Failed to write KB candidates: %s", exc)
            return None
