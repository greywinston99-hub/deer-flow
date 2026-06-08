# PHASE MANIFEST — CER/RMF EVIDENCE INTELLIGENCE CORE

> CCD 签发 | 2026-05-13 | Authoritative — supersedes all prior loose phase descriptions

## Phase Structure (Implementation Grouping)

```text
PHASE_0_READINESS
  → PHASE_1 (EI-1: Evidence Scoring + Admissibility)
  → PHASE_2 (EI-2~4: Claim Reasoning + Absence + Synthesis + Bridging)
  → PHASE_3 (EI-5~7: SOTA + BR + PMCF)
  → PHASE_4 (EI-8~9: Crosswalk + Audit + Human Review + Validation Harness)
  → PHASE_5 (Full Regression + Closeout)
  → PHASE_PILOT_VALIDATION
```

Each phase is a hard gate. No skipping. No parallel phases. Full per-batch detail below, organized under implementation phases.

**Reference**: `EI_CORE_EXECUTION_FRAMEWORK.md` for complete execution protocol, audit contract, failure classes, LOOP_STATE schema, and per-phase artifact requirements.

### Global Reference Specs (All Phases)

These 20 spec files are the authoritative EI Core spec set. Phase-specific specs are listed under each implementation phase below. The following are cross-cutting and not tied to a single phase:

| Spec | Purpose |
|---|---|
| `CER_RMF_EVIDENCE_INTELLIGENCE_CORE_MASTER_PLAN.md` | Master architecture, hard boundaries, integration points |
| `CLINICAL_FACT_LAYER_FINAL_SCOPE.md` | Fact layer boundary — referenced by all phases |
| `REASONING_INPUT_OUTPUT_CONTRACT_SPEC.md` | Exact I/O field definitions — binding on all phases |
| `CODEX_BATCH_PLAN_DRAFT_EI_CORE.md` | Per-batch PROBLEM/GOAL/BOUNDARY detail |
| `PRE_PILOT_EI_CORE_VALIDATION_CRITERIA.md` | Phase 5 validation criteria |

---

## PHASE_0 — Readiness Check

| Field | Value |
|---|---|
| **phase_id** | `PHASE_0_READINESS` |
| **status** | `PASS` — all 18 items confirmed (see `PHASE_0_EI_CORE_READINESS_REPORT.md`). Baseline: 165 passed, 7 warnings, 0 failed. |
| **specs** | `PHASE_0_EI_CORE_READINESS_REPORT.md` |
| **dependencies** | None (entry gate) |
| **allowed_scope** | Manifest verification, proof index verification, baseline test verification, stale-reference check, file inventory completeness |
| **forbidden_scope** | Code modification, spec modification beyond reconciliation patches, EI-1 implementation |
| **tests** | Baseline 165 tests passing ✅ |
| **claude_audit_checklist** | [x] 20 EI Core specs exist and match manifest, [x] 24 validation cases referenced, [x] ≥209 test target, [x] Codex implementation-location freedom, [x] 3 proof indexes present, [x] graph/gates/agents boundary in all batch cards, [x] Gate integration section in Master Plan, [x] Scoring as heuristic baselines, [x] Claim override with downgrade coupling, [x] SOTA 5-dim comparability, [x] V3-Core qualified status, [x] No stale 17/19/220 references, [x] Baseline 165 tests pass |
| **hard_stop_conditions** | Any proof index missing → STOP. Baseline tests fail → STOP. Stale 17/19/220 references → STOP. graph/gates/agents modification prescribed → STOP. |
| **downstream_consumption_expectation** | None. Phase 0 is verification-only. All EI outputs are staged-only until their consuming phase. |

---

## Implementation Phase 1 — EI-1

### PHASE_EI_1 — Evidence Scoring + Regulatory Admissibility

| Field | Value |
|---|---|
| **phase_id** | `PHASE_EI_1` |
| **status** | `AWAITING_OWNER_AUTHORIZATION` — PHASE_0_PASS achieved. Requires owner to authorize EI-1 start. |
| **specs** | `EVIDENCE_SCORING_MODEL_SPEC.md`, `REGULATORY_EVIDENCE_ADMISSIBILITY_SPEC.md`, `SCORING_CALIBRATION_AND_THRESHOLD_POLICY.md` |
| **dependencies** | PHASE_0_READINESS complete |
| **allowed_scope** | Implement 6-factor evidence scoring, regulatory admissibility matrix, provisional thresholds |
| **forbidden_scope** | graph.py / gates.py / agents.py. Presenting scores as regulatory certification. Hardcoding thresholds as stable. |
| **tests** | 6 new tests (see CODEX_BATCH_PLAN_DRAFT_EI_CORE.md) |
| **claude_audit_checklist** | [ ] Subject RCT → excellent tier, [ ] Competitor → ≤marginal + NOT_ADMISSIBLE, [ ] data quality boundaries, [ ] factor weight sum=1.0, [ ] admissibility CONDITIONAL check, [ ] calibration_required=true |
| **hard_stop_conditions** | Any test fails → STOP. graph/gates/agents modified → STOP. |
| **downstream_consumption_expectation** | `evidence_strength_score`, `evidence_quality_tier`, `admissibility_level` → **STAGED-ONLY** until PHASE_EI_2 consumes them via claim reasoning. Not read by Writer yet. |

---

## Implementation Phase 2 — EI-2~4

### PHASE_EI_2 — Device Claim Reasoning + Conclusion Strength

| Field | Value |
|---|---|
| **phase_id** | `PHASE_EI_2` |
| **status** | `NOT_AUTHORIZED` → requires PHASE_EI_1_PASS |
| **specs** | `DEVICE_CLAIM_REASONING_SPEC.md`, `CLAIM_CONCLUSION_STRENGTH_SPEC.md` |
| **dependencies** | PHASE_EI_1 (consumes evidence_strength_score, admissibility_level) |
| **allowed_scope** | Required source profiles, evidence-to-claim matching, claim_support_level, conclusion strength with override rules |
| **forbidden_scope** | graph.py / gates.py / agents.py. Downgrading profiles without gap/limitation/PMCF/cap coupling. |
| **tests** | 6 new tests |
| **claude_audit_checklist** | [ ] STRONG with 2 subject RCTs, [ ] INSUFFICIENT with 0 subject devices, [ ] quantitative_allowed gating, [ ] CRITICAL→INSUFFICIENT cap, [ ] device_class=III override in audit, [ ] forbidden_phrases per strength |
| **hard_stop_conditions** | INSUFFICIENT not gated → STOP. graph/gates/agents modified → STOP. |
| **downstream_consumption_expectation** | `claim_support_matrix`, `writer_conclusion_constraints` → **STAGED-ONLY** until PHASE_EI_9 integration + G46 bridge validates downstream consumption. |

---

## PHASE_EI_3 — Absence of Evidence + Synthesis Method

| Field | Value |
|---|---|
| **phase_id** | `PHASE_EI_3` |
| **status** | `NOT_AUTHORIZED` |
| **specs** | `ABSENCE_OF_EVIDENCE_REASONING_SPEC.md`, `EVIDENCE_SYNTHESIS_METHOD_POLICY.md` |
| **dependencies** | PHASE_EI_2 |
| **allowed_scope** | 7-category absence classification, per-category reasoning rules, synthesis method selection |
| **forbidden_scope** | graph.py / gates.py / agents.py. Concluding "safe" from absence. Silent conflict averaging. |
| **tests** | 6 new tests |
| **hard_stop_conditions** | Absence category misclassification → STOP. graph/gates/agents modified → STOP. |
| **downstream_consumption_expectation** | `absence_category`, `synthesis_method_selections` → **STAGED-ONLY** until consumed by SOTA/BR/PMCF. |

---

## PHASE_EI_4 — Equivalence / Similarity Bridging

| Field | Value |
|---|---|
| **phase_id** | `PHASE_EI_4` |
| **status** | `NOT_AUTHORIZED` |
| **specs** | `EQUIVALENCE_SIMILARITY_BRIDGING_SPEC.md` |
| **dependencies** | PHASE_EI_2 (V2 allowed-use rules) |
| **allowed_scope** | Bridging assessment per device_relationship, equivalence rationale check, conclusion cap |
| **forbidden_scope** | graph.py / gates.py / agents.py. Bridging competitor to subject device claims. |
| **tests** | 4 new tests |
| **hard_stop_conditions** | Competitor→subject device bridge → CRITICAL FAILURE → STOP. graph/gates/agents modified → STOP. |
| **downstream_consumption_expectation** | `bridging_assessment` → **STAGED-ONLY** until consumed by Claim Reasoning for indirect evidence claims. |

---

## Implementation Phase 3 — EI-5~7

### PHASE_EI_5 — SOTA Benchmark Synthesis

| Field | Value |
|---|---|
| **phase_id** | `PHASE_EI_5` |
| **status** | `NOT_AUTHORIZED` |
| **specs** | `SOTA_BENCHMARK_SYNTHESIS_SPEC.md` |
| **dependencies** | PHASE_EI_1 (scoring), PHASE_EI_3 (synthesis method), PHASE_EI_4 (bridging) |
| **allowed_scope** | 5-dim comparability, benchmark calculation, benchmark_confidence |
| **forbidden_scope** | graph.py / gates.py / agents.py. Including non-comparable studies. Claiming benchmark without comparability. |
| **tests** | 4 new tests |
| **hard_stop_conditions** | Non-comparable studies in benchmark → STOP. graph/gates/agents modified → STOP. |
| **downstream_consumption_expectation** | `sota_benchmark_table` → **STAGED-ONLY** until Writer consumption via conclusion constraints. |

---

## PHASE_EI_6 — Benefit-Risk Reasoning

| Field | Value |
|---|---|
| **phase_id** | `PHASE_EI_6` |
| **status** | `NOT_AUTHORIZED` |
| **specs** | `BENEFIT_RISK_REASONING_SPEC.md` |
| **dependencies** | PHASE_EI_1 (scoring), PHASE_EI_2 (claim support), PHASE_EI_5 (SOTA context) |
| **allowed_scope** | Benefit/risk identification, BR comparison, uncertainty discount, br_acceptability_confidence |
| **forbidden_scope** | graph.py / gates.py / agents.py. "favorable" when br_acceptability_confidence = insufficient_evidence. Benefits without risks. |
| **tests** | 4 new tests |
| **hard_stop_conditions** | "favorable" with insufficient evidence → BLOCK → STOP. graph/gates/agents modified → STOP. |
| **downstream_consumption_expectation** | `benefit_risk_conclusion` → **STAGED-ONLY** until Writer consumption + G46 bridge validation. |

---

## PHASE_EI_7 — PMCF Gap Reasoning

| Field | Value |
|---|---|
| **phase_id** | `PHASE_EI_7` |
| **status** | `NOT_AUTHORIZED` |
| **specs** | `PMCF_GAP_REASONING_SPEC.md` |
| **dependencies** | PHASE_EI_2 (claim support, missing gaps), PHASE_EI_6 (BR context) |
| **allowed_scope** | 6 gap triggers, gap_severity, PMCF objective templates |
| **forbidden_scope** | graph.py / gates.py / agents.py. Auto-filling PMCF plan details. |
| **tests** | 4 new tests |
| **hard_stop_conditions** | Critical safety gap not detected → STOP. graph/gates/agents modified → STOP. |
| **downstream_consumption_expectation** | `pmcf_gap_register` → **STAGED-ONLY** until Writer PMCF section + crosswalk consumption. |

---

## Implementation Phase 4 — EI-8~9

### PHASE_EI_8 — CER/RMF Crosswalk + Reasoning Audit Ledger

| Field | Value |
|---|---|
| **phase_id** | `PHASE_EI_8` |
| **status** | `NOT_AUTHORIZED` |
| **specs** | `CER_RMF_EVIDENCE_CROSSWALK_SPEC.md`, `REASONING_AUDIT_LEDGER_SPEC.md` |
| **dependencies** | PHASE_EI_2 (claims), PHASE_EI_7 (PMCF), all upstream reasoning |
| **allowed_scope** | Crosswalk entries (traceability/consistency only), audit ledger with full trace |
| **forbidden_scope** | graph.py / gates.py / agents.py. Merged CER-RMF judgment. Audit gaps. |
| **tests** | 4 new tests |
| **hard_stop_conditions** | Conclusion lacks audit trace to source fact → STOP. graph/gates/agents modified → STOP. |
| **downstream_consumption_expectation** | `cer_rmf_crosswalk_table`, `reasoning_audit_ledger` → **STAGED-ONLY** until consumed by Writer (cross-reference) + human review (audit). |

---

## PHASE_EI_9 — Human Review Packet + Validation Harness

| Field | Value |
|---|---|
| **phase_id** | `PHASE_EI_9` |
| **status** | `NOT_AUTHORIZED` |
| **specs** | `EVIDENCE_INTELLIGENCE_HUMAN_REVIEW_PACKET_SPEC.md`, `EVIDENCE_INTELLIGENCE_VALIDATION_HARNESS_SPEC.md` |
| **dependencies** | All PHASE_EI_1 through PHASE_EI_8 |
| **allowed_scope** | Tiered human review (1 auto, 2 flag, 3 block), 24-case validation harness, gate signal bridge (`_build_ei_gate_signals()` per Option C) |
| **forbidden_scope** | graph.py / gates.py / agents.py. Auto-promoting fact confidence. Tier 3 not blocking. |
| **tests** | 6 new tests + 24 validation cases |
| **claude_audit_checklist** | [ ] Tier 3 blocks with decision_required=true, [ ] Tier 1 auto-handled, [ ] Tier 2 flagged without blocking, [ ] N1-N8 negative cases pass, [ ] 24 cases all pass, [ ] G46 receives EI gate signals, [ ] Controlled Compromise triggers on INSUFFICIENT |
| **hard_stop_conditions** | Tier 3 does not block → CRITICAL → STOP. 24 validation cases not 100% → STOP. G46 does not consume EI gate signals → STOP. graph/gates/agents modified → STOP. |
| **downstream_consumption_expectation** | `human_review_packet` → to human review workflow. Gate signals → G46 via pipeline bridge. All EI outputs un-staged after Gate Integration Verification PASS. |

---

## PHASE_PILOT_VALIDATION — Pre-Pilot Criteria

| Field | Value |
|---|---|
| **phase_id** | `PHASE_PILOT_VALIDATION` |
| **status** | `NOT_AUTHORIZED` → requires all EI-1 through EI-9 PASS + V3 production validation |
| **specs** | `PRE_PILOT_EI_CORE_VALIDATION_CRITERIA.md` |
| **dependencies** | PHASE_EI_9 complete + gate integration verified |
| **allowed_scope** | CAL-001 full run with EI Core, production-scale V3 validation (5 items from V3 proof index), human review packet end-to-end |
| **forbidden_scope** | Pilot on new projects. NL submission. Claiming system is production-ready. |
| **tests** | ≥209 tests + 24 validation cases + CAL-001 R1-R9 + V3 V3-1 through V3-5 |
| **hard_stop_conditions** | Any V3 production validation item fails → STOP. CAL-001 R1-R9 not 100% → STOP. |
| **downstream_consumption_expectation** | All EI outputs confirmed consumed by Writer via conclusion constraints. Gate integration confirmed. → PILOT_READY (human authorization required). |

---

## Staged-Only Outputs Registry

The following EI Core outputs are **staged-only** until their consuming phase verifies downstream consumption:

| Output | Produced By | Consumed By | Staged Until |
|---|---|---|---|
| evidence_strength_score, evidence_quality_tier, admissibility_level | PHASE_EI_1 | PHASE_EI_2 (Claim Reasoning) | PHASE_EI_2 integration verified |
| claim_support_matrix, writer_conclusion_constraints | PHASE_EI_2 | PHASE_EI_9 (G46 bridge) | PHASE_EI_9 gate integration verified |
| absence_category, synthesis_method_selections | PHASE_EI_3 | PHASE_EI_5/6/7 | Respective phase verified |
| bridging_assessment | PHASE_EI_4 | PHASE_EI_2 (indirect claims) | PHASE_EI_2 verified |
| sota_benchmark_table | PHASE_EI_5 | Writer (SOTA section) | PHASE_EI_9 gate integration |
| benefit_risk_conclusion | PHASE_EI_6 | Writer (BR section) + G46 | PHASE_EI_9 gate integration |
| pmcf_gap_register | PHASE_EI_7 | Writer (PMCF section) | PHASE_EI_9 gate integration |
| cer_rmf_crosswalk_table, reasoning_audit_ledger | PHASE_EI_8 | Writer + Human Review | PHASE_EI_9 verified |
| human_review_packet, gate_signals | PHASE_EI_9 | Human workflow + G46 | PHASE_PILOT_VALIDATION verified |

**No staged-only output may be treated as operationally consumed until its consuming phase verifies the consumption path.**

---

## Global Forbidden Scope (All Phases)

- graph.py / gates.py / agents.py modification
- LLM-based reasoning (all rules must be deterministic)
- Auto-promotion of fact confidence
- Silent conflict averaging
- Claiming "safe" from absence of evidence
- Bridging competitor evidence to subject device claims
- Presenting evidence scores as regulatory certification
- Pilot resumption before all phase gates pass

---

*CCD 签发：2026-05-13*
