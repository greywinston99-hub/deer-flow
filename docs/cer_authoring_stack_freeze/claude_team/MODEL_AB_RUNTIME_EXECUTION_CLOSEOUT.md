# MODEL A/B RUNTIME EXECUTION CLOSEOUT

> Claude Code (VS Code implementer) | 2026-05-15

## Final Status: `MODEL_AB_RUNTIME_BLOCKED_ACCESS`

## What Was Attempted

AB-0 Model Resolution Preflight was launched with `run_cer_authoring.py --strict-v7` against PILOT_02 (Cardiac Tissue Stabilizer). The process ran for 10+ minutes with zero output — the DeerFlow LLM runtime is not accessible from VS Code Claude Code.

## What Was Verified (Deterministic, No LLM Required)

| Item | Status |
|------|--------|
| Model routing config resolution | 7/7 agents resolve correctly |
| Per-agent routing (isolation test) | PASS |
| Forbidden model enforcement | PASS (kimi-code/minimax blocked for Writer/QA) |
| Trace collection infrastructure | IMPLEMENTED (record_resolution_trace + write_resolution_trace_json) |
| Full regression | 323 PASS |
| graph.py / gates.py / agents.py | ZERO DIFF |
| Gate 1-5 deterministic evaluation | Correctly FAILs contaminated; PASSes clean |

## Why Blocked

1. **No LLM provider access**: VS Code Claude Code environment does not have the DeerFlow LLM provider/router configured. `run_cer_authoring.py --strict-v7` sets `CER_AUTHORING_STRICT_V7=1` but the SubagentExecutor requires actual LLM provider access which is not available here.

2. **Pipeline execution time**: Even in harness mode (no LLM), `run_cer_authoring.py` takes 5+ minutes for a full graph invocation. This is impractical for interactive A/B testing where 6 runs are needed.

3. **No DeerFlow runtime environment**: The A/B execution requires the DeerFlow runtime environment where LLM providers, MCP servers, and the full toolchain are configured.

## What Needs DeerFlow Runtime

| Run | Models | Purpose |
|-----|--------|---------|
| AB-0 | kimi-k2.6-code (global) | Resolution preflight |
| AB-1 | Writer=deepseek-v4-pro | Writer candidate A |
| AB-2 | Writer=kimi-api | Writer candidate B |
| AB-3 | Writer=kimi-k2.6-code | Writer baseline |
| AB-4 | QA=deepseek-v4-pro | QA candidate A |
| AB-5 | QA=kimi-api | QA candidate B |

## Execution Package Ready

Complete execution instructions and scoring templates available in:
- `DEERFLOW_OPERATOR_AB_COMMANDS.md` (step-by-step commands)
- `WRITER_MODEL_AB_RUNTIME_RESULT.md` (Writer scoring template)
- `QA_MODEL_AB_RUNTIME_RESULT.md` (QA scoring template)
- `MODEL_RESOLUTION_TRACE_REQUIREMENT.md` (trace validation rules)

## Infrastructure Ready

- `model_routing.py`: per-agent routing + trace collection (`record_resolution_trace`, `write_resolution_trace_json`)
- `agent_runtime.py`: routing integration + trace recording
- `artifacts.py`: automatic `MODEL_RESOLUTION_TRACE.json` export
- 323 tests validate deterministic correctness
