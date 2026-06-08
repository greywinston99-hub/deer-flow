"""Circuit Breaker for MCP and external API calls.

Prevents cascading failures by temporarily blocking calls to a service
that has recently failed repeatedly. The breaker has three states:

- CLOSED: Normal operation, calls pass through.
- OPEN: Calls are rejected immediately (fail-fast) for a cooldown period.
- HALF_OPEN: After cooldown, one probe call is allowed to test recovery.

Usage:
    from deerflow.runtime.cer_authoring.circuit_breaker import CircuitBreaker

    breaker = CircuitBreaker(name="nb-check", failure_threshold=3, cooldown_seconds=10)

    try:
        result = breaker.call(mcp_tools.call_tool, "nb-check", "appraise_evidence", {...})
    except CircuitBreakerOpenError:
        # Service is temporarily unavailable due to recent failures
        return fallback_result
"""

from __future__ import annotations

import logging
import threading
import time
from enum import Enum
from typing import Any, Callable

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreakerOpenError(RuntimeError):
    """Raised when a call is rejected because the circuit breaker is OPEN."""

    def __init__(self, name: str, remaining_seconds: float) -> None:
        self.name = name
        self.remaining_seconds = remaining_seconds
        super().__init__(
            f"Circuit breaker '{name}' is OPEN. "
            f"Retry after {remaining_seconds:.1f}s."
        )


class CircuitBreaker:
    """Thread-safe circuit breaker for protecting external service calls.

    Args:
        name: Identifier for logging and metrics.
        failure_threshold: Consecutive failures before opening (default 3).
        cooldown_seconds: Seconds to wait in OPEN before HALF_OPEN (default 10).
        half_open_max_calls: Max probe calls in HALF_OPEN before deciding (default 1).
        success_threshold: Consecutive successes in HALF_OPEN to close (default 1).
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 3,
        cooldown_seconds: float = 10.0,
        half_open_max_calls: int = 1,
        success_threshold: int = 1,
    ) -> None:
        self.name = name
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self.half_open_max_calls = half_open_max_calls
        self.success_threshold = success_threshold

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._half_open_calls = 0
        self._last_failure_time: float = 0.0
        self._lock = threading.Lock()

    @property
    def state(self) -> CircuitState:
        with self._lock:
            return self._state

    def call(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """Execute func(*args, **kwargs) with circuit breaker protection.

        Raises:
            CircuitBreakerOpenError: If the breaker is OPEN.
            Any exception raised by func if the breaker is CLOSED/HALF_OPEN.
        """
        with self._lock:
            if self._state == CircuitState.OPEN:
                elapsed = time.time() - self._last_failure_time
                if elapsed >= self.cooldown_seconds:
                    self._state = CircuitState.HALF_OPEN
                    self._half_open_calls = 0
                    self._success_count = 0
                    logger.info(
                        "Circuit breaker '%s' transitioned OPEN → HALF_OPEN",
                        self.name,
                    )
                else:
                    raise CircuitBreakerOpenError(self.name, self.cooldown_seconds - elapsed)

            if self._state == CircuitState.HALF_OPEN:
                if self._half_open_calls >= self.half_open_max_calls:
                    raise CircuitBreakerOpenError(
                        self.name,
                        max(0.0, self.cooldown_seconds - (time.time() - self._last_failure_time)),
                    )
                self._half_open_calls += 1

        # Execute the call outside the lock
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as exc:
            self._on_failure()
            raise

    def _on_success(self) -> None:
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.success_threshold:
                    self._state = CircuitState.CLOSED
                    self._failure_count = 0
                    logger.info(
                        "Circuit breaker '%s' transitioned HALF_OPEN → CLOSED",
                        self.name,
                    )
            elif self._state == CircuitState.CLOSED:
                self._failure_count = 0

    def _on_failure(self) -> None:
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()

            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.OPEN
                logger.warning(
                    "Circuit breaker '%s' transitioned HALF_OPEN → OPEN "
                    "(probe failed)",
                    self.name,
                )
            elif self._state == CircuitState.CLOSED:
                if self._failure_count >= self.failure_threshold:
                    self._state = CircuitState.OPEN
                    logger.warning(
                        "Circuit breaker '%s' transitioned CLOSED → OPEN "
                        "(%d consecutive failures)",
                        self.name,
                        self._failure_count,
                    )

    def force_close(self) -> None:
        """Manually reset the breaker to CLOSED (for recovery or testing)."""
        with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._success_count = 0
            self._half_open_calls = 0
            logger.info("Circuit breaker '%s' manually reset to CLOSED", self.name)


# ── Global registry for named breakers ──
_breakers: dict[str, CircuitBreaker] = {}
_breakers_lock = threading.Lock()


def get_circuit_breaker(
    name: str,
    failure_threshold: int = 3,
    cooldown_seconds: float = 10.0,
) -> CircuitBreaker:
    """Get or create a named circuit breaker.

    Breakers are shared across callers with the same name.
    """
    with _breakers_lock:
        if name not in _breakers:
            _breakers[name] = CircuitBreaker(
                name=name,
                failure_threshold=failure_threshold,
                cooldown_seconds=cooldown_seconds,
            )
        return _breakers[name]


def reset_all_breakers() -> None:
    """Reset all circuit breakers to CLOSED. Useful in tests."""
    with _breakers_lock:
        for breaker in _breakers.values():
            breaker.force_close()
