"""Test — evidence persistence helper.

Package 2: ``persist_evidence()`` must copy run artifacts to a fixed evidence
directory, generate an evidence manifest, and enforce acceptance vs diagnostic
classification rules. TDD — red first, then implementation.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

# Import will fail until evidence_persistence.py is created — expected TDD red.
# We use a deferred import pattern so the test file can be parsed before the
# module exists.
EVIDENCE_PERSISTENCE_AVAILABLE = False
try:
    from deerflow.runtime.evidence_persistence import (  # type: ignore[import-not-found]
        classify_acceptance,
        persist_evidence,
    )

    EVIDENCE_PERSISTENCE_AVAILABLE = True
except ImportError:
    pass


# ── helpers ──────────────────────────────────────────────────────────────────


def _make_artifact_tree(base: Path, *, include_trace: bool = True, include_summary: bool = True) -> Path:
    """Create a minimal artifact tree under ``base`` simulating a CER/RMF run.

    Returns the artifact root (base itself).
    """
    manifest_dir = base / "00_manifest"
    manifest_dir.mkdir(parents=True, exist_ok=True)

    if include_trace:
        trace = manifest_dir / "agent_invocation_trace.jsonl"
        trace.write_text(
            json.dumps({"agent_name": "cer-intake-reviewer", "duration_ms": 2300, "status": "completed"}) + "\n",
            encoding="utf-8",
        )

    run_manifest = {
        "run_id": "test-run-001",
        "workflow_id": "cer_review_v2",
        "project_id": "PRJ-TEST-001",
        "review_type": "CER",
        "created_at": "2026-04-26T10:00:00Z",
    }
    (manifest_dir / "run_manifest.json").write_text(json.dumps(run_manifest), encoding="utf-8")

    (manifest_dir / "event_log.json").write_text(
        json.dumps({"events": [{"type": "RUN_STARTED", "timestamp": "2026-04-26T10:00:00Z"}]}),
        encoding="utf-8",
    )

    (manifest_dir / "task_ledger.json").write_text(
        json.dumps({"status": "completed", "timestamp": "2026-04-26T10:05:00Z"}),
        encoding="utf-8",
    )

    (manifest_dir / "agent_usage_ledger.json").write_text(
        json.dumps({"agents": [{"name": "cer-intake-reviewer", "calls": 1, "total_duration_ms": 2300}]}),
        encoding="utf-8",
    )

    if include_summary:
        (manifest_dir / "run_summary.json").write_text(
            json.dumps({"status": "completed", "steps_completed": 10}),
            encoding="utf-8",
        )

    (manifest_dir / "schema_validation_summary.json").write_text(
        json.dumps({"total": 10, "valid": 10, "invalid": 0}),
        encoding="utf-8",
    )

    return base


# ── classification logic ─────────────────────────────────────────────────────


class TestClassifyAcceptance:
    """Unit tests for ``classify_acceptance()`` — pure logic, no I/O."""

    def test_clean_acceptance(self) -> None:
        """All flags clean → acceptance."""
        assert EVIDENCE_PERSISTENCE_AVAILABLE
        result, reason = classify_acceptance(
            severity_bypass_applied=False,
            monkey_patch_applied=False,
            schema_validated=True,
            agent_trace_available=True,
            trace_file_exists=True,
            mode="acceptance",
            findings_non_empty=True,
        )
        assert result == "acceptance"
        assert reason is None

    def test_severity_bypass_blocks_acceptance(self) -> None:
        assert EVIDENCE_PERSISTENCE_AVAILABLE
        result, reason = classify_acceptance(
            severity_bypass_applied=True,
            monkey_patch_applied=False,
            schema_validated=True,
            agent_trace_available=True,
            trace_file_exists=True,
            mode="acceptance",
            findings_non_empty=True,
        )
        assert result == "diagnostic"
        assert reason is not None
        assert "severity_bypass" in reason

    def test_monkey_patch_blocks_acceptance(self) -> None:
        assert EVIDENCE_PERSISTENCE_AVAILABLE
        result, reason = classify_acceptance(
            severity_bypass_applied=False,
            monkey_patch_applied=True,
            schema_validated=True,
            agent_trace_available=True,
            trace_file_exists=True,
            mode="acceptance",
            findings_non_empty=True,
        )
        assert result == "diagnostic"
        assert "monkey_patch" in reason

    def test_missing_trace_blocks_acceptance(self) -> None:
        assert EVIDENCE_PERSISTENCE_AVAILABLE
        result, reason = classify_acceptance(
            severity_bypass_applied=False,
            monkey_patch_applied=False,
            schema_validated=True,
            agent_trace_available=True,
            trace_file_exists=False,
            mode="acceptance",
            findings_non_empty=True,
        )
        assert result == "diagnostic"
        assert "trace" in reason.lower()

    def test_agent_trace_unavailable_blocks_acceptance(self) -> None:
        assert EVIDENCE_PERSISTENCE_AVAILABLE
        result, reason = classify_acceptance(
            severity_bypass_applied=False,
            monkey_patch_applied=False,
            schema_validated=True,
            agent_trace_available=False,
            trace_file_exists=True,
            mode="acceptance",
            findings_non_empty=True,
        )
        assert result == "diagnostic"
        assert "agent_trace_available" in reason

    def test_schema_not_validated_blocks_acceptance(self) -> None:
        assert EVIDENCE_PERSISTENCE_AVAILABLE
        result, reason = classify_acceptance(
            severity_bypass_applied=False,
            monkey_patch_applied=False,
            schema_validated=False,
            agent_trace_available=True,
            trace_file_exists=True,
            mode="acceptance",
            findings_non_empty=True,
        )
        assert result == "diagnostic"
        assert "schema_validated" in reason

    def test_diagnostic_mode_always_diagnostic(self) -> None:
        assert EVIDENCE_PERSISTENCE_AVAILABLE
        result, reason = classify_acceptance(
            severity_bypass_applied=False,
            monkey_patch_applied=False,
            schema_validated=True,
            agent_trace_available=True,
            trace_file_exists=True,
            mode="diagnostic",
            findings_non_empty=True,
        )
        assert result == "diagnostic"
        assert "mode=diagnostic" in reason

    def test_empty_findings_blocks_acceptance(self) -> None:
        assert EVIDENCE_PERSISTENCE_AVAILABLE
        result, reason = classify_acceptance(
            severity_bypass_applied=False,
            monkey_patch_applied=False,
            schema_validated=True,
            agent_trace_available=True,
            trace_file_exists=True,
            mode="acceptance",
            findings_non_empty=False,
        )
        assert result == "diagnostic"
        assert "findings" in reason.lower()

    def test_multiple_reasons_concatenated(self) -> None:
        assert EVIDENCE_PERSISTENCE_AVAILABLE
        result, reason = classify_acceptance(
            severity_bypass_applied=True,
            monkey_patch_applied=True,
            schema_validated=False,
            agent_trace_available=False,
            trace_file_exists=False,
            mode="diagnostic",
            findings_non_empty=False,
        )
        assert result == "diagnostic"
        assert reason is not None
        # Multiple reasons should be present
        parts = reason.split("; ")
        assert len(parts) >= 3

    def test_schema_partial_is_acceptable(self) -> None:
        """'partial' schema validation is still acceptable (not a hard block)."""
        assert EVIDENCE_PERSISTENCE_AVAILABLE
        result, reason = classify_acceptance(
            severity_bypass_applied=False,
            monkey_patch_applied=False,
            schema_validated="partial",
            agent_trace_available=True,
            trace_file_exists=True,
            mode="acceptance",
            findings_non_empty=True,
        )
        # partial is not False, so it does not block acceptance
        assert result == "acceptance"


# ── persist_evidence integration tests ────────────────────────────────────────


class TestPersistEvidence:
    """Integration tests for ``persist_evidence()`` — real file I/O in tmpdir."""

    def test_manifest_generated_with_all_fields(self, tmp_path: Path) -> None:
        assert EVIDENCE_PERSISTENCE_AVAILABLE
        artifact_root = _make_artifact_tree(tmp_path / "artifact_root")
        evidence_dir = tmp_path / "evidence"

        result = persist_evidence(
            artifact_root=artifact_root,
            evidence_dir=evidence_dir,
            run_id="test-run-001",
            review_type="CER",
            mode="acceptance",
            command_used="python scripts/cer_review_runner.py --mode production-smoke",
            severity_bypass_applied=False,
            monkey_patch_applied=False,
            schema_validated=True,
            agent_trace_available=True,
            llm_provider_available=True,
            workflow_id="cer_review_v2",
            project_id="PRJ-TEST-001",
            dry_run=False,
            overwrite=False,
        )

        # Manifest file should exist
        manifest_path = evidence_dir / "test-run-001" / "evidence_manifest.json"
        assert manifest_path.exists()

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert manifest["run_id"] == "test-run-001"
        assert manifest["workflow_id"] == "cer_review_v2"
        assert manifest["review_type"] == "CER"
        assert manifest["mode"] == "acceptance"
        assert manifest["acceptance_type"] == "acceptance"
        assert manifest["severity_bypass_applied"] is False
        assert manifest["monkey_patch_applied"] is False
        assert manifest["llm_provider_available"] is True
        assert manifest["schema_validated"] is True
        assert manifest["agent_trace_available"] is True
        assert manifest["evidence_created_at"] is not None
        assert manifest["command_used"] is not None
        assert manifest["artifact_root_source"] == str(artifact_root.resolve())
        assert manifest["evidence_root"] == str((evidence_dir / "test-run-001").resolve())
        assert "copied_files" in manifest
        assert "missing_files" in manifest

    def test_missing_optional_files_do_not_fail(self, tmp_path: Path) -> None:
        assert EVIDENCE_PERSISTENCE_AVAILABLE
        artifact_root = _make_artifact_tree(tmp_path / "artifact_root", include_summary=False)
        # Remove optional files
        (artifact_root / "00_manifest" / "agent_usage_ledger.json").unlink()
        (artifact_root / "00_manifest" / "event_log.json").unlink()

        evidence_dir = tmp_path / "evidence"

        result = persist_evidence(
            artifact_root=artifact_root,
            evidence_dir=evidence_dir,
            run_id="test-run-002",
            review_type="RMF",
            mode="smoke",
            command_used="python scripts/rmf_review_runner.py",
            severity_bypass_applied=False,
            monkey_patch_applied=False,
            schema_validated=True,
            agent_trace_available=True,
            llm_provider_available=True,
            workflow_id="rmf_review_v1",
            project_id="PRJ-TEST-002",
            dry_run=False,
            overwrite=False,
        )

        manifest_path = evidence_dir / "test-run-002" / "evidence_manifest.json"
        assert manifest_path.exists()
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        # Optional files should be in missing_files, not cause failure
        assert len(manifest["missing_files"]) > 0

    def test_required_trace_missing_blocks_acceptance(self, tmp_path: Path) -> None:
        assert EVIDENCE_PERSISTENCE_AVAILABLE
        artifact_root = _make_artifact_tree(tmp_path / "artifact_root", include_trace=False)
        evidence_dir = tmp_path / "evidence"

        result = persist_evidence(
            artifact_root=artifact_root,
            evidence_dir=evidence_dir,
            run_id="test-run-003",
            review_type="CER",
            mode="acceptance",
            command_used="python scripts/cer_review_runner.py",
            severity_bypass_applied=False,
            monkey_patch_applied=False,
            schema_validated=True,
            agent_trace_available=True,
            llm_provider_available=True,
            workflow_id="cer_review_v2",
            project_id="PRJ-TEST-003",
            dry_run=False,
            overwrite=False,
        )

        manifest_path = evidence_dir / "test-run-003" / "evidence_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        # Missing trace → trace_file_exists=False → not acceptance
        assert manifest["acceptance_type"] == "diagnostic"
        assert manifest["not_acceptable_for_full_pass_reason"] is not None
        assert "trace" in manifest["not_acceptable_for_full_pass_reason"].lower()

    def test_severity_bypass_run_is_diagnostic(self, tmp_path: Path) -> None:
        assert EVIDENCE_PERSISTENCE_AVAILABLE
        artifact_root = _make_artifact_tree(tmp_path / "artifact_root")
        evidence_dir = tmp_path / "evidence"

        result = persist_evidence(
            artifact_root=artifact_root,
            evidence_dir=evidence_dir,
            run_id="test-run-004",
            review_type="CER",
            mode="acceptance",
            command_used="python scripts/cer_review_runner.py --no-severity-scan",
            severity_bypass_applied=True,
            monkey_patch_applied=False,
            schema_validated=True,
            agent_trace_available=True,
            llm_provider_available=True,
            workflow_id="cer_review_v2",
            project_id="PRJ-TEST-004",
            dry_run=False,
            overwrite=False,
        )

        manifest = json.loads((evidence_dir / "test-run-004" / "evidence_manifest.json").read_text(encoding="utf-8"))
        assert manifest["acceptance_type"] == "diagnostic"
        assert "severity_bypass" in manifest["not_acceptable_for_full_pass_reason"]

    def test_monkey_patch_run_is_diagnostic(self, tmp_path: Path) -> None:
        assert EVIDENCE_PERSISTENCE_AVAILABLE
        artifact_root = _make_artifact_tree(tmp_path / "artifact_root")
        evidence_dir = tmp_path / "evidence"

        result = persist_evidence(
            artifact_root=artifact_root,
            evidence_dir=evidence_dir,
            run_id="test-run-005",
            review_type="RMF",
            mode="acceptance",
            command_used="python scripts/rmf_review_runner.py",
            severity_bypass_applied=False,
            monkey_patch_applied=True,
            schema_validated=True,
            agent_trace_available=True,
            llm_provider_available=True,
            workflow_id="rmf_review_v1",
            project_id="PRJ-TEST-005",
            dry_run=False,
            overwrite=False,
        )

        manifest = json.loads((evidence_dir / "test-run-005" / "evidence_manifest.json").read_text(encoding="utf-8"))
        assert manifest["acceptance_type"] == "diagnostic"
        assert "monkey_patch" in manifest["not_acceptable_for_full_pass_reason"]

    def test_overwrite_protection(self, tmp_path: Path) -> None:
        assert EVIDENCE_PERSISTENCE_AVAILABLE
        artifact_root = _make_artifact_tree(tmp_path / "artifact_root")
        evidence_dir = tmp_path / "evidence"

        # First run succeeds
        persist_evidence(
            artifact_root=artifact_root,
            evidence_dir=evidence_dir,
            run_id="test-run-006",
            review_type="CER",
            mode="smoke",
            command_used="cmd1",
            severity_bypass_applied=False,
            monkey_patch_applied=False,
            schema_validated=True,
            agent_trace_available=True,
            llm_provider_available=True,
            workflow_id="w1",
            project_id="p1",
            dry_run=False,
            overwrite=False,
        )

        # Second run without overwrite should raise
        with pytest.raises(FileExistsError, match="already exists"):
            persist_evidence(
                artifact_root=artifact_root,
                evidence_dir=evidence_dir,
                run_id="test-run-006",
                review_type="CER",
                mode="smoke",
                command_used="cmd2",
                severity_bypass_applied=False,
                monkey_patch_applied=False,
                schema_validated=True,
                agent_trace_available=True,
                llm_provider_available=True,
                workflow_id="w1",
                project_id="p1",
                dry_run=False,
                overwrite=False,
            )

    def test_overwrite_allowed_with_flag(self, tmp_path: Path) -> None:
        assert EVIDENCE_PERSISTENCE_AVAILABLE
        artifact_root = _make_artifact_tree(tmp_path / "artifact_root")
        evidence_dir = tmp_path / "evidence"

        # First run
        persist_evidence(
            artifact_root=artifact_root,
            evidence_dir=evidence_dir,
            run_id="test-run-007",
            review_type="CER",
            mode="smoke",
            command_used="cmd1",
            severity_bypass_applied=False,
            monkey_patch_applied=False,
            schema_validated=True,
            agent_trace_available=True,
            llm_provider_available=True,
            workflow_id="w1",
            project_id="p1",
            dry_run=False,
            overwrite=False,
        )

        # Overwrite should succeed
        result = persist_evidence(
            artifact_root=artifact_root,
            evidence_dir=evidence_dir,
            run_id="test-run-007",
            review_type="CER",
            mode="smoke",
            command_used="cmd2-overwritten",
            severity_bypass_applied=False,
            monkey_patch_applied=False,
            schema_validated=True,
            agent_trace_available=True,
            llm_provider_available=True,
            workflow_id="w1",
            project_id="p1",
            dry_run=False,
            overwrite=True,
        )

        manifest = json.loads((evidence_dir / "test-run-007" / "evidence_manifest.json").read_text(encoding="utf-8"))
        assert "cmd2-overwritten" in manifest["command_used"]

    def test_command_log_written(self, tmp_path: Path) -> None:
        assert EVIDENCE_PERSISTENCE_AVAILABLE
        artifact_root = _make_artifact_tree(tmp_path / "artifact_root")
        evidence_dir = tmp_path / "evidence"
        cmd = "PYTHONPATH=. python3 scripts/cer_review_runner.py --mode smoke --profile x.yaml"

        persist_evidence(
            artifact_root=artifact_root,
            evidence_dir=evidence_dir,
            run_id="test-run-008",
            review_type="CER",
            mode="smoke",
            command_used=cmd,
            severity_bypass_applied=False,
            monkey_patch_applied=False,
            schema_validated=True,
            agent_trace_available=True,
            llm_provider_available=True,
            workflow_id="w1",
            project_id="p1",
            dry_run=False,
            overwrite=False,
        )

        cmd_log = evidence_dir / "test-run-008" / "command_log.txt"
        assert cmd_log.exists()
        content = cmd_log.read_text(encoding="utf-8")
        assert cmd in content

    def test_cer_artifact_root_works(self, tmp_path: Path) -> None:
        assert EVIDENCE_PERSISTENCE_AVAILABLE
        artifact_root = _make_artifact_tree(tmp_path / "cer_artifacts")
        evidence_dir = tmp_path / "evidence"

        result = persist_evidence(
            artifact_root=artifact_root,
            evidence_dir=evidence_dir,
            run_id="cer-run-001",
            review_type="CER",
            mode="smoke",
            command_used="cmd",
            severity_bypass_applied=False,
            monkey_patch_applied=False,
            schema_validated=True,
            agent_trace_available=True,
            llm_provider_available=True,
            workflow_id="cer_review_v2",
            project_id="prj",
            dry_run=False,
            overwrite=False,
        )

        trace_dest = evidence_dir / "cer-run-001" / "agent_invocation_trace.jsonl"
        assert trace_dest.exists()
        manifest = json.loads((evidence_dir / "cer-run-001" / "evidence_manifest.json").read_text(encoding="utf-8"))
        assert manifest["review_type"] == "CER"

    def test_rmf_artifact_root_works(self, tmp_path: Path) -> None:
        assert EVIDENCE_PERSISTENCE_AVAILABLE
        artifact_root = _make_artifact_tree(tmp_path / "rmf_artifacts")
        evidence_dir = tmp_path / "evidence"

        result = persist_evidence(
            artifact_root=artifact_root,
            evidence_dir=evidence_dir,
            run_id="rmf-run-001",
            review_type="RMF",
            mode="smoke",
            command_used="cmd",
            severity_bypass_applied=False,
            monkey_patch_applied=False,
            schema_validated=True,
            agent_trace_available=True,
            llm_provider_available=True,
            workflow_id="rmf_review_v1",
            project_id="prj",
            dry_run=False,
            overwrite=False,
        )

        trace_dest = evidence_dir / "rmf-run-001" / "agent_invocation_trace.jsonl"
        assert trace_dest.exists()
        manifest = json.loads((evidence_dir / "rmf-run-001" / "evidence_manifest.json").read_text(encoding="utf-8"))
        assert manifest["review_type"] == "RMF"

    def test_dry_run_does_not_write_files(self, tmp_path: Path) -> None:
        assert EVIDENCE_PERSISTENCE_AVAILABLE
        artifact_root = _make_artifact_tree(tmp_path / "artifact_root")
        evidence_dir = tmp_path / "evidence"

        result = persist_evidence(
            artifact_root=artifact_root,
            evidence_dir=evidence_dir,
            run_id="dry-run-001",
            review_type="CER",
            mode="smoke",
            command_used="cmd",
            severity_bypass_applied=False,
            monkey_patch_applied=False,
            schema_validated=True,
            agent_trace_available=True,
            llm_provider_available=True,
            workflow_id="w1",
            project_id="p1",
            dry_run=True,
            overwrite=False,
        )

        # No files should be written in dry-run mode
        run_dir = evidence_dir / "dry-run-001"
        assert not run_dir.exists()
        # Result should contain what WOULD be done
        assert "would_copy" in result or "dry_run" in result

    def test_source_artifact_index_generated(self, tmp_path: Path) -> None:
        assert EVIDENCE_PERSISTENCE_AVAILABLE
        artifact_root = _make_artifact_tree(tmp_path / "artifact_root")
        evidence_dir = tmp_path / "evidence"

        persist_evidence(
            artifact_root=artifact_root,
            evidence_dir=evidence_dir,
            run_id="test-run-010",
            review_type="CER",
            mode="smoke",
            command_used="cmd",
            severity_bypass_applied=False,
            monkey_patch_applied=False,
            schema_validated=True,
            agent_trace_available=True,
            llm_provider_available=True,
            workflow_id="w1",
            project_id="p1",
            dry_run=False,
            overwrite=False,
        )

        index_path = evidence_dir / "test-run-010" / "source_artifact_index.json"
        assert index_path.exists()
        index = json.loads(index_path.read_text(encoding="utf-8"))
        assert "files" in index
        assert len(index["files"]) > 0

    def test_evidence_manifest_paths_are_absolute(self, tmp_path: Path) -> None:
        assert EVIDENCE_PERSISTENCE_AVAILABLE
        artifact_root = _make_artifact_tree(tmp_path / "artifact_root")
        evidence_dir = tmp_path / "evidence"

        persist_evidence(
            artifact_root=artifact_root,
            evidence_dir=evidence_dir,
            run_id="test-run-011",
            review_type="CER",
            mode="smoke",
            command_used="cmd",
            severity_bypass_applied=False,
            monkey_patch_applied=False,
            schema_validated=True,
            agent_trace_available=True,
            llm_provider_available=True,
            workflow_id="w1",
            project_id="p1",
            dry_run=False,
            overwrite=False,
        )

        manifest = json.loads((evidence_dir / "test-run-011" / "evidence_manifest.json").read_text(encoding="utf-8"))
        # Paths should be absolute (resolved)
        assert Path(manifest["artifact_root_source"]).is_absolute()
        assert Path(manifest["evidence_root"]).is_absolute()

    def test_schema_validation_missing_tolerated(self, tmp_path: Path) -> None:
        assert EVIDENCE_PERSISTENCE_AVAILABLE
        artifact_root = _make_artifact_tree(tmp_path / "artifact_root")
        (artifact_root / "00_manifest" / "schema_validation_summary.json").unlink()
        evidence_dir = tmp_path / "evidence"

        result = persist_evidence(
            artifact_root=artifact_root,
            evidence_dir=evidence_dir,
            run_id="test-run-012",
            review_type="CER",
            mode="smoke",
            command_used="cmd",
            severity_bypass_applied=False,
            monkey_patch_applied=False,
            schema_validated="partial",
            agent_trace_available=True,
            llm_provider_available=True,
            workflow_id="w1",
            project_id="p1",
            dry_run=False,
            overwrite=False,
        )

        manifest = json.loads((evidence_dir / "test-run-012" / "evidence_manifest.json").read_text(encoding="utf-8"))
        assert manifest["schema_validated"] == "partial"
        assert "00_manifest/schema_validation_summary.json" in manifest["missing_files"]
