"""Test that all WS gates are wired into the main authoring gate aggregation."""

from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))


class TestWSGatesInMainAggregation:
    def test_ws_gates_in_run_authoring_gates(self):
        """All WS2-WS10 gates must appear in run_authoring_gates()."""
        gate_source = (Path(__file__).resolve().parent.parent / "gates.py").read_text()
        run_agg_start = gate_source.index("def run_authoring_gates")
        run_agg_end = gate_source.index("def _gate_source_preflight", run_agg_start)
        agg_body = gate_source[run_agg_start:run_agg_end]

        required_gates = [
            "_gate_ws2_ifu_iteration_closure",
            "_gate_ws2_ifu_overclaim",
            "_gate_ws3_claim_taxonomy",
            "_gate_ws3_final_body_claim_eligibility",
            "_gate_ws4_prisma_reproducibility",
            "_gate_ws5_evidence_level_ceiling",
            "_gate_ws6_endpoint_homogeneity",
            "_gate_ws7_equivalence_route",
            "_gate_ws8_benefit_risk_body_section",
            "_gate_ws9_rmf_ifu_warning_linkage",
            "_gate_ws10_submission_cleanliness",
            "_gate_ws10_conclusion_completeness",
            "_gate_ws10_body_annex_boundary",
        ]

        for gate_name in required_gates:
            assert gate_name in agg_body, f"{gate_name} not found in run_authoring_gates()"

    def test_ws_critical_gate_ids_in_set(self):
        """WS critical gate IDs must be in the critical_gate_ids set."""
        gate_source = (Path(__file__).resolve().parent.parent / "gates.py").read_text()
        run_agg_start = gate_source.index("def run_authoring_gates")
        run_agg_end = gate_source.index("def _gate_source_preflight", run_agg_start)
        agg_body = gate_source[run_agg_start:run_agg_end]

        required_critical = [
            "WS2_IFU_OVERCLAIM",
            "WS3_CLAIM_ELIGIBILITY",
            "WS4_PRISMA_REPRODUCIBILITY",
            "WS5_EVIDENCE_LEVEL_CEILING",
            "WS7_EQUIVALENCE_ROUTE",
            "WS8_BR_BODY_SECTION",
            "WS9_RMF_IFU_LINKAGE",
            "WS10_SUBMISSION_CLEANLINESS",
        ]

        for gate_id in required_critical:
            assert gate_id in agg_body, f"Critical gate ID {gate_id} not in critical_gate_ids"

    def test_ws_gates_return_gate_result(self):
        """WS gates must return GateResult objects, not plain dicts."""
        from deerflow.runtime.cer_authoring.gates import (
            _gate_ws2_ifu_overclaim,
            _gate_ws3_claim_taxonomy,
            _gate_ws4_prisma_reproducibility,
            _gate_ws5_evidence_level_ceiling,
            _gate_ws7_equivalence_route,
            _gate_ws10_submission_cleanliness,
            GateResult,
        )

        state = {"claim_ledger": [], "source_inventory": []}

        g1 = _gate_ws2_ifu_overclaim(state)
        assert isinstance(g1, GateResult), f"Expected GateResult, got {type(g1)}"
        g2 = _gate_ws3_claim_taxonomy(state)
        assert isinstance(g2, GateResult)
        g3 = _gate_ws4_prisma_reproducibility(state)
        assert isinstance(g3, GateResult)
        g4 = _gate_ws5_evidence_level_ceiling(state)
        assert isinstance(g4, GateResult)
        g5 = _gate_ws7_equivalence_route(state)
        assert isinstance(g5, GateResult)

    def test_pre_writer_readiness_consumes_ws_gates(self):
        """Pre-writer readiness must include WS2-WS7 condition checks."""
        gate_source = (Path(__file__).resolve().parent.parent / "gates.py").read_text()
        pre_writer_start = gate_source.index("def evaluate_pre_writer_readiness_gate")
        # Find the next function after pre_writer
        next_func = gate_source.index("\ndef ", pre_writer_start + 100)
        pre_writer_body = gate_source[pre_writer_start:next_func]

        ws_conditions = [
            "WS4_PRISMA",
            "WS7_EQUIVALENCE",
            "WS2_IFU_OVERCLAIM",
            "WS3_CLAIM_ELIGIBILITY",
            "WS5_EVIDENCE_CEILING",
            "WS6_ENDPOINT_HOMOGENEITY",
            "WS9_RMF_LINKAGE",
        ]

        for cond in ws_conditions:
            assert cond in pre_writer_body, f"Pre-writer condition {cond} not found in evaluate_pre_writer_readiness_gate"

    def test_ws_gates_as_dict_method(self):
        """All GateResult objects must have as_dict() method."""
        from deerflow.runtime.cer_authoring.gates import GateResult

        gr = GateResult("TEST", "PASS", "ok")
        d = gr.as_dict()
        assert d["gate_id"] == "TEST"
        assert d["status"] == "PASS"
        assert "message" in d
