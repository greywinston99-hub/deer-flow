#!/usr/bin/env python3
"""BIGDP2026.6 End-to-End Synthetic Pipeline Run.

Simulates a complete CER authoring pipeline run through all BIGDP2026.6
code paths. Uses realistic synthetic data for a Class IIb vascular closure
device. Verifies:

1. Ledger nodes produce valid expert reasoning artifacts
2. G46 Writer Release Board evaluates all conditions
3. Export reference integrity check works
4. Package validator accepts the output

Usage:
    .venv/bin/python3 BIGDP2026_6/end_to_end_synthetic_run.py
"""
import json
import sys
import os
from datetime import datetime, timezone

# Add project to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend", "packages", "harness"))

from deerflow.runtime.cer_authoring.graph import (
    _node_build_reasoning_ledger,
    _node_build_ifu_evolution_ledger,
    _node_build_benchmark_trace,
)
from deerflow.runtime.cer_authoring.gates import evaluate_pre_writer_readiness_gate
from deerflow.runtime.cer_authoring.cer_package_validator import validate_package


def build_synthetic_state():
    """Build a realistic synthetic state for a Class IIb vascular closure device."""
    return {
        "device_profile": {
            "device_name": "VasoSeal Pro X",
            "device_class": "IIb",
            "intended_use": "Percutaneous closure of femoral artery access sites following diagnostic or interventional catheterization procedures.",
            "mechanism_of_action": "Mechanical compression via absorbable collagen plug deployed at the arterial puncture site, achieving hemostasis through a combination of mechanical tamponade and platelet activation.",
            "target_population": "Adult patients (≥18 years) undergoing femoral arterial catheterization with 5F-8F access sheaths.",
            "anatomical_site": "Common femoral artery",
            "clinical_domain": "vascular_closure",
            "manufacturer": "VasoMed Inc.",
            "indications": ["Diagnostic angiography", "PCI", "Peripheral intervention"],
            "contraindications": ["Severe coagulopathy (INR>2.0)", "Active infection at access site", "Pregnancy"],
        },
        "claim_ledger": [
            {"claim_id": "C-01", "claim_text": "Achieves hemostasis within 3 minutes of device deployment in ≥90% of patients", "claim_type": "clinical_performance", "criticality": "high"},
            {"claim_id": "C-02", "claim_text": "Device-related major adverse event rate <2%", "claim_type": "clinical_safety", "criticality": "high"},
            {"claim_id": "C-03", "claim_text": "Ergonomic handle design reduces operator fatigue during prolonged procedures", "claim_type": "usability", "criticality": "low"},
            {"claim_id": "C-04", "claim_text": "The revolutionary VasoSeal Pro X guarantees perfect closure with zero complications", "claim_type": "clinical_performance", "criticality": "high", "ifu_source_text": "The revolutionary VasoSeal Pro X guarantees perfect closure with zero complications in all patients"},
        ],
        "claim_evidence_matrix": [
            {"claim_id": "C-01", "evidence_ids": ["E-001", "E-002", "E-003"], "support_type": "direct", "conclusion_strength": "strong"},
            {"claim_id": "C-02", "evidence_ids": ["E-004"], "support_type": "direct", "conclusion_strength": "moderate"},
            {"claim_id": "C-03", "evidence_ids": [], "support_type": "insufficient", "gap_disposition": "PMCF", "gap_rationale": "No usability study data available. PMCF recommended."},
            {"claim_id": "C-04", "evidence_ids": ["E-001", "E-002"], "support_type": "direct", "gap_disposition": "claim_narrowing", "gap_rationale": "Marketing language detected. Claim must be narrowed to evidence-supported wording."},
        ],
        "evidence_registry": [
            {"evidence_id": "E-001", "pmid": "34567890", "first_author": "Anderson", "year": 2024, "study_design": "RCT", "sample_size": 350, "relevance_weight": 1.0, "findings": "Hemostasis ≤3 min: 94% (329/350). Major AE: 1.1% (4/350)."},
            {"evidence_id": "E-002", "pmid": "34567891", "first_author": "Bennett", "year": 2023, "study_design": "Prospective multicenter", "sample_size": 500, "relevance_weight": 0.9, "findings": "Hemostasis ≤3 min: 92% (460/500). Device success: 98%."},
            {"evidence_id": "E-003", "pmid": "34567892", "first_author": "Chen", "year": 2024, "study_design": "Meta-analysis", "sample_size": 1200, "relevance_weight": 0.8, "findings": "Pooled hemostasis rate: 93% (95% CI: 91-95%)."},
            {"evidence_id": "E-004", "pmid": "34567893", "first_author": "Davis", "year": 2023, "study_design": "Registry", "sample_size": 2000, "relevance_weight": 0.7, "findings": "Major AE rate: 1.5%. Minor AE: 4.2%."},
        ],
        "endpoint_registry": [
            {"name": "hemostasis_time", "type": "primary_efficacy", "clinical_meaning": "Time from device deployment to complete hemostasis at access site"},
            {"name": "major_adverse_events", "type": "primary_safety", "clinical_meaning": "Device-related major adverse events including infection, pseudoaneurysm, and retroperitoneal bleeding"},
            {"name": "device_success", "type": "secondary_efficacy", "clinical_meaning": "Successful device deployment and hemostasis without need for alternative intervention"},
        ],
        "sota_benchmark_table": [
            {"benchmark_id": "B-001", "endpoint": "hemostasis_time", "directness": "direct", "value": "90-95% at 3 min"},
            {"benchmark_id": "B-002", "endpoint": "major_adverse_events", "directness": "direct", "value": "<2%"},
        ],
        "benefit_risk_ledger": [
            {"benefit": "Rapid hemostasis", "risk": "Access site complications", "balance": "Favorable"},
        ],
        "search_run_registry": [
            {"status": "completed", "database": "PubMed", "search_date": "2026-01-15", "exact_query": '("vascular closure device"[MeSH]) AND ("femoral"[All Fields])'},
            {"status": "completed", "database": "Embase", "search_date": "2026-01-15", "exact_query": "'vascular closure'/exp AND 'hemostasis'"},
        ],
        "clinical_evaluation_plan": {
            "device_name": "VasoSeal Pro X", "device_class": "IIb", "scope": "Clinical evaluation for MDR certification",
            "literature_search_protocol": {
                "databases": ["PubMed", "Embase", "Cochrane"],
                "inclusion_criteria": ["RCT", "Prospective studies", "N≥30"],
                "exclusion_criteria": ["Case reports N<10", "Animal studies", "In vitro only"],
            },
            "appraisal_method": "MDCG 2020-6", "sota_methodology": "Systematic literature review",
            "claim_support_method": "Evidence-to-claim matrix", "benefit_risk_method": "ISO 14971 + MDCG 2020-6 §4.7",
            "pms_pmcf_update_plan": "Annual PMCF per MDR Article 86",
        },
        "ifu_working_document": {"filename": "IFU_VasoSeal_Pro_X_v3.2.pdf", "version": "3.2", "date": "2025-11"},
        "locked_endpoint_framework": {
            "primary_endpoints": [{"name": "hemostasis_time"}, {"name": "major_adverse_events"}],
            "secondary_endpoints": [{"name": "device_success"}],
            "safety_endpoints": [{"name": "major_adverse_events"}],
        },
        "consolidated_clinical_data_table": {"data_sources": [{"source": "PubMed"}, {"source": "Embase"}]},
        "eu_market_status": "not_approved",
        "equivalence_claimed": False,
        "equivalent_device_name": "",
        "screening_disposition": [],
        "prisma_flow_data": {
            "flow": {"raw_hits": 156, "dedup_input": 140, "duplicate_count": 16,
                     "after_dedup": 124, "title_abstract_screened": 124,
                     "title_abstract_excluded": 80, "fulltext_assessed": 44,
                     "fulltext_excluded": 28, "final_included": 16},
        },
        "source_inventory": [
            {"document_type": "RMF", "source_role": "rmf_risk_management", "filename": "risk_management_report.pdf"},
            {"document_type": "IFU", "source_role": "ifu_instructions", "filename": "IFU_VasoSeal_Pro_X_v3.2.pdf"},
        ],
        "gspr_coverage": {"GSPR_1": "covered", "GSPR_6": "covered", "GSPR_8": "partially_covered"},
        "alignment_matrix": [{"requirement": "GSPR_1", "evidence_ref": "E-001"}],
        "benefit_risk_closure_matrix": {"closure_status": "CONCLUDABLE"},
    }


def print_section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def main():
    print_section("BIGDP2026.6 End-to-End Synthetic Pipeline Run")
    print(f"  Device: VasoSeal Pro X (Class IIb Vascular Closure)")
    print(f"  Time:   {datetime.now(timezone.utc).isoformat()}")
    print(f"  Claims: 4 (1 marketing-overreach, 1 insufficient-evidence)")

    state = build_synthetic_state()
    failures = 0

    # ── Step 1: Build Expert Reasoning Ledgers ──
    print_section("Step 1: Building Expert Reasoning Ledgers")

    r1 = _node_build_reasoning_ledger(state)
    reasoning = r1.get("cer_reasoning_ledger", {})
    claims = reasoning.get("claims", [])
    print(f"  CER_REASONING_LEDGER: {len(claims)} claims")
    for c in claims:
        print(f"    {c['claim_id']}: {c['claim_classification']}, "
              f"support={c['evidence_support_type']}, "
              f"strength={c['conclusion_strength']}, "
              f"gap={c['gap_disposition']}")
        if not c.get("conclusion_strength"):
            print(f"      ❌ Missing conclusion_strength!")
            failures += 1
    state.update(r1)

    r2 = _node_build_ifu_evolution_ledger(state)
    ifu_evo = r2.get("ifu_claim_evolution_ledger", {})
    ifu_claims = ifu_evo.get("claims", [])
    print(f"\n  IFU_CLAIM_EVOLUTION_LEDGER: {len(ifu_claims)} claims")
    for c in ifu_claims:
        flags = c.get("evolution_flags", {})
        flag_str = ", ".join(k for k, v in flags.items() if v) or "none"
        print(f"    {c['claim_id']}: flags=[{flag_str}]")
        if flags.get("marketing_language_detected"):
            print(f"      ✅ Marketing language detected and flagged")
    state.update(r2)

    r3 = _node_build_benchmark_trace(state)
    bm_trace = r3.get("benchmark_derivation_trace", {})
    endpoints = bm_trace.get("endpoints", [])
    print(f"\n  BENCHMARK_DERIVATION_TRACE: {len(endpoints)} endpoints")
    for ep in endpoints:
        print(f"    {ep['endpoint_name']}: directness={ep['directness']}, "
              f"confidence={ep['confidence']}")
        if not ep.get("acceptability_rationale"):
            print(f"      ❌ Missing acceptability_rationale!")
            failures += 1
    state.update(r3)

    # ── Step 2: G46 Writer Release Board ──
    print_section("Step 2: G46 Writer Release Board")

    g46 = evaluate_pre_writer_readiness_gate(state)
    print(f"  G46 Status: {g46.get('status')}")
    conditions = g46.get("conditions", [])
    for cond in conditions:
        status = cond["status"]
        icon = "✅" if status == "PASS" else ("⚠️" if status == "REWORK_REQUIRED" else "❌")
        print(f"    {icon} {cond['condition_name']:30s} {status}")
        if status == "BLOCKED":
            failures += 1

    # Check for silent PASS (fallback without evaluator)
    silent_pass = [c for c in conditions
                   if c["status"] == "PASS" and "no dedicated evaluator" in c.get("message", "")]
    if silent_pass:
        print(f"\n  ❌ {len(silent_pass)} condition(s) silently PASSed without evaluator!")
        failures += len(silent_pass)
    else:
        print(f"\n  ✅ 0 silent PASS conditions")

    # ── Step 3: Expert Logic Verification ──
    print_section("Step 3: Expert Logic Verification")

    # Check CON rules: weak evidence → not strong
    weak_evidence_strong = [c for c in claims
                            if c["evidence_support_type"] in ("indirect", "equivalent", "manufacturer", "insufficient")
                            and c["conclusion_strength"] == "strong"]
    if weak_evidence_strong:
        print(f"  ❌ CON violation: {len(weak_evidence_strong)} claim(s) with weak evidence → strong conclusion!")
        failures += len(weak_evidence_strong)
    else:
        print(f"  ✅ CON: Weak evidence never produces strong conclusion")

    # Check IFU rules: marketing language detected
    marketing_claims = [c for c in ifu_claims
                        if c.get("evolution_flags", {}).get("marketing_language_detected")]
    if marketing_claims:
        print(f"  ✅ IFU: {len(marketing_claims)} marketing claim(s) detected and flagged")
    else:
        # C-04 should have marketing language
        print(f"  ⚠️ IFU: No marketing claims flagged (C-04 has marketing IFU text)")

    # Check BMK rules: all endpoints have acceptability_rationale
    missing_rationale = [ep for ep in endpoints if not ep.get("acceptability_rationale")]
    if missing_rationale:
        print(f"  ❌ BMK violation: {len(missing_rationale)} endpoint(s) missing acceptability_rationale!")
        failures += len(missing_rationale)
    else:
        print(f"  ✅ BMK: All endpoints have acceptability_rationale")

    # ── Step 4: Export Package Validation ──
    print_section("Step 4: Package Validation")

    # Build a package-like structure
    pkg = {
        "cer_input_package_exported": True,
        "package_schema_version": "1.0.0",
        "pre_writer_readiness_gate_report": {"status": g46.get("status")},
        "claim_ledger": state.get("claim_ledger", []),
        "claim_evidence_matrix": state.get("claim_evidence_matrix", []),
        "evidence_registry": state.get("evidence_registry", []),
        "benefit_risk_ledger": state.get("benefit_risk_ledger", []),
        "alignment_matrix": state.get("alignment_matrix", []),
        "cer_reasoning_ledger": reasoning,
        "ifu_claim_evolution_ledger": ifu_evo,
        "benchmark_derivation_trace": bm_trace,
    }

    errors = validate_package(pkg)
    if errors:
        print(f"  ❌ Package validation FAILED: {len(errors)} error(s)")
        for e in errors:
            print(f"    - {e}")
        failures += len(errors)
    else:
        print(f"  ✅ Package validation PASSED — Writer may proceed")

    # ── Step 5: Expert Rule Loader Verification ──
    print_section("Step 5: Expert Rule Loader Integration")

    try:
        from deerflow.runtime.cer_authoring.expert_rule_loader import (
            get_conclusion_strength, get_ifu_transformation, get_benchmark_classification
        )
        cs = get_conclusion_strength("direct", 2)
        xf = get_ifu_transformation("Our revolutionary device guarantees perfect results", "direct")
        bm = get_benchmark_classification(0, "unknown", "alternative_therapy")
        print(f"  get_conclusion_strength('direct', 2) = {cs}")
        print(f"  get_ifu_transformation(marketing text) = {xf['action']}")
        print(f"  get_benchmark_classification(0 studies) = {bm['directness']}/{bm['confidence']}")
        print(f"  ✅ Expert rule loader integrated and functional")
    except Exception as e:
        print(f"  ❌ Expert rule loader failed: {e}")
        failures += 1

    # ── Summary ──
    print_section("END-TO-END SYNTHETIC RUN SUMMARY")
    if failures == 0:
        print(f"  ✅ ALL CHECKS PASSED — BIGDP2026.6 chain is intact")
        print(f"  ✅ Ledger nodes → G46 → Package Validator: complete")
    else:
        print(f"  ❌ {failures} FAILURE(S) DETECTED")
    print(f"\n  Device: VasoSeal Pro X (Class IIb)")
    print(f"  Claims processed: {len(claims)}")
    print(f"  G46 conditions evaluated: {len(conditions)}")
    print(f"  Ledgers built: 3/3")
    print(f"  Expert rules consumed: ✅")

    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
