# MODEL ROUTING POLICY — CER Authoring V1.0

> Claude Code | 2026-05-15 | Phase 2C

## Policy

1. The CER Authoring runtime uses a single model for all agents (parent model inheritance).
2. Model is set via `CER_AUTHORING_MODEL_NAME` environment variable or `state["model_name"]`.
3. All subagent configs use `model="inherit"` — no per-agent model routing.
4. Model switch is a configuration change, not a code change.
5. Any model switch must be followed by full regression (≥298 tests) before production use.

## Default Model

- Provider: Local provider router
- Model: DeepSeek V4 Pro (or as configured via CER_AUTHORING_MODEL_NAME)
- Temperature: Pipeline-controlled (typically 0 for Writer, 0.1 for evidence tasks)

## Model Requirements

The Writer model must:
1. Follow complex multi-section medical device regulatory instructions
2. Obey domain-specific template boundaries (do not write cross-domain clinical prose)
3. Respect claim_support_matrix and writer_conclusion_constraints
4. Produce gate-compatible outputs (no internal system language leakage)
5. Generate source-grounded device descriptions from IFU data

## Change Procedure

1. Document proposed model change with rationale
2. Set CER_AUTHORING_MODEL_NAME to candidate model
3. Run full regression (≥298 tests)
4. Run gates against known contaminated fixtures (must still HARD FAIL)
5. Run human reviewability rubric on regenerated outputs
6. Update this document if model is changed permanently
