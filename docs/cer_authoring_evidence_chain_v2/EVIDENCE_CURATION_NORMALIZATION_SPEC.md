# EVIDENCE CURATION NORMALIZATION SPEC — V2 (REVISED)

> CCD 签发 | 2026-05-12

## Source Classification

Determine source_type by:
- **Content analysis**（primary）: document text, structure, key sections
- **Source anchor**（primary）: file metadata, identifiers, citations
- Folder location（secondary, weak evidence only）: 01_ subfolder as hint, not determinant

When content and folder location conflict → content prevails。

## Classification Rules

| Content Signal | → source_type |
|---|---|
| Clinical study with patient data, endpoints, statistics | subject_device_clinical_study |
| PMS/PMCF report with period, events, conclusions | subject_device_pms_pmcf |
| Test report with standard, method, acceptance criteria, result | subject_device_test_performance |
| IFU with intended use, warnings, contraindications | subject_device_ifu |
| RMF with hazard, risk, control | subject_device_risk_management |
| Published literature with PMID/DOI | literature_pubmed_sota |
| Competitor IFU/regulatory filing | competitor_device_public |
| Previous device version documentation | previous_generation_device |

## Normalization

Per source type, normalize key fields（PMID for literature, study ID for clinical, standard for test, etc.）

## Missing-Data

Per field: present → value | absent → missing_data_flag + impact + rationale。

Impact: `BLOCKING`（prevents pivotal/supportive）| `LIMITING`（restricts strength）| `INFORMATIONAL`（noted only）。

## Human Supplement Queue

Subject-device data expected but absent → HUMAN_SUPPLEMENT_NEEDED with field list。Do not silently treat as unavailable。

---

*CCD 签发：2026-05-12*
