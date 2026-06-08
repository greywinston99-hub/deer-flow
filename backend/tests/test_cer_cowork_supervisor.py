"""Tests for Claude Cowork CER unified supervisor wrapper."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "cer_cowork_supervisor.py"


def load_supervisor():
    spec = importlib.util.spec_from_file_location("cer_cowork_supervisor", SCRIPT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_cer_command_and_skill_define_first_decision_question():
    command = (REPO_ROOT / ".claude" / "commands" / "cer.md").read_text(encoding="utf-8")
    skill = (REPO_ROOT / ".claude" / "skills" / "cer-cowork-supervisor" / "SKILL.md").read_text(encoding="utf-8")

    assert "Please choose: CER Authoring or CER Review?" in command
    assert "Please choose: CER Authoring or CER Review?" in skill
    assert "--strict-v7" in command
    assert "stable-1plus6" in skill
    assert "fulltext-ingest" in skill
    assert "20-40" in skill
    assert "docx-beautifier" in skill
    assert (REPO_ROOT / ".claude" / "skills" / "docx-beautifier" / "SKILL.md").exists()


def test_authoring_dry_run_builds_strict_1plus6_command(tmp_path, monkeypatch):
    supervisor = load_supervisor()
    monkeypatch.setattr(supervisor, "COWORK_ROOT", tmp_path / "cowork")
    source = tmp_path / "source"
    source.mkdir()
    (source / "IFU.docx").write_text("IFU", encoding="utf-8")

    rc = supervisor.main(
        [
            "authoring-start",
            "--project-id",
            "TEST-AUTHORING",
            "--input-root",
            str(source),
            "--target-keywords",
            "Fixture Device",
            "--run-id",
            "dry",
            "--dry-run",
        ]
    )

    assert rc == 0
    run_dir = tmp_path / "cowork" / "TEST-AUTHORING" / "authoring" / "dry"
    command = (run_dir / "command.sh").read_text(encoding="utf-8")
    status = json.loads((run_dir / "status.json").read_text(encoding="utf-8"))
    assert "run_cer_authoring.py" in command
    assert "--strict-v7" in command
    assert "stable-1plus6" in command
    assert status["status"] == "dry_run"
    assert status["mode"] == "authoring"


def test_phase0_3_supervisor_ifu_detection_patterns(tmp_path):
    supervisor = load_supervisor()
    paths = [
        tmp_path / "01_IFU" / "TF-TLC-0301_IFU-Ligating clips(Ti).docx",
        tmp_path / "01_IFU" / "ifu_lowercase.docx",
        tmp_path / "01_IFU" / "IFU_UPPERCASE.docx",
        tmp_path / "01_IFU" / "Mixed_IfU_Name.docx",
        tmp_path / "中文" / "产品使用说明书.docx",
        tmp_path / "中文" / "产品说明书.docx",
        tmp_path / "01_IFU" / "TF-TLC-0301 Ligating clips Ti.docx",
    ]
    for path in paths:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fixture", encoding="utf-8")

    for path in paths:
        assert supervisor.infer_doc_type(path) == "IFU"


def test_phase0_3_supervisor_locked_final_ifu_not_counted_as_ifu(tmp_path):
    supervisor = load_supervisor()
    locked = tmp_path / "03_FINAL_CERTIFIED_PACKAGE_LOCKED" / "01_IFU" / "FINAL_IFU.docx"
    locked.parent.mkdir(parents=True)
    locked.write_text("locked", encoding="utf-8")

    assert supervisor.infer_doc_type(locked) == "Locked_Delta_Only"
    assert supervisor.has_doc_type(tmp_path, "IFU") is False


def test_review_dry_run_generates_project_profile_and_review_command(tmp_path, monkeypatch):
    supervisor = load_supervisor()
    monkeypatch.setattr(supervisor, "COWORK_ROOT", tmp_path / "cowork")
    source = tmp_path / "review_source"
    source.mkdir()
    (source / "Clinical evaluation report.docx").write_text("CER", encoding="utf-8")
    (source / "IFU.docx").write_text("IFU", encoding="utf-8")

    rc = supervisor.main(
        [
            "review-start",
            "--project-id",
            "TEST-REVIEW",
            "--input-root",
            str(source),
            "--run-id",
            "dry",
            "--dry-run",
        ]
    )

    assert rc == 0
    run_dir = tmp_path / "cowork" / "TEST-REVIEW" / "review" / "dry"
    command = (run_dir / "command.sh").read_text(encoding="utf-8")
    profile = json.loads((run_dir / "generated_project_profile.yaml").read_text(encoding="utf-8"))
    doc_types = {doc["doc_type"] for doc in profile["input_package"]["documents"]}
    assert "cer_review_runner.py" in command
    assert "formal-review" in command
    assert "run_cer_authoring.py" not in command
    assert {"CER", "IFU"}.issubset(doc_types)


def test_authoring_postflight_blocks_chinese_and_short_report(tmp_path):
    supervisor = load_supervisor()
    run_dir = tmp_path / "run"
    artifact_root = run_dir / "deerflow_authoring"
    artifact_root.mkdir(parents=True)
    (artifact_root / "CER_draft.md").write_text("This is a short CER draft with 中文 content.", encoding="utf-8")
    supervisor.write_json(
        run_dir / "status.json",
        {"mode": "authoring", "project_id": "TEST", "artifact_root": str(artifact_root), "status": "completed"},
    )

    rc = supervisor.main(["postflight", "--run-dir", str(run_dir)])

    status = json.loads((run_dir / "status.json").read_text(encoding="utf-8"))
    assert rc == 2
    assert status["final_status"] == "REWORK_REQUIRED"
    assert any("English" in issue for issue in status["issues"])
    assert any("word count" in issue for issue in status["issues"])


def test_review_postflight_blocks_terminal_verdict_terms(tmp_path):
    supervisor = load_supervisor()
    run_dir = tmp_path / "review"
    artifact_root = run_dir / "deerflow_review"
    artifact_root.mkdir(parents=True)
    (artifact_root / "review_package.md").write_text("Final verdict: APPROVED. Evidence source: CER. Severity: HIGH.", encoding="utf-8")
    supervisor.write_json(
        run_dir / "status.json",
        {"mode": "review", "project_id": "TEST", "artifact_root": str(artifact_root), "status": "completed"},
    )

    rc = supervisor.main(["postflight", "--run-dir", str(run_dir)])

    status = json.loads((run_dir / "status.json").read_text(encoding="utf-8"))
    assert rc == 2
    assert status["final_status"] == "REWORK_REQUIRED"
    assert any("prohibited terminal verdict" in issue for issue in status["issues"])


def test_postflight_classifies_xml_tool_call_as_runtime_protocol_failure(tmp_path):
    supervisor = load_supervisor()
    run_dir = tmp_path / "review-protocol"
    run_dir.mkdir()
    (run_dir / "stderr.log").write_text(
        'assistant emitted <function_calls><invoke name="search_cer_sections"></invoke></function_calls>',
        encoding="utf-8",
    )
    supervisor.write_json(
        run_dir / "status.json",
        {"mode": "review", "project_id": "TEST", "status": "completed_with_nonzero_exit", "returncode": 1},
    )

    rc = supervisor.main(["postflight", "--run-dir", str(run_dir)])

    status = json.loads((run_dir / "status.json").read_text(encoding="utf-8"))
    assert rc == 2
    assert status["final_status"] == "EXECUTION_FAILED"
    assert any("DEERFLOW_RUNTIME_PROTOCOL_FAILED" in issue for issue in status["issues"])


def _make_authoring_baseline(supervisor, run_dir: Path) -> Path:
    artifact_root = run_dir / "deerflow_authoring"
    artifact_root.mkdir(parents=True)
    for name in supervisor.CORE_AUTHORING_ARTIFACTS:
        path = artifact_root / name
        if name.endswith(".json"):
            path.write_text("{}\n", encoding="utf-8")
        elif name.endswith(".md"):
            path.write_text("", encoding="utf-8")
        else:
            path.write_text("placeholder", encoding="utf-8")
    workbook = {
        "source_role_report": {"status": "PASS"},
        "device_identity_lock": {"status": "PASS", "locked_domain": "urology_nephroscope"},
        "domain_contamination_report": {"status": "PASS", "findings": []},
        "claim_ledger": [{"claim_id": "C-01", "claim_type": "performance"}],
        "cep_pico_matrix": [
            {
                "pico_id": "PICO-01",
                "claim_id": "C-01",
                "population": "urology patients",
                "intervention": "subject device",
                "outcome": "visualization and safety",
                "derivation_rationale": "IFU claim -> clinical uncertainty -> PICO -> concepts -> query",
            }
        ],
        "search_run_registry": [
            {"search_id": "SEARCH-01", "database": "PubMed", "result_count": 1000},
            {"search_id": "SEARCH-02", "database": "Europe PMC", "result_count": 20},
            {"search_id": "SEARCH-02B", "database": "ClinicalTrials.gov", "result_count": 3},
            {"search_id": "SEARCH-02C", "database": "EU Clinical Trials Register", "result_count": None, "status": "source_unavailable"},
            {"search_id": "SEARCH-03", "database": "Embase", "result_count": None, "status": "auth_required"},
            {"search_id": "SEARCH-04", "database": "Cochrane Library", "result_count": None, "status": "auth_required"},
        ],
        "literature_search_protocol_profile": {"research_question_formulation": "IFU claim -> uncertainty -> PICO -> query -> appraisal -> benchmark"},
        "sota_pico_strategy": [{"row_id": "SOTA-PICO-001", "purpose": "SOTA", "population": "urology patients", "intervention": "endoscopic procedure", "comparator": "standard practice", "outcome": "safety/performance", "query": "fixture", "rationale": "fixture"}],
        "due_pico_strategy": [{"row_id": "DUE-PICO-001", "purpose": "Device under Evaluation", "population": "urology patients", "intervention": "Fixture Device", "comparator": "similar device", "outcome": "safety/performance", "query": "Fixture Device", "rationale": "fixture"}],
        "database_search_source_table": [
            {"row_id": "DB-001", "search_id": "SEARCH-01", "database": "PubMed", "purpose": "SOTA", "search_date": "2026-05-08", "query": "fixture", "status": "ok"},
            {"row_id": "DB-002", "search_id": "SEARCH-02", "database": "Europe PMC", "purpose": "SOTA", "search_date": "2026-05-08", "query": "fixture", "status": "ok"},
            {"row_id": "DB-002B", "search_id": "SEARCH-02B", "database": "ClinicalTrials.gov", "purpose": "SOTA", "search_date": "2026-05-08", "query": "fixture", "status": "ok"},
            {"row_id": "DB-002C", "search_id": "SEARCH-02C", "database": "EU Clinical Trials Register", "purpose": "SOTA", "search_date": "2026-05-08", "query": "fixture", "status": "source_unavailable"},
            {"row_id": "DB-003", "search_id": "SEARCH-03", "database": "Embase", "purpose": "SOTA", "search_date": "2026-05-08", "query": "fixture", "status": "auth_required"},
            {"row_id": "DB-004", "search_id": "SEARCH-04", "database": "Cochrane Library", "purpose": "SOTA", "search_date": "2026-05-08", "query": "fixture", "status": "auth_required"},
        ],
        "literature_defined_limits": [{"row_id": "LIMIT-001", "parameter": "language", "default": "no language exclusion"}],
        "literature_flow_registry": [{"row_id": "FLOW-001", "search_id": "SEARCH-01", "database": "PubMed", "objective": "SOTA", "included_count": 1, "status": "ok"}],
        "protocol_deviation_log": [{"deviation_id": "DEV-001", "search_id": "SEARCH-EMBASE", "database": "Embase", "deviation_type": "source_access_limitation", "description": "auth required", "impact": "limited", "control": "request access"}],
        "prisma_flow_data": {
            "identification": {"database_records": 1023, "returned_records": 24, "source_limitation_records": 3},
            "screening": {"deduplicated_records": 24, "title_abstract_screened": 1, "title_abstract_excluded": 0, "full_text_assessed": 1, "full_text_excluded": 0},
            "included": {"sota_included": 1, "due_included": 0, "total_included": 1},
        },
        "prisma_flow_diagram": {"mermaid": "flowchart TD\nA[Identification] --> B[Screening] --> C[Included]"},
        "sota_search_strategy_table": [{"row_id": "STR-001", "search_id": "SEARCH-01", "database": "PubMed", "purpose": "SOTA", "query": "fixture", "result_count": 1000, "screening_use": "benchmark", "conclusion": "fixture"}],
        "sota_screening_disposition_table": [{"row_id": "SOTA-SCR-001", "screen_id": "SCR-001", "article_id": "ART-001", "search_id": "SEARCH-01", "title": "Fixture article", "title_abstract_decision": "include", "full_text_decision": "include_for_appraisal", "purpose": "SOTA screening", "conclusion": "accepted"}],
        "sota_ck_appraisal_table": [{"row_id": "SOTA-CK-001", "article_id": "ART-001", "search_id": "SEARCH-01", "title": "Fixture article", "score": 7, "disposition": "accepted", "evidence_category": "clinical_study", "evidence_hierarchy": "moderate_or_supportive", "endpoint_contribution": "benchmark", "clinical_relevance": "fixture", "evidence_use": "benchmark", "limitation": "full text required"}],
        "alternative_treatment_benchmark_table": [{"row_id": "ALT-001", "option": "standard practice", "benchmark_use": "comparator", "conclusion": "fixture"}],
        "guideline_pathway_table": [{"row_id": "GL-001", "guideline_or_source": "fixture guideline", "pathway": "clinical pathway", "endpoint_relevance": "fixture", "device_positioning_impact": "fixture", "conclusion": "fixture"}],
        "similar_benchmark_device_table": [{"row_id": "SBD-001", "device_class": "similar device", "evidence_use": "benchmark", "limitation": "fixture", "conclusion": "fixture"}],
        "hazard_source_table": [{"row_id": "HZ-001", "hazard_source": "procedure", "hazard_family": "hazard", "sota_use": "risk benchmark", "conclusion": "fixture"}],
        "sota_to_47_usage_matrix": [{"row_id": "S47-001", "benchmark_id": "BM-01", "endpoint": "fixture", "section_4_7_use": "4.7 comparison", "used_in_4_7": True, "conclusion": "fixture"}],
        "similar_device_four_step_confirmation": [
            {"row_id": "SIM-STEP-001", "step": "Step 1 - European market verification", "source": "EUDAMED", "execution_record": "fixture", "required_evidence": "market source", "status": "source_limited", "conclusion": "fixture"},
            {"row_id": "SIM-STEP-002", "step": "Step 2 - Trade name and manufacturer identification", "source": "GUDID", "execution_record": "fixture", "required_evidence": "trade name source", "status": "recorded", "conclusion": "fixture"},
            {"row_id": "SIM-STEP-003", "step": "Step 3 - Technical parameter comparison", "source": "equivalence_matrix", "execution_record": "fixture", "required_evidence": "specification", "status": "conditional", "conclusion": "fixture"},
            {"row_id": "SIM-STEP-004", "step": "Step 4 - Attachment package index", "source": "similar_device_attachment_index", "execution_record": "fixture", "required_evidence": "attachments", "status": "generated", "conclusion": "fixture"},
        ],
        "similar_device_attachment_index": [
            {"attachment_id": f"ATT-SIM-{idx:03d}", "required_document": "fixture source", "use_in_cer": "similar-device evidence control", "if_missing": "downgrade conclusion or request source"}
            for idx in range(1, 11)
        ],
        "sota_literature_quantity_justification": {
            "search_exhaustion_rationale": "fixture search exhaustion",
            "database_limitations": "fixture database limitation",
            "screening_rationale": "fixture screening rationale",
            "evidence_gap_control": "fixture evidence gap control",
            "clinical_impact": "fixture clinical impact",
        },
        "evidence_registry": [
            {
                "evidence_id": "E-001",
                "article_id": "ART-001",
                "pmid": "12345",
                "title": "Fixture article",
                "weight": "supportive",
                "limitations": "Automated first-pass appraisal; full text required.",
            }
        ],
        "endpoint_extraction": [
            {
                "endpoint_id": "EP-001",
                "evidence_id": "E-001",
                "sample_size": "not extracted from summary",
                "statistical_result": "not extracted from summary",
            }
        ],
        "sota_benchmark_matrix": [{"benchmark_id": "BM-01", "used_in_4_7": True}],
        "vigilance_recall_registry": [
            {"database": "FDA MAUDE", "search_terms": "trade name"},
            {"database": "FDA Device Recall", "search_terms": "trade name"},
            {"database": "EUDAMED vigilance", "search_terms": "trade name", "raw_status": "source_unavailable"},
            {"database": "New Zealand Medsafe", "search_terms": "trade name", "raw_status": "source_unavailable"},
        ],
        "vigilance_event_statistics": [{"row_id": "VES-001", "database": "EUDAMED vigilance", "result_count": 0, "relevant_count": 0, "event_categories": "source limited", "risk_trace_link": "R-001", "status": "source_unavailable", "conclusion": "fixture"}],
        "marketing_pms_customer_questionnaire": [
            {"row_id": f"MQ-{idx:03d}", "customer_question": "fixture question", "cer_use": "marketing/PMS closure", "rationale": "fixture", "status": "requested"}
            for idx in range(1, 11)
        ],
        "risk_trace_matrix": [{"risk_id": "R-001", "rmf_coverage": "requires RMF source review"}],
        "gspr_coverage": [{"gspr_id": "GSPR-1", "claim_id": "C-01"}],
    }
    (artifact_root / "authoring_workbook.json").write_text(json.dumps(workbook), encoding="utf-8")
    (artifact_root / "CER_draft.md").write_text(
        "# Clinical Evaluation Report\n\n"
        "Claim C-01 is linked to PICO-01 and Evidence E-001. "
        "Ifu risk warning was extracted from an original-language source and is summarized in English in the CER; "
        "the original wording remains traceable in the controlled workbook.\n",
        encoding="utf-8",
    )
    (artifact_root / "qa_gate_report.json").write_text(json.dumps({"decision": "PASS_TO_DRAFT_DOCX", "failed_gate_count": 0}), encoding="utf-8")
    (artifact_root / "final_gate_closure_report.json").write_text(json.dumps({"decision": "PASS_TO_DRAFT_DOCX"}), encoding="utf-8")
    supervisor.write_json(
        run_dir / "status.json",
        {"mode": "authoring", "project_id": "TEST", "artifact_root": str(artifact_root), "status": "postflight_completed"},
    )
    return artifact_root


def test_claude_repair_loop_writes_separate_repair_package(tmp_path):
    supervisor = load_supervisor()
    run_dir = tmp_path / "run"
    artifact_root = _make_authoring_baseline(supervisor, run_dir)
    baseline_text = (artifact_root / "CER_draft.md").read_text(encoding="utf-8")

    assert supervisor.main(["deep-postflight", "--run-dir", str(run_dir)]) == 0
    assert supervisor.main(["classify-rework", "--run-dir", str(run_dir)]) == 0
    assert supervisor.main(["pico-loop", "--run-dir", str(run_dir)]) == 0
    assert supervisor.main(["fulltext-request", "--run-dir", str(run_dir)]) == 0
    assert supervisor.main(["controlled-patch", "--run-dir", str(run_dir)]) == 0
    assert supervisor.main(["consistency-gate", "--run-dir", str(run_dir)]) == 0
    assert supervisor.main(["finalize-package", "--run-dir", str(run_dir), "--beautify-docx"]) == 2

    repair = run_dir / "claude_repair"
    expected = {
        "deep_postflight_report.json",
        "rework_decision.json",
        "pico_revision_log.xlsx",
        "full_text_request_list.xlsx",
        "evidence_gap_register.xlsx",
        "enhanced_authoring_workbook.json",
        "section_patch_manifest.json",
        "CER_draft_patched.md",
        "CER_draft_patched.docx",
        "CER_draft_final_beautified.docx",
        "docx_beautification_report.json",
        "patch_qa_report.json",
        "final_closeout_report.json",
        "cer_self_check_scorecard.json",
        "cer_self_check_scorecard.xlsx",
        "nb_flag_triage.xlsx",
        "pico_v2_strategy.xlsx",
        "risk_benefit_closure_matrix.xlsx",
        "pmcf_timetable_request.xlsx",
    }
    assert expected.issubset({path.name for path in repair.iterdir()})
    assert (artifact_root / "CER_draft.md").read_text(encoding="utf-8") == baseline_text
    patched = (repair / "CER_draft_patched.md").read_text(encoding="utf-8")
    assert "Ifu risk warning was extracted" not in patched
    decision = json.loads((repair / "rework_decision.json").read_text(encoding="utf-8"))
    assert decision["decision"] == "EVIDENCE_ENHANCEMENT_REQUIRED"
    deep = json.loads((repair / "deep_postflight_report.json").read_text(encoding="utf-8"))
    assert "engineer_comment_theme_report" in deep
    assert {row["theme_id"] for row in deep["engineer_comment_theme_report"]} == {
        "theme_1_summary_scope",
        "theme_2_equivalence_logic",
        "theme_3_market_vigilance",
        "theme_4_sota_literature",
        "theme_5_gspr_benefit_risk",
        "theme_6_section_conclusions",
    }
    beautification = json.loads((repair / "docx_beautification_report.json").read_text(encoding="utf-8"))
    assert beautification["decision"] == "PASS"
    final_dir = artifact_root / "final"
    assert (final_dir / "final_manifest.json").exists()
    assert (final_dir / "CER_final.md").exists()
    closeout = json.loads((repair / "final_closeout_report.json").read_text(encoding="utf-8"))
    assert closeout["decision"] == "NOT_DELIVERABLE_REWORK_REQUIRED"


def test_fulltext_ingest_and_sota_enhancement_write_trace_artifacts(tmp_path):
    supervisor = load_supervisor()
    run_dir = tmp_path / "run-fulltext"
    _make_authoring_baseline(supervisor, run_dir)
    fulltext_root = tmp_path / "04_LITERATURE_FULL_TEXT"
    fulltext_root.mkdir()
    (fulltext_root / "Fixture article.txt").write_text(
        "Fixture article. Endpoint clinical success was reported in n=100 patients at 30 days. "
        "The clinical success rate was 95%. Serious adverse events were 2%.",
        encoding="utf-8",
    )

    assert supervisor.main(["fulltext-ingest", "--run-dir", str(run_dir), "--fulltext-root", str(fulltext_root)]) == 0
    assert supervisor.main(["sota-endpoint-enhance", "--run-dir", str(run_dir)]) == 0
    assert supervisor.main(["sota-reasoning-patch", "--run-dir", str(run_dir)]) == 0

    repair = run_dir / "claude_repair"
    assert (repair / "full_text_library_index.xlsx").exists()
    assert (repair / "manual_full_text_source_log.xlsx").exists()
    assert (repair / "full_text_endpoint_extraction.xlsx").exists()
    assert (repair / "sota_endpoint_derivation_table.xlsx").exists()
    assert (repair / "sota_quantitative_benchmark_table.xlsx").exists()
    assert (repair / "sota_benchmark_derivation_narratives.md").exists()
    patched = (repair / "CER_draft_patched.md").read_text(encoding="utf-8")
    assert "Controlled SOTA Endpoint Derivation Addendum" in patched
