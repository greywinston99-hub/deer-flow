# Locked Access Policy

Schema version: `phase0.2-locked-delta-analyzer-v1`

## Purpose

Prevent calibration data leakage between baseline CER authoring and post-freeze
delta analysis.

`02_NB_ROUNDS_AND_RESPONSES_LOCKED` and
`03_FINAL_CERTIFIED_PACKAGE_LOCKED` are delta-only sources. They must never be
read by the authoring writer, DeerFlow authoring graph, Claude Code repair
loop, or finalization stage before `BASELINE_FROZEN`.

## Allowed Access

The only allowed locked-folder access path is:

```bash
backend/.venv/bin/python scripts/calibration_delta_analyzer.py \
  --baseline-root "<FROZEN_BASELINE_ARTIFACT_ROOT>" \
  --authoring-workbook "<FROZEN_BASELINE_ARTIFACT_ROOT>/authoring_workbook.json" \
  --qa-gate-report "<FROZEN_BASELINE_ARTIFACT_ROOT>/qa_gate_report.json" \
  --nb-locked-root "<PROJECT>/02_NB_ROUNDS_AND_RESPONSES_LOCKED" \
  --final-locked-root "<PROJECT>/03_FINAL_CERTIFIED_PACKAGE_LOCKED" \
  --output-dir "<PROJECT>/delta_analysis/<RUN_ID>"
```

This access is allowed only after:

1. baseline authoring has completed;
2. baseline artifacts are frozen;
3. `BASELINE_FROZEN_MANIFEST.json` or equivalent run metadata exists;
4. no repair/finalization command has been executed.

## Prohibited Access

Claude Code may not directly run `find`, `cat`, text extraction, xlsx parsing,
docx parsing, PDF extraction, or ad-hoc scripts over:

- `02_NB_ROUNDS_AND_RESPONSES_LOCKED`
- `03_FINAL_CERTIFIED_PACKAGE_LOCKED`

The authoring writer and DeerFlow `cer_authoring_v1` graph may not receive:

- NB LoQ;
- NB response matrices;
- human accepted CER;
- final certified CER package;
- submitted response supporting files;
- any extracted text from the locked folders.

## Analyzer Duties

The Delta Analyzer must:

- classify locked file roles as `NB_FEEDBACK`, `OUR_RESPONSE`,
  `SUBMITTED_SUPPORTING_FILE`, `FINAL_CHANGE_REFERENCE`, or `UNKNOWN`;
- tolerate mixed NB feedback, responses, matrices and submitted files in the
  same locked folder;
- write every locked file encountered to `LOCKED_ACCESS_LOG.csv`;
- write unclear files to `NEEDS_HUMAN_CLASSIFICATION.csv`;
- write outputs only to a separate delta-analysis output directory;
- avoid writing into `01_INITIAL_INPUT_FOR_WRITER`;
- avoid modifying frozen baseline artifacts;
- avoid triggering repair loop or final package generation.

## Output Readback

Claude Code may read analyzer outputs after the analyzer finishes:

- `DELTA_ANALYSIS_MANIFEST.json`
- the 8 delta tables;
- `LOCKED_ACCESS_LOG.csv`;
- `NEEDS_HUMAN_CLASSIFICATION.csv`;
- `PILOT_RUN_REPORT.md`.

Claude Code still may not read the locked folder originals directly.
