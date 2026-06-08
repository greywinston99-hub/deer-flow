"""Test — RMF _build_term_consistency must not generate keyword-based findings.

Phase 2 cleanup: weak_terminology_alignment finding generation must be removed
and handled by rmf-precheck-reviewer subagent instead.
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


def _extract_term_consistency_source() -> str:
    """Extract the source code of _build_term_consistency method using AST."""
    source = RMF_RUNNER.read_text(encoding="utf-8")
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_build_term_consistency":
            lines = source.splitlines()
            start = node.lineno - 1
            end = node.end_lineno
            return "\n".join(lines[start:end])

    msg = "_build_term_consistency not found in RMF runner"
    raise AssertionError(msg)


def test_term_consistency_no_weak_terminology_alignment() -> None:
    """Verify _build_term_consistency no longer generates keyword-based finding."""
    body = _extract_term_consistency_source()

    assert "weak_terminology_alignment" not in body, (
        "_build_term_consistency still generates weak_terminology_alignment finding. "
        "This must be removed — term consistency is now handled by rmf-precheck-reviewer subagent."
    )


def test_term_consistency_returns_none_finding() -> None:
    """Verify the finding field in the return dict is always None."""
    body = _extract_term_consistency_source()

    assert '"finding": None' in body or "'finding': None" in body, (
        "_build_term_consistency return dict must have finding=None, "
        "since term consistency judgment is delegated to the subagent."
    )


def test_term_consistency_no_canonical_term_lower_in_all_text() -> None:
    """Verify no canonical_terms.lower() in all_text keyword check produces a finding."""
    body = _extract_term_consistency_source()

    # The forbidden pattern: canonical_terms keyword check producing a finding
    forbidden_phrases = [
        "if not any(term.lower() in all_text for term in canonical_terms)",
        "finding_type"
    ]

    for phrase in forbidden_phrases:
        if phrase in body:
            msg = f"_build_term_consistency still contains {phrase!r} which drives keyword-based finding generation"
            raise AssertionError(msg)
