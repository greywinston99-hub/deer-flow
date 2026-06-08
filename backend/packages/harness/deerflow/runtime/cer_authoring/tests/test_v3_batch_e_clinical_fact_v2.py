"""BIGDP2026.6V_3 Batch E: Clinical Fact V2 — E0 Eligibility + Statistical Parsers."""
import pytest
from deerflow.runtime.cer_authoring.expert_rule_loader import (
    classify_source_eligibility, classify_evidence_tier, determine_data_use,
    determine_clinical_limitation, parse_hr_rr_or, parse_ci_pvalue,
)


class TestE0EligibilityLayer:
    def test_fulltext_verified(self):
        assert classify_source_eligibility(True, True) == "fulltext_verified"

    def test_abstract_only(self):
        assert classify_source_eligibility(False, True) == "abstract_only"

    def test_secondary_source(self):
        assert classify_source_eligibility(False, True, is_secondary=True) == "secondary_source"

    def test_unavailable(self):
        assert classify_source_eligibility(False, False) == "unavailable"

    def test_evidence_tier_direct(self):
        assert classify_evidence_tier("RCT", "subject_device") == "direct_clinical"

    def test_evidence_tier_equivalent(self):
        assert classify_evidence_tier("Prospective", "equivalent_device") == "equivalent"

    def test_evidence_tier_manufacturer(self):
        assert classify_evidence_tier("bench", "", is_manufacturer=True) == "manufacturer"

    def test_data_use_unavailable_blocks(self):
        uses = determine_data_use("unavailable", "direct_clinical")
        assert "not_allowed" in uses

    def test_data_use_direct_allows_all(self):
        uses = determine_data_use("fulltext_verified", "direct_clinical", n_total=200, has_endpoint_match=True)
        assert "claim_support" in uses
        assert "benchmark" in uses
        assert "BR" in uses

    def test_data_use_abstract_only_background(self):
        uses = determine_data_use("abstract_only", "indirect_clinical")
        assert "background_only" in uses

    def test_limitation_subgroup(self):
        lim = determine_clinical_limitation("fulltext_verified", is_subgroup=True)
        assert lim == "subgroup_only"

    def test_limitation_low_sample(self):
        lim = determine_clinical_limitation("fulltext_verified", n_total=15)
        assert lim == "low_sample_size"


class TestStatisticalParsers:
    def test_parse_hr(self):
        results = parse_hr_rr_or("HR 0.85 (95% CI 0.70-1.05) for mortality")
        assert len(results) >= 1
        assert results[0]["stat_type"] == "HR"
        assert results[0]["value"] == 0.85

    def test_parse_rr(self):
        results = parse_hr_rr_or("RR=1.45 (95% CI 1.10-1.90)")
        assert len(results) >= 1
        assert results[0]["stat_type"] == "RR"

    def test_parse_or(self):
        results = parse_hr_rr_or("OR 2.1 95% CI 1.3-3.4")
        assert len(results) >= 1
        assert results[0]["stat_type"] == "OR"

    def test_parse_pvalue(self):
        results = parse_ci_pvalue("p=0.03 for primary endpoint")
        assert len(results) >= 1
        assert results[0]["value"] == 0.03
        assert results[0]["significant"] is True

    def test_empty_text(self):
        assert parse_hr_rr_or("") == []
        assert parse_ci_pvalue("") == []
