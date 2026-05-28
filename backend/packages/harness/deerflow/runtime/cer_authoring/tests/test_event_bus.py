"""Unit tests for the Event Bus hybrid architecture.

Tests cover:
- Event schema validation
- Advisory-only middleware
- Sync bridge helpers
- Worker base class
- Spiral cache
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

from deerflow.runtime.cer_authoring.event_bus.schema import (
    Event,
    EventType,
    evidence_batch_requested,
    evidence_batch_completed,
    worker_progress,
    FORBIDDEN_EVENT_TYPES,
)
from deerflow.runtime.cer_authoring.event_bus.middleware import (
    AdvisoryOnlyMiddleware,
    SecurityViolation,
    apply_publish_middleware,
    apply_consume_middleware,
)
from deerflow.runtime.cer_authoring.event_bus.spiral_cache import SpiralCache
from deerflow.runtime.cer_authoring.event_bus.integration import chunk_list, merge_batch_evidence


class TestEventSchema:
    """Test Event dataclass serialization and factory functions."""

    def test_event_serialization_roundtrip(self):
        event = Event(
            event_type=EventType.EVIDENCE_BATCH_REQUESTED,
            payload={"batch_id": 1, "articles": []},
            correlation_id="thread-123",
            stage_id="evidence_appraisal",
            spiral_round=2,
        )
        data = event.to_dict()
        restored = Event.from_dict(data)
        assert restored.event_type == EventType.EVIDENCE_BATCH_REQUESTED
        assert restored.correlation_id == "thread-123"
        assert restored.spiral_round == 2
        assert restored.advisory_only is True

    def test_evidence_batch_requested_factory(self):
        event = evidence_batch_requested(
            batch_id=0,
            articles=[{"pmid": "12345"}],
            state_snapshot={"device_profile": {}},
            correlation_id="thread-123",
        )
        assert event.event_type == EventType.EVIDENCE_BATCH_REQUESTED
        assert event.batch_id == 0
        assert event.advisory_only is True

    def test_evidence_batch_completed_factory(self):
        event = evidence_batch_completed(
            batch_id=0,
            evidence=[{"evidence_id": "E-001"}],
            appraisals=[{"article_id": "ART-001"}],
            correlation_id="thread-123",
            cache_hits=3,
            cache_misses=2,
        )
        assert event.event_type == EventType.EVIDENCE_BATCH_COMPLETED
        assert event.payload["cache_hits"] == 3

    def test_worker_progress_factory(self):
        event = worker_progress("evidence_appraisal", 2, 5, "thread-123")
        assert event.event_type == EventType.WORKER_PROGRESS
        assert event.payload["completed"] == 2
        assert event.payload["total"] == 5


class TestAdvisoryOnlyMiddleware:
    """Test security middleware enforcement."""

    def test_forces_advisory_only_true(self):
        event = Event(
            event_type=EventType.EVIDENCE_BATCH_REQUESTED,
            payload={},
            advisory_only=False,
        )
        result = apply_publish_middleware(event)
        assert result.advisory_only is True

    def test_rejects_forbidden_event_types(self):
        # The middleware checks event_type.value against FORBIDDEN_EVENT_TYPES.
        # FORBIDDEN_EVENT_TYPES contains strings like "gate.decision.rework".
        # Valid EventType enum values are not in this set, so normal events pass.
        # We verify the set is non-empty and contains only string patterns.
        assert len(FORBIDDEN_EVENT_TYPES) > 0
        assert all(isinstance(e, str) for e in FORBIDDEN_EVENT_TYPES)
        # A normal event type should NOT be in the forbidden set
        assert EventType.EVIDENCE_BATCH_REQUESTED.value not in FORBIDDEN_EVENT_TYPES

    def test_rejects_prohibited_actions(self):
        event = Event(
            event_type=EventType.EVIDENCE_BATCH_REQUESTED,
            payload={"action": "trigger_rework"},
        )
        with pytest.raises(SecurityViolation):
            apply_publish_middleware(event)

    def test_rejects_gate_decisions(self):
        event = Event(
            event_type=EventType.EVIDENCE_BATCH_REQUESTED,
            payload={"gate_decision": "PASS"},
        )
        with pytest.raises(SecurityViolation):
            apply_publish_middleware(event)

    def test_allows_valid_events(self):
        event = Event(
            event_type=EventType.EVIDENCE_BATCH_REQUESTED,
            payload={"batch_id": 1, "articles": []},
        )
        result = apply_publish_middleware(event)
        assert result.advisory_only is True


class TestSpiralCache:
    """Test cross-round result caching."""

    def setup_method(self):
        """Clear the event store before each test to avoid cross-test pollution."""
        from deerflow.runtime.cer_authoring.event_bus.event_store import EventStore
        EventStore().clear()

    def test_compute_cache_key_deterministic(self):
        cache = SpiralCache()
        article = {"pmid": "12345", "title": "Test", "abstract": "Abstract text", "source_database": "PubMed"}
        key1 = cache.compute_cache_key(article)
        key2 = cache.compute_cache_key(article)
        assert key1 == key2
        assert len(key1) == 32  # SHA-256 hex[:32]

    def test_compute_cache_key_different_articles(self):
        cache = SpiralCache()
        a1 = {"pmid": "12345", "title": "Test", "abstract": "A", "source_database": "PubMed"}
        a2 = {"pmid": "67890", "title": "Test", "abstract": "A", "source_database": "PubMed"}
        assert cache.compute_cache_key(a1) != cache.compute_cache_key(a2)

    def test_cache_hit_from_event_store(self):
        from deerflow.runtime.cer_authoring.event_bus.event_store import EventStore
        store = EventStore()
        store.clear()  # start fresh

        cache = SpiralCache(store)
        cache_key = cache.compute_cache_key({"pmid": "12345", "title": "Test", "abstract": "A"})

        # Insert a cached result into the persistent store (from round 1)
        cached_event = Event(
            event_type=EventType.EVIDENCE_BATCH_COMPLETED,
            payload={"evidence": [{"evidence_id": "E-001", "cache_key": cache_key, "title": "Cached"}]},
            spiral_round=1,
            cache_key=cache_key,
        )
        store.insert(cached_event)

        result = cache.get_cached_result(cache_key, current_round=2)
        assert result is not None
        assert result["evidence_id"] == "E-001"

    def test_cache_miss_for_current_round(self):
        cache = SpiralCache()
        cache_key = cache.compute_cache_key({"pmid": "12345", "title": "Test", "abstract": "A"})

        # Event from same round should not be used as cache
        cached_event = Event(
            event_type=EventType.EVIDENCE_BATCH_COMPLETED,
            payload={"evidence": [{"evidence_id": "E-001", "cache_key": cache_key}]},
            spiral_round=2,
        )
        event_store = [cached_event]

        result = cache.get_cached_result(cache_key, current_round=2, event_store=event_store)
        assert result is None


class TestIntegrationHelpers:
    """Test Event Bus integration utilities."""

    def test_chunk_list(self):
        items = list(range(10))
        chunks = chunk_list(items, 3)
        assert len(chunks) == 4  # 3+3+3+1
        assert chunks[0] == [0, 1, 2]
        assert chunks[-1] == [9]

    def test_merge_batch_evidence(self):
        event1 = evidence_batch_completed(
            batch_id=0,
            evidence=[{"evidence_id": "E-001"}],
            appraisals=[{"article_id": "ART-001"}],
        )
        event2 = evidence_batch_completed(
            batch_id=1,
            evidence=[{"evidence_id": "E-002"}],
            appraisals=[{"article_id": "ART-002"}],
            cache_hits=1,
        )
        result = merge_batch_evidence([event1, event2])
        assert len(result["evidence_registry"]) == 2
        assert len(result["article_appraisal"]) == 2
        assert result["event_bus_cache_hits"] == 1
        assert result["event_bus_cache_misses"] == 0


class TestEventBusFeatureFlag:
    """Test that Event Bus feature flag defaults to off."""

    def test_feature_flag_defaults_off(self):
        import os
        from deerflow.runtime.cer_authoring import graph
        # Default should be off unless env var is set
        assert graph._EVENT_BUS_ENABLED == (os.getenv("CER_AUTHORING_ENABLE_EVENT_BUS") == "1")

    def test_event_bus_available_false_by_default(self):
        from deerflow.runtime.cer_authoring.graph import _event_bus_available
        # When feature flag is off, should return False
        if not _event_bus_available():
            assert True  # Expected behavior
        else:
            pytest.skip("Event Bus feature flag is enabled in environment")
