# MODEL ROUTING POLICY V1.1 — DRAFT (Post A/B)

> Claude Code | 2026-05-15 | DRAFT — subject to A/B results + owner approval

## Changes from V1.0

| Change | V1.0 | V1.1 Draft |
|--------|------|-----------|
| Writer model | deepseek-v4-pro (provisional) | **[A/B RESULT PENDING]** |
| QA model | deepseek-v4-pro (provisional) | **[A/B RESULT PENDING]** |
| Evidence model status | deepseek-v4-pro (provisional) | deepseek-v4-pro (recommended, A/B deferred) |

## Routing Table V1.1 Draft

| Agent | Task | V1.1 Model | Status |
|-------|------|-----------|--------|
| intake-profile-claim | Extraction | kimi-k2.6-code | CONFIRMED |
| methodology-sota | Evidence Reasoning | deepseek-v4-pro | RECOMMENDED |
| evidence | Evidence Reasoning | deepseek-v4-pro | RECOMMENDED |
| cer-writer | CER Writer | **[OWNER DECISION]** | A/B PENDING |
| qa-review | QA Reviewer | **[OWNER DECISION]** | A/B PENDING |
| risk-equivalence-gspr | Risk/Equivalence | kimi-k2.6-code | CONFIRMED |
| cer-authoring-lead-agent | Controller | kimi-k2.6-code | CONFIRMED |

## What Changes When A/B Completes

1. Writer model: Fill in from WRITER_MODEL_AB_RUNTIME_RESULT.md scoring table
2. QA model: Fill in from QA_MODEL_AB_RUNTIME_RESULT.md scoring table
3. Evidence model: Can follow Writer selection or remain deepseek-v4-pro
4. Update `model_routing.py` ROUTING_POLICY_V1 default_model entries
5. Update MODEL_ROUTING_POLICY_V1.md change log

## What Does NOT Change

- kimi-k2.6-code boundaries: FORBIDDEN for Writer, QA, Evidence Reasoning
- minimax boundaries: FORBIDDEN for Writer, QA, Evidence Reasoning, Risk
- Extraction models: kimi-k2.6-code confirmed
- Deterministic gates: Gates 1-5 unchanged
- Gate semantics: unchanged
- Prompt content: unchanged
- Template content: unchanged
- EI Core: unchanged

## Activation Procedure

After owner approves V1.1:
1. Update `model_routing.py` ROUTING_POLICY_V1 default_model for cer-writer and qa-review
2. Set env vars in DeerFlow runtime: `CER_AUTHORING_MODEL_CER_WRITER`, `CER_AUTHORING_MODEL_QA_REVIEW`
3. Run full regression (≥323 tests)
4. Verify contaminated fixtures still HARD FAIL
5. Verify clean fixture PASS
6. Tag as MODEL_ROUTING_POLICY_V1_1_APPROVED

## Rollback

If regression detected: revert ROUTING_POLICY_V1 to V1.0 entries. Model routing is config, not code. No code rollback needed.

---

*DRAFT — DO NOT ACTIVATE WITHOUT A/B RESULTS + OWNER APPROVAL*
