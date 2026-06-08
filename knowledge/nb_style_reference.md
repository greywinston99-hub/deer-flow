# NB Style Reference (V22 Pass 4A Grounding)

**Version**: V22.0 | **Used by**: GS Stage 8 (NB Simulation)

Real NB questions from calibration projects. Used to ground the NB simulation prompt — GS learns the style, specificity, and evidence-referencing patterns that real NBs use, then generates questions in the same style.

**Rule**: NEVER use these exact questions. Use them as STYLE REFERENCE only. Generated questions must be about the CURRENT project's device and documents.

---

## BSI MDR — Clinical Reasoning Style (Dr Daniel Taylor)

### From PROJECT_041 (Cold Pack, Class IIa)
- Q: "GSPR 23.4 requires the IFU to state methods for safe disposal. I am unable to find this in the IFU."
  - **Style**: Clause-anchored. Cites specific GSPR sub-clause. States what is missing and where it should be.
- Q: "Please provide evidence that for ALL populations the benefit outweighs the risk."
  - **Style**: Population-stratified. Demands evidence coverage across all indicated groups.
- Q: "The CER section on safety is insufficient — it presents a bald statement with no consideration of evidence."
  - **Style**: Evidence-grounded. Rejects unsupported claims. Demands evidence for every assertion.
- Q: "Using the IFU Warning & Caution Hazard Trace List, it is not possible to confirm that IFU warnings have mitigations for the identified hazards."
  - **Style**: Traceability-focused. Checks that document references are bidirectional and verifiable.
- Q: "How does the PMCF plan address the specific clinical evidence gaps identified in the CER?"
  - **Style**: Cross-document integration. Checks that findings in one document feed into another.

### From PROJECT_012 (SPECT/CT, Class IIb, BSI)
- Q: "How does the evidence presented demonstrate that the device provides specific CT operating conditions for performing children scans based on factors such as the child's age, height, and weight?"
  - **Style**: Performance-evidence linked. Demands that claimed functionality has measurable verification.
- Q: "H45, H46, H47 have been addressed but there are other examples which still do not reference the IFU in the mitigation: H65, H69, H94, H96 and more."
  - **Style**: Systematic gap identification. Finds pattern across multiple instances, not just one-off.
- Q: "Please identify where ALL cybersecurity risks have been identified and considered."
  - **Style**: Completeness demand. "ALL" is explicit — partial coverage is insufficient.

---

## DEKRA MDR — Technical Documentation Review Style

### From PROJECT_017 (HF Surgical Generator, Class IIb)
- Q: "It cannot be ensured that the contra-indications of the device have been clearly described in the IFU."
  - **Style**: Negative verification. "Cannot be ensured" = evidence insufficient to confirm compliance.
- Q: "It cannot be verified that risk reduction endpoints have been defined clearly to ensure risks were reduced as far as possible."
  - **Style**: Process-traceability. Checks that risk management process deliverables exist and are verifiable.
- Q: "After 10-minute search, it cannot be verified that the following hazards are identified, assessed, controlled and verified in the risk management documentation."
  - **Style**: Searchability concern. If a reviewer can't find it in 10 minutes, the documentation is not adequately organized.
- Q: "The software was classified as safety classification level A. However, no specific rationale of classification was found."
  - **Style**: Classification justification. Demands explicit rationale for regulatory classification decisions.
- Q: "Acceptance criteria in the Performance Test Summary is inconsistent with the Technical Requirements."
  - **Style**: Cross-document consistency. Identifies numerical/technical conflicts between related documents.

### From PROJECT_013 (Powered Surgical Stapler, Class IIb, DEKRA)
- Q: "No description of software architectural design identifying the modules/functional units and their interfaces."
  - **Style**: Standards-referencing. Implicitly references IEC 62304 §5.3 requirements.
- Q: "CNEMB60 was selected as worst-case representative. Please clarify why CNP series (with different battery pack and larger package size) was not selected."
  - **Style**: Worst-case justification. Challenges engineering assumptions with specific model comparisons.

---

## TUV Rheinland — Comprehensive MDR Audit Style

### From PROJECT_017 (Additional)
- Q: "Pls. re-confirm the Method of Conformity of GSPR, which was incomplete for every clause."
  - **Style**: Systematic deficiency. "Every clause" — not just one or two missing references.
- Q: "The EN ISO13485, EN ISO10993 standard and MDCG should be considered into GSPR."
  - **Style**: Standards-gap identification. Names specific standards that should be referenced but aren't.

---

## TUV SUD — Technical File Review Style

### From PROJECT_037 (Surgical Gloves, Class I/IIa, TUV SUD)
- Q: "The warnings and precautions are missing."
  - **Style**: Completeness-first. Identifies missing sections before diving into detail.
- Q: "Whether the device is powder-free gloves or powdered glove? Pls clarify."
  - **Style**: Specification verification. Checks that device description is consistent and unambiguous.
- Q: "In 1.1.4, it mentioned powder on gloves surface should be removed, while in 1.1.1 the device are described as powder-free device. Pls clarify."
  - **Style**: Internal contradiction detection. Finds conflicts within the same document.
- Q: "Why only one similar device was identified?"
  - **Style**: Equivalence breadth check. Questions narrow equivalence device selection.
- Q: "The UDI carrier is missing. An indication that the device is a medical device is missing. The sterilisation method is missing."
  - **Style**: Labeling exhaustiveness. Systematically lists every missing labeling element.
- Q: "Pls provide list of EU countries in which the device is marketed."
  - **Style**: Market history verification. Checks post-market surveillance scope.

### TUV SUD Style Characteristics
- Device description exhaustiveness — every material, every specification, every variant
- Physical/chemical characterization emphasis
- Shelf life and packaging validation documentation
- EN 455 series compliance (for medical gloves) — anchor to specific product standards
- Labeling completeness — UDI, symbols, sterilization method, medical device indication
- Internal consistency — flags contradictions within the same technical documentation

---

## Style Patterns Summary

| NB Type | Question Pattern | Key Characteristics |
|---------|-----------------|-------------------|
| BSI Clinical | "I am unable to find X in document Y" | Specific, clause-anchored, evidence-referencing |
| BSI Clinical | "Please provide evidence that for ALL populations..." | Population-stratified, completeness demand |
| BSI Clinical | "X section is insufficient — it presents a bald statement" | Evidence-grounded, rejects unsupported claims |
| DEKRA Technical | "It cannot be ensured/verified that..." | Negative verification, process-traceability |
| DEKRA Technical | "After 10-minute search, it cannot be verified..." | Searchability standard, documentation organization |
| DEKRA Technical | "No specific rationale/justification was found" | Classification/d ecision justification |
| TUV Audit | "Pls. re-confirm... which was incomplete for every clause" | Systematic deficiency, completeness audit |
| TUV SUD | "The [X] is missing. The [Y] is missing. The [Z] is missing." | Labeling exhaustiveness, specification verification |
| TUV SUD | "Whether the device is powder-free or powdered? Pls clarify." | Internal contradiction detection, description consistency |

**When generating NB simulation questions**:
1. Match the target NB's style pattern (BSI=evidence-referencing, DEKRA=negative-verification, TUV=systematic)
2. Anchor every question to a specific document section, GSPR clause, or standard reference
3. Never ask: "Is the CER complete?" or "Are there any gaps?"
4. Always ask: "I cannot find [specific content] in [specific section]. [Regulatory basis]. Please provide."
