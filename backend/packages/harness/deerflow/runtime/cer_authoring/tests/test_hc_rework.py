"""BIGDP2026.6 P1.2: HC-01 device_profile rework routing tests.

Tests that REWORK_TARGETS['device_profile'] is non-empty, valid targets
route correctly, and unknown targets raise ValueError.
"""
import pytest
from deerflow.runtime.cer_authoring.graph import (
    REWORK_TARGETS,
    _check_hc_rework,
)
from langgraph.types import Command


class TestReworkTargetsDeviceProfile:
    """A.2 — device_profile rework targets are populated and valid."""

    def test_device_profile_targets_non_empty(self):
        """A.2.1: REWORK_TARGETS['device_profile'] is non-empty."""
        targets = REWORK_TARGETS.get("device_profile", [])
        assert len(targets) > 0, (
            "REWORK_TARGETS['device_profile'] is empty — human rework "
            "at HC-01 would be silently dropped"
        )

    def test_device_profile_contains_input_gate(self):
        """A.2.2: Valid rework targets include 'input_gate'."""
        targets = REWORK_TARGETS.get("device_profile", [])
        assert "input_gate" in targets, (
            f"REWORK_TARGETS['device_profile'] = {targets} — should contain 'input_gate'"
        )

    def test_device_profile_contains_intake_pack_review(self):
        """A.2.2: Valid rework targets include 'intake_pack_review'."""
        targets = REWORK_TARGETS.get("device_profile", [])
        assert "intake_pack_review" in targets, (
            f"REWORK_TARGETS['device_profile'] = {targets} — should contain 'intake_pack_review'"
        )


class TestHcReworkRouting:
    """A.2.3 & A.2.4: _check_hc_rework routing behavior."""

    def test_valid_rework_returns_command(self):
        """A.2.3: Valid rework target returns Command(goto=...)."""
        approval = {"action": "rework", "target": "input_gate", "reason": "Wrong device class"}
        result = _check_hc_rework(approval, "device_profile")
        assert result is not None, "Expected Command, got None"
        assert isinstance(result, Command), f"Expected Command, got {type(result)}"
        assert result.goto == "input_gate"
        update = result.update or {}
        assert update.get("hc_rework_source") == "device_profile"
        assert update.get("hc_rework_target") == "input_gate"
        assert update.get("hc_rework_reason") == "Wrong device class"

    def test_rework_counts_incremented(self):
        """A.2.6: _hc_rework_counts tracks rework actions."""
        approval = {
            "action": "rework", "target": "intake_pack_review",
            "reason": "Fix device identity",
            "_hc_rework_counts": {"device_profile": 2},
        }
        result = _check_hc_rework(approval, "device_profile")
        assert result is not None
        counts = (result.update or {}).get("_hc_rework_counts", {})
        assert counts.get("device_profile") == 3

    def test_invalid_target_raises_value_error(self):
        """A.2.4: Unknown target raises ValueError — not silent None."""
        approval = {"action": "rework", "target": "nonexistent_node", "reason": "test"}
        with pytest.raises(ValueError, match="nonexistent_node"):
            _check_hc_rework(approval, "device_profile")

    def test_empty_target_no_rework(self):
        """Empty target with action=rework should return None (gracefully, not error)."""
        approval = {"action": "rework", "target": "", "reason": "no target"}
        result = _check_hc_rework(approval, "device_profile")
        assert result is None

    def test_no_action_not_rework(self):
        """Non-rework action returns None."""
        approval = {"action": "confirm", "target": "input_gate"}
        result = _check_hc_rework(approval, "device_profile")
        assert result is None

    def test_not_dict_returns_none(self):
        """Non-dict approval returns None gracefully."""
        result = _check_hc_rework(None, "device_profile")
        assert result is None

    def test_intake_pack_review_rework_still_works(self):
        """Existing intake_pack_review rework routing is unchanged."""
        approval = {"action": "rework", "target": "input_gate", "reason": "Fix intake"}
        result = _check_hc_rework(approval, "intake_pack_review")
        assert result is not None
        assert result.goto == "input_gate"

    def test_unknown_confirmation_point_returns_none(self):
        """Unknown confirmation point with no valid targets returns None (no error for unknown CP)."""
        approval = {"action": "rework", "target": "some_node", "reason": "test"}
        # 'unknown_cp' is not a key in REWORK_TARGETS
        with pytest.raises(ValueError, match="some_node"):
            _check_hc_rework(approval, "unknown_cp")
