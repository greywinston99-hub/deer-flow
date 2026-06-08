"""BIGDP2026.6V4 Batches I/J/K/L tests."""
import pytest
from deerflow.runtime.cer_authoring.expert_rule_loader import (
    classify_strategy_route, WET_6_CONDITIONS, STRATEGY_ROUTES,
    classify_literature_role, LITERATURE_ROLES,
    get_route_blueprint, ROUTE_BLUEPRINTS,
    generate_nb_explainability_packet,
)


class TestBatchIStrategyRouter:
    def test_wet_all_conditions_pass(self):
        state = {"device_profile": {"device_class": "IIa"}, "evidence_registry": [{"weight": "pivotal"}]*3,
                 "wet_device_technology_established_stable": True, "wet_low_risk_scope_acceptable": True,
                 "wet_SOTA_stable": True, "wet_PMS_PMCF_data_sufficient": True,
                 "wet_BR_clearly_acceptable": True, "wet_intended_purpose_narrow_well_defined": True,
                 "PMS_PMCF_review_complete": True}
        r = classify_strategy_route(state)
        assert r["strategy_context_route"] == "WET"

    def test_wet_blocked_when_condition_fails(self):
        state = {"device_profile": {"device_class": "IIb", "is_implantable": True},
                 "evidence_registry": [], "wet_device_technology_established_stable": False}
        r = classify_strategy_route(state)
        assert r["strategy_context_route"] != "WET"

    def test_equivalence_without_data_access_blocked(self):
        state = {"device_profile": {"device_class": "IIb"}, "equivalence_claimed": True,
                 "equivalence_data_access": False, "evidence_registry": []}
        r = classify_strategy_route(state)
        assert r["final_CER_strategy"] == "cannot_support_current_claim"

    def test_unsupported_cannot_be_saved_by_pmcf(self):
        state = {"device_profile": {"device_class": "III"}, "evidence_registry": []}
        r = classify_strategy_route(state)
        assert r["sufficiency_decision"] == "cannot_support"

    def test_wet_6_conditions_defined(self):
        assert len(WET_6_CONDITIONS) == 6

    def test_all_routes_defined(self):
        assert len(STRATEGY_ROUTES) == 6


class TestBatchJLiteratureIntelligence:
    def test_direct_device_evidence(self):
        r = classify_literature_role({"title": "VasoSeal RCT", "device_studied": "VasoSeal Pro", "sample_size": 200}, "VasoSeal Pro")
        assert r["primary_article_role"] == "direct_device_evidence"

    def test_animal_study_excluded(self):
        r = classify_literature_role({"title": "Porcine model", "abstract": "swine study", "sample_size": 8}, "")
        assert r["primary_article_role"] == "excluded"

    def test_n10_excluded(self):
        r = classify_literature_role({"title": "Case study", "sample_size": 2}, "")
        assert r["primary_article_role"] == "excluded"

    def test_roles_defined(self):
        assert len(LITERATURE_ROLES) == 8


class TestBatchKCERBlueprints:
    def test_wet_forbids_demonstrates(self):
        bp = get_route_blueprint("WET")
        assert "demonstrates superiority" in bp["forbidden_language"]

    def test_legacy_forbids_grandfathered(self):
        bp = get_route_blueprint("legacy")
        assert "grandfathered" in bp["forbidden_language"]

    def test_equivalence_forbids_direct_evidence(self):
        bp = get_route_blueprint("equivalence")
        assert "direct evidence" in bp["forbidden_language"]

    def test_innovation_requires_ci_plan(self):
        bp = get_route_blueprint("innovation")
        assert "clinical_investigation_plan" in bp["required_elements"]

    def test_all_blueprints_defined(self):
        for route in ["WET", "legacy", "equivalence", "literature_primary", "innovation"]:
            assert route in ROUTE_BLUEPRINTS


class TestBatchLNBExplainability:
    def test_packet_generated(self):
        strat = {"strategy_context_route": "WET", "route_rationale": "Test", "route_confidence": "high",
                 "wet_6_condition_results": {c: True for c in WET_6_CONDITIONS}}
        pkt = generate_nb_explainability_packet(strat, {"evidence_registry": [{}]})
        assert "likely_NB_challenges" in pkt
        assert len(pkt["likely_NB_challenges"]) >= 2

    def test_wet_challenge_includes_conditions(self):
        strat = {"strategy_context_route": "WET", "route_rationale": "Test", "route_confidence": "high",
                 "wet_6_condition_results": {c: True for c in WET_6_CONDITIONS}}
        pkt = generate_nb_explainability_packet(strat, {"evidence_registry": []})
        wet_challenges = [c for c in pkt["likely_NB_challenges"] if c["decision_type"] == "WET_legacy"]
        assert len(wet_challenges) >= 1
