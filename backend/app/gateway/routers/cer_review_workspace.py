"""CER Review Workspace API — Governance Data Endpoints

Provides governance-aware REST endpoints for the CER Review Workspace:
  - GET /api/cer-review/projects                    -> list all CER projects
  - GET /api/cer-review/{project_id}/runs            -> list runs for a project
  - GET /api/cer-review/{project_id}/run/{run_id}    -> run detail with state/lane/gate summary
  - GET /api/cer-review/{project_id}/ledger          -> decision ledger (read-only)
  - GET /api/cer-review/{project_id}/gate-audit/{gate} -> gate audit trail
  - GET /api/cer-review/{project_id}/state-log      -> state transition log
  - GET /api/cer-review/{project_id}/bundle-lineage  -> bundle lineage
  - GET /api/cer-review/{project_id}/followups       -> follow-up registry
  - GET /api/cer-review/{project_id}/backflows       -> backflow registry
  - GET /api/cer-review/{project_id}/gate-1/bundle  -> Gate 1 bundle inputs
  - GET /api/cer-review/{project_id}/gate-3/bundle  -> Gate 3 RISK_BENEFIT composite
  - GET /api/cer-review/{project_id}/artifacts       -> artifact list
  - GET /api/cer-review/{project_id}/artifacts/{path} -> raw artifact
  - GET /api/cer-review/{project_id}/compare        -> rework comparison data
  - POST /api/cer-review/{project_id}/gate-1/decision -> submit Gate 1 decision
  - POST /api/cer-review/{project_id}/gate-3/decision -> submit BRR terminal decision

Frozen baseline: CER_REVIEWER_WORKSPACE_P0_SPEC.md
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from deerflow.runtime.cer_review.auth import (
    CERAuthContext,
    CERRole,
    is_rbac_enabled,
)
from deerflow.runtime.cer_review.auth.rbac_context import (
    get_cer_auth,
    get_cer_auth_with_gate_role,
)
from deerflow.runtime.cer_review.governance import GateAuditor

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/cer-review", tags=["cer-review"])

# ── Paths ──────────────────────────────────────────────────────────────────────

CER_ARTIFACTS_ROOT = Path("/Users/winstonwei/Documents/Playground/deer-flow/artifacts/cer")


# ── Pydantic Models ───────────────────────────────────────────────────────────


class ProjectSummary(BaseModel):
    project_id: str
    display_name: str
    latest_run_id: str | None = None
    latest_round: str | None = None
    latest_state: str | None = None
    gate_status: str | None = None  # most urgent pending gate
    updated_at: str | None = None


class AllProjectsResponse(BaseModel):
    projects: list[ProjectSummary]


class RunSummary(BaseModel):
    run_id: str
    round_id: str
    current_state: str
    lane_statuses: dict[str, str]  # lane -> COMPLETE/FLAGGED/PENDING
    gate_statuses: dict[str, str]  # gate -> PENDING/COMPLETE/BLOCKING
    model: str | None = None
    execution_mode: str | None = None
    is_stub: bool = False


class RunDetailResponse(BaseModel):
    project_id: str
    run_id: str
    round_id: str
    current_state: str
    lane_statuses: dict[str, str]
    gate_statuses: dict[str, str]
    ledger_summary: dict  # last 3 entries
    ledger_total: int = 0  # total entries in full ledger
    state_log_summary: list  # last 5 transitions
    bundle_lineage_summary: list  # key lineage records
    findings_summary: list  # from findings register
    followups_open: int
    model: str | None = None
    execution_mode: str | None = None
    is_stub: bool = False


class LedgerEntry(BaseModel):
    entry_id: str
    entry_type: str
    run_id: str
    round_id: str
    actor: str
    timestamp: str
    immutable: bool = True
    gate: str | None = None
    from_state: str | None = None
    to_state: str | None = None
    supersedes: str | None = None
    decision_data: dict = Field(default_factory=dict)


class LedgerResponse(BaseModel):
    project_id: str
    entries: list[LedgerEntry]
    total_count: int
    has_more: bool = False


class GateAuditEntry(BaseModel):
    gate: str
    decision: str
    actor: str
    timestamp: str
    contributions_verified: dict | None = None
    conditional: bool | None = None
    outstanding_rework: list | None = None
    file_path: str | None = None


class GateAuditResponse(BaseModel):
    project_id: str
    gate: str
    audits: list[GateAuditEntry]


class StateTransitionEntry(BaseModel):
    entry_id: str
    run_id: str
    round_id: str
    from_state: str
    to_state: str
    timestamp: str
    actor: str
    trigger: str | None = None
    duration_sec: float | None = None


class StateLogResponse(BaseModel):
    project_id: str
    transitions: list[StateTransitionEntry]
    total_count: int


class BundleLineageEntry(BaseModel):
    bundle_id: str
    bundle_type: str
    produced_at: str
    inputs: list[dict]
    output_artifact: str
    output_decision: str | None = None
    contributions_verified: dict | None = None


class BundleLineageResponse(BaseModel):
    project_id: str
    lineages: list[BundleLineageEntry]


class FollowupEntry(BaseModel):
    follow_up_id: str
    type: str
    description: str
    assigned_to: str
    status: str
    created_at: str
    due_date: str | None = None
    closure_criteria: str | None = None
    related_finding: str | None = None


class FollowupResponse(BaseModel):
    project_id: str
    follow_ups: list[FollowupEntry]
    summary: dict  # open/resolved/closed counts


class BackflowEntry(BaseModel):
    backflow_id: str
    trigger_type: str
    source_round: str
    new_round: str
    evidence_description: str
    created_at: str
    backflow_pack_ref: str | None = None


class BackflowResponse(BaseModel):
    project_id: str
    backflows: list[BackflowEntry]


class GateBundleArtifact(BaseModel):
    artifact_name: str
    lane: str | None = None
    agent_id: str | None = None
    path: str
    size_bytes: int
    modified_at: str


class Gate1BundleResponse(BaseModel):
    project_id: str
    run_id: str
    gate: str = "GATE_1"
    scope: str = "EQUIVALENCE_UNIT only"
    artifacts: list[GateBundleArtifact]
    lane_2c_summary: dict | None = None
    route_decision_summary: dict | None = None


class LaneContribution(BaseModel):
    agent_id: str
    agent_name: str
    question: str
    contribution_artifact: str | None = None
    summary: str | None = None
    status: str = "available"  # "available" | "missing"
    missing_reason: str | None = None  # "historical_run" | "not_generated" | None


class Gate3BundleResponse(BaseModel):
    project_id: str
    run_id: str
    gate: str = "GATE_3"
    scope: str = "RISK_BENEFIT composite ONLY"
    brr_only_location: bool = True
    contributions: list[LaneContribution]
    layer3_items: list[dict]  # human judgment required items
    findings_summary: list[dict]
    rework_items: list[dict]
    is_stub: bool = False


class ArtifactListing(BaseModel):
    path: str
    artifact_name: str
    state: str | None = None
    lane: str | None = None
    object_type: str | None = None
    has_flags: bool = False
    size_bytes: int
    modified_at: str


class ArtifactListResponse(BaseModel):
    project_id: str
    run_id: str
    artifacts: list[ArtifactListing]


class ReworkCompareLane(BaseModel):
    lane: str
    display_name: str
    artifacts: list[dict]  # artifact, round_n, round_n_plus_1, status


class ReworkCompareResponse(BaseModel):
    project_id: str
    round_n: str
    round_n_plus_1: str
    lanes: list[ReworkCompareLane]
    gate_decision_comparison: dict


class Gate1DecisionRequest(BaseModel):
    run_id: str
    round_id: str
    decision: str  # APPROVE_EQUIVALENCE_ROUTE | REJECT_EQUIVALENCE_ROUTE | REQUIRE_LITERATURE_ROUTE | CONDITIONAL_EQUIVALENCE
    reviewer: str
    rationale: str = ""


class Gate1DecisionResponse(BaseModel):
    success: bool
    ledger_entry_id: str | None = None
    gate_audit_path: str | None = None
    state_transition_id: str | None = None
    error: str | None = None


class Gate3DecisionRequest(BaseModel):
    run_id: str
    round_id: str
    decision: str  # BRR_ACCEPTABLE | BRR_UNACCEPTABLE | BRR_MISALIGNED
    conditional: bool = False
    outstanding_rework: list[str] = Field(default_factory=list)
    reviewer: str
    reauth_timestamp: str
    rationale: str = ""


class Gate3DecisionResponse(BaseModel):
    success: bool
    ledger_entry_id: str | None = None
    gate_audit_path: str | None = None
    state_transition_id: str | None = None
    error: str | None = None
    stub_blocked: bool = False


# ── /me Endpoint ────────────────────────────────────────────────────────────────


class MeResponse(BaseModel):
    user_id: str
    name: str
    role: str


@router.get("/me", response_model=MeResponse)
async def get_me(request: Request) -> MeResponse:
    """Return the authenticated user's identity and role.

    Requires X-CER-User-ID and X-CER-User-Role headers.
    Returns 401 if RBAC is enabled and headers are missing.
    """
    if is_rbac_enabled():
        # RBAC enabled — require auth headers
        auth = await get_cer_auth(request)
        return MeResponse(
            user_id=auth.user_id,
            name=auth.user_name,
            role=auth.role.value,
        )
    else:
        # RBAC disabled — return a default
        return MeResponse(
            user_id="rbac-disabled",
            name="RBAC Disabled",
            role=CERRole.SENIOR_REVIEWER.value,
        )


# ── Helper Functions ────────────────────────────────────────────────────────────


def _list_cer_projects() -> list[ProjectSummary]:
    """List all CER project directories under CER_ARTIFACTS_ROOT."""
    if not CER_ARTIFACTS_ROOT.exists():
        return []
    projects = []
    for d in CER_ARTIFACTS_ROOT.iterdir():
        if not d.is_dir():
            continue
        if d.name in ("system",):
            continue
        # Check if it's a CER project (has governance dir)
        governance_dir = d / "governance"
        if not governance_dir.exists():
            continue
        project_id = d.name

        # Find latest run
        run_manifests = list(d.glob("*/artifacts/00_manifest/run_manifest.json"))
        latest_run = None
        latest_state = None
        latest_round = None
        latest_updated = None
        for rm in run_manifests:
            try:
                data = json.loads(rm.read_text())
                ts = rm.stat().st_mtime
                if latest_updated is None or ts > latest_updated:
                    latest_updated = ts
                    latest_run = data.get("run_id")
                    latest_state = data.get("current_state")
                    latest_round = data.get("round_id", "round_001")
            except Exception:
                continue

        projects.append(ProjectSummary(
            project_id=project_id,
            display_name=project_id,
            latest_run_id=latest_run,
            latest_round=latest_round,
            latest_state=latest_state,
            gate_status=_derive_gate_status(latest_state) if latest_state else None,
            updated_at=datetime.fromtimestamp(latest_updated, tz=timezone.utc).isoformat() if latest_updated else None,
        ))
    return projects


def _derive_gate_status(state: str | None) -> str | None:
    if not state:
        return None
    # Map CER states to gate statuses
    state_gate_map = {
        "S00": "GATE_0",
        "S01": "GATE_0",
        "S02": None,  # route screen
        "S03": None, "S04": None, "S05": None, "S06": None,  # lanes
        "S07": "GATE_1",
        "S08": "GATE_1",
        "S09": "GATE_2",
        "S10": None,  # BRR composite
        "S11": "GATE_3",
        "S12": "COMPLETE",
        "S17": "GATE_3_REWORK",
    }
    return state_gate_map.get(state)


def _get_run_manifest(project_id: str, run_id: str) -> dict | None:
    """Find run_manifest.json for a run."""
    project_root = CER_ARTIFACTS_ROOT / project_id
    if not project_root.exists():
        return None
    # Search all round directories
    for round_dir in project_root.iterdir():
        if not round_dir.is_dir():
            continue
        manifest_path = round_dir / "artifacts" / "00_manifest" / "run_manifest.json"
        if manifest_path.exists():
            try:
                data = json.loads(manifest_path.read_text())
                if data.get("run_id") == run_id:
                    return data
            except Exception:
                continue
    return None


def _read_json_safe(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


# ── API Endpoints ───────────────────────────────────────────────────────────────


@router.get("/projects", response_model=AllProjectsResponse)
async def list_projects() -> AllProjectsResponse:
    """List all CER projects with latest run summary."""
    projects = _list_cer_projects()
    return AllProjectsResponse(projects=projects)


class FollowupsSummary(BaseModel):
    total_open: int = 0
    total_resolved: int = 0
    total_closed: int = 0
    projects_with_open: list[str] = []


@router.get("/followups-summary", response_model=FollowupsSummary)
async def get_followups_summary() -> FollowupsSummary:
    """Get aggregate open follow-ups across all projects."""
    total_open = 0
    total_resolved = 0
    total_closed = 0
    projects_with_open: list[str] = []

    if not CER_ARTIFACTS_ROOT.exists():
        return FollowupsSummary()

    for project_dir in CER_ARTIFACTS_ROOT.iterdir():
        if not project_dir.is_dir():
            continue
        if project_dir.name in ("system",):
            continue
        project_id = project_dir.name
        followup_path = project_dir / "governance" / "follow_up_registry.json"
        if not followup_path.exists():
            continue
        try:
            data = json.loads(followup_path.read_text())
            follow_ups = data.get("follow_ups", [])
            open_count = sum(1 for f in follow_ups if f.get("status") == "OPEN")
            resolved_count = sum(1 for f in follow_ups if f.get("status") == "RESOLVED")
            closed_count = sum(1 for f in follow_ups if f.get("status") == "CLOSED")
            total_open += open_count
            total_resolved += resolved_count
            total_closed += closed_count
            if open_count > 0:
                projects_with_open.append(project_id)
        except Exception:
            continue

    return FollowupsSummary(
        total_open=total_open,
        total_resolved=total_resolved,
        total_closed=total_closed,
        projects_with_open=projects_with_open,
    )


@router.get("/{project_id}/runs")
async def list_runs(project_id: str) -> dict:
    """List all runs for a project."""
    project_root = CER_ARTIFACTS_ROOT / project_id
    if not project_root.exists():
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    runs = []
    for round_dir in project_root.iterdir():
        if not round_dir.is_dir():
            continue
        manifest_path = round_dir / "artifacts" / "00_manifest" / "run_manifest.json"
        if manifest_path.exists():
            try:
                data = json.loads(manifest_path.read_text())
                runs.append({
                    "run_id": data.get("run_id"),
                    "round_id": round_dir.name,
                    "current_state": data.get("current_state", "unknown"),
                    "artifact_root": str(round_dir / "artifacts"),
                    "model": data.get("model"),
                    "execution_mode": data.get("execution_mode"),
                    "is_stub": "stub" in str(data.get("model", "")).lower() or "test" in str(data.get("model", "")).lower(),
                    "updated_at": datetime.fromtimestamp(manifest_path.stat().st_mtime, tz=timezone.utc).isoformat(),
                })
            except Exception:
                continue
    runs.sort(key=lambda r: r.get("updated_at", ""), reverse=True)
    return {"project_id": project_id, "runs": runs}


@router.get("/{project_id}/run/{run_id}", response_model=RunDetailResponse)
async def get_run_detail(project_id: str, run_id: str) -> RunDetailResponse:
    """Get full run detail with state/lane/gate/ledger summary."""
    project_root = CER_ARTIFACTS_ROOT / project_id
    if not project_root.exists():
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    manifest = None
    for round_dir in project_root.iterdir():
        if not round_dir.is_dir():
            continue
        mp = round_dir / "artifacts" / "00_manifest" / "run_manifest.json"
        if mp.exists():
            try:
                data = json.loads(mp.read_text())
                if data.get("run_id") == run_id:
                    manifest = data
                    break
            except Exception:
                continue

    if not manifest:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    current_state = manifest.get("current_state", "unknown")
    is_stub = "stub" in str(manifest.get("model", "")).lower()

    # Lane statuses
    lane_statuses = {}
    lane_artifacts = [
        ("lane_2a_claim", "03_lanes/claim_consistency_matrix.json"),
        ("lane_2b_evidence", "03_lanes/sota_findings.json"),
        ("lane_2c_equivalence", "03_lanes/difference_impact_assessment.json"),
        ("lane_2d_consistency_pmcf", "03_lanes/consistency_delta_matrix.json"),
    ]
    for lane, artifact in lane_artifacts:
        artifact_path = project_root / manifest.get("round_id", "round_001") / "artifacts" / artifact
        if artifact_path.exists() and artifact_path.stat().st_size > 0:
            lane_statuses[lane] = "COMPLETE"
        else:
            lane_statuses[lane] = "PENDING"

    # Gate statuses
    gate_statuses = {
        "GATE_0": "COMPLETE" if current_state not in ("S00",) else "PENDING",
        "GATE_1": "COMPLETE" if current_state not in ("S07", "S08") else "PENDING",
        "GATE_2": "COMPLETE" if current_state not in ("S09",) else "PENDING",
        "GATE_3": "COMPLETE" if current_state in ("S12",) else "PENDING",
    }

    # Ledger summary (last 3 entries) + total count
    ledger_path = project_root / "governance" / f"{project_id}_decision_ledger.json"
    ledger_entries = []
    ledger_total = 0
    if ledger_path.exists():
        try:
            ledger_data = json.loads(ledger_path.read_text())
            all_entries = ledger_data.get("entries", [])
            ledger_total = len(all_entries)
            ledger_entries = all_entries[-3:]
        except Exception:
            pass

    # State log summary (last 5)
    state_log_path = project_root / "governance" / "state_transition_log.jsonl"
    state_transitions = []
    if state_log_path.exists():
        try:
            with open(state_log_path) as f:
                lines = [l.strip() for l in f if l.strip()]
            for line in lines[-5:]:
                try:
                    state_transitions.append(json.loads(line))
                except Exception:
                    continue
        except Exception:
            pass

    # Findings summary
    findings_path = project_root / "CER_REAL_PROJECT_TRIAL_FINDINGS_REGISTER.json"
    findings_summary = []
    if findings_path.exists():
        try:
            fd = json.loads(findings_path.read_text())
            findings_summary = fd.get("findings", [])[:10]
        except Exception:
            pass

    # Follow-ups open count
    followup_path = project_root / "governance" / "follow_up_registry.json"
    followups_open = 0
    if followup_path.exists():
        try:
            fr = json.loads(followup_path.read_text())
            followups_open = sum(1 for f in fr.get("follow_ups", []) if f.get("status") == "OPEN")
        except Exception:
            pass

    return RunDetailResponse(
        project_id=project_id,
        run_id=run_id,
        round_id=manifest.get("round_id", "round_001"),
        current_state=current_state,
        lane_statuses=lane_statuses,
        gate_statuses=gate_statuses,
        ledger_summary={"entries": ledger_entries, "total": ledger_total},
        ledger_total=ledger_total,
        state_log_summary=state_transitions,
        bundle_lineage_summary=[],
        findings_summary=findings_summary,
        followups_open=followups_open,
        model=manifest.get("model"),
        execution_mode=manifest.get("execution_mode"),
        is_stub=is_stub,
    )


@router.get("/{project_id}/ledger", response_model=LedgerResponse)
async def get_ledger(
    project_id: str,
    limit: int | None = None,
    offset: int | None = None,
) -> LedgerResponse:
    """Get decision ledger with optional pagination.

    Args:
        limit: Maximum entries to return (default: all)
        offset: Number of entries to skip (default: 0)
    """
    project_root = CER_ARTIFACTS_ROOT / project_id
    ledger_path = project_root / "governance" / f"{project_id}_decision_ledger.json"
    if not ledger_path.exists():
        return LedgerResponse(project_id=project_id, entries=[], total_count=0)
    try:
        data = json.loads(ledger_path.read_text())
        all_entries = [LedgerEntry(**e) for e in data.get("entries", [])]
        total = len(all_entries)
        offset_val = offset or 0
        if limit is not None:
            paginated = all_entries[offset_val : offset_val + limit]
            has_more = (offset_val + limit) < total
        else:
            paginated = all_entries[offset_val:]
            has_more = False
        return LedgerResponse(
            project_id=project_id,
            entries=paginated,
            total_count=total,
            has_more=has_more,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read ledger: {e}")


@router.get("/{project_id}/gate-audit/{gate}", response_model=GateAuditResponse)
async def get_gate_audit(project_id: str, gate: str) -> GateAuditResponse:
    """Get gate audit trail for a specific gate."""
    project_root = CER_ARTIFACTS_ROOT / project_id
    audit_dir = project_root / "governance" / "gate_audits" / project_id
    if not audit_dir.exists():
        return GateAuditResponse(project_id=project_id, gate=gate, audits=[])

    gate_suffix = {"GATE_0": "G0", "GATE_1": "G1", "GATE_2": "G2", "GATE_3": "G3"}.get(gate.upper())
    if not gate_suffix:
        raise HTTPException(status_code=400, detail=f"Invalid gate: {gate}")

    audits = []
    for audit_file in sorted(audit_dir.glob(f"B-{gate_suffix}-*.json")):
        try:
            data = json.loads(audit_file.read_text())
            audits.append(GateAuditEntry(
                gate=data.get("gate", gate),
                decision=data.get("decision", ""),
                actor=data.get("actor", ""),
                timestamp=data.get("timestamp", ""),
                contributions_verified=data.get("contributions_verified"),
                conditional=data.get("conditional"),
                outstanding_rework=data.get("outstanding_rework"),
                file_path=str(audit_file),
            ))
        except Exception:
            continue
    return GateAuditResponse(project_id=project_id, gate=gate, audits=audits)


@router.get("/{project_id}/state-log", response_model=StateLogResponse)
async def get_state_log(project_id: str, run_id: str | None = None) -> StateLogResponse:
    """Get state transition log."""
    project_root = CER_ARTIFACTS_ROOT / project_id
    log_path = project_root / "governance" / "state_transition_log.jsonl"
    if not log_path.exists():
        return StateLogResponse(project_id=project_id, transitions=[], total_count=0)

    transitions = []
    with open(log_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                if run_id and entry.get("run_id") != run_id:
                    continue
                transitions.append(StateTransitionEntry(**entry))
            except Exception:
                continue
    return StateLogResponse(project_id=project_id, transitions=transitions, total_count=len(transitions))


@router.get("/{project_id}/followups", response_model=FollowupResponse)
async def get_followups(project_id: str) -> FollowupResponse:
    """Get follow-up registry."""
    project_root = CER_ARTIFACTS_ROOT / project_id
    followup_path = project_root / "governance" / "follow_up_registry.json"
    if not followup_path.exists():
        return FollowupResponse(project_id=project_id, follow_ups=[], summary={"total": 0, "open": 0, "resolved": 0, "closed": 0})

    try:
        data = json.loads(followup_path.read_text())
        follow_ups = [FollowupEntry(**f) for f in data.get("follow_ups", [])]
        total = len(follow_ups)
        open_count = sum(1 for f in follow_ups if f.status == "OPEN")
        resolved_count = sum(1 for f in follow_ups if f.status == "RESOLVED")
        closed_count = sum(1 for f in follow_ups if f.status == "CLOSED")
        return FollowupResponse(
            project_id=project_id,
            follow_ups=follow_ups,
            summary={"total": total, "open": open_count, "resolved": resolved_count, "closed": closed_count},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read follow-ups: {e}")


@router.get("/{project_id}/backflows", response_model=BackflowResponse)
async def get_backflows(project_id: str) -> BackflowResponse:
    """Get backflow registry."""
    project_root = CER_ARTIFACTS_ROOT / project_id
    backflow_path = project_root / "governance" / "backflow_registry.json"
    if not backflow_path.exists():
        return BackflowResponse(project_id=project_id, backflows=[])
    try:
        data = json.loads(backflow_path.read_text())
        backflows = [BackflowEntry(**b) for b in data.get("backflows", [])]
        return BackflowResponse(project_id=project_id, backflows=backflows)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read backflows: {e}")


@router.get("/{project_id}/gate-1/bundle", response_model=Gate1BundleResponse)
async def get_gate1_bundle(project_id: str, run_id: str) -> Gate1BundleResponse:
    """Get Gate 1 bundle inputs (route decision, equivalence assessment, special procedure flags)."""
    project_root = CER_ARTIFACTS_ROOT / project_id

    # Find the round directory for this run
    round_id = "round_001"
    for rd in project_root.iterdir():
        if not rd.is_dir():
            continue
        mp = rd / "artifacts" / "00_manifest" / "run_manifest.json"
        if mp.exists():
            try:
                data = json.loads(mp.read_text())
                if data.get("run_id") == run_id:
                    round_id = rd.name
                    break
            except Exception:
                continue

    artifacts_root = project_root / round_id / "artifacts"
    artifacts = []

    # Route decision
    route_path = artifacts_root / "01_route" / "route_decision_draft.json"
    if route_path.exists():
        artifacts.append(GateBundleArtifact(
            artifact_name="route_decision_draft.json",
            lane=None, agent_id="AG-001",
            path=str(route_path),
            size_bytes=route_path.stat().st_size,
            modified_at=datetime.fromtimestamp(route_path.stat().st_mtime, tz=timezone.utc).isoformat(),
        ))

    # Difference impact assessment (Lane 2C)
    eq_path = artifacts_root / "03_lanes" / "difference_impact_assessment.json"
    eq_summary = None
    if eq_path.exists():
        try:
            eq_data = json.loads(eq_path.read_text())
            eq_summary = {
                "predicate_device": eq_data.get("predicate_device"),
                "assessment_status": eq_data.get("assessment_status"),
                "key_differences": eq_data.get("key_differences", []),
                "residual_uncertainty": eq_data.get("residual_uncertainty"),
                "mandatory_human_review": eq_data.get("mandatory_human_review"),
            }
        except Exception:
            pass
        artifacts.append(GateBundleArtifact(
            artifact_name="difference_impact_assessment.json",
            lane="lane_2c_equivalence", agent_id="AG-005",
            path=str(eq_path),
            size_bytes=eq_path.stat().st_size,
            modified_at=datetime.fromtimestamp(eq_path.stat().st_mtime, tz=timezone.utc).isoformat(),
        ))

    # Special procedure flags
    flags_path = artifacts_root / "01_route" / "special_procedure_flags.json"
    if flags_path.exists():
        artifacts.append(GateBundleArtifact(
            artifact_name="special_procedure_flags.json",
            lane=None, agent_id="AG-001",
            path=str(flags_path),
            size_bytes=flags_path.stat().st_size,
            modified_at=datetime.fromtimestamp(flags_path.stat().st_mtime, tz=timezone.utc).isoformat(),
        ))

    return Gate1BundleResponse(
        project_id=project_id,
        run_id=run_id,
        artifacts=artifacts,
        lane_2c_summary=eq_summary,
        route_decision_summary=None,
    )


@router.get("/{project_id}/gate-3/bundle", response_model=Gate3BundleResponse)
async def get_gate3_bundle(project_id: str, run_id: str) -> Gate3BundleResponse:
    """Get Gate 3 RISK_BENEFIT composite bundle (5-agent contributions).

    BRR_ACCEPTABLE/UNACCEPTABLE/MISALIGNED can ONLY be issued from this endpoint.
    Stub model detection: if is_stub=True, returns stub_blocked=True warning.
    """
    project_root = CER_ARTIFACTS_ROOT / project_id

    # Find the round directory
    round_id = "round_001"
    is_stub = False
    for rd in project_root.iterdir():
        if not rd.is_dir():
            continue
        mp = rd / "artifacts" / "00_manifest" / "run_manifest.json"
        if mp.exists():
            try:
                data = json.loads(mp.read_text())
                if data.get("run_id") == run_id:
                    round_id = rd.name
                    model = str(data.get("model", ""))
                    is_stub = "stub" in model.lower() or "test" in model.lower()
            except Exception:
                continue

    artifacts_root = project_root / round_id / "artifacts"

    contributions = []
    # Agent-to-artifact mapping for G3 BRR contributions.
    # Updated 2026-04-21: previously looked for risk_benefit_contribution_report.json (MISSING).
    # Correct filenames discovered from round_002/03_lanes/ artifact agent_name fields.
    contribution_artifacts = [
        ("AG-003", "cer_claim_scope_agent",      "O5-Q3",         "claim_consistency_matrix.json"),
        ("AG-004", "cer_sota_evidence_agent",      "O5-Q3",         "sota_findings.json"),
        ("AG-005", "cer_equivalence_agent",       "O5-Q3",         "difference_impact_assessment.json"),
        ("AG-006", "cer_consistency_agent",       "O5-Q1/Q4/Q5",   "consistency_delta_matrix.json"),
        ("AG-007", "cer_pmcf_lifecycle_agent",    "O5-Q3",         "pmcf_adequacy_assessment.json"),
    ]

    # Always include all 5 agents in the response — mark missing ones explicitly.
    # The BRR composite is defined as exactly these 5 sources per CER constitution.
    # AG-003 to AG-006 are v1 lane agents; round_001 runs may not have them.
    for agent_id, agent_name, question, artifact_name in contribution_artifacts:
        # Risk-benefit contribution reports live in lane directories
        search_paths = [
            artifacts_root / "03_lanes" / artifact_name,
            artifacts_root / "03_lanes" / f"{artifact_name.replace('.json', '')}_{agent_id}.json",
        ]
        found_path = None
        for sp in search_paths:
            if sp.exists():
                found_path = sp
                break

        # Determine missing_reason:
        # - AG-003 to AG-006 may not exist in round_001 (historical runs)
        # - AG-007 (PMCF) was part of original v0, so missing is always "not_generated"
        missing_reason = None
        if not found_path:
            if round_id == "round_001" and agent_id in ("AG-003", "AG-004", "AG-005", "AG-006"):
                missing_reason = "historical_run"
            else:
                missing_reason = "not_generated"

        contributions.append(LaneContribution(
            agent_id=agent_id,
            agent_name=agent_name,
            question=question,
            contribution_artifact=str(found_path.name) if found_path else None,
            summary=None,
            status="available" if found_path else "missing",
            missing_reason=missing_reason,
        ))

    # Layer 3 items (human judgment required)
    layer3_items = []
    eq_path = artifacts_root / "03_lanes" / "difference_impact_assessment.json"
    if eq_path.exists():
        try:
            eq_data = json.loads(eq_path.read_text())
            if eq_data.get("mandatory_human_review"):
                layer3_items.append({
                    "item": "O5-Q3 Equivalence Assessment",
                    "type": "EQUIVALENCE_UNIT",
                    "status": eq_data.get("assessment_status", "unknown"),
                    "requires_human_review": True,
                })
        except Exception:
            pass

    # Findings summary
    findings_path = project_root / "CER_REAL_PROJECT_TRIAL_FINDINGS_REGISTER.json"
    findings_summary = []
    if findings_path.exists():
        try:
            fd = json.loads(findings_path.read_text())
            findings_summary = fd.get("findings", [])
        except Exception:
            pass

    # Rework items
    rework_items = []
    rework_note_path = project_root / "CER_REAL_PROJECT_TRIAL_REWORK_OR_FOLLOWUP_NOTE.md"
    if rework_note_path.exists():
        content = rework_note_path.read_text()
        # Parse R-XXX items from markdown
        import re
        r_items = re.findall(r'(R-\d+):\s*(.+?)(?=\n|$)', content)
        for item_id, desc in r_items:
            rework_items.append({"item_id": item_id, "description": desc.strip()})

    return Gate3BundleResponse(
        project_id=project_id,
        run_id=run_id,
        contributions=contributions,
        layer3_items=layer3_items,
        findings_summary=findings_summary,
        rework_items=rework_items,
        is_stub=is_stub,
    )


def _derive_lane(rel_path: str) -> str | None:
    """Derive lane from artifact relative path."""
    parts = str(rel_path).split("/")
    if len(parts) >= 1:
        dir_name = parts[0]
        if dir_name == "01_route":
            return "route"
        if dir_name == "03_lanes":
            return "lanes"
        if dir_name == "04_adjudication":
            return "adjudication"
    return None


def _derive_object_type(rel_path: str, artifact_name: str) -> str | None:
    """Derive object_type from artifact path and name."""
    name_lower = artifact_name.lower()
    if "claim" in name_lower or "scope" in name_lower:
        return "CLAIM"
    if "evidence" in name_lower or "sota" in name_lower:
        return "EVIDENCE_BLOCK"
    if "equivalence" in name_lower or "difference" in name_lower:
        return "EQUIVALENCE_UNIT"
    if "risk_benefit" in name_lower or "brr" in name_lower or "contribution" in name_lower:
        return "RISK_BENEFIT"
    if "pmcf" in name_lower or "consistency" in name_lower or "delta" in name_lower:
        return "PMCF_HANDOFF"
    if "route_decision" in name_lower or "gate_decision" in name_lower:
        return "ROUTE_DECISION"
    if "flag" in name_lower or "special_procedure" in name_lower:
        return "SPECIAL_PROCEDURE"
    if "backflow" in name_lower or "follow_up" in name_lower:
        return "FOLLOW_UP"
    return "OTHER"


def _has_flags_content(artifact_path: Path) -> bool:
    """Check if artifact JSON contains flag-related content."""
    try:
        content = json.loads(artifact_path.read_text())
        if isinstance(content, dict):
            # Check common flag patterns
            for val in content.values():
                if isinstance(val, str) and ("flag" in val.lower() or "⚑" in val):
                    return True
                if isinstance(val, list):
                    for item in val:
                        if isinstance(item, dict):
                            for v in item.values():
                                if isinstance(v, str) and ("flag" in v.lower() or "⚑" in v):
                                    return True
        return False
    except Exception:
        return False


@router.get("/{project_id}/artifacts", response_model=ArtifactListResponse)
async def list_artifacts(
    project_id: str,
    run_id: str,
    lane: str | None = None,
    object_type: str | None = None,
    has_flags: bool = False,
) -> ArtifactListResponse:
    """List artifacts for a run with optional filters."""
    project_root = CER_ARTIFACTS_ROOT / project_id

    # Find round directory
    round_id = "round_001"
    for rd in project_root.iterdir():
        if not rd.is_dir():
            continue
        mp = rd / "artifacts" / "00_manifest" / "run_manifest.json"
        if mp.exists():
            try:
                data = json.loads(mp.read_text())
                if data.get("run_id") == run_id:
                    round_id = rd.name
                    break
            except Exception:
                continue

    artifacts_root = project_root / round_id / "artifacts"
    if not artifacts_root.exists():
        return ArtifactListResponse(project_id=project_id, run_id=run_id, artifacts=[])

    # Lane to directory mapping
    lane_dir_map = {
        "lane_2a_claim": "03_lanes",
        "lane_2b_evidence": "03_lanes",
        "lane_2c_equivalence": "03_lanes",
        "lane_2d_consistency_pmcf": "03_lanes",
        "route": "01_route",
        "adjudication": "04_adjudication",
    }

    listings = []
    search_dirs = [artifacts_root]
    if lane and lane in lane_dir_map:
        search_dirs = [artifacts_root / lane_dir_map[lane]]
    elif lane == "lanes":
        search_dirs = [artifacts_root / "03_lanes"]

    for search_dir in search_dirs:
        if not search_dir.exists():
            continue
        for artifact_path in search_dir.rglob("*.json"):
            rel = artifact_path.relative_to(artifacts_root)
            derived_lane = _derive_lane(str(rel))
            derived_object_type = _derive_object_type(str(rel), artifact_path.name)
            flags = _has_flags_content(artifact_path)

            # Apply filters
            if object_type and derived_object_type != object_type:
                continue
            if has_flags and not flags:
                continue

            # Derive state from run manifest
            state = None
            try:
                manifest_path = artifacts_root.parent / "00_manifest" / "run_manifest.json"
                if manifest_path.exists():
                    state = json.loads(manifest_path.read_text()).get("current_state")
            except Exception:
                pass

            listings.append(ArtifactListing(
                path=str(artifact_path),
                artifact_name=artifact_path.name,
                state=state,
                lane=derived_lane,
                object_type=derived_object_type,
                has_flags=flags,
                size_bytes=artifact_path.stat().st_size,
                modified_at=datetime.fromtimestamp(artifact_path.stat().st_mtime, tz=timezone.utc).isoformat(),
            ))

    return ArtifactListResponse(project_id=project_id, run_id=run_id, artifacts=listings)


@router.get("/{project_id}/artifacts/{path:path}")
async def get_artifact(project_id: str, path: str) -> FileResponse:
    """Get raw artifact file."""
    project_root = CER_ARTIFACTS_ROOT / project_id
    # Search for the artifact
    for round_dir in project_root.iterdir():
        if not round_dir.is_dir():
            continue
        artifact_path = round_dir / "artifacts" / path
        if artifact_path.exists():
            return FileResponse(
                path=str(artifact_path),
                media_type="application/json",
                filename=artifact_path.name,
            )
    raise HTTPException(status_code=404, detail=f"Artifact not found: {path}")


@router.get("/{project_id}/compare", response_model=ReworkCompareResponse)
async def get_rework_compare(project_id: str, run_id: str, round_n: int = 1, round_n_plus_1: int = 2) -> ReworkCompareResponse:
    """Get rework comparison between two rounds."""
    project_root = CER_ARTIFACTS_ROOT / project_id
    round_n_id = f"round_{round_n:03d}"
    round_np1_id = f"round_{round_n_plus_1:03d}"

    lane_map = [
        ("lane_2a_claim", "2a — Claim Consistency", "claim_consistency_matrix.json"),
        ("lane_2b_evidence", "2b — SOTA Evidence", "sota_findings.json"),
        ("lane_2c_equivalence", "2c — Equivalence", "difference_impact_assessment.json"),
        ("lane_2d_consistency_pmcf", "2d — Consistency & PMCF", "consistency_delta_matrix.json"),
    ]

    import hashlib
    lanes = []
    for lane_id, display_name, artifact_name in lane_map:
        rn_artifact = project_root / round_n_id / "artifacts" / "03_lanes" / artifact_name
        rnp1_artifact = project_root / round_np1_id / "artifacts" / "03_lanes" / artifact_name

        rn_exists = rn_artifact.exists() and rn_artifact.stat().st_size > 0
        rnp1_exists = rnp1_artifact.exists() and rnp1_artifact.stat().st_size > 0

        if rn_exists and rnp1_exists:
            rn_hash = hashlib.sha256(rn_artifact.read_bytes()).hexdigest()
            rnp1_hash = hashlib.sha256(rnp1_artifact.read_bytes()).hexdigest()
            status = "UNCHANGED" if rn_hash == rnp1_hash else "CHANGED"
        elif rnp1_exists:
            status = "NEW"
        elif rn_exists:
            status = "REMOVED"
        else:
            status = "BOTH_MISSING"

        lanes.append(ReworkCompareLane(
            lane=lane_id,
            display_name=display_name,
            artifacts=[{
                "artifact": artifact_name,
                "round_n": str(rn_artifact) if rn_exists else None,
                "round_n_plus_1": str(rnp1_artifact) if rnp1_exists else None,
                "status": status,
            }],
        ))

    return ReworkCompareResponse(
        project_id=project_id,
        round_n=round_n_id,
        round_n_plus_1=round_np1_id,
        lanes=lanes,
        gate_decision_comparison={},
    )


@router.post("/{project_id}/gate-1/decision", response_model=Gate1DecisionResponse)
async def submit_gate1_decision(
    project_id: str,
    body: Gate1DecisionRequest,
    auth: CERAuthContext = Depends(get_cer_auth_with_gate_role),
) -> Gate1DecisionResponse:
    """Submit Gate 1 route adjudication decision.

    Requires SENIOR_REVIEWER or ADMIN role.

    Writes to: 04_adjudication/gate_1_decision.json
    Appends to: governance/{project_id}_decision_ledger.json
    Logs state transition in: governance/state_transition_log.jsonl
    """
    project_root = CER_ARTIFACTS_ROOT / project_id

    # Find round directory
    round_id = body.round_id or "round_001"
    artifacts_root = project_root / round_id / "artifacts"

    # Write gate_1_decision.json
    decision_data = {
        "schema_name": "cer_gate_decision",
        "schema_version": "v1",
        "gate": "GATE_1",
        "decision": body.decision,
        "reviewer": body.reviewer,
        "rationale": body.rationale,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "run_id": body.run_id,
        "round_id": round_id,
        "project_id": project_id,
    }
    decision_path = artifacts_root / "04_adjudication" / "gate_1_decision.json"
    decision_path.parent.mkdir(parents=True, exist_ok=True)
    decision_path.write_text(json.dumps(decision_data, indent=2))

    # Append to ledger
    ledger_path = project_root / "governance" / f"{project_id}_decision_ledger.json"
    if ledger_path.exists():
        try:
            ledger_data = json.loads(ledger_path.read_text())
        except Exception:
            ledger_data = {"schema_name": "cer_decision_ledger", "project_id": project_id, "entries": []}
    else:
        ledger_data = {"schema_name": "cer_decision_ledger", "project_id": project_id, "entries": []}

    entries = ledger_data.get("entries", [])
    next_id = f"LEDGER-{len(entries) + 1:03d}"
    ledger_entry = {
        "entry_id": next_id,
        "entry_type": "GATE_DECISION",
        "run_id": body.run_id,
        "round_id": round_id,
        "actor": body.reviewer,
        "actor_user_id": auth.user_id,
        "actor_role": auth.role.value,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "gate": "GATE_1",
        "decision_data": {"decision": body.decision, "rationale": body.rationale},
        "immutable": True,
        "from_state": "S08",
        "to_state": "S09",
    }
    entries.append(ledger_entry)
    ledger_data["entries"] = entries
    ledger_path.write_text(json.dumps(ledger_data, indent=2))

    # Log state transition
    state_log_path = project_root / "governance" / "state_transition_log.jsonl"
    st_entry = {
        "entry_id": f"ST-{len(entries):03d}",
        "run_id": body.run_id,
        "round_id": round_id,
        "from_state": "S08",
        "to_state": "S09",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "actor": body.reviewer,
        "actor_user_id": auth.user_id,
        "actor_role": auth.role.value,
        "trigger": "gate_1_decision",
    }
    with open(state_log_path, "a") as f:
        f.write(json.dumps(st_entry, ensure_ascii=False) + "\n")

    # Write gate audit record
    auditor = GateAuditor(project_root)
    bundle_ref = str(decision_path.relative_to(project_root))
    try:
        gate_audit_path = auditor.write_gate1_audit(
            run_id=body.run_id,
            round_id=round_id,
            decision=body.decision,
            equivalence_route=body.decision,
            actor=body.reviewer,
            actor_role=auth.role.value,
            trigger="gate_1_decision",
            bundle_ref=bundle_ref,
            project_id=project_id,
        )
    except Exception:
        gate_audit_path = str(decision_path)

    return Gate1DecisionResponse(
        success=True,
        ledger_entry_id=next_id,
        gate_audit_path=gate_audit_path,
        state_transition_id=st_entry["entry_id"],
    )


@router.post("/{project_id}/gate-3/decision", response_model=Gate3DecisionResponse)
async def submit_gate3_decision(
    project_id: str,
    body: Gate3DecisionRequest,
    auth: CERAuthContext = Depends(get_cer_auth_with_gate_role),
) -> Gate3DecisionResponse:
    """Submit BRR terminal decision (BRR_ACCEPTABLE/UNACCEPTABLE/MISALIGNED).

    THIS IS THE ONLY LOCATION WHERE RISK_BENEFIT TERMINAL DECISIONS CAN BE ISSUED.
    Stub model: BLOCKED — returns stub_blocked=True if model is a stub.
    Requires SENIOR_REVIEWER or ADMIN role.

    Writes to: 04_adjudication/gate_3_decision.json
    Appends to: governance/{project_id}_decision_ledger.json
    Logs state transition in: governance/state_transition_log.jsonl
    """
    project_root = CER_ARTIFACTS_ROOT / project_id

    # Check for stub model FIRST — before any role check
    round_id = body.round_id or "round_001"
    for rd in project_root.iterdir():
        if not rd.is_dir():
            continue
        mp = rd / "artifacts" / "00_manifest" / "run_manifest.json"
        if mp.exists():
            try:
                manifest_data = json.loads(mp.read_text())
                if manifest_data.get("run_id") == body.run_id:
                    model = str(manifest_data.get("model", ""))
                    if "stub" in model.lower() or "test" in model.lower():
                        return Gate3DecisionResponse(
                            success=False,
                            stub_blocked=True,
                            error=f"BRR terminal decision BLOCKED: stub model '{model}' cannot issue RISK_BENEFIT decision. Real model required.",
                        )
            except Exception:
                continue

    # Write gate_3_decision.json
    decision_data = {
        "schema_name": "cer_gate_decision",
        "schema_version": "v1",
        "gate": "GATE_3",
        "decision": body.decision,
        "conditional": body.conditional,
        "outstanding_rework": body.outstanding_rework,
        "reviewer": body.reviewer,
        "reauth_timestamp": body.reauth_timestamp,
        "rationale": body.rationale,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "run_id": body.run_id,
        "round_id": round_id,
        "project_id": project_id,
    }
    decision_path = project_root / round_id / "artifacts" / "04_adjudication" / "gate_3_decision.json"
    decision_path.parent.mkdir(parents=True, exist_ok=True)
    decision_path.write_text(json.dumps(decision_data, indent=2))

    # Append to ledger
    ledger_path = project_root / "governance" / f"{project_id}_decision_ledger.json"
    if ledger_path.exists():
        try:
            ledger_data = json.loads(ledger_path.read_text())
        except Exception:
            ledger_data = {"schema_name": "cer_decision_ledger", "project_id": project_id, "entries": []}
    else:
        ledger_data = {"schema_name": "cer_decision_ledger", "project_id": project_id, "entries": []}

    entries = ledger_data.get("entries", [])
    next_id = f"LEDGER-{len(entries) + 1:03d}"
    to_state = "S12" if body.decision == "BRR_ACCEPTABLE" and not body.conditional else "S17"
    ledger_entry = {
        "entry_id": next_id,
        "entry_type": "TERMINAL_DECISION",
        "run_id": body.run_id,
        "round_id": round_id,
        "actor": body.reviewer,
        "actor_user_id": auth.user_id,
        "actor_role": auth.role.value,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "gate": "GATE_3",
        "decision_data": {
            "decision": body.decision,
            "conditional": body.conditional,
            "outstanding_rework": body.outstanding_rework,
            "rationale": body.rationale,
        },
        "immutable": True,
        "from_state": "S11",
        "to_state": to_state,
    }
    entries.append(ledger_entry)
    ledger_data["entries"] = entries
    ledger_path.write_text(json.dumps(ledger_data, indent=2))

    # Log state transition
    state_log_path = project_root / "governance" / "state_transition_log.jsonl"
    st_entry = {
        "entry_id": f"ST-{len(entries):03d}",
        "run_id": body.run_id,
        "round_id": round_id,
        "from_state": "S11",
        "to_state": to_state,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "actor": body.reviewer,
        "actor_user_id": auth.user_id,
        "actor_role": auth.role.value,
        "trigger": "gate_3_decision",
    }
    with open(state_log_path, "a") as f:
        f.write(json.dumps(st_entry, ensure_ascii=False) + "\n")

    # Write gate audit record
    auditor = GateAuditor(project_root)
    bundle_ref = str(decision_path.relative_to(project_root))
    try:
        gate_audit_path = auditor.write_gate3_audit(
            run_id=body.run_id,
            round_id=round_id,
            decision=body.decision,
            actor=body.reviewer,
            actor_id=auth.user_id,
            actor_role=auth.role.value,
            reauth_timestamp=body.reauth_timestamp,
            brr_composite_bundle_ref=bundle_ref,
            contributions_verified={},
            conditional=body.conditional,
            outstanding_rework=body.outstanding_rework,
            project_id=project_id,
        )
    except Exception:
        gate_audit_path = str(decision_path)

    return Gate3DecisionResponse(
        success=True,
        ledger_entry_id=next_id,
        gate_audit_path=gate_audit_path,
        state_transition_id=st_entry["entry_id"],
    )
