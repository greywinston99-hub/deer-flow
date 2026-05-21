# S-BRALIGN-17: Cross-Evidence Synthesis & BR Alignment

- **Type**: Prompt+Guard
- **Step**: Writer Synthesis → G46 (Steps 22-27)
- **Batch**: P1
- **Agent**: authoring-cer-writer-agent

## Input
- `cross_evidence_synthesis_table`
- `benefit_risk_ledger`
- `alignment_matrix`
- G46 9-condition readiness report

## Output
- `cross_evidence_synthesis_narratives`
- `writer_synthesis_trace`
- BR conclusion with evidence quality asymmetry flag

## Decision Logic
1. Evidence conflict resolution:
   - Consistent direction → synthesize positive/negative conclusion
   - Contradictory direction → mark uncertainty, do not force conclusion
   - Insufficient → flag as gap, recommend PMCF
2. BR asymmetry handling:
   - Benefit from RCT (high quality) + Risk from PMS (lower quality) → flag `br_asymmetry_flag`
   - Asymmetry constrains conclusion wording: no "clearly favourable"
3. G46 9-condition failure repair priority (identity > retrieval > screening > fulltext > evidence_sufficiency > SOTA > claim_evidence > BR > alignment)
4. Evidence quality tier: benefit_evidence_quality_tier vs risk_evidence_quality_tier

## Checks
- Contradictory evidence not forced into false consensus
- `br_asymmetry_flag` set when quality tiers differ
- G46 repair follows documented priority order
- 5+ human-validated synthesis cases
