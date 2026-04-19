"""CER Review Intake API — Project Creation, Evidence Pack Upload, Run Trigger.

Provides governance-aware REST endpoints for CER project intake:
  - POST /api/cer-review/projects                          -> create project + project_profile.yaml
  - POST /api/cer-review/{project_id}/uploads              -> upload evidence pack files
  - POST /api/cer-review/{project_id}/runs                 -> trigger smoke-run via cer_review_runner.py

This module is the P1 intake layer for the CER Review Workspace.
It writes to artifacts/cer/{project_id}/ and invokes scripts/cer_review_runner.py.

Frozen baseline: CER_P1_MVP_CANDIDATE (CER_NEW_RUN_UPLOAD_INTAKE_P1 scope)
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from deerflow.runtime.cer_review.auth import (
    CERAuthContext,
    CERRole,
    is_rbac_enabled,
)
from deerflow.runtime.cer_review.auth.rbac_context import (
    get_cer_auth_with_gate_role,
)
from deerflow.runtime.cer_review.knowledge_candidate_state import (
    AssetType,
    CandidateState,
    KnowledgeCandidate,
)
from deerflow.runtime.cer_review.knowledge_review_gate import (
    KnowledgeReviewGate,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/cer-review", tags=["cer-intake"])

# ── Paths ──────────────────────────────────────────────────────────────────────

_CER_ARTIFACTS_ROOT = Path("/Users/winstonwei/Documents/Playground/deer-flow/artifacts/cer")
_REPO_ROOT = Path(__file__).resolve().parents[4]

# ── Evidence Pack Type ──────────────────────────────────────────────────────────

_EVIDENCE_PACK_TYPES = Literal["EP-001", "EP-002", "EP-003", "EP-004", "EP-005"]

_EP_DIRECTORY_MAP: dict[_EVIDENCE_PACK_TYPES, str] = {
    "EP-001": "EP-001_PRODUCT_DEFINITION",
    "EP-002": "EP-002_SOTA",
    "EP-003": "EP-003_EQUIVALENCE",
    "EP-004": "EP-004_CLINICAL_EVIDENCE",
    "EP-005": "EP-005_RISK_CONSISTENCY",
}

_EP_DESCRIPTIONS: dict[_EVIDENCE_PACK_TYPES, str] = {
    "EP-001": "Product Definition Pack — CER, IFU, CEP",
    "EP-002": "SOTA Pack — Literature and clinical evidence",
    "EP-003": "Equivalence Pack — Predicate device comparison",
    "EP-004": "Clinical Evidence Pack — CEP, PMCF, PMS/PSUR",
    "EP-005": "Risk & Consistency Pack — RMF, SSCP, GSPR mapping",
}

_MARKITDOWN_SUPPORTED = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx"}


# ── RBAC Check ────────────────────────────────────────────────────────────────


def _require_intake_role(auth: CERAuthContext) -> CERAuthContext:
    """Require SENIOR_REVIEWER or ADMIN for intake operations."""
    if auth.role not in {CERRole.SENIOR_REVIEWER, CERRole.ADMIN}:
        raise HTTPException(
            status_code=403,
            detail=f"Permission denied: {auth.role.value} cannot create projects or upload evidence. Requires SENIOR_REVIEWER or ADMIN.",
        )
    return auth


# ── Pydantic Models ───────────────────────────────────────────────────────────


class CreateProjectRequest(BaseModel):
    project_id: str = Field(..., pattern=r"^CER-PJT-\d{4}$")
    project_name: str
    device_name: str
    device_family: str | None = None
    device_class: str | None = None
    intended_use: str | None = None
    market_stage: Literal["CE Marked", "FDA 510(k)", "NMPA", "Other"] = "CE Marked"
    jurisdiction: str = "EU MDR 2017/745"
    organization: str | None = None


class CreateProjectResponse(BaseModel):
    project_id: str
    project_name: str
    created_at: str
    governance_path: str
    input_path: str


class UploadedFile(BaseModel):
    filename: str
    path: str
    size_bytes: int
    converted: bool


class UploadEvidencePackResponse(BaseModel):
    project_id: str
    evidence_pack_type: str
    uploaded_files: list[UploadedFile]


class StartRunRequest(BaseModel):
    mode: Literal["smoke-run"] = "smoke-run"
    thread_id: str | None = None
    input_root: str | None = None


class StartRunResponse(BaseModel):
    project_id: str
    thread_id: str
    run_id: str
    round_id: str
    mode: str
    workflow_name: str
    artifact_root: str
    executed_steps: list[str]
    message: str


# ── Intake Pydantic Models ────────────────────────────────────────────────────────


class IntakePathResponse(BaseModel):
    project_id: str
    raw_intake_path: str
    uploaded_path: str
    intake_session_path: str


class IntakeStageProgress(BaseModel):
    stage: str
    status: str  # pending | complete | error | skipped
    duration_sec: float | None = None
    output_artifact: str | None = None


class IntakeStatusResponse(BaseModel):
    project_id: str
    intake_session_id: str | None = None
    current_state: str
    artifacts: dict[str, str]
    history: list[dict]
    stage_progress: list[IntakeStageProgress]
    is_locked: bool = False


class ClassificationFileEntry(BaseModel):
    file_id: str
    relative_path: str
    final_type: str | None = None
    final_ep: str | None = None
    confidence: float | None = None
    requires_human_review: bool = False
    review_rationale: str | None = None


class ClassificationSummary(BaseModel):
    total_files: int
    auto_proceed_eligible: bool
    high_confidence_count: int
    low_confidence_count: int
    unknown_ep_count: int


class ClassificationResponse(BaseModel):
    project_id: str
    intake_session_id: str
    summary: ClassificationSummary
    files: list[ClassificationFileEntry]
    missing_required_documents: list[dict]


class HumanGateDecisionRequest(BaseModel):
    decision: Literal["APPROVED", "REJECTED", "APPROVED_WITH_CONDITIONS", "NEEDS_CORRECTION"]
    notes: str | None = None


class HumanGateDecisionResponse(BaseModel):
    project_id: str
    intake_session_id: str
    decision: str
    notes: str | None
    submitted_at: str
    decision_file: str


class LockedPackFileEntry(BaseModel):
    relative_path: str
    sha256: str
    ep: str
    size_bytes: int | None = None


class LockedPackResponse(BaseModel):
    project_id: str
    intake_session_id: str
    total_files: int
    files: list[LockedPackFileEntry]
    manifest_path: str | None = None
    verified: bool = False


class StartIntakeResponse(BaseModel):
    project_id: str
    intake_session_id: str
    mode: str
    current_state: str
    started_at: str
    artifact_root: str
    message: str


# ── Helpers ──────────────────────────────────────────────────────────────────


def _project_dir(project_id: str) -> Path:
    return _CER_ARTIFACTS_ROOT / project_id


def _project_exists(project_id: str) -> bool:
    return _project_dir(project_id).exists()


def _next_round_id(project_path: Path) -> str:
    """Find the next available round_XXX directory name.

    Scans project_path for existing round_* directories and returns
    round_{n+1} where n is the highest existing round number.
    Defaults to round_001 if no rounds exist.
    """
    existing = [
        d.name for d in project_path.iterdir()
        if d.is_dir() and d.name.startswith("round_")
    ]
    if not existing:
        return "round_001"
    numbers = []
    for name in existing:
        try:
            num = int(name.replace("round_", ""))
            numbers.append(num)
        except ValueError:
            continue
    return f"round_{max(numbers) + 1:03d}"


def _write_run_metadata(project_path: Path, round_id: str, thread_id: str, run_id: str, artifact_root: Path) -> None:
    """Write run_metadata.json to the project root.

    Bind metadata for project-bound runs.
    """
    import datetime

    metadata = {
        "schema": "cer_run_metadata",
        "version": "1",
        "project_id": project_path.name,
        "run_id": run_id,
        "thread_id": thread_id,
        "round_id": round_id,
        "evidence_packs": list(_EP_DIRECTORY_MAP.keys()),
        "started_by": "cer_intake_api",
        "started_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "runner_status": "completed",
        "artifact_root": str(artifact_root),
    }
    metadata_path = project_path / "run_metadata.json"
    metadata_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info(f"CER intake: wrote run_metadata.json to {metadata_path}")


def _generate_project_profile_yaml(req: CreateProjectRequest, project_path: Path) -> Path:
    """Generate project_profile.yaml from CreateProjectRequest."""
    yaml_path = project_path / "project_profile.yaml"
    docs = []
    for ep_type, ep_dir in _EP_DIRECTORY_MAP.items():
        docs.append(
            {
                "doc_type": ep_type.replace("EP-001", "CER").replace("EP-002", "SOTA").replace("EP-003", "EQUIVALENCE").replace("EP-004", "CLINICAL").replace("EP-005", "RISK"),
                "label": _EP_DESCRIPTIONS[ep_type],
                "path": f"input/{ep_dir}/",
                "required_for_p0": ep_type == "EP-001",
            }
        )

    yaml_content = f"""# Created by CER_NEW_RUN_UPLOAD_INTAKE_P1 — {__import__('datetime').datetime.now().isoformat()}
project_id: "{req.project_id}"
project_name: "{req.project_name}"
institution_profile:
  organization: "{req.organization or ''}"
  assessment_body: ""
  profile_version: "1.0"
review_scope:
  mode: "single_project_serial_review"
  review_language: "zh-CN"
  jurisdiction: "{req.jurisdiction}"
  human_gate_required: true
primary_review_object: "CER"
device_context:
  device_name: "{req.device_name}"
  device_family: "{req.device_family or ''}"
  device_class: "{req.device_class or ''}"
  intended_use: "{req.intended_use or ''}"
  market_stage: "{req.market_stage}"
input_package:
  root_path: "{project_path / 'input'}"
  documents: {json.dumps(docs, indent=4, ensure_ascii=False)}
artifact_policy:
  retention_days: 90
notes:
  - "Created via CER_NEW_RUN_UPLOAD_INTAKE_P1"
  - "Created at: {__import__('datetime').datetime.now().isoformat()}"
"""
    yaml_path.write_text(yaml_content, encoding="utf-8")
    return yaml_path


def _convert_with_markitdown(src_path: Path, dst_dir: Path) -> Path | None:
    """Convert document with markitdown. Returns path to converted .md file, or None if skipped."""
    import subprocess as sp

    suffix = src_path.suffix.lower()
    if suffix not in _MARKITDOWN_SUPPORTED:
        return None

    md_name = src_path.stem + ".md"
    md_path = dst_dir / md_name

    try:
        result = sp.run(
            ["npx", "markitdown", str(src_path), "-o", str(md_path)],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode == 0 and md_path.exists():
            return md_path
    except Exception:
        pass
    return None


def _unique_filename(dst_dir: Path, filename: str) -> Path:
    """Return a unique filename, appending _1, _2, etc. if already exists."""
    dst = dst_dir / filename
    if not dst.exists():
        return dst
    stem, suffix = dst.stem, dst.suffix
    counter = 1
    while True:
        new_dst = dst_dir / f"{stem}_{counter}{suffix}"
        if not new_dst.exists():
            return new_dst
        counter += 1


def _create_correction_candidate(
    project_id: str,
    intake_session_id: str,
    decision_data: dict,
    decision_file: Path,
    reviewer_id: str,
) -> None:
    """P2.2: Create knowledge candidate from NEEDS_CORRECTION human gate decision.

    Creates a CaseLesson or WorkflowImprovement knowledge candidate with
    needs_human_review state. The candidate is saved via KnowledgeReviewGate
    and requires explicit human approval before publication.

    Args:
        project_id: CER project identifier
        intake_session_id: Intake session ID
        decision_data: Full decision data dict
        decision_file: Path to human_intake_gate_decision.json
        reviewer_id: User ID of the reviewer who submitted the decision
    """
    import datetime

    notes = decision_data.get("notes", "") or ""

    # Determine asset type based on notes content heuristics
    notes_lower = notes.lower()
    if any(kw in notes_lower for kw in ["workflow", "process", "procedure", "step"]):
        asset_type = AssetType.WORKFLOW_IMPROVEMENT
    elif any(kw in notes_lower for kw in ["failure", "mistake", "error", "wrong", "incorrect", "defect"]):
        asset_type = AssetType.FAILURE_PATTERN
    else:
        asset_type = AssetType.CASE_LESSON

    # Build source chain
    source_chain = [
        project_id,
        intake_session_id,
        str(decision_file.relative_to(_CER_ARTIFACTS_ROOT / project_id)),
    ]

    # Build payload from decision data
    payload = {
        "verdict": decision_data.get("verdict"),
        "notes": notes,
        "submitted_by": decision_data.get("submitted_by"),
        "submitted_at": decision_data.get("submitted_at"),
        "intake_session_id": intake_session_id,
        "backflow_source": "human_intake_gate_decision",
    }

    # Create candidate in needs_human_review state (NOT approved)
    candidate = KnowledgeCandidate(
        asset_type=asset_type,
        source_artifact=str(decision_file),
        source_chain=source_chain,
        payload=payload,
        confidence=0.95,  # High confidence — direct from human reviewer
        project_id=project_id,
        state=CandidateState.NEEDS_HUMAN_REVIEW,
    )

    # Save via KnowledgeReviewGate
    gate = KnowledgeReviewGate(project_id)
    existing = gate.get_all_candidates()
    existing.append(candidate)
    gate.save_candidates(existing)

    logger.info(
        f"CER intake: correction backflow created candidate {candidate.candidate_id} "
        f"({asset_type.value}) for project {project_id}"
    )


# ── Endpoints ────────────────────────────────────────────────────────────────


@router.post("/projects", response_model=CreateProjectResponse, status_code=201)
async def create_project(
    body: CreateProjectRequest,
    auth: CERAuthContext = Depends(get_cer_auth_with_gate_role),
) -> CreateProjectResponse:
    """Create a new CER project directory with governance/ and project_profile.yaml.

    Requires SENIOR_REVIEWER or ADMIN role.
    """
    _require_intake_role(auth)

    project_path = _project_dir(body.project_id)

    if project_path.exists():
        raise HTTPException(
            status_code=409,
            detail=f"Project {body.project_id} already exists",
        )

    # Create directories
    project_path.mkdir(parents=True, exist_ok=True)
    (project_path / "governance").mkdir(exist_ok=True)
    (project_path / "input").mkdir(exist_ok=True)
    for ep_dir in _EP_DIRECTORY_MAP.values():
        (project_path / "input" / ep_dir).mkdir(exist_ok=True)

    # Generate project_profile.yaml
    yaml_path = _generate_project_profile_yaml(body, project_path)
    logger.info(f"CER intake: created project {body.project_id} at {project_path}")

    return CreateProjectResponse(
        project_id=body.project_id,
        project_name=body.project_name,
        created_at=__import__("datetime").datetime.now().isoformat() + "Z",
        governance_path=str(project_path / "governance"),
        input_path=str(project_path / "input"),
    )


@router.post("/{project_id}/uploads", response_model=UploadEvidencePackResponse)
async def upload_evidence_pack(
    project_id: str,
    evidence_pack_type: _EVIDENCE_PACK_TYPES = Form(...),
    files: list[UploadFile] = File(...),
    auth: CERAuthContext = Depends(get_cer_auth_with_gate_role),
) -> UploadEvidencePackResponse:
    """Upload evidence pack files to a project directory.

    Files are stored in artifacts/cer/{project_id}/input/{EP_DIRECTORY}/.
    PDF/Word/Excel/PPT files are converted via markitdown; both original and .md stored.

    Requires SENIOR_REVIEWER or ADMIN role.
    """
    _require_intake_role(auth)

    project_path = _project_dir(project_id)
    if not project_path.exists():
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    if evidence_pack_type not in _EP_DIRECTORY_MAP:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid evidence_pack_type. Must be one of: {list(_EP_DIRECTORY_MAP.keys())}",
        )

    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    ep_dir_name = _EP_DIRECTORY_MAP[evidence_pack_type]
    dst_base = project_path / "input" / ep_dir_name
    dst_base.mkdir(parents=True, exist_ok=True)

    uploaded: list[UploadedFile] = []
    for file in files:
        # Check file size (50 MB limit)
        content = await file.read()
        file_size = len(content)
        if file_size > 50 * 1024 * 1024:
            raise HTTPException(
                status_code=413,
                detail=f"File {file.filename} exceeds 50MB limit ({file_size} bytes)",
            )

        dst = _unique_filename(dst_base, file.filename)
        dst.write_bytes(content)
        logger.info(f"CER intake: uploaded {file.filename} to {dst}")

        # Convert with markitdown
        converted = False
        if dst.suffix.lower() in _MARKITDOWN_SUPPORTED:
            md_path = _convert_with_markitdown(dst, dst_base)
            if md_path:
                logger.info(f"CER intake: converted {file.filename} to {md_path.name}")
                converted = True

        uploaded.append(
            UploadedFile(
                filename=file.filename,
                path=str(dst.relative_to(project_path)),
                size_bytes=file_size,
                converted=converted,
            )
        )

    return UploadEvidencePackResponse(
        project_id=project_id,
        evidence_pack_type=evidence_pack_type,
        uploaded_files=uploaded,
    )


@router.post("/{project_id}/runs", response_model=StartRunResponse, status_code=201)
async def start_run(
    project_id: str,
    body: StartRunRequest = StartRunRequest(),
    auth: CERAuthContext = Depends(get_cer_auth_with_gate_role),
) -> StartRunResponse:
    """Trigger a smoke-run for a CER project.

    Reads project_profile.yaml from artifacts/cer/{project_id}/ and invokes
    scripts/cer_review_runner.py with the project profile path.

    Artifacts are written to the project-bound directory:
      artifacts/cer/{project_id}/round_XXX/artifacts/

    A run_manifest.json is written to round_XXX/artifacts/00_manifest/ so the run
    is visible in GET /api/cer-review/{project_id}/runs and the Artifact Browser.

    Requires SENIOR_REVIEWER or ADMIN role.
    """
    _require_intake_role(auth)

    project_path = _project_dir(project_id)
    if not project_path.exists():
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    yaml_path = project_path / "project_profile.yaml"
    if not yaml_path.exists():
        raise HTTPException(
            status_code=400,
            detail=f"project_profile.yaml not found in {project_id}. Create the project first.",
        )

    # Determine next available round_id
    round_id = _next_round_id(project_path)

    # Generate thread_id if not provided
    thread_id = body.thread_id or f"cer-{project_id.lower()}-{uuid.uuid4().hex[:8]}"

    # Project-bound artifact root: artifacts/cer/{project_id}/round_XXX/artifacts
    project_artifact_root = project_path / round_id / "artifacts"

    # Ensure round directory exists
    project_artifact_root.mkdir(parents=True, exist_ok=True)

    # Build command with project-bound artifact root override
    cmd = [
        sys.executable,
        str(_REPO_ROOT / "scripts" / "cer_review_runner.py"),
        "--project-profile",
        str(yaml_path),
        "--mode",
        body.mode,
        "--thread-id",
        thread_id,
        "--artifact-root-override",
        str(project_artifact_root),
    ]
    if body.input_root:
        cmd.extend(["--input-root", body.input_root])

    logger.info(
        f"CER intake: starting run for {project_id} "
        f"(round={round_id}, thread={thread_id}, "
        f"artifact_root_override={project_artifact_root})"
    )

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=str(_REPO_ROOT),
        timeout=1800,
    )

    if result.returncode != 0:
        logger.error(f"CER intake: runner failed: {result.stderr}")
        raise HTTPException(
            status_code=500,
            detail=f"cer_review_runner.py failed: {result.stderr[:500]}",
        )

    try:
        output = json.loads(result.stdout)
    except Exception:
        raise HTTPException(
            status_code=500,
            detail=f"cer_review_runner.py returned invalid JSON: {result.stdout[:200]}",
        )

    run_id = output.get("run_id", f"{project_id}-{uuid.uuid4().hex[:8]}")

    # Post-process: ensure run_manifest.json exists for governance compatibility.
    # The runner writes run_summary.json; we rename it to run_manifest.json
    # so list_runs() can discover this run.
    manifest_dir = project_artifact_root / "00_manifest"
    summary_path = manifest_dir / "run_summary.json"
    manifest_path = manifest_dir / "run_manifest.json"

    if summary_path.exists() and not manifest_path.exists():
        summary_data = json.loads(summary_path.read_text())
        # Add current_state so list_runs() can populate gate_status
        manifest_data = {
            **summary_data,
            "current_state": "S06",  # gate_closure_complete — terminal state for smoke-run
            "execution_mode": body.mode,
        }
        manifest_path.write_text(json.dumps(manifest_data, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.info(f"CER intake: wrote run_manifest.json from run_summary.json at {manifest_path}")

    # Write run_metadata.json to project root for bind metadata
    _write_run_metadata(project_path, round_id, thread_id, run_id, project_artifact_root)

    message = f"Smoke-run completed. thread_id={thread_id}, run_id={run_id}"

    return StartRunResponse(
        project_id=project_id,
        thread_id=thread_id,
        run_id=run_id,
        round_id=round_id,
        mode=body.mode,
        workflow_name=output.get("workflow_name", "cer_review_v1"),
        artifact_root=str(project_artifact_root),
        executed_steps=output.get("executed_steps", []),
        message=message,
    )


# ── Intake Status Endpoints ────────────────────────────────────────────────────────


@router.get("/{project_id}/intake/path", response_model=IntakePathResponse)
async def get_intake_path(
    project_id: str,
    auth: CERAuthContext = Depends(get_cer_auth_with_gate_role),
) -> IntakePathResponse:
    """Return intake path information for a project.

    Shows the exact folder paths for raw intake files.
    """
    project_path = _project_dir(project_id)
    if not project_path.exists():
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    return IntakePathResponse(
        project_id=project_id,
        raw_intake_path=str(project_path / "input"),
        uploaded_path=str(project_path / "input"),
        intake_session_path=str(project_path / "intake"),
    )


@router.get("/{project_id}/intake/status", response_model=IntakeStatusResponse)
async def get_intake_status(
    project_id: str,
    auth: CERAuthContext = Depends(get_cer_auth_with_gate_role),
) -> IntakeStatusResponse:
    """Return the current intake status and pipeline progress.

    Reads intake_state.json and intake_session_log.jsonl to show
    the 15-state pipeline progress.
    """
    project_path = _project_dir(project_id)
    if not project_path.exists():
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    intake_dir = project_path / "intake"
    state_file = intake_dir / "intake_state.json"
    log_file = intake_dir / "intake_session_log.jsonl"

    if not state_file.exists():
        # No intake run yet
        return IntakeStatusResponse(
            project_id=project_id,
            intake_session_id=None,
            current_state="not_started",
            artifacts={},
            history=[],
            stage_progress=[],
            is_locked=False,
        )

    state_data = json.loads(state_file.read_text())

    # Parse log file for stage progress
    stage_progress: list[IntakeStageProgress] = []
    if log_file.exists():
        for line in log_file.read_text().strip().split("\n"):
            if line:
                entry = json.loads(line)
                if entry.get("event") == "agent_invocation":
                    stage_progress.append(IntakeStageProgress(
                        stage=entry.get("stage", ""),
                        status="complete" if entry.get("success") else "error",
                        duration_sec=entry.get("duration_sec"),
                        output_artifact=entry.get("output_artifact"),
                    ))

    # Check if locked
    locked_dir = intake_dir / "locked"
    is_locked = locked_dir.exists() and any(locked_dir.iterdir())

    return IntakeStatusResponse(
        project_id=project_id,
        intake_session_id=state_data.get("intake_session_id"),
        current_state=state_data.get("current_state", "unknown"),
        artifacts=state_data.get("artifacts", {}),
        history=state_data.get("history", []),
        stage_progress=stage_progress,
        is_locked=is_locked,
    )


@router.get("/{project_id}/intake/classification", response_model=ClassificationResponse)
async def get_intake_classification(
    project_id: str,
    auth: CERAuthContext = Depends(get_cer_auth_with_gate_role),
) -> ClassificationResponse:
    """Return the classification review data.

    Reads classification_review_packet.json or
    evidence_classification_final.json to show per-file classifications.
    """
    project_path = _project_dir(project_id)
    if not project_path.exists():
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    intake_dir = project_path / "intake"

    # Try classification_review_packet first, then fall back to evidence_classification_final
    review_packet = intake_dir / "classification_review_packet.json"
    class_final = intake_dir / "evidence_classification_final.json"
    class_candidates = intake_dir / "classification_candidates.json"
    class_output = intake_dir / "classification_output.json"

    classification_data = None
    if review_packet.exists():
        classification_data = json.loads(review_packet.read_text())
    elif class_final.exists():
        classification_data = json.loads(class_final.read_text())
    elif class_candidates.exists():
        classification_data = json.loads(class_candidates.read_text())
    elif class_output.exists():
        classification_data = json.loads(class_output.read_text())
    else:
        raise HTTPException(
            status_code=404,
            detail="No classification data found. Run intake first.",
        )

    # Extract files list
    files: list[ClassificationFileEntry] = []
    if "classifications" in classification_data:
        for c in classification_data.get("classifications", []):
            files.append(ClassificationFileEntry(
                file_id=c.get("file_id", ""),
                relative_path=c.get("relative_path", ""),
                final_type=c.get("final_type"),
                final_ep=c.get("final_ep"),
                confidence=c.get("confidence"),
                requires_human_review=c.get("requires_human_review", False),
                review_rationale=c.get("review_rationale"),
            ))
    elif "candidates" in classification_data:
        for c in classification_data.get("candidates", []):
            files.append(ClassificationFileEntry(
                file_id=c.get("file_id", ""),
                relative_path=c.get("relative_path", ""),
                final_type=c.get("detected_type"),
                final_ep=c.get("detected_ep"),
                confidence=c.get("confidence"),
                requires_human_review=c.get("confidence", 1.0) < 0.8,
                review_rationale=c.get("reasoning"),
            ))

    # Compute summary
    total_files = len(files)
    low_confidence = sum(1 for f in files if f.confidence and f.confidence < 0.8)
    high_confidence = sum(1 for f in files if f.confidence and f.confidence >= 0.8)
    unknown_ep = sum(1 for f in files if not f.final_ep)

    return ClassificationResponse(
        project_id=project_id,
        intake_session_id=classification_data.get("intake_session_id", ""),
        summary=ClassificationSummary(
            total_files=total_files,
            auto_proceed_eligible=low_confidence == 0,
            high_confidence_count=high_confidence,
            low_confidence_count=low_confidence,
            unknown_ep_count=unknown_ep,
        ),
        files=files,
        missing_required_documents=classification_data.get("missing_required_documents", []),
    )


@router.post("/{project_id}/intake/human-decision", response_model=HumanGateDecisionResponse)
async def submit_human_gate_decision(
    project_id: str,
    body: HumanGateDecisionRequest,
    auth: CERAuthContext = Depends(get_cer_auth_with_gate_role),
) -> HumanGateDecisionResponse:
    """Submit a human intake gate decision.

    Writes human_intake_gate_decision.json which triggers the state machine
    to transition from human_gate_pending to approved/rejected.
    """
    _require_intake_role(auth)

    project_path = _project_dir(project_id)
    if not project_path.exists():
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    intake_dir = project_path / "intake"
    state_file = intake_dir / "intake_state.json"

    if not state_file.exists():
        raise HTTPException(
            status_code=400,
            detail="No intake session found. Run intake first.",
        )

    state_data = json.loads(state_file.read_text())
    current_state = state_data.get("current_state")

    if current_state != "human_gate_pending":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot submit decision in state '{current_state}'. Must be in 'human_gate_pending'.",
        )

    # Write decision file
    import datetime
    decision_data = {
        "schema_name": "cer_intake_human_gate_decision",
        "schema_version": "v1",
        "project_id": project_id,
        "intake_session_id": state_data.get("intake_session_id"),
        "verdict": body.decision,
        "notes": body.notes,
        "submitted_by": auth.user_id,
        "submitted_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    decision_file = intake_dir / "human_intake_gate_decision.json"
    decision_file.write_text(json.dumps(decision_data, indent=2, ensure_ascii=False))

    # Update state machine to reflect decision
    # This allows the next intake/run call to process pack locking
    submitted_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
    new_state = "human_gate_approved" if body.decision in ("APPROVED", "APPROVED_WITH_CONDITIONS") else "human_gate_rejected"

    # Update state file
    state_data["current_state"] = new_state
    state_data["persisted_at"] = submitted_at
    state_data.setdefault("history", []).append({
        "from_state": "human_gate_pending",
        "to_state": new_state,
        "reason": f"human gate {body.decision.lower()}",
        "timestamp": submitted_at,
    })
    state_file.write_text(json.dumps(state_data, indent=2, ensure_ascii=False))

    logger.info(
        f"CER intake: human gate decision submitted for {project_id}: {body.decision} -> state: {new_state}"
    )

    # P2.2: Correction backflow — create knowledge candidate when NEEDS_CORRECTION
    if body.decision == "NEEDS_CORRECTION" and body.notes:
        try:
            _create_correction_candidate(
                project_id=project_id,
                intake_session_id=state_data.get("intake_session_id", ""),
                decision_data=decision_data,
                decision_file=decision_file,
                reviewer_id=auth.user_id,
            )
        except Exception as e:
            # Don't fail the human gate decision if backflow fails
            logger.error(f"CER intake: correction backflow failed for {project_id}: {e}")

    return HumanGateDecisionResponse(
        project_id=project_id,
        intake_session_id=state_data.get("intake_session_id", ""),
        decision=body.decision,
        notes=body.notes,
        submitted_at=submitted_at,
        decision_file=str(decision_file.relative_to(project_path)),
    )


@router.get("/{project_id}/intake/locked-pack", response_model=LockedPackResponse)
async def get_locked_pack(
    project_id: str,
    auth: CERAuthContext = Depends(get_cer_auth_with_gate_role),
) -> LockedPackResponse:
    """Return the locked evidence pack information.

    Reads locked_evidence_pack_manifest.json to show the locked pack contents.
    """
    project_path = _project_dir(project_id)
    if not project_path.exists():
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    intake_dir = project_path / "intake"
    locked_dir = intake_dir / "locked"
    manifest_file = locked_dir / "locked_evidence_pack_manifest.json"

    if not manifest_file.exists():
        raise HTTPException(
            status_code=404,
            detail="No locked evidence pack found. Submit human gate decision first.",
        )

    manifest_data = json.loads(manifest_file.read_text())

    files = [
        LockedPackFileEntry(
            relative_path=f.get("relative_path", ""),
            sha256=f.get("sha256", ""),
            ep=f.get("ep", ""),
            size_bytes=f.get("size_bytes"),
        )
        for f in manifest_data.get("files", [])
    ]

    return LockedPackResponse(
        project_id=project_id,
        intake_session_id=manifest_data.get("intake_session_id", ""),
        total_files=manifest_data.get("total_files", 0),
        files=files,
        manifest_path=str(manifest_file.relative_to(project_path)),
        verified=True,
    )


@router.post("/{project_id}/intake/run", response_model=StartIntakeResponse, status_code=202)
async def start_intake(
    project_id: str,
    auth: CERAuthContext = Depends(get_cer_auth_with_gate_role),
) -> StartIntakeResponse:
    """Trigger a raw intake run for a CER project.

    Invokes cer_raw_intake_runner.py which executes the 15-state intake pipeline.
    This is a synchronous operation that may take several minutes due to LLM calls.

    Requires SENIOR_REVIEWER or ADMIN role.
    """
    import datetime

    _require_intake_role(auth)

    project_path = _project_dir(project_id)
    if not project_path.exists():
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    yaml_path = project_path / "project_profile.yaml"
    if not yaml_path.exists():
        raise HTTPException(
            status_code=400,
            detail=f"project_profile.yaml not found in {project_id}. Create the project first.",
        )

    # Determine input root - use the raw intake input directory
    input_root = project_path / "input"

    # Check if there are files to process
    has_files = any(f.is_file() for f in input_root.rglob("*") if not f.name.startswith("."))
    if not has_files:
        raise HTTPException(
            status_code=400,
            detail="No input files found. Place files in the input directories (EP-001 through EP-005) before running intake.",
        )

    logger.info(f"CER intake: starting intake run for {project_id}")

    cmd = [
        sys.executable,
        str(_REPO_ROOT / "scripts" / "cer_raw_intake_runner.py"),
        "--project-id",
        project_id,
        "--input-root",
        str(input_root),
        "--project-profile",
        str(yaml_path),
        "--artifact-root",
        str(project_path),
        "--mode",
        "smoke-run",
    ]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=str(_REPO_ROOT),
        timeout=600,  # 10 minute timeout for intake pipeline
    )

    if result.returncode != 0:
        logger.error(f"CER intake: runner failed: {result.stderr}")
        raise HTTPException(
            status_code=500,
            detail=f"cer_raw_intake_runner.py failed: {result.stderr[:500]}",
        )

    # Parse runner output to get intake_session_id and state
    runner_output: dict[str, Any] = {}
    try:
        runner_output = json.loads(result.stdout)
    except Exception:
        pass

    # Read the current state from intake_state.json
    state_file = project_path / "intake" / "intake_state.json"
    current_state = "unknown"
    intake_session_id = runner_output.get("intake_session_id", "")

    if state_file.exists():
        state_data = json.loads(state_file.read_text())
        current_state = state_data.get("current_state", current_state)
        intake_session_id = state_data.get("intake_session_id", intake_session_id)

    started_at = datetime.datetime.now(datetime.timezone.utc).isoformat()

    return StartIntakeResponse(
        project_id=project_id,
        intake_session_id=intake_session_id,
        mode="smoke-run",
        current_state=current_state,
        started_at=started_at,
        artifact_root=str(project_path),
        message=f"Intake run completed. Current state: {current_state}",
    )
