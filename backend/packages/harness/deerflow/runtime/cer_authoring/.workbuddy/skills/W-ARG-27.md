# W-ARG-27: Argumentation Logic Organization

- **Type**: Prompt+Guard
- **Step**: CER Writing (§4-§5 argumentation)
- **Batch**: P0
- **Agent**: authoring-cer-writer-agent

## Input
- `claim_support_matrix`
- `benefit_risk_ledger`
- `writer_conclusion_constraints`

## Output
- Coherent argumentation structure for §4-§5

## Argumentation Framework
**Clinical Theme Grouping** (not GSPR number ordering):
- Safety Theme: GSPR 1, 2, 8, 11 → "The device's safety profile is evaluated across..."
- Performance Theme: GSPR 3, 4, 6, 15 → "Performance characteristics demonstrate..."
- Risk Control Theme: GSPR 5, 8 → "Risk control measures address..."
- Design Verification Theme: GSPR 7, 9, 10 → "Design and material properties..."

**Triad Structure per Argument**: Problem → Evidence → Conclusion
1. **Problem**: What clinical question are we answering? (One sentence)
2. **Evidence**: What data answers it? (Multiple sources synthesized)
3. **Conclusion**: What does this mean for conformity? (Strength-calibrated)

**Transition Rules**: Between GSPR groups, use clinical logic transitions (not "Next, GSPR X..."):
- "Building on the safety evaluation above, the performance data further support..."
- "Complementing the clinical evidence, the bench test results confirm..."

**Conflict Synthesis**: When multiple evidence sources disagree:
- Consistent direction → synthesize "The body of evidence consistently..."
- Contradictory → flag "However, [source B] reported conflicting results..."
- Insufficient → acknowledge "Further data are needed to resolve the uncertainty regarding..."

## Checks
- GSPR groups have thematic intro/transition paragraphs
- Triad structure (Problem→Evidence→Conclusion) present
- Conflicts acknowledged, not forced into consensus
- 5+ human-reviewed argumentation organizations
