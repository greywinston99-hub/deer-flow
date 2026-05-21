# S-ALIGN-XX: Claim-SOTA-Conclusion Three-Way Alignment

- **Type**: Deterministic
- **Step**: Claim-SOTA Alignment (Step 20B, V2 NEW)
- **Batch**: P0
- **Agent**: authoring-evidence-agent

## Input
- `claim_ledger` (all claims)
- `sota_benchmark_matrix` (all SOTA benchmarks)
- `sota_clinical_context_table`

## Output
- `claim_sota_alignment_table`: claim_id, claim_text, claim_type, matched_benchmark_ids, benchmark_confidence, feasibility (supported/partial/unsupported), recommendation
- `sota_alignment_status`: PASS / CAUTION / BLOCKED
- `trigger_profile_iteration`: true when unsupported > 0 or partial ≥ 3

## Decision Logic
1. For each claim, match to SOTA benchmarks by endpoint token overlap
2. Feasibility judgment:
   - ≥ 1 high/medium confidence benchmark match → supported
   - Only low confidence matches → partial
   - Zero matches → unsupported
3. Unsupported → recommend claim scope adjustment or PMCF planning
4. Partial → recommend cautious wording, consider endpoint substitution
5. BLOCKED status when any claim is unsupported
6. Trigger profile iteration when unsupported > 0 or partial ≥ 3

## Checks
- 10+ human-validated alignment cases
- Unsupported claims trigger `device_profile_iteration`
- HC-07 human gate confirms alignment results
- `claim_feasibility` field propagated to claim_ledger
