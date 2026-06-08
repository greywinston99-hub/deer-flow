# Phase 2 v2 — CER Authoring Stack V1.0 Freeze

> CCD | 2026-05-15 | Revised per owner review

## Phase 2A0: Status / Handoff / Output Hygiene

**Before any implementation**, clean the project status landscape.

Clean `PROJECT_MASTER_STATUS.md`. Remove or archive stale active sections referencing Codex, Phase 4, old Phase 0. Current active truth: Phase 1 guardrails PASS. Writer source quality not fixed. Phase 2 stack freeze pending. Claude Code is implementer. CCD is controller. Pilot not authorized.

Confirm contaminated outputs quarantined in `/artifacts/cer_writer_quarantine/2026-05-15_contaminated_outputs/`. Confirm W0 handoff package + Phase 2 plan readable by Claude Code at `/docs/cer_authoring_writer_remediation/w0_handoff/`.

Output:
- `PROJECT_MASTER_STATUS.md` (cleaned)
- `PHASE2_MASTER_STATUS_CLEANUP_NOTE.md` — what was removed, what was kept, why

## Phase 2A: Source Fixes (Template + IFU)

### Template De-Contamination

Historical CER body prose from any prior project (CAL-001 or other) is prohibited as template content. Templates must be: section skeletons with field placeholders, source-grounded section structures that reference project-specific data, instructions for generation. Never copied clinical prose from another device.

Domain-specific templates: cardiac stabilizer, orthopedic RF plasma electrode, imaging software, PADN ablation catheter. Each domain has skeleton + field mapping. No shared clinical text. No cross-domain template fragments.

### IFU Fact Consumption

Writer 2.1/2.2 fields read from `document_structured_content` (source_type=IFU) using field-to-section mapping. Each field gets: extracted text, source anchor (document/page), extraction confidence. Fields with no IFU match remain empty with explicit `IFU source does not contain this information` — not `Not extracted from IFU source text`.

### Unknown Domain Handling

Unknown `locked_domain` (no matching Domain Term Matrix entry) must block Writer. Gate 1 may not be skipped. Writer must request human domain definition before proceeding. No fallback to generic template.

## Phase 2B: Prompt + Model Hardening

### Prompts First, Model Second

Extract and hash runtime prompts (actual compiled prompts from code, not manually rewritten documentation) before any model A/B testing. Prompt pack must reflect what agents actually receive at runtime. Options: extract from `agents.py` subagent config `generate_system_prompt()` calls; extract from `pipeline.py` prompt construction functions.

### Model A/B Testing

All model candidates receive identical input, prompt, template, and gate configuration. Scored on: domain consistency, evidence consistency, language quality, section completeness. Selection documented with scores and rationale. Model switch only after gate verification confirms no regression.

## Phase 2B Outputs

- `PROMPT_PACK_V1/` — actual runtime prompts, hashed
- `PROMPT_HASH_MANIFEST.json`
- `PROMPT_CHANGE_CONTROL.md`
- `WRITER_MODEL_SELECTION_REPORT.md` — A/B results + selection
- `MODEL_ROUTING_POLICY.md`
- `MODEL_FALLBACK_POLICY.md`

## Phase 2C: Formal Freeze

### Agent Teams: Runtime Inventory + Target Contract

Split into two documents. `AGENT_TEAM_RUNTIME_INVENTORY.md` documents what actually runs now — 6 physical subagents as configured in `agents.py`, their actual model assignments, actual input/output. `AGENT_TEAM_SPEC_V1.md` defines target contract — the 10-agent architecture with explicit per-agent contracts. Do not document aspirational agents as if they already run.

### Skills Freeze

11 skills registered in `CER_AUTHORING_SKILL_REGISTRY_V1.md` with scope, inputs, outputs, forbidden behavior, human gate, acceptance criteria. `SKILL_INPUT_OUTPUT_CONTRACTS.md` defines cross-skill data flow.

### Toolchain Freeze

Document and version-lock all tools. Include external access status and fallback policies for every external dependency: MCP server status, PubMed direct API, PMC, Europe PMC, CT.gov, Embase (unavailable), ScienceDirect (unavailable), paywall/manual export policy. Include artifact routing: output, quarantine, release candidate, audit-only body separation.

## Phase 2C Outputs

Agent: `AGENT_TEAM_RUNTIME_INVENTORY.md`, `AGENT_TEAM_SPEC_V1.md`, `AGENT_RESPONSIBILITY_MATRIX.xlsx`, `AGENT_HANDOFF_CONTRACTS.md`
Skills: `CER_AUTHORING_SKILL_REGISTRY_V1.md`, `SKILL_INPUT_OUTPUT_CONTRACTS.md`
Model: `MODEL_ROUTING_POLICY.md`, `MODEL_FALLBACK_POLICY.md`
Toolchain: `CER_AUTHORING_TOOLCHAIN_FREEZE_V1.md`, `PARSER_ROUTING_POLICY.md`, `RETRIEVAL_TOOL_POLICY.md`, `ARTIFACT_OUTPUT_CONTRACT.md`
Template: `CER_TEMPLATE_PACK_V1/`, `DOMAIN_TEMPLATE_BOUNDARY_MATRIX.xlsx`, `TEMPLATE_SOURCE_AND_ALLOWED_USE_LEDGER.md`

## Human Reviewability Rubric

Phase 2 acceptance cannot be only gates pass. Regenerated pilot reports must satisfy reviewer-facing criteria:

- Device description source-grounded: every 2.1 field has source anchor and extraction confidence
- Intended purpose coherent: 2.2 text matches locked device identity, no cross-domain terms
- SOTA domain correct: 3.x clinical field matches device domain, no urology in cardiac, no cardiac in orthopedic
- Evidence applicability explained: each claim's evidence basis is explicit, not template boilerplate
- Conclusion respects claim constraints: Summary/Chapter 5 language consistent with claim_support_matrix
- No template shell leakage: no workflow explanation text in CER body (no "should be evaluated", no "refer to IFU")
- No internal language: zero Claude/DeerFlow/MCP/not_allowed/score strings in CER body

Regenerated reports must be human-reviewable — a professional reviewer can read and assess clinical validity without first filtering out system artifacts.

## Final Acceptance

`CER_AUTHORING_STACK_V1.0_FREEZE` may only be declared when:

- PROJECT_MASTER_STATUS is clean, no stale Codex/old-route references remain
- Phase 2A source fixes pass: templates de-contaminated, IFU facts populated, unknown domain blocks Writer
- Phase 2B prompts extracted + hashed, model A/B completed with documented rationale
- Phase 2C formal freeze: all agent/skill/model/toolchain/template docs produced
- Three regenerated pilot CERs pass all 5 gates
- Human reviewability rubric passes on all three reports
- graph/gates/agents zero diff (all phases)
- Full regression passes (≥284 tests)
- CCD closeout confirms no stale status remains

---

*CCD 签发：2026-05-15 | v2 Revised*
