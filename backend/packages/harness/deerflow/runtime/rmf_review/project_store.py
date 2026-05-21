"""RMF Project persistence layer.

Provides RMFProjectStore — a filesystem-backed JSON store for the RMF
project layer that sits above thread_id/run_id.

Directory layout (under {base_dir}/):
    rmf_projects.json     # main project index
"""

from __future__ import annotations

import json
import shutil
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from deerflow.config.paths import get_paths

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ProjectStatus(str, Enum):
    DRAFT = "draft"
    READY_TO_RUN = "ready_to_run"
    RUNNING = "running"
    PENDING_HUMAN_DECISION = "pending_human_decision"
    REWORK_REQUIRED = "rework_required"
    CONDITIONAL_PASS = "conditional_pass"
    PASSED = "passed"
    CLOSED = "closed"


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class ReviewCycle:
    cycle_id: str
    cycle_number: int  # 0 = initial, 1+ = rework rounds
    thread_id: str
    run_id: str | None
    mode: str
    started_at: str
    completed_at: str | None = None
    machine_recommendation: str | None = None
    human_decision: str | None = None
    final_gate: str | None = None
    status: str = "running"  # running | completed | rework_pending

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ReviewCycle:
        return cls(**d)


@dataclass
class HumanDecisionAudit:
    decision_id: str
    reviewer: str
    decision: str  # pass | conditional_pass | rework_required
    decision_date: str
    rationale: str
    linked_review_items: list[str] = field(default_factory=list)
    linked_capa_ids: list[str] = field(default_factory=list)
    source_thread_id: str = ""
    source_run_id: str = ""
    source_cycle_id: str = ""
    project_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> HumanDecisionAudit:
        return cls(**d)


@dataclass
class RMFProject:
    project_id: str
    project_name: str
    product_name: str
    project_profile_path: str
    input_root: str
    current_status: ProjectStatus = ProjectStatus.DRAFT
    created_at: str = ""
    updated_at: str = ""
    # Runtime linkage
    latest_thread_id: str | None = None
    latest_run_id: str | None = None
    # State snapshot
    latest_gate_status: str | None = None
    latest_human_decision: str | None = None
    latest_machine_recommendation: str | None = None
    # Counters
    total_runs: int = 0
    total_rework_rounds: int = 0
    # Audit trail
    review_cycles: list[ReviewCycle] = field(default_factory=list)
    human_decision_history: list[HumanDecisionAudit] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = _now()
        if not self.updated_at:
            self.updated_at = _now()
        if isinstance(self.current_status, str):
            self.current_status = ProjectStatus(self.current_status)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["current_status"] = self.current_status.value
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> RMFProject:
        d = dict(d)
        # Rehydrate nested dataclass lists
        if "review_cycles" in d:
            d["review_cycles"] = [ReviewCycle.from_dict(c) if isinstance(c, dict) else c for c in d["review_cycles"]]
        if "human_decision_history" in d:
            d["human_decision_history"] = [HumanDecisionAudit.from_dict(h) if isinstance(h, dict) else h for h in d["human_decision_history"]]
        return cls(**d)

    def next_cycle_number(self) -> int:
        if not self.review_cycles:
            return 0
        return max(c.cycle_number for c in self.review_cycles) + 1

    def latest_cycle(self) -> ReviewCycle | None:
        if not self.review_cycles:
            return None
        return max(self.review_cycles, key=lambda c: c.cycle_number)

    def advance_status(self, new_status: ProjectStatus) -> None:
        self.current_status = new_status
        self.updated_at = _now()


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------

_PROJECTS_FILE_VERSION = 1


class RMFProjectStore:
    """Filesystem-backed JSON store for RMF projects.

    File: {base_dir}/rmf_projects.json
    """

    def __init__(self, base_dir: Path | None = None) -> None:
        self._paths = get_paths() if base_dir is None else _PathsWrapper(base_dir)
        self._file_path = self._paths.base_dir / "rmf_projects.json"
        self._lock_path = self._file_path.with_suffix(".json.lock")

    # ---- CRUD ----

    def create_project(
        self,
        project_name: str,
        product_name: str,
        project_profile_path: str,
        input_root: str,
    ) -> RMFProject:
        """Create a new RMF project."""
        project = RMFProject(
            project_id=f"rmf-proj-{uuid.uuid4().hex[:12]}",
            project_name=project_name,
            product_name=product_name,
            project_profile_path=project_profile_path,
            input_root=input_root,
            current_status=ProjectStatus.DRAFT,
        )
        self._save(project)
        return project

    def get_project(self, project_id: str) -> RMFProject | None:
        """Get a project by ID."""
        data = self._read()
        d = data.get("projects", {}).get(project_id)
        if d is None:
            return None
        return RMFProject.from_dict(d)

    def list_projects(
        self,
        status: ProjectStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[RMFProject]:
        """List projects, optionally filtered by status."""
        data = self._read()
        projects: list[RMFProject] = []
        for d in data.get("projects", {}).values():
            p = RMFProject.from_dict(d)
            if status is None or p.current_status == status:
                projects.append(p)
        projects.sort(key=lambda p: p.updated_at, reverse=True)
        return projects[offset : offset + limit]

    def update_project(self, project: RMFProject) -> None:
        """Update an existing project (full replace)."""
        project.updated_at = _now()
        self._save(project)

    def delete_project(self, project_id: str) -> bool:
        """Delete a project. Returns True if it existed."""
        data = self._read()
        if project_id not in data.get("projects", {}):
            return False
        del data["projects"][project_id]
        self._write(data)
        return True

    # ---- Cycle management ----

    def start_cycle(
        self,
        project_id: str,
        thread_id: str,
        mode: str = "smoke-run",
    ) -> ReviewCycle | None:
        """Start a new review cycle for a project. Returns the new cycle."""
        project = self.get_project(project_id)
        if project is None:
            return None
        cycle_number = project.next_cycle_number()
        cycle = ReviewCycle(
            cycle_id=f"cycle-{cycle_number}",
            cycle_number=cycle_number,
            thread_id=thread_id,
            run_id=None,
            mode=mode,
            started_at=_now(),
            status="running",
        )
        project.review_cycles.append(cycle)
        project.latest_thread_id = thread_id
        project.total_runs += 1
        project.advance_status(ProjectStatus.RUNNING)
        self.update_project(project)
        return cycle

    def complete_cycle(
        self,
        project_id: str,
        cycle_id: str,
        run_id: str,
        machine_recommendation: str | None = None,
        human_decision: str | None = None,
        final_gate: str | None = None,
    ) -> bool:
        """Mark a cycle as completed and update project state snapshot."""
        project = self.get_project(project_id)
        if project is None:
            return False
        cycle = self._find_cycle(project, cycle_id)
        if cycle is None:
            return False
        cycle.run_id = run_id
        cycle.machine_recommendation = machine_recommendation
        cycle.human_decision = human_decision
        cycle.final_gate = final_gate
        cycle.completed_at = _now()
        cycle.status = "completed"
        project.latest_run_id = run_id
        project.latest_machine_recommendation = machine_recommendation
        project.latest_gate_status = final_gate
        # Advance project status
        if human_decision == "rework_required":
            project.advance_status(ProjectStatus.REWORK_REQUIRED)
            cycle.status = "rework_pending"
            project.total_rework_rounds += 1
        elif human_decision == "conditional_pass":
            project.advance_status(ProjectStatus.CONDITIONAL_PASS)
        elif human_decision == "pass":
            project.advance_status(ProjectStatus.PASSED)
        elif machine_recommendation and not human_decision:
            project.advance_status(ProjectStatus.PENDING_HUMAN_DECISION)
        self.update_project(project)
        return True

    def add_human_decision(
        self,
        project_id: str,
        cycle_id: str,
        audit: HumanDecisionAudit,
    ) -> bool:
        """Record a human decision audit entry."""
        project = self.get_project(project_id)
        if project is None:
            return False
        cycle = self._find_cycle(project, cycle_id)
        if cycle is None:
            return False
        audit.project_id = project_id
        audit.source_cycle_id = cycle_id
        project.human_decision_history.append(audit)
        project.latest_human_decision = audit.decision
        # Also update the cycle's human_decision
        cycle.human_decision = audit.decision
        # Advance status based on decision
        if audit.decision == "rework_required":
            project.advance_status(ProjectStatus.REWORK_REQUIRED)
            cycle.status = "rework_pending"
        elif audit.decision == "conditional_pass":
            project.advance_status(ProjectStatus.CONDITIONAL_PASS)
        elif audit.decision == "pass":
            project.advance_status(ProjectStatus.PASSED)
        self.update_project(project)
        return True

    def close_project(self, project_id: str) -> bool:
        """Mark a project as closed."""
        project = self.get_project(project_id)
        if project is None:
            return False
        project.advance_status(ProjectStatus.CLOSED)
        self.update_project(project)
        return True

    def get_audit_trail(self, project_id: str) -> list[HumanDecisionAudit]:
        """Get the full human decision audit trail for a project."""
        project = self.get_project(project_id)
        if project is None:
            return []
        return sorted(project.human_decision_history, key=lambda a: a.decision_date)

    def get_cycle_history(self, project_id: str) -> list[ReviewCycle]:
        """Get cycles sorted by cycle_number."""
        project = self.get_project(project_id)
        if project is None:
            return []
        return sorted(project.review_cycles, key=lambda c: c.cycle_number)

    # ---- Internal helpers ----

    def _find_cycle(self, project: RMFProject, cycle_id: str) -> ReviewCycle | None:
        for c in project.review_cycles:
            if c.cycle_id == cycle_id:
                return c
        return None

    def _read(self) -> dict[str, Any]:
        if not self._file_path.exists():
            return {"version": _PROJECTS_FILE_VERSION, "projects": {}}
        try:
            return json.loads(self._file_path.read_text())
        except (json.JSONDecodeError, OSError):
            return {"version": _PROJECTS_FILE_VERSION, "projects": {}}

    def _write(self, data: dict[str, Any]) -> None:
        self._file_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._file_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        shutil.move(str(tmp), str(self._file_path))

    def _save(self, project: RMFProject) -> None:
        data = self._read()
        data["projects"][project.project_id] = project.to_dict()
        self._write(data)


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class _PathsWrapper:
    """Minimal Paths-compatible wrapper for a custom base_dir."""

    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir.resolve()
