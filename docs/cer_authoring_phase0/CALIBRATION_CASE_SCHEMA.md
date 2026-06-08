# Calibration Case Schema

Schema version: `cer-authoring-phase0-contract-v1`

Purpose: define how a real CER project enters calibration while preserving authoring baseline discipline and preventing leakage from human accepted CERs or NB comments into the AI writer stage.

## Required Project Metadata

| Field | Required | Notes |
|---|---:|---|
| `project_id` | yes | Stable calibration project ID. |
| `device_name` | yes | Subject device only, not similar/benchmark device. |
| `device_class` | yes | MDR class or source-stated class, with uncertainty if unknown. |
| `device_domain` | yes | Clinical/device family for stratified analysis. |
| `calibration_role` | yes | `dry_run`, `calibration`, or `holdout`. |
| `source_data_lock_date` | yes | Data-lock used by the AI baseline run. |
| `authoring_baseline_version` | yes | Frozen baseline version for formal calibration. |

## Input Partitions

| Input group | Writer access | Delta analyzer access | Rule |
|---|---:|---:|---|
| Allowed authoring source pack | yes | yes | IFU, CEP, GSPR, RMF, PMS/PMCF, manufacturer files, permitted full texts. |
| Human accepted CER | no | yes | May only be loaded after AI baseline artifacts are frozen. |
| NB comments / response letters | no | yes | Used only for CEAR pattern and root-cause analysis. |

## Required Delta Tables

- `CLAIM_DELTA_TABLE`
- `SOTA_BENCHMARK_DELTA_TABLE`
- `EVIDENCE_SELECTION_DELTA_TABLE`
- `EVIDENCE_APPRAISAL_DELTA_TABLE`
- `CLAIM_EVIDENCE_DELTA_MATRIX`
- `PMCF_BOUNDARY_DELTA_TABLE`
- `ALIGNMENT_DELTA_TABLE`
- `CEAR_DEFICIENCY_PATTERN_TABLE`

## Phase 1 Freeze Discipline

During the three formal calibration projects, do not change SOTA Agent logic, Evidence Appraisal logic, Writer Contract, Benefit-Risk Rule, PMCF Boundary Rule, Alignment Rule, or Gate Logic based on one project. Core upgrades must wait for the aggregate root-cause matrix.

