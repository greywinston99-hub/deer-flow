"""Test intelligent spiral convergence detection (_should_continue_spiral).

Regression coverage for infinite spiral loop fix.
"""

import pytest

from deerflow.runtime.cer_authoring.graph import _should_continue_spiral


class TestShouldContinueSpiral:
    """Verify spiral convergence logic."""

    def test_first_round_always_continues(self):
        """Round 1 should always get at least one retry."""
        state = {"evidence_spiral_lineage": [], "spiral_round_id": 1}
        assert _should_continue_spiral(state) is True

    def test_max_rounds_hard_ceiling(self):
        """Never exceed max_rounds regardless of growth."""
        state = {
            "evidence_spiral_lineage": [
                {"spiral_round_id": 1, "records_total": 100, "query_delta": "A"},
                {"spiral_round_id": 2, "records_total": 150, "query_delta": "B"},
                {"spiral_round_id": 3, "records_total": 200, "query_delta": "C"},
            ],
            "spiral_round_id": 3,
        }
        assert _should_continue_spiral(state, max_rounds=3) is False

    def test_low_growth_stops_spiral(self):
        """If record growth < 15%, evidence pool is saturated."""
        state = {
            "evidence_spiral_lineage": [
                {"spiral_round_id": 1, "records_total": 100, "query_delta": "A"},
                {"spiral_round_id": 2, "records_total": 105, "query_delta": "B"},
            ],
            "spiral_round_id": 2,
        }
        assert _should_continue_spiral(state) is False

    def test_high_growth_continues(self):
        """If record growth >= 15%, keep searching."""
        state = {
            "evidence_spiral_lineage": [
                {"spiral_round_id": 1, "records_total": 100, "query_delta": "A"},
                {"spiral_round_id": 2, "records_total": 130, "query_delta": "B"},
            ],
            "spiral_round_id": 2,
        }
        assert _should_continue_spiral(state) is True

    def test_identical_query_delta_stops(self):
        """Same query as last round = no new territory explored."""
        state = {
            "evidence_spiral_lineage": [
                {"spiral_round_id": 1, "records_total": 100, "query_delta": "same"},
                {"spiral_round_id": 2, "records_total": 150, "query_delta": "same"},
            ],
            "spiral_round_id": 2,
        }
        assert _should_continue_spiral(state) is False

    def test_non_pool_failure_stops(self):
        """If failure is NOT about insufficient pool, more searches won't help."""
        state = {
            "evidence_spiral_lineage": [
                {"spiral_round_id": 1, "records_total": 100, "query_delta": "A"},
            ],
            "spiral_round_id": 1,
        }
        assert _should_continue_spiral(state, failure_pattern="endpoint_quality_issue") is False

    def test_pool_failure_continues(self):
        """If failure IS about insufficient pool, more searches may help."""
        state = {
            "evidence_spiral_lineage": [
                {"spiral_round_id": 1, "records_total": 100, "query_delta": "A"},
            ],
            "spiral_round_id": 1,
        }
        assert _should_continue_spiral(state, failure_pattern="no_benchmark_derivable_from_pool") is True

    def test_second_round_with_strong_growth(self):
        """Round 2 with strong growth should continue."""
        state = {
            "evidence_spiral_lineage": [
                {"spiral_round_id": 1, "records_total": 50, "query_delta": "plasma electrode"},
                {"spiral_round_id": 2, "records_total": 80, "query_delta": "plasma electrode arthroscopy"},
            ],
            "spiral_round_id": 2,
        }
        assert _should_continue_spiral(state) is True

    def test_zero_records_before_continues(self):
        """If prior round had 0 records, growth calculation should not crash."""
        state = {
            "evidence_spiral_lineage": [
                {"spiral_round_id": 1, "records_total": 0, "query_delta": "A"},
                {"spiral_round_id": 2, "records_total": 10, "query_delta": "B"},
            ],
            "spiral_round_id": 2,
        }
        assert _should_continue_spiral(state) is True
