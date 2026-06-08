# CDE90 — Batch M: Clinical Study Data Model V3

**Target:** Upgrade clinical_fact_registry from v2 to v3
**Principle:** 数字不能脱离 source / population / denominator / endpoint / study arm 独立存在

---

## 1. clinical_fact_registry_v3 Schema

Each fact carries its full context from birth:

| Field | Type | Description |
|:---|:---|:---|
| fact_id | string | unique per fact |
| source_pmid | string | PMID anchor |
| source_file_path | string | file location |
| source_page | string | page reference |
| source_table_or_figure | string | Table 3 / Figure 2 |
| source_quote_or_cell | string | exact text or cell location |
| study_design | string | RCT / prospective / retrospective / case_series |
| study_arm | string | treatment / control / comparator |
| population_label | string | total / subgroup_name |
| analysis_set | string | ITT / PP / safety / evaluable |
| endpoint | string | endpoint name |
| endpoint_category | string | safety / performance / clinical_benefit |
| fact_type | string | proportion / mean / median / HR / RR / OR / KM / incidence |
| value | float | primary value |
| unit | string | % / mmHg / days / events/patient-year |
| numerator | int | if applicable |
| denominator | int | if applicable |
| timepoint | string | 30-day / 6-month / 12-month |
| followup_duration | string | mean/median follow-up |
| statistical_measure | string | 95% CI / IQR / range |
| confidence_interval_lower | float | if CI |
| confidence_interval_upper | float | if CI |
| p_value | float | if reported |
| source_eligibility | string | fulltext_verified / abstract_only / secondary / unavailable |
| data_use_allowed | string | benchmark / BR / claim_support / background_only / not_allowed |
| clinical_use_limitation | string | none / abstract_only / no_fulltext / subgroup_only / low_sample_size / endpoint_mismatch |
| extraction_confidence | string | high / medium / low |
| verification_status | string | source_verified / gold_label_verified / unverified |
| extraction_method | string | regex / llm / table_parse / hybrid |

## 2. Supporting Models

**clinical_study_model:** study_id, pmid, design, total_N, arms[], populations[], endpoints[], followup_duration
**analysis_population_model:** population_id, type (ITT/PP/safety/evaluable), N, inclusion_criteria
**study_arm_model:** arm_id, label (treatment/control/comparator), N, intervention
**endpoint_fact_model, adverse_event_fact_model, followup_fact_model, statistical_fact_model** — specialized schemas built on v3 base

## 3. Integration

- clinical_fact_registry_v3 replaces v2, maintaining backward compatibility
- E0 eligibility fields map to v3
- Batch O statistical parser populates v3
- Batch N table extraction populates v3 with source_table_or_figure anchors
- Batch P denominator resolver validates v3 denominator/arm/analysis_set fields
- Batch Q gold set validates v3 fact accuracy

## 4. Tests

- [ ] v3 schema validates against JSON Schema
- [ ] v2 facts migratable to v3 without data loss
- [ ] Backward compatibility: existing consumers still work
- [ ] study model populated from real PMID fixture
- [ ] arm model correctly separates treatment/control/comparator
