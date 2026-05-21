"""Integration regression tests for CER Authoring V2 upgrade."""
import pytest


class TestV2Integration:
    def test_graph_builds_with_new_nodes(self):
        from deerflow.runtime.cer_authoring.graph import build_cer_authoring_graph
        graph = build_cer_authoring_graph()
        node_names = graph.nodes.keys()
        assert "claim_sota_alignment" in node_names
        assert "device_profile_iteration" in node_names

    def test_pipeline_new_functions_exist(self):
        from deerflow.runtime.cer_authoring import pipeline
        assert hasattr(pipeline, "build_claim_sota_alignment")
        assert hasattr(pipeline, "iterate_device_profile")
        assert hasattr(pipeline, "build_cep")

    def test_gates_new_functions_exist(self):
        from deerflow.runtime.cer_authoring import gates
        assert hasattr(gates, "evaluate_claim_sota_alignment_gate")
        assert hasattr(gates, "evaluate_argument_quality_gate")
        assert hasattr(gates, "evaluate_cep_exists_gate")

    def test_agents_new_constants_exist(self):
        from deerflow.runtime.cer_authoring import agents
        assert hasattr(agents, "WRITER_QUANTIFIED_STYLE_CONSTRAINTS")
        assert hasattr(agents, "WRITER_GSPR_FIVE_PARAGRAPH_TEMPLATE")

    def test_artifacts_new_constants_exist(self):
        from deerflow.runtime.cer_authoring import artifacts
        assert hasattr(artifacts, "SEARCH_PROTOCOL_TABLE_FIELDS")
        assert hasattr(artifacts, "CLAIM_LEDGER_V2_FIELDS")

    def test_build_claim_sota_alignment_basic(self):
        from deerflow.runtime.cer_authoring.pipeline import build_claim_sota_alignment
        state = {
            "claim_ledger": [{"claim_id": "C-01", "claim_text": "Test claim", "claim_type": "clinical_benefit"}],
            "sota_benchmark_matrix": [{"benchmark_id": "B-01", "endpoint": "test", "benchmark_confidence": "medium"}],
        }
        result = build_claim_sota_alignment(state)
        assert "claim_sota_alignment_table" in result
        assert "sota_alignment_status" in result

    def test_build_cep_returns_plan(self):
        from deerflow.runtime.cer_authoring.pipeline import build_cep
        state = {"claim_ledger": [], "device_profile": {"device_name": "Test Device"}}
        result = build_cep(state)
        assert "clinical_evaluation_plan" in result
        assert result["clinical_evaluation_plan"]["document_type"] == "Clinical Evaluation Plan"
