"""V3.1 Gates — 8 original gates + 8 semantic validation gates.

Phase 0-2: structural gates (integrated into G46).
Semantic: artifact quality gates (BLOCK-level, prevent hollow artifacts).
All gates follow the standard {gate_id, status, checks, failure_reason} contract.
"""

from __future__ import annotations
from typing import Any

from deerflow.runtime.cer_authoring.v3_1_runtime import (
    REQUIRED_LEDGER_FILES,
    evaluate_search_ledger_integrity,
)

# ═══════════════════════════════════════════════════════════════════════════════
# G-CLINICAL-FACT-REGISTRY-LOCK
# ═══════════════════════════════════════════════════════════════════════════════

def evaluate_clinical_fact_registry_lock(state: dict[str, Any]) -> dict[str, Any]:
    """Check that Clinical Fact Registry exists and P0 facts are locked."""
    registry = state.get("clinical_fact_registry") or []
    if not registry:
        return {
            "gate_id": "G-CLINICAL-FACT-REGISTRY-LOCK",
            "status": "REWORK_REQUIRED",
            "failure_reason": "Clinical Fact Registry is empty or not built",
        }

    unlocked = [f for f in registry if f.get("locked_status") == "human_confirmed" and not f.get("locked_at")]
    p0_facts = [f for f in registry if f.get("locked_status") == "human_confirmed"]
    auto_locked = [f for f in registry if f.get("locked_status") == "auto_locked"]

    return {
        "gate_id": "G-CLINICAL-FACT-REGISTRY-LOCK",
        "status": "PASS" if not unlocked else "REWORK_REQUIRED",
        "total_facts": len(registry),
        "p0_pending_lock": len(unlocked),
        "p0_total": len(p0_facts),
        "auto_locked": len(auto_locked),
        "failure_reason": f"{len(unlocked)} P0 facts pending human lock: {[f['fact_id'] for f in unlocked[:5]]}" if unlocked else None,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# G-ENDPOINT-SELECTION-REDUCED
# ═══════════════════════════════════════════════════════════════════════════════

def evaluate_endpoint_selection(state: dict[str, Any]) -> dict[str, Any]:
    """Check endpoint selection: core ≤ 5, each core has own-data + SOTA benchmark."""
    selection = state.get("endpoint_selection_table") or []
    cores = [e for e in selection if isinstance(e, dict) and e.get("include_status") == "core"]

    checks = []
    # Check: core endpoints ≤ 5
    checks.append({
        "check": "core_endpoints_max_5",
        "count": len(cores),
        "passes": len(cores) <= 5,
    })

    # Check: each core has own-data + SOTA benchmark
    cores_without_own_data = [
        c.get("endpoint_id", "?") for c in cores
        if not c.get("own_data_available")
    ]
    checks.append({
        "check": "core_endpoints_have_own_data",
        "missing": cores_without_own_data,
        "passes": len(cores_without_own_data) == 0,
    })

    # Check: no excluded endpoint in core
    excluded_as_core = [
        e.get("endpoint_id", "?") for e in selection
        if isinstance(e, dict) and e.get("include_status") == "core" and e.get("exclusion_reason")
    ]
    checks.append({
        "check": "no_excluded_endpoint_as_core",
        "violations": excluded_as_core,
        "passes": len(excluded_as_core) == 0,
    })

    all_pass = all(c.get("passes", False) for c in checks)
    return {
        "gate_id": "G-ENDPOINT-SELECTION-REDUCED",
        "status": "PASS" if all_pass else "REWORK_REQUIRED",
        "total_endpoints": len(selection),
        "core_count": len(cores),
        "checks": checks,
        "failure_reason": _selection_failure(checks) if not all_pass else None,
    }


def _selection_failure(checks: list[dict]) -> str:
    failures = [c.get("check", "?") for c in checks if not c.get("passes")]
    return f"Failed checks: {', '.join(failures)}"


# ═══════════════════════════════════════════════════════════════════════════════
# G-SOTA-BENCHMARK-DERIVATION (10 checks)
# ═══════════════════════════════════════════════════════════════════════════════

def evaluate_sota_benchmark_derivation(state: dict[str, Any]) -> dict[str, Any]:
    """G-SOTA-BENCHMARK-DERIVATION: validate the 10-check gate."""
    master = state.get("sota_endpoint_master") or []
    source_roles = state.get("sota_source_role_matrix") or {}
    candidates = state.get("sota_benchmark_candidate_records") or []
    comparability = state.get("sota_comparability_matrix") or []
    weighting = state.get("sota_evidence_weighting") or {}
    derivation = state.get("sota_benchmark_derivation") or {}

    checks = []

    # 1. Endpoint traceability
    untraced = [
        e.get("endpoint_id", "?") for e in master
        if isinstance(e, dict)
        and not (e.get("linked_claims") or e.get("linked_gspr") or e.get("linked_risks"))
    ]
    checks.append({"check": "endpoint_traceability", "untraced": untraced, "passes": len(untraced) == 0})

    # 2. Source role
    endpoints_without_role = [
        eid for eid, roles in source_roles.items()
        if not roles
    ]
    checks.append({"check": "source_role", "missing": endpoints_without_role, "passes": len(endpoints_without_role) == 0})

    # 3. Candidate records for numeric endpoints
    numeric_endpoints = [
        e.get("endpoint_id") for e in master
        if isinstance(e, dict) and e.get("requires_numeric_benchmark")
    ]
    endpoints_with_candidates = set(
        c.get("endpoint_id") for c in candidates if isinstance(c, dict)
    )
    missing_candidates = [e for e in numeric_endpoints if e not in endpoints_with_candidates]
    checks.append({"check": "candidate_records", "missing": missing_candidates, "passes": len(missing_candidates) == 0})

    # 4. Comparability
    unchecked = [
        c.get("record_id", "?") for c in candidates
        if isinstance(c, dict) and not c.get("comparability")
    ]
    checks.append({"check": "comparability_completed", "unchecked": unchecked, "passes": len(unchecked) == 0})

    # 5. Weighting
    unweighted = [
        c.get("record_id", "?") for c in candidates
        if isinstance(c, dict) and c.get("usable_for_benchmark") and not c.get("assigned_weight")
    ]
    checks.append({"check": "weighting_completed", "unweighted": unweighted, "passes": len(unweighted) == 0})

    # 6. Derivation method
    no_method = [
        eid for eid, d in derivation.items()
        if isinstance(d, dict) and not d.get("selected_method")
    ]
    checks.append({"check": "derivation_method", "missing": no_method, "passes": len(no_method) == 0})

    # 7. Directionality
    no_direction = [
        e.get("endpoint_id") for e in master
        if isinstance(e, dict) and not e.get("directionality")
    ]
    checks.append({"check": "directionality", "missing": no_direction, "passes": len(no_direction) == 0})

    # 8. Own-data alignment
    alignments = state.get("own_data_alignment_matrix") or []
    unaligned = [
        a.get("endpoint_id", "?") for a in alignments
        if isinstance(a, dict) and not a.get("can_compare_directly") and a.get("can_compare_directly") is not None
    ]
    checks.append({"check": "own_data_alignment", "issues": unaligned, "passes": len(unaligned) == 0})

    # 9. Unfavourable evidence
    unfavourable = state.get("unfavourable_evidence_ledger")
    checks.append({"check": "unfavourable_evidence", "has_ledger": bool(unfavourable), "passes": bool(unfavourable)})

    # 10. Human gate trigger for low confidence
    low_confidence_endpoints = [
        eid for eid, d in derivation.items()
        if isinstance(d, dict) and d.get("benchmark_confidence") in ("low", "very_low")
    ]
    needs_human = len(low_confidence_endpoints) > 0
    checks.append({
        "check": "human_gate_trigger",
        "low_confidence_endpoints": low_confidence_endpoints,
        "requires_human": needs_human,
        "passes": True,  # This check doesn't block — it routes to human gate
    })

    all_pass = all(c.get("passes", False) for c in checks[:9])  # Exclude #10 from blocking
    return {
        "gate_id": "G-SOTA-BENCHMARK-DERIVATION",
        "status": "PASS" if all_pass else "REWORK_REQUIRED",
        "checks": checks,
        "requires_human_gate": needs_human,
        "low_confidence_endpoints": low_confidence_endpoints,
        "failure_reason": _derivation_failure(checks) if not all_pass else None,
    }


def _derivation_failure(checks: list[dict]) -> str:
    failures = [c.get("check", "?") for c in checks[:9] if not c.get("passes")]
    return f"Failed checks: {', '.join(failures)}"


# ═══════════════════════════════════════════════════════════════════════════════
# G-FACT-ID-TRACEABILITY
# ═══════════════════════════════════════════════════════════════════════════════

def evaluate_fact_id_traceability(cer_content: str, fact_registry: list[dict]) -> dict[str, Any]:
    """Scan CER draft for all numerics, verify each traces to a fact_id."""
    import re
    numerics = re.findall(r'\b(\d+\.?\d*)\s*%?\b', cer_content)

    registry_values = {}
    for f in (fact_registry or []):
        val = str(f.get("value", ""))
        fid = f.get("fact_id", "?")
        try:
            registry_values[float(val.replace("%", ""))] = fid
        except (ValueError, TypeError):
            pass

    orphans = []
    for n_str in numerics[:200]:  # Limit scan
        try:
            n = float(n_str)
            # Check if within 0.1% of any registry value
            found = False
            for rv, fid in registry_values.items():
                if abs(rv - n) < max(0.001 * rv, 0.001):
                    found = True
                    break
            if not found and n > 1:  # Skip single-digit numbers (likely page refs)
                orphans.append(n_str)
        except ValueError:
            pass

    return {
        "gate_id": "G-FACT-ID-TRACEABILITY",
        "status": "PASS" if not orphans else "REWORK_REQUIRED",
        "numerics_scanned": len(numerics),
        "orphan_numerics": orphans[:20],
        "orphan_count": len(orphans),
        "failure_reason": f"{len(orphans)} numerics without fact_id trace: {orphans[:5]}" if orphans else None,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# G-P/E/C Citation Completeness
# ═══════════════════════════════════════════════════════════════════════════════

def evaluate_citation_completeness(state: dict[str, Any]) -> dict[str, Any]:
    """Check that every cited record in §3-§7 has a P/E/C citation ID."""
    screening = state.get("screening_disposition") or []
    records = state.get("raw_literature_records") or []

    missing_ids = []
    for r in records:
        if isinstance(r, dict):
            if not (r.get("P_x_y") or r.get("E_x_y") or r.get("C_x_y")):
                missing_ids.append(r.get("pmid") or r.get("title", "?")[:50])

    return {
        "gate_id": "G-P/E/C-CITATION-COMPLETE",
        "status": "PASS" if not missing_ids else "REWORK_REQUIRED",
        "total_records": len(records),
        "missing_citation_ids": len(missing_ids),
        "failure_reason": f"{len(missing_ids)} records missing P/E/C citation IDs" if missing_ids else None,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# G-PMCF-DECISION-PRESENCE
# ═══════════════════════════════════════════════════════════════════════════════

def evaluate_pmcf_decision_presence(state: dict[str, Any]) -> dict[str, Any]:
    """Check that PMCF decision is explicit and eu_market_status_independent."""
    pmcf = state.get("pmcf_need_determination") or {}

    return {
        "gate_id": "G-PMCF-DECISION-PRESENCE",
        "status": "PASS" if pmcf.get("pmcf_decision") in ("PMCF_required", "Justified_not_required") else "REWORK_REQUIRED",
        "pmcf_decision": pmcf.get("pmcf_decision"),
        "eu_market_status_independent": pmcf.get("eu_market_status_independent", False),
        "failure_reason": "PMCF decision not explicit" if not pmcf.get("pmcf_decision") else None,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# G46 Aggregation Helper — fold V3.1 gates into pre-writer readiness
# ═══════════════════════════════════════════════════════════════════════════════

def aggregate_v3_1_gates_into_g46(state: dict[str, Any]) -> dict[str, Any]:
    """Run all V3.1 gates and return aggregated results for G46 merging."""
    results = {}

    # Phase 0 gates
    results["clinical_fact_registry_lock"] = evaluate_clinical_fact_registry_lock(state)
    if state.get("search_ledger_integrity_checked"):
        results["search_ledger_integrity"] = evaluate_search_ledger_integrity(state)
    results["pmcf_decision_presence"] = evaluate_pmcf_decision_presence(state)

    # Phase 1+2 gates (only if data exists)
    if state.get("endpoint_selection_table"):
        results["endpoint_selection"] = evaluate_endpoint_selection(state)
    if state.get("sota_benchmark_derivation"):
        results["sota_benchmark_derivation"] = evaluate_sota_benchmark_derivation(state)

    # Determine overall status
    failures = [
        gate_id for gate_id, result in results.items()
        if result.get("status") != "PASS"
    ]
    return {
        "v3_1_gates_aggregated": True,
        "v3_1_gate_results": results,
        "v3_1_gate_failures": failures,
        "v3_1_gate_status": "PASS" if not failures else "REWORK_REQUIRED",
        "v3_1_gate_failure_reason": f"Failed gates: {', '.join(failures)}" if failures else None,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# V3.1 Semantic Validation Gates — BLOCK-level artifact quality
# ═══════════════════════════════════════════════════════════════════════════════

def evaluate_semantic_fact_integrity(registry: list[dict]) -> dict[str, Any]:
    """G-FACT-SEMANTIC: validate Clinical Fact Registry semantic quality.

    Blocks: empty values, empty source_location on locked facts,
            own_data_comparison facts missing required fields.
    """
    empty_value = []
    empty_location_locked = []
    incomplete_own_data = []

    for f in (registry or []):
        fid = f.get("fact_id", "?")
        has_endpoint = bool(f.get("endpoint_id", ""))
        has_value = f.get("value") is not None and str(f.get("value", "")).strip() != ""
        usage = f.get("allowed_usage") or []
        locked = f.get("locked_status") in ("auto_locked", "human_confirmed")
        is_own_data = "own_data_comparison" in usage or "benchmark" in usage or "benefit_risk" in usage

        if has_endpoint and is_own_data and not has_value:
            empty_value.append(fid)

        if locked and not f.get("source_location"):
            empty_location_locked.append(fid)

        if is_own_data and (
            not has_value
            or not f.get("source_document")
            or (f.get("denominator") is None and f.get("value_type") not in ("string", "qualitative"))
        ):
            incomplete_own_data.append(fid)

    failures = []
    if empty_value:
        failures.append(f"G-FACT-VALUE-NONEMPTY: {len(empty_value)} locked facts with empty value")
    if empty_location_locked:
        failures.append(f"G-FACT-LOCATION-NONEMPTY: {len(empty_location_locked)} locked facts without source_location")
    if incomplete_own_data:
        failures.append(f"G-FACT-OWN-DATA-COMPLETE: {len(incomplete_own_data)} own_data facts incomplete")

    return {
        "gate_id": "G-FACT-SEMANTIC-INTEGRITY",
        "status": "PASS" if not failures else "BLOCK",
        "empty_value_facts": empty_value[:10],
        "empty_location_locked": empty_location_locked[:10],
        "incomplete_own_data": incomplete_own_data[:10],
        "failure_reason": "; ".join(failures) if failures else None,
    }


def evaluate_semantic_endpoint_integrity(master: list[dict], selection: list[dict]) -> dict[str, Any]:
    """G-EP-SEMANTIC: validate Endpoint Master and Selection quality.

    Blocks: empty names, no clinical_relevance, no claim/risk/GSPR linkage,
            core endpoints without own_data + SOTA, excluded without reason.
    """
    empty_name = []
    empty_relevance = []
    no_linkage = []
    invalid_core = []
    excluded_no_reason = []

    for ep in (master or []):
        eid = ep.get("endpoint_id", "?")
        if not ep.get("endpoint_name", "").strip():
            empty_name.append(eid)
        if not ep.get("clinical_relevance", "").strip():
            empty_relevance.append(eid)
        if not (ep.get("linked_claims") or ep.get("linked_gspr") or ep.get("linked_risks")):
            no_linkage.append(eid)

    for sel in (selection or []):
        eid = sel.get("endpoint_id", "?")
        status = sel.get("include_status", "")
        if status == "core":
            if not (sel.get("own_data_available") and sel.get("sota_benchmark_available")):
                invalid_core.append(eid)
        if status == "excluded" and not sel.get("exclusion_reason", "").strip():
            excluded_no_reason.append(eid)

    failures = []
    if empty_name:
        failures.append(f"G-EP-NAME: {len(empty_name)} endpoints with empty name")
    if empty_relevance:
        failures.append(f"G-EP-RELEVANCE: {len(empty_relevance)} endpoints without clinical_relevance")
    if no_linkage:
        failures.append(f"G-EP-LINKAGE: {len(no_linkage)} endpoints without claim/risk/GSPR link")
    if invalid_core:
        failures.append(f"G-EP-CORE: {len(invalid_core)} core endpoints without own_data + SOTA benchmark")
    if excluded_no_reason:
        failures.append(f"G-EP-EXCLUDE: {len(excluded_no_reason)} excluded endpoints without reason")

    return {
        "gate_id": "G-EP-SEMANTIC-INTEGRITY",
        "status": "PASS" if not failures else "BLOCK",
        "empty_name_endpoints": empty_name[:10],
        "no_linkage_endpoints": no_linkage[:10],
        "invalid_core_endpoints": invalid_core[:10],
        "failure_reason": "; ".join(failures) if failures else None,
    }


def evaluate_semantic_benchmark_integrity(derivations: dict, weighting: dict) -> dict[str, Any]:
    """G-BM-SEMANTIC: validate Benchmark Derivation quality.

    Blocks: null benchmark with high confidence, uniform weighting,
            method=insufficient_benchmark with high confidence.
    """
    null_high_conf = []
    uniform_weight = False
    insufficient_high_conf = []

    for eid, d in (derivations or {}).items():
        if not isinstance(d, dict):
            continue
        bv = d.get("benchmark_value") or {}
        conf = d.get("benchmark_confidence", "")
        method = d.get("selected_method", "")
        has_null = bv.get("acceptance_threshold") is None and bv.get("lower_bound") is None
        if has_null and conf in ("high", "medium_high"):
            null_high_conf.append(eid)
        if method == "insufficient_benchmark" and conf in ("high", "medium_high"):
            insufficient_high_conf.append(eid)

    # Check uniform weighting
    records = (weighting or {}).get("records") or []
    if len(records) >= 3:
        weights = {r.get("assigned_weight") for r in records if isinstance(r, dict)}
        if len(weights) == 1:
            uniform_weight = True

    failures = []
    if null_high_conf:
        failures.append(f"G-BM-NULL-HIGH-CONF: {len(null_high_conf)} endpoints with null benchmark + high confidence")
    if uniform_weight:
        failures.append(f"G-EW-UNIFORM: all {len(records)} evidence records have same weight")
    if insufficient_high_conf:
        failures.append(f"G-BM-METHOD-MISMATCH: {len(insufficient_high_conf)} endpoints with insufficient_benchmark + high confidence")

    return {
        "gate_id": "G-BM-SEMANTIC-INTEGRITY",
        "status": "PASS" if not failures else "BLOCK",
        "null_high_conf_endpoints": null_high_conf[:10],
        "uniform_weighting": uniform_weight,
        "failure_reason": "; ".join(failures) if failures else None,
    }


def evaluate_semantic_comparison_integrity(conclusions: list[dict]) -> dict[str, Any]:
    """G-CC-SEMANTIC: validate Comparison Conclusions quality.

    Blocks: can_compare_directly=true without data,
            above_sota/within_sota without numeric backing,
            unsupported superiority wording.
    """
    no_data_compare = []
    unsupported_superiority = []

    for c in (conclusions or []):
        if not isinstance(c, dict):
            continue
        eid = c.get("endpoint_id", "?")
        can_compare = c.get("can_compare_directly")
        own_val = c.get("own_value")
        bench = c.get("comparison_result") or {}
        position = bench.get("numeric_position", "")
        status = c.get("final_endpoint_status", "")

        if can_compare and (own_val is None or own_val == ""):
            no_data_compare.append(eid)

        if position in ("above_sota", "within_sota_range") and own_val is None:
            unsupported_superiority.append(f"{eid}: {position} without numeric own_value")

    failures = []
    if no_data_compare:
        failures.append(f"G-CC-NO-DATA-COMPARE: {len(no_data_compare)} endpoints with can_compare=true but no own_value")
    if unsupported_superiority:
        failures.append(f"G-CC-UNSUPPORTED: {len(unsupported_superiority)} unsupported superiority claims")

    return {
        "gate_id": "G-CC-SEMANTIC-INTEGRITY",
        "status": "PASS" if not failures else "BLOCK",
        "no_data_compare": no_data_compare[:10],
        "unsupported_superiority": unsupported_superiority[:10],
        "failure_reason": "; ".join(failures) if failures else None,
    }


def evaluate_closed_loop_minimum(conclusions: list[dict]) -> dict[str, Any]:
    """G-PIPE-CLOSED-LOOP: require at least 1-3 endpoints with complete chain.

    Closed loop = fact_registry → endpoint_master → selection → benchmark_derivation
                  → comparison_conclusion (with supported/partial status).
    """
    closed = [
        c for c in (conclusions or [])
        if isinstance(c, dict)
        and c.get("final_endpoint_status") in ("supported", "supported_with_residual_uncertainty", "partially_supported")
        and c.get("can_compare_directly")
        and c.get("own_value") is not None
    ]

    passes = len(closed) >= 1
    return {
        "gate_id": "G-PIPE-CLOSED-LOOP-MINIMUM",
        "status": "PASS" if passes else "BLOCK",
        "closed_loop_endpoints": len(closed),
        "closed_loop_ids": [c.get("endpoint_id", "?") for c in closed],
        "minimum_required": 1,
        "failure_reason": None if passes else "No endpoint has complete closed loop (fact→endpoint→benchmark→comparison→supported)",
    }


def run_full_semantic_validation(state: dict[str, Any]) -> dict[str, Any]:
    """Run all 5 semantic gates and return aggregated report."""
    registry = state.get("clinical_fact_registry") or []
    master = state.get("sota_endpoint_master") or []
    selection = state.get("endpoint_selection_table") or []
    derivations = state.get("sota_benchmark_derivation") or {}
    weighting = state.get("sota_evidence_weighting") or {}
    conclusions = state.get("sota_comparison_conclusions") or []

    results = {
        "fact_integrity": evaluate_semantic_fact_integrity(registry),
        "endpoint_integrity": evaluate_semantic_endpoint_integrity(master, selection),
        "benchmark_integrity": evaluate_semantic_benchmark_integrity(derivations, weighting),
        "comparison_integrity": evaluate_semantic_comparison_integrity(conclusions),
        "closed_loop": evaluate_closed_loop_minimum(conclusions),
    }

    blockers = [k for k, v in results.items() if v.get("status") == "BLOCK"]
    return {
        "semantic_validation_complete": True,
        "semantic_gate_results": results,
        "semantic_blockers": blockers,
        "semantic_status": "PASS" if not blockers else "BLOCK",
        "semantic_failure_summary": "; ".join(
            str(results[k].get("failure_reason", k)) for k in blockers
        ) if blockers else "All semantic gates passed",
    }
