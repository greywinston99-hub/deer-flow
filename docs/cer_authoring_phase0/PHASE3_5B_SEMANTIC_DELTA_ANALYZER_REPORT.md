# Phase 3.5B Semantic Delta Analyzer Report

## Decision

`PHASE3_5B_ACCEPTED_WITH_LIMITATIONS`

The existing `scripts/calibration_delta_analyzer.py` was upgraded in place. It remains the single approved post-baseline calibration entry and continues to enforce locked-folder access control. No parallel analyzer was created.

## Scope Control

The patch did not modify:

- `cer_authoring_v1`
- authoring graph
- 1+6 authoring agents
- authoring prompts
- G0-G38 gate criteria
- frozen baseline artifacts
- repair or finalization workflow

## Implemented

The analyzer now produces both layers:

1. Structural delta layer
   - Existing 8 delta tables are preserved.
   - Existing locked access log, role classification, manifest and pilot report are preserved.

2. Semantic delta layer
   - `semantic_delta/claim_semantic_alignment_table.csv`
   - `semantic_delta/evidence_correspondence_table.csv`
   - `semantic_delta/sota_benchmark_delta_table.csv`
   - `semantic_delta/evidence_appraisal_delta_table.csv`
   - `semantic_delta/pmcf_boundary_delta_table.csv`
   - `semantic_delta/benefit_risk_reasoning_delta_table.csv`
   - `semantic_delta/cross_document_alignment_delta_table.csv`
   - `semantic_delta/nb_relevance_delta_table.csv`
   - `semantic_delta/cognitive_gap_attribution_table.csv`
   - `semantic_delta_manifest.json`
   - `semantic_delta_case_summary.md`
   - `low_confidence_review_queue.csv`

Semantic tables are written under `delta_analysis/semantic_delta/` to avoid filename collisions on case-insensitive macOS filesystems, where `SOTA_BENCHMARK_DELTA_TABLE.csv` and `sota_benchmark_delta_table.csv` cannot coexist in the same directory.

## Four-Project Execution

| Project | Output directory | Status | Low-confidence queue |
|---|---|---|---:|
| CAL-002 | `artifacts/cer_cowork/CAL-002/authoring/20260509T125921Z-authoring/delta_analysis` | `SEMANTIC_DELTA_COMPLETE` | 186 |
| CAL-003 | `artifacts/cer_cowork/CAL-003/authoring/20260509T171636Z-authoring/delta_analysis` | `SEMANTIC_DELTA_COMPLETE` | 137 |
| HOLD-001 | `artifacts/cer_cowork/HOLD-001/authoring/20260510T031719Z-authoring/delta_analysis` | `SEMANTIC_DELTA_COMPLETE` | 163 |
| HOLD-002 | `artifacts/cer_cowork/HOLD-002/authoring/20260510T033129Z-authoring/delta_analysis` | `SEMANTIC_DELTA_COMPLETE` | 178 |

Cross-project outputs:

- `artifacts/cer_cowork/phase3_5b_semantic_delta_aggregation/cross_project_semantic_gap_aggregation_report.md`
- `artifacts/cer_cowork/phase3_5b_semantic_delta_aggregation/cross_project_gap_frequency_matrix.csv`
- `artifacts/cer_cowork/phase3_5b_semantic_delta_aggregation/semantic_quality_level_preliminary_judgment.md`
- `artifacts/cer_cowork/phase3_5b_semantic_delta_aggregation/next_upgrade_priority_ranking.csv`
- `artifacts/cer_cowork/phase3_5b_semantic_delta_aggregation/cross_project_semantic_aggregation_manifest.json`

## Key Finding

The analyzer can now generate semantic correspondence candidates and low-confidence human gates, but the current gold-reference text extraction and heuristic semantic matching produce a high low-confidence load across all four projects. The analyzer therefore correctly refuses to convert most candidate differences into confirmed systemic gaps.

Preliminary quality-level judgment from the aggregation:

> Current semantic evidence supports approximately a 70-point human-reviewable draft capability, but not a stable 80-point NB-ready draft.

## Known Limitations

1. The semantic matcher is deterministic and conservative; it uses extracted text, token overlap and confidence thresholds, not an LLM judge.
2. Locked final packages include mixed DOC/DOCX/XLSX/PDF material. Unsupported or weak text extraction reduces match confidence.
3. Low-confidence items are routed to `low_confidence_review_queue.csv` and are not counted as confirmed systemic gaps.
4. The current aggregation therefore identifies the next bottleneck as semantic extraction/matching confidence, not yet a clean ranked list of SOTA/Evidence/Writer rule defects.
5. Holdout outputs were evaluated only; no authoring tuning was performed from holdout results.

## Tests

```text
backend/.venv/bin/python -m pytest backend/tests/test_calibration_delta_analyzer.py -q
3 passed

backend/.venv/bin/python -m pytest backend/tests/test_calibration_delta_analyzer.py backend/tests/test_cer_cowork_supervisor.py -q
13 passed

backend/.venv/bin/python -m compileall -q scripts/calibration_delta_analyzer.py
PASS
```

## Next Upgrade Priority

Before treating semantic deltas as calibration-grade system root causes, improve semantic match confidence by adding one of:

1. richer final CER/full-package text extraction for DOC/PDF/XLSX;
2. LLM-assisted semantic adjudication inside the analyzer boundary;
3. project-specific gold artifact role mapping to separate final CER, final IFU, final RMF, final GSPR, and final PMCF before semantic matching.

These are analyzer-layer upgrades only and do not require changing `cer_authoring_v1`.
