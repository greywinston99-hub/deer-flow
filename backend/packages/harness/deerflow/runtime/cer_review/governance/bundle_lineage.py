"""CER Bundle Lineage Tracker — Artifact Provenance

Implements:
- Artifact dependency graph
- Bundle provenance manifest (inputs → outputs)
- Per-artifact derived_from tracking
- 5-agent BRR composite provenance
- Lane artifact lineage

Frozen baseline: CER_GOVERNANCE_AND_OBSERVABILITY_PLAN_V1.md Section 4
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ── CER Agent IDs ──────────────────────────────────────────────────────────────


CER_AGENT_IDS: dict[str, str] = {
    "cer_route_screen_agent": "AG-001",
    "cer_layer1_scan_agent": "AG-002",
    "cer_claim_scope_agent": "AG-003",
    "cer_sota_evidence_agent": "AG-004",
    "cer_equivalence_agent": "AG-005",
    "cer_consistency_agent": "AG-006",
    "cer_pmcf_lifecycle_agent": "AG-007",
    "cer_review_package_agent": "AG-008",
    "cer_gate_closure_agent": "AG-009",
    "cer_intake_agent": "AG-010",
}

# ── Standard Lane Output Artifacts ─────────────────────────────────────────────


LANE_ARTIFACT_MAP: dict[str, dict[str, str]] = {
    "lane_2a_claim": {
        "claim_consistency_matrix.json": "AG-003",
        "risk_benefit_contribution_report.json": "AG-003",
    },
    "lane_2b_evidence": {
        "evidence_qualified_report.json": "AG-004",
        "risk_benefit_contribution_report.json": "AG-004",
    },
    "lane_2c_equivalence": {
        "difference_impact_assessment.json": "AG-005",
        "access_verification_findings.json": "AG-005",
        "risk_benefit_contribution_report.json": "AG-005",
    },
    "lane_2d_consistency_pmcf": {
        "cross_doc_consistency_report.json": "AG-006",
        "pmcf_need_statement.json": "AG-007",
        "pmcf_adequacy_assessment.json": "AG-007",
        "risk_benefit_contribution_reports.json": "AG-006",
    },
}


# ── Bundle Lineage Tracker ──────────────────────────────────────────────────────


class BundleLineageTracker:
    """CER bundle lineage and artifact provenance tracker.

    Tracks:
    - Bundle provenance (which agents contributed to which bundle)
    - Artifact dependency graph (which artifacts were derived from which inputs)
    - BRR composite assembly provenance (5-agent contribution chain)

    Stored in: governance/bundle_lineage/{bundle_id}_lineage.json
    """

    LINEAGE_DIR = "governance/bundle_lineage"
    SCHEMA_NAME = "cer_bundle_lineage"
    SCHEMA_VERSION = "v1"
    AGENT_CONTRIBUTION_SCHEMA = ["AG-003", "AG-004", "AG-005", "AG-006", "AG-007"]

    def __init__(self, artifact_root: Path):
        self.artifact_root = Path(artifact_root)

    # ── Lane Artifact Lineage ─────────────────────────────────────────────────

    def track_lane_artifact(
        self,
        run_id: str,
        round_id: str,
        lane: str,
        artifact_name: str,
        derived_from: list[str] | None = None,
        evidence_packs: list[str] | None = None,
        project_id: str = "CER-PJT-UNKNOWN",
    ) -> str:
        """Track a lane artifact's provenance.

        Returns the lineage artifact path.
        """
        agent_id = LANE_ARTIFACT_MAP.get(lane, {}).get(artifact_name, "UNKNOWN")

        lineage = {
            "schema_name": self.SCHEMA_NAME,
            "schema_version": self.SCHEMA_VERSION,
            "artifact_name": artifact_name,
            "artifact_version": "v1",
            "lane": lane,
            "produced_by_agent": agent_id,
            "produced_by": lane.replace("_", " ").title(),
            "derived_from": derived_from or [],
            "evidence_packs": evidence_packs or [],
            "run_id": run_id,
            "round_id": round_id,
            "produced_at": datetime.now(timezone.utc).isoformat(),
            "project_id": project_id,
        }

        return self._write_lineage(project_id, run_id, lane, artifact_name, lineage)

    # ── Bundle Provenance ─────────────────────────────────────────────────────

    def track_bundle(
        self,
        run_id: str,
        round_id: str,
        bundle_id: str,
        bundle_type: str,
        inputs: list[dict[str, str]],
        output_artifact: str,
        output_decision: str | None = None,
        project_id: str = "CER-PJT-UNKNOWN",
    ) -> str:
        """Track a gate bundle's provenance (which agents/artifacts contributed).

        inputs: [{"artifact": "...", "from_agent": "AG-XXX"}, ...]
        """
        lineage = {
            "schema_name": self.SCHEMA_NAME,
            "schema_version": self.SCHEMA_VERSION,
            "bundle_id": bundle_id,
            "bundle_type": bundle_type,
            "produced_at": datetime.now(timezone.utc).isoformat(),
            "inputs": inputs,
            "output": {
                "artifact": output_artifact,
                "decision": output_decision,
            },
            "run_id": run_id,
            "round_id": round_id,
            "project_id": project_id,
        }

        return self._write_lineage(project_id, run_id, bundle_type, bundle_id, lineage)

    # ── BRR Composite Provenance ─────────────────────────────────────────────

    def track_brr_composite(
        self,
        run_id: str,
        round_id: str,
        brr_bundle_id: str,
        contributions: list[dict[str, str]],
        output_artifact: str = "risk_benefit_composite_assembly.json",
        project_id: str = "CER-PJT-UNKNOWN",
    ) -> str:
        """Track BRR composite assembly provenance.

        The BRR composite is assembled at S10 (system) from 5 agent contributions:
        - AG-003: risk_benefit_contribution_report (lane_2a)
        - AG-004: risk_benefit_contribution_report (lane_2b)
        - AG-005: risk_benefit_contribution_report (lane_2c)
        - AG-006: risk_benefit_contribution_reports (lane_2d)
        - AG-007: pmcf adequacy assessment (lane_2d)

        Verifies all 5 required contributions are present.
        """
        contribution_agent_ids = {c.get("from_agent") for c in contributions}
        required = set(self.AGENT_CONTRIBUTION_SCHEMA)
        missing = required - contribution_agent_ids

        lineage = {
            "schema_name": self.SCHEMA_NAME,
            "schema_version": self.SCHEMA_VERSION,
            "artifact_name": output_artifact,
            "artifact_version": "v1",
            "bundle_id": brr_bundle_id,
            "bundle_type": "RISK_BENEFIT_COMPOSITE",
            "produced_by": "system",
            "produced_at": datetime.now(timezone.utc).isoformat(),
            "contributions": contributions,
            "contributions_verified": {
                agent_id: ("present" if agent_id in contribution_agent_ids else "absent")
                for agent_id in required
            },
            "all_contributions_present": len(missing) == 0,
            "missing_contributions": list(missing),
            "run_id": run_id,
            "round_id": round_id,
            "project_id": project_id,
        }

        return self._write_lineage(project_id, run_id, "BRR_COMPOSITE", brr_bundle_id, lineage)

    # ── Artifact Dependency Graph ─────────────────────────────────────────────

    def build_artifact_dependency(
        self,
        run_id: str,
        artifact_name: str,
        derived_from: list[str],
        produced_by: str,
        produced_by_agent: str,
        project_id: str = "CER-PJT-UNKNOWN",
    ) -> dict[str, Any]:
        """Build an artifact dependency graph entry.

        Returns the dependency dict (caller can add to a graph structure).
        """
        return {
            "artifact_name": artifact_name,
            "artifact_version": "v1",
            "derived_from": derived_from,
            "produced_by": produced_by,
            "produced_by_agent": produced_by_agent,
            "run_id": run_id,
            "produced_at": datetime.now(timezone.utc).isoformat(),
            "project_id": project_id,
        }

    # ── Read ────────────────────────────────────────────────────────────────

    def get_lineage(
        self, project_id: str, lineage_id: str
    ) -> dict[str, Any] | None:
        """Read a lineage record by its ID."""
        lineage_dir = self.artifact_root / self.LINEAGE_DIR / project_id
        # Find the file that contains this lineage_id
        candidates = list(lineage_dir.glob(f"*_{lineage_id}.json"))
        if not candidates:
            return None
        with open(candidates[0], encoding="utf-8") as f:
            return json.load(f)

    def get_all_lineages_for_run(
        self, project_id: str, run_id: str
    ) -> list[dict[str, Any]]:
        """Get all lineage records for a run."""
        lineage_dir = self.artifact_root / self.LINEAGE_DIR / project_id
        if not lineage_dir.exists():
            return []
        results = []
        for path in lineage_dir.glob("*.json"):
            try:
                with open(path, encoding="utf-8") as f:
                    obj = json.load(f)
                    if obj.get("run_id") == run_id:
                        results.append(obj)
            except (json.JSONDecodeError, OSError):
                pass
        return sorted(results, key=lambda x: x.get("produced_at", ""))

    # ── Internal ─────────────────────────────────────────────────────────────

    def _write_lineage(
        self,
        project_id: str,
        run_id: str,
        category: str,
        lineage_id: str,
        lineage: dict[str, Any],
    ) -> str:
        lineage_dir = self.artifact_root / self.LINEAGE_DIR / project_id
        lineage_dir.mkdir(parents=True, exist_ok=True)

        filename = f"{category}_{lineage_id}.json"
        rel_path = f"{self.LINEAGE_DIR}/{project_id}/{filename}"
        lineage_path = lineage_dir / filename

        # Atomic write
        fd, temp = tempfile.mkstemp(
            dir=str(lineage_dir), suffix=".tmp", prefix=".lineage_"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(lineage, f, indent=2, ensure_ascii=False)
            if os.path.getsize(temp) == 0:
                os.unlink(temp)
                raise OSError(f"Partial write for {lineage_path}")
            os.rename(temp, lineage_path)
        except Exception:
            try:
                os.unlink(temp)
            except OSError:
                pass
            raise

        logger.info(f"Bundle lineage written: {rel_path}")
        return rel_path
