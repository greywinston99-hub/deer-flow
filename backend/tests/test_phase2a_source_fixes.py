"""Targeted tests for Phase 2A — Source generation fixes (template + IFU + domain blocking)."""

from __future__ import annotations

import pytest

from deerflow.runtime.cer_authoring.writer_remediation.domain_templates import (
    get_domain_template_sections,
    block_if_unknown,
    build_ifu_grounded_device_fields,
    get_ifu_field_instruction,
    IFU_FIELD_MAP,
    DOMAIN_TEMPLATE_MAP,
    KNOWN_DOMAINS,
)


class TestDomainTemplateDispatch:
    """Domain-specific template section generation."""

    def test_cardiac_stabilizer_has_domain_template(self):
        sections = get_domain_template_sections("cardiac_tissue_stabilizer")
        assert sections is not None, "Cardiac stabilizer should have domain template"
        assert len(sections) >= 3, f"Expected at least 3 sections, got {len(sections)}"
        # Verify section targets
        targets = {s["row_id"] for s in sections}
        assert "CS-2.1-DEVICE-DESC" in targets
        assert "CS-2.2-INTENDED-PURPOSE" in targets
        assert "CS-3-CLINICAL-BACKGROUND" in targets

    def test_plasma_electrode_has_domain_template(self):
        for domain in ("plasma_surgical_electrode", "orthopedic_rf_plasma_electrode"):
            sections = get_domain_template_sections(domain)
            assert sections is not None, f"{domain} should have domain template"
            targets = {s["row_id"] for s in sections}
            assert "PE-2.1-DEVICE-DESC" in targets

    def test_imaging_software_has_domain_template(self):
        for domain in ("medical_imaging_software", "ai_diagnostic_software"):
            sections = get_domain_template_sections(domain)
            assert sections is not None, f"{domain} should have domain template"
            targets = {s["row_id"] for s in sections}
            assert "IS-2.1-DEVICE-DESC" in targets

    def test_cardiac_template_forbids_urology_terms(self):
        sections = get_domain_template_sections("cardiac_tissue_stabilizer")
        for s in sections:
            if s["row_id"] == "CS-2.1-DEVICE-DESC":
                instr = s["writer_instruction"].lower()
                assert "ureteroscope" in instr or "urology" in instr, "Cardiac template should explicitly forbid urology terms"
                assert "forbidden" in instr, "Should mark cross-domain terms as forbidden"

    def test_plasma_template_forbids_cardiac_terms(self):
        sections = get_domain_template_sections("plasma_surgical_electrode")
        for s in sections:
            if s["row_id"] == "PE-2.1-DEVICE-DESC":
                instr = s["writer_instruction"].lower()
                assert "cardiac ablation" in instr or "padn" in instr, "Plasma template should forbid cardiac ablation terms"

    def test_imaging_template_forbids_physical_device_terms(self):
        sections = get_domain_template_sections("medical_imaging_software")
        for s in sections:
            if s["row_id"] == "IS-2.1-DEVICE-DESC":
                instr = s["writer_instruction"].lower()
                assert "catheter" in instr or "sterility" in instr, "Imaging template should forbid physical device terms"


class TestUnknownDomainBlocking:
    """Unknown domain must block Writer."""

    def test_generic_unknown_is_blocked(self):
        block = block_if_unknown("generic_unknown")
        assert block is not None
        assert block["writer_allowed"] is False

    def test_empty_domain_is_blocked(self):
        for domain in ("", "unknown", None):
            block = block_if_unknown(domain)
            if domain is None:
                assert block is not None  # None → treated as unknown
            else:
                assert block is not None, f"'{domain}' should be blocked"

    def test_known_domain_not_blocked(self):
        for domain in ("cardiac_tissue_stabilizer", "plasma_surgical_electrode",
                        "medical_imaging_software", "urology_uas"):
            block = block_if_unknown(domain)
            assert block is None, f"'{domain}' should NOT be blocked"


class TestIFUFieldMapping:
    """IFU field-to-section mapping and instruction generation."""

    def test_all_ifu_fields_have_instructions(self):
        for field in ("composition", "working_principle", "performance_summary",
                       "sterility", "model_specifications", "contraindications",
                       "intended_purpose", "target_population"):
            mapping = IFU_FIELD_MAP.get(field)
            assert mapping is not None, f"Field '{field}' should have IFU mapping"
            assert "cer_section" in mapping
            assert "missing_fallback" in mapping

    def test_ifu_text_generates_grounded_instruction(self):
        instr = get_ifu_field_instruction(
            "composition",
            source_text="Titanium alloy and medical-grade silicone components.",
            source_anchor="IFU-001 Section 2.1",
            confidence="high",
        )
        assert "Titanium alloy" in instr
        assert "IFU-001" in instr
        assert "Not extracted from IFU" not in instr

    def test_missing_ifu_text_generates_data_gap_instruction(self):
        instr = get_ifu_field_instruction("composition")
        assert "IFU source does not contain" in instr
        # The instruction warns the Writer NOT to use the placeholder text
        assert "Do NOT write" in instr

    def test_build_ifu_grounded_fields_populates_with_profile_data(self):
        dp = {
            "composition": "Titanium components",
            "working_principle": "RF energy delivery",
            "sterility": "EO sterilized",
        }
        fields = build_ifu_grounded_device_fields(dp, None)
        assert fields["composition"]["text"] == "Titanium components"
        assert fields["composition"]["confidence"] != "data_gap"

    def test_build_ifu_grounded_fields_marks_gaps(self):
        dp = {"device_name": "Test"}
        fields = build_ifu_grounded_device_fields(dp, None)
        # All fields should be marked as data_gap if not in profile
        for field_name in ("composition", "working_principle", "sterility"):
            assert fields[field_name]["data_gap"] is True
            assert fields[field_name]["confidence"] == "data_gap"
