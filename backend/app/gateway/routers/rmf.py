"""RMF Review Workflow gateway router.

Provides a REST entry layer for the RMF review workbench:
  - POST   /api/rmf/start              -> trigger smoke-run
  - GET    /api/rmf/runs              -> list all RMF thread summaries
  - GET    /api/rmf/runs/{thread_id}   -> list all runs for a thread
  - GET    /api/rmf/run/{thread_id}/{run_id} -> rich run detail
  - GET    /api/rmf/status/{thread_id} -> latest run status / summary
  - POST   /api/rmf/human-decision   -> submit human gate decision + closure
  - POST   /api/rmf/rework           -> trigger rework run for rework_required
  - GET    /api/rmf/closure/{thread_id} -> closure result + next action summary
  - GET    /api/rmf/artifacts/{thread_id} -> artifact path summary
"""

from __future__ import annotations

import json
import logging
import subprocess
import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/rmf", tags=["rmf"])

_REPO_ROOT = Path(__file__).resolve().parents[4]


# ---------------------------------------------------------------------------
# Shared artifact step mapping
# ---------------------------------------------------------------------------

_ARTIFACT_STEP_MAP = [
    ("06_final/final_report.md", "final_report.md", "rmf_report_agent"),
    ("06_final/final_report.json", "final_report.json", "rmf_report_agent"),
    ("06_final/capa_action_list.json", "capa_action_list.json", "rmf_report_agent"),
    ("06_final/backflow_candidates.json", "backflow_candidates.json", "rmf_report_agent"),
    ("07_gate_closure/gate_closure_report.md", "gate_closure_report.md", "rmf_gate_closure_agent"),
    ("07_gate_closure/gate_closure_report.json", "gate_closure_report.json", "rmf_gate_closure_agent"),
    ("07_gate_closure/next_action_packet.json", "next_action_packet.json", "rmf_gate_closure_agent"),
    ("05_human_boundary/human_review_queue.json", "human_review_queue.json", "rmf_human_boundary_agent"),
    ("05_human_boundary/provisional_gate_recommendation.json", "provisional_gate_recommendation.json", "rmf_human_boundary_agent"),
    ("05_human_boundary/human_gate_decision.json", "human_gate_decision.json", "rmf_human_boundary_agent"),
    ("04_dimension_review/dimension_assessment.json", "dimension_assessment.json", "rmf_dimension_review_agent"),
    ("04_dimension_review/dimension_review_report.md", "dimension_review_report.md", "rmf_dimension_review_agent"),
    ("03_rmf_precheck/rmf_precheck_report.json", "rmf_precheck_report.json", "rmf_precheck_agent"),
    ("02_fmea_precheck/fmea_precheck_report.json", "fmea_precheck_report.json", "fmea_precheck_agent"),
    ("01_parse/rmf_normalized.json", "rmf_normalized.json", "rmf_parse_normalize_agent"),
    ("01_parse/fmea_normalized.json", "fmea_normalized.json", "rmf_parse_normalize_agent"),
    ("00_manifest/run_manifest.json", "run_manifest.json", "rmf_intake_agent"),
    ("00_manifest/input_inventory.json", "input_inventory.json", "rmf_intake_agent"),
    ("00_manifest/missing_items_report.md", "missing_items_report.md", "rmf_intake_agent"),
]


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class RMFStartRequest(BaseModel):
    project_profile: str = Field(..., description="Absolute path to project_profile.yaml")
    input_root: str | None = Field(None, description="Optional override for input root")
    thread_id: str | None = Field(None, description="Optional thread id (generated if not provided)")
    mode: str = Field(default="smoke-run", description="Run mode: smoke-run | closure-only")


class RMFStartResponse(BaseModel):
    thread_id: str
    run_id: str
    mode: str
    workflow_name: str
    executed_steps: list[str]
    artifact_root_virtual: str
    artifact_root_actual: str


class HumanDecisionRequest(BaseModel):
    thread_id: str = Field(..., description="Thread id for the existing run")
    decision: str = Field(..., description="pass | conditional_pass | rework_required")
    reviewer: str = Field(..., description="Reviewer name or ID")
    rationale: str = Field(default="", description="Decision rationale")
    linked_review_items: list[str] = Field(default_factory=list)
    linked_capa_ids: list[str] = Field(default_factory=list)


class HumanDecisionResponse(BaseModel):
    success: bool
    decision_recorded: bool
    gate_closure_executed: bool
    artifact_root_actual: str
    gate_closure_report_path: str
    next_action_packet_path: str


class ReworkRequest(BaseModel):
    thread_id: str = Field(..., description="Thread id to rework")
    rationale: str = Field(default="", description="Reason for rework")


class ArtifactSummary(BaseModel):
    path: str
    artifact_name: str
    step_id: str
    download_url: str


class RMFStatusResponse(BaseModel):
    thread_id: str
    run_id: str | None
    mode: str | None
    workflow_name: str | None
    executed_steps: list[str]
    artifact_root_virtual: str | None
    artifact_root_actual: str | None
    has_final_report: bool
    has_gate_closure_report: bool
    has_human_decision: bool
    has_human_review_queue: bool
    has_provisional_gate: bool
    has_dimension_assessment: bool
    has_fmea_precheck: bool
    has_rmf_precheck: bool
    # Machine vs human distinction
    final_recommended_gate: str | None = None  # machine recommendation from final_report
    provisional_gate: str | None = None  # provisional gate from human_boundary
    human_gate_required: bool | None = None
    provisional_only: bool | None = None  # True if machine provisional only
    # Human decision
    human_decision_value: str | None = None  # pass / conditional_pass / rework_required
    human_decision_reviewer: str | None = None
    human_decision_simulated: bool | None = None
    human_decision_date: str | None = None
    # Closure
    final_gate_status: str | None = None  # final gate after human decision
    closure_completed: bool = False


class RMFArtifactsResponse(BaseModel):
    thread_id: str
    run_id: str
    artifact_root_actual: str
    artifacts: list[ArtifactSummary]


# ---- Run listing ----


class RunSummaryItem(BaseModel):
    run_id: str
    mode: str
    workflow_name: str
    executed_steps: list[str]
    artifact_root_actual: str
    updated_at: float  # mtime


class ThreadRunsResponse(BaseModel):
    thread_id: str
    runs: list[RunSummaryItem]


class ThreadSummary(BaseModel):
    thread_id: str
    latest_run_id: str | None
    latest_mode: str | None
    latest_executed_steps: list[str]
    latest_final_recommended_gate: str | None
    latest_final_gate_status: str | None
    latest_has_closure: bool
    updated_at: float


class AllRunsResponse(BaseModel):
    threads: list[ThreadSummary]


# ---- Rich run detail ----


class RichRunResponse(BaseModel):
    thread_id: str
    run_id: str
    mode: str
    workflow_name: str
    executed_steps: list[str]
    artifact_root_virtual: str
    artifact_root_actual: str
    # Run manifest summary
    project_id: str | None
    project_name: str | None
    primary_review_object: str | None
    input_root: str | None
    human_gate_required: bool
    # Step summaries
    intake_summary: dict | None = None
    fmea_precheck_summary: dict | None = None
    rmf_precheck_summary: dict | None = None
    dimension_summary: dict | None = None
    human_boundary_summary: dict | None = None
    # Machine recommendation
    final_recommended_gate: str | None = None
    provisional_gate: str | None = None
    provisional_only: bool | None = None
    human_gate_required_flag: bool | None = None
    # Human decision
    human_decision: dict | None = None
    # Closure
    gate_closure: dict | None = None
    next_action_packet: dict | None = None
    # Flags
    has_closure: bool = False
    closure_completed: bool = False


# ---- Closure / next action ----


class NextActionSummary(BaseModel):
    packet_type: str | None
    decision: str | None
    description: str | None
    blocking_actions_count: int = 0
    total_actions_count: int = 0
    linked_capa_ids: list[str]


class ClosureResponse(BaseModel):
    thread_id: str
    run_id: str
    closure_completed: bool
    final_gate_status: str | None
    human_decision: dict | None
    provisional_gate: str | None
    provisional_only: bool | None
    next_action: NextActionSummary | None
    gate_closure_report: dict | None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _get_rmf_threads_base() -> Path:
    from deerflow.config.paths import get_paths
    return get_paths().base_dir / "threads"


def _scan_rmf_threads() -> list[str]:
    """Return all thread_ids that have RMF runs."""
    base = _get_rmf_threads_base()
    if not base.exists():
        return []
    threads = []
    for d in base.iterdir():
        if not d.is_dir():
            continue
        rmf_path = d / "user-data" / "outputs" / "rmf_review_v1_1"
        if rmf_path.exists():
            threads.append(d.name)
    return threads


def _get_runs_for_thread(thread_id: str) -> list[RunSummaryItem]:
    """Return all runs for a thread, sorted newest first."""
    from deerflow.config.paths import get_paths
    paths = get_paths()
    outputs_dir = paths.sandbox_outputs_dir(thread_id)
    rmf_base = outputs_dir / "rmf_review_v1_1"
    if not rmf_base.exists():
        return []

    runs: list[RunSummaryItem] = []
    for run_dir in rmf_base.iterdir():
        if not run_dir.is_dir():
            continue
        summary_path = run_dir / "artifacts" / "00_manifest" / "run_summary.json"
        if not summary_path.exists():
            continue
        try:
            summary = json.loads(summary_path.read_text())
            runs.append(RunSummaryItem(
                run_id=summary["run_id"],
                mode=summary.get("mode", "unknown"),
                workflow_name=summary.get("workflow_name", "unknown"),
                executed_steps=summary.get("executed_steps", []),
                artifact_root_actual=summary.get("artifact_root_actual", str(run_dir)),
                updated_at=run_dir.stat().st_mtime,
            ))
        except Exception:
            continue
    runs.sort(key=lambda r: r.updated_at, reverse=True)
    return runs


def _get_thread_summary(thread_id: str) -> ThreadSummary | None:
    runs = _get_runs_for_thread(thread_id)
    if not runs:
        return None
    latest = runs[0]
    artifact_root = Path(latest.artifact_root_actual)
    has_closure = (artifact_root / "07_gate_closure" / "gate_closure_report.json").exists()
    final_gate_status = None
    final_recommended_gate = None
    if has_closure:
        try:
            gcr = json.loads((artifact_root / "07_gate_closure" / "gate_closure_report.json").read_text())
            final_gate_status = gcr.get("final_decision")
        except Exception:
            pass
    if (artifact_root / "06_final" / "final_report.json").exists():
        try:
            fr = json.loads((artifact_root / "06_final" / "final_report.json").read_text())
            final_recommended_gate = fr.get("gate_recommendation", {}).get("recommended_gate")
        except Exception:
            pass
    return ThreadSummary(
        thread_id=thread_id,
        latest_run_id=latest.run_id,
        latest_mode=latest.mode,
        latest_executed_steps=latest.executed_steps,
        latest_final_recommended_gate=final_recommended_gate,
        latest_final_gate_status=final_gate_status,
        latest_has_closure=has_closure,
        updated_at=latest.updated_at,
    )


def _build_status_response(thread_id: str, summary: dict, artifact_root: Path) -> RMFStatusResponse:
    """Build enriched RMFStatusResponse from run_summary and artifact files."""
    has_final_report = (artifact_root / "06_final" / "final_report.md").exists()
    has_gate_closure = (artifact_root / "07_gate_closure" / "gate_closure_report.json").exists()
    has_human_decision = (artifact_root / "05_human_boundary" / "human_gate_decision.json").exists()
    has_human_review_queue = (artifact_root / "05_human_boundary" / "human_review_queue.json").exists()
    has_provisional_gate = (artifact_root / "05_human_boundary" / "provisional_gate_recommendation.json").exists()
    has_dimension_assessment = (artifact_root / "04_dimension_review" / "dimension_assessment.json").exists()
    has_fmea_precheck = (artifact_root / "02_fmea_precheck" / "fmea_precheck_report.json").exists()
    has_rmf_precheck = (artifact_root / "03_rmf_precheck" / "rmf_precheck_report.json").exists()

    # Machine recommendations
    final_recommended_gate = None
    provisional_gate = None
    human_gate_required = None
    provisional_only = None
    if (artifact_root / "06_final" / "final_report.json").exists():
        try:
            fr = json.loads((artifact_root / "06_final" / "final_report.json").read_text())
            final_recommended_gate = fr.get("gate_recommendation", {}).get("recommended_gate")
            human_gate_required = fr.get("human_gate_required")
        except Exception:
            pass
    if has_provisional_gate:
        try:
            pg = json.loads((artifact_root / "05_human_boundary" / "provisional_gate_recommendation.json").read_text())
            provisional_gate = pg.get("gate")
            provisional_only = pg.get("provisional_only")
        except Exception:
            pass

    # Human decision
    human_decision_value = None
    human_decision_reviewer = None
    human_decision_simulated = None
    human_decision_date = None
    final_gate_status = None
    if has_human_decision:
        try:
            hd = json.loads((artifact_root / "05_human_boundary" / "human_gate_decision.json").read_text())
            human_decision_value = hd.get("decision")
            human_decision_reviewer = hd.get("reviewer")
            human_decision_simulated = hd.get("simulated")
            human_decision_date = hd.get("decision_date")
        except Exception:
            pass
    if has_gate_closure:
        try:
            gcr = json.loads((artifact_root / "07_gate_closure" / "gate_closure_report.json").read_text())
            final_gate_status = gcr.get("final_decision")
        except Exception:
            pass

    return RMFStatusResponse(
        thread_id=summary["thread_id"],
        run_id=summary.get("run_id"),
        mode=summary.get("mode"),
        workflow_name=summary.get("workflow_name"),
        executed_steps=summary.get("executed_steps", []),
        artifact_root_virtual=summary.get("artifact_root_virtual"),
        artifact_root_actual=summary.get("artifact_root_actual"),
        has_final_report=has_final_report,
        has_gate_closure_report=has_gate_closure,
        has_human_decision=has_human_decision,
        has_human_review_queue=has_human_review_queue,
        has_provisional_gate=has_provisional_gate,
        has_dimension_assessment=has_dimension_assessment,
        has_fmea_precheck=has_fmea_precheck,
        has_rmf_precheck=has_rmf_precheck,
        final_recommended_gate=final_recommended_gate,
        provisional_gate=provisional_gate,
        human_gate_required=human_gate_required,
        provisional_only=provisional_only,
        human_decision_value=human_decision_value,
        human_decision_reviewer=human_decision_reviewer,
        human_decision_simulated=human_decision_simulated,
        human_decision_date=human_decision_date,
        final_gate_status=final_gate_status,
        closure_completed=has_gate_closure,
    )


def _get_run_summary(thread_id: str) -> dict | None:
    """Read run_summary.json from the latest run in the thread's RMF outputs."""
    from deerflow.config.paths import get_paths
    paths = get_paths()
    outputs_dir = paths.sandbox_outputs_dir(thread_id)
    rmf_base = outputs_dir / "rmf_review_v1_1"
    if not rmf_base.exists():
        return None
    run_dirs = sorted(
        (d for d in rmf_base.iterdir() if d.is_dir()),
        key=lambda d: d.stat().st_mtime,
        reverse=True,
    )
    if not run_dirs:
        return None
    summary_path = run_dirs[0] / "artifacts" / "00_manifest" / "run_summary.json"
    if not summary_path.exists():
        return None
    return json.loads(summary_path.read_text())


def _write_human_decision(thread_id: str, run_summary: dict, decision: HumanDecisionRequest) -> None:
    """Write human_gate_decision.json into the existing run's artifact directory."""
    artifact_root = Path(run_summary["artifact_root_actual"])
    decision_path = artifact_root / "05_human_boundary" / "human_gate_decision.json"
    decision_path.parent.mkdir(parents=True, exist_ok=True)
    decision_record = {
        "decision": decision.decision,
        "reviewer": decision.reviewer,
        "decision_date": "2026-04-16",
        "rationale": decision.rationale,
        "linked_review_items": decision.linked_review_items,
        "linked_capa_ids": decision.linked_capa_ids,
        "simulated": False,
    }
    decision_path.write_text(json.dumps(decision_record, indent=2, ensure_ascii=False))


def _artifacts_for_run(thread_id: str, summary: dict, artifact_root: Path) -> list[ArtifactSummary]:
    """Build artifact list for a given run."""
    artifacts: list[ArtifactSummary] = []
    for rel_path, artifact_name, step_id in _ARTIFACT_STEP_MAP:
        full_path = artifact_root / rel_path
        if full_path.exists():
            virtual_path = f"mnt/user-data/outputs/rmf_review_v1_1/{summary['run_id']}/artifacts/{rel_path}"
            download_url = f"/api/threads/{thread_id}/artifacts/{virtual_path}"
            artifacts.append(ArtifactSummary(
                path=str(full_path),
                artifact_name=artifact_name,
                step_id=step_id,
                download_url=download_url,
            ))
    return artifacts


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/start", response_model=RMFStartResponse)
async def rmf_start(body: RMFStartRequest) -> RMFStartResponse:
    """Trigger an RMF review smoke-run."""
    existing = _get_run_summary(body.thread_id) if body.thread_id else None
    if existing:
        return RMFStartResponse(
            thread_id=existing["thread_id"],
            run_id=existing["run_id"],
            mode=existing["mode"],
            workflow_name=existing["workflow_name"],
            executed_steps=existing["executed_steps"],
            artifact_root_virtual=existing["artifact_root_virtual"],
            artifact_root_actual=existing["artifact_root_actual"],
        )

    cmd = [
        sys.executable,
        str(_REPO_ROOT / "scripts" / "rmf_review_runner.py"),
        "--project-profile",
        body.project_profile,
        "--mode",
        body.mode,
    ]
    if body.input_root:
        cmd.extend(["--input-root", body.input_root])
    if body.thread_id:
        cmd.extend(["--thread-id", body.thread_id])

    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(_REPO_ROOT), timeout=1800)
    if result.returncode != 0:
        logger.error("RMF runner failed: %s", result.stderr)
        raise HTTPException(status_code=500, detail=f"RMF runner failed: {result.stderr}")

    output = json.loads(result.stdout)
    return RMFStartResponse(**output)


@router.get("/runs", response_model=AllRunsResponse)
async def rmf_list_threads() -> AllRunsResponse:
    """List all RMF thread summaries."""
    threads = _scan_rmf_threads()
    summaries: list[ThreadSummary] = []
    for thread_id in threads:
        s = _get_thread_summary(thread_id)
        if s:
            summaries.append(s)
    summaries.sort(key=lambda t: t.updated_at, reverse=True)
    return AllRunsResponse(threads=summaries)


@router.get("/runs/{thread_id}", response_model=ThreadRunsResponse)
async def rmf_list_runs(thread_id: str) -> ThreadRunsResponse:
    """List all runs for a specific thread."""
    runs = _get_runs_for_thread(thread_id)
    return ThreadRunsResponse(thread_id=thread_id, runs=runs)


@router.get("/run/{thread_id}/{run_id}", response_model=RichRunResponse)
async def rmf_run_detail(thread_id: str, run_id: str) -> RichRunResponse:
    """Get rich detail for a specific run, including step summaries and decision state."""
    from deerflow.config.paths import get_paths
    paths = get_paths()
    outputs_dir = paths.sandbox_outputs_dir(thread_id)
    artifact_root = outputs_dir / "rmf_review_v1_1" / run_id / "artifacts"

    summary_path = artifact_root / "00_manifest" / "run_summary.json"
    if not summary_path.exists():
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found for thread {thread_id}")

    summary = json.loads(summary_path.read_text())

    # Run manifest
    run_manifest = None
    project_id = None
    project_name = None
    primary_review_object = None
    input_root = None
    human_gate_required = False
    manifest_summary = None
    run_manifest_path = artifact_root / "00_manifest" / "run_manifest.json"
    if run_manifest_path.exists():
        run_manifest = json.loads(run_manifest_path.read_text())
        project_id = run_manifest.get("project_id")
        project_name = run_manifest.get("project_name")
        primary_review_object = run_manifest.get("primary_review_object")
        input_root = run_manifest.get("input_root")
        human_gate_required = run_manifest.get("human_gate_required", False)
        # Inventory summary
        inv_path = artifact_root / "00_manifest" / "input_inventory.json"
        if inv_path.exists():
            inv = json.loads(inv_path.read_text())
            manifest_summary = {
                "document_count": len(inv.get("documents", [])),
                "documents": inv.get("documents", []),
            }

    # Step summaries
    intake_summary = manifest_summary
    fmea_summary = None
    rmf_precheck_summary = None
    dimension_summary = None
    human_boundary_summary = None

    if (artifact_root / "02_fmea_precheck" / "fmea_precheck_report.json").exists():
        try:
            fmea_summary = json.loads((artifact_root / "02_fmea_precheck" / "fmea_precheck_report.json").read_text())
        except Exception:
            pass
    if (artifact_root / "03_rmf_precheck" / "rmf_precheck_report.json").exists():
        try:
            rmf_precheck_summary = json.loads((artifact_root / "03_rmf_precheck" / "rmf_precheck_report.json").read_text())
        except Exception:
            pass
    if (artifact_root / "04_dimension_review" / "dimension_assessment.json").exists():
        try:
            dimension_summary = json.loads((artifact_root / "04_dimension_review" / "dimension_assessment.json").read_text())
        except Exception:
            pass
    if (artifact_root / "05_human_boundary" / "human_review_queue.json").exists():
        try:
            hq = json.loads((artifact_root / "05_human_boundary" / "human_review_queue.json").read_text())
            human_boundary_summary = {
                "item_count": len(hq.get("items", [])),
                "items": hq.get("items", []),
            }
        except Exception:
            pass

    # Machine recommendations
    final_recommended_gate = None
    provisional_gate = None
    provisional_only = None
    human_gate_required_flag = human_gate_required
    if (artifact_root / "06_final" / "final_report.json").exists():
        try:
            fr = json.loads((artifact_root / "06_final" / "final_report.json").read_text())
            final_recommended_gate = fr.get("gate_recommendation", {}).get("recommended_gate")
        except Exception:
            pass
    if (artifact_root / "05_human_boundary" / "provisional_gate_recommendation.json").exists():
        try:
            pg = json.loads((artifact_root / "05_human_boundary" / "provisional_gate_recommendation.json").read_text())
            provisional_gate = pg.get("gate")
            provisional_only = pg.get("provisional_only")
        except Exception:
            pass

    # Human decision
    human_decision = None
    if (artifact_root / "05_human_boundary" / "human_gate_decision.json").exists():
        try:
            human_decision = json.loads((artifact_root / "05_human_boundary" / "human_gate_decision.json").read_text())
        except Exception:
            pass

    # Closure
    has_closure = (artifact_root / "07_gate_closure" / "gate_closure_report.json").exists()
    gate_closure = None
    next_action_packet = None
    if has_closure:
        try:
            gate_closure = json.loads((artifact_root / "07_gate_closure" / "gate_closure_report.json").read_text())
        except Exception:
            pass
        try:
            next_action_packet = json.loads((artifact_root / "07_gate_closure" / "next_action_packet.json").read_text())
        except Exception:
            pass

    return RichRunResponse(
        thread_id=thread_id,
        run_id=run_id,
        mode=summary.get("mode", "unknown"),
        workflow_name=summary.get("workflow_name", "unknown"),
        executed_steps=summary.get("executed_steps", []),
        artifact_root_virtual=summary.get("artifact_root_virtual", ""),
        artifact_root_actual=summary.get("artifact_root_actual", ""),
        project_id=project_id,
        project_name=project_name,
        primary_review_object=primary_review_object,
        input_root=input_root,
        human_gate_required=human_gate_required,
        intake_summary=intake_summary,
        fmea_precheck_summary=fmea_summary,
        rmf_precheck_summary=rmf_precheck_summary,
        dimension_summary=dimension_summary,
        human_boundary_summary=human_boundary_summary,
        final_recommended_gate=final_recommended_gate,
        provisional_gate=provisional_gate,
        provisional_only=provisional_only,
        human_gate_required_flag=human_gate_required_flag,
        human_decision=human_decision,
        gate_closure=gate_closure,
        next_action_packet=next_action_packet,
        has_closure=has_closure,
        closure_completed=has_closure,
    )


@router.get("/status/{thread_id}", response_model=RMFStatusResponse)
async def rmf_status(thread_id: str) -> RMFStatusResponse:
    """Get the latest run status for a thread."""
    summary = _get_run_summary(thread_id)
    if not summary:
        raise HTTPException(status_code=404, detail=f"No RMF run found for thread_id={thread_id}")
    artifact_root = Path(summary["artifact_root_actual"])
    return _build_status_response(thread_id, summary, artifact_root)


@router.post("/human-decision", response_model=HumanDecisionResponse)
async def rmf_human_decision(body: HumanDecisionRequest) -> HumanDecisionResponse:
    """Submit a human gate decision and trigger closure (closure-only, no step 1-7 re-run)."""
    summary = _get_run_summary(body.thread_id)
    if not summary:
        raise HTTPException(status_code=404, detail=f"No RMF run found for thread_id={body.thread_id}")

    artifact_root_actual = Path(summary["artifact_root_actual"])
    _write_human_decision(body.thread_id, summary, body)

    run_manifest_path = artifact_root_actual / "00_manifest" / "run_manifest.json"
    if run_manifest_path.exists():
        run_manifest = json.loads(run_manifest_path.read_text())
        project_profile = run_manifest.get("project_profile_path")
        input_root = run_manifest.get("input_root")
    else:
        project_profile = None
        input_root = None

    if not project_profile:
        raise HTTPException(status_code=400, detail="Cannot determine project_profile path from run manifest.")

    cmd = [
        sys.executable,
        str(_REPO_ROOT / "scripts" / "rmf_review_runner.py"),
        "--project-profile",
        project_profile,
        "--thread-id",
        body.thread_id,
        "--mode",
        "closure-only",
        "--run-id-override",
        summary["run_id"],
        "--artifact-root-override",
        str(artifact_root_actual),
    ]
    if input_root:
        cmd.extend(["--input-root", input_root])

    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(_REPO_ROOT), timeout=600)
    gate_closure_executed = result.returncode == 0

    gate_closure_report_path = str(artifact_root_actual / "07_gate_closure" / "gate_closure_report.md")
    next_action_packet_path = str(artifact_root_actual / "07_gate_closure" / "next_action_packet.json")

    return HumanDecisionResponse(
        success=gate_closure_executed,
        decision_recorded=True,
        gate_closure_executed=gate_closure_executed,
        artifact_root_actual=str(artifact_root_actual),
        gate_closure_report_path=gate_closure_report_path,
        next_action_packet_path=next_action_packet_path,
    )


@router.post("/rework", response_model=RMFStartResponse)
async def rmf_rework(body: ReworkRequest) -> RMFStartResponse:
    """Trigger a new smoke-run for a thread that has rework_required closure.

    This creates a new run in the same thread, allowing the rework loop to proceed.
    """
    summary = _get_run_summary(body.thread_id)
    if not summary:
        raise HTTPException(status_code=404, detail=f"No RMF run found for thread_id={body.thread_id}")

    artifact_root = Path(summary["artifact_root_actual"])
    run_manifest_path = artifact_root / "00_manifest" / "run_manifest.json"
    if not run_manifest_path.exists():
        raise HTTPException(status_code=400, detail="Cannot determine project_profile path from run manifest.")

    run_manifest = json.loads(run_manifest_path.read_text())
    project_profile = run_manifest.get("project_profile_path")
    input_root = run_manifest.get("input_root")

    if not project_profile:
        raise HTTPException(status_code=400, detail="Cannot determine project_profile path from run manifest.")

    # Use a new thread_id derived from the original, to avoid returning cached summary
    # Add suffix so it registers as a new run
    new_thread_id = f"{body.thread_id}-rework"

    cmd = [
        sys.executable,
        str(_REPO_ROOT / "scripts" / "rmf_review_runner.py"),
        "--project-profile",
        project_profile,
        "--thread-id",
        new_thread_id,
        "--mode",
        "smoke-run",
    ]
    if input_root:
        cmd.extend(["--input-root", input_root])

    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(_REPO_ROOT), timeout=1800)
    if result.returncode != 0:
        logger.error("Rework run failed: %s", result.stderr)
        raise HTTPException(status_code=500, detail=f"Rework run failed: {result.stderr}")

    output = json.loads(result.stdout)
    return RMFStartResponse(**output)


@router.get("/closure/{thread_id}", response_model=ClosureResponse)
async def rmf_closure(thread_id: str) -> ClosureResponse:
    """Get gate closure result and next action summary for the latest run."""
    summary = _get_run_summary(thread_id)
    if not summary:
        raise HTTPException(status_code=404, detail=f"No RMF run found for thread_id={thread_id}")

    artifact_root = Path(summary["artifact_root_actual"])
    run_id = summary["run_id"]

    has_closure = (artifact_root / "07_gate_closure" / "gate_closure_report.json").exists()
    human_decision = None
    provisional_gate = None
    provisional_only = None
    next_action: NextActionSummary | None = None
    gate_closure_report: dict | None = None
    final_gate_status = None

    if has_closure:
        try:
            gcr = json.loads((artifact_root / "07_gate_closure" / "gate_closure_report.json").read_text())
            gate_closure_report = gcr
            final_gate_status = gcr.get("final_decision")
            human_decision = gcr.get("human_decision")
            nap = gcr.get("next_action_packet")
            if nap:
                blocking_count = sum(1 for a in nap.get("actions", []) if a.get("type") == "rework")
                next_action = NextActionSummary(
                    packet_type=nap.get("packet_type"),
                    decision=nap.get("decision"),
                    description=nap.get("description"),
                    blocking_actions_count=blocking_count,
                    total_actions_count=len(nap.get("actions", [])),
                    linked_capa_ids=nap.get("linked_capa_ids", []),
                )
        except Exception:
            pass

    if (artifact_root / "05_human_boundary" / "provisional_gate_recommendation.json").exists():
        try:
            pg = json.loads((artifact_root / "05_human_boundary" / "provisional_gate_recommendation.json").read_text())
            provisional_gate = pg.get("gate")
            provisional_only = pg.get("provisional_only")
        except Exception:
            pass

    return ClosureResponse(
        thread_id=thread_id,
        run_id=run_id,
        closure_completed=has_closure,
        final_gate_status=final_gate_status,
        human_decision=human_decision,
        provisional_gate=provisional_gate,
        provisional_only=provisional_only,
        next_action=next_action,
        gate_closure_report=gate_closure_report,
    )


@router.get("/artifacts/{thread_id}", response_model=RMFArtifactsResponse)
async def rmf_artifacts(thread_id: str) -> RMFArtifactsResponse:
    """List available artifact paths and download URLs for the latest run."""
    summary = _get_run_summary(thread_id)
    if not summary:
        raise HTTPException(status_code=404, detail=f"No RMF run found for thread_id={thread_id}")
    artifact_root = Path(summary["artifact_root_actual"])
    artifacts = _artifacts_for_run(thread_id, summary, artifact_root)
    return RMFArtifactsResponse(
        thread_id=thread_id,
        run_id=summary["run_id"],
        artifact_root_actual=str(artifact_root),
        artifacts=artifacts,
    )
