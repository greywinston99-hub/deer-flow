# QA MODEL A/B RUNNER — Plan + Config Skeleton

> Claude Code | 2026-05-15 | Phase 3A

## Status

**MODEL_AB_RUNTIME_BLOCKED** — VS Code Claude Code has no LLM runtime access. Config skeleton and runner plan are ready. Gates 1-5 are DETERMINISTIC (not model-dependent) and already verified. QA model A/B applies to the QA reviewer agent that evaluates body content, not the deterministic gates.

## A/B Test Configuration

```python
QA_AB_CONFIG = {
    "agent": "qa-review",
    "candidates": {
        "candidate_a": {"model": "deepseek-v4-pro", "env": "CER_AUTHORING_MODEL_QA_REVIEW=deepseek-v4-pro"},
        "candidate_b": {"model": "kimi-api", "env": "CER_AUTHORING_MODEL_QA_REVIEW=kimi-api"},
    },
    "test_inputs": {
        "contaminated_fixtures": [
            "PILOT_01 Plasma Electrode CER draft (known contaminated)",
            "PILOT_02 Cardiac Stabilizer CER draft (known contaminated)",
        ],
        "clean_fixture": "Clean cardiac stabilizer minimal report (expected PASS)",
    },
    "fixed_config": {
        "prompts": "PROMPT_PACK_V1 — qa-review prompt (frozen Phase 2B)",
        "gates": "Gates 1-5 deterministic evaluation (NOT model-dependent)",
    },
}
```

## Scoring (4 Dimensions)

| Dimension | Weight | Candidate A | Candidate B |
|-----------|--------|-------------|-------------|
| False pass rate (contaminated→FAIL) | 35% | [ ] | [ ] |
| False fail rate (clean→PASS) | 35% | [ ] | [ ] |
| Finding specificity | 15% | [ ] | [ ] |
| Dimension coverage | 15% | [ ] | [ ] |
| **TOTAL** | **100%** | **[ ]** | **[ ]** |

## Acceptance

- False pass rate MUST be 0 (no contaminated report gets PASS)
- False fail rate MUST be 0 (clean report gets PASS)
- If both candidates pass these criteria, select based on finding specificity + dimension coverage

## Note on Deterministic Gates vs QA Agent

Gates 1-5 (domain, IFU, evidence, cleanliness, composite QA) are DETERMINISTIC code — they don't use an LLM. The QA reviewer (qa-review agent) evaluates body content quality (human reviewability, professional expression, section completeness). Model selection for QA only affects the QA reviewer agent, not the deterministic gates.

Current deterministic gates already:
- Correctly FAIL all contaminated reports
- Correctly PASS clean reports
- Do NOT depend on model choice

QA model selection is therefore OPTIONAL — the deterministic gates provide the core quality enforcement regardless of QA model.
