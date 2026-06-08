# ⏸️ Human Gate: intake_pack_review

**Priority**: CRITICAL
**Step**: HC-0
**Message**: Please review manufacturer intake pack P0/P1 status before device profile.

---

## Manufacturer Intake Pack
**Workbook**: `/Users/winstonwei/CER-RAG/升级 CCD-3 个项目文件/2026.5.28- 试运行项目/A01_无忧跳动/MANUFACTURER_INTAKE_PACK_TEMPLATE_2026-05-28_FILLED_v2.xlsx`

- P0 draft/unconfirmed count: 0
- P1 draft/needs-review count: 1

### Critical Flags
- P1-DRAFT: pmcf_plan — PMCF Plans available for both system (PMCF_003) and tubing (PMCF_004). Both follow MDCG 2020-7 templ

### P0 Device Scope (10 rows)
| Field ID | Status | Response |
| --- | --- | --- |
| subject_device_boundary | confirmed | System combination — Bubble Study System (active medical electrical equipment, Model BS-2, Class IIb) + Disposable Contr |
| subject_device_domain | confirmed | contrast_imaging_bubble_study_system |
| product_name_en | confirmed | Bubble Study System / Disposable Contrast Injection Tubing Set |
| product_name_cn | confirmed | 全自动超声造影注射系统 / 一次性使用造影注射管路套件 |
| model_specifications | confirmed | BS-2 (Bubble Study System); DCS-3030, DCS-3030B, DCS-5030, DCS-5030B (Disposable Contrast Injection Tubing Set) |
| system_or_component | confirmed | System — standalone active device (Class IIb) with integral single-use consumable accessory (Class IIa) |
| mdr_classification | confirmed | IIb |
| mdr_rule | confirmed | Rule 10 + Rule 12 (system); Rule 2 (tubing set) |
| classification_rationale | confirmed | Bubble Study System is an active device intended for diagnosis (contrast imaging) and administers agitated saline via in |
| manufacturer_name | confirmed | WYTD MEDICAL TECHNOLOGY (SHENZHEN) CO., LTD. |

### P1 Evidence Controls (8 rows)
| Control ID | Status | Response |
| --- | --- | --- |
| gspr_checklist | confirmed | Available. (1) "GSPR checklist of Bubble Study System" (GSPR_001) for active device; (2) "GSPR checklist - Active Non-Sterile" (GSPR_002); (3) "GSPR checklist - Non-Active Sterile" |
| rmf_available | confirmed | Available for both system and consumables. System: Risk Management Plan (RMF_009), Risk Management Report (RMF_007), domestic RMP (RMF_017), domestic RMR (RMF_015), PFMEA (RMF_008) |
| ifu_warning_rmf_crosswalk | confirmed | Mapped. Key warnings cross-referenced to hazards in RMF: single-use warning → cross-infection hazard (biological risk); packaging damage warning → sterility breach hazard; air embo |
| pms_data | confirmed | PMS Plan available (PMS_002, PMS_003). Pre-market clinical data: prospective, multi-center, cross-over controlled clinical trial (CLINEV_001, protocol WYTD-YY-A03 V1.1). 3 centers: |
| pmcf_plan | draft | PMCF Plans available for both system (PMCF_003) and tubing (PMCF_004). Both follow MDCG 2020-7 template structure (Sections A-G). C.4 Clinical experience gathering: 67 cases/year,  |
| claim_evidence_mapping | confirmed | Primary claim (diagnostic accuracy): Positive/negative RLS detection concordance vs manual method. Evidence: prospective multi-center clinical trial (180 subjects, crossover design |
| sota_search_protocol | confirmed | Available. (1) "Annex 1 Literature Search Protocol and Report - SOTA" (SOTA_001) for state-of-the-art literature review. (2) "Annex 2 Literature Search Protocol and Report - Device |
| equivalence_boundary | confirmed | No direct equivalent device identified. Bubble Study System is a novel automated device for agitated saline preparation and injection. Clinical evaluation based on direct clinical  |

---

## To Continue

Edit `.human_gate/response.json` and save the file:
- `{"action": "confirm"}` — approve and continue forward
- `{"action": "rework", "target": "input_gate", "reason": "..."}` — rewind to input_gate

**File**: `/Users/winstonwei/Documents/Playground/deer-flow/backend/test-results/A01_WUYOU_HC_VALIDATION_005/.human_gate/intake_pack_review.md`