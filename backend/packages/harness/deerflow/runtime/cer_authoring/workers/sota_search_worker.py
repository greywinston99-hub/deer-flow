"""SOTA Search Worker for the Event Bus.

Subscribes to SOTA_SEARCH_REQUESTED events and executes a single
external database search (PubMed, Europe PMC, ClinicalTrials.gov, etc.).

Multiple workers can run concurrently to process different search plan rows
in parallel.
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


class SotaSearchWorker(EventWorker):
    """Worker that executes a single external database search.

    Each SOTA_SEARCH_REQUESTED event contains one search plan row.
    Multiple workers process different rows concurrently.
    """

    subscribed_events = [EventType.SOTA_SEARCH_REQUESTED]

    def __init__(self, worker_id: str | None = None) -> None:
        super().__init__(worker_id)
        self._executor = ThreadPoolExecutor(max_workers=2)

    async def handle(self, event: Event, bus: Any) -> None:
        """Process a single SOTA search request."""
        payload = event.payload or {}
        search_plan_row = payload.get("search_plan_row", {})
        profile = payload.get("device_profile", {})
        state = payload.get("state_snapshot", {})

        logger.info(
            "Worker %s executing SOTA search: %s (%s)",
            self.worker_id,
            search_plan_row.get("query_string", "")[:80],
            search_plan_row.get("database", "unknown"),
        )

        # Execute the search (blocking MCP call wrapped in executor)
        loop = asyncio.get_event_loop()
        try:
            result = await loop.run_in_executor(
                self._executor,
                self._execute_search,
                search_plan_row,
                state,
                profile,
            )
        except Exception as exc:
            logger.error("SOTA search failed: %s", exc)
            result = {"status": "error", "error": str(exc), "database": search_plan_row.get("database", "")}

        # Build search run record
        search_id = f"SEARCH-{search_plan_row.get('objective', 'SOTA')}-{event.batch_id or 0:02d}"
        search_run = {
            "search_id": search_id,
            "database": result.get("database", search_plan_row.get("database", "")),
            "search_terms": result.get("query", search_plan_row.get("query_string", "")),
            "search_date": result.get("search_date", ""),
            "objective": search_plan_row.get("objective", "SOTA"),
            "returned_count": result.get("returned_count", 0),
            "count": result.get("count", 0),
            "status": result.get("status", "unknown"),
            "url": result.get("url", ""),
        }

        raw_records = self._extract_raw_records(result)

        # Publish completion event
        await bus.publish(Event(
            event_type=EventType.SOTA_SEARCH_COMPLETED,
            payload={
                "search_run_registry": [search_run],
                "raw_literature_records": raw_records,
                "mcp_log": [mcp_tools.mcp_log_entry(result, "public_evidence_sota_search")],
            },
            correlation_id=event.correlation_id,
            stage_id=event.stage_id,
            spiral_round=event.spiral_round,
            worker_id=self.worker_id,
            batch_id=event.batch_id,
        ))

        logger.info("Worker %s completed SOTA search (%s)", self.worker_id, search_run["database"])

    def _execute_search(
        self,
        search_plan_row: dict[str, Any],
        state: dict[str, Any],
        profile: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute a single external database search using MCP tools.

        This mirrors the logic in pipeline._execute_external_database_search.
        """
        database = search_plan_row.get("database", "")
        query = search_plan_row.get("query_string", "")

        # Map database name to MCP tool
        tool_mapping = {
            "pubmed": "pubmed_search",
            "embase": "embase_search",
            "europe_pmc": "europe_pmc_search",
            "clinicaltrials.gov": "clinicaltrials_search",
            "pmc_fulltext": "pmc_fulltext_search",
            "cochrane": "cochrane_search",
            "cochrane library": "cochrane_search",
        }
        tool = tool_mapping.get(database.lower(), database)

        try:
            result = mcp_tools.call_public(tool, {"query": query, "retmax": 50})
        except Exception as exc:
            logger.error("MCP call failed for %s: %s", tool, exc)
            result = {"status": "error", "error": str(exc), "database": database, "query": query}

        # Normalize result
        if "records" not in result:
            result["records"] = []
        if "pmids" not in result:
            result["pmids"] = []
        if "returned_count" not in result:
            result["returned_count"] = len(result.get("records", [])) + len(result.get("pmids", []))

        return result

    def _extract_raw_records(self, result: dict[str, Any]) -> list[dict[str, Any]]:
        """Extract raw literature records from search result."""
        records = []
        for record in result.get("records", []):
            records.append({
                "pmid": record.get("pmid"),
                "title": record.get("title", ""),
                "abstract": record.get("abstract", ""),
                "doi": record.get("doi", ""),
                "database": result.get("database", ""),
                "query": result.get("query", ""),
                "search_date": result.get("search_date", ""),
            })
        for pmid in result.get("pmids", []):
            records.append({
                "pmid": pmid,
                "title": "",
                "abstract": "",
                "database": result.get("database", ""),
                "query": result.get("query", ""),
                "search_date": result.get("search_date", ""),
            })
        return records
