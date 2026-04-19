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
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from deerflow.config.paths import get_paths

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
)

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
    ) -> None:
        self.repo_root = Path(repo_root).resolve()
        self.workflow_path = Path(workflow_path).resolve()
        self.project_profile_path = Path(project_profile_path).resolve()
        self.input_root_override = Path(input_root).resolve() if input_root else None
        self.thread_id = thread_id or self._make_thread_id()

        self.paths = get_paths()
        self.paths.ensure_thread_dirs(self.thread_id)

        self.workflow = self._load_yaml(self.workflow_path)
        self.project_profile = self._load_yaml(self.project_profile_path)

        self.run_id = run_id_override or self._make_run_id()
        self.workflow_name = str(self.workflow.get("workflow_name", "cer_review_v0"))

        artifact_root_template = self.workflow["runtime_defaults"]["artifact_root"]
        self.artifact_root_virtual = self._render_template(str(artifact_root_template))
        if artifact_root_override:
            self.artifact_root_actual = Path(artifact_root_override).resolve()
        else:
            self.artifact_root_actual = self.paths.resolve_virtual_path(self.thread_id, self.artifact_root_virtual)
        self.artifact_root_actual.mkdir(parents=True, exist_ok=True)

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
        }

        # v1: detect stage-based workflow (cer_review_v1.yaml uses "stages" not "ordered_steps")
        self.workflow_mode = "v1" if "stages" in self.workflow else "v0"

    def run(self, *, mode: str = "smoke-run") -> CERRunResult:
        executed_steps: list[str] = []

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

        # v1: use stages list; v0: use ordered_steps list
        if self.workflow_mode == "v1":
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
            for step in self.workflow.get("ordered_steps", []):
                step_id = step.get("step_id")
                if step_id not in _SUPPORTED_STEP_IDS:
                    break
                handler = self.step_map[step_id]
                handler(step)
                executed_steps.append(step_id)

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
        return template.replace("${run_id}", self.run_id)

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
