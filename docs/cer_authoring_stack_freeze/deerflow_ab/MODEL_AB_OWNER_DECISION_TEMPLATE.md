# MODEL A/B OWNER DECISION TEMPLATE

> CCD | 2026-05-15 | For owner completion after A/B results

## Writer Model Selection

| Candidate | Score | Gate Pass | Human Reviewability | Recommendation |
|-----------|-------|-----------|---------------------|----------------|
| deepseek-v4-pro | [ ] | [ ] | [ ] | |
| kimi API | [ ] | [ ] | [ ] | |
| kimi-k2.6-code (baseline) | [ ] | [ ] | [ ] | |

**Selected Writer Model**: _______________

**Rationale**:

**Limitations**:

## QA Model Selection

| Candidate | False Pass | False Fail | Finding Quality | Recommendation |
|-----------|-----------|-----------|-----------------|----------------|
| deepseek-v4-pro | [ ] | [ ] | [ ] | |
| kimi API | [ ] | [ ] | [ ] | |

**Selected QA Model**: _______________

**Rationale**:

## Fallback Model

If selected Writer model unavailable: _______________

If selected QA model unavailable: _______________

## Rejected Models

| Model | Reason for Rejection |
|-------|---------------------|
| [model] | [reason] |

## Owner Approval

- [ ] Writer model approved
- [ ] QA model approved
- [ ] Fallback model approved
- [ ] Routing policy updated with selections

**Approved by**: _______________ **Date**: _______________

## Post-Approval

- Update ROUTING_POLICY_V1 default_model entries
- Regenerate three pilot CERs under confirmed routing
- Verify gates + rubric on regenerated reports

---

*CCD 签发：2026-05-15*
