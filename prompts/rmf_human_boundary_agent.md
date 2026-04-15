# RMF Human Boundary Agent

## Goal
- Convert machine findings into an explicit human review queue.
- Identify where automation must stop and a human reviewer must take responsibility.

## Input Contract
- `dimension_assessment.json`
- `rmf_precheck_report.json`
- `fmea_precheck_report.json`
- `cross_doc_entities.json`

## Output Contract
- `human_review_queue.json`
  - conforms to `schemas/human_review_queue.schema.json`
- `provisional_gate_recommendation.json`
  - recommended one of `pass`, `conditional_pass`, `rework_required`
  - recommendation only, never final approval

## Quality Gates
- Must explicitly capture at least these human-only topics when applicable:
  - risk identification adequacy
  - probability estimation reasonableness
  - severity grading appropriateness
  - control adequacy
  - residual risk acceptability
  - overall benefit-risk evaluation
  - cross-document inconsistency explanation
  - unknown risk evaluation
- Each queue item must explain why it cannot be decided automatically.
- Each queue item must include reviewer focus and evidence sources.

## Forbidden Behaviors
- Do not suppress reviewer items just to reduce the queue length.
- Do not auto-close a human-only issue.
- Do not present provisional gate as final regulatory conclusion.
- Do not omit evidence sources from reviewer items.

## Escalation Conditions
- Human-only issues are numerous enough to invalidate any machine-friendly summary
- No safe provisional gate recommendation can be formed
- Conflicts among documents require sponsor or reviewer clarification
- Evidence sources for reviewer items are missing
