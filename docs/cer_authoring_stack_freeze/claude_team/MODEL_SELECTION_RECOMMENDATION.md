# MODEL SELECTION RECOMMENDATION — Pending A/B Execution

> Claude Code | 2026-05-15 | For owner review after A/B execution

## Status: `AWAITING_AB_EXECUTION`

No model selection is final until A/B runtime results are available. This document provides the provisional recommendation with rationale.

## Writer Model

### Provisional Recommendation: **DeepSeek V4 Pro**

**Rationale**:
1. **Task match**: CER writing requires professional medical writing + domain consistency + evidence fidelity + constraint following. DeepSeek V4 Pro is the strongest reasoning model available with good Chinese-English clinical text capability.
2. **Baseline deficiency**: Current baseline (kimi-k2.6-code) is known to produce template reuse and internal language leakage (confirmed in PILOT_01/02/03 contaminated reports). It is a coding model, not a medical writing model.
3. **Gate compatibility**: DeepSeek's structured output format is compatible with the deterministic gate evaluation pipeline.
4. **Boundary safety**: DeepSeek has no forbidden task types — it is allowed for all CER authoring tasks.

**Risks**:
- Not yet validated on CER-specific medical writing quality
- Availability depends on local provider router

**Confirmation required from A/B**:
- Must beat kimi-code baseline on domain consistency, evidence consistency, and internal language leakage
- Must pass all 5 gates on clean fixture
- Professional expression must be human-reviewable

### Fallback: Kimi API

If DeepSeek is unavailable or A/B shows regression:
- Kimi API as Writer model
- Requires A/B to confirm no regression vs baseline

## QA Reviewer Model

### Provisional Recommendation: **DeepSeek V4 Pro** (or same as Writer for operational simplicity)

**Rationale**:
1. Deterministic Gates 1-5 already provide core quality enforcement — QA model is lower priority
2. DeepSeek's strong reasoning supports detection sensitivity (false pass/fail prevention)
3. Operational simplicity: using same model as Writer reduces configuration complexity

**Confirmation required from A/B**:
- False pass rate MUST be 0
- False fail rate MUST be 0

## Extraction Models (No A/B Required)

### Confirmed: **kimi-k2.6-code** for intake, risk/equivalence

Already validated through pipeline. Structured extraction task matches kimi-code's strengths. No model switch needed.

## Evidence Reasoning Models (Deferred)

### Provisional: **DeepSeek V4 Pro** for methodology-sota, evidence

A/B deferred — lower priority than Writer/QA. Current config routes these to deepseek-v4-pro via routing policy. Evidence reasoning A/B can follow Writer selection using same methodology.

## Summary Table

| Agent | Current | Provisional | A/B Required | Owner Decision |
|-------|---------|-------------|-------------|----------------|
| cer-writer | kimi-k2.6-code | deepseek-v4-pro | YES — RUN PENDING | REQUIRED |
| qa-review | kimi-k2.6-code | deepseek-v4-pro | YES — RUN PENDING | REQUIRED |
| methodology-sota | kimi-k2.6-code | deepseek-v4-pro | DEFERRED | After Writer |
| evidence | kimi-k2.6-code | deepseek-v4-pro | DEFERRED | After Writer |
| intake-profile-claim | kimi-k2.6-code | kimi-k2.6-code | NO | CONFIRMED |
| risk-equivalence-gspr | kimi-k2.6-code | kimi-k2.6-code | NO | CONFIRMED |

## Owner Decision Required For

1. Approve Writer model switch to DeepSeek V4 Pro (after A/B confirms)
2. Approve QA model switch to DeepSeek V4 Pro (or match Writer model)
3. Approve evidence reasoning model switch to DeepSeek V4 Pro (can be same decision)
4. Any deviation from these recommendations requires documented rationale
