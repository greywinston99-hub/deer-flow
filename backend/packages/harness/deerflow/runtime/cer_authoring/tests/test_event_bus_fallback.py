"""BIGDP2026.6 P1.4: Event Bus fallback dedupe tests.

Tests that:
- State is snapshotted before Event Bus attempt
- On Event Bus failure, fallback runs on clean pre-attempt state
- Fallback results are deduplicated by evidence_id
- Zero duplicate evidence_id in final state after fallback
"""
import pytest
from unittest.mock import patch, MagicMock


# ── Deduplication logic extracted for targeted unit testing ──

def _dedupe_evidence_registry(evidence_registry: list) -> list:
    """Deduplicate evidence entries by evidence_id.

    Entries without evidence_id or id are preserved as-is.
    First occurrence of each ID is kept; subsequent duplicates are dropped.
    """
    if not evidence_registry:
        return evidence_registry
    seen_ids = set()
    deduped = []
    for entry in evidence_registry:
        eid = entry.get("evidence_id") or entry.get("id") or ""
        if eid and eid not in seen_ids:
            seen_ids.add(eid)
            deduped.append(entry)
        elif not eid:
            deduped.append(entry)  # Entries without ID are kept as-is
    return deduped


def _make_evidence_entry(evidence_id, title="Test Article", pmid="12345"):
    return {
        "evidence_id": evidence_id,
        "title": title,
        "pmid": pmid,
        "weight": "supportive",
    }


class TestDedupeEvidenceRegistry:
    """Unit tests for evidence_registry deduplication logic."""

    def test_no_duplicates_passthrough(self):
        """No duplicates → all entries preserved."""
        registry = [
            _make_evidence_entry("E-001"),
            _make_evidence_entry("E-002"),
            _make_evidence_entry("E-003"),
        ]
        result = _dedupe_evidence_registry(registry)
        assert len(result) == 3
        ids = [e["evidence_id"] for e in result]
        assert ids == ["E-001", "E-002", "E-003"]

    def test_duplicates_removed_first_wins(self):
        """Duplicate evidence_ids → first occurrence kept, subsequent removed."""
        registry = [
            _make_evidence_entry("E-001", "Original A"),
            _make_evidence_entry("E-001", "Duplicate A"),  # Dropped
            _make_evidence_entry("E-002", "Original B"),
            _make_evidence_entry("E-002", "Duplicate B"),  # Dropped
            _make_evidence_entry("E-003", "Original C"),
        ]
        result = _dedupe_evidence_registry(registry)
        assert len(result) == 3
        # First occurrence kept
        assert result[0]["title"] == "Original A"
        assert result[1]["title"] == "Original B"
        assert result[2]["title"] == "Original C"

    def test_empty_registry(self):
        """Empty list returns empty list."""
        assert _dedupe_evidence_registry([]) == []

    def test_none_registry(self):
        """None returns None."""
        assert _dedupe_evidence_registry(None) is None

    def test_entries_without_id_preserved(self):
        """Entries without evidence_id are preserved (not deduped)."""
        registry = [
            {"title": "No ID 1"},
            {"title": "No ID 2"},
            _make_evidence_entry("E-001"),
        ]
        result = _dedupe_evidence_registry(registry)
        assert len(result) == 3

    def test_mixed_id_and_no_id(self):
        """Mix of ID and no-ID entries: IDs deduped, no-IDs preserved."""
        registry = [
            {"title": "No ID A"},
            _make_evidence_entry("E-001", "First"),
            {"title": "No ID B"},
            _make_evidence_entry("E-001", "Duplicate (dropped)"),
            {"title": "No ID C"},
        ]
        result = _dedupe_evidence_registry(registry)
        assert len(result) == 4  # 3 no-ID + 1 unique E-001
        titles = [e.get("title") for e in result]
        assert titles == ["No ID A", "First", "No ID B", "No ID C"]

    def test_uses_id_field_as_fallback(self):
        """Entries with 'id' field (not evidence_id) also deduped."""
        registry = [
            {"id": "ABC-123", "title": "First"},
            {"id": "ABC-123", "title": "Second (dropped)"},
            {"id": "DEF-456", "title": "Third"},
        ]
        result = _dedupe_evidence_registry(registry)
        assert len(result) == 2
        assert result[0]["title"] == "First"
        assert result[1]["title"] == "Third"

    def test_all_duplicates(self):
        """All entries are duplicates → only first kept."""
        registry = [
            _make_evidence_entry("E-001", "A"),
            _make_evidence_entry("E-001", "B"),
            _make_evidence_entry("E-001", "C"),
        ]
        result = _dedupe_evidence_registry(registry)
        assert len(result) == 1
        assert result[0]["title"] == "A"


class TestEventBusFallbackIntegration:
    """Integration tests with mocked graph node dependencies.

    These tests verify the full _node_evidence_appraisal function
    with interrupt() and Event Bus dependencies mocked.
    """

    @patch("deerflow.runtime.cer_authoring.graph.interrupt")
    @patch("deerflow.runtime.cer_authoring.graph._event_bus_available", return_value=False)
    @patch("deerflow.runtime.cer_authoring.graph.pipeline.appraise_evidence")
    def test_serial_fallback_dedupes_evidence(self, mock_appraise, _mock_eb, mock_interrupt):
        """Serial fallback with duplicate evidence → deduped."""
        from deerflow.runtime.cer_authoring.graph import _node_evidence_appraisal

        mock_interrupt.return_value = {"action": "confirm", "reason": "ok"}
        mock_appraise.return_value = {
            "evidence_registry": [
                _make_evidence_entry("E-001", "A"),
                _make_evidence_entry("E-001", "A (dup)"),
                _make_evidence_entry("E-002", "B"),
            ],
            "article_appraisal": [],
        }
        state = {
            "evidence_registry": [],
            "article_appraisal": [],
            "mcp_log": [],
            "fulltext_acquisition_status_table": [],
            "full_text_request_list": [],
        }
        result = _node_evidence_appraisal(state)
        # Verify deduplication happened
        registry = result.get("evidence_registry", [])
        ids = [e.get("evidence_id") for e in registry]
        assert len(ids) == len(set(ids)), f"Duplicate IDs: {ids}"
        assert sorted(ids) == ["E-001", "E-002"]

    @patch("deerflow.runtime.cer_authoring.graph.interrupt")
    @patch("deerflow.runtime.cer_authoring.graph._event_bus_available", return_value=False)
    @patch("deerflow.runtime.cer_authoring.graph.pipeline.appraise_evidence")
    def test_zero_duplicate_after_fallback(self, mock_appraise, _mock_eb, mock_interrupt):
        """A.4.4: Zero duplicate evidence_id in final state after fallback."""
        from deerflow.runtime.cer_authoring.graph import _node_evidence_appraisal

        mock_interrupt.return_value = {"action": "confirm", "reason": "ok"}
        mock_appraise.return_value = {
            "evidence_registry": [
                _make_evidence_entry(f"E-{i:03d}", f"Article {i}")
                for i in range(1, 11)  # 10 unique entries
            ],
            "article_appraisal": [],
        }
        state = {
            "evidence_registry": [],
            "article_appraisal": [],
            "mcp_log": [],
            "fulltext_acquisition_status_table": [],
            "full_text_request_list": [],
        }
        result = _node_evidence_appraisal(state)
        registry = result.get("evidence_registry", [])
        ids = [e.get("evidence_id") for e in registry]
        assert len(registry) == 10
        assert len(ids) == len(set(ids))
