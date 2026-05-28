"""WS6: Endpoint Homogeneity Gate Tests."""

from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from deerflow.runtime.cer_authoring.endpoint_homogeneity import (
    build_endpoint_homogeneity_matrix,
    _check_dimension_compatibility,
)


class TestEndpointHomogeneity:
    def test_compatible_single_value(self):
        ok, msg = _check_dimension_compatibility("unit", ["mmHg"])
        assert ok is True
        assert msg == ""

    def test_incompatible_multiple_values(self):
        ok, msg = _check_dimension_compatibility("unit", ["mmHg", "kPa", "%"])
        assert ok is False
        assert "Incompatible" in msg

    def test_empty_list_compatible(self):
        ok, msg = _check_dimension_compatibility("unit", [])
        assert ok is True

    def test_homogeneous_endpoints_pass(self):
        endpoints = [
            {"endpoint_family": "RLS detection rate", "unit": "%", "timepoint": "baseline",
             "population": "PFO patients", "comparator": "c-TTE"},
            {"endpoint_family": "RLS detection rate", "unit": "%", "timepoint": "baseline",
             "population": "PFO patients", "comparator": "c-TTE"},
        ]
        matrix = build_endpoint_homogeneity_matrix(endpoints)
        assert matrix["summary"]["benchmark_derivation_safe"] is True

    def test_heterogeneous_endpoints_downgrade(self):
        endpoints = [
            {"endpoint_family": "shunt grading", "unit": "grade 1-3", "timepoint": "baseline",
             "population": "adults", "comparator": "c-TTE", "measurement_method": "visual"},
            {"endpoint_family": "shunt grading", "unit": "grade 0-4", "timepoint": "6 months",
             "population": "pediatric", "comparator": "c-TCD", "measurement_method": "automated"},
        ]
        matrix = build_endpoint_homogeneity_matrix(endpoints)
        assert matrix["summary"]["conclusion_downgrade_required"] is True

    def test_empty_inputs(self):
        matrix = build_endpoint_homogeneity_matrix([], [])
        assert matrix["summary"]["total_endpoint_families"] == 0

    def test_mixed_homogeneity(self):
        endpoints = [
            {"endpoint_family": "safety_ae_rate", "unit": "%", "timepoint": "30d", "population": "adults", "comparator": "baseline"},
            {"endpoint_family": "safety_ae_rate", "unit": "%", "timepoint": "30d", "population": "adults", "comparator": "baseline"},
            {"endpoint_family": "efficacy_rate", "unit": "%", "timepoint": "12m", "population": "adults", "comparator": "control"},
            {"endpoint_family": "efficacy_rate", "unit": "OR", "timepoint": "6m", "population": "pediatric", "comparator": "placebo"},
        ]
        matrix = build_endpoint_homogeneity_matrix(endpoints)
        assert matrix["summary"]["homogeneous_count"] >= 1
        assert matrix["summary"]["heterogeneous_count"] >= 1

    def test_downgrade_required_for_heterogeneous(self):
        endpoints = [
            {"endpoint_family": "mortality", "unit": "%", "timepoint": "30d", "population": "adults", "comparator": "control"},
            {"endpoint_family": "mortality", "unit": "HR", "timepoint": "1y", "population": "elderly", "comparator": "placebo"},
        ]
        matrix = build_endpoint_homogeneity_matrix(endpoints)
        assert matrix["summary"]["conclusion_downgrade_required"] is True
        assert len(matrix["summary"]["downgraded_families"]) >= 1
