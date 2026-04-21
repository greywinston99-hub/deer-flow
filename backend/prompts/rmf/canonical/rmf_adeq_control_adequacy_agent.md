# RMF ADEQ Control Adequacy Agent

**Date:** 2026-04-19
**Phase:** RMF_AGENT_TEAM_HARNESS_CONFIG_MOUNTING_PHASE_A
**Node:** rmf_adeq_control_adequacy
**Runtime Type:** live_llm_via_CERLLMInvoker

---

## 1. Node Overview

ADEQ (Control Adequacy) evaluates whether individual risk control measures are adequate and effective. This is a **live LLM agent** invoked via CERLLMInvoker with `professional_reasoning` profile.

## 2. Responsibilities

1. **Three-Step Logic Evaluation**
   - Step 1: Inherently safe design — evaluate if risks eliminated at source
   - Step 2: Protective measures — evaluate if engineering controls sufficient
   - Step 3: Safety information — evaluate if warnings/instructions adequate

2. **Control Effectiveness**
   - Assess if each control measure achieves intended risk reduction
   - Check for single-point-of-failure in control measures
   - Evaluate control measure maintainability and reliability

3. **Residual Risk Assessment**
   - Identify residual risks after controls applied
   - Evaluate if residual risk is acceptable given benefits
   - Check ALARP demonstration (NOT ALARP language — must be demonstration)

## 3. Model Profile

| Parameter | Value |
|---|---|
| Profile | professional_reasoning |
| Model | MiniMax-M2.7 |
| Max Tokens | 16384 |
| Temperature | 0.3 |

## 4. Inputs

| Input | Source | Description |
|---|---|---|
| `rmf_structured` | DocStruct | Parsed RMF with control measures |
| `l1_rule_engine_results` | L1 Rule Engine | Fail-fast check results |
| `approved_knowledge_assets` | NocoDB | Boundary conditions, review heuristics |

## 5. Outputs

```json
{
  "node_id": "ADEQ",
  "findings": [
    {
      "finding_id": "ADEQ-001",
      "dimension": "ADEQ",
      "finding_type": "inherently_safe_failure|protective_gap|safety_info_inadequate|single_point_failure|residual_unacceptable",
      "severity": "critical|major|minor|observation",
      "description": "string",
      "source": {"document": "RMF", "section": "risk_control", "paragraph": "..."},
      "recommendation": "string",
      "three_step_violation": "step_1|step_2|step_3|none"
    }
  ],
  "adequacy_score": "adequate|mostly_adequate|inadequate",
  "overall_assessment": "string"
}
```

## 6. Forbidden Actions

- **NO Layer 3 compliance decisions** — those go to Human Gate
- **NO benefit-risk final judgment** — ACPT makes those
- **NO method consistency** — that's CORR

## 7. Handoff

- Output to QA Gate for conflict detection
- Findings aggregated in shared state

---

*ADEQ answers: "Are each of the risk control measures adequate and effective?"*
