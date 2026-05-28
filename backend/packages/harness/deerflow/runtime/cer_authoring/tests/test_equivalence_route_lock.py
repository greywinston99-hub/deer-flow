"""WS7: Equivalence Route Lock Tests."""

from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from deerflow.runtime.cer_authoring.equivalence_route_lock import (
    build_equivalence_route_lock,
    ALLOWED_EQUIVALENCE_DECISIONS,
)


class TestEquivalenceRouteLock:
    def test_no_similar_device_not_claimed(self):
        state = {"similar_devices": []}
        lock = build_equivalence_route_lock(state)
        assert lock["decision"] == "equivalence_not_claimed"
        assert lock["equivalence_claimed"] is False

    def test_similar_device_background_only(self):
        state = {
            "similar_devices": [{"device_id": "D1", "name": "Competitor X"}],
            "reference_similar_device_data": False,
        }
        lock = build_equivalence_route_lock(state)
        assert lock["decision"] == "similar_device_background_only"

    def test_full_equivalence_claimed_with_complete_matrices(self):
        eq_data = {
            "similar_devices": [{"device_id": "D1"}],
            "reference_clinical_data": True,
            "technical_equivalence": {"comparison_complete": True, "rows": [{}]},
            "biological_equivalence": {"comparison_complete": True, "rows": [{}]},
            "clinical_equivalence": {"comparison_complete": True, "rows": [{}]},
        }
        lock = build_equivalence_route_lock({}, eq_data)
        assert lock["decision"] == "full_equivalence_claimed"
        assert lock["equivalence_closed"] is True

    def test_customer_risk_accepted_data_gap(self):
        eq_data = {
            "similar_devices": [{"device_id": "D1"}],
            "reference_clinical_data": True,
            "technical_equivalence": {"comparison_complete": False},
            "biological_equivalence": {"comparison_complete": False},
            "clinical_equivalence": {"comparison_complete": False},
        }
        state = {"customer_risk_accepted_data_gap": True}
        lock = build_equivalence_route_lock(state, eq_data)
        assert lock["decision"] == "customer_risk_accepted_data_gap"

    def test_incomplete_matrices_without_risk_acceptance(self):
        eq_data = {
            "similar_devices": [{"device_id": "D1"}],
            "reference_clinical_data": True,
            "technical_equivalence": {},
            "biological_equivalence": {},
            "clinical_equivalence": {},
        }
        lock = build_equivalence_route_lock({}, eq_data)
        assert lock["decision"] == "equivalence_not_claimed"

    def test_writer_instruction_for_not_claimed(self):
        state = {"similar_devices": []}
        lock = build_equivalence_route_lock(state)
        assert "Equivalence is not claimed" in lock["writer_instruction"]

    def test_writer_instruction_for_claimed(self):
        eq_data = {
            "similar_devices": [{"device_id": "D1"}],
            "reference_clinical_data": True,
            "technical_equivalence": {"comparison_complete": True, "rows": [{}]},
            "biological_equivalence": {"comparison_complete": True, "rows": [{}]},
            "clinical_equivalence": {"comparison_complete": True, "rows": [{}]},
        }
        lock = build_equivalence_route_lock({}, eq_data)
        assert "equivalent device" in lock["writer_instruction"].lower()

    def test_all_allowed_decisions_are_valid(self):
        for decision in ALLOWED_EQUIVALENCE_DECISIONS:
            assert isinstance(decision, str)
            assert len(decision) > 5

    def test_manufacturer_intake_risk_acceptance(self):
        eq_data = {
            "similar_devices": [{"device_id": "D1"}],
            "reference_clinical_data": True,
            "technical_equivalence": {},
            "biological_equivalence": {},
            "clinical_equivalence": {},
        }
        intake = {"confirmed_fields": {"data_gap_risk_accepted": "true"}}
        lock = build_equivalence_route_lock({"manufacturer_intake_report": intake}, eq_data)
        assert lock["decision"] == "customer_risk_accepted_data_gap"
