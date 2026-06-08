#!/usr/bin/env bash
set -euo pipefail

cd "/Users/winstonwei/Documents/Playground/deer-flow"
echo "=========================================="
echo "  CER Cowork Supervisor"
echo "=========================================="
echo "Opening Claude Code with the CER Authoring / Review launcher..."
echo
exec backend/.venv/bin/python scripts/launch_cer_cowork.py
