"""BIGDP2026.6 Phase 2: Expert Business Logic Ledger tests.

Tests CER_REASONING_LEDGER, IFU_CLAIM_EVOLUTION_LEDGER, and
BENCHMARK_DERIVATION_TRACE nodes.
"""
import json
import pytest
from pathlib import Path


SCHEMAS_DIR = Path(__file__).resolve().parents[7] / "schemas"


def _make_state(**extra):
    """Minimal valid state for ledger node testing."""
    base = {
        "device_profile": {
            "device_name": "Test Device",
            "device_class": "IIb",
            "intended_use": "For hemostasis in surgical procedures",
            "mechanism_of_action": "Mechanical compression",
            "target_population": "Adult surgical patients",
            "anatomical_site": "Peripheral vasculature",
            "manufacturer": "Test Manufacturer",
        },
        "claim_ledger": [
            {"claim_id": "C-01", "claim_text": "Achieves hemostasis within 3 minutes", "claim_type": "clinical_performance", "criticality": "high"},
            {"claim_id": "C-02", "claim_text": "Safe for single use", "claim_type": "clinical_safety", "criticality": "high"},
            {"claim_id": "C-03", "claim_text": "Ergonomic handle design", "claim_type": "usability", "criticality": "low"},
        ],
        "claim_evidence_matrix": [
            {"claim_id": "C-01", "evidence_ids": ["E-001", "E-002"], "support_type": "direct", "conclusion_strength": "strong"},
            {"claim_id": "C-02", "evidence_ids": ["E-003"], "support_type": "direct", "conclusion_strength": "moderate"},
            {"claim_id": "C-03", "evidence_ids": [], "support_type": "insufficient", "conclusion_strength": "limited"},
        ],
        "endpoint_registry": [
            {"name": "hemostasis_time", "type": "primary_efficacy", "clinical_meaning": "Time to achieve complete hemostasis"},
            {"name": "adverse_events", "type": "primary_safety", "clinical_meaning": "Device-related adverse event rate"},
        ],
        "sota_benchmark_table": [
            {"benchmark_id": "B-001", "endpoint": "hemostasis_time", "directness": "direct"},
            {"benchmark_id": "B-002", "endpoint": "adverse_events", "directness": "indirect"},
        ],
        "benefit_risk_ledger": [],
        "evidence_registry": [
            {"pmid": "12345", "first_author": "Smith", "year": 2024, "study_design": "RCT", "sample_size": 200, "relevance_weight": 1.0},
            {"pmid": "12346", "first_author": "Jones", "year": 2023, "study_design": "Prospective", "sample_size": 150, "relevance_weight": 0.8},
            {"pmid": "12347", "first_author": "Lee", "year": 2024, "study_design": "RCT", "sample_size": 300, "relevance_weight": 0.9},
        ],
        "ifu_working_document": {"filename": "IFU_TestDevice_v2.pdf", "version": "2.0", "date": "2025-06", "language": "en"},
        "equivalence_claimed": False,
        "equivalent_device_name": "",
    }
    base.update(extra)
    return base


class TestCERReasoningLedger:
    """Section C: CER_REASONING_LEDGER schema and node tests."""

    def test_schema_exists_and_validates(self):
        """C.1: Schema file exists and is valid JSON Schema."""
        schema_path = SCHEMAS_DIR / "cer_reasoning_ledger.schema.json"
        assert schema_path.exists(), f"Schema not found at {schema_path}"
        schema = json.loads(schema_path.read_text())
        assert "$schema" in schema
        assert schema.get("title") == "CER Reasoning Ledger"

    def test_schema_required_fields(self):
        """C.2: Schema includes all required fields."""
        schema_path = SCHEMAS_DIR / "cer_reasoning_ledger.schema.json"
        schema = json.loads(schema_path.read_text())
        required = schema.get("required", [])
        for field in ["schema_version", "generated_at", "product_identity_reasoning", "claims"]:
            assert field in required, f"Missing required field: {field}"

        claim_props = schema["properties"]["claims"]["items"]["properties"]
        for field in ["claim_classification", "claim_criticality", "evidence_support_type", "conclusion_strength"]:
            assert field in claim_props, f"Missing claim property: {field}"

    def test_node_produces_valid_ledger(self):
        """C.3-C.5: Node executes and produces populated ledger."""
        from deerflow.runtime.cer_authoring.graph import _node_build_reasoning_ledger

        state = _make_state()
        result = _node_build_reasoning_ledger(state)
        ledger = result.get("cer_reasoning_ledger", {})
        assert ledger, "CER_REASONING_LEDGER is empty"
        assert ledger.get("schema_version") == "1.0.0"
        claims = ledger.get("claims", [])
        assert len(claims) == 3, f"Expected 3 claims, got {len(claims)}"
        # C.6: Every claim has a non-null conclusion_strength
        for c in claims:
            assert c.get("conclusion_strength"), f"Claim {c.get('claim_id')} has no conclusion_strength"

    def test_claim_with_evidence_gets_strong(self):
        """Claim with 2+ evidence IDs → strong conclusion."""
        from deerflow.runtime.cer_authoring.graph import _node_build_reasoning_ledger

        state = _make_state()
        result = _node_build_reasoning_ledger(state)
        claims = {c["claim_id"]: c for c in result["cer_reasoning_ledger"]["claims"]}
        assert claims["C-01"]["conclusion_strength"] == "strong"
        assert claims["C-01"]["evidence_support_type"] == "direct"

    def test_claim_without_evidence_gets_limited(self):
        """Claim with no evidence → limited conclusion, PMCF gap."""
        from deerflow.runtime.cer_authoring.graph import _node_build_reasoning_ledger

        state = _make_state()
        result = _node_build_reasoning_ledger(state)
        claims = {c["claim_id"]: c for c in result["cer_reasoning_ledger"]["claims"]}
        assert claims["C-03"]["conclusion_strength"] == "limited"
        assert claims["C-03"]["gap_disposition"] == "PMCF"


class TestIFUClaimEvolutionLedger:
    """Section D: IFU_CLAIM_EVOLUTION_LEDGER schema and node tests."""

    def test_schema_exists_and_validates(self):
        """D.1: Schema file exists."""
        schema_path = SCHEMAS_DIR / "ifu_claim_evolution_ledger.schema.json"
        assert schema_path.exists()
        schema = json.loads(schema_path.read_text())
        assert schema.get("title") == "IFU Claim Evolution Ledger"

    def test_five_stage_evolution_structure(self):
        """D.2: Schema tracks 5 stages per claim."""
        schema_path = SCHEMAS_DIR / "ifu_claim_evolution_ledger.schema.json"
        schema = json.loads(schema_path.read_text())
        stages = schema["properties"]["claims"]["items"]["properties"]["evolution_stages"]["properties"]
        for stage in ["stage_1_ifu_text", "stage_2_extracted_claim", "stage_3_classified_claim",
                       "stage_4_evidence_supported_claim", "stage_5_final_cer_claim"]:
            assert stage in stages, f"Missing stage: {stage}"

    def test_node_produces_valid_ledger(self):
        """D.3-D.5: Node produces ledger with 5-stage evolution."""
        from deerflow.runtime.cer_authoring.graph import _node_build_ifu_evolution_ledger

        state = _make_state()
        result = _node_build_ifu_evolution_ledger(state)
        ledger = result.get("ifu_claim_evolution_ledger", {})
        assert ledger, "IFU_CLAIM_EVOLUTION_LEDGER is empty"
        claims = ledger.get("claims", [])
        assert len(claims) == 3

    def test_marketing_language_detection(self):
        """D.6: Marketing-language claims are flagged."""
        from deerflow.runtime.cer_authoring.graph import _node_build_ifu_evolution_ledger

        state = _make_state(
            claim_ledger=[
                {"claim_id": "C-01", "claim_text": "Revolutionary device", "ifu_source_text": "Our revolutionary best-in-class device guarantees perfect results"},
            ],
            claim_evidence_matrix=[
                {"claim_id": "C-01", "evidence_ids": []},
            ],
        )
        result = _node_build_ifu_evolution_ledger(state)
        claims = result["ifu_claim_evolution_ledger"]["claims"]
        flags = claims[0]["evolution_flags"]
        assert flags["marketing_language_detected"], "Marketing language not detected"
        assert flags["requires_human_review"], "Should require human review"


class TestBenchmarkDerivationTrace:
    """Section E: BENCHMARK_DERIVATION_TRACE schema and node tests."""

    def test_schema_exists_and_validates(self):
        """E.1: Schema file exists."""
        schema_path = SCHEMAS_DIR / "benchmark_derivation_trace.schema.json"
        assert schema_path.exists()
        schema = json.loads(schema_path.read_text())
        assert schema.get("title") == "Benchmark Derivation Trace"

    def test_schema_required_fields(self):
        """E.2: Schema includes per-endpoint required fields."""
        schema_path = SCHEMAS_DIR / "benchmark_derivation_trace.schema.json"
        schema = json.loads(schema_path.read_text())
        ep_props = schema["properties"]["endpoints"]["items"]["properties"]
        for field in ["endpoint_name", "endpoint_clinical_meaning", "source_studies",
                       "benchmark_value_range", "directness", "confidence", "acceptability_rationale"]:
            assert field in ep_props, f"Missing field: {field}"

    def test_node_produces_valid_trace(self):
        """E.3-E.5: Node produces trace with per-endpoint data."""
        from deerflow.runtime.cer_authoring.graph import _node_build_benchmark_trace

        state = _make_state()
        result = _node_build_benchmark_trace(state)
        trace = result.get("benchmark_derivation_trace", {})
        assert trace, "BENCHMARK_DERIVATION_TRACE is empty"
        endpoints = trace.get("endpoints", [])
        assert len(endpoints) == 2  # hemostasis_time, adverse_events
        for ep in endpoints:
            assert ep.get("acceptability_rationale"), f"Endpoint {ep.get('endpoint_name')} missing acceptability_rationale"

    def test_fallback_endpoint_has_alternatives_rationale(self):
        """E.6: Fallback endpoints have alternatives_rejected_rationale."""
        from deerflow.runtime.cer_authoring.graph import _node_build_benchmark_trace

        state = _make_state(
            sota_benchmark_table=[],  # No benchmarks → all fallback
            evidence_registry=[],      # No evidence → all fallback
        )
        result = _node_build_benchmark_trace(state)
        endpoints = result["benchmark_derivation_trace"]["endpoints"]
        for ep in endpoints:
            if ep.get("directness") == "fallback":
                assert ep.get("alternatives_rejected_rationale") is not None, (
                    f"Endpoint {ep.get('endpoint_name')} missing alternatives_rejected_rationale"
                )


class TestLedgerIntegration:
    """Integration: ledgers are produced with consistent claim counts."""

    def test_all_three_ledgers_produced(self):
        """All three ledger nodes run successfully."""
        from deerflow.runtime.cer_authoring.graph import (
            _node_build_reasoning_ledger,
            _node_build_ifu_evolution_ledger,
            _node_build_benchmark_trace,
        )
        state = _make_state()
        r1 = _node_build_reasoning_ledger(state)
        r2 = _node_build_ifu_evolution_ledger(state)
        r3 = _node_build_benchmark_trace(state)
        assert r1.get("cer_reasoning_ledger"), "Reasoning ledger missing"
        assert r2.get("ifu_claim_evolution_ledger"), "IFU evolution ledger missing"
        assert r3.get("benchmark_derivation_trace"), "Benchmark trace missing"

    def test_schema_validation_all_three(self):
        """All three schemas validate against JSON Schema spec (structural)."""
        import jsonschema
        for schema_name in ["cer_reasoning_ledger", "ifu_claim_evolution_ledger", "benchmark_derivation_trace"]:
            schema_path = SCHEMAS_DIR / f"{schema_name}.schema.json"
            schema = json.loads(schema_path.read_text())
            # Verify it's a valid JSON Schema by checking it validates itself
            jsonschema.Draft202012Validator.check_schema(schema)
