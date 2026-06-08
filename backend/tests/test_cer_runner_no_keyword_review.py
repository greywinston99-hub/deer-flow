"""Guardrail test — CER runner must not perform review judgment via keyword matching.

The CER review pipeline is being refactored from local keyword-based heuristics
(e.g. ``if "<keyword>" in text.lower(): findings.append(...)``) to real
SubagentExecutor dispatch. This test forbids the keyword-review pattern from
returning to the runner. Step 7 — TDD red.

Allowed exceptions are tagged with ``# guardrail-only`` on the same line, which
identifies a residual schema-completeness or source-binding check that is not
performing review judgment. The whitelist budget is bounded.
"""

from __future__ import annotations

import re
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

RMF_RUNNER = (
    Path(__file__).parent.parent
    / "packages"
    / "harness"
    / "deerflow"
    / "runtime"
    / "rmf_review"
    / "runner.py"
)


# Pattern: `if "..." in <var>:` followed within 3 lines by `findings.append(`
KEYWORD_REVIEW_PATTERN = re.compile(
    r"""
    if\s+
    ['"][^'"]+['"]    # quoted keyword
    \s+in\s+
    \w+               # variable
    [^\n]*:\s*\n
    (?:[^\n]*\n){0,3}     # within 3 lines
    [^\n]*findings\.append
    """,
    re.VERBOSE,
)

# Pattern: `\.lower\(\)` used as gateway to keyword check (a strong code-smell
# of a keyword-matching review path).
LOWER_KEYWORD_PATTERN = re.compile(
    r"\.lower\(\)\s*\n?\s*[^\n]*\n[^\n]*findings\.append",
    re.MULTILINE,
)

# Pattern: `"keyword" in f.get("detail", "").lower()` list comprehension filter
# (keyword review disguised as structural filtering).
LOWER_COMPREHENSION_PATTERN = re.compile(
    r"""['"][^'"]+['"]\s+in\s+[a-zA-Z_][a-zA-Z0-9_]*\s*
    \.get\([^)]*\)\s*\.lower\(\)""",
    re.VERBOSE,
)

# Pattern: `\.lower\(\)` followed within 5 lines by `finding = {` or `findings = [`
# catching keyword-based finding dict/list construction.
LOWER_FINDING_DICT_PATTERN = re.compile(
    r"""\.lower\(\)[^\n]*\n
    (?:[^\n]*\n){0,5}
    [^\n]*(?:finding\s*=\s*\{|findings\s*=\s*\[|findings\.append\s*\()""",
    re.VERBOSE,
)


# Keyword-review remnants are allowed only when annotated with this marker
GUARDRAIL_TAG = "# guardrail-only"

# Maximum tolerated keyword remnants per runner (zero-tolerance grows over time).
MAX_KEYWORD_REVIEW_REMNANTS_CER = 0
MAX_KEYWORD_REVIEW_REMNANTS_RMF = 0


DEPRECATED_TAG = "# @deprecated"


def _find_active_code_start(text: str) -> int:
    """Find 0-indexed line number where active code starts after all @deprecated sections.

    Scans for the last ``# @deprecated`` tag, then the next ``def `` after it.
    That function definition (at class-member indent) is the boundary:
    everything before it is deprecated, everything from it onward is active
    review code. Returns ``0`` when no deprecated section is detected.
    """
    lines = text.splitlines()
    last_dep_line = -1
    for i, line in enumerate(lines):
        if DEPRECATED_TAG in line:
            last_dep_line = i

    if last_dep_line == -1:
        return 0

    for i in range(last_dep_line + 1, len(lines)):
        stripped = lines[i].strip()
        if stripped.startswith("def "):
            return i

    return len(lines)


def _count_violations(text: str, pattern: re.Pattern[str]) -> int:
    """Count violations of `pattern` excluding lines tagged guardrail-only or @deprecated."""
    active_start = _find_active_code_start(text)
    violations = 0
    for match in pattern.finditer(text):
        block = match.group(0)
        # Guardrail-only and @deprecated tags are line-scoped
        if GUARDRAIL_TAG in block or DEPRECATED_TAG in block:
            continue
        # The match may end before a trailing comment on the same line
        # (e.g. ``findings.append({`` matched without ``  # guardrail-only``).
        # Check the remainder of the line for a guardrail tag.
        match_end = match.end()
        line_end = text.find("\n", match_end)
        if line_end == -1:
            line_end = len(text)
        rest_of_line = text[match_end:line_end]
        if GUARDRAIL_TAG in rest_of_line or DEPRECATED_TAG in rest_of_line:
            continue
        # Exclude matches that fall within the @deprecated section and have
        # a @deprecated tag somewhere before them in the file
        match_line = text[: match.start()].count("\n")
        if match_line < active_start:
            if text.find(DEPRECATED_TAG, 0, match.start()) != -1:
                continue
        violations += 1
    return violations


def test_cer_runner_no_keyword_review() -> None:
    assert CER_RUNNER.exists(), f"CER runner not found at {CER_RUNNER}"
    text = CER_RUNNER.read_text(encoding="utf-8")

    keyword_in_then_append = _count_violations(text, KEYWORD_REVIEW_PATTERN)
    lower_then_append = _count_violations(text, LOWER_KEYWORD_PATTERN)
    lower_comprehension = _count_violations(text, LOWER_COMPREHENSION_PATTERN)
    lower_then_finding_dict = _count_violations(text, LOWER_FINDING_DICT_PATTERN)

    total = keyword_in_then_append + lower_then_append + lower_comprehension + lower_then_finding_dict
    assert total <= MAX_KEYWORD_REVIEW_REMNANTS_CER, (
        f"CER runner contains {total} keyword-review-driven findings.append "
        f"({keyword_in_then_append} from `if 'X' in var:`, "
        f"{lower_then_append} from `.lower()` chain, "
        f"{lower_comprehension} from `.lower()` in comprehension, "
        f"{lower_then_finding_dict} from `.lower()` to finding dict). "
        f"Mark each surviving block with `{GUARDRAIL_TAG}` only when it is a schema-completeness "
        "or source-binding guardrail (not a review judgment)."
    )


def test_rmf_runner_no_keyword_review() -> None:
    assert RMF_RUNNER.exists(), f"RMF runner not found at {RMF_RUNNER}"
    text = RMF_RUNNER.read_text(encoding="utf-8")

    keyword_in_then_append = _count_violations(text, KEYWORD_REVIEW_PATTERN)
    lower_then_append = _count_violations(text, LOWER_KEYWORD_PATTERN)
    lower_comprehension = _count_violations(text, LOWER_COMPREHENSION_PATTERN)
    lower_then_finding_dict = _count_violations(text, LOWER_FINDING_DICT_PATTERN)

    total = keyword_in_then_append + lower_then_append + lower_comprehension + lower_then_finding_dict
    assert total <= MAX_KEYWORD_REVIEW_REMNANTS_RMF, (
        f"RMF runner contains {total} keyword-review-driven findings.append "
        f"({keyword_in_then_append} from `if 'X' in var:`, "
        f"{lower_then_append} from `.lower()` chain, "
        f"{lower_comprehension} from `.lower()` in comprehension, "
        f"{lower_then_finding_dict} from `.lower()` to finding dict). "
        f"Mark each surviving block with `{GUARDRAIL_TAG}` only when it is a schema-completeness "
        "or source-binding guardrail (not a review judgment)."
    )


def test_cer_runner_no_collect_findings_static_helpers() -> None:
    """Forbid `_collect_<dim>_findings` style static helpers — these were the home of keyword review."""
    assert CER_RUNNER.exists()
    text = CER_RUNNER.read_text(encoding="utf-8")
    pattern = re.compile(r"^\s*def\s+_collect_\w+_findings\b", re.MULTILINE)
    matches = pattern.findall(text)
    assert not matches, f"CER runner still defines _collect_*_findings helpers: {matches}"


def test_rmf_runner_no_collect_findings_static_helpers() -> None:
    assert RMF_RUNNER.exists()
    text = RMF_RUNNER.read_text(encoding="utf-8")
    pattern = re.compile(r"^\s*def\s+_collect_\w+_findings\b", re.MULTILINE)
    matches = pattern.findall(text)
    assert not matches, f"RMF runner still defines _collect_*_findings helpers: {matches}"
