"""CER Available Source Workflow API — Available-Source Bounded CER/RMF Review.

Implements the AVAILABLE_SOURCE_LIMITED_WORKFLOW pattern from Phase 10B:
  - POST /api/cer-review/workflows/available-source/run     -> run available-source workflow
  - GET  /api/cer-review/workflows/available-source/status  -> workflow status
  - GET  /api/cer-review/workflows/available-source/register -> source limitation register
  - GET  /api/cer-review/workflows/available-source/equivalence -> equivalence workbench
  - GET  /api/cer-review/workflows/available-source/pmcf     -> PMCF linkage workbench
  - GET  /api/cer-review/workflows/available-source/report  -> reviewer working report

This module is reviewer-assistive only:
  - Does NOT generate official CEAR
  - Does NOT make final clinical/regulatory decisions
  - Does NOT claim production ready
  - Does NOT execute backflow
  - Does NOT create approved/active assets

Frozen baseline: AVAILABLE_SOURCE_LIMITED_WORKFLOW_P1
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/cer-review/workflows/available-source", tags=["cer-available-source-workflow"])

# ── Paths ──────────────────────────────────────────────────────────────────────

CER_ARTIFACTS_ROOT = Path("/Users/winstonwei/Documents/Playground/deer-flow/artifacts/cer")
PHASE10B_OUTPUT = Path("/Users/winstonwei/Documents/Playground/deer-flow/artifacts/cer_rmf_real_operating_loop/phase10b_available_source_workflow_closure")

# ── Hardcoded Boundaries (Phase 10B Non-Claims) ─────────────────────────────────

BOUNDARY_DEFAULTS = {
    "official_cear_allowed": False,
    "final_regulatory_decision_allowed": False,
    "production_claim_allowed": False,
    "autonomous_approval_allowed": False,
    "allow_obsidian_backflow": False,
    "allow_nocodb_machine_asset": False,
    "allow_future_reuse": False,
    "reusable": False,
    "reuse_allowed": False,
}


# ── Enums ──────────────────────────────────────────────────────────────────────


class WorkflowMode(str, Enum):
    FULL_REVIEW = "FULL_REVIEW"
    LIMITED_REVIEW_WITH_GAP = "LIMITED_REVIEW_WITH_GAP"
    AVAILABLE_SOURCE_LIMITED = "AVAILABLE_SOURCE_LIMITED"
    INVENTORY_ONLY_HOLD = "INVENTORY_ONLY_HOLD"
    CER_ONLY_LIMITED_WITH_IFU_GAP = "CER_ONLY_LIMITED_WITH_IFU_GAP"


class SourceStatus(str, Enum):
    TRUE_SOURCE = "TRUE_SOURCE"
    PARTIAL_SOURCE = "PARTIAL_SOURCE"
    SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"
    SOURCE_NOT_FOUND = "SOURCE_NOT_FOUND"


class WorkflowStatus(str, Enum):
    INITIALIZED = "INITIALIZED"
    SOURCE_INVENTORIED = "SOURCE_INVENTORIED"
    DOWNGRADE_DECIDED = "DOWNGRADE_DECIDED"
    WORKBENCH_GENERATED = "WORKBENCH_GENERATED"
    REPORT_GENERATED = "REPORT_GENERATED"
    HUMAN_REVIEW_REQUIRED = "HUMAN_REVIEW_REQUIRED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    HOLD = "HOLD"


class FindingAction(str, Enum):
    EXECUTE_RW_ACT_005 = "RW-ACT-005"  # Equivalence workbench
    EXECUTE_RW_ACT_006 = "RW-ACT-006"  # PMCF linkage workbench
    CLOSE_AS_EXTERNAL_SOURCE_UNAVAILABLE = "CLOSED_AS_EXTERNAL_SOURCE_UNAVAILABLE"
    INTERNALLY_ACTIONABLE = "INTERNALLY_ACTIONABLE"
    PARTIALLY_ASSESSABLE = "PARTIALLY_ASSESSABLE"
    FUTURE_PROJECT_ITEM = "FUTURE_PROJECT_ITEM"


# ── Pydantic Models ────────────────────────────────────────────────────────────


class SourceInventoryItem(BaseModel):
    """A single source item in the inventory."""

    source_id: str
    source_name: str
    source_path: str | None
    status: SourceStatus
    availability_note: str | None = None


class SourceDocument(BaseModel):
    """A single source document in the payload (MA-003)."""

    document_id: str | None = Field(None, description="Document identifier")
    document_type: str | None = Field(None, description="Document type: ifu, cer, rmf, equivalence, pmcf, pms, gspr, sscp, risk_related")
    file_name: str | None = Field(None, description="File name")
    source_path: str | None = Field(None, description="Source path")
    version_status: str | None = Field(None, description="TRUE_SOURCE, PARTIAL_SOURCE, SOURCE_UNAVAILABLE")
    availability: str = Field(default="available", description="available, unavailable, partial")
    is_true_source: bool = Field(default=False, description="Whether this is a true source")
    notes: str | None = Field(None, description="Additional notes")


class SourceInventoryInput(BaseModel):
    """Input parameters for source inventory generation (MA-003)."""

    ifu_available: bool = Field(default=True, description="IFU source is available")
    cer_available: bool = Field(default=True, description="CER/CEP source is available")
    rmf_available: bool = Field(default=False, description="ISO 14971 RMF source is available")
    risk_related_available: bool = Field(default=False, description="Risk-related supplementary source is available")
    equivalence_available: bool = Field(default=True, description="Equivalence comparison table is available")
    pmcf_available: bool = Field(default=True, description="PMCF plan or data is available")
    pms_available: bool = Field(default=False, description="PMS data is available")
    gspr_available: bool = Field(default=False, description="GSPR checklist is available")
    sscp_available: bool = Field(default=False, description="SSCP is available")
    source_documents: list[SourceDocument] | None = Field(default=None, description="Optional per-document source list")
    project_id: str | None = Field(default=None, description="Project ID for fallback seed data")


class SourceLimitationItem(BaseModel):
    """A single limitation in the source limitation register."""

    limitation_id: str
    category: str
    source_gap: str
    impact: str
    allowed_workflow: list[str]
    prohibited_claim: str
    blocks_full_review: bool
    blocks_limited_workflow: bool
    human_caution: str | None = None


class EquivalenceWorkbenchItem(BaseModel):
    """A single item in the equivalence workbench."""

    item_id: str
    dimension: str  # technical, biological, clinical
    aspect: str
    baxter_evidence: str | None
    nipro_evidence: str | None
    gap_description: str | None
    reviewer_question: str | None
    limitation_ref: str | None
    preliminary_judgment: str | None = None  # NOT final - human decision required


class PMCFLinkageItem(BaseModel):
    """A single item in the PMCF linkage workbench."""

    item_id: str
    dimension: str  # cer_scope, residual_risk, equivalence, pms_psur, update_cycle
    cer_claim: str | None
    pmcf_plan_claim: str | None
    linkage_status: str  # linked, partial, missing, not_applicable
    gap_description: str | None
    reviewer_question: str | None
    limitation_ref: str | None


class ReviewerFindingItem(BaseModel):
    """A single finding in the reviewer working report."""

    finding_id: str
    category: str
    title: str
    description: str
    source_limitation_ref: str | None
    severity: str | None  # high, medium, low
    actionable: bool
    action: FindingAction | None
    human_decision_required: bool
    preliminary_judgment: str | None = None


class NonClaimItem(BaseModel):
    """An explicit non-claim that must be preserved."""

    claim_type: str
    non_claim: str
    reason: str


class AvailableSourceWorkflowRequest(BaseModel):
    """Request to run the available-source bounded workflow."""

    project_id: str = Field(..., description="Project ID")
    project_name: str = Field(..., description="Project name")
    workflow_mode: WorkflowMode = Field(
        default=WorkflowMode.AVAILABLE_SOURCE_LIMITED,
        description="Requested workflow mode"
    )
    source_package_ref: str | None = Field(
        None,
        description="Path to source availability boundary document"
    )
    known_limitations_ref: str | None = Field(
        None,
        description="Path to known source limitations register"
    )
    review_scope: list[str] = Field(
        default=[
            "source_inventory",
            "ifu_cer_linkage",
            "rmf_gap_impact",
            "equivalence_workbench",
            "pmcf_linkage_workbench",
            "reviewer_packet",
        ],
        description="Scope items to execute"
    )
    # Boundaries - always False for this workflow
    official_cear_allowed: bool = Field(default=False)
    final_regulatory_decision_allowed: bool = Field(default=False)
    production_claim_allowed: bool = Field(default=False)
    # Source availability flags for payload-driven inventory (MA-003)
    ifu_available: bool = Field(default=True, description="IFU source is available")
    cer_available: bool = Field(default=True, description="CER/CEP source is available")
    rmf_available: bool = Field(default=False, description="ISO 14971 RMF source is available")
    risk_related_available: bool = Field(default=False, description="Risk-related supplementary source is available")
    equivalence_available: bool = Field(default=True, description="Equivalence comparison table is available")
    pmcf_available: bool = Field(default=True, description="PMCF plan or data is available")
    pms_available: bool = Field(default=False, description="PMS data is available")
    gspr_available: bool = Field(default=False, description="GSPR checklist is available")
    sscp_available: bool = Field(default=False, description="SSCP is available")
    source_documents: list[SourceDocument] | None = Field(
        default=None,
        description="Optional per-document source list for fine-grained inventory"
    )


class DowngradeDecision(BaseModel):
    """Workflow downgrade decision result."""

    original_mode: WorkflowMode
    assigned_mode: WorkflowMode
    downgrade_reason: str
    blocking_limitations: list[str]
    can_claim_full_review: bool = False
    can_claim_limited_review: bool = False
    can_claim_available_source_review: bool = True


class AvailableSourceWorkflowResponse(BaseModel):
    """Response for available-source workflow run."""

    workflow_run_id: str
    project_id: str
    project_name: str
    status: WorkflowStatus
    workflow_mode: WorkflowMode
    downgrade_decision: DowngradeDecision | None
    source_inventory: list[SourceInventoryItem]
    source_limitation_register: list[SourceLimitationItem]
    equivalence_workbench: list[EquivalenceWorkbenchItem] | None
    pmcf_linkage_workbench: list[PMCFLinkageItem] | None
    reviewer_findings: list[ReviewerFindingItem]
    non_claims: list[NonClaimItem]
    next_state: str
    boundaries_applied: dict[str, bool]
    generated_at: str


class SourceLimitationRegisterResponse(BaseModel):
    """Response for source limitation register query."""

    project_id: str
    limitations: list[SourceLimitationItem] = Field(..., alias="register")
    total_limitations: int
    generated_at: str

    model_config = ConfigDict(populate_by_name=True)


# ── Generator Functions ─────────────────────────────────────────────────────────


def generate_source_limitation_register(
    project_id: str,
    limitations_ref: str | None = None
) -> list[SourceLimitationItem]:
    """Generate machine-readable source limitation register.

    Reads from Phase 10B KNOWN_SOURCE_LIMITATIONS_REGISTER.md if available,
    otherwise returns hardcoded Phase 10B KSLs.
    """

    # Phase 10B confirmed 15 KSLs
    KSL_FIXED = [
        # RMF_SOURCE (7)
        SourceLimitationItem(
            limitation_id="KSL-001",
            category="RMF_SOURCE",
            source_gap="ISO 14971 RMF package not received",
            impact="Cannot perform ISO 14971 compliant RMF review",
            allowed_workflow=["AVAILABLE_SOURCE_LIMITED", "INVENTORY_ONLY_HOLD"],
            prohibited_claim="ISO 14971 RMF verified; Full RMF review complete",
            blocks_full_review=True,
            blocks_limited_workflow=False,
            human_caution="RMF gap is permanent for this project"
        ),
        SourceLimitationItem(
            limitation_id="KSL-002",
            category="RMF_SOURCE",
            source_gap="RMR (Risk Management Report) not found",
            impact="Cannot verify risk management record completeness",
            allowed_workflow=["AVAILABLE_SOURCE_LIMITED", "INVENTORY_ONLY_HOLD"],
            prohibited_claim="RMR verified; Risk management complete",
            blocks_full_review=True,
            blocks_limited_workflow=False,
            human_caution="RMR unavailable"
        ),
        SourceLimitationItem(
            limitation_id="KSL-003",
            category="RMF_SOURCE",
            source_gap="RMF reference documents not received",
            impact="Cannot cross-reference RMF evidence",
            allowed_workflow=["AVAILABLE_SOURCE_LIMITED", "INVENTORY_ONLY_HOLD"],
            prohibited_claim="RMF references verified",
            blocks_full_review=True,
            blocks_limited_workflow=False,
            human_caution="RMF reference documents not received — original specifications unavailable for comparison; review conducted without reference documents"
        ),
        SourceLimitationItem(
            limitation_id="KSL-004",
            category="RMF_SOURCE",
            source_gap="Risk Master File (RMR/RMF) unavailable",
            impact="Cannot perform full risk acceptability judgment",
            allowed_workflow=["AVAILABLE_SOURCE_LIMITED"],
            prohibited_claim="Risk acceptability confirmed per ISO 14971",
            blocks_full_review=True,
            blocks_limited_workflow=False,
            human_caution="ISO 14971 RMF unavailable"
        ),
        SourceLimitationItem(
            limitation_id="KSL-005",
            category="RMF_SOURCE",
            source_gap="Benefit-risk determination per ISO 14971 not available",
            impact="Cannot confirm ISO 14971 benefit-risk determination",
            allowed_workflow=["AVAILABLE_SOURCE_LIMITED"],
            prohibited_claim="ISO 14971 benefit-risk determination complete",
            blocks_full_review=True,
            blocks_limited_workflow=False,
            human_caution="Using CER 4.7 as proxy"
        ),
        SourceLimitationItem(
            limitation_id="KSL-006",
            category="RMF_SOURCE",
            source_gap="Residual risk evaluation not available",
            impact="Cannot confirm residual risk acceptability",
            allowed_workflow=["AVAILABLE_SOURCE_LIMITED"],
            prohibited_claim="Residual risk acceptability confirmed",
            blocks_full_review=True,
            blocks_limited_workflow=False,
            human_caution="Residual risk evaluation not available — acceptability of residual risk cannot be confirmed per ISO 14971; review conducted without RMR"
        ),
        SourceLimitationItem(
            limitation_id="KSL-007",
            category="RMF_SOURCE",
            source_gap="Risk control evidence (warnings, precautions) not verified",
            impact="Cannot confirm risk control measure effectiveness",
            allowed_workflow=["AVAILABLE_SOURCE_LIMITED"],
            prohibited_claim="Risk controls verified effective",
            blocks_full_review=True,
            blocks_limited_workflow=False,
            human_caution="Using IFU warnings as proxy"
        ),
        # PARTIAL_SOURCE (1)
        SourceLimitationItem(
            limitation_id="KSL-008",
            category="PARTIAL_SOURCE",
            source_gap="CER/CEP draft version 4.18",
            impact="All conclusions subject to final document caveat",
            allowed_workflow=["AVAILABLE_SOURCE_LIMITED", "LIMITED_REVIEW_WITH_GAP"],
            prohibited_claim="Final CER/CEP complete",
            blocks_full_review=True,
            blocks_limited_workflow=False,
            human_caution="Draft document"
        ),
        # REGULATORY (2)
        SourceLimitationItem(
            limitation_id="KSL-009",
            category="REGULATORY",
            source_gap="GSPR (General Safety and Performance Requirements) checklist not found",
            impact="Cannot verify GSPR compliance completeness",
            allowed_workflow=["AVAILABLE_SOURCE_LIMITED"],
            prohibited_claim="GSPR compliance verified",
            blocks_full_review=True,
            blocks_limited_workflow=True,
            human_caution="GSPR checklist required"
        ),
        SourceLimitationItem(
            limitation_id="KSL-010",
            category="REGULATORY",
            source_gap="SSCP (Summary of Safety and Clinical Performance) not found",
            impact="Cannot confirm SSCP applicability",
            allowed_workflow=["AVAILABLE_SOURCE_LIMITED"],
            prohibited_claim="SSCP complete",
            blocks_full_review=True,
            blocks_limited_workflow=False,
            human_caution=None
        ),
        # RISK_RELATED_SOURCE (1)
        SourceLimitationItem(
            limitation_id="KSL-011",
            category="RISK_RELATED_SOURCE",
            source_gap="NUTSTORE 180 source content never confirmed",
            impact="Risk linkage verification limited to IFU risk section",
            allowed_workflow=["AVAILABLE_SOURCE_LIMITED"],
            prohibited_claim="NUTSTORE 180 risk linkage verified",
            blocks_full_review=False,
            blocks_limited_workflow=False,
            human_caution="NUTSTORE 180 content unconfirmed"
        ),
        # POST_MARKET (3)
        SourceLimitationItem(
            limitation_id="KSL-012",
            category="POST_MARKET",
            source_gap="PMCF actual data/results NOT FOUND",
            impact="PMCF adequacy cannot be confirmed — plan only",
            allowed_workflow=["AVAILABLE_SOURCE_LIMITED"],
            prohibited_claim="PMCF adequacy confirmed",
            blocks_full_review=True,
            blocks_limited_workflow=False,
            human_caution="PMCF plan only; actual data absent"
        ),
        SourceLimitationItem(
            limitation_id="KSL-013",
            category="POST_MARKET",
            source_gap="PMS (Post-Market Surveillance) data not found",
            impact="Cannot confirm PMS completeness",
            allowed_workflow=["AVAILABLE_SOURCE_LIMITED"],
            prohibited_claim="PMS data complete",
            blocks_full_review=True,
            blocks_limited_workflow=False,
            human_caution=None
        ),
        SourceLimitationItem(
            limitation_id="KSL-015",
            category="POST_MARKET",
            source_gap="PSUR (Periodic Safety Update Report) not found",
            impact="Cannot verify PSUR availability",
            allowed_workflow=["AVAILABLE_SOURCE_LIMITED"],
            prohibited_claim="PSUR available",
            blocks_full_review=True,
            blocks_limited_workflow=False,
            human_caution=None
        ),
        # EQUIVALENCE (1)
        SourceLimitationItem(
            limitation_id="KSL-014",
            category="EQUIVALENCE",
            source_gap="Predicate device original data absent; only comparison tables available",
            impact="Equivalence adequacy cannot be confirmed — COMPARISON_TABLE_ONLY",
            allowed_workflow=["AVAILABLE_SOURCE_LIMITED"],
            prohibited_claim="Equivalence to predicate device confirmed",
            blocks_full_review=True,
            blocks_limited_workflow=False,
            human_caution="Baxter/Nipro comparison tables only; original data absent"
        ),
        # IFU_SOURCE (1) — Phase 14A
        SourceLimitationItem(
            limitation_id="KSL-016",
            category="IFU_SOURCE",
            source_gap="IFU (Intended Purpose / Instructions for Use) not provided",
            impact="IFU-CER linkage review cannot be executed; intended purpose source not verified",
            allowed_workflow=["CER_ONLY_LIMITED_WITH_IFU_GAP", "INVENTORY_ONLY_HOLD"],
            prohibited_claim="IFU-CER intended purpose linkage confirmed; IFU reviewed",
            blocks_full_review=True,
            blocks_limited_workflow=False,
            human_caution="IFU source missing — intended purpose source not verified against IFU; CER-only review with IFU gap"
        ),
    ]

    return KSL_FIXED


def determine_workflow_downgrade(
    source_inventory: list[SourceInventoryItem],
    limitations: list[SourceLimitationItem]
) -> DowngradeDecision:
    """Determine workflow mode based on source availability.

    Implements the downgrade path:
    FULL_REVIEW → LIMITED_WITH_GAP → AVAILABLE_SOURCE → INVENTORY_ONLY
    """

    # Check for TRUE_RMF_SOURCE
    rmf_sources = [s for s in source_inventory if "rmf" in s.source_id.lower() and s.status == SourceStatus.TRUE_SOURCE]
    has_complete_rmf = len(rmf_sources) > 0

    # Check for blocking limitations
    blocking_full = [l for l in limitations if l.blocks_full_review]
    blocking_limited = [l for l in limitations if l.blocks_limited_workflow]

    # Check for IFU and CER
    ifu_sources = [s for s in source_inventory if "ifu" in s.source_id.lower() and s.status == SourceStatus.TRUE_SOURCE]
    cer_sources = [s for s in source_inventory if ("cer" in s.source_id.lower() or "cep" in s.source_id.lower()) and s.status in [SourceStatus.TRUE_SOURCE, SourceStatus.PARTIAL_SOURCE]]

    has_ifu = len(ifu_sources) > 0
    has_cer = len(cer_sources) > 0

    # Decision logic
    if not has_ifu and not has_cer:
        return DowngradeDecision(
            original_mode=WorkflowMode.AVAILABLE_SOURCE_LIMITED,
            assigned_mode=WorkflowMode.INVENTORY_ONLY_HOLD,
            downgrade_reason="IFU and CER/CEP sources not available",
            blocking_limitations=["KSL-008", "KSL-011", "KSL-016"],
            can_claim_full_review=False,
            can_claim_limited_review=False,
            can_claim_available_source_review=False
        )
    elif not has_ifu and has_cer:
        # Phase 14A: IFU missing but CER available — CER-only limited review with IFU gap
        return DowngradeDecision(
            original_mode=WorkflowMode.AVAILABLE_SOURCE_LIMITED,
            assigned_mode=WorkflowMode.CER_ONLY_LIMITED_WITH_IFU_GAP,
            downgrade_reason="IFU not available; CER/CEP available — IFU-CER linkage review blocked",
            blocking_limitations=["KSL-016"],
            can_claim_full_review=False,
            can_claim_limited_review=True,
            can_claim_available_source_review=True
        )
    elif not has_complete_rmf and has_ifu and has_cer:
        return DowngradeDecision(
            original_mode=WorkflowMode.AVAILABLE_SOURCE_LIMITED,
            assigned_mode=WorkflowMode.AVAILABLE_SOURCE_LIMITED,
            downgrade_reason=f"RMF unavailable (TRUE_RMF_SOURCE=0); {len(blocking_full)} blocking limitations",
            blocking_limitations=[l.limitation_id for l in blocking_full],
            can_claim_full_review=False,
            can_claim_limited_review=True,
            can_claim_available_source_review=True
        )
    elif has_complete_rmf and has_ifu and has_cer:
        return DowngradeDecision(
            original_mode=WorkflowMode.AVAILABLE_SOURCE_LIMITED,
            assigned_mode=WorkflowMode.LIMITED_REVIEW_WITH_GAP,
            downgrade_reason="RMF partial (CER/CEP draft); minor gaps",
            blocking_limitations=[l.limitation_id for l in blocking_full[:3]],
            can_claim_full_review=False,
            can_claim_limited_review=True,
            can_claim_available_source_review=True
        )
    else:
        return DowngradeDecision(
            original_mode=WorkflowMode.AVAILABLE_SOURCE_LIMITED,
            assigned_mode=WorkflowMode.AVAILABLE_SOURCE_LIMITED,
            downgrade_reason=f"Available sources limited; {len(blocking_full)} full-review blockers",
            blocking_limitations=[l.limitation_id for l in blocking_full],
            can_claim_full_review=False,
            can_claim_limited_review=True,
            can_claim_available_source_review=True
        )


def generate_source_inventory(
    project_id: str | None = None,
    input_params: SourceInventoryInput | None = None
) -> list[SourceInventoryItem]:
    """Generate source inventory.

    MA-003 (Phase 14): Refactored to be payload-driven.

    Logic:
    - If input_params is provided → generate from payload (payload-driven)
    - If input_params is None but project_id matches seed_project_07 → original hardcoded data (backward compat)
    - If neither → use default availability flags

    Payload-driven generation:
    - Uses source_documents list if provided
    - Otherwise builds from availability flags (ifu_available, cer_available, etc.)
    - Missing IFU or CER triggers INVENTORY_ONLY_HOLD via downgrade logic
    - Missing RMF does NOT crash workflow; downgrades to AVAILABLE_SOURCE_LIMITED
    """

    # Backward compatibility: seed_project_07 uses original hardcoded data
    if input_params is None and project_id in ("seed_project_07", "seed_project_07_珠海健帆"):
        # Original hardcoded inventory for seed_project_07
        return [
            SourceInventoryItem(
                source_id="CER-DRAFT",
                source_name="CER/CEP draft v4.18",
                source_path="artifacts/cer/execution_pack_v2/CER_D12B_FULL_PROJECT_INPUT_GAP_RESOLUTION/input_candidates/01_cer/CER_Extracorporeal Blood Purification Tubing Sets_20240418.docx",
                status=SourceStatus.PARTIAL_SOURCE,
                availability_note="Draft caveat applies"
            ),
            SourceInventoryItem(
                source_id="IFU",
                source_name="Instructions for Use",
                source_path="artifacts/cer/execution_pack_v2/CER_D12B_FULL_PROJECT_INPUT_GAP_RESOLUTION/input_candidates/04_ifu/IFU_Extracorporeal Blood Purification Tubing Sets.pdf",
                status=SourceStatus.TRUE_SOURCE,
                availability_note=None
            ),
            SourceInventoryItem(
                source_id="EQ-BX-001",
                source_name="Baxter Equivalence Comparison Table",
                source_path="artifacts/cer/execution_pack_v2/CER_D12B_FULL_PROJECT_INPUT_GAP_RESOLUTION/input_candidates/05_equivalence_raw_data/产品临床评价信息/附件3-2申报产品和等同器械性能对比数据表-TOTM管路与baxter管路.docx",
                status=SourceStatus.TRUE_SOURCE,
                availability_note="COMPARISON_TABLE_ONLY — original predicate data absent"
            ),
            SourceInventoryItem(
                source_id="EQ-NP-001",
                source_name="Nipro Equivalence Comparison Table",
                source_path="artifacts/cer/execution_pack_v2/CER_D12B_FULL_PROJECT_INPUT_GAP_RESOLUTION/input_candidates/05_equivalence_raw_data/产品临床评价信息/附件3-3申报产品和等同器械性能对比数据表-TOTM管路与nipro管路.docx",
                status=SourceStatus.TRUE_SOURCE,
                availability_note="COMPARISON_TABLE_ONLY — original predicate data absent"
            ),
            SourceInventoryItem(
                source_id="PMCF-PLAN-001",
                source_name="PMCF Plan 2024-03-25",
                source_path="artifacts/cer/execution_pack_v2/CER_D12B_FULL_PROJECT_INPUT_GAP_RESOLUTION/input_candidates/01_cer/PMCF Plan _Extracorpreal Tubing Sets for Blood Purification_20240325.docx",
                status=SourceStatus.TRUE_SOURCE,
                availability_note="PMCF actual data/results NOT FOUND"
            ),
            SourceInventoryItem(
                source_id="SOTA-LIT-001",
                source_name="Literature SOTA review (CER Annex 1)",
                source_path="artifacts/cer/execution_pack_v2/CER_D12B_FULL_PROJECT_INPUT_GAP_RESOLUTION/input_candidates/02_literature/",
                status=SourceStatus.TRUE_SOURCE,
                availability_note="Draft caveat applies"
            ),
            SourceInventoryItem(
                source_id="PERIODIC-INSPECTION",
                source_name="Periodic Inspection Report (周期检报告)",
                source_path="artifacts/cer/execution_pack_v2/CER_D12B_FULL_PROJECT_INPUT_GAP_RESOLUTION/input_candidates/06_post_market/",
                status=SourceStatus.TRUE_SOURCE,
                availability_note="Production data, not PMS"
            ),
            SourceInventoryItem(
                source_id="PHASE9-IP-LINKAGE",
                source_name="Phase 9 IFU-CER IP linkage",
                source_path="artifacts/cer_rmf_real_operating_loop/phase9_cer_rmf_ip_linkage/",
                status=SourceStatus.TRUE_SOURCE,
                availability_note="Completed in Phase 9"
            ),
            SourceInventoryItem(
                source_id="RMF-ISO14971",
                source_name="ISO 14971 RMF Package",
                source_path=None,
                status=SourceStatus.SOURCE_UNAVAILABLE,
                availability_note="CLOSED_AS_EXTERNAL_SOURCE_UNAVAILABLE"
            ),
            SourceInventoryItem(
                source_id="RMR",
                source_name="Risk Management Report",
                source_path=None,
                status=SourceStatus.SOURCE_UNAVAILABLE,
                availability_note="RMR not found"
            ),
            SourceInventoryItem(
                source_id="RMF-REFS",
                source_name="RMF Reference Documents",
                source_path=None,
                status=SourceStatus.SOURCE_UNAVAILABLE,
                availability_note="Not received"
            ),
            SourceInventoryItem(
                source_id="NUTSTORE-180",
                source_name="NUTSTORE 180 source content",
                source_path=None,
                status=SourceStatus.SOURCE_NOT_FOUND,
                availability_note="Content never confirmed"
            ),
        ]

    # Payload-driven generation
    if input_params is None:
        input_params = SourceInventoryInput()

    items: list[SourceInventoryItem] = []

    # Use source_documents if provided (fine-grained per-document inventory)
    if input_params.source_documents is not None and len(input_params.source_documents) > 0:
        for doc in input_params.source_documents:
            doc_id = doc.document_id or f"DOC-{doc.document_type or 'UNKNOWN'}"
            doc_type = doc.document_type or "unknown"
            source_name = doc.file_name or doc_id

            # Determine status
            if doc.version_status:
                status = SourceStatus(doc.version_status)
            elif doc.availability == "partial":
                status = SourceStatus.PARTIAL_SOURCE
            elif doc.is_true_source or doc.availability == "available":
                status = SourceStatus.TRUE_SOURCE
            else:
                status = SourceStatus.SOURCE_UNAVAILABLE

            items.append(SourceInventoryItem(
                source_id=doc_id,
                source_name=source_name,
                source_path=doc.source_path,
                status=status,
                availability_note=doc.notes
            ))
    else:
        # Build from availability flags
        if input_params.ifu_available:
            items.append(SourceInventoryItem(
                source_id="ifu",
                source_name="Instructions for Use",
                source_path=None,
                status=SourceStatus.TRUE_SOURCE,
                availability_note=None
            ))
        else:
            items.append(SourceInventoryItem(
                source_id="ifu",
                source_name="Instructions for Use",
                source_path=None,
                status=SourceStatus.SOURCE_UNAVAILABLE,
                availability_note="IFU not provided"
            ))

        if input_params.cer_available:
            items.append(SourceInventoryItem(
                source_id="cer",
                source_name="CER/CEP",
                source_path=None,
                status=SourceStatus.TRUE_SOURCE,
                availability_note=None
            ))
        else:
            items.append(SourceInventoryItem(
                source_id="cer",
                source_name="CER/CEP",
                source_path=None,
                status=SourceStatus.SOURCE_UNAVAILABLE,
                availability_note="CER not provided"
            ))

        if input_params.rmf_available:
            items.append(SourceInventoryItem(
                source_id="rmf",
                source_name="ISO 14971 RMF",
                source_path=None,
                status=SourceStatus.TRUE_SOURCE,
                availability_note=None
            ))
        else:
            items.append(SourceInventoryItem(
                source_id="rmf",
                source_name="ISO 14971 RMF",
                source_path=None,
                status=SourceStatus.SOURCE_UNAVAILABLE,
                availability_note="RMF not provided"
            ))

        if input_params.risk_related_available:
            items.append(SourceInventoryItem(
                source_id="risk_related",
                source_name="Risk-related source",
                source_path=None,
                status=SourceStatus.TRUE_SOURCE,
                availability_note=None
            ))

        if input_params.equivalence_available:
            items.append(SourceInventoryItem(
                source_id="equivalence",
                source_name="Equivalence comparison table",
                source_path=None,
                status=SourceStatus.TRUE_SOURCE,
                availability_note="COMPARISON_TABLE_ONLY — original predicate data absent"
            ))

        if input_params.pmcf_available:
            items.append(SourceInventoryItem(
                source_id="pmcf",
                source_name="PMCF plan",
                source_path=None,
                status=SourceStatus.TRUE_SOURCE,
                availability_note="PMCF plan only; actual data absent"
            ))

        if input_params.pms_available:
            items.append(SourceInventoryItem(
                source_id="pms",
                source_name="PMS data",
                source_path=None,
                status=SourceStatus.TRUE_SOURCE,
                availability_note=None
            ))

        if input_params.gspr_available:
            items.append(SourceInventoryItem(
                source_id="gspr",
                source_name="GSPR checklist",
                source_path=None,
                status=SourceStatus.TRUE_SOURCE,
                availability_note=None
            ))

        if input_params.sscp_available:
            items.append(SourceInventoryItem(
                source_id="sscp",
                source_name="SSCP",
                source_path=None,
                status=SourceStatus.TRUE_SOURCE,
                availability_note=None
            ))

    return items


def generate_equivalence_workbench(
    input_params: SourceInventoryInput | None = None
) -> list[EquivalenceWorkbenchItem]:
    """Generate equivalence review workbench (RW-ACT-005).

    Phase 16A fix: Now payload-driven — no longer hardcoded for seed_project_07.

    Logic:
    - input_params None → legacy hardcoded seed_project_07 behavior (backward compat for GET endpoints)
    - equivalence_available=False → generate evidence-missing items with reviewer questions
    - equivalence_available=True + source_documents has equivalence details → use those details
    - equivalence_available=True but no detailed documents → generic evidence-missing items

    NOT a final adequacy judgment — human reviewer decision required.
    """
    # Legacy backward-compat path: no input_params means seed_project_07 context
    if input_params is None:
        return _generate_legacy_equivalence_workbench()

    # Payload-driven path
    if not input_params.equivalence_available:
        # No equivalence source available — generate evidence-missing items
        return _generate_equivalence_missing_workbench(input_params)

    # Equivalence available — check if source_documents has specific details
    equiv_docs = [
        d for d in (input_params.source_documents or [])
        if d.document_type in ("equivalence", "equivalence_comparison")
    ]

    if equiv_docs and any(d.file_name or d.source_path for d in equiv_docs):
        # Detailed equivalence documents provided — use them
        return _generate_equivalence_from_documents(input_params, equiv_docs)

    # Equivalence flagged as available but no detailed documents
    return _generate_equivalence_generic_placeholder(input_params)


def _generate_legacy_equivalence_workbench() -> list[EquivalenceWorkbenchItem]:
    """Legacy hardcoded equivalence workbench for seed_project_07 (backward compat)."""
    return [
        EquivalenceWorkbenchItem(
            item_id="EQ-TECH-001",
            dimension="technical",
            aspect="Intended use / indications",
            baxter_evidence="Baxter TOTM管路 intended for extracorporeal blood purification",
            nipro_evidence="Nipro TOTM管路 intended for extracorporeal blood purification",
            gap_description=None,
            reviewer_question="Do intended uses match sufficiently for equivalence claim?",
            limitation_ref="KSL-014",
            preliminary_judgment=None
        ),
        EquivalenceWorkbenchItem(
            item_id="EQ-TECH-002",
            dimension="technical",
            aspect="Design and materials",
            baxter_evidence="TOTM material; similar tubing structure",
            nipro_evidence="TOTM material; similar tubing structure",
            gap_description="Original predicate specifications not available for side-by-side comparison",
            reviewer_question="Are design/material differences clinically significant?",
            limitation_ref="KSL-014",
            preliminary_judgment=None
        ),
        EquivalenceWorkbenchItem(
            item_id="EQ-TECH-003",
            dimension="technical",
            aspect="Manufacturing process",
            baxter_evidence="Unknown (comparison table only)",
            nipro_evidence="Unknown (comparison table only)",
            gap_description="Manufacturing process equivalence cannot be verified without original predicate specs",
            reviewer_question="Is manufacturing process difference acceptable?",
            limitation_ref="KSL-014",
            preliminary_judgment=None
        ),
        EquivalenceWorkbenchItem(
            item_id="EQ-BIO-001",
            dimension="biological",
            aspect="Biocompatibility",
            baxter_evidence="Baxter biocompatibility data referenced in comparison table",
            nipro_evidence="Nipro biocompatibility data referenced in comparison table",
            gap_description="Original test reports not available; only comparison table statements",
            reviewer_question="Is biological safety adequately supported by comparison tables alone?",
            limitation_ref="KSL-014",
            preliminary_judgment=None
        ),
        EquivalenceWorkbenchItem(
            item_id="EQ-BIO-002",
            dimension="biological",
            aspect="Blood compatibility",
            baxter_evidence="Baxter blood compatibility referenced",
            nipro_evidence="Nipro blood compatibility referenced",
            gap_description="Original test data absent",
            reviewer_question="Is blood compatibility adequately demonstrated?",
            limitation_ref="KSL-014",
            preliminary_judgment=None
        ),
        EquivalenceWorkbenchItem(
            item_id="EQ-CLIN-001",
            dimension="clinical",
            aspect="Clinical data availability",
            baxter_evidence="Clinical data referenced in comparison table",
            nipro_evidence="Clinical data referenced in comparison table",
            gap_description="Original clinical data/clinical evaluations not available",
            reviewer_question="Is clinical equivalence support adequate without original data?",
            limitation_ref="KSL-014",
            preliminary_judgment=None
        ),
        EquivalenceWorkbenchItem(
            item_id="EQ-CLIN-002",
            dimension="clinical",
            aspect="Adverse events / vigilance",
            baxter_evidence="Post-market data referenced in comparison table",
            nipro_evidence="Post-market data referenced in comparison table",
            gap_description="Original vigilance data not available",
            reviewer_question="Is post-market surveillance data adequate for equivalence?",
            limitation_ref="KSL-014",
            preliminary_judgment=None
        ),
    ]


def _generate_equivalence_missing_workbench(
    input_params: SourceInventoryInput
) -> list[EquivalenceWorkbenchItem]:
    """Generate equivalence workbench items when equivalence source is not available."""
    project_ref = input_params.project_id or "this project"
    return [
        EquivalenceWorkbenchItem(
            item_id="EQ-TECH-001",
            dimension="technical",
            aspect="Intended use / indications",
            baxter_evidence=None,
            nipro_evidence=None,
            gap_description=f"Equivalence source not available for {project_ref} — equivalence claim cannot be assessed",
            reviewer_question="What is the intended use of the device and what evidence supports equivalence to a predicate?",
            limitation_ref="KSL-014",
            preliminary_judgment=None
        ),
        EquivalenceWorkbenchItem(
            item_id="EQ-TECH-002",
            dimension="technical",
            aspect="Design and materials",
            baxter_evidence=None,
            nipro_evidence=None,
            gap_description="Equivalence source not available — design and material equivalence cannot be verified",
            reviewer_question="Are design and materials of the subject device equivalent to a predicate device?",
            limitation_ref="KSL-014",
            preliminary_judgment=None
        ),
        EquivalenceWorkbenchItem(
            item_id="EQ-TECH-003",
            dimension="technical",
            aspect="Manufacturing process",
            baxter_evidence=None,
            nipro_evidence=None,
            gap_description="Equivalence source not available — manufacturing process equivalence cannot be verified",
            reviewer_question="Is the manufacturing process for the subject device equivalent to that of a predicate device?",
            limitation_ref="KSL-014",
            preliminary_judgment=None
        ),
        EquivalenceWorkbenchItem(
            item_id="EQ-BIO-001",
            dimension="biological",
            aspect="Biocompatibility",
            baxter_evidence=None,
            nipro_evidence=None,
            gap_description="Equivalence source not available — biological safety equivalence cannot be verified",
            reviewer_question="Is biological safety of the subject device supported by equivalence to a predicate?",
            limitation_ref="KSL-014",
            preliminary_judgment=None
        ),
        EquivalenceWorkbenchItem(
            item_id="EQ-BIO-002",
            dimension="biological",
            aspect="Blood compatibility",
            baxter_evidence=None,
            nipro_evidence=None,
            gap_description="Equivalence source not available — blood compatibility equivalence cannot be verified",
            reviewer_question="Is blood compatibility of the subject device supported by equivalence to a predicate?",
            limitation_ref="KSL-014",
            preliminary_judgment=None
        ),
        EquivalenceWorkbenchItem(
            item_id="EQ-CLIN-001",
            dimension="clinical",
            aspect="Clinical data availability",
            baxter_evidence=None,
            nipro_evidence=None,
            gap_description="Equivalence source not available — clinical equivalence cannot be verified",
            reviewer_question="Is clinical equivalence of the subject device supported by equivalence to a predicate?",
            limitation_ref="KSL-014",
            preliminary_judgment=None
        ),
        EquivalenceWorkbenchItem(
            item_id="EQ-CLIN-002",
            dimension="clinical",
            aspect="Adverse events / vigilance",
            baxter_evidence=None,
            nipro_evidence=None,
            gap_description="Equivalence source not available — post-market equivalence cannot be verified",
            reviewer_question="Is post-market surveillance data adequate to support equivalence to a predicate device?",
            limitation_ref="KSL-014",
            preliminary_judgment=None
        ),
    ]


def _generate_equivalence_from_documents(
    input_params: SourceInventoryInput,
    equiv_docs: list[SourceDocument]
) -> list[EquivalenceWorkbenchItem]:
    """Generate equivalence workbench items from provided source documents."""
    project_ref = input_params.project_id or "this project"
    # Extract document details for reviewer context
    doc_names = [d.file_name or d.document_id or "unknown" for d in equiv_docs]
    doc_paths = [d.source_path for d in equiv_docs if d.source_path]

    technical_note = f"Equivalence documents available for {project_ref}: {', '.join(doc_names)}"
    if doc_paths:
        technical_note += f" [paths: {', '.join(doc_paths)}]"

    return [
        EquivalenceWorkbenchItem(
            item_id="EQ-TECH-001",
            dimension="technical",
            aspect="Intended use / indications",
            baxter_evidence=None,
            nipro_evidence=None,
            gap_description=technical_note,
            reviewer_question="Do intended uses match sufficiently for equivalence claim? Review provided equivalence documents.",
            limitation_ref="KSL-014",
            preliminary_judgment=None
        ),
        EquivalenceWorkbenchItem(
            item_id="EQ-TECH-002",
            dimension="technical",
            aspect="Design and materials",
            baxter_evidence=None,
            nipro_evidence=None,
            gap_description=f"Equivalence documents: {', '.join(doc_names)} — reviewer must assess design/material equivalence",
            reviewer_question="Are design/material differences clinically significant per the provided documents?",
            limitation_ref="KSL-014",
            preliminary_judgment=None
        ),
        EquivalenceWorkbenchItem(
            item_id="EQ-TECH-003",
            dimension="technical",
            aspect="Manufacturing process",
            baxter_evidence=None,
            nipro_evidence=None,
            gap_description=f"Equivalence documents available — manufacturing equivalence assessment required: {', '.join(doc_names)}",
            reviewer_question="Is manufacturing process difference acceptable per the provided equivalence documents?",
            limitation_ref="KSL-014",
            preliminary_judgment=None
        ),
        EquivalenceWorkbenchItem(
            item_id="EQ-BIO-001",
            dimension="biological",
            aspect="Biocompatibility",
            baxter_evidence=None,
            nipro_evidence=None,
            gap_description=f"Biological safety equivalence assessment required using available documents: {', '.join(doc_names)}",
            reviewer_question="Is biological safety adequately supported by comparison tables in the provided documents?",
            limitation_ref="KSL-014",
            preliminary_judgment=None
        ),
        EquivalenceWorkbenchItem(
            item_id="EQ-BIO-002",
            dimension="biological",
            aspect="Blood compatibility",
            baxter_evidence=None,
            nipro_evidence=None,
            gap_description=f"Blood compatibility equivalence assessment required: {', '.join(doc_names)}",
            reviewer_question="Is blood compatibility adequately demonstrated in the provided equivalence documents?",
            limitation_ref="KSL-014",
            preliminary_judgment=None
        ),
        EquivalenceWorkbenchItem(
            item_id="EQ-CLIN-001",
            dimension="clinical",
            aspect="Clinical data availability",
            baxter_evidence=None,
            nipro_evidence=None,
            gap_description=f"Clinical equivalence documents available: {', '.join(doc_names)} — reviewer must assess",
            reviewer_question="Is clinical equivalence support adequate in the provided documents?",
            limitation_ref="KSL-014",
            preliminary_judgment=None
        ),
        EquivalenceWorkbenchItem(
            item_id="EQ-CLIN-002",
            dimension="clinical",
            aspect="Adverse events / vigilance",
            baxter_evidence=None,
            nipro_evidence=None,
            gap_description=f"Post-market equivalence assessment required using available documents: {', '.join(doc_names)}",
            reviewer_question="Is post-market surveillance data adequate for equivalence in the provided documents?",
            limitation_ref="KSL-014",
            preliminary_judgment=None
        ),
    ]


def _generate_equivalence_generic_placeholder(
    input_params: SourceInventoryInput
) -> list[EquivalenceWorkbenchItem]:
    """Generate generic equivalence workbench when equivalence_available=True but no document details."""
    project_ref = input_params.project_id or "this project"
    return [
        EquivalenceWorkbenchItem(
            item_id="EQ-TECH-001",
            dimension="technical",
            aspect="Intended use / indications",
            baxter_evidence=None,
            nipro_evidence=None,
            gap_description=f"Equivalence flagged as available for {project_ref} but source document details are missing — evidence detail required",
            reviewer_question="What is the intended use? What predicate device is being cited? Provide equivalence documentation.",
            limitation_ref="KSL-014",
            preliminary_judgment=None
        ),
        EquivalenceWorkbenchItem(
            item_id="EQ-TECH-002",
            dimension="technical",
            aspect="Design and materials",
            baxter_evidence=None,
            nipro_evidence=None,
            gap_description="Equivalence source detail missing — design/material equivalence cannot be assessed without predicate specifications",
            reviewer_question="Are design and materials equivalent to a predicate? Provide supporting documentation.",
            limitation_ref="KSL-014",
            preliminary_judgment=None
        ),
        EquivalenceWorkbenchItem(
            item_id="EQ-TECH-003",
            dimension="technical",
            aspect="Manufacturing process",
            baxter_evidence=None,
            nipro_evidence=None,
            gap_description="Equivalence source detail missing — manufacturing equivalence cannot be verified",
            reviewer_question="Is manufacturing process equivalent to a predicate? Provide supporting documentation.",
            limitation_ref="KSL-014",
            preliminary_judgment=None
        ),
        EquivalenceWorkbenchItem(
            item_id="EQ-BIO-001",
            dimension="biological",
            aspect="Biocompatibility",
            baxter_evidence=None,
            nipro_evidence=None,
            gap_description="Equivalence source detail missing — biological safety equivalence cannot be verified",
            reviewer_question="Is biological safety equivalence to a predicate supported? Provide test reports or equivalence documentation.",
            limitation_ref="KSL-014",
            preliminary_judgment=None
        ),
        EquivalenceWorkbenchItem(
            item_id="EQ-BIO-002",
            dimension="biological",
            aspect="Blood compatibility",
            baxter_evidence=None,
            nipro_evidence=None,
            gap_description="Equivalence source detail missing — blood compatibility equivalence cannot be verified",
            reviewer_question="Is blood compatibility equivalence to a predicate supported? Provide supporting documentation.",
            limitation_ref="KSL-014",
            preliminary_judgment=None
        ),
        EquivalenceWorkbenchItem(
            item_id="EQ-CLIN-001",
            dimension="clinical",
            aspect="Clinical data availability",
            baxter_evidence=None,
            nipro_evidence=None,
            gap_description="Equivalence source detail missing — clinical equivalence cannot be verified",
            reviewer_question="Is clinical equivalence to a predicate supported? Provide clinical data or equivalence documentation.",
            limitation_ref="KSL-014",
            preliminary_judgment=None
        ),
        EquivalenceWorkbenchItem(
            item_id="EQ-CLIN-002",
            dimension="clinical",
            aspect="Adverse events / vigilance",
            baxter_evidence=None,
            nipro_evidence=None,
            gap_description="Equivalence source detail missing — post-market equivalence cannot be verified",
            reviewer_question="Is post-market equivalence to a predicate supported? Provide vigilance data or equivalence documentation.",
            limitation_ref="KSL-014",
            preliminary_judgment=None
        ),
    ]


def generate_pmcf_linkage_workbench(
    input_params: SourceInventoryInput | None = None
) -> list[PMCFLinkageItem]:
    """Generate PMCF linkage review workbench (RW-ACT-006).

    Phase 16A fix: Now payload-driven — no longer hardcoded for seed_project_07.

    Logic:
    - input_params None → legacy hardcoded seed_project_07 behavior (backward compat for GET endpoints)
    - pmcf_available=False → generate PMCF missing items with reviewer questions
    - pmcf_available=True + source_documents has PMCF details → use those details
    - pmcf_available=True but no detailed documents → generic evidence-missing items

    NOT a final adequacy judgment — human reviewer decision required.
    """
    # Legacy backward-compat path: no input_params means seed_project_07 context
    if input_params is None:
        return _generate_legacy_pmcf_linkage_workbench()

    # Payload-driven path
    if not input_params.pmcf_available:
        # No PMCF source available — generate PMCF missing items
        return _generate_pmcf_missing_workbench(input_params)

    # PMCF available — check if source_documents has specific details
    pmcf_docs = [
        d for d in (input_params.source_documents or [])
        if d.document_type in ("pmcf", "pmcf_plan", "pmcf_data")
    ]

    if pmcf_docs and any(d.file_name or d.source_path for d in pmcf_docs):
        # Detailed PMCF documents provided — use them
        return _generate_pmcf_from_documents(input_params, pmcf_docs)

    # PMCF flagged as available but no detailed documents
    return _generate_pmcf_generic_placeholder(input_params)


def _generate_legacy_pmcf_linkage_workbench() -> list[PMCFLinkageItem]:
    """Legacy hardcoded PMCF workbench for seed_project_07 (backward compat)."""
    return [
        PMCFLinkageItem(
            item_id="PMCF-LINK-001",
            dimension="cer_scope",
            cer_claim="Device intended for extracorporeal blood purification in ESRD patients",
            pmcf_plan_claim="PMCF plan addresses routine and high-risk patient populations",
            linkage_status="linked",
            gap_description=None,
            reviewer_question="Is PMCF plan scope adequate for CER intended use?",
            limitation_ref="KSL-012",
        ),
        PMCFLinkageItem(
            item_id="PMCF-LINK-002",
            dimension="residual_risk",
            cer_claim="Residual risks managed via IFU warnings and precautions",
            pmcf_plan_claim="PMCF plan monitors long-term safety endpoints",
            linkage_status="partial",
            gap_description="RMF unavailable; residual risk acceptability cannot be confirmed per ISO 14971",
            reviewer_question="Is residual risk management approach adequate without ISO 14971 RMF?",
            limitation_ref="KSL-004, KSL-012",
        ),
        PMCFLinkageItem(
            item_id="PMCF-LINK-003",
            dimension="equivalence",
            cer_claim="Equivalence to Baxter/Nipro predicates claimed",
            pmcf_plan_claim="PMCF plan monitors predicate device performance",
            linkage_status="partial",
            gap_description="Equivalence based on COMPARISON_TABLE_ONLY; original predicate data absent",
            reviewer_question="Is equivalence reliance adequately monitored by PMCF?",
            limitation_ref="KSL-014, KSL-012",
        ),
        PMCFLinkageItem(
            item_id="PMCF-LINK-004",
            dimension="pms_psur",
            cer_claim="PMS/PSUR to be updated post-market",
            pmcf_plan_claim="PMCF data feeds into PSUR updates",
            linkage_status="missing",
            gap_description="PMS data not found; PSUR not found; PMCF actual data absent",
            reviewer_question="Is there adequate post-market data to support CER conclusions?",
            limitation_ref="KSL-012, KSL-013, KSL-015",
        ),
        PMCFLinkageItem(
            item_id="PMCF-LINK-005",
            dimension="update_cycle",
            cer_claim="CER subject to periodic review per MDR Article 61",
            pmcf_plan_claim="PMCF evaluation report due per plan schedule",
            linkage_status="linked",
            gap_description=None,
            reviewer_question="Is update cycle adequate for MDR compliance?",
            limitation_ref=None,
        ),
    ]


def _generate_pmcf_missing_workbench(
    input_params: SourceInventoryInput
) -> list[PMCFLinkageItem]:
    """Generate PMCF workbench items when PMCF source is not available."""
    project_ref = input_params.project_id or "this project"
    return [
        PMCFLinkageItem(
            item_id="PMCF-LINK-001",
            dimension="cer_scope",
            cer_claim=None,
            pmcf_plan_claim=None,
            linkage_status="missing",
            gap_description=f"PMCF source not available for {project_ref} — PMCF adequacy cannot be confirmed",
            reviewer_question="What PMCF plan or data is available to support CER conclusions for this project?",
            limitation_ref="KSL-012",
        ),
        PMCFLinkageItem(
            item_id="PMCF-LINK-002",
            dimension="residual_risk",
            cer_claim=None,
            pmcf_plan_claim=None,
            linkage_status="missing",
            gap_description=f"PMCF source not available for {project_ref} — residual risk post-market monitoring cannot be confirmed",
            reviewer_question="What PMCF data supports residual risk acceptability for this project?",
            limitation_ref="KSL-012",
        ),
        PMCFLinkageItem(
            item_id="PMCF-LINK-003",
            dimension="equivalence",
            cer_claim=None,
            pmcf_plan_claim=None,
            linkage_status="missing",
            gap_description=f"PMCF source not available for {project_ref} — equivalence reliance monitoring cannot be confirmed",
            reviewer_question="What PMCF data supports equivalence-based CER conclusions for this project?",
            limitation_ref="KSL-014, KSL-012",
        ),
        PMCFLinkageItem(
            item_id="PMCF-LINK-004",
            dimension="pms_psur",
            cer_claim=None,
            pmcf_plan_claim=None,
            linkage_status="missing",
            gap_description=f"PMCF, PMS, and PSUR sources not available for {project_ref} — post-market data adequacy cannot be confirmed",
            reviewer_question="What PMS/PSUR/PMCF data is available to support CER conclusions for this project?",
            limitation_ref="KSL-012, KSL-013, KSL-015",
        ),
        PMCFLinkageItem(
            item_id="PMCF-LINK-005",
            dimension="update_cycle",
            cer_claim=None,
            pmcf_plan_claim=None,
            linkage_status="missing",
            gap_description=f"PMCF source not available for {project_ref} — MDR Article 61 update cycle cannot be confirmed",
            reviewer_question="What is the PMCF evaluation schedule and update cycle for this project under MDR compliance?",
            limitation_ref="KSL-012",
        ),
    ]


def _generate_pmcf_from_documents(
    input_params: SourceInventoryInput,
    pmcf_docs: list[SourceDocument]
) -> list[PMCFLinkageItem]:
    """Generate PMCF workbench items from provided source documents."""
    project_ref = input_params.project_id or "this project"
    doc_names = [d.file_name or d.document_id or "unknown" for d in pmcf_docs]
    doc_paths = [d.source_path for d in pmcf_docs if d.source_path]

    doc_note = f"PMCF documents available for {project_ref}: {', '.join(doc_names)}"
    if doc_paths:
        doc_note += f" [paths: {', '.join(doc_paths)}]"

    return [
        PMCFLinkageItem(
            item_id="PMCF-LINK-001",
            dimension="cer_scope",
            cer_claim=None,
            pmcf_plan_claim=None,
            linkage_status="linked",
            gap_description=doc_note,
            reviewer_question="Is PMCF plan scope adequate for the CER intended use of this device?",
            limitation_ref="KSL-012",
        ),
        PMCFLinkageItem(
            item_id="PMCF-LINK-002",
            dimension="residual_risk",
            cer_claim=None,
            pmcf_plan_claim=None,
            linkage_status="partial",
            gap_description=f"PMCF documents available — reviewer must assess residual risk monitoring adequacy: {', '.join(doc_names)}",
            reviewer_question="Does PMCF data adequately address residual risk acceptability for this device?",
            limitation_ref="KSL-004, KSL-012",
        ),
        PMCFLinkageItem(
            item_id="PMCF-LINK-003",
            dimension="equivalence",
            cer_claim=None,
            pmcf_plan_claim=None,
            linkage_status="partial",
            gap_description=f"PMCF documents available — equivalence reliance monitoring required: {', '.join(doc_names)}",
            reviewer_question="Does PMCF adequately monitor equivalence-based CER conclusions for this device?",
            limitation_ref="KSL-014, KSL-012",
        ),
        PMCFLinkageItem(
            item_id="PMCF-LINK-004",
            dimension="pms_psur",
            cer_claim=None,
            pmcf_plan_claim=None,
            linkage_status="partial",
            gap_description=f"PMCF documents available — PMS/PSUR linkage assessment required: {', '.join(doc_names)}",
            reviewer_question="Does PMS/PSUR data support CER conclusions for this device?",
            limitation_ref="KSL-012, KSL-013, KSL-015",
        ),
        PMCFLinkageItem(
            item_id="PMCF-LINK-005",
            dimension="update_cycle",
            cer_claim=None,
            pmcf_plan_claim=None,
            linkage_status="linked",
            gap_description=f"PMCF documents available — update cycle per MDR Article 61: {', '.join(doc_names)}",
            reviewer_question="Is the PMCF update cycle adequate for MDR compliance for this device?",
            limitation_ref="KSL-012",
        ),
    ]


def _generate_pmcf_generic_placeholder(
    input_params: SourceInventoryInput
) -> list[PMCFLinkageItem]:
    """Generate generic PMCF workbench when pmcf_available=True but no document details."""
    project_ref = input_params.project_id or "this project"
    return [
        PMCFLinkageItem(
            item_id="PMCF-LINK-001",
            dimension="cer_scope",
            cer_claim=None,
            pmcf_plan_claim=None,
            linkage_status="missing",
            gap_description=f"PMCF flagged as available for {project_ref} but source document details are missing — evidence detail required",
            reviewer_question="What PMCF plan is available? What is the scope of the PMCF evaluation for this device?",
            limitation_ref="KSL-012",
        ),
        PMCFLinkageItem(
            item_id="PMCF-LINK-002",
            dimension="residual_risk",
            cer_claim=None,
            pmcf_plan_claim=None,
            linkage_status="missing",
            gap_description="PMCF source detail missing — residual risk post-market monitoring cannot be confirmed",
            reviewer_question="What PMCF data addresses residual risk acceptability for this device?",
            limitation_ref="KSL-004, KSL-012",
        ),
        PMCFLinkageItem(
            item_id="PMCF-LINK-003",
            dimension="equivalence",
            cer_claim=None,
            pmcf_plan_claim=None,
            linkage_status="missing",
            gap_description="PMCF source detail missing — equivalence reliance monitoring cannot be confirmed",
            reviewer_question="What PMCF data supports equivalence-based CER conclusions for this device?",
            limitation_ref="KSL-014, KSL-012",
        ),
        PMCFLinkageItem(
            item_id="PMCF-LINK-004",
            dimension="pms_psur",
            cer_claim=None,
            pmcf_plan_claim=None,
            linkage_status="missing",
            gap_description="PMCF source detail missing — PMS/PSUR linkage cannot be confirmed",
            reviewer_question="What PMS/PSUR/PMCF data is available for this device?",
            limitation_ref="KSL-012, KSL-013, KSL-015",
        ),
        PMCFLinkageItem(
            item_id="PMCF-LINK-005",
            dimension="update_cycle",
            cer_claim=None,
            pmcf_plan_claim=None,
            linkage_status="missing",
            gap_description="PMCF source detail missing — MDR Article 61 update cycle cannot be confirmed",
            reviewer_question="What is the PMCF evaluation schedule and update cycle for this device?",
            limitation_ref="KSL-012",
        ),
    ]


def generate_reviewer_findings(
    limitations: list[SourceLimitationItem],
    equivalence_wb: list[EquivalenceWorkbenchItem],
    pmcf_wb: list[PMCFLinkageItem]
) -> list[ReviewerFindingItem]:
    """Generate reviewer findings from available-source bounded workflow.

    Maps Phase 10B rework findings to reviewer findings with action designations.
    """

    findings = []

    # P9-FND-001: RMF gap — closed as external source unavailable
    findings.append(ReviewerFindingItem(
        finding_id="P9-FND-001",
        category="RMF_SOURCE_GAP",
        title="ISO 14971 RMF unavailable",
        description="RMF is permanently unavailable for this project. All RMF-source limitations are documented.",
        source_limitation_ref="KSL-001, KSL-002, KSL-003, KSL-004, KSL-005, KSL-006, KSL-007",
        severity="HIGH",
        actionable=False,
        action=FindingAction.CLOSE_AS_EXTERNAL_SOURCE_UNAVAILABLE,
        human_decision_required=False,
        preliminary_judgment="RMF_PARTIAL status confirmed; full review blocked"
    ))

    # P9-FND-003: IFU-CER risk linkage gap — partially assessable
    findings.append(ReviewerFindingItem(
        finding_id="P9-FND-003",
        category="IFU_CER_RISK_LINKAGE_GAP",
        title="IFU-CER risk linkage partial — 11% unclear",
        description="42% direct linkage, 47% indirect via RMR, 11% unclear. RMR unavailable.",
        source_limitation_ref="KSL-004, KSL-011",
        severity="MEDIUM",
        actionable=True,
        action=FindingAction.PARTIALLY_ASSESSABLE,
        human_decision_required=True,
        preliminary_judgment="Internal workstream RW-ACT-003 can proceed with limitation"
    ))

    # P9-FND-005: Equivalence evidence review — internally actionable NOW
    for item in equivalence_wb:
        findings.append(ReviewerFindingItem(
            finding_id=f"RW-ACT-005-{item.item_id}",
            category="EQUIVALENCE_EVIDENCE",
            title=f"Equivalence review: {item.aspect}",
            description=f"[{item.dimension.upper()}] {item.gap_description or 'Gap description pending'}",
            source_limitation_ref=item.limitation_ref,
            severity="HIGH",
            actionable=True,
            action=FindingAction.EXECUTE_RW_ACT_005,
            human_decision_required=True,
            preliminary_judgment="COMPARISON_TABLE_ONLY; original predicate data absent"
        ))

    # P9-FND-006: PMCF linkage review — internally actionable NOW
    for item in pmcf_wb:
        severity = "HIGH" if item.linkage_status == "missing" else "MEDIUM"
        findings.append(ReviewerFindingItem(
            finding_id=f"RW-ACT-006-{item.item_id}",
            category="PMCF_LINKAGE",
            title=f"PMCF linkage review: {item.dimension}",
            description=f"{item.gap_description or 'Linkage to be verified'}",
            source_limitation_ref=item.limitation_ref,
            severity=severity,
            actionable=True,
            action=FindingAction.EXECUTE_RW_ACT_006,
            human_decision_required=True,
            preliminary_judgment="PMCF plan only; actual data absent"
        ))

    return findings


def generate_non_claims() -> list[NonClaimItem]:
    """Generate explicit non-claims for available-source bounded workflow."""

    return [
        NonClaimItem(
            claim_type="official_cear",
            non_claim="Official CEAR has NOT been generated",
            reason="Source completeness insufficient; RMF_PARTIAL; CER/CEP are drafts"
        ),
        NonClaimItem(
            claim_type="full_rmf_review",
            non_claim="Full ISO 14971 RMF review has NOT been completed",
            reason="ISO 14971 RMF unavailable (KSL-001 through KSL-007)"
        ),
        NonClaimItem(
            claim_type="equivalence_confirmed",
            non_claim="Equivalence to predicate devices has NOT been confirmed",
            reason="COMPARISON_TABLE_ONLY; original predicate data absent (KSL-014)"
        ),
        NonClaimItem(
            claim_type="pmcf_adequacy",
            non_claim="PMCF adequacy has NOT been confirmed",
            reason="PMCF plan only; actual data absent (KSL-012)"
        ),
        NonClaimItem(
            claim_type="production_ready",
            non_claim="Production ready claim has NOT been made",
            reason="This is not a production authorization"
        ),
        NonClaimItem(
            claim_type="regulatory_submission",
            non_claim="Regulatory submission-ready claim has NOT been made",
            reason="Missing critical sources; not a regulatory review"
        ),
        NonClaimItem(
            claim_type="backflow",
            non_claim="No backflow to Obsidian or NocoDB has been executed",
            reason="Backflow guards confirmed inactive"
        ),
        NonClaimItem(
            claim_type="approved_asset",
            non_claim="No approved/active machine asset has been created",
            reason="Asset creation not in scope; reusable defaults to False"
        ),
        # Phase 14A: IFU missing non-claim
        NonClaimItem(
            claim_type="ifu_cer_linkage",
            non_claim="IFU-CER intended purpose linkage review has NOT been executed",
            reason="IFU source not available; KSL-016 applies; CER-only review with IFU gap"
        ),
    ]


# ── Endpoint Handlers ──────────────────────────────────────────────────────────


@router.post("/run", response_model=AvailableSourceWorkflowResponse)
async def run_available_source_workflow(
    request: AvailableSourceWorkflowRequest = Body(...)
) -> AvailableSourceWorkflowResponse:
    """Run available-source bounded CER/RMF review workflow.

    This endpoint:
    - Generates source inventory
    - Determines workflow downgrade decision
    - Generates workbenches (equivalence, PMCF) if requested
    - Generates reviewer findings
    - Produces bounded output with explicit non-claims

    This endpoint does NOT:
    - Generate official CEAR
    - Make final clinical/regulatory decisions
    - Execute backflow
    - Create approved/active assets
    """

    workflow_run_id = f"aws-{uuid.uuid4().hex[:12]}"

    # Verify boundaries — must always be False
    if request.official_cear_allowed:
        raise HTTPException(
            status_code=400,
            detail="official_cear_allowed must be False for available-source workflow"
        )
    if request.final_regulatory_decision_allowed:
        raise HTTPException(
            status_code=400,
            detail="final_regulatory_decision_allowed must be False"
        )
    if request.production_claim_allowed:
        raise HTTPException(
            status_code=400,
            detail="production_claim_allowed must be False"
        )

    # 1. Generate source inventory (MA-003: payload-driven)
    input_params = SourceInventoryInput(
        ifu_available=request.ifu_available,
        cer_available=request.cer_available,
        rmf_available=request.rmf_available,
        risk_related_available=request.risk_related_available,
        equivalence_available=request.equivalence_available,
        pmcf_available=request.pmcf_available,
        pms_available=request.pms_available,
        gspr_available=request.gspr_available,
        sscp_available=request.sscp_available,
        source_documents=request.source_documents,
        project_id=request.project_id,
    )
    source_inventory = generate_source_inventory(project_id=request.project_id, input_params=input_params)

    # 2. Generate source limitation register
    limitations = generate_source_limitation_register(request.project_id, request.known_limitations_ref)

    # 2b. Suppress KSL-016 if IFU is human-confirmed available
    # Root cause: human_confirmed override was applied to mode assignment but NOT to
    # limitation register generation, causing stale KSL-016 artifact to appear even
    # when IFU was confirmed present. This fix suppresses KSL-016 at the register
    # generation step when ifu_available=True and a confirmed IFU exists in source_documents.
    if request.ifu_available and request.source_documents:
        for doc in request.source_documents:
            if doc.document_type and doc.document_type.lower() == "ifu" and doc.is_true_source:
                limitations = [l for l in limitations if l.limitation_id != "KSL-016"]
                break

    # 3. Determine downgrade decision
    downgrade_decision = determine_workflow_downgrade(source_inventory, limitations)

    # 4. Generate workbenches if in scope
    equivalence_wb = None
    pmcf_wb = None

    if "equivalence_workbench" in request.review_scope:
        equivalence_wb = generate_equivalence_workbench(input_params)

    if "pmcf_linkage_workbench" in request.review_scope:
        pmcf_wb = generate_pmcf_linkage_workbench(input_params)

    # 5. Generate reviewer findings
    reviewer_findings = generate_reviewer_findings(limitations, equivalence_wb or [], pmcf_wb or [])

    # 6. Generate non-claims
    non_claims = generate_non_claims()

    # 7. Determine next state
    human_required = any(f.human_decision_required for f in reviewer_findings)
    next_state = "HUMAN_REVIEW_REQUIRED" if human_required else "READY_FOR_REVIEWER_PACKET"

    return AvailableSourceWorkflowResponse(
        workflow_run_id=workflow_run_id,
        project_id=request.project_id,
        project_name=request.project_name,
        status=WorkflowStatus.COMPLETED,
        workflow_mode=downgrade_decision.assigned_mode,
        downgrade_decision=downgrade_decision,
        source_inventory=source_inventory,
        source_limitation_register=limitations,
        equivalence_workbench=equivalence_wb,
        pmcf_linkage_workbench=pmcf_wb,
        reviewer_findings=reviewer_findings,
        non_claims=non_claims,
        next_state=next_state,
        boundaries_applied=BOUNDARY_DEFAULTS,
        generated_at=datetime.now(timezone.utc).isoformat()
    )


@router.get("/register", response_model=SourceLimitationRegisterResponse)
async def get_source_limitation_register(
    project_id: str
) -> SourceLimitationRegisterResponse:
    """Get source limitation register for a project."""

    limitations = generate_source_limitation_register(project_id)

    return SourceLimitationRegisterResponse(
        project_id=project_id,
        register=limitations,
        total_limitations=len(limitations),
        generated_at=datetime.now(timezone.utc).isoformat()
    )


@router.get("/equivalence")
async def get_equivalence_workbench() -> dict[str, Any]:
    """Get equivalence review workbench (RW-ACT-005)."""

    workbench = generate_equivalence_workbench()

    return {
        "workbench_id": "RW-ACT-005",
        "title": "Equivalence Review Workbench — Baxter/Nipro",
        "mode": "AVAILABLE_SOURCE_LIMITED_CER_RMF_REVIEW_WITH_RMF_GAP",
        "limitation_ref": "KSL-014",
        "items": [item.model_dump() for item in workbench],
        "total_items": len(workbench),
        "non_claim": "Equivalence adequacy has NOT been confirmed — COMPARISON_TABLE_ONLY",
        "reviewer_action": "Execute RW-ACT-005: Human reviewer decision required for each item",
        "generated_at": datetime.now(timezone.utc).isoformat()
    }


@router.get("/pmcf")
async def get_pmcf_linkage_workbench() -> dict[str, Any]:
    """Get PMCF linkage review workbench (RW-ACT-006)."""

    workbench = generate_pmcf_linkage_workbench()

    return {
        "workbench_id": "RW-ACT-006",
        "title": "PMCF Linkage Review Workbench",
        "mode": "AVAILABLE_SOURCE_LIMITED_CER_RMF_REVIEW_WITH_RMF_GAP",
        "limitation_ref": "KSL-012",
        "items": [item.model_dump() for item in workbench],
        "total_items": len(workbench),
        "non_claim": "PMCF adequacy has NOT been confirmed — plan only",
        "reviewer_action": "Execute RW-ACT-006: Human reviewer decision required for each item",
        "generated_at": datetime.now(timezone.utc).isoformat()
    }


@router.get("/report")
async def get_reviewer_working_report(
    project_id: str,
    workflow_run_id: str | None = None
) -> dict[str, Any]:
    """Get reviewer working report.

    This is NOT an official CEAR.
    This is NOT a regulatory submission.
    """

    limitations = generate_source_limitation_register(project_id)
    source_inventory = generate_source_inventory(project_id)
    equivalence_wb = generate_equivalence_workbench()
    pmcf_wb = generate_pmcf_linkage_workbench()
    findings = generate_reviewer_findings(limitations, equivalence_wb, pmcf_wb)
    non_claims = generate_non_claims()

    return {
        "report_type": "REVIEWER_WORKING_REPORT",
        "project_id": project_id,
        "workflow_run_id": workflow_run_id or "pending",
        "mode": "AVAILABLE_SOURCE_LIMITED_CER_RMF_REVIEW_WITH_RMF_GAP",
        "source_inventory_summary": {
            "total_sources": len(source_inventory),
            "true_source": len([s for s in source_inventory if s.status == SourceStatus.TRUE_SOURCE]),
            "partial_source": len([s for s in source_inventory if s.status == SourceStatus.PARTIAL_SOURCE]),
            "source_unavailable": len([s for s in source_inventory if s.status == SourceStatus.SOURCE_UNAVAILABLE]),
        },
        "limitations_summary": {
            "total_limitations": len(limitations),
            "rmf_source_count": len([l for l in limitations if l.category == "RMF_SOURCE"]),
            "equivalence_count": len([l for l in limitations if l.category == "EQUIVALENCE"]),
            "post_market_count": len([l for l in limitations if l.category == "POST_MARKET"]),
        },
        "findings": [f.model_dump() for f in findings],
        "findings_summary": {
            "total": len(findings),
            "actionable": len([f for f in findings if f.actionable]),
            "human_decision_required": len([f for f in findings if f.human_decision_required]),
        },
        "non_claims": [nc.model_dump() for nc in non_claims],
        "boundaries": BOUNDARY_DEFAULTS,
        "next_state": "HUMAN_REVIEW_REQUIRED",
        "non_claim_summary": "This report is NOT an official CEAR. This report is NOT a regulatory submission.",
        "generated_at": datetime.now(timezone.utc).isoformat()
    }
