"""CER Review Assist Lead Agent — 3-Stage LangGraph Graph.

Phase 2: 3-stage pipeline (evidence-curator -> gap-specialist -> logic-qa).
Constructs SubagentConfig directly from SKILL.md — bypasses BUILTIN_SUBAGENTS.
Integrates ReviewAssistStateMachine for pipeline governance.
Zero existing file modification required (beyond langgraph.json registration).
"""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Any, Literal

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, StateGraph

from deerflow.agents.thread_state import ThreadState
from deerflow.runtime.cer_review.review_assist_state_machine import (
    ReviewAssistState as SMState,
    ReviewAssistStateMachine,
)
from deerflow.sandbox.tools import bash_tool, ls_tool, read_file_tool, write_file_tool
from deerflow.subagents.cer_review_model_policy import CER_REVIEW_DEFAULT_MODEL
from deerflow.subagents.config import SubagentConfig
from deerflow.subagents.executor import SubagentExecutor

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[6]

SUBAGENT_TOOLS = [bash_tool, ls_tool, read_file_tool, write_file_tool]

# Skill directory names (relative to skills/public/cer-review-assist/)
SKILL_EVIDENCE_CURATOR = "cer-review-assist-evidence-curator"
SKILL_GAP_SPECIALIST = "cer-review-assist-gap-specialist"
SKILL_LOGIC_QA = "cer-review-assist-logic-qa"


# ── State Schema ────────────────────────────────────────────────────────────────


class ReviewAssistState(ThreadState):
    """Extended ThreadState for CER Review Assist 3-stage graph execution."""

    project_id: str | None
    artifact_root: str | None
    input_root: str | None
    review_session_id: str | None
    current_stage: str | None
    stage_result: Annotated[dict | None, lambda x, y: y if y is not None else x]
    flavor_profile: str
    stage_results: Annotated[list[dict], lambda x, y: (x or []) + ([y] if y else [])]
    state_machine: Annotated[ReviewAssistStateMachine | None, lambda x, y: y if y is not None else x]
    status: str | None
    inline_file_context: str
    stage_data: Annotated[dict, lambda x, y: {**x, **y}]  # D2: accumulate compact stage outputs for inline handoff


# ── Skill Loading ───────────────────────────────────────────────────────────────


def _load_review_skill(skill_dir_name: str) -> str:
    """Load Review Assist skill prompt body from SKILL.md (strips YAML frontmatter)."""
    skills_dir = REPO_ROOT / "skills" / "public" / "cer-review-assist" / skill_dir_name
    skill_path = skills_dir / "SKILL.md"
    if not skill_path.exists():
        raise FileNotFoundError(f"Skill not found: {skill_path}")

    content = skill_path.read_text(encoding="utf-8")
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            return parts[2].strip()
    return content


# ── SubagentConfig Construction (Path A: Direct, no BUILTIN_SUBAGENTS) ──────────


def _build_subagent_config(skill_name: str, skill_prompt: str, model_override: str | None = None, tools_override: list[str] | None = None) -> SubagentConfig:
    """Build SubagentConfig directly from skill metadata.

    Bypasses BUILTIN_SUBAGENTS and get_subagent_config() entirely.

    model_override: reserved for explicit operator-requested overrides; default is the CER review model policy.
    tools_override: if provided, use these tools instead of the default ["read_file", "ls", "write_file"].
    Used for gap-specialist which has all content inline — restricting to ["write_file"]
    prevents wasted turns on unnecessary read_file/ls tool calls.
    """
    return SubagentConfig(
        name=skill_name,
        description=f"Review Assist: {skill_name} — advisory-only CER review",
        system_prompt=skill_prompt,
        tools=tools_override if tools_override is not None else ["read_file", "ls", "write_file"],
        disallowed_tools=["task", "ask_clarification", "present_files"],
        model=model_override if model_override else CER_REVIEW_DEFAULT_MODEL,
        max_turns=200,
        timeout_seconds=1800,
    )


# ── Context Builder ─────────────────────────────────────────────────────────────


def _build_context(state: ReviewAssistState) -> dict[str, Any]:
    """Build project context dict from current state."""
    return {
        "project_id": state.get("project_id", ""),
        "review_session_id": state.get("review_session_id", ""),
        "artifact_root": state.get("artifact_root", ""),
        "input_root": state.get("input_root", ""),
        "flavor_profile": state.get("flavor_profile", "BALANCED"),
        "current_stage": state.get("current_stage", ""),
    }


def _truncate_prompt_value(value: Any, max_chars: int = 700) -> Any:
    if isinstance(value, str) and len(value) > max_chars:
        return value[:max_chars] + " ...[truncated for Logic QA prompt handoff]"
    if isinstance(value, list):
        return [_truncate_prompt_value(item, max_chars=max_chars) for item in value]
    if isinstance(value, dict):
        return {key: _truncate_prompt_value(item, max_chars=max_chars) for key, item in value.items()}
    return value


def _compact_stage_data_for_prompt(target_stage: SMState, stage_data: dict | None) -> dict | None:
    """Compact inline prior-stage handoff for prompt-only use.

    This never mutates persisted artifacts. Logic QA needs calibrated finding
    metadata, not full source text excerpts; preserving the complete upstream
    files on disk while reducing inline payload keeps medium/large families out
    of the model's slow tool/prose failure mode.
    """
    if not stage_data or target_stage != SMState.SEVERITY_SYNTHESIS_DONE:
        return stage_data

    compact = json.loads(json.dumps(stage_data))
    inventory = compact.get(SMState.EVIDENCE_INVENTORY_DONE.value)
    if isinstance(inventory, dict):
        for entry in inventory.get("source_inventory", []) or []:
            if isinstance(entry, dict):
                entry.pop("excerpt_preview", None)
                entry.pop("rationale", None)
                for key, value in list(entry.items()):
                    entry[key] = _truncate_prompt_value(value, max_chars=500)

    findings_doc = compact.get(SMState.GAP_ANALYSIS_DONE.value)
    if isinstance(findings_doc, dict):
        atomic_observations = findings_doc.get("atomic_observations")
        if isinstance(atomic_observations, list):
            findings_doc["atomic_observation_summary"] = {
                "total_atomic_observations": len(atomic_observations),
                "sample_refs": [
                    {
                        "id": item.get("id"),
                        "source_file": item.get("source_file"),
                        "section": item.get("section"),
                        "confidence": item.get("confidence"),
                    }
                    for item in atomic_observations[:25]
                    if isinstance(item, dict)
                ],
                "note": "Full atomic_observations are persisted in atomic_observations.json; Logic QA should use clusters/candidates inline and artifact paths for provenance.",
            }
            findings_doc.pop("atomic_observations", None)
        for cluster in findings_doc.get("finding_clusters", []) or []:
            if not isinstance(cluster, dict):
                continue
            for key, value in list(cluster.items()):
                cluster[key] = _truncate_prompt_value(value, max_chars=700)
        for finding in findings_doc.get("candidate_findings", []) or []:
            if not isinstance(finding, dict):
                continue
            for key, value in list(finding.items()):
                if key != "evidence":
                    finding[key] = _truncate_prompt_value(value, max_chars=700)
            for evidence in finding.get("evidence", []) or []:
                if isinstance(evidence, dict):
                    for key, value in list(evidence.items()):
                        evidence[key] = _truncate_prompt_value(value, max_chars=500)
        for key in ("summary", "pipeline_limitations"):
            if key in findings_doc:
                findings_doc[key] = _truncate_prompt_value(findings_doc[key], max_chars=700)

    return compact


def _build_task_prompt(
    skill_prompt: str,
    context: dict[str, Any],
    stage_description: str,
    upstream_artifacts: dict[str, str] | None = None,
    inline_file_context: str = "",
    inline_override: str | None = None,
    stage_data: dict | None = None,
) -> str:
    """Assemble the full task prompt with skill body, project context, and upstream refs.

    inline_override, when provided, replaces inline_file_context entirely.
    This allows batched evidence_curator to inject per-batch file content.

    stage_data, when provided, injects compact inline JSON from prior stages,
    so downstream agents can access upstream outputs without sandbox file reads.
    """
    parts = [skill_prompt, "", "## Project Context", "", "```json"]
    parts.append(json.dumps(context, indent=2, ensure_ascii=False))
    parts.append("```")

    effective_inline = inline_override if inline_override is not None else inline_file_context
    if effective_inline:
        parts.append("")
        parts.append(effective_inline)

    # D2: inject prior stage outputs inline (bypasses sandbox file read restrictions)
    if stage_data:
        parts.append("")
        parts.append("## Prior Stage Output (inline — no file read needed)")
        for stage_key, data in stage_data.items():
            parts.append(f"### {stage_key}")
            parts.append("```json")
            compact = json.dumps(data, indent=2, ensure_ascii=False)
            if len(compact) > 8000:
                compact = compact[:8000] + "\n... [truncated at 8000 chars]"
            parts.append(compact)
            parts.append("```")
            parts.append("")

    if upstream_artifacts:
        parts.append("")
        parts.append("## Upstream Artifact Paths (for reference)")
        parts.append("")
        for key, path in upstream_artifacts.items():
            parts.append(f"- **{key}**: `{path}`")

    parts.append("")
    parts.append(stage_description)

    return "\n".join(parts)


# ── Graph Nodes ─────────────────────────────────────────────────────────────────


# Tool-call JSON formatting error patterns produced by models (MiniMax, Kimi, etc.)
_TOOL_JSON_ERROR_PATTERNS = (
    "invalid function arguments json string",
    "Invalid parameter: invalid function arguments",
    "json_parse_error",
    "failed to parse function arguments",
)

_MAX_RETRIES = 3  # Total attempts (1 initial + 2 retries)
_AO_SHARD_MAX_CHARS = int(os.getenv("CER_REVIEW_AO_SHARD_MAX_CHARS", "2500"))
_AO_SHARD_OVERLAP_CHARS = int(os.getenv("CER_REVIEW_AO_SHARD_OVERLAP_CHARS", "120"))
_AO_MAX_SHARD_ERRORS = int(os.getenv("CER_REVIEW_AO_MAX_SHARD_ERRORS", "3"))
_AO_SHARD_MAX_ATTEMPTS = int(os.getenv("CER_REVIEW_AO_SHARD_MAX_ATTEMPTS", "2"))
_AO_SHARD_TIMEOUT_SECONDS = int(os.getenv("CER_REVIEW_AO_SHARD_TIMEOUT_SECONDS", "600"))
_AO_LARGE_FAMILY_SHARD_THRESHOLD = int(os.getenv("CER_REVIEW_AO_LARGE_FAMILY_SHARD_THRESHOLD", "24"))
_AO_LARGE_FAMILY_SELECTED_SHARDS = int(os.getenv("CER_REVIEW_AO_LARGE_FAMILY_SELECTED_SHARDS", "24"))
_AO_REMEDIATION_LLM_RETRY = os.getenv("CER_REVIEW_AO_REMEDIATION_LLM_RETRY", "0") == "1"


def _iter_json_candidates(text: str) -> list[tuple[str, str, list[str]]]:
    """Return parseable JSON object candidates with extraction strategy metadata."""
    import re

    if not text:
        return []

    decoder = json.JSONDecoder()
    candidates: list[tuple[str, str, list[str]]] = []
    seen: set[str] = set()

    def add_candidate(raw: str, strategy: str, warning_flags: list[str]) -> None:
        stripped = raw.strip()
        if not stripped or stripped in seen:
            return
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            return
        if isinstance(parsed, dict):
            seen.add(stripped)
            candidates.append((strategy, stripped, warning_flags))

    for pattern, strategy in (
        (r"```json\s*\n(.*?)\n```", "markdown_json_fence"),
        (r"```\s*\n(.*?)\n```", "markdown_code_fence"),
    ):
        for block in re.findall(pattern, text, re.DOTALL | re.IGNORECASE):
            add_candidate(block, strategy, ["polluted_output_recovered"] if text.strip() != block.strip() else [])

    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    if cleaned != text.strip():
        for pattern, strategy in (
            (r"```json\s*\n(.*?)\n```", "think_stripped_markdown_json_fence"),
            (r"```\s*\n(.*?)\n```", "think_stripped_markdown_code_fence"),
        ):
            for block in re.findall(pattern, cleaned, re.DOTALL | re.IGNORECASE):
                add_candidate(block, strategy, ["think_tags_removed", "polluted_output_recovered"])

    for source, strategy, flags in (
        (text, "embedded_json_object", ["polluted_output_recovered"]),
        (cleaned, "think_stripped_embedded_json_object", ["think_tags_removed", "polluted_output_recovered"]),
    ):
        for match in re.finditer(r"\{", source):
            try:
                parsed, end_idx = decoder.raw_decode(source[match.start() :])
            except json.JSONDecodeError:
                continue
            if not isinstance(parsed, dict):
                continue
            raw = source[match.start() : match.start() + end_idx]
            add_candidate(raw, strategy, flags)

    return candidates


def _validate_stage_json(data: dict, target_stage: SMState | None = None) -> dict[str, Any]:
    """Validate extracted JSON against the stage artifact contract."""
    errors: list[str] = []
    warnings: list[str] = []
    candidate_count: int | None = None
    atomic_count: int | None = None
    cluster_count: int | None = None

    if not isinstance(data, dict):
        errors.append("payload is not a JSON object")
    elif data.get("upstream_artifact_missing") is True:
        errors.append("upstream_artifact_missing guard payload is not a valid stage result")
        warnings.append("upstream_artifact_missing_not_zero_findings")

    if target_stage == SMState.GAP_ANALYSIS_DONE:
        atomic_observations = data.get("atomic_observations")
        if not isinstance(atomic_observations, list):
            errors.append("atomic_observations must be present and must be a list")
        else:
            atomic_count = len(atomic_observations)
            atomic_ids: set[str] = set()
            for idx, observation in enumerate(atomic_observations):
                if not isinstance(observation, dict):
                    errors.append(f"atomic_observations[{idx}] must be an object")
                    continue
                for key in ("id", "observation", "evidence_ref", "source_file", "section", "family", "confidence"):
                    if key not in observation:
                        errors.append(f"atomic_observations[{idx}] missing required key: {key}")
                obs_id = observation.get("id")
                if isinstance(obs_id, str) and obs_id:
                    if obs_id in atomic_ids:
                        errors.append(f"atomic_observations duplicate id: {obs_id}")
                    atomic_ids.add(obs_id)

        clusters = data.get("finding_clusters")
        if not isinstance(clusters, list):
            errors.append("finding_clusters must be present and must be a list")
        else:
            cluster_count = len(clusters)
            atomic_ids_for_refs = {
                item.get("id")
                for item in atomic_observations or []
                if isinstance(item, dict) and isinstance(item.get("id"), str)
            } if isinstance(atomic_observations, list) else set()
            for idx, cluster in enumerate(clusters):
                if not isinstance(cluster, dict):
                    errors.append(f"finding_clusters[{idx}] must be an object")
                    continue
                for key in ("cluster_id", "topic", "ao_refs", "summary"):
                    if key not in cluster:
                        errors.append(f"finding_clusters[{idx}] missing required key: {key}")
                refs = cluster.get("ao_refs")
                if not isinstance(refs, list):
                    errors.append(f"finding_clusters[{idx}].ao_refs must be a list")
                else:
                    for ref in refs:
                        if ref not in atomic_ids_for_refs:
                            errors.append(f"finding_clusters[{idx}].ao_refs references missing atomic_observation id: {ref}")

        findings = data.get("candidate_findings")
        if not isinstance(findings, list):
            errors.append("candidate_findings must be present and must be a list")
        else:
            candidate_count = len(findings)
            for idx, finding in enumerate(findings):
                if not isinstance(finding, dict):
                    errors.append(f"candidate_findings[{idx}] must be an object")
                    continue
                for key in ("finding_id", "type", "severity_advisory", "evidence"):
                    if key not in finding:
                        errors.append(f"candidate_findings[{idx}] missing required key: {key}")
                if "evidence" in finding and not isinstance(finding.get("evidence"), list):
                    errors.append(f"candidate_findings[{idx}].evidence must be a list")
        if data.get("reviewer_decision") not in (None, "PENDING"):
            errors.append("reviewer_decision must be PENDING when present")
    elif target_stage == SMState.EVIDENCE_INVENTORY_DONE:
        if not isinstance(data.get("source_inventory"), list):
            errors.append("source_inventory must be present and must be a list")
    elif target_stage == SMState.SEVERITY_SYNTHESIS_DONE:
        if not isinstance(data.get("severity_signals"), list):
            errors.append("severity_signals must be present and must be a list")
        if data.get("reviewer_decision") not in (None, "PENDING"):
            errors.append("reviewer_decision must be PENDING when present")

    classification = None
    if errors and target_stage == SMState.GAP_ANALYSIS_DONE:
        classification = "GAP_SPECIALIST_SCHEMA_CONTRACT_FAILURE"
    elif errors:
        classification = "STRUCTURED_OUTPUT_SCHEMA_CONTRACT_FAILURE"

    return {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "candidate_count": candidate_count,
        "atomic_observation_count": atomic_count,
        "finding_cluster_count": cluster_count,
        "classification": classification,
    }


def _extract_stage_json_from_text(text: str, target_stage: SMState | None = None) -> tuple[dict | None, dict[str, Any]]:
    """Extract and validate structured JSON for a stage."""
    attempts: list[dict[str, Any]] = []
    for strategy, raw, warning_flags in _iter_json_candidates(text):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            attempts.append({"strategy": strategy, "json_error": str(exc)})
            continue
        validation = _validate_stage_json(data, target_stage)
        attempts.append({
            "strategy": strategy,
            "schema_validation_result": validation,
            "warning_flags": warning_flags + validation.get("warnings", []),
        })
        if validation["valid"]:
            return data, {
                "extraction_strategy": strategy,
                "schema_validation_result": validation,
                "warning_flags": warning_flags + validation.get("warnings", []),
                "candidate_count": validation.get("candidate_count"),
                "candidate_attempts": attempts,
            }

    classification = None
    errors: list[str] = []
    for attempt in attempts:
        validation = attempt.get("schema_validation_result") or {}
        if validation.get("classification"):
            classification = validation["classification"]
        errors.extend(validation.get("errors") or [])
    if classification is None and target_stage == SMState.GAP_ANALYSIS_DONE:
        classification = "GAP_SPECIALIST_SCHEMA_CONTRACT_FAILURE"
    elif classification is None:
        classification = "STRUCTURED_OUTPUT_PARSE_FAILURE"

    return None, {
        "extraction_strategy": None,
        "schema_validation_result": {
            "valid": False,
            "errors": errors or ["No schema-conformant JSON payload found"],
            "warnings": [],
            "candidate_count": None,
            "classification": classification,
        },
        "warning_flags": [],
        "candidate_count": None,
        "candidate_attempts": attempts,
    }


def _extract_json_from_text(text: str) -> dict | None:
    """Backward-compatible JSON extraction helper."""
    data, _metadata = _extract_stage_json_from_text(text, None)
    return data


def _write_artifact_json(output_dir: str, filename: str, data: dict) -> str:
    """Write a JSON artifact to disk (direct Python I/O, bypasses sandbox)."""
    out_path = Path(output_dir) / filename
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("Wrote artifact: %s (%d bytes)", out_path, out_path.stat().st_size)
    return str(out_path)


def _write_artifact_text(output_dir: str, filename: str, text: str) -> str:
    """Write a text artifact to disk for diagnostics."""
    out_path = Path(output_dir) / filename
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8")
    logger.info("Wrote artifact: %s (%d bytes)", out_path, out_path.stat().st_size)
    return str(out_path)


def _stage_output_filename(target_stage: SMState) -> str | None:
    return {
        SMState.EVIDENCE_INVENTORY_DONE: "source_inventory.json",
        SMState.GAP_ANALYSIS_DONE: "finding_clusters.json",
        SMState.SEVERITY_SYNTHESIS_DONE: "review_report.json",
    }.get(target_stage)


def _load_valid_stage_artifact(artifact_root: str | Path, target_stage: SMState) -> tuple[dict | None, dict[str, Any] | None]:
    """Load a valid already-written stage artifact as parser fallback."""
    output_filename = _stage_output_filename(target_stage)
    if not output_filename:
        return None, None
    artifact_path = Path(artifact_root) / output_filename
    if not artifact_path.exists():
        return None, None
    try:
        data = json.loads(artifact_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return None, {
            "artifact_path": str(artifact_path),
            "schema_validation_result": {
                "valid": False,
                "errors": [f"existing artifact could not be parsed: {exc}"],
                "warnings": [],
                "candidate_count": None,
                "classification": "STRUCTURED_OUTPUT_PARSE_FAILURE",
            },
        }
    validation = _validate_stage_json(data, target_stage)
    return (data if validation["valid"] else None), {
        "artifact_path": str(artifact_path),
        "schema_validation_result": validation,
    }


# ── Batch File Helpers ──────────────────────────────────────────────────────────
# These replicate the pilot script's file-reading logic so the lead agent can
# read files directly from input_root in batched evidence_curator processing.

_BATCH_SIZE = 5


def _read_input_files(input_path: Path) -> dict[str, str]:
    """Read input files from input_root, supporting both .txt directory and .json formats."""
    files: dict[str, str] = {}
    if not input_path.exists():
        return files
    if input_path.is_dir():
        for f in sorted(input_path.glob("*.txt")):
            try:
                files[f.name] = f.read_text(encoding="utf-8")
            except Exception:
                files[f.name] = f"[READ ERROR]"
    elif input_path.suffix == ".json":
        try:
            data = json.loads(input_path.read_text(encoding="utf-8"))
        except Exception:
            return files
        for filename, entry in data.items():
            if isinstance(entry, dict) and "text" in entry:
                files[filename] = entry["text"]
            elif isinstance(entry, str):
                files[filename] = entry
            else:
                files[filename] = json.dumps(entry, ensure_ascii=False)
    return files


def _build_inline_for_batch(batch_files: dict[str, str], batch_num: int, total_batches: int) -> str:
    """Build inline file context block for a single batch of files."""
    lines = [
        f"## Batch {batch_num}/{total_batches}: Source Files ({len(batch_files)} files)",
        "",
    ]
    for name, content in batch_files.items():
        size = len(content)
        if size <= 2000:
            preview = content
            note = ""
        elif size <= 20000:
            preview = content[:2000]
            note = f" [...truncated at 2000 chars, full size: {size} chars]"
        else:
            preview = content[:1000]
            note = f" [...truncated at 1000 chars, full size: {size} chars]"

        lines.append(f"### {name} ({size} chars)")
        lines.append("```")
        lines.append(preview + note)
        lines.append("```")
        lines.append("")

    lines.append("## Batch Instructions")
    lines.append(f"You are analyzing batch {batch_num} of {total_batches}. ")
    lines.append("Output a JSON object with a source_inventory array containing entries ONLY for the files listed above. ")
    lines.append("Use file_id S-001, S-002, etc. within this batch — the orchestrator will renumber globally. ")
    lines.append("Return your JSON output in a ```json code block at the very end of your response.")
    lines.append("")

    return "\n".join(lines)


def _split_extracted_documents(filename: str, content: str) -> list[dict[str, str]]:
    """Split a family extracted-text bundle into source-file sections."""
    if filename.endswith("_extracted.txt"):
        return [{
            "source_file": filename,
            "text": content,
            "source_resolution": "consolidated_extracted_text",
        }]

    pattern = re.compile(r"^===\s*(.*?)\s*===\s*$", re.MULTILINE)
    matches = list(pattern.finditer(content))
    if not matches:
        return [{"source_file": filename, "text": content, "source_resolution": "single_text_file"}]

    docs: list[dict[str, str]] = []
    for idx, match in enumerate(matches):
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(content)
        source_file = match.group(1).strip() or f"{filename}#section-{idx + 1}"
        text = content[start:end].strip()
        if text:
            docs.append({"source_file": source_file, "text": text, "source_resolution": "embedded_source_section"})
    return docs or [{"source_file": filename, "text": content, "source_resolution": "single_text_file"}]


def _chunk_document_text(text: str, max_chars: int = _AO_SHARD_MAX_CHARS) -> list[tuple[int, str]]:
    if len(text) <= max_chars:
        return [(1, text)]

    chunks: list[tuple[int, str]] = []
    start = 0
    chunk_idx = 1
    while start < len(text):
        end = min(len(text), start + max_chars)
        if end < len(text):
            boundary = max(text.rfind("\n\n", start, end), text.rfind("\n", start, end))
            if boundary > start + max_chars // 2:
                end = boundary
        chunks.append((chunk_idx, text[start:end].strip()))
        chunk_idx += 1
        if end >= len(text):
            break
        start = max(end - _AO_SHARD_OVERLAP_CHARS, start + 1)
    return chunks


def _build_gap_shards(input_root: Path, family: str) -> list[dict[str, Any]]:
    all_files = _read_input_files(input_root)
    shards: list[dict[str, Any]] = []
    shard_idx = 1
    for filename, content in sorted(all_files.items()):
        for doc in _split_extracted_documents(filename, content):
            for chunk_idx, chunk in _chunk_document_text(doc["text"]):
                if not chunk:
                    continue
                shards.append({
                    "shard_id": f"SHARD-{shard_idx:04d}",
                    "family": family,
                    "bundle_file": filename,
                    "source_file": doc["source_file"],
                    "source_resolution": doc.get("source_resolution", "unknown"),
                    "section": f"chunk-{chunk_idx}",
                    "text": chunk,
                    "char_count": len(chunk),
                })
                shard_idx += 1
    return shards


_AO_REDUCTION_KEYWORDS = (
    "objective",
    "scope",
    "device description",
    "intended purpose",
    "indication",
    "clinical benefit",
    "equivalence",
    "clinical data",
    "literature search",
    "state of the art",
    "sota",
    "safety",
    "performance",
    "risk",
    "hazard",
    "adverse",
    "conclusion",
    "pmcf",
    "pms",
    "ifu",
    "annex",
    "evaluator",
    "declaration of interest",
)


def _select_gap_shards_for_ao(shards: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Reduce very large monolithic families to structural/keyword coverage shards.

    This is input reduction, not finding top-N: AO extraction remains exhaustive
    inside every selected shard, and the reduction metadata is persisted so a
    later resume can expand coverage.
    """
    if len(shards) <= _AO_LARGE_FAMILY_SHARD_THRESHOLD:
        return shards, {
            "applied": False,
            "original_shard_count": len(shards),
            "selected_shard_count": len(shards),
            "method": "none",
        }

    selected_by_id: dict[str, dict[str, Any]] = {}

    # Preserve front matter and core CER setup sections without scoring them as findings.
    for shard in shards[:6]:
        selected_by_id[shard["shard_id"]] = shard

    scored: list[tuple[int, int, dict[str, Any]]] = []
    for index, shard in enumerate(shards):
        text = str(shard.get("text", "")).lower()
        score = sum(1 for keyword in _AO_REDUCTION_KEYWORDS if keyword in text)
        if score:
            scored.append((score, -index, shard))
    scored.sort(reverse=True)

    for _score, _neg_index, shard in scored:
        selected_by_id.setdefault(shard["shard_id"], shard)
        if len(selected_by_id) >= _AO_LARGE_FAMILY_SELECTED_SHARDS:
            break

    if len(selected_by_id) < _AO_LARGE_FAMILY_SELECTED_SHARDS:
        stride = max(1, len(shards) // _AO_LARGE_FAMILY_SELECTED_SHARDS)
        for shard in shards[::stride]:
            selected_by_id.setdefault(shard["shard_id"], shard)
            if len(selected_by_id) >= _AO_LARGE_FAMILY_SELECTED_SHARDS:
                break

    selected = sorted(selected_by_id.values(), key=lambda item: int(str(item["shard_id"]).split("-")[-1]))
    return selected, {
        "applied": True,
        "original_shard_count": len(shards),
        "selected_shard_count": len(selected),
        "method": "structural_keyword_coverage",
        "keywords": list(_AO_REDUCTION_KEYWORDS),
        "note": "Large-family AO input reduction selected structural and keyword-bearing shards; AO extraction remains exhaustive within selected shards.",
    }


def _infer_family_from_state(state: ReviewAssistState) -> str:
    input_root = Path(state.get("input_root", ""))
    files = _read_input_files(input_root)
    if len(files) == 1:
        name = next(iter(files.keys()))
        if name.endswith("_extracted.txt"):
            return name[: -len("_extracted.txt")]
        if name.endswith(".txt"):
            return name[:-4]
    return input_root.name or "UNKNOWN_FAMILY"


def _resolve_family_name(state: ReviewAssistState, config: RunnableConfig | None = None) -> str:
    if config:
        metadata = config.get("metadata", {}) or {}
        family = metadata.get("family")
        if isinstance(family, str) and family.strip():
            return family.strip()
    return _infer_family_from_state(state)


def _validate_atomic_observation_doc(data: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    observations = data.get("atomic_observations")
    if not isinstance(observations, list):
        errors.append("atomic_observations must be present and must be a list")
    else:
        seen: set[str] = set()
        for idx, observation in enumerate(observations):
            if not isinstance(observation, dict):
                errors.append(f"atomic_observations[{idx}] must be an object")
                continue
            for key in ("id", "observation", "evidence_ref", "source_file", "section", "family", "confidence"):
                if key not in observation:
                    errors.append(f"atomic_observations[{idx}] missing required key: {key}")
            obs_id = observation.get("id")
            if isinstance(obs_id, str):
                if obs_id in seen:
                    errors.append(f"duplicate atomic_observation id: {obs_id}")
                seen.add(obs_id)
    return {
        "valid": not errors,
        "errors": errors,
        "atomic_observation_count": len(observations) if isinstance(observations, list) else None,
    }


def _normalize_atomic_observation(raw: dict[str, Any], shard: dict[str, Any], global_idx: int) -> dict[str, Any]:
    observation = str(raw.get("observation", "")).strip()
    if len(observation) > 360:
        observation = observation[:357].rstrip() + "..."
    evidence_ref = str(raw.get("evidence_ref") or f"{shard['shard_id']}:{shard['source_file']}:{shard['section']}").strip()
    source_file = str(raw.get("source_file") or shard["source_file"]).strip()
    section = str(raw.get("section") or shard["section"]).strip()
    family = str(raw.get("family") or shard["family"]).strip()
    raw_confidence = raw.get("confidence", 0.5)
    if isinstance(raw_confidence, str):
        confidence_map = {
            "high": 0.8,
            "medium": 0.55,
            "moderate": 0.55,
            "low": 0.25,
        }
        confidence = confidence_map.get(raw_confidence.strip().lower(), 0.5)
    else:
        try:
            confidence = float(raw_confidence)
        except (TypeError, ValueError):
            confidence = 0.5
    confidence = max(0.0, min(1.0, confidence))
    remediation = str(raw.get("remediation", "")).strip()
    if len(remediation) < 20:
        concern = observation[:90].rstrip(". ") or "the source-anchored observation"
        remediation = f"Review {source_file} {section} for {concern}."
    return {
        "id": f"AO-{global_idx:04d}",
        "observation": observation,
        "evidence_ref": evidence_ref,
        "source_file": source_file,
        "section": section,
        "family": family,
        "confidence": round(confidence, 2),
        "remediation": remediation,
    }


def _cluster_key_for_observation(observation: dict[str, Any]) -> str:
    text = str(observation.get("observation", "")).lower()
    source = str(observation.get("source_file", "")).lower()
    if "device name" in text or "model" in text or "identifier" in text:
        return "device_identifier_consistency"
    if "ifu" in text and ("cer" in text or "claim" in text):
        return "ifu_cer_alignment"
    if "clinical" in text or "evidence" in text or "literature" in text:
        return "clinical_evidence_chain"
    if "risk" in text or "hazard" in text or "mitigation" in text:
        return "risk_traceability"
    if "missing" in text or "absent" in text or "not found" in text:
        return "document_completeness"
    if "sota" in source or "literature" in source:
        return "sota_literature_traceability"
    return "general_document_gap"


def _cluster_label(cluster_key: str) -> str:
    return {
        "device_identifier_consistency": "Device identifier consistency",
        "ifu_cer_alignment": "IFU-CER alignment",
        "clinical_evidence_chain": "Clinical evidence chain",
        "risk_traceability": "Risk traceability",
        "document_completeness": "Document completeness",
        "sota_literature_traceability": "SOTA literature traceability",
        "general_document_gap": "General document gap",
    }.get(cluster_key, cluster_key.replace("_", " ").title())


def _candidate_type(cluster_key: str) -> str:
    return {
        "device_identifier_consistency": "inconsistency",
        "ifu_cer_alignment": "cross_document_gap",
        "clinical_evidence_chain": "evidence_chain_break",
        "risk_traceability": "traceability_gap",
        "document_completeness": "missing_document",
        "sota_literature_traceability": "evidence_chain_break",
        "general_document_gap": "cross_document_gap",
    }.get(cluster_key, "cross_document_gap")


def _build_gap_layers_from_atomic(
    observations: list[dict[str, Any]],
    *,
    project_id: str,
    review_session_id: str,
    family: str,
    source_inventory_ref: str | None,
    shard_count: int,
    original_shard_count: int,
    input_reduction: dict[str, Any],
    shard_errors: list[dict[str, Any]],
) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for observation in observations:
        grouped.setdefault(_cluster_key_for_observation(observation), []).append(observation)

    clusters: list[dict[str, Any]] = []
    candidate_findings: list[dict[str, Any]] = []
    for idx, (cluster_key, members) in enumerate(grouped.items(), 1):
        cluster_id = f"FC-{idx:03d}"
        label = _cluster_label(cluster_key)
        member_refs = [item["id"] for item in members]
        source_files = sorted({str(item.get("source_file", "")) for item in members if item.get("source_file")})
        summary = f"{label}: {len(members)} source-anchored observation(s) across {len(source_files)} source file(s)."
        clusters.append({
            "cluster_id": cluster_id,
            "topic": label,
            "ao_refs": member_refs,
            "summary": summary,
        })

        evidence = []
        for item in members[:3]:
            evidence.append({
                "source_file": item.get("source_file", ""),
                "location": item.get("section", ""),
                "excerpt": item.get("observation", ""),
                "atomic_observation_ref": item.get("id", ""),
            })
        candidate_findings.append({
            "finding_id": f"GAP-{idx:03d}",
            "type": _candidate_type(cluster_key),
            "severity_advisory": "MEDIUM",
            "blocking_level": "WARNING",
            "human_gate_required": False,
            "description": summary,
            "documents_involved": source_files,
            "calibration_rule_ref": "PENDING_LQA_CALIBRATION",
            "calibration_confidence": round(max((float(item.get("confidence", 0.0)) for item in members), default=0.5), 2),
            "g_point_category": "evidence_gap" if "evidence" in cluster_key or "literature" in cluster_key else "consistency_gap",
            "evidence_confidence": "PRIMARY_SUMMARY",
            "needs_primary_source_verification": False,
            "evidence": evidence,
            "recommended_action": "Human reviewer should evaluate the clustered atomic observations and confirm the appropriate remediation.",
            "cluster_ref": cluster_id,
            "atomic_observation_refs": member_refs,
        })

    return {
        "schema_name": "cer_review_gap_discovery_layers",
        "schema_version": "v3",
        "project_id": project_id,
        "review_session_id": review_session_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "reviewer_decision": "PENDING",
        "family": family,
        "source_inventory_ref": source_inventory_ref,
        "atomic_observations": observations,
        "finding_clusters": clusters,
        "candidate_findings": candidate_findings,
        "summary": {
            "total_atomic_observations": len(observations),
            "total_clusters": len(clusters),
            "total_candidate_findings": len(candidate_findings),
            "total_gaps": len(candidate_findings),
            "blocking_gaps": 0,
            "warning_gaps": len(candidate_findings),
            "informational_gaps": 0,
            "shards_processed": shard_count,
            "original_shards_available": original_shard_count,
            "input_reduction": input_reduction,
            "shard_errors": len(shard_errors),
            "layering_contract": "atomic_observations_exhaustive_discovery__clusters_dedup__candidate_findings_concise_lqa_handoff",
        },
        "pipeline_limitations": [
            {
                "description": "One or more atomic observation shards failed and were not guessed or repaired from prose.",
                "affected_documents": sorted({str(err.get("source_file", "")) for err in shard_errors if err.get("source_file")}),
                "limitation_type": "atomic_observation_shard_failure",
            }
        ] if shard_errors else [],
    }


def _write_ao_shard_status(artifact_root: Path, status_doc: dict[str, Any]) -> str:
    path = _write_artifact_json(str(artifact_root), "ao_shard_status.json", status_doc)
    return path


def _initial_ao_shard_status(
    *,
    project_id: str,
    review_session_id: str,
    family: str,
    shards: list[dict[str, Any]],
    input_reduction: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "schema_name": "cer_review_ao_shard_status",
        "schema_version": "v1",
        "project_id": project_id,
        "review_session_id": review_session_id,
        "family": family,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "running",
        "shard_count": len(shards),
        "input_reduction": input_reduction or {"applied": False},
        "completed_shards": 0,
        "failed_shards": 0,
        "events": [
            {
                "event": "ao_shard_discovery_started",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "shard_count": len(shards),
                "shard_max_chars": _AO_SHARD_MAX_CHARS,
                "shard_overlap_chars": _AO_SHARD_OVERLAP_CHARS,
            }
        ],
        "shards": [
            {
                "shard_id": shard["shard_id"],
                "source_file": shard["source_file"],
                "source_resolution": shard.get("source_resolution", "unknown"),
                "section": shard["section"],
                "char_count": shard["char_count"],
                "status": "pending",
                "atomic_observation_count": None,
                "attempts": 0,
                "error": None,
            }
            for shard in shards
        ],
    }


def _update_ao_shard_status(
    status_doc: dict[str, Any],
    *,
    shard_id: str,
    status: str,
    atomic_observation_count: int | None = None,
    attempt: int | None = None,
    error: Any = None,
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    for shard in status_doc.get("shards", []):
        if isinstance(shard, dict) and shard.get("shard_id") == shard_id:
            shard["status"] = status
            shard["updated_at"] = now
            if atomic_observation_count is not None:
                shard["atomic_observation_count"] = atomic_observation_count
            if attempt is not None:
                shard["attempts"] = attempt
            if error is not None:
                shard["error"] = error
            break
    status_doc["completed_shards"] = sum(
        1 for shard in status_doc.get("shards", []) if isinstance(shard, dict) and shard.get("status") == "completed"
    )
    status_doc["failed_shards"] = sum(
        1 for shard in status_doc.get("shards", []) if isinstance(shard, dict) and shard.get("status") == "failed"
    )
    status_doc.setdefault("events", []).append({
        "event": f"ao_shard_{status}",
        "timestamp": now,
        "shard_id": shard_id,
        "atomic_observation_count": atomic_observation_count,
        "attempt": attempt,
        "error": error,
    })


def _atomic_gap_specialist_system_prompt() -> str:
    return (
        "CER Review Assist Gap Specialist — atomic discovery mode. "
        "Advisory-only; never issue PASS, FAIL, APPROVED, REJECTED, or CEAR verdicts. "
        "Your only job is to extract lightweight, source-anchored atomic observations from the provided shard. "
        "Do not perform severity synthesis, regulatory final judgment, repair task card writing, or report assembly. "
        "Return exactly one JSON object with atomic_observations as a list. "
        "Each observation is a short problem-level observation grounded in the shard text and must include: "
        "id, observation, evidence_ref, source_file, section, family, confidence, remediation. "
        "No fixed top-N is allowed; include every schema-supported observation visible in the shard, while avoiding duplicates."
    )


async def _run_gap_atomic_shard(
    *,
    shard: dict[str, Any],
    state: ReviewAssistState,
    config: RunnableConfig,
    skill_prompt: str,
    context: dict[str, Any],
    shard_number: int,
    total_shards: int,
    attempt: int | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Run the Gap Specialist in lightweight atomic-observation mode for one shard."""
    shard_context = {
        "shard_id": shard["shard_id"],
        "shard_number": shard_number,
        "total_shards": total_shards,
        "family": shard["family"],
        "source_file": shard["source_file"],
        "source_resolution": shard.get("source_resolution", "unknown"),
        "section": shard["section"],
        "bundle_file": shard["bundle_file"],
        "char_count": shard["char_count"],
    }
    inline = (
        "## Gap Specialist Atomic Observation Shard\n\n"
        "```json\n"
        f"{json.dumps(shard_context, indent=2, ensure_ascii=False)}\n"
        "```\n\n"
        "## Source Text Shard\n\n"
        f"### {shard['source_file']} / {shard['section']}\n"
        "```\n"
        f"{shard['text']}\n"
        "```\n"
    )
    stage_description = (
        "NATIVE OUTPUT CONTRACT: return exactly one valid JSON object and no prose. "
        "This is the lightweight discovery layer. Output only atomic_observations; do not output "
        "candidate_findings, severity_rationale, repair task cards, human_gate narratives, or review report prose. "
        "No fixed top-N is allowed: emit every evidence-backed atomic observation visible in this shard. "
        "Each observation must be short and source-anchored with keys: id, observation, evidence_ref, "
        "source_file, section, family, confidence, remediation. Use temporary ids AO-TMP-001... within this shard. "
        "Keep observation under 220 characters; evidence_ref should identify the local phrase/paragraph/heading. "
        "Keep remediation under 160 characters and use the pattern: Review [source_file] [section] for [specific concern]. "
        "If the shard has no schema-supported observations, return {\"atomic_observations\": []}. "
        "All reviewer decisions remain PENDING and no PASS/FAIL/APPROVED/REJECTED/CEAR terminal verdicts."
    )
    # The full Gap Specialist skill already lives in the subagent system prompt.
    # Do not duplicate that large V2 candidate schema in every shard user prompt:
    # atomic discovery must stay lightweight enough to remain parseable.
    task_prompt = "\n".join([
        "## Project Context",
        "",
        "```json",
        json.dumps(context, indent=2, ensure_ascii=False),
        "```",
        "",
        inline,
        "",
        stage_description,
    ])
    model_name = config.get("metadata", {}).get("model_name") if config else None
    cfg = _build_subagent_config(
        SKILL_GAP_SPECIALIST,
        _atomic_gap_specialist_system_prompt(),
        model_override=model_name,
        tools_override=[],
    )
    cfg.max_turns = min(cfg.max_turns, 80)
    cfg.timeout_seconds = min(cfg.timeout_seconds, _AO_SHARD_TIMEOUT_SECONDS)
    executor = SubagentExecutor(
        config=cfg,
        tools=list(SUBAGENT_TOOLS),
        parent_model=config.get("metadata", {}).get("model_name") if config else None,
        sandbox_state=state.get("sandbox"),
        thread_data=state.get("thread_data"),
        thread_id=config.get("configurable", {}).get("thread_id") if config else None,
        trace_id=f"{context['review_session_id']}-{SKILL_GAP_SPECIALIST}-{shard['shard_id']}",
    )
    result = await executor._aexecute(task_prompt)
    raw_text = str(result.result or "")
    raw_output_path = _write_artifact_text(
        str(state.get("artifact_root", "/tmp")),
        f"ao_shards/{shard['shard_id']}_attempt-{attempt or 0:02d}_raw.txt",
        raw_text,
    )
    extracted, details = _extract_stage_json_from_text(raw_text, None)
    diagnostics = {
        "shard_id": shard["shard_id"],
        "source_file": shard["source_file"],
        "section": shard["section"],
        "raw_output_size": len(raw_text),
        "raw_output_path": raw_output_path,
        "status": result.status.value if hasattr(result.status, "value") else str(result.status),
        "error": str(result.error or ""),
        "extraction_details": details,
    }
    if not extracted:
        diagnostics["validation"] = {"valid": False, "errors": ["No parseable JSON object found"]}
        return [], diagnostics
    validation = _validate_atomic_observation_doc(extracted)
    diagnostics["validation"] = validation
    if not validation["valid"]:
        return [], diagnostics

    raw_observations = [item for item in extracted.get("atomic_observations", []) if isinstance(item, dict)]

    # ── Remediation Enforcement (V16.1 harness-level) ──────────────────────
    _REMEDIATION_MIN_CHARS = 20
    _REMEDIATION_TARGET_RATE = 0.50
    _REMEDIATION_ACCEPT_RATE = 0.30
    _REMEDIATION_MAX_RETRIES = 1

    total = len(raw_observations)
    if total > 0:
        rem_count = sum(
            1 for ao in raw_observations
            if ao.get("remediation") and len(str(ao["remediation"])) >= _REMEDIATION_MIN_CHARS
        )
        rem_rate = rem_count / total
        diagnostics["remediation_rate_initial"] = rem_rate

        if rem_rate < _REMEDIATION_TARGET_RATE and _AO_REMEDIATION_LLM_RETRY:
            missing = total - rem_count
            retry_prompt = (
                f"## REMEDIATION REQUIRED — RE-OUTPUT ALL ATOMIC OBSERVATIONS\n\n"
                f"Your previous output had {missing}/{total} atomic observations with empty or too-short "
                f"remediation (minimum {_REMEDIATION_MIN_CHARS} characters). "
                f"This is REQUIRED — every AO MUST have a concrete remediation sentence.\n\n"
                f"For EVERY AO, write remediation following EXACTLY one of these patterns:\n"
                f"A. 'Add [specific content] to [document] [section] to address [requirement].'\n"
                f"B. 'Update [document] [section] from [current] to [correct] per [standard].'\n"
                f"C. 'Create [missing document] with [required sections] per [regulation].'\n"
                f"If none fit: 'Review [document] [section] for [specific concern].'\n\n"
                f"Minimum {_REMEDIATION_MIN_CHARS} characters per remediation. "
                f"Re-output the COMPLETE atomic_observations array with ALL remediations filled.\n\n"
                f"## Previous Output (reference — fill ALL remediation fields):\n\n"
                f"```json\n{json.dumps(raw_observations, indent=2, ensure_ascii=False)[:4000]}\n```"
            )

            for rem_attempt in range(1, _REMEDIATION_MAX_RETRIES + 1):
                rem_task = task_prompt + "\n\n" + retry_prompt
                rem_executor = SubagentExecutor(
                    config=cfg,
                    tools=list(SUBAGENT_TOOLS),
                    parent_model=config.get("metadata", {}).get("model_name") if config else None,
                    sandbox_state=state.get("sandbox"),
                    thread_data=state.get("thread_data"),
                    thread_id=config.get("configurable", {}).get("thread_id") if config else None,
                    trace_id=f"{context['review_session_id']}-{SKILL_GAP_SPECIALIST}-{shard['shard_id']}-rem-{rem_attempt}",
                )
                rem_result = await rem_executor._aexecute(rem_task)
                rem_text = str(rem_result.result or "")
                diagnostics[f"remediation_retry_{rem_attempt}_raw_output_path"] = _write_artifact_text(
                    str(state.get("artifact_root", "/tmp")),
                    f"ao_shards/{shard['shard_id']}_attempt-{attempt or 0:02d}_remediation-{rem_attempt}_raw.txt",
                    rem_text,
                )
                rem_extracted, _ = _extract_stage_json_from_text(rem_text, None)
                if rem_extracted:
                    rem_aos = [item for item in rem_extracted.get("atomic_observations", []) if isinstance(item, dict)]
                    if rem_aos:
                        raw_observations = rem_aos
                        rem_count2 = sum(
                            1 for ao in raw_observations
                            if ao.get("remediation") and len(str(ao["remediation"])) >= _REMEDIATION_MIN_CHARS
                        )
                        rem_rate2 = rem_count2 / len(raw_observations) if raw_observations else 0
                        diagnostics[f"remediation_rate_retry_{rem_attempt}"] = rem_rate2
                        if rem_rate2 >= _REMEDIATION_ACCEPT_RATE:
                            diagnostics["remediation_enforced"] = True
                            break
                diagnostics[f"remediation_retry_{rem_attempt}_failed"] = True

            final_rem = sum(
                1 for ao in raw_observations
                if ao.get("remediation") and len(str(ao["remediation"])) >= _REMEDIATION_MIN_CHARS
            )
            diagnostics["remediation_rate_final"] = final_rem / len(raw_observations) if raw_observations else 0
            if final_rem / max(len(raw_observations), 1) < _REMEDIATION_ACCEPT_RATE:
                diagnostics["remediation_debt"] = f"{final_rem}/{len(raw_observations)} AOs have remediation — below accept threshold"
        elif rem_rate < _REMEDIATION_TARGET_RATE:
            diagnostics["remediation_enforced"] = "deterministic_normalization"

    return raw_observations, diagnostics


# ── Graph Nodes ─────────────────────────────────────────────────────────────────


async def node_directory_inventory(state: ReviewAssistState, config: RunnableConfig) -> dict[str, Any]:
    """Deterministic pre-processing node: scan input_root and produce directory manifest.

    Pure Python — no LLM calls, no token cost. Detects empty files, records sizes,
    and initializes the state machine for the pipeline.
    """
    input_root = Path(state.get("input_root", ""))

    # Initialize state machine (moved from evidence_curator since this is now entry)
    sm = state.get("state_machine")
    if sm is None:
        artifact_root = Path(state.get("artifact_root", "/tmp"))
        sm = ReviewAssistStateMachine(
            project_id=state.get("project_id", ""),
            review_session_id=state.get("review_session_id", ""),
            artifact_root=artifact_root,
        )
        sm.append_log({"event": "pipeline_started", "project_id": state.get("project_id")})

    # Read all files to build manifest
    all_files = _read_input_files(input_root)
    manifest = []
    for name, content in all_files.items():
        size = len(content)
        manifest.append({
            "name": name,
            "size": size,
            "is_empty": size == 0,
            "is_placeholder": size < 100,  # Very small files are likely placeholders
        })

    manifest_sorted = sorted(manifest, key=lambda x: x["name"])
    empty_files = [m["name"] for m in manifest_sorted if m["is_empty"]]
    placeholder_files = [m["name"] for m in manifest_sorted if m["is_placeholder"] and not m["is_empty"]]

    # Persist manifest
    manifest_data = {
        "files": manifest_sorted,
        "total_files": len(manifest_sorted),
        "empty_files": empty_files,
        "placeholder_files": placeholder_files,
        "total_size_chars": sum(m["size"] for m in manifest_sorted),
    }
    manifest_path = _write_artifact_json(str(sm.artifact_root), "directory_manifest.json", manifest_data)
    sm.record_artifact("directory_manifest", manifest_path)
    sm.append_log({
        "event": "directory_inventory_complete",
        "total_files": len(manifest_sorted),
        "empty_files": len(empty_files),
    })

    logger.info(
        "Directory inventory: %d files, %d empty, %d placeholder, %d total chars",
        len(manifest_sorted), len(empty_files), len(placeholder_files),
        manifest_data["total_size_chars"],
    )

    return {
        "current_stage": "directory_inventory",
        "state_machine": sm,
        "status": "ok",
    }


async def _run_skill_stage(
    skill_dir: str,
    state: ReviewAssistState,
    config: RunnableConfig,
    target_stage: SMState,
    stage_description: str,
    upstream_artifact_keys: list[str] | None = None,
    inline_override: str | None = None,
    skip_transition: bool = False,
    model_override: str | None = None,
    tools_override: list[str] | None = None,
) -> dict[str, Any]:
    """Execute a single skill stage via SubagentExecutor.

    Shared pattern for all 3 stages. Loads skill, builds config, executes,
    transitions state machine, and records results.

    Retries on tool-call JSON formatting errors (up to 2 retries) with
    degraded-output fallback on total failure.

    inline_override replaces the inline_file_context from state entirely,
    enabling per-batch file content injection in the evidence_curator.

    skip_transition prevents state machine transition — used by batched
    evidence_curator so only the final aggregation triggers the transition.

    model_override: if set, uses this model instead of the default. Routine stages
    should leave this unset so subagents stay aligned with the primary router.

    tools_override: if set, uses these tools instead of the default
    ["read_file", "ls", "write_file"]. Used for gap-specialist to restrict
    to write_file-only (all content is inline, tool calls waste turns).
    """
    skill_prompt = _load_review_skill(skill_dir)
    context = _build_context(state)
    context["current_stage"] = target_stage.value

    # Resolve upstream artifacts from state machine
    upstream: dict[str, str] | None = None
    sm = state.get("state_machine")
    if sm and upstream_artifact_keys:
        upstream = {}
        for key in upstream_artifact_keys:
            path = sm.artifacts.get(key)
            if path:
                upstream[key] = path

    prompt_stage_data = _compact_stage_data_for_prompt(target_stage, state.get("stage_data", {}))
    task_prompt = _build_task_prompt(
        skill_prompt, context, stage_description, upstream,
        inline_file_context=state.get("inline_file_context", ""),
        inline_override=inline_override,
        stage_data=prompt_stage_data,
    )

    cfg = _build_subagent_config(skill_dir, skill_prompt, model_override=model_override, tools_override=tools_override)

    last_error = None
    last_result = None

    for attempt in range(1, _MAX_RETRIES + 1):
        executor = SubagentExecutor(
            config=cfg,
            tools=list(SUBAGENT_TOOLS),
            parent_model=config.get("metadata", {}).get("model_name") if config else None,
            sandbox_state=state.get("sandbox"),
            thread_data=state.get("thread_data"),
            thread_id=config.get("configurable", {}).get("thread_id") if config else None,
            trace_id=f"{context['review_session_id']}-{skill_dir}",
        )

        logger.info("Executing %s via SubagentExecutor._aexecute() (attempt %d/%d)", skill_dir, attempt, _MAX_RETRIES)
        result = await executor._aexecute(task_prompt)

        result_status = result.status.value if hasattr(result.status, "value") else str(result.status)
        result_text = str(result.result or "")
        result_error = str(result.error or "")

        # Check for tool-call JSON formatting errors
        combined = f"{result_text} {result_error}".lower()
        is_tool_json_error = any(pattern.lower() in combined for pattern in _TOOL_JSON_ERROR_PATTERNS)

        if is_tool_json_error and attempt < _MAX_RETRIES:
            logger.warning(
                "%s attempt %d/%d: tool-call JSON error, retrying. Error: %s",
                skill_dir, attempt, _MAX_RETRIES, result_error or result_text[:200],
            )
            last_error = result_error or result_text
            continue

        if is_tool_json_error and attempt == _MAX_RETRIES:
            logger.error(
                "%s: all %d attempts failed with tool-call JSON error. "
                "Returning degraded placeholder output.",
                skill_dir, _MAX_RETRIES,
            )
            # Transition retry exhaustion to a valid next state (skip for batch calls).
            if sm and not skip_transition:
                exhausted_state = (
                    SMState.BLOCKED
                    if sm.current_state == SMState.GAP_ANALYSIS_DONE
                    else SMState.HUMAN_GATE_PENDING
                )
                sm.transition(
                    exhausted_state,
                    reason=f"{skill_dir}: all retries exhausted (model tool-call JSON error)",
                )

            stage_result = {
                "status": "degraded",
                "result": json.dumps({
                    "model_error": True,
                    "error_type": "tool_call_json_formatting",
                    "attempts": _MAX_RETRIES,
                    "last_error": str(last_error or result_error)[:500],
                    "stage": target_stage.value,
                    "human_gate_note": "Stage output could not be produced due to model tool-call JSON formatting errors. "
                                       "Review the inline analysis text below and manually assemble the output.",
                }, ensure_ascii=False),
                "error": f"Model tool-call JSON error after {_MAX_RETRIES} retries",
                "stage": target_stage.value,
            }

            return {
                "current_stage": target_stage.value,
                "stage_result": stage_result,
                "stage_results": stage_result,
                "state_machine": sm,
                "status": "degraded",
            }

        # Success or non-JSON error — use this result
        last_result = result
        last_error = result_error
        break

    result = last_result
    result_status = result.status.value if hasattr(result.status, "value") else str(result.status)

    # ── P-4: Save raw agent output BEFORE any parsing ───────────────────────────
    raw_text = str(result.result or "")
    raw_output_path: str | None = None
    if raw_text and sm and not skip_transition:
        raw_filename = f"{target_stage.value}_raw_output.txt"
        try:
            raw_path = Path(sm.artifact_root) / raw_filename
            raw_path.write_text(raw_text, encoding="utf-8")
            raw_output_path = str(raw_path)
            logger.info("Saved raw agent output: %s (%d chars)", raw_filename, len(raw_text))
        except Exception as e:
            logger.warning("Failed to save raw output for %s: %s", target_stage.value, e)

    # ── Extract structured JSON from agent response text ──────────────────────
    # The model often outputs JSON in text form (code blocks or raw) instead of
    # calling write_file. Extract it and persist directly via Python I/O.
    extraction_metadata = {
        "raw_output_size": len(raw_text),
        "raw_output_path": raw_output_path,
        "parse_success": False,
        "json_repair_applied": False,
        "repair_confidence": None,
        "parse_error": None,
        "candidate_count": None,
        "atomic_observation_count": None,
        "finding_cluster_count": None,
        "extraction_strategy": None,
        "schema_validation_result": None,
        "warning_flags": [],
        "diagnostic_classification": None,
        "write_method": "node_function",
        "write_status": "pending",
        "artifact_path": None,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    extracted_json, extraction_details = _extract_stage_json_from_text(raw_text, target_stage)
    extraction_metadata.update(extraction_details)
    validation_result = extraction_metadata.get("schema_validation_result") or {}
    extraction_metadata["atomic_observation_count"] = validation_result.get("atomic_observation_count")
    extraction_metadata["finding_cluster_count"] = validation_result.get("finding_cluster_count")
    artifact_paths: list[str] = []

    # Large-family Logic QA often follows the skill instruction by writing
    # review_report.json via write_file, then returns prose instead of JSON.
    # Validate that artifact before falling back to the guard skeleton.
    if extracted_json is None and sm and not skip_transition:
        artifact_json, artifact_details = _load_valid_stage_artifact(sm.artifact_root, target_stage)
        if artifact_json is not None:
            extracted_json = artifact_json
            extraction_metadata["parse_success"] = True
            extraction_metadata["extraction_strategy"] = "existing_stage_artifact"
            extraction_metadata["schema_validation_result"] = artifact_details["schema_validation_result"]
            extraction_metadata["warning_flags"] = list(extraction_metadata.get("warning_flags") or []) + [
                "final_text_not_json_existing_artifact_used"
            ]
            extraction_metadata["write_status"] = "existing_artifact_validated"
            extraction_metadata["artifact_path"] = artifact_details["artifact_path"]
            extraction_metadata["parse_error"] = None
            extraction_metadata["diagnostic_classification"] = None
        elif artifact_details is not None:
            extraction_metadata["candidate_attempts"] = list(extraction_metadata.get("candidate_attempts") or []) + [
                {"strategy": "existing_stage_artifact", **artifact_details}
            ]

    # ── P-2: JSON repair metadata ──────────────────────────────────────────────
    if extracted_json is not None:
        extraction_metadata["parse_success"] = True
        extraction_metadata["write_status"] = "attempting"
    elif raw_text:
        # Extraction failed — log and prepare guard artifact
        validation = extraction_metadata.get("schema_validation_result") or {}
        extraction_metadata["parse_error"] = "; ".join(validation.get("errors") or ["No parseable JSON found in agent response"])
        extraction_metadata["diagnostic_classification"] = validation.get("classification")
        logger.warning(
            "JSON extraction failed for stage %s (result length=%d chars, first 300 chars: %r)",
            target_stage.value,
            len(raw_text),
            raw_text[:300],
        )

    # ── P-2: Write artifact or guard on failure ────────────────────────────────
    if extracted_json and sm and not skip_transition:
        artifact_root = sm.artifact_root
        # Determine output filename from stage
        output_filename = _stage_output_filename(target_stage)
        if output_filename:
            try:
                path = _write_artifact_json(str(artifact_root), output_filename, extracted_json)
                artifact_paths.append(path)
                # Register artifact in state machine
                artifact_key = output_filename.replace(".json", "")
                sm.record_artifact(artifact_key, path)
                extraction_metadata["write_status"] = "artifacts_written"
                extraction_metadata["artifact_path"] = path
                logger.info("Extracted and persisted JSON artifact: %s", output_filename)
            except Exception as e:
                extraction_metadata["write_status"] = "artifact_write_failed"
                extraction_metadata["parse_error"] = str(e)
                logger.warning("Failed to persist extracted JSON for %s: %s", output_filename, e)

    # ── P-3: Guard artifact on extraction failure ──────────────────────────────
    if extracted_json is None and sm and not skip_transition and target_stage in (
        SMState.GAP_ANALYSIS_DONE, SMState.SEVERITY_SYNTHESIS_DONE,
    ):
        stage_guard_map = {
            SMState.GAP_ANALYSIS_DONE: ("candidate_findings.json", "g_points"),
            SMState.SEVERITY_SYNTHESIS_DONE: ("review_report.json", "severity_signals"),
        }
        guard_fn, guard_key = stage_guard_map.get(target_stage, (None, None))
        if guard_fn:
            guard_data = {
                guard_key: [],
                "note": f"No schema-conformant JSON extracted from {target_stage.value} agent response. See parse_diagnostics.",
                "reviewer_decision": "PENDING",
                "upstream_artifact_missing": True,
                "fallback_method": "inline_state",
                "diagnostic_classification": extraction_metadata.get("diagnostic_classification"),
                "not_zero_findings": True,
            }
            try:
                extraction_metadata["artifact_path"] = str(Path(sm.artifact_root) / guard_fn)
                extraction_metadata["write_status"] = "guard_written"
                path = _write_artifact_json(str(sm.artifact_root), guard_fn, guard_data)
                artifact_paths.append(path)
                sm.record_artifact(guard_fn.replace(".json", ""), path)
                logger.info("Wrote guard artifact (extraction failed): %s", guard_fn)
            except Exception as e:
                extraction_metadata["write_status"] = "guard_failed"
                extraction_metadata["parse_error"] = str(e)
                logger.warning("Failed to write guard artifact %s: %s", guard_fn, e)

    # ── P-4: Write parse diagnostics (always, even on failure) ─────────────────
    if sm and not skip_transition:
        diag_filename = f"{target_stage.value}_parse_diagnostics.json"
        try:
            _write_artifact_json(str(sm.artifact_root), diag_filename, extraction_metadata)
            logger.info("Wrote parse diagnostics: %s", diag_filename)
        except Exception as e:
            logger.warning("Failed to write parse diagnostics: %s", e)

    # ── P-3: Artifact contract check ───────────────────────────────────────────
    contract_required = {
        SMState.EVIDENCE_INVENTORY_DONE: "source_inventory.json",
        SMState.GAP_ANALYSIS_DONE: "candidate_findings.json",
        SMState.SEVERITY_SYNTHESIS_DONE: "review_report.json",
    }
    contract_status = "PASS"
    expected_file = contract_required.get(target_stage)
    if expected_file and not skip_transition and sm:
        expected_path = Path(sm.artifact_root) / expected_file
        if not expected_path.exists():
            contract_status = "STAGE_ARTIFACT_CONTRACT_FAILURE"
            logger.error(
                "ARTIFACT CONTRACT FAILURE: %s missing after %s stage. Expected at %s",
                expected_file, target_stage.value, expected_path,
            )

    # Transition state machine (skip for batch calls — caller handles transition)
    if sm and not skip_transition:
        if result_status == "completed":
            try:
                sm.transition(target_stage, reason=f"{skill_dir} completed successfully")
            except Exception as e:
                logger.warning("State transition failed (non-fatal): %s", e)
        else:
            sm.transition(SMState.BLOCKED, reason=f"{skill_dir} failed: {result.error or result_status}")

    stage_result = {
        "status": result_status,
        "result": result.result,
        "error": result.error,
        "stage": target_stage.value,
        "extracted_json": extracted_json is not None,
        "extracted_data": extracted_json,  # Raw data for batch aggregation
        "artifact_paths": artifact_paths,
        "artifact_contract": contract_status,
        "extraction_metadata": extraction_metadata,
    }

    # D2: build stage_data update for inline handoff to downstream stages
    stage_data_update = {}
    if extracted_json and not skip_transition:
        stage_key = target_stage.value
        # Compact: for source_inventory, strip verbose excerpt_preview to save context
        if "source_inventory" in extracted_json:
            compact = json.loads(json.dumps(extracted_json))  # deep copy
            for entry in compact.get("source_inventory", []):
                entry.pop("excerpt_preview", None)
                entry.pop("rationale", None)
            stage_data_update[stage_key] = compact
        else:
            stage_data_update[stage_key] = extracted_json

    return {
        "current_stage": target_stage.value,
        "stage_result": stage_result,
        "stage_results": stage_result,
        "state_machine": sm,
        "status": "blocked" if sm and sm.is_blocked() else "ok",
        "stage_data": stage_data_update,
    }


async def node_evidence_curator(state: ReviewAssistState, config: RunnableConfig) -> dict[str, Any]:
    """Stage 1: Evidence Artifact Curator — batched processing for reliable coverage.

    Reads files from input_root in batches of _BATCH_SIZE (5). Each batch gets
    its own SubagentExecutor call with only that batch's file content inline.
    Results are aggregated into a single source_inventory.json covering all files.

    This fixes the 1/20 coverage gap: instead of one giant prompt that overflows
    the model's token budget, we process 4 batches of 5 files each.
    """
    sm = state.get("state_machine")
    input_root = Path(state.get("input_root", ""))
    artifact_root = Path(state.get("artifact_root", "/tmp"))

    # Read all files
    all_files = _read_input_files(input_root)
    file_names = sorted(all_files.keys())
    total_files = len(file_names)

    if total_files == 0:
        logger.warning("Evidence curator: no files found at %s", input_root)
        sm.transition(SMState.BLOCKED, reason="No input files found")
        return {
            "current_stage": SMState.EVIDENCE_INVENTORY_DONE.value,
            "stage_result": {"status": "blocked", "error": "No input files"},
            "state_machine": sm,
            "status": "blocked",
        }

    # Split into batches
    batches = []
    for i in range(0, total_files, _BATCH_SIZE):
        batch_names = file_names[i:i + _BATCH_SIZE]
        batch_files = {name: all_files[name] for name in batch_names}
        batches.append((batch_names, batch_files))

    total_batches = len(batches)
    logger.info(
        "Evidence curator: %d files in %d batches (batch size=%d)",
        total_files, total_batches, _BATCH_SIZE,
    )

    # Process each batch
    all_entries: list[dict] = []
    batch_results: list[dict] = []
    global_idx = 1

    for batch_num, (batch_names, batch_files) in enumerate(batches, 1):
        batch_inline = _build_inline_for_batch(batch_files, batch_num, total_batches)

        batch_desc = (
            f"BATCH {batch_num}/{total_batches}: Analyze the {len(batch_files)} files listed above. "
            f"Output a single JSON object in a ```json code block at the very end. "
            f"Include a source_inventory array with one entry per file. "
            f"For each file include: file_id (use S-{global_idx:03d}..S-{global_idx + len(batch_files) - 1:03d}), "
            f"relative_path (filename), character_count, evidence_depth "
            f"(PRIMARY/SECONDARY/TERTIARY/INDIRECT), excerpt_quality (verbatim/paraphrased/synthetic), "
            f"document_type, flags (array), and rationale (one sentence). "
            f"Output format: {{\"source_inventory\": [{{...}}, ...], \"batch\": {batch_num}}}. "
            f"Be thorough but concise in rationales. "
            f"REMEMBER: Output ONLY the JSON code block — no explanation after it."
        )

        logger.info("Evidence curator batch %d/%d: %d files", batch_num, total_batches, len(batch_files))

        batch_result = await _run_skill_stage(
            skill_dir=SKILL_EVIDENCE_CURATOR,
            state=state,
            config=config,
            target_stage=SMState.EVIDENCE_INVENTORY_DONE,
            stage_description=batch_desc,
            inline_override=batch_inline,
            skip_transition=True,
        )

        batch_results.append({
            "batch_num": batch_num,
            "files": batch_names,
            "status": batch_result.get("status"),
        })

        # Extract entries from this batch — use returned extracted_data when available
        stage_result = batch_result.get("stage_result", {})
        extracted = stage_result.get("extracted_data")
        if not extracted:
            # Fallback: re-extract from result text
            result_text = str(stage_result.get("result", ""))
            extracted = _extract_json_from_text(result_text)

        if extracted and "source_inventory" in extracted:
            entries = extracted["source_inventory"]
            if isinstance(entries, list):
                # Renumber to global indices
                for entry in entries:
                    entry["file_id"] = f"S-{global_idx:03d}"
                    global_idx += 1
                all_entries.extend(entries)
                logger.info(
                    "Batch %d/%d: extracted %d entries (total: %d/%d)",
                    batch_num, total_batches, len(entries), len(all_entries), total_files,
                )
            else:
                logger.warning("Batch %d: source_inventory is not a list (type=%s), skipping", batch_num, type(entries).__name__)
        else:
            logger.warning(
                "Batch %d: no source_inventory found in output. Keys: %s, raw_len=%d",
                batch_num,
                list(extracted.keys()) if extracted else "NONE",
                len(str(stage_result.get("result", ""))),
            )

    # Aggregate and write final source_inventory.json
    coverage_pct = len(all_entries) / total_files * 100 if total_files > 0 else 0
    logger.info(
        "Evidence curator aggregation: %d/%d entries (%.0f%%) across %d batches",
        len(all_entries), total_files, coverage_pct, total_batches,
    )

    final_inventory = {
        "schema_name": "cer_review_source_inventory",
        "schema_version": "v1",
        "project_id": state.get("project_id", ""),
        "review_session_id": state.get("review_session_id", ""),
        "reviewer_decision": "PENDING",
        "source_inventory": all_entries,
        "batch_summary": {
            "total_batches": total_batches,
            "total_files": total_files,
            "files_covered": len(all_entries),
            "coverage_pct": round(coverage_pct, 1),
        },
    }

    inv_path = _write_artifact_json(str(artifact_root), "source_inventory.json", final_inventory)
    sm.record_artifact("source_inventory", inv_path)

    # Transition state machine (only if not already at target from a prior run)
    if sm.current_state != SMState.EVIDENCE_INVENTORY_DONE:
        if coverage_pct >= 75:
            sm.transition(SMState.EVIDENCE_INVENTORY_DONE, reason=f"Evidence curator: {len(all_entries)}/{total_files} files covered")
            final_status = "completed"
        elif coverage_pct > 0:
            sm.transition(SMState.EVIDENCE_INVENTORY_DONE, reason=f"Evidence curator partial: {len(all_entries)}/{total_files} files")
            final_status = "completed"
        else:
            sm.transition(SMState.BLOCKED, reason="Evidence curator: 0 files covered")
            final_status = "blocked"
    else:
        final_status = "completed"

    # D2: build compact stage_data for downstream inline handoff
    compact_inventory = json.loads(json.dumps(final_inventory))  # deep copy
    for entry in compact_inventory.get("source_inventory", []):
        entry.pop("excerpt_preview", None)
        entry.pop("rationale", None)

    return {
        "current_stage": SMState.EVIDENCE_INVENTORY_DONE.value,
        "stage_result": {
            "status": final_status,
            "result": json.dumps(final_inventory, ensure_ascii=False),
            "stage": SMState.EVIDENCE_INVENTORY_DONE.value,
            "batch_results": batch_results,
            "coverage_pct": coverage_pct,
            "total_entries": len(all_entries),
        },
        "stage_results": {
            "status": final_status,
            "stage": SMState.EVIDENCE_INVENTORY_DONE.value,
            "batch_results": batch_results,
        },
        "state_machine": sm,
        "status": "ok" if final_status == "completed" else "blocked",
        "stage_data": {SMState.EVIDENCE_INVENTORY_DONE.value: compact_inventory},
    }


async def node_gap_specialist(state: ReviewAssistState, config: RunnableConfig) -> dict[str, Any]:
    """Stage 2: Gap Specialist — produce layered discovery artifacts.

    The subagent is still the native Gap Specialist stage, but its model output is
    now a lightweight atomic_observations shard payload. The harness then builds
    finding_clusters and concise candidate_findings deterministically from the
    parsed AO ids, keeping exhaustive discovery separate from report candidates.
    """
    sm = state.get("state_machine")
    if sm is None:
        return {
            "current_stage": SMState.GAP_ANALYSIS_DONE.value,
            "stage_result": {"status": "blocked", "error": "state_machine missing"},
            "status": "blocked",
        }

    skill_prompt = _load_review_skill(SKILL_GAP_SPECIALIST)
    context = _build_context(state)
    context["current_stage"] = SMState.GAP_ANALYSIS_DONE.value
    family = _resolve_family_name(state, config)
    input_root = Path(state.get("input_root", ""))
    all_shards = _build_gap_shards(input_root, family)
    shards, input_reduction = _select_gap_shards_for_ao(all_shards)
    shard_diagnostics: list[dict[str, Any]] = []
    shard_errors: list[dict[str, Any]] = []
    atomic_observations: list[dict[str, Any]] = []
    shard_status_doc = _initial_ao_shard_status(
        project_id=state.get("project_id", ""),
        review_session_id=state.get("review_session_id", ""),
        family=family,
        shards=shards,
        input_reduction=input_reduction,
    )

    logger.info(
        "Gap Specialist layered mode: %d/%d atomic-observation shards for %s",
        len(shards),
        len(all_shards),
        family,
    )

    if not shards:
        sm.transition(SMState.BLOCKED, reason="Gap Specialist: no source text shards available")
        return {
            "current_stage": SMState.GAP_ANALYSIS_DONE.value,
            "stage_result": {"status": "blocked", "error": "no source text shards"},
            "state_machine": sm,
            "status": "blocked",
        }

    shard_status_path = _write_ao_shard_status(sm.artifact_root, shard_status_doc)
    sm.record_artifact("ao_shard_status", shard_status_path)

    global_idx = 1
    for shard_number, shard in enumerate(shards, 1):
        raw_observations: list[dict[str, Any]] = []
        diagnostics: dict[str, Any] = {}
        valid = False
        for attempt in range(1, _AO_SHARD_MAX_ATTEMPTS + 1):
            _update_ao_shard_status(shard_status_doc, shard_id=shard["shard_id"], status="running", attempt=attempt)
            _write_ao_shard_status(sm.artifact_root, shard_status_doc)
            raw_observations, diagnostics = await _run_gap_atomic_shard(
                shard=shard,
                state=state,
                config=config,
                skill_prompt=skill_prompt,
                context=context,
                shard_number=shard_number,
                total_shards=len(shards),
                attempt=attempt,
            )
            diagnostics["attempt"] = attempt
            valid = diagnostics.get("validation", {}).get("valid") is True
            if valid:
                break
            if attempt < _AO_SHARD_MAX_ATTEMPTS:
                _update_ao_shard_status(
                    shard_status_doc,
                    shard_id=shard["shard_id"],
                    status="retrying",
                    attempt=attempt,
                    atomic_observation_count=0,
                    error=diagnostics.get("validation", {}).get("errors") or diagnostics.get("error"),
                )
                _write_ao_shard_status(sm.artifact_root, shard_status_doc)
        shard_diagnostics.append(diagnostics)
        if not valid:
            shard_errors.append({
                "shard_id": shard["shard_id"],
                "source_file": shard["source_file"],
                "section": shard["section"],
                "error": diagnostics.get("validation", {}).get("errors") or diagnostics.get("error"),
            })
            _update_ao_shard_status(
                shard_status_doc,
                shard_id=shard["shard_id"],
                status="failed",
                attempt=_AO_SHARD_MAX_ATTEMPTS,
                atomic_observation_count=0,
                error=shard_errors[-1]["error"],
            )
            _write_ao_shard_status(sm.artifact_root, shard_status_doc)
            if len(shard_errors) > _AO_MAX_SHARD_ERRORS:
                break
            continue
        shard_ao_count = 0
        for raw in raw_observations:
            normalized = _normalize_atomic_observation(raw, shard, global_idx)
            if normalized["observation"]:
                atomic_observations.append(normalized)
                shard_ao_count += 1
                global_idx += 1
        _update_ao_shard_status(
            shard_status_doc,
            shard_id=shard["shard_id"],
            status="completed",
            attempt=diagnostics.get("attempt"),
            atomic_observation_count=shard_ao_count,
        )
        _write_ao_shard_status(sm.artifact_root, shard_status_doc)

    source_inventory_ref = sm.artifacts.get("source_inventory")
    layered_doc = _build_gap_layers_from_atomic(
        atomic_observations,
        project_id=state.get("project_id", ""),
        review_session_id=state.get("review_session_id", ""),
        family=family,
        source_inventory_ref=source_inventory_ref,
        shard_count=len(shards),
        original_shard_count=len(all_shards),
        input_reduction=input_reduction,
        shard_errors=shard_errors,
    )
    validation = _validate_stage_json(layered_doc, SMState.GAP_ANALYSIS_DONE)

    artifact_paths: list[str] = []
    extraction_metadata = {
        "parse_success": validation["valid"],
        "schema_validation_result": validation,
        "candidate_count": validation.get("candidate_count"),
        "atomic_observation_count": validation.get("atomic_observation_count"),
        "finding_cluster_count": validation.get("finding_cluster_count"),
        "diagnostic_classification": validation.get("classification"),
        "write_method": "node_function_layered_gap_specialist",
        "write_status": "pending",
        "shard_count": len(shards),
        "original_shard_count": len(all_shards),
        "input_reduction": input_reduction,
        "shard_errors": len(shard_errors),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    try:
        shard_status_doc["status"] = "completed" if len(shard_errors) <= _AO_MAX_SHARD_ERRORS else "failed"
        shard_status_doc["completed_at"] = datetime.now(timezone.utc).isoformat()
        shard_status_path = _write_ao_shard_status(sm.artifact_root, shard_status_doc)
        ao_path = _write_artifact_json(str(sm.artifact_root), "atomic_observations.json", {
            "schema_name": "cer_review_atomic_observations",
            "schema_version": "v1",
            "project_id": layered_doc["project_id"],
            "review_session_id": layered_doc["review_session_id"],
            "family": family,
            "reviewer_decision": "PENDING",
            "atomic_observations": atomic_observations,
            "summary": {
                "total_atomic_observations": len(atomic_observations),
                "shards_processed": len(shards),
                "original_shards_available": len(all_shards),
                "input_reduction": input_reduction,
                "shard_errors": len(shard_errors),
            },
        })
        fc_path = _write_artifact_json(str(sm.artifact_root), "finding_clusters.json", {
            "schema_name": "cer_review_finding_clusters",
            "schema_version": "v1",
            "project_id": layered_doc["project_id"],
            "review_session_id": layered_doc["review_session_id"],
            "family": family,
            "reviewer_decision": "PENDING",
            "finding_clusters": layered_doc["finding_clusters"],
            "summary": {
                "total_clusters": len(layered_doc["finding_clusters"]),
                "total_atomic_observations": len(atomic_observations),
            },
        })
        cf_path = _write_artifact_json(str(sm.artifact_root), "candidate_findings.json", layered_doc)
        extraction_metadata["write_status"] = "artifacts_written"
        extraction_metadata["artifact_path"] = cf_path
        diag_path = _write_artifact_json(str(sm.artifact_root), "gap_analysis_done_parse_diagnostics.json", {
            **extraction_metadata,
            "shard_diagnostics": shard_diagnostics,
            "ao_shard_status_path": shard_status_path,
        })
        artifact_paths.extend([shard_status_path, ao_path, fc_path, cf_path, diag_path])
        sm.record_artifact("ao_shard_status", shard_status_path)
        sm.record_artifact("atomic_observations", ao_path)
        sm.record_artifact("finding_clusters", fc_path)
        sm.record_artifact("candidate_findings", cf_path)
    except Exception as exc:
        extraction_metadata["write_status"] = "artifact_write_failed"
        extraction_metadata["parse_error"] = str(exc)
        logger.warning("Failed to persist layered gap artifacts: %s", exc)

    if validation["valid"] and len(shard_errors) <= _AO_MAX_SHARD_ERRORS:
        try:
            sm.transition(SMState.GAP_ANALYSIS_DONE, reason="Gap Specialist layered discovery completed")
        except Exception as exc:
            logger.warning("State transition failed (non-fatal): %s", exc)
        result_status = "completed"
    else:
        sm.transition(SMState.BLOCKED, reason="Gap Specialist layered discovery schema/shard failure")
        result_status = "blocked"

    stage_result = {
        "status": result_status,
        "result": json.dumps(layered_doc, ensure_ascii=False),
        "error": None if result_status == "completed" else validation.get("errors") or shard_errors,
        "stage": SMState.GAP_ANALYSIS_DONE.value,
        "extracted_json": validation["valid"],
        "extracted_data": layered_doc,
        "artifact_paths": artifact_paths,
        "artifact_contract": "PASS" if validation["valid"] else "STAGE_ARTIFACT_CONTRACT_FAILURE",
        "extraction_metadata": extraction_metadata,
    }

    return {
        "current_stage": SMState.GAP_ANALYSIS_DONE.value,
        "stage_result": stage_result,
        "stage_results": stage_result,
        "state_machine": sm,
        "status": "ok" if result_status == "completed" else "blocked",
        "stage_data": {SMState.GAP_ANALYSIS_DONE.value: layered_doc} if result_status == "completed" else {},
    }


async def node_logic_qa(state: ReviewAssistState, config: RunnableConfig) -> dict[str, Any]:
    """Stage 3: Logic QA — produce severity_signals.json, human_gate_items.json, review_report.json."""
    return await _run_skill_stage(
        skill_dir=SKILL_LOGIC_QA,
        state=state,
        config=config,
        target_stage=SMState.SEVERITY_SYNTHESIS_DONE,
        stage_description=(
            "Output your results as a single JSON object in a ```json code block at the end of your response. "
            "Use the layered Gap Specialist handoff: atomic_observations are the exhaustive discovery layer, "
            "finding_clusters group AO ids by underlying issue, and candidate_findings are concise cluster-level "
            "report candidates. Do not drop or overwrite the persisted discovery artifacts. "
            "Synthesize severity assessments from finding_clusters and candidate_findings, calibrate against Track C rules, "
            "route CRITICAL/HIGH findings to human_gate_items, and assemble the final review report summary. "
            "Output format: {\"severity_signals\": [...], \"human_gate_items\": [...], "
            "\"reviewer_decision\": \"PENDING\", \"discovery_layer_refs\": {...}}. "
            "All reviewer_decision values MUST be 'PENDING'. No terminal verdicts (PASS/FAIL/APPROVED/REJECTED/CEAR). "
            "Be concise — output only the JSON, no explanation after it."
        ),
        upstream_artifact_keys=["source_inventory", "atomic_observations", "finding_clusters", "candidate_findings"],
        tools_override=[],
    )


async def node_blocked(state: ReviewAssistState, _config: RunnableConfig | None = None) -> dict[str, Any]:
    """Terminal node: pipeline blocked. Records the blocked state."""
    sm = state.get("state_machine")
    if sm:
        sm.append_log({
            "event": "pipeline_blocked",
            "current_stage": state.get("current_stage", ""),
            "stage_result": state.get("stage_result", {}),
        })
    logger.warning("Review Assist pipeline BLOCKED at stage: %s", state.get("current_stage"))
    return {"status": "blocked"}


async def node_feedback_writer(state: ReviewAssistState, _config: RunnableConfig | None = None) -> dict[str, Any]:
    """Weak-coupling Layer 1: Write advisory feedback for Authoring pipeline.

    Extracts findings from stage_data and writes review_feedback/latest.json
    into the artifact root. This is a side-effect-only node — it does not
    mutate the ReviewAssistState. The feedback is advisory-only and is loaded
    by the Authoring pipeline at initialization time.
    """
    from deerflow.runtime.cer_review.feedback_writer import ReviewFeedbackWriter

    artifact_root = state.get("artifact_root")
    if not artifact_root:
        logger.warning("feedback_writer: no artifact_root — skipping")
        return {"status": "skipped", "reason": "no_artifact_root"}

    try:
        writer = ReviewFeedbackWriter(artifact_root)
        stage_data = state.get("stage_data", {})
        project_id = state.get("project_id")
        feedback_path = writer.write_feedback_from_assist_state(stage_data, source_project_id=project_id)
        # P1-3: Generate KB update candidates from high-severity findings
        findings = writer._extract_findings_from_assist(stage_data)
        kb_candidates_path = writer.generate_kb_update_candidates(findings, project_id=project_id or "")
        return {
            "status": "completed",
            "feedback_path": str(feedback_path),
            "feedback_written": True,
            "kb_candidates_path": str(kb_candidates_path) if kb_candidates_path else None,
        }
    except Exception as exc:
        logger.warning("feedback_writer failed (non-fatal): %s", exc)
        return {
            "status": "failed",
            "reason": str(exc),
            "feedback_written": False,
        }


# ── Conditional Routing ─────────────────────────────────────────────────────────


def _route_after_evidence(state: ReviewAssistState) -> Literal["gap_specialist", "blocked"]:
    sm = state.get("state_machine")
    if sm and sm.is_blocked():
        return "blocked"
    stage_result = state.get("stage_result", {})
    if stage_result.get("status") == "completed":
        return "gap_specialist"
    return "blocked"


def _route_after_gap(state: ReviewAssistState) -> Literal["logic_qa", "blocked"]:
    sm = state.get("state_machine")
    if sm and sm.is_blocked():
        return "blocked"
    stage_result = state.get("stage_result", {})
    if stage_result.get("status") == "completed":
        return "logic_qa"
    return "blocked"


def _route_after_logic(state: ReviewAssistState) -> Literal["feedback_writer", "blocked"]:
    sm = state.get("state_machine")
    if sm and sm.is_blocked():
        return "blocked"
    stage_result = state.get("stage_result", {})
    if stage_result.get("status") == "completed":
        # Transition to human_gate_pending before ending
        if sm:
            try:
                sm.transition(SMState.HUMAN_GATE_PENDING, reason="All 3 stages completed")
                sm.append_log({"event": "pipeline_completed", "status": "human_gate_pending"})
            except Exception as e:
                logger.warning("Final state transition failed (non-fatal): %s", e)
        return "feedback_writer"
    return "blocked"


# ── Graph Builder ───────────────────────────────────────────────────────────────


def build_review_assist_graph(config=None) -> StateGraph:
    """Build and compile the 3-stage Review Assist graph.

    Pipeline: directory_inventory -> evidence_curator -> gap_specialist -> logic_qa -> END
    directory_inventory is a deterministic pre-processing node (no LLM).
    evidence_curator processes files in batches of 5 for reliable coverage.
    Any stage failure routes to blocked -> END.

    Registered in langgraph.json as:
        "review_assist": "deerflow.runtime.cer_review.review_assist_lead_agent:build_review_assist_graph"
    """
    builder = StateGraph(ReviewAssistState)

    builder.add_node("directory_inventory", node_directory_inventory)
    builder.add_node("evidence_curator", node_evidence_curator)
    builder.add_node("gap_specialist", node_gap_specialist)
    builder.add_node("logic_qa", node_logic_qa)
    builder.add_node("blocked", node_blocked)
    builder.add_node("feedback_writer", node_feedback_writer)

    builder.set_entry_point("directory_inventory")

    # directory_inventory always proceeds to evidence_curator
    builder.add_edge("directory_inventory", "evidence_curator")

    builder.add_conditional_edges("evidence_curator", _route_after_evidence, {
        "gap_specialist": "gap_specialist",
        "blocked": "blocked",
    })

    builder.add_conditional_edges("gap_specialist", _route_after_gap, {
        "logic_qa": "logic_qa",
        "blocked": "blocked",
    })

    builder.add_conditional_edges("logic_qa", _route_after_logic, {
        "feedback_writer": "feedback_writer",
        "blocked": "blocked",
    })

    builder.add_edge("feedback_writer", END)
    builder.add_edge("blocked", END)

    return builder.compile()


def build_review_quick_scan_graph(config=None) -> StateGraph:
    """Build and compile a lightweight 2-stage Quick-Scan graph.

    Pipeline: directory_inventory -> evidence_curator -> gap_specialist -> quick_scan_feedback_writer -> END
    Skips logic_qa (Stage 3) for speed. Produces advisory feedback with a
    smaller scope — suitable for mid-pipeline Authoring requests.

    Output: review_feedback/quick_scan_latest.json
    """
    builder = StateGraph(ReviewAssistState)

    builder.add_node("directory_inventory", node_directory_inventory)
    builder.add_node("evidence_curator", node_evidence_curator)
    builder.add_node("gap_specialist", node_gap_specialist)
    builder.add_node("blocked", node_blocked)
    builder.add_node("quick_scan_feedback_writer", node_quick_scan_feedback_writer)

    builder.set_entry_point("directory_inventory")
    builder.add_edge("directory_inventory", "evidence_curator")
    builder.add_conditional_edges("evidence_curator", _route_after_evidence, {
        "gap_specialist": "gap_specialist",
        "blocked": "blocked",
    })
    builder.add_conditional_edges("gap_specialist", _route_after_gap_quick_scan, {
        "quick_scan_feedback_writer": "quick_scan_feedback_writer",
        "blocked": "blocked",
    })
    builder.add_edge("quick_scan_feedback_writer", END)
    builder.add_edge("blocked", END)

    return builder.compile()


async def node_quick_scan_feedback_writer(state: ReviewAssistState, _config: RunnableConfig | None = None) -> dict[str, Any]:
    """Write quick-scan advisory feedback.

    Similar to node_feedback_writer but writes to quick_scan_latest.json
    and limits findings to top 5 by severity.
    """
    from deerflow.runtime.cer_review.feedback_writer import ReviewFeedbackWriter

    artifact_root = state.get("artifact_root")
    if not artifact_root:
        return {"status": "skipped", "reason": "no_artifact_root"}

    try:
        writer = ReviewFeedbackWriter(artifact_root)
        stage_data = state.get("stage_data", {})
        findings = writer._extract_findings_from_assist(stage_data)
        # Limit to top 5 by severity
        _SEVERITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "INFORMATIONAL": 4}
        findings = sorted(
            findings,
            key=lambda f: _SEVERITY_ORDER.get(str(f.get("severity", "")).upper(), 99),
        )[:5]
        feedback = writer._build_feedback(findings, source="cer_review_quick_scan", source_project_id=state.get("project_id"))
        # Override output path to quick_scan_latest.json
        feedback_dir = Path(artifact_root) / "review_feedback"
        feedback_dir.mkdir(parents=True, exist_ok=True)
        target = feedback_dir / "quick_scan_latest.json"
        temp = feedback_dir / f".quick_scan_latest.json.tmp.{__import__('uuid').uuid4().hex}"
        with open(temp, "w", encoding="utf-8") as fh:
            json.dump(feedback, fh, indent=2, ensure_ascii=False)
        temp.replace(target)
        return {
            "status": "completed",
            "feedback_path": str(target),
            "findings_count": len(findings),
        }
    except Exception as exc:
        logger.warning("quick_scan_feedback_writer failed (non-fatal): %s", exc)
        return {"status": "failed", "reason": str(exc)}


def _route_after_gap_quick_scan(state: ReviewAssistState) -> Literal["quick_scan_feedback_writer", "blocked"]:
    sm = state.get("state_machine")
    if sm and sm.is_blocked():
        return "blocked"
    stage_result = state.get("stage_result", {})
    if stage_result.get("status") == "completed":
        return "quick_scan_feedback_writer"
    return "blocked"
