# CDE90 — Acceptance Checklist

**States:** ☐ NOT_CHECKED | ✅ PASS | ❌ FAIL | ⏭️ DEFERRED
**Evidence per item:** code | test | runtime | asset | source_verification | validation

---

## Batch M — Data Model V3

- [ ] M.1 clinical_fact_registry_v3 schema defined and validated
- [ ] M.2 study_model / analysis_population / study_arm / endpoint_fact / AE_fact / followup_fact / statistical_fact defined
- [ ] M.3 Backward compatible: v2 facts migrate without data loss
- [ ] M.4 Existing consumers (E0, G_DENOMINATOR, G46) still work
- [ ] M.5 30+ fields per fact including source_table_or_figure, verification_status
- [ ] M.6 data_use_allowed supports multi-value (list-like: benchmark,claim_support,BR_GSPR,background_only)
- [ ] M.7 BR renamed/mapped to BR_GSPR consistently

## Batch N — Table / Fulltext Extraction

- [ ] N.1 ≥50 table-derived facts
- [ ] N.2 ≥10 DOCX table facts
- [ ] N.3 ≥10 PDF table facts
- [ ] N.4 ≥10 facts with table footnote denominator context
- [ ] N.5 0 table fact without source table anchor
- [ ] N.6 Extraction failure classification implemented
- [ ] N.7 Incomplete facts correctly flagged
- [ ] N.8 KM/figure candidates are not counted as source-verified facts unless numeric data is verified
- [ ] N.9 Table-derived fact includes cell-level or row/column-level anchor

## Batch O — Statistical Parser V3

- [ ] O.1 ≥15/20 statistical types parseable
- [ ] O.2 ≥10 CI/range/statistical facts from fixtures
- [ ] O.3 ≥5 KM/survival/time-to-event facts
- [ ] O.4 ≥5 AE severity facts
- [ ] O.5 Incomplete facts → data_use_allowed includes background_only and/or human_gate_required; not single-value background_only
- [ ] O.6 No incomplete fact passes benchmark eligibility

## Batch P — Denominator / Arm Resolver

- [ ] P.1 All 10 denominator types distinguishable
- [ ] P.2 Subgroup generalization blocked without justification
- [ ] P.3 Per-procedure vs per-patient correctly detected
- [ ] P.4 McKee-style mismatch (N=216 / CMF n=80) detected
- [ ] P.5 Percentage recalculation validated
- [ ] P.6 Missing denominator + benchmark → FAIL

## Batch Q — Gold Dataset & Validation

- [ ] Q.1 Gold set exists with ≥150 source-verified facts
- [ ] Q.2 All 10 categories meet minimum counts
- [ ] Q.3 Negative / not_allowed cases included
- [ ] Q.4 Precision/recall/F1 measurable
- [ ] Q.5 Precision ≥ 0.85
- [ ] Q.6 Recall ≥ 0.80
- [ ] Q.7 Gold set schema validated
- [ ] Q.8 Validation protocol defines fact matching key, numeric tolerance, critical fields, fact-level and field-level accuracy
- [ ] Q.9 ≥150 count is unique gold facts; category counts may overlap by category_tags
- [ ] Q.10 Holdout gold facts (dataset_role=holdout) not used for parser training or calibration
- [ ] Q.11 Negative blocking accuracy ≥ 0.90 (correctly not extracted / total negative cases)
- [ ] Q.12 Not_allowed leakage into benchmark or claim_support = 0

## Regression

- [ ] R.1 All baseline tests pass (615)
- [ ] R.2 G46 chain intact
- [ ] R.3 E0 eligibility still enforced
- [ ] R.4 G_DENOMINATOR still works

---

**Total: 43 items**
