# S-ENDPT-ALT-XX: Endpoint Replacement Suggestions

- **Type**: Few-shot + Prompt
- **Step**: G42 auxiliary (Step 16A extension)
- **Batch**: P1
- **Agent**: authoring-evidence-agent

## Input
- G42 `ENDPOINT_GAP` failure claims
- `endpoint_alternatives.json` knowledge base
- `clinical_evidence_fact_table`

## Output
- Alternative endpoint recommendations with clinical equivalence rationale
- Recorded to `g42_failure_pattern_report`

## Decision Logic
1. When direct endpoint insufficient:
   - Look up domain in `endpoint_alternatives.json`
   - Find primary endpoint → alternatives mapping
2. Evaluate clinical equivalence of each alternative:
   - Clinical equivalence: same outcome family, similar clinical meaning
   - Statistical equivalence: correlated measurement, validated surrogate
   - Procedural equivalence: similar procedure outcome
3. Recommend highest-confidence alternative with literature support evidence
4. Record replacement decision to `evidence_spiral_lineage`

## Checks
- Replacement has clinical equivalence rationale
- Alternative has literature support
- 5+ clinically validated replacement cases
- `ENDPOINT_REPLACEABLE` pattern recorded in G42 report
