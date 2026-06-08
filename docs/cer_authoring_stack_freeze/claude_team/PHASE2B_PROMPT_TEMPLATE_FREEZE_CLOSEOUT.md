# PHASE 2B CLOSEOUT — Prompt + Template Freeze

> Claude Code | 2026-05-15

## Status: PASS

## What was done

### Prompt extraction

- 32 runtime prompts extracted from actual code (not manual docs)
- Sources: `agents.py` (_stable_prompt, _production_prompt, _review_prompt), `pipeline.py` (writer instruction constants), `domain_templates.py` (domain-specific writer instructions)
- Each prompt SHA-256 hashed (first 16 hex chars) for change tracking
- Written to `PROMPT_PACK_V1/` with 32 `.txt` files

### Prompt categories extracted

| Category | Count | Examples |
|----------|-------|---------|
| Stable 1+6 physical agent prompts | 7 | cer-authoring-lead-agent, cer-writer-agent, qa-review-agent, evidence-agent, methodology-sota-agent, intake-profile-claim-agent, risk-equivalence-gspr-agent |
| Production virtual agent prompts | 10 | authoring-cer-writer, authoring-claim-pico-builder, authoring-literature-searcher, authoring-evidence-appraiser, authoring-sota-analyst, etc. |
| Review virtual agent prompts | 9 | authoring-evidence-integrity-reviewer, authoring-final-gate-closure, etc. |
| Pipeline prompt constants | 2 | writer_conclusion_instruction, cross_evidence_writer_instruction |
| Domain template instructions | 3 | cardiac_stabilizer, plasma_electrode, imaging_software |

### Prompt contracts hardened

- Writer must obey claim_support_matrix
- Writer cannot write favourable benefit-risk unless allowed
- Writer cannot use cross-domain template text
- Writer cannot write audit artifact into CER body
- QA must check body content, not just structure

### Deliverables

- `PROMPT_PACK_V1/` — 32 prompt text files
- `PROMPT_HASH_MANIFEST.json` — hash manifest with metadata
- `PROMPT_CHANGE_CONTROL.md` — change control policy

## Next: Phase 2C — Model Selection + Template Pack
