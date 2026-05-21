# RMF ACPT Residual Risk & Benefit-Risk Agent

**Date:** 2026-04-19
**Phase:** RMF_AGENT_TEAM_HARNESS_CONFIG_MOUNTING_PHASE_A
**Node:** rmf_acpt_residual_risk_benefit_risk
**Runtime Type:** live_llm_via_CERLLMInvoker
**Requires Human Review:** true (default)

---

## 1. Node Overview

ACPT (Acceptability) evaluates residual risk acceptability and benefit-risk assessment. This is a **live LLM agent** invoked via CERLLMInvoker with `high_stakes_reasoning` profile. Due to the high-stakes nature of acceptability decisions, this node **requires human review by default**.

## 2. Responsibilities

1. **Residual Risk Evaluation**
   - Assess acceptability of residual risks after controls applied
   - Evaluate completeness of ALARP demonstration (NOT ALARP language — demonstration of risk reduction adequacy)
   - Check residual risk against acceptance criteria

2. **Benefit-Risk Assessment**
   - Evaluate if clinical benefits outweigh residual risks
   - Assess quality of benefit evidence in CER
   - Check proportionality of benefits to risks

3. **High-Risk Indicator Detection**
   - Flag high residual risks with weak acceptance rationale
   - Identify benefit-risk uncertainty areas
   - Detect unresolved acceptability questions

## 3. Model Profile

| Parameter | Value |
|---|---|
| Profile | high_stakes_reasoning |
| Model | MiniMax-M2.7 |
| Max Tokens | 20480 |
| Temperature | 0.3 |

## 4. Inputs

| Input | Source | Description |
|---|---|---|
| `rmf_structured` | DocStruct | Parsed RMF with residual risks |
| `cer_structured` | DocStruct | Parsed CER with clinical benefits |
| `l1_rule_engine_results` | L1 Rule Engine | Fail-fast check results (RMF-B-001) |
| `approved_knowledge_assets` | NocoDB | Boundary conditions, institution profiles |

## 5. Outputs

```json
{
  "node_id": "ACPT",
  "findings": [
    {
      "finding_id": "ACPT-001",
      "dimension": "ACPT",
      "finding_type": "residual_risk_weak_rationale|benefit_risk_uncertainty|high_risk_unresolved|alarp_insufficient|proportionality_concern",
      "severity": "critical|major|minor|observation",
      "description": "string",
      "source": {"document": "RMF", "section": "risk_evaluation", "paragraph": "..."},
      "recommendation": "string",
      "requires_human_review": true
    }
  ],
  "residual_risk_assessment": {
    "overall_residual_risk": "acceptable|conditionally_acceptable|unacceptable",
    "high_risk_residuals": ["ACPT-001"],
    "alarp_demonstration": "sufficient|insufficient|missing",
    "rationale_weakness": ["string"]
  },
  "benefit_risk_assessment": {
    "overall_benefit_risk": "favorable|uncertain|unfavorable",
    "evidence_quality": "strong|moderate|weak|insufficient",
    "uncertainty_areas": ["string"]
  },
  "requires_human_review": true,
  "overall_assessment": "string"
}
```

## 6. PMS Trigger Conditions

ACPT findings that trigger PMS Lane:

| Condition | Description |
|---|---|
| High residual risk with weak acceptance rationale | ACPT-001 with `severity=critical` |
| Benefit-risk uncertainty | `benefit_risk_assessment.overall_benefit_risk = uncertain` |
| CONS missing PMS/PMCF reference | CONS flagged missing PMCF |

## 7. Forbidden Actions

- **NO final acceptability decision** — Human Gate makes Layer 3 decisions
- **NO closure of residual risk questions** — must flag for human review

## 8. Handoff

- Output to QA Gate for conflict detection
- If high-risk indicators found, set PMS trigger conditions
- Findings aggregated in shared state
- **Flagged for human review before final gate**

---

*ACPT answers: "Are the residual risks acceptable given the clinical benefits?"*
