"""Subagent harness adapter for CER authoring.

The production pipeline remains deterministic for testability, but R6 records
and can execute every authoring-* role through DeerFlow's SubagentExecutor.  In
CI and local no-model environments the adapter records configured harness tasks;
when ``CER_AUTHORING_ENABLE_LLM_AGENTS=1`` or ``CER_AUTHORING_STRICT_V7=1`` is
set, it performs real subagent execution and returns the raw review/writing
response for audit.
"""

from __future__ import annotations

import json
import os
import re
import importlib
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from dataclasses import replace
from pathlib import Path
from typing import Any

from deerflow.runtime.cer_authoring.agents import STABLE_AGENT_TEAM_MODE, build_authoring_subagent_configs, covered_virtual_roles


RUN_SCOPED_STATE_CATEGORIES: dict[str, tuple[str, ...]] = {
    "source_intake_identity": (
        "source_inventory",
        "source_role_report",
        "input_gap_list",
        "device_profile",
        "device_identity_lock",
        "device_identity_arbitration",
        "device_identity_arbitration_table",
        "domain_contamination_report",
    ),
    "claims_pico_methodology": (
        "claim_ledger",
        "intended_purpose_claim_table",
        "cep_pico_matrix",
        "sota_pico_strategy",
        "due_pico_strategy",
        "literature_search_protocol_profile",
        "database_search_source_table",
        "literature_defined_limits",
        "literature_flow_registry",
        "protocol_deviation_log",
        "prisma_flow_data",
        "prisma_flow_diagram",
    ),
    "search_sota_evidence": (
        "search_run_registry",
        "sota_search_strategy_table",
        "sota_screening_disposition_table",
        "sota_ck_appraisal_table",
        "due_suitability_contribution_table",
        "raw_literature_records",
        "screening_disposition",
        "article_appraisal",
        "evidence_registry",
        "endpoint_extraction",
        "sota_benchmark_matrix",
        "endpoint_registry",
        "sota_endpoint_derivation_table",
        "sota_quantitative_benchmark_table",
        "sota_evidence_synthesis_matrix",
        "sota_claim_reverse_correction_table",
        "sota_medical_field_boundary",
        "sota_pico_v2_strategy",
        "sota_search_strategy_separated",
        "sota_screening_prisma",
        "sota_evidence_hierarchy",
        "sota_endpoint_extraction_fulltext",
        "sota_benchmark_derivation_table",
        "sota_section_conclusion_matrix",
        "sota_deduction_chain",
        "sota_endpoint_source_classification",
        "sota_aggregate_benchmark_rationale",
        "sota_conclusion_strength_guard",
        "sota_clinical_context_table",
        "sota_benchmark_contextual_rationale",
        "sota_context_injection_trace",
        "full_text_request_list",
        "sota_literature_quantity_justification",
    ),
    "equivalence_vigilance_risk_gspr": (
        "alternative_treatment_benchmark_table",
        "guideline_pathway_table",
        "similar_benchmark_device_table",
        "hazard_source_table",
        "sota_to_47_usage_matrix",
        "equivalence_matrix",
        "similar_device_four_step_confirmation",
        "similar_device_attachment_index",
        "vigilance_recall_registry",
        "vigilance_event_statistics",
        "vigilance_relevance_screening",
        "risk_trace_matrix",
        "gspr_coverage",
    ),
    "writer_synthesis_report": (
        "claim_evidence_matrix",
        "benefit_risk_ledger",
        "writer_conclusion_strength_guard",
        "cer_section_trace_map",
        "alignment_matrix",
        "cross_evidence_synthesis_table",
        "cross_evidence_synthesis_narratives",
        "writer_synthesis_trace",
        "writer_device_template_profile",
        "writer_device_conditional_sections",
        "cer_chapter_drafts",
        "gap_pmcf_recommendations",
        "pmcf_boundary_decision_log",
        "marketing_pms_customer_questionnaire",
    ),
    "qa_review_gate": (
        "qa_gate_report",
        "reviewer_results",
        "lead_decisions",
        "virtual_review_dimensions",
        "subagent_invocation_log",
        "rework_queue",
        "final_gate_decision",
        "stage_results",
    ),
    "artifact_mcp_template": (
        "mcp_call_log",
        "mcp_tool_results",
        "template_guidance",
        "writing_brief",
        "ap_template_profile",
        "template_logic_profile",
        "engineer_comment_profile",
        "human_cer_comparison_report",
        "human_style_benchmark_report",
        "authoring_workbook",
        "artifacts",
    ),
    "calibration_baseline_delta": (
        "authoring_baseline_version",
        "calibration_case_schema",
        "artifact_consumption_contract",
        "failure_taxonomy_cer_authoring",
        "cer_section_trace_map_schema",
        "gate_to_upstream_repair_map",
        "authoring_baseline_freeze_manifest",
        "calibration_event_log",
        "run_scope_audit",
    ),
}

RUN_SCOPED_STATE_KEYS = frozenset(key for keys in RUN_SCOPED_STATE_CATEGORIES.values() for key in keys)
RUN_INPUT_STATE_KEYS = frozenset(
    {
        "messages",
        "project_id",
        "input_root",
        "supplement_roots",
        "uploaded_files",
        "target_keywords",
        "artifact_root",
        "model_name",
        "agent_team_mode",
        "sandbox",
        "thread_data",
        "thread_id",
    }
)

_GIL_SAFE_NATIVE_PRELOADS: tuple[str, ...] = ("pandas._libs.writers",)
_GIL_SAFE_NATIVE_PRELOAD_STATUS: dict[str, str] = {}


def preload_gil_safe_native_modules() -> dict[str, str]:
    """Preload known native modules before CER subagent worker threads start.

    CAL-002 Phase 6 exposed a reproducible deadlock during first-time import of
    ``pandas._libs.writers`` from the agent execution path.  Importing the
    extension once from the main runtime path keeps its C-extension init outside
    the ThreadPoolExecutor timeout worker and avoids changing graph, gate,
    agent, evidence, or identity behavior.
    """

    for module_name in _GIL_SAFE_NATIVE_PRELOADS:
        if module_name in _GIL_SAFE_NATIVE_PRELOAD_STATUS:
            continue
        try:
            importlib.import_module(module_name)
        except Exception as exc:  # pragma: no cover - optional dependency/environment guard
            _GIL_SAFE_NATIVE_PRELOAD_STATUS[module_name] = f"unavailable:{type(exc).__name__}:{exc}"
        else:
            _GIL_SAFE_NATIVE_PRELOAD_STATUS[module_name] = "loaded"
    return dict(_GIL_SAFE_NATIVE_PRELOAD_STATUS)


def invoke_authoring_agent(agent_name: str, state: dict[str, Any], task: str, *, reviewer: bool = False) -> dict[str, Any]:
    native_preload_status = preload_gil_safe_native_modules()
    state = sanitize_run_scoped_state_for_agent_prompt(state)
    enabled = _env_enabled("CER_AUTHORING_ENABLE_LLM_AGENTS") or _env_enabled("CER_AUTHORING_STRICT_V7")
    agent_team_mode = state.get("agent_team_mode") or os.getenv("CER_AUTHORING_AGENT_TEAM_MODE") or STABLE_AGENT_TEAM_MODE
    payload = {
        "agent": agent_name,
        "agent_team_mode": agent_team_mode,
        "covered_virtual_roles": covered_virtual_roles(agent_name),
        "mode": "llm_subagent" if enabled else "harness_configured",
        "status": "CONFIGURED",
        "reviewer": reviewer,
        "task": task[:1200],
        "native_preload_status": native_preload_status,
    }
    if not enabled:
        return payload

    try:
        from deerflow.subagents.executor import SubagentExecutor, SubagentStatus
    except Exception as exc:  # pragma: no cover - environment dependent
        return {**payload, "status": "UNAVAILABLE", "error": f"{type(exc).__name__}: {exc}"}

    configs = build_authoring_subagent_configs(agent_team_mode)
    config = configs.get(agent_name)
    if config is None:
        return {**payload, "status": "UNAVAILABLE", "error": "authoring subagent config not found"}

    # ── Phase 3A: Config-driven per-agent model routing ──
    from deerflow.runtime.cer_authoring.writer_remediation.model_routing import (
        resolve_agent_model,
        is_model_allowed_for_agent,
        missing_provider_env,
        get_agent_provider_fallback_models,
        get_agent_task_type,
        record_resolution_trace,
        ROUTING_POLICY_V1,
    )
    routed_model = resolve_agent_model(agent_name, state)
    task_type = get_agent_task_type(agent_name)
    if not is_model_allowed_for_agent(agent_name, routed_model):
        return {
            **payload,
            "status": "BLOCKED",
            "error": f"Model '{routed_model}' is FORBIDDEN for agent '{agent_name}' (task_type={task_type}).",
        }
    config.model = routed_model
    payload["routed_model"] = routed_model
    payload["task_type"] = task_type
    missing_env = missing_provider_env(routed_model)
    fallback_models = [
        fallback
        for fallback in get_agent_provider_fallback_models(agent_name)
        if fallback != routed_model and is_model_allowed_for_agent(agent_name, fallback)
    ]
    configured_fallbacks = [fallback for fallback in fallback_models if not missing_provider_env(fallback)]
    # Determine routing source for audit trail
    env_key = f"CER_AUTHORING_MODEL_{agent_name.upper().replace('-', '_')}"
    if os.getenv(env_key):
        route_source = "env_var"
    elif (state.get("model_routing") or {}).get(agent_name):
        route_source = "state_config"
    else:
        route_source = "routing_policy_v1"
    payload["model_routing_source"] = route_source

    # Record resolution trace for MODEL_RESOLUTION_TRACE
    policy_model = ROUTING_POLICY_V1.get(agent_name, {}).get("default_model", "unknown")
    record_resolution_trace({
        "agent_name": agent_name,
        "task_type": task_type,
        "expected_model": policy_model,
        "actual_resolved_model": routed_model,
        "route_source": route_source,
        "fallback_used": False,
        "provider_status": "primary_missing_fallback_configured" if missing_env and configured_fallbacks else "missing_env" if missing_env else "configured",
        "missing_env": missing_env,
        "fallback_models": fallback_models,
        "configured_fallback_models": configured_fallbacks,
        "model_invocation_success": False,
    })
    if missing_env and not configured_fallbacks:
        return {
            **payload,
            "status": "BLOCKED_PROVIDER_UNAVAILABLE",
            "error": f"Model '{routed_model}' is configured for '{agent_name}', but required environment variable(s) are missing: {', '.join(missing_env)}.",
            "missing_env": missing_env,
            "fallback_models": fallback_models,
        }
    prompt = "\n".join(
        [
            task,
            "",
            "Return one compact JSON object only, with keys: decision, findings, rework_targets, confidence, rationale.",
            "Do not include step-by-step reasoning. Keep the response under 220 words.",
            "Use only the SharedAuthoringState summary below. Do not invent source evidence.",
            "Important: a controlled NB pre-review draft may pass with explicit evidence gaps when conclusions are downgraded. "
            "Block only if the draft contains unsupported strong conclusions, missing mandatory execution records, unverifiable pivotal evidence, or placeholders that would enter the final DOCX.",
            "Do not block solely for incomplete full-text extraction, missing RMF/PMS, non-demonstrated equivalence, or public-source unavailability when those items are explicit evidence gaps and conclusion strength is downgraded.",
            "```json",
            json.dumps(_state_summary(state, agent_name=agent_name), ensure_ascii=False, default=str)[:_summary_char_limit(agent_name)],
            "```",
        ]
    )

    attempted_models: list[dict[str, Any]] = []
    candidate_models = [routed_model, *fallback_models]
    last_error = ""
    for candidate_model in candidate_models:
        candidate_missing_env = missing_provider_env(candidate_model)
        if candidate_missing_env:
            attempted_models.append(
                {
                    "model_name": candidate_model,
                    "status": "SKIPPED_MISSING_ENV",
                    "missing_env": candidate_missing_env,
                }
            )
            last_error = f"Model '{candidate_model}' missing environment variable(s): {', '.join(candidate_missing_env)}"
            continue
        try:  # pragma: no cover - requires configured model provider
            config_for_model = _strict_runtime_config(replace(config, model=candidate_model), reviewer=reviewer)
            result = _execute_authoring_subagent(
                SubagentExecutor=SubagentExecutor,
                config=config_for_model,
                prompt=prompt,
                parent_model=_authoring_parent_model(state),
                sandbox_state=state.get("sandbox"),
                thread_data=state.get("thread_data"),
                thread_id=state.get("thread_id") or f"cer-authoring-{state.get('project_id') or 'run'}",
                trace_id=f"cer-authoring-{agent_name}",
            )
        except Exception as exc:  # pragma: no cover - requires configured model provider
            attempted_models.append(
                {
                    "model_name": candidate_model,
                    "status": "FAILED",
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
            last_error = f"{type(exc).__name__}: {exc}"
            if _is_provider_failure(last_error):
                continue
            return {
                **payload,
                "status": "FAILED",
                "error": last_error,
                "actual_model_name": candidate_model,
                "fallback_used": candidate_model != routed_model,
                "model_attempts": attempted_models,
            }
        status = result.status.value if hasattr(result.status, "value") else str(result.status)
        completed = result.status == SubagentStatus.COMPLETED
        attempted_models.append(
            {
                "model_name": candidate_model,
                "status": "COMPLETED" if completed else status,
                "error": result.error or "",
            }
        )
        last_error = result.error or result.result or f"subagent status={status}"
        if completed:
            # Guard: the error-handling middleware converts provider auth/quota/5xx
            # errors into AIMessage text instead of raising, so the subagent may
            # report COMPLETED with provider-failure content in result.result.
            if _is_provider_failure(last_error) and candidate_model != candidate_models[-1]:
                attempted_models[-1]["status"] = "FAILED_PROVIDER"
                attempted_models[-1]["error"] = last_error
                continue
            return {
                **payload,
                "status": "COMPLETED",
                "task_id": result.task_id,
                "result": result.result or "",
                "error": result.error or "",
                "actual_model_name": candidate_model,
                "fallback_used": candidate_model != routed_model,
                "model_attempts": attempted_models,
            }
        if candidate_model != candidate_models[-1] and _is_provider_failure(last_error):
            continue
        return {
            **payload,
            "status": status,
            "task_id": result.task_id,
            "result": result.result or "",
            "error": result.error or "",
            "actual_model_name": candidate_model,
            "fallback_used": candidate_model != routed_model,
            "model_attempts": attempted_models,
        }
    return {
        **payload,
        "status": "BLOCKED_PROVIDER_UNAVAILABLE",
        "error": last_error or "No configured model provider was available for this agent.",
        "fallback_models": fallback_models,
        "model_attempts": attempted_models,
    }


def _execute_authoring_subagent(
    *,
    SubagentExecutor: Any,
    config: Any,
    prompt: str,
    parent_model: str | None,
    sandbox_state: Any,
    thread_data: Any,
    thread_id: str,
    trace_id: str,
) -> Any:
        executor = SubagentExecutor(
            config=config,
            tools=[],
            parent_model=parent_model,
            sandbox_state=sandbox_state,
            thread_data=thread_data,
            thread_id=thread_id,
            trace_id=trace_id,
        )
        return _execute_with_outer_timeout(executor, prompt, config.timeout_seconds + 10)


def _is_provider_failure(error_text: str) -> bool:
    text = str(error_text or "").lower()
    provider_markers = (
        "401",
        "403",
        "unauthorized",
        "authentication",
        "auth",
        "api key",
        "x-api-key",
        "invalid key",
        "quota",
        "rate limit",
        "rate_limit",
        "too many requests",
        "unable to connect",
        "connection",
        "timeout",
        "timed out",
        "502",
        "503",
        "server-side",
    )
    return any(marker in text for marker in provider_markers)


def _authoring_parent_model(state: dict[str, Any]) -> str | None:
    explicit = str(state.get("model_name") or "").strip()
    if explicit:
        return explicit
    env_model = os.getenv("CER_AUTHORING_MODEL_NAME", "").strip()
    if env_model:
        return env_model
    if _env_enabled("CER_AUTHORING_STRICT_V7") or _env_enabled("CER_AUTHORING_ENABLE_LLM_AGENTS"):
        return "kimi-k2.6"
    return None


def _execute_with_outer_timeout(executor: Any, prompt: str, timeout_seconds: int) -> Any:
    pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="cer-authoring-agent-timeout")
    future = pool.submit(executor.execute, prompt)
    try:
        return future.result(timeout=timeout_seconds)
    except FuturesTimeoutError:
        future.cancel()
        pool.shutdown(wait=False, cancel_futures=True)
        raise TimeoutError(f"Subagent execution exceeded outer timeout of {timeout_seconds}s")
    finally:
        if future.done():
            pool.shutdown(wait=False, cancel_futures=True)


def reviewer_result_from_invocation(invocation: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    agent = invocation.get("agent")
    payload = extract_json_object(str(invocation.get("result") or ""))
    if invocation.get("mode") != "llm_subagent":
        return {"agent": agent, "status": "RECORDED", "scope": invocation.get("task", "")}, []
    if str(invocation.get("status", "")).upper() != "COMPLETED":
        return {"agent": agent, "status": "REWORK_REQUIRED", "findings": [invocation.get("error") or "subagent did not complete"]}, [
            {
                "finding_id": f"{agent}-EXECUTION",
                "agent": agent,
                "severity": "HIGH",
                "target_stage": agent,
                "finding": invocation.get("error") or "subagent did not complete",
            }
        ]
    decision = str((payload or {}).get("decision") or "PASS").upper()
    findings = (payload or {}).get("findings") or []
    pass_decisions = {
        "PASS",
        "APPROVED",
        "OK",
        "CONDITIONAL_PASS",
        "PASS_WITH_CONDITIONS",
        "PASS_WITH_GAP_DISCLOSURE",
        "ACCEPTABLE_WITH_GAPS",
    }
    status = "PASS" if decision in pass_decisions or decision.startswith("PASS") or decision.startswith("CONTROLLED_PASS") else "REWORK_REQUIRED"
    rework = []
    if status != "PASS":
        for idx, finding in enumerate(findings if isinstance(findings, list) else [findings], start=1):
            rework.append(
                {
                    "finding_id": f"{agent}-LLM-{idx:03d}",
                    "agent": agent,
                    "severity": str(finding.get("severity", "MEDIUM")).upper() if isinstance(finding, dict) else "MEDIUM",
                    "target_stage": _target_from_agent(agent),
                    "finding": finding.get("finding") if isinstance(finding, dict) else str(finding),
                    "evidence": finding,
                }
            )
    return {"agent": agent, "status": status, "findings": findings, "raw_decision": decision}, rework


def extract_json_object(text: str) -> dict[str, Any]:
    if not text:
        return {}
    fenced = re.search(r"```json\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
    candidates = [fenced.group(1)] if fenced else []
    brace = re.search(r"(\{.*\})", text, flags=re.DOTALL)
    if brace:
        candidates.append(brace.group(1))
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            continue
    return {}


def isolate_initial_authoring_state(state: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return a clean per-run initial state and an audit of dropped run state.

    This is the run-scoped boundary. A new authoring invocation may provide
    only input/configuration fields. Any generated state from a previous run is
    dropped before source intake, even if LangGraph/checkpoint transport passed
    it along on the same thread.
    """

    markers = _run_scope_markers(state)
    audit = _new_run_scope_audit(markers)
    clean: dict[str, Any] = {}
    for key, value in dict(state).items():
        if key in RUN_SCOPED_STATE_KEYS:
            if not _empty_value(value):
                _audit_drop(audit, key, value, "generated_state_not_allowed_at_run_boundary", markers)
            continue
        clean[key] = value
    clean["run_scope_audit"] = audit
    return clean, audit


def sanitize_run_scoped_state_for_agent_prompt(state: dict[str, Any]) -> dict[str, Any]:
    """Filter explicitly foreign rows before state is summarized for a subagent.

    The mid-run state itself is not rewritten here; this protects agent prompts
    from rows carrying another run's project/path markers.
    """

    markers = _run_scope_markers(state)
    audit = _new_run_scope_audit(markers)
    clean = dict(state)
    for key in RUN_SCOPED_STATE_KEYS:
        if key not in clean:
            continue
        clean[key] = _filter_foreign_rows(key, clean[key], markers, audit)
    prior = clean.get("run_scope_audit") if isinstance(clean.get("run_scope_audit"), dict) else {}
    clean["run_scope_audit"] = _merge_run_scope_audit(prior, audit)
    return clean


def _run_scope_markers(state: dict[str, Any]) -> dict[str, Any]:
    roots = _normalized_roots([state.get("input_root"), *(state.get("supplement_roots") or []), state.get("artifact_root")])
    project_id = str(state.get("project_id") or "").strip()
    return {
        "project_id": project_id,
        "input_root": str(state.get("input_root") or ""),
        "artifact_root": str(state.get("artifact_root") or ""),
        "allowed_roots": roots,
    }


def _normalized_roots(values: list[Any]) -> list[str]:
    roots: list[str] = []
    for value in values:
        if not value:
            continue
        try:
            path = str(Path(str(value)).expanduser().resolve())
        except Exception:
            path = str(value)
        if path and path not in roots:
            roots.append(path)
    return roots


def _new_run_scope_audit(markers: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_name": "cer_authoring_run_scope_audit",
        "project_id": markers.get("project_id"),
        "input_root": markers.get("input_root"),
        "artifact_root": markers.get("artifact_root"),
        "categories": [
            {"category": category, "key_count": len(keys), "dropped_key_count": 0, "dropped_row_count": 0}
            for category, keys in RUN_SCOPED_STATE_CATEGORIES.items()
        ],
        "dropped_keys": [],
        "dropped_rows": [],
        "decision": "PASS",
    }


def _category_for_key(key: str) -> str:
    for category, keys in RUN_SCOPED_STATE_CATEGORIES.items():
        if key in keys:
            return category
    return "unclassified"


def _audit_drop(audit: dict[str, Any], key: str, value: Any, reason: str, markers: dict[str, Any]) -> None:
    category = _category_for_key(key)
    count = _value_count(value)
    audit.setdefault("dropped_keys", []).append(
        {
            "key": key,
            "category": category,
            "reason": reason,
            "value_count": count,
            "foreign_markers": _foreign_markers(value, markers)[:8],
        }
    )
    _increment_category(audit, category, key_count=1, row_count=count)


def _audit_row_drop(audit: dict[str, Any], key: str, row: Any, reason: str, markers: dict[str, Any]) -> None:
    category = _category_for_key(key)
    audit.setdefault("dropped_rows", []).append(
        {
            "key": key,
            "category": category,
            "reason": reason,
            "foreign_markers": _foreign_markers(row, markers)[:8],
        }
    )
    _increment_category(audit, category, key_count=0, row_count=1)


def _increment_category(audit: dict[str, Any], category: str, *, key_count: int, row_count: int) -> None:
    for row in audit.get("categories", []):
        if row.get("category") == category:
            row["dropped_key_count"] = int(row.get("dropped_key_count") or 0) + key_count
            row["dropped_row_count"] = int(row.get("dropped_row_count") or 0) + row_count
            break


def _filter_foreign_rows(key: str, value: Any, markers: dict[str, Any], audit: dict[str, Any]) -> Any:
    if isinstance(value, list):
        kept = []
        for row in value:
            if _is_foreign_run_value(row, markers):
                _audit_row_drop(audit, key, row, "foreign_run_marker_removed_before_agent_prompt", markers)
            else:
                kept.append(row)
        return kept
    if isinstance(value, dict):
        if _is_foreign_run_value(value, markers):
            _audit_drop(audit, key, value, "foreign_run_marker_removed_before_agent_prompt", markers)
            return {}
        return value
    return value


def _is_foreign_run_value(value: Any, markers: dict[str, Any]) -> bool:
    current_project = str(markers.get("project_id") or "")
    if isinstance(value, dict):
        row_project = str(value.get("project_id") or value.get("run_project_id") or "")
        if current_project and row_project and row_project != current_project:
            return True
        for path_key in ("path", "source_path", "filepath", "artifact_path", "run_dir", "artifact_root"):
            if _path_is_foreign(value.get(path_key), markers):
                return True
    return False


def _path_is_foreign(value: Any, markers: dict[str, Any]) -> bool:
    if not value:
        return False
    text = str(value)
    if "://" in text:
        return False
    if not any(sep in text for sep in ("/", "\\")):
        return False
    try:
        path = str(Path(text).expanduser().resolve())
    except Exception:
        path = text
    allowed_roots = [str(root) for root in markers.get("allowed_roots") or [] if root]
    if not allowed_roots:
        return False
    return not any(path == root or path.startswith(root.rstrip("/") + "/") for root in allowed_roots)


def _foreign_markers(value: Any, markers: dict[str, Any]) -> list[str]:
    found: list[str] = []
    current_project = str(markers.get("project_id") or "")
    if isinstance(value, dict):
        row_project = str(value.get("project_id") or value.get("run_project_id") or "")
        if current_project and row_project and row_project != current_project:
            found.append(f"project_id={row_project}")
        for path_key in ("path", "source_path", "filepath", "artifact_path", "run_dir", "artifact_root"):
            if _path_is_foreign(value.get(path_key), markers):
                found.append(f"{path_key}={value.get(path_key)}")
    elif isinstance(value, list):
        for item in value[:20]:
            found.extend(_foreign_markers(item, markers))
    return list(dict.fromkeys(found))


def _value_count(value: Any) -> int:
    if isinstance(value, list):
        return len(value)
    if isinstance(value, dict):
        return 1 if value else 0
    return 1 if value is not None else 0


def _empty_value(value: Any) -> bool:
    if value is None:
        return True
    if value == "":
        return True
    if isinstance(value, (list, dict, tuple, set)) and len(value) == 0:
        return True
    return False


def _merge_run_scope_audit(existing: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    if not existing:
        return new
    merged = dict(existing)
    merged["dropped_keys"] = [*(existing.get("dropped_keys") or []), *(new.get("dropped_keys") or [])]
    merged["dropped_rows"] = [*(existing.get("dropped_rows") or []), *(new.get("dropped_rows") or [])]
    by_category = {row.get("category"): dict(row) for row in existing.get("categories") or []}
    for row in new.get("categories") or []:
        category = row.get("category")
        if category not in by_category:
            by_category[category] = dict(row)
            continue
        by_category[category]["dropped_key_count"] = int(by_category[category].get("dropped_key_count") or 0) + int(row.get("dropped_key_count") or 0)
        by_category[category]["dropped_row_count"] = int(by_category[category].get("dropped_row_count") or 0) + int(row.get("dropped_row_count") or 0)
    merged["categories"] = list(by_category.values())
    return merged


def _target_from_agent(agent: Any) -> str:
    name = str(agent or "")
    mapping = {
        "intake-profile-claim": "authoring-intake-profile-claim-agent",
        "methodology-sota": "authoring-methodology-sota-agent",
        "evidence-agent": "authoring-evidence-agent",
        "risk-equivalence-gspr": "authoring-risk-equivalence-gspr-agent",
        "cer-writer": "authoring-cer-writer-agent",
        "qa-review": "authoring-qa-review-agent",
        "methodology": "authoring-claim-pico-builder",
        "evidence": "authoring-evidence-appraiser",
        "sota": "authoring-sota-analyst",
        "equivalence": "authoring-equivalence-analyst",
        "vigilance": "authoring-vigilance-recall-analyst",
        "risk": "authoring-risk-gspr-mapper",
        "human-style": "authoring-cer-writer",
        "nb-precheck": "authoring-cer-writer",
        "final-gate": "authoring-cer-writer",
    }
    for needle, target in mapping.items():
        if needle in name:
            return target
    return name or "authoring-cer-writer"


def _state_summary(state: dict[str, Any], agent_name: str | None = None) -> dict[str, Any]:
    keys = [
        "project_id",
        "device_profile",
        "claim_ledger",
        "cep_pico_matrix",
        "search_run_registry",
        "evidence_registry",
        "endpoint_extraction",
        "sota_benchmark_matrix",
        "equivalence_matrix",
        "vigilance_recall_registry",
        "risk_trace_matrix",
        "gspr_coverage",
        "gap_pmcf_recommendations",
        "qa_gate_report",
        "human_cer_comparison_report",
        "template_logic_profile",
    ]
    summary: dict[str, Any] = {
        "project_id": state.get("project_id"),
        "artifact_root": state.get("artifact_root"),
        "counts": {
            "source_inventory": len(state.get("source_inventory") or []),
            "claim_ledger": len(state.get("claim_ledger") or []),
            "cep_pico_matrix": len(state.get("cep_pico_matrix") or []),
            "search_run_registry": len(state.get("search_run_registry") or []),
            "raw_literature_records": len(state.get("raw_literature_records") or []),
            "screening_disposition": len(state.get("screening_disposition") or []),
            "evidence_registry": len(state.get("evidence_registry") or []),
            "endpoint_extraction": len(state.get("endpoint_extraction") or []),
            "sota_benchmark_matrix": len(state.get("sota_benchmark_matrix") or []),
            "equivalence_matrix": len(state.get("equivalence_matrix") or []),
            "vigilance_recall_registry": len(state.get("vigilance_recall_registry") or []),
            "risk_trace_matrix": len(state.get("risk_trace_matrix") or []),
            "gspr_coverage": len(state.get("gspr_coverage") or []),
            "gap_pmcf_recommendations": len(state.get("gap_pmcf_recommendations") or []),
        },
        "strict_review_policy": (
            "Pass controlled drafts when gaps are explicit and conclusions are downgraded. "
            "Fail unsupported strong conclusions, missing executed search/vigilance records, unverified pivotal evidence, or unreproducible methodology."
        ),
        "controlled_draft_policy": (
            "Incomplete full-text extraction, missing RMF/PMS, source-unavailable public registries, and supportive-only evidence are advisory gaps "
            "when they are explicit in gap/PMCF recommendations and the CER conclusion is downgraded. They are blockers only if the draft claims final favourable benefit-risk, RMF closure, pivotal evidence, or absence of risk without support."
        ),
    }
    role_keys = _role_summary_keys(agent_name, keys)
    for key in role_keys:
        if key not in state:
            continue
        value = state.get(key)
        if isinstance(value, list):
            summary[key] = _sample_rows(value, limit=_summary_row_limit(agent_name))
        elif isinstance(value, dict):
            summary[key] = _sample_dict(value)
        else:
            summary[key] = value
    if state.get("mcp_call_log"):
        summary["mcp_call_log_tail"] = _sample_rows(state.get("mcp_call_log") or [], limit=8, tail=True)
    if state.get("screening_disposition"):
        summary["screening_disposition"] = _sample_rows(state.get("screening_disposition") or [], limit=6)
    if state.get("vigilance_relevance_screening"):
        summary["vigilance_relevance_screening"] = _sample_rows(state.get("vigilance_relevance_screening") or [], limit=6)
    if state.get("search_run_registry"):
        summary["search_screening_summary"] = [
            {
                "search_id": row.get("search_id"),
                "database": row.get("database"),
                "query": row.get("query"),
                "url": row.get("url"),
                "result_count": row.get("result_count"),
                "returned_count": row.get("returned_count"),
                "screened_count": row.get("screened_count"),
                "included_count": row.get("included_count"),
                "status": row.get("status"),
                "screening_status": row.get("screening_status"),
            }
            for row in state.get("search_run_registry") or []
        ]
    if state.get("vigilance_recall_registry"):
        summary["vigilance_execution_summary"] = [
            {
                "vigilance_id": row.get("vigilance_id"),
                "database": row.get("database"),
                "url": row.get("url"),
                "search_date": row.get("search_date"),
                "search_terms": row.get("search_terms"),
                "results": row.get("results"),
                "relevant_cases": row.get("relevant_cases"),
                "raw_status": row.get("raw_status"),
                "relevance_judgment": row.get("relevance_judgment"),
            }
            for row in state.get("vigilance_recall_registry") or []
        ]
    if state.get("cer_chapter_drafts"):
        summary["chapter_metrics"] = _chapter_metrics(state.get("cer_chapter_drafts") or {})
    if state.get("cer_chapter_drafts") and agent_name not in {"authoring-qa-review-agent", "cer-authoring-lead-agent"}:
        summary["cer_chapter_drafts"] = {k: str(v)[:1600] for k, v in (state.get("cer_chapter_drafts") or {}).items()}
    if agent_name == "authoring-cer-writer-agent":
        summary["pre_write_claim_coverage_instruction"] = (
            "Before drafting, compare the Claim Ledger with subject IFU claim-bearing full-text excerpts. "
            "If clinically material IFU claims are missing, return missing_claim_candidates and route rework to claim extraction; "
            "do not create unsupported claims in CER prose."
        )
        summary["subject_ifu_claim_audit_context"] = _subject_ifu_claim_audit_context(state)
    return summary


_IFU_CLAIM_HEADING_PATTERNS = [
    "intended use",
    "intended purpose",
    "indication",
    "clinical benefit",
    "performance",
    "safety",
    "contraindication",
    "warning",
    "precaution",
    "adverse event",
    "side effect",
    "residual risk",
    "pms",
    "pmcf",
    "compatibility",
    "accessor",
    "预期用途",
    "适用范围",
    "适应症",
    "临床获益",
    "临床受益",
    "性能",
    "安全",
    "禁忌",
    "警告",
    "注意事项",
    "不良事件",
    "副作用",
    "残余风险",
    "上市后",
    "兼容",
    "附件",
]


def _subject_ifu_claim_audit_context(state: dict[str, Any]) -> list[dict[str, Any]]:
    subject_ids = set((state.get("source_role_report") or {}).get("subject_ifu_source_ids") or [])
    rows: list[dict[str, Any]] = []
    for item in state.get("source_inventory") or []:
        if not isinstance(item, dict):
            continue
        source_id = str(item.get("source_id") or "")
        source_role = str(item.get("source_role") or "").lower()
        path = str(item.get("path") or item.get("source_path") or item.get("filename") or "")
        if "locked" in source_role or "locked" in path.lower():
            continue
        if item.get("excluded_from_device_profile") is True:
            continue
        is_subject_ifu = (
            source_id in subject_ids
            or source_role == "subject_device_ifu"
            or (str(item.get("document_type") or "").upper() == "IFU" and item.get("primary_for_authoring") is True)
        )
        if not is_subject_ifu:
            continue
        text = str(item.get("text") or item.get("text_excerpt") or "")
        rows.append(
            {
                "source_id": source_id,
                "filename": item.get("filename"),
                "document_type": item.get("document_type"),
                "source_role": item.get("source_role"),
                "text_length": item.get("text_length") or len(text),
                "claim_bearing_excerpt": _claim_bearing_ifu_excerpt(text),
            }
        )
    return rows[:4]


def _claim_bearing_ifu_excerpt(text: str, *, max_chars: int = 5200) -> str:
    normalized = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
    if not normalized.strip():
        return ""
    lines = [line.strip() for line in normalized.split("\n") if line.strip()]
    collected: list[str] = []
    lower_patterns = [pattern.lower() for pattern in _IFU_CLAIM_HEADING_PATTERNS]
    for idx, line in enumerate(lines):
        lower = line.lower()
        if any(pattern in lower for pattern in lower_patterns):
            collected.extend(lines[idx : min(len(lines), idx + 10)])
        if len("\n".join(collected)) >= max_chars:
            break
    excerpt = "\n".join(dict.fromkeys(collected))
    if not excerpt:
        excerpt = normalized[:max_chars]
    return excerpt[:max_chars]


def _role_summary_keys(agent_name: str | None, default_keys: list[str]) -> list[str]:
    name = agent_name or ""
    if name == "authoring-intake-profile-claim-agent":
        return ["project_id", "device_profile", "claim_ledger", "template_logic_profile"]
    if name == "authoring-methodology-sota-agent":
        return ["project_id", "device_profile", "claim_ledger", "cep_pico_matrix", "search_run_registry", "sota_benchmark_matrix", "template_logic_profile"]
    if name == "authoring-evidence-agent":
        return ["project_id", "device_profile", "cep_pico_matrix", "search_run_registry", "evidence_registry", "endpoint_extraction"]
    if name == "authoring-risk-equivalence-gspr-agent":
        return ["project_id", "device_profile", "claim_ledger", "equivalence_matrix", "vigilance_recall_registry", "risk_trace_matrix", "gspr_coverage"]
    if name == "authoring-cer-writer-agent":
        return ["project_id", "device_profile", "claim_ledger", "cep_pico_matrix", "evidence_registry", "endpoint_extraction", "sota_benchmark_matrix", "cross_evidence_synthesis_table", "risk_trace_matrix", "gspr_coverage", "gap_pmcf_recommendations", "template_logic_profile", "human_cer_comparison_report"]
    if name == "authoring-qa-review-agent":
        return ["project_id", "device_profile", "claim_ledger", "cep_pico_matrix", "search_run_registry", "evidence_registry", "endpoint_extraction", "sota_benchmark_matrix", "equivalence_matrix", "vigilance_recall_registry", "risk_trace_matrix", "gspr_coverage", "gap_pmcf_recommendations", "human_cer_comparison_report", "template_logic_profile"]
    if name == "cer-authoring-lead-agent":
        return ["project_id", "device_profile", "claim_ledger", "search_run_registry", "evidence_registry", "sota_benchmark_matrix", "vigilance_recall_registry", "risk_trace_matrix", "gspr_coverage", "gap_pmcf_recommendations", "qa_gate_report"]
    return default_keys


def _summary_char_limit(agent_name: str | None) -> int:
    if agent_name == "authoring-qa-review-agent":
        return 16_000
    if agent_name == "authoring-cer-writer-agent":
        return 18_000
    if agent_name == "cer-authoring-lead-agent":
        return 8_000
    if agent_name == "authoring-methodology-sota-agent":
        return 10_000
    return 12_000


def _summary_row_limit(agent_name: str | None) -> int:
    if agent_name in {"authoring-qa-review-agent", "authoring-methodology-sota-agent"}:
        return 5
    return 6


def _chapter_metrics(chapters: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for title, body in chapters.items():
        text = str(body or "")
        rows.append(
            {
                "section": title,
                "char_count": len(text),
                "table_count": text.count("\n|"),
                "has_evidence_id": "E-" in text or "Evidence" in text,
                "has_gap_language": "gap" in text.lower() or "partially support" in text.lower(),
                "has_4_7_analysis": "4.7" in text or "GSPR" in text,
            }
        )
    return rows


def _strict_runtime_config(config: Any, *, reviewer: bool) -> Any:
    if not _env_enabled("CER_AUTHORING_STRICT_V7"):
        return config
    timeout = int(os.getenv("CER_AUTHORING_STRICT_AGENT_TIMEOUT_SECONDS", "150" if reviewer else "120"))
    turns = int(os.getenv("CER_AUTHORING_STRICT_AGENT_MAX_TURNS", "14" if reviewer else "10"))
    return replace(config, max_turns=min(int(config.max_turns), turns), timeout_seconds=min(int(config.timeout_seconds), timeout))


def _sample_rows(rows: list[Any], *, limit: int = 8, tail: bool = False) -> list[Any]:
    selected = rows[-limit:] if tail else rows[:limit]
    return [_sample_dict(row) if isinstance(row, dict) else str(row)[:1200] for row in selected]


def _sample_dict(row: dict[str, Any]) -> dict[str, Any]:
    compact: dict[str, Any] = {}
    for key, value in row.items():
        if isinstance(value, str):
            compact[key] = value[:1200]
        elif isinstance(value, list):
            compact[key] = _sample_rows(value, limit=5)
        elif isinstance(value, dict):
            compact[key] = _sample_dict(value)
        else:
            compact[key] = value
    return compact


def _env_enabled(name: str) -> bool:
    return os.getenv(name, "").lower() in {"1", "true", "yes", "strict"}
