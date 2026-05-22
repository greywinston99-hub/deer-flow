"""E2E scenarios test — 6 scenarios × domain/NB/class combinations."""
import pytest
from deerflow.runtime.cer_authoring.pipeline import (
    _build_pmcf_template,
    _build_br_quantitative_template,
    _validate_data_flows,
    _device_domain_to_kb_family,
    _gspr_depth_config,
    _build_nb_specific_context,
)

_E2E_SCENARIOS = [
    {"domain": "cardiac_pfa", "nb": "BSI", "class": "III"},
    {"domain": "urology_nephroscope", "nb": "TUV_SUD", "class": "IIb"},
    {"domain": "cardiovascular_rf_ablation", "nb": "BSI", "class": "III"},
    {"domain": "plasma_surgical_electrode", "nb": "DEKRA", "class": "IIb"},
    {"domain": "ventricular_assist", "nb": "BSI", "class": "III"},
    {"domain": "medical_imaging_software", "nb": "MEDCERT", "class": "IIa"},
]


@pytest.mark.parametrize("scenario", _E2E_SCENARIOS)
def test_scenario_device_kb_loaded(scenario):
    """Each scenario's device KB family is resolvable."""
    family = _device_domain_to_kb_family(scenario["domain"])
    assert family, f"No KB family for {scenario['domain']}"
    assert family.startswith("DEV-"), f"Unexpected family: {family}"


@pytest.mark.parametrize("scenario", _E2E_SCENARIOS)
def test_scenario_gspr_depth(scenario):
    """Each scenario's GSPR depth config is correct."""
    cfg = _gspr_depth_config({"device_profile": {"device_class": scenario["class"]}})
    assert cfg["mode"] in ("per_item", "grouped", "summary")
    if "III" in scenario["class"]:
        assert cfg["mode"] == "per_item"
    elif "IIb" in scenario["class"]:
        assert cfg["mode"] == "grouped"


@pytest.mark.parametrize("scenario", _E2E_SCENARIOS)
def test_scenario_nb_profile(scenario):
    """Each scenario's NB profile resolves."""
    ctx = _build_nb_specific_context({"device_profile": {"nb_body": scenario["nb"]}})
    if scenario["nb"] in ("BSI", "TUV_SUD"):
        assert ctx.get("prompt_prefix"), f"No prompt_prefix for {scenario['nb']}"


def test_pmcf_template_generates():
    """PMCF template has required fields."""
    tmpl = _build_pmcf_template({"device_profile": {"device_class": "III"}})
    assert "pmcf_objectives" in tmpl
    assert "suggested_timeline" in tmpl
    assert "rmf_prerequisite_check" in tmpl


def test_br_template_generates():
    """BR quantitative template has required fields."""
    tmpl = _build_br_quantitative_template({
        "benefit_risk_ledger": [
            {"magnitude_of_benefit": "Reduces procedure time by 30%", "mdcg_level": 2},
            {"severity_of_risk": "Infection risk <2%"},
        ]
    })
    assert len(tmpl["benefits"]) >= 1
    assert "mdcg_weight_mapping" in tmpl


def test_data_flow_validation():
    """Data flow validation checks all 8 flows."""
    result = _validate_data_flows({
        "device_profile": {"device_name": "Test"},
        "sota_benchmark_matrix": [{"endpoint": "test"}],
        "evidence_registry": [{"id": "E1"}],
        "cer_chapter_drafts": {"5 Conclusions": "The benefit-risk is acceptable."},
        "benefit_risk_ledger": [{"benefit_risk_balance": "favourable"}],
        "claim_evidence_matrix": [],
        "vigilance_recall_registry": [],
    })
    assert "data_flow_validation" in result
    flows = result["data_flow_validation"]
    assert flows["§2→§3"] == "PASS"
    assert flows["§3→§4"] == "PASS"
    assert flows["§4→§5"] == "PASS"
    assert flows["BR→Conclusion"] == "PASS"
