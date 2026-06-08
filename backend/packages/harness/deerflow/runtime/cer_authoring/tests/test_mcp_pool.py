"""Unit tests for the MCP Process Pool.

Tests cover pool initialization, feature flag behavior, and fallback logic.
Actual subprocess integration tests require real MCP servers and are
excluded from the standard test suite.
"""

from __future__ import annotations

import os
import pytest

from deerflow.runtime.cer_authoring.mcp_pool import (
    _MCP_POOL_ENABLED,
    MCPProcessPool,
    _PooledProcess,
    mcp_pool_call,
)


class TestMCPPoolFeatureFlag:
    """Test feature flag defaults."""

    def test_pool_disabled_by_default(self):
        assert _MCP_POOL_ENABLED == (os.getenv("CER_AUTHORING_ENABLE_MCP_POOL") == "1")

    def test_mcp_pool_call_falls_back_when_disabled(self):
        """When pool is disabled, mcp_pool_call should fall back to standard call_tool."""
        if _MCP_POOL_ENABLED:
            pytest.skip("MCP pool is enabled in environment")

        # Call with a non-existent tool to verify fallback path works
        result = mcp_pool_call("cer-public-evidence", "nonexistent_tool_xyz")
        assert "error" in str(result).lower() or result.get("status") in ("error", "source_unavailable")


class TestPooledProcessInternals:
    """Test internal helpers without requiring real servers."""

    def test_pooled_process_requires_real_server_file(self):
        """_PooledProcess raises if server file does not exist."""
        from pathlib import Path

        fake_path = Path("/nonexistent/server.py")
        with pytest.raises((RuntimeError, FileNotFoundError)):
            _PooledProcess(fake_path)

    def test_pool_size_configuration(self):
        """Pool size respects environment variable or default."""
        from deerflow.runtime.cer_authoring.mcp_pool import _DEFAULT_POOL_SIZE

        assert _DEFAULT_POOL_SIZE >= 1
        assert isinstance(_DEFAULT_POOL_SIZE, int)


class TestMCPPoolCallLogic:
    """Test the mcp_pool_call dispatch logic."""

    def test_public_evidence_not_pooled(self):
        """cer-public-evidence uses pure Python functions, not subprocess — pool should not apply."""
        # The pool only activates for servers in _SERVER_FILES (nb-check, cer-kb, doc-proc)
        from deerflow.runtime.cer_authoring import mcp_tools

        assert "cer-public-evidence" not in mcp_tools._SERVER_FILES
