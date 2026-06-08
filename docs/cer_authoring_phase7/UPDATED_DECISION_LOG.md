# Updated Decision Log

## Phase 7 Decision
Implemented retrieval externalization in the existing CER authoring runtime without changing graph, gates, agents, prompts, or identity arbitration.

## Rationale
PILOT-01 showed that correct IFU intended-use extraction is insufficient if literature retrieval can drift into a wrong clinical domain. Evidence must be externally retrieved, screened, traceable, and writer-approved before it can support CER conclusions.

## Decision
Adopt Phase 7 retrieval grounding as a mandatory evidence acquisition carrier layer:

- query construction trace is mandatory;
- PubMed/MCP retrieval ledger is mandatory;
- PMID/source screening rationale is mandatory;
- full-text acquisition trace is mandatory;
- Writer evidence consumption trace is mandatory;
- retrieval-domain mismatches block writer consumption.

## Final Label
`PHASE7_ACCEPTED_RETRIEVAL_GROUNDED`
