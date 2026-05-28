"""WS8: Benefit-Risk Body Section Tests."""

from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from deerflow.runtime.cer_authoring.benefit_risk_section import build_benefit_risk_body_section


class TestBenefitRiskBodySection:
    def test_empty_body_detects_missing_section(self):
        br = build_benefit_risk_body_section({}, "")
        assert br["benefit_risk_body_section"]["section_present"] is False

    def test_body_with_br_section_detected(self):
        body = """
        ## 4.8 Benefit-Risk Analysis
        The clinical benefits include a 30% reduction in mortality (n=150, p<0.01).
        Residual risks are controlled through IFU warnings and design safeguards.
        PMS data from 500 patients shows no new safety signals.
        """
        br = build_benefit_risk_body_section({}, body)
        assert br["benefit_risk_body_section"]["section_present"] is True

    def test_quantitative_data_detected(self):
        body = "The incidence rate was 2.3% with 95% CI 1.1-3.5%, p=0.02."
        br = build_benefit_risk_body_section({}, body)
        assert br["benefit_risk_body_section"]["has_quantitative_data"] is True

    def test_risk_mapping_detected(self):
        body = "Residual risk after control measures is acceptable. The risk control measures include..."
        br = build_benefit_risk_body_section({}, body)
        assert br["benefit_risk_body_section"]["has_risk_mapping"] is True

    def test_pms_pmcf_maturity_detected(self):
        body = "Post-market surveillance data from 2023-2025 confirms the safety profile. The PMCF plan addresses remaining uncertainties."
        br = build_benefit_risk_body_section({}, body)
        assert br["benefit_risk_body_section"]["has_pms_pmcf_maturity_discussion"] is True

    def test_blocked_when_no_br_section(self):
        br = build_benefit_risk_body_section({}, "")
        assert br["conclusion_allowed"] == "blocked_missing_br_section"
        assert br["unqualified_favourable_allowed"] is False

    def test_controlled_uncertainty_when_incomplete(self):
        body = "## 4.8 Benefit-Risk Analysis\nThe device appears safe based on limited data."
        state = {"rmf_hazard_trace": {}, "pmcf_plan_control_matrix": {}}
        br = build_benefit_risk_body_section(state, body)
        assert br["benefit_risk_body_section"]["section_present"] is True
        assert br["unqualified_favourable_allowed"] is False

    def test_missing_elements_tracked(self):
        br = build_benefit_risk_body_section({}, "")
        assert len(br["missing_elements"]) >= 3

    def test_full_support_allows_controlled_positive(self):
        body = """## 4.8 Benefit-Risk Analysis
        Clinical benefits: 25% reduction in shunt detection failure rate (n=200, p<0.001, 95% CI 18-32%).
        Mapped risks: 12 hazards identified in RMF, all residual risks acceptable per ISO 14971.
        PMS maturity: 3 years of PMS data from 1200 patients; PMCF plan active with 2 ongoing studies.
        The benefit-risk profile is favourable when the device is used per IFU.
        """
        state = {
            "rmf_hazard_trace": {"has_rmf_source": True, "rows": [{"risk_id": "R1"}]},
            "pmcf_plan_control_matrix": {"pmcf_plan_exists": True, "pms_pmcf_source_present": True},
            "benefit_risk_closure_matrix": {"rows": [{"benefit_risk_conclusion_allowed": True}]},
        }
        br = build_benefit_risk_body_section(state, body)
        assert br["unqualified_favourable_allowed"] is True
