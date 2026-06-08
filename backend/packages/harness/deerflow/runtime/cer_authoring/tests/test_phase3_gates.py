"""BIGDP2026.6 Phase 3: Gate Integration tests.

Tests G42 dynamic max rounds, G43 ledger consumption, Source Preflight
4-tier severity, and G46 ledger-aware Writer Release Board conditions.
"""
import pytest


class TestG42DynamicMaxRounds:
    """F.1: G42 dynamic max rounds based on device class and claim criticality."""

    def test_class_iii_gets_higher_ceiling(self):
        """Class III devices get deeper retrieval allowance."""
        from deerflow.runtime.cer_authoring.gates import _compute_g42_dynamic_max_rounds

        state = {
            "device_profile": {"device_class": "III"},
            "claim_ledger": [],
        }
        result = _compute_g42_dynamic_max_rounds(state)
        assert result > 3, f"Class III should get > 3 rounds, got {result}"

    def test_class_i_gets_base_ceiling(self):
        """Class I devices get base ceiling (no bonus)."""
        from deerflow.runtime.cer_authoring.gates import _compute_g42_dynamic_max_rounds

        state = {
            "device_profile": {"device_class": "I"},
            "claim_ledger": [],
        }
        result = _compute_g42_dynamic_max_rounds(state)
        assert result == 3, f"Class I should get base 3 rounds, got {result}"

    def test_high_criticality_adds_bonus(self):
        """Claims with high criticality get +1 spiral round."""
        from deerflow.runtime.cer_authoring.gates import _compute_g42_dynamic_max_rounds

        state = {
            "device_profile": {"device_class": "IIa"},
            "cer_reasoning_ledger": {
                "claims": [
                    {"claim_id": "C-01", "claim_criticality": "high"},
                ],
            },
            "claim_ledger": [],
        }
        result = _compute_g42_dynamic_max_rounds(state)
        assert result == 4, f"IIa + high criticality should = 4, got {result}"

    def test_dynamic_max_capped_at_6(self):
        """Dynamic max rounds are capped at 6."""
        from deerflow.runtime.cer_authoring.gates import _compute_g42_dynamic_max_rounds

        state = {
            "device_profile": {"device_class": "III"},
            "cer_reasoning_ledger": {
                "claims": [
                    {"claim_id": "C-01", "claim_criticality": "high"},
                    {"claim_id": "C-02", "claim_criticality": "high"},
                ],
            },
            "claim_ledger": [],
        }
        result = _compute_g42_dynamic_max_rounds(state)
        assert result <= 6, f"Dynamic max should be capped at 6, got {result}"

    def test_g42_report_includes_dynamic_max(self):
        """G42 report includes dynamic_max_rounds and device_class."""
        from deerflow.runtime.cer_authoring.gates import evaluate_evidence_sufficiency_gate

        state = {
            "device_profile": {"device_class": "III"},
            "claim_ledger": [{"claim_id": "C-01"}],
            "pre_g42_claim_evidence_candidate_matrix": [
                {"claim_id": "C-01", "sufficiency_status": "REWORK_REQUIRED",
                 "failure_pattern": "EVIDENCE_TRULY_INSUFFICIENT", "repair_route": "query_expansion"},
            ],
            "evidence_spiral_lineage": [
                {"spiral_round_id": 1}, {"spiral_round_id": 2}, {"spiral_round_id": 3},
                {"spiral_round_id": 4}, {"spiral_round_id": 5},
            ],
        }
        result = evaluate_evidence_sufficiency_gate(state)
        reroute = result.get("reroute_context", {})
        assert "dynamic_max_rounds" in reroute, "G42 report missing dynamic_max_rounds"
        assert "device_class" in reroute, "G42 report missing device_class"


class TestG43LedgerConsumption:
    """F.2: G43 consumes CER_REASONING_LEDGER for claim classification context."""

    def test_g43_passes_with_valid_linkage(self):
        """All claims linked with valid support types → PASS."""
        from deerflow.runtime.cer_authoring.gates import evaluate_claim_evidence_gate

        state = {
            "claim_ledger": [{"claim_id": "C-01"}],
            "claim_evidence_matrix": [
                {"claim_id": "C-01", "evidence_ids": ["E-001"], "support_type": "direct"},
            ],
            "cer_reasoning_ledger": {
                "claims": [{"claim_id": "C-01", "evidence_support_type": "direct"}],
            },
        }
        result = evaluate_claim_evidence_gate(state)
        assert result["status"] == "PASS", f"Expected PASS, got {result['status']}"

    def test_g43_flags_insufficient_support_type(self):
        """Claim with 'insufficient' support type → REWORK_REQUIRED."""
        from deerflow.runtime.cer_authoring.gates import evaluate_claim_evidence_gate

        state = {
            "claim_ledger": [{"claim_id": "C-01"}],
            "claim_evidence_matrix": [
                {"claim_id": "C-01", "evidence_ids": ["E-001"], "support_type": "insufficient"},
            ],
        }
        result = evaluate_claim_evidence_gate(state)
        assert result["status"] == "REWORK_REQUIRED"

    def test_g43_missing_evidence_link(self):
        """Claim without evidence_ids → REWORK_REQUIRED."""
        from deerflow.runtime.cer_authoring.gates import evaluate_claim_evidence_gate

        state = {
            "claim_ledger": [{"claim_id": "C-01"}],
            "claim_evidence_matrix": [],
        }
        result = evaluate_claim_evidence_gate(state)
        assert result["status"] == "REWORK_REQUIRED"

    def test_g43_consumes_reasoning_ledger(self):
        """G43 report indicates reasoning_ledger_consumed."""
        from deerflow.runtime.cer_authoring.gates import evaluate_claim_evidence_gate

        state = {
            "claim_ledger": [{"claim_id": "C-01"}],
            "claim_evidence_matrix": [
                {"claim_id": "C-01", "evidence_ids": ["E-001"], "support_type": "direct"},
            ],
            "cer_reasoning_ledger": {
                "claims": [{"claim_id": "C-01", "evidence_support_type": "direct"}],
            },
        }
        result = evaluate_claim_evidence_gate(state)
        assert result.get("reasoning_ledger_consumed"), "G43 should indicate ledger consumption"


class TestSourcePreflightTiers:
    """F.3.4: Source Preflight 4-tier severity — CRITICAL/MAJOR/WARNING/AUTO_FIXABLE."""

    def test_critical_severity_blocks(self):
        """CRITICAL severity → BLOCKED."""
        from deerflow.runtime.cer_authoring.gates import _gate_source_preflight

        state = {
            "source_preflight_gate_report": {
                "severity": "CRITICAL",
                "critical_issues": ["RMF missing", "IFU missing"],
            },
        }
        result = _gate_source_preflight(state)
        assert result.status == "BLOCKED"
        assert "CRITICAL" in result.message

    def test_major_severity_passes_with_gaps(self):
        """MAJOR severity → PASS (with documented gaps)."""
        from deerflow.runtime.cer_authoring.gates import _gate_source_preflight

        state = {
            "source_preflight_gate_report": {
                "severity": "MAJOR",
                "controlled_gaps": ["TD missing — CER will note limitation"],
            },
        }
        result = _gate_source_preflight(state)
        assert result.status == "PASS"
        assert "MAJOR" in result.message

    def test_warning_severity_passes(self):
        """WARNING severity → PASS (non-blocking)."""
        from deerflow.runtime.cer_authoring.gates import _gate_source_preflight

        state = {
            "source_preflight_gate_report": {
                "severity": "WARNING",
                "warnings": ["IFU version is older than 3 years"],
            },
        }
        result = _gate_source_preflight(state)
        assert result.status == "PASS"
        assert "WARNING" in result.message

    def test_auto_fixable_passes(self):
        """AUTO_FIXABLE severity → PASS (auto-resolved)."""
        from deerflow.runtime.cer_authoring.gates import _gate_source_preflight

        state = {
            "source_preflight_gate_report": {
                "severity": "AUTO_FIXABLE",
                "auto_fixable": ["Normalized device name casing"],
            },
        }
        result = _gate_source_preflight(state)
        assert result.status == "PASS"

    def test_legacy_blocked_still_blocks(self):
        """Legacy 'BLOCKED' status (no severity field) → BLOCKED."""
        from deerflow.runtime.cer_authoring.gates import _gate_source_preflight

        state = {
            "source_preflight_gate_report": {
                "status": "BLOCKED",
                "blocking_issues": ["Missing required document"],
            },
        }
        result = _gate_source_preflight(state)
        assert result.status == "BLOCKED"

    def test_no_report_passes(self):
        """No source preflight report → PASS (no issues)."""
        from deerflow.runtime.cer_authoring.gates import _gate_source_preflight

        result = _gate_source_preflight({})
        assert result.status == "PASS"


class TestG46LedgerAwareness:
    """G46 Writer Release Board checks for ledger existence."""

    def test_g46_flags_missing_reasoning_ledger(self):
        """G46 reports REWORK when CER_REASONING_LEDGER is missing."""
        from deerflow.runtime.cer_authoring.gates import evaluate_pre_writer_readiness_gate

        state = {
            "prisma_flow_data": {"flow": {"raw_hits": 1}},
            "source_inventory": [],
            "claim_ledger": [{"claim_id": "C-01"}],
            "claim_evidence_matrix": [{"claim_id": "C-01", "evidence_ids": ["E-001"]}],
            "search_run_registry": [{"status": "completed", "database": "PubMed", "search_date": "2026-01-01", "exact_query": "test"}],
            "clinical_evaluation_plan": {"device_name": "T", "device_class": "IIb", "scope": "S",
                "literature_search_protocol": {"databases": ["PubMed"], "inclusion_criteria": ["RCT"], "exclusion_criteria": ["CR"]},
                "appraisal_method": "MDCG", "sota_methodology": "LSP", "claim_support_method": "M", "benefit_risk_method": "M", "pms_pmcf_update_plan": "P"},
            "locked_endpoint_framework": {"primary_endpoints": [{"name": "ep1"}]},
            "consolidated_clinical_data_table": {"data_sources": [{"source": "PubMed"}]},
            "eu_market_status": "approved",
            "device_profile": {"device_name": "T"},
            "screening_disposition": [],
        }
        result = evaluate_pre_writer_readiness_gate(state)
        conditions = {r["condition_name"]: r["status"] for r in result.get("conditions", [])}
        assert "CER_REASONING_LEDGER" in conditions, "G46 should check for CER_REASONING_LEDGER"

    def test_g46_with_all_ledgers_populated(self):
        """G46 does not fail when all 3 ledgers are populated."""
        from deerflow.runtime.cer_authoring.gates import evaluate_pre_writer_readiness_gate

        state = {
            "prisma_flow_data": {"flow": {"raw_hits": 1}},
            "source_inventory": [],
            "claim_ledger": [{"claim_id": "C-01"}],
            "claim_evidence_matrix": [{"claim_id": "C-01", "evidence_ids": ["E-001"]}],
            "search_run_registry": [{"status": "completed", "database": "PubMed", "search_date": "2026-01-01", "exact_query": "test"}],
            "clinical_evaluation_plan": {"device_name": "T", "device_class": "IIb", "scope": "S",
                "literature_search_protocol": {"databases": ["PubMed"], "inclusion_criteria": ["RCT"], "exclusion_criteria": ["CR"]},
                "appraisal_method": "MDCG", "sota_methodology": "LSP", "claim_support_method": "M", "benefit_risk_method": "M", "pms_pmcf_update_plan": "P"},
            "locked_endpoint_framework": {"primary_endpoints": [{"name": "ep1"}]},
            "consolidated_clinical_data_table": {"data_sources": [{"source": "PubMed"}]},
            "eu_market_status": "approved",
            "device_profile": {"device_name": "T"},
            "screening_disposition": [],
            # All 3 ledgers populated
            "cer_reasoning_ledger": {"claims": [{"claim_id": "C-01"}]},
            "ifu_claim_evolution_ledger": {"claims": [{"claim_id": "C-01"}]},
            "benchmark_derivation_trace": {"endpoints": [{"endpoint_name": "ep1"}]},
        }
        result = evaluate_pre_writer_readiness_gate(state)
        conditions = {r["condition_name"]: r["status"] for r in result.get("conditions", [])}
        cer_ledger_status = conditions.get("CER_REASONING_LEDGER", "NOT_FOUND")
        ifu_ledger_status = conditions.get("IFU_CLAIM_EVOLUTION_LEDGER", "NOT_FOUND")
        bench_status = conditions.get("BENCHMARK_DERIVATION_TRACE", "NOT_FOUND")
        # With populated ledgers, these conditions should PASS (not REWORK)
        assert cer_ledger_status != "REWORK_REQUIRED", f"CER_REASONING_LEDGER: {cer_ledger_status}"
        assert ifu_ledger_status != "REWORK_REQUIRED", f"IFU_CLAIM_EVOLUTION_LEDGER: {ifu_ledger_status}"
        assert bench_status != "REWORK_REQUIRED", f"BENCHMARK_DERIVATION_TRACE: {bench_status}"
