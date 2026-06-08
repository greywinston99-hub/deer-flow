"""Integration utilities for LangGraph nodes to use the Event Bus.

Provides helper functions for coordinator nodes to:
1. Publish batch tasks to the Event Bus
2. Wait for all batch completions
3. Merge results deterministically
4. Emit SSE progress events
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from deerflow.runtime.cer_authoring.event_bus.core import EventBus, get_event_bus
from deerflow.runtime.cer_authoring.event_bus.schema import Event, EventType

logger = logging.getLogger(__name__)


def chunk_list(items: list[Any], size: int) -> list[list[Any]]:
    """Split a list into chunks of given size."""
    return [items[i : i + size] for i in range(0, len(items), size)]


async def publish_batches(
    bus: EventBus,
    event_type: EventType,
    items: list[Any],
    batch_size: int,
    correlation_id: str,
    stage_id: str,
    spiral_round: int,
    payload_builder: Callable[[int, list[Any]], dict[str, Any]],
) -> list[str]:
    """Publish items as batch events to the Event Bus.

    Args:
        bus: The EventBus instance.
        event_type: The event type to publish (e.g., EVIDENCE_BATCH_REQUESTED).
        items: The items to batch and publish.
        batch_size: Number of items per batch.
        correlation_id: The LangGraph thread_id.
        stage_id: The LangGraph node name.
        spiral_round: Current spiral round.
        payload_builder: Function(batch_id, batch_items) → payload dict.

    Returns:
        List of published event_ids.
    """
    batches = chunk_list(items, batch_size)
    event_ids: list[str] = []

    for batch_id, batch in enumerate(batches):
        event = Event(
            event_type=event_type,
            payload=payload_builder(batch_id, batch),
            correlation_id=correlation_id,
            stage_id=stage_id,
            spiral_round=spiral_round,
            batch_id=batch_id,
        )
        await bus.publish(event)
        event_ids.append(event.event_id)
        logger.debug("Published batch %d/%d for %s", batch_id + 1, len(batches), stage_id)

    return event_ids


async def wait_for_batches(
    bus: EventBus,
    completion_event_type: EventType,
    expected_batch_count: int,
    correlation_id: str,
    stage_id: str,
    timeout: float = 300.0,
    on_progress: Callable[[int, int], None] | None = None,
) -> list[Event]:
    """Wait for all batch completion events.

    Args:
        bus: The EventBus instance.
        completion_event_type: The completion event type to wait for.
        expected_batch_count: Number of batches expected.
        correlation_id: Filter by thread_id.
        stage_id: Filter by stage.
        timeout: Max seconds to wait.
        on_progress: Optional callback(completed, total).

    Returns:
        List of completion events, sorted by batch_id.

    Raises:
        TimeoutError: If not all batches complete in time.
    """
    completed_events: dict[int, Event] = {}
    event_store = bus.get_event_store()

    start_time = __import__("asyncio").get_event_loop().time()

    while len(completed_events) < expected_batch_count:
        elapsed = __import__("asyncio").get_event_loop().time() - start_time
        if elapsed >= timeout:
            raise TimeoutError(
                f"wait_for_batches timed out after {timeout}s. "
                f"Completed: {len(completed_events)}/{expected_batch_count}"
            )

        # Scan event store for new completions
        for event in event_store:
            if event.event_type != completion_event_type:
                continue
            if event.correlation_id != correlation_id:
                continue
            if event.stage_id != stage_id:
                continue
            if event.batch_id is not None and event.batch_id not in completed_events:
                completed_events[event.batch_id] = event

        if on_progress:
            on_progress(len(completed_events), expected_batch_count)

        await __import__("asyncio").sleep(0.1)

    # Return sorted by batch_id for deterministic ordering
    results = [completed_events[i] for i in sorted(completed_events.keys())]
    return results


def merge_batch_evidence(results: list[Event]) -> dict[str, Any]:
    """Merge evidence_batch completion events into coordinator output.

    Results are merged in batch_id order to maintain deterministic output.
    """
    evidence_registry: list[dict[str, Any]] = []
    article_appraisal: list[dict[str, Any]] = []
    mcp_log: list[dict[str, Any]] = []
    fulltext_rows: list[dict[str, Any]] = []
    source_trace_rows: list[dict[str, Any]] = []
    cache_hits = 0
    cache_misses = 0

    for event in results:
        payload = event.payload or {}
        evidence_registry.extend(payload.get("evidence", []))
        article_appraisal.extend(payload.get("appraisals", []))
        mcp_log.extend(payload.get("mcp_log", []))
        fulltext_rows.extend(payload.get("fulltext_rows", []))
        source_trace_rows.extend(payload.get("source_trace_rows", []))
        cache_hits += payload.get("cache_hits", 0)
        cache_misses += payload.get("cache_misses", 0)

    return {
        "evidence_registry": evidence_registry,
        "article_appraisal": article_appraisal,
        "mcp_log": mcp_log,
        "fulltext_rows": fulltext_rows,
        "source_trace_rows": source_trace_rows,
        "event_bus_cache_hits": cache_hits,
        "event_bus_cache_misses": cache_misses,
    }


def merge_batch_sota_results(results: list[Event]) -> dict[str, Any]:
    """Merge sota_search completion events."""
    search_run_registry: list[dict[str, Any]] = []
    raw_literature_records: list[dict[str, Any]] = []
    mcp_log: list[dict[str, Any]] = []

    for event in results:
        payload = event.payload or {}
        search_run_registry.extend(payload.get("search_run_registry", []))
        raw_literature_records.extend(payload.get("raw_literature_records", []))
        mcp_log.extend(payload.get("mcp_log", []))

    return {
        "search_run_registry": search_run_registry,
        "raw_literature_records": raw_literature_records,
        "mcp_log": mcp_log,
    }


def merge_batch_vigilance_results(results: list[Event]) -> dict[str, Any]:
    """Merge vigilance_search completion events."""
    vigilance_registry: list[dict[str, Any]] = []
    mcp_log: list[dict[str, Any]] = []

    for event in results:
        payload = event.payload or {}
        vigilance_registry.extend(payload.get("vigilance_registry", []))
        mcp_log.extend(payload.get("mcp_log", []))

    return {"vigilance_registry": vigilance_registry, "mcp_log": mcp_log}
