# S-CLAIM-04: Claim Decomposition & Materiality

- **Type**: Few-shot + Prompt+Guard
- **Step**: Claim Decomposition (Step 4)
- **Batch**: P0
- **Agent**: authoring-intake-profile-claim-agent

## Input
- `device_profile` (intended_purpose, warnings, performance claims)
- IFU full text (claim-bearing sections)
- 20+ engineer-provided few-shot examples

## Output
- `claim_ledger`: claim_id, claim_text, claim_type, source_location, required_evidence_type
- `intended_purpose_claim_table`

## Decision Logic
1. Scan IFU for claim-bearing sentences (declarative statements about device effect/performance/safety)
2. Classify each sentence:
   - `intended_purpose` / `clinical_benefit`: clinical outcome claims → PubMed/CT.gov
   - `safety`: risk/safety claims → clinical + PMS + vigilance
   - `performance`: technical performance → bench test + IFU
   - `IFU_warning` / `warning_contraindication`: warnings → RMF/GSPR
3. Apply materiality rules:
   - Material if sentence describes clinical outcome, safety profile, or device capability
   - Non-material: packaging, administrative, logistics
4. Each claim gets `required_evidence_type` from `CLAIM_TYPE_SOURCE_ROUTING`
5. Output includes `source_location` (page/paragraph in IFU)

## Checks
- Recall ≥ 90% on 10 test IFUs
- Precision ≥ 85%
- Every claim has `claim_type` and `source_location`
- HC-02 human confirmation point validates output
