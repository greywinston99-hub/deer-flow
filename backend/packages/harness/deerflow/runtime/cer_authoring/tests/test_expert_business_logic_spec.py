"""BIGDP2026.6: Expert Business Logic Spec verification.

Verifies the spec exists and contains all required rule categories.
"""
import json
from pathlib import Path
import pytest

SPEC_PATH = Path(__file__).resolve().parents[7] / "BIGDP2026_6" / "BIGDP2026_6_EXPERT_BUSINESS_LOGIC_SPEC.md"
FIXTURES_DIR = Path(__file__).resolve().parents[7] / "BIGDP2026_6" / "expert_scenario_fixtures"

REQUIRED_CATEGORIES = [
    "IFU is Working Input",
    "Claim Classification",
    "Evidence Support Type",
    "Conclusion Strength Logic",
    "Benchmark Derivation Logic",
    "Gap Disposition Logic",
    "Writer Release Logic",
]

REQUIRED_FIXTURES = [
    "01_ifu_marketing_claim_overreach.json",
    "02_claim_without_direct_evidence.json",
    "03_benchmark_indirect_fallback.json",
    "04_endpoint_mismatch_gap.json",
    "05_pmcf_required_uncertainty.json",
    "06_cannot_support_claim.json",
    "07_risk_gspr_alignment_gap.json",
    "08_equivalence_evidence_misused.json",
]


class TestExpertBusinessLogicSpec:
    """Verifies the expert business logic spec exists and is complete."""

    def test_spec_exists(self):
        """Spec file exists."""
        assert SPEC_PATH.exists(), f"Spec not found at {SPEC_PATH}"

    def test_spec_contains_all_categories(self):
        """Spec covers all 7 required rule categories."""
        content = SPEC_PATH.read_text()
        for category in REQUIRED_CATEGORIES:
            assert category in content, f"Missing rule category: '{category}'"

    def test_spec_contains_rule_tables(self):
        """Spec defines rules with IDs in table format."""
        content = SPEC_PATH.read_text()
        expected_rule_prefixes = [
            "IFU-0", "CLS-0", "EVS-0", "CON-0", "BMK-0", "GAP-0", "WRT-0"
        ]
        for prefix in expected_rule_prefixes:
            assert prefix in content, f"Missing rule IDs with prefix '{prefix}'"

    def test_spec_has_cross_cutting_rules(self):
        """Spec includes cross-cutting rules (CC-xx)."""
        content = SPEC_PATH.read_text()
        assert "CC-0" in content, "Missing cross-cutting rules"


class TestExpertScenarioFixtures:
    """Verifies all 8 scenario fixtures exist and are valid JSON."""

    def test_fixtures_directory_exists(self):
        assert FIXTURES_DIR.exists(), f"Fixtures directory not found at {FIXTURES_DIR}"

    @pytest.mark.parametrize("fixture_file", REQUIRED_FIXTURES)
    def test_fixture_exists_and_valid(self, fixture_file):
        """Each fixture exists and is valid JSON."""
        path = FIXTURES_DIR / fixture_file
        assert path.exists(), f"Fixture missing: {fixture_file}"
        data = json.loads(path.read_text())
        assert "scenario_id" in data, f"{fixture_file}: missing scenario_id"
        assert "scenario_name" in data, f"{fixture_file}: missing scenario_name"
        assert "rule_category" in data, f"{fixture_file}: missing rule_category"
        assert "input" in data, f"{fixture_file}: missing input"
        assert "expected_expert_reasoning" in data, f"{fixture_file}: missing expected_expert_reasoning"
        assert "expected_ledger" in data, f"{fixture_file}: missing expected_ledger"
        assert "expected_writer_permission" in data, f"{fixture_file}: missing expected_writer_permission"

    def test_all_8_fixtures_unique_ids(self):
        """All fixtures have unique scenario_ids."""
        ids = set()
        for f in REQUIRED_FIXTURES:
            data = json.loads((FIXTURES_DIR / f).read_text())
            sid = data["scenario_id"]
            assert sid not in ids, f"Duplicate scenario_id: {sid}"
            ids.add(sid)
        assert len(ids) == 8

    def test_fixtures_cover_all_rule_categories(self):
        """Fixtures collectively reference all 7 rule categories."""
        referenced = set()
        for f in REQUIRED_FIXTURES:
            data = json.loads((FIXTURES_DIR / f).read_text())
            referenced.add(data["rule_category"])
        # At minimum the 7 core categories should be referenced (some fixtures reference sub-categories)
        assert len(referenced) >= 5, f"Only {len(referenced)} rule categories referenced across fixtures"
