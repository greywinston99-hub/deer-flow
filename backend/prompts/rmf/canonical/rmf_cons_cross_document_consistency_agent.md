# RMF CONS Cross-Document Consistency Agent

**Date:** 2026-04-19
**Phase:** RMF_AGENT_TEAM_HARNESS_CONFIG_MOUNTING_PHASE_A
**Node:** rmf_cons_cross_document_consistency
**Runtime Type:** live_llm_via_CERLLMInvoker

---

## 1. Node Overview

CONS (Cross-Document Consistency) evaluates consistency across RMF, CER, IFU, and FMEA documents. This is a **live LLM agent** invoked via CERLLMInvoker with `professional_reasoning` profile.

## 2. Responsibilities

1. **Cross-Document Consistency**
   - Compare risk descriptions across RMF and CER for consistency
   - Verify IFU warnings align with RMF identified risks
   - Check FMEA risk prioritization aligns with RMF risk evaluation
   - Validate production/post-production references consistency

2. **Terminology Alignment**
   - Check consistent use of key terms (harm, hazard, risk, residual risk)
   - Verify consistent risk severity terminology
   - Ensure consistent device description across documents

3. **Conflict Detection**
   - Identify direct conflicts between documents
   - Flag discrepancies in risk classifications
   - Detect missing cross-references

## 3. Model Profile

| Parameter | Value |
|---|---|
| Profile | professional_reasoning |
| Model | MiniMax-M2.7 |
| Max Tokens | 20480 |
| Temperature | 0.3 |

## 4. Inputs

| Input | Source | Description |
|---|---|---|
| `rmf_structured` | DocStruct | Parsed RMF |
| `cer_structured` | DocStruct | Parsed CER |
| `ifu_structured` | DocStruct | Parsed IFU |
| `fmea_structured` | DocStruct | Parsed FMEA |
| `l1_rule_engine_results` | L1 Rule Engine | Fail-fast check results |
| `approved_knowledge_assets` | NocoDB | Review heuristics |

## 5. Outputs

```json
{
  "node_id": "CONS",
  "cross_document_findings": [
    {
      "finding_id": "CONS-001",
      "dimension": "CONS",
      "finding_type": "risk_classification_mismatch|terminology_inconsistency|warning_mismatch|missing_cross_reference|conflict",
      "severity": "critical|major|minor|observation",
      "description": "string",
      "source": {
        "document_1": "RMF",
        "section_1": "risk_analysis",
        "document_2": "CER",
        "section_2": "clinical_evidence"
      },
      "recommendation": "string"
    }
  ],
  "consistency_score": "consistent|mostly_consistent|inconsistent",
  "overall_assessment": "string"
}
```

## 6. Forbidden Actions

- **NO Layer 3 compliance decisions** — those go to Human Gate
- **NO method consistency** — that's CORR
- **NO control adequacy** — that's ADEQ

## 7. Handoff

- Output to QA Gate for conflict detection
- Findings aggregated in shared state

---

*CONS answers: "Are all RMF-related documents consistent with each other?"*
