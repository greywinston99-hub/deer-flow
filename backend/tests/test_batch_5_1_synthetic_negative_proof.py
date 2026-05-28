"""Batch 5.1 — Synthetic Negative Proof: Spiral Architecture Safety Boundaries.

Test A: Writer Block — evidence spiral exhausts 3 rounds → G42 BLOCKED →
        controlled_compromise. Writer NOT invoked. No CER draft.
Test B: Domain Mismatch Block — G39 retrieval domain mismatch → BLOCKED →
        controlled_compromise. Writer NOT invoked. No CER draft.

Both tests verify:
  - Writer was NOT called (no cer_chapter_drafts / no CER_draft.md/docx)
  - controlled_compromise artifacts exist (compromise_manifest + evidence_status_report)
  - gate_routing_trace.csv records are complete
"""

from __future__ import annotations

import csv
import json
import io
from pathlib import Path
from typing import Any

import pytest

from deerflow.runtime.cer_authoring.gates import (
    evaluate_pre_writer_readiness_gate,
    evaluate_retrieval_domain_gate,
)
from deerflow.runtime.cer_authoring.graph import (
    _node_controlled_compromise,
    _node_evidence_sufficiency_gate,
    _node_pre_writer_readiness_gate,
    _node_retrieval_domain_gate,
    _route_after_evidence_sufficiency_gate,
    _route_after_pre_writer_readiness_gate,
    _route_after_retrieval_domain_gate,
)
from deerflow.runtime.cer_authoring import pipeline

# ---------------------------------------------------------------------------
# shared helper – mirrors _passing_state() from test_cer_authoring_runtime.py
# for fixtures that are not sensitive to the exact completeness level
# ---------------------------------------------------------------------------

def _minimal_urology_state() -> dict[str, Any]:
    """Minimal urology UAS device state for negative-proof routing tests."""
    return {
        "source_inventory": [
            {
                "source_id": "SRC-IFU-001",
                "document_type": "IFU",
                "filename": "IFU.docx",
                "source_role": "subject_device_ifu",
                "primary_for_authoring": True,
                "excluded_from_device_profile": False,
            },
            {
                "source_id": "SRC-RMF-001",
                "document_type": "RMF",
                "filename": "RMF.docx",
                "source_role": "subject_device_rmf",
                "primary_for_authoring": False,
                "excluded_from_device_profile": False,
            },
        ],
        "source_role_report": {
            "status": "PASS",
            "locked_domain_hint": "urology_uas",
            "subject_ifu_source_ids": ["SRC-IFU-001"],
        },
        "device_identity_lock": {
            "status": "PASS",
            "locked_domain": "urology_uas",
            "identity_statement": "Single-use Negative Pressure Ureteral Access Sheath — urology UAS domain.",
        },
        "device_profile": {
            "device_name": "Single-use Negative Pressure Ureteral Access Sheath",
            "device_type": "ureteral access sheath",
            "intended_purpose": "Urological endoscopic access and fluid evacuation",
            "target_population": "Patients requiring IFU-defined urological endoscopic access procedures",
            "mode_of_action": "Mechanical access and fluid evacuation",
            "device_domain": "urology_uas",
        },
        "claim_ledger": [
            {"claim_id": "C-01", "claim_type": "clinical_performance", "claim_text": "The device provides safe and effective ureteral access."},
            {"claim_id": "C-02", "claim_type": "safety", "claim_text": "The device does not cause ureteral injury above IFU-defined thresholds."},
        ],
        "intended_purpose_claim_table": [
            {"claim_id": "C-01", "statement": "Safe and effective ureteral access"},
            {"claim_id": "C-02", "statement": "No ureteral injury above threshold"},
        ],
        "cep_pico_matrix": [
            {"pico_id": "PICO-01", "claim_id": "C-01", "outcome": "access success rate", "derivation_rationale": "IFU claim -> PICO"},
            {"pico_id": "PICO-02", "claim_id": "C-02", "outcome": "adverse event rate", "derivation_rationale": "Safety claim -> PICO"},
        ],
        "search_run_registry": [
            {"search_id": "SEARCH-SOTA-01", "database": "PubMed", "objective": "SOTA", "search_date": "2026-05-01", "query": "ureteral access sheath safety performance", "result_count": 45},
        ],
        "evidence_registry": [],
        "endpoint_extraction": [],
        "sota_benchmark_matrix": [],
        "claim_evidence_matrix": [],
        "benefit_risk_ledger": [],
        "alignment_matrix": [],
        "gap_pmcf_recommendations": [],
        "risk_trace_matrix": [{"risk_id": "R-001", "rmf_coverage": "covered"}],
        "gspr_coverage": [],
        "vigilance_recall_registry": [],
        "equivalence_matrix": [],
        "cer_chapter_drafts": {},
        "agent_team_mode": "stable-1plus6",
        "evidence_spiral_lineage": [],
    }


def _build_gate_trace_csv(traces: list[dict[str, Any]]) -> str:
    """Render gate_routing_trace list as a CSV string for verification."""
    if not traces:
        return ""
    buf = io.StringIO()
    writer = csv.DictWriter(
        buf,
        fieldnames=[
            "gate_id",
            "invocation_order",
            "status",
            "failure_pattern",
            "upstream_node_routed_to",
            "spiral_round",
            "blocked_reason",
        ],
        extrasaction="ignore",
    )
    writer.writeheader()
    for row in traces:
        writer.writerow(row)
    return buf.getvalue()


# ===================================================================
# TEST A — Writer Block: evidence spiral exhausts 3 rounds
# ===================================================================

class TestAWriterBlockInsufficientEvidence:
    """Verify that when evidence spiral exhausts 3 rounds without sufficiency,
    G42 → BLOCKED → controlled_compromise. Writer is never invoked."""

    def test_a1_g42_blocked_after_spiral_round_three(self):
        """G42 must return BLOCKED when spiral_round >= 3 and evidence is insufficient."""
        state = _minimal_urology_state()
        state["evidence_spiral_lineage"] = [
            {"spiral_round_id": 1, "sufficiency_after_round": "REWORK"},
            {"spiral_round_id": 2, "sufficiency_after_round": "REWORK"},
            {"spiral_round_id": 3, "sufficiency_after_round": "REWORK"},
        ]
        # No evidence — all claims lack sufficient evidence
        state["evidence_registry"] = []

        report = pipeline.evaluate_evidence_sufficiency_gate(state)

        assert report["gate_id"] == "G42", f"Expected G42, got {report.get('gate_id')}"
        assert report["status"] == "BLOCKED", (
            f"G42 must BLOCKED after 3 rounds with no evidence; got {report['status']}"
        )
        assert report["next_node"] == "controlled_compromise", (
            f"G42 BLOCKED must route to controlled_compromise; got {report['next_node']}"
        )
        assert report["current_spiral_round"] == 3
        assert report["blocked_reason"], "BLOCKED must carry a blocked_reason"

    def test_a2_g42_blocked_routes_to_controlled_compromise_in_graph(self):
        """The graph node _node_evidence_sufficiency_gate and its router must
        send BLOCKED to controlled_compromise."""
        state = _minimal_urology_state()
        state["evidence_spiral_lineage"] = [{"spiral_round_id": 3}]
        state["evidence_sufficiency_gate_override"] = {
            "status": "REWORK",
            "message": "pool too shallow after 3 rounds",
        }

        update = _node_evidence_sufficiency_gate(state)

        assert update["evidence_sufficiency_gate_report"]["status"] == "BLOCKED"
        route = _route_after_evidence_sufficiency_gate(update)
        assert route == "controlled_compromise", (
            f"G42 BLOCKED must route to controlled_compromise; got {route}"
        )

    def test_a3_g46_pre_writer_readiness_blocked_by_evidence_sufficiency(self):
        """When evidence_sufficiency sub-condition is BLOCKED, G46 must
        output BLOCKED and route to controlled_compromise."""
        state = _minimal_urology_state()
        state["pre_writer_readiness_condition_overrides"] = {
            "evidence_sufficiency": {
                "status": "BLOCKED",
                "message": "Evidence spiral exhausted 3 rounds; claims lack sufficient evidence.",
                "source_gate_ids": "G42",
            }
        }

        report = evaluate_pre_writer_readiness_gate(state)

        assert report["gate_id"] == "G46"
        assert report["status"] == "BLOCKED", (
            f"G46 must be BLOCKED when evidence_sufficiency is BLOCKED; got {report['status']}"
        )
        assert report["next_node"] == "controlled_compromise"
        assert report["writer_invoked"] is False
        assert any(
            row["condition_name"] == "evidence_sufficiency" and row["status"] == "BLOCKED"
            for row in report["conditions"]
        )

    def test_a4_controlled_compromise_node_produces_required_artifacts(self):
        """_node_controlled_compromise must produce compromise_manifest,
        evidence_status_report, recommendation, and human_decision_required.
        It must NOT produce cer_chapter_drafts."""
        state = _minimal_urology_state()
        state.pop("cer_chapter_drafts", None)
        state["pre_writer_readiness_report"] = evaluate_pre_writer_readiness_gate(
            {
                **state,
                "pre_writer_readiness_condition_overrides": {
                    "evidence_sufficiency": {
                        "status": "BLOCKED",
                        "message": "3 spiral rounds exhausted without sufficient evidence per claim.",
                        "source_gate_ids": "G42",
                    }
                },
            }
        )

        update = _node_controlled_compromise(state)

        # Status
        assert update["status"] == "controlled_compromise"
        assert update["final_gate_decision"] == "HUMAN_HOLD"

        # Manifest (compromise_manifest.json equivalent)
        manifest = update["compromise_manifest"]
        assert manifest["writer_invoked"] is False, "Writer must NOT be invoked"
        assert manifest["cer_draft_generated"] is False, "No CER draft must be generated"
        assert manifest["blocked_conditions"], "Must list blocked conditions"
        assert manifest["terminal_status"] == "EVIDENCE_INSUFFICIENT_TERMINAL", (
            f"Expected EVIDENCE_INSUFFICIENT_TERMINAL; got {manifest['terminal_status']}"
        )

        # evidence_status_report.md equivalent
        assert "What Cannot Be Concluded" in update["evidence_status_report"]
        assert "Writer was not invoked" in update["evidence_status_report"]

        # recommendation.md equivalent
        assert "supplement_evidence" in update["recommendation"]

        # human_decision_required.json equivalent
        assert update["human_decision_required"]["decisions"], "Must have pending decisions"

        # MUST NOT contain CER draft
        assert "cer_chapter_drafts" not in update, "controlled_compromise must NOT generate CER chapters"

    def test_a5_writer_never_invoked_in_full_negative_flow(self):
        """End-to-end: G42 BLOCKED → controlled_compromise → END.
        The cer_writing node must never appear in the routing trace."""
        state = _minimal_urology_state()
        state["evidence_spiral_lineage"] = [
            {"spiral_round_id": 1, "sufficiency_after_round": "REWORK"},
            {"spiral_round_id": 2, "sufficiency_after_round": "REWORK"},
            {"spiral_round_id": 3, "sufficiency_after_round": "REWORK"},
        ]
        state["evidence_sufficiency_gate_override"] = {
            "status": "REWORK",
            "message": "All 3 rounds failed to produce sufficient evidence.",
        }

        # Simulate the evidence sufficiency gate node
        g42_update = _node_evidence_sufficiency_gate(state)
        route_g42 = _route_after_evidence_sufficiency_gate(g42_update)

        assert route_g42 == "controlled_compromise", (
            f"After 3 rounds, G42 must route to controlled_compromise; got {route_g42}"
        )
        assert g42_update["evidence_sufficiency_gate_report"]["status"] == "BLOCKED"

        # Now simulate the pre-writer readiness gate reflecting this
        merged = {**state, **g42_update}
        merged["pre_writer_readiness_condition_overrides"] = {
            "evidence_sufficiency": {
                "status": "BLOCKED",
                "message": "G42 blocked after spiral exhaustion.",
                "source_gate_ids": "G42",
            }
        }
        g46_report = evaluate_pre_writer_readiness_gate(merged)
        g46_update = _node_pre_writer_readiness_gate(merged)
        route_g46 = _route_after_pre_writer_readiness_gate(g46_update)

        assert g46_report["status"] == "BLOCKED"
        assert route_g46 == "controlled_compromise", (
            f"G46 BLOCKED must route to controlled_compromise; got {route_g46}"
        )
        assert g46_report["writer_invoked"] is False

        # controlled_compromise node
        merged["pre_writer_readiness_report"] = g46_report
        cc_update = _node_controlled_compromise(merged)

        assert cc_update["compromise_manifest"]["terminal_status"] == "EVIDENCE_INSUFFICIENT_TERMINAL"

        # Collect all gate traces
        all_traces = []
        all_traces.extend(g42_update.get("gate_routing_trace") or [])
        all_traces.extend(g46_update.get("gate_routing_trace") or [])

        csv_output = _build_gate_trace_csv(all_traces)
        assert "G42" in csv_output
        assert "G46" in csv_output
        assert "BLOCKED" in csv_output
        # cer_writing must never appear
        assert "cer_writing" not in str(g42_update.get("lead_decisions") or [])
        assert "cer_writing" not in str(g46_update.get("lead_decisions") or [])

    def test_a6_gate_routing_trace_csv_contains_complete_records(self):
        """Verify the gate_routing_trace records are complete and can be
        serialized as a valid CSV."""
        state = _minimal_urology_state()
        state["evidence_spiral_lineage"] = [{"spiral_round_id": 3}]
        state["evidence_sufficiency_gate_override"] = {
            "status": "REWORK",
            "message": "final round insufficient",
        }

        g42_update = _node_evidence_sufficiency_gate(state)
        traces = g42_update.get("gate_routing_trace") or []

        assert len(traces) >= 1, "G42 must produce at least one trace record"

        for trace in traces:
            assert trace["gate_id"] == "G42"
            assert trace["status"] in {"PASS", "REWORK_REQUIRED", "BLOCKED"}
            assert "invocation_order" in trace
            assert "blocked_reason" in trace
            assert "spiral_round" in trace

        csv_output = _build_gate_trace_csv(traces)
        lines = csv_output.strip().split("\n")
        assert len(lines) >= 2, "CSV must have header + at least 1 data row"
        assert "G42" in lines[1]


# ===================================================================
# TEST B — Domain Mismatch Block: G39 retrieval domain mismatch
# ===================================================================

class TestBDomainMismatchBlock:
    """Verify that when retrieval query domain does not match device domain,
    G39 → BLOCKED → controlled_compromise. Writer is never invoked."""

    def test_b1_g39_detects_retrieval_domain_mismatch(self):
        """G39 must detect RETRIEVAL_DOMAIN_MISMATCH in evidence_source_trace_matrix."""
        state = {
            "evidence_source_trace_matrix": [
                {
                    "source_id": "SRC-SOTA-001",
                    "retrieval_domain_status": "RETRIEVAL_DOMAIN_MISMATCH_REWORK_REQUIRED",
                    "query_domain": "cardiac_ep",
                    "device_domain": "urology_uas",
                }
            ]
        }

        signal = evaluate_retrieval_domain_gate(state)

        assert signal["gate_id"] == "G39"
        assert signal["status"] == "REWORK_REQUIRED", (
            f"Expected REWORK_REQUIRED; got {signal['status']}"
        )
        assert signal["failure_pattern"] == "retrieval_domain_mismatch"
        assert signal["upstream_node_to_reroute"] == "sota_search"

    def test_b2_g39_override_blocked_routes_to_compromise(self):
        """When G39 hard_gate_signal_override is BLOCKED, it must route
        to controlled_compromise."""
        state = {
            "hard_gate_signal_overrides": {
                "G39": {
                    "status": "BLOCKED",
                    "failure_pattern": "unrecoverable_retrieval_domain_mismatch",
                    "blocked_reason": "Device is urology UAS but search queries target cardiac EP domain. Fundamental misclassification.",
                }
            }
        }

        signal = evaluate_retrieval_domain_gate(state)
        update = _node_retrieval_domain_gate(state)

        assert signal["status"] == "BLOCKED"
        assert signal["next_node"] == "controlled_compromise"
        assert signal["blocked_reason"]

        route = _route_after_retrieval_domain_gate(update)
        assert route == "controlled_compromise", (
            f"G39 BLOCKED must route to controlled_compromise; got {route}"
        )

    def test_b3_g39_blocked_leads_to_full_compromise_flow(self):
        """End-to-end: G39 BLOCKED → controlled_compromise.
        Writer must never be invoked."""
        state = _minimal_urology_state()
        state["hard_gate_signal_overrides"] = {
            "G39": {
                "status": "BLOCKED",
                "failure_pattern": "unrecoverable_retrieval_domain_mismatch",
                "blocked_reason": (
                    "Device domain is urology_uas (ureteral access sheath) but "
                    "SOTA search keywords are cardiac EP (pulsed field ablation, "
                    "atrial fibrillation, pulmonary vein). This is a fundamental "
                    "domain mismatch."
                ),
            }
        }

        # G39 routing
        g39_update = _node_retrieval_domain_gate(state)
        route_g39 = _route_after_retrieval_domain_gate(g39_update)
        assert route_g39 == "controlled_compromise"

        # Pre-writer readiness must also reflect the domain mismatch
        merged = {**state, **g39_update}
        merged["pre_writer_readiness_condition_overrides"] = {
            "retrieval_domain": {
                "status": "BLOCKED",
                "message": "G39 retrieval domain mismatch: cardiac EP queries for urology device.",
                "source_gate_ids": "G39",
                "upstream_route": "sota_search",
            }
        }
        g46_report = evaluate_pre_writer_readiness_gate(merged)
        g46_update = _node_pre_writer_readiness_gate(merged)

        assert g46_report["status"] == "BLOCKED"
        assert g46_report["writer_invoked"] is False
        route_g46 = _route_after_pre_writer_readiness_gate(g46_update)
        assert route_g46 == "controlled_compromise"

        # controlled_compromise node
        merged["pre_writer_readiness_report"] = g46_report
        cc_update = _node_controlled_compromise(merged)

        assert cc_update["status"] == "controlled_compromise"
        assert cc_update["compromise_manifest"]["writer_invoked"] is False
        assert cc_update["compromise_manifest"]["cer_draft_generated"] is False
        assert cc_update["compromise_manifest"]["terminal_status"] == "DOMAIN_FATAL", (
            f"Cardiac EP queries for urology device must be DOMAIN_FATAL; "
            f"got {cc_update['compromise_manifest']['terminal_status']}"
        )

    def test_b4_g39_domain_mismatch_gate_trace_recorded(self):
        """Verify the gate trace for G39 domain mismatch is complete."""
        state = {
            "hard_gate_signal_overrides": {
                "G39": {
                    "status": "BLOCKED",
                    "failure_pattern": "retrieval_domain_mismatch_terminal",
                    "blocked_reason": "Cardiac EP search terms for urology device.",
                }
            }
        }

        update = _node_retrieval_domain_gate(state)
        traces = update.get("gate_routing_trace") or []

        assert len(traces) >= 1
        trace = traces[0]
        assert trace["gate_id"] == "G39"
        assert trace["status"] == "BLOCKED"
        assert trace["blocked_reason"]
        assert "upstream_node_to_reroute" in trace or "upstream_node_routed_to" in trace

        csv_output = _build_gate_trace_csv(traces)
        assert "G39" in csv_output
        assert "BLOCKED" in csv_output

    def test_b5_writer_not_invoked_in_domain_mismatch_flow(self):
        """The cer_writing node must never appear in decisions when G39 blocks."""
        state = _minimal_urology_state()
        state["hard_gate_signal_overrides"] = {
            "G39": {
                "status": "BLOCKED",
                "failure_pattern": "domain_fatal_cardiac_ep_for_urology",
                "blocked_reason": "Orthopedic soft-tissue RF device path with cardiac EP keywords is a domain mismatch.",
            }
        }

        g39_update = _node_retrieval_domain_gate(state)
        lead_decisions = g39_update.get("lead_decisions") or []
        decisions_text = json.dumps(lead_decisions)

        assert "cer_writing" not in decisions_text, (
            f"Writer must not appear in decisions when G39 blocks; got: {decisions_text}"
        )

    def test_b6_g39_rework_can_route_back_to_sota_search(self):
        """G39 REWORK_REQUIRED must route back to sota_search for query fix,
        not directly to compromise."""
        state = {
            "hard_gate_signal_overrides": {
                "G39": {
                    "status": "REWORK",
                    "failure_pattern": "retrieval_domain_mismatch",
                    "upstream_node_to_reroute": "sota_search",
                }
            }
        }

        update = _node_retrieval_domain_gate(state)
        route = _route_after_retrieval_domain_gate(update)

        assert route == "sota_search", (
            f"G39 REWORK must route to sota_search for query fix; got {route}"
        )
        assert update["gate_routing_trace"][0]["status"] == "REWORK_REQUIRED"


# ===================================================================
# CROSS-CUTTING: Both tests share these assertions
# ===================================================================

class TestSyntheticNegativeProofCrossCutting:
    """Verify properties that must hold for BOTH Test A and Test B."""

    def test_compromise_never_produces_cer_draft(self):
        """Regardless of the blocking path, controlled_compromise must NEVER
        produce cer_chapter_drafts."""
        for label, blocked_conditions in (
            ("A: evidence insufficiency", {"evidence_sufficiency": {"status": "BLOCKED", "message": "G42 spiral exhaustion"}}),
            ("B: domain mismatch", {"retrieval_domain": {"status": "BLOCKED", "message": "G39 cardiac EP for urology"}}),
        ):
            state = _minimal_urology_state()
            state.pop("cer_chapter_drafts", None)
            state["pre_writer_readiness_report"] = evaluate_pre_writer_readiness_gate(
                {"pre_writer_readiness_condition_overrides": blocked_conditions}
            )
            update = _node_controlled_compromise(state)
            assert "cer_chapter_drafts" not in update, f"{label}: must not contain cer_chapter_drafts"
            assert update["compromise_manifest"]["writer_invoked"] is False, f"{label}: writer must not be invoked"
            assert update["compromise_manifest"]["cer_draft_generated"] is False, f"{label}: no CER draft"

    def test_both_paths_produce_complete_controlled_compromise_packet(self):
        """Both blocking paths must produce the four required artifacts."""
        scenarios = {
            "A: evidence_spiral_exhaustion": {
                "pre_writer_readiness_condition_overrides": {
                    "evidence_sufficiency": {"status": "BLOCKED", "message": "G42: 3 rounds, no sufficient evidence per claim."}
                }
            },
            "B: retrieval_domain_mismatch": {
                "pre_writer_readiness_condition_overrides": {
                    "retrieval_domain": {"status": "BLOCKED", "message": "G39: cardiac EP queries for urology device."}
                }
            },
        }

        for label, overrides in scenarios.items():
            state = _minimal_urology_state()
            state.pop("cer_chapter_drafts", None)
            state["pre_writer_readiness_report"] = evaluate_pre_writer_readiness_gate(overrides)
            update = _node_controlled_compromise(state)

            # 1. compromise_manifest.json
            manifest = update.get("compromise_manifest") or update.get("controlled_compromise_manifest")
            assert manifest is not None, f"{label}: compromise_manifest missing"
            assert manifest.get("terminal_status"), f"{label}: terminal_status missing"
            assert manifest.get("blocked_reason"), f"{label}: blocked_reason missing"
            assert manifest.get("blocked_conditions"), f"{label}: blocked_conditions missing"
            assert manifest["writer_invoked"] is False, f"{label}: writer_invoked must be False"
            assert manifest["cer_draft_generated"] is False, f"{label}: cer_draft_generated must be False"

            # 2. evidence_status_report.md
            report = update.get("evidence_status_report") or ""
            assert "What Is Known" in report, f"{label}: evidence_status_report missing 'What Is Known'"
            assert "What Cannot Be Concluded" in report, f"{label}: evidence_status_report missing 'What Cannot Be Concluded'"
            assert "Writer was not invoked" in report, f"{label}: evidence_status_report missing Writer status"

            # 3. recommendation.md
            rec = update.get("recommendation") or ""
            assert len(rec) > 0, f"{label}: recommendation is empty"

            # 4. human_decision_required.json
            decisions = update.get("human_decision_required") or {}
            assert decisions.get("decisions"), f"{label}: human_decision_required.decisions missing"

    def test_gate_trace_includes_all_gate_invocations(self):
        """Gate trace for both scenarios must include the blocking gate and G46."""
        state_a = _minimal_urology_state()
        state_a["evidence_spiral_lineage"] = [{"spiral_round_id": 3}]
        state_a["evidence_sufficiency_gate_override"] = {"status": "REWORK", "message": "exhausted"}
        g42 = _node_evidence_sufficiency_gate(state_a)
        traces_a = g42.get("gate_routing_trace") or []
        assert any(t["gate_id"] == "G42" for t in traces_a), "Test A: G42 must be in trace"

        state_b = {
            "hard_gate_signal_overrides": {
                "G39": {"status": "BLOCKED", "failure_pattern": "domain_mismatch", "blocked_reason": "test"}
            }
        }
        g39 = _node_retrieval_domain_gate(state_b)
        traces_b = g39.get("gate_routing_trace") or []
        assert any(t["gate_id"] == "G39" for t in traces_b), "Test B: G39 must be in trace"
