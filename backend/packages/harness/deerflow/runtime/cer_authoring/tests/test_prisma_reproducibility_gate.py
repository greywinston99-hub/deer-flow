"""WS4: PRISMA Reproducibility Gate Tests."""

from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from deerflow.runtime.cer_authoring.prisma_reproducibility import build_prisma_reproducibility_audit


class TestPRISMAReproducibility:
    def test_empty_data_fails(self):
        audit = build_prisma_reproducibility_audit()
        assert audit["status"] == "FAIL"
        assert audit["submission_grade_sota_blocked"] is True

    def test_complete_prisma_passes(self):
        prisma = {
            "raw_hits": 200, "dedup_input": 200, "duplicate_count": 30,
            "after_dedup": 170, "title_abstract_screened": 170,
            "title_abstract_excluded": 130, "fulltext_assessed": 40,
            "fulltext_excluded": 15, "final_included": 25,
        }
        search_runs = [{"database": "PubMed", "search_date": "2026-01-15", "exact_query": "PFO AND bubble study"}]
        screening = [
            {"pmid": "123", "status": "excluded", "exclusion_reason": "Wrong population", "exclusion_criteria_id": "EC01"},
        ]
        audit = build_prisma_reproducibility_audit(prisma, search_runs, screening)
        assert audit["status"] == "PASS"

    def test_missing_search_date_fails(self):
        search_runs = [{"database": "PubMed", "exact_query": "test"}]
        audit = build_prisma_reproducibility_audit({}, search_runs, [])
        assert audit["status"] == "FAIL"

    def test_missing_exact_query_fails(self):
        search_runs = [{"database": "PubMed", "search_date": "2026-01-15"}]
        audit = build_prisma_reproducibility_audit({}, search_runs, [])
        assert audit["status"] == "FAIL"

    def test_count_reconciliation_ok(self):
        prisma = {
            "raw_hits": 100, "dedup_input": 100, "duplicate_count": 20,
            "after_dedup": 80, "title_abstract_screened": 80,
            "title_abstract_excluded": 50, "fulltext_assessed": 30,
            "fulltext_excluded": 10, "final_included": 20,
        }
        audit = build_prisma_reproducibility_audit(prisma, [], [])
        assert audit["count_reconciliation_ok"] is True

    def test_count_mismatch_detected(self):
        prisma = {"raw_hits": 100, "dedup_input": 100, "duplicate_count": 20, "after_dedup": 70}
        audit = build_prisma_reproducibility_audit(prisma, [], [])
        assert not audit["count_reconciliation_ok"]

    def test_dedup_before_screening(self):
        prisma = {
            "raw_hits": 100, "dedup_input": 100, "duplicate_count": 20,
            "after_dedup": 80, "title_abstract_screened": 80,
        }
        audit = build_prisma_reproducibility_audit(prisma, [], [])
        assert audit["dedup_before_screening"] is True

    def test_zero_raw_hits_fails(self):
        prisma = {"raw_hits": 0}
        audit = build_prisma_reproducibility_audit(prisma, [], [])
        assert audit["status"] == "FAIL"

    def test_blocked_when_submission_grade_sota_blocked(self):
        prisma = {"raw_hits": 0}
        audit = build_prisma_reproducibility_audit(prisma, [], [])
        assert audit["submission_grade_sota_blocked"] is True
