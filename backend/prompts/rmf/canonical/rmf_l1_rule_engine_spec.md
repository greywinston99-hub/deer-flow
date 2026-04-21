# RMF L1 Rule Engine Specification

**Date:** 2026-04-19
**Phase:** RMF_AGENT_TEAM_HARNESS_CONFIG_MOUNTING_PHASE_A
**Node:** rmf_l1_rule_engine
**Runtime Type:** deterministic_rule_engine

---

## 1. Node Overview

L1 Rule Engine performs **deterministic** checks against structured documents. It is a pure rule-based system — NO LLM involvement. It runs BEFORE all semantic dimension agents.

## 2. Responsibilities

1. **Mandatory Rule Checks**
   - RMF-B-001: Benefit-risk language check (ALARP forbidden)
   - RMF-C-001: Production section completeness
   - RMF-D-001: PMS/PMCF reference validation
   - RMF-E-001: Traceability chain completeness
   - RMF-F-001: IFU warnings alignment

2. **Fail-Fast Detection**
   - If any hard-fail rule triggers, set `hard_fail = true`
   - Route to QA Gate with FAIL status immediately

3. **Findings Generation**
   - Generate structured findings for each rule check
   - Severity: `critical` for hard-fail, `major` for soft-fail, `minor` for warnings

## 3. Rule Definitions

| Rule ID | Description | Fail Mode | Severity |
|---|---|---|---|
| RMF-B-001 | ALARP/benefit-risk language in acceptability section | HARD FAIL | critical |
| RMF-C-001 | Production section empty or template-like | HARD FAIL | critical |
| RMF-D-001 | PMS/PMCF referenced but no actual content | SOFT FAIL | major |
| RMF-E-001 | Traceability chain has gaps | SOFT FAIL | major |
| RMF-F-001 | IFU warnings not reflected in RMF risk controls | SOFT FAIL | major |

## 4. Inputs

| Input | Source | Description |
|---|---|---|
| `rmf_structured` | DocStruct | Parsed RMF document |
| `cer_structured` | DocStruct | Parsed CER document |
| `ifu_structured` | DocStruct | Parsed IFU document |
| `fmea_structured` | DocStruct | Parsed FMEA document |
| `approved_knowledge_assets` | NocoDB | Review checklists |

## 5. Outputs

```json
{
  "l1_rule_engine_results": {
    "rules_checked": ["RMF-B-001", "RMF-C-001", "RMF-D-001", "RMF-E-001", "RMF-F-001"],
    "failures": [
      {
        "rule_id": "RMF-B-001",
        "description": "ALARP language detected",
        "severity": "critical",
        "evidence": {"section": "risk_evaluation", "text": "..."},
        "hard_fail": true
      }
    ],
    "warnings": [],
    "hard_fail": false
  }
}
```

## 6. Forbidden Actions

- **NO LLM invocation** — deterministic only
- **NO semantic judgment** — only rule pattern matching
- **NO acceptability decisions** — hard_fail routes to QA Gate for Layer 1 arbitration

## 7. Handoff

- If `hard_fail = true`: Route immediately to QA Gate with FAIL status
- If `hard_fail = false`: Continue to parallel dimension agents
- All L1 findings are input to dimension agents for context

---

*L1 Rule Engine is the gatekeeper — deterministic checks run before any semantic review*
