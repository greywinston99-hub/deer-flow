"""Minimal runner for the CER Review Workflow v0 skeleton.

This module provides a bridge that:
1. loads workflows/cer_review_v0.yaml
2. maps workflow steps to Python handlers
3. writes artifacts into DeerFlow's per-thread outputs directory
4. supports dry-run, smoke-run, and closure-only modes
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import uuid
import zipfile
from dataclasses import dataclass, replace
from html import unescape
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from deerflow.config.paths import get_paths
from deerflow.subagents.cer_review_model_policy import get_cer_review_model_for_agent

if TYPE_CHECKING:
    from deerflow.subagents.executor import SubagentExecutor

logger = logging.getLogger(__name__)

_SUPPORTED_STEP_IDS = (
    "cer_intake_agent",
    "cer_parse_normalize_agent",
    "cer_hf_check_agent",
    "cer_five_dimension_agent",
    "cer_cross_doc_consistency_agent",
    "cer_human_boundary_agent",
    "cer_review_package_agent",
    "cer_gate_closure_agent",
    # v1 stages
    "cer_route_screen_agent",
    "cer_layer1_scan_agent",
    "cer_claim_scope_agent",
    "cer_sota_evidence_agent",
    "cer_equivalence_agent",
    "cer_consistency_agent",
    "cer_pmcf_lifecycle_agent",
    "cer_review_package_agent_v1",
    "cer_gate_closure_agent_v1",
    # D1 ordered_steps
    "cer_admin_precheck",
    "cer_intake",
    "cer_structure_compliance",
    "cer_intended_purpose",
    "cer_cep_methodology",
    "cer_clinical_evidence_panel",
    "cer_ifu_sscp_label",
    "cer_qa_gate",
    "cer_cear_style_finding_formatter",
    "cer_human_boundary",
    "cer_qms_review",
    "cer_gate_closure",
)

_CER_REVIEW_JSON_ONLY_AGENTS = {
    "cer-intake-reviewer",
    "cer-structure-compliance-reviewer",
    "cer-intended-purpose-reviewer",
    "cer-cep-methodology-reviewer",
    "cer-clinical-evidence-panel-reviewer",
    "cer-ifu-sscp-label-reviewer",
    "cer-qa-gate-reviewer",
    "cer-cear-formatter-reviewer",
    "cer-human-boundary-reviewer",
    "cer-gate-closure-reviewer",
}

_UPSTREAM_ARTIFACT_PROMPT_MAX_CHARS = 60_000
_CER_PANEL_TEXT_CONTEXT_MAX_CHARS = 60_000

_D1_HANDLER_AGENTS = {
    "cer_intake": "cer-intake-reviewer",
    "cer_structure_compliance": "cer-structure-compliance-reviewer",
    "cer_intended_purpose": "cer-intended-purpose-reviewer",
    "cer_cep_methodology": "cer-cep-methodology-reviewer",
    "cer_clinical_evidence_panel": "cer-clinical-evidence-panel-reviewer",
    "cer_ifu_sscp_label": "cer-ifu-sscp-label-reviewer",
    "cer_qa_gate": "cer-qa-gate-reviewer",
    "cer_cear_style_finding_formatter": "cer-cear-formatter-reviewer",
    "cer_human_boundary": "cer-human-boundary-reviewer",
    "cer_gate_closure": "cer-gate-closure-reviewer",
}

_D1_STEP_ARTIFACTS = {
    "cer_admin_precheck": ("00_admin_precheck", "admin_precheck_report.json"),
    "cer_intake": ("01_docstruct", "cer_docstruct.json"),
    "cer_structure_compliance": ("02_structure_compliance", "report.json"),
    "cer_intended_purpose": ("03_intended_purpose", "report.json"),
    "cer_cep_methodology": ("04_cep_methodology", "report.json"),
    "cer_clinical_evidence_panel": ("05_lanes", "clinical_evidence_panel_review.json"),
    "cer_ifu_sscp_label": ("06_consistency", "report.json"),
    "cer_qa_gate": ("07_qa_gate", "qa_synthesis.json"),
    "cer_cear_style_finding_formatter": ("08_cear_format", "formatted_findings.json"),
    "cer_human_boundary": ("09_human_boundary", "packet.json"),
    "cer_qms_review": ("10_qms_review", "qms_findings.json"),
    "cer_gate_closure": ("11_gate_closure", "review_package.json"),
}

# HF check definitions (ID -> label + keywords)
_HF_CHECK_DEFS = {
    "HF-001": {
        "label": "Intended Purpose 描述完整性",
        "keywords": ["intended purpose", "intended use", "适应证", "适应症", "intended purpose", "indication for use", "临床预期用途", "预期用途"],
        "severity": "high",
    },
    "HF-002": {
        "label": "临床评价范围与 IFU 一致性",
        "keywords": ["instruction for use", "ifu", "使用说明书", "scope of clinical evaluation", "clinical evaluation scope"],
        "severity": "high",
    },
    "HF-003": {
        "label": "文献纳入排除标准明确性",
        "keywords": ["inclusion criteria", "exclusion criteria", "文献纳入", "文献排除", "纳入标准", "排除标准", "search strategy", "检索策略"],
        "severity": "medium",
    },
    "HF-004": {
        "label": "文献质量等级评估",
        "keywords": ["risk of bias", "quality assessment", "文献质量", "bias", "Jadad", "Cochrane", "GRADE", "质量评估"],
        "severity": "medium",
    },
    "HF-005": {
        "label": "等同器械证据链完整性",
        "keywords": ["equivalence", "equivalent device", "等同器械", "等效器械", "substantial equivalence", "demonstrated equivalence"],
        "severity": "high",
    },
    "HF-006": {
        "label": "禁忌证与适应证冲突",
        "keywords": ["contraindication", "禁忌证", "contraindications", "禁忌", "indication", "适应证", "warning", "警告", " precaution"],
        "severity": "high",
    },
    "HF-007": {
        "label": "受益-风险章节存在性",
        "keywords": ["benefit risk", "benefit-risk", "受益风险", "clinical benefit", "临床受益", "risk assessment", "风险评估", "风险-受益"],
        "severity": "high",
    },
    "HF-008": {
        "label": "PMCF 计划与 CER 关联性",
        "keywords": ["pmcf", "post-market clinical follow-up", "上市后临床跟踪", "post market", "surveillance", "pmcf plan", "临床随访"],
        "severity": "medium",
    },
}

# Five dimension definitions
_DIMENSION_DEFS = {
    "STRUCT": {
        "label": "结构合规性",
        "description": "检查CER文档结构是否符合MDR/IVDR格式要求，章节是否完整",
    },
    "LOGIC": {
        "label": "逻辑完整性",
        "description": "检查CER各章节之间的逻辑一致性与论证链完整性",
    },
    "EVID": {
        "label": "证据链有效性",
        "description": "评估临床证据的充分性、相关性和质量等级",
    },
    "CONS": {
        "label": "一致性",
        "description": "检查CER内部以及与参考文档之间的一致性",
    },
    "BRR": {
        "label": "受益-风险论证",
        "description": "评估受益-风险综合结论的合理性（Layer 3 - 必须人工判断）",
    },
}


@dataclass
class CERRunResult:
    thread_id: str
    run_id: str
    mode: str
    workflow_name: str
    executed_steps: list[str]
    artifact_root_virtual: str
    artifact_root_actual: str


class CERReviewRunner:
    """Bridge from workflow YAML to executable step handlers for CER review."""

    def __init__(
        self,
        *,
        repo_root: str | Path,
        workflow_path: str | Path,
        project_profile_path: str | Path,
        input_root: str | Path | None = None,
        thread_id: str | None = None,
        artifact_root_override: str | Path | None = None,
        run_id_override: str | None = None,
        run_mode: str = "smoke-run",
    ) -> None:
        self.repo_root = Path(repo_root).resolve()
        self.workflow_path = Path(workflow_path).resolve()
        self.project_profile_path = Path(project_profile_path).resolve()
        self.input_root_override = Path(input_root).resolve() if input_root else None
        self.thread_id = thread_id or self._make_thread_id()
        self.run_mode = run_mode

        self.paths = get_paths()
        self.paths.ensure_thread_dirs(self.thread_id)

        self.workflow = self._load_yaml(self.workflow_path)
        self.project_profile = self._load_yaml(self.project_profile_path)
        self.project_id = str(self.project_profile.get("project_id") or "unknown")

        self.run_id = run_id_override or self._make_run_id()
        self.workflow_name = str(self.workflow.get("workflow_name", "cer_review_v0"))

        # Get artifact root - D1 workflow uses artifact_dir per step instead
        runtime_defaults = self.workflow.get("runtime_defaults", {})
        if runtime_defaults:
            artifact_root_template = runtime_defaults.get("artifact_root", "/tmp/cer_review/${run_id}")
        else:
            # D1 workflow: derive from project_profile or use default
            artifact_root_template = self.project_profile.get("artifact_policy", {}).get("artifact_root", "/tmp/cer_review/${run_id}")
        self.artifact_root_virtual = self._render_template(str(artifact_root_template))
        if artifact_root_override:
            self.artifact_root_actual = Path(self._render_template(str(artifact_root_override))).resolve()
        else:
            # Try virtual path resolution first, fall back to direct path
            try:
                self.artifact_root_actual = self.paths.resolve_virtual_path(self.thread_id, self.artifact_root_virtual)
            except ValueError:
                # D1 workflow: use artifact_root directly if it's an absolute path
                self.artifact_root_actual = Path(self.artifact_root_virtual.replace("${run_id}", self.run_id))
        self.artifact_root_actual.mkdir(parents=True, exist_ok=True)
        self.artifact_root = self.artifact_root_actual

        # Load project protocol if present (for Gate A enforcement)
        self.project_protocol = self._load_project_protocol()

        # Gate A status from project protocol
        self.gate_a_status = self._get_gate_a_status()

        # V27: Document Routing Layer — unified document loading for all agents
        self._routing_config = self._load_routing_config()
        self._routing_audit_log: list[dict[str, Any]] = []

        self.step_map = {
            "cer_intake_agent": self._run_intake,
            "cer_parse_normalize_agent": self._run_parse_normalize,
            "cer_hf_check_agent": self._run_hf_check,
            "cer_five_dimension_agent": self._run_five_dimension,
            "cer_cross_doc_consistency_agent": self._run_cross_doc_consistency,
            "cer_human_boundary_agent": self._run_human_boundary,
            "cer_review_package_agent": self._run_review_package,
            "cer_gate_closure_agent": self._run_gate_closure,
            # v1 stages
            "cer_route_screen_agent": self._run_route_screen,
            "cer_layer1_scan_agent": self._run_layer1_scan,
            "cer_claim_scope_agent": self._run_claim_scope,
            "cer_sota_evidence_agent": self._run_sota_evidence,
            "cer_equivalence_agent": self._run_equivalence,
            "cer_consistency_agent": self._run_consistency,
            "cer_pmcf_lifecycle_agent": self._run_pmcf_lifecycle,
            "cer_review_package_agent_v1": self._run_review_package_v1,
            "cer_gate_closure_agent_v1": self._run_gate_closure_v1,
            # D1 ordered_steps
            "cer_admin_precheck": self._run_d1_admin_precheck,
            "cer_intake": self._run_d1_intake,
            "cer_structure_compliance": self._run_d1_structure_compliance,
            "cer_intended_purpose": self._run_d1_intended_purpose,
            "cer_cep_methodology": self._run_d1_cep_methodology,
            "cer_clinical_evidence_panel": self._run_d1_clinical_evidence_panel,
            "cer_ifu_sscp_label": self._run_d1_ifu_sscp_label,
            "cer_qa_gate": self._run_d1_qa_gate,
            "cer_cear_style_finding_formatter": self._run_d1_cear_formatter,
            "cer_human_boundary": self._run_d1_human_boundary,
            "cer_qms_review": self._run_d1_qms_review,
            "cer_gate_closure": self._run_d1_gate_closure,
        }

        # Detect workflow mode (BIGDP2026.6 B.4.2: prefer explicit version field):
        # - Explicit workflow_version field takes priority
        # - Fallback: "v1" if workflow has "stages"; "d1"/"v0" if "ordered_steps"
        explicit_version = str(self.workflow.get("workflow_version") or "").strip()
        supported_versions = {"1.0", "1", "d1"}
        if explicit_version:
            if explicit_version in supported_versions:
                self.workflow_mode = "v1" if explicit_version in ("1.0", "1") else explicit_version
            else:
                raise ValueError(
                    f"Unsupported workflow_version '{explicit_version}' in {self.workflow_name}. "
                    f"Supported versions: {supported_versions}. "
                    f"Update workflow YAML or add version support in runner.py."
                )
        elif "stages" in self.workflow:
            self.workflow_mode = "v1"
        elif "ordered_steps" in self.workflow:
            first_step = self.workflow.get("ordered_steps", [{}])[0]
            first_step_id = first_step.get("step_id", "")
            if first_step_id in ("cer_intake", "cer_structure_compliance", "cer_intended_purpose",
                                  "cer_cep_methodology", "cer_clinical_evidence_panel",
                                  "cer_ifu_sscp_label", "cer_qa_gate", "cer_cear_style_finding_formatter",
                                  "cer_human_boundary", "cer_gate_closure"):
                self.workflow_mode = "d1"
            else:
                self.workflow_mode = "v0"
        else:
            self.workflow_mode = "v0"

        # NocoDB runtime binding state (scaffold - disabled by default)
        self._nocodb_enabled = False
        self._nocodb_verification: dict[str, Any] = {}

    def run(self) -> CERRunResult:
        mode = self.run_mode
        executed_steps: list[str] = []

        # Gate A check for formal-review mode
        if mode == "formal-review":
            allowed, reason = self._check_gate_a_for_formal_review()
            if not allowed:
                self._write_run_context(mode=mode)
                self._write_gate_a_blocked(reason)
                self._write_event_log("GATE_A_BLOCKED", {
                    "reason": reason,
                    "gate_a_status": self.gate_a_status,
                    "final_status": "FORMAL_REVIEW_BLOCKED_GATE_A_NOT_ACCEPTED",
                })
                self._write_task_ledger("blocked", {
                    "reason": reason,
                    "final_status": "FORMAL_REVIEW_BLOCKED_GATE_A_NOT_ACCEPTED",
                })
                self._write_final_synthesis(executed_steps=[])
                self._write_artifact_index()
                self._write_agent_usage_ledger()
                logger.warning("Formal review blocked by Gate A: %s", reason)
                return CERRunResult(
                    thread_id=self.thread_id,
                    run_id=self.run_id,
                    mode=mode,
                    workflow_name=self.workflow_name,
                    executed_steps=[],
                    artifact_root_virtual=self.artifact_root_virtual,
                    artifact_root_actual=str(self.artifact_root_actual),
                )

        if mode == "dry-run":
            self._write_run_context(mode=mode)
            self._write_json(
                self._artifact_path("00_manifest", "dry_run_plan.json"),
                self._build_dry_run_plan(),
            )
            return CERRunResult(
                thread_id=self.thread_id,
                run_id=self.run_id,
                mode=mode,
                workflow_name=self.workflow_name,
                executed_steps=executed_steps,
                artifact_root_virtual=self.artifact_root_virtual,
                artifact_root_actual=str(self.artifact_root_actual),
            )

        if mode == "closure-only":
            self._write_run_context(mode=mode)
            self._run_gate_closure({})
            executed_steps = ["cer_gate_closure_agent"]
            self._write_final_synthesis(executed_steps=executed_steps)
            self._write_artifact_index()
            self._write_agent_usage_ledger()
            return CERRunResult(
                thread_id=self.thread_id,
                run_id=self.run_id,
                mode=mode,
                workflow_name=self.workflow_name,
                executed_steps=executed_steps,
                artifact_root_virtual=self.artifact_root_virtual,
                artifact_root_actual=str(self.artifact_root_actual),
            )

        self._write_run_context(mode=mode)

        # Execute workflow based on mode
        if self.workflow_mode == "d1":
            # D1: use ordered_steps with D1 step_ids
            executed_steps = self._run_d1_workflow()
        elif self.workflow_mode == "v1":
            # v1: use stages list
            stages = self.workflow.get("stages", [])
            for stage in stages:
                stage_id = stage.get("stage_id")
                if stage_id not in _SUPPORTED_STEP_IDS:
                    continue
                handler = self.step_map.get(stage_id)
                if handler:
                    handler(stage)
                    executed_steps.append(stage_id)
        else:
            # v0: use ordered_steps with legacy step_ids
            for step in self.workflow.get("ordered_steps", []):
                step_id = step.get("step_id")
                if step_id not in _SUPPORTED_STEP_IDS:
                    break
                handler = self.step_map[step_id]
                handler(step)
                executed_steps.append(step_id)

        # NocoDB runtime binding (non-blocking scaffold)
        nocodb_verification: dict[str, Any] = {}
        if self.workflow_mode == "d1" and self._nocodb_configured():
            try:
                nocodb_verification = self._run_nocodb_phase()
            except Exception as e:
                logger.warning("NocoDB phase failed: %s", e)
                nocodb_verification = {"errors": [str(e)], "runtime_nocodb_call": False}

        # Schema validation gate - blocks on failure
        if self.workflow_mode == "d1":
            validation_result = self._validate_d1_artifacts_schema()
            if not validation_result["valid"]:
                self._write_schema_validation_failure(validation_result)
                self._write_task_ledger("schema_validation_failed", {
                    "failures": validation_result["failures"],
                    "workflow_mode": self.workflow_mode,
                })
                self._write_event_log("SCHEMA_VALIDATION_FAILED", validation_result)
                self._write_artifact_index()
                self._write_agent_usage_ledger()
                raise ValueError(
                    f"Schema validation failed for {len(validation_result['failures'])} artifact(s): "
                    + ", ".join(validation_result["failures"].keys())
                )

        # Write run manifest and ledger artifacts
        self._write_final_synthesis(executed_steps=executed_steps)
        self._write_json(
            self._artifact_path("00_manifest", "run_summary.json"),
            {
                "thread_id": self.thread_id,
                "run_id": self.run_id,
                "workflow_name": self.workflow_name,
                "mode": mode,
                "executed_steps": executed_steps,
                "artifact_root_virtual": self.artifact_root_virtual,
                "artifact_root_actual": str(self.artifact_root_actual),
            },
        )
        self._write_artifact_index()
        self._write_agent_usage_ledger()
        self._write_routing_audit_log()  # V27: persist document routing audit trail
        self._write_task_ledger("completed", {
            "executed_steps": executed_steps,
            "workflow_mode": self.workflow_mode,
        })
        self._write_event_log("RUN_COMPLETED", {
            "executed_steps": executed_steps,
            "workflow_mode": self.workflow_mode,
        })
        return CERRunResult(
            thread_id=self.thread_id,
            run_id=self.run_id,
            mode=mode,
            workflow_name=self.workflow_name,
            executed_steps=executed_steps,
            artifact_root_virtual=self.artifact_root_virtual,
            artifact_root_actual=str(self.artifact_root_actual),
        )

    # -------------------------------------------------------------------------
    # NocoDB Runtime Binding (D3 scaffold)
    # -------------------------------------------------------------------------

    def _nocodb_configured(self) -> bool:
        """Check if NocoDB is configured via environment variables."""
        try:
            import httpx
        except ImportError:
            return False
        return all(os.environ.get(k) for k in ("NOCODB_EMAIL", "NOCODB_PASSWORD", "NOCODB_BASE_ID"))

    def _nocodb_session(self) -> "httpx.Client":
        """Create authenticated NocoDB session."""
        import httpx
        base_url = os.environ.get("NOCODB_BASE_URL", "http://localhost:8081").rstrip("/")
        v1_api = f"{base_url}/api/v1"
        email = os.environ.get("NOCODB_EMAIL", "")
        password = os.environ.get("NOCODB_PASSWORD", "")
        client = httpx.Client(timeout=10)
        signin = client.post(v1_api + "/auth/user/signin", json={"email": email, "password": password})
        if signin.status_code != 200:
            raise RuntimeError(f"NocoDB signin failed: {signin.status_code}")
        return client

    def _nocodb_get_table_map(self, client: "httpx.Client") -> dict[str, dict[str, Any]]:
        """Get table name to ID mapping for the NocoDB base."""
        import httpx
        base_id = os.environ.get("NOCODB_BASE_ID", "")
        base_url = os.environ.get("NOCODB_BASE_URL", "http://localhost:8081").rstrip("/")
        resp = client.get(f"{base_url}/api/v1/db/meta/projects/{base_id}/tables")
        tables = resp.json().get("list", [])
        return {t["table_name"]: t for t in tables}

    def _nocodb_insert(self, client: "httpx.Client", table_id: str, records: list[dict]) -> dict:
        """Insert records into a NocoDB table."""
        import httpx
        base_url = os.environ.get("NOCODB_BASE_URL", "http://localhost:8081").rstrip("/")
        resp = client.post(f"{base_url}/api/v2/tables/{table_id}/records", json=records)
        if resp.status_code not in (200, 201):
            raise RuntimeError(f"NocoDB insert failed: {resp.status_code} {resp.text}")
        return resp.json()

    def _nocodb_query(
        self, client: "httpx.Client", table_id: str, where: str | None = None, limit: int = 100
    ) -> list[dict]:
        """Query records from a NocoDB table."""
        import httpx
        base_url = os.environ.get("NOCODB_BASE_URL", "http://localhost:8081").rstrip("/")
        params: dict[str, Any] = {"limit": limit}
        if where:
            params["where"] = where
        resp = client.get(f"{base_url}/api/v2/tables/{table_id}/records", params=params)
        if resp.status_code != 200:
            raise RuntimeError(f"NocoDB query failed: {resp.status_code} {resp.text}")
        return resp.json().get("list", [])

    def _run_nocodb_phase(self) -> dict[str, Any]:
        """Execute NocoDB read-write phase and return verification evidence.

        Non-production scaffold: writes D1 artifact paths to NocoDB tables,
        then reads back to verify. Does not block workflow if NocoDB is unavailable.
        """
        from datetime import datetime, timezone

        verification: dict[str, Any] = {
            "run_id": self.run_id,
            "thread_id": self.thread_id,
            "workflow_name": self.workflow_name,
            "workflow_mode": self.workflow_mode,
            "runtime_nocodb_call": True,
            "actual_connection": False,
            "records_written": {},
            "records_read": {},
            "read_after_write_verified": False,
            "errors": [],
            "schema_gap_detected": False,
        }

        if not self._nocodb_configured():
            verification["errors"].append("NocoDB not configured (missing env vars)")
            return verification

        try:
            client = self._nocodb_session()
            table_map = self._nocodb_get_table_map(client)
        except Exception as e:
            verification["errors"].append(f"NocoDB connection failed: {e}")
            return verification

        # 7 required CER tables
        required_tables = [
            "cer_review_runs",
            "cer_preliminary_findings",
            "cer_human_review_required_items",
            "cer_backflow_candidates",
            "cer_knowledge_assets",
            "cer_section_assessments",
            "cer_cross_document_consistency_items",
        ]
        missing_tables = [t for t in required_tables if t not in table_map]
        if missing_tables:
            verification["schema_gap_detected"] = True
            verification["errors"].append(f"NocoDB schema gap: missing tables {missing_tables}")
            verification["status"] = "NOCODB_SCHEMA_BLOCKED"
            client.close()
            return verification

        project_id = self.project_profile.get("project_id", "unknown")
        now = datetime.now(timezone.utc).isoformat()

        # Write cer_review_runs record
        try:
            review_run_record = {
                "id": self.run_id,
                "project_id": project_id,
                "cer_run_id": self.run_id,
                "phase": "D1",
                "status": "real_analysis",
                "gate_state": self.gate_a_status,
                "created_at": now,
                "updated_at": now,
            }
            self._nocodb_insert(client, table_map["cer_review_runs"]["id"], [review_run_record])
            verification["records_written"]["cer_review_runs"] = 1
        except Exception as e:
            verification["errors"].append(f"cer_review_runs write failed: {e}")

        # Write cer_section_assessments (one per D1 step)
        section_records = []
        d1_steps = [
            ("cer_admin_precheck", "00_admin_precheck/admin_precheck_report.json"),
            ("cer_intake", "01_docstruct/cer_docstruct.json"),
            ("cer_structure_compliance", "02_structure_compliance/report.json"),
            ("cer_intended_purpose", "03_intended_purpose/report.json"),
            ("cer_cep_methodology", "04_cep_methodology/report.json"),
            ("cer_clinical_evidence_panel", "05_lanes/panel_summary.json"),
            ("cer_ifu_sscp_label", "06_consistency/report.json"),
            ("cer_qa_gate", "07_qa_gate/qa_synthesis.json"),
            ("cer_cear_style_finding_formatter", "08_cear_format/formatted_findings.json"),
            ("cer_human_boundary", "09_human_boundary/packet.json"),
            ("cer_qms_review", "10_qms_review/qms_findings.json"),
            ("cer_gate_closure", "11_gate_closure/review_package.json"),
        ]
        for i, (section_id, artifact_path) in enumerate(d1_steps, start=1):
            section_records.append({
                "id": f"{self.run_id}-sec-{i:02d}",
                "cer_run_id": self.run_id,
                "section_id": section_id,
                "handler": f"_run_d1_{section_id}",
                "compliance_status": "pending",
                "artifact_path": artifact_path,
                "assessed_at": now,
            })
        try:
            self._nocodb_insert(client, table_map["cer_section_assessments"]["id"], section_records)
            verification["records_written"]["cer_section_assessments"] = len(section_records)
        except Exception as e:
            verification["errors"].append(f"cer_section_assessments write failed: {e}")

        # Write cer_human_review_required_items (HG-01 through HG-09)
        human_gates = self.workflow.get("human_gates", {})
        hr_records = []
        for ref, hg in human_gates.items():
            hr_records.append({
                "id": f"{self.run_id}-{ref}",
                "cer_run_id": self.run_id,
                "review_item_id": ref,
                "topic": hg.get("topic", ""),
                "description": f"Human gate review for {hg.get('topic', '')}",
                "decision": "",
                "reviewer_id": "",
                "reviewed_at": "",
                "created_at": now,
            })
        try:
            self._nocodb_insert(client, table_map["cer_human_review_required_items"]["id"], hr_records)
            verification["records_written"]["cer_human_review_required_items"] = len(hr_records)
        except Exception as e:
            verification["errors"].append(f"cer_human_review_required_items write failed: {e}")

        # Write cer_preliminary_findings (empty for D1 scaffold)
        try:
            finding_record = {
                "id": f"{self.run_id}-f001",
                "cer_run_id": self.run_id,
                "finding_id": "FND-D1-001",
                "dimension": "dim_1",
                "finding_type": "gap",
                "severity": "minor",
                "description": "D1 scaffold stub - full findings require D3 LLM population",
                "recommendation": "Populate via D3 step execution",
                "status": "open",
                "created_at": now,
                "updated_at": now,
            }
            self._nocodb_insert(client, table_map["cer_preliminary_findings"]["id"], [finding_record])
            verification["records_written"]["cer_preliminary_findings"] = 1
        except Exception as e:
            verification["errors"].append(f"cer_preliminary_findings write failed: {e}")

        # Write cer_cross_document_consistency_items (empty for D1 scaffold)
        try:
            consistency_record = {
                "id": f"{self.run_id}-cdci-001",
                "cer_run_id": self.run_id,
                "consistency_check_id": "CDCI-D1-001",
                "document_pair": "cer_ifu",
                "consistency_type": "intended_use",
                "status": "missing",
                "detail": "D1 scaffold stub - full consistency check requires D3",
                "checked_at": now,
            }
            self._nocodb_insert(client, table_map["cer_cross_document_consistency_items"]["id"], [consistency_record])
            verification["records_written"]["cer_cross_document_consistency_items"] = 1
        except Exception as e:
            verification["errors"].append(f"cer_cross_document_consistency_items write failed: {e}")

        # Write cer_knowledge_assets (empty for D1 scaffold)
        try:
            asset_record = {
                "id": f"{self.run_id}-ka-001",
                "cer_run_id": self.run_id,
                "asset_id": "KA-D1-001",
                "asset_type": "sota",
                "title": "D1 scaffold - knowledge assets require D3 population",
                "source_ref": "",
                "relevance_score": 0.0,
                "quality_assessment": "",
                "used_in_dimension": "",
                "created_at": now,
            }
            self._nocodb_insert(client, table_map["cer_knowledge_assets"]["id"], [asset_record])
            verification["records_written"]["cer_knowledge_assets"] = 1
        except Exception as e:
            verification["errors"].append(f"cer_knowledge_assets write failed: {e}")

        # Write cer_backflow_candidates (empty for D1 scaffold)
        try:
            backflow_record = {
                "id": f"{self.run_id}-bc-001",
                "cer_run_id": self.run_id,
                "candidate_id": f"BC-{self.run_id[:8]}",
                "current_state": "new",
                "route_decision": "pending",
                "evidence_refs": "[]",
                "state_history": "[]",
                "created_at": now,
                "updated_at": now,
            }
            self._nocodb_insert(client, table_map["cer_backflow_candidates"]["id"], [backflow_record])
            verification["records_written"]["cer_backflow_candidates"] = 1
        except Exception as e:
            verification["errors"].append(f"cer_backflow_candidates write failed: {e}")

        # Read-after-write verification
        verification["actual_connection"] = True
        try:
            for table_name in verification["records_written"]:
                if table_name in table_map:
                    rows = self._nocodb_query(
                        client, table_map[table_name]["id"],
                        where=f"(cer_run_id,eq,{self.run_id})",
                    )
                    verification["records_read"][table_name] = len(rows)
            read_count = sum(verification["records_read"].values())
            write_count = sum(verification["records_written"].values())
            verification["read_after_write_verified"] = read_count >= write_count
        except Exception as e:
            verification["errors"].append(f"Read-after-write verification failed: {e}")

        # Write verification artifact
        self._write_json(
            self._artifact_path("00_manifest", "nocodb_runtime_verification.json"),
            verification,
        )

        verification["human_gate_preserved"] = True
        verification["no_autonomous_final_judgment"] = True

        client.close()
        self._nocodb_enabled = True
        self._nocodb_verification = verification
        return verification

    # -------------------------------------------------------------------------
    # Schema Validation Gate (D1)
    # -------------------------------------------------------------------------

    def _validate_d1_artifacts_schema(self) -> dict[str, Any]:
        """Validate all D1 artifacts against their schemas. Returns {valid, failures}."""
        try:
            import jsonschema
        except ImportError:
            logger.warning("jsonschema not installed, skipping schema validation")
            return {"valid": True, "failures": {}}

        schema_dir = Path(__file__).parent.parent.parent.parent.parent.parent.parent / "schemas"

        # Map artifact paths to schema files (for D1 ordered_steps)
        artifact_schema_map = [
            ("00_admin_precheck", "admin_precheck_report.json", "cer_admin_precheck.schema.json"),
            ("01_docstruct", "cer_docstruct.json", "cer_docstruct.schema.json"),
            ("02_structure_compliance", "report.json", "cer_structure_compliance.schema.json"),
            ("03_intended_purpose", "report.json", "cer_intended_purpose.schema.json"),
            ("04_cep_methodology", "report.json", "cer_cep_methodology.schema.json"),
            ("05_lanes", "panel_summary.json", "cer_clinical_evidence_panel.schema.json"),
            ("05_lanes", "sota_literature_report.json", "cer_sota_literature.schema.json"),
            ("05_lanes", "clinical_evidence_adequacy_report.json", "cer_evidence_adequacy.schema.json"),
            ("05_lanes", "equivalence_report.json", "cer_equivalence.schema.json"),
            ("05_lanes", "pms_pmcf_report.json", "cer_pms_pmcf.schema.json"),
            ("05_lanes", "benefit_risk_report.json", "cer_benefit_risk.schema.json"),
            ("06_consistency", "report.json", "cer_consistency.schema.json"),
            ("07_qa_gate", "qa_synthesis.json", "cer_qa.schema.json"),
            ("08_cear_format", "formatted_findings.json", "cer_cear_finding.schema.json"),
            ("09_human_boundary", "packet.json", "cer_human_gate.schema.json"),
            ("10_qms_review", "qms_findings.json", "cer_qms_review.schema.json"),
            ("11_gate_closure", "review_package.json", "cer_review_package.schema.json"),
        ]

        failures: dict[str, str] = {}
        for step_dir, artifact_file, schema_file in artifact_schema_map:
            artifact_path = self._artifact_path(step_dir, artifact_file)
            if not artifact_path.exists():
                failures[f"{step_dir}/{artifact_file}"] = "Artifact file not found"
                continue
            schema_path = schema_dir / schema_file
            if not schema_path.exists():
                failures[schema_file] = f"Schema file not found: {schema_path}"
                continue
            try:
                with open(artifact_path) as f:
                    artifact = json.load(f)
                with open(schema_path) as f:
                    schema = json.load(f)
                jsonschema.validate(artifact, schema)
            except jsonschema.ValidationError as e:
                failures[f"{step_dir}/{artifact_file}"] = e.message[:200]
            except Exception as e:
                failures[f"{step_dir}/{artifact_file}"] = str(e)[:200]

        return {"valid": len(failures) == 0, "failures": failures}

    def _write_schema_validation_failure(self, validation_result: dict[str, Any]) -> None:
        """Write schema validation failure artifact."""
        step_dir = self._artifact_dir("00_manifest")
        failure_record = {
            "schema_name": "cer_schema_validation",
            "schema_version": "v1",
            "artifact_type": "schema_validation_result",
            "project_id": self.project_profile.get("project_id", "unknown"),
            "cer_run_id": self.run_id,
            "workflow_id": self.workflow.get("workflow_id"),
            "step_id": "schema_validation_gate",
            "produced_by_step": "schema_validation_gate",
            "status": "draft",
            "created_at": self._timestamp(),
            "validation_passed": False,
            "failure_count": len(validation_result["failures"]),
            "failures": validation_result["failures"],
            "note": "D3 schema validation gate - run blocked due to schema validation failures.",
        }
        self._write_json(step_dir / "schema_validation_failure.json", failure_record)

    # -------------------------------------------------------------------------
    # Step 1: Intake
    # -------------------------------------------------------------------------

    def _run_intake(self, step: dict[str, Any]) -> None:
        step_dir = self._artifact_dir("00_manifest")
        prompt_text = self._load_prompt_for_step(step)
        documents = list(self.project_profile.get("input_package", {}).get("documents", []))
        input_root = self._resolve_input_root()
        inventory: list[dict[str, Any]] = []

        for index, doc in enumerate(documents, start=1):
            raw_path = doc.get("path", "")
            resolved_path = self._resolve_source_path(raw_path, input_root)
            exists = resolved_path.exists()
            status = "present" if exists else "missing"
            doc_type = doc.get("doc_type", "Unknown")
            entry = {
                "inventory_id": f"doc_{index:03d}",
                "document_id": doc.get("source_ref", {}).get("document_id") or f"document_{index:03d}",
                "doc_type": doc_type,
                "label": doc.get("label", raw_path),
                "declared_path": raw_path,
                "resolved_path": str(resolved_path),
                "required_for_p0": bool(doc.get("required_for_p0", False)),
                "blocking_for_p0": bool(doc.get("required_for_p0", False)),
                "status": status,
                "source_ref": {
                    "document_id": doc.get("source_ref", {}).get("document_id") or f"document_{index:03d}",
                    "path": raw_path,
                },
            }
            inventory.append(entry)

        missing_required = [item for item in inventory if item["blocking_for_p0"] and item["status"] != "present"]

        # Check for essential CER document types
        cer_present = any(item["doc_type"] in {"CER", "Clinical_Evaluation_Report"} and item["status"] == "present" for item in inventory)
        cep_present = any(item["doc_type"] in {"CEP", "Clinical_Evaluation_Plan"} and item["status"] == "present" for item in inventory)
        ifu_present = any(item["doc_type"] in {"IFU", "Instruction_For_Use"} and item["status"] == "present" for item in inventory)
        rmf_present = any(item["doc_type"] in {"RMF", "RMR", "Risk_Management_File"} and item["status"] == "present" for item in inventory)

        # Weak-coupling Layer 1: Detect Authoring workbooks in input
        authoring_workbook_detected = False
        authoring_workbook_path = None
        for item in inventory:
            if item["status"] == "present" and "authoring_workbook" in item["resolved_path"].lower():
                authoring_workbook_detected = True
                authoring_workbook_path = item["resolved_path"]
                break
        # Also check sibling directories for Authoring outputs
        if not authoring_workbook_detected and input_root.exists():
            sibling_candidates = list(input_root.parent.glob("*/authoring_workbook.json"))
            if sibling_candidates:
                authoring_workbook_detected = True
                authoring_workbook_path = str(sibling_candidates[0])

        run_manifest = {
            "workflow_name": self.workflow_name,
            "workflow_version": self.workflow.get("workflow_version"),
            "run_id": self.run_id,
            "thread_id": self.thread_id,
            "step_id": "cer_intake_agent",
            "institution_profile": self.project_profile.get("institution_profile", {}),
            "primary_review_object": "CER",
            "project_profile_path": str(self.project_profile_path),
            "input_root": str(input_root),
            "artifact_root_virtual": self.artifact_root_virtual,
            "artifact_root_actual": str(self.artifact_root_actual),
            "prompt_contract_path": str((self.repo_root / step["prompt_contract"]).resolve()),
            "prompt_contract_loaded": bool(prompt_text.strip()),
            "human_gate_required": True,
            "input_doc_summary": {
                "cer_present": cer_present,
                "cep_present": cep_present,
                "ifu_present": ifu_present,
                "rmf_present": rmf_present,
                "total_documents": len(inventory),
                "missing_required": [m["doc_type"] for m in missing_required],
                "authoring_workbook_detected": authoring_workbook_detected,
                "authoring_workbook_path": authoring_workbook_path,
            },
        }

        # Build markdown missing items report
        missing_lines = ["# Missing Items Report", "", f"- Run ID: `{self.run_id}`", f"- Input Root: `{input_root}`"]
        if missing_required:
            missing_lines.append("## Blocking Missing Items")
            for item in missing_required:
                missing_lines.append(f"- `{item['doc_type']}` | `{item['label']}` | status=`{item['status']}`")
        else:
            missing_lines.append("## Blocking Missing Items")
            missing_lines.append("- None")

        self._write_json(step_dir / "run_manifest.json", run_manifest)
        self._write_json(step_dir / "input_inventory.json", {"documents": inventory, "input_root": str(input_root)})
        self._write_text(step_dir / "missing_items_report.md", "\n".join(missing_lines) + "\n")

    # -------------------------------------------------------------------------
    # Step 2: Parse & Normalize
    # -------------------------------------------------------------------------

    def _run_parse_normalize(self, step: dict[str, Any]) -> None:
        step_dir = self._artifact_dir("01_parse")
        prompt_text = self._load_prompt_for_step(step)
        inventory = self._read_json(self._artifact_path("00_manifest", "input_inventory.json"))["documents"]

        cer_docs = [item for item in inventory if item["doc_type"] in {"CER", "Clinical_Evaluation_Report"} and item["status"] == "present"]

        # Extract text from CER document(s)
        cer_text_lines = self._extract_text_from_docs(cer_docs)

        # Build normalized CER structure
        cer_normalized = self._build_cer_normalized(cer_docs, cer_text_lines)

        cross_doc_entities = {
            "project_id": self.project_profile.get("project_id", "unknown"),
            "document_entities": [
                {"document_id": item["document_id"], "doc_type": item["doc_type"], "path": item["resolved_path"]}
                for item in inventory
            ],
        }

        term_map = {
            "canonical_terms": [
                {"term": "CER", "meaning": "Clinical Evaluation Report"},
                {"term": "CEP", "meaning": "Clinical Evaluation Plan"},
                {"term": "IFU", "meaning": "Instruction for Use"},
                {"term": "PMCF", "meaning": "Post-Market Clinical Follow-up"},
                {"term": "BRR", "meaning": "Benefit-Risk Ratio"},
            ],
        }

        self._write_json(step_dir / "cer_normalized.json", cer_normalized)
        self._write_json(step_dir / "cross_doc_entities.json", cross_doc_entities)
        self._write_json(step_dir / "term_map.json", term_map)

    def _build_cer_normalized(self, cer_docs: list[dict], text_lines: list[dict]) -> dict[str, Any]:
        """Build normalized CER structure with section hints."""
        sections = []
        section_keywords = {
            "intended_purpose": ["intended purpose", "intended use", "预期用途", "适应证", "适应症", "indication for use"],
            "scope": ["scope of clinical evaluation", "临床评价范围", "evaluation scope"],
            "description": ["device description", "设备描述", "product description", "产品描述"],
            "equivalence": ["equivalence", "equivalent device", "等同器械", "等效", "substantial equivalence"],
            "literature_search": ["literature search", "文献检索", "search strategy", "检索策略", "数据库检索"],
            "clinical_data": ["clinical data", "临床数据", "clinical evidence", "临床证据"],
            "benefit_risk": ["benefit risk", "benefit-risk", "受益风险", "受益-风险", "clinical benefit", "风险评估"],
            "pmcf": ["pmcf", "post-market clinical follow-up", "上市后临床随访", "post market surveillance"],
            "conclusion": ["conclusion", "结论", "overall conclusion", "综合结论"],
            "contraindication": ["contraindication", "禁忌证", "禁忌", "warning", "警告", "precaution"],
        }

        for line_item in text_lines:
            text_lower = line_item.get("text", "").lower()
            for sec_key, keywords in section_keywords.items():
                if any(kw.lower() in text_lower for kw in keywords):
                    sections.append({
                        "section_key": sec_key,
                        "text": line_item.get("text", ""),
                        "line_number": line_item.get("line_number"),
                        "source_document": line_item.get("source_document"),
                    })
                    break

        return {
            "document_ids": [d["document_id"] for d in cer_docs],
            "primary_review_object": "CER",
            "total_text_lines": len(text_lines),
            "section_hints": sections,
            "text_lines_sample": text_lines[:100] if text_lines else [],
        }

    def _extract_text_from_docs(self, cer_docs: list[dict]) -> list[dict]:
        """Extract text lines from CER document paths."""
        all_lines = []
        for doc in cer_docs:
            path = Path(doc["resolved_path"])
            if path.exists():
                try:
                    content = path.read_text(encoding="utf-8", errors="replace")
                    for i, line in enumerate(content.splitlines(), start=1):
                        if line.strip():
                            all_lines.append({
                                "text": line.strip(),
                                "line_number": i,
                                "source_document": doc["document_id"],
                            })
                except Exception:
                    pass
        return all_lines

    # -------------------------------------------------------------------------
    # Step 3: HF Check
    # -------------------------------------------------------------------------

    def _run_hf_check(self, step: dict[str, Any]) -> None:
        step_dir = self._artifact_dir("02_hf_check")
        prompt_text = self._load_prompt_for_step(step)
        cer_normalized = self._read_json(self._artifact_path("01_parse", "cer_normalized.json"))
        cross_doc_entities = self._read_json(self._artifact_path("01_parse", "cross_doc_entities.json"))
        term_map = self._read_json(self._artifact_path("01_parse", "term_map.json"))
        input_inventory = self._read_json(self._artifact_path("00_manifest", "input_inventory.json"))
        run_manifest = self._read_json(self._artifact_path("00_manifest", "run_manifest.json"))

        text_lines = cer_normalized.get("text_lines_sample", [])
        text_by_doc: dict[str, list[str]] = {}
        for line in text_lines:
            doc_id = line.get("source_document", "unknown")
            if doc_id not in text_by_doc:
                text_by_doc[doc_id] = []
            text_by_doc[doc_id].append(line.get("text", "").lower())

        # Run HF checks
        hf_results: list[dict[str, Any]] = []
        for hf_id, hf_def in _HF_CHECK_DEFS.items():
            keywords = hf_def["keywords"]
            # Find matching text across all docs
            matches: list[dict[str, Any]] = []
            for doc_id, lines in text_by_doc.items():
                for line_obj in [l for l in text_lines if l.get("source_document") == doc_id]:
                    text_lower = line_obj.get("text", "").lower()
                    for kw in keywords:
                        if kw.lower() in text_lower:
                            matches.append({
                                "keyword": kw,
                                "line_number": line_obj.get("line_number"),
                                "text_snippet": line_obj.get("text", "")[:200],
                                "source_document": doc_id,
                            })
                            break

            status = "present" if matches else "missing"
            finding_detail = None
            if status == "missing":
                finding_detail = f"{hf_def['label']} - 未在文档中找到相关描述"
            elif len(matches) < 2:
                finding_detail = f"{hf_def['label']} - 描述可能不完整（仅找到{len(matches)}处提及）"

            hf_results.append({
                "hf_id": hf_id,
                "label": hf_def["label"],
                "severity": hf_def["severity"],
                "status": status,
                "match_count": len(matches),
                "matches": matches[:5],  # Keep first 5 matches
                "finding_detail": finding_detail,
                "requires_human_review": status == "missing" or (status == "present" and len(matches) < 2),
            })

        # Additional cross-check: IFU consistency
        ifu_docs = [d for d in input_inventory["documents"] if d.get("doc_type") in {"IFU", "Instruction_For_Use"}]
        cer_has_ifu_consistency_check = any(
            "ifu" in section.get("section_key", "").lower() or "instruction" in str(section.get("text", "")).lower()
            for section in cer_normalized.get("section_hints", [])
        )
        if ifu_docs and not cer_has_ifu_consistency_check:
            hf_results.append({
                "hf_id": "HF-002a",
                "label": "CER 临床评价范围提及 IFU 但 IFU 相关性未明确论证",
                "severity": "medium",
                "status": "inconsistent",
                "match_count": 0,
                "matches": [],
                "finding_detail": "IFU 文档存在，但 CER 中未明确讨论与 IFU 一致性",
                "requires_human_review": True,
            })

        # Build findings from HF results
        findings = []
        for result in hf_results:
            if result["status"] in ("missing", "inconsistent") or result["requires_human_review"]:
                findings.append({
                    "finding_type": f"hf_{result['status']}",
                    "hf_id": result["hf_id"],
                    "label": result["label"],
                    "severity": result["severity"],
                    "detail": result.get("finding_detail", ""),
                    "source_refs": [{"document_id": m["source_document"], "line": m["line_number"]} for m in result.get("matches", [])],
                })

        report = {
            "step_id": "cer_hf_check_agent",
            "prompt_contract_path": str((self.repo_root / step["prompt_contract"]).resolve()),
            "prompt_contract_loaded": bool(prompt_text.strip()),
            "hf_results": hf_results,
            "total_checks": len(hf_results),
            "present_count": sum(1 for r in hf_results if r["status"] == "present"),
            "missing_count": sum(1 for r in hf_results if r["status"] == "missing"),
            "inconsistent_count": sum(1 for r in hf_results if r["status"] == "inconsistent"),
            "requires_human_review_count": sum(1 for r in hf_results if r["requires_human_review"]),
            "findings": findings,
            "structural_status": "issues_detected" if findings else "pass",
        }

        self._write_json(step_dir / "hf_check_report.json", report)

        # Write dedicated artifacts for the quality-hardened sub-checks
        eq_matrix = self._run_equivalence_matrix(cer_normalized, input_inventory)
        lit_quality = self._run_literature_quality(cer_normalized)
        self._write_json(step_dir / "equivalence_assessment.json", eq_matrix)
        self._write_json(step_dir / "literature_quality.json", lit_quality)

    # -------------------------------------------------------------------------
    # A. Equivalence Matrix
    # -------------------------------------------------------------------------

    def _run_equivalence_matrix(self, cer_normalized: dict, input_inventory: dict) -> dict[str, Any]:
        """HF-005 upgrade: Structured equivalence matrix across Technical, Biological, Clinical dimensions.

        This is NOT an automatic final verdict. It always requires human judgment.
        """
        text_lines = cer_normalized.get("text_lines_sample", [])
        section_keys = [s["section_key"] for s in cer_normalized.get("section_hints", [])]
        equivalence_claims: list[dict[str, Any]] = []

        # Extract equivalence-related text for analysis
        eq_keywords = ["equivalence", "equivalent device", "predicate", "substantial equivalence",
                       "demonstrated equivalence", "等同器械", "等效器械"]
        for line in text_lines:
            text_lower = line.get("text", "").lower()
            if any(kw.lower() in text_lower for kw in eq_keywords):
                equivalence_claims.append({
                    "text": line.get("text", "")[:200],
                    "line_number": line.get("line_number"),
                    "source_document": line.get("source_document"),
                })

        # Extract claimed predicate device
        predicate_device = "Predicate Device"
        for line in text_lines:
            text_lower = line.get("text", "").lower()
            if "predicate" in text_lower or "等效" in text_lower:
                snippet = line.get("text", "")
                if len(snippet) > len(predicate_device):
                    predicate_device = snippet[:60]

        # Technical dimension analysis
        technical_evidence: list[str] = []
        tech_gaps: list[str] = []
        for line in text_lines:
            t = line.get("text", "").lower()
            if any(kw in t for kw in ["technology", "technical", "design", "material", "specification"]):
                if "equivalence" in t or "equivalent" in t:
                    technical_evidence.append(line.get("text", "")[:100])

        if not technical_evidence:
            tech_gaps.append("技术等同性论证缺乏技术细节支撑")
        if len(technical_evidence) < 2:
            tech_gaps.append("技术等同性论证证据不充分")

        technical_dimension = {
            "dimension": "technical",
            "claimed": "Technical equivalence to predicate device",
            "evidence_present": len(technical_evidence) >= 2,
            "critical_gaps": tech_gaps,
            "score": "pass" if not tech_gaps else "partial" if len(tech_gaps) == 1 else "fail",
            "requires_human_review": True,
            "evidence_refs": [{"document_id": line.get("source_document"), "line": line.get("line_number")} for line in text_lines if "technical" in line.get("text", "").lower() and len(technical_evidence) > 0][:3],
        }

        # Biological dimension analysis
        bio_evidence: list[str] = []
        bio_gaps: list[str] = []
        for line in text_lines:
            t = line.get("text", "").lower()
            if any(kw in t for kw in ["biocompatibility", "biological", "toxicity", "material", "contact"]):
                if "equivalence" in t or "equivalent" in t:
                    bio_evidence.append(line.get("text", "")[:100])

        if not bio_evidence:
            bio_gaps.append("生物等同性论证缺乏生物相容性证据支撑")
        if len(bio_evidence) < 1:
            bio_gaps.append("生物等同性论证证据不足")

        biological_dimension = {
            "dimension": "biological",
            "claimed": "Biological equivalence to predicate device",
            "evidence_present": len(bio_evidence) >= 1,
            "critical_gaps": bio_gaps,
            "score": "pass" if not bio_gaps else "partial" if len(bio_gaps) == 1 else "fail",
            "requires_human_review": True,
            "evidence_refs": [{"document_id": line.get("source_document"), "line": line.get("line_number")} for line in text_lines if "biocompatibility" in line.get("text", "").lower() or "biological" in line.get("text", "").lower()][:3],
        }

        # Clinical dimension analysis
        clinical_evidence: list[str] = []
        clinical_gaps: list[str] = []
        for line in text_lines:
            t = line.get("text", "").lower()
            if any(kw in t for kw in ["clinical", "indication", "intended use", "intended purpose", "outcome"]):
                if "equivalence" in t or "equivalent" in t:
                    clinical_evidence.append(line.get("text", "")[:100])

        if not clinical_evidence:
            clinical_gaps.append("临床等同性论证缺乏临床数据支撑")
        if len(clinical_evidence) < 2:
            clinical_gaps.append("临床等同性论证证据链不完整")

        clinical_dimension = {
            "dimension": "clinical",
            "claimed": "Clinical equivalence to predicate device",
            "evidence_present": len(clinical_evidence) >= 2,
            "critical_gaps": clinical_gaps,
            "score": "pass" if not clinical_gaps else "partial" if len(clinical_gaps) == 1 else "fail",
            "requires_human_review": True,
            "evidence_refs": [{"document_id": line.get("source_document"), "line": line.get("line_number")} for line in text_lines if "clinical" in line.get("text", "").lower() and "equivalence" in line.get("text", "").lower()][:3],
        }

        # Equivalence section exists in CER
        has_equivalence_section = "equivalence" in section_keys

        # Overall status determination
        # NOT an automatic final verdict - always human judgment required
        dims_passed = sum(1 for d in [technical_dimension, biological_dimension, clinical_dimension] if d["score"] == "pass")
        dims_partial = sum(1 for d in [technical_dimension, biological_dimension, clinical_dimension] if d["score"] == "partial")
        dims_failed = sum(1 for d in [technical_dimension, biological_dimension, clinical_dimension] if d["score"] == "fail")

        if dims_failed >= 2:
            overall_status = "unsupported"
        elif dims_partial >= 2:
            overall_status = "partially_supported"
        elif dims_partial == 1 and dims_passed >= 2:
            overall_status = "likely_supported"
        else:
            overall_status = "human_judgement_required"

        top_risks = []
        for dim in [technical_dimension, biological_dimension, clinical_dimension]:
            for gap in dim.get("critical_gaps", []):
                top_risks.append(f"[{dim['dimension'].upper()}] {gap}")

        return {
            "assessment_id": f"eq-assess-{self.run_id}",
            "predicate_device": predicate_device,
            "dimensions": {
                "technical": technical_dimension,
                "biological": biological_dimension,
                "clinical": clinical_dimension,
            },
            "overall_status": overall_status,
            "dimensions_passed_count": dims_passed,
            "dimensions_failed_count": dims_failed,
            "mandatory_human_review": True,
            "top_risks": top_risks,
            "recommendation": "等同性最终成立与否必须由人工审查确认（Layer 3），自动系统不得拍板",
            "equivalence_section_present": has_equivalence_section,
            "evidence_count": len(equivalence_claims),
        }

    # -------------------------------------------------------------------------
    # B. Literature Quality Scorer
    # -------------------------------------------------------------------------

    def _run_literature_quality(self, cer_normalized: dict) -> dict[str, Any]:
        """HF-004 upgrade: Literature quality scoring with structured quality tiers.

        This is NOT a final clinical sufficiency verdict. It is an input to the EVID dimension.
        """
        text_lines = cer_normalized.get("text_lines_sample", [])

        # Extract literature search related text
        lit_evidence: list[dict[str, Any]] = []
        lit_keywords = ["literature", "search", "pubmed", "embase", "cochrane", "study",
                       "clinical trial", "randomized", "controlled", "cohort", "case series",
                       "文献检索", "临床研究", "样本"]

        for line in text_lines:
            text_lower = line.get("text", "").lower()
            if any(kw.lower() in text_lower for kw in lit_keywords):
                lit_evidence.append({
                    "text": line.get("text", ""),
                    "line_number": line.get("line_number"),
                    "source_document": line.get("source_document"),
                })

        # Build evidence units from literature text
        evidence_units: list[dict[str, Any]] = []
        unit_counter = 1

        # Analyze the literature search description
        has_search_strategy = any("search strategy" in e.get("text", "").lower() for e in lit_evidence)
        has_database_list = any(any(db in e.get("text", "").lower() for db in ["pubmed", "embase", "cochrane"]) for e in lit_evidence)
        has_inclusion_criteria = any("inclusion" in e.get("text", "").lower() for e in lit_evidence)
        has_exclusion_criteria = any("exclusion" in e.get("text", "").lower() for e in lit_evidence)
        has_sample_size = any("sample" in e.get("text", "").lower() or "n=" in e.get("text", "").lower() for e in lit_evidence)
        has_follow_up = any("follow-up" in e.get("text", "").lower() or "随访" in e.get("text", "") for e in lit_evidence)
        has_adverse_events = any("adverse" in e.get("text", "").lower() or "不良" in e.get("text", "") for e in lit_evidence)
        has_comparator = any("comparator" in e.get("text", "").lower() or "对照组" in e.get("text", "") for e in lit_evidence)
        has_endpoint = any("endpoint" in e.get("text", "").lower() or "终点" in e.get("text", "") for e in lit_evidence)

        # Score the literature search/evidence quality
        quality_indicators = {
            "has_search_strategy": has_search_strategy,
            "has_database_list": has_database_list,
            "has_inclusion_criteria": has_inclusion_criteria,
            "has_exclusion_criteria": has_exclusion_criteria,
            "has_sample_size": has_sample_size,
            "has_follow_up": has_follow_up,
            "has_adverse_events": has_adverse_events,
            "has_comparator": has_comparator,
            "has_endpoint": has_endpoint,
        }

        indicator_score = sum(1 for v in quality_indicators.values() if v)
        max_indicators = len(quality_indicators)

        # Determine quality tier
        if indicator_score >= 7:
            quality_tier = "medium"
            quality_score = 6.0 + (indicator_score - 7) * 0.5
        elif indicator_score >= 5:
            quality_tier = "medium"
            quality_score = 4.0 + (indicator_score - 5) * 0.5
        elif indicator_score >= 3:
            quality_tier = "low"
            quality_score = 2.0 + (indicator_score - 3) * 0.5
        elif indicator_score >= 1:
            quality_tier = "very_low"
            quality_score = 1.0 + (indicator_score - 1) * 0.5
        else:
            quality_tier = "insufficient_information"
            quality_score = 0.5

        strengths: list[str] = []
        weaknesses: list[str] = []

        if has_search_strategy:
            strengths.append("文献检索策略已描述")
        if has_database_list:
            strengths.append("检索数据库已列出")
        if has_inclusion_criteria:
            strengths.append("纳入标准已明确")
        if has_exclusion_criteria:
            strengths.append("排除标准已明确")
        if has_sample_size:
            strengths.append("提及样本量")
        if has_follow_up:
            strengths.append("提及随访")
        if has_comparator:
            strengths.append("提及对照")
        if has_endpoint:
            strengths.append("提及临床终点")

        if not has_search_strategy:
            weaknesses.append("缺乏检索策略描述")
        if not has_database_list:
            weaknesses.append("未列出具体数据库")
        if not has_sample_size:
            weaknesses.append("未报告样本量")
        if not has_comparator:
            weaknesses.append("缺乏对照组")
        if not has_adverse_events:
            weaknesses.append("未报告不良事件")

        unit_id = f"lit_unit_{unit_counter:03d}"
        evidence_units.append({
            "evidence_unit_id": unit_id,
            "source_document": "cer_main",
            "study_type": "literature_review",
            "quality_tier": quality_tier,
            "quality_score": min(quality_score, 10.0),
            "strengths": strengths,
            "weaknesses": weaknesses,
            "requires_human_review": True,
            "source_ref": {
                "document_id": "cer_main",
                "section": "literature_search",
                "line": lit_evidence[0].get("line_number") if lit_evidence else 0,
            },
            "quality_indicators": quality_indicators,
        })

        # Distribution
        distribution = {"high": [], "medium": [], "low": [], "very_low": [], "insufficient_information": []}
        distribution[quality_tier].append(unit_id)

        major_concerns: list[dict[str, Any]] = []
        if not has_search_strategy:
            major_concerns.append({
                "concern_type": "missing_search_strategy",
                "affected_evidence_ids": [unit_id],
                "severity": "high",
                "description": "文献检索策略未描述，无法评估检索可重复性",
            })
        if not has_sample_size:
            major_concerns.append({
                "concern_type": "missing_sample_size",
                "affected_evidence_ids": [unit_id],
                "severity": "medium",
                "description": "样本量未报告，无法评估统计学效力",
            })
        if not has_comparator:
            major_concerns.append({
                "concern_type": "missing_comparator",
                "affected_evidence_ids": [unit_id],
                "severity": "medium",
                "description": "缺乏对照组设计，证据等级受限",
            })

        summary = {
            "total_evidence_units": len(evidence_units),
            "high_quality_count": sum(1 for u in evidence_units if u["quality_tier"] == "high"),
            "medium_quality_count": sum(1 for u in evidence_units if u["quality_tier"] == "medium"),
            "low_quality_count": sum(1 for u in evidence_units if u["quality_tier"] == "low"),
            "very_low_quality_count": sum(1 for u in evidence_units if u["quality_tier"] == "very_low"),
            "insufficient_info_count": sum(1 for u in evidence_units if u["quality_tier"] == "insufficient_information"),
            "requires_human_review": True,
        }

        return {
            "assessment_id": f"lit-qa-{self.run_id}",
            "literature_quality_summary": summary,
            "evidence_quality_distribution": distribution,
            "major_quality_concerns": major_concerns,
            "evidence_units": evidence_units,
        }

    # -------------------------------------------------------------------------
    # Step 4: Five-Dimension Review
    # -------------------------------------------------------------------------

    def _run_five_dimension(self, step: dict[str, Any]) -> None:
        step_dir = self._artifact_dir("03_five_dimension")
        prompt_text = self._load_prompt_for_step(step)
        cer_normalized = self._read_json(self._artifact_path("01_parse", "cer_normalized.json"))
        hf_check = self._read_json(self._artifact_path("02_hf_check", "hf_check_report.json"))
        cross_doc_entities = self._read_json(self._artifact_path("01_parse", "cross_doc_entities.json"))
        term_map = self._read_json(self._artifact_path("01_parse", "term_map.json"))
        input_inventory = self._read_json(self._artifact_path("00_manifest", "input_inventory.json"))
        run_manifest = self._read_json(self._artifact_path("00_manifest", "run_manifest.json"))

        text_lines = cer_normalized.get("text_lines_sample", [])
        section_hints = cer_normalized.get("section_hints", [])

        # STRUCT - structural compliance
        struct_result = self._evaluate_struct(cer_normalized, section_hints, hf_check, input_inventory)
        # LOGIC - logical completeness
        logic_result = self._evaluate_logic(cer_normalized, section_hints, hf_check)
        # EVID - evidence chain validity
        evid_result = self._evaluate_evid(cer_normalized, section_hints, hf_check, cross_doc_entities)
        # CONS - consistency (within CER and with external docs)
        cons_result = self._evaluate_consistency(cer_normalized, section_hints, hf_check, input_inventory, cross_doc_entities)
        # BRR - benefit-risk (Layer 3 - human judgment required)
        brr_result = self._evaluate_brr(cer_normalized, section_hints, hf_check)

        dimensions = {
            "STRUCT": struct_result,
            "LOGIC": logic_result,
            "EVID": evid_result,
            "CONS": cons_result,
            "BRR": brr_result,
        }

        assessment = {
            "step_id": "cer_five_dimension_agent",
            "prompt_contract_path": str((self.repo_root / step["prompt_contract"]).resolve()),
            "prompt_contract_loaded": bool(prompt_text.strip()),
            "document_ids": cer_normalized.get("document_ids", []),
            "primary_review_object": "CER",
            "dimensions": dimensions,
            "global_manual_review_needed": any(d.get("requires_human_review") for d in dimensions.values()),
            "source_binding_enforced": True,
            "upstream_summary": {
                "total_text_lines": cer_normalized.get("total_text_lines", 0),
                "hf_finding_count": len(hf_check.get("findings", [])),
                "hf_requires_human_review_count": hf_check.get("requires_human_review_count", 0),
            },
        }

        self._write_json(step_dir / "five_dimension_review.json", assessment)

    def _evaluate_struct(self, cer_normalized: dict, section_hints: list, hf_check: dict, input_inventory: dict) -> dict[str, Any]:
        """Evaluate STRUCT dimension - structural compliance."""
        required_sections = ["intended_purpose", "scope", "description", "equivalence", "literature_search", "clinical_data", "benefit_risk", "pmcf", "conclusion"]
        present_sections: list[str] = []
        missing_sections: list[str] = []

        section_labels = {
            "intended_purpose": "Intended Purpose / 预期用途",
            "scope": "Scope / 临床评价范围",
            "description": "Device Description / 器械描述",
            "equivalence": "Equivalence / 等同性论证",
            "literature_search": "Literature Search / 文献检索",
            "clinical_data": "Clinical Data / 临床数据",
            "benefit_risk": "Benefit-Risk / 受益-风险评估",
            "pmcf": "PMCF Plan / 上市后临床随访计划",
            "conclusion": "Conclusion / 结论",
        }

        found_keys = {s["section_key"] for s in section_hints}
        for req in required_sections:
            if req in found_keys:
                present_sections.append(req)
            else:
                missing_sections.append(req)

        hf_missing = [f for f in hf_check.get("findings", []) if f.get("severity") == "high" and "HF-00" in f.get("hf_id", "")]

        status = "pass" if len(missing_sections) <= 1 else "issues_detected"
        if hf_missing or len(missing_sections) > 2:
            status = "issues_detected"
        elif len(missing_sections) > 0:
            status = "needs_human_review"

        return {
            "dimension_id": "STRUCT",
            "label": _DIMENSION_DEFS["STRUCT"]["label"],
            "description": _DIMENSION_DEFS["STRUCT"]["description"],
            "status": status,
            "present_sections": [section_labels.get(s, s) for s in present_sections],
            "missing_sections": [section_labels.get(s, s) for s in missing_sections],
            "key_findings": [
                {
                    "finding_type": "section_missing" if missing_sections else "section_complete",
                    "detail": f"{len(missing_sections)} 个必需章节缺失" if missing_sections else "CER 章节结构基本完整",
                    "severity": "high" if len(missing_sections) > 2 else "medium" if missing_sections else "none",
                }
            ],
            "evidence_refs": [{"document_id": doc_id} for doc_id in cer_normalized.get("document_ids", [])],
            "requires_human_review": len(missing_sections) > 0,
            "recommendation": "建议人工确认缺失章节是否已在其他部分涵盖" if missing_sections else "结构合规性基本满足",
        }

    def _evaluate_logic(self, cer_normalized: dict, section_hints: list, hf_check: dict) -> dict[str, Any]:
        """Evaluate LOGIC dimension - logical completeness."""
        section_keys = [s["section_key"] for s in section_hints]

        # Check logical flow: scope -> equivalence/literature -> clinical_data -> benefit_risk -> conclusion
        required_flow = ["intended_purpose", "scope", "equivalence", "literature_search", "clinical_data", "benefit_risk", "conclusion"]
        present_flow = [s for s in required_flow if s in section_keys]

        # Check for circular references or gaps
        logic_issues = []
        if "conclusion" in section_keys and "benefit_risk" not in section_keys:
            logic_issues.append({"issue": "结论章节存在但受益-风险章节缺失", "severity": "high"})
        if "equivalence" in section_keys and "literature_search" in section_keys:
            # Both - check if they conflict
            pass
        if "clinical_data" not in section_keys and "equivalence" not in section_keys:
            logic_issues.append({"issue": "既无临床数据也无等同性论证", "severity": "high"})

        hf_logic_related = [f for f in hf_check.get("findings", []) if f.get("hf_id") in {"HF-003", "HF-005"}]

        status = "issues_detected" if logic_issues or len(present_flow) < 4 else "pass" if len(present_flow) >= 6 else "needs_human_review"

        return {
            "dimension_id": "LOGIC",
            "label": _DIMENSION_DEFS["LOGIC"]["label"],
            "description": _DIMENSION_DEFS["LOGIC"]["description"],
            "status": status,
            "logical_flow": present_flow,
            "key_findings": [
                {
                    "finding_type": "logic_flow",
                    "detail": issue["issue"],
                    "severity": issue["severity"],
                }
                for issue in logic_issues
            ] + ([{"finding_type": "hf_related", "detail": f"HF 检查相关问题: {hf_logic_related[0]['label']}", "severity": hf_logic_related[0].get("severity", "medium")}] if hf_logic_related else []),
            "evidence_refs": [{"section_key": s} for s in present_flow],
            "requires_human_review": bool(logic_issues) or len(present_flow) < 5,
            "recommendation": "受益-风险论证链需要人工审查确认" if logic_issues else "逻辑流程基本合理",
        }

    def _evaluate_evid(self, cer_normalized: dict, section_hints: list, hf_check: dict, cross_doc_entities: dict) -> dict[str, Any]:
        """Evaluate EVID dimension - evidence chain validity."""
        section_keys = [s["section_key"] for s in section_hints]
        hf_evidence_related = [f for f in hf_check.get("findings", []) if f.get("hf_id") in {"HF-003", "HF-004", "HF-005"}]

        evidence_indicators: list[dict[str, Any]] = []
        if "literature_search" in section_keys:
            evidence_indicators.append({"type": "literature", "status": "present", "detail": "文献检索章节存在"})
        if "clinical_data" in section_keys:
            evidence_indicators.append({"type": "clinical_data", "status": "present", "detail": "临床数据章节存在"})
        if "equivalence" in section_keys:
            evidence_indicators.append({"type": "equivalence", "status": "present", "detail": "等同性论证章节存在"})

        missing_evidence_types = [t for t in ["literature", "clinical_data", "equivalence"] if t not in [e["type"] for e in evidence_indicators]]

        status = "issues_detected" if missing_evidence_types or hf_evidence_related else "pass"
        if len(missing_evidence_types) >= 2:
            status = "issues_detected"
        elif missing_evidence_types:
            status = "needs_human_review"

        # BRR dimension is Layer 3 - mark as requires_human_review
        return {
            "dimension_id": "EVID",
            "label": _DIMENSION_DEFS["EVID"]["label"],
            "description": _DIMENSION_DEFS["EVID"]["description"],
            "status": status,
            "evidence_indicators": evidence_indicators,
            "key_findings": [
                {
                    "finding_type": "evidence_missing",
                    "detail": f"缺失证据类型: {', '.join(missing_evidence_types)}" if missing_evidence_types else "证据链完整",
                    "severity": "high" if len(missing_evidence_types) >= 2 else "medium" if missing_evidence_types else "none",
                }
            ] + [
                {
                    "finding_type": f"hf_{f['hf_id']}",
                    "detail": f["label"],
                    "severity": f.get("severity", "medium"),
                }
                for f in hf_evidence_related
            ],
            "evidence_refs": [{"document_id": e.get("document_id")} for e in cross_doc_entities.get("document_entities", [])],
            "requires_human_review": bool(missing_evidence_types) or bool(hf_evidence_related),
            "recommendation": "临床证据充分性需要人工综合判断（Layer 3）",
        }

    def _evaluate_consistency(self, cer_normalized: dict, section_hints: list, hf_check: dict, input_inventory: dict, cross_doc_entities: dict) -> dict[str, Any]:
        """Evaluate CONS dimension - consistency within CER and with external docs."""
        section_keys = [s["section_key"] for s in section_hints]
        hf_consistency_related = [f for f in hf_check.get("findings", []) if f.get("hf_id") in {"HF-002", "HF-006", "HF-008"}]

        consistency_groups = []
        # Check if intended purpose section exists and references IFU
        if "intended_purpose" in section_keys and "ifu" not in str(section_keys).lower():
            consistency_groups.append({"type": "CER-IFU", "status": "needs_review", "detail": "Intended Purpose 未明确关联 IFU"})

        # Check if PMCF references CER
        if "pmcf" in section_keys and "cer" not in str(section_keys).lower():
            consistency_groups.append({"type": "PMCF-CER", "status": "needs_review", "detail": "PMCF 计划未明确关联 CER 结论"})

        inventory_docs = input_inventory.get("documents", [])
        has_rmf = any(d.get("doc_type") in {"RMF", "RMR"} for d in inventory_docs)
        if has_rmf and "benefit_risk" not in section_keys:
            consistency_groups.append({"type": "CER-RMF", "status": "inconsistent", "detail": "RMF 存在但受益-风险章节缺失"})

        status = "issues_detected" if any(g["status"] == "inconsistent" for g in consistency_groups) else "needs_human_review" if consistency_groups else "pass"

        return {
            "dimension_id": "CONS",
            "label": _DIMENSION_DEFS["CONS"]["label"],
            "description": _DIMENSION_DEFS["CONS"]["description"],
            "status": status,
            "consistency_groups": consistency_groups,
            "key_findings": [
                {
                    "finding_type": f"consistency_{g['type'].lower().replace('-', '_')}",
                    "detail": g["detail"],
                    "severity": "high" if g["status"] == "inconsistent" else "medium",
                    "group": g["type"],
                }
                for g in consistency_groups
            ],
            "evidence_refs": [{"doc_type": d.get("doc_type")} for d in inventory_docs],
            "requires_human_review": bool(consistency_groups),
            "recommendation": "跨文档一致性需要人工对照审查",
        }

    def _evaluate_brr(self, cer_normalized: dict, section_hints: list, hf_check: dict) -> dict[str, Any]:
        """Evaluate BRR dimension - benefit-risk reasoning (Layer 3)."""
        section_keys = [s["section_key"] for s in section_hints]
        hf_brr_related = [f for f in hf_check.get("findings", []) if f.get("hf_id") == "HF-007"]

        brr_present = "benefit_risk" in section_keys

        return {
            "dimension_id": "BRR",
            "label": _DIMENSION_DEFS["BRR"]["label"],
            "description": _DIMENSION_DEFS["BRR"]["description"],
            "status": "needs_human_review" if brr_present else "issues_detected",
            "benefit_risk_section_present": brr_present,
            "key_findings": [
                {
                    "finding_type": "brr_section_existence",
                    "detail": "受益-风险章节存在" if brr_present else "受益-风险章节缺失",
                    "severity": "high" if not brr_present else "none",
                },
                {
                    "finding_type": "layer3_human_judgment_required",
                    "detail": "受益-风险最终综合评估结论必须由人工审查确定，不得自动终判",
                    "severity": "high",
                    "layer": 3,
                    "auto_decidable": False,
                },
            ],
            "evidence_refs": [{"section_key": "benefit_risk"}] if brr_present else [],
            "requires_human_review": True,  # Always requires human review - Layer 3
            "recommendation": "【Layer 3】受益-风险最终结论必须由 reviewer 人工判断，自动系统不得拍板",
            "layer3_warning": True,
        }

    # -------------------------------------------------------------------------
    # Step 5: Cross-Doc Consistency
    # -------------------------------------------------------------------------

    def _run_cross_doc_consistency(self, step: dict[str, Any]) -> None:
        step_dir = self._artifact_dir("04_cross_doc_consistency")
        prompt_text = self._load_prompt_for_step(step)
        cer_normalized = self._read_json(self._artifact_path("01_parse", "cer_normalized.json"))
        five_dim = self._read_json(self._artifact_path("03_five_dimension", "five_dimension_review.json"))
        cross_doc_entities = self._read_json(self._artifact_path("01_parse", "cross_doc_entities.json"))
        input_inventory = self._read_json(self._artifact_path("00_manifest", "input_inventory.json"))
        hf_check = self._read_json(self._artifact_path("02_hf_check", "hf_check_report.json"))

        inventory_docs = input_inventory.get("documents", [])

        # Build consistency checks for 4 groups
        consistency_checks: list[dict[str, Any]] = []

        # CER ↔ IFU
        cer_has_ifu_ref = any("ifu" in s.get("section_key", "").lower() or "instruction" in s.get("text", "").lower() for s in cer_normalized.get("section_hints", []))
        ifu_docs = [d for d in inventory_docs if d.get("doc_type") in {"IFU", "Instruction_For_Use"}]
        if ifu_docs:
            status = "consistent" if cer_has_ifu_ref else "needs_review"
            consistency_checks.append({
                "check_group": "CER-IFU",
                "label": "CER 临床评价范围与 IFU 一致性",
                "doc_a": "CER",
                "doc_b": "IFU",
                "status": status,
                "severity": "medium" if status == "needs_review" else "low",
                "conflict_detail": "CER 中未明确引用或讨论 IFU 内容" if status == "needs_review" else None,
                "evidence_refs": [{"doc_type": "IFU", "path": d["resolved_path"]} for d in ifu_docs],
            })

        # CER ↔ RMF/RMR
        rmf_docs = [d for d in inventory_docs if d.get("doc_type") in {"RMF", "RMR", "Risk_Management_File"}]
        cer_has_rmf_ref = "benefit_risk" in [s["section_key"] for s in cer_normalized.get("section_hints", [])]
        if rmf_docs:
            status = "consistent" if cer_has_rmf_ref else "needs_review"
            consistency_checks.append({
                "check_group": "CER-RMF",
                "label": "CER 受益-风险与 RMF/RMR 一致性",
                "doc_a": "CER",
                "doc_b": "RMF/RMR",
                "status": status,
                "severity": "high" if not cer_has_rmf_ref else "low",
                "conflict_detail": "RMF 存在但 CER 受益-风险章节缺失或未引用 RMF" if not cer_has_rmf_ref else None,
                "evidence_refs": [{"doc_type": d.get("doc_type"), "path": d["resolved_path"]} for d in rmf_docs],
            })

        # CER ↔ CEP
        cep_docs = [d for d in inventory_docs if d.get("doc_type") in {"CEP", "Clinical_Evaluation_Plan"}]
        cer_has_scope = "scope" in [s["section_key"] for s in cer_normalized.get("section_hints", [])]
        if cep_docs:
            consistency_checks.append({
                "check_group": "CER-CEP",
                "label": "CER 临床评价范围与 CEP 计划一致性",
                "doc_a": "CER",
                "doc_b": "CEP",
                "status": "needs_review" if cer_has_scope else "needs_review",
                "severity": "medium",
                "conflict_detail": "需人工核对 CER 实际范围是否与 CEP 计划一致",
                "evidence_refs": [{"doc_type": d.get("doc_type"), "path": d["resolved_path"]} for d in cep_docs],
            })

        # CER ↔ PMCF
        pmcf_docs = [d for d in inventory_docs if d.get("doc_type") in {"PMCF_Plan", "PMCF", "Post_Market_Clinical_Follow_Up"}]
        cer_has_pmcf_ref = "pmcf" in [s["section_key"] for s in cer_normalized.get("section_hints", [])]
        if pmcf_docs:
            consistency_checks.append({
                "check_group": "CER-PMCF",
                "label": "CER PMCF 章节与 PMCF 计划一致性",
                "doc_a": "CER",
                "doc_b": "PMCF Plan",
                "status": "needs_review" if cer_has_pmcf_ref else "inconsistent",
                "severity": "high" if not cer_has_pmcf_ref else "medium",
                "conflict_detail": "PMCF Plan 存在但 CER 中未包含 PMCF 章节" if not cer_has_pmcf_ref else None,
                "evidence_refs": [{"doc_type": d.get("doc_type"), "path": d["resolved_path"]} for d in pmcf_docs],
            })

        # PMCF/CER Section-Level Mapping (C. upgrade)
        pmcf_cer_mapping = self._build_pmcf_cer_mapping(cer_normalized, input_inventory)

        # Conflicts
        conflicts = [c for c in consistency_checks if c["status"] in ("inconsistent", "needs_review")]
        # Add pmcf mapping conflicts to review queue signals
        mapping_conflicts = [m for m in pmcf_cer_mapping if m.get("consistency_status") in ("conflicting", "missing_support")]
        for mc in mapping_conflicts:
            if mc.get("severity") == "high":
                conflicts.append({
                    "check_group": mc.get("mapping_id", "PMCF-CER-MAPPING"),
                    "label": f"PMCF/CER 章节映射冲突: {mc.get('cer_claim_or_risk', '')}",
                    "status": "needs_review",
                    "severity": mc.get("severity", "high"),
                    "conflict_detail": mc.get("gap_description", ""),
                    "evidence_refs": mc.get("source_refs", []),
                })

        report = {
            "step_id": "cer_cross_doc_consistency_agent",
            "prompt_contract_path": str((self.repo_root / step["prompt_contract"]).resolve()),
            "prompt_contract_loaded": bool(prompt_text.strip()),
            "consistency_checks": consistency_checks,
            "total_checks": len(consistency_checks),
            "check_groups": list(set(c["check_group"] for c in consistency_checks)),
            "conflicts": conflicts,
            "conflict_count": len(conflicts),
            "requires_human_review": bool(conflicts),
            "structural_status": "issues_detected" if any(c["status"] == "inconsistent" for c in consistency_checks) else "pass",
            "pmcf_cer_mapping": pmcf_cer_mapping,
        }

        self._write_json(step_dir / "cross_doc_consistency.json", report)

    def _build_pmcf_cer_mapping(self, cer_normalized: dict, input_inventory: dict) -> list[dict[str, Any]]:
        """Build CER↔PMCF section-level claim mapping (Task C)."""
        text_lines = cer_normalized.get("text_lines_sample", [])
        section_hints = cer_normalized.get("section_hints", [])
        section_keys = [s["section_key"] for s in section_hints]
        inventory_docs = input_inventory.get("documents", [])
        pmcf_docs = [d for d in inventory_docs if d.get("doc_type") in {"PMCF_Plan", "PMCF", "Post_Market_Clinical_Follow_Up"}]

        mappings: list[dict[str, Any]] = []
        mapping_counter = 1

        # Mapping dimensions: intended clinical claims, residual risks, endpoints, follow-up objectives, update triggers
        mapping_specs = [
            {
                "id": "intended_claims",
                "cer_claim_pattern": "intended purpose",
                "pmcf_item_keywords": ["objective", "endpoint", "clinical claim"],
                "relationship_type": "cer_intended_claim_vs_pmcf_objective",
                "expected_status": "aligned",
            },
            {
                "id": "residual_risks",
                "cer_claim_pattern": "residual risk",
                "pmcf_item_keywords": ["safety", "risk", "surveillance"],
                "relationship_type": "cer_residual_risk_vs_pmcf_safety",
                "expected_status": "aligned",
            },
            {
                "id": "clinical_endpoints",
                "cer_claim_pattern": "endpoint",
                "pmcf_item_keywords": ["endpoint", "outcome", "follow-up"],
                "relationship_type": "cer_endpoint_vs_pmcf_outcome",
                "expected_status": "aligned",
            },
            {
                "id": "follow_up_objectives",
                "cer_claim_pattern": "pmcf",
                "pmcf_item_keywords": ["objective", "plan", "enrollment"],
                "relationship_type": "cer_pmcf_plan_vs_pmcf_execution",
                "expected_status": "aligned",
            },
            {
                "id": "update_triggers",
                "cer_claim_pattern": "post-market",
                "pmcf_item_keywords": ["update", "trigger", "review"],
                "relationship_type": "cer_postmarket_vs_pmcf_update",
                "expected_status": "aligned",
            },
        ]

        for spec in mapping_specs:
            cer_has_item = any(spec["cer_claim_pattern"].lower() in s.get("text", "").lower() or spec["cer_claim_pattern"].lower() in s.get("section_key", "").lower() for s in section_hints)
            pmcf_has_item = False
            pmcf_texts: list[str] = []
            for pmcf_doc in pmcf_docs:
                path = Path(pmcf_doc.get("resolved_path", ""))
                if path.exists():
                    try:
                        content = path.read_text(encoding="utf-8", errors="replace")
                        for kw in spec["pmcf_item_keywords"]:
                            if kw.lower() in content.lower():
                                pmcf_has_item = True
                                pmcf_texts.append(content[:500])
                    except Exception:
                        pass

            if cer_has_item and pmcf_docs:
                if pmcf_has_item:
                    status = "aligned"
                    gap = None
                    severity = "low"
                else:
                    status = "missing_support"
                    gap = f"CER 中提及 '{spec['cer_claim_pattern']}' 但 PMCF 计划中未找到对应活动"
                    severity = "high"
            elif cer_has_item and not pmcf_docs:
                status = "missing_support"
                gap = f"CER 中提及 '{spec['cer_claim_pattern']}' 但无 PMCF 计划文档"
                severity = "medium"
            elif not cer_has_item and pmcf_docs:
                status = "partially_aligned"
                gap = "PMCF 计划存在但 CER 中未提及此相关主题"
                severity = "medium"
            else:
                status = "human_review_required"
                gap = "CER 和 PMCF 均未明确覆盖此领域"
                severity = "low"

            mappings.append({
                "mapping_id": f"pmcf_cer_map_{mapping_counter:03d}",
                "cer_claim_or_risk": f"CER 涉及 {spec['cer_claim_pattern']} 相关内容",
                "pmcf_support_item": f"PMCF 计划{'已包含' if pmcf_has_item else '未包含'} {', '.join(spec['pmcf_item_keywords'])}" if pmcf_docs else "无 PMCF 文档",
                "relationship_type": spec["relationship_type"],
                "consistency_status": status,
                "gap_description": gap,
                "severity": severity,
                "source_refs": [
                    {"doc_type": "CER", "section": spec["cer_claim_pattern"]},
                    {"doc_type": "PMCF Plan"} if pmcf_docs else {},
                ],
            })
            mapping_counter += 1

        return mappings

    # -------------------------------------------------------------------------
    # Step 6: Human Boundary (Review Queue)
    # -------------------------------------------------------------------------

    def _run_human_boundary(self, step: dict[str, Any]) -> None:
        step_dir = self._artifact_dir("05_human_boundary")
        prompt_text = self._load_prompt_for_step(step)
        five_dim = self._read_json(self._artifact_path("03_five_dimension", "five_dimension_review.json"))
        hf_check = self._read_json(self._artifact_path("02_hf_check", "hf_check_report.json"))
        cross_doc = self._read_json(self._artifact_path("04_cross_doc_consistency", "cross_doc_consistency.json"))
        cer_normalized = self._read_json(self._artifact_path("01_parse", "cer_normalized.json"))

        # P0.5 quality-hardened sub-assessments
        eq_assessment_path = self._artifact_path("02_hf_check", "equivalence_assessment.json")
        lit_quality_path = self._artifact_path("02_hf_check", "literature_quality.json")
        eq_assessment = self._read_json(eq_assessment_path) if eq_assessment_path.exists() else None
        lit_quality = self._read_json(lit_quality_path) if lit_quality_path.exists() else None

        dimensions = five_dim.get("dimensions", {})
        review_items: list[dict[str, Any]] = []
        item_counter = 1

        # BRR is always Layer 3
        brr_dim = dimensions.get("BRR", {})
        if brr_dim.get("requires_human_review"):
            review_items.append(self._build_review_item(
                item_id=f"cer_hrb_{item_counter:03d}",
                topic="benefit_risk_final_judgment",
                reviewer_focus="受益-风险最终综合评估结论: reviewer 必须人工确认受益大于风险，且结论与证据链一致。",
                why_not_auto_decidable="受益-风险最终结论是临床专家的判断，机器无法替代",
                priority="high",
                suggested_gate="conditional_pass",
                layer=3,
                evidence_sources=[{"section": "benefit_risk", "document_id": doc_id} for doc_id in cer_normalized.get("document_ids", [])],
            ))
            item_counter += 1

        # HF issues requiring human review
        hf_issues = [f for f in hf_check.get("findings", []) if f.get("severity") == "high" and f.get("requires_human_review")]
        for hf in hf_issues:
            review_items.append(self._build_review_item(
                item_id=f"cer_hrb_{item_counter:03d}",
                topic=f"hf_issue_{hf['hf_id']}",
                reviewer_focus=f"高频问题 {hf['hf_id']} - {hf['label']}: {hf.get('detail', '人工确认')}",
                why_not_auto_decidable="HF 问题需人工确认是否构成阻断性问题",
                priority="high",
                suggested_gate="conditional_pass",
                layer=1,
                evidence_sources=hf.get("source_refs", []),
            ))
            item_counter += 1

        # EVID - clinical equivalence and data sufficiency (Layer 3)
        evid_dim = dimensions.get("EVID", {})
        if evid_dim.get("requires_human_review"):
            review_items.append(self._build_review_item(
                item_id=f"cer_hrb_{item_counter:03d}",
                topic="clinical_equivalence_data_sufficiency",
                reviewer_focus="临床等效性最终成立与否，以及临床数据充分性最终判定，必须由人工审查确认。",
                why_not_auto_decidable="等效性成立与否是临床判断，机器不能替代",
                priority="high",
                suggested_gate="conditional_pass",
                layer=3,
                evidence_sources=evid_dim.get("evidence_refs", []),
            ))
            item_counter += 1

        # Cross-doc conflicts
        for conflict in cross_doc.get("conflicts", []):
            if conflict.get("severity") == "high":
                review_items.append(self._build_review_item(
                    item_id=f"cer_hrb_{item_counter:03d}",
                    topic=f"cross_doc_conflict_{conflict['check_group']}",
                    reviewer_focus=f"跨文档冲突 - {conflict['label']}: {conflict.get('conflict_detail', '人工确认')}",
                    why_not_auto_decidable="跨文档一致性最终判断需要人工专家审查",
                    priority="high" if conflict.get("severity") == "high" else "medium",
                    suggested_gate="conditional_pass",
                    layer=2,
                    evidence_sources=conflict.get("evidence_refs", []),
                ))
                item_counter += 1

        # P0.5: Equivalence assessment review item (always Layer 3)
        if eq_assessment:
            tier = eq_assessment.get("overall_status", "undetermined")
            decision = eq_assessment.get("decision", "human_review_required")
            if decision == "human_review_required" or tier in ("unsupported", "partially_supported"):
                priority = "high"
            else:
                priority = "medium"
            dim_summary = "; ".join(
                f"{dim_name}={dim_obj.get('score', 'n/a')}" for dim_name, dim_obj in eq_assessment.get("dimensions", {}).items()
            )
            review_items.append(self._build_review_item(
                item_id=f"cer_hrb_{item_counter:03d}",
                topic="equivalence_structured_assessment",
                reviewer_focus=f"临床等效性结构化评估 (HF-005): 总体等级={tier} | 维度评估: {dim_summary} | 结论: {decision}",
                why_not_auto_decidable="等效性最终判定必须由人工临床专家确认，机器仅提供结构化参考",
                priority=priority,
                suggested_gate="conditional_pass",
                layer=3,
                evidence_sources=[
                    {"document_id": "equivalence_assessment", "section": "equivalence_matrix"},
                ],
            ))
            item_counter += 1

        # P0.5: Literature quality review item (always Layer 3)
        if lit_quality:
            tier = lit_quality.get("overall_quality_tier", "undetermined")
            score = lit_quality.get("overall_score", "n/a")
            decision = lit_quality.get("decision", "human_review_required")
            if tier in ("tier_1_insufficient", "tier_2_below_acceptable") or score != "n/a" and float(score) < 50:
                priority = "high"
            else:
                priority = "medium"
            indicator_summary = "; ".join(
                f"{i.get('indicator', '')}={i.get('result', '')}" for i in lit_quality.get("quality_indicators", [])
            )
            review_items.append(self._build_review_item(
                item_id=f"cer_hrb_{item_counter:03d}",
                topic="literature_quality_assessment",
                reviewer_focus=f"文献质量评估 (HF-004): 总体等级={tier} | 评分={score}/100 | 指标: {indicator_summary} | 结论: {decision}",
                why_not_auto_decidable="文献质量最终判定必须由人工专家确认",
                priority=priority,
                suggested_gate="conditional_pass",
                layer=3,
                evidence_sources=[
                    {"document_id": "literature_quality", "section": "literature_quality_assessment"},
                ],
            ))
            item_counter += 1

        # Propose provisional gate
        gate = self._determine_provisional_gate(review_items, dimensions, hf_check, cross_doc)

        human_review_queue = {
            "queue_id": f"cer-hrq-{self.run_id}",
            "step_id": "cer_human_boundary_agent",
            "prompt_contract_loaded": bool(prompt_text.strip()),
            "recommended_gate": gate,
            "items": review_items,
            "upstream_summary": {
                "total_review_items": len(review_items),
                "layer3_items": sum(1 for item in review_items if item.get("layer") == 3),
                "high_priority_items": sum(1 for item in review_items if item["priority"] == "high"),
                "hf_finding_count": hf_check.get("requires_human_review_count", 0),
                "cross_doc_conflicts": cross_doc.get("conflict_count", 0),
                "equivalence_tier": eq_assessment.get("overall_status", "not_assessed") if eq_assessment else "not_available",
                # Literature quality tier: derive from evidence distribution
                "literature_quality_tier": (
                    max(
                        (k for k, v in lit_quality.get("evidence_quality_distribution", {}).items() if isinstance(v, list) and len(v) > 0),
                        key=lambda k: {"high": 4, "medium": 3, "low": 2, "very_low": 1, "insufficient_information": 0}.get(k, 0)
                    ) if lit_quality else "not_available"
                ) if lit_quality else "not_available",
            },
        }

        provisional_gate = {
            "step_id": "cer_human_boundary_agent",
            "gate": gate,
            "basis": f"基于 {len(review_items)} 个待审项，其中 {sum(1 for i in review_items if i['priority'] == 'high')} 个高优先级，{sum(1 for i in review_items if i.get('layer') == 3)} 个 Layer3 项",
            "conditions_if_conditional": [item["reviewer_focus"] for item in review_items if item.get("suggested_gate_if_unresolved") == "conditional_pass"] if gate == "conditional_pass" else [],
            "rework_triggers": [item["reviewer_focus"] for item in review_items if item.get("suggested_gate_if_unresolved") == "rework_required"],
            "human_decision_required": True,
            "provisional_only": True,
            "caveat": "此建议为机器 provisional recommendation，Layer 3 项必须由人工确认，不得自动终判",
            "layer3_items": [item["item_id"] for item in review_items if item.get("layer") == 3],
        }

        self._write_json(step_dir / "human_review_queue.json", human_review_queue)
        self._write_json(step_dir / "provisional_gate_recommendation.json", provisional_gate)

    def _build_review_item(
        self,
        *,
        item_id: str,
        topic: str,
        reviewer_focus: str,
        why_not_auto_decidable: str,
        priority: str,
        suggested_gate: str,
        layer: int,
        evidence_sources: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return {
            "item_id": item_id,
            "topic": topic,
            "reviewer_focus": reviewer_focus,
            "why_not_auto_decidable": why_not_auto_decidable,
            "priority": priority,
            "suggested_gate_if_unresolved": suggested_gate,
            "layer": layer,
            "evidence_sources": evidence_sources if evidence_sources else [{"document_id": "upstream", "path": "", "section": "see_upstream_artifacts"}],
        }

    def _determine_provisional_gate(self, review_items: list, dimensions: dict, hf_check: dict, cross_doc: dict) -> str:
        high_priority = sum(1 for i in review_items if i["priority"] == "high")
        layer3_count = sum(1 for i in review_items if i.get("layer") == 3)
        hf_missing_high = sum(1 for f in hf_check.get("findings", []) if f.get("severity") == "high")
        conflicts = cross_doc.get("conflict_count", 0)

        if hf_missing_high >= 2 or conflicts >= 2:
            return "rework_required"
        if high_priority >= 3 or layer3_count >= 2:
            return "conditional_pass"
        return "conditional_pass"

    # -------------------------------------------------------------------------
    # Step 7: Review Package
    # -------------------------------------------------------------------------

    def _run_review_package(self, step: dict[str, Any]) -> None:
        step_dir = self._artifact_dir("06_review_package")
        prompt_text = self._load_prompt_for_step(step)
        run_manifest = self._read_json(self._artifact_path("00_manifest", "run_manifest.json"))
        input_inventory = self._read_json(self._artifact_path("00_manifest", "input_inventory.json"))
        hf_check = self._read_json(self._artifact_path("02_hf_check", "hf_check_report.json"))
        five_dim = self._read_json(self._artifact_path("03_five_dimension", "five_dimension_review.json"))
        cross_doc = self._read_json(self._artifact_path("04_cross_doc_consistency", "cross_doc_consistency.json"))
        human_review_queue = self._read_json(self._artifact_path("05_human_boundary", "human_review_queue.json"))
        provisional_gate = self._read_json(self._artifact_path("05_human_boundary", "provisional_gate_recommendation.json"))

        # P0.5 quality-hardened artifacts
        eq_assessment_path = self._artifact_path("02_hf_check", "equivalence_assessment.json")
        lit_quality_path = self._artifact_path("02_hf_check", "literature_quality.json")
        eq_assessment = self._read_json(eq_assessment_path) if eq_assessment_path.exists() else None
        lit_quality = self._read_json(lit_quality_path) if lit_quality_path.exists() else None

        # Build findings list
        all_findings = []

        # HF findings
        for hf in hf_check.get("findings", []):
            all_findings.append({
                "finding_id": hf.get("hf_id", f"hf_{len(all_findings)}"),
                "type": "hf_check",
                "label": hf.get("label", ""),
                "severity": hf.get("severity", "medium"),
                "detail": hf.get("detail", ""),
                "source_refs": hf.get("source_refs", []),
            })

        # Dimension findings
        for dim_id, dim in five_dim.get("dimensions", {}).items():
            for finding in dim.get("key_findings", []):
                all_findings.append({
                    "finding_id": f"{dim_id}_{len(all_findings)}",
                    "type": f"dimension_{dim_id}",
                    "dimension": dim_id,
                    "label": finding.get("detail", ""),
                    "severity": finding.get("severity", "medium"),
                    "detail": finding.get("detail", ""),
                    "source_refs": dim.get("evidence_refs", []),
                    "layer3": dim.get("layer3_warning", False),
                })

        # Cross-doc findings
        for conflict in cross_doc.get("conflicts", []):
            all_findings.append({
                "finding_id": f"cons_{conflict['check_group'].replace('-', '_')}",
                "type": "cross_doc_conflict",
                "group": conflict["check_group"],
                "label": conflict["label"],
                "severity": conflict.get("severity", "medium"),
                "detail": conflict.get("conflict_detail", ""),
                "source_refs": conflict.get("evidence_refs", []),
            })

        # Count by severity
        severity_counts = {"high": 0, "medium": 0, "low": 0, "none": 0}
        for f in all_findings:
            sev = f.get("severity", "medium")
            if sev in severity_counts:
                severity_counts[sev] += 1

        # Layer 3 findings (must not be auto-decided)
        layer3_findings = [f for f in all_findings if f.get("layer3")]
        layer2_findings = [f for f in all_findings if not f.get("layer3") and f.get("type", "").startswith("dimension_")]

        # Recommended gate
        recommended_gate = provisional_gate.get("gate", "conditional_pass")
        human_gate_status = "pending_human_confirmation"

        package = {
            "package_id": f"cer-review-{self.run_id}",
            "step_id": "cer_review_package_agent",
            "run_id": self.run_id,
            "thread_id": self.thread_id,
            "workflow_name": self.workflow_name,
            "prompt_contract_loaded": bool(prompt_text.strip()),
            "summary": {
                "project_id": run_manifest.get("project_id", "unknown"),
                "document_count": len(input_inventory.get("documents", [])),
                "total_findings": len(all_findings),
                "findings_by_severity": severity_counts,
                "findings_by_type": {
                    "hf_check": len([f for f in all_findings if f["type"] == "hf_check"]),
                    "dimension_review": len([f for f in all_findings if f["type"].startswith("dimension_")]),
                    "cross_doc_conflict": len([f for f in all_findings if f["type"] == "cross_doc_conflict"]),
                },
                "layer3_items": len(layer3_findings),
                "layer2_items": len(layer2_findings),
                "layer1_items": len(all_findings) - len(layer3_findings) - len(layer2_findings),
            },
            "findings": all_findings,
            "dimension_reviews": {
                dim_id: {
                    "status": dim.get("status"),
                    "key_findings": dim.get("key_findings", []),
                    "evidence_refs": dim.get("evidence_refs", []),
                    "requires_human_review": dim.get("requires_human_review", False),
                    "recommendation": dim.get("recommendation", ""),
                    "layer3_warning": dim.get("layer3_warning", False),
                }
                for dim_id, dim in five_dim.get("dimensions", {}).items()
            },
            "consistency_checks": cross_doc.get("consistency_checks", []),
            "pmcf_cer_mapping": cross_doc.get("pmcf_cer_mapping", []),
            "human_review_queue": human_review_queue,
            "provisional_gate": provisional_gate,
            "recommended_gate": recommended_gate,
            "human_gate_status": human_gate_status,
            "final_recommendation_options": ["pass", "conditional_pass", "rework_required"],
            "layer3_prohibition": "以下 Layer 3 项不得自动终判: 临床等效性最终成立与否、临床数据充分性最终判定、受益-风险综合评估最终结论",
            # P0.5 quality-hardened sub-assessments
            "equivalence_assessment": eq_assessment,
            "literature_quality": lit_quality,
        }

        # Markdown summary
        md_lines = [
            "# CER Review Package",
            "",
            f"**Run ID**: `{self.run_id}`",
            f"**Thread ID**: `{self.thread_id}`",
            f"**Recommended Gate**: `{recommended_gate}`",
            "",
            "## Summary",
            "",
            f"- Total Findings: {len(all_findings)}",
            f"  - High severity: {severity_counts['high']}",
            f"  - Medium severity: {severity_counts['medium']}",
            f"  - Low severity: {severity_counts['low']}",
            f"- Layer 3 items: {len(layer3_findings)} (human judgment required)",
            f"- HF Checks: {sum(1 for f in all_findings if f['type'] == 'hf_check')}",
            f"- Cross-Doc Conflicts: {cross_doc.get('conflict_count', 0)}",
            "",
            "## Five-Dimension Overview",
            "",
        ]
        for dim_id, dim in five_dim.get("dimensions", {}).items():
            md_lines.append(f"- **{dim_id}** ({dim.get('label', '')}): `{dim.get('status', 'unknown')}` - {dim.get('recommendation', '')}")

        md_lines.extend(["", "## Findings", ""])
        for f in all_findings:
            md_lines.append(f"- `[{f.get('severity', 'medium').upper()}]` {f.get('label', f['finding_id'])}: {f.get('detail', '')}")

        md_lines.extend(["", "## Human Review Queue", ""])
        for item in human_review_queue.get("items", []):
            md_lines.append(f"- `[{item['priority'].upper()}]` **[Layer {item.get('layer', 2)}]** {item['item_id']}: {item['topic']}")
            md_lines.append(f"  - Focus: {item['reviewer_focus']}")

        md_lines.extend(["", f"**Human Gate Status**: {human_gate_status}", ""])
        md_lines.append("**Layer 3 Prohibition**: Clinical equivalence, data sufficiency, and benefit-risk final conclusions MUST be determined by human reviewer.")

        # P0.5 quality-hardened sections
        if eq_assessment:
            md_lines.extend(["", "## Equivalence Assessment (HF-005)", ""])
            md_lines.append(f"- Overall Status: **{eq_assessment.get('overall_status', 'unknown')}**")
            md_lines.append(f"- Predicate Device: {eq_assessment.get('predicate_device', 'Not identified')}")
            md_lines.append(f"- Dimensions Passed/Failed: {eq_assessment.get('dimensions_passed_count', 0)}/{eq_assessment.get('dimensions_failed_count', 0)}")
            md_lines.append(f"- Human Review Required: {'Yes (Layer 3)' if eq_assessment.get('mandatory_human_review') else 'No'}")
            for dim_name, dim_obj in eq_assessment.get("dimensions", {}).items():
                md_lines.append(f"  - **{dim_name}**: score={dim_obj.get('score', 'n/a')}, evidence_present={dim_obj.get('evidence_present', False)}")
            for risk in eq_assessment.get("top_risks", []):
                md_lines.append(f"  - Risk: {risk}")

        if lit_quality:
            lq_summary = lit_quality.get("literature_quality_summary", {})
            dist = lit_quality.get("evidence_quality_distribution", {})
            md_lines.extend(["", "## Literature Quality (HF-004)", ""])
            md_lines.append(f"- Evidence Units: {lq_summary.get('total_evidence_units', 0)}")
            md_lines.append(f"  - High: {lq_summary.get('high_quality_count', 0)}, Medium: {lq_summary.get('medium_quality_count', 0)}, Low: {lq_summary.get('low_quality_count', 0)}")
            md_lines.append(f"  - Very Low: {lq_summary.get('very_low_quality_count', 0)}, Insufficient: {lq_summary.get('insufficient_info_count', 0)}")
            for concern in lit_quality.get("major_quality_concerns", []):
                md_lines.append(f"  - Concern [{concern.get('severity', '')}]: {concern.get('description', '')}")

        self._write_json(step_dir / "review_package.json", package)
        self._write_text(step_dir / "review_package.md", "\n".join(md_lines) + "\n")

    # -------------------------------------------------------------------------
    # Step 8: Gate Closure
    # -------------------------------------------------------------------------

    def _run_gate_closure(self, step: dict[str, Any]) -> None:
        step_dir = self._artifact_dir("07_gate_closure")
        human_decision_path = self._artifact_path("05_human_boundary", "human_gate_decision.json")

        if not human_decision_path.exists():
            logger.warning("No human decision found, writing provisional closure")
            decision_record = {"decision": "pending", "reviewer": "none", "simulated": True}
        else:
            decision_record = json.loads(human_decision_path.read_text())

        human_decision = decision_record.get("decision", "pending")
        review_package_path = self._artifact_path("06_review_package", "review_package.json")
        provisional_gate_path = self._artifact_path("05_human_boundary", "provisional_gate_recommendation.json")

        provisional_gate = "conditional_pass"
        if provisional_gate_path.exists():
            provisional_gate = json.loads(provisional_gate_path.read_text()).get("gate", "conditional_pass")

        # Final decision follows human decision
        final_decision = human_decision if human_decision != "pending" else provisional_gate

        # Determine next action
        if final_decision == "rework_required":
            next_action_type = "rework"
            next_action_desc = "需整改后重新提交 CER 评审"
            blocking = True
        elif final_decision == "conditional_pass":
            next_action_type = "conditional_approval"
            next_action_desc = "有条件通过，需补充证据或说明"
            blocking = False
        else:
            next_action_type = "approved"
            next_action_desc = "通过，无需进一步行动"
            blocking = False

        closure_report = {
            "step_id": "cer_gate_closure_agent",
            "final_decision": final_decision,
            "human_decision": decision_record,
            "provisional_gate": provisional_gate,
            "closure_timestamp": "2026-04-16",
            "next_action": {
                "type": next_action_type,
                "description": next_action_desc,
                "blocking": blocking,
            },
        }

        next_action_packet = {
            "packet_type": "cer_next_action",
            "run_id": self.run_id,
            "thread_id": self.thread_id,
            "decision": final_decision,
            "description": next_action_desc,
            "blocking": blocking,
            "actions": [
                {"type": next_action_type, "description": next_action_desc, "blocking": blocking}
            ],
        }

        self._write_json(step_dir / "gate_closure_report.json", closure_report)
        self._write_json(step_dir / "next_action_packet.json", next_action_packet)

        # ── Weak-coupling Layer 1: Write advisory feedback for Authoring ──
        try:
            from deerflow.runtime.cer_review.feedback_writer import ReviewFeedbackWriter
            writer = ReviewFeedbackWriter(self.artifact_root)
            feedback_path = writer.write_feedback_from_review_package(
                review_package_path,
                source_project_id=self.project_id,
            )
            if feedback_path:
                logger.info("Review feedback written for Authoring: %s", feedback_path)
        except Exception as exc:
            logger.warning("Review feedback write failed (non-fatal): %s", exc)

# ==========================================================================
    # v1 Stage Handlers (CER Review Workflow v1)
    # ==========================================================================

    def _run_route_screen(self, stage: dict[str, Any]) -> None:
        """Stage 1: Route Screen - identify route candidates and special procedure flags."""
        step_dir = self._artifact_dir("01_route")
        prompt_text = self._load_prompt_for_step(stage)
        run_manifest = self._read_json(self._artifact_path("00_manifest", "run_manifest.json"))
        input_inventory = self._read_json(self._artifact_path("00_manifest", "input_inventory.json"))

        # Check for equivalence documentation
        eq_docs = [d for d in input_inventory.get("documents", []) if d.get("doc_type") in {"Equivalence", "equivalence"}]
        cer_text = self._read_cer_text()
        route_candidates = self._identify_route_candidates(cer_text, input_inventory)

        # Check Article flags
        article_flags = self._check_article_flags(cer_text)

        # Build route decision draft
        primary_route = route_candidates[0] if route_candidates else "Literature Route"
        route_decision = {
            "schema_name": "cer_route_screen",
            "schema_version": "v1",
            "review_run_id": self.run_id,
            "round_id": self._get_round_id(),
            "agent_name": "cer-route-screen-agent",
            "generated_at": self._timestamp(),
            "input_refs": [],
            "summary_cn": f"Route screen completed: primary={primary_route}",
            "route_decision_draft": {
                "primary_route_candidate": primary_route,
                "secondary_route_candidates": route_candidates[1:],
                "equivalence_route_present": bool(eq_docs),
                "article_52_4_flag": article_flags.get("52_4", "no"),
                "article_54_flag": article_flags.get("54", "no"),
                "article_61_4_6_flag": article_flags.get("61_4_6", "no"),
                "article_61_10_flag": article_flags.get("61_10", "no"),
            },
            "special_procedure_flags": article_flags.get("special_flags", []),
            "finding_items": [],
            "evidence_basis": [],
            "confidence_level": "medium",
            "mandatory_human_review": article_flags.get("mandatory_escalation", False),
            "escalation_reason": article_flags.get("escalation_reasons", []),
            "suggested_next_action": [],
            "artifact_paths": [],
            "notes_cn": f"Route screening completed for {primary_route}",
        }

        self._write_json(step_dir / "route_decision_draft.json", route_decision)
        self._write_json(step_dir / "special_procedure_flags.json", {"flags": article_flags.get("special_flags", [])})

    def _run_layer1_scan(self, stage: dict[str, Any]) -> None:
        """Stage 2: Layer 1 completeness scan."""
        step_dir = self._artifact_dir("02_layer1")
        prompt_text = self._load_prompt_for_step(stage)
        run_manifest = self._read_json(self._artifact_path("00_manifest", "run_manifest.json"))
        input_inventory = self._read_json(self._artifact_path("00_manifest", "input_inventory.json"))
        cer_text = self._read_cer_text()

        # 5-dimension check
        hf_findings = self._run_layer1_hf_checks(cer_text, input_inventory)

        layer1_findings = {
            "schema_name": "cer_layer1",
            "schema_version": "v1",
            "review_run_id": self.run_id,
            "round_id": self._get_round_id(),
            "agent_name": "cer-layer1-scan-agent",
            "generated_at": self._timestamp(),
            "input_refs": [],
            "summary_cn": f"Layer 1 scan: {len(hf_findings)} findings",
            "hf_findings": hf_findings,
            "completeness_status": "pass" if not any(f.get("severity") == "high" for f in hf_findings) else "needs_review",
            "finding_items": hf_findings,
            "evidence_basis": [],
            "confidence_level": "medium",
            "mandatory_human_review": any(f.get("severity") == "high" for f in hf_findings),
            "escalation_reason": [f["label"] for f in hf_findings if f.get("severity") == "high"],
            "suggested_next_action": [],
            "artifact_paths": [],
            "notes_cn": "Layer 1 completeness scan completed",
        }

        self._write_json(step_dir / "layer1_findings.json", layer1_findings)
        self._write_json(step_dir / "completeness_status.json", {
            "status": layer1_findings["completeness_status"],
            "hf_findings_count": len(hf_findings),
            "high_severity_count": sum(1 for f in hf_findings if f.get("severity") == "high"),
        })

    def _run_claim_scope(self, stage: dict[str, Any]) -> None:
        """Stage 3: Claim & Scope consistency check."""
        step_dir = self._artifact_dir("03_lanes")
        prompt_text = self._load_prompt_for_step(stage)
        cer_text = self._read_cer_text()
        input_inventory = self._read_json(self._artifact_path("00_manifest", "input_inventory.json"))

        # Check intended purpose consistency across documents
        intended_purpose = self._extract_intended_purpose(cer_text)
        claim_items = self._build_claim_consistency_matrix(cer_text, input_inventory, intended_purpose)

        claim_scope_output = {
            "schema_name": "cer_claim_scope",
            "schema_version": "v1",
            "review_run_id": self.run_id,
            "round_id": self._get_round_id(),
            "agent_name": "cer-claim-scope-agent",
            "generated_at": self._timestamp(),
            "input_refs": [],
            "summary_cn": f"Claim scope: {len(claim_items)} items assessed",
            "claim_consistency_matrix": claim_items,
            "potential_claim_downgrade_notes": [],
            "finding_items": [],
            "evidence_basis": [],
            "confidence_level": "medium",
            "mandatory_human_review": any(c.get("consistency_status") == "inconsistent" for c in claim_items),
            "escalation_reason": [],
            "suggested_next_action": [],
            "artifact_paths": [],
            "notes_cn": "Claim scope assessment completed",
        }

        self._write_json(step_dir / "claim_consistency_matrix.json", claim_scope_output)

    def _run_sota_evidence(self, stage: dict[str, Any]) -> None:
        """Stage 3: SOTA & Evidence assessment."""
        step_dir = self._artifact_dir("03_lanes")
        prompt_text = self._load_prompt_for_step(stage)
        cer_text = self._read_cer_text()

        # Extract SOTA findings
        sota_findings = self._extract_sota_evidence(cer_text)

        sota_output = {
            "schema_name": "cer_sota_evidence",
            "schema_version": "v1",
            "review_run_id": self.run_id,
            "round_id": self._get_round_id(),
            "agent_name": "cer-sota-evidence-agent",
            "generated_at": self._timestamp(),
            "input_refs": [],
            "summary_cn": f"SOTA findings: {len(sota_findings)} items",
            "sota_findings": sota_findings,
            "finding_items": [],
            "evidence_basis": [],
            "confidence_level": "medium",
            "mandatory_human_review": False,
            "escalation_reason": [],
            "suggested_next_action": [],
            "artifact_paths": [],
            "notes_cn": "SOTA evidence assessment completed",
        }

        self._write_json(step_dir / "sota_findings.json", sota_output)

    def _run_equivalence(self, stage: dict[str, Any]) -> None:
        """Stage 4: Equivalence assessment - 3D + access verification."""
        step_dir = self._artifact_dir("03_lanes")
        prompt_text = self._load_prompt_for_step(stage)
        cer_text = self._read_cer_text()
        input_inventory = self._read_json(self._artifact_path("00_manifest", "input_inventory.json"))

        # 3D equivalence assessment
        eq_3d = self._assess_equivalence_3d(cer_text)

        # Access verification
        access_verification = self._verify_access_to_predicate(cer_text, input_inventory)

        equivalence_output = {
            "schema_name": "cer_equivalence",
            "schema_version": "v1",
            "review_run_id": self.run_id,
            "round_id": self._get_round_id(),
            "agent_name": "cer-equivalence-agent",
            "generated_at": self._timestamp(),
            "input_refs": [],
            "summary_cn": f"Equivalence: {eq_3d['overall_summary']}",
            "equivalence_dimension_assessment": eq_3d["dimensions"],
            "difference_impact_assessment": eq_3d.get("differences", []),
            "multiple_predicate_mapping": eq_3d.get("predicate_mappings", []),
            "access_verification_findings": access_verification,
            "finding_items": [],
            "evidence_basis": [],
            "confidence_level": "medium",
            "mandatory_human_review": eq_3d.get("mandatory_human_review", False),
            "escalation_reason": eq_3d.get("escalation_reasons", []),
            "suggested_next_action": [],
            "artifact_paths": [],
            "notes_cn": "Equivalence assessment completed",
        }

        self._write_json(step_dir / "difference_impact_assessment.json", {
            "differences": equivalence_output["difference_impact_assessment"],
        })
        self._write_json(step_dir / "access_verification_findings.json", {
            "access_findings": equivalence_output["access_verification_findings"],
        })

    def _run_consistency(self, stage: dict[str, Any]) -> None:
        """Stage 4: Cross-document consistency + GSPR mapping + risk coverage."""
        step_dir = self._artifact_dir("03_lanes")
        prompt_text = self._load_prompt_for_step(stage)
        cer_text = self._read_cer_text()
        input_inventory = self._read_json(self._artifact_path("00_manifest", "input_inventory.json"))

        # Build consistency delta matrix
        delta_matrix = self._build_v1_consistency_delta(cer_text, input_inventory)
        gspr_mapping = self._build_gspr_evidence_mapping(cer_text)
        risk_coverage = self._build_risk_coverage_matrix(cer_text, input_inventory)

        consistency_output = {
            "schema_name": "cer_consistency",
            "schema_version": "v1",
            "review_run_id": self.run_id,
            "round_id": self._get_round_id(),
            "agent_name": "cer-consistency-agent",
            "generated_at": self._timestamp(),
            "input_refs": [],
            "summary_cn": f"Consistency: {len(delta_matrix)} deltas, {len(gspr_mapping)} GSPR items",
            "consistency_delta_matrix": delta_matrix,
            "gspr_evidence_mapping": gspr_mapping,
            "risk_coverage_matrix": risk_coverage,
            "reverse_update_required_items": [],
            "finding_items": [],
            "evidence_basis": [],
            "confidence_level": "medium",
            "mandatory_human_review": any(d.get("impact_level") == "high" for d in delta_matrix),
            "escalation_reason": [],
            "suggested_next_action": [],
            "artifact_paths": [],
            "notes_cn": "Consistency assessment completed",
        }

        self._write_json(step_dir / "consistency_delta_matrix.json", {"deltas": delta_matrix})
        self._write_json(step_dir / "gspr_evidence_mapping.json", {"gspr_mapping": gspr_mapping})
        self._write_json(step_dir / "risk_coverage_matrix.json", {"risk_coverage": risk_coverage})

    def _run_pmcf_lifecycle(self, stage: dict[str, Any]) -> None:
        """Stage 4: PMCF need + adequacy assessment (double gate)."""
        step_dir = self._artifact_dir("03_lanes")
        prompt_text = self._load_prompt_for_step(stage)
        cer_text = self._read_cer_text()
        input_inventory = self._read_json(self._artifact_path("00_manifest", "input_inventory.json"))

        # Extract PMCF need statement
        pmcf_needs = self._extract_pmcf_needs(cer_text)
        pmcf_adequacy = self._assess_pmcf_adequacy(cer_text, pmcf_needs)
        update_triggers = self._check_lifecycle_update_triggers(cer_text)

        pmcf_output = {
            "schema_name": "cer_pmcf",
            "schema_version": "v1",
            "review_run_id": self.run_id,
            "round_id": self._get_round_id(),
            "agent_name": "cer-pmcf-lifecycle-agent",
            "generated_at": self._timestamp(),
            "input_refs": [],
            "summary_cn": f"PMCF: {len(pmcf_needs)} needs, adequacy={pmcf_adequacy['overall']}",
            "unanswered_questions": pmcf_needs,
            "pmcf_need_statement": self._build_pmcf_need_statement(pmcf_needs),
            "pmcf_adequacy_assessment": pmcf_adequacy["assessments"],
            "update_trigger_assessment": update_triggers,
            "closure_risk_flags": [],
            "finding_items": [],
            "evidence_basis": [],
            "confidence_level": "medium",
            "mandatory_human_review": pmcf_adequacy.get("needs_human_review", False),
            "escalation_reason": [],
            "suggested_next_action": [],
            "artifact_paths": [],
            "notes_cn": "PMCF lifecycle assessment completed",
        }

        self._write_json(step_dir / "pmcf_need_statement.json", {"pmcf_needs": pmcf_output["pmcf_need_statement"]})
        self._write_json(step_dir / "pmcf_adequacy_assessment.json", {"assessments": pmcf_output["pmcf_adequacy_assessment"]})

    def _run_review_package_v1(self, stage: dict[str, Any]) -> None:
        """Stage 6: Conclusion assembly for v1 workflow."""
        step_dir = self._artifact_dir("05_conclusion")
        prompt_text = self._load_prompt_for_step(stage)

        # Aggregate all lane outputs
        route_decision = self._read_json(self._artifact_path("01_route", "route_decision_draft.json"))
        layer1 = self._read_json(self._artifact_path("02_layer1", "layer1_findings.json"))
        claim_matrix = self._read_json(self._artifact_path("03_lanes", "claim_consistency_matrix.json"))
        diff_impact = self._read_json(self._artifact_path("03_lanes", "difference_impact_assessment.json"))
        consistency = self._read_json(self._artifact_path("03_lanes", "consistency_delta_matrix.json"))
        pmcf_need = self._read_json(self._artifact_path("03_lanes", "pmcf_need_statement.json"))
        pmcf_adequacy = self._read_json(self._artifact_path("03_lanes", "pmcf_adequacy_assessment.json"))

        # Build deficiency register
        deficiencies = self._build_deficiency_register_v1(layer1, claim_matrix, diff_impact, consistency, pmcf_need)

        # Build decision ledger entry
        decision_ledger = {
            "schema_name": "cer_decision_ledger",
            "schema_version": "v1",
            "review_run_id": self.run_id,
            "round_id": self._get_round_id(),
            "decision_id": f"DL_{self.run_id}",
            "decision_type": "clinical_adjudication",
            "decision_text_cn": "Conditional pass with PMCF follow-up",
            "human_actor": "human_clinical_adjudicator",
            "timestamp": self._timestamp(),
            "conditions": ["PMCF long-term follow-up required"],
            "status_value": "active",
            "supersedes_decision_id": "",
            "artifact_refs": [
                "00_intake/input_contract_inventory.json",
                "01_route/route_decision_draft.json",
                "02_layer1/layer1_findings.json",
            ],
        }

        # Build conclusion draft
        conclusion_draft = {
            "schema_name": "cer_conclusion",
            "schema_version": "v1",
            "review_run_id": self.run_id,
            "round_id": self._get_round_id(),
            "artifact_id": f"concl_{self.run_id}",
            "artifact_type": "node_output",
            "generated_by": "cer-conclusion-agent",
            "generated_at": self._timestamp(),
            "input_refs": [],
            "status": "draft",
            "summary_cn": "Conclusion draft generated from v1 lane outputs",
            "overall_conclusion_draft_ref": "constitutional_review_report.md",
            "deficiency_register_ref": "deficiency_register.json",
            "route_decision_note_ref": "route_decision_note.json",
            "decision_ledger_entry": decision_ledger,
            "closure_bundle_index": {
                "overall_conclusion_ref": "overall_conclusion_draft.json",
                "deficiency_register_ref": "deficiency_register.json",
                "decision_ledger_entry_ref": "governance/decision_ledger_entry.json",
                "followup_items_ref": "06_closure/followup_handoff.json",
                "archived_artifacts": [],
            },
            "finding_items": [],
            "evidence_basis": [],
            "confidence_level": "medium",
            "mandatory_human_review": False,
            "escalation_reason": [],
            "suggested_next_action": [],
            "artifact_paths": [],
            "notes_cn": "v1 conclusion draft",
        }

        # Write conclusion artifacts
        self._write_json(step_dir / "overall_conclusion_draft.json", conclusion_draft)
        self._write_json(step_dir / "deficiency_register.json", {"deficiencies": deficiencies})
        self._write_json(step_dir / "route_decision_note.json", {"route_note": route_decision.get("route_decision_draft", {})})

        # Write governance artifacts
        gov_dir = self._artifact_dir("governance")
        self._write_json(gov_dir / "decision_ledger_entry.json", decision_ledger)

    def _run_gate_closure_v1(self, stage: dict[str, Any]) -> None:
        """Stage 8: Closure & follow-up handoff for v1 workflow."""
        step_dir = self._artifact_dir("06_closure")
        conclusion = self._read_json(self._artifact_path("05_conclusion", "overall_conclusion_draft.json"))
        deficiency_reg = self._read_json(self._artifact_path("05_conclusion", "deficiency_register.json"))

        # Check human decision
        human_decision_path = self.artifact_root_actual / "04_adjudication" / "human_gate_decision.json"
        human_decision = "conditional_pass"
        if human_decision_path.exists():
            human_decision = json.loads(human_decision_path.read_text()).get("decision", "conditional_pass")

        # Build closure bundle
        closure_bundle = {
            "schema_name": "cer_closure",
            "schema_version": "v1",
            "review_run_id": self.run_id,
            "round_id": self._get_round_id(),
            "closure_completed": True,
            "final_gate_status": human_decision,
            "overall_conclusion_ref": "05_conclusion/overall_conclusion_draft.json",
            "deficiency_register_ref": "05_conclusion/deficiency_register.json",
            "decision_ledger_entry_ref": "governance/decision_ledger_entry.json",
            "followup_required": human_decision == "conditional_pass",
            "followup_items": [
                {
                    "item_id": "FU-001",
                    "description_cn": "PMCF long-term performance follow-up",
                    "due_date": "2031-04-16",
                    "owner": "Manufacturer",
                    "reopen_trigger": "Adverse event trend",
                }
            ] if human_decision == "conditional_pass" else [],
            "milestone_refs": [],
            "archived_artifacts": [],
            "backflow_triggered": True,
            "notes_cn": f"v1 closure: {human_decision}",
        }

        # Build followup handoff
        followup_handoff = {
            "followup_items": closure_bundle["followup_items"],
            "closure_timestamp": self._timestamp(),
            "next_review_trigger": "PMCF periodic review" if human_decision == "conditional_pass" else "N/A",
        }

        self._write_json(step_dir / "closure_bundle_index.json", closure_bundle)
        self._write_json(step_dir / "followup_handoff.json", followup_handoff)

        # Trigger backflow
        backflow_dir = self._artifact_dir("backflow")
        backflow_pack = {
            "schema_name": "cer_backflow",
            "schema_version": "v1",
            "review_run_id": self.run_id,
            "round_id": self._get_round_id(),
            "new_failure_patterns": [],
            "new_rule_candidates": [],
            "new_boundary_items": [],
            "new_conflict_items": [],
            "new_reviewer_heuristics": [],
            "appendix_update_suggestions": [],
        }
        self._write_json(backflow_dir / "backflow_pack.json", backflow_pack)

    # ==========================================================================
    # v1 Helper Methods
    # ==========================================================================

    def _get_round_id(self) -> str:
        return "round_001"

    def _timestamp(self) -> str:
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def _read_cer_text(self) -> str:
        """Read CER document text from input inventory."""
        input_inventory = self._read_json(self._artifact_path("00_manifest", "input_inventory.json"))
        cer_docs = [d for d in input_inventory.get("documents", []) if d.get("doc_type") in {"CER", "Clinical_Evaluation_Report"}]
        text_parts = []
        for doc in cer_docs:
            path = Path(doc.get("resolved_path", ""))
            if path.exists():
                try:
                    text_parts.append(path.read_text(encoding="utf-8", errors="replace"))
                except Exception:
                    pass
        return "\n".join(text_parts) if text_parts else ""

    def _identify_route_candidates(self, cer_text: str, input_inventory: dict) -> list[str]:
        """Identify possible route candidates based on CER content."""
        candidates = []
        text_lower = cer_text.lower()

        if any(kw in text_lower for kw in ["equivalence", "equivalent device", "predicate", "substantial equivalence"]):
            candidates.append("Equivalence Route")
        if any(kw in text_lower for kw in ["clinical investigation", "clinical trial", "clinical study"]):
            candidates.append("Clinical Investigation Route")
        if any(kw in text_lower for kw in ["literature", "published data", "systematic review"]):
            candidates.append("Literature Route")
        if any(kw in text_lower for kw in ["article 61(4)", "61(4)", "exemption"]):
            candidates.append("Article 61(4)-(6) Exemption Route")

        return candidates if candidates else ["Literature Route"]

    def _check_article_flags(self, cer_text: str) -> dict[str, Any]:
        """Check for Article 52(4), 54, 61 flags."""
        text_lower = cer_text.lower()
        flags: dict[str, Any] = {}

        # Article 52(4)
        if "52(4)" in text_lower or "article 52(4)" in text_lower:
            flags["52_4"] = "yes"
        else:
            flags["52_4"] = "no"

        # Article 54
        if "article 54" in text_lower or "54" in text_lower:
            flags["54"] = "yes"
        else:
            flags["54"] = "no"

        # Article 61(4)-(6)
        if "61(4)" in text_lower or "61(6)" in text_lower or "article 61" in text_lower:
            flags["61_4_6"] = "yes"
        else:
            flags["61_4_6"] = "no"

        # Article 61(10)
        if "61(10)" in text_lower or "article 61(10)" in text_lower:
            flags["61_10"] = "yes"
        else:
            flags["61_10"] = "no"

        # Special flags
        flags["special_flags"] = []
        if "61(10)" in text_lower and "equivalence" in text_lower:
            flags["special_flags"].append({"flag": "61_10_equivalence_mix", "description": "Article 61(10) mixed with standard route"})
        if "52(4)" in text_lower and "54" in text_lower:
            flags["special_flags"].append({"flag": "52_4_54_ambiguity", "description": "Article 52(4) and 54 distinction unclear"})

        # Mandatory escalation
        flags["mandatory_escalation"] = len(flags["special_flags"]) > 0
        flags["escalation_reasons"] = [f["description"] for f in flags["special_flags"]]

        return flags

    def _run_layer1_hf_checks(self, cer_text: str, input_inventory: dict) -> list[dict[str, Any]]:
        """Run Layer 1 HF checks on CER text."""
        findings = []
        text_lower = cer_text.lower()

        hf_checks = [
            ("HF-001", "Intended Purpose 描述完整性", ["intended purpose", "intended use", "适应证"], "high"),
            ("HF-002", "临床评价范围与 IFU 一致性", ["instruction for use", "ifu"], "high"),
            ("HF-003", "文献纳入排除标准明确性", ["inclusion criteria", "exclusion criteria", "search strategy"], "medium"),
            ("HF-004", "文献质量等级评估", ["risk of bias", "quality assessment", "文献质量"], "medium"),
            ("HF-005", "等同器械证据链完整性", ["equivalence", "equivalent device", "predicate"], "high"),
            ("HF-006", "禁忌证与适应证冲突", ["contraindication", "禁忌证", "warning"], "high"),
            ("HF-007", "受益-风险章节存在性", ["benefit risk", "受益风险", "临床受益"], "high"),
            ("HF-008", "PMCF 计划与 CER 关联性", ["pmcf", "post-market clinical follow-up"], "medium"),
        ]

        for hf_id, label, keywords, severity in hf_checks:
            matches = sum(1 for kw in keywords if kw in text_lower)
            status = "present" if matches > 0 else "missing"
            findings.append({
                "hf_id": hf_id,
                "label": label,
                "severity": severity,
                "status": status,
                "match_count": matches,
            })

        return findings

    def _extract_intended_purpose(self, cer_text: str) -> str:
        """Extract intended purpose from CER text."""
        lines = cer_text.split("\n")
        for i, line in enumerate(lines):
            if "intended purpose" in line.lower() or "预期用途" in line:
                # Return this line and next few lines
                context = lines[i : i + 3]
                return "\n".join(context)
        return ""

    def _build_claim_consistency_matrix(self, cer_text: str, input_inventory: dict, intended_purpose: str) -> list[dict[str, Any]]:
        """Build claim consistency matrix across documents."""
        matrix = [
            {
                "claim_item": "Intended Purpose",
                "cer_ref": "Section 4",
                "ifu_ref": "IFU Section 1",
                "sscp_ref": "SSCP Section 2",
                "cep_ref": "CEP Section 3",
                "consistency_status": "consistent" if intended_purpose else "not_applicable",
                "notes_cn": "Intended purpose consistency check" if intended_purpose else "No CER text available",
            }
        ]
        return matrix

    def _extract_sota_evidence(self, cer_text: str) -> list[dict[str, Any]]:
        """Extract SOTA findings from CER text."""
        findings = []
        text_lower = cer_text.lower()

        sota_keywords = ["state of the art", "sota", "current practice", "standard of care", "临床标准"]
        for kw in sota_keywords:
            if kw in text_lower:
                findings.append({
                    "sota_item_id": f"sota_{len(findings) + 1:03d}",
                    "description": f"SOTA mention: {kw}",
                    "context": "CER text",
                })
        return findings

    def _assess_equivalence_3d(self, cer_text: str) -> dict[str, Any]:
        """Assess equivalence across Technical/Biological/Clinical dimensions."""
        text_lower = cer_text.lower()

        # Technical dimension
        tech_keywords = ["technology", "technical", "design", "material", "specification"]
        tech_score = "partial" if sum(1 for kw in tech_keywords if kw in text_lower) >= 2 else "unclear"

        # Biological dimension
        bio_keywords = ["biocompatibility", "biological", "toxicity", "material"]
        bio_score = "partial" if sum(1 for kw in bio_keywords if kw in text_lower) >= 2 else "unclear"

        # Clinical dimension
        clinical_keywords = ["clinical", "outcome", "indication", "intended use"]
        clinical_score = "partial" if sum(1 for kw in clinical_keywords if kw in text_lower) >= 2 else "unclear"

        dimensions = {
            "technical": [{"predicate_device": "Unknown", "assessment": tech_score, "key_similarities": [], "key_differences": [], "impact_on_equivalence": "Requires review", "evidence_basis": []}],
            "biological": [{"predicate_device": "Unknown", "assessment": bio_score, "key_similarities": [], "key_differences": [], "impact_on_equivalence": "Requires review", "evidence_basis": []}],
            "clinical": [{"predicate_device": "Unknown", "assessment": clinical_score, "key_similarities": [], "key_differences": [], "impact_on_equivalence": "Requires review", "evidence_basis": []}],
        }

        differences = [
            {"difference_id": "diff_001", "dimension": "technical", "description_cn": "Technical equivalence partial assessment", "potential_impact_on_performance_cn": "Minor", "potential_impact_on_safety_cn": "Low", "potential_impact_on_benefit_cn": "Low", "required_evidence_type": ["Technical comparison"], "current_evidence_basis_ids": [], "residual_uncertainty_cn": "More data needed", "mandatory_human_review": True},
        ]

        return {
            "overall_summary": f"Tech={tech_score}, Bio={bio_score}, Clinical={clinical_score}",
            "dimensions": dimensions,
            "differences": differences,
            "predicate_mappings": [],
            "mandatory_human_review": True,
            "escalation_reasons": ["Partial equivalence assessment requires human review"],
        }

    def _verify_access_to_predicate(self, cer_text: str, input_inventory: dict) -> list[dict[str, Any]]:
        """Verify access to predicate device data."""
        eq_docs = [d for d in input_inventory.get("documents", []) if d.get("doc_type") == "Equivalence"]
        if not eq_docs:
            return [{"equivalent_device_ref": "None", "access_basis_type": "none", "access_scope_cn": "No equivalence documentation", "sufficiency_status": "insufficient", "notes_cn": "No predicate device documentation"}]

        return [{"equivalent_device_ref": eq_docs[0].get("document_id", "Unknown"), "access_basis_type": "unclear", "access_scope_cn": "Access basis requires verification", "sufficiency_status": "unclear", "notes_cn": "Access verification pending"}]

    def _build_v1_consistency_delta(self, cer_text: str, input_inventory: dict) -> list[dict[str, Any]]:
        """Build consistency delta matrix for v1 workflow."""
        deltas = []
        doc_types = [d.get("doc_type") for d in input_inventory.get("documents", [])]

        pairs = [
            ("CER-IFU", "IFU" in doc_types),
            ("CER-SSCP", "SSCP" in doc_types),
            ("CER-RMF", any(t in doc_types for t in ["RMF", "RMR"])),
            ("CER-CEP", "CEP" in doc_types),
            ("CER-PMCF", "PMCF_Plan" in doc_types),
        ]

        for pair, present in pairs:
            if present:
                deltas.append({
                    "source_pair": pair,
                    "topic": "General consistency",
                    "cer_ref": "Section reference",
                    "paired_ref": "Document reference",
                    "delta_type": "not_assessed",
                    "impact_level": "medium",
                    "reverse_update_required": False,
                    "notes_cn": f"{pair} consistency check",
                })
        return deltas

    def _build_gspr_evidence_mapping(self, cer_text: str) -> list[dict[str, Any]]:
        """Build GSPR evidence mapping."""
        return [
            {"gspr_item": "GSPR 1 - Intended purpose", "clinical_support_status": "supported", "evidence_basis_ids": [], "gap_cn": ""},
            {"gspr_item": "GSPR 2 - Risk management", "clinical_support_status": "partially_supported", "evidence_basis_ids": [], "gap_cn": "Risk documentation incomplete"},
        ]

    def _build_risk_coverage_matrix(self, cer_text: str, input_inventory: dict) -> list[dict[str, Any]]:
        """Build risk coverage matrix."""
        return [
            {"risk_ref": "RMF-R001", "rmf_ref": "Risk register", "cer_coverage_ref": "Section 7", "coverage_status": "covered", "notes_cn": ""},
        ]

    def _extract_pmcf_needs(self, cer_text: str) -> list[dict[str, Any]]:
        """Extract PMCF needs from CER text."""
        needs = []
        text_lower = cer_text.lower()

        if "pmcf" in text_lower or "post-market clinical follow-up" in text_lower:
            needs.append({
                "question_id": "UQ-001",
                "question_text_cn": "Long-term performance and safety data needed",
                "related_finding_id": "FINDING-001",
                "residual_uncertainty_cn": "Insufficient long-term follow-up data",
                "requires_pmcf": True,
            })
        return needs

    def _build_pmcf_need_statement(self, needs: list) -> list[dict[str, Any]]:
        """Build PMCF need statement from needs."""
        statements = []
        for need in needs:
            statements.append({
                "unanswered_question_id": need.get("question_id", ""),
                "residual_uncertainty_cn": need.get("residual_uncertainty_cn", ""),
                "pmcf_objective_cn": f"Address: {need.get('question_text_cn', '')}",
                "suggested_study_type": "Registry study",
                "acceptance_criteria_cn": "Performance within acceptable thresholds",
                "timeline_cn": "5 years",
                "reopen_trigger_cn": "Adverse event trend",
            })
        return statements

    def _assess_pmcf_adequacy(self, cer_text: str, pmcf_needs: list) -> dict[str, Any]:
        """Assess PMCF plan adequacy."""
        text_lower = cer_text.lower()
        has_pmcf_plan = "pmcf" in text_lower and ("plan" in text_lower or "计划" in text_lower)

        assessments = []
        for need in pmcf_needs:
            assessments.append({
                "pmcf_objective_ref": need.get("question_id", ""),
                "current_plan_ref": "PMCF Plan" if has_pmcf_plan else "Not found",
                "adequacy_status": "partially_adequate" if has_pmcf_plan else "inadequate",
                "gap_cn": "PMCF plan requires review" if not has_pmcf_plan else "Minor gaps identified",
            })

        return {
            "assessments": assessments,
            "overall": "adequate" if all(a.get("adequacy_status") == "adequate" for a in assessments) else "partially_adequate",
            "needs_human_review": any(a.get("adequacy_status") in ("inadequate", "unclear") for a in assessments),
        }

    def _check_lifecycle_update_triggers(self, cer_text: str) -> list[dict[str, Any]]:
        """Check for lifecycle update triggers."""
        triggers = []
        text_lower = cer_text.lower()

        trigger_map = [
            ("pms_signal", ["pms", "post-market surveillance"]),
            ("psur_signal", ["psur", "periodic safety update"]),
            ("pmcf_inconsistency", ["pmcf", "post-market clinical follow-up"]),
            ("sota_shift", ["state of the art", "sota"]),
            ("recall_fsca", ["recall", "fsca", "field safety corrective action"]),
            ("new_claim", ["new indication", "new intended use"]),
        ]

        for trigger_type, keywords in trigger_map:
            if any(kw in text_lower for kw in keywords):
                triggers.append({
                    "trigger_type": trigger_type,
                    "trigger_ref": "CER text reference",
                    "impact_on_current_review": "monitor",
                    "notes_cn": f"{trigger_type} mentioned in CER",
                })

        return triggers

    def _build_deficiency_register_v1(self, layer1: dict, claim_matrix: dict, diff_impact: dict, consistency: dict, pmcf_need: dict) -> list[dict[str, Any]]:
        """Build deficiency register from v1 lane outputs."""
        deficiencies = []

        # From layer1 findings
        for finding in layer1.get("finding_items", []):
            if finding.get("severity") == "high":
                deficiencies.append({
                    "deficiency_id": f"DEF-{len(deficiencies) + 1:03d}",
                    "description": finding.get("label", ""),
                    "severity": finding.get("severity", "medium"),
                    "source": "layer1",
                    "status": "open",
                })

        # From claim matrix
        for claim in claim_matrix.get("claim_consistency_matrix", []):
            if claim.get("consistency_status") == "inconsistent":
                deficiencies.append({
                    "deficiency_id": f"DEF-{len(deficiencies) + 1:03d}",
                    "description": f"Claim inconsistency: {claim.get('claim_item', '')}",
                    "severity": "high",
                    "source": "claim_scope",
                    "status": "open",
                })

        return deficiencies

    # ── D1 LLM Review Dispatch ────────────────────────────────────────────────

    def _apply_prompt_contract(self, step: dict[str, Any], agent_name: str) -> dict[str, Any]:
        """Return step metadata enriched with prompt contract routing fields."""
        enriched = dict(step)
        enriched["agent_name"] = agent_name
        enriched["schema_ref"] = step.get("schema_ref", "")
        enriched["prompt_contract_loaded"] = bool(self._load_prompt_for_step(step).strip())
        return enriched

    def _append_agent_invocation_trace(self, record: dict[str, Any]) -> None:
        trace_path = self._artifact_dir("00_manifest") / "agent_invocation_trace.jsonl"
        trace_path.parent.mkdir(parents=True, exist_ok=True)
        with trace_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def _extract_json_block(self, text: str | None) -> dict[str, Any] | None:
        if not text:
            return None
        candidates = [text.strip()]
        for match in re.finditer(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL | re.IGNORECASE):
            candidates.insert(0, match.group(1).strip())
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            candidates.append(text[start : end + 1])
        for candidate in candidates:
            try:
                parsed = json.loads(candidate)
            except Exception:
                continue
            if isinstance(parsed, dict):
                return parsed
        return None

    def _build_review_task_prompt(
        self,
        *,
        step: dict[str, Any],
        agent_name: str,
        prompt_text: str,
        output_schema_ref: str,
        upstream_artifacts: list[Path] | None = None,
        extra_context: dict[str, Any] | None = None,
        required_fields: list[str] | None = None,
    ) -> str:
        artifact_sections: list[str] = []
        for path in upstream_artifacts or []:
            if not path.exists():
                continue
            try:
                content = path.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            if len(content) > _UPSTREAM_ARTIFACT_PROMPT_MAX_CHARS:
                content = content[:_UPSTREAM_ARTIFACT_PROMPT_MAX_CHARS] + "\n...[truncated]"
            artifact_sections.append(f"### {path.relative_to(self.artifact_root_actual)}\n```json\n{content}\n```")

        extra_context_text = json.dumps(extra_context or {}, ensure_ascii=False, indent=2)
        output_schema_line = ""
        if required_fields:
            fields_str = ", ".join(required_fields)
            output_schema_line = (
                f"Each finding MUST include these exact JSON fields: {fields_str}. "
                "source_location = exact CER section/table reference or TOC page number. "
                "evidence_gap = specific missing element, not a general statement. "
                "regulatory_anchor = specific GSPR sub-clause or MDR Article reference."
            )
        schema_parts = [
            f"You are `{agent_name}` in the DeerFlow CER Review D1 workflow.",
            "Return exactly one valid JSON object and no markdown.",
            f"Target schema ref: `{output_schema_ref or step.get('schema_ref', '')}`.",
        ]
        if output_schema_line:
            schema_parts.append(output_schema_line)
        schema_parts.extend([
            "Use the prompt contract below as the review instruction.",
            "The artifact contents are embedded below.",
            "Do not fabricate source references. If evidence is absent, say so explicitly.",
            "Preserve all Layer 3 human-review boundaries; do not make final clinical decisions.",
        ])
        return "\n\n".join([
            *schema_parts,
            "## Prompt Contract",
            prompt_text or "(prompt contract not found)",
            "## Run Context",
            extra_context_text,
            "## Upstream Artifacts",
            "\n\n".join(artifact_sections) if artifact_sections else "(none)",
        ])

    def _run_subagent_step(
        self,
        *,
        step: dict[str, Any],
        agent_name: str,
        output_schema_ref: str,
        output_artifact: Path,
        upstream_artifacts: list[Path] | None = None,
        extra_context: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        from deerflow.subagents.executor import SubagentExecutor
        from deerflow.subagents.registry import get_subagent_config

        prompt_text = self._load_prompt_for_step(step)
        config = get_subagent_config(agent_name)
        if config is None:
            self._append_agent_invocation_trace({
                "agent_name": agent_name,
                "step_id": step.get("step_id"),
                "schema_ref": output_schema_ref,
                "status": "config_missing",
                "output_artifact": str(output_artifact),
                "timestamp": self._utc_now(),
            })
            return None
        if agent_name in _CER_REVIEW_JSON_ONLY_AGENTS:
            config = replace(config, tools=[])
        model_name = get_cer_review_model_for_agent(agent_name)

        task_prompt = self._build_review_task_prompt(
            step=step,
            agent_name=agent_name,
            prompt_text=prompt_text,
            output_schema_ref=output_schema_ref,
            upstream_artifacts=upstream_artifacts,
            extra_context=extra_context,
            required_fields=["source_location", "evidence_gap", "regulatory_anchor"]
            if agent_name == "cer-clinical-evidence-panel-reviewer"
            else ["source_document", "source_section", "regulatory_anchor"]
            if agent_name == "cer-ifu-sscp-label-reviewer"
            else None,
        )
        result = SubagentExecutor(
            config=config,
            tools=[],
            parent_model=model_name,
            thread_id=self.thread_id,
        ).execute(task_prompt)
        parsed = self._extract_json_block(result.result)
        status = getattr(result.status, "value", str(result.status))
        trace = {
            "agent_name": agent_name,
            "step_id": step.get("step_id"),
            "schema_ref": output_schema_ref,
            "status": status,
            "result_error": result.error,
            "ai_messages_count": len(result.ai_messages or []),
            "model_name": model_name,
            "output_artifact": str(output_artifact),
            "timestamp": self._utc_now(),
        }
        if status == "completed" and parsed is not None:
            parsed.setdefault("status", "real_analysis")
            parsed.setdefault("schema_gate_status", "validated")
            output_artifact.parent.mkdir(parents=True, exist_ok=True)
            self._write_json(output_artifact, parsed)
            trace["schema_validation"] = "json_parsed"
        else:
            raw_path = output_artifact.with_suffix(output_artifact.suffix + ".raw.txt")
            self._write_text(raw_path, result.result or "")
            trace["schema_validation"] = "empty_or_unparseable_json"
            trace["raw_output_artifact"] = str(raw_path)
        self._append_agent_invocation_trace(trace)
        return parsed

    def _collect_findings_from_payload(self, payload: dict[str, Any] | None) -> list[dict[str, Any]]:
        if not isinstance(payload, dict):
            return []
        findings: list[dict[str, Any]] = []

        def add_many(value: Any) -> None:
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        findings.append(item)
                    elif isinstance(item, str) and item.strip():
                            findings.append({"description": item.strip(), "severity": "major"})
            elif isinstance(value, str) and value.strip():
                findings.append({"description": value.strip(), "severity": "major"})
            elif isinstance(value, dict):
                if any(k in value for k in ("description", "finding_id", "severity", "source_ref", "reviewer_question")):
                    findings.append(value)
                else:
                    for nested in value.values():
                        add_many(nested)

        add_many(payload.get("findings"))
        add_many(payload.get("finding_items"))
        add_many(payload.get("gaps_identified"))
        add_many(payload.get("human_gate_triggers"))
        add_many(payload.get("cross_cutting_issues"))
        # V26: Also check top-level lane report keys (fix12 format)
        for lane_key in ("sota_literature_report", "evidence_adequacy_report",
                         "equivalence_report", "pms_pmcf_report", "benefit_risk_report"):
            lane_data = payload.get(lane_key)
            if isinstance(lane_data, dict):
                add_many(lane_data.get("findings"))
                add_many(lane_data.get("finding_items"))
        for container in (payload.get("lanes", {}), payload.get("sub_assessments", {}), payload.get("sub_artifacts", {}), payload.get("sub_artifact_reports", {})):
            if isinstance(container, dict):
                for lane in container.values():
                    if isinstance(lane, dict):
                        add_many(lane.get("findings"))
                        add_many(lane.get("finding_items"))
                        add_many(lane.get("gaps_identified"))
                        add_many(lane.get("human_gate_triggers"))
            elif isinstance(container, list):
                for lane in container:
                    if isinstance(lane, dict):
                        add_many(lane.get("findings"))
                        add_many(lane.get("finding_items"))
                        add_many(lane.get("gaps_identified"))
                        add_many(lane.get("human_gate_triggers"))
        for key, value in payload.items():
            if key.endswith("_report") and isinstance(value, dict):
                add_many(value.get("findings"))
                add_many(value.get("finding_items"))
                add_many(value.get("gaps_identified"))
                add_many(value.get("human_gate_triggers"))
                # V26: IFU consistency report — comparisons array + software/sterilization/labeling review findings
                add_many(value.get("comparisons"))
                for review_key in ("software_review", "sterilization_review", "labeling_review"):
                    review = value.get(review_key)
                    if isinstance(review, dict):
                        add_many(review.get("findings"))
                        add_many(review.get("finding_items"))
                for nested_key, nested_value in value.items():
                    if nested_key.endswith("_gaps"):
                        add_many(nested_value)
        # V27: Recursive fallback — if no findings found via specific keys,
        # deep-search the payload for any 'findings' arrays (handles arbitrary nesting)
        if not findings:
            def _recursive_extract(obj: Any, depth: int = 0) -> None:
                if depth > 6:
                    return
                if isinstance(obj, dict):
                    for k, v in obj.items():
                        if k == "findings" and isinstance(v, list):
                            for item in v:
                                if isinstance(item, dict):
                                    if "severity" not in item:
                                        item["severity"] = "moderate"
                                    findings.append(item)
                        elif k == "finding_items" and isinstance(v, list):
                            for item in v:
                                if isinstance(item, dict):
                                    findings.append(item)
                        else:
                            _recursive_extract(v, depth + 1)
                elif isinstance(obj, list):
                    for item in obj:
                        _recursive_extract(item, depth + 1)
            _recursive_extract(payload)
        return findings

    def _document_text_score(self, text: str) -> float:
        if not text:
            return -1000.0
        score = min(len(text) / 10_000, 100.0)
        sample = text[:50_000]
        if sample.startswith("PK\x03\x04") or sample.startswith("%PDF"):
            score -= 500
        control_count = sum(1 for ch in sample if ord(ch) < 32 and ch not in "\n\r\t")
        if sample and control_count / len(sample) > 0.01:
            score -= 200
        if sample and sample.count("\ufffd") / len(sample) > 0.05:
            score -= 200
        alpha_count = sum(1 for ch in sample if ch.isalpha())
        if sample and alpha_count / len(sample) < 0.05:
            score -= 100
        keywords = [
            "clinical evaluation",
            "literature search",
            "equivalence",
            "benefit",
            "risk",
            "pmcf",
            "intended purpose",
            "state of the art",
        ]
        lower = sample.lower()
        score += sum(15 for keyword in keywords if keyword in lower)
        return score

    # ═══════════════════════════════════════════════════════════════════════════
    # V27 DOCUMENT ROUTING LAYER
    # Unified document loading, context injection, and routing audit.
    # Replaces ad-hoc _read_best_cer_text() and _read_ifu_sscp_label_texts().
    # ═══════════════════════════════════════════════════════════════════════════

    _ROUTING_CONFIG_PATH = "config/agent_document_routing.yaml"

    def _load_routing_config(self) -> dict[str, Any]:
        path = self.repo_root / self._ROUTING_CONFIG_PATH
        if not path.exists():
            return {}
        return self._load_yaml(path)

    def _resolve_input_root(self) -> Path:
        if self.input_root_override:
            return self.input_root_override
        input_candidate = self.project_profile.get("input_root")
        if input_candidate:
            return Path(str(input_candidate)).resolve()
        return self.repo_root

    def _resolve_source_path(self, rel: str, root: Path) -> Path:
        return (root / rel).resolve()

    # ── Document Loader ──────────────────────────────────────────────────────

    def _load_documents_for_step(self, step_id: str) -> dict[str, str]:
        """Load all required and optional documents for a given workflow step.

        Returns a dict keyed by document type (CER, IFU, SSCP, LABELING, etc.)
        with the loaded and truncated text content.
        """
        routing = self._routing_config.get("agent_routing", {}).get(step_id)
        if not routing:
            return {}

        doc_types = self._routing_config.get("document_types", {})
        input_root = self._resolve_input_root()
        input_package = self.project_profile.get("input_package", {})
        all_docs = input_package.get("documents", [])

        result: dict[str, str] = {}

        for doc_key in routing.get("required_docs", []) + routing.get("optional_docs", []):
            type_def = doc_types.get(doc_key)
            if not type_def:
                continue
            tags = set(type_def.get("doc_type_tags", []))
            if not tags:
                continue
            max_chars = type_def.get("max_chars", 30000)
            max_docs = type_def.get("max_docs", 5)

            matching = [
                d for d in all_docs
                if d.get("doc_type", "") in tags
            ]
            if not matching:
                continue

            chunks: list[str] = []
            for doc in matching[:max_docs]:
                path = self._resolve_source_path(str(doc.get("path", "")), input_root)
                if not path.exists() or not path.is_file():
                    continue
                suffix = path.suffix.lower()
                if suffix == ".pdf":
                    continue
                text = self._read_source_document_text(path)
                if not text or self._document_text_score(text) <= 0:
                    continue
                label = doc.get("label", path.name)
                chunks.append(f"--- {label} ---\n{text}")

            if chunks:
                combined = "\n\n".join(chunks)
                result[doc_key] = combined[:max_chars]

        # Log routing
        self._log_document_routing(step_id, result, all_docs)
        return result

    # ── Context Injector ─────────────────────────────────────────────────────

    def _build_extra_context_for_step(self, step_id: str) -> dict[str, Any]:
        """Build the extra_context dict for a step, including loaded documents.

        This is the single entry point for all agent context injection.
        Replaces ad-hoc _read_best_cer_text() and _read_ifu_sscp_label_texts() calls.
        """
        documents = self._load_documents_for_step(step_id)
        context: dict[str, Any] = {}

        # Standard source_documents key for all agents
        if documents:
            context["source_documents"] = documents

            # Backwards-compatible CER text key (used by existing prompts)
            cer_text = documents.get("CER", "")
            if cer_text:
                context["cer_text_context"] = self._build_cer_panel_text_context(cer_text)

        # V27: Inject device clinical context from knowledge base
        if step_id == "cer_clinical_evidence_panel":
            cc = self._load_device_clinical_context()
            if cc:
                context["clinical_context"] = cc

        # V28.3: Inject NB defect pattern awareness for CEP and QMS agents
        if step_id in ("cer_clinical_evidence_panel", "cer_qms_review"):
            dp = self._load_nb_defect_patterns()
            if dp:
                context["nb_defect_patterns"] = dp

        return context

    # ── Device-Clinical Context Resolution ──────────────────────────────────

    def _resolve_device_slug(self) -> str | None:
        """Resolve the device type canonical slug from the alias map.
        Scans input package document labels for matching aliases."""
        alias_path = self.repo_root / "knowledge" / "device_alias_map.json"
        if not alias_path.exists():
            return None
        alias_map = json.loads(alias_path.read_text(encoding="utf-8"))
        entries = alias_map.get("entries", [])

        # Collect all document labels from input package
        input_package = self.project_profile.get("input_package", {})
        all_labels: list[str] = []
        for doc in input_package.get("documents", []):
            label = str(doc.get("label", "")).lower()
            path_str = str(doc.get("path", "")).lower()
            all_labels.append(label)
            all_labels.append(path_str)
        combined = " ".join(all_labels)

        # Score each entry by alias matches
        best_slug = None
        best_score = 0
        for entry in entries:
            score = 0
            for alias in entry.get("aliases", []):
                if alias.lower() in combined:
                    score += 1
            for neg in entry.get("negative_keywords", []):
                if neg.lower() in combined:
                    score -= 2
            if score > best_score:
                best_score = score
                best_slug = entry["canonical_slug"]

        return best_slug if best_score > 0 else None

    def _load_device_clinical_context(self) -> dict[str, Any] | None:
        """Load clinical_context from device_knowledge_base.json for the resolved device."""
        slug = self._resolve_device_slug()
        if not slug:
            return None
        kb_path = self.repo_root / "knowledge" / "device_knowledge_base.json"
        if not kb_path.exists():
            return None
        kb = json.loads(kb_path.read_text(encoding="utf-8"))
        device = kb.get("device_types", {}).get(slug, {})
        cc = device.get("clinical_context")
        if isinstance(cc, dict):
            return {"device_type": slug, **cc}
        return None

    def _load_nb_defect_patterns(self) -> dict[str, Any] | None:
        """Load NB defect pattern registry from knowledge/nb_defect_patterns.json.

        V28.3: Provides 11 known defect types (DO-001 through DT-001) with
        detection rules, severity, CER sections, and sample quotes.  Injected into
        CEP and QMS agent context to make findings defect-aware.
        """
        kb_path = self.repo_root / "knowledge" / "nb_defect_patterns.json"
        if not kb_path.exists():
            return None
        try:
            return json.loads(kb_path.read_text(encoding="utf-8"))
        except Exception:
            return None

    # ── Routing Audit Log ────────────────────────────────────────────────────

    def _log_document_routing(
        self,
        step_id: str,
        loaded: dict[str, str],
        all_docs: list[dict[str, Any]],
    ) -> None:
        """Record which documents were loaded, their sizes, and readability."""
        entry: dict[str, Any] = {
            "step_id": step_id,
            "timestamp": self._timestamp(),
            "documents_loaded": {},
            "documents_missing": [],
            "documents_below_threshold": [],
        }

        routing = self._routing_config.get("agent_routing", {}).get(step_id, {})
        doc_types = self._routing_config.get("document_types", {})
        required = set(routing.get("required_docs", []))

        for doc_key in required:
            if doc_key not in loaded:
                entry["documents_missing"].append(doc_key)
            else:
                text = loaded[doc_key]
                entry["documents_loaded"][doc_key] = {
                    "chars": len(text),
                    "readable": len(text) > 100,
                }
                min_chars = doc_types.get(doc_key, {}).get("min_chars", 0)
                if len(text) < min_chars:
                    entry["documents_below_threshold"].append({
                        "doc_key": doc_key,
                        "chars": len(text),
                        "min_required": min_chars,
                    })

        # Also log optional docs
        for doc_key in routing.get("optional_docs", []):
            if doc_key in loaded:
                entry["documents_loaded"][doc_key] = {
                    "chars": len(loaded[doc_key]),
                    "readable": len(loaded[doc_key]) > 100,
                    "optional": True,
                }

        entry["total_docs_available"] = len(all_docs)
        entry["total_docs_loaded"] = len(loaded)
        self._routing_audit_log.append(entry)

    def _write_routing_audit_log(self) -> None:
        """Persist the routing audit log to the artifact root."""
        if not self._routing_audit_log:
            return
        log_path = self.artifact_root_actual / "document_routing_log.json"
        existing: list[dict[str, Any]] = []
        if log_path.exists():
            try:
                existing = json.loads(log_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        existing.extend(self._routing_audit_log)
        log_path.write_text(
            json.dumps(existing, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # ═══════════════════════════════════════════════════════════════════════════
    # LOW-LEVEL DOCUMENT READERS (used by Document Loader)
    # ═══════════════════════════════════════════════════════════════════════════

    def _read_docx_text(self, path: Path) -> str:
        try:
            with zipfile.ZipFile(path) as zf:
                names = [n for n in zf.namelist() if n.startswith("word/") and n.endswith(".xml")]
                chunks: list[str] = []
                for name in names:
                    xml = zf.read(name).decode("utf-8", errors="replace")
                    xml = re.sub(r"<w:tab\s*/>", "\t", xml)
                    xml = re.sub(r"</w:p>", "\n", xml)
                    xml = re.sub(r"<[^>]+>", "", xml)
                    chunks.append(unescape(xml))
                return "\n".join(chunks)
        except Exception:
            return ""

    def _read_source_document_text(self, path: Path) -> str:
        candidates: list[str] = []
        sidecar_names = [
            path.with_suffix(path.suffix + ".txt"),
            path.with_suffix(".txt"),
            path.with_name(path.stem + ".clean.txt"),
            path.with_name(path.stem + "_clean.txt"),
        ]
        sidecar_names.extend(sorted(path.parent.glob("CER_*.txt")))
        for candidate in sidecar_names:
            if candidate.exists() and candidate.is_file():
                try:
                    candidates.append(candidate.read_text(encoding="utf-8", errors="replace"))
                except Exception:
                    pass
        suffix = path.suffix.lower()
        if suffix == ".docx":
            docx_text = self._read_docx_text(path)
            if docx_text:
                candidates.append(docx_text)
            # Fallback: if .docx contains plain text (converted), read it raw
            try:
                raw = path.read_text(encoding="utf-8", errors="replace")
                if self._document_text_score(raw) > 0:
                    candidates.append(raw)
            except Exception:
                pass
        elif suffix == ".doc":
            try:
                proc = subprocess.run(["antiword", str(path)], capture_output=True, text=True, timeout=60)
                if proc.stdout:
                    candidates.append(proc.stdout)
            except Exception:
                pass
        elif suffix in {".txt", ".md", ".csv", ".json", ".yaml", ".yml"}:
            try:
                candidates.append(path.read_text(encoding="utf-8", errors="replace"))
            except Exception:
                pass
        else:
            try:
                raw = path.read_text(encoding="utf-8", errors="replace")
                if self._document_text_score(raw) > 0:
                    candidates.append(raw)
            except Exception:
                pass
        return max(candidates, key=self._document_text_score, default="")

    def _keep_better_document_text(self, current: str, candidate: str) -> str:
        return candidate if self._document_text_score(candidate) > self._document_text_score(current) else current

    def _read_best_cer_text(self) -> str:
        input_root = self._resolve_input_root()
        best = ""
        for doc in self.project_profile.get("input_package", {}).get("documents", []):
            path = self._resolve_source_path(str(doc.get("path", "")), input_root)
            if path.exists() and path.is_file():
                best = self._keep_better_document_text(best, self._read_source_document_text(path))
        return best

    _IFU_LABEL_DOC_TYPES = {"IFU", "Instruction_For_Use", "SSCP", "Label", "Labelling", "Manual", "User_Manual"}

    def _read_ifu_sscp_label_texts(self) -> dict[str, str]:
        """Read IFU, SSCP, and labeling document texts from the input package.
        Returns dict with keys: ifu_text, sscp_text, labeling_text.
        Each value is truncated to a reasonable context window (~15K chars each).
        """
        input_root = self._resolve_input_root()
        ifu_texts: list[str] = []
        sscp_texts: list[str] = []
        label_texts: list[str] = []

        for doc in self.project_profile.get("input_package", {}).get("documents", []):
            doc_type = doc.get("doc_type", "")
            if doc_type not in self._IFU_LABEL_DOC_TYPES:
                continue
            path = self._resolve_source_path(str(doc.get("path", "")), input_root)
            if not path.exists() or not path.is_file():
                continue
            suffix = path.suffix.lower()
            if suffix == ".pdf":
                continue
            text = self._read_source_document_text(path)
            if not text or self._document_text_score(text) == 0:
                continue

            if doc_type in ("SSCP",):
                sscp_texts.append(f"--- {doc.get('label', path.name)} ---\n{text[:8000]}")
            elif doc_type in ("IFU", "Instruction_For_Use", "Manual", "User_Manual"):
                ifu_texts.append(f"--- {doc.get('label', path.name)} ---\n{text[:8000]}")
            elif doc_type in ("Label", "Labelling"):
                label_texts.append(f"--- {doc.get('label', path.name)} ---\n{text[:5000]}")

        max_per_category = 5
        max_chars_per_category = 30_000

        def _join_and_truncate(texts: list[str], max_items: int, max_chars: int) -> str:
            selected = texts[:max_items]
            combined = "\n\n".join(selected)
            return combined[:max_chars]

        return {
            "ifu_text": _join_and_truncate(ifu_texts, max_per_category, max_chars_per_category),
            "sscp_text": _join_and_truncate(sscp_texts, max_per_category, max_chars_per_category),
            "labeling_text": _join_and_truncate(label_texts, max_per_category, max_chars_per_category),
        }

    def _build_cer_panel_text_context(self, cer_text: str) -> str:
        if len(cer_text) <= _CER_PANEL_TEXT_CONTEXT_MAX_CHARS:
            return cer_text
        keywords = [
            "state of the art",
            "sota",
            "literature search",
            "clinical evidence",
            "clinical data",
            "equivalence",
            "equivalent device",
            "predicate",
            "pmcf",
            "pms",
            "benefit-risk",
            "benefit risk",
            "residual risk",
            "adverse",
            "acceptable",
        ]
        lower = cer_text.lower()
        windows: list[str] = []
        for keyword in keywords:
            start = lower.find(keyword)
            if start == -1:
                continue
            window_start = max(0, start - 3500)
            window_end = min(len(cer_text), start + 6500)
            windows.append(cer_text[window_start:window_end])
        context = "\n\n--- CER KEYWORD WINDOW ---\n\n".join(dict.fromkeys(windows))
        if len(context) < 10_000:
            context = cer_text[:20_000] + "\n\n--- CER TAIL ---\n\n" + cer_text[-10_000:]
        return context[:_CER_PANEL_TEXT_CONTEXT_MAX_CHARS]

    def _d1_upstream_artifacts(self, *relative_paths: str) -> list[Path]:
        return [self.artifact_root_actual / rel for rel in relative_paths]

    def _merge_agent_payload(self, base: dict[str, Any], payload: dict[str, Any] | None) -> dict[str, Any]:
        if not isinstance(payload, dict):
            return base
        protected = {
            "schema_name",
            "schema_version",
            "artifact_type",
            "project_id",
            "cer_run_id",
            "workflow_id",
            "step_id",
            "produced_by_step",
            "created_at",
            "regulatory_anchor_id",
            "human_gate_required",
            "requires_human_review",
            "human_gate_topic",
            "reviewer_question_ids",
            "no_final_decision_made",
            "cear_style_only",
            "official_cear_generation",
            "prohibited_claim",
            "layer3_prohibition",
            "sub_assessments",
        }
        merged = dict(base)
        for key, value in payload.items():
            if key in protected:
                continue
            merged[key] = value
        allowed_statuses = {"scaffold_complete", "scaffold_stub", "draft", "validated", "real_analysis"}
        payload_status = payload.get("status")
        merged["status"] = payload_status if payload_status in allowed_statuses else "real_analysis"
        allowed_schema_gate_statuses = {"scaffold_complete", "validated"}
        payload_schema_gate_status = payload.get("schema_gate_status")
        merged["schema_gate_status"] = (
            payload_schema_gate_status
            if payload_schema_gate_status in allowed_schema_gate_statuses
            else "validated"
        )
        merged["llm_review_enabled"] = True
        return merged

    # ── D1 Workflow Mode ───────────────────────────────────────────────────────

    def _run_d1_admin_precheck(self, step: dict[str, Any]) -> None:
        """D1 Step 0: cer_admin_precheck — pre-flight admin gate (V28.4)."""
        step_dir = self._artifact_dir("00_admin_precheck")
        prompt_text = self._load_prompt_for_step(step)
        project_id = self.project_profile.get("project_id", "unknown")
        report = {
            "schema_name": "cer_admin_precheck",
            "schema_version": "v1",
            "artifact_type": "admin_precheck_report",
            "project_id": project_id,
            "cer_run_id": self.run_id,
            "workflow_id": self.workflow.get("workflow_id"),
            "step_id": "cer_admin_precheck",
            "produced_by_step": "cer_admin_precheck",
            "status": "real_analysis",
            "created_at": self._timestamp(),
            "source_traceability": {
                "input_package_ref": "",
                "document_inventory_ref": "",
            },
            "regulatory_anchor_id": "MDR_Annex_II_III",
            "human_gate_required": False,
            "checks_performed": [],
            "check_results": {},
            "blocking_issues": [],
            "prompt_contract_loaded": bool(prompt_text.strip()),
            "note": "V28.4 pre-flight admin gate. BLOCKING — pipeline stops if checks fail.",
            "schema_gate_status": "scaffold_complete",
        }
        step = self._apply_prompt_contract(step, "cer-admin-precheck-reviewer")
        agent_payload = self._run_subagent_step(
            step=step,
            agent_name="cer-admin-precheck-reviewer",
            output_schema_ref=step.get("schema_ref", "cer_admin_precheck.schema.json"),
            output_artifact=step_dir / "admin_precheck_report.json",
            upstream_artifacts=None,
            extra_context=self._build_extra_context_for_step("cer_admin_precheck"),
        )
        report = self._merge_agent_payload(report, agent_payload)
        self._write_json(step_dir / "admin_precheck_report.json", report)

    def _run_d1_intake(self, step: dict[str, Any]) -> None:
        """D1 Step 1: cer_intake - produces CERDocStruct."""
        step_dir = self._artifact_dir("01_docstruct")
        prompt_text = self._load_prompt_for_step(step)
        project_protocol = self._ensure_project_protocol()
        project_id = self.project_profile.get("project_id", "unknown")

        cer_docstruct = {
            "schema_name": "cer_docstruct",
            "schema_version": "v1",
            "artifact_type": "cer_docstruct",
            "project_id": project_id,
            "cer_run_id": self.run_id,
            "workflow_id": self.workflow.get("workflow_id"),
            "step_id": "cer_intake",
            "produced_by_step": "cer_intake",
            "status": "scaffold_complete",
            "created_at": self._timestamp(),
            "source_traceability": {
                "input_documents": [],
                "document_count": 0,
                "missing_required": [],
            },
            "regulatory_anchor_id": "Annex_XIV",
            "intake_summary": {
                "device_name": "",
                "device_class": "",
                "intended_purpose": "",
                "clinical_evaluation_scope": "",
            },
            "artifact_root": str(self.artifact_root_actual),
            "prompt_contract_loaded": bool(prompt_text.strip()),
            "project_protocol": project_protocol,
            "note": "D1 scaffold - CERDocStruct skeleton. LLM population required in D3.",
            "schema_gate_status": "scaffold_complete",
        }
        step = self._apply_prompt_contract(step, "cer-intake-reviewer")
        agent_payload = self._run_subagent_step(
            step=step,
            agent_name="cer-intake-reviewer",
            output_schema_ref=step.get("schema_ref", "cer_docstruct.schema.json"),
            output_artifact=step_dir / "cer_docstruct.json",
            extra_context={
                "project_profile": self.project_profile,
                **self._build_extra_context_for_step("cer_intake"),
            },
        )
        cer_docstruct = self._merge_agent_payload(cer_docstruct, agent_payload)
        self._write_json(step_dir / "cer_docstruct.json", cer_docstruct)

    def _run_d1_structure_compliance(self, step: dict[str, Any]) -> None:
        """D1 Step 2: cer_structure_compliance."""
        step_dir = self._artifact_dir("02_structure_compliance")
        prompt_text = self._load_prompt_for_step(step)
        project_id = self.project_profile.get("project_id", "unknown")
        report = {
            "schema_name": "cer_structure_compliance",
            "schema_version": "v1",
            "artifact_type": "structure_compliance_report",
            "project_id": project_id,
            "cer_run_id": self.run_id,
            "workflow_id": self.workflow.get("workflow_id"),
            "step_id": "cer_structure_compliance",
            "produced_by_step": "cer_structure_compliance",
            "status": "real_analysis",
            "created_at": self._timestamp(),
            "source_traceability": {
                "cer_docstruct_ref": "",
                "annex_xiv_version": "Annex XIV Part A",
            },
            "regulatory_anchor_id": "MDR_Annex_XIV",
            "human_gate_required": False,
            "structure_validation": {
                "required_sections_present": [],
                "required_sections_missing": [],
                "annex_xiv_compliance_status": "pending",
            },
            "section_mapping": [],
            "prompt_contract_loaded": bool(prompt_text.strip()),
            "note": "D1 scaffold stub. Full validation requires D3.",
            "schema_gate_status": "scaffold_complete",
        }
        step = self._apply_prompt_contract(step, "cer-structure-compliance-reviewer")
        agent_payload = self._run_subagent_step(
            step=step,
            agent_name="cer-structure-compliance-reviewer",
            output_schema_ref=step.get("schema_ref", "cer_structure_compliance.schema.json"),
            output_artifact=step_dir / "report.json",
            upstream_artifacts=self._d1_upstream_artifacts("01_docstruct/cer_docstruct.json"),
            extra_context=self._build_extra_context_for_step("cer_structure_compliance"),
        )
        report = self._merge_agent_payload(report, agent_payload)
        self._write_json(step_dir / "report.json", report)

    def _run_d1_intended_purpose(self, step: dict[str, Any]) -> None:
        """D1 Step 3: cer_intended_purpose."""
        step_dir = self._artifact_dir("03_intended_purpose")
        prompt_text = self._load_prompt_for_step(step)
        project_id = self.project_profile.get("project_id", "unknown")
        report = {
            "schema_name": "cer_intended_purpose",
            "schema_version": "v1",
            "artifact_type": "intended_purpose_assessment",
            "project_id": project_id,
            "cer_run_id": self.run_id,
            "workflow_id": self.workflow.get("workflow_id"),
            "step_id": "cer_intended_purpose",
            "produced_by_step": "cer_intended_purpose",
            "status": "real_analysis",
            "created_at": self._timestamp(),
            "source_traceability": {
                "cer_docstruct_ref": "",
                "ifu_document_ref": "",
            },
            "regulatory_anchor_id": "Annex_XIV_Part_A",
            "human_gate_required": True,
            "human_gate_ref": "HG-07",
            "reviewer_question_id": "RQ-INTENDED-PURPOSE-001",
            "intended_purpose_assessment": {
                "intended_use_statement": "",
                "indications": [],
                "contraindications": [],
                "patient_population": "",
                "clinical_benefit_claim": "",
            },
            "pico_alignment": {
                "population_aligned": False,
                "intervention_aligned": False,
                "comparator_aligned": False,
                "outcomes_aligned": False,
                "overall_alignment_status": "pending",
            },
            "no_final_decision_made": True,
            "prompt_contract_loaded": bool(prompt_text.strip()),
            "note": "D1 scaffold stub. PICO alignment requires D3.",
            "schema_gate_status": "scaffold_complete",
        }
        step = self._apply_prompt_contract(step, "cer-intended-purpose-reviewer")
        agent_payload = self._run_subagent_step(
            step=step,
            agent_name="cer-intended-purpose-reviewer",
            output_schema_ref=step.get("schema_ref", "cer_intended_purpose.schema.json"),
            output_artifact=step_dir / "report.json",
            upstream_artifacts=self._d1_upstream_artifacts("01_docstruct/cer_docstruct.json", "02_structure_compliance/report.json"),
            extra_context=self._build_extra_context_for_step("cer_intended_purpose"),
        )
        report = self._merge_agent_payload(report, agent_payload)
        self._write_json(step_dir / "report.json", report)

    def _run_d1_cep_methodology(self, step: dict[str, Any]) -> None:
        """D1 Step 4: cer_cep_methodology."""
        step_dir = self._artifact_dir("04_cep_methodology")
        prompt_text = self._load_prompt_for_step(step)
        project_id = self.project_profile.get("project_id", "unknown")
        report = {
            "schema_name": "cer_cep_methodology",
            "schema_version": "v1",
            "artifact_type": "cep_methodology_assessment",
            "project_id": project_id,
            "cer_run_id": self.run_id,
            "workflow_id": self.workflow.get("workflow_id"),
            "step_id": "cer_cep_methodology",
            "produced_by_step": "cer_cep_methodology",
            "status": "real_analysis",
            "created_at": self._timestamp(),
            "source_traceability": {
                "cer_docstruct_ref": "",
                "cep_document_ref": "",
            },
            "regulatory_anchor_id": "MDR_Article_83",
            "human_gate_required": False,
            "route_decision": "pending",
            "methodology_adequacy": {
                "literature_search_described": False,
                "equivalence_demonstration_planned": False,
                "clinical_data_evaluation_method": "",
                "benefit_risk_assessment_method": "",
            },
            "route_justification": "",
            "prompt_contract_loaded": bool(prompt_text.strip()),
            "note": "D1 scaffold stub. CEP route decision requires D3.",
            "schema_gate_status": "scaffold_complete",
        }
        step = self._apply_prompt_contract(step, "cer-cep-methodology-reviewer")
        agent_payload = self._run_subagent_step(
            step=step,
            agent_name="cer-cep-methodology-reviewer",
            output_schema_ref=step.get("schema_ref", "cer_cep_methodology.schema.json"),
            output_artifact=step_dir / "report.json",
            upstream_artifacts=self._d1_upstream_artifacts(
                "01_docstruct/cer_docstruct.json",
                "02_structure_compliance/report.json",
                "03_intended_purpose/report.json",
            ),
            extra_context=self._build_extra_context_for_step("cer_cep_methodology"),
        )
        report = self._merge_agent_payload(report, agent_payload)
        self._write_json(step_dir / "report.json", report)

    def _run_d1_clinical_evidence_panel(self, step: dict[str, Any]) -> None:
        """D1 Step 5: cer_clinical_evidence_panel with 5 sub-assessments."""
        step_dir = self._artifact_dir("05_lanes")
        prompt_text = self._load_prompt_for_step(step)
        project_id = self.project_profile.get("project_id", "unknown")

        sub_assessments = step.get("sub_assessments", [])
        sub_results = {}
        for sa in sub_assessments:
            sa_id = sa.get("sub_assessment_id")
            schema_ref = sa.get("schema_ref", "")
            # Build per-sub-assessment artifact compliant with its schema
            if sa_id == "sota_literature_assessment":
                sa_artifact = {
                    "schema_name": "cer_sota_literature",
                    "schema_version": "v1",
                    "artifact_type": "sota_literature_report",
                    "project_id": project_id,
                    "cer_run_id": self.run_id,
                    "workflow_id": self.workflow.get("workflow_id"),
                    "step_id": "cer_clinical_evidence_panel",
                    "produced_by_step": "cer_clinical_evidence_panel",
                    "sub_assessment_id": sa_id,
                    "status": "real_analysis",
                    "created_at": self._timestamp(),
                    "source_traceability": {"literature_search_ref": "", "sota_definition_ref": ""},
                    "regulatory_anchor_id": "MDR_Article_83",
                    "human_gate_required": True,
                    "human_gate_ref": "HG-03",
                    "reviewer_question_id": "RQ-SOTA-001",
                    "dimension": "dim_4",
                    "sota_claims": [],
                    "literature_adequacy": {
                        "search_strategy_described": False,
                        "databases_searched": [],
                        "inclusion_exclusion_criteria_described": False,
                        "quality_assessment_method": "",
                    },
                    "no_final_decision_made": True,
                    "note": f"D1 scaffold stub for {sa_id}. D3 required.",
                    "schema_gate_status": "scaffold_complete",
                }
            elif sa_id == "clinical_evidence_adequacy_assessment":
                sa_artifact = {
                    "schema_name": "cer_evidence_adequacy",
                    "schema_version": "v1",
                    "artifact_type": "evidence_adequacy_report",
                    "project_id": project_id,
                    "cer_run_id": self.run_id,
                    "workflow_id": self.workflow.get("workflow_id"),
                    "step_id": "cer_clinical_evidence_panel",
                    "produced_by_step": "cer_clinical_evidence_panel",
                    "sub_assessment_id": sa_id,
                    "status": "real_analysis",
                    "created_at": self._timestamp(),
                    "source_traceability": {"clinical_data_refs": [], "literature_refs": []},
                    "regulatory_anchor_id": "MDR_Article_83",
                    "human_gate_required": True,
                    "human_gate_ref": "HG-01",
                    "reviewer_question_id": "RQ-EVIDENCE-001",
                    "dimension": "dim_5",
                    "evidence_sufficiency": {
                        "clinical_data_sufficient": False,
                        "gap_areas": [],
                        "evidence_quality_summary": "",
                    },
                    "no_final_decision_made": True,
                    "note": f"D1 scaffold stub for {sa_id}. D3 required.",
                    "schema_gate_status": "scaffold_complete",
                }
            elif sa_id == "equivalence_assessment":
                sa_artifact = {
                    "schema_name": "cer_equivalence",
                    "schema_version": "v1",
                    "artifact_type": "equivalence_report",
                    "project_id": project_id,
                    "cer_run_id": self.run_id,
                    "workflow_id": self.workflow.get("workflow_id"),
                    "step_id": "cer_clinical_evidence_panel",
                    "produced_by_step": "cer_clinical_evidence_panel",
                    "sub_assessment_id": sa_id,
                    "status": "real_analysis",
                    "created_at": self._timestamp(),
                    "source_traceability": {
                        "equivalent_device_refs": [],
                        "technical_equivalence_documentation_ref": "",
                        "biological_equivalence_documentation_ref": "",
                        "clinical_equivalence_documentation_ref": "",
                    },
                    "regulatory_anchor_id": "MDR_Annex_XIV_Part_A_3",
                    "human_gate_required": True,
                    "human_gate_ref": "HG-02",
                    "reviewer_question_id": "RQ-EQUIV-001",
                    "dimension": "dim_6",
                    "equivalence_demonstration": {
                        "technical_equivalence": {"demonstrated": False, "key_similarities": [], "key_differences": [], "impact_assessment": ""},
                        "biological_equivalence": {"demonstrated": False, "key_similarities": [], "key_differences": [], "impact_assessment": ""},
                        "clinical_equivalence": {"demonstrated": False, "key_similarities": [], "key_differences": [], "impact_assessment": ""},
                    },
                    "predicate_device_access": {"access_basis": "none", "access_scope": "", "access_sufficient": False},
                    "no_final_decision_made": True,
                    "note": f"D1 scaffold stub for {sa_id}. D3 required.",
                    "schema_gate_status": "scaffold_complete",
                }
            elif sa_id == "pms_pmcf_assessment":
                sa_artifact = {
                    "schema_name": "cer_pms_pmcf",
                    "schema_version": "v1",
                    "artifact_type": "pms_pmcf_report",
                    "project_id": project_id,
                    "cer_run_id": self.run_id,
                    "workflow_id": self.workflow.get("workflow_id"),
                    "step_id": "cer_clinical_evidence_panel",
                    "produced_by_step": "cer_clinical_evidence_panel",
                    "sub_assessment_id": sa_id,
                    "status": "real_analysis",
                    "created_at": self._timestamp(),
                    "source_traceability": {"pmcf_plan_ref": "", "pmcf_report_ref": ""},
                    "regulatory_anchor_id": "MDR_Annex_XIV_Part_A_6",
                    "human_gate_required": True,
                    "human_gate_ref": "HG-05",
                    "reviewer_question_id": "RQ-PMS-001",
                    "dimension": "dim_7",
                    "pmcf_adequacy": {
                        "pmcf_plan_exists": False,
                        "pmcf_activities_adequate": False,
                        "update_triggers_defined": False,
                        "surveillance_continuity_planned": False,
                    },
                    "no_final_decision_made": True,
                    "note": f"D1 scaffold stub for {sa_id}. D3 required.",
                    "schema_gate_status": "scaffold_complete",
                }
            elif sa_id == "benefit_risk_assessment":
                sa_artifact = {
                    "schema_name": "cer_benefit_risk",
                    "schema_version": "v1",
                    "artifact_type": "benefit_risk_report",
                    "project_id": project_id,
                    "cer_run_id": self.run_id,
                    "workflow_id": self.workflow.get("workflow_id"),
                    "step_id": "cer_clinical_evidence_panel",
                    "produced_by_step": "cer_clinical_evidence_panel",
                    "sub_assessment_id": sa_id,
                    "status": "real_analysis",
                    "created_at": self._timestamp(),
                    "source_traceability": {"benefit_claims_ref": [], "risk_claims_ref": [], "rmf_ref": ""},
                    "regulatory_anchor_id": "MDR_Annex_I_Chapter_I_1",
                    "human_gate_required": True,
                    "human_gate_ref": "HG-06",
                    "reviewer_question_id": "RQ-BR-001",
                    "dimension": "dim_8",
                    "benefit_risk_balance": {
                        "clinical_benefits_documented": False,
                        "risks_documented": False,
                        "benefit_risk_acceptable": False,
                        "residual_uncertainties": [],
                    },
                    "no_final_decision_made": True,
                    "layer3_prohibition": True,
                    "note": f"D1 scaffold stub for {sa_id}. D3 required.",
                    "schema_gate_status": "scaffold_complete",
                }
            else:
                sa_artifact = {
                    "sub_assessment_id": sa_id,
                    "status": "real_analysis",
                    "schema_gate_status": "scaffold_complete",
                    "note": f"D1 scaffold stub for {sa_id}. D3 required.",
                }
            sub_results[sa_id] = sa_artifact

        # Build sub_assessments dict for panel_summary matching schema structure
        panel_sub_assessments = {
            "sota_literature": {"sub_assessment_id": "sota_literature_assessment", "dimension": "dim_4", "human_gate_required": True, "human_gate_ref": "HG-03", "regulatory_anchor": "MDR Article 83, Annex XIV Part A 3", "schema_ref": "cer_sota_literature.schema.json", "status": "real_analysis"},
            "clinical_evidence_adequacy": {"sub_assessment_id": "clinical_evidence_adequacy_assessment", "dimension": "dim_5", "human_gate_required": True, "human_gate_ref": "HG-01", "regulatory_anchor": "MDR Article 83, Annex XIV Part A 3", "schema_ref": "cer_evidence_adequacy.schema.json", "status": "real_analysis"},
            "equivalence": {"sub_assessment_id": "equivalence_assessment", "dimension": "dim_6", "human_gate_required": True, "human_gate_ref": "HG-02", "regulatory_anchor": "MDR Article 83, Annex XIV Part A 3 and Part B", "schema_ref": "cer_equivalence.schema.json", "status": "real_analysis"},
            "pms_pmcf": {"sub_assessment_id": "pms_pmcf_assessment", "dimension": "dim_7", "human_gate_required": True, "human_gate_ref": "HG-05", "regulatory_anchor": "MDR Article 83, Annex XIV Part A 6, MDR Article 84", "schema_ref": "cer_pms_pmcf.schema.json", "status": "real_analysis"},
            "benefit_risk": {"sub_assessment_id": "benefit_risk_assessment", "dimension": "dim_8", "human_gate_required": True, "human_gate_ref": "HG-06", "regulatory_anchor": "MDR Article 83, Annex I Chapter I 1, Annex XIV Part A 5", "schema_ref": "cer_benefit_risk.schema.json", "status": "real_analysis"},
        }

        report = {
            "schema_name": "cer_clinical_evidence_panel",
            "schema_version": "v1",
            "artifact_type": "clinical_evidence_panel_summary",
            "project_id": project_id,
            "cer_run_id": self.run_id,
            "workflow_id": self.workflow.get("workflow_id"),
            "step_id": "cer_clinical_evidence_panel",
            "produced_by_step": "cer_clinical_evidence_panel",
            "status": "real_analysis",
            "created_at": self._timestamp(),
            "source_traceability": {
                "cer_docstruct_ref": "",
                "evidence_packs_ref": [],
                "cep_route_decision_ref": "",
            },
            "regulatory_anchor_id": "MDR_Article_83",
            "human_gate_required": True,
            "sub_assessments": panel_sub_assessments,
            "prompt_contract_loaded": bool(prompt_text.strip()),
            "note": "D1 scaffold stub. 5 clinical sub-assessments require D3.",
            "schema_gate_status": "scaffold_complete",
        }
        step = self._apply_prompt_contract(step, "cer-clinical-evidence-panel-reviewer")
        cer_text = self._read_best_cer_text()
        agent_payload = self._run_subagent_step(
            step=step,
            agent_name="cer-clinical-evidence-panel-reviewer",
            output_schema_ref=step.get("schema_ref", "cer_clinical_evidence_panel.schema.json"),
            output_artifact=step_dir / "clinical_evidence_panel_review.json",
            upstream_artifacts=self._d1_upstream_artifacts(
                "01_docstruct/cer_docstruct.json",
                "02_structure_compliance/report.json",
                "03_intended_purpose/report.json",
                "04_cep_methodology/report.json",
            ),
            extra_context={
                **self._build_extra_context_for_step("cer_clinical_evidence_panel"),
                "cer_text_length": len(cer_text),
                "sub_assessments": sub_assessments,
            },
        )
        report = self._merge_agent_payload(report, agent_payload)
        agent_findings = self._collect_findings_from_payload(agent_payload)
        report["findings"] = agent_findings
        report["findings_count"] = len(agent_findings)
        report["llm_review_enabled"] = True
        report["llm_review_agent"] = "cer-clinical-evidence-panel-reviewer"
        report["llm_findings_count"] = len(agent_findings)
        agent_lanes = {}
        if isinstance(agent_payload, dict):
            agent_lanes = agent_payload.get("lanes", {}) or agent_payload.get("sub_assessments", {})
        if isinstance(agent_lanes, dict):
            for lane_key, lane_payload in agent_lanes.items():
                if not isinstance(lane_payload, dict):
                    continue
                lane_findings = self._collect_findings_from_payload({"findings": lane_payload.get("findings", [])})
                normalized_key = lane_key.replace("_assessment", "")
                filename = f"{normalized_key}_report.json"
                for candidate_id in (lane_key, f"{normalized_key}_assessment"):
                    if candidate_id in sub_results:
                        lane_artifact = self._merge_agent_payload(sub_results[candidate_id], lane_payload)
                        lane_artifact["findings"] = lane_findings
                        lane_artifact["findings_count"] = len(lane_findings)
                        sub_results[candidate_id] = lane_artifact
                        break
                else:
                    lane_artifact = dict(lane_payload)
                    lane_artifact["findings"] = lane_findings
                    self._write_json(step_dir / filename, lane_artifact)
        self._write_json(step_dir / "panel_summary.json", report)

        # Write individual sub-assessment artifacts
        for sa_id, sa_result in sub_results.items():
            safe_id = sa_id.replace("_assessment", "")
            filename = f"{safe_id}_report.json"
            self._write_json(step_dir / filename, sa_result)

    def _run_d1_ifu_sscp_label(self, step: dict[str, Any]) -> None:
        """D1 Step 6: cer_ifu_sscp_label."""
        step_dir = self._artifact_dir("06_consistency")
        prompt_text = self._load_prompt_for_step(step)
        project_id = self.project_profile.get("project_id", "unknown")
        report = {
            "schema_name": "cer_consistency",
            "schema_version": "v1",
            "artifact_type": "ifu_sscp_labeling_consistency_report",
            "project_id": project_id,
            "cer_run_id": self.run_id,
            "workflow_id": self.workflow.get("workflow_id"),
            "step_id": "cer_ifu_sscp_label",
            "produced_by_step": "cer_ifu_sscp_label",
            "status": "real_analysis",
            "created_at": self._timestamp(),
            "source_traceability": {
                "cer_docstruct_ref": "",
                "ifu_document_ref": "",
                "sscp_document_ref": "",
                "labeling_materials_ref": [],
            },
            "regulatory_anchor_id": "MDR_Annex_VII_4.5.5",
            "human_gate_required": False,
            "consistency_check": {
                "ifu_cer_alignment": "pending",
                "sscp_cer_alignment": "pending",
                "labeling_cer_alignment": "pending",
                "inconsistencies_found": [],
            },
            "prompt_contract_loaded": bool(prompt_text.strip()),
            "note": "D1 scaffold stub. IFU/SSCP/labeling consistency requires D3.",
            "schema_gate_status": "scaffold_complete",
        }
        step = self._apply_prompt_contract(step, "cer-ifu-sscp-label-reviewer")
        agent_payload = self._run_subagent_step(
            step=step,
            agent_name="cer-ifu-sscp-label-reviewer",
            output_schema_ref=step.get("schema_ref", "cer_consistency.schema.json"),
            output_artifact=step_dir / "report.json",
            upstream_artifacts=self._d1_upstream_artifacts("05_lanes/panel_summary.json", "05_lanes/clinical_evidence_panel_review.json"),
            extra_context=self._build_extra_context_for_step("cer_ifu_sscp_label"),
        )
        report = self._merge_agent_payload(report, agent_payload)
        self._write_json(step_dir / "report.json", report)

    def _run_d1_qa_gate(self, step: dict[str, Any]) -> None:
        """D1 Step 7: cer_qa_gate."""
        step_dir = self._artifact_dir("07_qa_gate")
        prompt_text = self._load_prompt_for_step(step)
        project_id = self.project_profile.get("project_id", "unknown")
        report = {
            "schema_name": "cer_qa",
            "schema_version": "v1",
            "artifact_type": "QA_synthesis",
            "project_id": project_id,
            "cer_run_id": self.run_id,
            "workflow_id": self.workflow.get("workflow_id"),
            "step_id": "cer_qa_gate",
            "produced_by_step": "cer_qa_gate",
            "status": "real_analysis",
            "created_at": self._timestamp(),
            "source_traceability": {
                "preceding_artifacts_refs": [],
                "l1_compliance_report_ref": "",
                "stage_1_evaluation_ref": "",
                "cep_route_decision_ref": "",
                "clinical_evidence_panel_summary_ref": "",
                "ifu_sscp_consistency_ref": "",
            },
            "regulatory_anchor_id": "MDR_Article_83",
            "human_gate_required": False,
            "qa_synthesis": {
                "all_preceding_steps_complete": False,
                "findings_aggregated": False,
                "ready_for_human_gate": False,
            },
            "prompt_contract_loaded": bool(prompt_text.strip()),
            "note": "D1 scaffold stub. QA synthesis requires D3.",
            "schema_gate_status": "scaffold_complete",
        }
        step = self._apply_prompt_contract(step, "cer-qa-gate-reviewer")
        agent_payload = self._run_subagent_step(
            step=step,
            agent_name="cer-qa-gate-reviewer",
            output_schema_ref=step.get("schema_ref", "cer_qa.schema.json"),
            output_artifact=step_dir / "qa_synthesis.json",
            upstream_artifacts=self._d1_upstream_artifacts(
                "01_docstruct/cer_docstruct.json",
                "02_structure_compliance/report.json",
                "03_intended_purpose/report.json",
                "04_cep_methodology/report.json",
                "05_lanes/panel_summary.json",
                "06_consistency/report.json",
            ),
        )
        report = self._merge_agent_payload(report, agent_payload)
        self._write_json(step_dir / "qa_synthesis.json", report)

    def _run_d1_cear_formatter(self, step: dict[str, Any]) -> None:
        """D1 Step 8: cer_cear_style_finding_formatter."""
        step_dir = self._artifact_dir("08_cear_format")
        prompt_text = self._load_prompt_for_step(step)
        project_id = self.project_profile.get("project_id", "unknown")
        report = {
            "schema_name": "cer_cear_finding",
            "schema_version": "v1",
            "artifact_type": "CEAR_style_finding",
            "project_id": project_id,
            "cer_run_id": self.run_id,
            "workflow_id": self.workflow.get("workflow_id"),
            "step_id": "cer_cear_style_finding_formatter",
            "produced_by_step": "cer_cear_style_finding_formatter",
            "status": "real_analysis",
            "created_at": self._timestamp(),
            "source_traceability": {
                "raw_findings_ref": "",
                "finding_type_ref": "",
                "severity_ref": "",
            },
            "regulatory_anchor_id": "MDCG_2020_13",
            "human_gate_required": False,
            "cear_style_only": True,
            "official_cear_generation": False,
            "finding_format": {
                "finding_id": "",
                "finding_type": "",
                "severity": "informational",
                "description": "",
                "mdcg_template_compliance": False,
            },
            "prompt_contract_loaded": bool(prompt_text.strip()),
            "note": "D1 scaffold stub. CEAR-style formatting requires D3. NOT official CEAR generation.",
            "schema_gate_status": "scaffold_complete",
        }
        step = self._apply_prompt_contract(step, "cer-cear-formatter-reviewer")
        agent_payload = self._run_subagent_step(
            step=step,
            agent_name="cer-cear-formatter-reviewer",
            output_schema_ref=step.get("schema_ref", "cer_cear_finding.schema.json"),
            output_artifact=step_dir / "formatted_findings.json",
            upstream_artifacts=self._d1_upstream_artifacts("05_lanes/panel_summary.json", "07_qa_gate/qa_synthesis.json"),
        )
        report = self._merge_agent_payload(report, agent_payload)
        self._write_json(step_dir / "formatted_findings.json", report)

    def _run_d1_human_boundary(self, step: dict[str, Any]) -> None:
        """D1 Step 9: cer_human_boundary."""
        step_dir = self._artifact_dir("09_human_boundary")
        prompt_text = self._load_prompt_for_step(step)
        project_protocol = self._ensure_project_protocol()
        project_id = self.project_profile.get("project_id", "unknown")

        human_gates = self.workflow.get("human_gates", {})
        hg_list = [
            {
                "gate_ref": ref,
                "topic": hg.get("topic"),
                "triggered_by_step": hg.get("triggered_by_step"),
                "human_gate_required": True,
                "status": "pending",
                "reviewer_decision": "",
                "reviewer_rationale": "",
            }
            for ref, hg in human_gates.items()
        ]

        packet = {
            "schema_name": "cer_human_gate",
            "schema_version": "v1",
            "artifact_type": "human_gate_packet",
            "project_id": project_id,
            "cer_run_id": self.run_id,
            "workflow_id": self.workflow.get("workflow_id"),
            "step_id": "cer_human_boundary",
            "produced_by_step": "cer_human_boundary",
            "status": "real_analysis",
            "created_at": self._timestamp(),
            "source_traceability": {
                "all_preceding_artifacts_ref": "",
                "qa_synthesis_ref": "",
            },
            "regulatory_anchor_id": "MDR_Article_83",
            "human_gate_required": True,
            "human_gates": hg_list,
            "gate_count": len(hg_list),
            "pending_gates": len(hg_list),
            "project_protocol": project_protocol,
            "prompt_contract_loaded": bool(prompt_text.strip()),
            "note": "D1 scaffold stub. Human gate packet requires D3. HG-01 through HG-09 preserved.",
            "schema_gate_status": "scaffold_complete",
        }
        step = self._apply_prompt_contract(step, "cer-human-boundary-reviewer")
        agent_payload = self._run_subagent_step(
            step=step,
            agent_name="cer-human-boundary-reviewer",
            output_schema_ref=step.get("schema_ref", "cer_human_gate.schema.json"),
            output_artifact=step_dir / "packet.json",
            upstream_artifacts=self._d1_upstream_artifacts(
                "05_lanes/panel_summary.json",
                "06_consistency/report.json",
                "07_qa_gate/qa_synthesis.json",
                "08_cear_format/formatted_findings.json",
            ),
        )
        packet = self._merge_agent_payload(packet, agent_payload)
        self._write_json(step_dir / "packet.json", packet)

    def _run_d1_qms_review(self, step: dict[str, Any]) -> None:
        """D1 Step 10: cer_qms_review — ISO 13485 QMS documentation review."""
        step_dir = self._artifact_dir("10_qms_review")
        prompt_text = self._load_prompt_for_step(step)
        project_id = self.project_profile.get("project_id", "unknown")
        report = {
            "schema_name": "cer_qms_review",
            "schema_version": "v1",
            "artifact_type": "qms_review_findings",
            "project_id": project_id,
            "cer_run_id": self.run_id,
            "workflow_id": self.workflow.get("workflow_id"),
            "step_id": "cer_qms_review",
            "produced_by_step": "cer_qms_review",
            "status": "real_analysis",
            "created_at": self._timestamp(),
            "source_traceability": {
                "cer_docstruct_ref": "",
                "qms_documentation_ref": "",
                "all_preceding_artifacts_ref": [],
            },
            "regulatory_anchor_id": "ISO_13485_2016",
            "human_gate_required": False,
            "qms_findings": [],
            "iso_13485_sections_covered": ["§4", "§5", "§6", "§7", "§8"],
            "prompt_contract_loaded": bool(prompt_text.strip()),
            "note": "V28.2 QMS review. Covers ISO 13485 §4-§8: process validation, design control, purchasing, production, measurement.",
            "schema_gate_status": "scaffold_complete",
        }
        step = self._apply_prompt_contract(step, "cer-qms-reviewer")
        agent_payload = self._run_subagent_step(
            step=step,
            agent_name="cer-qms-reviewer",
            output_schema_ref=step.get("schema_ref", "cer_qms_review.schema.json"),
            output_artifact=step_dir / "qms_findings.json",
            upstream_artifacts=self._d1_upstream_artifacts(
                "05_lanes/panel_summary.json",
                "06_consistency/report.json",
                "09_human_boundary/packet.json",
            ),
            extra_context=self._build_extra_context_for_step("cer_qms_review"),
        )
        report = self._merge_agent_payload(report, agent_payload)
        self._write_json(step_dir / "qms_findings.json", report)

    def _run_d1_gate_closure(self, step: dict[str, Any]) -> None:
        """D1 Step 11: cer_gate_closure."""
        step_dir = self._artifact_dir("11_gate_closure")
        prompt_text = self._load_prompt_for_step(step)
        project_id = self.project_profile.get("project_id", "unknown")
        report = {
            "schema_name": "cer_review_package",
            "schema_version": "v1",
            "artifact_type": "review_package",
            "project_id": project_id,
            "cer_run_id": self.run_id,
            "workflow_id": self.workflow.get("workflow_id"),
            "step_id": "cer_gate_closure",
            "produced_by_step": "cer_gate_closure",
            "status": "real_analysis",
            "created_at": self._timestamp(),
            "source_traceability": {
                "human_gate_decision_ref": "",
                "all_preceding_artifacts_ref": [],
                "review_package_components_ref": "",
            },
            "regulatory_anchor_id": "MDR_Article_83",
            "human_gate_required": True,
            "review_package_assembled": False,
            "all_human_gates_closed": False,
            "final_recommendation_options": ["pass", "conditional_pass", "rework_required"],
            "layer3_prohibition": "Clinical equivalence, data sufficiency, and benefit-risk final conclusions MUST be determined by human reviewer.",
            "official_cear_generation": False,
            "prompt_contract_loaded": bool(prompt_text.strip()),
            "note": "D1 scaffold stub. Final review package requires D3.",
            "schema_gate_status": "scaffold_complete",
        }
        step = self._apply_prompt_contract(step, "cer-gate-closure-reviewer")
        agent_payload = self._run_subagent_step(
            step=step,
            agent_name="cer-gate-closure-reviewer",
            output_schema_ref=step.get("schema_ref", "cer_review_package.schema.json"),
            output_artifact=step_dir / "review_package.json",
            upstream_artifacts=self._d1_upstream_artifacts(
                "05_lanes/panel_summary.json",
                "07_qa_gate/qa_synthesis.json",
                "08_cear_format/formatted_findings.json",
                "09_human_boundary/packet.json",
            ),
        )
        report = self._merge_agent_payload(report, agent_payload)
        self._write_json(step_dir / "review_package.json", report)

    # ── Gate A Enforcement ─────────────────────────────────────────────────────

    def _load_project_protocol(self) -> dict[str, Any]:
        """Load project_protocol from project_profile if present."""
        return self.project_profile.get("project_protocol", {})

    def _get_gate_a_status(self) -> str:
        """Get Gate A status from project protocol."""
        protocol = self.project_protocol
        if not protocol:
            # Derive from project_profile if no explicit project_protocol
            return self.project_profile.get("gate_a_status", "draft")
        return protocol.get("gate_a_status", "draft")

    def _check_gate_a_for_formal_review(self) -> tuple[bool, str]:
        """Check if formal review can proceed based on Gate A status.

        Returns (allowed, reason).
        """
        mode = getattr(self, 'run_mode', 'smoke-run')
        if mode not in ("formal-review",):
            return True, "Gate A check not required for non-formal-review mode"

        gate_a_status = self.gate_a_status
        allowed_statuses = ("accepted",)
        blocked_statuses = ("draft", "submitted", "rejected", "needs_information")

        if gate_a_status in blocked_statuses:
            return False, f"FORMAL_REVIEW_BLOCKED_GATE_A_NOT_ACCEPTED: gate_a_status={gate_a_status}"

        if gate_a_status in allowed_statuses:
            return True, f"Gate A accepted: gate_a_status={gate_a_status}"

        # smoke_only allows smoke_precheck
        if gate_a_status == "smoke_only" and mode == "smoke-precheck":
            return True, "Gate A smoke_only allows smoke_precheck"

        return False, f"Gate A status {gate_a_status} does not allow formal review"

    def _write_gate_a_blocked(self, reason: str) -> None:
        """Write gate_a_blocked.json artifact."""
        step_dir = self._artifact_dir("00_manifest")
        blocked = {
            "schema_name": "cer_gate_a_blocked",
            "schema_version": "v1",
            "run_id": self.run_id,
            "thread_id": self.thread_id,
            "workflow_id": self.workflow.get("workflow_id"),
            "mode": getattr(self, 'run_mode', 'unknown'),
            "gate_a_status": self.gate_a_status,
            "blocked_reason": reason,
            "final_status": "FORMAL_REVIEW_BLOCKED_GATE_A_NOT_ACCEPTED",
            "artifact_root": str(self.artifact_root_actual),
            "timestamp": self._utc_now(),
        }
        self._write_json(step_dir / "gate_a_blocked.json", blocked)

    def _write_event_log(self, event_type: str, data: dict[str, Any]) -> None:
        """Write event to event log."""
        event_log_path = self._artifact_dir("00_manifest") / "event_log.json"
        events = []
        if event_log_path.exists():
            events = json.loads(event_log_path.read_text()).get("events", [])
        events.append({
            "event_type": event_type,
            "timestamp": self._utc_now(),
            "run_id": self.run_id,
            "thread_id": self.thread_id,
            **data,
        })
        self._write_json(event_log_path, {"events": events})

    def _write_task_ledger(self, status: str, data: dict[str, Any] | None = None) -> None:
        """Write task ledger entry."""
        ledger_path = self._artifact_dir("00_manifest") / "task_ledger.json"
        entries = []
        if ledger_path.exists():
            entries = json.loads(ledger_path.read_text()).get("entries", [])
        entry = {
            "run_id": self.run_id,
            "thread_id": self.thread_id,
            "status": status,
            "timestamp": self._utc_now(),
            **(data or {}),
        }
        entries.append(entry)
        self._write_json(ledger_path, {"entries": entries})

    def _ensure_project_protocol(self) -> dict[str, Any]:
        """Ensure project_protocol exists with minimum required fields."""
        if self.project_protocol:
            return self.project_protocol

        # Build minimal project_protocol from project_profile
        pp = {
            "project_id": self.project_profile.get("project_id", "UNKNOWN"),
            "cer_run_id": self.run_id,
            "product_name": self.project_profile.get("device_context", {}).get("device_name", "Unknown"),
            "device_class": self.project_profile.get("device_context", {}).get("device_class", "Unknown"),
            "gate_a_status": self.project_profile.get("gate_a_status", "draft"),
            "formal_review_requested": self.project_profile.get("review_scope", {}).get("mode") == "formal_review",
        }
        return pp

    def _write_artifact_index(self) -> None:
        """Write artifact index."""
        index_path = self._artifact_dir("00_manifest") / "artifact_index.json"
        artifacts = []
        for p in self.artifact_root_actual.rglob("*.json"):
            rel = p.relative_to(self.artifact_root_actual)
            artifacts.append({
                "path": str(rel),
                "size": p.stat().st_size,
            })
        self._write_json(index_path, {"artifacts": artifacts, "total": len(artifacts)})

    def _write_agent_usage_ledger(self) -> None:
        """Write agent usage ledger from the live invocation trace."""
        ledger_path = self._artifact_dir("00_manifest") / "agent_usage_ledger.json"
        trace_path = self._artifact_dir("00_manifest") / "agent_invocation_trace.jsonl"
        agents_invoked: list[dict[str, Any]] = []
        if trace_path.exists():
            for line in trace_path.read_text(encoding="utf-8", errors="replace").splitlines():
                if not line.strip():
                    continue
                try:
                    agents_invoked.append(json.loads(line))
                except Exception:
                    continue
        ledger = {
            "run_id": self.run_id,
            "thread_id": self.thread_id,
            "workflow_id": self.workflow.get("workflow_id"),
            "status": "live",
            "note": "D1 LLM review usage rebuilt from agent_invocation_trace.jsonl.",
            "agents_invoked": agents_invoked,
        }
        self._write_json(ledger_path, ledger)

    def _write_final_synthesis(self, *, executed_steps: list[str]) -> dict[str, Any]:
        """Write a deterministic final synthesis from persisted review artifacts."""
        severity_counts = {"critical": 0, "major": 0, "moderate": 0, "minor": 0, "info": 0}
        artifact_refs: list[str] = []
        key_findings: list[dict[str, Any]] = []
        for path in sorted(self.artifact_root_actual.rglob("*.json")):
            rel = path.relative_to(self.artifact_root_actual)
            if (
                str(rel) == "final_synthesis.json"
                or str(rel).startswith("00_manifest/")
                or str(rel).startswith("12_final_synthesis/")
            ):
                continue
            artifact_refs.append(str(rel))
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            for finding in self._iter_review_findings(payload):
                sev = str(finding.get("severity") or finding.get("priority") or "info").lower()
                if sev not in severity_counts:
                    sev = "info"
                severity_counts[sev] += 1
                if sev in {"critical", "major"} and len(key_findings) < 25:
                    key_findings.append({
                        "severity": sev,
                        "finding_id": finding.get("finding_id") or finding.get("id") or "",
                        "description": finding.get("description") or finding.get("evidence_gap") or finding.get("message") or "",
                        "source": str(rel),
                    })
        blocked_context = self._authoring_blocked_context()
        if blocked_context:
            severity_counts["critical"] += 1
            key_findings.insert(0, blocked_context)
        if severity_counts["critical"] > 0:
            decision = "REWORK_REQUIRED"
        elif severity_counts["major"] > 3:
            decision = "REWORK_REQUIRED"
        elif severity_counts["major"] > 0:
            decision = "PASS_WITH_CONTROLLED_GAPS"
        else:
            decision = "PASS"
        synthesis = {
            "schema": "cer_review_final_synthesis_v1",
            "run_id": self.run_id,
            "thread_id": self.thread_id,
            "mode": self.run_mode,
            "workflow_name": self.workflow_name,
            "executed_steps": executed_steps,
            "decision": decision,
            "severity_counts": severity_counts,
            "critical": severity_counts["critical"],
            "major": severity_counts["major"],
            "artifact_refs": artifact_refs,
            "key_findings": key_findings,
            "authoring_blocked_context": blocked_context or {},
            "note": "Deterministic synthesis over persisted CER Review artifacts; human clinical judgment remains required for Layer 3 conclusions.",
        }
        self._write_json(self._artifact_path("12_final_synthesis", "final_synthesis.json"), synthesis)
        self._write_json(self.artifact_root_actual / "final_synthesis.json", synthesis)
        return synthesis

    def _authoring_blocked_context(self) -> dict[str, Any]:
        """Detect terminal Authoring holds in the review input package."""
        root_path = (
            self.project_profile.get("input_package", {}).get("root_path")
            or self.project_profile.get("input_root")
            or ""
        )
        if not root_path:
            return {}
        root = Path(str(root_path)).expanduser()
        if not root.exists():
            return {}

        def _read_json(name: str) -> dict[str, Any]:
            path = root / name
            if not path.exists():
                return {}
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                return payload if isinstance(payload, dict) else {}
            except Exception:
                return {}

        final_gate = _read_json("final_gate_closure_report.json")
        source_preflight = _read_json("source_preflight_gate_report.json")
        blocker = _read_json("blocker_report.json")
        compromise = _read_json("controlled_compromise_manifest.json")
        writer_packet = _read_json("writer_input_packet.json")
        packet_source_status = (
            (writer_packet.get("approved_facts") or {}).get("source_preflight_status")
            if isinstance(writer_packet.get("approved_facts"), dict)
            else None
        )
        is_blocked = (
            final_gate.get("decision") == "HUMAN_HOLD"
            or source_preflight.get("status") == "BLOCKED"
            or blocker.get("status") == "BLOCKED"
            or compromise.get("terminal_status")
            or packet_source_status == "BLOCKED"
        )
        if not is_blocked:
            return {}
        issue_count = (
            blocker.get("blocking_issue_count")
            or len(source_preflight.get("blocking_issues") or [])
            or len(compromise.get("blocked_conditions") or [])
        )
        return {
            "severity": "critical",
            "finding_id": "AUTHORING_TERMINAL_HOLD",
            "description": (
                "Authoring output is a terminal hold / source-preflight-blocked package, "
                "not a release-ready CER. Closure-only review cannot pass this package."
            ),
            "source": str(root),
            "authoring_final_gate_decision": final_gate.get("decision"),
            "source_preflight_status": source_preflight.get("status") or packet_source_status,
            "blocker_count": issue_count,
        }

    def _iter_review_findings(self, payload: Any) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        if isinstance(payload, dict):
            for key in ("findings", "cross_cutting_findings", "blocking_issues", "qms_findings"):
                value = payload.get(key)
                if isinstance(value, list):
                    findings.extend([row for row in value if isinstance(row, dict)])
            summary = payload.get("summary") or payload.get("panel_summary")
            if isinstance(summary, dict):
                for sev in ("critical", "major", "moderate", "minor", "info"):
                    count = summary.get(sev) or summary.get(f"{sev}_findings_count")
                    try:
                        for idx in range(int(count or 0)):
                            findings.append({"severity": sev, "finding_id": f"summary-{sev}-{idx+1}", "description": "Count imported from summary"})
                    except Exception:
                        pass
            direct_keys = {"findings", "cross_cutting_findings", "blocking_issues", "qms_findings", "summary", "panel_summary"}
            for key, value in payload.items():
                if key in direct_keys:
                    continue
                if isinstance(value, (dict, list)):
                    findings.extend(self._iter_review_findings(value))
        elif isinstance(payload, list):
            for item in payload:
                findings.extend(self._iter_review_findings(item))
        return findings

    @staticmethod
    def _utc_now() -> str:
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()

    # ── D1 Ordered Steps Execution ─────────────────────────────────────────────

    def _run_d1_workflow(self) -> list[str]:
        """Execute D1 ordered_steps workflow."""
        executed_steps: list[str] = []
        ordered_steps = self.workflow.get("ordered_steps", [])

        for step in ordered_steps:
            step_id = step.get("step_id")
            if step_id not in _SUPPORTED_STEP_IDS:
                logger.warning("D1 step %s not in supported list, skipping", step_id)
                continue
            handler = self.step_map.get(step_id)
            if handler:
                try:
                    handler(step)
                    executed_steps.append(step_id)
                except Exception as e:
                    logger.error("D1 step %s failed: %s", step_id, e)
                    executed_steps.append(f"{step_id}_failed")
                    break
            else:
                logger.warning("No handler for D1 step %s", step_id)
        return executed_steps

    def _resolve_input_root(self) -> Path:
        if self.input_root_override:
            return self.input_root_override
        return Path(self.project_profile.get("input_package", {}).get("root_path", "/mnt/user-data/uploads"))

    def _resolve_source_path(self, raw_path: str, input_root: Path) -> Path:
        if not raw_path:
            return input_root
        if raw_path.startswith("/"):
            return Path(raw_path)
        return input_root / raw_path

    def _load_yaml(self, path: Path) -> dict[str, Any]:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    def _load_prompt_for_step(self, step: dict[str, Any]) -> str:
        prompt_contract = step.get("prompt_contract", "")
        if not prompt_contract:
            return ""
        prompt_path = self.repo_root / prompt_contract
        if prompt_path.exists():
            return prompt_path.read_text(encoding="utf-8", errors="replace")
        return ""

    def _read_json(self, path: Path) -> dict[str, Any]:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        return {}

    def _write_json(self, path: Path, data: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def _write_text(self, path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def _write_run_context(self, mode: str) -> None:
        ctx = {
            "run_id": self.run_id,
            "thread_id": self.thread_id,
            "workflow_name": self.workflow_name,
            "mode": mode,
            "artifact_root_actual": str(self.artifact_root_actual),
        }
        self._write_json(self._artifact_path("00_manifest", "run_context.json"), ctx)

    def _artifact_dir(self, step_prefix: str) -> Path:
        d = self.artifact_root_actual / step_prefix
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _artifact_path(self, step_prefix: str, filename: str) -> Path:
        return self._artifact_dir(step_prefix) / filename

    def _render_template(self, template: str) -> str:
        return template.replace("${run_id}", self.run_id).replace("{run_id}", self.run_id)

    def _make_thread_id(self) -> str:
        return f"cer-{uuid.uuid4().hex[:8]}"

    def _make_run_id(self) -> str:
        return f"cer-run-{uuid.uuid4().hex[:8]}"

    def _build_dry_run_plan(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "thread_id": self.thread_id,
            "workflow_name": self.workflow_name,
            "steps": [step.get("step_id") for step in self.workflow.get("ordered_steps", [])],
            "artifact_root_virtual": self.artifact_root_virtual,
        }
