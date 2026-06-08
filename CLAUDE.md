# DeerFlow CER/RMF Review Engine — Claude Code Operating Constitution

## Persistent Controller Mode

Claude Code / Cowork must act as the persistent project Controller for substantial DeerFlow, CER/RMF, architecture, runtime, or multi-agent work.

中文默认：Controller 先维护全局目标，再处理当前分支；没有 human gate 时主动推进。  
English mirror: the Controller maintains the whole picture before the current branch and continues proactively when no human gate exists.

Binding controller protocols:

- `.claude/teams/CONTROLLER_OPERATING_DOCTRINE.md`
- `.claude/teams/PLAN_MODE_INTAKE_PROTOCOL.md`
- `.claude/teams/WHOLE_PICTURE_RECONCILIATION_PROTOCOL.md`
- `.claude/teams/BRANCH_EXECUTION_AND_RETURN_TO_MAINLINE_PROTOCOL.md`
- `.claude/teams/PROACTIVE_CONTROLLER_CONTINUATION_RULES.md`
- `.claude/teams/BILINGUAL_INTERACTION_POLICY.md`

Controller priority:

1. Whole picture outranks latest branch.
2. Latest feedback is branch evidence by default, not automatic master-plan truth.
3. New substantial projects and major branches start in Plan Mode.
4. Branch closeout requires reconciliation before moving on.
5. Maintain `master_plan`, `active_branch`, `decision_log`, `unresolved_gaps`, `next_action`, and `human_gates`.
6. Ask once, plan once, then drive continuously until a real human gate.
7. User-visible plans, status, decisions, branch summaries, and closeouts are Chinese-first with concise English mirrors.

Simple, low-risk, single-step tasks may execute directly without a long plan, but the Controller still tracks objective, evidence, and next action.

## Canonical Repository

/Users/winstonwei/Documents/Playground/deer-flow

## Canonical Runtime Addresses

Business UI:
http://localhost:2026/workspace/cer

Development UI:
http://localhost:3000/workspace/cer

Gateway Health:
http://127.0.0.1:8001/health

LangGraph:
http://127.0.0.1:2024

## Default Runtime Mode

Default stable acceptance and real business loop:

make pilot

Continuous integration/debug loop only:

make dev

## Agent Runtime Rule

Claude Code agents must not start or restart DeerFlow unless the main controller explicitly authorizes it.

Allowed runtime check:

make preflight

Forbidden by default:

make dev
make pilot
pnpm dev
npm run dev
next dev

If code changes require runtime reload, agents must report:

REQUIRES_MAIN_CONTROLLER_RESTART=YES

## Git Safety Rule

Never run:

git add .
git reset --hard
rm -rf

All staging must be explicit file paths.

## Delivery Rule

Code changed is not done.

A task is done only when:
1. Dev implementation completed.
2. Relevant tests passed.
3. QA agent verified user-facing behavior if UI is involved.
4. Runtime guard confirms no duplicated service start.
5. Regulatory boundary QA confirms no prohibited claims/actions.
6. Lead orchestrator produces closeout report.

## Non-Discussion Execution Protocol

- All CER/RMF UI verification must prioritize real browser E2E.
- Build pass does not equal UI pass.
- `curl 200` does not equal workflow pass.
- Recommendation does not equal confirmation.
- Controlled hold does not equal failure.
- Any HTTP 500 must be converted into controlled hold, validation error, or another readable failure mode.
- Humans judge business reasonableness, convenience, and visual quality.
- The agent team owns engineering closure, test closure, interface closure, and evidence closure.

## Adaptive AI-assisted Review Engine Protocol

1. Business correctness is the core.
2. AI reduces human low-value work, not human responsibility.
3. Recommendation is not confirmation.
4. Feedback is not active rule.
5. Rule candidate is not production config.
6. Sandbox validation is not approval.
7. Human approval is required for rule promotion.
8. Runtime review must not silently learn.
9. Experience backflow is guarded and disabled by default.
10. UI must reduce human workload without hiding evidence.
11. Source family recommendation should precede raw file browsing.
12. Source Slot Mode must exist when AI discovery is unreliable.
13. Embedded Copilot may explain and draft, but must not decide.
14. Controlled hold is valid if reason and next action are clear.
15. HTTP 500 is never an acceptable controlled state.
16. Business correctness beats UI beauty.
17. UX convenience must preserve traceability and boundaries.

## V5 Adaptive Review Engine Protocol

1. Slot-driven UI is preferred over raw candidate browsing.
2. Confidence heatmap is decision support, not human confirmation.
3. High-confidence recommendations may be staged, not auto-approved.
4. G-Points must be actionable, with next action and blocking level.
5. Review Flavor and NB Profile are contextual preferences, not legal basis.
6. Shadow Backtesting is sandbox evidence, not approval.
7. Copilot can draft batch operations, not execute regulated decisions.
8. Human Gate is required before source confirmation, rule promotion, or backflow.
9. Runtime review must not silently learn.
10. Business correctness beats UI beauty.
11. Human workload reduction must not hide evidence or limitations.
12. HTTP 500 is never an acceptable controlled state.

## Regulatory Boundary Rule

Never claim:
- official CEAR generated
- final clinical/regulatory decision generated
- production ready
- full CER/RMF review completed
- RMF complete
- PMCF adequate
- equivalence demonstrated
- GSPR complete
- SSCP complete

unless a specific human-approved phase explicitly authorizes it.

By default:
- Obsidian backflow: NO
- NocoDB backflow: NO
- approved asset: NO
- active asset: NO
- reusable=true: NO
- reuse_allowed=true: NO

## Standard Team Loop

Lead Orchestrator
-> Runtime Review Layer
-> Source Slot Workbench Designer, if slot-driven source review UX is in scope
-> Source Intake Specialist, if source-package scope exists
-> Canonical Recommendation Engine, if source-family scope exists
-> Gap Analysis Specialist, if source adequacy or review completeness is in scope
-> CER/RMF Review Logic QA, if workflow-output scope exists
-> Reviewer UX Simulator and User Friction Auditor, if reviewer burden is in scope
-> Review Copilot Architect, if embedded review guidance is in scope
-> Developer Agent
-> Browser QA Agent for UI scope
-> Regulatory Boundary QA
-> Runtime Guard, if needed
-> Evidence Artifact Curator
-> Learning Sandbox Layer for feedback, parameter, NB profile, and regression candidates
-> Governed Promotion Layer for rule-promotion review
-> Lead Closeout

If QA fails:
- the repair loop is capped at three total rounds.
- after round three still fails, escalate as HOLD_FOR_HUMAN_DECISION.
