# Phase 7 Retrieval Externalization Spec

## Scope
Phase 7 externalizes the evidence acquisition layer for CER authoring. It does not modify the authoring graph, gate criteria, 1+6 agents, prompts, or device identity arbitration.

## Implemented Runtime Path
The implementation is in `backend/packages/harness/deerflow/runtime/cer_authoring/pipeline.py` and `backend/packages/harness/deerflow/runtime/cer_authoring/artifacts.py`.

The authoring flow now includes:

1. Domain-lock-aware query planning in `_phase7_search_plan`.
2. Retrieval-domain profile construction in `_phase7_retrieval_domain_profile`.
3. PubMed/MCP retrieval ledgers through `_pubmed_mcp_retrieval_ledger_rows`.
4. Domain-aware title/abstract screening through `screen_literature`.
5. Evidence-source trace and full-text acquisition trace through `appraise_evidence`.
6. Writer evidence consumption trace through `build_claim_evidence_benefit_risk_ledgers`.

## Evidence Consumption Rule
No evidence may be treated as pivotal or supportive writer input unless it has:

- a stable source ID or PMID where available;
- query provenance (`query_id`);
- a screening decision;
- clinical-domain matching;
- device/procedure applicability;
- citation verification;
- full-text status or abstract-only limitation;
- no retrieval-domain mismatch.

Evidence that fails these checks can remain background or gap context, but cannot support strong clinical conclusions.

## Query Construction Inputs
Queries are constructed from:

- locked device identity;
- intended purpose / intended use / indications;
- clinical domain;
- anatomical site;
- procedure type;
- PICO endpoint targets;
- exclusion terms for known wrong domains.

This prevents generic technology terms such as `radiofrequency ablation` from drifting into unrelated domains, for example cardiac electrophysiology when the locked IFU use is orthopedic joint soft-tissue surgery.

## Artifact Contract
Phase 7 adds these artifacts:

- `query_construction_trace.csv`
- `pubmed_mcp_retrieval_ledger.csv`
- `pmid_screening_and_exclusion_table.csv`
- `fulltext_acquisition_status_table.csv`
- `evidence_source_trace_matrix.csv`
- `retrieval_domain_grounding_report.md`
- `writer_evidence_consumption_trace.csv`

These artifacts are also included in `authoring_workbook.json`.

## Boundaries
This patch does not:

- hardcode PILOT-01;
- fake PubMed results;
- allow LLM-generated citations without retrieval provenance;
- change G30/G33/G38 criteria;
- change identity arbitration;
- change graph topology.
