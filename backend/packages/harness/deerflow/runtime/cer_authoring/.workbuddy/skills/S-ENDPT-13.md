# S-ENDPT-13: Clinical Endpoint Extraction

- **Type**: Prompt+Guard
- **Step**: Endpoint Extraction (Step 13A)
- **Batch**: P0
- **Agent**: authoring-evidence-agent

## Input
- Full-text article content from `document_structured_content`
- `claim_ledger` for claim context anchoring
- Article appraisal for evidence role

## Output
- `endpoint_extraction`: endpoint_id, endpoint_name, value, unit, timepoint, sample_size, statistical_test, p_value, confidence_interval, source_location (page/table), associated_claim_ids

## Decision Logic
1. Search path in paper: Abstract → Results → Tables → Figures → Supplementary
2. Numeric endpoint recognition: "X% (95% CI: Y-Z, p=0.0X)" pattern
3. Event-type endpoint: "X events in Y patients (Z%)"
4. Footnote/qualifier handling: extract and attach as qualifier field
5. Table extraction: parse table cells for endpoint values, attach header as context
6. Claim association: semantic match extracted endpoint → claim_ledger.claim_text

## Checks
- Recall ≥ 75% on 20 test papers
- Each endpoint has source page/table trace
- `associated_claim_ids` populated via semantic matching
- HC-04 human confirmation validates extraction
