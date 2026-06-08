"""Verify each CER D1 step handler dispatches review judgment to a SubagentExecutor.

Step 7 / TDD red — covers Step 9 outcome.

Static-analysis guardrail: every handler in the CER D1 ordered_steps map must
delegate the review judgment to a real subagent (`self._run_subagent_step(...)`).
The pre-refactor implementation performed local keyword matching and hard-coded
findings.append(...) blocks. Post-refactor, all 10 D1 step handlers MUST:

1. Invoke `self._run_subagent_step(...)` to dispatch to the appropriate agent.
2. Reference the correct `agent_name` (one of the 10 review agents).
3. The runner module must import `SubagentExecutor` (so the dispatch path exists).
4. The runner must define `_run_subagent_step` and `_append_agent_invocation_trace` helpers.

Static guards run < 1 second and avoid the brittleness of full-stack smoke
fixtures. Integration coverage for the dispatch path is provided separately
during Step 17 (real smoke run).
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

# Handler -> expected subagent name mapping (10 D1 step handlers).
EXPECTED_HANDLER_TO_AGENT: dict[str, str] = {
    "_run_d1_intake": "cer-intake-reviewer",
    "_run_d1_structure_compliance": "cer-structure-compliance-reviewer",
    "_run_d1_intended_purpose": "cer-intended-purpose-reviewer",
    "_run_d1_cep_methodology": "cer-cep-methodology-reviewer",
    "_run_d1_clinical_evidence_panel": "cer-clinical-evidence-panel-reviewer",
    "_run_d1_ifu_sscp_label": "cer-ifu-sscp-label-reviewer",
    "_run_d1_qa_gate": "cer-qa-gate-reviewer",
    "_run_d1_cear_formatter": "cer-cear-formatter-reviewer",
    "_run_d1_human_boundary": "cer-human-boundary-reviewer",
    "_run_d1_gate_closure": "cer-gate-closure-reviewer",
}


def _extract_method_body(source: str, method_name: str) -> str:
    """Return the source lines belonging to the body of `def method_name(...):`.

    Uses indentation tracking — collects every line whose indent is greater
    than the `def` line until a sibling top-level construct appears.
    """
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


def test_cer_runner_imports_subagent_executor() -> None:
    """The runner module must import SubagentExecutor for dispatch to work."""
    assert CER_RUNNER.exists(), f"CER runner not found at {CER_RUNNER}"
    text = CER_RUNNER.read_text(encoding="utf-8")
    assert re.search(r"from\s+deerflow\.subagents(\.executor)?\s+import\s+[^\n]*SubagentExecutor", text), (
        "CER runner must import SubagentExecutor from deerflow.subagents — "
        "the dispatch helper cannot work without it."
    )


def test_cer_runner_defines_run_subagent_step_helper() -> None:
    """The runner must define a `_run_subagent_step` helper used by all D1 handlers."""
    text = CER_RUNNER.read_text(encoding="utf-8")
    assert re.search(r"^\s+def\s+_run_subagent_step\b", text, re.MULTILINE), (
        "CER runner must define `_run_subagent_step(...)` helper — every D1 step "
        "handler should dispatch through this single entry point."
    )


def test_cer_runner_defines_agent_invocation_trace_writer() -> None:
    """The runner must define `_append_agent_invocation_trace` for trace observability."""
    text = CER_RUNNER.read_text(encoding="utf-8")
    assert re.search(r"^\s+def\s+_append_agent_invocation_trace\b", text, re.MULTILINE), (
        "CER runner must define `_append_agent_invocation_trace(...)` — each subagent "
        "invocation should append one JSON line to 00_manifest/agent_invocation_trace.jsonl."
    )


def test_cer_runner_defines_extract_json_block_helper() -> None:
    """The runner must define `_extract_json_block` to parse SubagentResult content."""
    text = CER_RUNNER.read_text(encoding="utf-8")
    assert re.search(r"^\s+def\s+_extract_json_block\b", text, re.MULTILINE), (
        "CER runner must define `_extract_json_block(...)` — used to extract the JSON "
        "payload from subagent responses (handles ```json fenced blocks)."
    )


def test_confirmed_looping_reviewers_run_json_only() -> None:
    """Confirmed D1 recursion-loop reviewers must not run as tool agents."""
    text = CER_RUNNER.read_text(encoding="utf-8")
    assert "_CER_REVIEW_JSON_ONLY_AGENTS" in text
    assert '"cer-structure-compliance-reviewer"' in text
    assert '"cer-intended-purpose-reviewer"' in text
    assert '"cer-clinical-evidence-panel-reviewer"' in text
    assert re.search(r"replace\(\s*config,\s*tools=\[\]\s*\)", text), (
        "Confirmed recursion-loop reviewers should be cloned with tools=[] so "
        "they emit bounded JSON instead of entering a LangGraph tool loop."
    )


def test_review_task_prompt_embeds_upstream_artifacts() -> None:
    """D1 review prompts should include upstream artifact content directly."""
    text = CER_RUNNER.read_text(encoding="utf-8")
    body = _extract_method_body(text, "_build_review_task_prompt")
    assert "The artifact contents are embedded below." in body
    assert "read these via the read_file tool" not in body


def test_clinical_panel_reviewer_findings_feed_panel_summary() -> None:
    """Clinical panel reviewer findings should drive D1 panel counts."""
    text = CER_RUNNER.read_text(encoding="utf-8")
    body = _extract_method_body(text, "_run_d1_clinical_evidence_panel")
    assert 'output_artifact=step_dir / "clinical_evidence_panel_review.json"' in body
    assert 'report["findings"] = agent_findings' in body
    assert 'report["findings_count"] = len(agent_findings)' in body
    assert 'report["llm_review_agent"] = "cer-clinical-evidence-panel-reviewer"' in body
    assert 'lane_artifact["findings"] = lane_findings' in body


def test_clinical_panel_collects_sub_assessment_findings() -> None:
    """Clinical panel payloads may nest findings under sub_assessments."""
    text = CER_RUNNER.read_text(encoding="utf-8")
    collect_body = _extract_method_body(text, "_collect_findings_from_payload")
    panel_body = _extract_method_body(text, "_run_d1_clinical_evidence_panel")
    assert 'payload.get("sub_assessments", {})' in collect_body
    assert 'agent_payload.get("sub_assessments", {})' in panel_body


def test_clinical_panel_uses_keyword_windowed_cer_context() -> None:
    """Clinical panel should not send only the first 8000 characters of CER text."""
    text = CER_RUNNER.read_text(encoding="utf-8")
    panel_body = _extract_method_body(text, "_run_d1_clinical_evidence_panel")
    context_body = _extract_method_body(text, "_build_cer_panel_text_context")
    assert "cer_text[:8000]" not in panel_body
    assert "state of the art" in context_body
    assert "benefit-risk" in context_body
    assert "_CER_PANEL_TEXT_CONTEXT_MAX_CHARS" in context_body


def test_each_d1_handler_dispatches_to_subagent_step() -> None:
    """Every D1 step handler MUST call `self._run_subagent_step(...)`."""
    text = CER_RUNNER.read_text(encoding="utf-8")
    missing: list[str] = []
    for handler in EXPECTED_HANDLER_TO_AGENT:
        body = _extract_method_body(text, handler)
        assert body, f"could not locate body of `{handler}` in CER runner"
        if "_run_subagent_step(" not in body:
            missing.append(handler)
    assert not missing, (
        f"The following D1 step handlers do not dispatch to SubagentExecutor: "
        f"{missing}. Each handler must call `self._run_subagent_step(...)` "
        "instead of doing local keyword/regex review judgments."
    )


def test_each_d1_handler_references_its_expected_agent_name() -> None:
    """Each handler must mention the agent name it is expected to dispatch to."""
    text = CER_RUNNER.read_text(encoding="utf-8")
    mismatches: list[str] = []
    for handler, agent_name in EXPECTED_HANDLER_TO_AGENT.items():
        body = _extract_method_body(text, handler)
        if agent_name not in body:
            mismatches.append(f"{handler} -> {agent_name}")
    assert not mismatches, (
        f"The following handlers do not reference their expected subagent name: "
        f"{mismatches}. Each handler must dispatch to the agent named in its prompt contract."
    )


def test_agent_usage_ledger_is_not_scaffold_stub() -> None:
    """`_write_agent_usage_ledger` must produce status=live, not scaffold_stub."""
    text = CER_RUNNER.read_text(encoding="utf-8")
    pattern = re.compile(r'"status"\s*:\s*"scaffold_stub"')
    matches = pattern.findall(text)
    assert not matches, (
        f"CER runner still writes hardcoded `\"status\": \"scaffold_stub\"` "
        f"({len(matches)} occurrences). After Step 10, the agent usage ledger "
        "must be rebuilt from agent_invocation_trace.jsonl with status=\"live\"."
    )


def test_apply_prompt_contract_stores_agent_name_not_just_bool() -> None:
    """`_apply_prompt_contract` must populate richer state than just `loaded: True`.

    Pre-refactor stored only `prompt_contract_loaded: True`. Post-refactor must
    record the agent_name and schema_ref so `_run_subagent_step` can consume them.
    """
    text = CER_RUNNER.read_text(encoding="utf-8")
    body = _extract_method_body(text, "_apply_prompt_contract")
    assert body, "could not locate `_apply_prompt_contract` in CER runner"
    # The post-refactor state record must reference at least agent_name or schema_ref;
    # a literal `prompt_contract_loaded: True` alone (without other context) is insufficient.
    assert "agent_name" in body or "schema_ref" in body, (
        "`_apply_prompt_contract` must record agent_name (and ideally schema_ref) "
        "so `_run_subagent_step` can use this metadata. Storing only "
        "`prompt_contract_loaded: True` is insufficient."
    )
