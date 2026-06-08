# V3 Patch A Tier 2 — Quality Gate Report

**Generated:** 2026-06-08 16:59:35
**Scope:** BIGDP2026.6V_3 Patch A Tier 2 Asset Completion

## 1. File Existence Check

| CSV | Exists | Rows | Status |
|:---|:---:|:---:|:---|
| PROJECT_SELECTION_COVERAGE_MATRIX | YES | 44 | PASS |
| HISTORICAL_REGRESSION_EXCLUDED | YES | 1 | PASS |
| E1_PMID_CLINICAL_FACT | YES | 62 | PASS |
| E2_DENOMINATOR_SUBGROUP | YES | 12 | PASS |
| E3_TABLE_FIGURE | YES | 12 | PASS |
| E4_FOLLOWUP_AE | YES | 10 | PASS |
| F1_CLAIM_EVIDENCE | YES | 12 | PASS |
| F2_EQUIVALENCE | YES | 5 | PASS |
| F3_EQUIVALENT_LIMITATIONS | YES | 5 | PASS |
| G1_ENDPOINT_DOMAIN | YES | 28 | PASS |
| G2_COMPARATOR_BENCHMARK | YES | 14 | PASS |
| G3_BENEFIT_EVIDENCE | YES | 12 | PASS |
| G4_RISK_MITIGATION | YES | 10 | PASS |
| G5_GSPR_CLAUSE | YES | 10 | PASS |
| G6_UNCERTAINTY | YES | 7 | PASS |
| H1_CER_TEXTS | YES | 15 | PASS |
| H2_WRITER_QA | YES | 13 | PASS |
| H3_VALIDATION_READY | YES | 6 | PASS |
| REGULATORY_TARGETS | YES | 8 | PASS |
| ASSET_CONTRACT | YES | 123 | PASS |

## 2. U1-U6 Coverage Check

| Upgrade | Assets Found | Status |
|:---|:---:|:---|
| U1 Clinical Fact V2 | E1-E4 | PASS |
| U2 Semantic Support | F1 | PASS |
| U3 Equivalence Gate | F2-F3 | PASS |
| U4 Domain Library | G1-G2 | PASS |
| U5 BR/GSPR Crosswalk | G3-G6 | PASS |
| U6 Writer QA | H1-H3 | PASS |

## 3. Batch E/F/G/H Coverage Check

| Batch | Assets Found | Status |
|:---|:---:|:---|
| Batch E | YES | PASS |
| Batch F | YES | PASS |
| Batch G | YES | PASS |
| Batch H | YES | PASS |

## 4. Holdout Contamination Check

**Result:** PASS — No holdout data used in rule generation sources

## 5. 南驰/iTClamp/A06 Exclusion Check

**Result:** PASS — Excluded projects documented in HISTORICAL_REGRESSION_EXCLUDED_PROJECTS.csv

## 6. Source File Path Check

All rows contain source_file_path references. No empty paths found.

## 7. Evidence Level Check

All rows have evidence_level populated.

## 8. Overall Assessment

**Quality Gate Result: PASS**

All required CSVs exist and contain data.
All U1-U6 upgrades have corresponding assets.
All Batch E/F/G/H have corresponding assets.
No holdout contamination detected.
南驰/iTClamp/A06 properly excluded.

**Status: READY_FOR_V3_ABSORPTION (with HEURISTIC_ONLY / DERIVED_VALIDATION closure)**

## 9. Asset Statistics

- Total CSV files: 20
- Total data rows: 409
- Projects covered: 18 (V2 selected pool)
- Calibration: 9 | Stress: 4 | Holdout: 4 | Special Evidence: 1