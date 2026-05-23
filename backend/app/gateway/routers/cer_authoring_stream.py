"""CER Authoring SSE streaming endpoint.

Streams real-time LangGraph node transitions, interrupts, gate results,
and Quick-Scan completions to the frontend via Server-Sent Events.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from deerflow.runtime.cer_authoring.graph import build_cer_authoring_graph
from deerflow.runtime.cer_authoring.stream_adapter import (
    AuthoringEventType,
    filter_sensitive,
    normalize_event,
    serialize_sse_event,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/cer-authoring", tags=["cer-authoring-stream"])


async def _authoring_sse_generator(
    thread_id: str,
    checkpointer: Any,
) -> Any:
    """Async generator that yields SSE-formatted strings.

    Loads current thread state from checkpointer, creates the authoring graph,
    and streams normalized events.
    """
    graph = build_cer_authoring_graph(checkpointer=checkpointer)
    config = {"configurable": {"thread_id": thread_id}}

    # Try to load existing checkpoint state
    checkpoint_tuple = await checkpointer.aget_tuple(config)
    if checkpoint_tuple is None:
        yield serialize_sse_event({
            "event": AuthoringEventType.ERROR.value,
            "error": f"Thread {thread_id} not found",
            "timestamp": _now_iso(),
        })
        return

    # Extract channel values (current state)
    checkpoint = getattr(checkpoint_tuple, "checkpoint", {}) or {}
    channel_values = checkpoint.get("channel_values", {}) or {}
    state = dict(channel_values)

    # Yield initial state snapshot (filtered)
    yield serialize_sse_event({
        "event": "state_snapshot",
        "node": state.get("status") or "unknown",
        "state": filter_sensitive(state),
        "timestamp": _now_iso(),
    })

    node_start_times: dict[str, float] = {}

    try:
        async for update in graph.astream(
            state,
            config=config,
            stream_mode="updates",
        ):
            # update is a dict keyed by node name
            if not isinstance(update, dict):
                continue

            event = normalize_event(update, node_start_times=node_start_times)
            if event is None:
                continue

            # Handle batch events
            if event.get("event") == "batch":
                for sub in event.get("events", []):
                    yield serialize_sse_event(sub)
            else:
                yield serialize_sse_event(event)

        # Stream done event
        yield serialize_sse_event({
            "event": AuthoringEventType.DONE.value,
            "timestamp": _now_iso(),
        })

    except asyncio.CancelledError:
        logger.info("SSE stream cancelled for thread %s", thread_id)
        yield serialize_sse_event({
            "event": AuthoringEventType.DONE.value,
            "reason": "cancelled",
            "timestamp": _now_iso(),
        })
        raise
    except Exception as exc:
        logger.exception("SSE stream error for thread %s", thread_id)
        yield serialize_sse_event({
            "event": AuthoringEventType.ERROR.value,
            "error": str(exc),
            "timestamp": _now_iso(),
        })


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


@router.get("/stream/{thread_id}")
async def stream_authoring(thread_id: str, request: Request) -> StreamingResponse:
    """Stream CER Authoring graph events for a given thread.

    Returns Server-Sent Events (SSE) with the following event types:
    - `node_start` / `node_end`: pipeline node transitions
    - `interrupt`: human intervention required
    - `gate_result`: hard gate evaluation result
    - `quick_scan`: mid-pipeline review scan completion
    - `lead_decision`: lead agent routing decision
    - `stage_update`: stage completion/update
    - `error`: stream or graph error
    - `done`: stream complete
    """
    from app.gateway.deps import get_checkpointer

    checkpointer = get_checkpointer(request)

    return StreamingResponse(
        _authoring_sse_generator(thread_id, checkpointer),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
