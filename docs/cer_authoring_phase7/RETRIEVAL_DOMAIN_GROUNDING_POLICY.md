# Retrieval Domain Grounding Policy

## Policy
Evidence retrieval must remain grounded in the locked device identity and IFU-defined clinical use.

## Required Checks
Before any paper can support Writer conclusions, the runtime compares:

- locked clinical/device domain;
- constructed query domain;
- retrieved literature domain;
- screening domain judgement;
- evidence appraisal domain.

## Mismatch Handling
If a retrieved item matches wrong-domain exclusion terms and lacks same-domain inclusion terms, it is marked:

`RETRIEVAL_DOMAIN_MISMATCH_REWORK_REQUIRED`

Such items are excluded before appraisal and cannot become pivotal or supportive evidence.

If an item contains both same-domain and wrong-domain terms, it is retained only with review status:

`DOMAIN_MATCH_WITH_WRONG_DOMAIN_CONTEXT_REVIEW`

## PILOT-01 Principle
For IFU use in joint surgery, soft-tissue resection, ablation, coagulation, or hemostasis, cardiac EP/cardiovascular ablation literature cannot be used as clinical evidence unless explicitly limited to technical background. It cannot support SOTA benchmark values, pivotal evidence, or Writer benefit-risk conclusions for orthopedic use.

## Writer Rule
Writer may consume only evidence rows marked `ledger_approved_for_writer=True` and not marked retrieval-domain mismatch.
