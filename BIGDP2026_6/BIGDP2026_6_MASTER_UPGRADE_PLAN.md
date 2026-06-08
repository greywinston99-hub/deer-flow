# BIGDP2026.6 — Master Upgrade Plan

**Project:** BIGDP2026.6
**Type:** Major System Upgrade (not bugfix)
**Controller:** DeerFlow CER System Controller
**Date:** 2026-06-07
**Evidence Base:** `artifacts/cer/system_audit/SYSTEM_EVIDENCE_PACK_20260607_142204/`

---

## 1. Project Objective

Upgrade DeerFlow CER Authoring / Review / Intake system from **"process-type automation"** to **"expert-reasoning-type CER execution system."**

The current system follows a 42-node DAG with 61 gates and produces a `CER_INPUT_PACKAGE.json` for Claude Code to consume. The architecture is correct. But key gates are placeholder shells, expert reasoning is not encoded in the system, and several P0 defects make the human-gate and writer-release paths unreliable.

This upgrade must simultaneously cover: business logic, code repair, gate hardening, Claude Code handoff enforcement, test coverage, and final acceptance checklist.

---

## 2. Current System Real State

**Source:** `00_EXECUTIVE_VERDICT.md` (Evidence Pack)

| Subsystem | Status | Confidence | Key Finding |
|:---|:---|:---:|:---|
| CER Intake | Mostly functional | Medium | 15-state pipeline exists; only terminal `human_gate_pending` is API-visible |
| CER Authoring — Data Engine | Structurally strong | High | 42-node DAG + 61 gates + V3.1 chain; `DF_WRITING_ENGINE=claude_code` default |
| CER Authoring — Gate Integrity | **Compromised** | High | G46 auto-downgrades BLOCKED; HC-01 rework silently dropped; G42 spiral ceiling ambiguous |
| CER Authoring → Claude Code Handoff | Controlled by design | High | Graph terminates at `cer_input_package_export`; Writer is external |
| CER Review | Multi-path ambiguity | Medium | D1 active, v1 doc-only, v0 legacy — runner auto-detects mode heuristically |
| Evidence Traceability | Best-effort | Low-Medium | Lineage/ledger failures swallowed silently; not hard requirements |

**One-sentence verdict (from `00_EXECUTIVE_VERDICT.md`):**
> The CER data-engine backbone is architecturally sound and explicitly gate-guarded, but the current codebase contains multiple P0/P1 defects that make key human-gate and writer-release paths unreliable in production.

---

## 3. Why This Upgrade Is Necessary

### 3.1 P0 Defects (Evidence Pack: `05_BUSINESS_LOGIC_GAP_REGISTER.csv`, `03_GATE_AND_REWORK_AUDIT.md`)

| ID | Defect | Code Evidence | Impact |
|:---|:---|:---|:---|
| BLG-002/011 | G46 auto-downgrades BLOCKED to REWORK_REQUIRED for `claim_evidence` and `retrieval_completeness` | `gates.py:254-264` | Writer can be released before evidence links are verified |
| BLG-004 | `device_profile` REWORK_TARGETS is empty → human rework at HC-01 silently dropped | `graph.py:161-163, 175-192` | Wrong device identity cannot be corrected |
| BLG-001 | G42 spiral max rounds hardcoded to 3 (doc claims 5 in places) | `graph.py:1100, 1160, 1235, 2037` | Doc-code conflict; evidence retrieval may be prematurely truncated |
| — | Event Bus fallback doesn't clear prior partial state → duplicate risk | `graph.py:901-910` | Evidence duplicates in final state |

### 3.2 Expert Reasoning Gap (Evidence Pack: `Comments审核发现.md` §2, §4)

The Chinese expert review identified 6 business logic errors where the system's behavior diverges from how a 10+ year regulatory engineer would execute a CER:

1. **G46 is a placeholder shell** — only 3 of 9 conditions have real evaluators
2. **HC-01 rework is silently dropped** — device profile errors propagate downstream
3. **G42 spiral is fixed-iteration, not dynamic** — doesn't consider device class, claim criticality, or endpoint maturity
4. **SOTA benchmark is domain-hardcoded** — only 2 domains (cardiac_pfa, urology_nephroscope) have real builders
5. **Claude Code Writer is not contract-enforced** — no runtime assertion validates `CER_INPUT_PACKAGE.json` before writing
6. **Evidence traceability is best-effort** — lineage failures don't block export

### 3.3 Scale Risk (Evidence Pack: `10_REPAIR_ROADMAP.md`)

Running more projects before fixing P0/P1 will repeat the same failures: G46 not hard, HC-01 broken, G42 rules conflicting, SOTA benchmark domain-non-generalizable, handoff evidence orphaned.

---

## 4. Upgrade Scope

### 4.1 Business Layer Upgrade Scope

| Upgrade | Description | Source |
|:---|:---|:---|
| CER_REASONING_LEDGER | New artifact: claim classification, evidence support type, endpoint rationale, gap disposition, conclusion strength | `Comments审核发现.md` §4 升级方向一 |
| IFU_CLAIM_EVOLUTION_LEDGER | New artifact: tracks each IFU claim from raw text → extracted → classified → evidence-supported → final CER claim | `Comments审核发现.md` §4 升级方向二 |
| BENCHMARK_DERIVATION_TRACE | New artifact: endpoint-level benchmark with source studies, comparability, confidence, acceptability rationale | `Comments审核发现.md` §4 升级方向三 |
| G42 expert gate logic | Upgrade from fixed-round spiral to dynamic decision based on device class + claim criticality + evidence gap type + endpoint maturity | `Comments审核发现.md` §2 错误 3 |
| G46 Writer Release Board | Upgrade from 9-condition placeholder to full writer-release gate with real evaluators for ALL conditions | `Comments审核发现.md` §2 错误 1 |
| Source Preflight tiered severity | CRITICAL / MAJOR / WARNING / AUTO_FIXABLE (currently only BLOCKED / REWORK) | `Comments审核发现.md` §3 P1 项 7 |

### 4.2 Code Layer Repair Scope

**P0 (Fix before any production use):**

| ID | Fix | Files |
|:---|:---|:---|
| BLG-002/011 | Implement real `claim_evidence` and `retrieval_completeness` evaluators; remove auto-downgrade | `gates.py` |
| BLG-004 | Populate `REWORK_TARGETS['device_profile']` with valid targets; raise error on unknown target | `graph.py` |
| BLG-001 | Centralize `MAX_SPIRAL_ROUNDS` constant; update all call sites and docs | `graph.py`, `gates.py` |
| CD-004 | Event Bus fallback: snapshot state before attempt, restore + dedupe on fallback | `graph.py` |

**P1 (Fix before scaling to more projects):**

| ID | Fix | Files |
|:---|:---|:---|
| BLG-005 | Externalize SOTA benchmark domains to YAML config; add generic fallback builder | `pipeline.py`, `graph.py`, `v3_1_graph_integration.py` |
| BLG-003 | Delete unused `get_v3_1_rewire_spec` or refactor graph.py to consume it | `v3_1_graph_integration.py`, `graph.py` |
| BLG-012 | `controlled_compromise` must report export failures, not silently swallow | `graph.py` |
| BLG-018 | Clarify Review workflow: single production path (D1 or v1), deprecate others | `runner.py`, workflow YAMLs |

### 4.3 Gate / Runtime / Handoff / Review / Intake Boundaries

| Boundary | Current State | Target State | Source |
|:---|:---|:---|:---|
| **Gate: G42** | Fixed 3-round spiral; doc-code conflict | Dynamic ceiling based on device class + claim criticality; configurable | `03_GATE_AND_REWORK_AUDIT.md` |
| **Gate: G43** | Active but feeds into weak G46 aggregation | Claim evidence link must be real, not placeholder | `03_GATE_AND_REWORK_AUDIT.md` |
| **Gate: G46** | 9 conditions, 3 real evaluators, 2 auto-downgraded | All 9 conditions have real evaluators; no auto-downgrade; Writer Release Board | `03_GATE_AND_REWORK_AUDIT.md` |
| **Runtime: Event Bus** | Fallback can duplicate evidence; no dedupe | State snapshot + dedupe merge on fallback | `05_BUSINESS_LOGIC_GAP_REGISTER.csv` BLG-007 |
| **Runtime: V3.1 chain** | Hard-wired edges; unused rewire spec | Single source of truth for V3.1 wiring | `07_DOC_VS_CODE_CONFLICTS.md` |
| **Handoff: V3.2** | Orphaned evidence references in exported package | Reference integrity check before export; orphan = BLOCKED | `08_RUNTIME_ARTIFACT_AUDIT.md` |
| **Handoff: Claude Code** | Contract documented but not enforced at runtime | Runtime assertion: package exists, G46=PASS, all refs resolve, schema version supported | `04_WRITING_ENGINE_HANDOFF_AUDIT.md` |
| **Review** | D1/v1/v0 ambiguity; auto-detection heuristic | Single production path; explicit version field in workflow YAML | `01_SYSTEM_TOPOLOGY_MAP.md` |
| **Intake** | 15-state pipeline; only terminal state API-visible | Expose intermediate states; add WARNING tier to Source Preflight | `05_BUSINESS_LOGIC_GAP_REGISTER.csv` BLG-017 |

---

## 5. Phased Execution Order

### Phase 0: Master Plan Freeze
- **Input:** Evidence Pack `SYSTEM_EVIDENCE_PACK_20260607_142204`
- **Output:** 4 planning documents (this file + 3 companions)
- **Acceptance:** All 4 files written; all evidence references verified; no fake completed states
- **Stop Condition:** Controller approval of master plan

### Phase 1: P0 Runtime Safety Repair
- **Input:** `BIGDP2026_6_MASTER_UPGRADE_PLAN.md`
- **Scope:** 4 P0 fixes only — no refactoring, no new features
  1. G46 real evaluator (`claim_evidence`, `retrieval_completeness`) + remove auto-downgrade
  2. HC-01 `device_profile` rework routing repair
  3. `MAX_SPIRAL_ROUNDS` centralization
  4. Event Bus fallback dedupe
- **Output:** Patched `gates.py`, `graph.py`; passing targeted tests; verified by test suite
- **Acceptance:**
  - [ ] `test_g46.py`: G46 returns BLOCKED when claim lacks evidence_id
  - [ ] `test_g46.py`: G46 returns BLOCKED when retrieval is incomplete
  - [ ] `test_g46.py`: No silent BLOCKED → REWORK downgrade
  - [ ] HC-01 rework: `Command(goto=...)` returned for valid target
  - [ ] HC-01 rework: `ValueError` raised for unknown target
  - [ ] All `max_rounds` call sites reference same `MAX_SPIRAL_ROUNDS` constant
  - [ ] Event Bus fallback test: no duplicate `evidence_id` in final state
- **Stop Condition:** All 4 P0 acceptance criteria pass; no silent failures remain

### Phase 2: Expert Business Logic Artifacts
- **Input:** Phase 1 completed; `Comments审核发现.md` §4
- **Scope:** Create 3 new ledger artifacts as Python dataclasses + JSON schemas + graph nodes
  1. `CER_REASONING_LEDGER` — claim classification, evidence support type, endpoint rationale, gap disposition, conclusion strength
  2. `IFU_CLAIM_EVOLUTION_LEDGER` — IFU raw text → extracted → classified → evidence-supported → final CER claim
  3. `BENCHMARK_DERIVATION_TRACE` — endpoint-level benchmark with source studies, directness, confidence, acceptability
- **Output:**
  - `schemas/cer_reasoning_ledger.schema.json`
  - `schemas/ifu_claim_evolution_ledger.schema.json`
  - `schemas/benchmark_derivation_trace.schema.json`
  - New nodes in `graph.py`: `_node_build_reasoning_ledger`, `_node_build_ifu_evolution_ledger`, `_node_build_benchmark_trace`
  - Integration into pre-G46 data flow
- **Acceptance:**
  - [ ] All 3 schemas validate against JSON Schema spec
  - [ ] All 3 nodes produce valid output in integration test
  - [ ] All 3 ledgers are populated BEFORE G46 evaluation
  - [ ] Each ledger field is traceable to a specific upstream artifact
- **Stop Condition:** 3 ledgers are integrated into the DAG and populate correctly in dry-run

### Phase 3: Gate Integration
- **Input:** Phase 2 completed (ledgers exist)
- **Scope:** Upgrade G42, G43, G46 to consume new ledgers
  1. G42 consumes `BENCHMARK_DERIVATION_TRACE` for dynamic round decisions
  2. G43 consumes `CER_REASONING_LEDGER` for claim-evidence linkage verification
  3. G46 consumes all 3 ledgers for Writer Release Board (real 9-condition evaluation)
  4. Source Preflight upgraded to 4-tier (CRITICAL / MAJOR / WARNING / AUTO_FIXABLE)
- **Output:** Patched `gates.py`, `gates.py` G42/G43/G46 functions, `source_preflight.py`
- **Acceptance:**
  - [ ] G46 blocks Writer when any of 9 conditions is BLOCKED (no downgrades)
  - [ ] G42 routes vary by device class (Class III allows deeper retrieval)
  - [ ] G43 verifies every claim has at least one evidence_id with direct/indirect support
  - [ ] Source Preflight emits WARNING tier without blocking
- **Stop Condition:** All 3 key gates are "hard" — no placeholder shells remain

### Phase 4: Claude Code Handoff Enforcement
- **Input:** Phase 3 completed (gates are hard)
- **Scope:**
  1. `cer_input_package_export` node: add reference integrity check (no orphan evidence_ids)
  2. Claude Code skill entry: runtime assertion validates package before writing
  3. Package schema versioning: add `package_schema_version` field
  4. Optional: HMAC signature on exported package
- **Output:** Patched `graph.py` export node; patched Claude Code `cer-authoring-section-writer` skill
- **Acceptance:**
  - [ ] Export BLOCKED if any `evidence_id` in narrative not in registry
  - [ ] Claude Code skill startup validates: G46=PASS, package exists, schema version supported
  - [ ] Claude Code skill refuses to write if any check fails
- **Stop Condition:** Writer cannot run without gate-passed package

### Phase 5: SOTA / Benchmark Generalization
- **Input:** Phase 4 completed
- **Scope:**
  1. Move domain benchmark builders to external YAML config (`config/cer/benchmark_domains.yaml`)
  2. Add generic benchmark template builder for unknown domains
  3. Support endpoint clustering from extraction data
  4. Support device class / indication / claim type → benchmark mapping
- **Output:** `config/cer/benchmark_domains.yaml`; patched `pipeline.py`, `v3_1_graph_integration.py`
- **Acceptance:**
  - [ ] New domain (non-cardiac, non-urology) generates benchmark derivation without code change
  - [ ] Unknown domain produces reasoned fallback, not empty list
  - [ ] G30 can classify benchmark as: direct / indirect / fallback / insufficient
- **Stop Condition:** Benchmark generation works for any device domain with config-only extension

### Phase 6: Review Feedback Boundary / Optional Ingestion
- **Input:** Phase 5 completed
- **Scope:**
  1. Clarify Review production path: D1 or v1 (pick one); deprecate v0
  2. Add explicit `version` field to workflow YAMLs
  3. Review feedback backflow: implement `review_feedback_ingestion` node behind feature flag (disabled by default)
  4. Document SOP for how human uses Review feedback in Authoring
- **Output:** Updated `cer_review_v1.yaml` (or D1 spec); patched `runner.py`; new ingestion node
- **Acceptance:**
  - [ ] Only one Review workflow is active
  - [ ] `runner.py` fails fast on unknown version
  - [ ] Ingestion node exists, tested, feature-flagged disabled
  - [ ] SOP document exists for Review → Authoring feedback loop
- **Stop Condition:** Single production Review path; feedback boundary clearly defined

### Phase 7: Full Validation and Release Decision
- **Input:** Phases 0-6 completed
- **Scope:**
  1. Run full `BIGDP2026_6_ACCEPTANCE_CHECKLIST.md` (all sections)
  2. Run ALL existing tests; fix regressions
  3. Run targeted new tests (13 recommended from `09_TEST_COVERAGE_AND_MISSING_TESTS.md`)
  4. Dry-run CER pipeline on at least 1 real project (non-production, read-only validation)
  5. Compare output quality against pre-upgrade baseline
- **Output:** `BIGDP2026_6_VALIDATION_REPORT.md`; go/no-go release decision
- **Acceptance:** All checklist items in `BIGDP2026_6_ACCEPTANCE_CHECKLIST.md` marked PASS or DEFERRED with rationale
- **Stop Condition:** Controller makes explicit go/no-go decision; if go, tag release

---

## 6. Dependency Graph

```
Phase 0 (Master Plan Freeze)
  │
  ▼
Phase 1 (P0 Safety Repair) ──────────────────────┐
  │                                               │
  ▼                                               │
Phase 2 (Expert Business Logic Artifacts)         │
  │                                               │
  ▼                                               │
Phase 3 (Gate Integration) ◄──────────────────────┘
  │
  ▼
Phase 4 (Claude Code Handoff Enforcement)
  │
  ▼
Phase 5 (SOTA / Benchmark Generalization)
  │
  ▼
Phase 6 (Review Feedback Boundary)
  │
  ▼
Phase 7 (Full Validation and Release Decision)
```

Phase 1 is parallelizable into 4 independent workstreams:
1. G46 evaluator fix (gates.py)
2. HC-01 rework fix (graph.py REWORK_TARGETS)
3. MAX_SPIRAL_ROUNDS centralization (graph.py + gates.py + config)
4. Event Bus fallback dedupe (graph.py)

---

## 7. Risk Register

| Risk | Impact | Mitigation |
|:---|:---|:---|
| P0 fix introduces regression in DAG routing | Graph deadlocks or skips gates | Targeted unit tests before integration; contract tests for graph edges |
| New ledgers increase DAG execution time | CER pipeline slower | Ledger generation is read-only aggregation of existing artifacts; minimal overhead |
| SOTA generalization reduces specificity for known domains | Cardiac/urology benchmarks regress | Regression tests for existing domain builders before generalization |
| Review feedback ingestion breaks production Review | Review pipeline corrupted | Feature flag disabled by default; opt-in only |
| Real project validation reveals unanticipated gaps | Phase 7 fails | Plan includes explicit validation phase with stop condition; no release without passing |
