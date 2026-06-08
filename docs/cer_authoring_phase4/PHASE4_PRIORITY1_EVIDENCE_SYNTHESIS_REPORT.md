# Phase 4 Priority 1 Evidence Synthesis Report

## Scope

Priority 1 addresses COG-003 across calibration projects: the CER writer was too close to article-by-article summaries and did not consistently synthesize the evidence body across claims, endpoints, benchmarks and benefit-risk conclusions.

This patch adds a deterministic `writer_synthesis` layer before CER section 4 writing.

## Implemented

- Added `build_cross_evidence_synthesis()` as the deterministic writer-synthesis carrier.
- Added graph stage `writer_synthesis` between `evidence_review_gates` and `cer_writing`.
- Added structured outputs:
  - `cross_evidence_synthesis_table`
  - `cross_evidence_synthesis_narratives`
  - `writer_synthesis_trace`
- Added workbook and XLSX export support for the three new artifacts.
- Updated section 4 writer output so §4.5 and §4.7 consume cross-evidence synthesis before article-level appraisal detail.
- Updated writer-stage state summarization so the writer trace can see `cross_evidence_synthesis_table`.

## Boundaries Kept

- G30/G33/G38 gate criteria were not changed.
- 1+6 authoring agents and prompts were not changed.
- Phase 0.6 identity arbitration was not changed.
- Baseline versioning and baseline artifacts were not modified.

## Writer Rule

CER §4 must first synthesize evidence by claim / endpoint / SOTA benchmark:

```text
Claim
→ Endpoint / Benchmark
→ Evidence body
→ Weight distribution
→ Sample size / follow-up / result synthesis
→ Consistency and limitation synthesis
→ Allowed conclusion strength
→ §4.5 and §4.7 narrative
```

Article-level summaries remain available, but they no longer serve as the primary reasoning structure.

## Verification

Executed:

```bash
backend/.venv/bin/python -m py_compile backend/packages/harness/deerflow/runtime/cer_authoring/pipeline.py backend/packages/harness/deerflow/runtime/cer_authoring/state.py backend/packages/harness/deerflow/runtime/cer_authoring/artifacts.py backend/packages/harness/deerflow/runtime/cer_authoring/graph.py
```

Result: pass.

Executed:

```bash
backend/.venv/bin/python -m pytest backend/tests/test_cer_authoring_runtime.py -k "phase4_1 or phase2_3 or phase2_1" -q
```

Result: `9 passed, 34 deselected`.

Executed:

```bash
backend/.venv/bin/python -m pytest backend/tests/test_cer_authoring_runtime.py -q
```

Result: `43 passed`.

## Changed Files

- `backend/packages/harness/deerflow/runtime/cer_authoring/pipeline.py`
- `backend/packages/harness/deerflow/runtime/cer_authoring/graph.py`
- `backend/packages/harness/deerflow/runtime/cer_authoring/state.py`
- `backend/packages/harness/deerflow/runtime/cer_authoring/artifacts.py`
- `backend/packages/harness/deerflow/runtime/cer_authoring/agent_runtime.py`
- `backend/tests/test_cer_authoring_runtime.py`
- `docs/cer_authoring_phase4/PHASE4_PRIORITY1_EVIDENCE_SYNTHESIS_REPORT.md`

## CCD Decision

`PHASE4_PRIORITY1_READY_FOR_CCD_ACCEPTANCE`
