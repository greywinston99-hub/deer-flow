# WRITER MODEL A/B RUNNER — Plan + Config Skeleton

> Claude Code | 2026-05-15 | Phase 3A

## Status

**MODEL_AB_RUNTIME_BLOCKED** — VS Code Claude Code has no LLM runtime access. A/B execution requires DeerFlow runtime environment (`run_cer_authoring.py --strict-v7`). Config skeleton and runner plan are ready.

## A/B Test Configuration

```python
WRITER_AB_CONFIG = {
    "agent": "cer-writer",
    "candidates": {
        "current_baseline": {"model": "kimi-k2.6-code", "env": "CER_AUTHORING_MODEL_CER_WRITER=kimi-k2.6-code"},
        "candidate_a": {"model": "deepseek-v4-pro", "env": "CER_AUTHORING_MODEL_CER_WRITER=deepseek-v4-pro"},
        "candidate_b": {"model": "kimi-api", "env": "CER_AUTHORING_MODEL_CER_WRITER=kimi-api"},
    },
    "fixed_config": {
        "project": "PILOT_01 (Plasma Electrode) or PILOT_02 (Cardiac Stabilizer)",
        "prompts": "PROMPT_PACK_V1 (frozen Phase 2B)",
        "templates": "Domain-specific template (Phase 2A)",
        "gates": "Gates 1-5 active (Phase 1+2)",
        "claim_support_matrix": "From project 02_AI_BASELINE_OUTPUT_FREEZE",
    },
}
```

## Execution Procedure

```bash
# Run 1: Current baseline (kimi-k2.6-code)
export CER_AUTHORING_MODEL_CER_WRITER=kimi-k2.6-code
python run_cer_authoring.py --strict-v7 --project PILOT_01

# Run 2: Candidate A (deepseek-v4-pro)
export CER_AUTHORING_MODEL_CER_WRITER=deepseek-v4-pro
python run_cer_authoring.py --strict-v7 --project PILOT_01

# Run 3: Candidate B (kimi-api)
export CER_AUTHORING_MODEL_CER_WRITER=kimi-api
python run_cer_authoring.py --strict-v7 --project PILOT_01
```

## Scoring (8 Dimensions)

| Dimension | Weight | Baseline | Candidate A | Candidate B |
|-----------|--------|----------|-------------|-------------|
| Domain consistency (Gate 1) | 20% | [ ] | [ ] | [ ] |
| Evidence consistency (Gate 3) | 20% | [ ] | [ ] | [ ] |
| IFU source usage (Gate 2) | 15% | [ ] | [ ] | [ ] |
| Internal language (Gate 4) | 10% | [ ] | [ ] | [ ] |
| Section completeness | 10% | [ ] | [ ] | [ ] |
| Professional expression | 10% | [ ] | [ ] | [ ] |
| Gate pass rate | 10% | [ ] | [ ] | [ ] |
| Repeatability | 5% | [ ] | [ ] | [ ] |
| **TOTAL** | **100%** | **[ ]** | **[ ]** | **[ ]** |

## Acceptance

Best model selected based on aggregate score. Model switch only if:
1. Candidate outperforms current on ≥3 dimensions
2. NO dimension regresses below current baseline
3. All 5 gates pass

## Current Recommendation (Pending A/B)

DeepSeek V4 Pro as Writer model. Rationale: strongest medical writing candidate, best domain consistency in preliminary assessment, kimi-code known to produce template reuse and internal language leakage.
