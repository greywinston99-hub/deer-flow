"""CCD-interactive pilot runner with optional auto-confirm mode for full-graph validation.

Usage:
  # Production mode — pauses at each HC interrupt (human confirms via --resume)
  CER_AUTHORING_STRICT_V7=1 CER_AUTHORING_ENABLE_LLM_AGENTS=1 \
    python run_cer_authoring_pilot.py --project-id X --input-root ... --artifact-root ... --strict-v7

  # Auto-confirm mode — auto-resumes through all 42 nodes for validation
  CER_AUTHORING_STRICT_V7=1 CER_AUTHORING_ENABLE_LLM_AGENTS=1 \
    python run_cer_authoring_pilot.py --project-id X --input-root ... --artifact-root ... --strict-v7 --auto-confirm
"""
from __future__ import annotations

import argparse, asyncio, json, os, sys, time, traceback
from pathlib import Path

os.environ.setdefault("CER_AUTHORING_STRICT_V7", "1")
os.environ.setdefault("CER_AUTHORING_ENABLE_LLM_AGENTS", "1")

# Suppress httpx event-loop-closed cleanup noise (Python 3.12 + httpx + langgraph).
# This patches BaseEventLoop.call_exception_handler to drop known-cosmetic
# "Event loop is closed" RuntimeErrors from httpx.AsyncClient.aclose() cleanup.
_asyncio_call_exc_original = asyncio.base_events.BaseEventLoop.call_exception_handler


def _noisy_cleanup_filter(self: asyncio.base_events.BaseEventLoop, context: dict) -> None:
    exc = context.get("exception")
    if isinstance(exc, RuntimeError) and "Event loop is closed" in str(exc):
        return
    _asyncio_call_exc_original(self, context)


asyncio.base_events.BaseEventLoop.call_exception_handler = _noisy_cleanup_filter

from deerflow.runtime.cer_authoring.graph import build_cer_authoring_graph
from langgraph.types import Command

MAX_AUTO_INTERRUPTS = 72  # safety ceiling for --auto-confirm


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--input-root", required=True)
    parser.add_argument("--artifact-root", required=True)
    parser.add_argument("--target-keywords", default="")
    parser.add_argument("--strict-v7", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--resume", action="store_true",
                        help="Resume from last interrupt with confirmed=True")
    parser.add_argument("--auto-confirm", action="store_true",
                        help="Auto-resume through all HC interrupts for full 42-node validation")
    parser.add_argument("--max-interrupts", type=int, default=MAX_AUTO_INTERRUPTS,
                        help=f"Max auto-resumes before giving up (default: {MAX_AUTO_INTERRUPTS})")
    args = parser.parse_args()

    input_root = Path(args.input_root).expanduser().resolve()
    artifact_root = Path(args.artifact_root).expanduser().resolve()
    artifact_root.mkdir(parents=True, exist_ok=True)

    cp_ctx = None
    checkpointer = None
    try:
        if args.auto_confirm:
            from deerflow.agents.checkpointer.provider import checkpointer_context
            cp_ctx = checkpointer_context()
            checkpointer = cp_ctx.__enter__()

        graph = build_cer_authoring_graph(checkpointer=checkpointer)
        config = {"configurable": {"thread_id": args.project_id}}

        if args.resume:
            state: dict | Command = Command(resume={"confirmed": True, "action": "confirm"})
            print("[CCD] Resuming from last interrupt with confirmed=True...", file=sys.stderr)
        else:
            state = {
                "messages": [],
                "project_id": args.project_id,
                "input_root": str(input_root),
                "supplement_roots": [],
                "artifact_root": str(artifact_root),
                "target_keywords": [k.strip() for k in args.target_keywords.split(",") if k.strip()],
                "agent_team_mode": "stable-1plus6",
            }
            print("[CCD] Starting fresh run...", file=sys.stderr)

        if args.auto_confirm:
            return _auto_confirm_loop(graph, state, config, args)
        else:
            return _single_invoke(graph, state, config)
    finally:
        if cp_ctx is not None:
            try:
                cp_ctx.__exit__(None, None, None)
            except Exception:
                pass


# ── Dashboard ─────────────────────────────────────────────────────────────

_DAG_FLOW = {
    "device_profile": ["claim_decomposition"],
    "claim_decomposition": ["pico_derivation"],
    "pico_derivation": ["methodology_review"],
    "methodology_review": ["sota_search"],
    "sota_search": ["retrieval_domain_gate", "device_equivalence_search"],
    "evidence_appraisal": ["fulltext_basis_gate"],
    "endpoint_extraction": ["sota_endpoint_gate"],
    "sota_endpoint_gate": ["pre_g42_claim_evidence_candidate_linking"],
    "evidence_sufficiency_gate": ["claim_evidence_matrix", "query_expansion", "controlled_compromise"],
    "query_expansion": ["sota_search"],
    "claim_evidence_matrix": ["claim_evidence_gate"],
    "cer_writing": ["human_style_review"],
    "human_style_review": ["nb_precheck"],
    "nb_precheck": ["workbook"],
    "workbook": ["gates"],
    "gates": ["self_inspection"],
    "self_inspection": ["export"],
    "export": [],
    "controlled_compromise": ["cer_writing"],
}

_DASHBOARD_STARTED = time.time()
_NODE_STARTED: dict[str, float] = {}
_CURRENT_NODE = "starting"


def _write_dashboard(artifact_root: str, node: str, state_dict: dict | None = None) -> str:
    """Write dashboard.json with live pipeline progress."""
    import psutil as _pu
    dashboard = {
        "project_id": state_dict.get("project_id", "unknown") if state_dict else "unknown",
        "status": "running",
        "started_at": time.strftime("%H:%M:%S", time.localtime(_DASHBOARD_STARTED)),
        "elapsed": f"{time.time() - _DASHBOARD_STARTED:.0f}s",
        "current_node": node,
        "node_elapsed": f"{time.time() - _NODE_STARTED.get(node, time.time()):.0f}s" if node in _NODE_STARTED else "0s",
        "next_nodes": _DAG_FLOW.get(node, []),
        "interrupt_count": state_dict.get("_dashboard_interrupt_count", 0) if state_dict else 0,
        "spiral_round": state_dict.get("rework_gate_counter", 0) if state_dict else 0,
        "memory_mb": f"{_pu.Process().memory_info().rss / 1024 / 1024:.0f}",
    }
    # Evidence funnel counts from state
    if state_dict:
        dashboard.update({
            "source_files": len(state_dict.get("source_inventory", [])),
            "claims": len(state_dict.get("claim_ledger", [])),
            "literature_searched": sum(
                int(r.get("hits", 0)) for r in state_dict.get("search_run_registry", []) if isinstance(r, dict)
            ),
            "literature_screened": len(state_dict.get("screening_disposition", [])),
            "literature_included": len(state_dict.get("evidence_registry", [])),
            "sota_endpoints": len(state_dict.get("sota_benchmark_matrix", [])),
        })
    path = Path(artifact_root) / "dashboard.json"
    path.write_text(json.dumps(dashboard, ensure_ascii=False, indent=2))
    return _render_dashboard_card(dashboard)


def _render_dashboard_card(d: dict) -> str:
    """Render dashboard as a compact status card."""
    next_nodes = d.get("next_nodes", [])
    next_str = " → ".join(next_nodes[:3]) if next_nodes else "🏁 DONE"
    spiral = d.get("spiral_round", 0)
    spiral_str = f"🔄 Round {spiral}/5" if spiral > 0 else ""
    return (
        f"┌─────────────────────────────────────────┐\n"
        f"│ 🏗️  {d.get('project_id', '')[:30]:<30} │\n"
        f"│ ⏱️  {d.get('elapsed', '0s'):>8}  💾 {d.get('memory_mb', '0')}MB         │\n"
        f"│ 📍 {d.get('current_node', '?')[:20]:<20} ({d.get('node_elapsed', '0s')})       │\n"
        f"│ ➡️  {next_str[:38]:<38} │\n"
        f"│ 📚 {d.get('literature_searched', 0):>5} searched  🔍 {d.get('literature_screened', 0):>4} screened  ✅ {d.get('literature_included', 0):>4} incl │\n"
        f"│ 📝 {d.get('claims', 0):>4} claims  🎯 {d.get('sota_endpoints', 0):>4} endpoints  {spiral_str:<20} │\n"
        f"└─────────────────────────────────────────┘"
    )


# ── Auto-confirm loop ────────────────────────────────────────────────────────

def _auto_confirm_loop(graph, state, config, args) -> int:
    interrupted_at: list[str] = []
    for iteration in range(args.max_interrupts + 1):
        try:
            result = graph.invoke(state, config)
        except Exception as e:
            err_msg = str(e)
            # Without checkpointer, GraphInterrupt is raised. Auto-resume anyway.
            if "GraphInterrupt" in type(e).__name__:
                node = _extract_node_from_error(err_msg, e)
                interrupted_at.append(node)
                # Update dashboard
                try:
                    gs = graph.get_state(config)
                    sdict = gs.values if gs else {}
                    sdict["_dashboard_interrupt_count"] = iteration + 1
                    card = _write_dashboard(str(artifact_root), node, sdict)
                    print(card, file=sys.stderr)
                except Exception:
                    pass
                print(f"[CCD] ⏸️  Interrupt #{iteration + 1} at '{node}' — auto-confirming...",
                      file=sys.stderr)
                state = Command(resume={"confirmed": True, "action": "confirm"})
                continue
            tb = traceback.format_exc()
            print(f"[CCD] Fatal error: {err_msg[:200]}", file=sys.stderr)
            print(f"[CCD] Traceback (last 3 frames):", file=sys.stderr)
            for line in tb.split("\n")[-8:]:
                if line.strip():
                    print(f"  {line}", file=sys.stderr)
            # Try to get last known state
            last_status = "unknown"
            try:
                gs = graph.get_state(config)
                if gs and gs.values:
                    last_status = gs.values.get("status", "unknown")
            except Exception:
                pass
            summary = {"error": err_msg[:300], "status": "fatal_error",
                       "last_known_node": last_status,
                       "interrupts_handled": len(interrupted_at),
                       "interrupted_nodes": interrupted_at}
            print(json.dumps(summary, ensure_ascii=False, indent=2))
            return 3

        # With checkpointer: interrupt() saves state and returns. Check for
        # pending interrupts via graph.get_state().
        gs = graph.get_state(config)
        pending = gs.interrupts if gs else []
        if pending:
            for entry in pending:
                node = _extract_node_from_error(str(entry), None)
                interrupted_at.append(node)
            # Update dashboard
            try:
                sdict = gs.values if gs else {}
                sdict["_dashboard_interrupt_count"] = iteration + 1
                card = _write_dashboard(str(artifact_root), interrupted_at[-1], sdict)
                print(card, file=sys.stderr)
            except Exception:
                pass
            print(f"[CCD] ⏸️  Interrupt #{iteration + 1} at '{interrupted_at[-1]}' — "
                  f"auto-confirming... ({len(pending)} pending)",
                  file=sys.stderr)
            state = Command(resume={"confirmed": True, "action": "confirm"})
            continue

        # No interrupt pending — pipeline completed
        summary = _build_summary(result, args)
        summary["auto_confirm"] = True
        summary["interrupts_handled"] = len(interrupted_at)
        summary["interrupted_nodes"] = interrupted_at
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0 if result.get("final_gate_decision") == "PASS_TO_DRAFT_DOCX" else 2

    print(f"[CCD] Max auto-interrupts ({args.max_interrupts}) reached.", file=sys.stderr)
    return 2


# ── Single invoke (production HC-pause mode) ──────────────────────────────────

def _write_human_gate_file(artifact_root: str, node: str, info: dict) -> str:
    """Write HC gate data to a markdown file for VS Code / terminal review."""
    gate_dir = Path(artifact_root) / ".human_gate"
    gate_dir.mkdir(parents=True, exist_ok=True)
    gate_file = gate_dir / f"{node}.md"
    lines = [
        f"# ⏸️ Human Gate: {node}",
        "",
        f"**Priority**: {info.get('priority', '?')}",
        f"**Step**: {info.get('step', '?')}",
        f"**Message**: {info.get('message', 'N/A')}",
        "",
        "---",
        "",
    ]
    # Render device_profile data as table
    device_profile = info.get("device_profile")
    if device_profile and isinstance(device_profile, dict):
        lines.append("## Device Profile")
        lines.append("| Field | Value |")
        lines.append("| --- | --- |")
        for k, v in device_profile.items():
            if k != "profile_source_ids":
                lines.append(f"| {k} | {str(v)[:200]} |")
        lines.append("")
    # Render claim_ledger
    claim_ledger = info.get("claim_ledger")
    if claim_ledger and isinstance(claim_ledger, list):
        lines.append(f"## Claim Ledger ({len(claim_ledger)} claims)")
        lines.append("| ID | Type | Text |")
        lines.append("| --- | --- | --- |")
        for c in claim_ledger[:20]:
            lines.append(f"| {c.get('claim_id', '?')} | {c.get('claim_type', '?')} | {str(c.get('claim_text', ''))[:120]} |")
        lines.append("")
    # Render search runs
    search_runs = info.get("search_runs")
    if search_runs and isinstance(search_runs, list):
        lines.append(f"## Search Strategy ({len(search_runs)} searches)")
        lines.append("| DB | Terms |")
        lines.append("| --- | --- |")
        for s in search_runs[:10]:
            lines.append(f"| {s.get('database', '?')} | {str(s.get('search_terms', ''))[:150]} |")
        lines.append("")
    # Render evidence sample
    evidence_count = info.get("evidence_count")
    appraisal_sample = info.get("appraisal_sample")
    if evidence_count:
        lines.append(f"## Evidence Appraisal ({evidence_count} records)")
        if appraisal_sample:
            lines.append("| Evidence ID | Score | Weight |")
            lines.append("| --- | --- | --- |")
            for a in appraisal_sample[:10]:
                lines.append(f"| {a.get('evidence_id', '?')} | {a.get('score', '?')} | {a.get('weight', '?')} |")
        lines.append("")
    # Render endpoints
    endpoint_count = info.get("endpoint_count")
    sample_endpoints = info.get("sample_endpoints")
    if endpoint_count:
        lines.append(f"## Endpoints ({endpoint_count} extracted)")
        if sample_endpoints:
            lines.append("| ID | Endpoint | Source |")
            lines.append("| --- | --- | --- |")
            for ep in sample_endpoints[:10]:
                lines.append(f"| {ep.get('endpoint_id', '?')} | {str(ep.get('endpoint', ''))[:100]} | {ep.get('source_article', '?')} |")
        lines.append("")
    # Render sections to review (export gate)
    sections = info.get("sections_to_review")
    if sections:
        lines.append("## Sections to Review")
        for s in sections:
            lines.append(f"- {s}")
        lines.append("")
    # Footer
    lines.append("---")
    lines.append("")
    lines.append("**To continue**: run the same command with `--resume`")
    lines.append(f"**File**: `{gate_file}`")
    content = "\n".join(lines)
    gate_file.write_text(content, encoding="utf-8")
    return str(gate_file)


def _single_invoke(graph, state, config) -> int:
    try:
        result = graph.invoke(state, config)
        summary = _build_summary(result, None)
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0 if result.get("final_gate_decision") == "PASS_TO_DRAFT_DOCX" else 2
    except Exception as e:
        err_msg = str(e)
        if "GraphInterrupt" in type(e).__name__:
            interrupt_info = _extract_interrupt_info(err_msg, e)
            node = interrupt_info.get('node', 'unknown')
            message = interrupt_info.get('message', 'N/A')
            # Write gate data to file for VS Code review
            artifact_root = interrupt_info.get('artifact_root', str(Path.cwd() / "02_CER_OUTPUT"))
            gate_file = _write_human_gate_file(artifact_root, node, interrupt_info)
            print(json.dumps(interrupt_info, ensure_ascii=False, indent=2))
            print(f"\n{'='*60}", file=sys.stderr)
            print(f"[CCD] ⏸️  PIPELINE PAUSED — HUMAN CONFIRMATION REQUIRED", file=sys.stderr)
            print(f"[CCD] Node: {node}", file=sys.stderr)
            print(f"[CCD] Message: {message[:200]}", file=sys.stderr)
            print(f"[CCD] Review: {gate_file}", file=sys.stderr)
            print(f"[CCD] Action: To continue, run the same command with --resume", file=sys.stderr)
            print(f"{'='*60}", file=sys.stderr)
            return 10
        summary = {"error": err_msg[:300], "status": "fatal_error"}
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 3


# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_summary(result: dict, args) -> dict:
    return {
        "project_id": getattr(args, "project_id", "") if args else "",
        "status": result.get("status"),
        "final_gate_decision": result.get("final_gate_decision"),
        "source_count": len(result.get("source_inventory") or []),
        "claim_count": len(result.get("claim_ledger") or []),
        "evidence_count": len(result.get("evidence_registry") or []),
        "artifact_count": len(result.get("artifacts") or []),
        "llm_refined": result.get("llm_refinement_applied", False),
        "writer_quality": (result.get("writer_quality_report") or {}).get("writer_quality_pct"),
        "argument_flow": (result.get("argument_flow_report") or {}).get("overall_flow"),
        "artifacts": (result.get("artifacts") or [])[:10],
    }


def _extract_interrupt_info(err_msg: str, exc: Exception) -> dict:
    info = {"node": "unknown", "message": err_msg[:500], "step": "?"}
    if hasattr(exc, 'args') and exc.args:
        for arg in exc.args:
            if isinstance(arg, dict):
                info["message"] = str(arg.get("message", arg))[:500]
                info["node"] = str(arg.get("confirmation_point", arg.get("node", "unknown")))
                info["step"] = str(arg.get("step", "?"))
                info["priority"] = str(arg.get("priority", "?"))
                info["sections"] = arg.get("sections_to_review", [])
    return info


def _extract_node_from_error(err_msg: str, exc: Exception | None = None) -> str:
    if exc and hasattr(exc, 'args') and exc.args:
        for arg in exc.args:
            if isinstance(arg, dict):
                node = arg.get("confirmation_point", arg.get("node", ""))
                if node:
                    return str(node)
    for keyword in ["device_profile", "claim_decomposition", "sota_search",
                    "evidence_appraisal", "endpoint_extraction", "cer_writing",
                    "gates", "export", "pre_writer", "human_style"]:
        if keyword in err_msg.lower():
            return keyword
    return "unknown"


if __name__ == "__main__":
    raise SystemExit(main())
