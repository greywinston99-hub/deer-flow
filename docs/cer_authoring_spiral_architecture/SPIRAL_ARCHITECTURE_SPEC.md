# SPIRAL ARCHITECTURE SPEC — V2

> CCD 签发 | 2026-05-11 | Phase 0 Architecture Freeze

## Target Graph

```text
[INTAKE]
initialize → input_gate → device_profile → claim_decomposition → pico_derivation

[EVIDENCE SPIRAL — max 3 rounds]
sota_search → literature_screening → evidence_appraisal → endpoint_extraction
  → evidence_sufficiency_gate (per-claim, not article count)
    PASS → exit spiral
    REWORK → query_expansion → back to sota_search (spiral_round++)
    BLOCKED → controlled_compromise (terminal, no Writer)

[EQUIVALENCE/RISK — parallel]
equivalence → vigilance → risk_gspr

[REASONING CHAIN GATES]
claim_evidence → gap_pmcf → benefit_risk → alignment
  → pre_writer_readiness_gate
    PASS → cer_writing (INVOKE)
    REWORK → specific upstream node per failure
    BLOCKED → controlled_compromise

[WRITER — conditional only]
cer_writing → human_style_review → nb_precheck → workbook → final_gates → export
```

## Key Changes from Current cer_authoring_v1

| Current | Target |
|---|---|
| Writer fixed node before gates | Writer conditional, after pre_writer_readiness_gate |
| Gates post-Writer, report-only | Gates distributed per stage, hard routing (REWORK/BLOCKED) |
| No cyclic edges | REWORK = graph-native back-edge to upstream node |
| Retrieval capped at 40 | No cap. 5-pool model. 20-40 = final inclusion target |
| Repair = external Claude supervisor | Repair = graph-native back-edge |
| Evidence: one-shot | Evidence: bounded spiral (max 3 rounds) |
| Sufficiency: article count | Sufficiency: per-claim evidence chain |

## Evidence Pool Model

`database_hit_count` → `retrieved_record_pool`(~200-500) → `screened_candidate_pool`(~50-100) → `fulltext_assessed_pool`(~20-50) → `final_cer_included_set`(20-40)

## Spiral Parameters

Max 3 rounds. Round 1: domain-locked. Round 2: query expansion + adjacent DB. Round 3: grey lit + registries. After round 3: BLOCKED.

## Pre-Writer Readiness

See `PRE_WRITER_READINESS_CONTRACT.md`. Aggregates: evidence_sufficiency + SOTA + claim_evidence + BR + alignment. All must PASS for Writer to invoke.

## Controlled Compromise

See `CONTROLLED_COMPROMISE_SPEC.md`. Terminal non-CER path. No Writer. No CER draft. Structured insufficiency report + human decision.

---

*CCD 签发：2026-05-11*
