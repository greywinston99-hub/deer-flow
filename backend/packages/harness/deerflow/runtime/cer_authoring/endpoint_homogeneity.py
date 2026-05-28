"""WS6: Endpoint Homogeneity Gate.

Checks whether endpoints can be meaningfully compared across studies.
Heterogeneous endpoints must downgrade conclusion strength or become PMCF
objectives.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

HOMOGENEITY_DIMENSIONS = [
    "endpoint_family",
    "endpoint_definition",
    "measurement_method",
    "unit",
    "timepoint",
    "population",
    "comparator",
]


def _check_dimension_compatibility(
    dim: str,
    values: list[str],
) -> tuple[bool, str]:
    """Check if all values for a dimension are compatible."""
    unique = list({v.strip().lower() for v in values if v.strip()})
    if len(unique) <= 1:
        return True, ""
    return False, f"Incompatible {dim}: {unique}"


def build_endpoint_homogeneity_matrix(
    endpoints: list[dict[str, Any]] | None = None,
    benchmark_endpoints: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Assess endpoint homogeneity across studies for benchmark derivation.

    Returns a matrix showing which endpoints are homogeneous enough to
    combine into a single benchmark or meta-analytic conclusion.
    """
    now = datetime.now(timezone.utc).isoformat()
    endpoints = endpoints or []
    benchmark_endpoints = benchmark_endpoints or []
    all_endpoints = list(endpoints) + list(benchmark_endpoints)

    families: dict[str, list[dict[str, Any]]] = {}
    for ep in all_endpoints:
        family = str(ep.get("endpoint_family") or ep.get("family") or ep.get("name") or "unknown").lower()
        families.setdefault(family, []).append(ep)

    rows: list[dict[str, Any]] = []
    homogeneous_count = 0
    heterogeneous_count = 0
    downgraded_families: list[str] = []

    for family, members in families.items():
        dim_values: dict[str, list[str]] = {d: [] for d in HOMOGENEITY_DIMENSIONS}
        for m in members:
            for d in HOMOGENEITY_DIMENSIONS:
                val = str(m.get(d) or m.get(d.replace("_", " ")) or "")
                if val:
                    dim_values[d].append(val)

        issues: list[str] = []
        homogeneous = True
        for dim in HOMOGENEITY_DIMENSIONS:
            ok, msg = _check_dimension_compatibility(dim, dim_values[dim])
            if not ok:
                homogeneous = False
                issues.append(msg)

        if not homogeneous:
            heterogeneous_count += 1
            downgraded_families.append(family)
        else:
            homogeneous_count += 1

        rows.append({
            "endpoint_family": family,
            "member_count": len(members),
            "endpoint_definitions": sorted(set(str(m.get("endpoint_definition") or m.get("definition") or "") for m in members)),
            "measurement_methods": sorted(set(str(m.get("measurement_method") or m.get("method") or "") for m in members)),
            "units": sorted(set(str(m.get("unit") or "") for m in members)),
            "timepoints": sorted(set(str(m.get("timepoint") or "") for m in members)),
            "populations": sorted(set(str(m.get("population") or "") for m in members)),
            "comparators": sorted(set(str(m.get("comparator") or "") for m in members)),
            "homogeneous_for_benchmark": homogeneous,
            "compatibility_issues": issues,
            "acceptable_substitutions": [],
            "substitution_rationale": "",
            "downgraded": not homogeneous,
        })

    return {
        "schema": "endpoint_homogeneity_matrix_v1",
        "generated_at": now,
        "summary": {
            "total_endpoint_families": len(families),
            "homogeneous_count": homogeneous_count,
            "heterogeneous_count": heterogeneous_count,
            "downgraded_families": downgraded_families,
            "benchmark_derivation_safe": heterogeneous_count == 0,
            "conclusion_downgrade_required": heterogeneous_count > 0,
        },
        "rows": rows,
    }
