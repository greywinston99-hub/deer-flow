"""Knowledge Candidate Extractor.

Extracts knowledge candidates from CER artifacts:
1. Intake Classification (classification_output.json, evidence_classification_final.json)
2. Human Gate Decision (human_intake_gate_decision.json)
3. CER Route Decision (route_decision_draft.json)
4. HF Check Findings (layer1_findings.json, hf_check_report.json)
5. Lane Findings (03_lanes/*.json)
6. Gate Decisions (governance/gate_audits/*.json, decision_ledger_entry.json)
7. Findings Register (*_FINDINGS_REGISTER.json)
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from deerflow.runtime.cer_review.knowledge_candidate_state import (
    AssetType,
    CandidateState,
    KnowledgeCandidate,
    SOURCE_TYPE_MAPPINGS,
)

CER_ARTIFACTS_ROOT = Path("/Users/winstonwei/Documents/Playground/deer-flow/artifacts/cer")


class KnowledgeCandidateExtractor:
    """Extracts knowledge candidates from CER artifacts."""

    def __init__(self, project_id: str, artifact_root: Path | None = None):
        """Initialize extractor for a project.

        Args:
            project_id: CER project identifier
            artifact_root: Root path to artifacts (defaults to CER_ARTIFACTS_ROOT)
        """
        self.project_id = project_id
        self.artifact_root = artifact_root or CER_ARTIFACTS_ROOT / project_id
        self.candidates: list[KnowledgeCandidate] = []

    def extract_all(self) -> list[KnowledgeCandidate]:
        """Extract all candidates from all sources.

        Returns:
            List of extracted knowledge candidates (all in needs_human_review state)
        """
        self.candidates = []
        self.candidates.extend(self.extract_from_intake())
        self.candidates.extend(self.extract_from_cer_review())
        self.candidates.extend(self.extract_from_governance())

        # Transition all candidates to needs_human_review state
        for candidate in self.candidates:
            if candidate.state == CandidateState.NORMALIZED:
                candidate.transition(CandidateState.NEEDS_HUMAN_REVIEW)

        return self.candidates

    def extract_from_intake(self) -> list[KnowledgeCandidate]:
        """Extract from intake artifacts.

        Sources:
        - classification_output.json -> TerminologyUnit, EvidenceRequirement, FailurePattern
        - evidence_classification_final.json -> TerminologyUnit, EvidenceRequirement, FailurePattern
        - human_intake_gate_decision.json -> CaseLesson
        - completeness_output.json -> ChecklistUnit
        """
        candidates = []
        intake_dir = self.artifact_root / "intake"

        # Classification output
        class_output = intake_dir / "classification_output.json"
        if class_output.exists():
            candidates.extend(self._extract_from_classification_output(class_output))

        # Evidence classification final
        class_final = intake_dir / "evidence_classification_final.json"
        if class_final.exists():
            candidates.extend(self._extract_from_evidence_classification_final(class_final))

        # Human gate decision
        human_decision = intake_dir / "human_intake_gate_decision.json"
        if human_decision.exists():
            candidates.extend(self._extract_from_human_gate_decision(human_decision))

        # Completeness output
        completeness = intake_dir / "completeness_output.json"
        if completeness.exists():
            candidates.extend(self._extract_from_completeness(completeness))

        return candidates

    def extract_from_cer_review(self) -> list[KnowledgeCandidate]:
        """Extract from CER review artifacts.

        Searches round directories for review artifacts.
        """
        candidates = []
        review_root = self.artifact_root / "round_001" / "artifacts"

        if not review_root.exists():
            return candidates

        # Route decision
        route = review_root / "01_route" / "route_decision_draft.json"
        if route.exists():
            candidates.extend(self._extract_from_route_decision(route))

        # Layer1 findings (HF checks)
        layer1 = review_root / "02_layer1" / "layer1_findings.json"
        if layer1.exists():
            candidates.extend(self._extract_from_layer1_findings(layer1))

        # Lane findings
        lanes_dir = review_root / "03_lanes"
        if lanes_dir.exists():
            candidates.extend(self._extract_from_lane_findings(lanes_dir))

        # Conclusion artifacts
        conclusion_dir = review_root / "05_conclusion"
        if conclusion_dir.exists():
            candidates.extend(self._extract_from_conclusion(conclusion_dir))

        return candidates

    def extract_from_governance(self) -> list[KnowledgeCandidate]:
        """Extract from governance artifacts.

        Sources:
        - decision_ledger_entry.json -> CaseLesson
        - state_transition_log.jsonl -> WorkflowImprovement
        - gate_audits/*.json -> ReviewHeuristic
        """
        candidates = []
        governance_dir = self.artifact_root / "governance"

        if not governance_dir.exists():
            return candidates

        # Decision ledger entry
        ledger = governance_dir / "decision_ledger_entry.json"
        if ledger.exists():
            candidates.extend(self._extract_from_decision_ledger(ledger))

        return candidates

    # --- Intake extraction methods ---

    def _extract_from_classification_output(self, path: Path) -> list[KnowledgeCandidate]:
        """Extract from classification_output.json."""
        candidates = []
        data = _load_json(path)

        # Extract TerminologyUnit for each EP type found
        ep_types: set[str] = set()
        for item in data.get("classifications", []):
            ep_types.add(item.get("final_ep", "UNKNOWN"))
            ep_types.add(item.get("final_type", "UNKNOWN"))

        for ep_type in ep_types:
            if ep_type == "UNKNOWN":
                continue
            candidates.append(
                KnowledgeCandidate(
                    asset_type=AssetType.TERMINOLOGY_UNIT,
                    source_artifact=str(path),
                    source_chain=[self.project_id, str(path)],
                    payload={
                        "term": ep_type,
                        "source": "classification_output",
                        "definition": f"Evidence Package type: {ep_type}",
                    },
                    confidence=0.9,
                    project_id=self.project_id,
                    state=CandidateState.NORMALIZED,
                )
            )

        # Extract EvidenceRequirement for confidence thresholds
        conf_dist = data.get("confidence_distribution", {})
        if conf_dist:
            candidates.append(
                KnowledgeCandidate(
                    asset_type=AssetType.EVIDENCE_REQUIREMENT,
                    source_artifact=str(path),
                    source_chain=[self.project_id, str(path)],
                    payload={
                        "threshold_type": "classification_confidence",
                        "high_confidence_ge_08": conf_dist.get("high_confidence_ge_08", 0),
                        "medium_confidence_06_08": conf_dist.get("medium_confidence_06_08", 0),
                        "low_confidence_lt_06": conf_dist.get("low_confidence_lt_06", 0),
                        "auto_proceed_eligible": data.get("auto_proceed_eligible", False),
                    },
                    confidence=0.9,
                    project_id=self.project_id,
                    state=CandidateState.NORMALIZED,
                )
            )

        return candidates

    def _extract_from_evidence_classification_final(
        self, path: Path
    ) -> list[KnowledgeCandidate]:
        """Extract from evidence_classification_final.json."""
        candidates = []
        data = _load_json(path)

        # Extract FailurePattern for low-confidence classifications
        for item in data.get("classifications", []):
            confidence = item.get("confidence", 1.0)
            if confidence < 0.6:
                candidates.append(
                    KnowledgeCandidate(
                        asset_type=AssetType.FAILURE_PATTERN,
                        source_artifact=str(path),
                        source_chain=[self.project_id, str(path)],
                        payload={
                            "pattern_type": "low_confidence_classification",
                            "file_id": item.get("file_id"),
                            "relative_path": item.get("relative_path"),
                            "final_ep": item.get("final_ep"),
                            "confidence": confidence,
                            "review_reason": item.get("review_reason"),
                        },
                        confidence=confidence,
                        project_id=self.project_id,
                        state=CandidateState.NORMALIZED,
                    )
                )

        # Extract missing required documents as ChecklistUnit
        for missing in data.get("missing_required_documents", []):
            candidates.append(
                KnowledgeCandidate(
                    asset_type=AssetType.CHECKLIST_UNIT,
                    source_artifact=str(path),
                    source_chain=[self.project_id, str(path)],
                    payload={
                        "checklist_type": "required_document",
                        "ep": missing.get("ep"),
                        "required_type": missing.get("required_type"),
                        "description": missing.get("description"),
                        "severity": missing.get("severity"),
                        "note": missing.get("note"),
                    },
                    confidence=0.9,
                    project_id=self.project_id,
                    state=CandidateState.NORMALIZED,
                )
            )

        return candidates

    def _extract_from_human_gate_decision(self, path: Path) -> list[KnowledgeCandidate]:
        """Extract from human_intake_gate_decision.json."""
        candidates = []
        data = _load_json(path)

        candidates.append(
            KnowledgeCandidate(
                asset_type=AssetType.CASE_LESSON,
                source_artifact=str(path),
                source_chain=[self.project_id, str(path)],
                payload={
                    "lesson_type": "human_gate_decision",
                    "verdict": data.get("verdict"),
                    "notes": data.get("notes"),
                    "submitted_by": data.get("submitted_by"),
                    "submitted_at": data.get("submitted_at"),
                    "intake_session_id": data.get("intake_session_id"),
                },
                confidence=0.95,
                project_id=self.project_id,
                state=CandidateState.NORMALIZED,
            )
        )

        return candidates

    def _extract_from_completeness(self, path: Path) -> list[KnowledgeCandidate]:
        """Extract from completeness_output.json."""
        candidates = []
        data = _load_json(path)

        # Extract ChecklistUnit for completeness items
        for item in data.get("completeness_items", []):
            candidates.append(
                KnowledgeCandidate(
                    asset_type=AssetType.CHECKLIST_UNIT,
                    source_artifact=str(path),
                    source_chain=[self.project_id, str(path)],
                    payload={
                        "checklist_type": "intake_completeness",
                        "item_id": item.get("item_id"),
                        "status": item.get("status"),
                        "description": item.get("description"),
                        "severity": item.get("severity"),
                    },
                    confidence=0.85,
                    project_id=self.project_id,
                    state=CandidateState.NORMALIZED,
                )
            )

        return candidates

    # --- CER Review extraction methods ---

    def _extract_from_route_decision(self, path: Path) -> list[KnowledgeCandidate]:
        """Extract from route_decision_draft.json."""
        candidates = []
        data = _load_json(path)

        route = data.get("route_decision_draft", {})

        # Extract BoundaryCondition for article flags
        article_flags = [
            ("article_52_4_flag", "Article 52.4"),
            ("article_54_flag", "Article 54"),
            ("article_61_4_6_flag", "Article 61.4.6"),
            ("article_61_10_flag", "Article 61.10"),
        ]
        for flag_key, article_name in article_flags:
            flag_value = route.get(flag_key, "no")
            if flag_value and flag_value != "no":
                candidates.append(
                    KnowledgeCandidate(
                        asset_type=AssetType.BOUNDARY_CONDITION,
                        source_artifact=str(path),
                        source_chain=[self.project_id, str(path)],
                        payload={
                            "condition_type": "article_flag",
                            "article": article_name,
                            "flag_value": flag_value,
                            "route": route.get("primary_route_candidate"),
                        },
                        confidence=0.9,
                        project_id=self.project_id,
                        state=CandidateState.NORMALIZED,
                    )
                )

        # Extract RuleUnit for route eligibility
        candidates.append(
            KnowledgeCandidate(
                asset_type=AssetType.RULE_UNIT,
                source_artifact=str(path),
                source_chain=[self.project_id, str(path)],
                payload={
                    "rule_type": "route_eligibility",
                    "primary_route": route.get("primary_route_candidate"),
                    "secondary_routes": route.get("secondary_route_candidates", []),
                    "equivalence_present": route.get("equivalence_route_present", False),
                },
                confidence=0.85,
                project_id=self.project_id,
                state=CandidateState.NORMALIZED,
            )
        )

        return candidates

    def _extract_from_layer1_findings(self, path: Path) -> list[KnowledgeCandidate]:
        """Extract from layer1_findings.json (HF check findings)."""
        candidates = []
        data = _load_json(path)

        # Extract FailurePattern for each HF finding
        for item in data.get("hf_findings", []):
            candidates.append(
                KnowledgeCandidate(
                    asset_type=AssetType.FAILURE_PATTERN,
                    source_artifact=str(path),
                    source_chain=[self.project_id, str(path)],
                    payload={
                        "pattern_type": "hf_checkfinding",
                        "hf_id": item.get("hf_id"),
                        "label": item.get("label"),
                        "severity": item.get("severity"),
                        "status": item.get("status"),
                    },
                    confidence=0.9,
                    project_id=self.project_id,
                    state=CandidateState.NORMALIZED,
                )
            )

        # Extract ChecklistUnit for completeness status
        status = data.get("completeness_status")
        if status:
            candidates.append(
                KnowledgeCandidate(
                    asset_type=AssetType.CHECKLIST_UNIT,
                    source_artifact=str(path),
                    source_chain=[self.project_id, str(path)],
                    payload={
                        "checklist_type": "layer1_completeness",
                        "status": status,
                        "total_findings": len(data.get("hf_findings", [])),
                    },
                    confidence=0.85,
                    project_id=self.project_id,
                    state=CandidateState.NORMALIZED,
                )
            )

        return candidates

    def _extract_from_lane_findings(self, lanes_dir: Path) -> list[KnowledgeCandidate]:
        """Extract from lane findings JSON files."""
        candidates = []

        lane_files = {
            "claim_consistency_matrix.json": AssetType.CROSS_DOCUMENT_MAPPING,
            "difference_impact_assessment.json": AssetType.METHOD_UNIT,
            "sota_findings.json": AssetType.EVIDENCE_REQUIREMENT,
            "consistency_delta_matrix.json": AssetType.CROSS_DOCUMENT_MAPPING,
            "gspr_evidence_mapping.json": AssetType.CHECKLIST_UNIT,
            "pmcf_adequacy_assessment.json": AssetType.METHOD_UNIT,
            "pmcf_need_statement.json": AssetType.METHOD_UNIT,
            "access_verification_findings.json": AssetType.EVIDENCE_REQUIREMENT,
            "risk_coverage_matrix.json": AssetType.CHECKLIST_UNIT,
        }

        for filename, asset_type in lane_files.items():
            file_path = lanes_dir / filename
            if file_path.exists():
                candidates.extend(
                    self._extract_lane_file(file_path, asset_type)
                )

        return candidates

    def _extract_lane_file(
        self, path: Path, asset_type: AssetType
    ) -> list[KnowledgeCandidate]:
        """Extract from a single lane findings file."""
        candidates = []
        data = _load_json(path)

        if asset_type == AssetType.CROSS_DOCUMENT_MAPPING:
            # Extract cross-document mappings
            matrix = data.get("claim_consistency_matrix") or data.get("consistency_delta_matrix") or []
            for item in matrix:
                candidates.append(
                    KnowledgeCandidate(
                        asset_type=asset_type,
                        source_artifact=str(path),
                        source_chain=[self.project_id, str(path)],
                        payload={
                            "mapping_type": "cer_document_consistency",
                            "source_pair": item.get("source_pair", ""),
                            "delta_type": item.get("delta_type", ""),
                            "impact_level": item.get("impact_level", ""),
                            "status": item.get("consistency_status", item.get("status", "")),
                        },
                        confidence=0.8,
                        project_id=self.project_id,
                        state=CandidateState.NORMALIZED,
                    )
                )

        elif asset_type == AssetType.METHOD_UNIT:
            # Extract equivalence dimensions or PMCF methods
            if "differences" in data:
                for diff in data.get("differences", []):
                    candidates.append(
                        KnowledgeCandidate(
                            asset_type=asset_type,
                            source_artifact=str(path),
                            source_chain=[self.project_id, str(path)],
                            payload={
                                "method_type": "equivalence_assessment",
                                "dimension": diff.get("dimension"),
                                "description": diff.get("description_cn"),
                                "residual_uncertainty": diff.get("residual_uncertainty_cn"),
                                "mandatory_human_review": diff.get("mandatory_human_review", False),
                            },
                            confidence=0.8,
                            project_id=self.project_id,
                            state=CandidateState.NORMALIZED,
                        )
                    )
            elif "pmcf_need_statement" in data or "pmcf_adequacy_assessment" in data:
                pmcf_data = data.get("pmcf_need_statement") or data.get("pmcf_adequacy_assessment") or []
                for item in pmcf_data:
                    candidates.append(
                        KnowledgeCandidate(
                            asset_type=asset_type,
                            source_artifact=str(path),
                            source_chain=[self.project_id, str(path)],
                            payload={
                                "method_type": "pmcf_evaluation",
                                "item": item,
                            },
                            confidence=0.8,
                            project_id=self.project_id,
                            state=CandidateState.NORMALIZED,
                        )
                    )

        elif asset_type == AssetType.EVIDENCE_REQUIREMENT:
            # Extract SOTA evidence requirements
            if "sota_findings" in data:
                for finding in data.get("sota_findings", []):
                    candidates.append(
                        KnowledgeCandidate(
                            asset_type=asset_type,
                            source_artifact=str(path),
                            source_chain=[self.project_id, str(path)],
                            payload={
                                "requirement_type": "sota_evidence",
                                "sota_item": finding.get("sota_item"),
                                "alternatives_covered": finding.get("current_alternatives_covered"),
                                "device_relevant": finding.get("device_relevant_benchmark"),
                            },
                            confidence=0.8,
                            project_id=self.project_id,
                            state=CandidateState.NORMALIZED,
                        )
                    )
            elif "access_verification_findings" in data:
                for finding in data.get("access_verification_findings", []):
                    candidates.append(
                        KnowledgeCandidate(
                            asset_type=asset_type,
                            source_artifact=str(path),
                            source_chain=[self.project_id, str(path)],
                            payload={
                                "requirement_type": "equivalence_access",
                                "equivalent_device": finding.get("equivalent_device_ref"),
                                "access_type": finding.get("access_basis_type"),
                                "sufficiency": finding.get("sufficiency_status"),
                            },
                            confidence=0.8,
                            project_id=self.project_id,
                            state=CandidateState.NORMALIZED,
                        )
                    )

        elif asset_type == AssetType.CHECKLIST_UNIT:
            # Extract GSPR or risk coverage checklist items
            if "gspr_evidence_mapping" in data:
                for item in data.get("gspr_evidence_mapping", []):
                    candidates.append(
                        KnowledgeCandidate(
                            asset_type=asset_type,
                            source_artifact=str(path),
                            source_chain=[self.project_id, str(path)],
                            payload={
                                "checklist_type": "gspr_evidence",
                                "gspr_item": item.get("gspr_item"),
                                "clinical_support": item.get("clinical_support_status"),
                            },
                            confidence=0.8,
                            project_id=self.project_id,
                            state=CandidateState.NORMALIZED,
                        )
                    )
            elif "risk_coverage_matrix" in data:
                for item in data.get("risk_coverage_matrix", []):
                    candidates.append(
                        KnowledgeCandidate(
                            asset_type=asset_type,
                            source_artifact=str(path),
                            source_chain=[self.project_id, str(path)],
                            payload={
                                "checklist_type": "risk_coverage",
                                "risk_ref": item.get("risk_ref"),
                                "coverage_status": item.get("coverage_status"),
                            },
                            confidence=0.8,
                            project_id=self.project_id,
                            state=CandidateState.NORMALIZED,
                        )
                    )

        return candidates

    def _extract_from_conclusion(self, conclusion_dir: Path) -> list[KnowledgeCandidate]:
        """Extract from conclusion artifacts."""
        candidates = []

        # Deficiency register
        deficiency = conclusion_dir / "deficiency_register.json"
        if deficiency.exists():
            data = _load_json(deficiency)
            for item in data.get("deficiencies", []):
                candidates.append(
                    KnowledgeCandidate(
                        asset_type=AssetType.FAILURE_PATTERN,
                        source_artifact=str(deficiency),
                        source_chain=[self.project_id, str(deficiency)],
                        payload={
                            "pattern_type": "deficiency",
                            "deficiency_id": item.get("deficiency_id"),
                            "description": item.get("description"),
                            "severity": item.get("severity"),
                            "status": item.get("status"),
                        },
                        confidence=0.9,
                        project_id=self.project_id,
                        state=CandidateState.NORMALIZED,
                    )
                )

        return candidates

    # --- Governance extraction methods ---

    def _extract_from_decision_ledger(self, path: Path) -> list[KnowledgeCandidate]:
        """Extract from decision_ledger_entry.json."""
        candidates = []
        data = _load_json(path)

        candidates.append(
            KnowledgeCandidate(
                asset_type=AssetType.CASE_LESSON,
                source_artifact=str(path),
                source_chain=[self.project_id, str(path)],
                payload={
                    "lesson_type": "gate_decision",
                    "entry_type": data.get("entry_type"),
                    "gate": data.get("gate"),
                    "decision": data.get("decision_data", {}).get("decision"),
                    "actor": data.get("actor"),
                    "run_id": data.get("run_id"),
                    "round_id": data.get("round_id"),
                },
                confidence=0.95,
                project_id=self.project_id,
                state=CandidateState.NORMALIZED,
            )
        )

        return candidates


def _load_json(path: Path) -> dict[str, Any]:
    """Load JSON file safely."""
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        return {"_error": str(e)}
