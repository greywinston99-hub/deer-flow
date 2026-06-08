#!/usr/bin/env bash
set -euo pipefail

cd "/Users/winstonwei/Documents/Playground/deer-flow"

clear || true
echo "=========================================="
echo "  CER Cowork Supervisor"
echo "=========================================="
echo
echo "This launcher opens Claude Code/Cowork and loads the unified CER workflow."
echo
echo "First question in Claude:"
echo "  Please choose: CER Authoring or CER Review?"
echo
echo "Authoring path:"
echo "  Claude Code supervisor -> DeerFlow strict v7 baseline -> Claude repair loop"
echo
echo "Review path:"
echo "  Claude Code supervisor -> DeerFlow CER review workflow"
echo
echo "Opening now..."
echo

exec backend/.venv/bin/python scripts/launch_cer_cowork.py
