"""Vigilance Search Worker for the Event Bus.

Subscribes to VIGILANCE_SEARCH_REQUESTED events and queries safety databases.
Each event typically triggers multiple independent database searches
(FDA MAUDE, FDA recall, MHRA, BfArM, Swissmedic, Eudamed, NZ Medsafe).
"""

from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from deerflow.runtime.cer_authoring import mcp_tools
from deerflow.runtime.cer_authoring.event_bus.schema import Event, EventType
from deerflow.runtime.cer_authoring.event_bus.worker import EventWorker

logger = logging.getLogger(__name__)

# Safety database search tools — each can run independently
_VIGILANCE_SEARCHES: list[dict[str, Any]] = [
    {"tool": "fda_maude_search", "args": {"limit": 10}},
    {"tool": "fda_recall_search", "args": {"limit": 10}},
    {"tool": "mhra_safety_search", "args": {}},
    {"tool": "bfarm_safety_search", "args": {}},
    {"tool": "swissmedic_safety_search", "args": {}},
    {"tool": "eudamed_vigilance_search", "args": {}},
    {"tool": "nz_medsafe_safety_search", "args": {}},
]


def _normalize_vigilance_database(name: str) -> str:
    """Normalize vigilance database name for registry entries."""
    mapping = {
        "fda_maude": "FDA MAUDE",
        "fda_recall": "FDA Recall",
        "mhra": "MHRA",
        "bfarm": "BfArM",
        "swissmedic": "Swissmedic",
        "eudamed": "Eudamed",
        "nz_medsafe": "NZ Medsafe",
    }
    return mapping.get(name.lower(), name)


def _screen_vigilance_records(result: dict[str, Any], terms: str) -> list[dict[str, Any]]:
    """First-pass relevance screening of vigilance records."""
    records = result.get("records") or []
    rows = []
    for record in records:
        text = " ".join(str(record.get(k, "")) for k in ("description", "product_name", "event_type", "summary"))
        relevance = "potentially_relevant" if terms.lower() in text.lower() else "not_relevant"
        rows.append({
            "source_database": _normalize_vigilance_database(result.get("database", "")),
            "record_id": record.get("id", ""),
            "relevance": relevance,
            "text_snippet": text[:300],
        })
    return rows


def _vigilance_event_statistics_rows(registry: list[dict], screening: list[dict]) -> list[dict]:
    """Build summary statistics from vigilance results."""
    total_records = sum(r.get("results") or 0 for r in registry)
    potentially_relevant = sum(1 for s in screening if s.get("relevance") == "potentially_relevant")
    return [
        {
            "statistic_id": "VIG-STAT-01",
            "total_searches": len(registry),
            "total_records_found": total_records,
            "potentially_relevant": potentially_relevant,
            "databases_queried": [r.get("database") for r in registry],
        }
    ]


class VigilanceSearchWorker(EventWorker):
    """Worker that queries safety databases in parallel.

    Each VIGILANCE_SEARCH_REQUESTED event triggers all 7 safety DB queries
    concurrently using ThreadPoolExecutor.
    """

    subscribed_events = [EventType.VIGILANCE_SEARCH_REQUESTED]

    def __init__(self, worker_id: str | None = None, max_workers: int = 7) -> None:
        super().__init__(worker_id)
        self._executor = ThreadPoolExecutor(max_workers=max_workers)

    async def handle(self, event: Event, bus: Any) -> None:
        """Process a vigilance search request."""
        payload = event.payload or {}
        search_terms = payload.get("search_terms", "")

        logger.info("Worker %s starting vigilance search for terms: %s", self.worker_id, search_terms)

        # Run all 7 safety DB queries concurrently
        loop = asyncio.get_event_loop()
        futures = []
        for search_def in _VIGILANCE_SEARCHES:
            tool_name = search_def["tool"]
            args = {**search_def["args"], "search_terms": search_terms}
            future = loop.run_in_executor(self._executor, mcp_tools.call_public, tool_name, args)
            futures.append((tool_name, future))

        # Gather results
        results = []
        mcp_log = []
        for tool_name, future in futures:
            try:
                result = await future
                results.append(result)
                mcp_log.append(mcp_tools.mcp_log_entry(result, "public_evidence_vigilance_recall"))
            except Exception as exc:
                logger.error("Vigilance search failed for %s: %s", tool_name, exc)
                results.append({"status": "error", "error": str(exc), "database": tool_name})

        # Build registry
        registry = []
        screening_rows = []
        for idx, result in enumerate(results, start=1):
            relevance = _screen_vigilance_records(result, search_terms)
            screening_rows.extend(relevance)
            registry.append({
                "vigilance_id": f"VIG-{idx:03d}",
                "database": _normalize_vigilance_database(result.get("database", "")),
                "url": result.get("url", ""),
                "search_date": result.get("search_date", ""),
                "search_terms": result.get("query", search_terms),
                "results": result.get("count"),
                "relevant_cases": sum(1 for row in relevance if row.get("relevance") == "potentially_relevant"),
                "relevance_judgment": (
                    "source unavailable; no risk conclusion allowed"
                    if result.get("status") == "source_unavailable"
                    else "first-pass relevance screening completed; human confirmation required for final coding"
                ),
                "conclusion": "No risk conclusion inferred solely from this search count.",
                "raw_status": result.get("status"),
            })

        # Publish completion event
        await bus.publish(Event(
            event_type=EventType.VIGILANCE_SEARCH_COMPLETED,
            payload={
                "vigilance_recall_registry": registry,
                "vigilance_relevance_screening": screening_rows,
                "vigilance_event_statistics": _vigilance_event_statistics_rows(registry, screening_rows),
                "mcp_log": mcp_log,
            },
            correlation_id=event.correlation_id,
            stage_id=event.stage_id,
            spiral_round=event.spiral_round,
            worker_id=self.worker_id,
        ))

        logger.info("Worker %s completed vigilance search (%d databases)", self.worker_id, len(results))
