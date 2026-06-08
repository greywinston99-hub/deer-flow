"""Config-driven per-agent model routing for CER Authoring.

This module provides a centralized, versioned model routing policy that maps
each CER authoring agent/subagent to a model based on task intelligence type.
It does NOT modify agents.py, graph.py, or gates.py. Routing is applied as a
post-config override in agent_runtime.py.

CCD | 2026-05-15 | stable-1plus6 model assignment
"""

from __future__ import annotations

import os
import json
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from deerflow.config.app_config import get_app_config

# -- Default parent model (used when no per-agent override) ------------------

DEFAULT_PARENT_MODEL = "kimi-k2.6-api"

AGENT_NAME_ALIASES = {
    "cer-writer": "authoring-cer-writer-agent",
    "qa-review": "authoring-qa-review-agent",
    "methodology-sota": "authoring-methodology-sota-agent",
    "evidence": "authoring-evidence-agent",
    "intake-profile-claim": "authoring-intake-profile-claim-agent",
}

# -- Task-to-model routing policy -------------------------------------------

# This is the SINGLE SOURCE OF TRUTH for per-agent model assignment.
# All routing decisions are config-driven; model names are not hardcoded in
# agent_runtime.py, agents.py, graph.py, or gates.py.

MINIMAX_FORBIDDEN_MODELS = [
    "minimax-m2.7-highspeed",
    "minimax-M2.7-highspeed",
    "MiniMax-M2.7-highspeed",
]

ROUTING_POLICY_V1: dict[str, dict[str, Any]] = {
    "cer-authoring-lead-agent": {
        "role": "lead / controller agent",
        "task_type": "controller_triage",
        "default_model": "kimi-k2.6-api",
        "provider_fallback_models": ["kimi-k2.6-api", "deepseek-v4-pro"],
        "forbidden_models": MINIMAX_FORBIDDEN_MODELS,
        "rationale": "Stable 1+6 lead/controller routing only. It does not write CER prose or perform final clinical reasoning.",
    },
    "authoring-intake-profile-claim-agent": {
        "role": "intake / device profile / IFU structured extraction / structured claim-fact intake",
        "task_type": "extraction_structuring",
        "default_model": "kimi-k2.6-api",
        "provider_fallback_models": ["kimi-k2.6-api", "deepseek-v4-pro"],
        "forbidden_models": MINIMAX_FORBIDDEN_MODELS,
        "rationale": "Owns intake, source inventory, device profile, IFU extraction, claim ledger and structured facts. The direct Kimi API path is the fixed model for this structured chain.",
    },
    "authoring-methodology-sota-agent": {
        "role": "SOTA reasoning / methodology / endpoint benchmark reasoning",
        "task_type": "evidence_reasoning",
        "default_model": "deepseek-v4-pro",
        "provider_fallback_models": ["kimi-k2.6-api"],
        "forbidden_models": MINIMAX_FORBIDDEN_MODELS,
        "rationale": "Owns SOTA, methodology and benchmark reasoning. This is a clinical reasoning chain and is fixed to DeepSeek V4 Pro.",
    },
    "authoring-evidence-agent": {
        "role": "evidence appraisal / endpoint extraction / claim support reasoning",
        "task_type": "evidence_reasoning",
        "default_model": "deepseek-v4-pro",
        "provider_fallback_models": ["kimi-k2.6-api"],
        "forbidden_models": MINIMAX_FORBIDDEN_MODELS,
        "rationale": "Owns retrieval screening, citation verification, evidence appraisal, endpoint interpretation and claim support. Physical stable agent includes reasoning, so it is fixed to DeepSeek V4 Pro.",
    },
    "authoring-risk-equivalence-gspr-agent": {
        "role": "risk / equivalence / GSPR / benefit-risk / PMCF reasoning",
        "task_type": "risk_equivalence",
        "default_model": "deepseek-v4-pro",
        "provider_fallback_models": ["kimi-k2.6-api"],
        "structured_comparability_model": "kimi-k2.6-api",
        "clinical_reasoning_model": "deepseek-v4-pro",
        "forbidden_models": MINIMAX_FORBIDDEN_MODELS,
        "rationale": "The stable physical agent mixes equivalence, vigilance, risk/GSPR and clinical admissibility. Because clinical equivalence and benefit-risk/PMCF reasoning are in scope, the physical agent is fixed to DeepSeek V4 Pro. Structured comparability-only work may use Kimi API in a future split, but this stable 1+6 agent is not split here.",
    },
    "risk-equivalence-gspr": {
        "role": "risk / equivalence / GSPR structured extraction lane",
        "task_type": "risk_equivalence",
        "default_model": "kimi-k2.6-api",
        "provider_fallback_models": ["kimi-k2.6-api", "deepseek-v4-pro"],
        "forbidden_models": MINIMAX_FORBIDDEN_MODELS,
        "rationale": "Compatibility short-name lane used by routing tests and structured extraction dispatch; full physical authoring-risk-equivalence-gspr-agent remains DeepSeek for clinical reasoning.",
    },
    "authoring-cer-writer-agent": {
        "role": "CER writer agent",
        "task_type": "cer_writer",
        "default_model": "deepseek-v4-pro",
        "requires_ab_test": True,
        "ab_status": "pending",
        "candidate_a": "deepseek-v4-pro",
        "candidate_b": "kimi-k2.6",
        "provider_fallback_models": ["kimi-k2.6-api", "deepseek-v4-pro"],
        "forbidden_models": MINIMAX_FORBIDDEN_MODELS,
        "rationale": "CER body writing requires evidence fidelity and medical writing quality. Default: DeepSeek V4 Pro; Kimi API remains available as explicit fallback/AB candidate.",
    },
    "authoring-qa-review-agent": {
        "role": "QA / reviewer agent",
        "task_type": "qa_reviewer",
        "default_model": "deepseek-v4-pro",
        "requires_ab_test": True,
        "ab_status": "pending",
        "candidate_a": "deepseek-v4-pro",
        "candidate_b": "kimi-k2.6",
        "provider_fallback_models": ["kimi-k2.6-api"],
        "forbidden_models": MINIMAX_FORBIDDEN_MODELS,
        "rationale": "Integrated QA review requires detection sensitivity across methodology, evidence, SOTA, equivalence, risk/GSPR and NB precheck. Fixed to DeepSeek V4 Pro.",
    },
}

# -- Model usage boundaries (global) -----------------------------------------

MODEL_BOUNDARIES: dict[str, dict[str, Any]] = {
    "deepseek-v4-pro": {
        "label": "DeepSeek V4 Pro",
        "allowed_for": ["sota_reasoning", "evidence_reasoning", "risk_equivalence_reasoning", "benefit_risk_pmcf_reasoning", "cer_writer", "qa_reviewer", "controller_triage"],
        "forbidden_for": [],
        "notes": "Fixed for SOTA, evidence/claim support, clinical equivalence, BR/PMCF, Writer and QA in stable-1plus6.",
    },
    "kimi-k2.6": {
        "label": "Kimi API candidate",
        "allowed_for": ["controller_triage", "extraction_structuring", "evidence_reasoning", "risk_equivalence", "cer_writer", "qa_reviewer"],
        "forbidden_for": [],
        "notes": "Kimi API may be used as a provider fallback or explicit override when DeepSeek providers fail.",
    },
    "kimi-k2.6-api": {
        "label": "Kimi API candidate",
        "allowed_for": ["controller_triage", "extraction_structuring", "evidence_reasoning", "risk_equivalence", "cer_writer", "qa_reviewer"],
        "forbidden_for": [],
        "notes": "Kimi API may be used as a provider fallback or explicit override when DeepSeek providers fail.",
    },
    "kimi-api": {
        "label": "Kimi API legacy alias",
        "allowed_for": ["cer_writer", "qa_reviewer"],
        "forbidden_for": [],
        "notes": "Legacy env/state override alias retained for compatibility with older routing fixtures.",
    },
    "minimax-m2.7-highspeed": {
        "label": "MiniMax M2.7 Highspeed",
        "allowed_for": [],
        "forbidden_for": ["controller_triage", "extraction_structuring", "sota_reasoning", "evidence_reasoning", "risk_equivalence_reasoning", "benefit_risk_pmcf_reasoning", "cer_writer", "qa_reviewer"],
        "notes": "Not enabled in this stable-1plus6 routing. Forbidden for Writer, QA, evidence reasoning, BR/PMCF and final claim support.",
        "requires_timeout": True,
        "requires_fallback": True,
    },
    "minimax-M2.7-highspeed": {
        "label": "MiniMax M2.7 Highspeed",
        "allowed_for": [],
        "forbidden_for": ["controller_triage", "extraction_structuring", "sota_reasoning", "evidence_reasoning", "risk_equivalence", "risk_equivalence_reasoning", "benefit_risk_pmcf_reasoning", "cer_writer", "qa_reviewer"],
        "notes": "Case-preserved compatibility alias. Not enabled in stable-1plus6 routing.",
        "requires_timeout": True,
        "requires_fallback": True,
    },
}

MODEL_REQUIRED_ENV: dict[str, tuple[str, ...]] = {
    "kimi-k2.6": ("KIMI_API_KEY",),
    "kimi-k2.6-api": ("KIMI_API_KEY",),
    "kimi-api": ("KIMI_API_KEY",),
    "deepseek-v4-pro": ("DEEPSEEK_API_KEY",),
}

_PROVIDER_ENV_LOADED = False

# -- Routing resolver --------------------------------------------------------

# Priority for resolving model name per agent:
# 1. CER_AUTHORING_MODEL_<AGENT> env var (e.g., CER_AUTHORING_MODEL_CER_WRITER)
# 2. state["model_routing"] dict (per-agent overrides from runtime config)
# 3. ROUTING_POLICY_V1 default_model
# 4. DEFAULT_PARENT_MODEL (global fallback)


def resolve_agent_model(
    agent_name: str,
    state: dict[str, Any] | None = None,
) -> str:
    """Resolve the model name for a specific CER authoring agent.

    Priority: env var > state config > routing policy > global default.
    """
    canonical_agent_name = _canonical_agent_name(agent_name)
    # 1. Check per-agent env var
    env_key = _agent_env_key(agent_name)
    canonical_env_key = _agent_env_key(canonical_agent_name)
    env_val = os.getenv(env_key, "").strip()
    if not env_val and canonical_env_key != env_key:
        env_val = os.getenv(canonical_env_key, "").strip()
    if env_val:
        _validate_model_allowed(canonical_agent_name, env_val)
        return env_val

    # 2. Check state-level routing config
    if state:
        routing_config = state.get("model_routing") or {}
        model = ""
        if isinstance(routing_config, dict):
            model = str(routing_config.get(agent_name) or routing_config.get(canonical_agent_name) or "").strip()
            if model:
                _validate_model_allowed(canonical_agent_name, model)
                return model

    # 3. Use routing policy default
    policy = ROUTING_POLICY_V1.get(canonical_agent_name)
    if policy:
        return policy["default_model"]

    # 4. Global fallback
    return os.getenv("CER_AUTHORING_MODEL_NAME", "").strip() or DEFAULT_PARENT_MODEL


def resolve_all_agent_models(
    state: dict[str, Any] | None = None,
) -> dict[str, str]:
    """Resolve models for all known CER authoring agents. Returns {agent_name: model_name}."""
    result: dict[str, str] = {}
    for agent_name in ROUTING_POLICY_V1:
        result[agent_name] = resolve_agent_model(agent_name, state)
    return result


def is_model_allowed_for_agent(agent_name: str, model_name: str) -> bool:
    """Check whether a model is allowed for a specific agent's task type."""
    policy = ROUTING_POLICY_V1.get(_canonical_agent_name(agent_name))
    if not policy:
        return True  # Unknown agent — allow, will be logged
    if not _model_supports_native_tool_calls(model_name):
        return False
    forbidden = policy.get("forbidden_models") or []
    if model_name in forbidden:
        return False
    # Also check global boundaries
    boundaries = MODEL_BOUNDARIES.get(model_name)
    if boundaries:
        task_type = policy.get("task_type", "")
        if task_type in (boundaries.get("forbidden_for") or []):
            return False
    return True


def get_agent_task_type(agent_name: str) -> str:
    """Return the task type for an agent."""
    policy = ROUTING_POLICY_V1.get(_canonical_agent_name(agent_name))
    return policy.get("task_type", "unknown") if policy else "unknown"


def get_agent_routing_info(agent_name: str) -> dict[str, Any] | None:
    """Return the full routing policy entry for an agent."""
    return ROUTING_POLICY_V1.get(_canonical_agent_name(agent_name))


def get_agent_provider_fallback_models(agent_name: str) -> list[str]:
    """Return configured provider fallback models for an agent."""

    policy = get_agent_routing_info(agent_name) or {}
    return list(policy.get("provider_fallback_models") or [])


def get_model_boundaries(model_name: str) -> dict[str, Any] | None:
    """Return the usage boundary rules for a model."""
    return MODEL_BOUNDARIES.get(model_name)


def missing_provider_env(model_name: str) -> list[str]:
    """Return missing environment variables required by the routed model."""

    _ensure_provider_env_loaded()
    required = MODEL_REQUIRED_ENV.get(model_name, ())
    return [name for name in required if not os.getenv(name)]


def is_model_provider_configured(model_name: str) -> bool:
    """Whether the routed model has the local credentials needed to instantiate."""

    return not missing_provider_env(model_name)


def build_provider_preflight(state: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build a run-start provider readiness report for all routed agents."""

    agent_models = resolve_all_agent_models(state)
    checks = []
    missing: dict[str, list[str]] = {}
    for agent_name, model_name in agent_models.items():
        missing_env = missing_provider_env(model_name)
        fallback_models = [
            fallback
            for fallback in get_agent_provider_fallback_models(agent_name)
            if is_model_allowed_for_agent(agent_name, fallback)
        ]
        configured_fallbacks = [
            fallback for fallback in fallback_models if not missing_provider_env(fallback)
        ]
        if missing_env:
            if configured_fallbacks:
                provider_status = "primary_missing_fallback_configured"
            else:
                missing[agent_name] = missing_env
                provider_status = "missing_env"
        else:
            provider_status = "configured"
        checks.append(
            {
                "agent_name": agent_name,
                "model_name": model_name,
                "provider_status": provider_status,
                "missing_env": missing_env,
                "fallback_models": fallback_models,
                "configured_fallback_models": configured_fallbacks,
            }
        )
    return {
        "schema_name": "cer_authoring_model_provider_preflight",
        "status": "BLOCKED_PROVIDER_UNAVAILABLE" if missing else "PASS",
        "missing_provider_count": len(missing),
        "missing_providers": missing,
        "checks": checks,
    }


def is_deterministic_stage(agent_name: str) -> bool:
    """Check if an agent/stage is deterministic (should not have a model)."""
    return _canonical_agent_name(agent_name) not in ROUTING_POLICY_V1


# ── Internal helpers ────────────────────────────────────────────────────────


def _agent_env_key(agent_name: str) -> str:
    """Convert agent name to env var key. e.g., 'cer-writer' → 'CER_AUTHORING_MODEL_CER_WRITER'."""
    safe = agent_name.upper().replace("-", "_").replace(".", "_")
    return f"CER_AUTHORING_MODEL_{safe}"


def _ensure_provider_env_loaded() -> None:
    """Load DeerFlow provider credentials before model-route preflight checks.

    Some CER authoring entrypoints check provider readiness before AppConfig is
    instantiated. Loading the same deterministic dotenv locations here prevents
    false "provider unavailable" reports and avoids falling back to unrelated
    Anthropic/OpenAI credentials.
    """

    global _PROVIDER_ENV_LOADED
    if _PROVIDER_ENV_LOADED:
        return
    if os.getenv("DEERFLOW_SKIP_PROVIDER_DOTENV", "").strip() == "1":
        _PROVIDER_ENV_LOADED = True
        return
    backend_dir = Path(__file__).resolve().parents[6]
    repo_root = backend_dir.parent
    for path in (Path.cwd() / ".env", backend_dir / ".env", repo_root / ".env"):
        if path.exists():
            load_dotenv(path, override=False)
    _PROVIDER_ENV_LOADED = True


def _canonical_agent_name(agent_name: str) -> str:
    return AGENT_NAME_ALIASES.get(agent_name, agent_name)


def _model_supports_native_tool_calls(model_name: str) -> bool:
    """Return false only when the configured model explicitly disables tool calls."""

    try:
        app_config = get_app_config()
        model_config = app_config.get_model_config(model_name)
    except Exception:
        return True
    if model_config is None:
        return True
    return bool(model_config.supports_tool_calls)


def _validate_model_allowed(agent_name: str, model_name: str) -> None:
    """Raise ValueError if model is forbidden for this agent."""
    canonical_agent_name = _canonical_agent_name(agent_name)
    if not is_model_allowed_for_agent(canonical_agent_name, model_name):
        policy = ROUTING_POLICY_V1.get(canonical_agent_name, {})
        raise ValueError(
            f"Model '{model_name}' is FORBIDDEN for agent '{agent_name}' "
            f"(task_type={policy.get('task_type', 'unknown')}). "
            f"Forbidden models: {policy.get('forbidden_models', [])}"
        )


# ── A/B test config skeleton ────────────────────────────────────────────────


def build_ab_test_config(agent_name: str) -> dict[str, Any] | None:
    """Build A/B test configuration for an agent, or None if A/B not applicable."""
    canonical_agent_name = _canonical_agent_name(agent_name)
    policy = ROUTING_POLICY_V1.get(canonical_agent_name)
    if not policy:
        return None
    if not policy.get("requires_ab_test"):
        return None

    candidates = {}
    if policy.get("candidate_a"):
        candidates["candidate_a"] = {
            "model": policy["candidate_a"],
            "env_var": _agent_env_key(agent_name),
        }
    if policy.get("candidate_b"):
        candidates["candidate_b"] = {
            "model": policy["candidate_b"],
            "env_var": _agent_env_key(agent_name),
        }
    if policy.get("current_baseline"):
        candidates["current_baseline"] = {
            "model": policy["current_baseline"],
            "env_var": _agent_env_key(agent_name),
        }

    return {
        "agent_name": agent_name,
        "task_type": policy.get("task_type"),
        "ab_status": policy.get("ab_status", "not_required"),
        "candidates": candidates,
        "fixed_config": {
            "prompts": "PROMPT_PACK_V1",
            "templates": "CER_TEMPLATE_PACK_V1 (frozen Phase 2C)",
            "gates": "Gates 1-5 active",
        },
        "scoring_dimensions": _ab_scoring_dimensions(agent_name),
    }


def _ab_scoring_dimensions(agent_name: str) -> list[dict[str, Any]]:
    """Return A/B scoring dimensions for an agent's task type."""
    task_type = get_agent_task_type(agent_name)
    if task_type == "cer_writer":
        return [
            {"dimension": "domain_consistency", "weight": 0.20, "metric": "Gate 1 status + forbidden term count"},
            {"dimension": "evidence_consistency", "weight": 0.20, "metric": "Gate 3 status + forbidden phrase count"},
            {"dimension": "ifu_source_usage", "weight": 0.15, "metric": "Gate 2 status + placeholder count"},
            {"dimension": "internal_language_leakage", "weight": 0.10, "metric": "Gate 4 status + banned string count"},
            {"dimension": "section_completeness", "weight": 0.10, "metric": "Gate 5 structural dimension"},
            {"dimension": "professional_expression", "weight": 0.10, "metric": "Human reviewer score 1-5"},
            {"dimension": "gate_pass_rate", "weight": 0.10, "metric": "All 5 gates pass/fail"},
            {"dimension": "repeatability", "weight": 0.05, "metric": "Two-run output consistency"},
        ]
    elif task_type == "qa_reviewer":
        return [
            {"dimension": "false_pass_rate", "weight": 0.35, "metric": "QA score on contaminated fixtures — must be 0/FAIL"},
            {"dimension": "false_fail_rate", "weight": 0.35, "metric": "QA score on clean fixture — must be PASS"},
            {"dimension": "finding_specificity", "weight": 0.15, "metric": "Specific contamination type identified vs generic fail"},
            {"dimension": "dimension_coverage", "weight": 0.15, "metric": "All 4 QA dimensions independently scored"},
        ]
    else:
        return [
            {"dimension": "task_accuracy", "weight": 0.50, "metric": "Output correctness vs baseline"},
            {"dimension": "gate_compatibility", "weight": 0.50, "metric": "Downstream gate pass rate"},
        ]


# ── Model Resolution Trace ──────────────────────────────────────────────────

# In-memory trace collector. Populated during agent invocation in agent_runtime.py.
# Written to disk as MODEL_RESOLUTION_TRACE.json by write_resolution_trace().
_TRACE_COLLECTOR: list[dict[str, Any]] = []


def record_resolution_trace(entry: dict[str, Any]) -> None:
    """Record a single agent's model resolution for the current run."""
    _TRACE_COLLECTOR.append(entry)


def clear_resolution_trace() -> None:
    """Clear the in-memory trace collector (call at start of each run)."""
    _TRACE_COLLECTOR.clear()


def get_resolution_trace() -> list[dict[str, Any]]:
    """Get the collected model resolution trace for the current run."""
    return list(_TRACE_COLLECTOR)


def build_resolution_trace_report(
    run_id: str = "",
    project: str = "",
    global_model_env: str = "",
    per_agent_overrides: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Build the MODEL_RESOLUTION_TRACE report from collected agent traces."""
    from datetime import datetime, timezone

    agents = []
    for entry in _TRACE_COLLECTOR:
        agents.append({
            "agent_name": entry.get("agent_name", ""),
            "task_type": entry.get("task_type", ""),
            "expected_model": entry.get("expected_model", ""),
            "actual_resolved_model": entry.get("actual_resolved_model", ""),
            "route_source": entry.get("route_source", ""),
            "fallback_used": entry.get("fallback_used", False),
            "provider_status": entry.get("provider_status", "unknown"),
            "model_invocation_success": entry.get("model_invocation_success", False),
        })

    return {
        "schema": "model_resolution_trace_v1",
        "run_id": run_id,
        "project": project,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "global_model_env": global_model_env,
        "per_agent_overrides": per_agent_overrides or _collect_active_overrides(),
        "agents": agents,
        "agent_count": len(agents),
        "all_resolved_correctly": all(
            a.get("actual_resolved_model") == a.get("expected_model")
            for a in agents
        ),
        "any_fallback_used": any(a.get("fallback_used") for a in agents),
    }


def write_resolution_trace_json(
    artifact_root: str,
    run_id: str = "",
    project: str = "",
    global_model_env: str = "",
) -> str:
    """Write MODEL_RESOLUTION_TRACE.json to the artifact directory.

    Returns the path to the written file.
    """
    import os as _os
    report = build_resolution_trace_report(
        run_id=run_id,
        project=project,
        global_model_env=global_model_env,
    )
    path = _os.path.join(str(artifact_root), "MODEL_RESOLUTION_TRACE.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    return path


def _collect_active_overrides() -> dict[str, str]:
    """Collect currently active per-agent model env var overrides."""
    overrides: dict[str, str] = {}
    for agent_name in ROUTING_POLICY_V1:
        env_key = _agent_env_key(agent_name)
        val = os.getenv(env_key, "").strip()
        if val:
            overrides[env_key] = val
    return overrides
