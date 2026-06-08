# BIGDP2026.6 — Decision Ledger

**Purpose:** Record all key architectural and strategic decisions for the BIGDP2026.6 upgrade.
**Format:** Each entry has: Decision, Rationale, Evidence Reference, Alternatives Considered, Date.

---

## D-001: Start with Master Plan, Not Direct Code Changes

**Decision:** Create a comprehensive master plan and acceptance checklist before writing any code.

**Rationale:**
The Evidence Pack (`00_EXECUTIVE_VERDICT.md`, `10_REPAIR_ROADMAP.md`) identified 38 discrete repair items across 4 priority levels. The Chinese expert review (`Comments审核发现.md`) identified 6 business logic errors and 4 upgrade directions that go beyond simple bug fixes.

Direct code patching without a master plan would risk:
- Fixing symptoms while missing the root cause (placeholder gate logic, missing expert reasoning layer)
- Introducing regressions in the complex 42-node DAG
- Inconsistent fixes across `graph.py` (122KB), `gates.py` (193KB), and `pipeline.py` (1.4MB)
- No shared understanding of what "done" means

**Evidence:** `00_EXECUTIVE_VERDICT.md` — "The system is not production-ready for unsupervised CER generation until 4 items are addressed"; `Comments审核发现.md` §1 — "先修 P0/P1。否则跑更多项目只会重复暴露同样问题"

**Alternatives Considered:**
- Direct code patching of P0 items only — rejected because P0 fixes alone don't address the expert reasoning gap
- Running full CER pipeline first to gather more data — rejected because Evidence Pack already has code-confirmed findings

**Date:** 2026-06-07

---

## D-002: P0 Safety Fixes First, Before Any Feature Work

**Decision:** Phase 1 addresses only 4 P0 runtime safety defects before any new features or ledgers.

**Rationale:**
The P0 defects (`05_BUSINESS_LOGIC_GAP_REGISTER.csv` BLG-002, BLG-004, BLG-001; `06_CODE_DEBT_REGISTER.csv` CD-004) make the system unreliable at runtime:
- G46 can release Writer without verifying evidence links (downgrade bug)
- HC-01 human rework is silently dropped (empty REWORK_TARGETS)
- Spiral retrieval ceiling is ambiguous (3 vs 5 doc-code conflict)
- Event Bus fallback can duplicate evidence

Adding new ledgers or gate logic on top of these defects would compound the unreliability. The system must be "hard" at its critical control points before we add expert reasoning layers.

**Evidence:** `03_GATE_AND_REWORK_AUDIT.md` — detailed code evidence for all 4 defects; `Comments审核发现.md` §3 — "第一阶段：修 P0，不碰大重构"

**Alternatives Considered:**
- Fix P0 and build ledgers in parallel — rejected: ledgers feed into gates; gates must be reliable before ledgers are useful
- Skip Event Bus fix (mark as P2) — rejected: `10_REPAIR_ROADMAP.md` classifies it as P0; evidence duplication is a production blocker

**Date:** 2026-06-07

---

## D-003: Three Expert Business Ledgers Are the Core Upgrade

**Decision:** Phase 2 creates 3 new formal artifacts (`CER_REASONING_LEDGER`, `IFU_CLAIM_EVOLUTION_LEDGER`, `BENCHMARK_DERIVATION_TRACE`) as the central upgrade from "process-type" to "expert-reasoning-type" CER.

**Rationale:**
The Chinese expert review (`Comments审核发现.md` §4) identified that the system follows the right process steps but lacks the judgment layer that a regulatory engineer applies at each step. Specifically:

1. **CER_REASONING_LEDGER** — encodes the engineer's judgment about claim classification, evidence support type, endpoint rationale, gap disposition, and conclusion strength. Currently none of this reasoning is captured in a structured artifact.

2. **IFU_CLAIM_EVOLUTION_LEDGER** — prevents the system from writing marketing-language IFU claims directly into CER conclusions. Tracks how each claim evolves from raw IFU text through classification, evidence support, and final CER expression. This addresses the real-world risk of over-claiming.

3. **BENCHMARK_DERIVATION_TRACE** — makes SOTA benchmark derivation auditable. Currently benchmarks are either hardcoded (2 domains) or empty. This ledger requires per-endpoint rationale: what studies were used, why the benchmark is acceptable, what alternatives were rejected.

These three ledgers together form the "expert reasoning layer" that sits between the DAG process flow and the Writer. The Writer should only write from these ledgers, not from raw evidence.

**Evidence:** `Comments审核发现.md` §4 升级方向一/二/三; `03_GATE_AND_REWORK_AUDIT.md` — G46 currently only has 3/9 real evaluators

**Alternatives Considered:**
- Keep ledgers as informal Markdown notes — rejected: structured JSON is required for gate consumption and export integrity
- Build only CER_REASONING_LEDGER and defer the other two — rejected: all three address orthogonal expert concerns; partial implementation doesn't close the reasoning gap
- Embed reasoning in existing artifacts (e.g., extend claim_evidence_matrix) — rejected: separate ledgers maintain clear separation of concerns and are independently validatable

**Date:** 2026-06-07

---

## D-004: Writer Must Be Constrained to Gate-Passed Package Only

**Decision:** The Claude Code Writer (cer-authoring-section-writer skill) must perform runtime assertions validating `CER_INPUT_PACKAGE.json` before writing any CER section. Refuse to write if the package is missing, G46 is not PASS, or any reference is unresolvable.

**Rationale:**
The DeerFlow side of the handoff contract is enforced by graph construction: the DAG ends at `cer_input_package_export` in default `claude_code` mode; Writer nodes are not registered (`graph.py:2360-2370`). But the Claude Code side is not enforced — the skill could theoretically write without reading the package.

The handoff audit (`04_WRITING_ENGINE_HANDOFF_AUDIT.md`) confirmed this risk: "Claude Code skill could write without reading the package, if the skill implementation does not enforce the contract."

The expert reviewer (`Comments审核发现.md` §2 错误 5) identified this as a business logic error: "Writer 不应该'自己找资料写'。Writer 只能写已经过 gate 的 claim、evidence、benchmark、BR、alignment。"

**Evidence:** `04_WRITING_ENGINE_HANDOFF_AUDIT.md` Risk 2; `Comments审核发现.md` §2 错误 5, §3 P2 项 9

**Alternatives Considered:**
- Trust the process flow (G46 PASS → export → Writer) — rejected: defense in depth; the Writer is an external process and must independently verify
- Sign the package with HMAC and verify signature — considered as optional enhancement (Phase 4); signature prevents tampering but doesn't verify content completeness

**Date:** 2026-06-07

---

## D-005: Review Feedback Remains Advisory-Only by Default

**Decision:** Review feedback backflow to Authoring (auto-rework based on Review findings) is NOT enabled by default. A `review_feedback_ingestion` node will be implemented behind a feature flag (disabled), with a documented SOP for human-mediated Review → Authoring feedback.

**Rationale:**
The system currently has Review as advisory-only (`graph.py:199-204`, confirmed in `05_BUSINESS_LOGIC_GAP_REGISTER.csv` BLG-010, BLG-011). The expert reviewer noted that Review should eventually become a closed loop but recommended feature-flagging it: "我建议后者，但先 feature flag disabled。不要一开始就自动改写。" (`Comments审核发现.md` §3 P2 项 10)

Auto-backflow carries regulatory risk: if the system automatically modifies claims or evidence assessments based on Review findings without human oversight, it could silently weaken or strengthen CER conclusions in ways an NB auditor would flag.

**Evidence:** `05_BUSINESS_LOGIC_GAP_REGISTER.csv` BLG-010; `Comments审核发现.md` §1C, §3 P2 项 10

**Alternatives Considered:**
- Full auto-backflow enabled immediately — rejected: regulatory risk; needs human oversight
- No backflow ever (keep purely advisory) — rejected: limits long-term system evolution; feature flag allows controlled experimentation

**Date:** 2026-06-07

---

## D-006: Deferrals — What Is NOT in Scope for BIGDP2026.6

The following items from the Repair Roadmap are explicitly DEFERRED:

| Item | Reason for Deferral |
|:---|:---|
| BLG-013 — Quick-Scan node timeout status (P3) | UX improvement; not blocking expert reasoning upgrade |
| BLG-014 — GSPR coverage check (A7) weak proxy (P2) | Will be addressed when G45 Alignment Gate is upgraded in Phase 3 |
| BLG-015 — V3.1 intermediate nodes lack gates (P2) | V3.1 chain restructuring planned for post-BIGDP2026.6 |
| BLG-016 — Domain keyword matching brittle (P2) | Addressed by device_profile rework fix (Phase 1) + manufacturer intake override already exists |
| BLG-017 — Intake intermediate states not API-visible (P2) | Intake UI upgrade is a separate project |
| BLG-019 — SOTA search before endpoint selection (P2) | Documented as by-design; redesign is a separate project |
| BLG-020 — RMF coverage threshold uniform (P2) | Configuration externalization in Phase 5 will address threshold configurability |
| CD-012 — Human gate decision idempotency (P1) | Not blocking expert reasoning; can be added post-release |
| CD-016 — Agent/state YAML tight coupling (P2) | Startup validation improvement; not blocking |
| P3 items (8 items from `10_REPAIR_ROADMAP.md` Phase 4) | Deferred to post-BIGDP2026.6 maintenance cycle |

**Rationale for deferrals:** The BIGDP2026.6 scope is already significant (7 phases, 114 checklist items). Including all 38 roadmap items would delay the expert reasoning upgrade by months. The deferred items are either: (a) not blocking the expert reasoning transformation, (b) addressed indirectly by a higher-priority fix in scope, or (c) belong to a separate project track.

**Date:** 2026-06-07

---

## D-007: Phase Execution Must Be Strictly Sequential

**Decision:** Phases 1-7 execute in strict order. No parallel phase execution.

**Rationale:**
Each phase produces artifacts that the next phase consumes:
- Phase 2 ledgers are consumed by Phase 3 gates
- Phase 3 hardened gates are consumed by Phase 4 handoff enforcement
- Phase 4 contract enforcement is consumed by Phase 5 generalization (benchmark config must be validated end-to-end through handoff)
- Phase 6 Review clarification depends on gate stability from Phase 3

Parallel execution would risk integration failures where downstream phases consume incomplete upstream artifacts.

**Exception:** Within Phase 1, the 4 P0 fixes are independent and can be executed in parallel (different code paths, different test files).

**Evidence:** Dependency graph in `10_REPAIR_ROADMAP.md` — shows independent clusters within P0 but sequential dependencies between priority levels.

**Date:** 2026-06-07

---

## D-008: BIGDP2026.6 ACCEPTED by Controller

**Decision:** BIGDP2026.6 upgrade is ACCEPTED. All 7 phases complete, Repair Sprint closed, 16/16 audit GAPs resolved, 500 tests pass.

**Rationale:**
The implementation is genuine at code level. P0 defects repaired. Expert reasoning is runtime-executable, not documentation-only. G46 is a hard gate (0 silent PASS). Claude Code handoff is contract-enforced. Expert Logic Pack (50 rules, 6 decision tables, 12 scenarios) is consumed by runtime via `expert_rule_loader.py`. 3 semantic proofs verified. Deploy script: 25/25 checks pass.

**Evidence:**
- `CONTROLLER_REVIEW_PACKAGE.md` — comprehensive evidence aggregation
- `deploy_verify.sh` — 25/25 PASS
- `pytest -q` — 500/500 pass
- 16/16 audit GAPs closed (GAP-001 through GAP-015 + GAP-007 verified already implemented)

**Conditions:** None. Unconditional ACCEPT.

**Next Steps (Controller):**
1. Schedule real project dry-run (Phase 7 post-acceptance)
2. Review 8 remaining deferred checklist items (J section — environment-dependent)
3. Tag release when dry-run confirms no regressions

**Date:** 2026-06-08

| ID | Decision | Date | Status |
|:---|:---|:---|:---|
| D-001 | Start with Master Plan, not direct code changes | 2026-06-07 | Active |
| D-002 | P0 safety fixes first, before feature work | 2026-06-07 | Active |
| D-003 | Three expert business ledgers are the core upgrade | 2026-06-07 | Active |
| D-004 | Writer constrained to gate-passed package only | 2026-06-07 | Active |
| D-005 | Review feedback remains advisory-only by default | 2026-06-07 | Active |
| D-006 | 10 items deferred (P2/P3); scope control | 2026-06-07 | Active |
| D-007 | Strictly sequential phase execution | 2026-06-07 | Active |
| D-008 | BIGDP2026.6 ACCEPTED by Controller | 2026-06-08 | Active |
| D-009 | BIGDP2026.6 GO — Release authorized | 2026-06-08 | **FINAL** |
