# MODEL PROVIDER CONFIG NOTES — CER Authoring V1.0

> Claude Code | 2026-05-15 | Phase 3A

## Current Provider Setup

The CER Authoring runtime uses a local provider router. All models route through:
- Provider: local router (DeepSeek V4 Pro, Kimi K2.6, Kimi API, MiniMax M2.7)
- Config: runtime environment variables + `run_cer_authoring.py` CLI

## Per-Model Provider Configuration

### kimi-k2.6-code
- **Provider**: Local router → Kimi K2.6
- **Env var**: `CER_AUTHORING_MODEL_NAME=kimi-k2.6-code` (global)
- **Per-agent**: `CER_AUTHORING_MODEL_INTAKE_PROFILE_CLAIM=kimi-k2.6-code`
- **Fallback**: None configured
- **Notes**: Current default parent model. Used for extraction, risk mapping, controller.

### deepseek-v4-pro
- **Provider**: Local router → DeepSeek V4 Pro
- **Env var**: `CER_AUTHORING_MODEL_NAME=deepseek-v4-pro` (global override)
- **Per-agent**: `CER_AUTHORING_MODEL_CER_WRITER=deepseek-v4-pro` etc.
- **Fallback**: kimi-api (if deepseek unavailable)
- **Notes**: Recommended for Writer, QA, evidence reasoning. Not yet default parent model.

### kimi-api
- **Provider**: Local router → Kimi API
- **Env var**: `CER_AUTHORING_MODEL_NAME=kimi-api`
- **Per-agent**: `CER_AUTHORING_MODEL_CER_WRITER=kimi-api`
- **Fallback**: None configured
- **Notes**: A/B candidate only. Not validated for CER authoring.

### minimax-M2.7-highspeed
- **Provider**: Local router → MiniMax M2.7
- **Env var**: `CER_AUTHORING_MODEL_NAME=minimax-M2.7-highspeed`
- **Restrictions**: FORBIDDEN for Writer, QA, evidence reasoning
- **Timeout**: Required (30s default) for any MiniMax usage
- **Fallback**: Required — must have kimi-code or deepseek fallback
- **Notes**: Only for bulk pre-screen. Must not enter critical path.

## Environment Variable Reference

```bash
# Global parent model (all agents inherit unless overridden)
export CER_AUTHORING_MODEL_NAME=kimi-k2.6-code

# Per-agent overrides
export CER_AUTHORING_MODEL_CER_WRITER=deepseek-v4-pro
export CER_AUTHORING_MODEL_QA_REVIEW=deepseek-v4-pro
export CER_AUTHORING_MODEL_METHODOLOGY_SOTA=deepseek-v4-pro
export CER_AUTHORING_MODEL_EVIDENCE=deepseek-v4-pro
export CER_AUTHORING_MODEL_INTAKE_PROFILE_CLAIM=kimi-k2.6-code
export CER_AUTHORING_MODEL_RISK_EQUIVALENCE_GSPR=kimi-k2.6-code

# A/B testing
export CER_AUTHORING_MODEL_CER_WRITER=kimi-api        # Writer candidate B
export CER_AUTHORING_MODEL_QA_REVIEW=kimi-api          # QA candidate B
```

## State-Level Config

```python
state["model_routing"] = {
    "cer-writer": "deepseek-v4-pro",
    "qa-review": "deepseek-v4-pro",
    "methodology-sota": "deepseek-v4-pro",
}
```

## Unavailable Provider Handling

If a model's provider is unreachable:
1. Agent invocation returns BLOCKED (not silent fallback)
2. Error logged in agent invocation payload
3. Fallback only if explicitly configured in fallback policy
4. No silent model swap without owner knowledge
