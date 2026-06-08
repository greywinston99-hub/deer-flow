# SEMANTIC ENDPOINT MAPPING SPEC

> CCD 签发 | 2026-05-12 | V3-Core

## Problem

Current endpoint matching is raw string matching. "PVI success rate" ≠ "acute ablation success" ≠ "pulmonary vein isolation" — all the same clinical endpoint, different naming.

## Endpoint Families

| Family | Includes |
|---|---|
| safety | adverse_event, complication, device_related_harm, death, SAE |
| effectiveness | procedural_success, clinical_success, technical_success |
| hemodynamic | blood_pressure, heart_rate, cardiac_output, vascular_resistance |
| device_integrity | device_failure, malfunction, material_degradation |
| quality_of_life | QoL_score, functional_status, symptom_score |
| biomarker | lab_value, imaging_finding, physiological_measurement |
| usability | user_error, training_required, IFU_compliance |
| post_market | PMCF_finding, complaint_rate, recall_event |

## Mapping Method — Multidimensional

Not semantic similarity alone。Each match evaluates:
  - endpoint_definition: what is being measured
  - measurement_method: how it is measured
  - timepoint: when it is measured
  - population: in whom
  - procedure_anatomy: under what conditions
  - benefit_risk_direction: favorable vs unfavorable interpretation

## Trace Fields

Each mapping records:
  - embedding_model: model + version used
  - threshold_source: threshold value + rationale
  - similarity_score: raw similarity
  - match_dimensions: which dimensions passed/failed
  - endpoint_match_trace: full trace of matching decision

## Confidence

- All 6 dimensions match + exact label → high
- ≥4 dimensions match + similarity >0.8 → medium
- Family match only → low
- No match → unmatched

## Integration

Output: `semantic_endpoint_mapping_table.csv` + `endpoint_match_trace.json`
→ clinical_evidence_fact_table (endpoint_family, mapping_confidence, candidate_claim_ids)

Final linking through `fact_to_claim_link_matrix` (not raw claim_id at extraction).

---

*CCD 签发：2026-05-12*
