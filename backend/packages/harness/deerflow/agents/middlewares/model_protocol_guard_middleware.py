"""Model protocol guards for tool-using agent runtimes."""

from __future__ import annotations

import re
from typing import Any, override

from langchain.agents import AgentState
from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import AIMessage
from langgraph.runtime import Runtime


class ModelToolProtocolError(RuntimeError):
    """Raised when a model emits textual tool markup instead of native tool calls."""


_FUNCTION_CALL_XML_RE = re.compile(
    r"<\s*function_calls?\s*>|<\s*invoke\s+name\s*=|<\s*tool_call\s*>",
    flags=re.IGNORECASE,
)


def _content_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                text = block.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "\n".join(parts)
    return str(content or "")


def looks_like_textual_tool_call(message: AIMessage) -> bool:
    """Return true when a model produced XML-like function-call text without native tool_calls."""
    if getattr(message, "tool_calls", None):
        return False
    if getattr(message, "invalid_tool_calls", None):
        return False
    content = _content_text(message.content)
    return bool(_FUNCTION_CALL_XML_RE.search(content))


class ModelToolProtocolGuardMiddleware(AgentMiddleware[AgentState]):
    """Fail fast when a provider returns MiniMax-style XML function calls as text.

    LangGraph only executes native ``AIMessage.tool_calls``. If a provider emits
    ``<function_calls>`` / ``<invoke name=...>`` markup inside message content,
    the run can silently skip tools. That is more dangerous than a hard failure,
    especially for CER workflows where evidence retrieval and gate tools must
    actually execute.
    """

    def _guard(self, state: AgentState) -> None:
        messages = state.get("messages", [])
        if not messages:
            return
        last = messages[-1]
        if not isinstance(last, AIMessage):
            return
        if not looks_like_textual_tool_call(last):
            return
        raise ModelToolProtocolError(
            "MODEL_TOOL_PROTOCOL_UNSUPPORTED: model emitted XML/textual function_calls instead of native tool_calls. "
            "LangGraph will not execute these tools. Route tool-using DeerFlow nodes to a native tool-call capable model "
            "or add a tested provider adapter before retrying."
        )

    @override
    def after_model(self, state: AgentState, runtime: Runtime) -> dict | None:
        self._guard(state)
        return None

    @override
    async def aafter_model(self, state: AgentState, runtime: Runtime) -> dict | None:
        self._guard(state)
        return None

