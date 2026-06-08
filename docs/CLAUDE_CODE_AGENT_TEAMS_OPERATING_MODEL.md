# Claude Code Agent Teams Operating Model

## Purpose

This repository uses Claude Code Agent Teams so DeerFlow CER/RMF work is delivered through an explicit role system instead of a single agent attempting end-to-end completion without independent verification.

## Agent Teams and Subagents

- Project-level subagents are role definitions. Each role has a stable mission, allowed actions, forbidden actions, required inputs and outputs, done criteria, escalation rules, and report format.
- Agent team playbooks are the collaboration protocol. They define who leads, who implements, who verifies, when repair loops are allowed, and when to stop for human review.
- Hooks are safety guardrails. They are used to block prohibited runtime starts and unsafe git commands before they execute.
- The adaptive review engine separates Runtime Review Layer, Learning Sandbox Layer, and Governed Promotion Layer so exploration does not silently become active runtime logic.
- V5 introduces slot-driven workbenches, confidence heatmaps, actionable gap paths, review-flavor sandboxing, and shadow backtesting as first-class coordination concepts.

## Operating principles

1. Do not let a single Claude Code instance directly declare delivery complete.
2. Every task must have a QA loop.
3. UI work is not done until user-visible behavior is checked.
4. Regulatory boundary checks are mandatory for CER/RMF-facing changes and outputs.
5. Runtime actions remain human-gated unless the main controller explicitly authorizes them.
6. Recommendations, feedback, and rule candidates are not confirmations or active config.
7. Adaptive learning stays sandboxed until human approval and regression evidence exist.
8. Slot-driven source review is preferred over raw-file-first browsing.
9. Confidence heatmaps guide attention but do not approve sources.

## Team pattern used in DeerFlow

- Lead orchestrator decomposes and decides scope.
- Source Slot Workbench Designer defines the primary slot-based review surface.
- Source intake, canonical recommendation, gap analysis, and logic QA handle review correctness before implementation claims.
- Reviewer UX roles and review copilot design reduce human low-value work without hiding evidence.
- Confidence heatmaps and actionable gap paths focus reviewer attention on the right unresolved decisions.
- Specialized dev agent implements within bounded ownership.
- Browser QA validates from the real user perspective.
- Regulatory boundary QA validates wording, scope, recommendation traceability, and asset/backflow boundaries.
- Runtime guard validates runtime safety when needed.
- Learning sandbox roles capture feedback, parameter candidates, NB profile candidates, review flavors, and regression scenarios without activating them.
- Evidence curator organizes the record for closeout and future review.

## Why this model exists

The current DeerFlow pain points are not only code quality issues. They are coordination issues:
- code can look complete while UI closure is still broken
- QA and dev handoff can fall back to manual coordination
- done criteria can be skipped
- agents can accidentally start duplicate runtimes
- limited review work can drift into prohibited regulatory claims
- reviewer workload can stay too high even when AI assistance exists
- adaptive ideas can leak into runtime behavior without governance if not explicitly separated

The agent team system addresses those coordination failures directly.
