"""Skill calibration tests for CER Authoring V2."""
import pytest


class TestBRoute01Calibration:
    """B-ROUTE-01: Claim type → evidence source routing."""

    ROUTING_CASES = [
        ({"claim_type": "clinical_benefit"}, "PubMed/CT.gov", "equivalent_device"),
        ({"claim_type": "IFU_warning"}, "RMF/GSPR", "PMS"),
        ({"claim_type": "warning_contraindication"}, "RMF/GSPR", "PMS"),
        ({"claim_type": "safety"}, "clinical+PMS+vigilance", "PubMed/CT.gov"),
        ({"claim_type": "performance"}, "PubMed/CT.gov", "bench_test"),
        ({"claim_type": "technical"}, "bench_test/IFU", "equivalent_device"),
    ]

    @pytest.mark.parametrize("claim,expected_primary,expected_fallback", ROUTING_CASES)
    def test_routing_maps_correctly(self, claim, expected_primary, expected_fallback):
        from deerflow.runtime.cer_authoring.pipeline import _route_evidence_source_for_claim
        result = _route_evidence_source_for_claim(claim["claim_type"])
        assert expected_primary in result["primary"], f"Expected {expected_primary} in primary, got {result['primary']}"
        if expected_fallback:
            assert expected_fallback in str(result.get("fallback", "")), f"Expected {expected_fallback} in fallback"

    def test_ifu_warning_excludes_pubmed(self):
        from deerflow.runtime.cer_authoring.pipeline import _route_evidence_source_for_claim
        result = _route_evidence_source_for_claim("IFU_warning")
        assert "PubMed" in result.get("excluded", [])

    def test_unknown_type_defaults_to_pubmed(self):
        from deerflow.runtime.cer_authoring.pipeline import _route_evidence_source_for_claim
        result = _route_evidence_source_for_claim("nonexistent_type")
        assert "PubMed" in result.get("primary", "")


class TestBScore02Calibration:
    """B-SCORE-02: Score → weight consumption rules."""

    def test_low_score_cannot_support_moderate(self):
        from deerflow.runtime.cer_authoring.gates import _conclusion_rank
        assert _conclusion_rank("CAUTIOUS") < _conclusion_rank("MODERATE")
        assert _conclusion_rank("INSUFFICIENT") < _conclusion_rank("MODERATE")

    def test_oxford_mapping_consistent(self):
        from deerflow.runtime.cer_authoring.gates import OXFORD_CONCLUSION_MAP
        assert OXFORD_CONCLUSION_MAP["1a"] == "STRONG"
        assert OXFORD_CONCLUSION_MAP["2b"] == "MODERATE"
        assert OXFORD_CONCLUSION_MAP["4"] == "CAUTIOUS"
        assert OXFORD_CONCLUSION_MAP["5"] == "INSUFFICIENT"

    def test_high_score_allows_strong(self):
        from deerflow.runtime.cer_authoring.gates import _conclusion_rank
        assert _conclusion_rank("STRONG") > _conclusion_rank("MODERATE")
        assert _conclusion_rank("STRONG") == 3


class TestWLang25Calibration:
    """W-LANG-25: Language style quantified constraints."""

    def test_writer_style_constants_exist(self):
        from deerflow.runtime.cer_authoring.agents import WRITER_QUANTIFIED_STYLE_CONSTRAINTS
        assert "22-32 words" in WRITER_QUANTIFIED_STYLE_CONSTRAINTS
        assert "Passive-to-active" in WRITER_QUANTIFIED_STYLE_CONSTRAINTS
        assert "STRONG -> demonstrate" in WRITER_QUANTIFIED_STYLE_CONSTRAINTS

    def test_gate_g12_oxford_consistency(self):
        from deerflow.runtime.cer_authoring.gates import _gate_conclusion_strength, GateResult
        result = _gate_conclusion_strength({})
        assert isinstance(result, GateResult)

    def test_sota_confidence_wording_map(self):
        from deerflow.runtime.cer_authoring.pipeline import get_sota_confidence_wording
        high = get_sota_confidence_wording("high")
        assert high["verb"] == "demonstrates"
        low = get_sota_confidence_wording("low")
        assert low["verb"] == "suggests"

    def test_gspr_template_exists(self):
        from deerflow.runtime.cer_authoring.agents import WRITER_GSPR_FIVE_PARAGRAPH_TEMPLATE
        assert "Paragraph 1" in WRITER_GSPR_FIVE_PARAGRAPH_TEMPLATE
        assert "GSPR X.X" in WRITER_GSPR_FIVE_PARAGRAPH_TEMPLATE


class TestG42PerTypeThresholds:
    """BL-02/03: G42 per-claim-type sufficiency thresholds."""

    def test_ifu_warning_framework_skips_pubmed(self):
        from deerflow.runtime.cer_authoring.gates import _get_sufficiency_framework
        fw = _get_sufficiency_framework("IFU_warning")
        assert fw.get("skip_pubmed"), "IFU_warning should skip PubMed"

    def test_clinical_benefit_requires_pivotal(self):
        from deerflow.runtime.cer_authoring.gates import _get_sufficiency_framework
        fw = _get_sufficiency_framework("clinical_benefit")
        assert fw.get("min_pivotal", 0) >= 1

    def test_safety_requires_independent_sources(self):
        from deerflow.runtime.cer_authoring.gates import _get_sufficiency_framework
        fw = _get_sufficiency_framework("safety")
        assert fw.get("min_independent_sources", 0) >= 2
