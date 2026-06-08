# AGENT TEAM RUNTIME INVENTORY — CER Authoring V1.0

> Claude Code | 2026-05-15 | Phase 2D | Documents what actually runs

## Team Mode

- Active: `stable-1plus6` (7 physical agents)
- Legacy: `legacy-20` (20 virtual agents) — maintained for compatibility, not recommended

## Physical Agents (what actually runs in stable mode)

### 1. cer-authoring-lead-agent (Lead)
- **Role**: Orchestrator only — does NOT write CER prose, does NOT replace deterministic gates
- **Input**: SharedAuthoringState (full state snapshot)
- **Output**: JSON with decision, findings, rework_targets, confidence, rationale
- **Virtual roles covered**: authoring-final-gate-closure
- **Model**: inherit
- **Max turns**: 80 | **Timeout**: 900s

### 2. authoring-cer-writer-agent (Writer)
- **Role**: CER prose writer — consumes gate-passed evidence, writes sections 1-5 + annexes
- **Input**: device_profile, claim_support_matrix, evidence_registry, gate-passed ledgers
- **Output**: cer_chapter_drafts, writer_synthesis_trace
- **Model**: inherit | **Max turns**: 80 | **Timeout**: 900s

### 3. authoring-evidence-agent (Evidence)
- **Role**: Evidence registry, appraisal, full-text acquisition, claim-evidence matrix
- **Input**: search results, full-text supplements, screening dispositions
- **Output**: evidence_registry, claim_evidence_matrix, evidence_appraisal_table
- **Model**: inherit | **Max turns**: 80 | **Timeout**: 900s

### 4. authoring-methodology-sota-agent (SOTA)
- **Role**: SOTA search, clinical background, benchmark construction, literature methodology
- **Input**: PICO matrix, search protocols, clinical domain context
- **Output**: sota_benchmark_table, sota_screening_disposition_table, clinical_background_sections
- **Model**: inherit | **Max turns**: 80 | **Timeout**: 900s

### 5. authoring-intake-profile-claim-agent (Intake)
- **Role**: Device profile, claim decomposition, PICO derivation, source inventory
- **Input**: source_inventory, IFU text, device_identity_lock
- **Output**: device_profile, claim_ledger, cep_pico_matrix
- **Model**: inherit | **Max turns**: 80 | **Timeout**: 900s

### 6. authoring-risk-equivalence-gspr-agent (Risk/GSPR)
- **Role**: Risk management, GSPR mapping, equivalence analysis, benefit-risk
- **Input**: RMF sources, GSPR checklist, similar device data
- **Output**: benefit_risk_conclusion, risk_gspr_trace_matrix, equivalence_comparison_matrix
- **Model**: inherit | **Max turns**: 80 | **Timeout**: 900s

### 7. authoring-qa-review-agent (QA)
- **Role**: Integrated QA reviewer — all 8 virtual review dimensions
- **Input**: complete state with all artifacts
- **Output**: qa_gate_report with decision, findings, rework_targets
- **Model**: inherit | **Max turns**: 80 | **Timeout**: 900s

## Companion Pipelines (Not Agents, But Part of Runtime)

- graph.py: LangGraph state machine with deterministic gate nodes
- pipeline.py: Deterministic pipeline helpers (evidence sufficiency, SOTA search, claim matrix, Writer template)
- artifacts.py: Artifact export and quarantine routing
- writer_remediation/: 5 post-Writer content gates (Gates 1-5)
- phase0_contracts.py: Calibration contracts and failure taxonomy
- state.py: State schema and validation
