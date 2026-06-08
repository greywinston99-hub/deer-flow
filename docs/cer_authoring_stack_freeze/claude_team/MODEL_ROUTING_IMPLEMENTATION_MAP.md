# MODEL ROUTING IMPLEMENTATION MAP

> Claude Code | 2026-05-15 | Phase 3A

## Implementation Summary

Config-driven per-agent model routing implemented via `model_routing.py` resolver + `agent_runtime.py` integration. No changes to agents.py, graph.py, or gates.py.

## Per-Agent Resolution

| Agent | Task Type | Default Model | Override | Status |
|-------|-----------|---------------|----------|--------|
| intake-profile-claim | extraction_structuring | kimi-k2.6-code | env/state | ACTIVE |
| methodology-sota | evidence_reasoning | deepseek-v4-pro | env/state | ACTIVE |
| evidence | evidence_reasoning | deepseek-v4-pro | env/state | ACTIVE |
| cer-writer | cer_writer | deepseek-v4-pro | env/state | ACTIVE (A/B pending) |
| qa-review | qa_reviewer | deepseek-v4-pro | env/state | ACTIVE (A/B pending) |
| risk-equivalence-gspr | risk_equivalence | kimi-k2.6-code | env/state | ACTIVE |
| cer-authoring-lead-agent | controller_triage | kimi-k2.6-code | env/state | ACTIVE |

## Override Mechanism

Priority (highest first):
1. `CER_AUTHORING_MODEL_<AGENT>` env var (e.g., `CER_AUTHORING_MODEL_CER_WRITER=deepseek-v4-pro`)
2. `state["model_routing"]` dict per-agent override
3. `ROUTING_POLICY_V1` default_model in model_routing.py
4. `CER_AUTHORING_MODEL_NAME` global env var
5. `DEFAULT_PARENT_MODEL = "kimi-k2.6-code"`

## Deterministic Stages (No Model)

Following stages are deterministic functions — no model routing:
- Gate evaluation functions (Gates 1-5, G39-G46)
- Quarantine routing
- PDF parsing pipeline
- Artifact export
- Evidence sufficiency computation
- Claim-to-PICO derivation

## Model Boundaries Enforced

- kimi-k2.6-code → FORBIDDEN for cer-writer, qa-review, methodology-sota, evidence
- minimax-M2.7-highspeed → FORBIDDEN for cer-writer, qa-review, evidence_reasoning, risk_equivalence
- deepseek-v4-pro → ALLOWED for all agent task types
- kimi-api → ALLOWED for all agent task types (A/B candidate)

## Code Changes

- `model_routing.py` — NEW: routing policy, resolver, boundary validation
- `agent_runtime.py` — modified: per-agent model override after config build (~15 lines)
- agents.py — UNCHANGED
- graph.py — UNCHANGED
- gates.py — UNCHANGED
