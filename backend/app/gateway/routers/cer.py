"""CER Review Workflow gateway router.

Provides a REST entry layer for the CER review workbench:
  - POST   /api/cer/start              -> trigger smoke-run
  - GET    /api/cer/runs              -> list all CER thread summaries
  - GET    /api/cer/runs/{thread_id}   -> list all runs for a thread
  - GET    /api/cer/run/{thread_id}/{run_id} -> rich run detail
  - GET    /api/cer/status/{thread_id} -> latest run status / summary
  - POST   /api/cer/human-decision   -> submit human gate decision + closure
  - POST   /api/cer/rework           -> trigger rework run for rework_required
  - GET    /api/cer/closure/{thread_id} -> closure result + next action summary
  - GET    /api/cer/artifacts/{thread_id} -> artifact path summary
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
router = APIRouter(prefix="/api/cer", tags=["cer"])

_REPO_ROOT = Path(__file__).resolve().parents[4]

_ARTIFACT_STEP_MAP = [
    ("06_review_package/review_package.json", "review_package.json", "cer_review_package_agent"),
    ("06_review_package/review_package.md", "review_package.md", "cer_review_package_agent"),
    ("07_gate_closure/gate_closure_report.json", "gate_closure_report.json", "cer_gate_closure_agent"),
    ("07_gate_closure/next_action_packet.json", "next_action_packet.json", "cer_gate_closure_agent"),
    ("05_human_boundary/human_review_queue.json", "human_review_queue.json", "cer_human_boundary_agent"),
    ("05_human_boundary/provisional_gate_recommendation.json", "provisional_gate_recommendation.json", "cer_human_boundary_agent"),
    ("05_human_boundary/human_gate_decision.json", "human_gate_decision.json", "cer_human_boundary_agent"),
    ("04_cross_doc_consistency/cross_doc_consistency.json", "cross_doc_consistency.json", "cer_cross_doc_consistency_agent"),
    ("03_five_dimension/five_dimension_review.json", "five_dimension_review.json", "cer_five_dimension_agent"),
    ("02_hf_check/hf_check_report.json", "hf_check_report.json", "cer_hf_check_agent"),
    ("01_parse/cer_normalized.json", "cer_normalized.json", "cer_parse_normalize_agent"),
    ("01_parse/cross_doc_entities.json", "cross_doc_entities.json", "cer_parse_normalize_agent"),
    ("01_parse/term_map.json", "term_map.json", "cer_parse_normalize_agent"),
    ("00_manifest/run_manifest.json", "run_manifest.json", "cer_intake_agent"),
    ("00_manifest/input_inventory.json", "input_inventory.json", "cer_intake_agent"),
    ("00_manifest/missing_items_report.md", "missing_items_report.md", "cer_intake_agent"),
]


class CERStartRequest(BaseModel):
    project_profile: str = Field(..., description="Absolute path to project_profile.yaml")
    input_root: str | None = Field(None, description="Optional override for input root")
    thread_id: str | None = Field(None, description="Optional thread id (generated if not provided)")
    mode: str = Field(default="smoke-run", description="Run mode: smoke-run | closure-only")


class CERStartResponse(BaseModel):
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


class CERStatusResponse(BaseModel):
    thread_id: str
    run_id: str | None
    mode: str | None
    workflow_name: str | None
    executed_steps: list[str]
    artifact_root_virtual: str | None
    artifact_root_actual: str | None
    has_review_package: bool
    has_gate_closure_report: bool
    has_human_decision: bool
    has_human_review_queue: bool
    has_provisional_gate: bool
    has_five_dimension_review: bool
    has_hf_check: bool
    has_cross_doc_consistency: bool
    # Machine vs human distinction
    final_recommended_gate: str | None = None
    provisional_gate: str | None = None
    human_gate_required: bool | None = True
    provisional_only: bool | None = None
    # Human decision
    human_decision_value: str | None = None
    human_decision_reviewer: str | None = None
    human_decision_simulated: bool | None = None
    human_decision_date: str | None = None
    # Closure
    final_gate_status: str | None = None
    closure_completed: bool = False


class CERArtifactsResponse(BaseModel):
    thread_id: str
    run_id: str
    artifact_root_actual: str
    artifacts: list[ArtifactSummary]


class RunSummaryItem(BaseModel):
    run_id: str
    mode: str
    workflow_name: str
    executed_steps: list[str]
    artifact_root_actual: str
    updated_at: float


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


class RichRunResponse(BaseModel):
    thread_id: str
    run_id: str
    mode: str
    workflow_name: str
    executed_steps: list[str]
    artifact_root_virtual: str
    artifact_root_actual: str
    project_id: str | None = None
    input_root: str | None = None
    human_gate_required: bool = True
    # Step summaries
    intake_summary: dict | None = None
    hf_check_summary: dict | None = None
    five_dim_summary: dict | None = None
    cross_doc_summary: dict | None = None
    human_boundary_summary: dict | None = None
    review_package_summary: dict | None = None
    # P0.5 quality-hardened sub-assessments
    equivalence_assessment_summary: dict | None = None
    literature_quality_summary: dict | None = None
    # Machine recommendation
    final_recommended_gate: str | None = None
    provisional_gate: str | None = None
    provisional_only: bool | None = None
    human_gate_required_flag: bool | None = True
    # Human decision
    human_decision: dict | None = None
    # Closure
    gate_closure: dict | None = None
    next_action_packet: dict | None = None
    has_closure: bool = False
    closure_completed: bool = False


class NextActionSummary(BaseModel):
    packet_type: str | None
    decision: str | None
    description: str | None
    blocking_actions_count: int = 0
    total_actions_count: int = 0
    linked_capa_ids: list[str] = []


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


def _get_cer_threads_base() -> Path:
    from deerflow.config.paths import get_paths
    return get_paths().base_dir / "threads"


def _scan_cer_threads() -> list[str]:
    """Return all thread_ids that have CER runs."""
    base = _get_cer_threads_base()
    if not base.exists():
        return []
    threads = []
    for d in base.iterdir():
        if not d.is_dir():
            continue
        cer_path = d / "user-data" / "outputs" / "cer_review_v0"
        if cer_path.exists():
            threads.append(d.name)
    return threads


def _get_runs_for_thread(thread_id: str) -> list[RunSummaryItem]:
    from deerflow.config.paths import get_paths
    paths = get_paths()
    outputs_dir = paths.sandbox_outputs_dir(thread_id)
    cer_base = outputs_dir / "cer_review_v0"
    if not cer_base.exists():
        return []

    runs: list[RunSummaryItem] = []
    for run_dir in cer_base.iterdir():
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
    if has_closure:
        try:
            gcr = json.loads((artifact_root / "07_gate_closure" / "gate_closure_report.json").read_text())
            final_gate_status = gcr.get("final_decision")
        except Exception:
            pass
    return ThreadSummary(
        thread_id=thread_id,
        latest_run_id=latest.run_id,
        latest_mode=latest.mode,
        latest_executed_steps=latest.executed_steps,
        latest_final_recommended_gate=None,
        latest_final_gate_status=final_gate_status,
        latest_has_closure=has_closure,
        updated_at=latest.updated_at,
    )


def _build_status_response(thread_id: str, summary: dict, artifact_root: Path) -> CERStatusResponse:
    has_review_package = (artifact_root / "06_review_package" / "review_package.json").exists()
    has_gate_closure = (artifact_root / "07_gate_closure" / "gate_closure_report.json").exists()
    has_human_decision = (artifact_root / "05_human_boundary" / "human_gate_decision.json").exists()
    has_human_review_queue = (artifact_root / "05_human_boundary" / "human_review_queue.json").exists()
    has_provisional_gate = (artifact_root / "05_human_boundary" / "provisional_gate_recommendation.json").exists()
    has_five_dimension_review = (artifact_root / "03_five_dimension" / "five_dimension_review.json").exists()
    has_hf_check = (artifact_root / "02_hf_check" / "hf_check_report.json").exists()
    has_cross_doc_consistency = (artifact_root / "04_cross_doc_consistency" / "cross_doc_consistency.json").exists()

    final_recommended_gate = None
    provisional_gate = None
    if has_review_package:
        try:
            rp = json.loads((artifact_root / "06_review_package" / "review_package.json").read_text())
            final_recommended_gate = rp.get("recommended_gate")
        except Exception:
            pass
    if has_provisional_gate:
        try:
            pg = json.loads((artifact_root / "05_human_boundary" / "provisional_gate_recommendation.json").read_text())
            provisional_gate = pg.get("gate")
        except Exception:
            pass

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

    return CERStatusResponse(
        thread_id=summary["thread_id"],
        run_id=summary.get("run_id"),
        mode=summary.get("mode"),
        workflow_name=summary.get("workflow_name"),
        executed_steps=summary.get("executed_steps", []),
        artifact_root_virtual=summary.get("artifact_root_virtual"),
        artifact_root_actual=summary.get("artifact_root_actual"),
        has_review_package=has_review_package,
        has_gate_closure_report=has_gate_closure,
        has_human_decision=has_human_decision,
        has_human_review_queue=has_human_review_queue,
        has_provisional_gate=has_provisional_gate,
        has_five_dimension_review=has_five_dimension_review,
        has_hf_check=has_hf_check,
        has_cross_doc_consistency=has_cross_doc_consistency,
        final_recommended_gate=final_recommended_gate,
        provisional_gate=provisional_gate,
        human_gate_required=True,
        provisional_only=True,
        human_decision_value=human_decision_value,
        human_decision_reviewer=human_decision_reviewer,
        human_decision_simulated=human_decision_simulated,
        human_decision_date=human_decision_date,
        final_gate_status=final_gate_status,
        closure_completed=has_gate_closure,
    )


def _get_run_summary(thread_id: str) -> dict | None:
    from deerflow.config.paths import get_paths
    paths = get_paths()
    outputs_dir = paths.sandbox_outputs_dir(thread_id)
    cer_base = outputs_dir / "cer_review_v0"
    if not cer_base.exists():
        return None
    run_dirs = sorted(
        (d for d in cer_base.iterdir() if d.is_dir()),
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
    artifacts: list[ArtifactSummary] = []
    for rel_path, artifact_name, step_id in _ARTIFACT_STEP_MAP:
        full_path = artifact_root / rel_path
        if full_path.exists():
            virtual_path = f"mnt/user-data/outputs/cer_review_v0/{summary['run_id']}/artifacts/{rel_path}"
            download_url = f"/api/threads/{thread_id}/artifacts/{virtual_path}"
            artifacts.append(ArtifactSummary(
                path=str(full_path),
                artifact_name=artifact_name,
                step_id=step_id,
                download_url=download_url,
            ))
    return artifacts


@router.post("/start", response_model=CERStartResponse)
async def cer_start(body: CERStartRequest) -> CERStartResponse:
    """Trigger a CER review smoke-run."""
    existing = _get_run_summary(body.thread_id) if body.thread_id else None
    if existing:
        return CERStartResponse(
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
        str(_REPO_ROOT / "scripts" / "cer_review_runner.py"),
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
        logger.error("CER runner failed: %s", result.stderr)
        raise HTTPException(status_code=500, detail=f"CER runner failed: {result.stderr}")

    output = json.loads(result.stdout)
    return CERStartResponse(**output)


@router.get("/runs", response_model=AllRunsResponse)
async def cer_list_threads() -> AllRunsResponse:
    """List all CER thread summaries."""
    threads = _scan_cer_threads()
    summaries: list[ThreadSummary] = []
    for thread_id in threads:
        s = _get_thread_summary(thread_id)
        if s:
            summaries.append(s)
    summaries.sort(key=lambda t: t.updated_at, reverse=True)
    return AllRunsResponse(threads=summaries)


@router.get("/runs/{thread_id}", response_model=ThreadRunsResponse)
async def cer_list_runs(thread_id: str) -> ThreadRunsResponse:
    """List all runs for a specific thread."""
    runs = _get_runs_for_thread(thread_id)
    return ThreadRunsResponse(thread_id=thread_id, runs=runs)


@router.get("/run/{thread_id}/{run_id}", response_model=RichRunResponse)
async def cer_run_detail(thread_id: str, run_id: str) -> RichRunResponse:
    """Get rich detail for a specific run."""
    from deerflow.config.paths import get_paths
    paths = get_paths()
    outputs_dir = paths.sandbox_outputs_dir(thread_id)
    artifact_root = outputs_dir / "cer_review_v0" / run_id / "artifacts"

    summary_path = artifact_root / "00_manifest" / "run_summary.json"
    if not summary_path.exists():
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found for thread {thread_id}")

    summary = json.loads(summary_path.read_text())

    # Intake summary
    intake_summary = None
    run_manifest_path = artifact_root / "00_manifest" / "run_manifest.json"
    if run_manifest_path.exists():
        try:
            rm = json.loads(run_manifest_path.read_text())
            intake_summary = {
                "project_id": rm.get("project_id"),
                "input_doc_summary": rm.get("input_doc_summary", {}),
            }
        except Exception:
            pass

    # HF check summary
    hf_check_summary = None
    if (artifact_root / "02_hf_check" / "hf_check_report.json").exists():
        try:
            hf = json.loads((artifact_root / "02_hf_check" / "hf_check_report.json").read_text())
            hf_check_summary = {
                "total_checks": hf.get("total_checks"),
                "present_count": hf.get("present_count"),
                "missing_count": hf.get("missing_count"),
                "findings": hf.get("findings", []),
            }
        except Exception:
            pass

    # P0.5: Equivalence assessment (HF-005)
    equivalence_assessment_summary = None
    if (artifact_root / "02_hf_check" / "equivalence_assessment.json").exists():
        try:
            eq = json.loads((artifact_root / "02_hf_check" / "equivalence_assessment.json").read_text())
            equivalence_assessment_summary = {
                "assessment_id": eq.get("assessment_id"),
                "predicate_device": eq.get("predicate_device"),
                "overall_tier": eq.get("overall_status"),
                "dimensions_passed_count": eq.get("dimensions_passed_count"),
                "dimensions_failed_count": eq.get("dimensions_failed_count"),
                "mandatory_human_review": eq.get("mandatory_human_review"),
                "top_risks": eq.get("top_risks", []),
            }
        except Exception:
            pass

    # P0.5: Literature quality (HF-004)
    literature_quality_summary = None
    if (artifact_root / "02_hf_check" / "literature_quality.json").exists():
        try:
            lq = json.loads((artifact_root / "02_hf_check" / "literature_quality.json").read_text())
            lq_summary = lq.get("literature_quality_summary", {})
            dist = lq.get("evidence_quality_distribution", {})
            # Determine dominant tier
            tier_counts = {k: len(v) for k, v in dist.items() if isinstance(v, list)}
            dominant_tier = max(tier_counts, key=tier_counts.get) if tier_counts else "unknown"
            literature_quality_summary = {
                "literature_search_conducted": lq.get("literature_quality_summary", {}).get("total_evidence_units", 0) > 0,
                "included_studies_count": lq.get("literature_quality_summary", {}).get("total_evidence_units"),
                "high_quality_count": lq_summary.get("high_quality_count"),
                "medium_quality_count": lq_summary.get("medium_quality_count"),
                "low_quality_count": lq_summary.get("low_quality_count"),
                "very_low_quality_count": lq_summary.get("very_low_quality_count"),
                "insufficient_info_count": lq_summary.get("insufficient_info_count"),
                "dominant_tier": dominant_tier,
                "requires_human_review": lq_summary.get("requires_human_review"),
            }
        except Exception:
            pass

    # Five dimension summary
    five_dim_summary = None
    if (artifact_root / "03_five_dimension" / "five_dimension_review.json").exists():
        try:
            fd = json.loads((artifact_root / "03_five_dimension" / "five_dimension_review.json").read_text())
            five_dim_summary = {
                "dimensions": {k: {"status": v.get("status"), "label": v.get("label"), "requires_human_review": v.get("requires_human_review")} for k, v in fd.get("dimensions", {}).items()},
            }
        except Exception:
            pass

    # Cross-doc summary
    cross_doc_summary = None
    if (artifact_root / "04_cross_doc_consistency" / "cross_doc_consistency.json").exists():
        try:
            cd = json.loads((artifact_root / "04_cross_doc_consistency" / "cross_doc_consistency.json").read_text())
            cross_doc_summary = {
                "total_checks": cd.get("total_checks"),
                "conflicts": cd.get("conflicts", []),
                "pmcf_cer_mapping": cd.get("pmcf_cer_mapping", []),
            }
        except Exception:
            pass

    # Human boundary summary
    human_boundary_summary = None
    if (artifact_root / "05_human_boundary" / "human_review_queue.json").exists():
        try:
            hq = json.loads((artifact_root / "05_human_boundary" / "human_review_queue.json").read_text())
            human_boundary_summary = {
                "item_count": len(hq.get("items", [])),
                "items": hq.get("items", []),
                "recommended_gate": hq.get("recommended_gate"),
            }
        except Exception:
            pass

    # Review package summary
    review_package_summary = None
    if (artifact_root / "06_review_package" / "review_package.json").exists():
        try:
            rp = json.loads((artifact_root / "06_review_package" / "review_package.json").read_text())
            review_package_summary = rp.get("summary")
        except Exception:
            pass

    # Provisional gate
    provisional_gate = None
    provisional_only = None
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

    # Gate closure
    gate_closure = None
    next_action_packet = None
    has_closure = False
    if (artifact_root / "07_gate_closure" / "gate_closure_report.json").exists():
        try:
            gate_closure = json.loads((artifact_root / "07_gate_closure" / "gate_closure_report.json").read_text())
            has_closure = True
        except Exception:
            pass
    if (artifact_root / "07_gate_closure" / "next_action_packet.json").exists():
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
        project_id=intake_summary.get("project_id") if intake_summary else None,
        human_gate_required=True,
        intake_summary=intake_summary,
        hf_check_summary=hf_check_summary,
        five_dim_summary=five_dim_summary,
        cross_doc_summary=cross_doc_summary,
        human_boundary_summary=human_boundary_summary,
        review_package_summary=review_package_summary,
        final_recommended_gate=review_package_summary.get("recommended_gate") if review_package_summary else None,
        provisional_gate=provisional_gate,
        provisional_only=provisional_only,
        human_gate_required_flag=True,
        human_decision=human_decision,
        gate_closure=gate_closure,
        next_action_packet=next_action_packet,
        has_closure=has_closure,
        closure_completed=has_closure,
        equivalence_assessment_summary=equivalence_assessment_summary,
        literature_quality_summary=literature_quality_summary,
    )


@router.get("/status/{thread_id}", response_model=CERStatusResponse)
async def cer_status(thread_id: str) -> CERStatusResponse:
    """Get latest run status for a thread."""
    summary = _get_run_summary(thread_id)
    if not summary:
        raise HTTPException(status_code=404, detail=f"No CER run found for thread_id={thread_id}")
    artifact_root = Path(summary["artifact_root_actual"])
    return _build_status_response(thread_id, summary, artifact_root)


@router.post("/human-decision", response_model=HumanDecisionResponse)
async def cer_human_decision(body: HumanDecisionRequest) -> HumanDecisionResponse:
    """Submit human gate decision and trigger closure-only run.

    This does NOT overwrite any prior human decision - if one exists, it is preserved.
    """
    summary = _get_run_summary(body.thread_id)
    if not summary:
        raise HTTPException(status_code=404, detail=f"No CER run found for thread_id={body.thread_id}")

    artifact_root_actual = Path(summary["artifact_root_actual"])
    decision_path = artifact_root_actual / "05_human_boundary" / "human_gate_decision.json"

    # If human decision already exists, do NOT overwrite - closure-only only
    already_decided = decision_path.exists()
    if already_decided:
        logger.info("Human decision already recorded for thread_id=%s, skipping write", body.thread_id)
    else:
        _write_human_decision(body.thread_id, summary, body)

    # Get project profile path from run manifest
    run_manifest_path = artifact_root_actual / "00_manifest" / "run_manifest.json"
    project_profile = None
    input_root = None
    if run_manifest_path.exists():
        try:
            run_manifest = json.loads(run_manifest_path.read_text())
            project_profile = run_manifest.get("project_profile_path")
            input_root = run_manifest.get("input_root")
        except Exception:
            pass

    if not project_profile:
        raise HTTPException(status_code=400, detail="Cannot determine project_profile path from run manifest.")

    cmd = [
        sys.executable,
        str(_REPO_ROOT / "scripts" / "cer_review_runner.py"),
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

    gate_closure_report_path = str(artifact_root_actual / "07_gate_closure" / "gate_closure_report.json")
    next_action_packet_path = str(artifact_root_actual / "07_gate_closure" / "next_action_packet.json")

    return HumanDecisionResponse(
        success=gate_closure_executed,
        decision_recorded=not already_decided,
        gate_closure_executed=gate_closure_executed,
        artifact_root_actual=str(artifact_root_actual),
        gate_closure_report_path=gate_closure_report_path,
        next_action_packet_path=next_action_packet_path,
    )


@router.post("/rework", response_model=CERStartResponse)
async def cer_rework(body: ReworkRequest) -> CERStartResponse:
    """Trigger a new smoke-run for a thread that has rework_required closure."""
    summary = _get_run_summary(body.thread_id)
    if not summary:
        raise HTTPException(status_code=404, detail=f"No CER run found for thread_id={body.thread_id}")

    artifact_root = Path(summary["artifact_root_actual"])
    run_manifest_path = artifact_root / "00_manifest" / "run_manifest.json"
    if not run_manifest_path.exists():
        raise HTTPException(status_code=400, detail="Cannot determine project_profile path from run manifest.")

    run_manifest = json.loads(run_manifest_path.read_text())
    project_profile = run_manifest.get("project_profile_path")
    input_root = run_manifest.get("input_root")

    if not project_profile:
        raise HTTPException(status_code=400, detail="Cannot determine project_profile path from run manifest.")

    new_thread_id = f"{body.thread_id}-rework"

    cmd = [
        sys.executable,
        str(_REPO_ROOT / "scripts" / "cer_review_runner.py"),
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
    return CERStartResponse(**output)


@router.get("/closure/{thread_id}", response_model=ClosureResponse)
async def cer_closure(thread_id: str) -> ClosureResponse:
    """Get gate closure result and next action summary for the latest run."""
    summary = _get_run_summary(thread_id)
    if not summary:
        raise HTTPException(status_code=404, detail=f"No CER run found for thread_id={thread_id}")

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
            nap = gcr.get("next_action")
            if nap:
                next_action = NextActionSummary(
                    packet_type=nap.get("type"),
                    decision=nap.get("type"),
                    description=nap.get("description"),
                    blocking_actions_count=1 if nap.get("blocking") else 0,
                    total_actions_count=1,
                    linked_capa_ids=[],
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


@router.get("/artifacts/{thread_id}", response_model=CERArtifactsResponse)
async def cer_artifacts(thread_id: str) -> CERArtifactsResponse:
    """List available artifact paths and download URLs for the latest run."""
    summary = _get_run_summary(thread_id)
    if not summary:
        raise HTTPException(status_code=404, detail=f"No CER run found for thread_id={thread_id}")
    artifact_root = Path(summary["artifact_root_actual"])
    artifacts = _artifacts_for_run(thread_id, summary, artifact_root)
    return CERArtifactsResponse(
        thread_id=thread_id,
        run_id=summary["run_id"],
        artifact_root_actual=str(artifact_root),
        artifacts=artifacts,
    )
