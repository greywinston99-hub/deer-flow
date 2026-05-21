# S-FT-12: Fulltext Acquisition Strategy

- **Type**: Deterministic
- **Step**: Fulltext Basis Gate (G41, Step 12A)
- **Batch**: P2
- **Agent**: authoring-evidence-agent

## Input
- `full_text_request_list` with PMID/DOI
- `evidence_registry` article metadata

## Output
- `fulltext_acquisition_status_table`: acquisition_status, fulltext_source, adapter_used
- `document_structured_content` for acquired full texts

## Decision Logic
1. Priority order: PMC Open Access → Europe PMC → Institutional access → Manual download
2. Accept abstract_only when:
   - Article is non-pivotal (background/supportive weight)
   - Claim is not high-risk safety claim
3. Require fulltext when:
   - Article is pivotal evidence
   - Claim is safety-critical (MDR Class III)
   - Statistical data needs verification
4. Failure degradation: mark as `fulltext_unavailable` with reason
5. Record adapter used and lineage to `fulltext_acquisition_status_table`

## Checks
- Pivotal + high-risk claims always have fulltext
- Abstract_only usage has documented justification
- Failure recorded with degradation strategy
