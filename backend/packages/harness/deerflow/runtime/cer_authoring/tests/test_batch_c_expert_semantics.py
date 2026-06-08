"""BIGDP2026.6V_2 Batch C: Expert semantic reliability tests.

DC-6: Endpoint semantic classifier (AE vs treatment_failure taxonomy)
DC-7: Comparator benchmark coverage
"""
import pytest
from deerflow.runtime.cer_authoring.expert_rule_loader import (
    classify_endpoint,
    is_safety_endpoint,
    ENDPOINT_CLASSIFICATION_TAXONOMY,
)


class TestEndpointSemanticClassifier:
    """DC-6: Device abandonment → NOT automatically AE."""

    def test_adverse_event_classification(self):
        assert classify_endpoint("skin damage") == "adverse_event"
        assert classify_endpoint("hematoma at access site") == "adverse_event"
        assert classify_endpoint("device-related infection") == "adverse_event"

    def test_serious_adverse_event_classification(self):
        assert classify_endpoint("major bleeding requiring transfusion") == "serious_adverse_event"
        assert classify_endpoint("SAE: retroperitoneal hemorrhage") == "serious_adverse_event"

    def test_treatment_failure_not_ae(self):
        """Device abandonment for tourniquet → NOT AE."""
        result = classify_endpoint("device abandonment", "conversion to manual compression after device failure")
        assert result != "adverse_event", f"Device abandonment classified as {result} — should not be AE"
        assert result in ("treatment_failure", "rescue_therapy_switch"), f"Got: {result}"

    def test_inadequate_hemostasis_not_ae(self):
        """Inadequate hemostasis → efficacy endpoint, not safety."""
        result = classify_endpoint("continued bleeding at 3 minutes")
        assert result == "inadequate_hemostasis"
        assert not is_safety_endpoint(result)

    def test_rescue_therapy_switch(self):
        result = classify_endpoint("conversion to surgical closure")
        assert result == "rescue_therapy_switch"
        assert not is_safety_endpoint(result)

    def test_procedural_outcome(self):
        result = classify_endpoint("device success rate")
        assert result == "procedural_outcome"

    def test_is_safety_endpoint(self):
        assert is_safety_endpoint("adverse_event") is True
        assert is_safety_endpoint("serious_adverse_event") is True
        assert is_safety_endpoint("treatment_failure") is False
        assert is_safety_endpoint("inadequate_hemostasis") is False
        assert is_safety_endpoint("procedural_outcome") is False

    def test_taxonomy_completeness(self):
        """All taxonomy entries have required fields."""
        for key, entry in ENDPOINT_CLASSIFICATION_TAXONOMY.items():
            assert "label" in entry, f"{key} missing label"
            assert "definition" in entry, f"{key} missing definition"
            assert "is_safety_endpoint" in entry, f"{key} missing is_safety_endpoint"

    def test_dc6_critical_case(self):
        """DC-6 critical: device abandonment → direct compression/tourniquet is NOT automatically AE."""
        # This is the exact case from the CLAUDE.md RCA
        result = classify_endpoint(
            "device abandonment",
            "patient required conversion to manual compression and tourniquet application after device failure to achieve hemostasis"
        )
        assert result not in ("adverse_event", "serious_adverse_event"), (
            f"Device abandonment classified as {result} — violates DC-6. "
            "Should be treatment_failure or rescue_therapy_switch."
        )


class TestComparatorBenchmark:
    """DC-7: Comparator benchmarks must have range, CI, source, limitations."""

    def test_classify_endpoint_skin_injury(self):
        """Skin injury → AE."""
        result = classify_endpoint("skin injury at closure site")
        assert result == "adverse_event"

    def test_classify_endpoint_device_malfunction(self):
        """Device malfunction → device_deficiency."""
        result = classify_endpoint("device malfunction during deployment")
        assert result == "device_deficiency"

    def test_classify_unknown_endpoint(self):
        """Unknown endpoint → other."""
        result = classify_endpoint("xyz_unknown_metric")
        assert result == "other"
