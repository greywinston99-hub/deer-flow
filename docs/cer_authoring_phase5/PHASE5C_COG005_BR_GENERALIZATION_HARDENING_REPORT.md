# Phase 5C COG-005 BR Generalization Hardening Report

## Decision

`PHASE5C_COG005_BR_GUARD_IMPLEMENTED_ACCEPTED / OVERALL_80_GENERALIZATION_NOT_GRANTED`

## Scope

Changed files:

- `backend/packages/harness/deerflow/runtime/cer_authoring/pipeline.py`
- `backend/tests/test_cer_authoring_runtime.py`

No changes were made to:

- authoring graph
- gate criteria
- 1+6 agents
- prompts
- identity arbitration
- `BASELINE_V2.4` structural pipeline

## Rule Design Boundary

HOLD-002 was treated as a validation signal only. No HOLD-002 gold reference or final certified package content was used to design this rule.

The generalized BR conclusion guard is based on:

- CAL-001/CAL-002/CAL-003 calibration BR patterns.
- Device-class taxonomy.
- MDR Annex I GSPR 1 benefit-risk reasoning.

## Implemented Changes

### 1. Device-Class BR Taxonomy

The Benefit-Risk Ledger now classifies BR reasoning into:

- `samd_or_ai_diagnostic`
- `therapeutic_energy_catheter_or_system`
- `implantable_or_surgically_implanted_device`
- `disposable_physical_device`
- `generic_medical_device`

### 2. Enhanced BR Ledger Fields

Added BR fields:

- `device_class_taxonomy`
- `device_class_br_policy`
- `regulatory_reasoning_basis`
- `calibration_generalization_basis`
- `conclusion_guard_result`
- `conclusion_guard_instruction`

### 3. Writer Conclusion Guard Generalization

`writer_conclusion_strength_guard` now includes device-class policy and MDR GSPR reasoning so section 4.7 / chapter 5 wording is constrained by:

- magnitude of benefit
- severity of risk
- evidence strength
- residual uncertainty
- device class
- alignment status

### 4. G38 Hygiene at Writer Output Layer

The CER markdown sanitizer is now case-insensitive and table headers are sanitized. This prevents non-conclusion occurrences such as article titles containing `Superior` or table headers such as `superiority_claim_allowed` from falsely triggering G38.

## Test Results

Commands:

```bash
backend/.venv/bin/python -m py_compile backend/packages/harness/deerflow/runtime/cer_authoring/pipeline.py backend/tests/test_cer_authoring_runtime.py
backend/.venv/bin/python -m pytest backend/tests/test_cer_authoring_runtime.py -q -k "phase5c or phase5_2 or phase2_3"
backend/.venv/bin/python -m pytest backend/tests/test_cer_authoring_runtime.py -q
```

Results:

```text
9 passed, 67 deselected
76 passed in 6.80s
```

## Targeted Regression Runs

### CAL-001

Artifact:

`artifacts/cer_cowork/CAL-001/authoring/PHASE5C_20260511_CAL001/deerflow_authoring`

Result:

```text
final_gate_decision = PASS_TO_DRAFT_DOCX
failed_gate_count = 0
G38 = PASS
```

### CAL-002

Artifact:

`artifacts/cer_cowork/CAL-002/authoring/PHASE5C_20260511_CAL002/deerflow_authoring`

Result:

```text
final_gate_decision = PASS_TO_DRAFT_DOCX
failed_gate_count = 0
G38 = PASS
```

### CAL-003

Artifact:

`artifacts/cer_cowork/CAL-003/authoring/PHASE5C_20260511_CAL003/deerflow_authoring`

Result:

```text
final_gate_decision = REWORK_REQUIRED
failed_gate_count = 1
G38 = PASS
remaining failure = G1e domain contamination for ureteroscope context
```

Interpretation:

- The COG-005 BR/G38 issue is fixed for CAL-003.
- CAL-003 still has a non-BR identity/domain contamination issue, outside Phase 5C scope.

## Holdout Reruns

### HOLD-002

Artifact:

`artifacts/cer_cowork/HOLD-002/authoring/PHASE5C_20260511_HOLD002/deerflow_authoring`

Result:

```text
final_gate_decision = PASS_TO_DRAFT_DOCX
failed_gate_count = 0
G38 = PASS
```

### HOLD-001

Artifact:

`artifacts/cer_cowork/HOLD-001/authoring/PHASE5C_20260511_HOLD001/deerflow_authoring`

Result:

```text
final_gate_decision = REWORK_REQUIRED
failed_gate_count = 1
G38 = PASS
remaining failure = G22 human CER comparison / section coverage
```

## Generalization Judgment

BR conclusion guard generalization:

`PASS`

Reason:

- CAL-001/CAL-002/CAL-003 all show G38 PASS after the patch.
- HOLD-001/HOLD-002 both show G38 PASS.
- HOLD-002 no longer fails the BR conclusion-strength guard.

Overall 80-level generalization judgment:

`NOT GRANTED`

Reason:

- 2/2 holdout requirement is not met at the whole-workflow level.
- HOLD-002 passed all gates.
- HOLD-001 still fails G22 due to human-style/section coverage gaps.

Next issue is not COG-005. It is a template/human-section coverage generalization issue surfaced by HOLD-001.
