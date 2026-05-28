#!/usr/bin/env python3
"""Claude Cowork supervisor for DeerFlow CER authoring and review.

This wrapper is intentionally thin: it prepares run folders, builds the exact
DeerFlow command, captures logs, and performs Claude-side postflight checks. It
does not merge authoring and review workflows.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import shlex
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
PYTHON = REPO_ROOT / "backend" / ".venv" / "bin" / "python"
AUTHORING_SCRIPT = REPO_ROOT / "backend" / "scripts" / "run_cer_authoring.py"
REVIEW_SCRIPT = REPO_ROOT / "scripts" / "cer_review_runner.py"
REVIEW_ASSIST_SCRIPT = REPO_ROOT / "scripts" / "cer_review_assist.py"
REVIEW_WORKFLOW = REPO_ROOT / "backend" / "workflows" / "cer_review_workflow_v1.yaml"
COWORK_ROOT = REPO_ROOT / "artifacts" / "cer_cowork"

FINAL_STATUSES = {
    "AUTHORING_NB_READY_DRAFT",
    "AUTHORING_CONTROLLED_DRAFT_WITH_GAPS",
    "REVIEW_PACKAGE_READY",
    "REWORK_REQUIRED",
    "HUMAN_HOLD",
    "EXECUTION_FAILED",
}

DOC_EXTENSIONS = {".doc", ".docx", ".pdf", ".txt", ".md", ".rtf", ".xlsx", ".xls", ".json"}
CORE_AUTHORING_ARTIFACTS = [
    "authoring_workbook.json",
    "source_inventory.xlsx",
    "device_profile.json",
    "claim_ledger.xlsx",
    "claim_pico_derivation.xlsx",
    "literature_search_protocol_profile.json",
    "sota_pico_strategy.xlsx",
    "due_pico_strategy.xlsx",
    "database_search_source_table.xlsx",
    "literature_defined_limits.xlsx",
    "search_protocol_and_results.docx",
    "search_run_registry.json",
    "literature_flow_registry.xlsx",
    "protocol_deviation_log.xlsx",
    "prisma_flow_data.json",
    "prisma_flow_diagram.md",
    "sota_search_strategy_table.xlsx",
    "sota_screening_disposition_table.xlsx",
    "sota_ck_appraisal_table.xlsx",
    "due_suitability_contribution_table.xlsx",
    "screening_disposition_table.xlsx",
    "evidence_appraisal_table.xlsx",
    "endpoint_extraction_table.xlsx",
    "sota_benchmark_matrix.xlsx",
    "alternative_treatment_benchmark_table.xlsx",
    "guideline_pathway_table.xlsx",
    "similar_benchmark_device_table.xlsx",
    "hazard_source_table.xlsx",
    "sota_to_47_usage_matrix.xlsx",
    "full_text_request_list.xlsx",
    "sota_literature_quantity_justification.md",
    "sota_endpoint_derivation_table.xlsx",
    "sota_quantitative_benchmark_table.xlsx",
    "sota_evidence_synthesis_matrix.xlsx",
    "equivalence_comparison_matrix.xlsx",
    "similar_device_four_step_confirmation.xlsx",
    "similar_device_attachment_index.xlsx",
    "vigilance_recall_registry.xlsx",
    "vigilance_event_statistics.xlsx",
    "risk_gspr_trace_matrix.xlsx",
    "marketing_pms_customer_questionnaire.xlsx",
    "CER_draft.md",
    "CER_draft.docx",
    "gap_pmcf_recommendations.docx",
    "qa_gate_report.json",
    "nb_precheck_report.docx",
    "final_gate_closure_report.json",
]
AUTHORING_PLACEHOLDERS = ["HUMAN_REVIEW", "DATA GAP", "pending execution", "TODO", "TBD"]
PROHIBITED_REVIEW_VERDICTS = ["PASS", "FAIL", "APPROVED", "REJECTED", "CEAR"]
MODEL_PROTOCOL_MARKERS = [
    "MODEL_TOOL_PROTOCOL_UNSUPPORTED",
    "<function_calls>",
    "</function_calls>",
    "<invoke name=",
    "XML/textual function_calls",
]


def load_repair_module() -> Any:
    """Load the sibling Claude-side repair module without requiring packaging."""
    path = REPO_ROOT / "scripts" / "cer_cowork_repair.py"
    spec = importlib.util.spec_from_file_location("cer_cowork_repair", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load repair module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def slugify(value: str, fallback: str = "cer-project") -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip()).strip("-._")
    return cleaned[:80] or fallback


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def read_mapping(path: Path) -> dict[str, Any]:
    """Read JSON or YAML mapping files used for project profiles."""
    data = read_json(path)
    if data:
        return data
    try:
        import yaml  # type: ignore

        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def run_id(prefix: str) -> str:
    return f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{slugify(prefix)}"


def is_process_alive(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def scan_documents(root: Path, *, limit: int = 1500) -> list[Path]:
    if root.is_file():
        return [root] if root.suffix.lower() in DOC_EXTENSIONS else []
    docs: list[Path] = []
    for path in sorted(root.rglob("*")):
        if len(docs) >= limit:
            break
        if path.is_file() and path.suffix.lower() in DOC_EXTENSIONS:
            docs.append(path)
    return docs


def _normalized_doc_path(value: str) -> str:
    return re.sub(r"[^a-z0-9\u3400-\u9fff]+", "_", str(value or "").lower()).strip("_")


def _compact_doc_path(value: str) -> str:
    return re.sub(r"[^a-z0-9\u3400-\u9fff]+", "", str(value or "").lower())


def _is_locked_delta_document_path(path: Path) -> bool:
    normalized = _normalized_doc_path(str(path))
    return any(
        token in normalized
        for token in (
            "02_nb_rounds_and_responses_locked",
            "02_nb_rounds",
            "03_final_certified_package_locked",
            "03_final_certified_package",
        )
    )


def _is_ifu_document_path(path: Path) -> bool:
    if _is_locked_delta_document_path(path):
        return False
    text = f"{path.name} {path}"
    normalized = _normalized_doc_path(text)
    compact = _compact_doc_path(text)
    if any(
        token in compact or token in normalized
        for token in (
            "ifu",
            "instructionsforuse",
            "instructionforuse",
            "instructions_for_use",
            "instruction_for_use",
            "使用说明书",
            "使用说明",
            "说明书",
        )
    ):
        return True
    parts = {_normalized_doc_path(part) for part in path.parts}
    if {"01_ifu", "ifu", "instructions_for_use", "instruction_for_use", "使用说明书", "说明书"} & parts:
        return True
    if any(token in compact or token in normalized for token in ("intendeduse", "intendedpurpose", "intended_use", "intended_purpose")) and (
        {"01_ifu", "ifu"} & parts
    ):
        return True
    return False


def infer_doc_type(path: Path) -> str:
    name = path.name.lower()
    compact = re.sub(r"[\s_-]+", "", name)
    if _is_locked_delta_document_path(path):
        return "Locked_Delta_Only"
    if "cer" in compact or "clinicalevaluationreport" in compact or "临床评价" in name or "临床评估" in name:
        return "CER"
    if _is_ifu_document_path(path):
        return "IFU"
    if "cep" in compact or "clinicalevaluationplan" in compact:
        return "CEP"
    if "rmf" in compact or "riskmanagement" in compact or "fmea" in compact or "风险" in name:
        return "RMF"
    if "gspr" in compact or "gpr" in compact:
        return "GSPR"
    if "pmcf" in compact:
        return "PMCF_Plan"
    if "pms" in compact or "postmarket" in compact:
        return "PMS_Plan"
    if "sscp" in compact:
        return "SSCP"
    if "equivalence" in compact or "等同" in name:
        return "Equivalence"
    if "literature" in compact or "文献" in name:
        return "SOTA_Literature"
    return "Supporting"


def has_doc_type(root: Path, doc_type: str) -> bool:
    return any(infer_doc_type(path) == doc_type for path in scan_documents(root))


def make_run_dir(project_id: str, mode: str, explicit_run_id: str | None) -> Path:
    rid = explicit_run_id or run_id(mode)
    return COWORK_ROOT / slugify(project_id) / mode / rid


def proxy_env(args: argparse.Namespace | None = None) -> dict[str, str]:
    env = os.environ.copy()
    explicit_proxy_requested = bool(getattr(args, "proxy_url", None) or getattr(args, "all_proxy_url", None))
    use_proxy = (
        not bool(getattr(args, "no_proxy", False))
        and (explicit_proxy_requested or env.get("CER_COWORK_USE_PROXY", "0") == "1")
    )
    proxy_url = getattr(args, "proxy_url", None) or env.get("CER_COWORK_PROXY_URL") or "http://127.0.0.1:7890"
    all_proxy_url = getattr(args, "all_proxy_url", None) or env.get("CER_COWORK_ALL_PROXY_URL") or "socks5://127.0.0.1:7890"
    if use_proxy:
        env.setdefault("HTTPS_PROXY", proxy_url)
        env.setdefault("HTTP_PROXY", proxy_url)
        env.setdefault("ALL_PROXY", all_proxy_url)
    else:
        for key in ("HTTPS_PROXY", "HTTP_PROXY", "ALL_PROXY", "https_proxy", "http_proxy", "all_proxy"):
            env.pop(key, None)
        env["NO_PROXY"] = "*"
        env["no_proxy"] = "*"
    env.setdefault("CER_AUTHORING_STRICT_AGENT_TIMEOUT_SECONDS", "300")
    env.setdefault("CER_AUTHORING_STRICT_AGENT_MAX_TURNS", "10")
    return env


def shell_command(command: list[str]) -> str:
    return " ".join(shlex.quote(item) for item in command)


def write_initial_status(run_dir: Path, payload: dict[str, Any]) -> None:
    status = {
        "schema_name": "cer_cowork_supervisor_status",
        "schema_version": "v1",
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "status": "configured",
        "pid": None,
        "returncode": None,
        "final_status": None,
        "issues": [],
        **payload,
    }
    write_json(run_dir / "status.json", status)


def update_status(run_dir: Path, **updates: Any) -> dict[str, Any]:
    status = read_json(run_dir / "status.json")
    status.update(updates)
    status["updated_at"] = now_iso()
    write_json(run_dir / "status.json", status)
    return status


def write_questions(run_dir: Path, mode: str) -> None:
    if mode == "authoring":
        text = "\n".join(
            [
                "# Claude Supervisor Questions",
                "",
                "Ask the user before authoring starts:",
                "- Project source folder containing IFU and available source documents.",
                "- Project ID.",
                "- Target device keywords, including English and Chinese names/models.",
                "- Supplement folders for GSPR/RMF/PMS/PMCF/equivalence data, if any.",
                "- Whether this is a new run or continuation of existing artifacts.",
            ]
        )
    else:
        text = "\n".join(
            [
                "# Claude Supervisor Questions",
                "",
                "Ask the user before review starts:",
                "- Whether the input is a CER file, a full project folder, or extracted texts.",
                "- Project ID.",
                "- Whether IFU/GSPR/RMF/CEP/PMS/PMCF are available.",
                "- Review goal and expected output depth.",
                "- Whether to use canonical review or Review Assist extracted-text mode.",
            ]
        )
    write_text(run_dir / "supervisor_questions.md", text + "\n")


def execute_command(run_dir: Path, command: list[str], *, background: bool, dry_run: bool, env: dict[str, str]) -> int:
    stdout_path = run_dir / "stdout.log"
    stderr_path = run_dir / "stderr.log"
    write_text(run_dir / "command.sh", f"#!/usr/bin/env bash\nset -euo pipefail\ncd {shlex.quote(str(REPO_ROOT))}\n{shell_command(command)}\n")
    if dry_run:
        update_status(run_dir, status="dry_run", final_status=None)
        return 0

    update_status(run_dir, status="running", pid=None, started_at=now_iso(), proxy_enabled=env.get("HTTPS_PROXY") is not None)

    if background:
        stdout_file = stdout_path.open("w", encoding="utf-8")
        stderr_file = stderr_path.open("w", encoding="utf-8")
        proc = subprocess.Popen(command, cwd=REPO_ROOT, stdout=stdout_file, stderr=stderr_file, env=env)
        update_status(run_dir, status="running", pid=proc.pid, started_at=now_iso())
        return 0

    with stdout_path.open("w", encoding="utf-8") as stdout_file, stderr_path.open("w", encoding="utf-8") as stderr_file:
        proc = subprocess.run(command, cwd=REPO_ROOT, stdout=stdout_file, stderr=stderr_file, env=env, check=False)
    update_status(run_dir, status="completed" if proc.returncode == 0 else "completed_with_nonzero_exit", returncode=proc.returncode, finished_at=now_iso())
    return proc.returncode


def parse_last_json(text: str) -> dict[str, Any]:
    starts = [match.start() for match in re.finditer(r"\{", text)]
    for start in reversed(starts):
        try:
            value = json.loads(text[start:])
        except Exception:
            continue
        if isinstance(value, dict):
            return value
    return {}


def authoring_start(args: argparse.Namespace) -> int:
    input_root = Path(args.input_root).expanduser().resolve()
    run_dir = make_run_dir(args.project_id, "authoring", args.run_id)
    authoring_root = run_dir / "deerflow_authoring"
    run_dir.mkdir(parents=True, exist_ok=True)
    write_questions(run_dir, "authoring")

    if not input_root.exists():
        write_initial_status(run_dir, {"mode": "authoring", "project_id": args.project_id, "run_dir": str(run_dir)})
        update_status(run_dir, status="blocked", final_status="HUMAN_HOLD", issues=[f"Input root does not exist: {input_root}"])
        print(json.dumps(read_json(run_dir / "status.json"), ensure_ascii=False, indent=2))
        return 3
    if not has_doc_type(input_root, "IFU"):
        write_initial_status(run_dir, {"mode": "authoring", "project_id": args.project_id, "run_dir": str(run_dir), "input_root": str(input_root)})
        update_status(run_dir, status="blocked", final_status="HUMAN_HOLD", issues=["No IFU candidate found. Authoring must stop until IFU is provided."])
        print(json.dumps(read_json(run_dir / "status.json"), ensure_ascii=False, indent=2))
        return 3

    command = [
        str(PYTHON),
        str(AUTHORING_SCRIPT),
        "--strict-v7",
        "--agent-team-mode",
        "stable-1plus6",
        "--project-id",
        args.project_id,
        "--input-root",
        str(input_root),
        "--artifact-root",
        str(authoring_root),
        "--json",
    ]
    for supplement in args.supplement_root or []:
        command += ["--supplement-root", str(Path(supplement).expanduser().resolve())]
    if args.target_keywords:
        command += ["--target-keywords", args.target_keywords]

    write_initial_status(
        run_dir,
        {
            "mode": "authoring",
            "project_id": args.project_id,
            "run_dir": str(run_dir),
            "input_root": str(input_root),
            "artifact_root": str(authoring_root),
            "command": command,
        },
    )
    write_json(
        run_dir / "run_config.json",
        {
            "mode": "authoring",
            "project_id": args.project_id,
            "input_root": str(input_root),
            "supplement_roots": [str(Path(item).expanduser().resolve()) for item in args.supplement_root or []],
            "artifact_root": str(authoring_root),
            "target_keywords": args.target_keywords,
            "agent_team_mode": "stable-1plus6",
            "strict_v7": True,
        },
    )
    rc = execute_command(run_dir, command, background=args.background, dry_run=args.dry_run, env=proxy_env(args))
    if not args.background and not args.dry_run:
        postflight(argparse.Namespace(run_dir=str(run_dir), json=True))
    print(json.dumps(status_summary(run_dir), ensure_ascii=False, indent=2))
    return rc


def build_review_profile(project_id: str, input_root: Path, run_dir: Path) -> Path:
    docs = scan_documents(input_root)
    document_entries: list[dict[str, Any]] = []
    for path in docs:
        doc_type = infer_doc_type(path)
        if doc_type == "Supporting":
            continue
        rel = path.relative_to(input_root) if path.is_relative_to(input_root) else path
        document_entries.append(
            {
                "doc_type": doc_type,
                "label": doc_type,
                "path": str(rel),
                "required_for_p0": doc_type == "CER",
                "blocking_for_p0": doc_type == "CER",
                "source_ref": {"document_id": slugify(path.stem), "path": str(rel)},
            }
        )
    profile = {
        "project_id": project_id,
        "cer_run_id": run_dir.name,
        "device_context": {
            "device_name": "To be confirmed from source package",
            "device_class": "To be confirmed",
            "manufacturer": "To be confirmed",
            "intended_use": "To be confirmed from CER/IFU",
        },
        "review_scope": {
            "mode": "single_project_serial_review",
            "review_language": "en",
            "jurisdiction": "EU MDR",
            "human_gate_required": True,
            "final_decision_allowed": False,
        },
        "primary_review_object": "CER",
        "gate_a_status": "accepted",
        "gate_a_accepted": True,
        "input_package": {
            "root_path": str(input_root),
            "type": "CLAUDE_COWORK_GENERATED_INPUT",
            "documents": document_entries,
        },
        "artifact_policy": {
            "artifact_root": str(run_dir / "deerflow_review" / run_dir.name),
            "persist_intermediate_artifacts": True,
        },
        "notes": [
            "Generated by Claude Cowork CER supervisor.",
            "Advisory review only. Human reviewer remains responsible for final regulatory judgment.",
        ],
    }
    profile_path = run_dir / "generated_project_profile.yaml"
    write_json(profile_path, profile)
    return profile_path


def review_start(args: argparse.Namespace) -> int:
    input_root = Path(args.input_root).expanduser().resolve()
    run_dir = make_run_dir(args.project_id, "review", args.run_id)
    run_dir.mkdir(parents=True, exist_ok=True)
    write_questions(run_dir, "review")

    if not input_root.exists():
        write_initial_status(run_dir, {"mode": "review", "project_id": args.project_id, "run_dir": str(run_dir)})
        update_status(run_dir, status="blocked", final_status="HUMAN_HOLD", issues=[f"Input root does not exist: {input_root}"])
        print(json.dumps(read_json(run_dir / "status.json"), ensure_ascii=False, indent=2))
        return 3

    if args.review_engine == "canonical":
        profile_path = Path(args.project_profile).expanduser().resolve() if args.project_profile else build_review_profile(args.project_id, input_root, run_dir)
        profile = read_mapping(profile_path)
        docs = ((profile.get("input_package") or {}).get("documents") or [])
        if not any((doc.get("doc_type") == "CER") for doc in docs):
            write_initial_status(run_dir, {"mode": "review", "project_id": args.project_id, "run_dir": str(run_dir), "input_root": str(input_root)})
            update_status(run_dir, status="blocked", final_status="HUMAN_HOLD", issues=["No CER candidate found. Review mode requires a CER document or extracted CER text."])
            print(json.dumps(read_json(run_dir / "status.json"), ensure_ascii=False, indent=2))
            return 3
        command = [
            str(PYTHON),
            str(REVIEW_SCRIPT),
            "--workflow",
            str(REVIEW_WORKFLOW),
            "--project-profile",
            str(profile_path),
            "--mode",
            "formal-review",
            "--input-root",
            str(input_root),
        ]
        artifact_root = str((profile.get("artifact_policy") or {}).get("artifact_root") or (run_dir / "deerflow_review"))
    else:
        profile_path = None
        artifact_root = str(run_dir / "review_assist")
        command = [
            str(PYTHON),
            str(REVIEW_ASSIST_SCRIPT),
            "--project-id",
            args.project_id,
            "--input-dir",
            str(input_root),
            "--output-dir",
            artifact_root,
        ]

    write_initial_status(
        run_dir,
        {
            "mode": "review",
            "review_engine": args.review_engine,
            "project_id": args.project_id,
            "run_dir": str(run_dir),
            "input_root": str(input_root),
            "project_profile": str(profile_path) if profile_path else None,
            "artifact_root": artifact_root,
            "command": command,
        },
    )
    write_json(
        run_dir / "run_config.json",
        {
            "mode": "review",
            "review_engine": args.review_engine,
            "project_id": args.project_id,
            "input_root": str(input_root),
            "project_profile": str(profile_path) if profile_path else None,
            "artifact_root": artifact_root,
        },
    )
    rc = execute_command(run_dir, command, background=args.background, dry_run=args.dry_run, env=proxy_env(args))
    if not args.background and not args.dry_run:
        postflight(argparse.Namespace(run_dir=str(run_dir), json=True))
    print(json.dumps(status_summary(run_dir), ensure_ascii=False, indent=2))
    return rc


def status_summary(run_dir: Path) -> dict[str, Any]:
    status = read_json(run_dir / "status.json")
    pid = status.get("pid")
    alive = is_process_alive(pid if isinstance(pid, int) else None)
    stdout = run_dir / "stdout.log"
    stderr = run_dir / "stderr.log"
    summary = {
        "run_dir": str(run_dir),
        "mode": status.get("mode"),
        "project_id": status.get("project_id"),
        "status": status.get("status"),
        "final_status": status.get("final_status"),
        "pid": pid,
        "process_alive": alive,
        "returncode": status.get("returncode"),
        "issues": status.get("issues") or [],
        "stdout_log": str(stdout) if stdout.exists() else None,
        "stderr_log": str(stderr) if stderr.exists() else None,
        "artifact_root": status.get("artifact_root"),
    }
    if status.get("status") == "running" and not alive:
        summary["status"] = "process_not_running_status_needs_postflight"
    return summary


def status_cmd(args: argparse.Namespace) -> int:
    summary = status_summary(Path(args.run_dir).expanduser().resolve())
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def find_files(run_dir: Path, names: set[str]) -> list[Path]:
    return [path for path in run_dir.rglob("*") if path.is_file() and path.name in names]


def inspect(args: argparse.Namespace) -> int:
    run_dir = Path(args.run_dir).expanduser().resolve()
    status = read_json(run_dir / "status.json")
    mode = status.get("mode")
    payload: dict[str, Any] = {"run_dir": str(run_dir), "mode": mode, "status": status_summary(run_dir)}
    if mode == "authoring":
        artifact_root = Path(status.get("artifact_root") or run_dir / "deerflow_authoring")
        payload["qa_gate_report"] = read_json(artifact_root / "qa_gate_report.json")
        payload["final_gate_closure_report"] = read_json(artifact_root / "final_gate_closure_report.json")
        payload["authoring_workbook_present"] = (artifact_root / "authoring_workbook.json").exists()
        payload["cer_draft_md"] = str(artifact_root / "CER_draft.md")
    else:
        review_files = find_files(run_dir, {"review_package.json", "review_package.md", "gate_closure_report.json", "candidate_findings.json", "review_report.json"})
        payload["review_artifacts"] = [str(path) for path in review_files]
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def cjk_count(text: str) -> int:
    return len(re.findall(r"[\u3400-\u9fff]", text))


def word_count(text: str) -> int:
    return len(re.findall(r"\b[A-Za-z][A-Za-z0-9'-]*\b", text))


def runtime_protocol_issues(run_dir: Path) -> list[str]:
    haystacks: list[str] = []
    for name in ("stdout.log", "stderr.log", "status.json"):
        path = run_dir / name
        if path.exists():
            haystacks.append(path.read_text(encoding="utf-8", errors="ignore")[-200000:])
    combined = "\n".join(haystacks)
    if any(marker.lower() in combined.lower() for marker in MODEL_PROTOCOL_MARKERS):
        return [
            "DEERFLOW_RUNTIME_PROTOCOL_FAILED: model emitted XML/textual function_calls instead of native tool_calls; "
            "LangGraph did not execute the intended tools. Route tool-using DeerFlow nodes to a native tool-call capable model before re-running."
        ]
    return []


def authoring_postflight(run_dir: Path, status: dict[str, Any]) -> tuple[str, list[str]]:
    issues: list[str] = []
    protocol_issues = runtime_protocol_issues(run_dir)
    if protocol_issues:
        return "EXECUTION_FAILED", protocol_issues
    artifact_root = Path(status.get("artifact_root") or run_dir / "deerflow_authoring")
    missing = [name for name in CORE_AUTHORING_ARTIFACTS if not (artifact_root / name).exists()]
    if missing:
        issues.append(f"Missing authoring artifacts: {', '.join(missing[:8])}{'...' if len(missing) > 8 else ''}")
    cer_md = artifact_root / "CER_draft.md"
    text = cer_md.read_text(encoding="utf-8") if cer_md.exists() else ""
    if not text:
        issues.append("CER_draft.md is missing or empty.")
    else:
        if cjk_count(text) > 0:
            issues.append("CER draft contains CJK/Chinese characters; final report must be English.")
        wc = word_count(text)
        if wc < 18000:
            issues.append(f"CER draft word count is {wc}; NB-ready target is at least 18000 words.")
        found_placeholders = [item for item in AUTHORING_PLACEHOLDERS if item.lower() in text.lower()]
        if found_placeholders:
            issues.append(f"CER draft contains placeholders: {', '.join(found_placeholders)}")
        for chapter in ["2 Scope", "3 Clinical", "4 Device", "4.7", "5 Conclusions"]:
            if chapter.lower() not in text.lower():
                issues.append(f"CER draft may be missing core chapter marker: {chapter}")
    qa = read_json(artifact_root / "qa_gate_report.json")
    closure = read_json(artifact_root / "final_gate_closure_report.json")
    final_decision = closure.get("final_gate_decision") or qa.get("decision")
    failed = qa.get("failed_gate_count")
    if final_decision and final_decision != "PASS_TO_DRAFT_DOCX":
        issues.append(f"Authoring final gate is not PASS_TO_DRAFT_DOCX: {final_decision}")
    if isinstance(failed, int) and failed > 0:
        issues.append(f"Authoring failed gate count is {failed}.")
    if issues:
        return ("REWORK_REQUIRED" if text else "EXECUTION_FAILED"), issues
    return "AUTHORING_NB_READY_DRAFT", []


def contains_terminal_review_verdict(text: str) -> list[str]:
    hits: list[str] = []
    for term in PROHIBITED_REVIEW_VERDICTS:
        pattern = re.compile(rf"\b{re.escape(term)}\b", re.IGNORECASE)
        if pattern.search(text):
            hits.append(term)
    return hits


def review_postflight(run_dir: Path, status: dict[str, Any]) -> tuple[str, list[str]]:
    issues: list[str] = []
    protocol_issues = runtime_protocol_issues(run_dir)
    if protocol_issues:
        return "EXECUTION_FAILED", protocol_issues
    review_files = find_files(run_dir, {"review_package.json", "review_package.md", "review_report.json", "candidate_findings.json"})
    if not review_files:
        issues.append("No review package/report artifacts found.")
        return "EXECUTION_FAILED", issues
    combined = "\n".join(path.read_text(encoding="utf-8", errors="ignore")[:200000] for path in review_files)
    hits = contains_terminal_review_verdict(combined)
    if hits:
        issues.append(f"Review output contains prohibited terminal verdict terms: {', '.join(sorted(set(hits)))}")
    if "source" not in combined.lower() and "evidence" not in combined.lower():
        issues.append("Review output appears to lack source/evidence references.")
    if "severity" not in combined.lower() and "human_gate" not in combined.lower() and "human gate" not in combined.lower():
        issues.append("Review output appears to lack severity or human-gate framing.")

    # V28 Step 8: Auto-compute STRONG baseline (Post-Run Hook)
    try:
        _try_compute_strong_baseline(run_dir)
    except Exception as e:
        issues.append(f"STRONG baseline computation failed (non-blocking): {e}")

    if issues:
        return "REWORK_REQUIRED", issues
    return "REVIEW_PACKAGE_READY", []


def _try_compute_strong_baseline(run_dir: Path) -> None:
    """V28 Step 8: Compute STRONG baseline crosswalk after review completes."""
    strong_baseline_path = run_dir / "strong_baseline.json"
    if strong_baseline_path.exists():
        return  # Already computed — skip

    tools_dir = REPO_ROOT / "tools"
    strong_script = tools_dir / "strong_baseline.py"
    if not strong_script.exists():
        return

    import subprocess
    result = subprocess.run(
        [str(PYTHON), str(strong_script), str(run_dir), "--json"],
        capture_output=True, text=True, timeout=120,
    )
    if result.returncode == 0:
        # Also write a human-readable summary
        try:
            report = json.loads(result.stdout)
            summary = [
                "# STRONG Baseline (Auto-generated)",
                "",
                f"- **Project**: {report.get('project_id', 'unknown')}",
                f"- **Findings extracted**: {report.get('findings_extracted', 0)}",
                f"- **NB observations loaded**: {report.get('nb_observations_loaded', 0)}",
                f"- **Strong Rate**: {report.get('strong_baseline_score', 0):.1%}",
                f"- **Interpretation**: {report.get('interpretation', 'N/A')}",
                "",
                "## Match Distribution",
                "",
            ]
            dist = report.get("crosswalk", {}).get("match_distribution", {})
            for quality in ["STRONG", "MODERATE", "WEAK", "NO_MATCH"]:
                summary.append(f"- **{quality}**: {dist.get(quality, 0)}")
            summary.append("")
            summary.append("> Auto-generated by V28 STRONG Baseline hook. This is a deterministic keyword-overlap crosswalk — not a substitute for human NB review calibration.")
            (run_dir / "strong_baseline.md").write_text("\n".join(summary))
        except Exception:
            pass


def postflight(args: argparse.Namespace) -> int:
    run_dir = Path(args.run_dir).expanduser().resolve()
    status = read_json(run_dir / "status.json")
    if not status:
        print(json.dumps({"final_status": "EXECUTION_FAILED", "issues": ["status.json not found"]}, ensure_ascii=False, indent=2))
        return 2
    mode = status.get("mode")
    if mode == "authoring":
        final_status, issues = authoring_postflight(run_dir, status)
    elif mode == "review":
        final_status, issues = review_postflight(run_dir, status)
    else:
        final_status, issues = "EXECUTION_FAILED", [f"Unknown mode: {mode}"]
    closeout = "\n".join(
        [
            "# Claude Cowork Supervisor Closeout",
            "",
            f"- Run directory: `{run_dir}`",
            f"- Mode: `{mode}`",
            f"- Final status: `{final_status}`",
            "",
            "## Issues",
            *(f"- {issue}" for issue in issues),
            "" if issues else "- None",
            "",
            "Human evaluator/reviewer responsibility remains required before regulatory submission or final decision.",
        ]
    )
    write_text(run_dir / "supervisor_closeout.md", closeout)
    update_status(run_dir, final_status=final_status, issues=issues, status="postflight_completed")
    payload = {"run_dir": str(run_dir), "mode": mode, "final_status": final_status, "issues": issues, "closeout": str(run_dir / "supervisor_closeout.md")}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if final_status in {"AUTHORING_NB_READY_DRAFT", "REVIEW_PACKAGE_READY"} else 2


def rework_plan(args: argparse.Namespace) -> int:
    run_dir = Path(args.run_dir).expanduser().resolve()
    status = read_json(run_dir / "status.json")
    issues = status.get("issues") or []
    lines = [
        "# CER Cowork Rework Plan",
        "",
        f"- Run directory: `{run_dir}`",
        f"- Mode: `{status.get('mode')}`",
        f"- Final status: `{status.get('final_status')}`",
        "",
        "## Required Actions",
    ]
    if not issues:
        lines.append("- No blocking issues recorded. Re-run `postflight` if this looks stale.")
    for idx, issue in enumerate(issues, start=1):
        lines.append(f"{idx}. {issue}")
    lines += [
        "",
        "## Boundary",
        "",
        "Do not mark the package as NB-ready until postflight returns an accepted final status.",
    ]
    path = run_dir / "rework_plan.md"
    write_text(path, "\n".join(lines) + "\n")
    print(json.dumps({"rework_plan": str(path), "issue_count": len(issues)}, ensure_ascii=False, indent=2))
    return 0


def deep_postflight(args: argparse.Namespace) -> int:
    run_dir = Path(args.run_dir).expanduser().resolve()
    payload = load_repair_module().build_deep_postflight(run_dir)
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    return 0 if not any(issue.get("severity") == "critical" for issue in payload.get("issues", [])) else 2


def classify_rework(args: argparse.Namespace) -> int:
    run_dir = Path(args.run_dir).expanduser().resolve()
    payload = load_repair_module().classify_rework(run_dir)
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    return 0 if payload.get("decision") in {"ACCEPT_BASELINE", "CONTROLLED_MINOR_PATCH", "EVIDENCE_ENHANCEMENT_REQUIRED", "HUMAN_HOLD"} else 2


def pico_loop(args: argparse.Namespace) -> int:
    run_dir = Path(args.run_dir).expanduser().resolve()
    payload = load_repair_module().build_pico_loop(run_dir)
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    return 0


def fulltext_request(args: argparse.Namespace) -> int:
    run_dir = Path(args.run_dir).expanduser().resolve()
    payload = load_repair_module().build_fulltext_request(run_dir)
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    return 0


def fulltext_ingest(args: argparse.Namespace) -> int:
    run_dir = Path(args.run_dir).expanduser().resolve()
    payload = load_repair_module().fulltext_ingest(run_dir, fulltext_root=args.fulltext_root)
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    return 0 if payload.get("file_count", 0) > 0 else 2


def sota_endpoint_enhance(args: argparse.Namespace) -> int:
    run_dir = Path(args.run_dir).expanduser().resolve()
    payload = load_repair_module().sota_endpoint_enhance(run_dir)
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    return 0 if payload.get("enhanced_endpoint_count", 0) > 0 else 2


def sota_reasoning_patch(args: argparse.Namespace) -> int:
    run_dir = Path(args.run_dir).expanduser().resolve()
    payload = load_repair_module().sota_reasoning_patch(run_dir)
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    return 0


def sota_narrative_merge(args: argparse.Namespace) -> int:
    run_dir = Path(args.run_dir).expanduser().resolve()
    payload = load_repair_module().sota_narrative_merge(run_dir)
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    return 0


def nb_flag_triage(args: argparse.Namespace) -> int:
    run_dir = Path(args.run_dir).expanduser().resolve()
    payload = load_repair_module().nb_flag_triage(run_dir)
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    return 0


def pico_v2_execute(args: argparse.Namespace) -> int:
    run_dir = Path(args.run_dir).expanduser().resolve()
    payload = load_repair_module().pico_v2_execute(run_dir)
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    return 0


def rmf_pmcf_closure(args: argparse.Namespace) -> int:
    run_dir = Path(args.run_dir).expanduser().resolve()
    payload = load_repair_module().rmf_pmcf_closure(run_dir)
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    return 0


def self_check_scorecard(args: argparse.Namespace) -> int:
    run_dir = Path(args.run_dir).expanduser().resolve()
    payload = load_repair_module().self_check_scorecard(run_dir)
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    return 0 if payload.get("delivery_conclusion") != "NOT_DELIVERABLE" else 2


def controlled_patch(args: argparse.Namespace) -> int:
    run_dir = Path(args.run_dir).expanduser().resolve()
    payload = load_repair_module().controlled_patch(run_dir)
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    return 0


def consistency_gate(args: argparse.Namespace) -> int:
    run_dir = Path(args.run_dir).expanduser().resolve()
    payload = load_repair_module().consistency_gate(run_dir)
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    return 0 if payload.get("decision") == "PASS" else 2


def signature_readiness_check(args: argparse.Namespace) -> int:
    run_dir = Path(args.run_dir).expanduser().resolve()
    payload = load_repair_module().signature_readiness_check(run_dir)
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    return 0 if payload.get("decision") == "SIGNATURE_REVIEW_CANDIDATE" else 2


def finalize_package(args: argparse.Namespace) -> int:
    run_dir = Path(args.run_dir).expanduser().resolve()
    payload = load_repair_module().finalize_package(run_dir, beautify_docx=args.beautify_docx, theme=args.theme)
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    return 0 if payload.get("decision") in {"SIGNATURE_READY", "CONTROLLED_DRAFT_WITH_GAPS"} else 2


def publish_final_package(args: argparse.Namespace) -> int:
    run_dir = Path(args.run_dir).expanduser().resolve()
    payload = load_repair_module().publish_final_package(run_dir)
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    return 0 if payload.get("decision") in {"SIGNATURE_READY", "CONTROLLED_DRAFT_WITH_GAPS"} else 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Claude Cowork wrapper for DeerFlow CER authoring/review.")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_common_start(p: argparse.ArgumentParser) -> None:
        p.add_argument("--project-id", required=True)
        p.add_argument("--input-root", required=True)
        p.add_argument("--run-id")
        p.add_argument("--background", action="store_true")
        p.add_argument("--dry-run", action="store_true")
        p.add_argument("--no-proxy", action="store_true", help="Force direct API networking for the DeerFlow child process.")
        p.add_argument("--proxy-url", help="Opt in to an HTTP(S) proxy URL for this run only.")
        p.add_argument("--all-proxy-url", help="Opt in to an ALL_PROXY URL for this run only.")

    authoring = sub.add_parser("authoring-start", help="Start strict DeerFlow CER authoring.")
    add_common_start(authoring)
    authoring.add_argument("--target-keywords", default="")
    authoring.add_argument("--supplement-root", action="append", default=[])
    authoring.set_defaults(func=authoring_start)

    review = sub.add_parser("review-start", help="Start DeerFlow CER review.")
    add_common_start(review)
    review.add_argument("--project-profile")
    review.add_argument("--review-engine", choices=["canonical", "assist"], default="canonical")
    review.set_defaults(func=review_start)

    status_p = sub.add_parser("status", help="Show run status.")
    status_p.add_argument("--run-dir", required=True)
    status_p.set_defaults(func=status_cmd)

    inspect_p = sub.add_parser("inspect", help="Inspect run artifacts.")
    inspect_p.add_argument("--run-dir", required=True)
    inspect_p.set_defaults(func=inspect)

    postflight_p = sub.add_parser("postflight", help="Run Claude-side postflight gates.")
    postflight_p.add_argument("--run-dir", required=True)
    postflight_p.add_argument("--json", action="store_true")
    postflight_p.set_defaults(func=postflight)

    rework_p = sub.add_parser("rework-plan", help="Create a rework plan from status issues.")
    rework_p.add_argument("--run-dir", required=True)
    rework_p.set_defaults(func=rework_plan)

    deep_p = sub.add_parser("deep-postflight", help="Run Claude-side deep postflight across baseline CER artifacts.")
    deep_p.add_argument("--run-dir", required=True)
    deep_p.set_defaults(func=deep_postflight)

    classify_p = sub.add_parser("classify-rework", help="Classify whether to accept, patch, request evidence, hold, or rerun DeerFlow.")
    classify_p.add_argument("--run-dir", required=True)
    classify_p.set_defaults(func=classify_rework)

    pico_p = sub.add_parser("pico-loop", help="Generate PICO revision log from search/evidence/endpoint sufficiency.")
    pico_p.add_argument("--run-dir", required=True)
    pico_p.set_defaults(func=pico_loop)

    fulltext_p = sub.add_parser("fulltext-request", help="Generate full-text request list and evidence gap register.")
    fulltext_p.add_argument("--run-dir", required=True)
    fulltext_p.set_defaults(func=fulltext_request)

    ingest_p = sub.add_parser("fulltext-ingest", help="Ingest user-provided full text PDFs/DOCX/TXT and extract page-level endpoint candidates.")
    ingest_p.add_argument("--run-dir", required=True)
    ingest_p.add_argument("--fulltext-root", help="Folder or file containing user-provided full text. Defaults to project/run full-text folders.")
    ingest_p.set_defaults(func=fulltext_ingest)

    enhance_p = sub.add_parser("sota-endpoint-enhance", help="Enhance SOTA endpoint and benchmark tables from ingested full text.")
    enhance_p.add_argument("--run-dir", required=True)
    enhance_p.set_defaults(func=sota_endpoint_enhance)

    sota_patch_p = sub.add_parser("sota-reasoning-patch", help="Patch SOTA endpoint derivation and 4.7 use narrative from enhanced evidence.")
    sota_patch_p.add_argument("--run-dir", required=True)
    sota_patch_p.set_defaults(func=sota_reasoning_patch)

    sota_merge_p = sub.add_parser("sota-narrative-merge", help="Merge differentiated SOTA benchmark narratives into the final CER body.")
    sota_merge_p.add_argument("--run-dir", required=True)
    sota_merge_p.set_defaults(func=sota_narrative_merge)

    nb_triage_p = sub.add_parser("nb-flag-triage", help="Write one-by-one triage rows for NB precheck flags.")
    nb_triage_p.add_argument("--run-dir", required=True)
    nb_triage_p.set_defaults(func=nb_flag_triage)

    pico_v2_p = sub.add_parser("pico-v2-execute", help="Convert PICO-loop narrow/split/broaden advice into a PICO v2 strategy table.")
    pico_v2_p.add_argument("--run-dir", required=True)
    pico_v2_p.set_defaults(func=pico_v2_execute)

    rmf_p = sub.add_parser("rmf-pmcf-closure", help="Generate RMF deep-extraction, risk-benefit closure, and PMCF timetable request tables.")
    rmf_p.add_argument("--run-dir", required=True)
    rmf_p.set_defaults(func=rmf_pmcf_closure)

    patch_p = sub.add_parser("controlled-patch", help="Create Claude repair package without overwriting DeerFlow baseline artifacts.")
    patch_p.add_argument("--run-dir", required=True)
    patch_p.set_defaults(func=controlled_patch)

    consistency_p = sub.add_parser("consistency-gate", help="Validate patched CER/workbook consistency.")
    consistency_p.add_argument("--run-dir", required=True)
    consistency_p.set_defaults(func=consistency_gate)

    readiness_p = sub.add_parser("signature-readiness-check", help="Check whether the patched CER package is ready for human evaluator signature review.")
    readiness_p.add_argument("--run-dir", required=True)
    readiness_p.set_defaults(func=signature_readiness_check)

    scorecard_p = sub.add_parser("self-check-scorecard", help="Run the 55-item CER self-check scorecard and delivery classification.")
    scorecard_p.add_argument("--run-dir", required=True)
    scorecard_p.set_defaults(func=self_check_scorecard)

    finalize_p = sub.add_parser("finalize-package", help="Write final Claude repair closeout report.")
    finalize_p.add_argument("--run-dir", required=True)
    finalize_p.add_argument("--beautify-docx", action="store_true", help="Run final DOCX beautification after consistency-gate PASS.")
    finalize_p.add_argument("--theme", default="slate", choices=["slate", "forest", "wine", "ink"], help="docx-beautifier theme.")
    finalize_p.set_defaults(func=finalize_package)

    publish_p = sub.add_parser("publish-final-package", help="Publish the current repair package to deerflow_authoring/final without overwriting baseline.")
    publish_p.add_argument("--run-dir", required=True)
    publish_p.set_defaults(func=publish_final_package)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
