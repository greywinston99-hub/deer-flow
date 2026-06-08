# MODEL ROUTING POLICY — DRAFT V2

> CCD | 2026-05-15 | 4-Model Pool

## Provisional Routing Table

| Agent | Model | Status |
|-------|-------|--------|
| intake-profile-claim | kimi-k2.6-code | CURRENT — structured extraction, validated |
| methodology-sota | deepseek V4 pro | RECOMMENDED — reasoning + clinical knowledge |
| evidence | deepseek V4 pro | RECOMMENDED — quantitative + domain precision |
| cer-writer | deepseek V4 pro | RECOMMENDED — best medical writing candidate. A/B vs kimi API required |
| risk-equivalence-gspr | kimi-k2.6-code | CURRENT — structured mapping |
| qa-review | deepseek V4 pro | RECOMMENDED — detection sensitivity. A/B vs kimi API required |
| MCP adapters | N/A | Deterministic API calls |

## Model Usage Boundaries

| 模型 | 可用于 | 禁止用于 |
|------|--------|---------|
| kimi-k2.6-code | Extraction, Risk/Equivalence | Writer, QA (unless A/B proves superiority) |
| kimi API | Writer (A/B candidate), QA (A/B candidate), Reasoning (fallback) | — |
| deepseek V4 pro | Reasoning, Writer, QA (all recommended) | — |
| minimax M2.7 highspeed | Extraction (latency test only) | Writer, QA, Evidence Reasoning |

## Implementation States

**Phase 3A (current)**: All agents inherit from parent model. A/B plans documented. Per-agent routing not implemented.

**Phase 3B (post-A/B)**: Per-agent model override implemented in agents.py. Writer and QA assigned based on A/B results. Extraction kept on kimi-code.

**Phase 3C (verified)**: Regenerated pilot CERs under routed models pass all gates + rubric.

## Rollback

Model assignments stored in versioned config. Previous assignment hash-tracked. Rollback = restore previous config + re-verify gates. No code rollback needed — model routing is config, not code.

## Owner Authorization

Model switch requires owner approval. Model switch ≠ gate bypass. All 5 gates remain active on any model.

---

*CCD 签发：2026-05-15 | Draft V2 — subject to A/B results*
