# DEERFLOW MODEL A/B PROJECT RUN PLAN

> CCD | 2026-05-15

## Project

Cardiac Tissue Stabilizer（米道斯 PILOT_02）。

**Input**: `/Users/winstonwei/CER-RAG/升级 CCD-3 个项目文件/CER_PILOT_STANDARD_02米道斯/01_AUTHORING_INPUT_ALLOWED`

**Output per run**: `.../CER_PILOT_STANDARD_02米道斯/02_AI_BASELINE_OUTPUT_FREEZE/ab_run_<N>/`

## Input Fixation

All A/B runs use identical:
- Same project input directory
- Same frozen prompts (PROMPT_PACK_V1)
- Same domain-specific template (cardiac_tissue_stabilizer)
- Same Gate 1-5 active
- Same evidence and claims (from first baseline run)

## Run Matrix

| Run ID | Writer Model | QA Model | Extraction | Reasoning | Purpose |
|--------|-------------|----------|------------|-----------|---------|
| AB-0 | kimi-k2.6-code (global) | same | same | same | Resolution preflight — verify all agents resolve correctly. Record MODEL_RESOLUTION_TRACE. |
| AB-1 | deepseek-v4-pro | kimi-k2.6-code (baseline) | kimi-k2.6-code | deepseek-v4-pro | Writer A/B candidate A |
| AB-2 | kimi API | kimi-k2.6-code (baseline) | kimi-k2.6-code | deepseek-v4-pro | Writer A/B candidate B |
| AB-3 | kimi-k2.6-code | kimi-k2.6-code (baseline) | kimi-k2.6-code | deepseek-v4-pro | Writer baseline (current) |
| AB-4 | Best Writer from AB-1/2/3 | deepseek-v4-pro | kimi-k2.6-code | deepseek-v4-pro | QA A/B candidate A |
| AB-5 | Best Writer from AB-1/2/3 | kimi API | kimi-k2.6-code | deepseek-v4-pro | QA A/B candidate B |

## Per-Run Execution

Each run:
```
CER_AUTHORING_MODEL_CER_WRITER=<model> \
CER_AUTHORING_MODEL_QA_REVIEW=<model> \
backend/.venv/bin/python backend/scripts/run_cer_authoring.py \
  --project-id PILOT_02_MIDOS_AB_<N> \
  --input-root ".../01_AUTHORING_INPUT_ALLOWED" \
  --artifact-root ".../02_AI_BASELINE_OUTPUT_FREEZE/ab_run_<N>/" \
  --strict-v7 --agent-team-mode stable-1plus6
```

## Scoring per Run

After each run, score the Writer output on 8 dimensions:
- Gate 1: domain consistency (pass/fail + forbidden term count)
- Gate 2: IFU consumption (placeholder count)
- Gate 3: evidence consistency (forbidden phrase count)
- Gate 4: body cleanliness (banned string count)
- Gate 5: QA score (0-100)
- Professional expression (human reviewer qualitative 1-5)
- Section completeness (structural dimension from Gate 5)
- Internal language leakage count

QA output scored on:
- False pass on contaminated fixture
- False fail on clean fixture
- Finding specificity
- Dimension coverage

## Stop Conditions

- Any run modifies graph/gates/agents → STOP
- 323 tests fail at any point → STOP
- MODEL_RESOLUTION_TRACE shows global model used instead of per-agent → STOP
- Gate 1-5 all FAIL on all Writer candidates → STOP, report

## Acceptance

Writer model selected based on highest aggregate score across 8 dimensions. QA model selected based on false pass/fail rate. Owner reviews and approves final selection.

---

*CCD 签发：2026-05-15*
