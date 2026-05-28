"""Stdio compatibility bridge for lightweight MCP servers.

Some legacy MCP servers reply to JSON-RPC notifications with ``id: null``.
The official MCP client treats those lines as invalid responses and logs parse
errors. This bridge sits between DeerFlow and such servers, forwarding stdin to
the child process and filtering invalid notification responses from stdout.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import threading
from typing import TextIO


def _is_invalid_notification_response(line: str) -> bool:
    try:
        payload = json.loads(line)
    except json.JSONDecodeError:
        return False
    if not isinstance(payload, dict):
        return False
    if payload.get("jsonrpc") != "2.0":
        return False
    if payload.get("id") is not None:
        return False
    return "result" in payload or "error" in payload


def _copy_input(source: TextIO, target: TextIO) -> None:
    try:
        for line in source:
            target.write(line)
            target.flush()
    finally:
        try:
            target.close()
        except Exception:
            pass


def _copy_output(source: TextIO, target: TextIO, *, filter_invalid: bool) -> None:
    for line in source:
        if filter_invalid and _is_invalid_notification_response(line):
            continue
        target.write(line)
        target.flush()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Filter invalid MCP stdio notification responses.")
    parser.add_argument("command", nargs=argparse.REMAINDER, help="Child MCP command to run")
    args = parser.parse_args(argv)
    if not args.command:
        print("stdio_compat_bridge requires a child command", file=sys.stderr)
        return 2

    child = subprocess.Popen(
        args.command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    assert child.stdin is not None
    assert child.stdout is not None
    assert child.stderr is not None

    threads = [
        threading.Thread(target=_copy_input, args=(sys.stdin, child.stdin), daemon=True),
        threading.Thread(target=_copy_output, args=(child.stdout, sys.stdout), kwargs={"filter_invalid": True}, daemon=True),
        threading.Thread(target=_copy_output, args=(child.stderr, sys.stderr), kwargs={"filter_invalid": False}, daemon=True),
    ]
    for thread in threads:
        thread.start()
    return child.wait()


if __name__ == "__main__":
    raise SystemExit(main())
