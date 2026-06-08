# HARD GATE ROUTING SPEC — V3 (FROZEN)

> CCD 签发 | 2026-05-11 | Phase 0 Architecture Freeze

## Gate Types

| ID | Name | Stage | Checks |
|---|---|---|---|
| G1c/G1d | Device Identity | device_profile | IFU role, identity lock |
| G39 | Retrieval Domain Mismatch | sota_search | Query domain ≠ device domain? |
| G40 | Screening Pool Shallow | screening | Pool below device-class minimum? (30 = floor, not universal) |
| G41 | Full-Text Basis Inadequate | appraisal | Pivotal items lack full text? |
| G30 | SOTA Not Established | endpoint | Benchmarks derived or NR+rationale? |
| G42 | Evidence Insufficient Per Claim | sufficiency_gate | Each claim has ≥1 pivotal/supportive with applicability+directness+fulltext+endpoint match? |
| G43 | Claim-Evidence Incomplete | claim_evidence | Every claim linked to evidence? |
| G44 | BR Not Justified | benefit_risk | BR based on evidence, not template? |
| G45 | Alignment Not Ready | alignment | CER↔IFU/RMF/GSPR consistent? |
| G46 | Pre-Writer Readiness | pre_writer | All 9 sub-conditions PASS? |
| G38 | Conclusion Strength | final | Wording matches evidence level? |

## Routing Matrix

| Gate | PASS→ | REWORK→ | BLOCKED→ |
|---|---|---|---|
| G1c/G1d | claim | device_profile | HUMAN_HOLD |
| G39 | screening | sota_search(fix query) | COMPROMISE |
| G40 | appraisal | sota_search(expand) | COMPROMISE |
| G41* | endpoint or spiral or COMPROMISE | per failure_pattern | COMPROMISE |
| G30* | claim_evidence or spiral | per failure_pattern | COMPROMISE |
| G42 | claim_evidence | sota_search(spiral) | COMPROMISE |
| G43 | gap_pmcf | claim_evidence(re-link) | COMPROMISE |
| G44 | alignment | benefit_risk(re-justify) | COMPROMISE |
| G45 | pre_writer | alignment(re-align) | COMPROMISE |
| G46 | Writer(PASS) | upstream causality priority | COMPROMISE |
| G38 | export | Writer(fix wording) | **N/A — G38 has no BLOCKED** |

## G38: PASS/REWORK only。No BLOCKED。

G38 cannot BLOCKED→REWORK。PASS/REWORK only。
If wording cannot be fixed → REWORK with explicit reason。

## G30/G41: Failure-Pattern-Aware Routing

| Gate | Failure Pattern | REWORK Route |
|---|---|---|
| G41 | full_text_unavailable | fulltext_acquisition → re-appraise OR COMPROMISE |
| G41 | full_text_not_consumed | evidence_appraisal(re-evaluate with full text) |
| G30 | no_benchmark_derivable_from_pool | sota_search(spiral re-entry for more evidence) |
| G30 | benchmark_fields_incomplete | endpoint_extraction(re-derive with current pool) |

## G46: Upstream Causality Priority (not first-failure list order)

If multiple sub-conditions fail simultaneously, route by upstream causality:

1. Identity/domain errors first (G1c/G1d, G39)
2. Evidence acquisition errors (G40, G41)
3. Evidence sufficiency (G42)
4. Reasoning chain errors (G30, G43, G44)
5. Alignment errors last (G45)

Route to the most-upstream failing condition, not the first in list order.

## REWORK vs BLOCKED vs HUMAN_HOLD

| REWORK | BLOCKED→COMPROMISE | HUMAN_HOLD |
|---|---|---|
| Fixable in graph | Terminal for this run | Cannot proceed without human input |
| Bounded retry | Human decision required before restart | Device misclassified, IFU missing, etc. |
| Auto-route to upstream node | Outputs insufficiency report, no CER | Stop immediately |

---

*CCD 签发：2026-05-11*
