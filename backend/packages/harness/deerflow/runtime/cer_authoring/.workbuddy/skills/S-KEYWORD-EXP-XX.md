# S-KEYWORD-EXP-XX: Keyword Association Expansion

- **Type**: Prompt+Guard
- **Step**: query_expansion (Step 7/16A auxiliary)
- **Batch**: P2
- **Agent**: authoring-methodology-sota-agent

## Input
- Current search terms from `query_construction_trace`
- `domain_term_variants.json` knowledge base
- Domain context from `DOMAIN_DEFAULTS`

## Output
- Expanded search terms with association strength scores
- Updated `query_construction_trace`

## Decision Logic
1. Knowledge graph expansion mode (3-level traversal):
   - Level 1: direct synonyms from MeSH/thesaurus
   - Level 2: associated concepts (co-occurring MeSH terms)
   - Level 3: broader/narrower concept hierarchy
2. Each expansion term scored by:
   - Domain relevance (0-1): how specific to the clinical domain
   - Co-occurrence frequency (0-1): how often appears with original terms
   - Term specificity (0-1): precision vs recall trade-off
3. No domain-external terms (enforce via `locked_domain` constraint)
4. Record expansion strategy to `query_construction_trace`

## Checks
- 3+ recall improvement test cases validated
- No domain-external terms introduced
- Expansion terms have strength scores
- Strategy recorded in trace
