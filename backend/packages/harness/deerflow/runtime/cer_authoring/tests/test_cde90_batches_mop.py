"""CDE90 Batches M/O/P/Q tests — Denominator resolver + Gold evaluator + Score caps."""
import pytest
from deerflow.runtime.cer_authoring.expert_rule_loader import (
    resolve_denominator_context, DENOMINATOR_TYPES,
    validate_gold_fact_match, compute_validation_metrics, compute_stage5_score_cap,
    STAGE5_SCORE_CAPS,
)


class TestBatchMDenominatorResolver:
    def test_all_denominator_types_defined(self):
        assert len(DENOMINATOR_TYPES) == 11

    def test_subgroup_not_total(self):
        r = resolve_denominator_context({"n_total": 216, "n_events": 80, "value": 37.0, "unit": "percentage",
                                          "population_label": "CMF subgroup", "endpoint": "response_rate"})
        assert r["denominator_type"] == "subgroup_n"

    def test_mckee_style_mismatch(self):
        r = resolve_denominator_context({"n_total": 216, "n_events": 70, "value": 87.5, "unit": "percentage",
                                          "population_label": "CMF subgroup all patients", "endpoint": "response_rate"})
        assert not r["is_valid"] or len(r["denominator_issues"]) > 0

    def test_percentage_recalculation(self):
        r = resolve_denominator_context({"n_total": 350, "n_events": 329, "value": 94.0, "unit": "percentage",
                                          "population_label": "ITT", "endpoint": "hemostasis"})
        assert r["recalculated_percentage"] == 94.0

    def test_percentage_mismatch_detected(self):
        r = resolve_denominator_context({"n_total": 200, "n_events": 50, "value": 50.0, "unit": "percentage",
                                          "population_label": "ITT", "endpoint": "success"})
        assert not r["is_valid"]


class TestBatchQGoldEvaluator:
    def test_gold_fact_match_full(self):
        predicted = {"pmid": "12345", "endpoint": "hemostasis", "value": 94.0, "n_events": 329, "n_total": 350,
                     "endpoint_category": "efficacy", "unit": "percentage"}
        gold = {"pmid": "12345", "endpoint": "hemostasis", "value": 94.0, "n_events": 329, "n_total": 350,
                "endpoint_category": "efficacy", "unit": "percentage"}
        r = validate_gold_fact_match(predicted, gold)
        assert r["is_match"]

    def test_no_key_match(self):
        predicted = {"pmid": "12345", "endpoint": "hemostasis"}
        gold = {"pmid": "99999", "endpoint": "hemostasis"}
        r = validate_gold_fact_match(predicted, gold)
        assert not r["is_match"]

    def test_metrics_computation(self):
        results = [
            {"is_match": True, "predicted_has_fact": True},
            {"is_match": True, "predicted_has_fact": True},
            {"is_match": False, "predicted_has_fact": True},
            {"is_match": False, "predicted_has_fact": False},
        ]
        m = compute_validation_metrics(results)
        assert m["precision"] == 0.667
        assert m["recall"] == 0.667

    def test_score_cap_no_gold(self):
        cap = compute_stage5_score_cap({"precision": 0.9, "recall": 0.85, "negative_blocking_accuracy": 0.95, "not_allowed_leakage": 0}, has_gold=False)
        assert cap == 86

    def test_score_cap_low_precision(self):
        cap = compute_stage5_score_cap({"precision": 0.7, "recall": 0.85}, has_gold=True, has_real_project=True)
        assert cap == 85

    def test_stage5_caps_defined(self):
        assert len(STAGE5_SCORE_CAPS) >= 10
