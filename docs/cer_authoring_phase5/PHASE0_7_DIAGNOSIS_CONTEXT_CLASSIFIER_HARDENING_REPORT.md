# Phase 0.7 Diagnosis Context Classifier Hardening Report

## Decision

`PHASE0_7_IMPLEMENTED_ACCEPTED / HOLD-002_IDENTITY_FIXED / NON_IDENTITY_G38_REWORK_REMAINS`

## Scope

Changed files:

- `backend/packages/harness/deerflow/runtime/cer_authoring/pipeline.py`
- `backend/tests/test_cer_authoring_runtime.py`

No changes were made to:

- authoring graph
- gates
- 1+6 agents
- prompts
- Phase 0.6 evidence hierarchy
- SOTA / evidence / writer / PMCF / alignment core logic

## Implemented Rule

The classifier no longer treats `diagnosis` / `diagnostic` alone as evidence for `ai_diagnostic_software`.

SaMD / AI diagnostic software classification now requires diagnostic wording to co-occur with software-specific evidence, such as:

- software
- algorithm
- model / AI model
- AI / artificial intelligence
- machine learning
- diagnostic output
- image analysis
- decision support

Physical counterevidence suppresses the SaMD path, including:

- needle / puncture needle / nerve block needle
- catheter
- clip
- implant
- sterile
- gauge
- disposable
- material

The classifier continues to respect Phase 0.6 hierarchy:

`locked_domain_hint` remains rank 1 and cannot be silently overridden by classifier output.

## Domain Addition

Added deterministic support for:

- `nerve_block_needle`
- `nerve block puncture needle`
- sterile disposable puncture needle family

This is necessary because HOLD-002 is a physical puncture needle project; suppressing SaMD alone would otherwise leave it as a generic/unknown device.

## Regression Tests

Added regressions for:

- diagnosis alone is not AI diagnostic software
- physical + diagnosis context suppresses SaMD
- HOLD-002 selects `nerve_block_needle`
- CAL-002 still selects `ai_diagnostic_software`
- CAL-001 remains `cardiovascular_rf_ablation_catheter`

Commands:

```bash
backend/.venv/bin/python -m py_compile backend/packages/harness/deerflow/runtime/cer_authoring/pipeline.py backend/tests/test_cer_authoring_runtime.py
backend/.venv/bin/python -m pytest backend/tests/test_cer_authoring_runtime.py -q -k "phase0_4 or phase0_5 or phase0_6 or phase0_7"
backend/.venv/bin/python -m pytest backend/tests/test_cer_authoring_runtime.py -q
```

Results:

```text
17 passed, 56 deselected
73 passed in 6.57s
```

## HOLD-002 Clean Rerun

Command:

```bash
backend/.venv/bin/python backend/scripts/run_cer_authoring.py \
  --project-id HOLD-002 \
  --input-root "/Users/winstonwei/CER-RAG/升级 CCD-3 个项目文件/PROJECT_05_CALIBRATION/01_INITIAL_INPUT_FOR_WRITER" \
  --artifact-root "/Users/winstonwei/Documents/Playground/deer-flow/artifacts/cer_cowork/HOLD-002/authoring/PHASE0_7_20260511_HOLD002/deerflow_authoring" \
  --target-keywords "Nerve Block Needle,Puncture Needle,Disposable,神经阻滞针,穿刺针,一次性" \
  --agent-team-mode stable-1plus6 \
  --json
```

Summary:

```json
{
  "status": "gate_rework_required",
  "final_gate_decision": "REWORK_REQUIRED",
  "failed_gate_count": 1,
  "source_count": 34,
  "claim_count": 11,
  "pico_count": 11,
  "evidence_count": 10,
  "risk_count": 8,
  "artifact_count": 80
}
```

Identity result:

```text
device_type = nerve block puncture needle
device_family = sterile disposable puncture needle
clinical_domain = nerve_block_needle
device_identity_lock.status = PASS
G1d = PASS
G1e = PASS
```

Remaining failure:

```text
G38 = REWORK_REQUIRED
CER uses superiority/absolute wording that is not allowed by the evidence-level guard.
```

Interpretation:

- The Phase 0.7 classifier issue is fixed.
- HOLD-002 no longer routes to `ai_diagnostic_software`.
- The remaining HOLD-002 rework is not an identity/classifier issue; it belongs to conclusion-strength/writer synthesis handling.
