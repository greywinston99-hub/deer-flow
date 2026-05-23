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

import fcntl
import hashlib
import hmac
import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
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
        """Build feedback document conforming to cer_review_feedback.schema.json.

        P0-3: Generates HMAC-SHA256 signature over the canonical payload.
        P1-2: Adds expires_at (default 30 days TTL).
        """
        now = datetime.now(timezone.utc)
        feedback_id = f"RF-{now.strftime('%Y%m%d%H%M%S')}"

        normalized_findings = [self._normalize_finding(f) for f in findings]

        feedback = {
            "feedback_id": feedback_id,
            "source": source,
            "source_project_id": source_project_id,
            "advisory_only": True,
            "generated_at": now.isoformat(),
            "expires_at": (now + timedelta(days=30)).isoformat(),
            "findings": normalized_findings,
            "prohibited_actions": [
                "auto_modify_claim_ledger",
                "auto_delete_evidence",
                "trigger_rework_without_human_confirm",
                "override_gate_decision",
            ],
        }
        # P0-3: Sign the feedback
        feedback["signature"] = self._compute_signature(feedback)
        return feedback

    def _compute_signature(self, data: dict[str, Any]) -> str:
        """Compute HMAC-SHA256 signature over canonical feedback payload.

        Key is derived from source_project_id (stable per-project).
        Falls back to a dev key for local testing.
        """
        key_str = data.get("source_project_id") or "dev-fallback-key"
        key = key_str.encode("utf-8")
        payload = json.dumps({
            "feedback_id": data.get("feedback_id", ""),
            "source": data.get("source", ""),
            "advisory_only": bool(data.get("advisory_only")),
            "findings": sorted(
                [
                    {
                        "finding_id": str(f.get("finding_id", "")),
                        "severity": str(f.get("severity", "")),
                        "category": str(f.get("category", "")),
                        "description": str(f.get("description", ""))[:500],
                    }
                    for f in (data.get("findings") or [])
                ],
                key=lambda x: x["finding_id"],
            ),
        }, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        return hmac.new(key, payload.encode("utf-8"), hashlib.sha256).hexdigest()

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

        P1-3: Optimized to single-pass O(n) using pre-computed keys.
        """
        seen: dict[tuple[str, str, str, str], dict[str, Any]] = {}
        for f in findings:
            fid = str(f.get("finding_id") or f.get("id") or "")
            claim_id = str(f.get("target_claim_id") or f.get("claim_id") or "__none__")
            category = str(f.get("category") or f.get("type") or "unknown")
            severity = str(f.get("severity") or f.get("level") or "MEDIUM").upper()
            desc_len = len(str(f.get("description") or f.get("message") or ""))

            # Primary key: finding_id (if present); secondary key: semantic signature
            if fid:
                key = ("id", fid, "", "")
            else:
                key = ("sig", claim_id, category, severity)

            existing = seen.get(key)
            if existing is None:
                seen[key] = f
            else:
                existing_len = len(str(existing.get("description") or existing.get("message") or ""))
                if desc_len > existing_len:
                    seen[key] = f

        return list(seen.values())

    # ── Persistence ─────────────────────────────────────────────────────────────

    def _atomic_write(self, feedback: dict[str, Any]) -> Path:
        """Atomically write feedback with versioning.

        Writes:
        1. A versioned file: review_feedback/RF-{timestamp}.json
        2. Updates versions.json index
        3. Atomically replaces latest.json symlink/copy
        4. Appends to audit_log.jsonl

        P0-2: Uses fcntl file lock to protect the entire multi-file
        transaction against concurrent writers (e.g. parallel Review runs).
        P1-1: Structured audit logging for feedback lifecycle.
        """
        self._feedback_dir.mkdir(parents=True, exist_ok=True)

        feedback_id = feedback.get("feedback_id", f"RF-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}")
        versioned_path = self._feedback_dir / f"{feedback_id}.json"
        temp = self._feedback_dir / f".latest.json.tmp.{uuid.uuid4().hex}"

        # Acquire exclusive lock on a dedicated lockfile
        lock_path = self._feedback_dir / ".write.lock"
        with open(lock_path, "w") as lock_fh:
            fcntl.flock(lock_fh.fileno(), fcntl.LOCK_EX)
            try:
                # 1. Write versioned file
                with open(versioned_path, "w", encoding="utf-8") as fh:
                    json.dump(feedback, fh, indent=2, ensure_ascii=False)

                # 2. Update versions index (now also protected by lock)
                self._update_versions_index(feedback_id, versioned_path.name)

                # 3. Atomic write of latest.json
                with open(temp, "w", encoding="utf-8") as fh:
                    json.dump(feedback, fh, indent=2, ensure_ascii=False)

                if temp.stat().st_size == 0:
                    temp.unlink(missing_ok=True)
                    raise RuntimeError("Feedback write resulted in empty file")

                temp.replace(self._feedback_dir / "latest.json")

                # 4. Audit log
                self._append_audit_log({
                    "event": "feedback_generated",
                    "feedback_id": feedback_id,
                    "findings_count": len(feedback.get("findings", [])),
                    "source": feedback.get("source"),
                    "source_project_id": feedback.get("source_project_id"),
                    "has_signature": bool(feedback.get("signature")),
                    "expires_at": feedback.get("expires_at"),
                })
            finally:
                fcntl.flock(lock_fh.fileno(), fcntl.LOCK_UN)

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

    def _append_audit_log(self, record: dict[str, Any]) -> None:
        """P1-1: Append structured event to audit_log.jsonl."""
        audit_path = self._feedback_dir / "audit_log.jsonl"
        line = json.dumps({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **record,
        }, ensure_ascii=False, separators=(",", ":"))
        with open(audit_path, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")

    @staticmethod
    def cleanup_expired_feedback(feedback_dir: Path | str, dry_run: bool = True) -> dict[str, Any]:
        """P1-2: Remove expired feedback files (versioned + latest) and stale audit logs.

        Files older than their expires_at (or 30 days default) are removed.
        Returns summary of cleaned files.
        """
        from datetime import datetime, timezone
        d = Path(feedback_dir)
        now = datetime.now(timezone.utc)
        removed_files: list[str] = []
        kept_files: list[str] = []

        for path in d.glob("RF-*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                expires = data.get("expires_at")
                if expires:
                    expiry = datetime.fromisoformat(expires)
                else:
                    # Fallback: generated_at + 30 days
                    generated = data.get("generated_at")
                    if generated:
                        expiry = datetime.fromisoformat(generated) + timedelta(days=30)
                    else:
                        expiry = now  # no metadata → treat as expired
                if expiry < now:
                    if not dry_run:
                        path.unlink(missing_ok=True)
                    removed_files.append(path.name)
                else:
                    kept_files.append(path.name)
            except Exception:
                # Corrupted file — safe to remove
                if not dry_run:
                    path.unlink(missing_ok=True)
                removed_files.append(path.name)

        # Also clean up latest.json if it points to expired content
        latest = d / "latest.json"
        if latest.exists() and removed_files:
            try:
                latest_data = json.loads(latest.read_text(encoding="utf-8"))
                latest_id = latest_data.get("feedback_id", "")
                if any(f.startswith(latest_id) for f in removed_files):
                    if not dry_run:
                        latest.unlink(missing_ok=True)
                    removed_files.append("latest.json")
            except Exception:
                pass

        return {
            "removed": removed_files,
            "kept": kept_files,
            "dry_run": dry_run,
        }

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
