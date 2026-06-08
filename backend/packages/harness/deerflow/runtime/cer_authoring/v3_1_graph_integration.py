"""V3.1 Graph Integration — non-invasive extension to the existing graph.

Adds V3.1 nodes and routes after endpoint_extraction, before sota_endpoint_gate.
Patches G46 to include V3.1 gate results.
P/E/C citation IDs assigned during sota_search.
"""

from __future__ import annotations
from typing import Any


def get_v3_1_node_definitions() -> dict[str, Any]:
    """Return new node definitions for the V3.1 chain.

    These can be registered after the existing graph is built.
    Returns {node_name: (_node_function, _route_function_or_None)}
    """
    from deerflow.runtime.cer_authoring.v3_1_runtime import (
        build_clinical_fact_registry,
        build_endpoint_master,
        build_endpoint_selection_table,
        assemble_reference_framework,
        compute_evidence_weighting,
        derive_sota_benchmark,
        align_own_data_to_benchmark,
        assign_citation_ids,
        determine_pmcf_need,
    )
    from deerflow.runtime.cer_authoring.v3_1_gates import (
        evaluate_clinical_fact_registry_lock,
        evaluate_endpoint_selection,
        evaluate_sota_benchmark_derivation,
        aggregate_v3_1_gates_into_g46,
    )

    def _node_clinical_fact_registry(state: dict[str, Any]) -> dict[str, Any]:
        result = build_clinical_fact_registry(state)
        return {"stage_results": [{"node": "clinical_fact_registry", "status": "completed"}], **result}

    def _node_endpoint_master(state: dict[str, Any]) -> dict[str, Any]:
        result = build_endpoint_master(state)
        return {"stage_results": [{"node": "endpoint_master", "status": "completed"}], **result}

    def _node_endpoint_selection(state: dict[str, Any]) -> dict[str, Any]:
        result = build_endpoint_selection_table(state)
        lock_result = evaluate_endpoint_selection(state)
        return {
            "stage_results": [{"node": "endpoint_selection", "status": lock_result.get("status", "completed")}],
            **result,
            "_v3_1_endpoint_selection_gate": lock_result,
        }

    def _node_reference_framework(state: dict[str, Any]) -> dict[str, Any]:
        result = assemble_reference_framework(state)
        return {"stage_results": [{"node": "reference_framework", "status": "completed"}], **result}

    def _node_evidence_weighting(state: dict[str, Any]) -> dict[str, Any]:
        result = compute_evidence_weighting(state)
        return {"stage_results": [{"node": "evidence_weighting", "status": "completed"}], **result}

    def _node_benchmark_derivation(state: dict[str, Any]) -> dict[str, Any]:
        result = derive_sota_benchmark(state)
        gate_result = evaluate_sota_benchmark_derivation(state)
        return {
            "stage_results": [{"node": "benchmark_derivation", "status": gate_result.get("status", "completed")}],
            **result,
            "_v3_1_sota_benchmark_gate": gate_result,
        }

    def _node_own_data_alignment(state: dict[str, Any]) -> dict[str, Any]:
        result = align_own_data_to_benchmark(state)
        pmcf_result = determine_pmcf_need({**state, **result})
        return {
            "stage_results": [{"node": "own_data_alignment", "status": "completed"}],
            **result,
            **pmcf_result,
        }

    def _node_citation_assignment(state: dict[str, Any]) -> dict[str, Any]:
        result = assign_citation_ids(state)
        return {"stage_results": [{"node": "citation_assignment", "status": "completed"}], **result}

    # V3.1 gate aggregation node (runs before G46)
    def _node_v3_1_gate_aggregation(state: dict[str, Any]) -> dict[str, Any]:
        result = aggregate_v3_1_gates_into_g46(state)
        return {"stage_results": [{"node": "v3_1_gates", "status": result.get("v3_1_gate_status", "completed")}], **result}

    # ── V3.1 Literature Bridge nodes ──
    def _node_literature_download_gate(state):
        from deerflow.runtime.cer_authoring.v3_1_literature_bridge import build_literature_download_request, scan_full_text_pdfs
        req=build_literature_download_request(state); scan=scan_full_text_pdfs(state.get("artifact_root",""))
        needed=req.get("literature_download_request",{}).get("total_needed",0); available=scan.get("pdfs_available",0)
        still=max(0,needed-available)
        return {"stage_results":[{"node":"literature_download_gate","status":"human_intervention_required" if still>0 else "ready"}],
            "literature_download_request":req.get("literature_download_request"),"literature_pdf_status":scan,
            "literature_still_needed":still,"_literature_human_gate_required":still>0}
    def _node_liteparse_extraction(state):
        from deerflow.runtime.cer_authoring.v3_1_literature_bridge import extract_full_text_with_liteparse, enrich_state_with_full_text
        result=extract_full_text_with_liteparse(state.get("artifact_root",""))
        enrichment=enrich_state_with_full_text(state,result)
        return {"stage_results":[{"node":"liteparse_extraction","status":"completed"}],"liteparse_extraction_results":result,**enrichment}

    return {
        "literature_download_gate": (_node_literature_download_gate, None),
        "liteparse_extraction": (_node_liteparse_extraction, None),
        "clinical_fact_registry": (_node_clinical_fact_registry, None),
        "endpoint_master": (_node_endpoint_master, None),
        "endpoint_selection": (_node_endpoint_selection, None),
        "reference_framework": (_node_reference_framework, None),
        "evidence_weighting": (_node_evidence_weighting, None),
        "benchmark_derivation": (_node_benchmark_derivation, None),
        "own_data_alignment": (_node_own_data_alignment, None),
        "citation_assignment": (_node_citation_assignment, None),
        "v3_1_gate_aggregation": (_node_v3_1_gate_aggregation, None),
    }


def get_v3_1_edge_chain() -> list[tuple[str, str]]:
    """Return the V3.1 node chain as (source, target) edge pairs.

    Insert this chain between endpoint_extraction and sota_endpoint_gate.
    Additionally, insert citation_assignment between sota_search and retrieval_domain_gate.
    Additionally, insert v3_1_gate_aggregation before pre_writer_readiness_gate.
    """
    # Literature bridge + Main V3.1 chain
    # endpoint_extraction → literature_download_gate → liteparse_extraction → clinical_fact_registry → ... → sota_endpoint_gate
    main_chain = [
        ("endpoint_extraction", "literature_download_gate"),
        ("literature_download_gate", "liteparse_extraction"),
        ("liteparse_extraction", "clinical_fact_registry"),
        ("clinical_fact_registry", "endpoint_master"),
        ("endpoint_master", "endpoint_selection"),
        ("endpoint_selection", "reference_framework"),
        ("reference_framework", "evidence_weighting"),
        ("evidence_weighting", "benchmark_derivation"),
        ("benchmark_derivation", "own_data_alignment"),
        ("own_data_alignment", "sota_endpoint_gate"),  # reconnects to existing graph
    ]

    # Citation assignment: inserts between sota_search outputs
    citation_chain = [
        ("sota_search", "citation_assignment"),
        ("citation_assignment", "retrieval_domain_gate"),
        ("citation_assignment", "device_equivalence_search"),
    ]

    # Gate aggregation: inserts before pre_writer_readiness_gate
    gate_chain = [
        ("alignment_gate", "v3_1_gate_aggregation"),  # replaces alignment_gate → pre_writer_readiness_gate
        ("v3_1_gate_aggregation", "pre_writer_readiness_gate"),
    ]

    return main_chain + citation_chain + gate_chain


def get_v3_1_rewire_spec() -> dict[str, Any]:
    """Return the rewiring specification for graph.py.

    `remove_edges`: list of (source, target) edges to remove before inserting V3.1 chain.
    `add_edges`: list of (source, target) edges to add (the V3.1 chain).
    `remove_conditionals`: list of source nodes whose existing conditional edges should be replaced.
    """
    return {
        "remove_edges": [
            ("endpoint_extraction", "sota_endpoint_gate"),  # replaced by V3.1 chain
            ("sota_search", "retrieval_domain_gate"),       # replaced by citation → retrieval
            ("sota_search", "device_equivalence_search"),   # replaced by citation → equivalence
        ],
        "add_edges": get_v3_1_edge_chain(),
        "v3_1_nodes": list(get_v3_1_node_definitions().keys()),
        "gate_integration": {
            "G46_aggregation_node": "v3_1_gate_aggregation",
            "G46_position": "before pre_writer_readiness_gate",
        },
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Bug fixes (Phase 7 — implemented alongside integration to minimize rework)
# ═══════════════════════════════════════════════════════════════════════════════

def fix_latent_bugs():
    """Return a report of the 7 latent bugs with fix descriptions.

    These are applied separately to graph.py, gates.py, and pipeline.py.
    """
    return [
        {
            "bug_id": "BUG-001",
            "file": "graph.py",
            "issue": "Missing datetime/timezone imports at L1-12 (used at L276, L545)",
            "fix": "Add `from datetime import datetime, timezone` to imports",
            "severity": "high",
        },
        {
            "bug_id": "BUG-002",
            "file": "graph.py",
            "issue": "8 stage-IDs not in _STAGE_AGENT (device_profile_iteration, pre_writer_summary, intake_pack_review, prisma_flow_review, claim_sota_alignment, review_quick_scan, query_expansion, self_inspection)",
            "fix": "Add these stage-IDs to _STAGE_AGENT mapping with appropriate agent assignments",
            "severity": "medium",
        },
        {
            "bug_id": "BUG-003",
            "file": "gates.py",
            "issue": "G42 spiral ceiling inconsistency: max_rounds=3 in evaluator but max_rounds=5 in route fn",
            "fix": "Use max_rounds=3 (the evaluator's hard ceiling) consistently",
            "severity": "medium",
        },
        {
            "bug_id": "BUG-004",
            "file": "graph.py",
            "issue": "Atomic write TOCTOU race in _node_export (.export_completed) and _node_controlled_compromise",
            "fix": "Use tempfile + os.rename for atomic writes",
            "severity": "medium",
        },
        {
            "bug_id": "BUG-005",
            "file": "graph.py",
            "issue": "try/except in _node_controlled_compromise swallows write_authoring_artifacts failures",
            "fix": "Log error, set status='export_failed', do NOT report success",
            "severity": "high",
        },
        {
            "bug_id": "BUG-006",
            "file": "artifacts.py",
            "issue": "Consolidated workbook does not include V3.1 artifacts (7 SOTA derivation + fact_registry + endpoint_selection + treatment_landscape + reference_framework)",
            "fix": "Extend OUTPUT_FILES and workbook payloads with V3.1 artifacts",
            "severity": "low",
        },
        {
            "bug_id": "BUG-007",
            "file": "gates.py",
            "issue": "G46 only checks 9 conditions; missing V3.1 gate aggregation",
            "fix": "Call aggregate_v3_1_gates_into_g46() and merge results into pre_writer_readiness gate output",
            "severity": "high",
        },
    ]
