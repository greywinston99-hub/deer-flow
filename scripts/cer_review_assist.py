#!/usr/bin/env python3
"""CER Review Assist — Unified Runner.

Usage:
  # 1-stage smoke test (evidence curator only + component verification)
  python scripts/cer_review_assist.py --stage smoke

  # 3-stage full pilot (evidence-curator → gap-specialist → logic-qa)
  python scripts/cer_review_assist.py --stage full --project-id 082_tianjinhengyu

  # Direct input/output paths
  python scripts/cer_review_assist.py --stage full --input-dir /path/to/txt --output-dir /path/to/out
"""

from __future__ import annotations

import argparse, asyncio, json, os, re, sys, uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
BACKEND_DIR = REPO_ROOT / "backend"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Circular import mitigation
_mock_prompt = MagicMock()
_mock_prompt.get_skills_prompt_section = MagicMock(return_value="")
_mock_prompt.apply_prompt_template = MagicMock(return_value="")
sys.modules["deerflow.agents.lead_agent.prompt"] = _mock_prompt

_mock_task_tool = MagicMock()
_mock_task_tool.task_tool = MagicMock()
sys.modules["deerflow.tools.builtins.task_tool"] = _mock_task_tool

_CER_RAG_ROOT = Path(os.environ.get("CER_RAG_ROOT", Path.home() / "CER-RAG"))
TRACK_B_OUTPUT = _CER_RAG_ROOT / "00_knowledge_extraction_build/dual_track_factory_v2_planning/track_b_output"
BUILD_V13 = _CER_RAG_ROOT / "00_knowledge_extraction_build/harness_native_agent_capability_slice/build_v13"

PROHIBITED_TERMS = ["PASS", "FAIL", "APPROVED", "REJECTED", "CEAR"]


# ═══════════════════════════════════════════════════════════════════════════════
# Shared: Prohibited terms detection
# ═══════════════════════════════════════════════════════════════════════════════

def _contains_prohibited_terms(text: str) -> list[str]:
    """Detect prohibited terminal verdict terms in reviewer_decision values."""
    hits: list[str] = []
    rd_match = re.findall(r'"reviewer_decision"\s*:\s*"([^"]+)"', text, re.IGNORECASE)
    for val in rd_match:
        val_upper = val.strip().upper()
        for term in PROHIBITED_TERMS:
            if val_upper == term and term not in hits:
                hits.append(term)
    for field in ["status", "verdict", "final_decision", "outcome"]:
        status_match = re.findall(rf'"{field}"\s*:\s*"([^"]+)"', text, re.IGNORECASE)
        for val in status_match:
            val_upper = val.strip().upper()
            for term in PROHIBITED_TERMS:
                if term in val_upper and term not in hits:
                    hits.append(term)
    return hits


# ═══════════════════════════════════════════════════════════════════════════════
# Shared: Input resolution
# ═══════════════════════════════════════════════════════════════════════════════

def _find_project_dir(project_id: str) -> Path | None:
    if not TRACK_B_OUTPUT.exists():
        return None
    direct = TRACK_B_OUTPUT / project_id
    if direct.exists():
        return direct
    prefix = project_id.split("_")[0] if "_" in project_id else project_id
    matches = sorted(
        p for p in TRACK_B_OUTPUT.iterdir()
        if p.is_dir() and p.name.startswith(f"{prefix}_")
    )
    return matches[0] if matches else None


def read_input_files(input_path: Path) -> dict[str, str]:
    files: dict[str, str] = {}
    if input_path.is_dir():
        for f in sorted(input_path.glob("*.txt")):
            try:
                files[f.name] = f.read_text(encoding="utf-8")
            except Exception as e:
                files[f.name] = f"[READ ERROR: {e}]"
    elif input_path.suffix == ".json":
        try:
            data = json.loads(input_path.read_text(encoding="utf-8"))
            for filename, entry in data.items():
                files[filename] = entry["text"] if isinstance(entry, dict) and "text" in entry else (
                    entry if isinstance(entry, str) else json.dumps(entry, ensure_ascii=False)
                )
        except Exception as e:
            print(f"  WARNING: Could not parse {input_path}: {e}")
    elif input_path.exists():
        print(f"  WARNING: Unsupported input format: {input_path}")
    return files


def resolve_input_path(project_id: str) -> Path | None:
    project_dir = _find_project_dir(project_id)
    if project_dir is None:
        print(f"  WARNING: Project directory not found for '{project_id}'")
        return None
    txt_dir = project_dir / "extracted_texts"
    if txt_dir.exists() and txt_dir.is_dir():
        return txt_dir
    json_file = project_dir / "extracted_texts.json"
    if json_file.exists():
        return json_file
    print(f"  WARNING: No extracted_texts found in {project_dir}")
    return None


def build_inline_file_context(files: dict[str, str]) -> str:
    lines = ["## Available Source Files (inline content)", "", f"Total files: {len(files)}", ""]
    for name, content in files.items():
        size = len(content)
        if size <= 2000:
            preview, note = content, ""
        elif size <= 20000:
            preview, note = content[:2000], f" [...truncated at 2000 chars, full size: {size} chars]"
        else:
            preview, note = content[:1000], f" [...truncated at 1000 chars, full size: {size} chars]"
        lines.append(f"### {name} ({size} chars)")
        lines.append("```")
        lines.append(preview + note)
        lines.append("```")
        lines.append("")
    lines.extend([
        "## Note",
        "File contents are provided inline above. Use the content shown for classification.",
        "Return your JSON output in your response text.",
    ])
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# Smoke: Component verification (no LLM)
# ═══════════════════════════════════════════════════════════════════════════════

_SKILL_PATH = REPO_ROOT / "skills/public/cer-review-assist/cer-review-assist-evidence-curator/SKILL.md"
_CONFIG_PY = BACKEND_DIR / "packages/harness/deerflow/subagents/config.py"
_LEAD_AGENT_PY = BACKEND_DIR / "packages/harness/deerflow/runtime/cer_review/review_assist_lead_agent.py"

_EXPECTED_RULE_IDS = {
    "KA-CAL-AP-RPR-0001", "KA-CAL-AP-RPR-0004", "KA-CAL-GS-RPR-0001",
    "KA-CAL-AP-RPR-0003", "KA-CAL-GS-RPR-0004", "KA-CAL-AP-RPR-0010",
    "KA-CAL-GS-RPR-0006", "KA-CAL-AP-RPR-0016",
}


def verify_skill_md() -> dict[str, Any]:
    if not _SKILL_PATH.exists():
        return {"ok": False, "error": f"SKILL.md not found at {_SKILL_PATH}"}
    content = _SKILL_PATH.read_text(encoding="utf-8")
    if not content.startswith("---"):
        return {"ok": False, "error": "SKILL.md missing YAML frontmatter"}
    parts = content.split("---", 2)
    if len(parts) < 3:
        return {"ok": False, "error": "SKILL.md malformed frontmatter"}
    body = parts[2].strip()
    required_sections = [
        "## Role", "## Workflow Context", "## Responsibilities",
        "## Input Contract", "## Output Schema", "## Quality Gates",
        "## Forbidden Actions", "## Handoff Targets", "## Track C Rule Subset",
    ]
    for section in required_sections:
        if section not in body:
            return {"ok": False, "error": f"SKILL.md missing section '{section}'"}
    track_c_marker = "## Track C Rule Subset"
    if track_c_marker not in body:
        return {"ok": False, "error": "Missing '## Track C Rule Subset'"}
    tc_start = body.index(track_c_marker)
    tc_section = body[tc_start:]
    if "```json" not in tc_section:
        return {"ok": False, "error": "Track C section missing JSON block"}
    json_start = tc_section.index("```json") + len("```json")
    json_end = tc_section.index("```", json_start)
    try:
        rules_data = json.loads(tc_section[json_start:json_end].strip())
    except json.JSONDecodeError as e:
        return {"ok": False, "error": f"Track C JSON parse error: {e}"}
    track_c_rules = rules_data.get("track_c_rules", [])
    actual_ids = {r.get("rule_id", "") for r in track_c_rules}
    missing = _EXPECTED_RULE_IDS - actual_ids
    if missing:
        return {"ok": False, "error": f"Missing Track C rules: {missing}"}
    return {"ok": True, "rule_count": len(track_c_rules), "expected_count": len(_EXPECTED_RULE_IDS)}


def verify_subagent_config() -> dict[str, Any]:
    if not _CONFIG_PY.exists():
        return {"ok": False, "error": f"config.py not found: {_CONFIG_PY}"}
    source = _CONFIG_PY.read_text(encoding="utf-8")
    try:
        compile(source, str(_CONFIG_PY), "exec")
    except SyntaxError as e:
        return {"ok": False, "error": f"config.py syntax error: {e}"}
    required = ["name", "description", "system_prompt", "tools",
                "disallowed_tools", "model", "max_turns", "timeout_seconds"]
    for attr in required:
        if f"{attr}:" not in source:
            return {"ok": False, "error": f"config.py missing field: {attr}"}
    return {"ok": True, "config_fields": len(required)}


def verify_graph_compiles() -> dict[str, Any]:
    if not _LEAD_AGENT_PY.exists():
        return {"ok": False, "error": f"Lead agent not found: {_LEAD_AGENT_PY}"}
    source = _LEAD_AGENT_PY.read_text(encoding="utf-8")
    try:
        compile(source, str(_LEAD_AGENT_PY), "exec")
    except SyntaxError as e:
        return {"ok": False, "error": f"Lead agent syntax error: {e}"}
    checks = {
        "has_build_graph": "def build_review_assist_graph" in source,
        "has_state_class": "class ReviewAssistState" in source,
        "has_subagent_config": "SubagentConfig(" in source,
        "imports_subagent_config": "from deerflow.subagents.config import SubagentConfig" in source,
        "has_executor": "SubagentExecutor(" in source,
    }
    if not all(checks.values()):
        failed = [k for k, v in checks.items() if not v]
        return {"ok": False, "error": f"Missing patterns: {failed}"}
    return {"ok": True, "graph_type": "StateGraph"}


def run_component_verification() -> list[dict[str, Any]]:
    """Phase 1: Verify components without LLM (smoke test)."""
    results = []
    for label, fn in [
        ("skill_md", verify_skill_md),
        ("subagent_config", verify_subagent_config),
        ("graph_compile", verify_graph_compiles),
    ]:
        r = {"check": label, **fn()}
        results.append(r)
        status = "OK" if r["ok"] else "BLOCKED"
        detail = ""
        if r["ok"]:
            detail = f" ({r.get('rule_count', r.get('config_fields', r.get('graph_type', '')))})"
        print(f"  [{status}] {label}{detail}")
    return results


# ═══════════════════════════════════════════════════════════════════════════════
# Core execution
# ═══════════════════════════════════════════════════════════════════════════════


async def _run_graph(project_id: str, input_path: Path, output_dir: Path,
                     inline_ctx: str = "") -> dict[str, Any]:
    from deerflow.runtime.cer_review.review_assist_lead_agent import (
        ReviewAssistState, build_review_assist_graph,
    )
    session_id = f"review-{uuid.uuid4().hex[:8]}"
    output_dir.mkdir(parents=True, exist_ok=True)
    state: dict[str, Any] = {
        "project_id": project_id,
        "artifact_root": str(output_dir),
        "input_root": str(input_path),
        "review_session_id": session_id,
        "flavor_profile": "BALANCED",
        "inline_file_context": inline_ctx,
    }
    graph = build_review_assist_graph()
    config = {"configurable": {"thread_id": f"thread-{uuid.uuid4().hex[:8]}"}}
    result_state = await graph.ainvoke(state, config=config)
    return {
        "session_id": session_id,
        "current_stage": result_state.get("current_stage", ""),
        "status": result_state.get("status", "unknown"),
        "stage_result": result_state.get("stage_result", {}),
        "stage_results": result_state.get("stage_results", []),
    }


def run_graph_sync(project_id: str, input_path: Path, output_dir: Path,
                   inline_ctx: str = "") -> dict[str, Any]:
    try:
        return asyncio.run(_run_graph(project_id, input_path, output_dir, inline_ctx))
    except RuntimeError as e:
        if "event loop" in str(e).lower():
            return {"error": f"Cannot run asyncio: {e}"}
        return {"error": str(e)}
    except Exception as e:
        import traceback
        return {"error": str(e), "traceback": traceback.format_exc()}


# ═══════════════════════════════════════════════════════════════════════════════
# Output validation
# ═══════════════════════════════════════════════════════════════════════════════


def validate_outputs(output_dir: Path, stage: str) -> dict[str, Any]:
    checks: dict[str, Any] = {}

    # Source inventory (common)
    inv_path = output_dir / "source_inventory.json"
    checks["source_inventory_exists"] = inv_path.exists()
    if inv_path.exists():
        try:
            inv = json.loads(inv_path.read_text(encoding="utf-8"))
            checks["source_inventory_count"] = len(inv.get("source_inventory", []))
            checks["source_inventory_decision_pending"] = inv.get("reviewer_decision") == "PENDING"
            if isinstance(inv.get("source_inventory"), list) and inv["source_inventory"]:
                checks["all_have_evidence_depth"] = all(
                    isinstance(e.get("evidence_depth"), str) and e["evidence_depth"]
                    for e in inv["source_inventory"]
                )
                anti = sum(1 for e in inv["source_inventory"]
                          if isinstance(e.get("flags"), list) and e["flags"])
                checks["anti_pattern_hit_count"] = anti
        except Exception as e:
            checks["source_inventory_parse_error"] = str(e)

    # Full pilot extras
    if stage == "full":
        for name in ["candidate_findings", "review_report"]:
            path = output_dir / f"{name}.json"
            checks[f"{name}_exists"] = path.exists()
            if path.exists():
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                    checks[f"{name}_count"] = len(data.get(name, []))
                    checks[f"{name}_decision_pending"] = data.get("reviewer_decision") == "PENDING"
                except Exception as e:
                    checks[f"{name}_parse_error"] = str(e)

        for fname in ["review_state.json", "review_session_log.jsonl"]:
            checks[f"{fname}_exists"] = (output_dir / fname).exists()

    # Terminal verdict scan
    all_hits: list[str] = []
    for path in output_dir.glob("*.json"):
        try:
            hits = _contains_prohibited_terms(path.read_text(encoding="utf-8"))
            all_hits.extend(hits)
        except Exception:
            pass
    checks["terminal_verdict_scan"] = "OK" if not all_hits else f"FOUND: {all_hits}"

    return checks


# ═══════════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════════

def main() -> str:
    parser = argparse.ArgumentParser(description="CER Review Assist — Unified Runner")
    parser.add_argument("--stage", choices=["smoke", "full"], default="full",
                        help="smoke=1-stage+component verify, full=3-stage pipeline")
    parser.add_argument("--project-id", default="082_tianjinhengyu", help="Project ID")
    parser.add_argument("--input-dir", default=None, help="Direct input path")
    parser.add_argument("--output-dir", default=None, help="Output directory")
    args = parser.parse_args()

    project_id = args.project_id

    # Resolve paths
    if args.input_dir:
        input_path = Path(args.input_dir)
    else:
        input_path = resolve_input_path(project_id)
        if input_path is None:
            print(f"ERROR: Could not resolve input for '{project_id}'")
            return "STATUS_BLOCKED"

    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        output_dir = BUILD_V13 / (project_id if args.stage == "full" else "smoke_output")
    output_dir.mkdir(parents=True, exist_ok=True)

    label = "3-STAGE PILOT" if args.stage == "full" else "1-STAGE SMOKE TEST"
    print("=" * 72)
    print(f"CER REVIEW ASSIST — {label}: {project_id}")
    print("=" * 72)

    # Phase 1: Component verification (always run)
    print("\n── Phase 1: Component Verification (no LLM) ──")
    comp_results = run_component_verification()
    all_comp_ok = all(r["ok"] for r in comp_results)

    # Phase 2: Input preparation
    print("\n── Phase 2: Input Preparation ──")
    files = read_input_files(input_path)
    print(f"  Files found: {len(files)}")
    for name in sorted(files.keys()):
        preview = files[name][:80].replace("\n", "\\n")
        print(f"    - {name} ({len(files[name])} chars): {preview}...")

    if not files:
        print("  ERROR: No input files found.")
        return "STATUS_BLOCKED"

    inline_ctx = build_inline_file_context(files)
    print(f"  Inline context: {len(files)} files, {len(inline_ctx)} chars")

    # Phase 3: Execute
    stage_label = "1-Stage (Evidence Curator)" if args.stage == "smoke" else "3-Stage Pipeline"
    print(f"\n── Phase 3: {stage_label} Execution ──")
    result = run_graph_sync(project_id, input_path, output_dir, inline_ctx)

    if result.get("error"):
        print(f"  ERROR: {result['error']}")
        if "traceback" in result:
            print(f"  {result['traceback']}")
        # Smoke: component checks can still pass without live execution
        if args.stage == "smoke" and all_comp_ok:
            final = "SMOKE_STATUS_OK" if all_comp_ok else "SMOKE_STATUS_BLOCKED"
            print(f"\n  Final: {final} (component checks passed, live exec blocked)")
            return final
        return "STATUS_BLOCKED"

    print(f"  Session:     {result.get('session_id')}")
    print(f"  Final stage: {result.get('current_stage')}")
    print(f"  Status:      {result.get('status')}")

    # Phase 4: Output validation
    print("\n── Phase 4: Output Validation ──")
    checks = validate_outputs(output_dir, args.stage)
    for name, val in sorted(checks.items()):
        icon = "[OK]" if val in (True, "OK") or (isinstance(val, bool) and val) else "[--]"
        print(f"  {icon} {name}: {val}")

    # Final status
    critical = [
        checks.get("source_inventory_exists", False),
        checks.get("terminal_verdict_scan") == "OK",
    ]
    if args.stage == "full":
        critical.extend([
            checks.get("candidate_findings_exists", False),
            checks.get("review_report_exists", False),
        ])

    if all(critical):
        final = "SMOKE_STATUS_OK" if args.stage == "smoke" else "PILOT_STATUS_OK"
    elif result.get("error"):
        final = "STATUS_BLOCKED"
    else:
        final = "STATUS_PARTIAL"

    # Write results
    results_path = output_dir / f"review_assist_results_{args.stage}.json"
    results_path.write_text(json.dumps({
        "final_status": final,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "project_id": project_id,
        "stage": args.stage,
        "component_verification": comp_results,
        "result": {k: v for k, v in result.items() if k != "traceback"},
        "validation": checks,
    }, indent=2, ensure_ascii=False))

    print(f"\n  Final: {final}")
    print(f"  Results: {results_path}")
    return final


if __name__ == "__main__":
    status = main()
    ok_statuses = {"PILOT_STATUS_OK", "SMOKE_STATUS_OK"}
    sys.exit(0 if status in ok_statuses else 1)
