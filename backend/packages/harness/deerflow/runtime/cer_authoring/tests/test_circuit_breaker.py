"""Tests for the Circuit Breaker."""

from __future__ import annotations

import time
from unittest.mock import patch

import pytest

from deerflow.runtime.cer_authoring.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerOpenError,
    CircuitState,
    get_circuit_breaker,
    reset_all_breakers,
)


class TestCircuitBreaker:
    """Test circuit breaker state transitions."""

    def test_initial_state_closed(self) -> None:
        cb = CircuitBreaker("test")
        assert cb.state == CircuitState.CLOSED

    def test_success_does_not_open(self) -> None:
        cb = CircuitBreaker("test", failure_threshold=3)
        result = cb.call(lambda: "ok")
        assert result == "ok"
        assert cb.state == CircuitState.CLOSED

    def test_failure_count_increments(self) -> None:
        cb = CircuitBreaker("test", failure_threshold=3)
        with pytest.raises(RuntimeError):
            cb.call(lambda: (_ for _ in ()).throw(RuntimeError("fail")))
        assert cb._failure_count == 1
        assert cb.state == CircuitState.CLOSED

    def test_opens_after_threshold(self) -> None:
        cb = CircuitBreaker("test", failure_threshold=3)
        for _ in range(3):
            with pytest.raises(RuntimeError):
                cb.call(lambda: (_ for _ in ()).throw(RuntimeError("fail")))
        assert cb.state == CircuitState.OPEN

    def test_open_rejects_immediately(self) -> None:
        cb = CircuitBreaker("test", failure_threshold=1, cooldown_seconds=10)
        with pytest.raises(RuntimeError):
            cb.call(lambda: (_ for _ in ()).throw(RuntimeError("fail")))

        with pytest.raises(CircuitBreakerOpenError) as exc_info:
            cb.call(lambda: "ok")
        assert exc_info.value.name == "test"
        assert exc_info.value.remaining_seconds > 0

    def test_half_open_after_cooldown(self) -> None:
        cb = CircuitBreaker("test", failure_threshold=1, cooldown_seconds=0.01)
        with pytest.raises(RuntimeError):
            cb.call(lambda: (_ for _ in ()).throw(RuntimeError("fail")))
        assert cb.state == CircuitState.OPEN

        time.sleep(0.02)
        # The next call transitions to HALF_OPEN and executes
        result = cb.call(lambda: "ok")
        assert result == "ok"
        assert cb.state == CircuitState.CLOSED

    def test_half_open_failure_reopens(self) -> None:
        cb = CircuitBreaker("test", failure_threshold=1, cooldown_seconds=0.01)
        with pytest.raises(RuntimeError):
            cb.call(lambda: (_ for _ in ()).throw(RuntimeError("fail")))

        time.sleep(0.02)
        with pytest.raises(RuntimeError):
            cb.call(lambda: (_ for _ in ()).throw(RuntimeError("fail again")))
        assert cb.state == CircuitState.OPEN

    def test_force_close(self) -> None:
        cb = CircuitBreaker("test", failure_threshold=1)
        with pytest.raises(RuntimeError):
            cb.call(lambda: (_ for _ in ()).throw(RuntimeError("fail")))
        assert cb.state == CircuitState.OPEN

        cb.force_close()
        assert cb.state == CircuitState.CLOSED
        result = cb.call(lambda: "ok")
        assert result == "ok"

    def test_thread_safety(self) -> None:
        import threading

        cb = CircuitBreaker("test", failure_threshold=10)
        errors = []
        successes = []

        def worker() -> None:
            for _ in range(10):
                try:
                    cb.call(lambda: "ok")
                    successes.append(1)
                except Exception as exc:
                    errors.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(successes) == 50
        assert len(errors) == 0


class TestGlobalRegistry:
    """Test the global circuit breaker registry."""

    def test_get_circuit_breaker_creates_new(self) -> None:
        reset_all_breakers()
        cb = get_circuit_breaker("server-a")
        assert cb.name == "server-a"
        cb2 = get_circuit_breaker("server-a")
        assert cb2 is cb  # Same instance

    def test_reset_all_breakers(self) -> None:
        reset_all_breakers()
        cb = get_circuit_breaker("server-b", failure_threshold=1)
        with pytest.raises(RuntimeError):
            cb.call(lambda: (_ for _ in ()).throw(RuntimeError("fail")))
        assert cb.state == CircuitState.OPEN

        reset_all_breakers()
        assert cb.state == CircuitState.CLOSED
