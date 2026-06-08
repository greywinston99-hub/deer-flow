# CER Review Frontend Integration Contract

**Version:** 1.0.0
**Date:** 2026-04-25
**Status:** API Contract Freeze — Backend E2E Verified

---

## 1. Overview

This document defines the exact integration contract between the DeerFlow CER Review Backend Engine and the Frontend UI. The backend provides a complete StateGraph DAG workflow with severity-based human-gate halts, NocoDB writeback/backflow, and resume-from-node capability.

The frontend must implement a **three-phase interaction model**:

1. **Start Phase** — Initiate a CER review run
2. **Poll/Status Phase** — Detect halt and surface findings to the human reviewer
3. **Resume Phase** — Submit human adjudication and continue the workflow

---

## 2. Base URL

All endpoints are prefixed under the Gateway API:

```
Base URL: http://localhost:8001/api/cer
```

When running through Nginx (production):

```
Base URL: http://localhost:2026/api/cer
```

---

## 3. Phase 1: Start a CER Review

### `POST /api/cer/start`

Trigger a new CER review workflow run. If `thread_id` already exists, returns the existing run (idempotent).

#### Request Body: `CERStartRequest`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `project_profile` | `string` | Yes | Absolute path to `project_profile.yaml` |
| `input_root` | `string | null` | No | Optional override for input document root |
| `thread_id` | `string | null` | No | Optional thread ID (auto-generated if omitted) |
| `mode` | `string` | No | Default: `"smoke-run"`. Options: `smoke-run`, `closure-only` |

#### Example Request (cURL)

```bash
curl -X POST http://localhost:8001/api/cer/start \
  -H "Content-Type: application/json" \
  -d '{
    "project_profile": "/absolute/path/to/project_profile.yaml",
    "input_root": "/absolute/path/to/input/documents",
    "mode": "smoke-run"
  }'
```

#### Example Request (JavaScript fetch)

```javascript
const response = await fetch("http://localhost:8001/api/cer/start", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    project_profile: "/absolute/path/to/project_profile.yaml",
    input_root: "/absolute/path/to/input/documents",
    mode: "smoke-run",
  }),
});
const result = await response.json();
```

#### Response: `CERStartResponse`

| Field | Type | Description |
|-------|------|-------------|
| `thread_id` | `string` | Unique thread identifier for this review |
| `run_id` | `string` | Unique run identifier |
| `mode` | `string` | Run mode (`smoke-run`, `closure-only`, etc.) |
| `workflow_name` | `string` | Name of the workflow executed |
| `executed_steps` | `string[]` | List of step IDs executed so far |
| `artifact_root_virtual` | `string` | Virtual artifact path |
| `artifact_root_actual` | `string` | Absolute filesystem artifact path |
| `halt_state` | `object | null` | **Critical:** If not `null`, the workflow halted for human adjudication |

#### Example Response

```json
{
  "thread_id": "cer-smoke-run-a1b2c3d4",
  "run_id": "RUN-20260425-001",
  "mode": "smoke-run",
  "workflow_name": "cer_review_workflow_v1",
  "executed_steps": [
    "cer_intake",
    "cer_structure_compliance",
    "cer_intended_purpose",
    "cer_cep_methodology",
    "cer_clinical_evidence_panel",
    "cer_clinical_evidence_panel_halted_human_adjudication_pending"
  ],
  "artifact_root_virtual": "/mnt/user-data/outputs/cer_review_v0/RUN-20260425-001/artifacts",
  "artifact_root_actual": "/Users/.../.deer-flow/threads/cer-smoke-run-a1b2c3d4/user-data/outputs/cer_review_v0/RUN-20260425-001/artifacts",
  "halt_state": {
    "status": "human_adjudication_pending",
    "reason": "Severity threshold breached: high",
    "triggering_findings_count": 3,
    "triggering_findings": [
      {
        "source_artifact": "05_lanes/benefit_risk_report.json",
        "item": "R2_F-002: ALARP Prohibition",
        "severity": "high",
        "mismatch_description": "CER references ALARP (As Low As Reasonably Practicable), which is NOT acceptable under EU MDR/ISO 14971:2019. Must use binary criterion (acceptable/unacceptable)."
      }
    ],
    "halted_after_step": "cer_clinical_evidence_panel",
    "resume_from_node": "cer_ifu_sscp_label"
  }
}
```

---

## 4. Phase 2: Poll Status (Detect Halt)

### `GET /api/cer/status/{thread_id}`

Poll the latest run status for a given thread. The frontend should poll this endpoint every 2-3 seconds after starting a run.

#### Path Parameters

| Field | Type | Description |
|-------|------|-------------|
| `thread_id` | `string` | Thread ID returned from `POST /start` |

#### Example Request

```bash
curl http://localhost:8001/api/cer/status/cer-smoke-run-a1b2c3d4
```

#### Response: `CERStatusResponse`

| Field | Type | Description |
|-------|------|-------------|
| `thread_id` | `string` | Thread ID |
| `run_id` | `string | null` | Latest run ID |
| `mode` | `string | null` | Run mode |
| `workflow_name` | `string | null` | Workflow name |
| `executed_steps` | `string[]` | Steps executed in latest run |
| `artifact_root_actual` | `string | null` | Absolute artifact path |
| `has_review_package` | `bool` | Whether review package artifact exists |
| `has_gate_closure_report` | `bool` | Whether gate closure report exists |
| `has_human_decision` | `bool` | Whether a human decision has been recorded |
| `has_human_review_queue` | `bool` | Whether human review queue exists |
| `has_provisional_gate` | `bool` | Whether provisional gate recommendation exists |
| `final_recommended_gate` | `string | null` | Machine-recommended gate status |
| `provisional_gate` | `string | null` | Provisional gate status |
| `human_gate_required` | `bool` | Whether human gate is required |
| `human_decision_value` | `string | null` | Recorded human decision (`pass`, `conditional_pass`, `rework_required`) |
| `human_decision_reviewer` | `string | null` | Name/ID of reviewer |
| `final_gate_status` | `string | null` | Final gate status from closure report |
| `closure_completed` | `bool` | Whether gate closure is complete |
| **Human Adjudication Halt Fields** |
| `human_adjudication_pending` | `bool` | **True if workflow is halted awaiting human decision** |
| `human_adjudication_halt_reason` | `string | null` | Reason for halt (e.g., "Severity threshold breached: high") |
| `human_adjudication_triggering_findings_count` | `int | null` | Number of findings that triggered the halt |
| `halted_node` | `string | null` | Step ID where halt occurred |
| `resume_from_node` | `string | null` | **Step ID to resume from** (pass this to `POST /resume`) |

#### Interpreting `human_adjudication_pending`

```javascript
if (status.human_adjudication_pending) {
  // Workflow is halted. Surface findings to the reviewer.
  // Show: status.human_adjudication_halt_reason
  // Show: status.human_adjudication_triggering_findings_count findings
  // The reviewer must make a decision, then call POST /resume
  // with status.resume_from_node implicitly handled by backend
}
```

#### Example Response (Halted State)

```json
{
  "thread_id": "cer-smoke-run-a1b2c3d4",
  "run_id": "RUN-20260425-001",
  "mode": "smoke-run",
  "workflow_name": "cer_review_workflow_v1",
  "executed_steps": [
    "cer_intake",
    "cer_structure_compliance",
    "cer_intended_purpose",
    "cer_cep_methodology",
    "cer_clinical_evidence_panel",
    "cer_clinical_evidence_panel_halted_human_adjudication_pending"
  ],
  "artifact_root_actual": "/Users/.../artifacts",
  "has_review_package": false,
  "has_gate_closure_report": false,
  "has_human_decision": false,
  "has_human_review_queue": true,
  "has_provisional_gate": true,
  "human_gate_required": true,
  "provisional_only": true,
  "human_adjudication_pending": true,
  "human_adjudication_halt_reason": "Severity threshold breached: high",
  "human_adjudication_triggering_findings_count": 3,
  "halted_node": "cer_clinical_evidence_panel",
  "resume_from_node": "cer_ifu_sscp_label",
  "closure_completed": false
}
```

#### Example Response (Completed State)

```json
{
  "thread_id": "cer-smoke-run-a1b2c3d4",
  "run_id": "RUN-20260425-001",
  "mode": "smoke-run",
  "executed_steps": [
    "cer_intake",
    "cer_structure_compliance",
    "cer_intended_purpose",
    "cer_cep_methodology",
    "cer_clinical_evidence_panel",
    "cer_ifu_sscp_label",
    "cer_qa_gate",
    "cer_cear_style_finding_formatter",
    "cer_human_boundary",
    "cer_gate_closure"
  ],
  "has_gate_closure_report": true,
  "has_human_decision": true,
  "human_decision_value": "conditional_pass",
  "final_gate_status": "conditional_pass",
  "closure_completed": true,
  "human_adjudication_pending": false,
  "resume_from_node": null
}
```

---

## 5. Phase 3: Resume After Human Adjudication

### `POST /api/cer/resume`

Submit a human adjudication decision and resume the workflow from the halt checkpoint.

**Important:** The backend reads `resume_from_node` automatically from the halt artifact. The frontend does **not** need to pass it.

#### Request Body: `ResumeRequest`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `thread_id` | `string` | Yes | Thread ID of the halted run |
| `decision` | `string` | Yes | `approved` \| `conditional_approval` \| `rework_required` |
| `reviewer` | `string` | Yes | Reviewer name or ID |
| `rationale` | `string` | No | Decision rationale / notes |

#### Example Request (cURL)

```bash
curl -X POST http://localhost:8001/api/cer/resume \
  -H "Content-Type: application/json" \
  -d '{
    "thread_id": "cer-smoke-run-a1b2c3d4",
    "decision": "approved",
    "reviewer": "Dr. Smith",
    "rationale": "ALARP issue acknowledged; manufacturer will update B-R analysis."
  }'
```

#### Example Request (JavaScript fetch)

```javascript
const response = await fetch("http://localhost:8001/api/cer/resume", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    thread_id: "cer-smoke-run-a1b2c3d4",
    decision: "approved",
    reviewer: "Dr. Smith",
    rationale: "ALARP issue acknowledged; manufacturer will update B-R analysis.",
  }),
});
const result = await response.json();
```

#### Response: `ResumeResponse`

| Field | Type | Description |
|-------|------|-------------|
| `success` | `bool` | Whether resume succeeded |
| `decision_recorded` | `bool` | Whether a new decision was written |
| `resumed` | `bool` | Whether the workflow was resumed |
| `thread_id` | `string` | Thread ID |
| `run_id` | `string` | Run ID |
| `executed_steps` | `string[]` | Steps executed during the resume run |
| `artifact_root_actual` | `string` | Absolute artifact path |
| `halt_state` | `object | null` | If not `null`, a NEW halt occurred during resume |

#### Example Response

```json
{
  "success": true,
  "decision_recorded": true,
  "resumed": true,
  "thread_id": "cer-smoke-run-a1b2c3d4",
  "run_id": "RUN-20260425-001",
  "executed_steps": [
    "cer_ifu_sscp_label",
    "cer_qa_gate",
    "cer_cear_style_finding_formatter",
    "cer_human_boundary",
    "cer_gate_closure"
  ],
  "artifact_root_actual": "/Users/.../artifacts",
  "halt_state": null
}
```

**Note:** `halt_state: null` means the workflow completed through `cer_gate_closure` without further halts. If `halt_state` is not null, another human adjudication is required.

---

## 6. Complete Frontend Flow: Halt -> Human Approve -> Resume

This is the golden-path interaction loop the frontend must implement:

```javascript
// Step 1: Start the review
const startRes = await fetch("/api/cer/start", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    project_profile: "/path/to/project_profile.yaml",
    mode: "smoke-run",
  }),
});
const { thread_id } = await startRes.json();

// Step 2: Poll status until halt or completion
let status;
while (true) {
  const statusRes = await fetch(`/api/cer/status/${thread_id}`);
  status = await statusRes.json();

  if (status.closure_completed) {
    console.log("Review complete! Final gate:", status.final_gate_status);
    break;
  }

  if (status.human_adjudication_pending) {
    console.log("Workflow halted:", status.human_adjudication_halt_reason);
    console.log("Findings count:", status.human_adjudication_triggering_findings_count);
    // Surface findings to reviewer UI here
    break; // Exit polling loop; wait for human action
  }

  await new Promise(r => setTimeout(r, 3000)); // Poll every 3s
}

// Step 3: Human makes decision → call resume
if (status.human_adjudication_pending) {
  const resumeRes = await fetch("/api/cer/resume", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      thread_id,
      decision: "approved", // or "conditional_approval" / "rework_required"
      reviewer: "Dr. Smith",
      rationale: "Findings reviewed and accepted with conditions.",
    }),
  });
  const resumeResult = await resumeRes.json();

  if (resumeResult.halt_state === null) {
    console.log("Review completed through gate closure!");
  } else {
    console.log("Another halt occurred:", resumeResult.halt_state.reason);
    // Loop back to human adjudication UI
  }
}
```

---

## 7. Supporting Endpoints

### `GET /api/cer/runs`
List all CER thread summaries (for dashboard/overview page).

### `GET /api/cer/runs/{thread_id}`
List all runs for a specific thread.

### `GET /api/cer/run/{thread_id}/{run_id}`
Get rich detail for a specific run (all artifacts, findings, metadata).

### `GET /api/cer/artifacts/{thread_id}`
List artifact summaries with download URLs for a thread.

### `POST /api/cer/human-decision`
**Legacy endpoint** — used for `closure-only` mode after a full smoke-run. Prefer `POST /api/cer/resume` for halt-and-resume flows.

### `POST /api/cer/rework`
Trigger a new smoke-run for a thread marked `rework_required`.

---

## 8. Artifact Directory Layout (for Frontend Reference)

After a run, artifacts are organized under `artifact_root_actual`:

```
artifact_root/
  00_manifest/
    run_manifest.json
    input_inventory.json
    human_adjudication_halt.json   # <-- Created when halt occurs
    resume_signal.json             # <-- Created when resume occurs
  01_docstruct/
  02_structure_compliance/
  03_intended_purpose/
  04_cep_methodology/
  05_lanes/
    benefit_risk_report.json
    equivalence_report.json
    ...
  06_consistency/
  07_qa_gate/
  08_cear_format/
  09_human_boundary/
    human_gate_decision.json
    human_review_queue.json
    provisional_gate_recommendation.json
  10_gate_closure/
    review_package.json
    nocodb_writeback.json
    backflow_writeback.json
```

---

## 9. Decision Matrix for Frontend

| `human_adjudication_pending` | `closure_completed` | Frontend Action |
|------------------------------|---------------------|-----------------|
| `true` | `false` | Show human adjudication UI with findings. Enable "Approve / Conditional / Rework" buttons. Call `POST /resume` on decision. |
| `false` | `false` | Workflow is running. Continue polling `GET /status`. |
| `false` | `true` | Workflow complete. Show final gate status and closure report. |

---

## 10. Error Handling

| HTTP Status | Meaning | Frontend Action |
|-------------|---------|-----------------|
| `200` | Success | Proceed normally |
| `404` | Thread/run not found | Check `thread_id` / `run_id` |
| `400` | Bad request (missing project_profile, etc.) | Validate payload |
| `500` | Server error | Show generic error; retry with backoff |

---

## 11. Changelog

| Date | Version | Change |
|------|---------|--------|
| 2026-04-25 | 1.0.0 | Initial contract freeze. Includes `/start`, `/status`, `/resume` with severity-based halt and resume-from-node. |
