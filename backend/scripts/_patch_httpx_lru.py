"""Monkey-patch langchain_anthropic httpx client to fix local router zlib errors.

Root cause: langchain_anthropic's cached httpx client reuses connections to the
local nginx router. When nginx closes the connection, httpx tries to reuse the
stale connection and gets zlib decompression errors.

The module-level import in chat_models.py caches a reference to the original
_get_default_httpx_client. We must patch BOTH _client_utils AND chat_models.
"""
from __future__ import annotations

import httpx


def _make_client(*, base_url: str | None = None, timeout=None, **_):
    """Create a fresh httpx client with connection pooling disabled."""
    kwargs: dict = {
        "base_url": base_url or "https://api.anthropic.com",
        "timeout": timeout if timeout is not None else httpx.Timeout(600.0),
        "follow_redirects": True,
        "limits": httpx.Limits(max_keepalive_connections=0, max_connections=10),
        "headers": {"Connection": "close", "Accept-Encoding": "identity"},
    }
    return httpx.Client(**kwargs)


def _make_async_client(*, base_url: str | None = None, timeout=None, **_):
    """Create a fresh async httpx client with connection pooling disabled."""
    kwargs: dict = {
        "base_url": base_url or "https://api.anthropic.com",
        "timeout": timeout if timeout is not None else httpx.Timeout(600.0),
        "follow_redirects": True,
        "limits": httpx.Limits(max_keepalive_connections=0, max_connections=10),
        "headers": {"Connection": "close", "Accept-Encoding": "identity"},
    }
    return httpx.AsyncClient(**kwargs)


def apply() -> None:
    """Replace httpx client factory in BOTH _client_utils AND chat_models."""
    # 1. Patch _client_utils (used by newer code paths)
    import langchain_anthropic._client_utils as utils_mod
    if hasattr(utils_mod._get_default_httpx_client, "cache_clear"):
        utils_mod._get_default_httpx_client.cache_clear()
    if hasattr(utils_mod._get_default_async_httpx_client, "cache_clear"):
        utils_mod._get_default_async_httpx_client.cache_clear()
    utils_mod._get_default_httpx_client = _make_client  # type: ignore[assignment]
    utils_mod._get_default_async_httpx_client = _make_async_client  # type: ignore[assignment]

    # 2. Patch chat_models module-level imports (critical fix)
    import langchain_anthropic.chat_models as cm
    cm._get_default_httpx_client = _make_client  # type: ignore[attr-defined]
    cm._get_default_async_httpx_client = _make_async_client  # type: ignore[attr-defined]


apply()
