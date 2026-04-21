"""CER Runtime Custom Exceptions — SKELETON

This module defines custom exceptions for the CER Review Runtime.
SKELETON implementation per D1 Phase 1 scaffolding requirements.
NOT production code.

D0C Contract: CER_D0C_GATE_A_PROTOCOL_ENFORCEMENT_CLOSURE.md
"""

from __future__ import annotations


class CERRuntimeError(Exception):
    """Base exception for all CER runtime errors."""
    pass


class GateAException(CERRuntimeError):
    """Raised when formal review is blocked by Gate A.

    Formal review requires gate_a_status = 'accepted'.
    Any other status blocks formal review.
    """

    def __init__(self, message: str, gate_a_status: str | None = None):
        self.gate_a_status = gate_a_status
        super().__init__(message)


class CERDocStructValidationError(CERRuntimeError):
    """Raised when CERDocStruct validation fails.

    This blocks formal review if run_mode == 'formal'.
    """

    def __init__(self, message: str, errors: list[str] | None = None):
        self.errors = errors or []
        super().__init__(message)


class WorkflowValidationError(CERRuntimeError):
    """Raised when workflow YAML validation fails.

    Blocks formal review if YAML is invalid or missing required keys.
    """

    def __init__(self, message: str, workflow_path: str | None = None):
        self.workflow_path = workflow_path
        super().__init__(message)


class BackflowStateTransitionError(CERRuntimeError):
    """Raised when backflow candidate state transition is invalid."""

    def __init__(
        self,
        event_id: str,
        current_state: str,
        attempted_state: str,
        message: str | None = None,
    ):
        self.event_id = event_id
        self.current_state = current_state
        self.attempted_state = attempted_state
        self.message = message or f"Invalid transition: {current_state} -> {attempted_state}"
        super().__init__(self.message)


class EvidencePackError(CERRuntimeError):
    """Raised when evidence pack is missing or invalid."""

    def __init__(self, pack_id: str, message: str):
        self.pack_id = pack_id
        super().__init__(message)


class LedgerWriteError(CERRuntimeError):
    """Raised when ledger artifact write fails."""

    pass


class ArtifactValidationError(CERRuntimeError):
    """Raised when artifact validation fails."""

    pass
