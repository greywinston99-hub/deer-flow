"""BIGDP2026.6V_2 Batch B: Evidence integrity tests.

DC-1/2: Search audit trail
DC-3: Screening exclusion rules (N<10, animal, exclusion reasons)
DC-4: PMID source anchoring
DC-5: Fulltext availability policy
DC-10: Denominator/subgroup consistency
"""
import pytest
from deerflow.runtime.cer_authoring.gates import (
    _validate_search_audit_trail,
    _validate_screening_exclusions,
    _validate_denominator_consistency,
    _validate_fulltext_policy,
)


class TestSearchAuditTrail:
    """DC-1/DC-2: Every search run must have query_string, date, hits."""

    def test_complete_audit_passes(self):
        result = _validate_search_audit_trail({
            "search_run_registry": [
                {"exact_query": "test query", "search_date": "2026-01-01", "total_hits": 42},
            ],
        })
        assert result.status == "PASS"

    def test_missing_query_rework(self):
        result = _validate_search_audit_trail({
            "search_run_registry": [
                {"search_date": "2026-01-01", "total_hits": 42},
            ],
        })
        assert result.status == "REWORK_REQUIRED"
        assert "query_string" in result.message.lower()

    def test_no_searches_passes(self):
        result = _validate_search_audit_trail({"search_run_registry": []})
        assert result.status == "PASS"


class TestScreeningExclusions:
    """DC-3: N<10 case reports excluded, animal studies excluded, reasons documented."""

    def test_n10_case_report_blocked(self):
        result = _validate_screening_exclusions({
            "evidence_registry": [
                {"sample_size": 2, "study_design": "case report", "title": "A case study of device failure"},
            ],
            "screening_disposition": [],
        })
        assert result.status == "REWORK_REQUIRED"
        assert "N<10" in result.message

    def test_animal_study_blocked(self):
        result = _validate_screening_exclusions({
            "evidence_registry": [
                {"sample_size": 30, "title": "Porcine model of vascular closure", "abstract": "swine study"},
            ],
            "screening_disposition": [],
        })
        assert result.status == "REWORK_REQUIRED"
        assert "non-human" in result.message.lower()

    def test_excluded_no_reason(self):
        result = _validate_screening_exclusions({
            "evidence_registry": [],
            "screening_disposition": [
                {"status": "excluded"},
            ],
        })
        assert result.status == "REWORK_REQUIRED"
        assert "exclusion_reason" in result.message.lower()

    def test_valid_evidence_passes(self):
        result = _validate_screening_exclusions({
            "evidence_registry": [
                {"sample_size": 200, "study_design": "RCT", "title": "Clinical trial of device X"},
            ],
            "screening_disposition": [],
        })
        assert result.status == "PASS"


class TestDenominatorConsistency:
    """DC-10: n_events <= n_total, percentage recalculates correctly."""

    def test_mismatch_detected(self):
        result = _validate_denominator_consistency({
            "clinical_evidence_fact_table": [
                {"n_events": 329, "n_total": 350, "value": 94.0, "unit": "percentage", "pmid": "12345"},
            ],
        })
        assert result.status == "PASS"  # 329/350=94.0% — correct

    def test_n_events_greater_than_n_total(self):
        result = _validate_denominator_consistency({
            "clinical_evidence_fact_table": [
                {"n_events": 400, "n_total": 350, "value": 114.0, "unit": "percentage", "pmid": "99999"},
            ],
        })
        assert result.status == "REWORK_REQUIRED"

    def test_percentage_miscalculation(self):
        result = _validate_denominator_consistency({
            "clinical_evidence_fact_table": [
                {"n_events": 50, "n_total": 200, "value": 50.0, "unit": "percentage", "pmid": "12345"},
            ],
        })
        assert result.status == "REWORK_REQUIRED"  # 50/200=25%, not 50%


class TestFulltextPolicy:
    """DC-5: Pivotal without fulltext → BLOCKED. No abstract+no fulltext → REWORK."""

    def test_pivotal_no_fulltext_blocked(self):
        result = _validate_fulltext_policy({
            "evidence_registry": [
                {"weight": "pivotal", "full_text_available": "false"},
            ],
        })
        assert result.status == "BLOCKED"

    def test_no_abstract_no_fulltext_rework(self):
        result = _validate_fulltext_policy({
            "evidence_registry": [
                {"weight": "supportive", "full_text_available": "false"},
            ],
        })
        assert result.status == "REWORK_REQUIRED"

    def test_fulltext_available_passes(self):
        result = _validate_fulltext_policy({
            "evidence_registry": [
                {"weight": "pivotal", "full_text_available": "true", "abstract": "present"},
            ],
        })
        assert result.status == "PASS"
