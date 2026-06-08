# Claude Code Done Criteria

## UI done criteria

- Implementation completed in the intended frontend scope.
- Relevant lint, build, or type checks passed or were explicitly blocked.
- Browser E2E verified the user-visible behavior.
- Screenshot, trace, console log, and network log evidence were captured or any missing evidence was explicitly treated as non-pass.
- Slot-driven review is preferred over raw-file-first browsing when source review UX is involved.
- Breadcrumb, loading, error, and success states were checked where applicable.
- Regulatory boundary QA passed.
- Reviewer workload was not reduced by hiding evidence or limitations.

## Backend done criteria

- Relevant routes, schemas, or contracts are updated.
- Import smoke passes for touched modules.
- Relevant `pytest` or TestClient coverage passes.
- API contract impact is documented.
- Regulatory boundary QA passed when responses, prompts, or artifacts are affected.

## Runtime done criteria

- `make preflight` completed and result recorded.
- Port and service ownership checks were performed.
- Duplicate runtime risk was evaluated.
- Restart need was explicitly stated.

## Regulatory done criteria

- Prohibited claim scan completed.
- Unauthorized backflow scan completed.
- Asset status boundaries checked.
- Human-gated review language preserved.
- Recommendation traceability preserved.
- Candidate experience and sandbox outputs were kept out of active runtime rule status.

## Adaptive review done criteria

- Runtime review behavior did not silently learn from current-session feedback.
- Feedback, rule candidates, parameter candidates, and NB profile candidates stayed in sandbox scope.
- Human approval is still required before any promotion to active config.
- Source Slot Mode fallback exists when AI discovery is unreliable.
- Embedded copilot explains and drafts, but does not decide.
- Confidence heatmaps remain decision support, not confirmation.
- G-Points become actionable paths with blocking level and next action.
- Shadow backtesting exists for rule and parameter candidates.

## Baseline done criteria

- Working tree changes are classified.
- Explicit include and exclude sets are documented.
- Artifact handling is documented.
- Unsafe staging patterns are not used.
- No commit happens without explicit authorization.
