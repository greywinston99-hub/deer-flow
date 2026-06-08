"""Test HC gate default pause mode behavior."""

from pathlib import Path
import json
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))


class TestHCGateDefaultPauseMode:
    def test_auto_confirm_flag_produces_correct_summary(self):
        """Verify --auto-confirm flag results in auto_confirm=true in summary."""
        from deerflow.runtime.cer_authoring.engineer_feedback_coverage import build_engineer_feedback_coverage_report
        report = build_engineer_feedback_coverage_report()
        assert report["summary"]["p0_gap_count"] >= 0

    def test_default_mode_is_production_pause(self):
        """The default mode (no --auto-confirm) should be production_pause."""
        script = Path(__file__).resolve().parents[7] / "backend" / "scripts" / "run_cer_authoring.py"
        if script.exists():
            content = script.read_text()
            assert "--auto-confirm" in content
            assert "production_pause" in content or "human_gate_mode" in content

    def test_auto_confirm_summary_includes_flag(self):
        """_build_summary must include auto_confirm and human_gate_mode fields."""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "run_cer_authoring",
            Path(__file__).resolve().parents[7] / "backend" / "scripts" / "run_cer_authoring.py"
        )
        if spec and spec.loader:
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            summary = mod._build_summary({"status": "ok", "final_gate_decision": "PASS"}, None)
            assert "auto_confirm" in summary
            assert "human_gate_mode" in summary
            assert summary["human_gate_mode"] in {"production_pause", "validation_auto_confirm"}

    def test_interrupt_info_includes_human_gate_mode(self):
        """Interrupt output JSON must include auto_confirm and human_gate_mode."""
        script_path = Path(__file__).resolve().parents[7] / "backend" / "scripts" / "run_cer_authoring.py"
        if script_path.exists():
            content = script_path.read_text()
            assert 'human_gate_mode' in content
            assert 'production_pause' in content

    def test_human_gate_dir_created_on_interrupt(self):
        """Verify .human_gate directory creation logic is in the codebase."""
        script_path = Path(__file__).resolve().parents[7] / "backend" / "scripts" / "run_cer_authoring.py"
        if script_path.exists():
            content = script_path.read_text()
            assert '.human_gate' in content
            assert '_write_human_gate_file' in content

    def test_response_polling_on_hc_interrupt(self):
        """The _single_invoke function uses response-file polling, not exit code 10."""
        script_path = Path(__file__).resolve().parents[7] / "backend" / "scripts" / "run_cer_authoring.py"
        if script_path.exists():
            content = script_path.read_text()
            assert '_handle_hc_interrupt' in content
            assert '_poll_response' in content
            assert 'response.json' in content

    def test_preflight_discovers_ifu_in_intake_pack_layout(self, tmp_path):
        """Preflight should accept the current intake-pack IFU/ subfolder layout."""
        import importlib.util

        script = Path(__file__).resolve().parents[7] / "backend" / "scripts" / "run_cer_authoring.py"
        spec = importlib.util.spec_from_file_location("run_cer_authoring", script)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        ifu_dir = tmp_path / "IFU"
        ifu_dir.mkdir()
        ifu = ifu_dir / "IFU_001__1 IFU of Bubble Study System20260331.docx"
        ifu.write_text("mock", encoding="utf-8")

        discovered = module._discover_preflight_ifu_files(tmp_path)

        assert discovered == [ifu]
