# Phase 0.3 Intake Blocker Repair Report

Date: 2026-05-09

## Executive Summary

Phase 0.3 repairs the CAL-003 intake blocker by strengthening source intake and
IFU detection only. The patch does not modify SOTA, Evidence, Writer,
Benefit-Risk, PMCF, Alignment, or G0-G38 gate criteria.

## Blocker

CAL-003 baseline authoring reached `HUMAN_HOLD` because the subject IFU was not
locked:

```text
01_IFU/TF-TLC-0301_IFU-Ligating clips(Ti).docx
```

Observed failure chain:

```text
IFU not recognized / not promoted
-> subject_ifu_source_ids=[]
-> device_profile={}
-> claims/PICO/SOTA/evidence/risk = 0
-> HUMAN_HOLD
```

## Scope of Repair

Only source intake / IFU detection was changed:

- strengthened IFU filename recognition;
- added IFU folder-name heuristic for `01_IFU/` and `IFU/`;
- added locked delta-only path exclusion for `03_FINAL_CERTIFIED_PACKAGE_LOCKED`;
- added IFU candidate ranking in `source_role_report`;
- ensured strong IFU filename/path signal can promote an otherwise
  `unconfirmed_ifu` candidate to `subject_device_ifu` when it is outside
  similar/locked folders.

## Changed Files

- `backend/packages/harness/deerflow/runtime/cer_authoring/pipeline.py`
- `scripts/cer_cowork_supervisor.py`
- `backend/tests/test_cer_authoring_runtime.py`
- `backend/tests/test_cer_cowork_supervisor.py`
- `docs/cer_authoring_phase0/PHASE0_3_INTAKE_BLOCKER_REPAIR_REPORT.md`

## Before / After Example

Before:

```json
{
  "filename": "TF-TLC-0301_IFU-Ligating clips(Ti).docx",
  "document_type": "not locked as IFU candidate",
  "source_role": "not subject_device_ifu",
  "subject_ifu_source_ids": []
}
```

After, using the CAL-003 fixture path:

```json
{
  "filename": "TF-TLC-0301_IFU-Ligating clips(Ti).docx",
  "document_type": "IFU",
  "source_role": "subject_device_ifu",
  "primary_for_authoring": true,
  "excluded_from_device_profile": false,
  "subject_ifu_source_ids": ["SRC-001"],
  "ifu_candidate_score": 12,
  "role_reason": "IFU outside similar/locked folders with subject/domain score 0; strong_ifu_signal=True."
}
```

## Regression Coverage

Added regression checks for:

- `TF-TLC-0301_IFU-Ligating clips(Ti).docx`;
- lowercase / uppercase / mixed-case IFU filenames;
- Chinese `使用说明书` and `说明书`;
- reasonable documents located under `01_IFU/`;
- locked final IFU under `03_FINAL_CERTIFIED_PACKAGE_LOCKED` not entering writer
  source intake;
- supervisor preflight `infer_doc_type()` matching the same IFU/locked rules.

## Verification

Commands run:

```bash
backend/.venv/bin/python -m pytest backend/tests/test_cer_authoring_runtime.py backend/tests/test_cer_cowork_supervisor.py -q
backend/.venv/bin/python -m compileall -q backend/packages/harness/deerflow/runtime/cer_authoring/pipeline.py scripts/cer_cowork_supervisor.py
```

Observed result:

```text
29 passed
compileall passed
```

## Boundaries Preserved

This patch did not:

- modify SOTA logic;
- modify Evidence Appraisal logic;
- modify Writer behavior;
- modify Benefit-Risk logic;
- modify PMCF rules;
- modify Alignment rules;
- modify G0-G38 gate criteria;
- run Project 2/3 formal calibration;
- consume holdout;
- read or process real locked `02_/03_` project content.

## Conclusion

`PHASE0_3_INTAKE_BLOCKER_REPAIR_READY_FOR_CCD_ACCEPTANCE`

CAL-003 or affected projects should only be rerun after CCD accepts this intake
blocker repair.
