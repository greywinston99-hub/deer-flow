#!/usr/bin/env python3
"""CER quality auto-scoring from artifact directory."""
import json, sys
from pathlib import Path

root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()

def _exists(f): return (root / f).exists()
def _size(f):
    p = root / f
    return p.stat().st_size if p.exists() else 0
def _words(f):
    p = root / f
    return len(p.read_text().split()) if p.exists() else 0

scores = {}

# P0: Must have
for f in ["CER_draft.docx", "prisma_flow_diagram.md", "final_gate_closure_report.json"]:
    scores[f"exists:{f}"] = 10 if _exists(f) else 0

# CER body
wc = _words("CER_draft.md")
scores["cer_words"] = min(10, wc // 100)

# Gate
try:
    gate = json.loads((root / "final_gate_closure_report.json").read_text())
    scores["gate_passed"] = 10 if gate.get("decision") == "PASS_TO_DRAFT_DOCX" else (5 if gate.get("decision") else 3)
except Exception:
    scores["gate_passed"] = 0

# Evidence
try:
    funnel = json.loads((root / "evidence_count_funnel.json").read_text())
    ev = funnel.get("evidence_registry", 0) if isinstance(funnel, dict) else 0
    scores["evidence_count"] = min(10, ev // 5)
except Exception:
    scores["evidence_count"] = 0

# PRISMA
prisma_text = (root / "prisma_flow_diagram.md").read_text() if _exists("prisma_flow_diagram.md") else ""
scores["prisma_content"] = 10 if "mermaid" in prisma_text.lower() else 0

# Total
total = sum(scores.values())
max_score = 60
pct = round(total / max_score * 100)

print(f" CER Quality Score: {total}/{max_score} ({pct}%)")
print(f"{'─'*40}")
for k, v in scores.items():
    bar = "█" * (v // 2) + "░" * (5 - v // 2)
    print(f"  {k:<30} {v:>2}/10 {bar}")
print(f"{'─'*40}")
print(f"  {'TOTAL':<30} {total:>2}/{max_score}")
