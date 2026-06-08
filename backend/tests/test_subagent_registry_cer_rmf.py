"""Verify CER + RMF subagent registry contains all 22 agents with correct config shape.

Step 7 / TDD red — covers Step 4 outcome (builtins/__init__.py registration).
"""

from __future__ import annotations


EXPECTED_AGENT_NAMES = {
    "general-purpose",
    "bash",
    "cer-intake-document-analyst",
    "cer-intake-compliance-reviewer",
    "cer-intake-reviewer",
    "cer-structure-compliance-reviewer",
    "cer-intended-purpose-reviewer",
    "cer-cep-methodology-reviewer",
    "cer-clinical-evidence-panel-reviewer",
    "cer-ifu-sscp-label-reviewer",
    "cer-qa-gate-reviewer",
    "cer-cear-formatter-reviewer",
    "cer-human-boundary-reviewer",
    "cer-gate-closure-reviewer",
    "rmf-intake-reviewer",
    "rmf-parse-normalize-reviewer",
    "rmf-precheck-reviewer",
    "rmf-dimension-reviewer",
    "rmf-human-boundary-reviewer",
    "rmf-report-reviewer",
    "rmf-gate-closure-reviewer",
    "rmf-cer-linkage-reviewer",
}


CER_NEW_REVIEW_AGENTS = {
    "cer-intake-reviewer",
    "cer-structure-compliance-reviewer",
    "cer-intended-purpose-reviewer",
    "cer-cep-methodology-reviewer",
    "cer-clinical-evidence-panel-reviewer",
    "cer-ifu-sscp-label-reviewer",
    "cer-qa-gate-reviewer",
    "cer-cear-formatter-reviewer",
    "cer-human-boundary-reviewer",
    "cer-gate-closure-reviewer",
}


RMF_REVIEW_AGENTS = {
    "rmf-intake-reviewer",
    "rmf-parse-normalize-reviewer",
    "rmf-precheck-reviewer",
    "rmf-dimension-reviewer",
    "rmf-human-boundary-reviewer",
    "rmf-report-reviewer",
    "rmf-gate-closure-reviewer",
    "rmf-cer-linkage-reviewer",
}


def test_registry_contains_all_22_agents() -> None:
    from deerflow.subagents.builtins import BUILTIN_SUBAGENTS

    actual = set(BUILTIN_SUBAGENTS.keys())
    missing = EXPECTED_AGENT_NAMES - actual
    extra = actual - EXPECTED_AGENT_NAMES

    assert not missing, f"missing agents in registry: {sorted(missing)}"
    assert not extra, f"unexpected extra agents in registry: {sorted(extra)}"
    assert len(BUILTIN_SUBAGENTS) == 22


def test_each_agent_has_non_empty_system_prompt() -> None:
    from deerflow.subagents.builtins import BUILTIN_SUBAGENTS

    for name, config in BUILTIN_SUBAGENTS.items():
        assert isinstance(config.system_prompt, str), f"{name}: system_prompt must be str"
        assert len(config.system_prompt) > 100, (
            f"{name}: system_prompt too short ({len(config.system_prompt)} chars) — "
            "likely a missing or empty prompt file"
        )


def test_review_agents_disallow_recursive_task_tool() -> None:
    """Review agents must not be able to spawn additional subagents (no `task` tool)."""
    from deerflow.subagents.builtins import BUILTIN_SUBAGENTS

    review_agents = CER_NEW_REVIEW_AGENTS | RMF_REVIEW_AGENTS
    for name in review_agents:
        config = BUILTIN_SUBAGENTS[name]
        tools = config.tools or []
        disallowed = config.disallowed_tools or []
        assert "task" not in tools, f"{name}: tools list must not include 'task'"
        assert "task" in disallowed, f"{name}: disallowed_tools must include 'task'"


def test_review_agents_have_consistent_default_tools() -> None:
    """Review agents must have read_file/ls/write_file/str_replace at minimum."""
    from deerflow.subagents.builtins import BUILTIN_SUBAGENTS

    required_tools = {"read_file", "ls", "write_file", "str_replace"}
    review_agents = CER_NEW_REVIEW_AGENTS | RMF_REVIEW_AGENTS
    for name in review_agents:
        config = BUILTIN_SUBAGENTS[name]
        tools = set(config.tools or [])
        missing_tools = required_tools - tools
        assert not missing_tools, f"{name}: missing required tools {missing_tools}"


def test_cer_review_agents_count_is_ten() -> None:
    from deerflow.subagents.builtins import BUILTIN_SUBAGENTS

    cer_review = [n for n in BUILTIN_SUBAGENTS if n in CER_NEW_REVIEW_AGENTS]
    assert len(cer_review) == 10, f"expected 10 CER D1 review agents, got {len(cer_review)}: {cer_review}"


def test_rmf_review_agents_count_is_eight() -> None:
    from deerflow.subagents.builtins import BUILTIN_SUBAGENTS

    rmf_review = [n for n in BUILTIN_SUBAGENTS if n in RMF_REVIEW_AGENTS]
    assert len(rmf_review) == 8, f"expected 8 RMF agents (7 reviewers + 1 linkage), got {len(rmf_review)}"


def test_inherit_model_for_review_agents() -> None:
    """All review agents should inherit the parent model (no hardcoded model lock-in)."""
    from deerflow.subagents.builtins import BUILTIN_SUBAGENTS

    review_agents = CER_NEW_REVIEW_AGENTS | RMF_REVIEW_AGENTS
    for name in review_agents:
        config = BUILTIN_SUBAGENTS[name]
        assert config.model == "inherit", (
            f"{name}: model must be 'inherit' so review agents can run on the same model "
            f"as the parent runner; got {config.model!r}"
        )
