# PHASE 2A CLOSEOUT — Source Fixes (Template + IFU + Domain)

> Claude Code | 2026-05-15

## Status: PASS

## What was implemented

### 1. Domain-specific template skeletons

New module: `writer_remediation/domain_templates.py`

Three domain-specific template packs created:
- `cardiac_stabilizer_template_sections()` — 4 sections (2.1, 2.2, 3.x, 5) with cardiac-specific instructions
- `orthopedic_plasma_electrode_template_sections()` — 4 sections with orthopedic/arthroscopy instructions
- `imaging_software_template_sections()` — 4 sections with SaMD-specific instructions

Each template explicitly forbids cross-domain terms in Writer instructions.

### 2. Unknown domain blocking

- `block_if_unknown(clinical_domain)` returns Writer block for truly unrecognised domains
- Integrated into `build_writer_device_template_profile()` in pipeline.py
- Known domains include existing pipeline-supported domains + Phase 2A pilot domains
- Domain check happens before template profile construction

### 3. Domain template dispatch

- `_compose_modular_writer_sections()` now has domain-specific dispatch for:
  - `cardiac_tissue_stabilizer`
  - `orthopedic_rf_plasma_electrode` / `plasma_surgical_electrode`
  - `medical_imaging_software` / `ai_diagnostic_software` / `diagnostic_software`
- Domain templates take priority over generic family/function dispatch
- Falls back to existing template system for other domains

### 4. IFU field-to-section mapping

- `IFU_FIELD_MAP` defines 11 field-to-section mappings
- `get_ifu_field_instruction()` generates grounded Writer instructions from IFU data
- `build_ifu_grounded_device_fields()` builds field data from device_profile + document_structured_content
- Missing fields get explicit "IFU source does not contain this information" (not placeholder text)

## Files changed

- `backend/.../writer_remediation/domain_templates.py` — NEW (domain templates, IFU mapping, unknown domain blocking)
- `backend/.../pipeline.py` — import + domain dispatch + unknown domain blocking (~30 lines added)
- `backend/tests/test_phase2a_source_fixes.py` — NEW (14 targeted tests)

## Test results

- 298 tests PASS (284 original + 14 Phase 2A targeted)
- graph.py / gates.py / agents.py: zero diff

## Next: Phase 2B — Prompt + Template Freeze
