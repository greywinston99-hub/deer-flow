"""Shared LLM client factory for ALL DeerFlow modules.

Replaces scattered `Anthropic()` calls with a single, correctly-configured
client that works with the local router (127.0.0.1:18765).

Problem: _patch_httpx_lru only patches langchain_anthropic, not raw Anthropic SDK.
The local router returns gzip-compressed responses that httpx can't decompress
unless Accept-Encoding: identity is set.

Usage:
    from _v3_1_llm_client import get_llm_client
    client = get_llm_client(timeout=600.0)
    response = client.messages.create(model="kimi-k2.6", ...)
"""

from __future__ import annotations
import threading
import httpx
from anthropic import Anthropic

_client_cache: dict[str, Anthropic] = {}
_lock = threading.Lock()


def get_llm_client(
    model: str = "kimi-k2.6",
    timeout: float = 600.0,
    base_url: str = "http://127.0.0.1:18765/anthropic",
    api_key: str = "router-local",
) -> Anthropic:
    """Get or create a shared Anthropic client configured for local router.

    Uses Accept-Encoding: identity to prevent gzip zlib errors from the
    local nginx router. The httpx connection pool is disabled to avoid
    stale connection reuse.

    Clients are cached by base_url to allow multiple endpoints.
    """
    cache_key = f"{base_url}:{api_key}:{timeout}"
    with _lock:
        if cache_key not in _client_cache:
            _client_cache[cache_key] = Anthropic(
                base_url=base_url,
                api_key=api_key,
                timeout=httpx.Timeout(timeout),
                http_client=httpx.Client(
                    headers={"Accept-Encoding": "identity"},
                    timeout=httpx.Timeout(timeout),
                    limits=httpx.Limits(max_keepalive_connections=0, max_connections=10),
                ),
            )
    return _client_cache[cache_key]
