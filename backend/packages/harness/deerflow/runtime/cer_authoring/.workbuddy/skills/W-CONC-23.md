# W-CONC-23: Conclusion Paragraph Writing

- **Type**: Prompt+Guard
- **Step**: CER Writing 28.8 (§5 Conclusions)
- **Batch**: P0
- **Agent**: authoring-cer-writer-agent

## Input
- `claim_support_matrix`: per-claim support status
- `benefit_risk_conclusion`: overall BR outcome
- `writer_conclusion_constraints`: wording strength limits
- `gap_pmcf_recommendations`: open gaps

## Output
- §5 Conclusions: natural paragraphs (NOT a table)

## Wording Mapping (STRICT)
| Support Level | Verbs | Adverbs | Template |
|--------------|-------|---------|----------|
| STRONG | demonstrate, confirm, establish, validate | clearly, consistently | "The clinical evidence demonstrates that..." |
| MODERATE | indicate, show, support, provide evidence for | generally, typically | "The available evidence indicates that..." |
| CAUTIOUS | suggest, may indicate, appear to, be consistent with | cautiously, preliminarily | "The preliminary data suggest that..." |
| INSUFFICIENT | is not yet established, requires further investigation | N/A | "There is insufficient evidence to conclude that..." |

## Decision Logic
1. Per-claim conclusion: claim_text → evidence support → conclusion sentence
2. BR synthesis: benefit vs risk quality tier → overall BR conclusion
3. Limitations: acknowledge gaps, PMCF needs, evidence quality asymmetry
4. Overall CER conclusion: strength-capped by weakest pivotal claim

## Writing Rules
- Max sentence length: 20 words (§5 is measured/tight)
- Never use STRONG wording for CAUTIOUS/INSUFFICIENT support
- INSUFFICIENT claims: write "insufficient evidence to conclude" not "may support"
- Cover BR synthesis as final judgment

## Checks
- Natural paragraphs, NOT table rendering
- No claim ID or ALLOWED_USE_BLOCKED in body
- Wording consistent with support_level
- BR asymmetry acknowledged in conclusion
- 5+ human-reviewed conclusions
