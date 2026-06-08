"""Security middleware for the Event Bus.

Enforces the advisory-only constraint at the event layer.
All events must carry advisory_only=true.
No event may trigger automatic gate decisions or state overwrites.
"""

from __future__ import annotations

import logging
from typing import Callable

from deerflow.runtime.cer_authoring.event_bus.schema import Event, FORBIDDEN_EVENT_TYPES

logger = logging.getLogger(__name__)


class SecurityViolation(Exception):
    """Raised when an event violates the advisory-only security model."""

    pass


class AdvisoryOnlyMiddleware:
    """Middleware that enforces advisory-only constraints on all events.

    This middleware is applied on both publish and consume paths to ensure
    that the Event Bus can never be used to bypass LangGraph's gate decisions
    or human interrupt mechanisms.
    """

    def on_publish(self, event: Event) -> Event:
        """Validate and sanitize an event before publishing.

        Raises:
            SecurityViolation: If the event type is forbidden or advisory_only is False.
        """
        # 1. Force advisory_only = True
        if not event.advisory_only:
            logger.warning(
                "Event %s (%s) missing advisory_only flag — forcing to True",
                event.event_id,
                event.event_type,
            )
            event.advisory_only = True

        # 2. Reject forbidden event types
        if event.event_type.value in FORBIDDEN_EVENT_TYPES:
            raise SecurityViolation(
                f"Event type '{event.event_type}' is prohibited in advisory-only mode. "
                f"Gate decisions and automatic triggers must remain within LangGraph orchestration."
            )

        # 3. Validate payload does not contain prohibited actions
        payload = event.payload or {}
        if payload.get("action") in {"trigger_rework", "auto_publish", "override_gate"}:
            raise SecurityViolation(
                f"Prohibited action '{payload['action']}' in event payload"
            )

        # 4. Validate payload does not contain direct gate decisions
        if "gate_decision" in payload or "final_gate_decision" in payload:
            raise SecurityViolation(
                "Event payload must not contain gate decisions — these are LangGraph responsibilities"
            )

        return event

    def on_consume(self, event: Event) -> Event:
        """Validate an event before consumption by a worker."""
        if not event.advisory_only:
            raise SecurityViolation(
                f"Event {event.event_id} has advisory_only=False — rejecting consumption"
            )
        return event


# Singleton instance for convenience
_default_middleware = AdvisoryOnlyMiddleware()


def apply_publish_middleware(event: Event) -> Event:
    """Apply publish middleware to an event."""
    return _default_middleware.on_publish(event)


def apply_consume_middleware(event: Event) -> Event:
    """Apply consume middleware to an event."""
    return _default_middleware.on_consume(event)
