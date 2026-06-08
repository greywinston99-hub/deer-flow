# Phase 3.5C Calibration-Grade Semantic Delta Analyzer Hardening Report

Generated: 2026-05-10

## Decision

`PHASE3_5C_ACCEPTED_WITH_LIMITATIONS`

The existing `scripts/calibration_delta_analyzer.py` was upgraded in place. No second analyzer was created. The upgrade preserves the structural delta layer and adds calibration-grade semantic support, but the four-project rerun still shows a high low-confidence workload. The analyzer is now more explainable and better suited for calibration triage, but it is not yet fully calibration-grade without human-gate review and further entity normalization improvements.

## Scope Compliance

- Did not modify `cer_authoring_v1`, authoring graph, 1+6 agents, prompts, gates, `BASELINE_V2.3`, or existing AI baseline outputs.
- Did not run new authoring, repair, finalization, workflow retuning, or production use.
- Did not lower the 0.70 confidence threshold.
- Did not convert low-confidence items into confirmed AI CER defects.
- Reused the existing locked access, manifest, classification, and output-root model of `calibration_delta_analyzer.py`.

## Implemented Upgrades

1. Gold reference extraction hardening:
   - Added document role normalization, section index, table index, citation index, paragraph anchors, semantic zones, and extraction manifest.
   - Outputs:
     - `gold_reference_extraction_manifest.json`
     - `gold_reference_section_index.csv`
     - `gold_reference_table_index.csv`
     - `gold_reference_citation_index.csv`

2. Section-aware retrieval:
   - Added semantic zones for claims, SOTA, evidence selection, evidence appraisal, PMCF, benefit-risk, conclusion, and alignment.
   - Semantic rows now preserve source section, target section, retrieval basis, and retrieval confidence.

3. Entity normalization:
   - Added normalized entity extraction for device/clinical controlled terms, citations, benchmark labels, PMCF/PMS, RMF/IFU/GSPR, and capitalized candidate names.
   - Semantic rows now include baseline entities, gold entities, entity bridge, and normalized entity overlap.

4. Multi-stage confidence:
   - Added candidate retrieval, semantic equivalence, clinical materiality, NB relevance, and root-cause confidence.
   - The human-gate threshold remains unchanged.

5. NB rounds to final package linkage:
   - Added `nb_to_final_resolution_link_table.csv`.
   - Added `ai_gap_to_nb_finding_link_table.csv`.

6. Root-cause evidence chain:
   - Material semantic rows now include AI-side span, gold-side span, materiality reasoning, alternative-cause reasoning, and upgrade implication.
   - Cognitive gap attribution rows now include observed AI/gold/NB spans and root-cause confidence.

7. Low-confidence typing:
   - Added low-confidence categories:
     - `TEXT_EXTRACTION_GAP`
     - `SECTION_MAPPING_GAP`
     - `ENTITY_NORMALIZATION_GAP`
     - `SEMANTIC_MATCHING_GAP`
     - `TRUE_AMBIGUITY_HUMAN_GATE`
   - Added per-case and cross-project low-confidence reports.

8. Cross-project reliability reporting:
   - Added:
     - `cross_project_low_confidence_root_cause_report.md`
     - `cross_project_semantic_match_reliability_report.md`
     - `calibration_grade_readiness_report.md`
     - updated `next_upgrade_priority_ranking.csv`

## Four-Project Rerun Results

| Project | Locked files | Low-confidence | Gold sections | Gold tables | Gold citations | NB→Final links | AI Gap→NB links |
|---|---:|---:|---:|---:|---:|---:|---:|
| CAL-002 | 98 | 186 | 1084 | 0 | 92 | 140 | 164 |
| CAL-003 | 379 | 136 | 1362 | 0 | 48 | 97 | 121 |
| HOLD-001 | 76 | 163 | 1169 | 0 | 36 | 106 | 135 |
| HOLD-002 | 157 | 178 | 747 | 0 | 67 | 107 | 145 |

Cross-project totals:

- Usable semantic cases: 4 / 4
- Semantic rows: 1473
- Low-confidence rows: 663
- Automatic high-confidence rate: 55.0%
- Gold sections indexed: 4362
- Gold citations indexed: 243

## Low-Confidence Breakdown

| Type | Count | Percentage | Interpretation |
|---|---:|---:|---|
| `TEXT_EXTRACTION_GAP` | 17 | 2.6% | Limited text extraction still affects a small part of the gold reference. |
| `SECTION_MAPPING_GAP` | 0 | 0.0% | Section label fallback now avoids treating `unsectioned` as a hard section failure. |
| `ENTITY_NORMALIZATION_GAP` | 320 | 48.3% | Largest analyzer-upgrade target; device, endpoint, citation, risk and benchmark synonym expansion is still needed. |
| `SEMANTIC_MATCHING_GAP` | 20 | 3.0% | Retrieval/reranking issues remain limited. |
| `TRUE_AMBIGUITY_HUMAN_GATE` | 306 | 46.2% | These should stay in human gate and must not be converted into systemic defects automatically. |

## Key Finding

Phase 3.5C meaningfully improves explainability and auditability, but not enough to claim full calibration-grade automation. The analyzer can now say *why* an item is uncertain and whether uncertainty is caused by extraction, normalization, matching, or true ambiguity. However, the high `ENTITY_NORMALIZATION_GAP` and `TRUE_AMBIGUITY_HUMAN_GATE` counts mean next system-upgrade prioritization should be reviewed by CCD before using these outputs as definitive root-cause evidence.

## Generated Outputs

Per project:

- 9 semantic delta tables under `delta_analysis/semantic_delta/`
- `semantic_delta_manifest.json`
- `semantic_delta_case_summary.md`
- `low_confidence_review_queue.csv`
- `gold_reference_extraction_manifest.json`
- `gold_reference_section_index.csv`
- `gold_reference_table_index.csv`
- `gold_reference_citation_index.csv`
- `low_confidence_root_cause_breakdown.csv`
- `nb_to_final_resolution_link_table.csv`
- `ai_gap_to_nb_finding_link_table.csv`

Cross-project:

- `artifacts/cer_cowork/phase3_5c_semantic_delta_aggregation/cross_project_semantic_gap_aggregation_report.md`
- `artifacts/cer_cowork/phase3_5c_semantic_delta_aggregation/cross_project_gap_frequency_matrix.csv`
- `artifacts/cer_cowork/phase3_5c_semantic_delta_aggregation/cross_project_low_confidence_root_cause_report.md`
- `artifacts/cer_cowork/phase3_5c_semantic_delta_aggregation/cross_project_semantic_match_reliability_report.md`
- `artifacts/cer_cowork/phase3_5c_semantic_delta_aggregation/calibration_grade_readiness_report.md`
- `artifacts/cer_cowork/phase3_5c_semantic_delta_aggregation/next_upgrade_priority_ranking.csv`

## Tests

Passed:

```text
backend/.venv/bin/python -m py_compile scripts/calibration_delta_analyzer.py
backend/.venv/bin/python -m pytest backend/tests/test_calibration_delta_analyzer.py -q
3 passed
backend/.venv/bin/python -m pytest backend/tests/test_calibration_delta_analyzer.py backend/tests/test_cer_cowork_supervisor.py -q
13 passed
```

## Limitations

- Gold table extraction remains weak in the current deterministic extractor (`Gold tables = 0` across four projects), likely because many source tables are not recoverable from the current extracted paragraph stream.
- The analyzer still requires human gate for true ambiguity and for deciding whether low-confidence semantic differences can be generalized into system rules.
- The automatic high-confidence rate is 55.0%, which is useful for triage but not enough for unrestricted calibration-grade acceptance.

## Next Recommended Analyzer Upgrade

Before using semantic deltas as a definitive rule-upgrade basis, improve:

1. Entity normalization for device type, endpoint, adverse event, benchmark, citation and PMCF activity synonyms.
2. Table extraction from DOCX/PDF final packages, especially CER benchmark/evidence/RMF/GSPR tables.
3. Section-aware retrieval reranking for SOTA benchmark candidates, so literature-method sections do not out-rank actual benchmark sections.

Final label: `PHASE3_5C_ACCEPTED_WITH_LIMITATIONS`
