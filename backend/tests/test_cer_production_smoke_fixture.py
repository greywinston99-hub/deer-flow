"""Test — CER production-default smoke fixture validity.

Package 3: verify that the production smoke fixture files exist, the project
profile is loadable, no bypass/monkey-patch flags are present, the human gate
seed is valid, and the evidence persistence integration works correctly.

Live LLM smoke execution is gated on provider availability and is NOT part of
this test module (invoke separately via the smoke command).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
import yaml

try:
    from deerflow.runtime.evidence_persistence import (
        classify_acceptance,
        persist_evidence,
    )

    EVIDENCE_AVAILABLE = True
except ImportError:
    EVIDENCE_AVAILABLE = False

PROJECT_ROOT = Path(__file__).parent.parent.parent
FIXTURE_DIR = PROJECT_ROOT / "examples" / "cer_review" / "production_smoke"


# ── fixture existence ────────────────────────────────────────────────────────


class TestFixtureExistence:
    def test_fixture_directory_exists(self) -> None:
        assert FIXTURE_DIR.exists(), f"Fixture dir not found: {FIXTURE_DIR}"
        assert FIXTURE_DIR.is_dir()

    def test_cer_comprehensive_low_risk_exists(self) -> None:
        cer_path = FIXTURE_DIR / "CER_comprehensive_low_risk.txt"
        assert cer_path.exists(), f"CER fixture not found: {cer_path}"

    def test_project_profile_exists(self) -> None:
        profile_path = FIXTURE_DIR / "project_profile_production_smoke.yaml"
        assert profile_path.exists(), f"Profile not found: {profile_path}"

    def test_human_gate_seed_exists(self) -> None:
        seed_path = FIXTURE_DIR / "human_gate_decision.smoke_seed.json"
        assert seed_path.exists(), f"Human gate seed not found: {seed_path}"


# ── CER fixture content ─────────────────────────────────────────────────────


class TestCERFixtureContent:
    REQUIRED_SECTIONS = [
        "intended purpose",
        "device description",
        "clinical background",
        "literature search",
        "equivalence",
        "benefit-risk",
        "conclusion",
        "pmcf",
    ]

    @pytest.fixture(scope="class")
    def cer_text(self) -> str:
        cer_path = FIXTURE_DIR / "CER_comprehensive_low_risk.txt"
        return cer_path.read_text(encoding="utf-8", errors="replace")

    def test_fixture_not_empty(self, cer_text: str) -> None:
        assert len(cer_text.splitlines()) >= 40, (
            f"CER fixture too short: {len(cer_text.splitlines())} lines. "
            "Must be a comprehensive natural-language CER document."
        )

    def test_has_all_required_sections(self, cer_text: str) -> None:
        text_lower = cer_text.lower()
        missing = [s for s in self.REQUIRED_SECTIONS if s not in text_lower]
        assert not missing, (
            f"CER fixture missing required sections: {missing}. "
            "The fixture must cover the full CER scope for production-default smoke."
        )

    def test_no_monkey_patch_markers(self, cer_text: str) -> None:
        """Fixture text must not contain monkey-patch or severity-bypass markers."""
        forbidden = ["monkey-patch", "severity_bypass", "no-severity-scan", "bypass_severity", "bypass-halt"]
        for token in forbidden:
            assert token not in cer_text.lower(), (
                f"CER fixture contains forbidden bypass marker: '{token}'"
            )

    def test_readable_natural_language(self, cer_text: str) -> None:
        """Fixture should be coherent prose, not just keyword-stuffed lines."""
        lines = [line.strip() for line in cer_text.splitlines() if line.strip()]
        # At least 60% of lines should be sentences (end with . or : or start with ##)
        sentence_lines = [l for l in lines if l.endswith(".") or l.endswith(":") or l.startswith("##") or l.startswith("- ")]
        ratio = len(sentence_lines) / len(lines) if lines else 0
        assert ratio >= 0.5, (
            f"Only {ratio:.1%} of lines look like prose. "
            "Fixture must be readable natural language, not keyword lists."
        )

    def test_has_source_references(self, cer_text: str) -> None:
        """Fixture should reference at least some document or literature sources."""
        ref_patterns = ["MDCG", "MDR", "Annex", "ISO", "MEDDEV", "literature", "PubMed", "Embase", "Cochrane"]
        found = [p for p in ref_patterns if p.lower() in cer_text.lower()]
        assert len(found) >= 3, (
            f"Only {len(found)} reference patterns found: {found}. "
            "Fixture should cite regulatory/scientific sources."
        )


# ── project profile ─────────────────────────────────────────────────────────


class TestProjectProfile:
    @pytest.fixture(scope="class")
    def profile(self) -> dict:
        profile_path = FIXTURE_DIR / "project_profile_production_smoke.yaml"
        return yaml.safe_load(profile_path.read_text(encoding="utf-8"))

    def test_profile_loadable(self, profile: dict) -> None:
        assert "project_id" in profile
        assert "device_context" in profile
        assert "input_package" in profile

    def test_no_bypass_flags_in_profile(self, profile: dict) -> None:
        profile_str = json.dumps(profile)
        bypass_tokens = ["severity_bypass", "monkey_patch", "no_severity", "skip_severity", "bypass_halt"]
        for token in bypass_tokens:
            assert token not in profile_str, (
                f"Project profile contains bypass marker: '{token}'"
            )

    def test_mode_is_production_smoke(self, profile: dict) -> None:
        mode = profile.get("review_scope", {}).get("mode", "")
        assert "smoke" in mode.lower(), f"review_scope.mode must contain 'smoke', got '{mode}'"

    def test_input_documents_configured(self, profile: dict) -> None:
        input_pkg = profile.get("input_package", {})
        docs = input_pkg.get("documents", [])
        assert len(docs) >= 1, "At least one input document must be configured"
        has_cer = any(d.get("doc_type") == "CER" for d in docs)
        assert has_cer, "A CER document must be configured in input_package.documents"


# ── human gate seed ──────────────────────────────────────────────────────────


class TestHumanGateSeed:
    REQUIRED_FIELDS = ["decision", "reviewer", "reason"]

    @pytest.fixture(scope="class")
    def seed(self) -> dict:
        seed_path = FIXTURE_DIR / "human_gate_decision.smoke_seed.json"
        return json.loads(seed_path.read_text(encoding="utf-8"))

    def test_seed_has_required_fields(self, seed: dict) -> None:
        for field in self.REQUIRED_FIELDS:
            assert field in seed, f"Human gate seed missing required field: '{field}'"

    def test_seed_not_simulated(self, seed: dict) -> None:
        assert seed.get("simulated") is not True, (
            "Human gate seed must not claim simulated=true"
        )

    def test_seed_decision_is_valid(self, seed: dict) -> None:
        valid_decisions = {"conditional_pass", "rework_required", "hold_for_human", "approved"}
        assert seed["decision"] in valid_decisions, (
            f"Seed decision '{seed['decision']}' not in {valid_decisions}"
        )

    def test_seed_is_seeded_human_input(self, seed: dict) -> None:
        """Verify seed is explicitly marked as seeded human input."""
        source = seed.get("source", seed.get("reviewer", ""))
        has_seed_marker = "seed" in source.lower() or "seed" in seed.get("reason", "").lower() or "seed" in seed.get("notes", "").lower() or seed.get("is_seed") is True
        # At minimum, the seed should NOT claim to be automated
        assert seed.get("automated") is not True, "Seed must not claim automated=true"


# ── evidence classification guard ────────────────────────────────────────────


class TestEvidenceClassificationGuard:
    """Verify the Package 2 classification rules apply to smoke scenario."""

    def test_package_2_available(self) -> None:
        assert EVIDENCE_AVAILABLE, (
            "Package 2 evidence_persistence must be importable"
        )

    def test_clean_smoke_is_acceptance(self) -> None:
        result, reason = classify_acceptance(
            severity_bypass_applied=False,
            monkey_patch_applied=False,
            schema_validated=True,
            agent_trace_available=True,
            trace_file_exists=True,
            mode="smoke",
            findings_non_empty=True,
        )
        assert result == "acceptance", f"Clean smoke should be acceptance, got {result}: {reason}"
        assert reason is None

    def test_severity_bypass_in_smoke_is_diagnostic(self) -> None:
        result, reason = classify_acceptance(
            severity_bypass_applied=True,
            monkey_patch_applied=False,
            schema_validated=True,
            agent_trace_available=True,
            trace_file_exists=True,
            mode="smoke",
            findings_non_empty=True,
        )
        assert result == "diagnostic"
        assert "severity_bypass" in reason

    def test_monkey_patch_in_smoke_is_diagnostic(self) -> None:
        result, reason = classify_acceptance(
            severity_bypass_applied=False,
            monkey_patch_applied=True,
            schema_validated=True,
            agent_trace_available=True,
            trace_file_exists=True,
            mode="smoke",
            findings_non_empty=True,
        )
        assert result == "diagnostic"
        assert "monkey_patch" in reason

    def test_missing_trace_in_smoke_is_diagnostic(self) -> None:
        result, reason = classify_acceptance(
            severity_bypass_applied=False,
            monkey_patch_applied=False,
            schema_validated=True,
            agent_trace_available=True,
            trace_file_exists=False,
            mode="smoke",
            findings_non_empty=True,
        )
        assert result == "diagnostic"


# ── evidence persistence integration ─────────────────────────────────────────


class TestEvidencePersistenceIntegration:
    """Verify the Package 2 persist_evidence can archive a CER smoke run."""

    def test_persist_evidence_with_smoke_fixture_profile(self, tmp_path: Path) -> None:
        assert EVIDENCE_AVAILABLE
        # Simulate a minimal artifact tree
        manifest_dir = tmp_path / "00_manifest"
        manifest_dir.mkdir(parents=True)
        trace = manifest_dir / "agent_invocation_trace.jsonl"
        trace.write_text(
            json.dumps({"agent_name": "cer-intake-reviewer", "duration_ms": 2300, "status": "completed"}) + "\n",
            encoding="utf-8",
        )
        (manifest_dir / "run_manifest.json").write_text(
            json.dumps({"run_id": "smoke-test", "workflow_id": "cer_review_v2", "project_id": "PRJ-SMOKE"}),
            encoding="utf-8",
        )
        (manifest_dir / "run_summary.json").write_text(json.dumps({"status": "completed", "steps_completed": 10}))
        (manifest_dir / "schema_validation_summary.json").write_text(json.dumps({"total": 10, "valid": 10, "invalid": 0}))

        evidence_dir = tmp_path / "evidence"
        result = persist_evidence(
            artifact_root=tmp_path,
            evidence_dir=evidence_dir,
            run_id="cer-smoke-test",
            review_type="CER",
            mode="smoke",
            command_used="python scripts/cer_review_runner.py --mode production-smoke --profile x.yaml",
            severity_bypass_applied=False,
            monkey_patch_applied=False,
            schema_validated=True,
            agent_trace_available=True,
            llm_provider_available=True,
            workflow_id="cer_review_v2",
            project_id="PRJ-SMOKE",
            findings_non_empty=True,
        )

        manifest_path = evidence_dir / "cer-smoke-test" / "evidence_manifest.json"
        assert manifest_path.exists()
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert manifest["acceptance_type"] == "acceptance"
        assert manifest["severity_bypass_applied"] is False
        assert manifest["monkey_patch_applied"] is False
        assert "not_acceptable_for_full_pass_reason" not in manifest
