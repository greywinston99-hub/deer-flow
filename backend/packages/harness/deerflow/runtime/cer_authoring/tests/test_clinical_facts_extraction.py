"""P0-1: Clinical facts extraction + PMID binding tests.

Verifies numerical data extraction from evidence abstracts,
exclusion reason documentation, and Humans filter audit.
"""
import pytest


class TestClinicalFactsExtraction:
    """Numerical data points extracted from evidence with PMID binding."""

    def test_pattern_extraction_percentage(self):
        """'94% (329/350)' → extracts percentage with n_events/n_total."""
        from deerflow.runtime.cer_authoring.graph import _extract_patterns_from_findings

        text = "Hemostasis success rate was 94% (329/350) at 3 minutes post-deployment."
        facts = _extract_patterns_from_findings(text, "PMID12345")
        assert len(facts) >= 1
        pct_fact = [f for f in facts if f["unit"] == "percentage"][0]
        assert pct_fact["value"] == 94.0
        assert pct_fact["n_events"] == 329
        assert pct_fact["n_total"] == 350
        assert pct_fact["pmid"] == "PMID12345"

    def test_pattern_extraction_mean_sd(self):
        """'mean 12.5 ± 3.2' → extracts mean with SD."""
        from deerflow.runtime.cer_authoring.graph import _extract_patterns_from_findings

        text = "Mean procedure time was 12.5 ± 3.2 minutes."
        facts = _extract_patterns_from_findings(text, "PMID99999")
        mean_facts = [f for f in facts if f["unit"] == "continuous"]
        assert len(mean_facts) >= 1
        assert mean_facts[0]["value"] == 12.5
        assert mean_facts[0]["sd"] == 3.2

    def test_empty_findings_graceful(self):
        """Empty findings text → empty facts list, no crash."""
        from deerflow.runtime.cer_authoring.graph import _extract_patterns_from_findings

        facts = _extract_patterns_from_findings("", "PMID0")
        assert facts == []

    def test_endpoint_inference(self):
        """Endpoint hint inferred from context around the match."""
        from deerflow.runtime.cer_authoring.graph import _infer_endpoint_from_context

        hint = _infer_endpoint_from_context(
            "Primary endpoint was hemostasis success: 92% achieved within 3 minutes.",
            "92%",
        )
        assert hint == "hemostasis"

    def test_full_node_execution(self):
        """_node_extract_clinical_facts produces fact table from evidence_registry."""
        from deerflow.runtime.cer_authoring.graph import _node_extract_clinical_facts

        state = {
            "evidence_registry": [
                {"pmid": "11111", "findings": "Hemostasis achieved in 94% (329/350). Mean time 2.8 ± 1.1 min."},
                {"pmid": "22222", "findings": "Major AE rate: 1.5% (30/2000)."},
                {"pmid": "33333", "findings": ""},  # Empty findings
            ],
        }
        result = _node_extract_clinical_facts(state)
        facts = result.get("clinical_evidence_fact_table", [])
        stats = result.get("clinical_fact_extraction_stats", {})
        assert len(facts) >= 2  # At least 2 facts from 2 articles with data
        assert stats["articles_scanned"] == 3
        assert stats["articles_without_findings"] == 1
        # Every fact must have PMID
        for fact in facts:
            assert fact.get("pmid"), f"Fact missing PMID: {fact}"


class TestExclusionReasonDocumentation:
    """P0-2: Every excluded article must have a documented reason."""

    def test_auto_classify_case_report(self):
        """Case report → auto-classified as EXCL-01."""
        from deerflow.runtime.cer_authoring.graph import _auto_classify_exclusion

        reason = _auto_classify_exclusion({"title": "A case report of device failure"})
        assert "case report" in reason.lower()

    def test_auto_classify_animal_study(self):
        """Animal study → auto-classified as EXCL-02."""
        from deerflow.runtime.cer_authoring.graph import _auto_classify_exclusion

        reason = _auto_classify_exclusion({"title": "Porcine model of vascular closure", "abstract": "swine study"})
        assert "non-human" in reason.lower()

    def test_auto_classify_review(self):
        """Review article → auto-classified as EXCL-03."""
        from deerflow.runtime.cer_authoring.graph import _auto_classify_exclusion

        reason = _auto_classify_exclusion({"title": "Review", "study_type": "review"})
        assert "review" in reason.lower()

    def test_match_exclusion_criteria(self):
        """Exclusion reason mapped to standard criteria ID."""
        from deerflow.runtime.cer_authoring.graph import _match_exclusion_criteria

        assert _match_exclusion_criteria({"exclusion_reason": "Case report (N<10)"}) == "EXCL-01"
        assert _match_exclusion_criteria({"exclusion_reason": "Non-human study"}) == "EXCL-02"
        assert _match_exclusion_criteria({"exclusion_reason": "Review/guideline"}) == "EXCL-03"


class TestHumansFilter:
    """P0-3: Humans[Mesh] filter audit in sota_search."""

    def test_humans_filter_detection(self):
        """Detects presence/absence of Humans[Mesh] in search queries."""
        query_with = '("vascular closure"[MeSH]) AND Humans[Mesh]'
        query_without = '("vascular closure"[MeSH]) AND ("clinical"[All Fields])'

        assert 'humans[mesh]' in query_with.lower()
        assert 'humans[mh]' not in query_without.lower()
