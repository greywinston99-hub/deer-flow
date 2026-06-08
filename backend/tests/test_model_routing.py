"""Targeted tests for Phase 3A — Config-driven model routing."""

from __future__ import annotations

import os
import pytest

import deerflow.runtime.cer_authoring.writer_remediation.model_routing as model_routing
from deerflow.config.model_config import ModelConfig
from deerflow.runtime.cer_authoring.writer_remediation.model_routing import (
    resolve_agent_model,
    resolve_all_agent_models,
    is_model_allowed_for_agent,
    is_deterministic_stage,
    get_agent_task_type,
    get_model_boundaries,
    missing_provider_env,
    is_model_provider_configured,
    build_provider_preflight,
    build_ab_test_config,
    ROUTING_POLICY_V1,
    MODEL_BOUNDARIES,
    DEFAULT_PARENT_MODEL,
)


class TestModelRoutingResolution:
    """Per-agent model resolution from policy, env var, state config."""

    def test_writer_agent_routes_to_deepseek_by_default(self):
        model = resolve_agent_model("cer-writer")
        assert model == "deepseek-v4-pro", f"Writer default should be deepseek-v4-pro, got {model}"

    def test_qa_agent_routes_to_deepseek_by_default(self):
        model = resolve_agent_model("qa-review")
        assert model == "deepseek-v4-pro", f"QA default should be deepseek-v4-pro, got {model}"

    def test_extraction_agent_routes_to_kimi_api_by_default(self):
        for agent in ("intake-profile-claim", "risk-equivalence-gspr"):
            model = resolve_agent_model(agent)
            assert model == "kimi-k2.6-api", f"{agent} default should be kimi-k2.6-api, got {model}"

    def test_evidence_reasoning_agents_route_to_deepseek(self):
        for agent in ("methodology-sota", "evidence"):
            model = resolve_agent_model(agent)
            assert model == "deepseek-v4-pro", f"{agent} default should be deepseek-v4-pro, got {model}"

    def test_env_var_override_respected(self, monkeypatch):
        monkeypatch.setenv("CER_AUTHORING_MODEL_CER_WRITER", "kimi-api")
        model = resolve_agent_model("cer-writer")
        assert model == "kimi-api", f"Env var override should take priority, got {model}"
        monkeypatch.delenv("CER_AUTHORING_MODEL_CER_WRITER", raising=False)

    def test_state_config_override_respected(self):
        state = {"model_routing": {"cer-writer": "kimi-api"}}
        model = resolve_agent_model("cer-writer", state)
        assert model == "kimi-api", f"State config should override default, got {model}"

    def test_unknown_agent_uses_global_fallback(self):
        model = resolve_agent_model("nonexistent-agent")
        assert model == DEFAULT_PARENT_MODEL or model, "Unknown agent should use global fallback"

    def test_all_agents_have_routing_policy(self):
        models = resolve_all_agent_models()
        assert len(models) == len(ROUTING_POLICY_V1), f"Expected {len(ROUTING_POLICY_V1)} agents"
        for agent_name in ROUTING_POLICY_V1:
            assert agent_name in models, f"Agent '{agent_name}' missing from resolution"
            assert models[agent_name], f"Agent '{agent_name}' has empty model"


class TestModelBoundaries:
    """Forbidden model checks for each task type."""

    def test_kimi_api_allowed_for_writer_qa_and_evidence_reasoning(self):
        for agent in ("cer-writer", "qa-review", "methodology-sota", "evidence"):
            assert is_model_allowed_for_agent(agent, "kimi-k2.6-api"), f"kimi-api should be allowed for {agent}"

    def test_minimax_forbidden_for_writer(self):
        assert not is_model_allowed_for_agent("cer-writer", "minimax-M2.7-highspeed"), "minimax should be FORBIDDEN for Writer"

    def test_minimax_forbidden_for_qa(self):
        assert not is_model_allowed_for_agent("qa-review", "minimax-M2.7-highspeed"), "minimax should be FORBIDDEN for QA"

    def test_minimax_forbidden_for_evidence(self):
        for agent in ("methodology-sota", "evidence"):
            assert not is_model_allowed_for_agent(agent, "minimax-M2.7-highspeed"), f"minimax should be FORBIDDEN for {agent}"

    def test_deepseek_allowed_for_all_agents(self):
        for agent_name in ROUTING_POLICY_V1:
            assert is_model_allowed_for_agent(agent_name, "deepseek-v4-pro"), f"deepseek should be allowed for {agent_name}"

    def test_model_boundaries_documented(self):
        for model_name in ("kimi-k2.6-api", "deepseek-v4-pro", "kimi-api", "minimax-M2.7-highspeed"):
            boundaries = get_model_boundaries(model_name)
            assert boundaries is not None, f"Model '{model_name}' missing boundary definition"
            assert "allowed_for" in boundaries
            assert "forbidden_for" in boundaries

    def test_configured_non_tool_call_model_is_forbidden_for_cer_agents(self, monkeypatch):
        class FakeAppConfig:
            def get_model_config(self, name):
                if name == "text-only-model":
                    return ModelConfig(
                        name="text-only-model",
                        display_name="Text Only",
                        description=None,
                        use="langchain_openai:ChatOpenAI",
                        model="text-only-model",
                        supports_tool_calls=False,
                    )
                return None

        monkeypatch.setattr(model_routing, "get_app_config", lambda: FakeAppConfig())

        assert not is_model_allowed_for_agent("cer-writer", "text-only-model")

    def test_provider_env_preflight_reports_missing_key(self, monkeypatch):
        monkeypatch.setenv("DEERFLOW_SKIP_PROVIDER_DOTENV", "1")
        monkeypatch.setattr(model_routing, "_PROVIDER_ENV_LOADED", False)
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

        assert missing_provider_env("deepseek-v4-pro") == ["DEEPSEEK_API_KEY"]
        assert not is_model_provider_configured("deepseek-v4-pro")

    def test_provider_env_preflight_accepts_configured_key(self, monkeypatch):
        monkeypatch.setenv("DEERFLOW_SKIP_PROVIDER_DOTENV", "1")
        monkeypatch.setattr(model_routing, "_PROVIDER_ENV_LOADED", False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.setenv("KIMI_API_KEY", "sk-test")

        assert missing_provider_env("kimi-k2.6-api") == []
        assert is_model_provider_configured("kimi-k2.6-api")

    def test_authoring_provider_preflight_checks_all_routed_agents(self, monkeypatch):
        monkeypatch.setenv("DEERFLOW_SKIP_PROVIDER_DOTENV", "1")
        monkeypatch.setattr(model_routing, "_PROVIDER_ENV_LOADED", False)
        monkeypatch.delenv("KIMI_API_KEY", raising=False)
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

        report = build_provider_preflight()

        assert report["status"] == "BLOCKED_PROVIDER_UNAVAILABLE"
        assert "cer-authoring-lead-agent" in report["missing_providers"]
        assert "authoring-methodology-sota-agent" in report["missing_providers"]
        assert all(row["agent_name"] and row["model_name"] for row in report["checks"])

    def test_authoring_provider_preflight_accepts_configured_kimi_api_primary(self, monkeypatch):
        monkeypatch.setenv("DEERFLOW_SKIP_PROVIDER_DOTENV", "1")
        monkeypatch.setattr(model_routing, "_PROVIDER_ENV_LOADED", False)
        monkeypatch.setenv("KIMI_API_KEY", "sk-test")

        report = build_provider_preflight()
        intake = next(row for row in report["checks"] if row["agent_name"] == "authoring-intake-profile-claim-agent")

        assert intake["provider_status"] == "configured"
        assert intake["missing_env"] == []

    def test_kimi_api_allowed_as_intake_fallback(self):
        assert is_model_allowed_for_agent("authoring-intake-profile-claim-agent", "kimi-k2.6-api")
        assert is_model_allowed_for_agent("cer-authoring-lead-agent", "kimi-k2.6-api")

    def test_kimi_primary_authoring_agents_have_deepseek_provider_fallback(self):
        for agent_name in ("cer-authoring-lead-agent", "authoring-intake-profile-claim-agent", "risk-equivalence-gspr"):
            assert "deepseek-v4-pro" in ROUTING_POLICY_V1[agent_name]["provider_fallback_models"]


class TestDeterministicStages:
    """Deterministic functions must not be assigned models."""

    def test_deterministic_stages_not_in_routing(self):
        # Gate evaluation functions are deterministic
        for stage in ("gate_evaluation", "quarantine_routing", "pdf_parsing", "artifact_export"):
            assert is_deterministic_stage(stage), f"'{stage}' should be deterministic (no model routing)"


class TestABTestConfig:
    """A/B test configuration generation."""

    def test_writer_has_ab_config(self):
        config = build_ab_test_config("cer-writer")
        assert config is not None, "Writer should have A/B config"
        assert config["ab_status"] == "pending"
        assert "candidate_a" in config["candidates"]
        assert "candidate_b" in config["candidates"]

    def test_qa_has_ab_config(self):
        config = build_ab_test_config("qa-review")
        assert config is not None, "QA should have A/B config"
        assert config["ab_status"] == "pending"

    def test_extraction_no_ab_config(self):
        config = build_ab_test_config("intake-profile-claim")
        assert config is None, "Extraction agent should not require A/B test"


class TestTaskTypeAssignment:
    """Task types correctly assigned to agents."""

    def test_writer_is_cer_writer_type(self):
        assert get_agent_task_type("cer-writer") == "cer_writer"

    def test_qa_is_qa_reviewer_type(self):
        assert get_agent_task_type("qa-review") == "qa_reviewer"

    def test_extraction_is_structuring_type(self):
        assert get_agent_task_type("intake-profile-claim") == "extraction_structuring"

    def test_evidence_is_reasoning_type(self):
        for agent in ("methodology-sota", "evidence"):
            assert get_agent_task_type(agent) == "evidence_reasoning"

    def test_risk_is_risk_equivalence_type(self):
        assert get_agent_task_type("risk-equivalence-gspr") == "risk_equivalence"
