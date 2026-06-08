# BIGDP2026.6 — Repair Sprint Scope Lock

**Status:** `ACCEPT_WITH_REPAIRS`
**Purpose:** Define exactly what IS and IS NOT in the Repair Sprint scope.
**Controller:** BIGDP2026.6 Controller

---

## IN SCOPE ✅

### R0: Test Execution
- Fix `test_cal001_integration.py::test_t1_graph_compilation` (`self_inspection` assertion)
- Run full cer_authoring test suite → 0 failures
- All 7 BIGDP test files must pass

### R1: Expert Logic Pack Runtime Integration
- Create `runtime/expert_rule_loader.py` (YAML → typed rule objects)
- Wire rulebook into `_node_build_reasoning_ledger` (`graph.py`)
- Wire IFU rules into `_node_build_ifu_evolution_ledger` (`graph.py`)
- Wire benchmark rules into `_node_build_benchmark_trace` (`graph.py`)
- Wire human gate rules into G46 / HC routing (`gates.py`)
- Create `test_expert_logic_consumption.py` (fixture-driven)
- Files touched: `graph.py` (3 node functions), `gates.py` (G46 loop + HC routing), +1 new file

### R2: Claude Code Handoff Enforcement
- Locate or create writer package validator entrypoint
- MUST exist: validator that reads `CER_INPUT_PACKAGE.json` and asserts ALL 8 checks
- Writer skill must invoke validator before writing any CER section
- Files touched: `.claude/skills/` or `skills/` (1 file), or `BIGDP2026_6/repairs/`

### R3: G46 Evaluator Hardening
- Wire existing G44 (BR), G45 (alignment), SOTA benchmark evaluators into G46 conditions
- Implement real evaluators for remaining fallback conditions OR add `controlled_deferral` with explicit rationale
- Safety-critical rule: no patient-safety condition defaults to PASS
- Files touched: `gates.py` (G46 loop), `v3_1_gates.py` (may reuse SOTA evaluator)

### R4: Benchmark Generalization
- Create or verify runtime loader for `benchmark_domains.yaml`
- End-to-end test: new domain → benchmark generated without code change
- Regression test: existing domains unchanged
- Files touched: `pipeline.py` (benchmark builder), +1 test file

### R5: Scope Clarification
- Audit all modified files against BIGDP2026.6 scope
- Classify out-of-scope files
- Add experimental/feature-flag markers as appropriate
- Files touched: `BIGDP2026_6_REPAIR_SPRINT_SCOPE_LOCK.md`

### Repair Sprint Reports
- 6 report files in `BIGDP2026_6/repairs/` (one per R-item)
- Updated `BIGDP2026_6_ACCEPTANCE_CHECKLIST.md`

---

## OUT OF SCOPE ❌

These items are EXPLICITLY excluded from the Repair Sprint:

### Phase 6: Review Feedback Boundary
- **NOT IN SCOPE.** Phase 6 was NOT_STARTED per audit. No code changes exist.
- The existing advisory-only boundary is safe (`08_GLOBAL_CORRECTNESS_AUDIT.md` §7).

### Phase 7: Full Validation
- **NOT IN SCOPE.** Requires real project dry-run which is a post-repair activity.
- The Repair Sprint enables Phase 7; it does not execute Phase 7.

### Source Preflight 4-Tier Upgrade
- **NOT IN SCOPE.** Per `09_RESIDUAL_GAP_REGISTER.csv` GAP-007: still 2-tier.
- Deferred per Decision Ledger D-006. Not blocking expert reasoning upgrade.

### Review v5 Files
- **NOT IN SCOPE.** Per GAP-011: scope unclear. R5 classifies them but does not modify.
- If determined to be production path → Controller decision required (separate from Repair Sprint).

### Full Pipeline Dry-Run
- **NOT IN SCOPE.** Post-repair activity (Phase 7).

### Claude Code Skill Full Implementation
- **NOT IN SCOPE.** R2 creates the validator + documents invocation path.
- R2 does NOT rewrite the entire `cer-authoring-section-writer` skill.

### Intake 15-State Full Traversal
- **NOT IN SCOPE.** Intake subsystem untouched by BIGDP2026.6 (`08_GLOBAL_CORRECTNESS_AUDIT.md` §8).

### GSPR Coverage Deep Fix (BLG-014)
- **NOT IN SCOPE.** Deferred per D-006. Not blocking expert reasoning.

### V3.1 Intermediate Node Gates (BLG-015)
- **NOT IN SCOPE.** Deferred per D-006. Post-BIGDP2026.6 track.

### Review Workflow Migration
- **NOT IN SCOPE.** `cer_review_v0.yaml` deprecated banner exists. Migration is Phase 6, not Repair Sprint.

---

## Files That MAY Be Modified

| File | Scope Limit |
|:---|:---|
| `gates.py` | G46 loop, HC routing, gate evaluator wiring — scoped edits |
| `graph.py` | 3 ledger node functions, export node, rework routing — scoped edits |
| `pipeline.py` | Benchmark domain loader integration — minimal edit |
| `v3_1_gates.py` | May reuse SOTA evaluator for G46 — read-only + import |
| `test_cal001_integration.py` | Fix `self_inspection` assertion — 1-line change |

## Files That MAY Be Created

| File | Purpose |
|:---|:---|
| `runtime/cer_authoring/expert_rule_loader.py` | YAML → typed rule objects |
| `tests/test_expert_logic_consumption.py` | Fixture-driven expert logic tests |
| `BIGDP2026_6/repairs/writer_package_validator.py` | Standalone Claude Code handoff validator |
| `BIGDP2026_6/repairs/HANDOFF_VALIDATOR_README.md` | Validator documentation |
| `BIGDP2026_6/repairs/R*_REPORT.md` (6 files) | Repair evidence reports |

## Files That MUST NOT Be Modified

| File | Reason |
|:---|:---|
| `BIGDP2026_6_MASTER_UPGRADE_PLAN.md` | Phase 0 ACCEPTED — frozen |
| `BIGDP2026_6_DECISION_LEDGER.md` | Phase 0 ACCEPTED — frozen |
| `BIGDP2026_6_PHASE_STATUS.md` | Controller-only update after repair verification |
| `cer_intake.py` | Intake untouched by BIGDP2026.6 |
| `cer_review/runner.py` | Review migration is Phase 6 — NOT in repair sprint |
| Any file with `v5_` prefix | Review v5 is out of scope for repair sprint |

---

## Verification Gate

Before Repair Sprint is marked complete, Controller verifies:
1. `pytest -q` → 0 failures (R0)
2. `grep -r "EXPERT_REASONING_RULEBOOK\|CLAIM_CLASSIFICATION_DECISION\|IFU_CLAIM_TRANSFORMATION" gates.py graph.py` → matches found (R1)
3. `grep -r "validate_cer_input_package\|cer_package_validator" .claude/skills/ skills/ BIGDP2026_6/repairs/` → matches found (R2)
4. Manual code inspection: no G46 condition silently defaults to PASS (R3)
5. `pytest -k test_benchmark` → passes including unknown domain test (R4)
6. All out-of-scope files classified in this document (R5)
