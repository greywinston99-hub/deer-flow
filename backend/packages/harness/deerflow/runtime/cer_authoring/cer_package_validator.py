"""BIGDP2026.6 Phase 4: CER Input Package Validator.

Standalone callable module for Claude Code writer skill to validate
CER_INPUT_PACKAGE.json before writing any CER section.

Usage:
    from deerflow.runtime.cer_authoring.cer_package_validator import validate_package

    errors = validate_package(package)
    if errors:
        raise SystemExit(f"CER_INPUT_PACKAGE validation failed: {errors}")
"""
from __future__ import annotations

from typing import Any

# Supported package schema versions
SUPPORTED_SCHEMA_VERSIONS = {"1.0.0"}


def validate_package(package: dict[str, Any]) -> list[str]:
    """Validate CER_INPUT_PACKAGE.json for Claude Code writing.

    Returns a list of error messages. Empty list = valid, Writer may proceed.
    Implements all 8 G.5 runtime assertions.
    """
    errors: list[str] = []

    # G.5.1: Package must exist
    if not package or not isinstance(package, dict):
        return ["CER_INPUT_PACKAGE.json is empty, missing, or not a valid JSON object."]

    # G.5.2: G46 must be PASS
    g46 = package.get("pre_writer_readiness_gate_report") or {}
    g46_status = str(g46.get("status") or "")
    if g46_status != "PASS":
        errors.append(
            f"G.5.2: G46 pre_writer_readiness_gate status is '{g46_status}', expected 'PASS'. "
            "Writer cannot proceed until all pre-writer conditions are met."
        )

    # G.5.3: cer_input_package_exported must be true
    exported = package.get("cer_input_package_exported")
    if not exported:
        errors.append(
            "G.5.3: cer_input_package_exported is not true. "
            "Package was not successfully exported from the DeerFlow pipeline."
        )

    # G.5.4: All claim_ids must resolve
    claim_ledger = package.get("claim_ledger") or []
    claim_ids = {str(c.get("claim_id") or "") for c in claim_ledger}
    claim_ids.discard("")

    claim_matrix = package.get("claim_evidence_matrix") or []
    for row in claim_matrix:
        cid = str(row.get("claim_id") or "")
        if cid and cid not in claim_ids:
            errors.append(
                f"G.5.4: claim_evidence_matrix references unknown claim_id '{cid}'. "
                "Claim must exist in claim_ledger."
            )

    # G.5.5: All evidence_ids must resolve
    evidence_registry = package.get("evidence_registry") or []
    known_eids = {
        str(e.get("evidence_id") or e.get("id") or e.get("pmid") or "")
        for e in evidence_registry
    }
    known_eids.discard("")

    for row in claim_matrix:
        eids = row.get("evidence_ids") or []
        if isinstance(eids, str):
            eids = [eids] if eids else []
        for eid in eids:
            if str(eid) and str(eid) not in known_eids:
                errors.append(
                    f"G.5.5: claim '{row.get('claim_id', '?')}' references unknown evidence_id '{eid}'. "
                    "Evidence must exist in evidence_registry."
                )

    # G.5.6: All benchmark_ids must resolve (if benchmark_trace present)
    benchmark_trace = package.get("benchmark_derivation_trace") or {}
    benchmark_endpoints = benchmark_trace.get("endpoints") or []
    if benchmark_endpoints:
        for ep in benchmark_endpoints:
            bm_id = ep.get("endpoint_name") or ""
            if not bm_id:
                errors.append(
                    "G.5.6: benchmark_derivation_trace endpoint missing endpoint_name."
                )

    # G.5.7: BR/alignment refs resolve
    br_ledger = package.get("benefit_risk_ledger") or []
    alignment = package.get("alignment_matrix") or []
    if br_ledger and not isinstance(br_ledger, list):
        errors.append("G.5.7: benefit_risk_ledger is not a valid list.")
    if alignment and not isinstance(alignment, list):
        errors.append("G.5.7: alignment_matrix is not a valid list.")

    # G.5.8: Package schema version must be supported
    schema_ver = str(package.get("package_schema_version") or "")
    if not schema_ver:
        errors.append(
            "G.5.8: package_schema_version is missing. "
            f"Supported versions: {SUPPORTED_SCHEMA_VERSIONS}."
        )
    elif schema_ver not in SUPPORTED_SCHEMA_VERSIONS:
        errors.append(
            f"G.5.8: Unsupported package_schema_version '{schema_ver}'. "
            f"Supported versions: {SUPPORTED_SCHEMA_VERSIONS}."
        )

    # ── Additional semantic checks (BIGDP2026.6) ──
    reasoning_ledger = package.get("cer_reasoning_ledger") or {}
    if not reasoning_ledger.get("claims"):
        errors.append(
            "CER_REASONING_LEDGER is missing or has no claims. "
            "Writer cannot write without expert reasoning context."
        )

    ifu_evolution = package.get("ifu_claim_evolution_ledger") or {}
    if not ifu_evolution.get("claims"):
        errors.append(
            "IFU_CLAIM_EVOLUTION_LEDGER is missing or has no claims. "
            "Writer should verify IFU claims have been properly evolved."
        )

    return errors


def validate_package_or_exit(package: dict[str, Any], exit_on_error: bool = True) -> list[str]:
    """Validate and optionally exit with non-zero code on failure.

    This is the entry point for Claude Code writer skills. When exit_on_error=True,
    the process exits with code 2 if any validation errors are found.
    """
    errors = validate_package(package)
    if errors and exit_on_error:
        import sys
        print("=== CER_INPUT_PACKAGE VALIDATION FAILED ===", file=sys.stderr)
        for i, err in enumerate(errors, 1):
            print(f"  [{i}] {err}", file=sys.stderr)
        print(f"\n{len(errors)} validation error(s). Writer cannot proceed.", file=sys.stderr)
        sys.exit(2)
    return errors
