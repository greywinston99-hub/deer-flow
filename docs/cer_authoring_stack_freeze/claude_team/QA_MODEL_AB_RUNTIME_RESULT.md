# QA MODEL A/B RUNTIME RESULT

> Claude Code | 2026-05-15

## Status: `MODEL_AB_BLOCKED_RUNTIME_ACCESS`

## Blocked Reason

Same as Writer A/B — no LLM runtime access from VS Code Claude Code.
QA reviewer agent (`qa-review`) requires LLM execution.

## Important Distinction

Gates 1-5 are **DETERMINISTIC** — they do not use an LLM. They are already verified:
- Correctly FAIL all contaminated reports (verified against PILOT_01, PILOT_02, PILOT_03)
- Correctly PASS clean reports (verified against minimal fixture)
- 25 targeted gate tests PASS
- Full regression 323 PASS

The QA model A/B only affects the `qa-review` agent which evaluates body content quality beyond deterministic gates. QA model selection is therefore **lower priority** than Writer model selection.

## Complete Execution Instructions for DeerFlow Operator

### Prerequisites

Same as Writer A/B: `CER_AUTHORING_STRICT_V7=1`, `CER_AUTHORING_ENABLE_LLM_AGENTS=1`

### Test Inputs

Contaminated fixtures (expect QA FAIL):
- PILOT_01 Plasma Electrode contaminated draft
- PILOT_02 Cardiac Stabilizer contaminated draft

Clean fixture (expect QA PASS):
- Clean cardiac stabilizer minimal report (all fields populated, INSUFFICIENT claims with honest wording, no internal language)

### Run Procedure

```bash
# QA Candidate A (deepseek-v4-pro)
export CER_AUTHORING_MODEL_QA_REVIEW=deepseek-v4-pro
python backend/scripts/run_cer_authoring.py --strict-v7 --project PILOT_01
# Inspect: writer_remediation_qa_report.json
# Verify: score 0/FAIL on contaminated, PASS on clean

# QA Candidate B (kimi-api)
export CER_AUTHORING_MODEL_QA_REVIEW=kimi-api
python backend/scripts/run_cer_authoring.py --strict-v7 --project PILOT_01
# Inspect: writer_remediation_qa_report.json
```

### Scoring Template (To Fill In)

| Dimension | Weight | Candidate A (deepseek) | Candidate B (kimi-api) |
|-----------|--------|----------------------|----------------------|
| False pass rate (contaminated→FAIL) | 35% | [ ]/35 — Must be 0 false passes | [ ]/35 |
| False fail rate (clean→PASS) | 35% | [ ]/35 — Must be 0 false fails | [ ]/35 |
| Finding specificity | 15% | [ ]/15 — Identifies specific contamination type? | [ ]/15 |
| Dimension coverage | 15% | [ ]/15 — All 4 QA dimensions scored? | [ ]/15 |
| **TOTAL** | **100%** | **[ ]** | **[ ]** |

### Acceptance

- False pass rate MUST be 0 (NO contaminated report marked PASS)
- False fail rate MUST be 0 (clean report marked PASS)
- If both pass: select based on finding specificity + dimension coverage

## Recommendation (Pending A/B)

QA model selection is LOWER PRIORITY than Writer selection. Deterministic Gates 1-5 already provide core quality enforcement. If A/B shows both candidates satisfy false pass/fail = 0, defer to whichever matches the selected Writer model (for operational simplicity).
