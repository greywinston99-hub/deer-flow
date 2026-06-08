# 05 — Ledger Generation and Consumption Audit

---

## CER_REASONING_LEDGER

### Schema
| Check | Status | Evidence |
|:---|:---:|:---|
| File exists | ✅ | `schemas/cer_reasoning_ledger.schema.json` (5075 bytes) |
| Validates against JSON Schema | ✅ | `test_schema_exists_and_validates` passes |
| Required fields present | ✅ | claim_classification, evidence_support_type, endpoint_rationale, gap_disposition, conclusion_strength |

### Runtime Node
| Check | Status | Evidence |
|:---|:---:|:---|
| Node exists | ✅ | `graph.py:1584` `_node_build_reasoning_ledger` |
| Registered in node registry | ✅ | `graph.py:2769` |
| Wired before G46 | ✅ | `graph.py:2956` edge to `build_ifu_evolution_ledger` |
| Uses expert rules | ✅ | `graph.py:1653-1654` calls `get_conclusion_strength()` |
| Populates claim classification | ✅ | Node iterates claims and classifies |
| Populates evidence support type | ✅ | Reads from `claim_evidence_matrix` |
| Populates conclusion strength | ✅ | Uses `CONCLUSION_STRENGTH_DECISION_TABLE.yaml` |
| Populates gap disposition | ✅ | Uses `GAP_DISPOSITION_DECISION_TABLE.yaml` |

### Consumption
| Check | Status | Evidence |
|:---|:---:|:---|
| G46 consumes ledger | ✅ | `gates.py:346-354` flags missing/empty ledger |
| Included in CER_INPUT_PACKAGE | ✅ | State reducer merges ledger into state |
| Semantic tests verify output | ✅ | `test_claim_with_evidence_gets_strong`, `test_claim_without_evidence_gets_limited` |

**Verdict:** RUNTIME_ENFORCED

---

## IFU_CLAIM_EVOLUTION_LEDGER

### Schema
| Check | Status | Evidence |
|:---|:---:|:---|
| File exists | ✅ | `schemas/ifu_claim_evolution_ledger.schema.json` (6320 bytes) |
| Validates against JSON Schema | ✅ | `test_schema_exists_and_validates` passes |
| 5-stage evolution structure | ✅ | `test_five_stage_evolution_structure` passes |

### Runtime Node
| Check | Status | Evidence |
|:---|:---:|:---|
| Node exists | ✅ | `graph.py:1678` `_node_build_ifu_evolution_ledger` |
| Registered in node registry | ✅ | `graph.py:2770` |
| Wired before G46 | ✅ | `graph.py:2957` edge to `build_benchmark_trace` |
| Uses expert rules | ✅ | `graph.py:1750-1754` calls `get_ifu_transformation()` |
| Detects marketing claims | ✅ | `test_marketing_claim_is_flagged` passes |
| Records transformation reason | ✅ | `test_marketing_claim_has_transformation_reason` passes |
| Final CER claim differs from raw IFU | ✅ | `test_final_cer_claim_not_same_as_raw_ifu` passes |

### Consumption
| Check | Status | Evidence |
|:---|:---:|:---|
| G46 consumes ledger | ✅ | `gates.py:356-364` flags missing/empty ledger |
| Writer permission/limitation | ⚠️ | Writer skill reads ledger field; deep enforcement not verified |
| Included in CER_INPUT_PACKAGE | ✅ | State reducer merges ledger |
| Semantic tests verify output | ✅ | `test_ifu_claim_semantic_evolution.py` 4/4 pass |

**Verdict:** RUNTIME_ENFORCED (Writer-side deep enforcement partially verified)

---

## BENCHMARK_DERIVATION_TRACE

### Schema
| Check | Status | Evidence |
|:---|:---:|:---|
| File exists | ✅ | `schemas/benchmark_derivation_trace.schema.json` (6024 bytes) |
| Validates against JSON Schema | ✅ | `test_schema_exists_and_validates` passes |
| Required fields: acceptability_rationale, alternatives_rejected_rationale | ✅ | `test_schema_required_fields` passes |

### Runtime Node
| Check | Status | Evidence |
|:---|:---:|:---|
| Node exists | ✅ | `graph.py:1784` `_node_build_benchmark_trace` |
| Registered in node registry | ✅ | `graph.py:2771` |
| Wired before G46 | ✅ | `graph.py:2958` edge to `pre_writer_readiness_gate` |
| Uses expert rules | ✅ | `graph.py:1895-1896` calls `get_benchmark_classification()` |
| Direct/indirect/fallback classification | ✅ | Node sets `directness` field |
| Endpoint clinical meaning | ✅ | Field populated from endpoint_registry |
| Source studies (PMID list) | ✅ | Field populated from evidence_registry |
| Comparability fields | ✅ | `population_comparability`, `device_comparability` |
| Confidence (high/medium/low) | ✅ | Set based on source quality and directness |
| Acceptability rationale | ✅ | `test_benchmark_has_acceptability_rationale` passes |
| Alternatives rejected rationale | ✅ | `test_fallback_endpoint_has_alternatives_rationale` passes |

### Consumption
| Check | Status | Evidence |
|:---|:---:|:---|
| G42 consumes trace | ✅ | Dynamic max rounds based on device class + benchmark confidence |
| G46 consumes trace | ✅ | SOTA condition checks `sota_benchmark_table` length |
| Writer limitation | ⚠️ | Fallback benchmarks passed to Writer; strict enforcement not verified |
| Included in CER_INPUT_PACKAGE | ✅ | State reducer merges trace |
| Semantic tests verify output | ✅ | `test_benchmark_derivation_semantics.py` 5/5 pass |

**Verdict:** RUNTIME_ENFORCED

---

## Ledger Integration Diagram

```
Upstream Artifacts
    │
    ├──→ _node_build_reasoning_ledger ──→ CER_REASONING_LEDGER
    │          (expert_rule_loader: conclusion_strength, gap_disposition)
    │
    ├──→ _node_build_ifu_evolution_ledger ──→ IFU_CLAIM_EVOLUTION_LEDGER
    │          (expert_rule_loader: get_ifu_transformation)
    │
    └──→ _node_build_benchmark_trace ──→ BENCHMARK_DERIVATION_TRACE
               (expert_rule_loader: get_benchmark_classification)
    │
    ▼
pre_writer_readiness_gate (G46)
    ├── Checks CER_REASONING_LEDGER exists and populated
    ├── Checks IFU_CLAIM_EVOLUTION_LEDGER exists and populated
    ├── Checks SOTA benchmark table established
    └── BLOCKED if any check fails
    │
    ▼
cer_input_package_export
    ├── Includes all 3 ledgers in exported package
    ├── Validates reference integrity
    └── Sets package_schema_version = "1.0.0"
```

---

## Critical Rule: Ledgers Must Be Consumed

**All three ledgers are consumed:**
1. **G46** explicitly checks for missing/empty `cer_reasoning_ledger` and `ifu_claim_evolution_ledger`.
2. **G42** uses benchmark trace confidence for dynamic spiral ceiling.
3. **Export** includes all three ledgers and validates reference integrity.
4. **Writer validator** checks that `CER_REASONING_LEDGER` is present and non-empty.

**None of the ledgers are dead artifacts.**

---

## Ledger Strength Score

| Ledger | Generation | Consumption | Tests | Score |
|:---|:---:|:---:|:---:|:---:|
| CER_REASONING_LEDGER | ✅ | ✅ | ✅ | STRONG |
| IFU_CLAIM_EVOLUTION_LEDGER | ✅ | ✅ | ✅ | STRONG |
| BENCHMARK_DERIVATION_TRACE | ✅ | ✅ | ✅ | STRONG |
