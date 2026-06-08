"""Test — CER D1 handlers must not generate keyword-based findings.

Phase 2 cleanup: keyword-based R2_M-002 compliance findings and 3D checklist
findings in _run_d1_cep_methodology and _run_d1_clinical_evidence_panel must
be removed. Review findings are produced by the respective subagents.
"""

from __future__ import annotations

import ast
from pathlib import Path

CER_RUNNER = (
    Path(__file__).parent.parent
    / "packages"
    / "harness"
    / "deerflow"
    / "runtime"
    / "cer_review"
    / "runner.py"
)


TARGET_HANDLERS = [
    "_run_d1_cep_methodology",
    "_run_d1_clinical_evidence_panel",
]

# These keyword-based pattern strings are forbidden in D1 handlers
# (not counting guardrail-only structural metadata lines).
FORBIDDEN_PATTERNS = [
    # R2_M-002 compliance finding generation
    "R2_M-002 Stage 1 Gap",
    "R2_M-002 Stage 2 Gap",
    "R2_M-002 Stage 3 Gap",
    # 3D Checklist finding generation
    "3D Checklist: Technical Equivalence",
    "3D Checklist: Biological Equivalence",
    "3D Checklist: Clinical Equivalence",
    # Predicate device identification finding
    "Predicate Device Identification",
    # Data access contract finding (Class III)
    "Data Access Contract",
]


def _handler_sources() -> dict[str, str]:
    """Extract source code of each target handler."""
    source = CER_RUNNER.read_text(encoding="utf-8")
    tree = ast.parse(source)

    results: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in TARGET_HANDLERS:
            lines = source.splitlines()
            start = node.lineno - 1
            end = node.end_lineno
            results[node.name] = "\n".join(lines[start:end])

    missing = [h for h in TARGET_HANDLERS if h not in results]
    if missing:
        msg = f"D1 handlers not found in CER runner: {missing}"
        raise AssertionError(msg)
    return results


def test_cep_methodology_no_r2_m002_findings() -> None:
    """Verify _run_d1_cep_methodology no longer generates R2_M-002 findings."""
    sources = _handler_sources()
    body = sources["_run_d1_cep_methodology"]

    for pattern in FORBIDDEN_PATTERNS:
        lines = body.splitlines()
        for i, line in enumerate(lines):
            if pattern in line:
                # Allow guardrail-only comments
                if "# guardrail-only" in line:
                    continue
                msg = (
                    f"_run_d1_cep_methodology line ~{i+1} contains "
                    f"forbidden pattern {pattern!r}. "
                    "R2_M-002 compliance findings must be produced by subagent."
                )
                raise AssertionError(msg)


def test_clinical_evidence_panel_no_3d_checklist_findings() -> None:
    """Verify _run_d1_clinical_evidence_panel no longer generates 3D checklist findings."""
    sources = _handler_sources()
    body = sources["_run_d1_clinical_evidence_panel"]

    for pattern in FORBIDDEN_PATTERNS:
        lines = body.splitlines()
        for i, line in enumerate(lines):
            if pattern in line:
                if "# guardrail-only" in line:
                    continue
                msg = (
                    f"_run_d1_clinical_evidence_panel line ~{i+1} contains "
                    f"forbidden pattern {pattern!r}. "
                    "3D checklist findings must be produced by subagent."
                )
                raise AssertionError(msg)


def test_clinical_evidence_panel_no_keyword_biology_findings() -> None:
    """Verify no keyword-based bio/clin/tech finding appends remain."""
    sources = _handler_sources()
    body = sources["_run_d1_clinical_evidence_panel"]

    # The equivalence section should not have keyword-driven finding appends
    # Allow the structural score variables and metadata
    forbidden_equivalence_patterns = [
        "bio_checks",
        "clin_checks",
        "tech_checks",
    ]
    for pattern in forbidden_equivalence_patterns:
        lines = body.splitlines()
        for i, line in enumerate(lines):
            stripped = line.strip()
            if pattern in stripped and "=" in stripped and "findings.append" in body.splitlines()[i + 1:i + 5]:
                msg = (
                    f"_run_d1_clinical_evidence_panel line ~{i+1} has keyword check "
                    f"`{stripped}` followed by findings.append. "
                    "These findings must be removed."
                )
                raise AssertionError(msg)
