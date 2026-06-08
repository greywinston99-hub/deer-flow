# CODEX BATCH PLAN DRAFT — EVIDENCE INTELLIGENCE CORE

> CCD 签发 | 2026-05-12 | Revised — Problem/Goal/Boundary Format

## Implementation Discipline

All 9 batches follow this format. Each batch is a self-contained task card. Codex decides implementation location subject only to: **graph.py / gates.py / agents.py MUST NOT be modified.**

---

## Batch EI-1: Evidence Scoring + Regulatory Admissibility

**PROBLEM**: Evidence quality is assessed ad-hoc by Writer LLM. No deterministic multi-factor scoring exists. No regulatory admissibility rules are enforced.

**GOAL**: Produce deterministic evidence scoring (6-factor weighted model) and regulatory admissibility checking (source_type × claim_type matrix). Both are rule-based, not LLM-prompt-based.

**BOUNDARY**: Do not modify graph.py / gates.py / agents.py. Do not present scores as regulatory certification. Mark all weights and thresholds as `provisional` (deterministic heuristic baselines).

**INPUT** (from I/O Contract): evidence_registry (source_type, device_relationship, comparability_band, study_design, sample_size, oxford_level), clinical_evidence_fact_table (extraction_confidence), evidence_conflict_report (conflict_type, severity)

**OUTPUT** (to I/O Contract): evidence_registry extended with evidence_strength_score, evidence_quality_tier, score_calibration_status, calibration_required, score_confidence, score_limitations, admissibility_level, admissibility_rationale

**ACCEPTANCE** (6 tests):
- subject_device RCT → excellent tier, admissibility ADMISSIBLE
- competitor_device → evidence_quality_tier ≤ marginal, admissibility NOT_ADMISSIBLE for safety claims
- Data quality scoring with sample_size boundaries (n=29→marginal, n=30→acceptable)
- Factor weight validation (sum = 1.0)
- Admissibility CONDITIONAL with condition check
- score_calibration_status = provisional, calibration_required = true

**STOP_CONDITION**: If any acceptance test fails → fix before EI-2.

---

## Batch EI-2: Device Claim Reasoning + Conclusion Strength

**PROBLEM**: No deterministic link between what evidence exists and what claims can be made. Writer can make unsupported strong statements.

**GOAL**: Per claim_type, define required_source_profile. Match available evidence to requirements. Produce claim_support_level (STRONG/MODERATE/WEAK/INSUFFICIENT) and max_conclusion_strength. Generate Writer conclusion constraints (allowed language, forbidden phrases, quantitative flag).

**BOUNDARY**: Do not modify graph.py / gates.py / agents.py. Required source profiles are default baselines — allow overrides for device_class/risk_level/intended_use/available_data_profile with audit ledger entries.

**INPUT**: evidence_registry (with EI-1 scores + admissibility), claim_decomposition (claim_id, claim_type, required_source_profile)

**OUTPUT**: claim_support_matrix, writer_conclusion_constraints

**ACCEPTANCE** (6 tests):
- safety_clinical + 2 subject device RCT → STRONG support
- safety_clinical + 0 subject device → INSUFFICIENT
- MEDIUM confidence → quantitative_allowed = false
- CRITICAL conflict → conclusion capped at INSUFFICIENT
- device_class=III override upgrades safety_clinical count to ≥2 (with audit entry)
- Writer forbidden_phrases correctly populated per conclusion strength

**STOP_CONDITION**: If STRONG/INSUFFICIENT boundaries not correctly gated → fix before EI-3.

---

## Batch EI-3: Absence of Evidence + Synthesis Method

**PROBLEM**: When evidence is missing, the system is silent. It doesn't distinguish between "didn't search" and "searched but found nothing" and "found but low quality".

**GOAL**: Classify evidence absence into 7 categories. Apply per-category reasoning rules (what can/cannot be said, conclusion cap, PMCF trigger, human review tier). Select evidence synthesis method per endpoint_cluster (benchmark / narrative / none).

**BOUNDARY**: Do not modify graph.py / gates.py / agents.py. Never conclude "safe" from absence. Never silently average conflicting evidence.

**INPUT**: evidence_registry, clinical_evidence_fact_table, evidence_conflict_report, semantic_endpoint_mapping_table (endpoint_cluster_id)

**OUTPUT**: evidence_registry extended with absence_category, absence_reasoning_output. synthesis_method_selections per endpoint_cluster.

**ACCEPTANCE** (6 tests):
- searched_not_found → conclusion capped at CAUTIOUS, not "safe"
- not_searched vs searched_not_found distinction
- ≥3 comparable studies → benchmark synthesis selected
- CRITICAL conflict → no synthesis (method = "none")
- found_but_low_quality → evidence role background, quality tier ≤ marginal
- CT.gov no_results → evidence kept, fact not created

**STOP_CONDITION**: If any absence category is misclassified → fix before EI-4.

---

## Batch EI-4: Equivalence / Similarity Bridging

**PROBLEM**: V2 defines device relationships (equivalent/similar/competitor/previous_gen) but no reasoning rules for how to bridge indirect evidence to claims.

**GOAL**: For each device_relationship, determine what claim types the evidence can bridge to, under what conditions, and with what maximum conclusion strength.

**BOUNDARY**: Do not modify graph.py / gates.py / agents.py. Never bridge competitor data to subject device claims. Equivalence requires all 3 rationale elements (technical/biological/clinical).

**INPUT**: evidence_registry (device_relationship, comparability_band, comparability_score_raw), V2 SIMILAR_COMPETITOR_EVIDENCE_SPEC allowed-use rules

**OUTPUT**: evidence_registry extended with bridging_assessment (bridge_to_claim_types, forbidden_claim_types, max_conclusion_strength, bridging_conditions, bridging_limitations)

**ACCEPTANCE** (4 tests):
- equivalent + rationale成立 → max MODERATE, bridge to safety+performance within scope
- similar → SOTA + risk context only, NOT for subject device claims → max CAUTIOUS
- competitor → NOT_ADMISSIBLE for all subject device claims, SOTA only
- equivalence rationale fails → downgrade to similar (with audit entry)

**STOP_CONDITION**: If competitor evidence bridges to subject device claims → CRITICAL FAILURE → fix before EI-5.

---

## Batch EI-5: SOTA Benchmark Synthesis

**PROBLEM**: SOTA benchmark is generated without checking whether studies are actually comparable. ≥3 count alone is insufficient.

**GOAL**: Apply 5-dimension comparability check (endpoint_definition, timepoint, population, procedure_context, device_relationship) before synthesizing. Compute benchmark statistics only for comparable studies. Generate benchmark_confidence.

**BOUNDARY**: Do not modify graph.py / gates.py / agents.py. Do not claim benchmark confidence = high without comparability verification. Do not build benchmarks from competitor-only data without flagging.

**INPUT**: clinical_evidence_fact_table (per endpoint_cluster), semantic_endpoint_mapping_table, evidence_registry (admissibility for SOTA), synthesis_method_selections (from EI-3)

**OUTPUT**: sota_benchmark_table (including excluded_studies, comparability_assessment, benchmark_confidence)

**ACCEPTANCE** (4 tests):
- ≥3 comparable studies (all 5 dimensions pass) → benchmark_confidence = high
- <3 comparable studies (after exclusions) → benchmark_confidence = insufficient_data
- Study excluded for timepoint incomparability → listed in excluded_studies with reason
- Competitor-only data → benchmark_confidence capped at medium, data source flagged

**STOP_CONDITION**: If non-comparable studies included in benchmark calculation → fix before EI-6.

---

## Batch EI-6: Benefit-Risk Reasoning

**PROBLEM**: No structured benefit-risk analysis. Writer LLM may claim "benefits outweigh risks" without quantitative backing.

**GOAL**: For each claim, identify and quantify benefits and risks from fact_table. Compare benefit vs risk magnitude. Apply uncertainty discount based on evidence quality. Produce overall BR judgment with br_acceptability_confidence.

**BOUNDARY**: Do not modify graph.py / gates.py / agents.py. Never output "favorable" when br_acceptability_confidence = insufficient_evidence. Never cite benefits without citing risks.

**INPUT**: claim_support_matrix (from EI-2), clinical_evidence_fact_table (benefit + risk endpoints), evidence_registry

**OUTPUT**: benefit_risk_conclusion (overall_judgment, br_acceptability_confidence, per_claim_benefit, per_claim_risk, uncertainty_discounts)

**ACCEPTANCE** (4 tests):
- Clear benefit > risk + high confidence → favorable, br_acceptability_confidence = high
- Benefit ≈ risk → balanced or borderline
- br_acceptability_confidence = insufficient_evidence → blocked, no favorable output
- Uncertainty discount correctly lowers borderline to unfavorable when evidence is weak

**STOP_CONDITION**: If "favorable" output when evidence insufficient → BLOCK → fix before EI-7.

---

## Batch EI-7: PMCF Gap Reasoning

**PROBLEM**: PMCF gaps are not systematically identified from clinical data.

**GOAL**: Check 6 PMCF gap triggers against fact_table and evidence_registry. Determine gap_severity. Generate PMCF objectives from templates (no detail fabrication).

**BOUNDARY**: Do not modify graph.py / gates.py / agents.py. Do not auto-fill PMCF plan details (sample size, follow-up years, study center count). Template only.

**INPUT**: clinical_evidence_fact_table (follow_up, population_n, source_types), claim_support_matrix (missing_evidence_gaps), evidence_registry

**OUTPUT**: pmcf_gap_register (gap_id, gap_type, gap_severity, affected_claims, pmcf_objective_template, pmcf_method_suggestion)

**ACCEPTANCE** (4 tests):
- follow_up < expected_lifetime/2 + implantable → long_term_data gap, severity ≥ high
- Small sample + low expected AE rate → rare_event gap triggered
- All single-arm studies → comparator_gap triggered
- Multiple gaps per claim → correctly aggregated

**STOP_CONDITION**: If critical safety gap not detected → fix before EI-8.

---

## Batch EI-8: CER/RMF Crosswalk + Reasoning Audit Ledger

**PROBLEM**: No traceability between CER claims and RMF hazards. No full reasoning audit trail.

**GOAL**: Build CER/RMF crosswalk (traceability + consistency, not merged judgment). Record every reasoning step in audit_ledger with inputs, rule applied, outputs, assumptions, alternatives.

**BOUNDARY**: Do not modify graph.py / gates.py / agents.py. Crosswalk = traceability, NOT merged CER-RMF judgment. Every audit entry must trace to source fact.

**INPUT**: claim_support_matrix, benefit_risk_conclusion, pmcf_gap_register, risk_management_file (if available), all upstream reasoning outputs

**OUTPUT**: cer_rmf_crosswalk_table, reasoning_audit_ledger

**ACCEPTANCE** (4 tests):
- Safety claim → RMF hazard identification crosswalk with link_nature = traceability
- RMF risk control requires CER performance evidence → crosswalk created
- Audit entry traces conclusion to source fact (FACT-### in input_artifacts)
- Crosswalk mismatch (CER has AE data but RMF has no matching hazard) → flagged as HIGH

**STOP_CONDITION**: If any conclusion lacks audit trace to source fact → fix before EI-9.

---

## Batch EI-9: Human Review Packet + Validation Harness

**PROBLEM**: No structured human review workflow. All low-confidence items would flood human reviewer.

**GOAL**: Tiered human review (Tier 1 auto, Tier 2 flag, Tier 3 block). Generate human_review_packet with decision_options. Implement 24-case validation harness (8 positive + 8 negative + 8 boundary).

**BOUNDARY**: Do not modify graph.py / gates.py / agents.py. Only Tier 3 blocks. Never auto-promote fact confidence.

**INPUT**: All EI-1 through EI-8 outputs

**OUTPUT**: human_review_packet (tiered, with decision_options), validation harness test suite

**ACCEPTANCE** (6 tests):
- CRITICAL conflict → Tier 3, decision_required = true
- LOW confidence fact → Tier 1, auto-handled, not in packet
- HIGH conflict → Tier 2, decision_required = false
- All 8 negative/adversarial validation cases pass (N1-N8)
- Packet structure has all required fields
- Full integration: EI-1 through EI-9 regression passed (≥209 tests total)

**STOP_CONDITION**: If any Tier 3 condition does not block → critical failure → fix before pilot.

---

## Global Constraints

| Constraint | Applies To |
|---|---|
| graph.py / gates.py / agents.py MUST NOT be modified | All batches |
| All reasoning rules must be deterministic, not LLM-prompt-based | All batches |
| Codex decides implementation file placement | All batches |
| Each batch must pass its acceptance tests before next batch | Sequencing |
| Baseline 165 tests must continue to pass | All batches |

## Baseline

165 tests passing (V3-Core Batch 7.6 completion).

## Target

Baseline 165 + new 44 (EI-1:6 + EI-2:6 + EI-3:6 + EI-4:4 + EI-5:4 + EI-6:4 + EI-7:4 + EI-8:4 + EI-9:6) = **≥209 tests**.

---

*CCD 签发：2026-05-12 | Revised — Problem/Goal/Boundary Format*
