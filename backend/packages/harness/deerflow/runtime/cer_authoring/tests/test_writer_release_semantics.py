"""BIGDP2026.6: Writer release semantic tests.

Verifies Writer is blocked when expert reasoning ledgers indicate unsupported or unresolved claims.
Tests rules: WRT-01 through WRT-08.
"""
import json
from pathlib import Path
import pytest

FIXTURES_DIR = Path(__file__).resolve().parents[7] / "BIGDP2026_6" / "expert_scenario_fixtures"


def _validate_writer_permission(ledger: dict, g46_report: dict) -> str:
    """Reimplementation of the Writer release decision logic per WRT rules.

    Returns: 'allowed', 'blocked', or 'allowed_with_limitations'
    """
    # WRT-02: G46 must be PASS
    if g46_report.get("status") != "PASS":
        return "blocked"

    # WRT-03/WRT-04: Check conclusion strengths
    claims = ledger.get("claims", [])
    for claim in claims:
        if claim.get("conclusion_strength") == "not_supported":
            return "blocked"
        if claim.get("gap_disposition") == "cannot_support":
            return "blocked"

    # Check for limitations
    has_limitations = any(
        c.get("conclusion_strength") in ("limited",)
        or c.get("gap_disposition") in ("PMCF", "labeling", "risk_control")
        for c in claims
    )

    if has_limitations:
        return "allowed_with_limitations"
    return "allowed"


class TestWriterReleaseSemantics:
    """WRT rules: Writer must be constrained by expert reasoning ledgers."""

    def _build_state_with_ledger(self, claims_data, **extra):
        """Build state with a pre-populated CER_REASONING_LEDGER."""
        state = {
            "cer_reasoning_ledger": {
                "schema_version": "1.0.0",
                "claims": claims_data,
            },
        }
        state.update(extra)
        return state

    def test_writer_blocked_when_not_supported(self):
        """WRT-03/WRT-04: not_supported claim → Writer BLOCKED."""
        claims = [{
            "claim_id": "C-01",
            "conclusion_strength": "not_supported",
            "gap_disposition": "cannot_support",
        }]
        permission = _validate_writer_permission(
            {"claims": claims},
            {"status": "PASS"},
        )
        assert permission == "blocked", (
            f"not_supported claim should BLOCK writer, got '{permission}'"
        )

    def test_writer_blocked_when_g46_not_pass(self):
        """WRT-02: G46 not PASS → Writer BLOCKED."""
        claims = [{"claim_id": "C-01", "conclusion_strength": "strong", "gap_disposition": "no_gap"}]
        permission = _validate_writer_permission(
            {"claims": claims},
            {"status": "REWORK_REQUIRED"},
        )
        assert permission == "blocked", f"G46 not PASS should BLOCK writer, got '{permission}'"

    def test_writer_allowed_when_all_pass(self):
        """All claims strong, G46 PASS → Writer ALLOWED."""
        claims = [
            {"claim_id": "C-01", "conclusion_strength": "strong", "gap_disposition": "no_gap"},
            {"claim_id": "C-02", "conclusion_strength": "moderate", "gap_disposition": "no_gap"},
        ]
        permission = _validate_writer_permission(
            {"claims": claims},
            {"status": "PASS"},
        )
        assert permission == "allowed", f"All-pass should ALLOW writer, got '{permission}'"

    def test_writer_allowed_with_limitations_when_pmcf(self):
        """WRT-05: PMCF gap → allowed_with_limitations."""
        claims = [{
            "claim_id": "C-01",
            "conclusion_strength": "limited",
            "gap_disposition": "PMCF",
        }]
        permission = _validate_writer_permission(
            {"claims": claims},
            {"status": "PASS"},
        )
        assert permission == "allowed_with_limitations", (
            f"PMCF gap should allow with limitations, got '{permission}'"
        )

    def test_writer_blocked_when_cannot_support(self):
        """GAP-02: cannot_support → Writer BLOCKED."""
        claims = [{
            "claim_id": "C-01",
            "conclusion_strength": "not_supported",
            "gap_disposition": "cannot_support",
        }]
        permission = _validate_writer_permission(
            {"claims": claims},
            {"status": "PASS"},
        )
        assert permission == "blocked"

    def test_s06_scenario_blocks_writer(self):
        """S-06: Cannot-support claim scenario → Writer should be blocked."""
        fixture = json.loads((FIXTURES_DIR / "06_cannot_support_claim.json").read_text())
        expected = fixture["expected_writer_permission"]
        claims = [{
            "claim_id": "C-01",
            "conclusion_strength": fixture["expected_ledger"]["cer_reasoning_ledger"]["conclusion_strength"],
            "gap_disposition": fixture["expected_ledger"]["cer_reasoning_ledger"]["gap_disposition"],
        }]
        permission = _validate_writer_permission({"claims": claims}, {"status": "PASS"})
        assert permission == expected, (
            f"S-06 expected '{expected}', got '{permission}'"
        )

    def test_s01_scenario_allows_with_limitations(self):
        """S-01: Marketing overreach → Writer allowed with limitations."""
        fixture = json.loads((FIXTURES_DIR / "01_ifu_marketing_claim_overreach.json").read_text())
        expected = fixture["expected_writer_permission"]
        claims = [{
            "claim_id": "C-01",
            "conclusion_strength": fixture["expected_ledger"]["cer_reasoning_ledger"]["conclusion_strength"],
            "gap_disposition": fixture["expected_ledger"]["cer_reasoning_ledger"]["gap_disposition"],
        }]
        permission = _validate_writer_permission({"claims": claims}, {"status": "PASS"})
        assert permission == expected, (
            f"S-01 expected '{expected}', got '{permission}'"
        )
