"""CER Review Guardrail Provider — Tool-call authorization policies for Review Assist.

Implements the GuardrailProvider Protocol from deerflow.guardrails.provider.
Evaluates write_file tool calls against 3 policies:
  1. cer-review-terminal-decision-block — Deny writes containing terminal verdicts
  2. cer-review-missing-evidence-block — Deny severity writes without evidence excerpts
  3. cer-review-auto-approval-block — Deny writes containing APPROVED/REJECTED

Fail-closed: provider errors result in blocked tool calls.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from deerflow.guardrails.provider import (
    GuardrailDecision,
    GuardrailReason,
    GuardrailRequest,
)

logger = logging.getLogger(__name__)

# Terminal verdict terms that must never appear in Review Assist output
_PROHIBITED_TERMS = ["PASS", "FAIL", "APPROVED", "REJECTED", "CEAR"]

# Tool names this guardrail applies to
_WRITE_TOOLS = {"write_file", "str_replace"}


class CERReviewGuardrailProvider:
    """Tool-call guardrail for CER Review Assist pipeline.

    Implements GuardrailProvider Protocol:
      - name: str
      - evaluate(request) -> GuardrailDecision
      - aevaluate(request) -> GuardrailDecision
    """

    name = "cer-review-guardrail"

    def __init__(self, *, fail_closed: bool = True):
        self._fail_closed = fail_closed

    # ── Policy: Terminal Decision Block ──────────────────────────────────────

    def _check_terminal_decision(self, tool_name: str, tool_input: dict[str, Any]) -> GuardrailDecision | None:
        """Deny write_file if content contains terminal verdict terms."""
        if tool_name not in _WRITE_TOOLS:
            return None

        content = tool_input.get("content", "") or tool_input.get("text", "")
        if not content:
            return None

        content_upper = str(content).upper()
        hits = [t for t in _PROHIBITED_TERMS if t in content_upper]
        if hits:
            return GuardrailDecision(
                allow=False,
                reasons=[
                    GuardrailReason(
                        code="cer-review.terminal_decision_blocked",
                        message=f"Write blocked: content contains prohibited terminal verdict term(s): {', '.join(hits)}. "
                        "Review Assist output must use advisory language only (PENDING, not PASS/FAIL/APPROVED/REJECTED/CEAR).",
                    )
                ],
                policy_id="cer-review-terminal-decision-block",
                metadata={"prohibited_terms_found": hits},
            )
        return None

    # ── Policy: Missing Evidence Block ───────────────────────────────────────

    def _check_evidence_requirement(self, tool_name: str, tool_input: dict[str, Any]) -> GuardrailDecision | None:
        """Deny write_file if severity is CRITICAL/HIGH but no evidence excerpt provided."""
        if tool_name not in _WRITE_TOOLS:
            return None

        content = tool_input.get("content", "") or tool_input.get("text", "")
        if not content:
            return None

        content_str = str(content)

        # Only check JSON content that has severity fields
        has_severity = "CRITICAL" in content_str or '"severity"' in content_str
        has_evidence = "evidence_excerpt" in content_str or "evidence_summary" in content_str

        if has_severity and not has_evidence:
            return GuardrailDecision(
                allow=False,
                reasons=[
                    GuardrailReason(
                        code="cer-review.missing_evidence_blocked",
                        message="Write blocked: content contains severity assessment without evidence excerpt. "
                        "All CRITICAL/HIGH findings must include evidence_excerpt or evidence_summary field.",
                    )
                ],
                policy_id="cer-review-missing-evidence-block",
            )
        return None

    # ── Policy: Auto-Approval Block ──────────────────────────────────────────

    def _check_auto_approval(self, tool_name: str, tool_input: dict[str, Any]) -> GuardrailDecision | None:
        """Deny write_file if content suggests automated approval or terminal decision."""
        if tool_name not in _WRITE_TOOLS:
            return None

        content = tool_input.get("content", "") or tool_input.get("text", "")
        if not content:
            return None

        content_str = str(content)

        # Check for auto-approval patterns in JSON reviewer_decision field
        if '"reviewer_decision"' in content_str:
            try:
                # Try to find reviewer_decision value
                import re
                match = re.search(r'"reviewer_decision"\s*:\s*"([^"]+)"', content_str)
                if match:
                    decision = match.group(1).upper()
                    if decision != "PENDING":
                        return GuardrailDecision(
                            allow=False,
                            reasons=[
                                GuardrailReason(
                                    code="cer-review.auto_approval_blocked",
                                    message=f"Write blocked: reviewer_decision is '{decision}' but must be 'PENDING'. "
                                    "Review Assist is advisory-only and cannot issue terminal decisions.",
                                )
                            ],
                            policy_id="cer-review-auto-approval-block",
                            metadata={"reviewer_decision_value": decision},
                        )
            except Exception:
                pass
        return None

    # ── Protocol Implementation ──────────────────────────────────────────────

    def evaluate(self, request: GuardrailRequest) -> GuardrailDecision:
        """Evaluate a tool call against all CER Review Assist policies.

        Returns:
            GuardrailDecision with allow=True if all policies pass,
            or allow=False with the first violation reason.
        """
        try:
            policies = [
                self._check_terminal_decision,
                self._check_evidence_requirement,
                self._check_auto_approval,
            ]

            for policy in policies:
                decision = policy(request.tool_name, request.tool_input)
                if decision is not None and not decision.allow:
                    logger.warning(
                        "Guardrail blocked tool=%s policy=%s",
                        request.tool_name,
                        decision.policy_id,
                    )
                    return decision

            return GuardrailDecision(
                allow=True,
                reasons=[GuardrailReason(code="cer-review.allowed")],
            )

        except Exception:
            logger.exception("Guardrail provider error evaluating %s", request.tool_name)
            if self._fail_closed:
                return GuardrailDecision(
                    allow=False,
                    reasons=[
                        GuardrailReason(
                            code="cer-review.evaluator_error",
                            message="Guardrail provider error (fail-closed). Tool call blocked.",
                        )
                    ],
                )

            return GuardrailDecision(
                allow=True,
                reasons=[GuardrailReason(code="cer-review.error_bypass")],
            )

    async def aevaluate(self, request: GuardrailRequest) -> GuardrailDecision:
        """Async variant — delegates to sync evaluate (no async deps)."""
        return self.evaluate(request)
