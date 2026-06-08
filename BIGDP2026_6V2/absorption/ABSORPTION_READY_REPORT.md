# BIGDP2026.6V_2 — Absorption Ready Report

**Date:** 2026-06-08 | **Assets:** 17 CSVs, 726 rows | **Score:** 75/100

---

## Absorption Status

| DC | Asset Rows | Absorbed Into | Closure Level |
|:---|:---:|:---|:---|
| DC-1/2 | 51 | `_validate_search_audit_trail` (gates.py) | HEURISTIC_VALIDATION |
| DC-3 | 46 | `_validate_screening_exclusions` (gates.py) | HEURISTIC_VALIDATION |
| DC-4 | 70 | `_node_extract_clinical_facts` (graph.py) — PMID anchor | SYNTHETIC_FIXTURE_ONLY |
| DC-5 | 121 | `_validate_fulltext_policy` (gates.py) | HEURISTIC_VALIDATION |
| DC-6 | 90 | `ENDPOINT_CLASSIFICATION_TAXONOMY` (expert_rule_loader.py) | HEURISTIC_VALIDATION |
| DC-7 | 54 | `COMPARATOR_EXPECTED_DIRECTNESS_RATIO` (expert_rule_loader.py) | SYNTHETIC_FIXTURE_ONLY |
| DC-8/9 | 18+18 | `TestSOTAAccountingConsistency` (test_batch_d) | HEURISTIC_VALIDATION |
| DC-10 | 47 | `_validate_denominator_consistency` (gates.py) | HEURISTIC_VALIDATION |
| DC-11 | 90 | `TestWriterSemanticQA` (test_batch_d) + `cer_package_validator.py` | DERIVED_VALIDATION |

## Key Absorbed Patterns

1. **DC-6**: ALL non-AE endpoints share `common_misclassification="adverse_event"` — confirmed the dominant error pattern
2. **DC-7**: 78% direct / 22% fallback comparator distribution
3. **DC-6**: Classification basis hierarchy — NB_comment > engineer_correction > expert_judgment > ISO_14155 > heuristic

## Limitations

- B1/5/D3 asset values largely TO_BE_EXTRACTED/TO_BE_VERIFIED — full numeric absorption blocked
- No gold labels available — all closures HEURISTIC or SYNTHETIC
- No Domain Expert calibration performed
- Score capped at 75/100
