"""MCP Process Pool for reducing subprocess spawn overhead.

The standard mcp_tools.call_tool() spawns a new subprocess for every MCP call.
This module provides a connection pool that keeps MCP server processes alive
and reuses them across multiple requests, dramatically reducing latency for
frequently-called servers (nb-check, cer-kb, doc-proc).

Usage:
    from deerflow.runtime.cer_authoring.mcp_pool import get_mcp_pool, mcp_pool_call

    # Replace call_tool with pooled version (feature-flagged)
    result = mcp_pool_call("nb-check", "appraise_evidence", {...})

Requires CER_AUTHORING_ENABLE_MCP_POOL=1 to activate.
"""

from __future__ import annotations

import json
import logging
import os
import queue
import subprocess
import threading
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_MCP_POOL_ENABLED = os.getenv("CER_AUTHORING_ENABLE_MCP_POOL", "0") == "1"
_KIMI_PYTHON = os.getenv("CER_AUTHORING_KIMI_PYTHON", "python3")
_DEFAULT_POOL_SIZE = int(os.getenv("CER_AUTHORING_MCP_POOL_SIZE", "4"))
_DEFAULT_POOL_TIMEOUT = int(os.getenv("CER_AUTHORING_MCP_POOL_TIMEOUT", "90"))


class _PooledProcess:
    """A single pooled MCP server process with its own lock for exclusive use."""

    def __init__(self, server_file: Path) -> None:
        self.server_file = server_file
        self.proc: subprocess.Popen[str] | None = None
        self.lock = threading.Lock()
        self._request_id = 0
        self._start()

    def _start(self) -> None:
        """Start the subprocess and send initialize handshake."""
        self.proc = subprocess.Popen(
            [_KIMI_PYTHON, str(self.server_file)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,  # line buffered
        )
        # Send initialize handshake
        init_request = {
            "jsonrpc": "2.0",
            "id": 0,
            "method": "initialize",
            "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "deerflow-mcp-pool"}},
        }
        self._send_raw(init_request)
        # Read and discard initialize response
        self._readline(timeout=5.0)
        logger.debug("Pooled process started for %s (pid=%s)", self.server_file.name, self.proc.pid)

    def _send_raw(self, request: dict[str, Any]) -> None:
        """Send a JSON-RPC request to the subprocess."""
        if self.proc is None or self.proc.poll() is not None:
            raise RuntimeError("Pooled process is dead")
        line = json.dumps(request, ensure_ascii=False) + "\n"
        self.proc.stdin.write(line)  # type: ignore[union-attr]
        self.proc.stdin.flush()  # type: ignore[union-attr]

    def _readline(self, timeout: float) -> str:
        """Read one line from stdout with timeout."""
        import select

        if self.proc is None:
            raise RuntimeError("Pooled process is dead")

        ready, _, _ = select.select([self.proc.stdout], [], [], timeout)  # type: ignore[arg-type]
        if not ready:
            raise TimeoutError(f"Pooled process read timeout after {timeout}s")
        line = self.proc.stdout.readline()  # type: ignore[union-attr]
        if not line:
            raise RuntimeError("Pooled process stdout closed unexpectedly")
        return line.strip()

    def call(self, tool: str, arguments: dict[str, Any], timeout: float) -> dict[str, Any]:
        """Execute a single tool call via this pooled process.

        Must be called while holding self.lock for thread safety.
        """
        self._request_id += 1
        request = {
            "jsonrpc": "2.0",
            "id": self._request_id,
            "method": "tools/call",
            "params": {"name": tool, "arguments": arguments},
        }
        self._send_raw(request)
        response_line = self._readline(timeout=timeout)

        # Robust JSON parsing: handle stray non-JSON lines (server logs, empty lines)
        try:
            response = json.loads(response_line)
        except json.JSONDecodeError as exc:
            logger.warning("MCP server %s returned non-JSON response for %s: %r — treating as server error", self.server_file.name, tool, response_line[:200])
            raise RuntimeError(f"MCP server returned non-JSON response: {response_line[:200]}") from exc

        if response.get("error"):
            raise RuntimeError(f"MCP error: {response['error']}")

        result = response.get("result", {})
        content = result.get("content", [])
        if content and isinstance(content, list) and content:
            text = content[0].get("text", "")
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return {"status": "ok", "value": text}
        return result

    def is_alive(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def restart(self) -> None:
        """Kill and restart the subprocess."""
        if self.proc is not None:
            try:
                self.proc.kill()
                self.proc.wait(timeout=2)
            except Exception:
                pass
        self._start()

    def shutdown(self) -> None:
        """Gracefully terminate the subprocess."""
        if self.proc is not None and self.proc.poll() is None:
            try:
                self.proc.stdin.close()  # type: ignore[union-attr]
                self.proc.wait(timeout=3)
            except Exception:
                self.proc.kill()


class MCPProcessPool:
    """Thread-safe pool of reusable MCP server processes.

    Each server (e.g., nb-check) has its own pool of pre-started processes.
    Processes are acquired from a queue, used for one request, then returned.
    """

    def __init__(self, server_file: Path, size: int = _DEFAULT_POOL_SIZE) -> None:
        self.server_file = server_file
        self.size = size
        self._q: queue.Queue[_PooledProcess] = queue.Queue(maxsize=size)
        self._shutdown = False

        # Pre-start processes
        for i in range(size):
            try:
                proc = _PooledProcess(server_file)
                self._q.put(proc)
            except Exception as exc:
                logger.error("Failed to start pooled process %d/%d for %s: %s", i + 1, size, server_file, exc)

    def call(self, tool: str, arguments: dict[str, Any], timeout: float = _DEFAULT_POOL_TIMEOUT) -> dict[str, Any]:
        """Execute a tool call using a pooled process.

        Acquires a process from the pool, executes the call, and returns
        the process to the pool. If the process dies during the call,
        it is restarted transparently.
        """
        if self._shutdown:
            raise RuntimeError("Pool is shutdown")

        proc = self._q.get(timeout=timeout + 5)
        try:
            with proc.lock:
                if not proc.is_alive():
                    logger.warning("Pooled process died, restarting...")
                    proc.restart()
                return proc.call(tool, arguments, timeout)
        except (TimeoutError, RuntimeError) as exc:
            # Process-level errors: restart may help
            logger.warning("Pooled call failed for %s: %s — restarting process", tool, exc)
            try:
                proc.restart()
            except Exception:
                pass
            raise
        except json.JSONDecodeError as exc:
            # JSON parse errors are server response issues; restarting the process won't help.
            # Just re-raise so the caller can fall back to subprocess.
            logger.warning("Pooled call JSON parse failed for %s: %s — not restarting (server response issue)", tool, exc)
            raise
        finally:
            if not self._shutdown:
                self._q.put(proc)

    def shutdown(self) -> None:
        """Shutdown all pooled processes."""
        self._shutdown = True
        while not self._q.empty():
            try:
                proc = self._q.get_nowait()
                proc.shutdown()
            except Exception:
                pass


# ── Global pool registry ──
_pools: dict[str, MCPProcessPool] = {}
_pools_lock = threading.Lock()


def get_mcp_pool(server: str, server_file: Path | None = None) -> MCPProcessPool:
    """Get or create the process pool for a given MCP server."""
    with _pools_lock:
        if server not in _pools:
            if server_file is None:
                from deerflow.runtime.cer_authoring import mcp_tools

                server_file = mcp_tools._SERVER_FILES.get(server)
            if server_file is None or not server_file.exists():
                raise ValueError(f"MCP server file not found for: {server}")
            _pools[server] = MCPProcessPool(server_file)
        return _pools[server]


def mcp_pool_call(server: str, tool: str, arguments: dict[str, Any] | None = None, timeout: int | None = None) -> dict[str, Any]:
    """Drop-in replacement for mcp_tools.call_tool() that uses the process pool.

    Falls back to standard subprocess if pool is unavailable or fails.
    """
    if not _MCP_POOL_ENABLED:
        from deerflow.runtime.cer_authoring import mcp_tools
        return mcp_tools.call_tool(server, tool, arguments, timeout)

    try:
        pool = get_mcp_pool(server)
        return pool.call(tool, arguments or {}, timeout=timeout or _DEFAULT_POOL_TIMEOUT)
    except Exception as exc:
        logger.warning("MCP pool call failed for %s/%s: %s — falling back to subprocess", server, tool, exc)
        from deerflow.runtime.cer_authoring import mcp_tools
        return mcp_tools.call_tool(server, tool, arguments, timeout)
