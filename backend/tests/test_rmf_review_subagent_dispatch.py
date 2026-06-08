"""Verify each RMF stage handler dispatches review judgment to a SubagentExecutor.

Step 7 / TDD red — covers Step 14 outcome.

Static-analysis guardrail: every stage handler in the RMF runner must
delegate the review judgment to a real subagent (`self._run_subagent_step(...)`).
The pre-refactor implementation performed local keyword matching plus
`_collect_<dim>_findings` static helpers. Post-refactor, all 8 RMF stage
handlers MUST:

1. Invoke `self._run_subagent_step(...)` to dispatch to the appropriate agent.
2. Reference the correct `agent_name` (one of the 7 RMF review agents — note
   `rmf-precheck-reviewer` is shared between `_run_fmea_precheck` and
   `_run_rmf_precheck` via a `mode` parameter).
3. The runner module must import `SubagentExecutor`.
4. The runner must define the helpers `_run_subagent_step`,
   `_append_agent_invocation_trace`, `_extract_json_block`, `_write_event_log`,
   `_write_task_ledger`, `_write_resume_signal`.
5. The RMF dimension review must remain a SINGLE agent invocation that produces
   all 6 dimensions (COMP/CORR/ADEQ/TRAC/CONS/ACPT) — NOT 6 parallel calls.

Also enforces the deletion of `_collect_<dim>_findings` static helpers, which
were the home of keyword review judgments.
"""

from __future__ import annotations

import re
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

# Handler -> expected subagent name mapping (8 RMF stage handlers).
# Note the 2 precheck handlers share `rmf-precheck-reviewer` with a mode arg.
EXPECTED_HANDLER_TO_AGENT: dict[str, str] = {
    "_run_intake": "rmf-intake-reviewer",
    "_run_parse_normalize": "rmf-parse-normalize-reviewer",
    "_run_fmea_precheck": "rmf-precheck-reviewer",
    "_run_rmf_precheck": "rmf-precheck-reviewer",
    "_run_rmf_dimension_review": "rmf-dimension-reviewer",
    "_run_human_boundary": "rmf-human-boundary-reviewer",
    "_run_report": "rmf-report-reviewer",
    "_run_gate_closure": "rmf-gate-closure-reviewer",
}


def _extract_method_body(source: str, method_name: str) -> str:
    """Return the source lines belonging to the body of `def method_name(...):`."""
    pattern = re.compile(rf"^(?P<indent>\s+)def\s+{re.escape(method_name)}\b", re.MULTILINE)
    match = pattern.search(source)
    if not match:
        return ""

    base_indent = len(match.group("indent"))
    lines = source[match.end():].splitlines()
    body_lines: list[str] = []
    for line in lines:
        if line.strip() == "":
            body_lines.append(line)
            continue
        line_indent = len(line) - len(line.lstrip())
        if line_indent <= base_indent and line.strip().startswith(("def ", "class ", "@")):
            break
        body_lines.append(line)
    return "\n".join(body_lines)


def test_rmf_runner_imports_subagent_executor() -> None:
    """The runner module must import SubagentExecutor for dispatch to work."""
    assert RMF_RUNNER.exists(), f"RMF runner not found at {RMF_RUNNER}"
    text = RMF_RUNNER.read_text(encoding="utf-8")
    assert re.search(r"from\s+deerflow\.subagents(\.executor)?\s+import\s+[^\n]*SubagentExecutor", text), (
        "RMF runner must import SubagentExecutor from deerflow.subagents — "
        "the dispatch helper cannot work without it."
    )


def test_rmf_runner_defines_dispatch_helpers() -> None:
    """RMF runner must define all 4 dispatch / observability helpers."""
    text = RMF_RUNNER.read_text(encoding="utf-8")
    required_helpers = {
        "_run_subagent_step": "core dispatch helper",
        "_append_agent_invocation_trace": "trace observability writer",
        "_extract_json_block": "JSON payload extraction",
    }
    missing: list[str] = []
    for helper, purpose in required_helpers.items():
        if not re.search(rf"^\s+def\s+{re.escape(helper)}\b", text, re.MULTILINE):
            missing.append(f"{helper} ({purpose})")
    assert not missing, (
        f"RMF runner is missing required helpers: {missing}. These helpers are "
        "needed by every stage handler to dispatch through SubagentExecutor."
    )


def test_rmf_runner_defines_event_log_and_task_ledger_writers() -> None:
    """RMF runner must define event_log / task_ledger / resume_signal writers.

    Pre-refactor RMF runtime had no such observability writers — every artifact
    was just dropped by `_write_json` with no event lifecycle. Step 13 adds these.
    """
    text = RMF_RUNNER.read_text(encoding="utf-8")
    required_helpers = {
        "_write_event_log": "lifecycle event logger",
        "_write_task_ledger": "task status ledger writer",
        "_write_resume_signal": "resume coordination writer",
    }
    missing: list[str] = []
    for helper, purpose in required_helpers.items():
        if not re.search(rf"^\s+def\s+{re.escape(helper)}\b", text, re.MULTILINE):
            missing.append(f"{helper} ({purpose})")
    assert not missing, (
        f"RMF runner is missing observability helpers: {missing}. CER runner "
        "already has these; RMF must reach parity in Step 13."
    )


def test_each_rmf_handler_dispatches_to_subagent_step() -> None:
    """Every RMF stage handler MUST call `self._run_subagent_step(...)`."""
    text = RMF_RUNNER.read_text(encoding="utf-8")
    missing: list[str] = []
    for handler in EXPECTED_HANDLER_TO_AGENT:
        body = _extract_method_body(text, handler)
        assert body, f"could not locate body of `{handler}` in RMF runner"
        if "_run_subagent_step(" not in body:
            missing.append(handler)
    assert not missing, (
        f"The following RMF stage handlers do not dispatch to SubagentExecutor: "
        f"{missing}. Each handler must call `self._run_subagent_step(...)` "
        "instead of using `_collect_*_findings` keyword helpers."
    )


def test_each_rmf_handler_references_its_expected_agent_name() -> None:
    """Each handler must mention the agent name it is expected to dispatch to."""
    text = RMF_RUNNER.read_text(encoding="utf-8")
    mismatches: list[str] = []
    for handler, agent_name in EXPECTED_HANDLER_TO_AGENT.items():
        body = _extract_method_body(text, handler)
        if agent_name not in body:
            mismatches.append(f"{handler} -> {agent_name}")
    assert not mismatches, (
        f"The following RMF handlers do not reference their expected subagent name: "
        f"{mismatches}. Each handler must dispatch to the agent named in its prompt contract."
    )


def test_rmf_dimension_review_is_a_single_call_not_six() -> None:
    """RMF dimension review must dispatch ONCE and produce 6 dimensions in the same payload.

    Per the locked-in design in the plan: the dimension reviewer agent is a single
    LLM call that emits a JSON object with 6 dimension keys (COMP/CORR/ADEQ/TRAC/CONS/ACPT).
    Calling SubagentExecutor 6 times (one per dimension) is FORBIDDEN — it explodes
    LLM cost, breaks evidence cross-reference, and wastes the prompt-contract design.
    """
    text = RMF_RUNNER.read_text(encoding="utf-8")
    body = _extract_method_body(text, "_run_rmf_dimension_review")
    assert body, "could not locate `_run_rmf_dimension_review` in RMF runner"

    # Count occurrences of `_run_subagent_step(` inside the dimension review body.
    dispatch_calls = len(re.findall(r"_run_subagent_step\s*\(", body))
    assert dispatch_calls == 1, (
        f"_run_rmf_dimension_review must invoke `_run_subagent_step` EXACTLY ONCE "
        f"(producing all 6 dimensions in a single agent call); found {dispatch_calls} "
        "invocations. Multi-call dispatch breaks the locked-in single-pass design."
    )


def test_rmf_runner_no_collect_dimension_findings_helpers() -> None:
    """`_collect_<dimension>_findings` helpers were the home of keyword review.

    Pre-refactor pattern — explicit names per dimension:
      _collect_completeness_findings, _collect_correctness_findings,
      _collect_adequacy_findings, _collect_traceability_findings,
      _collect_consistency_findings, _collect_acceptability_findings.

    All six must be deleted in Step 14; the dimension reviewer agent produces
    findings now.
    """
    text = RMF_RUNNER.read_text(encoding="utf-8")
    forbidden_helpers = (
        "_collect_completeness_findings",
        "_collect_correctness_findings",
        "_collect_adequacy_findings",
        "_collect_traceability_findings",
        "_collect_consistency_findings",
        "_collect_acceptability_findings",
    )
    surviving = [
        helper
        for helper in forbidden_helpers
        if re.search(rf"^\s+def\s+{re.escape(helper)}\b", text, re.MULTILINE)
    ]
    assert not surviving, (
        f"RMF runner still defines dimension-finding helpers: {surviving}. "
        "These were keyword-review judgment helpers and must be removed in Step 14 "
        "now that the dimension reviewer agent owns this logic."
    )


def test_rmf_no_simulated_reviewer_fabrication_in_source() -> None:
    """The literal string `smoke-run-simulated-reviewer` must not appear in the source.

    This is a static guard against the self-fabrication bug at runner.py:1686-1695
    where the runner auto-wrote a fake human gate decision when the file was missing.
    """
    text = RMF_RUNNER.read_text(encoding="utf-8")
    assert "smoke-run-simulated-reviewer" not in text, (
        "RMF runner still contains the literal string 'smoke-run-simulated-reviewer'. "
        "Step 15 must delete the auto-fabrication path at lines 1686-1695."
    )
    # Also forbid the simulated-true literal pattern — there is no legitimate
    # case for the runner to write `\"simulated\": true` itself.
    simulated_true_pattern = re.compile(r'"simulated"\s*:\s*True\b')
    matches = simulated_true_pattern.findall(text)
    assert not matches, (
        f"RMF runner still writes `\"simulated\": True` ({len(matches)} occurrences). "
        "The runner must not fabricate simulated reviewer state; that flag should "
        "only be set by genuine smoke-test fixtures, never by the production runner."
    )
