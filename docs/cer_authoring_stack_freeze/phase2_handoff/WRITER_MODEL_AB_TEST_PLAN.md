# WRITER MODEL A/B TEST PLAN

> CCD | 2026-05-15 | Phase 3A

## Test Design

**Fixed variables**: Same project (choose one pilot), same frozen prompts (PROMPT_PACK_V1), same domain-specific template, same decomposed claims and evidence, same Gate 1-5 active.

**Variable**: Writer model only. Current model vs at least one candidate writing model.

**Execution environment**: DeerFlow runtime (`run_cer_authoring.py --strict-v7`). Cannot be executed in VS Code Claude Code — must be in environment with LLM runtime.

## Candidates

| Name | Type | Rationale |
|------|------|-----------|
| Current: kimi-k2.6-code | Coding model | Baseline. Known issues: template reuse, internal language leakage. |
| Candidate A: DeepSeek V4 Pro | General + reasoning | Already used as parent router model. Good Chinese-English clinical text. |
| Candidate B: Claude Sonnet | Writing + reasoning | Strong professional writing, domain-aware. |

## Scoring Dimensions

Each generated CER section scored on 8 dimensions:

| Dimension | Weight | How Scored |
|-----------|--------|-----------|
| Domain consistency | 20% | Gate 1 pass/fail + forbidden term count |
| Evidence consistency | 20% | Gate 3 pass/fail + forbidden phrase count |
| IFU source usage | 15% | Gate 2 pass/fail + placeholder count |
| Internal language leakage | 10% | Gate 4 pass/fail + banned string count |
| Section completeness | 10% | Gate 5 structural dimension |
| Professional expression | 10% | Human reviewer qualitative score (1-5) |
| Gate pass rate | 10% | Binary: all 5 pass or not |
| Repeatability | 5% | Two runs, same output consistency |

## Execution

1. Run Pilot 01 with current model → collect all scores
2. Run Pilot 01 with candidate A → collect all scores
3. Run Pilot 01 with candidate B → collect all scores
4. Compare scores → select best Writer model
5. Document rationale in WRITER_MODEL_SELECTION_REPORT.md

## Acceptance

Best model selected based on aggregate score. Model switch only if candidate outperforms current on ≥3 dimensions AND no dimension regresses below current baseline.

---

*CCD 签发：2026-05-15*
