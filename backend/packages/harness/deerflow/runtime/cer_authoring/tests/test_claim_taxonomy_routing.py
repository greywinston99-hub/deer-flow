"""WS3: Claim Taxonomy and Evidence Routing Tests."""

from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from deerflow.runtime.cer_authoring.claim_taxonomy import (
    classify_claim,
    route_claim_evidence,
    build_claim_taxonomy_decision_table,
    CLAIM_CLASSES,
    CLAIM_EVIDENCE_ROUTES,
)


class TestClaimTaxonomy:
    def test_classify_efficacy_benefit(self):
        cls = classify_claim("The device reduces mortality and improves outcomes")
        assert cls == "efficacy_clinical_benefit"

    def test_classify_safety_benefit(self):
        cls = classify_claim("The device is safe with fewer complications and no serious adverse events")
        assert cls == "safety_clinical_benefit"

    def test_classify_ifu_warning(self):
        cls = classify_claim("Warning: Do not use in MRI environment")
        assert cls == "ifu_warning_residual_risk"

    def test_classify_contraindication(self):
        cls = classify_claim("Contraindicated in patients with active bleeding")
        assert cls == "contraindication"

    def test_classify_technical_specification(self):
        cls = classify_claim("Catheter diameter 2.0mm, length 150cm, material polyurethane")
        assert cls == "technical_specification"

    def test_classify_sterility(self):
        cls = classify_claim("EO sterilized, shelf life 3 years")
        assert cls == "sterility_or_shelf_life"

    def test_classify_non_claim_admin(self):
        cls = classify_claim("Package contains 1 catheter and 1 guidewire. Store in cool dry place.")
        assert cls == "non_claim_admin"

    def test_classify_intended_purpose_fallback(self):
        cls = classify_claim("The device is a ureteral access sheath")
        assert cls == "intended_purpose_scope"

    def test_route_ifu_warning_skips_pubmed(self):
        route = route_claim_evidence("ifu_warning_residual_risk")
        assert route["skip_pubmed"] is True
        assert route["require_rmf"] is True

    def test_route_clinical_benefit_requires_direct(self):
        route = route_claim_evidence("efficacy_clinical_benefit")
        assert route["require_direct"] is True
        assert route["min_pivotal"] >= 1

    def test_route_non_claim_admin_skips_all(self):
        route = route_claim_evidence("non_claim_admin")
        assert route["skip_pubmed"] is True
        assert route["skip_sota"] is True

    def test_all_claim_classes_have_routes(self):
        for cls in CLAIM_CLASSES:
            route = route_claim_evidence(cls)
            assert "primary_route" in route, f"Missing route for {cls}"

    def test_taxonomy_table_no_unsupported_in_body(self):
        claims = [
            {"claim_id": "C1", "claim_text": "Reduces mortality", "claim_type": "clinical_benefit"},
            {"claim_id": "C2", "claim_text": "Package contains items", "claim_type": "admin"},
        ]
        result = build_claim_taxonomy_decision_table(claims)
        ineligible = [r for r in result["claim_taxonomy_decision_table"] if not r["final_body_allowed"]]
        assert len(ineligible) == 0

    def test_warning_claims_not_misclassified_as_benefit(self):
        claims = [{"claim_id": "W1", "claim_text": "Warning: Do not use in MRI", "claim_type": "ifu_warning"}]
        result = build_claim_taxonomy_decision_table(claims)
        row = result["claim_taxonomy_decision_table"][0]
        assert row["is_benefit_claim"] is False
        assert row["is_warning"] is True

    def test_intended_purpose_is_not_benefit_claim(self):
        cls = classify_claim("The device is intended for the treatment of pulmonary arterial hypertension")
        assert cls != "efficacy_clinical_benefit"
