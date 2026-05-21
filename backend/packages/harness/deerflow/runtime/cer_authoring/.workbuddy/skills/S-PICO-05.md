# S-PICO-05: PICO Precision Boundaries

- **Type**: Prompt+Guard
- **Step**: PICO Derivation (Step 5)
- **Batch**: P2
- **Agent**: authoring-methodology-sota-agent

## Input
- `claim_ledger` (only clinical_benefit and safety type claims)
- `device_profile` (target_population, intended_purpose)
- Domain context from `DOMAIN_DEFAULTS`

## Output
- `cep_pico_matrix`: Population, Intervention, Comparator, Outcome per claim
- `sota_pico_strategy`: search-ready MeSH + synonym terms

## Decision Logic
1. Only process claims with `claim_type` in {clinical_benefit, intended_purpose, safety, performance}
2. Skip `IFU_warning` / `warning_contraindication` types (evidence from RMF, not PubMed)
3. Population: precise to the indication (not generalized to "patients")
4. Intervention: the subject device under its intended use conditions
5. Comparator: current standard of care or SOTA alternative treatment
6. Outcome: measurable clinical endpoint linked to the claim
7. Generate MeSH terms + 2-3 synonyms per PICO element

## Checks
- IFU_warning claims NOT in `cep_pico_matrix`
- Population is specific to indication
- Each PICO has MeSH terms and synonyms
- Comparator has documented selection rationale
