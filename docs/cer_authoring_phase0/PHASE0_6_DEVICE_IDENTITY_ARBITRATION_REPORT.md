# Phase 0.6 Device Identity Arbitration Hardening Report

## Scope

Phase 0.6 fixes the device identity arbitration defect where weaker classifier/GSPR evidence could silently overwrite the deterministic `locked_domain_hint`.

No authoring model, baseline artifact, SOTA logic, evidence appraisal logic, writer contract, PMCF logic, alignment logic, or gate criteria were changed.

## Implemented

- Added the 8-rank Device Identity Evidence Hierarchy.
- Added deterministic-vs-classifier arbitration.
- Added `DEVICE_IDENTITY_CONFLICT` row-level reporting for lower-ranked conflicting evidence.
- Preserved the selected deterministic domain when `locked_domain_hint` is specific.
- Added `device_identity_arbitration` and `device_identity_arbitration_table` to the authoring state/workbook.
- Added Annex K output for the arbitration table.
- Added regression coverage for:
  - CAL-001 -> `cardiovascular_rf_ablation_catheter`
  - CAL-002 -> `ai_diagnostic_software`
  - CAL-003 -> `surgical_ligating_clip`

## Key Rule

`locked_domain_hint` is the strongest evidence source. LLM/text classifier evidence is the weakest source. If they disagree, the selected domain remains the locked domain and the lower-ranked row is marked `DEVICE_IDENTITY_CONFLICT`.

## Files Changed

- `backend/packages/harness/deerflow/runtime/cer_authoring/pipeline.py`
- `backend/packages/harness/deerflow/runtime/cer_authoring/state.py`
- `backend/packages/harness/deerflow/runtime/cer_authoring/artifacts.py`
- `backend/tests/test_cer_authoring_runtime.py`
- `docs/cer_authoring_phase0/DEVICE_IDENTITY_EVIDENCE_HIERARCHY_SPEC.md`
- `docs/cer_authoring_phase0/PHASE0_6_DEVICE_IDENTITY_ARBITRATION_REPORT.md`

## Verification

Executed:

```bash
backend/.venv/bin/python -m pytest backend/tests/test_cer_authoring_runtime.py -k "phase0_6 or phase0_4_cal001 or phase0_4_cal003 or phase0_5_cal002" -q
```

Result: `6 passed, 34 deselected`.

Executed:

```bash
backend/.venv/bin/python -m pytest backend/tests/test_cer_authoring_runtime.py -k "phase0_4 or phase0_5 or phase0_6" -q
```

Result: `12 passed, 28 deselected`.

Executed:

```bash
backend/.venv/bin/python -m pytest backend/tests/test_cer_authoring_runtime.py -q
```

Result: `40 passed`.

## CCD Decision

`PHASE0_6_READY_FOR_CCD_ACCEPTANCE`
