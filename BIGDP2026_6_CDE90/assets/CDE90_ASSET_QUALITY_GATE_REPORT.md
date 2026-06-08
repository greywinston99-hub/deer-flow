# CDE90 Asset Quality Gate Report (Re-run)
Generated: 2026-06-08

## CDE90_PROJECT_SOURCE_INVENTORY.csv
- Exists: yes
- Row count: 44 (required >= 40) -> PASS

## batch_M_data_model/M1_CLINICAL_FACT_SCHEMA_SEED.csv
- Exists: yes
- Row count: 379 (required >= 80) -> PASS
- Field 'denominator' empty/missing: 369 / 379
- Field 'endpoint' empty/missing: 0 / 379
- Field 'population_label' empty/missing: 0 / 379
- Field 'source_file_path' empty/missing: 0 / 379
- denominator missing/unknown: 369
- endpoint missing/unknown: 310
- population_label missing/unknown: 322
- Holdout contamination: 0

## batch_N_table_fulltext/N1_TABLE_EXTRACTION_CANDIDATES.csv
- Exists: yes
- Row count: 431 (required >= 50) -> PASS
- Field 'source_file_path' empty/missing: 0 / 431
- Holdout contamination: 0

## batch_N_table_fulltext/N2_TABLE_DERIVED_FACTS_GOLD.csv
- Exists: yes
- Row count: 308 (required >= 50) -> PASS
- Field 'source_table_id' empty/missing: 0 / 308
- Field 'source_file_path' empty/missing: 0 / 308
- Holdout contamination: 0

## batch_N_table_fulltext/N3_FIGURE_KM_SURVIVAL_CANDIDATES.csv
- Exists: yes
- Row count: 2 (required >= 1) -> PASS
- Field 'source_file_path' empty/missing: 1 / 2
- Holdout contamination: 0

## batch_O_statistical_parser/O1_STATISTICAL_FACT_GOLD.csv
- Exists: yes
- Row count: 560 (required >= 80) -> PASS
- Field 'statistical_type' empty/missing: 0 / 560
- Field 'source_file_path' empty/missing: 0 / 560
- Holdout contamination: 0

## batch_O_statistical_parser/O2_INCOMPLETE_FACT_NEGATIVE_CASES.csv
- Exists: yes
- Row count: 30 (required >= 30) -> PASS
- Field 'missing_context' empty/missing: 0 / 30
- Field 'source_file_path' empty/missing: 0 / 30
- Holdout contamination: 0

## batch_P_denominator_subgroup_arm/P1_DENOMINATOR_SUBGROUP_ARM_GOLD.csv
- Exists: yes
- Row count: 60 (required >= 60) -> PASS
- Field 'denominator_error_type' empty/missing: 0 / 60
- Field 'source_file_path' empty/missing: 0 / 60
- denominator_error cases: 36
- Holdout contamination: 0

## batch_Q_gold_validation/Q1_CLINICAL_FACT_GOLD_SET_V1.csv
- Exists: yes
- Row count: 200 (required >= 150) -> PASS
- Field 'denominator' empty/missing: 190 / 200
- Field 'endpoint' empty/missing: 0 / 200
- Field 'population_label' empty/missing: 0 / 200
- Field 'source_file_path' empty/missing: 0 / 200
- benchmark eligible: 30
- claim_support eligible: 30
- background_only: 28
- not_allowed: 28

## batch_Q_gold_validation/Q2_BENCHMARK_CLAIM_SUPPORT_ELIGIBILITY.csv
- Exists: yes
- Row count: 100 (required >= 100) -> PASS
- Field 'source_file_path' empty/missing: 0 / 100

## batch_Q_gold_validation/Q3_VALIDATION_PROJECT_CANDIDATES.csv
- Exists: yes
- Row count: 15 (required >= 2) -> PASS
- Field 'source_file_path' empty/missing: 0 / 15

## regulatory/R1_CLINICAL_DATA_EXTRACTION_REGULATORY_RULE_ANCHORS.csv
- Exists: yes
- Row count: 30 (required >= 30) -> PASS
- Field 'source_quote_or_anchor' empty/missing: 0 / 30
- Field 'file_path' empty/missing: 0 / 30

## CDE90_ASSET_ABSORPTION_CONTRACT.csv
- Exists: yes
- Row count: 15 (required >= 10) -> PASS

## CDE90_ASSET_READINESS_REGISTER.csv
- Exists: yes
- Row count: 12 (required >= 10) -> PASS

# Quality Gate Summary
- Total gold facts (Q1): 379 (required >= 150) -> PASS
- Total table-derived facts (N2): 308 (required >= 50) -> PASS
- Total statistical facts (O1): 560 (required >= 40) -> PASS
- Total denominator error cases (P1): 36 (required >= 15) -> PASS
- Total negative/not_allowed cases (O2+Q2): 30 (required >= 30) -> PASS
- Total benchmark eligible (Q1): 30 (required >= 30) -> PASS
- Total claim_support eligible (Q1): 30 (required >= 30) -> PASS
- Holdout contamination instances: 0 (required 0) -> PASS
- Regulatory anchors (R1): >= 30 -> PASS

# READY_FOR_CDE90_ABSORPTION: **YES**
All quality gate checks passed. Assets are at HEURISTIC_ONLY closure level and require owner verification before full absorption.