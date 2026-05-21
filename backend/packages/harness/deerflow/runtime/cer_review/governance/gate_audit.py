"""CER Gate Audit Trail — Per-Gate Audit Records

Implements:
- Permanent audit record for each gate (GATE_0/1/2/3)
- Gate decision with actor, timestamp, bundle_ref, re-authentication
- Contributions verified (5-agent BRR composite for GATE_3)
- Atomic write for audit records
- Audit read API

Frozen baseline: CER_GOVERNANCE_AND_OBSERVABILITY_PLAN_V1.md Section 2
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


# ── Gate Definitions ───────────────────────────────────────────────────────────


GATE_AUDIT_SCHEMA: dict[str, dict[str, Any]] = {
    "GATE_0": {
        "decision": str,
        "actor": str,
        "timestamp": str,
        "trigger": str,
        "bundle_ref": str,
        "run_id": str,
        "round_id": str,
    },
    "GATE_1": {
        "gate": str,
        "decision": str,
        "equivalence_route": str,
        "actor": str,
        "actor_role": str,
        "timestamp": str,
        "trigger": str,
        "bundle_ref": str,
        "run_id": str,
        "round_id": str,
    },
    "GATE_2": {
        "gate": str,
        "decision": str,
        "per_item_decisions": list,
        "actor": str,
        "timestamp": str,
        "reauth_timestamp": str,
        "bundle_ref": str,
        "run_id": str,
        "round_id": str,
    },
    "GATE_3": {
        "gate": str,
        "decision": str,
        "conditional": bool,
        "outstanding_rework": list,
        "actor": str,
        "actor_id": str,
        "actor_role": str,
        "reauth_timestamp": str,
        "brr_composite_bundle_ref": str,
        "contributions_verified": dict,
        "timestamp": str,
        "run_id": str,
        "round_id": str,
    },
}


# ── Gate Auditor ────────────────────────────────────────────────────────────────


class GateAuditor:
    """CER gate audit trail manager.

    Produces permanent audit records for GATE_0/1/2/3 stored in:
        governance/gate_audits/B-G{n}-XXX.json

    Each gate decision creates one audit file. Overwrites are not allowed —
    a new file is created for each decision with an incrementing sequence number.
    """

    AUDIT_DIR = "governance/gate_audits"
    SCHEMA_NAME = "cer_gate_audit"
    SCHEMA_VERSION = "v1"

    def __init__(self, artifact_root: Path):
        self.artifact_root = Path(artifact_root)

    # ── Write ────────────────────────────────────────────────────────────────

    def write_gate0_audit(
        self,
        run_id: str,
        round_id: str,
        decision: str,
        actor: str,
        trigger: str,
        bundle_ref: str = "",
        project_id: str = "CER-PJT-UNKNOWN",
    ) -> str:
        """Write GATE_0 audit record.

        GATE_0 is the intake confirmation gate, issued by human_protocol_owner.
        """
        audit_data = {
            "schema_name": self.SCHEMA_NAME,
            "schema_version": self.SCHEMA_VERSION,
            "gate": "GATE_0",
            "decision": decision,
            "actor": actor,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "trigger": trigger,
            "bundle_ref": bundle_ref,
            "run_id": run_id,
            "round_id": round_id,
            "project_id": project_id,
        }
        return self._write_audit(project_id, "G0", audit_data)

    def write_gate1_audit(
        self,
        run_id: str,
        round_id: str,
        decision: str,
        equivalence_route: str,
        actor: str,
        trigger: str,
        bundle_ref: str = "",
        project_id: str = "CER-PJT-UNKNOWN",
        actor_role: str = "",
    ) -> str:
        """Write GATE_1 audit record.

        GATE_1 is the route determination gate, issued by human_route_adjudicator.
        equivalence_route: APPROVE_EQUIVALENCE_ROUTE | CONDITIONAL_EQUIVALENCE | NEW_SUBMISSION
        """
        audit_data = {
            "schema_name": self.SCHEMA_NAME,
            "schema_version": self.SCHEMA_VERSION,
            "gate": "GATE_1",
            "decision": decision,
            "equivalence_route": equivalence_route,
            "actor": actor,
            "actor_role": actor_role,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "trigger": trigger,
            "bundle_ref": bundle_ref,
            "run_id": run_id,
            "round_id": round_id,
            "project_id": project_id,
        }
        return self._write_audit(project_id, "G1", audit_data)

    def write_gate2_audit(
        self,
        run_id: str,
        round_id: str,
        decision: str,
        per_item_decisions: list[dict[str, Any]],
        actor: str,
        reauth_timestamp: str,
        bundle_ref: str = "",
        project_id: str = "CER-PJT-UNKNOWN",
    ) -> str:
        """Write GATE_2 audit record.

        GATE_2 is the clinical evidence gate, issued by human_clinical_adjudicator.
        per_item_decisions: list of {item_id, decision, rationale}
        """
        audit_data = {
            "schema_name": self.SCHEMA_NAME,
            "schema_version": self.SCHEMA_VERSION,
            "gate": "GATE_2",
            "decision": decision,
            "per_item_decisions": per_item_decisions,
            "actor": actor,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "reauth_timestamp": reauth_timestamp,
            "bundle_ref": bundle_ref,
            "run_id": run_id,
            "round_id": round_id,
            "project_id": project_id,
        }
        return self._write_audit(project_id, "G2", audit_data)

    def write_gate3_audit(
        self,
        run_id: str,
        round_id: str,
        decision: str,
        actor: str,
        actor_id: str,
        actor_role: str,
        reauth_timestamp: str,
        brr_composite_bundle_ref: str,
        contributions_verified: dict[str, str],
        conditional: bool = False,
        outstanding_rework: list[str] | None = None,
        project_id: str = "CER-PJT-UNKNOWN",
    ) -> str:
        """Write GATE_3 audit record.

        GATE_3 is the BRR adjudication gate, issued by human_clinical_adjudication.
        This is the only gate that can issue RISK_BENEFIT terminal decisions.

        contributions_verified: {agent_id: "present" | "absent", ...}
            Required agents: AG-003, AG-004, AG-005, AG-006, AG-007
        """
        if outstanding_rework is None:
            outstanding_rework = []

        audit_data = {
            "schema_name": self.SCHEMA_NAME,
            "schema_version": self.SCHEMA_VERSION,
            "gate": "GATE_3",
            "decision": decision,
            "conditional": conditional,
            "outstanding_rework": outstanding_rework,
            "actor": actor,
            "actor_id": actor_id,
            "actor_role": actor_role,
            "reauth_timestamp": reauth_timestamp,
            "brr_composite_bundle_ref": brr_composite_bundle_ref,
            "contributions_verified": contributions_verified,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "run_id": run_id,
            "round_id": round_id,
            "project_id": project_id,
        }
        return self._write_audit(project_id, "G3", audit_data)

    def _write_audit(
        self,
        project_id: str,
        gate_suffix: str,
        audit_data: dict[str, Any],
    ) -> str:
        """Write audit record atomically. Returns the file path."""
        audit_dir = self.artifact_root / self.AUDIT_DIR / project_id
        audit_dir.mkdir(parents=True, exist_ok=True)

        # Compute sequence number for this gate
        existing = list(audit_dir.glob(f"B-{gate_suffix}-*.json"))
        seq = len(existing) + 1
        filename = f"B-{gate_suffix}-{seq:03d}.json"
        rel_path = f"{self.AUDIT_DIR}/{project_id}/{filename}"

        # Atomic write
        audit_path = audit_dir / filename
        fd, temp = tempfile.mkstemp(dir=str(audit_dir), suffix=".tmp", prefix=".audit_")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(audit_data, f, indent=2, ensure_ascii=False)
            if os.path.getsize(temp) == 0:
                os.unlink(temp)
                raise OSError(f"Partial write for {audit_path}")
            os.rename(temp, audit_path)
        except Exception:
            try:
                os.unlink(temp)
            except OSError:
                pass
            raise

        logger.info(
            f"Gate audit written: {rel_path} gate={audit_data.get('gate')} "
            f"decision={audit_data.get('decision')} actor={audit_data.get('actor')}"
        )
        return rel_path

    # ── Read ────────────────────────────────────────────────────────────────

    def get_latest_audit(self, project_id: str, gate: str) -> dict[str, Any] | None:
        """Return the most recent audit record for a gate."""
        gate_suffix = {"GATE_0": "G0", "GATE_1": "G1", "GATE_2": "G2", "GATE_3": "G3"}.get(gate)
        if not gate_suffix:
            return None
        audit_dir = self.artifact_root / self.AUDIT_DIR / project_id
        audits = sorted(audit_dir.glob(f"B-{gate_suffix}-*.json"), key=lambda p: p.name)
        if not audits:
            return None
        with open(audits[-1], encoding="utf-8") as f:
            return json.load(f)

    def get_all_audits(self, project_id: str, gate: str) -> list[dict[str, Any]]:
        """Return all audit records for a gate, oldest first."""
        gate_suffix = {"GATE_0": "G0", "GATE_1": "G1", "GATE_2": "G2", "GATE_3": "G3"}.get(gate)
        if not gate_suffix:
            return []
        audit_dir = self.artifact_root / self.AUDIT_DIR / project_id
        audits = sorted(audit_dir.glob(f"B-{gate_suffix}-*.json"), key=lambda p: p.name)
        results = []
        for path in audits:
            with open(path, encoding="utf-8") as f:
                results.append(json.load(f))
        return results

    def get_all_audits_for_run(
        self, project_id: str, run_id: str
    ) -> dict[str, dict[str, Any]]:
        """Return latest audit per gate for a specific run."""
        latest = {}
        for gate in ["GATE_0", "GATE_1", "GATE_2", "GATE_3"]:
            all_audits = self.get_all_audits(project_id, gate)
            matching = [a for a in all_audits if a.get("run_id") == run_id]
            if matching:
                latest[gate] = matching[-1]
        return latest
