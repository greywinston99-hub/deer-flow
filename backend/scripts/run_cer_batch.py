"""Batch CER runner — run multiple projects sequentially."""
import subprocess, sys, json, time
from pathlib import Path

PROJECTS = [
    {
        "id": "EONHAR_PLASMA_003",
        "input": "/Users/winstonwei/CER-RAG/升级 CCD-3 个项目文件/CER_PILOT_STANDARD_01启灏/01_AUTHORING_INPUT_ALLOWED",
        "output": "/Users/winstonwei/CER-RAG/升级 CCD-3 个项目文件/CER_PILOT_STANDARD_01启灏/02_CER_OUTPUT",
        "keywords": "等离子,射频,手术电极,plasma,radiofrequency,electrode,arthroscopy",
    },
    {
        "id": "MEDOS_STABILIZER_003",
        "input": "/Users/winstonwei/CER-RAG/升级 CCD-3 个项目文件/CER_PILOT_STANDARD_02米道斯/01_AUTHORING_INPUT_ALLOWED",
        "output": "/Users/winstonwei/CER-RAG/升级 CCD-3 个项目文件/CER_PILOT_STANDARD_02米道斯/02_CER_OUTPUT",
        "keywords": "心脏固定器,cardiac,stabilizer,tissue,coronary,bypass",
    },
]

HARNESS = Path("/Users/winstonwei/Documents/Playground/deer-flow/backend/packages/harness")
PYTHON = "/Users/winstonwei/Documents/Playground/deer-flow/.venv/bin/python3"
SCRIPT = "../../scripts/run_cer_authoring.py"

results = []
for proj in PROJECTS:
    print(f"\n{'='*60}")
    print(f"Starting: {proj['id']}")
    start = time.time()
    ret = subprocess.run(
        [PYTHON, SCRIPT,
         "--project-id", proj["id"],
         "--input-root", proj["input"],
         "--artifact-root", proj["output"],
         "--target-keywords", proj["keywords"],
         "--strict-v7", "--json", "--auto-confirm"],
        cwd=str(HARNESS),
        env={**__import__("os").environ,
             "CER_AUTHORING_STRICT_V7": "1",
             "CER_AUTHORING_ENABLE_LLM_AGENTS": "1",
             "CER_AUTHORING_ENABLE_EVENT_BUS": "0"},
    )
    elapsed = time.time() - start
    results.append({"project": proj["id"], "exit": ret.returncode, "elapsed": f"{elapsed:.0f}s"})
    print(f"Completed: {proj['id']} (exit {ret.returncode}, {elapsed:.0f}s)")

print(f"\n{'='*60}")
print("BATCH SUMMARY")
for r in results:
    icon = "✅" if r["exit"] == 0 else "⚠️"
    print(f"  {icon} {r['project']}: exit={r['exit']}, {r['elapsed']}")
