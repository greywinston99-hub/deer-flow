# Pilot Calibration Protocol

Schema version: `phase0.2-locked-delta-analyzer-v1`

## Status

Current rule: Project 1 must not be rerun until Phase 0.2 is accepted and the
baseline version is bumped.

The previous Project 1 Pilot is classified as:

`PROJECT_01_PILOT_INVALID_DUE_TO_LOCKED_ACCESS_LEAKAGE`

Reason: locked delta-only material was read and manually classified outside an
approved Delta Analyzer boundary.

## Pilot Sequence

1. Put only writer-allowed source files in `01_INITIAL_INPUT_FOR_WRITER`.
2. Run DeerFlow authoring through the approved supervisor entrypoint.
3. Do not run any Claude repair, finalization, controlled patch, or review
   modification command.
4. Freeze baseline artifacts.
5. Preserve the original authoring QA gate failures as calibration evidence.
6. Run `scripts/calibration_delta_analyzer.py`.
7. Read only analyzer outputs.
8. Produce pilot closeout.

## Locked Folder Rule

Claude Code may not directly run `find`, `cat`, text extraction, xlsx parsing,
docx parsing, PDF extraction, or ad-hoc scripts over:

- `02_NB_ROUNDS_AND_RESPONSES_LOCKED`
- `03_FINAL_CERTIFIED_PACKAGE_LOCKED`

The only allowed locked access path is through
`scripts/calibration_delta_analyzer.py` after `BASELINE_FROZEN`.

## Analyzer Command

```bash
backend/.venv/bin/python scripts/calibration_delta_analyzer.py \
  --baseline-root "<FROZEN_BASELINE_ARTIFACT_ROOT>" \
  --authoring-workbook "<FROZEN_BASELINE_ARTIFACT_ROOT>/authoring_workbook.json" \
  --qa-gate-report "<FROZEN_BASELINE_ARTIFACT_ROOT>/qa_gate_report.json" \
  --nb-locked-root "<PROJECT>/02_NB_ROUNDS_AND_RESPONSES_LOCKED" \
  --final-locked-root "<PROJECT>/03_FINAL_CERTIFIED_PACKAGE_LOCKED" \
  --output-dir "<PROJECT>/delta_analysis/<RUN_ID>" \
  --json
```

## Required Analyzer Outputs

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

## Hard Stops

Stop and mark the run invalid if:

- locked folder originals are read outside the analyzer;
- authoring baseline is repaired before delta analysis;
- output directory is under baseline, locked folders, or
  `01_INITIAL_INPUT_FOR_WRITER`;
- authoring writer receives any locked content;
- a holdout project is consumed.
