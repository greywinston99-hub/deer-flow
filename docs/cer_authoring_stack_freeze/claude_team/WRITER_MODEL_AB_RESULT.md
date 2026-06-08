# WRITER MODEL A/B RESULT — DeerFlow Runtime

> Claude Code | 2026-05-15

## Status: `MODEL_AB_BLOCKED_RUNTIME_ACCESS`

## Blocked Reason

DeerFlow LLM runtime not accessible from VS Code Claude Code. Writer A/B runs (AB-1, AB-2, AB-3) require `run_cer_authoring.py --strict-v7` with actual LLM provider access.

## Scoring Template (To Fill After DeerFlow Execution)

### Run AB-1: Writer = deepseek-v4-pro

| Dimension | Weight | Score | Notes |
|-----------|--------|-------|-------|
| Gate 1 — Domain consistency | 20% | [ ]/20 | Forbidden term count: ___ |
| Gate 2 — IFU source usage | 15% | [ ]/15 | IFU placeholder count: ___ |
| Gate 3 — Evidence consistency | 20% | [ ]/20 | Forbidden phrase count: ___ |
| Gate 4 — Internal language | 10% | [ ]/10 | Banned string count: ___ |
| Gate 5 — QA composite | 10% | [ ]/10 | QA score: ___ |
| Section completeness | 10% | [ ]/10 | Sections with content: ___/___ |
| Professional expression | 10% | [ ]/10 | Reviewer score 1-5: ___ |
| Repeatability (2 runs) | 5% | [ ]/5 | Overlap: ___% |
| **TOTAL** | **100%** | **[ ]** | |

### Run AB-2: Writer = kimi-api

| Dimension | Weight | Score | Notes |
|-----------|--------|-------|-------|
| Gate 1 — Domain consistency | 20% | [ ]/20 | |
| Gate 2 — IFU source usage | 15% | [ ]/15 | |
| Gate 3 — Evidence consistency | 20% | [ ]/20 | |
| Gate 4 — Internal language | 10% | [ ]/10 | |
| Gate 5 — QA composite | 10% | [ ]/10 | |
| Section completeness | 10% | [ ]/10 | |
| Professional expression | 10% | [ ]/10 | |
| Repeatability (2 runs) | 5% | [ ]/5 | |
| **TOTAL** | **100%** | **[ ]** | |

### Run AB-3: Writer = kimi-k2.6-code (baseline)

| Dimension | Weight | Score | Notes |
|-----------|--------|-------|-------|
| Gate 1 — Domain consistency | 20% | [ ]/20 | |
| Gate 2 — IFU source usage | 15% | [ ]/15 | |
| Gate 3 — Evidence consistency | 20% | [ ]/20 | |
| Gate 4 — Internal language | 10% | [ ]/10 | |
| Gate 5 — QA composite | 10% | [ ]/10 | |
| Section completeness | 10% | [ ]/10 | |
| Professional expression | 10% | [ ]/10 | |
| Repeatability (2 runs) | 5% | [ ]/5 | |
| **TOTAL** | **100%** | **[ ]** | |

### Acceptance

- Best aggregate score across 8 dimensions
- Must beat baseline on ≥3 dimensions
- NO dimension may regress below baseline
- All 5 gates must PASS on clean fixture

## Execution Commands (DeerFlow Operator)

```bash
cd /Users/winstonwei/Documents/Playground/deer-flow

# AB-1: Writer Candidate A
CER_AUTHORING_MODEL_CER_WRITER=deepseek-v4-pro \
CER_AUTHORING_MODEL_METHODOLOGY_SOTA=deepseek-v4-pro \
CER_AUTHORING_MODEL_EVIDENCE=deepseek-v4-pro \
backend/.venv/bin/python backend/scripts/run_cer_authoring.py \
  --project-id PILOT_02_MIDOS_AB_1 \
  --input-root "/Users/winstonwei/CER-RAG/升级 CCD-3 个项目文件/CER_PILOT_STANDARD_02米道斯/01_AUTHORING_INPUT_ALLOWED" \
  --artifact-root "/Users/winstonwei/CER-RAG/升级 CCD-3 个项目文件/CER_PILOT_STANDARD_02米道斯/02_AI_BASELINE_OUTPUT_FREEZE/ab_run_1/" \
  --strict-v7 --agent-team-mode stable-1plus6

# AB-2: Writer Candidate B
CER_AUTHORING_MODEL_CER_WRITER=kimi-api \
[rest same as AB-1, artifact-root .../ab_run_2/]

# AB-3: Writer Baseline
CER_AUTHORING_MODEL_CER_WRITER=kimi-k2.6-code \
[rest same as AB-1, artifact-root .../ab_run_3/]
```
