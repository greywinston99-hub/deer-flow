"""Tests for isolated CER authoring runtime scaffolding."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from deerflow.runtime.cer_authoring.agents import (
    PHYSICAL_AGENT_NAMES,
    REVIEW_GATE_AGENT_NAMES,
    VIRTUAL_REVIEW_DIMENSIONS,
    build_authoring_subagent_configs,
)
from deerflow.runtime.cer_authoring.agent_runtime import (
    _authoring_parent_model,
    _state_summary,
    isolate_initial_authoring_state,
    preload_gil_safe_native_modules,
    reviewer_result_from_invocation,
    sanitize_run_scoped_state_for_agent_prompt,
)
from deerflow.runtime.cer_authoring.artifacts import build_authoring_workbook, write_authoring_artifacts
from deerflow.runtime.cer_authoring.gates import (
    evaluate_alignment_gate,
    evaluate_br_justified_gate,
    evaluate_claim_evidence_gate,
    evaluate_fulltext_basis_gate,
    evaluate_pre_writer_readiness_gate,
    evaluate_retrieval_domain_gate,
    evaluate_screening_depth_gate,
    run_authoring_gates,
)
from deerflow.runtime.cer_authoring.graph import (
    _node_controlled_compromise,
    _node_evidence_sufficiency_gate,
    _node_retrieval_domain_gate,
    _node_pre_writer_readiness_gate,
    _node_query_expansion,
    _route_after_evidence_sufficiency_gate,
    _route_after_retrieval_domain_gate,
    _route_after_pre_writer_readiness_gate,
)
from deerflow.runtime.cer_authoring.graph import build_cer_authoring_graph
from deerflow.runtime.cer_authoring import pipeline


def _passing_state():
    engineer_tokens = "MDR Article 61 clinical benefit equivalence is not claimed marketing history vigilance SOTA benchmark GSPR benefit-risk comparison section conclusion clinical pathway alternative treatment guideline hazard acceptance criterion section 4.7. "
    dense_reasoning = (engineer_tokens + "Controlled CER reasoning question with Evidence E-001, Benchmark B-001, Claim C-01, IFU trace, GSPR linkage, analysis limitation and conclusion. ") * 140
    dense_table = "\n".join(["| ID | Evidence | Benchmark | Conclusion |", "| --- | --- | --- | --- |"] + [f"| ROW-{i:02d} | E-001 | B-001 | controlled |" for i in range(30)])
    return {
        "source_inventory": [
            {
                "source_id": "SRC-IFU-001",
                "document_type": "IFU",
                "filename": "IFU.docx",
                "source_role": "subject_device_ifu",
                "primary_for_authoring": True,
                "excluded_from_device_profile": False,
            }
        ],
        "source_role_report": {
            "status": "PASS",
            "locked_domain_hint": "urology_uas",
            "subject_ifu_source_ids": ["SRC-IFU-001"],
            "excluded_similar_ifu_source_ids": [],
        },
        "device_identity_lock": {
            "status": "PASS",
            "locked_domain": "urology_uas",
            "subject_ifu_source_ids": ["SRC-IFU-001"],
            "identity_statement": "Fixture device identity locked.",
        },
        "domain_contamination_report": {"locked_domain": "urology_uas", "findings": [], "status": "PASS"},
        "device_profile": {
            "device_name": "Fixture Device",
            "device_type": "sheath",
            "intended_purpose": "Clinical access and procedure support under IFU-defined conditions",
            "target_population": "adult patients",
            "mode_of_action": "Mechanical access and fluid evacuation",
            "device_domain": "urology_uas",
        },
        "claim_ledger": [{"claim_id": "C-01", "claim_type": "intended_purpose", "required_evidence": "fixture evidence"}],
        "intended_purpose_claim_table": [{"claim_id": "C-01", "element": "intended_purpose", "statement": "fixture claim"}],
        "cep_pico_matrix": [
            {
                "pico_id": "PICO-01",
                "claim_id": "C-01",
                "outcome": "clinical success",
                "derivation_rationale": "IFU claim -> clinical uncertainty -> PICO -> concepts -> query",
            }
        ],
        "search_run_registry": [
            {
                "search_id": "SEARCH-SOTA-01",
                "database": "PubMed",
                "objective": "SOTA",
                "search_date": "2026-05-06",
                "query": "fixture",
                "result_count": 1,
            },
            {"search_id": "SEARCH-SOTA-02", "database": "Europe PMC", "objective": "SOTA", "search_date": "2026-05-06", "query": "fixture", "result_count": 1},
            {"search_id": "SEARCH-SOTA-02B", "database": "ClinicalTrials.gov", "objective": "SOTA", "search_date": "2026-05-06", "query": "fixture", "result_count": 1},
            {"search_id": "SEARCH-SOTA-02C", "database": "EU Clinical Trials Register", "objective": "SOTA", "search_date": "2026-05-06", "query": "fixture", "result_count": None, "status": "source_unavailable"},
            {"search_id": "SEARCH-SOTA-03", "database": "Embase", "objective": "SOTA", "search_date": "2026-05-06", "query": "fixture", "result_count": None, "status": "auth_required"},
            {"search_id": "SEARCH-SOTA-04", "database": "Cochrane Library", "objective": "SOTA", "search_date": "2026-05-06", "query": "fixture", "result_count": None, "status": "auth_required"},
        ],
        "literature_search_protocol_profile": {"research_question_formulation": "IFU claim -> uncertainty -> PICO -> query -> appraisal -> benchmark"},
        "sota_pico_strategy": [{"row_id": "SOTA-PICO-001", "purpose": "SOTA", "population": "adult patients", "intervention": "urology", "comparator": "standard practice", "outcome": "safety/performance", "query": "fixture", "rationale": "fixture"}],
        "due_pico_strategy": [{"row_id": "DUE-PICO-001", "purpose": "Device under Evaluation", "population": "adult patients", "intervention": "Fixture Device", "comparator": "similar device", "outcome": "safety/performance", "query": "fixture device", "rationale": "fixture"}],
        "database_search_source_table": [
            {"row_id": "DB-001", "search_id": "SEARCH-SOTA-01", "database": "PubMed", "purpose": "SOTA", "search_date": "2026-05-06", "query": "fixture", "result_count": 1, "returned_count": 1, "status": "ok"},
            {"row_id": "DB-002", "search_id": "SEARCH-SOTA-02", "database": "Europe PMC", "purpose": "SOTA", "search_date": "2026-05-06", "query": "fixture", "result_count": 1, "returned_count": 1, "status": "ok"},
            {"row_id": "DB-002B", "search_id": "SEARCH-SOTA-02B", "database": "ClinicalTrials.gov", "purpose": "SOTA", "search_date": "2026-05-06", "query": "fixture", "result_count": 1, "returned_count": 1, "status": "ok"},
            {"row_id": "DB-002C", "search_id": "SEARCH-SOTA-02C", "database": "EU Clinical Trials Register", "purpose": "SOTA", "search_date": "2026-05-06", "query": "fixture", "result_count": None, "returned_count": 0, "status": "source_unavailable", "limitation": "source currently unavailable"},
            {"row_id": "DB-003", "search_id": "SEARCH-SOTA-03", "database": "Embase", "purpose": "SOTA", "search_date": "2026-05-06", "query": "fixture", "result_count": None, "returned_count": 0, "status": "auth_required", "limitation": "subscription limitation"},
            {"row_id": "DB-004", "search_id": "SEARCH-SOTA-04", "database": "Cochrane Library", "purpose": "SOTA", "search_date": "2026-05-06", "query": "fixture", "result_count": None, "returned_count": 0, "status": "auth_required", "limitation": "subscription limitation"},
        ],
        "literature_defined_limits": [{"row_id": "LIMIT-001", "parameter": "language", "default": "no language exclusion", "deviation_rule": "English-only is deviation"}],
        "literature_flow_registry": [{"row_id": "FLOW-001", "search_id": "SEARCH-SOTA-01", "database": "PubMed", "objective": "SOTA", "retrieved_count": 1, "returned_count": 1, "deduplicated_count": 1, "title_abstract_screened": 1, "full_text_assessed": 1, "included_count": 1, "excluded_count": 0, "status": "ok"}],
        "protocol_deviation_log": [{"deviation_id": "DEV-001", "search_id": "SEARCH-SOTA-03", "database": "Embase", "deviation_type": "source_access_limitation", "description": "auth required", "impact": "limited", "control": "request access"}],
        "prisma_flow_data": {
            "identification": {"database_records": 4, "returned_records": 2, "source_limitation_records": 3},
            "screening": {"deduplicated_records": 2, "title_abstract_screened": 1, "title_abstract_excluded": 0, "full_text_assessed": 1, "full_text_excluded": 0},
            "included": {"sota_included": 1, "due_included": 0, "total_included": 1},
            "limitations": "fixture",
        },
        "prisma_flow_diagram": {"mermaid": "flowchart TD\nA[Identification] --> B[Screening] --> C[Included]"},
        "sota_search_strategy_table": [{"row_id": "STR-001", "search_id": "SEARCH-SOTA-01", "database": "PubMed", "purpose": "SOTA", "query": "fixture", "result_count": 1, "deduplicated_count": 1, "screening_use": "benchmark", "conclusion": "fixture"}],
        "sota_screening_disposition_table": [{"row_id": "SOTA-SCR-001", "screen_id": "SCR-001", "article_id": "ART-001", "search_id": "SEARCH-SOTA-01", "title": "fixture", "title_abstract_decision": "include", "full_text_decision": "include_for_appraisal", "purpose": "SOTA screening", "conclusion": "accepted"}],
        "sota_ck_appraisal_table": [{"row_id": "SOTA-CK-001", "article_id": "ART-001", "search_id": "SEARCH-SOTA-01", "title": "fixture", "score": 6, "disposition": "accepted", "evidence_category": "systematic_review_meta_analysis", "evidence_hierarchy": "high", "endpoint_contribution": "benchmark", "clinical_relevance": "fixture", "evidence_use": "benchmark", "limitation": "fixture"}],
        "due_suitability_contribution_table": [{"row_id": "DUE-SC-001", "article_id": "ART-001", "evidence_id": "E-001", "score": 18, "weight_effect": "pivotal", "disposition": "accepted_not_pivotal", "limitation": "fixture"}],
        "screening_disposition": [{"screen_id": "SCR-001", "article_id": "ART-001", "title_abstract_decision": "include"}],
        "article_appraisal": [{"article_id": "ART-001", "evidence_id": "E-001", "weight": "pivotal"}],
        "evidence_registry": [
            {
                "evidence_id": "E-001",
                "weight": "pivotal",
                "verified": True,
                "sample_size": "100",
                "follow_up": "30 days",
                "endpoint": "clinical success",
                "result": "95%",
            }
        ],
        "endpoint_extraction": [
            {
                "endpoint_id": "EP-001",
                "evidence_id": "E-001",
                "benchmark_id": "B-001",
                "endpoint": "clinical success",
                "sample_size": "100",
                "timepoint": "30 days",
                "statistical_result": "95%",
                "full_text_page_or_section": "page 4 table 2",
                "extraction_basis": "user-provided full text page/table-level endpoint extraction",
            }
        ],
        "sota_benchmark_matrix": [{"benchmark_id": "B-001", "endpoint": "clinical success", "clinical_significance": "fixture clinical meaning", "sota_source": "SEARCH-SOTA-01", "used_in_4_7": True, "acceptance_criterion": "fixture criterion", "conclusion": "fixture"}],
        "alternative_treatment_benchmark_table": [{"row_id": "ALT-001", "option": "standard practice", "mechanism": "fixture", "benchmark_use": "comparator", "conclusion": "fixture"}],
        "guideline_pathway_table": [{"row_id": "GL-001", "guideline_or_source": "fixture guideline", "pathway": "clinical pathway", "endpoint_relevance": "fixture", "device_positioning_impact": "fixture", "conclusion": "fixture"}],
        "similar_benchmark_device_table": [{"row_id": "SBD-001", "device_class": "similar device", "evidence_use": "benchmark only", "limitation": "fixture", "conclusion": "fixture"}],
        "hazard_source_table": [{"row_id": "HZ-001", "hazard_source": "procedure", "hazard_family": "hazard", "sota_use": "risk benchmark", "conclusion": "fixture"}],
        "sota_to_47_usage_matrix": [{"row_id": "S47-001", "benchmark_id": "B-001", "endpoint": "clinical success", "section_4_7_use": "4.7 analysis", "used_in_4_7": True, "conclusion": "fixture"}],
        "full_text_request_list": [],
        "sota_literature_quantity_justification": {
            "status": "below_target_controlled",
            "included_count": 1,
            "search_exhaustion_rationale": "fixture search exhaustion",
            "database_limitations": "fixture limitation",
            "screening_rationale": "fixture screening",
            "evidence_gap_control": "fixture control",
            "clinical_impact": "fixture clinical impact",
        },
        "sota_endpoint_derivation_table": [{"row_id": "SOTA-DER-001", "pico_id": "SOTA-PICO-001", "search_id": "SEARCH-SOTA-01", "article_id": "ART-001", "evidence_id": "E-001", "endpoint_id": "EP-001", "benchmark_id": "B-001", "full_text_page_table_section": "page 4 table 2", "endpoint_definition": "clinical success", "numerator_denominator": "95/100", "sample_size": "100", "timepoint": "30 days", "statistical_result": "95%", "clinical_meaning": "fixture clinical meaning", "benchmark_value_or_range": "95%", "limitation": "fixture", "use_in_section_4_7": "4.7 analysis", "conclusion": "fixture"}],
        "sota_quantitative_benchmark_table": [{"row_id": "SOTA-QBM-001", "benchmark_id": "B-001", "endpoint": "clinical success", "clinical_meaning": "fixture clinical meaning", "source_evidence_ids": "E-001", "source_page_or_table": "page 4 table 2", "derived_value_or_range": "95%", "acceptance_criterion": "fixture criterion", "limitation": "fixture", "section_4_7_use": "4.7 analysis", "conclusion": "fixture"}],
        "sota_evidence_synthesis_matrix": [{"row_id": "SOTA-SYN-001", "evidence_id": "E-001", "article_id": "ART-001", "endpoint_id": "EP-001", "benchmark_id": "B-001", "evidence_weight": "pivotal", "sample_size": "100", "timepoint": "30 days", "statistical_result": "95%", "applicability": "fixture", "sota_use": "benchmark", "conclusion": "fixture"}],
        "sota_medical_field_boundary": [{"row_id": "SOTA-FIELD-001", "element": "medical field", "definition": "fixture field", "source_basis": "IFU", "boundary_rule": "fixture", "extrapolation_limit": "fixture", "use_in_cer": "SOTA/4.7", "conclusion": "fixture"}],
        "sota_pico_v2_strategy": [{"row_id": "SOTA-PICO-V2-001", "source_pico_id": "SOTA-PICO-001", "population": "adult patients", "intervention": "fixture", "comparator": "standard practice", "outcome": "clinical success", "revision_logic": "fixture", "query": "fixture", "conclusion": "fixture"}],
        "sota_search_strategy_separated": [{"row_id": "SOTA-SEARCH-SEP-001", "search_id": "SEARCH-SOTA-01", "database": "PubMed", "search_role": "SOTA", "query": "fixture", "separation_rule": "fixture", "result_count": 1, "conclusion": "fixture"}],
        "sota_screening_prisma": [{"row_id": "SOTA-SCREEN-001", "phase": "screening", "metric": "ART-001", "value": "include", "exclusion_reason": "", "conclusion": "fixture"}],
        "sota_evidence_hierarchy": [{"row_id": "SOTA-EH-001", "article_id": "ART-001", "evidence_id": "E-001", "evidence_category": "systematic_review_meta_analysis", "evidence_level": "level 1", "weight": "pivotal", "endpoint_contribution": "benchmark", "limitation": "fixture", "conclusion": "fixture"}],
        "sota_endpoint_extraction_fulltext": [{"row_id": "SOTA-FT-EP-001", "endpoint_id": "EP-001", "benchmark_id": "B-001", "evidence_id": "E-001", "endpoint": "clinical success", "sample_size": "100", "timepoint": "30 days", "statistical_result": "95%", "full_text_trace": "page 4 table 2", "full_text_status": "full_text_or_source_trace_present", "conclusion": "fixture"}],
        "sota_benchmark_derivation_table": [{"row_id": "SOTA-BM-DER-001", "benchmark_id": "B-001", "endpoint": "clinical success", "clinical_meaning": "fixture", "derived_value_or_range": "95%", "source_evidence_ids": "E-001", "acceptance_criterion": "fixture", "limitation": "fixture", "conclusion": "fixture"}],
        "sota_section_conclusion_matrix": [{"row_id": "SOTA-CONC-001", "section": "3.8", "topic": "Endpoints", "required_conclusion_logic": "fixture", "trace_source": "fixture", "use_in_cer": "section conclusion", "conclusion": "fixture"}],
        "sota_deduction_chain": [
            {
                "row_id": f"SOTA-STEP-{idx:03d}",
                "step_number": idx,
                "logic_question": f"Why/how question {idx}",
                "why": "fixture why",
                "how": "fixture how",
                "source_basis": "fixture source",
                "output_artifact": "fixture artifact",
                "conclusion_control": "fixture conclusion control",
            }
            for idx in range(1, 8)
        ],
        "sota_endpoint_source_classification": [
            {
                "row_id": "SOTA-ENDSRC-001",
                "benchmark_id": "B-001",
                "endpoint": "clinical success",
                "endpoint_family": "performance_or_clinical_benefit_endpoint",
                "source_class": "aggregate_systematic_review_or_meta_analysis",
                "allowed_endpoint_use": "May support benchmark derivation",
                "source_basis": "E-001",
                "clinical_relevance_rationale": "fixture",
                "limitation": "fixture",
                "conclusion": "fixture",
            }
        ],
        "sota_aggregate_benchmark_rationale": [
            {
                "row_id": "SOTA-AGG-001",
                "benchmark_id": "B-001",
                "endpoint": "clinical success",
                "benchmark_value_or_range": "95%",
                "aggregate_basis_status": "aggregate_available",
                "aggregate_source_requirement": "systematic review/meta-analysis/registry",
                "source_evidence_ids": "E-001",
                "single_study_control": "single isolated study cannot define benchmark without downgrade",
                "allowed_conclusion_strength": "quantitative SOTA comparison allowed after applicability check",
                "limitation": "fixture",
                "conclusion": "fixture",
            }
        ],
        "sota_conclusion_strength_guard": [
            {
                "row_id": "SOTA-CG-001",
                "guard_scope": "Overall SOTA conclusion",
                "highest_evidence_level": "level 1",
                "pivotal_evidence_count": 2,
                "comparator_basis": "aggregate comparator available",
                "superiority_claim_allowed": False,
                "allowed_language": "consistent with SOTA / acceptable / partially supported",
                "prohibited_language": "superior, proven better, definitive",
                "reason": "fixture evidence-level guard",
                "conclusion": "fixture",
            }
        ],
        "equivalence_matrix": [{"comparison_id": "EQ-001", "confidence": "not_claimed", "difference_impact_conclusion": "not claimed"}],
        "similar_device_four_step_confirmation": [
            {"row_id": "SIM-STEP-001", "step": "Step 1 - European market verification", "source": "EUDAMED", "execution_record": "fixture", "required_evidence": "EU market evidence", "status": "source_limited", "conclusion": "fixture"},
            {"row_id": "SIM-STEP-002", "step": "Step 2 - Trade name and manufacturer identification", "source": "GUDID", "execution_record": "fixture", "required_evidence": "trade name", "status": "first_pass_recorded", "conclusion": "fixture"},
            {"row_id": "SIM-STEP-003", "step": "Step 3 - Technical parameter comparison", "source": "equivalence_matrix", "execution_record": "fixture", "required_evidence": "specification", "status": "conditional", "conclusion": "fixture"},
            {"row_id": "SIM-STEP-004", "step": "Step 4 - Attachment package index", "source": "similar_device_attachment_index", "execution_record": "fixture", "required_evidence": "attachments", "status": "generated_request", "conclusion": "fixture"},
        ],
        "similar_device_attachment_index": [
            {"attachment_id": f"ATT-SIM-{idx:03d}", "required_document": "fixture source", "use_in_cer": "similar-device confirmation", "if_missing": "downgrade or request source"}
            for idx in range(1, 11)
        ],
        "risk_trace_matrix": [{"risk_id": "R-001", "rmf_coverage": "gap", "ifu_coverage": "covered by IFU source text"}],
        "gspr_coverage": [{"gspr_id": "GSPR-1", "coverage_status": "partial", "mapped_evidence": "E-001"}],
        "vigilance_recall_registry": [
            {"database": "FDA MAUDE"},
            {"database": "FDA Device Recall"},
            {"database": "MHRA"},
            {"database": "BfArM"},
            {"database": "Swissmedic"},
            {"database": "EUDAMED vigilance", "raw_status": "source_unavailable"},
            {"database": "New Zealand Medsafe", "raw_status": "source_unavailable"},
        ],
        "vigilance_event_statistics": [{"row_id": "VES-001", "database": "EUDAMED vigilance", "result_count": 0, "relevant_count": 0, "event_categories": "source limited", "risk_trace_link": "R-001", "status": "source_unavailable", "conclusion": "fixture"}],
        "marketing_pms_customer_questionnaire": [
            {"row_id": f"MQ-{idx:03d}", "customer_question": "fixture question", "cer_use": "marketing/PMS closure", "rationale": "fixture", "status": "requested"}
            for idx in range(1, 11)
        ],
        "gap_pmcf_recommendations": [{"gap_id": "GAP-RMF-001", "gap": "RMF missing", "pmcf_measure": "upgrade later"}],
        "cer_chapter_drafts": {
            "1 Summary": dense_reasoning + dense_table,
            "2 Scope of Clinical Evaluation": dense_reasoning + dense_table,
            "3 Clinical Background, Current Knowledge and SOTA": dense_reasoning + dense_table,
            "4 Device Under Evaluation": ("4.1 pathway. 4.2 equivalence. 4.3 manufacturer data. 4.4 search. 4.5 appraisal. 4.6 vigilance. 4.7 GSPR Evidence Benchmark analysis. " * 120) + dense_table,
            "5 Conclusions": dense_reasoning + dense_table,
            "6 Date of Next Clinical Evaluation": dense_reasoning + dense_table,
            "7 Evaluator Qualification": dense_reasoning,
            "8 Declaration of Interest": dense_reasoning,
            "9 Dates and Signatures": dense_reasoning,
            "Annex A Source Inventory and Input Completeness": dense_reasoning + dense_table,
            "Annex B Claim Ledger": dense_reasoning + dense_table,
            "Annex C PICO Derivation and Search Protocol": dense_reasoning + dense_table,
            "Annex D Literature Screening and Evidence Appraisal": dense_reasoning + dense_table,
            "Annex E Endpoint Benchmark Matrix": dense_reasoning + dense_table,
            "Annex F Equivalence and Similar Device Use": dense_reasoning + dense_table,
            "Annex G Vigilance and Recall Registry": dense_reasoning + dense_table,
            "Annex H Risk, IFU, RMF, PMS/PMCF and GSPR Trace": dense_reasoning + dense_table,
            "Annex I Evidence Gaps and PMCF Recommendations": dense_reasoning + dense_table,
            "Annex J MCP Execution and Human Template Benchmark": dense_reasoning + dense_table,
        },
        "qa_gate_report": {"nb_precheck_report": {"critical_count": 0, "high_risk_count": 0}},
        "human_style_benchmark_report": {"status": "PASS", "score": 90},
        "ap_template_profile": {"template_count": 6, "templates": [{"filename": "AP CER template", "template_role": "main CER chapter structure"}]},
        "template_logic_profile": {
            "chapter_logic": [{"chapter": "1 Summary", "writing_logic": "question evidence analysis limitation conclusion benchmark GSPR"}],
            "depth_rules": ["question", "evidence", "analysis", "limitation"],
        },
        "engineer_comment_profile": {
            "schema_name": "cer_engineer_comment_profile",
            "themes": [
                {"theme_id": f"theme_{idx}", "writing_rule": "fixture"}
                for idx in range(1, 7)
            ],
        },
        "human_cer_comparison_report": {"status": "ok", "key_gaps_ranked": []},
        "vigilance_relevance_screening": [{"screening_id": "VRS-001", "database": "FDA MAUDE", "relevance": "potentially_relevant"}],
        "subagent_invocation_log": [
            {"agent": name, "status": "CONFIGURED"}
            for name in PHYSICAL_AGENT_NAMES
        ],
        "mcp_call_log": [
            {"server": "doc-proc", "tool": "extract_document_metadata", "status": "ok"},
            {"server": "cer-kb", "tool": "get_best_template", "status": "ok"},
            {"server": "cer-kb", "tool": "generate_writing_brief", "status": "ok"},
            {"server": "nb-check", "tool": "generate_search_strategy", "status": "ok"},
            {"server": "nb-check", "tool": "predict_deficiencies", "status": "ok"},
            {"server": "cer-public-evidence", "tool": "pubmed_search", "status": "ok"},
            {"server": "cer-public-evidence", "tool": "clinicaltrials_search", "status": "ok"},
            {"server": "cer-public-evidence", "tool": "euctr_search", "status": "source_unavailable"},
            {"server": "cer-public-evidence", "tool": "embase_search", "status": "auth_required"},
            {"server": "cer-public-evidence", "tool": "cochrane_reviews_search", "status": "auth_required"},
            {"server": "cer-public-evidence", "tool": "eudamed_device_search", "status": "source_unavailable"},
            {"server": "cer-public-evidence", "tool": "eudamed_vigilance_search", "status": "source_unavailable"},
            {"server": "cer-public-evidence", "tool": "nz_medsafe_safety_search", "status": "source_unavailable"},
            {"server": "cer-public-evidence", "tool": "fda_maude_search", "status": "ok"},
            {"server": "cer-public-evidence", "tool": "fda_recall_search", "status": "ok"},
        ],
        "reviewer_results": [
            *[{"agent": name, "status": "RECORDED", "covered_by": "authoring-qa-review-agent"} for name in VIRTUAL_REVIEW_DIMENSIONS],
            {"agent": "authoring-final-gate-closure", "status": "RECORDED"},
        ],
        "virtual_review_dimensions": [{"agent": name, "status": "PASS", "covered_by": "authoring-qa-review-agent"} for name in VIRTUAL_REVIEW_DIMENSIONS],
        "agent_team_mode": "stable-1plus6",
    }


def test_authoring_review_gate_agents_are_internal_and_present():
    configs = build_authoring_subagent_configs()

    for name in PHYSICAL_AGENT_NAMES:
        assert name in configs
        assert configs[name].model == "inherit"

    for name in REVIEW_GATE_AGENT_NAMES:
        assert name in configs
        assert configs[name].model == "inherit"
        assert "task" in (configs[name].disallowed_tools or [])


def test_strict_v7_authoring_defaults_to_kimi_api_not_failover_router(monkeypatch):
    monkeypatch.setenv("CER_AUTHORING_STRICT_V7", "1")
    monkeypatch.delenv("CER_AUTHORING_MODEL_NAME", raising=False)

    assert _authoring_parent_model({}) == "kimi-k2.6-api"


def test_authoring_model_env_override_wins(monkeypatch):
    monkeypatch.setenv("CER_AUTHORING_STRICT_V7", "1")
    monkeypatch.setenv("CER_AUTHORING_MODEL_NAME", "custom-authoring-model")

    assert _authoring_parent_model({}) == "custom-authoring-model"
    assert _authoring_parent_model({"model_name": "explicit-model"}) == "explicit-model"


def test_authoring_gates_pass_controlled_complete_state():
    report = run_authoring_gates(_passing_state())

    assert report["decision"] == "PASS_TO_DRAFT_DOCX"
    assert report["failed_gate_count"] == 0


def test_authoring_gates_enforce_prisma_similar_vigilance_and_market_controls():
    state = _passing_state()
    state["prisma_flow_data"] = {}
    state["similar_device_four_step_confirmation"] = []
    state["vigilance_recall_registry"] = [{"database": "FDA MAUDE"}]
    state["marketing_pms_customer_questionnaire"] = []

    report = run_authoring_gates(state)

    failed = {item["gate_id"] for item in report["results"] if item["status"] != "PASS"}
    assert {"G32", "G33", "G34", "G35"}.issubset(failed)


def test_strict_g24_requires_1plus6_physical_agents(monkeypatch):
    monkeypatch.setenv("CER_AUTHORING_STRICT_V7", "1")
    state = _passing_state()
    state["subagent_invocation_log"] = [
        {"agent": name, "status": "COMPLETED", "mode": "llm_subagent"}
        for name in PHYSICAL_AGENT_NAMES
    ]

    report = run_authoring_gates(state)

    failed = {item["gate_id"] for item in report["results"] if item["status"] != "PASS"}
    assert "G24" not in failed


def test_integrated_qa_covers_virtual_review_dimensions():
    report = run_authoring_gates(_passing_state())

    g18 = next(item for item in report["results"] if item["gate_id"] == "G18")
    assert g18["status"] == "PASS"


def test_engineer_comment_theme_gate_is_enforced():
    state = _passing_state()
    state["engineer_comment_profile"] = {}

    report = run_authoring_gates(state)

    g21b = next(item for item in report["results"] if item["gate_id"] == "G21b")
    assert g21b["status"] == "REWORK_REQUIRED"


def test_qa_pass_with_conditions_is_not_blocking():
    review, rework = reviewer_result_from_invocation(
        {
            "agent": "authoring-qa-review-agent",
            "mode": "llm_subagent",
            "status": "COMPLETED",
            "result": '{"decision":"PASS_WITH_CONDITIONS","findings":{"evidence":"advisory gap"},"rework_targets":[{"priority":"P2"}]}',
        }
    )

    assert review["status"] == "PASS"
    assert rework == []


def test_qa_controlled_pass_with_rework_is_not_blocking():
    review, rework = reviewer_result_from_invocation(
        {
            "agent": "authoring-qa-review-agent",
            "mode": "llm_subagent",
            "status": "COMPLETED",
            "result": '{"decision":"CONTROLLED_PASS_WITH_REWORK","findings":{"endpoint":"advisory gap"},"rework_targets":[{"priority":"P2"}]}',
        }
    )

    assert review["status"] == "PASS"
    assert rework == []


def test_authoring_gates_block_missing_ifu_and_unverified_pivotal():
    state = _passing_state()
    state["source_inventory"] = []
    state["evidence_registry"] = [{"evidence_id": "E-FAKE", "weight": "pivotal", "verified": False}]

    report = run_authoring_gates(state)

    assert report["decision"] in {"REWORK_REQUIRED", "HUMAN_HOLD"}
    failed = {item["gate_id"] for item in report["results"] if item["status"] != "PASS"}
    assert "G0" in failed
    assert "G5" in failed


def test_g46_pre_writer_readiness_pass_routes_to_writer():
    report = evaluate_pre_writer_readiness_gate({})
    update = _node_pre_writer_readiness_gate({})

    assert report["gate_id"] == "G46"
    assert report["status"] == "PASS"
    assert report["next_node"] == "cer_writing"
    assert all(row["status"] == "PASS" for row in report["conditions"])
    assert _route_after_pre_writer_readiness_gate(update) == "cer_writing"


def test_g46_pre_writer_readiness_rework_uses_upstream_causality_priority():
    state = {
        "pre_writer_readiness_condition_overrides": {
            "alignment": {"status": "REWORK", "message": "alignment late failure"},
            "retrieval_domain": {"status": "REWORK", "message": "retrieval domain earlier failure"},
        }
    }

    report = evaluate_pre_writer_readiness_gate(state)
    update = _node_pre_writer_readiness_gate(state)

    assert report["status"] == "REWORK_REQUIRED"
    assert report["route_condition"] == "retrieval_domain"
    assert report["next_node"] == "sota_search"
    assert _route_after_pre_writer_readiness_gate(update) == "sota_search"


def test_g46_pre_writer_readiness_blocked_routes_to_controlled_compromise():
    state = {"pre_writer_readiness_condition_overrides": {"fulltext_basis": {"status": "BLOCKED", "message": "full text exhausted"}}}

    report = evaluate_pre_writer_readiness_gate(state)
    update = _node_pre_writer_readiness_gate(state)

    assert report["status"] == "BLOCKED"
    assert report["next_node"] == "controlled_compromise"
    assert report["writer_invoked"] is False
    assert _route_after_pre_writer_readiness_gate(update) == "controlled_compromise"


def test_batch_3_1_g39_to_g45_gate_signals_are_structured_and_permissive_by_default():
    for evaluator, gate_id in (
        (evaluate_retrieval_domain_gate, "G39"),
        (evaluate_screening_depth_gate, "G40"),
        (evaluate_fulltext_basis_gate, "G41"),
        (evaluate_claim_evidence_gate, "G43"),
        (evaluate_br_justified_gate, "G44"),
        (evaluate_alignment_gate, "G45"),
    ):
        signal = evaluator({})

        assert signal["gate_id"] == gate_id
        assert signal["status"] == "PASS"
        assert {
            "gate_id",
            "status",
            "failure_pattern",
            "upstream_node_to_reroute",
            "spiral_round",
            "blocked_reason",
            "reroute_context",
            "gate_routing_trace",
        }.issubset(signal)
        assert signal["gate_routing_trace"][0]["gate_id"] == gate_id
        assert "upstream_node_to_reroute" in signal["gate_routing_trace"][0]


def test_batch_3_1_g39_to_g45_gate_overrides_route_rework_and_blocked():
    state = {
        "hard_gate_signal_overrides": {
            "G39": {"status": "REWORK", "failure_pattern": "domain drift", "upstream_node_to_reroute": "sota_search"},
            "G41": {"status": "BLOCKED", "failure_pattern": "no full text", "blocked_reason": "pivotal full text unavailable"},
        },
        "evidence_spiral_lineage": [{"spiral_round_id": 2}],
    }

    g39 = evaluate_retrieval_domain_gate(state)
    g41 = evaluate_fulltext_basis_gate(state)

    assert g39["status"] == "REWORK_REQUIRED"
    assert g39["failure_pattern"] == "domain drift"
    assert g39["upstream_node_to_reroute"] == "sota_search"
    assert g39["spiral_round"] == 2
    assert g39["reroute_context"]["override_applied"] is True
    assert g39["gate_routing_trace"][0]["reroute_context"]["override_applied"] is True
    assert g41["status"] == "BLOCKED"
    assert g41["next_node"] == "controlled_compromise"
    assert g41["blocked_reason"] == "pivotal full text unavailable"


def test_batch_3_3_g42_and_g46_include_full_gate_signal_contract_and_trace():
    g42 = pipeline.evaluate_evidence_sufficiency_gate(_passing_state())
    g46 = evaluate_pre_writer_readiness_gate(
        {"pre_writer_readiness_condition_overrides": {"BR": {"status": "REWORK", "message": "BR needs ledger rework"}}}
    )

    for signal in (g42, g46):
        assert {
            "gate_id",
            "status",
            "failure_pattern",
            "upstream_node_to_reroute",
            "spiral_round",
            "blocked_reason",
            "reroute_context",
            "gate_routing_trace",
        }.issubset(signal)
        assert signal["status"] in {"PASS", "REWORK_REQUIRED", "BLOCKED"}
        assert signal["gate_routing_trace"][0]["gate_id"] == signal["gate_id"]
        assert "reroute_context" in signal["gate_routing_trace"][0]


def test_batch_3_3_final_gate_results_include_structured_signal_fields():
    report = run_authoring_gates(_passing_state())
    first = report["results"][0]

    assert {
        "gate_id",
        "status",
        "failure_pattern",
        "upstream_node_to_reroute",
        "spiral_round",
        "blocked_reason",
        "reroute_context",
    }.issubset(first)

    hold_report = run_authoring_gates({**_passing_state(), "source_inventory": []})
    g0 = next(row for row in hold_report["results"] if row["gate_id"] == "G0")
    assert g0["status"] == "BLOCKED"
    assert g0["legacy_status"] == "HUMAN_HOLD"


def test_batch_3_1_g40_and_g45_detect_shallow_pool_and_alignment_conflict():
    shallow = evaluate_screening_depth_gate({"screened_candidate_pool": [{"article_id": "ART-001"}]})
    conflict = evaluate_alignment_gate(
        {
            "alignment_matrix": [
                {
                    "alignment_id": "ALIGN-001",
                    "claim_id": "C-01",
                    "alignment_status": "conflict",
                    "blocks_CER_conclusion": "yes",
                }
            ]
        }
    )

    assert shallow["status"] == "REWORK_REQUIRED"
    assert shallow["failure_pattern"] == "screening_pool_below_floor"
    assert shallow["upstream_node_to_reroute"] == "sota_search"
    assert conflict["status"] == "REWORK_REQUIRED"
    assert conflict["failure_pattern"] == "alignment_conflict_or_missing"
    assert conflict["upstream_node_to_reroute"] == "risk_gspr_mapping"


def test_batch_3_2_graph_routes_g39_rework_to_sota_search_and_blocked_to_compromise():
    rework = _node_retrieval_domain_gate(
        {
            "hard_gate_signal_overrides": {
                "G39": {"status": "REWORK", "failure_pattern": "retrieval domain mismatch", "upstream_node_to_reroute": "sota_search"}
            }
        }
    )
    blocked = _node_retrieval_domain_gate(
        {
            "hard_gate_signal_overrides": {
                "G39": {"status": "BLOCKED", "failure_pattern": "unrecoverable retrieval domain mismatch"}
            }
        }
    )

    assert _route_after_retrieval_domain_gate(rework) == "sota_search"
    assert rework["gate_routing_trace"][0]["upstream_node_routed_to"] == "sota_search"
    assert _route_after_retrieval_domain_gate(blocked) == "controlled_compromise"
    assert blocked["gate_routing_trace"][0]["blocked_reason"]


def test_controlled_compromise_node_builds_non_cer_insufficiency_packet():
    state = _passing_state()
    state.pop("cer_chapter_drafts", None)
    state["pre_writer_readiness_report"] = evaluate_pre_writer_readiness_gate(
        {"pre_writer_readiness_condition_overrides": {"fulltext_basis": {"status": "BLOCKED", "message": "full text exhausted"}}}
    )

    update = _node_controlled_compromise(state)

    assert update["status"] == "controlled_compromise"
    assert update["final_gate_decision"] == "HUMAN_HOLD"
    assert update["compromise_manifest"]["writer_invoked"] is False
    assert update["compromise_manifest"]["cer_draft_generated"] is False
    assert update["compromise_manifest"]["blocked_conditions"]
    assert "What Cannot Be Concluded" in update["evidence_status_report"]
    assert "supplement_evidence" in update["recommendation"]
    assert update["human_decision_required"]["decisions"]
    assert "cer_chapter_drafts" not in update


def test_batch_2_2_g42_pass_routes_to_reasoning_chain():
    state = _passing_state()
    report = pipeline.evaluate_evidence_sufficiency_gate(state)
    update = _node_evidence_sufficiency_gate(state)

    assert report["gate_id"] == "G42"
    assert report["status"] == "PASS"
    assert report["next_node"] == "sota_clinical_context"
    assert _route_after_evidence_sufficiency_gate(update) == "claim_evidence_matrix"
    assert report["claim_sufficiency"][0]["sufficiency_status"] == "PASS"


def test_batch_2_2_g42_rework_routes_to_query_expansion_and_records_lineage():
    state = {
        "evidence_sufficiency_gate_override": {"status": "REWORK", "message": "pool too shallow"},
        "raw_literature_records": [
            {"article_id": "ART-001", "pmid": "111", "title": "A"},
            {"article_id": "ART-002", "pmid": "111", "title": "A duplicate"},
            {"article_id": "ART-003", "doi": "10.1/x", "title": "B"},
        ],
        "search_run_registry": [{"search_id": "SEARCH-SOTA-01", "query": "domain locked query"}],
    }
    gate_update = _node_evidence_sufficiency_gate(state)

    assert _route_after_evidence_sufficiency_gate(gate_update) == "query_expansion"
    expansion = _node_query_expansion({**state, **gate_update})

    assert expansion["spiral_round_id"] == 2
    assert expansion["spiral_query_expansion_request"]["strategy"] == "mesh_adjacent_database_citation_chasing"
    assert expansion["evidence_spiral_lineage"][0]["spiral_round_id"] == 2
    assert expansion["evidence_spiral_lineage"][0]["query_delta"]
    assert len(expansion["raw_literature_records"]) == 2


def test_batch_2_2_g42_blocked_routes_to_controlled_compromise_after_round_three():
    state = {
        "evidence_sufficiency_gate_override": {"status": "REWORK", "message": "still insufficient"},
        "evidence_spiral_lineage": [{"spiral_round_id": 3, "sufficiency_after_round": "REWORK"}],
    }

    update = _node_evidence_sufficiency_gate(state)

    assert update["evidence_sufficiency_gate_report"]["status"] == "BLOCKED"
    assert _route_after_evidence_sufficiency_gate(update) == "controlled_compromise"


def test_batch_2_3_g42_reworks_when_claim_lacks_sufficient_evidence():
    state = _passing_state()
    state["evidence_registry"] = [
        {
            "evidence_id": "E-001",
            "weight": "background",
            "verified": True,
            "endpoint": "clinical success",
            "sample_size": "100",
            "follow_up": "30 days",
            "result": "95%",
        }
    ]

    report = pipeline.evaluate_evidence_sufficiency_gate(state)

    assert report["status"] == "REWORK_REQUIRED"
    assert report["next_node"] == "pre_g42_claim_evidence_candidate_linking"
    assert report["insufficient_claims"]


def test_batch_2_3_g42_low_directness_requires_cautious_strength():
    state = _passing_state()
    state["evidence_registry"] = [
        {
            "evidence_id": "E-001",
            "weight": "supportive",
            "verified": True,
            "directness": "low",
            "device_relevance": "medium",
            "population_relevance": "medium",
            "endpoint_match": "medium",
            "appraisal_basis": "extended_abstract_or_structured_summary",
            "conclusion_strength_allowed": "cautious_descriptive_only",
            "endpoint": "clinical success",
            "sample_size": "100",
            "follow_up": "30 days",
            "result": "95%",
        }
    ]

    report = pipeline.evaluate_evidence_sufficiency_gate(state)

    assert report["status"] == "PASS"
    assert report["claim_sufficiency"][0]["best_directness"] == "low"
    assert report["claim_sufficiency"][0]["best_allowed_conclusion_strength"] == "cautious_descriptive_only"


def test_batch_5_7_linking_gap_routes_to_pre_g42_candidate_linking():
    state = {"claim_ledger": [{"claim_id": "C-01", "claim_type": "clinical_benefit", "claim_text": "clinical benefit"}]}

    report = pipeline.evaluate_evidence_sufficiency_gate(state)

    assert report["status"] == "REWORK_REQUIRED"
    assert "SOURCE_TYPE_REQUIREMENT_NOT_MET" in report["failure_pattern"]
    assert report["next_node"] == "evidence_appraisal"
    assert report["reroute_context"]["repair_routes_by_claim"]["C-01"] == "evidence_appraisal"


def test_batch_5_7_endpoint_gap_routes_to_endpoint_extraction():
    state = {
        "claim_ledger": [{"claim_id": "C-01", "claim_type": "clinical_benefit", "claim_text": "clinical benefit"}],
        "pre_g42_claim_evidence_candidate_matrix": [
            {
                "claim_id": "C-01",
                "claim_type": "clinical_benefit",
                "candidate_evidence_ids": "E-001",
                "candidate_count": 1,
                "best_evidence_id": "E-001",
                "best_role": "supportive",
                "best_applicability": "high",
                "best_directness": "medium",
                "best_endpoint_or_outcome_family_match": "none",
                "best_full_text_status": "available",
                "semantic_support_relation": "contextual_background",
                "sufficiency_status": "REWORK_REQUIRED",
                "failure_pattern": "ENDPOINT_GAP",
                "repair_route": "endpoint_extraction",
                "insufficiency_reason_if_any": "Endpoint family remap required.",
            }
        ],
    }

    report = pipeline.evaluate_evidence_sufficiency_gate(state)

    assert report["status"] == "REWORK_REQUIRED"
    assert report["next_node"] == "endpoint_extraction"
    assert "ENDPOINT_GAP" in report["reroute_context"]["failure_patterns"]


def test_batch_5_7_ifu_safety_warning_uses_non_literature_source_support():
    state = _passing_state()
    state["claim_ledger"] = [
        {
            "claim_id": "C-WARN",
            "claim_type": "safety",
            "claim_text": "Warning: do not use if sterile package is damaged.",
        }
    ]
    state["source_inventory"] = [
        {"source_id": "SRC-IFU", "document_type": "IFU", "filename": "IFU.docx"},
        {"source_id": "SRC-RMF", "document_type": "RMF", "filename": "Risk management file.docx"},
        {"source_id": "SRC-GSPR", "document_type": "GSPR", "filename": "GSPR checklist.xlsx"},
    ]
    state["evidence_registry"] = []

    update = pipeline.build_pre_g42_claim_evidence_candidate_matrix(state)
    report = pipeline.evaluate_evidence_sufficiency_gate({**state, **update})

    row = update["pre_g42_claim_evidence_candidate_matrix"][0]
    assert row["claim_type"] == "IFU_safety_warning"
    assert row["primary_evidence_source_type"] == "IFU"
    assert row["required_source_profile"] == "(IFU) AND (RMF)"
    assert row["source_profile_status"] == "PASS"
    assert row["sufficiency_status"] == "PASS"
    assert "SRC-IFU" in row["candidate_evidence_ids"]
    assert "SRC-RMF" in row["candidate_evidence_ids"]
    assert report["status"] == "PASS"


def test_batch_6_5_ifu_warning_missing_rmf_routes_to_source_requirement_repair():
    state = _passing_state()
    state["claim_ledger"] = [
        {
            "claim_id": "C-WARN",
            "claim_type": "IFU_safety_warning",
            "claim_text": "Warning: do not use if sterile package is damaged.",
        }
    ]
    state["source_inventory"] = [{"source_id": "SRC-IFU", "document_type": "IFU", "filename": "IFU.docx"}]
    state["evidence_registry"] = []

    update = pipeline.build_pre_g42_claim_evidence_candidate_matrix(state)
    report = pipeline.evaluate_evidence_sufficiency_gate({**state, **update})
    row = update["pre_g42_claim_evidence_candidate_matrix"][0]

    assert row["source_profile_status"] == "SOURCE_TYPE_REQUIREMENT_NOT_MET"
    assert row["source_profile_unmet_clauses"] == "RMF"
    assert row["failure_pattern"] == "SOURCE_TYPE_REQUIREMENT_NOT_MET"
    assert report["next_node"] == "risk_gspr_mapping"


def test_batch_6_5_blocking_missing_data_cannot_be_supportive_for_g42():
    state = _passing_state()
    state["source_inventory"] = []
    state["claim_ledger"] = [{"claim_id": "C-01", "claim_type": "clinical_benefit", "claim_text": "clinical benefit"}]
    state["evidence_registry"] = [
        {
            "evidence_id": "E-BLOCK-001",
            "weight": "supportive",
            "verified": True,
            "source_type": "literature_pubmed_sota",
            "pmid": "123",
            "endpoint": "clinical benefit",
            "sample_size": "not extracted",
            "follow_up": "not extracted",
            "result": "not extracted",
            "endpoint_match": "high",
            "missing_data_flags": ["sample_size_not_extracted", "endpoint_statistics_not_extracted"],
            "missing_data_impact": "BLOCKING",
            "missing_data_rationale": "Quantitative endpoint data not extracted.",
        }
    ]
    state["sota_benchmark_matrix"] = [{"benchmark_id": "BM-01", "corresponding_claim_id": "C-01"}]
    state["sota_endpoint_derivation_table"] = [{"benchmark_id": "BM-01", "evidence_id": "E-BLOCK-001", "endpoint_id": "EP-01", "benchmark_value": "not extracted"}]

    update = pipeline.build_pre_g42_claim_evidence_candidate_matrix(state)
    report = pipeline.evaluate_evidence_sufficiency_gate({**state, **update})
    row = update["pre_g42_claim_evidence_candidate_matrix"][0]

    assert row["best_missing_data_impact"] == "BLOCKING"
    assert "sample_size_not_extracted" in row["best_missing_data_flags"]
    assert row["failure_pattern"] == "MISSING_DATA_BLOCKING"
    assert report["next_node"] == "query_expansion"


def test_batch_6_5_allowed_use_block_routes_to_query_expansion():
    state = _passing_state()
    state["claim_ledger"] = [{"claim_id": "C-01", "claim_type": "clinical_benefit", "claim_text": "clinical benefit"}]
    state["allowed_use_matrix"] = [
        {
            "claim_id": "C-01",
            "evidence_id": "E-COMP-001",
            "allowed_use_decision": "blocked",
            "block_reason_codes": "CLAIM_TYPE_NOT_ALLOWED, DEVICE_RELATIONSHIP_FORBIDDEN",
        }
    ]
    state["pre_g42_claim_evidence_candidate_matrix"] = [
        {
            "claim_id": "C-01",
            "claim_type": "clinical_benefit",
            "candidate_count": 1,
            "candidate_evidence_ids": "E-COMP-001",
            "sufficiency_status": "REWORK_REQUIRED",
            "failure_pattern": "ALLOWED_USE_BLOCKED",
            "repair_route": "query_expansion",
            "insufficiency_reason_if_any": "Allowed-use verification blocked all candidates.",
        }
    ]

    report = pipeline.evaluate_evidence_sufficiency_gate(state)

    assert report["next_node"] == "query_expansion"
    assert "ALLOWED_USE_BLOCKED" in report["reroute_context"]["failure_patterns"]


def test_batch_5_7_endpoint_low_full_text_does_not_automatically_become_supportive():
    weight = pipeline._evidence_weight_from_appraisal(
        verified=True,
        study_design="Prospective cohort",
        oxford_level="Level 3",
        full_text_status="full_text_available",
        device_applicability="high",
        population_applicability="high",
        endpoint_match="low",
        sample_size="n=120",
        statistical_adequacy="adequate_for_extracted_endpoint",
    )

    assert weight == "background"


def test_batch_5_7_semantic_support_can_promote_endpoint_low_evidence_when_justified():
    weight = pipeline._evidence_weight_from_appraisal(
        verified=True,
        study_design="Prospective cohort",
        oxford_level="Level 3",
        full_text_status="full_text_available",
        device_applicability="high",
        population_applicability="high",
        endpoint_match="low",
        sample_size="n=120",
        statistical_adequacy="adequate_for_extracted_endpoint",
        semantic_support_relation="indirectly_supports",
        source_appropriateness="high",
        directness="medium",
    )

    assert weight == "supportive"


def test_batch_5_7_g42_routes_are_failure_pattern_specific_not_all_sota_search():
    routes = []
    for pattern in ["LINKING_GAP", "ENDPOINT_GAP", "CLAIM_SOURCE_MISMATCH", "EVIDENCE_TRULY_INSUFFICIENT"]:
        state = {
            "claim_ledger": [{"claim_id": f"C-{pattern}", "claim_type": "clinical_benefit", "claim_text": "clinical benefit"}],
            "pre_g42_claim_evidence_candidate_matrix": [
                {
                    "claim_id": f"C-{pattern}",
                    "claim_type": "clinical_benefit",
                    "candidate_count": 0,
                    "sufficiency_status": "REWORK_REQUIRED",
                    "failure_pattern": pattern,
                    "insufficiency_reason_if_any": pattern,
                }
            ],
        }
        routes.append(pipeline.evaluate_evidence_sufficiency_gate(state)["next_node"])

    assert "sota_search" not in routes
    assert len(set(routes)) > 1


def test_batch_5_7_writer_still_blocked_when_pre_writer_readiness_not_pass():
    state = _passing_state()
    state["pre_writer_readiness_report"] = {"status": "REWORK_REQUIRED", "failure_pattern": "evidence_sufficiency"}

    result = pipeline.write_cer_chapters(state)

    assert result["writer_invocation_allowed"] is False
    assert "cer_chapter_drafts" not in result


def test_batch_2_4_spiral_lineage_records_required_fields_and_freezes_on_compromise():
    state = {
        "evidence_sufficiency_gate_report": {"status": "REWORK_REQUIRED", "rework_reason": "claim C-01 lacks endpoint-matched evidence"},
        "raw_literature_records": [{"article_id": "ART-001", "pmid": "111"}],
        "search_run_registry": [{"search_id": "SEARCH-SOTA-01", "query": "domain locked query"}],
        "pre_writer_readiness_report": {
            "status": "BLOCKED",
            "compromise_reason": "G42 exhausted the bounded evidence spiral.",
            "failing_sub_conditions": [{"condition_name": "evidence_sufficiency", "status": "BLOCKED"}],
        },
    }

    expansion = pipeline.query_expansion(state)
    lineage = expansion["evidence_spiral_lineage"][0]

    assert {
        "spiral_round_id",
        "rework_trigger_gate",
        "rework_reason",
        "query_before",
        "query_delta",
        "records_before",
        "records_added",
        "records_total",
        "screened_delta",
        "appraised_delta",
        "sufficiency_after_round",
    }.issubset(lineage)

    compromise = pipeline.build_controlled_compromise_report({**state, **expansion})

    assert compromise["evidence_lineage_frozen"] is True
    assert compromise["evidence_lineage_frozen_at_stage"] == "controlled_compromise"
    assert compromise["evidence_spiral_lineage"][0]["lineage_frozen"] is True


def test_batch_2_4_workbook_and_export_include_spiral_lineage_and_gate_trace(tmp_path):
    state = {
        "evidence_spiral_lineage": [
            {
                "spiral_round_id": 1,
                "rework_trigger_gate": "initial_search",
                "rework_reason": "Initial domain-locked retrieval round.",
                "query_before": "",
                "query_delta": "R1 domain-locked query",
                "records_before": 0,
                "records_added": 2,
                "records_total": 2,
                "screened_delta": 0,
                "appraised_delta": 0,
                "sufficiency_after_round": "PASS",
            }
        ],
        "gate_routing_trace": [
            {
                "gate_id": "G42",
                "invocation_order": 1,
                "status": "PASS",
                "failure_pattern": "",
                "upstream_node_routed_to": "",
                "spiral_round": 1,
                "blocked_reason": "",
            }
        ],
    }

    workbook = build_authoring_workbook(state)
    written = write_authoring_artifacts(tmp_path, state)

    assert workbook["evidence_spiral_lineage"][0]["spiral_round_id"] == 1
    assert workbook["gate_routing_trace"][0]["gate_id"] == "G42"
    assert str(tmp_path / "evidence_spiral_lineage.json") in written
    assert str(tmp_path / "gate_routing_trace.csv") in written
    assert json.loads((tmp_path / "evidence_spiral_lineage.json").read_text(encoding="utf-8"))[0]["records_total"] == 2
    assert "upstream_node_routed_to" in (tmp_path / "gate_routing_trace.csv").read_text(encoding="utf-8")


def test_source_role_separates_subject_ifu_from_competitor_folder():
    state = {
        "project_id": "PROJECT_YUANHE",
        "input_root": "/tmp/圆和 肾盂镜",
        "target_keywords": ["一次性使用电子输尿管肾盂内窥镜导管", "肾盂镜", "Yuanhe"],
        "source_inventory": [
            {
                "source_id": "SRC-FILE-001",
                "path": "/tmp/圆和 肾盂镜/2.1 YH 一次性使用电子输尿管肾盂内窥镜导管 产品使用说明书.doc",
                "filename": "2.1 YH 一次性使用电子输尿管肾盂内窥镜导管 产品使用说明书.doc",
                "document_type": "IFU",
            },
            {
                "source_id": "SRC-FILE-002",
                "path": "/tmp/圆和 肾盂镜/6.6 同类产品说明书收集/51551333-01A_LITHOVUE_IFU_EU_ML_s.pdf",
                "filename": "51551333-01A_LITHOVUE_IFU_EU_ML_s.pdf",
                "document_type": "IFU",
            },
        ],
    }

    result = pipeline.prepare_source_inventory(state)
    by_name = {row["filename"]: row for row in result["source_inventory"]}

    subject = by_name["2.1 YH 一次性使用电子输尿管肾盂内窥镜导管 产品使用说明书.doc"]
    competitor = by_name["51551333-01A_LITHOVUE_IFU_EU_ML_s.pdf"]
    assert subject["source_role"] == "subject_device_ifu"
    assert subject["primary_for_authoring"] is True
    assert competitor["source_role"] == "similar_device_ifu"
    assert competitor["excluded_from_device_profile"] is True
    assert competitor["primary_for_authoring"] is False


def test_phase0_3_ifu_detection_handles_cal003_ligating_clip_filename(tmp_path):
    source = tmp_path / "CAL-003" / "01_IFU"
    source.mkdir(parents=True)
    ifu = source / "TF-TLC-0301_IFU-Ligating clips(Ti).docx"
    ifu.write_text("IFU content", encoding="utf-8")

    result = pipeline.prepare_source_inventory({"project_id": "CAL-003", "input_root": str(tmp_path / "CAL-003")})

    row = next(item for item in result["source_inventory"] if item["filename"] == ifu.name)
    assert row["document_type"] == "IFU"
    assert row["source_role"] == "subject_device_ifu"
    assert row["primary_for_authoring"] is True
    assert result["source_role_report"]["subject_ifu_source_ids"] == [row["source_id"]]
    assert result["source_role_report"]["ifu_candidate_ranking"][0]["source_id"] == row["source_id"]


def test_phase0_3_ifu_detection_case_and_chinese_patterns(tmp_path):
    root = tmp_path / "source"
    files = [
        root / "01_IFU" / "ifu_lowercase.docx",
        root / "01_IFU" / "IFU_UPPERCASE.docx",
        root / "01_IFU" / "Mixed_IfU_Name.docx",
        root / "中文" / "产品使用说明书.docx",
        root / "中文" / "产品说明书.docx",
    ]
    for path in files:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("IFU content", encoding="utf-8")

    result = pipeline.prepare_source_inventory({"project_id": "IFU-PATTERNS", "input_root": str(root)})
    by_name = {item["filename"]: item for item in result["source_inventory"]}

    for path in files:
        assert by_name[path.name]["document_type"] == "IFU"
        assert by_name[path.name]["source_role"] == "subject_device_ifu"
    assert len(result["source_role_report"]["ifu_candidate_ranking"]) == len(files)
    assert result["source_role_report"]["multiple_subject_ifu_candidates"] is True


def test_phase0_3_ifu_folder_promotes_reasonable_document(tmp_path):
    source = tmp_path / "source" / "01_IFU"
    source.mkdir(parents=True)
    path = source / "TF-TLC-0301 Ligating clips Ti.docx"
    path.write_text("Instructions content", encoding="utf-8")

    result = pipeline.prepare_source_inventory({"project_id": "IFU-FOLDER", "input_root": str(tmp_path / "source")})
    row = next(item for item in result["source_inventory"] if item["filename"] == path.name)

    assert row["document_type"] == "IFU"
    assert row["source_role"] == "subject_device_ifu"
    assert row["excluded_from_device_profile"] is False


def test_phase0_3_locked_final_ifu_is_not_writer_source(tmp_path):
    root = tmp_path / "project"
    initial = root / "01_INITIAL_INPUT_FOR_WRITER" / "01_IFU"
    locked = root / "03_FINAL_CERTIFIED_PACKAGE_LOCKED" / "01_IFU"
    initial.mkdir(parents=True)
    locked.mkdir(parents=True)
    subject = initial / "TF-TLC-0301_IFU-Ligating clips(Ti).docx"
    locked_ifu = locked / "FINAL_IFU.docx"
    subject.write_text("subject IFU", encoding="utf-8")
    locked_ifu.write_text("locked final IFU", encoding="utf-8")

    result = pipeline.prepare_source_inventory({"project_id": "LOCKED-IFU", "input_root": str(root)})
    by_name = {item["filename"]: item for item in result["source_inventory"]}

    assert by_name[subject.name]["source_role"] == "subject_device_ifu"
    assert by_name[locked_ifu.name]["document_type"] == "locked_delta_only"
    assert by_name[locked_ifu.name]["source_role"] == "locked_delta_only"
    assert by_name[locked_ifu.name]["primary_for_authoring"] is False
    assert by_name[locked_ifu.name]["excluded_from_device_profile"] is True
    assert by_name[locked_ifu.name]["source_id"] not in result["source_role_report"]["subject_ifu_source_ids"]


def test_phase0_4_cal003_ligating_clip_not_classified_as_stent():
    identity = pipeline._classify_device_identity(
        "TF-TLC-0301_IFU-Ligating clips(Ti)",
        "The device is intended for ligating of tubular structures or vessels during surgery.",
        "Ligating clips hemostatic clips vascular clips intended for ligating of tubular structures or vessels.",
        {"source_inventory": [{"source_id": "SRC-IFU-001", "document_type": "IFU", "source_role": "subject_device_ifu"}]},
    )

    assert identity["device_type"] == "ligating clip"
    assert identity["device_family"] == "surgical ligating clip"
    assert identity["clinical_domain"] == "surgical_ligating_clip"
    assert identity["classification_confidence"] == "high"
    assert identity["device_type"] != "stent"
    assert identity["anatomical_site"] == "tubular structures or vessels as defined in the IFU"


def test_phase0_4_cal002_hemoperfusion_fixture_not_unrelated_stent():
    identity = pipeline._classify_device_identity(
        "Hemoperfusion cartridge IFU",
        "The device is intended for extracorporeal hemoperfusion and blood purification.",
        "hemoperfusion adsorber cartridge blood purification cartridge 灌流器 吸附器",
        {"source_inventory": [{"source_id": "SRC-IFU-002", "document_type": "IFU", "source_role": "subject_device_ifu"}]},
    )

    assert identity["device_type"] == "hemoperfusion adsorber cartridge"
    assert identity["device_family"] == "blood purification adsorber"
    assert identity["clinical_domain"] == "blood_purification_hemoperfusion"
    assert identity["device_type"] != "stent"


def test_phase0_4_cal001_padn_rf_ablation_catheter_classification():
    identity = pipeline._classify_device_identity(
        "PADN RF Ablation Catheter IFU",
        "The catheter is intended for pulmonary artery denervation using radiofrequency ablation.",
        "radiofrequency ablation catheter PADN pulmonary artery denervation RF ablation catheter",
        {"source_inventory": [{"source_id": "SRC-IFU-003", "document_type": "IFU", "source_role": "subject_device_ifu"}]},
    )

    assert identity["device_type"] == "radiofrequency ablation catheter"
    assert identity["device_family"] == "energy ablation catheter"
    assert identity["clinical_domain"] == "cardiovascular_rf_ablation_catheter"
    assert identity["device_type"] != "stent"


def test_g18_accessory_sections_excluded_before_device_identity_classification():
    text = "\n".join(
        [
            "Product Name",
            "PADN RF Ablation Catheter",
            "Intended Use",
            "The catheter is intended for pulmonary artery denervation using radiofrequency ablation.",
            "Kit contents",
            "1. Puncture needle",
            "2. Local anesthesia syringe",
            "3. Nerve block needle",
            "Working Principle",
            "Radiofrequency energy is delivered through the ablation catheter to the pulmonary artery target.",
        ]
    )

    cleaned = pipeline._exclude_accessory_sections(text)
    excluded = pipeline._excluded_accessory_tokens(text)
    identity = pipeline._classify_device_identity(
        "PADN RF Ablation Catheter IFU",
        "The catheter is intended for pulmonary artery denervation using radiofrequency ablation.",
        cleaned,
        {"source_inventory": [{"source_id": "SRC-G18", "document_type": "IFU", "source_role": "subject_device_ifu", "text": text}]},
    )

    assert "Puncture needle" not in cleaned
    assert any(row["token"] == "puncture needle" for row in excluded)
    assert identity["clinical_domain"] == "cardiovascular_rf_ablation_catheter"
    assert identity["device_type"] == "radiofrequency ablation catheter"


def test_g18_inline_accessory_components_do_not_compete_with_rf_ablation_identity():
    text = "\n".join(
        [
            "Product Name: PADN RF Ablation Catheter",
            "Intended Use: The catheter is intended for pulmonary artery denervation using radiofrequency ablation.",
            "Components: RF ablation catheter, cable, puncture needle, nerve block needle for local anesthesia.",
            "Working Principle: Radiofrequency energy is delivered through the ablation catheter.",
        ]
    )

    cleaned = pipeline._exclude_accessory_sections(text)
    excluded = pipeline._excluded_accessory_tokens(text)
    identity = pipeline._classify_device_identity(
        "PADN RF Ablation Catheter IFU",
        "The catheter is intended for pulmonary artery denervation using radiofrequency ablation. Components: puncture needle, nerve block needle.",
        cleaned,
        {"source_inventory": [{"source_id": "SRC-G18-INLINE", "document_type": "IFU", "source_role": "subject_device_ifu", "text": text}]},
    )

    assert "puncture needle" not in cleaned.lower()
    assert any(row["token"] == "puncture needle" for row in excluded)
    assert identity["clinical_domain"] == "cardiovascular_rf_ablation_catheter"
    assert all(row["clinical_domain"] != "nerve_block_needle" for row in identity["alternative_candidates"])


def test_g18_build_device_profile_logs_excluded_accessory_tokens_and_keeps_padn_mode(monkeypatch):
    monkeypatch.setattr(pipeline.mcp_tools, "call_tool", lambda *args, **kwargs: {"status": "ok"})
    monkeypatch.setattr(pipeline.mcp_tools, "mcp_log_entry", lambda result, name: {"tool": name, "status": result.get("status")})

    ifu_text = "\n".join(
        [
            "Product Name",
            "PADN RF Ablation Catheter",
            "Intended Use",
            "The catheter is intended for pulmonary artery denervation using radiofrequency ablation.",
            "Components",
            "Puncture needle",
            "Nerve block needle for local anesthesia",
            "Working Principle",
            "The RF ablation catheter delivers radiofrequency energy for PADN.",
        ]
    )
    state = {
        "project_id": "CAL-001",
        "target_keywords": ["PADN", "radiofrequency ablation catheter"],
        "source_role_report": {"locked_domain_hint": "cardiovascular_rf_ablation_catheter", "subject_ifu_source_ids": ["SRC-IFU-CAL001"]},
        "source_inventory": [
            {
                "source_id": "SRC-IFU-CAL001",
                "document_type": "IFU",
                "source_role": "subject_device_ifu",
                "filename": "PADN_RF_Ablation_Catheter_IFU.docx",
                "path": "/tmp/CAL-001/01_IFU/PADN_RF_Ablation_Catheter_IFU.docx",
                "text": ifu_text,
                "excluded_from_device_profile": False,
                "primary_for_authoring": True,
            }
        ],
    }

    result = pipeline.build_device_profile(state)
    profile = result["device_profile"]
    arbitration = result["device_identity_arbitration"]

    assert profile["clinical_domain"] == "cardiovascular_rf_ablation_catheter"
    assert "Radiofrequency energy" in profile["mode_of_action"] or "radiofrequency energy" in profile["mode_of_action"]
    assert "drug injection" not in profile["mode_of_action"].lower()
    assert arbitration["excluded_accessory_tokens"]
    assert any(row["token"] == "puncture needle" for row in arbitration["excluded_accessory_tokens"])


def test_g18_inline_accessory_components_keep_arbitration_pass_for_padn(monkeypatch):
    monkeypatch.setattr(pipeline.mcp_tools, "call_tool", lambda *args, **kwargs: {"status": "ok"})
    monkeypatch.setattr(pipeline.mcp_tools, "mcp_log_entry", lambda result, name: {"tool": name, "status": result.get("status")})

    ifu_text = "\n".join(
        [
            "Product Name: PADN RF Ablation Catheter",
            "Intended Use: The catheter is intended for pulmonary artery denervation using radiofrequency ablation.",
            "Components: RF ablation catheter, cable, puncture needle, nerve block needle for local anesthesia.",
            "Working Principle: The RF ablation catheter delivers radiofrequency energy for PADN.",
        ]
    )
    state = {
        "project_id": "CAL-001",
        "target_keywords": ["PADN", "radiofrequency ablation catheter"],
        "source_role_report": {"locked_domain_hint": "cardiovascular_rf_ablation_catheter", "subject_ifu_source_ids": ["SRC-IFU-CAL001"]},
        "source_inventory": [
            {
                "source_id": "SRC-IFU-CAL001",
                "document_type": "IFU",
                "source_role": "subject_device_ifu",
                "filename": "PADN_RF_Ablation_Catheter_IFU.docx",
                "path": "/tmp/CAL-001/01_IFU/PADN_RF_Ablation_Catheter_IFU.docx",
                "text": ifu_text,
                "excluded_from_device_profile": False,
                "primary_for_authoring": True,
            }
        ],
    }

    result = pipeline.build_device_profile(state)
    profile = result["device_profile"]
    arbitration = result["device_identity_arbitration"]

    assert profile["clinical_domain"] == "cardiovascular_rf_ablation_catheter"
    assert profile["mode_of_action"] == "Radiofrequency energy delivery through a catheter to ablate target tissue."
    assert arbitration["arbitration_status"] == "PASS"
    assert arbitration.get("conflicts") == []


def test_g18_rf_ablation_generator_text_does_not_fall_through_to_pfa_domain():
    text = "Multi-pole Pulmonary Artery RF Ablation Generator Operation Manual for pulmonary artery radiofrequency ablation."

    assert pipeline._clinical_domain_from_text(text) == "cardiovascular_rf_ablation_catheter"


def test_phase0_6_locked_domain_hint_is_strongest_against_llm_classifier_conflict():
    state = {
        "project_id": "CAL-001",
        "target_keywords": ["PADN", "radiofrequency ablation catheter"],
        "source_role_report": {
            "locked_domain_hint": "cardiovascular_rf_ablation_catheter",
            "subject_ifu_source_ids": ["SRC-IFU-CAL001"],
        },
        "source_inventory": [
            {
                "source_id": "SRC-IFU-CAL001",
                "document_type": "IFU",
                "source_role": "subject_device_ifu",
                "filename": "PADN_RF_Ablation_Catheter_IFU.docx",
                "path": "/tmp/CAL-001/01_IFU/PADN_RF_Ablation_Catheter_IFU.docx",
                "text": "The catheter is intended for pulmonary artery denervation using radiofrequency ablation.",
                "excluded_from_device_profile": False,
            },
            {
                "source_id": "SRC-GSPR-CAL001",
                "document_type": "GSPR",
                "source_role": "manufacturer_source",
                "filename": "GSPR_checklist.xlsx",
                "path": "/tmp/CAL-001/02_GSPR/GSPR_checklist.xlsx",
                "text": "Incidental checklist wording: diagnostic output and diagnostic software interface are not the subject device identity.",
                "excluded_from_device_profile": False,
            },
        ],
    }
    classifier_identity = {
        "device_type": "AI diagnostic software",
        "device_family": "software as a medical device",
        "clinical_domain": "ai_diagnostic_software",
        "classification_confidence": "high",
        "supporting_source_ids": ["SRC-GSPR-CAL001"],
    }

    arbitration = pipeline._arbitrate_device_identity_domain(
        state,
        "cardiovascular_rf_ablation_catheter",
        classifier_identity,
        intended_purpose="The catheter is intended for pulmonary artery denervation using radiofrequency ablation.",
        fallback_name="PADN RF Ablation Catheter IFU",
        source_basis_text="GSPR diagnostic software incidental wording",
    )

    assert arbitration["selected_domain"] == "cardiovascular_rf_ablation_catheter"
    assert arbitration["arbitration_status"] == "DEVICE_IDENTITY_CONFLICT"
    table = arbitration["device_identity_arbitration_table"]
    assert len(table) == 8
    assert table[0]["evidence_source"] == "locked_domain_hint"
    assert table[0]["strength"] == "STRONGEST"
    assert table[0]["arbitration_result"] == "SELECTED"
    llm_row = next(row for row in table if row["evidence_source"] == "llm_or_text_classifier")
    assert llm_row["observed_domain"] == "ai_diagnostic_software"
    assert llm_row["arbitration_result"] == "DEVICE_IDENTITY_CONFLICT"


def test_phase0_6_regression_cal002_ai_diagnostic_domain_selected():
    classifier_identity = {
        "device_type": "AI diagnostic software",
        "device_family": "software as a medical device",
        "clinical_domain": "ai_diagnostic_software",
        "classification_confidence": "high",
        "supporting_source_ids": ["SRC-IFU-CAL002"],
    }
    arbitration = pipeline._arbitrate_device_identity_domain(
        {
            "project_id": "CAL-002",
            "source_role_report": {"locked_domain_hint": "ai_diagnostic_software", "subject_ifu_source_ids": ["SRC-IFU-CAL002"]},
            "source_inventory": [
                {
                    "source_id": "SRC-IFU-CAL002",
                    "document_type": "IFU",
                    "source_role": "subject_device_ifu",
                    "filename": "AI_Diagnostic_Software_IFU.docx",
                    "path": "/tmp/CAL-002/01_IFU/AI_Diagnostic_Software_IFU.docx",
                    "text": "The software algorithm analyses medical images to assist diagnosis.",
                }
            ],
        },
        "ai_diagnostic_software",
        classifier_identity,
        intended_purpose="The software is intended to assist diagnosis.",
        fallback_name="AI Diagnostic Software IFU",
    )

    assert arbitration["selected_domain"] == "ai_diagnostic_software"
    assert arbitration["arbitration_status"] == "PASS"


def test_phase0_6_regression_cal003_surgical_ligating_domain_selected():
    classifier_identity = {
        "device_type": "ligating clip",
        "device_family": "surgical ligating clip",
        "clinical_domain": "surgical_ligating_clip",
        "classification_confidence": "high",
        "supporting_source_ids": ["SRC-IFU-CAL003"],
    }
    arbitration = pipeline._arbitrate_device_identity_domain(
        {
            "project_id": "CAL-003",
            "source_role_report": {"locked_domain_hint": "surgical_ligating_clip", "subject_ifu_source_ids": ["SRC-IFU-CAL003"]},
            "source_inventory": [
                {
                    "source_id": "SRC-IFU-CAL003",
                    "document_type": "IFU",
                    "source_role": "subject_device_ifu",
                    "filename": "TF-TLC-0301_IFU-Ligating clips(Ti).docx",
                    "path": "/tmp/CAL-003/01_IFU/TF-TLC-0301_IFU-Ligating clips(Ti).docx",
                    "text": "The device is intended for ligating of tubular structures or vessels during surgery.",
                }
            ],
        },
        "surgical_ligating_clip",
        classifier_identity,
        intended_purpose="The device is intended for ligating of tubular structures or vessels during surgery.",
        fallback_name="TF-TLC-0301_IFU-Ligating clips(Ti)",
    )

    assert arbitration["selected_domain"] == "surgical_ligating_clip"
    assert arbitration["arbitration_status"] == "PASS"


def test_phase0_7_diagnosis_alone_is_not_ai_diagnostic_software():
    identity = pipeline._classify_device_identity(
        "Clinical Procedure IFU",
        "According to the needs of clinical diagnosis, select the appropriate device.",
        "The document mentions diagnosis in generic clinical-use context and does not describe computerized analysis or digital decision outputs.",
        {"source_inventory": [{"source_id": "SRC-IFU-DIAG", "document_type": "IFU", "source_role": "subject_device_ifu"}]},
    )

    assert identity["clinical_domain"] != "ai_diagnostic_software"
    assert identity["clinical_domain"] != "software_medical_device"


def test_phase0_7_physical_diagnosis_context_suppresses_samd_path():
    identity = pipeline._classify_device_identity(
        "Disposable Nerve Block Puncture Needle",
        "Disposable Nerve Block Puncture Needle is used for puncture and injection of drugs during nerve block local anesthesia.",
        "According to the needs of clinical diagnosis, select the puncture needle of appropriate length. Sterile disposable 22G needle with stylet and material specification.",
        {"source_inventory": [{"source_id": "SRC-IFU-HOLD002", "document_type": "IFU", "source_role": "subject_device_ifu"}]},
    )

    assert identity["device_type"] == "nerve block puncture needle"
    assert identity["device_family"] == "sterile disposable puncture needle"
    assert identity["clinical_domain"] == "nerve_block_needle"
    assert identity["classification_confidence"] == "high"


def test_phase0_7_hold002_domain_hint_and_arbitration_select_nerve_block_needle():
    state = {
        "project_id": "HOLD-002",
        "input_root": "/tmp/HOLD-002/01_INITIAL_INPUT_FOR_WRITER",
        "target_keywords": ["Nerve Block Needle", "Puncture Needle", "Disposable", "神经阻滞针", "穿刺针", "一次性"],
        "source_role_report": {"locked_domain_hint": "nerve_block_needle", "subject_ifu_source_ids": ["SRC-IFU-HOLD002"]},
        "source_inventory": [
            {
                "source_id": "SRC-IFU-HOLD002",
                "document_type": "IFU",
                "source_role": "subject_device_ifu",
                "filename": "02-04 IFU.pdf",
                "path": "/tmp/HOLD-002/01_IFU/02-04 IFU.pdf",
                "text": "Disposable Nerve Block Puncture Needle is used for puncture and injection of drugs during nerve block local anesthesia. According to the needs of clinical diagnosis, select the puncture needle of appropriate length.",
            }
        ],
    }
    identity = pipeline._classify_device_identity(
        "Disposable Nerve Block Puncture Needle",
        "Disposable Nerve Block Puncture Needle is used for puncture and injection of drugs during nerve block local anesthesia.",
        "clinical diagnosis puncture needle sterile disposable gauge stylet material",
        state,
    )
    arbitration = pipeline._arbitrate_device_identity_domain(
        state,
        pipeline._initial_domain_hint(state, state["target_keywords"]),
        identity,
        intended_purpose="Disposable Nerve Block Puncture Needle is used for puncture and injection of drugs during nerve block local anesthesia.",
        fallback_name="Disposable Nerve Block Puncture Needle",
    )

    assert pipeline._initial_domain_hint(state, state["target_keywords"]) == "nerve_block_needle"
    assert identity["clinical_domain"] == "nerve_block_needle"
    assert arbitration["selected_domain"] == "nerve_block_needle"
    assert arbitration["arbitration_status"] == "PASS"
    assert arbitration["selected_evidence_source"] == "locked_domain_hint"


def test_phase0_7_cal002_ai_diagnostic_still_requires_software_specific_evidence():
    identity = pipeline._classify_device_identity(
        "CAL-002 AI Diagnostic Software",
        "The software is intended to assist diagnosis.",
        "The software algorithm analyses medical images to generate diagnostic output for clinical decision support using AI and machine learning.",
        {"source_inventory": [{"source_id": "SRC-IFU-CAL002", "document_type": "IFU", "source_role": "subject_device_ifu"}]},
    )

    assert identity["device_type"] == "AI diagnostic software"
    assert identity["clinical_domain"] == "ai_diagnostic_software"


def test_phase0_7_cal001_rf_ablation_not_overridden_by_diagnostic_gspr_context():
    state = {
        "project_id": "CAL-001",
        "target_keywords": ["PADN", "radiofrequency ablation catheter"],
        "source_role_report": {"locked_domain_hint": "cardiovascular_rf_ablation_catheter", "subject_ifu_source_ids": ["SRC-IFU-CAL001"]},
        "source_inventory": [
            {
                "source_id": "SRC-IFU-CAL001",
                "document_type": "IFU",
                "source_role": "subject_device_ifu",
                "filename": "PADN_RF_Ablation_Catheter_IFU.docx",
                "path": "/tmp/CAL-001/01_IFU/PADN_RF_Ablation_Catheter_IFU.docx",
                "text": "The catheter is intended for pulmonary artery denervation using radiofrequency ablation.",
            },
            {
                "source_id": "SRC-GSPR-CAL001",
                "document_type": "GSPR",
                "source_role": "manufacturer_source",
                "filename": "GSPR.xlsx",
                "path": "/tmp/CAL-001/02_GSPR/GSPR.xlsx",
                "text": "Incidental diagnostic output wording in a checklist does not define the subject device.",
            },
        ],
    }
    identity = pipeline._classify_device_identity(
        "PADN RF Ablation Catheter IFU",
        "The catheter is intended for pulmonary artery denervation using radiofrequency ablation.",
        "catheter radiofrequency ablation diagnostic output checklist wording",
        state,
    )
    arbitration = pipeline._arbitrate_device_identity_domain(
        state,
        "cardiovascular_rf_ablation_catheter",
        identity,
        intended_purpose="The catheter is intended for pulmonary artery denervation using radiofrequency ablation.",
        fallback_name="PADN RF Ablation Catheter IFU",
    )

    assert identity["clinical_domain"] == "cardiovascular_rf_ablation_catheter"
    assert arbitration["selected_domain"] == "cardiovascular_rf_ablation_catheter"
    assert arbitration["arbitration_status"] == "PASS"


def test_phase0_8_enteral_feeding_pump_classified_as_powered_therapeutic_not_stent():
    identity = pipeline._classify_device_identity(
        "CE TF Enteral Feeding Pump Link IFU",
        "The enteral feeding pump is intended to deliver enteral nutrition through a powered flow-controlled pump.",
        "The device includes motor drive, battery, flow rate control, occlusion alarm and enteral feeding delivery. Incidental comparison text mentions stent but not as the subject device.",
        {"source_inventory": [{"source_id": "SRC-IFU-HOLD001", "document_type": "IFU", "source_role": "subject_device_ifu"}]},
    )

    assert identity["device_type"] == "enteral feeding pump"
    assert identity["device_family"] == "powered therapeutic equipment"
    assert identity["clinical_domain"] == "powered_therapeutic_equipment"
    assert identity["classification_confidence"] == "high"
    assert identity["device_type"] != "stent"


def test_phase0_8_hold001_domain_hint_and_arbitration_select_powered_therapeutic():
    state = {
        "project_id": "HOLD-001",
        "input_root": "/tmp/HOLD-001/01_INITIAL_INPUT_FOR_WRITER",
        "target_keywords": ["Enteral Feeding Pump", "enteral nutrition", "feeding pump", "Link-07", "肠内营养泵", "喂养泵"],
        "source_role_report": {"locked_domain_hint": "powered_therapeutic_equipment", "subject_ifu_source_ids": ["SRC-IFU-HOLD001"]},
        "source_inventory": [
            {
                "source_id": "SRC-IFU-HOLD001",
                "document_type": "IFU",
                "source_role": "subject_device_ifu",
                "filename": "CE TF Enteral Feeding Pump Link IFU.docx",
                "path": "/tmp/HOLD-001/01_IFU/CE TF Enteral Feeding Pump Link IFU.docx",
                "text": "Enteral Feeding Pump Link delivers enteral nutrition using a powered pump, flow control, battery and alarm functions.",
            }
        ],
    }
    identity = pipeline._classify_device_identity(
        "CE TF Enteral Feeding Pump Link",
        "The enteral feeding pump is intended to deliver enteral nutrition through powered flow control.",
        "feeding pump flow delivery motor battery alarm powered equipment incidental stent comparison",
        state,
    )
    arbitration = pipeline._arbitrate_device_identity_domain(
        state,
        pipeline._initial_domain_hint(state, state["target_keywords"]),
        identity,
        intended_purpose="The enteral feeding pump is intended to deliver enteral nutrition through powered flow control.",
        fallback_name="CE TF Enteral Feeding Pump Link",
    )

    assert pipeline._initial_domain_hint(state, state["target_keywords"]) == "powered_therapeutic_equipment"
    assert identity["clinical_domain"] == "powered_therapeutic_equipment"
    assert arbitration["selected_domain"] == "powered_therapeutic_equipment"
    assert arbitration["arbitration_status"] == "PASS"
    assert arbitration["selected_evidence_source"] == "locked_domain_hint"


def test_phase0_8_existing_identity_regressions_remain_stable():
    cases = [
        (
            "CAL-001 PADN RF Ablation Catheter IFU",
            "The catheter is intended for pulmonary artery denervation using radiofrequency ablation.",
            "radiofrequency ablation catheter PADN pulmonary artery denervation",
            "cardiovascular_rf_ablation_catheter",
        ),
        (
            "CAL-002 AI Diagnostic Software",
            "The software is intended to assist diagnosis.",
            "software algorithm analyses medical images to generate diagnostic output using AI",
            "ai_diagnostic_software",
        ),
        (
            "TF-TLC-0301_IFU-Ligating clips(Ti)",
            "The device is intended for ligating of tubular structures or vessels during surgery.",
            "ligating clips hemostatic clips vascular clips",
            "surgical_ligating_clip",
        ),
        (
            "Disposable Nerve Block Puncture Needle",
            "The device is used for puncture and injection of drugs during nerve block local anesthesia.",
            "clinical diagnosis puncture needle sterile disposable gauge stylet material",
            "nerve_block_needle",
        ),
    ]
    for name, intended, source, expected_domain in cases:
        identity = pipeline._classify_device_identity(
            name,
            intended,
            source,
            {"source_inventory": [{"source_id": "SRC-IFU", "document_type": "IFU", "source_role": "subject_device_ifu"}]},
        )
        assert identity["clinical_domain"] == expected_domain


def test_phase0_4_unclear_input_does_not_default_to_stent():
    identity = pipeline._classify_device_identity(
        "Device Manual",
        "The device is intended for clinical use.",
        "general instructions without device family or clinical domain",
        {"source_inventory": [{"source_id": "SRC-IFU-004", "document_type": "IFU", "source_role": "subject_device_ifu"}]},
    )

    assert identity["device_type"] == "UNKNOWN_WITH_CANDIDATES"
    assert identity["clinical_domain"] == "generic_unknown"
    assert identity["device_type"] != "stent"
    assert "stent fallback is prohibited" in identity["uncertainty_reason"]


def test_phase0_4_locked_final_sources_do_not_participate_in_device_identity():
    state = {
        "source_inventory": [
            {
                "source_id": "SRC-INITIAL-IFU",
                "document_type": "IFU",
                "source_role": "subject_device_ifu",
                "filename": "Instructions for Use.docx",
                "text": "General instructions without device type.",
            },
            {
                "source_id": "SRC-LOCKED-FINAL",
                "document_type": "locked_delta_only",
                "source_role": "locked_delta_only",
                "filename": "FINAL_IFU_stent.docx",
                "text": "stent urinary tract renal pelvis pyeloplasty",
                "excluded_from_device_profile": True,
            },
        ]
    }
    basis = pipeline._identity_source_basis_text(state, "General instructions without device type.")
    identity = pipeline._classify_device_identity("Device Manual", "", basis, state)

    assert "stent urinary tract" not in basis
    assert identity["device_type"] == "UNKNOWN_WITH_CANDIDATES"
    assert identity["supporting_source_ids"] == ["SRC-INITIAL-IFU"]


def test_phase0_4_ligating_clip_domain_mismatch_flag():
    report = pipeline._domain_contamination_report(
        {
            "device_identity_lock": {"locked_domain": "surgical_ligating_clip"},
            "device_profile": {
                "device_type": "ligating clip",
                "intended_purpose": "ligating of tubular structures or vessels",
                "anatomical_site": "urinary tract renal pelvis",
            },
            "cer_chapter_drafts": {"3 State of the Art": "pyeloplasty stent ureteroscope urinary tract"},
            "sota_benchmark_matrix": [{"benchmark_id": "BM-WRONG", "endpoint": "ureteral stent migration"}],
            "evidence_registry": [{"evidence_id": "E-WRONG", "endpoint": "pyeloplasty urinary tract stent"}],
        }
    )

    assert report["domain_mismatch_flag"] is True
    assert report["flag_code"] == "DOMAIN_MISMATCH_FLAG"
    assert any(item["token"] in {"stent", "urinary tract", "renal pelvis", "pyeloplasty", "ureteroscope"} for item in report["findings"])


def test_phase0_5_cal002_ai_diagnostic_software_multi_source_identity_lock():
    state = {
        "project_id": "CAL-002",
        "target_keywords": ["AI diagnostic software"],
        "source_inventory": [
            {
                "source_id": "SRC-IFU-002",
                "document_type": "IFU",
                "source_role": "subject_device_ifu",
                "filename": "CAL-002_AI_Diagnostic_Software_IFU.docx",
                "path": "/tmp/CAL-002/01_IFU/CAL-002_AI_Diagnostic_Software_IFU.docx",
                "text": "Instructions for Use. The software algorithm analyses medical images to assist diagnosis and clinical decision support.",
                "primary_for_authoring": True,
                "excluded_from_device_profile": False,
            },
            {
                "source_id": "SRC-GSPR-002",
                "document_type": "GSPR",
                "source_role": "manufacturer_source",
                "filename": "CAL-002_GSPR_Checklist.xlsx",
                "path": "/tmp/CAL-002/02_GSPR/CAL-002_GSPR_Checklist.xlsx",
                "text": "The subject device is software as a medical device. It uses artificial intelligence and an algorithm for diagnostic support.",
                "excluded_from_device_profile": False,
            },
            {
                "source_id": "SRC-META-002",
                "document_type": "metadata",
                "source_role": "manufacturer_source",
                "filename": "device_metadata.json",
                "path": "/tmp/CAL-002/device_metadata.json",
                "text": "Device family: SaMD. Device type: AI diagnostic software. Clinical domain: diagnosis.",
                "doc_proc_metadata": {"device_family": "SaMD", "keywords": ["AI", "diagnostic software", "algorithm"]},
                "excluded_from_device_profile": False,
            },
            {
                "source_id": "SRC-LOCKED-FINAL",
                "document_type": "locked_delta_only",
                "source_role": "locked_delta_only",
                "filename": "FINAL_IFU_stent.docx",
                "path": "/tmp/CAL-002/03_FINAL_CERTIFIED_PACKAGE_LOCKED/FINAL_IFU_stent.docx",
                "text": "stent urinary tract renal pelvis pyeloplasty",
                "excluded_from_device_profile": True,
            },
        ],
    }

    basis = pipeline._identity_source_basis_text(state, state["source_inventory"][0]["text"])
    identity = pipeline._classify_device_identity("CAL-002 AI Diagnostic Software", "The software is intended to assist diagnosis.", basis, state)

    assert "stent urinary tract" not in basis
    assert "GSPR" in basis
    assert "SaMD" in basis
    assert identity["device_type"] == "AI diagnostic software"
    assert identity["device_family"] == "software as a medical device"
    assert identity["clinical_domain"] == "ai_diagnostic_software"
    assert identity["classification_confidence"] == "high"
    assert identity["device_type"] != "stent"
    assert set(identity["supporting_source_ids"]) >= {"SRC-IFU-002", "SRC-GSPR-002", "SRC-META-002"}
    assert "locked_delta_only" not in identity["supporting_source_types"]
    assert {span["source_id"] for span in identity["evidence_spans"]} & {"SRC-IFU-002", "SRC-GSPR-002", "SRC-META-002"}


def test_phase0_5_general_samd_not_default_stent():
    identity = pipeline._classify_device_identity(
        "Clinical Decision Support Software IFU",
        "The software medical device is intended to support clinical monitoring and decision support.",
        "medical device software SaMD clinical decision support software monitoring patient workflow",
        {"source_inventory": [{"source_id": "SRC-IFU-SAMD", "document_type": "IFU", "source_role": "subject_device_ifu"}]},
    )

    assert identity["device_type"] == "software medical device"
    assert identity["device_family"] == "software as a medical device"
    assert identity["clinical_domain"] == "software_medical_device"
    assert identity["device_type"] != "stent"


def test_phase0_5_samd_domain_mismatch_flag():
    report = pipeline._domain_contamination_report(
        {
            "device_identity_lock": {"locked_domain": "ai_diagnostic_software"},
            "device_profile": {
                "device_type": "AI diagnostic software",
                "intended_purpose": "software algorithm for diagnosis",
                "anatomical_site": "software-only diagnostic data context",
            },
            "cer_chapter_drafts": {"3 State of the Art": "urinary tract stent migration and renal pelvis complications"},
            "sota_benchmark_matrix": [{"benchmark_id": "BM-WRONG", "endpoint": "ureteral stent migration"}],
        }
    )

    assert report["domain_mismatch_flag"] is True
    assert report["flag_code"] == "DOMAIN_MISMATCH_FLAG"
    assert any(item["token"] in {"stent", "urinary tract", "renal pelvis"} for item in report["findings"])


def test_g1e_context_aware_token_matching_allows_dr_and_surgical_context_mentions():
    cal002 = _passing_state()
    cal002["device_identity_lock"] = {"status": "PASS", "locked_domain": "ai_diagnostic_software", "identity_statement": "AI diagnostic software identity locked."}
    cal002["device_profile"] = {
        "device_name": "AI Diagnostic Software",
        "device_type": "AI diagnostic software",
        "intended_purpose": "Assist diagnosis from medical images.",
        "target_population": "adult patients",
        "mode_of_action": "Software algorithm",
        "clinical_domain": "ai_diagnostic_software",
    }
    cal002["domain_contamination_report"] = {
        "locked_domain": "ai_diagnostic_software",
        "findings": [{"scope": "dr_comparison", "token": "stent", "severity": "HIGH"}],
    }

    cal003 = _passing_state()
    cal003["device_identity_lock"] = {"status": "PASS", "locked_domain": "surgical_ligating_clip", "identity_statement": "Surgical ligating clip identity locked."}
    cal003["device_profile"] = {
        "device_name": "Ligating Clip",
        "device_type": "ligating clip",
        "intended_purpose": "Ligating of tubular structures or vessels.",
        "target_population": "patients requiring surgical ligation",
        "mode_of_action": "Mechanical ligation",
        "clinical_domain": "surgical_ligating_clip",
    }
    cal003["domain_contamination_report"] = {
        "locked_domain": "surgical_ligating_clip",
        "findings": [
            {"scope": "surgical_context", "token": "stent", "severity": "HIGH"},
            {"scope": "surgical_context", "token": "urinary tract", "severity": "HIGH"},
        ],
    }

    for state in (cal002, cal003):
        report = run_authoring_gates(state)
        g1e = next(row for row in report["results"] if row["gate_id"] == "G1e")
        assert g1e["status"] == "PASS"


def test_g1e_still_blocks_device_identity_token_contamination():
    state = _passing_state()
    state["device_identity_lock"] = {"status": "PASS", "locked_domain": "ai_diagnostic_software", "identity_statement": "AI diagnostic software identity locked."}
    state["device_profile"] = {
        "device_name": "AI Diagnostic Software",
        "device_type": "stent",
        "intended_purpose": "Assist diagnosis from medical images.",
        "target_population": "adult patients",
        "mode_of_action": "Software algorithm",
        "clinical_domain": "ai_diagnostic_software",
    }
    state["domain_contamination_report"] = {
        "locked_domain": "ai_diagnostic_software",
        "findings": [{"scope": "device_profile", "token": "stent", "severity": "HIGH"}],
    }

    report = run_authoring_gates(state)
    g1e = next(row for row in report["results"] if row["gate_id"] == "G1e")

    assert g1e["status"] == "REWORK_REQUIRED"


def test_g1e_exempts_ureteroscope_in_core_comparator_context():
    state = _passing_state()
    state["device_identity_lock"] = {"status": "PASS", "locked_domain": "surgical_ligating_clip", "identity_statement": "Surgical ligating clip identity locked."}
    state["device_profile"] = {
        "device_name": "Ligating Clip",
        "device_type": "ligating clip",
        "intended_purpose": "Ligating of tubular structures or vessels.",
        "target_population": "patients requiring surgical ligation",
        "mode_of_action": "Mechanical ligation",
        "clinical_domain": "surgical_ligating_clip",
    }
    state["cer_chapter_drafts"] = {
        "1 Summary": "Unlike ureteroscope surgery, the subject device is a ligating clip used for mechanical vessel ligation.",
        "2 Scope of Clinical Evaluation": "The ureteroscope procedure is discussed only as comparator clinical context and is not the subject device.",
    }
    state["domain_contamination_report"] = {
        "locked_domain": "surgical_ligating_clip",
        "findings": [{"scope": "profile_or_core_chapters", "token": "ureteroscope", "severity": "HIGH"}],
    }

    report = run_authoring_gates(state)
    g1e = next(row for row in report["results"] if row["gate_id"] == "G1e")

    assert g1e["status"] == "PASS"


def test_phase2_1_extract_endpoints_generates_missing_sota_derivation_tables():
    state = {
        "device_profile": {"target_population": "adult patients requiring IFU-defined treatment"},
        "claim_ledger": [{"claim_id": "C-01", "claim_text": "The device supports clinical performance."}],
        "cep_pico_matrix": [{"pico_id": "PICO-01", "claim_id": "C-01", "outcome": "clinical success"}],
        "search_run_registry": [{"search_id": "SEARCH-SOTA-01", "database": "PubMed", "objective": "SOTA"}],
        "evidence_registry": [
            {
                "evidence_id": "E-001",
                "article_id": "ART-001",
                "source": "PMID 123456",
                "evidence_type": "systematic review and meta-analysis",
                "population": "adult patients",
                "sample_size": "250",
                "follow_up": "6 months",
                "result": "clinical success 92% (95% CI 88% to 95%)",
                "weight": "pivotal",
            }
        ],
        "endpoint_extraction": [
            {
                "endpoint_id": "EP-OLD-001",
                "benchmark_id": "BM-01",
                "source_evidence_id": "E-001",
                "endpoint": "clinical success",
                "sample_size": "250",
                "timepoint": "6 months",
                "statistical_result": "92% (95% CI 88% to 95%)",
                "full_text_page_or_section": "page 5 table 2",
                "extraction_basis": "user-provided full text page/table-level endpoint extraction",
            }
        ],
        "sota_benchmark_matrix": [
            {
                "benchmark_id": "BM-01",
                "endpoint": "clinical success",
                "clinical_significance": "Primary performance benchmark",
                "sota_source": "SEARCH-SOTA-01",
                "sota_value_range": "92% (95% CI 88% to 95%)",
                "acceptance_criterion": "Consistent with accepted SOTA range",
                "corresponding_claim_id": "C-01",
                "used_in_4_7": True,
            }
        ],
    }

    update = pipeline.extract_endpoints(state)

    assert update["endpoint_registry"][0]["endpoint_id"] == "END-001"
    derivation = update["sota_endpoint_derivation_table"][0]
    for field in ("benchmark_value", "source", "population", "sample_size", "CI_or_range"):
        assert derivation[field]
    assert derivation["source_hierarchy_level"] == "aggregate"
    assert derivation["source_hierarchy_rank"] == 1
    assert update["sota_quantitative_benchmark_table"][0]["benchmark_value"] == derivation["benchmark_value"]
    assert update["sota_claim_reverse_correction_table"][0]["claim_id"] == "C-01"
    assert update["claim_ledger"][0]["sota_reverse_correction"] == "keep_with_sota_limits"


def test_phase2_1_source_hierarchy_does_not_default_to_missing_benchmark_fields():
    state = {
        "device_profile": {"target_population": "IFU-defined population"},
        "claim_ledger": [{"claim_id": "C-02", "claim_text": "The device has acceptable safety."}],
        "cep_pico_matrix": [{"pico_id": "PICO-02", "claim_id": "C-02", "outcome": "serious adverse events"}],
        "search_run_registry": [{"search_id": "SEARCH-SOTA-02", "database": "Registry", "objective": "SOTA"}],
        "evidence_registry": [
            {
                "evidence_id": "E-REG-001",
                "article_id": "ART-REG-001",
                "source": "Registry report",
                "evidence_type": "registry real-world data",
                "sample_size": "not extracted",
                "follow_up": "not extracted",
                "result": "adverse event rate not quantified in summary",
                "weight": "supportive",
            }
        ],
        "sota_benchmark_matrix": [
            {
                "benchmark_id": "BM-02",
                "endpoint": "serious adverse events",
                "clinical_significance": "Safety benchmark",
                "sota_source": "SEARCH-SOTA-02",
                "sota_value_range": "Rates to be extracted from registry data.",
                "acceptance_criterion": "Within accepted SOTA after RMF/IFU controls",
                "corresponding_claim_id": "C-02",
                "used_in_4_7": True,
            }
        ],
    }

    update = pipeline.extract_endpoints(state)
    row = update["sota_endpoint_derivation_table"][0]

    assert row["benchmark_value"]
    assert row["source"]
    assert row["population"]
    assert row["sample_size"] == "not reported in source"
    assert row["CI_or_range"]
    assert row["source_hierarchy_level"] == "registry"
    assert update["claim_ledger"][0]["sota_reverse_correction"] == "qualify"


def test_phase2_1_workbook_and_export_include_endpoint_registry_and_claim_correction(tmp_path):
    state = _passing_state()
    state.update(pipeline.extract_endpoints(state))

    workbook = build_authoring_workbook(state)

    assert workbook["endpoint_registry"]
    assert workbook["sota_claim_reverse_correction_table"]
    written = write_authoring_artifacts(tmp_path, state)
    written_names = {path.rsplit("/", 1)[-1] for path in written}
    assert "endpoint_registry.xlsx" in written_names
    assert "sota_claim_reverse_correction_table.xlsx" in written_names


def test_phase2_3_writer_builds_claim_evidence_benefit_risk_ledgers_and_g38_passes():
    state = _passing_state()
    state.pop("cer_chapter_drafts")

    update = pipeline.write_cer_chapters(state)
    merged = {**state, **update}

    assert merged["claim_evidence_matrix"]
    assert merged["benefit_risk_ledger"]
    assert merged["writer_conclusion_strength_guard"]
    assert merged["cer_section_trace_map"]
    draft = "\n".join(merged["cer_chapter_drafts"].values()).lower()
    for prohibited in ("superior", "proven better", "definitively", "fully demonstrated", "all risks are acceptable"):
        assert prohibited not in draft

    report = run_authoring_gates(merged)
    g38 = next(row for row in report["results"] if row["gate_id"] == "G38")
    assert g38["status"] == "PASS"


def test_phase2_3_weak_evidence_claim_is_limited_before_writer():
    state = {
        "claim_ledger": [{"claim_id": "C-01", "claim_type": "performance", "claim_text": "The device achieves the intended performance."}],
        "cep_pico_matrix": [{"pico_id": "PICO-01", "claim_id": "C-01", "outcome": "clinical success"}],
        "evidence_registry": [{"evidence_id": "E-GAP-001", "weight": "background", "result": "Evidence gap", "evidence_level": "not graded"}],
        "sota_benchmark_matrix": [{"benchmark_id": "BM-01", "endpoint": "clinical success", "corresponding_claim_id": "C-01", "used_in_4_7": True}],
        "sota_endpoint_derivation_table": [],
        "risk_trace_matrix": [{"risk_id": "R-001", "ifu_coverage": "gap", "rmf_coverage": "gap"}],
        "gap_pmcf_recommendations": [{"gap_id": "GAP-001", "gap": "Missing clinical endpoint data", "pmcf_measure": "PMCF endpoint collection"}],
    }

    update = pipeline.build_claim_evidence_benefit_risk_ledgers(state)

    matrix = update["claim_evidence_matrix"][0]
    guard = update["writer_conclusion_strength_guard"][1]
    benefit = update["benefit_risk_ledger"][0]
    assert matrix["support_status"] == "evidence_gap"
    assert matrix["conclusion_strength"] == "limited"
    assert "evidence gap" in guard["reason"]
    assert "not sufficiently supported" in benefit["overall_judgment"]
    assert "superior" not in " ".join(str(row.get("prohibited_language")) for row in update["writer_conclusion_strength_guard"]).lower()


def test_phase2_3_workbook_and_export_include_benefit_risk_ledgers(tmp_path):
    state = _passing_state()
    state.update(pipeline.build_claim_evidence_benefit_risk_ledgers(state))

    workbook = build_authoring_workbook(state)

    assert workbook["claim_evidence_matrix"]
    assert workbook["benefit_risk_ledger"]
    assert workbook["writer_conclusion_strength_guard"]
    assert workbook["cer_section_trace_map"]
    written = write_authoring_artifacts(tmp_path, state)
    written_names = {path.rsplit("/", 1)[-1] for path in written}
    assert "claim_evidence_matrix.xlsx" in written_names
    assert "benefit_risk_ledger.xlsx" in written_names
    assert "writer_conclusion_strength_guard.xlsx" in written_names
    assert "cer_section_trace_map.xlsx" in written_names


def test_phase4_1_cross_evidence_synthesis_aggregates_by_claim_before_writer():
    state = _passing_state()
    state.pop("cer_chapter_drafts")
    state["evidence_registry"] = [
        {
            "evidence_id": "E-001",
            "weight": "pivotal",
            "evidence_level": "level 1",
            "sample_size": "100",
            "follow_up": "30 days",
            "endpoint": "clinical success",
            "result": "95%",
            "limitations": "single endpoint definition requires verification",
        },
        {
            "evidence_id": "E-002",
            "weight": "supportive-quantitative",
            "evidence_level": "level 3",
            "sample_size": "80",
            "follow_up": "90 days",
            "endpoint": "clinical success",
            "result": "92%",
            "limitations": "supportive cohort",
        },
    ]
    state["sota_endpoint_derivation_table"] = [
        {
            "row_id": "SOTA-DER-001",
            "evidence_id": "E-001",
            "endpoint_id": "END-001",
            "benchmark_id": "B-001",
            "sample_size": "100",
            "timepoint": "30 days",
            "statistical_result": "95%",
            "benchmark_value": "95%",
            "limitation": "full-text verified",
        },
        {
            "row_id": "SOTA-DER-002",
            "evidence_id": "E-002",
            "endpoint_id": "END-001",
            "benchmark_id": "B-001",
            "sample_size": "80",
            "timepoint": "90 days",
            "statistical_result": "92%",
            "benchmark_value": "92%",
            "limitation": "supportive endpoint",
        },
    ]
    state["claim_evidence_matrix"] = [
        {
            "matrix_id": "CEM-001",
            "claim_id": "C-01",
            "claim_text": "fixture claim",
            "endpoint_ids": "END-001",
            "sota_ids": "B-001",
            "evidence_ids": "E-001, E-002",
            "evidence_strength": "moderate",
            "support_status": "partially_supported",
            "conclusion_strength": "cautious",
        }
    ]

    update = pipeline.build_cross_evidence_synthesis(state)
    row = update["cross_evidence_synthesis_table"][0]

    assert row["evidence_count"] == 2
    assert row["pivotal_evidence_ids"] == "E-001"
    assert row["supportive_evidence_ids"] == "E-002"
    assert "95%" in row["result_synthesis"]
    assert "92%" in row["result_synthesis"]
    assert update["writer_synthesis_trace"][0]["stage"] == "writer_synthesis"


def test_phase4_1_writer_consumes_cross_evidence_synthesis_in_section_4():
    state = _passing_state()
    state.pop("cer_chapter_drafts")

    update = pipeline.write_cer_chapters(state)
    section_4 = update["cer_chapter_drafts"]["4 Device Under Evaluation"]

    assert update["cross_evidence_synthesis_table"]
    assert "Cross-evidence synthesis is performed before the article-level appraisal table" in section_4
    assert "Cross-Evidence Synthesis Table" in section_4
    assert "This prevents section 4 from becoming a sequence of article summaries" in section_4


def test_phase4_1_workbook_and_export_include_cross_evidence_synthesis(tmp_path):
    state = _passing_state()
    state.update(pipeline.build_cross_evidence_synthesis(state))

    workbook = build_authoring_workbook(state)

    assert workbook["cross_evidence_synthesis_table"]
    assert workbook["cross_evidence_synthesis_narratives"]
    assert workbook["writer_synthesis_trace"]
    written = write_authoring_artifacts(tmp_path, state)
    written_names = {path.rsplit("/", 1)[-1] for path in written}
    assert "cross_evidence_synthesis_table.xlsx" in written_names
    assert "cross_evidence_synthesis_narratives.xlsx" in written_names
    assert "writer_synthesis_trace.xlsx" in written_names


def test_phase4_2_writer_prompt_requires_prewrite_ifu_claim_extraction():
    configs = build_authoring_subagent_configs()
    stable_prompt = configs["authoring-cer-writer-agent"].system_prompt
    virtual_prompt = configs["authoring-cer-writer"].system_prompt

    for prompt in (stable_prompt, virtual_prompt):
        assert "pre-write IFU full-text claim coverage check" in prompt
        assert "Claim Ledger" in prompt
        assert "missing_claim_candidates" in prompt
        assert "rework_targets" in prompt


def test_batch_4_1_agent_prompts_include_optional_insufficiency_signals():
    configs = build_authoring_subagent_configs()

    methodology_prompt = configs["authoring-methodology-sota-agent"].system_prompt
    evidence_prompt = configs["authoring-evidence-agent"].system_prompt
    risk_prompt = configs["authoring-risk-equivalence-gspr-agent"].system_prompt
    writer_prompt = configs["authoring-cer-writer-agent"].system_prompt

    assert "insufficiency.recall_sufficiency" in methodology_prompt
    assert "insufficiency.benchmark_derivable" in methodology_prompt
    assert "insufficiency.fulltext_basis_adequate" in evidence_prompt
    assert "insufficiency.br_justifiable" in risk_prompt
    assert "insufficiency.br_justifiable" in writer_prompt
    assert "return structured REWORK_REQUIRED or BLOCKED" in methodology_prompt
    assert "Return one compact JSON object" in writer_prompt and "optional insufficiency" in writer_prompt


def test_batch_4_2_writer_prompt_requires_gate_passed_ledger_consumption():
    configs = build_authoring_subagent_configs()
    prompt = configs["authoring-cer-writer-agent"].system_prompt

    assert "writer_invocation_allowed" in prompt
    assert "pre_writer_readiness_gate" in prompt
    assert "gate-passed ledgers" in prompt
    assert "background-only evidence" in prompt


def test_batch_4_2_writer_blocks_when_pre_writer_readiness_not_passed():
    state = _passing_state()
    state["pre_writer_readiness_report"] = {"gate_id": "G46", "status": "REWORK_REQUIRED", "next_node": "sota_search"}

    update = pipeline.write_cer_chapters(state)

    assert update["writer_invocation_allowed"] is False
    assert update["writer_invocation_guard"]["pre_writer_gate_status"] == "REWORK_REQUIRED"
    assert "cer_chapter_drafts" not in update
    assert update["stage_results"][0]["status"] == "blocked_pre_writer_readiness"


def test_batch_4_2_writer_pass_path_records_allowed_gate_passed_ledgers():
    state = _passing_state()
    state.pop("cer_chapter_drafts", None)
    state["pre_writer_readiness_report"] = {"gate_id": "G46", "status": "PASS"}
    state["claim_evidence_gate_report"] = {"gate_id": "G43", "status": "PASS"}
    state["br_justified_gate_report"] = {"gate_id": "G44", "status": "PASS"}
    state["alignment_gate_report"] = {"gate_id": "G45", "status": "PASS"}

    update = pipeline.write_cer_chapters(state)

    assert update["writer_invocation_allowed"] is True
    assert all(row["consumption_allowed"] for row in update["writer_invocation_guard"]["allowed_ledgers"])
    assert "cer_chapter_drafts" in update


def test_phase4_2_writer_summary_includes_subject_ifu_claim_audit_context():
    state = _passing_state()
    state["source_inventory"][0]["text"] = """
    Instructions for Use
    Intended Use
    The device is intended to provide access and procedure support.
    Clinical benefits
    The device supports completion of the indicated procedure.
    Warnings
    Do not use when the patient anatomy is incompatible.
    Adverse events
    Potential adverse events include mucosal trauma and bleeding.
    """
    state["source_inventory"].append(
        {
            "source_id": "SRC-FINAL-IFU-LOCKED",
            "document_type": "IFU",
            "filename": "FINAL_IFU.docx",
            "source_role": "locked_delta_only",
            "primary_for_authoring": False,
            "excluded_from_device_profile": True,
            "text": "Clinical benefits Gold-only claim must not enter writer context.",
        }
    )

    summary = _state_summary(state, agent_name="authoring-cer-writer-agent")
    context = summary["subject_ifu_claim_audit_context"]

    assert context
    excerpt = context[0]["claim_bearing_excerpt"]
    assert "Intended Use" in excerpt
    assert "Clinical benefits" in excerpt
    assert "Warnings" in excerpt
    assert "Adverse events" in excerpt
    assert "Gold-only claim" not in str(context)
    assert "pre_write_claim_coverage_instruction" in summary


def test_phase4_3_sota_clinical_context_injected_before_benchmark_derivation():
    state = _passing_state()
    state.pop("sota_clinical_context_table", None)
    state.pop("sota_benchmark_contextual_rationale", None)
    state.pop("sota_endpoint_derivation_table", None)
    state["device_profile"]["device_domain"] = "urology_nephroscope"
    state["sota_benchmark_matrix"] = [
        {
            "benchmark_id": "B-001",
            "endpoint": "Successful endoscopic visualization and procedure support",
            "clinical_significance": "Claim-specific benchmark generated from PICO-01",
            "sota_source": "SEARCH-SOTA-01",
            "sota_value_range": "not quantitatively derived - full-text or aggregate source required",
            "acceptance_criterion": "clinically justified against SOTA",
            "corresponding_claim_id": "C-01",
            "used_in_4_7": True,
        }
    ]

    context_update = pipeline.inject_sota_clinical_context(state)
    enriched = {**state, **context_update}
    endpoint_update = pipeline.extract_endpoints(enriched)
    derivation = endpoint_update["sota_endpoint_derivation_table"][0]

    assert context_update["sota_clinical_context_table"]
    assert context_update["sota_benchmark_contextual_rationale"]
    assert "endourology" in context_update["sota_clinical_context_table"][0]["medical_field"]
    assert "endourology" in derivation["domain_aware_benchmark_rationale"]
    assert "visualization" in derivation["endpoint_selection_reason"].lower()
    assert "superiority" in derivation["overclaim_guard"].lower()


def test_phase4_3_workflow_exports_sota_clinical_context_artifacts(tmp_path):
    state = _passing_state()
    state.update(pipeline.inject_sota_clinical_context(state))

    workbook = build_authoring_workbook(state)

    assert workbook["sota_clinical_context_table"]
    assert workbook["sota_benchmark_contextual_rationale"]
    assert workbook["sota_context_injection_trace"]
    written = write_authoring_artifacts(tmp_path, state)
    written_names = {path.rsplit("/", 1)[-1] for path in written}
    assert "sota_clinical_context_table.xlsx" in written_names
    assert "sota_benchmark_contextual_rationale.xlsx" in written_names
    assert "sota_context_injection_trace.xlsx" in written_names


def test_phase4_4_writer_template_selector_cardiovascular_rf_sections():
    state = _passing_state()
    state["source_role_report"]["locked_domain_hint"] = "cardiovascular_rf_ablation_catheter"
    state["device_identity_lock"] = {
        **state["device_identity_lock"],
        "locked_domain": "cardiovascular_rf_ablation_catheter",
        "classification_confidence": "high",
    }
    state["device_profile"].update(
        {
            "device_type": "therapeutic RF ablation catheter",
            "device_family": "therapeutic catheter",
            "device_domain": "cardiovascular_rf_ablation_catheter",
            "clinical_domain": "cardiovascular_rf_ablation_catheter",
            "mode_of_action": "radiofrequency energy delivery using a compatible generator and ablation catheter",
            "intended_purpose": "cardiovascular RF ablation under IFU-defined procedural conditions",
        }
    )
    state.pop("cer_chapter_drafts", None)

    update = pipeline.write_cer_chapters(state)
    chapter = update["cer_chapter_drafts"]["4 Device Under Evaluation"]

    assert update["writer_device_template_profile"]["template_id"] == "modular_therapeutic_catheter_rf_ablation"
    assert update["writer_device_template_profile"]["device_family"] == "disposable"
    assert update["writer_device_template_profile"]["functional_profile"] == "therapeutic"
    assert "energy_delivery" in update["writer_device_template_profile"]["feature_modules"]
    assert "Energy Delivery and Lesion-Control Evidence" in chapter
    assert "Procedural Safety and Use-Environment Controls" in chapter
    assert "Generator-Catheter Compatibility" in chapter
    assert "feature_energy_delivery / Energy Delivery Parameters and Collateral Injury Controls" in chapter


def test_phase4_4_locked_cardiovascular_template_overrides_incidental_software_terms():
    state = _passing_state()
    state["source_role_report"]["locked_domain_hint"] = "cardiovascular_rf_ablation_catheter"
    state["device_identity_lock"] = {
        **state["device_identity_lock"],
        "locked_domain": "cardiovascular_rf_ablation_catheter",
        "classification_confidence": "high",
    }
    state["device_profile"].update(
        {
            "device_type": "radiofrequency ablation catheter",
            "device_family": "energy ablation catheter",
            "device_domain": "cardiovascular_rf_ablation_catheter",
            "clinical_domain": "cardiovascular_rf_ablation_catheter",
            "working_principle": "The generator contains software controls, but the clinical device is an RF ablation catheter.",
            "mode_of_action": "RF energy delivery through a compatible generator-catheter system",
            "intended_purpose": "treatment of adult pulmonary arterial hypertension by pulmonary artery RF ablation",
        }
    )

    update = pipeline.build_writer_device_template_profile(state)

    assert update["writer_device_template_profile"]["template_id"] == "modular_therapeutic_catheter_rf_ablation"


def test_phase4_4_writer_template_selector_software_sections():
    state = _passing_state()
    state["source_role_report"]["locked_domain_hint"] = "ai_diagnostic_software"
    state["device_identity_lock"] = {
        **state["device_identity_lock"],
        "locked_domain": "ai_diagnostic_software",
        "classification_confidence": "high",
    }
    state["device_profile"].update(
        {
            "device_type": "AI diagnostic software",
            "device_family": "software as a medical device",
            "device_domain": "ai_diagnostic_software",
            "clinical_domain": "ai_diagnostic_software",
            "mode_of_action": "software algorithm analyses clinical images and provides diagnostic decision support",
            "intended_purpose": "diagnostic decision support using an AI algorithm",
        }
    )
    state.pop("cer_chapter_drafts", None)

    update = pipeline.write_cer_chapters(state)
    chapter = update["cer_chapter_drafts"]["4 Device Under Evaluation"]

    assert update["writer_device_template_profile"]["template_id"] == "modular_software_medical_device"
    assert update["writer_device_template_profile"]["device_family"] == "SaMD"
    assert update["writer_device_template_profile"]["functional_profile"] == "diagnostic"
    assert "software_component" in update["writer_device_template_profile"]["feature_modules"]
    assert "Algorithm and Model Description" in chapter
    assert "Analytical and Clinical Validation" in chapter
    assert "Cybersecurity, Data Integrity and Software Lifecycle" in chapter


def test_phase4_4_writer_template_selector_ligating_clip_sections():
    state = _passing_state()
    state["source_role_report"]["locked_domain_hint"] = "surgical_ligating_clip"
    state["device_identity_lock"] = {
        **state["device_identity_lock"],
        "locked_domain": "surgical_ligating_clip",
        "classification_confidence": "high",
    }
    state["device_profile"].update(
        {
            "device_type": "surgical implant ligating clip",
            "device_family": "ligating clip",
            "device_domain": "surgical_ligating_clip",
            "clinical_domain": "surgical_ligating_clip",
            "composition": "titanium ligating clip material",
            "intended_purpose": "ligating of tubular structures or vessels during surgical procedures",
        }
    )
    state.pop("cer_chapter_drafts", None)

    update = pipeline.write_cer_chapters(state)
    chapter = update["cer_chapter_drafts"]["4 Device Under Evaluation"]

    assert update["writer_device_template_profile"]["template_id"] == "modular_surgical_implant_ligating_clip"
    assert update["writer_device_template_profile"]["device_family"] == "implantable"
    assert update["writer_device_template_profile"]["functional_profile"] == "therapeutic"
    assert "implantable" in update["writer_device_template_profile"]["feature_modules"]
    assert "Material, Implant Contact and Biocompatibility" in chapter
    assert "Sterilization, Packaging and Shelf-life" in chapter
    assert "Implantation, Ligation Security and Procedure-Specific Risks" in chapter


def test_phase4_4_writer_template_generic_only_when_identity_not_high():
    state = _passing_state()
    state["source_role_report"]["locked_domain_hint"] = "generic_unknown"
    state["device_identity_lock"] = {
        **state["device_identity_lock"],
        "locked_domain": "generic_unknown",
        "classification_confidence": "low",
    }
    state["device_profile"].update(
        {
            "device_type": "unconfirmed device",
            "device_family": "unconfirmed",
            "device_domain": "generic_unknown",
            "clinical_domain": "generic_unknown",
            "intended_purpose": "IFU-defined purpose requires confirmation",
        }
    )

    low_update = pipeline.build_writer_device_template_profile(state)
    assert low_update["writer_device_template_profile"]["template_id"] == "generic_medical_device"

    state["device_identity_lock"]["classification_confidence"] = "high"
    high_update = pipeline.build_writer_device_template_profile({**state, "writer_device_template_profile": {}, "writer_device_conditional_sections": []})
    assert high_update["writer_device_template_profile"]["template_id"] == "device_class_unmapped_requires_template_review"


def test_phase5d_writer_template_modular_powered_therapeutic_pump_sections():
    state = _passing_state()
    state["source_role_report"]["locked_domain_hint"] = "powered_therapeutic_equipment"
    state["device_identity_lock"] = {
        **state["device_identity_lock"],
        "locked_domain": "powered_therapeutic_equipment",
        "classification_confidence": "high",
    }
    state["device_profile"].update(
        {
            "device_type": "enteral feeding pump",
            "device_family": "powered equipment",
            "device_domain": "powered_therapeutic_equipment",
            "clinical_domain": "powered_therapeutic_equipment",
            "mode_of_action": "powered enteral nutrition delivery with alarms and software-controlled flow rate",
            "intended_purpose": "therapeutic enteral feeding and fluid delivery in intended patients",
            "working_principle": "electric powered pump with occlusion alarm, flow control and disposable feeding tubing",
        }
    )
    state.pop("cer_chapter_drafts", None)

    update = pipeline.write_cer_chapters(state)
    profile = update["writer_device_template_profile"]
    chapter = update["cer_chapter_drafts"]["4 Device Under Evaluation"]

    assert profile["template_id"] == "modular_powered_non_implantable_therapeutic_equipment"
    assert profile["device_family"] == "powered_equipment"
    assert profile["functional_profile"] == "therapeutic"
    assert "powered_device" in profile["feature_modules"]
    assert "fluid_delivery" in profile["feature_modules"]
    assert "alarmed_system" in profile["feature_modules"]
    assert "Powered Equipment Safety, Essential Performance and EMC" in chapter
    assert "Fluid Delivery Accuracy, Flow Path and Occlusion Controls" in chapter
    assert "Alarm System, Detectability and User Response" in chapter
    assert "Writer template selector: `generic_medical_device`" not in chapter
    assert "Selected by" in chapter


def test_phase4_5_pmcf_boundary_distinguishes_core_evidence_gap():
    state = _passing_state()
    state["evidence_registry"] = [
        {
            "evidence_id": "E-GAP-001",
            "weight": "background",
            "result": "Core clinical endpoint evidence gap; pivotal endpoint data are not available.",
            "evidence_level": "not graded",
        }
    ]

    update = pipeline.build_gap_pmcf_recommendations(state)
    decisions = update["pmcf_boundary_decision_log"]
    evidence_decision = next(row for row in decisions if row["gap_id"] == "GAP-EVIDENCE-001")

    assert evidence_decision["pre_submission_required"] == "required_before_nb_submission_for_signature_level_or_strong_claim"
    assert evidence_decision["pmcf_allowed"] == "allowed_only_for_residual_uncertainty_after_pre_submission_evidence_or_claim_downgrade"
    assert evidence_decision["claim_downgrade_required"] == "downgrade_to_partial_support_or_remove_claim_until_evidence_resolved"
    assert "cannot be the only basis" in evidence_decision["pmcf_allowed_rationale"]
    assert evidence_decision["claim_action"] == "downgrade_or_qualify_claim_and_record_pmcf_boundary"


def test_phase4_5_pmcf_boundary_blocks_rmf_gap_as_pmcf_substitute():
    state = _passing_state()
    update = pipeline.build_gap_pmcf_recommendations(state)
    rmf_decision = next(row for row in update["pmcf_boundary_decision_log"] if row["gap_id"] == "GAP-RMF-001")

    assert rmf_decision["pre_submission_required"] == "required_before_nb_submission_for_final_conformity_or_benefit_risk_claim"
    assert rmf_decision["pmcf_allowed"] == "not_allowed_as_primary_resolution"
    assert rmf_decision["claim_downgrade_required"] == "downgrade_or_hold_safety_benefit_risk_and_conformity_claims"
    assert rmf_decision["human_gate_required"] == "yes"


def test_phase4_5_claim_benefit_risk_ledger_consumes_pmcf_boundary():
    state = _passing_state()
    state["gap_pmcf_recommendations"] = [
        {
            "gap_id": "GAP-CORE-001",
            "gap": "Missing pivotal performance endpoint data for claimed clinical benefit.",
            "pmcf_measure": "PMCF endpoint collection",
        }
    ]

    update = pipeline.build_claim_evidence_benefit_risk_ledgers(state)
    matrix_row = update["claim_evidence_matrix"][0]
    br_row = update["benefit_risk_ledger"][0]

    assert "required_before_nb_submission_for_signature_level_or_strong_claim" in matrix_row["pre_submission_required"]
    assert "allowed_only_for_residual_uncertainty" in matrix_row["pmcf_allowed"]
    assert "downgrade_to_partial_support" in matrix_row["claim_downgrade_required"]
    assert "PMCF boundary" in br_row["rationale"]
    assert update["pmcf_boundary_decision_log"]


def test_phase4_5_pmcf_boundary_exports_to_workbook_and_artifacts(tmp_path):
    state = _passing_state()
    state.update(pipeline.build_gap_pmcf_recommendations(state))

    workbook = build_authoring_workbook(state)
    assert workbook["pmcf_boundary_decision_log"]

    written = write_authoring_artifacts(tmp_path, state)
    written_names = {Path(path).name for path in written}
    assert "pmcf_boundary_decision_log.xlsx" in written_names


def test_phase5_1_alignment_matrix_generates_document_pair_statuses():
    state = _passing_state()

    update = pipeline.build_claim_evidence_benefit_risk_ledgers(state)
    rows = update["alignment_matrix"]
    by_pair = {row["document_pair"]: row for row in rows}

    assert {"CER↔IFU", "CER↔RMF", "CER↔GSPR", "CER↔PMCF"}.issubset(by_pair)
    assert by_pair["CER↔IFU"]["alignment_status"] == "aligned"
    assert by_pair["CER↔RMF"]["alignment_status"] in {"partial", "missing"}
    assert by_pair["CER↔GSPR"]["alignment_status"] == "partial"
    assert by_pair["CER↔PMCF"]["alignment_status"] == "partial"
    assert "alignment_matrix" in update
    assert "alignment_ids" in update["claim_evidence_matrix"][0]


def test_phase5_1_alignment_conflict_downgrades_writer_conclusion_strength():
    state = _passing_state()
    state["claim_ledger"] = [
        {
            "claim_id": "C-01",
            "claim_type": "safety",
            "claim_text": "All residual risks are acceptable and fully controlled.",
        }
    ]
    state["alignment_matrix"] = [
        {
            "alignment_id": "ALIGN-001-02",
            "claim_id": "C-01",
            "document_pair": "CER↔RMF",
            "target_document": "RMF",
            "alignment_status": "conflict",
            "writer_instruction": "Flag for revision and downgrade wording.",
        }
    ]

    update = pipeline.build_claim_evidence_benefit_risk_ledgers(state)
    matrix_row = update["claim_evidence_matrix"][0]
    guard_row = update["writer_conclusion_strength_guard"][1]

    assert matrix_row["conclusion_strength"] == "not_allowed"
    assert "conflict" in matrix_row["alignment_status_summary"]
    assert "Alignment control" in matrix_row["writer_instruction"]
    assert "alignment" in guard_row["reason"].lower()


def test_phase5_1_writer_and_exports_consume_alignment_matrix(tmp_path):
    state = _passing_state()
    state.pop("cer_chapter_drafts")
    update = pipeline.write_cer_chapters(state)
    merged = {**state, **update}
    draft = "\n".join(merged["cer_chapter_drafts"].values())

    assert merged["alignment_matrix"]
    assert "CER/IFU/RMF/GSPR/PMCF Alignment Matrix" in draft
    assert "alignment_ids" in merged["cer_section_trace_map"][0]

    workbook = build_authoring_workbook(merged)
    assert workbook["alignment_matrix"]
    written = write_authoring_artifacts(tmp_path, merged)
    written_names = {Path(path).name for path in written}
    assert "alignment_matrix.xlsx" in written_names


def test_phase5_2_benefit_risk_ledger_adds_quantitative_depth_fields():
    state = _passing_state()
    state["risk_trace_matrix"] = [
        {
            "risk_id": "R-001",
            "severity": "serious",
            "occurrence_rate": "2%",
            "ifu_coverage": "covered by IFU warning",
            "rmf_coverage": "covered by RMR control",
        }
    ]
    state["gap_pmcf_recommendations"] = []
    state["pmcf_boundary_decision_log"] = []

    update = pipeline.build_claim_evidence_benefit_risk_ledgers(state)
    br_row = update["benefit_risk_ledger"][0]

    assert "95%" in br_row["magnitude_of_benefit"]
    assert "serious" in br_row["severity_of_risk"]
    assert "E-001" in br_row["benefit_evidence_basis"]
    assert "R-001" in br_row["risk_evidence_basis"]
    assert br_row["evidence_strength"]
    assert br_row["uncertainty_level"]
    assert br_row["benefit_risk_balance"]
    assert "Benefit magnitude" in br_row["balance_rationale"]


def test_phase5_2_material_uncertainty_exposes_conditional_br_and_downgrade():
    state = {
        "source_inventory": [{"source_id": "SRC-IFU-001", "document_type": "IFU", "filename": "IFU.docx", "primary_for_authoring": True}],
        "claim_ledger": [{"claim_id": "C-01", "claim_type": "performance", "claim_text": "The device provides clinical benefit."}],
        "cep_pico_matrix": [{"pico_id": "PICO-01", "claim_id": "C-01", "outcome": "clinical success"}],
        "evidence_registry": [{"evidence_id": "E-GAP-001", "weight": "background", "result": "Evidence gap", "evidence_level": "not graded"}],
        "sota_benchmark_matrix": [{"benchmark_id": "BM-01", "endpoint": "clinical success", "corresponding_claim_id": "C-01", "used_in_4_7": True}],
        "sota_endpoint_derivation_table": [],
        "risk_trace_matrix": [{"risk_id": "R-001", "severity": "serious", "ifu_coverage": "gap", "rmf_coverage": "gap"}],
        "gap_pmcf_recommendations": [{"gap_id": "GAP-001", "gap": "Missing clinical endpoint data", "pmcf_measure": "PMCF endpoint collection"}],
    }

    update = pipeline.build_claim_evidence_benefit_risk_ledgers(state)
    br_row = update["benefit_risk_ledger"][0]

    assert br_row["uncertainty_level"].startswith("high")
    assert "conditional" in br_row["benefit_risk_balance"] or "not_established" in br_row["benefit_risk_balance"]
    assert "PMCF boundary" in br_row["balance_rationale"]
    assert "downgrade" in str(br_row["claim_downgrade_required"])


def test_phase5_2_chapter5_consumes_enhanced_benefit_risk_ledger():
    state = _passing_state()
    state.pop("cer_chapter_drafts")
    update = pipeline.write_cer_chapters(state)
    conclusions = update["cer_chapter_drafts"]["5 Conclusions"]

    assert "Benefit-Risk Balance Used for Conclusions" in conclusions
    assert "Benefit magnitude" in conclusions
    assert "Risk severity" in conclusions
    assert "Uncertainty" in conclusions


def test_phase5c_disposable_physical_br_guard_generalizes_without_holdout_gold():
    state = _passing_state()
    state["device_identity_lock"] = {"status": "PASS", "locked_domain": "nerve_block_needle"}
    state["device_profile"] = {
        "device_name": "Disposable Nerve Block Puncture Needle",
        "device_type": "nerve block puncture needle",
        "device_family": "sterile disposable puncture needle",
        "intended_purpose": "Puncture and drug injection during nerve block local anesthesia.",
        "clinical_domain": "nerve_block_needle",
    }
    state["evidence_registry"] = [{"evidence_id": "E-001", "weight": "supportive", "evidence_level": "Level 4", "result": "supportive evidence"}]
    state["risk_trace_matrix"] = [
        {"risk_id": "R-001", "severity": "serious", "occurrence_rate": "not extracted", "ifu_coverage": "covered", "rmf_coverage": "covered"}
    ]

    update = pipeline.build_claim_evidence_benefit_risk_ledgers(state)
    br_row = update["benefit_risk_ledger"][0]
    guard_row = update["writer_conclusion_strength_guard"][0]

    assert br_row["device_class_taxonomy"] == "disposable_physical_device"
    assert "HOLD-002 is reserved as validation signal" in br_row["calibration_generalization_basis"]
    assert br_row["conclusion_guard_result"] in {
        "blocks_unqualified_br_conclusion",
        "requires_disposable_physical_controlled_conclusion",
        "requires_limited_or_gap_controlled_conclusion",
    }
    assert "supportive-only evidence" in br_row["not_allowed_wording"]
    assert guard_row["device_class_taxonomy"] == "disposable_physical_device"
    assert "MDR Annex I GSPR 1" in guard_row["regulatory_reasoning_basis"]


def test_phase5c_samd_and_implantable_br_policies_are_device_class_specific():
    samd = _passing_state()
    samd["device_identity_lock"] = {"status": "PASS", "locked_domain": "ai_diagnostic_software"}
    samd["device_profile"] = {"device_type": "AI diagnostic software", "device_family": "software as a medical device", "clinical_domain": "ai_diagnostic_software"}
    samd_update = pipeline.build_claim_evidence_benefit_risk_ledgers(samd)
    assert samd_update["benefit_risk_ledger"][0]["device_class_taxonomy"] == "samd_or_ai_diagnostic"
    assert "validation evidence" in samd_update["benefit_risk_ledger"][0]["device_class_br_policy"]

    implant = _passing_state()
    implant["device_identity_lock"] = {"status": "PASS", "locked_domain": "surgical_ligating_clip"}
    implant["device_profile"] = {"device_type": "ligating clip", "device_family": "surgical ligating clip", "clinical_domain": "surgical_ligating_clip"}
    implant_update = pipeline.build_claim_evidence_benefit_risk_ledgers(implant)
    assert implant_update["benefit_risk_ledger"][0]["device_class_taxonomy"] == "implantable_or_surgically_implanted_device"
    assert "material" in implant_update["benefit_risk_ledger"][0]["device_class_br_policy"].lower()


def test_phase5c_regulatory_language_sanitizer_prevents_g38_false_positive_terms():
    text = pipeline._sanitize_regulatory_language(
        "Superiority_claim_allowed appears in a table header and the article title mentions Superior thoracic segment. "
        "The conclusion is not fully demonstrated and should not be stated definitively."
    )

    lowered = text.lower()
    assert "superior" not in lowered
    assert "superiority" not in lowered
    assert "fully demonstrated" not in lowered
    assert "definitively" not in lowered


def test_phase2_5_existing_equivalence_generates_g33_attachment_index_without_mcp():
    state = {
        "device_profile": {"device_name": "Ligating Clips", "device_type": "ligating clip"},
        "equivalence_matrix": [
            {
                "comparison_id": "EQ-001",
                "comparison_type": "similar_device_context",
                "subject_device": "Ligating Clips",
                "comparator_device": "Comparable ligating clip",
                "difference_impact_conclusion": "Similar-device context only; equivalence not claimed.",
                "confidence": "not_claimed",
            }
        ],
    }

    update = pipeline.run_device_equivalence_search(state)
    merged = {**state, **update}

    assert len(update["similar_device_attachment_index"]) >= 10
    assert all(row.get("required_document") and row.get("use_in_cer") and row.get("if_missing") for row in update["similar_device_attachment_index"][:10])
    report = run_authoring_gates({**_passing_state(), **merged})
    g33 = next(row for row in report["results"] if row["gate_id"] == "G33")
    assert g33["status"] == "PASS"


def test_phase2_5_legacy_attachment_rows_are_hardened_to_g33_fields():
    rows = pipeline._similar_device_attachment_rows(
        {"device_profile": {"device_name": "Fixture Device"}},
        [],
        [{"comparison_id": "EQ-LEGACY-001"}],
        [
            {
                "row_id": "ATT-SIM-001",
                "attachment_type": "Legacy market source",
                "required_content": "Legacy EUDAMED screenshot",
                "purpose": "market_status",
            }
        ],
    )

    first = rows[0]
    assert first["attachment_id"] == "ATT-SIM-001"
    assert first["required_document"] == "Legacy EUDAMED screenshot"
    assert first["use_in_cer"]
    assert first["if_missing"]
    assert len(rows) == 10


def test_phase2_5_incomplete_attachment_index_is_not_treated_complete():
    assert pipeline._similar_device_attachment_index_complete(
        [{"attachment_id": f"ATT-SIM-{idx:03d}", "required_document": "doc"} for idx in range(1, 11)]
    ) is False


def test_device_identity_gate_blocks_pfa_contamination_in_nephroscope_profile():
    state = _passing_state()
    state["source_role_report"] = {
        "status": "PASS",
        "locked_domain_hint": "urology_nephroscope",
        "subject_ifu_source_ids": ["SRC-IFU-001"],
    }
    state["device_identity_lock"] = {
        "status": "REWORK_REQUIRED",
        "locked_domain": "urology_nephroscope",
        "subject_ifu_source_ids": ["SRC-IFU-001"],
        "conflicting_profile_fields": ["target_population", "anatomical_site"],
    }
    state["device_profile"] = {
        "device_name": "Pulsed Field Ablation System",
        "device_type": "pulsed field ablation system",
        "intended_purpose": "Cardiac ablation for atrial fibrillation",
        "target_population": "Patients requiring cardiac ablation",
        "anatomical_site": "cardiac / pulmonary vein anatomy",
        "mode_of_action": "Pulsed electric field ablation",
        "device_domain": "urology_nephroscope",
    }
    state["domain_contamination_report"] = {
        "locked_domain": "urology_nephroscope",
        "findings": [{"scope": "device_profile", "token": "pulsed field", "severity": "HIGH"}],
    }

    report = run_authoring_gates(state)

    failed = {item["gate_id"] for item in report["results"] if item["status"] != "PASS"}
    assert "G1d" in failed
    assert "G1e" in failed


def test_authoring_gates_block_chinese_text_in_final_cer_body():
    state = _passing_state()
    state["cer_chapter_drafts"]["1 Summary"] += " 中文残留"

    report = run_authoring_gates(state)

    failed = {item["gate_id"] for item in report["results"] if item["status"] != "PASS"}
    assert "G19" in failed


def test_authoring_graph_is_independent_and_exports_input_hold(tmp_path):
    graph = build_cer_authoring_graph()

    result = graph.invoke({"messages": [], "artifact_root": str(tmp_path), "source_inventory": []})

    assert result["final_gate_decision"] == "HUMAN_HOLD"
    assert (tmp_path / "authoring_workbook.json").exists()
    assert (tmp_path / "final_gate_closure_report.json").exists()


def test_authoring_graph_can_pass_complete_state(tmp_path):
    graph = build_cer_authoring_graph()
    state = _passing_state()
    state.update({"messages": [], "artifact_root": str(tmp_path)})

    result = graph.invoke(state)

    assert result["final_gate_decision"] == "PASS_TO_DRAFT_DOCX"
    assert (tmp_path / "CER_draft.md").exists()
    assert (tmp_path / "qa_gate_report.json").exists()


def test_phase0_calibration_contracts_are_in_workbook_and_export(tmp_path):
    state = _passing_state()
    state["authoring_baseline_version"] = "baseline-freeze-test"

    workbook = build_authoring_workbook(state)

    assert workbook["authoring_baseline_version"] == "baseline-freeze-test"
    assert workbook["calibration_case_schema"]["schema_name"] == "calibration_case_schema"
    assert workbook["authoring_baseline_freeze_manifest"]["core_authoring_workflow_frozen_during_formal_calibration"] is True
    assert "SOTA Agent logic change" in workbook["authoring_baseline_freeze_manifest"]["forbidden_between_formal_projects"]

    repair_map = {row["gate_id"]: row for row in workbook["gate_to_upstream_repair_map"]}
    assert {"G30", "G33", "G38"}.issubset(repair_map)
    assert repair_map["G30"]["upstream_stage"] == "endpoint_extraction / sota_search"
    assert repair_map["G33"]["required_artifact_to_fix"] == "similar_device_attachment_index"
    assert repair_map["G38"]["recheck_gates"] == "G12,G38"

    contract = {row["artifact_name"]: row for row in workbook["artifact_consumption_contract"]}
    assert contract["sota_benchmark_matrix"]["consumer"] == "extract_endpoints, write_cer_chapters, gates"
    assert contract["claude_repair/enhanced_authoring_workbook"]["consumption_status"] == "external_to_graph"

    written = write_authoring_artifacts(tmp_path, state)
    written_names = {path.rsplit("/", 1)[-1] for path in written}
    assert "calibration_case_schema.json" in written_names
    assert "authoring_baseline_freeze_manifest.json" in written_names
    assert "artifact_consumption_contract.xlsx" in written_names
    assert "failure_taxonomy_cer_authoring.xlsx" in written_names
    assert "cer_section_trace_map_schema.xlsx" in written_names
    assert "gate_to_upstream_repair_map.xlsx" in written_names


def test_phase6_writers_native_module_is_preloaded_before_agent_workers():
    status = preload_gil_safe_native_modules()

    assert status.get("pandas._libs.writers") == "loaded"


def _install_evidence_appraisal_mcp_stubs(monkeypatch, fetched_article: dict, abstract_record: dict | None = None):
    def fake_call_public(tool: str, payload: dict):
        if tool == "pubmed_fetch":
            return {"status": "ok", "articles": [fetched_article]}
        if tool == "pubmed_fetch_abstracts":
            return {"status": "ok", "articles": [abstract_record or fetched_article]}
        if tool == "pubmed_verify_citation":
            return {"status": "ok", "verified": True, "pmid": payload.get("pmid")}
        return {"status": "ok"}

    def fake_call_tool(server: str, tool: str, payload: dict, timeout: int = 90):
        return {"status": "ok", "cebm_level": "Level 2" if payload.get("randomized") else "Level 5"}

    monkeypatch.setattr(pipeline.mcp_tools, "call_public", fake_call_public)
    monkeypatch.setattr(pipeline.mcp_tools, "call_tool", fake_call_tool)
    monkeypatch.setattr(pipeline.mcp_tools, "mcp_log_entry", lambda result, name: {"tool": name, "status": result.get("status")})


def test_phase6_full_text_rct_appraisal_is_pivotal_with_oxford_level(monkeypatch):
    full_text = (
        "Methods: randomized controlled trial comparing ureteral access sheath procedures in adult patients. "
        "The study enrolled n=126 patients and used a controlled comparator. "
        "Results: clinical success was 94% (95% CI 88% to 98%) after 12 months follow-up. "
        "Adverse events and complications were recorded in the results table."
    )
    article = {"pmid": "12345678", "title": "Randomized controlled trial of ureteral access sheath performance", "full_text": full_text}
    _install_evidence_appraisal_mcp_stubs(monkeypatch, article)

    state = _passing_state()
    state.pop("evidence_registry", None)
    state.pop("article_appraisal", None)
    state["raw_literature_records"] = [{"pmid": "12345678", "title": article["title"], "full_text": full_text}]

    result = pipeline.appraise_evidence(state)

    evidence = result["evidence_registry"][0]
    appraisal = result["article_appraisal"][0]
    due_row = result["due_suitability_contribution_table"][0]
    assert evidence["weight"] == "pivotal"
    assert evidence["study_design"] == "Randomized controlled clinical trial"
    assert evidence["evidence_level"] == "Level 2"
    assert evidence["sample_size"] == "n=126"
    assert evidence["follow_up"] == "12 months"
    assert evidence["endpoint_match"] == "high"
    assert appraisal["full_text_status"] == "full_text_available"
    assert due_row["disposition"] == "accepted_pivotal"
    assert due_row["score"] == 12


def test_phase6_abstract_only_editorial_is_excluded_from_pivotal_use(monkeypatch):
    abstract = "Editorial comment on ureteral access sheath safety. No original patient cohort, endpoint table, or follow-up was reported."
    article = {"pmid": "87654321", "title": "Editorial comment on ureteral access sheath safety", "abstract": abstract}
    _install_evidence_appraisal_mcp_stubs(monkeypatch, article, {"pmid": "87654321", "abstract": abstract})

    state = _passing_state()
    state.pop("evidence_registry", None)
    state.pop("article_appraisal", None)
    state["raw_literature_records"] = [{"pmid": "87654321", "title": article["title"], "abstract": abstract}]

    result = pipeline.appraise_evidence(state)

    evidence = result["evidence_registry"][0]
    due_row = result["due_suitability_contribution_table"][0]
    assert evidence["study_design"] == "Editorial / letter / comment"
    assert evidence["evidence_level"] == "Level 5"
    assert evidence["weight"] == "excluded"
    assert evidence["conclusion_strength_allowed"] == "not_allowed_for_claim_support"
    assert due_row["disposition"] == "excluded"
    assert due_row["score"] == 35


def test_batch_5_5_pubmed_fetch_batches_all_eligible_pmids(monkeypatch):
    calls: list[tuple[str, list[str]]] = []

    def fake_call_public(tool: str, payload: dict):
        pmids = [str(pmid) for pmid in payload.get("pmids", [])]
        if tool in {"pubmed_fetch", "pubmed_fetch_abstracts"}:
            calls.append((tool, pmids))
        if tool == "pubmed_fetch":
            return {
                "status": "ok",
                "articles": [
                    {
                        "pmid": pmid,
                        "title": f"Randomized controlled trial {pmid}",
                        "full_text": f"Methods randomized controlled trial enrolled n=126 patients. Results success 94% after 12 months follow-up for endpoint {pmid}.",
                    }
                    for pmid in pmids
                ],
            }
        if tool == "pubmed_fetch_abstracts":
            return {
                "status": "ok",
                "articles": [
                    {
                        "pmid": pmid,
                        "abstract": f"Structured abstract for endpoint {pmid}: n=126, 12 months follow-up, success 94%.",
                    }
                    for pmid in pmids
                ],
            }
        if tool == "pubmed_verify_citation":
            return {"status": "ok", "verified": True, "pmid": payload.get("pmid")}
        return {"status": "ok"}

    monkeypatch.setattr(pipeline.mcp_tools, "call_public", fake_call_public)
    monkeypatch.setattr(pipeline.mcp_tools, "call_tool", lambda *args, **kwargs: {"status": "ok", "cebm_level": "Level 2"})
    monkeypatch.setattr(pipeline.mcp_tools, "mcp_log_entry", lambda result, name: {"tool": name, "status": result.get("status")})

    state = _passing_state()
    state.pop("evidence_registry", None)
    state.pop("article_appraisal", None)
    pmids = [str(10_000_000 + idx) for idx in range(25)]
    state["screening_disposition"] = [
        {
            "article_id": f"ART-{idx:03d}",
            "pmid": pmid,
            "full_text_decision": "include_for_appraisal",
            "retrieval_domain_status": "DOMAIN_MATCH_HIGH",
            "endpoint_match": "high",
        }
        for idx, pmid in enumerate(pmids, start=1)
    ]
    state["raw_literature_records"] = [
        {
            "article_id": f"ART-{idx:03d}",
            "pmid": pmid,
            "query_id": "Q-SOTA-001",
            "search_id": "SEARCH-SOTA-01",
            "retrieval_domain_status": "DOMAIN_MATCH_HIGH",
        }
        for idx, pmid in enumerate(pmids, start=1)
    ]

    result = pipeline.appraise_evidence(state)

    fetch_batches = [batch for tool, batch in calls if tool == "pubmed_fetch"]
    abstract_batches = [batch for tool, batch in calls if tool == "pubmed_fetch_abstracts"]
    assert [len(batch) for batch in fetch_batches] == [10, 10, 5]
    assert [len(batch) for batch in abstract_batches] == [10, 10, 5]
    assert len(result["evidence_registry"]) == 25
    assert len(result["article_appraisal"]) == 25
    assert result["evidence_funnel_counts"]["fetched_pubmed_article_count"] == 25
    assert result["evidence_funnel_counts"]["evidence_registry_count"] == 25
    assert result["evidence_funnel_counts"]["G42_input_evidence_count"] > 10


def test_batch_6_1_evidence_source_inventory_classifies_by_content_not_folder():
    state = {
        "source_inventory": [
            {
                "source_id": "SRC-RMF-001",
                "filename": "ambiguous_source.docx",
                "path": "/tmp/10_OTHER/ambiguous_source.docx",
                "document_type": "source",
                "text": "Risk management report according to ISO 14971 with hazard, residual risk and risk control traceability.",
            },
            {
                "source_id": "SRC-UNK-001",
                "filename": "miscellaneous_note.txt",
                "path": "/tmp/10_OTHER/miscellaneous_note.txt",
                "document_type": "source",
                "text": "Administrative note without evidence classification signals.",
            },
            {
                "source_id": "SRC-GSPR-001",
                "filename": "GSPR checklist.docx",
                "path": "/tmp/03_GSPR/GSPR checklist.docx",
                "document_type": "GSPR",
                "text": "General Safety and Performance Requirements Annex I checklist with benefit-risk and hazard traceability.",
            },
        ]
    }

    result = pipeline.prepare_source_inventory(state)
    rows = {row["source_id"]: row for row in result["evidence_source_inventory"]}

    assert rows["SRC-RMF-001"]["source_type"] == "subject_device_risk_management"
    assert rows["SRC-RMF-001"]["classification_confidence"] == "high"
    assert rows["SRC-GSPR-001"]["source_type"] == "subject_device_gspr"
    assert rows["SRC-UNK-001"]["source_type"] == "unknown_unclassified"
    assert rows["SRC-UNK-001"]["classification_basis"].startswith("content classification did not match")


def test_batch_6_1_appraise_evidence_adds_pubmed_source_anchor_fields(monkeypatch):
    def fake_call_public(tool: str, payload: dict):
        if tool == "pubmed_fetch":
            return {
                "status": "ok",
                "articles": [
                    {
                        "pmid": "12345678",
                        "title": "Randomized controlled trial for clinical success",
                        "full_text": "Methods randomized controlled trial enrolled n=126 patients. Results clinical success 94% after 12 months follow-up.",
                    }
                ],
            }
        if tool == "pubmed_fetch_abstracts":
            return {
                "status": "ok",
                "articles": [
                    {
                        "pmid": "12345678",
                        "abstract": "Structured abstract: n=126, 12 months follow-up, success 94%.",
                    }
                ],
            }
        if tool == "pubmed_verify_citation":
            return {"status": "ok", "verified": True, "pmid": payload.get("pmid")}
        return {"status": "ok"}

    monkeypatch.setattr(pipeline.mcp_tools, "call_public", fake_call_public)
    monkeypatch.setattr(pipeline.mcp_tools, "call_tool", lambda *args, **kwargs: {"status": "ok", "cebm_level": "Level 2"})
    monkeypatch.setattr(pipeline.mcp_tools, "mcp_log_entry", lambda result, name: {"tool": name, "status": result.get("status")})

    state = _passing_state()
    state.pop("evidence_registry", None)
    state.pop("article_appraisal", None)
    state["screening_disposition"] = [
        {
            "article_id": "ART-001",
            "pmid": "12345678",
            "full_text_decision": "include_for_appraisal",
            "retrieval_domain_status": "DOMAIN_MATCH_HIGH",
            "endpoint_match": "high",
            "search_id": "SEARCH-SOTA-01",
        }
    ]
    state["raw_literature_records"] = [
        {
            "article_id": "ART-001",
            "pmid": "12345678",
            "query_id": "Q-SOTA-001",
            "search_id": "SEARCH-SOTA-01",
            "retrieval_domain_status": "DOMAIN_MATCH_HIGH",
        }
    ]

    result = pipeline.appraise_evidence(state)
    evidence = result["evidence_registry"][0]
    trace = result["evidence_source_trace_matrix"][0]

    assert evidence["source_type"] == "literature_pubmed_sota"
    assert evidence["source_anchor"] == "PMID:12345678"
    assert evidence["source_provenance"] == "external_pubmed_mcp_retrieval"
    assert evidence["device_relationship"] == "similar"
    assert evidence["comparability_band"] in {"LOW", "MEDIUM", "HIGH"}
    assert evidence["weight"] in {"pivotal", "supportive", "background", "excluded"}
    assert trace["source_type"] == "literature_pubmed_sota"
    assert trace["source_anchor"] == "PMID:12345678"


def test_batch_6_1_existing_evidence_registry_is_anchored_without_role_change():
    state = {
        "evidence_registry": [
            {
                "evidence_id": "E-001",
                "pmid": "87654321",
                "weight": "supportive",
                "evidence_level": "Level 2",
            }
        ],
        "article_appraisal": [{"evidence_id": "E-001"}],
    }

    result = pipeline.appraise_evidence(state)
    evidence = result["evidence_registry"][0]

    assert evidence["source_type"] == "literature_pubmed_sota"
    assert evidence["source_anchor"] == "PMID:87654321"
    assert evidence["device_relationship"] == "similar"
    assert "clinical_benefit" not in evidence["allowed_claim_types"]
    assert evidence["weight"] == "supportive"
    assert evidence["evidence_level"] == "Level 2"


def test_batch_6_2_subject_device_sources_are_ingested_into_evidence_registry(monkeypatch):
    def fake_call_public(tool: str, payload: dict):
        if tool == "pubmed_fetch":
            return {
                "status": "ok",
                "articles": [
                    {
                        "pmid": "22334455",
                        "title": "Randomized controlled trial for clinical success",
                        "full_text": "Methods randomized controlled trial enrolled n=126 patients. Results clinical success 94% after 12 months follow-up.",
                    }
                ],
            }
        if tool == "pubmed_fetch_abstracts":
            return {"status": "ok", "articles": [{"pmid": "22334455", "abstract": "n=126; 12 months follow-up; success 94%."}]}
        if tool == "pubmed_verify_citation":
            return {"status": "ok", "verified": True, "pmid": payload.get("pmid")}
        return {"status": "ok"}

    monkeypatch.setattr(pipeline.mcp_tools, "call_public", fake_call_public)
    monkeypatch.setattr(pipeline.mcp_tools, "call_tool", lambda *args, **kwargs: {"status": "ok", "cebm_level": "Level 2"})
    monkeypatch.setattr(pipeline.mcp_tools, "mcp_log_entry", lambda result, name: {"tool": name, "status": result.get("status")})

    state = _passing_state()
    state.pop("evidence_registry", None)
    state.pop("article_appraisal", None)
    state["screening_disposition"] = [
        {
            "article_id": "ART-001",
            "pmid": "22334455",
            "full_text_decision": "include_for_appraisal",
            "retrieval_domain_status": "DOMAIN_MATCH_HIGH",
            "endpoint_match": "high",
            "search_id": "SEARCH-SOTA-01",
        }
    ]
    state["raw_literature_records"] = [
        {
            "article_id": "ART-001",
            "pmid": "22334455",
            "query_id": "Q-SOTA-001",
            "search_id": "SEARCH-SOTA-01",
            "retrieval_domain_status": "DOMAIN_MATCH_HIGH",
        }
    ]
    state["source_inventory"] = [
        {
            "source_id": "SRC-IFU-001",
            "filename": "Subject IFU.docx",
            "path": "/tmp/01_IFU/Subject IFU.docx",
            "document_type": "IFU",
            "source_role": "subject_device_ifu",
            "primary_for_authoring": True,
            "text": "Instructions for use. Intended use, warnings, contraindications and risk-control instructions.",
        },
        {
            "source_id": "SRC-TEST-001",
            "filename": "Performance verification report.docx",
            "path": "/tmp/06_PRECLINICAL/Performance verification report.docx",
            "document_type": "source",
            "source_role": "manufacturer_source",
            "text": "Performance test verification report. Acceptance criteria were predefined. Result: passed. Endpoint clinical success bench verification conforms.",
        },
        {
            "source_id": "SRC-MISC-001",
            "filename": "admin.txt",
            "path": "/tmp/10_OTHER/admin.txt",
            "document_type": "source",
            "source_role": "manufacturer_source",
            "text": "Administrative note with no evidence content.",
        },
    ]
    state["evidence_source_inventory"] = pipeline.prepare_source_inventory({"source_inventory": state["source_inventory"]})["evidence_source_inventory"]

    result = pipeline.appraise_evidence(state)
    source_types = {row["source_type"] for row in result["evidence_registry"]}
    subject_rows = [row for row in result["evidence_registry"] if row.get("source_provenance") == "subject_device_source_inventory_ingestion"]

    assert "literature_pubmed_sota" in source_types
    assert "subject_device_ifu" in source_types
    assert "subject_device_test_performance" in source_types
    assert "unknown_unclassified" not in {row["source_type"] for row in subject_rows}
    assert all(row["device_relationship"] == "subject" for row in subject_rows)
    assert all(row["source_anchor"] for row in subject_rows)
    assert all("/tmp/" not in str(row.get("source")) for row in subject_rows)
    assert all("Subject IFU.docx" not in str(row.get("title")) for row in subject_rows)
    assert any(row["weight"] == "supportive" for row in subject_rows if row["source_type"] == "subject_device_test_performance")


def test_batch_6_2_ifu_rmf_gspr_context_sources_do_not_get_role_uplift():
    state = _passing_state()
    state.pop("evidence_registry", None)
    state.pop("article_appraisal", None)
    state["screening_disposition"] = []
    state["raw_literature_records"] = []
    state["source_inventory"] = [
        {
            "source_id": "SRC-IFU-001",
            "filename": "Subject IFU.docx",
            "path": "/tmp/01_IFU/Subject IFU.docx",
            "document_type": "IFU",
            "source_role": "subject_device_ifu",
            "primary_for_authoring": True,
            "text": "Instructions for use with intended use, warnings, contraindications, sample size n=999 and result 99% stated as labeling text.",
        },
        {
            "source_id": "SRC-RMF-001",
            "filename": "Risk management report.docx",
            "path": "/tmp/02_RMF/Risk management report.docx",
            "document_type": "RMF",
            "source_role": "manufacturer_source",
            "text": "Risk management report ISO 14971 hazard residual risk risk control.",
        },
        {
            "source_id": "SRC-GSPR-001",
            "filename": "GSPR checklist.docx",
            "path": "/tmp/03_GSPR/GSPR checklist.docx",
            "document_type": "GSPR",
            "source_role": "manufacturer_source",
            "text": "General Safety and Performance Requirements Annex I checklist.",
        },
    ]
    state["evidence_source_inventory"] = pipeline.prepare_source_inventory({"source_inventory": state["source_inventory"]})["evidence_source_inventory"]

    result = pipeline.appraise_evidence(state)
    rows = {row["source_type"]: row for row in result["evidence_registry"]}

    for source_type in ("subject_device_ifu", "subject_device_risk_management", "subject_device_gspr"):
        assert rows[source_type]["weight"] == "background"
        assert rows[source_type]["ledger_approved_for_writer"] is False
        assert rows[source_type]["missing_data_flags"]
        assert rows[source_type]["device_relationship"] == "subject"


def test_batch_6_3_competitor_source_has_comparability_and_forbidden_claim_use():
    state = {
        "source_inventory": [
            {
                "source_id": "SRC-COMP-001",
                "filename": "LithoVue competitor IFU.pdf",
                "path": "/tmp/07_SIMILAR_COMPETITOR_DEVICES_OPTIONAL/LithoVue competitor IFU.pdf",
                "document_type": "IFU",
                "source_role": "similar_device_ifu",
                "text": "Boston Scientific LithoVue competitor device instructions for use. Intended use, procedure and clinical context are described.",
            }
        ]
    }

    result = pipeline.prepare_source_inventory(state)
    row = result["evidence_source_inventory"][0]

    assert row["device_relationship"] == "competitor"
    assert row["relationship_type"] == "competitor_device"
    assert row["comparability_score_raw"] >= 0
    assert row["comparability_score_normalized"] >= 0
    assert row["comparability_band"] in {"LOW", "MEDIUM", "HIGH"}
    assert row["allowed_claim_types"] == ["SOTA_benchmark"]
    assert "clinical_benefit" in row["forbidden_use"]


def test_batch_6_3_non_subject_sources_ingest_as_background_not_claim_support():
    state = _passing_state()
    state.pop("evidence_registry", None)
    state.pop("article_appraisal", None)
    state["screening_disposition"] = []
    state["raw_literature_records"] = []
    state["source_inventory"] = [
        {
            "source_id": "SRC-COMP-001",
            "filename": "LithoVue competitor IFU.pdf",
            "path": "/tmp/07_SIMILAR_COMPETITOR_DEVICES_OPTIONAL/LithoVue competitor IFU.pdf",
            "document_type": "IFU",
            "source_role": "similar_device_ifu",
            "text": "Boston Scientific LithoVue competitor device instructions for use. Intended use and clinical procedure context.",
        },
        {
            "source_id": "SRC-SIM-001",
            "filename": "Similar benchmark device report.docx",
            "path": "/tmp/07_SIMILAR_COMPETITOR_DEVICES_OPTIONAL/Similar benchmark device report.docx",
            "document_type": "source",
            "source_role": "similar_or_benchmark_source",
            "text": "Similar device comparator with intended use, technical specification, material contact and clinical procedure context.",
        },
    ]
    state["evidence_source_inventory"] = pipeline.prepare_source_inventory({"source_inventory": state["source_inventory"]})["evidence_source_inventory"]

    result = pipeline.appraise_evidence(state)
    rows = {row["source_id"]: row for row in result["evidence_registry"]}

    competitor = rows["SRC-COMP-001"]
    similar = rows["SRC-SIM-001"]
    assert competitor["device_relationship"] == "competitor"
    assert competitor["weight"] == "background"
    assert competitor["ledger_approved_for_writer"] is False
    assert competitor["allowed_claim_types"] == ["SOTA_benchmark"]
    assert "clinical_benefit" in competitor["forbidden_use"]
    assert similar["device_relationship"] == "similar"
    assert similar["weight"] == "background"
    assert "clinical_benefit" not in similar["allowed_claim_types"]
    assert "clinical_benefit" in similar["forbidden_use"]


def test_batch_6_3_formal_equivalence_requires_three_axis_rationale():
    weak_state = {
        "source_inventory": [
            {
                "source_id": "SRC-EQ-WEAK",
                "filename": "Equivalent device note.docx",
                "document_type": "equivalence",
                "source_role": "similar_or_benchmark_source",
                "text": "Equivalent device name is listed without analysis.",
            }
        ]
    }
    strong_state = {
        "source_inventory": [
            {
                "source_id": "SRC-EQ-STRONG",
                "filename": "Equivalence rationale.docx",
                "document_type": "equivalence",
                "source_role": "similar_or_benchmark_source",
                "text": "Technical, biological and clinical equivalence has been demonstrated and validated in the equivalence rationale.",
            }
        ]
    }

    weak = pipeline.prepare_source_inventory(weak_state)["evidence_source_inventory"][0]
    strong = pipeline.prepare_source_inventory(strong_state)["evidence_source_inventory"][0]

    assert weak["relationship_type"] == "similar_device"
    assert strong["relationship_type"] == "equivalent_device"
    assert "claims_outside_equivalence_scope" in strong["forbidden_use"]


def test_batch_6_3_competitor_pubmed_record_cannot_be_writer_approved(monkeypatch):
    def fake_call_public(tool: str, payload: dict):
        if tool == "pubmed_fetch":
            return {
                "status": "ok",
                "articles": [
                    {
                        "pmid": "99887766",
                        "title": "Competitor device clinical outcomes",
                        "full_text": "Boston Scientific competitor device randomized controlled trial enrolled n=126 patients. Results success 94% after 12 months follow-up.",
                    }
                ],
            }
        if tool == "pubmed_fetch_abstracts":
            return {"status": "ok", "articles": [{"pmid": "99887766", "abstract": "Competitor device n=126; 12 months follow-up; success 94%."}]}
        if tool == "pubmed_verify_citation":
            return {"status": "ok", "verified": True, "pmid": payload.get("pmid")}
        return {"status": "ok"}

    monkeypatch.setattr(pipeline.mcp_tools, "call_public", fake_call_public)
    monkeypatch.setattr(pipeline.mcp_tools, "call_tool", lambda *args, **kwargs: {"status": "ok", "cebm_level": "Level 2"})
    monkeypatch.setattr(pipeline.mcp_tools, "mcp_log_entry", lambda result, name: {"tool": name, "status": result.get("status")})

    state = _passing_state()
    state.pop("evidence_registry", None)
    state.pop("article_appraisal", None)
    state["screening_disposition"] = [
        {
            "article_id": "ART-001",
            "pmid": "99887766",
            "full_text_decision": "include_for_appraisal",
            "retrieval_domain_status": "DOMAIN_MATCH_HIGH",
            "endpoint_match": "high",
            "search_id": "SEARCH-SOTA-01",
            "purpose": "competitor benchmark context",
        }
    ]
    state["raw_literature_records"] = [
        {
            "article_id": "ART-001",
            "pmid": "99887766",
            "query_id": "Q-SOTA-001",
            "search_id": "SEARCH-SOTA-01",
            "retrieval_domain_status": "DOMAIN_MATCH_HIGH",
            "purpose": "competitor benchmark context",
            "title": "Boston Scientific competitor device clinical outcomes",
        }
    ]

    result = pipeline.appraise_evidence(state)
    evidence = result["evidence_registry"][0]

    assert evidence["device_relationship"] == "competitor"
    assert evidence["relationship_type"] == "competitor_device"
    assert evidence["allowed_claim_types"] == ["SOTA_benchmark"]
    assert "clinical_benefit" in evidence["forbidden_use"]
    assert evidence["weight"] == "background"
    assert evidence["ledger_approved_for_writer"] is False


def test_batch_5_5_endpoint_extraction_processes_all_records():
    evidence_rows = [
        {
            "evidence_id": f"E-{idx:03d}",
            "title": f"Endpoint study {idx}",
            "abstract_text": f"Clinical endpoint result n={100 + idx} success {80 + (idx % 10)}% at 12 months.",
            "follow_up": "12 months",
        }
        for idx in range(1, 61)
    ]

    rows = pipeline._extract_endpoint_rows_from_evidence(evidence_rows)

    assert len(rows) == 60
    assert rows[0]["source_evidence_id"] == "E-001"
    assert rows[-1]["source_evidence_id"] == "E-060"


def test_batch_5_5_sota_ck_appraisal_uses_all_sota_records():
    records = [
        {
            "article_id": f"ART-{idx:03d}",
            "search_id": "SEARCH-SOTA-01",
            "title": f"Systematic review benchmark record {idx}",
        }
        for idx in range(1, 56)
    ]

    rows = pipeline._sota_ck_appraisal_rows({"raw_literature_records": records}, [])

    assert len(rows) == 55
    assert rows[-1]["article_id"] == "ART-055"


def test_batch_5_5_source_inventory_scans_more_than_two_hundred_files(tmp_path):
    for idx in range(250):
        (tmp_path / f"source_{idx:03d}.txt").write_text("IFU source text", encoding="utf-8")

    inventory = pipeline._inventory_from_root(tmp_path)

    assert len(inventory) == 250
    assert "source_249.txt" in {row["filename"] for row in inventory}


def test_phase7_domain_lock_query_construction_excludes_cardiac_ep_for_orthopedic_rf():
    state = _passing_state()
    state["device_profile"] = {
        "device_name": "Arthroscopic RF Ablation Probe",
        "device_type": "radiofrequency surgical ablation probe",
        "intended_purpose": "joint surgery soft tissue resection ablation coagulation and hemostasis",
        "anatomical_site": "joint soft tissue",
    }
    state["device_identity_lock"] = {"locked_domain": "orthopedic_soft_tissue_rf_ablation", "classification_confidence": "high"}
    state["claim_ledger"] = [{"claim_id": "C-01", "claim_text": "Soft tissue ablation and hemostasis during joint surgery", "claim_type": "performance"}]
    state["cep_pico_matrix"] = [{"pico_id": "PICO-01", "claim_id": "C-01", "outcome": "soft tissue resection hemostasis safety"}]

    plan = pipeline._phase7_search_plan(state["device_profile"], state)
    pubmed_sota = next(row for row in plan if row["query_id"] == "Q-SOTA-001")

    assert pubmed_sota["retrieval_domain"] == "orthopedic_joint_soft_tissue_rf_ablation"
    assert "arthroscopy" in pubmed_sota["query_string"].lower()
    assert "radiofrequency" in pubmed_sota["query_string"].lower()
    assert "atrial fibrillation" in pubmed_sota["query_string"].lower()
    assert "NOT" in pubmed_sota["query_string"]


def test_phase7_screening_blocks_cardiac_ep_record_under_orthopedic_retrieval_domain():
    state = _passing_state()
    state.pop("screening_disposition", None)
    state["query_construction_trace"] = [
        {
            "query_id": "Q-SOTA-001",
            "retrieval_domain": "orthopedic_joint_soft_tissue_rf_ablation",
            "inclusion_terms": "orthopedic; arthroscopy; joint surgery; soft tissue; radiofrequency",
            "exclusion_terms": "atrial fibrillation; pulmonary vein; cardiac electrophysiology; catheter ablation",
        }
    ]
    state["raw_literature_records"] = [
        {
            "article_id": "ART-001",
            "pmid": "111",
            "title": "Pulmonary vein catheter ablation for atrial fibrillation",
            "search_id": "SEARCH-SOTA-01",
            "query_id": "Q-SOTA-001",
            "retrieval_domain": "orthopedic_joint_soft_tissue_rf_ablation",
            "database": "PubMed",
        }
    ]

    result = pipeline.screen_literature(state)
    row = result["screening_disposition"][0]

    assert row["title_abstract_decision"] == "exclude"
    assert row["retrieval_domain_status"] == "RETRIEVAL_DOMAIN_MISMATCH_REWORK_REQUIRED"
    assert row["evidence_role_candidate"] == "excluded_domain_mismatch"


def test_phase7_writer_consumes_only_ledger_approved_evidence():
    state = _passing_state()
    state["evidence_registry"] = [
        {"evidence_id": "E-001", "pmid": "111", "query_id": "Q-001", "search_id": "SEARCH-SOTA-01", "weight": "pivotal", "ledger_approved_for_writer": True, "retrieval_domain_status": "DOMAIN_MATCH_HIGH"},
        {"evidence_id": "E-002", "pmid": "222", "query_id": "Q-002", "search_id": "SEARCH-SOTA-02", "weight": "pivotal", "ledger_approved_for_writer": False, "retrieval_domain_status": "RETRIEVAL_DOMAIN_MISMATCH_REWORK_REQUIRED"},
    ]
    state["claim_ledger"] = [{"claim_id": "C-01", "claim_text": "Claim", "claim_type": "performance"}]
    state["sota_benchmark_matrix"] = [{"benchmark_id": "BM-01", "corresponding_claim_id": "C-01"}]
    state["sota_endpoint_derivation_table"] = [{"benchmark_id": "BM-01", "evidence_id": "E-002", "endpoint_id": "EP-01"}]

    matrix = pipeline._claim_evidence_matrix_rows(state)
    writer_trace = pipeline._writer_evidence_consumption_trace_rows(state)

    assert matrix[0]["evidence_ids"] != "E-002"
    blocked = next(row for row in writer_trace if row["evidence_id"] == "E-002")
    assert blocked["consumption_decision"] == "blocked"


def test_batch_6_4_competitor_evidence_blocked_for_clinical_benefit_claim():
    state = _passing_state()
    state["claim_ledger"] = [{"claim_id": "C-01", "claim_text": "Clinical benefit claim", "claim_type": "clinical_benefit"}]
    state["evidence_registry"] = [
        {
            "evidence_id": "E-COMP-001",
            "weight": "supportive",
            "ledger_approved_for_writer": True,
            "retrieval_domain_status": "DOMAIN_MATCH_HIGH",
            "source_type": "competitor_device_public",
            "device_relationship": "competitor",
            "allowed_claim_types": ["SOTA_benchmark"],
            "allowed_conclusion_strength_max": "descriptive_or_cautious",
            "forbidden_use": ["clinical_benefit", "clinical_safety", "performance"],
        }
    ]
    state["sota_benchmark_matrix"] = [{"benchmark_id": "BM-01", "corresponding_claim_id": "C-01"}]
    state["sota_endpoint_derivation_table"] = [{"benchmark_id": "BM-01", "evidence_id": "E-COMP-001", "endpoint_id": "EP-01", "benchmark_value": "94%"}]

    matrix = pipeline._claim_evidence_matrix_rows(state)
    trace = pipeline._writer_evidence_consumption_trace_rows(state)

    assert matrix[0]["support_status"] == "ALLOWED_USE_BLOCKED"
    assert matrix[0]["conclusion_strength"] == "not_allowed"
    assert matrix[0]["blocked_evidence_ids"] == "E-COMP-001"
    blocked = trace[0]
    assert blocked["claim_id"] == "C-01"
    assert blocked["consumption_decision"] == "blocked"
    assert blocked["writer_consumes_as"] == "blocked_allowed_use_violation"
    assert "CLAIM_TYPE_NOT_ALLOWED" in blocked["block_reason_codes"]
    assert "DEVICE_RELATIONSHIP_FORBIDDEN" in blocked["block_reason_codes"]


def test_batch_6_4_competitor_evidence_allowed_for_sota_benchmark_claim():
    state = _passing_state()
    state["claim_ledger"] = [{"claim_id": "C-01", "claim_text": "SOTA benchmark claim", "claim_type": "SOTA_benchmark"}]
    state["evidence_registry"] = [
        {
            "evidence_id": "E-COMP-001",
            "weight": "supportive",
            "ledger_approved_for_writer": True,
            "retrieval_domain_status": "DOMAIN_MATCH_HIGH",
            "source_type": "competitor_device_public",
            "device_relationship": "competitor",
            "allowed_claim_types": ["SOTA_benchmark"],
            "allowed_conclusion_strength_max": "descriptive_or_cautious",
            "forbidden_use": ["clinical_benefit", "clinical_safety", "performance"],
        }
    ]
    state["sota_benchmark_matrix"] = [{"benchmark_id": "BM-01", "corresponding_claim_id": "C-01"}]
    state["sota_endpoint_derivation_table"] = [{"benchmark_id": "BM-01", "evidence_id": "E-COMP-001", "endpoint_id": "EP-01", "benchmark_value": "94%"}]

    matrix = pipeline._claim_evidence_matrix_rows(state)
    trace = pipeline._writer_evidence_consumption_trace_rows(state)

    assert matrix[0]["evidence_ids"] == "E-COMP-001"
    assert matrix[0]["support_status"] == "partially_supported"
    assert trace[0]["allowed_use_decision"] == "allowed"
    assert trace[0]["consumption_decision"] == "approved"


def test_batch_6_4_conclusion_strength_cap_blocks_writer_consumption():
    state = _passing_state()
    state["claim_ledger"] = [{"claim_id": "C-01", "claim_text": "Performance claim", "claim_type": "performance"}]
    state["evidence_registry"] = [
        {
            "evidence_id": "E-SUBJ-001",
            "weight": "supportive",
            "ledger_approved_for_writer": True,
            "retrieval_domain_status": "DOMAIN_MATCH_HIGH",
            "source_type": "subject_device_test_performance",
            "device_relationship": "subject",
            "allowed_claim_types": ["performance"],
            "allowed_conclusion_strength_max": "background_or_gap_controlled",
        }
    ]
    state["sota_benchmark_matrix"] = [{"benchmark_id": "BM-01", "corresponding_claim_id": "C-01"}]
    state["sota_endpoint_derivation_table"] = [{"benchmark_id": "BM-01", "evidence_id": "E-SUBJ-001", "endpoint_id": "EP-01", "benchmark_value": "pass"}]

    matrix = pipeline._claim_evidence_matrix_rows(state)
    trace = pipeline._writer_evidence_consumption_trace_rows(state)

    assert matrix[0]["support_status"] == "ALLOWED_USE_BLOCKED"
    assert trace[0]["consumption_decision"] == "blocked"
    assert "CONCLUSION_STRENGTH_EXCEEDED" in trace[0]["block_reason_codes"]


def test_batch_6_4_legacy_evidence_without_v2_metadata_remains_writer_compatible():
    state = _passing_state()
    state["claim_ledger"] = [{"claim_id": "C-01", "claim_text": "Performance claim", "claim_type": "performance"}]
    state["evidence_registry"] = [
        {
            "evidence_id": "E-LEGACY-001",
            "weight": "pivotal",
            "ledger_approved_for_writer": True,
            "retrieval_domain_status": "DOMAIN_MATCH_HIGH",
        }
    ]
    state["sota_benchmark_matrix"] = [{"benchmark_id": "BM-01", "corresponding_claim_id": "C-01"}]
    state["sota_endpoint_derivation_table"] = [{"benchmark_id": "BM-01", "evidence_id": "E-LEGACY-001", "endpoint_id": "EP-01", "benchmark_value": "pass"}]

    matrix = pipeline._claim_evidence_matrix_rows(state)
    trace = pipeline._writer_evidence_consumption_trace_rows(state)

    assert matrix[0]["evidence_ids"] == "E-LEGACY-001"
    assert trace[0]["consumption_decision"] == "approved"
    assert trace[0]["metadata_mode"] == "legacy_metadata_absent"
    assert trace[0]["block_reason_codes"] == "LEGACY_METADATA_ABSENT_PASS"


def test_phase7_artifact_writer_emits_retrieval_grounding_csvs(tmp_path):
    state = _passing_state()
    state["query_construction_trace"] = [{"query_id": "Q-001", "query_string": "orthopedic AND radiofrequency"}]
    state["pubmed_mcp_retrieval_ledger"] = [{"retrieval_id": "RET-001", "query_id": "Q-001", "retrieval_count": 1}]
    state["pmid_screening_and_exclusion_table"] = [{"screen_id": "SCR-001", "pmid": "111", "title_abstract_decision": "include"}]
    state["fulltext_acquisition_status_table"] = [{"evidence_id": "E-001", "full_text_available": "yes"}]
    state["evidence_source_trace_matrix"] = [{"evidence_id": "E-001", "query_id": "Q-001", "ledger_approved_for_writer": True}]
    state["allowed_use_matrix"] = [{"allowed_use_id": "AUM-001", "claim_id": "C-01", "evidence_id": "E-001", "allowed_use_decision": "allowed"}]
    state["writer_evidence_consumption_trace"] = [{"evidence_id": "E-001", "consumption_decision": "approved"}]
    state["retrieval_domain_grounding_report"] = "# Retrieval Domain Grounding Report\n\nOK\n"

    workbook = build_authoring_workbook(state)
    written = write_authoring_artifacts(tmp_path, state)
    names = {Path(path).name for path in written}

    assert workbook["allowed_use_matrix"][0]["allowed_use_id"] == "AUM-001"
    assert "query_construction_trace.csv" in names
    assert "pubmed_mcp_retrieval_ledger.csv" in names
    assert "pmid_screening_and_exclusion_table.csv" in names
    assert "fulltext_acquisition_status_table.csv" in names
    assert "evidence_source_trace_matrix.csv" in names
    assert "allowed_use_matrix.xlsx" in names
    assert "writer_evidence_consumption_trace.csv" in names
    assert "retrieval_domain_grounding_report.md" in names


def _write_structured_table_pdf(path: Path) -> None:
    import fitz

    doc = fitz.open()
    page = doc.new_page(width=320, height=240)
    page.insert_text((40, 35), "Batch 7.1 Structured Table Source", fontsize=15)
    x0, y0 = 40, 70
    cell_w, cell_h = 82, 30
    rows, cols = 3, 3
    for idx in range(rows + 1):
        page.draw_line((x0, y0 + idx * cell_h), (x0 + cols * cell_w, y0 + idx * cell_h), color=(0, 0, 0), width=1)
    for idx in range(cols + 1):
        page.draw_line((x0 + idx * cell_w, y0), (x0 + idx * cell_w, y0 + rows * cell_h), color=(0, 0, 0), width=1)
    values = [["Endpoint", "N", "Result"], ["Clinical success", "100", "95%"], ["Safety", "100", "0 SAE"]]
    for row_idx, row in enumerate(values):
        for col_idx, value in enumerate(row):
            page.insert_text((x0 + 5 + col_idx * cell_w, y0 + 20 + row_idx * cell_h), value, fontsize=8)
    doc.save(path)


def _write_scanned_pdf_with_ocr_text(path: Path) -> None:
    import fitz
    from PIL import Image, ImageDraw, ImageFont

    image = Image.new("RGB", (1800, 1100), "white")
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 54)
    except Exception:
        font = ImageFont.load_default()
    line = "Scanned OCR fallback clinical evaluation table text endpoint success rate ninety five percent."
    for idx in range(10):
        draw.text((80, 80 + idx * 90), f"{idx + 1}. {line}", fill="black", font=font)
    image_path = path.with_suffix(".png")
    image.save(image_path)
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    page.insert_image(page.rect, filename=str(image_path))
    doc.save(path)


def test_batch_7_1_dependency_preflight_passes_after_install():
    report = pipeline.validate_document_parsing_dependencies()

    assert report["status"] == "PASS"
    assert all(report["checks"].values())


def test_batch_7_1_pymupdf_and_camelot_extract_pdf_table_into_state(tmp_path):
    pdf = tmp_path / "structured_table.pdf"
    _write_structured_table_pdf(pdf)

    result = pipeline.prepare_source_inventory(
        {
            "source_inventory": [
                {
                    "source_id": "SRC-PDF-001",
                    "path": str(pdf),
                    "filename": pdf.name,
                    "document_type": "source",
                }
            ]
        }
    )

    documents = result["document_structured_content"]
    lineage = result["document_parsing_lineage"]
    parsed = documents[0]
    tables = [table for page in parsed["pages"] for table in page["tables"]]
    source_row = result["source_inventory"][0]

    assert parsed["page_count"] == 1
    assert parsed["heading_count"] >= 1
    assert tables
    assert tables[0]["extraction_method"] in {"camelot_lattice", "camelot_stream"}
    assert any("Clinical success" in " ".join(row) for row in tables[0]["cells"])
    assert lineage[0]["status"] == "parsed"
    assert lineage[0]["table_count"] >= 1
    assert source_row["document_structured_content_available"] is True
    assert "Clinical success" in source_row["text"]


def test_batch_7_1_pymupdf_parses_cal001_pdf_when_available():
    cal_root = Path("/Users/winstonwei/Downloads/PROJECT_01_PILOT_CALIBRATION/01_INITIAL_INPUT_FOR_WRITER")
    if not cal_root.exists():
        pytest.skip("CAL-001 local source folder is not available on this machine.")
    pdfs = sorted(cal_root.rglob("*.pdf"))
    if not pdfs:
        pytest.skip("CAL-001 local source folder contains no PDF files.")
    pdf = pdfs[0]

    result = pipeline.parse_document_structured_content(
        [{"source_id": "SRC-CAL001-PDF-001", "path": str(pdf), "filename": pdf.name, "document_type": "source"}]
    )

    parsed = result["document_structured_content"][0]
    assert parsed["page_count"] >= 1
    assert parsed["heading_count"] + parsed["paragraph_count"] >= 1
    assert result["document_parsing_lineage"][0]["status"] in {"parsed", "parse_timeout"}
    assert result["document_parsing_lineage"][0]["pages_parsed"] >= 1


def test_batch_7_1_artifact_export_includes_document_parsing_lineage_csv(tmp_path):
    state = _passing_state()
    state["document_structured_content"] = [
        {
            "document_id": "DOC-SRC-PDF-001",
            "source_id": "SRC-PDF-001",
            "filename": "structured_table.pdf",
            "parser_stack": "PyMuPDF+Camelot(lattice->stream)",
            "page_count": 1,
            "paragraph_count": 1,
            "heading_count": 1,
            "table_count": 1,
            "pages": [{"page_number": 1, "headings": [], "paragraphs": [], "tables": []}],
        }
    ]
    state["document_parsing_lineage"] = [
        {
            "row_id": "DPL-SRC-PDF-001",
            "source_id": "SRC-PDF-001",
            "parser_stack": "PyMuPDF+Camelot(lattice->stream)",
            "status": "parsed",
            "page_count": 1,
            "table_count": 1,
        }
    ]

    written = write_authoring_artifacts(tmp_path, state)
    workbook = json.loads((tmp_path / "authoring_workbook.json").read_text(encoding="utf-8"))

    assert str(tmp_path / "document_parsing_lineage.csv") in written
    assert "document_structured_content" in workbook
    assert workbook["document_parsing_lineage"][0]["source_id"] == "SRC-PDF-001"
    assert "parser_stack" in (tmp_path / "document_parsing_lineage.csv").read_text(encoding="utf-8")


def test_batch_7_2_ocr_fallback_triggers_on_scanned_pdf_and_lineage_records_usage(tmp_path):
    pdf = tmp_path / "scanned_ocr_source.pdf"
    _write_scanned_pdf_with_ocr_text(pdf)

    result = pipeline.prepare_source_inventory(
        {
            "source_inventory": [
                {
                    "source_id": "SRC-OCR-001",
                    "path": str(pdf),
                    "filename": pdf.name,
                    "document_type": "source",
                }
            ]
        }
    )

    parsed = result["document_structured_content"][0]
    lineage = result["document_parsing_lineage"][0]
    page = parsed["pages"][0]
    ocr_paragraphs = [row for row in page["paragraphs"] if row.get("extraction_method") == "tesseract_ocr"]

    assert page["extractable_text_chars"] < 100
    assert page["ocr_used"] is True
    assert page["ocr_text_chars"] >= 100
    assert ocr_paragraphs
    assert "Scanned OCR fallback" in ocr_paragraphs[0]["text"]
    assert lineage["parser_used"].startswith("PyMuPDF+Camelot")
    assert lineage["pages_total"] == 1
    assert lineage["pages_extractable"] == 0
    assert lineage["pages_ocr"] == 1
    assert lineage["ocr_recovered_content"] is True


def test_v3_pdf_hardening_skips_camelot_on_image_page_and_records_page_lineage(tmp_path, monkeypatch):
    pdf = tmp_path / "image_only.pdf"
    _write_scanned_pdf_with_ocr_text(pdf)

    def fail_camelot(*args, **kwargs):
        raise AssertionError("Camelot must not run for image-only pages")

    def fake_ocr(path, page_number, *, timeout_seconds=None):
        return {"used": True, "text": "OCR recovered endpoint success rate 95 percent. " * 4, "chars": 184, "quality_flag": "", "error": ""}

    monkeypatch.setattr(pipeline, "_run_camelot_page_with_timeout", fail_camelot)
    monkeypatch.setattr(pipeline, "_ocr_pdf_page_with_tesseract", fake_ocr)

    result = pipeline.parse_document_structured_content(
        [{"source_id": "SRC-IMG-001", "path": str(pdf), "filename": pdf.name, "document_type": "source"}]
    )

    parsed = result["document_structured_content"][0]
    lineage = result["document_parsing_lineage"][0]
    page = parsed["pages"][0]

    assert page["source_page"] == 1
    assert page["source_anchor"] == "SRC-IMG-001:p1"
    assert page["extraction_status"] == "ocr_fallback"
    assert page["table_extraction_status"] == "skipped_image_page"
    assert page["page_lineage"]["text_extraction_status"] == "ocr_fallback"
    assert lineage["pages_skipped_image"] == 1
    assert lineage["page_lineage"][0]["table_extraction_status"] == "skipped_image_page"


def test_v3_pdf_hardening_file_timeout_records_all_pages_without_silent_drop(tmp_path):
    import fitz

    pdf = tmp_path / "timeout_source.pdf"
    doc = fitz.open()
    for idx in range(2):
        page = doc.new_page(width=320, height=240)
        page.insert_text((40, 40), f"Timeout page {idx + 1} with text", fontsize=12)
    doc.save(pdf)

    result = pipeline.parse_document_structured_content(
        [{"source_id": "SRC-TIMEOUT-001", "path": str(pdf), "filename": pdf.name, "document_type": "source", "pdf_parse_timeout_seconds": 0}]
    )

    parsed = result["document_structured_content"][0]
    lineage = result["document_parsing_lineage"][0]

    assert parsed["status"] == "parse_timeout"
    assert parsed["page_count"] == 2
    assert len(parsed["pages"]) == 2
    assert {page["extraction_status"] for page in parsed["pages"]} == {"file_timeout_skipped"}
    assert lineage["status"] == "parse_timeout"
    assert lineage["pages_timeout"] == 2
    assert lineage["page_lineage"][1]["source_anchor"] == "SRC-TIMEOUT-001:p2"


def test_v3_pdf_hardening_camelot_lattice_only_never_calls_stream(tmp_path, monkeypatch):
    pdf = tmp_path / "text_table_candidate.pdf"
    _write_structured_table_pdf(pdf)

    calls: list[tuple[int, str]] = []

    def fake_camelot(path, source_id, page_number, flavor, timeout_seconds):
        calls.append((page_number, flavor))
        if flavor != "lattice":
            raise AssertionError("PDF-1 must not call Camelot stream fallback")
        return [
            {
                "table_id": "TEMP",
                "page_number": page_number,
                "extraction_method": "camelot_lattice",
                "row_count": 1,
                "column_count": 2,
                "cells": [["Endpoint", "95%"]],
            }
        ], ""

    monkeypatch.setattr(pipeline, "_run_camelot_page_with_timeout", fake_camelot)

    result = pipeline.parse_document_structured_content(
        [{"source_id": "SRC-CAM-001", "path": str(pdf), "filename": pdf.name, "document_type": "source"}]
    )

    tables = [table for page in result["document_structured_content"][0]["pages"] for table in page["tables"]]

    assert calls == [(1, "lattice")]
    assert tables[0]["source_table"] == "SRC-CAM-001-T001"
    assert tables[0]["source_anchor"] == "SRC-CAM-001:p1:T001"


def test_v3_pdf_hardening_lattice_timeout_is_cached_and_recorded(tmp_path, monkeypatch):
    pdf = tmp_path / "timeout_table.pdf"
    _write_structured_table_pdf(pdf)
    pipeline.PDF_ENGINE_FAILURE_CACHE.clear()

    def fake_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=args[0], timeout=kwargs.get("timeout"))

    monkeypatch.setattr(pipeline.subprocess, "run", fake_run)

    tables, first_error = pipeline._run_camelot_page_with_timeout(pdf, "SRC-TIMEOUT-CAM", 1, "lattice", 1)
    tables_cached, cached_error = pipeline._run_camelot_page_with_timeout(pdf, "SRC-TIMEOUT-CAM", 1, "lattice", 1)

    assert tables == []
    assert first_error.startswith("camelot_timeout:lattice:page_1")
    assert tables_cached == []
    assert cached_error.startswith("cached_failure:camelot_timeout:lattice:page_1")


def test_v3_pdf_hardening_failure_cache_prevents_repeated_camelot_call(tmp_path, monkeypatch):
    pdf = tmp_path / "cache_table.pdf"
    _write_structured_table_pdf(pdf)
    pipeline.PDF_ENGINE_FAILURE_CACHE.clear()
    calls = {"count": 0}

    class Result:
        returncode = 2
        stdout = ""
        stderr = "synthetic camelot failure"

    def fake_run(*args, **kwargs):
        calls["count"] += 1
        return Result()

    monkeypatch.setattr(pipeline.subprocess, "run", fake_run)

    pipeline._run_camelot_page_with_timeout(pdf, "SRC-CACHE", 1, "lattice", 1)
    pipeline._run_camelot_page_with_timeout(pdf, "SRC-CACHE", 1, "lattice", 1)

    assert calls["count"] == 1


def test_v3_pdf_hardening_file_timeout_continues_next_file(tmp_path):
    import fitz

    first = tmp_path / "timeout_first.pdf"
    doc = fitz.open()
    for idx in range(2):
        page = doc.new_page(width=320, height=240)
        page.insert_text((40, 40), f"Timeout page {idx + 1} with text", fontsize=12)
    doc.save(first)
    second = tmp_path / "second.pdf"
    _write_structured_table_pdf(second)

    result = pipeline.parse_document_structured_content(
        [
            {"source_id": "SRC-TIMEOUT-FIRST", "path": str(first), "filename": first.name, "document_type": "source", "pdf_parse_timeout_seconds": 0},
            {"source_id": "SRC-SECOND", "path": str(second), "filename": second.name, "document_type": "source"},
        ]
    )

    by_id = {row["source_id"]: row for row in result["document_parsing_lineage"]}

    assert by_id["SRC-TIMEOUT-FIRST"]["status"] == "parse_timeout"
    assert by_id["SRC-TIMEOUT-FIRST"]["pages_timeout"] == 2
    assert by_id["SRC-SECOND"]["pages_total"] == 1


def test_v3_pdf_hardening_page_lineage_contains_classifier_router_timing_fields(tmp_path, monkeypatch):
    pdf = tmp_path / "lineage.pdf"
    _write_scanned_pdf_with_ocr_text(pdf)

    monkeypatch.setattr(
        pipeline,
        "_ocr_pdf_page_with_tesseract",
        lambda path, page_number, *, timeout_seconds=None: {"used": True, "text": "", "chars": 0, "quality_flag": "OCR_LOW_QUALITY", "error": "synthetic_low_quality"},
    )

    result = pipeline.parse_document_structured_content(
        [{"source_id": "SRC-LINEAGE", "path": str(pdf), "filename": pdf.name, "document_type": "source"}]
    )

    lineage = result["document_parsing_lineage"][0]["page_lineage"][0]

    assert {
        "source_file",
        "page_number",
        "classified_as",
        "routed_to",
        "engine_mode",
        "extraction_status",
        "fallback_reason",
        "extraction_confidence",
        "timing_ms",
        "timeout_ms",
        "parser_engine_used",
        "parser_engine_version",
    }.issubset(lineage)
    assert lineage["classified_as"] == "image_scanned"
    assert lineage["routed_to"] == "tesseract_ocr"


def test_pdf2_docling_unavailable_falls_back_to_existing_parser(tmp_path, monkeypatch):
    import fitz

    pdf = tmp_path / "docling_unavailable.pdf"
    doc = fitz.open()
    page = doc.new_page(width=320, height=240)
    page.insert_text((30, 40), " ".join(["Digital text page for Docling fallback"] * 20), fontsize=10)
    doc.save(pdf)

    monkeypatch.setattr(pipeline, "_docling_available", lambda: (False, "docling_not_installed"))

    result = pipeline.parse_document_structured_content(
        [{"source_id": "SRC-DOCLING-OFF", "path": str(pdf), "filename": pdf.name, "document_type": "source", "parser_depth": "deep", "docling_mode": "preferred"}]
    )

    page = result["document_structured_content"][0]["pages"][0]

    assert page["page_lineage"]["routed_to"] == "pymupdf_text"
    assert "docling" in page["fallback_reason"]
    assert page["paragraphs"]


def test_pdf2_docling_timeout_returns_structured_error(monkeypatch, tmp_path):
    pdf = tmp_path / "docling_timeout.pdf"
    _write_structured_table_pdf(pdf)

    def fake_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=args[0], timeout=kwargs.get("timeout"))

    monkeypatch.setattr(pipeline, "_docling_available", lambda: (True, "test-version"))
    monkeypatch.setattr(pipeline.subprocess, "run", fake_run)

    result = pipeline._parse_with_docling(pdf, pages=[1], timeout_seconds=1)

    assert result["parser_engine"] == "docling"
    assert result["parser_status"] == "timeout"
    assert "docling_timeout" in result["error_message"]
    assert result["pages"] == {}


def test_pdf2_docling_parse_success_normalized_output(monkeypatch, tmp_path):
    pdf = tmp_path / "docling_success.pdf"
    _write_structured_table_pdf(pdf)

    class Result:
        returncode = 0
        stderr = ""
        stdout = json.dumps(
            {
                "parser_engine": "docling",
                "parser_status": "parsed",
                "parser_engine_version": "test-version",
                "pages": {
                    "1": {
                        "text": "Docling normalized text",
                        "tables": [{"rows": 1, "cols": 2, "data": [["A", "B"]], "source_table_anchor": "DOCLING-T001"}],
                        "layout_tree": {"num_pages": 1},
                        "parser_engine": "docling",
                        "parser_status": "parsed",
                        "timing_ms": 12,
                        "confidence": "medium",
                        "error_message": "",
                    }
                },
                "timing_ms": 12,
                "confidence": "medium",
                "error_message": "",
            }
        )

    monkeypatch.setattr(pipeline, "_docling_available", lambda: (True, "test-version"))
    monkeypatch.setattr(pipeline.subprocess, "run", lambda *args, **kwargs: Result())

    result = pipeline._parse_with_docling(pdf, pages=[1], timeout_seconds=1)

    page = result["pages"]["1"]
    assert page["text"] == "Docling normalized text"
    assert page["tables"][0]["source_table_anchor"] == "DOCLING-T001"
    assert page["layout_tree"]["num_pages"] == 1
    assert page["parser_status"] == "parsed"


def test_pdf2_docling_shadow_mode_does_not_change_operational_output(tmp_path, monkeypatch):
    import fitz

    pdf = tmp_path / "docling_shadow.pdf"
    doc = fitz.open()
    page = doc.new_page(width=320, height=240)
    page.insert_text((30, 40), " ".join(["Operational PyMuPDF text"] * 20), fontsize=10)
    doc.save(pdf)

    monkeypatch.setattr(
        pipeline,
        "_parse_with_docling",
        lambda path, pages=None, timeout_seconds=None: {
            "parser_engine": "docling",
            "parser_status": "parsed",
            "pages": {"1": {"text": "SHADOW DOCLING TEXT", "tables": [], "layout_tree": {}, "parser_status": "parsed", "timing_ms": 1, "confidence": "medium", "error_message": ""}},
            "timing_ms": 1,
            "confidence": "medium",
            "error_message": "",
        },
    )

    result = pipeline.parse_document_structured_content(
        [{"source_id": "SRC-SHADOW", "path": str(pdf), "filename": pdf.name, "document_type": "source", "docling_mode": "shadow", "docling_shadow_pages": [1]}]
    )

    parsed = result["document_structured_content"][0]
    page = parsed["pages"][0]

    assert "SHADOW DOCLING TEXT" not in " ".join(row.get("text", "") for row in page["paragraphs"])
    assert parsed["docling_shadow"]["parser_status"] == "parsed"
    assert page["page_lineage"]["parser_engine_used"] == "PyMuPDF"


def test_pdf2_docling_preferred_routes_text_digital_and_falls_back_on_failure(tmp_path, monkeypatch):
    import fitz

    pdf = tmp_path / "docling_preferred.pdf"
    doc = fitz.open()
    page = doc.new_page(width=320, height=240)
    page.insert_text((30, 40), " ".join(["Docling preferred digital text"] * 20), fontsize=10)
    doc.save(pdf)

    monkeypatch.setattr(
        pipeline,
        "_parse_with_docling",
        lambda path, pages=None, timeout_seconds=None: {
            "parser_engine": "docling",
            "parser_status": "error",
            "pages": {},
            "timing_ms": 1,
            "confidence": "low",
            "error_message": "synthetic_docling_failure",
        },
    )

    result = pipeline.parse_document_structured_content(
        [{"source_id": "SRC-PREFERRED", "path": str(pdf), "filename": pdf.name, "document_type": "source", "parser_depth": "deep", "docling_mode": "preferred"}]
    )

    page = result["document_structured_content"][0]["pages"][0]

    assert page["page_lineage"]["routed_to"] == "pymupdf_text"
    assert page["fallback_reason"] == "docling_unavailable_or_failed"
    assert page["paragraphs"]


def test_pdf2b_docling_routing_is_page_type_gated_and_image_scanned_disabled(tmp_path, monkeypatch):
    pdf = tmp_path / "docling_image_disabled.pdf"
    _write_scanned_pdf_with_ocr_text(pdf)

    monkeypatch.setattr(
        pipeline,
        "_parse_with_docling",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("image_scanned pages must not request Docling")),
    )
    monkeypatch.setattr(
        pipeline,
        "_ocr_pdf_page_with_tesseract",
        lambda path, page_number, *, timeout_seconds=None: {"used": True, "text": "OCR recovered", "chars": 13, "quality_flag": "OCR_LOW_QUALITY", "error": ""},
    )

    result = pipeline.parse_document_structured_content(
        [
            {
                "source_id": "SRC-DOCLING-IMG",
                "path": str(pdf),
                "filename": pdf.name,
                "document_type": "source",
                "docling_routing": {"image_scanned": "preferred"},
            }
        ]
    )

    page = result["document_structured_content"][0]["pages"][0]

    assert page["classified_as"] == "image_scanned"
    assert page["page_lineage"]["routed_to"] == "tesseract_ocr"
    assert page["ocr_used"] is True


def test_pdf2b_docling_benchmark_report_contains_per_type_metrics(tmp_path, monkeypatch):
    pdf = tmp_path / "docling_benchmark.pdf"
    _write_structured_table_pdf(pdf)

    monkeypatch.setattr(
        pipeline,
        "_extract_pdf_tables_with_camelot",
        lambda path, source_id, pages=None, deadline=None: (
            [
                {
                    "table_id": "T001",
                    "page_number": 1,
                    "source_table": "T001",
                    "source_anchor": "SRC:p1:T001",
                    "cells": [["Endpoint", "95%"]],
                }
            ],
            [],
        ),
    )
    monkeypatch.setattr(
        pipeline,
        "_parse_with_docling",
        lambda path, pages=None, timeout_seconds=None: {
            "parser_engine": "docling",
            "parser_status": "parsed",
            "pages": {
                "1": {
                    "text": "Docling benchmark text " * 12,
                    "tables": [{"rows": 1, "cols": 2, "data": [["A", "B"]], "source_table_anchor": "DOCLING-T001"}],
                    "layout_tree": {},
                    "parser_status": "parsed",
                    "timing_ms": 2,
                    "confidence": "medium",
                    "error_message": "",
                }
            },
            "timing_ms": 2,
            "confidence": "medium",
            "error_message": "",
        },
    )

    report_path = tmp_path / "PDF2_DOCLING_BENCHMARK_REPORT.md"
    report = pipeline.build_docling_shadow_benchmark_report([pdf], report_path)

    assert report["routing_model"] == "per_page_type"
    assert report["page_rows"]
    assert report["page_type_metrics"]
    assert report["recommended_routing"]["image_scanned"] == "disabled"
    assert "Page-Type Metrics" in report_path.read_text(encoding="utf-8")


def test_pdf2_1_bulk_screening_fast_skips_camelot_docling_and_ocr(tmp_path, monkeypatch):
    pdf = tmp_path / "fast_bulk.pdf"
    _write_structured_table_pdf(pdf)

    monkeypatch.setattr(pipeline, "_extract_pdf_tables_with_camelot", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("fast mode must skip Camelot")))
    monkeypatch.setattr(pipeline, "_parse_with_docling", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("fast mode must skip Docling")))
    monkeypatch.setattr(pipeline, "_ocr_pdf_page_with_tesseract", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("fast mode must skip OCR")))

    result = pipeline.parse_document_structured_content(
        [{"source_id": "SRC-FAST", "path": str(pdf), "filename": pdf.name, "document_type": "source", "pipeline_stage": "bulk_screening"}]
    )

    document = result["document_structured_content"][0]
    page = document["pages"][0]

    assert document["parser_depth"] == "fast"
    assert page["extraction_status"] in {"text_preview", "no_text_preview_available"}
    assert page["tables"] == []
    assert page["page_lineage"]["routed_engine"] == "pymupdf_text_preview"


def test_pdf2_1_fast_image_only_records_ocr_needed_without_ocr(tmp_path, monkeypatch):
    pdf = tmp_path / "fast_image.pdf"
    _write_scanned_pdf_with_ocr_text(pdf)

    monkeypatch.setattr(pipeline, "_ocr_pdf_page_with_tesseract", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("fast image preview must not OCR")))

    result = pipeline.parse_document_structured_content(
        [{"source_id": "SRC-FAST-IMG", "path": str(pdf), "filename": pdf.name, "document_type": "source", "pipeline_stage": "bulk_screening"}]
    )

    page = result["document_structured_content"][0]["pages"][0]

    assert page["classified_as"] == "image_scanned"
    assert page["extraction_status"] == "image_only_detected"
    assert page["fallback_reason"] == "ocr_needed"
    assert page["ocr_used"] is False


def test_pdf2_1_evidence_appraisal_defaults_to_standard(tmp_path):
    pdf = tmp_path / "standard.pdf"
    _write_structured_table_pdf(pdf)

    result = pipeline.parse_document_structured_content(
        [{"source_id": "SRC-STANDARD", "path": str(pdf), "filename": pdf.name, "document_type": "source", "pipeline_stage": "evidence_appraisal"}]
    )

    document = result["document_structured_content"][0]

    assert document["parser_depth"] == "standard"
    assert document["parser_depth_reason"] == "pipeline_stage=evidence_appraisal"


def test_pdf2_1_human_marked_key_evidence_selects_deep(tmp_path):
    pdf = tmp_path / "human_key.pdf"
    _write_structured_table_pdf(pdf)

    result = pipeline.parse_document_structured_content(
        [{"source_id": "SRC-HUMAN-KEY", "path": str(pdf), "filename": pdf.name, "document_type": "source", "human_marked_key_evidence": True}]
    )

    document = result["document_structured_content"][0]

    assert document["parser_depth"] == "deep"
    assert document["parser_depth_status"] == "bounded"


def test_pdf2_1_high_value_source_type_is_deep_bounded_not_unlimited(tmp_path):
    import fitz

    pdf = tmp_path / "pmcf_many_pages.pdf"
    doc = fitz.open()
    for idx in range(3):
        page = doc.new_page(width=320, height=240)
        page.insert_text((30, 40), f"PMCF page {idx + 1} with endpoint success rate 90%", fontsize=10)
    doc.save(pdf)

    result = pipeline.parse_document_structured_content(
        [
            {
                "source_id": "SRC-PMCF",
                "path": str(pdf),
                "filename": pdf.name,
                "document_type": "source",
                "source_type": "subject_device_pms_pmcf",
                "deep_max_pages": 1,
            }
        ]
    )

    document = result["document_structured_content"][0]

    assert document["parser_depth"] == "deep"
    assert len(document["pages"]) == 3
    assert document["pages"][1]["extraction_status"] == "deep_scope_skipped"
    assert document["pages"][2]["extraction_status"] == "deep_scope_skipped"


def test_pdf2_1_standard_parse_enqueues_deep_reparse_for_pivotal(tmp_path):
    pdf = tmp_path / "pivotal.pdf"
    _write_structured_table_pdf(pdf)
    pipeline.PDF_DEEP_REPARSE_REQUEST_CACHE.clear()

    result = pipeline.parse_document_structured_content(
        [
            {
                "source_id": "SRC-PIVOTAL",
                "path": str(pdf),
                "filename": pdf.name,
                "document_type": "source",
                "pipeline_stage": "evidence_appraisal",
                "evidence_role": "pivotal",
            }
        ]
    )

    requests = result["deep_reparse_requests"]

    assert requests
    assert requests[0]["deep_reparse_reason"] == "evidence_role=pivotal"
    assert result["document_structured_content"][0]["deep_reparse_requested"] is True


def test_pdf2_1_deep_reparse_request_cache_prevents_repeat(tmp_path):
    pdf = tmp_path / "pivotal_cached.pdf"
    _write_structured_table_pdf(pdf)
    pipeline.PDF_DEEP_REPARSE_REQUEST_CACHE.clear()
    item = {
        "source_id": "SRC-PIVOTAL-CACHE",
        "path": str(pdf),
        "filename": pdf.name,
        "document_type": "source",
        "pipeline_stage": "evidence_appraisal",
        "evidence_role": "pivotal",
    }

    first = pipeline.parse_document_structured_content([item])
    second = pipeline.parse_document_structured_content([item])

    assert len(first["deep_reparse_requests"]) == 1
    assert second["deep_reparse_requests"] == []


def test_pdf2_1_deep_docling_only_when_allowed_otherwise_standard_route(tmp_path, monkeypatch):
    import fitz

    pdf = tmp_path / "deep_docling_gate.pdf"
    doc = fitz.open()
    page = doc.new_page(width=320, height=240)
    page.insert_text((30, 40), " ".join(["Deep digital text"] * 30), fontsize=10)
    doc.save(pdf)

    calls = {"docling": 0}

    def fake_docling(*args, **kwargs):
        calls["docling"] += 1
        return {
            "parser_engine": "docling",
            "parser_status": "parsed",
            "pages": {"1": {"text": "Docling deep text", "tables": [], "layout_tree": {}, "parser_status": "parsed", "timing_ms": 1, "confidence": "medium", "error_message": ""}},
            "timing_ms": 1,
            "confidence": "medium",
            "error_message": "",
        }

    monkeypatch.setattr(pipeline, "_parse_with_docling", fake_docling)

    standard_route = pipeline.parse_document_structured_content(
        [{"source_id": "SRC-DEEP-NO-DOCLING", "path": str(pdf), "filename": pdf.name, "document_type": "source", "parser_depth": "deep"}]
    )
    preferred_route = pipeline.parse_document_structured_content(
        [{"source_id": "SRC-DEEP-DOCLING", "path": str(pdf), "filename": pdf.name, "document_type": "source", "parser_depth": "deep", "docling_routing": {"text_digital": "preferred", "text_scientific": "preferred"}}]
    )

    assert calls["docling"] == 1
    assert standard_route["document_structured_content"][0]["pages"][0]["page_lineage"]["routed_to"] == "pymupdf_text"
    assert preferred_route["document_structured_content"][0]["pages"][0]["page_lineage"]["routed_to"] == "docling"


def test_pdf2_1_deep_failure_falls_back_and_creates_gap_for_high_impact(tmp_path, monkeypatch):
    import fitz

    pdf = tmp_path / "deep_failure.pdf"
    doc = fitz.open()
    page = doc.new_page(width=320, height=240)
    page.insert_text((30, 40), " ".join(["High impact claim evidence"] * 30), fontsize=10)
    doc.save(pdf)

    monkeypatch.setattr(
        pipeline,
        "_parse_with_docling",
        lambda *args, **kwargs: {"parser_engine": "docling", "parser_status": "error", "pages": {}, "timing_ms": 1, "confidence": "low", "error_message": "synthetic_failure"},
    )

    result = pipeline.parse_document_structured_content(
        [
            {
                "source_id": "SRC-DEEP-FAIL",
                "path": str(pdf),
                "filename": pdf.name,
                "document_type": "source",
                "parser_depth": "deep",
                "docling_routing": {"text_digital": "preferred", "text_scientific": "preferred"},
                "high_impact_claim": True,
            }
        ]
    )

    page = result["document_structured_content"][0]["pages"][0]

    assert page["page_lineage"]["routed_to"] == "pymupdf_text"
    assert result["extraction_gaps"]
    assert result["human_review_queue"]


def test_pdf2_1_lineage_records_depth_engine_timeout_and_timing(tmp_path):
    pdf = tmp_path / "depth_lineage.pdf"
    _write_structured_table_pdf(pdf)

    result = pipeline.parse_document_structured_content(
        [{"source_id": "SRC-DEPTH-LINEAGE", "path": str(pdf), "filename": pdf.name, "document_type": "source", "pipeline_stage": "evidence_appraisal"}]
    )

    lineage = result["document_parsing_lineage"][0]["page_lineage"][0]

    assert {
        "parser_depth",
        "parser_depth_reason",
        "parser_depth_status",
        "routed_engine",
        "timeout_budget_ms",
        "actual_timing_ms",
        "deep_reparse_requested",
        "deep_reparse_reason",
        "deep_reparse_attempt_count",
    }.issubset(lineage)
    assert lineage["parser_depth"] == "standard"
    assert lineage["timeout_budget_ms"] > 0


def test_pdf2_1_fast_mode_creates_no_clinical_fact_claims(tmp_path):
    pdf = tmp_path / "fast_no_facts.pdf"
    _write_structured_table_pdf(pdf)

    parsed = pipeline.parse_document_structured_content(
        [{"source_id": "SRC-FAST-NO-FACTS", "path": str(pdf), "filename": pdf.name, "document_type": "source", "pipeline_stage": "bulk_screening"}]
    )
    facts = pipeline.extract_clinical_facts({"document_structured_content": parsed["document_structured_content"], "evidence_registry": []})

    assert facts["clinical_evidence_fact_table"] == []


def test_batch_7_2_lineage_csv_exports_ocr_columns(tmp_path):
    state = _passing_state()
    state["document_parsing_lineage"] = [
        {
            "row_id": "DPL-SRC-OCR-001",
            "source_id": "SRC-OCR-001",
            "parser_used": "PyMuPDF+Camelot(lattice->stream)",
            "pages_total": 1,
            "pages_extractable": 0,
            "pages_ocr": 1,
            "tables_found": 0,
            "tables_extracted": 0,
            "ocr_recovered_content": True,
        }
    ]

    write_authoring_artifacts(tmp_path, state)
    csv_text = (tmp_path / "document_parsing_lineage.csv").read_text(encoding="utf-8")

    assert "parser_used" in csv_text
    assert "pages_ocr" in csv_text
    assert "ocr_recovered_content" in csv_text


def test_batch_7_3_pmc_fulltext_adapter_returns_native_structured_record(monkeypatch):
    def fake_fetch_json(url: str, timeout: int = 20):
        return {"esearchresult": {"count": "1", "idlist": ["12345"]}}

    def fake_fetch_text(url: str, timeout: int = 20):
        return """
        <pmc-articleset>
          <article>
            <front>
              <article-meta>
                <article-id pub-id-type="pmc">12345</article-id>
                <article-id pub-id-type="pmid">999</article-id>
                <article-id pub-id-type="doi">10.1000/pmc-test</article-id>
                <title-group><article-title>PMC full text article</article-title></title-group>
                <abstract><p>PMC abstract endpoint success.</p></abstract>
              </article-meta>
            </front>
            <body><p>PMC full text body with extractable clinical endpoint detail.</p></body>
          </article>
        </pmc-articleset>
        """

    monkeypatch.setattr(pipeline.mcp_tools, "_adapter_fetch_json", fake_fetch_json)
    monkeypatch.setattr(pipeline.mcp_tools, "_adapter_fetch_text", fake_fetch_text)

    result = pipeline.mcp_tools.call_clinical_source_adapter("pmc_fulltext_search", {"query": "ablation endpoint", "retmax": 1})
    record = result["records"][0]

    assert result["status"] == "ok"
    assert record["source_type"] == "literature_pmc_fulltext"
    assert record["source_anchor"] == "PMC:12345"
    assert record["pmid"] == "999"
    assert "full text body" in record["full_text"]
    assert record["query_signature"]


def test_batch_7_3_europe_pmc_adapter_returns_native_structured_record(monkeypatch):
    def fake_fetch_json(url: str, timeout: int = 20):
        return {
            "hitCount": 1,
            "resultList": {
                "result": [
                    {
                        "id": "EP-001",
                        "pmid": "123",
                        "doi": "10.1000/europe-pmc-test",
                        "title": "Europe PMC device abstract",
                        "abstractText": "Abstract text for a clinical device endpoint.",
                        "journalTitle": "Fixture Journal",
                        "pubYear": "2025",
                        "hasFullText": "Y",
                        "fullTextUrlList": {"fullTextUrl": [{"url": "https://example.test/fulltext"}]},
                    }
                ]
            },
        }

    monkeypatch.setattr(pipeline.mcp_tools, "_adapter_fetch_json", fake_fetch_json)

    result = pipeline.mcp_tools.call_clinical_source_adapter("europe_pmc_adapter_search", {"query": "device endpoint", "page_size": 1})
    record = result["records"][0]

    assert result["status"] == "ok"
    assert record["source_type"] == "literature_europe_pmc"
    assert record["source_anchor"] == "EUROPE_PMC:EP-001"
    assert record["has_full_text"] is True
    assert record["full_text_links"] == ["https://example.test/fulltext"]


def test_fulltext_pubmed_appraisal_fetches_pmc_full_text_and_extracts_facts(monkeypatch):
    adapter_calls: list[str] = []

    def fake_call_public(tool: str, payload: dict):
        if tool == "pubmed_fetch":
            return {"status": "ok", "articles": [{"pmid": "12345678", "title": "PADN clinical success study"}]}
        if tool == "pubmed_fetch_abstracts":
            return {"status": "ok", "articles": [{"pmid": "12345678", "abstract": "Abstract reports clinical success."}]}
        if tool == "pubmed_verify_citation":
            return {"status": "ok", "verified": True, "pmid": payload.get("pmid")}
        return {"status": "ok"}

    def fake_call_adapter(tool: str, payload: dict):
        adapter_calls.append(tool)
        if tool == "pmc_fulltext_search":
            return {
                "status": "ok",
                "database": "NCBI PMC",
                "records": [
                    {
                        "source_type": "literature_pmc_fulltext",
                        "source_anchor": "PMC:123456",
                        "source_url": "https://pmc.example.test/123456",
                        "pmid": "12345678",
                        "title": "PADN clinical success study",
                        "full_text": (
                            "Methods: prospective clinical study enrolled n=126 patients. "
                            "Results: clinical success was 87.3% (95% CI: 82.1-91.4) after 12 months follow-up."
                        ),
                    }
                ],
            }
        return {"status": "ok", "database": "Europe PMC", "records": []}

    monkeypatch.setattr(pipeline.mcp_tools, "call_public", fake_call_public)
    monkeypatch.setattr(pipeline.mcp_tools, "call_clinical_source_adapter", fake_call_adapter)
    monkeypatch.setattr(pipeline.mcp_tools, "call_tool", lambda *args, **kwargs: {"status": "ok", "cebm_level": "Level 4"})
    monkeypatch.setattr(pipeline.mcp_tools, "mcp_log_entry", lambda result, name: {"tool": name, "status": result.get("status")})

    state = _passing_state()
    state.pop("evidence_registry", None)
    state.pop("article_appraisal", None)
    state["screening_disposition"] = [
        {
            "article_id": "ART-001",
            "pmid": "12345678",
            "full_text_decision": "include_for_appraisal",
            "retrieval_domain_status": "DOMAIN_MATCH_HIGH",
            "endpoint_match": "high",
        }
    ]
    state["raw_literature_records"] = [{"article_id": "ART-001", "pmid": "12345678", "search_id": "SEARCH-SOTA-01"}]

    result = pipeline.appraise_evidence(state)

    assert adapter_calls == ["pmc_fulltext_search"]
    assert result["fulltext_acquisition_status_table"][0]["full_text_retrieval_status"] == "full_text_available"
    assert result["fulltext_acquisition_status_table"][0]["full_text_source_anchor"] == "PMC:123456"
    assert result["document_structured_content"][0]["evidence_id"] == "E-001"
    assert result["clinical_evidence_fact_table"]
    assert result["clinical_evidence_fact_table"][0]["evidence_id"] == "E-001"
    assert result["evidence_registry"][0]["evidence_strength_score"] is not None


def test_fulltext_pubmed_appraisal_falls_back_to_europe_pmc_when_pmc_has_no_body(monkeypatch):
    adapter_calls: list[str] = []

    def fake_call_public(tool: str, payload: dict):
        if tool == "pubmed_fetch":
            return {"status": "ok", "articles": [{"pmid": "87654321", "title": "Abstract only source"}]}
        if tool == "pubmed_fetch_abstracts":
            return {"status": "ok", "articles": [{"pmid": "87654321", "abstract": "Structured abstract only."}]}
        if tool == "pubmed_verify_citation":
            return {"status": "ok", "verified": True, "pmid": payload.get("pmid")}
        return {"status": "ok"}

    def fake_call_adapter(tool: str, payload: dict):
        adapter_calls.append(tool)
        if tool == "pmc_fulltext_search":
            return {"status": "ok", "database": "NCBI PMC", "records": []}
        return {
            "status": "ok",
            "database": "Europe PMC",
            "records": [
                {
                    "source_type": "literature_europe_pmc",
                    "source_anchor": "EUROPE_PMC:87654321",
                    "pmid": "87654321",
                    "abstract": "Europe PMC abstract.",
                    "has_full_text": True,
                    "full_text_links": ["https://example.test/fulltext"],
                }
            ],
        }

    monkeypatch.setattr(pipeline.mcp_tools, "call_public", fake_call_public)
    monkeypatch.setattr(pipeline.mcp_tools, "call_clinical_source_adapter", fake_call_adapter)
    monkeypatch.setattr(pipeline.mcp_tools, "call_tool", lambda *args, **kwargs: {"status": "ok", "cebm_level": "Level 5"})
    monkeypatch.setattr(pipeline.mcp_tools, "mcp_log_entry", lambda result, name: {"tool": name, "status": result.get("status")})

    state = _passing_state()
    state.pop("evidence_registry", None)
    state.pop("article_appraisal", None)
    state["screening_disposition"] = [
        {
            "article_id": "ART-001",
            "pmid": "87654321",
            "full_text_decision": "include_for_appraisal",
            "retrieval_domain_status": "DOMAIN_MATCH_HIGH",
        }
    ]
    state["raw_literature_records"] = [{"article_id": "ART-001", "pmid": "87654321", "search_id": "SEARCH-SOTA-01"}]

    result = pipeline.appraise_evidence(state)
    row = result["fulltext_acquisition_status_table"][0]

    assert adapter_calls == ["pmc_fulltext_search", "europe_pmc_adapter_search"]
    assert row["full_text_retrieval_status"] == "abstract_only"
    assert row["full_text_available"] == "no"
    assert "https://example.test/fulltext" in row["full_text_links"]
    assert result["clinical_evidence_fact_table"] == []


def test_batch_7_3_clinicaltrials_adapter_maps_results_and_device_relationship(monkeypatch):
    def fake_fetch_json(url: str, timeout: int = 20):
        return {
            "totalCount": 1,
            "studies": [
                {
                    "protocolSection": {
                        "identificationModule": {
                            "nctId": "NCT12345678",
                            "briefTitle": "Pulnovo PADN catheter trial",
                            "officialTitle": "Pulmonary artery denervation catheter clinical study",
                        },
                        "statusModule": {"completionDateStruct": {"date": "2025-01"}},
                        "designModule": {"studyType": "Interventional", "phases": ["NA"], "enrollmentInfo": {"count": 100}},
                        "conditionsModule": {"conditions": ["Pulmonary Arterial Hypertension"]},
                        "armsInterventionsModule": {"interventions": [{"type": "DEVICE", "name": "PADN catheter"}]},
                        "outcomesModule": {"primaryOutcomes": [{"measure": "mPAP"}]},
                    },
                    "resultsSection": {
                        "outcomeMeasuresModule": {
                            "outcomeMeasures": [{"title": "mPAP reduction", "unitOfMeasure": "mmHg", "groups": [{"value": "-8"}]}]
                        },
                        "adverseEventsModule": {"seriousEvents": [{"term": "Serious adverse event", "stats": [{"numEvents": 1}]}]},
                    },
                }
            ],
        }

    monkeypatch.setattr(pipeline.mcp_tools, "_adapter_fetch_json", fake_fetch_json)

    result = pipeline.mcp_tools.call_clinical_source_adapter(
        "clinicaltrials_gov_adapter_search",
        {
            "query": "PADN catheter",
            "page_size": 1,
            "target_keywords": ["Pulnovo", "PADN"],
            "device_profile": {"device_name": "Pulnovo PADN catheter", "device_type": "radiofrequency ablation catheter"},
        },
    )
    record = result["records"][0]

    assert result["status"] == "ok"
    assert record["source_type"] == "clinical_trial_record"
    assert record["source_anchor"] == "NCT12345678"
    assert record["results_status"] == "RESULTS_AVAILABLE"
    assert {fact["fact_type"] for fact in record["result_facts"]} == {"primary_or_secondary_outcome", "serious_adverse_event"}
    assert record["device_relationship"] == "subject"
    assert "sponsor is not used" in record["relationship_rationale"]


def test_batch_7_3_clinical_source_adapter_records_enter_screening_pipeline(monkeypatch):
    adapter_records = {
        "pmc_fulltext_search": {
            "source_type": "literature_pmc_fulltext",
            "record_id": "PMC12345",
            "stable_record_id": "NCBI PMC:PMC12345",
            "source_anchor": "PMC:12345",
            "title": "PMC full text record",
            "abstract": "PMC abstract.",
            "full_text": "PMC full text.",
        },
        "europe_pmc_adapter_search": {
            "source_type": "literature_europe_pmc",
            "record_id": "EP-001",
            "stable_record_id": "Europe PMC:EP-001",
            "source_anchor": "EUROPE_PMC:EP-001",
            "title": "Europe PMC record",
            "abstract": "Europe PMC abstract.",
        },
        "clinicaltrials_gov_adapter_search": {
            "source_type": "clinical_trial_record",
            "record_id": "NCT12345678",
            "stable_record_id": "ClinicalTrials.gov:NCT12345678",
            "source_anchor": "NCT12345678",
            "title": "Clinical trial record",
            "abstract": "Clinical trial abstract.",
            "device_relationship": "similar",
        },
    }

    def fake_call_public(tool: str, payload: dict):
        return {
            "status": "ok",
            "database": tool,
            "query": payload.get("query"),
            "search_date": "2026-05-12",
            "count": 0,
            "returned_count": 0,
            "records": [],
            "pmids": [],
        }

    def fake_call_adapter(tool: str, payload: dict):
        record = dict(adapter_records[tool])
        record.update(
            {
                "source_db": {
                    "pmc_fulltext_search": "NCBI PMC",
                    "europe_pmc_adapter_search": "Europe PMC",
                    "clinicaltrials_gov_adapter_search": "ClinicalTrials.gov",
                }[tool],
                "retrieval_timestamp": "2026-05-12T00:00:00+00:00",
                "query_signature": "fixture-query",
            }
        )
        return {
            "status": "ok",
            "database": record["source_db"],
            "adapter": tool,
            "query": payload.get("query"),
            "search_date": "2026-05-12",
            "count": 1,
            "returned_count": 1,
            "records": [record],
        }

    monkeypatch.setattr(pipeline.mcp_tools, "call_public", fake_call_public)
    monkeypatch.setattr(pipeline.mcp_tools, "call_clinical_source_adapter", fake_call_adapter)
    monkeypatch.setattr(pipeline.mcp_tools, "mcp_log_entry", lambda result, name: {"tool": result.get("mcp_tool"), "status": result.get("status")})
    state = _passing_state()
    state.pop("sota_benchmark_matrix", None)
    state.pop("search_run_registry", None)
    state.pop("screening_disposition", None)
    state.pop("pmid_screening_and_exclusion_table", None)
    state.pop("sota_screening_disposition_table", None)

    search_result = pipeline.run_sota_search(state)
    source_types = {row.get("source_type") for row in search_result["raw_literature_records"]}
    screened = pipeline.screen_literature({**state, **search_result})
    disposition_source_types = {row.get("source_type") for row in screened["screening_disposition"]}

    assert {"literature_pmc_fulltext", "literature_europe_pmc", "clinical_trial_record"} <= source_types
    assert len(search_result["clinical_source_adapter_records"]) == 6
    assert all(row["records_enter_screening_pipeline"] is True for row in search_result["clinical_source_adapter_lineage"])
    assert {"literature_pmc_fulltext", "literature_europe_pmc", "clinical_trial_record"} <= disposition_source_types


def test_mcp_search_router_records_source_unavailable_as_reproducible_database_rows(monkeypatch):
    def fake_call_public(tool: str, payload: dict):
        return {
            "status": "source_unavailable",
            "error_type": "ConnectionError",
            "message": f"{tool} unavailable in fixture",
            "_mcp": {"server": "cer-public-evidence", "tool": tool, "status": "source_unavailable", "arguments": payload, "elapsed_ms": 1},
        }

    def fake_call_adapter(tool: str, payload: dict):
        return {
            "status": "source_unavailable",
            "error_type": "ConnectionError",
            "message": f"{tool} unavailable in fixture",
            "_mcp": {"server": "cer-clinical-source-adapters", "tool": tool, "status": "source_unavailable", "arguments": payload, "elapsed_ms": 1},
        }

    monkeypatch.setattr(pipeline.mcp_tools, "call_public", fake_call_public)
    monkeypatch.setattr(pipeline.mcp_tools, "call_clinical_source_adapter", fake_call_adapter)

    state = _passing_state()
    state.pop("sota_benchmark_matrix", None)
    state.pop("search_run_registry", None)
    result = pipeline.run_sota_search(state)
    registry = result["search_run_registry"]
    by_database = {row["database"]: row for row in registry}

    assert by_database["NCBI PMC"]["status"] == "source_unavailable"
    assert by_database["NCBI PMC"]["result_count"] is None
    assert "unavailable" in by_database["NCBI PMC"]["error_message"]
    assert by_database["Europe PMC"]["status"] == "source_unavailable"
    assert by_database["ClinicalTrials.gov"]["status"] == "source_unavailable"
    assert all(row.get("query") and row.get("search_date") for row in registry)
    assert any(row["database"] == "ClinicalTrials.gov" for row in result["database_search_source_table"])


def test_mcp_search_router_invokes_clinicaltrials_public_tool_for_g17_compatibility(monkeypatch):
    public_calls = []

    def fake_call_public(tool: str, payload: dict):
        public_calls.append(tool)
        return {
            "status": "ok",
            "database": "ClinicalTrials.gov" if tool == "clinicaltrials_search" else "PubMed",
            "query": payload.get("query"),
            "search_date": "2026-05-13",
            "count": 0,
            "returned_count": 0,
            "records": [],
            "pmids": [],
            "_mcp": {"server": "cer-public-evidence", "tool": tool, "status": "ok", "arguments": payload, "elapsed_ms": 1},
        }

    def fake_call_adapter(tool: str, payload: dict):
        return {
            "status": "ok",
            "database": {
                "pmc_fulltext_search": "NCBI PMC",
                "europe_pmc_adapter_search": "Europe PMC",
                "clinicaltrials_gov_adapter_search": "ClinicalTrials.gov",
            }[tool],
            "query": payload.get("query"),
            "search_date": "2026-05-13",
            "count": 0,
            "returned_count": 0,
            "records": [],
            "_mcp": {"server": "cer-clinical-source-adapters", "tool": tool, "status": "ok", "arguments": payload, "elapsed_ms": 1},
        }

    monkeypatch.setattr(pipeline.mcp_tools, "call_public", fake_call_public)
    monkeypatch.setattr(pipeline.mcp_tools, "call_clinical_source_adapter", fake_call_adapter)

    state = _passing_state()
    state.pop("sota_benchmark_matrix", None)
    state.pop("search_run_registry", None)
    result = pipeline.run_sota_search(state)
    public_log_tools = {
        (row.get("server"), row.get("tool"))
        for row in result["mcp_call_log"]
        if row.get("server") == "cer-public-evidence"
    }

    assert "clinicaltrials_search" in public_calls
    assert ("cer-public-evidence", "clinicaltrials_search") in public_log_tools
    assert any(row["database"] == "ClinicalTrials.gov" for row in result["search_run_registry"])


def test_clinicaltrials_direct_api_fallback_satisfies_g17_compatibility(monkeypatch):
    def fake_call_public(tool: str, payload: dict):
        if tool == "clinicaltrials_search":
            return {
                "status": "source_unavailable",
                "database": "ClinicalTrials.gov",
                "query": payload.get("query"),
                "search_date": "2026-05-14",
                "count": None,
                "returned_count": 0,
                "records": [],
                "message": "MCP server unavailable in fixture",
                "_mcp": {"server": "cer-public-evidence", "tool": tool, "status": "source_unavailable", "arguments": payload, "elapsed_ms": 1},
            }
        return {
            "status": "ok",
            "database": "PubMed",
            "query": payload.get("query"),
            "search_date": "2026-05-14",
            "count": 0,
            "returned_count": 0,
            "records": [],
            "pmids": [],
            "_mcp": {"server": "cer-public-evidence", "tool": tool, "status": "ok", "arguments": payload, "elapsed_ms": 1},
        }

    def fake_call_adapter(tool: str, payload: dict):
        if tool == "clinicaltrials_gov_adapter_search":
            return {
                "status": "ok",
                "database": "ClinicalTrials.gov",
                "adapter": tool,
                "query": payload.get("query"),
                "search_date": "2026-05-14",
                "url": "https://clinicaltrials.gov/api/v2/studies?query.term=fixture",
                "count": 2,
                "returned_count": 1,
                "records": [{"source_type": "clinical_trial_record", "source_anchor": "NCT12345678"}],
                "_mcp": {"server": "cer-clinical-source-adapters", "tool": tool, "status": "ok", "arguments": payload, "elapsed_ms": 1},
            }
        return {
            "status": "ok",
            "database": {"pmc_fulltext_search": "NCBI PMC", "europe_pmc_adapter_search": "Europe PMC"}[tool],
            "adapter": tool,
            "query": payload.get("query"),
            "search_date": "2026-05-14",
            "count": 0,
            "returned_count": 0,
            "records": [],
            "_mcp": {"server": "cer-clinical-source-adapters", "tool": tool, "status": "ok", "arguments": payload, "elapsed_ms": 1},
        }

    monkeypatch.setattr(pipeline.mcp_tools, "call_public", fake_call_public)
    monkeypatch.setattr(pipeline.mcp_tools, "call_clinical_source_adapter", fake_call_adapter)

    state = _passing_state()
    state.pop("sota_benchmark_matrix", None)
    state.pop("search_run_registry", None)
    result = pipeline.run_sota_search(state)
    clinical_logs = [
        row
        for row in result["mcp_call_log"]
        if row.get("server") == "cer-public-evidence" and row.get("tool") == "clinicaltrials_search"
    ]
    clinical_registry = [row for row in result["search_run_registry"] if row.get("database") == "ClinicalTrials.gov"]
    gate_state = _passing_state()
    gate_state["mcp_call_log"] = [
        *(row for row in gate_state["mcp_call_log"] if not (row.get("server") == "cer-public-evidence" and row.get("tool") == "clinicaltrials_search")),
        clinical_logs[0],
    ]
    report = run_authoring_gates(gate_state)

    assert clinical_logs
    assert clinical_logs[0]["status"] == "warning"
    assert clinical_registry[0]["status"] == "ok"
    assert clinical_registry[0]["hit_count"] == 2
    assert clinical_registry[0]["url"].startswith("https://clinicaltrials.gov")
    assert next(item for item in report["results"] if item["gate_id"] == "G17")["status"] == "PASS"


def test_validate_language_local_language_fallback_satisfies_g17(monkeypatch):
    def fake_call_tool(server: str, tool: str, arguments: dict, timeout: int | None = None):
        if tool == "validate_language":
            return {
                "status": "source_unavailable",
                "message": "nb-check unavailable in fixture",
                "_mcp": {"server": server, "tool": tool, "status": "source_unavailable", "arguments": arguments, "elapsed_ms": 1},
            }
        return {
            "status": "ok",
            "_mcp": {"server": server, "tool": tool, "status": "ok", "arguments": arguments, "elapsed_ms": 1},
        }

    monkeypatch.setattr(pipeline.mcp_tools, "call_tool", fake_call_tool)
    state = _passing_state()
    state["clinical_evidence_fact_table"] = [{"fact_id": "FACT-LANG-001", "evidence_id": "E-001", "source_language": "zh"}]
    result = pipeline.build_nb_precheck_report(state)
    language_log = next(row for row in result["mcp_call_log"] if row.get("tool") == "validate_language")
    gate_state = _passing_state()
    gate_state["mcp_call_log"] = [*gate_state["mcp_call_log"], language_log]
    report = run_authoring_gates(gate_state)

    assert language_log["status"] == "warning"
    assert result["mcp_tool_results"]["nb_check_language"]["equivalent_local_fallback"] is True
    assert next(item for item in report["results"] if item["gate_id"] == "G17")["status"] == "PASS"


def test_pending_evidence_placeholders_are_landed_as_retrieval_gaps_not_g6_numeric_failures():
    state = _passing_state()
    state["evidence_registry"] = pipeline._mark_pending_evidence_records(
        [
            {
                "evidence_id": "EVIDENCE_PENDING_SRC-IFU-001",
                "source_type": "EVIDENCE_PENDING_SRC-IFU",
                "source_anchor": "pending IFU endpoint extraction",
            }
        ]
    )
    state.update(pipeline.build_gap_pmcf_recommendations(state))
    report = run_authoring_gates(state)

    pending = state["evidence_registry"][0]
    assert pending["retrieval_gap"] is True
    assert pending["evidence_limitation_category"] == "pending_source_placeholder"
    assert any(row["gap_id"].startswith("GAP-EVIDENCE-PENDING") for row in state["gap_pmcf_recommendations"])
    assert next(item for item in report["results"] if item["gate_id"] == "G6")["status"] == "PASS"


def test_phase7_pico_queries_use_current_device_profile_not_ifu_placeholder_terms():
    state = _passing_state()
    state["target_keywords"] = ["IFU-defined cardiovascular target anatomy", "PADN RF ablation catheter"]
    state["device_profile"] = {
        "device_name": "PADN Radiofrequency Ablation Catheter",
        "device_type": "radiofrequency ablation catheter",
        "clinical_domain": "cardiovascular_rf_ablation_catheter",
        "anatomical_site": "pulmonary artery nerve plexus",
        "mode_of_action": "Radiofrequency ablation for pulmonary artery denervation",
        "intended_purpose": "Pulmonary artery denervation by radiofrequency ablation.",
    }
    rows = pipeline._phase7_search_plan(state["device_profile"], state)
    queries = " ".join(str(row.get("query_string") or "") for row in rows)

    assert "IFU-defined cardiovascular target anatomy" not in queries
    assert "pulmonary artery nerve plexus" in queries or "PADN Radiofrequency Ablation Catheter" in queries


def test_batch_7_4_extracts_clinical_facts_from_parsed_text_and_tables():
    state = _passing_state()
    state["claim_ledger"] = [
        {"claim_id": "C-SAFETY", "claim_type": "safety", "statement": "Device has acceptable adverse event profile."},
        {"claim_id": "C-PERF", "claim_type": "performance", "statement": "Device supports procedural success."},
    ]
    state["evidence_registry"] = [{"evidence_id": "E-DOC-001", "source_id": "SRC-PDF-001", "weight": "supportive"}]
    state["document_structured_content"] = [
        {
            "document_id": "DOC-SRC-PDF-001",
            "source_id": "SRC-PDF-001",
            "pages": [
                {
                    "page_number": 2,
                    "headings": [],
                    "paragraphs": [
                        {
                            "block_id": "B-001",
                            "text": "Clinical success was 95% in N=100 patients at 30 days compared with standard practice.",
                        }
                    ],
                    "tables": [
                        {
                            "table_id": "SRC-PDF-001-T001",
                            "page_number": 2,
                            "cells": [
                                ["Endpoint", "N", "Result", "Follow-up"],
                                ["Serious adverse events", "100", "1 events", "30 days"],
                            ],
                        }
                    ],
                }
            ],
        }
    ]

    result = pipeline.extract_clinical_facts(state)
    facts = result["clinical_evidence_fact_table"]
    by_method = {row["extraction_method"]: row for row in facts}

    assert len(facts) == 2
    assert by_method["direct_text"]["evidence_id"] == "E-DOC-001"
    assert by_method["direct_text"]["endpoint_family"] == "procedural_success"
    assert by_method["direct_text"]["value_numeric"] == 95
    assert by_method["direct_text"]["value_unit"] == "%"
    assert by_method["table_cell"]["endpoint_family"] == "safety"
    assert by_method["table_cell"]["population_n"] == "100"
    assert by_method["table_cell"]["source_table"] == "SRC-PDF-001-T001"


def test_batch_7_4_confidence_is_gated_by_method_and_validators():
    state = {
        "claim_ledger": [{"claim_id": "C-PERF", "claim_type": "performance", "statement": "success rate"}],
        "evidence_registry": [{"evidence_id": "E-DOC-001", "source_id": "SRC-PDF-001"}],
        "document_structured_content": [
            {
                "document_id": "DOC-SRC-PDF-001",
                "source_id": "SRC-PDF-001",
                "pages": [
                    {
                        "page_number": 1,
                        "headings": [],
                        "paragraphs": [{"text": "Clinical success was 150% in N=100 patients."}],
                        "tables": [],
                    }
                ],
            }
        ],
    }

    fact = pipeline.extract_clinical_facts(state)["clinical_evidence_fact_table"][0]

    assert fact["extraction_method"] == "direct_text"
    assert fact["method_confidence"] == "high"
    assert fact["numeric_sanity"] == "medium"
    assert fact["extraction_confidence"] == "medium"


def test_batch_7_4_bilingual_fact_preserves_original_excerpt_and_flags_translation():
    state = {
        "claim_ledger": [{"claim_id": "C-SAFETY", "claim_type": "safety", "statement": "adverse events"}],
        "evidence_registry": [{"evidence_id": "E-DOC-001", "source_id": "SRC-CN-001"}],
        "document_structured_content": [
            {
                "document_id": "DOC-SRC-CN-001",
                "source_id": "SRC-CN-001",
                "pages": [
                    {
                        "page_number": 3,
                        "headings": [],
                        "paragraphs": [{"text": "不良事件发生率为2%，样本量N=100。"}],
                        "tables": [],
                    }
                ],
            }
        ],
    }

    result = pipeline.extract_clinical_facts(state)
    fact = result["clinical_evidence_fact_table"][0]

    assert fact["source_language"] == "zh"
    assert fact["endpoint_label"] == "adverse events"
    assert fact["original_excerpt"] == "不良事件发生率为2%，样本量N=100。"
    assert "TRANSLATION_NEEDED" in fact["extraction_flags"]
    assert result["human_review_queue"][0]["flag"] == "TRANSLATION_NEEDED"


def test_batch_7_4_artifact_export_includes_clinical_evidence_fact_table(tmp_path):
    state = _passing_state()
    state["clinical_evidence_fact_table"] = [
        {
            "fact_id": "FACT-001",
            "evidence_id": "E-001",
            "endpoint_family": "procedural_success",
            "endpoint_label": "clinical success",
            "value_numeric": 95,
            "value_unit": "%",
            "extraction_confidence": "high",
        }
    ]

    written = write_authoring_artifacts(tmp_path, state)
    workbook = json.loads((tmp_path / "authoring_workbook.json").read_text(encoding="utf-8"))
    names = {Path(path).name for path in written}

    assert "clinical_evidence_fact_table.xlsx" in names
    assert workbook["clinical_evidence_fact_table"][0]["fact_id"] == "FACT-001"


def test_batch_7_5_semantic_endpoint_mapping_high_confidence_and_trace():
    state = {
        "claim_ledger": [{"claim_id": "C-PERF", "claim_type": "performance", "statement": "clinical success endpoint"}],
        "clinical_evidence_fact_table": [
            {
                "fact_id": "FACT-001",
                "evidence_id": "E-001",
                "endpoint_family": "procedural_success",
                "endpoint_label": "clinical success",
                "value_type": "rate",
                "value_numeric": 95,
                "value_unit": "%",
                "population_n": "100",
                "follow_up": "30 days",
                "source_excerpt": "Clinical success was 95% in N=100 patients at 30 days.",
            }
        ],
    }

    result = pipeline.map_semantic_endpoints(state)
    mapped = result["clinical_evidence_fact_table"][0]
    mapping = result["semantic_endpoint_mapping_table"][0]
    trace = result["endpoint_match_trace"]["mappings"][0]

    assert mapped["endpoint_family"] == "effectiveness"
    assert mapped["mapping_confidence"] == "high"
    assert mapped["normalized_value"] == 0.95
    assert result["fact_to_claim_link_matrix"][0]["claim_id"] == "C-PERF"
    assert mapping["embedding_model"] == "deerflow-deterministic-endpoint-mapper-v1"
    assert "endpoint_definition" in mapping["match_dimensions"]
    assert trace["endpoint_match_trace"]["confidence_rule"]


def test_batch_7_5_quantitative_normalization_failure_goes_to_review_queue():
    state = {
        "claim_ledger": [{"claim_id": "C-PERF", "claim_type": "performance", "statement": "clinical success"}],
        "clinical_evidence_fact_table": [
            {
                "fact_id": "FACT-001",
                "evidence_id": "E-001",
                "endpoint_family": "effectiveness",
                "endpoint_label": "clinical success",
                "value_type": "rate",
                "value_numeric": "not extracted",
                "value_unit": "%",
                "source_excerpt": "Clinical success reported narratively without extractable value.",
            }
        ],
    }

    result = pipeline.map_semantic_endpoints(state)
    fact = result["clinical_evidence_fact_table"][0]

    assert fact["normalizer_status"] == "needs_human_review"
    assert result["human_review_queue"][0]["flag"] == "QUANTITATIVE_NORMALIZATION_FAILED"


def test_batch_7_5_clinicaltrials_record_with_results_creates_evidence_and_facts():
    state = {
        "device_profile": {"device_name": "PADN catheter", "device_type": "radiofrequency ablation catheter"},
        "target_keywords": ["PADN"],
        "claim_ledger": [{"claim_id": "C-BEN", "claim_type": "clinical_benefit", "statement": "hemodynamic improvement"}],
        "raw_literature_records": [
            {
                "article_id": "ART-TRIAL-001",
                "source_type": "clinical_trial_record",
                "source_anchor": "NCT12345678",
                "record_id": "NCT12345678",
                "title": "PADN catheter trial",
                "abstract": "PADN catheter for pulmonary arterial hypertension",
                "results_status": "RESULTS_AVAILABLE",
                "enrollment": 100,
                "completion_date": "2025-01",
                "study_type": "Interventional",
                "intervention_names": ["PADN catheter"],
                "result_facts": [
                    {"fact_type": "primary_or_secondary_outcome", "endpoint": "mPAP reduction", "value": "-8", "unit": "mmHg", "extraction_confidence": "high"},
                    {"fact_type": "serious_adverse_event", "endpoint": "Serious adverse event", "value": "1", "unit": "events", "extraction_confidence": "high"},
                ],
            }
        ],
    }

    result = pipeline.appraise_evidence(state)
    trial_evidence = [row for row in result["evidence_registry"] if row.get("source_type") == "clinical_trial_record"]
    trial_facts = [row for row in result["clinical_evidence_fact_table"] if row.get("source_anchor") == "NCT12345678"]

    assert len(trial_evidence) == 1
    assert trial_evidence[0]["source_anchor"] == "NCT12345678"
    assert trial_evidence[0]["device_relationship"] == "subject"
    assert "sponsor was not used" in trial_evidence[0]["relationship_rationale"]
    assert len(trial_facts) == 2
    assert {row["extraction_confidence"] for row in trial_facts} == {"high"}


def test_batch_7_5_clinicaltrials_no_results_does_not_create_fact():
    state = {
        "raw_literature_records": [
            {
                "article_id": "ART-TRIAL-001",
                "source_type": "clinical_trial_record",
                "source_anchor": "NCT00000000",
                "record_id": "NCT00000000",
                "title": "Trial without posted results",
                "results_status": "NO_RESULTS_AVAILABLE",
                "result_facts": [],
            }
        ],
    }

    result = pipeline.appraise_evidence(state)

    assert all(row.get("source_anchor") != "NCT00000000" for row in result["evidence_registry"])
    assert result["clinical_evidence_fact_table"] == []


def test_batch_7_5_conflict_detection_flags_directional_critical_and_claim_impact():
    state = {
        "fact_to_claim_link_matrix": [
            {"fact_id": "FACT-001", "claim_id": "C-SAFE"},
            {"fact_id": "FACT-002", "claim_id": "C-SAFE"},
        ],
        "clinical_evidence_fact_table": [
            {
                "fact_id": "FACT-001",
                "evidence_id": "E-001",
                "endpoint_cluster_id": "ENDPOINT-CLUSTER-SAE",
                "endpoint_family": "safety",
                "endpoint_label": "serious adverse events",
                "normalized_value": 0.01,
                "source_excerpt": "Serious adverse events 1%.",
            },
            {
                "fact_id": "FACT-002",
                "evidence_id": "E-002",
                "endpoint_cluster_id": "ENDPOINT-CLUSTER-SAE",
                "endpoint_family": "safety",
                "endpoint_label": "serious adverse events",
                "normalized_value": 0.20,
                "source_excerpt": "Serious adverse events 20%.",
            },
        ],
    }

    result = pipeline.detect_evidence_conflicts(state)
    conflict = result["evidence_conflict_report"]["conflicts"][0]

    assert conflict["conflict_type"] == "DIRECTIONAL"
    assert conflict["conflict_scope"] == "semantic"
    assert conflict["severity"] == "CRITICAL"
    assert result["evidence_conflict_report"]["claim_impacts"][0]["claim_id"] == "C-SAFE"
    assert result["human_review_queue"][0]["impact"] == "BLOCKING"


def test_conflict_generator_marks_unlinked_pairwise_records_as_entity_level():
    state = {
        "clinical_evidence_fact_table": [
            {
                "fact_id": "FACT-001",
                "evidence_id": "E-001",
                "endpoint_cluster_id": "ENDPOINT-CLUSTER-SAE",
                "endpoint_family": "safety",
                "endpoint_label": "serious adverse events",
                "normalized_value": 0.01,
                "source_excerpt": "Serious adverse events 1%.",
            },
            {
                "fact_id": "FACT-002",
                "evidence_id": "E-002",
                "endpoint_cluster_id": "ENDPOINT-CLUSTER-SAE",
                "endpoint_family": "safety",
                "endpoint_label": "serious adverse events",
                "normalized_value": 0.20,
                "source_excerpt": "Serious adverse events 20%.",
            },
        ],
    }

    result = pipeline.detect_evidence_conflicts(state)
    conflict = result["evidence_conflict_report"]["conflicts"][0]

    assert conflict["conflict_type"] == "DIRECTIONAL"
    assert conflict["conflict_scope"] == "entity_level"
    assert pipeline._is_entity_level_conflict_record(conflict) is True
    phase4 = pipeline.build_ei_core_phase4_audit_review(
        {
            "claim_ledger": [{"claim_id": "C-1", "claim_type": "safety_clinical"}],
            "risk_trace_matrix": [{"risk_id": "R-1"}],
            "evidence_registry": [_ei_evidence("E-001"), _ei_evidence("E-002")],
            "clinical_evidence_fact_table": state["clinical_evidence_fact_table"],
            "claim_support_matrix": {"C-1": {"claim_id": "C-1", "support_level": "STRONG"}},
            "benefit_risk_conclusion": {"overall_judgment": "favorable", "br_acceptability_confidence": "high"},
            "pmcf_gap_register": [],
            "evidence_conflict_report": result["evidence_conflict_report"],
        }
    )

    assert not any(packet["trigger"] in {"critical_conflict", "high_conflict"} for packet in phase4["human_review_packet"])
    assert phase4["human_review_packet_filtering_summary"]["filtered_out_count"] > 0


def test_conflict_generator_aggregates_same_cluster_semantic_pairwise_conflicts():
    facts = [
        {
            "fact_id": f"FACT-{idx:03d}",
            "evidence_id": f"E-{idx:03d}",
            "endpoint_cluster_id": "ENDPOINT-CLUSTER-SUCCESS",
            "endpoint_family": "effectiveness",
            "endpoint_label": "clinical success",
            "normalized_value": value,
            "source_excerpt": f"Clinical success was {value}%.",
        }
        for idx, value in enumerate([1, 3, 9, 27], start=1)
    ]
    state = {
        "fact_to_claim_link_matrix": [{"fact_id": fact["fact_id"], "claim_id": "C-PERF"} for fact in facts],
        "clinical_evidence_fact_table": facts,
    }

    result = pipeline.detect_evidence_conflicts(state)
    conflicts = result["evidence_conflict_report"]["conflicts"]
    summary = result["evidence_conflict_report"]["generation_summary"]

    assert len(conflicts) == 1
    assert conflicts[0]["conflict_scope"] == "semantic"
    assert conflicts[0]["conflict_type"] == "MAGNITUDE"
    assert conflicts[0]["comparison_count"] == 6
    assert conflicts[0]["claim_ids"] == ["C-PERF"]
    assert summary["pairwise_conflicts_detected"] == 6
    assert summary["emitted_conflict_records"] == 1
    assert summary["aggregated_pairwise_conflicts"] == 5


def test_conflict_generator_aggregates_same_cluster_entity_level_pairwise_conflicts():
    facts = [
        {
            "fact_id": f"FACT-E-{idx:03d}",
            "evidence_id": f"E-{idx:03d}",
            "endpoint_cluster_id": "ENDPOINT-CLUSTER-SUCCESS",
            "endpoint_family": "effectiveness",
            "endpoint_label": "clinical success",
            "normalized_value": value,
            "source_excerpt": f"Clinical success was {value}%.",
        }
        for idx, value in enumerate([1, 3, 9, 27], start=1)
    ]

    result = pipeline.detect_evidence_conflicts({"clinical_evidence_fact_table": facts})
    conflicts = result["evidence_conflict_report"]["conflicts"]
    summary = result["evidence_conflict_report"]["generation_summary"]

    assert len(conflicts) == 1
    assert conflicts[0]["conflict_scope"] == "entity_level"
    assert conflicts[0]["comparison_count"] == 6
    assert summary["conflict_scope_counts"]["entity_level"] == 1
    assert summary["aggregated_pairwise_conflicts"] == 5


def test_batch_7_5_critical_conflict_caps_pivotal_evidence_to_supportive():
    evidence = [
        {"evidence_id": "E-001", "weight": "pivotal"},
        {"evidence_id": "E-002", "weight": "supportive"},
    ]
    report = {
        "conflicts": [
            {
                "conflict_id": "CONF-001",
                "severity": "CRITICAL",
                "evidence_ids": ["E-001", "E-002"],
            }
        ]
    }

    capped = pipeline._apply_conflict_caps_to_evidence(evidence, report)

    assert capped[0]["weight"] == "supportive"
    assert capped[0]["conflict_role_cap"] == "supportive"
    assert capped[1]["conflict_role_cap"] == "supportive"


def test_batch_7_5_artifact_export_includes_mapping_and_conflict_outputs(tmp_path):
    state = _passing_state()
    state["semantic_endpoint_mapping_table"] = [{"mapping_id": "SEM-001", "fact_id": "FACT-001", "mapping_confidence": "high"}]
    state["endpoint_match_trace"] = {"mappings": [{"mapping_id": "SEM-001"}]}
    state["fact_to_claim_link_matrix"] = [{"link_id": "FCL-001", "fact_id": "FACT-001", "claim_id": "C-01"}]
    state["evidence_conflict_report"] = {"conflict_count": 1, "conflicts": [{"conflict_id": "CONF-001"}]}

    written = write_authoring_artifacts(tmp_path, state)
    names = {Path(path).name for path in written}

    assert "semantic_endpoint_mapping_table.csv" in names
    assert "endpoint_match_trace.json" in names
    assert "fact_to_claim_link_matrix.xlsx" in names
    assert "evidence_conflict_report.json" in names
    assert json.loads((tmp_path / "endpoint_match_trace.json").read_text(encoding="utf-8"))["mappings"][0]["mapping_id"] == "SEM-001"


def test_batch_7_6_fact_confidence_high_makes_evidence_pivotal_eligible_without_upgrade():
    evidence = [{"evidence_id": "E-001", "weight": "supportive", "ledger_approved_for_writer": True}]
    appraisals = [{"evidence_id": "E-001", "weight": "supportive"}]
    facts = [{"fact_id": "FACT-001", "evidence_id": "E-001", "extraction_confidence": "high"}]

    result = pipeline._aggregate_fact_confidence_to_evidence(evidence, appraisals, facts, {"conflicts": []})
    row = result["evidence_registry"][0]

    assert row["weight"] == "supportive"
    assert row["fact_role_cap"] == "pivotal_eligible"
    assert row["g42_fact_signal"] == "pivotal_eligible"
    assert result["article_appraisal"][0]["fact_confidence_signal"] == "FACT_HIGH_CONFIDENCE_PIVOTAL_ELIGIBLE"


def test_batch_7_6_medium_low_facts_cap_pivotal_evidence_to_supportive():
    evidence = [{"evidence_id": "E-001", "weight": "pivotal", "ledger_approved_for_writer": True}]
    facts = [
        {"fact_id": "FACT-001", "evidence_id": "E-001", "extraction_confidence": "medium"},
        {"fact_id": "FACT-002", "evidence_id": "E-001", "extraction_confidence": "low"},
    ]

    result = pipeline._aggregate_fact_confidence_to_evidence(evidence, [], facts, {"conflicts": []})
    row = result["evidence_registry"][0]

    assert row["weight"] == "supportive"
    assert row["fact_role_cap"] == "supportive"
    assert row["fact_confidence_medium_count"] == 1
    assert row["fact_confidence_low_count"] == 1


def test_batch_7_6_all_low_or_ocr_facts_cap_evidence_to_background():
    evidence = [{"evidence_id": "E-001", "weight": "supportive", "ledger_approved_for_writer": True}]
    facts = [
        {"fact_id": "FACT-001", "evidence_id": "E-001", "extraction_confidence": "low"},
        {"fact_id": "FACT-002", "evidence_id": "E-001", "extraction_confidence": "OCR_uncertain"},
    ]

    result = pipeline._aggregate_fact_confidence_to_evidence(evidence, [], facts, {"conflicts": []})
    row = result["evidence_registry"][0]

    assert row["weight"] == "background"
    assert row["ledger_approved_for_writer"] is False
    assert row["fact_role_cap"] == "background"


def test_batch_7_6_human_review_queue_has_required_structure_for_all_triggers():
    facts = [
        {"fact_id": "FACT-LOW", "evidence_id": "E-001", "extraction_confidence": "low"},
        {"fact_id": "FACT-NORM", "evidence_id": "E-002", "extraction_confidence": "high", "normalizer_status": "needs_human_review"},
        {"fact_id": "FACT-TR", "evidence_id": "E-003", "extraction_confidence": "high", "extraction_flags": "TRANSLATION_NEEDED"},
        {"fact_id": "FACT-CONF", "evidence_id": "E-004", "extraction_confidence": "high"},
    ]
    conflict_report = {
        "conflicts": [
            {
                "conflict_id": "CONF-001",
                "severity": "HIGH",
                "conflict_type": "MAGNITUDE",
                "fact_ids": ["FACT-CONF"],
                "evidence_ids": ["E-004", "E-005"],
            }
        ]
    }

    queue = pipeline._build_human_review_queue(facts, conflict_report, [])
    reasons = {row["trigger_reason"] for row in queue}

    assert {"low_confidence", "normalization_failure", "translation_needed", "conflict_flagged"} <= reasons
    assert all(row["review_id"].startswith("HR-") for row in queue)
    assert all(row["status"] == "pending" for row in queue)
    assert all("reviewer_notes" in row and "reviewed_at" in row for row in queue)


def test_batch_7_6_fact_anchored_claims_allow_quantitative_only_for_high_confidence():
    state = {
        "clinical_evidence_fact_table": [
            {
                "fact_id": "FACT-HIGH",
                "evidence_id": "E-001",
                "endpoint_label": "clinical success",
                "value_numeric": 87.3,
                "value_unit": "%",
                "CI_lower": "82.1",
                "CI_upper": "91.4",
                "follow_up": "30 days",
                "extraction_confidence": "high",
            },
            {
                "fact_id": "FACT-MED",
                "evidence_id": "E-002",
                "endpoint_label": "clinical success",
                "value_numeric": 80,
                "value_unit": "%",
                "extraction_confidence": "medium",
            },
        ],
        "fact_to_claim_link_matrix": [
            {"fact_id": "FACT-HIGH", "claim_id": "C-01", "evidence_id": "E-001"},
            {"fact_id": "FACT-MED", "claim_id": "C-01", "evidence_id": "E-002"},
        ],
    }

    rows = pipeline._fact_anchored_claim_rows(state)
    by_fact = {row["fact_id"]: row for row in rows}

    assert by_fact["FACT-HIGH"]["writer_use_level"] == "quantitative_allowed"
    assert "87.3%" in by_fact["FACT-HIGH"]["formatted_claim"]
    assert "95% CI: 82.1-91.4" in by_fact["FACT-HIGH"]["formatted_claim"]
    assert by_fact["FACT-MED"]["writer_use_level"] == "qualitative_only"
    assert "qualitative wording only" in by_fact["FACT-MED"]["formatted_claim"]


def test_batch_7_6_human_review_queue_json_and_fact_anchored_claims_export(tmp_path):
    state = _passing_state()
    state["human_review_queue"] = [
        {
            "review_id": "HR-001",
            "fact_id": "FACT-001",
            "evidence_id": "E-001",
            "trigger_reason": "low_confidence",
            "trigger_detail": "extraction_confidence=low",
            "status": "pending",
            "reviewer_notes": None,
            "reviewed_at": None,
        }
    ]
    state["fact_anchored_claims"] = [
        {
            "row_id": "FAC-001",
            "claim_id": "C-01",
            "fact_id": "FACT-001",
            "evidence_id": "E-001",
            "writer_use_level": "quantitative_allowed",
            "formatted_claim": "clinical success was 87.3%.",
        }
    ]

    written = write_authoring_artifacts(tmp_path, state)
    workbook = json.loads((tmp_path / "authoring_workbook.json").read_text(encoding="utf-8"))
    queue = json.loads((tmp_path / "human_review_queue.json").read_text(encoding="utf-8"))
    names = {Path(path).name for path in written}

    assert "human_review_queue.json" in names
    assert queue[0]["review_id"] == "HR-001"
    assert workbook["fact_anchored_claims"][0]["writer_use_level"] == "quantitative_allowed"


def test_batch_2_1_search_plan_uses_pool_target_not_forty_record_cap():
    state = _passing_state()
    state["retrieved_record_pool_target"] = 300

    plan = pipeline._phase7_search_plan(state["device_profile"], state)
    numeric_limits = []
    for row in plan:
        args = row["tool_args"]
        numeric_limits.extend(value for key, value in args.items() if key in {"retmax", "page_size", "limit"})

    assert numeric_limits
    assert all(limit != 40 for limit in numeric_limits)
    assert max(numeric_limits) >= 80
    assert all(row["retrieved_record_pool_target"] == "200-500" for row in plan)
    assert all(row["final_cer_included_target"] == "20-40" for row in plan)


def test_batch_2_1_run_sota_search_returns_five_pool_fields(monkeypatch):
    def fake_call_public(tool: str, payload: dict):
        if tool == "pubmed_search":
            return {
                "status": "ok",
                "database": "PubMed",
                "query": payload.get("query"),
                "search_date": "2026-05-11",
                "count": 250,
                "returned_count": 2,
                "pmids": ["111", "222"],
            }
        return {
            "status": "ok",
            "database": tool,
            "query": payload.get("query"),
            "search_date": "2026-05-11",
            "count": 25,
            "returned_count": 1,
            "records": [{"title": f"{tool} record"}],
        }

    monkeypatch.setattr(pipeline.mcp_tools, "call_public", fake_call_public)
    monkeypatch.setattr(pipeline.mcp_tools, "mcp_log_entry", lambda result, name: {"tool": name, "status": result.get("status")})
    state = _passing_state()
    state.pop("sota_benchmark_matrix", None)
    state.pop("search_run_registry", None)

    result = pipeline.run_sota_search(state)

    assert result["database_hit_count"]
    assert result["retrieved_record_pool"]
    assert result["screened_candidate_pool"]
    assert result["fulltext_assessed_pool"] == []
    assert result["final_cer_included_set"] == []
    assert len(result["retrieved_record_pool"]) == len(result["raw_literature_records"])
    assert {row["pool_stage"] for row in result["retrieved_record_pool"]} == {"retrieved_record_pool"}


def _contaminated_state(project_id: str, domain: str, root: Path) -> dict:
    input_root = root / project_id / "01_INITIAL_INPUT_FOR_WRITER"
    artifact_root = root / project_id / "deerflow_authoring"
    return {
        "project_id": project_id,
        "input_root": str(input_root),
        "artifact_root": str(artifact_root),
        "messages": [],
        "target_keywords": [domain],
        "source_inventory": [{"source_id": f"SRC-{project_id}", "project_id": project_id, "path": str(input_root / "IFU.docx")}],
        "device_profile": {"device_name": project_id, "device_type": domain, "clinical_domain": domain},
        "device_identity_lock": {"locked_domain": domain, "project_id": project_id},
        "claim_ledger": [{"claim_id": f"C-{project_id}", "project_id": project_id, "claim_text": domain}],
        "cep_pico_matrix": [{"pico_id": f"PICO-{project_id}", "project_id": project_id, "outcome": domain}],
        "evidence_registry": [{"evidence_id": f"E-{project_id}", "project_id": project_id, "result": domain}],
        "sota_benchmark_matrix": [{"benchmark_id": f"BM-{project_id}", "project_id": project_id, "endpoint": domain}],
        "risk_trace_matrix": [{"risk_id": f"R-{project_id}", "project_id": project_id, "risk": domain}],
        "benefit_risk_ledger": [{"br_id": f"BR-{project_id}", "project_id": project_id, "benefit_risk_balance": domain}],
        "qa_gate_report": {"project_id": project_id, "decision": "REWORK_REQUIRED"},
        "authoring_workbook": {"project_id": project_id, "schema_name": "cer_authoring_workbook"},
        "authoring_baseline_version": f"{project_id}-baseline",
    }


def _fresh_run_state(project_id: str, domain: str, root: Path) -> dict:
    return {
        "project_id": project_id,
        "input_root": str(root / project_id / "01_INITIAL_INPUT_FOR_WRITER"),
        "artifact_root": str(root / project_id / "deerflow_authoring"),
        "messages": [],
        "target_keywords": [domain],
    }


def test_run_scope_isolation_drops_all_eight_state_categories_at_initialize(tmp_path):
    state = _contaminated_state("HOLD-002", "nerve_block_needle", tmp_path)

    clean, audit = isolate_initial_authoring_state(state)

    assert clean["project_id"] == "HOLD-002"
    assert clean["input_root"] == str(tmp_path / "HOLD-002" / "01_INITIAL_INPUT_FOR_WRITER")
    assert "device_profile" not in clean
    assert "claim_ledger" not in clean
    assert "evidence_registry" not in clean
    assert "risk_trace_matrix" not in clean
    assert "benefit_risk_ledger" not in clean
    assert "qa_gate_report" not in clean
    assert "authoring_workbook" not in clean
    assert "authoring_baseline_version" not in clean

    category_drops = {row["category"]: row for row in audit["categories"]}
    assert set(category_drops) == {
        "source_intake_identity",
        "claims_pico_methodology",
        "search_sota_evidence",
        "equivalence_vigilance_risk_gspr",
        "writer_synthesis_report",
        "qa_review_gate",
        "artifact_mcp_template",
        "calibration_baseline_delta",
    }
    assert category_drops["source_intake_identity"]["dropped_key_count"] >= 3
    assert category_drops["claims_pico_methodology"]["dropped_key_count"] >= 2
    assert category_drops["search_sota_evidence"]["dropped_key_count"] >= 2
    assert category_drops["equivalence_vigilance_risk_gspr"]["dropped_key_count"] >= 1
    assert category_drops["writer_synthesis_report"]["dropped_key_count"] >= 1
    assert category_drops["qa_review_gate"]["dropped_key_count"] >= 1
    assert category_drops["artifact_mcp_template"]["dropped_key_count"] >= 1
    assert category_drops["calibration_baseline_delta"]["dropped_key_count"] >= 1


def test_run_scope_sanitizer_filters_foreign_rows_before_agent_summary(tmp_path):
    state = _fresh_run_state("HOLD-002", "nerve_block_needle", tmp_path)
    state["source_inventory"] = [
        {"source_id": "SRC-HOLD-002", "project_id": "HOLD-002", "path": str(tmp_path / "HOLD-002" / "01_INITIAL_INPUT_FOR_WRITER" / "IFU.docx")},
        {"source_id": "SRC-CAL-002", "project_id": "CAL-002", "path": str(tmp_path / "CAL-002" / "01_INITIAL_INPUT_FOR_WRITER" / "IFU.docx")},
    ]
    state["evidence_registry"] = [
        {"evidence_id": "E-HOLD-002", "project_id": "HOLD-002", "result": "current"},
        {"evidence_id": "E-CAL-002", "project_id": "CAL-002", "result": "foreign"},
        {"evidence_id": "E-UNMARKED", "result": "allowed until explicitly marked foreign"},
    ]

    clean = sanitize_run_scoped_state_for_agent_prompt(state)

    assert [row["source_id"] for row in clean["source_inventory"]] == ["SRC-HOLD-002"]
    assert [row["evidence_id"] for row in clean["evidence_registry"]] == ["E-HOLD-002", "E-UNMARKED"]
    assert clean["run_scope_audit"]["dropped_rows"]
    assert {row["category"] for row in clean["run_scope_audit"]["dropped_rows"]} == {
        "source_intake_identity",
        "search_sota_evidence",
    }


def test_run_scope_regression_cal002_hold002_hold002_cal002_and_full_smoke_sequence(tmp_path):
    domains = {
        "CAL-001": "cardiovascular_rf_ablation_catheter",
        "CAL-002": "ai_diagnostic_software",
        "CAL-003": "surgical_ligating",
        "HOLD-001": "enteral_feeding_pump",
        "HOLD-002": "nerve_block_needle",
    }

    def boundary_after(previous_project: str | None, current_project: str) -> dict:
        state = _fresh_run_state(current_project, domains[current_project], tmp_path)
        if previous_project:
            state.update(_contaminated_state(previous_project, domains[previous_project], tmp_path))
            state.update(_fresh_run_state(current_project, domains[current_project], tmp_path))
        clean, audit = isolate_initial_authoring_state(state)
        assert "device_profile" not in clean
        assert "claim_ledger" not in clean
        assert "evidence_registry" not in clean
        assert "risk_trace_matrix" not in clean
        assert "benefit_risk_ledger" not in clean
        assert clean["project_id"] == current_project
        assert clean["target_keywords"] == [domains[current_project]]
        return audit

    cal_to_hold = boundary_after("CAL-002", "HOLD-002")
    hold_standalone = boundary_after(None, "HOLD-002")
    hold_to_cal = boundary_after("HOLD-002", "CAL-002")

    assert cal_to_hold["dropped_keys"]
    assert hold_standalone["dropped_keys"] == []
    assert hold_to_cal["dropped_keys"]

    previous = None
    for project_id in ["CAL-001", "CAL-002", "CAL-003", "HOLD-001", "HOLD-002"]:
        audit = boundary_after(previous, project_id)
        if previous:
            assert audit["dropped_keys"], f"{previous}->{project_id} should drop previous generated state"
        previous = project_id


def test_hold001_run_scope_audit_verifies_identity_not_contaminated(tmp_path):
    state = _fresh_run_state("HOLD-001", "enteral_feeding_pump", tmp_path)
    state.update(_contaminated_state("CAL-003", "surgical_ligating", tmp_path))
    state.update(_fresh_run_state("HOLD-001", "enteral_feeding_pump", tmp_path))

    clean, audit = isolate_initial_authoring_state(state)

    assert clean["project_id"] == "HOLD-001"
    assert clean["target_keywords"] == ["enteral_feeding_pump"]
    assert "device_identity_lock" not in clean
    assert "device_profile" not in clean
    assert "surgical_ligating" not in str(clean)
    source_identity_audit = next(row for row in audit["categories"] if row["category"] == "source_intake_identity")
    assert source_identity_audit["dropped_key_count"] >= 2


def _ei_evidence(evidence_id: str, **overrides):
    row = {
        "evidence_id": evidence_id,
        "source_type": "subject_device_clinical_study",
        "device_relationship": "subject",
        "study_design": "randomized controlled trial",
        "sample_size": "n=150",
        "follow_up": "12 months",
        "statistical_adequacy": "adequate_for_extracted_endpoint",
        "allowed_claim_types": ["safety_clinical"],
        "target_claim_type": "safety_clinical",
        "weight": "pivotal",
    }
    row.update(overrides)
    return row


def _ei_fact(fact_id: str, evidence_id: str, **overrides):
    row = {
        "fact_id": fact_id,
        "evidence_id": evidence_id,
        "endpoint_family": "clinical_performance",
        "endpoint_label": "clinical success",
        "endpoint_cluster_id": "CL-success",
        "value_numeric": 90.0,
        "value_unit": "%",
        "population_n": 150,
        "follow_up": "12 months",
        "CI_lower": 85.0,
        "CI_upper": 95.0,
        "p_value": 0.01,
        "extraction_confidence": "high",
    }
    row.update(overrides)
    return row


def test_ei_phase1_subject_rct_scores_excellent_and_admissible():
    state = {
        "claim_ledger": [{"claim_id": "C-1", "claim_type": "safety_clinical"}],
        "evidence_registry": [_ei_evidence("E-1")],
        "clinical_evidence_fact_table": [_ei_fact("F-1", "E-1")],
    }
    row = pipeline.build_ei_core_phase1_scoring(state)["evidence_registry"][0]
    assert row["evidence_quality_tier"] == "excellent"
    assert row["admissibility_level"] == "ADMISSIBLE"


def test_ei_phase1_competitor_is_marginal_or_lower_and_not_admissible_for_safety():
    state = {
        "claim_ledger": [{"claim_id": "C-1", "claim_type": "safety_clinical"}],
        "evidence_registry": [_ei_evidence("E-C", source_type="competitor_device_public", device_relationship="competitor")],
        "clinical_evidence_fact_table": [_ei_fact("F-C", "E-C")],
    }
    row = pipeline.build_ei_core_phase1_scoring(state)["evidence_registry"][0]
    assert pipeline.EI_QUALITY_TIER_RANK[row["evidence_quality_tier"]] <= pipeline.EI_QUALITY_TIER_RANK["marginal"]
    assert row["admissibility_level"] == "NOT_ADMISSIBLE"


def test_ei_phase1_data_quality_sample_size_boundary_29_vs_30():
    state = {
        "claim_ledger": [{"claim_id": "C-1", "claim_type": "safety_clinical"}],
        "evidence_registry": [
            _ei_evidence("E-29", study_design="case series", sample_size="n=29", follow_up="not reported in source", statistical_adequacy="not extracted"),
            _ei_evidence("E-30", study_design="case series", sample_size="n=30", follow_up="not reported in source", statistical_adequacy="not extracted"),
        ],
    }
    rows = {row["evidence_id"]: row for row in pipeline.build_ei_core_phase1_scoring(state)["evidence_registry"]}
    assert rows["E-29"]["evidence_quality_tier"] == "marginal"
    assert rows["E-30"]["evidence_quality_tier"] == "acceptable"


def test_ei_phase1_factor_weights_sum_to_one():
    assert sum(pipeline.EI_SCORE_FACTOR_WEIGHTS.values()) == pytest.approx(1.0)


def test_ei_phase1_conditional_admissibility_records_condition_status():
    state = {
        "claim_ledger": [{"claim_id": "C-1", "claim_type": "safety_clinical"}],
        "evidence_registry": [
            _ei_evidence(
                "E-EQ",
                source_type="equivalent_device_literature",
                device_relationship="equivalent",
                equivalence_rationale="technical biological clinical equivalence documented",
            )
        ],
    }
    row = pipeline.build_ei_core_phase1_scoring(state)["evidence_registry"][0]
    assert row["admissibility_level"] == "CONDITIONAL"
    assert row["admissibility_condition_status"] == "met"


def test_ei_phase1_calibration_is_provisional_and_required():
    row = pipeline.build_ei_core_phase1_scoring({"evidence_registry": [_ei_evidence("E-1")]})["evidence_registry"][0]
    assert row["score_calibration_status"] == "provisional"
    assert row["calibration_required"] is True


def test_ei_scoring_lands_in_appraisal_table_without_reusing_comparability(tmp_path):
    state = {
        "claim_ledger": [{"claim_id": "C-1", "claim_type": "safety_clinical"}],
        "evidence_registry": [_ei_evidence("E-1", comparability_score_normalized=0.17)],
        "article_appraisal": [{"article_id": "ART-001", "evidence_id": "E-1", "comparability_score_normalized": 0.17}],
        "clinical_evidence_fact_table": [_ei_fact("F-1", "E-1")],
    }

    result = pipeline.build_ei_core_phase1_scoring(state)
    appraisal = result["article_appraisal"][0]
    written = write_authoring_artifacts(tmp_path, {**_passing_state(), **result})
    workbook = build_authoring_workbook({**_passing_state(), **result})

    assert {"evidence_strength_score", "evidence_quality_tier", "admissibility_level", "score_calibration_status"} <= set(appraisal)
    assert appraisal["comparability_score_normalized"] == 0.17
    assert appraisal["evidence_strength_score"] != appraisal["comparability_score_normalized"]
    assert appraisal["score_calibration_status"] == "provisional"
    assert "evidence_appraisal_table.xlsx" in {Path(path).name for path in written}
    assert "evidence_strength_score" in workbook["article_appraisal"][0]


@pytest.mark.parametrize(
    ("case_id", "state_update", "assertion"),
    [
        ("strong_two_subject", {}, lambda result: result["claim_support_matrix"]["C-1"]["support_level"] == "STRONG"),
        ("insufficient_no_subject", {"evidence_registry": []}, lambda result: result["claim_support_matrix"]["C-1"]["support_level"] == "INSUFFICIENT"),
        ("medium_fact_no_quant", {"clinical_evidence_fact_table": [_ei_fact("F-1", "E-1", extraction_confidence="medium")]}, lambda result: result["claim_support_matrix"]["C-1"]["quantitative_allowed"] is False),
        ("critical_conflict_caps", {"evidence_conflict_report": {"conflicts": [{"conflict_id": "CON-1", "severity": "CRITICAL", "evidence_ids": ["E-1"]}]}}, lambda result: result["claim_support_matrix"]["C-1"]["support_level"] == "INSUFFICIENT"),
        ("class_iii_override", {"device_profile": {"device_class": "III"}, "evidence_registry": [_ei_evidence("E-1")]}, lambda result: result["claim_support_matrix"]["C-1"]["required_source_profile"]["min_evidence_count"] == 2),
        ("forbidden_phrases", {}, lambda result: "superiority unless comparator evidence directly supports it" in result["writer_conclusion_constraints"]["C-1"]["forbidden_phrases"]),
        ("searched_not_found_reasoning", {"evidence_registry": []}, lambda result: result["claim_support_matrix"]["C-1"]["missing_evidence_flags"]),
        ("benchmark_synthesis_selected", {}, lambda result: result["synthesis_method_selections"][0]["synthesis_method"] == "benchmark"),
        ("critical_no_synthesis", {"evidence_conflict_report": {"conflicts": [{"severity": "CRITICAL", "endpoint_cluster_id": "CL-success", "evidence_ids": ["E-1"]}]}}, lambda result: result["synthesis_method_selections"][0]["synthesis_method"] == "none"),
        ("low_quality_absence", {"evidence_registry": [_ei_evidence("E-1", study_design="case series", sample_size="n=20", follow_up="not reported in source", statistical_adequacy="not extracted")], "clinical_evidence_fact_table": []}, lambda result: result["evidence_registry"][0]["absence_category"] == "found_but_low_quality"),
        ("ctgov_no_results", {"evidence_registry": [_ei_evidence("E-CT", source_type="clinical_trial_record", results_status="NO_RESULTS_AVAILABLE")]}, lambda result: result["evidence_registry"][0]["absence_category"] == "no_results"),
        ("equivalent_bridge", {"evidence_registry": [_ei_evidence("E-EQ", source_type="equivalent_device_literature", device_relationship="equivalent", equivalence_rationale="technical biological clinical equivalence")]}, lambda result: result["evidence_registry"][0]["bridging_assessment"]["max_conclusion_strength"] == "MODERATE"),
        ("similar_bridge_context", {"evidence_registry": [_ei_evidence("E-SIM", source_type="similar_device_literature", device_relationship="similar")]}, lambda result: "safety_clinical" in result["evidence_registry"][0]["bridging_assessment"]["forbidden_claim_types"]),
        ("competitor_bridge_sota_only", {"evidence_registry": [_ei_evidence("E-COMP", source_type="competitor_device_public", device_relationship="competitor")]}, lambda result: result["evidence_registry"][0]["bridging_assessment"]["bridge_to_claim_types"] == ["sota_benchmark"]),
        ("equivalence_fails_downgrades", {"evidence_registry": [_ei_evidence("E-EQF", source_type="equivalent_device_literature", device_relationship="equivalent", equivalence_rationale="technical only")]}, lambda result: result["evidence_registry"][0]["bridging_assessment"]["max_conclusion_strength"] == "CAUTIOUS"),
        ("writer_constraints_present", {}, lambda result: result["writer_conclusion_constraints"]["C-1"]["allowed_language_strength"] in {"STRONG", "MODERATE", "CAUTIOUS", "INSUFFICIENT"}),
    ],
)
def test_ei_phase2_claim_absence_synthesis_and_bridging(case_id, state_update, assertion):
    base = {
        "claim_ledger": [{"claim_id": "C-1", "claim_type": "safety_clinical"}],
        "evidence_registry": [_ei_evidence("E-1"), _ei_evidence("E-2"), _ei_evidence("E-3")],
        "clinical_evidence_fact_table": [_ei_fact("F-1", "E-1"), _ei_fact("F-2", "E-2", value_numeric=91.0), _ei_fact("F-3", "E-3", value_numeric=92.0)],
    }
    base.update(state_update)
    assert assertion(pipeline.build_ei_core_phase2_reasoning(base))


@pytest.mark.parametrize(
    ("case_id", "state_update", "assertion"),
    [
        ("sota_high", {}, lambda result: result["sota_benchmark_table"][0]["benchmark_confidence"] == "high"),
        ("sota_insufficient_after_exclusion", {"clinical_evidence_fact_table": [_ei_fact("F-1", "E-1"), _ei_fact("F-2", "E-2", timepoint="timepoint_mismatch")]}, lambda result: result["sota_benchmark_table"][0]["benchmark_confidence"] == "insufficient_data"),
        ("sota_excluded_reason", {"clinical_evidence_fact_table": [_ei_fact("F-1", "E-1"), _ei_fact("F-2", "E-2", timepoint="timepoint_mismatch"), _ei_fact("F-3", "E-3")]}, lambda result: result["sota_benchmark_table"][0]["excluded_studies"]),
        ("competitor_cap_medium", {"evidence_registry": [_ei_evidence("E-1", source_type="competitor_device_public", device_relationship="competitor"), _ei_evidence("E-2", source_type="competitor_device_public", device_relationship="competitor"), _ei_evidence("E-3", source_type="competitor_device_public", device_relationship="competitor")]}, lambda result: result["sota_benchmark_table"][0]["benchmark_confidence"] == "medium"),
        ("br_favorable_high", {}, lambda result: result["benefit_risk_conclusion"]["overall_judgment"] == "favorable"),
        ("br_borderline_equal", {"clinical_evidence_fact_table": [_ei_fact("F-B", "E-1", value_numeric=5), _ei_fact("F-R", "E-2", endpoint_family="safety", endpoint_label="adverse event", value_numeric=5)]}, lambda result: result["benefit_risk_conclusion"]["overall_judgment"] == "borderline"),
        ("br_insufficient_no_favorable", {"clinical_evidence_fact_table": [_ei_fact("F-B", "E-1", value_numeric=90)]}, lambda result: result["benefit_risk_conclusion"]["overall_judgment"] != "favorable"),
        ("pmcf_long_term", {"device_profile": {"device_type": "implantable"}, "clinical_evidence_fact_table": [_ei_fact("F-B", "E-1", follow_up="3 months"), _ei_fact("F-R", "E-2", endpoint_family="safety", endpoint_label="adverse event", value_numeric=5)]}, lambda result: any(row["gap_type"] == "long_term_data" for row in result["pmcf_gap_register"])),
        ("pmcf_rare_event", {"clinical_evidence_fact_table": [_ei_fact("F-B", "E-1", population_n=30), _ei_fact("F-R", "E-2", endpoint_family="safety", endpoint_label="adverse event", value_numeric=5, population_n=30)]}, lambda result: any(row["gap_type"] == "rare_event" for row in result["pmcf_gap_register"])),
        ("pmcf_comparator", {}, lambda result: any(row["gap_type"] == "comparator_gap" for row in result["pmcf_gap_register"])),
        ("multiple_gaps", {"device_profile": {"device_type": "implantable"}, "clinical_evidence_fact_table": [_ei_fact("F-B", "E-1", follow_up="3 months", population_n=30), _ei_fact("F-R", "E-2", endpoint_family="safety", endpoint_label="adverse event", value_numeric=5, population_n=30)]}, lambda result: len(result["pmcf_gap_register"]) >= 2),
        ("br_has_benefit_and_risk_lists", {}, lambda result: result["benefit_risk_conclusion"]["per_claim_benefit"] and result["benefit_risk_conclusion"]["per_claim_risk"]),
    ],
)
def test_ei_phase3_sota_benefit_risk_and_pmcf(case_id, state_update, assertion):
    base = {
        "claim_ledger": [{"claim_id": "C-1", "claim_type": "safety_clinical"}],
        "evidence_registry": [_ei_evidence("E-1"), _ei_evidence("E-2"), _ei_evidence("E-3")],
        "clinical_evidence_fact_table": [
            _ei_fact("F-1", "E-1", value_numeric=90),
            _ei_fact("F-2", "E-2", value_numeric=91),
            _ei_fact("F-3", "E-3", value_numeric=92),
            _ei_fact("F-R", "E-2", endpoint_family="safety", endpoint_label="adverse event", value_numeric=5),
        ],
    }
    base.update(state_update)
    assert assertion(pipeline.build_ei_core_phase3_sota_br_pmcf(base))


@pytest.mark.parametrize(
    ("case_id", "state_update", "assertion"),
    [
        ("critical_conflict_tier3", {"evidence_conflict_report": {"conflicts": [{"conflict_id": "CON-1", "severity": "CRITICAL", "conflict_type": "DIRECTIONAL", "claim_ids": ["C-1"], "evidence_ids": ["E-1"]}]}}, lambda result: any(p["tier"] == 3 and p["decision_required"] for p in result["human_review_packet"])),
        ("high_conflict_tier2", {"evidence_conflict_report": {"conflicts": [{"conflict_id": "CON-1", "severity": "HIGH", "conflict_type": "STATISTICAL", "claim_ids": ["C-1"], "evidence_ids": ["E-1"]}]}}, lambda result: any(p["tier"] == 2 and not p["decision_required"] for p in result["human_review_packet"])),
        ("low_confidence_not_packet", {"clinical_evidence_fact_table": [_ei_fact("F-LOW", "E-1", extraction_confidence="low")]}, lambda result: not any(p.get("trigger") == "low_confidence" for p in result["human_review_packet"])),
        ("packet_structure", {"evidence_conflict_report": {"conflicts": [{"severity": "CRITICAL", "conflict_type": "MAGNITUDE", "claim_ids": ["C-1"], "evidence_ids": ["E-1"]}]}}, lambda result: {"packet_id", "tier", "trigger", "affected_claims", "evidence_summary", "decision_options", "recommendation", "decision_required", "deadline_signal"}.issubset(result["human_review_packet"][0])),
        ("g46_consumes_block", {"evidence_conflict_report": {"conflicts": [{"severity": "CRITICAL", "conflict_type": "DIRECTIONAL", "claim_ids": ["C-1"], "evidence_ids": ["E-1"]}]}}, lambda result: evaluate_pre_writer_readiness_gate(result)["status"] == "REWORK_REQUIRED"),
        ("crosswalk_traceability", {}, lambda result: result["cer_rmf_crosswalk_table"][0]["link_nature"] == "traceability"),
        ("crosswalk_mismatch_high", {"risk_trace_matrix": []}, lambda result: result["cer_rmf_crosswalk_table"][0]["mismatch_flag"] == "HIGH"),
        ("audit_traces_fact", {}, lambda result: any("FACT" in str(entry["input_artifacts"]) for entry in result["reasoning_audit_ledger"])),
        ("validation_harness_24", {}, lambda result: len(result["ei_validation_harness_results"]) == 24 and all(row["status"] == "PASS" for row in result["ei_validation_harness_results"])),
        ("artifact_exports_ei_outputs", {"tmp_export": True}, lambda result: result["human_review_packet"] is not None),
    ],
)
def test_ei_phase4_crosswalk_audit_human_review_and_gate_bridge(case_id, state_update, assertion, tmp_path):
    base = {
        "claim_ledger": [{"claim_id": "C-1", "claim_type": "safety_clinical"}],
        "risk_trace_matrix": [{"risk_id": "R-1", "hazard": "adverse event"}],
        "evidence_registry": [_ei_evidence("E-1"), _ei_evidence("E-2")],
        "clinical_evidence_fact_table": [_ei_fact("FACT-1", "E-1"), _ei_fact("FACT-R", "E-2", endpoint_family="safety", endpoint_label="adverse event", value_numeric=5)],
    }
    update = dict(state_update)
    export = update.pop("tmp_export", False)
    base.update(update)
    result = pipeline.build_ei_core_phase4_audit_review(base)
    if export:
        names = {Path(path).name for path in write_authoring_artifacts(tmp_path, result)}
        assert {"human_review_packet.json", "reasoning_audit_ledger.xlsx", "ei_validation_harness_results.xlsx"}.issubset(names)
    assert assertion(result)


def test_human_review_packet_filters_entity_level_conflicts_and_reports_summary():
    state = {
        "claim_ledger": [{"claim_id": "C-1", "claim_type": "safety_clinical"}],
        "risk_trace_matrix": [{"risk_id": "R-1", "hazard": "adverse event"}],
        "evidence_registry": [_ei_evidence("E-1"), _ei_evidence("E-2")],
        "clinical_evidence_fact_table": [_ei_fact("FACT-1", "E-1"), _ei_fact("FACT-2", "E-2")],
        "claim_support_matrix": {"C-1": {"claim_id": "C-1", "support_level": "STRONG", "supporting_evidence_ids": ["E-1"]}},
        "benefit_risk_conclusion": {"overall_judgment": "favorable", "br_acceptability_confidence": "high"},
        "pmcf_gap_register": [],
        "evidence_conflict_report": {
            "conflicts": [
                {
                    "conflict_id": "ENTITY-CONF-001",
                    "severity": "CRITICAL",
                    "conflict_type": "DIRECTIONAL",
                    "claim_ids": ["C-1"],
                    "evidence_ids": ["E-1", "E-2"],
                    "comparison_scope": "entity_level",
                    "left_entity_id": "ENT-1",
                    "right_entity_id": "ENT-2",
                }
            ]
        },
    }

    result = pipeline.build_ei_core_phase4_audit_review(state)
    summary = result["human_review_packet_filtering_summary"]

    assert not any(packet["trigger"] in {"critical_conflict", "high_conflict"} for packet in result["human_review_packet"])
    assert summary["total_conflicts"] == 1
    assert summary["entity_level_conflicts"] == 1
    assert summary["semantic_conflicts"] == 0
    assert summary["hrq_generated_conflicts"] == 0
    assert summary["filtered_out_count"] == 1
    assert summary["filter_reason_distribution"]["entity_level_pairwise_filtered"] == 1


def test_human_review_packet_keeps_high_critical_semantic_conflicts():
    state = {
        "claim_ledger": [{"claim_id": "C-1", "claim_type": "safety_clinical"}],
        "risk_trace_matrix": [{"risk_id": "R-1", "hazard": "adverse event"}],
        "evidence_registry": [_ei_evidence("E-1"), _ei_evidence("E-2")],
        "clinical_evidence_fact_table": [_ei_fact("FACT-1", "E-1"), _ei_fact("FACT-2", "E-2")],
        "claim_support_matrix": {"C-1": {"claim_id": "C-1", "support_level": "STRONG", "supporting_evidence_ids": ["E-1"]}},
        "benefit_risk_conclusion": {"overall_judgment": "favorable", "br_acceptability_confidence": "high"},
        "pmcf_gap_register": [],
        "evidence_conflict_report": {
            "conflicts": [
                {
                    "conflict_id": "CONF-SEM-001",
                    "severity": "HIGH",
                    "conflict_type": "STATISTICAL",
                    "claim_ids": ["C-1"],
                    "evidence_ids": ["E-1", "E-2"],
                    "fact_ids": ["FACT-1", "FACT-2"],
                }
            ]
        },
    }

    result = pipeline.build_ei_core_phase4_audit_review(state)
    summary = result["human_review_packet_filtering_summary"]

    assert any(packet["trigger"] == "high_conflict" for packet in result["human_review_packet"])
    assert summary["semantic_conflicts"] == 1
    assert summary["hrq_generated_conflicts"] == 1
    assert summary["filter_reason_distribution"]["semantic_high_critical_linked"] == 1


def test_provisional_ei_runs_after_fact_table_when_retrieval_is_blocked():
    state = {
        "claim_ledger": [{"claim_id": "C-1", "claim_type": "safety_clinical"}],
        "evidence_registry": [_ei_evidence("E-1"), _ei_evidence("E-2")],
        "clinical_evidence_fact_table": [_ei_fact("FACT-1", "E-1"), _ei_fact("FACT-2", "E-2", endpoint_family="safety", endpoint_label="adverse event", value_numeric=3)],
        "search_run_registry": [
            {"search_id": "SEARCH-SOTA-01", "database": "ClinicalTrials.gov", "query": "fixture", "search_date": "2026-05-13", "status": "source_unavailable", "result_count": None}
        ],
        "mcp_call_log": [{"server": "cer-public-evidence", "tool": "pubmed_search", "status": "ok"}],
        "qa_gate_report": {"failed_gates": ["G17"]},
    }

    result = pipeline._run_provisional_ei_reasoning(state)

    assert result["retrieval_completeness"]["retrieval_status"] == "blocked_by_mcp"
    assert result["claim_support_matrix"]["retrieval_completeness"]["evidence_scope"] == "retrieval_incomplete"
    assert result["claim_support_matrix"]["C-1"]["max_conclusion_strength"] == "CAUTIOUS"
    assert result["claim_support_matrix"]["C-1"]["quantitative_allowed"] is False
    assert result["benefit_risk_conclusion"]["br_acceptability_confidence"] == "low"
    assert result["ei_gate_signals"]["writer_status"] == "BLOCKED"
    assert result["human_review_packet"][-1]["trigger"] == "retrieval_incomplete_provisional_ei"
    assert "does not authorize Writer" in result["provisional_ei_reasoning_report"]


def test_provisional_ei_artifact_export_and_human_review_queue_compaction(tmp_path):
    huge_payload = {"source_document_text": "x" * 1_000_000, "raw": {"nested": "y" * 1_000_000}}
    state = {
        "claim_ledger": [{"claim_id": "C-1", "claim_type": "safety_clinical"}],
        "evidence_registry": [_ei_evidence("E-1")],
        "clinical_evidence_fact_table": [_ei_fact("FACT-1", "E-1")],
        "search_run_registry": [
            {"search_id": "SEARCH-SOTA-01", "database": "ClinicalTrials.gov", "query": "fixture", "search_date": "2026-05-13", "status": "source_unavailable", "result_count": None}
        ],
        "human_review_queue": [
            {
                "review_id": "HR-001",
                "fact_id": "FACT-1",
                "evidence_id": "E-1",
                "trigger_reason": "low_confidence",
                "trigger_detail": "fixture",
                **huge_payload,
            }
        ],
    }

    written = write_authoring_artifacts(tmp_path, state)
    names = {Path(path).name for path in written}
    claim_support = json.loads((tmp_path / "claim_support_matrix.json").read_text(encoding="utf-8"))
    queue_text = (tmp_path / "human_review_queue.json").read_text(encoding="utf-8")
    report_text = (tmp_path / "provisional_ei_reasoning_report.md").read_text(encoding="utf-8")

    assert "provisional_ei_reasoning_report.md" in names
    assert claim_support["retrieval_completeness"]["retrieval_status"] == "blocked_by_mcp"
    assert len(queue_text) < 20_000
    assert "source_document_text" not in queue_text
    assert "retrieval_incomplete / local_only" in report_text


def test_human_review_packet_uses_id_references_not_inline_full_text(tmp_path):
    huge_conflict = {
        "conflict_id": "CONF-HUGE",
        "severity": "CRITICAL",
        "conflict_type": "DIRECTIONAL",
        "claim_ids": ["C-1"],
        "evidence_ids": ["E-1", "E-2"],
        "fact_ids": ["FACT-1", "FACT-2"],
        "full_conflict_matrix": "x" * 2_000_000,
        "evidence_records": [{"evidence_id": "E-1", "full_text": "y" * 2_000_000}],
    }
    state = {
        "claim_ledger": [{"claim_id": "C-1", "claim_type": "safety_clinical"}],
        "risk_trace_matrix": [{"risk_id": "R-1"}],
        "evidence_registry": [_ei_evidence("E-1"), _ei_evidence("E-2")],
        "clinical_evidence_fact_table": [_ei_fact("FACT-1", "E-1"), _ei_fact("FACT-2", "E-2")],
        "evidence_conflict_report": {"conflicts": [huge_conflict]},
    }

    result = pipeline.build_ei_core_phase4_audit_review(state)
    packet = result["human_review_packet"][0]
    summary = packet["evidence_summary"]
    written = write_authoring_artifacts(tmp_path, result)
    packet_text = (tmp_path / "human_review_packet.json").read_text(encoding="utf-8")

    assert {"packet_id", "tier", "trigger", "affected_claims", "evidence_summary", "decision_options", "decision_required"} <= set(packet)
    assert summary["evidence_ids"] == ["E-1", "E-2"]
    assert summary["fact_ids"] == ["FACT-1", "FACT-2"]
    assert summary["conflict_id"] == "CONF-HUGE"
    assert len(summary["summary"]) <= 500
    assert "full_conflict_matrix" not in packet_text
    assert "full_text" not in packet_text
    assert len(packet_text.encode("utf-8")) < 1_000_000
    assert "human_review_packet.json" in {Path(path).name for path in written}


def test_artifact_writer_filters_existing_entity_level_conflict_packets(tmp_path):
    entity_conflict = {
        "conflict_id": "ENTITY-CONF-001",
        "conflict_scope": "entity_level",
        "severity": "CRITICAL",
        "conflict_type": "DIRECTIONAL",
        "claim_ids": ["C-1"],
        "evidence_ids": ["E-1", "E-2"],
    }
    state = {
        **_passing_state(),
        "claim_ledger": [{"claim_id": "C-1", "claim_type": "safety_clinical"}],
        "risk_trace_matrix": [{"risk_id": "R-1"}],
        "evidence_registry": [_ei_evidence("E-1"), _ei_evidence("E-2")],
        "clinical_evidence_fact_table": [_ei_fact("FACT-1", "E-1"), _ei_fact("FACT-2", "E-2")],
        "claim_support_matrix": {"C-1": {"claim_id": "C-1", "support_level": "STRONG", "supporting_evidence_ids": ["E-1"]}},
        "benefit_risk_conclusion": {"overall_judgment": "favorable", "br_acceptability_confidence": "high"},
        "pmcf_gap_register": [],
        "ei_gate_signals": {"pre_writer_readiness_condition_overrides": {}},
        "evidence_conflict_report": {"conflict_count": 1, "conflicts": [entity_conflict]},
        "human_review_packet": [
            {
                "packet_id": "HRP-HUGE",
                "tier": 3,
                "trigger": "critical_conflict",
                "affected_claims": ["C-1"],
                "evidence_summary": {"conflict": entity_conflict, "full_conflict_matrix": "x" * 200_000},
                "decision_options": ["supplement_evidence"],
                "decision_required": True,
            }
        ],
    }

    written = write_authoring_artifacts(tmp_path, state)
    packet_payload = json.loads((tmp_path / "human_review_packet.json").read_text(encoding="utf-8"))
    summary = json.loads((tmp_path / "human_review_packet_filtering_summary.json").read_text(encoding="utf-8"))

    assert "human_review_packet_filtering_summary.json" in {Path(path).name for path in written}
    assert not any(row.get("trigger") == "critical_conflict" for row in packet_payload)
    assert summary["total_conflicts"] == 1
    assert summary["entity_level_conflicts"] == 1
    assert summary["filtered_out_count"] == 1
    assert summary["filter_reason_distribution"]["entity_level_pairwise_filtered"] == 1
    assert len((tmp_path / "human_review_packet.json").read_bytes()) < 20_000
