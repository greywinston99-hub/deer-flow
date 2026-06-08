# PROMPT CHANGE CONTROL — CER Authoring Stack V1.0

> Claude Code | 2026-05-15 | Phase 2B

## Change Control Policy

1. Any prompt change requires owner review via this document.
2. Prompt changes must update PROMPT_HASH_MANIFEST.json.
3. Changed prompts must be tested with full regression before approval.
4. Prompt changes that weaken writer gates are prohibited.

## Prompt Categories

| Category | Count | Source | Change Authority |
|----------|-------|--------|-----------------|
| Stable physical agent prompts | 7 | agents.py `_stable_prompt()` | Owner + CCD |
| Production virtual agent prompts | 10 | agents.py `_production_prompt()` | Owner + CCD |
| Review virtual agent prompts | 9 | agents.py `_review_prompt()` | Owner + CCD |
| Pipeline prompt constants | 2 | pipeline.py | Owner + CCD |
| Domain template instructions | 3 | domain_templates.py | Owner + CCD |

## Writer Agent Prompt Hardening

The following constraints are frozen in the prompt contracts:

1. Writer MUST obey claim_support_matrix support levels
2. Writer MUST obey writer_conclusion_constraints (allowed/forbidden phrases)
3. Writer CANNOT write favourable benefit-risk unless allowed by BR policy
4. Writer CANNOT use cross-domain template text (domain-specific templates enforced)
5. Writer CANNOT write audit artifact/internal language into CER body
6. QA MUST check body content (domain, evidence, cleanliness), not just structure

## Change Log

| Date | Change | Hash Before | Hash After | Authorized By |
|------|--------|-------------|------------|---------------|
| 2026-05-15 | Initial freeze PROMPT_PACK_V1 | — | See manifest | CCD (Phase 2B) |
