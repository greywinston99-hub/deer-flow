# S-SOTA-07: SOTA Search Strategy

- **Type**: Prompt+Guard
- **Step**: SOTA Search (Step 7)
- **Batch**: P1
- **Agent**: authoring-methodology-sota-agent

## Input
- `sota_pico_strategy` from PICO derivation
- `device_profile.device_class` for database tier selection
- `DATABASE_TIERS` configuration

## Output
- `search_run_registry` with per-database search records
- `sota_search_strategy_table`
- Query construction trace

## Decision Logic
1. Select database tier: Class III → enhanced, Class IIb → standard, others → minimum
2. Build database-specific search queries from PICO MeSH terms
3. SOTA search: wide scope, multiple databases, benchmark-oriented
4. DUE search: narrow scope, device-focused, registry-oriented
5. Set date range: past 10 years or since device first marketed
6. Filter: English language, human studies
7. Record each search: database, date, terms, hits count

## Checks
- ≥ 3 database coverage
- Search terms reproducible
- SOTA and DUE have independent `search_run_registry` entries
- HC-03 human confirmation validates strategy
