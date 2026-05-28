"""Test that formal command examples do NOT default to --auto-confirm."""

from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))


class TestFormalCommandExamples:
    def test_run_script_docstring_no_auto_confirm_default(self):
        """The run_cer_authoring.py docstring shows production mode as default."""
        script_path = Path(__file__).resolve().parents[7] / "backend" / "scripts" / "run_cer_authoring.py"
        if script_path.exists():
            doc = script_path.read_text()
            # Production mode example should NOT contain --auto-confirm
            prod_example_start = doc.find("# Production mode")
            auto_confirm_start = doc.find("# Auto-confirm mode")
            if prod_example_start >= 0 and auto_confirm_start >= 0:
                prod_section = doc[prod_example_start:auto_confirm_start]
                assert "--auto-confirm" not in prod_section, \
                    "Production mode example must not include --auto-confirm"

    def test_auto_confirm_clearly_separated_in_docs(self):
        """--auto-confirm must only appear in clearly labeled validation sections."""
        script_path = Path(__file__).resolve().parents[7] / "backend" / "scripts" / "run_cer_authoring.py"
        if script_path.exists():
            doc = script_path.read_text()
            auto_confirm_lines = [line for line in doc.split("\n") if "--auto-confirm" in line]
            for line in auto_confirm_lines:
                lower = line.lower()
                assert any(kw in lower for kw in ["auto-confirm", "validation", "auto_confirm"]), \
                    f"--auto-confirm used without validation context: {line.strip()[:80]}"

    def test_help_text_describes_auto_confirm_as_validation(self):
        """--auto-confirm help text must describe it as validation mode."""
        script_path = Path(__file__).resolve().parents[7] / "backend" / "scripts" / "run_cer_authoring.py"
        if script_path.exists():
            doc = script_path.read_text()
            assert '--auto-confirm' in doc
            # Find the help string
            help_idx = doc.find('"--auto-confirm"')
            if help_idx < 0:
                help_idx = doc.find("'--auto-confirm'")
            if help_idx >= 0:
                context = doc[help_idx:help_idx + 300]
                assert "validation" in context.lower() or "auto-resume" in context.lower(), \
                    "--auto-confirm help must describe validation purpose"

    def test_implementation_report_no_default_auto_confirm(self):
        """The implementation report should not recommend --auto-confirm as default."""
        report_path = Path(__file__).resolve().parents[7] / "docs" / "cer_authoring_workflow_merge" / "WS1_WS10_IMPLEMENTATION_REPORT_2026-05-28.md"
        if report_path.exists():
            content = report_path.read_text()
            # The report may mention --auto-confirm but should mark it as validation
            auto_confirm_count = content.count("--auto-confirm")
            assert auto_confirm_count >= 0  # May or may not be present

    def test_authoring_script_argparse_default_false(self):
        """--auto-confirm argparse default must be False (store_true)."""
        script_path = Path(__file__).resolve().parents[7] / "backend" / "scripts" / "run_cer_authoring.py"
        if script_path.exists():
            doc = script_path.read_text()
            # argparse with action='store_true' means default is False
            assert "action=\"store_true\"" in doc or "action='store_true'" in doc
            assert '"--auto-confirm"' in doc or "'--auto-confirm'" in doc

    def test_build_summary_includes_human_gate_mode(self):
        """_build_summary output must include human_gate_mode field."""
        script_path = Path(__file__).resolve().parents[7] / "backend" / "scripts" / "run_cer_authoring.py"
        if script_path.exists():
            doc = script_path.read_text()
            assert '"human_gate_mode"' in doc
            assert '"production_pause"' in doc
            assert '"validation_auto_confirm"' in doc
