"""RMF Project API Router.

Provides project-layer REST endpoints for the RMF review system:
  - POST   /api/rmf/projects                    -> create project
  - GET    /api/rmf/projects                    -> list projects
  - GET    /api/rmf/projects/{project_id}        -> project detail
  - PATCH  /api/rmf/projects/{project_id}        -> update project status
  - DELETE /api/rmf/projects/{project_id}       -> delete project
  - POST   /api/rmf/projects/{project_id}/runs  -> start a new run in project
  - GET    /api/rmf/projects/{project_id}/history -> cycles + rework history
  - POST   /api/rmf/projects/{project_id}/human-decision -> submit decision
  - GET    /api/rmf/projects/{project_id}/audit-trail -> human decision audit trail
"""

from __future__ import annotations

import json
import logging
import subprocess
import sys
import uuid
from pathlib import Path

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from deerflow.runtime.rmf_review import (
    RMFProjectStore,
    RMFProject,
    ReviewCycle,
    HumanDecisionAudit,
    ProjectStatus,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/rmf/projects", tags=["rmf-projects"])

_REPO_ROOT = Path(__file__).resolve().parents[4]


# ---------------------------------------------------------------------------
# Store accessor
# ---------------------------------------------------------------------------

def _store() -> RMFProjectStore:
    return RMFProjectStore()


# ---------------------------------------------------------------------------
# Role permission helpers
# ---------------------------------------------------------------------------

# Role definitions
ROLE_ADMIN = "admin"
ROLE_APPROVER = "approver"
ROLE_REVIEWER = "reviewer"
ROLE_OPERATOR = "operator"

# Permission matrix: action -> allowed roles
_PERMISSIONS: dict[str, set[str]] = {
    "create_project": {ROLE_ADMIN, ROLE_OPERATOR},
    "delete_project": {ROLE_ADMIN},
    "close_project": {ROLE_ADMIN, ROLE_APPROVER},
    "submit_decision": {ROLE_ADMIN, ROLE_APPROVER, ROLE_REVIEWER, ROLE_OPERATOR},
    "start_run": {ROLE_ADMIN, ROLE_OPERATOR},
    "view_all_projects": {ROLE_ADMIN},
    "view_project": {ROLE_ADMIN, ROLE_APPROVER, ROLE_REVIEWER, ROLE_OPERATOR},
    "update_project": {ROLE_ADMIN, ROLE_APPROVER},
}


def _check_role(role: str | None, action: str) -> str:
    """Validate role has permission for action. Returns role if valid. Raises HTTPException otherwise."""
    if role is None:
        raise HTTPException(
            status_code=401,
            detail=f"Missing X-RMF-Role header for action: {action}",
        )
    allowed = _PERMISSIONS.get(action, set())
    if role not in allowed:
        raise HTTPException(
            status_code=403,
            detail=f"Role '{role}' is not authorized for '{action}'. Allowed: {', '.join(sorted(allowed)) or 'none'}",
        )
    return role


def _role_info(role: str | None) -> dict[str, str]:
    """Return role info for audit trail."""
    return {"role": role or "unknown", "user": role or "anonymous"}


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class CreateProjectRequest(BaseModel):
    project_name: str = Field(..., description="Human-readable project name")
    product_name: str = Field(..., description="Device/product name")
    project_profile: str = Field(..., description="Absolute path to project_profile.yaml")
    input_root: str = Field(default="", description="Input root override")


class UpdateProjectRequest(BaseModel):
    status: ProjectStatus | None = Field(None, description="New project status")
    close: bool = Field(False, description="If true, close the project")


class ProjectResponse(BaseModel):
    project_id: str
    project_name: str
    product_name: str
    project_profile_path: str
    input_root: str
    current_status: str
    created_at: str
    updated_at: str
    latest_thread_id: str | None
    latest_run_id: str | None
    latest_gate_status: str | None
    latest_human_decision: str | None
    latest_machine_recommendation: str | None
    total_runs: int
    total_rework_rounds: int

    @classmethod
    def from_project(cls, p: RMFProject) -> ProjectResponse:
        return cls(
            project_id=p.project_id,
            project_name=p.project_name,
            product_name=p.product_name,
            project_profile_path=p.project_profile_path,
            input_root=p.input_root,
            current_status=p.current_status.value,
            created_at=p.created_at,
            updated_at=p.updated_at,
            latest_thread_id=p.latest_thread_id,
            latest_run_id=p.latest_run_id,
            latest_gate_status=p.latest_gate_status,
            latest_human_decision=p.latest_human_decision,
            latest_machine_recommendation=p.latest_machine_recommendation,
            total_runs=p.total_runs,
            total_rework_rounds=p.total_rework_rounds,
        )


class ProjectDetailResponse(ProjectResponse):
    review_cycles: list[dict]
    human_decision_history: list[dict]
    audit_trail: list[dict] = Field(default_factory=list)

    @classmethod
    def from_project(cls, p: RMFProject) -> ProjectDetailResponse:
        return cls(
            **cls._project_base(p),
            review_cycles=[c.to_dict() for c in p.review_cycles],
            human_decision_history=[h.to_dict() for h in p.human_decision_history],
            audit_trail=[h.to_dict() for h in sorted(p.human_decision_history, key=lambda a: a.decision_date)],
        )

    @staticmethod
    def _project_base(p: RMFProject) -> dict:
        return {
            "project_id": p.project_id,
            "project_name": p.project_name,
            "product_name": p.product_name,
            "project_profile_path": p.project_profile_path,
            "input_root": p.input_root,
            "current_status": p.current_status.value,
            "created_at": p.created_at,
            "updated_at": p.updated_at,
            "latest_thread_id": p.latest_thread_id,
            "latest_run_id": p.latest_run_id,
            "latest_gate_status": p.latest_gate_status,
            "latest_human_decision": p.latest_human_decision,
            "latest_machine_recommendation": p.latest_machine_recommendation,
            "total_runs": p.total_runs,
            "total_rework_rounds": p.total_rework_rounds,
        }


class CycleResponse(BaseModel):
    cycle_id: str
    cycle_number: int
    thread_id: str
    run_id: str | None
    mode: str
    started_at: str
    completed_at: str | None
    machine_recommendation: str | None
    human_decision: str | None
    final_gate: str | None
    status: str


class StartRunResponse(BaseModel):
    project_id: str
    cycle_id: str
    cycle_number: int
    thread_id: str
    run_id: str
    status: str


class HumanDecisionSubmitRequest(BaseModel):
    decision: str = Field(..., description="pass | conditional_pass | rework_required")
    reviewer: str = Field(..., description="Reviewer name")
    rationale: str = Field(default="")
    linked_review_items: list[str] = Field(default_factory=list)
    linked_capa_ids: list[str] = Field(default_factory=list)
    thread_id: str | None = Field(None, description="Override thread_id (defaults to latest)")


class HumanDecisionSubmitResponse(BaseModel):
    success: bool
    decision_recorded: bool
    project_status: str
    cycle_status: str


class ProjectHistoryResponse(BaseModel):
    project_id: str
    current_status: str
    cycles: list[CycleResponse]
    human_decision_audit: list[dict]


class AuditTrailEntry(BaseModel):
    decision_id: str
    reviewer: str
    decision: str
    decision_date: str
    rationale: str
    linked_review_items: list[str]
    linked_capa_ids: list[str]
    source_thread_id: str
    source_run_id: str
    source_cycle_id: str


class AuditTrailResponse(BaseModel):
    project_id: str
    entries: list[AuditTrailEntry]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_cycle_response(c: ReviewCycle) -> CycleResponse:
    return CycleResponse(
        cycle_id=c.cycle_id,
        cycle_number=c.cycle_number,
        thread_id=c.thread_id,
        run_id=c.run_id,
        mode=c.mode,
        started_at=c.started_at,
        completed_at=c.completed_at,
        machine_recommendation=c.machine_recommendation,
        human_decision=c.human_decision,
        final_gate=c.final_gate,
        status=c.status,
    )


def _run_rmf_runner(
    project_profile: str,
    thread_id: str,
    input_root: str | None,
    mode: str = "smoke-run",
) -> dict:
    """Run the RMF review runner script and return parsed JSON output."""
    cmd = [
        sys.executable,
        str(_REPO_ROOT / "scripts" / "rmf_review_runner.py"),
        "--project-profile",
        project_profile,
        "--thread-id",
        thread_id,
        "--mode",
        mode,
    ]
    if input_root:
        cmd.extend(["--input-root", input_root])
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(_REPO_ROOT), timeout=1800)
    if result.returncode != 0:
        raise RuntimeError(f"RMF runner failed: {result.stderr}")
    return json.loads(result.stdout)


def _run_closure_only(
    project_profile: str,
    thread_id: str,
    run_id: str,
    artifact_root: str,
    input_root: str | None,
) -> dict:
    """Run closure-only mode for a given run."""
    cmd = [
        sys.executable,
        str(_REPO_ROOT / "scripts" / "rmf_review_runner.py"),
        "--project-profile",
        project_profile,
        "--thread-id",
        thread_id,
        "--mode",
        "closure-only",
        "--run-id-override",
        run_id,
        "--artifact-root-override",
        artifact_root,
    ]
    if input_root:
        cmd.extend(["--input-root", input_root])
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(_REPO_ROOT), timeout=600)
    return json.loads(result.stdout) if result.returncode == 0 else {}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("", response_model=ProjectResponse)
async def create_project(
    body: CreateProjectRequest,
    x_rmf_role: str | None = Header(None, alias="X-RMF-Role"),
) -> ProjectResponse:
    """Create a new RMF review project. Requires admin or operator role."""
    _check_role(x_rmf_role, "create_project")
    store = _store()
    project = store.create_project(
        project_name=body.project_name,
        product_name=body.product_name,
        project_profile_path=body.project_profile,
        input_root=body.input_root,
    )
    project.advance_status(ProjectStatus.READY_TO_RUN)
    store.update_project(project)
    return ProjectResponse.from_project(project)


@router.get("", response_model=list[ProjectResponse])
async def list_projects(
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[ProjectResponse]:
    """List all RMF projects, optionally filtered by status."""
    store = _store()
    status_enum = ProjectStatus(status) if status else None
    projects = store.list_projects(status=status_enum, limit=limit, offset=offset)
    return [ProjectResponse.from_project(p) for p in projects]


@router.get("/{project_id}", response_model=ProjectDetailResponse)
async def get_project(project_id: str) -> ProjectDetailResponse:
    """Get project detail including cycles and audit history."""
    store = _store()
    project = store.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    return ProjectDetailResponse.from_project(project)


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: str,
    body: UpdateProjectRequest,
    x_rmf_role: str | None = Header(None, alias="X-RMF-Role"),
) -> ProjectResponse:
    """Update project status or close it. Close requires admin or approver role."""
    if body.close:
        _check_role(x_rmf_role, "close_project")
    else:
        _check_role(x_rmf_role, "update_project")
    store = _store()
    project = store.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    if body.close:
        store.close_project(project_id)
    elif body.status is not None:
        project.advance_status(body.status)
        store.update_project(project)
    project = store.get_project(project_id)
    return ProjectResponse.from_project(project)


@router.delete("/{project_id}")
async def delete_project(
    project_id: str,
    x_rmf_role: str | None = Header(None, alias="X-RMF-Role"),
) -> dict:
    """Delete a project. Requires admin role."""
    _check_role(x_rmf_role, "delete_project")
    store = _store()
    existed = store.delete_project(project_id)
    if not existed:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    return {"deleted": True, "project_id": project_id}


@router.post("/{project_id}/runs", response_model=StartRunResponse)
async def start_run_in_project(
    project_id: str,
    x_rmf_role: str | None = Header(None, alias="X-RMF-Role"),
) -> StartRunResponse:
    """Start a new smoke-run in the context of a project. Requires admin or operator role."""
    _check_role(x_rmf_role, "start_run")
    store = _store()
    project = store.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    # Determine thread_id and mode
    thread_id = f"rmf-proj-{uuid.uuid4().hex[:12]}"
    mode = "smoke-run"

    # Start cycle in store
    cycle = store.start_cycle(project_id, thread_id, mode)
    if cycle is None:
        raise HTTPException(status_code=500, detail="Failed to start cycle")

    # Run the actual RMF runner
    try:
        result = _run_rmf_runner(
            project_profile=project.project_profile_path,
            thread_id=thread_id,
            input_root=project.input_root or None,
            mode=mode,
        )
    except Exception as e:
        logger.error("RMF runner failed for project %s: %s", project_id, e)
        raise HTTPException(status_code=500, detail=f"RMF runner failed: {e}")

    # Complete the cycle
    run_id = result.get("run_id", thread_id)
    machine_rec = None
    human_dec = None
    final_gate = None

    # Try to read machine recommendation from final_report
    try:
        outputs_base = Path(result.get("artifact_root_actual", ""))
        if outputs_base.exists():
            fr_path = outputs_base / "06_final" / "final_report.json"
            if fr_path.exists():
                fr = json.loads(fr_path.read_text())
                machine_rec = fr.get("recommended_gate") or fr.get("gate_recommendation", {}).get("recommended_gate")
            hg_path = outputs_base / "05_human_boundary" / "human_gate_decision.json"
            if hg_path.exists():
                hg = json.loads(hg_path.read_text())
                human_dec = hg.get("decision")
            gc_path = outputs_base / "07_gate_closure" / "gate_closure_report.json"
            if gc_path.exists():
                gc = json.loads(gc_path.read_text())
                final_gate = gc.get("final_decision")
    except Exception:
        pass

    store.complete_cycle(
        project_id=project_id,
        cycle_id=cycle.cycle_id,
        run_id=run_id,
        machine_recommendation=machine_rec,
        human_decision=human_dec,
        final_gate=final_gate,
    )

    project = store.get_project(project_id)
    assert project is not None
    latest_cycle = project.latest_cycle()

    return StartRunResponse(
        project_id=project_id,
        cycle_id=cycle.cycle_id,
        cycle_number=cycle.cycle_number,
        thread_id=thread_id,
        run_id=run_id,
        status=project.current_status.value,
    )


@router.get("/{project_id}/history", response_model=ProjectHistoryResponse)
async def get_project_history(project_id: str) -> ProjectHistoryResponse:
    """Get cycle history and human decision audit for a project."""
    store = _store()
    project = store.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    cycles = store.get_cycle_history(project_id)
    audit = store.get_audit_trail(project_id)
    return ProjectHistoryResponse(
        project_id=project_id,
        current_status=project.current_status.value,
        cycles=[_build_cycle_response(c) for c in cycles],
        human_decision_audit=[a.to_dict() for a in audit],
    )


@router.post("/{project_id}/human-decision", response_model=HumanDecisionSubmitResponse)
async def submit_human_decision(
    project_id: str,
    body: HumanDecisionSubmitRequest,
) -> HumanDecisionSubmitResponse:
    """Submit a human gate decision for the project's latest (or specified) cycle."""
    store = _store()
    project = store.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    # Find the target cycle
    cycle = project.latest_cycle()
    if cycle is None:
        raise HTTPException(status_code=400, detail="No cycles found in project")

    # Use specified thread_id or latest
    thread_id = body.thread_id or project.latest_thread_id or cycle.thread_id

    # Write human decision to the run artifact
    try:
        from deerflow.config.paths import get_paths
        paths = get_paths()
        outputs_dir = paths.sandbox_outputs_dir(thread_id)
        artifact_root = outputs_dir / "rmf_review_v1_1"
        # Find the latest run dir
        run_dirs = sorted((d for d in artifact_root.iterdir() if d.is_dir()), key=lambda d: d.stat().st_mtime, reverse=True)
        if not run_dirs:
            raise HTTPException(status_code=400, detail=f"No runs found for thread {thread_id}")
        run_dir = run_dirs[0]
        decision_path = run_dir / "artifacts" / "05_human_boundary" / "human_gate_decision.json"
        decision_path.parent.mkdir(parents=True, exist_ok=True)
        from datetime import datetime, timezone
        decision_record = {
            "decision": body.decision,
            "reviewer": body.reviewer,
            "decision_date": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "rationale": body.rationale,
            "linked_review_items": body.linked_review_items,
            "linked_capa_ids": body.linked_capa_ids,
            "simulated": False,
        }
        decision_path.write_text(json.dumps(decision_record, indent=2, ensure_ascii=False))
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to write human decision: %s", e)
        raise HTTPException(status_code=500, detail=f"Failed to write decision: {e}")

    # Run closure-only
    try:
        run_id = cycle.run_id or thread_id
        _run_closure_only(
            project_profile=project.project_profile_path,
            thread_id=thread_id,
            run_id=run_id,
            artifact_root=str(run_dir / "artifacts"),
            input_root=project.input_root or None,
        )
    except Exception as e:
        logger.warning("Closure-only run failed (non-fatal): %s", e)

    # Read final gate from closure report
    final_gate = None
    try:
        gc_path = run_dir / "artifacts" / "07_gate_closure" / "gate_closure_report.json"
        if gc_path.exists():
            gc = json.loads(gc_path.read_text())
            final_gate = gc.get("final_decision")
    except Exception:
        pass

    # Record audit entry
    audit = HumanDecisionAudit(
        decision_id=f"hda-{uuid.uuid4().hex[:8]}",
        reviewer=body.reviewer,
        decision=body.decision,
        decision_date=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        rationale=body.rationale,
        linked_review_items=body.linked_review_items,
        linked_capa_ids=body.linked_capa_ids,
        source_thread_id=thread_id,
        source_run_id=cycle.run_id or "",
        source_cycle_id=cycle.cycle_id,
        project_id=project_id,
    )
    store.add_human_decision(project_id, cycle.cycle_id, audit)

    # Update cycle with final gate
    store.complete_cycle(
        project_id=project_id,
        cycle_id=cycle.cycle_id,
        run_id=cycle.run_id or thread_id,
        machine_recommendation=project.latest_machine_recommendation,
        human_decision=body.decision,
        final_gate=final_gate,
    )

    project = store.get_project(project_id)
    assert project is not None
    latest_cycle = project.latest_cycle()

    return HumanDecisionSubmitResponse(
        success=True,
        decision_recorded=True,
        project_status=project.current_status.value,
        cycle_status=latest_cycle.status if latest_cycle else "unknown",
    )


@router.get("/{project_id}/audit-trail", response_model=AuditTrailResponse)
async def get_audit_trail(project_id: str) -> AuditTrailResponse:
    """Get the full human decision audit trail for a project."""
    store = _store()
    project = store.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    audit = store.get_audit_trail(project_id)
    return AuditTrailResponse(
        project_id=project_id,
        entries=[
            AuditTrailEntry(
                decision_id=a.decision_id,
                reviewer=a.reviewer,
                decision=a.decision,
                decision_date=a.decision_date,
                rationale=a.rationale,
                linked_review_items=a.linked_review_items,
                linked_capa_ids=a.linked_capa_ids,
                source_thread_id=a.source_thread_id,
                source_run_id=a.source_run_id,
                source_cycle_id=a.source_cycle_id,
            )
            for a in audit
        ],
    )
