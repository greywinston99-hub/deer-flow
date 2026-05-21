# W-SUM-18: Summary Synthesis Writing

- **Type**: Prompt+Guard
- **Step**: CER Writing 28.1 (§1 Summary)
- **Batch**: P0
- **Agent**: authoring-cer-writer-agent

## Input
- `claim_support_matrix`: claim-level support status
- `benefit_risk_conclusion`: BR synthesis outcome
- `evidence_funnel_counts`: retrieval → screening → appraisal → consumption counts
- `claim_sota_alignment_table`: alignment status

## Output
- §1 Summary: 1-2 pages natural paragraphs

## Decision Logic (4 required elements)
1. **Device Overview** (1 paragraph): what device, what it does, device class, target population
2. **Evidence Base Summary** (1-2 paragraphs): funnel counts with stage labels, evidence quality overview
3. **Key Uncertainties** (1 paragraph): gaps, partial SOTA support, BR asymmetry
4. **Overall Conclusion** (1 paragraph): strength-appropriate conclusion matching BR outcome

## Writing Rules
- NO evidence ID listing (never "E-001, E-002, E-003...")
- Evidence quantity uses funnel stage labels
- Conclusion strength must match BR conclusion
- Max 500 words

## Checks
- No evidence ID enumeration
- Funnel stages explicitly labeled
- Conclusion matches BR strength
- 5+ human-reviewed summaries
