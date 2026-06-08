"""EventBus core for the CER Authoring hybrid architecture.

A lightweight in-process event bus based on asyncio.Queue.
Supports publish/subscribe, request/response patterns, and progress callbacks.
Designed to run within the same Python process as LangGraph, with zero
external dependencies (Redis/Kafka optional for future multi-process scaling).
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from typing import Any, Callable

from deerflow.runtime.cer_authoring.event_bus.schema import Event, EventType
from deerflow.runtime.cer_authoring.event_bus.middleware import apply_publish_middleware
from deerflow.runtime.cer_authoring.event_bus.event_store import EventStore

logger = logging.getLogger(__name__)


class EventBus:
    """Lightweight asyncio-based event bus for CER Authoring.

    Usage:
        bus = EventBus()
        await bus.start()

        # Publish a task
        await bus.publish(event)

        # Wait for specific events
        results = await bus.wait_for_all(
            [event_id_1, event_id_2],
            timeout=300,
            on_progress=lambda c, t: print(f"{c}/{t}")
        )
    """

    def __init__(self, max_queue_size: int = 1000) -> None:
        # Defer Queue creation to start() to ensure it binds to the
        # same event loop that runs _dispatch_loop(). This prevents
        # RuntimeError when LangGraph creates the bus on one thread
        # and starts it on another.
        self._max_queue_size = max_queue_size
        self._queue: asyncio.Queue[Event] | None = None
        self._subscribers: dict[EventType, list[Callable[[Event], None]]] = defaultdict(list)
        self._pending_requests: dict[str, asyncio.Future[Event]] = {}
        self._store = EventStore()
        self._running = False
        self._dispatch_task: asyncio.Task[Any] | None = None
        self._paused_threads: set[str] = set()

    async def start(self) -> None:
        """Start the event dispatch loop.

        Creates the asyncio.Queue here (not in __init__) so it is
        bound to the same event loop that runs _dispatch_loop().

        If the queue was previously created on a different event loop
        (e.g. from a previous graph run), it is recreated on the
        current loop to avoid cross-loop binding errors.
        """
        if self._queue is None:
            self._queue = asyncio.Queue(maxsize=self._max_queue_size)
        else:
            # Queue may be bound to a previous event loop. Verify by
            # attempting a no-op get future creation.
            try:
                self._queue._get_loop()
            except RuntimeError:
                # Bound to a different loop — recreate on current loop
                logger.info("EventBus queue recreated on new event loop")
                self._queue = asyncio.Queue(maxsize=self._max_queue_size)

        self._running = True
        self._dispatch_task = asyncio.create_task(self._dispatch_loop())
        logger.info("EventBus started")

    async def stop(self) -> None:
        """Stop the event bus gracefully."""
        self._running = False
        if self._dispatch_task:
            self._dispatch_task.cancel()
            try:
                await self._dispatch_task
            except asyncio.CancelledError:
                pass
        logger.info("EventBus stopped")

    async def publish(self, event: Event) -> None:
        """Publish an event to the bus.

        Events are validated by security middleware before enqueue.
        If the bus has not been started yet, the queue is created lazily
        on the current event loop.
        """
        try:
            event = apply_publish_middleware(event)
        except Exception as exc:
            logger.error("Publish rejected for event %s: %s", event.event_id, exc)
            raise

        # Persist to SQLite for audit trail and Spiral Cache
        self._store.insert(event)

        # Lazy queue creation: ensures queue is bound to caller's loop.
        # If queue exists but is bound to a different loop (from a previous
        # graph run), recreate it on the current loop.
        if self._queue is None:
            self._queue = asyncio.Queue(maxsize=self._max_queue_size)
        else:
            try:
                self._queue._get_loop()
            except RuntimeError:
                self._queue = asyncio.Queue(maxsize=self._max_queue_size)

        # Enqueue for dispatch
        await self._queue.put(event)
        logger.debug("Published event %s (%s)", event.event_id, event.event_type)

        # Metrics
        try:
            from deerflow.runtime.cer_authoring.event_bus.metrics import metrics_collector
            metrics_collector.inc(
                "event_bus.events_published_total",
                labels={"event_type": event.event_type.value},
            )
        except Exception:
            pass

    def subscribe(self, event_type: EventType, callback: Callable[[Event], None]) -> None:
        """Subscribe to a specific event type.

        Note: For worker integration, workers typically use wait_for_event()
        rather than subscribe(). This method is available for one-off listeners.
        """
        self._subscribers[event_type].append(callback)

    async def wait_for_event(
        self,
        event_types: list[EventType],
        timeout: float | None = None,
    ) -> Event | None:
        """Wait for an event matching any of the given types.

        Used by workers to pull events from the bus.
        """
        if self._queue is None:
            return None
        start = asyncio.get_event_loop().time()
        while self._running:
            try:
                elapsed = asyncio.get_event_loop().time() - start
                remaining = timeout - elapsed if timeout else None
                if remaining is not None and remaining <= 0:
                    return None

                event = await asyncio.wait_for(self._queue.get(), timeout=min(remaining, 0.1) if remaining else 0.1)

                if event.event_type in event_types:
                    return event

                # Not for us — put it back (simplified; real impl would use multiple queues)
                # For now, just dispatch to subscribers
                await self._dispatch_single(event)

            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break

        return None

    async def wait_for_all(
        self,
        pending_event_ids: list[str],
        timeout: float = 300.0,
        on_progress: Callable[[int, int], None] | None = None,
    ) -> list[Event]:
        """Wait for all pending events to complete.

        This is the primary API used by LangGraph coordinator nodes.
        They publish tasks, then wait for all completions.

        Args:
            pending_event_ids: List of event_ids to wait for.
            timeout: Maximum seconds to wait.
            on_progress: Optional callback(completed, total) for SSE streaming.

        Returns:
            List of completion events in batch_id order.

        Raises:
            TimeoutError: If not all events complete within timeout.
        """
        if self._queue is None:
            raise RuntimeError("EventBus queue not initialized. Call start() first.")
        completed: dict[str, Event] = {}
        total = len(pending_event_ids)

        start = asyncio.get_event_loop().time()

        while len(completed) < total:
            elapsed = asyncio.get_event_loop().time() - start
            if elapsed >= timeout:
                missing = set(pending_event_ids) - set(completed.keys())
                raise TimeoutError(
                    f"wait_for_all timed out after {timeout}s. "
                    f"Completed: {len(completed)}/{total}. Missing: {missing}"
                )

            try:
                event = await asyncio.wait_for(self._queue.get(), timeout=min(1.0, timeout - elapsed))

                # Check if this is a completion event for one of our pending requests
                if event.event_type in {
                    EventType.EVIDENCE_BATCH_COMPLETED,
                    EventType.SOTA_SEARCH_COMPLETED,
                    EventType.VIGILANCE_SEARCH_COMPLETED,
                    EventType.FULLTEXT_COMPLETED,
                }:
                    # Match by event_id: if the completion event's event_id is in our
                    # pending list, or if we track by correlation_id.
                    # For simplicity, we collect all matching completion events and
                    # de-duplicate by event_id.
                    if event.event_id not in completed:
                        completed[event.event_id] = event

                # Dispatch to any progress callbacks
                if on_progress:
                    on_progress(len(completed), total)

            except asyncio.TimeoutError:
                continue

        # Return results sorted by batch_id for deterministic ordering
        results = list(completed.values())
        results.sort(key=lambda e: (e.batch_id or 0))
        return results

    async def _dispatch_loop(self) -> None:
        """Main dispatch loop: pull from queue and route to subscribers."""
        if self._queue is None:
            logger.error("Dispatch loop started but queue is None")
            return
        report_counter = 0
        while self._running:
            try:
                event = await asyncio.wait_for(self._queue.get(), timeout=0.5)
                await self._dispatch_single(event)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Dispatch loop error")

            # Periodic metrics gauge update
            report_counter += 1
            if report_counter % 20 == 0:
                try:
                    from deerflow.runtime.cer_authoring.event_bus.metrics import metrics_collector
                    metrics_collector.set_gauge(
                        "event_bus.queue_size",
                        float(self._queue.qsize() if hasattr(self._queue, "qsize") else -1),
                    )
                except Exception:
                    pass

    async def _dispatch_single(self, event: Event) -> None:
        """Dispatch a single event to all matching subscribers."""
        callbacks = self._subscribers.get(event.event_type, [])
        for callback in callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    asyncio.create_task(callback(event))
                else:
                    callback(event)
            except Exception:
                logger.exception("Subscriber callback error for event %s", event.event_id)

    def pause_for_interrupt(self, thread_id: str) -> None:
        """Pause event processing for a thread that has hit an interrupt()."""
        self._paused_threads.add(thread_id)
        logger.info("EventBus paused for thread %s (interrupt)", thread_id)

    def resume_after_interrupt(self, thread_id: str) -> None:
        """Resume event processing after interrupt() resume."""
        self._paused_threads.discard(thread_id)
        logger.info("EventBus resumed for thread %s", thread_id)

    def get_event_store(self) -> list[Event]:
        """Return all events in the store (for audit/debugging)."""
        return self._store.query(limit=10000)

    def clear_event_store(self) -> None:
        """Clear the event store."""
        self._store.clear()


# Singleton instance (per-process)
_event_bus_instance: EventBus | None = None


def get_event_bus() -> EventBus:
    """Get or create the singleton EventBus instance."""
    global _event_bus_instance
    if _event_bus_instance is None:
        _event_bus_instance = EventBus()
    return _event_bus_instance
