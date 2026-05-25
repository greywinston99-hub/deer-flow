"""Minimal read_file probe: test that a subagent can read the CER fixture via the read_file tool.

Uses the same SubagentExecutor / Minimax model / sandbox as the review workflow.
Timeout: 60s. Max tokens: 256.
"""
import sys, time, json, asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "harness"))

from deerflow.subagents.executor import SubagentExecutor
from deerflow.subagents.config import SubagentConfig
from deerflow.subagents.registry import get_subagent_config

CER_PATH = Path(__file__).resolve().parents[3] / "examples" / "cer_review" / "production_smoke" / "CER_comprehensive_low_risk.txt"
assert CER_PATH.exists(), f"CER file not found: {CER_PATH}"

# Use the same config as cer-intake-reviewer
config = get_subagent_config("cer-intake-reviewer")
assert config is not None

# Override for probe
config = SubagentConfig(
    name="read-file-probe",
    description="Probe agent to test read_file tool",
    system_prompt="""You are a probe agent. Use the read_file tool to read the file at the given path.
    Return ONLY this exact JSON (no thinking, no markdown):
    {"file_read": true, "device_name": "<extracted from file>", "section_count_estimate": <number>, "first_section_title": "<title>"}

    If read_file fails, return: {"file_read": false, "error": "<reason>"}""",
    tools=["read_file", "ls"],
    disallowed_tools=["task", "write_file", "str_replace"],
    model="inherit",
    max_turns=3,
    timeout_seconds=60,
)

executor = SubagentExecutor(config, parent_model="minimax-m2.7")

task = f"""Read the CER fixture file at this path: {CER_PATH}
Extract: device_name, section_count_estimate, first_section_title.
Return JSON only."""

print("Running read_file probe...", flush=True)
start = time.time()

try:
    result = asyncio.run(executor.execute(task))
    elapsed = time.time() - start
    print(f"Status: {result.status.value}")
    print(f"Duration: {elapsed:.1f}s")
    print(f"Messages: {len(result.ai_messages or [])}")

    if result.ai_messages:
        last = result.ai_messages[-1]
        content = last.content if hasattr(last, 'content') else str(last)
        print(f"\nAgent response:\n{content[:500]}")

    if result.error:
        print(f"Error: {result.error}")

    print(f"\nSchema validation: {result.schema_validation}")

except Exception as e:
    elapsed = time.time() - start
    print(f"FAILED after {elapsed:.1f}s: {e}")
