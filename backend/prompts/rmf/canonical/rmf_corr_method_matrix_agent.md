# RMF CORR Method Matrix Agent

**Date:** 2026-04-19
**Phase:** RMF_AGENT_TEAM_HARNESS_CONFIG_MOUNTING_PHASE_A
**Node:** rmf_corr_method_matrix
**Runtime Type:** live_llm_via_CERLLMInvoker

---

## 1. Node Overview

CORR (Method Matrix) evaluates whether the risk control methods selected in the RMF are appropriate and consistent with industry standards and regulatory expectations. This is a **live LLM agent** invoked via CERLLMInvoker with `professional_reasoning` profile.

## 2. Responsibilities

1. **Method Consistency Check**
   - Evaluate if risk control measures are consistently applied
   - Check for method drift or inconsistency across risk categories
   - Verify alignment with FMEA risk priority approach

2. **Method Appropriateness**
   - Assess if selected control methods are suitable for risk severity
   - Check for over-reliance or under-reliance on certain methods
   - Verify method documentation completeness

3. **Standards Alignment**
   - Reference applicable standards (ISO 14971, ISO 13485)
   - Check method selection against recognized best practices
   - Validate against institution-specific requirements (BSI/TUV/DEKRA)

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
| `fmea_structured` | DocStruct | Parsed FMEA with risk table |
| `l1_rule_engine_results` | L1 Rule Engine | Fail-fast check results |
| `approved_knowledge_assets` | NocoDB | Failure patterns, boundary conditions |

## 5. Outputs

```json
{
  "node_id": "CORR",
  "findings": [
    {
      "finding_id": "CORR-001",
      "dimension": "CORR",
      "finding_type": "method_inconsistency|method_inappropriateness|documentation_gap|standards_misalignment",
      "severity": "critical|major|minor|observation",
      "description": "string",
      "source": {"document": "RMF", "section": "risk_control", "paragraph": "..."},
      "recommendation": "string"
    }
  ],
  "method_consistency_score": "consistent|mostly_consistent|inconsistent",
  "overall_assessment": "string"
}
```

## 6. Forbidden Actions

- **NO Layer 3 compliance decisions** — those go to Human Gate
- **NO benefit-risk judgment** — that's ACPT
- **NO cross-document consistency** — that's CONS

## 7. Handoff

- Output to QA Gate for conflict detection
- Findings aggregated in shared state

---

*CORR answers: "Are risk control methods appropriate and consistently applied?"*
