import asyncio
from pathlib import Path
from types import SimpleNamespace

from deerflow.runtime.cer_review import review_assist_lead_agent as lead_agent
from deerflow.runtime.cer_review.review_assist_state_machine import (
    ReviewAssistState,
    ReviewAssistStateMachine,
)


class _ToolJsonErrorExecutor:
    def __init__(self, *_args, **_kwargs):
        pass

    async def _aexecute(self, _task_prompt):
        return SimpleNamespace(
            status="failed",
            result="invalid function arguments json string",
            error="invalid function arguments json string",
        )


def test_gap_analysis_done_retry_exhaustion_routes_to_blocked(tmp_path, monkeypatch):
    sm = ReviewAssistStateMachine(
        project_id="project-021",
        review_session_id="session-g5",
        artifact_root=Path(tmp_path),
        _current_state=ReviewAssistState.GAP_ANALYSIS_DONE,
    )
    state = {
        "project_id": "project-021",
        "review_session_id": "session-g5",
        "artifact_root": str(tmp_path),
        "state_machine": sm,
        "inline_file_context": "",
        "stage_data": {},
    }

    monkeypatch.setattr(lead_agent, "SubagentExecutor", _ToolJsonErrorExecutor)

    result = asyncio.run(
        lead_agent._run_skill_stage(
            lead_agent.SKILL_LOGIC_QA,
            state,
            {},
            ReviewAssistState.SEVERITY_SYNTHESIS_DONE,
            "Run severity synthesis.",
        )
    )

    assert result["status"] == "degraded"
    assert sm.current_state == ReviewAssistState.BLOCKED
    assert sm.history[-1]["from_state"] == ReviewAssistState.GAP_ANALYSIS_DONE.value
    assert sm.history[-1]["to_state"] == ReviewAssistState.BLOCKED.value
