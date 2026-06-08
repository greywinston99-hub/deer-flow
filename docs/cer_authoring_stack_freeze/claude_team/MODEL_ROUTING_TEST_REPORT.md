# MODEL ROUTING TEST REPORT — Phase 3A

> Claude Code | 2026-05-15

## Targeted Tests: 25/25 PASS

### Model Resolution (8 tests)
- Writer routes to deepseek-v4-pro by default ✓
- QA routes to deepseek-v4-pro by default ✓
- Extraction agents (intake, risk) route to kimi-k2.6-code ✓
- Evidence reasoning agents (sota, evidence) route to deepseek ✓
- Env var override respected ✓
- State config override respected ✓
- Unknown agent uses global fallback ✓
- All agents have routing policy entries ✓

### Model Boundaries (9 tests)
- kimi-code FORBIDDEN for Writer ✓
- kimi-code FORBIDDEN for QA ✓
- kimi-code FORBIDDEN for evidence reasoning (sota, evidence) ✓
- minimax FORBIDDEN for Writer ✓
- minimax FORBIDDEN for QA ✓
- minimax FORBIDDEN for evidence reasoning ✓
- deepseek ALLOWED for ALL agents ✓
- All 4 models have boundary definitions ✓

### Deterministic Stages (1 test)
- Gate evaluation, quarantine, PDF parsing, artifact export are deterministic ✓

### A/B Config (3 tests)
- Writer has A/B config with 2 candidates ✓
- QA has A/B config with 2 candidates ✓
- Extraction does not require A/B test ✓

### Task Type Assignment (4 tests)
- Writer = cer_writer ✓
- QA = qa_reviewer ✓
- Intake = extraction_structuring ✓
- Evidence agents = evidence_reasoning ✓
- Risk = risk_equivalence ✓

## Full Regression: 323/323 PASS

- test_cer_authoring_runtime.py: 259 PASS
- test_writer_remediation_gates.py: 25 PASS
- test_phase2a_source_fixes.py: 14 PASS
- test_model_routing.py: 25 PASS
- graph.py / gates.py / agents.py: zero diff

## Runtime Access

VS Code Claude Code has NO LLM runtime. All tests pass without LLM (structural/config tests only). A/B execution requires DeerFlow runtime.
