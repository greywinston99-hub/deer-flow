from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult

from deerflow.models import failover_router as router_module


class FakeRateLimitError(Exception):
    def __init__(self, status_code: int, message: str = "provider temporarily unavailable"):
        super().__init__(message)
        self.response = type("Response", (), {"status_code": status_code, "text": message})()


class StubModel(BaseChatModel):
    response_text: str = "ok"
    fail_with: Exception | None = None
    stream_chunks: list[str] | None = None

    @property
    def _llm_type(self) -> str:
        return "stub"

    def bind_tools(self, tools, *, tool_choice=None, **kwargs):
        return self.bind(tools=tools, tool_choice=tool_choice, **kwargs)

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        if self.fail_with is not None:
            raise self.fail_with
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=self.response_text))])

    async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):
        return self._generate(messages, stop=stop, run_manager=run_manager, **kwargs)

    def _stream(self, messages, stop=None, run_manager=None, **kwargs):
        if self.fail_with is not None:
            raise self.fail_with
        for index, chunk in enumerate(self.stream_chunks or [self.response_text]):
            yield ChatGenerationChunk(
                message=AIMessageChunk(
                    content=chunk,
                    chunk_position="last" if index == len(self.stream_chunks or [self.response_text]) - 1 else None,
                )
            )

    async def _astream(self, messages, stop=None, run_manager=None, **kwargs):
        for chunk in self._stream(messages, stop=stop, run_manager=run_manager, **kwargs):
            yield chunk


def _make_router(tmp_path: Path) -> router_module.FailoverChatModel:
    return router_module.FailoverChatModel(
        model="minimax-m2.7",
        primary_model_name="minimax-primary",
        fallback_model_name="kimi-k2.5",
        cooldown_seconds=900,
        state_file=str(tmp_path / "failover-state.json"),
    )


def test_failsover_to_fallback_and_persists_cooldown(monkeypatch, tmp_path):
    router = _make_router(tmp_path)
    models = {
        "minimax-primary": StubModel(fail_with=FakeRateLimitError(529)),
        "kimi-k2.5": StubModel(response_text="fallback ok"),
    }
    monkeypatch.setattr(router_module, "create_chat_model", lambda name=None, **kwargs: models[name])

    result = router.invoke([HumanMessage(content="hello")])

    assert result.content == "fallback ok"
    state = router._load_state()
    assert state["active_model_name"] == "kimi-k2.5"
    assert state["cooldown_until"] > 0


def test_uses_fallback_during_cooldown_without_touching_primary(monkeypatch, tmp_path):
    router = _make_router(tmp_path)
    router._save_state({"active_model_name": "kimi-k2.5", "cooldown_until": 9999999999, "updated_at": 0})

    primary = StubModel(fail_with=AssertionError("primary should not be called during cooldown"))
    fallback = StubModel(response_text="warm fallback")
    models = {
        "minimax-primary": primary,
        "kimi-k2.5": fallback,
    }
    monkeypatch.setattr(router_module, "create_chat_model", lambda name=None, **kwargs: models[name])

    result = router.invoke([HumanMessage(content="hello")])

    assert result.content == "warm fallback"


def test_returns_to_primary_after_cooldown(monkeypatch, tmp_path):
    router = _make_router(tmp_path)
    router._save_state({"active_model_name": "kimi-k2.5", "cooldown_until": 1, "updated_at": 0})

    models = {
        "minimax-primary": StubModel(response_text="primary back"),
        "kimi-k2.5": StubModel(response_text="fallback"),
    }
    monkeypatch.setattr(router_module, "create_chat_model", lambda name=None, **kwargs: models[name])

    result = asyncio.run(router.ainvoke([HumanMessage(content="hello")]))

    assert result.content == "primary back"
    assert router._load_state()["cooldown_until"] == 0


def test_stream_falls_back_before_first_chunk(monkeypatch, tmp_path):
    router = _make_router(tmp_path)
    models = {
        "minimax-primary": StubModel(fail_with=FakeRateLimitError(529)),
        "kimi-k2.5": StubModel(stream_chunks=["fall", "back"]),
    }
    monkeypatch.setattr(router_module, "create_chat_model", lambda name=None, **kwargs: models[name])

    chunks = list(router.stream([HumanMessage(content="hello")]))

    assert "".join(chunk.content for chunk in chunks) == "fallback"
