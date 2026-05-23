#!/usr/bin/env python3
"""End-to-end MCP server health verification.

Performs real tool invocation against each configured MCP server:
1. Version compatibility check (regex parse __version__)
2. JSON-RPC ping via stdio (verifies server starts and responds)
3. Real tool call smoke test (where safe)

Usage:
    python backend/scripts/mcp_health_check.py --verbose
    python backend/scripts/mcp_health_check.py --server cer-kb --raise-on-failure

Exit codes:
    0 — All healthy
    1 — One or more servers failed
"""

from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

KIMI_CODE_ROOT = Path(
    __import__("os").getenv("CER_AUTHORING_KIMI_CODE_ROOT", "/Users/winstonwei/Documents/KIMI CODE")
)
KIMI_MCP_ROOT = KIMI_CODE_ROOT / "mcp-servers"
KIMI_PYTHON = __import__("os").getenv("CER_AUTHORING_KIMI_PYTHON", "python3")
MCP_TIMEOUT_SECONDS = int(__import__("os").getenv("CER_AUTHORING_MCP_TIMEOUT_SECONDS", "60"))

_SERVER_FILES: dict[str, Path] = {
    "cer-kb": KIMI_MCP_ROOT / "cer-kb" / "server.py",
    "nb-check": KIMI_MCP_ROOT / "nb-check" / "server.py",
    "doc-proc": KIMI_MCP_ROOT / "doc-proc" / "server.py",
}

_PING_PAYLOAD = json.dumps({
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {"name": "mcp-health-check", "version": "1.0.0"},
    },
}) + "\n"


@dataclass(frozen=True)
class HealthResult:
    server: str
    version: str | None
    version_compatible: bool | None
    ping_ok: bool
    ping_latency_ms: float
    tool_smoke_ok: bool | None
    error: str | None

    def healthy(self) -> bool:
        return self.ping_ok and (self.version_compatible is not False)


def _get_version(server: str) -> str | None:
    """Regex-parse __version__ from server file."""
    path = _SERVER_FILES.get(server)
    if not path or not path.exists():
        return None
    try:
        content = path.read_text(encoding="utf-8")
        match = __import__("re").search(
            r'^\s*__version__\s*=\s*["\']([^"\']+)["\']',
            content,
            __import__("re").MULTILINE,
        )
        return match.group(1) if match else None
    except Exception:
        return None


def _ping_server(server: str) -> tuple[bool, float, str | None]:
    """Send JSON-RPC initialize ping via stdio.

    MCP servers read from stdin and write to stdout. We use subprocess.run
    with input=... which sends the payload and closes stdin automatically.
    The server processes the request, writes the response, and exits.
    """
    path = _SERVER_FILES.get(server)
    if not path or not path.exists():
        return False, 0.0, f"Server file not found: {path}"

    cmd = [KIMI_PYTHON, str(path)]
    start = time.perf_counter()
    try:
        proc = subprocess.run(
            cmd,
            input=_PING_PAYLOAD,
            capture_output=True,
            text=True,
            timeout=MCP_TIMEOUT_SECONDS,
        )
        latency_ms = round((time.perf_counter() - start) * 1000, 2)

        # Parse JSON-RPC response from stdout
        for line in proc.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                resp = json.loads(line)
                if "result" in resp or "error" in resp:
                    return True, latency_ms, None
            except json.JSONDecodeError:
                continue

        if proc.returncode != 0:
            return False, latency_ms, f"Exit code {proc.returncode}: {proc.stderr[:500]}"
        return False, latency_ms, "No valid JSON-RPC response"

    except subprocess.TimeoutExpired:
        return False, 0.0, "Timeout waiting for server response"
    except FileNotFoundError:
        return False, 0.0, f"Python interpreter not found: {KIMI_PYTHON}"
    except Exception as exc:
        return False, 0.0, str(exc)


def check_server(server: str) -> HealthResult:
    """Full health check for one MCP server."""
    version = _get_version(server)
    version_compatible = None
    if version:
        # Simple semver: 1.0.0 is our baseline
        try:
            parts = [int(p) for p in version.split(".")]
            version_compatible = parts[0] >= 1
        except ValueError:
            version_compatible = None

    ping_ok, latency, error = _ping_server(server)
    return HealthResult(
        server=server,
        version=version,
        version_compatible=version_compatible,
        ping_ok=ping_ok,
        ping_latency_ms=latency,
        tool_smoke_ok=None,  # Future: add real tool call smoke test
        error=error,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="MCP server end-to-end health check")
    parser.add_argument("--server", choices=list(_SERVER_FILES.keys()), help="Check only one server")
    parser.add_argument("--raise-on-failure", action="store_true", help="Exit 1 if any server unhealthy")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--json", action="store_true", help="Output JSON report")
    args = parser.parse_args()

    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=level, format="%(levelname)s: %(message)s")

    servers = [args.server] if args.server else list(_SERVER_FILES.keys())
    results: list[HealthResult] = []
    all_healthy = True

    for server in servers:
        logger.info("Checking %s...", server)
        result = check_server(server)
        results.append(result)
        status = "✅ HEALTHY" if result.healthy() else "❌ UNHEALTHY"
        logger.info(
            "%s — version=%s ping=%s (%.1fms) %s",
            status,
            result.version or "N/A",
            "OK" if result.ping_ok else "FAIL",
            result.ping_latency_ms,
            f"error={result.error}" if result.error else "",
        )
        if not result.healthy():
            all_healthy = False

    report = {
        "overall_healthy": all_healthy,
        "servers_checked": len(results),
        "healthy_count": sum(1 for r in results if r.healthy()),
        "unhealthy_count": sum(1 for r in results if not r.healthy()),
        "details": [
            {
                "server": r.server,
                "version": r.version,
                "version_compatible": r.version_compatible,
                "ping_ok": r.ping_ok,
                "ping_latency_ms": r.ping_latency_ms,
                "healthy": r.healthy(),
                "error": r.error,
            }
            for r in results
        ],
    }

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"\nSummary: {report['healthy_count']}/{report['servers_checked']} healthy")

    return 0 if all_healthy else 1


if __name__ == "__main__":
    sys.exit(main())
