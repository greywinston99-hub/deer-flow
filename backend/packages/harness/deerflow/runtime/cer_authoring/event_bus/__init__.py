"""Event Bus hybrid architecture for CER Authoring.

Provides a lightweight in-process event bus that enables parallel execution
of I/O-bound tasks within LangGraph nodes, while preserving LangGraph's
orchestration, gate decisions, human interrupts, and checkpointing.

Key components:
    - EventBus: asyncio-based pub/sub core
    - EventWorker: base class for task workers
    - SpiralCache: cross-round result caching
    - AdvisoryOnlyMiddleware: enforces safety constraints
    - Integration helpers: publish_batches, wait_for_batches, merge functions

Usage:
    from deerflow.runtime.cer_authoring.event_bus import get_event_bus, EventType

    bus = get_event_bus()
    await bus.start()

    # In a LangGraph coordinator node:
    event_ids = await publish_batches(bus, EventType.EVIDENCE_BATCH_REQUESTED, ...)
    results = await wait_for_batches(bus, EventType.EVIDENCE_BATCH_COMPLETED, ...)
    output = merge_batch_evidence(results)
"""

from deerflow.runtime.cer_authoring.event_bus.core import EventBus, get_event_bus
from deerflow.runtime.cer_authoring.event_bus.schema import (
    Event,
    EventType,
    evidence_batch_requested,
    evidence_batch_completed,
    worker_progress,
    FORBIDDEN_EVENT_TYPES,
)
from deerflow.runtime.cer_authoring.event_bus.worker import EventWorker
from deerflow.runtime.cer_authoring.event_bus.middleware import (
    AdvisoryOnlyMiddleware,
    SecurityViolation,
    apply_publish_middleware,
    apply_consume_middleware,
)
from deerflow.runtime.cer_authoring.event_bus.spiral_cache import SpiralCache
from deerflow.runtime.cer_authoring.event_bus.integration import (
    publish_batches,
    wait_for_batches,
    merge_batch_evidence,
    merge_batch_sota_results,
    merge_batch_vigilance_results,
    chunk_list,
)

__all__ = [
    "EventBus",
    "get_event_bus",
    "Event",
    "EventType",
    "evidence_batch_requested",
    "evidence_batch_completed",
    "worker_progress",
    "FORBIDDEN_EVENT_TYPES",
    "EventWorker",
    "AdvisoryOnlyMiddleware",
    "SecurityViolation",
    "apply_publish_middleware",
    "apply_consume_middleware",
    "SpiralCache",
    "publish_batches",
    "wait_for_batches",
    "merge_batch_evidence",
    "merge_batch_sota_results",
    "merge_batch_vigilance_results",
    "chunk_list",
]
