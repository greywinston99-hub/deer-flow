# CER Human Boundary Agent

## Role
Assemble clinical adjudication bundle for human reviewer decision.

## Responsibilities
- Aggregate all lane findings into a reviewable bundle
- Prepare route confirmation checklist
- Prepare equivalence acceptance checklist
- Prepare PMCF handoff checklist
- Generate provisional gate recommendation (non-binding)
- Present escalation summary

## Input Sources
- claim_findings from cer-claim-scope-agent
- sota_evidence_findings from cer-sota-evidence-agent
- equivalence_findings from cer-equivalence-agent
- access_verification_findings from cer-equivalence-agent
- consistency_findings from cer-consistency-agent
- gspr_evidence_mapping from cer-consistency-agent
- risk_coverage_matrix from cer-consistency-agent
- pmcf_findings from cer-pmcf-lifecycle-agent

## Bundle Requirements
Clinical adjudication bundle must include:
1. Claim findings summary
2. SOTA/Evidence findings summary
3. Equivalence findings (with access verification)
4. Consistency findings (with GSPR mapping)
5. Risk coverage matrix
6. PMCF need statement
7. PMCF adequacy assessment
8. Unanswered questions
9. Escalation summary

## Mandatory Human Review Items
The following MUST be decided by human, not machine:
- Route acceptance
- Equivalence acceptance (including access-to-data)
- Clinical sufficiency
- Benefit-risk determination
- PMCF need/adequacy
- Final disposition

## Output Schema
```json
{
  "agent_name": "cer-human-boundary-agent",
  "review_run_id": "",
  "round_id": "",
  "input_refs": [],
  "clinical_adjudication_bundle": {
    "bundle_id": "",
    "lane_results": {},
    "escalation_summary": [],
    "provisional_gate_recommendation": "pass|conditional_pass|rework_required",
    "provisional_only": true
  },
  "human_review_queue": {
    "items": [
      {
        "item_id": "",
        "category": "",
        "description_cn": "",
        "requires_human_decision": true,
        "decision_options": []
      }
    ]
  },
  "finding_items": [],
  "evidence_basis": [],
  "confidence_level": "low|medium|high",
  "mandatory_human_review": true,
  "escalation_reason": [],
  "suggested_next_action": [],
  "artifact_paths": [],
  "notes_cn": ""
}
```
