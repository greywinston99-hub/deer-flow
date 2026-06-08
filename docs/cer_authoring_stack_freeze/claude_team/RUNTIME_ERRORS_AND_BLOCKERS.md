# RUNTIME ERRORS AND BLOCKERS — Model A/B Execution

> Claude Code | 2026-05-15

## BLOCKER 1: DeerFlow LLM Runtime Not Accessible

- **Severity**: BLOCKING
- **Impact**: AB-0 through AB-5 cannot execute
- **Detail**: `run_cer_authoring.py --strict-v7` launched against PILOT_02 hung for 10+ minutes with zero output. The SubagentExecutor requires actual LLM provider access which is not configured in the VS Code Claude Code environment.
- **Resolution**: Execute A/B runs from the DeerFlow runtime environment where LLM providers, MCP servers, and the full toolchain are configured.

## BLOCKER 2: Pipeline Execution Time

- **Severity**: HIGH
- **Impact**: Interactive A/B testing impractical
- **Detail**: Even in harness mode (no LLM), `run_cer_authoring.py` takes 5+ minutes per run. 6 A/B runs × 5+ minutes = 30+ minutes minimum.
- **Resolution**: Batch execution in dedicated DeerFlow runtime. Not suitable for interactive VS Code Claude Code session.

## NON-BLOCKER: Trace Infrastructure Not End-to-End Verified

- **Severity**: LOW
- **Impact**: MODEL_RESOLUTION_TRACE.json not verified in actual pipeline output
- **Detail**: `record_resolution_trace()` and `write_resolution_trace_json()` are integrated in agent_runtime.py + artifacts.py, module-level tests pass, but end-to-end trace generation not verified in a full pipeline run.
- **Resolution**: First successful AB-0 run in DeerFlow runtime will verify trace generation.

## What Works (Deterministic)

| Component | Status |
|-----------|--------|
| model_routing.py resolver | 7/7 agents resolve correctly |
| Per-agent routing (isolation) | PASS |
| Forbidden model enforcement | PASS |
| Trace collection code | COMPILES + IMPORTS |
| 323 tests | PASS |
| graph/gates/agents diff | ZERO |

## Environment Requirements for DeerFlow Operator

```bash
# Required env vars
export CER_AUTHORING_STRICT_V7=1       # Set automatically by --strict-v7
export CER_AUTHORING_ENABLE_LLM_AGENTS=1

# Required: LLM provider/router configured and accessible
# Required: MCP servers accessible (PubMed, Europe PMC, CT.gov)
# Required: All Python dependencies installed
```

## Next Action

DeerFlow operator executes `DEERFLOW_OPERATOR_AB_COMMANDS.md` step by step in the DeerFlow runtime environment. AB-0 must pass before AB-1 through AB-5. Scoring templates in WRITER_MODEL_AB_RUNTIME_RESULT.md and QA_MODEL_AB_RUNTIME_RESULT.md.
