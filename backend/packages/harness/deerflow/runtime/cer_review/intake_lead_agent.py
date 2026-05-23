"""CER Intake Lead Agent — LangGraph Graph for Agent Teams execution.

Orchestrates the 15-state CER intake pipeline using DeerFlow harness:
- Deterministic stages run as pure Python graph nodes
- LLM stages delegate to SubagentExecutor (cer-intake-document-analyst,
  cer-intake-compliance-reviewer)
- State persists via IntakeStateMachine (governance) + LangGraph checkpointer (runtime)
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from pathlib import Path
from typing import Annotated, Any

from langchain.agents import AgentState
from langchain_core.messages import HumanMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, StateGraph

from deerflow.agents.thread_state import ThreadState
from deerflow.models import create_chat_model
from deerflow.runtime.cer_review.intake_state_machine import IntakeState, IntakeStateMachine
from deerflow.sandbox.tools import bash_tool, ls_tool, read_file_tool, write_file_tool
from deerflow.subagents.executor import SubagentExecutor
from deerflow.subagents.registry import get_subagent_config

logger = logging.getLogger(__name__)

# Resolve repo root for prompt files
REPO_ROOT = Path(__file__).resolve().parents[6]

# Sandbox tools available to subagents
SUBAGENT_TOOLS = [bash_tool, ls_tool, read_file_tool, write_file_tool]


# ── State Schema ───────────────────────────────────────────────────────────────


def add_stage_results(existing: list[dict] | None, new: list[dict] | None) -> list[dict]:
    if existing is None:
        return new or []
    if new is None:
        return existing
    return existing + new


class IntakeAgentState(ThreadState):
    """Extended ThreadState for CER Intake graph execution."""

    intake_state_machine: Annotated[IntakeStateMachine | None, lambda x, y: y if y is not None else x]
    project_id: str | None
    artifact_root: str | None
    input_root: str | None
    project_profile_path: str | None
    intake_session_id: str | None
    current_stage: str | None
    stage_results: Annotated[list[dict], add_stage_results]


# ── Prompt Builders ────────────────────────────────────────────────────────────


def _load_skill_prompt(skill_file: str) -> str:
    """Load skill prompt from DeerFlow skills/public/cer-intake/ first, then fall back to prompts/cer/intake/."""
    # Derive skill name from skill_file (e.g. "pdf_readability_agent.md" -> "cer-intake-pdf-readability")
    base = skill_file.replace("_agent.md", "").replace("_writer.md", "").replace("_", "-")
    skill_name = f"cer-intake-{base}"

    # Priority 1: DeerFlow skills/public/ system
    skills_dir = REPO_ROOT / "skills" / "public" / "cer-intake" / skill_name
    skill_path = skills_dir / "SKILL.md"
    if skill_path.exists():
        content = skill_path.read_text(encoding="utf-8")
        # Strip YAML frontmatter (---\n...\n---\n)
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                return parts[2].strip()
        return content

    # Priority 2: Legacy prompts/cer/intake/ fallback
    legacy_path = REPO_ROOT / "prompts" / "cer" / "intake" / skill_file
    if legacy_path.exists():
        return legacy_path.read_text(encoding="utf-8")

    logger.warning("Skill prompt not found: %s (skill=%s, legacy=%s)", skill_file, skill_path, legacy_path)
    return ""


def _build_subagent_task(
    stage: str,
    skill_file: str,
    context: dict[str, Any],
) -> str:
    """Build the task prompt for a subagent stage."""
    prompt_text = _load_skill_prompt(skill_file)
    context_md = json.dumps(context, indent=2, ensure_ascii=False)
    return (
        f"{prompt_text}\n\n"
        f"## Project Context\n\n"
        f"```json\n{context_md}\n```\n\n"
        f"Please complete the '{stage}' stage and return structured JSON output."
    )


def _subagent_for_stage(stage: str) -> str:
    mapping = {
        "pdf_check": "cer-intake-document-analyst",
        "type_detection": "cer-intake-document-analyst",
        "classification": "cer-intake-document-analyst",
        "completeness": "cer-intake-compliance-reviewer",
        "citations": "cer-intake-compliance-reviewer",
        "human_gate_packet": "cer-intake-compliance-reviewer",
    }
    return mapping.get(stage, "general-purpose")


# ── Deterministic Nodes ────────────────────────────────────────────────────────


async def node_init(state: IntakeAgentState, config: RunnableConfig) -> dict[str, Any]:
    """Initialize or resume intake state machine."""
    project_id = state.get("project_id")
    artifact_root = Path(state["artifact_root"])

    sm = IntakeStateMachine.from_artifacts(
        project_id=project_id,
        artifact_root=artifact_root,
        intake_session_id=state.get("intake_session_id"),
    )
    sm.append_log({
        "event": "runner_initialized",
        "project_id": project_id,
        "workflow_version": "1.0",
        "agent_teams": True,
    })
    return {
        "intake_state_machine": sm,
        "project_id": project_id,
        "intake_session_id": sm.intake_session_id,
        "current_stage": sm.current_state.value,
        "stage_results": [],
    }


async def node_file_inventory(state: IntakeAgentState, config: RunnableConfig) -> dict[str, Any]:
    sm = state["intake_state_machine"]
    artifact_root = Path(state["artifact_root"])
    input_root = Path(state["input_root"])
    intake_dir = artifact_root / "intake"
    intake_dir.mkdir(parents=True, exist_ok=True)

    from deerflow.runtime.cer_review.intake_file_ops import build_file_inventory

    inventory = build_file_inventory(
        input_root=input_root,
        project_id=state["project_id"],
        intake_session_id=sm.intake_session_id,
    )

    (intake_dir / "file_inventory.json").write_text(
        json.dumps(inventory, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    sm.record_artifact("file_inventory", "intake/file_inventory.json")
    sm.transition(IntakeState.INVENTORY_CREATED, reason="file inventory complete")
    sm.append_log({"event": "stage_complete", "stage": "file_inventory", "total_files": inventory["total_files"]})

    return {
        "intake_state_machine": sm,
        "current_stage": "inventory_created",
        "stage_results": state.get("stage_results", []) + [{"stage": "file_inventory", "status": "success"}],
    }


async def node_dedupe(state: IntakeAgentState, config: RunnableConfig) -> dict[str, Any]:
    sm = state["intake_state_machine"]
    artifact_root = Path(state["artifact_root"])
    intake_dir = artifact_root / "intake"

    from deerflow.runtime.cer_review.intake_file_ops import compute_checksum_manifest, enumerate_files

    files = enumerate_files(Path(state["input_root"]))
    checksums = compute_checksum_manifest(files, Path(state["input_root"]))

    (intake_dir / "checksum_manifest.json").write_text(
        json.dumps(checksums, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # Simple exact dedupe by sha256
    seen = {}
    dupes = []
    for f in checksums["files"]:
        sha = f["sha256"]
        if sha in seen:
            dupes.append({"sha256": sha, "files": [seen[sha], f["relative_path"]]})
        else:
            seen[sha] = f["relative_path"]

    dedupe_report = {
        "schema_name": "cer_intake_dedupe_report",
        "schema_version": "v1",
        "duplicate_groups": len(dupes),
        "duplicates": dupes,
    }
    (intake_dir / "dedupe_report.json").write_text(
        json.dumps(dedupe_report, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    sm.record_artifact("checksum_manifest", "intake/checksum_manifest.json")
    sm.record_artifact("dedupe_report", "intake/dedupe_report.json")
    sm.transition(IntakeState.DEDUPE_COMPLETED, reason="dedupe complete")
    sm.append_log({"event": "stage_complete", "stage": "dedupe", "duplicate_groups": len(dupes)})

    return {
        "intake_state_machine": sm,
        "current_stage": "dedupe_completed",
        "stage_results": state.get("stage_results", []) + [{"stage": "dedupe", "status": "success"}],
    }


async def node_parse(state: IntakeAgentState, config: RunnableConfig) -> dict[str, Any]:
    sm = state["intake_state_machine"]
    artifact_root = Path(state["artifact_root"])
    input_root = Path(state["input_root"])
    intake_dir = artifact_root / "intake"
    text_extracted_dir = intake_dir / "text_extracted"

    from deerflow.runtime.cer_review.intake_file_ops import enumerate_files
    from deerflow.runtime.cer_review.intake_text_extractor import extract_text_batch

    files = enumerate_files(input_root)
    result = extract_text_batch(file_paths=files, output_dir=text_extracted_dir)

    (intake_dir / "document_text_index.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    sm.record_artifact("document_text_index", "intake/document_text_index.json")
    sm.transition(IntakeState.PARSE_COMPLETED, reason="text extraction complete")
    sm.append_log({
        "event": "stage_complete",
        "stage": "parse",
        "extracted": result.get("total_files_extracted", 0),
        "failed": result.get("total_files_failed", 0),
    })

    return {
        "intake_state_machine": sm,
        "current_stage": "parse_completed",
        "stage_results": state.get("stage_results", []) + [{"stage": "parse", "status": "success"}],
    }


# ── LLM Nodes (Subagent Delegation) ────────────────────────────────────────────


async def _run_subagent_stage(
    state: IntakeAgentState,
    config: RunnableConfig,
    stage: str,
    skill_file: str,
    output_filename: str,
    artifact_key: str,
    to_state: IntakeState,
) -> dict[str, Any]:
    """Generic LLM stage runner via SubagentExecutor."""
    sm = state["intake_state_machine"]
    artifact_root = Path(state["artifact_root"])
    intake_dir = artifact_root / "intake"

    sm.append_log({"event": "stage_start", "stage": stage})

    # Build context for subagent
    context = {
        "project_id": state["project_id"],
        "intake_session_id": sm.intake_session_id,
        "artifact_root": str(artifact_root),
        "input_root": state["input_root"],
        "stage": stage,
    }

    # Load previous stage outputs into context
    for key, path in sm.artifacts.items():
        full_path = artifact_root / path
        if full_path.exists() and full_path.suffix == ".json":
            try:
                context[key] = json.loads(full_path.read_text(encoding="utf-8"))
            except Exception:
                pass

    task_prompt = _build_subagent_task(stage, skill_file, context)
    subagent_type = _subagent_for_stage(stage)

    # Resolve model from config
    model_name = None
    if config.get("metadata", {}).get("model_name"):
        model_name = config["metadata"]["model_name"]

    # Build SubagentExecutor
    cfg = get_subagent_config(subagent_type)
    executor = SubagentExecutor(
        config=cfg,
        tools=list(SUBAGENT_TOOLS),
        parent_model=model_name,
        sandbox_state=state.get("sandbox"),
        thread_data=state.get("thread_data"),
        thread_id=config.get("configurable", {}).get("thread_id"),
        trace_id=f"{sm.intake_session_id}-{stage}",
    )

    logger.info("[intake-%s] Dispatching subagent %s for stage %s", sm.intake_session_id, subagent_type, stage)
    result = await executor._aexecute(task_prompt)

    # Write output artifact
    output_data = {"_meta": {"stage": stage, "subagent_type": subagent_type, "status": result.status.value}, "data": {}}
    if result.result:
        try:
            parsed = json.loads(result.result)
            if isinstance(parsed, dict):
                output_data["data"] = parsed
            else:
                output_data["data"] = {"raw_result": result.result}
        except json.JSONDecodeError:
            output_data["data"] = {"raw_result": result.result}
    if result.error:
        output_data["_meta"]["error"] = result.error

    (intake_dir / output_filename).write_text(
        json.dumps(output_data, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    sm.record_artifact(artifact_key, f"intake/{output_filename}")
    sm.transition(to_state, reason=f"{stage} complete via subagent {subagent_type}")
    sm.append_log({
        "event": "subagent_invocation",
        "stage": stage,
        "subagent_type": subagent_type,
        "status": result.status.value,
        "error": result.error,
        "output_artifact": output_filename,
    })

    return {
        "intake_state_machine": sm,
        "current_stage": to_state.value,
        "stage_results": state.get("stage_results", []) + [{"stage": stage, "status": result.status.value}],
    }


async def node_pdf_check(state: IntakeAgentState, config: RunnableConfig) -> dict[str, Any]:
    return await _run_subagent_stage(
        state, config,
        stage="pdf_check",
        skill_file="pdf_readability_agent.md",
        output_filename="pdf_readability_report.json",
        artifact_key="pdf_readability_report",
        to_state=IntakeState.PDF_CHECKED,
    )


async def node_type_detection(state: IntakeAgentState, config: RunnableConfig) -> dict[str, Any]:
    return await _run_subagent_stage(
        state, config,
        stage="type_detection",
        skill_file="document_type_detection_agent.md",
        output_filename="type_detection_output.json",
        artifact_key="classification_candidates",
        to_state=IntakeState.TYPE_DETECTION_DONE,
    )


async def node_classification(state: IntakeAgentState, config: RunnableConfig) -> dict[str, Any]:
    return await _run_subagent_stage(
        state, config,
        stage="classification",
        skill_file="evidence_classification_agent.md",
        output_filename="classification_output.json",
        artifact_key="evidence_classification_final",
        to_state=IntakeState.CLASSIFICATION_COMPLETED,
    )


async def node_completeness(state: IntakeAgentState, config: RunnableConfig) -> dict[str, Any]:
    return await _run_subagent_stage(
        state, config,
        stage="completeness",
        skill_file="evidence_completeness_agent.md",
        output_filename="completeness_output.json",
        artifact_key="evidence_completeness_report",
        to_state=IntakeState.COMPLETENESS_EVALUATED,
    )


async def node_citations(state: IntakeAgentState, config: RunnableConfig) -> dict[str, Any]:
    return await _run_subagent_stage(
        state, config,
        stage="citations",
        skill_file="citation_locator_agent.md",
        output_filename="citations_output.json",
        artifact_key="citation_trace_report",
        to_state=IntakeState.CITATIONS_TRACED,
    )


async def node_human_gate_packet(state: IntakeAgentState, config: RunnableConfig) -> dict[str, Any]:
    return await _run_subagent_stage(
        state, config,
        stage="human_gate_packet",
        skill_file="human_gate_packet_writer.md",
        output_filename="human_gate_packet_output.json",
        artifact_key="classification_review_packet",
        to_state=IntakeState.HUMAN_GATE_PENDING,
    )


# ── Human Gate & Post-Gate Nodes ───────────────────────────────────────────────


async def node_wait_human_gate(state: IntakeAgentState, config: RunnableConfig) -> dict[str, Any]:
    """Check for human gate decision file."""
    sm = state["intake_state_machine"]
    artifact_root = Path(state["artifact_root"])
    intake_dir = artifact_root / "intake"
    decision_file = intake_dir / "human_intake_gate_decision.json"

    sm.append_log({"event": "stage_start", "stage": "wait_human_gate"})

    if decision_file.exists():
        try:
            decision = json.loads(decision_file.read_text(encoding="utf-8"))
            verdict = decision.get("verdict", "").upper()
            if verdict in ("APPROVED", "APPROVED_WITH_CONDITIONS"):
                sm.transition(IntakeState.HUMAN_GATE_APPROVED, reason=f"human gate {verdict.lower()}")
                sm.append_log({"event": "human_gate_approved", "verdict": verdict})
                return {
                    "intake_state_machine": sm,
                    "current_stage": "human_gate_approved",
                    "stage_results": state.get("stage_results", []) + [{"stage": "wait_human_gate", "status": "approved"}],
                }
            else:
                sm.transition(IntakeState.HUMAN_GATE_REJECTED, reason=f"human gate {verdict.lower()}")
                sm.append_log({"event": "human_gate_rejected", "verdict": verdict})
                return {
                    "intake_state_machine": sm,
                    "current_stage": "human_gate_rejected",
                    "stage_results": state.get("stage_results", []) + [{"stage": "wait_human_gate", "status": "rejected"}],
                }
        except Exception as e:
            logger.warning("Failed to parse human gate decision: %s", e)

    # Decision not yet submitted — stay in pending
    sm.append_log({"event": "human_gate_pending", "reason": "decision file not found"})
    # Sleep briefly to avoid tight spin when called in a loop
    await asyncio.sleep(1)
    return {
        "intake_state_machine": sm,
        "current_stage": "human_gate_pending",
        "stage_results": state.get("stage_results", []) + [{"stage": "wait_human_gate", "status": "pending"}],
    }


async def node_pack_lock(state: IntakeAgentState, config: RunnableConfig) -> dict[str, Any]:
    sm = state["intake_state_machine"]
    artifact_root = Path(state["artifact_root"])
    intake_dir = artifact_root / "intake"
    locked_dir = intake_dir / "locked"
    locked_dir.mkdir(parents=True, exist_ok=True)

    from deerflow.runtime.cer_review.intake_file_ops import compute_sha256

    # Build locked pack manifest
    input_root = Path(state["input_root"])
    files = []
    for f in input_root.rglob("*"):
        if f.is_file() and not f.name.startswith("."):
            rel = str(f.relative_to(input_root))
            files.append({
                "relative_path": rel,
                "sha256": compute_sha256(f),
                "ep": rel.split("/")[0] if "/" in rel else "",
                "size_bytes": f.stat().st_size,
            })

    manifest = {
        "schema_name": "cer_intake_locked_pack_manifest",
        "schema_version": "v1",
        "project_id": state["project_id"],
        "intake_session_id": sm.intake_session_id,
        "total_files": len(files),
        "files": files,
    }
    (locked_dir / "locked_evidence_pack_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    sm.record_artifact("locked_pack_manifest", "intake/locked/locked_evidence_pack_manifest.json")
    sm.transition(IntakeState.EVIDENCE_PACK_LOCKED, reason="pack locked")
    sm.append_log({"event": "stage_complete", "stage": "pack_lock", "total_files": len(files)})

    return {
        "intake_state_machine": sm,
        "current_stage": "evidence_pack_locked",
        "stage_results": state.get("stage_results", []) + [{"stage": "pack_lock", "status": "success"}],
    }


async def node_qa(state: IntakeAgentState, config: RunnableConfig) -> dict[str, Any]:
    sm = state["intake_state_machine"]
    artifact_root = Path(state["artifact_root"])
    locked_dir = artifact_root / "intake" / "locked"
    manifest_file = locked_dir / "locked_evidence_pack_manifest.json"

    verified = False
    if manifest_file.exists():
        try:
            manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
            from deerflow.runtime.cer_review.intake_file_ops import compute_sha256
            input_root = Path(state["input_root"])
            all_match = True
            for f in manifest.get("files", []):
                actual = input_root / f["relative_path"]
                if actual.exists() and compute_sha256(actual) == f["sha256"]:
                    continue
                all_match = False
                break
            verified = all_match
        except Exception as e:
            logger.warning("QA checksum verification failed: %s", e)

    if verified:
        sm.transition(IntakeState.READY_FOR_CER_REVIEW, reason="QA passed")
    else:
        sm.transition(IntakeState.BLOCKED, reason="QA failed — checksum mismatch")

    sm.append_log({"event": "stage_complete", "stage": "qa", "verified": verified})

    return {
        "intake_state_machine": sm,
        "current_stage": sm.current_state.value,
        "stage_results": state.get("stage_results", []) + [{"stage": "qa", "status": "passed" if verified else "failed"}],
    }


async def node_end(state: IntakeAgentState, config: RunnableConfig) -> dict[str, Any]:
    sm = state["intake_state_machine"]
    sm.append_log({"event": "pipeline_complete", "final_state": sm.current_state.value})
    logger.info("CER Intake pipeline complete for %s: %s", state["project_id"], sm.current_state.value)
    return {
        "current_stage": sm.current_state.value,
        "stage_results": state.get("stage_results", []) + [{"stage": "end", "status": "complete"}],
    }


# ── Conditional Routing ────────────────────────────────────────────────────────


def route_from_init(state: IntakeAgentState) -> str:
    """Route from init based on current state machine state."""
    sm = state.get("intake_state_machine")
    if sm is None:
        return "file_inventory"
    current = sm.current_state.value
    routing = {
        "raw_uploaded": "file_inventory",
        "inventory_created": "dedupe",
        "dedupe_completed": "parse",
        "parse_completed": "pdf_check",
        "pdf_checked": "type_detection",
        "type_detection_done": "classification",
        "classification_completed": "completeness",
        "completeness_evaluated": "citations",
        "citations_traced": "human_gate_packet",
        "human_gate_pending": "wait_human_gate",
        "human_gate_approved": "pack_lock",
        "human_gate_rejected": "end",
        "evidence_pack_locked": "qa",
        "ready_for_cer_review": "end",
        "blocked": "end",
    }
    return routing.get(current, "file_inventory")


def route_from_wait_human_gate(state: IntakeAgentState) -> str:
    sm = state.get("intake_state_machine")
    if sm is None:
        return "end"
    current = sm.current_state.value
    if current == "human_gate_approved":
        return "pack_lock"
    elif current == "human_gate_rejected":
        return "end"
    # Still pending — loop back to wait (will be throttled by sleep)
    return "wait_human_gate"


# ── Graph Builder ──────────────────────────────────────────────────────────────


def build_intake_graph(config=None) -> StateGraph:
    """Build and compile the CER Intake Lead Agent graph.

    Args:
        config: RunnableConfig passed by run_agent (optional, may be None).
    """
    builder = StateGraph(IntakeAgentState)

    # Register nodes
    builder.add_node("init", node_init)
    builder.add_node("file_inventory", node_file_inventory)
    builder.add_node("dedupe", node_dedupe)
    builder.add_node("parse", node_parse)
    builder.add_node("pdf_check", node_pdf_check)
    builder.add_node("type_detection", node_type_detection)
    builder.add_node("classification", node_classification)
    builder.add_node("completeness", node_completeness)
    builder.add_node("citations", node_citations)
    builder.add_node("human_gate_packet", node_human_gate_packet)
    builder.add_node("wait_human_gate", node_wait_human_gate)
    builder.add_node("pack_lock", node_pack_lock)
    builder.add_node("qa", node_qa)
    builder.add_node("end", node_end)

    # Set entry point
    builder.set_entry_point("init")

    # Conditional from init based on existing state
    builder.add_conditional_edges("init", route_from_init)

    # Linear chain after init
    builder.add_edge("file_inventory", "dedupe")
    builder.add_edge("dedupe", "parse")
    builder.add_edge("parse", "pdf_check")
    builder.add_edge("pdf_check", "type_detection")
    builder.add_edge("type_detection", "classification")
    builder.add_edge("classification", "completeness")
    builder.add_edge("completeness", "citations")
    builder.add_edge("citations", "human_gate_packet")
    builder.add_edge("human_gate_packet", "wait_human_gate")

    # Conditional from wait_human_gate
    builder.add_conditional_edges("wait_human_gate", route_from_wait_human_gate)

    builder.add_edge("pack_lock", "qa")
    builder.add_edge("qa", "end")

    return builder.compile()
