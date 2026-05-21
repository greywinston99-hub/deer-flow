"""CER Integration API — RMF × CER Cross-Document Integration View.

Provides read-only RMF × CER cross-document integration endpoints:
  - POST /api/cer-review/{project_id}/integration/run     -> trigger integration run
  - GET  /api/cer-review/{project_id}/integration/status  -> integration run status
  - GET  /api/cer-review/{project_id}/integration/linkage  -> RMF-CER linkage matrix
  - GET  /api/cer-review/{project_id}/integration/findings -> consistency findings
  - GET  /api/cer-review/{project_id}/integration/gaps    -> evidence gap report
  - GET  /api/cer-review/{project_id}/integration/knowledge-suggestions -> knowledge suggestions
  - POST /api/cer-review/{project_id}/integration/review-mark -> submit reviewer mark

This module is reviewer-assistive only:
  - Does NOT automatically decide RMF acceptability
  - Does NOT automatically decide CER acceptability
  - Does NOT alter Gate 1 / Gate 3 decisions
  - Does NOT write to Decision Ledger
  - Does NOT alter BRR matrix semantics

Frozen baseline: RMF_CER_INTEGRATION_VIEW_P1
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel, Field

from deerflow.runtime.cer_review.auth import (
    CERAuthContext,
    CERRole,
)
from deerflow.runtime.cer_review.auth.rbac_context import (
    get_cer_auth_with_gate_role,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/cer-review", tags=["cer-integration"])

CER_ARTIFACTS_ROOT = Path("/Users/winstonwei/Documents/Playground/deer-flow/artifacts/cer")
SKILL_PROMPTS_ROOT = Path("/Users/winstonwei/Documents/Playground/deer-flow/prompts/cer/integration")

# ── Integration stage definitions ──────────────────────────────────────────────

INTEGRATION_STAGES = [
    "rmf_cer_linkage",
    "intended_purpose_consistency",
    "benefit_risk_crosscheck",
    "residual_risk_crosscheck",
    "ifu_risk_information",
    "pms_pmcf_rmf_linkage",
    "knowledge_suggestion",
    "integration_qa",
]

AGENT_NAME_MAP = {
    "rmf_cer_linkage": "rmf_cer_linkage_agent",
    "intended_purpose_consistency": "intended_purpose_consistency_agent",
    "benefit_risk_crosscheck": "benefit_risk_crosscheck_agent",
    "residual_risk_crosscheck": "residual_risk_crosscheck_agent",
    "ifu_risk_information": "ifu_risk_information_agent",
    "pms_pmcf_rmf_linkage": "pms_pmcf_rmf_linkage_agent",
    "knowledge_suggestion": "knowledge_suggestion_agent",
    "integration_qa": "integration_qa_agent",
}

# ── Pydantic Models ────────────────────────────────────────────────────────────


class IntegrationRunRequest(BaseModel):
    """Request to trigger an integration run."""

    run_id: str | None = Field(
        None,
        description="Optional run_id to scope artifacts. Defaults to latest run.",
    )
    force_rerun: bool = Field(
        False,
        description="If true, re-run even if outputs already exist.",
    )


class IntegrationRunResponse(BaseModel):
    """Response for triggering an integration run."""

    project_id: str
    run_id: str | None
    integration_run_id: str | None
    stages_triggered: list[str]
    status: str
    message: str


class IntegrationStatusResponse(BaseModel):
    """Response for integration status."""

    project_id: str
    integration_run_id: str | None
    status: str  # not_started | running | completed | failed
    stages: dict[str, str]  # stage -> status
    started_at: str | None
    completed_at: str | None
    errors: list[str]


class LinkageMatrixItem(BaseModel):
    """A single linkage entry in the RMF-CER matrix."""

    linkage_id: str
    cer_element: str
    rmf_element: str
    ifu_element: str | None
    linkage_type: str
    consistency_status: str  # consistent | inconsistent | needs_review | historical_incomplete | unresolved_gap
    confidence: float | None
    requires_human_review: bool
    source_artifact_path: str | None
    notes: str | None = None


class IntegrationLinkageResponse(BaseModel):
    """Response for RMF-CER linkage matrix."""

    project_id: str
    integration_run_id: str | None
    generated_at: str
    total_linkages: int
    by_type: dict[str, int]
    by_status: dict[str, int]
    linkages: list[dict[str, Any]]


class ConsistencyFindingItem(BaseModel):
    """A single consistency finding."""

    finding_id: str
    category: str  # intended_purpose | benefit_risk | residual_risk | ifu_risk | pms_pmcf | finding_rmf | knowledge_suggestion
    finding_type: str  # evidence_fact | agent_observation | unresolved_gap | historical_incomplete
    title: str
    description: str
    severity: str | None  # high | medium | low | null
    source_artifact_path: str | None
    confidence: float | None
    requires_human_review: bool
    reviewer_mark: str | None = None  # confirmed | needs_follow_up | dismissed | parked


class IntegrationFindingsResponse(BaseModel):
    """Response for consistency findings."""

    project_id: str
    integration_run_id: str | None
    generated_at: str
    total_findings: int
    by_category: dict[str, int]
    by_type: dict[str, int]
    findings: list[dict[str, Any]]


class GapItem(BaseModel):
    """A single evidence gap entry."""

    gap_id: str
    gap_type: str  # missing_artifact | incomplete_data | historical_incomplete | unresolved_linkage
    topic: str
    description: str
    impacted_linkages: list[str]
    source_hint: str | None
    requires_human_review: bool
    reviewer_mark: str | None = None


class IntegrationGapsResponse(BaseModel):
    """Response for evidence gap report."""

    project_id: str
    integration_run_id: str | None
    generated_at: str
    total_gaps: int
    gaps: list[dict[str, Any]]


class KnowledgeSuggestionItem(BaseModel):
    """A single knowledge asset suggestion."""

    suggestion_id: str
    asset_type: str
    suggested_content: str
    source_artifact_path: str
    rationale: str
    confidence: float | None
    requires_human_review: bool
    reviewer_mark: str | None = None


class IntegrationKnowledgeSuggestionsResponse(BaseModel):
    """Response for knowledge suggestions."""

    project_id: str
    integration_run_id: str | None
    generated_at: str
    total_suggestions: int
    by_type: dict[str, int]
    suggestions: list[dict[str, Any]]


class ReviewMarkRequest(BaseModel):
    """Request to submit a reviewer mark on an integration item."""

    item_id: str = Field(..., description="ID of the item being marked")
    item_type: str = Field(
        ...,
        pattern="^(linkage|finding|gap|suggestion)$",
        description="Type of item: linkage, finding, gap, or suggestion",
    )
    mark: str = Field(
        ...,
        pattern="^(confirmed|needs_follow_up|dismissed|parked)$",
        description="Reviewer mark: confirmed, needs_follow_up, dismissed, or parked",
    )
    notes: str | None = Field(None, description="Optional reviewer notes")


class ReviewMarkResponse(BaseModel):
    """Response for review mark submission."""

    project_id: str
    item_id: str
    item_type: str
    mark: str
    marked_at: str
    marked_by: str | None


# ── Artifact Resolution Helpers ───────────────────────────────────────────────


def _resolve_artifact_path(
    project_root: Path,
    relative_path: str,
) -> Path | None:
    """Resolve a relative artifact path with physical validation.

    Follows Scope B resolver requirement:
    - Resolve using manifest + metadata + physical path validation
    - Do not rely on UI round_id alone
    - If artifact path is missing, mark as missing / historical incomplete
    """
    candidate = project_root / relative_path
    if candidate.exists() and candidate.is_file():
        return candidate
    return None


def _read_artifact_json(project_root: Path, relative_path: str) -> dict[str, Any] | None:
    """Read a JSON artifact, returning None if missing."""
    path = _resolve_artifact_path(project_root, relative_path)
    if path is None:
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _read_artifact_text(project_root: Path, relative_path: str) -> str | None:
    """Read a text artifact, returning None if missing."""
    path = _resolve_artifact_path(project_root, relative_path)
    if path is None:
        return None
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None


def _discover_artifacts(project_root: Path) -> dict[str, Any]:
    """Discover all available artifacts for a project.

    Returns a manifest of available artifacts grouped by category.
    """
    artifacts: dict[str, Any] = {
        "available": [],
        "missing": [],
        "historical_incomplete": [],
    }

    # Check intake artifacts
    intake_dir = project_root / "intake"
    if intake_dir.exists():
        for fname in ["intake_state.json", "locked_evidence_pack_manifest.json",
                       "human_intake_gate_decision.json", "classification_output.json"]:
            fpath = intake_dir / fname
            if fpath.exists():
                artifacts["available"].append(f"intake/{fname}")
            else:
                artifacts["missing"].append(f"intake/{fname}")

    # Check governance artifacts
    gov_dir = project_root / "governance"
    if gov_dir.exists():
        for fname in ["decision_ledger_entry.json", "state_transition_log.jsonl"]:
            fpath = gov_dir / fname
            if fpath.exists():
                artifacts["available"].append(f"governance/{fname}")

    # Check rounds
    for round_dir in sorted(project_root.glob("round_*")):
        if not round_dir.is_dir():
            continue
        round_id = round_dir.name
        artifacts_dir = round_dir / "artifacts"
        if not artifacts_dir.exists():
            continue

        for lane_dir in sorted(artifacts_dir.glob("*")):
            if not lane_dir.is_dir():
                continue
            lane_id = lane_dir.name
            for fpath in sorted(lane_dir.glob("*")):
                if fpath.is_file():
                    rel = f"{round_id}/artifacts/{lane_id}/{fpath.name}"
                    artifacts["available"].append(rel)

    # Check knowledge store
    ks_dir = project_root / "knowledge_store"
    if ks_dir.exists():
        for subdir in ["human", "machine_assets"]:
            kd = ks_dir / subdir
            if kd.exists():
                for fpath in sorted(kd.rglob("*")):
                    if fpath.is_file():
                        artifacts["available"].append(f"knowledge_store/{subdir}/{fpath.name}")

    return artifacts


def _build_project_context(project_root: Path) -> dict[str, Any]:
    """Build project context by reading available artifacts.

    Returns structured context for LLM agents including:
    - Project profile (intended purpose, indications, device info)
    - Available artifact manifest
    - Key artifact contents
    """
    context: dict[str, Any] = {
        "artifact_discovery": _discover_artifacts(project_root),
        "project_profile": None,
        "intake": {},
        "cer_artifacts": {},
        "knowledge_assets": [],
        "governance": {},
    }

    # Read project profile
    profile_paths = [
        "project_profile.yaml",
        "project_profile_CER_PJT_0001.yaml",
        "project_profile_CER_PJT_0002.yaml",
    ]
    for p in profile_paths:
        pp = _read_artifact_json(project_root, p)
        if pp is not None:
            context["project_profile"] = pp
            break
        # Try as YAML (project profile is often YAML)
        yaml_path = project_root / p.replace(".json", ".yaml")
        if yaml_path.exists():
            try:
                import yaml
                with open(yaml_path, encoding="utf-8") as f:
                    context["project_profile"] = yaml.safe_load(f)
                    break
            except Exception:
                pass

    # Read intake artifacts
    intake_data = _read_artifact_json(project_root, "intake/intake_state.json")
    if intake_data:
        context["intake"]["state"] = intake_data

    locked_pack = _read_artifact_json(project_root, "intake/locked_evidence_pack_manifest.json")
    if locked_pack:
        context["intake"]["locked_pack"] = locked_pack

    classification = _read_artifact_json(project_root, "intake/classification_output.json")
    if classification:
        context["intake"]["classification"] = classification

    # Read governance
    ledger = _read_artifact_json(project_root, "governance/decision_ledger_entry.json")
    if ledger:
        context["governance"]["ledger_entry"] = ledger

    # Read latest round artifacts
    round_dirs = sorted([d for d in project_root.glob("round_*") if d.is_dir()])
    if round_dirs:
        latest_round = round_dirs[-1].name
        round_manifest = _read_artifact_json(
            project_root, f"{latest_round}/artifacts/00_manifest/run_manifest.json"
        )
        if round_manifest:
            context["cer_artifacts"]["round_manifest"] = round_manifest

        # Read lane artifacts
        lanes_dir = project_root / latest_round / "artifacts"
        if lanes_dir.exists():
            for lane_file in lanes_dir.glob("*/*.json"):
                key = f"{lane_file.parent.name}/{lane_file.name}"
                data = json.loads(lane_file.read_text(encoding="utf-8"))
                context["cer_artifacts"][key] = data

    # Read knowledge store machine assets
    ks_dir = project_root / "knowledge_store" / "machine_assets"
    if ks_dir.exists():
        for fpath in sorted(ks_dir.glob("*.json")):
            try:
                data = json.loads(fpath.read_text(encoding="utf-8"))
                context["knowledge_assets"].append({
                    "filename": fpath.name,
                    "data": data,
                })
            except (json.JSONDecodeError, OSError):
                pass

    return context


# ── LLM Invocation ─────────────────────────────────────────────────────────────


def _load_skill_prompt(stage: str) -> str | None:
    """Load skill prompt for a given stage."""
    agent_name = AGENT_NAME_MAP.get(stage)
    if not agent_name:
        return None
    skill_file = f"{agent_name}.md"
    skill_path = SKILL_PROMPTS_ROOT / skill_file
    if not skill_path.exists():
        logger.warning(f"Skill prompt not found: {skill_path}")
        return None
    return skill_path.read_text(encoding="utf-8")


def _invoke_llm_agent(
    stage: str,
    context: dict[str, Any],
    integration_run_id: str,
    model_name: str | None = None,
) -> dict[str, Any]:
    """Invoke a single integration LLM agent via CERLLMInvoker.

    Returns agent output dict with _meta fields populated.
    """
    prompt = _load_skill_prompt(stage)
    if prompt is None:
        return {
            "_meta": {
                "agent_id": AGENT_NAME_MAP.get(stage, stage),
                "execution_mode": "direct_llm",
                "invoked_at": datetime.now(timezone.utc).isoformat(),
                "model": model_name or "unknown",
                "skill_file": f"{AGENT_NAME_MAP.get(stage, stage)}.md",
                "stage_name": stage,
                "invocation_method": "cerllminvoker",
                "status": "skipped",
                "reason": "skill_prompt_not_found",
            },
            "status": "skipped",
            "reason": "skill_prompt_not_found",
        }

    # Build messages
    context_json = json.dumps(context, indent=2, ensure_ascii=False)
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": f"Project integration context:\n```json\n{context_json}\n```"},
    ]

    # Try CERLLMInvoker
    try:
        from deerflow.runtime.cer_review.llm_invoker import CERLLMInvoker

        # Get LLM client
        from deerflow.models import create_chat_model
        from deerflow.config import get_app_config

        config = get_app_config()
        llm = create_chat_model(
            config.models[0].name if config.models else "claude",
            thinking_enabled=False,
        )
        invoker = CERLLMInvoker(llm)
        outcome = invoker.invoke(
            agent_name=f"integration_{stage}",
            messages=messages,
            extract_json=True,
            run_id=integration_run_id,
        )

        # Extract output from last invocation result
        invocation_output: str | dict | None = None
        if outcome.invocation_results:
            last = outcome.invocation_results[-1]
            invocation_output = last.parsed_output if last.parsed_output else last.raw_output

        result: dict[str, Any] = {
            "_meta": {
                "agent_id": AGENT_NAME_MAP.get(stage, stage),
                "execution_mode": "cerllminvoker",
                "invoked_at": datetime.now(timezone.utc).isoformat(),
                "model": model_name or getattr(llm, "model_name", "unknown"),
                "skill_file": f"{AGENT_NAME_MAP.get(stage, stage)}.md",
                "stage_name": stage,
                "invocation_method": "cerllminvoker",
                "status": outcome.final_status,
                "error": outcome.final_error,
            },
            "status": outcome.final_status,
        }

        if outcome.eventual_success and invocation_output:
            if isinstance(invocation_output, dict):
                result["data"] = invocation_output
            else:
                try:
                    result["data"] = json.loads(invocation_output)
                except json.JSONDecodeError:
                    result["data"] = {"raw_output": invocation_output}

        return result

    except Exception as e:
        logger.exception(f"LLM invocation failed for stage {stage}")
        return {
            "_meta": {
                "agent_id": AGENT_NAME_MAP.get(stage, stage),
                "execution_mode": "direct_llm",
                "invoked_at": datetime.now(timezone.utc).isoformat(),
                "model": model_name or "unknown",
                "skill_file": f"{AGENT_NAME_MAP.get(stage, stage)}.md",
                "stage_name": stage,
                "invocation_method": "cerllminvoker",
                "status": "error",
                "error": str(e),
            },
            "status": "error",
            "error": str(e),
        }


# ── Integration State ───────────────────────────────────────────────────────────


INTEGRATION_STATE_FILE = "integration/integration_state.json"


def _read_integration_state(project_root: Path) -> dict[str, Any]:
    """Read existing integration state, or return default."""
    state_path = project_root / INTEGRATION_STATE_FILE
    if state_path.exists():
        try:
            return json.loads(state_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {
        "integration_run_id": None,
        "status": "not_started",
        "stages": {s: "pending" for s in INTEGRATION_STAGES},
        "started_at": None,
        "completed_at": None,
        "errors": [],
        "outputs": {},
    }


def _write_integration_state(project_root: Path, state: dict[str, Any]) -> None:
    """Write integration state atomically."""
    state_path = project_root / INTEGRATION_STATE_FILE
    state_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = state_path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp_path.replace(state_path)


# ── Integration Output Writers ──────────────────────────────────────────────────


def _write_integration_output(project_root: Path, stage: str, data: dict[str, Any]) -> None:
    """Write integration stage output to artifacts/cer/{project_id}/integration/."""
    output_dir = project_root / "integration"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Write individual stage output
    stage_file = output_dir / f"{stage}_output.json"
    stage_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _get_agent_data(stage_file: Path) -> dict[str, Any]:
    """Load agent output file and return the inner data dict.

    The output file has structure: {"_meta":..., "status":..., "data": {...}}
    We want the inner "data" dict.
    """
    if not stage_file.exists():
        return {}
    try:
        parsed = json.loads(stage_file.read_text(encoding="utf-8"))
        # If output has inner "data" dict, use it; otherwise use top-level
        if isinstance(parsed, dict) and "data" in parsed and isinstance(parsed["data"], dict):
            return parsed["data"]
        return parsed
    except (json.JSONDecodeError, OSError):
        return {}


def _aggregate_linkage_matrix(project_root: Path) -> dict[str, Any]:
    """Aggregate all stage outputs into the linkage matrix."""
    output_dir = project_root / "integration"
    linkage_data = {
        "linkages": [],
        "by_type": {},
        "by_status": {},
    }

    # Collect from each stage that has linkage-relevant output
    for stage in INTEGRATION_STAGES:
        stage_file = output_dir / f"{stage}_output.json"
        data = _get_agent_data(stage_file)
        if not data:
            continue
        if "linkages" in data:
            linkage_data["linkages"].extend(data["linkages"])
        if "by_type" in data:
            for k, v in data["by_type"].items():
                # Agent output: {"intended_purpose": {"count": 2, "linkage_ids": [...], ...}}
                if isinstance(v, dict) and "count" in v:
                    linkage_data["by_type"][k] = linkage_data["by_type"].get(k, 0) + v["count"]
                elif isinstance(v, int):
                    linkage_data["by_type"][k] = linkage_data["by_type"].get(k, 0) + v
        if "by_status" in data:
            for k, v in data["by_status"].items():
                # Agent output: {"consistent": {"count": 4, "linkage_ids": [...]}}
                if isinstance(v, dict) and "count" in v:
                    linkage_data["by_status"][k] = linkage_data["by_status"].get(k, 0) + v["count"]
                elif isinstance(v, int):
                    linkage_data["by_status"][k] = linkage_data["by_status"].get(k, 0) + v

    return linkage_data


def _aggregate_findings(project_root: Path) -> dict[str, Any]:
    """Aggregate all findings from stage outputs."""
    output_dir = project_root / "integration"
    all_findings = []
    by_category: dict[str, int] = {}
    by_type: dict[str, int] = {}

    for stage in INTEGRATION_STAGES:
        stage_file = output_dir / f"{stage}_output.json"
        data = _get_agent_data(stage_file)
        if not data:
            continue
        findings_key = None
        for k in ["findings", "finding_items", "consistency_findings", "observations"]:
            if k in data:
                findings_key = k
                break
        if findings_key:
            for f in data[findings_key]:
                f["_source_stage"] = stage
                all_findings.append(f)
                cat = f.get("category", "unknown")
                by_category[cat] = by_category.get(cat, 0) + 1
                ftype = f.get("finding_type", f.get("type", "unknown"))
                by_type[ftype] = by_type.get(ftype, 0) + 1

    return {
        "findings": all_findings,
        "by_category": by_category,
        "by_type": by_type,
    }


def _aggregate_gaps(project_root: Path) -> dict[str, Any]:
    """Aggregate evidence gaps from stage outputs."""
    output_dir = project_root / "integration"
    all_gaps = []

    for stage in INTEGRATION_STAGES:
        stage_file = output_dir / f"{stage}_output.json"
        data = _get_agent_data(stage_file)
        if not data:
            continue
        for k in ["gaps", "evidence_gaps", "missing_items", "unresolved_gaps"]:
            if k in data:
                for g in data[k]:
                    g["_source_stage"] = stage
                    all_gaps.append(g)

    return {"gaps": all_gaps}


def _aggregate_knowledge_suggestions(project_root: Path) -> dict[str, Any]:
    """Aggregate knowledge suggestions from knowledge_suggestion stage."""
    output_dir = project_root / "integration"
    stage_file = output_dir / "knowledge_suggestion_output.json"
    inner = _get_agent_data(stage_file)
    if not inner:
        return {"suggestions": [], "by_type": {}}

    suggestions = inner.get("suggestions", inner.get("knowledge_suggestions", []))
    by_type: dict[str, int] = {}
    for s in suggestions:
        t = s.get("asset_type", "unknown")
        by_type[t] = by_type.get(t, 0) + 1
    return {"suggestions": suggestions, "by_type": by_type}


# ── API Endpoints ───────────────────────────────────────────────────────────────


@router.post("/{project_id}/integration/run", response_model=IntegrationRunResponse)
async def run_integration(
    project_id: str,
    request: IntegrationRunRequest = Body(default=IntegrationRunRequest()),
) -> IntegrationRunResponse:
    """Trigger an RMF × CER integration run.

    Runs all 8 integration agents sequentially and aggregates outputs.
    This is reviewer-assistive only — does NOT make regulatory decisions.
    """
    project_root = CER_ARTIFACTS_ROOT / project_id
    if not project_root.exists():
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    # Check existing state
    state = _read_integration_state(project_root)
    integration_run_id = f"INT-{project_id}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"

    # Skip if already completed and not forcing rerun
    if state.get("status") == "completed" and not request.force_rerun:
        return IntegrationRunResponse(
            project_id=project_id,
            run_id=request.run_id,
            integration_run_id=state.get("integration_run_id", "unknown"),
            stages_triggered=[],
            status="already_completed",
            message="Integration already completed. Set force_rerun=true to re-run.",
        )

    # Build context
    context = _build_project_context(project_root)
    context["_integration"] = {
        "integration_run_id": integration_run_id,
        "run_id": request.run_id,
        "project_id": project_id,
        "started_at": datetime.now(timezone.utc).isoformat(),
    }

    # Run stages sequentially
    state = {
        "integration_run_id": integration_run_id,
        "status": "running",
        "stages": {s: "running" for s in INTEGRATION_STAGES},
        "started_at": datetime.now(timezone.utc).isoformat(),
        "completed_at": None,
        "errors": [],
        "outputs": {},
    }
    _write_integration_state(project_root, state)

    for stage in INTEGRATION_STAGES:
        stage_context = dict(context)
        stage_context["_stage"] = stage

        result = _invoke_llm_agent(stage, stage_context, integration_run_id)

        if result.get("status") == "error" or result.get("_meta", {}).get("status") == "error":
            state["stages"][stage] = "failed"
            state["errors"].append(f"{stage}: {result.get('error', 'unknown error')}")
            state["outputs"][stage] = result
        else:
            state["stages"][stage] = "completed"
            state["outputs"][stage] = result

        _write_integration_output(project_root, stage, result)
        _write_integration_state(project_root, state)

    # Finalize
    state["status"] = "completed"
    state["completed_at"] = datetime.now(timezone.utc).isoformat()
    for s in INTEGRATION_STAGES:
        if state["stages"][s] == "running":
            state["stages"][s] = "completed"
    _write_integration_state(project_root, state)

    return IntegrationRunResponse(
        project_id=project_id,
        run_id=request.run_id,
        integration_run_id=integration_run_id,
        stages_triggered=INTEGRATION_STAGES,
        status="completed",
        message="Integration run completed.",
    )


@router.get("/{project_id}/integration/status", response_model=IntegrationStatusResponse)
async def get_integration_status(project_id: str) -> IntegrationStatusResponse:
    """Get integration run status for a project."""
    project_root = CER_ARTIFACTS_ROOT / project_id
    if not project_root.exists():
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    state = _read_integration_state(project_root)

    return IntegrationStatusResponse(
        project_id=project_id,
        integration_run_id=state.get("integration_run_id", "none"),
        status=state.get("status", "not_started"),
        stages=state.get("stages", {}),
        started_at=state.get("started_at"),
        completed_at=state.get("completed_at"),
        errors=state.get("errors", []),
    )


@router.get("/{project_id}/integration/linkage", response_model=IntegrationLinkageResponse)
async def get_integration_linkage(project_id: str) -> IntegrationLinkageResponse:
    """Get RMF × CER linkage matrix."""
    project_root = CER_ARTIFACTS_ROOT / project_id
    if not project_root.exists():
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    state = _read_integration_state(project_root)
    linkage_data = _aggregate_linkage_matrix(project_root)

    # Load review marks
    marks_file = project_root / "integration" / "integration_review_marks.json"
    marks: dict[str, str] = {}
    if marks_file.exists():
        try:
            marks_data = json.loads(marks_file.read_text(encoding="utf-8"))
            marks = {m["item_id"]: m["mark"] for m in marks_data.get("marks", [])}
        except (json.JSONDecodeError, OSError):
            pass

    # Apply review marks to linkages
    for linkage in linkage_data.get("linkages", []):
        lid = linkage.get("linkage_id", "")
        if lid in marks:
            linkage["reviewer_mark"] = marks[lid]

    return IntegrationLinkageResponse(
        project_id=project_id,
        integration_run_id=state.get("integration_run_id", "none"),
        generated_at=datetime.now(timezone.utc).isoformat(),
        total_linkages=len(linkage_data.get("linkages", [])),
        by_type=linkage_data.get("by_type", {}),
        by_status=linkage_data.get("by_status", {}),
        linkages=linkage_data.get("linkages", []),
    )


@router.get("/{project_id}/integration/findings", response_model=IntegrationFindingsResponse)
async def get_integration_findings(project_id: str) -> IntegrationFindingsResponse:
    """Get consistency findings from all integration agents."""
    project_root = CER_ARTIFACTS_ROOT / project_id
    if not project_root.exists():
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    state = _read_integration_state(project_root)
    findings_data = _aggregate_findings(project_root)

    # Load review marks
    marks_file = project_root / "integration" / "integration_review_marks.json"
    marks: dict[str, str] = {}
    if marks_file.exists():
        try:
            marks_data = json.loads(marks_file.read_text(encoding="utf-8"))
            marks = {m["item_id"]: m["mark"] for m in marks_data.get("marks", [])}
        except (json.JSONDecodeError, OSError):
            pass

    # Apply review marks
    for f in findings_data.get("findings", []):
        fid = f.get("finding_id", "")
        if fid in marks:
            f["reviewer_mark"] = marks[fid]

    return IntegrationFindingsResponse(
        project_id=project_id,
        integration_run_id=state.get("integration_run_id", "none"),
        generated_at=datetime.now(timezone.utc).isoformat(),
        total_findings=len(findings_data.get("findings", [])),
        by_category=findings_data.get("by_category", {}),
        by_type=findings_data.get("by_type", {}),
        findings=findings_data.get("findings", []),
    )


@router.get("/{project_id}/integration/gaps", response_model=IntegrationGapsResponse)
async def get_integration_gaps(project_id: str) -> IntegrationGapsResponse:
    """Get evidence gap report."""
    project_root = CER_ARTIFACTS_ROOT / project_id
    if not project_root.exists():
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    state = _read_integration_state(project_root)
    gaps_data = _aggregate_gaps(project_root)

    # Load review marks
    marks_file = project_root / "integration" / "integration_review_marks.json"
    marks: dict[str, str] = {}
    if marks_file.exists():
        try:
            marks_data = json.loads(marks_file.read_text(encoding="utf-8"))
            marks = {m["item_id"]: m["mark"] for m in marks_data.get("marks", [])}
        except (json.JSONDecodeError, OSError):
            pass

    # Apply review marks
    for g in gaps_data.get("gaps", []):
        gid = g.get("gap_id", "")
        if gid in marks:
            g["reviewer_mark"] = marks[gid]

    return IntegrationGapsResponse(
        project_id=project_id,
        integration_run_id=state.get("integration_run_id", "none"),
        generated_at=datetime.now(timezone.utc).isoformat(),
        total_gaps=len(gaps_data.get("gaps", [])),
        gaps=gaps_data.get("gaps", []),
    )


@router.get(
    "/{project_id}/integration/knowledge-suggestions",
    response_model=IntegrationKnowledgeSuggestionsResponse,
)
async def get_knowledge_suggestions(project_id: str) -> IntegrationKnowledgeSuggestionsResponse:
    """Get knowledge asset suggestions from integration."""
    project_root = CER_ARTIFACTS_ROOT / project_id
    if not project_root.exists():
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    state = _read_integration_state(project_root)
    suggestions_data = _aggregate_knowledge_suggestions(project_root)

    # Load review marks
    marks_file = project_root / "integration" / "integration_review_marks.json"
    marks: dict[str, str] = {}
    if marks_file.exists():
        try:
            marks_data = json.loads(marks_file.read_text(encoding="utf-8"))
            marks = {m["item_id"]: m["mark"] for m in marks_data.get("marks", [])}
        except (json.JSONDecodeError, OSError):
            pass

    # Apply review marks
    for s in suggestions_data.get("suggestions", []):
        sid = s.get("suggestion_id", "")
        if sid in marks:
            s["reviewer_mark"] = marks[sid]

    return IntegrationKnowledgeSuggestionsResponse(
        project_id=project_id,
        integration_run_id=state.get("integration_run_id", "none"),
        generated_at=datetime.now(timezone.utc).isoformat(),
        total_suggestions=len(suggestions_data.get("suggestions", [])),
        by_type=suggestions_data.get("by_type", {}),
        suggestions=suggestions_data.get("suggestions", []),
    )


@router.post("/{project_id}/integration/review-mark", response_model=ReviewMarkResponse)
async def submit_review_mark(
    project_id: str,
    request: ReviewMarkRequest = Body(...),
    auth: CERAuthContext = Depends(get_cer_auth_with_gate_role),
) -> ReviewMarkResponse:
    """Submit a reviewer mark on an integration item.

    Reviewer marks are PERSISTED but do NOT alter:
    - Gate 1 / Gate 3 decisions
    - BRR matrix semantics
    - Decision Ledger
    - State Transition Log
    - Knowledge Container publication state

    Marks are stored in integration/integration_review_marks.json only.
    """
    project_root = CER_ARTIFACTS_ROOT / project_id
    if not project_root.exists():
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    marks_file = project_root / "integration" / "integration_review_marks.json"
    marks_file.parent.mkdir(parents=True, exist_ok=True)

    # Load existing marks
    marks_data: dict[str, Any] = {"marks": []}
    if marks_file.exists():
        try:
            marks_data = json.loads(marks_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            marks_data = {"marks": []}

    # Add or update mark
    now = datetime.now(timezone.utc).isoformat()
    item_mark = {
        "item_id": request.item_id,
        "item_type": request.item_type,
        "mark": request.mark,
        "notes": request.notes,
        "marked_at": now,
        "marked_by": auth.user_id,
    }

    # Replace existing mark for same item
    existing = [m for m in marks_data["marks"] if m["item_id"] != request.item_id]
    existing.append(item_mark)
    marks_data["marks"] = existing

    # Write atomically
    tmp_path = marks_file.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(marks_data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp_path.replace(marks_file)

    return ReviewMarkResponse(
        project_id=project_id,
        item_id=request.item_id,
        item_type=request.item_type,
        mark=request.mark,
        marked_at=now,
        marked_by=auth.user_id,
    )


# ── Unified Integration View Endpoint ────────────────────────────────────────


class IntegrationViewSummary(BaseModel):
    """Summary counts for the integration view."""

    total_linkages: int
    total_findings: int
    historical_incomplete: int
    knowledge_suggestions: int
    reviewer_marks: int


class IntegrationViewResponse(BaseModel):
    """Unified integration view response for frontend rendering."""

    project_id: str
    integration_run_id: str | None
    status: str
    summary: IntegrationViewSummary
    linkages: list[dict[str, Any]]
    findings: list[dict[str, Any]]
    knowledge_suggestions: list[dict[str, Any]]
    reviewer_marks: list[dict[str, Any]]


class SuggestionActionRequest(BaseModel):
    """Request to act on a knowledge suggestion."""

    action: str = Field(
        ...,
        pattern="^(confirm|dismiss|park)$",
        description="Action: confirm, dismiss, or park",
    )
    notes: str | None = Field(None, description="Optional reviewer notes")


class SuggestionActionResponse(BaseModel):
    """Response for knowledge suggestion action."""

    project_id: str
    suggestion_id: str
    action: str
    marked_at: str
    marked_by: str | None


@router.get("/{project_id}/integration/view", response_model=IntegrationViewResponse)
async def get_integration_view(project_id: str) -> IntegrationViewResponse:
    """Get unified integration view data for frontend rendering.

    Aggregates all integration outputs into a single frontend-friendly response.
    """
    project_root = CER_ARTIFACTS_ROOT / project_id
    if not project_root.exists():
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    # Get integration state
    state = _read_integration_state(project_root)
    integration_run_id = state.get("integration_run_id")

    # Aggregate all data
    linkage_data = _aggregate_linkage_matrix(project_root)
    findings_data = _aggregate_findings(project_root)
    suggestions_data = _aggregate_knowledge_suggestions(project_root)

    # Load review marks
    marks_file = project_root / "integration" / "integration_review_marks.json"
    reviewer_marks: list[dict[str, Any]] = []
    if marks_file.exists():
        try:
            marks_data = json.loads(marks_file.read_text(encoding="utf-8"))
            reviewer_marks = marks_data.get("marks", [])
        except (json.JSONDecodeError, OSError):
            reviewer_marks = []

    # Build summary
    findings = findings_data.get("findings", [])
    historical_incomplete_count = sum(
        1 for f in findings
        if f.get("finding_type") == "historical_incomplete" or f.get("finding_type") == "historical_only"
    )

    summary = IntegrationViewSummary(
        total_linkages=len(linkage_data.get("linkages", [])),
        total_findings=len(findings),
        historical_incomplete=historical_incomplete_count,
        knowledge_suggestions=len(suggestions_data.get("suggestions", [])),
        reviewer_marks=len(reviewer_marks),
    )

    return IntegrationViewResponse(
        project_id=project_id,
        integration_run_id=integration_run_id,
        status=state.get("status", "not_started"),
        summary=summary,
        linkages=linkage_data.get("linkages", []),
        findings=findings,
        knowledge_suggestions=suggestions_data.get("suggestions", []),
        reviewer_marks=reviewer_marks,
    )


@router.post(
    "/{project_id}/integration/knowledge-suggestion/{suggestion_id}/action",
    response_model=SuggestionActionResponse,
)
async def act_on_knowledge_suggestion(
    project_id: str,
    suggestion_id: str,
    request: SuggestionActionRequest = Body(...),
    auth: CERAuthContext = Depends(get_cer_auth_with_gate_role),
) -> SuggestionActionResponse:
    """Act on a knowledge suggestion (confirm / dismiss / park).

    This submits a reviewer mark for the suggestion item.
    Reviewer marks are stored in integration_review_marks.json only.
    Does NOT auto-publish or auto-apply the knowledge suggestion.
    """
    project_root = CER_ARTIFACTS_ROOT / project_id
    if not project_root.exists():
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    # Persist as a reviewer mark
    marks_file = project_root / "integration" / "integration_review_marks.json"
    marks_file.parent.mkdir(parents=True, exist_ok=True)

    marks_data: dict[str, Any] = {"marks": []}
    if marks_file.exists():
        try:
            marks_data = json.loads(marks_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            marks_data = {"marks": []}

    now = datetime.now(timezone.utc).isoformat()
    item_mark = {
        "item_id": suggestion_id,
        "item_type": "suggestion",
        "mark": request.action,
        "notes": request.notes,
        "marked_at": now,
        "marked_by": auth.user_id,
    }

    # Replace existing mark for same item
    existing = [m for m in marks_data["marks"] if m["item_id"] != suggestion_id]
    existing.append(item_mark)
    marks_data["marks"] = existing

    # Write atomically
    tmp_path = marks_file.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(marks_data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp_path.replace(marks_file)

    return SuggestionActionResponse(
        project_id=project_id,
        suggestion_id=suggestion_id,
        action=request.action,
        marked_at=now,
        marked_by=auth.user_id,
    )
