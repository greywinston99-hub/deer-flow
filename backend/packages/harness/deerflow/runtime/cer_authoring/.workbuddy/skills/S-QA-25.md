# S-QA-25: CER Draft Review Path

- **Type**: Few-shot
- **Step**: NB Precheck + Gates (Steps 29-33)
- **Batch**: P2
- **Agent**: authoring-qa-review-agent

## Input
- CER chapter drafts (§1-§9 + Annex A-O)
- All gate reports (43 final gates)
- Writer remediation gate results (W1-W6)

## Output
- `qa_gate_report` with structured review findings
- Final gate decision: PASS_TO_DRAFT_DOCX / REWORK_REQUIRED / HUMAN_HOLD

## Decision Logic (Quick review checklist — 10+ items)
1. Template residue check: scan for "This CER evaluates whether...", "According to MEDDEV..."
2. Domain contamination: forbidden terms in wrong domain context
3. Evidence contradiction: conclusion strength vs evidence quality mismatch
4. Missing SOTA benchmark: claims without benchmark support
5. Internal control fields: ALLOWED_USE_BLOCKED in body text
6. Placeholder text: "Not extracted", "TBD", "pending", "---SEGMENT---"
7. Circular reasoning: conclusion citing claims instead of evidence
8. Overstrong conclusion: "demonstrates conformity" with gap evidence
9. Inconsistent numbers: claim count vs evidence count mismatch
10. Missing required sections: §1-§9 all present

High-risk signals (30-second gate): template_residue OR domain_contamination OR evidence_conflict OR overstrong_conclusion → immediate fail

## Checks
- All 10+ checklist items evaluated
- Consistency with human review ≥ 80%
- High-risk signals trigger immediate HARD_FAIL
