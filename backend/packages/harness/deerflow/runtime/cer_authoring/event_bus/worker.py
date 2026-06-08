"""EventWorker base class for the Event Bus hybrid architecture.

Workers subscribe to specific event types, process them, and publish
completion events back to the bus. Workers run in their own asyncio tasks
and may perform blocking I/O (MCP calls) internally.
"""

from __future__ import annotations

import asyncio
import logging
import traceback
from abc import ABC, abstractmethod
from typing import Any

from deerflow.runtime.cer_authoring.event_bus.schema import Event, EventType
from deerflow.runtime.cer_authoring.event_bus.middleware import apply_consume_middleware

logger = logging.getLogger(__name__)


class EventWorker(ABC):
    """Base class for all Event Bus workers.

    Subclasses must define `subscribed_events` and implement `handle()`.
    The worker runs in an asyncio task, processing events from the bus.
    """

    subscribed_events: list[EventType] = []
    worker_id: str = ""

    def __init__(self, worker_id: str | None = None) -> None:
        self.worker_id = worker_id or f"{self.__class__.__name__}-{id(self)}"
        self._running = False
        self._task: asyncio.Task[Any] | None = None

    async def start(self, bus: Any) -> None:
        """Start the worker as an asyncio task."""
        self._running = True
        self._task = asyncio.create_task(self._run_loop(bus))
        logger.info("Worker %s started, subscribed to %s", self.worker_id, self.subscribed_events)

    async def stop(self) -> None:
        """Stop the worker gracefully."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Worker %s stopped", self.worker_id)

    async def _run_loop(self, bus: Any) -> None:
        """Main event loop for the worker."""
        while self._running:
            try:
                # Wait for events matching our subscription
                event = await bus.wait_for_event(self.subscribed_events)
                if event is None:
                    continue

                # Security middleware on consume
                try:
                    event = apply_consume_middleware(event)
                except Exception as exc:
                    logger.error("Security violation on consume: %s", exc)
                    continue

                # Attach worker_id to event for tracing
                event.worker_id = self.worker_id

                # Publish worker started event
                await bus.publish(Event(
                    event_type=EventType.WORKER_STARTED,
                    payload={"worker_id": self.worker_id, "input_event_id": event.event_id},
                    correlation_id=event.correlation_id,
                    stage_id=event.stage_id,
                    spiral_round=event.spiral_round,
                    worker_id=self.worker_id,
                ))

                # Process the event
                import time as _time
                process_start = _time.time()
                try:
                    await self.handle(event, bus)
                    await bus.publish(Event(
                        event_type=EventType.WORKER_COMPLETED,
                        payload={"worker_id": self.worker_id, "input_event_id": event.event_id},
                        correlation_id=event.correlation_id,
                        stage_id=event.stage_id,
                        spiral_round=event.spiral_round,
                        worker_id=self.worker_id,
                    ))
                except Exception as exc:
                    logger.exception("Worker %s failed processing event %s", self.worker_id, event.event_id)
                    await bus.publish(Event(
                        event_type=EventType.WORKER_FAILED,
                        payload={
                            "worker_id": self.worker_id,
                            "input_event_id": event.event_id,
                            "error": str(exc),
                            "traceback": traceback.format_exc(),
                        },
                        correlation_id=event.correlation_id,
                        stage_id=event.stage_id,
                        spiral_round=event.spiral_round,
                        worker_id=self.worker_id,
                    ))
                finally:
                    try:
                        from deerflow.runtime.cer_authoring.event_bus.metrics import metrics_collector
                        duration_ms = (_time.time() - process_start) * 1000
                        metrics_collector.observe(
                            "worker.processing_duration_ms",
                            duration_ms,
                            labels={
                                "worker_type": self.__class__.__name__,
                                "event_type": event.event_type.value,
                            },
                        )
                    except Exception:
                        pass

            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Worker %s run loop error", self.worker_id)
                await asyncio.sleep(0.1)

    @abstractmethod
    async def handle(self, event: Event, bus: Any) -> None:
        """Process a single event.

        Subclasses should implement their business logic here.
        They may call bus.publish() to emit completion events.

        Args:
            event: The event to process.
            bus: The EventBus instance for publishing results.
        """
        raise NotImplementedError
