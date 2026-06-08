# MODEL ROUTING CLOSEOUT — Phase 3A

> Claude Code | 2026-05-15

## Final Status: `MODEL_ROUTING_IMPLEMENTED_READY_FOR_AB`

## What was implemented

### 1. Config-Driven Per-Agent Model Routing

New module: `writer_remediation/model_routing.py`
- `ROUTING_POLICY_V1`: centralized per-agent routing table (7 agents, 4 models)
- `resolve_agent_model()`: 5-level priority resolution (env var > state config > policy > global env > default)
- `is_model_allowed_for_agent()`: boundary enforcement
- `MODEL_BOUNDARIES`: 4-model usage boundary definitions
- `build_ab_test_config()`: A/B test configuration generator
- `_validate_model_allowed()`: runtime enforcement

### 2. agent_runtime.py Integration

- After `build_authoring_subagent_configs()`, applies per-agent model override via config.model assignment
- Forbidden model check blocks agent invocation with BLOCKED status
- Routing source tracked in payload (env_var / state_config / routing_policy_v1)
- agents.py UNCHANGED

### 3. Routing Table

| Agent | Task Type | Default Model |
|-------|-----------|---------------|
| intake-profile-claim | Extraction | kimi-k2.6-code |
| methodology-sota | Evidence Reasoning | deepseek-v4-pro |
| evidence | Evidence Reasoning | deepseek-v4-pro |
| cer-writer | CER Writer | deepseek-v4-pro |
| qa-review | QA Reviewer | deepseek-v4-pro |
| risk-equivalence-gspr | Risk/Equivalence | kimi-k2.6-code |
| cer-authoring-lead-agent | Controller | kimi-k2.6-code |

### 4. Model Boundaries Enforced

- kimi-k2.6-code: FORBIDDEN for Writer, QA, Evidence Reasoning
- minimax-M2.7-highspeed: FORBIDDEN for Writer, QA, Evidence Reasoning, Risk, Extraction (bulk pre-screen only)
- deepseek-v4-pro: ALLOWED for all
- kimi-api: ALLOWED for all (A/B candidate)

## Test Results

- 323 tests PASS (298 original + 25 model routing)
- graph.py / gates.py / agents.py: zero diff

## Deliverables

1. MODEL_ROUTING_IMPLEMENTATION_MAP.md — per-agent resolution map
2. MODEL_ROUTING_POLICY_V1.md — routing policy with change procedure
3. MODEL_PROVIDER_CONFIG_NOTES.md — provider config + env var reference
4. WRITER_MODEL_AB_RUNNER_OR_PLAN.md — A/B config + scoring + execution procedure
5. QA_MODEL_AB_RUNNER_OR_PLAN.md — A/B config + scoring + deterministic gate note
6. MODEL_ROUTING_TEST_REPORT.md — 25 targeted tests report
7. MODEL_ROUTING_CLOSEOUT.md — this file

## A/B Status

- Writer A/B: **READY** — config skeleton + runner plan complete. Execution requires DeerFlow runtime.
- QA A/B: **READY** — config skeleton + runner plan complete. Note: deterministic gates provide core enforcement regardless of QA model.

## Next Steps

1. Owner reviews routing policy (MODEL_ROUTING_POLICY_V1.md)
2. A/B tests executed in DeerFlow runtime environment
3. Owner approves final Writer/QA model selection
4. Update ROUTING_POLICY_V1 default_model entries with A/B results
5. Regenerate pilot CERs under selected models
