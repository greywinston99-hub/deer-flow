# RMF QA Human Gate Packet Agent

**Date:** 2026-04-19
**Phase:** RMF_AGENT_TEAM_HARNESS_CONFIG_MOUNTING_PHASE_A
**Node:** rmf_qa_human_gate_packet
**Runtime Type:** live_llm_plus_deterministic_validation

---

## 1. Node Overview

QA Gate Agent synthesizes all dimension findings into a Human Gate Packet and performs Layer 1/2 technical arbitration. **QA is NOT a Layer 3 裁决者 (arbitrator/judge).**

## 2. Responsibilities

### Layer 1/2 Technical Arbitration (Allowed)

| Arbitration Type | Description |
|---|---|
| Source-backed beats unsupported | Structured extraction evidence beats LLM-only observation |
| Deterministic beats LLM | Rule engine output beats free LLM observation |
| High-confidence beats low-confidence | Source-backed high-confidence beats low-confidence unsupported |
| Unresolved conflicts → Human Gate | If cannot resolve, escalate to Human Gate |

### Human Gate Packet Synthesis

Generate a structured packet for human decision-making:

```
Section A: Executive Summary
Section B: Dimension Findings Summary (COMP, CORR, ADEQ, TRAC, CONS, ACPT, PMS)
Section C: Identified Conflicts and QA Resolutions
Section D: High-Risk Items Requiring Human Attention
Section E: PMS Lane Findings (if triggered)
Section F: Recommended Human Decisions
```

## 3. Model Profile

| Parameter | Value |
|---|---|
| Profile | qa_synthesis |
| Model | MiniMax-M2.7 |
| Max Tokens | 16384 |
| Temperature | 0.2 |

## 4. Inputs

| Input | Source | Description |
|---|---|---|
| `dimension_findings` | All dimension agents | COMP, CORR, ADEQ, TRAC, CONS, ACPT, PMS findings |
| `l1_rule_engine_results` | L1 Rule Engine | Hard-fail results |
| `shared_state` | Orchestrator | Dimension status aggregation |

## 5. QA Arbitration Rules

### Resolved Automatically (No Human Needed)

| Condition | Resolution |
|---|---|
| L1 hard fail + dimension finding same issue | Accept dimension finding |
| Source-backed finding contradicts unsupported | Accept source-backed |
| Deterministic rule + LLM finding conflict | Accept deterministic |
| Multiple sources agree on issue | Elevate severity |

### Unresolved → Human Gate

| Condition | Action |
|---|---|
| Source-backed conflict with source-backed | Flag conflict, both positions noted |
| Competing high-confidence findings | Flag conflict, human decides |
| ACPT acceptability in question | Flag for Layer 3 decision |
| Any dimension severity = critical with weak rationale | Flag for human review |

## 6. Outputs

```json
{
  "node_id": "QA",
  "human_gate_packet": {
    "section_a_executive_summary": "string",
    "section_b_dimension_findings": {
      "COMP": {"status": "complete", "finding_count": 3, "critical_issues": 0},
      "CORR": {"status": "complete", "finding_count": 2, "critical_issues": 0},
      "ADEQ": {"status": "complete", "finding_count": 1, "critical_issues": 0},
      "TRAC": {"status": "complete", "finding_count": 0, "critical_issues": 0},
      "CONS": {"status": "complete", "finding_count": 2, "critical_issues": 0},
      "ACPT": {"status": "complete", "finding_count": 1, "critical_issues": 1, "requires_human_review": true},
      "PMS": {"status": "not_triggered|triggered", "finding_count": 0}
    },
    "section_c_conflicts_and_qa_resolutions": [
      {
        "conflict_id": "QA-CONF-001",
        "description": "string",
        "qa_resolution": "accepted|escalated|partially_resolved",
        "resolution_basis": "string",
        "parties_involved": ["COMP", "CONS"]
      }
    ],
    "section_d_high_risk_items": [
      {
        "risk_item_id": "HR-001",
        "description": "string",
        "severity": "critical",
        "dimension": "ACPT",
        "requires_human_layer3_decision": true
      }
    ],
    "section_e_pms_findings": [],
    "section_f_recommended_decisions": [
      {
        "decision_area": "RMF_acceptability",
        "recommendation": "approve|conditional_approve|reject|defer",
        "rationale": "string",
        "conditions_for_approval": ["string"]
      }
    ]
  },
  "qa_gate_status": "pass|conditional_pass|fail|escalated",
  "unresolved_conflicts": []
}
```

## 7. Forbidden Actions

- **NO Layer 3 compliance decisions**
- **NO final RMF acceptability decisions**
- **NO benefit-risk final decisions**
- **NO closure of residual risk acceptability questions**

## 8. Human Gate Behavior

- **STOP HERE** — workflow pauses at Human Gate
- Human reviewer reviews packet and makes Layer 3 decisions
- Human decision injected back into workflow
- Only after human decision does flow continue to Findings Synthesis

---

*QA Gate synthesizes findings and prepares for human Layer 3 decisions — it does NOT make those decisions itself*
