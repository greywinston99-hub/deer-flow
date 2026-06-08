# Claude Code Team Workflows

## UI fix workflow

1. Lead classifies the issue as UI closure work.
2. `frontend-closure-dev` implements the smallest scoped fix.
3. `qa-browser-dogfood` validates user-visible behavior with real browser E2E evidence.
4. If QA fails, the repair loop may continue up to three total rounds.
5. `regulatory-boundary-qa` validates non-claims, traceability, and no-backflow boundaries.
6. Lead issues final closeout.

## Backend fix workflow

1. Lead classifies the issue as backend/API work.
2. `backend-api-dev` updates routes, schemas, or tests.
3. Relevant `pytest` or TestClient checks run.
4. `regulatory-boundary-qa` validates output and prompt boundaries.
5. Lead issues final closeout.

## Runtime issue workflow

1. Lead classifies the issue as runtime.
2. `runtime-guard` runs `make preflight` and inspects ports/processes.
3. Results are reported without restarting services.
4. If restart is needed, report `REQUIRES_MAIN_CONTROLLER_RESTART=YES`.
5. Lead issues final closeout or escalation.

## Complete project run workflow

1. Lead starts the observation workflow.
2. `runtime-guard` confirms runtime safety and duplicate-runtime status.
3. `qa-browser-dogfood` observes the 2026 business UI workflow.
4. `regulatory-boundary-qa` validates claims and boundaries.
5. `evidence-artifact-curator` packages the report set.
6. Lead issues final closeout.

## Adaptive review engine workflow

1. Lead separates Runtime Review Layer, Learning Sandbox Layer, and Governed Promotion Layer.
2. `source-slot-workbench-designer` makes slot-driven review the primary UX target and keeps raw-candidate audit as secondary evidence.
3. `source-intake-specialist`, `canonical-recommendation-engine`, `gap-analysis-specialist`, and `cer-rmf-review-logic-qa` handle review correctness.
4. `canonical-recommendation-engine` emits a confidence heatmap and `gap-analysis-specialist` converts G-Points into actionable paths.
5. `reviewer-ux-simulator` and `user-friction-auditor` evaluate reviewer burden and whether Source Slot Mode is needed.
6. `review-copilot-architect` defines embedded copilot behavior that explains and drafts but does not decide.
7. `frontend-closure-dev` and `backend-api-dev` implement bounded changes when needed.
8. `qa-browser-dogfood` executes real browser E2E.
9. `regulatory-boundary-qa` verifies non-claims, recommendation traceability, confidence misuse, profile misuse, and adaptive governance boundaries.
10. `feedback-learning-loopback`, `business-parameter-tuner`, `adaptive-logic-architect`, `notified-body-profile-curator`, and `scenario-regression-curator` capture sandbox-only learning outputs.
11. `adaptive-logic-architect` and `rule-promotion-governor` require shadow backtesting before any promotion path progresses.
12. `adaptive-experience-curator` prepares draft experience assets without executing backflow.
13. `product-readiness-governor` assesses readiness for human expert use without claiming production ready.
14. Lead issues final closeout or hold decision.

## Baseline freeze workflow

1. Lead classifies the task as baseline or git hygiene.
2. `git-baseline-guardian` classifies tracked and untracked changes.
3. `evidence-artifact-curator` recommends artifact inclusion and archive handling if needed.
4. Lead provides an explicit include set and exclusion set.
5. No commit occurs without explicit human authorization.
