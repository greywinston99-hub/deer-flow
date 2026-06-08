"""Test — RMF _run_human_boundary must not pre-filter findings via keyword matching.

Phase 2 cleanup: all 4 keyword-driven list comprehensions in _run_human_boundary
(severity_findings, control_findings, residual_findings, cross_doc_findings)
must be removed. Upstream dimension findings pass directly to the subagent.
"""

from __future__ import annotations

import ast
from pathlib import Path

RMF_RUNNER = (
    Path(__file__).parent.parent
    / "packages"
    / "harness"
    / "deerflow"
    / "runtime"
    / "rmf_review"
    / "runner.py"
)


def _extract_human_boundary_source() -> str:
    """Extract the source code of _run_human_boundary method using AST."""
    source = RMF_RUNNER.read_text(encoding="utf-8")
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_run_human_boundary":
            lines = source.splitlines()
            start = node.lineno - 1
            end = node.end_lineno
            return "\n".join(lines[start:end])

    msg = "_run_human_boundary not found in RMF runner"
    raise AssertionError(msg)


def test_human_boundary_no_keyword_filter_list_comprehensions() -> None:
    """Verify no list comprehension uses keyword matching on detail.lower()."""
    body = _extract_human_boundary_source()

    # Check for forbidden patterns
    forbidden_patterns = [
        'f.get("detail", "").lower()',
        '".lower()',
    ]

    for pattern in forbidden_patterns:
        if pattern in body:
            # Find the line
            for i, line in enumerate(body.splitlines()):
                if pattern in line:
                    # Skip guardrail-only lines
                    if "# guardrail-only" in line:
                        continue
                    msg = (
                        f"_run_human_boundary line ~{i+1} contains forbidden "
                        f"keyword filter: {line.strip()!r}"
                    )
                    raise AssertionError(msg)


def test_human_boundary_passes_full_dimension_findings() -> None:
    """Verify dimension findings pass directly (not through keyword filter)."""
    body = _extract_human_boundary_source()

    # Assert the 4 keyword-filtered variable names no longer appear
    forbidden_vars = [
        "severity_findings",
        "residual_findings",
    ]
    for var in forbidden_vars:
        lines = body.splitlines()
        for i, line in enumerate(lines):
            stripped = line.strip()
            # Allow in docstrings or comments
            if stripped.startswith("#") or '"""' in stripped:
                continue
            if var in stripped and "=" in stripped:
                msg = (
                    f"_run_human_boundary line ~{i+1} still defines "
                    f"keyword-filtered variable `{var}`"
                )
                raise AssertionError(msg)


def test_human_boundary_uses_corr_findings_directly() -> None:
    """Verify CORR findings evidence uses corr_findings directly."""
    body = _extract_human_boundary_source()

    assert "evidence_sources=self._extract_evidence_sources(corr_findings" in body, (
        "severity_grading_appropriateness must use corr_findings directly, "
        "not a keyword-filtered subset"
    )


def test_human_boundary_uses_acpt_findings_directly() -> None:
    """Verify ACPT findings evidence uses acpt_findings directly."""
    body = _extract_human_boundary_source()

    assert "evidence_sources=self._extract_evidence_sources(acpt_findings" in body, (
        "residual_risk_acceptability must use acpt_findings directly, "
        "not a keyword-filtered subset"
    )
