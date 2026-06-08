# RESUME COMMAND — DeerFlow Model A/B Execution

## Current Status: MODEL_AB_RUNTIME_BLOCKED_ACCESS

## What's Complete

- Model routing config: VERIFIED (7/7 agents resolve correctly)
- Trace infrastructure: IMPLEMENTED (record + write in agent_runtime.py + artifacts.py)
- A/B config package: READY (6-run matrix with exact commands)
- Scoring templates: READY
- 323 tests: PASS
- graph/gates/agents: ZERO DIFF

## What Needs DeerFlow Runtime

6 A/B runs requiring LLM provider access:

```bash
cd /Users/winstonwei/Documents/Playground/deer-flow
CER_AUTHORING_STRICT_V7=1 CER_AUTHORING_ENABLE_LLM_AGENTS=1

# AB-0: Preflight
CER_AUTHORING_MODEL_NAME=kimi-k2.6-code \
backend/.venv/bin/python backend/scripts/run_cer_authoring.py \
  --project-id PILOT_02_MIDOS_AB_0 \
  --input-root "/Users/winstonwei/CER-RAG/升级 CCD-3 个项目文件/CER_PILOT_STANDARD_02米道斯/01_AUTHORING_INPUT_ALLOWED" \
  --artifact-root ".../ab_run_0/" --strict-v7 --agent-team-mode stable-1plus6

# AB-1: Writer deepseek
CER_AUTHORING_MODEL_CER_WRITER=deepseek-v4-pro \
CER_AUTHORING_MODEL_METHODOLOGY_SOTA=deepseek-v4-pro \
CER_AUTHORING_MODEL_EVIDENCE=deepseek-v4-pro \
[.../ab_run_1/]

# AB-2: Writer kimi-api [.../ab_run_2/]
# AB-3: Writer baseline kimi-k2.6-code [.../ab_run_3/]
# AB-4: QA deepseek (best writer) [.../ab_run_4/]
# AB-5: QA kimi-api (best writer) [.../ab_run_5/]
```

## After Execution

1. Verify MODEL_RESOLUTION_TRACE.json in each ab_run_N/ directory
2. Fill scoring tables in WRITER_MODEL_AB_RESULT.md and QA_MODEL_AB_RESULT.md
3. Fill MODEL_AB_SCORING_TABLE.md
4. Present MODEL_SELECTION_RECOMMENDATION_FOR_OWNER.md to owner
5. Owner signs MODEL_AB_OWNER_DECISION_TEMPLATE.md
6. Update model_routing.py ROUTING_POLICY_V1 with owner-approved models

## Key Files

- `DEERFLOW_OPERATOR_AB_COMMANDS.md` — Step-by-step commands
- `WRITER_MODEL_AB_RESULT.md` — Writer scoring template
- `QA_MODEL_AB_RESULT.md` — QA scoring template
- `MODEL_AB_SCORING_TABLE.md` — Consolidated scoring
- `MODEL_SELECTION_RECOMMENDATION_FOR_OWNER.md` — Owner decision document
