# Phase 6 Evidence Foundation Upgrade Report

## Decision

`PHASE6_EVIDENCE_FOUNDATION_IMPLEMENTED_ACCEPTED / THREE_PROJECT_VALIDATION_COMPLETE`

Phase 6 is implemented at the evidence appraisal layer. It does not change the authoring graph, gate criteria, 1+6 agent structure, device identity arbitration, or baseline structural pipeline.

## Scope Control

- Changed layer: evidence appraisal / DUE suitability artifact consumption in `pipeline.py`.
- No graph changes.
- No G30/G33/G38 or other gate criteria changes.
- No agent changes.
- No device identity changes.
- CAL/HOLD projects used only for validation, not for rule training.

## Implementation Summary

The evidence appraisal flow now performs a stronger evidence-foundation pass before evidence rows are consumed by downstream artifacts:

1. Full-text-first appraisal basis:
   - uses `full_text`, `pdf_text`, `body`, extended source text, abstract, and raw records in priority order;
   - locked delta-only and final package sources are excluded from authoring-side appraisal.
2. Oxford / CEBM-style evidence level:
   - systematic review/meta-analysis -> Level 1;
   - randomized controlled trial -> Level 2;
   - controlled/prospective/registry evidence -> Level 3;
   - retrospective/single-arm/case-series evidence -> Level 4;
   - editorial/letter/comment -> Level 5.
3. Pivotal/supportive/background/excluded classification:
   - `pivotal` requires verified source, full-text availability, Level 1/2 design, sample-size/statistical extraction, and device/population/endpoint applicability;
   - quantitative but non-pivotal evidence remains `supportive` with `quantitative_support=true`, preserving the existing gate vocabulary;
   - editorial/letter/comment evidence is excluded from claim support.
4. Applicability scoring:
   - device applicability;
   - population applicability;
   - endpoint match;
   - intended-use match.
5. Extraction fields:
   - sample size;
   - follow-up;
   - statistical adequacy;
   - endpoint label;
   - limitations;
   - allowed conclusion strength.
6. DUE suitability table now consumes the richer appraisal results:
   - disposition;
   - evidence level;
   - sample size;
   - follow-up;
   - allowed conclusion strength;
   - quantitative-support marker.

## Important Boundary Fix During Validation

An initial implementation used a new evidence weight value `supportive-quantitative`. CAL-001 validation correctly exposed this as a G8 failure because gate criteria were not allowed to change. The implementation was corrected:

- allowed weight vocabulary remains unchanged;
- quantitative supportive evidence is represented with `weight=supportive` plus `quantitative_support=true`;
- pivotal evidence is restricted to true full-text-available sources, not abstract-only or extended-record sources.

## Files Changed

- `backend/packages/harness/deerflow/runtime/cer_authoring/pipeline.py`
- `backend/tests/test_cer_authoring_runtime.py`
- `docs/cer_authoring_phase6/PHASE6_EVIDENCE_FOUNDATION_UPGRADE_REPORT.md`

## Test Results

Command:

```bash
backend/.venv/bin/python -m pytest backend/tests/test_cer_authoring_runtime.py -q
```

Result after the V2.6 runtime fix:

```text
83 passed
```

New regression coverage:

- full-text RCT is appraised as Level 2 and can become pivotal;
- abstract-only editorial/commentary is Level 5 and excluded from pivotal/claim-support use;
- DUE suitability consumes evidence level, sample size, follow-up and conclusion-strength fields.

## V2.6 Runtime Blocker Fix

CAL-002 Phase 6 initially reproduced a startup/module-loading blocker with the native extension `pandas._libs.writers` (`writers.cpython-312-darwin.so`). The fix is runtime-only:

- preload `pandas._libs.writers` in the CLI before importing the DeerFlow authoring graph;
- keep a second preload guard in `agent_runtime.py` before subagent worker execution;
- record preload status in lead decisions and subagent invocation logs;
- bump default authoring baseline to `V2.6_PHASE6_EVIDENCE_WRITERS_FIX`.

This does not change graph topology, gates, agents, identity arbitration or evidence rules.

## Validation Runs

| Project | Run directory | Decision | Failed gates | Evidence distribution | Evidence levels |
| --- | --- | --- | ---: | --- | --- |
| CAL-001 | `artifacts/cer_cowork/CAL-001/authoring/PHASE6_20260511_CAL001B/deerflow_authoring` | `PASS_TO_DRAFT_DOCX` | 0 | excluded 3; background 2; supportive 5 | L1 3; L2 1; L3 1; L4 2; L5 3 |
| CAL-002 | `artifacts/cer_cowork/CAL-002/authoring/PHASE6_V26B_20260511_CAL002/deerflow_authoring` | `REWORK_REQUIRED` | 1 | background 1; supportive 9 | L2 1; L3 2; L4 5; L5 2 |
| CAL-003 | `artifacts/cer_cowork/CAL-003/authoring/PHASE6_20260511_CAL003/deerflow_authoring` | `REWORK_REQUIRED` | 1 | supportive 9; background 1 | L4 10 |

CAL-002 completed after the V2.6 native preload fix. Its remaining failed gate is G18 due to a masked/corrupted extraction artifact in `claim_ledger[3].claim_text`, not due to the writers native module blocker.

CAL-003 failed only G1e due to `ureteroscope` domain contamination in generated/profile text. That is outside Phase 6 scope.

## Semantic Re-Evaluation

Semantic delta was rerun for all three calibration projects with valid Phase 6/V2.6 baseline artifacts:

| Project | Delta output | Semantic rows | Low-confidence rows |
| --- | --- | ---: | ---: |
| CAL-001 | `artifacts/cer_cowork/CAL-001/authoring/PHASE6_20260511_CAL001B/delta_analysis` | 363 | 94 |
| CAL-002 | `artifacts/cer_cowork/CAL-002/authoring/PHASE6_V26B_20260511_CAL002/delta_analysis` | 500 | 99 |
| CAL-003 | `artifacts/cer_cowork/CAL-003/authoring/PHASE6_20260511_CAL003/delta_analysis` | 384 | 111 |

Three-case aggregation:

- `artifacts/cer_cowork/PHASE6_V26_20260511_THREE_CASE_SEMANTIC_AGGREGATION`
- semantic rows: 1,247;
- low-confidence rows: 304;
- automatic high-confidence rate: 75.6%;
- gold sections indexed: 6,381;
- gold citations indexed: 454.

The analyzer still correctly reports that fewer than four target projects are available, so this is not enough for final quality-level judgment.

## Known Limitations

- Phase 6 improves appraisal depth, but it does not add full-text retrieval. If full text is not present in the source/raw record, the system will not fabricate pivotal strength.
- CAL-002 still has a non-evidence G18 issue caused by corrupted/masked claim text.
- CAL-003 remains blocked by a domain-contamination gate unrelated to evidence appraisal.
- No 80-level or 85-90 capability judgment is claimed from three calibration projects alone; holdout validation is still required.

## Final Status

`PHASE6_EVIDENCE_FOUNDATION_IMPLEMENTED_ACCEPTED / THREE_PROJECT_VALIDATION_COMPLETE`
