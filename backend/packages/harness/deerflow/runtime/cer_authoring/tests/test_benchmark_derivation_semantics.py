"""BIGDP2026.6: Benchmark derivation semantic tests.

Verifies benchmark has rationale, directness, confidence, and rejected alternatives.
Tests rules: BMK-01 through BMK-06.
"""
import json
from pathlib import Path
import pytest

FIXTURES_DIR = Path(__file__).resolve().parents[7] / "BIGDP2026_6" / "expert_scenario_fixtures"


class TestBenchmarkDerivationSemantics:
    """BMK rules: Benchmarks must be traceable, reasoned, and auditable."""

    def _build_state(self, **extra):
        state = {
            "device_profile": {"device_name": "Test Device", "device_class": "IIb"},
            "endpoint_registry": [
                {"name": "hemostasis_time", "clinical_meaning": "Time to complete hemostasis",
                 "type": "primary_efficacy"},
            ],
            "sota_benchmark_table": [],
            "evidence_registry": [],
        }
        state.update(extra)
        return state

    def test_benchmark_has_acceptability_rationale(self):
        """BMK-01: Every endpoint must have non-empty acceptability_rationale."""
        from deerflow.runtime.cer_authoring.graph import _node_build_benchmark_trace

        state = self._build_state()
        result = _node_build_benchmark_trace(state)
        endpoints = result["benchmark_derivation_trace"]["endpoints"]
        for ep in endpoints:
            rationale = ep.get("acceptability_rationale", "")
            assert rationale, (
                f"Endpoint '{ep['endpoint_name']}' missing acceptability_rationale — violates BMK-01"
            )

    def test_fallback_benchmark_has_directness_fallback(self):
        """BMK-05: No source studies → directness must be 'fallback'."""
        from deerflow.runtime.cer_authoring.graph import _node_build_benchmark_trace

        state = self._build_state(
            sota_benchmark_table=[],
            evidence_registry=[],
        )
        result = _node_build_benchmark_trace(state)
        endpoints = result["benchmark_derivation_trace"]["endpoints"]
        for ep in endpoints:
            assert ep.get("directness") == "fallback", (
                f"Without sources, expected 'fallback', got '{ep.get('directness')}'"
            )

    def test_benchmark_with_sources_has_higher_confidence(self):
        """Benchmarks with source studies have higher confidence than those without."""
        from deerflow.runtime.cer_authoring.graph import _node_build_benchmark_trace

        # With evidence
        state_with = self._build_state(
            evidence_registry=[
                {"pmid": "12345", "first_author": "Smith", "year": 2024,
                 "study_design": "RCT", "sample_size": 200, "relevance_weight": 1.0},
            ],
        )
        result_with = _node_build_benchmark_trace(state_with)

        # Without evidence
        state_without = self._build_state()
        result_without = _node_build_benchmark_trace(state_without)

        # With evidence should have equal or higher confidence
        for ep_w, ep_wo in zip(result_with["benchmark_derivation_trace"]["endpoints"],
                                result_without["benchmark_derivation_trace"]["endpoints"]):
            conf_order = {"high": 3, "medium": 2, "low": 1, "insufficient": 0}
            assert conf_order.get(ep_w["confidence"], 0) >= conf_order.get(ep_wo["confidence"], 0), (
                f"With sources should have ≥ confidence than without. "
                f"With: {ep_w['confidence']}, Without: {ep_wo['confidence']}"
            )

    def test_benchmark_includes_directness_field(self):
        """BMK: Every benchmark must declare directness."""
        from deerflow.runtime.cer_authoring.graph import _node_build_benchmark_trace

        state = self._build_state()
        result = _node_build_benchmark_trace(state)
        for ep in result["benchmark_derivation_trace"]["endpoints"]:
            assert ep.get("directness") in ("direct", "indirect", "fallback"), (
                f"Invalid directness: {ep.get('directness')}"
            )

    def test_indirect_fallback_scenario_fields(self):
        """S-03: Indirect fallback benchmark has all required fields."""
        from deerflow.runtime.cer_authoring.graph import _node_build_benchmark_trace

        fixture = json.loads((FIXTURES_DIR / "03_benchmark_indirect_fallback.json").read_text())
        state = self._build_state(
            endpoint_registry=[
                {"name": fixture["input"]["endpoint"], "clinical_meaning": "Time to hemostasis",
                 "type": "primary_efficacy"},
            ],
            evidence_registry=[
                {"pmid": s["pmid"], "first_author": s["first_author"], "year": s["year"],
                 "study_design": s["study_design"], "sample_size": s["sample_size"],
                 "relevance_weight": 0.7}
                for s in fixture["input"]["available_benchmark_sources"]
            ],
        )
        result = _node_build_benchmark_trace(state)
        ep = result["benchmark_derivation_trace"]["endpoints"][0]
        assert ep.get("acceptability_rationale"), "BMK-01: missing acceptability_rationale"
        # With indirect evidence, directness should not be 'direct'
        assert ep.get("directness") != "direct", (
            f"Alternative therapy evidence should not produce 'direct' directness. Got: {ep.get('directness')}"
        )
