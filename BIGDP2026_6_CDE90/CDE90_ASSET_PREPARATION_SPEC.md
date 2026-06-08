# CDE90 — Asset Preparation Spec V2 (for Work Buddy)

**Purpose:** Detailed field-level extraction spec for Work Buddy. Every CSV has complete field definitions, quality gates, and absorption targets.

---

## Common Fields (All CSVs)

Every asset file must include these common fields:

| Field | Type | Description |
|:---|:---|:---|
| source_file_path | string | full path to source PDF/DOCX |
| source_page_or_section | string | page number or section name |
| source_table_or_figure | string | Table 3 / Figure 2 |
| source_quote_or_cell | string | exact text or cell reference |
| evidence_level | string | source_verified / gold_label_verified / unverified |
| dataset_role | string | calibration / stress / holdout |
| confidence | string | high / medium / low |
| locked_status | string | open_input / calibration_only / validation_only / locked_no_writer |
| writer_access_allowed | bool | default NO for gold/feedback/negative cases |
| project_id | string | source project identifier |
| project_name | string | source project name |
| target_batch | string | M / N / O / P / Q |
| target_capability | string | data_model / table_extraction / statistical_parsing / denominator_resolver / gold_validation |
| absorption_type | string | gold_validation / parser_training / fixture_generation / semantic_test / holdout_validation |
| closure_level_supported | string | FULLY_CLOSED / DERIVED_VALIDATION / HEURISTIC_ONLY / SYNTHETIC_ONLY |
| notes | string | free-text |
| extraction_date | string | ISO date |

## Asset 1: clinical_fact_gold_set_v1.csv

**Purpose:** Gold-verified clinical facts for parser training and validation. **Min 150 unique facts.**

| Field | Type | Example |
|:---|:---|:---|
| gold_fact_id | string | GF-001 |
| source_pmid | string | 30635996 |
| source_file_path | string | per common |
| source_page_or_section | string | Results, Table 2 |
| source_table_or_figure | string | Table 2 |
| source_quote_or_cell | string | "CMF hemostasis adequate 87.5% (70/80)" |
| endpoint | string | hemostasis success |
| endpoint_category | string | performance |
| fact_type | string | proportion |
| value | float | 87.5 |
| numerator | int | 70 |
| denominator | int | 80 |
| population_label | string | CMF subgroup |
| study_arm | string | treatment |
| analysis_set | string | evaluable |
| timepoint | string | at procedure completion |
| statistical_measure | string | — |
| ci_lower | float | — |
| ci_upper | float | — |
| p_value | float | — |
| source_eligibility | string | fulltext_verified |
| data_use_allowed | string | benchmark,claim_support |
| clinical_use_limitation | string | subgroup_only |
| verification_status | string | source_verified |
| category_tags | string | statistical,subgroup,denominator_error |
| is_negative | bool | false (false=correct fact, true=should NOT be extracted) |
| evidence_level | string | source_verified |
| dataset_role | string | calibration |
| notes | string | McKee 2019 — subgroup N=80 vs total N=216 |

**Category tags:** table_derived, statistical, subgroup, AE, followup, negative, denominator_error, benchmark_eligible, claim_support_eligible. One fact can have multiple tags. 150 is unique facts count. Category counts may overlap.

## Asset 2: table_extraction_candidates.csv

**Purpose:** Tables for Batch N extraction. **Min 50 tables.**

| Field | Type |
|:---|:---|
| table_id | string |
| source_file_path | string |
| source_page | string |
| table_number | string (Table 3) |
| table_title | string (exact) |
| table_format | string (born-digital PDF / DOCX / text) |
| table_type | string (efficacy / safety / demographics / followup) |
| rows_approx | int |
| has_footnotes | bool |
| footnotes_text | string |
| contains_endpoint_data | bool |
| contains_denominator_info | bool |
| contains_subgroup_data | bool |
| contains_CI_or_statistical | bool |
| extraction_complexity | string (low/medium/high) |

## Asset 3: denominator_subgroup_gold.csv

**Purpose:** Facts with verified denominator/subgroup/arm labels. **Min 30 facts.**

Additional fields beyond gold set: correct_denominator_type (total_enrolled_N / safety_set / evaluable / subgroup_n / treatment_arm_N / event_denominator / per_patient / per_procedure / per_device), denominator_mismatch_description, correct_population_label, correct_arm_label.

## Asset 4: statistical_fact_gold.csv

**Purpose:** Facts covering all 20 statistical types. **Min 40 facts.**

Additional fields: statistical_type (from 20-type list), parser_complexity, requires_context_for_parsing.

## Asset 5: ae_followup_gold.csv

**Min 40 facts.** Additional fields beyond common + gold set base:

| Field | Type | Example |
|:---|:---|:---|
| ae_term | string | skin injury |
| ae_severity_grade | string | Grade 1 / 2 / 3 / 4 |
| ae_relatedness | string | device_related / procedure_related / unrelated |
| ae_count | int | 5 |
| ae_rate | float | 2.3 |
| followup_duration_value | float | 12 |
| followup_duration_unit | string | months |
| followup_completeness | float | 85.0 (percent) |

## Asset 6: not_allowed_fact_cases.csv

**Min 30 negative cases.** Facts that SHOULD NOT be extracted or MUST carry limitation.

| Field | Type | Example |
|:---|:---|:---|
| case_id | string | NEG-001 |
| source_pmid | string | 31539432 |
| source_quote | string | (the text that looks like a fact but isn't) |
| why_not_allowed | string | abstract_only / wrong_population / excluded_article / no_source / data_not_in_source |
| would_be_misclassified_as | string | AE / performance_claim / benchmark |
| correct_action | string | do_not_extract / background_only / human_gate_required |
| is_negative | bool | true |

## Asset 7: benchmark_eligibility_labels.csv

**Min 30 facts.**

| Field | Type | Example |
|:---|:---|:---|
| fact_ref | string | GF-042 or PMID+endpoint ref |
| benchmark_eligible | bool | true / false |
| eligibility_rationale | string | direct comparator with CI and source |
| comparator_name | string | tourniquet / sutures / staples |
| required_benchmark_format | string | rate + CI / mean ± SD / KM curve |
| missing_for_full_eligibility | string | CI not reported / no source PMID / no comparator |

## Asset 8: claim_support_eligibility.csv

**Min 30 facts.**

| Field | Type | Example |
|:---|:---|:---|
| fact_ref | string | GF-042 or PMID+endpoint ref |
| claim_support_eligible | bool | true / false |
| claim_type_supported | string | safety / performance / clinical_benefit |
| support_strength | string | strong / moderate / limited |
| eligibility_rationale | string | direct device evidence, endpoint match |
| limitation_for_claim_use | string | subgroup only / short follow-up / small sample |

---

## Work Buddy Quality Gate

Each CSV must pass before submission:

- [ ] All common fields present and non-empty
- [ ] source_quote_or_cell non-empty for gold/expert level
- [ ] dataset_role assigned
- [ ] locked_status assigned
- [ ] No holdout data in calibration set
- [ ] No duplicate gold_fact_ids
- [ ] Machine-readable (pandas verify)

## Asset Readiness Register

Create `CDE90_ASSET_READINESS_REGISTER.csv`:

| asset_id | filename | status | min_count | actual_count | quality_gate | next_action |
|:---|:---|:---|:--:|:--:|:---|:---|

## Asset-to-Absorption Contract

Create `CDE90_ASSET_ABSORPTION_CONTRACT.csv`:

| asset_id | target_batch | absorption_type | can_train | can_validate | can_holdout | writer_allowed |
|:---|:---|:---|:--:|:--:|:--:|:--:|
| gold_set | Q | gold_validation | yes | yes | yes | no |
| table_candidates | N | extraction_target | yes | yes | no | no |
| denom_gold | P | gold_validation | yes | yes | yes | no |

## Closeout

Create `CDE90_ASSET_PREP_CLOSEOUT.md` with: status, files produced, counts per asset, quality gate results, missing assets, readiness for Claude Code absorption.
