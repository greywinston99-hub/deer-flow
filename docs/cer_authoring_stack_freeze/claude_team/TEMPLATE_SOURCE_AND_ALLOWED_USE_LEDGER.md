# TEMPLATE SOURCE AND ALLOWED USE LEDGER — CER Authoring V1.0

> Claude Code | 2026-05-15 | Phase 2C

## Template Origins

| Template | Source | Origin | Allowed Use |
|----------|--------|--------|-------------|
| cardiac_stabilizer | domain_templates.py | NEW — Phase 2A | cardiac_tissue_stabilizer domain ONLY |
| orthopedic_plasma_electrode | domain_templates.py | NEW — Phase 2A | plasma_surgical_electrode / orthopedic_rf_plasma_electrode domain ONLY |
| imaging_software | domain_templates.py | NEW — Phase 2A | medical_imaging_software / ai_diagnostic_software domains ONLY |
| therapeutic_catheter | pipeline.py `_therapeutic_catheter_template_sections()` | Pre-Phase 2 | cardiovascular_rf_ablation_catheter domain ONLY |
| surgical_ligating_clip | pipeline.py `_surgical_implant_ligating_clip_template_sections()` | Pre-Phase 2 | surgical_ligating_clip domain ONLY |
| software_medical_device | pipeline.py `_software_medical_device_template_sections()` | Pre-Phase 2 | SaMD / software domains ONLY |
| powered_equipment | pipeline.py `_powered_equipment_template_sections()` | Pre-Phase 2 | powered_equipment family ONLY |
| implantable_device | pipeline.py `_implantable_device_template_sections()` | Pre-Phase 2 | implantable family ONLY |
| disposable_device | pipeline.py `_disposable_device_template_sections()` | Pre-Phase 2 | disposable family ONLY |
| generic_fallback | pipeline.py `_generic_device_template_sections()` | Pre-Phase 2 | LOW CONFIDENCE identity ONLY |

## Forbidden Template Fragments

The following historical prose is PROHIBITED from use as template content:

1. CAL-001 PADN/pulmonary artery ablation clinical prose — must not appear in non-cardiac-ablation templates
2. CAL-001 UAS/ureteroscope/urinary tract clinical prose — must not appear in non-urology templates
3. Any "clinical data partially support" boilerplate applied uniformly regardless of claim support level
4. Any internal system language (Claude, DeerFlow, MCP, not_allowed, score: 100, benchmark decision) in template instructions
5. Any "Not extracted from IFU source text" as fallback placeholder (replaced by "IFU source does not contain this information")

## Domain Template Boundary Matrix

| Domain | Template | Forbidden Cross-Domain Terms |
|--------|----------|------------------------------|
| cardiac_tissue_stabilizer | cardiac_stabilizer | ureteroscope, UAS, urology, PADN, ablation, stone burden |
| plasma_surgical_electrode | orthopedic_plasma_electrode | cardiac ablation, PADN, ureteroscope, UAS, urology |
| medical_imaging_software | imaging_software | catheter, implant, sterility, shelf life, surgical access |
| cardiovascular_rf_ablation_catheter | therapeutic_catheter | arthroscopy, orthopedic, ureteroscope, urological |

## Change Control

Template changes must:
1. Update TEMPLATE_SOURCE_AND_ALLOWED_USE_LEDGER.md
2. Update domain_templates.py if applicable
3. Re-run full regression
4. Re-run gates against all domain fixtures
