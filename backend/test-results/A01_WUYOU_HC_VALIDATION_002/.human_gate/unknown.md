# ⏸️ Human Gate: unknown

**Priority**: CRITICAL
**Step**: 3
**Message**: Please confirm Device Profile before proceeding to claim decomposition.

---

## Device Profile
| Field | Value |
| --- | --- |
| device_name | IFU of Bubble Study System |
| manufacturer | WYTD MEDICAL TECHNOLOGY (SHENZHEN) CO., LTD. |
| device_class | IIb |
| device_type | automated agitated-saline contrast injection system with single-use contrast injection tubing set |
| device_family | ultrasound contrast bubble-study diagnostic system |
| clinical_domain | contrast_imaging_bubble_study_system |
| device_identity_arbitration_status | DEVICE_IDENTITY_CONFLICT |
| device_identity_selected_evidence_source | locked_domain_hint |
| device_identity_conflicts | [{'rank': 8, 'evidence_source': 'llm_or_text_classifier', 'observed_domain': 'stent_device', 'selected_domain': 'contrast_imaging_bubble_study_system', 'source_ids': ['SRC-010', 'SRC-018', 'SRC-030',  |
| excluded_accessory_tokens | [] |
| device_type_confidence | low |
| classification_confidence | low |
| identity_evidence_spans | [{'source_id': 'SRC-256', 'matched_token': 'stent', 'span': 'e MANUFACTURER of MEDICAL DEVICE SOFTWARE shall demonstrate the ability to provide MEDICAL DEVICE SOFTWARE that consistently meets customer |
| identity_alternative_candidates | [{'device_type': 'catheter', 'device_family': 'catheter device', 'clinical_domain': 'generic_catheter', 'score': 4, 'reason': 'Generic catheter terminology found without stronger domain evidence.'}] |
| identity_uncertainty_reason | Only weak generic device-type evidence was available. |
| identity_supporting_source_types | ['RMF', 'IFU', 'GSPR', 'source'] |
| identity_source_scope | IFU + manufacturer metadata/GSPR/RMF source inventory, excluding locked delta-only and similar-device sources. |
| intended_purpose | The Bubble Study System is used in conjunction with Disposable Masks and Disposable Contrast Injection Tubing Set for the preparation and injection of agitated saline during bubble study procedures fo |
| model_specifications | BS-2 (system); DCS-3030, DCS-3030B, DCS-5030, DCS-5030B (tubing set) |
| composition | Requires confirmation from IFU §产品结构组成/结构及组成; refer to subject device IFU for details. |
| working_principle | Requires confirmation from IFU §工作原理; refer to subject device IFU for details. |
| sterility | Requires confirmation from IFU §灭菌方式/无菌屏障系统组成; refer to subject device IFU for details. |
| shelf_life_storage | Requires confirmation from IFU §使用期限/储存与运输; refer to subject device IFU for details. |
| performance_summary | Requires confirmation from IFU §产品性能; refer to subject device IFU for details. |
| contraindications | 1) Severe cardiac, hepatic, renal, or pulmonary impairment; malignant tumors; hematological or autoimmune diseases. 2) Patients unable to cooperate due to consciousness or cognitive disorders. 3) Caro |
| target_population | Adults aged 18-75 years, both sexes. Patients clinically suspected of right-to-left shunt who can complete contrast echocardiography or transcranial Doppler ultrasound assessment and can cooperate wit |
| intended_user | Trained and experienced medical staff with professional certification. Specifically: cardiac ultrasound physicians for c-TTE; neurology ultrasound physicians for c-TCD. |
| intended_environment | Professional healthcare environment |
| anatomical_site | Cardiac: right atrium, interatrial septum (foramen ovale) for transthoracic echocardiographic contrast imaging (c-TTE). Cerebral: middle cerebral artery (MCA) for contrast-enhanced transcranial Dopple |
| mode_of_action | Automated preparation and injection of agitated saline contrast through single-use tubing for transthoracic echocardiographic contrast imaging (c-TTE) or contrast-enhanced transcranial Doppler ultraso |
| profile_source | IFU/source_inventory |
| device_domain | contrast_imaging_bubble_study_system |
| ifu_structured_extraction | {'fields_extracted': ['model_specifications', 'contraindications'], 'fields_pending': ['composition', 'working_principle', 'sterility', 'shelf_life_storage', 'performance_summary'], 'source_type': 'IF |
| mcp_profile_enriched | True |

---

## To Continue

Edit `.human_gate/response.json` and save the file:
- `{"action": "confirm"}` — approve and continue forward

**File**: `/Users/winstonwei/Documents/Playground/deer-flow/backend/test-results/A01_WUYOU_HC_VALIDATION_002/.human_gate/unknown.md`