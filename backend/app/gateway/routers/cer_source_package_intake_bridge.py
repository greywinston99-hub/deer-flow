"""CER Source Package Intake Bridge — Phase 19C Implementation.

Provides the bridge between:
  - Intake pipeline (folder path input → scan → classification → locked pack)
  - Available-source bounded workflow (source_status + source_documents → reviewer packet)

This module implements the Phase 19A minimum intake bridge requirements.

Non-claims enforced:
  - Does NOT generate official CEAR
  - Does NOT make final clinical/regulatory decisions
  - Does NOT claim production ready
  - Does NOT execute backflow to Obsidian/NocoDB
  - Does NOT create approved/active/reusable assets

Frozen baseline: PHASE_19C_SOURCE_PACKAGE_INTAKE_BRIDGE_IMPLEMENTATION
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/cer-review/intake/source-package", tags=["cer-source-package-intake-bridge"])

# ── Constants ──────────────────────────────────────────────────────────────────

ARTIFACTS_ROOT = Path("/Users/winstonwei/Documents/Playground/deer-flow/artifacts/cer")

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".doc", ".xlsx", ".xls", ".csv", ".txt", ".md", ".pptx"}

# Directories that are NEVER allowed as source package roots
BLOCKED_PATH_PREFIXES = (
    "/",
    "/System",
    "/Library",
    "/bin",
    "/usr",
    "/etc",
    "/sbin",
    "/boot",
    "/dev",
    "/proc",
    "/sys",
    "/run",
    "/snap",
    "/srv",
    "/mnt",
    "/media",
    "/opt",
    "/cores",
)

BLOCKED_PATTERNS = (
    ".ssh",
    ".aws",
    ".gcp",
    ".azure",
    "credentials",
    "secrets",
    "password",
    ".env",
    ".git",
    ".svn",
    "node_modules",
)


# ── Enums ──────────────────────────────────────────────────────────────────────


class DocumentType(str, Enum):
    IFU = "ifu"
    CER = "cer"
    CEP = "cep"
    RMF = "rmf"
    RISK_ANALYSIS = "risk_related"
    EQUIVALENCE = "equivalence"
    LITERATURE = "literature"
    SOTA = "sota"
    PMCF = "pmcf"
    PMS = "pms"
    GSPR = "gspr"
    SSCP = "sscp"
    CLINICAL_EVIDENCE = "clinical_evidence"
    BIOCOMPATIBILITY = "biocompatibility"
    PERFORMANCE = "performance"
    REVIEWER_NOTE = "reviewer_note"
    UNKNOWN = "unknown"


class VersionStatus(str, Enum):
    FINAL = "final"
    DRAFT = "draft"
    UNKNOWN = "unknown"


class Availability(str, Enum):
    AVAILABLE = "available"
    MISSING = "missing"
    PARTIAL = "partial"
    REQUIRES_CONFIRMATION = "requires_confirmation"


class BridgeStatus(str, Enum):
    READY_FOR_HUMAN_CONFIRMATION = "READY_FOR_HUMAN_CONFIRMATION"
    HOLD_FOR_SOURCE_PACKAGE_PATH = "HOLD_FOR_SOURCE_PACKAGE_PATH"
    HOLD_FOR_CLASSIFICATION_CONFIRMATION = "HOLD_FOR_CLASSIFICATION_CONFIRMATION"
    READY_TO_RUN_AVAILABLE_SOURCE_WORKFLOW = "READY_TO_RUN_AVAILABLE_SOURCE_WORKFLOW"


class ScanMode(str, Enum):
    METADATA_ONLY = "metadata_only"
    LIGHTWEIGHT_CONTENT = "lightweight_content"


# ── Pydantic Models ────────────────────────────────────────────────────────────


class SourcePackageScanRequest(BaseModel):
    """Request to scan a source package folder."""

    project_id: str = Field(..., description="Project ID")
    project_name: str = Field(..., description="Project name")
    source_package_path: str = Field(..., description="Absolute path to source package folder")
    scan_mode: ScanMode = Field(default=ScanMode.METADATA_ONLY, description="Scan depth")
    recursive: bool = Field(default=True, description="Recursively scan subdirectories")
    max_files: int = Field(default=500, ge=1, le=5000, description="Maximum files to scan")
    human_confirmation_required: bool = Field(default=True, description="Whether human confirmation is required")


class ScannedFile(BaseModel):
    """A single file discovered during source package scan."""

    file_id: str
    file_name: str
    source_path: str
    relative_path: str
    extension: str
    size_bytes: int
    modified_time: str | None
    scan_status: str  # "ok", "flagged", "error"
    warning: str | None = None


class ClassificationCandidate(BaseModel):
    """A document classification candidate inferred from filename/path."""

    file_id: str
    document_type: str  # DocumentType value
    confidence: float = Field(ge=0.0, le=1.0)
    matched_keywords: list[str]
    reason: str
    requires_human_confirmation: bool
    is_true_source_candidate: bool
    version_status: str  # VersionStatus value
    notes: str | None = None


class SourceDocumentOut(BaseModel):
    """A source document in the bridge output (matches AvailableSourceWorkflow SourceDocument)."""

    document_id: str
    document_type: str | None
    file_name: str | None
    source_path: str | None
    version_status: str | None
    availability: str = "available"
    is_true_source: bool = False
    classification_confidence: float | None = None
    requires_human_confirmation: bool = False
    notes: str | None = None


class SourceStatusOut(BaseModel):
    """Source availability status derived from scanned and classified documents."""

    ifu_available: bool = False
    cer_available: bool = False
    rmf_available: bool = False
    risk_related_source_available: bool = False
    equivalence_available: bool = False
    pmcf_available: bool = False
    pms_available: bool = False
    gspr_available: bool = False
    sscp_available: bool = False


class AvailableSourceRequestPreview(BaseModel):
    """Preview of the available-source workflow request."""

    project_id: str
    project_name: str
    workflow_mode: str = "AVAILABLE_SOURCE_LIMITED"
    source_package_ref: str | None
    review_scope: list[str]
    official_cear_allowed: bool = False
    final_regulatory_decision_allowed: bool = False
    production_claim_allowed: bool = False
    source_status: SourceStatusOut
    source_documents_count: int
    human_confirmation_required: bool


class HumanConfirmationPacket(BaseModel):
    """Human confirmation packet for operator review."""

    status: str  # BridgeStatus value
    project_id: str
    project_name: str
    source_package_path: str
    scanned_files_count: int
    high_confidence_count: int
    low_confidence_count: int
    classification_candidates: list[ClassificationCandidate]
    source_status: SourceStatusOut
    source_documents_preview: list[SourceDocumentOut]
    available_source_request_preview: AvailableSourceRequestPreview
    warnings: list[str]
    recommended_actions: list[str]
    generated_at: str
    non_claims: dict[str, str]


class SourcePackageScanResponse(BaseModel):
    """Response from source package scan endpoint."""

    scan_id: str
    project_id: str
    project_name: str
    source_package_path: str
    scanned_files: list[ScannedFile]
    classification_candidates: list[ClassificationCandidate]
    source_documents: list[SourceDocumentOut]
    source_status: SourceStatusOut
    status: str  # BridgeStatus value
    warnings: list[str]
    generated_at: str


class AvailableSourceRequestBuildResponse(BaseModel):
    """Response from available-source request build endpoint."""

    build_id: str
    project_id: str
    project_status: str  # BridgeStatus value
    source_status: SourceStatusOut
    source_documents: list[SourceDocumentOut]
    available_source_request: dict[str, Any]  # Raw dict for direct POST
    human_confirmation_packet: HumanConfirmationPacket
    warnings: list[str]
    generated_at: str


class SourcePackagePrepareResponse(BaseModel):
    """Combined scan + build response (single prepare endpoint)."""

    prepare_id: str
    project_id: str
    project_name: str
    source_package_path: str
    status: str  # BridgeStatus value
    scanned_files_count: int
    classification_candidates_count: int
    source_documents_count: int
    source_status: SourceStatusOut
    available_source_request: dict[str, Any] | None
    human_confirmation_packet: HumanConfirmationPacket
    warnings: list[str]
    generated_at: str


# ── Path Validation ────────────────────────────────────────────────────────────


def validate_safe_path(path: str) -> tuple[bool, str]:
    """Validate that a path is safe to scan (no system directories, no traversal).

    Returns (is_safe, error_message).

    For blocked path prefixes: checks BOTH the user-provided path and the resolved path.
    This handles macOS symlinks where /etc -> /private/etc and /tmp -> /private/tmp.
    """
    path_lower = path.lower()

    # Check for blocked patterns in the user-provided path (before symlink resolution)
    for blocked in BLOCKED_PATTERNS:
        if blocked.lower() in path_lower:
            return False, f"Blocked path pattern detected: {blocked}"

    # Check blocked prefixes against the user-provided path
    for blocked in BLOCKED_PATH_PREFIXES:
        if blocked == "/":
            if path == "/":
                return False, "Root directory / is blocked"
            continue
        if path == blocked or path.startswith(blocked + "/"):
            return False, f"Blocked system directory: {blocked}"

    # Check resolved path for symlink-enlarged system directories (macOS: /etc->/private/etc, /tmp->/private/tmp)
    try:
        resolved = Path(path).resolve()
    except (OSError, RuntimeError) as e:
        return False, f"Path resolution failed: {e}"

    resolved_str = str(resolved)
    if resolved_str != path:
        # Path was symlinked — check resolved path against blocked prefixes
        for blocked in BLOCKED_PATH_PREFIXES:
            if blocked == "/":
                if resolved_str == "/":
                    return False, "Root directory / is blocked (via symlink)"
                continue
            if resolved_str == blocked or resolved_str.startswith(blocked + "/"):
                return False, f"Blocked system directory (symlink resolves to {blocked}): {resolved_str}"

    return True, ""


def validate_source_package_path(path: str) -> tuple[bool, str]:
    """Validate that the path exists and is a directory.

    Returns (is_valid, error_message).
    """
    is_safe, error = validate_safe_path(path)
    if not is_safe:
        return False, error

    p = Path(path)
    if not p.exists():
        return False, "Source package path does not exist"
    if not p.is_dir():
        return False, "Source package path is not a directory"
    return True, ""


# ── Source Package Scanner ──────────────────────────────────────────────────────


def scan_source_package(
    package_path: str,
    recursive: bool = True,
    max_files: int = 500,
) -> tuple[list[ScannedFile], list[str]]:
    """Scan a source package folder and return discovered files.

    Does NOT read file content. Only collects metadata.

    Returns (scanned_files, warnings).
    """
    warnings: list[str] = []
    scanned: list[ScannedFile] = []

    root = Path(package_path)

    # Collect files
    if recursive:
        all_paths = sorted(root.rglob("*"))
    else:
        all_paths = sorted(root.glob("*"))

    file_paths = [p for p in all_paths if p.is_file() and not p.name.startswith(".")]

    if len(file_paths) > max_files:
        warnings.append(f"File count {len(file_paths)} exceeds max_files={max_files}; truncating to {max_files}")
        file_paths = file_paths[:max_files]

    for i, fp in enumerate(file_paths):
        file_id = f"SP-{i+1:04d}"
        ext = fp.suffix.lower()
        warning = None

        # Check extension first — unsupported files get flagged immediately
        warning = None
        scan_status = "ok"
        if ext not in SUPPORTED_EXTENSIONS:
            warning = f"Unsupported file type: {ext}"
            scan_status = "flagged"

        # Check size
        size = 0
        try:
            size = fp.stat().st_size
            if size == 0:
                warning = "Zero-byte file"
                scan_status = "flagged"
            elif size > 100 * 1024 * 1024 and scan_status != "flagged":  # 100MB, don't override unsupported flag
                warning = "Large file (>100MB); content not read"
                scan_status = "flagged"
        except OSError as e:
            warning = f"Cannot stat file: {e}"
            scan_status = "error"

        # Get modified time
        modified = None
        try:
            modified = datetime.fromtimestamp(fp.stat().st_mtime, tz=timezone.utc).isoformat()
        except OSError:
            pass

        scanned.append(ScannedFile(
            file_id=file_id,
            file_name=fp.name,
            source_path=str(fp),
            relative_path=str(fp.relative_to(root)),
            extension=ext,
            size_bytes=size,
            modified_time=modified,
            scan_status=scan_status,
            warning=warning,
        ))
        if warning:
            warnings.append(f"{file_id} ({fp.name}): {warning}")

    return scanned, warnings


# ── Document Classifier ─────────────────────────────────────────────────────────


# Keyword → DocumentType mapping
DOCUMENT_TYPE_KEYWORDS: dict[str, list[tuple[str, list[str]]]] = {
    "ifu": [
        ("ifu", ["ifu", "instructions for use", "使用说明书", "说明书", "手册"]),
        ("cer", ["clinical evaluation report", "cer", "临床评价报告", "clinical evaluation"]),
        ("cep", ["clinical evaluation plan", "cep", "临床评价计划"]),
    ],
    "rmf": [
        ("rmf", ["risk management file", "rmf", "风险管理文件", "iso 14971"]),
        ("risk_related", ["risk analysis", "fmea", "haccep", "风险分析", "风险管理报告", "rmr"]),
    ],
    "equivalence": [
        ("equivalence", ["equivalence", "等同", "等效", "equivalent device", "predicate device"]),
        ("sota", ["state of the art", "sota", "literature search", "文献检索"]),
    ],
    "pmcf_pms": [
        ("pmcf", ["pmcf", "post-market clinical follow", "上市后临床跟踪", "临床跟踪"]),
        ("pms", ["pms", "post-market surveillance", "上市后监督", "pms data"]),
    ],
    "regulatory": [
        ("gspr", ["gspr", "general safety and performance", "基本安全和性能要求"]),
        ("sscp", ["sscp", "summary of safety and clinical performance", "安全和临床性能总结"]),
    ],
    "other": [
        ("clinical_evidence", ["clinical evidence", "clinical data", "临床证据", "临床数据"]),
        ("biocompatibility", ["biocompatibility", "生物相容性", "iso 10993"]),
        ("performance", ["performance test", "性能测试", "bench test"]),
        ("reviewer_note", ["reviewer note", "reviewer's note", "审核记录"]),
    ],
}

# Flatten for classification
DOCUMENT_TYPE_RULES: list[tuple[str, list[str], float]] = [
    # (document_type, keywords, base_confidence)
    ("ifu", ["ifu", "instructions for use", "使用说明书", "说明书", "if u", "instruction for use"], 0.95),
    ("cer", ["clinical evaluation report", "cer", "临床评价报告"], 0.95),
    ("cep", ["clinical evaluation plan", "cep", "临床评价计划", "clinical evaluation plan"], 0.95),
    ("rmf", ["risk management file", "rmf", "iso 14971", "risk management report", "rmr", "risk management", "risk_management_file"], 0.90),
    ("risk_related", ["risk analysis", "fmea", "haccep", "风险分析", "风险管理报告", "risk_analysis", "risk_file"], 0.85),
    ("equivalence", ["equivalence table", "equivalence", "等同", "等效", "predicate", "baxter", "nipro"], 0.80),
    ("sota", ["state of the art", "sota", "literature search", "文献检索", "literature review"], 0.80),
    ("literature", ["literature", "pubmed", "systematic review"], 0.75),
    ("pmcf", ["pmcf plan", "pmcf", "post-market clinical follow", "上市后临床跟踪"], 0.90),
    ("pms", ["pms", "post-market surveillance", "上市后监督", "psur"], 0.85),
    ("gspr", ["gspr", "general safety and performance requirements", "基本安全和性能要求"], 0.90),
    ("sscp", ["sscp", "summary of safety and clinical performance", "安全和临床性能总结"], 0.90),
    ("clinical_evidence", ["clinical evidence", "clinical data", "临床证据", "clinical results"], 0.70),
    ("biocompatibility", ["biocompatibility", "iso 10993", "生物相容性"], 0.85),
    ("performance", ["performance test", "bench test", "性能测试"], 0.70),
    ("reviewer_note", ["reviewer note", "reviewer's note", "审核记录", "审核备注"], 0.50),
]

# Version indicators
VERSION_FINAL_KEYWORDS = ["final", "approved", "终版", "批准版", "approved version"]
VERSION_DRAFT_KEYWORDS = ["draft", "草稿", "discussion", "讨论", "working", "工作版", "rev"]


def classify_document_candidates(
    scanned_files: list[ScannedFile],
) -> list[ClassificationCandidate]:
    """Classify scanned files into document types based on filename/path keywords.

    This is a heuristic classifier — not an LLM classifier.
    It does NOT read file content.
    """
    candidates: list[ClassificationCandidate] = []

    for sf in scanned_files:
        # Skip unsupported files
        if sf.extension not in SUPPORTED_EXTENSIONS:
            candidates.append(ClassificationCandidate(
                file_id=sf.file_id,
                document_type="unknown",
                confidence=0.0,
                matched_keywords=[],
                reason=f"Unsupported file type: {sf.extension}",
                requires_human_confirmation=True,
                is_true_source_candidate=False,
                version_status="unknown",
                notes=f"Extension {sf.extension} is not a recognized document type",
            ))
            continue

        # Classify by filename
        name_lower = sf.file_name.lower()
        path_lower = sf.relative_path.lower()

        matched_type: str | None = None
        matched_keywords: list[str] = []
        best_confidence = 0.0

        for doc_type, keywords, base_conf in DOCUMENT_TYPE_RULES:
            for kw in keywords:
                if kw.lower() in name_lower or kw.lower() in path_lower:
                    if base_conf > best_confidence:
                        best_confidence = base_conf
                        matched_type = doc_type
                        matched_keywords = [kw]

        # Check version status
        version_status = "unknown"
        for kw in VERSION_FINAL_KEYWORDS:
            if kw.lower() in name_lower:
                version_status = "final"
                break
        if version_status == "unknown":
            for kw in VERSION_DRAFT_KEYWORDS:
                if kw.lower() in name_lower:
                    version_status = "draft"
                    break

        # True source candidate check
        # Generated artifacts are NOT true source candidates
        is_true_source = matched_type not in ("unknown", "reviewer_note", "literature", "sota")
        path_lower = sf.relative_path.lower()
        artifact_indicators = ["artifacts", "phase", "generated", "report", "closeout", "output", "artifact"]
        if any(ind in path_lower for ind in artifact_indicators):
            is_true_source = False
            if matched_type not in ("unknown", "reviewer_note"):
                best_confidence *= 0.7  # Reduce confidence for generated paths

        if matched_type is None:
            matched_type = "unknown"
            best_confidence = 0.1
            reason = "No document type keywords matched"
        else:
            reason = f"Matched keywords: {matched_keywords} → {matched_type}"

        requires_human = best_confidence < 0.80 or matched_type == "unknown"

        candidates.append(ClassificationCandidate(
            file_id=sf.file_id,
            document_type=matched_type,
            confidence=round(best_confidence, 3),
            matched_keywords=matched_keywords,
            reason=reason,
            requires_human_confirmation=requires_human,
            is_true_source_candidate=is_true_source and version_status == "final",
            version_status=version_status,
            notes=None,
        ))

    return candidates


# ── Source Documents Builder ────────────────────────────────────────────────────


def build_source_documents_from_candidates(
    candidates: list[ClassificationCandidate],
    scanned_files: list[ScannedFile],
) -> list[SourceDocumentOut]:
    """Build SourceDocument array from classification candidates."""
    file_map = {sf.file_id: sf for sf in scanned_files}
    documents: list[SourceDocumentOut] = []

    for c in candidates:
        sf = file_map.get(c.file_id)
        if sf is None:
            continue

        # Map document_type to source availability type
        # Only include if confidence >= 0.5
        if c.confidence < 0.5:
            availability = "requires_confirmation"
        else:
            availability = "available"

        # version_status: final → TRUE_SOURCE candidate, draft → PARTIAL_SOURCE
        if c.version_status == "final":
            version_status_str = "TRUE_SOURCE" if c.is_true_source_candidate else "PARTIAL_SOURCE"
        elif c.version_status == "draft":
            version_status_str = "PARTIAL_SOURCE"
        else:
            version_status_str = "SOURCE_UNAVAILABLE"

        documents.append(SourceDocumentOut(
            document_id=c.file_id,
            document_type=c.document_type if c.document_type != "unknown" else None,
            file_name=sf.file_name,
            source_path=sf.relative_path,
            version_status=version_status_str,
            availability=availability,
            is_true_source=c.is_true_source_candidate and c.confidence >= 0.8,
            classification_confidence=c.confidence,
            requires_human_confirmation=c.requires_human_confirmation,
            notes=c.reason,
        ))

    return documents


# ── Source Status Deriver ──────────────────────────────────────────────────────


def derive_source_status(
    candidates: list[ClassificationCandidate],
) -> tuple[SourceStatusOut, list[str]]:
    """Derive the 9 source availability flags from classification candidates.

    Returns (source_status, warnings).
    """
    warnings: list[str] = []

    doc_types = {c.document_type for c in candidates if c.document_type != "unknown" and c.confidence >= 0.5}
    all_candidates_by_type: dict[str, list[ClassificationCandidate]] = {}
    for c in candidates:
        if c.document_type != "unknown":
            all_candidates_by_type.setdefault(c.document_type, []).append(c)

    def has_type(doc_type: str) -> bool:
        return any(t == doc_type for t in doc_types)

    def has_any(types: list[str]) -> bool:
        return any(has_type(t) for t in types)

    ifu_available = has_any(["ifu"])
    cer_available = has_any(["cer", "cep"])
    rmf_available = has_type("rmf")
    risk_related_available = has_any(["risk_related", "rmf"])
    equivalence_available = has_any(["equivalence"])
    pmcf_available = has_type("pmcf")
    pms_available = has_type("pms")
    gspr_available = has_type("gspr")
    sscp_available = has_type("sscp")

    # Warnings for missing critical sources
    if not ifu_available:
        warnings.append("IFU source not found — IFU-CER linkage review blocked")
    if not cer_available:
        warnings.append("CER/CEP source not found — clinical evaluation source unavailable")
    if not rmf_available:
        warnings.append("ISO 14971 RMF not found — risk management review will be limited")
    if not equivalence_available:
        warnings.append("Equivalence comparison table not found — equivalence workbench will be limited")

    status = SourceStatusOut(
        ifu_available=ifu_available,
        cer_available=cer_available,
        rmf_available=rmf_available,
        risk_related_source_available=risk_related_available,
        equivalence_available=equivalence_available,
        pmcf_available=pmcf_available,
        pms_available=pms_available,
        gspr_available=gspr_available,
        sscp_available=sscp_available,
    )

    return status, warnings


# ── Available Source Request Builder ──────────────────────────────────────────


def build_available_source_request(
    project_id: str,
    project_name: str,
    source_package_path: str,
    source_status: SourceStatusOut,
    source_documents: list[SourceDocumentOut],
) -> tuple[dict[str, Any], list[str]]:
    """Build available-source workflow request dict from bridge output.

    Returns (request_dict, warnings).
    """
    warnings: list[str] = []

    # Map source_status to dict
    status_dict = source_status.model_dump()

    # Determine recommended action based on source availability
    core_sources = [source_status.ifu_available, source_status.cer_available]
    if not any(core_sources):
        recommended_action = "HOLD_FOR_SOURCE_CONFIRMATION"
        warnings.append("Core sources (IFU/CER) missing — recommended to HOLD until source confirmation")
    else:
        recommended_action = "READY_TO_RUN"

    # Review scope — always the 6 bounded scope items
    review_scope = [
        "source_inventory",
        "ifu_cer_linkage",
        "rmf_gap_impact",
        "equivalence_workbench",
        "pmcf_linkage_workbench",
        "reviewer_packet",
    ]

    # Build source_documents list compatible with AvailableSourceWorkflowRequest
    source_docs_list = []
    for sd in source_documents:
        source_docs_list.append({
            "document_id": sd.document_id,
            "document_type": sd.document_type,
            "file_name": sd.file_name,
            "source_path": sd.source_path,
            "version_status": sd.version_status,
            "availability": sd.availability,
            "is_true_source": sd.is_true_source,
            "notes": sd.notes,
        })

    request = {
        "project_id": project_id,
        "project_name": project_name,
        "workflow_mode": "AVAILABLE_SOURCE_LIMITED",
        "source_package_ref": source_package_path,
        "known_limitations_ref": None,
        "review_scope": review_scope,
        # Boundaries — always False (non-claims)
        "official_cear_allowed": False,
        "final_regulatory_decision_allowed": False,
        "production_claim_allowed": False,
        # Source status
        **status_dict,
        # Source documents
        "source_documents": source_docs_list,
    }

    return request, warnings


# ── Human Confirmation Packet Builder ────────────────────────────────────────


def build_human_confirmation_packet(
    project_id: str,
    project_name: str,
    source_package_path: str,
    scanned_files: list[ScannedFile],
    classification_candidates: list[ClassificationCandidate],
    source_documents: list[SourceDocumentOut],
    source_status: SourceStatusOut,
    available_source_request: dict[str, Any] | None,
    warnings: list[str],
) -> HumanConfirmationPacket:
    """Build human confirmation packet for operator review."""
    high_conf = [c for c in classification_candidates if c.confidence >= 0.80]
    low_conf = [c for c in classification_candidates if c.confidence < 0.80]

    # Determine status
    if not source_package_path:
        status = BridgeStatus.HOLD_FOR_SOURCE_PACKAGE_PATH
    elif not scanned_files:
        # Empty package: path is valid but no supported files found
        status = BridgeStatus.HOLD_FOR_SOURCE_PACKAGE_PATH
    elif any(c.requires_human_confirmation for c in classification_candidates):
        status = BridgeStatus.HOLD_FOR_CLASSIFICATION_CONFIRMATION
    elif available_source_request is not None:
        status = BridgeStatus.READY_TO_RUN_AVAILABLE_SOURCE_WORKFLOW
    else:
        status = BridgeStatus.READY_FOR_HUMAN_CONFIRMATION

    # Recommended actions
    recommended_actions: list[str] = []
    if status == BridgeStatus.HOLD_FOR_SOURCE_PACKAGE_PATH:
        if not scanned_files:
            recommended_actions.append("Provide a valid source package with at least one supported document file")
            recommended_actions.append("CONFIRM: source_package_path points to the intended project folder")
            recommended_actions.append("Do NOT run available-source workflow until source documents are present")
        else:
            recommended_actions.append("Provide a valid source package path")
    if not source_status.ifu_available:
        recommended_actions.append("CONFIRM: IFU source is intentionally missing before proceeding")
    if not source_status.cer_available:
        recommended_actions.append("CONFIRM: CER/CEP source is intentionally missing before proceeding")
    if status == BridgeStatus.HOLD_FOR_CLASSIFICATION_CONFIRMATION:
        recommended_actions.append("REVIEW: Some classification candidates require human confirmation")
        recommended_actions.append("VERIFY document types before running available-source workflow")
    if status == BridgeStatus.READY_TO_RUN_AVAILABLE_SOURCE_WORKFLOW:
        recommended_actions.append("RUN: Available-source bounded workflow is ready")
        recommended_actions.append("NOTE: This will NOT generate official CEAR or final regulatory decision")

    # Non-claims
    non_claims = {
        "official_cear_allowed": "FALSE — official CEAR will NOT be generated",
        "final_regulatory_decision_allowed": "FALSE — final regulatory decision will NOT be made",
        "production_claim_allowed": "FALSE — production readiness will NOT be claimed",
        "obsidian_backflow": "NOT executed",
        "nocodb_backflow": "NOT executed",
        "reusable_asset": "NOT created",
        "reuse_allowed": "NOT set",
    }

    request_preview = AvailableSourceRequestPreview(
        project_id=project_id,
        project_name=project_name,
        workflow_mode="AVAILABLE_SOURCE_LIMITED",
        source_package_ref=source_package_path,
        review_scope=["source_inventory", "ifu_cer_linkage", "rmf_gap_impact", "equivalence_workbench", "pmcf_linkage_workbench", "reviewer_packet"],
        official_cear_allowed=False,
        final_regulatory_decision_allowed=False,
        production_claim_allowed=False,
        source_status=source_status,
        source_documents_count=len(source_documents),
        human_confirmation_required=status == BridgeStatus.READY_FOR_HUMAN_CONFIRMATION,
    )

    return HumanConfirmationPacket(
        status=status.value,
        project_id=project_id,
        project_name=project_name,
        source_package_path=source_package_path,
        scanned_files_count=len(scanned_files),
        high_confidence_count=len(high_conf),
        low_confidence_count=len(low_conf),
        classification_candidates=classification_candidates,
        source_status=source_status,
        source_documents_preview=source_documents[:20],  # Limit preview to 20
        available_source_request_preview=request_preview,
        warnings=warnings,
        recommended_actions=recommended_actions,
        generated_at=datetime.now(timezone.utc).isoformat(),
        non_claims=non_claims,
    )


# ── API Endpoints ──────────────────────────────────────────────────────────────


@router.post("/scan", response_model=SourcePackageScanResponse)
async def scan_source_package_endpoint(request: SourcePackageScanRequest):
    """Scan a source package folder and return discovered files with classification.

    This endpoint:
    1. Validates the source package path (safety + existence)
    2. Recursively scans for supported file types
    3. Classifies documents by filename/path keywords
    4. Returns classification candidates (not confirmed — human review required)

    Does NOT:
    - Read full file content
    - Execute LLM classification
    - Run any workflow
    - Create any assets
    """
    scan_id = f"SCAN-{uuid.uuid4().hex[:12].upper()}"

    # Validate path
    is_valid, error = validate_source_package_path(request.source_package_path)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error)

    # Scan
    scanned_files, scan_warnings = scan_source_package(
        request.source_package_path,
        recursive=request.recursive,
        max_files=request.max_files,
    )

    if not scanned_files:
        scan_warnings.append("No supported files found in source package path")

    # Classify
    classification_candidates = classify_document_candidates(scanned_files)

    # Build source documents
    source_documents = build_source_documents_from_candidates(classification_candidates, scanned_files)

    # Derive source status
    source_status, status_warnings = derive_source_status(classification_candidates)

    all_warnings = scan_warnings + status_warnings

    return SourcePackageScanResponse(
        scan_id=scan_id,
        project_id=request.project_id,
        project_name=request.project_name,
        source_package_path=request.source_package_path,
        scanned_files=scanned_files,
        classification_candidates=classification_candidates,
        source_documents=source_documents,
        source_status=source_status,
        status=BridgeStatus.READY_FOR_HUMAN_CONFIRMATION.value,
        warnings=all_warnings,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )


@router.post("/build-available-source-request", response_model=AvailableSourceRequestBuildResponse)
async def build_available_source_request_endpoint(request: SourcePackageScanRequest):
    """Build available-source workflow request from source package scan.

    Combines scan → classify → source_documents → source_status → request builder.
    Returns full request dict ready for POST to /workflows/available-source/run.

    Does NOT POST to the workflow endpoint — caller must do that after confirmation.
    """
    build_id = f"BUILD-{uuid.uuid4().hex[:12].upper()}"

    # Validate and scan
    is_valid, error = validate_source_package_path(request.source_package_path)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error)

    scanned_files, scan_warnings = scan_source_package(
        request.source_package_path,
        recursive=request.recursive,
        max_files=request.max_files,
    )

    classification_candidates = classify_document_candidates(scanned_files)
    source_documents = build_source_documents_from_candidates(classification_candidates, scanned_files)
    source_status, status_warnings = derive_source_status(classification_candidates)

    # Build request
    available_source_request, request_warnings = build_available_source_request(
        request.project_id,
        request.project_name,
        request.source_package_path,
        source_status,
        source_documents,
    )

    # Build confirmation packet
    all_warnings = scan_warnings + status_warnings + request_warnings
    confirmation_packet = build_human_confirmation_packet(
        request.project_id,
        request.project_name,
        request.source_package_path,
        scanned_files,
        classification_candidates,
        source_documents,
        source_status,
        available_source_request,
        all_warnings,
    )

    return AvailableSourceRequestBuildResponse(
        build_id=build_id,
        project_id=request.project_id,
        project_status=confirmation_packet.status,
        source_status=source_status,
        source_documents=source_documents,
        available_source_request=available_source_request,
        human_confirmation_packet=confirmation_packet,
        warnings=all_warnings,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )


@router.post("/prepare", response_model=SourcePackagePrepareResponse)
async def prepare_source_package(request: SourcePackageScanRequest):
    """Combined endpoint: scan + classify + build + confirmation packet.

    Returns everything needed to make a human decision about running
    the available-source bounded workflow.

    This is the primary Phase 19C endpoint for the intake bridge.
    """
    prepare_id = f"PREP-{uuid.uuid4().hex[:12].upper()}"

    # Validate
    is_valid, error = validate_source_package_path(request.source_package_path)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error)

    # Scan
    scanned_files, scan_warnings = scan_source_package(
        request.source_package_path,
        recursive=request.recursive,
        max_files=request.max_files,
    )

    if not scanned_files:
        return SourcePackagePrepareResponse(
            prepare_id=prepare_id,
            project_id=request.project_id,
            project_name=request.project_name,
            source_package_path=request.source_package_path,
            status=BridgeStatus.HOLD_FOR_SOURCE_PACKAGE_PATH.value,
            scanned_files_count=0,
            classification_candidates_count=0,
            source_documents_count=0,
            source_status=SourceStatusOut(),
            available_source_request=None,
            human_confirmation_packet=HumanConfirmationPacket(
                status=BridgeStatus.HOLD_FOR_SOURCE_PACKAGE_PATH.value,
                project_id=request.project_id,
                project_name=request.project_name,
                source_package_path=request.source_package_path,
                scanned_files_count=0,
                high_confidence_count=0,
                low_confidence_count=0,
                classification_candidates=[],
                source_status=SourceStatusOut(),
                source_documents_preview=[],
                available_source_request_preview=AvailableSourceRequestPreview(
                    project_id=request.project_id,
                    project_name=request.project_name,
                    source_package_ref=request.source_package_path,
                    review_scope=[],
                    source_status=SourceStatusOut(),
                    source_documents_count=0,
                    human_confirmation_required=True,
                ),
                warnings=["No supported files found in source package path"],
                recommended_actions=["Verify source package path contains supported document types"],
                generated_at=datetime.now(timezone.utc).isoformat(),
                non_claims={
                    "official_cear_allowed": "FALSE",
                    "final_regulatory_decision_allowed": "FALSE",
                    "production_claim_allowed": "FALSE",
                },
            ),
            warnings=["No supported files found"],
            generated_at=datetime.now(timezone.utc).isoformat(),
        )

    # Classify
    classification_candidates = classify_document_candidates(scanned_files)
    source_documents = build_source_documents_from_candidates(classification_candidates, scanned_files)
    source_status, status_warnings = derive_source_status(classification_candidates)

    # Build request
    available_source_request, request_warnings = build_available_source_request(
        request.project_id,
        request.project_name,
        request.source_package_path,
        source_status,
        source_documents,
    )

    all_warnings = scan_warnings + status_warnings + request_warnings
    confirmation_packet = build_human_confirmation_packet(
        request.project_id,
        request.project_name,
        request.source_package_path,
        scanned_files,
        classification_candidates,
        source_documents,
        source_status,
        available_source_request,
        all_warnings,
    )

    return SourcePackagePrepareResponse(
        prepare_id=prepare_id,
        project_id=request.project_id,
        project_name=request.project_name,
        source_package_path=request.source_package_path,
        status=confirmation_packet.status,
        scanned_files_count=len(scanned_files),
        classification_candidates_count=len(classification_candidates),
        source_documents_count=len(source_documents),
        source_status=source_status,
        available_source_request=available_source_request,
        human_confirmation_packet=confirmation_packet,
        warnings=all_warnings,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )
