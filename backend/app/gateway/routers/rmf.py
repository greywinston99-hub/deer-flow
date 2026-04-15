"""RMF Review Workflow gateway router.

Provides a minimal REST entry layer for the RMF review runner:
  - POST /api/rmf/start          -> trigger smoke-run
  - GET  /api/rmf/status/{thread_id} -> run summary / status
  - POST /api/rmf/human-decision -> submit human gate decision + closure
  - GET  /api/rmf/artifacts/{thread_id} -> artifact path summary

All endpoints operate on the existing RMFReviewRunner via subprocess,
reusing the same artifact directory structure already served by the
artifacts router.
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

# ---------------------------------------------------------------------------
# Repo root (backend/ is two levels below repo root)
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[4]


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class RMFStartRequest(BaseModel):
    project_profile: str = Field(..., description="Absolute path to project_profile.yaml")
    input_root: str | None = Field(None, description="Optional override for input root")
    thread_id: str | None = Field(None, description="Optional thread id (generated if not provided)")
    mode: str = Field(default="smoke-run", description="Run mode: smoke-run (only)")


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
    final_recommended_gate: str | None
    final_gate_status: str | None


class RMFArtifactsResponse(BaseModel):
    thread_id: str
    artifact_root_actual: str
    artifacts: list[ArtifactSummary]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_run_summary(thread_id: str) -> dict | None:
    """Read run_summary.json from the latest run in the thread's RMF outputs."""
    from deerflow.config.paths import get_paths

    paths = get_paths()
    outputs_dir = paths.sandbox_outputs_dir(thread_id)
    rmf_base = outputs_dir / "rmf_review_v1_1"

    if not rmf_base.exists():
        return None

    # Find the latest run directory by modification time
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
        "decision_date": "2026-04-15",  # Caller can override via rationale prefix
        "rationale": decision.rationale,
        "linked_review_items": decision.linked_review_items,
        "linked_capa_ids": decision.linked_capa_ids,
        "simulated": False,
    }
    decision_path.write_text(json.dumps(decision_record, indent=2, ensure_ascii=False))


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/start", response_model=RMFStartResponse)
async def rmf_start(body: RMFStartRequest) -> RMFStartResponse:
    """Trigger an RMF review smoke-run.

    Runs the RMFReviewRunner as a subprocess and returns the result.
    If artifacts already exist for the given thread_id, returns the
    existing summary instead of re-running.
    """
    # Check if a run already exists for this thread
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

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=str(_REPO_ROOT),
        timeout=1800,  # 30 min max for full smoke-run
    )

    if result.returncode != 0:
        logger.error("RMF runner failed: %s", result.stderr)
        raise HTTPException(
            status_code=500,
            detail=f"RMF runner failed: {result.stderr}",
        )

    output = json.loads(result.stdout)
    return RMFStartResponse(**output)


@router.get("/status/{thread_id}", response_model=RMFStatusResponse)
async def rmf_status(thread_id: str) -> RMFStatusResponse:
    """Get the status and artifact summary for an RMF run."""
    summary = _get_run_summary(thread_id)

    if not summary:
        raise HTTPException(
            status_code=404,
            detail=f"No RMF run found for thread_id={thread_id}",
        )

    artifact_root_actual = Path(summary["artifact_root_actual"])
    has_final_report = (artifact_root_actual / "06_final" / "final_report.md").exists()
    has_gate_closure = (artifact_root_actual / "07_gate_closure" / "gate_closure_report.json").exists()
    has_human_decision = (artifact_root_actual / "05_human_boundary" / "human_gate_decision.json").exists()

    final_recommended_gate = None
    final_gate_status = None

    if has_gate_closure:
        gcr = json.loads((artifact_root_actual / "07_gate_closure" / "gate_closure_report.json").read_text())
        final_gate_status = gcr.get("final_decision")

    if has_final_report:
        final_json = artifact_root_actual / "06_final" / "final_report.json"
        if final_json.exists():
            fr = json.loads(final_json.read_text())
            final_recommended_gate = fr.get("gate_recommendation", {}).get("recommended_gate")

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
        final_recommended_gate=final_recommended_gate,
        final_gate_status=final_gate_status,
    )


@router.post("/human-decision", response_model=HumanDecisionResponse)
async def rmf_human_decision(body: HumanDecisionRequest) -> HumanDecisionResponse:
    """Submit a human gate decision and trigger gate closure.

    Writes human_gate_decision.json, then re-runs the RMF runner
    to produce the gate_closure_report and next_action_packet.
    """
    summary = _get_run_summary(body.thread_id)
    if not summary:
        raise HTTPException(
            status_code=404,
            detail=f"No RMF run found for thread_id={body.thread_id}",
        )

    _write_human_decision(body.thread_id, summary, body)

    # Re-run the full runner to execute gate closure step
    artifact_root_actual = Path(summary["artifact_root_actual"])

    # Determine project_profile path from the run_manifest
    run_manifest_path = artifact_root_actual / "00_manifest" / "run_manifest.json"
    if run_manifest_path.exists():
        run_manifest = json.loads(run_manifest_path.read_text())
        project_profile = run_manifest.get("project_profile_path")
        input_root = run_manifest.get("input_root")
    else:
        project_profile = None
        input_root = None

    if not project_profile:
        raise HTTPException(
            status_code=400,
            detail="Cannot determine project_profile path from run manifest. Please re-run with a run that includes the manifest.",
        )

    cmd = [
        sys.executable,
        str(_REPO_ROOT / "scripts" / "rmf_review_runner.py"),
        "--project-profile",
        project_profile,
        "--thread-id",
        body.thread_id,
        "--mode",
        "smoke-run",
    ]

    if input_root:
        cmd.extend(["--input-root", input_root])

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=str(_REPO_ROOT),
        timeout=1800,
    )

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


@router.get("/artifacts/{thread_id}", response_model=RMFArtifactsResponse)
async def rmf_artifacts(thread_id: str) -> RMFArtifactsResponse:
    """List available artifact paths and download URLs for an RMF run."""
    summary = _get_run_summary(thread_id)

    if not summary:
        raise HTTPException(
            status_code=404,
            detail=f"No RMF run found for thread_id={thread_id}",
        )

    artifact_root_actual = Path(summary["artifact_root_actual"])
    artifacts: list[ArtifactSummary] = []

    # Key artifacts to expose
    key_artifacts = [
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
        ("03_rmf_precheck/rmf_precheck_report.json", "rmf_precheck_report.json", "rmf_precheck_agent"),
        ("02_fmea_precheck/fmea_precheck_report.json", "fmea_precheck_report.json", "fmea_precheck_agent"),
        ("01_parse/rmf_normalized.json", "rmf_normalized.json", "rmf_parse_normalize_agent"),
        ("01_parse/fmea_normalized.json", "fmea_normalized.json", "rmf_parse_normalize_agent"),
        ("00_manifest/run_manifest.json", "run_manifest.json", "rmf_intake_agent"),
        ("00_manifest/input_inventory.json", "input_inventory.json", "rmf_intake_agent"),
        ("00_manifest/missing_items_report.md", "missing_items_report.md", "rmf_intake_agent"),
    ]

    for rel_path, artifact_name, step_id in key_artifacts:
        full_path = artifact_root_actual / rel_path
        if full_path.exists():
            # Virtual path for the artifacts router
            # artifact_root_virtual is like /mnt/user-data/outputs/rmf_review_v1_1/{run_id}/artifacts
            virtual_path = f"mnt/user-data/outputs/rmf_review_v1_1/{summary['run_id']}/artifacts/{rel_path}"
            download_url = f"/api/threads/{thread_id}/artifacts/{virtual_path}"
            artifacts.append(
                ArtifactSummary(
                    path=str(full_path),
                    artifact_name=artifact_name,
                    step_id=step_id,
                    download_url=download_url,
                )
            )

    return RMFArtifactsResponse(
        thread_id=thread_id,
        artifact_root_actual=str(artifact_root_actual),
        artifacts=artifacts,
    )
