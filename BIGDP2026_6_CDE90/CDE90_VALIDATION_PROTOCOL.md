# CDE90 — Validation Protocol

**Purpose:** Define exact fact matching, tolerance, critical fields, and evaluation methodology for gold set validation.

---

## Fact Matching Key

A system-extracted fact matches a gold fact when these fields match:

`source_pmid + source_table_or_figure + endpoint + population_label + fact_type + timepoint`

## Numeric Tolerance

| Field | Tolerance |
|:---|:---|
| value (percentage) | ±0.5 percentage points |
| value (continuous - mmHg, days) | ±0.1 (rounded) |
| numerator | exact match required |
| denominator | exact match required |
| CI lower/upper | ±0.1 percentage points |
| p_value | exact match (or both ≤0.05 / both >0.05 for significance-level matching) |

## Critical Fields

These fields must be correct for a fact to count as fact-level PASS:

`value, numerator, denominator, endpoint, endpoint_category, population_label, study_arm, source_quote_or_cell, data_use_allowed, verification_status, clinical_use_limitation`

## Non-Critical Fields

These fields contribute to field-level accuracy but do not block fact-level PASS:

`statistical_measure, timepoint, followup_duration, extraction_confidence, extraction_method`

## Evaluation Metrics

| Metric | Formula |
|:---|:---|
| Fact-level precision | correct_facts / total_extracted_facts |
| Fact-level recall | correct_facts / total_gold_facts (eligible subset) |
| Fact-level F1 | 2 × P × R / (P + R) |
| Field-level accuracy | correct_field_values / total_field_values per field |
| Benchmark eligibility accuracy | correct_benchmark_eligible / total_benchmark_labeled |

## Negative Case Metrics

**Negative blocking accuracy** = correctly_not_extracted_negative_cases / total_negative_cases
Where `correctly_not_extracted` = system correctly did NOT produce a fact for a negative case.
Required: ≥ 0.90.

**Not_allowed leakage rate** = leaked_not_allowed_cases / total_not_allowed_cases
Where `leaked` = a fact with `data_use_allowed` including `not_allowed` was used for `benchmark` or `claim_support`.
Required: = 0 (zero tolerance for leakage into benchmark or claim_support).

## Eligible Gold Facts for Recall

Exclude from recall denominator:
- gold facts with is_negative=true (these test that system does NOT extract them — scored via negative blocking accuracy)
- gold facts from holdout dataset_role (if holdout used for validation only)

## Holdout Rule

Gold facts with `dataset_role=holdout` must NOT be used for parser training, rule induction, or threshold calibration. They are for final validation only.

## Parser-Specific Evaluation

| Parser | Additional Check |
|:---|:---|
| Statistical parser | fact_type + statistical_measure + CI + p_value correct |
| Table extraction | source_table_or_figure + cell anchor correct |
| Denominator resolver | denominator + population_label + analysis_set correct |
| AE extractor | endpoint_category=safety + severity correct |
