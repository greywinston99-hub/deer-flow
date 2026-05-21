"""CER Follow-up & Backflow Tracker

Implements:
- Follow-up registry (F-001, F-002, ...) with OPEN/RESOLVED/CLOSED status
- Backflow registry (BF-001, BF-002, ...) for new evidence events
- Conditional pass follow-up items tracking
- Backflow pack traceability to source run/round
- Follow-up assignment and due date tracking

Frozen baseline: CER_GOVERNANCE_AND_OBSERVABILITY_PLAN_V1.md Section 6
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ── Follow-up Types ─────────────────────────────────────────────────────────────


FOLLOWUP_TYPES = {
    "PMCF_UNRESOLVED_UNCERTAINTY",
    "EQUIVALENCE_DATA_UPDATE",
    "NEW_SAFETY_SIGNAL",
    "LABELING_REVISION",
    "CER_SECTION_ANNOTATION",
    "PMCF_PLAN_UPDATE",
    "REWORK_REQUIRED",
    "OUTSTANDING_REWORK",
    "NMPA_SCOPE_CONFIRMATION",
    "EQUIVALENCE_DATA_ACCESS",
}


# ── Followup Tracker ────────────────────────────────────────────────────────────


class FollowupTracker:
    """CER follow-up item tracker.

    Follow-ups are created when:
    - GATE_3 issues a conditional pass with outstanding rework items
    - A gate decision identifies a finding that requires follow-up
    - A rework scope identifies unresolved items

    Stored in: governance/follow_up_registry.json

    Follow-up entry:
    {
      "follow_up_id": "F-001",
      "type": "PMCF_UNRESOLVED_UNCERTAINTY",
      "related_finding": "CER-Finding-003",
      "description": "Update PMCF plan with UQ-001 data collection",
      "assigned_to": "PMCF Owner",
      "status": "OPEN",
      "created_at": "2026-04-16T16:03:28.654399+00:00",
      "due_date": null,
      "closure_criteria": "PMCF plan updated and approved",
      "project_id": "CER-PJT-0001",
      "run_id": "cer-real-pjt0001-ca0b3709",
      "round_id": "round_001",
      "superseded_by": null
    }
    """

    FOLLOWUP_REGISTRY_FILE = "governance/follow_up_registry.json"
    SCHEMA_NAME = "cer_followup_registry"
    SCHEMA_VERSION = "v1"

    def __init__(self, artifact_root: Path):
        self.artifact_root = Path(artifact_root)
        self._lock = threading.Lock()
        self._ensure_governance_dir()

    def _ensure_governance_dir(self) -> None:
        governance_dir = self.artifact_root / "governance"
        governance_dir.mkdir(parents=True, exist_ok=True)

    @property
    def _registry_path(self) -> Path:
        return self.artifact_root / self.FOLLOWUP_REGISTRY_FILE

    # ── CRUD ─────────────────────────────────────────────────────────────────

    def create(
        self,
        followup_type: str,
        related_finding: str,
        description: str,
        assigned_to: str,
        closure_criteria: str,
        project_id: str,
        run_id: str,
        round_id: str,
        due_date: str | None = None,
    ) -> str:
        """Create a new follow-up item. Returns F-XXX ID."""
        if followup_type not in FOLLOWUP_TYPES:
            raise ValueError(f"Invalid followup_type: {followup_type}")

        with self._lock:
            registry = self._read_registry_unlocked(project_id)
            follow_up_id = self._next_id(registry)
            now = datetime.now(timezone.utc).isoformat()

            entry: dict[str, Any] = {
                "follow_up_id": follow_up_id,
                "type": followup_type,
                "related_finding": related_finding,
                "description": description,
                "assigned_to": assigned_to,
                "status": "OPEN",
                "created_at": now,
                "due_date": due_date,
                "closure_criteria": closure_criteria,
                "project_id": project_id,
                "run_id": run_id,
                "round_id": round_id,
                "superseded_by": None,
                "resolved_at": None,
                "closed_at": None,
            }

            registry["follow_ups"].append(entry)
            self._write_registry_unlocked(registry, project_id)

        logger.info(
            f"Follow-up created: {follow_up_id} type={followup_type} "
            f"project={project_id} assigned_to={assigned_to}"
        )
        return follow_up_id

    def resolve(
        self,
        project_id: str,
        follow_up_id: str,
        resolution_note: str | None = None,
    ) -> bool:
        """Mark a follow-up as RESOLVED (pending closure)."""
        with self._lock:
            registry = self._read_registry_unlocked(project_id)
            now = datetime.now(timezone.utc).isoformat()
            for entry in registry["follow_ups"]:
                if entry["follow_up_id"] == follow_up_id:
                    entry["status"] = "RESOLVED"
                    entry["resolved_at"] = now
                    if resolution_note:
                        entry["resolution_note"] = resolution_note
                    self._write_registry_unlocked(registry, project_id)
                    logger.info(f"Follow-up resolved: {follow_up_id}")
                    return True
            return False

    def close(
        self,
        project_id: str,
        follow_up_id: str,
        closure_note: str | None = None,
    ) -> bool:
        """Mark a follow-up as CLOSED (completed)."""
        with self._lock:
            registry = self._read_registry_unlocked(project_id)
            now = datetime.now(timezone.utc).isoformat()
            for entry in registry["follow_ups"]:
                if entry["follow_up_id"] == follow_up_id:
                    entry["status"] = "CLOSED"
                    entry["closed_at"] = now
                    if closure_note:
                        entry["closure_note"] = closure_note
                    self._write_registry_unlocked(registry, project_id)
                    logger.info(f"Follow-up closed: {follow_up_id}")
                    return True
            return False

    def supersede(
        self,
        project_id: str,
        follow_up_id: str,
        new_follow_up_id: str,
    ) -> bool:
        """Mark a follow-up as superseded by another follow-up."""
        with self._lock:
            registry = self._read_registry_unlocked(project_id)
            for entry in registry["follow_ups"]:
                if entry["follow_up_id"] == follow_up_id:
                    entry["status"] = "SUPERSEDED"
                    entry["superseded_by"] = new_follow_up_id
                    self._write_registry_unlocked(registry, project_id)
                    logger.info(f"Follow-up superseded: {follow_up_id} → {new_follow_up_id}")
                    return True
            return False

    # ── Query ────────────────────────────────────────────────────────────────

    def get_open(
        self, project_id: str
    ) -> list[dict[str, Any]]:
        """Return all OPEN follow-ups for a project."""
        return [
            e for e in self._read_registry(project_id)["follow_ups"]
            if e["status"] == "OPEN"
        ]

    def get_resolved(
        self, project_id: str
    ) -> list[dict[str, Any]]:
        """Return all RESOLVED follow-ups (pending closure)."""
        return [
            e for e in self._read_registry(project_id)["follow_ups"]
            if e["status"] == "RESOLVED"
        ]

    def get_all(
        self, project_id: str
    ) -> list[dict[str, Any]]:
        """Return all follow-ups for a project."""
        return self._read_registry(project_id)["follow_ups"]

    def get_for_run(
        self, project_id: str, run_id: str
    ) -> list[dict[str, Any]]:
        """Return all follow-ups created during a specific run."""
        return [
            e for e in self._read_registry(project_id)["follow_ups"]
            if e.get("run_id") == run_id
        ]

    def get_summary(
        self, project_id: str
    ) -> dict[str, Any]:
        """Return a summary count of follow-ups by status."""
        registry = self._read_registry(project_id)
        follow_ups = registry.get("follow_ups", [])
        return {
            "total": len(follow_ups),
            "open": sum(1 for e in follow_ups if e["status"] == "OPEN"),
            "resolved": sum(1 for e in follow_ups if e["status"] == "RESOLVED"),
            "closed": sum(1 for e in follow_ups if e["status"] == "CLOSED"),
            "superseded": sum(1 for e in follow_ups if e["status"] == "SUPERSEDED"),
        }

    # ── Internal ─────────────────────────────────────────────────────────────

    def _next_id(self, registry: dict[str, Any]) -> str:
        follow_ups = registry.get("follow_ups", [])
        if not follow_ups:
            return "F-001"
        max_num = 0
        for e in follow_ups:
            fid = e.get("follow_up_id", "")
            if fid.startswith("F-"):
                try:
                    num = int(fid.split("-")[1])
                    if num > max_num:
                        max_num = num
                except (ValueError, IndexError):
                    pass
        return f"F-{max_num + 1:03d}"

    def _read_registry(self, project_id: str) -> dict[str, Any]:
        with self._lock:
            return self._read_registry_unlocked(project_id)

    def _read_registry_unlocked(self, project_id: str) -> dict[str, Any]:
        path = self._registry_path
        if not path.exists():
            return {
                "schema_name": self.SCHEMA_NAME,
                "schema_version": self.SCHEMA_VERSION,
                "project_id": project_id,
                "follow_ups": [],
            }
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {
                "schema_name": self.SCHEMA_NAME,
                "schema_version": self.SCHEMA_VERSION,
                "project_id": project_id,
                "follow_ups": [],
            }

    def _write_registry_unlocked(self, registry: dict[str, Any], project_id: str) -> None:
        path = self._registry_path
        fd, temp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp", prefix=".followup_")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(registry, f, indent=2, ensure_ascii=False)
            if os.path.getsize(temp) == 0:
                os.unlink(temp)
                raise OSError(f"Partial write for {path}")
            os.rename(temp, path)
        except Exception:
            try:
                os.unlink(temp)
            except OSError:
                pass
            raise


# ── Backflow Registry ─────────────────────────────────────────────────────────


class BackflowRegistry:
    """CER backflow registry.

    Backflows are created when new evidence arrives that requires a new round:
    - New equivalence data received
    - Updated SOTA evidence
    - New safety signal
    - Manufacturer data update

    Stored in: governance/backflow_registry.json

    Backflow entry:
    {
      "backflow_id": "BF-001",
      "trigger_type": "NEW_EQUIVALENCE_EVIDENCE",
      "project_id": "CER-PJT-0001",
      "source_round": "round_001",
      "new_round": "round_002",
      "evidence_description": "AMICA GEN AGN detailed technical specifications...",
      "created_at": "2026-04-20T10:00:00+00:00",
      "backflow_pack_ref": "B-BF-001",
      "run_id": "cer-real-pjt0001-ca0b3709"
    }
    """

    BACKFLOW_REGISTRY_FILE = "governance/backflow_registry.json"
    SCHEMA_NAME = "cer_backflow_registry"
    SCHEMA_VERSION = "v1"

    def __init__(self, artifact_root: Path):
        self.artifact_root = Path(artifact_root)
        self._lock = threading.Lock()
        self._ensure_governance_dir()

    def _ensure_governance_dir(self) -> None:
        governance_dir = self.artifact_root / "governance"
        governance_dir.mkdir(parents=True, exist_ok=True)

    @property
    def _registry_path(self) -> Path:
        return self.artifact_root / self.BACKFLOW_REGISTRY_FILE

    def create(
        self,
        trigger_type: str,
        project_id: str,
        source_round: str,
        new_round: str,
        evidence_description: str,
        backflow_pack_ref: str,
        run_id: str = "unknown",
    ) -> str:
        """Create a new backflow record. Returns BF-XXX ID."""
        with self._lock:
            registry = self._read_registry_unlocked(project_id)
            backflow_id = self._next_id(registry)
            now = datetime.now(timezone.utc).isoformat()

            entry: dict[str, Any] = {
                "backflow_id": backflow_id,
                "trigger_type": trigger_type,
                "project_id": project_id,
                "source_round": source_round,
                "new_round": new_round,
                "evidence_description": evidence_description,
                "created_at": now,
                "backflow_pack_ref": backflow_pack_ref,
                "run_id": run_id,
            }

            registry["backflows"].append(entry)
            self._write_registry_unlocked(registry, project_id)

        logger.info(
            f"Backflow created: {backflow_id} trigger={trigger_type} "
            f"project={project_id} {source_round} → {new_round}"
        )
        return backflow_id

    def get_all(self, project_id: str) -> list[dict[str, Any]]:
        """Return all backflow records for a project."""
        return self._read_registry(project_id).get("backflows", [])

    def get_for_round(
        self, project_id: str, round_id: str
    ) -> list[dict[str, Any]]:
        """Return all backflows that created a specific round."""
        return [
            b for b in self.get_all(project_id)
            if b.get("new_round") == round_id
        ]

    # ── Internal ─────────────────────────────────────────────────────────────

    def _next_id(self, registry: dict[str, Any]) -> str:
        backflows = registry.get("backflows", [])
        if not backflows:
            return "BF-001"
        max_num = 0
        for b in backflows:
            bid = b.get("backflow_id", "")
            if bid.startswith("BF-"):
                try:
                    num = int(bid.split("-")[1])
                    if num > max_num:
                        max_num = num
                except (ValueError, IndexError):
                    pass
        return f"BF-{max_num + 1:03d}"

    def _read_registry(self, project_id: str) -> dict[str, Any]:
        with self._lock:
            return self._read_registry_unlocked(project_id)

    def _read_registry_unlocked(self, project_id: str) -> dict[str, Any]:
        path = self._registry_path
        if not path.exists():
            return {
                "schema_name": self.SCHEMA_NAME,
                "schema_version": self.SCHEMA_VERSION,
                "project_id": project_id,
                "backflows": [],
            }
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {
                "schema_name": self.SCHEMA_NAME,
                "schema_version": self.SCHEMA_VERSION,
                "project_id": project_id,
                "backflows": [],
            }

    def _write_registry_unlocked(self, registry: dict[str, Any], project_id: str) -> None:
        path = self._registry_path
        fd, temp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp", prefix=".backflow_")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(registry, f, indent=2, ensure_ascii=False)
            if os.path.getsize(temp) == 0:
                os.unlink(temp)
                raise OSError(f"Partial write for {path}")
            os.rename(temp, path)
        except Exception:
            try:
                os.unlink(temp)
            except OSError:
                pass
            raise
