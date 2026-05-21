"""CER Rework Comparison — Round Isolation & Comparison API

Implements:
- Round isolation (archived round vs new round)
- Side-by-side lane output comparison
- Lane artifact status: UNCHANGED | CHANGED | NEW
- Gate decision comparison (prior vs current)
- Rework scope visibility

Frozen baseline: CER_GOVERNANCE_AND_OBSERVABILITY_PLAN_V1.md Section 5
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..artifact_writer import CERArtifactWriter, LANE_REQUIRED_ARTIFACTS

logger = logging.getLogger(__name__)


# ── Lane Artifacts by Round ────────────────────────────────────────────────────


LANE_ARTIFACTS_ORDERED = [
    "lane_2a_claim",
    "lane_2b_evidence",
    "lane_2c_equivalence",
    "lane_2d_consistency_pmcf",
]

LANE_DISPLAY_NAMES: dict[str, str] = {
    "lane_2a_claim": "2a — Claim Consistency",
    "lane_2b_evidence": "2b — SOTA Evidence",
    "lane_2c_equivalence": "2c — Equivalence",
    "lane_2d_consistency_pmcf": "2d — Consistency & PMCF",
}


# ── Rework Comparator ───────────────────────────────────────────────────────────


class ReworkComparator:
    """CER rework comparison API.

    Round isolation: when rework is triggered, original round (Round N) is
    archived as S19 and a new round (Round N+1) starts. Both rounds exist
    as separate directory trees.

    Directory structure:
        artifacts/cer/{project_id}/round_001/...
        artifacts/cer/{project_id}/round_002/...
        artifacts/cer/{project_id}/round_001_archived/...  (S19 archived)
    """

    LANE_STEP_PREFIX = "03_lanes"
    ADJUDICATION_PREFIX = "04_adjudication"

    def __init__(self, artifact_root: Path):
        self.artifact_root = Path(artifact_root)
        self._writer = CERArtifactWriter(artifact_root)

    # ── Core Comparison ───────────────────────────────────────────────────────

    def get_round_comparison(
        self,
        project_id: str,
        round_n: int,
        round_n_plus_1: int,
    ) -> dict[str, Any]:
        """Returns side-by-side summary of all lane outputs for two rounds.

        round_n: the prior (archived) round number
        round_n_plus_1: the current (active) round number
        """
        round_n_id = f"round_{round_n:03d}"
        round_np1_id = f"round_{round_n_plus_1:03d}"

        round_n_root = self.artifact_root / project_id / round_n_id
        round_np1_root = self.artifact_root / project_id / round_np1_id

        lane_comparisons = []
        for lane in LANE_ARTIFACTS_ORDERED:
            lane_comparison = self._compare_lane(
                lane, round_n_root, round_np1_root
            )
            lane_comparisons.append(lane_comparison)

        gate_decision_comparison = self._compare_gate_decisions(
            project_id, round_n_id, round_np1_id
        )

        return {
            "project_id": project_id,
            "round_n": {
                "round_id": round_n_id,
                "path": str(round_n_root),
                "exists": round_n_root.exists(),
            },
            "round_n_plus_1": {
                "round_id": round_np1_id,
                "path": str(round_np1_root),
                "exists": round_np1_root.exists(),
            },
            "lane_comparisons": lane_comparisons,
            "gate_decision_comparison": gate_decision_comparison,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    def _compare_lane(
        self,
        lane: str,
        round_n_root: Path,
        round_np1_root: Path,
    ) -> dict[str, Any]:
        """Compare lane artifacts between two rounds."""
        required = LANE_REQUIRED_ARTIFACTS.get(lane, [])

        lane_n_root = round_n_root / self.LANE_STEP_PREFIX
        lane_np1_root = round_np1_root / self.LANE_STEP_PREFIX

        comparisons = []
        for artifact in required:
            n_path = lane_n_root / artifact
            np1_path = lane_np1_root / artifact

            n_exists = n_path.exists() and n_path.stat().st_size > 0
            np1_exists = np1_path.exists() and np1_path.stat().st_size > 0

            if n_exists and np1_exists:
                # Both exist — compare content
                n_hash = self._hash_file(n_path)
                np1_hash = self._hash_file(np1_path)
                status = "UNCHANGED" if n_hash == np1_hash else "CHANGED"
            elif np1_exists and not n_exists:
                status = "NEW"
            elif n_exists and not np1_exists:
                status = "REMOVED"
            else:
                status = "BOTH_MISSING"

            comparisons.append({
                "artifact": artifact,
                "round_n_status": "present" if n_exists else "absent",
                "round_n_plus_1_status": "present" if np1_exists else "absent",
                "status": status,
            })

        return {
            "lane": lane,
            "display_name": LANE_DISPLAY_NAMES.get(lane, lane),
            "artifacts": comparisons,
        }

    def _compare_gate_decisions(
        self,
        project_id: str,
        round_n_id: str,
        round_np1_id: str,
    ) -> dict[str, Any]:
        """Compare gate decisions between rounds."""
        comparison = {}
        for gate in ["GATE_1", "GATE_3"]:
            n_decision = self._read_gate_decision(project_id, round_n_id, gate)
            np1_decision = self._read_gate_decision(project_id, round_np1_id, gate)
            comparison[gate] = {
                "round_n": n_decision,
                "round_n_plus_1": np1_decision,
            }
        return comparison

    def _read_gate_decision(
        self, project_id: str, round_id: str, gate: str
    ) -> dict[str, Any] | None:
        """Read a gate decision artifact for a round."""
        gate_file = f"{self.ADJUDICATION_PREFIX}/gate_{gate.lower().replace('gate_', '')}_decision.json"
        # Map GATE_1 → gate_1_decision.json, GATE_3 → gate_3_decision.json
        if gate == "GATE_1":
            gate_file = f"{self.ADJUDICATION_PREFIX}/gate_1_decision.json"
        elif gate == "GATE_3":
            gate_file = f"{self.ADJUDICATION_PREFIX}/gate_3_decision.json"

        path = self.artifact_root / project_id / round_id / gate_file
        if not path.exists():
            return None
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return None

    @staticmethod
    def _hash_file(path: Path) -> str:
        import hashlib
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()

    # ── Rework Scope Visibility ───────────────────────────────────────────────

    def get_rework_scope(
        self,
        project_id: str,
        run_id: str,
        round_id: str,
    ) -> dict[str, Any] | None:
        """Return rework scope information from ledger entry.

        Looks up the REWORK_SCOPE ledger entry for this run/round.
        """
        # This would be called with ledger data already loaded
        # Return structure matching CER_GOVERNANCE_AND_OBSERVABILITY_PLAN_V1.md Section 5.3
        return None  # Caller must populate from ledger

    # ── Lane-Level Status ─────────────────────────────────────────────────────

    def get_lane_status(
        self,
        project_id: str,
        round_id: str,
        lane: str,
    ) -> dict[str, Any]:
        """Get status of all artifacts for a lane in a specific round."""
        required = LANE_REQUIRED_ARTIFACTS.get(lane, [])
        lane_root = self.artifact_root / project_id / round_id / self.LANE_STEP_PREFIX

        artifacts = []
        missing = []
        for artifact in required:
            path = lane_root / artifact
            if path.exists() and path.stat().st_size > 0:
                artifacts.append({
                    "artifact": artifact,
                    "status": "present",
                    "size": path.stat().st_size,
                    "hash": self._hash_file(path),
                })
            else:
                missing.append(artifact)

        return {
            "lane": lane,
            "round_id": round_id,
            "project_id": project_id,
            "complete": len(missing) == 0,
            "missing_artifacts": missing,
            "present_artifacts": artifacts,
        }
