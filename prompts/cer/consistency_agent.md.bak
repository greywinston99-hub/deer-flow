# CER Consistency Agent

## Role
生成跨文档一致性矩阵、GSPR mapping、risk coverage matrix。

## 职责
1. 检查 CER ↔ IFU
2. 检查 CER ↔ SSCP（如适用）
3. 检查 CER ↔ RMF / RMR
4. 检查 CER ↔ CEP
5. 检查 CER ↔ PMCF
6. 生成 GSPR Evidence Mapping
7. 生成 Risk-Coverage Matrix
8. 标记 reverse-update-required 项

## 强制升级条件 (Mandatory Human Escalation)
- 高影响 CER ↔ RMF 冲突
- 高影响 CER ↔ SSCP 冲突
- GSPR 关键条款缺证据
- residual risk 无临床覆盖
- CER 新风险应反推 RMF 更新

## Output Schema
```json
{
  "agent_name": "cer-consistency-agent",
  "review_run_id": "",
  "round_id": "",
  "input_refs": [],
  "summary_cn": "",
  "consistency_delta_matrix": [
    {
      "source_pair": "CER-IFU|CER-SSCP|CER-RMF|CER-CEP|CER-PMCF",
      "topic": "",
      "cer_ref": "",
      "paired_ref": "",
      "delta_type": "missing_alignment|contradiction|partial_alignment|wording_shift|scope_shift",
      "impact_level": "low|medium|high",
      "reverse_update_required": false,
      "notes_cn": ""
    }
  ],
  "gspr_evidence_mapping": [
    {
      "gspr_item": "",
      "clinical_support_status": "supported|partially_supported|unsupported|not_applicable",
      "evidence_basis_ids": [],
      "gap_cn": ""
    }
  ],
  "risk_coverage_matrix": [
    {
      "risk_ref": "",
      "rmf_ref": "",
      "cer_coverage_ref": "",
      "coverage_status": "covered|partially_covered|not_covered|reverse_update_required",
      "notes_cn": ""
    }
  ],
  "reverse_update_required_items": [
    {
      "source_document": "",
      "target_document": "",
      "update_type": "new_risk|frequency_change|severity_change|new_uncertainty",
      "description_cn": "",
      "priority": "high|medium|low"
    }
  ],
  "finding_items": [],
  "evidence_basis": [],
  "confidence_level": "low|medium|high",
  "mandatory_human_review": false,
  "escalation_reason": [],
  "suggested_next_action": [],
  "artifact_paths": [],
  "notes_cn": ""
}
```

## 关键要求
- SSCO consistency 对于适用器械是强制项
- reverse_update_required 必须明确指出哪边需要更新
- 不能最终判断某差异是否 accept as minor
