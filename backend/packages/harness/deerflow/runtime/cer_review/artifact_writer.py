"""CER Artifact Writer — Atomic Write + Completeness Guarantees

Implements:
- Atomic write (temp + rename)
- Partial write detection (zero bytes)
- Artifact completeness checklist
- Bundle assembly pre/post integrity checks
- Artifact lineage tracking

Frozen baseline: CER_RUNTIME_HARDENING_PLAN_V1.md Section 6
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .exceptions import (
    AtomicWriteError,
    BundleIncompleteError,
    PartialWriteError,
)


# ── Completeness Checklist ──────────────────────────────────────────────────────


LANE_REQUIRED_ARTIFACTS: dict[str, list[str]] = {
    "lane_2a_claim": [
        "claim_consistency_matrix.json",
        "risk_benefit_contribution_report.json",
    ],
    "lane_2b_evidence": [
        "evidence_qualified_report.json",
        "risk_benefit_contribution_report.json",
    ],
    "lane_2c_equivalence": [
        "difference_impact_assessment.json",
        "access_verification_findings.json",
        "risk_benefit_contribution_report.json",
    ],
    "lane_2d_consistency_pmcf": [
        "cross_doc_consistency_report.json",
        "pmcf_need_statement.json",
        "pmcf_adequacy_assessment.json",
        "risk_benefit_contribution_reports.json",
    ],
}

GATE_BUNDLE_REQUIREMENTS: dict[str, list[str]] = {
    "GATE_0": [
        "gate_0_bundle.json",
        "intended_purpose_validation.json",
    ],
    "GATE_1": [
        "route_decision_draft.json",
        "difference_impact_assessment.json",
        "special_procedure_flags.json",
    ],
    "GATE_2": [
        "claim_consistency_matrix.json",
        "evidence_qualified_report.json",
        "pmcf_need_statement.json",
        "gate_1_decision.json",
    ],
    "GATE_3": [
        "risk_benefit_composite_assembly.json",
        "cross_doc_consistency_report.json",
        "pmcf_need_statement.json",
        "gate_2_decision.json",
    ],
    "CLOSURE": [
        "review_package.json",
        "gate_1_decision.json",
        "gate_3_decision.json",
        "decision_ledger_entry.json",
    ],
}

CLOSURE_BUNDLE_INDEX_REQUIRED = [
    "00_manifest/run_manifest.json",
    "01_route/route_decision_draft.json",
    "03_lanes/claim_consistency_matrix.json",
    "03_lanes/sota_findings.json",
    "03_lanes/difference_impact_assessment.json",
    "03_lanes/consistency_delta_matrix.json",
    "03_lanes/pmcf_need_statement.json",
    "04_adjudication/gate_1_decision.json",
    "04_adjudication/gate_3_decision.json",
    "05_conclusion/review_package.json",
    "governance/decision_ledger_entry.json",
]


# ── Artifact Writer ─────────────────────────────────────────────────────────────


class CERArtifactWriter:
    """Atomic artifact writer with completeness guarantees."""

    def __init__(self, artifact_root: Path):
        self.artifact_root = Path(artifact_root)

    # ── Core Write Operations ────────────────────────────────────────────────

    def atomic_write(
        self,
        relative_path: str,
        data: dict[str, Any],
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, str]:
        """Write artifact atomically: temp file + rename.

        Returns lineage record with file hash and write timestamp.
        Raises AtomicWriteError on failure.
        """
        artifact_path = self.artifact_root / relative_path
        artifact_dir = artifact_path.parent

        try:
            artifact_dir.mkdir(parents=True, exist_ok=True)

            # Write to temp file in same directory (required for atomic rename)
            fd, temp_path = tempfile.mkstemp(
                dir=str(artifact_dir),
                suffix=".tmp",
                prefix=".cer_",
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)

                # Verify non-empty before rename
                temp_size = os.path.getsize(temp_path)
                if temp_size == 0:
                    os.unlink(temp_path)
                    raise PartialWriteError(str(artifact_path))

                # Atomic rename
                os.rename(temp_path, artifact_path)

            except Exception:
                # Clean up temp file on any error
                try:
                    os.unlink(temp_path)
                except OSError:
                    pass
                raise

        except PartialWriteError:
            raise
        except Exception as e:
            raise AtomicWriteError(
                f"Failed to write {relative_path}: {e}"
            ) from e

        # Compute hash after successful rename
        file_hash = self._sha256(artifact_path)
        timestamp = datetime.now(timezone.utc).isoformat()

        lineage = {
            "artifact": relative_path,
            "hash_sha256": file_hash,
            "size_bytes": os.path.getsize(artifact_path),
            "written_at": timestamp,
            "write_method": "atomic_temp_rename",
        }
        if metadata:
            lineage["metadata"] = metadata

        return lineage

    def write_json_unchecked(
        self,
        relative_path: str,
        data: dict[str, Any],
    ) -> None:
        """Legacy write without atomic guarantees (for backward compatibility).

        Only used during transition period. All new code must use atomic_write.
        """
        artifact_path = self.artifact_root / relative_path
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        artifact_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def verify_artifact(self, relative_path: str) -> dict[str, Any]:
        """Verify artifact exists, non-empty, and return its metadata."""
        artifact_path = self.artifact_root / relative_path
        if not artifact_path.exists():
            return {"status": "missing", "path": str(artifact_path)}
        size = artifact_path.stat().st_size
        if size == 0:
            return {"status": "partial_write", "path": str(artifact_path), "size": 0}
        return {
            "status": "valid",
            "path": str(artifact_path),
            "size": size,
            "hash_sha256": self._sha256(artifact_path),
            "modified_at": datetime.fromtimestamp(
                artifact_path.stat().st_mtime, tz=timezone.utc
            ).isoformat(),
        }

    # ── Completeness Checks ─────────────────────────────────────────────────

    def check_lane_bundle_complete(
        self, lane: str, step_prefix: str = "03_lanes"
    ) -> list[str]:
        """Return list of missing artifacts for a lane bundle."""
        required = LANE_REQUIRED_ARTIFACTS.get(lane, [])
        missing = []
        for artifact in required:
            artifact_path = self.artifact_root / step_prefix / artifact
            if not artifact_path.exists() or artifact_path.stat().st_size == 0:
                missing.append(artifact)
        return missing

    def verify_gate_bundle(self, gate: str, step_prefix: str = "04_adjudication") -> dict[str, Any]:
        """Verify all artifacts required for a gate bundle are present."""
        required = GATE_BUNDLE_REQUIREMENTS.get(gate, [])
        results = {}
        for artifact in required:
            artifact_path = self.artifact_root / step_prefix / artifact
            results[artifact] = self.verify_artifact(str(step_prefix / artifact))
        missing = [a for a, r in results.items() if r["status"] != "valid"]
        return {
            "gate": gate,
            "complete": len(missing) == 0,
            "missing_artifacts": missing,
            "all_artifacts": results,
        }

    def verify_closure_bundle(self) -> dict[str, Any]:
        """Verify all artifacts required for CLOSED state."""
        results = {}
        missing = []
        for rel_path in CLOSURE_BUNDLE_INDEX_REQUIRED:
            result = self.verify_artifact(rel_path)
            results[rel_path] = result
            if result["status"] != "valid":
                missing.append(rel_path)
        return {
            "closure_complete": len(missing) == 0,
            "missing_artifacts": missing,
            "all_artifacts": results,
        }

    def write_closure_bundle_index(
        self,
        run_id: str,
        closure_type: str,
        extra_artifacts: list[str] | None = None,
    ) -> None:
        """Write closure_bundle_index.json after verifying all required artifacts."""
        required = list(CLOSURE_BUNDLE_INDEX_REQUIRED)
        if extra_artifacts:
            required.extend(extra_artifacts)

        results = {}
        for rel_path in required:
            results[rel_path] = self.verify_artifact(rel_path)

        missing = [p for p, r in results.items() if r["status"] != "valid"]

        index = {
            "schema_name": "cer_closure_bundle_index",
            "schema_version": "v1",
            "run_id": run_id,
            "bundle_id": "B-CL-001",
            "closure_type": closure_type,
            "required_artifacts": required,
            "verification_results": results,
            "closure_complete": len(missing) == 0,
            "missing_artifacts": missing,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

        self.atomic_write(
            "06_closure/closure_bundle_index.json",
            index,
            metadata={"bundle_type": "CLOSURE_BUNDLE", "run_id": run_id},
        )

    def write_error_artifact(
        self,
        error_type: str,
        agent_name: str,
        error_message: str,
        context: dict[str, Any] | None = None,
    ) -> str:
        """Write a runtime error artifact for observability."""
        error_artifact = {
            "schema_name": "cer_runtime_error",
            "schema_version": "v1",
            "error_type": error_type,
            "agent_name": agent_name,
            "error_message": error_message,
            "context": context or {},
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        error_path = f"00_manifest/errors/{error_type}_{agent_name}_{int(time.time())}.json"
        self.atomic_write(error_path, error_artifact)
        return error_path

    # ── Lineage Tracking ──────────────────────────────────────────────────────

    def write_lineage_registry(
        self,
        run_id: str,
        round_id: str,
        artifacts: list[dict[str, str]],
    ) -> None:
        """Write artifact lineage registry for a run."""
        registry = {
            "schema_name": "cer_artifact_lineage_registry",
            "schema_version": "v1",
            "run_id": run_id,
            "round_id": round_id,
            "artifacts": artifacts,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        self.atomic_write(
            "governance/artifact_lineage_registry.json",
            registry,
            metadata={"run_id": run_id, "round_id": round_id},
        )

    # ── Helpers ─────────────────────────────────────────────────────────────

    @staticmethod
    def _sha256(path: Path) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()
