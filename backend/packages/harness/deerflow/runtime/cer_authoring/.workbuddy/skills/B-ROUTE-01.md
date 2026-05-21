# B-ROUTE-01: Claim Type → Evidence Source Routing

- **Type**: Deterministic
- **Step**: Claim Decomposition + SOTA Search (Steps 4, 7)
- **Batch**: P0
- **Agent**: authoring-intake-profile-claim-agent

## Input
- `claim_ledger` with `claim_type` per claim
- `CLAIM_TYPE_SOURCE_ROUTING` configuration

## Output
- Each claim tagged with `primary_source`, `fallback_source`
- Search strategy selection per claim type

## Routing Table
| claim_type | primary_source | fallback_source | excluded_source |
|-----------|---------------|----------------|----------------|
| clinical_benefit | PubMed/CT.gov | equivalent_device | — |
| intended_purpose | PubMed/CT.gov | equivalent_device | — |
| safety | clinical+PMS+vigilance | PubMed/CT.gov | — |
| performance | PubMed/CT.gov | bench_test | — |
| IFU_warning | RMF/GSPR | PMS | PubMed |
| warning_contraindication | RMF/GSPR | PMS | PubMed |
| technical | bench_test/IFU | equivalent_device | — |

## Decision Logic
1. At claim creation (Step 4): auto-tag `primary_source` + `fallback_source`
2. At search (Step 7): skip PubMed if claim_type in {IFU_warning, warning_contraindication}
3. At G42 (Step 16A): validate sufficiency against source-specific thresholds
4. Routing configurable via `CLAIM_TYPE_SOURCE_ROUTING` constant

## Checks
- All claims have `primary_source` populated
- IFU_warning claims skip PubMed search
- Routing rules documented and configurable
