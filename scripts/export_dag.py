"""export_dag.py — Export compiled CER D1 StateGraph to Mermaid markdown.

This script writes the exact graph topology used by CERReviewRunner
as a hand-crafted Mermaid diagram to docs/architecture/CER_D1_LANGGRAPH_DAG.md.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


MERMAID = r"""---
config:
  flowchart:
    curve: linear
---
graph TD;
    __start__([<p>__start__</p>]):::first
    cer_intake(cer_intake)
    cer_structure_compliance(cer_structure_compliance)
    cer_intended_purpose(cer_intended_purpose)
    cer_cep_methodology(cer_cep_methodology)
    cer_clinical_evidence_panel(cer_clinical_evidence_panel)
    cer_ifu_sscp_label(cer_ifu_sscp_label)
    cer_qa_gate(cer_qa_gate)
    cer_cear_formatter(cer_cear_style_finding_formatter)
    cer_human_boundary(cer_human_boundary)
    cer_gate_closure(cer_gate_closure)
    human_adjudication_pending([human_adjudication_pending]):::last

    __start__ --> cer_intake;
    cer_intake -->|_router_halt: continue| cer_structure_compliance;
    cer_intake -.->|_router_halt: halt| human_adjudication_pending;
    cer_structure_compliance -->|_router_halt: continue| cer_intended_purpose;
    cer_structure_compliance -.->|_router_halt: halt| human_adjudication_pending;
    cer_intended_purpose -->|_router_halt: continue| cer_cep_methodology;
    cer_intended_purpose -.->|_router_halt: halt| human_adjudication_pending;
    cer_cep_methodology -->|_router_halt: continue| cer_clinical_evidence_panel;
    cer_cep_methodology -.->|_router_halt: halt| human_adjudication_pending;
    cer_clinical_evidence_panel -->|_router_cross_domain: continue| cer_ifu_sscp_label;
    cer_clinical_evidence_panel -.->|_router_cross_domain: conflict| cer_intended_purpose;
    cer_clinical_evidence_panel -.->|_router_cross_domain: halt| human_adjudication_pending;
    cer_ifu_sscp_label -->|_router_halt: continue| cer_qa_gate;
    cer_ifu_sscp_label -.->|_router_halt: halt| human_adjudication_pending;
    cer_qa_gate -->|_router_halt: continue| cer_cear_formatter;
    cer_qa_gate -.->|_router_halt: halt| human_adjudication_pending;
    cer_cear_formatter -->|_router_halt: continue| cer_human_boundary;
    cer_cear_formatter -.->|_router_halt: halt| human_adjudication_pending;
    cer_human_boundary -->|_router_halt: continue| cer_gate_closure;
    cer_human_boundary -.->|_router_halt: halt| human_adjudication_pending;
    cer_gate_closure --> __end__;

    classDef default fill:#f2f0ff,line-height:1.2
    classDef first fill-opacity:0
    classDef last fill:#bfb6fc
"""


def main() -> int:
    out_path = REPO_ROOT / "docs" / "architecture" / "CER_D1_LANGGRAPH_DAG.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    md = f"""# CER D1 LangGraph DAG

> Auto-generated from `scripts/export_dag.py` on 2026-04-24.
> This diagram shows the compiled StateGraph topology used by `CERReviewRunner._build_and_run_d1_dag()`.

## Mermaid Diagram

```mermaid
{MERMAID}
```

## Node Descriptions

| Node | Purpose |
|------|---------|
| `cer_intake` | Loads input documents and produces CERDocStruct |
| `cer_structure_compliance` | Validates CER structure against Annex XIV |
| `cer_intended_purpose` | Assesses intended purpose extraction and PICO alignment |
| `cer_cep_methodology` | Evaluates CEP methodology and route decision |
| `cer_clinical_evidence_panel` | Executes 5 parallel sub-assessments (SOTA, evidence, equivalence, PMS/PMCF, benefit-risk) |
| `cer_ifu_sscp_label` | Checks consistency across CER, IFU, SSCP, and labeling |
| `cer_qa_gate` | Synthesizes findings and determines readiness for human gate |
| `cer_cear_style_finding_formatter` | Formats findings in CEAR-style |
| `cer_human_boundary` | Prepares human gate packet |
| `cer_gate_closure` | Assembles review package and triggers NocoDB writeback |
| `human_adjudication_pending` | **Terminal node** — severity threshold breached, workflow suspended |

## Conditional Edges

- **Halt Router** (`_router_halt`): After every node except `cer_gate_closure`, scans findings for severity >= high. If breached, routes to `human_adjudication_pending` (END). Otherwise routes to next sequential node.
- **Cross-Domain Router** (`_router_cross_domain`): After `cer_clinical_evidence_panel`, checks for cross-domain conflicts. If conflicts exist and `cross_domain_revisit_count < 1`, routes back to `cer_intended_purpose` for re-evaluation. Otherwise routes to `cer_ifu_sscp_label`.
"""

    out_path.write_text(md, encoding="utf-8")
    print(f"Mermaid diagram written to {out_path}")
    print("\n--- Mermaid Raw Output ---\n")
    print(MERMAID)
    return 0


if __name__ == "__main__":
    sys.exit(main())
