# BIGDP2026.6V_2 — Architecture Fit Check

**Date:** 2026-06-08

---

## DC-1: Retrieval recall → Extend search_run_registry

| Decision | Rationale |
|:---|:---|
| Extend existing artifact | `search_run_registry` already exists. Add mandatory fields: query_string, total_hits, humans_filter, excluded_count. |
| Extend existing gate | G30 (SOTA Endpoint Gate) can check search completeness. |
| No new node needed | Enhancement is field-level, not node-level. |

## DC-2: Query reproducibility → Extend G30

| Decision | Rationale |
|:---|:---|
| Extend existing gate | G30 already validates search results. Add query_string presence check. |
| No new module | Simple validation rule. |

## DC-3: Screening exclusion → Extend literature_screening + existing rules

| Decision | Rationale |
|:---|:---|
| Extend existing node | `_node_literature_screening` already has `_auto_classify_exclusion()`. Add N<10 and animal exclusion enforcement. |
| Add validator | New `exclusion_rule_validator` as function in gates.py, not new node. |
| No new DAG node | Rules are enforced at screening time. |

## DC-4: PMID traceability → Extend clinical_fact_registry

| Decision | Rationale |
|:---|:---|
| Extend existing node | `_node_extract_clinical_facts` (P0-1) already anchors facts to PMID. Add source_anchor field. |
| Add validator | `_validate_fact_source_anchoring` in gates.py. |
| No new module | Enhancement of existing extraction logic. |

## DC-5: Fulltext policy → Extend fulltext_basis_gate

| Decision | Rationale |
|:---|:---|
| Extend existing gate | `fulltext_basis_gate` already checks pivotal fulltext. Add abstract_only constraint. |
| No new node | Policy enforcement at existing gate. |

## DC-6: Endpoint semantics → Extend expert_rule_loader

| Decision | Rationale |
|:---|:---|
| Extend existing rule loader | Add AE classification taxonomy to `expert_rule_loader.py`. |
| Add test only | Classification rules are configuration, not new runtime module. |

## DC-7: Comparator benchmark → Extend benchmark_derivation_trace

| Decision | Rationale |
|:---|:---|
| Extend existing artifact | `BENCHMARK_DERIVATION_TRACE` already has directness/confidence/rationale. Add comparator-specific fields. |
| No new node | Enhancement of existing trace. |

## DC-8/9: SOTA accounting → Extend PRISMA + add reconciler

| Decision | Rationale |
|:---|:---|
| Extend existing node | PRISMA already generates flow numbers. Add accounting reconciliation in `_node_prisma_flow_review`. |
| Add validator | `_reconcile_sota_accounting()` in gates.py. |
| No new module | Accounting is a consistency check on existing data. |

## DC-10: Denominator/subgroup → Add validator

| Decision | Rationale |
|:---|:---|
| Add validator | `_validate_denominator_consistency()` in gates.py. Checks total_N vs subgroup_n, percentage recalc. |
| Add test only | Validator function, not new DAG node. |

## DC-11: Writer consistency → Extend package validator

| Decision | Rationale |
|:---|:---|
| Extend existing validator | `cer_package_validator.py` already has 8 assertions. Add semantic constraint checks. |
| No new module | Enhancement of existing validator. |

---

## Summary

| Decision | Count |
|:---|:---|
| Extend existing artifact/node/gate | 9 |
| Add validator (function, not node) | 4 |
| Add new DAG node | 0 |
| Add new module | 0 |
| Add test only | 1 |

**No new DAG nodes needed. No new modules needed. All changes extend existing BIGDP2026.6 architecture.**
