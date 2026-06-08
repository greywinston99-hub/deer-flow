"""Test — CER/RMF Review Agent Teams read-only API.

Validates that the agent listing, detail, and runtime-evidence endpoints
return correct data from the subagent registry without leaking secrets.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.gateway.routers.cer_review_agents as agents_router


# ── mock SubagentConfig ──────────────────────────────────────────────────────


@dataclass
class MockSubagentConfig:
    name: str
    description: str = ""
    system_prompt: str = ""
    tools: list[str] | None = None
    disallowed_tools: list[str] | None = field(default_factory=lambda: ["task"])
    model: str = "inherit"
    max_turns: int = 50
    timeout_seconds: int = 900


MOCK_CER_AGENTS = [
    MockSubagentConfig(
        name="cer-intake-reviewer",
        description="Reviews CER intake documents for completeness and compliance.",
        system_prompt="You are a CER intake reviewer. Analyze the provided documents.",
        tools=["read_file", "ls"],
    ),
    MockSubagentConfig(
        name="cer-structure-compliance-reviewer",
        description="Checks CER document structure against MDR Annex XIV requirements.",
        system_prompt="You are a structure compliance reviewer.",
        tools=["read_file", "write_file"],
    ),
    MockSubagentConfig(
        name="cer-clinical-evidence-panel-reviewer",
        description="Evaluates clinical evidence adequacy and equivalence claims.",
        system_prompt="X" * 3000,  # Long prompt to test truncation
        tools=["read_file", "ls", "write_file", "str_replace"],
    ),
]

MOCK_RMF_AGENTS = [
    MockSubagentConfig(
        name="rmf-precheck-reviewer",
        description="Pre-checks RMF and FMEA documents for structural completeness.",
        system_prompt="You are an RMF precheck reviewer.",
        tools=["read_file", "ls"],
    ),
    MockSubagentConfig(
        name="rmf-dimension-reviewer",
        description="Performs six-dimension analysis on RMF documents.",
        system_prompt="You are an RMF dimension reviewer.",
        tools=["read_file", "ls", "bash"],
    ),
]

MOCK_LINKAGE_AGENT = MockSubagentConfig(
    name="rmf-cer-linkage-reviewer",
    description="Cross-references CER and RMF findings for consistency.",
    system_prompt="You are a CER-RMF linkage reviewer.",
    tools=["read_file", "ls"],
)

MOCK_BASH_AGENT = MockSubagentConfig(
    name="bash",
    description="Executes bash commands.",
    system_prompt="",
    tools=["bash"],
)

MOCK_ALL = MOCK_CER_AGENTS + MOCK_RMF_AGENTS + [MOCK_LINKAGE_AGENT, MOCK_BASH_AGENT]


# ── fixtures ─────────────────────────────────────────────────────────────────


def _mock_list_subagents():
    return MOCK_ALL


def _mock_get_subagent_config(name: str):
    for m in MOCK_ALL:
        if m.name == name:
            return m
    return None


@pytest.fixture(autouse=True)
def _patch_registry(monkeypatch):
    """Replace registry functions with mock versions."""
    monkeypatch.setattr(agents_router, "list_subagents", _mock_list_subagents)
    monkeypatch.setattr(agents_router, "get_subagent_config", _mock_get_subagent_config)


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(agents_router.router)
    return TestClient(app)


# ── agent listing ────────────────────────────────────────────────────────────


class TestListAgents:
    def test_returns_all_review_agents(self, client: TestClient) -> None:
        resp = client.get("/api/cer-review/agents")
        assert resp.status_code == 200
        data = resp.json()
        assert "agents" in data
        names = {a["name"] for a in data["agents"]}
        assert "cer-intake-reviewer" in names
        assert "rmf-precheck-reviewer" in names
        assert "rmf-cer-linkage-reviewer" in names
        # bash is not a review agent — should be excluded
        assert "bash" not in names

    def test_filter_by_cer_domain(self, client: TestClient) -> None:
        resp = client.get("/api/cer-review/agents?domain=CER")
        assert resp.status_code == 200
        data = resp.json()
        domains = {a["domain"] for a in data["agents"]}
        assert domains == {"CER"}

    def test_filter_by_rmf_domain(self, client: TestClient) -> None:
        resp = client.get("/api/cer-review/agents?domain=RMF")
        assert resp.status_code == 200
        data = resp.json()
        domains = {a["domain"] for a in data["agents"]}
        assert domains == {"RMF"}

    def test_filter_by_linkage_domain(self, client: TestClient) -> None:
        resp = client.get("/api/cer-review/agents?domain=Linkage")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["agents"]) == 1
        assert data["agents"][0]["name"] == "rmf-cer-linkage-reviewer"

    def test_empty_unknown_domain(self, client: TestClient) -> None:
        resp = client.get("/api/cer-review/agents?domain=NONEXISTENT")
        assert resp.status_code == 200
        assert resp.json()["agents"] == []

    def test_agent_fields_match_config(self, client: TestClient) -> None:
        resp = client.get("/api/cer-review/agents?domain=CER")
        cer_agent = resp.json()["agents"][0]
        required = [
            "name", "domain", "category", "description", "role", "model",
            "tools", "disallowed_tools", "max_turns", "timeout_seconds",
            "prompt_loaded", "prompt_path", "prompt_path_source", "prompt_hash",
            "prompt_preview", "registered",
        ]
        for field in required:
            assert field in cer_agent, f"Missing field: {field}"
        assert cer_agent["registered"] is True

    def test_response_has_total_and_domains(self, client: TestClient) -> None:
        resp = client.get("/api/cer-review/agents")
        data = resp.json()
        assert data["total"] > 0
        assert "CER" in data["domains"]
        assert "RMF" in data["domains"]

    def test_agents_have_category(self, client: TestClient) -> None:
        resp = client.get("/api/cer-review/agents")
        categories = {a["category"] for a in resp.json()["agents"]}
        assert "CER Review" in categories
        assert "RMF Review" in categories

    def test_prompt_path_source_is_explicit_or_derived(self, client: TestClient) -> None:
        resp = client.get("/api/cer-review/agents")
        for agent in resp.json()["agents"]:
            assert agent["prompt_path_source"] in ("explicit", "derived")


# ── agent detail ─────────────────────────────────────────────────────────────


class TestGetAgentDetail:
    def test_returns_detail_with_prompt(self, client: TestClient) -> None:
        resp = client.get("/api/cer-review/agents/cer-intake-reviewer")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "cer-intake-reviewer"
        assert data["domain"] == "CER"
        assert "full_system_prompt" in data
        assert len(data["full_system_prompt"]) > 0
        assert len(data["prompt_preview"]) > 0

    def test_404_for_unknown_agent(self, client: TestClient) -> None:
        resp = client.get("/api/cer-review/agents/nonexistent-agent")
        assert resp.status_code == 404

    def test_404_for_bash_not_review_agent(self, client: TestClient) -> None:
        resp = client.get("/api/cer-review/agents/bash")
        assert resp.status_code == 404


# ── prompt handling ──────────────────────────────────────────────────────────


class TestPromptHandling:
    def test_prompt_loaded_true(self, client: TestClient) -> None:
        resp = client.get("/api/cer-review/agents/cer-intake-reviewer")
        assert resp.json()["prompt_loaded"] is True

    def test_prompt_preview_truncated(self, client: TestClient) -> None:
        resp = client.get("/api/cer-review/agents/cer-clinical-evidence-panel-reviewer")
        data = resp.json()
        # System prompt is 3000 chars; list preview should be <= 1500
        list_resp = client.get("/api/cer-review/agents?domain=CER")
        for agent in list_resp.json()["agents"]:
            if agent["name"] == "cer-clinical-evidence-panel-reviewer":
                assert len(agent["prompt_preview"]) <= 1500
                break


# ── runtime evidence ─────────────────────────────────────────────────────────


class TestRuntimeEvidence:
    def test_no_evidence_when_no_traces(self, client: TestClient, monkeypatch) -> None:
        import tempfile

        tmp = tempfile.mkdtemp()
        monkeypatch.setattr(agents_router, "_PROJECT_ROOT", Path(tmp))
        monkeypatch.setattr(agents_router, "_PACKAGE_2_EVIDENCE_DIR", Path(tmp) / "nonexistent")

        resp = client.get("/api/cer-review/agents/runtime-evidence")
        assert resp.status_code == 200
        data = resp.json()
        assert data["agents"] == []
        assert data["total_traces_found"] == 0
        assert data["evidence_source"] == "no_evidence"

    def test_package2_evidence_priority(self, client: TestClient, tmp_path: Path, monkeypatch) -> None:
        # Set up Package 2 evidence dir (should take priority)
        p2_dir = tmp_path / "artifacts" / "cer_rmf_review_engine" / "evidence" / "run-001"
        manifest_dir = p2_dir / "00_manifest"
        manifest_dir.mkdir(parents=True)
        (p2_dir / "evidence_manifest.json").write_text(json.dumps({"acceptance_type": "acceptance"}))
        trace = manifest_dir / "agent_invocation_trace.jsonl"
        trace.write_text(json.dumps({
            "agent_name": "cer-intake-reviewer",
            "status": "completed",
            "started_at": "2026-04-26T10:00:00Z",
            "duration_ms": 5000,
            "schema_validation": {"valid": True},
        }) + "\n")

        monkeypatch.setattr(agents_router, "_PROJECT_ROOT", tmp_path)
        monkeypatch.setattr(agents_router, "_PACKAGE_2_EVIDENCE_DIR", tmp_path / "artifacts" / "cer_rmf_review_engine" / "evidence")

        resp = client.get("/api/cer-review/agents/runtime-evidence")
        assert resp.status_code == 200
        data = resp.json()
        assert data["evidence_source"] == "persistent_evidence"

    def test_evidence_with_mocked_traces(self, client: TestClient, tmp_path: Path, monkeypatch) -> None:
        # Create fake thread dir with trace and ledger
        thread_dir = tmp_path / "backend" / ".deer-flow" / "threads" / "cer-test-001"
        manifest_dir = thread_dir / "00_manifest"
        manifest_dir.mkdir(parents=True)

        trace = manifest_dir / "agent_invocation_trace.jsonl"
        trace.write_text(
            json.dumps({
                "agent_name": "cer-intake-reviewer",
                "step_id": "cer_intake",
                "status": "completed",
                "started_at": "2026-04-26T10:00:00Z",
                "completed_at": "2026-04-26T10:00:05Z",
                "duration_ms": 5000,
                "schema_validation": {"valid": True},
                "output_artifact": "/tmp/cer/artifacts/00_manifest/intake.json",
            }) + "\n",
            encoding="utf-8",
        )

        ledger = manifest_dir / "agent_usage_ledger.json"
        ledger.write_text(json.dumps({
            "run_id": "cer-test-001",
            "agents_invoked": [
                {"name": "cer-intake-reviewer", "calls": 1, "total_duration_ms": 5000, "failures": 0},
            ],
            "summary": {"total_invocations": 1, "unique_agents": 1},
        }), encoding="utf-8")

        monkeypatch.setattr(agents_router, "_PROJECT_ROOT", tmp_path)

        resp = client.get("/api/cer-review/agents/runtime-evidence")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_traces_found"] >= 1

        agents = {a["agent_name"]: a for a in data["agents"]}
        assert "cer-intake-reviewer" in agents
        ev = agents["cer-intake-reviewer"]
        assert ev["total_invocations"] >= 1
        assert ev["last_status"] == "completed"
        assert ev["last_schema_valid"] is True


# ── no secrets ───────────────────────────────────────────────────────────────


class TestNoSecrets:
    def test_response_has_no_secret_keys(self, client: TestClient) -> None:
        resp = client.get("/api/cer-review/agents")
        data_str = json.dumps(resp.json())
        secret_tokens = ["api_key", "password", "secret", "token", "OPENAI", "ANTHROPIC", "env_var"]
        for token in secret_tokens:
            assert token not in data_str, f"Response contains secret-like token: '{token}'"

    def test_full_prompt_has_no_secrets(self, client: TestClient) -> None:
        resp = client.get("/api/cer-review/agents/cer-intake-reviewer")
        prompt = resp.json().get("full_system_prompt", "")
        secret_tokens = ["api_key", "password", "$OPENAI", "$ANTHROPIC", "Bearer", "Authorization"]
        for token in secret_tokens:
            assert token not in prompt, f"Full prompt contains secret-like token: '{token}'"
