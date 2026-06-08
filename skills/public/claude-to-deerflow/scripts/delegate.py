#!/usr/bin/env python3
"""Claude Code -> DeerFlow delegation bridge.

This script lets Claude Code hand a bounded task to DeerFlow, collect the
complete run trace, and leave reviewable artifacts for the supervising Claude
session. It uses DeerFlow's embedded client, so it does not require the web UI,
Nginx, Gateway, or LangGraph server to be running.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEERFLOW_ROOT = Path(os.environ.get("DEERFLOW_ROOT", "/Users/winstonwei/Documents/Playground/deer-flow"))
DEERFLOW_BACKEND = DEERFLOW_ROOT / "backend"
HARNESS_PATH = DEERFLOW_BACKEND / "packages" / "harness"
ROUND2_ROOT = Path(os.environ.get("ROUND2_ROOT", "/Users/winstonwei/CER-RAG/00_knowledge_extraction_build/round2_autonomous_loop"))
DEFAULT_OUTPUT_ROOT = DEERFLOW_ROOT / "artifacts" / "claude_deerflow_delegations"
DEFAULT_MODEL = "minimax-m2.7-highspeed"

if str(HARNESS_PATH) not in sys.path:
    sys.path.insert(0, str(HARNESS_PATH))


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def slugify(text: str, fallback: str = "task") -> str:
    text = re.sub(r"[^A-Za-z0-9._-]+", "-", text.strip())[:80].strip("-._")
    return text or fallback


def infer_project_id(*values: str | None) -> str | None:
    for value in values:
        if not value:
            continue
        match = re.search(r"\bPROJECT_\d+\b", value)
        if match:
            return match.group(0)
    return None


def default_output_root(args: argparse.Namespace, task: str, supervisor_notes: str) -> Path:
    if args.out_dir:
        return Path(args.out_dir).expanduser()
    project_id = args.project_id or infer_project_id(args.run_id, task, supervisor_notes)
    if project_id and args.level:
        return ROUND2_ROOT / "10_reports" / "project_learning_capsules" / project_id / args.level / "deerflow_delegations"
    return DEFAULT_OUTPUT_ROOT


def read_text_arg(value: str | None, path: str | None, *, label: str, required: bool = False) -> str:
    if path:
        return Path(path).read_text(encoding="utf-8")
    if value:
        return value
    if required:
        raise SystemExit(f"Missing required {label}: pass --{label} or --{label}-file")
    return ""


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def sanitize_event(event: Any) -> dict[str, Any]:
    data = dict(getattr(event, "data", {}) or {})
    return {"type": getattr(event, "type", "unknown"), "data": data, "timestamp": now_iso()}


def configure_extensions(run_dir: Path, allow_mcp: bool) -> dict[str, Any]:
    if allow_mcp:
        return {
            "mode": "global_extensions_enabled",
            "config_path": os.environ.get("DEER_FLOW_EXTENSIONS_CONFIG_PATH"),
        }

    config_path = run_dir / "extensions_config.disabled.json"
    write_json(
        config_path,
        {
            "mcpServers": {},
            "skills": {},
            "note": "External MCP disabled for Claude-supervised DeerFlow delegation.",
            "generated_at": now_iso(),
        },
    )
    os.environ["DEER_FLOW_EXTENSIONS_CONFIG_PATH"] = str(config_path)
    return {
        "mode": "external_mcp_disabled",
        "config_path": str(config_path),
        "enabled_mcp_servers": [],
    }


def build_prompt(task: str, acceptance: str, files_info: list[dict[str, Any]], supervisor_notes: str) -> str:
    parts = [
        "# Claude-Supervised DeerFlow Delegation Task",
        "",
        "You are DeerFlow executing a bounded subtask for a supervising Claude Code session.",
        "Do the delegated work directly, keep the result inspectable, and do not claim final acceptance.",
        "The supervising Claude Code session will review your output against the acceptance criteria.",
        "",
        "## Task",
        "",
        task.strip(),
    ]
    if acceptance.strip():
        parts += [
            "",
            "## Acceptance Criteria",
            "",
            acceptance.strip(),
        ]
    if files_info:
        parts += [
            "",
            "## Uploaded Files",
            "",
        ]
        for item in files_info:
            line = f"- `{item.get('filename')}` at `{item.get('virtual_path')}`"
            if item.get("markdown_virtual_path"):
                line += f"; markdown: `{item.get('markdown_virtual_path')}`"
            parts.append(line)
    if supervisor_notes.strip():
        parts += [
            "",
            "## Supervisor Notes",
            "",
            supervisor_notes.strip(),
        ]
    parts += [
        "",
        "## Required Response Format",
        "",
        "Return a concise Markdown result with these sections:",
        "- Work Performed",
        "- Key Findings Or Changes",
        "- Output Artifacts",
        "- Risks Or Blockers",
        "- Self-Check Against Acceptance Criteria",
    ]
    return "\n".join(parts)


def classify_friendly_failure(text: str) -> dict[str, str] | None:
    lowered = (text or "").lower()
    patterns = [
        (
            "llm_provider_unavailable",
            "configured llm provider is temporarily unavailable",
        ),
        (
            "llm_connection_error",
            "connection error",
        ),
        (
            "empty_deerflow_response",
            "(no response from agent)",
        ),
    ]
    for error_type, needle in patterns:
        if needle in lowered:
            return {
                "class": error_type,
                "message": text[:1000],
            }
    if not text.strip():
        return {
            "class": "empty_deerflow_response",
            "message": "DeerFlow returned no visible result text.",
        }
    return None


def run_delegate(args: argparse.Namespace) -> int:
    from deerflow.client import DeerFlowClient

    task = read_text_arg(args.task, args.task_file, label="task", required=True)
    acceptance = read_text_arg(args.acceptance, args.acceptance_file, label="acceptance")
    supervisor_notes = read_text_arg(args.supervisor_notes, args.supervisor_notes_file, label="supervisor-notes")

    run_id = args.run_id or f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{slugify(task[:60])}"
    out_root = default_output_root(args, task, supervisor_notes)
    run_dir = out_root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    extensions_status = configure_extensions(run_dir, args.allow_mcp)
    thread_id = args.thread_id or f"claude-deerflow-{uuid.uuid4().hex[:12]}"

    task_packet = {
        "schema_name": "claude_deerflow_delegate_task",
        "schema_version": "v1",
        "run_id": run_id,
        "thread_id": thread_id,
        "created_at": now_iso(),
        "model": args.model,
        "model_policy": "Use DeerFlow current primary router; fallback is governed by DeerFlow config.",
        "mode": args.mode,
        "thinking_enabled": args.thinking,
        "subagent_enabled": args.mode == "ultra",
        "plan_mode": args.mode in {"pro", "ultra"},
        "allow_mcp": args.allow_mcp,
        "task": task,
        "acceptance_criteria": acceptance,
        "supervisor_notes": supervisor_notes,
        "files": [str(Path(f).expanduser()) for f in args.file],
    }
    write_json(run_dir / "task_packet.json", task_packet)
    write_text(run_dir / "task.md", task)
    if acceptance:
        write_text(run_dir / "acceptance.md", acceptance)

    status: dict[str, Any] = {
        "schema_name": "claude_deerflow_delegate_status",
        "schema_version": "v1",
        "run_id": run_id,
        "thread_id": thread_id,
        "started_at": now_iso(),
        "finished_at": None,
        "status": "running",
        "model": args.model,
        "mode": args.mode,
        "extensions": extensions_status,
        "usage": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
        "error": None,
        "outputs": {},
    }
    write_json(run_dir / "status.json", status)

    try:
        client = DeerFlowClient(
            model_name=args.model,
            thinking_enabled=args.thinking,
            plan_mode=args.mode in {"pro", "ultra"},
            subagent_enabled=args.mode == "ultra",
        )

        upload_result: dict[str, Any] = {"success": True, "files": []}
        if args.file:
            upload_result = client.upload_files(thread_id, [Path(f).expanduser() for f in args.file])
        write_json(run_dir / "uploads.json", upload_result)

        prompt = build_prompt(task, acceptance, upload_result.get("files", []), supervisor_notes)
        write_text(run_dir / "deerflow_prompt.md", prompt)

        raw_parts: list[str] = []
        last_ai_text = ""
        events_path = run_dir / "events.jsonl"
        with events_path.open("w", encoding="utf-8") as events_file:
            for event in client.stream(
                prompt,
                thread_id=thread_id,
                model_name=args.model,
                thinking_enabled=args.thinking,
                plan_mode=args.mode in {"pro", "ultra"},
                subagent_enabled=args.mode == "ultra",
                recursion_limit=args.recursion_limit,
            ):
                events_file.write(json.dumps(sanitize_event(event), ensure_ascii=False) + "\n")
                events_file.flush()

                if event.type == "messages-tuple" and event.data.get("type") == "ai":
                    content = event.data.get("content") or ""
                    if content:
                        raw_parts.append(content)
                        last_ai_text = content
                elif event.type == "end":
                    usage = event.data.get("usage") or {}
                    status["usage"] = {
                        "input_tokens": usage.get("input_tokens", 0) or 0,
                        "output_tokens": usage.get("output_tokens", 0) or 0,
                        "total_tokens": usage.get("total_tokens", 0) or 0,
                    }

        raw_response = "\n\n".join(raw_parts)
        final_response = last_ai_text or raw_response
        write_text(run_dir / "raw_response.md", raw_response)
        write_text(run_dir / "result.md", final_response)
        write_text(
            run_dir / "supervisor_acceptance_checklist.md",
            "\n".join(
                [
                    "# Supervisor Acceptance Checklist",
                    "",
                    "- [ ] DeerFlow addressed the delegated task, not unrelated work.",
                    "- [ ] Output artifacts referenced by DeerFlow exist and are readable.",
                    "- [ ] Acceptance criteria are explicitly satisfied or blockers are stated.",
                    "- [ ] Claude Code independently reviewed the result before using it.",
                    "",
                    "## Acceptance Criteria",
                    "",
                    acceptance or "(none supplied)",
                ]
            ),
        )

        friendly_failure = classify_friendly_failure(final_response)
        if friendly_failure:
            status["status"] = "failed"
            status["error"] = friendly_failure
        else:
            status["status"] = "completed"
        status["finished_at"] = now_iso()
        status["outputs"] = {
            "run_dir": str(run_dir),
            "task_packet": str(run_dir / "task_packet.json"),
            "events": str(events_path),
            "raw_response": str(run_dir / "raw_response.md"),
            "result": str(run_dir / "result.md"),
            "acceptance_checklist": str(run_dir / "supervisor_acceptance_checklist.md"),
        }
        write_json(run_dir / "status.json", status)

        print(json.dumps({
            "status": status["status"],
            "run_id": run_id,
            "thread_id": thread_id,
            "run_dir": str(run_dir),
            "result_path": str(run_dir / "result.md"),
            "status_path": str(run_dir / "status.json"),
            "usage": status["usage"],
            "error": status["error"],
        }, indent=2, ensure_ascii=False))
        return 1 if friendly_failure else 0

    except Exception as exc:
        status["status"] = "failed"
        status["finished_at"] = now_iso()
        status["error"] = {
            "class": type(exc).__name__,
            "message": str(exc),
            "traceback": traceback.format_exc(),
        }
        write_json(run_dir / "status.json", status)
        write_text(run_dir / "exception_trace.txt", traceback.format_exc())
        print(json.dumps({
            "status": "failed",
            "run_id": run_id,
            "run_dir": str(run_dir),
            "status_path": str(run_dir / "status.json"),
            "error_class": type(exc).__name__,
            "error": str(exc),
        }, indent=2, ensure_ascii=False), file=sys.stderr)
        return 1


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Delegate a bounded Claude Code subtask to DeerFlow.")
    parser.add_argument("--task", help="Task text to send to DeerFlow.")
    parser.add_argument("--task-file", help="Path to a Markdown/text task packet.")
    parser.add_argument("--acceptance", help="Acceptance criteria text.")
    parser.add_argument("--acceptance-file", help="Path to acceptance criteria text.")
    parser.add_argument("--supervisor-notes", help="Additional notes from Claude Code supervisor.")
    parser.add_argument("--supervisor-notes-file", help="Path to supervisor notes.")
    parser.add_argument("--file", action="append", default=[], help="File to upload into the DeerFlow thread. Repeatable.")
    parser.add_argument("--out-dir", help=f"Output root. Default: project L1 folder when --project-id/--level are supplied, else {DEFAULT_OUTPUT_ROOT}")
    parser.add_argument("--project-id", help="Project id such as PROJECT_021. With --level, outputs go under that project learning capsule folder.")
    parser.add_argument("--level", default=os.environ.get("DEERFLOW_DELEGATE_LEVEL"), help="Level folder such as L1_AUTHORITATIVE_RERUN.")
    parser.add_argument("--run-id", help="Stable run id. Default is timestamp + task slug.")
    parser.add_argument("--thread-id", help="Existing DeerFlow thread id to reuse.")
    parser.add_argument("--model", default=os.environ.get("DEERFLOW_DELEGATE_MODEL", DEFAULT_MODEL), help=argparse.SUPPRESS)
    parser.add_argument("--mode", choices=["flash", "standard", "pro", "ultra"], default=os.environ.get("DEERFLOW_DELEGATE_MODE", "pro"))
    parser.add_argument("--thinking", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--allow-mcp", action="store_true", help="Use global DeerFlow MCP config. Default disables external MCP for reproducible delegation.")
    parser.add_argument("--recursion-limit", type=int, default=1000)
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(run_delegate(parse_args()))
