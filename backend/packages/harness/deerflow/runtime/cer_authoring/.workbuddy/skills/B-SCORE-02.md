# B-SCORE-02: Score → Weight Consumption Chain

- **Type**: Deterministic
- **Step**: Claim-Evidence Matrix (Step 17A)
- **Batch**: P0
- **Agent**: authoring-evidence-agent

## Input
- `article_appraisal`: evidence_strength_score (0-100)
- `evidence_registry`: evidence weight (pivotal/supportive/background/excluded)

## Output
- `claim_support_matrix` with `weighted_support_score`
- `writer_conclusion_constraints` with per-claim strength limits

## Weight Formula
```
weighted_support_score = Σ(evidence_strength_score × relevance_weight) / Σ(relevance_weight)
```

## Score → Support Level Thresholds
| Score Range | Max Support Level | Notes |
|------------|------------------|-------|
| < 40 | INSUFFICIENT or CAUTIOUS (background) | Cannot support MODERATE+ alone |
| 40-60 | CAUTIOUS | Needs supporting evidence |
| 60-80 | MODERATE | Acceptable with corroboration |
| > 80 | STRONG | Requires multi-source (>1 independent) |

## Oxford Level → Support Level
| Oxford Level | Max Conclusion Strength |
|-------------|------------------------|
| 1a (SR of RCTs) | STRONG |
| 1b (RCT) | STRONG |
| 2a-2b (cohort) | MODERATE |
| 3a-3b (case-control) | CAUTIOUS |
| 4 (case series) | CAUTIOUS |
| 5 (expert opinion) | INSUFFICIENT |

## Checks
- < 40 score never supports MODERATE+ alone
- > 80 score requires multi-source for STRONG
- Oxford Level constraints applied via G12
- 10+ engineer-calibrated scoring cases
