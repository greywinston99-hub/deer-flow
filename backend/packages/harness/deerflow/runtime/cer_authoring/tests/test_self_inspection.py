"""Test the repair self-inspection mechanism.

Verifies that build_self_inspection_report() produces a complete report
with all required fields from the Repair Self-Check Checklist (§0-§15).
"""


def test_self_inspection_report_structure():
    """Verify report contains all required fields from the checklist."""
    from deerflow.runtime.cer_authoring.pipeline import build_self_inspection_report

    report = build_self_inspection_report({})

    required_top_level = [
        "overall_assessment",
        "nodes_executed",
        "nodes_blocked",
        "environmental_skips",
        "gate_decision",
        "writer_quality_score",
        "missing_data",
        "ready_for_export",
    ]
    for field in required_top_level:
        assert field in report, f"Missing top-level field: {field}"

    # Extended fields from Repair Checklist §1-§12
    required_extended = [
        "runtime_enforcement",
        "gate_path_audit",
        "cleanroom_writer_context",
        "contamination_scan",
        "render_boundary",
        "claim_br_consistency",
        "evidence_count_audit",
        "knowledge_asset_status",
        "skill_layer_status",
        "test_classification",
        "environment_assessment",
    ]
    for field in required_extended:
        assert field in report, f"Missing extended field: {field}"

    # Runtime enforcement sub-fields (§1)
    re_keys = ["g39_in_gate_list", "g39_not_noop", "quarantine_in_graph_routing", "gate_rework_blocks_export"]
    for key in re_keys:
        assert key in report["runtime_enforcement"], f"Missing runtime_enforcement.{key}"

    # Gate path audit sub-fields (§8)
    gate_keys = ["g42_evidence_sufficiency", "g46_pre_writer_readiness", "g39_final_draft_qa",
                 "writer_gates", "export_decision", "quarantine_routing"]
    for key in gate_keys:
        assert key in report["gate_path_audit"], f"Missing gate_path_audit.{key}"

    # Skill layer sub-fields (§12)
    skill_keys = ["skill_cards_exist", "skill_registry_exists", "skill_selector_exists",
                  "dynamic_injection_exists", "current_injection_method"]
    for key in skill_keys:
        assert key in report["skill_layer_status"], f"Missing skill_layer_status.{key}"

    # Knowledge asset sub-fields (§11)
    ka_keys = ["defect_patterns", "remediation_playbook", "endpoint_alternatives",
               "nb_body_profiles", "device_heuristics", "domain_term_variants",
               "section_defense_rules", "slot_templates"]
    for key in ka_keys:
        assert key in report["knowledge_asset_status"], f"Missing knowledge_asset_status.{key}"

    # Environment sub-fields (§10)
    env_keys = ["llm_api_available", "full_pipeline_validatable", "deterministic_tests_runnable"]
    for key in env_keys:
        assert key in report["environment_assessment"], f"Missing environment_assessment.{key}"

    print(f"Self-inspection report structure: {len(report)} top-level fields, all sub-fields present")


def test_self_inspection_empty_state():
    """Empty state produces valid (not crashed) report with correct default values."""
    from deerflow.runtime.cer_authoring.pipeline import build_self_inspection_report

    report = build_self_inspection_report({})

    assert report["nodes_executed"] == 0
    assert report["nodes_blocked"] == 0
    assert report["gate_decision"] == "not_executed"
    assert report["ready_for_export"] is False
    assert report["overall_assessment"] == "INCOMPLETE — pipeline did not reach gate closure"
    assert report["missing_data"] == ["claim_ledger", "evidence_registry", "sota_benchmark_matrix", "device_profile_incomplete"]
    assert report["environment_assessment"]["deterministic_tests_runnable"] is True
    assert report["skill_layer_status"]["current_injection_method"] == "STATIC_PROMPT_REFERENCE"
    assert report["skill_layer_status"]["skill_registry_exists"] is False

    print("Empty state report valid: all defaults correct")


def test_self_inspection_llm_available_uses_deepseek_or_kimi_api_not_anthropic(monkeypatch):
    """Kimi API/DeepSeek credentials are sufficient; Anthropic official key is not required."""
    from deerflow.runtime.cer_authoring.pipeline import build_self_inspection_report

    for key in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("KIMI_API_KEY", "test-kimi-api")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    report = build_self_inspection_report({})

    assert report["environment_assessment"]["llm_api_available"] is True


def test_self_inspection_rich_state():
    """Rich state with mock data produces enhanced report."""
    from deerflow.runtime.cer_authoring.pipeline import build_self_inspection_report

    state = {
        "device_profile": {"device_type": "Catheter", "device_class": "III", "clinical_domain": "cardiovascular"},
        "claim_ledger": [{"claim_id": "C-01"}],
        "evidence_registry": [{"evidence_id": "E-001"}],
        "sota_benchmark_matrix": [{"benchmark_id": "B-01"}],
        "benefit_risk_ledger": [{"br_id": "BR-01"}],
        "claim_sota_alignment_table": [{"claim_id": "C-01", "feasibility": "supported"}],
        "search_run_registry": [{"search_id": "S-01"}],
        "source_inventory": [{"file": "test.pdf"}],
        "stage_results": [
            {"stage": "initialize", "status": "completed"},
            {"stage": "sota_search", "status": "completed"},
        ],
        "qa_gate_report": {"decision": "PASS_TO_DRAFT_DOCX"},
        "writer_quality_report": {"writer_quality_score": "7/7", "writer_quality_pct": 100},
        "writer_input_packet": {"schema": "writer_input_packet_v1"},
    }

    report = build_self_inspection_report(state)

    assert report["nodes_executed"] == 2
    assert report["gate_decision"] == "PASS_TO_DRAFT_DOCX"
    assert report["ready_for_export"] is True
    assert report["overall_assessment"] == "PASS — all gates passed, ready for export"
    assert len(report["missing_data"]) == 0
    assert report["claim_br_consistency"]["claims_assessed"] == 1
    assert report["claim_br_consistency"]["br_entries"] == 1
    assert report["evidence_count_audit"]["searched"] == 1
    assert report["evidence_count_audit"]["evidence_registry"] == 1
    assert report["cleanroom_writer_context"]["writer_input_packet_fields"] is True

    print("Rich state report valid: all counts and decisions correct")
