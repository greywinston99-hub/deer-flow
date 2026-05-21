# S-DOMAIN-08: Domain Term Severity Grading

- **Type**: Deterministic
- **Step**: Retrieval Domain Gate (G39, Step 8A)
- **Batch**: P2
- **Agent**: authoring-evidence-agent

## Input
- `retrieval_domain_grounding_report`
- `domain_term_matrix` (forbidden terms per domain)
- Article titles/abstracts from search results

## Output
- `domain_contamination_report`: forbidden term hits with severity grading
- Gate routing: PASS / REWORK / BLOCKED

## Decision Logic
1. Scan retrieved literature for forbidden domain terms
2. Grade severity by context:
   - Accessory description / background mention → minor
   - Clinical background / SOTA context → critical
   - Same-device-family terminology → exception
3. Exception contexts auto-recognized from `exception_contexts` in domain_term_matrix
4. Aggregate: any critical contamination → REWORK or BLOCKED

## Checks
- All 5 domains configured with forbidden/allowed/ambiguous terms
- `exception_contexts` auto-recognition functional
- Report distinguishes critical vs minor contamination
