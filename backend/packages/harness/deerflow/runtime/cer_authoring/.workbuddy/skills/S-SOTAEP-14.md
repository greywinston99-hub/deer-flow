# S-SOTAEP-14: SOTA Endpoint Derivation Standards

- **Type**: Deterministic
- **Step**: SOTA Endpoint Gate (G30, Step 14A)
- **Batch**: P2
- **Agent**: authoring-methodology-sota-agent

## Input
- `sota_benchmark_matrix`
- `endpoint_extraction` from appraised evidence
- `sota_endpoint_derivation_table`

## Output
- `sota_quantitative_benchmark_table` with quality_weighted_median, comparability_score
- Gate routing: PASS / REWORK / BLOCKED

## Decision Logic
1. Benchmark derivable when: ≥ 3 high-quality comparable studies available
2. < 3 studies → qualitative description only (no quantitative benchmark)
3. Confidence tiers:
   - High: ≥ 5 studies, I² < 30%, consistent outcomes
   - Medium: 3-5 studies, I² 30-60%, mostly consistent
   - Low: < 3 studies or I² > 60%
   - Insufficient: single study or incompatible endpoints
4. Quality-weighted median: weight by study design score and device applicability
5. Exclusion reasons recorded for each excluded study

## Checks
- Benchmark methodology documented
- ≥ 3 studies for quantitative benchmark
- Exclusion reasons recorded
- Confidence tier consistent with evidence quality
