"""BIGDP2026.6V_3 Batch F/G/H: Semantic support, equivalence, domain, BR/GSPR, Writer QA."""
import pytest
from deerflow.runtime.cer_authoring.expert_rule_loader import (
    validate_semantic_claim_support,
    validate_equivalence_route,
    get_equivalence_limitation_for_writer,
    EQUIVALENCE_ROUTES,
)


class TestU2SemanticSupport:
    def test_direct_match_passes(self):
        result = validate_semantic_claim_support(
            {"endpoint": "hemostasis_time", "population": "adult", "device_name": "VasoSeal"},
            {"endpoint": "hemostasis_time", "population": "adult", "device_studied": "VasoSeal", "support_type": "direct"},
        )
        assert result["is_valid"], f"Expected valid, got: {result['rationale']}"

    def test_endpoint_mismatch_fails(self):
        result = validate_semantic_claim_support(
            {"endpoint": "hemostasis_time"},
            {"endpoint": "blood_loss", "support_type": "direct"},
        )
        assert "endpoint_match" in result["checks_failed"]

    def test_insufficient_support_fails(self):
        result = validate_semantic_claim_support(
            {"endpoint": "hemostasis_time"},
            {"endpoint": "hemostasis_time", "support_type": "insufficient"},
        )
        assert "directness_ok" in result["checks_failed"]

    def test_all_checks_passed(self):
        result = validate_semantic_claim_support(
            {"endpoint": "hemostasis_time", "population": "adult", "device_name": "VasoSeal"},
            {"endpoint": "hemostasis_time", "population": "adult patients", "device_studied": "VasoSeal Pro", "support_type": "direct", "evidence_strength_score": "75"},
        )
        assert result["is_valid"]


class TestU3EquivalenceGate:
    def test_no_equivalence_claimed(self):
        route = validate_equivalence_route({"equivalence_claimed": False})
        assert route == "equivalence_not_claimed"

    def test_missing_dimensions_not_allowed(self):
        route = validate_equivalence_route({
            "equivalence_claimed": True, "equivalent_device_name": "DeviceX",
            "equivalence_technical_comparison": True,
        })
        assert route == "equivalence_not_allowed"

    def test_all_dimensions_no_data_access(self):
        route = validate_equivalence_route({
            "equivalence_claimed": True, "equivalent_device_name": "DeviceX",
            "equivalence_technical_comparison": True,
            "equivalence_biological_comparison": True,
            "equivalence_clinical_comparison": True,
        })
        assert route == "human_gate_required"

    def test_full_equivalence_claimed(self):
        route = validate_equivalence_route({
            "equivalence_claimed": True, "equivalent_device_name": "DeviceX",
            "equivalence_technical_comparison": True,
            "equivalence_biological_comparison": True,
            "equivalence_clinical_comparison": True,
            "equivalence_data_access": True,
            "equivalence_differences_impact_analysis": True,
        })
        assert route == "equivalence_claimed"

    def test_writer_limitation_no_equivalence(self):
        text = get_equivalence_limitation_for_writer("equivalence_not_claimed")
        assert "not claimed" in text.lower()

    def test_equivalence_routes_defined(self):
        assert len(EQUIVALENCE_ROUTES) == 6


class TestU4U5U6:
    """Placeholder for domain library, BR/GSPR, Writer QA — structural coverage."""

    def test_e0_fields_exist(self):
        from deerflow.runtime.cer_authoring.expert_rule_loader import (
            SOURCE_ELIGIBILITY, DATA_USE_ALLOWED, EVIDENCE_TIER, CLINICAL_USE_LIMITATION,
        )
        assert len(SOURCE_ELIGIBILITY) == 5
        assert len(DATA_USE_ALLOWED) == 6
        assert len(EVIDENCE_TIER) == 8
        assert len(CLINICAL_USE_LIMITATION) == 9

    def test_stat_parsers_basic(self):
        from deerflow.runtime.cer_authoring.expert_rule_loader import parse_hr_rr_or
        results = parse_hr_rr_or("HR 0.85 (95% CI 0.70-1.05) p=0.08")
        assert len(results) >= 1
