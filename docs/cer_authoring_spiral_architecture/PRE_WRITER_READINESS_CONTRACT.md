# PRE-WRITER READINESS CONTRACT — V2 (FROZEN)

> CCD 签发 | 2026-05-11

## 9 Sub-Conditions

Identity, evidence_sufficiency, retrieval_domain, screening_pool, fulltext_basis, SOTA, claim_evidence, BR, alignment。All must PASS。

## Gate Logic

All PASS → Writer invoked。Any REWORK → route by upstream causality priority。Any BLOCKED → COMPROMISE。

## Multi-Failure Routing: Upstream Causality Priority

NOT first-failure-in-list-order。Priority order:

1. Identity/domain (G1c/G1d, G39)
2. Evidence acquisition (G40, G41)
3. Evidence sufficiency (G42)
4. Reasoning chain (G30, G43, G44)
5. Alignment (G45)

Route to most-upstream failing condition。Fixing identity may resolve downstream failures automatically。

## REWORK Targets

| Failing | Route To |
|---|---|
| Identity | device_profile |
| Retrieval domain | sota_search(fix query) |
| Screening shallow | sota_search(expand) |
| Full-text inadequate | evidence_appraisal or fulltext_acquisition |
| Evidence insufficient | sota_search(spiral) |
| SOTA not established | endpoint_extraction or spiral |
| Claim-evidence | claim_evidence_matrix |
| BR not justified | benefit_risk_ledger |
| Alignment | alignment_matrix |

---

*CCD 签发：2026-05-11*
