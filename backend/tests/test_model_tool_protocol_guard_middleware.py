from __future__ import annotations

import asyncio

import pytest
from langchain_core.messages import AIMessage

from deerflow.agents.middlewares.model_protocol_guard_middleware import (
    ModelToolProtocolError,
    ModelToolProtocolGuardMiddleware,
    looks_like_textual_tool_call,
)
from deerflow.agents.middlewares.tool_error_handling_middleware import (
    build_lead_runtime_middlewares,
    build_subagent_runtime_middlewares,
)


def test_detects_minimax_xml_function_call_without_native_tool_calls() -> None:
    message = AIMessage(
        content=(
            "<function_calls>"
            '<invoke name="search_cer_sections">'
            "<parameter name=\"query\">SOTA</parameter>"
            "</invoke>"
            "</function_calls>"
        )
    )

    assert looks_like_textual_tool_call(message)

    middleware = ModelToolProtocolGuardMiddleware()
    with pytest.raises(ModelToolProtocolError, match="MODEL_TOOL_PROTOCOL_UNSUPPORTED"):
        middleware.after_model({"messages": [message]}, runtime=None)  # type: ignore[arg-type]


def test_allows_native_tool_calls_even_when_content_mentions_xml() -> None:
    message = AIMessage(
        content="<function_calls>",
        tool_calls=[{"name": "search", "args": {"q": "test"}, "id": "tc-1", "type": "tool_call"}],
    )

    assert not looks_like_textual_tool_call(message)
    assert ModelToolProtocolGuardMiddleware().after_model({"messages": [message]}, runtime=None) is None  # type: ignore[arg-type]


def test_async_guard_raises_same_protocol_error() -> None:
    message = AIMessage(content='<invoke name="pubmed_search"></invoke>')

    async def run() -> None:
        with pytest.raises(ModelToolProtocolError, match="native tool-call capable model"):
            await ModelToolProtocolGuardMiddleware().aafter_model({"messages": [message]}, runtime=None)  # type: ignore[arg-type]

    asyncio.run(run())


def test_protocol_guard_is_installed_in_shared_agent_runtimes() -> None:
    assert any(isinstance(m, ModelToolProtocolGuardMiddleware) for m in build_lead_runtime_middlewares())
    assert any(isinstance(m, ModelToolProtocolGuardMiddleware) for m in build_subagent_runtime_middlewares())
