# MODEL RESOLUTION TRACE REQUIREMENT

> CCD | 2026-05-15

## Per-Run Requirement

Every DeerFlow strict-v7 run in the A/B matrix must output `MODEL_RESOLUTION_TRACE.json` in the artifact directory. This file proves per-agent routing was active and which model each agent resolved to.

## Trace Schema

```json
{
  "run_id": "AB-1",
  "project": "PILOT_02_MIDOS",
  "timestamp": "...",
  "global_model_env": "deepseek-v4-pro",
  "per_agent_overrides": {
    "CER_AUTHORING_MODEL_CER_WRITER": "deepseek-v4-pro",
    "CER_AUTHORING_MODEL_QA_REVIEW": "kimi-k2.6-code"
  },
  "agents": [
    {
      "agent_name": "cer-writer",
      "task_type": "cer_writer",
      "expected_model": "deepseek-v4-pro",
      "actual_resolved_model": "deepseek-v4-pro",
      "route_source": "env_var",
      "fallback_used": false,
      "provider_status": "ok",
      "model_invocation_success": true
    },
    {
      "agent_name": "qa-review",
      "task_type": "qa_reviewer",
      "expected_model": "kimi-k2.6-code",
      "actual_resolved_model": "kimi-k2.6-code",
      "route_source": "routing_policy_v1",
      "fallback_used": false,
      "provider_status": "ok",
      "model_invocation_success": true
    }
  ]
}
```

## Validation Rules

**HARD FAIL** if:
- Any agent's `actual_resolved_model` ≠ `expected_model` without documented fallback reason
- Any agent shows `route_source: global_env` when per-agent override was configured
- `fallback_used: true` for Writer or QA without owner-approved fallback policy
- Trace file missing from artifact directory

**ACCEPTABLE** if:
- All agents resolve to expected model
- Route source correctly reflects override mechanism
- Provider status ok for all agents

## Preflight Check (AB-0)

Run AB-0 first with kimi-k2.6-code global. Verify MODEL_RESOLUTION_TRACE shows all 7 agents. If any agent is missing from trace → routing integration failure → STOP.

---

*CCD 签发：2026-05-15*
