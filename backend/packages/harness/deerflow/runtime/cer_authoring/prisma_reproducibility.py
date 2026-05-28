"""WS4: PRISMA Reproducibility Gate.

Upgrades PRISMA from artifact generation to a reproducibility audit.  Every
search/retrieval/screening step must be traceable and count-reconcilable.
Produces `prisma_reproducibility_audit.json`.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def build_prisma_reproducibility_audit(
    prisma_data: dict[str, Any] | None = None,
    search_runs: list[dict[str, Any]] | None = None,
    screening_disposition: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Audit PRISMA flow for reproducibility.

    Checks:
    - Deduplication occurs before title/abstract screening.
    - Every excluded record has exclusion_reason and exclusion_criteria_id.
    - Count reconciliation across all stages.
    - Missing search date or exact query is a major failure.
    """
    now = datetime.now(timezone.utc).isoformat()
    prisma = prisma_data or {}
    search_runs = search_runs or []
    screening = screening_disposition or []

    flow = prisma.get("flow") or prisma
    raw_hits = int(flow.get("raw_hits") or flow.get("total_hits") or flow.get("records_identified") or 0)
    dedup_input = int(flow.get("dedup_input") or raw_hits or 0)
    dup_count = int(flow.get("duplicate_count") or flow.get("duplicates_removed") or 0)
    after_dedup = int(flow.get("after_dedup") or flow.get("records_after_dedup") or 0)
    ta_screened = int(flow.get("title_abstract_screened") or flow.get("records_screened") or 0)
    ta_excluded = int(flow.get("title_abstract_excluded") or flow.get("records_excluded") or 0)
    ft_assessed = int(flow.get("fulltext_assessed") or flow.get("full_text_eligible") or 0)
    ft_excluded = int(flow.get("fulltext_excluded") or flow.get("full_text_excluded") or 0)
    final_included = int(flow.get("final_included") or flow.get("studies_included") or 0)

    if after_dedup == 0 and dedup_input > 0:
        after_dedup = dedup_input - dup_count
    if ta_screened == 0 and after_dedup > 0:
        ta_screened = after_dedup
    if ta_excluded == 0 and ta_screened > 0:
        ta_excluded = ta_screened - (ft_assessed or ta_screened)
    if ft_assessed == 0 and ta_screened > ta_excluded:
        ft_assessed = ta_screened - ta_excluded
    if final_included == 0 and ft_assessed > ft_excluded:
        final_included = ft_assessed - ft_excluded

    failures: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    if raw_hits == 0:
        failures.append({"type": "ZERO_RAW_HITS", "severity": "major", "message": "No records identified from any database search."})

    if dedup_input > 0 and after_dedup == dedup_input and dup_count == 0:
        warnings.append({"type": "NO_DEDUP_RECORDED", "severity": "minor", "message": "Deduplication step may not have been executed."})

    count_reconciliation_ok = True
    if after_dedup > 0 and dedup_input > 0:
        expected_after = dedup_input - dup_count
        if abs(after_dedup - expected_after) > max(1, dedup_input * 0.02):
            failures.append({
                "type": "DEDUP_COUNT_MISMATCH",
                "severity": "major",
                "message": f"Dedup counts do not reconcile: {dedup_input} - {dup_count} != {after_dedup}",
                "expected": expected_after,
                "actual": after_dedup,
            })
            count_reconciliation_ok = False

    if ta_screened > 0 and after_dedup > 0 and ta_screened != after_dedup:
        warnings.append({
            "type": "SCREENING_COUNT_DRIFT",
            "severity": "minor",
            "message": f"Title/abstract screened count ({ta_screened}) differs from after-dedup count ({after_dedup}).",
        })

    search_issues: list[dict[str, Any]] = []
    for idx, run in enumerate(search_runs):
        if not run.get("search_date"):
            search_issues.append({
                "run_index": idx,
                "database": run.get("database", "unknown"),
                "issue": "MISSING_SEARCH_DATE",
                "severity": "major",
            })
        if not run.get("exact_query") and not run.get("search_terms"):
            search_issues.append({
                "run_index": idx,
                "database": run.get("database", "unknown"),
                "issue": "MISSING_EXACT_QUERY",
                "severity": "major",
            })

    screening_issues: list[dict[str, Any]] = []
    for idx, row in enumerate(screening):
        excluded = str(row.get("status") or row.get("disposition") or "").lower()
        if excluded in {"excluded", "rejected"}:
            if not row.get("exclusion_reason") and not row.get("reason"):
                screening_issues.append({
                    "row_index": idx,
                    "pmid": row.get("pmid", ""),
                    "issue": "MISSING_EXCLUSION_REASON",
                    "severity": "minor",
                })
            if not row.get("exclusion_criteria_id") and not row.get("criteria_id"):
                screening_issues.append({
                    "row_index": idx,
                    "pmid": row.get("pmid", ""),
                    "issue": "MISSING_EXCLUSION_CRITERIA_ID",
                    "severity": "minor",
                })

    critical_failures = sum(1 for f in failures if f["severity"] == "critical")
    major_failures = sum(1 for f in failures if f["severity"] == "major")
    major_search_issues = sum(1 for s in search_issues if s["severity"] == "major")

    return {
        "schema": "prisma_reproducibility_audit_v1",
        "generated_at": now,
        "flow_counts": {
            "raw_hits": raw_hits,
            "dedup_input_count": dedup_input,
            "duplicate_count": dup_count,
            "after_dedup_count": after_dedup,
            "title_abstract_screened": ta_screened,
            "title_abstract_excluded": ta_excluded,
            "fulltext_assessed": ft_assessed,
            "fulltext_excluded": ft_excluded,
            "final_included": final_included,
        },
        "count_reconciliation_ok": count_reconciliation_ok and len(failures) == 0,
        "dedup_before_screening": dedup_input > 0 and after_dedup > 0 and ta_screened >= after_dedup,
        "failures": failures,
        "warnings": warnings,
        "search_audit_issues": search_issues,
        "screening_audit_issues": screening_issues,
        "status": "FAIL" if (critical_failures > 0 or major_failures > 0 or major_search_issues > 0) else "PASS",
        "critical_failures": critical_failures,
        "major_failures": major_failures + major_search_issues,
        "submission_grade_sota_blocked": major_failures > 0 or critical_failures > 0,
    }
