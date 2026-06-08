# WRITER MODEL A/B RUNTIME RESULT

> Claude Code | 2026-05-15

## Status: `MODEL_AB_BLOCKED_RUNTIME_ACCESS`

## Blocked Reason

VS Code Claude Code environment has NO LLM runtime access. Confirmed:
- `CER_AUTHORING_STRICT_V7` env var: NOT SET
- `CER_AUTHORING_ENABLE_LLM_AGENTS` env var: NOT SET
- `_authoring_parent_model({})` returns `None`
- `invoke_authoring_agent()` returns `harness_configured` mode (no actual LLM call)
- `run_cer_authoring.py --strict-v7` requires DeerFlow runtime with configured LLM providers

Writer A/B testing requires full pipeline execution with the Writer agent generating CER drafts under different model configurations. This is not possible from VS Code Claude Code.

## What CAN Be Verified (Deterministic, No LLM Required)

| Item | Status |
|------|--------|
| Model routing config (model_routing.py) | 323 tests PASS |
| Per-agent routing resolution | 25 tests PASS |
| Gate 1-5 deterministic evaluation | Correctly FAILs contaminated; PASSes clean |
| Forbidden model enforcement | kimi-code/minimax blocked for Writer |
| A/B config skeleton | Ready |
| Full regression | 323 PASS |
| graph/gates/agents diff | ZERO |

## Complete Execution Instructions for DeerFlow Operator

### Prerequisites

```bash
cd /Users/winstonwei/Documents/Playground/deer-flow
export CER_AUTHORING_STRICT_V7=1
export CER_AUTHORING_ENABLE_LLM_AGENTS=1
```

### Test Projects

1. PILOT_01: `/Users/winstonwei/CER-RAG/升级 CCD-3 个项目文件/CER_PILOT_STANDARD_01启灏/`
2. PILOT_02: `/Users/winstonwei/CER-RAG/升级 CCD-3 个项目文件/CER_PILOT_STANDARD_02米道斯/`
3. PILOT_03: `/Users/winstonwei/CER-RAG/升级 CCD-3 个项目文件/CER_PILOT_STANDARD_03 永新-软件/`

### Run 1: Baseline (kimi-k2.6-code)

```bash
export CER_AUTHORING_MODEL_NAME=kimi-k2.6-code
# Run for each pilot project
python backend/scripts/run_cer_authoring.py --strict-v7 --project PILOT_01
python backend/scripts/run_cer_authoring.py --strict-v7 --project PILOT_02
python backend/scripts/run_cer_authoring.py --strict-v7 --project PILOT_03
# Collect: CER_draft.md, writer_remediation_gate_results.json, writer_remediation_qa_report.json
# Save to: ab_results/baseline_kimi_code/
```

### Run 2: Candidate A (deepseek-v4-pro)

```bash
export CER_AUTHORING_MODEL_NAME=deepseek-v4-pro
export CER_AUTHORING_MODEL_CER_WRITER=deepseek-v4-pro
python backend/scripts/run_cer_authoring.py --strict-v7 --project PILOT_01
python backend/scripts/run_cer_authoring.py --strict-v7 --project PILOT_02
python backend/scripts/run_cer_authoring.py --strict-v7 --project PILOT_03
# Save to: ab_results/candidate_a_deepseek/
```

### Run 3: Candidate B (kimi-api)

```bash
export CER_AUTHORING_MODEL_NAME=kimi-api
export CER_AUTHORING_MODEL_CER_WRITER=kimi-api
python backend/scripts/run_cer_authoring.py --strict-v7 --project PILOT_01
python backend/scripts/run_cer_authoring.py --strict-v7 --project PILOT_02
python backend/scripts/run_cer_authoring.py --strict-v7 --project PILOT_03
# Save to: ab_results/candidate_b_kimi_api/
```

### Run 4: Clean Fixture (minimal CER)

Create a clean minimal input with:
- device_domain: `cardiac_tissue_stabilizer`
- All IFU fields populated (no placeholders)
- INSUFFICIENT claims with honest wording

Run with each model candidate. Expected: Gates 1-5 all PASS.

### Scoring Template (To Fill In After Execution)

| Dimension | Weight | Baseline (kimi-code) | Candidate A (deepseek) | Candidate B (kimi-api) |
|-----------|--------|---------------------|----------------------|----------------------|
| Gate 1 — Domain consistency | 20% | [ ]/20 | [ ]/20 | [ ]/20 |
| Gate 2 — IFU source usage | 15% | [ ]/15 | [ ]/15 | [ ]/15 |
| Gate 3 — Evidence consistency | 20% | [ ]/20 | [ ]/20 | [ ]/20 |
| Gate 4 — Internal language | 10% | [ ]/10 | [ ]/10 | [ ]/10 |
| Gate 5 — QA composite | 10% | [ ]/10 | [ ]/10 | [ ]/10 |
| Section completeness | 10% | [ ]/10 | [ ]/10 | [ ]/10 |
| Professional expression | 10% | [ ]/10 | [ ]/10 | [ ]/10 |
| Repeatability (2-run) | 5% | [ ]/5 | [ ]/5 | [ ]/5 |
| **TOTAL** | **100%** | **[ ]** | **[ ]** | **[ ]** |

Scoring per dimension:
- Gate dimensions: PASS = full points, HARD_FAIL = 0
- Section completeness: % of required sections with non-placeholder content
- Professional expression: human reviewer 1-5 scale, scaled to 0-10
- Repeatability: % overlap between two runs on same input

### Acceptance Criteria

1. Candidate must beat baseline on ≥3 dimensions
2. NO dimension may regress below baseline
3. All 5 gates must PASS on clean fixture
4. MiniMax must NOT be used (already enforced by model_routing.py)
5. kimi-code can only be baseline, not final selection (unless A/B proves superiority and owner approves)
