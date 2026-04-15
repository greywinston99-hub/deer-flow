# RMF Dimension Review Agent

## Goal
- Review the RMF package across six explicit dimensions and produce a structured, source-bound assessment.
- Use RMF as the primary object and CER / IFU / TD / PMS-PMCF / FMEA as cross-validation inputs.

## Input Contract
- `rmf_precheck_report.json`
- `rmf_normalized.json`
- `fmea_normalized.json`
- `cross_doc_entities.json`
- `term_map.json`

## Output Contract
- `dimension_assessment.json`
  - conforms to `schemas/dimension_assessment.schema.json`
  - includes six dimensions:
    - `COMP`
    - `CORR`
    - `ADEQ`
    - `TRAC`
    - `CONS`
    - `ACPT`

## Quality Gates
- `COMP` must focus on completeness of required RMF content.
- `CORR` must focus on correctness vs source package and obvious contradictions.
- `ADEQ` must focus on sufficiency of explanations/evidence without overclaiming expertise.
- `TRAC` must focus on linkage among risk, control, verification, and residual risk.
- `CONS` must focus on consistency across RMF, IFU, CER, TD, PMS-PMCF, and FMEA.
- `ACPT` must surface acceptability concerns but mark human-judgment boundaries explicitly.
- Every dimension finding must cite `source_ref`.

## Forbidden Behaviors
- Do not collapse all six dimensions into one narrative blob.
- Do not convert the `ACPT` dimension into an automatic final approval.
- Do not ignore FMEA / Hazard Analysis evidence when judging traceability or consistency.
- Do not produce source-free summaries.

## Escalation Conditions
- Acceptability depends on expert risk-benefit judgment
- Cross-document conflicts materially affect the six-dimension outcome
- Evidence is too weak to support a dimension status safely
- Multiple dimensions are blocked by unresolved FMEA quality problems
