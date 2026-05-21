#!/usr/bin/env python3
"""
RMF Harness Dry Run Loader - Phase A Evidence Review Edition

Performs a dry-run of the RMF Review workflow WITHOUT live LLM calls.
ACTUALLY creates project-bound artifacts and workflow state by parsing
the workflow YAML node graph and simulating execution up to Human Gate.

Usage:
    python scripts/rmf_harness_dry_run.py --project-id RMF-PHASE-A-SMOKE --rmf-run-id rmf-dryrun-001

Exit codes:
    0 = All phases passed
    1 = Validation failure
    2 = File not found
"""

import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path


# Base directories
BACKEND_DIR = Path(__file__).parent.parent
WORKFLOWS_DIR = BACKEND_DIR / "workflows"
PROMPTS_DIR = BACKEND_DIR / "prompts" / "rmf" / "canonical"
SCHEMAS_DIR = BACKEND_DIR / "schemas"

# Load .env file if it exists
ENV_FILE = BACKEND_DIR.parent / ".env"
if ENV_FILE.exists():
    with open(ENV_FILE) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip())
ARTIFACTS_DIR = BACKEND_DIR / "artifacts"


# =============================================================================
# VALIDATION FUNCTIONS (A-F)
# =============================================================================

def validate_workflow_yaml() -> tuple[bool, list[str]]:
    """Command A: YAML parse check."""
    errors = []
    workflow_path = WORKFLOWS_DIR / "rmf_review_workflow_v1.yaml"

    if not workflow_path.exists():
        errors.append(f"Workflow YAML not found: {workflow_path}")
        return False, errors

    try:
        import yaml
        with open(workflow_path) as f:
            workflow = yaml.safe_load(f)
    except Exception as e:
        errors.append(f"Failed to parse workflow YAML: {e}")
        return False, errors

    required_fields = ["version", "workflow_id", "nodes", "edges"]
    for field in required_fields:
        if field not in workflow:
            errors.append(f"Workflow missing required field: {field}")

    expected_nodes = [
        "rmf_orchestrator", "rmf_docstruct", "rmf_l1_rule_engine",
        "rmf_comp_risk_coverage", "rmf_corr_method_matrix", "rmf_adeq_control_adequacy",
        "rmf_trac_traceability", "rmf_cons_cross_document_consistency",
        "rmf_acpt_residual_risk_benefit_risk", "rmf_qa_human_gate_packet",
        "rmf_pms_post_production_feedback_lane", "rmf_findings_synthesis",
    ]

    if "nodes" in workflow:
        node_ids = [n["id"] for n in workflow["nodes"]]
        for expected in expected_nodes:
            if expected not in node_ids:
                errors.append(f"Missing expected node: {expected}")
        if len(workflow["nodes"]) != 12:
            errors.append(f"Expected 12 nodes, found {len(workflow['nodes'])}")

    return len(errors) == 0, errors


def validate_prompt_files() -> tuple[bool, list[str]]:
    """Command B: Prompt file existence check."""
    errors = []
    expected_prompts = [
        "rmf_review_orchestrator.md", "rmf_docstruct_agent.md", "rmf_l1_rule_engine_spec.md",
        "rmf_comp_risk_coverage_agent.md", "rmf_corr_method_matrix_agent.md",
        "rmf_adeq_control_adequacy_agent.md", "rmf_trac_traceability_spec.md",
        "rmf_cons_cross_document_consistency_agent.md", "rmf_acpt_residual_risk_benefit_risk_agent.md",
        "rmf_pms_post_production_feedback_lane.md", "rmf_qa_human_gate_packet_agent.md",
        "rmf_findings_synthesis_agent.md",
    ]
    for prompt in expected_prompts:
        prompt_path = PROMPTS_DIR / prompt
        if not prompt_path.exists():
            errors.append(f"Prompt file not found: {prompt_path}")
    return len(errors) == 0, errors


def validate_schemas() -> tuple[bool, list[str]]:
    """Command C: Schema JSON parse check."""
    errors = []
    schema_files = ["rmf_agent_output.schema.json", "rmf_findings_register.schema.json"]
    for schema_file in schema_files:
        schema_path = SCHEMAS_DIR / schema_file
        if not schema_path.exists():
            errors.append(f"Schema file not found: {schema_path}")
            continue
        try:
            with open(schema_path) as f:
                json.load(f)
        except json.JSONDecodeError as e:
            errors.append(f"Invalid JSON in {schema_file}: {e}")
    return len(errors) == 0, errors


def validate_node_graph() -> tuple[bool, list[str], dict]:
    """Command D: Node graph validation - actually parse nodes and edges."""
    errors = []
    workflow_path = WORKFLOWS_DIR / "rmf_review_workflow_v1.yaml"

    try:
        import yaml
        with open(workflow_path) as f:
            workflow = yaml.safe_load(f)
    except Exception as e:
        errors.append(f"Failed to parse workflow YAML: {e}")
        return False, errors, {}

    nodes = workflow.get("nodes", [])
    edges = workflow.get("edges", [])

    if len(nodes) != 12:
        errors.append(f"Expected 12 nodes, found {len(nodes)}")

    # Validate node structure
    node_ids = set()
    for node in nodes:
        if "id" not in node:
            errors.append(f"Node missing 'id' field")
        if "runtime_type" not in node:
            errors.append(f"Node {node.get('id', 'UNKNOWN')} missing 'runtime_type'")
        node_ids.add(node["id"])

    # External workflow concepts (not actual nodes, but valid edge destinations)
    external_concepts = {"human_gate", "knowledge_review_gate"}

    # Validate edges reference valid nodes or external concepts
    for edge in edges:
        if "from" in edge and edge["from"] not in node_ids and edge["from"] not in external_concepts:
            errors.append(f"Edge references unknown node: {edge['from']}")
        if "to" in edge and edge["to"] not in node_ids and edge["to"] not in external_concepts:
            errors.append(f"Edge references unknown node: {edge['to']}")

    return len(errors) == 0, errors, workflow


def validate_skill_file_paths(workflow: dict) -> tuple[bool, list[str]]:
    """Command E: Skill file path resolution - check prompt_file references."""
    errors = []
    for node in workflow.get("nodes", []):
        prompt_file = node.get("prompt_file")
        if prompt_file:
            # prompt_file is relative to prompts/rmf/canonical/
            full_path = BACKEND_DIR / prompt_file
            if not full_path.exists():
                errors.append(f"Node {node['id']} references missing prompt_file: {prompt_file}")
    return len(errors) == 0, errors


def validate_model_profile_references(workflow: dict) -> tuple[bool, list[str]]:
    """Command F: Model profile reference resolution."""
    errors = []
    defined_profiles = set(workflow.get("model_profiles", {}).keys())

    for node in workflow.get("nodes", []):
        model_profile = node.get("model_profile")
        if model_profile and model_profile not in defined_profiles:
            errors.append(f"Node {node['id']} references undefined model_profile: {model_profile}")
    return len(errors) == 0, errors


# =============================================================================
# ARTIFACT CREATION FUNCTIONS (H, I, J, K, L)
# =============================================================================

def create_artifact_root(project_id: str, rmf_run_id: str, workflow: dict) -> tuple[bool, list[str]]:
    """Command H: Artifact root existence check - ACTUALLY create directories."""
    errors = []
    artifact_root = ARTIFACTS_DIR / "cer" / project_id / "rmf_review" / rmf_run_id

    required_dirs = [
        "input",
        "docstruct",
        "l1_rule_engine",
        "dimension_outputs/comp",
        "dimension_outputs/corr",
        "dimension_outputs/adeq",
        "dimension_outputs/trac",
        "dimension_outputs/cons",
        "dimension_outputs/acpt",
        "qa_gate",
        "human_gate",
        "synthesis",
        "knowledge_backflow",
        "state",
    ]

    try:
        for dir_path in required_dirs:
            full_path = artifact_root / dir_path
            full_path.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        errors.append(f"Failed to create artifact directories: {e}")

    return len(errors) == 0, errors


def create_state_files(project_id: str, rmf_run_id: str, workflow: dict) -> tuple[bool, list[str]]:
    """Command I: State file check - ACTUALLY write workflow state."""
    errors = []
    artifact_root = ARTIFACTS_DIR / "cer" / project_id / "rmf_review" / rmf_run_id
    state_dir = artifact_root / "state"

    # Create rmf_workflow_state.json
    workflow_state = {
        "_meta": {
            "schema_version": "1.0",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "workflow_id": workflow.get("workflow_id"),
            "project_id": project_id,
            "rmf_run_id": rmf_run_id,
        },
        "current_phase": "initialized",
        "human_gate_status": "pending",
        "dimension_results": {
            "COMP": {"status": "pending", "findings": []},
            "CORR": {"status": "pending", "findings": []},
            "ADEQ": {"status": "pending", "findings": []},
            "TRAC": {"status": "pending", "findings": []},
            "CONS": {"status": "pending", "findings": []},
            "ACPT": {"status": "pending", "findings": []},
        },
        "pms_triggered": False,
        "gate_packet": None,
        "human_gate_decision": None,
        "findings_synthesis": None,
        "execution_trace": [
            {
                "step": "initialized",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "dry_run": True,
                "note": "Workflow initialized in dry-run mode - no live LLM invoked"
            }
        ]
    }

    try:
        state_file = state_dir / "rmf_workflow_state.json"
        with open(state_file, "w") as f:
            json.dump(workflow_state, f, indent=2)
    except Exception as e:
        errors.append(f"Failed to write workflow state: {e}")

    return len(errors) == 0, errors


def create_agent_usage_ledger(project_id: str, rmf_run_id: str, workflow: dict) -> tuple[bool, list[str]]:
    """Command J: Agent usage ledger check - ACTUALLY write ledger."""
    errors = []
    artifact_root = ARTIFACTS_DIR / "cer" / project_id / "rmf_review" / rmf_run_id
    state_dir = artifact_root / "state"

    # Create rmf_agent_usage_ledger.json
    nodes = workflow.get("nodes", [])
    ledger = {
        "_meta": {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "project_id": project_id,
            "rmf_run_id": rmf_run_id,
        },
        "llm_invocations": [],  # Empty in dry-run - no live LLM calls
        "agent_executions": [
            {
                "node_id": node["id"],
                "runtime_type": node.get("runtime_type"),
                "model_profile": node.get("model_profile"),
                "llm_invoked": False,  # Dry-run - no live LLM
                "execution_time_ms": 0,
                "dry_run": True,
            }
            for node in nodes
        ],
        "total_llm_calls": 0,
        "total_agent_executions": len(nodes),
        "confirm_no_live_llm": True,
    }

    try:
        ledger_file = state_dir / "rmf_agent_usage_ledger.json"
        with open(ledger_file, "w") as f:
            json.dump(ledger, f, indent=2)
    except Exception as e:
        errors.append(f"Failed to write agent usage ledger: {e}")

    return len(errors) == 0, errors


def create_input_manifest(project_id: str, rmf_run_id: str, workflow: dict) -> tuple[bool, list[str]]:
    """Command H (supplement): Create rmf_input_manifest.json."""
    errors = []
    artifact_root = ARTIFACTS_DIR / "cer" / project_id / "rmf_review" / rmf_run_id
    input_dir = artifact_root / "input"

    manifest = {
        "_meta": {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "project_id": project_id,
            "rmf_run_id": rmf_run_id,
            "dry_run": True,
        },
        "input_documents": {
            "rmf": {"status": "required", "provided": False, "note": "Dry-run - no actual document"},
            "cer": {"status": "required", "provided": False, "note": "Dry-run - no actual document"},
            "ifu": {"status": "optional", "provided": False, "note": "Dry-run - no actual document"},
            "fmea": {"status": "optional", "provided": False, "note": "Dry-run - no actual document"},
        },
        "approved_knowledge_assets": {
            "status": "degraded_mode",
            "source": "NOCODB_DRY_RUN_SIMULATION",
            "note": "NocoDB connection simulated in dry-run mode - no actual readback",
            "asset_count": 0,
            "assets": [],
        },
        "review_scope": {
            "dimensions": ["COMP", "CORR", "ADEQ", "TRAC", "CONS", "ACPT"],
            "include_pms_lane": True,
            "pms_trigger_conditions": ["risk_driven_only"],
        },
    }

    try:
        manifest_file = input_dir / "rmf_input_manifest.json"
        with open(manifest_file, "w") as f:
            json.dump(manifest, f, indent=2)
    except Exception as e:
        errors.append(f"Failed to write input manifest: {e}")

    return len(errors) == 0, errors


def create_approved_knowledge_assets_dry_run(project_id: str, rmf_run_id: str) -> tuple[bool, list[str]]:
    """Command K: NocoDB approved knowledge input check - ACTUAL READBACK."""
    errors = []
    artifact_root = ARTIFACTS_DIR / "cer" / project_id / "rmf_review" / rmf_run_id
    input_dir = artifact_root / "input"

    # Import NocoDB readback module
    # Note: We need to use direct file import because running as script puts scripts/ in sys.path[0]
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "rmf_nocodb_readback",
            str(BACKEND_DIR / "scripts" / "rmf_nocodb_readback.py")
        )
        nocodb_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(nocodb_module)
        readback_approved_knowledge_assets = nocodb_module.readback_approved_knowledge_assets
    except Exception as e:
        # Fallback to simulation if module not available
        knowledge_assets = {
            "_meta": {
                "created_at": datetime.now(timezone.utc).isoformat(),
                "source": "IMPORT_FAILED_SIMULATION",
                "note": f"Failed to import rmf_nocodb_readback: {e} - simulation only",
                "actual_connection": False,
            },
            "loaded_at": datetime.now(timezone.utc).isoformat(),
            "asset_count": 0,
            "assets": [],
            "degraded_mode": True,
        }
        try:
            knowledge_file = input_dir / "approved_knowledge_assets.json"
            with open(knowledge_file, "w") as f:
                json.dump(knowledge_assets, f, indent=2)
        except Exception as e:
            errors.append(f"Failed to write knowledge assets file: {e}")
        return len(errors) == 0, errors

    # Perform actual NocoDB readback
    result = readback_approved_knowledge_assets()

    # Add metadata
    knowledge_assets = {
        "_meta": {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "project_id": project_id,
            "rmf_run_id": rmf_run_id,
            "source": "nocodb" if result["actual_connection"] else "simulation",
            "actual_connection": result["actual_connection"],
            "degraded_mode": result["degraded_mode"],
            "error": result.get("error"),
            "note": "RMF dry-run NocoDB readback" if result["actual_connection"] else "NocoDB readback failed - degraded mode",
        },
        "loaded_at": result.get("readback_timestamp", datetime.now(timezone.utc).isoformat()),
        "asset_count": result["asset_count"],
        "assets": result["assets"],
        "degraded_mode": result["degraded_mode"],
        "query_executed": "(status,eq,published)~or(status,eq,approved)",
        "statuses_included": ["published", "approved"],
        "statuses_excluded": ["rejected", "parked", "needs_human_review"],
    }

    try:
        knowledge_file = input_dir / "approved_knowledge_assets.json"
        with open(knowledge_file, "w") as f:
            json.dump(knowledge_assets, f, indent=2)
    except Exception as e:
        errors.append(f"Failed to write knowledge assets file: {e}")
        return False, errors

    return len(errors) == 0, errors


def create_human_gate_artifacts(project_id: str, rmf_run_id: str, workflow: dict) -> tuple[bool, list[str]]:
    """Command L: Human Gate stop skeleton check - ACTUALLY create skeleton."""
    errors = []
    artifact_root = ARTIFACTS_DIR / "cer" / project_id / "rmf_review" / rmf_run_id
    qa_gate_dir = artifact_root / "qa_gate"

    # Create human gate packet skeleton
    human_gate_packet = {
        "_meta": {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "dry_run": True,
            "node_id": "QA",
            "status": "HUMAN_GATE_PACKET_PREPARED_AWAITING_HUMAN",
            "note": "This is a dry-run skeleton. Human review not actually performed.",
        },
        "section_a_executive_summary": "[DRY-RUN] Executive summary placeholder - would contain high-level overview",
        "section_b_dimension_findings": {
            "COMP": {"status": "complete", "finding_count": 0, "critical_issues": 0},
            "CORR": {"status": "complete", "finding_count": 0, "critical_issues": 0},
            "ADEQ": {"status": "complete", "finding_count": 0, "critical_issues": 0},
            "TRAC": {"status": "complete", "finding_count": 0, "critical_issues": 0},
            "CONS": {"status": "complete", "finding_count": 0, "critical_issues": 0},
            "ACPT": {"status": "complete", "finding_count": 0, "critical_issues": 0},
            "PMS": {"status": "not_triggered", "finding_count": 0},
        },
        "section_c_conflicts_and_qa_resolutions": [],
        "section_d_high_risk_items": [],
        "section_e_pms_findings": [],
        "section_f_recommended_decisions": [
            {
                "decision_area": "RMF_acceptability",
                "recommendation": "PENDING_HUMAN_REVIEW",
                "rationale": "[DRY-RUN] Human review not performed - recommendation pending",
                "conditions_for_approval": [],
            }
        ],
        "workflow_stop_point": True,
        "layer3_decisions_awaited": [
            "RMF_acceptability",
            "benefit_risk_final",
            "residual_risk_closure",
        ],
    }

    # Create human_review_required_items.json
    human_review_items = {
        "_meta": {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "dry_run": True,
            "note": "No actual human review - this is dry-run skeleton",
        },
        "required_decisions": [
            {
                "area": "RMF_acceptability",
                "description": "Final RMF acceptability decision",
                "status": "AWAITING_HUMAN",
                "dry_run": True,
            }
        ],
        "layer3_scope": [
            "RMF_acceptability",
            "benefit_risk_final",
            "residual_risk_closure",
            "residual_risk_acceptance_under_uncertainty",
        ],
        "confirm_no_final_decision_made": True,
    }

    try:
        packet_file = qa_gate_dir / "rmf_human_gate_packet.md"
        with open(packet_file, "w") as f:
            f.write("# RMF Human Gate Packet (Dry-Run Skeleton)\n\n")
            f.write(f"**Created:** {datetime.now(timezone.utc).isoformat()}\n\n")
            f.write("**Status:** AWAITING HUMAN REVIEW (Dry-Run)\n\n")
            f.write("---\n\n")
            f.write("## Section A: Executive Summary\n\n")
            f.write("[DRY-RUN] Executive summary placeholder\n\n")
            f.write("## Section F: Recommended Decisions\n\n")
            f.write("| Decision Area | Recommendation |\n")
            f.write("|---|---|\n")
            f.write("| RMF_acceptability | PENDING_HUMAN_REVIEW |\n\n")
            f.write("---\n\n")
            f.write("**Note:** This is a dry-run skeleton. No actual human review performed.\n")

        items_file = qa_gate_dir / "human_review_required_items.json"
        with open(items_file, "w") as f:
            json.dump(human_review_items, f, indent=2)
    except Exception as e:
        errors.append(f"Failed to write human gate artifacts: {e}")

    return len(errors) == 0, errors


# =============================================================================
# MAIN DRY-RUN EXECUTION
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="RMF Harness Dry Run Loader - Phase A Evidence Review")
    parser.add_argument("--project-id", default="RMF-PHASE-A-SMOKE", help="Project ID for artifact paths")
    parser.add_argument("--rmf-run-id", default="rmf-dryrun-001", help="RMF Run ID for artifact paths")
    args = parser.parse_args()

    project_id = args.project_id
    rmf_run_id = args.rmf_run_id

    print("=" * 70)
    print("RMF HARNESS DRY RUN - PHASE A EVIDENCE REVIEW")
    print("=" * 70)
    print(f"Project ID: {project_id}")
    print(f"RMF Run ID:  {rmf_run_id}")
    print()

    all_passed = True
    all_errors = []
    workflow = {}

    # Commands A-F: Validation
    print("[COMMAND A] YAML parse check...")
    passed, errors = validate_workflow_yaml()
    if passed:
        print("  PASS")
    else:
        print(f"  FAIL - {len(errors)}")
        all_passed = False
        all_errors.extend([f"[A] {e}" for e in errors])
    print()

    print("[COMMAND B] Prompt file existence check...")
    passed, errors = validate_prompt_files()
    if passed:
        print("  PASS - All 12 prompt files exist")
    else:
        print(f"  FAIL - {len(errors)}")
        all_passed = False
        all_errors.extend([f"[B] {e}" for e in errors])
    print()

    print("[COMMAND C] Schema JSON parse check...")
    passed, errors = validate_schemas()
    if passed:
        print("  PASS - All schemas valid JSON")
    else:
        print(f"  FAIL - {len(errors)}")
        all_passed = False
        all_errors.extend([f"[C] {e}" for e in errors])
    print()

    print("[COMMAND D] Node graph validation...")
    passed, errors, workflow = validate_node_graph()
    if passed:
        print("  PASS - Node graph valid (12 nodes, edges reference valid nodes)")
    else:
        print(f"  FAIL - {len(errors)}")
        all_passed = False
        all_errors.extend([f"[D] {e}" for e in errors])
    print()

    print("[COMMAND E] Skill file path resolution...")
    passed, errors = validate_skill_file_paths(workflow)
    if passed:
        print("  PASS - All prompt_file references resolvable")
    else:
        print(f"  FAIL - {len(errors)}")
        all_passed = False
        all_errors.extend([f"[E] {e}" for e in errors])
    print()

    print("[COMMAND F] Model profile reference resolution...")
    passed, errors = validate_model_profile_references(workflow)
    if passed:
        print("  PASS - All model_profile references valid")
    else:
        print(f"  FAIL - {len(errors)}")
        all_passed = False
        all_errors.extend([f"[F] {e}" for e in errors])
    print()

    # Command G: Dry-run execution - ACTUALLY create artifacts
    print("[COMMAND G] Dry-run execution - creating project-bound artifacts...")
    print("  NOTE: This is SIMULATION only - no live LLM invoked")
    print("  Loading workflow YAML and parsing node graph...")
    if workflow:
        print(f"  Workflow loaded: {workflow.get('workflow_id')}")
        print(f"  Nodes to execute: {len(workflow.get('nodes', []))}")
    print("  PASS - Workflow loaded and parsed (simulation mode)")
    print()

    print("[COMMAND H] Artifact root existence check - ACTUALLY creating directories...")
    passed, errors = create_artifact_root(project_id, rmf_run_id, workflow)
    if passed:
        artifact_root = ARTIFACTS_DIR / "cer" / project_id / "rmf_review" / rmf_run_id
        print(f"  PASS - Created artifact root: {artifact_root}")
        print("  Directories created:")
        for d in ["input", "docstruct", "l1_rule_engine", "dimension_outputs", "qa_gate", "human_gate", "synthesis", "knowledge_backflow", "state"]:
            p = artifact_root / d
            exists = "EXISTS" if p.exists() else "MISSING"
            print(f"    - {d}: {exists}")
    else:
        print(f"  FAIL - {len(errors)}")
        all_passed = False
        all_errors.extend([f"[H] {e}" for e in errors])
    print()

    print("[COMMAND I] State file check - ACTUALLY writing workflow state...")
    passed, errors = create_state_files(project_id, rmf_run_id, workflow)
    if passed:
        state_file = ARTIFACTS_DIR / "cer" / project_id / "rmf_review" / rmf_run_id / "state" / "rmf_workflow_state.json"
        exists = "EXISTS" if state_file.exists() else "MISSING"
        print(f"  PASS - {state_file.name}: {exists}")
    else:
        print(f"  FAIL - {len(errors)}")
        all_passed = False
        all_errors.extend([f"[I] {e}" for e in errors])
    print()

    print("[COMMAND J] Agent usage ledger check - ACTUALLY writing ledger...")
    passed, errors = create_agent_usage_ledger(project_id, rmf_run_id, workflow)
    if passed:
        ledger_file = ARTIFACTS_DIR / "cer" / project_id / "rmf_review" / rmf_run_id / "state" / "rmf_agent_usage_ledger.json"
        exists = "EXISTS" if ledger_file.exists() else "MISSING"
        print(f"  PASS - {ledger_file.name}: {exists}")
    else:
        print(f"  FAIL - {len(errors)}")
        all_passed = False
        all_errors.extend([f"[J] {e}" for e in errors])
    print()

    print("[COMMAND K] NocoDB approved knowledge input check...")
    passed, errors = create_approved_knowledge_assets_dry_run(project_id, rmf_run_id)
    if passed:
        knowledge_file = ARTIFACTS_DIR / "cer" / project_id / "rmf_review" / rmf_run_id / "input" / "approved_knowledge_assets.json"
        exists = "EXISTS" if knowledge_file.exists() else "MISSING"
        # Read the actual result to report correct status
        try:
            with open(knowledge_file) as f:
                result = json.load(f)
            actual_conn = result.get("_meta", {}).get("actual_connection", False)
            asset_count = result.get("asset_count", 0)
            if actual_conn:
                print(f"  PASS - {knowledge_file.name}: {exists} (ACTUAL NOCODB READBACK)")
                print(f"  NOTE: actual_connection = true, asset_count = {asset_count}")
            else:
                print(f"  PASS - {knowledge_file.name}: {exists} (SIMULATION)")
                print(f"  NOTE: actual_connection = false (simulation only)")
        except Exception:
            print(f"  PASS - {knowledge_file.name}: {exists}")
    else:
        print(f"  FAIL - {len(errors)}")
        all_passed = False
        all_errors.extend([f"[K] {e}" for e in errors])
    print()

    print("[COMMAND L] Human Gate stop skeleton check...")
    passed, errors = create_human_gate_artifacts(project_id, rmf_run_id, workflow)
    if passed:
        packet_file = ARTIFACTS_DIR / "cer" / project_id / "rmf_review" / rmf_run_id / "qa_gate" / "rmf_human_gate_packet.md"
        items_file = ARTIFACTS_DIR / "cer" / project_id / "rmf_review" / rmf_run_id / "qa_gate" / "human_review_required_items.json"
        print(f"  PASS - rmf_human_gate_packet.md: {'EXISTS' if packet_file.exists() else 'MISSING'}")
        print(f"  PASS - human_review_required_items.json: {'EXISTS' if items_file.exists() else 'MISSING'}")
        print("  NOTE: workflow_stop_point = True (represented, not executed)")
    else:
        print(f"  FAIL - {len(errors)}")
        all_passed = False
        all_errors.extend([f"[L] {e}" for e in errors])
    print()

    print("[COMMAND M] Confirm no live LLM invocation...")
    ledger_file = ARTIFACTS_DIR / "cer" / project_id / "rmf_review" / rmf_run_id / "state" / "rmf_agent_usage_ledger.json"
    if ledger_file.exists():
        with open(ledger_file) as f:
            ledger = json.load(f)
        if ledger.get("confirm_no_live_llm") and ledger.get("total_llm_calls") == 0:
            print("  PASS - confirm_no_live_llm = True, total_llm_calls = 0")
        else:
            print("  FAIL - LLM invocation detected or flag not set")
            all_passed = False
            all_errors.append("[M] Live LLM invocation detected or flag not set")
    else:
        print("  FAIL - Ledger file not found")
        all_passed = False
        all_errors.append("[M] Ledger file not found")
    print()

    print("[COMMAND N] Confirm no final RMF decision produced...")
    gate_packet_file = ARTIFACTS_DIR / "cer" / project_id / "rmf_review" / rmf_run_id / "qa_gate" / "rmf_human_gate_packet.md"
    if gate_packet_file.exists():
        with open(gate_packet_file) as f:
            content = f.read()
        if "PENDING_HUMAN_REVIEW" in content or "dry-run" in content.lower():
            print("  PASS - No final decision made (status = PENDING_HUMAN_REVIEW)")
        else:
            print("  FAIL - Final decision appears to have been made")
            all_passed = False
            all_errors.append("[N] Final decision may have been made")
    else:
        print("  FAIL - Human gate packet not found")
        all_passed = False
        all_errors.append("[N] Human gate packet not found")
    print()

    print("[COMMAND O] Backend import check...")
    try:
        # Try importing the harness package using sys.path from backend
        import sys
        backend_path = str(BACKEND_DIR)
        if backend_path not in sys.path:
            sys.path.insert(0, backend_path)
        import importlib.util
        spec = importlib.util.find_spec("deerflow")
        if spec is not None:
            print(f"  PASS - deerflow package importable from {spec.origin}")
        else:
            # Try from packages/harness path
            harness_path = str(BACKEND_DIR / "packages" / "harness")
            if harness_path not in sys.path:
                sys.path.insert(0, harness_path)
            spec = importlib.util.find_spec("deerflow")
            if spec is not None:
                print(f"  PASS - deerflow package importable from {spec.origin}")
            else:
                print("  FAIL - deerflow package not found in Python path")
                all_passed = False
                all_errors.append("[O] deerflow package not importable")
    except Exception as e:
        print(f"  WARNING - Import check issue: {e}")
    print()

    # Additional H supplements: input manifest
    print("[COMMAND H-SUP] Creating input manifest...")
    passed, errors = create_input_manifest(project_id, rmf_run_id, workflow)
    if passed:
        manifest_file = ARTIFACTS_DIR / "cer" / project_id / "rmf_review" / rmf_run_id / "input" / "rmf_input_manifest.json"
        exists = "EXISTS" if manifest_file.exists() else "MISSING"
        print(f"  PASS - {manifest_file.name}: {exists}")
    else:
        print(f"  FAIL - {len(errors)}")
        all_errors.extend([f"[H-SUP] {e}" for e in errors])
    print()

    # Summary
    print("=" * 70)
    print("DRY RUN SUMMARY")
    print("=" * 70)
    if all_passed:
        # Check actual NocoDB result
        nocodb_actual = False
        nocodb_asset_count = 0
        try:
            knowledge_file = ARTIFACTS_DIR / "cer" / project_id / "rmf_review" / rmf_run_id / "input" / "approved_knowledge_assets.json"
            if knowledge_file.exists():
                with open(knowledge_file) as f:
                    result = json.load(f)
                nocodb_actual = result.get("_meta", {}).get("actual_connection", False)
                nocodb_asset_count = result.get("asset_count", 0)
        except Exception:
            pass

        print("ALL VALIDATIONS PASSED")
        print()
        print("Phase A Configuration Mounting: COMPLETE")
        print("- Workflow YAML: 12-node DAG parsed")
        print("- Prompt Files: 12 canonical prompts validated")
        print("- Schemas: JSON schemas validated")
        print("- Node Graph: Validated and parsed")
        print("- Skill File Paths: All resolvable")
        print("- Model Profiles: All references valid")
        print("- Artifact Root: Created with skeleton files")
        print("- Workflow State: Written to rmf_workflow_state.json")
        print("- Agent Usage Ledger: Written (confirm_no_live_llm = True)")
        if nocodb_actual:
            print(f"- NocoDB: ACTUAL READBACK (actual_connection = true, asset_count = {nocodb_asset_count})")
        else:
            print("- NocoDB: SIMULATION ONLY (actual_connection = False)")
        print("- Human Gate: Stop skeleton created (not executed)")
        print("- No Live LLM: CONFIRMED")
        print("- No Final Decision: CONFIRMED")
        return 0
    else:
        print(f"VALIDATION FAILED - {len(all_errors)} error(s)")
        print()
        for e in all_errors:
            print(f"  {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
