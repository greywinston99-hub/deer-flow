"""Test EventBus queue binding across different event loops.

This reproduces the bug where EventBus.__init__() creates an asyncio.Queue
on one loop, but start()/publish() are called from a different loop
(e.g. LangGraph worker threads).
"""

from __future__ import annotations

import asyncio
import threading

import pytest

from deerflow.runtime.cer_authoring.event_bus.core import EventBus
from deerflow.runtime.cer_authoring.event_bus.schema import Event, EventType


class TestEventBusCrossLoopBinding:
    """Ensure EventBus works when created and started on different loops."""

    def test_queue_created_in_start_not_init(self) -> None:
        """Queue should be None after __init__, created in start()."""

        async def _inner() -> None:
            bus = EventBus()
            assert bus._queue is None
            await bus.start()
            assert bus._queue is not None
            await bus.stop()

        asyncio.run(_inner())

    def test_publish_before_start_creates_queue_lazily(self) -> None:
        """publish() should lazily create the queue if not started."""

        async def _inner() -> None:
            bus = EventBus()
            event = Event(
                event_type=EventType.EVIDENCE_BATCH_COMPLETED,
                payload={"test": True},
                correlation_id="thread-test",
            )
            # Publish without explicit start()
            await bus.publish(event)
            assert bus._queue is not None
            assert bus._queue.qsize() == 1

        asyncio.run(_inner())

    def test_cross_thread_loop_binding(self) -> None:
        """Simulate LangGraph creating bus on main thread, starting on worker thread."""
        bus = EventBus()  # Created on main thread (no active loop in sync test)

        result: dict[str, bool] = {"started": False, "published": False, "error": False}

        async def _worker() -> None:
            try:
                await bus.start()
                result["started"] = True

                event = Event(
                    event_type=EventType.EVIDENCE_BATCH_COMPLETED,
                    payload={"test": True},
                    correlation_id="thread-test",
                )
                await bus.publish(event)
                result["published"] = True

                # Give dispatch loop a chance to process
                await asyncio.sleep(0.1)
                await bus.stop()
            except Exception:
                result["error"] = True
                raise

        def _run_in_new_loop() -> None:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(_worker())
            loop.close()

        # Run in a separate thread with its own event loop
        t = threading.Thread(target=_run_in_new_loop)
        t.start()
        t.join(timeout=5)

        assert result["started"], "EventBus failed to start on different loop"
        assert result["published"], "EventBus failed to publish on different loop"
        assert not result["error"], "EventBus raised error on different loop"
