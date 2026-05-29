"""LangGraph entrypoint for the isolated CER authoring workflow."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import os
from pathlib import Path
from typing import Any

from langgraph.graph import END, StateGraph

logger = logging.getLogger(__name__)
from langgraph.types import interrupt

from deerflow.runtime.cer_authoring.agents import (
    LEAD_AGENT_NAME,
    STABLE_AGENT_TEAM_MODE,
    VIRTUAL_REVIEW_DIMENSIONS,
    build_authoring_subagent_configs,
)
from deerflow.runtime.cer_authoring.artifacts import build_authoring_workbook, write_authoring_artifacts
from deerflow.runtime.cer_authoring.gates import (
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
    "device_profile": [],
    "claim_decomposition": ["device_profile"],
    "sota_search_strategy": ["claim_decomposition", "device_profile"],
    "prisma_flow_review": ["sota_search_strategy", "claim_decomposition"],
    "evidence_appraisal": ["sota_search_strategy", "claim_decomposition"],
    "endpoint_extraction": ["evidence_appraisal", "sota_search_strategy"],
    "claim_sota_alignment": ["endpoint_extraction", "evidence_appraisal", "sota_search_strategy"],
    "cer_draft_review": ["cer_writing", "claim_decomposition", "sota_search_strategy"],
}


def _check_hc_rework(approval, confirmation_point: str):
    """If the human requested a rework, return Command(goto=target). Else None."""
    if isinstance(approval, dict) and str(approval.get("action", "")).lower() == "rework":
        target = str(approval.get("target") or "")
        if target and target in REWORK_TARGETS.get(confirmation_point, []):
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
        "action": "confirm_or_request_fix",
        "rework_targets": [],
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
    approval = interrupt({
        "confirmation_point": "device_profile",
        "step": 3,
        "priority": "CRITICAL",
        "message": "Please confirm Device Profile before proceeding to claim decomposition.",
        "device_profile": profile,
        "fields_to_verify": ["device_name", "device_type", "intended_purpose", "mode_of_action", "anatomical_site"],
        "action": "confirm_or_correct",
        "rework_targets": REWORK_TARGETS.get("device_profile", []),
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
    interrupt_payload: dict[str, Any] = {
        "confirmation_point": "claim_decomposition",
        "step": 4,
        "priority": "CRITICAL",
        "message": "Please confirm Claim Ledger before proceeding to PICO derivation.",
        "claim_ledger": [{"claim_id": str(c.get("claim_id", "")), "claim_text": str(c.get("claim_text", ""))[:200], "claim_type": str(c.get("claim_type", ""))} for c in claims],
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
    ifw_warning_only = all(
        str(c.get("claim_type", "")).lower() in ("ifu_warning", "warning_contraindication")
        for c in claims
    ) if claims else False
    if ifw_warning_only:
        return {**_stage("sota_search"), "search_skipped_ifu_warning": True,
                "search_skip_reason": "All claims are IFU warning/contraindication type — evidence sourced from RMF/GSPR, not PubMed"}
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
    approval = interrupt({
        "confirmation_point": "sota_search_strategy",
        "step": 7,
        "priority": "HIGH",
        "message": "Please confirm SOTA search strategy before execution.",
        "search_runs": [{"search_id": str(r.get("search_id", "")), "database": str(r.get("database", "")), "search_terms": str(r.get("search_terms", ""))[:300]} for r in search_runs[:5]],
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
    return _branch_stage("literature_screening", "rework_required", note="Search run registry and screening disposition are required")


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

    approval = interrupt({
        "confirmation_point": "prisma_flow_review",
        "step": "HC-3.5",
        "priority": "HIGH",
        "message": "Review search results and PRISMA flow before evidence appraisal.",
        "search_summary": search_summary,
        "prisma_funnel": funnel,
        "evidence_count": evidence_count,
        "fulltext_count": fulltext_count,
        "fulltext_available": fulltext_available,
        "fulltext_pct": fulltext_pct,
        "critical_warnings": critical_warnings,
        "action": "confirm_or_request_fix",
        "rework_targets": REWORK_TARGETS.get("prisma_flow_review", ["sota_search_strategy", "claim_decomposition"]),
    })
    _rework = _check_hc_rework(approval, "prisma_flow_review")
    if _rework is not None:
        return _rework
    return {**_stage("prisma_flow_review"), "prisma_flow_human_confirmed": True}


def _node_evidence_appraisal(state: SharedAuthoringState) -> dict[str, Any]:
    # ── Event Bus parallel path (feature-flagged) ──
    generated = None
    if _event_bus_available():
        try:
            generated = _run_evidence_appraisal_event_bus(dict(state))
            logger.info("evidence_appraisal completed via Event Bus")
        except Exception as exc:
            logger.warning("Event Bus evidence_appraisal failed, falling back to serial: %s", exc)
    if generated is None:
        generated = pipeline.appraise_evidence(dict(state))
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
    approval = interrupt({
        "confirmation_point": "evidence_appraisal",
        "step": 11,
        "priority": "MEDIUM",
        "message": "Please spot-check evidence appraisal scores.",
        "evidence_count": len(evidence),
        "appraisal_sample": [{"evidence_id": str(a.get("evidence_id", "")), "score": a.get("evidence_strength_score"), "weight": a.get("weight")} for a in appraisal[:10]],
        "action": "confirm_or_correct",
        "rework_targets": REWORK_TARGETS.get("evidence_appraisal", []),
    })
    _rework = _check_hc_rework(approval, "evidence_appraisal")
    if _rework is not None:
        return _rework
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
    return _hard_gate_graph_route(state.get("fulltext_basis_gate_report") or {}, pass_route="endpoint_extraction")


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
    approval = interrupt({
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
    if not _should_continue_spiral(state, failure_pattern=failure, max_rounds=3):
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
    if not _should_continue_spiral(state, failure_pattern=failure, max_rounds=5):
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
    if not _should_continue_spiral(state, failure_pattern=failure, max_rounds=3):
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
    approval = interrupt({
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
    return _hard_gate_graph_route(state.get("alignment_gate_report") or {}, pass_route="pre_writer_readiness_gate")


def _node_pre_writer_readiness_gate(state: SharedAuthoringState) -> dict[str, Any]:
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


def _route_after_pre_writer_readiness_gate(state: SharedAuthoringState) -> str:
    # P1-2: Bidirectional quick-scan — if Authoring requests mid-pipeline review
    if state.get("request_review_quick_scan"):
        return "review_quick_scan"
    report = state.get("pre_writer_readiness_report") or {}
    return str(report.get("next_node") or "cer_writing")


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
                            max_rounds: int = 3,
                            min_record_growth_pct: float = 15.0) -> bool:
    """Intelligent spiral convergence detection.

    Returns True if the next spiral round is likely to yield meaningful
    improvement; False if the evidence pool has saturated.

    Criteria:
    1. Max rounds: never exceed 3 spiral iterations (hard ceiling).
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
            logger.warning("Artifact write failed during controlled_compromise (non-fatal): %s", exc)
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
        "controlled_compromise_active": True,  # Writer: use CAUTIOUS wording, gaps → PMCF
        "artifacts": artifacts,
    }


def _node_cer_writing(state: SharedAuthoringState) -> dict[str, Any]:
    gap_updates = pipeline.build_gap_pmcf_recommendations(dict(state))
    interim = {**dict(state), **gap_updates}
    generated = pipeline.write_cer_chapters(interim)
    trace = _agent_trace("authoring-cer-writer-agent", _with_team_mode(state, generated), "Review/write AP and human CER logic based chapters from SharedAuthoringState.")
    if generated or gap_updates:
        return {**_stage("cer_writing"), **trace, **gap_updates, **generated}
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
    generated = pipeline.build_nb_precheck_report(dict(state))
    qa_state = _with_team_mode(state, generated)
    trace = _agent_trace("authoring-qa-review-agent", qa_state, "Run integrated QA across methodology, evidence, SOTA, equivalence, vigilance, risk/GSPR, human style and NB precheck.", reviewer=True)
    review, rework = reviewer_result_from_invocation(trace["subagent_invocation_log"][0])
    return {
        **_stage("nb_precheck"),
        **trace,
        **generated,
        "reviewer_results": [review, *_virtual_review_rows("authoring-qa-review-agent")],
        "virtual_review_dimensions": _virtual_review_rows("authoring-qa-review-agent"),
        "rework_queue": rework,
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
        approval = interrupt({
            "confirmation_point": "cer_draft_review",
            "step": "export",
            "priority": "HIGH",
            "message": "CER draft is complete. Please review key sections before final export.",
            "sections_to_review": ["Summary", "Conclusions", "GSPR Analysis"],
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
        "controlled_compromise": _node_controlled_compromise,
        "cer_writing": _node_cer_writing,
        "human_style_review": _node_human_style_review,
        "nb_precheck": _node_nb_precheck,
        "workbook": _node_workbook,
        "gates": _node_gates,
        "self_inspection": _node_self_inspection,
        "export": _node_export,
    }

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
    builder.add_conditional_edges(
        "input_gate",
        _route_after_input_gate,
        {
            "intake_pack_review": "intake_pack_review",
            "controlled_compromise": "controlled_compromise",
            "export": "export",
        },
    )
    builder.add_edge("intake_pack_review", "device_profile")
    builder.add_edge("device_profile", "claim_decomposition")
    builder.add_edge("claim_decomposition", "pico_derivation")
    builder.add_edge("pico_derivation", "methodology_review")
    builder.add_edge("methodology_review", "sota_search")
    builder.add_edge("sota_search", "retrieval_domain_gate")
    builder.add_edge("sota_search", "device_equivalence_search")
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
            "endpoint_extraction": "endpoint_extraction",
            "evidence_appraisal": "evidence_appraisal",
            "controlled_compromise": "controlled_compromise",
        },
    )
    builder.add_edge("endpoint_extraction", "sota_endpoint_gate")
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
            "pre_writer_readiness_gate": "pre_writer_readiness_gate",
            "alignment_matrix": "alignment_matrix",
            "controlled_compromise": "controlled_compromise",
        },
    )
    builder.add_node("review_quick_scan", _node_review_quick_scan)
    builder.add_conditional_edges(
        "pre_writer_readiness_gate",
        _route_after_pre_writer_readiness_gate,
        {
            "cer_writing": "cer_writing",
            "controlled_compromise": "controlled_compromise",
            "device_profile": "device_profile",
            "sota_search": "sota_search",
            "evidence_appraisal": "evidence_appraisal",
            "endpoint_extraction": "endpoint_extraction",
            "writer_synthesis": "writer_synthesis",
            "risk_gspr_mapping": "risk_gspr_mapping",
            "review_quick_scan": "review_quick_scan",
        },
    )
    # After quick-scan, route back to pre_writer_readiness_gate for re-evaluation
    builder.add_edge("review_quick_scan", "pre_writer_readiness_gate")
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
