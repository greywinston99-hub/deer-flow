# S-APPRAISE-11: Evidence Scoring Framework

- **Type**: Deterministic
- **Step**: Evidence Appraisal (Step 11A)
- **Batch**: P0
- **Agent**: authoring-evidence-agent

## Input
- `evidence_registry` entries with full-text content
- `document_structured_content` from full-text parsing

## Output
- `article_appraisal`: evidence_strength_score (0-100), study_design, oxford_level, sample_size, follow_up, statistical_adequacy, device_applicability, population_applicability, endpoint_match, limitations
- `evidence_registry.weight`: pivotal / supportive / background / excluded

## Decision Logic (Six-factor weighted scoring)
| Factor | Weight | What it measures |
|--------|--------|-----------------|
| F1: study_design | 0.25 | RCT > prospective cohort > retrospective > case series |
| F2: device_relationship | 0.25 | Subject device > equivalent > similar > competitor > unrelated |
| F3: data_quality | 0.20 | Direct text > table extraction > LLM inferred > OCR recovered |
| F4: fact_confidence | 0.15 | Clinical fact confidence from extraction |
| F5: conflict_status | 0.10 | Consistent > no conflict data > contradictory |
| F6: regulatory_admissibility | 0.05 | Meets MEDDEV/MDCG standards > partial > insufficient |

Score = Σ(factor_score × weight) × 100

## Checks
- Oxford Level mapped from study_design via `OXFORD_STUDY_DESIGN_MAP`
- Score ≥ 80 → pivotal weight
- Score 40-80 → supportive weight
- Score < 40 → background or excluded
- 10+ engineer calibration cases validated
