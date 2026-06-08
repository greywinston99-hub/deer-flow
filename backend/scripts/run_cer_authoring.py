"""Run the isolated CER authoring graph for a source package.

Usage:
  # Network mode:
  #   Default is direct Kimi/DeepSeek API access with HTTP(S)_PROXY cleared.
  #   DEERFLOW_NETWORK_MODE=preserve keeps HTTP(S)_PROXY only for diagnostics.
  #
  # Production mode — pauses at each HC interrupt (human confirms via --resume)
  CER_AUTHORING_STRICT_V7=1 CER_AUTHORING_ENABLE_LLM_AGENTS=1 \\
    python run_cer_authoring.py --project-id X --input-root ... --artifact-root ... --strict-v7

  # Auto-confirm mode — auto-resumes through all 42 nodes for validation
  CER_AUTHORING_STRICT_V7=1 CER_AUTHORING_ENABLE_LLM_AGENTS=1 \\
    python run_cer_authoring.py --project-id X --input-root ... --artifact-root ... --strict-v7 --auto-confirm

  # With supplement folders and custom agent team
  python run_cer_authoring.py --project-id X --input-root ... --artifact-root ... \\
    --supplement-root /path/to/rmf --supplement-root /path/to/gspr \\
    --agent-team-mode stable-1plus6 --target-keywords "keyword1,keyword2"
"""

from __future__ import annotations

import argparse, asyncio, importlib, json, os, subprocess, sys, time, threading, traceback
from pathlib import Path

from deerflow.utils.network import force_direct_api_network

force_direct_api_network()

_NATIVE_PRELOADS = ("pandas._libs.writers",)


def _preload_native_modules_before_deerflow_import() -> dict[str, str]:
    status: dict[str, str] = {}
    for module_name in _NATIVE_PRELOADS:
        try:
            importlib.import_module(module_name)
        except Exception as exc:
            status[module_name] = f"unavailable:{type(exc).__name__}:{exc}"
        else:
            status[module_name] = "loaded"
    return status


_NATIVE_PRELOAD_STATUS = _preload_native_modules_before_deerflow_import()

os.environ.setdefault("CER_AUTHORING_STRICT_V7", "1")
os.environ.setdefault("CER_AUTHORING_ENABLE_LLM_AGENTS", "1")

# Suppress httpx event-loop-closed cleanup noise (Python 3.12 + httpx + langgraph).
_asyncio_call_exc_original = asyncio.base_events.BaseEventLoop.call_exception_handler


def _noisy_cleanup_filter(self: asyncio.base_events.BaseEventLoop, context: dict) -> None:
    exc = context.get("exception")
    if isinstance(exc, RuntimeError) and "Event loop is closed" in str(exc):
        return
    _asyncio_call_exc_original(self, context)


asyncio.base_events.BaseEventLoop.call_exception_handler = _noisy_cleanup_filter

from deerflow.runtime.cer_authoring.graph import build_cer_authoring_graph
from langgraph.types import Command

DEFAULT_STRICT_AUTHORING_MODEL = "kimi-k2.6-api"
MAX_AUTO_INTERRUPTS = 72


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run cer_authoring_v1 against an IFU/source package."
    )
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--input-root", required=True)
    parser.add_argument("--artifact-root", required=True)
    parser.add_argument(
        "--supplement-root",
        action="append",
        default=[],
        help="Additional source folders to search for RMF/GSPR/PMS/performance files. May be provided multiple times.",
    )
    parser.add_argument("--target-keywords", default="")
    parser.add_argument(
        "--agent-team-mode",
        choices=["stable-1plus6", "legacy-20"],
        default="stable-1plus6",
        help="Physical CER authoring agent team mode. stable-1plus6 is the production default; legacy-20 is for comparison only.",
    )
    parser.add_argument(
        "--model-name",
        default="",
        help="Optional parent model name inherited by authoring subagents.",
    )
    parser.add_argument("--strict-v7", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from last interrupt with confirmed=True",
    )
    parser.add_argument(
        "--rework-to",
        default="",
        help="Resume and rewind to a specific upstream node (use with --resume). "
             "Example: --resume --rework-to sota_search_strategy",
    )
    parser.add_argument(
        "--rework-reason",
        default="",
        help="Reason for rework (shown in HC rework metadata).",
    )
    parser.add_argument(
        "--auto-confirm",
        action="store_true",
        help="Auto-resume through all HC interrupts for full 42-node validation",
    )
    parser.add_argument(
        "--max-interrupts",
        type=int,
        default=MAX_AUTO_INTERRUPTS,
        help=f"Max auto-resumes before giving up (default: {MAX_AUTO_INTERRUPTS})",
    )
    args = parser.parse_args()

    if args.rework_to and not args.resume:
        parser.error("--rework-to requires --resume")

    if args.strict_v7:
        os.environ["CER_AUTHORING_STRICT_V7"] = "1"
        os.environ["CER_AUTHORING_ENABLE_LLM_AGENTS"] = "1"
    os.environ["CER_AUTHORING_AGENT_TEAM_MODE"] = args.agent_team_mode
    model_name = (
        args.model_name
        or os.environ.get("CER_AUTHORING_MODEL_NAME")
        or (DEFAULT_STRICT_AUTHORING_MODEL if args.strict_v7 else None)
    )
    if model_name:
        os.environ["CER_AUTHORING_MODEL_NAME"] = model_name

    input_root = Path(args.input_root).expanduser().resolve()
    artifact_root = Path(args.artifact_root).expanduser().resolve()
    artifact_root.mkdir(parents=True, exist_ok=True)

    if os.environ.get("CER_AUTHORING_ENABLE_LLM_AGENTS") == "1" or args.strict_v7:
        _llm_provider_preflight_or_exit(artifact_root)

    # ── 1: Log cleanup — archive logs older than 24h ──
    _cleanup_old_logs(artifact_root)

    # ── 2: Pre-flight checks ──
    _preflight_checks(input_root, artifact_root)

    supplement_roots = [str(Path(item).expanduser().resolve()) for item in args.supplement_root]

    cp_ctx = None
    checkpointer = None
    try:
        # FIX (2026-06-07, RCA A06_南驰): Always use SqliteSaver for persistence.
        # Previously auto-confirm used InMemorySaver which caused device_profile loops
        # because build_device_profile() results were lost between interrupts.
        # SqliteSaver thread deadlock was resolved by StructuredTool patch and model routing fix.
        try:
            from langgraph.checkpoint.sqlite import SqliteSaver
            legacy_db = Path(artifact_root).parent.parent / ".deer-flow" / f"checkpoints_{args.project_id}.db"
            db_path = Path(artifact_root) / ".checkpoints.db"
            if legacy_db.exists():
                db_path = legacy_db
            conn_str = str(db_path)
            cp_ctx = SqliteSaver.from_conn_string(conn_str)
            checkpointer = cp_ctx.__enter__()
            checkpointer.setup()
            mode = "auto-confirm" if args.auto_confirm else "production"
            print(f"[CCD] Using SqliteSaver ({conn_str}) — persistent across restarts [{mode} mode]", file=sys.stderr)
        except ImportError:
            from langgraph.checkpoint.memory import InMemorySaver
            checkpointer = InMemorySaver()
            print("[CCD] WARNING: SqliteSaver not available, using InMemorySaver (NON-PERSISTENT)", file=sys.stderr)

        graph = build_cer_authoring_graph(checkpointer=checkpointer)
        config = {
            "configurable": {"thread_id": args.project_id},
            "max_concurrency": 32,
        }

        if args.resume:
            if args.rework_to:
                resume_value = {
                    "action": "rework",
                    "target": args.rework_to,
                    "reason": args.rework_reason or "Manual rework requested",
                }
                print(f"[CCD] Resuming with rework → {args.rework_to}...", file=sys.stderr)
                state = Command(resume=resume_value)
            else:
                # Bug 1 fix: Don't auto-confirm. Use special marker so
                # _single_invoke detects the pending interrupt and enters
                # the normal polling loop — the human must review each gate.
                print("[CCD] Resuming — will poll at current HC gate...", file=sys.stderr)
                state = Command(resume={"_resume_poll": True})
        else:
            state = {
                "messages": [],
                "project_id": args.project_id,
                "input_root": str(input_root),
                "supplement_roots": supplement_roots,
                "artifact_root": str(artifact_root),
                "target_keywords": [k.strip() for k in args.target_keywords.split(",") if k.strip()],
                "agent_team_mode": args.agent_team_mode,
                "model_name": model_name,
                "native_preload_status": _NATIVE_PRELOAD_STATUS,
            }
            print("[CCD] Starting fresh run...", file=sys.stderr)

        if args.auto_confirm:
            return _auto_confirm_loop(graph, state, config, args)
        else:
            return _single_invoke(graph, state, config, str(artifact_root))
    finally:
        if cp_ctx is not None:
            _cleanup_watchdog = threading.Timer(30.0, lambda: os._exit(0))
            _cleanup_watchdog.daemon = True
            _cleanup_watchdog.start()
            try:
                cp_ctx.__exit__(None, None, None)
            except Exception:
                pass
            _cleanup_watchdog.cancel()


# ── Dashboard ─────────────────────────────────────────────────────────────


def _llm_provider_preflight_or_exit(artifact_root: Path) -> None:
    """Fail before graph execution if DeepSeek/Kimi routing is not ready.

    CER Authoring is intentionally configured for DeepSeek + Kimi only. Missing
    `ANTHROPIC_API_KEY` is not an error in this deployment, even when the
    Kimi API is accessed directly through the Moonshot OpenAI-compatible API.
    """

    from deerflow.runtime.cer_authoring.writer_remediation.model_routing import build_provider_preflight

    report = build_provider_preflight()
    report_path = artifact_root / "llm_provider_preflight_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if report.get("status") == "PASS":
        print("[LLM_PREFLIGHT] PASS — DeepSeek/Kimi API providers configured. ANTHROPIC_API_KEY is not required.", file=sys.stderr)
        return
    message = {
        "status": "BLOCKED_PROVIDER_UNAVAILABLE",
        "reason": "DeepSeek/Kimi API provider preflight failed before CER graph execution.",
        "important": "Do not fix this by adding ANTHROPIC_API_KEY. This CER stack is configured for DeepSeek/Kimi API only.",
        "report_path": str(report_path),
        "missing_providers": report.get("missing_providers", {}),
    }
    print(json.dumps(message, ensure_ascii=False, indent=2), file=sys.stderr)
    raise SystemExit(78)

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
        "node_elapsed": f"{time.time() - _NODE_STARTED.get(node, time.time()):.0f}s"
        if node in _NODE_STARTED
        else "0s",
        "next_nodes": _DAG_FLOW.get(node, []),
        "interrupt_count": state_dict.get("_dashboard_interrupt_count", 0) if state_dict else 0,
        "spiral_round": state_dict.get("rework_gate_counter", 0) if state_dict else 0,
        "memory_mb": f"{_pu.Process().memory_info().rss / 1024 / 1024:.0f}",
    }
    if state_dict:
        dashboard.update(
            {
                "source_files": len(state_dict.get("source_inventory", [])),
                "claims": len(state_dict.get("claim_ledger", [])),
                "literature_searched": sum(
                    int(r.get("hits", 0))
                    for r in state_dict.get("search_run_registry", [])
                    if isinstance(r, dict)
                ),
                "literature_screened": len(state_dict.get("screening_disposition", [])),
                "literature_included": len(state_dict.get("evidence_registry", [])),
                "sota_endpoints": len(state_dict.get("sota_benchmark_matrix", [])),
            }
        )
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


# ── Auto-confirm loop ────────────────────────────────────────────────────

_GRAPH_INVOKE_TIMEOUT = int(os.getenv("CER_GRAPH_INVOKE_TIMEOUT", "600"))
_MAX_SAME_AUTO_CONFIRM_GATE = int(os.getenv("CER_MAX_SAME_AUTO_CONFIRM_GATE", "10"))  # FIX (2026-06-07, RCA A06_南驰): Increased from 2 to 10; SqliteSaver persistence prevents true loops


def _same_tail_count(items: list[str], value: str) -> int:
    count = 0
    for item in reversed(items):
        if item != value:
            break
        count += 1
    return count


def _auto_confirm_loop(graph, state, config, args) -> int:
    interrupted_at: list[str] = []
    artifact_root = (
        state.get("artifact_root", "")
        if isinstance(state, dict)
        else getattr(args, "artifact_root", "")
    )
    for iteration in range(args.max_interrupts + 1):
        try:
            invoke_result: list = [None]
            invoke_error: list = [None]

            def _invoke():
                try:
                    invoke_result[0] = graph.invoke(state, config)
                except Exception as exc:
                    invoke_error[0] = exc

            t = threading.Thread(target=_invoke, daemon=True)
            t.start()
            t.join(timeout=_GRAPH_INVOKE_TIMEOUT)
            if t.is_alive():
                print(
                    f"[CCD] graph.invoke() timed out after {_GRAPH_INVOKE_TIMEOUT}s — "
                    f"LangGraph thread pool likely deadlocked; forcing exit.",
                    file=sys.stderr,
                )
                os._exit(4)
            if invoke_error[0] is not None:
                raise invoke_error[0]
            result = invoke_result[0]
        except Exception as e:
            err_msg = str(e)
            if "GraphInterrupt" in type(e).__name__:
                node = _extract_node_from_error(err_msg, e)
                interrupted_at.append(node)
                if _same_tail_count(interrupted_at, node) > _MAX_SAME_AUTO_CONFIRM_GATE:
                    summary = {
                        "status": "auto_confirm_repeated_gate_blocked",
                        "human_gate_mode": "validation_auto_confirm",
                        "auto_confirm": True,
                        "blocked_node": node,
                        "interrupts_handled": len(interrupted_at),
                        "interrupted_nodes": interrupted_at,
                        "message": (
                            f"Auto-confirm saw '{node}' more than {_MAX_SAME_AUTO_CONFIRM_GATE} times consecutively. "
                            "Stopping validation so a real HC decision or code fix can handle the loop."
                        ),
                    }
                    print(json.dumps(summary, ensure_ascii=False, indent=2))
                    return 5
                try:
                    gs = graph.get_state(config)
                    sdict = gs.values if gs else {}
                    sdict["_dashboard_interrupt_count"] = iteration + 1
                    card = _write_dashboard(str(artifact_root), node, sdict)
                    print(card, file=sys.stderr)
                except Exception:
                    pass
                print(
                    f"[CCD] ⏸️  Interrupt #{iteration + 1} at '{node}' — auto-confirming...",
                    file=sys.stderr,
                )
                state = Command(resume={"confirmed": True, "action": "confirm"})
                continue
            tb = traceback.format_exc()
            print(f"[CCD] Fatal error: {err_msg[:200]}", file=sys.stderr)
            print(f"[CCD] Traceback (last 3 frames):", file=sys.stderr)
            for line in tb.split("\n")[-8:]:
                if line.strip():
                    print(f"  {line}", file=sys.stderr)
            last_status = "unknown"
            try:
                gs = graph.get_state(config)
                if gs and gs.values:
                    last_status = gs.values.get("status", "unknown")
            except Exception:
                pass
            summary = {
                "error": err_msg[:300],
                "status": "fatal_error",
                "last_known_node": last_status,
                "interrupts_handled": len(interrupted_at),
                "interrupted_nodes": interrupted_at,
            }
            print(json.dumps(summary, ensure_ascii=False, indent=2))
            return 3

        gs = graph.get_state(config)
        pending = gs.interrupts if gs else []
        if pending:
            for entry in pending:
                node = _extract_node_from_error(str(entry), None)
                interrupted_at.append(node)
            repeated_node = interrupted_at[-1] if interrupted_at else "unknown"
            if _same_tail_count(interrupted_at, repeated_node) > _MAX_SAME_AUTO_CONFIRM_GATE:
                summary = {
                    "status": "auto_confirm_repeated_gate_blocked",
                    "human_gate_mode": "validation_auto_confirm",
                    "auto_confirm": True,
                    "blocked_node": repeated_node,
                    "interrupts_handled": len(interrupted_at),
                    "interrupted_nodes": interrupted_at,
                    "message": (
                        f"Auto-confirm saw '{repeated_node}' more than {_MAX_SAME_AUTO_CONFIRM_GATE} times consecutively. "
                        "Stopping validation so a real HC decision or code fix can handle the loop."
                    ),
                }
                print(json.dumps(summary, ensure_ascii=False, indent=2))
                return 5
            try:
                sdict = gs.values if gs else {}
                sdict["_dashboard_interrupt_count"] = iteration + 1
                card = _write_dashboard(str(artifact_root), interrupted_at[-1], sdict)
                print(card, file=sys.stderr)
            except Exception:
                pass
            print(
                f"[CCD] ⏸️  Interrupt #{iteration + 1} at '{interrupted_at[-1]}' — "
                f"auto-confirming... ({len(pending)} pending)",
                file=sys.stderr,
            )
            state = Command(resume={"confirmed": True, "action": "confirm"})
            continue

        # No interrupt pending — pipeline completed
        summary = _build_summary(result, args)
        summary["auto_confirm"] = True
        summary["interrupts_handled"] = len(interrupted_at)
        summary["interrupted_nodes"] = interrupted_at
        summary["node_timing"] = _node_timing_report(interrupted_at)
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        status = result.get("final_gate_decision", "completed")
        _notify("CER Pipeline Done", f"{args.project_id}: {status}")
        _shutdown_watchdog = threading.Timer(30.0, lambda: os._exit(0))
        _shutdown_watchdog.daemon = True
        _shutdown_watchdog.start()
        _vacuum_checkpoint(args.project_id)
        _shutdown_watchdog.cancel()
        return 0 if result.get("final_gate_decision") == "PASS_TO_DRAFT_DOCX" else 2

    print(f"[CCD] Max auto-interrupts ({args.max_interrupts}) reached.", file=sys.stderr)
    return 2


# ── Single invoke (production HC-pause mode) ──────────────────────────────
# Response-file driven: the process stays alive across HC gates.  Instead of
# printing "run --resume" and returning exit code 10, it writes a gate review
# file (.md) and a response template (response.json) into .human_gate/, then
# polls response.json every 2 s.  When the human saves an action, the process
# resumes the graph automatically.  No process restart needed.
#
# Supported actions in response.json:
#   {"action": "confirm"}                    → approve and continue forward
#   {"action": "rework", "target": "<node>"} → rewind to upstream node
#   {"action": "correct", "corrections": {}} → apply corrections and continue

_HC_POLL_INTERVAL = float(os.getenv("CER_HC_POLL_INTERVAL", "2"))  # seconds between response.json checks
_HC_POLL_TIMEOUT = float(os.getenv("CER_HC_POLL_TIMEOUT", "0"))    # 0 = wait forever; >0 = seconds before giving up


def _write_response_template(artifact_root: str, node: str, rework_targets: list[str]) -> Path:
    """Write (or overwrite) the response.json template for this HC gate."""
    gate_dir = Path(artifact_root) / ".human_gate"
    gate_dir.mkdir(parents=True, exist_ok=True)
    resp_path = gate_dir / "response.json"
    # Atomic write: write to temp then rename so poller never sees a half-written file
    tmp_path = gate_dir / ".response.json.tmp"
    # Bug 1 fix: Include gate_node so _poll_response can detect stale files
    template = {"action": "", "target": "", "reason": "", "gate_node": node}
    if rework_targets:
        template["rework_targets"] = rework_targets
    tmp_path.write_text(json.dumps(template, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.rename(resp_path)
    return resp_path


def _poll_response(artifact_root: str, node: str) -> dict[str, Any] | None:
    """Poll .human_gate/response.json until the human writes a valid action.

    Returns the parsed response dict, or None on timeout / graceful exit.
    """
    resp_path = Path(artifact_root) / ".human_gate" / "response.json"
    last_mtime = resp_path.stat().st_mtime if resp_path.exists() else 0.0
    started = time.time()
    while True:
        try:
            time.sleep(_HC_POLL_INTERVAL)
        except KeyboardInterrupt:
            print("\n[CCD] Interrupted — pipeline state saved. Resume with --resume.", file=sys.stderr)
            return None
        if _HC_POLL_TIMEOUT > 0 and (time.time() - started) > _HC_POLL_TIMEOUT:
            print(f"[CCD] HC gate timed out after {_HC_POLL_TIMEOUT}s — exiting.", file=sys.stderr)
            return None
        try:
            current_mtime = resp_path.stat().st_mtime
        except FileNotFoundError:
            continue
        if abs(current_mtime - last_mtime) < 0.01:
            continue
        last_mtime = current_mtime
        try:
            data = json.loads(resp_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, ValueError):
            print(f"[CCD] Invalid JSON in response.json — waiting for valid input...", file=sys.stderr)
            continue
        # Bug 1 fix: Check that gate_node matches current node.
        # If a previous gate's response.json was not archived (e.g. due to
        # crash), its action might auto-confirm the WRONG gate.  Force
        # overwrite if the gate_node doesn't match.
        stored_node = str(data.get("gate_node", ""))
        if stored_node and stored_node != node:
            print(f"[CCD] ⚠️  response.json gate_node='{stored_node}' ≠ current='{node}' — overwriting stale file", file=sys.stderr)
            _write_response_template(artifact_root, node, data.get("rework_targets", []))
            last_mtime = resp_path.stat().st_mtime
            continue
        action = str(data.get("action", "")).strip().lower()
        if action in ("confirm", "rework", "correct"):
            # Archive the response so the next gate starts fresh
            _archive_response(artifact_root, node, data)
            return data
        if action:
            print(f"[CCD] Unknown action '{action}' — expected confirm, rework, or correct.", file=sys.stderr)


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
    device_profile = info.get("device_profile")
    if device_profile and isinstance(device_profile, dict):
        lines.append("## Device Profile")
        lines.append("| Field | Value |")
        lines.append("| --- | --- |")
        for k, v in device_profile.items():
            if k != "profile_source_ids":
                lines.append(f"| {k} | {str(v)[:200]} |")
        lines.append("")
    claim_ledger = info.get("claim_ledger")
    if claim_ledger and isinstance(claim_ledger, list):
        lines.append(f"## Claim Ledger ({len(claim_ledger)} claims)")
        lines.append("| ID | Type | Text |")
        lines.append("| --- | --- | --- |")
        for c in claim_ledger[:20]:
            lines.append(
                f"| {c.get('claim_id', '?')} | {c.get('claim_type', '?')} | {str(c.get('claim_text', ''))[:120]} |"
            )
        lines.append("")
    search_runs = info.get("search_runs")
    if search_runs and isinstance(search_runs, list):
        lines.append(f"## Search Strategy ({len(search_runs)} searches)")
        lines.append("| DB | Terms |")
        lines.append("| --- | --- |")
        for s in search_runs[:10]:
            lines.append(f"| {s.get('database', '?')} | {str(s.get('search_terms', ''))[:150]} |")
        lines.append("")
    evidence_count = info.get("evidence_count")
    appraisal_sample = info.get("appraisal_sample")
    if evidence_count:
        lines.append(f"## Evidence Appraisal ({evidence_count} records)")
        if appraisal_sample:
            lines.append("| Evidence ID | Score | Weight |")
            lines.append("| --- | --- | --- |")
            for a in appraisal_sample[:10]:
                lines.append(
                    f"| {a.get('evidence_id', '?')} | {a.get('score', '?')} | {a.get('weight', '?')} |"
                )
        lines.append("")
    p0_rows = info.get("p0_rows")
    p1_rows = info.get("p1_rows")
    critical_flags = info.get("critical_flags")
    if p0_rows or p1_rows or critical_flags:
        lines.append("## Manufacturer Intake Pack")
        if info.get("intake_pack_path"):
            lines.append(f"**Workbook**: `{info.get('intake_pack_path')}`")
            lines.append("")
        lines.append(f"- P0 draft/unconfirmed count: {info.get('p0_draft_count', 0)}")
        lines.append(f"- P1 draft/needs-review count: {info.get('p1_draft_count', 0)}")
        if critical_flags:
            lines.append("")
            lines.append("### Critical Flags")
            for flag in critical_flags[:20]:
                lines.append(f"- {flag}")
        if p0_rows:
            lines.append("")
            lines.append(f"### P0 Device Scope ({len(p0_rows)} rows)")
            lines.append("| Field ID | Status | Response |")
            lines.append("| --- | --- | --- |")
            for row in p0_rows[:30]:
                lines.append(
                    f"| {row.get('field_id', '?')} | {row.get('status', '?')} | {str(row.get('response', ''))[:180]} |"
                )
        if p1_rows:
            lines.append("")
            lines.append(f"### P1 Evidence Controls ({len(p1_rows)} rows)")
            lines.append("| Control ID | Status | Response |")
            lines.append("| --- | --- | --- |")
            for row in p1_rows[:30]:
                lines.append(
                    f"| {row.get('control_id', '?')} | {row.get('status', '?')} | {str(row.get('response', ''))[:180]} |"
                )
        lines.append("")
    endpoint_count = info.get("endpoint_count")
    sample_endpoints = info.get("sample_endpoints")
    if endpoint_count:
        lines.append(f"## Endpoints ({endpoint_count} extracted)")
        if sample_endpoints:
            lines.append("| ID | Endpoint | Source |")
            lines.append("| --- | --- | --- |")
            for ep in sample_endpoints[:10]:
                lines.append(
                    f"| {ep.get('endpoint_id', '?')} | {str(ep.get('endpoint', ''))[:100]} | {ep.get('source_article', '?')} |"
                )
        lines.append("")
    sections = info.get("sections_to_review")
    if sections:
        lines.append("## Sections to Review")
        for s in sections:
            lines.append(f"- {s}")
        lines.append("")
    rework_targets = info.get("rework_targets") or []
    lines.append("---")
    lines.append("")
    lines.append("## To Continue")
    lines.append("")
    lines.append("Edit `.human_gate/response.json` and save the file:")
    lines.append('- `{"action": "confirm"}` — approve and continue forward')
    if rework_targets:
        for rt in rework_targets:
            lines.append(f'- `{{"action": "rework", "target": "{rt}", "reason": "..."}}` — rewind to {rt}')
    lines.append("")
    lines.append(f"**File**: `{gate_file}`")
    content = "\n".join(lines)
    gate_file.write_text(content, encoding="utf-8")
    return str(gate_file)


def _archive_response(artifact_root: str, node: str, data: dict[str, Any]) -> None:
    """Move the consumed response.json to a timestamped archive."""
    resp_path = Path(artifact_root) / ".human_gate" / "response.json"
    archive_dir = Path(artifact_root) / ".human_gate" / ".responses"
    archive_dir.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%dT%H%M%S")
    archive_path = archive_dir / f"{node}_{ts}.json"
    try:
        resp_path.rename(archive_path)
    except OSError:
        pass


def _handle_hc_interrupt(graph, state, config, interrupt_info: dict, artifact_root: str) -> Command | None:
    """Write gate files, poll response.json, return a Command for resume/rework.

    Returns None if the process should exit (timeout / KeyboardInterrupt).
    """
    node = interrupt_info.get("node", "unknown")
    message = interrupt_info.get("message", "N/A")
    rework_targets = interrupt_info.get("rework_targets") or []

    # Write review files
    gate_file = _write_human_gate_file(artifact_root, node, interrupt_info)
    _write_response_template(artifact_root, node, rework_targets)

    # Print pause banner
    payload = {**interrupt_info, "auto_confirm": False, "human_gate_mode": "production_pause"}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    print(f"\n{'='*60}", file=sys.stderr)
    print(f"[CCD] ⏸️  PIPELINE PAUSED at '{node}'", file=sys.stderr)
    print(f"[CCD] Message: {message[:200]}", file=sys.stderr)
    print(f"[CCD] Review: {gate_file}", file=sys.stderr)
    if rework_targets:
        print(f"[CCD] Rework targets: {', '.join(rework_targets)}", file=sys.stderr)
    print(f"[CCD] Edit .human_gate/response.json and save to continue", file=sys.stderr)
    print(f"{'='*60}\n", file=sys.stderr)

    # Poll for human response
    response = _poll_response(artifact_root, node)
    if response is None:
        return None

    action = str(response.get("action", "")).strip().lower()
    if action == "rework":
        target = str(response.get("target", "")).strip()
        reason = str(response.get("reason", "")).strip()
        if target:
            print(f"[CCD] ↩️  Rework → {target} ({reason})", file=sys.stderr)
            return Command(resume={"action": "rework", "target": target, "reason": reason})
        print(f"[CCD] ⚠️  Rework requested but no target specified — confirming instead.", file=sys.stderr)
    if action == "correct":
        corrections = response.get("corrections") or {}
        return Command(resume={"confirmed": True, "corrections": corrections})
    # action == "confirm" (or empty fallthrough)
    print(f"[CCD] ✅ Confirmed — continuing.", file=sys.stderr)
    return Command(resume={"confirmed": True, "action": "confirm"})


def _single_invoke(graph, state, config, artifact_root: str = "") -> int:
    """Production HC-pause loop with response-file polling.

    The process stays alive across HC gates.  At each gate it writes review
    files and polls response.json.  The human edits the file in-place and
    saves; the process detects the change and resumes automatically.
    """
    default_artifact = str(Path(artifact_root) if artifact_root else Path.cwd() / "02_CER_OUTPUT")

    # ── Bug 1 fix: --resume preamble ──
    # When --resume is used (state = Command(resume={"_resume_poll": True})),
    # check for pending interrupts at the LAST checkpoint and enter the
    # polling loop for THAT gate.  This ensures the human sees the gate
    # data they missed when the process previously died.
    if isinstance(state, Command) and isinstance(state.resume, dict) and state.resume.get("_resume_poll"):
        gs = graph.get_state(config)
        pending = gs.interrupts if gs else []
        if pending:
            entry = pending[0]
            interrupt_value = entry.value if hasattr(entry, "value") else entry
            if isinstance(interrupt_value, dict):
                node = str(interrupt_value.get("confirmation_point", "unknown"))
                message = str(interrupt_value.get("message", "N/A"))
                interrupt_info = dict(interrupt_value)
                interrupt_info.setdefault("node", node)
            else:
                node = "unknown"
                message = str(interrupt_value)[:200]
                interrupt_info = {"node": node, "message": message, "step": "?"}
            interrupt_info["artifact_root"] = str(
                interrupt_info.get("artifact_root") or default_artifact
            )
            print(f"[CCD] 🔄 Resume polling at gate: {node}", file=sys.stderr)
            cmd = _handle_hc_interrupt(graph, state, config, interrupt_info, interrupt_info["artifact_root"])
            if cmd is None:
                return 0
            state = cmd
        else:
            print("[CCD] No pending interrupt — pipeline may already be complete.", file=sys.stderr)
            return 0

    while True:
        try:
            result = graph.invoke(state, config)
        except Exception as e:
            err_msg = str(e)
            if "GraphInterrupt" in type(e).__name__:
                interrupt_info = _extract_interrupt_info(err_msg, e)
                artifact_root = interrupt_info.get(
                    "artifact_root", str(Path.cwd() / "02_CER_OUTPUT")
                )
                cmd = _handle_hc_interrupt(graph, state, config, interrupt_info, artifact_root)
                if cmd is None:
                    return 0
                state = cmd
                continue
            summary = {"error": err_msg[:300], "status": "fatal_error"}
            print(json.dumps(summary, ensure_ascii=False, indent=2))
            return 3

        # Check for pending interrupts (SqliteSaver path)
        gs = graph.get_state(config)
        pending = gs.interrupts if gs else []
        if pending:
            artifact_root = str(
                result.get("artifact_root")
                or (state.get("artifact_root") if isinstance(state, dict) else "")
                or Path.cwd() / "02_CER_OUTPUT"
            )
            for entry in pending:
                interrupt_value = entry.value if hasattr(entry, "value") else entry
                if isinstance(interrupt_value, dict):
                    node = str(interrupt_value.get("confirmation_point", "unknown"))
                    message = str(interrupt_value.get("message", "N/A"))
                    interrupt_info = dict(interrupt_value)
                    interrupt_info.setdefault("node", node)
                else:
                    node = "unknown"
                    message = str(interrupt_value)[:200]
                    interrupt_info = {"node": node, "message": message, "step": "?"}
                interrupt_info["artifact_root"] = artifact_root
                if not interrupt_info.get("device_profile"):
                    interrupt_info["device_profile"] = result.get("device_profile")
                if not interrupt_info.get("claim_ledger"):
                    interrupt_info["claim_ledger"] = result.get("claim_ledger")
                if not interrupt_info.get("sota_benchmark_matrix"):
                    interrupt_info["sota_benchmark_matrix"] = result.get("sota_benchmark_matrix")
                cmd = _handle_hc_interrupt(graph, state, config, interrupt_info, artifact_root)
                if cmd is None:
                    return 0
                state = cmd
                break  # One interrupt per loop iteration
            continue

        # Pipeline complete
        summary = _build_summary(result, None)
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0 if result.get("final_gate_decision") == "PASS_TO_DRAFT_DOCX" else 2


# ── Helpers ───────────────────────────────────────────────────────────────


def _build_summary(result: dict, args) -> dict:
    auto_confirm = getattr(args, "auto_confirm", False) if args else False
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
        "auto_confirm": auto_confirm,
        "human_gate_mode": "validation_auto_confirm" if auto_confirm else "production_pause",
    }


def _extract_interrupt_info(err_msg: str, exc: Exception) -> dict:
    info = {"node": "unknown", "message": err_msg[:500], "step": "?"}
    if hasattr(exc, "args") and exc.args:
        for arg in exc.args:
            if isinstance(arg, dict):
                info.update({k: v for k, v in arg.items() if k not in ("message",)})
                info["message"] = str(arg.get("message", arg))[:500]
                info["node"] = str(
                    arg.get("confirmation_point", arg.get("node", "unknown"))
                )
                info["step"] = str(arg.get("step", "?"))
                info["priority"] = str(arg.get("priority", "?"))
                info["sections"] = arg.get("sections_to_review", [])
    return info


def _extract_node_from_error(err_msg: str, exc: Exception | None = None) -> str:
    if exc and hasattr(exc, "args") and exc.args:
        for arg in exc.args:
            if isinstance(arg, dict):
                node = arg.get("confirmation_point", arg.get("node", ""))
                if node:
                    return str(node)
    for keyword in [
        "device_profile",
        "claim_decomposition",
        "sota_search",
        "evidence_appraisal",
        "endpoint_extraction",
        "cer_writing",
        "gates",
        "export",
        "pre_writer",
        "human_style",
    ]:
        if keyword in err_msg.lower():
            return keyword
    return "unknown"


# ── Productivity helpers ──────────────────────────────────────────────────


def _cleanup_old_logs(artifact_root: Path) -> None:
    """Archive logs older than 24h to .archive/. Keeps last 5 logs."""
    log_files = sorted(artifact_root.glob("*.log"), key=lambda p: p.stat().st_mtime)
    if len(log_files) <= 5:
        return
    archive_dir = artifact_root / ".archive"
    archive_dir.mkdir(exist_ok=True)
    cutoff = time.time() - 86400
    for lf in log_files[:-5]:
        if lf.stat().st_mtime < cutoff:
            lf.rename(archive_dir / lf.name)


def _preflight_checks(input_root: Path, artifact_root: Path) -> None:
    """Check project readiness before pipeline start."""
    ok = True
    ifu_files = _discover_preflight_ifu_files(input_root)
    if not ifu_files:
        print("[PREFLIGHT] ⚠️  No IFU files found", file=sys.stderr)
        ok = False
    try:
        import shutil

        free = shutil.disk_usage(artifact_root).free / (1024**3)
        if free < 1:
            print(f"[PREFLIGHT] ⚠️  Low disk space: {free:.1f}GB free", file=sys.stderr)
            ok = False
    except Exception:
        pass
    if ok:
        print(f"[PREFLIGHT] ✅ Ready — IFU found ({len(ifu_files)}), disk OK", file=sys.stderr)


def _discover_preflight_ifu_files(input_root: Path) -> list[Path]:
    """Find IFU files across legacy and intake-pack source layouts."""
    if not input_root.exists():
        return []
    extensions = {".doc", ".docx", ".pdf", ".txt", ".md", ".rtf"}
    preferred_dirs = ("01_IFU_REQUIRED", "IFU", "LABELING_UDI_PACKAGING")
    candidates: list[Path] = []
    for dirname in preferred_dirs:
        base = input_root / dirname
        if base.exists():
            candidates.extend(
                path
                for path in base.rglob("*")
                if path.is_file() and path.suffix.lower() in extensions and _path_has_ifu_signal(path)
            )
    candidates.extend(
        path
        for path in input_root.rglob("*")
        if path.is_file()
        and path.suffix.lower() in extensions
        and _path_has_ifu_signal(path)
    )
    return sorted(set(candidates))


def _path_has_ifu_signal(path: Path) -> bool:
    text = " ".join(str(part) for part in path.parts[-4:]).lower()
    original = str(path)
    return any(
        token in text
        for token in (
            "ifu",
            "instructions for use",
            "user manual",
            "product information",
            "labeling",
        )
    ) or any(token in original for token in ("说明书", "使用信息", "产品使用信息"))


def _notify(title: str, message: str) -> None:
    """macOS notification when pipeline completes."""
    try:
        subprocess.run(
            ["osascript", "-e", f'display notification "{message}" with title "{title}"'],
            timeout=5,
        )
    except Exception:
        pass


def _vacuum_checkpoint(project_id: str) -> None:
    """VACUUM SQLite checkpoint after successful run."""
    db_path = Path("checkpoints.db")
    if not db_path.exists():
        return
    try:
        import sqlite3

        conn = sqlite3.connect(str(db_path))
        conn.execute("VACUUM")
        conn.close()
    except Exception:
        pass


def _node_timing_report(interrupted_nodes: list[str]) -> str:
    """Build per-node timing summary."""
    from collections import Counter

    counts = Counter(interrupted_nodes)
    lines = ["## Node Timing"]
    lines.append("| Node | Count |")
    lines.append("| --- | --- |")
    for node, count in counts.most_common():
        lines.append(f"| {node} | {count} |")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
