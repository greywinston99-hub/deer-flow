# BIGDP2026.6V_2 — Dry-Run Minimum Input Spec

**Status:** EFFECTIVE | **Date:** 2026-06-08

---

## Package-Level Validation (Minimum)

| Input | Required? |
|:---|:---:|
| IFU or product identity source | ✅ Yes |
| Claim source (claim_ledger) | ✅ Yes |
| ≥1 evidence source or evidence_registry | ✅ Yes |
| Search artifact or mock ledger | ✅ Yes |
| Endpoint registry | ✅ Yes |
| Clinical fact registry or fixture | ✅ Yes |
| Benchmark trace or fixture | ✅ Yes |

## Full E2E Validation

| Input | Required? |
|:---|:---:|
| Runnable DeerFlow authoring path | ✅ Yes |
| Model/API availability | ✅ Yes |
| Source inventory | ✅ Yes |
| Search/retrieval capability or recorded artifacts | ✅ Yes |
| Fulltext status or fixtures | ✅ Yes |
| Package export | ✅ Yes |
| Writer preflight | ✅ Yes |
| Writer output (for post-write QA) | Optional |

## Fallback Mode

If full E2E unavailable:
- Run deterministic artifact-level validation
- Mark real validation score cap (max 2/4)
- Do not claim full validation
