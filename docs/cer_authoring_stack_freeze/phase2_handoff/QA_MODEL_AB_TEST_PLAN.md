# QA MODEL A/B TEST PLAN

> CCD | 2026-05-15 | Phase 3A

## Test Design

**Test inputs**: Contaminated regression fixtures (F1 Plasma Electrode, F2 Cardiac Stabilizer) + one clean fixture.

**Fixed variables**: Same frozen QA prompt, same Gate 1-5 evaluation logic.

**Variable**: QA model only. Current model vs same candidate used for Writer.

## Scoring

| Dimension | How Scored |
|-----------|-----------|
| False pass rate | QA gate score on contaminated reports. Must be 0 or FAIL. |
| False fail rate | QA gate score on clean fixture. Must be PASS. |
| Finding specificity | Does QA identify the specific contamination type or give generic "fail"? |
| Dimension coverage | Are all 4 QA dimensions (domain, evidence, IFU, cleanliness) independently scored? |

## Acceptance

False pass rate MUST be 0 on contaminated fixtures. False fail rate MUST be 0 on clean fixture. If current model already meets these criteria, model switch for QA is optional.

---

*CCD 签发：2026-05-15*
