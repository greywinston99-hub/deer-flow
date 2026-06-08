# Cross-Run State Isolation Regression Report

## Decision

`RUN_ISOLATION_HARDENING_IMPLEMENTED_ACCEPTED / HOLD-002_GENERALIZATION_BLOCKED_BY_IDENTITY_CLASSIFIER`

This patch implements true run-scoped state isolation for `cer_authoring_v1` at the active graph entrypoint and at the subagent prompt boundary. The requested `RUN_SCOPED_STATE_BOUNDARY_SPEC.md` was not present in the repository, so the implementation follows the explicit run-isolation requirements in the task card.

## Scope

Changed files:

- `backend/packages/harness/deerflow/runtime/cer_authoring/agent_runtime.py`
- `backend/packages/harness/deerflow/runtime/cer_authoring/graph.py`
- `backend/packages/harness/deerflow/runtime/cer_authoring/state.py`
- `backend/packages/harness/deerflow/runtime/cer_authoring/artifacts.py`
- `backend/tests/test_cer_authoring_runtime.py`

No changes were made to:

- CER authoring gate criteria.
- 1+6 agent responsibilities or prompts.
- Device identity arbitration rules.
- SOTA, evidence, writer, PMCF, alignment, or benefit-risk logic.

## Implementation Summary

### 1. Initialize Boundary

`_node_initialize()` now calls `isolate_initial_authoring_state()` before source intake. This prevents any previously generated state from entering `prepare_source_inventory()` or the Lead Agent invocation when runs are executed sequentially in the same thread/checkpoint context.

Allowed run input fields remain available, including:

- `project_id`
- `input_root`
- `supplement_roots`
- `uploaded_files`
- `target_keywords`
- `artifact_root`
- `agent_team_mode`
- model/thread/sandbox metadata

### 2. Prompt Boundary

`invoke_authoring_agent()` now sanitizes the state summary before sending it to any authoring subagent. Rows with explicit foreign `project_id`, `run_project_id`, or paths outside the active run roots are removed from the prompt summary and logged in `run_scope_audit`.

### 3. Eight State Categories Audited

The audit covers all requested run-scoped categories:

1. `source_intake_identity`
2. `claims_pico_methodology`
3. `search_sota_evidence`
4. `equivalence_vigilance_risk_gspr`
5. `writer_synthesis_report`
6. `qa_review_gate`
7. `artifact_mcp_template`
8. `calibration_baseline_delta`

### 4. Audit Persistence

`run_scope_audit` is now part of `SharedAuthoringState` and is included in `authoring_workbook.json` for downstream inspection.

## Regression Coverage

Added state-boundary regressions:

- `CAL-002 -> HOLD-002`
- `HOLD-002 standalone`
- `HOLD-002 -> CAL-002`
- Full smoke sequence: `CAL-001 -> CAL-002 -> CAL-003 -> HOLD-001 -> HOLD-002`
- HOLD-001 run-scope audit verifying prior surgical ligating identity does not survive into the HOLD-001 run state.

These regressions verify that generated state from a previous run is dropped before source intake, rather than only clearing `device_profile`.

## HOLD-001 Run-Scope Audit

The HOLD-001 regression simulates prior CAL-003 surgical-ligating identity state and then starts a HOLD-001 run. The clean run state retains only HOLD-001 input/configuration fields and drops:

- prior `device_profile`
- prior `device_identity_lock`
- prior identity-domain markers

Result: no prior surgical-ligating identity is available to source intake or subagent prompts.

## Test Results

Commands run:

```bash
backend/.venv/bin/python -m py_compile backend/packages/harness/deerflow/runtime/cer_authoring/agent_runtime.py backend/packages/harness/deerflow/runtime/cer_authoring/graph.py backend/packages/harness/deerflow/runtime/cer_authoring/state.py backend/packages/harness/deerflow/runtime/cer_authoring/artifacts.py
backend/.venv/bin/python -m pytest backend/tests/test_cer_authoring_runtime.py -q
```

Result:

```text
68 passed in 7.73s
```

## HOLD-002 Clean Rerun Status

The code-level run isolation fix is complete. A clean HOLD-002 authoring rerun was executed after the fix:

```bash
backend/.venv/bin/python backend/scripts/run_cer_authoring.py \
  --project-id HOLD-002 \
  --input-root "/Users/winstonwei/CER-RAG/升级 CCD-3 个项目文件/PROJECT_05_CALIBRATION/01_INITIAL_INPUT_FOR_WRITER" \
  --artifact-root "/Users/winstonwei/Documents/Playground/deer-flow/artifacts/cer_cowork/HOLD-002/authoring/RUN_ISOLATION_20260511_HOLD002/deerflow_authoring" \
  --target-keywords "Nerve Block Needle,Puncture Needle,Disposable,神经阻滞针,穿刺针,一次性" \
  --agent-team-mode stable-1plus6 \
  --json
```

Summary:

```json
{
  "project_id": "HOLD-002",
  "status": "gate_passed",
  "final_gate_decision": "PASS_TO_DRAFT_DOCX",
  "failed_gate_count": 0,
  "source_count": 34,
  "claim_count": 11,
  "pico_count": 11,
  "evidence_count": 10,
  "risk_count": 8,
  "artifact_count": 80
}
```

Run-scope audit result:

```text
8 categories audited; dropped_key_count=0 and dropped_row_count=0 for all categories.
```

Interpretation:

- This clean rerun proves the new run did not inherit generated state from a previous project.
- However, HOLD-002 still misclassified the Disposable Nerve Block Puncture Needle as `ai_diagnostic_software` based on an incidental IFU phrase containing "clinical diagnosis".
- Therefore the requested 80-level generalization judgment is **not granted** from this run. The blocker is no longer cross-run state leakage; it is device identity classification/arbitration for incidental diagnostic wording in non-software device IFUs.

Next required investigation:

- Treat HOLD-002 as an identity classifier/arbitration defect, not a run-isolation defect.
- Add a future identity rule that "diagnosis" inside generic clinical-use prose must not classify a physical puncture needle as SaMD unless software/algorithm/model/diagnostic-output evidence is also present.
