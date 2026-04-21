# RMF Review Orchestrator

**Date:** 2026-04-19
**Phase:** RMF_AGENT_TEAM_HARNESS_CONFIG_MOUNTING_PHASE_A
**Node:** rmf_review_orchestrator
**Runtime Type:** deterministic_orchestrator

---

## 1. Node Overview

The Orchestrator is the entry point and central coordinator for the RMF Review DAG. It is **deterministic** — it does not invoke LLMs directly but orchestrates the flow of data between nodes.

## 2. Responsibilities

1. **Project Initialization**
   - Validate incoming project has required documents (RMF, CER, IFU, FMEA as applicable)
   - Initialize shared state with project metadata
   - Set `project_id`, `project_type`, `institution`, `review_start_time`

2. **Document Ingestion**
   - Receive uploaded documents and classify by type
   - Route documents to DocStruct for parsing
   - Track document inventory in shared state

3. **Orchestration Flow**
   - Sequentially trigger DocStruct → L1 Rule Engine
   - Parallel trigger for dimension agents (COMP, CORR, ADEQ, TRAC, CONS, ACPT)
   - Route to QA Gate after dimension reviews
   - Handle PMS Lane conditional trigger
   - Produce Human Gate Packet
   - Trigger Findings Synthesis after human gate

4. **State Management**
   - Maintain `rmf_run_id` for this review cycle
   - Track `current_phase` (ingestion | review | gate | synthesis)
   - Aggregate findings from all dimension agents
   - Manage `human_gate_status` (pending | approved | rejected | deferred)

## 3. Inputs

| Input | Source | Description |
|---|---|---|
| `project_documents` | User upload / API | Dict of document_type → content |
| `project_metadata` | User / API | project_id, institution, project_type |
| `approved_knowledge_assets` | NocoDB (dry-run) | Loaded at orchestration start |

## 4. Outputs

| Output | Destination | Description |
|---|---|---|
| `orchestrator_output` | DocStruct | Structured document manifest |
| `review_scope` | All dimension agents | Defines which dimensions apply |
| `shared_state` | All nodes | Read/write access to shared state |

## 5. Shared State Schema

```json
{
  "rmf_run_id": "string",
  "project_id": "string",
  "project_type": "string",
  "institution": "string",
  "current_phase": "ingestion|review|gate|synthesis",
  "human_gate_status": "pending|approved|rejected|deferred",
  "dimension_results": {
    "COMP": {"status": "pending|complete|failed", "findings": []},
    "CORR": {"status": "pending|complete|failed", "findings": []},
    "ADEQ": {"status": "pending|complete|failed", "findings": []},
    "TRAC": {"status": "pending|complete|failed", "findings": []},
    "CONS": {"status": "pending|complete|failed", "findings": []},
    "ACPT": {"status": "pending|complete|failed", "findings": []}
  },
  "pms_triggered": false,
  "gate_packet": null,
  "findings_synthesis": null
}
```

## 6. Forbidden Actions

- **NO direct LLM invocation** — this node is purely deterministic
- **NO final compliance decisions** — all Layer 3 decisions go through Human Gate
- **NO bypass of QA Gate** — all dimension results must pass through QA

## 7. Handoff Protocol

After completing ingestion and initialization:
1. Set `current_phase = "ingestion"` → `"review"`
2. Emit `orchestrator_output` with document manifest
3. Trigger DocStruct with document references
4. Await DocStruct completion before proceeding to L1 Rule Engine
5. After L1 Rule Engine, parallel trigger all 6 dimension agents
6. Await all dimension agents, aggregate findings
7. Route to QA Gate for conflict detection
8. If PMS conditions met, trigger PMS Lane before QA Gate
9. Await QA Gate → generate Human Gate Packet
10. **STOP** at Human Gate (wait for human decision)
11. After human gate → trigger Findings Synthesis

## 8. Error Handling

| Error | Response |
|---|---|
| Missing required document | Set dimension to `failed`, continue with available docs |
| Dimension agent timeout | Mark as `failed`, aggregate partial findings |
| NocoDB knowledge load failure | Continue without knowledge assets (degraded mode) |

---

*Orchestrator is the heart of RMF Review DAG — all data flows through here*
