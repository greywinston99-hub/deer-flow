# Phase 4A P4 — Writer Template Device-Class Adaptation

Decision: `IMPLEMENTED_ACCEPTED`

Effectiveness status: `EFFECTIVENESS_PENDING`

## Scope

This patch addresses COG-007 by adapting the CER writer template to the locked device class and clinical domain before section 4 drafting.

The change is limited to the writer template layer:

- no graph structure changes;
- no G30/G33/G38 gate criteria changes;
- no 1+6 authoring agent changes;
- no Phase 0.6 device identity arbitration changes;
- no baseline structural pipeline changes.

## Implemented Template Selection

The writer now builds a `writer_device_template_profile` and `writer_device_conditional_sections` before chapter drafting. The selector uses the locked clinical domain, device class, device type, device family, intended purpose, mode of action, anatomical site and composition.

Conditional templates:

- `therapeutic_catheter_rf_ablation`
  - Energy Delivery and Lesion-Control Evidence
  - Procedural Safety and Use-Environment Controls
  - Generator-Catheter Compatibility

- `software_medical_device`
  - Algorithm and Model Description
  - Analytical and Clinical Validation
  - Cybersecurity, Data Integrity and Software Lifecycle

- `surgical_implant_ligating_clip`
  - Material, Implant Contact and Biocompatibility
  - Sterilization, Packaging and Shelf-life
  - Implantation, Ligation Security and Procedure-Specific Risks

- `implantable_device`
  - Materials, Implant Contact and Biocompatibility
  - Sterilization, Packaging and Shelf-life
  - Implant-Related Residual Risks and Long-term Follow-up

- `surgical_instrument`
  - Cleaning, Sterilization and Reprocessing
  - Instrument Integrity, Mechanical Performance and Use-life
  - Procedure-Specific Use Risks

- `generic_medical_device`
  - Device-Class Specific Evidence Gap
  - This is used only when no high-confidence specific device-class template can be selected.

High-confidence locked domains take precedence over incidental source terms. For example, a cardiovascular RF ablation catheter remains on the therapeutic-catheter template even if generator/software-control text appears in the source profile.

## Writer Behavior

The selected conditional sections are injected into section 4.3.2A as device-class evidence requirements. Missing inputs remain explicit source gaps and must not be replaced with unrelated generic CER wording.

This directly targets the observed gap where AI CERs retained a generic CER structure and missed device-specific gold-reference sections.

## Tests

Commands executed:

```bash
backend/.venv/bin/python -m py_compile backend/packages/harness/deerflow/runtime/cer_authoring/pipeline.py backend/packages/harness/deerflow/runtime/cer_authoring/state.py backend/packages/harness/deerflow/runtime/cer_authoring/artifacts.py
backend/.venv/bin/python -m pytest backend/tests/test_cer_authoring_runtime.py -k "phase4_4 or phase4_3 or phase4_2 or phase4_1" -q
backend/.venv/bin/python -m pytest backend/tests/test_cer_authoring_runtime.py -q
```

Results:

- Phase 4A P4/P5 targeted runtime tests after selector-ordering hardening: `9 passed, 47 deselected`
- CER authoring runtime tests after P5: `56 passed`

## Acceptance

`IMPLEMENTED_ACCEPTED`

Effectiveness remains pending until the next semantic delta rerun checks whether device-specific section gaps shrink for CAL-001, CAL-002 and CAL-003.
