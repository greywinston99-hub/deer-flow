# EVIDENCE OBJECT MODEL SPEC — V2

> CCD 签发 | 2026-05-12

## Core Fields (inherited from V1)

article_id, evidence_id, study_design, evidence_level, oxford_level, full_text_status, sample_size, follow_up, device_applicability, population_match, endpoint_match, evidence_role, conclusion_strength_allowed

## V2 New Fields

### Source Anchoring
- `source_type`: one of SOURCE_TYPE taxonomy
- `source_anchor`: file path / PMID / DOI / registry ID
- `source_provenance`: how this evidence entered the pipeline
- `source_reliability`: high / medium / low / unknown

### Device Relationship
- `device_relationship`: subject / similar / competitor / previous_gen / unrelated
- `technical_comparability_score`: 0-3
- `biological_comparability_score`: 0-3
- `clinical_comparability_score`: 0-3
- `comparability_score_raw`: 0-9
- `comparability_score_normalized`: 0-100
- `comparability_band`: HIGH / MEDIUM / LOW / NOT_COMPARABLE
- `comparability_rationale`: text explanation

### Allowed Use
- `allowed_claim_types`: list of claim_type values this evidence may support
- `allowed_conclusion_strength_max`: maximum conclusion strength
- `use_restrictions`: any restrictions on use
- `requires_corroboration`: whether this evidence needs additional support

### Missing Data
- `missing_data_flags`: list of fields that are unavailable
- `missing_data_impact`: how missing data affects evidence role
- `missing_data_rationale`: why data is missing

### Curation
- `curation_status`: raw / normalized / reviewed
- `curation_timestamp`
- `normalized_fields`: fields that were normalized

---

*CCD 签发：2026-05-12*
