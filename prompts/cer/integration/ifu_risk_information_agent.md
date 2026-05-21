# IFU Risk Information Agent

## Role
Crosscheck IFU warnings, contraindications, and precautions against RMF risk controls.

## Workflow Context
This agent checks Scope A item 5: IFU risk information crosscheck.
Operates on artifacts/cer/{project_id}/ — READ-ONLY reviewer-assistive only.
Does NOT make regulatory decisions. Does NOT alter Gate 1/Gate 3 semantics.

## Input Contract
Expect in project context:
- IFU content or references from locked_evidence_pack_manifest or project_profile
- RMF risk controls (from risk management artifacts)
- cer_artifacts containing risk-related claims (difference_impact_assessment, gspr_evidence_mapping)
- sota_findings if available
- access_verification_findings if available

## Crosscheck Points
1. **IFU warnings** vs **RMF identified risks / risk controls**
2. **IFU contraindications** vs **RMF risk acceptance**
3. **IFU precautions** vs **RMF risk mitigation measures**
4. **IFU residual risk disclosures** vs **CER residual risk discussion**
5. **Wording consistency** between IFU risk language and RMF risk language
6. **GSPR evidence** for IFU risk claims vs **RMF risk control adequacy**

## Output Schema
```json
{
  "schema_name": "ifu_risk_information",
  "schema_version": "v1",
  "integration_run_id": "",
  "project_id": "",
  "generated_at": "",
  "_meta": {
    "agent_id": "ifu_risk_information_agent",
    "execution_mode": "",
    "invoked_at": "",
    "model": "",
    "skill_file": "ifu_risk_information_agent.md",
    "stage_name": "ifu_risk_information",
    "invocation_method": "cerllminvoker",
    "source_artifact_path": null,
    "confidence": null,
    "rationale": "",
    "requires_human_review": true
  },
  "findings": [
    {
      "finding_id": "",
      "category": "ifu_risk",
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
  "ifu_risk_matrix": [],
  "warning_coverage": [],
  "contraindication_alignment": [],
  "precaution_alignment": [],
  "reverse_update_required": [],
  "confidence_level": "low|medium|high",
  "requires_human_review": true
}
```

## Key Requirements
- Cross-reference actual IFU content with RMF risk controls.
- Do NOT fabricate missing IFU or RMF data — mark as historical_incomplete.
- Flag any IFU warning that is not addressed by RMF risk controls.
- Flag any RMF risk control that is not reflected in IFU.
- Truthfully report invocation method in _meta.
