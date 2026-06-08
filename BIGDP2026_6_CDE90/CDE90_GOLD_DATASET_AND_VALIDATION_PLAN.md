# CDE90 — Batch Q: Clinical Fact Verification & Gold Dataset

**Target:** Build source-verified gold validation set. Without it, Stage 5 cannot exceed 86/100.

---

## 1. clinical_fact_gold_set_v1

**≥150 unique clinical facts.** Each fact carries category_tags for multi-label classification. Category counts may overlap by tags—the 150 count is unique facts, not category-summed.

| Category Tag | Min Tagged Facts | Source |
|:---|:--:|:---|
| table_derived | 50 | DOCX + PDF tables |
| statistical | 40 | HR, RR, OR, CI, KM, incidence |
| subgroup | 20 | Subgroup analysis data |
| AE | 20 | Safety tables |
| followup | 20 | Follow-up data |
| negative | 30 | Excluded data, abstract-only numerical, wrong population |
| denominator_error | 15 | McKee-style, subgroup mixing |
| benchmark_eligible | 30 | Comparator data with clear source |
| claim_support_eligible | 30 | Direct device evidence |

**Counting rule:** One gold_fact_id may carry multiple tags. E.g., GF-001 can be tagged `table_derived, statistical, subgroup, denominator_error` and count toward all four category minimums. The 150 floor is on unique gold_fact_ids.

## 2. Gold Fact Schema

```json
{
  "gold_fact_id": "GF-001",
  "source_pmid": "30635996",
  "source_location": "Table 2, row 3",
  "source_quote": "CMF hemostasis adequate 87.5% (70/80)",
  "expected_fields": {
    "endpoint": "hemostasis success",
    "numerator": 70,
    "denominator": 80,
    "population_label": "CMF subgroup",
    "study_arm": "treatment",
    "value": 87.5,
    "fact_type": "proportion"
  },
  "is_negative": false,
  "difficulty": "subgroup_denominator",
  "gold_source": "source_verified"
}
```

## 3. Verification Methods

| Method | Confidence | Use When |
|:---|:--:|:---|
| source_verified | HIGH | Direct comparison with published abstract/full-text/table |
| gold_label_verified | HIGH | Domain expert confirmed |
| cross_reference_verified | MEDIUM | Verified against 2+ independent sources |
| unverified | LOW | Not yet checked |

## 4. Validation Protocol

Fact matching key: `source_pmid + source_table_or_figure + endpoint + population_label + fact_type + timepoint`.
Numeric tolerance: percentage ±0.5pp; N/n exact match required; CI ±0.1pp.
Critical fields (must be correct for fact-level PASS): value, numerator, denominator, endpoint, population_label, source_quote_or_cell, data_use_allowed, verification_status.
Fact-level accuracy: % of gold facts where all critical fields match.
Field-level accuracy: per-field correctness rate independently.
Benchmark eligibility: requires denominator + source anchor + data_use_allowed includes `benchmark`.
Holdout gold facts (dataset_role=holdout) must not be used for parser training.

## 5. Metrics

- Precision: correct_facts / total_extracted_facts
- Recall: correct_facts / gold_set_total
- F1: harmonic mean
- Fact-level accuracy: % facts with all fields correct
- Field-level accuracy: per-field correctness rate

## 5. Cap Rules

| Condition | Max Stage 5 Score |
|:---|:--:|
| No gold set | 86 |
| No real project validation | 88 |
| Gold set < 150 facts | 88 |
| Precision < 0.85 | 85 |
| Recall < 0.80 | 85 |

## 6. Acceptance

- [ ] gold set exists with ≥150 source-verified facts
- [ ] All 10 categories have minimum counts
- [ ] Negative cases included
- [ ] Precision/recall/F1 measurable
- [ ] Gold set schema validated
