# RMF COMP Risk Coverage Agent

**Date:** 2026-04-19
**Phase:** RMF_AGENT_TEAM_HARNESS_CONFIG_MOUNTING_PHASE_A
**Node:** rmf_comp_risk_coverage
**Runtime Type:** live_llm_via_CERLLMInvoker

---

## 1. Node Overview

COMP (Risk Coverage) evaluates whether the RMF adequately covers all relevant risks for the device. This is a **live LLM agent** invoked via CERLLMInvoker with `professional_reasoning` profile.

## 2. Responsibilities

1. **Coverage Assessment**
   - Evaluate if all known hazard scenarios are addressed
   - Check if risk controls are proportionate to severity
   - Verify production and post-production risk monitoring

2. **Evidence Evaluation**
   - Cross-reference RMF risks against CER clinical evidence
   - Identify gaps in risk coverage
   - Assess adequacy of risk control measures

3. **Findings Generation**
   - Generate structured findings with severity levels
   - Provide specific, actionable observations
   - Cite source documents and sections

## 3. Model Profile

| Parameter | Value |
|---|---|
| Profile | professional_reasoning |
| Model | MiniMax-M2.7 |
| Max Tokens | 16384 |
| Temperature | 0.2 |

## 4. Inputs

| Input | Source | Description |
|---|---|---|
| `rmf_structured` | DocStruct | Parsed RMF with risk items |
| `cer_structured` | DocStruct | Parsed CER with clinical evidence |
| `l1_rule_engine_results` | L1 Rule Engine | Fail-fast check results |
| `approved_knowledge_assets` | NocoDB | Review heuristics |

## 5. Outputs

```json
{
  "node_id": "COMP",
  "findings": [
    {
      "finding_id": "COMP-001",
      "dimension": "COMP",
      "finding_type": "coverage_gap|insufficient_control|proportionality_concern|evidence_mismatch",
      "severity": "critical|major|minor|observation",
      "description": "string",
      "source": {"document": "RMF", "section": "risk_analysis", "paragraph": "..."},
      "recommendation": "string"
    }
  ],
  "coverage_score": "adequate|inadequate|partial",
  "overall_assessment": "string"
}
```

## 6. Forbidden Actions

- **NO Layer 3 compliance decisions** — those go to Human Gate
- **NO final risk acceptability judgments** — ACPT makes those
- **NO cross-document consistency determination** — that's CONS

## 7. Handoff

- Output to QA Gate for conflict detection
- Findings aggregated in shared state

---

*COMP answers: "Are all risks adequately covered and controlled?"*
