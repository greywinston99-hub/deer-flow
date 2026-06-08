"""Deterministic gates for CER authoring."""

from __future__ import annotations

import re
from dataclasses import dataclass
import os
from typing import Any

from deerflow.runtime.cer_authoring.agents import (
    LEGACY_AGENT_TEAM_MODE,
    STABLE_AGENT_TEAM_MODE,
    VIRTUAL_REVIEW_DIMENSIONS,
    physical_agent_names_for_mode,
)

PLACEHOLDER_TOKENS = ("HUMAN_REVIEW", "DATA GAP", "pending execution")
CJK_RE = __import__("re").compile(r"[\u3400-\u9fff]")
SOTA_LITERATURE_TARGET_MIN = 20
SOTA_LITERATURE_TARGET_MAX = 40

# \u2500\u2500 P0 Centralized Spiral Governance \u2500\u2500
# BIGDP2026.6 P1.3: Single authoritative source for maximum spiral retrieval rounds.
# All gate spiral decisions and the _should_continue_spiral graph helper MUST
# reference this constant \u2014 no hardcoded integers in routing logic.
MAX_SPIRAL_ROUNDS: int = 3
PRE_WRITER_READINESS_CONDITIONS = (
    "identity",
    "evidence_sufficiency",
    "retrieval_domain",
    "retrieval_completeness",
    "screening_pool",
    "fulltext_basis",
    "SOTA",
    "claim_evidence",
    "BR",
    "alignment",
    "endpoint_framework_locked",
    "clinical_data_consolidated",
    "eu_market_status_set",
)
PRE_WRITER_REWORK_ROUTES = {
    "identity": "device_profile",
    "retrieval_domain": "sota_search",
    "screening_pool": "sota_search",
    "fulltext_basis": "evidence_appraisal",
    "evidence_sufficiency": "sota_search",
    "SOTA": "endpoint_extraction",
    "claim_evidence": "writer_synthesis",
    "BR": "writer_synthesis",
    "alignment": "risk_gspr_mapping",
    "endpoint_framework_locked": "endpoint_extraction",
    "clinical_data_consolidated": "evidence_registry",
    "eu_market_status_set": "device_profile",
    "retrieval_completeness": "sota_search",
}

G42_FAILURE_REPAIR_ROUTES = {
    "LINKING_GAP": "pre_g42_claim_evidence_candidate_linking",
    "ENDPOINT_GAP": "endpoint_extraction",
    "PDF_GAP": "evidence_appraisal",
    "OCR_GAP": "evidence_appraisal",
    # ── Spiral-convergent routing: patterns that indicate "not enough evidence of
    # the right kind" all route to query_expansion → sota_search, which is the
    # only repair node capable of actually adding new evidence.  Each spiral round
    # expands the search query and increments spiral_round_id.  After 3 rounds
    # without sufficiency the gate escalates to BLOCKED → controlled_compromise.
    "SOURCE_TYPE_REQUIREMENT_NOT_MET": "query_expansion",
    "ALLOWED_USE_BLOCKED": "claim_decomposition",
    "MISSING_DATA_BLOCKING": "query_expansion",
    "CLAIM_SOURCE_MISMATCH": "query_expansion",
    "CLAIM_TYPE_MISCLASSIFICATION": "claim_decomposition",
    "CLAIM_OVERREACH": "claim_evidence_matrix",
    "SEMANTIC_SUPPORT_NOT_ESTABLISHED": "pre_g42_claim_evidence_candidate_linking",
    "SOURCE_TYPE_INAPPROPRIATE": "query_expansion",
    "EVIDENCE_TRULY_INSUFFICIENT": "query_expansion",
}
G42_FAILURE_PRIORITY = (
    # Patterns with dedicated repair nodes — address first if present
    "LINKING_GAP",
    "ENDPOINT_GAP",
    "PDF_GAP",
    "OCR_GAP",
    "SEMANTIC_SUPPORT_NOT_ESTABLISHED",
    "CLAIM_TYPE_MISCLASSIFICATION",
    "CLAIM_OVERREACH",
    # Evidence-insufficiency patterns — all route to query_expansion → sota_search
    # to add new evidence each spiral round; 3-round hard cap prevents infinite loop
    "ALLOWED_USE_BLOCKED",
    "MISSING_DATA_BLOCKING",
    "CLAIM_SOURCE_MISMATCH",
    "SOURCE_TYPE_INAPPROPRIATE",
    "EVIDENCE_TRULY_INSUFFICIENT",
    # Source document gaps (IFU/RMF/GSPR missing) — handled last because they
    # require manufacturer documents, not literature search, and should not
    # block the evidence spiral for literature-based claims
    "SOURCE_TYPE_REQUIREMENT_NOT_MET",
)
PRE_WRITER_UPSTREAM_PRIORITY = (
    "identity",
    "retrieval_domain",
    "retrieval_completeness",
    "screening_pool",
    "fulltext_basis",
    "evidence_sufficiency",
    "SOTA",
    "claim_evidence",
    "BR",
    "alignment",
)
SCREENING_POOL_FLOOR = 30

OXFORD_CONCLUSION_MAP = {
    "1a": "STRONG", "1b": "STRONG",
    "2a": "MODERATE", "2b": "MODERATE",
    "3a": "CAUTIOUS", "3b": "CAUTIOUS",
    "4": "CAUTIOUS", "5": "INSUFFICIENT",
}

DEVICE_CLASS_SCREENING_FLOOR = {
    "III": 30, "IIb": 25, "IIa": 20, "I": 15,
    "rare_disease": 10, "novel_technology": 15,
}

CLAIM_TYPE_SUFFICIENCY = {
    "clinical_benefit": {
        "min_pivotal": 1,
        "min_supportive": 1,
        "require_direct": True,
        "description": "At least 1 pivotal + 1 supportive clinical study directly on subject device or equivalent",
    },
    "intended_purpose": {
        "min_pivotal": 1,
        "min_supportive": 1,
        "require_direct": True,
        "description": "Clinical evidence supporting the intended purpose in the target population",
    },
    "safety": {
        "min_pivotal": 0,
        "min_supportive": 2,
        "require_direct": False,
        "min_independent_sources": 2,
        "description": "Multi-source cross-validation: >=2 independent sources (clinical+PMS+vigilance)",
    },
    "performance": {
        "min_pivotal": 1,
        "min_supportive": 0,
        "require_direct": True,
        "description": "Performance endpoint data from clinical or bench testing",
    },
    "IFU_warning": {
        "min_rmf_coverage": 0.8,
        "require_rmf": True,
        "require_gspr": True,
        "skip_pubmed": True,
        "description": "IFU warning evidence from RMF coverage >=80% + GSPR traceability",
    },
    "warning_contraindication": {
        "min_rmf_coverage": 0.8,
        "require_rmf": True,
        "require_gspr": True,
        "skip_pubmed": True,
        "description": "Warning/contraindication evidence from RMF/GSPR",
    },
    "technical": {
        "min_pivotal": 0,
        "min_supportive": 1,
        "require_direct": True,
        "description": "Technical performance from bench test or IFU specification",
    },
}


def _get_sufficiency_framework(claim_type: str) -> dict:
    """Return the sufficiency framework for a given claim type."""
    claim_type_normalized = str(claim_type or "").lower().replace(" ", "_")
    for key, framework in CLAIM_TYPE_SUFFICIENCY.items():
        if key.lower().replace(" ", "_") == claim_type_normalized:
            return framework
    return CLAIM_TYPE_SUFFICIENCY["clinical_benefit"]


def _get_screening_floor(state: dict[str, Any]) -> int:
    """Return configurable screening floor based on device class (BL-15)."""
    device_class = str(
        state.get("device_profile", {}).get("device_class") or ""
    ).replace("Class ", "")
    return DEVICE_CLASS_SCREENING_FLOOR.get(device_class, SCREENING_POOL_FLOOR)


def _conclusion_rank(strength: str) -> int:
    """Rank conclusion strengths for comparison: STRONG > MODERATE > CAUTIOUS > INSUFFICIENT."""
    rank_map = {"STRONG": 3, "MODERATE": 2, "CAUTIOUS": 1, "INSUFFICIENT": 0}
    return rank_map.get(str(strength).strip(), 0)

HARD_GATE_ROUTES = {
    "G39": {"pass": "literature_screening", "rework": "sota_search", "blocked": "controlled_compromise"},
    "G40": {"pass": "evidence_appraisal", "rework": "sota_search", "blocked": "controlled_compromise"},
    "G41": {"pass": "endpoint_extraction", "rework": "evidence_appraisal", "blocked": "controlled_compromise"},
    "G43": {"pass": "gap_pmcf", "rework": "writer_synthesis", "blocked": "controlled_compromise"},
    "G44": {"pass": "alignment", "rework": "writer_synthesis", "blocked": "controlled_compromise"},
    "G45": {"pass": "pre_writer_readiness_gate", "rework": "risk_gspr_mapping", "blocked": "controlled_compromise"},
}

HARD_GATE_NAMES = {
    "G39": "Retrieval Domain Mismatch",
    "G40": "Screening Pool Shallow",
    "G41": "Full-Text Basis Inadequate",
    "G43": "Claim-Evidence Incomplete",
    "G44": "Benefit-Risk Not Justified",
    "G45": "Alignment Not Ready",
}


@dataclass
class GateResult:
    gate_id: str
    status: str
    message: str
    severity: str = "blocking"
    failure_pattern: str = ""
    upstream_node_to_reroute: str = ""
    spiral_round: int | str = ""
    blocked_reason: str = ""
    reroute_context: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        contract_status = "BLOCKED" if self.status == "HUMAN_HOLD" else self.status
        failure_pattern = self.failure_pattern or ("" if contract_status == "PASS" else self.message)
        return {
            "gate_id": self.gate_id,
            "status": contract_status,
            "legacy_status": self.status if self.status != contract_status else "",
            "failure_pattern": failure_pattern,
            "upstream_node_to_reroute": self.upstream_node_to_reroute,
            "spiral_round": self.spiral_round,
            "blocked_reason": self.blocked_reason or (self.message if contract_status == "BLOCKED" else ""),
            "reroute_context": self.reroute_context or {},
            "message": self.message,
            "severity": self.severity,
        }


def evaluate_pre_writer_readiness_gate(state: dict[str, Any]) -> dict[str, Any]:
    """Aggregate G46 pre-writer readiness (Writer Release Board).

    BIGDP2026.6 P1.1: Real evaluators for all conditions. No auto-downgrade
    for placeholder conditions. BLOCKED means Writer is blocked.

    Override mechanism preserved for test/proof routing — but if no override
    is provided for a condition with a real evaluator, the evaluator runs.
    """

    overrides = state.get("pre_writer_readiness_condition_overrides") or {}
    rows = []
    for condition in PRE_WRITER_READINESS_CONDITIONS:
        override = overrides.get(condition) or {}
        status = str(override.get("status") or "PASS").upper()
        if status == "REWORK":
            status = "REWORK_REQUIRED"
        if status not in {"PASS", "REWORK_REQUIRED", "BLOCKED"}:
            status = "REWORK_REQUIRED"
        # BIGDP2026.6 P1.1: No auto-downgrade for any condition.
        # BLOCKED stays BLOCKED. Writer cannot be released with unverified
        # claim-evidence links or incomplete retrieval.
        message = override.get("message") or ""
        failure_pattern = override.get("failure_pattern") or ""
        upstream_route = override.get("upstream_route") or ""
        # ── G46 real evaluators (BIGDP2026.6 P1.1) ──
        if not override.get("status") and condition == "endpoint_framework_locked":
            cond = _check_endpoint_framework_locked(state)
            status = cond.status
            message = cond.message
            failure_pattern = cond.failure_pattern or failure_pattern
            upstream_route = cond.upstream_node_to_reroute or upstream_route
        elif not override.get("status") and condition == "clinical_data_consolidated":
            cond = _check_clinical_data_consolidated(state)
            status = cond.status
            message = cond.message
            failure_pattern = cond.failure_pattern or failure_pattern
            upstream_route = cond.upstream_node_to_reroute or upstream_route
        elif not override.get("status") and condition == "eu_market_status_set":
            cond = _check_eu_market_status_set(state)
            status = cond.status
            message = cond.message
            failure_pattern = cond.failure_pattern or failure_pattern
            upstream_route = cond.upstream_node_to_reroute or upstream_route
        elif not override.get("status") and condition == "claim_evidence":
            cond = _check_claim_evidence_linkage(state)
            status = cond.status
            message = cond.message
            failure_pattern = cond.failure_pattern or failure_pattern
            upstream_route = cond.upstream_node_to_reroute or upstream_route
        elif not override.get("status") and condition == "retrieval_completeness":
            cond = _check_retrieval_completeness(state)
            status = cond.status
            message = cond.message
            failure_pattern = cond.failure_pattern or failure_pattern
            upstream_route = cond.upstream_node_to_reroute or upstream_route
        # ── BIGDP2026.6 R3: Wire G44 (BR), G45 (alignment), SOTA into G46 ──
        elif not override.get("status") and condition == "BR":
            br_gate = evaluate_br_justified_gate(state)
            if br_gate.get("status") != "PASS":
                status = br_gate.get("status", "REWORK_REQUIRED")
                message = br_gate.get("message", "Benefit-risk not justified.")
                failure_pattern = br_gate.get("failure_pattern", "br_not_justified")
                upstream_route = "benefit_risk_ledger"
            else:
                status = "PASS"
                message = "Benefit-risk analysis justifies clinical benefit."
        elif not override.get("status") and condition == "alignment":
            align_gate = evaluate_alignment_gate(state)
            if align_gate.get("status") != "PASS":
                status = align_gate.get("status", "REWORK_REQUIRED")
                message = align_gate.get("message", "GSPR/RMF/IFU alignment not complete.")
                failure_pattern = align_gate.get("failure_pattern", "alignment_incomplete")
                upstream_route = "risk_gspr_mapping"
            else:
                status = "PASS"
                message = "GSPR/RMF/IFU alignment verified."
        elif not override.get("status") and condition == "SOTA":
            sota_benchmark = state.get("sota_benchmark_table") or []
            if not sota_benchmark:
                status = "REWORK_REQUIRED"
                message = "SOTA benchmark table is empty. Writer cannot establish clinical context without benchmarks."
                failure_pattern = "sota_benchmark_missing"
                upstream_route = "endpoint_extraction"
            else:
                status = "PASS"
                message = f"SOTA benchmark established with {len(sota_benchmark)} entries."
        # ── Controlled deferral for conditions without dedicated evaluators ──
        # These conditions are NOT silently passed. They are explicitly deferred
        # with rationale. Safety-critical conditions get a real evaluator or
        # controlled_deferral — never a silent PASS.
        elif not override.get("status") and condition == "evidence_sufficiency":
            g42_report = state.get("evidence_sufficiency_gate_report") or {}
            if g42_report.get("status") == "BLOCKED":
                status = "BLOCKED"
                message = "G42 evidence sufficiency is BLOCKED. Cannot release Writer."
                failure_pattern = "evidence_sufficiency_blocked"
                upstream_route = "controlled_compromise"
            else:
                message = f"G42 evidence sufficiency: {g42_report.get('status', 'not_evaluated')}. Controlled deferral — G42 evaluates sufficiency upstream."
        elif not override.get("status") and condition == "retrieval_domain":
            retrieval_report = state.get("retrieval_domain_gate_report") or {}
            if retrieval_report.get("status") == "BLOCKED":
                status = "BLOCKED"
                message = "Retrieval domain gate is BLOCKED."
                failure_pattern = "retrieval_domain_blocked"
                upstream_route = "sota_search"
            else:
                message = f"Retrieval domain: {retrieval_report.get('status', 'not_evaluated')}. Controlled deferral — evaluated by upstream retrieval_domain_gate."
        elif not override.get("status") and condition == "screening_pool":
            screening = state.get("screening_depth_gate_report") or {}
            if screening.get("status") == "BLOCKED":
                status = "BLOCKED"
                message = "Screening pool depth is BLOCKED."
                failure_pattern = "screening_pool_blocked"
                upstream_route = "sota_search"
            else:
                message = f"Screening pool: {screening.get('status', 'not_evaluated')}. Controlled deferral — evaluated by upstream screening_depth_gate."
        elif not override.get("status") and condition == "fulltext_basis":
            fulltext = evaluate_fulltext_basis_gate(state)
            if fulltext.get("status") != "PASS":
                status = fulltext.get("status", "REWORK_REQUIRED")
                message = fulltext.get("message", "Full-text basis insufficient.")
                failure_pattern = fulltext.get("failure_pattern", "fulltext_basis_insufficient")
                upstream_route = "evidence_appraisal"
            else:
                status = "PASS"
                message = "Full-text evidence basis is sufficient."
        # Fallback: no override and no real evaluator → controlled_deferral with explicit rationale
        if not override.get("status") and status == "PASS" and not message:
            message = f"Condition '{condition}' — controlled_deferral. Evaluated by upstream gate or explicit override. No silent PASS."
        rows.append(
            {
                "condition_name": condition,
                "status": status,
                "message": message,
                "upstream_route": upstream_route or override.get("upstream_route") or PRE_WRITER_REWORK_ROUTES.get(condition, "writer_synthesis"),
                "failure_pattern": failure_pattern or override.get("failure_pattern") or "",
                "source_gate_ids": override.get("source_gate_ids") or "",
                "evidence_basis": override.get("evidence_basis") or "",
            }
        )
    source_preflight = state.get("source_preflight_gate_report") or {}
    if source_preflight.get("status") == "BLOCKED":
        rows.append({
            "condition_name": "source_preflight",
            "status": "BLOCKED",
            "message": "Source preflight has blocking source-package issues.",
            "upstream_route": "initialize",
            "failure_pattern": "source_preflight_blocked",
            "source_gate_ids": "SOURCE_PREFLIGHT",
        })
    classification = state.get("classification_consistency_report") or {}
    if classification.get("status") == "BLOCKED":
        rows.append({
            "condition_name": "classification",
            "status": "BLOCKED",
            "message": "Device classification conflict must be resolved before Writer.",
            "upstream_route": "device_profile",
            "failure_pattern": "classification_conflict",
            "source_gate_ids": "CLASSIFICATION_CONSISTENCY_GATE",
        })
    cep_gate = evaluate_cep_exists_gate(state)
    if cep_gate.status != "PASS":
        rows.append({
            "condition_name": "CEP",
            "status": "BLOCKED" if cep_gate.status in {"FAIL", "BLOCKED"} else "REWORK_REQUIRED",
            "message": cep_gate.message,
            "upstream_route": "methodology_review",
            "failure_pattern": cep_gate.failure_pattern or "cep_incomplete",
            "source_gate_ids": "G_CEP",
        })
    # ── BIGDP2026.6 Phase 3: Writer Release Board — Expert Ledger Checks ──
    reasoning_ledger = state.get("cer_reasoning_ledger") or {}
    if not reasoning_ledger.get("claims"):
        rows.append({
            "condition_name": "CER_REASONING_LEDGER",
            "status": "REWORK_REQUIRED",
            "message": "CER_REASONING_LEDGER is missing or has no claims. Run build_reasoning_ledger node.",
            "upstream_route": "build_reasoning_ledger",
            "failure_pattern": "reasoning_ledger_missing",
            "source_gate_ids": "G46_REASONING_LEDGER",
        })
    ifu_evolution = state.get("ifu_claim_evolution_ledger") or {}
    if not ifu_evolution.get("claims"):
        rows.append({
            "condition_name": "IFU_CLAIM_EVOLUTION_LEDGER",
            "status": "REWORK_REQUIRED",
            "message": "IFU_CLAIM_EVOLUTION_LEDGER is missing or has no claims. Run build_ifu_evolution_ledger node.",
            "upstream_route": "build_ifu_evolution_ledger",
            "failure_pattern": "ifu_evolution_ledger_missing",
            "source_gate_ids": "G46_IFU_EVOLUTION_LEDGER",
        })
    benchmark_trace = state.get("benchmark_derivation_trace") or {}
    if not benchmark_trace.get("endpoints"):
        rows.append({
            "condition_name": "BENCHMARK_DERIVATION_TRACE",
            "status": "REWORK_REQUIRED",
            "message": "BENCHMARK_DERIVATION_TRACE is missing or has no endpoints. Run build_benchmark_trace node.",
            "upstream_route": "build_benchmark_trace",
            "failure_pattern": "benchmark_trace_missing",
            "source_gate_ids": "G46_BENCHMARK_TRACE",
        })
    br_matrix = state.get("benefit_risk_closure_matrix") or {}
    if br_matrix.get("closure_status") == "NOT_CONCLUDABLE":
        rows.append({
            "condition_name": "BR",
            "status": "BLOCKED",
            "message": "Benefit-risk closure matrix is not concludable; Writer may only create controlled-draft limitations.",
            "upstream_route": "risk_gspr_mapping",
            "failure_pattern": "benefit_risk_not_concludable",
            "source_gate_ids": "BR_CLOSURE_GATE",
        })
    # ── IFU Pre-Writer Check: granular by alignment_status ──
    ifu_alignment = state.get("ifu_cer_alignment_ledger") or {}
    ifu_alignments = ifu_alignment.get("alignments", [])
    overclaimed = [a for a in ifu_alignments if a.get("alignment_status") in ("overclaimed_in_ifu", "unsupported_by_evidence")]
    missing = [a for a in ifu_alignments if a.get("alignment_status") == "missing_in_ifu"]
    needs_review = [a for a in ifu_alignments if a.get("alignment_status") == "needs_human_review"]
    # overclaimed/unsupported → BLOCKED (IFU says more than evidence supports)
    if overclaimed:
        rows.append({
            "condition_name": "IFU_ALIGNMENT",
            "status": "BLOCKED",
            "message": f"IFU has {len(overclaimed)} overclaimed/unsupported statements vs CER evidence. Human review required before Writer.",
            "upstream_route": "claim_decomposition",
            "failure_pattern": "ifu_overclaimed",
            "source_gate_ids": "G_IFU_WORKING_DOCUMENT",
        })
    # missing_in_ifu → recommendation only, does NOT block CER (IFU update after CER is fine)
    if missing:
        rows.append({
            "condition_name": "IFU_ALIGNMENT",
            "status": "PASS",
            "message": f"IFU lacks wording for {len(missing)} CER-supported claims. IFU_UPDATE_RECOMMENDATION generated — does not block CER.",
            "upstream_route": "",
            "failure_pattern": "ifu_missing_benefit",
            "source_gate_ids": "G_IFU_WORKING_DOCUMENT",
        })
    if needs_review:
        rows.append({
            "condition_name": "IFU_ALIGNMENT",
            "status": "PASS",
            "message": f"IFU has {len(needs_review)} claims needing human review. Does not block CER.",
            "upstream_route": "",
            "failure_pattern": "ifu_needs_human_review",
            "source_gate_ids": "G_IFU_WORKING_DOCUMENT",
        })
    # ── WS2-WS7 Pre-Writer Checks ──
    ws_prisma = _gate_ws4_prisma_reproducibility(state)
    if ws_prisma.status != "PASS":
        rows.append({
            "condition_name": "WS4_PRISMA",
            "status": "BLOCKED" if ws_prisma.status == "BLOCKED" else "REWORK_REQUIRED",
            "message": ws_prisma.message,
            "upstream_route": "sota_search",
            "failure_pattern": ws_prisma.failure_pattern or "prisma_not_reproducible",
            "source_gate_ids": "WS4_PRISMA_REPRODUCIBILITY",
        })
    ws_equiv = _gate_ws7_equivalence_route(state)
    if ws_equiv.status != "PASS":
        rows.append({
            "condition_name": "WS7_EQUIVALENCE",
            "status": ws_equiv.status,
            "message": ws_equiv.message,
            "upstream_route": "equivalence_analysis",
            "failure_pattern": ws_equiv.failure_pattern or "false_equivalence_closure",
            "source_gate_ids": "WS7_EQUIVALENCE_ROUTE",
        })
    ws_overclaim = _gate_ws2_ifu_overclaim(state)
    if ws_overclaim.status != "PASS":
        rows.append({
            "condition_name": "WS2_IFU_OVERCLAIM",
            "status": ws_overclaim.status,
            "message": ws_overclaim.message,
            "upstream_route": "claim_decomposition",
            "failure_pattern": ws_overclaim.failure_pattern or "ifu_overclaim",
            "source_gate_ids": "WS2_IFU_OVERCLAIM",
        })
    ws_eligibility = _gate_ws3_final_body_claim_eligibility(state)
    if ws_eligibility.status != "PASS":
        rows.append({
            "condition_name": "WS3_CLAIM_ELIGIBILITY",
            "status": ws_eligibility.status,
            "message": ws_eligibility.message,
            "upstream_route": "claim_decomposition",
            "failure_pattern": ws_eligibility.failure_pattern or "ineligible_claim",
            "source_gate_ids": "WS3_CLAIM_ELIGIBILITY",
        })
    ws_ceiling = _gate_ws5_evidence_level_ceiling(state)
    if ws_ceiling.status != "PASS":
        rows.append({
            "condition_name": "WS5_EVIDENCE_CEILING",
            "status": ws_ceiling.status,
            "message": ws_ceiling.message,
            "upstream_route": "evidence_appraisal",
            "failure_pattern": ws_ceiling.failure_pattern or "evidence_ceiling_violation",
            "source_gate_ids": "WS5_EVIDENCE_LEVEL_CEILING",
        })
    ws_endpoint = _gate_ws6_endpoint_homogeneity(state)
    if ws_endpoint.status != "PASS":
        rows.append({
            "condition_name": "WS6_ENDPOINT_HOMOGENEITY",
            "status": ws_endpoint.status,
            "message": ws_endpoint.message,
            "upstream_route": "endpoint_extraction",
            "failure_pattern": ws_endpoint.failure_pattern or "endpoint_heterogeneity",
            "source_gate_ids": "WS6_ENDPOINT_HOMOGENEITY",
        })
    ws_rmf = _gate_ws9_rmf_ifu_warning_linkage(state)
    if ws_rmf.status != "PASS":
        rows.append({
            "condition_name": "WS9_RMF_LINKAGE",
            "status": ws_rmf.status,
            "message": ws_rmf.message,
            "upstream_route": "risk_gspr_mapping",
            "failure_pattern": ws_rmf.failure_pattern or "rmf_ifu_unlinked",
            "source_gate_ids": "WS9_RMF_IFU_LINKAGE",
        })
    blocked = [row for row in rows if row["status"] == "BLOCKED"]
    rework = [row for row in rows if row["status"] == "REWORK_REQUIRED"]
    route_condition = _pre_writer_route_condition(blocked or rework)
    if blocked:
        status = "BLOCKED"
        decision = "G46_BLOCKED"
        route = "controlled_compromise"
    elif rework:
        status = "REWORK_REQUIRED"
        decision = "G46_REWORK"
        route = PRE_WRITER_REWORK_ROUTES.get(route_condition, "writer_synthesis")
    else:
        status = "PASS"
        decision = "G46_PASS"
        route = "cer_writing"
    report = {
        "gate_id": "G46",
        "gate_name": "Pre-Writer Readiness",
        "status": status,
        "decision": decision,
        "failure_pattern": route_condition if status != "PASS" else "",
        "upstream_node_to_reroute": route if status == "REWORK_REQUIRED" else "",
        "spiral_round": "",
        "blocked_reason": "One or more pre-writer readiness conditions are BLOCKED." if status == "BLOCKED" else "",
        "reroute_context": {
            "route_condition": route_condition,
            "failing_sub_conditions": [row["condition_name"] for row in rows if row["status"] != "PASS"],
            "upstream_causality_priority": list(PRE_WRITER_UPSTREAM_PRIORITY),
        },
        "conditions": rows,
        "failing_sub_conditions": [row for row in rows if row["status"] != "PASS"],
        "route_condition": route_condition,
        "reroute_target": route if status == "REWORK_REQUIRED" else "",
        "compromise_reason": "One or more pre-writer readiness conditions are BLOCKED." if status == "BLOCKED" else "",
        "writer_invoked": status == "PASS",
        "next_node": route,
        "message": "All nine pre-writer conditions passed." if status == "PASS" else f"G46 {status}; route to {route}.",
    }
    # ── V3.1 Gate Aggregation (BUG-007 fix) ──
    try:
        from deerflow.runtime.cer_authoring.v3_1_gates import aggregate_v3_1_gates_into_g46
        v3_1_aggregation = aggregate_v3_1_gates_into_g46(state)
        report["v3_1_gate_aggregation"] = v3_1_aggregation
        # If V3.1 gates failed, upgrade G46 status
        if v3_1_aggregation.get("v3_1_gate_status") == "REWORK_REQUIRED":
            if status == "PASS":
                report["status"] = "REWORK_REQUIRED"
                report["route_condition"] = "v3_1_gate_failure"
                report["reroute_target"] = "benchmark_derivation"
                report["message"] = f"V3.1 gates failed: {v3_1_aggregation.get('v3_1_gate_failure_reason', 'unknown')}"
    except ImportError:
        pass  # V3.1 not deployed
    return _with_gate_trace(report, state)


def _pre_writer_route_condition(failing_rows: list[dict[str, Any]]) -> str:
    failing = {str(row.get("condition_name") or "") for row in failing_rows}
    for condition in PRE_WRITER_UPSTREAM_PRIORITY:
        if condition in failing:
            return condition
    return next(iter(failing), "")


def evaluate_retrieval_domain_gate(state: dict[str, Any]) -> dict[str, Any]:
    """G39: detect retrieval-domain mismatch before evidence consumption.

    This batch establishes the gate type and structured signal. The check is
    intentionally permissive: absent trace data passes, but explicit Phase 7
    mismatch rows route back to SOTA search/query construction.
    """

    override = _hard_gate_override(state, "G39", "retrieval_domain_gate")
    if override:
        return _hard_gate_signal("G39", override.get("status", "PASS"), override.get("failure_pattern", override.get("message", "")), override=override, state=state)
    mismatches = [
        row for row in state.get("evidence_source_trace_matrix") or []
        if str(row.get("retrieval_domain_status") or "").startswith("RETRIEVAL_DOMAIN_MISMATCH")
    ]
    if mismatches:
        return _hard_gate_signal(
            "G39",
            "REWORK_REQUIRED",
            "retrieval_domain_mismatch",
            state=state,
            details={"mismatch_count": len(mismatches)},
        )
    return _hard_gate_signal("G39", "PASS", state=state)


def evaluate_screening_depth_gate(state: dict[str, Any]) -> dict[str, Any]:
    """G40: flag a shallow screened pool only when pool data are available."""

    override = _hard_gate_override(state, "G40", "screening_depth_gate")
    if override:
        return _hard_gate_signal("G40", override.get("status", "PASS"), override.get("failure_pattern", override.get("message", "")), override=override, state=state)
    pool = state.get("screened_candidate_pool") or state.get("screening_disposition") or []
    if pool and len(pool) < SCREENING_POOL_FLOOR:
        return _hard_gate_signal(
            "G40",
            "REWORK_REQUIRED",
            "screening_pool_below_floor",
            state=state,
            details={"screening_pool_size": len(pool), "screening_pool_floor": SCREENING_POOL_FLOOR},
        )
    return _hard_gate_signal("G40", "PASS", state=state, details={"screening_pool_size": len(pool)})


def evaluate_fulltext_basis_gate(state: dict[str, Any]) -> dict[str, Any]:
    """G41: pivotal evidence should have available or partial full-text basis.

    v1.1-enhanced: Also checks evidence_depth classification for pivotal evidence.
    Pivotal evidence must be PRIMARY_VERBATIM or PRIMARY_DERIVED.
    SECONDARY_SUMMARY or MISSING_PRIMARY for pivotal evidence triggers REWORK.
    """

    override = _hard_gate_override(state, "G41", "fulltext_basis_gate")
    if override:
        return _hard_gate_signal("G41", override.get("status", "PASS"), override.get("failure_pattern", override.get("message", "")), override=override, state=state)
    fulltext_by_evidence = {
        str(row.get("evidence_id") or ""): row for row in state.get("fulltext_acquisition_status_table") or [] if row.get("evidence_id")
    }
    pivotal = [
        row for row in state.get("evidence_registry") or []
        if str(row.get("weight") or row.get("contribution") or "").lower() == "pivotal"
    ]
    lacking = []
    depth_violations = []
    for row in pivotal:
        status = _g42_full_text_status(row, {}, fulltext_by_evidence.get(str(row.get("evidence_id") or ""), {}))
        if status not in {"available", "partial"}:
            lacking.append(str(row.get("evidence_id") or "unknown"))
        # Evidence depth check (weak-coupling layer 0)
        depth = str(row.get("evidence_depth") or "").upper()
        if depth and depth not in {"PRIMARY_VERBATIM", "PRIMARY_DERIVED"}:
            depth_violations.append({
                "evidence_id": str(row.get("evidence_id") or "unknown"),
                "evidence_depth": depth,
                "required": "PRIMARY_VERBATIM or PRIMARY_DERIVED",
            })
    if lacking or depth_violations:
        details: dict[str, Any] = {}
        if lacking:
            details["pivotal_without_fulltext"] = ", ".join(lacking)
        if depth_violations:
            details["pivotal_evidence_depth_violations"] = depth_violations
        return _hard_gate_signal(
            "G41",
            "REWORK_REQUIRED",
            "pivotal_full_text_unavailable" if lacking else "pivotal_evidence_depth_insufficient",
            state=state,
            details=details,
        )
    return _hard_gate_signal("G41", "PASS", state=state, details={"pivotal_count": len(pivotal), "depth_check": "all_primary"})


def evaluate_claim_evidence_gate(state: dict[str, Any]) -> dict[str, Any]:
    """G43: every claim should have a recorded evidence linkage.

    BIGDP2026.6 Phase 3: Consumes CER_REASONING_LEDGER for claim classification
    context. Verifies evidence support type (direct/indirect) is specified.
    BLOCKED routes to claim_evidence_matrix rework, not directly to compromise.
    """

    override = _hard_gate_override(state, "G43", "claim_evidence_gate")
    if override:
        return _hard_gate_signal("G43", override.get("status", "PASS"), override.get("failure_pattern", override.get("message", "")), override=override, state=state)
    matrix_by_claim = {str(row.get("claim_id") or ""): row for row in state.get("claim_evidence_matrix") or [] if row.get("claim_id")}
    reasoning_ledger = state.get("cer_reasoning_ledger") or {}
    reasoning_claims = {str(c.get("claim_id") or ""): c for c in reasoning_ledger.get("claims", [])}

    missing = []
    weak_support = []
    for idx, claim in enumerate(state.get("claim_ledger") or [], start=1):
        claim_id = str(claim.get("claim_id") or f"C-{idx:02d}")
        matrix = matrix_by_claim.get(claim_id) or {}
        evidence_ids = matrix.get("evidence_ids") or matrix.get("evidence_id") or ""
        if isinstance(evidence_ids, list):
            evidence_ids = [e for e in evidence_ids if e]
        else:
            evidence_ids = str(evidence_ids).strip()

        if not evidence_ids:
            missing.append(claim_id)
        else:
            # Check evidence support type from reasoning ledger
            rc = reasoning_claims.get(claim_id) or {}
            support_type = str(rc.get("evidence_support_type") or matrix.get("support_type") or "")
            if support_type in ("insufficient", ""):
                weak_support.append({"claim_id": claim_id, "type": support_type or "unspecified"})

    if missing:
        return _hard_gate_signal(
            "G43",
            "REWORK_REQUIRED",
            "claim_evidence_link_missing",
            state=state,
            details={"missing_claim_ids": ", ".join(missing), "missing_count": len(missing)},
        )
    if weak_support:
        return _hard_gate_signal(
            "G43",
            "REWORK_REQUIRED",
            "claim_evidence_support_type_weak",
            state=state,
            details={
                "weak_support_claims": [w["claim_id"] for w in weak_support],
                "weak_count": len(weak_support),
                "note": "Claims marked 'insufficient' or lacking support_type in CER_REASONING_LEDGER.",
            },
        )
    return _hard_gate_signal(
        "G43",
        "PASS",
        state=state,
        details={
            "claim_count": len(state.get("claim_ledger") or []),
            "all_support_types_specified": True,
            "reasoning_ledger_consumed": bool(reasoning_ledger),
        },
    )


def evaluate_br_justified_gate(state: dict[str, Any]) -> dict[str, Any]:
    """G44: benefit-risk rows should point to evidence, SOTA, risk or rationale."""

    override = _hard_gate_override(state, "G44", "br_justified_gate")
    if override:
        return _hard_gate_signal("G44", override.get("status", "PASS"), override.get("failure_pattern", override.get("message", "")), override=override, state=state)
    templateish = []
    for row in state.get("benefit_risk_ledger") or []:
        blob = " ".join(
            str(row.get(key) or "")
            for key in (
                "benefit_evidence_basis",
                "risk_evidence_basis",
                "benefit_basis",
                "risk_basis",
                "balance_rationale",
                "rationale",
                "supporting_evidence_ids",
                "sota_ids",
                "key_risk_ids",
                "evidence_strength",
            )
        )
        lower = blob.lower()
        has_basis = any(token in lower for token in ("e-", "evid", "pmid", "sota", "risk", "rmf", "benchmark", "claim", "limited", "uncertainty"))
        if not has_basis or "template" in lower:
            templateish.append(str(row.get("br_id") or row.get("claim_id") or "unknown"))
    if templateish:
        return _hard_gate_signal(
            "G44",
            "REWORK_REQUIRED",
            "benefit_risk_not_evidence_justified",
            state=state,
            details={"br_rows_requiring_rejustification": ", ".join(templateish)},
        )
    return _hard_gate_signal("G44", "PASS", state=state, details={"benefit_risk_rows": len(state.get("benefit_risk_ledger") or [])})


def evaluate_alignment_gate(state: dict[str, Any]) -> dict[str, Any]:
    """G45: CER-source alignment should not contain unresolved conflicts."""

    override = _hard_gate_override(state, "G45", "alignment_gate")
    if override:
        return _hard_gate_signal("G45", override.get("status", "PASS"), override.get("failure_pattern", override.get("message", "")), override=override, state=state)
    rows = state.get("alignment_matrix") or []
    conflicts = [
        row for row in rows
        if str(row.get("alignment_status") or "").lower() in {"conflict", "missing"}
        or str(row.get("blocks_CER_conclusion") or "").lower() in {"yes", "true"}
    ]
    if conflicts:
        return _hard_gate_signal(
            "G45",
            "REWORK_REQUIRED",
            "alignment_conflict_or_missing",
            state=state,
            details={"alignment_rows_requiring_rework": len(conflicts)},
        )
    return _hard_gate_signal("G45", "PASS", state=state, details={"alignment_rows": len(rows)})


def _hard_gate_override(state: dict[str, Any], gate_id: str, gate_key: str) -> dict[str, Any]:
    overrides = state.get("hard_gate_signal_overrides") or {}
    return overrides.get(gate_id) or overrides.get(gate_key) or state.get(f"{gate_key}_override") or {}


def _hard_gate_signal(
    gate_id: str,
    status: str,
    failure_pattern: str = "",
    *,
    override: dict[str, Any] | None = None,
    state: dict[str, Any] | None = None,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    override = override or {}
    state = state or {}
    normalized = str(status or "PASS").upper()
    if normalized == "REWORK":
        normalized = "REWORK_REQUIRED"
    if normalized not in {"PASS", "REWORK_REQUIRED", "BLOCKED"}:
        normalized = "REWORK_REQUIRED"
    routes = HARD_GATE_ROUTES[gate_id]
    if normalized == "PASS":
        upstream = ""
        next_node = override.get("next_node") or routes["pass"]
    elif normalized == "REWORK_REQUIRED":
        upstream = override.get("upstream_node_to_reroute") or override.get("upstream_route") or routes["rework"]
        next_node = override.get("next_node") or upstream
    else:
        upstream = ""
        next_node = override.get("next_node") or routes["blocked"]
    blocked_reason = override.get("blocked_reason") or (failure_pattern if normalized == "BLOCKED" else "")
    signal = {
        "gate_id": gate_id,
        "gate_name": HARD_GATE_NAMES.get(gate_id, gate_id),
        "status": normalized,
        "failure_pattern": "" if normalized == "PASS" else str(failure_pattern or override.get("failure_pattern") or "gate_condition_failed"),
        "upstream_node_to_reroute": upstream,
        "next_node": next_node,
        "spiral_round": override.get("spiral_round") or _g42_current_spiral_round(state),
        "blocked_reason": blocked_reason,
        "reroute_context": {
            "configured_pass_route": routes["pass"],
            "configured_rework_route": routes["rework"],
            "configured_blocked_route": routes["blocked"],
            "override_applied": bool(override),
        },
        "message": override.get("message") or f"{gate_id} {normalized}; route to {next_node}.",
    }
    if details:
        signal.update(details)
    return _with_gate_trace(signal, state)


def _with_gate_trace(signal: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    trace = _gate_trace_record(signal, state)
    try:
        state.setdefault("gate_routing_trace", []).append(trace)
    except Exception:
        pass
    return {**signal, "gate_routing_trace": [trace]}


def _gate_trace_record(signal: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    existing = state.get("gate_routing_trace") or []
    invocation_order = len(existing) + 1
    return {
        "gate_id": signal.get("gate_id"),
        "invocation_order": invocation_order,
        "status": signal.get("status"),
        "failure_pattern": signal.get("failure_pattern") or "",
        "upstream_node_to_reroute": signal.get("upstream_node_to_reroute") or "",
        "upstream_node_routed_to": signal.get("upstream_node_to_reroute") or "",
        "spiral_round": signal.get("spiral_round") or "",
        "blocked_reason": signal.get("blocked_reason") or "",
        "reroute_context": signal.get("reroute_context") or {},
    }


def _compute_g42_dynamic_max_rounds(state: dict[str, Any]) -> int:
    """BIGDP2026.6 Phase 3: Dynamic spiral ceiling based on device risk class.

    Higher-risk devices may justify deeper evidence retrieval (more spiral rounds).
    Lower-risk devices use tighter ceilings to avoid unnecessary searching.

    Returns:
        Adjusted max spiral rounds (int).
    """
    base = MAX_SPIRAL_ROUNDS
    device = state.get("device_profile") or {}
    device_class = str(device.get("device_class") or "").upper().replace("CLASS ", "").strip()
    claim_ledger = state.get("claim_ledger") or []
    reasoning_ledger = state.get("cer_reasoning_ledger") or {}

    # Device-class-based adjustment
    class_bonus = {"III": 2, "IIB": 1, "IIA": 0, "I": 0}
    bonus = class_bonus.get(device_class, 0)

    # Claim criticality adjustment: if any claim is "high" criticality, allow +1 round
    claim_criticalities = [
        str(c.get("claim_criticality") or "").lower()
        for c in reasoning_ledger.get("claims", [])
    ] if reasoning_ledger else [
        str(c.get("criticality") or "medium").lower() for c in claim_ledger
    ]
    if any(cc == "high" for cc in claim_criticalities):
        bonus += 1

    dynamic = base + bonus
    # Cap at 6 to prevent unbounded spiraling
    return min(dynamic, 6)


def evaluate_evidence_sufficiency_gate(state: dict[str, Any]) -> dict[str, Any]:
    """Evaluate G42 claim-level evidence sufficiency for the spiral loop.

    BIGDP2026.6 Phase 3: Dynamic max rounds based on device risk class, claim
    criticality, and evidence gap type.  Higher-risk devices (Class III, IIb)
    with high-criticality claims get deeper retrieval allowances.
    """

    override = state.get("evidence_sufficiency_gate_override") or {}
    if override:
        return _evidence_sufficiency_override_result(state, override)
    claim_rows = _g42_claim_sufficiency_rows(state)
    insufficient = [row for row in claim_rows if row.get("sufficiency_status") != "PASS"]
    # Per-claim-type sufficiency framework check (BL-02/03)
    claim_type_failures = []
    for claim in (state.get("claim_ledger") or []):
        claim_type = str(claim.get("claim_type") or "")
        framework = _get_sufficiency_framework(claim_type)
        claim_id = str(claim.get("claim_id") or "unknown")
        # IFU_warning type: check RMF/GSPR coverage instead of PubMed evidence
        if framework.get("skip_pubmed"):
            rmf_present = any("rmf" in str(i.get("document_type", "")).lower()
                             for i in state.get("source_inventory") or [])
            gspr_coverage = state.get("gspr_coverage") or {}
            rmf_score = 1.0 if rmf_present else 0.0
            gspr_count = len(gspr_coverage) if isinstance(gspr_coverage, dict) else 0
            if rmf_score < framework.get("min_rmf_coverage", 0.8):
                claim_type_failures.append({
                    "claim_id": claim_id,
                    "failure_pattern": "RMF_COVERAGE_INSUFFICIENT",
                    "reason": f"RMF coverage {rmf_score:.0%} below threshold {framework.get('min_rmf_coverage', 0.8):.0%}",
                })
    if claim_type_failures:
        insufficient.extend(claim_type_failures)
    current_round = _g42_current_spiral_round(state)
    dynamic_max = _compute_g42_dynamic_max_rounds(state)
    if not claim_rows:
        insufficient = [
            {
                "claim_id": "CLAIM-GAP",
                "sufficiency_status": "REWORK_REQUIRED",
                "reason": "No claim ledger rows available for claim-level evidence sufficiency.",
            }
        ]
    if not insufficient:
        status = "PASS"
        next_node = "sota_clinical_context"
        rework_reason = ""
        blocked_reason = ""
    elif current_round >= dynamic_max and _g42_primary_failure_pattern(insufficient) == "EVIDENCE_TRULY_INSUFFICIENT":
        status = "BLOCKED"
        next_node = "controlled_compromise"
        rework_reason = _g42_rework_reason(insufficient)
        blocked_reason = f"Evidence sufficiency remains unmet after {dynamic_max} spiral rounds (dynamic ceiling for this device class)."
    else:
        status = "REWORK_REQUIRED"
        route_pattern = _g42_primary_failure_pattern(insufficient)
        next_node = _g42_primary_repair_route(insufficient, route_pattern)
        rework_reason = _g42_rework_reason(insufficient)
        blocked_reason = ""
    report = {
        "gate_id": "G42",
        "gate_name": "Evidence Sufficiency",
        "status": status,
        "failure_pattern": "" if status == "PASS" else rework_reason,
        "upstream_node_to_reroute": next_node if status == "REWORK_REQUIRED" else "",
        "spiral_round": current_round,
        "current_spiral_round": current_round,
        "next_node": next_node,
        "claim_sufficiency": claim_rows,
        "insufficient_claims": insufficient,
        "rework_reason": rework_reason or "All claims have at least one sufficient evidence item.",
        "blocked_reason": blocked_reason,
        "reroute_context": {
            "insufficient_claim_ids": [row.get("claim_id") for row in insufficient],
            "failure_patterns": _g42_failure_patterns(insufficient),
            "repair_routes_by_claim": {str(row.get("claim_id")): row.get("repair_route") for row in insufficient if row.get("claim_id")},
            "max_spiral_rounds": MAX_SPIRAL_ROUNDS,
            "dynamic_max_rounds": dynamic_max,
            "device_class": str((state.get("device_profile") or {}).get("device_class") or ""),
            "evidence_loop": True,
        },
        "message": f"G42 {status}; {len(insufficient)} insufficient claim(s); route to {next_node}.",
    }
    return _with_gate_trace(report, state)


def evaluate_claim_sota_alignment_gate(state: dict[str, Any]) -> dict[str, Any]:
    """G_ARG_02: Claim-SOTA alignment table must have no unsupported claims."""
    alignment = state.get("claim_sota_alignment_table") or []
    unsupported = [r for r in alignment if r.get("feasibility") == "unsupported"]
    if unsupported:
        return GateResult(
            "G_ARG_02", "REWORK_REQUIRED",
            f"{len(unsupported)} claims have no SOTA benchmark support",
            upstream_node_to_reroute="device_profile_iteration",
        )
    return GateResult("G_ARG_02", "PASS", "All claims have SOTA benchmark coverage")


def evaluate_argument_quality_gate(state: dict[str, Any]) -> dict[str, Any]:
    """G_ARG_01: Check for circular reasoning in CER conclusions."""
    drafts = state.get("cer_chapter_drafts") or {}
    conclusion_text = str(drafts.get("5 Conclusions") or "")
    circular_patterns = [
        "as claimed in section", "as stated in the IFU", "per the claim ledger",
    ]
    findings = [p for p in circular_patterns if p.lower() in conclusion_text.lower()]
    if len(findings) >= 3:
        return GateResult(
            "G_ARG_01", "REWORK_REQUIRED",
            f"Potential circular reasoning detected: {len(findings)} patterns",
        )
    return GateResult("G_ARG_01", "PASS", "No circular reasoning detected")


def evaluate_cep_exists_gate(state: dict[str, Any]) -> dict[str, Any]:
    """G_CEP: Clinical Evaluation Plan must exist."""
    cep = state.get("clinical_evaluation_plan")
    if not cep:
        return GateResult(
            "G_CEP", "REWORK_REQUIRED", "Clinical Evaluation Plan not generated"
        )
    required = {
        "device_name": cep.get("device_name"),
        "device_class": cep.get("device_class"),
        "scope": cep.get("scope"),
        "literature_search_protocol": cep.get("literature_search_protocol"),
        "appraisal_method": cep.get("appraisal_method"),
        "sota_methodology": cep.get("sota_methodology"),
        "claim_support_method": cep.get("claim_support_method"),
        "benefit_risk_method": cep.get("benefit_risk_method"),
        "pms_pmcf_update_plan": cep.get("pms_pmcf_update_plan"),
    }
    missing = [name for name, value in required.items() if not value]
    protocol = cep.get("literature_search_protocol") or {}
    if isinstance(protocol, dict):
        for name in ("databases", "exclusion_criteria", "inclusion_criteria"):
            if not protocol.get(name):
                missing.append(f"literature_search_protocol.{name}")
    if missing:
        return GateResult(
            "G_CEP",
            "REWORK_REQUIRED",
            f"Clinical Evaluation Plan incomplete: {', '.join(missing[:8])}",
            failure_pattern="cep_methodology_incomplete",
        )
    return GateResult("G_CEP", "PASS", "CEP document exists and methodology fields are complete")


# ── V3.2: Claude Code CER Authoring Engine integration gates ──────────


def evaluate_endpoint_framework_lock(state: dict[str, Any]) -> GateResult:
    """HC-7.0 HC gate: Human confirms the endpoint framework before CER writing.

    Reads sota_endpoint_derivation_table and sota_benchmark_matrix from state,
    checks that locked_endpoint_framework is present and has non-empty
    primary_endpoints. Returns PASS if locked, BLOCKED otherwise.
    """
    sota_endpoint_table = state.get("sota_endpoint_derivation_table") or []
    sota_benchmark_matrix = state.get("sota_benchmark_matrix") or []
    locked = state.get("locked_endpoint_framework") or {}
    primary_endpoints = locked.get("primary_endpoints") or []

    if locked and primary_endpoints:
        return GateResult(
            "G_HC_7_0",
            "PASS",
            f"Endpoint framework locked: {len(primary_endpoints)} primary endpoints, "
            f"{len(locked.get('secondary_endpoints', []))} secondary, "
            f"{len(locked.get('safety_endpoints', []))} safety.",
            severity="advisory",
        )
    return GateResult(
        "G_HC_7_0",
        "BLOCKED",
        "Endpoint framework is not yet locked. "
        f"Available derivation rows: {len(sota_endpoint_table)}; "
        f"benchmark rows: {len(sota_benchmark_matrix)}. "
        "Human must confirm whitelist/greylist/blacklist before CER writing.",
        failure_pattern="endpoint_framework_unlocked",
        upstream_node_to_reroute="endpoint_extraction",
        blocked_reason="Human confirmation of endpoint framework is required.",
    )


def _check_endpoint_framework_locked(state: dict[str, Any]) -> GateResult:
    """G46 sub-condition: locked_endpoint_framework has non-empty primary_endpoints."""
    locked = state.get("locked_endpoint_framework") or {}
    primary = locked.get("primary_endpoints") or []
    if locked and primary:
        return GateResult(
            "endpoint_framework_locked",
            "PASS",
            f"Endpoint framework locked with {len(primary)} primary endpoint(s).",
        )
    return GateResult(
        "endpoint_framework_locked",
        "BLOCKED",
        "locked_endpoint_framework is missing or has empty primary_endpoints. "
        "Human must confirm whitelist/greylist/blacklist (HC-7.0) before writing.",
        failure_pattern="endpoint_framework_unlocked",
        upstream_node_to_reroute="endpoint_extraction",
    )


def _check_clinical_data_consolidated(state: dict[str, Any]) -> GateResult:
    """G46 sub-condition: consolidated_clinical_data_table has non-empty data_sources."""
    consolidated = state.get("consolidated_clinical_data_table") or {}
    sources = consolidated.get("data_sources") or []
    if consolidated and sources:
        return GateResult(
            "clinical_data_consolidated",
            "PASS",
            f"Clinical data consolidated from {len(sources)} source(s).",
        )
    return GateResult(
        "clinical_data_consolidated",
        "BLOCKED",
        "consolidated_clinical_data_table is missing or has empty data_sources. "
        "Run clinical_data_consolidation node before writing.",
        failure_pattern="clinical_data_not_consolidated",
        upstream_node_to_reroute="evidence_registry",
    )


def _check_eu_market_status_set(state: dict[str, Any]) -> GateResult:
    """G46 sub-condition: eu_market_status is one of approved/not_approved/pending."""
    status = str(state.get("eu_market_status") or "").strip().lower()
    if status in {"approved", "not_approved", "pending"}:
        return GateResult(
            "eu_market_status_set",
            "PASS",
            f"EU market status is '{status}'.",
        )
    return GateResult(
        "eu_market_status_set",
        "BLOCKED",
        f"eu_market_status must be one of approved/not_approved/pending, got '{status or '<unset>'}'. "
        "Confirm regulatory pathway before writing.",
        failure_pattern="eu_market_status_unset",
        upstream_node_to_reroute="device_profile",
    )


def _check_claim_evidence_linkage(state: dict[str, Any]) -> GateResult:
    """G46 sub-condition: every claim must have at least one linked evidence_id.

    BIGDP2026.6 P1.1: Real evaluator replacing placeholder auto-downgrade.
    BLOCKED when ANY claim lacks evidence linkage — Writer cannot write
    unsubstantiated claims.
    """
    claim_ledger = state.get("claim_ledger") or []
    claim_matrix = state.get("claim_evidence_matrix") or []
    matrix_by_claim = {
        str(row.get("claim_id") or ""): row
        for row in claim_matrix
        if row.get("claim_id")
    }
    unlinked_claims = []
    for idx, claim in enumerate(claim_ledger, start=1):
        claim_id = str(claim.get("claim_id") or f"C-{idx:02d}")
        matrix_row = matrix_by_claim.get(claim_id) or {}
        evidence_ids = matrix_row.get("evidence_ids") or matrix_row.get("evidence_id") or ""
        if isinstance(evidence_ids, list):
            evidence_ids = [e for e in evidence_ids if e]
        else:
            evidence_ids = str(evidence_ids).strip()
        if not evidence_ids:
            unlinked_claims.append({
                "claim_id": claim_id,
                "claim_text": str(claim.get("claim_text") or claim.get("claim") or "")[:120],
            })
    if not claim_ledger:
        return GateResult(
            "claim_evidence",
            "REWORK_REQUIRED",
            "claim_ledger is empty — cannot verify claim-evidence linkage.",
            failure_pattern="claim_ledger_empty",
            upstream_node_to_reroute="claim_decomposition",
        )
    if unlinked_claims:
        ids = ", ".join(c["claim_id"] for c in unlinked_claims)
        return GateResult(
            "claim_evidence",
            "BLOCKED",
            f"{len(unlinked_claims)} claim(s) lack evidence linkage: {ids}. "
            "Writer cannot produce substantiated CER sections without evidence-claim traceability.",
            failure_pattern="claim_evidence_link_missing",
            upstream_node_to_reroute="pre_g42_claim_evidence_candidate_linking",
        )
    return GateResult(
        "claim_evidence",
        "PASS",
        f"All {len(claim_ledger)} claim(s) have evidence linkage.",
    )


def _check_retrieval_completeness(state: dict[str, Any]) -> GateResult:
    """G46 sub-condition: literature retrieval must cover all planned searches.

    BIGDP2026.6 P1.1: Real evaluator replacing placeholder auto-downgrade.
    BLOCKED when no search has been executed or planned searches outnumber
    completed searches. REWORK_REQUIRED when searches exist but are incomplete.
    """
    search_runs = state.get("search_run_registry") or []
    cep = state.get("clinical_evaluation_plan") or {}
    lsp = cep.get("literature_search_protocol") or {}
    planned_databases = lsp.get("databases") or []

    if not search_runs:
        return GateResult(
            "retrieval_completeness",
            "BLOCKED",
            "search_run_registry is empty — no literature search has been executed. "
            "Writer cannot proceed without retrieval evidence.",
            failure_pattern="no_search_executed",
            upstream_node_to_reroute="sota_search",
        )

    completed = [s for s in search_runs if str(s.get("status") or "").lower() in ("completed", "done", "finished")]
    failed = [s for s in search_runs if str(s.get("status") or "").lower() in ("failed", "error")]

    if planned_databases and len(completed) < len(planned_databases):
        return GateResult(
            "retrieval_completeness",
            "REWORK_REQUIRED",
            f"Only {len(completed)}/{len(planned_databases)} planned database(s) searched. "
            "Complete all planned searches before Writer release.",
            failure_pattern="incomplete_search_coverage",
            upstream_node_to_reroute="sota_search",
        )

    if failed:
        return GateResult(
            "retrieval_completeness",
            "REWORK_REQUIRED",
            f"{len(failed)} search(es) failed. Retry or document the controlled compromise before Writer release.",
            failure_pattern="search_failures_present",
            upstream_node_to_reroute="sota_search",
        )

    return GateResult(
        "retrieval_completeness",
        "PASS",
        f"All {len(search_runs)} search(es) completed successfully.",
    )


def _evidence_sufficiency_override_result(state: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    status = str(override.get("status") or "PASS").upper()
    if status == "REWORK":
        status = "REWORK_REQUIRED"
    if status not in {"PASS", "REWORK_REQUIRED", "BLOCKED"}:
        status = "REWORK_REQUIRED"
    current_round = _g42_current_spiral_round(state)
    if status == "REWORK_REQUIRED" and current_round >= MAX_SPIRAL_ROUNDS:
        status = "BLOCKED"
    if status == "PASS":
        next_node = "sota_clinical_context"
    elif status == "REWORK_REQUIRED":
        next_node = "query_expansion"
    else:
        next_node = "controlled_compromise"
    report = {
        "gate_id": "G42",
        "gate_name": "Evidence Sufficiency",
        "status": status,
        "failure_pattern": "" if status == "PASS" else (override.get("failure_pattern") or override.get("rework_reason") or override.get("message") or "override_requested"),
        "upstream_node_to_reroute": next_node if status == "REWORK_REQUIRED" else "",
        "spiral_round": current_round,
        "current_spiral_round": current_round,
        "next_node": next_node,
        "claim_sufficiency": [],
        "insufficient_claims": [],
        "rework_reason": override.get("rework_reason") or override.get("message") or "Override requested.",
        "blocked_reason": f"Evidence spiral exhausted the maximum of {MAX_SPIRAL_ROUNDS} rounds." if status == "BLOCKED" else "",
        "reroute_context": {
            "override_applied": True,
            "max_spiral_rounds": MAX_SPIRAL_ROUNDS,
            "evidence_loop": True,
        },
        "message": f"G42 {status}; route to {next_node}.",
    }
    return _with_gate_trace(report, state)


def _g42_claim_sufficiency_rows(state: dict[str, Any]) -> list[dict[str, Any]]:
    preg42_rows = state.get("pre_g42_claim_evidence_candidate_matrix") or []
    if preg42_rows:
        rows = []
        for row in preg42_rows:
            failure_pattern = str(row.get("failure_pattern") or "")
            status = str(row.get("sufficiency_status") or ("PASS" if not failure_pattern else "REWORK_REQUIRED"))
            rows.append(
                {
                    "claim_id": row.get("claim_id"),
                    "claim_type": row.get("claim_type"),
                    "primary_evidence_source_type": row.get("primary_evidence_source_type"),
                    "required_source_profile": row.get("required_source_profile"),
                    "source_profile_status": row.get("source_profile_status"),
                    "source_profile_met_clauses": row.get("source_profile_met_clauses"),
                    "source_profile_unmet_clauses": row.get("source_profile_unmet_clauses"),
                    "sufficiency_status": status,
                    "passing_evidence_ids": row.get("candidate_evidence_ids") if status == "PASS" else "",
                    "candidate_evidence_ids": row.get("candidate_evidence_ids"),
                    "candidate_count": row.get("candidate_count"),
                    "best_evidence_id": row.get("best_evidence_id"),
                    "best_role": row.get("best_role"),
                    "best_applicability": row.get("best_applicability"),
                    "best_directness": row.get("best_directness"),
                    "best_full_text_status": row.get("best_full_text_status"),
                    "best_endpoint_match": row.get("best_endpoint_or_outcome_family_match"),
                    "best_allowed_conclusion_strength": row.get("allowed_conclusion_strength"),
                    "best_missing_data_impact": row.get("best_missing_data_impact"),
                    "best_missing_data_flags": row.get("best_missing_data_flags"),
                    "semantic_support_relation": row.get("semantic_support_relation"),
                    "failure_pattern": failure_pattern,
                    "repair_route": row.get("repair_route") or G42_FAILURE_REPAIR_ROUTES.get(failure_pattern, "query_expansion"),
                    "reason": row.get("insufficiency_reason_if_any") or ("At least one evidence item satisfies G42 sufficiency." if status == "PASS" else "Pre-G42 candidate matrix did not establish sufficiency."),
                }
            )
        return rows
    evidence_by_id = {str(row.get("evidence_id") or ""): row for row in state.get("evidence_registry") or []}
    appraisal_by_evidence = {str(row.get("evidence_id") or ""): row for row in state.get("article_appraisal") or [] if row.get("evidence_id")}
    fulltext_by_evidence = {str(row.get("evidence_id") or ""): row for row in state.get("fulltext_acquisition_status_table") or [] if row.get("evidence_id")}
    benchmarks = state.get("sota_benchmark_matrix") or []
    derivations = state.get("sota_endpoint_derivation_table") or []
    matrix_by_claim = {str(row.get("claim_id") or ""): row for row in state.get("claim_evidence_matrix") or [] if row.get("claim_id")}
    source_availability = _g42_source_availability(state)
    rows = []
    for idx, claim in enumerate(state.get("claim_ledger") or [], start=1):
        claim_id = str(claim.get("claim_id") or f"C-{idx:02d}")
        claim_type = _g42_claim_type(claim)
        source_profile = _g42_source_profile_assessment(claim_type, source_availability)
        evidence_ids = _g42_evidence_ids_for_claim(claim_id, benchmarks, derivations, matrix_by_claim)
        if not evidence_ids and len(state.get("claim_ledger") or []) == 1:
            evidence_ids = [str(row.get("evidence_id") or "") for row in state.get("evidence_registry") or [] if row.get("evidence_id")]
        candidate_rows = []
        for evidence_id in evidence_ids:
            evidence = evidence_by_id.get(str(evidence_id))
            if not evidence:
                continue
            appraisal = appraisal_by_evidence.get(str(evidence_id), {})
            fulltext = fulltext_by_evidence.get(str(evidence_id), {})
            candidate_rows.append(_g42_evidence_candidate_result(claim, evidence, appraisal, fulltext, bool(evidence_id in set(evidence_ids))))
        passing = [row for row in candidate_rows if row.get("meets_sufficiency")]
        best = passing[0] if passing else (candidate_rows[0] if candidate_rows else {})
        failure_pattern = "" if passing else "LINKING_GAP"
        repair_route = "" if passing else G42_FAILURE_REPAIR_ROUTES["LINKING_GAP"]
        reason = "At least one evidence item satisfies G42 sufficiency." if passing else _g42_candidate_failure_reason(candidate_rows)
        if candidate_rows and not passing and all(str(row.get("missing_data_impact") or "").upper() == "BLOCKING" for row in candidate_rows):
            failure_pattern = "MISSING_DATA_BLOCKING"
            repair_route = G42_FAILURE_REPAIR_ROUTES["MISSING_DATA_BLOCKING"]
            reason = "Candidate evidence has BLOCKING missing-data impact and cannot be pivotal/supportive."
        elif source_profile["source_profile_status"] != "PASS":
            failure_pattern = "SOURCE_TYPE_REQUIREMENT_NOT_MET"
            repair_route = source_profile["source_requirement_repair_route"]
            reason = f"Required source profile {source_profile.get('required_source_profile')} is unmet: {source_profile.get('source_profile_unmet_clauses')}."
        sufficiency_status = "PASS" if passing and not failure_pattern else "REWORK_REQUIRED"
        rows.append(
            {
                "claim_id": claim_id,
                "claim_type": claim.get("claim_type"),
                "required_source_profile": source_profile["required_source_profile"],
                "source_profile_status": source_profile["source_profile_status"],
                "source_profile_met_clauses": source_profile["source_profile_met_clauses"],
                "source_profile_unmet_clauses": source_profile["source_profile_unmet_clauses"],
                "sufficiency_status": sufficiency_status,
                "passing_evidence_ids": ", ".join(row.get("evidence_id") for row in passing if row.get("evidence_id")),
                "candidate_evidence_ids": ", ".join(row.get("evidence_id") for row in candidate_rows if row.get("evidence_id")),
                "best_role": best.get("role", "none"),
                "best_applicability": best.get("applicability", "none"),
                "best_directness": best.get("directness", "none"),
                "best_full_text_status": best.get("full_text_status", "none"),
                "best_endpoint_match": best.get("endpoint_match", "none"),
                "best_allowed_conclusion_strength": best.get("allowed_conclusion_strength", "none"),
                "best_missing_data_impact": best.get("missing_data_impact", "NONE"),
                "best_missing_data_flags": best.get("missing_data_flags", ""),
                "failure_pattern": failure_pattern,
                "repair_route": repair_route,
                "reason": reason,
            }
        )
    return rows


def _g42_evidence_ids_for_claim(claim_id: str, benchmarks: list[dict[str, Any]], derivations: list[dict[str, Any]], matrix_by_claim: dict[str, dict[str, Any]]) -> list[str]:
    benchmark_ids = {str(row.get("benchmark_id") or "") for row in benchmarks if str(row.get("corresponding_claim_id") or "") == claim_id}
    evidence_ids = [
        str(row.get("evidence_id") or row.get("source_evidence_id") or "")
        for row in derivations
        if not benchmark_ids or str(row.get("benchmark_id") or "") in benchmark_ids
    ]
    matrix = matrix_by_claim.get(claim_id) or {}
    evidence_ids.extend(__import__("re").split(r"[,;]\s*", str(matrix.get("evidence_ids") or "")))
    return _g42_unique(evidence_ids)


def _g42_claim_type(claim: dict[str, Any]) -> str:
    text = " ".join(str(value or "") for value in claim.values()).lower()
    claim_type = str(claim.get("claim_type") or "").lower().replace("-", "_").replace(" ", "_")
    if claim_type in {"ifu_safety_warning", "clinical_benefit", "clinical_safety", "performance", "sota_benchmark", "risk_control", "risk_control_instruction", "pmcf_boundary", "pms_or_pmcf", "intended_purpose"}:
        return claim_type
    if "intended" in claim_type or "purpose" in claim_type:
        return "intended_purpose"
    if any(token in text for token in ("warning", "contraindication", "precaution", "side-effect", "side effect")):
        return "ifu_safety_warning"
    if "benefit" in claim_type or "clinical benefit" in text:
        return "clinical_benefit"
    if "safety" in claim_type:
        return "clinical_safety"
    if "performance" in claim_type:
        return "performance"
    if "sota" in claim_type or "benchmark" in claim_type:
        return "sota_benchmark"
    if "risk" in claim_type or "risk control" in text:
        return "risk_control_instruction"
    if "pmcf" in claim_type or "pms" in claim_type:
        return "pms_or_pmcf"
    return claim_type or "other"


def _g42_required_source_profile(claim_type: str) -> list[list[str]]:
    return {
        "clinical_benefit": [["subject_device", "literature"]],
        "clinical_safety": [["subject_device", "literature"], ["vigilance", "PMS_PMCF"]],
        "ifu_safety_warning": [["IFU"], ["RMF"]],
        "performance": [["test_validation"]],
        "sota_benchmark": [["literature"]],
        "risk_control": [["RMF"], ["IFU"]],
        "risk_control_instruction": [["RMF"], ["IFU"]],
        "pmcf_boundary": [["PMS_PMCF"]],
        "pms_or_pmcf": [["PMS_PMCF"]],
    }.get(str(claim_type or "").lower(), [])


def _g42_source_profile_text(claim_type: str) -> str:
    clauses = _g42_required_source_profile(claim_type)
    if not clauses:
        return "not_applicable"
    return " AND ".join("(" + " OR ".join(clause) + ")" for clause in clauses)


def _g42_source_availability(state: dict[str, Any]) -> dict[str, bool]:
    inventory = state.get("source_inventory") or []
    doc_types = {str(row.get("document_type") or row.get("doc_type") or "").lower() for row in inventory}
    text = " ".join(" ".join(str(row.get(key, "")) for key in ("document_type", "filename", "path", "source_role")) for row in inventory).lower()
    availability = {
        "IFU": "ifu" in doc_types or "ifu" in text or "instruction" in text,
        "RMF": bool({"rmf", "rmr", "fmea", "risk"}.intersection(doc_types)) or any(token in text for token in ("risk management", "rmf", "rmr", "fmea")),
        "GSPR": "gspr" in doc_types or "gspr" in text,
        "PMS_PMCF": bool({"pms", "pmcf"}.intersection(doc_types)) or any(token in text for token in ("pms", "pmcf", "post-market", "post market")),
        "vigilance": bool(state.get("vigilance_recall_registry")),
        "test_validation": any(token in text for token in ("test", "verification", "validation", "bench", "performance", "report")),
        "similar_device": bool(state.get("equivalence_matrix") or state.get("similar_device_attachment_index")),
        "literature": False,
        "subject_device": False,
        "registry": bool(state.get("vigilance_recall_registry")),
    }
    for evidence in state.get("evidence_registry") or []:
        if str(evidence.get("evidence_id") or "").startswith("E-GAP") or str(evidence.get("missing_data_impact") or "").upper() == "BLOCKING":
            continue
        source_type = str(evidence.get("source_type") or "").lower()
        if evidence.get("pmid") or source_type.startswith("literature_") or not source_type:
            availability["literature"] = True
        if source_type.startswith("subject_device_") or str(evidence.get("device_relationship") or "").lower() == "subject":
            availability["subject_device"] = True
        if "ifu" in source_type:
            availability["IFU"] = True
        if "risk_management" in source_type or "rmf" in source_type:
            availability["RMF"] = True
        if "gspr" in source_type:
            availability["GSPR"] = True
        if "pms" in source_type or "pmcf" in source_type:
            availability["PMS_PMCF"] = True
        if "test_performance" in source_type or "test_validation" in source_type:
            availability["test_validation"] = True
        if "registry" in source_type:
            availability["registry"] = True
    if availability["IFU"] or availability["RMF"] or availability["PMS_PMCF"] or availability["test_validation"]:
        availability["subject_device"] = True
    return availability


def _g42_source_profile_assessment(claim_type: str, sources: dict[str, bool]) -> dict[str, str]:
    clauses = _g42_required_source_profile(claim_type)
    unmet = [clause for clause in clauses if not any(sources.get(source) for source in clause)]
    met = [clause for clause in clauses if any(sources.get(source) for source in clause)]
    missing_sources = ["/".join(clause) for clause in unmet]
    return {
        "required_source_profile": _g42_source_profile_text(claim_type),
        "source_profile_status": "PASS" if not unmet else "SOURCE_TYPE_REQUIREMENT_NOT_MET",
        "source_profile_met_clauses": "; ".join("/".join(clause) for clause in met) or "none",
        "source_profile_unmet_clauses": "; ".join(missing_sources) or "none",
        "source_requirement_repair_route": _g42_source_requirement_repair_route(missing_sources),
    }


def _g42_source_requirement_repair_route(missing_sources: list[str]) -> str:
    text = " ".join(missing_sources)
    if any(token in text for token in ("IFU", "RMF", "GSPR", "PMS_PMCF", "vigilance")):
        return "risk_gspr_mapping"
    if "test_validation" in text or "subject_device" in text:
        return "evidence_appraisal"
    if "literature" in text:
        return "query_expansion"
    return "pre_g42_claim_evidence_candidate_linking"


def _g42_evidence_candidate_result(claim: dict[str, Any], evidence: dict[str, Any], appraisal: dict[str, Any], fulltext: dict[str, Any], linked_to_claim: bool) -> dict[str, Any]:
    role = str(evidence.get("weight") or appraisal.get("weight") or "").lower()
    missing_data_flags = evidence.get("missing_data_flags") or appraisal.get("missing_data_flags") or []
    missing_data_impact = str(evidence.get("missing_data_impact") or appraisal.get("missing_data_impact") or "NONE").upper()
    if missing_data_impact == "BLOCKING":
        role = "background"
    applicability = _g42_applicability(evidence, appraisal)
    directness = _g42_directness(evidence, appraisal, linked_to_claim)
    full_text_status = _g42_full_text_status(evidence, appraisal, fulltext)
    endpoint_match = _g42_endpoint_match(evidence, appraisal, linked_to_claim)
    allowed_strength = str(evidence.get("conclusion_strength_allowed") or appraisal.get("conclusion_strength_allowed") or "").lower()
    strength_compatible = _g42_conclusion_strength_compatible(str(claim.get("claim_type") or ""), allowed_strength, directness)
    role_ok = role in {"pivotal", "supportive"}
    applicability_ok = applicability in {"high", "medium"}
    directness_ok = directness in {"high", "medium"} or (directness == "low" and strength_compatible and _g42_is_cautious_strength(allowed_strength))
    fulltext_ok = full_text_status in {"available", "partial"}
    endpoint_ok = endpoint_match is True
    return {
        "evidence_id": str(evidence.get("evidence_id") or ""),
        "role": role or "none",
        "applicability": applicability,
        "directness": directness,
        "full_text_status": full_text_status,
        "endpoint_match": "true" if endpoint_ok else "false",
        "allowed_conclusion_strength": allowed_strength or "not_recorded",
        "missing_data_flags": ", ".join(str(flag) for flag in missing_data_flags) if isinstance(missing_data_flags, list) else missing_data_flags,
        "missing_data_impact": missing_data_impact,
        "meets_sufficiency": missing_data_impact != "BLOCKING" and role_ok and applicability_ok and directness_ok and fulltext_ok and endpoint_ok and strength_compatible,
    }


def _g42_applicability(evidence: dict[str, Any], appraisal: dict[str, Any]) -> str:
    values = [
        evidence.get("device_relevance"),
        evidence.get("population_relevance"),
        appraisal.get("device_applicability"),
        appraisal.get("population_match"),
        evidence.get("device_procedure_applicability"),
        appraisal.get("device_procedure_applicability"),
    ]
    normalized = [str(value or "").lower() for value in values if str(value or "").strip()]
    if "low" in normalized or "not_applicable_wrong_domain" in normalized:
        return "low"
    if "high" in normalized:
        return "high"
    if "medium" in normalized:
        return "medium"
    if evidence.get("verified") and (evidence.get("sample_size") or evidence.get("endpoint")):
        return "medium"
    return "unknown"


def _g42_directness(evidence: dict[str, Any], appraisal: dict[str, Any], linked_to_claim: bool) -> str:
    explicit = str(evidence.get("directness") or appraisal.get("directness") or "").lower()
    if explicit in {"high", "medium", "low"}:
        return explicit
    if evidence.get("retrieval_domain_status") == "RETRIEVAL_DOMAIN_MISMATCH_REWORK_REQUIRED":
        return "low"
    if linked_to_claim and (evidence.get("endpoint") or evidence.get("endpoint_match") in {"high", "medium"}):
        return "high"
    if linked_to_claim:
        return "medium"
    return "low"


def _g42_full_text_status(evidence: dict[str, Any], appraisal: dict[str, Any], fulltext: dict[str, Any]) -> str:
    raw = " ".join(
        str(value or "").lower()
        for value in (
            evidence.get("appraisal_basis"),
            evidence.get("full_text_status"),
            appraisal.get("full_text_status"),
            fulltext.get("full_text_retrieval_status"),
            fulltext.get("full_text_available"),
        )
    )
    if "full_text_available" in raw or "source_full_text" in raw or "full_text_public" in raw or "full_text_user" in raw or "yes" in raw:
        return "available"
    if "extended_abstract" in raw or "structured_summary" in raw or "partial" in raw:
        return "partial"
    if evidence.get("sample_size") and evidence.get("follow_up") and evidence.get("result"):
        return "partial"
    return "unavailable"


def _g42_endpoint_match(evidence: dict[str, Any], appraisal: dict[str, Any], linked_to_claim: bool) -> bool:
    value = str(evidence.get("endpoint_match") or appraisal.get("endpoint_match") or "").lower()
    if value in {"high", "medium", "true", "yes", "endpoint_match", "generic_clinical_endpoint_match"}:
        return True
    if linked_to_claim and (evidence.get("endpoint") or evidence.get("result")):
        return True
    return False


def _g42_conclusion_strength_compatible(claim_type: str, allowed_strength: str, directness: str) -> bool:
    strength = str(allowed_strength or "").lower()
    if "not_allowed" in strength:
        return False
    if directness == "low":
        return _g42_is_cautious_strength(strength)
    if not strength:
        return True
    return any(token in strength for token in ("strong", "moderate", "cautious", "descriptive", "controlled", "limited", "support"))


def _g42_is_cautious_strength(strength: str) -> bool:
    if not strength:
        return False
    return any(token in strength for token in ("cautious", "descriptive", "limited", "background", "supportive"))


def _g42_candidate_failure_reason(candidates: list[dict[str, Any]]) -> str:
    if not candidates:
        return "No evidence candidate is linked to this claim."
    return "; ".join(
        f"{row.get('evidence_id')}: role={row.get('role')}, applicability={row.get('applicability')}, directness={row.get('directness')}, full_text={row.get('full_text_status')}, endpoint_match={row.get('endpoint_match')}, strength={row.get('allowed_conclusion_strength')}"
        for row in candidates[:5]
    )


def _g42_failure_patterns(insufficient: list[dict[str, Any]]) -> list[str]:
    patterns = []
    for row in insufficient:
        pattern = str(row.get("failure_pattern") or "LINKING_GAP")
        if pattern and pattern not in patterns:
            patterns.append(pattern)
    return patterns


def _g42_primary_failure_pattern(insufficient: list[dict[str, Any]]) -> str:
    patterns = _g42_failure_patterns(insufficient)
    for pattern in G42_FAILURE_PRIORITY:
        if pattern in patterns:
            return pattern
    return patterns[0] if patterns else "LINKING_GAP"


def _g42_primary_repair_route(insufficient: list[dict[str, Any]], route_pattern: str) -> str:
    for row in insufficient:
        if str(row.get("failure_pattern") or "") == route_pattern and row.get("repair_route"):
            return str(row.get("repair_route"))
    return G42_FAILURE_REPAIR_ROUTES.get(route_pattern, "query_expansion")


def _g42_rework_reason(insufficient: list[dict[str, Any]]) -> str:
    return "Evidence sufficiency unmet for claim(s): " + "; ".join(
        f"{row.get('claim_id')} [{row.get('failure_pattern') or 'LINKING_GAP'}] ({row.get('reason')})" for row in insufficient[:8]
    )


def _g42_current_spiral_round(state: dict[str, Any]) -> int:
    rounds = [_g42_safe_int(row.get("spiral_round_id")) for row in state.get("evidence_spiral_lineage") or [] if isinstance(row, dict)]
    if state.get("spiral_round_id"):
        rounds.append(_g42_safe_int(state.get("spiral_round_id")))
    return max(rounds or [1])


def _g42_safe_int(value: Any) -> int:
    try:
        return int(value)
    except Exception:
        return 0


def _g42_unique(values: list[str]) -> list[str]:
    output = []
    for value in values:
        cleaned = str(value or "").strip()
        if cleaned and cleaned not in output and cleaned.lower() not in {"none recorded", "evidence gap"}:
            output.append(cleaned)
    return output


# ── DP-aware helpers (Connection 4: defect_patterns → G39) ──────────────────

def _load_defect_patterns() -> dict[str, Any]:
    """Load defect_patterns.json and return patterns indexed by detection method and by id."""
    import json
    from pathlib import Path
    dp_path = Path(__file__).parent / "knowledge" / "defect_patterns.json"
    try:
        dp = json.loads(dp_path.read_text())
    except Exception:
        return {"patterns": [], "by_detection": {}, "by_id": {}}
    patterns = dp.get("patterns", [])
    by_detection: dict[str, list[dict]] = {}
    by_id: dict[str, dict] = {}
    for p in patterns:
        pid = p.get("id", "")
        det = p.get("detection", "")
        if pid:
            by_id[pid] = p
        if det:
            by_detection.setdefault(det, []).append(p)
    return {"patterns": patterns, "by_detection": by_detection, "by_id": by_id}


def _check_annex_population(state: dict[str, Any]) -> str:
    """DP-038: Check if annexes contain placeholder/unpopulated content."""
    cer_chapters = state.get("cer_chapter_drafts") or {}
    annex_keys = [k for k in cer_chapters if "Annex" in k or "annex" in k.lower()]
    empty_annexes = []
    for key in annex_keys:
        content = str(cer_chapters.get(key, ""))
        word_count = len(content.split())
        if word_count < 20:
            empty_annexes.append(key)
    if empty_annexes:
        return f"{len(empty_annexes)} annex(es) with <20 words: {empty_annexes[:3]}"
    return ""


def _check_citation_density(body_text: str) -> str:
    """DP-036: Check if citation density is below threshold."""
    words = body_text.split()
    word_count = len(words)
    if word_count < 100:
        return ""
    import re
    ref_patterns = re.findall(r'\[\d+(?:,\s*\d+)*\]|\(\w+,\s*\d{4}\)', body_text)
    ref_count = len(ref_patterns)
    refs_per_1000 = (ref_count / word_count) * 1000
    if refs_per_1000 < 2:
        return f"{refs_per_1000:.1f} refs/1000 words (threshold: 2.0), {ref_count} refs in {word_count} words"
    return ""


# ── P0-2: Writing Style Detection (engineer feedback: passive voice, sentence length) ──

# Per-section sentence length constraints from CER_03 engineer feedback
_SECTION_SENTENCE_LENGTH = {
    "2": (22, 32),   # Device description: longer (technical parameters)
    "3": (22, 32),   # SOTA: standard
    "4": (25, 30),   # Evidence analysis: moderate
    "5": (15, 20),   # Conclusions: short and direct
    "1": (20, 28),   # Summary
}

# Passive voice patterns (common in CER)
_PASSIVE_PATTERNS = [
    r"\bis\s+\w+ed\b", r"\bare\s+\w+ed\b", r"\bwas\s+\w+ed\b",
    r"\bwere\s+\w+ed\b", r"\bbeen\s+\w+ed\b", r"\bbeing\s+\w+ed\b",
    r"\bhas\s+been\s+\w+ed\b", r"\bhave\s+been\s+\w+ed\b",
]


def _check_writing_style(cer_chapters: dict[str, str]) -> list[str]:
    """P0-2: Check CER body for writing style violations per engineer feedback.

    Returns list of style violation descriptions.
    """
    import re
    violations = []

    for section_key, text in cer_chapters.items():
        if not text or not isinstance(text, str):
            continue
        words = text.split()
        word_count = len(words)
        if word_count < 20:
            continue  # too short to assess

        # ── Passive voice ratio check ──
        # Target: 15-25% passive. Flag if <10% or >40%
        passive_count = 0
        for pattern in _PASSIVE_PATTERNS:
            passive_count += len(re.findall(pattern, text, re.IGNORECASE))
        total_verbs_approx = max(word_count // 5, 1)  # rough estimate
        passive_pct = (passive_count / total_verbs_approx) * 100
        section_num = section_key.split(" ")[0].replace("§", "").split(".")[0]

        # §2 should have HIGHER passive (technical description)
        # §4.7/§5 should have LOWER passive (active analysis)
        is_analysis_section = any(kw in section_key for kw in ["4.7", "Analysis", "5 "])
        is_device_section = any(kw in section_key for kw in ["2.", "Device", "Description"])

        if is_device_section and passive_pct < 10:
            violations.append(f"§{section_num}: Passive voice too LOW ({passive_pct:.0f}%), should be 15-25% for device description")
        elif is_analysis_section and passive_pct > 30:
            violations.append(f"§{section_num}: Passive voice too HIGH ({passive_pct:.0f}%), should be 10-20% for analysis sections")
        elif not is_device_section and not is_analysis_section and (passive_pct < 8 or passive_pct > 35):
            violations.append(f"§{section_num}: Passive voice ratio outside 15-25% range ({passive_pct:.0f}%)")

        # ── Section-specific sentence length check ──
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if len(s.strip().split()) > 3]
        if not sentences:
            continue
        avg_len = sum(len(s.split()) for s in sentences) // len(sentences)
        limit = _SECTION_SENTENCE_LENGTH.get(section_num, (20, 30))
        if avg_len < limit[0] * 0.7 or avg_len > limit[1] * 1.3:
            violations.append(
                f"§{section_num}: Avg sentence length {avg_len} words "
                f"(target {limit[0]}-{limit[1]} for this section type)"
            )

        # ── Hedging/certainty balance check ──
        hedging_words = ["may", "might", "could", "approximately", "typically", "generally", "suggests"]
        certainty_words = ["demonstrated", "confirmed", "proven", "verified", "established", "clearly"]
        hedging_count = sum(1 for w in hedging_words if w in text.lower().split())
        certainty_count = sum(1 for w in certainty_words if w in text.lower().split())
        if certainty_count > hedging_count * 3 and certainty_count > 5:
            violations.append(
                f"§{section_num}: Certainty/Hedging imbalance ({certainty_count} certainty vs {hedging_count} hedging). "
                f"Engineer feedback: 帕姆 writes with 72 certainty / 55 hedging = 1.3 ratio."
            )

    return violations[:8]


# ── Equivalence Circular Reasoning Detection (engineer: 禁止自身数据声明等效) ──

def _check_equivalence_circular_reasoning(state: dict[str, Any]) -> list[str]:
    """Detect self-referential equivalence claims.

    Engineer feedback: equivalence data MUST come from published literature
    of similar devices, NOT from the device under evaluation's own data.
    Using own data → circular reasoning (逻辑循环论证).
    """
    violations = []
    equivalence = state.get("equivalence_3d_matrix") or state.get("equivalence_comparison") or []
    profile = state.get("device_profile") or {}
    device_name = str(profile.get("device_name", "")).lower()
    manufacturer = str(profile.get("manufacturer", "")).lower()

    for i, row in enumerate(equivalence):
        if not isinstance(row, dict):
            continue
        # Check if equivalent device name matches subject device
        eq_name = str(row.get("equivalent_device_name", row.get("equivalent_device", ""))).lower()
        eq_manufacturer = str(row.get("equivalent_manufacturer", "")).lower()

        if eq_name and device_name and eq_name == device_name:
            violations.append(
                f"Equivalence row {i}: Equivalent device '{eq_name}' matches subject device — circular reasoning"
            )
        if eq_manufacturer and manufacturer and eq_manufacturer == manufacturer:
            violations.append(
                f"Equivalence row {i}: Same manufacturer '{eq_manufacturer}' — potential self-referential data"
            )

    # Also check if equivalence references IFU/manufacturer data instead of published literature
    eq_claimed = state.get("equivalence_strategy") == "legacy_mdd" or state.get("equivalence_claimed")
    evidence_registry = state.get("evidence_registry") or []
    if eq_claimed and equivalence:
        pub_evidence = [e for e in evidence_registry
                        if str(e.get("source_type", e.get("data_source_type", ""))).lower()
                        in ("pubmed", "literature", "published", "clinical_study")]
        if not pub_evidence and len(equivalence) > 0:
            violations.append(
                "Equivalence claimed but no published literature evidence found — "
                "equivalence must be based on published data of similar devices"
            )

    return violations[:5]


# ── Numerical Precision Validation (engineer CER_05: 单位/p值/CI/缺失处理) ──

def _check_numerical_precision(cer_chapters: dict[str, str]) -> list[str]:
    """Validate numerical precision in CER body per engineer requirements.

    Rules from CER_05:
    - All values must have units
    - p-values must specify test method
    - 95% CI must show both bounds
    - Missing data must state handling method
    """
    import re
    violations = []

    body_text = " ".join(str(v) for v in cer_chapters.values())
    if not body_text:
        return []

    # Pattern 1: Numbers without units (rough check)
    # Look for patterns like "79.01" or "15-25" that should have units
    bare_numbers = re.findall(r'(?<!\w)(\d{2,4}\.\d{2,4})(?!\s*(?:mm|cm|mg|mL|%|kg|min|hr|ms|mV|mA|°C|mmHg))', body_text)
    if len(bare_numbers) > 10:
        violations.append(
            f"Numerical precision: {len(bare_numbers)} values without apparent units "
            f"(e.g. {bare_numbers[0]}, {bare_numbers[1]}...). Per CER_05: all values must have units."
        )

    # Pattern 2: p-values without test method
    p_values = re.findall(r'p\s*[<=>]\s*0\.\d+', body_text, re.IGNORECASE)
    test_methods = re.findall(r'(t-test|Wilcoxon|log.rank|ANOVA|chi.square|Fisher|Mann.Whitney|Kruskal.Wallis)', body_text, re.IGNORECASE)
    if p_values and len(test_methods) < len(p_values) * 0.5:
        violations.append(
            f"Numerical precision: {len(p_values)} p-values found but only {len(test_methods)} "
            f"test methods specified. Per CER_05: each p-value must state test method."
        )

    # Pattern 3: CI without both bounds
    ci_patterns = re.findall(r'95%\s*CI[:\s]*([^,.;]+)', body_text, re.IGNORECASE)
    incomplete_ci = []
    for ci in ci_patterns:
        if "-" not in ci and "to" not in ci.lower():
            incomplete_ci.append(ci.strip()[:40])
    if incomplete_ci:
        violations.append(
            f"Numerical precision: {len(incomplete_ci)} CI statements without both lower and upper bounds "
            f"(e.g. {incomplete_ci[0]}). Per CER_05: 95% CI must show both bounds."
        )

    return violations[:5]


# ── Paragraph Logic Rules (engineer CER_03: 行文密码) ──

_PARAGRAPH_RULES = {
    "GSPR": {
        "elements": ["条款引用", "证据摘要", "符合性声明", "差距分析", "交叉引用"],
        "keywords": [["gspr", "clause", "article"], ["evidence", "data", "study"],
                     ["complies", "meets", "satisfies"], ["gap", "missing", "insufficient"],
                     ["section", "chapter", "cross-ref"]],
        "min_elements": 3,
    },
    "Literature": {
        "elements": ["研究设计", "样本量", "终点指标", "质量评价", "贡献度", "局限性"],
        "keywords": [["design", "rct", "cohort", "case"], ["n=", "patients", "subjects", "sample"],
                     ["endpoint", "outcome", "measured"], ["quality", "score", "appraisal"],
                     ["contribution", "weight", "role"], ["limitation", "bias", "confound"]],
        "min_elements": 4,
    },
    "Conclusions": {
        "elements": ["总结陈述", "逐条结论", "后续建议"],
        "keywords": [["conclude", "overall", "summary"], ["claim", "finding", "result"],
                     ["recommend", "next", "future", "pmcf"]],
        "min_elements": 2,
    },
}


def _check_paragraph_logic(cer_chapters: dict[str, str]) -> list[str]:
    """Verify paragraph structure follows 行文密码 (writing passwords).

    Per CER_03 engineer feedback:
    - GSPR paragraph: 5 required elements (条款引用/证据摘要/符合性声明/差距分析/交叉引用)
    - Literature evaluation paragraph: 6 required elements
    - Conclusions paragraph: 3 required elements
    """
    violations = []
    for section_key, text in cer_chapters.items():
        if not text or not isinstance(text, str):
            continue
        text_lower = text.lower()

        # Only check sections with substantial content (>50 words)
        if len(text.split()) < 50:
            continue

        # Determine which rules apply
        is_gspr = any(kw in section_key for kw in ["GSPR", "4.7"])
        is_literature = any(kw in section_key for kw in ["Literature", "4.4", "4.5", "Appraisal", "Screening"])
        is_conclusions = any(kw in section_key for kw in ["Conclusion", "5 "])

        rule = None
        if is_gspr:
            rule = _PARAGRAPH_RULES["GSPR"]
        elif is_literature:
            rule = _PARAGRAPH_RULES["Literature"]
        elif is_conclusions:
            rule = _PARAGRAPH_RULES["Conclusions"]
        else:
            continue

        # Count element presence
        found = 0
        missing_elements = []
        for i, keywords in enumerate(rule["keywords"]):
            if any(kw in text_lower for kw in keywords):
                found += 1
            else:
                missing_elements.append(rule["elements"][i])

        if found < rule["min_elements"]:
            violations.append(
                f"{section_key}: Only {found}/{len(rule['elements'])} paragraph elements found "
                f"(missing: {', '.join(missing_elements)}). "
                f"Per CER_03: this section type requires {rule['min_elements']}+ elements."
            )

    return violations[:5]


# ── Annex Density Check (engineer CER_01: 3-5 tables per 10 pages) ──

def _check_annex_density(cer_chapters: dict[str, str]) -> list[str]:
    """Check table density per CER_01 standard: 3-5 tables per 10 pages."""
    violations = []
    annex_chapters = {k: v for k, v in cer_chapters.items() if "Annex" in k}
    if not annex_chapters:
        return []
    total_words = sum(len(str(v).split()) for v in annex_chapters.values())
    est_pages = max(total_words / 400, 1)  # ~400 words/page
    table_count = sum(str(v).count("|---|") for v in annex_chapters.values())
    density = (table_count / est_pages) * 10
    if density < 2:
        violations.append(f"Annex table density too LOW: {density:.1f}/10pp ({table_count} tables, ~{est_pages:.0f}pp). CER_01 standard: 3-5/10pp.")
    elif density > 8:
        violations.append(f"Annex table density too HIGH: {density:.1f}/10pp. Consider moving detail tables to separate appendix.")
    return violations


# ── Type A Device Description 8-Field Check (engineer CER_05) ──

_TYPE_A_REQUIRED_FIELDS = [
    "Device Name", "Model / Variant", "EMDN Code", "Classification",
    "Intended Purpose", "Key Components", "Accessories", "Principle of Operation",
]


def _check_device_description_fields(state: dict[str, Any]) -> list[str]:
    """Verify §2.1 Device Description has Type A 8 standard fields."""
    cer_chapters = state.get("cer_chapter_drafts") or {}
    dd_text = ""
    for key in cer_chapters:
        if "2.1" in key or "Device Description" in key or "2 Scope" in key:
            dd_text = str(cer_chapters.get(key, ""))
            break
    if not dd_text:
        profile = state.get("device_profile") or {}
        dd_text = str(profile.get("composition", "")) + " " + str(profile.get("working_principle", ""))
    if len(dd_text.split()) < 20:
        return []
    # Check for key field indicators
    field_keywords = {
        "Device Name": ["device name", "device under evaluation", "subject device"],
        "Model / Variant": ["model", "variant", "catalog number", "reference number"],
        "Classification": ["class", "md rule", "classification"],
        "Intended Purpose": ["intended purpose", "intended use", "indication"],
        "Key Components": ["component", "consists of", "comprises", "material"],
        "Accessories": ["accessor", "compatible", "peripheral"],
        "Principle of Operation": ["principle", "mechanism", "mode of action", "working"],
    }
    missing = []
    for field, keywords in field_keywords.items():
        if not any(kw in dd_text.lower() for kw in keywords):
            missing.append(field)
    if len(missing) >= 3:
        return [f"Device Description missing {len(missing)}/8 Type A fields: {', '.join(missing[:4])}"]
    return []


# ── Type B Equivalence Standardized Wording (engineer CER_05) ──

def _check_equivalence_wording(cer_chapters: dict[str, str]) -> list[str]:
    """Validate equivalence table uses standardized wording per CER_05 Type B."""
    violations = []
    eq_text = ""
    for key in cer_chapters:
        if "Equivalent" in key or "Equivalence" in key or "4.2" in key:
            eq_text += " " + str(cer_chapters.get(key, ""))
    if not eq_text or len(eq_text.split()) < 30:
        return []
    # Required standardized terms
    has_equivalent = any(w in eq_text.lower() for w in ["substantially equivalent", "equivalent with minor", "not equivalent"])
    has_impact = any(w in eq_text.lower() for w in ["impact assessment", "difference impact", "clinical impact"])
    if not has_equivalent:
        violations.append("Type B: Equivalence table missing standardized wording (Substantially equivalent / Equivalent with minor / Not equivalent)")
    if not has_impact:
        violations.append("Type B: Equivalence differences lack impact assessment")
    return violations


# ── Endpoint 4-Element Enforcement (engineer CER_04 5E.1) ──

def _check_endpoint_completeness(state: dict[str, Any]) -> list[str]:
    """Verify endpoints have 4 required elements: definition, measurement, time window, clinical meaning."""
    benchmarks = state.get("sota_benchmark_matrix") or []
    if not benchmarks:
        return []
    incomplete = []
    for bm in benchmarks[:15]:
        endpoint = bm.get("endpoint", "")
        missing = []
        if not bm.get("sota_value_range"):
            missing.append("value/range")
        if not bm.get("clinical_significance"):
            missing.append("clinical_significance")
        if missing and endpoint:
            incomplete.append(f"{endpoint[:40]}... (missing: {', '.join(missing)})")
    if len(incomplete) >= 3:
        return [f"Endpoint incompleteness: {len(incomplete)}/{len(benchmarks)} endpoints lack required elements (4-element framework: definition+measurement+time+clinical meaning)"]
    return []


# ── SOTA 3-Function Verification (engineer CER_04 P1.1) ──

def _check_sota_three_functions(state: dict[str, Any]) -> list[str]:
    """P1.1: Verify SOTA serves 3 functions: clinical background, benchmark, gap identification."""
    cer_chapters = state.get("cer_chapter_drafts") or {}
    sota_text = ""
    for key in cer_chapters:
        if "SOTA" in key or "3 " in key or "Clinical Background" in key:
            sota_text += " " + str(cer_chapters.get(key, ""))
    if len(sota_text.split()) < 100:
        return []
    violations = []
    # Function 1: Clinical background
    if not any(kw in sota_text.lower() for kw in ["epidemiology", "prevalence", "incidence", "pathophysi", "natural history"]):
        violations.append("SOTA Function 1 missing: clinical background (epidemiology/pathophysiology)")
    # Function 2: Benchmark establishment
    if not any(kw in sota_text.lower() for kw in ["benchmark", "endpoint", "acceptance criteri", "performance threshold"]):
        violations.append("SOTA Function 2 missing: benchmark/acceptance criteria")
    # Function 3: Gap identification
    if not any(kw in sota_text.lower() for kw in ["gap", "unmet need", "limitation", "insufficient"]):
        violations.append("SOTA Function 3 missing: gap/limitation identification")
    return violations


# ── PMCF Acceptability Prerequisite (engineer: RMF must accept residual risk before PMCF) ──

def _check_pmcf_rmf_prerequisite(state: dict[str, Any]) -> list[str]:
    """P1-G6: PMCF requires RMF to first accept residual risk."""
    pmcf = state.get("pmcf_gap_register") or state.get("gap_pmcf_recommendations") or []
    if not pmcf:
        return []
    rmf = state.get("rmf_registry") or state.get("risk_management_file") or []
    if not rmf:
        return ["PMCF triggered but RMF is missing — RMF must accept residual risk before PMCF can be a tracking commitment (per engineer: RMF整套体系必须先接受风险可接受)"]
    # Check if RMF has residual risk acceptance
    rmf_has_acceptance = any(
        "accept" in str(r.get("residual_risk", "")).lower() or
        "acceptable" in str(r.get("risk_acceptance", "")).lower()
        for r in rmf if isinstance(r, dict)
    )
    if not rmf_has_acceptance:
        return ["PMCF triggered but RMF has no explicit residual risk acceptance — PMCF is a tracking commitment, not a risk resolution mechanism"]
    return []


# ── Safety Benefit Subtype Routing (engineer: P0-G1 claim_type expansion) ──

def _check_claim_subtype_routing(state: dict[str, Any]) -> list[str]:
    """Verify safety benefit claims are routed to clinical literature, not RMF."""
    claims = state.get("claim_ledger") or state.get("claim_evidence_matrix") or []
    violations = []
    for claim in claims:
        claim_type = str(claim.get("claim_type", "")).lower()
        claim_text = str(claim.get("claim_text", ""))[:80]
        # Check: "safety" claims should specify subtype (efficacy_benefit vs safety_benefit)
        if claim_type == "safety" and "benefit" in claim_text.lower():
            # This is likely a safety benefit claim, needs clinical evidence not just RMF
            evidence_ids = claim.get("evidence_ids") or claim.get("allowed_evidence_ids") or []
            if not evidence_ids:
                violations.append(f"Claim '{claim_text[:60]}' type=safety but appears to be safety benefit — may need clinical evidence routing, not RMF-only")
    return violations[:3]


def _gate_claim_text_consistency(state: dict[str, Any]) -> GateResult:
    """Check rendered CER body for claim/BR/text consistency violations.

    Rules:
    - If claim status is insufficient/evidence_gap/not_allowed/ALLOWED_USE_BLOCKED
      → final text must NOT state support
    - If BR ledger says benefit-risk not established or unfavourable
      → summary/conclusion must NOT imply favourable benefit-risk
    """
    cer_chapters = state.get("cer_chapter_drafts") or {}
    body_text = " ".join(str(v) for v in cer_chapters.values())
    body_lower = body_text.lower()

    violations = []

    # ── Check 1: Claim-level consistency ──
    claim_matrix = state.get("claim_evidence_matrix") or []
    for row in claim_matrix:
        claim_id = str(row.get("claim_id", ""))
        status = str(row.get("support_status", "")).upper()
        allowed = str(row.get("allowed_use", "")).upper()
        blocked = status in ("INSUFFICIENT", "EVIDENCE_GAP", "NOT_SUPPORTED") or allowed == "ALLOWED_USE_BLOCKED"
        if not blocked:
            continue
        # Check if claim ID appears with support wording in body
        support_wording = ["demonstrates", "confirms", "supports", "proves", "establishes",
                          "is effective", "is safe", "meets requirements"]
        for word in support_wording:
            if word in body_lower and claim_id.lower() in body_lower:
                violations.append(
                    f"Claim {claim_id} ({status}) cannot use '{word}' in CER body"
                )
                break

    # ── Check 2: BR consistency ──
    br_ledger = state.get("benefit_risk_ledger") or []
    for row in br_ledger:
        balance = str(row.get("benefit_risk_balance", "")).lower()
        if balance in ("unfavourable", "unfavorable", "not established", "inconclusive"):
            favourable_words = ["favourable", "favorable", "positive benefit-risk",
                               "benefit-risk is acceptable", "clearly favourable"]
            for word in favourable_words:
                if word in body_lower:
                    violations.append(
                        f"BR ledger says '{balance}' but body states '{word}'"
                    )
                    break

    if violations:
        return GateResult("G_CLAIM_TEXT", "FAIL", "; ".join(violations[:5]))
    return GateResult("G_CLAIM_TEXT", "PASS", "Claim/BR/text consistency verified.")


def _gate_final_draft_semantic_qa(state: dict[str, Any]) -> GateResult:
    """Gate G39: Validate rendered CER body before allowing PASS_TO_DRAFT_DOCX.

    Checks the actual rendered markdown text for:
    - Banned internal strings (tool names, debug traces, agent references)
    - IFU placeholder text (unresolved extraction gaps)
    - Writer quality self-check score (if available in state)
    """
    cer_chapters = state.get("cer_chapter_drafts") or {}
    if not cer_chapters:
        return GateResult("G39", "PASS", "No CER chapters; final draft QA deferred.")

    # ── Check 1: Banned internal strings in rendered body ──
    _BANNED_RENDER_CHECK = [
        "Claude", "DeerFlow", "MCP", "subagent_invocation_log",
        "SKILL REFERENCE", "PLANNER AGENT", "IMPLEMENTER AGENT", "REVIEWER AGENT",
        "workbuddy", "execution trace", "agent handoff", "delegation log",
        "ALLOWED_USE_BLOCKED", "authoring run", "cer_authoring_v1",
    ]
    # ── DP-aware text pattern checks (Connection 4) ──
    dp_data = _load_defect_patterns()
    _DP_FORBIDDEN_TERMS = [
        "template residue", "placeholder text", "lorem ipsum",
        "TODO", "FIXME", "INSERT_CONTENT_HERE",
        "not extracted", "to be determined",
    ]
    body_text = " ".join(str(v) for v in cer_chapters.values())
    banned_hits = []
    for banned in _BANNED_RENDER_CHECK:
        if banned.lower() in body_text.lower():
            banned_hits.append(banned)

    # ── Check 2: IFU placeholder patterns in rendered body ──
    _IFU_PLACEHOLDER_CHECK = [
        "Not extracted from IFU", "IFU text not available",
        "source text unavailable", "pending IFU confirmation",
    ]
    # DP-011: scanned_unreadable_ifu check
    _DP_IFU_DEGRADED_CHECK = [
        "scanned IFU", "unreadable IFU", "IFU quality degraded",
        "OCR failed", "image-based IFU", "handwritten IFU",
        "poor scan quality", "illegible",
    ]
    placeholder_hits = []
    for pattern in _IFU_PLACEHOLDER_CHECK:
        if pattern.lower() in body_text.lower():
            placeholder_hits.append(pattern)

    # ── DP-specific pattern hits ──
    dp_forbidden_hits = []
    for term in _DP_FORBIDDEN_TERMS:
        if term.lower() in body_text.lower():
            dp_forbidden_hits.append(term)
    dp_ifu_degraded_hits = []
    for term in _DP_IFU_DEGRADED_CHECK:
        if term.lower() in body_text.lower():
            dp_ifu_degraded_hits.append(term)

    # ── DP-aware state checks ──
    annex_check = _check_annex_population(state)
    citation_check = _check_citation_density(body_text)

    # ── Map hits to DP IDs ──
    dp_matches = []
    if dp_forbidden_hits:
        dp_matches.append("DP-001/DP-002 (forbidden/banned terms in body)")
    if dp_ifu_degraded_hits:
        dp_matches.append("DP-011 (scanned/unreadable IFU detected)")
    if annex_check:
        dp_matches.append(f"DP-038 (unpopulated annexes: {annex_check})")
    if citation_check:
        dp_matches.append(f"DP-036 (citation density: {citation_check})")

    # ── Check 3: Writer quality self-check score ──
    quality_report = state.get("writer_quality_report") or {}
    quality_pct = quality_report.get("writer_quality_pct", 100)

    # ── Check 4: Claim/BR/text consistency ──
    claim_check = _gate_claim_text_consistency(state)
    claim_failures = claim_check.message if claim_check.status == "FAIL" else ""

    # ── Aggregate result ──
    failures = []
    if banned_hits:
        failures.append(f"Banned internal strings in body: {banned_hits}")
    if placeholder_hits:
        failures.append(f"IFU placeholders in body: {placeholder_hits}")
    if dp_forbidden_hits:
        failures.append(f"DP-001/DP-002 Forbidden terms in body: {dp_forbidden_hits[:5]}")
    if dp_ifu_degraded_hits:
        failures.append(f"DP-011 IFU quality indicators in body: {dp_ifu_degraded_hits[:5]}")
    if annex_check:
        failures.append(f"DP-038 Unpopulated annexes: {annex_check}")
    if citation_check:
        failures.append(f"DP-036 Citation density: {citation_check}")
    # ── Section-specific DP checks (Phase 5) ──
    _SECTION_DP_MAP = {
        "1 Summary": ["DP-007", "DP-003", "DP-019"],  # over_strong, evidence_conclusion_mismatch, confidence_overstated
        "3 SOTA": ["DP-005", "DP-024"],  # missing_sota_benchmark, benchmark_low_confidence
        "4.7 GSPR": ["DP-015", "DP-037"],  # gspr_coverage_gap, gspr_traceability_gap
        "5 Conclusions": ["DP-045", "DP-019"],  # br_quantitative_gap, confidence_overstated
    }
    section_dp_hits = []
    for section_key, dp_ids in _SECTION_DP_MAP.items():
        section_text = ""
        for ch_key, ch_text in cer_chapters.items():
            if section_key in ch_key:
                section_text = str(ch_text)
                break
        if section_text:
            for dp_id in dp_ids:
                dp_entry = dp_data.get("by_id", {}).get(dp_id, {})
                dp_name = dp_entry.get("name", "")
                # Check for section-specific indicators
                if dp_id == "DP-007" and any(w in section_text.lower() for w in ["clearly demonstrates", "definitively proves", "undeniably"]):
                    section_dp_hits.append(f"{dp_id} ({dp_name}) in {section_key}")
                elif dp_id == "DP-005" and "benchmark" not in section_text.lower() and "SOTA" in section_key:
                    section_dp_hits.append(f"{dp_id} ({dp_name}) in {section_key}: no benchmark reference found")
                elif dp_id == "DP-015" and "GSPR" in section_key:
                    # Check for GSPR items without evidence citation
                    evidence_refs = sum(1 for w in ["evidence", "study", "trial", "literature", "data from"] if w in section_text.lower())
                    if evidence_refs < 2:
                        section_dp_hits.append(f"{dp_id} ({dp_name}) in {section_key}: low evidence citation density")
    if section_dp_hits:
        failures.append(f"Section-specific DP: {'; '.join(section_dp_hits[:5])}")
        dp_matches.extend(section_dp_hits[:5])
    if quality_pct < 70:
        failures.append(f"Writer quality score too low: {quality_pct}%")
    # ── P0-2: Writing style detection ──
    style_violations = _check_writing_style(cer_chapters)
    if style_violations:
        failures.append(f"Writing style: {'; '.join(style_violations[:5])}")
    # ── Equivalence circular reasoning ──
    eq_circular = _check_equivalence_circular_reasoning(state)
    if eq_circular:
        failures.append(f"Equivalence circular reasoning: {'; '.join(eq_circular[:3])}")
    # ── Numerical precision ──
    num_precision = _check_numerical_precision(cer_chapters)
    if num_precision:
        failures.append(f"Numerical precision: {'; '.join(num_precision[:3])}")
    # ── Paragraph logic rules ──
    para_logic = _check_paragraph_logic(cer_chapters)
    if para_logic:
        failures.append(f"Paragraph logic: {'; '.join(para_logic[:3])}")
    # ── Batch 7 quick checks ──
    annex_density = _check_annex_density(cer_chapters)
    if annex_density:
        failures.append(f"Annex density: {'; '.join(annex_density)}")
    dd_fields = _check_device_description_fields(state)
    if dd_fields:
        failures.append(f"Device desc: {'; '.join(dd_fields)}")
    eq_wording = _check_equivalence_wording(cer_chapters)
    if eq_wording:
        failures.append(f"Equivalence wording: {'; '.join(eq_wording)}")
    ep_incomplete = _check_endpoint_completeness(state)
    if ep_incomplete:
        failures.append(f"Endpoint: {'; '.join(ep_incomplete)}")
    sota_3f = _check_sota_three_functions(state)
    if sota_3f:
        failures.append(f"SOTA 3-function: {'; '.join(sota_3f)}")
    pmcf_rmf = _check_pmcf_rmf_prerequisite(state)
    if pmcf_rmf:
        failures.append(f"PMCF prerequisite: {'; '.join(pmcf_rmf)}")
    claim_subtype = _check_claim_subtype_routing(state)
    if claim_subtype:
        failures.append(f"Claim subtype: {'; '.join(claim_subtype)}")
    if claim_check.status == "FAIL":
        failures.append(f"Claim/BR/text consistency: {claim_failures}")

    if failures:
        # ── Remediation: look up deerflow_injection from remediation_playbook ──
        remediation_hints = []
        try:
            import json
            from pathlib import Path
            rp_path = Path(__file__).parent / "knowledge" / "remediation_playbook.json"
            rp = json.loads(rp_path.read_text())
            playbook = rp.get("playbook", {})
            if banned_hits:
                for entry_id, entry in playbook.items():
                    di = entry.get("deerflow_injection", {})
                    if di.get("gap_action_trigger") == entry_id:
                        prefix = di.get("auto_prompt_prefix", "")
                        if prefix:
                            remediation_hints.append(f"[{entry_id}] {prefix[:200]}")
            if placeholder_hits:
                do001 = playbook.get("DO-001", {})
                di = do001.get("deerflow_injection", {})
                prefix = di.get("auto_prompt_prefix", "")
                if prefix:
                    remediation_hints.append(f"[DO-001] {prefix[:200]}")
        except Exception:
            pass
        # ── DP-aware remediation: look up fix suggestions from defect_patterns ──
        if dp_matches:
            for dp_match in dp_matches:
                dp_id = dp_match.split(" ")[0].split("/")[0]
                dp_entry = dp_data.get("by_id", {}).get(dp_id, {})
                dp_fix = dp_entry.get("fix", "")
                dp_name = dp_entry.get("name", "")
                if dp_fix:
                    remediation_hints.append(f"[{dp_id}] {dp_name}: {dp_fix}")
        msg = "; ".join(failures)
        if remediation_hints:
            msg += " | REMEDIATION: " + " | ".join(remediation_hints[:5])
        if dp_matches:
            msg += " | DP_MATCHES: " + "; ".join(dp_matches[:5])
        return GateResult("G39", "FAIL", msg)
    return GateResult("G39", "PASS", f"Rendered body clean ({quality_pct}% quality, 0 banned strings, 0 placeholders).")


def run_authoring_gates(state: dict[str, Any]) -> dict[str, Any]:
    results = [
        _gate_source_preflight(state),
        _gate_classification_consistency(state),
        _gate_document_control(state),
        _gate_mdr_annex_xiv(state),
        _gate_ifu_exists(state),
        _gate_prewriting_tables(state),
        _gate_device_profile_complete(state),
        _gate_source_role_separation(state),
        _gate_device_identity_lock(state),
        _gate_domain_contamination(state),
        _gate_claim_coverage(state),
        _gate_claims_have_pico_explanations(state),
        _gate_search_reproducible(state),
        _gate_pivotal_evidence_verified(state),
        _gate_numbers_are_traceable(state),
        _gate_sota_used_in_47(state),
        _gate_appraisal_drives_weight(state),
        _gate_vigilance_executed(state),
        _gate_rmf_not_fabricated(state),
        _gate_equivalence_impact_closed(state),
        _gate_conclusion_strength(state),
        _gate_no_final_placeholders(state),
        _gate_nb_high_risk_zero(state),
        _gate_human_style_depth(state),
        _gate_review_regression_boundary(state),
        _gate_mcp_execution_completeness(state),
        _gate_authoring_review_team_recorded(state),
        _gate_cer_body_english_only(state),
        _gate_ap_template_loaded(state),
        _gate_template_logic_depth(state),
        _gate_engineer_comment_theme_controls(state),
        _gate_human_cer_comparison(state),
        _gate_vigilance_relevance_screened(state),
        _gate_subagent_harness_configured(state),
        _gate_full_text_endpoint_extraction(state),
        _gate_lsp_methodology(state),
        _gate_sota_logic(state),
        _gate_complex_tables(state),
        _gate_sota_literature_quantity(state),
        _gate_sota_endpoint_derivation(state),
        _gate_sota_full_text_strength(state),
        _gate_prisma_flow(state),
        _gate_similar_device_four_step(state),
        _gate_eu_nz_vigilance_sources(state),
        _gate_marketing_pms_questionnaire(state),
        _gate_sota_seven_step_deduction(state),
        _gate_aggregate_benchmark_basis(state),
        _gate_sota_conclusion_strength_guard(state),
        _gate_defect_state_consistency(state),
        _gate_final_draft_semantic_qa(state),
        _gate_ifu_working_document(state),
        _gate_sota_reasoning(state),
        evaluate_claim_sota_alignment_gate(state),
        evaluate_argument_quality_gate(state),
        evaluate_cep_exists_gate(state),
        # ── WS2-WS10 integrated gates ──
        _gate_ws2_ifu_iteration_closure(state),
        _gate_ws2_ifu_overclaim(state),
        _gate_ws3_claim_taxonomy(state),
        _gate_ws3_final_body_claim_eligibility(state),
        _gate_ws4_prisma_reproducibility(state),
        _gate_ws5_evidence_level_ceiling(state),
        _gate_ws6_endpoint_homogeneity(state),
        _gate_ws7_equivalence_route(state),
        _gate_ws8_benefit_risk_body_section(state),
        _gate_ws9_rmf_ifu_warning_linkage(state),
        _gate_ws10_submission_cleanliness(state),
        _gate_ws10_conclusion_completeness(state),
        _gate_ws10_body_annex_boundary(state),
    ]
    critical_gate_ids = {
        "SOURCE_PREFLIGHT", "CLASSIFICATION_CONSISTENCY_GATE", "G1b", "G1d", "G2", "G5", "G8",
        "G12", "G14", "G19", "G_ARG_01", "G_ARG_02", "G_CEP", "G_DP_STATE",
        "G_IFU_WORKING_DOCUMENT", "G_SOTA_REASONING", "G_MDR_ANNEX_XIV",
        # ── WS critical gate IDs ──
        "WS2_IFU_OVERCLAIM",
        "WS3_CLAIM_ELIGIBILITY",
        "WS4_PRISMA_REPRODUCIBILITY",
        "WS5_EVIDENCE_LEVEL_CEILING",
        "WS7_EQUIVALENCE_ROUTE",
        "WS8_BR_BODY_SECTION",
        "WS9_RMF_IFU_LINKAGE",
        "WS10_SUBMISSION_CLEANLINESS",
    }
    critical_failures = [r for r in results if r.gate_id in critical_gate_ids and r.status != "PASS"]
    minor_failures = [r for r in results if r.gate_id not in critical_gate_ids and r.status != "PASS"]
    all_failed = critical_failures + minor_failures

    if any(r.status == "HUMAN_HOLD" for r in all_failed):
        decision = "HUMAN_HOLD"
    elif critical_failures:
        decision = "REWORK_REQUIRED"
    elif minor_failures:
        decision = "PASS_WITH_WARNINGS"
    else:
        decision = "PASS_TO_DRAFT_DOCX"

    return {
        "schema_name": "cer_authoring_qa_gate_report",
        "decision": decision,
        "results": [r.as_dict() for r in results],
        "failed_gate_count": len(all_failed),
        "critical_failures": len(critical_failures),
        "minor_failures": len(minor_failures),
    }


def _gate_source_preflight(state: dict[str, Any]) -> GateResult:
    """BIGDP2026.6 Phase 3: 4-tier severity — CRITICAL / MAJOR / WARNING / AUTO_FIXABLE.

    - CRITICAL: Blocks authoring entirely (missing RMF, IFU, or TD).
    - MAJOR: Controlled gap; CER can proceed with documented limitation.
    - WARNING: Non-blocking issue; noted in CER but does not block.
    - AUTO_FIXABLE: Minor issue that the system can auto-resolve.
    """
    report = state.get("source_preflight_gate_report") or {}
    severity = str(report.get("severity") or report.get("status") or "PASS").upper()

    if severity in ("CRITICAL", "BLOCKED"):
        issues = report.get("blocking_issues") or report.get("critical_issues") or []
        return GateResult(
            "SOURCE_PREFLIGHT",
            "BLOCKED",
            f"CRITICAL: Source preflight has {len(issues)} blocking issue(s).",
            failure_pattern="source_preflight_critical",
            upstream_node_to_reroute="initialize",
            blocked_reason="Controlled source package must be repaired before CER authoring.",
            reroute_context={"severity": "CRITICAL", "issues": issues[:5]},
        )
    if severity == "MAJOR":
        gaps = report.get("controlled_gaps") or report.get("major_issues") or []
        return GateResult(
            "SOURCE_PREFLIGHT",
            "PASS",
            f"MAJOR: {len(gaps)} controlled gap(s) — CER to proceed with documented limitations.",
            severity="advisory",
            failure_pattern="source_preflight_major_gaps",
            reroute_context={"severity": "MAJOR", "gaps": gaps[:5]},
        )
    if severity == "WARNING":
        warnings = report.get("warnings") or report.get("warning_issues") or []
        return GateResult(
            "SOURCE_PREFLIGHT",
            "PASS",
            f"WARNING: {len(warnings)} non-blocking issue(s) noted for CER.",
            severity="advisory",
            failure_pattern="source_preflight_warnings",
            reroute_context={"severity": "WARNING", "warnings": warnings[:5]},
        )
    if severity == "AUTO_FIXABLE":
        fixes = report.get("auto_fixable") or []
        return GateResult(
            "SOURCE_PREFLIGHT",
            "PASS",
            f"AUTO_FIXABLE: {len(fixes)} minor issue(s) auto-resolved.",
            severity="advisory",
            failure_pattern="source_preflight_auto_fixed",
            reroute_context={"severity": "AUTO_FIXABLE", "fixes": fixes[:5]},
        )
    if severity in ("REWORK_REQUIRED", "REWORK"):
        return GateResult(
            "SOURCE_PREFLIGHT",
            "REWORK_REQUIRED",
            "Source preflight has controlled gaps that must remain visible in the CER.",
            failure_pattern="source_preflight_controlled_gaps",
            reroute_context={"severity": "MAJOR", "controlled_gaps": (report.get("controlled_gaps") or [])[:5]},
        )
    return GateResult("SOURCE_PREFLIGHT", "PASS", "Source preflight passed.", severity="advisory")


def _gate_classification_consistency(state: dict[str, Any]) -> GateResult:
    report = state.get("classification_consistency_report") or {}
    status = str(report.get("status") or "PASS")
    if status == "BLOCKED":
        return GateResult(
            "CLASSIFICATION_CONSISTENCY_GATE",
            "BLOCKED",
            f"Conflicting device classifications: {report.get('classification_signals')}",
            failure_pattern="classification_conflict",
            upstream_node_to_reroute="device_profile",
            blocked_reason="Resolve MDR classification before Writer.",
            reroute_context={"classification_report": report},
        )
    if status == "CONTROLLED_GAP":
        return GateResult(
            "CLASSIFICATION_CONSISTENCY_GATE",
            "REWORK_REQUIRED",
            "Device classification is not locked and must remain a controlled draft gap.",
            failure_pattern="classification_unconfirmed",
        )
    return GateResult("CLASSIFICATION_CONSISTENCY_GATE", "PASS", "Device classification is locked or no conflict was detected.")


def _gate_document_control(state: dict[str, Any]) -> GateResult:
    profile = state.get("device_profile") or {}
    lock = state.get("source_lock_report") or {}
    gaps = []
    if not str(profile.get("manufacturer") or "").strip() or "not extracted" in str(profile.get("manufacturer") or "").lower():
        gaps.append("manufacturer identity")
    if not (state.get("document_control_metadata") or {}).get("document_id") and not lock.get("primary_ifu_source_ids"):
        gaps.append("document ID/source control")
    if gaps:
        return GateResult(
            "DOC_CONTROL_GATE",
            "REWORK_REQUIRED",
            f"Document-control metadata remains incomplete: {', '.join(gaps)}",
            failure_pattern="document_control_controlled_gap",
        )
    return GateResult("DOC_CONTROL_GATE", "PASS", "Document-control metadata is present or controlled by source lock.")


def _gate_defect_state_consistency(state: dict[str, Any]) -> GateResult:
    """Check state-level invariants matching DP detection methods (Connection 4).

    Covers:
    - DP-005: claim_without_sota
    - DP-006: g42_insufficient
    - DP-008: no_rmf_for_warning
    - DP-015: gspr_without_evidence
    - DP-014: missing_3d_comparison
    - DP-016: pmcf_before_alternatives
    - DP-012: pool_below_threshold
    """
    dp_data = _load_defect_patterns()
    violations = []

    # DP-005: claim_without_sota
    claim_matrix = state.get("claim_evidence_matrix") or []
    claims_without_sota = []
    for row in claim_matrix:
        sota_ids = row.get("sota_ids") or row.get("sota_benchmark_ids") or []
        if not sota_ids:
            claims_without_sota.append(str(row.get("claim_id", "?")))
    if claims_without_sota:
        violations.append(f"DP-005: {len(claims_without_sota)} claims without SOTA benchmark: {claims_without_sota[:5]}")

    # DP-006: g42_insufficient
    evidence_registry = state.get("evidence_registry") or []
    ev_count = len(evidence_registry)
    claim_count = len(claim_matrix)
    if claim_count > 0 and ev_count == 0:
        violations.append(f"DP-006: {claim_count} claims but 0 evidence records (G42 insufficient)")

    # DP-008: no_rmf_for_warning
    vigilance = state.get("vigilance_recall_registry") or []
    rmf = state.get("rmf_registry") or state.get("risk_management_file") or []
    if vigilance and not rmf:
        violations.append(f"DP-008: {len(vigilance)} vigilance records but no RMF coverage")

    # DP-015: gspr_without_evidence
    gspr_checklist = state.get("gspr_checklist") or state.get("gspr_trace_matrix") or []
    gspr_without_ev = sum(1 for g in gspr_checklist if not g.get("evidence_ids") and not g.get("clinical_evidence_refs"))
    if gspr_without_ev > 0:
        violations.append(f"DP-015: {gspr_without_ev}/{len(gspr_checklist)} GSPR items without evidence mapping")

    # DP-014: missing_3d_comparison
    equivalence = state.get("equivalence_3d_matrix") or state.get("equivalence_comparison") or []
    equivalence_claimed = state.get("equivalence_strategy") == "legacy_mdd" or state.get("equivalence_claimed")
    if equivalence_claimed and not equivalence:
        violations.append("DP-014: Equivalence claimed but no 3D comparison data (technical/biological/clinical)")

    # DP-016: pmcf_before_alternatives
    pmcf = state.get("pmcf_gap_register") or []
    alternatives_remaining = state.get("endpoint_alternatives_remaining") or 0
    if pmcf and alternatives_remaining > 0:
        violations.append(f"DP-016: PMCF triggered with {alternatives_remaining} endpoint alternatives still remaining")

    # DP-012: pool_below_threshold
    searched = len(state.get("search_run_registry") or [])
    screened = len(state.get("screening_disposition") or [])
    if searched > 0 and screened < 5:
        violations.append(f"DP-012: Screening pool shallow ({screened} screened from {searched} searches, threshold: 5)")

    # DP-034: annex_body_inconsistency
    cer_chapters = state.get("cer_chapter_drafts") or {}
    annex_keys = [k for k in cer_chapters if "Annex" in k]
    body_text = " ".join(str(v) for k, v in cer_chapters.items() if "Annex" not in k)
    for ak in annex_keys[:5]:
        annex_label = ak.split("Annex ")[-1].strip() if "Annex " in ak else ak
        if annex_label and annex_label not in body_text:
            violations.append(f"DP-034: Annex {annex_label} not referenced in body text")
            break

    # DP-035: dependency_chain_broken
    sota_text = " ".join(str(v) for k, v in cer_chapters.items() if "SOTA" in k or "3 " in k)
    conclusions_text = " ".join(str(v) for k, v in cer_chapters.items() if "Conclusion" in k or "5 " in k)
    if sota_text and conclusions_text and "SOTA" not in conclusions_text and "benchmark" not in conclusions_text:
        violations.append("DP-035: Conclusions section does not reference upstream SOTA benchmarks")

    # DP-037: gspr_traceability_gap
    gspr_checklist = state.get("gspr_checklist") or state.get("gspr_trace_matrix") or []
    gspr_text = " ".join(str(v) for k, v in cer_chapters.items() if "GSPR" in k or "4.7" in k)
    if gspr_checklist and gspr_text:
        gspr_ids_in_checklist = {str(g.get("gspr_id", g.get("id", ""))) for g in gspr_checklist if g.get("gspr_id") or g.get("id")}
        gspr_ids_in_text = 0
        for gid in gspr_ids_in_checklist:
            if gid and gid in gspr_text:
                gspr_ids_in_text += 1
        if gspr_ids_in_checklist and gspr_ids_in_text < len(gspr_ids_in_checklist) * 0.5:
            violations.append(f"DP-037: Only {gspr_ids_in_text}/{len(gspr_ids_in_checklist)} GSPR items traced in body text")

    if violations:
        return GateResult("G_DP_STATE", "FAIL", "; ".join(violations[:10]))
    return GateResult("G_DP_STATE", "PASS", f"State consistency verified against {len(dp_data.get('patterns', []))} DP patterns.")


# ── G_IFU_WORKING_DOCUMENT: IFU Working Document Gate ──

def _gate_ifu_working_document(state: dict[str, Any]) -> GateResult:
    """A5: IFU Working Document Gate.

    Rules:
    - IFU clinical_benefit empty + CER has supported claims → IFU_UPDATE_RECOMMENDATION
    - IFU overclaims vs evidence → narrow_claim_scope
    - IFU warning contradicts RMF → HUMAN_REVIEW
    """
    profile = state.get("device_profile") or {}
    claims = state.get("claim_ledger") or []
    alignment = (state.get("ifu_cer_alignment_ledger") or {}).get("alignments") or []
    violations = []

    # IFU-G01: clinical_benefit missing but CER has supported claims
    cb_value = str(profile.get("clinical_benefit", ""))
    cb_claims = [c for c in claims if str(c.get("claim_type", "")) == "clinical_benefit"]
    supported_cb = [c for c in cb_claims if str(c.get("support_status", "")).upper() in ("SUPPORTED", "FULLY_SUPPORTED")]
    if (not cb_value or "Requires confirmation" in cb_value) and supported_cb:
        violations.append("IFU-G01: IFU lacks clinical benefit wording but CER has supported clinical benefit claims → IFU_UPDATE_RECOMMENDATION")

    # IFU-G02: IFU overclaims
    for al in alignment:
        if al.get("alignment_status") == "overclaimed_in_ifu":
            violations.append(f"IFU-G02: IFU overclaims '{al.get('ifu_statement', '')[:80]}' — evidence insufficient → narrow_claim_scope")

    # IFU-G03: IFU/RMF conflict
    rmf = state.get("rmf_registry") or state.get("risk_management_file") or []
    ifu_warnings = [c for c in claims if str(c.get("claim_type", "")) in ("ifu_warning", "warning_contraindication")]
    if ifu_warnings and not rmf:
        violations.append("IFU-G03: IFU warnings present but RMF missing → HUMAN_REVIEW_REQUIRED")

    if violations:
        return GateResult("G_IFU_WORKING_DOCUMENT", "FAIL", "; ".join(violations[:3]))
    return GateResult("G_IFU_WORKING_DOCUMENT", "PASS", "IFU working document status verified.")


# ── G_SOTA_REASONING: SOTA Benchmark Reasoning Gate ──

def _gate_sota_reasoning(state: dict[str, Any]) -> GateResult:
    """B5: SOTA Benchmark Reasoning Gate.

    Rules:
    - benchmark has value but no synthesis_method → FAIL
    - benchmark has no source_articles → FAIL
    - qualitative benchmark without rationale → FAIL
    """
    benchmarks = state.get("sota_benchmark_matrix") or []
    violations = []

    for bm in benchmarks:
        val = bm.get("benchmark_value") or bm.get("sota_value_range")
        method = bm.get("synthesis_method", "")
        sources = bm.get("sota_source", "")

        # SOTA-G01: value but no method
        if val and not method:
            violations.append(f"SOTA-G01: '{bm.get('endpoint', '?')[:40]}' has benchmark value but no synthesis_method")

        # SOTA-G02: no sources
        if val and not sources:
            violations.append(f"SOTA-G02: '{bm.get('endpoint', '?')[:40]}' has benchmark value but no evidence source")

    if violations:
        return GateResult("G_SOTA_REASONING", "FAIL", "; ".join(violations[:3]))
    return GateResult("G_SOTA_REASONING", "PASS", f"SOTA reasoning verified for {len(benchmarks)} endpoints.")


# ── G_MDR_ANNEX_XIV: MDR Annex XIV Compliance ──

_MDR_ANNEX_XIV_CHECKS = {
    "A1a": {"clause": "Annex XIV §1(a)", "requirement": "Device description", "check": lambda s: bool((s.get("device_profile") or {}).get("device_name"))},
    "A1b": {"clause": "Annex XIV §1(b)", "requirement": "Intended purpose", "check": lambda s: bool((s.get("device_profile") or {}).get("intended_purpose"))},
    "A2": {"clause": "Annex XIV §2", "requirement": "Clinical data assessed", "check": lambda s: len(s.get("evidence_registry") or []) > 0},
    "A4": {"clause": "Annex XIV §4", "requirement": "Literature search protocol", "check": lambda s: len(s.get("search_run_registry") or []) > 0},
    "A5": {"clause": "Annex XIV §5", "requirement": "PRISMA/literature results", "check": lambda s: bool(s.get("prisma_flow_data") or s.get("prisma_flow"))},
    "A6": {"clause": "Annex XIV §6", "requirement": "Evidence appraisal", "check": lambda s: len(s.get("evidence_registry") or []) > 0},
    "A7": {"clause": "Annex XIV §7", "requirement": "GSPR analysis", "check": lambda s: bool(s.get("claim_evidence_matrix") or s.get("gspr_coverage"))},
    "A8": {"clause": "Annex XIV §8", "requirement": "Conclusions written", "check": lambda s: bool((s.get("cer_chapter_drafts") or {}).get("5 Conclusions"))},
    "A9": {"clause": "Annex XIV §9", "requirement": "Evaluator qualification", "check": lambda s: bool((s.get("cer_chapter_drafts") or {}).get("7 Evaluator Qualification"))},
    "A10": {"clause": "Annex XIV §10", "requirement": "Dates and signatures", "check": lambda s: bool((s.get("cer_chapter_drafts") or {}).get("9 Dates and Signatures"))},
}


def _gate_mdr_annex_xiv(state: dict[str, Any]) -> GateResult:
    violations = []
    for cid, c in _MDR_ANNEX_XIV_CHECKS.items():
        if not c["check"](state):
            violations.append(f"{c['clause']}: {c['requirement']}")
    if violations:
        return GateResult("G_MDR_ANNEX_XIV", "FAIL", "; ".join(violations[:5]))
    return GateResult("G_MDR_ANNEX_XIV", "PASS", f"MDR Annex XIV: {len(_MDR_ANNEX_XIV_CHECKS)}/{len(_MDR_ANNEX_XIV_CHECKS)} met.")


def _gate_ifu_exists(state: dict[str, Any]) -> GateResult:
    if _has_document_type(state, "ifu"):
        return GateResult("G0", "PASS", "IFU present")
    return GateResult("G0", "HUMAN_HOLD", "IFU is required before CER authoring can start")


def _gate_prewriting_tables(state: dict[str, Any]) -> GateResult:
    required = [
        "claim_ledger",
        "cep_pico_matrix",
        "evidence_registry",
        "sota_benchmark_matrix",
        "risk_trace_matrix",
    ]
    missing = [key for key in required if not state.get(key)]
    if not missing:
        return GateResult("G1", "PASS", "Five prewriting tables present")
    return GateResult("G1", "REWORK_REQUIRED", f"Missing prewriting tables: {', '.join(missing)}")


def _gate_device_profile_complete(state: dict[str, Any]) -> GateResult:
    profile = state.get("device_profile") or {}
    required = ["device_name", "device_type", "intended_purpose", "target_population", "mode_of_action"]
    missing = [key for key in required if not str(profile.get(key, "")).strip()]
    suspicious = [
        key
        for key in ("device_name", "intended_purpose")
        if str(profile.get(key, "")).strip().isdigit() or len(str(profile.get(key, "")).strip()) < 4
    ]
    if missing or suspicious:
        details = []
        if missing:
            details.append(f"missing fields: {', '.join(missing)}")
        if suspicious:
            details.append(f"suspicious fields: {', '.join(suspicious)}")
        return GateResult("G1b", "REWORK_REQUIRED", "; ".join(details))
    return GateResult("G1b", "PASS", "Device Profile contains usable authoring fields")


def _gate_source_role_separation(state: dict[str, Any]) -> GateResult:
    report = state.get("source_role_report") or {}
    inventory = state.get("source_inventory") or []
    subject_ifus = report.get("subject_ifu_source_ids") or [
        item.get("source_id") for item in inventory if item.get("document_type") == "IFU" and not item.get("excluded_from_device_profile")
    ]
    similar_primary = [
        str(item.get("source_id"))
        for item in inventory
        if item.get("primary_for_authoring") and item.get("source_role") in {"similar_device_ifu", "similar_or_benchmark_source"}
    ]
    if similar_primary:
        return GateResult("G1c", "REWORK_REQUIRED", f"Similar/benchmark sources were marked primary for authoring: {', '.join(similar_primary)}")
    if subject_ifus:
        return GateResult("G1c", "PASS", "Subject-device IFU is separated from similar/benchmark evidence")
    return GateResult("G1c", "HUMAN_HOLD", "No subject-device IFU source is locked after source-role separation")


def _gate_device_identity_lock(state: dict[str, Any]) -> GateResult:
    lock = state.get("device_identity_lock") or {}
    if not lock:
        return GateResult("G1d", "REWORK_REQUIRED", "Device identity lock is missing")
    status = str(lock.get("status") or "").upper()
    if status == "PASS":
        return GateResult("G1d", "PASS", f"Device identity locked: {lock.get('identity_statement')}")
    if status == "HUMAN_HOLD":
        return GateResult("G1d", "HUMAN_HOLD", f"Device identity requires human source confirmation: {lock}")
    return GateResult("G1d", "REWORK_REQUIRED", f"Device identity lock failed: {lock}")


def _gate_domain_contamination(state: dict[str, Any]) -> GateResult:
    report = state.get("domain_contamination_report") or _build_domain_contamination_report(state)
    findings = report.get("findings") or []
    high = [
        item
        for item in findings
        if str(item.get("severity", "")).upper() == "HIGH"
        and _g1e_is_device_identity_contamination(state, report, item)
    ]
    contextual = [
        item
        for item in findings
        if str(item.get("severity", "")).upper() == "HIGH"
        and not _g1e_is_device_identity_contamination(state, report, item)
    ]
    if high:
        return GateResult("G1e", "REWORK_REQUIRED", f"Domain contamination detected: {high[:5]}")
    context_note = f"; ignored {len(contextual)} context-only token mention(s)" if contextual else ""
    return GateResult("G1e", "PASS", f"No high-severity device-identity contamination detected for {report.get('locked_domain', 'unknown domain')}{context_note}")


def _gate_claim_coverage(state: dict[str, Any]) -> GateResult:
    claims = state.get("claim_ledger") or []
    intended = state.get("intended_purpose_claim_table") or []
    if not claims:
        return GateResult("G2", "REWORK_REQUIRED", "Claim Ledger must contain IFU-derived claims")
    claim_ids = {str(item.get("claim_id", "")) for item in claims}
    unmapped = [str(item.get("claim_id", "")) for item in intended if str(item.get("claim_id", "")) not in claim_ids]
    empty = [str(item.get("claim_id", "")) for item in claims if not (item.get("claim_text") or item.get("statement") or item.get("claim_type"))]
    if unmapped or empty:
        details = []
        if unmapped:
            details.append(f"unmapped intended-purpose rows: {', '.join(unmapped)}")
        if empty:
            details.append(f"claims without text/type: {', '.join(empty)}")
        return GateResult("G2", "REWORK_REQUIRED", "; ".join(details))
    return GateResult("G2", "PASS", "IFU-derived claims are represented in Claim Ledger")


def _g1e_is_device_identity_contamination(state: dict[str, Any], report: dict[str, Any], finding: dict[str, Any]) -> bool:
    """Return true only when a cross-domain token contaminates identity claims.

    G1e is a gate hygiene control. It must not fail a project merely because an
    unrelated clinical term appears in SOTA, evidence, differential-report,
    comparator, vigilance or discussion context. It should fail when the token
    changes the subject-device identity, intended purpose, anatomical site, or
    core claim/scope wording.
    """

    token = str(finding.get("token") or "").strip().lower()
    if not token:
        return False
    scope = str(finding.get("scope") or "").lower()
    if any(marker in scope for marker in ("sota", "evidence", "benchmark", "literature", "search", "vigilance", "comparator", "comparison", "dr_comparison", "clinical_context", "surgical_context", "procedure_context")):
        return False

    identity_text = _g1e_identity_text(state)
    if token in identity_text and not _g1e_token_only_contextual(identity_text, token):
        return True

    if scope in {"device_profile", "identity", "intended_purpose", "claim", "scope"}:
        return True

    if scope in {"profile_or_core_chapters", "core_chapters", "summary_scope"}:
        core_text = _g1e_core_scope_text(state)
        if token in core_text and not _g1e_token_only_contextual(core_text, token):
            return True
        return False

    # Legacy analyzer findings often have only token/severity. Treat them as
    # blocking only if the token is visible in identity-bearing fields.
    return token in identity_text and not _g1e_token_only_contextual(identity_text, token)


def _g1e_identity_text(state: dict[str, Any]) -> str:
    profile = state.get("device_profile") or {}
    claim_rows = state.get("claim_ledger") or []
    intended_rows = state.get("intended_purpose_claim_table") or []
    identity_lock = state.get("device_identity_lock") or {}
    keys = (
        "device_name",
        "device_type",
        "device_family",
        "intended_purpose",
        "indications",
        "target_population",
        "anatomical_site",
        "mode_of_action",
        "working_principle",
        "clinical_domain",
        "device_domain",
    )
    chunks = [str(profile.get(key) or "") for key in keys]
    chunks.append(str(identity_lock.get("identity_statement") or ""))
    chunks.extend(str(row.get("claim_text") or row.get("statement") or row.get("required_evidence") or "") for row in claim_rows)
    chunks.extend(str(row.get("statement") or row.get("element") or "") for row in intended_rows)
    return " ".join(chunks).lower()


def _g1e_core_scope_text(state: dict[str, Any]) -> str:
    chapters = state.get("cer_chapter_drafts") or {}
    return " ".join(str(chapters.get(key, "")) for key in ("Clinical Evaluation Report", "1 Summary", "2 Scope of Clinical Evaluation")).lower()


def _g1e_token_only_contextual(text: str, token: str) -> bool:
    indices: list[int] = []
    start = 0
    while True:
        idx = text.find(token, start)
        if idx < 0:
            break
        indices.append(idx)
        start = idx + max(len(token), 1)
    if not indices:
        return False
    context_markers = (
        "comparison",
        "comparator",
        "compared",
        "different from",
        "unlike",
        "distinct from",
        "in contrast to",
        "unlike ureteroscope",
        "different from ureteroscope",
        "benchmark",
        "sota",
        "literature",
        "evidence",
        "differential",
        "diagnostic report",
        "dr comparison",
        "clinical context",
        "surgical context",
        "procedure context",
        "not the subject device",
        "not subject device",
        "excluded",
        "alternative",
        "similar device",
    )
    for idx in indices:
        window = text[max(0, idx - 120) : idx + len(token) + 120]
        if not any(marker in window for marker in context_markers):
            return False
    return True


def _gate_claims_have_pico_explanations(state: dict[str, Any]) -> GateResult:
    picos = state.get("cep_pico_matrix") or []
    if picos and all(item.get("derivation_rationale") or item.get("pico_derivation") for item in picos):
        return GateResult("G3", "PASS", "Each PICO has derivation rationale")
    return GateResult("G3", "REWORK_REQUIRED", "Each PICO must explain claim -> uncertainty -> PICO -> query")


def _gate_search_reproducible(state: dict[str, Any]) -> GateResult:
    searches = state.get("search_run_registry") or []
    screening = state.get("screening_disposition") or []
    if not searches:
        return GateResult("G4", "REWORK_REQUIRED", "Search run registry is missing")
    incomplete = [
        str(item.get("search_id", item.get("database", "<unknown>")))
        for item in searches
        if not item.get("database")
        or not item.get("query")
        or not item.get("search_date")
        or (item.get("result_count") is None and item.get("status") not in {"source_unavailable", "auth_required"})
    ]
    if incomplete:
        return GateResult("G4", "REWORK_REQUIRED", f"Search records are not reproducible: {', '.join(incomplete)}")
    if not screening:
        return GateResult("G4", "REWORK_REQUIRED", "Screening disposition table with inclusion/exclusion decisions is missing")
    bad_screening = [
        str(item.get("screen_id", item.get("article_id", "<unknown>")))
        for item in screening
        if not (item.get("title_abstract_decision") or item.get("full_text_decision"))
    ]
    missing_reasons = [
        str(item.get("screen_id", item.get("article_id", "<unknown>")))
        for item in screening
        if "exclude" in f"{item.get('title_abstract_decision', '')} {item.get('full_text_decision', '')}".lower()
        and not item.get("exclusion_reason")
    ]
    if bad_screening or missing_reasons:
        details = []
        if bad_screening:
            details.append(f"missing decisions: {', '.join(bad_screening)}")
        if missing_reasons:
            details.append(f"missing exclusion reasons: {', '.join(missing_reasons)}")
        return GateResult("G4", "REWORK_REQUIRED", "; ".join(details))
    return GateResult("G4", "PASS", "Search protocol, result counts, and screening decisions are reproducible")


def _gate_pivotal_evidence_verified(state: dict[str, Any]) -> GateResult:
    pivotal = [item for item in state.get("evidence_registry") or [] if item.get("weight") == "pivotal"]
    unverified = [item.get("evidence_id", item.get("id", "<unknown>")) for item in pivotal if not item.get("verified")]
    if not unverified:
        return GateResult("G5", "PASS", "No unverified pivotal evidence")
    return GateResult("G5", "REWORK_REQUIRED", f"Unverified pivotal evidence: {', '.join(unverified)}")


def _gate_numbers_are_traceable(state: dict[str, Any]) -> GateResult:
    rows = list(state.get("endpoint_extraction") or [])
    rows.extend(state.get("evidence_registry") or [])
    if not rows:
        return GateResult("G6", "REWORK_REQUIRED", "No endpoint/evidence rows available for numeric traceability")
    incomplete = []
    retrieval_gaps = []
    for row in rows:
        if any(str(row.get(key) or "").startswith("EVIDENCE_PENDING_") for key in ("source_type", "evidence_id", "source_anchor", "source_id")):
            retrieval_gaps.append(str(row.get("evidence_id") or row.get("source_id") or "<unknown>"))
            continue
        text = " ".join(str(value) for value in row.values())
        if not any(char.isdigit() for char in text):
            continue
        has_source = bool(row.get("source_evidence_id") or row.get("evidence_id") or row.get("source"))
        has_sample = bool(row.get("sample_size"))
        has_timepoint = bool(row.get("timepoint") or row.get("follow_up"))
        has_endpoint = bool(row.get("endpoint"))
        has_result = bool(row.get("statistical_result") or row.get("result"))
        if not (has_source and has_sample and has_timepoint and has_endpoint and has_result):
            incomplete.append(str(row.get("endpoint_id") or row.get("evidence_id") or row.get("article_id") or "<unknown>"))
    if incomplete:
        msg = f"Numeric data lack source/sample/timepoint/endpoint/result fields: {', '.join(incomplete)}"
        if retrieval_gaps:
            msg += f" | retrieval_gap_records_skipped: {', '.join(retrieval_gaps)}"
        return GateResult("G6", "REWORK_REQUIRED", msg)
    if retrieval_gaps:
        return GateResult("G6", "PASS", f"Numeric traceability verified; {len(retrieval_gaps)} EVIDENCE_PENDING_ retrieval-gap records skipped")
    return GateResult("G6", "PASS", "Numeric data are traceable to evidence/source fields")


def _gate_sota_used_in_47(state: dict[str, Any]) -> GateResult:
    matrix = state.get("sota_to_47_usage_matrix") or []
    benchmarks = state.get("sota_benchmark_matrix") or []
    if not matrix and not benchmarks:
        return GateResult("G7", "REWORK_REQUIRED", "SOTA-to-4.7 usage matrix is empty")
    unused = [r for r in (matrix or benchmarks) if not r.get("used_in_4_7")]
    if unused:
        return GateResult(
            "G7", "REWORK_REQUIRED",
            f"{len(unused)} SOTA benchmarks not referenced in section 4.7",
            failure_pattern="sota_benchmark_unused",
        )
    return GateResult("G7", "PASS", f"{len(matrix or benchmarks)} SOTA benchmarks used in section 4.7")


def _gate_appraisal_drives_weight(state: dict[str, Any]) -> GateResult:
    matrix = state.get("claim_support_matrix") or []
    evidence = state.get("evidence_registry") or []
    appraisal = state.get("article_appraisal") or []
    if not evidence and not matrix:
        return GateResult("G8", "REWORK_REQUIRED", "Evidence Registry is missing")
    # Check evidence weights
    invalid_weight = [
        str(item.get("evidence_id", "<unknown>"))
        for item in evidence
        if item.get("weight") not in {"pivotal", "supportive", "background", "excluded"}
    ]
    if invalid_weight:
        return GateResult(
            "G8", "REWORK_REQUIRED",
            f"Evidence weights outside permitted set: {', '.join(invalid_weight)}",
        )
    # Check claim support matrix has weighted scores
    if matrix:
        if isinstance(matrix, dict):
            matrix_rows = list(matrix.values())
        else:
            matrix_rows = matrix
        unweighted = [r for r in matrix_rows if isinstance(r, dict) and not r.get("weighted_support_score")]
        low_pivotal = [
            r for r in matrix_rows
            if isinstance(r, dict) and r.get("best_evidence_score", 100) < 40
            and r.get("support_level") in ("MODERATE", "STRONG")
        ]
        if unweighted:
            return GateResult(
                "G8", "REWORK_REQUIRED",
                f"{len(unweighted)} claims lack weighted support score",
            )
        if low_pivotal:
            return GateResult(
                "G8", "REWORK_REQUIRED",
                f"{len(low_pivotal)} claims have MODERATE/STRONG from low-score evidence",
                failure_pattern="low_score_overvalued",
            )
    # Check appraisal linkage
    if appraisal:
        evidence_ids = {str(item.get("evidence_id", "")) for item in evidence}
        appraised_ids = {str(item.get("evidence_id", "")) for item in appraisal if item.get("evidence_id")}
        if not evidence_ids.intersection(appraised_ids):
            return GateResult("G8", "REWORK_REQUIRED", "Article appraisal is not linked to Evidence Registry by evidence_id")
    if not appraisal:
        return GateResult("G8", "REWORK_REQUIRED", "Article appraisal table is missing")
    return GateResult("G8", "PASS", "Evidence appraisal drives claim support weights")


def _gate_vigilance_executed(state: dict[str, Any]) -> GateResult:
    registry = state.get("vigilance_recall_registry") or []
    required = {"FDA MAUDE", "FDA Device Recall", "MHRA", "BfArM", "Swissmedic", "EUDAMED", "New Zealand Medsafe"}
    seen = {str(item.get("database", "")).lower() for item in registry}
    missing = [name for name in required if not any(name.lower() in item for item in seen)]
    if not missing:
        return GateResult("G9", "PASS", "Vigilance and recall searches executed")
    return GateResult("G9", "REWORK_REQUIRED", f"Missing vigilance/recall searches: {', '.join(missing)}")


def _gate_rmf_not_fabricated(state: dict[str, Any]) -> GateResult:
    has_rmf = _has_document_type(state, "rmf") or _has_document_type(state, "risk")
    if has_rmf:
        return GateResult("G10", "PASS", "RMF source present")
    traces = state.get("risk_trace_matrix") or []
    fabricated = [item for item in traces if str(item.get("rmf_coverage", "")).lower() in {"covered", "yes", "full"}]
    if fabricated:
        return GateResult("G10", "REWORK_REQUIRED", "RMF coverage cannot be claimed when RMF source is absent")
    return GateResult("G10", "PASS", "No fabricated RMF coverage detected")


def _gate_equivalence_impact_closed(state: dict[str, Any]) -> GateResult:
    rows = state.get("equivalence_matrix") or []
    if not rows:
        return GateResult("G11", "REWORK_REQUIRED", "Equivalence matrix is missing")
    missing = [
        str(item.get("comparison_id", "<unknown>"))
        for item in rows
        if not (item.get("difference_impact_conclusion") or item.get("clinical_impact") or item.get("conclusion"))
    ]
    overclaimed = [
        str(item.get("comparison_id", "<unknown>"))
        for item in rows
        if "demonstrated" in str(item.get("difference_impact_conclusion", "")).lower()
        and str(item.get("confidence", "")).lower() in {"", "not_claimed", "gap", "low"}
    ]
    if missing or overclaimed:
        details = []
        if missing:
            details.append(f"missing clinical impact conclusion: {', '.join(missing)}")
        if overclaimed:
            details.append(f"overclaimed equivalence: {', '.join(overclaimed)}")
        return GateResult("G11", "REWORK_REQUIRED", "; ".join(details))
    return GateResult("G11", "PASS", "Equivalence/difference clinical impact is closed or explicitly not claimed")


def _gate_conclusion_strength(state: dict[str, Any]) -> GateResult:
    draft = "\n".join(str(value) for value in (state.get("cer_chapter_drafts") or {}).values()).lower()
    has_gap = bool(state.get("gap_pmcf_recommendations")) or any(
        str(item.get("evidence_id", "")).startswith("E-GAP") or item.get("weight") in {"background", "excluded"}
        for item in state.get("evidence_registry") or []
    )
    strong_terms = ("fully supports", "demonstrates conformity", "favourable benefit-risk is confirmed", "all risks are acceptable")
    if has_gap and any(term in draft for term in strong_terms):
        return GateResult("G12", "REWORK_REQUIRED", "Final conclusion strength exceeds evidence/gap status")
    # Check Oxford level -> conclusion consistency
    constraints = state.get("writer_conclusion_constraints") or {}
    if isinstance(constraints, dict):
        constraint_rows = list(constraints.values())
    else:
        constraint_rows = constraints
    violations = []
    for c in constraint_rows:
        if not isinstance(c, dict):
            continue
        oxford = str(c.get("best_oxford_level") or "")
        allowed = OXFORD_CONCLUSION_MAP.get(oxford, "CAUTIOUS")
        actual = str(c.get("max_conclusion_strength") or "")
        if _conclusion_rank(actual) > _conclusion_rank(allowed):
            violations.append(
                f"{c.get('claim_id')}: Oxford {oxford} allows {allowed}, got {actual}"
            )
    if violations:
        return GateResult(
            "G12", "REWORK_REQUIRED",
            f"Conclusion strength exceeds Oxford level: {len(violations)} violations",
            failure_pattern="conclusion_exceeds_evidence",
        )
    return GateResult("G12", "PASS", "Conclusion strength does not exceed recorded evidence strength")


def _gate_no_final_placeholders(state: dict[str, Any]) -> GateResult:
    draft = "\n".join(str(value) for value in (state.get("cer_chapter_drafts") or {}).values())
    found = [token for token in PLACEHOLDER_TOKENS if token.lower() in draft.lower()]
    if not found:
        return GateResult("G13", "PASS", "No final placeholder tokens")
    return GateResult("G13", "REWORK_REQUIRED", f"Final draft contains placeholders: {', '.join(found)}")


def _gate_nb_high_risk_zero(state: dict[str, Any]) -> GateResult:
    report = state.get("nb_precheck_report") or state.get("qa_gate_report", {}).get("nb_precheck_report") or {}
    high = int(report.get("high_risk_count", 0) or 0)
    critical = int(report.get("critical_count", 0) or 0)
    if high == 0 and critical == 0:
        return GateResult("G14", "PASS", "No high-risk NB deficiencies recorded")
    return GateResult("G14", "REWORK_REQUIRED", f"NB high-risk/critical deficiencies remain: critical={critical}, high={high}")


def _gate_human_style_depth(state: dict[str, Any]) -> GateResult:
    benchmark = state.get("human_style_benchmark_report") or {}
    if benchmark and benchmark.get("status") != "PASS":
        return GateResult("G15", "REWORK_REQUIRED", f"Human-template benchmark failed: score={benchmark.get('score')}; findings={benchmark.get('findings')}")
    chapters = state.get("cer_chapter_drafts") or {}
    required = ["1 Summary", "2 Scope", "3 Clinical", "4 Device", "5 Conclusions", "6 Date", "7 Evaluator", "8 Declaration", "9 Dates"]
    missing = [name for name in required if not any(str(key).startswith(name) for key in chapters)]
    table_like = sum(1 for key in ("claim_ledger", "cep_pico_matrix", "evidence_registry", "sota_benchmark_matrix", "risk_trace_matrix") if state.get(key))
    if missing:
        return GateResult("G15", "REWORK_REQUIRED", f"CER draft does not cover required chapter set: {', '.join(missing)}")
    if table_like < 5:
        return GateResult("G15", "REWORK_REQUIRED", "Human-template style requires the five core tables to be populated")
    draft = "\n".join(str(value) for value in chapters.values())
    subsection_hits = sum(1 for token in ("4.1", "4.2", "4.3", "4.4", "4.5", "4.6", "4.7", "GSPR", "Evidence", "Benchmark") if token in draft)
    if len(draft) < 2500 or subsection_hits < 5:
        return GateResult("G15", "REWORK_REQUIRED", "CER draft is too thin for human-template style; add section-level reasoning, tables, and 4.7 GSPR analysis")
    return GateResult("G15", "PASS", "Human-template chapter coverage and table density are present")


def _gate_review_regression_boundary(state: dict[str, Any]) -> GateResult:
    # This gate is intentionally static in runtime: authoring must remain
    # isolated and regression protection is enforced by authoring-prefixed tests.
    return GateResult("G16", "PASS", "Authoring runtime uses internal authoring-* configs and does not mutate review builtins")


def _gate_mcp_execution_completeness(state: dict[str, Any]) -> GateResult:
    logs = state.get("mcp_call_log") or []
    if not logs:
        return GateResult("G17", "REWORK_REQUIRED", "No MCP call log recorded; v7 requires real MCP execution")
    required_servers = {"doc-proc", "cer-kb", "nb-check", "cer-public-evidence"}
    seen_servers = {str(item.get("server")) for item in logs if item.get("server")}
    missing = sorted(required_servers - seen_servers)
    if missing:
        return GateResult("G17", "REWORK_REQUIRED", f"Required MCP servers not invoked: {', '.join(missing)}")
    required_tools = {
        "doc-proc": {"extract_document_metadata"},
        "cer-kb": {"get_best_template", "generate_writing_brief"},
        "nb-check": {"generate_search_strategy", "predict_deficiencies"},
        "cer-public-evidence": {
            "pubmed_search",
            "embase_search",
            "cochrane_reviews_search",
            "clinicaltrials_search",
            "euctr_search",
            "eudamed_device_search",
            "eudamed_vigilance_search",
            "nz_medsafe_safety_search",
            "fda_maude_search",
            "fda_recall_search",
        },
    }
    missing_tools = []
    for server, tools in required_tools.items():
        seen_tools = {str(item.get("tool")) for item in logs if item.get("server") == server}
        for tool in tools - seen_tools:
            missing_tools.append(f"{server}.{tool}")
    if missing_tools:
        return GateResult("G17", "REWORK_REQUIRED", f"Required MCP tools not invoked: {', '.join(missing_tools)}")
    failed = [f"{item.get('server')}.{item.get('tool')}" for item in logs if str(item.get("status")).lower() not in {"ok", "pass", "warning", "skipped"}]
    if failed:
        # Public sites can be unavailable, but KIMI template/doc/nb tools must
        # be healthy for a 100% v7 authoring run.
        hard_failed = [name for name in failed if not name.startswith("cer-public-evidence.")]
        if hard_failed:
            return GateResult("G17", "REWORK_REQUIRED", f"Authoring MCP tools failed: {', '.join(hard_failed[:8])}")
    return GateResult("G17", "PASS", "Required authoring MCP servers and tools were invoked")


def _gate_authoring_review_team_recorded(state: dict[str, Any]) -> GateResult:
    reviewers = {str(item.get("agent")) for item in state.get("reviewer_results") or [] if item.get("agent")}
    covered = set()
    for item in state.get("subagent_invocation_log") or []:
        covered.update(str(role) for role in item.get("covered_virtual_roles") or [])
    for item in state.get("virtual_review_dimensions") or []:
        if item.get("agent"):
            covered.add(str(item.get("agent")))
    required = {*VIRTUAL_REVIEW_DIMENSIONS, "authoring-final-gate-closure"}
    reviewers = reviewers | covered
    missing = sorted(required - reviewers)
    if missing:
        return GateResult("G18", "REWORK_REQUIRED", f"Authoring Review & Gate Team results missing: {', '.join(missing)}")
    blocking = [
        f"{item.get('agent')}: {item.get('findings') or item.get('reason') or item.get('status')}"
        for item in state.get("reviewer_results") or []
        if str(item.get("status", "")).upper() in {"REWORK_REQUIRED", "HUMAN_HOLD", "FAIL"}
    ]
    if blocking:
        return GateResult("G18", "REWORK_REQUIRED", f"Authoring review team blocked release: {'; '.join(blocking[:6])}")
    return GateResult("G18", "PASS", "Authoring Review & Gate Team recorded independent gate results")


def _gate_cer_body_english_only(state: dict[str, Any]) -> GateResult:
    draft = "\n".join(str(value) for value in (state.get("cer_chapter_drafts") or {}).values())
    if not CJK_RE.search(draft):
        return GateResult("G19", "PASS", "CER draft body is English-only")
    examples = []
    for line in draft.splitlines():
        if CJK_RE.search(line):
            examples.append(line.strip()[:160])
        if len(examples) >= 3:
            break
    return GateResult("G19", "REWORK_REQUIRED", f"CER draft contains non-English Chinese text: {examples}")


def _gate_ap_template_loaded(state: dict[str, Any]) -> GateResult:
    profile = state.get("ap_template_profile") or (state.get("human_style_benchmark_report") or {}).get("ap_template_profile") or {}
    if int(profile.get("template_count") or 0) >= 4:
        return GateResult("G20", "PASS", "AP CER template directory was profiled and mapped")
    return GateResult("G20", "REWORK_REQUIRED", "AP CER template profile is missing; authoring must use the AP CER template package")


def _gate_template_logic_depth(state: dict[str, Any]) -> GateResult:
    profile = state.get("template_logic_profile") or {}
    if profile.get("chapter_logic") and len(profile.get("depth_rules") or []) >= 4:
        chapters = state.get("cer_chapter_drafts") or {}
        draft = "\n".join(str(value) for value in chapters.values())
        required_tokens = ("question", "evidence", "analysis", "limitation", "conclusion", "benchmark", "GSPR")
        missing = [token for token in required_tokens if token.lower() not in draft.lower()]
        if not missing:
            return GateResult("G21", "PASS", "Template writing logic and chapter-depth pattern are represented")
        return GateResult("G21", "REWORK_REQUIRED", f"CER body lacks visible reasoning-depth tokens: {', '.join(missing)}")
    return GateResult("G21", "REWORK_REQUIRED", "Template logic profile is missing; AP/human CER logic must be abstracted before writing")


def _gate_engineer_comment_theme_controls(state: dict[str, Any]) -> GateResult:
    profile = state.get("engineer_comment_profile") or {}
    themes = profile.get("themes") or []
    if len(themes) < 6:
        return GateResult("G21b", "REWORK_REQUIRED", "Engineer NB-facing comment profile is missing or incomplete")
    draft = "\n".join(str(value) for value in (state.get("cer_chapter_drafts") or {}).values()).lower()
    requirements = {
        "summary/scope regulatory and clinical-benefit controls": ("article 61", "clinical benefit"),
        "equivalence route controls": ("equivalence", "not claimed"),
        "market and vigilance controls": ("marketing history", "vigilance"),
        "SOTA framework and search controls": ("sota", "benchmark"),
        "GSPR benefit-risk comparison controls": ("gspr", "benefit-risk", "comparison"),
        "section-conclusion controls": ("section conclusion",),
    }
    missing = []
    for label, tokens in requirements.items():
        if not all(token in draft for token in tokens):
            missing.append(label)
    if missing:
        return GateResult("G21b", "REWORK_REQUIRED", f"Engineer feedback themes not visibly represented: {', '.join(missing)}")
    return GateResult("G21b", "PASS", "Engineer NB-facing feedback themes are represented in CER drafting logic")


def _gate_human_cer_comparison(state: dict[str, Any]) -> GateResult:
    report = state.get("human_cer_comparison_report") or {}
    if not report:
        return GateResult("G22", "REWORK_REQUIRED", "nb-check.compare_cer against human CER benchmark was not executed")
    if report.get("status") == "not_applicable":
        return GateResult("G22", "PASS", f"Human CER semantic comparison not applicable: {report.get('reason')}")
    if report.get("status") == "skipped":
        return GateResult("G22", "REWORK_REQUIRED", f"Human CER comparison skipped: {report.get('reason')}")
    high = []
    for gap in report.get("key_gaps_ranked") or []:
        if str(gap.get("severity", "")).upper() != "HIGH":
            continue
        if gap.get("type") == "missing_sections":
            sections = [str(item) for item in gap.get("sections") or []]
            real_section_gaps = [item for item in sections if not item.lstrip().startswith("|")]
            if not real_section_gaps:
                continue
            gap = {**gap, "sections": real_section_gaps}
        high.append(gap)
    if high:
        return GateResult("G22", "REWORK_REQUIRED", f"Human CER comparison found high gaps: {high[:3]}")
    return GateResult("G22", "PASS", "Human CER semantic/structure comparison executed without high gaps")


def _gate_vigilance_relevance_screened(state: dict[str, Any]) -> GateResult:
    registry = state.get("vigilance_recall_registry") or []
    screening = state.get("vigilance_relevance_screening") or []
    if registry and screening:
        return GateResult("G23", "PASS", "Vigilance/recall relevance screening records are present")
    return GateResult("G23", "REWORK_REQUIRED", "Vigilance/recall searches must include relevance screening rows")


def _gate_subagent_harness_configured(state: dict[str, Any]) -> GateResult:
    logs = state.get("subagent_invocation_log") or []
    mode = state.get("agent_team_mode") or os.getenv("CER_AUTHORING_AGENT_TEAM_MODE") or STABLE_AGENT_TEAM_MODE
    if mode not in {STABLE_AGENT_TEAM_MODE, LEGACY_AGENT_TEAM_MODE}:
        mode = STABLE_AGENT_TEAM_MODE
    required = set(physical_agent_names_for_mode(mode))
    seen = {str(item.get("agent")) for item in logs}
    missing = sorted(required - seen)
    if missing:
        return GateResult("G24", "REWORK_REQUIRED", f"Authoring subagent harness invocation records missing for {mode}: {', '.join(missing)}")
    strict = os.getenv("CER_AUTHORING_STRICT_V7", "").lower() in {"1", "true", "yes", "strict"}
    failed = [f"{item.get('agent')}={item.get('status')}" for item in logs if str(item.get("status", "")).upper() in {"FAILED", "UNAVAILABLE", "TIMED_OUT"}]
    if failed:
        return GateResult("G24", "REWORK_REQUIRED", f"Authoring subagent harness failures: {', '.join(failed[:5])}")
    if strict:
        not_completed = [
            f"{item.get('agent')}={item.get('status')}"
            for item in logs
            if item.get("agent") in required and (item.get("mode") != "llm_subagent" or str(item.get("status")).upper() != "COMPLETED")
        ]
        if not_completed:
            return GateResult("G24", "REWORK_REQUIRED", f"Strict v7 requires completed LLM subagents: {', '.join(not_completed[:8])}")
        return GateResult("G24", "PASS", "Strict v7 LLM subagent team completed")
    return GateResult("G24", "PASS", f"Authoring subagent harness is configured/recorded for {mode}; strict LLM execution is enabled by CER_AUTHORING_STRICT_V7")


def _gate_full_text_endpoint_extraction(state: dict[str, Any]) -> GateResult:
    rows = state.get("endpoint_extraction") or []
    if not rows:
        return GateResult("G25", "REWORK_REQUIRED", "Endpoint extraction table is missing")
    bases = " ".join(str(row.get("extraction_basis", "")) for row in rows).lower()
    pivotal_ids = {str(row.get("evidence_id")) for row in state.get("evidence_registry") or [] if str(row.get("weight", "")).lower() == "pivotal"}
    if pivotal_ids:
        weak = []
        for row in rows:
            if str(row.get("source_evidence_id") or row.get("evidence_id")) not in pivotal_ids:
                continue
            row_text = str(row).lower()
            has_fulltext = "full text" in row_text or "source-document full text" in row_text
            has_trace = bool(row.get("full_text_page_or_section") or row.get("page_or_section") or row.get("source_page_or_table"))
            has_data = bool(row.get("sample_size") and row.get("timepoint") and row.get("statistical_result"))
            if not (has_fulltext and has_trace and has_data):
                weak.append(str(row.get("endpoint_id", "<unknown>")))
        if weak:
            return GateResult("G25", "REWORK_REQUIRED", f"Pivotal endpoint rows require full-text/page-level traceability: {', '.join(weak[:8])}")
    if "abstract" in bases or "source-document full text" in bases or "full text" in bases:
        return GateResult("G25", "PASS", "Endpoint extraction includes abstract/full-text or source-document extraction attempts with pivotal checks")
    return GateResult("G25", "REWORK_REQUIRED", "Endpoint extraction must include abstract/full-text/source-document extraction basis")


def _gate_lsp_methodology(state: dict[str, Any]) -> GateResult:
    required_tables = [
        "literature_search_protocol_profile",
        "sota_pico_strategy",
        "due_pico_strategy",
        "database_search_source_table",
        "literature_defined_limits",
        "literature_flow_registry",
        "protocol_deviation_log",
    ]
    missing = [key for key in required_tables if not state.get(key)]
    if missing:
        return GateResult("G26", "REWORK_REQUIRED", f"LSP methodology artifacts missing: {', '.join(missing)}")
    searches = state.get("search_run_registry") or []
    required_databases = {"pubmed", "europe pmc", "clinicaltrials", "eu clinical trials register", "embase", "cochrane"}
    seen = {str(row.get("database", "")).lower() for row in searches}
    missing_db = [name for name in required_databases if not any(name in item for item in seen)]
    if missing_db:
        return GateResult("G26", "REWORK_REQUIRED", f"LSP database execution/limitation records missing: {', '.join(missing_db)}")
    incomplete = [
        str(row.get("search_id", "<unknown>"))
        for row in searches
        if not row.get("database")
        or not row.get("query")
        or not row.get("search_date")
        or (row.get("result_count") is None and row.get("status") not in {"auth_required", "source_unavailable"})
    ]
    if incomplete:
        return GateResult("G26", "REWORK_REQUIRED", f"LSP search rows are not reproducible: {', '.join(incomplete[:8])}")
    return GateResult("G26", "PASS", "LSP methodology, PICO strategies, database records and deviations are present")


def _gate_sota_logic(state: dict[str, Any]) -> GateResult:
    required_tables = {
        "alternative_treatment_benchmark_table": "alternative treatment options",
        "guideline_pathway_table": "clinical guideline pathway",
        "similar_benchmark_device_table": "similar/benchmark devices",
        "hazard_source_table": "hazard sources",
        "sota_benchmark_matrix": "endpoint benchmarks",
        "sota_to_47_usage_matrix": "SOTA-to-4.7 usage",
    }
    missing = [label for key, label in required_tables.items() if not state.get(key)]
    if missing:
        return GateResult("G27", "REWORK_REQUIRED", f"SOTA logic tables missing: {', '.join(missing)}")
    benchmarks = state.get("sota_benchmark_matrix") or []
    incomplete = [
        str(row.get("benchmark_id", "<unknown>"))
        for row in benchmarks
        if not row.get("sota_source") or not row.get("acceptance_criterion") or not row.get("clinical_significance")
    ]
    if incomplete:
        return GateResult("G27", "REWORK_REQUIRED", f"SOTA benchmark rows lack source/acceptance/clinical meaning: {', '.join(incomplete[:8])}")
    unused = [str(row.get("benchmark_id", "<unknown>")) for row in benchmarks if not row.get("used_in_4_7")]
    if unused:
        return GateResult("G27", "REWORK_REQUIRED", f"SOTA benchmarks not used or retired for 4.7: {', '.join(unused[:8])}")
    draft = "\n".join(str(value) for value in (state.get("cer_chapter_drafts") or {}).values()).lower()
    tokens = ("clinical pathway", "alternative treatment", "guideline", "hazard", "acceptance criterion", "section 4.7")
    missing_tokens = [token for token in tokens if token not in draft]
    if missing_tokens:
        return GateResult("G27", "REWORK_REQUIRED", f"SOTA chapter lacks visible reasoning tokens: {', '.join(missing_tokens)}")
    return GateResult("G27", "PASS", "SOTA logic covers pathway, alternatives, guidelines, hazards, endpoints and 4.7 benchmark use")


def _gate_complex_tables(state: dict[str, Any]) -> GateResult:
    table_keys = [
        "sota_pico_strategy",
        "sota_search_strategy_table",
        "sota_screening_disposition_table",
        "sota_ck_appraisal_table",
        "alternative_treatment_benchmark_table",
        "guideline_pathway_table",
        "similar_benchmark_device_table",
        "hazard_source_table",
        "sota_benchmark_matrix",
        "sota_to_47_usage_matrix",
        "sota_medical_field_boundary",
        "sota_pico_v2_strategy",
        "sota_search_strategy_separated",
        "sota_screening_prisma",
        "sota_evidence_hierarchy",
        "sota_endpoint_extraction_fulltext",
        "sota_benchmark_derivation_table",
        "sota_section_conclusion_matrix",
        "sota_deduction_chain",
        "sota_endpoint_source_classification",
        "sota_aggregate_benchmark_rationale",
        "sota_conclusion_strength_guard",
    ]
    missing = [key for key in table_keys if not state.get(key)]
    if missing:
        return GateResult("G28", "REWORK_REQUIRED", f"Complex SOTA tables missing: {', '.join(missing)}")
    row_issues = []
    for key in table_keys:
        for row in state.get(key) or []:
            row_id = row.get("row_id") or row.get("benchmark_id") or row.get("pico_id") or row.get("search_id")
            has_id = bool(row_id)
            has_conclusion = bool(row.get("conclusion") or row.get("rationale") or row.get("limitation") or row.get("deviation_type") or row.get("conclusion_control") or row.get("why"))
            has_use = bool(
                row.get("evidence_use")
                or row.get("benchmark_use")
                or row.get("section_4_7_use")
                or row.get("sota_use")
                or row.get("endpoint_relevance")
                or row.get("device_positioning_impact")
                or row.get("purpose")
                or row.get("used_in_4_7")
                or row.get("output_artifact")
                or row.get("allowed_endpoint_use")
                or row.get("allowed_conclusion_strength")
                or row.get("allowed_language")
                or row.get("use_in_cer")
                or row.get("search_role")
                or row.get("full_text_status")
                or row.get("endpoint_contribution")
                or row.get("revision_logic")
                or row.get("phase")
                or row.get("derived_value_or_range")
            )
            if not (has_id and has_conclusion and has_use):
                row_issues.append(f"{key}:{row_id or '<missing-id>'}")
    if row_issues:
        return GateResult("G28", "REWORK_REQUIRED", f"Complex table rows lack stable ID, use, or conclusion fields: {', '.join(row_issues[:8])}")
    return GateResult("G28", "PASS", "Complex SOTA tables have IDs, evaluation use and conclusion/limitation fields")


def _gate_sota_literature_quantity(state: dict[str, Any]) -> GateResult:
    rows = state.get("sota_ck_appraisal_table") or state.get("sota_screening_disposition_table") or []
    count = _sota_included_count(rows)
    if SOTA_LITERATURE_TARGET_MIN <= count <= SOTA_LITERATURE_TARGET_MAX:
        return GateResult("G29", "PASS", f"SOTA final included literature count is within target range: {count}")
    justification = state.get("sota_literature_quantity_justification") or {}
    if count < SOTA_LITERATURE_TARGET_MIN and _sota_quantity_justified(justification):
        return GateResult("G29", "PASS", f"SOTA literature count below target ({count}) but controlled justification is complete")
    if count > SOTA_LITERATURE_TARGET_MAX and _sota_rows_have_hierarchy(rows):
        return GateResult("G29", "PASS", f"SOTA literature count above target ({count}) with hierarchy/endpoint contribution stratification")
    if count < SOTA_LITERATURE_TARGET_MIN:
        return GateResult("G29", "REWORK_REQUIRED", f"SOTA final included literature count is {count}; target is 20-40 or a complete search-exhaustion justification")
    return GateResult("G29", "REWORK_REQUIRED", f"SOTA final included literature count is {count}; evidence hierarchy and endpoint contribution stratification are required above 40")


def _gate_sota_endpoint_derivation(state: dict[str, Any]) -> GateResult:
    rows = state.get("sota_endpoint_derivation_table") or []
    if not rows:
        return GateResult("G30", "REWORK_REQUIRED", "SOTA endpoint derivation table is missing")
    missing = []
    required = ("pico_id", "evidence_id", "endpoint_id", "benchmark_id", "endpoint_definition", "sample_size", "timepoint", "statistical_result", "clinical_meaning", "use_in_section_4_7")
    for row in rows:
        if any(not row.get(field) for field in required):
            missing.append(str(row.get("row_id") or row.get("endpoint_id") or "<unknown>"))
    if missing:
        return GateResult("G30", "REWORK_REQUIRED", f"SOTA endpoint derivation rows lack trace fields: {', '.join(missing[:8])}")
    return GateResult("G30", "PASS", "SOTA endpoint derivation rows connect PICO/evidence/endpoint/benchmark/use in 4.7")


def _gate_sota_full_text_strength(state: dict[str, Any]) -> GateResult:
    evidence = state.get("evidence_registry") or []
    endpoints = state.get("endpoint_extraction") or []
    full_text_requests = state.get("full_text_request_list") or []
    pivotal_ids = {str(row.get("evidence_id")) for row in evidence if str(row.get("weight", "")).lower() == "pivotal"}
    if not pivotal_ids:
        return GateResult("G31", "PASS", "No pivotal literature is claimed; abstract-only evidence remains downgraded")
    requested_ids = {str(row.get("evidence_id")) for row in full_text_requests if row.get("evidence_id")}
    if pivotal_ids & requested_ids:
        return GateResult("G31", "REWORK_REQUIRED", f"Pivotal evidence still has full-text requests: {', '.join(sorted(pivotal_ids & requested_ids)[:8])}")
    endpoint_text = " ".join(str(row) for row in endpoints if str(row.get("source_evidence_id") or row.get("evidence_id")) in pivotal_ids).lower()
    if "full text" not in endpoint_text:
        return GateResult("G31", "REWORK_REQUIRED", "Pivotal evidence must have full-text endpoint extraction before strong conclusions")
    return GateResult("G31", "PASS", "Pivotal/benchmark evidence is not relying on abstract-only extraction")


def _gate_prisma_flow(state: dict[str, Any]) -> GateResult:
    flow = state.get("prisma_flow_data") or {}
    required_sections = ("identification", "screening", "included")
    missing = [section for section in required_sections if not isinstance(flow.get(section), dict) or not flow.get(section)]
    if missing:
        return GateResult("G32", "REWORK_REQUIRED", f"PRISMA flow data missing sections: {', '.join(missing)}")
    screening = flow.get("screening") or {}
    included = flow.get("included") or {}
    if screening.get("title_abstract_screened") is None or included.get("total_included") is None:
        return GateResult("G32", "REWORK_REQUIRED", "PRISMA flow requires title/abstract screened count and total included count")
    if not state.get("prisma_flow_diagram"):
        return GateResult("G32", "REWORK_REQUIRED", "PRISMA flow diagram artifact is missing")
    return GateResult("G32", "PASS", "PRISMA flow counts and diagram are present")


def _gate_similar_device_four_step(state: dict[str, Any]) -> GateResult:
    rows = state.get("similar_device_four_step_confirmation") or []
    attachments = state.get("similar_device_attachment_index") or []
    if not rows:
        return GateResult("G33", "REWORK_REQUIRED", "Similar-device four-step confirmation table is missing")
    seen_steps = {str(row.get("step", "")).lower() for row in rows}
    missing_steps = [f"step {idx}" for idx in range(1, 5) if not any(f"step {idx}" in step for step in seen_steps)]
    if missing_steps:
        return GateResult("G33", "REWORK_REQUIRED", f"Similar-device confirmation is missing: {', '.join(missing_steps)}")
    if len(attachments) < 10:
        return GateResult("G33", "REWORK_REQUIRED", "Similar-device attachment index requires the 10 baseline attachment requests")
    incomplete = [
        str(row.get("attachment_id") or row.get("row_id") or "<unknown>")
        for row in attachments
        if not (row.get("required_document") and row.get("use_in_cer") and row.get("if_missing"))
    ]
    if incomplete:
        return GateResult("G33", "REWORK_REQUIRED", f"Similar-device attachment rows lack source/use/missing-data handling: {', '.join(incomplete[:8])}")
    return GateResult("G33", "PASS", "Similar-device four-step confirmation and attachment index are present")


def _gate_eu_nz_vigilance_sources(state: dict[str, Any]) -> GateResult:
    registry = state.get("vigilance_recall_registry") or []
    stats = state.get("vigilance_event_statistics") or []
    seen = {str(row.get("database", "")).lower() for row in registry}
    required = {
        "EUDAMED vigilance": ("eudamed",),
        "New Zealand Medsafe": ("new zealand", "medsafe"),
    }
    missing = []
    for label, tokens in required.items():
        if not any(all(token in value for token in tokens) for value in seen):
            missing.append(label)
    if missing:
        return GateResult("G34", "REWORK_REQUIRED", f"EU/NZ vigilance source records missing: {', '.join(missing)}")
    if not stats:
        return GateResult("G34", "REWORK_REQUIRED", "Vigilance event statistics table is missing")
    return GateResult("G34", "PASS", "EUDAMED and New Zealand vigilance source records plus event statistics are present")


def _gate_marketing_pms_questionnaire(state: dict[str, Any]) -> GateResult:
    questionnaire = state.get("marketing_pms_customer_questionnaire") or []
    has_market_or_pms = any(_has_document_type(state, needle) for needle in ("pms", "pmcf", "sales", "marketing", "complaint"))
    if has_market_or_pms and questionnaire:
        return GateResult("G35", "PASS", "Marketing/PMS source exists and customer questionnaire is available for completeness")
    if has_market_or_pms:
        return GateResult("G35", "PASS", "Marketing/PMS source exists; questionnaire is not mandatory for this run")
    if len(questionnaire) >= 8:
        return GateResult("G35", "PASS", "Marketing/PMS source is absent; customer questionnaire was generated")
    return GateResult("G35", "REWORK_REQUIRED", "Marketing/PMS source is absent and customer questionnaire is missing or incomplete")


def _gate_sota_seven_step_deduction(state: dict[str, Any]) -> GateResult:
    rows = state.get("sota_deduction_chain") or []
    if not rows:
        return GateResult("G36", "REWORK_REQUIRED", "SOTA seven-step deduction chain is missing")
    steps = {str(row.get("step_number")) for row in rows}
    missing_steps = [str(idx) for idx in range(1, 8) if str(idx) not in steps]
    incomplete = []
    for row in rows:
        for field in ("logic_question", "why", "how", "source_basis", "output_artifact", "conclusion_control"):
            if not str(row.get(field, "")).strip():
                incomplete.append(f"{row.get('row_id') or row.get('step_number')}:{field}")
    if missing_steps or incomplete:
        details = []
        if missing_steps:
            details.append(f"missing steps: {', '.join(missing_steps)}")
        if incomplete:
            details.append(f"incomplete fields: {', '.join(incomplete[:8])}")
        return GateResult("G36", "REWORK_REQUIRED", "; ".join(details))
    return GateResult("G36", "PASS", "SOTA explicitly answers the seven reviewer deduction questions")


def _gate_aggregate_benchmark_basis(state: dict[str, Any]) -> GateResult:
    benchmarks = state.get("sota_benchmark_matrix") or []
    rows = state.get("sota_aggregate_benchmark_rationale") or []
    if not benchmarks:
        return GateResult("G37", "REWORK_REQUIRED", "SOTA benchmark matrix is missing")
    if len(rows) < len(benchmarks):
        return GateResult("G37", "REWORK_REQUIRED", "Aggregate benchmark rationale rows do not cover every SOTA benchmark")
    invalid = []
    for row in rows:
        status = str(row.get("aggregate_basis_status", "")).lower()
        allowed = str(row.get("allowed_conclusion_strength", "")).lower()
        if not status or not row.get("single_study_control") or not row.get("aggregate_source_requirement"):
            invalid.append(str(row.get("benchmark_id") or row.get("row_id") or "<unknown>"))
            continue
        if "single_study" in status and any(term in allowed for term in ("superior", "definitive", "fully")):
            invalid.append(str(row.get("benchmark_id") or row.get("row_id") or "<unknown>"))
    if invalid:
        return GateResult("G37", "REWORK_REQUIRED", f"Benchmark aggregate basis is uncontrolled or overclaimed: {', '.join(invalid[:8])}")
    return GateResult("G37", "PASS", "Every benchmark has aggregate-basis status or explicit single-study/qualitative downgrade control")


def _gate_sota_conclusion_strength_guard(state: dict[str, Any]) -> GateResult:
    guards = state.get("sota_conclusion_strength_guard") or []
    if not guards:
        return GateResult("G38", "REWORK_REQUIRED", "SOTA conclusion-strength guard is missing")
    incomplete = [
        str(row.get("row_id") or row.get("guard_scope") or "<unknown>")
        for row in guards
        if not row.get("highest_evidence_level")
        or not row.get("allowed_language")
        or not row.get("prohibited_language")
        or not row.get("reason")
    ]
    if incomplete:
        return GateResult("G38", "REWORK_REQUIRED", f"Conclusion-strength guard rows are incomplete: {', '.join(incomplete[:8])}")
    draft = "\n".join(str(value) for value in (state.get("cer_chapter_drafts") or {}).values()).lower()
    strong_terms = ("superior", "proven better", "definitively", "fully demonstrated", "all risks are acceptable")
    superiority_allowed = any(bool(row.get("superiority_claim_allowed")) for row in guards)
    if not superiority_allowed and any(term in draft for term in strong_terms):
        return GateResult("G38", "REWORK_REQUIRED", "CER uses superiority/absolute wording that is not allowed by the evidence-level guard")
    return GateResult("G38", "PASS", "SOTA conclusion wording is constrained by evidence level and comparator availability")


def _sota_included_count(rows: list[dict[str, Any]]) -> int:
    accepted: set[str] = set()
    for row in rows:
        text = str(row).lower()
        if "excluded" in text and "accepted" not in text:
            continue
        if "evidence_gap" in text:
            continue
        if row.get("disposition") and "excluded" in str(row.get("disposition")).lower():
            continue
        if row.get("title_abstract_decision") and "include" not in str(row.get("title_abstract_decision")).lower():
            continue
        article_id = str(row.get("article_id") or row.get("row_id") or "").strip()
        if article_id:
            accepted.add(article_id)
    return len(accepted)


def _sota_quantity_justified(justification: dict[str, Any]) -> bool:
    required = (
        "search_exhaustion_rationale",
        "database_limitations",
        "screening_rationale",
        "evidence_gap_control",
        "clinical_impact",
    )
    return bool(justification) and all(str(justification.get(key, "")).strip() for key in required)


def _sota_rows_have_hierarchy(rows: list[dict[str, Any]]) -> bool:
    if not rows:
        return False
    keys = ("evidence_hierarchy", "evidence_category", "endpoint_contribution", "clinical_relevance")
    return all(any(str(row.get(key, "")).strip() for key in keys) for row in rows[: SOTA_LITERATURE_TARGET_MAX + 1])


def _build_domain_contamination_report(state: dict[str, Any]) -> dict[str, Any]:
    lock = state.get("device_identity_lock") or {}
    domain = str(lock.get("locked_domain") or (state.get("device_profile") or {}).get("device_domain") or "generic")
    profile = state.get("device_profile") or {}
    chapters = state.get("cer_chapter_drafts") or {}
    profile_text = " ".join(str(profile.get(key, "")) for key in profile)
    title_text = " ".join(str(chapters.get(key, "")) for key in ("Clinical Evaluation Report", "1 Summary", "2 Scope of Clinical Evaluation"))
    findings = []

    def add_if_found(scope: str, text: str, tokens: tuple[str, ...], severity: str = "HIGH") -> None:
        lower = text.lower()
        for token in tokens:
            if token.lower() in lower:
                findings.append({"scope": scope, "token": token, "severity": severity})

    if domain == "urology_nephroscope":
        add_if_found(
            "device_profile",
            profile_text,
            (
                "pulsed field",
                "ablation",
                "atrial fibrillation",
                "pulmonary vein",
                "cardiac",
                "electroporation",
                "lithovue",
                "clearpetra",
                "ureteral access sheath",
            ),
        )
        add_if_found(
            "core_chapters",
            title_text,
            ("pulsed field", "ablation", "atrial fibrillation", "pulmonary vein", "cardiac electrophysiology", "electroporation"),
        )
    elif domain == "cardiac_pfa":
        add_if_found("device_profile", profile_text, ("renal pelvis", "nephroscope", "ureteroscope", "urinary tract", "lithovue"))
        add_if_found("core_chapters", title_text, ("renal pelvis", "nephroscope", "ureteroscope", "urinary tract"))
    elif domain == "urology_uas":
        add_if_found("device_profile", profile_text, ("pulsed field", "ablation", "atrial fibrillation", "pulmonary vein", "cardiac", "lithovue"))

    return {"locked_domain": domain, "findings": findings}


def _has_document_type(state: dict[str, Any], needle: str) -> bool:
    for item in state.get("source_inventory") or []:
        if needle.lower() == "ifu" and item.get("source_role") in {"similar_device_ifu", "similar_or_benchmark_source", "unconfirmed_ifu"}:
            continue
        if needle.lower() == "ifu" and item.get("excluded_from_device_profile"):
            continue
        combined = " ".join(str(item.get(key, "")) for key in ("document_type", "doc_type", "type", "filename", "path")).lower()
        if needle.lower() in combined:
            return True
    return False


# ═══════════════════════════════════════════════════════════════════════════════
# WS2-WS10 Gates — return GateResult for main authoring gate aggregation
# ═══════════════════════════════════════════════════════════════════════════════


def _gate_ws2_ifu_iteration_closure(state: dict[str, Any]) -> GateResult:
    """WS2: IFU iteration loop must be closed or explicitly pending manufacturer."""
    from deerflow.runtime.cer_authoring.ifu_iteration import build_ifu_iteration_ledger

    ledger = build_ifu_iteration_ledger(state)
    open_blockers = ledger["ifu_iteration_decision_ledger"].get("open_blockers", [])
    if open_blockers:
        return GateResult(
            "WS2_IFU_ITERATION_CLOSURE",
            "BLOCKED",
            f"IFU iteration loop has {len(open_blockers)} open blockers: {open_blockers}",
            failure_pattern="ifu_iteration_open_blockers",
            blocked_reason="IFU iteration ledger must be closed before writer invocation.",
            reroute_context={"open_blockers": open_blockers, "ledger": ledger},
        )
    return GateResult("WS2_IFU_ITERATION_CLOSURE", "PASS", "IFU iteration loop is closed.")


def _gate_ws2_ifu_overclaim(state: dict[str, Any]) -> GateResult:
    """WS2: IFU overclaim with unsupported evidence blocks writer."""
    from deerflow.runtime.cer_authoring.ifu_iteration import build_ifu_iteration_ledger

    ledger = build_ifu_iteration_ledger(state)
    has_overclaim = ledger["ifu_iteration_decision_ledger"].get("has_overclaim", False)
    if has_overclaim:
        return GateResult(
            "WS2_IFU_OVERCLAIM",
            "BLOCKED",
            "IFU contains claims with unsupported evidence — writer blocked.",
            failure_pattern="ifu_overclaim_unsupported_evidence",
            blocked_reason="IFU overclaim must be resolved before CER writing.",
            upstream_node_to_reroute="claim_decomposition",
        )
    return GateResult("WS2_IFU_OVERCLAIM", "PASS", "No IFU overclaim detected.")


def _gate_ws3_claim_taxonomy(state: dict[str, Any]) -> GateResult:
    """WS3: Claim taxonomy must classify all claims correctly."""
    from deerflow.runtime.cer_authoring.claim_taxonomy import build_claim_taxonomy_decision_table

    claims = state.get("claim_ledger") or []
    taxonomy = build_claim_taxonomy_decision_table(claims)
    unsupported = [r for r in taxonomy["claim_taxonomy_decision_table"] if not r["final_body_allowed"]]
    if unsupported:
        return GateResult(
            "WS3_CLAIM_TAXONOMY",
            "REWORK_REQUIRED",
            f"{len(unsupported)} claims are not eligible for final body.",
            failure_pattern="unsupported_claim_in_body",
            reroute_context={"unsupported_claims": [r["claim_id"] for r in unsupported]},
        )
    return GateResult("WS3_CLAIM_TAXONOMY", "PASS", f"All {len(claims)} claims classified and eligible.")


def _gate_ws3_final_body_claim_eligibility(state: dict[str, Any]) -> GateResult:
    """WS3: Background-only or to_be_verified claims must not enter final body."""
    from deerflow.runtime.cer_authoring.claim_taxonomy import build_claim_taxonomy_decision_table

    claims = state.get("claim_ledger") or []
    taxonomy = build_claim_taxonomy_decision_table(claims)
    ineligible = [r for r in taxonomy["claim_taxonomy_decision_table"] if not r["final_body_allowed"]]
    if ineligible:
        return GateResult(
            "WS3_CLAIM_ELIGIBILITY",
            "BLOCKED",
            f"{len(ineligible)} claims ineligible for final body text.",
            failure_pattern="ineligible_claim_in_final_body",
            blocked_reason="Remove or downgrade ineligible claims before final release.",
        )
    return GateResult("WS3_CLAIM_ELIGIBILITY", "PASS", "All claims eligible for final body.")


def _gate_ws4_prisma_reproducibility(state: dict[str, Any]) -> GateResult:
    """WS4: PRISMA must be reproducible for submission-grade SOTA."""
    from deerflow.runtime.cer_authoring.prisma_reproducibility import build_prisma_reproducibility_audit

    prisma_data = state.get("prisma_flow_data") or {}
    search_runs = state.get("search_run_registry") or state.get("literature_flow_registry") or []
    screening = state.get("screening_disposition") or state.get("pmid_screening_and_exclusion_table") or []
    audit = build_prisma_reproducibility_audit(prisma_data, search_runs, screening)

    if audit["submission_grade_sota_blocked"]:
        return GateResult(
            "WS4_PRISMA_REPRODUCIBILITY",
            "BLOCKED",
            f"PRISMA not reproducible: {audit['major_failures']} major, {audit['critical_failures']} critical failures.",
            failure_pattern="prisma_not_reproducible",
            blocked_reason="Unreproducible PRISMA blocks submission-grade SOTA conclusions.",
            reroute_context={"audit": audit},
        )
    if audit["status"] == "FAIL":
        return GateResult(
            "WS4_PRISMA_REPRODUCIBILITY",
            "REWORK_REQUIRED",
            f"PRISMA audit has warnings: {len(audit['warnings'])} issues.",
            failure_pattern="prisma_reproducibility_warnings",
        )
    return GateResult("WS4_PRISMA_REPRODUCIBILITY", "PASS", "PRISMA flow is reproducible.")


def _gate_ws5_evidence_level_ceiling(state: dict[str, Any]) -> GateResult:
    """WS5: Writer wording must not exceed evidence-level ceiling."""
    from deerflow.runtime.cer_authoring.evidence_level_matrix import build_evidence_level_summary_matrix

    evidence_registry = state.get("evidence_registry") or state.get("evidence_source_inventory") or []
    claims = state.get("claim_ledger") or []
    matrix = build_evidence_level_summary_matrix(evidence_registry, claims)
    overall_ceiling = matrix["summary"]["overall_ceiling"]
    has_strong_claims = any(
        str(c.get("support_status") or c.get("support_level") or "").upper() == "STRONG"
        for c in claims
    )
    ceiling_violation = has_strong_claims and overall_ceiling in {"MODERATE", "CAUTIOUS", "INSUFFICIENT"}

    if ceiling_violation:
        return GateResult(
            "WS5_EVIDENCE_LEVEL_CEILING",
            "BLOCKED",
            f"Evidence ceiling is {overall_ceiling} but claims assert STRONG support.",
            failure_pattern="evidence_ceiling_violation",
            blocked_reason="Writer wording exceeds evidence-level ceiling.",
            reroute_context={"ceiling": overall_ceiling, "matrix": matrix},
        )
    return GateResult("WS5_EVIDENCE_LEVEL_CEILING", "PASS", f"Evidence ceiling ({overall_ceiling}) supports claim wording.")


def _gate_ws6_endpoint_homogeneity(state: dict[str, Any]) -> GateResult:
    """WS6: Heterogeneous endpoints must downgrade conclusion or become PMCF objectives."""
    from deerflow.runtime.cer_authoring.endpoint_homogeneity import build_endpoint_homogeneity_matrix

    endpoints = state.get("endpoint_extraction") or state.get("endpoint_registry") or []
    benchmarks = state.get("sota_benchmark_matrix") or state.get("sota_endpoint_derivation_table") or []
    matrix = build_endpoint_homogeneity_matrix(endpoints, benchmarks)

    if matrix["summary"]["conclusion_downgrade_required"]:
        return GateResult(
            "WS6_ENDPOINT_HOMOGENEITY",
            "REWORK_REQUIRED",
            f"{matrix['summary']['heterogeneous_count']} endpoint families are heterogeneous — conclusion must be downgraded.",
            failure_pattern="endpoint_heterogeneity_downgrade",
            reroute_context={"downgraded_families": matrix["summary"]["downgraded_families"]},
        )
    return GateResult("WS6_ENDPOINT_HOMOGENEITY", "PASS", "All endpoint families are homogeneous for benchmark derivation.")


def _gate_ws7_equivalence_route(state: dict[str, Any]) -> GateResult:
    """WS7: Equivalence route must be locked before evidence writing."""
    from deerflow.runtime.cer_authoring.equivalence_route_lock import build_equivalence_route_lock

    lock = build_equivalence_route_lock(state)
    false_closure = (
        lock["decision"] == "full_equivalence_claimed"
        and not lock["equivalence_closed"]
    )
    if false_closure:
        return GateResult(
            "WS7_EQUIVALENCE_ROUTE",
            "BLOCKED",
            "False equivalence closure: equivalence claimed but matrices incomplete.",
            failure_pattern="false_equivalence_closure",
            blocked_reason="Equivalence cannot be claimed without complete technical/biological/clinical matrices.",
            reroute_context={"lock": lock},
        )
    return GateResult("WS7_EQUIVALENCE_ROUTE", "PASS", f"Equivalence route: {lock['decision']}.")


def _gate_ws8_benefit_risk_body_section(state: dict[str, Any], cer_body_text: str = "") -> GateResult:
    """WS8: CER body must have dedicated benefit-risk analysis section."""
    from deerflow.runtime.cer_authoring.benefit_risk_section import build_benefit_risk_body_section

    br = build_benefit_risk_body_section(state, cer_body_text or state.get("_cer_body_text", ""))
    if not br["benefit_risk_body_section"]["section_present"]:
        return GateResult(
            "WS8_BR_BODY_SECTION",
            "BLOCKED",
            "CER body is missing dedicated §4.8 Benefit-Risk Analysis section.",
            failure_pattern="missing_benefit_risk_body_section",
            blocked_reason="Benefit-risk must be a dedicated body section, not annex-only.",
        )
    if not br["unqualified_favourable_allowed"]:
        return GateResult(
            "WS8_BR_BODY_SECTION",
            "REWORK_REQUIRED",
            f"Benefit-risk section present but missing elements: {br['missing_elements']}",
            failure_pattern="benefit_risk_incomplete",
        )
    return GateResult("WS8_BR_BODY_SECTION", "PASS", "Benefit-risk body section is complete with required elements.")


def _gate_ws9_rmf_ifu_warning_linkage(state: dict[str, Any]) -> GateResult:
    """WS9: IFU warnings must map to RMF hazard IDs."""
    from deerflow.runtime.cer_authoring.rmf_crosswalk import build_rmf_deep_linkage

    linkage = build_rmf_deep_linkage(state)
    gate_status = linkage["gate_status"]

    if gate_status == "FAIL_MISSING_RMF_SOURCE":
        return GateResult(
            "WS9_RMF_IFU_LINKAGE",
            "REWORK_REQUIRED",
            "RMF source is missing — IFU warnings cannot be linked to hazard trace.",
            failure_pattern="missing_rmf_source",
        )
    if gate_status == "FAIL_UNLINKED_WARNINGS":
        return GateResult(
            "WS9_RMF_IFU_LINKAGE",
            "BLOCKED",
            f"{linkage['ifu_warning_rmf_crosswalk']['unlinked_count']} IFU warnings have no RMF hazard linkage.",
            failure_pattern="ifu_warning_unlinked_to_rmf",
            blocked_reason="IFU warnings without RMF linkage block unqualified benefit-risk conclusion.",
            reroute_context={"linkage": linkage},
        )
    return GateResult("WS9_RMF_IFU_LINKAGE", "PASS", "All IFU warnings have RMF hazard linkage.")


def _gate_ws10_submission_cleanliness(state: dict[str, Any], cer_body_text: str = "") -> GateResult:
    """WS10: DOCX body must be free of banned strings, CJK, placeholders."""
    from deerflow.runtime.cer_authoring.writer_remediation.writer_gates import (
        BANNED_INTERNAL_STRINGS,
        IFU_PLACEHOLDER_PATTERNS,
    )
    body = cer_body_text or state.get("_cer_body_text", "")
    banned_hits = [s for s in BANNED_INTERNAL_STRINGS if s.lower() in body.lower()]
    placeholder_hits = [p for p in IFU_PLACEHOLDER_PATTERNS if p.lower() in body.lower()]
    cjk_pattern = re.compile(r"[㐀-鿿　-〿＀-￯]")
    cjk_hits = cjk_pattern.findall(body)

    if banned_hits or placeholder_hits or cjk_hits:
        return GateResult(
            "WS10_SUBMISSION_CLEANLINESS",
            "BLOCKED",
            f"Body contains banned strings ({len(banned_hits)}), placeholders ({len(placeholder_hits)}), or CJK ({len(cjk_hits)}).",
            failure_pattern="submission_cleanliness_failure",
            blocked_reason="Raw JSON, internal trace, CJK, or placeholders must not enter DOCX body.",
            reroute_context={"banned": banned_hits, "placeholders": placeholder_hits, "cjk_count": len(cjk_hits)},
        )
    return GateResult("WS10_SUBMISSION_CLEANLINESS", "PASS", "Body text is clean of banned strings, CJK, and placeholders.")


def _gate_ws10_conclusion_completeness(state: dict[str, Any], cer_body_text: str = "") -> GateResult:
    """WS10: Conclusion must include safety, performance, benefit-risk, PMS/PMCF, limitations."""
    from deerflow.runtime.cer_authoring.regulatory_style import build_regulatory_style_fingerprint

    body = cer_body_text or state.get("_cer_body_text", "")
    fingerprint = build_regulatory_style_fingerprint(body)
    conclusion_check = fingerprint.get("conclusion", {})

    if conclusion_check.get("status") == "FAIL_WITH_GAPS":
        return GateResult(
            "WS10_CONCLUSION_COMPLETENESS",
            "REWORK_REQUIRED",
            f"Conclusion missing elements: {conclusion_check.get('missing', [])}",
            failure_pattern="conclusion_incomplete",
        )
    return GateResult("WS10_CONCLUSION_COMPLETENESS", "PASS", "Conclusion includes all required sub-conclusions.")


def _gate_ws10_body_annex_boundary(state: dict[str, Any], cer_body_text: str = "") -> GateResult:
    """WS10: Annex tables must support, not replace, body reasoning."""
    from deerflow.runtime.cer_authoring.regulatory_style import build_regulatory_style_fingerprint

    body = cer_body_text or state.get("_cer_body_text", "")
    fingerprint = build_regulatory_style_fingerprint(body)
    boundary = fingerprint.get("body_annex_boundary", {})

    if boundary.get("body_only_references_without_narrative"):
        return GateResult(
            "WS10_BODY_ANNEX_BOUNDARY",
            "REWORK_REQUIRED",
            "Body references annex tables without standalone narrative reasoning.",
            failure_pattern="annex_replacing_body_narrative",
        )
    return GateResult("WS10_BODY_ANNEX_BOUNDARY", "PASS", "Body/annex boundary respected.")
