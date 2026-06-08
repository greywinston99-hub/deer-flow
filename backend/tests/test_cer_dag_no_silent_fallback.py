"""Verify CER runner does not silently fall back to sequential when LangGraph DAG fails.

Step 7 / TDD red — covers Step 11 outcome (remove silent fallback at runner.py:5811-5816).
The current implementation catches DAG exceptions and silently runs `_run_d1_workflow_sequential`
which masks production DAG failures. The refactored runner must:

1. Raise CERWorkflowExecutionError on DAG failure (not silently fall back).
2. Sequential execution is permitted only when explicitly resuming via --resume-from-node.
3. Failure is logged to event_log.json with event_type=DAG_EXECUTION_FAILED.
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


def test_cer_runner_defines_cer_workflow_execution_error() -> None:
    """CERWorkflowExecutionError must exist for hard-failure on DAG breakage."""
    assert CER_RUNNER.exists(), f"CER runner not found at {CER_RUNNER}"
    text = CER_RUNNER.read_text(encoding="utf-8")
    pattern = re.compile(r"class\s+CERWorkflowExecutionError\s*\(")
    assert pattern.search(text), (
        "CER runner must define `class CERWorkflowExecutionError` so DAG failures "
        "raise rather than silently fall back to sequential."
    )


def test_cer_runner_dag_failure_does_not_silently_fall_back() -> None:
    """Forbid the `try DAG / except: fall back to sequential` pattern."""
    assert CER_RUNNER.exists()
    text = CER_RUNNER.read_text(encoding="utf-8")

    pattern = re.compile(
        r"falling\s+back\s+to\s+sequential",
        re.IGNORECASE,
    )
    matches = pattern.findall(text)
    assert not matches, (
        "CER runner must not log 'falling back to sequential' on DAG exception. "
        "DAG failures must raise CERWorkflowExecutionError; sequential is allowed only "
        "when --resume-from-node is explicitly set."
    )


def test_cer_runner_event_log_records_dag_failure() -> None:
    """The runner must emit a DAG_EXECUTION_FAILED event when DAG breaks."""
    assert CER_RUNNER.exists()
    text = CER_RUNNER.read_text(encoding="utf-8")
    assert "DAG_EXECUTION_FAILED" in text, (
        "CER runner must record DAG_EXECUTION_FAILED event so the failure is observable."
    )
