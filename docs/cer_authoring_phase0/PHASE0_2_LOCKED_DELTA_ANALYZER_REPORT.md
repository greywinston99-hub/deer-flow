# Phase 0.2 Locked Delta Analyzer Report

Date: 2026-05-09

## Executive Summary

Phase 0.2 adds a standalone locked Delta Analyzer to close the HC2/HC6/HC8
leakage issue observed in the Project 1 Pilot.

The patch does not modify:

- SOTA Agent logic;
- Evidence Appraisal logic;
- Writer Contract;
- Benefit-Risk Rule;
- PMCF Boundary Rule;
- Alignment Rule;
- Gate Logic;
- Project 1 artifacts.

## Problem Addressed

The previous Project 1 Pilot directly accessed locked delta-only material in
`02_NB_ROUNDS_AND_RESPONSES_LOCKED` outside a controlled analyzer boundary.
Therefore it is marked:

`PROJECT_01_PILOT_INVALID_DUE_TO_LOCKED_ACCESS_LEAKAGE`

and cannot count as Calibration Project 1.

## Implemented Components

- `scripts/calibration_delta_analyzer.py`
- `docs/cer_authoring_phase0/LOCKED_ACCESS_POLICY.md`
- `docs/cer_authoring_phase0/PILOT_CALIBRATION_PROTOCOL.md`
- `docs/cer_authoring_phase0/BASELINE_VERSION_LEDGER.md`
- `docs/cer_authoring_phase0/DECISION_LOG.md`
- `backend/tests/test_calibration_delta_analyzer.py`

## Analyzer Inputs

- frozen baseline artifact root;
- frozen `authoring_workbook.json`;
- frozen `qa_gate_report.json`;
- `02_NB_ROUNDS_AND_RESPONSES_LOCKED`;
- `03_FINAL_CERTIFIED_PACKAGE_LOCKED`;
- separate delta-analysis output directory.

## Analyzer Outputs

- `CLAIM_DELTA_TABLE.csv`
- `SOTA_BENCHMARK_DELTA_TABLE.csv`
- `EVIDENCE_SELECTION_DELTA_TABLE.csv`
- `EVIDENCE_APPRAISAL_DELTA_TABLE.csv`
- `CLAIM_EVIDENCE_DELTA_MATRIX.csv`
- `PMCF_BOUNDARY_DELTA_TABLE.csv`
- `ALIGNMENT_DELTA_TABLE.csv`
- `CEAR_DEFICIENCY_PATTERN_TABLE.csv`
- `DELTA_ANALYSIS_MANIFEST.json`
- `LOCKED_ACCESS_LOG.csv`
- `NEEDS_HUMAN_CLASSIFICATION.csv`
- `PILOT_RUN_REPORT.md`

## Locked Folder Handling

The analyzer classifies locked files as:

- `NB_FEEDBACK`
- `OUR_RESPONSE`
- `SUBMITTED_SUPPORTING_FILE`
- `FINAL_CHANGE_REFERENCE`
- `UNKNOWN`

Mixed NB feedback, responses, response matrices and submitted files in the same
folder are allowed. Unclear files are not rejected; they are written to
`NEEDS_HUMAN_CLASSIFICATION.csv`.

## Access Control

The analyzer:

- logs every locked file it scans in `LOCKED_ACCESS_LOG.csv`;
- rejects output directories under baseline, locked roots, or
  `01_INITIAL_INPUT_FOR_WRITER`;
- writes only to the separate delta-analysis output directory;
- does not modify frozen baseline artifacts;
- does not trigger repair/finalization;
- does not run Project 1.

## Verification

Targeted test:

```bash
backend/.venv/bin/python -m pytest backend/tests/test_calibration_delta_analyzer.py -q
```

Expected result:

```text
2 passed
```

Regression checks should also include:

```bash
backend/.venv/bin/python -m pytest backend/tests/test_cer_authoring_runtime.py backend/tests/test_cer_cowork_supervisor.py -q
```

## Acceptance Conclusion

`PHASE0_2_ACCEPTED_FOR_PROJECT1_RERUN`

Project 1 rerun remains blocked until the baseline version is bumped.
