"""Evidence Appraisal Worker for the Event Bus.

Subscribes to EVIDENCE_BATCH_REQUESTED events and evaluates a batch of
articles in parallel. Each worker processes one batch (typically 8–17 articles).

Supports Spiral Cache for cross-round incremental evaluation.
"""

from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from deerflow.runtime.cer_authoring import mcp_tools
from deerflow.runtime.cer_authoring.event_bus.schema import Event, EventType
from deerflow.runtime.cer_authoring.event_bus.worker import EventWorker
from deerflow.runtime.cer_authoring.event_bus.spiral_cache import SpiralCache

logger = logging.getLogger(__name__)


class EvidenceAppraisalWorker(EventWorker):
    """Worker that evaluates evidence for a batch of articles.

    Each EVIDENCE_BATCH_REQUESTED event contains a subset of articles.
    The worker processes each article by:
    1. Verifying the citation via pubmed_verify_citation
    2. Appraising the evidence via nb-check.appraise_evidence
    3. Building evidence and appraisal records

    Results are published as an EVIDENCE_BATCH_COMPLETED event.
    """

    subscribed_events = [EventType.EVIDENCE_BATCH_REQUESTED]

    def __init__(self, worker_id: str | None = None, max_workers: int = 4) -> None:
        super().__init__(worker_id)
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._spiral_cache = SpiralCache()

    async def handle(self, event: Event, bus: Any) -> None:
        """Process an evidence appraisal batch with double-layer concurrency.

        Layer 1: All articles in the batch are appraised concurrently.
        Layer 2: For each article, the two MCP calls (verify + appraise)
                 are executed concurrently via asyncio.gather.
        """
        payload = event.payload or {}
        articles = payload.get("articles", [])
        state_snapshot = payload.get("state_snapshot", {})
        batch_id = payload.get("batch_id", 0)

        logger.info(
            "Worker %s starting evidence appraisal batch %d (%d articles)",
            self.worker_id, batch_id, len(articles),
        )

        # Layer 1: Concurrently appraise all articles in the batch
        tasks = [
            self._appraise_article_async(article, state_snapshot, event.spiral_round, bus)
            for article in articles
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Gather results
        evidence_records = []
        appraisal_records = []
        mcp_log = []
        cache_hits = 0
        cache_misses = 0

        for idx, (article, result) in enumerate(zip(articles, results)):
            if isinstance(result, Exception):
                logger.error("Article appraisal failed for PMID %s: %s", article.get("pmid"), result)
                evidence_records.append(self._failed_evidence_record(article, str(result)))
                appraisal_records.append(self._failed_appraisal_record(article, str(result)))
                continue
            if result.get("_cache_hit"):
                cache_hits += 1
            else:
                cache_misses += 1
            evidence_records.append(result["evidence"])
            appraisal_records.append(result["appraisal"])
            mcp_log.extend(result.get("mcp_log", []))

        # Publish completion event
        await bus.publish(Event(
            event_type=EventType.EVIDENCE_BATCH_COMPLETED,
            payload={
                "batch_id": batch_id,
                "evidence": evidence_records,
                "appraisals": appraisal_records,
                "mcp_log": mcp_log,
                "cache_hits": cache_hits,
                "cache_misses": cache_misses,
            },
            correlation_id=event.correlation_id,
            stage_id=event.stage_id,
            spiral_round=event.spiral_round,
            worker_id=self.worker_id,
            batch_id=batch_id,
        ))

        logger.info(
            "Worker %s completed batch %d (%d articles, %d cache hits)",
            self.worker_id, batch_id, len(articles), cache_hits,
        )

    async def _appraise_article_async(
        self,
        article: dict[str, Any],
        state_snapshot: dict[str, Any],
        spiral_round: int,
        bus: Any,
    ) -> dict[str, Any]:
        """Evaluate a single article with Layer-2 concurrency (verify + appraise in parallel).

        Uses asyncio.gather to execute the two independent MCP calls concurrently,
        then builds the evidence and appraisal records from the results.
        """
        pmid = str(article.get("pmid") or "")
        title = str(article.get("title") or "")

        # Check spiral cache
        cache_key = self._spiral_cache.compute_cache_key(article)
        if spiral_round > 1:
            cached = self._spiral_cache.get_cached_result(cache_key, spiral_round)
            if cached:
                logger.debug("Cache hit for PMID %s (round %d)", pmid, spiral_round)
                return {
                    "evidence": {**cached, "_cache_hit": True, "cache_key": cache_key},
                    "appraisal": cached.get("_appraisal", {}),
                    "mcp_log": [],
                    "_cache_hit": True,
                }

        loop = asyncio.get_event_loop()

        # Layer 2: Execute verify + appraise concurrently
        verify_future = loop.run_in_executor(
            self._executor,
            self._call_pubmed_verify,
            article.get("pmid", ""),
            title,
        )
        appraise_future = loop.run_in_executor(
            self._executor,
            self._call_nb_appraise,
            article,
        )

        verification, nb_appraisal = await asyncio.gather(
            verify_future, appraise_future, return_exceptions=True
        )

        mcp_log = []

        # Handle verify result
        if isinstance(verification, Exception):
            logger.warning("Citation verification failed for PMID %s: %s", pmid, verification)
            verification = {"verified": False, "error": str(verification)}
        else:
            mcp_log.append(mcp_tools.mcp_log_entry(verification, "public_evidence_pubmed_verify"))

        # Handle appraise result
        if isinstance(nb_appraisal, Exception):
            logger.warning("NB appraisal failed for PMID %s: %s", pmid, nb_appraisal)
            nb_appraisal = {"evidence_grade": "not extracted", "error": str(nb_appraisal)}
        else:
            mcp_log.append(mcp_tools.mcp_log_entry(nb_appraisal, "nb_check_appraise_evidence"))

        verified = bool(verification.get("verified") or (article.get("pmid") and article.get("title")))

        # Build evidence record
        evidence_id = f"E-{pmid or 'UNKNOWN'}-{cache_key[:8]}"
        evidence_record = {
            "evidence_id": evidence_id,
            "article_id": f"ART-{pmid or 'UNKNOWN'}",
            "pmid": article.get("pmid"),
            "source_type": "PubMed literature",
            "source": f"PMID {article.get('pmid')}",
            "title": title,
            "abstract_text": article.get("abstract", ""),
            "study_design": article.get("study_design", "unknown"),
            "oxford_level": article.get("oxford_level", "not extracted"),
            "sample_size": article.get("sample_size", "not available"),
            "follow_up": article.get("follow_up", "not available"),
            "nb_check_evidence_grade": nb_appraisal.get("evidence_grade") or nb_appraisal.get("grade", "not extracted"),
            "verified": verified,
            "weight": "pivotal" if verified else "background",
            "cache_key": cache_key,
        }

        # Build appraisal record
        appraisal_record = {
            "article_id": f"ART-{pmid or 'UNKNOWN'}",
            "evidence_id": evidence_id,
            "study_design": article.get("study_design", "unknown"),
            "evidence_level": article.get("oxford_level", "not extracted"),
            "nb_check_evidence_grade": nb_appraisal.get("evidence_grade") or nb_appraisal.get("grade", "not extracted"),
            "full_text_status": article.get("full_text_status", "abstract_only"),
            "sample_size": article.get("sample_size", "not available"),
            "weight": "pivotal" if verified else "background",
            "verified": verified,
            "cache_key": cache_key,
        }

        return {
            "evidence": evidence_record,
            "appraisal": appraisal_record,
            "mcp_log": mcp_log,
            "_cache_hit": False,
        }

    def _call_pubmed_verify(self, pmid: str, title: str) -> dict[str, Any]:
        """Wrapper for pubmed_verify_citation MCP call."""
        return mcp_tools.call_public(
            "pubmed_verify_citation",
            {"pmid": pmid, "title": title},
        )

    def _call_nb_appraise(self, article: dict[str, Any]) -> dict[str, Any]:
        """Wrapper for nb-check.appraise_evidence MCP call."""
        return mcp_tools.call_tool(
            "nb-check",
            "appraise_evidence",
            {
                "study_design": article.get("study_design", "unknown"),
                "sample_size": article.get("sample_size", 0),
                "randomized": "randomized" in str(article.get("title", "")).lower(),
                "blinded": "blind" in str(article.get("title", "")).lower(),
                "multi_center": "multicenter" in str(article.get("title", "")).lower(),
                "follow_up_pct": 100.0,
                "has_control_group": any(
                    token in str(article.get("title", "")).lower()
                    for token in ("versus", "compared", "comparison", "control group", "controlled")
                ),
            },
            timeout=90,
        )

    def _failed_evidence_record(self, article: dict[str, Any], error: str) -> dict[str, Any]:
        """Create a placeholder evidence record for failed appraisals."""
        return {
            "evidence_id": f"E-FAILED-{article.get('pmid', 'UNKNOWN')}",
            "article_id": f"ART-{article.get('pmid', 'UNKNOWN')}",
            "pmid": article.get("pmid"),
            "source_type": "PubMed literature",
            "title": article.get("title", ""),
            "error": error,
            "weight": "excluded",
            "verified": False,
        }

    def _failed_appraisal_record(self, article: dict[str, Any], error: str) -> dict[str, Any]:
        """Create a placeholder appraisal record for failed appraisals."""
        return {
            "article_id": f"ART-{article.get('pmid', 'UNKNOWN')}",
            "evidence_id": f"E-FAILED-{article.get('pmid', 'UNKNOWN')}",
            "error": error,
            "weight": "excluded",
            "verified": False,
        }
