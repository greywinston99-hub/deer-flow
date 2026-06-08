# 04 — Expert Logic Implementation Audit

**Scope:** `EXPERT_CER_EXECUTION_SOP.md`, `EXPERT_REASONING_RULEBOOK.yaml`, decision tables, scenario fixtures, ledgers, and their runtime consumption.

---

## 1. Expert Logic Pack Files

| File | Exists | Size | Schema Valid | Runtime Used |
|:---|:---:|:---:|:---:|:---:|
| `EXPERT_CER_EXECUTION_SOP.md` | ✅ | ~15KB | N/A (markdown) | ❌ NOT_FOUND in runtime |
| `EXPERT_REASONING_RULEBOOK.yaml` | ✅ | ~8KB | ✅ | ❌ NOT_FOUND in runtime |
| `EXPERT_EXECUTION_CHECKLISTS.md` | ✅ | ~5KB | N/A | ❌ NOT_FOUND in runtime |
| `CLAIM_CLASSIFICATION_DECISION_TABLE.yaml` | ✅ | ~3KB | ✅ | ❌ NOT_FOUND in runtime |
| `EVIDENCE_SUPPORT_DECISION_TABLE.yaml` | ✅ | ~3KB | ✅ | ❌ NOT_FOUND in runtime |
| `GAP_DISPOSITION_DECISION_TABLE.yaml` | ✅ | ~3KB | ✅ | ❌ NOT_FOUND in runtime |
| `BENCHMARK_DERIVATION_DECISION_TABLE.yaml` | ✅ | ~4KB | ✅ | ❌ NOT_FOUND in runtime |
| `CONCLUSION_STRENGTH_DECISION_TABLE.yaml` | ✅ | ~3KB | ✅ | ❌ NOT_FOUND in runtime |
| `IFU_CLAIM_TRANSFORMATION_RULES.yaml` | ✅ | ~4KB | ✅ | ❌ NOT_FOUND in runtime |
| `HUMAN_GATE_TRIGGER_RULES.yaml` | ✅ | ~2KB | ✅ | ❌ NOT_FOUND in runtime |

**Verdict:** All 10 files exist and are well-structured. **None are imported or consumed by runtime code.**

---

## 2. Scenario Fixtures

| Fixture | Exists | Runtime Used |
|:---|:---:|:---:|
| `01_ifu_marketing_claim_overreach.json` | ✅ | ❌ |
| `02_claim_without_direct_evidence.json` | ✅ | ❌ |
| `03_benchmark_indirect_fallback.json` | ✅ | ❌ |
| `04_endpoint_mismatch_gap.json` | ✅ | ❌ |
| `05_pmcf_required_uncertainty.json` | ✅ | ❌ |
| `06_cannot_support_claim.json` | ✅ | ❌ |
| `07_risk_gspr_alignment_gap.json` | ✅ | ❌ |
| `08_equivalence_evidence_misused.json` | ✅ | ❌ |

**Verdict:** All 8 fixtures exist. **None are referenced by tests or runtime code.**

---

## 3. CER_REASONING_LEDGER

| Aspect | Status | Evidence |
|:---|:---|:---|
| Schema exists | ✅ ARTIFACT_CONFIRMED | `schemas/cer_reasoning_ledger.schema.json` (5075 bytes) |
| DAG node exists | ✅ CODE_CONFIRMED | `graph.py:1584` `_node_build_reasoning_ledger` |
| Node registered | ✅ CODE_CONFIRMED | `graph.py:2769` |
| Wired before G46 | ✅ CODE_CONFIRMED | `graph.py:2956` edge to `build_ifu_evolution_ledger` |
| G46 consumes it | ✅ CODE_CONFIRMED | `gates.py:346-354` checks `cer_reasoning_ledger` |
| Exported in package | ⚠️ INFERRED | Node returns ledger dict; state reducer should merge it |
| Semantic tests | ❌ NOT_FOUND | No test validates ledger content against expert rulebook |

**Verdict:** SCHEMA + NODE + WIRING are real. But the expert rulebook/decision tables are **not** used to populate the ledger. The ledger is built from existing artifacts (claim_ledger, evidence_matrix, etc.), not from expert logic.

---

## 4. IFU_CLAIM_EVOLUTION_LEDGER

| Aspect | Status | Evidence |
|:---|:---|:---|
| Schema exists | ✅ ARTIFACT_CONFIRMED | `schemas/ifu_claim_evolution_ledger.schema.json` (6320 bytes) |
| DAG node exists | ✅ CODE_CONFIRMED | `graph.py:1678` `_node_build_ifu_evolution_ledger` |
| Node registered | ✅ CODE_CONFIRMED | `graph.py:2770` |
| Wired before G46 | ✅ CODE_CONFIRMED | `graph.py:2957` edge to `build_benchmark_trace` |
| G46 consumes it | ✅ CODE_CONFIRMED | `gates.py:356-364` checks `ifu_claim_evolution_ledger` |
| Detects marketing claims | ⚠️ INFERRED | Node logic inspects claim transformations |
| Semantic tests | ❌ NOT_FOUND | No test validates 5-stage evolution |

**Verdict:** SCHEMA + NODE + WIRING are real. Expert IFU transformation rules are **not** consumed by the node.

---

## 5. BENCHMARK_DERIVATION_TRACE

| Aspect | Status | Evidence |
|:---|:---|:---|
| Schema exists | ✅ ARTIFACT_CONFIRMED | `schemas/benchmark_derivation_trace.schema.json` (6024 bytes) |
| DAG node exists | ✅ CODE_CONFIRMED | `graph.py:1784` `_node_build_benchmark_trace` |
| Node registered | ✅ CODE_CONFIRMED | `graph.py:2771` |
| Wired before G46 | ✅ CODE_CONFIRMED | `graph.py:2958` edge to `pre_writer_readiness_gate` |
| G42 consumes it | ⚠️ INFERRED | G42 comment says "Phase 3: consumes BENCHMARK_DERIVATION_TRACE" but actual consumption not fully verified |
| Per-endpoint rationale | ✅ CODE_CONFIRMED | Node generates `acceptability_rationale` and `alternatives_rejected_rationale` |
| Semantic tests | ❌ NOT_FOUND | No test validates benchmark derivation logic |

**Verdict:** SCHEMA + NODE + WIRING are real. G42 consumption partially implemented.

---

## 6. Expert Logic is Meaningful or Shallow?

**Assessment:** The expert logic pack is **comprehensive and well-structured** — but **shallow at runtime**.

What exists:
- 10 YAML/Markdown files with detailed reasoning rules
- 8 JSON scenario fixtures with realistic regulatory scenarios
- 3 JSON schemas for structured ledgers
- 3 DAG nodes that generate ledgers

What is missing:
- **No runtime consumption of rulebook/decision tables.** The `EXPERT_REASONING_RULEBOOK.yaml` is not imported by `gates.py` or `graph.py`.
- **No semantic tests.** No test asserts that a marketing claim in IFU is correctly flagged, or that an indirect benchmark is correctly labeled "fallback."
- **No fixture-driven tests.** The 8 scenario fixtures are not loaded by any test.

**This is a DOC_ONLY gap at the expert logic layer.** The artifacts are real, but they are not executable rules.

---

## 7. Critical Audit Finding

**Red Flag:** The expert reasoning layer is **documentation-only**.

The Master Plan (D-003) states: "Phase 2 creates 3 new ledger artifacts as Python dataclasses + JSON schemas + graph nodes." This has been done.

But the expert logic pack (rulebook, decision tables, fixtures) was intended to **drive** the ledger content. Instead, the ledgers are populated by existing pipeline artifacts (claim_ledger, evidence_matrix, sota_benchmark_table) with minor transformations.

**Impact:** The system has not yet been upgraded from "process-type" to "expert-reasoning-type." It has been upgraded to "process-type with extra ledgers."

**Recommended repair:**
1. Import decision tables into `_node_build_reasoning_ledger` to classify claims using expert rules
2. Import IFU transformation rules into `_node_build_ifu_evolution_ledger` to detect marketing language
3. Write fixture-driven tests: load each scenario fixture, run the node, assert the ledger matches expected expert judgment
4. Add semantic test: `test_expert_logic_consumption.py` that asserts rulebook YAML is loaded and influences output
