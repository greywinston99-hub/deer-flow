# PHASE 2 TWO-AGENT REVIEW PROTOCOL

> CCD | 2026-05-15

## Roles

### Dev Agent (VS Code Claude Code — Implementation Window)

- Primary implementer. Can modify code. Can run tests. Can re-run pipeline. Can close loop until pass or hard stop.
- Reads all specs, plans, and handoff files.
- Writes implementation, tests, closeout files, LOOP_STATE, RESUME_COMMAND.
- Reads Review Agent challenge queue at each sub-phase closeout and responds to all active challenges before proceeding.

### Review Agent (VS Code Claude Code — Audit Window)

- Real-time auditor / challenger. Read-only by default.
- Does NOT modify code. Does NOT start new runs. Does NOT implement.
- Reads Dev Agent commits, diffs, test results, regenerated outputs.
- Writes challenge findings, stop-the-line notices, review closeout.
- Can escalate to CCD if Dev Agent does not respond to blocking challenge.

### CCD (Controller)

- Does not write code. Does not start Pilot.
- Audits final closeout after both agents complete their cycle.
- Issues final verdict.

## Allowed Writes per Agent

### Dev Agent
- Source code files (pipeline.py, writer_remediation/, tests, etc.)
- `changed_files.txt`, `targeted_test_results.txt`, `full_regression_result.txt`, `forbidden_files_diff_check.txt`
- `IMPLEMENTATION_LOOP_STATE.json`, `LAST_SUCCESSFUL_CHECKPOINT`, `RESUME_COMMAND.md`
- `DEV_PLAN.md`, `DEV_RESPONSE_TO_REVIEW.md`
- Phase closeout files

### Review Agent
- `REVIEW_FINDINGS.md`
- `REVIEW_CHALLENGE_QUEUE.md`
- `STOP_THE_LINE.md`
- `PHASE2_REVIEW_CLOSEOUT.md`

## Forbidden Writes

### Dev Agent
- `REVIEW_FINDINGS.md`, `REVIEW_CHALLENGE_QUEUE.md`, `STOP_THE_LINE.md` — these are Review Agent territory
- `PHASE2_REVIEW_CLOSEOUT.md`
- graph.py / gates.py / agents.py (unless owner authorizes)

### Review Agent
- Any source code file
- Any test file
- Any generated output or artifact
- LOOP_STATE, RESUME_COMMAND — these are Dev Agent territory

## Review Checkpoints

Review Agent performs audit at these checkpoints:
- After Phase 2A source fixes
- After Phase 2B prompt extraction
- After Phase 2C model A/B + templates
- After Phase 2D agent/skill/toolchain freeze
- After Phase 2E final verification

## Stop-the-Line Conditions

Review Agent may write `STOP_THE_LINE.md` with `status=ACTIVE` when:
- graph.py / gates.py / agents.py modified without owner authorization
- EI Core _ei_* semantics changed
- Gate-failed report written to release/final output
- Model switched before gate verification
- PRISM/Prompt/Template changes not hash-tracked
- IFU placeholder text still present after Phase 2A
- Forbidden terms still in regenerated CER body after Phase 2A
- Internal system language still in CER body after Phase 2B

When STOP_THE_LINE.md exists with status=ACTIVE, Dev Agent halts implementation. CCD or owner must resolve the stop before Dev Agent continues.

## Review Agent Output Format

`REVIEW_CHALLENGE_QUEUE.md` entries:
```
### CHG-###: [title]
Phase: [2A|2B|2C|2D|2E]
Severity: BLOCKING | HIGH | MEDIUM | LOW
Finding: [what was found]
Expected: [what should be]
Evidence: [file path or test output]
Status: OPEN | RESOLVED | ESCALATED
```

`REVIEW_FINDINGS.md` appends per checkpoint:
```
## Checkpoint: Phase [X] — [date]
Gate checks: [PASS/FAIL per gate]
Scope check: [compliant/deviation]
Quality checks: [findings summary]
```

## Dev Agent Response to Challenge

Dev Agent reads `REVIEW_CHALLENGE_QUEUE.md` at each sub-phase closeout. For each OPEN challenge:
- BLOCKING: must fix before proceeding. Write fix + resolution to `DEV_RESPONSE_TO_REVIEW.md`.
- HIGH: should fix. If not fixed, document rationale.
- MEDIUM/LOW: may defer with documented rationale.

Dev Agent updates challenge status to RESOLVED after fix. Review Agent verifies resolution at next checkpoint.

If Dev Agent disagrees with BLOCKING challenge, writes rationale to `DEV_RESPONSE_TO_REVIEW.md` and escalates to CCD.

## CCD Final Audit

When both agents complete and PHASE2_REVIEW_CLOSEOUT.md shows all challenges RESOLVED or ESCALATED, CCD audits final closeout and issues one of:
- `PHASE2_STACK_FREEZE_PASS`
- `PHASE2_STACK_FREEZE_REWORK_REQUIRED`
- `PHASE2_STACK_FREEZE_BLOCKED_OWNER_DECISION_REQUIRED`

---

*CCD 签发：2026-05-15*
