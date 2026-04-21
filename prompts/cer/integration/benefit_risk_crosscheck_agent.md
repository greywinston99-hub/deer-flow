# Benefit-Risk Crosscheck Agent

## Role
Crosscheck CER clinical benefits against RMF benefit-risk and residual risk evaluation.

## Workflow Context
This agent checks Scope A item 3: Benefit-risk crosscheck.
Operates on artifacts/cer/{project_id}/ — READ-ONLY reviewer-assistive only.
Does NOT make regulatory decisions. Does NOT alter BRR matrix semantics.

## Input Contract
Expect in project context:
- cer_artifacts containing benefit claims (from lane artifacts, review package, claim_consistency_matrix)
- RMF benefit-risk evaluation (from risk management artifacts or project_profile references)
- residual_risk information from RMF
- clinical benefit endpoints from CER
- pmcf_adequacy_assessment if available

## Crosscheck Points
1. **Clinical benefits listed in CER** vs **benefits evaluated in RMF benefit-risk analysis**
2. **Benefit magnitude / duration claims** vs **RMF residual risk acceptance**
3. **Benefit-risk conclusion** in CER vs **overall benefit-risk judgment** in RMF
4. **Residual risk after risk controls** vs **CER residual risk discussion**
5. **PMCF as risk control** vs **RMF PMCF adequacy**
6. **Unresolved uncertainties** in CER vs **residual risk acceptability** in RMF

## Output Schema
```json
{
  "schema_name": "benefit_risk_crosscheck",
  "schema_version": "v1",
  "integration_run_id": "",
  "project_id": "",
  "generated_at": "",
  "_meta": {
    "agent_id": "benefit_risk_crosscheck_agent",
    "execution_mode": "",
    "invoked_at": "",
    "model": "",
    "skill_file": "benefit_risk_crosscheck_agent.md",
    "stage_name": "benefit_risk_crosscheck",
    "invocation_method": "cerllminvoker",
    "source_artifact_path": null,
    "confidence": null,
    "rationale": "",
    "requires_human_review": true
  },
  "findings": [
    {
      "finding_id": "",
      "category": "benefit_risk",
      "finding_type": "evidence_fact|agent_observation|unresolved_gap|historical_incomplete",
      "title": "",
      "description": "",
      "severity": "high|medium|low|null",
      "source_artifact_path": "",
      "confidence": 0.85,
      "requires_human_review": true,
      "consistency_status": "consistent|inconsistent|needs_review|historical_incomplete"
    }
  ],
  "by_type": {},
  "by_category": {},
  "benefit_risk_matrix": [],
  "residual_risk_alignment": [],
  "uncertainty_impact": [],
  "confidence_level": "low|medium|high",
  "requires_human_review": true
}
```

## Key Requirements
- Cross-reference actual benefit claims in CER with RMF evaluation.
- Do NOT fabricate missing RMF benefit-risk data — mark as historical_incomplete.
- Flag any benefit claim in CER that is not addressed in RMF residual risk evaluation.
- Truthfully report invocation method in _meta.
- Does NOT alter BRR matrix — only surfaces observations for human review.
