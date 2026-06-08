# MODEL SELECTION RECOMMENDATION FOR OWNER

> Claude Code (implementer) | 2026-05-15 | AWAITING A/B EXECUTION

## Status: `AWAITING_AB_EXECUTION`

No model selection is final until A/B runtime results are available. This document provides provisional recommendation with full rationale for owner review.

## Writer Model

### Provisional Recommendation: **DeepSeek V4 Pro**

**Rationale**:
1. **Task match**: CER writing requires professional medical writing, domain consistency, evidence fidelity, and constraint following. DeepSeek V4 Pro is the strongest reasoning model available in the current pool.
2. **Baseline deficiency**: Current baseline (kimi-k2.6-code) is a coding model. Phase 1 contaminated report audit confirmed kimi-code produces: template reuse (urology text in cardiac report), internal language leakage (Claude/DeerFlow/MCP/not_allowed/score:100 in CER body), and cross-domain SOTA contamination.
3. **Gate compatibility**: All 5 writer remediation gates are deterministic — they validate output regardless of which model produced it. Any model that passes all 5 gates is acceptable. DeepSeek's structured output format aligns with gate validation.
4. **Boundary safety**: DeepSeek has NO forbidden task types in the model usage boundaries.

**Risks**:
- Not yet validated on CER-specific medical writing quality (A/B required)
- Availability depends on local provider router

**Confirmation required from A/B**:
- Must beat kimi-code baseline on domain consistency (Gate 1) and evidence consistency (Gate 3)
- Must beat kimi-code baseline on internal language leakage (Gate 4)
- Professional expression must be human-reviewable (score ≥3 on 1-5 scale)

### Fallback: **Kimi API**

If DeepSeek is unavailable or A/B shows regression:
- Use Kimi API as Writer model
- Requires A/B to confirm no regression vs baseline

## QA Reviewer Model

### Provisional Recommendation: **DeepSeek V4 Pro** (Match Writer model)

**Rationale**:
1. Deterministic Gates 1-5 already provide core quality enforcement — QA model is LOWER PRIORITY
2. Using same model as Writer simplifies operational configuration
3. DeepSeek's strong reasoning supports detection sensitivity

**Confirmation required from A/B**:
- False pass rate MUST be 0 (no contaminated report gets QA PASS)
- False fail rate MUST be 0 (clean report gets QA PASS)

## Extraction Models

### Confirmed: **kimi-k2.6-code** for intake, risk/equivalence

Already validated through pipeline. Structured extraction task. No A/B required. No model switch needed.

## Evidence Reasoning Models

### Provisional: **DeepSeek V4 Pro** for methodology-sota, evidence

A/B deferred — lower priority than Writer/QA. Current routing policy already assigns deepseek-v4-pro to these agents.

## Summary for Owner Decision

| Agent | Current | Recommended | A/B Required | Owner Decision |
|-------|---------|-------------|-------------|----------------|
| cer-writer | kimi-k2.6-code | deepseek-v4-pro | YES — pending execution | [ ] Approve / [ ] Reject |
| qa-review | kimi-k2.6-code | deepseek-v4-pro | YES — pending execution | [ ] Approve / [ ] Reject |
| methodology-sota | kimi-k2.6-code | deepseek-v4-pro | Deferred | [ ] Follow Writer |
| evidence | kimi-k2.6-code | deepseek-v4-pro | Deferred | [ ] Follow Writer |
| intake-profile-claim | kimi-k2.6-code | kimi-k2.6-code | No | [ ] Confirmed |
| risk-equivalence-gspr | kimi-k2.6-code | kimi-k2.6-code | No | [ ] Confirmed |

## What Changes After A/B

1. Fill WRITER_MODEL_AB_RESULT.md scoring table
2. Fill QA_MODEL_AB_RESULT.md scoring table
3. Owner reviews and signs MODEL_AB_OWNER_DECISION_TEMPLATE.md
4. Update model_routing.py ROUTING_POLICY_V1 default_model entries
5. Deploy to DeerFlow runtime with confirmed models
6. Regenerate pilot CERs under confirmed routing

## Owner Approval

- [ ] Writer model approved: _______________
- [ ] QA model approved: _______________
- [ ] Fallback model approved: _______________
- [ ] Evidence reasoning models approved: _______________

**Approved by**: _______________ **Date**: _______________
