# RMF PMS Post-Production Feedback Lane

**Date:** 2026-04-19
**Phase:** RMF_AGENT_TEAM_HARNESS_CONFIG_MOUNTING_PHASE_A
**Node:** rmf_pms_post_production_feedback_lane
**Runtime Type:** conditional_live_llm_via_CERLLMInvoker
**Conditional:** YES — only triggers based on risk conditions

---

## 1. Node Overview

PMS Lane is a **conditional** node that performs additional review when specific risk conditions are met. It is NOT triggered merely because PMS/PMCF documents exist — it is triggered by risk-driven conditions.

## 2. Trigger Conditions

PMS Lane triggers if ANY of the following conditions are met:

| Condition | Source | Description |
|---|---|---|
| ACPT high residual risk | ACPT findings | `severity=critical` residual risk with weak rationale |
| ACPT benefit-risk uncertainty | ACPT assessment | `overall_benefit_risk = uncertain` |
| CONS missing PMS/PMCF reference | CONS findings | `finding_type = missing_pms_reference` |
| COMP production section weak | COMP findings | `severity=critical` in production section |
| Project profile concerns | Project metadata | Complaints, vigilance, trend, PMCF data flagged |
| Human reviewer explicit request | Human Gate | Reviewer requests PMS Lane review |

**PMS Lane does NOT trigger if:**
- PMS/PMCF documents simply exist
- No risk-driven conditions are present

## 3. Responsibilities

1. **PMS/PMCF Adequacy Review**
   - Evaluate completeness of PMS data collection plan
   - Assess PMCF plan adequacy for identified risks
   - Check vigilance and trend monitoring procedures

2. **Post-Production Risk Assessment**
   - Evaluate if production risks are adequately monitored
   - Assess feedback loop effectiveness
   - Check recall and field safety corrective action procedures

3. **Real-World Evidence Integration**
   - If real-world data available, assess its integration with RMF
   - Evaluate post-market surveillance effectiveness

## 4. Model Profile

| Parameter | Value |
|---|---|
| Profile | professional_reasoning |
| Model | MiniMax-M2.7 |
| Max Tokens | 16384 |
| Temperature | 0.3 |

## 5. Inputs

| Input | Source | Description |
|---|---|---|
| `rmf_structured` | DocStruct | Parsed RMF with PMS sections |
| `l1_rule_engine_results` | L1 Rule Engine | Fail-fast check results (RMF-D-001) |
| `approved_knowledge_assets` | NocoDB | Institution profiles, boundary conditions |
| `trigger_condition` | Orchestrator | Which condition triggered PMS Lane |

## 6. Outputs

```json
{
  "node_id": "PMS",
  "triggered_by": "ACPT_high_residual_risk|ACPT_benefit_risk_uncertainty|CONS_missing_PMS|COMP_production_weak|project_profile|human_request",
  "findings": [
    {
      "finding_id": "PMS-001",
      "dimension": "PMS",
      "finding_type": "pms_plan_incomplete|pmcf_inadequate|vigilance_gap|feedback_loop_weak|recall_procedure_gap",
      "severity": "critical|major|minor|observation",
      "description": "string",
      "source": {"document": "RMF", "section": "production_post_monitoring", "paragraph": "..."},
      "recommendation": "string"
    }
  ],
  "pms_adequacy_score": "adequate|mostly_adequate|inadequate",
  "overall_assessment": "string"
}
```

## 7. Forbidden Actions

- **NO trigger based on document existence alone** — must be risk-driven
- **NO Layer 3 compliance decisions** — those go to Human Gate
- **NO standalone PMS judgment** — always part of risk acceptability context

## 8. Handoff

- Output to QA Gate for conflict detection
- Findings aggregated in shared state

---

*PMS Lane answers: "Is post-production risk monitoring adequate given the identified risks?"*
