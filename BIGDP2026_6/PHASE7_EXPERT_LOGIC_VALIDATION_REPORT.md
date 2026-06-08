# Phase 7 — Expert Logic Validation Report

**Date:** 2026-06-08
**Project:** VasoSeal Pro X (Class IIb)

---

## 1. IFU as Working Input (Rule Category 1)

| Check | Result | Evidence |
|:---|:---:|:---|
| Raw IFU claims not blindly copied | ✅ PASS | C-04 IFU text "revolutionary...guarantees perfect" detected and flagged |
| Transformations have reasons | ✅ PASS | C-04: `marketing_language_detected=true`, `marketing_language_downgraded=true` |
| Marketing claims flagged | ✅ PASS | IFU_CLAIM_EVOLUTION_LEDGER: 1 marketing claim flagged (C-04) |

**Assessment:** IFU is treated as working input. Marketing language is detected by `expert_rule_loader.get_ifu_transformation()` and flagged in the IFU evolution ledger.

---

## 2. Claim Support (Rule Categories 2-3)

| Claim | Classification | Support Type | Evidence IDs | Status |
|:---|:---|:---|:---|:---|
| C-01 | clinical_performance | direct | E-001, E-002, E-003 | ✅ Supported |
| C-02 | clinical_safety | direct | E-004 | ✅ Supported (moderate) |
| C-03 | usability | insufficient | (none) | ⚠️ PMCF gap |
| C-04 | clinical_performance | direct | E-001, E-002 | ❌ Marketing overreach — claim_narrowing gap |

**Assessment:** All claims have support type classification. C-04 correctly identified as overreach despite having evidence links — the issue is the IFU wording, not evidence absence.

---

## 3. Conclusion Strength (Rule Category 4)

| Claim | Support Type | Evidence Count | Conclusion Strength | Ceiling Check |
|:---|:---|:---:|:---|:---|
| C-01 | direct | 3 | strong | ✅ Correct (direct + >=2) |
| C-02 | direct | 1 | moderate | ✅ Correct (direct + 1) |
| C-03 | insufficient | 0 | limited | ✅ Correct (insufficient capped) |
| C-04 | direct | 2 | strong | ✅ Correct (evidence strength is fine; issue is IFU wording) |

**Assessment:** Conclusion strength correctly derived from evidence support type and count per `CONCLUSION_STRENGTH_DECISION_TABLE`. No weak evidence produces strong conclusion. ✅

---

## 4. Benchmark Derivation (Rule Category 5)

| Endpoint | Directness | Confidence | Acceptability Rationale |
|:---|:---|:---|:---|
| hemostasis_time | direct | high | ✅ Present |
| major_adverse_events | direct | high | ✅ Present |

**Assessment:** Both endpoints have acceptability rationale. Domain "vascular_closure" is unknown — correctly falls back with generic template. Generic fallback benchmark provides `directness=fallback`, `confidence=low` for 0-source cases. ✅

---

## 5. PMCF Usage (Rule Category 6)

| Claim | Gap | PMCF Appropriate? |
|:---|:---|:---|
| C-03 (usability) | PMCF | ✅ Yes — insufficient evidence, non-safety-critical |
| C-04 (marketing) | claim_narrowing | ✅ Not PMCF — wording issue, not evidence gap |

**Assessment:** PMCF is NOT used as universal patch. C-03 correctly gets PMCF for genuine evidence gap. C-04 correctly gets claim_narrowing (IFU wording issue, not additional-study issue). ✅

---

## 6. Risk / GSPR / IFU Alignment (Rule Category 7)

| Claim | Type | RMF/GSPR Required? | Status |
|:---|:---|:---:|:---|
| C-02 | clinical_safety | Yes | ✅ G46 alignment: PASS |

**Assessment:** Safety claim C-02 passes alignment check. IFU alignment ledger present. ✅

---

## 7. Human Gate Triggers

| Trigger | Activated? | Gate |
|:---|:---:|:---|
| HG-MARKETING-LANGUAGE (C-04) | ✅ Yes | HC-03 (claim_decomposition rework) |
| HG-CANNOT-SUPPORT | ❌ No | — |

**Assessment:** Marketing language trigger correctly activated for C-04. Human review required before Writer release. ✅

---

## 8. Overall Expert Logic Assessment

| Category | Status |
|:---|:---:|
| IFU as working input | ✅ PASS |
| Claim classification | ✅ PASS |
| Evidence support type | ✅ PASS |
| Conclusion strength | ✅ PASS |
| Benchmark derivation | ✅ PASS |
| Gap disposition | ✅ PASS |
| Human gate triggers | ✅ PASS |
| PMCF anti-pattern avoidance | ✅ PASS |

**Verdict: Expert logic correctly enforced. 0 violations of core rules.**
