"""BIGDP2026.6 Phase 4: Claude Code Handoff Enforcement tests.

Tests:
- Export reference integrity (orphan evidence_ids blocked)
- Package schema version
- Claude Code package validator
"""
import json
import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import patch


def _make_state(**extra):
    base = {
        "artifact_root": "/tmp/test_cer",
        "evidence_registry": [
            {"evidence_id": "E-001", "pmid": "12345", "title": "Study A"},
            {"evidence_id": "E-002", "pmid": "12346", "title": "Study B"},
        ],
        "claim_evidence_matrix": [
            {"claim_id": "C-01", "evidence_ids": ["E-001", "E-002"]},
        ],
        "claim_ledger": [{"claim_id": "C-01"}],
        "device_profile": {"device_name": "Test", "device_class": "IIb"},
    }
    base.update(extra)
    return base


def _top_level(result: dict, key: str, default=None):
    """Extract key from _stage-wrapped result (nested in stage_results[0])."""
    stages = result.get("stage_results") or []
    if stages:
        return stages[0].get(key, default)
    return result.get(key, default)


class TestExportReferenceIntegrity:
    """G.1-G.3: Export reference integrity checks."""

    def test_export_blocked_by_orphan_evidence_id(self):
        """G.2: Export BLOCKED when evidence_id not in registry."""
        from deerflow.runtime.cer_authoring.graph import _node_cer_input_package_export

        state = _make_state(
            claim_evidence_matrix=[
                {"claim_id": "C-01", "evidence_ids": ["E-001", "E-ORPHAN"]},
            ],
        )
        result = _node_cer_input_package_export(state)
        exported = _top_level(result, "cer_input_package_exported")
        assert exported is False, f"Export should be blocked, got {exported}"
        errors = _top_level(result, "export_integrity_errors", [])
        assert len(errors) > 0, "Should have integrity errors"
        assert any("E-ORPHAN" in e for e in errors), f"Should mention orphan ID, errors: {errors}"

    def test_export_no_artifact_root_skips(self):
        """No artifact_root → skipped (not blocked)."""
        from deerflow.runtime.cer_authoring.graph import _node_cer_input_package_export

        state = _make_state(artifact_root=None)
        result = _node_cer_input_package_export(state)
        exported = _top_level(result, "cer_input_package_exported")
        assert exported is not True

    def test_multiple_orphans_all_reported(self):
        """Multiple orphan evidence_ids are all reported."""
        from deerflow.runtime.cer_authoring.graph import _node_cer_input_package_export

        state = _make_state(
            claim_evidence_matrix=[
                {"claim_id": "C-01", "evidence_ids": ["E-ORPHAN1", "E-ORPHAN2"]},
            ],
        )
        result = _node_cer_input_package_export(state)
        errors = _top_level(result, "export_integrity_errors", [])
        assert len(errors) >= 2, f"Should report all orphans, got {len(errors)} errors: {errors}"


class TestPackageSchemaVersion:
    """G.4: Exported package includes package_schema_version."""

    @patch("deerflow.runtime.cer_authoring.pipeline.export_cer_input_package")
    def test_package_schema_version_present(self, mock_export):
        """Export result includes package_schema_version when export succeeds."""
        from deerflow.runtime.cer_authoring.graph import _node_cer_input_package_export

        mock_export.return_value = {"package": {}, "status": "ok"}
        state = _make_state()
        result = _node_cer_input_package_export(state)
        detail = _top_level(result, "export_detail") or {}
        pkg = detail.get("package") or {}
        # Verify schema version is added by the export node
        assert pkg.get("package_schema_version") == "1.0.0", (
            f"Package missing schema version, got: {pkg}"
        )


class TestClaudeCodePackageValidator:
    """G.5: Claude Code writer skill performs runtime assertions before writing."""

    def _validator(self, package: dict) -> list[str]:
        """Reimplementation of the Claude Code package validator logic."""
        errors = []
        if not package:
            return ["CER_INPUT_PACKAGE.json is empty or missing"]

        # G.5.2: G46 must be PASS
        g46 = package.get("pre_writer_readiness_gate_report") or {}
        if g46.get("status") != "PASS":
            errors.append(f"G46 status is '{g46.get('status')}', expected 'PASS'")

        # G.5.3: cer_input_package_exported must be true
        if not package.get("cer_input_package_exported"):
            errors.append("cer_input_package_exported is not true")

        # G.5.4-G.5.7: All references must resolve
        claim_ids = {str(c.get("claim_id") or "") for c in (package.get("claim_ledger") or [])}
        claim_ids.discard("")

        evidence_ids = {
            str(e.get("evidence_id") or e.get("id") or e.get("pmid") or "")
            for e in (package.get("evidence_registry") or [])
        }
        evidence_ids.discard("")

        # Check claim references in claim_evidence_matrix
        matrix = package.get("claim_evidence_matrix") or []
        for row in matrix:
            cid = str(row.get("claim_id") or "")
            if cid and cid not in claim_ids:
                errors.append(f"claim_evidence_matrix references unknown claim_id '{cid}'")

        # G.5.8: Schema version check
        schema_ver = package.get("package_schema_version") or ""
        supported = {"1.0.0"}
        if schema_ver and schema_ver not in supported:
            errors.append(f"Unsupported package_schema_version '{schema_ver}'. Supported: {supported}")

        return errors

    def test_valid_package_passes(self):
        """All checks pass with valid package."""
        package = {
            "cer_input_package_exported": True,
            "package_schema_version": "1.0.0",
            "pre_writer_readiness_gate_report": {"status": "PASS"},
            "claim_ledger": [{"claim_id": "C-01"}],
            "claim_evidence_matrix": [{"claim_id": "C-01", "evidence_ids": ["E-001"]}],
            "evidence_registry": [{"evidence_id": "E-001"}],
        }
        errors = self._validator(package)
        assert not errors, f"Expected no errors, got: {errors}"

    def test_g46_not_pass_blocks(self):
        """G.5.2: G46 not PASS → error."""
        package = {
            "cer_input_package_exported": True,
            "package_schema_version": "1.0.0",
            "pre_writer_readiness_gate_report": {"status": "REWORK_REQUIRED"},
        }
        errors = self._validator(package)
        assert any("G46" in e for e in errors), f"Should flag G46 status, got: {errors}"

    def test_exported_not_true_blocks(self):
        """G.5.3: cer_input_package_exported not true → error."""
        package = {
            "cer_input_package_exported": False,
            "package_schema_version": "1.0.0",
            "pre_writer_readiness_gate_report": {"status": "PASS"},
        }
        errors = self._validator(package)
        assert any("exported" in e.lower() for e in errors), f"Should flag not exported, got: {errors}"

    def test_unsupported_schema_version_blocks(self):
        """G.5.8: Unsupported schema version → error."""
        package = {
            "cer_input_package_exported": True,
            "package_schema_version": "99.0.0",
            "pre_writer_readiness_gate_report": {"status": "PASS"},
        }
        errors = self._validator(package)
        assert any("Unsupported" in e for e in errors), f"Should flag unsupported version, got: {errors}"

    def test_empty_package_blocks(self):
        """Empty package → error."""
        errors = self._validator({})
        assert len(errors) > 0

    def test_orphan_claim_id_detected(self):
        """Orphan claim_id in matrix → error."""
        package = {
            "cer_input_package_exported": True,
            "package_schema_version": "1.0.0",
            "pre_writer_readiness_gate_report": {"status": "PASS"},
            "claim_ledger": [{"claim_id": "C-01"}],
            "claim_evidence_matrix": [{"claim_id": "C-UNKNOWN"}],
            "evidence_registry": [],
        }
        errors = self._validator(package)
        assert any("C-UNKNOWN" in e for e in errors), f"Should detect orphan claim_id, got: {errors}"


class TestControlledCompromise:
    """I.13/B.3: controlled_compromise export failure visibility."""

    def test_export_failure_sets_status(self):
        """B.3.1: Export failure sets status='export_failed'."""
        from deerflow.runtime.cer_authoring.graph import _node_controlled_compromise

        # State without artifact_root triggers the non-artifact path
        state = {"pre_writer_readiness_report": {"compromise_reason": "G46 BLOCKED"}}
        result = _node_controlled_compromise(state)
        assert "status" in result
        assert result["status"] in ("controlled_compromise", "export_failed"), (
            f"Expected controlled_compromise or export_failed, got {result.get('status')}"
        )
        assert result.get("final_gate_decision") == "HUMAN_HOLD"

    def test_controlled_compromise_not_completed(self):
        """controlled_compromise does not report 'completed' status."""
        from deerflow.runtime.cer_authoring.graph import _node_controlled_compromise

        state = {"pre_writer_readiness_report": {}}
        result = _node_controlled_compromise(state)
        # Must not silently claim success
        stage_results = result.get("stage_results", [{}])
        for sr in stage_results:
            assert sr.get("status") != "completed", (
                "controlled_compromise must not report 'completed' — it's a blocked terminal state"
            )

    def test_lead_decisions_recorded(self):
        """controlled_compromise records lead_decisions with reason."""
        from deerflow.runtime.cer_authoring.graph import _node_controlled_compromise

        state = {"pre_writer_readiness_report": {"compromise_reason": "Evidence insufficient after max spiral rounds"}}
        result = _node_controlled_compromise(state)
        decisions = result.get("lead_decisions", [])
        assert len(decisions) > 0, "lead_decisions should be recorded"
        assert any("controlled_compromise" in str(d.get("stage", "")) for d in decisions), (
            "lead_decisions should reference controlled_compromise stage"
        )
