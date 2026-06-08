"""Config tests for CER authoring MCP integration."""

from __future__ import annotations

from deerflow.config.extensions_config import ExtensionsConfig, McpServerConfig
from deerflow.mcp.client import build_servers_config
from deerflow.tools.builtins.tool_search import DeferredToolRegistry


def test_authoring_mcp_servers_build_params():
    extensions = ExtensionsConfig(
        mcp_servers={
            "cer-kb": McpServerConfig(enabled=True, type="stdio", command="python3", args=["bridge.py", "python3", "cer-kb/server.py"]),
            "nb-check": McpServerConfig(enabled=True, type="stdio", command="python3", args=["bridge.py", "python3", "nb-check/server.py"]),
            "doc-proc": McpServerConfig(enabled=True, type="stdio", command="python3", args=["bridge.py", "python3", "doc-proc/server.py"]),
            "cer-public-evidence": McpServerConfig(enabled=True, type="stdio", command="python3", args=["cer_public_evidence_server.py"]),
        },
        skills={},
    )

    built = build_servers_config(extensions)

    assert set(built) == {"cer-kb", "nb-check", "doc-proc", "cer-public-evidence"}
    assert built["cer-public-evidence"]["transport"] == "stdio"


def test_tool_search_can_discover_prefixed_cer_authoring_tools():
    registry = DeferredToolRegistry()

    from langchain_core.tools import tool as langchain_tool

    @langchain_tool("cer-kb_search_cer_sections")
    def search_cer_sections(query: str) -> str:
        """Search CER sections."""
        return query

    @langchain_tool("cer-public-evidence_embase_search")
    def embase_search(query: str) -> str:
        """Search Embase."""
        return query

    @langchain_tool("cer-public-evidence_cochrane_search")
    def cochrane_search(query: str) -> str:
        """Search Cochrane."""
        return query

    @langchain_tool("cer-public-evidence_euctr_search")
    def euctr_search(query: str) -> str:
        """Search EUCTR."""
        return query

    @langchain_tool("cer-public-evidence_eudamed_vigilance_search")
    def eudamed_vigilance_search(query: str) -> str:
        """Search EUDAMED vigilance."""
        return query

    registry.register(search_cer_sections)
    registry.register(embase_search)
    registry.register(cochrane_search)
    registry.register(euctr_search)
    registry.register(eudamed_vigilance_search)

    results = registry.search("select:cer-kb_search_cer_sections")

    assert len(results) == 1
    assert results[0].name == "cer-kb_search_cer_sections"
    assert registry.search("select:cer-public-evidence_embase_search")[0].name == "cer-public-evidence_embase_search"
    assert registry.search("select:cer-public-evidence_cochrane_search")[0].name == "cer-public-evidence_cochrane_search"
    assert registry.search("select:cer-public-evidence_euctr_search")[0].name == "cer-public-evidence_euctr_search"
    assert registry.search("select:cer-public-evidence_eudamed_vigilance_search")[0].name == "cer-public-evidence_eudamed_vigilance_search"
