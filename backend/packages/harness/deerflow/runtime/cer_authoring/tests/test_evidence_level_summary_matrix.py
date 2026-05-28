"""WS5: Evidence Level Summary Matrix Tests."""

from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from deerflow.runtime.cer_authoring.evidence_level_matrix import (
    build_evidence_level_summary_matrix,
    _map_oxford_level,
    _classify_role,
)


class TestEvidenceLevelSummaryMatrix:
    def test_map_oxford_rct(self):
        assert _map_oxford_level("rct") == "1b"
        assert _map_oxford_level("randomized controlled trial") == "1b"

    def test_map_oxford_systematic_review(self):
        assert _map_oxford_level("systematic_review_rct") == "1a"

    def test_map_oxford_case_series(self):
        assert _map_oxford_level("case_series") == "4"

    def test_map_oxford_expert_opinion(self):
        assert _map_oxford_level("expert_opinion") == "5"

    def test_classify_pivotal(self):
        ev = {"source_type": "subject_device_clinical_study", "study_design": "rct", "direct_evidence": True, "oxford_level": "1b"}
        role = _classify_role(ev, [])
        assert role == "pivotal"

    def test_classify_background(self):
        ev = {"source_type": "literature_pubmed_sota", "study_design": "narrative_review"}
        role = _classify_role(ev, [])
        assert role == "background"

    def test_classify_excluded(self):
        ev = {"source_type": "unknown_unclassified"}
        role = _classify_role(ev, [])
        assert role == "excluded"

    def test_empty_registry_produces_matrix(self):
        matrix = build_evidence_level_summary_matrix([], [])
        assert matrix["schema"] == "evidence_level_summary_matrix_v1"
        assert matrix["summary"]["total_evidence_sources"] == 0

    def test_pivotal_supportive_classification(self):
        evidence = [
            {"evidence_id": "E1", "source_type": "subject_device_clinical_study", "study_design": "rct", "direct_evidence": True},
            {"evidence_id": "E2", "source_type": "literature_pubmed_sota", "study_design": "prospective_cohort", "direct_evidence": True},
            {"evidence_id": "E3", "source_type": "literature_pubmed_sota", "study_design": "narrative_review"},
        ]
        matrix = build_evidence_level_summary_matrix(evidence, [])
        assert matrix["summary"]["pivotal_count"] >= 1
        assert matrix["summary"]["supportive_count"] + matrix["summary"]["background_count"] >= 1

    def test_overall_ceiling_with_pivotal(self):
        # Pivotal evidence alone → MODERATE (need supportive to reach STRONG)
        evidence = [
            {"evidence_id": "E1", "source_type": "subject_device_clinical_study", "study_design": "rct", "direct_evidence": True},
            {"evidence_id": "E2", "source_type": "subject_device_clinical_study", "study_design": "prospective_cohort", "direct_evidence": True},
        ]
        matrix = build_evidence_level_summary_matrix(evidence, [])
        assert matrix["summary"]["overall_ceiling"] == "MODERATE"

    def test_overall_ceiling_no_evidence(self):
        matrix = build_evidence_level_summary_matrix([], [])
        assert matrix["summary"]["overall_ceiling"] == "INSUFFICIENT"

    def test_claim_linking(self):
        evidence = [{"evidence_id": "E1", "source_type": "subject_device_clinical_study", "study_design": "rct"}]
        claims = [{"claim_id": "C1", "evidence_ids": ["E1"]}]
        matrix = build_evidence_level_summary_matrix(evidence, claims)
        assert "C1" in matrix["rows"][0]["claim_ids_supported"]
