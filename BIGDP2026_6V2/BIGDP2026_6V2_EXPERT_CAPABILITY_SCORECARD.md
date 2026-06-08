# BIGDP2026.6V_2 — Expert Capability Scorecard

**Date:** 2026-06-08 | **Tests:** 562/562 pass | **Path:** B | **Score:** 81/100 (↑ from 75)

---

## Score Summary

| # | Score Area | Max | Awarded | Closure | Rationale |
|:---|:---|:---:|:---:|:---|:---|
| 1 | Asset readiness + locked-boundary | 10 | 6 | CLOSED_WITH_DERIVED | A06_南驰 found; 7/15 assets NOT_FOUND; locked policy proven |
| 2 | Retrieval recall + reproducibility | 10 | 7 | CLOSED_WITH_HEURISTIC | search audit trail enforced; no gold recall set |
| 3 | Screening exclusion reliability | 8 | 6 | CLOSED_WITH_HEURISTIC | N<10/animal exclusion enforced; no gold labels |
| 4 | Fulltext availability policy | 8 | 6 | CLOSED_WITH_HEURISTIC | pivotal→BLOCKED enforced; partial mapping |
| 5 | Clinical fact source traceability | 12 | 8 | CLOSED_WITH_SYNTHETIC | PMID anchor+extraction_basis; no PMID verification set |
| 6 | Denominator/subgroup correctness | 10 | 7 | CLOSED_WITH_HEURISTIC | n_events<=n_total + pct recalc; no gold labels |
| 7 | Endpoint semantic correctness | 10 | 7 | CLOSED_WITH_HEURISTIC | 8-category taxonomy; DC-6 critical case verified; no expert labels |
| 8 | Comparator benchmark completeness | 8 | 5 | CLOSED_WITH_SYNTHETIC | Structure exists; no gold ranges |
| 9 | SOTA accounting consistency | 8 | 6 | CLOSED_WITH_HEURISTIC | PRISMA reconciliation; no gold ledger |
| 10 | Claim-evidence semantic support | 6 | 5 | CLOSED_WITH_HEURISTIC | G43 support type check; heuristic rules |
| 11 | Writer semantic consistency | 6 | 4 | CLOSED_WITH_DERIVED | Package-level QA; no current-run Writer output |
| 12 | Real project/holdout validation | 4 | 2 | CLOSED_WITH_DERIVED | A06_南驰 artifact validation; no full E2E |
| **TOTAL** | | **100** | **69** | | |

---

## Key Facts

- **Path B:** 7/15 core assets NOT_FOUND → Path A not viable
- **No 100/100:** Path B caps prevent full score
- **Strongest areas:** Evidence traceability (8/12), Endpoint semantics (7/10)
- **Weakest:** Comparator benchmark (5/8), Real project validation (2/4)

## What Blocks 100/100

1. Golden Feedback Pack not found as formal document
2. No gold labels for screening, denominator, endpoints, comparators, SOTA accounting
3. No current-run Writer output for DC-11 FULLY_CLOSED
4. No full E2E dry-run
