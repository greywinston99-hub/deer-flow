"""CER LLM Invoker — Timeout / Retry / Overload Handling

Implements:
- Per-agent timeout control
- 429 / 529 / overloaded_error detection
- Retry with exponential backoff (有限次)
- Retry exhaustion →明确状态，不得静默失败
- 生成 runtime error artifact / log entry

Frozen baseline: CER_RUNTIME_HARDENING_PLAN_V1.md Section 1
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .exceptions import (
    AgentRetryExhaustedError,
    AgentTimeoutError,
    APIOverloadError,
)

logger = logging.getLogger(__name__)


# ── Agent Timeout Defaults ──────────────────────────────────────────────────────


AGENT_TIMEOUTS_SEC: dict[str, int] = {
    "cer_route_screen_agent": 60,
    "cer_layer1_scan_agent": 60,
    "cer_claim_scope_agent": 120,
    "cer_sota_evidence_agent": 120,
    "cer_equivalence_agent": 120,
    "cer_consistency_agent": 120,
    "cer_pmcf_lifecycle_agent": 120,
    "cer_review_package_agent": 60,
    "cer_gate_closure_agent": 60,
    "cer_intake_agent": 180,
}

DEFAULT_TIMEOUT_SEC = 180
MAX_RETRIES = 2
OVERLOAD_STATUS_CODES = {429, 529, 503}


# ── Invocation Result ─────────────────────────────────────────────────────────


@dataclass
class LLMInvocationResult:
    """Result of a single LLM invocation attempt."""

    success: bool
    raw_output: str | None = None
    parsed_output: dict[str, Any] | None = None
    agent_name: str = ""
    attempt: int = 1
    duration_sec: float = 0.0
    error: str | None = None
    error_type: str | None = None
    status_code: int | None = None  # HTTP status if applicable
    retry_after_sec: int | None = None
    model_used: str | None = None
    timestamp: str = ""


@dataclass
class LLMCallOutcome:
    """Final outcome after all retry attempts."""

    agent_name: str
    eventual_success: bool
    total_attempts: int
    total_duration_sec: float
    final_error: str | None = None
    final_status: str = "unknown"  # success | timeout_exhausted | overload | error | unknown
    invocation_results: list[LLMInvocationResult] = field(default_factory=list)
    last_error_artifact_path: str | None = None


# ── LLM Invoker ───────────────────────────────────────────────────────────────


class CERLLMInvoker:
    """CER LLM invoker with timeout, retry, and overload protection.

    Wraps any LLM client (ChatAnthropic, ChatOpenAI, etc.) and adds:
    - Per-agent timeout
    - Exponential backoff retry (max 2 retries)
    - HTTP 429/529/503 detection
    - Structured error artifact generation
    - Non-silent failure
    """

    def __init__(
        self,
        llm_client: Any,
        artifact_writer: Any | None = None,  # CERArtifactWriter
        timeout_override: dict[str, int] | None = None,
    ):
        self.llm_client = llm_client
        self.artifact_writer = artifact_writer
        self._timeouts = {**AGENT_TIMEOUTS_SEC}
        if timeout_override:
            self._timeouts.update(timeout_override)

    def invoke(
        self,
        agent_name: str,
        messages: list[dict[str, str]],
        *,
        extract_json: bool = True,
        max_retries: int = MAX_RETRIES,
        run_id: str = "unknown",
    ) -> LLMCallOutcome:
        """Invoke LLM with timeout + retry.

        Never silently fails. On retry exhaustion, returns LLMCallOutcome
        with explicit final_status and error details.
        """
        timeout_sec = self._timeouts.get(agent_name, DEFAULT_TIMEOUT_SEC)
        eventual_success = False
        total_duration = 0.0
        results: list[LLMInvocationResult] = []
        final_error = None
        final_status = "unknown"

        for attempt in range(1, max_retries + 2):  # 1..max_retries inclusive + 1 for final
            attempt_result = self._single_attempt(
                agent_name=agent_name,
                messages=messages,
                timeout_sec=timeout_sec,
                attempt=attempt,
                extract_json=extract_json,
            )
            total_duration += attempt_result.duration_sec
            results.append(attempt_result)

            if attempt_result.success:
                eventual_success = True
                final_status = "success"
                break

            final_error = attempt_result.error or "unknown"
            error_type = attempt_result.error_type or "unknown"

            # Check for overload
            if attempt_result.status_code in OVERLOAD_STATUS_CODES:
                retry_after = attempt_result.retry_after_sec or self._backoff_seconds(attempt)
                if attempt <= max_retries + 1:
                    logger.warning(
                        f"Overload HTTP {attempt_result.status_code} for "
                        f"{agent_name} attempt {attempt}, retrying after {retry_after}s"
                    )
                    time.sleep(retry_after)
                    continue
                else:
                    final_status = "overload_exhausted"

            elif error_type == "timeout":
                if attempt <= max_retries + 1:
                    backoff = self._backoff_seconds(attempt)
                    logger.warning(
                        f"Timeout for {agent_name} attempt {attempt}, "
                        f"retrying after {backoff}s"
                    )
                    time.sleep(backoff)
                    continue
                else:
                    final_status = "timeout_exhausted"

            elif error_type == "server_error":
                # Retry on 500/502 errors — server-side issues may be transient
                if attempt <= max_retries + 1:
                    backoff = self._backoff_seconds(attempt)
                    logger.warning(
                        f"Server error for {agent_name} attempt {attempt}, "
                        f"retrying after {backoff}s"
                    )
                    time.sleep(backoff)
                    continue
                else:
                    final_status = "server_error_exhausted"

            else:
                # Other errors — do not retry
                final_status = f"error_{error_type}"
                break

        if not eventual_success and final_status == "unknown":
            final_status = "exhausted"

        outcome = LLMCallOutcome(
            agent_name=agent_name,
            eventual_success=eventual_success,
            total_attempts=len(results),
            total_duration_sec=total_duration,
            final_error=final_error,
            final_status=final_status,
            invocation_results=results,
        )

        # Log final outcome
        logger.info(
            f"LLM invocation for {agent_name}: "
            f"{'SUCCESS' if eventual_success else 'FAILED'} "
            f"(status={final_status}, attempts={len(results)}, "
            f"duration={total_duration:.1f}s)"
        )

        # Generate error artifact on failure
        if not eventual_success and self.artifact_writer:
            self._write_error_artifact(
                agent_name=agent_name,
                run_id=run_id,
                outcome=outcome,
            )

        return outcome

    def _single_attempt(
        self,
        agent_name: str,
        messages: list[dict[str, str]],
        timeout_sec: int,
        attempt: int,
        extract_json: bool,
    ) -> LLMInvocationResult:
        """Execute a single LLM call attempt with timeout."""
        start = time.time()
        raw_output = None
        parsed_output = None
        error = None
        error_type = None
        status_code = None
        retry_after = None
        success = False

        try:
            # Use invoke with timeout via a signal-based approach or threading
            # For simplicity, we use a polling loop with time check
            import threading

            result_container = [None]
            error_container = [None]
            timeout_flag = [False]

            def _call():
                try:
                    result_container[0] = self.llm_client.invoke(messages)
                except Exception as e:
                    error_container[0] = e

            t = threading.Thread(target=_call, daemon=True)
            t.start()
            t.join(timeout=timeout_sec)

            if t.is_alive():
                # Thread is still running — timeout
                timeout_flag[0] = True
                error = f"Timeout after {timeout_sec}s"
                error_type = "timeout"
                # Do not join forcefully — let thread die
            elif error_container[0]:
                exc = error_container[0]
                error = str(exc)
                error_type = self._classify_error(exc)
                status_code = self._extract_status_code(exc)
                if status_code in OVERLOAD_STATUS_CODES:
                    error_type = "overload"
                retry_after = self._extract_retry_after(exc)
            else:
                raw_output = self._extract_text(result_container[0])
                if extract_json:
                    parsed_output = self._try_parse_json(raw_output)
                    if parsed_output is None:
                        error = f"Could not parse JSON from response: {raw_output[:200]}"
                        error_type = "parse_error"
                    else:
                        success = True
                else:
                    parsed_output = {"text": raw_output}
                    success = True

        except Exception as e:
            error = str(e)
            error_type = "exception"
            error_type = self._classify_error(e)

        duration = time.time() - start

        return LLMInvocationResult(
            success=success and error is None,
            raw_output=raw_output,
            parsed_output=parsed_output,
            agent_name=agent_name,
            attempt=attempt,
            duration_sec=duration,
            error=error,
            error_type=error_type,
            status_code=status_code,
            retry_after_sec=retry_after,
            model_used=getattr(self.llm_client, "model", None),
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    # ── Error Classification ───────────────────────────────────────────────

    @staticmethod
    def _classify_error(exc: Exception) -> str:
        """Classify error type for structured logging."""
        exc_str = str(exc).lower()
        if "timeout" in exc_str:
            return "timeout"
        # Check exception attributes for status code
        status_code = None
        for attr in ("status_code", "status"):
            value = getattr(exc, attr, None)
            if isinstance(value, int):
                status_code = value
                break
        # Check nested response object
        if status_code is None:
            response = getattr(exc, "response", None)
            if response is not None:
                status_code = getattr(response, "status_code", None)
        # Classify based on status code
        if status_code is not None:
            if status_code in {429, 529, 503, 504}:
                return "overload"
            if status_code == 400:
                return "bad_request"
            if status_code == 401:
                return "auth_error"
            if status_code == 403:
                return "forbidden"
            if status_code in {500, 502}:
                return "server_error"
            if status_code == 408:
                return "timeout"
        # Check string content for status codes
        if any(code in str(exc) for code in ["429", "529", "503", "504"]):
            return "overload"
        if any(code in str(exc) for code in ["400"]):
            return "bad_request"
        if "json" in exc_str or "parse" in exc_str:
            return "parse_error"
        if "auth" in exc_str or "401" in str(exc) or "403" in str(exc):
            return "auth_error"
        if "connection" in exc_str or "network" in exc_str:
            return "network_error"
        return "unknown"

    @staticmethod
    def _extract_status_code(exc: Exception) -> int | None:
        """Extract HTTP status code from exception."""
        import re
        # Check direct exception attributes first
        for attr in ("status_code", "status"):
            value = getattr(exc, attr, None)
            if isinstance(value, int):
                return value
        # Check nested response object
        response = getattr(exc, "response", None)
        if response is not None:
            status = getattr(response, "status_code", None)
            if isinstance(status, int):
                return status
        # Fall back to parsing string representation
        match = re.search(r"\b(400|401|403|408|429|500|502|503|504|529)\b", str(exc))
        if match:
            return int(match.group(1))
        return None

    @staticmethod
    def _extract_retry_after(exc: Exception) -> int | None:
        """Extract Retry-After seconds from exception."""
        import re
        match = re.search(r"retry.?after[:\s]+(\d+)", str(exc), re.IGNORECASE)
        if match:
            return int(match.group(1))
        return None

    @staticmethod
    def _backoff_seconds(attempt: int) -> int:
        """Exponential backoff: 1s, 2s."""
        return min(2 ** (attempt - 1), 8)

    # ── Thinking Block Stripping ───────────────────────────────────────────

    THOUGHT_BLOCK_PATTERN = re.compile(r"<think>[\s\S]*?</think>", re.IGNORECASE)
    THOUGHT_XML_PATTERN = re.compile(r"<thinking>[\s\S]*?</thinking>", re.IGNORECASE)

    @classmethod
    def _strip_thinking_blocks(cls, text: str) -> str:
        """Remove model thinking/reasoning blocks from text before JSON parsing.

        Models that produce extended thinking (reasoning, reflection) embed the
        thinking content in XML-like tags (<think>...</think> or <thinking>...</thinking>)
        or as plain text blocks. These corrupt JSON parsing.

        This method removes all such blocks before attempting JSON extraction.
        """
        if not text:
            return text
        text = cls.THOUGHT_BLOCK_PATTERN.sub("", text)
        text = cls.THOUGHT_XML_PATTERN.sub("", text)
        return text.strip()

    @staticmethod
    def _extract_text(response: Any) -> str:
        """Extract text from LLM response."""
        if hasattr(response, "content"):
            content = response.content
            if isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        return item.get("text", "")
            return str(content)
        return str(response)

    @staticmethod
    def _try_parse_json(text: str) -> dict[str, Any] | None:
        """Attempt to parse JSON from text.

        Handles:
        - Direct JSON text
        - JSON wrapped in ```json code blocks
        - JSON with preceding thinking/reasoning blocks (strips them first)
        - Bare JSON objects anywhere in text (last resort)
        """
        import re

        if not text:
            return None

        # Pre-process: strip thinking blocks that corrupt JSON parsing
        text = CERLLMInvoker._strip_thinking_blocks(text)

        text = text.strip()
        # Try direct parse
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        # Try extracting from markdown code blocks
        match = re.search(r"```json\s*(\{[\s\S]+?\})\s*```", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
        # Try extracting bare JSON object (strip thinking first)
        match = re.search(r"\{[\s\S]+\}", text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        return None

    # ── Error Artifact ────────────────────────────────────────────────────

    def _write_error_artifact(
        self,
        agent_name: str,
        run_id: str,
        outcome: LLMCallOutcome,
    ) -> None:
        """Write a structured error artifact for observability."""
        if not self.artifact_writer:
            return
        error_data = {
            "schema_name": "cer_llm_invocation_error",
            "schema_version": "v1",
            "agent_name": agent_name,
            "run_id": run_id,
            "eventual_success": outcome.eventual_success,
            "final_status": outcome.final_status,
            "final_error": outcome.final_error,
            "total_attempts": outcome.total_attempts,
            "total_duration_sec": outcome.total_duration_sec,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "attempts": [
                {
                    "attempt": r.attempt,
                    "success": r.success,
                    "duration_sec": r.duration_sec,
                    "error": r.error,
                    "error_type": r.error_type,
                    "status_code": r.status_code,
                    "retry_after_sec": r.retry_after_sec,
                }
                for r in outcome.invocation_results
            ],
        }
        error_path = f"00_manifest/errors/{agent_name}_{outcome.final_status}_{int(time.time())}.json"
        try:
            self.artifact_writer.atomic_write(error_path, error_data)
        except Exception:
            logger.warning(f"Could not write error artifact: {error_path}")
