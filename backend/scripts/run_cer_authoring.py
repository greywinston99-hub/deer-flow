"""Run the isolated CER authoring graph for a source package.

Example:
    python backend/scripts/run_cer_authoring.py \
      --project-id EONHAR_UAS_PILOT \
      --input-root "/path/to/source/package" \
      --artifact-root "/path/to/output"
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
from pathlib import Path

_NATIVE_PRELOADS = ("pandas._libs.writers",)


def _preload_native_modules_before_deerflow_import() -> dict[str, str]:
    status: dict[str, str] = {}
    for module_name in _NATIVE_PRELOADS:
        try:
            importlib.import_module(module_name)
        except Exception as exc:  # pragma: no cover - optional runtime dependency guard
            status[module_name] = f"unavailable:{type(exc).__name__}:{exc}"
        else:
            status[module_name] = "loaded"
    return status


_NATIVE_PRELOAD_STATUS = _preload_native_modules_before_deerflow_import()

from deerflow.runtime.cer_authoring.graph import build_cer_authoring_graph

DEFAULT_STRICT_AUTHORING_MODEL = "kimi-k2.6-code"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run cer_authoring_v1 against an IFU/source package.")
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--input-root", required=True)
    parser.add_argument(
        "--supplement-root",
        action="append",
        default=[],
        help="Additional source folders to search for RMF/GSPR/PMS/performance files. May be provided multiple times.",
    )
    parser.add_argument("--artifact-root", required=True)
    parser.add_argument(
        "--target-keywords",
        default="",
        help="Comma-separated target device keywords used to select the primary IFU/RMF/evidence files.",
    )
    parser.add_argument("--json", action="store_true", help="Print the full final summary as JSON.")
    parser.add_argument(
        "--strict-v7",
        action="store_true",
        help="Require real LLM authoring-* subagents and strict v7 gates.",
    )
    parser.add_argument(
        "--agent-team-mode",
        choices=["stable-1plus6", "legacy-20"],
        default="stable-1plus6",
        help="Physical CER authoring agent team mode. stable-1plus6 is the production default; legacy-20 is for comparison only.",
    )
    parser.add_argument("--model-name", default="", help="Optional parent model name inherited by authoring subagents.")
    args = parser.parse_args()
    if args.strict_v7:
        os.environ["CER_AUTHORING_STRICT_V7"] = "1"
        os.environ["CER_AUTHORING_ENABLE_LLM_AGENTS"] = "1"
    os.environ["CER_AUTHORING_AGENT_TEAM_MODE"] = args.agent_team_mode
    model_name = args.model_name or os.environ.get("CER_AUTHORING_MODEL_NAME") or (DEFAULT_STRICT_AUTHORING_MODEL if args.strict_v7 else None)
    if model_name:
        os.environ["CER_AUTHORING_MODEL_NAME"] = model_name

    input_root = Path(args.input_root).expanduser().resolve()
    artifact_root = Path(args.artifact_root).expanduser().resolve()
    artifact_root.mkdir(parents=True, exist_ok=True)

    graph = build_cer_authoring_graph()
    result = graph.invoke(
        {
            "messages": [],
            "project_id": args.project_id,
            "input_root": str(input_root),
            "supplement_roots": [str(Path(item).expanduser().resolve()) for item in args.supplement_root],
            "artifact_root": str(artifact_root),
            "target_keywords": [item.strip() for item in args.target_keywords.split(",") if item.strip()],
            "model_name": model_name,
            "agent_team_mode": args.agent_team_mode,
            "native_preload_status": _NATIVE_PRELOAD_STATUS,
        }
    )
    summary = {
        "project_id": args.project_id,
        "input_root": str(input_root),
        "artifact_root": str(artifact_root),
        "status": result.get("status"),
        "final_gate_decision": result.get("final_gate_decision"),
        "failed_gate_count": (result.get("qa_gate_report") or {}).get("failed_gate_count"),
        "source_count": len(result.get("source_inventory") or []),
        "claim_count": len(result.get("claim_ledger") or []),
        "pico_count": len(result.get("cep_pico_matrix") or []),
        "evidence_count": len(result.get("evidence_registry") or []),
        "risk_count": len(result.get("risk_trace_matrix") or []),
        "artifact_count": len(result.get("artifacts") or []),
        "agent_team_mode": result.get("agent_team_mode") or args.agent_team_mode,
    }
    print(json.dumps(summary if args.json else {k: v for k, v in summary.items()}, ensure_ascii=False, indent=2))
    return 0 if result.get("final_gate_decision") == "PASS_TO_DRAFT_DOCX" else 2


if __name__ == "__main__":
    raise SystemExit(main())
