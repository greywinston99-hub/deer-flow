# RMF DocStruct Agent

**Date:** 2026-04-19
**Phase:** RMF_AGENT_TEAM_HARNESS_CONFIG_MOUNTING_PHASE_A
**Node:** rmf_docstruct
**Runtime Type:** deterministic_parser_plus_optional_llm

---

## 1. Node Overview

DocStruct parses and structures incoming RMF documents. It uses a **deterministic parser** for structured extraction, with **optional LLM enhancement** for ambiguous content.

## 2. Responsibilities

1. **Document Parsing**
   - Parse RMF document structure (sections, subsections, risk tables)
   - Extract CER clinical evidence sections
   - Parse IFU warnings and precautions
   - Structure FMEA risk tables

2. **Structured Extraction**
   - Extract risk items with: id, description, severity, probability, detectability, RPN
   - Extract hazard scenarios and hazardous situations
   - Extract risk control measures and their effectiveness
   - Extract benefit-risk assessment sections

3. **Optional LLM Enhancement**
   - Use CERLLMInvoker with `structured_extraction` profile for unclear sections
   - Temperature: 0.1 (low creativity for extraction accuracy)
   - Only invoke LLM when deterministic parser cannot resolve structure

## 3. Inputs

| Input | Source | Description |
|---|---|---|
| `raw_documents` | Orchestrator | Raw document content by type |
| `document_type` | Orchestrator | RMF, CER, IFU, FMEA |

## 4. Outputs

| Output | Schema | Description |
|---|---|---|
| `rmf_structured` | RMF Document Schema | Parsed RMF with risk items |
| `cer_structured` | CER Document Schema | Parsed CER with clinical evidence |
| `ifu_structured` | IFU Document Schema | Parsed IFU with warnings |
| `fmea_structured` | FMEA Document Schema | Parsed FMEA with risk table |

## 5. Output Schema (RMF Structured)

```json
{
  "document_type": "RMF",
  "sections": {
    "risk_management_plan": {"present": true, "content_hash": "string"},
    "risk_analysis": {"present": true, "risk_count": "number", "risks": []},
    "risk_evaluation": {"present": true, "accepted_risks": [], "residual_risks": []},
    "risk_control": {"present": true, "measures": []},
    "production_post_monitoring": {"present": true, "pmcf_reference": "string"}
  },
  "parsing_metadata": {
    "parser_version": "det-1.0",
    "llm_enhancement_used": false,
    "ambiguous_sections": []
  }
}
```

## 6. Forbidden Actions

- **NO compliance judgment** — only structure extraction
- **NO risk acceptability decisions** — those are for ACPT and Human Gate
- **NO traceability verification** — that's for TRAC

## 7. Handoff

- Output to L1 Rule Engine for deterministic rule checks
- Output also available to all dimension agents for semantic review

---

*DocStruct is the data extraction layer — what gets parsed here feeds all downstream nodes*
