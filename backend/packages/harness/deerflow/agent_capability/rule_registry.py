"""Minimal RuleRegistry — loads Track C calibration and provides per-agent rule slices.

Reads TRACK_C_CALIBRATION_PACK_V5.json, classifies rules into 7 capability roles,
and formats them for prompt injection at DomainAgentSpec compile time.
"""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Track C type → registry capability role
_TYPE_TO_ROLE = {
    "AP": "ANTI_PATTERN_GUARDRAIL",
    "GS": "EVIDENCE_QUALITY_STANDARD",
    "SV": "SEVERITY_CALIBRATION_SIGNAL",
    "RP": "REPAIR_RECOMMENDATION_PATTERN",
    "RD": "REPAIR_RECOMMENDATION_PATTERN",
    "BD": "HUMAN_BOUNDARY_REFERENCE",
}

# Known calibration asset IDs that are not themselves directly detectable
# but provide context that an agent may reference
_NON_AUTOMATABLE_SUBTYPES: set[str] = {
    "calibration_coverage_escalation",
    "calibration_coverage_gap",
    "knowledge_fragment_type_too_generic",
    "knowledge_generalization_quality",
    "contextualization_quality",
    "extraction_convergence_inconsistency",
    "diminishing_calibration_yield_from_json_only_projects",
    "candidate_count_inflation_from_text_extraction_artifacts",
    "network_density_without_growth_target",
    "static_network_metric_without_temporal_context",
    "nocodb_dependency_for_convergence_validation",
    "rmf_distribution_imbalance",
    "evaluation_framework_convergence",
    "gate_boundary_architecture",
    "loop_exhaustion_misidentified_as_completion",
    "quality_stratification_without_remediation_priority",
    "process_go_hold_decision",
    "raw_array_candidate_packaging",
    "move_to_under_review",
    "deerflow_agent_to_gate_type",
    "all_pass_consistency_masks_quality_gaps",
}


class RuleRegistry:
    """Loads Track C calibration pack and provides per-agent rule queries.

    Rules are classified into 7 capability roles:
      - DIRECT_DETECTION_RULE
      - ANTI_PATTERN_GUARDRAIL
      - EVIDENCE_QUALITY_STANDARD
      - SEVERITY_CALIBRATION_SIGNAL
      - REPAIR_RECOMMENDATION_PATTERN
      - HUMAN_BOUNDARY_REFERENCE
      - NON_AUTOMATABLE_CONTEXT_ONLY
    """

    def __init__(self, calibration_pack_path: str | Path | None = None):
        self.rules: list[dict] = []
        self._by_id: dict[str, dict] = {}
        if calibration_pack_path is not None:
            self.load(Path(calibration_pack_path))

    # ── Loading ───────────────────────────────────────────

    def load(self, path: Path) -> None:
        """Load and classify rules from a Track C calibration pack JSON."""
        if not path.exists():
            raise FileNotFoundError(f"Calibration pack not found: {path}")

        pack = json.loads(path.read_text(encoding="utf-8"))
        candidates = pack.get("candidates", [])
        logger.info("Loading %d candidates from %s", len(candidates), path)

        for candidate in candidates:
            rule = self._convert(candidate)
            self.rules.append(rule)
            self._by_id[rule["rule_id"]] = rule

        logger.info("Loaded %d rules into registry", len(self.rules))

    def _convert(self, c: dict) -> dict:
        """Convert a Track C candidate into a registry rule."""
        tc_type = c.get("type", "AP")
        subtype = c.get("subtype", "")

        # Determine capability role
        if subtype in _NON_AUTOMATABLE_SUBTYPES:
            role = "NON_AUTOMATABLE_CONTEXT_ONLY"
        elif tc_type in _TYPE_TO_ROLE:
            role = _TYPE_TO_ROLE[tc_type]
        else:
            role = "DIRECT_DETECTION_RULE"

        return {
            "rule_id": c["id"],
            "capability_role": role,
            "track_c_type": tc_type,
            "subtype": subtype,
            "severity": c.get("severity", "MEDIUM"),
            "description": self._build_description(tc_type, subtype),
            "detection_guidance": self._build_detection(subtype, c.get("excerpt", "")),
            "action": self._build_action(c.get("severity", "MEDIUM")),
            "source_calibration_id": c["id"],
            "source_evidence": self._truncate(c.get("excerpt", ""), 250),
            "regulatory_context": c.get("regulatory_context", "MDR_EU"),
            "confidence": self._normalize_confidence(c.get("confidence", 0.85)),
            "quality_tier": c.get("quality_tier", "PASS"),
            "p0_quarantine": c.get("quality_tier") == "P0_QUARANTINE",
            "project_id": c.get("project_id", ""),
        }

    # ── Description builders ──────────────────────────────

    @staticmethod
    def _build_description(tc_type: str, subtype: str) -> str:
        readable = subtype.replace("_", " ")
        return f"[{tc_type}] {readable}"

    @staticmethod
    def _build_detection(subtype: str, excerpt: str) -> str:
        guidance_map: dict[str, str] = {
            "empty_file_accepted_as_source":
                "Check file sizes in inventory; any 0-byte file should be flagged.",
            "synthetic_summary_instead_of_excerpt":
                "Compare excerpt text against source file verbatim; flag non-matching text.",
            "copy_paste_template_artifact":
                "Check for identical or near-identical text blocks across different sections/projects.",
            "version_inconsistency":
                "Compare version fields across all documents; identify most recent NB-reviewed version.",
            "placeholder_content":
                "Check for template placeholder text (lorem ipsum, [[TODO]], <<INSERT>>).",
            "over_generalization":
                "Check for vague claims without specific quantitative data or named references.",
            "plan_without_execution":
                "Check if plans (PMCF, PMS) reference specific execution evidence or are purely descriptive.",
            "missing_cross_reference_verification_in_large_extraction":
                "Verify that every cross-reference resolves to a real document in the bundle.",
            "cross_document_consistency_gap":
                "Cross-check key claims across document pairs (CER vs IFU, CER vs SSCP, etc.).",
            "document_reference_correction":
                "Verify every referenced document exists in the project bundle.",
            "ifu_contraindication_not_in_cer":
                "Compare IFU contraindications with CER safety sections; flag mismatches.",
            "device_name_inconsistency":
                "Check device name spelling/variant across all documents for consistency.",
            "cer_approval_claim_contradicted_by_open_nb_deficiencies":
                "Cross-check any approval language with NB review status; flag contradictions.",
            "evidence_gap_pattern":
                "Check whether each finding's claim is backed by a source_file and excerpt.",
            "source_excerpt_fidelity":
                "Compare excerpt text against original source file; must be verbatim.",
            "missing_document_retrieval":
                "Check if referenced documents exist in the project bundle.",
            "benefit_risk_argument_pattern":
                "Verify benefit-risk conclusion is backed by quantitative data in the dossier.",
            "pmcf_execution_gap":
                "Check if PMCF plan references specific study design versus generic template.",
            "equivalence_evidence_insufficiency":
                "Verify equivalence claim is backed by specific comparative data.",
            "ifu_rmf_cer_consistency_pattern":
                "Cross-check risk controls across IFU, RMF, and CER for consistency.",
            "clinical_claim_pattern":
                "Verify clinical performance claims are backed by specific evidence sections.",
            "all_pass_consistency_masks_quality_gaps":
                "If zero inconsistencies found across high-risk document pairs, flag as suspicious.",
            "cross_document_consistency_failure":
                "Flag contradictions between document pairs with specific citations.",
        }
        if subtype in guidance_map:
            return guidance_map[subtype]
        # Fallback: use excerpt as guidance hint
        short = excerpt[:150].replace("\n", " ")
        return f"Review for pattern: {subtype.replace('_', ' ')}. Excerpt: {short}"

    @staticmethod
    def _build_action(severity: str) -> str:
        if severity == "CRITICAL":
            return "HOLD_FOR_HUMAN_REVIEW: flag as CRITICAL; block automated progression."
        elif severity == "HIGH":
            return "Flag as HIGH severity; include repair recommendation if available."
        else:
            return f"Flag as {severity} severity; include in findings with rationale."

    @staticmethod
    def _truncate(text: str, max_len: int) -> str:
        return text if len(text) <= max_len else text[:max_len - 3] + "..."

    @staticmethod
    def _normalize_confidence(value) -> float:
        if isinstance(value, (int, float)):
            return float(value)
        conf_map = {"HIGH": 0.90, "MEDIUM": 0.75, "LOW": 0.50}
        return conf_map.get(str(value), 0.75)

    # ── Queries ───────────────────────────────────────────

    def get_agent_rule_slice(self, rule_ids: list[str]) -> str:
        """Format specified rules as markdown for prompt injection.

        Returns empty string if no matching rules found.
        Only includes rules that are NOT NON_AUTOMATABLE_CONTEXT_ONLY.
        """
        matching = []
        for rid in rule_ids:
            rule = self._by_id.get(rid)
            if rule is None:
                # Try partial-match: rid may be a Track C candidate ID prefix
                for full_id, r in self._by_id.items():
                    if full_id.startswith(rid) or rid in full_id:
                        rule = r
                        break
            if rule is not None and rule["capability_role"] != "NON_AUTOMATABLE_CONTEXT_ONLY":
                matching.append(rule)

        if not matching:
            return ""

        lines = []
        for r in matching:
            lines.append(f"### {r['rule_id']}: {r['description']}")
            lines.append(
                f"- Role: `{r['capability_role']}` | "
                f"Severity: `{r['severity']}` | "
                f"Confidence: {r['confidence']:.2f}"
            )
            lines.append(f"- Detection: {r['detection_guidance']}")
            lines.append(f"- Action: {r['action']}")
            lines.append(f"- Source: [{r['source_calibration_id']}] {r['source_evidence']}")
            lines.append("")
        return "\n".join(lines)

    def get_rules_by_role(self, role: str) -> list[dict]:
        """Return all rules of a given capability role."""
        return [r for r in self.rules if r["capability_role"] == role]

    def rule_count(self) -> int:
        return len(self.rules)

    def role_distribution(self) -> dict[str, int]:
        dist: dict[str, int] = {}
        for r in self.rules:
            role = r["capability_role"]
            dist[role] = dist.get(role, 0) + 1
        return dist
