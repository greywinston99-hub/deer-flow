# WRITER MODEL SELECTION REPORT — Phase 2C

> Claude Code | 2026-05-15

## Current Model Routing

The CER Authoring runtime uses a unified model routing scheme:
- Parent model: inherited from runtime environment (`CER_AUTHORING_MODEL_NAME` env var or `state["model_name"]`)
- All subagents (stable 1+6 + production virtual + review virtual): `model="inherit"`
- No per-agent model override in current configuration
- Model fallback: currently disabled (no fallback array configured)

## Model Selection Rationale

The current model (DeepSeek V4 Pro via local provider router) was selected for:
1. Strong domain reasoning: follows complex medical device regulatory instructions
2. Structured output: produces gate-compatible JSON outputs
3. Availability: runs through local provider router without external API dependency

## A/B Testing Framework (Documented, Not Executed)

Model A/B testing requires identical input, prompts, templates, and gates across candidates.
This requires full pipeline execution which is outside the implementer scope (requires graph/gates execution).

### Evaluation Dimensions

| Dimension | Weight | Measurement |
|-----------|--------|-------------|
| Domain consistency | 25% | Gate 1 forbidden term count |
| Evidence consistency | 25% | Gate 3 forbidden phrase matches |
| IFU source usage | 15% | Gate 2 placeholder count |
| Internal language leakage | 15% | Gate 4 banned string count |
| Section completeness | 10% | Required section coverage |
| Professional expression | 5% | Human reviewability rubric |
| Gate pass rate | 5% | Gates 1-5 combined result |

### Candidate Models (for future testing)

| Model | Provider | Notes |
|-------|----------|-------|
| DeepSeek V4 Pro | Local router | Current; strong regulatory reasoning |
| Kimi K2.6 | Local router | Fast iteration; useful for evidence processing |
| Claude Opus 4.7 | Anthropic API | Strongest regulatory writing; external API required |

## Recommendation

Keep current model (DeepSeek V4 Pro / inherited from parent runtime) for authoring.
Model switch is a configuration change (env var), not a code change.
Model evaluation must be repeated whenever CER_AUTHORING_MODEL_NAME changes.
