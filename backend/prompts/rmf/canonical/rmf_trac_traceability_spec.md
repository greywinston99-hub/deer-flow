# RMF TRAC Traceability Specification

**Date:** 2026-04-19
**Phase:** RMF_AGENT_TEAM_HARNESS_CONFIG_MOUNTING_PHASE_A
**Node:** rmf_trac_traceability
**Runtime Type:** rule_engine_with_llm_semantic_patch

---

## 1. Node Overview

TRAC (Traceability) verifies the completeness and correctness of risk-to-control traceability chains. It is a **hybrid node**: deterministic rule engine first, LLM semantic patch only for unclear linkages.

## 2. Architecture

```
Layer 1: Deterministic Traceability Chain Verification (always runs first)
    ↓
    [If structural chain exists but semantic fit unclear]
    ↓
Layer 2: LLM Semantic Patch (selective, for unclear linkages only)
```

## 3. Responsibilities

### Layer 1: Deterministic Chain Verification

1. **Upstream Traceability**
   - Every risk must trace to at least one hazard
   - Every hazard must trace to at least one risk scenario
   - Complete chain: Hazard → Hazardous Situation → Risk → Harm

2. **Downstream Traceability**
   - Every risk control measure must trace to at least one risk it mitigates
   - Every risk must trace to at least one control measure
   - Production/post-production controls must trace to monitored risks

3. **Gap Detection (Deterministic)**
   - Orphan risks (no hazard linkage)
   - Orphan hazards (no risk linkage)
   - Orphan controls (no risk linkage)
   - Incomplete chains (missing intermediate links)

### Layer 2: LLM Semantic Patch (Conditional)

Only invoked when:
- Structural chain exists (Layer 1 passes)
- But semantic fit is unclear (e.g., "Does this control actually address this risk?")

Trigger conditions:
- Risk-control linkage is documented but semantically weak
- Hazard-risk linkage involves interpretation
- Cross-document traceability (RMF → CER → IFU) has ambiguous links

## 4. Model Profile

| Parameter | Value |
|---|---|
| Profile | rule_patch_semantic |
| Model | MiniMax-M2.7 |
| Max Tokens | 16384 |
| Temperature | 0.2 |

## 5. Inputs

| Input | Source | Description |
|---|---|---|
| `rmf_structured` | DocStruct | Parsed RMF with traceability matrix |
| `cer_structured` | DocStruct | CER traceability to RMF risks |
| `l1_rule_engine_results` | L1 Rule Engine | RMF-E-001 check results |
| `approved_knowledge_assets` | NocoDB | Institution profiles for expectations |

## 6. Outputs

```json
{
  "node_id": "TRAC",
  "layer1_results": {
    "upstream_traceability": {
      "complete": true,
      "orphan_risks": [],
      "orphan_hazards": [],
      "incomplete_chains": []
    },
    "downstream_traceability": {
      "complete": true,
      "orphan_controls": [],
      "uncontrolled_risks": []
    },
    "post_production_traceability": {
      "complete": true,
      "unmonitored_residual_risks": []
    }
  },
  "layer2_patch_results": {
    "invoked": false,
    "unclear_linkages": [],
    "patched_linkages": []
  },
  "findings": [
    {
      "finding_id": "TRAC-001",
      "dimension": "TRAC",
      "finding_type": "orphan_risk|orphan_hazard|orphan_control|incomplete_chain|semantic_gap",
      "severity": "critical|major|minor|observation",
      "description": "string",
      "source": {"document": "RMF", "section": "traceability_matrix", "row": "..."},
      "recommendation": "string"
    }
  ],
  "traceability_score": "complete|mostly_complete|incomplete",
  "overall_assessment": "string"
}
```

## 7. Forbidden Actions

- **NO pure LLM traceability** — must have deterministic base
- **NO Layer 3 compliance decisions** — those go to Human Gate
- **NO acceptability judgments** — those are for ACPT

## 8. Handoff

- Output to QA Gate for conflict detection
- Findings aggregated in shared state

---

*TRAC answers: "Is the risk-to-control traceability chain complete and correct?"*
