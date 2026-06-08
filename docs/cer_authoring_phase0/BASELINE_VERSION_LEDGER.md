# Baseline Version Ledger

Schema version: `phase0.2-locked-delta-analyzer-v1`

## Current Entries

| Date | Baseline / Run | Status | Reason | Required Action |
|---|---|---|---|---|
| 2026-05-09 | Project 1 Pilot before Phase 0.2 | `INVALID_DIAGNOSTIC` | Locked delta-only material was accessed outside an approved Delta Analyzer boundary. | Do not count toward Calibration Project 1. |
| 2026-05-09 | `PROJECT_01_PILOT_INVALID_DUE_TO_LOCKED_ACCESS_LEAKAGE` | `RECORDED` | HC2/HC6/HC8 leakage discipline was violated. | Require baseline version bump before rerun. |
| 2026-05-11 | `V2.6_PHASE6_EVIDENCE_WRITERS_FIX` | `ACTIVE_RUNTIME_FIX` | CAL-002 Phase 6 exposed a reproducible startup/module-loading blocker involving `pandas._libs.writers` native extension initialization. | Use V2.6 for reruns after the native preload guard; do not mix pre-fix CAL-002 results with V2.6 validation without stratification. |

## Rerun Rule

Project 1 may only be rerun after:

1. Phase 0.2 is accepted;
2. `authoring_baseline_version` is bumped;
3. the rerun uses only `01_INITIAL_INPUT_FOR_WRITER` before baseline freeze;
4. locked folders are consumed only by `scripts/calibration_delta_analyzer.py`;
5. no repair/finalization command runs before the frozen baseline and delta
   analysis are complete.

## Aggregate Calibration Rule

Formal three-project calibration may not mix baselines unless the aggregate
root-cause matrix explicitly stratifies results by baseline version.
