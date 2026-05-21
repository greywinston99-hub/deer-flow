# S-SCREEN-10: Literature Screening Quick Judgment

- **Type**: Few-shot
- **Step**: Literature Screening (Step 9A)
- **Batch**: P2
- **Agent**: authoring-evidence-agent

## Input
- `raw_literature_records` from search results
- `query_construction_trace` for search context
- 20+ engineer-provided screening examples

## Output
- `screening_disposition` per article: screen_id, title_abstract_decision, full_text_decision, screening_category, evidence_role_candidate, inclusion/exclusion reason

## Decision Logic
1. Title/abstract quick scan for inclusion signals:
   - Same device family or procedure type
   - Relevant clinical endpoint mentioned
   - Target population overlap
2. Exclusion signals:
   - Wrong anatomical site / disease
   - Preclinical / animal / in vitro only
   - Case report (< 10 patients, non-pivotal)
   - Editorial / commentary / letter
3. Screening categories: pivotal_candidate / supportive_candidate / background / excluded
4. Standardized exclusion reason: "wrong_population", "wrong_device", "wrong_outcome", "non_clinical", "publication_type"

## Checks
- Consistency with human screening ≥ 85%
- Every excluded article has exclusion_reason
- Screening rationale recorded
