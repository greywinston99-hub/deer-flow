#!/usr/bin/env python3
"""Executable entrypoint for the CER Raw Project Intake workflow runner.

Usage:
    python cer_raw_intake_runner.py --project-id CER-PJT-XXXX \
        --input-root artifacts/cer/CER-PJT-XXXX/input \
        --project-profile artifacts/cer/CER-PJT-XXXX/project_profile.yaml \
        --artifact-root artifacts/cer/CER-PJT-XXXX
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
HARNESS_ROOT = REPO_ROOT / "backend" / "packages" / "harness"
if str(HARNESS_ROOT) not in sys.path:
    sys.path.insert(0, str(HARNESS_ROOT))

from deerflow.runtime.cer_review.intake_state_machine import (
    IntakeStateMachine,
    IntakeState,
    InvalidTransitionError,
)
from deerflow.runtime.cer_review.intake_file_ops import (
    build_file_inventory,
    write_checksum_manifest,
    write_file_inventory,
    compute_sha256,
)
from deerflow.runtime.cer_review.intake_pack_builder import build_locked_pack
from deerflow.runtime.cer_review.intake_text_extractor import extract_text_batch
from deerflow.runtime.cer_review.intake_agent_bridge import (
    LiveAgentStageRunner,
)

logger = logging.getLogger(__name__)


# ── CLI Parser ───────────────────────────────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the CER Raw Project Intake Workflow v1."
    )
    parser.add_argument(
        "--project-id",
        required=True,
        help="CER project ID (e.g., CER-PJT-XXXX).",
    )
    parser.add_argument(
        "--input-root",
        required=True,
        help="Path to raw input files directory.",
    )
    parser.add_argument(
        "--project-profile",
        required=True,
        help="Path to project_profile.yaml.",
    )
    parser.add_argument(
        "--artifact-root",
        required=True,
        help="Base artifact root for this project.",
    )
    parser.add_argument(
        "--workflow",
        default=str(REPO_ROOT / "workflows" / "cer_intake_workflow_v1.yaml"),
        help="Path to the workflow YAML.",
    )
    parser.add_argument(
        "--mode",
        choices=("dry-run", "smoke-run", "human-gate-wait"),
        default="smoke-run",
        help="dry-run validates inputs; smoke-run executes pipeline; human-gate-wait waits for decision.",
    )
    parser.add_argument(
        "--intake-session-id",
        help="Existing intake session ID to resume.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging.",
    )
    return parser


# ── Intake Runner ────────────────────────────────────────────────────────────────


class CERRawIntakeRunner:
    """Runner for CER Raw Project Intake Workflow v1.

    Follows the 15-state intake pipeline:
    raw_uploaded → inventory_created → [dedupe_completed, parse_completed] →
    type_detection_done → classification_completed → completeness_evaluated →
    citations_traced → human_gate_pending → [APPROVED | REJECTED] →
    evidence_pack_locked → ready_for_cer_review | blocked

    Phase 1: Deterministic file ops for inventory/checksums, LLM calls for agents.
    """

    def __init__(
        self,
        *,
        project_id: str,
        input_root: Path,
        project_profile_path: Path,
        artifact_root: Path,
        workflow_path: Path,
        intake_session_id: str | None = None,
    ) -> None:
        self.project_id = project_id
        self.input_root = Path(input_root).resolve()
        self.project_profile_path = Path(project_profile_path).resolve()
        self.artifact_root = Path(artifact_root).resolve()
        self.workflow_path = Path(workflow_path).resolve()
        self.intake_session_id = intake_session_id

        self._load_workflow()
        self._init_state_machine()
        self._init_paths()

    def _load_workflow(self) -> None:
        import yaml
        with open(self.workflow_path, encoding="utf-8") as f:
            self.workflow = yaml.safe_load(f)

    def _init_state_machine(self) -> None:
        self.state_machine = IntakeStateMachine.from_artifacts(
            project_id=self.project_id,
            artifact_root=self.artifact_root,
            intake_session_id=self.intake_session_id,
        )
        self.intake_session_id = self.state_machine.intake_session_id
        self.state_machine.append_log({
            "event": "runner_initialized",
            "project_id": self.project_id,
            "workflow_version": self.workflow.get("workflow_version"),
        })

    def _init_paths(self) -> None:
        self.intake_dir = self.artifact_root / "intake"
        self.intake_dir.mkdir(parents=True, exist_ok=True)
        self.locked_dir = self.artifact_root / "intake" / "locked"
        self.text_extracted_dir = self.intake_dir / "text_extracted"
        self.text_extracted_dir.mkdir(parents=True, exist_ok=True)

    # ── Stage Handlers ─────────────────────────────────────────────────────────

    def run(self, *, mode: str = "smoke-run") -> dict:
        """Execute the intake workflow."""
        if mode == "dry-run":
            return self._run_dry()

        if mode == "human-gate-wait":
            return self._wait_for_human_decision()

        # smoke-run: execute full pipeline
        return self._run_smoke()

    def _run_dry(self) -> dict:
        """Validate inputs and write dry-run plan."""
        import yaml
        with open(self.project_profile_path, encoding="utf-8") as f:
            project_profile = yaml.safe_load(f)

        dry_plan = {
            "project_id": self.project_id,
            "intake_session_id": self.intake_session_id,
            "current_state": self.state_machine.current_state.value,
            "input_root": str(self.input_root),
            "input_files": [
                str(p.relative_to(self.input_root))
                for p in self._enumerate_input_files()
            ] if self.input_root.exists() else [],
            "workflow_stages": [
                {"stage_id": s["stage_id"], "agent": s["agent"]}
                for s in self.workflow.get("stages", [])
            ],
            "project_profile": project_profile,
        }

        dry_path = self.intake_dir / "dry_run_plan.json"
        dry_path.write_text(json.dumps(dry_plan, indent=2, ensure_ascii=False))
        return dry_plan

    def _run_smoke(self) -> dict:
        """Execute the full intake pipeline."""
        state = self.state_machine.current_state

        if state == IntakeState.RAW_UPLOADED:
            self._run_file_inventory()
            self._run_dedupe()
            self._run_parse()
            self._run_pdf_check()
            self._run_type_detection()
            self._run_classification()
            self._run_completeness()
            self._run_citations()
            self._run_human_gate_packet()
            self._wait_for_human_decision()

        elif state == IntakeState.HUMAN_GATE_APPROVED:
            self._run_pack_lock()
            self._run_qa()
            if self.state_machine.can_proceed_to_cer_review():
                logger.info("Intake pipeline complete. Ready for CER Review.")

        return {
            "project_id": self.project_id,
            "intake_session_id": self.intake_session_id,
            "current_state": self.state_machine.current_state.value,
            "artifacts": self.state_machine.artifacts,
        }

    # ── Deterministic Stages ───────────────────────────────────────────────────

    def _run_file_inventory(self) -> None:
        """Run deterministic file inventory + checksum (no LLM)."""
        logger.info("Running file inventory (deterministic)...")
        self.state_machine.append_log({"event": "stage_start", "stage": "file_inventory"})

        # Build inventory
        inventory = build_file_inventory(
            input_root=self.input_root,
            project_id=self.project_id,
            intake_session_id=self.intake_session_id,
        )

        # Write checksum manifest
        files = [
            self.input_root / f["relative_path"]
            for f in inventory["files"]
        ]
        checksum_manifest = {
            "schema_name": "cer_intake_checksum_manifest",
            "schema_version": "v1",
            "generated_at": inventory["generated_at"],
            "total_files": len(files),
            "files": [
                {
                    "relative_path": f["relative_path"],
                    "filename": f["filename"],
                    "sha256": f["sha256"],
                    "size_bytes": f["size_bytes"],
                }
                for f in inventory["files"]
            ],
        }

        write_checksum_manifest(self.intake_dir, checksum_manifest)
        write_file_inventory(self.intake_dir, inventory)

        self.state_machine.record_artifact("file_inventory", "intake/file_inventory.json")
        self.state_machine.record_artifact("checksum_manifest", "intake/checksum_manifest.json")

        self.state_machine.transition(IntakeState.INVENTORY_CREATED, reason="file inventory complete")
        self.state_machine.append_log({
            "event": "stage_complete",
            "stage": "file_inventory",
            "total_files": inventory["total_files"],
        })
        logger.info(f"File inventory: {inventory['total_files']} files enumerated.")

    def _run_dedupe(self) -> None:
        """Run deterministic deduplication (checksum-based, no LLM needed for exact dupes)."""
        logger.info("Running dedupe (deterministic)...")
        self.state_machine.append_log({"event": "stage_start", "stage": "dedupe"})

        checksum_path = self.intake_dir / "checksum_manifest.json"
        checksums = json.loads(checksum_path.read_text())

        # Group by checksum
        groups: dict[str, list] = {}
        for f in checksums["files"]:
            sha = f["sha256"]
            groups.setdefault(sha, []).append(f)

        # Find duplicates
        duplicate_groups = []
        for sha, files in groups.items():
            if len(files) > 1:
                duplicate_groups.append({
                    "group_id": f"DUP-{len(duplicate_groups)+1:03d}",
                    "duplicate_type": "exact",
                    "canonical_file": files[0],
                    "duplicate_files": files[1:],
                })

        dedupe_report = {
            "schema_name": "cer_intake_dedupe_report",
            "schema_version": "v1",
            "project_id": self.project_id,
            "intake_session_id": self.intake_session_id,
            "total_files_processed": checksums["total_files"],
            "duplicate_groups": duplicate_groups,
            "canonical_summary": {
                "total_groups": len(duplicate_groups),
                "exact_duplicates": len(duplicate_groups),
                "near_duplicates": 0,
                "version_conflicts": 0,
            },
        }

        dedupe_path = self.intake_dir / "dedupe_report.json"
        dedupe_path.write_text(json.dumps(dedupe_report, indent=2, ensure_ascii=False))

        self.state_machine.record_artifact("dedupe_report", "intake/dedupe_report.json")
        self.state_machine.transition(IntakeState.DEDUPE_COMPLETED, reason="dedupe complete")
        self.state_machine.append_log({
            "event": "stage_complete",
            "stage": "dedupe",
            "duplicate_groups": len(duplicate_groups),
        })
        logger.info(f"Dedupe: {len(duplicate_groups)} duplicate groups found.")

    def _run_parse(self) -> None:
        """Run deterministic text extraction."""
        logger.info("Running text extraction (deterministic)...")
        self.state_machine.append_log({"event": "stage_start", "stage": "parse"})

        inventory = json.loads((self.intake_dir / "file_inventory.json").read_text())
        extractable = [
            self.input_root / f["relative_path"]
            for f in inventory["files"]
            if f["extension"] in {".pdf", ".docx", ".xlsx", ".txt", ".md"}
        ]

        text_index = extract_text_batch(extractable, self.text_extracted_dir)

        index_path = self.intake_dir / "document_text_index.json"
        index_path.write_text(json.dumps(text_index, indent=2, ensure_ascii=False))

        self.state_machine.record_artifact("document_text_index", "intake/document_text_index.json")
        self.state_machine.transition(IntakeState.PARSE_COMPLETED, reason="text extraction complete")
        self.state_machine.append_log({
            "event": "stage_complete",
            "stage": "parse",
            "extracted": text_index["total_files_extracted"],
            "failed": text_index["total_files_failed"],
        })
        logger.info(
            f"Parse: {text_index['total_files_extracted']} extracted, "
            f"{text_index['total_files_failed']} failed."
        )

    def _run_pdf_check(self) -> None:
        """Create skeleton pdf_readability_report (Phase 1: LLM call deferred)."""
        self.state_machine.append_log({"event": "stage_start", "stage": "pdf_check"})
        # Phase 1: PDF readability check deferred to LLM agent
        # Write placeholder — runner will call LLM for actual assessment
        pdf_report = {
            "schema_name": "cer_intake_pdf_readability_report",
            "schema_version": "v1",
            "project_id": self.project_id,
            "intake_session_id": self.intake_session_id,
            "total_pdfs_assessed": 0,
            "readability_distribution": {"EXCELLENT": 0, "GOOD": 0, "FAIR": 0, "POOR": 0, "UNREADABLE": 0},
            "pdfs": [],
            "ocr_required_files": [],
            "flagged_for_review": [],
            "note": "Phase 1: PDF readability assessment deferred to LLM agent",
        }
        path = self.intake_dir / "pdf_readability_report.json"
        path.write_text(json.dumps(pdf_report, indent=2, ensure_ascii=False))
        self.state_machine.record_artifact("pdf_readability_report", "intake/pdf_readability_report.json")
        self.state_machine.transition(IntakeState.PDF_CHECKED, reason="pdf check deferred")
        self.state_machine.append_log({"event": "stage_complete", "stage": "pdf_check"})

    # ── LLM-Powered Stages ──────────────────────────────────────────────────────

    def _run_type_detection(self) -> None:
        """Run document type detection (LLM call)."""
        logger.info("Running type detection (LLM)...")
        self.state_machine.append_log({"event": "stage_start", "stage": "type_detection"})
        # Phase 1: LLM call placeholder — uses CERLLMInvoker
        result = self._call_agent(
            agent_name="intake_document_type_detection",
            prompt_path=REPO_ROOT / "prompts" / "cer" / "intake" / "document_type_detection_agent.md",
            context=self._build_agent_context(),
        )
        self._write_agent_output("type_detection", result)
        self.state_machine.record_artifact("classification_candidates", "intake/classification_candidates.json")
        self.state_machine.transition(IntakeState.TYPE_DETECTION_DONE, reason="type detection complete")
        self.state_machine.append_log({"event": "stage_complete", "stage": "type_detection"})

    def _run_classification(self) -> None:
        """Run evidence classification (LLM call)."""
        logger.info("Running evidence classification (LLM)...")
        self.state_machine.append_log({"event": "stage_start", "stage": "classification"})
        result = self._call_agent(
            agent_name="intake_evidence_classification",
            prompt_path=REPO_ROOT / "prompts" / "cer" / "intake" / "evidence_classification_agent.md",
            context=self._build_agent_context(),
        )
        self._write_agent_output("classification", result)
        self.state_machine.record_artifact("evidence_classification_final", "intake/evidence_classification_final.json")
        self.state_machine.transition(IntakeState.CLASSIFICATION_COMPLETED, reason="classification complete")
        self.state_machine.append_log({"event": "stage_complete", "stage": "classification"})

    def _run_completeness(self) -> None:
        """Run evidence completeness evaluation (LLM call)."""
        logger.info("Running completeness evaluation (LLM)...")
        self.state_machine.append_log({"event": "stage_start", "stage": "completeness"})
        result = self._call_agent(
            agent_name="intake_evidence_completeness",
            prompt_path=REPO_ROOT / "prompts" / "cer" / "intake" / "evidence_completeness_agent.md",
            context=self._build_agent_context(),
        )
        self._write_agent_output("completeness", result)
        self.state_machine.record_artifact("evidence_completeness_report", "intake/evidence_completeness_report.md")
        self.state_machine.transition(IntakeState.COMPLETENESS_EVALUATED, reason="completeness evaluated")
        self.state_machine.append_log({"event": "stage_complete", "stage": "completeness"})

    def _run_citations(self) -> None:
        """Run citation tracing (LLM call)."""
        logger.info("Running citation tracing (LLM)...")
        self.state_machine.append_log({"event": "stage_start", "stage": "citations"})
        result = self._call_agent(
            agent_name="intake_citation_locator",
            prompt_path=REPO_ROOT / "prompts" / "cer" / "intake" / "citation_locator_agent.md",
            context=self._build_agent_context(),
        )
        self._write_agent_output("citations", result)
        self.state_machine.record_artifact("citation_trace_report", "intake/citation_trace_report.json")
        self.state_machine.transition(IntakeState.CITATIONS_TRACED, reason="citations traced")
        self.state_machine.append_log({"event": "stage_complete", "stage": "citations"})

    def _run_human_gate_packet(self) -> None:
        """Run human gate packet writer (LLM call)."""
        logger.info("Running human gate packet writer (LLM)...")
        self.state_machine.append_log({"event": "stage_start", "stage": "human_gate_packet"})
        result = self._call_agent(
            agent_name="intake_human_gate_packet_writer",
            prompt_path=REPO_ROOT / "prompts" / "cer" / "intake" / "human_gate_packet_writer.md",
            context=self._build_agent_context(),
        )
        self._write_agent_output("human_gate_packet", result)
        self.state_machine.record_artifact("classification_review_packet", "intake/classification_review_packet.json")
        self.state_machine.transition(IntakeState.HUMAN_GATE_PENDING, reason="human gate packet ready")
        self.state_machine.append_log({
            "event": "human_gate_pending",
            "stage": "human_gate_packet",
            "packet_path": "intake/classification_review_packet.json",
        })

    def _wait_for_human_decision(self) -> dict:
        """Wait for human gate decision file to appear."""
        decision_path = self.intake_dir / "human_intake_gate_decision.json"
        if decision_path.exists():
            return self._process_human_decision(decision_path)
        return {
            "status": "waiting_for_human_decision",
            "decision_file": str(decision_path),
            "intake_session_id": self.intake_session_id,
        }

    def _process_human_decision(self, decision_path: Path) -> dict:
        """Process human gate decision and route accordingly."""
        decision = json.loads(decision_path.read_text())
        verdict = decision.get("verdict")

        self.state_machine.append_log({
            "event": "human_decision_received",
            "verdict": verdict,
            "reviewer": decision.get("reviewer", {}).get("name"),
        })

        if verdict in ("APPROVED", "APPROVED_WITH_CONDITIONS"):
            self.state_machine.transition(IntakeState.HUMAN_GATE_APPROVED, reason=f"human approved: {verdict}")
            self._run_pack_lock()
            self._run_qa()
        else:
            self.state_machine.transition(IntakeState.HUMAN_GATE_REJECTED, reason="human rejected")
            self.state_machine.append_log({
                "event": "human_gate_rejected",
                "rejection_reason": decision.get("rejection_reason"),
            })

        return {
            "status": "decision_processed",
            "verdict": verdict,
            "intake_session_id": self.intake_session_id,
        }

    def _run_pack_lock(self) -> None:
        """Build locked evidence pack (deterministic)."""
        logger.info("Building locked evidence pack...")
        self.state_machine.append_log({"event": "stage_start", "stage": "pack_lock"})

        decision_path = self.intake_dir / "human_intake_gate_decision.json"
        checksum_path = self.intake_dir / "checksum_manifest.json"

        decision = json.loads(decision_path.read_text())
        checksum_manifest = json.loads(checksum_path.read_text())

        # Get approved files from classification_final
        class_final_path = self.intake_dir / "evidence_classification_final.json"
        if class_final_path.exists():
            classification = json.loads(class_final_path.read_text())
            approved_files = classification.get("classifications", [])
            # Attach checksums to approved files
            checksum_map = {f["relative_path"]: f["sha256"] for f in checksum_manifest["files"]}
            for f in approved_files:
                f["sha256"] = checksum_map.get(f.get("relative_path", ""))
            decision["approved_files"] = approved_files

        manifest = build_locked_pack(
            project_id=self.project_id,
            intake_session_id=self.intake_session_id,
            input_root=self.input_root,
            output_root=self.artifact_root.parent,
            approved_decision=decision,
            checksum_manifest=checksum_manifest,
        )

        self.state_machine.record_artifact("locked_evidence_pack_manifest", "intake/locked/locked_evidence_pack_manifest.json")
        self.state_machine.transition(IntakeState.EVIDENCE_PACK_LOCKED, reason="pack locked")
        self.state_machine.append_log({
            "event": "stage_complete",
            "stage": "pack_lock",
            "locked_files": manifest["total_files"],
        })
        logger.info(f"Locked pack built: {manifest['total_files']} files.")

    def _run_qa(self) -> None:
        """Run QA verification (LLM call + deterministic checks)."""
        logger.info("Running QA verification...")
        self.state_machine.append_log({"event": "stage_start", "stage": "qa"})

        # Deterministic: verify checksums
        locked_manifest_path = self.locked_dir / "locked_evidence_pack_manifest.json"
        checksum_manifest = json.loads((self.intake_dir / "checksum_manifest.json").read_text())

        from deerflow.runtime.cer_review.intake_file_ops import verify_locked_pack_checksums
        all_match, mismatches = verify_locked_pack_checksums(
            self.locked_dir,
            checksum_manifest,
        )

        # LLM call for QA agent assessment
        result = self._call_agent(
            agent_name="intake_qa",
            prompt_path=REPO_ROOT / "prompts" / "cer" / "intake" / "intake_qa_agent.md",
            context={
                **self._build_agent_context(),
                "deterministic_checksum_valid": all_match,
                "checksum_mismatches": mismatches,
            },
        )
        self._write_agent_output("qa", result)

        qa_passed = result.get("qa_passed", False) if isinstance(result, dict) else False
        if all_match and qa_passed:
            self.state_machine.transition(IntakeState.READY_FOR_CER_REVIEW, reason="QA passed")
            self.state_machine.append_log({"event": "ready_for_cer_review"})
        else:
            self.state_machine.transition(IntakeState.BLOCKED, reason="QA found anomalies")
            self.state_machine.append_log({"event": "blocked", "reason": "QA failure"})

        self.state_machine.append_log({"event": "stage_complete", "stage": "qa", "passed": qa_passed})

    # ── LLM Call Helper ────────────────────────────────────────────────────────

    # Map agent_name suffix → SEMANTIC_STAGES key
    _AGENT_NAME_TO_STAGE = {
        "document_type_detection": "type_detection",
        "evidence_classification": "classification",
        "evidence_completeness": "completeness",
        "citation_locator": "citations",
        "human_gate_packet_writer": "human_gate_packet",
        "qa": "qa",
        "pdf_readability": "pdf_check",
    }

    def _call_agent(
        self,
        *,
        agent_name: str,
        prompt_path: Path,
        context: dict,
    ) -> dict:
        """Call an LLM agent using CERLLMInvoker with skill prompt.

        Uses LiveAgentStageRunner for proper skill-prompt loading,
        structured output, and honest invocation tracking.
        Falls back to structured placeholder if LLM unavailable.
        """
        # Map agent_name (e.g. "intake_document_type_detection")
        # to SEMANTIC_STAGES key (e.g. "type_detection")
        raw_stage = agent_name.replace("intake_", "")
        stage = self._AGENT_NAME_TO_STAGE.get(raw_stage, raw_stage)

        # Use LiveAgentStageRunner for proper execution
        runner = LiveAgentStageRunner(
            repo_root=REPO_ROOT,
            project_id=self.project_id,
            intake_session_id=self.intake_session_id,
            intake_dir=self.intake_dir,
            llm_client=self._get_llm_client(),
        )

        result = runner.run_stage(stage, context)

        # Log the invocation
        self.state_machine.append_log({
            "event": "agent_invocation",
            "stage": stage,
            "agent_name": agent_name,
            "skill_file": result.skill_file,
            "invocation_method": result.invocation_method.value,
            "status": result.status,
            "success": result.success,
            "error": result.error,
            "duration_sec": round(result.duration_sec, 2),
            "llm_attempts": result.llm_attempts,
            "model_used": result.model_used,
            "output_artifact": result.output_artifact,
        })

        if result.success and result.output_artifact:
            output_path = self.intake_dir / result.output_artifact
            if output_path.exists():
                return json.loads(output_path.read_text())

        # Fallback: return placeholder dict
        return {
            "schema_name": f"cer_intake_{agent_name}_result",
            "schema_version": "v1",
            "project_id": self.project_id,
            "intake_session_id": self.intake_session_id,
            "agent_name": agent_name,
            "status": result.status,
            "note": result.error or "Phase 1 structured placeholder",
        }

    def _get_llm_client(self):
        """Get or create LLM client (cached on runner instance)."""
        if not hasattr(self, "_llm_client"):
            self._llm_client = None
            try:
                from deerflow.models.factory import create_chat_model
                from deerflow.config import get_app_config
                config = get_app_config()
                if config.models:
                    self._llm_client = create_chat_model(config.models[0].name)
                    logger.info(f"LLM client initialized: {config.models[0].name}")
            except Exception as e:
                logger.warning(f"Could not initialize LLM client: {e}")
        return self._llm_client

    def _build_agent_context(self) -> dict:
        """Build context dict for agent calls."""
        inventory = {}
        dedupe = {}
        text_index = {}
        classification_final = {}
        completeness = {}

        inv_path = self.intake_dir / "file_inventory.json"
        dedupe_path = self.intake_dir / "dedupe_report.json"
        text_path = self.intake_dir / "document_text_index.json"
        class_path = self.intake_dir / "evidence_classification_final.json"
        comp_path = self.intake_dir / "evidence_completeness_report.md"

        if inv_path.exists():
            inventory = json.loads(inv_path.read_text())
        if dedupe_path.exists():
            dedupe = json.loads(dedupe_path.read_text())
        if text_path.exists():
            text_index = json.loads(text_path.read_text())
        if class_path.exists():
            classification_final = json.loads(class_path.read_text())

        return {
            "project_id": self.project_id,
            "intake_session_id": self.intake_session_id,
            "input_root": str(self.input_root),
            "intake_dir": str(self.intake_dir),
            "file_inventory": inventory,
            "dedupe_report": dedupe,
            "document_text_index": text_index,
            "evidence_classification_final": classification_final,
            "evidence_completeness": completeness,
        }

    def _write_agent_output(self, stage: str, result: dict) -> None:
        """Write agent output to intake directory."""
        path = self.intake_dir / f"{stage}_output.json"
        path.write_text(json.dumps(result, indent=2, ensure_ascii=False))

    def _enumerate_input_files(self):
        """Enumerate all files in input root."""
        for p in self.input_root.rglob("*"):
            if p.is_file() and not p.name.startswith("."):
                yield p


# ── Main ─────────────────────────────────────────────────────────────────────────


def main() -> int:
    args = build_parser().parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    runner = CERRawIntakeRunner(
        project_id=args.project_id,
        input_root=Path(args.input_root),
        project_profile_path=Path(args.project_profile),
        artifact_root=Path(args.artifact_root),
        workflow_path=Path(args.workflow),
        intake_session_id=args.intake_session_id,
    )

    result = runner.run(mode=args.mode)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
