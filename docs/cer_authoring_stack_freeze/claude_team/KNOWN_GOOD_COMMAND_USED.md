# KNOWN GOOD COMMAND USED — Stack A/B Execution

> Claude Code | 2026-05-15

## Primary Command

```bash
cd /Users/winstonwei/Documents/Playground/deer-flow
backend/.venv/bin/python backend/scripts/run_cer_authoring.py \
  --project-id <PROJECT_ID> \
  --input-root "<INPUT_ROOT>" \
  --artifact-root "<ARTIFACT_ROOT>" \
  --strict-v7 --agent-team-mode stable-1plus6
```

## Source

- Script: `backend/scripts/run_cer_authoring.py` (also used by `scripts/cer_cowork_supervisor.py` as `AUTHORING_SCRIPT`)
- Python: `backend/.venv/bin/python`
- Mode: `--strict-v7` enables `CER_AUTHORING_STRICT_V7=1` and `CER_AUTHORING_ENABLE_LLM_AGENTS=1`
- Agent team: `stable-1plus6` (7 physical agents)

## Model Routing

Per-agent model routing via `CER_AUTHORING_MODEL_<AGENT>` env vars, resolved by `model_routing.py`.

## Previous Run Results

- Harness mode (no --strict-v7): Graph runs end-to-end. Takes 5-10 minutes. No LLM calls. Agents return harness_configured status.
- Strict-v7 mode: `run_cer_authoring.py --strict-v7` sets env vars for LLM execution. Previous run hung (no LLM provider access from VS Code). Attempting again with monitoring.

## Verification

- 323 tests pass (harness mode)
- graph/gates/agents zero diff
- Model routing resolves correctly for all 7 agents in isolation
