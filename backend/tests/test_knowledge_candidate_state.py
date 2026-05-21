"""Tests for Knowledge Candidate State Machine.

Verifies:
- State transitions are valid
- NORMALIZED -> PUBLISHED is BLOCKED (security hardening)
- All publication requires human review approval
"""

import pytest
import sys
from pathlib import Path

# Add harness to path
sys.path.insert(0, str(Path(__file__).parent.parent / "packages" / "harness"))

from deerflow.runtime.cer_review.knowledge_candidate_state import (
    KnowledgeCandidate,
    CandidateState,
    STATE_TRANSITIONS,
    AssetType,
)


class TestKnowledgeCandidateStateMachine:
    """Test the knowledge candidate state machine transitions."""

    def test_extracted_can_transition_to_normalized(self):
        """EXTRACTED -> NORMALIZED is allowed."""
        candidate = KnowledgeCandidate(
            asset_type=AssetType.RULE_UNIT,
            source_artifact="test.json",
            source_chain=["project1", "run1"],
            payload={},
            confidence=0.8,
            project_id="test-project",
        )
        assert candidate.can_transition(CandidateState.NORMALIZED) is True

    def test_normalized_cannot_transition_directly_to_published(self):
        """HARDENING: NORMALIZED -> PUBLISHED is BLOCKED.

        All machine asset publication requires explicit human review approval.
        Candidate must go through: EXTRACTED -> NORMALIZED -> NEEDS_HUMAN_REVIEW -> APPROVED -> PUBLISHED
        """
        candidate = KnowledgeCandidate(
            asset_type=AssetType.RULE_UNIT,
            source_artifact="test.json",
            source_chain=["project1", "run1"],
            payload={},
            confidence=0.8,
            project_id="test-project",
        )
        # First transition to NORMALIZED
        candidate.transition(CandidateState.NORMALIZED)

        # NORMALIZED -> PUBLISHED should be BLOCKED
        assert candidate.can_transition(CandidateState.PUBLISHED) is False

        # Attempting the transition should raise ValueError
        with pytest.raises(ValueError, match="Invalid transition"):
            candidate.transition(CandidateState.PUBLISHED)

    def test_normalized_must_go_through_human_review(self):
        """NORMALIZED must transition to NEEDS_HUMAN_REVIEW, not directly to PUBLISHED."""
        candidate = KnowledgeCandidate(
            asset_type=AssetType.RULE_UNIT,
            source_artifact="test.json",
            source_chain=["project1", "run1"],
            payload={},
            confidence=0.8,
            project_id="test-project",
        )
        candidate.transition(CandidateState.NORMALIZED)

        # NORMALIZED -> NEEDS_HUMAN_REVIEW is allowed
        assert candidate.can_transition(CandidateState.NEEDS_HUMAN_REVIEW) is True

        # Transition to human review
        candidate.transition(CandidateState.NEEDS_HUMAN_REVIEW)

        # NEEDS_HUMAN_REVIEW -> APPROVED is allowed
        assert candidate.can_transition(CandidateState.APPROVED) is True

        # Transition to approved
        candidate.transition(CandidateState.APPROVED)

        # APPROVED -> PUBLISHED is allowed
        assert candidate.can_transition(CandidateState.PUBLISHED) is True

    def test_full_valid_transition_path(self):
        """Test the full valid path: extracted -> normalized -> needs_review -> approved -> published."""
        candidate = KnowledgeCandidate(
            asset_type=AssetType.RULE_UNIT,
            source_artifact="test.json",
            source_chain=["project1", "run1"],
            payload={},
            confidence=0.8,
            project_id="test-project",
        )

        # Execute full valid path
        candidate.transition(CandidateState.NORMALIZED)
        assert candidate.state == CandidateState.NORMALIZED

        candidate.transition(CandidateState.NEEDS_HUMAN_REVIEW)
        assert candidate.state == CandidateState.NEEDS_HUMAN_REVIEW

        candidate.transition(CandidateState.APPROVED)
        assert candidate.state == CandidateState.APPROVED

        candidate.transition(CandidateState.PUBLISHED)
        assert candidate.state == CandidateState.PUBLISHED

    def test_rejected_is_terminal(self):
        """REJECTED is a terminal state with no outgoing transitions."""
        candidate = KnowledgeCandidate(
            asset_type=AssetType.RULE_UNIT,
            source_artifact="test.json",
            source_chain=["project1", "run1"],
            payload={},
            confidence=0.8,
            project_id="test-project",
        )

        candidate.transition(CandidateState.NORMALIZED)
        candidate.transition(CandidateState.NEEDS_HUMAN_REVIEW)
        candidate.transition(CandidateState.REJECTED)

        # REJECTED has no valid transitions
        for state in CandidateState:
            assert candidate.can_transition(state) is False

    def test_published_is_terminal(self):
        """PUBLISHED is a terminal state with no outgoing transitions."""
        candidate = KnowledgeCandidate(
            asset_type=AssetType.RULE_UNIT,
            source_artifact="test.json",
            source_chain=["project1", "run1"],
            payload={},
            confidence=0.8,
            project_id="test-project",
        )

        # Go to published via valid path
        candidate.transition(CandidateState.NORMALIZED)
        candidate.transition(CandidateState.NEEDS_HUMAN_REVIEW)
        candidate.transition(CandidateState.APPROVED)
        candidate.transition(CandidateState.PUBLISHED)

        # PUBLISHED has no valid transitions
        for state in CandidateState:
            assert candidate.can_transition(state) is False

    def test_parked_can_requeue(self):
        """PARKED candidates can be re-queued for human review."""
        candidate = KnowledgeCandidate(
            asset_type=AssetType.RULE_UNIT,
            source_artifact="test.json",
            source_chain=["project1", "run1"],
            payload={},
            confidence=0.8,
            project_id="test-project",
        )

        candidate.transition(CandidateState.NORMALIZED)
        candidate.transition(CandidateState.NEEDS_HUMAN_REVIEW)
        candidate.transition(CandidateState.PARKED)

        # PARKED -> NEEDS_HUMAN_REVIEW is allowed (re-queue)
        assert candidate.can_transition(CandidateState.NEEDS_HUMAN_REVIEW) is True

    def test_state_transitions_mapping(self):
        """Verify STATE_TRANSITIONS dict has correct structure."""
        # Verify NORMALIZED only allows NEEDS_HUMAN_REVIEW, not PUBLISHED
        normalized_transitions = STATE_TRANSITIONS[CandidateState.NORMALIZED]
        assert CandidateState.PUBLISHED not in normalized_transitions
        assert CandidateState.NEEDS_HUMAN_REVIEW in normalized_transitions

        # Verify APPROVED allows PUBLISHED
        approved_transitions = STATE_TRANSITIONS[CandidateState.APPROVED]
        assert CandidateState.PUBLISHED in approved_transitions