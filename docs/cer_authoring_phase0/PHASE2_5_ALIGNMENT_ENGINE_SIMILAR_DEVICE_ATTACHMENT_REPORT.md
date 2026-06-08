# Phase 2.5 Alignment Engine / Similar-Device Attachment Hardening Report

Date: 2026-05-10

## Conclusion

`PHASE2_5_ACCEPTED_FOR_CCD_READ_ONLY_VALIDATION`

AGG-003 / G33 recurrence was addressed by hardening deterministic similar-device four-step and attachment-index generation. The patch does not change G33 pass/fail criteria, does not change 1+6 agent roles/prompts, and does not change any other gate criteria.

## Root Cause Addressed

G33 requires:

1. four similar-device confirmation steps;
2. at least 10 baseline attachment request rows;
3. each attachment row must contain:
   - `required_document`
   - `use_in_cer`
   - `if_missing`

Before this patch, generated attachment rows used adjacent field names such as `required_content`, `purpose`, and `available_source_hint`, which made the artifact useful to humans but incomplete for the actual G33 contract. A second failure mode existed when `equivalence_matrix` was already present: `run_device_equivalence_search()` returned early, so missing four-step/attachment rows were never backfilled.

## Implemented Changes

### 1. No Early Return When G33 Artifacts Are Missing

`run_device_equivalence_search()` now returns early only when all three are present:

- `equivalence_matrix`
- complete `similar_device_four_step_confirmation`
- complete `similar_device_attachment_index`

If `equivalence_matrix` exists but G33 artifacts are missing/incomplete, the function backfills similar-device four-step rows and the attachment index without rerunning MCP/public searches.

### 2. Attachment Index Mandatory Fields

`_similar_device_attachment_rows()` now emits at least 10 baseline rows with the actual G33-required fields:

- `attachment_id`
- `row_id`
- `subject_device`
- `attachment_type`
- `required_document`
- `required_content`
- `purpose`
- `source_hint`
- `available_source_hint`
- `source_status`
- `status`
- `use_in_cer`
- `if_missing`
- `conclusion`

### 3. Legacy Row Hardening

Existing legacy/partial rows are preserved and hardened:

- `required_content` is promoted to `required_document`
- source hints are normalized
- missing `use_in_cer` and `if_missing` controls are filled
- additional rows are retained with mandatory fields

### 4. Artifact Consumption Contract

The Phase 0 artifact consumption contract now explicitly lists:

- `similar_device_four_step_confirmation`
- `similar_device_attachment_index`

with producer, consumer and calibration use.

## Files Changed

- `backend/packages/harness/deerflow/runtime/cer_authoring/pipeline.py`
- `backend/packages/harness/deerflow/runtime/cer_authoring/phase0_contracts.py`
- `backend/tests/test_cer_authoring_runtime.py`
- `docs/cer_authoring_phase0/PHASE2_5_ALIGNMENT_ENGINE_SIMILAR_DEVICE_ATTACHMENT_REPORT.md`

## Constraints Confirmed

- G33 gate criteria: unchanged.
- G0-G38 other gate criteria: unchanged.
- 1+6 agent roles/prompts: unchanged.
- No calibration project rerun was executed.
- No locked 02/03 calibration content was read.
- No Project 2/3 formal calibration was run.

## Test Evidence

Commands executed:

```bash
backend/.venv/bin/python -m pytest backend/tests/test_cer_authoring_runtime.py -q
backend/.venv/bin/python -m pytest backend/tests/test_calibration_delta_analyzer.py backend/tests/test_cer_cowork_supervisor.py -q
backend/.venv/bin/python -m compileall -q backend/packages/harness/deerflow/runtime/cer_authoring backend/tests/test_cer_authoring_runtime.py
```

Results:

- `34 passed`
- `12 passed`
- compileall completed without errors

## CCD Read-Only Validation Focus

CCD should verify:

1. If `equivalence_matrix` exists but G33 artifacts are missing, `run_device_equivalence_search()` backfills four-step and attachment rows.
2. `similar_device_attachment_index` has at least 10 baseline rows.
3. Every baseline attachment row contains `required_document`, `use_in_cer`, and `if_missing`.
4. Legacy rows using `required_content` are promoted to G33-compatible rows.
5. G33 criteria and agents were not modified.

