"""Read-only API for CER/RMF Review Agent visibility.

Mounts under ``/api/cer-review/agents`` and serves agent metadata (from the
subagent registry), prompt previews (from on-disk prompt files), and runtime
evidence (aggregated from Package 2 evidence first, then thread traces).
"""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from deerflow.subagents.registry import get_subagent_config, list_subagents

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["cer-review-agents"])

# ── helpers ──────────────────────────────────────────────────────────────────

_REVIEW_AGENT_PREFIXES = ("cer-", "rmf-")
_LINKAGE_SUFFIX = "linkage"
_INTAKE_SUFFIXES = ("-intake-document-analyst", "-intake-compliance-reviewer")

_PROJECT_ROOT = Path(__file__).resolve().parents[4]
_PROJECT_ROOT = _PROJECT_ROOT.parent if _PROJECT_ROOT.name == "backend" else _PROJECT_ROOT

_PROMPT_SEARCH_DIRS = [
    _PROJECT_ROOT / "prompts" / "cer" / "canonical",
    _PROJECT_ROOT / "prompts",
]

_PACKAGE_2_EVIDENCE_DIR = _PROJECT_ROOT / "artifacts" / "cer_rmf_review_engine" / "evidence"


def _derive_agent_category(name: str) -> str:
    """Return the agent category for UI grouping."""
    if _LINKAGE_SUFFIX in name:
        return "Linkage"
    if name.startswith("cer-"):
        if name.endswith(_INTAKE_SUFFIXES):
            return "CER Intake"
        return "CER Review"
    if name.startswith("rmf-"):
        return "RMF Review"
    return "General"


def _derive_agent_domain(name: str) -> str:
    """Return the top-level domain for filter grouping."""
    if _LINKAGE_SUFFIX in name:
        return "Linkage"
    if name.startswith("cer-"):
        return "CER"
    if name.startswith("rmf-"):
        return "RMF"
    return "General"


def _find_prompt_path(name: str) -> tuple[str | None, bool]:
    """Scan known prompt directories for a .md file matching the agent name.

    Returns ``(path, is_explicit)`` — ``is_explicit`` is ``True`` when the
    file was actually found on disk, ``False`` when the path is derived by
    convention.
    """
    candidates = [
        f"{name.replace('-', '_')}.md",
        f"{name}.md",
    ]
    for search_dir in _PROMPT_SEARCH_DIRS:
        if not search_dir.exists():
            continue
        for cand in candidates:
            candidate_path = search_dir / cand
            if candidate_path.exists():
                try:
                    return (str(candidate_path.relative_to(_PROJECT_ROOT)), True)
                except ValueError:
                    return (str(candidate_path), True)
    return (None, False)


def _compute_prompt_hash(prompt_path: str | None, is_explicit: bool) -> str | None:
    """Compute SHA-256 of the actual prompt file content.  Returns ``None``
    when the file cannot be read (derived path or missing file)."""
    if not prompt_path or not is_explicit:
        return None
    full_path = _PROJECT_ROOT / prompt_path
    try:
        content = full_path.read_text(encoding="utf-8")
        return hashlib.sha256(content.encode("utf-8")).hexdigest()
    except Exception:
        return None


def _get_system_prompt(config: Any) -> str:
    """Extract the system_prompt field from a SubagentConfig."""
    return getattr(config, "system_prompt", "") or ""


def _build_agent_info(config: Any) -> dict[str, Any]:
    """Convert a SubagentConfig into an AgentInfo dict."""
    name = config.name
    system_prompt = _get_system_prompt(config)
    prompt_path, prompt_explicit = _find_prompt_path(name)
    default_path = prompt_path or _derive_default_prompt_path(name)
    prompt_loaded = bool(system_prompt.strip()) if system_prompt else False
    prompt_hash = _compute_prompt_hash(prompt_path, prompt_explicit) if prompt_path else None

    return {
        "name": name,
        "domain": _derive_agent_domain(name),
        "category": _derive_agent_category(name),
        "description": getattr(config, "description", ""),
        "role": _derive_agent_category(name),
        "model": getattr(config, "model", "inherit"),
        "tools": list(getattr(config, "tools", []) or []),
        "disallowed_tools": list(getattr(config, "disallowed_tools", []) or []),
        "max_turns": getattr(config, "max_turns", 50),
        "timeout_seconds": getattr(config, "timeout_seconds", 900),
        "prompt_loaded": prompt_loaded,
        "prompt_path": default_path,
        "prompt_path_source": "explicit" if prompt_explicit else "derived",
        "prompt_hash": prompt_hash,
        "prompt_preview": system_prompt[:1500] if system_prompt else "",
        "registered": True,
    }


def _derive_default_prompt_path(name: str) -> str:
    if name.startswith("cer-"):
        return f"prompts/cer/canonical/{name.replace('-', '_')}.md"
    if name.startswith("rmf-"):
        return f"prompts/{name.replace('-', '_')}.md"
    return f"prompts/{name}.md"


def _is_review_agent(name: str) -> bool:
    return name.startswith(_REVIEW_AGENT_PREFIXES) or _LINKAGE_SUFFIX in name


# ── Pydantic models ──────────────────────────────────────────────────────────

from pydantic import BaseModel, Field  # noqa: E402


class AgentInfo(BaseModel):
    name: str
    domain: str
    category: str = ""
    description: str
    role: str
    model: str
    tools: list[str]
    disallowed_tools: list[str]
    max_turns: int
    timeout_seconds: int
    prompt_loaded: bool
    prompt_path: str
    prompt_path_source: str = "derived"
    prompt_hash: str | None = None
    prompt_preview: str
    registered: bool


class AgentDetailResponse(AgentInfo):
    full_system_prompt: str = ""


class AgentsListResponse(BaseModel):
    agents: list[AgentInfo]
    total: int = 0
    domains: dict[str, int] = Field(default_factory=dict)


class AgentRuntimeEvidence(BaseModel):
    agent_name: str
    last_invoked_at: str | None = None
    last_status: str | None = None
    last_duration_ms: int | None = None
    last_schema_valid: bool | None = None
    last_artifact_path: str | None = None
    total_invocations: int = 0
    total_failures: int = 0
    trace_source: str | None = None


class RuntimeEvidenceResponse(BaseModel):
    agents: list[AgentRuntimeEvidence]
    total_traces_found: int = 0
    trace_sources: list[str] = Field(default_factory=list)
    evidence_source: str = "no_evidence"


# ── evidence helpers ─────────────────────────────────────────────────────────


def _aggregate_from_trace_file(
    trace_file: Path,
    evidence_map: dict[str, dict[str, Any]],
) -> None:
    """Read a ``agent_invocation_trace.jsonl`` and merge into ``evidence_map``."""
    try:
        lines = trace_file.read_text(encoding="utf-8").strip().splitlines()
        for line in lines[-100:]:
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            agent_name = entry.get("agent_name", "")
            if not agent_name:
                continue

            if agent_name not in evidence_map:
                evidence_map[agent_name] = {
                    "agent_name": agent_name,
                    "last_invoked_at": None,
                    "last_status": None,
                    "last_duration_ms": None,
                    "last_schema_valid": None,
                    "last_artifact_path": None,
                    "total_invocations": 0,
                    "total_failures": 0,
                    "trace_source": None,
                }

            rec = evidence_map[agent_name]
            rec["total_invocations"] += 1
            if entry.get("status") != "completed":
                rec["total_failures"] += 1

            started = entry.get("started_at", "")
            if started and (rec["last_invoked_at"] is None or started > rec["last_invoked_at"]):
                rec["last_invoked_at"] = started
                rec["last_status"] = entry.get("status")
                rec["last_duration_ms"] = entry.get("duration_ms")
                sv = entry.get("schema_validation")
                if isinstance(sv, dict):
                    rec["last_schema_valid"] = sv.get("valid", None)
                rec["last_artifact_path"] = entry.get("output_artifact")
                rec["trace_source"] = "agent_invocation_trace.jsonl"
    except Exception:
        logger.warning("Failed to read trace file: %s", trace_file, exc_info=True)


def _aggregate_from_ledger(
    ledger_file: Path,
    evidence_map: dict[str, dict[str, Any]],
) -> None:
    """Read an ``agent_usage_ledger.json`` and merge into ``evidence_map``."""
    try:
        ledger = json.loads(ledger_file.read_text(encoding="utf-8"))
        for entry in ledger.get("agents_invoked", []):
            agent_name = entry.get("name", "")
            if not agent_name:
                continue
            if agent_name not in evidence_map:
                evidence_map[agent_name] = {
                    "agent_name": agent_name,
                    "last_invoked_at": None,
                    "last_status": None,
                    "last_duration_ms": None,
                    "last_schema_valid": None,
                    "last_artifact_path": None,
                    "total_invocations": 0,
                    "total_failures": 0,
                    "trace_source": None,
                }
            rec = evidence_map[agent_name]
            rec["total_invocations"] = max(rec["total_invocations"], entry.get("calls", 0))
            rec["total_failures"] = max(rec["total_failures"], entry.get("failures", 0))
            rec["trace_source"] = "agent_usage_ledger.json"
    except Exception:
        logger.warning("Failed to read ledger file: %s", ledger_file, exc_info=True)


def _collect_from_dir(
    scan_dir: Path,
    evidence_map: dict[str, dict[str, Any]],
    trace_sources: list[str],
) -> int:
    """Scan a directory tree for trace/ledger files.  Returns count of dirs found."""
    if not scan_dir.exists():
        return 0
    found = 0
    for child in scan_dir.iterdir():
        if not child.is_dir():
            continue
        trace_file = child / "00_manifest" / "agent_invocation_trace.jsonl"
        if trace_file.exists():
            trace_sources.append(
                str(trace_file.relative_to(_PROJECT_ROOT)
                    if _PROJECT_ROOT in trace_file.parents
                    else trace_file)
            )
            _aggregate_from_trace_file(trace_file, evidence_map)
            found += 1

        ledger_file = child / "00_manifest" / "agent_usage_ledger.json"
        if ledger_file.exists():
            _aggregate_from_ledger(ledger_file, evidence_map)
    return found


# ── endpoints ────────────────────────────────────────────────────────────────


@router.get(
    "/cer-review/agents",
    response_model=AgentsListResponse,
    summary="List CER/RMF Review Agents",
)
async def list_cer_review_agents(
    domain: str | None = Query(default=None, description="Filter by domain: CER, RMF, Linkage, or omit for all"),
) -> AgentsListResponse:
    all_configs = list_subagents()
    agents: list[AgentInfo] = []
    domain_counts: dict[str, int] = {}

    for config in all_configs:
        name = config.name
        if not _is_review_agent(name):
            continue
        info = _build_agent_info(config)
        agent = AgentInfo(**info)
        if domain and agent.domain != domain:
            continue
        agents.append(agent)
        domain_counts[agent.domain] = domain_counts.get(agent.domain, 0) + 1

    return AgentsListResponse(agents=agents, total=len(agents), domains=domain_counts)


@router.get(
    "/cer-review/agents/runtime-evidence",
    response_model=RuntimeEvidenceResponse,
    summary="Get Aggregated Runtime Evidence",
)
async def get_review_agents_runtime_evidence() -> RuntimeEvidenceResponse:
    """Aggregate runtime evidence with priority:

    1. Package 2 persistent evidence (``artifacts/cer_rmf_review_engine/evidence/``)
    2. Fallback: ``.deer-flow/threads/`` runtime traces
    """
    evidence_map: dict[str, dict[str, Any]] = {}
    trace_sources: list[str] = []
    evidence_source = "no_evidence"

    # ── Priority 1: Package 2 persistent evidence ──────────────────────────
    p2_found = _collect_from_dir(_PACKAGE_2_EVIDENCE_DIR, evidence_map, trace_sources)
    if p2_found > 0 and evidence_map:
        evidence_source = "persistent_evidence"

    # ── Priority 2: thread runtime traces (fallback only) ──────────────────
    if evidence_source == "no_evidence":
        threads_dir = _PROJECT_ROOT / "backend" / ".deer-flow" / "threads"
        thread_found = 0
        if threads_dir.exists():
            for child in threads_dir.iterdir():
                if not child.is_dir():
                    continue
                if child.name.startswith("cer-") or child.name.startswith("rmf-review-") or child.name.startswith("rmf-project-"):
                    trace_file = child / "00_manifest" / "agent_invocation_trace.jsonl"
                    if trace_file.exists():
                        trace_sources.append(
                            str(trace_file.relative_to(_PROJECT_ROOT)
                                if _PROJECT_ROOT in trace_file.parents
                                else trace_file)
                        )
                        _aggregate_from_trace_file(trace_file, evidence_map)
                        thread_found += 1
                    ledger_file = child / "00_manifest" / "agent_usage_ledger.json"
                    if ledger_file.exists():
                        _aggregate_from_ledger(ledger_file, evidence_map)
        if thread_found > 0 and evidence_map:
            evidence_source = "thread_runtime"

    agents = [AgentRuntimeEvidence(**v) for v in evidence_map.values()]
    return RuntimeEvidenceResponse(
        agents=agents,
        total_traces_found=len(trace_sources),
        trace_sources=trace_sources,
        evidence_source=evidence_source,
    )


@router.get(
    "/cer-review/agents/{agent_name}",
    response_model=AgentDetailResponse,
    summary="Get CER/RMF Review Agent Detail",
)
async def get_cer_review_agent(agent_name: str) -> AgentDetailResponse:
    if not _is_review_agent(agent_name):
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' is not a CER/RMF review agent")

    config = get_subagent_config(agent_name)
    if config is None:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found in registry")

    info = _build_agent_info(config)
    system_prompt = _get_system_prompt(config)
    info["full_system_prompt"] = system_prompt
    info["prompt_preview"] = system_prompt[:2000] if system_prompt else ""

    return AgentDetailResponse(**info)
