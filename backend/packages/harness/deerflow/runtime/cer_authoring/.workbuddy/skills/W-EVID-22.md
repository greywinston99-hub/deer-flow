# W-EVID-22: GSPR Argumentation Writing

- **Type**: Prompt+Guard
- **Step**: CER Writing 28.7 (§4.7 Evidence Analysis)
- **Batch**: P0
- **Agent**: authoring-cer-writer-agent

## Input
- `claim_support_matrix` with weighted_support_score
- `writer_conclusion_constraints`
- `gspr_coverage` mapping

## Output
- §4.7 GSPR Analysis: organized by GSPR groups, paragraph format

## Decision Logic (5-paragraph template per GSPR group)
**Paragraph 1 — Requirement Restatement**: "GSPR X.X requires that [requirement text]"
**Paragraph 2 — Evidence Source Identification**: "The following evidence sources are relevant: [list with IDs and types]"
**Paragraph 3 — Evidence Summary**: "The [study/trial/data] demonstrated that [finding with statistical detail]"
**Paragraph 4 — Analysis & Reasoning**: "Based on the above evidence, [clinical interpretation connecting evidence to requirement]"
**Paragraph 5 — Conformity Conclusion**: "Therefore, the device meets GSPR X.X [with strength qualifier]"

## GSPR Grouping (configurable)
- Safety: GSPR 1, 2, 5, 8 (general safety, risk control, benefit-risk)
- Performance: GSPR 3, 4, 6 (performance, design, clinical evaluation)
- Chemical/Physical: GSPR 7, 9, 10 (material properties, biocompatibility)
- Infection/Microbial: GSPR 11 (infection control, sterilization)

## Writing Rules
- NOT a table — narrative paragraphs with clinical logic transitions
- Internal control fields (ALLOWED_USE_BLOCKED) never in body text
- Conclusion wording matches `support_level` from matrix
- Each paragraph cites evidence_id or gap_id

## Checks
- No matrix table rendered in body
- GSPR groups have thematic transitions
- Conclusion strength consistent with matrix
- 5+ human-reviewed GSPR analyses
