# RMF Findings Synthesis Agent

**Date:** 2026-04-19
**Phase:** RMF_AGENT_TEAM_HARNESS_CONFIG_MOUNTING_PHASE_A
**Node:** rmf_findings_synthesis
**Runtime Type:** report_synthesis_draft

---

## 1. Node Overview

Findings Synthesis drafts the final RMF review report after Human Gate decision. It synthesizes all findings into a coherent narrative and generates knowledge backflow candidates.

## 2. Responsibilities

1. **Findings Synthesis**
   - Synthesize all dimension findings into coherent narrative
   - Organize by severity and risk area
   - Include QA resolutions and human decisions
   - Draft actionable recommendations

2. **Report Generation**
   - Generate structured review report
   - Include executive summary, findings detail, and recommendations
   - Reference source documents and sections
   - Flag knowledge backflow candidates

3. **Knowledge Backflow Preparation**
   - Identify reusable knowledge from this review
   - Generate knowledge candidates for NocoDB
   - Format candidates for Knowledge Review Gate

## 3. Model Profile

| Parameter | Value |
|---|---|
| Profile | qa_synthesis |
| Model | MiniMax-M2.7 |
| Max Tokens | 24576 |
| Temperature | 0.4 |

## 4. Inputs

| Input | Source | Description |
|---|---|---|
| `dimension_findings` | All dimension agents | COMP, CORR, ADEQ, TRAC, CONS, ACPT, PMS |
| `human_gate_packet` | QA Gate | Pre-gate synthesis |
| `human_gate_decision` | Human Gate | Layer 3 decisions |
| `qa_gate_status` | QA Gate | Pass/conditional/fail/escalated |

## 5. Outputs

### Findings Synthesis Report

```json
{
  "node_id": "SYNTHESIS",
  "report_metadata": {
    "rmf_run_id": "string",
    "synthesis_version": "1.0",
    "synthesized_at": "ISO8601",
    "human_gate_decision": "approved|conditional_approval|rejected|deferred"
  },
  "executive_summary": "string",
  "findings_by_dimension": {
    "COMP": {"summary": "string", "critical_findings": [], "major_findings": [], "minor_findings": []},
    "CORR": {"summary": "string", "critical_findings": [], "major_findings": [], "minor_findings": []},
    "ADEQ": {"summary": "string", "critical_findings": [], "major_findings": [], "minor_findings": []},
    "TRAC": {"summary": "string", "critical_findings": [], "major_findings": [], "minor_findings": []},
    "CONS": {"summary": "string", "critical_findings": [], "major_findings": [], "minor_findings": []},
    "ACPT": {"summary": "string", "critical_findings": [], "major_findings": [], "minor_findings": []},
    "PMS": {"summary": "string", "critical_findings": [], "major_findings": [], "minor_findings": []}
  },
  "human_gate_decisions_incorporated": [
    {
      "decision_id": "HG-001",
      "decision_area": "string",
      "decision": "string",
      "rationale": "string"
    }
  ],
  "recommendations": [
    {
      "recommendation_id": "REC-001",
      "priority": "high|medium|low",
      "description": "string",
      "rationale": "string",
      "responsible_party": "string"
    }
  ],
  "knowledge_backflow_candidates": [
    {
      "candidate_id": "KC-001",
      "type": "TerminologyUnit|RuleUnit|FailurePattern|BoundaryCondition|ReviewHeuristic",
      "description": "string",
      "confidence": 0.85,
      "recommended_action": "approve|review|reject",
      "proposed_content": {}
    }
  ]
}
```

## 6. Artifact Outputs

```
artifacts/cer/{project_id}/rmf_review/{rmf_run_id}/
├── synthesis/
│   └── rmf_findings_synthesis.md    # Final synthesized report
└── knowledge_backflow/
    └── rmf_knowledge_candidates.json # Knowledge backflow candidates
```

## 7. Knowledge Backflow Types

| Type | Description | Example |
|---|---|---|
| TerminologyUnit | Standardized term definitions | "residual risk" definition |
| RuleUnit | Reusable review rules | "ACPT must verify benefit-risk evidence" |
| FailurePattern | Known failure patterns | "Software risk traceability gaps" |
| BoundaryCondition | Institution-specific conditions | "BSI requires explicit RPN criteria" |
| ReviewHeuristic | Domain heuristics | "High-severity risks always require Layer 3" |

## 8. Forbidden Actions

- **NO direct NocoDB publication** — all through Knowledge Review Gate
- **NO direct Obsidian writes** — all through Knowledge Review Gate
- **NO bypass of Knowledge Review Gate** — all candidates reviewed before publication

## 9. Handoff

- Output to Knowledge Review Gate (after human gate)
- Report saved to artifact path
- Knowledge candidates saved for review

---

*Findings Synthesis creates the final deliverable — a coherent report with knowledge backflow candidates*
