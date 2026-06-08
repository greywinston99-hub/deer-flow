# MODEL RUNTIME INVENTORY

> CCD | 2026-05-15 | Phase 3A

## Current Model Configuration

**Parent model source**: `DEFAULT_STRICT_AUTHORING_MODEL = "kimi-k2.6-code"` (run_cer_authoring.py:37). Override via `--model-name` CLI or `CER_AUTHORING_MODEL_NAME` env var.

**Subagent inheritance**: All 6 physical subagents use `model="inherit"` (agents.py:313-335). No per-agent model override configured.

## Per-Agent Actual Model

| Agent | Current Model | Override Available | Notes |
|-------|-------------|-------------------|-------|
| intake-profile-claim | inherit (→ kimi-k2.6-code) | env var only | Device profile extraction |
| methodology-sota | inherit (→ kimi-k2.6-code) | env var only | SOTA search + benchmark |
| evidence | inherit (→ kimi-k2.6-code) | env var only | Evidence appraisal |
| cer-writer | inherit (→ kimi-k2.6-code) | env var only | CER section writing |
| risk-equivalence-gspr | inherit (→ kimi-k2.6-code) | env var only | Risk/GSPR mapping |
| qa-review | inherit (→ kimi-k2.6-code) | env var only | Gate review |

## Override Mechanism

`run_cer_authoring.py` line 74: `model_name = args.model_name or os.environ.get("CER_AUTHORING_MODEL_NAME") or DEFAULT_STRICT_AUTHORING_MODEL`. Single model for all agents. No per-agent override in current codebase. `agents.py` `model="inherit"` means each agent receives the parent model — no agent-specific model name parameter.

## Runtime Access Status

Claude Code VS Code environment has NO LLM runtime access. Model A/B testing requires full pipeline execution with `run_cer_authoring.py --strict-v7`. This can only be done in the DeerFlow runtime environment, not in the VS Code Claude Code window.

## Recommendation

Per-agent model override requires code change to `agents.py` subagent config (add `model` field per agent). Until then, model routing is global via env var. A/B testing deferred to DeerFlow runtime environment.

---

*CCD 签发：2026-05-15*
