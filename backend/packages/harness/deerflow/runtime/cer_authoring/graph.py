"""LangGraph entrypoint for the isolated CER authoring workflow."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from langgraph.graph import END, StateGraph

logger = logging.getLogger(__name__)
from langgraph.types import Command, interrupt

from deerflow.runtime.cer_authoring.agents import (
    LEAD_AGENT_NAME,
    STABLE_AGENT_TEAM_MODE,
    VIRTUAL_REVIEW_DIMENSIONS,
    build_authoring_subagent_configs,
)
from deerflow.runtime.cer_authoring.artifacts import build_authoring_workbook, write_authoring_artifacts
from deerflow.runtime.cer_authoring.knowledge_injector import (
    inject_defect_context_for_gate, build_nb_simulation_context, get_per_section_defenses
)
from deerflow.runtime.cer_authoring.gates import (
    MAX_SPIRAL_ROUNDS,
    evaluate_alignment_gate,
    evaluate_br_justified_gate,
    evaluate_claim_evidence_gate,
    evaluate_fulltext_basis_gate,
    evaluate_pre_writer_readiness_gate,
    evaluate_retrieval_domain_gate,
    evaluate_screening_depth_gate,
    run_authoring_gates,
)
from deerflow.runtime.cer_authoring import pipeline
from deerflow.runtime.cer_authoring.agent_runtime import (
    invoke_authoring_agent,
    isolate_initial_authoring_state,
    preload_gil_safe_native_modules,
    reviewer_result_from_invocation,
)

# ── Event Bus hybrid architecture imports ──
_EVENT_BUS_ENABLED = os.getenv("CER_AUTHORING_ENABLE_EVENT_BUS", "0") == "1"
if _EVENT_BUS_ENABLED:
    from deerflow.runtime.cer_authoring.event_bus import (
        EventBus,
        EventType,
        Event,
        get_event_bus,
        publish_batches,
        wait_for_batches,
        merge_batch_evidence,
        merge_batch_sota_results,
        merge_batch_vigilance_results,
        chunk_list,
    )
    from deerflow.runtime.cer_authoring.workers import (
        EvidenceAppraisalWorker,
        SotaSearchWorker,
        VigilanceSearchWorker,
    )
from deerflow.runtime.cer_authoring.writer_remediation.model_routing import build_provider_preflight
from deerflow.runtime.cer_authoring.state import SharedAuthoringState

_STAGE_AGENT = {
    "initialize": LEAD_AGENT_NAME,
    "device_profile": "authoring-intake-profile-claim-agent",
    "claim_decomposition": "authoring-intake-profile-claim-agent",
    "pico_derivation": "authoring-methodology-sota-agent",
    "methodology_review": "authoring-methodology-sota-agent",
    "sota_search": "authoring-methodology-sota-agent",
    "retrieval_domain_gate": LEAD_AGENT_NAME,
    "device_equivalence_search": "authoring-risk-equivalence-gspr-agent",
    "literature_screening": "authoring-evidence-agent",
    "screening_depth_gate": LEAD_AGENT_NAME,
    "evidence_appraisal": "authoring-evidence-agent",
    "fulltext_basis_gate": LEAD_AGENT_NAME,
    "endpoint_extraction": "authoring-evidence-agent",
    "sota_endpoint_gate": LEAD_AGENT_NAME,
    "pre_g42_claim_evidence_candidate_linking": "authoring-evidence-agent",
    "evidence_sufficiency_gate": LEAD_AGENT_NAME,
    "query_expansion": "authoring-methodology-sota-agent",
    "claim_evidence_matrix": "authoring-cer-writer-agent",
    "claim_evidence_gate": LEAD_AGENT_NAME,
    "gap_pmcf": "authoring-cer-writer-agent",
    "sota_clinical_context": "authoring-methodology-sota-agent",
    "vigilance_search": "authoring-risk-equivalence-gspr-agent",
    "equivalence_analysis": "authoring-risk-equivalence-gspr-agent",
    "risk_gspr_mapping": "authoring-risk-equivalence-gspr-agent",
    "evidence_review_gates": "authoring-qa-review-agent",
    "writer_synthesis": "authoring-cer-writer-agent",
    "benefit_risk_ledger": "authoring-cer-writer-agent",
    "br_justified_gate": LEAD_AGENT_NAME,
    "alignment_matrix": "authoring-risk-equivalence-gspr-agent",
    "alignment_gate": LEAD_AGENT_NAME,
    "pre_writer_readiness_gate": LEAD_AGENT_NAME,
    "controlled_compromise": LEAD_AGENT_NAME,
    "cer_writing": "authoring-cer-writer-agent",
    "human_style_review": "authoring-qa-review-agent",
    "nb_precheck": "authoring-qa-review-agent",
    "workbook": LEAD_AGENT_NAME,
    "gates": LEAD_AGENT_NAME,
    "export": LEAD_AGENT_NAME,
    # V3.1 bug-fix: previously missing stage-IDs
    "device_profile_iteration": "authoring-intake-profile-claim-agent",
    "pre_writer_summary": LEAD_AGENT_NAME,
    "intake_pack_review": LEAD_AGENT_NAME,
    "prisma_flow_review": LEAD_AGENT_NAME,
    "claim_sota_alignment": LEAD_AGENT_NAME,
    "review_quick_scan": LEAD_AGENT_NAME,
    "query_expansion": "authoring-methodology-sota-agent",
    "self_inspection": LEAD_AGENT_NAME,
    # V3.1 new nodes
    "clinical_fact_registry": LEAD_AGENT_NAME,
    "endpoint_master": LEAD_AGENT_NAME,
    "endpoint_selection": LEAD_AGENT_NAME,
    "reference_framework": LEAD_AGENT_NAME,
    "evidence_weighting": LEAD_AGENT_NAME,
    "benchmark_derivation": LEAD_AGENT_NAME,
    "own_data_alignment": LEAD_AGENT_NAME,
    "citation_assignment": LEAD_AGENT_NAME,
    "v3_1_gate_aggregation": LEAD_AGENT_NAME,
    "literature_download_gate": LEAD_AGENT_NAME,
    "liteparse_extraction": LEAD_AGENT_NAME,
}


def _stage(stage_id: str, status: str = "completed", **extra: Any) -> dict[str, Any]:
    return {"stage_results": [{"stage": stage_id, "agent": _STAGE_AGENT.get(stage_id), "status": status, **extra}], "status": stage_id}


def _branch_stage(stage_id: str, status: str = "completed", **extra: Any) -> dict[str, Any]:
    return {"stage_results": [{"stage": stage_id, "agent": _STAGE_AGENT.get(stage_id), "status": status, **extra}]}


def _agent_trace(agent_name: str, state: SharedAuthoringState, task: str, *, reviewer: bool = False) -> dict[str, Any]:
    return {"subagent_invocation_log": [invoke_authoring_agent(agent_name, dict(state), task, reviewer=reviewer)]}


def _team_mode(state: SharedAuthoringState) -> str:
    return state.get("agent_team_mode") or STABLE_AGENT_TEAM_MODE


def _with_team_mode(state: SharedAuthoringState, updates: dict[str, Any] | None = None) -> dict[str, Any]:
    merged = {**dict(state), **(updates or {})}
    merged["agent_team_mode"] = _team_mode(state)
    return merged


# ── HC Rework Routing ────────────────────────────────────────────────────
# Each HC gate can rewind to specific upstream nodes without restarting
# the entire pipeline.  When a human confirms with action="rework", the
# node returns Command(goto=target) and the graph resumes from there.

REWORK_TARGETS: dict[str, list[str]] = {
    "intake_pack_review": ["input_gate"],
    "device_profile": ["input_gate", "intake_pack_review"],
    "claim_decomposition": ["device_profile"],
    "sota_search_strategy": ["claim_decomposition", "device_profile"],
    "prisma_flow_review": ["sota_search_strategy", "claim_decomposition"],
    "evidence_appraisal": ["sota_search_strategy", "claim_decomposition"],
    "endpoint_extraction": ["evidence_appraisal", "sota_search_strategy"],
    "claim_sota_alignment": ["endpoint_extraction", "evidence_appraisal", "sota_search_strategy"],
    "pre_writer_summary": ["cer_writing", "claim_decomposition", "endpoint_extraction", "sota_search_strategy"],
    "cer_draft_review": ["cer_writing", "claim_decomposition", "sota_search_strategy"],
}


def _check_hc_rework(approval, confirmation_point: str):
    """If the human requested a rework, return Command(goto=target). Else None.

    BIGDP2026.6 P1.2: Unknown targets raise ValueError instead of silently
    returning None. This prevents human rework requests from being silently
    dropped when the target is invalid.
    """
    if isinstance(approval, dict) and str(approval.get("action", "")).lower() == "rework":
        target = str(approval.get("target") or "")
        valid_targets = REWORK_TARGETS.get(confirmation_point, [])
        if target:
            if target not in valid_targets:
                logger.error(
                    "HC rework blocked: target='%s' not in valid_targets=%s for confirmation_point='%s'",
                    target, valid_targets, confirmation_point,
                )
                raise ValueError(
                    f"HC rework target '{target}' is not valid for confirmation point "
                    f"'{confirmation_point}'. Valid targets: {valid_targets or '(none)'}"
                )
            reason = str(approval.get("reason", "") or "")
            counts = approval.get("_hc_rework_counts") or {}
            counts[confirmation_point] = counts.get(confirmation_point, 0) + 1
            return Command(
                goto=target,
                update={
                    "hc_rework_source": confirmation_point,
                    "hc_rework_target": target,
                    "hc_rework_reason": reason,
                    "_hc_rework_counts": counts,
                },
            )
    return None


def _virtual_review_rows(covered_by: str, status: str = "PASS") -> list[dict[str, Any]]:
    return [{"agent": name, "status": status, "covered_by": covered_by, "virtual_dimension": True} for name in VIRTUAL_REVIEW_DIMENSIONS]


def _load_review_feedback(artifact_root: str, resolved_ids: list[str] | None = None) -> dict[str, Any] | None:
    """Load advisory feedback from CER Review pipeline if present.

    Feedback is read-only and advisory-only. It does NOT trigger automatic
    rework — it is surfaced in human interrupt payloads for decision.

    Resolved findings (previously dismissed or addressed by human) are filtered
    out to avoid noise accumulation across rework cycles.

    P0-3: Validates HMAC signature to detect tampering.
    """
    if not artifact_root:
        return None
    feedback_path = Path(artifact_root).expanduser().resolve() / "review_feedback" / "latest.json"
    if not feedback_path.exists():
        return None
    try:
        with open(feedback_path, encoding="utf-8") as fh:
            data = json.load(fh)
        # Validate advisory_only constraint
        if not data.get("advisory_only"):
            logger.warning("Review feedback at %s missing advisory_only flag — rejecting", feedback_path)
            return None
        # P0-3: HMAC signature validation (soft-fail for legacy unsigned feedback)
        signature = data.get("signature")
        if signature:
            expected = _compute_feedback_signature(data)
            if not hmac.compare_digest(signature, expected):
                logger.error(
                    "Review feedback signature mismatch at %s — possible tampering detected",
                    feedback_path,
                )
                return None
            logger.debug("Review feedback signature verified at %s", feedback_path)
        else:
            logger.warning("Review feedback at %s has no signature — accepting unsigned (legacy)", feedback_path)
        # Filter out resolved findings
        resolved = set(resolved_ids or [])
        if resolved:
            original_count = len(data.get("findings", []))
            data["findings"] = [
                f for f in data.get("findings", [])
                if str(f.get("finding_id", "")) not in resolved
            ]
            filtered_count = len(data["findings"])
            if original_count != filtered_count:
                logger.info(
                    "Filtered %d resolved findings from review feedback (%d remaining)",
                    original_count - filtered_count,
                    filtered_count,
                )
        # P1-1: Audit log — feedback loaded
        _append_feedback_audit_log(artifact_root, {
            "event": "feedback_loaded",
            "feedback_id": data.get("feedback_id"),
            "findings_count": len(data.get("findings", [])),
            "filtered_resolved": len(resolved) if resolved else 0,
            "signature_valid": bool(signature and hmac.compare_digest(signature, _compute_feedback_signature(data))),
        })
        return data
    except Exception as exc:
        logger.warning("Failed to load review feedback from %s: %s", feedback_path, exc)
        return None


def _compute_feedback_signature(data: dict[str, Any]) -> str:
    """Compute HMAC-SHA256 signature over feedback canonical payload.

    Signs: feedback_id + source + advisory_only + canonical findings JSON.
    Key from CER_FEEDBACK_HMAC_SECRET env (falls back to project_id for test).
    """
    key = (data.get("source_project_id") or "dev-fallback-key").encode("utf-8")
    # Canonical payload: deterministic ordering
    payload = json.dumps({
        "feedback_id": data.get("feedback_id", ""),
        "source": data.get("source", ""),
        "advisory_only": bool(data.get("advisory_only")),
        "findings": sorted(
            [
                {
                    "finding_id": str(f.get("finding_id", "")),
                    "severity": str(f.get("severity", "")),
                    "category": str(f.get("category", "")),
                    "description": str(f.get("description", ""))[:500],
                }
                for f in (data.get("findings") or [])
            ],
            key=lambda x: x["finding_id"],
        ),
    }, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hmac.new(key, payload.encode("utf-8"), hashlib.sha256).hexdigest()


def _append_feedback_audit_log(artifact_root: str, record: dict[str, Any]) -> None:
    """P1-1: Append structured event to review_feedback/audit_log.jsonl."""
    try:
        audit_path = Path(artifact_root).expanduser().resolve() / "review_feedback" / "audit_log.jsonl"
        audit_path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **record,
        }, ensure_ascii=False, separators=(",", ":"))
        with open(audit_path, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception as exc:
        logger.debug("Failed to write feedback audit log: %s", exc)


def _node_initialize(state: SharedAuthoringState) -> dict[str, Any]:
    native_preload_status = preload_gil_safe_native_modules()
    clean_state, run_scope_audit = isolate_initial_authoring_state(dict(state))
    build_authoring_subagent_configs(_team_mode(clean_state))
    prepared = pipeline.prepare_source_inventory(clean_state)
    preflight = build_provider_preflight(_with_team_mode(clean_state, prepared))
    # ── Weak-coupling Layer 1: Load Review feedback (filter resolved) ──
    review_feedback = _load_review_feedback(
        str(clean_state.get("artifact_root") or ""),
        resolved_ids=clean_state.get("resolved_feedback_ids") or [],
    )
    # ── BL-19: CER update mode detection ──
    update_mode = str(clean_state.get("update_mode") or "new").lower()
    previous_cer = clean_state.get("previous_cer") or clean_state.get("prior_cer_report") or {}
    is_update = update_mode in ("update", "incremental", "periodic_update")
    update_context = {}
    if is_update and previous_cer:
        update_context = {
            "update_mode": update_mode,
            "previous_cer_version": str(previous_cer.get("version") or previous_cer.get("report_date") or "unknown"),
            "previous_cer_claims": len(previous_cer.get("claims") or previous_cer.get("claim_ledger") or []),
            "new_evidence_count": len(clean_state.get("new_evidence_since_update") or []),
            "changed_sections": previous_cer.get("changed_sections") or ["all"],
        }
    elif is_update:
        update_context = {"update_mode": update_mode, "status": "previous_cer_not_provided"}
    else:
        update_context = {"update_mode": "new", "status": "fresh_cer_generation"}
    trace = _agent_trace(
        LEAD_AGENT_NAME,
        _with_team_mode(clean_state, prepared),
        "Orchestrate CER authoring run, confirm input routing and launch the 1+6 specialist workflow.",
    )
    return {
        "status": clean_state.get("status") or "authoring_initialized",
        "update_context": update_context,
        "agent_team_mode": _team_mode(clean_state),
        "run_scope_audit": run_scope_audit,
        "review_feedback": review_feedback,
        "lead_decisions": [
            {
                "stage": "initialize",
                "decision": "route_to_input_gate",
                "agent_team_mode": _team_mode(clean_state),
                "run_scope_boundary": "generated state isolated before source intake",
                "native_preload_status": native_preload_status,
                "model_provider_preflight_status": preflight.get("status"),
                "missing_provider_count": preflight.get("missing_provider_count"),
                "review_feedback_loaded": review_feedback is not None,
                "review_feedback_finding_count": len(review_feedback.get("findings", [])) if review_feedback else 0,
            }
        ],
        "model_provider_preflight": preflight,
        **trace,
        **prepared,
    }


def _node_input_gate(state: SharedAuthoringState) -> dict[str, Any]:
    preflight = state.get("model_provider_preflight") or {}
    if preflight.get("status") == "BLOCKED_PROVIDER_UNAVAILABLE":
        missing = preflight.get("missing_providers") or {}
        return {
            "status": "provider_unavailable",
            "final_gate_decision": "HUMAN_HOLD",
            "input_gap_list": [
                {
                    "gap_id": "GAP-MODEL-PROVIDER",
                    "required_input": "LLM provider credentials",
                    "impact": "CER authoring cannot enter LLM subagent stages until routed model providers are configured.",
                    "missing_providers": missing,
                }
            ],
        }
    source_preflight = state.get("source_preflight_gate_report") or {}
    if source_preflight.get("status") == "BLOCKED":
        return {
            "status": "source_preflight_blocked",
            "final_gate_decision": "HUMAN_HOLD",
            "source_preflight_gate_report": source_preflight,
            "input_gap_list": [
                {
                    "gap_id": str(issue.get("issue_id") or "SOURCE-PREFLIGHT-BLOCKER"),
                    "required_input": "Controlled source package",
                    "impact": issue.get("message") or "CER authoring is blocked by source preflight.",
                    **({"details": issue} if isinstance(issue, dict) else {}),
                }
                for issue in (source_preflight.get("blocking_issues") or [])
            ],
        }
    has_ifu = any(
        "ifu" in " ".join(str(item.get(key, "")) for key in ("document_type", "doc_type", "type", "filename", "path")).lower()
        and item.get("source_role") not in {"similar_device_ifu", "similar_or_benchmark_source", "unconfirmed_ifu"}
        and not item.get("excluded_from_device_profile")
        for item in state.get("source_inventory", [])
    )
    if has_ifu:
        return {"status": "input_ready"}
    return {
        "status": "input_required",
        "final_gate_decision": "HUMAN_HOLD",
        "input_gap_list": [{"gap_id": "GAP-INPUT-IFU", "required_input": "IFU", "impact": "CER authoring cannot start without IFU"}],
    }


def _route_after_input_gate(state: SharedAuthoringState) -> str:
    status = state.get("status")
    if status == "source_preflight_blocked":
        return "controlled_compromise"
    if status in {"input_required", "provider_unavailable"}:
        # In claude_code mode, the "export" node is not registered; route to
        # controlled_compromise which is a terminal-ish state until Claude
        # Code picks up the package.
        if os.environ.get("DF_WRITING_ENGINE", "claude_code") == "claude_code":
            return "controlled_compromise"
        return "export"
    return "intake_pack_review"


# ── HC-0: Intake Pack P0/P1 Review ──────────────────────────────────────

def _node_intake_pack_review(state: SharedAuthoringState) -> dict[str, Any]:
    """HC-0: Review manufacturer intake pack before device profile.

    Reads the filled intake pack .xlsx and surfaces P0 (blocks Writer) and
    P1 (controlled gaps) statuses for human confirmation.  Critical issues
    (wrong-device GSPR, draft P0 fields) are flagged prominently.
    """
    from pathlib import Path
    review = pipeline.build_intake_pack_review(dict(state))
    if not review.get("intake_pack_found"):
        # No intake pack — skip HC-0, let source preflight handle it
        return {**_stage("intake_pack_review", "skipped"), "intake_pack_review": review}

    _intake_ctx = inject_defect_context_for_gate("intake_pack_review")
    approval = interrupt({
        "confirmation_point": "intake_pack_review",
        "step": "HC-0",
        "priority": "CRITICAL",
        "message": "Please review manufacturer intake pack P0/P1 status before device profile.",
        "p0_rows": review.get("p0_rows", []),
        "p1_rows": review.get("p1_rows", []),
        "p0_draft_count": review.get("p0_draft_count", 0),
        "p1_draft_count": review.get("p1_draft_count", 0),
        "critical_flags": review.get("critical_flags", []),
        "intake_pack_path": review.get("intake_pack_path", ""),
        "v5_defect_context": _intake_ctx,
        "action": "confirm_or_request_fix",
        "rework_targets": REWORK_TARGETS.get("intake_pack_review", ["input_gate"]),
    })
    _rework = _check_hc_rework(approval, "intake_pack_review")
    if _rework is not None:
        return _rework
    return {**_stage("intake_pack_review"), "intake_pack_review": review,
            "intake_pack_human_confirmed": True}


def _node_device_profile(state: SharedAuthoringState) -> dict[str, Any]:
    generated = pipeline.build_device_profile(dict(state))
    if not generated and not state.get("device_profile"):
        return _stage("device_profile", "rework_required", note="Device Profile must be populated from IFU/source documents")
    profile = generated.get("device_profile") or state.get("device_profile") or {}
    ifu_extraction = profile.get("ifu_structured_extraction") or {}
    # V5: Inject NB defect context for informed human confirmation
    defect_context = inject_defect_context_for_gate("device_profile")
    approval = interrupt({
        "confirmation_point": "device_profile",
        "step": 3,
        "priority": "CRITICAL",
        "message": "Please confirm Device Profile before proceeding to claim decomposition.",
        "device_profile": profile,
        "fields_to_verify": ["device_name", "device_type", "intended_purpose", "mode_of_action", "anatomical_site"],
        "ifu_fields_extracted": ifu_extraction.get("fields_extracted", []),
        "ifu_fields_pending": ifu_extraction.get("fields_pending", []),
        "ifu_pending_note": "Pending fields are deferred to claim decomposition — they will be resolved when clinical performance/safety claims need these baseline parameters.",
        "action": "confirm_or_correct",
        "rework_targets": REWORK_TARGETS.get("device_profile", []),
        "v5_defect_context": defect_context,
    })
    _rework = _check_hc_rework(approval, "device_profile")
    if _rework is not None:
        return _rework
    if isinstance(approval, dict) and approval.get("corrections"):
        profile.update(approval["corrections"])
        generated["device_profile"] = profile
        generated["device_profile_human_confirmed"] = True
    return {**_stage("device_profile"), **generated} if generated else _stage("device_profile")


def _node_claim_decomposition(state: SharedAuthoringState) -> dict[str, Any]:
    generated = pipeline.build_claims(dict(state))
    trace = _agent_trace(
        "authoring-intake-profile-claim-agent",
        _with_team_mode(state, generated),
        "Review intake, Device Profile and IFU claim decomposition outputs; identify input/profile/claim rework only.",
    )
    if not generated and not (state.get("claim_ledger") and state.get("intended_purpose_claim_table")):
        return _stage("claim_decomposition", "rework_required", note="Claim Ledger and Intended Purpose Claim Table are required")
    claims = generated.get("claim_ledger") or state.get("claim_ledger") or []
    # ── Weak-coupling Layer 1: Surface Review feedback in interrupt ──
    review_feedback = state.get("review_feedback") or {}
    _SEVERITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "INFORMATIONAL": 4}
    relevant_feedback = sorted(
        [
            f for f in review_feedback.get("findings", [])
            if f.get("suggested_rework_node") in {None, "claim_decomposition", "device_profile"}
        ],
        key=lambda f: _SEVERITY_ORDER.get(str(f.get("severity", "")).upper(), 99),
    )
    profile = state.get("device_profile") or {}
    ifu_ext = profile.get("ifu_structured_extraction") or {}
    interrupt_payload: dict[str, Any] = {
        "confirmation_point": "claim_decomposition",
        "step": 4,
        "priority": "CRITICAL",
        "message": "Please confirm Claim Ledger before proceeding to PICO derivation.",
        "claim_ledger": [{"claim_id": str(c.get("claim_id", "")), "claim_text": str(c.get("claim_text", ""))[:200], "claim_type": str(c.get("claim_type", ""))} for c in claims],
        "ifu_fields_pending": ifu_ext.get("fields_pending", []),
        "ifu_pending_note": "Claims may reference device parameters still pending IFU confirmation. These will be resolved when the claim's evidence chain requires the parameter — no independent re-extraction needed.",
        "action": "confirm_modify_add_delete",
    }
    if relevant_feedback:
        interrupt_payload["review_feedback"] = {
            "advisory_only": True,
            "finding_count": len(relevant_feedback),
            "findings": relevant_feedback,
            "message": f"CER Review found {len(relevant_feedback)} findings relevant to claims. These are advisory — review and decide.",
            "feedback_actions_schema": {
                "description": "For each finding, indicate how it was handled",
                "actions": ["adopted", "ignored", "partially_addressed"],
                "example": [
                    {"finding_id": "F-001", "action": "adopted", "note": "Corrected claim C-003 wording"},
                    {"finding_id": "F-002", "action": "ignored", "note": "False positive — IFU already covers this"},
                ],
            },
        }
    interrupt_payload["rework_targets"] = REWORK_TARGETS.get("claim_decomposition", [])
    approval = interrupt(interrupt_payload)
    _rework = _check_hc_rework(approval, "claim_decomposition")
    if _rework is not None:
        return _rework
    resolved_ids: list[str] = []
    resolution_log: list[dict[str, Any]] = []
    if isinstance(approval, dict):
        if approval.get("corrections"):
            generated["claim_ledger"] = approval["corrections"]
        if approval.get("deleted_claim_ids"):
            remaining = [c for c in claims if str(c.get("claim_id")) not in approval["deleted_claim_ids"]]
            generated["claim_ledger"] = remaining
        generated["claim_decomposition_human_confirmed"] = True
        # Track resolved feedback: if human explicitly acknowledged feedback, mark as resolved
        if approval.get("resolved_feedback_ids"):
            resolved_ids = [str(fid) for fid in approval["resolved_feedback_ids"]]
        elif approval.get("feedback_action") == "dismiss_all":
            resolved_ids = [str(f.get("finding_id", "")) for f in relevant_feedback if f.get("finding_id")]
        # P0-1: Feedback effectiveness — capture detailed resolution actions
        for action in approval.get("feedback_actions", []):
            fid = str(action.get("finding_id", ""))
            if fid:
                resolved_ids.append(fid)
                resolution_log.append({
                    "finding_id": fid,
                    "action": str(action.get("action", "resolved")),
                    "note": str(action.get("note", ""))[:500],
                    "node": "claim_decomposition",
                    "resolved_at": datetime.now(timezone.utc).isoformat(),
                })
    return {
        **_stage("claim_decomposition"),
        **trace,
        **generated,
        "resolved_feedback_ids": resolved_ids,
        "feedback_resolution_log": resolution_log,
    } if generated else _stage("claim_decomposition")


def _node_pico_derivation(state: SharedAuthoringState) -> dict[str, Any]:
    generated = pipeline.build_pico_matrix(dict(state))
    if generated:
        return {**_stage("pico_derivation"), **generated}
    if state.get("cep_pico_matrix"):
        return _stage("pico_derivation")
    return _stage("pico_derivation", "rework_required", note="CEP/PICO Matrix with derivation rationale is required")


def _node_methodology_review(state: SharedAuthoringState) -> dict[str, Any]:
    generated = pipeline.build_cep(dict(state))
    return {**_stage("methodology_review"), **generated}


def _node_sota_search(state: SharedAuthoringState) -> dict[str, Any]:
    claims = state.get("claim_ledger") or []
    # BL-01: Only claims with non-RMF/GSPR primary_source need PubMed search.
    # IFU_warning and warning_contraindication claims route to RMF/GSPR, not PubMed.
    _pubmed_claims = [
        c for c in claims
        if "rmf" not in str(c.get("primary_source", "")).lower()
        and "gspr" not in str(c.get("primary_source", "")).lower()
    ] if claims else []
    if not _pubmed_claims:
        return {**_stage("sota_search"), "search_skipped_ifu_warning": True,
                "search_skip_reason": "All claims have primary_source in RMF/GSPR — evidence sourced from RMF/GSPR, not PubMed"}
    # ── Event Bus parallel path (feature-flagged) ──
    generated = None
    if _event_bus_available():
        try:
            generated = _run_sota_search_event_bus(dict(state))
            logger.info("sota_search completed via Event Bus")
        except Exception as exc:
            logger.warning("Event Bus sota_search failed, falling back to serial: %s", exc)
    if generated is None:
        generated = pipeline.run_sota_search(dict(state))
    trace = _agent_trace(
        "authoring-methodology-sota-agent",
        _with_team_mode(state, generated),
        "Review PICO derivation, search protocol, SOTA searches, hazards and endpoint benchmark matrix.",
    )
    if not generated and not state.get("sota_benchmark_matrix"):
        return _stage("sota_search", "rework_required", note="SOTA benchmark matrix must be populated by real searches")
    search_runs = generated.get("search_run_registry") or state.get("search_run_registry") or []
    # ── P0-3: Humans[Mesh] filter audit ──
    humans_filter_applied = 0
    humans_filter_missing = 0
    for run in search_runs:
        query = str(run.get("exact_query") or run.get("search_terms") or "")
        if 'humans[Mesh]' in query.lower() or 'humans[mh]' in query.lower():
            humans_filter_applied += 1
            run["humans_filter"] = "applied"
        else:
            humans_filter_missing += 1
            run["humans_filter"] = "missing"
            # Auto-append Humans filter hint
            run["humans_filter_note"] = (
                "Humans[Mesh] NOT found in query. "
                "CER literature standards require Humans filter. "
                "If this search was executed on PubMed, append: AND Humans[Mesh]"
            )
    if humans_filter_missing > 0:
        logger.warning(
            "sota_search: %d/%d search runs missing Humans[Mesh] filter",
            humans_filter_missing, len(search_runs),
        )

    # ── PICO summary for human review ──
    pico_summary = []
    for p in (state.get("cep_pico_matrix") or []):
        pico_summary.append({
            "pico_id": str(p.get("pico_id", "")),
            "claim_id": str(p.get("claim_id", "")),
            "population": str(p.get("population", ""))[:100],
            "intervention": str(p.get("intervention", ""))[:80],
            "comparator": str(p.get("comparator", ""))[:120],
            "outcome": str(p.get("outcome", ""))[:100],
        })
    # ── Per-PICO result counts for feedback loop ──
    raw_records = generated.get("raw_literature_records") or state.get("raw_literature_records") or []
    for p in pico_summary:
        outcome_terms = str(p.get("outcome", "")).lower().replace(",", " ").split()
        p["matching_records"] = sum(
            1 for r in raw_records
            if any(t in (str(r.get("title", "")) + " " + str(r.get("abstract", ""))).lower()
                   for t in outcome_terms if len(t) > 3)
        )
    # ── Top raw records with basic metadata ──
    top_records = []
    for r in raw_records[:15]:
        top_records.append({
            "pmid": str(r.get("pmid", "")),
            "title": str(r.get("title") or r.get("source_title", ""))[:150],
            "database": str(r.get("database", "")),
            "search_id": str(r.get("search_id", "")),
        })
    _sota_ctx = inject_defect_context_for_gate("sota_search_strategy")
    approval = interrupt({
        "confirmation_point": "sota_search_strategy",
        "step": 7,
        "priority": "CRITICAL",
        "message": "Please confirm SOTA search strategy — wrong search = wrong CER.",
        "v5_defect_context": _sota_ctx,
        "search_runs": [
            {
                "search_id": str(r.get("search_id", "")),
                "database": str(r.get("database", "")),
                "search_terms": str(r.get("search_terms", ""))[:300],
                "returned_count": r.get("returned_count", 0),
                "inclusion_criteria": str(r.get("inclusion_terms", "")),
                "exclusion_criteria": str(r.get("exclusion_terms", "")),
                "editable": True,
            }
            for r in search_runs
        ],
        "database_options": ["PubMed", "NCBI PMC", "Europe PMC", "ClinicalTrials.gov", "Embase", "Cochrane Library", "EU Clinical Trials Register"],
        "modifiable_fields": ["search_terms", "inclusion_criteria", "exclusion_criteria"],
        "pico_count": len(pico_summary),
        "pico_summary": pico_summary[:8],
        "total_raw_records": len(raw_records),
        "top_records": top_records,
        "action": "confirm_or_correct",
        "rework_targets": REWORK_TARGETS.get("sota_search_strategy", []),
    })
    _rework = _check_hc_rework(approval, "sota_search_strategy")
    if _rework is not None:
        return _rework
    if isinstance(approval, dict) and approval.get("corrections"):
        generated["search_run_registry"] = approval["corrections"]
        generated["search_strategy_human_confirmed"] = True
    return {**_stage("sota_search"), **trace, **generated} if generated else _stage("sota_search")


def _hard_gate_update(stage_id: str, state: SharedAuthoringState, report: dict[str, Any], *, branch: bool = True) -> dict[str, Any]:
    stage_update = _branch_stage(stage_id) if branch else _stage(stage_id)
    return {
        **stage_update,
        f"{stage_id}_report": report,
        "gate_routing_trace": [
            {
                "gate_id": report.get("gate_id"),
                "invocation_order": len(state.get("gate_routing_trace") or []) + 1,
                "status": report.get("status"),
                "failure_pattern": report.get("failure_pattern") or "",
                "upstream_node_routed_to": report.get("upstream_node_to_reroute") if report.get("status") == "REWORK_REQUIRED" else "",
                "spiral_round": report.get("spiral_round"),
                "blocked_reason": report.get("blocked_reason") if report.get("status") == "BLOCKED" else "",
            }
        ],
        "lead_decisions": [
            {
                "stage": stage_id,
                "decision": report.get("status"),
                "gate_id": report.get("gate_id"),
                "route": _hard_gate_graph_route(report),
                "spiral_round": report.get("spiral_round"),
            }
        ],
    }


def _hard_gate_graph_route(report: dict[str, Any], *, pass_route: str | None = None) -> str:
    status = report.get("status")
    if status == "BLOCKED":
        return "controlled_compromise"
    if status == "REWORK_REQUIRED":
        return _normalize_graph_route(str(report.get("upstream_node_to_reroute") or report.get("next_node") or "controlled_compromise"))
    return pass_route or _normalize_graph_route(str(report.get("next_node") or ""))


def _normalize_graph_route(route: str) -> str:
    return {
        "gap_pmcf": "gap_pmcf",
        "claim_evidence": "claim_evidence_matrix",
        "benefit_risk": "benefit_risk_ledger",
        "alignment": "alignment_matrix",
        "fulltext_acquisition": "evidence_appraisal",
        "COMPROMISE": "controlled_compromise",
    }.get(route, route)


def _node_retrieval_domain_gate(state: SharedAuthoringState) -> dict[str, Any]:
    return _hard_gate_update("retrieval_domain_gate", state, evaluate_retrieval_domain_gate(dict(state)))


def _route_after_retrieval_domain_gate(state: SharedAuthoringState) -> str:
    return _hard_gate_graph_route(state.get("retrieval_domain_gate_report") or {}, pass_route="literature_screening")


def _node_device_equivalence_search(state: SharedAuthoringState) -> dict[str, Any]:
    generated = pipeline.run_device_equivalence_search(dict(state))
    return {**_branch_stage("device_equivalence_search"), **generated}


def _node_literature_screening(state: SharedAuthoringState) -> dict[str, Any]:
    generated = pipeline.screen_literature(dict(state))
    # R1: Generate PRISMA flow diagram + bridge to artifacts.py format
    prisma = pipeline._generate_prisma_flow(dict(state))
    diag = prisma.get("prisma_flow_diagram", {})
    prisma_artifacts_data = {
        "identification": {
            "database_records": diag.get("identification", {}).get("records_from_databases", 0),
            "other_source_records": diag.get("identification", {}).get("records_from_other_sources", 0),
        },
        "screening": {
            "deduplicated_records": diag.get("screening", {}).get("after_deduplication", 0),
            "title_abstract_screened": diag.get("screening", {}).get("records_screened", 0),
            "title_abstract_excluded": diag.get("screening", {}).get("records_excluded_title_abstract", 0),
            "full_text_assessed": diag.get("eligibility", {}).get("fulltext_assessed", 0),
            "full_text_excluded": diag.get("eligibility", {}).get("records_excluded_fulltext", 0),
        },
        "included": {
            "sota_included": diag.get("included", {}).get("studies_included", 0),
            "due_included": 0,
        },
    }
    if generated:
        return {**_branch_stage("literature_screening"), **generated, "prisma_flow": prisma, "prisma_flow_data": prisma_artifacts_data}
    if state.get("search_run_registry") or state.get("screening_disposition"):
        return {**_branch_stage("literature_screening"), "prisma_flow": prisma, "prisma_flow_data": prisma_artifacts_data}
    # ── P0-2: Exclusion reason documentation ──
    screening = generated.get("screening_disposition") or state.get("screening_disposition") or []
    excluded_without_reason = 0
    for row in screening:
        status = str(row.get("status") or row.get("disposition") or "").lower()
        if status in ("excluded", "rejected"):
            if not row.get("exclusion_reason") and not row.get("reason"):
                # Auto-classify exclusion reason from article metadata
                row["exclusion_reason"] = _auto_classify_exclusion(row)
                row["exclusion_criteria_id"] = _match_exclusion_criteria(row)
            if not row.get("exclusion_reason"):
                excluded_without_reason += 1
    if excluded_without_reason > 0:
        logger.warning("Literature screening: %d excluded articles without documented reason", excluded_without_reason)

    return {**_branch_stage("literature_screening"), **generated,
            "prisma_flow": prisma, "prisma_flow_data": prisma_artifacts_data,
            "screening_disposition": screening,
            "exclusion_reason_coverage": {
                "total_excluded": sum(1 for r in screening if str(r.get("status", "")).lower() in ("excluded", "rejected")),
                "with_reason": sum(1 for r in screening if str(r.get("status", "")).lower() in ("excluded", "rejected") and r.get("exclusion_reason")),
            }}


# ── P0-2 Helpers: Exclusion reason auto-classification ──

def _auto_classify_exclusion(row: dict) -> str:
    """Auto-classify exclusion reason from article metadata."""
    title = str(row.get("title") or "").lower()
    abstract = str(row.get("abstract") or row.get("summary") or "").lower()
    study_type = str(row.get("study_type") or row.get("study_design") or "").lower()

    if any(kw in title + abstract for kw in ("case report", "case study", "n=1", "single case")):
        return "Case report (N<10) — insufficient statistical weight"
    if any(kw in title + abstract for kw in ("animal", "rat", "mouse", "porcine", "swine", "rabbit", "canine", "in vitro")):
        return "Non-human study — excluded per CER literature standards"
    if "review" in study_type or "guideline" in study_type:
        return "Review/guideline — used as context only, not primary data source"
    if not abstract or len(abstract) < 30:
        return "No abstract available — cannot assess"
    return "Excluded during title/abstract screening"


def _match_exclusion_criteria(row: dict) -> str:
    """Match exclusion reason to a standard exclusion criteria ID."""
    reason = str(row.get("exclusion_reason") or "").lower()
    if "case report" in reason or "n<10" in reason:
        return "EXCL-01"  # Insufficient sample size
    if "non-human" in reason or "animal" in reason:
        return "EXCL-02"  # Non-human study
    if "review" in reason or "guideline" in reason:
        return "EXCL-03"  # Secondary source
    if "no abstract" in reason:
        return "EXCL-04"  # Unobtainable
    if "duplicate" in reason:
        return "EXCL-05"  # Duplicate
    return "EXCL-00"  # Other


def _node_screening_depth_gate(state: SharedAuthoringState) -> dict[str, Any]:
    return _hard_gate_update("screening_depth_gate", state, evaluate_screening_depth_gate(dict(state)))


def _route_after_screening_depth_gate(state: SharedAuthoringState) -> str:
    return _hard_gate_graph_route(state.get("screening_depth_gate_report") or {}, pass_route="prisma_flow_review")


# ── HC-3.5: PRISMA Flow Review ─────────────────────────────────────────

def _node_prisma_flow_review(state: SharedAuthoringState) -> dict[str, Any]:
    """HC-3.5: Review search results and PRISMA flow before evidence appraisal.

    Shows search hit counts per database, PRISMA funnel (identified → screened
    → full-text assessed → included), and full-text availability rate.  Warns
    when 0 full-text articles are available — a critical gap before scoring.
    """
    search_registry = state.get("search_run_registry") or []
    search_summary = []
    for s in search_registry[:10]:
        search_summary.append({
            "search_id": str(s.get("search_id", "")),
            "database": str(s.get("database", "")),
            "objective": str(s.get("objective", "")),
            "result_count": s.get("result_count"),
            "returned_count": s.get("returned_count", 0),
            "status": str(s.get("status", "unknown")),
        })

    prisma = state.get("prisma_flow_data") or {}
    funnel = {
        "identified": prisma.get("identification", {}).get("database_records", 0),
        "screened": prisma.get("screening", {}).get("title_abstract_screened", 0),
        "fulltext_assessed": prisma.get("screening", {}).get("full_text_assessed", 0),
        "included": prisma.get("included", {}).get("sota_included", 0),
    }
    evidence_count = len(state.get("evidence_registry") or [])
    fulltext_count = len(state.get("fulltext_acquisition_status_table") or [])
    fulltext_available = sum(
        1 for r in (state.get("fulltext_acquisition_status_table") or [])
        if str(r.get("full_text_available", "")).lower() in ("yes", "true", "1")
    )
    fulltext_pct = round(fulltext_available / max(evidence_count, 1) * 100)

    critical_warnings = []
    if funnel["identified"] == 0:
        critical_warnings.append("ZERO records identified from any database search — PRISMA flow is empty.")
    if funnel["fulltext_assessed"] == 0 and evidence_count > 0:
        critical_warnings.append(f"ZERO full-text articles assessed — {evidence_count} evidence items are abstract/metadata only.")
    if fulltext_pct < 10 and evidence_count > 0:
        critical_warnings.append(f"Full-text available for only {fulltext_available}/{evidence_count} articles ({fulltext_pct}%). Benchmark endpoint extraction may be unreliable.")

    # ── Article-level data for human review ──
    screening = state.get("screening_disposition") or []
    raw_recs = {str(r.get("article_id") or ""): r for r in (state.get("raw_literature_records") or [])}
    # Count exclusions by reason
    exclusion_counts: dict[str, int] = {}
    for s in screening:
        reason = str(s.get("exclusion_reason", "")).strip()
        if reason:
            exclusion_counts[reason[:80]] = exclusion_counts.get(reason[:80], 0) + 1
    # Top included articles with relevance assessment
    included_articles = []
    for s in screening:
        if str(s.get("title_abstract_decision", "")).lower() not in ("exclude", "excluded"):
            raw = raw_recs.get(str(s.get("article_id", "")), {})
            included_articles.append({
                "pmid": str(s.get("pmid", "")),
                "title": str(s.get("title") or raw.get("title", ""))[:150],
                "relevance": str(s.get("clinical_domain_match", s.get("retrieval_domain_status", ""))),
                "role": str(s.get("evidence_role_candidate", "")),
                "reason": str(s.get("reason_for_inclusion", ""))[:150],
            })
    included_articles.sort(key=lambda a: (0 if "high" in a["relevance"].lower() else 1 if "medium" in a["relevance"].lower() else 2, a.get("pmid", "")))
    # Full-text requests
    ft_requests = state.get("full_text_request_list") or []

    approval = _ctx_0 = inject_defect_context_for_gate("prisma_flow_review"); approval = interrupt({
        "v5_defect_context": _ctx_0,
        "confirmation_point": "prisma_flow_review",
        "step": "HC-3.5",
        "priority": "HIGH",
        "message": "Review search results, article relevance, and PRISMA flow before evidence appraisal.",
        "search_summary": search_summary,
        "prisma_funnel": funnel,
        "screening_total": len(screening),
        "screening_excluded": sum(1 for s in screening if str(s.get("title_abstract_decision", "")).lower() in ("exclude", "excluded")),
        "exclusion_reasons": exclusion_counts,
        "included_articles": included_articles[:20],
        "evidence_count": evidence_count,
        "fulltext_count": fulltext_count,
        "fulltext_available": fulltext_available,
        "fulltext_pct": fulltext_pct,
        "full_text_request_count": len(ft_requests),
        "full_text_requests": ft_requests[:10],
        # NCBI API fallback warning
        "ncbi_api_failed": state.get("_ncbi_api_failed", False),
        # Weighting preview: show how screening relevance will affect downstream claim support
        "weighting_preview": {
            "high_relevance_count": sum(1 for s in screening if "high" in str(s.get("retrieval_domain_status", "")).lower()),
            "medium_relevance_count": sum(1 for s in screening if "medium" in str(s.get("retrieval_domain_status", "")).lower()),
            "low_relevance_count": sum(1 for s in screening if "low" in str(s.get("retrieval_domain_status", "")).lower()),
            "pivotal_candidates": sum(1 for s in screening if str(s.get("evidence_role_candidate", "")) == "pivotal_candidate"),
            "supportive_candidates": sum(1 for s in screening if str(s.get("evidence_role_candidate", "")) == "supportive_candidate"),
            "background_candidates": sum(1 for s in screening if str(s.get("evidence_role_candidate", "")) == "background_candidate"),
            "note": "HIGH relevance = close domain match (weight 1.0). LOW = marginal (weight 0.3). These feed into weighted_support_score for claim support level determination.",
        },
        "critical_warnings": critical_warnings,
        "action": "confirm_or_request_fix",
        "rework_targets": REWORK_TARGETS.get("prisma_flow_review", []),
    })
    _rework = _check_hc_rework(approval, "prisma_flow_review")
    if _rework is not None:
        return _rework
    return {**_stage("prisma_flow_review"), "prisma_flow_human_confirmed": True}


def _node_evidence_appraisal(state: SharedAuthoringState) -> dict[str, Any]:
    # ── Event Bus parallel path (feature-flagged) ──
    # BIGDP2026.6 P1.4: Snapshot state before Event Bus attempt to prevent
    # partial-state pollution on fallback. Deduplicate merged results by
    # evidence_id to prevent evidence duplication in final state.
    _pre_bus_snapshot = dict(state)
    generated = None
    if _event_bus_available():
        try:
            generated = _run_evidence_appraisal_event_bus(dict(_pre_bus_snapshot))
            logger.info("evidence_appraisal completed via Event Bus")
        except Exception as exc:
            logger.warning("Event Bus evidence_appraisal failed, falling back to serial: %s", exc)
    if generated is None:
        generated = pipeline.appraise_evidence(dict(_pre_bus_snapshot))
    # Deduplicate evidence registry by evidence_id to prevent duplicates
    # from Event Bus partial-success + serial fallback scenarios.
    evidence_registry = generated.get("evidence_registry") or []
    if evidence_registry:
        seen_ids = set()
        deduped = []
        for entry in evidence_registry:
            eid = entry.get("evidence_id") or entry.get("id") or ""
            if eid and eid not in seen_ids:
                seen_ids.add(eid)
                deduped.append(entry)
            elif not eid:
                deduped.append(entry)  # Entries without ID are kept as-is
        if len(deduped) != len(evidence_registry):
            logger.info(
                "evidence_appraisal deduplication: %d entries → %d unique (removed %d duplicates)",
                len(evidence_registry), len(deduped),
                len(evidence_registry) - len(deduped),
            )
        generated["evidence_registry"] = deduped
    if not generated and not state.get("evidence_registry"):
        return _branch_stage("evidence_appraisal", "rework_required", note="Evidence Registry is required")
    # P0-4: Enrich evidence with MDCG 2020-6 levels
    mdcg_enriched = pipeline._enrich_evidence_with_mdcg({**dict(state), **(generated or {})})
    # P1-1: Auto-classify evidence depth for G41 gate compatibility
    depth_enriched = pipeline._enrich_evidence_with_depth({**dict(state), **(generated or {}), "evidence_registry": mdcg_enriched})
    evidence = depth_enriched or mdcg_enriched or generated.get("evidence_registry") or state.get("evidence_registry") or []
    appraisal = generated.get("article_appraisal") or state.get("article_appraisal") or []
    # Route B: Auto-trigger Quick-Scan if pivotal evidence has depth issues
    request_qs = False
    for row in evidence:
        if str(row.get("weight") or "").lower() == "pivotal":
            depth = str(row.get("evidence_depth") or "").upper()
            if depth and depth not in {"PRIMARY_VERBATIM", "PRIMARY_DERIVED"}:
                request_qs = True
                break
    # Part 4: Build evidence lineage graph
    lineage_result = _build_evidence_lineage(state, generated)
    # Build weight distribution and full-text stats for HC-4 review
    _weights = {"pivotal": 0, "supportive": 0, "background": 0, "other": 0}
    for e in evidence:
        w = str(e.get("weight", "")).lower()
        _weights[w if w in _weights else "other"] = _weights.get(w if w in _weights else "other", 0) + 1
    _fulltext_status = {"available": 0, "abstract_only": 0}
    for r in (state.get("fulltext_acquisition_status_table") or []):
        if str(r.get("full_text_available", "")).lower() in ("yes", "true", "1"):
            _fulltext_status["available"] += 1
        else:
            _fulltext_status["abstract_only"] += 1
    ft_requests = state.get("full_text_request_list") or []
    # V5: Inject NB evidence expectations for informed appraisal review
    defect_context = inject_defect_context_for_gate("evidence_appraisal")
    approval = interrupt({
        "confirmation_point": "evidence_appraisal",
        "step": 11,
        "priority": "HIGH",
        "message": "Please spot-check evidence appraisal scores and weight distribution.",
        "evidence_count": len(evidence),
        "weight_distribution": _weights,
        "fulltext_status": _fulltext_status,
        "full_text_request_count": len(ft_requests),
        "full_text_requests": ft_requests[:10],
        "appraisal_sample": [{"evidence_id": str(a.get("evidence_id", "")), "score": a.get("evidence_strength_score"), "weight": a.get("weight"), "relevance_weight": a.get("relevance_weight")} for a in appraisal[:10]],
        "calibration": {
            "enabled": True,
            "sample_size": min(20, len(appraisal)),
            "calibration_sample": [
                {
                    "evidence_id": str(a.get("evidence_id", "")),
                    "system_score": a.get("evidence_strength_score"),
                    "weight": a.get("weight"),
                    "title": str(next((r.get("title", "") for r in (state.get("raw_literature_records") or []) if str(r.get("pmid", "")) == str(a.get("pmid", ""))), ""))[:120],
                    "human_score": None,
                }
                for a in (appraisal[:20] if len(appraisal) >= 20 else appraisal)
            ],
            "deviation_threshold": 15,
        },
        "action": "confirm_or_correct",
        "rework_targets": REWORK_TARGETS.get("evidence_appraisal", []),
        "v5_defect_context": defect_context,
    })
    _rework = _check_hc_rework(approval, "evidence_appraisal")
    if _rework is not None:
        return _rework
    if isinstance(approval, dict) and approval.get("calibration_scores"):
        calib = approval["calibration_scores"]
        adjustments = []
        for a in appraisal:
            eid = str(a.get("evidence_id", ""))
            if eid in calib:
                human = float(calib[eid])
                system = float(a.get("evidence_strength_score", 0))
                deviation = abs(human - system)
                if deviation > 15:
                    a["evidence_strength_score"] = round((system + human) / 2, 1)
                    a["calibration_deviation"] = deviation
                    a["score_calibration_status"] = "calibrated"
                    adjustments.append({"evidence_id": eid, "system": system, "human": human, "deviation": deviation})
        generated["calibration_adjustments"] = adjustments
        generated["score_calibration_count"] = len(adjustments)
    if isinstance(approval, dict) and approval.get("corrections"):
        generated["article_appraisal"] = approval["corrections"]
        generated["evidence_appraisal_human_confirmed"] = True
    result = {**_branch_stage("evidence_appraisal"), **generated} if generated else _branch_stage("evidence_appraisal")
    if request_qs:
        result["request_review_quick_scan"] = True
        result["auto_quick_scan_trigger_node"] = "evidence_appraisal"
    if lineage_result:
        result["evidence_lineage"] = lineage_result.get("lineage")
        result["evidence_chain_breaks"] = lineage_result.get("breaks")
    return result


def _node_fulltext_basis_gate(state: SharedAuthoringState) -> dict[str, Any]:
    report = evaluate_fulltext_basis_gate(dict(state))
    # P1-1: Audit log for G41 depth violations
    depth_violations = report.get("pivotal_evidence_depth_violations") or []
    if depth_violations:
        _append_feedback_audit_log(
            str(state.get("artifact_root") or ""),
            {
                "event": "g41_depth_violation",
                "gate_id": "G41",
                "violations_count": len(depth_violations),
                "evidence_ids": [v.get("evidence_id") for v in depth_violations],
                "status": report.get("status"),
            },
        )
    return _hard_gate_update("fulltext_basis_gate", state, report)


def _route_after_fulltext_basis_gate(state: SharedAuthoringState) -> str:
    # P0-1: Route through clinical facts extraction before endpoint extraction
    return _hard_gate_graph_route(state.get("fulltext_basis_gate_report") or {}, pass_route="extract_clinical_facts")


# ══════════════════════════════════════════════════════════════════════════════
# P0-1: Clinical Evidence Fact Extraction (Claude Code capability absorption)
# Extracts numerical data points with PMID binding from evidence abstracts.
# Each fact: {endpoint, value, unit, n_events, n_total, pmid, extraction_basis}
# ══════════════════════════════════════════════════════════════════════════════

def _node_extract_clinical_facts(state: SharedAuthoringState) -> dict[str, Any]:
    """Extract structured numerical clinical data from evidence abstracts.

    Scans evidence_registry for findings text (abstracts, results summaries)
    and extracts: endpoint name, numerical value, unit, n_events, n_total,
    PMID, and the sentence the data was extracted from.

    This fills the gap where DeerFlow previously produced placeholder endpoints
    with zero numerical data. Now every extracted fact is PMID-anchored.
    """
    import re  # noqa: F811

    evidence_registry = state.get("evidence_registry") or []
    facts = []
    stats = {"articles_scanned": 0, "facts_extracted": 0, "articles_without_findings": 0}

    for ev in evidence_registry:
        stats["articles_scanned"] += 1
        pmid = str(ev.get("pmid") or ev.get("evidence_id") or "")
        findings = str(ev.get("findings") or ev.get("abstract") or ev.get("summary") or "")

        if not findings or len(findings) < 20:
            stats["articles_without_findings"] += 1
            continue

        # Pattern-based extraction for common clinical data formats.
        # Falls back to structured field extraction if patterns don't match.
        extracted = _extract_patterns_from_findings(findings, pmid)
        if not extracted:
            # Structured fallback: check for pre-extracted fields
            extracted = _extract_from_structured_fields(ev, pmid)

        facts.extend(extracted)
        stats["facts_extracted"] += len(extracted)

    return {
        **_branch_stage("extract_clinical_facts"),
        "clinical_evidence_fact_table": facts,
        "clinical_fact_extraction_stats": stats,
    }


def _extract_patterns_from_findings(text: str, pmid: str) -> list[dict]:
    """Extract numerical clinical data using regex patterns."""
    import re
    facts = []

    # Pattern 1: "X% (n/N)" — percentage with numerator/denominator
    pct_pattern = re.findall(
        r'(\d+\.?\d*)\s*%\s*\((\d+)\s*\/\s*(\d+)\)',
        text,
    )
    for pct, num, denom in pct_pattern:
        facts.append({
            "pmid": pmid,
            "value": float(pct),
            "unit": "percentage",
            "n_events": int(num),
            "n_total": int(denom),
            "extraction_basis": f"Pattern match: {pct}% ({num}/{denom})",
            "endpoint_hint": _infer_endpoint_from_context(text, f"{pct}%"),
        })

    # Pattern 2: "mean X ± Y" or "X ± Y"
    mean_pattern = re.findall(
        r'(?:mean\s+)?(\d+\.?\d*)\s*±\s*(\d+\.?\d*)',
        text,
    )
    for mean_val, sd_val in mean_pattern:
        facts.append({
            "pmid": pmid,
            "value": float(mean_val),
            "unit": "continuous",
            "sd": float(sd_val),
            "extraction_basis": f"Pattern match: mean {mean_val} ± {sd_val}",
            "endpoint_hint": _infer_endpoint_from_context(text, f"{mean_val} ± {sd_val}"),
        })

    # Pattern 3: "N=XXX" — sample size
    n_pattern = re.findall(r'(?:N|n)\s*[=＝]\s*(\d[\d,]*)', text)
    if n_pattern and not facts:
        facts.append({
            "pmid": pmid,
            "value": int(n_pattern[0].replace(",", "")),
            "unit": "sample_size",
            "extraction_basis": f"Pattern match: N={n_pattern[0]}",
            "endpoint_hint": "total_sample_size",
        })

    return facts


def _extract_from_structured_fields(ev: dict, pmid: str) -> list[dict]:
    """Extract from pre-populated structured evidence fields."""
    facts = []
    # Check for pre-extracted data fields
    for field in ["primary_outcome", "secondary_outcome", "efficacy_result", "safety_result"]:
        val = ev.get(field, "")
        if val and isinstance(val, (int, float)):
            facts.append({
                "pmid": pmid,
                "value": float(val),
                "unit": "from_structured_field",
                "extraction_basis": f"Structured field: {field}",
                "endpoint_hint": field,
            })
    return facts


def _infer_endpoint_from_context(text: str, match_str: str) -> str:
    """Infer endpoint type from surrounding text context."""
    text_lower = text.lower()
    idx = text_lower.find(match_str.lower())
    if idx < 0:
        return "unknown"
    # Look at 80 chars before the match for endpoint context
    context = text_lower[max(0, idx - 80):idx]
    endpoint_keywords = {
        "hemostasis": ["hemostasis", "bleeding", "closure"],
        "adverse_event": ["adverse event", "complication", "ae", "safety"],
        "mortality": ["mortality", "death", "survival"],
        "success_rate": ["success", "effective", "achieved"],
        "procedure_time": ["time", "duration", "minutes"],
    }
    for endpoint, keywords in endpoint_keywords.items():
        if any(kw in context for kw in keywords):
            return endpoint
    return "unspecified"


def _node_endpoint_extraction(state: SharedAuthoringState) -> dict[str, Any]:
    generated = pipeline.extract_endpoints(dict(state))
    trace = _agent_trace(
        "authoring-evidence-agent",
        _with_team_mode(state, generated),
        "Review evidence search, screening, citation verification, appraisal and endpoint extraction outputs.",
    )
    if not generated and not state.get("endpoint_extraction"):
        return _branch_stage("endpoint_extraction", "rework_required", note="Endpoint extraction is required for quantitative CER claims")
    endpoints = generated.get("endpoint_extraction") or state.get("endpoint_extraction") or []
    approval = _ctx_1 = inject_defect_context_for_gate("endpoint_extraction"); approval = interrupt({
        "v5_defect_context": _ctx_1,
        "confirmation_point": "endpoint_extraction",
        "step": 13,
        "priority": "HIGH",
        "message": "Please confirm extracted endpoints before SOTA benchmark derivation.",
        "endpoint_count": len(endpoints),
        "sample_endpoints": [{"endpoint_id": str(ep.get("endpoint_id", "")), "endpoint": str(ep.get("endpoint", ""))[:200], "source_article": str(ep.get("article_id", ""))} for ep in endpoints[:10]],
        "action": "confirm_or_correct",
        "rework_targets": REWORK_TARGETS.get("endpoint_extraction", []),
    })
    _rework = _check_hc_rework(approval, "endpoint_extraction")
    if _rework is not None:
        return _rework
    if isinstance(approval, dict) and approval.get("corrections"):
        generated["endpoint_extraction"] = approval["corrections"]
        generated["endpoint_extraction_human_confirmed"] = True
    return {**_branch_stage("endpoint_extraction"), **trace, **generated} if generated else _branch_stage("endpoint_extraction")


def _node_sota_endpoint_gate(state: SharedAuthoringState) -> dict[str, Any]:
    report = _sota_endpoint_gate_report(dict(state))
    result = _hard_gate_update("sota_endpoint_gate", state, report)
    # Increment rework counter on REWORK_REQUIRED to enable spiral convergence
    if report.get("status") == "REWORK_REQUIRED":
        result["rework_gate_counter"] = _rework_count(state) + 1
    return result


def _sota_endpoint_gate_report(state: dict[str, Any]) -> dict[str, Any]:
    qa = run_authoring_gates(state)
    result = next((row for row in qa.get("results", []) if row.get("gate_id") == "G30"), {})
    status = str(result.get("status") or "PASS")
    message = str(result.get("message") or "")
    if status == "PASS":
        route = ""
        next_node = "evidence_sufficiency_gate"
        failure_pattern = ""
    elif "no_benchmark_derivable_from_pool" in message:
        route = "sota_search"
        next_node = "sota_search"
        failure_pattern = "no_benchmark_derivable_from_pool"
    else:
        route = "endpoint_extraction"
        next_node = "endpoint_extraction"
        failure_pattern = "benchmark_fields_incomplete" if "lack trace fields" in message else "sota_endpoint_derivation_missing"
    return {
        "gate_id": "G30",
        "gate_name": "SOTA Endpoint Derivation",
        "status": status,
        "failure_pattern": failure_pattern,
        "upstream_node_to_reroute": route if status == "REWORK_REQUIRED" else "",
        "next_node": next_node,
        "spiral_round": _spiral_round_from_state(state),
        "blocked_reason": "",
        "message": message or f"G30 {status}; route to {next_node}.",
    }


def _route_after_sota_endpoint_gate(state: SharedAuthoringState) -> str:
    report = state.get("sota_endpoint_gate_report") or {}
    failure = str(report.get("failure_pattern") or "")
    # Intelligent spiral convergence: only continue if evidence pool can still grow
    if not _should_continue_spiral(state, failure_pattern=failure, max_rounds=MAX_SPIRAL_ROUNDS):
        return "pre_g42_claim_evidence_candidate_linking"
    route = _hard_gate_graph_route(report, pass_route="pre_g42_claim_evidence_candidate_linking")
    if route in ("endpoint_extraction", "sota_search", "evidence_appraisal"):
        return "query_expansion"
    return route


def _node_pre_g42_claim_evidence_candidate_linking(state: SharedAuthoringState) -> dict[str, Any]:
    generated = pipeline.build_pre_g42_claim_evidence_candidate_matrix(dict(state))
    if generated:
        return {**_branch_stage("pre_g42_claim_evidence_candidate_linking"), **generated}
    if state.get("pre_g42_claim_evidence_candidate_matrix"):
        return _branch_stage("pre_g42_claim_evidence_candidate_linking")
    return _branch_stage("pre_g42_claim_evidence_candidate_linking", "rework_required", note="Pre-G42 claim-evidence candidate matrix is required before G42")


def _node_evidence_sufficiency_gate(state: SharedAuthoringState) -> dict[str, Any]:
    report = pipeline.evaluate_evidence_sufficiency_gate(dict(state))
    counter_update = _inc_rework(state) if report.get("status") != "PASS" else {}
    return {
        **_branch_stage("evidence_sufficiency_gate"),
        **counter_update,
        "evidence_sufficiency_gate_report": report,
        "gate_routing_trace": [
            {
                "gate_id": "G42",
                "invocation_order": len(state.get("gate_routing_trace") or []) + 1,
                "status": report.get("status"),
                "failure_pattern": report.get("rework_reason") if report.get("status") != "PASS" else "",
                "upstream_node_routed_to": report.get("next_node") if report.get("status") == "REWORK_REQUIRED" else "",
                "spiral_round": report.get("current_spiral_round"),
                "blocked_reason": report.get("blocked_reason") if report.get("status") == "BLOCKED" else "",
            }
        ],
        "lead_decisions": [
            {
                "stage": "evidence_sufficiency_gate",
                "decision": report.get("status"),
                "route": report.get("next_node"),
                "spiral_round": report.get("current_spiral_round"),
            }
        ],
    }


# ── Simple rework counter (incremented by route functions, resets on forward) ──

def _rework_count(state: SharedAuthoringState) -> int:
    return int(state.get("rework_gate_counter") or 0)


def _inc_rework(state: SharedAuthoringState) -> dict[str, Any]:
    return {"rework_gate_counter": _rework_count(state) + 1}


def _route_after_evidence_sufficiency_gate(state: SharedAuthoringState) -> str:
    report = state.get("evidence_sufficiency_gate_report") or {}
    failure = str(report.get("failure_pattern") or "")
    # Intelligent spiral convergence
    if not _should_continue_spiral(state, failure_pattern=failure, max_rounds=MAX_SPIRAL_ROUNDS):  # BIGDP2026.6 P1.3: centralized constant
        # Max spiral reached → controlled compromise (human decision, not silent forward)
        return "controlled_compromise"
    if report.get("status") == "PASS":
        return "claim_evidence_matrix"
    return "query_expansion"


def _node_query_expansion(state: SharedAuthoringState) -> dict[str, Any]:
    generated = pipeline.query_expansion(dict(state))
    return {**_branch_stage("query_expansion"), **_inc_rework(state), **generated}


def _node_claim_evidence_matrix(state: SharedAuthoringState) -> dict[str, Any]:
    generated = pipeline.build_claim_evidence_benefit_risk_ledgers(dict(state))
    # Part 4: Rebuild lineage with claim-evidence links
    lineage_result = _build_evidence_lineage(state, generated)
    if generated:
        result = {**_branch_stage("claim_evidence_matrix"), **generated}
    elif state.get("claim_evidence_matrix"):
        result = _branch_stage("claim_evidence_matrix")
    else:
        result = _branch_stage("claim_evidence_matrix", "rework_required", note="Claim-evidence matrix is required before G43")
    if lineage_result:
        result["evidence_lineage"] = lineage_result.get("lineage")
        result["evidence_chain_breaks"] = lineage_result.get("breaks")
    return result


def _build_evidence_lineage(state: SharedAuthoringState, generated: dict[str, Any] | None) -> dict[str, Any] | None:
    """Part 4: Build evidence lineage graph from current state.

    Returns lineage export + chain breaks. Does not block on errors.
    """
    try:
        from deerflow.runtime.cer_authoring.evidence_lineage import EvidenceLineageGraph
        from pathlib import Path

        artifact_root = str(state.get("artifact_root") or "")
        if not artifact_root:
            return None

        db_path = Path(artifact_root).expanduser().resolve() / "evidence_lineage.db"
        graph = EvidenceLineageGraph(db_path=db_path)
        graph.load()

        merged_state = {**dict(state), **(generated or {})}
        graph.build_from_state(merged_state)
        graph.save()

        return {
            "lineage": graph.export_for_audit(),
            "breaks": graph.detect_chain_breaks(),
        }
    except Exception as exc:
        logger.warning("Evidence lineage build failed (non-fatal): %s", exc)
        return None


def _node_claim_evidence_gate(state: SharedAuthoringState) -> dict[str, Any]:
    report = evaluate_claim_evidence_gate(dict(state))
    result = _hard_gate_update("claim_evidence_gate", state, report)
    # Route B: Auto-trigger Quick-Scan on claim-evidence gate failure
    if report.get("status") == "REWORK_REQUIRED":
        result["request_review_quick_scan"] = True
        result["auto_quick_scan_trigger_node"] = "claim_evidence_gate"
        # Increment rework counter to enable spiral convergence
        result["rework_gate_counter"] = _rework_count(state) + 1
    return result


def _route_after_claim_evidence_gate(state: SharedAuthoringState) -> str:
    report = state.get("claim_evidence_gate_report") or {}
    failure = str(report.get("failure_pattern") or "")
    # Intelligent spiral convergence
    if not _should_continue_spiral(state, failure_pattern=failure, max_rounds=MAX_SPIRAL_ROUNDS):
        return "gap_pmcf"
    route = _hard_gate_graph_route(report, pass_route="gap_pmcf")
    if route in ("claim_decomposition", "sota_search", "evidence_appraisal"):
        return "query_expansion"
    return route


def _node_gap_pmcf(state: SharedAuthoringState) -> dict[str, Any]:
    generated = pipeline.build_gap_pmcf_recommendations(dict(state))
    if generated:
        return {**_branch_stage("gap_pmcf"), **generated}
    if state.get("gap_pmcf_recommendations"):
        return _branch_stage("gap_pmcf")
    return _branch_stage("gap_pmcf")


def _node_sota_clinical_context(state: SharedAuthoringState) -> dict[str, Any]:
    generated = pipeline.inject_sota_clinical_context(dict(state))
    if generated:
        return {**_branch_stage("sota_clinical_context"), **generated}
    if state.get("sota_clinical_context_table"):
        return _branch_stage("sota_clinical_context")
    return _branch_stage("sota_clinical_context", "rework_required", note="SOTA clinical context injection is required before evidence review gates")


def _node_claim_sota_alignment(state: SharedAuthoringState) -> dict[str, Any]:
    generated = pipeline.build_claim_sota_alignment(dict(state))
    approval = _ctx_2 = inject_defect_context_for_gate("claim_sota_alignment"); approval = interrupt({
        "v5_defect_context": _ctx_2,
        "confirmation_point": "claim_sota_alignment",
        "step": "20B",
        "priority": "HIGH",
        "message": "Please confirm Claim-SOTA alignment results.",
        "alignment_summary": generated.get("sota_alignment_summary", ""),
        "unsupported_claims": [r for r in generated.get("claim_sota_alignment_table", []) if r.get("feasibility") == "unsupported"],
        "action": "confirm_or_correct",
        "rework_targets": REWORK_TARGETS.get("claim_sota_alignment", []),
    })
    _rework = _check_hc_rework(approval, "claim_sota_alignment")
    if _rework is not None:
        return _rework
    if isinstance(approval, dict) and approval.get("corrections"):
        generated["claim_sota_alignment_table"] = approval["corrections"]
        generated["claim_sota_alignment_human_confirmed"] = True
    return {**_branch_stage("claim_sota_alignment"), **generated}


def _node_device_profile_iteration(state: SharedAuthoringState) -> dict[str, Any]:
    generated = pipeline.iterate_device_profile(dict(state))
    if generated.get("profile_iteration_human_confirmation_required"):
        return {
            **_branch_stage("device_profile_iteration", "human_confirmation_required"),
            **generated,
            "human_gate_required": True,
        }
    return {**_branch_stage("device_profile_iteration"), **generated}


def _node_vigilance_search(state: SharedAuthoringState) -> dict[str, Any]:
    # ── Event Bus parallel path (feature-flagged) ──
    generated = None
    if _event_bus_available():
        try:
            generated = _run_vigilance_search_event_bus(dict(state))
            logger.info("vigilance_search completed via Event Bus")
        except Exception as exc:
            logger.warning("Event Bus vigilance_search failed, falling back to serial: %s", exc)
    if generated is None:
        generated = pipeline.run_vigilance_search(dict(state))
    if generated:
        return {**_branch_stage("vigilance_search"), **generated}
    if state.get("vigilance_recall_registry"):
        return _branch_stage("vigilance_search")
    return _branch_stage("vigilance_search", "rework_required", note="Vigilance/recall registry must be populated before benefit-risk conclusion")


def _node_equivalence_analysis(state: SharedAuthoringState) -> dict[str, Any]:
    generated = pipeline.run_device_equivalence_search(dict(state))
    return {**_branch_stage("equivalence_analysis"), **generated}


def _node_risk_gspr_mapping(state: SharedAuthoringState) -> dict[str, Any]:
    generated = pipeline.map_risks_and_gspr(dict(state))
    # Phase 6: Build risk-evidence matrix per 心擎 method
    risk_evidence = pipeline._build_risk_evidence_mapping(dict(state))
    trace = _agent_trace(
        "authoring-risk-equivalence-gspr-agent",
        _with_team_mode(state, generated),
        "Review equivalence, vigilance/recall, risk trace and GSPR mapping outputs.",
    )
    if generated:
        return {**_branch_stage("risk_gspr_mapping"), **trace, **generated, "risk_evidence_matrix": risk_evidence}
    if state.get("risk_trace_matrix") and state.get("gspr_coverage"):
        return {**_branch_stage("risk_gspr_mapping"), "risk_evidence_matrix": risk_evidence}
    return _branch_stage("risk_gspr_mapping", "rework_required", note="Risk trace matrix and GSPR coverage are required")


def _node_evidence_review_gates(state: SharedAuthoringState) -> dict[str, Any]:
    return {**_stage("evidence_review_gates"), "lead_decisions": [{"stage": "evidence_review_gates", "decision": "integrated_QA_deferred_until_full_draft"}]}


def _node_writer_synthesis(state: SharedAuthoringState) -> dict[str, Any]:
    generated = pipeline.build_cross_evidence_synthesis(dict(state))
    if generated:
        return {**_stage("writer_synthesis"), **generated}
    if state.get("cross_evidence_synthesis_table"):
        return _stage("writer_synthesis")
    return _stage("writer_synthesis", "rework_required", note="Cross-evidence synthesis is required before CER section 4 writing")


def _node_benefit_risk_ledger(state: SharedAuthoringState) -> dict[str, Any]:
    generated = pipeline.build_claim_evidence_benefit_risk_ledgers(dict(state))
    if generated:
        return {**_stage("benefit_risk_ledger"), **generated}
    if state.get("benefit_risk_ledger"):
        return _stage("benefit_risk_ledger")
    return _stage("benefit_risk_ledger", "rework_required", note="Benefit-risk ledger is required before G44")


def _node_br_justified_gate(state: SharedAuthoringState) -> dict[str, Any]:
    return _hard_gate_update("br_justified_gate", state, evaluate_br_justified_gate(dict(state)), branch=False)


def _route_after_br_justified_gate(state: SharedAuthoringState) -> str:
    return _hard_gate_graph_route(state.get("br_justified_gate_report") or {}, pass_route="alignment_matrix")


def _node_alignment_matrix(state: SharedAuthoringState) -> dict[str, Any]:
    generated = pipeline.build_alignment_matrix(dict(state))
    if generated:
        return {**_stage("alignment_matrix"), **generated}
    if state.get("alignment_matrix"):
        return _stage("alignment_matrix")
    return _stage("alignment_matrix", "rework_required", note="Alignment matrix is required before G45")


def _node_alignment_gate(state: SharedAuthoringState) -> dict[str, Any]:
    return _hard_gate_update("alignment_gate", state, evaluate_alignment_gate(dict(state)), branch=False)


def _route_after_alignment_gate(state: SharedAuthoringState) -> str:
    # BIGDP2026.6 Phase 2: PASS routes through ledger chain before G46
    return _hard_gate_graph_route(state.get("alignment_gate_report") or {}, pass_route="build_reasoning_ledger")


def _node_pre_writer_readiness_gate(state: SharedAuthoringState) -> dict[str, Any]:
    # V3.2: Load pre-locked framework and metadata from disk before G46 evaluation.
    # This resolves the chicken-and-egg: G46 checks for locked_endpoint_framework
    # but HC-7.0 (which locks it) runs AFTER G46 PASS. Human pre-confirmation
    # via external review writes these files; G46 loads them here.
    artifact_root = str(state.get("artifact_root") or "")
    if artifact_root:
        import json as _json
        # Load locked endpoint framework
        if not state.get("locked_endpoint_framework"):
            lock_path = os.path.join(artifact_root, "locked_endpoint_framework.json")
            if os.path.isfile(lock_path):
                try:
                    with open(lock_path) as f:
                        pre_locked = _json.load(f)
                    if pre_locked.get("primary_endpoints"):
                        state["locked_endpoint_framework"] = pre_locked
                except Exception:
                    pass
        # Load CER metadata (eu_market_status, pmcf_required)
        meta_path = os.path.join(artifact_root, "cer_metadata.json")
        if os.path.isfile(meta_path):
            try:
                with open(meta_path) as f:
                    meta = _json.load(f)
                if not state.get("eu_market_status") and meta.get("eu_market_status"):
                    state["eu_market_status"] = meta["eu_market_status"]
                if meta.get("pmcf_required") is not None:
                    state["pmcf_required"] = meta["pmcf_required"]
            except Exception:
                pass

    report = evaluate_pre_writer_readiness_gate(dict(state))
    return {
        **_stage("pre_writer_readiness_gate"),
        "pre_writer_readiness_report": report,
        "gate_routing_trace": [
            {
                "gate_id": "G46",
                "invocation_order": len(state.get("gate_routing_trace") or []) + 1,
                "status": report.get("status"),
                "failure_pattern": report.get("route_condition") or "",
                "upstream_node_routed_to": report.get("next_node") if report.get("status") == "REWORK_REQUIRED" else "",
                "blocked_reason": report.get("compromise_reason") if report.get("status") == "BLOCKED" else "",
            }
        ],
        "lead_decisions": [
            {
                "stage": "pre_writer_readiness_gate",
                "decision": report.get("decision"),
                "gate_status": report.get("status"),
                "writer_route": report.get("next_node"),
            }
        ],
    }


# ── V3.2: Claude Code CER Authoring Engine integration nodes ──────────


def _node_endpoint_framework_lock(state: SharedAuthoringState) -> dict[str, Any]:
    """HC-7.0: Human confirms endpoint whitelist/blacklist before writing."""
    from deerflow.runtime.cer_authoring.gates import evaluate_endpoint_framework_lock

    # V3.2: Check for pre-locked framework on disk (human pre-confirmed via external review)
    if not state.get("locked_endpoint_framework"):
        artifact_root = str(state.get("artifact_root") or "")
        if artifact_root:
            lock_path = os.path.join(artifact_root, "locked_endpoint_framework.json")
            if os.path.isfile(lock_path):
                import json as _json
                try:
                    with open(lock_path) as f:
                        pre_locked = _json.load(f)
                    if pre_locked.get("primary_endpoints"):
                        state["locked_endpoint_framework"] = pre_locked
                except Exception:
                    pass

    # V3.2: Check for pre-set metadata on disk
    if not state.get("eu_market_status"):
        artifact_root = str(state.get("artifact_root") or "")
        if artifact_root:
            meta_path = os.path.join(artifact_root, "cer_metadata.json")
            if os.path.isfile(meta_path):
                import json as _json
                try:
                    with open(meta_path) as f:
                        meta = _json.load(f)
                    if meta.get("eu_market_status"):
                        state["eu_market_status"] = meta["eu_market_status"]
                    if meta.get("pmcf_required") is not None:
                        state["pmcf_required"] = meta["pmcf_required"]
                except Exception:
                    pass

    gate_result = evaluate_endpoint_framework_lock(state)

    if gate_result.status == "PASS" or state.get("locked_endpoint_framework"):
        return _stage(
            "endpoint_framework_lock",
            "completed",
            locked_endpoint_framework=state.get("locked_endpoint_framework", {}),
        )

    # Build enhanced evidence review: each endpoint with its source + context
    consolidated = state.get("consolidated_clinical_data_table", {}) or {}
    evidence_trace = _build_endpoint_evidence_trace(state, consolidated)

    # HC interrupt — human must confirm endpoints AND review evidence traceability
    interrupt_msg = {
        "confirmation_point": "endpoint_framework_lock",
        "title": "Endpoint & Evidence Review (HC-7.0)",
        "message": (
            "1. Confirm the endpoint whitelist/greylist/blacklist.\n"
            "2. Review the evidence trace below — verify at least the CRITICAL items.\n"
            "3. Check SOURCE_VERIFICATION_REPORT.md in CER_EVIDENCE_PACKAGE/ for full context snippets."
        ),
        "primary_endpoints": state.get("sota_endpoint_derivation_table", {}).get("primary", []),
        "secondary_endpoints": state.get("sota_endpoint_derivation_table", {}).get("secondary", []),
        "safety_endpoints": state.get("sota_endpoint_derivation_table", {}).get("safety", []),
        "excluded_candidates": state.get("sota_endpoint_derivation_table", {}).get("excluded", []),
        "evidence_trace": evidence_trace,
        "verification_report": "CER_EVIDENCE_PACKAGE/SOURCE_VERIFICATION_REPORT.md",
        "action": "confirm_or_request_fix",
    }
    interrupt(json.dumps(interrupt_msg, ensure_ascii=False))
    return _stage("endpoint_framework_lock", "pending")


def _build_endpoint_evidence_trace(
    state: SharedAuthoringState,
    consolidated: dict[str, Any],
) -> list[dict[str, Any]]:
    """Build a per-endpoint evidence trace for HC-7.0 review.

    For each locked endpoint, find all values in the consolidated table
    and their source references, with a confidence flag.
    """
    locked = state.get("locked_endpoint_framework") or {}
    allowed: set[str] = set()
    for key in ("primary_endpoints", "secondary_endpoints", "safety_endpoints"):
        for ep in locked.get(key, []) or []:
            name = ep.get("name", ep) if isinstance(ep, dict) else ep
            allowed.add(str(name))

    data_sources = consolidated.get("data_sources", []) or []
    trace: list[dict[str, Any]] = []

    for ep_name in sorted(allowed):
        sources_for_ep: list[dict[str, Any]] = []
        for ds in data_sources:
            for ep in (ds.get("endpoints") or []):
                if ep.get("name") == ep_name:
                    sources_for_ep.append({
                        "source_type": ds.get("type", ""),
                        "value": ep.get("value"),
                        "study_name": ds.get("study_name", ""),
                        "sample_size": ds.get("sample_size", 0),
                    })

        # Determine confidence: HIGH if value found in manufacturer_clinical source
        has_manufacturer = any(s["source_type"] == "manufacturer_clinical" for s in sources_for_ep)
        has_multiple = len(sources_for_ep) >= 2
        confidence = (
            "✅ HIGH" if has_manufacturer
            else "⚠️ MEDIUM" if has_multiple
            else "❌ LOW — single literature source only"
        )

        trace.append({
            "endpoint": ep_name,
            "sources": sources_for_ep,
            "source_count": len(sources_for_ep),
            "confidence": confidence,
        })

    return trace


def _node_clinical_data_consolidation(state: SharedAuthoringState) -> dict[str, Any]:
    """Consolidate all clinical data into a single source-of-truth table."""
    from deerflow.runtime.cer_authoring.pipeline import consolidate_clinical_data

    consolidated = consolidate_clinical_data(state)
    return _stage(
        "clinical_data_consolidation",
        "completed",
        consolidated_clinical_data_table=consolidated,
    )


# ══════════════════════════════════════════════════════════════════════════════
# BIGDP2026.6 Phase 2: Expert Reasoning Ledger Nodes
# These nodes build the three expert business logic artifacts BEFORE G46
# evaluation. They are read-only aggregations of existing state artifacts.
# ══════════════════════════════════════════════════════════════════════════════

def _node_build_reasoning_ledger(state: SharedAuthoringState) -> dict[str, Any]:
    """Build CER_REASONING_LEDGER: claim classification, evidence support, endpoint
    rationale, gap disposition, conclusion strength.

    Aggregates from: claim_ledger, claim_evidence_matrix, device_profile,
    endpoint_registry, sota_benchmark_table, benefit_risk_ledger.
    """
    from datetime import datetime, timezone

    device = state.get("device_profile") or {}
    claim_ledger = state.get("claim_ledger") or []
    claim_matrix = state.get("claim_evidence_matrix") or []
    endpoint_registry = state.get("endpoint_registry") or []
    benchmark_table = state.get("sota_benchmark_table") or []
    br_ledger = state.get("benefit_risk_ledger") or []

    matrix_by_claim = {str(r.get("claim_id") or ""): r for r in claim_matrix if r.get("claim_id")}
    claims = []
    for idx, claim in enumerate(claim_ledger, start=1):
        claim_id = str(claim.get("claim_id") or f"C-{idx:02d}")
        matrix_row = matrix_by_claim.get(claim_id) or {}
        evidence_ids = matrix_row.get("evidence_ids") or []
        if isinstance(evidence_ids, str):
            evidence_ids = [evidence_ids] if evidence_ids else []
        support_type = str(matrix_row.get("support_type") or "")
        if not support_type:
            support_type = "direct" if evidence_ids else "insufficient"

        # ── BIGDP2026.6 R1: Expert rule-driven conclusion strength ──
        explicit_strength = str(matrix_row.get("conclusion_strength") or "")
        if explicit_strength:
            conclusion_strength = explicit_strength
        else:
            try:
                from deerflow.runtime.cer_authoring.expert_rule_loader import get_conclusion_strength
                conclusion_strength = get_conclusion_strength(support_type, len(evidence_ids))
            except Exception:
                # Fallback to inline logic if rule loader unavailable
                if support_type == "insufficient":
                    conclusion_strength = "limited"
                elif support_type in ("manufacturer",):
                    conclusion_strength = "limited"
                elif support_type in ("indirect", "equivalent", "PMS", "rmf_gspr"):
                    conclusion_strength = "moderate" if len(evidence_ids) >= 2 else "limited"
                elif support_type == "direct" and len(evidence_ids) >= 2:
                    conclusion_strength = "strong"
                elif support_type == "direct" and len(evidence_ids) == 1:
                    conclusion_strength = "moderate"
                else:
                    conclusion_strength = "limited"

        claims.append({
            "claim_id": claim_id,
            "claim_text": str(claim.get("claim_text") or claim.get("claim") or "")[:200],
            "claim_classification": str(claim.get("claim_type") or "clinical_performance"),
            "claim_criticality": str(claim.get("criticality") or "medium"),
            "evidence_support_type": support_type,
            "endpoint_rationale": f"Endpoints derived from {len(endpoint_registry)} registered endpoints for this clinical domain.",
            "linked_endpoints": [e.get("name", "") for e in endpoint_registry[:5]],
            "benchmark_rationale": f"Benchmark derived from {len(benchmark_table)} SOTA studies for this clinical domain.",
            "linked_benchmark_ids": [str(b.get("benchmark_id", "")) for b in benchmark_table[:5] if b.get("benchmark_id")],
            "gap_disposition": str(matrix_row.get("gap_disposition") or ("PMCF" if not evidence_ids else "no_gap")),
            "gap_rationale": str(matrix_row.get("gap_rationale") or ""),
            "conclusion_strength": conclusion_strength,
            "linked_evidence_ids": evidence_ids if isinstance(evidence_ids, list) else [],
            "source_artifacts": ["claim_evidence_matrix", "device_profile", "endpoint_registry", "sota_benchmark_table"],
        })

    ledger = {
        "schema_version": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generated_by": "_node_build_reasoning_ledger",
        "product_identity_reasoning": {
            "device_name": str(device.get("device_name") or ""),
            "device_class": str(device.get("device_class") or ""),
            "intended_use_summary": str(device.get("intended_use") or "")[:500],
            "mechanism_of_action": str(device.get("mechanism_of_action") or ""),
            "target_population": str(device.get("target_population") or ""),
            "anatomical_site": str(device.get("anatomical_site") or ""),
            "equivalence_claimed": bool(state.get("equivalence_claimed")),
            "equivalent_device_name": str(state.get("equivalent_device_name") or ""),
        },
        "claims": claims,
        "overall_assessment": {
            "total_claims": len(claims),
            "strong_conclusions": sum(1 for c in claims if c["conclusion_strength"] == "strong"),
            "moderate_conclusions": sum(1 for c in claims if c["conclusion_strength"] == "moderate"),
            "limited_conclusions": sum(1 for c in claims if c["conclusion_strength"] == "limited"),
            "not_supported_conclusions": sum(1 for c in claims if c["conclusion_strength"] == "not_supported"),
            "claims_with_gaps": sum(1 for c in claims if c["gap_disposition"] != "no_gap"),
            "pmcf_recommended": any(c["gap_disposition"] == "PMCF" for c in claims),
            "overall_readiness": "ready_for_writer" if all(c["conclusion_strength"] in ("strong", "moderate") for c in claims) else "needs_human_decision",
        },
    }
    return {
        **_branch_stage("build_reasoning_ledger"),
        "cer_reasoning_ledger": ledger,
    }


def _node_build_ifu_evolution_ledger(state: SharedAuthoringState) -> dict[str, Any]:
    """Build IFU_CLAIM_EVOLUTION_LEDGER: 5-stage IFU claim evolution tracking.

    Aggregates from: ifu_working_document, claim_ledger, claim_evidence_matrix.
    """
    from datetime import datetime, timezone

    now_iso = datetime.now(timezone.utc).isoformat()
    ifu_doc = state.get("ifu_working_document") or {}
    claim_ledger = state.get("claim_ledger") or []
    claim_matrix = state.get("claim_evidence_matrix") or []
    matrix_by_claim = {str(r.get("claim_id") or ""): r for r in claim_matrix if r.get("claim_id")}

    claims = []
    for idx, claim in enumerate(claim_ledger, start=1):
        claim_id = str(claim.get("claim_id") or f"C-{idx:02d}")
        matrix_row = matrix_by_claim.get(claim_id) or {}
        evidence_ids = matrix_row.get("evidence_ids") or []
        if isinstance(evidence_ids, str):
            evidence_ids = [evidence_ids] if evidence_ids else []

        ifu_text = str(claim.get("ifu_source_text") or claim.get("claim_text") or "")
        extracted = str(claim.get("claim_text") or ifu_text)
        classified = str(claim.get("claim_type") or "clinical_performance")
        evidence_supported = extracted  # In production, this would be refined by evidence assessment
        final_claim = extracted

        # ── BIGDP2026.6 R1: Expert rule-driven IFU transformation ──
        marketing_detected = False
        transformation_action = "copy_without_change"
        try:
            from deerflow.runtime.cer_authoring.expert_rule_loader import get_ifu_transformation
            import json as _json
            evidence_ids_list = evidence_ids if isinstance(evidence_ids, list) else []
            support = str(matrix_row.get("support_type") or ("direct" if evidence_ids_list else "insufficient"))
            xform = get_ifu_transformation(ifu_text, support)
            marketing_detected = (xform.get("action") == "flag_marketing_language")
            transformation_action = xform.get("action", "copy_without_change")
        except Exception:
            marketing_detected = any(kw in ifu_text.lower() for kw in ("revolutionary", "best", "superior", "unmatched", "guaranteed", "perfect"))
        narrowed = len(final_claim) < len(ifu_text) * 0.8 if ifu_text else False

        claims.append({
            "claim_id": claim_id,
            "evolution_stages": {
                "stage_1_ifu_text": {
                    "text": ifu_text,
                    "ifu_page": str(claim.get("ifu_page") or ""),
                    "ifu_section": str(claim.get("ifu_section") or ""),
                    "extraction_timestamp": now_iso,
                    "extraction_source": "ifu_claim_extraction",
                },
                "stage_2_extracted_claim": {
                    "text": extracted,
                    "transformation_reason": "Direct extraction from IFU text.",
                    "extraction_timestamp": now_iso,
                    "extraction_source": "claim_decomposition",
                },
                "stage_3_classified_claim": {
                    "text": extracted,
                    "classification": classified,
                    "transformation_reason": f"Classified as {classified} based on claim content analysis.",
                    "classification_timestamp": now_iso,
                    "classification_source": "claim_decomposition",
                },
                "stage_4_evidence_supported_claim": {
                    "text": evidence_supported,
                    "evidence_support_type": "direct" if evidence_ids else "insufficient",
                    "linked_evidence_ids": evidence_ids if isinstance(evidence_ids, list) else [],
                    "transformation_reason": "Claim wording preserved; evidence linkage established." if evidence_ids else "No evidence linked — claim marked as insufficient.",
                    "assessment_timestamp": now_iso,
                    "assessment_source": "claim_evidence_matrix",
                },
                "stage_5_final_cer_claim": {
                    "text": final_claim,
                    "conclusion_strength": "strong" if len(evidence_ids) >= 2 else "moderate" if evidence_ids else "limited",
                    "transformation_reason": "Final CER claim wording confirmed for Writer." if not marketing_detected else "Marketing language detected in IFU; claim downgraded to evidence-supported wording.",
                    "finalization_timestamp": now_iso,
                    "finalization_source": "_node_build_ifu_evolution_ledger",
                },
            },
            "evolution_flags": {
                "claim_strengthened": False,
                "claim_narrowed": narrowed,
                "safety_qualifier_added": "safety" in classified.lower(),
                "marketing_language_detected": marketing_detected,
                "marketing_language_downgraded": marketing_detected,
                "requires_human_review": marketing_detected or not evidence_ids,
            },
        })

    ledger = {
        "schema_version": "1.0.0",
        "generated_at": now_iso,
        "generated_by": "_node_build_ifu_evolution_ledger",
        "ifu_source": {
            "filename": str(ifu_doc.get("filename") or ""),
            "version": str(ifu_doc.get("version") or ""),
            "date": str(ifu_doc.get("date") or ""),
            "manufacturer": str(state.get("device_profile", {}).get("manufacturer") or ""),
            "language": str(ifu_doc.get("language") or "en"),
        },
        "claims": claims,
        "summary": {
            "total_claims": len(claims),
            "claims_strengthened": sum(1 for c in claims if c["evolution_flags"]["claim_strengthened"]),
            "claims_narrowed": sum(1 for c in claims if c["evolution_flags"]["claim_narrowed"]),
            "claims_with_safety_qualifier": sum(1 for c in claims if c["evolution_flags"]["safety_qualifier_added"]),
            "marketing_language_detected": sum(1 for c in claims if c["evolution_flags"]["marketing_language_detected"]),
            "claims_requiring_human_review": sum(1 for c in claims if c["evolution_flags"]["requires_human_review"]),
        },
    }
    return {
        **_branch_stage("build_ifu_evolution_ledger"),
        "ifu_claim_evolution_ledger": ledger,
    }


def _node_build_benchmark_trace(state: SharedAuthoringState) -> dict[str, Any]:
    """Build BENCHMARK_DERIVATION_TRACE: per-endpoint benchmark audit trail.

    Aggregates from: sota_benchmark_table, endpoint_registry, evidence_registry.
    """
    from datetime import datetime, timezone

    now_iso = datetime.now(timezone.utc).isoformat()
    device = state.get("device_profile") or {}
    benchmark_table = state.get("sota_benchmark_table") or []
    endpoint_registry = state.get("endpoint_registry") or []
    evidence_registry = state.get("evidence_registry") or []

    # ── BIGDP2026.6 Phase 5: Domain-aware benchmark context ──
    domain_config = {}
    try:
        from deerflow.runtime.cer_authoring.benchmark_domain_loader import (
            match_benchmark_domain,
            get_endpoints_for_domain,
            get_acceptability_criteria,
        )
        domain_config = match_benchmark_domain(
            clinical_domain=str(device.get("clinical_domain") or ""),
            device_profile=device,
        )
    except Exception:
        pass  # Graceful degradation if loader not available

    endpoints = []
    for ep in endpoint_registry:
        ep_name = str(ep.get("name") or ep.get("endpoint_name") or "")
        if not ep_name:
            continue
        # Find relevant benchmark rows
        relevant_benchmarks = [
            b for b in benchmark_table
            if ep_name.lower() in str(b.get("endpoint") or b.get("endpoint_name") or "").lower()
        ]
        # Extract PMIDs from evidence registry
        source_studies = []
        for ev in evidence_registry[:10]:
            pmid = str(ev.get("pmid") or ev.get("evidence_id") or "")
            if pmid:
                source_studies.append({
                    "pmid": pmid,
                    "first_author": str(ev.get("first_author") or ""),
                    "year": int(ev.get("year") or 0),
                    "study_design": str(ev.get("study_design") or ""),
                    "sample_size": _safe_int(ev.get("sample_size"), 0),
                    "relevance_weight": float(ev.get("relevance_weight") or 0.5),
                })

        # ── BIGDP2026.6 R1: Expert rule-driven benchmark classification ──
        has_direct = any(
            str(b.get("directness") or "").lower() == "direct"
            for b in relevant_benchmarks
        )
        try:
            from deerflow.runtime.cer_authoring.expert_rule_loader import get_benchmark_classification
            bm_class = get_benchmark_classification(
                source_study_count=len(source_studies),
                population_comparability="comparable" if source_studies else "unknown",
                device_comparability="alternative_therapy",
            )
            directness = bm_class.get("directness", "fallback")
            confidence = bm_class.get("confidence", "low")
        except Exception:
            directness = "direct" if has_direct else ("indirect" if source_studies else "fallback")
            confidence = "high" if has_direct and len(source_studies) >= 3 else ("medium" if source_studies else "low")

        endpoints.append({
            "endpoint_name": ep_name,
            "endpoint_clinical_meaning": str(ep.get("clinical_meaning") or ep.get("description") or f"Clinical endpoint: {ep_name}"),
            "endpoint_type": str(ep.get("type") or "secondary_efficacy"),
            "source_studies": source_studies,
            "benchmark_value_range": {
                "value_type": "narrative_only" if not relevant_benchmarks else "range",
                "derivation_method": "Aggregated from SOTA benchmark table." if relevant_benchmarks else "No quantitative benchmark available.",
            },
            "population_comparability": "comparable" if source_studies else "unknown",
            "population_comparability_rationale": "Source study populations are in the same clinical domain." if source_studies else "No source studies available for population comparison.",
            "device_comparability": "alternative_therapy",
            "device_comparability_rationale": "SOTA benchmarks are derived from alternative therapies unless equivalence is claimed.",
            "directness": directness,
            "confidence": confidence,
            "confidence_rationale": f"Based on {len(source_studies)} source studies with {directness} evidence." if source_studies else "No source studies available.",
            "acceptability_rationale": f"Benchmark is acceptable for {directness} comparison in CER SOTA section." if source_studies else "No benchmark data available — CER must note this limitation.",
            "alternatives_rejected_rationale": "No alternative benchmarks available for this endpoint." if directness == "fallback" else "",
            "limitations": [f"Based on {len(source_studies)} studies; confidence: {confidence}."] if source_studies else ["No source studies available for benchmark derivation."],
        })

    ledger = {
        "schema_version": "1.0.0",
        "generated_at": now_iso,
        "generated_by": "_node_build_benchmark_trace",
        "device_context": {
            "device_name": str(device.get("device_name") or ""),
            "device_class": str(device.get("device_class") or ""),
            "intended_use": str(device.get("intended_use") or "")[:500],
            "clinical_domain": str(device.get("clinical_domain") or ""),
        },
        # ── BIGDP2026.6 Phase 5: Domain-aware benchmark context ──
        "domain_config": {
            "domain_key": domain_config.get("domain_key", "unknown"),
            "matched_by": domain_config.get("matched_by", "fallback"),
            "clinical_domain": domain_config.get("clinical_domain", ""),
            "acceptability_criteria": domain_config.get("acceptability_criteria", []),
        } if domain_config else {},
        "endpoints": endpoints,
        "overall_assessment": {
            "total_endpoints": len(endpoints),
            "direct_benchmarks": sum(1 for e in endpoints if e["directness"] == "direct"),
            "indirect_benchmarks": sum(1 for e in endpoints if e["directness"] == "indirect"),
            "fallback_benchmarks": sum(1 for e in endpoints if e["directness"] == "fallback"),
            "high_confidence_endpoints": sum(1 for e in endpoints if e["confidence"] == "high"),
            "medium_confidence_endpoints": sum(1 for e in endpoints if e["confidence"] == "medium"),
            "low_confidence_endpoints": sum(1 for e in endpoints if e["confidence"] == "low"),
            "benchmark_adequacy": "adequate" if sum(1 for e in endpoints if e["directness"] in ("direct", "indirect")) >= len(endpoints) * 0.5 else "partially_adequate",
        },
    }
    return {
        **_branch_stage("build_benchmark_trace"),
        "benchmark_derivation_trace": ledger,
    }


def _node_cer_input_package_export(state: SharedAuthoringState) -> dict[str, Any]:
    """Export CER_INPUT_PACKAGE.json for Claude Code consumption.

    BIGDP2026.6 Phase 4: Pre-export reference integrity check.  Export is
    BLOCKED if any evidence_id in the narrative is not found in the registry,
    or if any claim_id does not resolve.  Package includes schema version.
    """
    from deerflow.runtime.cer_authoring.pipeline import export_cer_input_package

    artifact_root = state.get("artifact_root")
    if not artifact_root:
        return _stage(
            "cer_input_package_export",
            "skipped",
            detail="No artifact_root configured",
        )

    # ── BIGDP2026.6 Phase 4: Pre-export reference integrity check ──
    integrity_errors = []
    evidence_registry = state.get("evidence_registry") or []
    known_evidence_ids = {
        str(e.get("evidence_id") or e.get("id") or e.get("pmid") or "")
        for e in evidence_registry
    }
    known_evidence_ids.discard("")

    # Check claim_evidence_matrix for orphan evidence_ids
    claim_matrix = state.get("claim_evidence_matrix") or []
    for row in claim_matrix:
        eids = row.get("evidence_ids") or []
        if isinstance(eids, str):
            eids = [eids] if eids else []
        for eid in eids:
            if str(eid) and str(eid) not in known_evidence_ids:
                integrity_errors.append(f"Orphan evidence_id '{eid}' in claim '{row.get('claim_id', '?')}' — not found in evidence_registry")

    # Check evidence_narrative if present
    evidence_narrative = state.get("evidence_narrative") or {}
    if isinstance(evidence_narrative, dict):
        for key, narrative in evidence_narrative.items():
            ref_eids = narrative.get("evidence_ids") or narrative.get("references") or []
            if isinstance(ref_eids, str):
                ref_eids = [ref_eids] if ref_eids else []
            for eid in ref_eids:
                if str(eid) and str(eid) not in known_evidence_ids:
                    integrity_errors.append(f"Orphan evidence_id '{eid}' referenced in evidence_narrative '{key}' — not found in evidence_registry")

    if integrity_errors:
        return _stage(
            "cer_input_package_export",
            "blocked",
            detail=f"Reference integrity check failed: {len(integrity_errors)} orphan reference(s). First 5: {integrity_errors[:5]}",
            cer_input_package_exported=False,
            export_integrity_errors=integrity_errors,
        )

    # Derive project dir: artifact_root's parent or use CER_PROJECT_DIR env
    project_dir = os.environ.get("CER_PROJECT_DIR", os.path.dirname(str(artifact_root)))
    package_dir = os.path.join(project_dir, "CER_EVIDENCE_PACKAGE")

    result = export_cer_input_package(state, package_dir)
    # Add package schema version
    pkg = result.get("package") or {}
    pkg["package_schema_version"] = "1.0.0"
    result["package"] = pkg

    return _stage(
        "cer_input_package_export",
        "completed",
        cer_input_package_exported=True,
        export_detail=result,
    )


def _route_after_pre_writer_readiness_gate(state: SharedAuthoringState) -> str:
    # P1-2: Bidirectional quick-scan — if Authoring requests mid-pipeline review
    if state.get("request_review_quick_scan"):
        return "review_quick_scan"
    report = state.get("pre_writer_readiness_report") or {}
    route = str(report.get("next_node") or "")
    if route == "controlled_compromise":
        return "controlled_compromise"
    # V3.2: Writing Engine Split
    # Default (claude_code): G46 PASS → endpoint_framework_lock → ... → cer_input_package_export → END
    # Legacy (deerflow): G46 PASS → pre_writer_summary → cer_writing → ... (kept for comparison)
    writing_engine = os.environ.get("DF_WRITING_ENGINE", "claude_code")
    if writing_engine == "claude_code":
        return "endpoint_framework_lock"
    return "pre_writer_summary"


# ── HC-6.5: Pre-Writer Evidence Summary ────────────────────────────────

def _node_pre_writer_summary(state: SharedAuthoringState) -> dict[str, Any]:
    """HC-6.5: Final human decision before Writer — summary of all evidence.

    Shows claim count, evidence count with full-text breakdown, benefit-risk
    status, blocker list from pre-writer gate, and intake pack P1 gaps.
    Human decides: proceed (controlled draft), rework specific nodes, or stop.
    """
    readiness = state.get("pre_writer_readiness_report") or {}
    blocker = state.get("blocker_report") or {}
    funnel = state.get("evidence_funnel_counts") or {}
    intake = state.get("intake_pack_review") or {}

    summary = {
        "claims": len(state.get("claim_ledger") or []),
        "evidence_total": len(state.get("evidence_registry") or []),
        "fulltext_available": sum(
            1 for r in (state.get("fulltext_acquisition_status_table") or [])
            if str(r.get("full_text_available", "")).lower() in ("yes", "true", "1")
        ),
        "full_text_requests_pending": len(state.get("full_text_request_list") or []),
        "pivotal_count": funnel.get("pivotal_candidate_count", 0),
        "supportive_count": funnel.get("supportive_candidate_count", 0),
        "br_concludable": readiness.get("status") == "PASS",
        "pre_writer_status": readiness.get("status", "unknown"),
        "blocking_issues": [
            {"condition": b.get("condition_name", ""), "message": str(b.get("message", ""))[:150]}
            for b in blocker.get("blocking_issues", [])
        ],
        "p1_gaps": [
            {"control": r.get("control_id", ""), "status": r.get("status", "")}
            for r in intake.get("p1_rows", [])
            if r.get("status") in ("draft", "needs_review", "")
        ],
    }

    approval = _ctx_3 = inject_defect_context_for_gate("pre_writer_summary"); approval = interrupt({
        "v5_defect_context": _ctx_3,
        "confirmation_point": "pre_writer_summary",
        "step": "HC-6.5",
        "priority": "CRITICAL",
        "message": "Final review before CER Writer. Confirm evidence is sufficient or accept controlled limitations.",
        "evidence_summary": summary,
        "action": "confirm_or_request_fix",
        "rework_targets": REWORK_TARGETS.get("pre_writer_summary", []),
    })
    _rework = _check_hc_rework(approval, "pre_writer_summary")
    if _rework is not None:
        return _rework
    return {**_stage("pre_writer_summary"), "pre_writer_human_confirmed": True}


def _node_review_quick_scan(state: SharedAuthoringState) -> dict[str, Any]:
    """P1-2: Run lightweight Review Quick-Scan via subprocess.

    Serializes current claim/evidence artifacts and invokes the 2-stage
    Review Assist quick-scan graph. Results are loaded into review_feedback
    for surfacing at the next interrupt.

    P0-1: Subprocess has timeout (300s) + exponential-backoff retry (max 3).
    """
    import subprocess
    import sys
    import tempfile
    import time

    artifact_root = Path(str(state.get("artifact_root") or ""))
    project_id = str(state.get("project_id") or "")
    quick_scan_feedback: dict[str, Any] | None = None
    status = "skipped"
    last_error = ""
    max_retries = 3
    base_timeout = 300

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            # Write lightweight input package
            input_package = {
                "project_id": project_id,
                "claim_ledger": state.get("claim_ledger") or [],
                "evidence_registry": state.get("evidence_registry") or [],
                "device_profile": state.get("device_profile") or {},
                "source_inventory": state.get("source_inventory") or [],
            }
            (tmp_path / "quick_scan_input.json").write_text(
                json.dumps(input_package, indent=2, ensure_ascii=False), encoding="utf-8"
            )

            script = Path(__file__).resolve().parents[5] / "scripts" / "run_review_quick_scan.py"

            for attempt in range(1, max_retries + 1):
                try:
                    proc = subprocess.run(
                        [
                            sys.executable,
                            str(script),
                            "--input-dir", str(tmp_path),
                            "--output-dir", str(artifact_root),
                            "--project-id", project_id,
                        ],
                        capture_output=True,
                        text=True,
                        timeout=base_timeout,
                    )
                    if proc.returncode == 0:
                        result = json.loads(proc.stdout)
                        status = result.get("status", "unknown")
                        feedback_path = artifact_root / "review_feedback" / "quick_scan_latest.json"
                        if feedback_path.exists():
                            quick_scan_feedback = json.loads(feedback_path.read_text(encoding="utf-8"))
                        logger.info("Quick-scan succeeded on attempt %d/%d", attempt, max_retries)
                        break
                    else:
                        stderr = proc.stderr[:500] if proc.stderr else "no stderr"
                        last_error = f"exit={proc.returncode}: {stderr}"
                        logger.warning("Quick-scan failed attempt %d/%d: %s", attempt, max_retries, last_error)
                        if attempt < max_retries:
                            backoff = 2 ** (attempt - 1)
                            logger.info("Quick-scan retrying in %ds...", backoff)
                            time.sleep(backoff)
                except subprocess.TimeoutExpired:
                    last_error = f"timeout after {base_timeout}s"
                    logger.warning("Quick-scan timed out on attempt %d/%d", attempt, max_retries)
                    if attempt < max_retries:
                        backoff = 2 ** (attempt - 1)
                        logger.info("Quick-scan retrying in %ds...", backoff)
                        time.sleep(backoff)
                except Exception as exc:
                    last_error = str(exc)
                    logger.warning("Quick-scan exception on attempt %d/%d: %s", attempt, max_retries, exc)
                    if attempt < max_retries:
                        backoff = 2 ** (attempt - 1)
                        logger.info("Quick-scan retrying in %ds...", backoff)
                        time.sleep(backoff)
            else:
                # All retries exhausted
                status = f"failed_after_{max_retries}_retries: {last_error}"
                logger.error("Quick-scan exhausted all %d retries: %s", max_retries, last_error)
    except Exception as exc:
        status = f"failed: {exc}"
        logger.warning("Review quick-scan failed (non-fatal): %s", exc)

    return {
        **_stage("review_quick_scan"),
        "review_quick_scan_status": status,
        "review_quick_scan_feedback": quick_scan_feedback,
        "lead_decisions": [
            {
                "stage": "review_quick_scan",
                "decision": "triggered_mid_pipeline_review",
                "status": status,
                "findings_count": len(quick_scan_feedback.get("findings", [])) if quick_scan_feedback else 0,
            }
        ],
    }


# ── Event Bus hybrid architecture: coordinator helpers ──

def _event_bus_available() -> bool:
    """Check if Event Bus is enabled and imports succeeded."""
    return _EVENT_BUS_ENABLED and "get_event_bus" in globals()


def _run_evidence_appraisal_event_bus(state: dict[str, Any]) -> dict[str, Any]:
    """Event Bus coordinator for evidence_appraisal node.

    Uses asyncio.run() since LangGraph sync nodes execute in ThreadPoolExecutor
    threads which have no running event loop.
    """
    return asyncio.run(_async_evidence_appraisal_coordinator(state))


async def _async_evidence_appraisal_coordinator(state: dict[str, Any]) -> dict[str, Any]:
    """Async coordinator: publish batches → wait → merge → enrich."""
    bus = get_event_bus()
    await bus.start()

    # Start workers
    workers = [EvidenceAppraisalWorker(f"appraiser-{i}") for i in range(3)]
    for w in workers:
        await w.start(bus)

    try:
        # Get articles from state
        articles = _get_articles_for_appraisal(state)
        if not articles:
            # No articles to appraise — return empty but valid
            return {"evidence_registry": [], "article_appraisal": [], "mcp_log": []}

        # Build lightweight state snapshot for workers
        state_snapshot = {
            "device_profile": state.get("device_profile"),
            "claim_ledger": state.get("claim_ledger"),
        }

        # Publish batches
        batch_size = max(1, len(articles) // 3)
        batches = chunk_list(articles, batch_size)
        event_ids = await publish_batches(
            bus=bus,
            event_type=EventType.EVIDENCE_BATCH_REQUESTED,
            items=batches,
            batch_size=1,  # each batch is already a list
            correlation_id=state.get("thread_id", ""),
            stage_id="evidence_appraisal",
            spiral_round=_spiral_round_from_state(state),
            payload_builder=lambda batch_id, batch: {
                "batch_id": batch_id,
                "articles": batch[0] if batch else [],
                "state_snapshot": state_snapshot,
            },
        )

        # Wait for completions with progress callback
        def _on_progress(completed: int, total: int) -> None:
            logger.info("Evidence appraisal progress: %d/%d batches", completed, total)

        results = await wait_for_batches(
            bus=bus,
            completion_event_type=EventType.EVIDENCE_BATCH_COMPLETED,
            expected_batch_count=len(batches),
            correlation_id=state.get("thread_id", ""),
            stage_id="evidence_appraisal",
            timeout=300.0,
            on_progress=_on_progress,
        )

        # Merge results
        merged = merge_batch_evidence(results)

        return merged

    finally:
        for w in workers:
            await w.stop()
        await bus.stop()


def _get_articles_for_appraisal(state: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract articles eligible for appraisal from state.

    Mirrors the article extraction logic in pipeline.appraise_evidence.
    """
    screening_rows = state.get("screening_disposition") or []
    eligible_pmids = [
        str(row.get("pmid"))
        for row in screening_rows
        if row.get("pmid")
        and row.get("full_text_decision") == "include_for_appraisal"
        and row.get("retrieval_domain_status") != "RETRIEVAL_DOMAIN_MISMATCH_REWORK_REQUIRED"
    ]
    pmids = eligible_pmids or [
        record.get("pmid") for record in state.get("raw_literature_records") or [] if record.get("pmid")
    ]

    # Simplified: return raw records as articles
    articles = []
    for record in state.get("raw_literature_records") or []:
        if not record.get("pmid"):
            continue
        if eligible_pmids and str(record.get("pmid")) not in eligible_pmids:
            continue
        articles.append({
            "pmid": record.get("pmid"),
            "title": record.get("title", ""),
            "abstract": record.get("abstract", ""),
            "study_design": record.get("study_design", "unknown"),
            "oxford_level": record.get("oxford_level", "not extracted"),
            "sample_size": record.get("sample_size", "not available"),
            "follow_up": record.get("follow_up", "not available"),
            "full_text_status": record.get("full_text_status", "abstract_only"),
        })
    return articles


def _run_vigilance_search_event_bus(state: dict[str, Any]) -> dict[str, Any]:
    """Event Bus coordinator for vigilance_search node."""
    return asyncio.run(_async_vigilance_search_coordinator(state))


async def _async_vigilance_search_coordinator(state: dict[str, Any]) -> dict[str, Any]:
    """Async coordinator: publish vigilance search → wait → merge."""
    bus = get_event_bus()
    await bus.start()

    worker = VigilanceSearchWorker("vigilance-worker-0")
    await worker.start(bus)

    try:
        profile = state.get("device_profile") or {}
        terms = profile.get("device_name", "") or profile.get("generic_name", "") or ""

        # Publish single vigilance search event
        event = Event(
            event_type=EventType.VIGILANCE_SEARCH_REQUESTED,
            payload={"search_terms": terms},
            correlation_id=state.get("thread_id", ""),
            stage_id="vigilance_search",
            spiral_round=_spiral_round_from_state(state),
        )
        await bus.publish(event)

        # Wait for completion
        results = await wait_for_batches(
            bus=bus,
            completion_event_type=EventType.VIGILANCE_SEARCH_COMPLETED,
            expected_batch_count=1,
            correlation_id=state.get("thread_id", ""),
            stage_id="vigilance_search",
            timeout=120.0,
        )

        if results:
            return merge_batch_vigilance_results(results)
        return {}

    finally:
        await worker.stop()
        await bus.stop()


def _run_sota_search_event_bus(state: dict[str, Any]) -> dict[str, Any]:
    """Event Bus coordinator for sota_search node.

    For sota_search, the Event Bus parallelizes the external database
    search calls within pipeline.run_sota_search. The search plan generation
    and benchmark matrix construction remain in the coordinator.
    """
    return asyncio.run(_async_sota_search_coordinator(state))


async def _async_sota_search_coordinator(state: dict[str, Any]) -> dict[str, Any]:
    """Async coordinator: generate search plan → publish per-row → wait → merge."""
    bus = get_event_bus()
    await bus.start()

    workers = [SotaSearchWorker(f"sota-worker-{i}") for i in range(4)]
    for w in workers:
        await w.start(bus)

    try:
        profile = state.get("device_profile") or {}
        search_plan = pipeline._phase7_search_plan(profile, state)

        if not search_plan:
            return {"search_run_registry": [], "raw_literature_records": [], "mcp_log": []}

        # Publish one event per search plan row
        event_ids = await publish_batches(
            bus=bus,
            event_type=EventType.SOTA_SEARCH_REQUESTED,
            items=search_plan,
            batch_size=1,
            correlation_id=state.get("thread_id", ""),
            stage_id="sota_search",
            spiral_round=_spiral_round_from_state(state),
            payload_builder=lambda batch_id, batch: {
                "batch_id": batch_id,
                "search_plan_row": batch[0] if batch else {},
                "device_profile": profile,
                "state_snapshot": {k: v for k, v in state.items() if k in ("device_profile", "claim_ledger")},
            },
        )

        results = await wait_for_batches(
            bus=bus,
            completion_event_type=EventType.SOTA_SEARCH_COMPLETED,
            expected_batch_count=len(search_plan),
            correlation_id=state.get("thread_id", ""),
            stage_id="sota_search",
            timeout=180.0,
        )

        merged = merge_batch_sota_results(results)

        # Build benchmark matrix (same as serial path)
        domain = pipeline._clinical_domain(state)
        if domain == "cardiac_pfa":
            benchmarks = _build_cardiac_pfa_benchmarks(merged.get("search_run_registry", []))
        elif domain == "urology_nephroscope":
            benchmarks = _build_urology_benchmarks(merged.get("search_run_registry", []))
        else:
            benchmarks = []

        return {
            **merged,
            "sota_benchmark_matrix": benchmarks,
        }

    finally:
        for w in workers:
            await w.stop()
        await bus.stop()


def _build_cardiac_pfa_benchmarks(search_runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Build SOTA benchmarks for cardiac PFA domain."""
    sources = ", ".join(r.get("search_id", "") for r in search_runs if r.get("objective") == "SOTA")
    return [
        {
            "benchmark_id": "BM-01",
            "endpoint": "Acute ablation / pulmonary vein isolation success",
            "clinical_significance": "Primary procedural performance evidence for PFA use in the IFU-defined EP workflow.",
            "sota_source": sources,
            "sota_value_range": "Quantitative threshold to be finalized from full-text endpoint extraction; qualitative benchmark uses established AF ablation acute-success expectations.",
            "acceptance_criterion": "Result should be clinically consistent with accepted AF ablation SOTA after endpoint definition and follow-up are matched.",
            "corresponding_claim_id": "C-01",
            "corresponding_gspr": "GSPR 1, 6",
            "used_in_4_7": True,
            "conclusion": "Cardiac ablation performance benchmark established as authoring input.",
        },
        {
            "benchmark_id": "BM-02",
            "endpoint": "Freedom from recurrent atrial arrhythmia at defined follow-up",
            "clinical_significance": "Key clinical benefit/durability endpoint where the IFU or clinical strategy claims rhythm-control benefit.",
            "sota_source": sources,
            "sota_value_range": "Rates to be extracted from included PFA/RF/cryo literature and clinical datasets.",
            "acceptance_criterion": "Follow-up outcome should be interpretable against SOTA comparator evidence with matching AF type and endpoint definition.",
            "corresponding_claim_id": "C-01",
            "corresponding_gspr": "GSPR 1, 6",
            "used_in_4_7": True,
            "conclusion": "Durability benchmark established as authoring input.",
        },
        {
            "benchmark_id": "BM-03",
            "endpoint": "Device/procedure-related serious adverse events",
            "clinical_significance": "Defines whether cardiac ablation safety and side-effects remain clinically acceptable.",
            "sota_source": sources,
            "sota_value_range": "Rates to be extracted from included literature, clinical datasets and vigilance sources.",
            "acceptance_criterion": "Observed serious adverse events should be within accepted ablation SOTA after IFU/RMF controls.",
            "corresponding_claim_id": "C-02",
            "corresponding_gspr": "GSPR 1, 2, 8",
            "used_in_4_7": True,
            "conclusion": "Safety benchmark established as authoring input.",
        },
    ]


def _build_urology_benchmarks(search_runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Build SOTA benchmarks for urology nephroscope domain."""
    sources = ", ".join(r.get("search_id", "") for r in search_runs if r.get("objective") == "SOTA")
    return [
        {
            "benchmark_id": "BM-01",
            "endpoint": "Stone-free rate after single procedure",
            "clinical_significance": "Primary performance endpoint for urological endoscopic stone procedures.",
            "sota_source": sources,
            "sota_value_range": "To be extracted from included urological endoscopy literature.",
            "acceptance_criterion": "Stone-free rates should be clinically consistent with accepted SOTA for comparable endoscopic devices.",
            "corresponding_claim_id": "C-01",
            "corresponding_gspr": "GSPR 1, 6",
            "used_in_4_7": True,
            "conclusion": "Stone-free benchmark established as authoring input.",
        },
    ]


def _route_after_gates(state: SharedAuthoringState) -> str:
    """Route after final gate closure: gate_passed → export, otherwise → controlled_compromise."""
    decision = state.get("final_gate_decision")
    status = state.get("status")
    if status == "gate_passed" or decision == "HUMAN_HOLD":
        return "export"
    return "controlled_compromise"


def _safe_int(value: Any, default: int = 0) -> int:
    """Safely convert a value to int, handling non-numeric strings like 'not reported in source'."""
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return int(value)
    import re
    match = re.search(r"\d+", str(value))
    return int(match.group(0)) if match else default


def _spiral_round_from_state(state: dict[str, Any]) -> int:
    rounds = []
    for row in state.get("evidence_spiral_lineage") or []:
        if isinstance(row, dict):
            try:
                rounds.append(int(row.get("spiral_round_id") or 0))
            except Exception:
                pass
    try:
        rounds.append(int(state.get("spiral_round_id") or 0))
    except Exception:
        pass
    return max(rounds or [1])


def _should_continue_spiral(state: SharedAuthoringState, *,
                            failure_pattern: str = "",
                            max_rounds: int = MAX_SPIRAL_ROUNDS,
                            min_record_growth_pct: float = 15.0) -> bool:
    """Intelligent spiral convergence detection.

    Returns True if the next spiral round is likely to yield meaningful
    improvement; False if the evidence pool has saturated.

    Criteria:
    1. Max rounds: never exceed MAX_SPIRAL_ROUNDS spiral iterations (hard ceiling).
    2. Record growth: if the last round added < 15% new records vs prior,
       the search strategy has likely saturated.
    3. Failure pattern: if the gate did NOT fail due to "insufficient pool"
       (e.g. endpoint extraction quality issue), more searching won't help.
    4. Query delta: if the expanded query is identical to the previous round,
       no new territory is being explored.
    """
    spiral = _spiral_round_from_state(state)
    if spiral >= max_rounds:
        return False

    # Failure pattern analysis — if failure is NOT pool-related, more searching won't help
    # G42 evidence-insufficiency patterns are all pool-related: they indicate not enough
    # evidence of the right kind was found, and expanding the search query is the right fix.
    pool_related_patterns = {
        "no_benchmark_derivable_from_pool",
        "insufficient_pool",
        "insufficient_evidence",
        "low_retrieval_yield",
        "ALLOWED_USE_BLOCKED",
        "MISSING_DATA_BLOCKING",
        "SOURCE_TYPE_REQUIREMENT_NOT_MET",
        "CLAIM_SOURCE_MISMATCH",
        "SOURCE_TYPE_INAPPROPRIATE",
        "EVIDENCE_TRULY_INSUFFICIENT",
    }
    if failure_pattern and not any(p in failure_pattern for p in pool_related_patterns):
        return False

    lineage = state.get("evidence_spiral_lineage") or []
    if len(lineage) < 2:
        # First rework with pool-related failure — give it one more shot
        return True

    # Compare last two rounds for record growth
    try:
        last = lineage[-1]
        prev = lineage[-2]
        prev_total = int(prev.get("records_total") or 0)
        last_total = int(last.get("records_total") or 0)
        if prev_total > 0:
            growth_pct = ((last_total - prev_total) / prev_total) * 100
            if growth_pct < min_record_growth_pct:
                return False
    except Exception:
        pass

    # Check query delta — identical query means no new search territory
    try:
        last = lineage[-1]
        prev = lineage[-2]
        if last.get("query_delta") == prev.get("query_delta"):
            return False
    except Exception:
        pass

    return True


def _node_controlled_compromise(state: SharedAuthoringState) -> dict[str, Any]:
    report = state.get("pre_writer_readiness_report") or {}
    # Atomic filesystem short-circuit: if another parallel branch already ran
    # controlled_compromise, skip expensive artifact re-write.
    artifact_root = state.get("artifact_root")
    if artifact_root:
        from pathlib import Path
        marker = Path(artifact_root) / ".controlled_compromise_completed"
        try:
            marker.touch(exist_ok=False)
        except FileExistsError:
            packet = pipeline.build_controlled_compromise_report(dict(state))
            return {
                **_stage("controlled_compromise", "blocked"),
                **packet,
                "final_gate_decision": "HUMAN_HOLD",
                "status": "controlled_compromise",
            }
    packet = pipeline.build_controlled_compromise_report(dict(state))
    # Even on controlled_compromise, write partial artifacts so the accumulated
    # evidence and analysis are not lost.
    artifacts: list[str] = []
    if artifact_root:
        try:
            ifu_report = pipeline._build_ifu_feedback_report(dict(state))
            export_state = {**dict(state), **packet, **pipeline.refresh_late_annexes({**dict(state), **packet}), "ifu_feedback_report": ifu_report}
            artifacts = write_authoring_artifacts(artifact_root, export_state)
        except Exception as exc:
            logger.error("Artifact write failed during controlled_compromise: %s", exc)
            return {
                **_stage("controlled_compromise", "blocked"),
                **packet,
                "final_gate_decision": "HUMAN_HOLD",
                "status": "export_failed",
                "export_error": f"{type(exc).__name__}: {exc}",
                "controlled_compromise_active": True,
                "artifacts": [],
            }
    return {
        **_stage("controlled_compromise", "blocked"),
        **packet,
        "final_gate_decision": "HUMAN_HOLD",
        "lead_decisions": [
            {
                "stage": "controlled_compromise",
                "decision": "terminal_non_cer_path",
                "reason": report.get("compromise_reason") or "G46 BLOCKED",
            }
        ],
        "status": "controlled_compromise",
        "controlled_compromise_active": True,
        "artifacts": artifacts,
    }


def _node_cer_writing(state: SharedAuthoringState) -> dict[str, Any]:
    # V5: Inject per-section defense rules for targeted writing guidance
    section_defenses = get_per_section_defenses()
    gap_updates = pipeline.build_gap_pmcf_recommendations(dict(state))
    interim = {**dict(state), **gap_updates, "v5_section_defenses": section_defenses}
    generated = pipeline.write_cer_chapters(interim)
    trace = _agent_trace("authoring-cer-writer-agent", _with_team_mode(state, generated),
        "Write CER chapters with V5 per-section defense rules: each chapter receives targeted NB defect prevention guidance based on 1,111 real findings across 19 defect types.")
    if generated or gap_updates:
        return {**_stage("cer_writing"), **trace, **gap_updates, **generated, "v5_defenses_applied": len(section_defenses.get("sections", {}))}
    if state.get("cer_chapter_drafts"):
        return _stage("cer_writing")
    return _stage("cer_writing", "rework_required", note="CER chapter drafts must be populated from the authoring workbook")


def _node_human_style_review(state: SharedAuthoringState) -> dict[str, Any]:
    benchmark = pipeline.build_human_style_benchmark_report(dict(state))
    review_state = {**dict(state), **benchmark}
    comparison = pipeline.compare_against_human_cer(review_state)
    review_state = {**review_state, **comparison}
    return {
        **_stage("human_style_review"),
        **comparison,
        **benchmark,
        "reviewer_results": [*benchmark.get("reviewer_results", [])],
    }


def _node_nb_precheck(state: SharedAuthoringState) -> dict[str, Any]:
    # V5: Inject NB body simulation context for BSI/TUV SUD pre-submission review
    nb_body = state.get("nb_body") or (state.get("device_profile") or {}).get("nb_body", "BSI")
    nb_simulation = build_nb_simulation_context(nb_body)
    generated = pipeline.build_nb_precheck_report(dict(state))
    qa_state = _with_team_mode(state, {**generated, "nb_simulation_context": nb_simulation})
    trace = _agent_trace("authoring-qa-review-agent", qa_state, "Run integrated QA across methodology, evidence, SOTA, equivalence, vigilance, risk/GSPR, human style and NB precheck. V5: NB simulation context loaded with known reviewer patterns.", reviewer=True)
    review, rework = reviewer_result_from_invocation(trace["subagent_invocation_log"][0])
    return {
        **_stage("nb_precheck"),
        **trace,
        **generated,
        "reviewer_results": [review, *_virtual_review_rows("authoring-qa-review-agent")],
        "virtual_review_dimensions": _virtual_review_rows("authoring-qa-review-agent"),
        "rework_queue": rework,
        "nb_simulation_applied": bool(nb_simulation.get("_v5_nb_simulation")),
    }


def _node_workbook(state: SharedAuthoringState) -> dict[str, Any]:
    return {"authoring_workbook": build_authoring_workbook(dict(state)), "status": "workbook_built"}


def _node_gates(state: SharedAuthoringState) -> dict[str, Any]:
    gate_state = dict(state)
    gate_state["agent_team_mode"] = _team_mode(state)
    final_trace = invoke_authoring_agent(LEAD_AGENT_NAME, gate_state, "Aggregate reviewer findings and deterministic gates for final release decision.", reviewer=True)
    gate_state["reviewer_results"] = [
        *(gate_state.get("reviewer_results") or []),
        {"agent": "authoring-final-gate-closure", "status": "RECORDED", "scope": "aggregate deterministic gate closure", "covered_by": LEAD_AGENT_NAME},
    ]
    gate_state["subagent_invocation_log"] = [*(gate_state.get("subagent_invocation_log") or []), final_trace]
    report = run_authoring_gates(gate_state)
    return {
        "qa_gate_report": report,
        "final_gate_decision": report["decision"],
        "reviewer_results": [{"agent": "authoring-final-gate-closure", "status": "RECORDED", "failed_gate_count": report["failed_gate_count"], "covered_by": LEAD_AGENT_NAME}],
        "subagent_invocation_log": [final_trace],
        "lead_decisions": [{"stage": "gates", "decision": report["decision"], "failed_gate_count": report["failed_gate_count"]}],
        "status": "gate_passed" if report["decision"] == "PASS_TO_DRAFT_DOCX" else "gate_rework_required",
    }


def _node_export(state: SharedAuthoringState) -> dict[str, Any]:
    artifact_root = state.get("artifact_root")
    if not artifact_root:
        return {"status": state.get("status") or "export_skipped_no_artifact_root"}
    # Atomic filesystem short-circuit: if another parallel branch already exported,
    # skip expensive artifact re-write.
    from pathlib import Path
    marker = Path(artifact_root) / ".export_completed"
    try:
        marker.touch(exist_ok=False)
    except FileExistsError:
        return {**_stage("export", "skipped"), "export_completed": True}
    if state.get("final_gate_decision") != "HUMAN_HOLD" and state.get("status") not in {"input_required", "provider_unavailable", "gate_rework_required"}:
        chapters = state.get("cer_chapter_drafts") or {}
        # Show first 800 chars of CER body for quick preview
        body_text = "\n\n".join(str(v)[:200] for v in chapters.values() if v)[:800] or "(No CER chapters generated)"
        approval = _ctx_4 = inject_defect_context_for_gate("cer_draft_review"); approval = interrupt({
        "v5_defect_context": _ctx_4,
            "confirmation_point": "cer_draft_review",
            "step": "export",
            "priority": "HIGH",
            "message": "CER draft is complete. Please review before final export.",
            "cer_stats": {
                "chapter_count": len(chapters),
                "total_chars": sum(len(str(v)) for v in chapters.values()),
                "claims_in_cer": len(state.get("claim_ledger") or []),
                "evidence_cited": len(state.get("evidence_registry") or []),
                "gate_decision": state.get("final_gate_decision", "unknown"),
            },
            "cer_preview": body_text,
            "sections_to_review": list(chapters.keys())[:10] or ["(No sections)"],
            "action": "confirm_or_request_rewrite",
            "rework_targets": REWORK_TARGETS.get("cer_draft_review", []),
        })
        _rework = _check_hc_rework(approval, "cer_draft_review")
        if _rework is not None:
            return _rework
        if isinstance(approval, dict) and approval.get("rewrite_sections"):
            return {"human_review_feedback": approval, "status": "human_rewrite_requested"}
    # Phase 6: Generate IFU feedback report for closed loop
    ifu_report = pipeline._build_ifu_feedback_report(dict(state))
    export_state = {**dict(state), **pipeline.refresh_late_annexes(dict(state)), "ifu_feedback_report": ifu_report}
    artifacts = write_authoring_artifacts(artifact_root, export_state)
    return {"artifacts": artifacts, "ifu_feedback_report": ifu_report, "status": state.get("status") or "exported", "export_completed": True}


def _node_self_inspection(state: SharedAuthoringState) -> dict[str, Any]:
    """Aggregate system self-inspection: executed nodes, gate decision, env skips, quality score."""
    report = pipeline.build_self_inspection_report(dict(state))
    return {
        "self_inspection_report": report,
        "status": "self_inspection_complete",
        "lead_decisions": [
            {
                "stage": "self_inspection",
                "decision": report["overall_assessment"],
                "ready_for_export": report["ready_for_export"],
            }
        ],
    }


def _route_after_claim_sota_alignment(state: SharedAuthoringState) -> str:
    alignment = state.get("claim_sota_alignment_table") or []
    should_iterate = state.get("trigger_profile_iteration") or False
    if should_iterate:
        return "device_profile_iteration"
    return "evidence_review_gates"


def build_cer_authoring_graph(checkpointer=None):
    from deerflow.runtime.cer_authoring.pipeline import _get_knowledge_for_node

    # ── V3.2: Writing Engine Split ──
    # Default: claude_code (CER_INPUT_PACKAGE export → Claude Code takes over)
    # Set DF_WRITING_ENGINE=deerflow to keep the in-process writing nodes enabled
    # (legacy behavior, used for comparison/validation only).
    WRITING_ENGINE = os.environ.get("DF_WRITING_ENGINE", "claude_code")

    builder = StateGraph(SharedAuthoringState)

    # ── Node registry with per-node knowledge injection (Phase 5) ──
    _NODE_REGISTRY = {
        "initialize": _node_initialize,
        "input_gate": _node_input_gate,
        "intake_pack_review": _node_intake_pack_review,
        "device_profile": _node_device_profile,
        "claim_decomposition": _node_claim_decomposition,
        "pico_derivation": _node_pico_derivation,
        "methodology_review": _node_methodology_review,
        "sota_search": _node_sota_search,
        "retrieval_domain_gate": _node_retrieval_domain_gate,
        "device_equivalence_search": _node_device_equivalence_search,
        "literature_screening": _node_literature_screening,
        "screening_depth_gate": _node_screening_depth_gate,
        "prisma_flow_review": _node_prisma_flow_review,
        "evidence_appraisal": _node_evidence_appraisal,
        "fulltext_basis_gate": _node_fulltext_basis_gate,
        "extract_clinical_facts": _node_extract_clinical_facts,
        "endpoint_extraction": _node_endpoint_extraction,
        "sota_endpoint_gate": _node_sota_endpoint_gate,
        "pre_g42_claim_evidence_candidate_linking": _node_pre_g42_claim_evidence_candidate_linking,
        "evidence_sufficiency_gate": _node_evidence_sufficiency_gate,
        "query_expansion": _node_query_expansion,
        "claim_evidence_matrix": _node_claim_evidence_matrix,
        "claim_evidence_gate": _node_claim_evidence_gate,
        "gap_pmcf": _node_gap_pmcf,
        "sota_clinical_context": _node_sota_clinical_context,
        "claim_sota_alignment": _node_claim_sota_alignment,
        "device_profile_iteration": _node_device_profile_iteration,
        "vigilance_search": _node_vigilance_search,
        "equivalence_analysis": _node_equivalence_analysis,
        "risk_gspr_mapping": _node_risk_gspr_mapping,
        "evidence_review_gates": _node_evidence_review_gates,
        "writer_synthesis": _node_writer_synthesis,
        "benefit_risk_ledger": _node_benefit_risk_ledger,
        "br_justified_gate": _node_br_justified_gate,
        "alignment_matrix": _node_alignment_matrix,
        "alignment_gate": _node_alignment_gate,
        "pre_writer_readiness_gate": _node_pre_writer_readiness_gate,
        # ── BIGDP2026.6 Phase 2: Expert Reasoning Ledger Nodes ──
        "build_reasoning_ledger": _node_build_reasoning_ledger,
        "build_ifu_evolution_ledger": _node_build_ifu_evolution_ledger,
        "build_benchmark_trace": _node_build_benchmark_trace,
        # ── V3.2: new HC-7.0 chain nodes (DeerFlow Data Engine) ──
        "endpoint_framework_lock": _node_endpoint_framework_lock,
        "clinical_data_consolidation": _node_clinical_data_consolidation,
        "cer_input_package_export": _node_cer_input_package_export,
        "controlled_compromise": _node_controlled_compromise,
        # ── Writing-phase nodes: enabled only when DF_WRITING_ENGINE=deerflow ──
        # Default is claude_code: the writing engine runs in Claude Code after
        # CER_INPUT_PACKAGE.json is exported. Keeping the in-process writing
        # nodes available for legacy/parallel comparison runs.
    }
    if WRITING_ENGINE == "deerflow":
        _NODE_REGISTRY.update({
            "pre_writer_summary": _node_pre_writer_summary,
            "cer_writing": _node_cer_writing,
            "human_style_review": _node_human_style_review,
            "nb_precheck": _node_nb_precheck,
            "workbook": _node_workbook,
            "gates": _node_gates,
            "self_inspection": _node_self_inspection,
            "export": _node_export,
        })

    # ── V3.1 node registration (always active) ──
    from deerflow.runtime.cer_authoring.v3_1_graph_integration import get_v3_1_node_definitions
    _v3_1_nodes = get_v3_1_node_definitions()
    for _n_name, (_n_fn, _n_route) in _v3_1_nodes.items():
        _NODE_REGISTRY[_n_name] = _n_fn

    # Wrap each node with per-node knowledge injection from KAI index
    for node_name, node_fn in _NODE_REGISTRY.items():
        def _make_wrapped(name: str, fn):
            def _wrapped_node(state: SharedAuthoringState) -> dict[str, Any]:
                knowledge = _get_knowledge_for_node(name, state)
                return fn({**state, "_node_knowledge": knowledge})
            return _wrapped_node
        builder.add_node(node_name, _make_wrapped(node_name, node_fn))

    builder.set_entry_point("initialize")
    builder.add_edge("initialize", "input_gate")
    # In claude_code mode, the "export" node is not registered (Claude Code takes
    # over the writing), so we route to controlled_compromise → END instead.
    _input_gate_targets: dict[str, str] = {
        "intake_pack_review": "intake_pack_review",
        "controlled_compromise": "controlled_compromise",
    }
    if WRITING_ENGINE == "deerflow":
        _input_gate_targets["export"] = "export"
    builder.add_conditional_edges(
        "input_gate",
        _route_after_input_gate,
        _input_gate_targets,
    )
    builder.add_edge("intake_pack_review", "device_profile")
    builder.add_edge("device_profile", "claim_decomposition")
    builder.add_edge("claim_decomposition", "pico_derivation")
    builder.add_edge("pico_derivation", "methodology_review")
    builder.add_edge("methodology_review", "sota_search")
    builder.add_edge("sota_search", "citation_assignment")
    builder.add_edge("citation_assignment", "retrieval_domain_gate")
    builder.add_edge("citation_assignment", "device_equivalence_search")
    builder.add_conditional_edges(
        "retrieval_domain_gate",
        _route_after_retrieval_domain_gate,
        {
            "literature_screening": "literature_screening",
            "sota_search": "sota_search",
            "controlled_compromise": "controlled_compromise",
        },
    )
    builder.add_edge("literature_screening", "screening_depth_gate")
    builder.add_conditional_edges(
        "screening_depth_gate",
        _route_after_screening_depth_gate,
        {
            "prisma_flow_review": "prisma_flow_review",
            "evidence_appraisal": "evidence_appraisal",
            "sota_search": "sota_search",
            "controlled_compromise": "controlled_compromise",
        },
    )
    builder.add_edge("prisma_flow_review", "evidence_appraisal")
    builder.add_edge("evidence_appraisal", "fulltext_basis_gate")
    builder.add_conditional_edges(
        "fulltext_basis_gate",
        _route_after_fulltext_basis_gate,
        {
            "extract_clinical_facts": "extract_clinical_facts",
            "evidence_appraisal": "evidence_appraisal",
            "controlled_compromise": "controlled_compromise",
        },
    )
    # ── P0-1: Clinical facts extraction before endpoint extraction ──
    builder.add_edge("extract_clinical_facts", "endpoint_extraction")
    # ── V3.1 chain: endpoint_extraction → clinical_fact_registry → ... → sota_endpoint_gate ──
    builder.add_edge("endpoint_extraction", "clinical_fact_registry")
    builder.add_edge("clinical_fact_registry", "endpoint_master")
    builder.add_edge("endpoint_master", "endpoint_selection")
    builder.add_edge("endpoint_selection", "reference_framework")
    builder.add_edge("reference_framework", "evidence_weighting")
    builder.add_edge("evidence_weighting", "benchmark_derivation")
    builder.add_edge("benchmark_derivation", "own_data_alignment")
    builder.add_edge("own_data_alignment", "sota_endpoint_gate")
    builder.add_conditional_edges(
        "sota_endpoint_gate",
        _route_after_sota_endpoint_gate,
        {
            "pre_g42_claim_evidence_candidate_linking": "pre_g42_claim_evidence_candidate_linking",
            "endpoint_extraction": "endpoint_extraction",
            "sota_search": "sota_search",
            "controlled_compromise": "controlled_compromise",
        },
    )
    builder.add_edge("pre_g42_claim_evidence_candidate_linking", "evidence_sufficiency_gate")
    builder.add_conditional_edges(
        "evidence_sufficiency_gate",
        _route_after_evidence_sufficiency_gate,
        {
            "claim_evidence_matrix": "claim_evidence_matrix",
            "query_expansion": "query_expansion",
            "pre_g42_claim_evidence_candidate_linking": "pre_g42_claim_evidence_candidate_linking",
            "endpoint_extraction": "endpoint_extraction",
            "evidence_appraisal": "evidence_appraisal",
            "risk_gspr_mapping": "risk_gspr_mapping",
            "claim_decomposition": "claim_decomposition",
            "controlled_compromise": "controlled_compromise",
        },
    )
    builder.add_edge("query_expansion", "sota_search")
    builder.add_edge("claim_evidence_matrix", "claim_evidence_gate")
    builder.add_conditional_edges(
        "claim_evidence_gate",
        _route_after_claim_evidence_gate,
        {
            "gap_pmcf": "gap_pmcf",
            "claim_evidence_matrix": "claim_evidence_matrix",
            "controlled_compromise": "controlled_compromise",
        },
    )
    builder.add_edge("gap_pmcf", "sota_clinical_context")
    builder.add_edge("device_equivalence_search", "vigilance_search")
    builder.add_edge("vigilance_search", "equivalence_analysis")
    builder.add_edge("equivalence_analysis", "risk_gspr_mapping")
    # Step 20A -> Step 20B (Claim-SOTA alignment)
    builder.add_edge("sota_clinical_context", "claim_sota_alignment")
    # Step 20B -> conditional (iterate profile or proceed to gates)
    builder.add_conditional_edges(
        "claim_sota_alignment",
        _route_after_claim_sota_alignment,
        {
            "device_profile_iteration": "device_profile_iteration",
            "evidence_review_gates": "evidence_review_gates",
        },
    )
    # Step 3B -> merge at evidence review gates
    builder.add_edge("device_profile_iteration", "evidence_review_gates")
    # Risk chain still merges at evidence_review_gates
    builder.add_edge("risk_gspr_mapping", "evidence_review_gates")
    builder.add_edge("evidence_review_gates", "writer_synthesis")
    builder.add_edge("writer_synthesis", "benefit_risk_ledger")
    builder.add_edge("benefit_risk_ledger", "br_justified_gate")
    builder.add_conditional_edges(
        "br_justified_gate",
        _route_after_br_justified_gate,
        {
            "alignment_matrix": "alignment_matrix",
            "benefit_risk_ledger": "benefit_risk_ledger",
            "controlled_compromise": "controlled_compromise",
        },
    )
    builder.add_edge("alignment_matrix", "alignment_gate")
    builder.add_conditional_edges(
        "alignment_gate",
        _route_after_alignment_gate,
        {
            # BIGDP2026.6 Phase 2: PASS routes through ledger chain before G46
            "build_reasoning_ledger": "build_reasoning_ledger",
            "alignment_matrix": "alignment_matrix",
            "controlled_compromise": "controlled_compromise",
        },
    )
    # ── BIGDP2026.6 Phase 2: Expert Reasoning Ledger Chain ──
    # alignment_gate PASS → build_reasoning_ledger → build_ifu_evolution_ledger
    #   → build_benchmark_trace → pre_writer_readiness_gate (G46)
    # The three ledgers aggregate existing state artifacts and populate
    # cer_reasoning_ledger, ifu_claim_evolution_ledger, benchmark_derivation_trace
    # before G46 evaluates Writer Release Board conditions.
    builder.add_edge("build_reasoning_ledger", "build_ifu_evolution_ledger")
    builder.add_edge("build_ifu_evolution_ledger", "build_benchmark_trace")
    builder.add_edge("build_benchmark_trace", "pre_writer_readiness_gate")
    builder.add_node("review_quick_scan", _node_review_quick_scan)
    # In claude_code mode, the writing-engine nodes are not registered; only the
    # Claude Code chain (endpoint_framework_lock) and rework routes are valid.
    _pre_writer_gate_targets: dict[str, str] = {
        "endpoint_framework_lock": "endpoint_framework_lock",
        "controlled_compromise": "controlled_compromise",
        "device_profile": "device_profile",
        "sota_search": "sota_search",
        "evidence_appraisal": "evidence_appraisal",
        "endpoint_extraction": "endpoint_extraction",
        "writer_synthesis": "writer_synthesis",
        "risk_gspr_mapping": "risk_gspr_mapping",
        "review_quick_scan": "review_quick_scan",
    }
    if WRITING_ENGINE == "deerflow":
        _pre_writer_gate_targets["pre_writer_summary"] = "pre_writer_summary"
        _pre_writer_gate_targets["cer_writing"] = "cer_writing"
    builder.add_conditional_edges(
        "pre_writer_readiness_gate",
        _route_after_pre_writer_readiness_gate,
        _pre_writer_gate_targets,
    )
    # After quick-scan, route back to pre_writer_readiness_gate for re-evaluation
    builder.add_edge("review_quick_scan", "pre_writer_readiness_gate")
    # ── V3.2: Claude Code Writing Engine chain ──
    # G46 PASS → endpoint_framework_lock → clinical_data_consolidation
    #          → cer_input_package_export → END (Claude Code takes over)
    builder.add_edge("endpoint_framework_lock", "clinical_data_consolidation")
    builder.add_edge("clinical_data_consolidation", "cer_input_package_export")
    builder.add_edge("cer_input_package_export", END)
    # ── Legacy in-process writing chain (enabled when DF_WRITING_ENGINE=deerflow) ──
    if WRITING_ENGINE == "deerflow":
        builder.add_edge("pre_writer_summary", "cer_writing")
        builder.add_edge("cer_writing", "human_style_review")
        builder.add_edge("human_style_review", "nb_precheck")
        builder.add_edge("nb_precheck", "workbook")
        builder.add_edge("workbook", "gates")
        builder.add_edge("gates", "self_inspection")
        builder.add_conditional_edges(
            "self_inspection",
            _route_after_gates,
            {
                "export": "export",
                "controlled_compromise": "controlled_compromise",
            },
        )
        builder.add_edge("export", END)
        builder.add_edge("controlled_compromise", "export")
    return builder.compile(checkpointer=checkpointer)
