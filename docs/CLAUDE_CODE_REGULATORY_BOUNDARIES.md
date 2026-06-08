# Claude Code Regulatory Boundaries

## Prohibited claims

Do not claim:
- official CEAR generated
- final clinical/regulatory decision generated
- production ready
- full CER/RMF review completed
- RMF complete
- PMCF adequate
- equivalence demonstrated
- GSPR complete
- SSCP complete

## Unauthorized actions

By default, do not perform or claim:
- Obsidian backflow
- NocoDB backflow
- approved asset
- active asset
- reusable=true
- reuse_allowed=true

## Limited review language rules

- Use language consistent with limited review, workflow validation, or bounded verification.
- Keep human review as the gate for official or final regulatory judgment.
- UI copy, prompts, docs, and artifacts must all follow the same boundary language.
- Controlled hold is valid when the reason and next action are explicit.
- HTTP 500 is never an acceptable controlled state.

## Adaptive governance rules

- Every recommendation must be traceable to current evidence, explicit rule logic, parameter logic, or approved experience.
- Feedback is evidence, not active rule.
- Rule candidates are not production config.
- Sandbox validation is not approval.
- Shadow backtesting is not approval.
- Adaptive learning must not bypass the human gate.
- UX simplification must not hide evidence, limitations, or hold reasons.
- Source Slot Mode is the fallback when AI discovery confidence is too low.
- High confidence is not automatic confirmation.
- NB profiles and review flavors are contextual preferences, not legal basis.
- Copilot batch drafts are not executed decisions.

## Human gate required

- No agent may convert workflow validation into an official clinical or regulatory conclusion.
- If wording is ambiguous, stop and escalate for human review.
- Boundary QA is mandatory before closeout when CER/RMF-facing wording or artifacts are involved.
