# BIGDP2026.6 — Phase 2: Expert Business Logic Ledger Contracts Report

**Date:** 2026-06-08
**Status:** CORE COMPLETE — All 3 schemas created, DAG nodes implemented, 15/15 tests pass
**Phase 1 Dependency:** Phase 1 READY_FOR_REVIEW ✅

---

## Summary

All three expert reasoning artifacts have been created:

| Ledger | Schema | DAG Node | Tests | Status |
|:---|:---|:---|:---:|:---:|
| CER_REASONING_LEDGER | `schemas/cer_reasoning_ledger.schema.json` | `_node_build_reasoning_ledger` | 5 pass | ✅ |
| IFU_CLAIM_EVOLUTION_LEDGER | `schemas/ifu_claim_evolution_ledger.schema.json` | `_node_build_ifu_evolution_ledger` | 4 pass | ✅ |
| BENCHMARK_DERIVATION_TRACE | `schemas/benchmark_derivation_trace.schema.json` | `_node_build_benchmark_trace` | 4 pass | ✅ |

---

## CER_REASONING_LEDGER

**Schema:** `schemas/cer_reasoning_ledger.schema.json` (JSON Schema 2020-12)

Fields:
- `product_identity_reasoning` — device name, class, intended use, MoA, target population, equivalence
- `claims[]` — per-claim: classification (clinical_performance/safety/usability/warning/non_clinical), criticality (high/medium/low), evidence_support_type (direct/indirect/equivalent/manufacturer/PMS/insufficient), endpoint_rationale, benchmark_rationale, gap_disposition (no_gap/PMCF/labeling/risk_control/cannot_support), conclusion_strength (strong/moderate/limited/not_supported)
- `overall_assessment` — aggregate counts, PMCF recommendation, overall readiness

**Node:** `_node_build_reasoning_ledger` in `graph.py:1577-1650`
- Aggregates from: `claim_ledger`, `claim_evidence_matrix`, `device_profile`, `endpoint_registry`, `sota_benchmark_table`
- Every claim has non-null `conclusion_strength`

---

## IFU_CLAIM_EVOLUTION_LEDGER

**Schema:** `schemas/ifu_claim_evolution_ledger.schema.json` (JSON Schema 2020-12)

5-stage tracking per claim:
1. `stage_1_ifu_text` — raw IFU text with page/section/line reference
2. `stage_2_extracted_claim` — extracted claim form with transformation reason
3. `stage_3_classified_claim` — regulatory classification
4. `stage_4_evidence_supported_claim` — evidence-linked claim
5. `stage_5_final_cer_claim` — final Writer-ready wording

Evolution flags: claim_strengthened, claim_narrowed, safety_qualifier_added, marketing_language_detected, marketing_language_downgraded, requires_human_review.

**Node:** `_node_build_ifu_evolution_ledger` in `graph.py:1653-1740`
- Detects marketing language keywords
- Flags claims needing human review

---

## BENCHMARK_DERIVATION_TRACE

**Schema:** `schemas/benchmark_derivation_trace.schema.json` (JSON Schema 2020-12)

Per-endpoint fields:
- `source_studies` — PMID, author, year, design, sample_size, relevance_weight
- `benchmark_value_range` — point_estimate/range/pooled/narrative with CI
- `population_comparability` — direct_match/comparable/partial_overlap/different/unknown
- `device_comparability` — same_device/similar_device/alternative_therapy/different
- `directness` — direct/indirect/fallback
- `confidence` — high/medium/low/insufficient
- `acceptability_rationale` — non-empty for all endpoints
- `alternatives_rejected_rationale` — required when directness=fallback

**Node:** `_node_build_benchmark_trace` in `graph.py:1743-1818`
- Aggregates from: `sota_benchmark_table`, `endpoint_registry`, `evidence_registry`

---

## Tests

**File:** `backend/packages/harness/deerflow/runtime/cer_authoring/tests/test_phase2_ledgers.py` (15 tests)

| # | Test | Status |
|:---|:---|:---:|
| 1-2 | CER_REASONING_LEDGER schema existence + required fields | ✅ |
| 3-5 | Node produces valid ledger, claim-evidence linkage, gap disposition | ✅ |
| 6-7 | IFU_CLAIM_EVOLUTION_LEDGER schema existence + 5-stage structure | ✅ |
| 8-9 | Node produces ledger, marketing language detection | ✅ |
| 10-11 | BENCHMARK_DERIVATION_TRACE schema existence + required fields | ✅ |
| 12-13 | Node produces trace, fallback alternatives rationale | ✅ |
| 14-15 | Integration: all 3 ledgers produced, all 3 schemas validate | ✅ |

**All 15 tests pass.**

---

## Acceptance Checklist Status (Sections C, D, E)

| Item | Description | Status | Evidence |
|:---|:---|:---:|:---|
| C.1 | `cer_reasoning_ledger.schema.json` exists | ✅ PASS | `schemas/cer_reasoning_ledger.schema.json` |
| C.2 | Schema includes all required fields | ✅ PASS | JSON Schema validation |
| C.3 | DAG node `_node_build_reasoning_ledger` exists | ✅ PASS | `graph.py:1577` |
| C.4 | Node executes before G46 | 🔶 PARTIAL | Node exists; DAG edge not yet wired |
| C.5 | Ledger populated from upstream artifacts | ✅ PASS | Aggregates from 5 state artifacts |
| C.6 | Every claim has non-null conclusion_strength | ✅ PASS | `test_node_produces_valid_ledger` |
| D.1 | `ifu_claim_evolution_ledger.schema.json` exists | ✅ PASS | `schemas/ifu_claim_evolution_ledger.schema.json` |
| D.2 | 5-stage evolution structure | ✅ PASS | Schema validated |
| D.3 | DAG node `_node_build_ifu_evolution_ledger` exists | ✅ PASS | `graph.py:1653` |
| D.6 | Marketing language detection | ✅ PASS | `test_marketing_language_detection` |
| E.1 | `benchmark_derivation_trace.schema.json` exists | ✅ PASS | `schemas/benchmark_derivation_trace.schema.json` |
| E.2 | Per-endpoint required fields | ✅ PASS | Schema validated |
| E.3 | DAG node `_node_build_benchmark_trace` exists | ✅ PASS | `graph.py:1743` |
| E.5 | Non-empty acceptability_rationale | ✅ PASS | `test_node_produces_valid_trace` |
| E.6 | Fallback alternatives_rejected_rationale | ✅ PASS | `test_fallback_endpoint_has_alternatives_rationale` |

---

## Remaining for Phase 2

- [ ] C.7: G46 consumes CER_REASONING_LEDGER (Phase 3 integration)
- [ ] C.8: LEDGER appears in CER_INPUT_PACKAGE.json export (Phase 4 integration)
- [ ] D.4/D.5: IFU evolution node detects scope narrowing/safety qualifiers (enhancement)
- [ ] D.7: Writer consumes IFU evolution ledger (Phase 4 integration)
- [ ] E.7: BENCHMARK_DERIVATION_TRACE in CER_INPUT_PACKAGE.json (Phase 4 integration)

These integrations are planned for Phase 3 (Gate Integration) and Phase 4 (Handoff).
