# BIGDP2026.6 — Repair Sprint Plan

**Status:** `ACCEPT_WITH_REPAIRS`
**Audit Base:** `BIGDP2026_6/audits/CODE_IMPLEMENTATION_AUDIT_20260608_003541/`
**Controller:** BIGDP2026.6 Controller (planning + audit only)
**Executor:** Claude Code implementer

---

## A. Current Conclusion: `ACCEPT_WITH_REPAIRS`

Per audit verdict (`00_AUDIT_EXECUTIVE_VERDICT.md`), Phases 1-3 are implemented in real code with passing tests (496/497 pass, 1 pre-existing `test_cal001_integration` failure from `self_inspection` node not registered in `claude_code` mode).

**This is not ACCEPT (there are gaps). This is not REJECT (code is real). This is ACCEPT_WITH_REPAIRS — the implementation is acceptable to continue, but mandatory repairs must be completed before any release claim.**

---

## B. Mandatory Repair Items

### R0 — Test Execution Unblock (P0)

**Problem:** Audit (`07_TEST_EVIDENCE_AUDIT.md`) reports pytest not installed, 0 tests executed. Controller verified: pytest IS available in `.venv` — 496/497 pass. The 1 failure (`test_cal001_integration.py::test_t1_graph_compilation`) expects `self_inspection` node which is only registered in legacy `DF_WRITING_ENGINE=deerflow` mode.

**Actions:**
- [x] R0.1 pytest environment confirmed: `.venv/bin/python3 -m pytest` works ✅
- [x] R0.2 Full suite run: 496 pass, 1 fail (`test_cal001_integration`) ✅
- [ ] R0.3 Fix `test_cal001_integration.py::test_t1_graph_compilation` — update `self_inspection` assertion to be conditional on `DF_WRITING_ENGINE` mode
- [ ] R0.4 Re-run full suite → 497/497 pass

**Evidence required:** `pytest -q` output showing 0 failures

**Stop condition:** Any test that blocks and cannot be fixed within scope → STOP and report to Controller

---

### R1 — Expert Logic Pack Runtime Integration (P1)

**Problem:** Per `04_EXPERT_LOGIC_IMPLEMENTATION_AUDIT.md`, Audit Finding §7: 10 YAML files and 8 scenario fixtures exist but ZERO are imported or consumed by runtime. The ledgers are built from existing pipeline artifacts, not from expert rules. The system is "process-type with extra ledgers," not "expert-reasoning-type."

**Files that MUST be consumed by runtime:**
| File | Must Be Consumed By |
|:---|:---|
| `EXPERT_REASONING_RULEBOOK.yaml` | `_node_build_reasoning_ledger` in `graph.py` |
| `CLAIM_CLASSIFICATION_DECISION_TABLE.yaml` | `_node_build_reasoning_ledger` in `graph.py` |
| `EVIDENCE_SUPPORT_DECISION_TABLE.yaml` | `_node_build_reasoning_ledger` in `graph.py` |
| `CONCLUSION_STRENGTH_DECISION_TABLE.yaml` | `_node_build_reasoning_ledger` in `graph.py` |
| `GAP_DISPOSITION_DECISION_TABLE.yaml` | `_node_build_reasoning_ledger` in `graph.py` |
| `IFU_CLAIM_TRANSFORMATION_RULES.yaml` | `_node_build_ifu_evolution_ledger` in `graph.py` |
| `BENCHMARK_DERIVATION_DECISION_TABLE.yaml` | `_node_build_benchmark_trace` in `graph.py` |
| `HUMAN_GATE_TRIGGER_RULES.yaml` | G46 and HC routing in `gates.py` |

**Scenario fixtures that MUST be consumed by tests:**
| Fixture | Tests Against |
|:---|:---|
| `01_ifu_marketing_claim_overreach.json` | `_node_build_ifu_evolution_ledger` → marketing language detected |
| `02_claim_without_direct_evidence.json` | `_node_build_reasoning_ledger` → evidence_support_type=indirect |
| `03_benchmark_indirect_fallback.json` | `_node_build_benchmark_trace` → directness=fallback, alternatives_rejected populated |
| `04_endpoint_mismatch_gap.json` | G43 → gap_disposition=PMCF |
| `05_pmcf_required_uncertainty.json` | G46 → PMCF recommendation required |
| `06_cannot_support_claim.json` | `_node_build_reasoning_ledger` → conclusion_strength=not_supported |
| `07_risk_gspr_alignment_gap.json` | G45 → alignment gap flagged |
| `08_equivalence_evidence_misused.json` | G42 → equivalence evidence not meeting 3-dim rule |

**Actions:**
- [ ] R1.1 Create `runtime/expert_rule_loader.py` — loads YAML decision tables at import time, returns typed rule objects
- [ ] R1.2 Wire `expert_rule_loader` into `_node_build_reasoning_ledger` (`graph.py`) — use CLAIM_CLASSIFICATION, EVIDENCE_SUPPORT, CONCLUSION_STRENGTH, GAP_DISPOSITION tables to populate ledger
- [ ] R1.3 Wire `expert_rule_loader` into `_node_build_ifu_evolution_ledger` (`graph.py`) — use IFU_CLAIM_TRANSFORMATION_RULES to detect marketing language, over-scoping, absolute language
- [ ] R1.4 Wire `expert_rule_loader` into `_node_build_benchmark_trace` (`graph.py`) — use BENCHMARK_DERIVATION_DECISION_TABLE for directness classification
- [ ] R1.5 Wire `expert_rule_loader` into G46 and HC routing (`gates.py`) — use HUMAN_GATE_TRIGGER_RULES for human gate decisions
- [ ] R1.6 Create `tests/test_expert_logic_consumption.py` — loads each scenario fixture, runs the relevant node/gate, asserts output matches expected expert judgment
- [ ] R1.7 Verify: no expert YAML file remains unconsumed by runtime (audit with `grep` for each YAML filename in `gates.py` and `graph.py`)

**Acceptance:** Each scenario fixture passes semantic test. Expert rulebook YAML is imported at runtime. Ledger content reflects expert decision tables, not just raw pipeline artifact passthrough.

**Stop condition:** If any expert rule conflicts with existing runtime logic and cannot be resolved without architecture change → STOP and report to Controller.

---

### R2 — Claude Code Writer Handoff Enforcement (P1)

**Problem:** Per `06_CLAUDE_CODE_HANDOFF_AUDIT.md`, Critical Finding: handoff is one-sided. DeerFlow side has `cer_package_validator.py` with 170+ lines of validation. Claude Code skill side: `cer-authoring-section-writer` NOT FOUND. Writer could theoretically receive an invalid package.

**Actions:**
- [ ] R2.1 Locate existing Claude Code writer skill entrypoint: search `.claude/skills/`, `skills/`, `prompts/cer/` for writer invocation path
- [ ] R2.2 If skill found: add `validate_cer_input_package()` assertion block at skill entry
- [ ] R2.3 If skill NOT found: create `BIGDP2026_6/repairs/writer_package_validator.py` — a standalone validator script that the Claude Code skill MUST invoke before writing
- [ ] R2.4 Validator must assert ALL of:
  - `CER_INPUT_PACKAGE.json` file exists
  - `pre_writer_readiness_gate_report.status == "PASS"`
  - `cer_input_package_exported == True`
  - All `claim_ids` resolve in package
  - All `evidence_ids` resolve in package
  - All `benchmark_ids` resolve in package
  - All BR/alignment refs resolve
  - `package_schema_version` is in supported list (`["1.0.0"]`)
- [ ] R2.5 Validator exits non-zero on any failure (refuses to write)
- [ ] R2.6 Document in `BIGDP2026_6/repairs/HANDOFF_VALIDATOR_README.md` where the validator was placed and how the Claude Code skill invokes it
- [ ] R2.7 Test: create intentionally invalid packages (G46 BLOCKED, orphan ref, empty file) → validator exits non-zero for each

**Acceptance:** Writer cannot write without gate-passed package. Tested with 3 invalid package scenarios.

**Stop condition:** If writer skill location cannot be determined after exhaustive search → STOP, document findings, recommend Controller provide the path.

---

### R3 — G46 Remaining Evaluator Hardening (P1)

**Problem:** Per `05_GATE_RUNTIME_WIRING_AUDIT.md`, G46 section: 5/9 conditions have real evaluators. 4 conditions still fallback to PASS with note. Per `09_RESIDUAL_GAP_REGISTER.csv` GAP-015: "4 of 9 conditions fallback to PASS with note — these conditions are not fully evaluated."

**Current evaluator status:**
| Condition | Evaluator | Status |
|:---|:---|:---|
| `claim_evidence` | `_check_claim_evidence_linkage` | ✅ Real (R0 fix) |
| `retrieval_completeness` | `_check_retrieval_completeness` | ✅ Real (R0 fix) |
| `endpoint_framework_locked` | `_check_endpoint_framework_locked` | ✅ Real |
| `clinical_data_consolidated` | `_check_clinical_data_consolidated` | ✅ Real |
| `eu_market_status_set` | `_check_eu_market_status_set` | ✅ Real |
| `SOTA` | ??? | ⚠️ Fallback to PASS |
| `BR` | ??? (G44 evaluator exists separately) | ⚠️ Fallback to PASS |
| `alignment` | ??? (G45 evaluator exists separately) | ⚠️ Fallback to PASS |
| `retrieval_domain` / `identity` / `screening_pool` / `fulltext_basis` | ??? | ⚠️ Fallback to PASS |

**Actions:**
- [ ] R3.1 Identify exact 4 conditions that fallback to PASS (read `gates.py` G46 loop to confirm which conditions lack dedicated evaluators)
- [ ] R3.2 For `SOTA`: wire existing `evaluate_sota_benchmark_derivation` (from `v3_1_gates.py`) into G46 condition check
- [ ] R3.3 For `BR`: wire existing `evaluate_benefit_risk_gate` (G44) result into G46 condition check
- [ ] R3.4 For `alignment`: wire existing `evaluate_alignment_gate` (G45) result into G46 condition check
- [ ] R3.5 For safety-critical conditions with no existing evaluator: implement a real evaluator OR create a `controlled_deferral` with explicit rationale in gate report
- [ ] R3.6 Safety-critical rule: **no condition that affects patient safety may default to PASS**
- [ ] R3.7 Update `tests/test_g46.py`: add test for each newly-wired condition — assert BLOCKED when gate fails, PASS when gate passes

**Acceptance:** 9/9 G46 conditions have real evaluation paths. 0 conditions fallback to PASS silently. Any deferral has explicit rationale in gate report.

**Stop condition:** If any condition cannot be evaluated with existing data and requires architecture change → implement `controlled_deferral` with explicit rationale; do NOT silently PASS.

---

### R4 — Benchmark Generalization Validation (P2)

**Problem:** Per `00_AUDIT_EXECUTIVE_VERDICT.md` Phase 5 assessment: `benchmark_domains.yaml` exists but no end-to-end test for unknown domain. `09_RESIDUAL_GAP_REGISTER.csv` GAP-008: "Config exists but no end-to-end test for unknown domain."

**Actions:**
- [ ] R4.1 Verify `benchmark_domains.yaml` is loaded at runtime (check for `load_benchmark_domain_config` or create it)
- [ ] R4.2 Write end-to-end test: add a new domain to YAML (e.g., `orthopedic_implant`) → run `_node_build_benchmark_trace` → assert benchmark is generated with `directness=fallback`, `confidence=low`, `limitations` populated
- [ ] R4.3 Verify existing domains (`cardiac_pfa`, `urology_nephroscope`) still produce identical output
- [ ] R4.4 Test: unknown domain NOT in YAML → generic fallback with `confidence=low` and `limitations=["No domain-specific benchmark template available"]`

**Acceptance:** New domain can be added via YAML-only change. Unknown domains produce reasoned fallback, not empty benchmark.

**Stop condition:** If generic fallback produces empty or nonsensical output → STOP and fix fallback template before continuing.

---

### R5 — Scope Clarification (P1)

**Problem:** Per `09_RESIDUAL_GAP_REGISTER.csv` GAP-011: 8 v5 Review files added. Scope unclear — may be experimental or parallel project. `00_AUDIT_EXECUTIVE_VERDICT.md` Phase 6: NOT_STARTED (no code changes for Review boundary).

**Actions:**
- [ ] R5.1 Identify all new files added outside BIGDP2026.6 scope (check `git diff --stat` against `BIGDP2026_6_MASTER_UPGRADE_PLAN.md` scope)
- [ ] R5.2 For each out-of-scope file: classify as `experimental` / `parallel_project` / `accidental_inclusion`
- [ ] R5.3 For experimental files: add `# EXPERIMENTAL — NOT FOR BIGDP2026.6 RELEASE` banner
- [ ] R5.4 For parallel project files: move to separate directory or feature-flag gate
- [ ] R5.5 Update `BIGDP2026_6_REPAIR_SPRINT_SCOPE_LOCK.md` with classification

**Acceptance:** All files in the working tree are classified. No ambiguous scope items remain.

**Stop condition:** If Review v5 files are determined to be production path → Controller must decide whether to absorb into BIGDP2026.6 or defer to separate track.

---

## C. Claude Code Execution Boundaries

### Claude Code MAY:
- Read any file in the repository
- Modify `gates.py`, `graph.py`, `pipeline.py` (scoped changes only)
- Create new files: `expert_rule_loader.py`, `test_expert_logic_consumption.py`, `writer_package_validator.py`
- Add/modify tests in `tests/` directory
- Run `pytest` to verify fixes
- Update Repair Sprint reports (`BIGDP2026_6/repairs/`)
- Fix `test_cal001_integration.py` (conditional assertion)

### Claude Code MUST NOT:
- Rewrite the entire `graph.py` or `pipeline.py` (1.4MB — scoped edits only)
- Expand into unrelated Review v5 refactoring
- `git push` or create PRs
- Mark DOC_ONLY items as PASS without runtime evidence
- Claim "done" without `pytest -q` output showing 0 failures
- Skip Expert Logic runtime integration (R1 is mandatory, not optional)
- Modify `BIGDP2026_6_MASTER_UPGRADE_PLAN.md` or `BIGDP2026_6_DECISION_LEDGER.md`

---

## D. Acceptance Criteria Per R-Item

Each R-item requires ALL of:
1. **Code evidence** — `git diff` showing the change
2. **Runtime wiring evidence** — `grep` or code inspection confirming the new code is called at runtime
3. **Test evidence** — `pytest -v` output showing passing tests for the new behavior
4. **Checklist delta** — updated `BIGDP2026_6_ACCEPTANCE_CHECKLIST.md` (mark items PASS)
5. **Residual risk** — if any gap remains, document in repair report

---

## E. Stop Conditions

Halt and report to Controller if:
- [ ] pytest environment cannot execute tests (NOT the case — already verified)
- [ ] Expert decision table logic conflicts with existing runtime and cannot be resolved without architecture change
- [ ] Claude Code writer skill location cannot be found after exhaustive search
- [ ] Fixing any P0 item requires rewriting >200 lines of graph.py or pipeline.py
- [ ] Review v5 files are determined to be production path (Controller decision needed)
- [ ] Any expert rule has ambiguous regulatory interpretation

---

## F. Execution Order

```
R0 (Test unblock) → must complete first
  │
  ├─→ R3 (G46 hardening) → can start after R0
  ├─→ R2 (Handoff enforcement) → can start after R0
  └─→ R1 (Expert logic integration) → can start after R0; benefits from R3 context
       │
       └─→ R4 (Benchmark validation) → benefits from R1 context
            │
            └─→ R5 (Scope clarification) → last; depends on knowing what was changed
```

R1 and R3 are the highest-value repairs — they close the gap between "documentation-only" and "runtime-executable" expert reasoning.

---

## G. Repair Sprint Reports

All repair evidence goes into `BIGDP2026_6/repairs/`:
- `R0_TEST_UNBLOCK_REPORT.md`
- `R1_EXPERT_LOGIC_RUNTIME_INTEGRATION_REPORT.md`
- `R2_HANDOFF_ENFORCEMENT_REPORT.md`
- `R3_G46_HARDENING_REPORT.md`
- `R4_BENCHMARK_VALIDATION_REPORT.md`
- `R5_SCOPE_CLARIFICATION_REPORT.md`
