"""Spiral Cache for cross-round incremental evaluation.

Uses the persistent SQLite Event Store to cache evaluation results
across spiral rounds. When a worker processes a batch, it checks
if articles were already evaluated in a previous round. If so,
it reuses the cached result instead of re-invoking MCP tools.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any

from deerflow.runtime.cer_authoring.event_bus.schema import EventType
from deerflow.runtime.cer_authoring.event_bus.event_store import EventStore

logger = logging.getLogger(__name__)


class SpiralCache:
    """Cache for evidence evaluation results across spiral rounds.

    Queries the persistent EventStore (SQLite) for cached results
    from previous spiral rounds. This enables cross-process and
    cross-restart cache hits.
    """

    def __init__(self, store: EventStore | None = None) -> None:
        self._store = store or EventStore()

    def compute_cache_key(self, article: dict[str, Any]) -> str:
        """Compute a deterministic cache key for an article.

        The key includes:
        - PMID
        - Title
        - Abstract text hash
        - Source database
        """
        pmid = str(article.get("pmid") or "")
        title = str(article.get("title") or "")
        abstract = str(article.get("abstract", ""))
        source = str(article.get("source_database") or article.get("database") or "")

        content = f"{pmid}:{title}:{abstract}:{source}"
        return hashlib.sha256(content.encode("utf-8")).hexdigest()[:32]

    def get_cached_result(
        self,
        cache_key: str,
        current_round: int,
        event_store: list[Any] | None = None,
    ) -> dict[str, Any] | None:
        """Check if a result exists from a previous round via SQLite EventStore.

        Args:
            cache_key: The article's cache key.
            current_round: The current spiral round (only look at rounds < current).
            event_store: Legacy param; ignored in favor of SQLite query.

        Returns:
            The cached evidence/appraisal dict if found and valid, else None.
        """
        events = self._store.query(
            event_type=EventType.EVIDENCE_BATCH_COMPLETED,
            cache_key=cache_key,
            spiral_round_lt=current_round,
            limit=10,
        )
        for event in events:
            payload = event.payload or {}
            evidence_list = payload.get("evidence", [])
            for ev in evidence_list:
                if ev.get("cache_key") == cache_key:
                    logger.debug(
                        "Cache hit for key %s (round %d → %d)",
                        cache_key, event.spiral_round, current_round,
                    )
                    try:
                        from deerflow.runtime.cer_authoring.event_bus.metrics import metrics_collector
                        metrics_collector.inc("spiral_cache.hits_total")
                    except Exception:
                        pass
                    return ev
        try:
            from deerflow.runtime.cer_authoring.event_bus.metrics import metrics_collector
            metrics_collector.inc("spiral_cache.misses_total")
        except Exception:
            pass
        return None

    def attach_cache_key(self, article: dict[str, Any]) -> dict[str, Any]:
        """Attach a cache_key to an article dict (mutates in place)."""
        article["cache_key"] = self.compute_cache_key(article)
        return article
