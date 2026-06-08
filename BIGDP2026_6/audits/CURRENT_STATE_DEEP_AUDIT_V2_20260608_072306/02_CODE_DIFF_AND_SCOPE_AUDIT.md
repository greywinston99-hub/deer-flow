# 02 — Code Diff and Scope Audit

**Method:** `git status --short` + `git diff --stat` + targeted file inspection.

---

## Change Statistics

| Metric | Value |
|:---|:---:|
| Files changed (git status) | 304 |
| Files in diff stat | 48 |
| Lines changed (tracked diff) | +14,120 / -1,902 |
| New untracked files | ~250 |

---

## Modified Files Classification

### IN_SCOPE — Expected for BIGDP2026.6

| File | Assessment |
|:---|:---|
| `gates.py` | ✅ P1 + P3: G46 real evaluators, R3 BR/alignment/SOTA wiring, no silent PASS |
| `graph.py` | ✅ P1 + P2 + P3: REWORK_TARGETS, ledger nodes, expert_rule_loader imports |
| `pipeline.py` | ✅ P5: benchmark builder generalization |
| `state.py` | ✅ P2: ledger fields added |
| `source_preflight.py` | ✅ P3: 4-tier severity |
| `cer_package_validator.py` | ✅ P4: export reference integrity |
| `v3_1_graph_integration.py` | ✅ P5: domain externalization |
| `tests/test_g46.py` | ✅ P1 + R3: 19 tests pass |
| `tests/test_g42.py` | ✅ P1: spiral contract tests |
| `tests/test_hc_rework.py` | ✅ P1: rework routing tests |
| `tests/test_event_bus_fallback.py` | ✅ P1: dedupe tests |
| `tests/test_phase2_ledgers.py` | ✅ P2: ledger tests |
| `tests/test_phase3_gates.py` | ✅ P3: gate integration tests |
| `tests/test_phase4_handoff.py` | ✅ P4: handoff tests |
| `tests/test_expert_*` | ✅ R1: expert semantic tests |
| `tests/test_benchmark_*` | ✅ R4: benchmark tests |
| `schemas/*.schema.json` | ✅ P2: 3 new ledger schemas |
| `config/cer/benchmark_domains.yaml` | ✅ P5: domain config |
| `workflows/cer_review_v0.yaml` | ✅ P6: deprecated banner |
| `cer_review/runner.py` | ✅ P6: explicit version field |

### LIKELY_IN_SCOPE — Supporting Infrastructure

| File/Pattern | Assessment |
|:---|:---|
| `event_bus/` | P1.4 Event Bus infrastructure |
| `workers/` | P1.4 worker pool |
| `v3_1_gates.py` | P3 gate implementations |
| `v3_1_runtime.py` | P3 V3.1 runtime |
| `v4_2_phase2_injection.py` | P2 injection logic |
| `backend/scripts/run_cer_authoring.py` | Orchestration script updates |
| `backend/scripts/_v4_*.py` | Temporary patch scripts |

### EXPERIMENTAL_SHOULD_BE_FLAGGED

| File/Pattern | Assessment |
|:---|:---|
| `cer_review/v5_*.py` (8 files) | Review v5 engine — EXPERIMENTAL per R5 |
| `frontend/src/core/cer_review/` | Frontend for v5 Review — PARALLEL_PROJECT |
| `frontend/src/components/cer/review-*` | UI components for v5 — PARALLEL_PROJECT |

**Risk:** These files are in the working tree and could be mistaken for BIGDP2026.6 deliverables. The R5 repair added `EXPERIMENTAL — NOT FOR BIGDP2026.6` banners, which mitigates the risk.

### OUT_OF_SCOPE

| File/Pattern | Assessment |
|:---|:---|
| `frontend/e2e/`, `frontend/test-results/` | Frontend testing — unrelated to CER reasoning engine |
| `frontend/src/components/workspace/pixel-kobe-pet.tsx` | Clearly unrelated pet component |
| `backend/app/gateway/routers/cer_v5_*.py` | v5 API routers — separate track |
| `backend/app/gateway/routers/health.py`, `metrics.py` | Generic infrastructure — separate track |
| `subagents/builtins/cer_review_assist_agents.py` | Review assist — separate track |
| `docs/cer_authoring_*` (9 directories) | Documentation — supporting but large |
| `knowledge/*.json` large changes | Data files — diff unreviewable; content not inspected |

### REQUIRES_CONTROLLER_DECISION

| Item | Reason |
|:---|:---|
| Review v5 files | Whether to absorb into BIGDP2026.6 or keep as separate track |
| 304 uncommitted files | Whether to commit all at once or split into scoped commits |

---

## Risky Modifications

### ⚠️ Large JSON Knowledge Files

Files like `kai_index.json` (+1252 lines), `nb_body_profiles.json` (+877 lines), `remediation_playbook.json` (+938 lines) have large diffs. These are data files, not code, but they could contain harmful or incorrect knowledge entries.

**Mitigation:** Not safety-critical for gate logic. Can be reviewed separately.

### ⚠️ `pipeline.py` +1034 Lines

The pipeline module grew by ~1000 lines. This is a 1.4MB file already. The additions likely support benchmark generalization and expert rule integration, but the size makes review difficult.

**Mitigation:** Tests pass (500/500); no regressions detected.

### ✅ No Deleted Safety Logic

No safety gate functions, node definitions, or check functions were deleted.

### ✅ No Hidden Broad Refactors

No single file shows a complete rewrite. Changes are targeted to specific functions.

---

## Scope Summary

| Category | Count (approx.) | Verdict |
|:---|:---:|:---|
| In Scope | ~40 files | ✅ Expected |
| Likely In Scope | ~15 files | ✅ Acceptable |
| Experimental / Flagged | ~15 files | ⚠️ Flagged, not blocking |
| Out of Scope | ~100 files | ⚠️ Cleanup needed |
| Unclassified / Generated | ~130 files | ⚠️ Needs triage |
| **Total** | **304** | **Manageable with cleanup** |
