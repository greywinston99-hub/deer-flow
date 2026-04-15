"""Timed failover chat model wrapper.

Routes requests to a primary model by default, automatically falls back to a
secondary model on transient provider failures, and switches back to the
primary model after a cooldown window elapses.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import AsyncIterator, Iterator, Sequence
from pathlib import Path
from typing import Any

from langchain_core.callbacks import AsyncCallbackManagerForLLMRun, CallbackManagerForLLMRun
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessageChunk, BaseMessage
from langchain_core.outputs import ChatGenerationChunk, ChatResult
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool
from langchain_core.utils.function_calling import convert_to_openai_tool

from deerflow.config.paths import get_paths
from deerflow.models.factory import create_chat_model

logger = logging.getLogger(__name__)

_DEFAULT_TRIGGER_STATUS_CODES = (408, 409, 425, 429, 500, 502, 503, 504, 529)
_DEFAULT_TRIGGER_PATTERNS = (
    "server busy",
    "temporarily unavailable",
    "try again later",
    "please retry",
    "please try again",
    "overloaded",
    "high demand",
    "rate limit",
    "负载较高",
    "服务繁忙",
    "稍后重试",
    "请稍后重试",
)
_DEFAULT_TRIGGER_EXCEPTION_NAMES = (
    "APITimeoutError",
    "APIConnectionError",
    "InternalServerError",
    "RateLimitError",
    "RemoteProtocolError",
    "ReadTimeout",
    "WriteTimeout",
    "ConnectTimeout",
    "PoolTimeout",
    "ConnectError",
)


class FailoverChatModel(BaseChatModel):
    """Model wrapper that fails over to a backup model for a cooldown period."""

    model: str = "failover-router"
    primary_model_name: str
    fallback_model_name: str
    cooldown_seconds: int = 900
    state_file: str | None = None
    trigger_status_codes: list[int] = list(_DEFAULT_TRIGGER_STATUS_CODES)
    trigger_error_patterns: list[str] = list(_DEFAULT_TRIGGER_PATTERNS)
    trigger_exception_names: list[str] = list(_DEFAULT_TRIGGER_EXCEPTION_NAMES)

    @property
    def _llm_type(self) -> str:
        return "failover-router"

    @property
    def _identifying_params(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "primary_model_name": self.primary_model_name,
            "fallback_model_name": self.fallback_model_name,
            "cooldown_seconds": self.cooldown_seconds,
        }

    def model_post_init(self, __context: Any) -> None:
        if self.primary_model_name == self.fallback_model_name:
            raise ValueError("primary_model_name and fallback_model_name must be different")
        if self.cooldown_seconds < 1:
            raise ValueError("cooldown_seconds must be >= 1")
        super().model_post_init(__context)

    def bind_tools(
        self,
        tools: Sequence[dict[str, Any] | type | Any | BaseTool],
        *,
        tool_choice: str | None = None,
        **kwargs: Any,
    ) -> Runnable:
        formatted_tools = [convert_to_openai_tool(tool) for tool in tools]
        bound_kwargs: dict[str, Any] = {"tools": formatted_tools, **kwargs}
        if tool_choice is not None:
            bound_kwargs["tool_choice"] = tool_choice
        return self.bind(**bound_kwargs)

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        model_name = self._choose_model_name()
        try:
            return self._invoke_model(model_name, messages, stop=stop, run_manager=run_manager, **kwargs)
        except Exception as exc:
            if not self._should_fail_over(model_name, exc):
                raise
            fallback_name = self._activate_fallback(exc)
            return self._invoke_model(fallback_name, messages, stop=stop, run_manager=run_manager, **kwargs)

    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: AsyncCallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        model_name = self._choose_model_name()
        try:
            return await self._ainvoke_model(model_name, messages, stop=stop, run_manager=run_manager, **kwargs)
        except Exception as exc:
            if not self._should_fail_over(model_name, exc):
                raise
            fallback_name = self._activate_fallback(exc)
            return await self._ainvoke_model(fallback_name, messages, stop=stop, run_manager=run_manager, **kwargs)

    def _stream(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> Iterator[ChatGenerationChunk]:
        model_name = self._choose_model_name()
        yielded = False
        try:
            for chunk in self._iter_model_stream(model_name, messages, stop=stop, run_manager=run_manager, **kwargs):
                yielded = True
                yield chunk
        except Exception as exc:
            if yielded or not self._should_fail_over(model_name, exc):
                raise
            fallback_name = self._activate_fallback(exc)
            yield from self._iter_model_stream(fallback_name, messages, stop=stop, run_manager=run_manager, **kwargs)

    async def _astream(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: AsyncCallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[ChatGenerationChunk]:
        model_name = self._choose_model_name()
        yielded = False
        try:
            async for chunk in self._aiter_model_stream(model_name, messages, stop=stop, run_manager=run_manager, **kwargs):
                yielded = True
                yield chunk
        except Exception as exc:
            if yielded or not self._should_fail_over(model_name, exc):
                raise
            fallback_name = self._activate_fallback(exc)
            async for chunk in self._aiter_model_stream(fallback_name, messages, stop=stop, run_manager=run_manager, **kwargs):
                yield chunk

    def _invoke_model(
        self,
        model_name: str,
        messages: list[BaseMessage],
        *,
        stop: list[str] | None,
        run_manager: CallbackManagerForLLMRun | None,
        **kwargs: Any,
    ) -> ChatResult:
        model = self._build_model(model_name)
        return model._generate(messages, stop=stop, run_manager=run_manager, **kwargs)  # type: ignore[attr-defined]

    async def _ainvoke_model(
        self,
        model_name: str,
        messages: list[BaseMessage],
        *,
        stop: list[str] | None,
        run_manager: AsyncCallbackManagerForLLMRun | None,
        **kwargs: Any,
    ) -> ChatResult:
        model = self._build_model(model_name)
        if type(model)._agenerate != BaseChatModel._agenerate:  # noqa: SLF001
            return await model._agenerate(messages, stop=stop, run_manager=run_manager, **kwargs)  # type: ignore[attr-defined]
        return await asyncio.to_thread(self._invoke_model, model_name, messages, stop=stop, run_manager=None, **kwargs)

    def _iter_model_stream(
        self,
        model_name: str,
        messages: list[BaseMessage],
        *,
        stop: list[str] | None,
        run_manager: CallbackManagerForLLMRun | None,
        **kwargs: Any,
    ) -> Iterator[ChatGenerationChunk]:
        model = self._build_model(model_name)
        if type(model)._stream != BaseChatModel._stream:  # noqa: SLF001
            yield from model._stream(messages, stop=stop, run_manager=run_manager, **kwargs)  # type: ignore[attr-defined]
            return

        result = self._invoke_model(model_name, messages, stop=stop, run_manager=run_manager, **kwargs)
        message = result.generations[0].message
        yield ChatGenerationChunk(message=AIMessageChunk(**message.model_dump()))

    async def _aiter_model_stream(
        self,
        model_name: str,
        messages: list[BaseMessage],
        *,
        stop: list[str] | None,
        run_manager: AsyncCallbackManagerForLLMRun | None,
        **kwargs: Any,
    ) -> AsyncIterator[ChatGenerationChunk]:
        model = self._build_model(model_name)
        if type(model)._astream != BaseChatModel._astream:  # noqa: SLF001
            async for chunk in model._astream(messages, stop=stop, run_manager=run_manager, **kwargs):  # type: ignore[attr-defined]
                yield chunk
            return

        result = await self._ainvoke_model(model_name, messages, stop=stop, run_manager=run_manager, **kwargs)
        message = result.generations[0].message
        yield ChatGenerationChunk(message=AIMessageChunk(**message.model_dump()))

    def _build_model(self, model_name: str) -> BaseChatModel:
        logger.debug("Failover router selecting model '%s' for router '%s'", model_name, self.model)
        return create_chat_model(name=model_name)

    def _choose_model_name(self) -> str:
        state = self._load_state()
        cooldown_until = float(state.get("cooldown_until", 0))
        now = time.time()
        if cooldown_until > now:
            return self.fallback_model_name
        if cooldown_until:
            self._clear_cooldown()
        return self.primary_model_name

    def _should_fail_over(self, attempted_model_name: str, exc: BaseException) -> bool:
        if attempted_model_name != self.primary_model_name:
            return False
        status_code = self._extract_status_code(exc)
        if status_code in set(self.trigger_status_codes):
            return True
        exc_name = exc.__class__.__name__
        if exc_name in set(self.trigger_exception_names):
            return True
        detail = self._extract_error_detail(exc).lower()
        return any(pattern.lower() in detail for pattern in self.trigger_error_patterns)

    def _activate_fallback(self, exc: BaseException) -> str:
        cooldown_until = time.time() + self.cooldown_seconds
        state = self._load_state()
        state.update(
            {
                "active_model_name": self.fallback_model_name,
                "cooldown_until": cooldown_until,
                "last_primary_error": self._extract_error_detail(exc),
                "updated_at": time.time(),
            }
        )
        self._save_state(state)
        logger.warning(
            "Primary model '%s' entered cooldown for %ss after error; routing '%s' through fallback '%s'.",
            self.primary_model_name,
            self.cooldown_seconds,
            self.model,
            self.fallback_model_name,
        )
        return self.fallback_model_name

    def _clear_cooldown(self) -> None:
        state = self._load_state()
        if not state:
            return
        state.update(
            {
                "active_model_name": self.primary_model_name,
                "cooldown_until": 0,
                "updated_at": time.time(),
            }
        )
        self._save_state(state)
        logger.info(
            "Primary model '%s' cooldown expired; router '%s' switched back from fallback '%s'.",
            self.primary_model_name,
            self.model,
            self.fallback_model_name,
        )

    def _state_file_path(self) -> Path:
        raw_path = self.state_file or "model_failover_state.json"
        path = Path(raw_path).expanduser()
        if not path.is_absolute():
            path = get_paths().base_dir / path
        return path

    def _load_state(self) -> dict[str, Any]:
        path = self._state_file_path()
        if not path.exists():
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            logger.warning("Failed to read failover state file: %s", path, exc_info=True)
            return {}
        routers = payload.get("routers")
        if isinstance(routers, dict):
            state = routers.get(self.model)
            if isinstance(state, dict):
                return state
        return {}

    def _save_state(self, state: dict[str, Any]) -> None:
        path = self._state_file_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"routers": {}}
        if path.exists():
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                logger.warning("Failed to parse existing failover state file, replacing it: %s", path, exc_info=True)
                payload = {"routers": {}}
        routers = payload.get("routers")
        if not isinstance(routers, dict):
            routers = {}
        routers[self.model] = state
        payload["routers"] = routers
        temp_path = path.with_suffix(f"{path.suffix}.tmp")
        temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temp_path.replace(path)

    @staticmethod
    def _extract_status_code(exc: BaseException) -> int | None:
        for attr in ("status_code", "status"):
            value = getattr(exc, attr, None)
            if isinstance(value, int):
                return value
        response = getattr(exc, "response", None)
        status = getattr(response, "status_code", None)
        return status if isinstance(status, int) else None

    @staticmethod
    def _extract_error_detail(exc: BaseException) -> str:
        for attr in ("message", "detail"):
            value = getattr(exc, attr, None)
            if isinstance(value, str) and value.strip():
                return value
        body = getattr(exc, "body", None)
        if isinstance(body, dict):
            return json.dumps(body, ensure_ascii=False)
        response = getattr(exc, "response", None)
        text = getattr(response, "text", None)
        if isinstance(text, str) and text.strip():
            return text
        return str(exc)
