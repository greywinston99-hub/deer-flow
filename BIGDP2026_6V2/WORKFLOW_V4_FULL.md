/goal BIGDP2026.6V_2 全链路闭环升级 — 从 Owner 资产验证、能力吸收、DeerFlow 代码升级、测试修复、真实项目验证，到专家能力评分闭环。目标是尽最大可能达到系统内专家能力 100/100；但必须根据资产可用性判断是 Full Validation Path 还是 Capped Validation Path，不允许资产不足时假装 100/100。

/workflow BIGDP2026.6V_2-full-closed-loop-execution-v4

Project root: `/Users/winstonwei/Documents/Playground/deer-flow`

You are responsible for executing BIGDP2026.6V_2 end-to-end: resource verification, asset absorption, DeerFlow code upgrade, tests and repair loops, knowledge/rule/fixture/runtime integration, real or representative project validation, Writer semantic QA, final expert capability scorecard, and closeout or blocker report. Do not fake closure. Do not claim 100/100 unless strict Path A criteria are met.

---

# 0. Core definitions

## 0.1 Meaning of 100/100

100/100 means internal system maturity. Allowed only if every hard acceptance defect has: source material or valid gold label, rule or SOP, fixture, semantic test, runtime landing, gate/validator/writer QA, passing tests, real or representative project validation, no P0/P1/P2 residual gap, no DOC_ONLY/NOT_RUN/UNKNOWN item. If any item lacks runtime/test/validation/asset evidence, do not claim 100/100.

## 0.2 Hard acceptance defect classes

Close or honestly asset-block these:

- DC-1 Retrieval recall gap
- DC-2 Retrieval irreproducibility / missing query string
- DC-3 Small sample / N<10 literature incorrectly included
- DC-4 Data not traceable to PMID / source
- DC-5 Full text unavailable but concrete data generated
- DC-6 Endpoint semantic error: device abandonment / compression / tourniquet not automatically AE
- DC-7 Comparator benchmark range / CI / source missing
- DC-8 Context / cross-section inconsistency
- DC-9 SOTA accounting inconsistency
- DC-10 Denominator / subgroup misuse
- DC-11 Writer output exceeds evidence strength / ledger constraints

Each DC classified as: FULLY_CLOSED / CLOSED_WITH_DERIVED_VALIDATION / CLOSED_WITH_HEURISTIC_VALIDATION / CLOSED_WITH_SYNTHETIC_FIXTURE_ONLY / ASSET_BLOCKED / ENV_BLOCKED / DOMAIN_DECISION_BLOCKED / NOT_IMPLEMENTED. Only FULLY_CLOSED supports full score.

---

# 1. Authorization and safety boundary

Owner authorizes local read-only scanning of `/Users/winstonwei/CER-RAG/Source/项目文件夹/`, `/Users/winstonwei/CER-RAG/`, `/Users/winstonwei/Documents/Playground/deer-flow/`. Owner authorizes creation of manifests, indexes, reports, tests, and code changes inside `/Users/winstonwei/Documents/Playground/deer-flow/BIGDP2026_6V2/` and DeerFlow CER authoring runtime files when implementation begins.

Default resource mode: path-reference manifests. Do not copy customer project files unless explicit authorization exists. Do not copy locked NB/engineer feedback by default. Locked feedback may be read for calibration, defect mapping, fixture generation, validation. Locked feedback must never enter Writer input, CER_INPUT_PACKAGE, or final CER generation.

Do not: push, create PR, delete unrelated files, run destructive commands, upload confidential files, expand into unrelated Review v5/frontend/gateway, mark doc-only as PASS, count skipped tests as PASS, claim Owner approval not given.

---

# 2. Required files to read

Read existing V2 files: `BIGDP2026_6V2_MASTER_PLAN.md`, `BIGDP2026_6V2_ASSET_PREPARATION_SPEC.md`, `BIGDP2026_6V2_ENGINEER_FEEDBACK_DEFECT_MAP.md`, `BIGDP2026_6V2_12_STAGE_BATCH_PLAN.md`, `BIGDP2026_6V2_ABSORPTION_WORKFLOW.md`, `BIGDP2026_6V2_STAGE_INTERFACE_MAP.md`, `BIGDP2026_6V2_SKILL_AND_TOOL_GAP_PLAN.md`, `BIGDP2026_6V2_ACCEPTANCE_CHECKLIST.md`, `BIGDP2026_6V2_PHASE_STATUS.md`. Read resource planning files: `RESOURCE_SELECTION_STRATEGY.md`, `CANDIDATE_PROJECT_INVENTORY.csv`, `ENGINEER_FEEDBACK_COVERAGE_TARGETS.md`, `RESOURCE_GAP_QUESTIONS_FOR_OWNER.md`, `RECOMMENDED_RESOURCE_SET.md`, `NEXT_CONTROLLER_ACTION.md`. Read absorption guide: `OWNER_EXTRACTION_SPEC.md`, `ABSORPTION_EXECUTION_GUIDE.md`.

Read latest BIGDP2026.6 audit at `BIGDP2026_6/audits/CURRENT_STATE_DEEP_AUDIT_V2_<latest>/` — resolve by listing, sorting by timestamp, using most recently modified, documenting in preflight. If absent, mark NOT_FOUND, do not block.

---

# 3. State authority

Maintain `BIGDP2026_6V2_LOOP_STATE.md` (execution authority): current mode, batch, step, validation path, score, last checkpoint, assets ready/missing, authorization, code changes, tests run, failures, repair loops, blockers, next action, resume command. Maintain `BIGDP2026_6V2_PHASE_STATUS.md` (acceptance authority): batch/phase status only. If conflict: LOOP_STATE controls execution, repair PHASE_STATUS before closeout. Also maintain `BIGDP2026_6V2_DECISION_LEDGER.md`. Create missing files.

---

# 4. Execution modes

Sequential: Controller/Preflight → Resource Operator → Absorption Designer → Implementer → Auditor/Validator → Closeout. Do not enter Implementer Mode until Resource Operator and Absorption Designer reach PASS or acceptable fallback.

---

# 5. Validation path selection

Create `VALIDATION_PATH_DECISION.md` — PRELIMINARY in Phase 0, updated to FINAL_FOR_IMPLEMENTATION after Batch A.

**Path A — Full Expert Validation**: All 12 Core Validation Assets READY. Max 100/100.

**Path B — Capped Expert Validation**: Any asset missing. Implement deterministic infrastructure, heuristic rules where expert labels absent (mark HEURISTIC_ONLY), synthetic/injected fixture validation, cap score via SCORE_CAP_RULES, generate Owner/Domain Expert request list. Cannot claim 100/100.

---

# 6. Score cap rules

Create `SCORE_CAP_RULES.md`:

| Score Area | Pts | Full-score requirement | Score cap if missing |
|:---|---:|---|:---|
| Asset readiness and locked-boundary control | 10 | Assets classified AND Writer boundary enforced AND locked feedback policy proven | max 6 if auth incomplete; max 4 if boundary not proven |
| Retrieval recall and reproducibility | 10 | (Manual Search Gold OR equivalent recall set) AND query provenance AND runtime test | max 5 without recall set; max 7 synthetic only |
| Screening exclusion reliability | 8 | Screening Gold Labels OR accepted expert rationale AND runtime tests | max 5 without gold/rationale; max 6 heuristic only |
| Fulltext availability policy | 8 | Fulltext Mapping AND policy tests | max 5 without mapping; max 6 synthetic only |
| Clinical fact source traceability | 12 | PMID verification data AND source anchor proof AND runtime validator | max 6 without verification; max 8 synthetic only |
| Denominator / subgroup correctness | 10 | Denominator Gold Labels OR accepted verification AND runtime validator | max 5 without gold/verification; max 7 heuristic only |
| Endpoint semantic correctness | 10 | Endpoint/AE Expert Labels OR engineer correction AND runtime classifier | max 6 without labels/correction; max 7 heuristic only |
| Comparator benchmark completeness | 8 | Comparator Gold Ranges AND source mapping AND runtime test | max 5 without ranges; max 6 synthetic only |
| SOTA accounting consistency | 8 | SOTA Gold Ledger OR reproducible artifact AND runtime reconciliation | max 5 without ledger/artifact; max 6 synthetic only |
| Claim-evidence semantic support | 6 | Support labels OR accepted NB-derived validation AND runtime test | max 4 without labels; max 5 heuristic only |
| Writer semantic consistency | 6 | Post-write on current-run OR representative output AND constraint mapping | max 3 synthetic prose; max 4 historical CER only |
| Real project / holdout validation | 4 | Real/representative validation completed AND artifacts generated | max 1 without validation; max 2 artifact-only |

No full points from documentation-only, heuristic-only, synthetic-only, or NOT_RUN evidence.

---

# 7. Asset dependency matrix

Create `ASSET_DEPENDENCY_MATRIX.csv`: defect_id, score_area, capability, required_asset, asset_status (READY/PARTIAL/NOT_FOUND/NEEDS_OWNER/NEEDS_DOMAIN_EXPERT/NOT_REQUIRED/UNKNOWN), source_path, fallback_allowed, fallback_type, full_score_allowed, max_score_if_missing, blocks_full_100, Owner_question, Domain_expert_question, last_updated_phase. Phase 0 framework with UNKNOWN; Batch A updates with scan. Golden missing must impact DC-1/3/4/6/7/9/10 + validation — not just validation score.

---

# 8. Expert label source policy

Create `EXPERT_LABEL_SOURCE_POLICY.md`. Closure levels: FULLY_CLOSED = Domain Expert label OR Engineer feedback correction with source evidence. CLOSED_WITH_DERIVED_VALIDATION = NB feedback + accepted revision OR accepted CER reverse-derived (requires documented source path, before/after, no conflicting evidence, non-training validation). HEURISTIC_ONLY = generalized rule without expert label. SYNTHETIC_ONLY = synthetic fixture only. ASSET_BLOCKED / DOMAIN_DECISION_BLOCKED.

---

# 9. Locked feedback use policy

Create `LOCKED_FEEDBACK_USE_POLICY.md`. Locked feedback may be used for calibration, rule induction, fixture generation, regression, evaluator design. Rules/thresholds/classifiers derived from locked feedback may enter runtime if generalized. Specific locked feedback content must NOT enter Writer input or CER_INPUT_PACKAGE. Every asset marked: WRITER_ALLOWED / CALIBRATION_ONLY / VALIDATION_ONLY / LOCKED_NO_WRITER / HOLDOUT_ONLY.

---

# 10. Writer QA architecture

Create `WRITER_QA_ARCHITECTURE_DECISION.md`. **Pre-write constraint layer**: DeerFlow package export / G46 / CER_INPUT_PACKAGE validation / Claude Code preflight — blocks unsupported claims, enforces conclusion_strength, blocks invalid packages. **Post-write validation layer**: Claude Code writer skill or post-generation validator — checks no conclusion exceeds ledger, no hidden numeric data, no denominator misuse, no endpoint contradiction, no SOTA inconsistency, no missing benchmark limitation. Writer output levels: Level 1 = current-run output (FULLY_CLOSED), Level 2 = historical output (DERIVED_VALIDATION), Level 3 = synthetic prose (SYNTHETIC_ONLY).

---

# 11. Golden Feedback fallback

Create `GOLDEN_FEEDBACK_FALLBACK_PLAN.md`. If Golden found: use as GOLDEN. If not: use best calibration + injected defects, mark unavailable, apply all score caps across affected areas, produce Owner request. Golden missing blocks 100/100 unless equivalent validated feedback project found.

---

# 12. Dry-run minimum input

Create `DRY_RUN_MINIMUM_INPUT_SPEC.md`. Package-level: IFU, claim source, evidence, search artifact, endpoint registry, clinical fact registry, benchmark trace. Full E2E: runnable authoring path, model/API, source inventory, search/retrieval, fulltext status, package export, writer output. If E2E unavailable: deterministic artifact-level validation, mark cap, do not claim full.

---

# 13. Phase 0 — Preflight and framework

## 13.1 Environment preflight

Create `00_PREFLIGHT_REPORT.md`: branch, git status, dirty tree, Python, pytest, CWD, V2 files present/missing, CSV readability, audit path, baseline test status, tool availability, blockers. Run baseline: `.venv/bin/python3 -m pytest backend/packages/harness/deerflow/runtime/cer_authoring/tests/ -q`. If missing venv/pytest: ENV_BLOCKED, try setup, do not skip. If tests fail: repair regression, rerun, do not continue until pass or blocker documented.

## 13.2 Planning repair

Repair: `CANDIDATE_PROJECT_INVENTORY.csv` must be pure CSV (no Markdown, create summary separately, verify pandas-readable). Status coherent: A0/A1/A2/A3/A4/Batch B/C/D/Final. CAND-001 = strongest candidate not confirmed Golden. Acceptance Checklist needs A0 Asset Readiness Gate. All proposed new gates/modules = PROPOSED_RUNTIME_LANDING. Create `00_PLAN_REPAIR_REPORT.md`.

## 13.3 Framework files

Create: `VALIDATION_PATH_DECISION.md` (PRELIMINARY), `ASSET_DEPENDENCY_MATRIX.csv` (UNKNOWN), `SCORE_CAP_RULES.md`, `EXPERT_LABEL_SOURCE_POLICY.md`, `LOCKED_FEEDBACK_USE_POLICY.md`, `WRITER_QA_ARCHITECTURE_DECISION.md`, `GOLDEN_FEEDBACK_FALLBACK_PLAN.md`, `DRY_RUN_MINIMUM_INPUT_SPEC.md`.

Phase 0 PASS: baseline pass or blocker documented, CSV readable, framework files created, path PRELIMINARY, LOOP_STATE updated. Checkpoint: `CHECKPOINT_00_PREFLIGHT_AND_FRAMEWORK.md`.

---

# 14. Batch A — Resource verification and absorption readiness

**A0 — Owner extraction already completed externally.** Owner extracted assets from 15–20 L1 projects per `OWNER_EXTRACTION_SPEC.md`. Assets in `assets/` directory. Claude Code does NOT re-scan 44-project directory — reads Owner-prepared assets. Excluded: A06_南驰 / iTClamp / 108.江苏南驰 (already absorbed; historical regression only; NOT calibration/holdout/new gold source). A1 below VERIFIES, not discovers.

## A1 — Asset verification and gap detection

Read Owner-extracted assets from `assets/`. Verify: all CSVs machine-readable, DC coverage quotas met (≥5 projects for DC-1/2/3/4/5/8/9; ≥6 for DC-6; ≥4 for DC-7/10/11). Run two-tier quality gate:

**Tier 1 — Structural (MUST pass before any absorption):** (1) CSV machine-readable (pandas); (2) all required columns present; (3) dataset_role present per row; (4) locked_status present per row; (5) writer_access_allowed present per row; (6) DC mapping present per row; (7) score_area mapping present per row; (8) no duplicate PMID/endpoint/claim; (9) holdout contamination = 0; (10) 南驰/iTClamp excluded from calibration/holdout.

**Tier 2 — Content (MUST pass before claiming DERIVED_VALIDATION or above):** (11) source_file_path non-empty AND file exists; (12) gold/expert rows: source_quote_or_anchor non-empty AND not `TO_BE_EXTRACTED`; (13) evidence_level is real value (not placeholder); (14) confidence is real value (not placeholder or "unknown" when source-verified).

**A1 result:** Tier 1 PASS + Tier 2 PASS → READY for full absorption. Tier 1 PASS + Tier 2 FAIL → PARTIAL; generate `assets/OWNER_CONTENT_FILL_CHECKLIST.md` (per gap: file, row, field, source PDF, action). Tier 1 FAIL → BLOCKED; fix CSV structure first.

Update `CANDIDATE_PROJECT_INVENTORY.csv` and `ASSET_READINESS_REGISTER.csv` with tiered results.

## A2 — Golden feedback discovery

Search for iTClamp/南驰/PMID 31539432/32209132/30635996/McKee/止血/止血带/缝线/缝钉. Create `GOLDEN_FEEDBACK_SOURCE_DISCOVERY.md`. If found: path-reference manifests. If not: `GOLDEN_FEEDBACK_SOURCE_NOT_FOUND.md` with Owner questions. Continue under Path B if fallback exists.

## A3 — Core asset readiness

Create `assets/ASSET_READINESS_REGISTER.csv` with 15 assets: Engineer Feedback, Real Project, Full-text/Clinical, Manual Search Gold, Screening Gold, Fulltext Mapping, PMID Verification, Denominator Gold, Endpoint/AE Labels, Comparator Gold, SOTA Gold, Claim-Evidence Labels, Writer Output, Regulatory Core, Endpoint/AE Labels (minimal). Each: asset_id, status, source_path, defects_covered, score_areas, locked_status, writer_access (default NO for feedback/labels), blocks_Path_A, caps_score, next_action.

## A4 — Update path decision

Update `VALIDATION_PATH_DECISION.md` PRELIMINARY→FINAL_FOR_IMPLEMENTATION. After Owner extraction + A1 verification: if ≥8 Core Assets READY → re-evaluate Path A; if 南驰 excluded → Path B confirmed; if DC quotas met → absorption readiness increased. Update `ASSET_DEPENDENCY_MATRIX.csv`, `SCORE_CAP_RULES.md`, `EXPERT_LABEL_SOURCE_POLICY.md`, `GOLDEN_FEEDBACK_FALLBACK_PLAN.md`, `DRY_RUN_MINIMUM_INPUT_SPEC.md`.

## A5 — Defect-to-capability map

Create `absorption/DEFECT_TO_CAPABILITY_MAP.csv`: for DC-1 through DC-11 — expert behavior, BIGDP2026.6 coverage, V2 planning coverage, required asset, asset status, rule candidate, fixture candidate, semantic test candidate, architecture fit target, runtime landing proposal, writer QA proposal, validation method, hard acceptance, closure status, score impact. Create `absorption/ABSORPTION_READY_REPORT.md`.

## A6 — Asset-to-Absorption Contract

Create `absorption/ASSET_ABSORPTION_CONTRACT.csv`. For each extract B1–D4: extract_id, target_batch, target_dc, absorption_type (rule/SOP/fixture/semantic_test/runtime_validator/writer_QA/validation_asset), closure_level_supported, score_area, can_train_rules, can_validate_holdout, writer_allowed, locked_boundary (open_input/calibration_only/validation_only/locked_no_writer/holdout_only).

## A7 — Partial asset absorption path

If A1 verification finds PARTIAL assets (Tier 1 PASS, Tier 2 FAIL with TO_BE_EXTRACTED placeholders), do not block all progress. Apply two-track approach:

**Track 1 — Structure-complete assets:** Assets where all rows are fully populated with verified content → proceed to absorption classification (Step 2) and rule induction (Step 3) for those specific DCs.

**Track 2 — Content-partial assets:** Assets with TO_BE_EXTRACTED placeholders → mark PARTIAL in ASSET_READINESS_REGISTER.csv. Generate precise Owner action list in `assets/OWNER_CONTENT_FILL_CHECKLIST.md`. Format per gap: file, row, field, source (e.g., "PMID 31539432 PubMed abstract"), action (e.g., "Open abstract, verify data exists, fill yes/no").

**Absorption readiness by asset state:**
- Structure-only assets (Tier 1 only) → CLOSED_WITH_SYNTHETIC_FIXTURE_ONLY max
- Content-verified assets (Tier 1 + Tier 2) → up to DERIVED_VALIDATION
- Gold/expert-verified assets → FULLY_CLOSED

Do not mark any asset READY until content is verified. Do not claim FULLY_CLOSED from structure-only assets.

Batch A PASS: CSV valid, Golden found or fallback, asset register exists, DC-1–11 mapped, missing assets classified, locked boundary explicit, path FINAL_FOR_IMPLEMENTATION, absorption contract created, two-track absorption path defined for PARTIAL assets. Checkpoint: `CHECKPOINT_A_RESOURCE_AND_ABSORPTION_READY.md`.

---

# 15. Architecture fit check

Create `ARCHITECTURE_FIT_CHECK.md`. For each proposed capability: extend existing / add validator / add writer QA / add module / test only / config / human label / not implementable. Prefer extending existing. Check: can G39/G40/G41/G42/G43/G46 carry? Can package validator extend? Can rule loader extend? Can writer QA extend? New artifact needed? New gate needed? Smallest safe implementation? Do not implement until complete. Checkpoint: `CHECKPOINT_ARCHITECTURE_FIT_CHECK.md`.

---

# 16. Batch B — Evidence integrity (DC-1/2/3/4/5/10)

**B1 Retrieval audit**: record query_string, database, date, filters, total_hits, humans_filter, humans_hits, dedup_hits, selected_pmids, excluded_pmids, exclusion_reasons. Tests: missing query→block, recall vs gold→REWORK (or HEURISTIC_ONLY if gold missing). **B2 Screening**: N<10→EXCLUDE, animal/in-vitro→EXCLUDE, time_unspecified→REWORK, reason_code required. **B3 Fulltext**: status per PMID, no numeric from unobtainable, abstract-only data only if abstract-contains. **B4 Source anchoring**: every data point has PMID, source_type, source_sentence, population_label, confidence. **B5 Denominator**: numerator/denominator/population consistency, McKee-style detection, subgroup not generalized.

Batch B outputs: `batch_B/BATCH_B_IMPLEMENTATION_REPORT.md`, `batch_B/BATCH_B_TEST_REPORT.md`, `batch_B/BATCH_B_DEFECT_CLOSURE_MATRIX.csv`. PASS: all tests pass, DCs classified honestly, FULLY_CLOSED only when asset+validation met. Checkpoint: `CHECKPOINT_B_EVIDENCE_INTEGRITY.md`.

---

# 17. Batch C — Expert semantics (DC-6/7)

**C1 Endpoint classifier**: taxonomy for adverse_event/serious_adverse_event/treatment_failure/rescue_therapy_switch/inadequate_hemostasis/device_deficiency/procedural_outcome/skin_injury/other. Device abandonment→compression/tourniquet NOT AE. **C2 Comparator benchmark**: point estimate, CI, sample size, source PMID, directness, limitations — tourniquet/sutures/staples cannot be omitted. **C3 Claim-evidence**: beyond existence—endpoint match, population match, directness, support strength. **C4 PMCF/BR**: no-evidence→cannot_support (not PMCF pass), PMCF only for residual uncertainty.

Batch C outputs: `batch_C/BATCH_C_IMPLEMENTATION_REPORT.md`, `batch_C/BATCH_C_TEST_REPORT.md`, `batch_C/BATCH_C_DEFECT_CLOSURE_MATRIX.csv`. Checkpoint: `CHECKPOINT_C_EXPERT_SEMANTICS.md`.

---

# 18. Batch D — SOTA accounting, Writer QA, validation (DC-8/9/11)

**D1 SOTA accounting**: single source-of-truth for search_groups/raw/dedup/screened/fulltext/included/evidence — no 13 vs 1000 vs 183 vs 219. **D2 Cross-section**: endpoint list, safety count, benchmark values, conclusion strength, PMCF/limitation, narrative vs ledger consistency. **D3 Writer QA**: no stronger conclusion than ledger, no unsupported claim, no hidden numeric, no subgroup generalization, no AE misclassification, fallback limitations preserved, comparator omissions flagged. **D4 Validation**: Golden/calibration/stress/holdout projects; produce package, retrieval audit, screening, clinical facts, denominator, endpoint, benchmark, SOTA, Writer QA, validation summary. If E2E blocked: deterministic artifact-level, document blocker, cap score.

Batch D outputs: `batch_D/BATCH_D_VALIDATION_REPORT.md`, `batch_D/BATCH_D_REAL_PROJECT_RESULTS.csv`, `batch_D/BATCH_D_WRITER_QA_REPORT.md`, `batch_D/BATCH_D_DEFECT_CLOSURE_MATRIX.csv`. Checkpoint: `CHECKPOINT_D_VALIDATION_AND_WRITER_QA.md`.

---

# 19. Testing policy

Run all tests after each batch: cer_authoring suite, Batch B/C/D tests, package validator, writer QA, DC-1–11 regression fixtures. No skipped/inspected-only counts. Each batch report: command, env, pass/fail/skip, failures, repairs, rerun.

---

# 20. Repair loop budget

Per DC: max 3 repair loops; stop at 2 consecutive without progress. Per batch: max 2 architecture rewrites; no broad Review v5/frontend refactor. Budget exhausted → blocker report, score per cap rules.

---

# 21. Final scorecard

Create `BIGDP2026_6V2_EXPERT_CAPABILITY_SCORECARD.md`. 100 points: Asset readiness (10), Retrieval recall (10), Screening (8), Fulltext (8), Clinical fact traceability (12), Denominator (10), Endpoint semantics (10), Comparator benchmark (8), SOTA accounting (8), Claim-evidence (6), Writer consistency (6), Real project (4). Each area: score, requirement, code/test/runtime/validation evidence, cap applied, deduction reason, next action.

---

# 22. Final closeout

Create `BIGDP2026_6V2_FINAL_CLOSEOUT_REPORT.md`. Status: EXPERT_CAPABILITY_100_ACHIEVED / READY_WITH_LIMITATIONS / REPAIR_REQUIRED / BLOCKED_BY_ASSETS / BLOCKED_BY_ENVIRONMENT / BLOCKED_BY_DOMAIN_DECISION. 100_ACHIEVED only if Path A + score 100 + all DC FULLY_CLOSED + all tests pass + no residual gaps + real validation + locked boundary proven + Writer QA pass. Checkpoint: `CHECKPOINT_FINAL_CLOSEOUT.md`.

---

# 23. Required final artifacts

`00_PREFLIGHT_REPORT.md`, `00_PLAN_REPAIR_REPORT.md`, `VALIDATION_PATH_DECISION.md`, `SCORE_CAP_RULES.md`, `ASSET_DEPENDENCY_MATRIX.csv`, `EXPERT_LABEL_SOURCE_POLICY.md`, `LOCKED_FEEDBACK_USE_POLICY.md`, `WRITER_QA_ARCHITECTURE_DECISION.md`, `GOLDEN_FEEDBACK_FALLBACK_PLAN.md`, `DRY_RUN_MINIMUM_INPUT_SPEC.md`, `LOOP_STATE.md`, `assets/ASSET_READINESS_REGISTER.csv`, `absorption/DEFECT_TO_CAPABILITY_MAP.csv`, `absorption/ASSET_ABSORPTION_CONTRACT.csv`, `absorption/ABSORPTION_READY_REPORT.md`, `ARCHITECTURE_FIT_CHECK.md`, `batch_B/BATCH_B_*`, `batch_C/BATCH_C_*`, `batch_D/BATCH_D_*`, `EXPERT_CAPABILITY_SCORECARD.md`, `FINAL_CLOSEOUT_REPORT.md`, all checkpoints. If blocked: `BLOCKER_REPORT.md` (blocker, evidence, repairs, why unsafe, score impact, Owner action, resume).

---

# 24. Session management

Checkpoints: `CHECKPOINT_00_PREFLIGHT_AND_FRAMEWORK.md`, `CHECKPOINT_A_RESOURCE_AND_ABSORPTION_READY.md`, `CHECKPOINT_ARCHITECTURE_FIT_CHECK.md`, `CHECKPOINT_B_EVIDENCE_INTEGRITY.md`, `CHECKPOINT_C_EXPERT_SEMANTICS.md`, `CHECKPOINT_D_VALIDATION_AND_WRITER_QA.md`, `CHECKPOINT_FINAL_CLOSEOUT.md`. Each: completed work, files changed, tests run, path, score, blockers, resume command. After each checkpoint: compact context, resume from `LOOP_STATE.md`.

---

# 25. Final response

Reply only: final status, Path A/B, score, 100 achieved?, assets prepared, assets missing, batches completed, tests run/results, validation projects used, unresolved blockers, next Owner/Domain Expert/Controller action.
