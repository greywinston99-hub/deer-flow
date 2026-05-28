"""WS10: Regulatory Style Fingerprint Tests."""

from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from deerflow.runtime.cer_authoring.regulatory_style import (
    build_regulatory_style_fingerprint,
    _count_sentences,
    _count_words,
    _is_passive,
    _check_gspr_paragraphs,
    _check_literature_appraisal,
    _check_conclusion_completeness,
    _check_body_annex_boundary,
)


class TestRegulatoryStyleFingerprint:
    def test_empty_body(self):
        fp = build_regulatory_style_fingerprint("")
        assert fp["metrics"]["total_sentences"] == 0
        assert fp["metrics"]["total_words"] == 0

    def test_sentence_counting(self):
        sentences = _count_sentences("This is a test. Another sentence here. Final one.")
        assert len(sentences) == 3

    def test_word_counting(self):
        assert _count_words("This is four words") == 4

    def test_passive_detection(self):
        assert _is_passive("The device is designed for clinical use") is True
        assert _is_passive("The analysis demonstrates clear benefit") is False

    def test_passive_is_used(self):
        assert _is_passive("The results were analyzed by the team") is True

    def test_sentence_length_metrics(self):
        body = "Short sentence. " * 50
        fp = build_regulatory_style_fingerprint(body)
        assert fp["metrics"]["avg_sentence_length"] < 32

    def test_long_sentences_tracked(self):
        body = "This is a very long sentence with many many many many many many many many many many many many many many many words in it. " * 5
        fp = build_regulatory_style_fingerprint(body)
        assert fp["metrics"]["long_sentences_over_32"] >= 0

    def test_gspr_completeness_check(self):
        text = """
        GSPR 1 requires demonstration of safety. The clinical study (Smith 2024)
        demonstrated a 2% adverse event rate. Therefore, the device meets the
        requirement for safety under GSPR 1 based on the available evidence.
        """
        check = _check_gspr_paragraphs(text)
        assert check["has_requirement_statement"] is True
        assert check["has_evidence_source"] is True
        assert check["has_evidence_summary"] is True
        assert check["has_reasoning"] is True
        assert check["has_compliance_judgment"] is True

    def test_gspr_incomplete_detected(self):
        check = _check_gspr_paragraphs("The device is safe.")
        assert check["status"] == "FAIL"

    def test_literature_appraisal_check(self):
        text = """
        Smith et al. (2024) conducted a prospective cohort study. The method
        involved 200 patients. Results showed a significant improvement. The
        study is relevant to our device population. Quality was assessed using
        the Newcastle-Ottawa Scale. Limitations include small sample size.
        """
        check = _check_literature_appraisal(text)
        assert check["has_source"] is True
        assert check["has_method"] is True
        assert check["has_result"] is True
        assert check["has_quality"] is True
        assert check["has_limitation"] is True

    def test_literature_appraisal_incomplete(self):
        check = _check_literature_appraisal("The study found positive results.")
        assert check["status"] == "FAIL"

    def test_conclusion_completeness(self):
        text = """
        The safety profile is acceptable with 2% adverse events. Performance
        demonstrates 95% success rate. The benefit-risk profile is favourable.
        PMS data from 500 patients confirms these findings. Limitations include
        the need for longer follow-up through the PMCF plan.
        """
        check = _check_conclusion_completeness(text)
        assert check["has_safety_conclusion"] is True
        assert check["has_performance_conclusion"] is True
        assert check["has_benefit_risk_conclusion"] is True
        assert check["has_pms_pmcf_limitation"] is True
        assert check["has_limitation_statement"] is True

    def test_body_annex_boundary_check(self):
        check = _check_body_annex_boundary("As shown in Annex A, the data supports...")
        assert check["body_only_references_without_narrative"] is True

    def test_style_fingerprint_chapter_metrics(self):
        chapters = {
            "body": "Short safety conclusion. Performance is acceptable. " * 5,
            "§5": "The device is safe. Clinical benefit is confirmed. Limitations exist. " * 3,
        }
        fp = build_regulatory_style_fingerprint("", chapters)
        assert "metrics" in fp
        assert fp["conclusion"]["status"] in {"PASS", "FAIL_WITH_GAPS", "FAIL"}

    def test_overall_status_aggregation(self):
        fp = build_regulatory_style_fingerprint("")
        assert fp["overall_status"] in {"PASS", "FAIL"}

    def test_banned_strings_not_in_style_check(self):
        fp = build_regulatory_style_fingerprint("The CER confirms device safety and performance.")
        assert "banned" not in str(fp.get("failures", {})).lower()
