# DeerFlow CER Engineer Feedback Full-Absorption Upgrade Plan

Date: 2026-05-28

## Goal

Upgrade DeerFlow CER Authoring from "can run and can block bad inputs" to a system that fully operationalizes the engineer feedback in:

- `CER_01_MATRIX_章节结构对比矩阵.md`
- `CER_02_LOGIC_逻辑关系与依赖分析.md`
- `CER_03_STYLE_写作风格与行文密码.md`
- `CER_04_ANSWERS_第一性原理问题回答.md`
- `CER_05_TABLES_表格体系与证据脉络分析.md`
- `SKILL_ELICITATION_QUESTIONS_EXPLAINED.md`

The target is not to guarantee a high score from poor inputs. The target is to guarantee that complete source packages are processed through a workflow capable of producing submission-grade controlled draft CERs with expected Review quality around 85/100 or higher: critical findings = 0 and major findings <= 3.

## Current Absorption Assessment

Estimated system-level absorption of engineer feedback: 78-82%.

Already operationalized:

- Source preflight and manufacturer intake hard gates.
- IFU P0 completeness and classification/domain source lock.
- CEP-before-search method gate.
- Claim-SOTA alignment and device-profile iteration nodes.
- PRISMA artifacts and screening disposition tables.
- Claim evidence matrix, allowed wording, final-body eligibility and writer packet.
- IFU feedback suggestions and IFU/CER alignment ledgers.
- Benefit-risk ledger and writer conclusion guard.
- RMF/IFU warning/PMCF/benefit-risk crosswalk artifacts.
- Writer gates for raw JSON, internal terms, CJK contamination, placeholders, weak support and conclusion strength.
- CER Review final synthesis and authoring-blocked context.

Still not fully operationalized:

- No single coverage ledger proving every engineer feedback rule is mapped to code, artifact, gate and test.
- IFU feedback remains advisory; it is not yet a formal IFU iteration loop with human/manufacturer decision records.
- Claim taxonomy does not yet fully distinguish intended purpose vs clinical benefit, efficacy benefit vs safety benefit, IFU warning as residual-risk disclosure, and non-claim administrative text.
- PRISMA reproducibility is present but not strict enough: database-level counts, dedupe-before-screening proof, exclusion criteria IDs and repeatable-count checks need hard gating.
- Evidence level mapping exists, but no first-class `evidence_level_summary_matrix` exported and consumed by writer/review as a required artifact.
- Endpoint homogeneity is not a hard pre-benchmark gate; endpoint family, unit, timepoint, population and comparator matching need deterministic checks.
- Equivalence logic exists, but the system needs a stronger route lock: equivalence claimed, equivalence not claimed, background-only similar device use, or customer-risk-accepted data gap.
- Benefit-risk is ledger-controlled, but the body CER must have a dedicated Benefit-Risk Analysis section with qualitative and quantitative reasoning, not only annex support.
- RMF linkage is too filename-driven; IFU warnings and vigilance risks should map to parsed RMF hazard IDs/residual-risk IDs where source text allows.
- Style feedback exists as heuristics, but PEEL/GSPR paragraph completeness, conclusion sentence length and table/body boundary are not strict release gates.

## Upgrade Workstreams

### WS1: Engineer Feedback Coverage Ledger

Add a machine-readable feedback coverage system.

New files:

- `backend/packages/harness/deerflow/runtime/cer_authoring/knowledge/engineer_feedback_rules.json`
- `backend/packages/harness/deerflow/runtime/cer_authoring/tests/test_engineer_feedback_coverage.py`

New artifact:

- `engineer_feedback_coverage_report.json`

Required fields:

- `feedback_id`
- `source_document`
- `requirement`
- `severity`
- `implemented_by`
- `artifact_contract`
- `gate_contract`
- `test_contract`
- `coverage_status`

Gate rule:

- Any P0/P1 feedback rule without code + artifact + test coverage fails `FINAL_DRAFT_QA_REPORT`.

### WS2: Formal IFU Iteration Loop

Turn existing IFU suggestions into a controlled workflow.

Enhance:

- `pipeline._generate_ifu_feedback`
- `pipeline._build_ifu_cer_alignment_ledger`
- `gates.evaluate_pre_writer_readiness_gate`
- artifact export list

New artifacts:

- `ifu_iteration_decision_ledger.json`
- `ifu_update_recommendation_ledger.json` as required final artifact
- `ifu_claim_scope_delta_matrix.xlsx`

Rules:

- IFU overclaim with unsupported evidence blocks writer.
- Missing clinical benefit does not block writer, but must create an IFU update recommendation.
- Final CER cannot state IFU is fully aligned unless the IFU iteration ledger is closed or explicitly marked as manufacturer pending.

### WS3: Claim Taxonomy And Evidence Routing

Upgrade claim classification from broad labels to engineer-aligned claim classes.

Required classes:

- `non_claim_admin`
- `intended_purpose_scope`
- `indication`
- `efficacy_clinical_benefit`
- `safety_clinical_benefit`
- `performance_claim`
- `ifu_warning_residual_risk`
- `contraindication`
- `technical_specification`
- `sterility_or_shelf_life`

New artifacts:

- `claim_taxonomy_decision_table.xlsx`
- `claim_evidence_route_matrix.xlsx`

Rules:

- `ifu_warning_residual_risk` must route to RMF/GSPR/IFU warning crosswalk.
- `efficacy_clinical_benefit` and `safety_clinical_benefit` must require clinical evidence or PMS/PMCF support.
- `intended_purpose_scope` is not automatically a benefit claim.
- `non_claim_admin` must not enter PubMed/SOTA claim support routing.

### WS4: PRISMA Reproducibility Gate

Upgrade PRISMA from artifact generation to reproducibility gate.

Enhance:

- `pipeline.screen_literature`
- `_prisma_flow_data`
- `_prisma_flow_diagram_payload`
- `gates._gate_prisma_flow`

New artifact:

- `prisma_reproducibility_audit.json`

Required fields:

- query ID, database, search date/time, exact query, filters
- raw hits, dedup input count, duplicate count, after-dedup count
- title/abstract screened count
- title/abstract excluded count with exclusion criteria ID
- full-text assessed count
- full-text excluded count with exclusion criteria ID
- final included count

Gate rules:

- Dedupe must occur before title/abstract screening.
- Every excluded record must have `exclusion_reason` and `exclusion_criteria_id`.
- Sum of counts must reconcile.
- Missing search date or exact query is a major failure.

### WS5: Evidence Level Summary Matrix

Make MDCG/Oxford evidence grading visible to writers and reviewers.

New artifact:

- `evidence_level_summary_matrix.xlsx`

Required fields:

- evidence ID
- source type
- study design
- sample size
- follow-up
- Oxford level
- MDCG 2020-6 level
- pivotal/supportive/background role
- claim IDs supported
- endpoint IDs supported
- conclusion strength ceiling

Rules:

- Writer cannot use stronger wording than the evidence-level ceiling.
- Review must flag any final claim whose support level is lower than final wording.

### WS6: Endpoint Homogeneity Gate

Operationalize the engineer rule: endpoints can only be compared when they are homogeneous.

New artifact:

- `endpoint_homogeneity_matrix.xlsx`

Required fields:

- endpoint family
- endpoint definition
- measurement method
- unit
- timepoint
- population
- comparator
- acceptable substitutions
- substitution rationale
- homogeneous_for_benchmark

Gate rules:

- Benchmark derivation fails if endpoint family/unit/timepoint/population are incompatible without a substitution rationale.
- Endpoint alternatives may downgrade strength but cannot silently support a pivotal conclusion.

### WS7: Equivalence Route Lock

Make equivalence route decisions explicit before evidence writing.

New artifact:

- `equivalence_route_lock.json`

Allowed decisions:

- `equivalence_not_claimed`
- `full_equivalence_claimed`
- `similar_device_background_only`
- `customer_risk_accepted_data_gap`

Rules:

- If equivalence is not claimed, the writer must explicitly say so.
- If equivalence is claimed, technical/biological/clinical matrices are mandatory.
- If performance data are unavailable but customer accepts risk, the audit trail must record it and final wording must be limited.

### WS8: Dedicated Benefit-Risk Body Section

Insert a dedicated body section between evidence analysis and GSPR/conclusion.

Enhance:

- `write_cer_chapters`
- `_chapter_device_under_evaluation`
- `_chapter_conclusions`

New body section:

- `4.8 Benefit-Risk Analysis`

Minimum content:

- clinical benefits with quantitative/semi-quantitative data
- mapped risks with severity/occurrence/residual-risk status
- comparison of benefit magnitude vs risk severity
- PMS/PMCF maturity
- conclusion strength and limitation

Gate rules:

- Benefit-risk section cannot be replaced by annex tables.
- Unqualified favourable benefit-risk wording is prohibited unless evidence, RMF and PMS/PMCF closure support it.

### WS9: RMF Deep Linkage

Upgrade RMF crosswalk from source-present checks to parsed hazard/residual-risk linkage.

Enhance:

- `rmf_crosswalk.py`
- document parsing lineage consumption

New fields:

- `rmf_hazard_id`
- `sequence_of_events`
- `hazardous_situation`
- `harm`
- `initial_risk`
- `risk_control_measure`
- `residual_risk`
- `residual_risk_acceptability`
- `ifu_warning_id`
- `vigilance_signal_id`

Gate rules:

- IFU warning without RMF linkage is major or critical depending on risk severity.
- Missing RMF blocks unqualified benefit-risk conclusion.

### WS10: Style And Body/Annex Release Gates

Convert style feedback into measurable release controls.

Enhance:

- writer gates
- final draft QA

New artifact:

- `regulatory_style_fingerprint_report.json`

Rules:

- GSPR paragraphs must contain requirement, evidence source, evidence summary, reasoning and compliance judgment.
- Literature appraisal paragraphs must contain source, method, result, relevance, quality and limitation.
- Conclusion section must include safety, performance, benefit-risk and PMS/PMCF limitation conclusions.
- Conclusion sentence length target: mostly <= 20 words.
- Annex tables may support but may not replace body reasoning.

## Validation Plan

Add or update tests:

- `test_engineer_feedback_coverage.py`
- `test_ifu_iteration_loop.py`
- `test_claim_taxonomy_routing.py`
- `test_prisma_reproducibility_gate.py`
- `test_evidence_level_summary_matrix.py`
- `test_endpoint_homogeneity_gate.py`
- `test_equivalence_route_lock.py`
- `test_benefit_risk_body_section.py`
- `test_rmf_deep_linkage.py`
- `test_regulatory_style_fingerprint.py`

Real-project acceptance run:

1. Use A01 WYTD Bubble Study project with filled manufacturer intake.
2. Run full CER Authoring.
3. Run CER Review formal-review.
4. Confirm:
   - source preflight PASS
   - engineer feedback coverage P0/P1 = 100%
   - final writer gate PASS
   - CER Review critical = 0
   - CER Review major <= 3
   - no unqualified benefit-risk conclusion if PMCF remains draft

## Expected Quality Impact

Current system capability:

- Good at flow completion and deterministic blocking.
- Medium-good at writer control.
- Medium at engineer feedback absorption.
- Weak-to-medium at proving every feedback rule is actually covered.

After this upgrade:

- Bad input will fail earlier with precise repair instructions.
- Good input will have stronger claim/evidence/risk/BR traceability.
- Review findings should shift from critical/major structural defects to minor editorial or source-completeness findings.
- Submission-grade controlled drafts should be capable of reaching 85/100+ when source package is complete.
