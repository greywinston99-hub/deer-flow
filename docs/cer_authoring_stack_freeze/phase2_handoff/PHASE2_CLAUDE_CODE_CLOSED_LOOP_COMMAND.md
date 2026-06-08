# PHASE 2 CLOSED-LOOP EXECUTION COMMAND FOR CLAUDE CODE

> CCD | 2026-05-15

## Context

Phase 1 installed five guardrail gates. They reject contaminated output but the Writer's source-level generation problems remain unfixed — template contamination, IFU fact non-consumption, no model/prompt/template/toolchain freeze. Phase 2 fixes the source quality and freezes the entire stack as `CER_AUTHORING_STACK_V1.0_FREEZE`.

You are the implementer. CCD is controller (audits closeouts, does not implement). Owner authorizes final freeze.

## Required Reading (Before Starting)

1. `PHASE2_STACK_FREEZE_PLAN_V2.md` — complete Phase 2A0-2E plan
2. `PHASE2_ACCEPTANCE_CRITERIA_V2.md` — gate + human reviewability criteria
3. `PHASE2_EXECUTION_BOUNDARY_FOR_CLAUDE_CODE.md` — what you can and cannot do
4. `PHASE2_MASTER_STATUS_CLEANUP_NOTE.md` — status cleanup confirmation
5. `/docs/cer_authoring_writer_remediation/w0_handoff/` — Phase 1 gate specs, domain matrix, phrase policy, fixtures, quarantine policy

## Execution Loop

Do not stop between sub-phases. Continue through 2A0 → 2A → 2B → 2C → 2D → 2E. Only stop on HARD STOP conditions.

```
READ specs → PLAN → IMPLEMENT → TARGETED TESTS → FULL REGRESSION
→ REGENERATE/VERIFY → INSPECT OUTPUTS → REPAIR IF FAILED
→ RERUN → CONTINUE → until PHASE2_STACK_FREEZE_PASS or HARD STOP
```

## Phase 2A0 — Status Cleanup

- Read `PROJECT_MASTER_STATUS.md`. Confirm no stale Codex/Phase 4/old Phase 0 active references.
- Confirm W0 handoff readable at `/docs/cer_authoring_writer_remediation/w0_handoff/`.
- Confirm contaminated outputs quarantined at `/artifacts/cer_writer_quarantine/2026-05-15_contaminated_outputs/`.
- Write `PHASE2_MASTER_STATUS_CLEANUP_NOTE.md`.

## Phase 2A — Source Fixes

Template de-contamination:
- Prohibit reuse of historical CER body prose as template content.
- Domain-specific templates must be skeletons/instructions/source-grounded structures, not copied clinical prose.
- Generate per-domain template pack.

IFU fact consumption:
- Writer 2.1/2.2 reads from `document_structured_content` (source_type=IFU).
- Each field: extracted text, source anchor (document/page), extraction confidence.
- Fields with no IFU match: `IFU source does not contain this information`.

Unknown domain handling:
- Unknown `locked_domain` blocks Writer. Gate 1 may not be skipped.

## Phase 2B — Prompt Freeze

- Extract actual runtime prompts from code (not manually written ideal docs).
- Hash each prompt file.
- Generate `PROMPT_PACK_V1/` and `PROMPT_HASH_MANIFEST.json`.
- Write `PROMPT_CHANGE_CONTROL.md`.

## Phase 2C — Model A/B + Template Freeze

- Writer model A/B test: identical input, prompt, template, gates for all candidates.
- Score on: domain consistency, evidence consistency, IFU usage, internal language leakage, section completeness, professional expression, gate pass rate, repeatability.
- Domain-specific template pack generation.
- Write `WRITER_MODEL_SELECTION_REPORT.md`, `MODEL_ROUTING_POLICY.md`, `MODEL_FALLBACK_POLICY.md`.
- Write `CER_TEMPLATE_PACK_V1/`, `DOMAIN_TEMPLATE_BOUNDARY_MATRIX.xlsx`, `TEMPLATE_SOURCE_AND_ALLOWED_USE_LEDGER.md`.

## Phase 2D — Agent / Skill / Toolchain Freeze

Agent: `AGENT_TEAM_RUNTIME_INVENTORY.md` (what actually runs) + `AGENT_TEAM_SPEC_V1.md` (target contract). Do not document aspirational agents as running.

Skills: `CER_AUTHORING_SKILL_REGISTRY_V1.md` + `SKILL_INPUT_OUTPUT_CONTRACTS.md`.

Toolchain: `CER_AUTHORING_TOOLCHAIN_FREEZE_V1.md` + `PARSER_ROUTING_POLICY.md` + `RETRIEVAL_TOOL_POLICY.md` + `ARTIFACT_OUTPUT_CONTRACT.md`. Include external access status (MCP, PubMed, PMC, Europe PMC, CT.gov, Embase, ScienceDirect, paywall policy).

## Phase 2E — Frozen Stack Verification

- Regenerate three contaminated pilot CERs under frozen stack.
- All 5 gates must PASS on all three reports.
- Human reviewability rubric must PASS (from `PHASE2_ACCEPTANCE_CRITERIA_V2.md`).
- Full regression ≥284 tests PASS.
- graph/gates/agents zero diff.
- Do not claim Pilot ready.

## State Tracking

Maintain:
- `LOOP_STATE.json` — current phase, status, repair round, stop reason
- `LAST_SUCCESSFUL_CHECKPOINT` — last completed sub-phase
- `RESUME_COMMAND.md` — how to resume if interrupted
- `changed_files.txt` — all files modified
- `targeted_test_results.txt` — per-phase targeted test output
- `full_regression_result.txt` — full test suite output
- `forbidden_files_diff_check.txt` — graph/gates/agents diff verification

## HARD STOP Conditions

- 284 tests fail at any point
- graph.py / gates.py / agents.py modified
- EI Core _ei_* semantics modified
- Gate-failed report written to release/final/customer-facing output
- Model switched before gate verification
- Unknown domain allowed past Gate 1

## Allowed Final Status Labels

Only these three:
- `PHASE2_STACK_FREEZE_PASS`
- `PHASE2_STACK_FREEZE_REWORK_REQUIRED`
- `PHASE2_STACK_FREEZE_BLOCKED_OWNER_DECISION_REQUIRED`

---

*CCD 签发：2026-05-15*
