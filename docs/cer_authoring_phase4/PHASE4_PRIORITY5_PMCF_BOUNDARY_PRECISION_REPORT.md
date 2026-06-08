# Phase 4A P5 — PMCF Boundary Precision

Decision: `IMPLEMENTED_ACCEPTED`

Effectiveness status: `EFFECTIVENESS_PENDING`

Phase 4A status after P5: `IMPLEMENTED_ACCEPTED / EFFECTIVENESS_PENDING`

## Scope

This patch addresses COG-004 as a weakened-but-retained material gap affecting CAL-001 and CAL-003. It is implemented at the rule layer only.

No changes were made to:

- graph structure;
- G30/G33/G38 or other gate criteria;
- 1+6 authoring agents;
- prompts;
- Phase 0.6 identity arbitration.

## Implemented Rule

The system now emits a `pmcf_boundary_decision_log` and carries the decision into the Claim-Evidence-Benefit-Risk writer spine.

Each gap is assessed across three separate axes:

1. `pre_submission_required`
   - whether the gap must be resolved before NB submission or before signature-level claim wording;
   - with `pre_submission_rationale`.

2. `pmcf_allowed`
   - whether PMCF is a valid control for this gap;
   - distinguishes residual uncertainty tracking from impermissible PMCF substitution for missing pre-submission evidence;
   - with `pmcf_allowed_rationale`.

3. `claim_downgrade_required`
   - whether claim wording must be downgraded, qualified, held or removed;
   - with `claim_downgrade_rationale`.

The decisions intentionally avoid simple yes/no labels. They use auditable regulatory-action wording such as:

- `required_before_nb_submission_for_signature_level_or_strong_claim`
- `allowed_only_for_residual_uncertainty_after_pre_submission_evidence_or_claim_downgrade`
- `not_allowed_as_primary_resolution`
- `downgrade_to_partial_support_or_remove_claim_until_evidence_resolved`

## Output Artifacts

Added:

- `pmcf_boundary_decision_log` in the authoring workbook
- `pmcf_boundary_decision_log.xlsx`
- PMCF boundary section inside `gap_pmcf_recommendations.docx`
- PMCF boundary fields in `claim_evidence_matrix`
- PMCF boundary fields in `benefit_risk_ledger`
- PMCF boundary table in Annex I

## Boundary Logic

Core clinical evidence gaps:

- must be resolved pre-submission for strong/signature-level claims or the claim must be downgraded;
- PMCF is allowed only for residual uncertainty after evidence is added or claim strength is reduced.

RMF/GSPR gaps:

- cannot be solved primarily by PMCF;
- block unqualified final conformity and favourable benefit-risk wording.

Evidence extraction precision gaps:

- require full-text/source extraction before quantitative benchmark or comparative wording;
- PMCF is not the primary fix.

PMS/PMCF data gaps:

- may be controlled with a defined PMCF/PMS plan, timetable and acceptance criteria when the project is pre-market/no-sales or when the question is genuinely post-market/residual.

## Tests

Commands executed:

```bash
backend/.venv/bin/python -m py_compile backend/packages/harness/deerflow/runtime/cer_authoring/pipeline.py backend/packages/harness/deerflow/runtime/cer_authoring/state.py backend/packages/harness/deerflow/runtime/cer_authoring/artifacts.py
backend/.venv/bin/python -m pytest backend/tests/test_cer_authoring_runtime.py -k "phase4_5" -q
backend/.venv/bin/python -m pytest backend/tests/test_cer_authoring_runtime.py -k "phase4_5 or phase4_4 or phase4_3 or phase4_2 or phase4_1" -q
backend/.venv/bin/python -m pytest backend/tests/test_cer_authoring_runtime.py -q
```

Results:

- Phase 4A P5 targeted tests: `4 passed, 51 deselected`
- Phase 4A P4/P5 targeted runtime tests after selector-ordering hardening: `9 passed, 47 deselected`
- CER authoring runtime tests after P5: `56 passed`

## Acceptance

`IMPLEMENTED_ACCEPTED`

Effectiveness remains pending until PHASE4B unified rerun and Semantic Delta validation confirm whether COG-004 is removed or downgraded for CAL-001 and CAL-003.
