from __future__ import annotations

import json
from pathlib import Path
from zipfile import ZipFile

import yaml

from deerflow.runtime.rmf_review import RMFReviewRunner


def _write_minimal_docx(path: Path, *, paragraphs: list[str] | None = None, tables: list[list[list[str]]] | None = None) -> None:
    paragraph_xml = "".join(
        f"<w:p><w:r><w:t>{value}</w:t></w:r></w:p>"
        for value in (paragraphs or [])
    )
    table_xml = ""
    for table in tables or []:
        rows_xml = []
        for row in table:
            cells = "".join(
                f"<w:tc><w:p><w:r><w:t>{value}</w:t></w:r></w:p></w:tc>"
                for value in row
            )
            rows_xml.append(f"<w:tr>{cells}</w:tr>")
        table_xml += f"<w:tbl>{''.join(rows_xml)}</w:tbl>"

    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        "<w:body>"
        f"{paragraph_xml}{table_xml}"
        '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/></w:sectPr>'
        "</w:body>"
        "</w:document>"
    )

    content_types_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        "</Types>"
    )

    rels_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"></Relationships>'
    )

    path.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(path, "w") as archive:
        archive.writestr("[Content_Types].xml", content_types_xml)
        archive.writestr("_rels/.rels", rels_xml)
        archive.writestr("word/document.xml", document_xml)


def _write_project_profile(project_profile_path: Path, input_root: Path) -> None:
    project_profile = {
        "project_id": "demo",
        "project_name": "Demo Project",
        "institution_profile": {
            "organization": "Example Team",
            "assessment_body": "BSI",
            "profile_version": "v1",
        },
        "review_scope": {
            "mode": "single_project_serial_review",
            "review_language": "en",
            "jurisdiction": "EU MDR",
            "human_gate_required": True,
        },
        "primary_review_object": "RMF",
        "device_context": {
            "device_name": "Demo Device",
        },
        "input_package": {
            "root_path": str(input_root),
            "documents": [
                {
                    "doc_type": "RMF",
                    "label": "RMF",
                    "path": str(input_root / "Risk_Management_File.docx"),
                    "required_for_p0": True,
                    "source_ref": {
                        "document_id": "rmf_main",
                        "path": str(input_root / "Risk_Management_File.docx"),
                    },
                },
                {
                    "doc_type": "FMEA",
                    "label": "DFMEA",
                    "path": str(input_root / "Design_DFMEA.docx"),
                    "required_for_p0": True,
                    "source_ref": {
                        "document_id": "dfmea_main",
                        "path": str(input_root / "Design_DFMEA.docx"),
                    },
                },
                {
                    "doc_type": "FMEA",
                    "label": "PFMEA",
                    "path": str(input_root / "Process_PFMEA.docx"),
                    "required_for_p0": False,
                    "source_ref": {
                        "document_id": "pfmea_main",
                        "path": str(input_root / "Process_PFMEA.docx"),
                    },
                },
                {
                    "doc_type": "Hazard_Analysis",
                    "label": "Hazard Analysis",
                    "path": str(input_root / "legacy" / "Hazard_Analysis.xlsx"),
                    "required_for_p0": True,
                    "source_ref": {
                        "document_id": "hazard_main",
                        "path": str(input_root / "legacy" / "Hazard_Analysis.xlsx"),
                    },
                },
                {
                    "doc_type": "IFU",
                    "label": "IFU",
                    "path": str(input_root / "IFU.docx"),
                    "required_for_p0": False,
                    "source_ref": {
                        "document_id": "ifu_main",
                        "path": str(input_root / "IFU.docx"),
                    },
                },
            ],
        },
        "artifact_policy": {
            "artifact_root": "/mnt/user-data/outputs/rmf_review_v1_1/demo",
            "persist_intermediate_artifacts": True,
            "final_outputs": [],
        },
    }
    project_profile_path.write_text(yaml.safe_dump(project_profile, sort_keys=False), encoding="utf-8")


def _build_runner(tmp_path: Path, monkeypatch) -> RMFReviewRunner:
    repo_root = Path("/Users/winstonwei/Documents/Playground/deer-flow")
    deer_home = tmp_path / "deer-home"
    monkeypatch.setenv("DEER_FLOW_HOME", str(deer_home))

    input_root = tmp_path / "inputs"
    input_root.mkdir(parents=True)
    _write_minimal_docx(
        input_root / "Risk_Management_File.docx",
        paragraphs=[
            "Demo Device 风险管理报告",
            "本报告包含风险分析、风险控制、综合剩余风险评价。",
            "生产和生产后信息应持续收集。",
        ],
    )
    _write_minimal_docx(
        input_root / "Design_DFMEA.docx",
        tables=[
            [
                ["Risk ID", "Failure Mode", "Effect", "Cause", "Severity", "Occurrence", "Detection", "RPN", "Current Control"],
                ["R-001", "Seal failure", "Leakage", "Poor weld", "5", "3", "2", "30", "100% leak test"],
            ]
        ],
    )
    _write_minimal_docx(
        input_root / "Process_PFMEA.docx",
        tables=[
            [
                ["Failure Mode", "Effect", "Cause", "Severity", "Occurrence", "Detection"],
                ["Assembly error", "Loose fit", "Operator variation", "4", "2", "3"],
            ]
        ],
    )
    _write_minimal_docx(
        input_root / "IFU.docx",
        paragraphs=["Demo Device 使用说明书"],
    )

    project_profile_path = tmp_path / "project_profile.yaml"
    _write_project_profile(project_profile_path, input_root)

    return RMFReviewRunner(
        repo_root=repo_root,
        workflow_path=repo_root / "workflows" / "rmf_review_v1_1.yaml",
        project_profile_path=project_profile_path,
        input_root=input_root,
        thread_id="rmf-smoke-test",
    )


def test_rmf_review_smoke_run_executes_first_five_steps_and_writes_dimension_artifacts(tmp_path, monkeypatch):
    runner = _build_runner(tmp_path, monkeypatch)
    result = runner.run(mode="smoke-run")

    artifact_root = Path(result.artifact_root_actual)
    assessment = json.loads((artifact_root / "04_dimension_review" / "dimension_assessment.json").read_text(encoding="utf-8"))

    assert result.executed_steps == [
        "rmf_intake_agent",
        "rmf_parse_normalize_agent",
        "fmea_precheck_agent",
        "rmf_precheck_agent",
        "rmf_dimension_review_agent",
        "rmf_human_boundary_agent",
        "rmf_report_agent",
        "rmf_gate_closure_agent",
    ]
    assert (artifact_root / "04_dimension_review" / "dimension_review_report.md").exists()
    assert set(assessment["dimensions"].keys()) == {"COMP", "CORR", "ADEQ", "TRAC", "CONS", "ACPT"}


def test_dimension_results_are_non_empty_and_not_all_supported(tmp_path, monkeypatch):
    runner = _build_runner(tmp_path, monkeypatch)
    result = runner.run(mode="smoke-run")

    artifact_root = Path(result.artifact_root_actual)
    assessment = json.loads((artifact_root / "04_dimension_review" / "dimension_assessment.json").read_text(encoding="utf-8"))
    statuses = {key: value["status"] for key, value in assessment["dimensions"].items()}

    assert all(assessment["dimensions"][key]["evidence_hints"] or assessment["dimensions"][key]["findings"] for key in assessment["dimensions"])
    assert any(status != "supported" for status in statuses.values())
    assert assessment["global_manual_review_needed"] is True


def test_hazard_analysis_missing_is_not_blocking_when_pfmea_exists(tmp_path, monkeypatch):
    runner = _build_runner(tmp_path, monkeypatch)
    result = runner.run(mode="smoke-run")

    artifact_root = Path(result.artifact_root_actual)
    inventory = json.loads((artifact_root / "00_manifest" / "input_inventory.json").read_text(encoding="utf-8"))
    run_manifest = json.loads((artifact_root / "00_manifest" / "run_manifest.json").read_text(encoding="utf-8"))
    missing_report = (artifact_root / "00_manifest" / "missing_items_report.md").read_text(encoding="utf-8")

    hazard_item = next(item for item in inventory["documents"] if item["doc_type"] == "Hazard_Analysis")

    assert hazard_item["status"] == "aliased_to_fmea"
    assert hazard_item["blocking_for_p0"] is False
    assert hazard_item["alias_target_document_id"] == "pfmea_main"
    assert run_manifest["hazard_resolution"]["resolution_mode"] == "alias_to_pfmea"
    assert run_manifest["fmea_status"]["hazard_analysis_present"] is True
    assert "Required Missing Count: `0`" in missing_report


def test_seventh_node_produces_final_artifacts_and_preserves_human_boundary(tmp_path, monkeypatch):
    runner = _build_runner(tmp_path, monkeypatch)
    result = runner.run(mode="smoke-run")

    artifact_root = Path(result.artifact_root_actual)

    # Node 7 artifacts exist
    assert (artifact_root / "06_final" / "final_report.md").exists()
    assert (artifact_root / "06_final" / "final_report.json").exists()
    assert (artifact_root / "06_final" / "capa_action_list.json").exists()
    assert (artifact_root / "06_final" / "backflow_candidates.json").exists()

    # final_report.json content checks
    final_json = json.loads((artifact_root / "06_final" / "final_report.json").read_text(encoding="utf-8"))
    assert final_json["step_id"] == "rmf_report_agent"
    assert "recommended_gate" in final_json
    assert final_json["final_gate_status"] == "pending_human_confirmation"
    assert "MACHINE-GENERATED RECOMMENDATION ONLY" in final_json["gate_caveat"]
    assert final_json["human_gate_required"] is True
    assert "executive_summary" in final_json
    assert "capa_action_list" in final_json
    assert "backflow_candidates" in final_json

    # capa_action_list is non-empty
    capa = json.loads((artifact_root / "06_final" / "capa_action_list.json").read_text(encoding="utf-8"))
    assert isinstance(capa, list)
    assert len(capa) > 0
    assert any("source" in item for item in capa)

    # backflow_candidates is non-empty
    backflow = json.loads((artifact_root / "06_final" / "backflow_candidates.json").read_text(encoding="utf-8"))
    assert isinstance(backflow, list)
    assert len(backflow) > 0
    assert any("pattern_type" in item for item in backflow)

    # human boundary is preserved in final report
    hrb = json.loads((artifact_root / "05_human_boundary" / "human_review_queue.json").read_text(encoding="utf-8"))
    assert len(hrb["items"]) > 0
    assert hrb["recommended_gate"] in ("pass", "conditional_pass", "rework_required")

    # provisional_gate preserves human decision required flag
    prov_gate = json.loads((artifact_root / "05_human_boundary" / "provisional_gate_recommendation.json").read_text(encoding="utf-8"))
    assert prov_gate.get("human_decision_required") is True
    assert prov_gate.get("provisional_only") is True
    assert "does not constitute" in prov_gate.get("caveat", "")


def test_gate_closure_produces_closure_artifacts_and_next_action_packet(tmp_path, monkeypatch):
    runner = _build_runner(tmp_path, monkeypatch)
    result = runner.run(mode="smoke-run")

    artifact_root = Path(result.artifact_root_actual)

    # Node 8 artifacts exist
    assert (artifact_root / "07_gate_closure" / "gate_closure_report.md").exists()
    assert (artifact_root / "07_gate_closure" / "gate_closure_report.json").exists()
    assert (artifact_root / "07_gate_closure" / "next_action_packet.json").exists()

    # human_gate_decision was auto-written
    assert (artifact_root / "05_human_boundary" / "human_gate_decision.json").exists()

    # gate_closure_report.json checks
    closure_json = json.loads((artifact_root / "07_gate_closure" / "gate_closure_report.json").read_text(encoding="utf-8"))
    assert closure_json["step_id"] == "rmf_gate_closure_agent"
    assert "human_decision" in closure_json
    assert closure_json["final_decision"] in ("pass", "conditional_pass", "rework_required")
    assert closure_json["human_gate_required"] is True
    assert "next_action_packet" in closure_json

    # next_action_packet checks
    nap = json.loads((artifact_root / "07_gate_closure" / "next_action_packet.json").read_text(encoding="utf-8"))
    assert nap["packet_type"] in ("archive", "condition_tracking", "rework")
    assert nap["decision"] in ("pass", "conditional_pass", "rework_required")
    assert isinstance(nap["actions"], list)
    assert len(nap["actions"]) > 0
    assert all("action_id" in a and "type" in a for a in nap["actions"])
