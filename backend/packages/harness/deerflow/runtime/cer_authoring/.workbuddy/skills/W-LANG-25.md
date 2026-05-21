# W-LANG-25: Language Style Quantified Constraints

- **Type**: Few-shot + Quantified
- **Step**: CER Writing (all sub-steps)
- **Batch**: P0
- **Agent**: authoring-cer-writer-agent

## Quantified Constraints
1. Sentence length: 22-32 words (§1-§4), ≤ 20 words (§5 Conclusions)
2. Paragraph length: 25-40 words. Table-bridging paragraphs: 10-20 words
3. Each paragraph: 1 core argument + supporting evidence
4. Passive-to-active ratio: 1:3 to 1:4
5. Hedging density: ≥ 2 per 100 words in §3 (SOTA uncertainty) and §4.7 (evidence limitations)
6. Certainty density: ≤ 3 per 100 words in §5 (conclusions must remain measured)
7. Evidence Strength → Wording Map (strict, see W-CONC-23)
8. SOTA Confidence → Wording Map:
   - high → demonstrates / clearly / is within or superior to
   - medium → indicates / generally / is comparable to
   - low → suggests / cautiously / appears consistent with
   - insufficient_data → is not yet established / cannot be compared to

## Wording Replacements (20+ items)
| Avoid | Use |
|-------|-----|
| show | demonstrate / indicate |
| prove | establish / confirm |
| good | favourable / acceptable |
| bad | adverse / unfavourable |
| a lot | substantial / considerable |
| think / believe | the evidence suggests |
| safe | has an acceptable safety profile |
| works | performs as intended |

## Few-shot Profiles
Provide 3+ human-written CER excerpts as style exemplars for the Writer.

## Checks
- Sentence/paragraph length within quantified bounds (Gate W4 check)
- Passive:active ratio meets threshold
- Evidence strength wording consistent with support level
- SOTA confidence wording consistent with benchmark confidence
