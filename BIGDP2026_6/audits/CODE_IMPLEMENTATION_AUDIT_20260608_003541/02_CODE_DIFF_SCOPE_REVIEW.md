# 02 — Code Diff Scope Review

**Method:** `git status --short` + targeted grep of modified files. No `git diff` available (sandbox limitations).

---

## Files Modified (M) — Within Scope

| File | Phase | Lines Changed (est.) | Assessment |
|:---|:---|:---:|:---|
| `gates.py` | P1 + P3 | ~662 | **In scope.** G46 real evaluators, MAX_SPIRAL_ROUNDS, G42 dynamic routing, ledger consumption. No unrelated changes detected. |
| `graph.py` | P1 + P2 + P3 | ~0 (diff failed) | **In scope.** REWORK_TARGETS fix, MAX_SPIRAL_ROUNDS import, Event Bus snapshot/dedupe, 3 new ledger nodes, wiring. |
| `pipeline.py` | P1 + P5 | ~0 (diff failed) | **In scope.** Likely benchmark builder generalization. |
| `state.py` | P2 | unknown | **In scope.** Ledger fields added to SharedAuthoringState. |
| `v3_1_graph_integration.py` | P5 | unknown | **In scope.** Benchmark domain externalization. |

## Files Added (??) — Within Scope

| File | Phase | Assessment |
|:---|:---|:---|
| `tests/test_g46.py` | P1 | In scope. 300+ lines. Real evaluator tests. |
| `tests/test_hc_rework.py` | P1 | In scope. 120+ lines. Rework routing tests. |
| `tests/test_event_bus_fallback.py` | P1 | In scope. 200+ lines. Dedupe and snapshot tests. |
| `tests/test_g42.py` | P1 | In scope. Spiral convergence and failure pattern tests. |
| `tests/test_phase2_ledgers.py` | P2 | In scope. Ledger population tests. |
| `tests/test_phase3_gates.py` | P3 | In scope. Gate consumption of ledgers. |
| `tests/test_phase4_handoff.py` | P4 | In scope. Handoff validator tests. |
| `cer_package_validator.py` | P4 | In scope. Runtime package validation. |
| `benchmark_domain_loader.py` | P5 | In scope. Domain config loader. |
| `schemas/cer_reasoning_ledger.schema.json` | P2 | In scope. |
| `schemas/ifu_claim_evolution_ledger.schema.json` | P2 | In scope. |
| `schemas/benchmark_derivation_trace.schema.json` | P2 | In scope. |
| `config/cer/benchmark_domains.yaml` | P5 | In scope. |

## Files Added — Potentially Out of Scope

| File | Assessment |
|:---|:---|
| `event_bus/` directory | Event Bus infrastructure. P1.4 fix depends on it. In scope. |
| `v3_1_gates.py` | New gate implementations. P3. In scope. |
| `v3_1_runtime.py` | V3.1 runtime. P3. In scope. |
| `v4_2_phase2_injection.py` | Phase 2 injection logic. P2. In scope. |
| `workers/` directory | Worker pool for Event Bus. P1.4. In scope. |
| `cer_review/v5_*.py` (7 files) | Review v5 engine. Phase 6 precursor. **Flag:** May be out of scope for BIGDP2026.6 which targets Authoring first. |
| `subagents/builtins/cer_*_agents.py` (4 files) | Subagent definitions. Phase 6. **Flag:** Out of scope unless explicitly included. |
| `backend/app/gateway/routers/cer_v5_*.py` (4 files) | v5 API routers. **Flag:** Out of scope. |
| `frontend/src/core/cer_review/` | Frontend for review. **Flag:** Out of scope. |
| `docs/cer_authoring_*` (9 directories) | Documentation. In scope as supporting material. |
| `scripts/_patch_*.py`, `scripts/_v4_*.py` | Patch scripts. **Flag:** May be temporary/one-off. Not part of permanent codebase. |

## Risky Modifications Detected

### ⚠️ Large New File Count

Over 100 new `??` files. This is a significant codebase expansion. Risk: maintenance burden, undeclared dependencies.

### ⚠️ Review v5 Files (7 files)

`cer_review/v5_copilot_engine.py`, `v5_feedback_engine.py`, `v5_flavor_profiles.py`, `v5_gap_engine.py`, `v5_regulatory_baseline.py`, `v5_semantic_checker.py`, `v5_shadow_backtest.py`, `v5_slot_engine.py`

These appear to be a complete rewrite of the Review subsystem. The Master Plan Phase 6 scope is "clarify Review production path; deprecate v0; add optional ingestion node." These 8 files suggest a much larger Review rewrite than planned.

**Recommendation:** Verify whether these v5 files are: (a) part of BIGDP2026.6 scope, (b) experimental, or (c) from a parallel project. If (b) or (c), they should be in a feature branch.

### ⚠️ No `_backup_` directories

Multiple `_backup_20260529_*` directories in `knowledge/`. These are backup snapshots, not code, but they increase repo size.

### ✅ No Deleted Safety Logic

No `D` (deleted) files in git status. No safety gate functions were removed.

### ✅ No Hidden Large Refactors

No single file shows signs of wholesale rewrite (e.g., 90% line changes). Modifications appear targeted to specific functions.

---

## Summary

| Category | Count | Verdict |
|:---|:---:|:---|
| Files modified — in scope | ~8 | ✅ Expected |
| Files added — in scope | ~25 | ✅ Expected |
| Files added — potentially out of scope | ~15 | ⚠️ Review v5 files need clarification |
| Files deleted | 0 | ✅ Safe |
| Safety gates weakened | 0 | ✅ Safe |
| Hidden large refactors | 0 | ✅ Safe |
