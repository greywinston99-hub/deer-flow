# QA MODEL A/B RESULT — DeerFlow Runtime

> Claude Code | 2026-05-15

## Status: `MODEL_AB_BLOCKED_RUNTIME_ACCESS`

## Blocked Reason

Same as Writer A/B — DeerFlow LLM runtime not accessible.

## Important Note

Gates 1-5 are DETERMINISTIC (not model-dependent). QA model A/B only affects the `qa-review` agent which evaluates body content quality. Deterministic gates already correctly FAIL contaminated reports and PASS clean reports.

## Scoring Template (To Fill After DeerFlow Execution)

### Run AB-4: QA = deepseek-v4-pro

| Dimension | Weight | Score | Notes |
|-----------|--------|-------|-------|
| False pass rate (contaminated→FAIL) | 35% | [ ]/35 | Must be 0 false passes |
| False fail rate (clean→PASS) | 35% | [ ]/35 | Must be 0 false fails |
| Finding specificity | 15% | [ ]/15 | Specific contamination type identified? |
| Dimension coverage | 15% | [ ]/15 | All 4 QA dimensions scored? |
| **TOTAL** | **100%** | **[ ]** | |

### Run AB-5: QA = kimi-api

| Dimension | Weight | Score | Notes |
|-----------|--------|-------|-------|
| False pass rate | 35% | [ ]/35 | |
| False fail rate | 35% | [ ]/35 | |
| Finding specificity | 15% | [ ]/15 | |
| Dimension coverage | 15% | [ ]/15 | |
| **TOTAL** | **100%** | **[ ]** | |

### Acceptance

- False pass rate MUST be 0 (NO contaminated report gets PASS)
- False fail rate MUST be 0 (clean report gets PASS)
- If both pass: select based on finding specificity + dimension coverage
- If both fail false pass/fail: QA model switch is NOT the fix — deterministic gates provide core enforcement

## Execution Commands (DeerFlow Operator)

```bash
# AB-4: QA Candidate A (use best Writer from AB-1/2/3)
CER_AUTHORING_MODEL_CER_WRITER=<best_writer_model> \
CER_AUTHORING_MODEL_QA_REVIEW=deepseek-v4-pro \
CER_AUTHORING_MODEL_METHODOLOGY_SOTA=deepseek-v4-pro \
CER_AUTHORING_MODEL_EVIDENCE=deepseek-v4-pro \
backend/.venv/bin/python backend/scripts/run_cer_authoring.py \
  --project-id PILOT_02_MIDOS_AB_4 \
  --input-root "/Users/winstonwei/CER-RAG/升级 CCD-3 个项目文件/CER_PILOT_STANDARD_02米道斯/01_AUTHORING_INPUT_ALLOWED" \
  --artifact-root "/Users/winstonwei/CER-RAG/升级 CCD-3 个项目文件/CER_PILOT_STANDARD_02米道斯/02_AI_BASELINE_OUTPUT_FREEZE/ab_run_4/" \
  --strict-v7 --agent-team-mode stable-1plus6

# AB-5: QA Candidate B
CER_AUTHORING_MODEL_QA_REVIEW=kimi-api \
[rest same, artifact-root .../ab_run_5/]
```
