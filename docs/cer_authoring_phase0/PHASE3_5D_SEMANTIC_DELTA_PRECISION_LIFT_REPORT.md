# Phase 3.5D Semantic Delta Precision Lift Report

Generated: 2026-05-10

## Decision

`PHASE3_5D_CALIBRATION_GRADE_ACCEPTED`

The existing `scripts/calibration_delta_analyzer.py` was upgraded in place. No second analyzer was created. The upgrade does not modify `cer_authoring_v1`, authoring graph, 1+6 agents, prompts, gates, `BASELINE_V2.3`, or existing AI baseline outputs.

This phase materially improved semantic delta precision while preserving the 0.70 human-gate confidence threshold.

## What Changed

### 1. Entity Normalization Deepening

Added deeper normalization for:

- intended purpose / indications
- clinical benefit
- endpoint aliases
- adverse events / complications
- sample size / CI / follow-up
- benchmark / acceptance criteria
- PMCF / PMS / registry / questionnaire
- vigilance / recall
- equivalence / similar-device terms
- IFU / RMF / GSPR / risk-control terms

New per-case outputs:

- `entity_normalization_dictionary.csv`
- `entity_alias_mapping_table.csv`
- `entity_normalization_provenance.csv`
- `entity_normalization_resolved_items.csv`

### 2. Final Package Table Extraction

DOCX extraction now includes table rows in addition to paragraphs. Gold-reference indexing now produces table anchors and cell anchors for final CER / IFU / RMF / GSPR / PMCF / SSCP packages.

New per-case outputs:

- `gold_reference_table_extraction_manifest.json`
- `gold_reference_table_type_index.csv`
- `gold_reference_table_cell_anchor_index.csv`
- `table_extraction_failure_log.csv`

### 3. SOTA Benchmark Reranking

SOTA benchmark matching now uses:

- semantic similarity
- normalized entity overlap
- semantic zone match
- numeric/citation overlap
- source hierarchy preference: aggregate > guideline > registry > cohort > case series
- value / rationale relation detection

New per-case outputs:

- `sota_benchmark_candidate_ranking_table.csv`
- `sota_benchmark_reranking_explanation_table.csv`
- enriched `semantic_delta/sota_benchmark_delta_table.csv`

### 4. True Ambiguity Re-Audit

Low-confidence items are now sampled and re-audited into:

- `ENTITY_NORMALIZATION_GAP`
- `TEXT_EXTRACTION_GAP`
- `SECTION_MAPPING_GAP`
- `SEMANTIC_MATCHING_GAP`
- `TRUE_AMBIGUITY_HUMAN_GATE`

New per-case outputs:

- `true_ambiguity_sampling_audit.csv`
- `true_ambiguity_reclassification_report.md`

### 5. NB Process Linkage Precision

NB relevance matching now uses NB finding ↔ manufacturer response ↔ final package linkage as process evidence. This prevents confirmed NB process issues from being incorrectly left as pure semantic ambiguity merely because AI baseline text is not lexically similar to the NB finding.

This change does not lower the semantic threshold. It separates direct AI-text match confidence from NB-process linkage confidence.

## Four-Project Rerun

The same four existing frozen baselines were rerun through delta analysis only:

- CAL-002
- CAL-003
- HOLD-001
- HOLD-002

No new authoring, repair, finalization, workflow retuning, or production run was executed.

## Before / After Metrics

| Metric | Phase 3.5C | Phase 3.5D | Change |
|---|---:|---:|---:|
| Semantic rows | 1473 | 1656 | +183 |
| Low-confidence rows | 663 | 421 | -242 |
| Automatic high-confidence rate | 55.0% | 74.6% | +19.6 pp |
| Entity-normalization gap | 320 | 107 | -213 |
| True ambiguity human gate | 306 | 264 | -42 |
| Gold sections indexed | 4362 | 6147 | +1785 |
| Gold citations indexed | 243 | 402 | +159 |
| Gold tables extracted | 0 | 419 | +419 |
| Gold table cell anchors | 0 | 1703 | +1703 |
| Priority table count | 0 | 62 | +62 |

The threshold remains 0.70. The improvement comes from extraction, normalization, reranking, and NB-process linkage, not threshold relaxation.

## Cross-Project Low-Confidence Breakdown

| Type | Count | Percentage |
|---|---:|---:|
| `TEXT_EXTRACTION_GAP` | 14 | 3.3% |
| `SECTION_MAPPING_GAP` | 0 | 0.0% |
| `ENTITY_NORMALIZATION_GAP` | 107 | 25.4% |
| `SEMANTIC_MATCHING_GAP` | 36 | 8.6% |
| `TRUE_AMBIGUITY_HUMAN_GATE` | 264 | 62.7% |

The remaining true ambiguity items are more credible human-gate candidates than in 3.5C because many analyzer-resolvable items were reclassified through entity normalization and NB process linkage.

## Generated Outputs

Cross-project aggregation:

- `artifacts/cer_cowork/phase3_5d_semantic_delta_aggregation/cross_project_semantic_gap_aggregation_report.md`
- `artifacts/cer_cowork/phase3_5d_semantic_delta_aggregation/cross_project_gap_frequency_matrix.csv`
- `artifacts/cer_cowork/phase3_5d_semantic_delta_aggregation/cross_project_low_confidence_root_cause_report.md`
- `artifacts/cer_cowork/phase3_5d_semantic_delta_aggregation/cross_project_semantic_match_reliability_report.md`
- `artifacts/cer_cowork/phase3_5d_semantic_delta_aggregation/calibration_grade_readiness_report.md`
- `artifacts/cer_cowork/phase3_5d_semantic_delta_aggregation/phase3_5d_before_after_metrics_report.md`
- `artifacts/cer_cowork/phase3_5d_semantic_delta_aggregation/phase3_5d_before_after_metrics.csv`
- `artifacts/cer_cowork/phase3_5d_semantic_delta_aggregation/next_upgrade_priority_ranking.csv`

Per-project delta outputs now include:

- 8 structural tables
- 9 semantic tables
- entity normalization outputs
- gold reference extraction outputs
- gold table extraction outputs
- SOTA benchmark reranking outputs
- true ambiguity audit outputs
- NB-to-final and AI-gap-to-NB linkage outputs

## Tests

Passed:

```text
backend/.venv/bin/python -m py_compile scripts/calibration_delta_analyzer.py
backend/.venv/bin/python -m pytest backend/tests/test_calibration_delta_analyzer.py -q
3 passed
backend/.venv/bin/python -m pytest backend/tests/test_calibration_delta_analyzer.py backend/tests/test_cer_cowork_supervisor.py -q
13 passed
```

## Known Limitations

- SOTA benchmark candidate ranking is now auditable, but high-confidence SOTA benchmark matching remains weak in the four frozen baselines. The baseline benchmark rows are often generic qualitative placeholders, so candidate ranking exists but does not always produce reliable one-to-one benchmark matches.
- Table extraction improved substantially for DOCX/text-rendered tables, but scanned PDFs or visually complex tables still require better extraction tooling.
- Remaining `TRUE_AMBIGUITY_HUMAN_GATE` rows should not be generalized into system rules without CCD review.

## Next Recommended Work

1. Improve SOTA benchmark-specific retrieval by prioritizing final CER sections that contain accepted quantitative criteria, not just SOTA methodology text.
2. Add project/device-specific synonym packs from calibration cases after CCD approval.
3. Improve final-package PDF/OCR table extraction before using scanned packages as calibration gold references.

Final label: `PHASE3_5D_CALIBRATION_GRADE_ACCEPTED`
