"""RMF Operations Board / Status Board API.

Provides a team-operations view of all RMF projects:
  - GET /api/rmf/board                    -> overall summary stats
  - GET /api/rmf/board?status=<status>    -> filtered project list
  - GET /api/rmf/board/recent             -> recently updated projects
  - GET /api/rmf/board/by-status          -> projects grouped by status
"""

from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel
from typing import Any

from deerflow.runtime.rmf_review import RMFProjectStore, ProjectStatus

logger = __name__
router = APIRouter(prefix="/api/rmf/board", tags=["rmf-board"])


# ---------------------------------------------------------------------------
# Role permission helper
# ---------------------------------------------------------------------------

def _check_role(
    role: str | None,
    allowed: set[str],
    action: str,
) -> None:
    """Raise HTTPException if role is not in allowed set."""
    if role is None:
        raise HTTPException(status_code=401, detail=f"Missing X-RMF-Role header for {action}")
    if role not in allowed:
        raise HTTPException(
            status_code=403,
            detail=f"Role '{role}' is not authorized for {action}. Allowed: {', '.join(sorted(allowed))}",
        )


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class ProjectBoardItem(BaseModel):
    project_id: str
    project_name: str
    product_name: str
    current_status: str
    latest_machine_recommendation: str | None
    latest_human_decision: str | None
    latest_gate_status: str | None
    total_runs: int
    total_rework_rounds: int
    updated_at: str
    latest_thread_id: str | None
    latest_run_id: str | None


class StatusGroup(BaseModel):
    status: str
    count: int
    projects: list[ProjectBoardItem]


class BlockingReason(BaseModel):
    reason: str
    count: int
    project_ids: list[str]


class BoardSummary(BaseModel):
    total_projects: int
    total_runs: int
    total_rework_rounds: int
    by_status: dict[str, int]
    by_machine_recommendation: dict[str, int]
    by_human_decision: dict[str, int]
    pending_human_decision_count: int
    rework_required_count: int
    passed_count: int
    blocking_reasons: list[BlockingReason]


class BoardResponse(BaseModel):
    summary: BoardSummary
    projects: list[ProjectBoardItem]
    filter_status: str | None


class RecentActivityItem(BaseModel):
    project_id: str
    project_name: str
    event: str
    detail: str
    timestamp: str


class RecentActivityResponse(BaseModel):
    items: list[RecentActivityItem]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _store() -> RMFProjectStore:
    return RMFProjectStore()


def _project_to_board_item(p) -> ProjectBoardItem:
    return ProjectBoardItem(
        project_id=p.project_id,
        project_name=p.project_name,
        product_name=p.product_name,
        current_status=p.current_status.value,
        latest_machine_recommendation=p.latest_machine_recommendation,
        latest_human_decision=p.latest_human_decision,
        latest_gate_status=p.latest_gate_status,
        total_runs=p.total_runs,
        total_rework_rounds=p.total_rework_rounds,
        updated_at=p.updated_at,
        latest_thread_id=p.latest_thread_id,
        latest_run_id=p.latest_run_id,
    )


def _build_summary(projects: list) -> BoardSummary:
    total_runs = sum(p.total_runs for p in projects)
    total_rework = sum(p.total_rework_rounds for p in projects)
    by_status: dict[str, int] = {}
    by_machine: dict[str, int] = {}
    by_human: dict[str, int] = {}
    pending_human = 0
    rework_required = 0
    passed = 0
    rework_project_ids: list[str] = []
    pending_decision_project_ids: list[str] = []
    conditional_pass_ids: list[str] = []

    for p in projects:
        s = p.current_status.value
        by_status[s] = by_status.get(s, 0) + 1
        if p.latest_machine_recommendation:
            by_machine[p.latest_machine_recommendation] = by_machine.get(p.latest_machine_recommendation, 0) + 1
        if p.latest_human_decision:
            by_human[p.latest_human_decision] = by_human.get(p.latest_human_decision, 0) + 1
        if s == "pending_human_decision":
            pending_human += 1
            pending_decision_project_ids.append(p.project_id)
        elif s == "rework_required":
            rework_required += 1
            rework_project_ids.append(p.project_id)
        elif s in ("passed", "conditional_pass", "closed"):
            passed += 1

    blocking_reasons: list[BlockingReason] = []
    if rework_project_ids:
        blocking_reasons.append(BlockingReason(
            reason="Rework in progress",
            count=len(rework_project_ids),
            project_ids=rework_project_ids,
        ))
    if pending_decision_project_ids:
        blocking_reasons.append(BlockingReason(
            reason="Awaiting human decision",
            count=len(pending_decision_project_ids),
            project_ids=pending_decision_project_ids,
        ))
    if conditional_pass_ids:
        blocking_reasons.append(BlockingReason(
            reason="Conditional pass — CAPAs pending",
            count=len(conditional_pass_ids),
            project_ids=conditional_pass_ids,
        ))

    return BoardSummary(
        total_projects=len(projects),
        total_runs=total_runs,
        total_rework_rounds=total_rework,
        by_status=by_status,
        by_machine_recommendation=by_machine,
        by_human_decision=by_human,
        pending_human_decision_count=pending_human,
        rework_required_count=rework_required,
        passed_count=passed,
        blocking_reasons=blocking_reasons,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("", response_model=BoardResponse)
async def get_board(
    status: str | None = None,
    x_rmf_role: str | None = Header(None, alias="X-RMF-Role"),
) -> BoardResponse:
    """Get the RMF operations board with summary stats and optional status filter.

    Available to all roles.
    """
    store = _store()
    status_enum = ProjectStatus(status) if status else None
    all_projects = store.list_projects(limit=500)
    filtered = [p for p in all_projects if status_enum is None or p.current_status == status_enum]
    summary = _build_summary(all_projects)
    return BoardResponse(
        summary=summary,
        projects=[_project_to_board_item(p) for p in filtered],
        filter_status=status,
    )


@router.get("/by-status", response_model=list[StatusGroup])
async def get_board_by_status(
    x_rmf_role: str | None = Header(None, alias="X-RMF-Role"),
) -> list[StatusGroup]:
    """Get projects grouped by status."""
    store = _store()
    all_projects = store.list_projects(limit=500)
    by_status: dict[str, list] = {}
    for p in all_projects:
        s = p.current_status.value
        if s not in by_status:
            by_status[s] = []
        by_status[s].append(_project_to_board_item(p))
    return [
        StatusGroup(status=s, count=len(items), projects=items)
        for s, items in sorted(by_status.items())
    ]


@router.get("/recent", response_model=RecentActivityResponse)
async def get_recent_activity(
    x_rmf_role: str | None = Header(None, alias="X-RMF-Role"),
) -> RecentActivityResponse:
    """Get recent activity across all projects."""
    store = _store()
    all_projects = store.list_projects(limit=500)

    def _status_event(p) -> tuple[str, str]:
        s = p.current_status.value
        if s == "rework_required":
            latest = p.review_cycles[-1] if p.review_cycles else None
            detail = f"Round {len(p.review_cycles) - 1}: {latest.machine_recommendation if latest else '—'}"
            return ("Rework required", detail)
        elif s == "pending_human_decision":
            return ("Pending human decision", f"Machine recommends: {p.latest_machine_recommendation or '—'}")
        elif s == "running":
            return ("Run started", f"Thread: {p.latest_thread_id or '—'}")
        elif s == "conditional_pass":
            return ("Conditional pass", p.latest_human_decision or "Human decision recorded")
        elif s == "passed":
            return ("Passed", "Final gate issued")
        elif s == "closed":
            return ("Closed", "Project closed")
        else:
            return (s.replace("_", " ").title(), f"Status: {s}")

    items: list[RecentActivityItem] = []
    for p in sorted(all_projects, key=lambda x: x.updated_at, reverse=True)[:20]:
        event, detail = _status_event(p)
        items.append(RecentActivityItem(
            project_id=p.project_id,
            project_name=p.project_name,
            event=event,
            detail=detail,
            timestamp=p.updated_at,
        ))

    return RecentActivityResponse(items=items)
