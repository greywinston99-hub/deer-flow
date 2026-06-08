#!/usr/bin/env python3
"""BIGDP2026.6 R2: Standalone Claude Code Writer Package Validator.

Usage (from Claude Code skill or CLI):
    python writer_package_validator.py <path_to_CER_INPUT_PACKAGE.json>

Exits 0 if package is valid for writing. Exits 2 if any check fails.
"""
import json
import sys
from pathlib import Path

SUPPORTED_VERSIONS = {"1.0.0"}


def validate_package_file(package_path: str) -> list[str]:
    """Validate a CER_INPUT_PACKAGE.json file. Returns list of errors."""
    errors = []

    # Check file exists
    pkg_file = Path(package_path)
    if not pkg_file.exists():
        return [f"CER_INPUT_PACKAGE.json not found at {package_path}"]

    # Parse JSON
    try:
        package = json.loads(pkg_file.read_text())
    except json.JSONDecodeError as e:
        return [f"CER_INPUT_PACKAGE.json is not valid JSON: {e}"]

    if not isinstance(package, dict):
        return ["CER_INPUT_PACKAGE.json is not a JSON object"]

    # G.5.2: G46 PASS
    g46 = package.get("pre_writer_readiness_gate_report") or {}
    if g46.get("status") != "PASS":
        errors.append(f"G46 status is '{g46.get('status')}', expected 'PASS'")

    # G.5.3: exported
    if not package.get("cer_input_package_exported"):
        errors.append("cer_input_package_exported is not true")

    # G.5.4: claim_ids resolve
    claim_ids = {str(c.get("claim_id") or "") for c in (package.get("claim_ledger") or [])}
    claim_ids.discard("")
    for row in (package.get("claim_evidence_matrix") or []):
        cid = str(row.get("claim_id") or "")
        if cid and cid not in claim_ids:
            errors.append(f"Orphan claim_id '{cid}' in claim_evidence_matrix")

    # G.5.5: evidence_ids resolve
    known_eids = {str(e.get("evidence_id") or e.get("id") or e.get("pmid") or "")
                  for e in (package.get("evidence_registry") or [])}
    known_eids.discard("")
    for row in (package.get("claim_evidence_matrix") or []):
        for eid in (row.get("evidence_ids") or []):
            if str(eid) and str(eid) not in known_eids:
                errors.append(f"Orphan evidence_id '{eid}' in claim '{row.get('claim_id', '?')}'")

    # G.5.6: benchmark endpoints
    bm_trace = package.get("benchmark_derivation_trace") or {}
    for ep in (bm_trace.get("endpoints") or []):
        if not ep.get("endpoint_name"):
            errors.append("benchmark_derivation_trace endpoint missing endpoint_name")

    # G.5.7: BR/alignment valid
    br = package.get("benefit_risk_ledger")
    if br is not None and not isinstance(br, list):
        errors.append("benefit_risk_ledger is not a valid list")
    al = package.get("alignment_matrix")
    if al is not None and not isinstance(al, list):
        errors.append("alignment_matrix is not a valid list")

    # G.5.8: schema version
    sv = str(package.get("package_schema_version") or "")
    if not sv:
        errors.append("package_schema_version is missing")
    elif sv not in SUPPORTED_VERSIONS:
        errors.append(f"Unsupported package_schema_version '{sv}'")

    # Expert ledger checks
    rl = package.get("cer_reasoning_ledger") or {}
    if not rl.get("claims"):
        errors.append("CER_REASONING_LEDGER missing or empty")

    return errors


def main():
    if len(sys.argv) < 2:
        print("Usage: python writer_package_validator.py <path_to_CER_INPUT_PACKAGE.json>", file=sys.stderr)
        sys.exit(2)

    errors = validate_package_file(sys.argv[1])
    if errors:
        print(f"=== CER_INPUT_PACKAGE VALIDATION FAILED ({len(errors)} errors) ===", file=sys.stderr)
        for i, err in enumerate(errors, 1):
            print(f"  [{i}] {err}", file=sys.stderr)
        sys.exit(2)

    print("CER_INPUT_PACKAGE validation PASSED — Writer may proceed.")
    sys.exit(0)


if __name__ == "__main__":
    main()
