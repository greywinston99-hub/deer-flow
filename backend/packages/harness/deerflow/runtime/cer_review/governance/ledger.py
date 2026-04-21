"""CER Decision Ledger — Append-Only Governance Record

Implements:
- Append-only ledger with atomic write
- LEDGER-XXX auto-incrementing entry IDs
- Entry immutability (never modify/delete after creation)
- Structured ledger with project_id, run_id, round_id, actor, decision_data
- Ledger read/query API

Frozen baseline: CER_GOVERNANCE_AND_OBSERVABILITY_PLAN_V1.md Section 1
"""

from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ── Entry Types ────────────────────────────────────────────────────────────────


class LedgerEntryType:
    STATE_TRANSITION = "STATE_TRANSITION"
    GATE_DECISION = "GATE_DECISION"
    TERMINAL_DECISION = "TERMINAL_DECISION"
    REWORK_SCOPE = "REWORK_SCOPE"
    FOLLOWUP_CREATE = "FOLLOWUP_CREATE"
    BACKFLOW_CREATE = "BACKFLOW_CREATE"
    LANE_COMPLETE = "LANE_COMPLETE"
    BUNDLE_ASSEMBLY = "BUNDLE_ASSEMBLY"


LEDGER_ENTRY_TYPES = {
    LedgerEntryType.STATE_TRANSITION,
    LedgerEntryType.GATE_DECISION,
    LedgerEntryType.TERMINAL_DECISION,
    LedgerEntryType.REWORK_SCOPE,
    LedgerEntryType.FOLLOWUP_CREATE,
    LedgerEntryType.BACKFLOW_CREATE,
    LedgerEntryType.LANE_COMPLETE,
    LedgerEntryType.BUNDLE_ASSEMBLY,
}

# ── Ledger ─────────────────────────────────────────────────────────────────────


class DecisionLedger:
    """Append-only decision ledger.

    Ledger structure:
    {
      "schema_name": "cer_decision_ledger",
      "project_id": "CER-PJT-0001",
      "entries": [
        {
          "entry_id": "LEDGER-001",
          "entry_type": "STATE_TRANSITION",
          "run_id": "...",
          "round_id": "round_001",
          "from_state": "S00",
          "to_state": "S01",
          "trigger": "gate_0_decision",
          "actor": "human_protocol_owner",
          "timestamp": "2026-04-16T16:03:28.654399+00:00",
          "decision_data": {...},
          "immutable": true
        },
        ...
      ]
    }

    Rules:
    - Entries are NEVER modified after creation
    - Entries are NEVER deleted
    - Corrections create new entries (not overwrites)
    - entry_id is assigned by Ledger.append() — never by caller
    """

    LEDGER_FILENAME = "governance/decision_ledger.json"
    SCHEMA_NAME = "cer_decision_ledger"
    SCHEMA_VERSION = "v1"

    def __init__(self, artifact_root: Path):
        self.artifact_root = Path(artifact_root)
        self._lock = threading.Lock()
        self._ensure_governance_dir()

    def _ensure_governance_dir(self) -> None:
        governance_dir = self.artifact_root / "governance"
        governance_dir.mkdir(parents=True, exist_ok=True)

    # ── Core Append ───────────────────────────────────────────────────────────

    def append(
        self,
        entry_type: str,
        run_id: str,
        round_id: str,
        actor: str,
        decision_data: dict[str, Any],
        *,
        from_state: str | None = None,
        to_state: str | None = None,
        trigger: str | None = None,
        gate: str | None = None,
        supersedes: str | None = None,
        project_id: str = "CER-PJT-UNKNOWN",
        extra: dict[str, Any] | None = None,
    ) -> str:
        """Append a new entry to the ledger.

        Returns the assigned entry_id (e.g., "LEDGER-001").

        This method is thread-safe and uses atomic write.
        """
        if entry_type not in LEDGER_ENTRY_TYPES:
            raise ValueError(f"Invalid entry_type: {entry_type}")

        with self._lock:
            ledger = self._read_ledger_unlocked(project_id)
            entry_id = self._next_entry_id(ledger)
            timestamp = datetime.now(timezone.utc).isoformat()

            entry: dict[str, Any] = {
                "entry_id": entry_id,
                "entry_type": entry_type,
                "run_id": run_id,
                "round_id": round_id,
                "actor": actor,
                "timestamp": timestamp,
                "decision_data": decision_data,
                "immutable": True,
            }

            if from_state is not None:
                entry["from_state"] = from_state
            if to_state is not None:
                entry["to_state"] = to_state
            if trigger is not None:
                entry["trigger"] = trigger
            if gate is not None:
                entry["gate"] = gate
            if supersedes is not None:
                entry["supersedes"] = supersedes
            if extra is not None:
                entry.update(extra)

            ledger["entries"].append(entry)
            self._write_ledger_unlocked(ledger, project_id)

        logger.info(
            f"Ledger append: {entry_id} ({entry_type}) "
            f"run={run_id} round={round_id} actor={actor}"
        )
        return entry_id

    # ── Convenience Factory Methods ────────────────────────────────────────────

    def append_state_transition(
        self,
        run_id: str,
        round_id: str,
        from_state: str,
        to_state: str,
        actor: str,
        trigger: str,
        decision_data: dict[str, Any] | None = None,
        project_id: str = "CER-PJT-UNKNOWN",
    ) -> str:
        """Append a STATE_TRANSITION entry."""
        return self.append(
            entry_type=LedgerEntryType.STATE_TRANSITION,
            run_id=run_id,
            round_id=round_id,
            actor=actor,
            decision_data=decision_data or {},
            from_state=from_state,
            to_state=to_state,
            trigger=trigger,
            project_id=project_id,
        )

    def append_gate_decision(
        self,
        run_id: str,
        round_id: str,
        gate: str,
        from_state: str,
        to_state: str,
        actor: str,
        decision_data: dict[str, Any],
        project_id: str = "CER-PJT-UNKNOWN",
        supersedes: str | None = None,
    ) -> str:
        """Append a GATE_DECISION entry."""
        return self.append(
            entry_type=LedgerEntryType.GATE_DECISION,
            run_id=run_id,
            round_id=round_id,
            actor=actor,
            decision_data=decision_data,
            gate=gate,
            from_state=from_state,
            to_state=to_state,
            project_id=project_id,
            supersedes=supersedes,
        )

    def append_terminal_decision(
        self,
        run_id: str,
        round_id: str,
        actor: str,
        decision_data: dict[str, Any],
        project_id: str = "CER-PJT-UNKNOWN",
    ) -> str:
        """Append a TERMINAL_DECISION entry (human-only final decision)."""
        return self.append(
            entry_type=LedgerEntryType.TERMINAL_DECISION,
            run_id=run_id,
            round_id=round_id,
            actor=actor,
            decision_data=decision_data,
            project_id=project_id,
        )

    def append_rework_scope(
        self,
        run_id: str,
        round_id: str,
        source_gate: str,
        decision: str,
        primary_lane: str,
        affected_objects: list[str],
        non_affected_lanes: list[str],
        project_id: str = "CER-PJT-UNKNOWN",
    ) -> str:
        """Append a REWORK_SCOPE entry (triggered when rework is ordered)."""
        return self.append(
            entry_type=LedgerEntryType.REWORK_SCOPE,
            run_id=run_id,
            round_id=round_id,
            actor="system",
            decision_data={
                "source_gate": source_gate,
                "decision": decision,
                "primary_lane": primary_lane,
                "affected_objects": affected_objects,
                "non_affected_lanes": non_affected_lanes,
            },
            project_id=project_id,
        )

    def append_followup_create(
        self,
        run_id: str,
        round_id: str,
        follow_up_id: str,
        followup_type: str,
        related_finding: str,
        description: str,
        assigned_to: str,
        due_date: str | None = None,
        closure_criteria: str | None = None,
        project_id: str = "CER-PJT-UNKNOWN",
    ) -> str:
        """Append a FOLLOWUP_CREATE entry."""
        return self.append(
            entry_type=LedgerEntryType.FOLLOWUP_CREATE,
            run_id=run_id,
            round_id=round_id,
            actor="system",
            decision_data={
                "follow_up_id": follow_up_id,
                "type": followup_type,
                "related_finding": related_finding,
                "description": description,
                "assigned_to": assigned_to,
                "due_date": due_date,
                "closure_criteria": closure_criteria,
                "status": "OPEN",
            },
            project_id=project_id,
        )

    def append_backflow_create(
        self,
        project_id: str,
        source_round: str,
        new_round: str,
        trigger_type: str,
        evidence_description: str,
        backflow_pack_ref: str,
        run_id: str = "unknown",
        round_id: str = "round_001",
    ) -> str:
        """Append a BACKFLOW_CREATE entry."""
        return self.append(
            entry_type=LedgerEntryType.BACKFLOW_CREATE,
            run_id=run_id,
            round_id=round_id,
            actor="system",
            decision_data={
                "backflow_id": f"BF-{len(self.read(project_id) or []):03d}",
                "trigger_type": trigger_type,
                "project_id": project_id,
                "source_round": source_round,
                "new_round": new_round,
                "evidence_description": evidence_description,
                "backflow_pack_ref": backflow_pack_ref,
            },
            project_id=project_id,
        )

    def append_bundle_assembly(
        self,
        run_id: str,
        round_id: str,
        bundle_id: str,
        bundle_type: str,
        agent_contributions: list[dict[str, str]],
        output_artifact: str,
        output_decision: str | None = None,
        project_id: str = "CER-PJT-UNKNOWN",
    ) -> str:
        """Append a BUNDLE_ASSEMBLY entry (system assembles a bundle for gate)."""
        return self.append(
            entry_type=LedgerEntryType.BUNDLE_ASSEMBLY,
            run_id=run_id,
            round_id=round_id,
            actor="system",
            decision_data={
                "bundle_id": bundle_id,
                "bundle_type": bundle_type,
                "agent_contributions": agent_contributions,
                "output_artifact": output_artifact,
                "output_decision": output_decision,
            },
            project_id=project_id,
        )

    # ── Read API ──────────────────────────────────────────────────────────────

    def read(self, project_id: str) -> list[dict[str, Any]]:
        """Return all entries for project, ordered by timestamp."""
        ledger = self._read_raw(project_id)
        return ledger.get("entries", []) if ledger else []

    def get_entries_for_run(self, project_id: str, run_id: str) -> list[dict[str, Any]]:
        """Filter entries by run_id."""
        return [e for e in self.read(project_id) if e.get("run_id") == run_id]

    def get_entries_for_gate(
        self, project_id: str, gate: str
    ) -> list[dict[str, Any]]:
        """Filter entries by gate."""
        return [
            e for e in self.read(project_id)
            if e.get("gate") == gate or e.get("entry_type") == LedgerEntryType.GATE_DECISION and e.get("gate") == gate
        ]

    def get_entries_for_round(
        self, project_id: str, round_id: str
    ) -> list[dict[str, Any]]:
        """Filter entries by round_id."""
        return [e for e in self.read(project_id) if e.get("round_id") == round_id]

    def get_latest_terminal_decision(
        self, project_id: str, run_id: str
    ) -> dict[str, Any] | None:
        """Return the latest TERMINAL_DECISION for a run."""
        entries = [
            e for e in self.get_entries_for_run(project_id, run_id)
            if e["entry_type"] == LedgerEntryType.TERMINAL_DECISION
        ]
        return entries[-1] if entries else None

    def get_rework_scope_entries(
        self, project_id: str, run_id: str
    ) -> list[dict[str, Any]]:
        """Return all REWORK_SCOPE entries for a run."""
        return [
            e for e in self.get_entries_for_run(project_id, run_id)
            if e["entry_type"] == LedgerEntryType.REWORK_SCOPE
        ]

    # ── Internal ─────────────────────────────────────────────────────────────

    def _ledger_path(self, project_id: str) -> Path:
        """Ledger is stored per-project."""
        # Use project_id to create project-specific path
        safe_id = project_id.replace("/", "_").replace("\\", "_")
        return self.artifact_root / f"governance/{safe_id}_decision_ledger.json"

    def _read_raw(self, project_id: str) -> dict[str, Any]:
        """Read raw ledger dict without locking."""
        path = self._ledger_path(project_id)
        if not path.exists():
            return {"schema_name": self.SCHEMA_NAME, "project_id": project_id, "entries": []}
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {"schema_name": self.SCHEMA_NAME, "project_id": project_id, "entries": []}

    def _read_ledger_unlocked(self, project_id: str) -> dict[str, Any]:
        return self._read_raw(project_id)

    def _write_ledger_unlocked(self, ledger: dict[str, Any], project_id: str) -> None:
        path = self._ledger_path(project_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        # Atomic write
        import tempfile
        import os
        fd, temp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp", prefix=".ledger_")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(ledger, f, indent=2, ensure_ascii=False)
            temp_size = os.path.getsize(temp)
            if temp_size == 0:
                os.unlink(temp)
                raise OSError(f"Partial write detected for {path}")
            os.rename(temp, path)
        except Exception:
            try:
                os.unlink(temp)
            except OSError:
                pass
            raise

    @staticmethod
    def _next_entry_id(ledger: dict[str, Any]) -> str:
        """Compute next LEDGER-XXX ID from existing entries."""
        entries = ledger.get("entries", [])
        if not entries:
            return "LEDGER-001"
        max_num = 0
        for e in entries:
            eid = e.get("entry_id", "")
            if eid.startswith("LEDGER-"):
                try:
                    num = int(eid.split("-")[1])
                    if num > max_num:
                        max_num = num
                except (ValueError, IndexError):
                    pass
        return f"LEDGER-{max_num + 1:03d}"
