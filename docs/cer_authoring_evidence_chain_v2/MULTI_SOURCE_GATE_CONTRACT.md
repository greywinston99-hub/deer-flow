# MULTI-SOURCE GATE CONTRACT — V2 (REVISED)

> CCD 签发 | 2026-05-12

## Required Source Profile（per claim）

Instead of static rules, use `required_source_profile` by:
`claim_type × device_class × risk_level × available_data_profile`

| Claim Type | Required (ALL must have ≥1) | Optional (at least N from) |
|---|---|---|
| clinical_benefit | subject_device OR literature | similar_device, registry |
| clinical_safety | subject_device OR literature AND (vigilance OR PMCF) | similar_device |
| IFU_safety_warning | IFU AND RMF | GSPR |
| performance | test_performance | literature, similar_device |
| SOTA_benchmark | literature | similar_device, registry |
| risk_control | RMF AND IFU | GSPR |
| PMCF_boundary | PMS_PMCF | literature |

## AND/OR Logic

- `A AND B`: both source types must have ≥1 qualifying evidence
- `A OR B`: at least one source type must have ≥1 qualifying evidence
- `A AND (B OR C)`: A required, plus either B or C

## Multi-Source REWORK Routing

| Failure | Route |
|---|---|
| Missing subject-device clinical | human supplement queue |
| Similar/competitor not classified | evidence classification node |
| Allowed-use violation | claim type review or evidence re-classification |
| Missing-data blocking pivotal | human supplement OR controlled_compromise |
| Source type mismatch | correct source pipeline |
| Source requirement not met（AND clause）| specific missing source type acquisition |
| Source requirement not met（OR clause）| try alternative source type |

## Writer Consumption Guard

Writer may only consume evidence where:
- All AND requirements for the claim's claim_type are met
- `device_relationship` permits use per SIMILAR_COMPETITOR_EVIDENCE_SPEC
- `allowed_conclusion_strength_max` ≥ required by claim

---

*CCD 签发：2026-05-12*
