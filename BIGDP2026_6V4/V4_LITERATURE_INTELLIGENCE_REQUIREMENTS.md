# V4 — Literature Intelligence V2 Requirements

**Purpose:** Define article role classification, appraisal criteria, and data-use eligibility for each piece of literature in the CER context.

---

## 1. Article Role Classifier

Each article has ONE `primary_article_role` and may have multiple `secondary_roles`. Roles are also assignable at the data-point level.

**Primary article roles:**

| Role | Definition |
|:---|:---|
| `direct_device_evidence` | Clinical data specifically on the subject device |
| `equivalent_device_evidence` | Clinical data on the claimed equivalent device |
| `similar_device_context` | Data on similar but not equivalent devices |
| `comparator_benchmark` | Data on alternative therapies for benchmark |
| `alternative_treatment` | Data on alternatives for treatment landscape |
| `background_sota` | General state of the art background |
| `safety_signal` | Literature reporting safety concerns |
| `excluded` | Does not meet inclusion criteria |

**Secondary roles allowed per primary role:**
- `background_sota` primary + `comparator_benchmark` secondary (systematic review with benchmark data)
- `similar_device_context` primary + `safety_signal` secondary (similar device study reporting AE)
- `equivalent_device_evidence` primary + `comparator_benchmark` secondary (equivalent device data also serves as benchmark)

**Data-point-level roles:** Individual data points within an article may have different roles:
```json
{
  "primary_article_role": "similar_device_context",
  "secondary_roles": ["safety_signal"],
  "data_point_level_roles": [
    {"data_point": "hemostasis rate 95%", "role": "comparator_benchmark", "use_allowed": "benchmark_only"},
    {"data_point": "skin injury 2%", "role": "safety_signal", "use_allowed": "safety_context_only"}
  ]
}
```

**Role conflict resolution:** If primary role conflicts with data-point role (e.g., `excluded` article but data point used as benchmark) → FLAG for human review.

---

## 2. Literature Appraisal Criteria

Per article:

| Dimension | Assessment |
|:---|:---|
| study_design | RCT / prospective / retrospective / case_series / registry / review / meta_analysis |
| oxford_cebm_level | 1a–5 |
| sample_size | N value + adequacy assessment |
| population_match | Does study population match target population? (full / partial / none) |
| endpoint_match | Do study endpoints match CER claim endpoints? (full / partial / none) |
| indication_match | Does study indication match device indication? (full / partial / none) |
| device_match | Is this the subject device / equivalent device / similar device / different device? |
| follow_up_adequacy | Is follow-up duration sufficient for safety/performance assessment? |
| fulltext_basis | obtained / abstract_only / unobtainable |
| risk_of_bias | low / moderate / high |
| applicability | direct / indirect / not_applicable |

---

## 3. Data-Use Eligibility

Per data point extracted from literature:

| Eligibility Level | Can Be Used For | Cannot Be Used For |
|:---|:---|:---|
| `fulltext_direct` | Benchmark, BR, claim support, SOTA | — |
| `abstract_only` | Background SOTA only | Numerical claim support, benchmark |
| `secondary_source` | Contextual reference only | Primary evidence |
| `unavailable` | None | Any clinical claim |
| `excluded` | None | Any purpose |

---

## 4. Benchmark Eligibility

Article data can be used as comparator benchmark if:

- [ ] fulltext_basis = obtained
- [ ] study_design supports benchmark use (RCT/prospective preferred)
- [ ] endpoint_match ≥ partial
- [ ] population_match ≥ partial
- [ ] sample_size adequate (N≥30 preferred)
- [ ] comparator device/therapy clearly defined
- [ ] numerical data available (rate, CI, mean, SD)

If any condition not met → `benchmark_eligibility = limited` with explicit limitation.

---

## 5. Claim Support Eligibility

Article data can support a CER claim if:

- [ ] fulltext_basis = obtained (abstract_only allowed with `limited` confidence)
- [ ] device_match = subject_device OR equivalent_device
- [ ] endpoint_match ≥ partial
- [ ] population_match ≥ partial
- [ ] study_design appropriate for claim type
- [ ] data quality sufficient for claim strength

If using indirect evidence → `support_type = indirect` with explicit limitation.

---

## 6. Exclusion and Limitation Logic

| Condition | Action |
|:---|:---|
| N < 10 | EXCLUDE from primary evidence (background context only) |
| Animal / in-vitro / cadaver | EXCLUDE from clinical evidence |
| Review / guideline as primary data | EXCLUDE — trace to original studies |
| Abstract-only with numerical claim | LIMIT — cannot support benchmark or primary claim |
| Fulltext unavailable | LIMIT — cannot extract numerical data |
| Wrong population | EXCLUDE or LIMIT with explicit mismatch rationale |
| Wrong endpoint | LIMIT — cannot support mismatched claim |
| High risk of bias | LIMIT — reduce evidence weight |
