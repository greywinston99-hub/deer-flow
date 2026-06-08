"""Shared state for the isolated CER authoring workflow."""

from __future__ import annotations

import operator
from typing import Annotated, Any, NotRequired

from deerflow.agents.thread_state import ThreadState


def merge_dict(existing: dict | None, new: dict | None) -> dict:
    if existing is None:
        return new or {}
    if new is None:
        return existing
    return {**existing, **new}


def append_list(existing: list | None, new: list | None) -> list:
    if existing is None:
        return new or []
    if new is None:
        return existing
    return existing + new


def _keep_first(existing: Any, new: Any) -> Any:
    """Reducer for fields that should not be overwritten once set (e.g. freeze markers)."""
    return existing if existing is not None else new


_ID_FIELDS = (
    "contract_id",
    "failure_type_id",
    "claim_id",
    "pico_id",
    "article_id",
    "screen_id",
    "evidence_id",
    "endpoint_id",
    "benchmark_id",
    "comparison_id",
    "vigilance_id",
    "risk_id",
    "gspr_id",
    "gap_id",
    "search_id",
    "source_id",
    "row_id",
    "field_name",
    "gate_id",
    "spiral_round_id",
    "event_id",
    "correction_id",
    "matrix_id",
    "br_id",
    "trace_id",
    "document_id",
    "lineage_id",
    "fact_id",
    "review_id",
    "mapping_id",
    "link_id",
    "conflict_id",
)


def merge_records(existing: list | None, new: list | None) -> list:
    if existing is None:
        existing = []
    if new is None:
        return existing
    output = list(existing)
    index: dict[tuple[str, str], int] = {}
    for idx, item in enumerate(output):
        key = _record_key(item)
        if key:
            index[key] = idx
    for item in new:
        key = _record_key(item)
        if key and key in index and isinstance(output[index[key]], dict) and isinstance(item, dict):
            output[index[key]] = {**output[index[key]], **item}
        else:
            if key:
                index[key] = len(output)
            output.append(item)
    return output


def _record_key(item: Any) -> tuple[str, str] | None:
    if not isinstance(item, dict):
        return None
    for field in _ID_FIELDS:
        if item.get(field):
            return field, str(item[field])
    return None


class SharedAuthoringState(ThreadState):
    """Single source of truth for CER authoring.

    IDs are expected to chain as:
    source_id -> claim_id -> pico_id -> search_id -> article_id -> evidence_id
    -> endpoint_id -> benchmark_id -> risk_id -> gspr_id -> section_id.
    """

    project_id: NotRequired[str | None]
    input_root: NotRequired[str | None]
    supplement_roots: NotRequired[list[str]]
    uploaded_files: NotRequired[list[dict[str, Any]]]
    target_keywords: NotRequired[list[str]]
    artifact_root: NotRequired[str | None]
    status: NotRequired[Annotated[str | None, lambda e, n: n if n else e]]
    export_completed: NotRequired[bool]
    final_gate_decision: NotRequired[str | None]
    agent_team_mode: NotRequired[str | None]

    # ── Claude Code CER Authoring Engine integration ──
    locked_endpoint_framework: Annotated[dict[str, Any], merge_dict]
    consolidated_clinical_data_table: Annotated[dict[str, Any], merge_dict]
    eu_market_status: NotRequired[str | None]
    cer_input_package_exported: NotRequired[bool]

    source_inventory: Annotated[list[dict[str, Any]], merge_records]
    manufacturer_intake_report: Annotated[dict[str, Any], merge_dict]
    source_lock_report: Annotated[dict[str, Any], merge_dict]
    ifu_fact_table: Annotated[dict[str, Any], merge_dict]
    source_preflight_gate_report: Annotated[dict[str, Any], merge_dict]
    classification_consistency_report: Annotated[dict[str, Any], merge_dict]
    document_structured_content: Annotated[list[dict[str, Any]], merge_records]
    document_parsing_lineage: Annotated[list[dict[str, Any]], merge_records]
    deep_reparse_requests: Annotated[list[dict[str, Any]], merge_records]
    extraction_gaps: Annotated[list[dict[str, Any]], merge_records]
    clinical_evidence_fact_table: Annotated[list[dict[str, Any]], merge_records]
    semantic_endpoint_mapping_table: Annotated[list[dict[str, Any]], merge_records]
    endpoint_match_trace: Annotated[dict[str, Any], merge_dict]
    fact_to_claim_link_matrix: Annotated[list[dict[str, Any]], merge_records]
    evidence_conflict_report: Annotated[dict[str, Any], merge_dict]
    human_review_queue: Annotated[list[dict[str, Any]], merge_records]
    fact_anchored_claims: Annotated[list[dict[str, Any]], merge_records]
    claim_support_matrix: Annotated[dict[str, Any], merge_dict]
    writer_conclusion_constraints: Annotated[dict[str, Any], merge_dict]
    synthesis_method_selections: Annotated[list[dict[str, Any]], merge_records]
    sota_benchmark_table: Annotated[list[dict[str, Any]], merge_records]
    benefit_risk_conclusion: Annotated[dict[str, Any], merge_dict]
    pmcf_gap_register: Annotated[list[dict[str, Any]], merge_records]
    cer_rmf_crosswalk_table: Annotated[list[dict[str, Any]], merge_records]
    reasoning_audit_ledger: Annotated[list[dict[str, Any]], merge_records]
    human_review_packet: Annotated[list[dict[str, Any]], merge_records]
    ei_gate_signals: Annotated[dict[str, Any], merge_dict]
    ei_validation_harness_results: Annotated[list[dict[str, Any]], merge_records]
    retrieval_completeness: Annotated[dict[str, Any], merge_dict]
    provisional_ei_reasoning_report: NotRequired[str | None]
    source_role_report: Annotated[dict[str, Any], merge_dict]
    input_gap_list: Annotated[list[dict[str, Any]], merge_records]
    device_profile: Annotated[dict[str, Any], merge_dict]
    device_classification_lock: Annotated[dict[str, Any], merge_dict]
    device_identity_lock: Annotated[dict[str, Any], merge_dict]
    device_identity_arbitration: Annotated[dict[str, Any], merge_dict]
    device_identity_arbitration_table: Annotated[list[dict[str, Any]], merge_records]
    domain_contamination_report: Annotated[dict[str, Any], merge_dict]
    claim_ledger: Annotated[list[dict[str, Any]], merge_records]
    intended_purpose_claim_table: Annotated[list[dict[str, Any]], merge_records]
    clinical_evaluation_plan: Annotated[dict[str, Any], merge_dict]
    cep_pico_matrix: Annotated[list[dict[str, Any]], merge_records]
    search_run_registry: Annotated[list[dict[str, Any]], merge_records]
    literature_search_protocol_profile: Annotated[dict[str, Any], merge_dict]
    sota_pico_strategy: Annotated[list[dict[str, Any]], merge_records]
    due_pico_strategy: Annotated[list[dict[str, Any]], merge_records]
    database_search_source_table: Annotated[list[dict[str, Any]], merge_records]
    literature_defined_limits: Annotated[list[dict[str, Any]], merge_records]
    literature_flow_registry: Annotated[list[dict[str, Any]], merge_records]
    protocol_deviation_log: Annotated[list[dict[str, Any]], merge_records]
    prisma_flow_data: Annotated[dict[str, Any], merge_dict]
    prisma_flow_diagram: Annotated[dict[str, Any], merge_dict]
    sota_search_strategy_table: Annotated[list[dict[str, Any]], merge_records]
    sota_screening_disposition_table: Annotated[list[dict[str, Any]], merge_records]
    sota_ck_appraisal_table: Annotated[list[dict[str, Any]], merge_records]
    due_suitability_contribution_table: Annotated[list[dict[str, Any]], merge_records]
    alternative_treatment_benchmark_table: Annotated[list[dict[str, Any]], merge_records]
    guideline_pathway_table: Annotated[list[dict[str, Any]], merge_records]
    similar_benchmark_device_table: Annotated[list[dict[str, Any]], merge_records]
    hazard_source_table: Annotated[list[dict[str, Any]], merge_records]
    sota_to_47_usage_matrix: Annotated[list[dict[str, Any]], merge_records]
    full_text_request_list: Annotated[list[dict[str, Any]], merge_records]
    sota_literature_quantity_justification: Annotated[dict[str, Any], merge_dict]
    endpoint_registry: Annotated[list[dict[str, Any]], merge_records]
    sota_endpoint_derivation_table: Annotated[list[dict[str, Any]], merge_records]
    sota_quantitative_benchmark_table: Annotated[list[dict[str, Any]], merge_records]
    sota_evidence_synthesis_matrix: Annotated[list[dict[str, Any]], merge_records]
    sota_claim_reverse_correction_table: Annotated[list[dict[str, Any]], merge_records]
    sota_medical_field_boundary: Annotated[list[dict[str, Any]], merge_records]
    sota_pico_v2_strategy: Annotated[list[dict[str, Any]], merge_records]
    sota_search_strategy_separated: Annotated[list[dict[str, Any]], merge_records]
    sota_screening_prisma: Annotated[list[dict[str, Any]], merge_records]
    sota_evidence_hierarchy: Annotated[list[dict[str, Any]], merge_records]
    sota_endpoint_extraction_fulltext: Annotated[list[dict[str, Any]], merge_records]
    sota_benchmark_derivation_table: Annotated[list[dict[str, Any]], merge_records]
    sota_section_conclusion_matrix: Annotated[list[dict[str, Any]], merge_records]
    sota_deduction_chain: Annotated[list[dict[str, Any]], merge_records]
    sota_endpoint_source_classification: Annotated[list[dict[str, Any]], merge_records]
    sota_aggregate_benchmark_rationale: Annotated[list[dict[str, Any]], merge_records]
    sota_conclusion_strength_guard: Annotated[list[dict[str, Any]], merge_records]
    sota_clinical_context_table: Annotated[list[dict[str, Any]], merge_records]
    sota_benchmark_contextual_rationale: Annotated[list[dict[str, Any]], merge_records]
    sota_context_injection_trace: Annotated[list[dict[str, Any]], merge_records]
    claim_evidence_matrix: Annotated[list[dict[str, Any]], merge_records]
    benefit_risk_ledger: Annotated[list[dict[str, Any]], merge_records]
    writer_conclusion_strength_guard: Annotated[list[dict[str, Any]], merge_records]
    cer_section_trace_map: Annotated[list[dict[str, Any]], merge_records]
    alignment_matrix: Annotated[list[dict[str, Any]], merge_records]
    cross_evidence_synthesis_table: Annotated[list[dict[str, Any]], merge_records]
    cross_evidence_synthesis_narratives: Annotated[list[dict[str, Any]], merge_records]
    writer_synthesis_trace: Annotated[list[dict[str, Any]], merge_records]
    writer_device_template_profile: Annotated[dict[str, Any], merge_dict]
    writer_device_conditional_sections: Annotated[list[dict[str, Any]], merge_records]
    raw_literature_records: Annotated[list[dict[str, Any]], merge_records]
    clinical_source_adapter_records: Annotated[list[dict[str, Any]], merge_records]
    clinical_source_adapter_lineage: Annotated[list[dict[str, Any]], merge_records]
    database_hit_count: Annotated[list[dict[str, Any]], merge_records]
    retrieved_record_pool: Annotated[list[dict[str, Any]], merge_records]
    screened_candidate_pool: Annotated[list[dict[str, Any]], merge_records]
    fulltext_assessed_pool: Annotated[list[dict[str, Any]], merge_records]
    final_cer_included_set: Annotated[list[dict[str, Any]], merge_records]
    query_construction_trace: Annotated[list[dict[str, Any]], merge_records]
    pubmed_mcp_retrieval_ledger: Annotated[list[dict[str, Any]], merge_records]
    pmid_screening_and_exclusion_table: Annotated[list[dict[str, Any]], merge_records]
    fulltext_acquisition_status_table: Annotated[list[dict[str, Any]], merge_records]
    evidence_source_trace_matrix: Annotated[list[dict[str, Any]], merge_records]
    evidence_source_inventory: Annotated[list[dict[str, Any]], merge_records]
    allowed_use_matrix: Annotated[list[dict[str, Any]], merge_records]
    writer_evidence_consumption_trace: Annotated[list[dict[str, Any]], merge_records]
    pubmed_fetch_batch_lineage: Annotated[list[dict[str, Any]], merge_records]
    evidence_funnel_counts: Annotated[dict[str, Any], merge_dict]
    writer_input_packet: Annotated[dict[str, Any], merge_dict]
    evidence_spiral_lineage: Annotated[list[dict[str, Any]], merge_records]
    gate_routing_trace: Annotated[list[dict[str, Any]], append_list]
    spiral_query_expansion_request: Annotated[dict[str, Any], merge_dict]
    evidence_sufficiency_gate_report: Annotated[dict[str, Any], merge_dict]
    pre_g42_claim_evidence_candidate_matrix: Annotated[list[dict[str, Any]], merge_records]
    required_source_profile_matrix: Annotated[list[dict[str, Any]], merge_records]
    claim_support_type_classifier: Annotated[list[dict[str, Any]], merge_records]
    semantic_claim_evidence_candidate_matrix: Annotated[list[dict[str, Any]], merge_records]
    g42_failure_pattern_report: Annotated[list[dict[str, Any]], merge_records]
    g42_repair_routing_trace: Annotated[list[dict[str, Any]], merge_records]
    pre_writer_readiness_report: Annotated[dict[str, Any], merge_dict]
    compromise_manifest: Annotated[dict[str, Any], merge_dict]
    controlled_compromise_manifest: Annotated[dict[str, Any], merge_dict]
    screening_disposition: Annotated[list[dict[str, Any]], merge_records]
    article_appraisal: Annotated[list[dict[str, Any]], merge_records]
    evidence_registry: Annotated[list[dict[str, Any]], merge_records]
    evidence_depth_taxonomy: Annotated[dict[str, Any], merge_dict]
    evidence_lineage: NotRequired[dict[str, Any] | None]
    evidence_chain_breaks: NotRequired[list[dict[str, Any]] | None]
    endpoint_extraction: Annotated[list[dict[str, Any]], merge_records]
    sota_benchmark_matrix: Annotated[list[dict[str, Any]], merge_records]
    equivalence_matrix: Annotated[list[dict[str, Any]], merge_records]
    similar_device_four_step_confirmation: Annotated[list[dict[str, Any]], merge_records]
    similar_device_attachment_index: Annotated[list[dict[str, Any]], merge_records]
    vigilance_recall_registry: Annotated[list[dict[str, Any]], merge_records]
    vigilance_event_statistics: Annotated[list[dict[str, Any]], merge_records]
    risk_trace_matrix: Annotated[list[dict[str, Any]], merge_records]
    rmf_hazard_trace: Annotated[dict[str, Any], merge_dict]
    ifu_warning_rmf_crosswalk: Annotated[dict[str, Any], merge_dict]
    benefit_risk_closure_matrix: Annotated[dict[str, Any], merge_dict]
    pmcf_plan_control_matrix: Annotated[dict[str, Any], merge_dict]
    gspr_coverage: Annotated[list[dict[str, Any]], merge_records]
    cer_chapter_drafts: Annotated[dict[str, Any], merge_dict]
    qa_gate_report: Annotated[dict[str, Any], merge_dict]
    gap_pmcf_recommendations: Annotated[list[dict[str, Any]], merge_records]
    pmcf_boundary_decision_log: Annotated[list[dict[str, Any]], merge_records]
    marketing_pms_customer_questionnaire: Annotated[list[dict[str, Any]], merge_records]
    reviewer_results: Annotated[list[dict[str, Any]], append_list]
    lead_decisions: Annotated[list[dict[str, Any]], append_list]
    virtual_review_dimensions: Annotated[list[dict[str, Any]], merge_records]
    mcp_call_log: Annotated[list[dict[str, Any]], append_list]
    mcp_tool_results: Annotated[dict[str, Any], merge_dict]
    template_guidance: Annotated[dict[str, Any], merge_dict]
    writing_brief: Annotated[dict[str, Any], merge_dict]
    ap_template_profile: Annotated[dict[str, Any], merge_dict]
    template_logic_profile: Annotated[dict[str, Any], merge_dict]
    engineer_comment_profile: Annotated[dict[str, Any], merge_dict]
    human_cer_comparison_report: Annotated[dict[str, Any], merge_dict]
    human_style_benchmark_report: Annotated[dict[str, Any], merge_dict]
    vigilance_relevance_screening: Annotated[list[dict[str, Any]], merge_records]
    subagent_invocation_log: Annotated[list[dict[str, Any]], append_list]
    rework_queue: Annotated[list[dict[str, Any]], merge_records]
    authoring_workbook: Annotated[dict[str, Any], merge_dict]
    stage_results: Annotated[list[dict[str, Any]], append_list]
    model_provider_preflight: Annotated[dict[str, Any], merge_dict]
    spiral_round_id: NotRequired[int | None]
    evidence_lineage_frozen: Annotated[bool, operator.or_]
    evidence_lineage_frozen_at_stage: Annotated[str | None, _keep_first]
    evidence_lineage_frozen_reason: Annotated[str | None, _keep_first]

    authoring_baseline_version: NotRequired[str | None]
    calibration_case_schema: Annotated[dict[str, Any], merge_dict]
    artifact_consumption_contract: Annotated[list[dict[str, Any]], merge_records]
    failure_taxonomy_cer_authoring: Annotated[list[dict[str, Any]], merge_records]
    cer_section_trace_map_schema: Annotated[list[dict[str, Any]], merge_records]
    gate_to_upstream_repair_map: Annotated[list[dict[str, Any]], merge_records]
    authoring_baseline_freeze_manifest: Annotated[dict[str, Any], merge_dict]
    calibration_event_log: Annotated[list[dict[str, Any]], merge_records]
    run_scope_audit: Annotated[dict[str, Any], merge_dict]
    review_feedback: NotRequired[dict[str, Any] | None]
    resolved_feedback_ids: Annotated[list[str], merge_records]
    feedback_resolution_log: Annotated[list[dict[str, Any]], merge_records]

    # ── V3.1 keys: SOTA Benchmark Derivation Layer ──
    clinical_fact_registry: Annotated[list[dict[str, Any]], merge_records]
    endpoint_selection_table: Annotated[list[dict[str, Any]], merge_records]
    reference_framework: Annotated[dict[str, Any], merge_dict]
    treatment_landscape: Annotated[dict[str, Any], merge_dict]
    sota_endpoint_master: Annotated[list[dict[str, Any]], merge_records]
    sota_source_role_matrix: Annotated[dict[str, Any], merge_dict]
    sota_benchmark_candidate_records: Annotated[list[dict[str, Any]], merge_records]
    sota_comparability_matrix: Annotated[list[dict[str, Any]], merge_records]
    sota_evidence_weighting: Annotated[dict[str, Any], merge_dict]
    sota_benchmark_derivation: Annotated[dict[str, Any], merge_dict]
    own_data_alignment_matrix: Annotated[list[dict[str, Any]], merge_records]
    sota_comparison_conclusions: Annotated[list[dict[str, Any]], merge_records]
    endpoint_selection_completed: Annotated[bool, operator.or_]
    clinical_fact_registry_locked: Annotated[bool, operator.or_]
    search_ledger_integrity_checked: Annotated[bool, operator.or_]
    pmcf_need_determination: Annotated[dict[str, Any], merge_dict]
    single_clinical_analysis_applied: Annotated[bool, operator.or_]
    hc_sota_benchmark_decision: Annotated[dict[str, Any], merge_dict]
