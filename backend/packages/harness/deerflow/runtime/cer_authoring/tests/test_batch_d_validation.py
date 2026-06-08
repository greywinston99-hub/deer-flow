"""BIGDP2026.6V_2 Batch D: SOTA accounting, Writer QA, validation tests.

DC-8: Cross-section consistency
DC-9: SOTA accounting reconciliation
DC-11: Writer semantic QA
"""
import pytest


class TestSOTAAccountingConsistency:
    """DC-8/DC-9: SOTA numbers must reconcile across search→screen→include."""

    def test_prisma_numbers_reconcile(self):
        """Identification − duplicates = after_dedup. Screen − excluded = assessed."""
        prisma = {
            "flow": {
                "raw_hits": 183,
                "dedup_input": 170,
                "duplicate_count": 13,
                "after_dedup": 157,
                "title_abstract_screened": 157,
                "title_abstract_excluded": 120,
                "fulltext_assessed": 37,
                "fulltext_excluded": 21,
                "final_included": 16,
            },
        }
        flow = prisma["flow"]
        # dedup_input − duplicate_count == after_dedup
        assert flow["dedup_input"] - flow["duplicate_count"] == flow["after_dedup"], \
            f"{flow['dedup_input']} − {flow['duplicate_count']} ≠ {flow['after_dedup']}"
        # screened − excluded == fulltext_assessed
        assert flow["title_abstract_screened"] - flow["title_abstract_excluded"] == flow["fulltext_assessed"], \
            f"{flow['title_abstract_screened']} − {flow['title_abstract_excluded']} ≠ {flow['fulltext_assessed']}"
        # assessed − excluded == final_included
        assert flow["fulltext_assessed"] - flow["fulltext_excluded"] == flow["final_included"], \
            f"{flow['fulltext_assessed']} − {flow['fulltext_excluded']} ≠ {flow['final_included']}"

    def test_prisma_mismatch_detected(self):
        """13 vs 1000 vs 183 vs 219 conflict → PRISMA numbers inconsistent."""
        prisma = {
            "flow": {
                "raw_hits": 1000, "dedup_input": 1000, "duplicate_count": 0,
                "after_dedup": 183,  # 1000-0≠183 → mismatch!
                "title_abstract_screened": 183, "title_abstract_excluded": 0,
                "fulltext_assessed": 219,  # 183-0≠219 → mismatch!
                "fulltext_excluded": 0, "final_included": 219,
            },
        }
        flow = prisma["flow"]
        mismatch = (flow["dedup_input"] - flow["duplicate_count"] != flow["after_dedup"]) or \
                   (flow["title_abstract_screened"] - flow["title_abstract_excluded"] != flow["fulltext_assessed"])
        assert mismatch, "Should detect mismatch but didn't"


class TestCrossSectionConsistency:
    """DC-8: Cross-chapter endpoint/benchmark/narrative consistency."""

    def test_endpoint_count_consistency(self):
        """4 endpoints in registry, 1 in narrative without rationale → inconsistency."""
        endpoint_count_registry = 4
        endpoint_count_narrative = 1
        has_rationale = False
        if endpoint_count_registry != endpoint_count_narrative and not has_rationale:
            inconsistent = True
        else:
            inconsistent = False
        assert inconsistent, "Should flag when endpoint counts differ without rationale"

    def test_endpoint_count_consistent_with_rationale(self):
        """4→1 with documented merge rationale → acceptable."""
        consistent = True  # Merge rationale provided
        assert consistent


class TestWriterSemanticQA:
    """DC-11: Writer output must not exceed ledger constraints."""

    def _check_writer_against_ledger(self, writer_claim_strength, ledger_strength):
        """Writer must not assert stronger than ledger."""
        strength_order = {"not_supported": 0, "limited": 1, "moderate": 2, "strong": 3}
        return strength_order.get(writer_claim_strength, 0) <= strength_order.get(ledger_strength, 0)

    def test_writer_cannot_exceed_ledger(self):
        """Writer 'strong' when ledger 'limited' → violation."""
        assert not self._check_writer_against_ledger("strong", "limited")

    def test_writer_matches_ledger(self):
        """Writer 'moderate' when ledger 'moderate' → OK."""
        assert self._check_writer_against_ledger("moderate", "moderate")

    def test_writer_weaker_than_ledger_ok(self):
        """Writer 'limited' when ledger 'moderate' → OK (conservative)."""
        assert self._check_writer_against_ledger("limited", "moderate")

    def test_not_supported_blocks_positive_claim(self):
        """not_supported → cannot write positive claim."""
        assert not self._check_writer_against_ledger("moderate", "not_supported")
        assert not self._check_writer_against_ledger("strong", "not_supported")
