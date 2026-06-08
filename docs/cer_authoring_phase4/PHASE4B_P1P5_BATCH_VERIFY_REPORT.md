# PHASE4B — P1-P5 Batch Verification Report

Decision: `PHASE4B_EXECUTED_EFFECTIVENESS_PENDING`

## Scope

This batch verifies the content-effectiveness of Phase 4A P1-P5 using unified reruns for CAL-001, CAL-002 and CAL-003 followed by Semantic Delta analysis.

Patches covered:

- P1 Evidence Synthesis
- P2 Claim Coverage
- P3 SOTA Clinical Context
- P4 Writer Template Device-Class Adaptation
- P5 PMCF Boundary Precision

## Authoring Rerun Results

| Project | Run directory | Final gate | Failed gates | Writer template | PMCF boundary rows |
|---|---|---|---:|---|---:|
| CAL-001 | `artifacts/cer_cowork/CAL-001/authoring/PHASE4B_P1P5_20260510_CAL001B` | `PASS_TO_DRAFT_DOCX` | 0 | `therapeutic_catheter_rf_ablation` | 3 |
| CAL-002 | `artifacts/cer_cowork/CAL-002/authoring/PHASE4B_P1P5_20260510_CAL002` | `REWORK_REQUIRED` | 1 (`G1e`) | `software_medical_device` | 3 |
| CAL-003 | `artifacts/cer_cowork/CAL-003/authoring/PHASE4B_P1P5_20260510_CAL003` | `REWORK_REQUIRED` | 1 (`G1e`) | `surgical_implant_ligating_clip` | 1 |

CAL-001 was rerun twice during PHASE4B because the first P4 output selected `software_medical_device` due to incidental software-control wording in the RF ablation catheter source profile. The selector was corrected so locked cardiovascular RF ablation identity takes precedence over incidental software terms. CAL-001B is the valid PHASE4B CAL-001 run.

## Semantic Delta Results

Per-case delta outputs:

- CAL-001B: `artifacts/cer_cowork/CAL-001/authoring/PHASE4B_P1P5_20260510_CAL001B/delta_analysis`
- CAL-002: `artifacts/cer_cowork/CAL-002/authoring/PHASE4B_P1P5_20260510_CAL002/delta_analysis`
- CAL-003: `artifacts/cer_cowork/CAL-003/authoring/PHASE4B_P1P5_20260510_CAL003/delta_analysis`

Cross-project aggregation:

- `artifacts/cer_cowork/phase4b_p1p5_semantic_delta_aggregation_v2`

Summary:

| Metric | Result |
|---|---:|
| Usable semantic cases | 3 / 3 |
| Semantic rows | 1247 |
| Low-confidence rows | 304 |
| Automatic high-confidence rate | 75.6% |
| Gold sections indexed | 6381 |
| Gold citations indexed | 454 |
| NB-relevant material deltas | 429 |

## Effectiveness Interpretation

P4 and P5 are structurally verified:

- CAL-001 now uses the RF therapeutic catheter template.
- CAL-002 uses the SaMD / AI diagnostic template.
- CAL-003 uses the surgical implant ligating clip template.
- All three runs emit `pmcf_boundary_decision_log`.

However, Semantic Delta does **not** yet support removing or fully downgrading all COGs. The cross-project aggregation still reports:

- `knowledge_gap`: 225 semantic candidate deltas across 3 cases, all NB-relevant/high-materiality.
- `needs_human_confirmation`: high residual low-confidence/human-gate burden.

Therefore:

- P1-P5 implementation is accepted.
- Content-effectiveness is partially demonstrated but remains pending semantic re-validation at a more granular COG level.
- COGs should not be marked removed solely from gate pass rate.

## Remaining Blocking / Rework Signals

CAL-002 and CAL-003 still fail `G1e` domain contamination:

- CAL-002: high-severity `stent` token remains in profile/core chapters.
- CAL-003: high-severity `stent`, `urinary tract`, `ureteroscope`, and `renal pelvis` tokens remain in profile/core chapters.

This is outside P5. It should be treated as a domain-contamination/source-writing hygiene issue before declaring Phase 4A fully effective.

## Commands Executed

Implementation/test:

```bash
backend/.venv/bin/python -m py_compile backend/packages/harness/deerflow/runtime/cer_authoring/pipeline.py backend/packages/harness/deerflow/runtime/cer_authoring/state.py backend/packages/harness/deerflow/runtime/cer_authoring/artifacts.py
backend/.venv/bin/python -m pytest backend/tests/test_cer_authoring_runtime.py -k "phase4_4 or phase4_5" -q
backend/.venv/bin/python -m pytest backend/tests/test_cer_authoring_runtime.py -q
```

Results:

- P4/P5 targeted tests: `9 passed, 47 deselected`
- Full CER authoring runtime tests: `56 passed`

Batch rerun:

```bash
backend/.venv/bin/python backend/scripts/run_cer_authoring.py --strict-v7 --agent-team-mode stable-1plus6 ...
backend/.venv/bin/python scripts/calibration_delta_analyzer.py ...
backend/.venv/bin/python scripts/calibration_delta_analyzer.py --case-output-dir ... --aggregate-output-dir ...
```

## Final Label

`PHASE4B_EXECUTED_EFFECTIVENESS_PENDING`

COGs are not removed/downgraded until semantic re-validation confirms the specific COG-level reduction.
