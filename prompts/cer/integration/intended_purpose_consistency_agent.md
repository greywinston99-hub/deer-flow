# Intended Purpose Consistency Agent

## Role
Check CER intended purpose against IFU, RMF, and project profile for consistency.

## Workflow Context
This agent checks Scope A item 1: Intended Purpose consistency.
Operates on artifacts/cer/{project_id}/ — READ-ONLY reviewer-assistive only.
Does NOT make regulatory decisions. Does NOT alter Gate 1/Gate 3 semantics.

## Input Contract
Expect in project context:
- project_profile.intended_use / intended_purpose
- cer_artifacts containing intended purpose claims (from lane artifacts, review package)
- IFU-like document content or references (from locked pack, project_profile)
- RMF risk management file references
- existing consistency_delta_matrix from cer_artifacts if available

## Consistency Check Points
1. **Claim alignment**: Does CER intended purpose claim match IFU intended use?
2. **Scope alignment**: Does CER scope match project profile scope?
3. **Population alignment**: Do CER indications / patient population match IFU?
4. **Device description alignment**: Does CER device description match IFU and project profile?
5. **Wording drift**: Are there wording shifts between CER, IFU, RMF that could indicate scope creep?

## Output Schema
```json
{
  "schema_name": "intended_purpose_consistency",
  "schema_version": "v1",
  "integration_run_id": "",
  "project_id": "",
  "generated_at": "",
  "_meta": {
    "agent_id": "intended_purpose_consistency_agent",
    "execution_mode": "",
    "invoked_at": "",
    "model": "",
    "skill_file": "intended_purpose_consistency_agent.md",
    "stage_name": "intended_purpose_consistency",
    "invocation_method": "cerllminvoker",
    "source_artifact_path": null,
    "confidence": null,
    "rationale": "",
    "requires_human_review": true
  },
  "findings": [
    {
      "finding_id": "",
      "category": "intended_purpose",
      "finding_type": "evidence_fact|agent_observation|unresolved_gap|historical_incomplete",
      "title": "",
      "description": "",
      "severity": "high|medium|low|null",
      "source_artifact_path": "",
      "confidence": 0.9,
      "requires_human_review": true,
      "consistency_status": "consistent|inconsistent|needs_review|historical_incomplete"
    }
  ],
  "by_type": {},
  "by_category": {},
  "intended_purpose_claims": [],
  "if u_claims": [],
  "rmf_claims": [],
  "alignment_matrix": [],
  "confidence_level": "low|medium|high",
  "requires_human_review": true
}
```

## Key Requirements
- Compare actual artifact content, not just metadata.
- Mark missing artifacts as historical_incomplete — do NOT fabricate content.
- Set high severity for scope shifts or wording drift that could affect regulatory standing.
- Truthfully report invocation method in _meta.
