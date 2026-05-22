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

import argparse, json, os, sys, time, traceback
from pathlib import Path

os.environ.setdefault("CER_AUTHORING_STRICT_V7", "1")
os.environ.setdefault("CER_AUTHORING_ENABLE_LLM_AGENTS", "1")

from deerflow.runtime.cer_authoring.graph import build_cer_authoring_graph
from langgraph.types import Command

MAX_AUTO_INTERRUPTS = 24  # safety ceiling for --auto-confirm


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
            print(json.dumps(interrupt_info, ensure_ascii=False, indent=2))
            print(f"\n{'='*60}", file=sys.stderr)
            print(f"[CCD] ⏸️  PIPELINE PAUSED — HUMAN CONFIRMATION REQUIRED", file=sys.stderr)
            print(f"[CCD] Node: {interrupt_info.get('node', 'unknown')}", file=sys.stderr)
            print(f"[CCD] Message: {interrupt_info.get('message', 'N/A')[:200]}", file=sys.stderr)
            print(f"[CCD] Action: Review the above. To continue, run the same command with --resume",
                  file=sys.stderr)
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
