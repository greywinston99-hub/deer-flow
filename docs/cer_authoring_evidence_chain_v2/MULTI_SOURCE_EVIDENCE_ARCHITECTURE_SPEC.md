# MULTI-SOURCE EVIDENCE ARCHITECTURE SPEC

> CCD 签发 | 2026-05-12

## Evidence Source Taxonomy

```text
SOURCE_TYPE:
  literature_pubmed_sota
  subject_device_clinical_study
  subject_device_clinical_data
  subject_device_pms_pmcf
  subject_device_psur
  subject_device_vigilance
  subject_device_test_performance
  subject_device_risk_management
  subject_device_ifu
  subject_device_gspr
  similar_device_literature
  similar_device_regulatory
  competitor_device_public
  previous_generation_device
  public_registry_eudamed
  public_registry_gudid_fda
  manufacturer_cep_technical_file
  other_manufacturer_data
```

## Evidence Object Model

Each evidence item MUST carry:
- `evidence_id`
- `source_type`
- `source_anchor` (file/PMID/DOI/registry ID)
- `device_relationship` (subject / similar / competitor / previous_gen / unrelated)
- `comparability_score` (if not subject device)
- `allowed_use` (per claim type)
- `missing_data_flags` (explicit fields that are unavailable)
- Plus all existing appraisal fields (role, level, applicability, etc.)

## Multi-Source Inventory

Before evidence pipeline runs:
1. Scan 01_INITIAL_INPUT_FOR_WRITER for all evidence source files
2. Classify each source by type and device relationship
3. Build evidence_source_inventory
4. Route each source type to appropriate ingestion pipeline

## Integration with Spiral Architecture

G42 must derive `required_source_profile` by:
  `claim_type × device_class × risk_level × available_data_profile`

Static claim-source examples below are examples only.
Per `MULTI_SOURCE_GATE_CONTRACT.md` for authoritative AND/OR logic.

Writer consumption: each evidence item carries `allowed_use` tags.
Writer may only use evidence for claims where allowed_use permits it.

---

*CCD 签发：2026-05-12*
