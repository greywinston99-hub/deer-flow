from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
ANALYZER = REPO_ROOT / "scripts" / "calibration_delta_analyzer.py"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _fixture(tmp_path: Path) -> dict[str, Path]:
    baseline = tmp_path / "baseline_frozen"
    writer_input = tmp_path / "01_INITIAL_INPUT_FOR_WRITER"
    nb_locked = tmp_path / "02_NB_ROUNDS_AND_RESPONSES_LOCKED"
    final_locked = tmp_path / "03_FINAL_CERTIFIED_PACKAGE_LOCKED"
    output = tmp_path / "delta_analysis"
    for path in (baseline, writer_input, nb_locked, final_locked, output):
        path.mkdir(parents=True, exist_ok=True)

    _write_json(
        baseline / "authoring_workbook.json",
        {
            "claim_ledger": [{"claim_id": "CLAIM-001"}],
            "cep_pico_matrix": [{"pico_id": "PICO-001"}],
            "sota_benchmark_matrix": [{"benchmark_id": "BM-001"}],
            "evidence_registry": [{"evidence_id": "E-001"}],
            "endpoint_extraction": [{"endpoint_id": "END-001"}],
            "risk_trace_matrix": [{"risk_id": "RISK-001"}],
        },
    )
    _write_json(
        baseline / "qa_gate_report.json",
        {
            "results": [
                {"gate_id": "G30", "status": "FAIL", "message": "SOTA endpoint derivation missing", "severity": "high"},
                {"gate_id": "G1", "status": "PASS", "message": "ok"},
            ]
        },
    )
    (writer_input / "IFU.txt").write_text("subject IFU input", encoding="utf-8")
    (nb_locked / "Round1_NB_LoQ.txt").write_text("NB deficiency about SOTA benchmark", encoding="utf-8")
    (nb_locked / "manufacturer_response_matrix.csv").write_text("response,action\nreply,accepted\n", encoding="utf-8")
    (nb_locked / "submitted_supporting_file.pdf").write_bytes(b"%PDF-1.4 fake")
    (nb_locked / "unclassified_material.bin").write_bytes(b"\x00\x01unknown")
    (final_locked / "FINAL_CER_CERTIFIED.txt").write_text(
        "\n".join(
            [
                "3 State of the Art",
                "Endpoint | Benchmark value | Source | Population",
                "Technical success | 95% | PMID: 12345678 | n=120",
                "The final CER uses a SOTA benchmark endpoint for SOTA benchmark derivation with PMID: 12345678 and CI not reported.",
                "4 Clinical Evidence",
                "The final evidence appraisal identifies one pivotal randomized study, n=120, with supportive literature.",
                "5 Benefit-Risk Conclusion",
                "The final benefit-risk conclusion states that residual risks are acceptable when compared with the benchmark.",
            ]
        ),
        encoding="utf-8",
    )
    return {
        "baseline": baseline,
        "authoring_workbook": baseline / "authoring_workbook.json",
        "qa_gate_report": baseline / "qa_gate_report.json",
        "writer_input": writer_input,
        "nb_locked": nb_locked,
        "final_locked": final_locked,
        "output": output,
    }


def test_locked_delta_analyzer_outputs_tables_and_access_log(tmp_path: Path) -> None:
    fx = _fixture(tmp_path)
    baseline_hashes = {path: _sha(path) for path in fx["baseline"].rglob("*") if path.is_file()}
    writer_hashes = {path: _sha(path) for path in fx["writer_input"].rglob("*") if path.is_file()}

    result = subprocess.run(
        [
            sys.executable,
            str(ANALYZER),
            "--baseline-root",
            str(fx["baseline"]),
            "--authoring-workbook",
            str(fx["authoring_workbook"]),
            "--qa-gate-report",
            str(fx["qa_gate_report"]),
            "--nb-locked-root",
            str(fx["nb_locked"]),
            "--final-locked-root",
            str(fx["final_locked"]),
            "--output-dir",
            str(fx["output"]),
            "--json",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr

    expected_tables = {
        "CLAIM_DELTA_TABLE.csv",
        "SOTA_BENCHMARK_DELTA_TABLE.csv",
        "EVIDENCE_SELECTION_DELTA_TABLE.csv",
        "EVIDENCE_APPRAISAL_DELTA_TABLE.csv",
        "CLAIM_EVIDENCE_DELTA_MATRIX.csv",
        "PMCF_BOUNDARY_DELTA_TABLE.csv",
        "ALIGNMENT_DELTA_TABLE.csv",
        "CEAR_DEFICIENCY_PATTERN_TABLE.csv",
    }
    assert expected_tables.issubset({path.name for path in fx["output"].iterdir()})
    assert (fx["output"] / "DELTA_ANALYSIS_MANIFEST.json").exists()
    assert (fx["output"] / "semantic_delta_manifest.json").exists()
    assert (fx["output"] / "semantic_delta_case_summary.md").exists()
    assert (fx["output"] / "low_confidence_review_queue.csv").exists()
    assert (fx["output"] / "low_confidence_root_cause_breakdown.csv").exists()
    assert (fx["output"] / "gold_reference_extraction_manifest.json").exists()
    assert (fx["output"] / "gold_reference_section_index.csv").exists()
    assert (fx["output"] / "gold_reference_table_index.csv").exists()
    assert (fx["output"] / "gold_reference_citation_index.csv").exists()
    assert (fx["output"] / "entity_normalization_dictionary.csv").exists()
    assert (fx["output"] / "entity_alias_mapping_table.csv").exists()
    assert (fx["output"] / "entity_normalization_provenance.csv").exists()
    assert (fx["output"] / "entity_normalization_resolved_items.csv").exists()
    assert (fx["output"] / "gold_reference_table_extraction_manifest.json").exists()
    assert (fx["output"] / "gold_reference_table_type_index.csv").exists()
    assert (fx["output"] / "gold_reference_table_cell_anchor_index.csv").exists()
    assert (fx["output"] / "table_extraction_failure_log.csv").exists()
    assert (fx["output"] / "sota_benchmark_candidate_ranking_table.csv").exists()
    assert (fx["output"] / "sota_benchmark_reranking_explanation_table.csv").exists()
    assert (fx["output"] / "true_ambiguity_sampling_audit.csv").exists()
    assert (fx["output"] / "true_ambiguity_reclassification_report.md").exists()
    assert (fx["output"] / "nb_to_final_resolution_link_table.csv").exists()
    assert (fx["output"] / "ai_gap_to_nb_finding_link_table.csv").exists()
    assert (fx["output"] / "LOCKED_ACCESS_LOG.csv").exists()
    assert (fx["output"] / "NEEDS_HUMAN_CLASSIFICATION.csv").exists()
    assert (fx["output"] / "PILOT_RUN_REPORT.md").exists()

    manifest = json.loads((fx["output"] / "DELTA_ANALYSIS_MANIFEST.json").read_text(encoding="utf-8"))
    assert manifest["access_policy"]["authoring_writer_may_read_locked_roots"] is False
    assert manifest["access_policy"]["repair_or_finalization_triggered"] is False
    assert manifest["invalidated_prior_run"] == "PROJECT_01_PILOT_INVALID_DUE_TO_LOCKED_ACCESS_LEAKAGE"
    assert manifest["baseline_bump_required_before_project1_rerun"] is True
    assert manifest["semantic_delta_layer"]["enabled"] is True

    semantic_manifest = json.loads((fx["output"] / "semantic_delta_manifest.json").read_text(encoding="utf-8"))
    assert semantic_manifest["status"] == "SEMANTIC_DELTA_COMPLETE"
    assert semantic_manifest["schema_version"] == "phase3.5d-semantic-delta-precision-lift-v1"
    assert semantic_manifest["gold_reference_extraction"]["section_count"] >= 1
    assert semantic_manifest["gold_reference_table_extraction"]["table_count"] >= 1
    assert semantic_manifest["entity_normalization"]["alias_count"] >= 1
    expected_semantic = {
        "claim_semantic_alignment_table.csv",
        "evidence_correspondence_table.csv",
        "sota_benchmark_delta_table.csv",
        "evidence_appraisal_delta_table.csv",
        "pmcf_boundary_delta_table.csv",
        "benefit_risk_reasoning_delta_table.csv",
        "cross_document_alignment_delta_table.csv",
        "nb_relevance_delta_table.csv",
        "cognitive_gap_attribution_table.csv",
    }
    semantic_dir = fx["output"] / "semantic_delta"
    assert expected_semantic.issubset({path.name for path in semantic_dir.iterdir()})
    claim_rows = _read_csv(semantic_dir / "claim_semantic_alignment_table.csv")
    assert claim_rows
    assert {
        "semantic_delta_id",
        "delta_classification",
        "match_confidence",
        "candidate_retrieval_confidence",
        "semantic_equivalence_confidence",
        "clinical_materiality_confidence",
        "root_cause_candidate",
        "ai_side_evidence_span",
        "gold_side_evidence_span",
        "reasoning_why_material",
    }.issubset(claim_rows[0])
    low_breakdown = _read_csv(fx["output"] / "low_confidence_root_cause_breakdown.csv")
    assert {row["low_confidence_type"] for row in low_breakdown} >= {"TEXT_EXTRACTION_GAP", "SEMANTIC_MATCHING_GAP", "TRUE_AMBIGUITY_HUMAN_GATE"}

    access_rows = _read_csv(fx["output"] / "LOCKED_ACCESS_LOG.csv")
    roles = {row["role"] for row in access_rows}
    assert {"NB_FEEDBACK", "OUR_RESPONSE", "SUBMITTED_SUPPORTING_FILE", "FINAL_CHANGE_REFERENCE", "UNKNOWN"}.issubset(roles)
    assert len(access_rows) == 5

    human_rows = _read_csv(fx["output"] / "NEEDS_HUMAN_CLASSIFICATION.csv")
    assert len(human_rows) == 1
    assert human_rows[0]["relative_path"] == "unclassified_material.bin"

    assert baseline_hashes == {path: _sha(path) for path in baseline_hashes}
    assert writer_hashes == {path: _sha(path) for path in writer_hashes}


def test_locked_delta_analyzer_rejects_output_in_writer_or_locked_inputs(tmp_path: Path) -> None:
    fx = _fixture(tmp_path)

    for bad_output in (
        fx["writer_input"] / "delta_analysis",
        fx["nb_locked"] / "delta_analysis",
        fx["final_locked"] / "delta_analysis",
        fx["baseline"] / "delta_analysis",
    ):
        result = subprocess.run(
            [
                sys.executable,
                str(ANALYZER),
                "--baseline-root",
                str(fx["baseline"]),
                "--authoring-workbook",
                str(fx["authoring_workbook"]),
                "--qa-gate-report",
                str(fx["qa_gate_report"]),
                "--nb-locked-root",
                str(fx["nb_locked"]),
                "--final-locked-root",
                str(fx["final_locked"]),
                "--output-dir",
                str(bad_output),
            ],
            text=True,
            capture_output=True,
            check=False,
        )
        assert result.returncode != 0


def test_locked_delta_analyzer_cross_project_semantic_aggregation(tmp_path: Path) -> None:
    case_dirs = []
    for idx in range(2):
        fx = _fixture(tmp_path / f"case_{idx}")
        result = subprocess.run(
            [
                sys.executable,
                str(ANALYZER),
                "--baseline-root",
                str(fx["baseline"]),
                "--authoring-workbook",
                str(fx["authoring_workbook"]),
                "--qa-gate-report",
                str(fx["qa_gate_report"]),
                "--nb-locked-root",
                str(fx["nb_locked"]),
                "--final-locked-root",
                str(fx["final_locked"]),
                "--output-dir",
                str(fx["output"]),
            ],
            text=True,
            capture_output=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        case_dirs.append(fx["output"])

    aggregate = tmp_path / "aggregate"
    command = [sys.executable, str(ANALYZER), "--aggregate-output-dir", str(aggregate)]
    for case_dir in case_dirs:
        command.extend(["--case-output-dir", str(case_dir)])
    result = subprocess.run(command, text=True, capture_output=True, check=False)
    assert result.returncode == 0, result.stderr
    assert (aggregate / "cross_project_semantic_gap_aggregation_report.md").exists()
    assert (aggregate / "cross_project_gap_frequency_matrix.csv").exists()
    assert (aggregate / "semantic_quality_level_preliminary_judgment.md").exists()
    assert (aggregate / "next_upgrade_priority_ranking.csv").exists()
    assert (aggregate / "cross_project_low_confidence_root_cause_report.md").exists()
    assert (aggregate / "cross_project_semantic_match_reliability_report.md").exists()
    assert (aggregate / "calibration_grade_readiness_report.md").exists()
    assert (aggregate / "phase3_5d_before_after_metrics.csv").exists()
    assert (aggregate / "phase3_5d_before_after_metrics_report.md").exists()
