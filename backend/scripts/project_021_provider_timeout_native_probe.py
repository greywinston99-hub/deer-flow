#!/usr/bin/env python3
"""PROJECT_021 native graph provider-timeout probe.

This is a diagnostic-only smoke. It invokes the CER Review Assist native graph
through the existing formal launcher helpers, but replaces the router primary
provider with a hanging fake model and the fallback provider with a compact JSON
fake model. The goal is to prove the actual runtime code path turns provider
hangs into timeout/fallback or clean failure, while always writing artifacts.
"""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import inspect
import json
import shutil
import sys
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, AIMessageChunk
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult


DEERFLOW_BACKEND = Path("/Users/winstonwei/Documents/Playground/deer-flow/backend")
DEERFLOW_HARNESS = DEERFLOW_BACKEND / "packages/harness"
LAUNCHER_PATH = Path(
    "/Users/winstonwei/CER-RAG/00_knowledge_extraction_build/round2_autonomous_loop/"
    "00_controller/deerflow_client_invocation/run_project_021_review.py"
)
PROBE_ROOT = Path(
    "/Users/winstonwei/CER-RAG/00_knowledge_extraction_build/round2_autonomous_loop/"
    "10_reports/project_learning_capsules/PROJECT_021/v6_provider_timeout_probes"
)
FAMILY = "DECLARATION_OF_CONFORMITY"

sys.path.insert(0, str(DEERFLOW_HARNESS))


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def append_event(path: Path, run_id: str, event: str, **data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"timestamp": now_iso(), "run_id": run_id, "event": event, **data}, ensure_ascii=False) + "\n")


def load_launcher_module():
    spec = importlib.util.spec_from_file_location("project_021_v5_launcher_for_timeout_probe", LAUNCHER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load launcher module from {LAUNCHER_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class HangingPrimaryModel(BaseChatModel):
    sleep_seconds: float = 3600.0

    @property
    def _llm_type(self) -> str:
        return "project-021-hanging-primary"

    def bind_tools(self, tools, *, tool_choice=None, **kwargs):
        return self.bind(tools=tools, tool_choice=tool_choice, **kwargs)

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        raise TimeoutError("Synchronous path not used by this native probe")

    async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):
        await asyncio.sleep(self.sleep_seconds)
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content="unreachable"))])

    async def _astream(self, messages, stop=None, run_manager=None, **kwargs):
        await asyncio.sleep(self.sleep_seconds)
        if False:
            yield ChatGenerationChunk(message=AIMessageChunk(content="unreachable"))


class FallbackJsonModel(BaseChatModel):
    @property
    def _llm_type(self) -> str:
        return "project-021-fallback-json"

    def bind_tools(self, tools, *, tool_choice=None, **kwargs):
        return self.bind(tools=tools, tool_choice=tool_choice, **kwargs)

    def _payload_for(self, messages) -> str:
        prompt = "\n".join(str(getattr(message, "content", "")) for message in messages)
        if "severity_signals" in prompt or "Logic QA" in prompt:
            payload = {
                "schema_name": "cer_review_severity_synthesis",
                "schema_version": "probe",
                "reviewer_decision": "PENDING",
                "severity_signals": [],
                "human_gate_items": [],
                "summary": {"total_signals": 0},
            }
        elif "candidate_findings" in prompt or "Gap Specialist" in prompt:
            payload = {
                "schema_name": "cer_review_gap_findings",
                "schema_version": "v2",
                "reviewer_decision": "PENDING",
                "candidate_findings": [],
                "summary": {"total_gaps": 0, "blocking_gaps": 0, "warning_gaps": 0, "informational_gaps": 0},
                "pipeline_limitations": [{"description": "Provider timeout probe fallback response", "affected_documents": [], "limitation_type": "diagnostic_probe"}],
            }
        else:
            payload = {
                "schema_name": "cer_review_source_inventory",
                "schema_version": "probe",
                "reviewer_decision": "PENDING",
                "source_inventory": [
                    {
                        "file_id": "S-001",
                        "relative_path": "DECLARATION_OF_CONFORMITY_extracted.txt",
                        "document_type": "Declaration of Conformity",
                        "document_status": "PARTIAL",
                        "evidence_role": "diagnostic_probe_input",
                    }
                ],
            }
        return "```json\n" + json.dumps(payload, ensure_ascii=False) + "\n```"

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=self._payload_for(messages)))])

    async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):
        return self._generate(messages, stop=stop, run_manager=run_manager, **kwargs)

    async def _astream(self, messages, stop=None, run_manager=None, **kwargs):
        yield ChatGenerationChunk(message=AIMessageChunk(content=self._payload_for(messages), chunk_position="last"))


def runtime_introspection(provider_timeout: float, subagent_timeout: float) -> dict[str, Any]:
    import deerflow.models.failover_router as router_module
    import deerflow.runtime.cer_review.review_assist_lead_agent as lead
    from deerflow.config import get_app_config
    from deerflow.models import create_chat_model

    executor_module = sys.modules[lead.SubagentExecutor.__module__]
    router = create_chat_model("minimax-m2.7-highspeed")
    app_config = get_app_config()
    router_cfg = app_config.get_model_config("minimax-m2.7-highspeed")
    return {
        "python": sys.executable,
        "sys_path_head": sys.path[:5],
        "launcher_path": str(LAUNCHER_PATH),
        "failover_router_file": router_module.__file__,
        "subagent_executor_file": executor_module.__file__,
        "router_class": router.__class__.__name__,
        "router_config_provider_timeout_seconds": getattr(router, "provider_timeout_seconds", None),
        "router_config_primary": getattr(router, "primary_model_name", None),
        "router_config_fallback": getattr(router, "fallback_model_name", None),
        "router_config_without_secret": router_cfg.model_dump(exclude={"api_key", "anthropic_api_key"}, exclude_none=True) if router_cfg else None,
        "probe_provider_timeout_seconds": provider_timeout,
        "probe_subagent_timeout_seconds": subagent_timeout,
        "patch_loaded": {
            "has_provider_timeout_error": hasattr(router_module, "ProviderTimeoutError"),
            "executor_has_async_timeout": "asyncio.timeout" in inspect.getsource(executor_module.SubagentExecutor._aexecute),
        },
    }


async def run_probe(args: argparse.Namespace) -> int:
    launcher = load_launcher_module()
    run_id = args.run_id or f"proj-021-v6-provider-timeout-probe-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:6]}"
    run_root = PROBE_ROOT / run_id
    if run_root.exists():
        shutil.rmtree(run_root)
    run_root.mkdir(parents=True, exist_ok=True)
    events_path = run_root / "events.jsonl"

    append_event(events_path, run_id, "run_started", probe="provider_timeout_native_graph", family=FAMILY)
    status_base = {
        "run_id": run_id,
        "command_id": "PROJECT_021_V6_PROVIDER_TIMEOUT_NATIVE_PROBE",
        "status": "running",
        "started_at": now_iso(),
        "artifact_root": str(run_root),
        "input_families": [FAMILY],
    }
    write_json(run_root / "status.json", {**status_base, "error": None})

    introspection = runtime_introspection(args.provider_timeout, args.subagent_timeout)
    write_json(run_root / "runtime_introspection.json", introspection)

    import deerflow.models.failover_router as router_module
    import deerflow.runtime.cer_review.review_assist_lead_agent as lead

    executor_module = sys.modules[lead.SubagentExecutor.__module__]

    original_executor_create_chat_model = executor_module.create_chat_model
    original_router_create_chat_model = router_module.create_chat_model

    def executor_model_factory(name: str | None = None, **kwargs):
        if name == "minimax-m2.7-highspeed":
            return router_module.FailoverChatModel(
                model="PROJECT_021 timeout probe router",
                primary_model_name="probe-primary-hang",
                fallback_model_name="probe-fallback-json",
                cooldown_seconds=30,
                provider_timeout_seconds=args.provider_timeout,
                state_file=str(run_root / "probe_failover_state.json"),
            )
        return original_executor_create_chat_model(name=name, **kwargs)

    def router_model_factory(name: str | None = None, **kwargs):
        if name == "probe-primary-hang":
            return HangingPrimaryModel(sleep_seconds=args.hang_sleep)
        if name == "probe-fallback-json":
            return FallbackJsonModel()
        return original_router_create_chat_model(name=name, **kwargs)

    executor_module.create_chat_model = executor_model_factory
    router_module.create_chat_model = router_model_factory

    run = launcher.FormalRun(run_id, run_root, model="router", smoke=True)
    run.events_path = events_path
    failure = None
    final_status = "failed"
    families = [FAMILY]
    try:
        mcp_status = launcher.configure_headless_mcp_disabled(run)
        task_packet = launcher.build_task_packet(families, [], run)
        task_packet["command_id"] = "PROJECT_021_V6_PROVIDER_TIMEOUT_NATIVE_PROBE"
        task_packet["schema_name"] = "project_021_v6_provider_timeout_probe_task_packet"
        task_packet["probe"] = {
            "purpose": "prove provider hang timeout/fallback in native graph runtime",
            "provider_timeout_seconds": args.provider_timeout,
            "subagent_timeout_seconds": args.subagent_timeout,
            "primary_model": "probe-primary-hang",
            "fallback_model": "probe-fallback-json",
        }
        task_packet["runtime_introspection"] = introspection
        task_packet["mcp_headless"] = mcp_status
        write_json(run_root / "task_packet.json", task_packet)

        import deerflow.runtime.cer_review.review_assist_lead_agent as lead

        original_build_subagent_config = lead._build_subagent_config

        def short_timeout_build_subagent_config(skill_name, skill_prompt, model_override=None, tools_override=None):
            cfg = original_build_subagent_config(skill_name, skill_prompt, model_override=model_override, tools_override=tools_override)
            cfg.timeout_seconds = args.subagent_timeout
            return cfg

        lead._build_subagent_config = short_timeout_build_subagent_config
        try:
            result = await launcher.run_review_assist_family(run, FAMILY)
            run.family_results.append(result)
        finally:
            lead._build_subagent_config = original_build_subagent_config

        failover_state = launcher.read_json(run_root / "probe_failover_state.json")
        write_json(run_root / "probe_failover_state_observed.json", failover_state)
        observed = json.dumps(failover_state, ensure_ascii=False).lower()
        timeout_observed = "timed out" in observed and "probe-fallback-json" in observed
        append_event(events_path, run_id, "provider_timeout_observed", timeout_observed=timeout_observed, failover_state=failover_state)
        if result.get("status") == "completed" and timeout_observed:
            final_status = "completed"
            append_event(events_path, run_id, "run_completed", status=final_status)
        else:
            failure = {
                "classes": ["PROVIDER_TIMEOUT_PROBE_FAILED"],
                "primary_class": "PROVIDER_TIMEOUT_PROBE_FAILED",
                "message": "Native graph finished without proving timeout fallback",
                "family_result": result,
                "failover_state": failover_state,
            }
            append_event(events_path, run_id, "run_failed", status="failed", error=failure)
    except Exception as exc:
        failure = {
            "classes": ["PROVIDER_TIMEOUT_PROBE_EXCEPTION"],
            "primary_class": "PROVIDER_TIMEOUT_PROBE_EXCEPTION",
            "message": str(exc),
            "exception_type": type(exc).__name__,
            "traceback": traceback.format_exc(),
        }
        append_event(events_path, run_id, "run_failed", status="failed", error=failure)
    finally:
        executor_module.create_chat_model = original_executor_create_chat_model
        router_module.create_chat_model = original_router_create_chat_model

    native_summary = launcher.write_native_stage_summary(run)
    launcher.write_raw_response(run)
    launcher.write_result_summary(run, families, native_summary)
    result_path = run_root / "result.md"
    if result_path.exists():
        result_text = result_path.read_text(encoding="utf-8")
        result_text = result_text.replace("# PROJECT_021 V5 Native Run Result", "# PROJECT_021 V6 Provider Timeout Native Probe Result")
        result_text = result_text.replace("Command ID: `PROJECT_021_NATIVE_RUN_CMD_V5`", "Command ID: `PROJECT_021_V6_PROVIDER_TIMEOUT_NATIVE_PROBE`")
        result_path.write_text(result_text, encoding="utf-8")
    run.completed_at = now_iso()
    run.failure = failure
    launcher.write_failure_classification(run)
    model_diag = launcher.get_model_diagnostics("router")
    model_diag["runtime_introspection"] = introspection
    launcher.write_status(run, families, status=final_status, error=failure, model_diag=model_diag)
    status_path = run_root / "status.json"
    status_payload = launcher.read_json(status_path)
    status_payload["command_id"] = "PROJECT_021_V6_PROVIDER_TIMEOUT_NATIVE_PROBE"
    write_json(status_path, status_payload)
    print(f"PROBE_STATUS={final_status}")
    print(f"PROBE_ARTIFACT_ROOT={run_root}")
    return 0 if final_status == "completed" else 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="PROJECT_021 V6 provider timeout native graph probe")
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--provider-timeout", type=float, default=1.0)
    parser.add_argument("--subagent-timeout", type=float, default=8.0)
    parser.add_argument("--hang-sleep", type=float, default=3600.0)
    return parser.parse_args()


def main() -> int:
    return asyncio.run(run_probe(parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
