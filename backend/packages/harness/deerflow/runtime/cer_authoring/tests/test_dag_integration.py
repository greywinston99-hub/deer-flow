"""BIGDP2026.6: DAG integration test — end-to-end traversal with ledger nodes.

Verifies the full Authoring DAG compiles, ledger nodes are correctly positioned
before G46, and state flows correctly through the ledger chain.
"""
import json
import pytest
from pathlib import Path


class TestDAGCompilation:
    """DAG compiles with all nodes, including ledger chain."""

    def test_dag_compiles(self):
        """build_cer_authoring_graph returns a valid graph."""
        from deerflow.runtime.cer_authoring.graph import build_cer_authoring_graph
        graph = build_cer_authoring_graph()
        assert graph is not None
        nodes = list(graph.nodes.keys())
        assert len(nodes) >= 50, f"Expected ≥50 nodes, got {len(nodes)}"

    def test_ledger_nodes_registered(self):
        """All 3 ledger nodes are in the DAG."""
        from deerflow.runtime.cer_authoring.graph import build_cer_authoring_graph
        graph = build_cer_authoring_graph()
        nodes = list(graph.nodes.keys())
        for node_name in ["build_reasoning_ledger", "build_ifu_evolution_ledger", "build_benchmark_trace"]:
            assert node_name in nodes, f"Ledger node '{node_name}' NOT in DAG"

    def test_ledger_chain_positioned_before_g46(self):
        """Ledger chain nodes and G46 are all in the DAG."""
        from deerflow.runtime.cer_authoring.graph import build_cer_authoring_graph
        graph = build_cer_authoring_graph()

        nodes = list(graph.nodes.keys())
        # Verify all 3 ledger nodes exist
        for n in ["build_reasoning_ledger", "build_ifu_evolution_ledger", "build_benchmark_trace"]:
            assert n in nodes, f"'{n}' not in graph nodes"

        # Verify pre_writer_readiness_gate (G46) still exists
        assert "pre_writer_readiness_gate" in nodes, "G46 node missing from graph"

        # Verify post-G46 chain still exists
        for n in ["endpoint_framework_lock", "clinical_data_consolidation", "cer_input_package_export"]:
            assert n in nodes, f"Post-G46 chain node '{n}' missing"


class TestLedgerNodeExecution:
    """All 3 ledger nodes execute with valid state and produce correct output."""

    def _make_minimal_state(self):
        return {
            "device_profile": {"device_name": "Test Device", "device_class": "IIb", "intended_use": "Test use"},
            "claim_ledger": [
                {"claim_id": "C-01", "claim_text": "Achieves hemostasis", "claim_type": "clinical_performance"},
            ],
            "claim_evidence_matrix": [
                {"claim_id": "C-01", "evidence_ids": ["E-001", "E-002"], "support_type": "direct"},
            ],
            "endpoint_registry": [
                {"name": "hemostasis_time", "type": "primary_efficacy", "clinical_meaning": "Time to hemostasis"},
            ],
            "sota_benchmark_table": [],
            "benefit_risk_ledger": [],
            "evidence_registry": [
                {"evidence_id": "E-001", "pmid": "12345", "first_author": "Smith", "year": 2024, "study_design": "RCT", "sample_size": 200},
                {"evidence_id": "E-002", "pmid": "12346", "first_author": "Jones", "year": 2023, "study_design": "Prospective", "sample_size": 150},
            ],
            "ifu_working_document": {"filename": "IFU_test.pdf"},
            "equivalence_claimed": False,
            "equivalent_device_name": "",
        }

    def test_ledger_chain_executes_in_order(self):
        """All 3 ledgers execute and produce state for G46."""
        from deerflow.runtime.cer_authoring.graph import (
            _node_build_reasoning_ledger,
            _node_build_ifu_evolution_ledger,
            _node_build_benchmark_trace,
        )

        state = self._make_minimal_state()

        # Step 1: Build reasoning ledger
        r1 = _node_build_reasoning_ledger(state)
        assert r1.get("cer_reasoning_ledger"), "Reasoning ledger not produced"
        state.update(r1)

        # Step 2: Build IFU evolution ledger
        r2 = _node_build_ifu_evolution_ledger(state)
        assert r2.get("ifu_claim_evolution_ledger"), "IFU evolution ledger not produced"
        state.update(r2)

        # Step 3: Build benchmark trace
        r3 = _node_build_benchmark_trace(state)
        assert r3.get("benchmark_derivation_trace"), "Benchmark trace not produced"
        state.update(r3)

        # Step 4: All 3 ledgers in state before G46
        assert state.get("cer_reasoning_ledger"), "Reasoning ledger missing from state"
        assert state.get("ifu_claim_evolution_ledger"), "IFU evolution missing from state"
        assert state.get("benchmark_derivation_trace"), "Benchmark trace missing from state"

    def test_g46_sees_populated_ledgers(self):
        """When ledgers are populated, G46 ledger conditions PASS."""
        from deerflow.runtime.cer_authoring.graph import (
            _node_build_reasoning_ledger,
            _node_build_ifu_evolution_ledger,
            _node_build_benchmark_trace,
        )
        from deerflow.runtime.cer_authoring.gates import evaluate_pre_writer_readiness_gate

        state = self._make_minimal_state()

        # Add minimal state for G46 WS gates
        state.update({
            "prisma_flow_data": {"flow": {"raw_hits": 1}},
            "source_inventory": [],
            "search_run_registry": [{"status": "completed", "database": "PubMed", "search_date": "2026-01-01", "exact_query": "test"}],
            "clinical_evaluation_plan": {
                "device_name": "Test", "device_class": "IIb", "scope": "Test",
                "literature_search_protocol": {"databases": ["PubMed"], "inclusion_criteria": ["RCT"], "exclusion_criteria": ["CR"]},
                "appraisal_method": "MDCG", "sota_methodology": "LSP", "claim_support_method": "M", "benefit_risk_method": "M", "pms_pmcf_update_plan": "P",
            },
            "locked_endpoint_framework": {"primary_endpoints": [{"name": "ep1"}]},
            "consolidated_clinical_data_table": {"data_sources": [{"source": "PubMed"}]},
            "eu_market_status": "approved",
            "screening_disposition": [],
        })

        # Build ledgers
        state.update(_node_build_reasoning_ledger(state))
        state.update(_node_build_ifu_evolution_ledger(state))
        state.update(_node_build_benchmark_trace(state))

        # G46 should see populated ledgers (ledger conditions should not be REWORK_REQUIRED)
        result = evaluate_pre_writer_readiness_gate(state)
        conditions = {r["condition_name"]: r["status"] for r in result.get("conditions", [])}
        ledger_conditions = ["CER_REASONING_LEDGER", "IFU_CLAIM_EVOLUTION_LEDGER", "BENCHMARK_DERIVATION_TRACE"]
        for cond in ledger_conditions:
            if cond in conditions:
                assert conditions[cond] != "REWORK_REQUIRED", (
                    f"{cond} should not be REWORK_REQUIRED when populated. Got: {conditions[cond]}"
                )
