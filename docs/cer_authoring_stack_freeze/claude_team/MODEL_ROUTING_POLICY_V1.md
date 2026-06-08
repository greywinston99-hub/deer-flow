# MODEL ROUTING POLICY V1.0 — CER Authoring

> Claude Code | 2026-05-15 | Phase 3A

## Policy Statement

CER Authoring agents must use task-appropriate models. No single model serves all task types. This policy defines per-task-type model assignments with explicit boundaries and forbidden combinations.

## Routing Table

| Agent | Task | Default Model | A/B Candidates | Forbidden |
|-------|------|---------------|----------------|-----------|
| intake-profile-claim | Extraction | kimi-k2.6-code | None | minimax |
| methodology-sota | Evidence Reasoning | deepseek-v4-pro | kimi-api | kimi-code, minimax |
| evidence | Evidence Reasoning | deepseek-v4-pro | kimi-api | kimi-code, minimax |
| cer-writer | CER Writer | deepseek-v4-pro | kimi-api (A/B pending) | kimi-code, minimax |
| qa-review | QA Reviewer | deepseek-v4-pro | kimi-api (A/B pending) | kimi-code, minimax |
| risk-equivalence-gspr | Risk/Equivalence | kimi-k2.6-code | deepseek-v4-pro | minimax |
| cer-authoring-lead-agent | Controller | kimi-k2.6-code | None | minimax |

## Model Usage Boundaries

### kimi-k2.6-code
- **For**: Extraction, structured mapping, controller triage
- **Not for**: Writer, QA, evidence reasoning
- **Risk if misused**: Template reuse, internal language leakage, weak domain reasoning

### deepseek-v4-pro
- **For**: Evidence reasoning, Writer, QA, Risk/Equivalence (recommended for all)
- **Not for**: —
- **Risk if unavailable**: Fall back to kimi-api for Writer/QA; keep kimi-code ONLY for extraction

### kimi-api
- **For**: A/B candidate for Writer and QA, reasoning fallback
- **Not for**: —
- **Risk**: Not yet validated for CER authoring; requires A/B test

### minimax-M2.7-highspeed
- **For**: Bulk title/abstract pre-screen ONLY (with timeout + fallback)
- **Not for**: Writer, QA, evidence reasoning, risk analysis, extraction
- **Risk**: Accuracy insufficient for medical writing or nuanced detection

## Change Procedure

1. Model change proposed with rationale in MODEL_ROUTING_POLICY_V1.md
2. If Writer/QA model change: A/B test required (same prompt/template/gates)
3. Set per-agent env var or state config for testing
4. Run full regression (≥323 tests)
5. Verify all 5 gates pass on clean fixture
6. Verify contaminated fixtures still HARD FAIL
7. Owner approves
8. Update default_model in model_routing.py ROUTING_POLICY_V1

## Rollback

Model assignments are config-driven. Rollback = restore env var or ROUTING_POLICY_V1 to previous version. No code rollback needed. Previous assignments hash-tracked in this document's change log.

## Change Log

| Date | Agent | Old Model | New Model | A/B Result | Authorized |
|------|-------|-----------|-----------|------------|------------|
| 2026-05-15 | All agents | inherit (→ kimi-k2.6-code) | Per ROUTING_POLICY_V1 | Pending | Pending owner |
