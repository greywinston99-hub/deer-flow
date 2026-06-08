#!/usr/bin/env bash
# delegate.sh — Claude Code -> DeerFlow supervised delegation wrapper.
set -euo pipefail

DEERFLOW_ROOT="${DEERFLOW_ROOT:-/Users/winstonwei/Documents/Playground/deer-flow}"
PYTHON="${DEERFLOW_PYTHON:-${DEERFLOW_ROOT}/backend/.venv/bin/python}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

exec "$PYTHON" "$SCRIPT_DIR/delegate.py" "$@"
