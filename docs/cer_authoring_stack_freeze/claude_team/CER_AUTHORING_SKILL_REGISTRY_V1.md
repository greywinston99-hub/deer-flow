# CER AUTHORING SKILL REGISTRY V1.0

> Claude Code | 2026-05-15 | Phase 2D

## Registered Skills

### 1. Source Inventory & Intake
- **Scope**: Source document inventory, device identity arbitration, domain locking
- **Input**: Raw source files (IFU, RMF, GSPR, PMS, clinical data)
- **Output**: source_inventory, device_identity_lock, device_profile
- **Forbidden**: Overriding deterministic identity lock, skipping domain check
- **Human Gate**: Owner confirms device identity for unknown domains
- **Status**: ACTIVE

### 2. Claim Decomposition & PICO Derivation
- **Scope**: Extract claims from IFU, derive PICO from clinical uncertainty
- **Input**: IFU intended purpose text, device_profile
- **Output**: claim_ledger, cep_pico_matrix, intended_purpose_claim_table
- **Forbidden**: Inventing claims not grounded in IFU text
- **Status**: ACTIVE

### 3. SOTA Search & Benchmark Construction
- **Scope**: PubMed/PMC/Europe PMC/CT.gov literature search, screening, benchmark
- **Input**: PICO matrix, search protocols, clinical domain
- **Output**: sota_benchmark_table, screening dispositions, clinical background
- **Forbidden**: Cross-domain SOTA, fabricated benchmarks, wrong clinical field
- **Status**: ACTIVE

### 4. Evidence Appraisal & Registry
- **Scope**: Full-text appraisal, evidence hierarchy, claim-evidence linking
- **Input**: Search results, full-text supplements, screening dispositions
- **Output**: evidence_registry, claim_evidence_matrix, evidence_appraisal_table
- **Forbidden**: Inventing evidence, wrong-domain linking
- **Status**: ACTIVE

### 5. Risk/GSPR/Equivalence Analysis
- **Scope**: Risk management trace, GSPR mapping, equivalence determination
- **Input**: RMF sources, GSPR checklist, similar device data
- **Output**: benefit_risk_conclusion, risk_gspr_trace_matrix, equivalence_comparison_matrix
- **Forbidden**: Unsupported equivalence claims
- **Status**: ACTIVE

### 6. CER Writer (Prose Generation)
- **Scope**: Generate CER sections 1-5 + annexes from gate-passed evidence
- **Input**: All upstream artifacts, gate-passed ledgers, domain template
- **Output**: cer_chapter_drafts
- **Forbidden**: Cross-domain text, internal language, favourable conclusions for INSUFFICIENT claims
- **Human Gate**: Owner review before final sign-off
- **Status**: ACTIVE (with Phase 2A domain template hardening)

### 7. QA Review
- **Scope**: 8-dimension QA: methodology, evidence integrity, SOTA, equivalence, vigilance, risk/GSPR, human style, NB precheck
- **Input**: Complete state with all artifacts + CER draft
- **Output**: qa_gate_report with per-dimension findings
- **Forbidden**: False PASS on contaminated reports, score 100 without findings
- **Status**: ACTIVE (with Phase 2A Gate 5 hardening)

### 8. Writer Remediation Gates (1-5)
- **Scope**: Post-Writer content validation: domain consistency, IFU consumption, evidence-conclusion match, body cleanliness, composite QA
- **Input**: CER body text, device_profile, claim_support_matrix
- **Output**: Per-gate results, quarantine routing, QA report
- **Forbidden**: Letting gate-failed reports into release
- **Status**: ACTIVE (Phase 1 + Phase 2A)

### 9. Artifact Export & Quarantine
- **Scope**: Write artifacts to output, route gate-failed to quarantine
- **Input**: State, CER draft, gate results
- **Output**: Output files + quarantine directory
- **Forbidden**: Writing gate-failed reports to release directory
- **Status**: ACTIVE

### 10. PDF Parsing Pipeline
- **Scope**: PDF-to-text extraction with depth-aware routing (Camelot + Docling)
- **Input**: PDF files (IFU, RMF, GSPR, clinical data)
- **Output**: document_structured_content
- **Forbidden**: Silent extraction failure
- **Status**: ACTIVE (verified functional, not in remediation scope)

### 11. Prompt & Template Management
- **Scope**: Prompt extraction, hashing, change control, domain template freeze
- **Input**: Agent configs, pipeline prompt constants
- **Output**: PROMPT_PACK_V1, PROMPT_HASH_MANIFEST.json, TEMPLATE_SOURCE_AND_ALLOWED_USE_LEDGER.md
- **Forbidden**: Changing prompts without owner review
- **Status**: ACTIVE (Phase 2B freeze)
