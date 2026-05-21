# S-CEMAT-16: Endpoint Equivalence Judgment

- **Type**: Deterministic
- **Step**: Claim-Evidence Matrix (Step 17A)
- **Batch**: P2
- **Agent**: authoring-evidence-agent

## Input
- `endpoint_extraction` from multiple evidence sources
- `semantic_endpoint_mapping_table`
- `endpoint_match_trace`

## Output
- Endpoint equivalence decisions: equivalent / related / distinct
- `claim_evidence_matrix` with grouped endpoint statistics

## Decision Logic
1. Name similarity: Levenshtein distance + clinical synonym matching
2. Clinical concept overlap: same outcome family (e.g., MACE ⊆ {cardiac death, MI, stroke})
3. Equivalent endpoints → mergeable statistics (meta-analysis compatible)
4. Non-equivalent endpoints → separate reporting in CER
5. Endpoint family: group by clinical concept (efficacy, safety, QoL, procedural)

## Checks
- Equivalent endpoints correctly merged
- Non-equivalent endpoints separately reported
- 5+ test cases judged accurately
- `endpoint_match_trace` records all equivalence decisions
