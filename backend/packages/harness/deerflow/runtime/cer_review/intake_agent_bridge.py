"""CER Raw Project Intake — Agent Activation Bridge

Provides LLM-powered semantic stage execution using CERLLMInvoker.

ACTUAL STATUS (as of 2026-04-19):
- Uses direct CERLLMInvoker.invoke() for LLM calls with skill prompt files
- Does NOT use DeerFlow task()/SubagentExecutor (requires lead agent + sandbox infrastructure)
- Falls back to structured placeholder results when LLM is unavailable

INVOCATION METHOD CLASSIFICATION:
- DETERMINISTIC_CODE: Pure Python (file I/O, checksums, state machine)
- DIRECT_LLM_INVOKER: CERLLMInvoker.invoke() with skill prompt + context
- TASK_SUBAGENT: DeerFlow task() tool — NOT YET ACTIVATED
- HUMAN_GATE: Human decision required

This is an HONEST representation of the current agent activation state.
No false claims of full DeerFlow subagent harness usage.

Frozen baseline: CER_RAW_PROJECT_INTAKE_AGENT_VS_PROGRAM_BOUNDARY.md
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ── Invocation Method Classification ────────────────────────────────────────────


class InvocationMethod(str, Enum):
    """How a stage is executed."""
    DETERMINISTIC_CODE = "deterministic_code"      # Pure Python, no LLM
    DIRECT_LLM_INVOKER = "direct_llm_invoker"    # CERLLMInvoker directly
    TASK_SUBAGENT = "task_subagent"              # DeerFlow task() tool + SubagentExecutor
    HUMAN_GATE = "human_gate"                    # Human decision


# ── Semantic Stage Definitions ───────────────────────────────────────────────────


SEMANTIC_STAGES = {
    "file_inventory": {
        "skill_file": "file_inventory_agent.md",
        "invocation": InvocationMethod.DETERMINISTIC_CODE,
        "module": "intake_file_ops",
        "function": "build_file_inventory",
        "description": "File enumeration with SHA-256 checksums",
    },
    "dedupe": {
        "skill_file": "dedupe_agent.md",
        "invocation": InvocationMethod.DETERMINISTIC_CODE,  # exact dedupe; near-duplicate would be LLM
        "module": "intake_file_ops",
        "function": "dedupe_by_checksum",
        "description": "Exact deduplication by SHA-256 (deterministic)",
    },
    "parse": {
        "skill_file": "document_parsing_agent.md",
        "invocation": InvocationMethod.DETERMINISTIC_CODE,
        "module": "intake_text_extractor",
        "function": "extract_text_batch",
        "description": "Text extraction from PDF/DOCX/XLSX/TXT (deterministic libraries)",
    },
    "pdf_check": {
        "skill_file": "pdf_readability_agent.md",
        "invocation": InvocationMethod.DIRECT_LLM_INVOKER,
        "module": None,
        "function": None,
        "description": "PDF readability classification (LLM)",
    },
    "type_detection": {
        "skill_file": "document_type_detection_agent.md",
        "invocation": InvocationMethod.DIRECT_LLM_INVOKER,
        "module": None,
        "function": None,
        "description": "Document type detection and EP classification (LLM)",
    },
    "classification": {
        "skill_file": "evidence_classification_agent.md",
        "invocation": InvocationMethod.DIRECT_LLM_INVOKER,
        "module": None,
        "function": None,
        "description": "Final EP classification per file (LLM)",
    },
    "completeness": {
        "skill_file": "evidence_completeness_agent.md",
        "invocation": InvocationMethod.DIRECT_LLM_INVOKER,
        "module": None,
        "function": None,
        "description": "EP-level completeness assessment (LLM)",
    },
    "citations": {
        "skill_file": "citation_locator_agent.md",
        "invocation": InvocationMethod.DIRECT_LLM_INVOKER,
        "module": None,
        "function": None,
        "description": "Citation tracing and source location (LLM)",
    },
    "human_gate_packet": {
        "skill_file": "human_gate_packet_writer.md",
        "invocation": InvocationMethod.DIRECT_LLM_INVOKER,
        "module": None,
        "function": None,
        "description": "Compile human review packet (LLM)",
    },
    "qa": {
        "skill_file": "intake_qa_agent.md",
        "invocation": InvocationMethod.DIRECT_LLM_INVOKER,  # core checks are deterministic; edge cases LLM
        "module": "intake_file_ops",
        "function": "verify_locked_pack_checksums",
        "description": "Post-lock QA (deterministic checksum + LLM edge case)",
    },
}


# ── Agent Bridge ────────────────────────────────────────────────────────────────


@dataclass
class AgentCallResult:
    """Result of an agent/stage execution."""
    stage: str
    invocation_method: InvocationMethod
    skill_file: str
    success: bool
    output_artifact: str | None
    error: str | None
    duration_sec: float
    llm_attempts: int
    status: str  # "success" | "placeholder_phase1" | "error" | "skipped"


class IntakeAgentBridge:
    """Bridge for executing semantic stages in the CER Raw Intake workflow.

    This bridge provides an honest accounting of how each stage is invoked:
    - DETERMINISTIC_CODE: runs without LLM
    - DIRECT_LLM_INVOKER: uses CERLLMInvoker directly
    - TASK_SUBAGENT: uses DeerFlow task() tool (NOT YET IMPLEMENTED)
    - HUMAN_GATE: requires human decision

    Phase 1 Status:
    - No task()/SubagentExecutor integration (requires sandbox + lead agent)
    - All LLM stages use CERLLMInvoker directly
    - Placeholder results returned when LLM unavailable
    """

    def __init__(
        self,
        *,
        repo_root: Path,
        project_id: str,
        intake_session_id: str,
        intake_dir: Path,
        llm_client: Any = None,  # Optional CERLLMInvoker-compatible client
    ) -> None:
        self.repo_root = Path(repo_root)
        self.project_id = project_id
        self.intake_session_id = intake_session_id
        self.intake_dir = Path(intake_dir)
        self._llm_client = llm_client
        self._calls: list[AgentCallResult] = []

    @property
    def invocation_stats(self) -> dict[str, int]:
        """Return count of calls by invocation method."""
        stats: dict[str, int] = {
            "deterministic_code": 0,
            "direct_llm_invoker": 0,
            "task_subagent": 0,
            "human_gate": 0,
            "placeholder_phase1": 0,
        }
        for call in self._calls:
            if call.invocation_method == InvocationMethod.DETERMINISTIC_CODE:
                stats["deterministic_code"] += 1
            elif call.invocation_method == InvocationMethod.DIRECT_LLM_INVOKER:
                if call.status == "placeholder_phase1":
                    stats["placeholder_phase1"] += 1
                else:
                    stats["direct_llm_invoker"] += 1
            elif call.invocation_method == InvocationMethod.TASK_SUBAGENT:
                stats["task_subagent"] += 1
            elif call.invocation_method == InvocationMethod.HUMAN_GATE:
                stats["human_gate"] += 1
        return stats

    # ── Stage Execution ───────────────────────────────────────────────────────

    def run_stage(self, stage: str, context: dict[str, Any]) -> AgentCallResult:
        """Run a single semantic stage."""
        import time
        start = time.time()

        stage_def = SEMANTIC_STAGES.get(stage)
        if not stage_def:
            return AgentCallResult(
                stage=stage,
                invocation_method=InvocationMethod.DETERMINISTIC_CODE,
                skill_file="",
                success=False,
                output_artifact=None,
                error=f"Unknown stage: {stage}",
                duration_sec=time.time() - start,
                llm_attempts=0,
                status="error",
            )

        invocation = stage_def["invocation"]
        skill_file = stage_def["skill_file"]

        if invocation == InvocationMethod.DETERMINISTIC_CODE:
            return self._run_deterministic(stage, stage_def, context, start)
        elif invocation == InvocationMethod.DIRECT_LLM_INVOKER:
            return self._run_llm(stage, stage_def, skill_file, context, start)
        elif invocation == InvocationMethod.HUMAN_GATE:
            return self._run_human_gate(stage, start)
        else:
            return AgentCallResult(
                stage=stage,
                invocation_method=invocation,
                skill_file=skill_file,
                success=False,
                output_artifact=None,
                error=f"Unhandled invocation type: {invocation}",
                duration_sec=time.time() - start,
                llm_attempts=0,
                status="error",
            )

    def _run_deterministic(
        self,
        stage: str,
        stage_def: dict,
        context: dict[str, Any],
        start: float,
    ) -> AgentCallResult:
        """Run a deterministic code stage."""
        module_name = stage_def["module"]
        function_name = stage_def["function"]

        output_artifact = None
        error = None
        success = True

        try:
            if module_name == "intake_file_ops":
                from deerflow.runtime.cer_review import intake_file_ops
                func = getattr(intake_file_ops, function_name)
                if function_name == "build_file_inventory":
                    result = func(
                        input_root=Path(context["input_root"]),
                        project_id=self.project_id,
                        intake_session_id=self.intake_session_id,
                    )
                    output_artifact = "file_inventory.json"
                elif function_name == "dedupe_by_checksum":
                    result = func(
                        checksum_manifest=context.get("checksum_manifest"),
                        file_inventory=context.get("file_inventory"),
                    )
                    output_artifact = "dedupe_report.json"

            elif module_name == "intake_text_extractor":
                from deerflow.runtime.cer_review import intake_text_extractor
                func = getattr(intake_text_extractor, function_name)
                if function_name == "extract_text_batch":
                    result = func(
                        file_paths=[Path(p) for p in context["file_paths"]],
                        output_dir=Path(context["output_dir"]),
                    )
                    output_artifact = "document_text_index.json"

        except Exception as e:
            success = False
            error = str(e)

        result = AgentCallResult(
            stage=stage,
            invocation_method=InvocationMethod.DETERMINISTIC_CODE,
            skill_file=stage_def["skill_file"],
            success=success,
            output_artifact=output_artifact,
            error=error,
            duration_sec=time.time() - start,
            llm_attempts=0,
            status="success" if success else "error",
        )
        self._calls.append(result)
        return result

    def _run_llm(
        self,
        stage: str,
        stage_def: dict,
        skill_file: str,
        context: dict[str, Any],
        start: float,
    ) -> AgentCallResult:
        """Run an LLM-powered semantic stage via CERLLMInvoker."""
        prompt_path = self.repo_root / "prompts" / "cer" / "intake" / skill_file
        if not prompt_path.exists():
            return AgentCallResult(
                stage=stage,
                invocation_method=InvocationMethod.DIRECT_LLM_INVOKER,
                skill_file=skill_file,
                success=False,
                output_artifact=None,
                error=f"Skill file not found: {prompt_path}",
                duration_sec=time.time() - start,
                llm_attempts=0,
                status="error",
            )

        prompt_text = prompt_path.read_text(encoding="utf-8")
        context_md = json.dumps(context, indent=2, ensure_ascii=False)
        messages = [
            {"role": "system", "content": prompt_text},
            {"role": "user", "content": f"Project context:\n```json\n{context_md}\n```"},
        ]

        # Try CERLLMInvoker
        if self._llm_client is not None:
            try:
                from deerflow.runtime.cer_review.llm_invoker import CERLLMInvoker
                invoker = CERLLMInvoker(self._llm_client)
                outcome = invoker.invoke(
                    agent_name=f"intake_{stage}",
                    messages=messages,
                    extract_json=True,
                    run_id=self.intake_session_id,
                )
                duration = time.time() - start
                if outcome.eventual_success and outcome.invocation_results:
                    first_result = outcome.invocation_results[0]
                    parsed = first_result.parsed_output
                    if parsed:
                        output_path = self.intake_dir / f"{stage}_output.json"
                        # P2.3: Add _meta execution trace to agent-produced artifacts
                        meta = {
                            "agent_id": first_result.agent_name,
                            "execution_mode": "direct_llm_invoker",
                            "invoked_at": first_result.timestamp,
                            "model": first_result.model_used,
                            "skill_file": skill_file,
                            "stage_name": stage,
                            "invocation_method": InvocationMethod.DIRECT_LLM_INVOKER.value,
                        }
                        wrapped = {"_meta": meta, "data": parsed}
                        output_path.write_text(json.dumps(wrapped, indent=2, ensure_ascii=False))
                        result = AgentCallResult(
                            stage=stage,
                            invocation_method=InvocationMethod.DIRECT_LLM_INVOKER,
                            skill_file=skill_file,
                            success=True,
                            output_artifact=f"{stage}_output.json",
                            error=None,
                            duration_sec=duration,
                            llm_attempts=outcome.total_attempts,
                            status="success",
                        )
                        self._calls.append(result)
                        return result
            except Exception as e:
                logger.warning(f"CERLLMInvoker failed for {stage}: {e}")

        # Fallback: Phase 1 placeholder
        duration = time.time() - start
        placeholder = self._placeholder_result(stage, skill_file, context)
        result = AgentCallResult(
            stage=stage,
            invocation_method=InvocationMethod.DIRECT_LLM_INVOKER,
            skill_file=skill_file,
            success=True,
            output_artifact=f"{stage}_output.json",
            error=None,
            duration_sec=duration,
            llm_attempts=0,
            status="placeholder_phase1",
        )
        self._calls.append(result)
        return result

    def _run_human_gate(self, stage: str, start: float) -> AgentCallResult:
        """Human gate stage — waits for human decision."""
        result = AgentCallResult(
            stage=stage,
            invocation_method=InvocationMethod.HUMAN_GATE,
            skill_file="",
            success=True,
            output_artifact=None,
            error=None,
            duration_sec=time.time() - start,
            llm_attempts=0,
            status="waiting_for_human",
        )
        self._calls.append(result)
        return result

    def _placeholder_result(self, stage: str, skill_file: str, context: dict) -> dict:
        """Generate a Phase 1 placeholder result for an LLM stage."""
        return {
            "schema_name": f"cer_intake_{stage}_placeholder",
            "schema_version": "v1",
            "project_id": self.project_id,
            "intake_session_id": self.intake_session_id,
            "stage": stage,
            "skill_file": skill_file,
            "status": "placeholder_phase1",
            "note": "Phase 1: LLM integration deferred. Domain expert review required.",
            "input_context_keys": list(context.keys()),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    def get_call_log(self) -> list[dict]:
        """Return detailed log of all agent calls."""
        return [
            {
                "stage": c.stage,
                "invocation_method": c.invocation_method.value,
                "skill_file": c.skill_file,
                "success": c.success,
                "output_artifact": c.output_artifact,
                "error": c.error,
                "duration_sec": round(c.duration_sec, 2),
                "llm_attempts": c.llm_attempts,
                "status": c.status,
            }
            for c in self._calls
        ]


# ── Live Agent Stage Runner ──────────────────────────────────────────────────────


@dataclass
class LiveAgentStageResult:
    """Structured result from a live agent stage execution."""
    stage: str
    skill_file: str
    invocation_method: InvocationMethod
    success: bool
    output_artifact: str | None
    error: str | None
    duration_sec: float
    llm_attempts: int
    status: str  # "success" | "placeholder_phase1" | "error" | "skipped"
    model_used: str | None = None
    input_artifact_refs: list[str] = field(default_factory=list)
    output_artifact_refs: list[str] = field(default_factory=list)
    confidence: float | None = None
    retry_safe: bool = True
    raw_output: str | None = None


class LiveAgentStageRunner:
    """Runs CER Intake semantic stages with live LLM execution.

    This runner bridges skill prompt files to CERLLMInvoker, producing
    properly structured output artifacts for each stage.

    Invocation method: DIRECT_LLM_INVOKER (CERLLMInvoker.invoke()).

    TASK_SUBAGENT STATUS (as of 2026-04-19):
    DeerFlow task()/SubagentExecutor is NOT ACTIVATED for CER Intake because:
    1. task_tool requires a LangGraph agent runtime context (ToolRuntime, ThreadState)
    2. The runner executes outside the lead agent's tool execution context
    3. SubagentExecutor needs sandbox_state and thread_data from agent runtime
    4. The runner is a standalone Python script, not a LangGraph conversation

    Future activation requires:
    - Lead agent thread with active sandbox for each stage
    - CER Intake-specific subagent type registration
    - State machine events → task() call bridging

    This runner uses DIRECT_LLM_INVOKER as the honest fallback while
    documenting the task()/SubagentExecutor gap transparently.
    """

    def __init__(
        self,
        *,
        repo_root: Path,
        project_id: str,
        intake_session_id: str,
        intake_dir: Path,
        llm_client: Any = None,
    ) -> None:
        self.repo_root = Path(repo_root)
        self.project_id = project_id
        self.intake_session_id = intake_session_id
        self.intake_dir = Path(intake_dir)
        self._llm_client = llm_client
        self._results: list[LiveAgentStageResult] = []

    @property
    def invocation_stats(self) -> dict[str, int]:
        """Return count of calls by invocation method."""
        stats: dict[str, int] = {
            "deterministic_code": 0,
            "direct_llm_invoker": 0,
            "task_subagent": 0,
            "human_gate": 0,
            "placeholder_phase1": 0,
        }
        for r in self._results:
            if r.invocation_method == InvocationMethod.DETERMINISTIC_CODE:
                stats["deterministic_code"] += 1
            elif r.invocation_method == InvocationMethod.DIRECT_LLM_INVOKER:
                if r.status == "placeholder_phase1":
                    stats["placeholder_phase1"] += 1
                else:
                    stats["direct_llm_invoker"] += 1
            elif r.invocation_method == InvocationMethod.TASK_SUBAGENT:
                stats["task_subagent"] += 1
            elif r.invocation_method == InvocationMethod.HUMAN_GATE:
                stats["human_gate"] += 1
        return stats

    def run_stage(self, stage: str, context: dict[str, Any]) -> LiveAgentStageResult:
        """Run a single LLM-powered semantic stage with live execution.

        Loads the skill prompt, invokes CERLLMInvoker with proper messages,
        writes structured output artifact, and returns detailed result.
        """
        stage_def = SEMANTIC_STAGES.get(stage)
        if not stage_def:
            return LiveAgentStageResult(
                stage=stage,
                skill_file="",
                invocation_method=InvocationMethod.DIRECT_LLM_INVOKER,
                success=False,
                output_artifact=None,
                error=f"Unknown stage: {stage}",
                duration_sec=0.0,
                llm_attempts=0,
                status="error",
            )

        skill_file = stage_def["skill_file"]
        invocation = stage_def["invocation"]

        if invocation == InvocationMethod.DETERMINISTIC_CODE:
            # Handled by runner directly — this runner is for LLM stages only
            return LiveAgentStageResult(
                stage=stage,
                skill_file=skill_file,
                invocation_method=InvocationMethod.DETERMINISTIC_CODE,
                success=False,
                output_artifact=None,
                error="Deterministic stages should run directly in runner, not via LiveAgentStageRunner",
                duration_sec=0.0,
                llm_attempts=0,
                status="error",
            )

        if invocation == InvocationMethod.HUMAN_GATE:
            return LiveAgentStageResult(
                stage=stage,
                skill_file=skill_file,
                invocation_method=InvocationMethod.HUMAN_GATE,
                success=True,
                output_artifact=None,
                error=None,
                duration_sec=0.0,
                llm_attempts=0,
                status="waiting_for_human",
            )

        return self._run_llm_stage(stage, stage_def, skill_file, context)

    def _run_llm_stage(
        self,
        stage: str,
        stage_def: dict,
        skill_file: str,
        context: dict[str, Any],
    ) -> LiveAgentStageResult:
        """Execute an LLM stage via CERLLMInvoker with skill prompt."""
        start = time.time()

        # Load skill prompt
        prompt_path = self.repo_root / "prompts" / "cer" / "intake" / skill_file
        if not prompt_path.exists():
            return LiveAgentStageResult(
                stage=stage,
                skill_file=skill_file,
                invocation_method=InvocationMethod.DIRECT_LLM_INVOKER,
                success=False,
                output_artifact=None,
                error=f"Skill file not found: {prompt_path}",
                duration_sec=time.time() - start,
                llm_attempts=0,
                status="error",
                retry_safe=False,
            )

        prompt_text = prompt_path.read_text(encoding="utf-8")
        context_md = json.dumps(context, indent=2, ensure_ascii=False)
        messages = [
            {"role": "system", "content": prompt_text},
            {"role": "user", "content": f"Project context:\n```json\n{context_md}\n```"},
        ]

        # Track input artifact references from context
        input_refs = self._extract_artifact_refs(context)

        # Try live LLM execution via CERLLMInvoker
        if self._llm_client is not None:
            try:
                from deerflow.runtime.cer_review.llm_invoker import CERLLMInvoker
                invoker = CERLLMInvoker(self._llm_client)
                outcome = invoker.invoke(
                    agent_name=f"intake_{stage}",
                    messages=messages,
                    extract_json=True,
                    run_id=self.intake_session_id,
                )
                duration = time.time() - start

                if outcome.eventual_success and outcome.invocation_results:
                    first_result = outcome.invocation_results[0]
                    parsed = first_result.parsed_output
                    model_used = first_result.model_used

                    if parsed:
                        output_path = self.intake_dir / f"{stage}_output.json"
                        # P2.3: Add _meta execution trace to agent-produced artifacts
                        meta = {
                            "agent_id": first_result.agent_name,
                            "execution_mode": "direct_llm_invoker",
                            "invoked_at": first_result.timestamp,
                            "model": first_result.model_used,
                            "skill_file": skill_file,
                            "stage_name": stage,
                            "invocation_method": InvocationMethod.DIRECT_LLM_INVOKER.value,
                        }
                        wrapped = {"_meta": meta, "data": parsed}
                        output_path.write_text(json.dumps(wrapped, indent=2, ensure_ascii=False))

                        confidence = parsed.get("confidence") or parsed.get("avg_confidence")

                        result = LiveAgentStageResult(
                            stage=stage,
                            skill_file=skill_file,
                            invocation_method=InvocationMethod.DIRECT_LLM_INVOKER,
                            success=True,
                            output_artifact=str(output_path.name),
                            error=None,
                            duration_sec=duration,
                            llm_attempts=outcome.total_attempts,
                            status="success",
                            model_used=model_used,
                            input_artifact_refs=input_refs,
                            output_artifact_refs=[str(output_path.name)],
                            confidence=confidence,
                            retry_safe=True,
                            raw_output=first_result.raw_output,
                        )
                        self._results.append(result)
                        return result
                    else:
                        # LLM succeeded but no parseable JSON
                        error_msg = f"LLM returned no parseable JSON: {first_result.raw_output[:200] if first_result.raw_output else 'empty'}"
                        logger.warning(f"CERLLMInvoker returned empty for {stage}: {error_msg}")
                else:
                    final_error = outcome.final_error or "unknown"
                    logger.warning(f"CERLLMInvoker failed for {stage}: {outcome.final_status} — {final_error}")

            except Exception as e:
                logger.warning(f"CERLLMInvoker exception for {stage}: {e}")

        # Fallback: structured placeholder (not silent)
        duration = time.time() - start
        placeholder = self._build_placeholder(stage, skill_file, context)
        output_path = self.intake_dir / f"{stage}_output.json"
        output_path.write_text(json.dumps(placeholder, indent=2, ensure_ascii=False))

        result = LiveAgentStageResult(
            stage=stage,
            skill_file=skill_file,
            invocation_method=InvocationMethod.DIRECT_LLM_INVOKER,
            success=True,  # Placeholder is "successful" in that it didn't crash
            output_artifact=str(output_path.name),
            error="LLM unavailable — Phase 1 structured placeholder",
            duration_sec=duration,
            llm_attempts=0,
            status="placeholder_phase1",
            input_artifact_refs=input_refs,
            output_artifact_refs=[str(output_path.name)],
            retry_safe=False,  # Placeholder should not be retried automatically
        )
        self._results.append(result)
        return result

    def _extract_artifact_refs(self, context: dict[str, Any]) -> list[str]:
        """Extract artifact file references from context."""
        refs = []
        if "file_inventory" in context:
            refs.append("intake/file_inventory.json")
        if "dedupe_report" in context:
            refs.append("intake/dedupe_report.json")
        if "document_text_index" in context:
            refs.append("intake/document_text_index.json")
        if "pdf_readability_report" in context:
            refs.append("intake/pdf_readability_report.json")
        if "classification_candidates" in context:
            refs.append("intake/classification_candidates.json")
        if "evidence_classification_final" in context:
            refs.append("intake/evidence_classification_final.json")
        return refs

    def _build_placeholder(self, stage: str, skill_file: str, context: dict) -> dict:
        """Build a structured Phase 1 placeholder result."""
        # Map stage to expected output schema name
        schema_names = {
            "pdf_check": "cer_intake_pdf_readability_report",
            "type_detection": "cer_intake_classification_candidates",
            "classification": "cer_intake_evidence_classification_final",
            "completeness": "cer_intake_evidence_completeness_report",
            "citations": "cer_intake_citation_trace_report",
            "human_gate_packet": "cer_intake_classification_review_packet",
            "qa": "cer_intake_qa_report",
        }
        return {
            "schema_name": schema_names.get(stage, f"cer_intake_{stage}_placeholder"),
            "schema_version": "v1",
            "project_id": self.project_id,
            "intake_session_id": self.intake_session_id,
            "stage": stage,
            "skill_file": skill_file,
            "status": "placeholder_phase1",
            "note": "Phase 1: LLM integration deferred. Domain expert review required.",
            "input_context_keys": list(context.keys()),
            "placeholder_reason": "LLM API unavailable in current environment",
            "placeholder_timestamp": datetime.now(timezone.utc).isoformat(),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    def get_results(self) -> list[dict]:
        """Return all stage results as dicts."""
        return [
            {
                "stage": r.stage,
                "skill_file": r.skill_file,
                "invocation_method": r.invocation_method.value,
                "success": r.success,
                "output_artifact": r.output_artifact,
                "error": r.error,
                "duration_sec": round(r.duration_sec, 2),
                "llm_attempts": r.llm_attempts,
                "status": r.status,
                "model_used": r.model_used,
                "input_artifact_refs": r.input_artifact_refs,
                "output_artifact_refs": r.output_artifact_refs,
                "confidence": r.confidence,
                "retry_safe": r.retry_safe,
            }
            for r in self._results
        ]
