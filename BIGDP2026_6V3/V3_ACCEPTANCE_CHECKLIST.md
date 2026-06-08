# BIGDP2026.6V_3 — Acceptance Checklist

**States:** ☐ NOT_CHECKED | ✅ PASS | ❌ FAIL | ⏭️ DEFERRED
**Rule:** 无 code + test + runtime + asset + regulatory_decision evidence = 不能标 PASS。
**Evidence columns per item:** code_evidence | test_evidence | runtime_evidence | asset_evidence | regulatory_decision_evidence | allowed_closure_level | human_gate_if_ambiguous

---

## Batch E — Clinical Fact Extraction V2

- [ ] E.1 clinical_fact_registry_v2 schema defined and documented
- [ ] E.2 Statistical fact parser: HR extraction from text (e.g., "HR 0.72 (95% CI 0.58–0.89)")
- [ ] E.3 Statistical fact parser: RR extraction
- [ ] E.4 Statistical fact parser: OR extraction
- [ ] E.5 Statistical fact parser: CI extraction with Wilson verification
- [ ] E.6 Statistical fact parser: p-value extraction
- [ ] E.7 Statistical fact parser: median/IQR extraction
- [ ] E.8 Subgroup detector identifies and labels subgroup facts
- [ ] E.9 Table/figure extractor via liteparse produces clinical facts
- [ ] E.10 Follow-up duration parser
- [ ] E.11 AE severity extractor
- [ ] E.12 ≥50 facts from test fixtures
- [ ] E.13 ≥10 table-derived facts
- [ ] E.14 ≥10 CI/range/statistical facts
- [ ] E.15 ≥5 subgroup facts with explicit labels
- [ ] E.16 0 orphan numeric facts (all have PMID or source anchor)
- [ ] E.17 Denominator validator integration (consumes registry_v2)
- [ ] E.18 Backward compatibility: existing tests pass
- [ ] E.19 Registry_v2 wired into graph and consumed by downstream nodes
- [ ] E.20 All Batch E tests pass

## Batch F — Semantic Support + Equivalence

- [ ] F.1 Semantic support validator: endpoint_match check
- [ ] F.2 Semantic support validator: population_match check
- [ ] F.3 Semantic support validator: indication_match check
- [ ] F.4 Semantic support validator: directness check
- [ ] F.5 Semantic support validator: support_strength check
- [ ] F.6 Semantic support validator: contradiction detection
- [ ] F.7 Irrelevant evidence linked to claim → FAIL
- [ ] F.8 Weak evidence strong conclusion → FAIL
- [ ] F.9 Indirect as direct without limitation → FAIL
- [ ] F.10 Semantic validator integrated into G43 (or as G43 sub-check)
- [ ] F.11 G46 consumes G43 semantic results
- [ ] F.12 Equivalence gate: 3-dim technical comparison
- [ ] F.13 Equivalence gate: 3-dim biological comparison
- [ ] F.14 Equivalence gate: 3-dim clinical comparison
- [ ] F.15 Equivalence gate: differences impact analysis
- [ ] F.16 Equivalence gate: data access check
- [ ] F.17 Equivalence gate: no-equivalence path support
- [ ] F.18 Equivalent evidence limitation propagation to Writer
- [ ] F.19 EQV Rulebook rules imported at runtime (grep confirmed)
- [ ] F.20 All Batch F tests pass

## Batch G — Domain Library + BR/GSPR

- [ ] G.1 endpoint_domain_templates.yaml exists with ≥5 domains
- [ ] G.2 Domain template: hemostasis/wound closure
- [ ] G.3 Domain template: ablation
- [ ] G.4 Domain template: implant/orthopaedic
- [ ] G.5 Domain template: cardiovascular support
- [ ] G.6 Domain template: surgical instrument
- [ ] G.7 Domain template loads at runtime
- [ ] G.8 Endpoint classifier consumes domain template for context
- [ ] G.9 Unknown domain → generic fallback with limitation
- [ ] G.10 benefit_to_evidence_crosswalk: every benefit has linked evidence
- [ ] G.11 risk_to_mitigation_crosswalk: every risk has mitigation
- [ ] G.12 GSPR_clinical_clause_to_evidence_matrix populated
- [ ] G.13 unresolved_uncertainty_register exists and populated
- [ ] G.14 BR conclusion strength validator: benefit without evidence → FAIL
- [ ] G.15 BR conclusion strength validator: risk without mitigation → REWORK
- [ ] G.16 BR conclusion strength validator: GSPR clause without evidence → REWORK
- [ ] G.17 BR conclusion strength validator: conclusion exceeds evidence → FAIL
- [ ] G.18 Unresolved uncertainty must map to PMCF/limitation/human gate → REWORK
- [ ] G.19 All Batch G tests pass

## Batch H — Writer QA + E2E

- [ ] H.1 Post-write QA: conclusion_overstatement detector
- [ ] H.2 Post-write QA: unsupported_positive_claim detector
- [ ] H.3 Post-write QA: no_source_numeric detector
- [ ] H.4 Post-write QA: denominator_misuse detector
- [ ] H.5 Post-write QA: endpoint_taxonomy_contradiction detector
- [ ] H.6 Post-write QA: missing_benchmark_limitation detector
- [ ] H.7 Post-write QA: pmcf_overclaim detector
- [ ] H.8 Post-write QA: sota_prose_consistency detector
- [ ] H.9 All 8 detectors produce output on representative CER text
- [ ] H.10 Conclusion exceeds ledger → FAIL
- [ ] H.11 No-source numeric in prose → FAIL
- [ ] H.12 Denominator misuse in prose → FAIL
- [ ] H.13 Endpoint taxonomy contradiction in prose → FAIL
- [ ] H.14 Clean prose with constraints → PASS
- [ ] H.15 Integration path documented and tested
- [ ] H.16 Holdout or artifact-level validation completed
- [ ] H.17 All Batch H tests pass

## Regression

- [ ] R.1 All BIGDP2026.6V_2 tests pass (542 baseline)
- [ ] R.2 No gate bypass introduced
- [ ] R.3 G46 chain intact

---

## Summary

| Batch | Items | Target |
|:---|:--:|:--:|
| E: Clinical Fact V2 | 20 | All PASS |
| F: Semantic + Equivalence | 20 | All PASS |
| G: Domain + BR/GSPR | 19 | All PASS |
| H: Writer QA + E2E | 17 | All PASS |
| Regression | 3 | All PASS |
| **Total** | **79** | |
