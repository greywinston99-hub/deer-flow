# DEERFLOW OPERATOR A/B COMMANDS

> CCD | 2026-05-15

## Prerequisites

- DeerFlow runtime environment with LLM access
- 323 tests passing
- Model routing module (`model_routing.py`) deployed
- PROMPT_PACK_V1 accessible

## Step 0: Verify Routing Integration

Confirm per-agent model override is active in agent_runtime.py. Check that `CER_AUTHORING_MODEL_<AGENT>` env vars are respected.

## Step 1: AB-0 — Resolution Preflight

Run with global kimi-k2.6-code to verify all agents resolve and MODEL_RESOLUTION_TRACE generates correctly.

```bash
cd /Users/winstonwei/Documents/Playground/deer-flow

CER_AUTHORING_MODEL_NAME=kimi-k2.6-code \
backend/.venv/bin/python backend/scripts/run_cer_authoring.py \
  --project-id PILOT_02_MIDOS_AB_0 \
  --input-root "/Users/winstonwei/CER-RAG/升级 CCD-3 个项目文件/CER_PILOT_STANDARD_02米道斯/01_AUTHORING_INPUT_ALLOWED" \
  --artifact-root "/Users/winstonwei/CER-RAG/升级 CCD-3 个项目文件/CER_PILOT_STANDARD_02米道斯/02_AI_BASELINE_OUTPUT_FREEZE/ab_run_0/" \
  --strict-v7 --agent-team-mode stable-1plus6
```

Check: MODEL_RESOLUTION_TRACE.json exists with all 7 agents. Each agent's route_source recorded. No fallback_used: true unexpected.

## Step 2-4: Writer A/B — AB-1, AB-2, AB-3

Three Writer model runs. Only Writer model changes between runs. QA kept on baseline. Extraction and reasoning kept on recommended models.

**AB-1 — Writer deepseek-v4-pro:**
```bash
CER_AUTHORING_MODEL_CER_WRITER=deepseek-v4-pro \
CER_AUTHORING_MODEL_METHODOLOGY_SOTA=deepseek-v4-pro \
CER_AUTHORING_MODEL_EVIDENCE=deepseek-v4-pro \
backend/.venv/bin/python backend/scripts/run_cer_authoring.py \
  --project-id PILOT_02_MIDOS_AB_1 \
  --input-root ".../01_AUTHORING_INPUT_ALLOWED" \
  --artifact-root ".../02_AI_BASELINE_OUTPUT_FREEZE/ab_run_1/" \
  --strict-v7 --agent-team-mode stable-1plus6
```

**AB-2 — Writer kimi API:**
```bash
CER_AUTHORING_MODEL_CER_WRITER=kimi-api \
[rest same as AB-1]
```

**AB-3 — Writer baseline (kimi-k2.6-code):**
```bash
CER_AUTHORING_MODEL_CER_WRITER=kimi-k2.6-code \
[rest same as AB-1]
```

## Step 5-6: QA A/B — AB-4, AB-5

Use best Writer model from AB-1/2/3. Only QA model changes.

**AB-4 — QA deepseek-v4-pro:**
```bash
CER_AUTHORING_MODEL_CER_WRITER=<best_writer> \
CER_AUTHORING_MODEL_QA_REVIEW=deepseek-v4-pro \
[rest same]
```

**AB-5 — QA kimi API:**
```bash
CER_AUTHORING_MODEL_CER_WRITER=<best_writer> \
CER_AUTHORING_MODEL_QA_REVIEW=kimi-api \
[rest same]
```

## After All Runs

Collect MODEL_RESOLUTION_TRACE from each run. Score Writer and QA outputs per DEERFLOW_MODEL_AB_PROJECT_RUN_PLAN.md. Fill WRITER_MODEL_AB_PROJECT_MATRIX and QA_MODEL_AB_PROJECT_MATRIX. Present to owner for selection.

---

*CCD 签发：2026-05-15*
