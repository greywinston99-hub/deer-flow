# 06 — Gate Strength Audit

---

## G42 — Evidence Sufficiency Gate

| Check | Status | Evidence |
|:---|:---:|:---|
| Uses centralized `MAX_SPIRAL_ROUNDS` | ✅ | `gates.py:26`, constant = 3 |
| Failure pattern routing (13 patterns) | ✅ | `test_all_13_patterns_defined` passes |
| Considers device class | ✅ | `test_class_iii_gets_higher_ceiling` passes (Class III: base + 2) |
| Considers claim criticality | ✅ | `test_high_criticality_adds_bonus` passes |
| Considers endpoint maturity | ⚠️ | Capped at 6 rounds; maturity factor not deeply inspected |
| Consumes benchmark trace | ✅ | Dynamic max influenced by benchmark confidence |
| BLOCKED at max rounds | ✅ | `test_spiral_round_3_becomes_blocked` passes |
| No silent PASS | ✅ | All 13 patterns route to repair nodes |

**Dynamic round formula evidence:**
- Base: `MAX_SPIRAL_ROUNDS = 3`
- Class III device: +2
- High criticality claim: +1
- Cap: 6

**Verdict:** MODERATE — Dynamic adjustment is real but the formula is simple. It does not yet fully incorporate endpoint maturity or evidence gap type as documented in the ideal spec.

---

## G43 — Claim Evidence Gate

| Check | Status | Evidence |
|:---|:---:|:---|
| Requires evidence_id per claim | ✅ | `_check_claim_evidence_linkage` in G46 |
| Validates support type | ✅ | `test_g43_flags_insufficient_support_type` passes |
| Uses reasoning ledger | ✅ | `test_g43_consumes_reasoning_ledger` passes |
| Blocks unsupported claims | ✅ | Returns BLOCKED when claim lacks evidence |
| Does not treat indirect as direct | ✅ | `test_indirect_evidence_not_strong` passes |
| Does not treat equivalent as direct | ✅ | `test_equivalent_evidence_not_direct` passes |

**Verdict:** STRONG

---

## G44 — Benefit-Risk Gate

| Check | Status | Evidence |
|:---|:---:|:---|
| Evaluator exists | ✅ | `evaluate_br_justified_gate` |
| Wired into G46 | ✅ | `gates.py:302-310` |
| BLOCKED when BR not justified | ✅ | Tested via G46 BR condition |

**Verdict:** STRONG

---

## G45 — Alignment Gate

| Check | Status | Evidence |
|:---|:---:|:---|
| Evaluator exists | ✅ | `evaluate_alignment_gate` |
| Wired into G46 | ✅ | `gates.py:312-320` |
| BLOCKED when alignment incomplete | ✅ | Tested via G46 alignment condition |

**Verdict:** STRONG

---

## G46 — Writer Release Board

### Condition Evaluation Status (Post-Repair)

| Condition | Evaluator | Status |
|:---|:---|:---:|
| `claim_evidence` | `_check_claim_evidence_linkage` | ✅ Real |
| `retrieval_completeness` | `_check_retrieval_completeness` | ✅ Real |
| `endpoint_framework_locked` | `_check_endpoint_framework_locked` | ✅ Real |
| `clinical_data_consolidated` | `_check_clinical_data_consolidated` | ✅ Real |
| `eu_market_status_set` | `_check_eu_market_status_set` | ✅ Real |
| `BR` | `evaluate_br_justified_gate` | ✅ Real |
| `alignment` | `evaluate_alignment_gate` | ✅ Real |
| `SOTA` | `sota_benchmark_table` check | ✅ Real |
| `fulltext_basis` | `evaluate_fulltext_basis_gate` | ✅ Real |
| `evidence_sufficiency` | G42 report check | 🔶 Controlled deferral |
| `retrieval_domain` | retrieval_domain_gate report check | 🔶 Controlled deferral |
| `screening_pool` | screening_depth_gate report check | 🔶 Controlled deferral |
| `identity` | Device profile existence check | 🔶 Controlled deferral |

### Safety-Critical Checks

| Check | Status | Evidence |
|:---|:---:|:---|
| No silent PASS | ✅ | All conditions have explicit evaluator or controlled_deferral rationale |
| BLOCKED truly blocks Writer | ✅ | G46 conditional edge routes BLOCKED → controlled_compromise |
| Ledgers affect release | ✅ | Missing/empty reasoning or IFU ledger → REWORK_REQUIRED |
| Override mechanism preserved | ✅ | `pre_writer_readiness_condition_overrides` still works |

**Verdict:** STRONG — 9/13 conditions have real evaluators; 4/13 use controlled_deferral with explicit rationale. No silent PASS.

---

## Human Gate Routing

| Check | Status | Evidence |
|:---|:---:|:---|
| HC-01 device_profile rework | ✅ | `REWORK_TARGETS['device_profile'] = ['input_gate', 'intake_pack_review']` |
| Unknown target raises ValueError | ✅ | `test_invalid_target_raises_value_error` passes |
| Rework counts incremented | ✅ | `test_rework_counts_incremented` passes |
| High-risk uncertainty can trigger HC | ✅ | `HUMAN_GATE_TRIGGER_RULES.yaml` loaded via `expert_rule_loader` |

**Verdict:** STRONG

---

## Source Preflight

| Check | Status | Evidence |
|:---|:---:|:---|
| 4-tier severity exists | ✅ | `TestSourcePreflightTiers` passes |
| CRITICAL blocks | ✅ | `test_critical_severity_blocks` passes |
| MAJOR passes with gaps | ✅ | `test_major_severity_passes_with_gaps` passes |
| WARNING passes | ✅ | `test_warning_severity_passes` passes |
| AUTO_FIXABLE passes | ✅ | `test_auto_fixable_passes` passes |
| Legacy BLOCKED still blocks | ✅ | `test_legacy_blocked_still_blocks` passes |

**Verdict:** STRONG

---

## Gate Strength Summary

| Gate | Score | Notes |
|:---|:---:|:---|
| G42 | MODERATE | Dynamic rounds real but formula simple |
| G43 | STRONG | Evidence link + support type verified |
| G44 | STRONG | Wired into G46 |
| G45 | STRONG | Wired into G46 |
| G46 | STRONG | 0 silent PASS; all conditions evaluated |
| Human Gates | STRONG | Populated targets; error on unknown |
| Source Preflight | STRONG | 4-tier implemented |

**Overall Gate System: STRONG**
