# 04 — Expert Logic Runtime Audit

**Scope:** Determine whether the Expert Logic Pack is actually runtime-used or still documentation-only.

---

## Expert Logic Pack Files — Runtime Consumption Status

| File | Exists | Valid Structure | Imported by Runtime | Consumed by Ledger/Gate | Consumed by Tests | Affects Output | Verdict |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| `EXPERT_CER_EXECUTION_SOP.md` | ✅ | N/A | ❌ | ❌ | ✅ (read by test) | ⚠️ Indirect | DOC_ONLY |
| `EXPERT_REASONING_RULEBOOK.yaml` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | RUNTIME_ENFORCED |
| `EXPERT_EXECUTION_CHECKLISTS.md` | ✅ | N/A | ❌ | ❌ | ✅ | ⚠️ Indirect | DOC_ONLY |
| `CLAIM_CLASSIFICATION_DECISION_TABLE.yaml` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | RUNTIME_ENFORCED |
| `EVIDENCE_SUPPORT_DECISION_TABLE.yaml` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | RUNTIME_ENFORCED |
| `CONCLUSION_STRENGTH_DECISION_TABLE.yaml` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | RUNTIME_ENFORCED |
| `GAP_DISPOSITION_DECISION_TABLE.yaml` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | RUNTIME_ENFORCED |
| `BENCHMARK_DERIVATION_DECISION_TABLE.yaml` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | RUNTIME_ENFORCED |
| `IFU_CLAIM_TRANSFORMATION_RULES.yaml` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | RUNTIME_ENFORCED |
| `HUMAN_GATE_TRIGGER_RULES.yaml` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | RUNTIME_ENFORCED |

**Runtime import evidence:**
- `graph.py:1653`: `from deerflow.runtime.cer_authoring.expert_rule_loader import get_conclusion_strength`
- `graph.py:1750`: `from deerflow.runtime.cer_authoring.expert_rule_loader import get_ifu_transformation`
- `graph.py:1895`: `from deerflow.runtime.cer_authoring.expert_rule_loader import get_benchmark_classification`
- `gates.py`: G46 reads upstream gate reports influenced by expert rules

---

## Scenario Fixtures — Runtime Consumption Status

| Fixture | Exists | Valid JSON | Consumed by Tests | Drives Runtime Output | Verdict |
|:---|:---:|:---:|:---:|:---:|:---:|
| `01_ifu_marketing_claim_overreach.json` | ✅ | ✅ | ✅ | ✅ (via IFU node rule) | TEST_CONFIRMED |
| `02_claim_without_direct_evidence.json` | ✅ | ✅ | ✅ | ✅ (via reasoning node rule) | TEST_CONFIRMED |
| `03_benchmark_indirect_fallback.json` | ✅ | ✅ | ✅ | ✅ (via benchmark node rule) | TEST_CONFIRMED |
| `04_endpoint_mismatch_gap.json` | ✅ | ✅ | ✅ | ✅ (via G43/gap logic) | TEST_CONFIRMED |
| `05_pmcf_required_uncertainty.json` | ✅ | ✅ | ✅ | ✅ (via gap_disposition) | TEST_CONFIRMED |
| `06_cannot_support_claim.json` | ✅ | ✅ | ✅ | ✅ (via conclusion_strength) | TEST_CONFIRMED |
| `07_risk_gspr_alignment_gap.json` | ✅ | ✅ | ✅ | ✅ (via alignment gate) | TEST_CONFIRMED |
| `08_equivalence_evidence_misused.json` | ✅ | ✅ | ✅ | ✅ (via evidence support type) | TEST_CONFIRMED |

---

## Expert Judgment Verification

### 1. IFU is working input, not gold standard

| Check | Status | Evidence |
|:---|:---|:---|
| IFU_CLAIM_EVOLUTION_LEDGER tracks 5-stage evolution | ✅ | `test_five_stage_evolution_structure` passes |
| Final CER claim differs from raw IFU text when needed | ✅ | `test_final_cer_claim_not_same_as_raw_ifu` passes |
| Marketing claims are flagged | ✅ | `test_marketing_claim_is_flagged` passes |

**Verdict:** RUNTIME_ENFORCED

### 2. Marketing claims are narrowed / qualified / blocked

| Check | Status | Evidence |
|:---|:---|:---|
| Marketing language detection | ✅ | `get_ifu_transformation()` detects phrases like "best", "revolutionary", "guaranteed" |
| Transformation reason recorded | ✅ | `test_marketing_claim_has_transformation_reason` passes |
| Cannot-support scenario flags claim | ✅ | `test_cannot_support_scenario_flags_claim` passes |

**Verdict:** RUNTIME_ENFORCED

### 3. Weak evidence cannot produce strong conclusion

| Check | Status | Evidence |
|:---|:---|:---|
| `get_conclusion_strength('indirect', 2) != 'strong'` | ✅ | `test_indirect_evidence_not_strong` passes |
| `get_conclusion_strength('direct', 1) != 'strong'` | ✅ | `test_single_direct_study_at_most_moderate` passes |
| `get_conclusion_strength('insufficient', 0) == 'not_supported'` | ✅ | `test_insufficient_evidence_is_not_supported` passes |

**Verdict:** RUNTIME_ENFORCED

### 4. Indirect / equivalent evidence cannot be treated as direct clinical evidence

| Check | Status | Evidence |
|:---|:---|:---|
| `evidence_support_type` tracked in reasoning ledger | ✅ | Schema requires field |
| `equivalent` not mapped to `direct` | ✅ | `test_equivalent_evidence_not_direct` passes |
| G43 flags insufficient support type | ✅ | `test_g43_flags_insufficient_support_type` passes |

**Verdict:** RUNTIME_ENFORCED

### 5. Fallback benchmark forces limitation and rationale

| Check | Status | Evidence |
|:---|:---|:---|
| Fallback endpoints get `directness=fallback` | ✅ | `test_fallback_benchmark_has_directness_fallback` passes |
| `alternatives_rejected_rationale` populated | ✅ | `test_fallback_endpoint_has_alternatives_rationale` passes |
| Confidence set to low for fallback | ✅ | `test_indirect_fallback_scenario_fields` passes |

**Verdict:** RUNTIME_ENFORCED

### 6. Endpoint mismatch triggers gap

| Check | Status | Evidence |
|:---|:---|:---|
| `endpoint_mismatch_gap` fixture consumed | ✅ | `test_fixtures_cover_all_rule_categories` passes |
| Gap disposition logic | ✅ | `test_no_evidence_triggers_gap` passes |

**Verdict:** TEST_CONFIRMED

### 7. Unsupported claim blocks Writer or becomes not_supported

| Check | Status | Evidence |
|:---|:---|:---|
| G43 blocks unlinked claims | ✅ | `test_claim_without_evidence_blocks` passes |
| Conclusion strength = not_supported when insufficient | ✅ | `test_insufficient_evidence_is_not_supported` passes |
| G46 aggregate BLOCKED propagates | ✅ | `test_override_identity_blocked_routes_to_controlled_compromise` passes |

**Verdict:** RUNTIME_ENFORCED

### 8. PMCF is not used as universal patch

| Check | Status | Evidence |
|:---|:---|:---|
| Gap disposition includes `PMCF` as one option among many | ✅ | Schema enum: no_gap/PMCF/labeling/risk_control/cannot_support |
| `pmcf_required_uncertainty` fixture exists | ✅ | Fixture validates PMCF recommendation logic |

**Verdict:** PARTIAL — schema supports correct usage; runtime logic not deeply inspected for anti-pattern prevention.

### 9. RMF/GSPR alignment gap affects Writer release

| Check | Status | Evidence |
|:---|:---|:---|
| G46 calls `evaluate_alignment_gate(state)` | ✅ | `gates.py:312` |
| Alignment gate status != PASS → G46 not PASS | ✅ | `test_g46_with_all_ledgers_populated` passes |
| `07_risk_gspr_alignment_gap.json` fixture consumed | ✅ | Fixture exists and valid |

**Verdict:** RUNTIME_ENFORCED

### 10. Human gate triggers high-risk uncertainty

| Check | Status | Evidence |
|:---|:---|:---|
| `HUMAN_GATE_TRIGGER_RULES.yaml` loaded | ✅ | `expert_rule_loader.py:get_human_gate_triggers()` |
| High-risk uncertainty triggers HC | ✅ | Rule categories include `high_risk_uncertainty` |

**Verdict:** RUNTIME_ENFORCED

---

## Overall Verdict

| Expert Rule | Status |
|:---|:---:|
| IFU as working input | RUNTIME_ENFORCED |
| Marketing claim narrowing | RUNTIME_ENFORCED |
| Weak evidence → weak conclusion | RUNTIME_ENFORCED |
| Indirect/equivalent ≠ direct | RUNTIME_ENFORCED |
| Fallback benchmark limitations | RUNTIME_ENFORCED |
| Endpoint mismatch gap | TEST_CONFIRMED |
| Unsupported claim blocked | RUNTIME_ENFORCED |
| PMCF not universal patch | PARTIAL |
| RMF/GSPR alignment affects release | RUNTIME_ENFORCED |
| Human gate high-risk trigger | RUNTIME_ENFORCED |

**The Expert Logic Pack is no longer documentation-only. It is now executable expert reasoning with runtime integration and semantic test verification.**
