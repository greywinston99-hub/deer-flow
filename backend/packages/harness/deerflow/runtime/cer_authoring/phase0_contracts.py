"""Phase 0 calibration contracts for CER authoring.

These contracts are intentionally descriptive carrier artifacts.  They do not
change authoring decisions, SOTA logic, evidence appraisal, writer wording, or
gate pass/fail behavior.  Their job is to make future calibration runs
auditable and comparable under a frozen authoring baseline.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any


PHASE0_SCHEMA_VERSION = "cer-authoring-phase0-contract-v1"
DEFAULT_AUTHORING_BASELINE_VERSION = "V2.6_PHASE6_EVIDENCE_WRITERS_FIX"
_UNKNOWN_GENERATED_AT = "not_recorded"


def build_phase0_contracts(state: dict[str, Any]) -> dict[str, Any]:
    """Return Phase 0 carrier artifacts, preserving provided values."""

    contracts = {
        "authoring_baseline_version": authoring_baseline_version(state),
        "calibration_case_schema": state.get("calibration_case_schema") or calibration_case_schema(state),
        "artifact_consumption_contract": state.get("artifact_consumption_contract") or artifact_consumption_contract(),
        "failure_taxonomy_cer_authoring": state.get("failure_taxonomy_cer_authoring") or failure_taxonomy_cer_authoring(),
        "cer_section_trace_map_schema": state.get("cer_section_trace_map_schema") or cer_section_trace_map_schema(),
        "gate_to_upstream_repair_map": state.get("gate_to_upstream_repair_map") or gate_to_upstream_repair_map(),
        "authoring_baseline_freeze_manifest": state.get("authoring_baseline_freeze_manifest") or authoring_baseline_freeze_manifest(state),
        "calibration_event_log": state.get("calibration_event_log") or [],
    }
    return contracts


def authoring_baseline_version(state: dict[str, Any] | None = None) -> str:
    state = state or {}
    return str(
        state.get("authoring_baseline_version")
        or os.getenv("CER_AUTHORING_BASELINE_VERSION")
        or DEFAULT_AUTHORING_BASELINE_VERSION
    )


def _manifest_generated_at(state: dict[str, Any]) -> str:
    """Return a stable timestamp when the run already provides one."""

    for key in ("generated_at", "created_at", "started_at", "run_started_at"):
        if state.get(key):
            return str(state[key])
    run_metadata = state.get("run_metadata")
    if isinstance(run_metadata, dict):
        for key in ("generated_at", "created_at", "started_at", "run_started_at"):
            if run_metadata.get(key):
                return str(run_metadata[key])
    if os.getenv("CER_AUTHORING_BASELINE_GENERATED_AT"):
        return str(os.getenv("CER_AUTHORING_BASELINE_GENERATED_AT"))
    return datetime.now(UTC).isoformat()


def calibration_case_schema(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_name": "calibration_case_schema",
        "schema_version": PHASE0_SCHEMA_VERSION,
        "purpose": "Define how a real CER project enters calibration without leaking human accepted CER or NB comments into writer stages.",
        "authoring_baseline_version": authoring_baseline_version(state),
        "project_metadata_required": [
            "project_id",
            "device_name",
            "device_class",
            "device_domain",
            "calibration_role",
            "source_data_lock_date",
            "authoring_baseline_version",
        ],
        "input_groups": [
            {
                "group_id": "CAL-IN-001",
                "name": "Allowed authoring source pack",
                "allowed_for_writer": True,
                "examples": "IFU, CEP, GSPR, RMF/RMR/FMEA, PMS/PMCF, pre-clinical, manufacturer source files, permitted full-text PDFs.",
            },
            {
                "group_id": "CAL-IN-002",
                "name": "Human accepted CER",
                "allowed_for_writer": False,
                "allowed_for_delta_analyzer": True,
                "control": "May only be loaded after AI baseline artifacts are frozen.",
            },
            {
                "group_id": "CAL-IN-003",
                "name": "NB comments and response letters",
                "allowed_for_writer": False,
                "allowed_for_delta_analyzer": True,
                "control": "Used only for CEAR deficiency pattern and root-cause analysis.",
            },
        ],
        "required_delta_tables": [
            "CLAIM_DELTA_TABLE",
            "SOTA_BENCHMARK_DELTA_TABLE",
            "EVIDENCE_SELECTION_DELTA_TABLE",
            "EVIDENCE_APPRAISAL_DELTA_TABLE",
            "CLAIM_EVIDENCE_DELTA_MATRIX",
            "PMCF_BOUNDARY_DELTA_TABLE",
            "ALIGNMENT_DELTA_TABLE",
            "CEAR_DEFICIENCY_PATTERN_TABLE",
        ],
        "dry_run_allowed_changes": [
            "schema/protocol bug fix",
            "artifact/export/readback fix",
            "data leakage control fix",
            "blocker recording",
        ],
        "formal_calibration_forbidden_changes": [
            "SOTA Agent logic",
            "Evidence Appraisal logic",
            "Writer Contract",
            "Benefit-Risk Rule",
            "PMCF Boundary Rule",
            "Alignment Rule",
            "Gate Logic",
        ],
    }


def artifact_consumption_contract() -> list[dict[str, Any]]:
    rows = [
        ("ACC-001", "source_inventory", "prepare_source_inventory", "input_gate, build_device_profile", "required", "state_used_and_exported", "Primary source-role control and input completeness."),
        ("ACC-002", "device_profile", "build_device_profile", "build_claims, build_pico_matrix, write_cer_chapters, gates", "required", "state_used_and_exported", "Single device identity and intended-purpose source."),
        ("ACC-003", "claim_ledger", "build_claims", "build_pico_matrix, write_cer_chapters, gates", "required", "state_used_and_exported", "Claim registry; every claim must enter downstream PICO/evidence logic."),
        ("ACC-004", "cep_pico_matrix", "build_pico_matrix", "run_sota_search, write_cer_chapters, gates, repair pico-loop", "required", "state_used_and_exported", "Clinical question and search-planning spine."),
        ("ACC-005", "search_run_registry", "run_sota_search, screen_literature", "screen_literature, appraise_evidence, gates, writer", "required", "state_used_and_exported", "Reproducible LSP/search execution record."),
        ("ACC-006", "sota_benchmark_matrix", "run_sota_search", "extract_endpoints, write_cer_chapters, gates", "required", "state_used_and_exported", "SOTA benchmark input to section 4.7."),
        ("ACC-007", "evidence_registry", "appraise_evidence", "extract_endpoints, write_cer_chapters, gates", "required", "state_used_and_exported", "Evidence weighting and traceability spine."),
        ("ACC-008", "endpoint_extraction", "extract_endpoints", "write_cer_chapters, gates, repair fulltext enhancement", "required", "state_used_and_exported", "Endpoint data source for numeric conclusions."),
        ("ACC-017", "endpoint_registry", "extract_endpoints", "sota_endpoint_derivation_table, writer, CCD validation", "required", "state_used_and_exported", "Unified END-numbered endpoint registry for SOTA benchmark derivation."),
        ("ACC-018", "sota_endpoint_derivation_table", "extract_endpoints", "G30, writer, CCD validation", "required", "state_used_and_exported", "G30-controlled derivation table linking PICO/search/evidence/endpoint/benchmark."),
        ("ACC-019", "sota_quantitative_benchmark_table", "extract_endpoints", "writer, SOTA-to-4.7 usage, CCD validation", "required", "state_used_and_exported", "Benchmark value/source/population/sample-size/CI-or-range table."),
        ("ACC-020", "sota_claim_reverse_correction_table", "extract_endpoints", "claim_ledger, writer contract, CCD validation", "required", "state_used_and_exported", "SOTA-to-claim reverse correction constraints for claim wording strength."),
        ("ACC-021", "claim_evidence_matrix", "write_cer_chapters", "benefit_risk_ledger, writer, G38/CCD validation", "required", "state_used_and_exported", "Claim-to-evidence support and conclusion-strength matrix."),
        ("ACC-022", "benefit_risk_ledger", "write_cer_chapters", "writer 4.7/5, G12/G38/CCD validation", "required", "state_used_and_exported", "Quantitative/semi-quantitative benefit-risk ledger derived from claims, evidence, SOTA, risks, alignment and gaps."),
        ("ACC-023", "writer_conclusion_strength_guard", "write_cer_chapters", "sota_conclusion_strength_guard, writer, G38", "required", "state_used_and_exported", "Writer-stage conclusion-strength guard enforcing allowed wording before CER prose."),
        ("ACC-024", "cer_section_trace_map", "write_cer_chapters", "writer, export, CCD validation", "required", "state_used_and_exported", "CER paragraph trace map linking claims, evidence, SOTA, risks, PMCF and benefit-risk rows."),
        ("ACC-024A", "alignment_matrix", "write_cer_chapters", "claim_evidence_matrix, benefit_risk_ledger, writer 4.7/5, G33 post-writing verification", "required", "state_used_and_exported", "CER-to-IFU/RMF/GSPR/PMCF alignment matrix used before writer prose and rechecked after writing."),
        ("ACC-009", "equivalence_matrix", "run_device_equivalence_search", "map_risks_and_gspr, write_cer_chapters, gates", "required_when_equivalence_or_similar_used", "state_used_and_exported", "Equivalence/similar-device boundary."),
        ("ACC-025", "similar_device_four_step_confirmation", "run_device_equivalence_search", "G33, writer Annex Q, CCD validation", "required", "state_used_and_exported", "Four-step similar-device eligibility and use-boundary table."),
        ("ACC-026", "similar_device_attachment_index", "run_device_equivalence_search", "G33, writer Annex Q, CCD validation", "required", "state_used_and_exported", "10 baseline similar-device attachment requests with source/use/missing-data controls."),
        ("ACC-010", "vigilance_recall_registry", "run_vigilance_search", "map_risks_and_gspr, write_cer_chapters, gates", "required", "state_used_and_exported", "Vigilance and recall evidence input."),
        ("ACC-011", "risk_trace_matrix", "map_risks_and_gspr", "write_cer_chapters, gates, repair rmf-pmcf-closure", "required", "state_used_and_exported", "Risk/RMF/IFU/PMS closure input."),
        ("ACC-012", "gspr_coverage", "map_risks_and_gspr", "write_cer_chapters, gates", "required", "state_used_and_exported", "GSPR traceability input."),
        ("ACC-013", "cer_chapter_drafts", "write_cer_chapters", "human_style_review, nb_precheck, export", "required", "state_used_and_exported", "Baseline CER body."),
        ("ACC-014", "qa_gate_report", "run_authoring_gates", "supervisor postflight, repair classification, final package", "required", "exported_and_read_by_supervisor", "Baseline quality decision."),
        ("ACC-015", "claude_repair/enhanced_authoring_workbook", "Claude repair layer", "finalize-package, publish-final-package", "optional_repair", "external_to_graph", "Repair output must not be confused with baseline."),
        ("ACC-016", "deerflow_authoring/final", "publish-final-package", "human reviewer / NB pre-review package", "optional_final", "external_delivery", "Final package lineage must cite baseline and repair sources."),
    ]
    return [
        {
            "contract_id": contract_id,
            "artifact_name": artifact_name,
            "producer": producer,
            "consumer": consumer,
            "required_or_optional": required,
            "consumption_status": status,
            "calibration_use": use,
        }
        for contract_id, artifact_name, producer, consumer, required, status, use in rows
    ]


def failure_taxonomy_cer_authoring() -> list[dict[str, Any]]:
    categories = [
        ("FTC-001", "source", "Wrong, missing or contaminated input source; IFU/domain identity not locked.", "Usually requires source-role fix or full rerun.", "high"),
        ("FTC-002", "claim", "IFU/intended-purpose/clinical-benefit claims missing, overbroad or unsupported.", "Requires claim registry correction before writer.", "high"),
        ("FTC-003", "sota", "SOTA endpoint/benchmark/pathway/acceptance criterion missing or not used in 4.7.", "Repair SOTA benchmark artifacts before evidence conclusion.", "critical"),
        ("FTC-004", "evidence", "Evidence harvesting, citation verification, full-text extraction or endpoint extraction insufficient.", "Repair evidence registry and endpoint extraction.", "critical"),
        ("FTC-005", "appraisal", "Evidence level, applicability, contribution or pivotal/supportive weight wrong.", "Repair evidence appraisal before conclusion strength.", "high"),
        ("FTC-006", "pmcf", "PMCF used as evidence-gap dumping ground or lacks boundary/timetable.", "Repair gap/PMCF decision log and benefit-risk conditions.", "high"),
        ("FTC-007", "alignment", "CER conflicts with RMF/IFU/PMCF/CEP/SSCP or missing cross-document closure.", "Repair alignment matrix or human hold.", "high"),
        ("FTC-008", "writer", "CER paragraph wording is unsupported, too strong, template-like, or not traceable.", "Repair section trace map and writer output.", "medium"),
        ("FTC-009", "gate", "Gate detects failure but lacks upstream route or recheck discipline.", "Repair gate-to-upstream map, not core gate logic during calibration.", "medium"),
        ("FTC-010", "lineage", "Baseline/repair/final/calibration artifacts are mixed or unversioned.", "Repair baseline freeze manifest and final manifest.", "high"),
        ("FTC-011", "leakage", "Human CER/NB comments leak into authoring writer stage.", "Stop calibration; repair data partition controls.", "critical"),
    ]
    return [
        {
            "failure_type_id": failure_type_id,
            "root_cause_category": category,
            "definition": definition,
            "default_handling": handling,
            "default_severity": severity,
        }
        for failure_type_id, category, definition, handling, severity in categories
    ]


def cer_section_trace_map_schema() -> list[dict[str, Any]]:
    fields = [
        ("section_id", "CER section identifier, e.g. CER-4.7.2", "required"),
        ("paragraph_id", "Stable paragraph identifier, e.g. CER-4.7.2-P03", "required"),
        ("claim_ids", "Claim IDs supporting the paragraph", "required_for_core_conclusions"),
        ("endpoint_ids", "Endpoint IDs supporting numeric/performance/safety statements", "required_for_core_conclusions"),
        ("sota_ids", "SOTA benchmark IDs used by the paragraph", "required_for_sota_or_4_7"),
        ("evidence_ids", "Evidence IDs used by the paragraph", "required_for_evidence_claims"),
        ("gap_ids", "Evidence gap IDs disclosed or controlled by the paragraph", "required_when_gap_present"),
        ("pmcf_ids", "PMCF activity IDs linked to residual questions", "required_when_pmcf_used"),
        ("risk_ids", "Risk/RMF/IFU-linked IDs", "required_for_safety_or_benefit_risk"),
        ("alignment_ids", "Alignment rows for CER/RMF/IFU/SSCP/PMCF consistency", "required_when_alignment_checked"),
        ("benefit_risk_ids", "Benefit-risk ledger IDs", "required_for_benefit_risk_conclusions"),
        ("allowed_wording_strength", "strong/cautious/descriptive/not_allowed", "required"),
        ("source_artifact_hashes", "Hashes or lineage pointers for upstream artifacts", "required_for_calibration"),
        ("qa_status", "pass/flag/human_hold", "required"),
        ("human_review_required", "yes/no", "required"),
    ]
    return [
        {
            "field_name": field,
            "field_definition": definition,
            "requirement_level": requirement,
            "schema_use": "CER Section Trace Map",
        }
        for field, definition, requirement in fields
    ]


def gate_to_upstream_repair_map() -> list[dict[str, Any]]:
    rows = [
        ("G30", "SOTA endpoint derivation", "SOTA endpoint derivation table missing or lacks trace fields", "sota", "endpoint_extraction / sota_search", "sota_endpoint_derivation_table", "repair_sota_endpoint_derivation", "yes", "G30,G31,G37,G38", "no", "2 attempts then HUMAN_HOLD"),
        ("G33", "Similar-device four-step confirmation", "Similar-device attachment rows lack source/use/missing-data handling", "equivalence", "device_equivalence_search", "similar_device_attachment_index", "repair_similar_device_attachment_index", "yes", "G11,G33", "yes_if_attachment_evidence_missing", "1 attempt then HUMAN_HOLD"),
        ("G38", "SOTA conclusion strength guard", "CER uses superiority/absolute wording not allowed by evidence-level guard", "wording/evidence", "cer_writing / benefit_risk_ledger", "sota_conclusion_strength_guard", "repair_conclusion_strength_and_writer_wording", "yes", "G12,G38", "no", "2 attempts then reviewer hold"),
        ("G6", "Numeric traceability", "Numeric data lack source/sample/timepoint/endpoint/result fields", "evidence", "endpoint_extraction / evidence_appraisal", "endpoint_extraction", "repair_numeric_traceability", "yes", "G6,G25,G30", "no", "2 attempts then full-text request"),
        ("G12", "Conclusion strength", "Final conclusion strength exceeds evidence/gap status", "benefit-risk/writer", "benefit_risk_ledger / cer_writing", "benefit_risk_ledger", "repair_benefit_risk_conclusion_strength", "yes", "G12,G38", "no", "2 attempts then human review"),
        ("G17", "MCP execution completeness", "Required MCP server/tool missing or failed", "execution", "same_stage_retry_or_source_limitation", "mcp_call_log", "repair_mcp_execution_or_record_limitation", "conditional", "G17", "yes_if_tool_required_for_claim", "retry once then source limitation or HUMAN_HOLD"),
    ]
    return [
        {
            "gate_id": gate_id,
            "gate_name": gate_name,
            "failure_pattern": pattern,
            "failure_category": category,
            "upstream_stage": upstream_stage,
            "required_artifact_to_fix": artifact,
            "repair_node": repair_node,
            "partial_rerun_allowed": partial,
            "recheck_gates": recheck,
            "human_gate_required": human,
            "stop_condition": stop,
        }
        for gate_id, gate_name, pattern, category, upstream_stage, artifact, repair_node, partial, recheck, human, stop in rows
    ]


def authoring_baseline_freeze_manifest(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_name": "authoring_baseline_freeze_manifest",
        "schema_version": PHASE0_SCHEMA_VERSION,
        "generated_at": _manifest_generated_at(state) or _UNKNOWN_GENERATED_AT,
        "authoring_baseline_version": authoring_baseline_version(state),
        "phase": "Phase 0 carrier layer",
        "core_authoring_workflow_frozen_during_formal_calibration": True,
        "formal_calibration_entry_rule": "Run one dry-run first; freeze baseline before the three formal calibration projects.",
        "allowed_between_formal_projects": [
            "delta analysis",
            "root-cause classification",
            "schema/protocol bug fix",
            "artifact/export/readback fix",
            "data leakage fix",
            "blocker recording",
        ],
        "forbidden_between_formal_projects": [
            "SOTA Agent logic change",
            "Evidence Appraisal logic change",
            "Writer Contract change",
            "Benefit-Risk Rule change",
            "PMCF Boundary Rule change",
            "Alignment Rule change",
            "Gate Logic change",
        ],
        "fatal_blocker_protocol": [
            "bump authoring_baseline_version",
            "record blocker and repair reason",
            "rerun affected calibration project",
            "aggregate only same-baseline projects, or stratify by baseline version",
        ],
    }
