# BATCH 5.7 G42 Semantic Claim-Evidence Routing Report

## Decision

`G42_SEMANTIC_CLAIM_EVIDENCE_ROUTING_READY_FOR_RECOVERY_RERUN`

This patch upgrades G42 from a retrieval-only evidence sufficiency gate into a semantic claim-evidence reasoning gate with failure-pattern-specific repair routing. It does not resume pilot validation and does not declare CAL/HOLD regression passed.

## Scope

Changed files:

- `backend/packages/harness/deerflow/runtime/cer_authoring/pipeline.py`
- `backend/packages/harness/deerflow/runtime/cer_authoring/gates.py`
- `backend/packages/harness/deerflow/runtime/cer_authoring/graph.py`
- `backend/packages/harness/deerflow/runtime/cer_authoring/state.py`
- `backend/packages/harness/deerflow/runtime/cer_authoring/artifacts.py`
- `backend/tests/test_cer_authoring_runtime.py`

No agents, prompts, MCP tools, model configuration, or unrelated gate criteria were changed.

## Implemented

1. Added pre-G42 claim-evidence candidate linking.
2. Replaced rigid one-to-one benchmark-to-evidence lookup with a ranked candidate pool.
3. Added claim support type classification, including non-literature support routes for IFU/RMF/GSPR/PMS/test-style claims.
4. Added semantic claim-evidence support evaluation using claim intent, clinical context, source appropriateness, endpoint/outcome family, applicability, directness, and full-text status.
5. Updated evidence weighting so low endpoint match can be promoted only when semantic support and source appropriateness justify it. Full text alone does not promote evidence.
6. Added endpoint/outcome family mapping.
7. Added explicit G42 failure patterns and repair routes.
8. Added G42 artifacts:
   - `pre_g42_claim_evidence_candidate_matrix.xlsx`
   - `claim_support_type_classifier.xlsx`
   - `semantic_claim_evidence_candidate_matrix.xlsx`
   - `g42_failure_pattern_report.xlsx`
   - `g42_repair_routing_trace.xlsx`

## CAL-001 Validation Run

Run:

`artifacts/cer_cowork/CAL-001/authoring/BATCH5_7_20260512_CAL001/deerflow_authoring`

Summary:

| Metric | Result |
| --- | ---: |
| final gate decision | `PASS_TO_DRAFT_DOCX` |
| failed gate count | 0 |
| claims | 11 |
| evidence items | 14 |
| pre-G42 matrix rows | 11 |
| minimum candidates per claim | 15 |
| maximum candidates per claim | 15 |
| G42 claim statuses | 11 PASS / 0 REWORK / 0 BLOCKED |

Observed behavior:

- Every claim received a candidate pool, not a single benchmark-linked item.
- IFU/PMS/similar-device source support was represented as non-literature source candidates where appropriate.
- G42 did not route all failures to `sota_search`; in this run no G42 failures remained.
- Writer was invoked only after G42/G46 pass and the final gate was clean.

## Tests

Command:

```bash
backend/.venv/bin/python -m pytest backend/tests/test_cer_authoring_runtime.py -q
```

Result:

`121 passed in 7.14s`

## Boundaries Preserved

- No G42 sufficiency weakening.
- No full-text automatic support promotion.
- No Writer forcing.
- No pilot resume.
- No CAL/HOLD regression success claim.

