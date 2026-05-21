"""CER Runtime Hardening — Custom Exception Hierarchy

All custom exceptions for CER runtime hardening.
Business hard constraints are NOT encoded here — they are enforced at the logic layer.
"""

from __future__ import annotations


class CERHardeningError(Exception):
    """Base exception for all CER runtime hardening errors."""

    pass


# ── A. Timeout / Retry / Overload ─────────────────────────────────────────────


class AgentTimeoutError(CERHardeningError):
    """Agent invocation exceeded maximum allowed time."""

    def __init__(self, agent_name: str, timeout_sec: int, attempted: int = 1):
        self.agent_name = agent_name
        self.timeout_sec = timeout_sec
        self.attempted = attempted
        super().__init__(
            f"Agent '{agent_name}' timed out after {timeout_sec}s "
            f"(attempt {attempted}/{attempted})"
        )


class AgentRetryExhaustedError(CERHardeningError):
    """Agent invocation failed after all retry attempts."""

    def __init__(
        self,
        agent_name: str,
        attempts: int,
        last_error: str,
        final_status: str = "exhausted",
    ):
        self.agent_name = agent_name
        self.attempts = attempts
        self.last_error = last_error
        self.final_status = final_status
        super().__init__(
            f"Agent '{agent_name}' failed after {attempts} attempts. "
            f"Last error: {last_error}. Status: {final_status}"
        )


class APIOverloadError(CERHardeningError):
    """API returned 429 / 529 / overloaded error."""

    def __init__(self, agent_name: str, status_code: int, retry_after_sec: int | None = None):
        self.agent_name = agent_name
        self.status_code = status_code
        self.retry_after_sec = retry_after_sec
        super().__init__(
            f"API overload for '{agent_name}': HTTP {status_code}"
            + (f", retry after {retry_after_sec}s" if retry_after_sec else "")
        )


# ── B. Safe Resume / Replay ────────────────────────────────────────────────────


class ResumeError(CERHardeningError):
    """Cannot resume run from current state."""

    pass


class ReplayModeError(CERHardeningError):
    """Attempted a forbidden operation in replay mode."""

    pass


# ── C. Real Model Invocation Enforcement ───────────────────────────────────────


class StubDetectionError(CERHardeningError):
    """A stub model was detected in a production context."""

    def __init__(self, run_id: str, model: str, context: str):
        self.run_id = run_id
        self.model = model
        self.context = context
        super().__init__(
            f"Stub model '{model}' detected in run '{run_id}' "
            f"during {context}. Real model required."
        )


class StubRISKBenefitProhibitedError(CERHardeningError):
    """Attempted to issue RISK_BENEFIT terminal decision from stub mode."""

    def __init__(self, run_id: str, model: str, decision: str):
        self.run_id = run_id
        self.model = model
        self.decision = decision
        super().__init__(
            f"RISK_BENEFIT terminal decision '{decision}' blocked: "
            f"stub model '{model}' in run '{run_id}'"
        )


class StubModelMismatchError(CERHardeningError):
    """Execution mode and model are inconsistent."""

    pass


# ── D. Schema Validation ────────────────────────────────────────────────────────


class SchemaValidationError(CERHardeningError):
    """Agent output failed schema validation before artifact write."""

    def __init__(self, artifact_name: str, schema_name: str, details: str):
        self.artifact_name = artifact_name
        self.schema_name = schema_name
        self.details = details
        super().__init__(
            f"Artifact '{artifact_name}' failed schema '{schema_name}' "
            f"validation: {details}"
        )


class BundleIncompleteError(CERHardeningError):
    """Bundle is missing required artifacts."""

    def __init__(self, bundle_name: str, missing_artifacts: list[str]):
        self.bundle_name = bundle_name
        self.missing_artifacts = missing_artifacts
        super().__init__(
            f"Bundle '{bundle_name}' incomplete. "
            f"Missing: {', '.join(missing_artifacts)}"
        )


# ── E. Artifact Write Guarantees ────────────────────────────────────────────────


class PartialWriteError(CERHardeningError):
    """Artifact write was detected as partial (zero bytes)."""

    def __init__(self, artifact_path: str):
        self.artifact_path = artifact_path
        super().__init__(f"Partial write detected: {artifact_path} has 0 bytes")


class AtomicWriteError(CERHardeningError):
    """Atomic write (temp+rename) failed."""

    pass


# ── F. State Machine Constraints ─────────────────────────────────────────────────


class RISKBenefitGate3OnlyError(CERHardeningError):
    """Attempted RISK_BENEFIT routing to a gate other than Gate 3."""

    def __init__(self, from_state: str, to_gate: str, decision: str | None = None):
        self.from_state = from_state
        self.to_gate = to_gate
        self.decision = decision
        msg = f"RISK_BENEFIT routing forbidden: {from_state} → {to_gate}"
        if decision:
            msg += f" (decision: {decision})"
        super().__init__(msg)


class MachineTerminalRISKBenefitError(CERHardeningError):
    """A machine agent attempted to issue RISK_BENEFIT terminal decision."""

    def __init__(self, agent_name: str, decision: str):
        self.agent_name = agent_name
        self.decision = decision
        super().__init__(
            f"Machine agent '{agent_name}' issued RISK_BENEFIT terminal "
            f"decision '{decision}'. This is forbidden."
        )


# ── G. Config Validation ────────────────────────────────────────────────────────


class ConfigValidationError(CERHardeningError):
    """Workflow or config YAML failed schema validation on load."""

    pass


# ── H. Crash / Resume ──────────────────────────────────────────────────────────


class RunDegradedError(CERHardeningError):
    """Run has exceeded maximum resume attempts and is degraded."""

    def __init__(self, run_id: str, resume_count: int, max_resumes: int = 3):
        self.run_id = run_id
        self.resume_count = resume_count
        self.max_resumes = max_resumes
        super().__init__(
            f"Run '{run_id}' degraded: {resume_count} resume attempts "
            f"(max {max_resumes}). Human intervention required."
        )
