# BIGDP2026.6 — Baseline Preflight Report

**Date:** 2026-06-07
**Preflight performed by:** BIGDP2026.6 Implementer (Claude Code)
**Status:** SAFE TO PROCEED (Working tree dirty but planned changes are isolated)

---

## 1. Git State

| Field | Value |
|:---|:---|
| **Branch** | `main` |
| **Working tree** | DIRTY — 35 modified files in `backend/` |
| **Recent commits** | 5 commits, latest: `ca95ccd8 V2: HC-3/3.5/4 upgrade` |
| **Staged changes** | None (all unstaged) |
| **Unpushed commits** | Unknown (not checked) |
| **Risk** | LOW — modified files are in the same package as planned changes; no conflicts expected |

**Assessment:** The dirty working tree is from prior V2 HC upgrade work and contains related changes. Since BIGDP2026.6 changes are in the same files (`graph.py`, `gates.py`), the existing modifications must be preserved during our changes.

---

## 2. Control Files Status

| File | Present | Status |
|:---|:---:|:---|
| `BIGDP2026_6_MASTER_UPGRADE_PLAN.md` | ✅ | Complete |
| `BIGDP2026_6_ACCEPTANCE_CHECKLIST.md` | ✅ | Complete (114 items, all NOT_CHECKED) |
| `BIGDP2026_6_PHASE_STATUS.md` | ✅ | Complete (Phase 0 ACCEPTED, Phases 1-7 NOT_STARTED) |
| `BIGDP2026_6_DECISION_LEDGER.md` | ✅ | Complete (7 decisions recorded) |
| `BIGDP2026_6_LOOP_STATE.md` | ❌ | To be created |
| `BIGDP2026_6_BASELINE_PREFLIGHT.md` | — | This file, being created now |
| `PREFLIGHT_BLOCKER_REPORT.md` | ❌ | Not needed (no blockers) |

---

## 3. Key Source Files

| File | Path | Lines | Status |
|:---|:---|:---:|:---|
| `graph.py` | `backend/packages/harness/deerflow/runtime/cer_authoring/graph.py` | 2,607 | Modified (dirty) |
| `gates.py` | `backend/packages/harness/deerflow/runtime/cer_authoring/gates.py` | 3,898 | Modified (dirty) |
| `pipeline.py` | `backend/packages/harness/deerflow/runtime/cer_authoring/pipeline.py` | 26,443 | Modified (dirty) |

---

## 4. Test Baseline

### 4.1 Existing Test Files (authoring tests directory)

**Location:** `backend/packages/harness/deerflow/runtime/cer_authoring/tests/`

42 test files exist. Key files for BIGDP2026.6:

| Test File | Lines | Tests | Pass | Fail | Notes |
|:---|:---:|:---:|:---:|:---:|:---|
| `test_g46.py` | 178 | 26 | 11 | 15 | Pre-existing failures: `_ws_pass_state()` fixture incomplete for WS gates |
| `test_g42.py` | — | 17 | 17 | 0 | All passing |
| `test_event_bus.py` | 8,689 | 17 | 17 | 0 | All passing |
| `test_hc_gate_default_pause_mode.py` | — | Not run | — | — | Exists but not yet tested |
| `test_source_preflight.py` | — | Not run | — | — | Exists but not yet tested |

### 4.2 Pre-Existing G46 Test Failures — Root Cause Analysis

The 15 failing G46 tests share the same root cause: the `_ws_pass_state()` fixture does not provide enough state to satisfy the WS (Writer Safety) sub-gates integrated into `evaluate_pre_writer_readiness_gate()`.

Specifically, the G46 aggregator now evaluates:
- **WS4_PRISMA** — needs `prisma_flow_data` ✅ (provided)
- **WS7_EQUIVALENCE** — needs equivalence route data ❌ (missing)
- **WS2_IFU_OVERCLAIM** — needs IFU alignment ledger ❌ (missing)
- **WS3_CLAIM_ELIGIBILITY** — needs claim eligibility data ❌ (missing)
- **BR closure** — needs `benefit_risk_closure_matrix` ❌ (missing)
- **CEP gate** — needs CEP data ❌ (partially provided)

These are **pre-existing test fixture issues**, not code defects. The WS gate integration happened after the G46 tests were written, and the fixture wasn't updated. This will be fixed in Phase 1 as part of P1.1 (when we implement real evaluators, the fixture must be updated to match).

### 4.3 Test Environment

| Item | Value |
|:---|:---|
| **Python** | 3.12.5 (venv at `.venv/bin/python3`) |
| **pytest** | 9.0.3 |
| **langgraph** | Available in venv |
| **Test runner** | `.venv/bin/python3 -m pytest` |
| **Root dir** | `backend/` (has `pyproject.toml`) |
| **System Python** | 3.14.3 (brew) — lacks langgraph |

---

## 5. P0 Defect Code Evidence (Verified)

### 5.1 P1.1 — G46 Auto-Downgrade

**Location:** `gates.py:254-264`

```python
_PLACEHOLDER_ONLY_CONDITIONS = {"claim_evidence", "retrieval_completeness"}
if status == "BLOCKED" and condition in _PLACEHOLDER_ONLY_CONDITIONS:
    status = "REWORK_REQUIRED"
```

**Impact:** Writer can be released without verified claim-evidence links and without complete retrieval coverage.

**Current real evaluators** (lines 267-277):
- `_check_endpoint_framework_locked` — real (line 933)
- `_check_clinical_data_consolidated` — real (line 953)
- `_check_eu_market_status_set` — real (line 973)

**Remaining placeholder conditions** (no dedicated evaluator):
- `claim_evidence` — downgraded placeholder
- `retrieval_completeness` — downgraded placeholder
- `identity`, `evidence_sufficiency`, `retrieval_domain`, `screening_pool`, `fulltext_basis`, `SOTA`, `BR`, `alignment` — overridden only

### 5.2 P1.2 — HC-01 Empty REWORK_TARGETS

**Location:** `graph.py:161-163`

```python
REWORK_TARGETS: dict[str, list[str]] = {
    "intake_pack_review": ["input_gate"],
    "device_profile": [],  # ← EMPTY — rework silently dropped
```

**Impact:** When human requests rework at HC-01 (device profile), `_check_hc_rework` (line 179) checks `target in REWORK_TARGETS.get(confirmation_point, [])` — which is `[]` for `device_profile`. Any rework target is silently rejected; the graph continues forward with incorrect device identity.

### 5.3 P1.3 — MAX_SPIRAL_ROUNDS Scattered

**Locations (all hardcoded `3`):**
- `graph.py:1100` — `_route_after_sota_endpoint_gate`: `max_rounds=3`
- `graph.py:1160` — `_route_after_evidence_sufficiency_gate`: `max_rounds=3`
- `graph.py:1235` — `_route_after_claim_evidence_gate`: `max_rounds=3`
- `graph.py:2069` — `_should_continue_spiral` default: `max_rounds: int = 3`
- `gates.py:797` — hardcoded `current_round >= 3` check

**No single `MAX_SPIRAL_ROUNDS` constant exists.**

### 5.4 P1.4 — Event Bus Fallback

**Location:** `graph.py:900-910`

```python
if _event_bus_available():
    try:
        generated = _run_evidence_appraisal_event_bus(dict(state))
    except Exception as exc:
        logger.warning("Event Bus evidence_appraisal failed, falling back to serial: %s", exc)
if generated is None:
    generated = pipeline.appraise_evidence(dict(state))
```

**Issue:** No state snapshot before Event Bus attempt. If Event Bus partially publishes some evidence and then fails, the state may be polluted with partial results. The serial fallback then runs on potentially already-polluted state, and results from both paths may have duplicate `evidence_id`.

---

## 6. Environment Limitations

| Limitation | Impact | Mitigation |
|:---|:---|:---|
| Tests must run in venv (`.venv/bin/python3`) | System Python 3.14 lacks langgraph | Document command prefix |
| No real Event Bus for integration tests | Fallback path can only be unit-tested | Mock Event Bus in tests |
| Working tree dirty | Cannot git reset easily | Use `git stash` if conflicts arise |
| No real CER project available for dry-run (Phase 7) | Full validation limited | Use mock/integration test fixtures |

---

## 7. Risk Assessment

| Risk | Severity | Likelihood | Mitigation |
|:---|:---:|:---:|:---|
| Phase 1 changes conflict with dirty working tree | MEDIUM | LOW | All changes are in same files already modified; use careful diffs |
| G46 real evaluator breaks existing WS gate integration | HIGH | MEDIUM | Add evaluators without changing aggregate logic shape |
| HC-01 rework routing change breaks graph edges | MEDIUM | LOW | Only adds to REWORK_TARGETS dict; no graph edge changes |
| MAX_SPIRAL_ROUNDS centralization changes behavior | LOW | LOW | Value remains 3; just centralized |
| Event Bus fallback dedupe adds overhead | LOW | LOW | Snapshot + dedupe are cheap operations |
| Pre-existing test failures mask new regressions | MEDIUM | HIGH | Fix test fixture first; then add new tests |

---

## 8. Recommended Execution Order

Phase 1 items can be executed in any order (independent code paths), but the recommended order is:

1. **P1.3 MAX_SPIRAL_ROUNDS centralization** — Simplest change, lowest risk, establishes the constant that other changes reference
2. **P1.2 HC-01 rework repair** — Isolated change to `REWORK_TARGETS` dict
3. **P1.4 Event Bus fallback dedupe** — Changes to `_node_evidence_appraisal` in graph.py
4. **P1.1 G46 real evaluator + remove auto-downgrade** — Most complex change, highest risk, but most important

---

## 9. Verdict

**SAFE TO PROCEED.** No blockers detected. The working tree is dirty but all changes will be in-scope. Pre-existing test failures are understood (fixture mismatch from WS gate integration). Phase 1 can begin immediately.

**Next action:** Enter Phase 1 — P0 Runtime Safety Repair.
