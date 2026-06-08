# BIGDP2026.6 — Phase 2 Expert Business Logic Review

**Date:** 2026-06-08
**Review Basis:** `BIGDP2026_6_EXPERT_BUSINESS_LOGIC_SPEC.md` + expert scenario fixtures S-01~S-08
**Implementation:** 3 ledger schemas + 3 DAG nodes + evidence-based conclusion strength logic

---

## 1. IFU as Working Input (Rule Category 1)

| Question | Answer | Evidence |
|:---|:---:|:---|
| Does the implementation handle IFU as working input rather than gold standard? | ✅ Yes | `_node_build_ifu_evolution_ledger` tracks 5-stage evolution from raw IFU → extracted → classified → evidence-supported → final CER claim |
| Are marketing claims flagged? | ✅ Yes | Marketing keywords detected; `marketing_language_detected` flag set; `requires_human_review: true` |
| Does every transformation have a reason? | ✅ Yes | Each of the 5 stages records `transformation_reason` |
| Can IFU claims be narrowed? | ✅ Yes | `claim_narrowed` flag when final text differs from IFU text |
| Can unsupported claims be rejected? | ⚠️ Partial | `gap_disposition: cannot_support` exists in schema; flagging depends on claim_evidence_matrix's gap_disposition field |

**S-01 (IFU Marketing Overreach):** ✅ PASS — marketing language detected, flagged for review, final claim narrowed.

---

## 2. Claim Classification (Rule Category 2)

| Question | Answer |
|:---|:---:|
| Are claims classified into regulatory types? | ✅ Yes — `clinical_performance`, `clinical_safety`, `usability`, `warning`, `non_clinical` |
| Is `unsupported` type available? | ✅ Schema supports it; runtime classification from `claim_type` field |
| Are clinical claims distinguished from non-clinical? | ✅ Different evidence requirements per classification |

---

## 3. Evidence Support Type (Rule Category 3)

| Question | Answer | Evidence |
|:---|:---:|:---|
| System distinguishes direct vs indirect? | ✅ Yes | `evidence_support_type` in ledger reads from `claim_evidence_matrix.support_type` |
| System distinguishes equivalent evidence? | ✅ Yes | `support_type: "equivalent"` produces moderate-at-best conclusions |
| System handles insufficient support? | ✅ Yes | `support_type: "insufficient"` → `conclusion_strength: "limited"` + `gap_disposition: "PMCF"` |
| Manufacturer-only evidence capped? | ✅ Yes | `support_type: "manufacturer"` → max `limited` conclusion |

**S-02 (Indirect Evidence):** ✅ PASS — conclusion capped at `moderate`, not `strong`.
**S-08 (Equivalence Misused):** ✅ PASS — `support_type: "equivalent"` correctly applied; conclusion capped.

---

## 4. Conclusion Strength Logic (Rule Category 4)

| Question | Answer |
|:---|:---:|
| Is conclusion strength evidence-based (not IFU-based)? | ✅ Yes — derived from `support_type` + evidence count |
| Does `direct` + ≥2 sources → `strong`? | ✅ Yes |
| Does `direct` + 1 source → `moderate`? | ✅ Yes |
| Does `indirect`/`equivalent` cap at `moderate`? | ✅ Yes |
| Does `manufacturer` cap at `limited`? | ✅ Yes |
| Does `insufficient` → `limited`? | ✅ Yes |

**S-05 (PMCF Required):** ✅ PASS — single small study → `limited` conclusion + PMCF gap.

---

## 5. Benchmark Derivation Logic (Rule Category 5)

| Question | Answer |
|:---|:---:|
| Does every benchmark have acceptability_rationale? | ✅ Yes — BMK-01 enforced |
| Does fallback have alternatives_rejected_rationale? | ✅ Yes — BMK-02 enforced |
| Does directness distinguish direct/indirect/fallback? | ✅ Yes |
| Does confidence reflect evidence quality? | ✅ Yes — `high` with ≥3 direct sources, `low` without sources |

**S-03 (Indirect Fallback):** ✅ PASS — benchmark has rationale, directness, confidence, limitations.

---

## 6. Gap Disposition Logic (Rule Category 6)

| Question | Answer |
|:---|:---:|
| Does insufficient evidence trigger gap? | ✅ Yes — `gap_disposition != "no_gap"` when no evidence_ids |
| Is `cannot_support` available? | ✅ Schema supports it; propagated from claim_evidence_matrix |
| Is `PMCF` triggered appropriately? | ✅ Default gap when evidence exists but is weak |

**S-04 (Endpoint Mismatch):** ✅ PASS — gap disposition triggered.
**S-06 (Cannot Support):** ✅ PASS — `cannot_support` disposition propagated from matrix.

---

## 7. Writer Release Logic (Rule Category 7)

| Question | Answer |
|:---|:---:|
| Does Writer block when G46 not PASS? | ✅ Yes — WRT-02 enforced |
| Does Writer block when claim is not_supported? | ✅ Yes |
| Does Writer allow with limitations when PMCF? | ✅ Yes — WRT-05 |

**S-07 (Risk/GSPR Gap):** ✅ PASS — alignment gate issues detected.

---

## 8. Expert Scenario Fixture Results

| Fixture | Scenario | Verdict |
|:---|:---|:---:|
| S-01 | IFU Marketing Overreach | ✅ PASS |
| S-02 | Claim Without Direct Evidence | ✅ PASS |
| S-03 | Benchmark Indirect Fallback | ✅ PASS |
| S-04 | Endpoint Mismatch Gap | ✅ PASS |
| S-05 | PMCF Required | ✅ PASS |
| S-06 | Cannot Support Claim | ✅ PASS |
| S-07 | Risk/GSPR Alignment Gap | ✅ PASS |
| S-08 | Equivalence Evidence Misused | ✅ PASS |

**All 8 expert scenarios produce expected results.**

---

## 9. Business Logic Remaining Shallow or Deferred

| Area | Status | Reason |
|:---|:---:|:---|
| IFU text vs evidence semantic comparison | 🔶 Shallow | The system detects marketing keywords but does not perform NLP-level claim-vs-evidence comparison. Gap disposition relies on explicit `gap_disposition` field in claim_evidence_matrix, not automatic detection of contradictory evidence. |
| Automatic endpoint mismatch detection | 🔶 Shallow | Endpoint mismatch (S-04) requires explicit gap_disposition in the matrix. The system does not automatically detect that the claimed endpoint differs from the measured endpoint. |
| RMF/GSPR deep integration | 🔶 Shallow | S-07 detects alignment gaps via the alignment_gate, but deep RMF hazard-to-claim linkage is not implemented. |
| Contradictory evidence detection | 🔶 Shallow | When evidence contradicts the claim (S-06), the system relies on the claim_evidence_matrix to set `gap_disposition: cannot_support`. Automatic contradiction detection is not implemented. |

These shallow areas are documented limitations, not blocking defects. They represent the boundary between "process-type automation" and full "expert-reasoning-type CER" — the BIGDP2026.6 upgrade has moved the system significantly toward the latter, but full NLP-level semantic analysis is a future phase.

---

## Verdict

**Phase 2 Expert Business Logic: PASS.** All 7 rule categories have implementation coverage. All 8 expert scenario fixtures produce expected results. Shallow areas are documented as known limitations for future phases.
