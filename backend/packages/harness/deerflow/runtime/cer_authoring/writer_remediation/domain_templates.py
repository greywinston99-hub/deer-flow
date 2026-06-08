"""Domain-specific CER Writer template skeletons — Phase 2A.

Each domain gets a clean template skeleton with:
- Section field mappings (IFU source → CER section)
- Domain-specific writing instructions (NO historical prose)
- Forbidden cross-domain terms in writer instructions
- Unknown domain block signal

CCD | 2026-05-15 | Phase 2A Source Fixes
"""

from __future__ import annotations

from typing import Any

# ── Known domains that have template skeletons ──────────────────────────────

KNOWN_DOMAINS: set[str] = {
    # Phase 2A pilot domains
    "cardiac_tissue_stabilizer",
    "contrast_imaging_bubble_study_system",
    "orthopedic_rf_plasma_electrode",
    "plasma_surgical_equipment",
    "plasma_surgical_electrode",
    "medical_imaging_software",
    "nuclear_medicine_image_processing_software",
    "ai_diagnostic_software",
    "diagnostic_software",
    # Existing pipeline template-supported domains
    "cardiovascular_rf_ablation_catheter",
    "surgical_ligating_clip",
    "urology_uas",
    "powered_therapeutic_equipment",
    # Generic family-dispatched domains (supported by family/function dispatch)
    "powered_equipment",
    "generic_implantable",
    "generic_disposable",
    "generic_powered",
    "monitoring_device",
    "life_supporting_device",
    "therapeutic_device",
    "diagnostic_device",
}

# ── Unknown domain blocking ─────────────────────────────────────────────────

UNKNOWN_DOMAIN_BLOCK = {
    "writer_allowed": False,
    "block_reason": "locked_domain is not recognised in the domain term matrix. Writer generation is blocked until the domain is defined by the owner/manufacturer.",
    "required_action": "Owner/manufacturer must provide device domain definition before CER authoring can proceed.",
    "fallback_template": None,
}

# ── IFU field-to-section mapping ────────────────────────────────────────────

IFU_FIELD_MAP: dict[str, dict[str, str]] = {
    "composition": {
        "cer_section": "2.1.2",
        "cer_label": "Device Composition / Variants",
        "ifu_source_type": "IFU",
        "description": "Physical components, materials, and model variants of the device.",
        "missing_fallback": "IFU source does not contain composition information.",
    },
    "working_principle": {
        "cer_section": "2.1.3",
        "cer_label": "Principle of Operation",
        "ifu_source_type": "IFU",
        "description": "How the device achieves its intended function.",
        "missing_fallback": "IFU source does not contain working principle information.",
    },
    "performance_summary": {
        "cer_section": "2.1.3",
        "cer_label": "Performance Characteristics",
        "ifu_source_type": "IFU",
        "description": "Key performance parameters as stated in the IFU.",
        "missing_fallback": "IFU source does not contain performance specification information.",
    },
    "sterility": {
        "cer_section": "2.1.4",
        "cer_label": "Sterility and Packaging",
        "ifu_source_type": "IFU",
        "description": "Sterilisation method, packaging, and shelf life.",
        "missing_fallback": "IFU source does not contain sterility or packaging information.",
    },
    "model_specifications": {
        "cer_section": "2.1.2",
        "cer_label": "Model Variants / Specifications",
        "ifu_source_type": "IFU",
        "description": "Available model variants with specifications.",
        "missing_fallback": "IFU source does not contain model specification information.",
    },
    "contraindications": {
        "cer_section": "2.2",
        "cer_label": "Contraindications",
        "ifu_source_type": "IFU",
        "description": "Contraindications stated in the IFU.",
        "missing_fallback": "IFU source does not contain explicit contraindication information.",
    },
    "intended_purpose": {
        "cer_section": "2.2",
        "cer_label": "Intended Purpose",
        "ifu_source_type": "IFU",
        "description": "IFU-stated intended purpose / indications for use.",
        "missing_fallback": "Intended purpose must be confirmed from the IFU source text.",
    },
    "target_population": {
        "cer_section": "2.2",
        "cer_label": "Target Population",
        "ifu_source_type": "IFU",
        "description": "Patient population for whom the device is intended.",
        "missing_fallback": "IFU source does not contain explicit target population information.",
    },
    "intended_user": {
        "cer_section": "2.2",
        "cer_label": "Intended User",
        "ifu_source_type": "IFU",
        "description": "Qualified user profile.",
        "missing_fallback": "IFU source does not contain explicit intended user information.",
    },
    "intended_environment": {
        "cer_section": "2.2",
        "cer_label": "Intended Use Environment",
        "ifu_source_type": "IFU",
        "description": "Clinical environment where the device is used.",
        "missing_fallback": "IFU source does not contain explicit environment information.",
    },
    "anatomical_site": {
        "cer_section": "2.2",
        "cer_label": "Anatomical Site",
        "ifu_source_type": "IFU",
        "description": "Anatomical location where the device is applied.",
        "missing_fallback": "IFU source does not contain explicit anatomical site information.",
    },
}


def get_ifu_field_instruction(field_name: str, source_text: str | None = None, source_anchor: str | None = None, confidence: str | None = None) -> str:
    """Generate a Writer instruction for an IFU-grounded field.

    If source_text is available, the Writer must use it verbatim with source anchor.
    If not available, the Writer must output the explicit missing fallback.
    """
    mapping = IFU_FIELD_MAP.get(field_name)
    if not mapping:
        return f"Describe {field_name} based on available IFU documentation."

    if source_text and source_text.strip() and source_text.strip() not in (
        "Not extracted from IFU source text; refer to subject device IFU for details.",
        "Not extracted from IFU source text",
        "Manufacturer not extracted from IFU source text",
    ):
        anchor = f" [SOURCE: {source_anchor}]" if source_anchor else ""
        conf = f" (confidence: {confidence})" if confidence else ""
        return (
            f"Write the {mapping['cer_label']} section ({mapping['cer_section']}) using the following "
            f"IFU-extracted content{conf}:\n\n{source_text.strip()}{anchor}\n\n"
            f"Do not replace this with placeholder text. Use the extracted IFU content as the primary source."
        )
    else:
        return (
            f"For the {mapping['cer_label']} section ({mapping['cer_section']}): "
            f"'{mapping['missing_fallback']}'. "
            f"Do NOT write 'Not extracted from IFU source text'. "
            f"State clearly that the IFU source does not contain this information."
        )


# ── Domain-specific template skeletons ──────────────────────────────────────


def cardiac_stabilizer_template_sections() -> list[dict[str, Any]]:
    """Cardiac Tissue Stabilizer domain — skeleton sections only, no historical prose."""
    return [
        {
            "row_id": "CS-2.1-DEVICE-DESC",
            "title": "2.1 Device Description — Cardiac Tissue Stabilizer",
            "rationale": "Cardiac tissue stabilizer used in CABG/off-pump surgery for mechanical stabilization of target vessel. Device domain: cardiac_tissue_stabilizer.",
            "required_inputs": "device_profile.composition, device_profile.working_principle, device_profile.model_specifications, device_profile.sterility, device_profile.shelf_life_storage, device_profile.performance_summary, document_structured_content (source_type=IFU)",
            "writer_instruction": (
                "Describe the cardiac tissue stabilizer device. Use IFU-extracted data for composition, "
                "working principle, performance, sterility, and model variants. "
                "The device is a mechanical stabilizer for cardiac tissue during CABG. "
                "Do NOT write about ureteroscopes, UAS, urology, stone burden, urinary tract, endourology, "
                "or PADN/pulmonary artery ablation. These are FORBIDDEN cross-domain terms for this device. "
                "Do NOT reuse template text from other device domains. "
                "Each field must have a source anchor from the IFU or state "
                "'IFU source does not contain this information' if absent."
            ),
            "section_target": "2.1",
        },
        {
            "row_id": "CS-2.2-INTENDED-PURPOSE",
            "title": "2.2 Intended Purpose — Cardiac Tissue Stabilizer",
            "rationale": "Mechanical cardiac stabilizer for CABG, not an energy-delivery or urological device.",
            "required_inputs": "device_profile.intended_purpose, device_profile.target_population, device_profile.anatomical_site, device_profile.contraindications, document_structured_content (source_type=IFU)",
            "writer_instruction": (
                "State the intended purpose as: mechanical stabilization of cardiac tissue during "
                "coronary artery bypass grafting (CABG), including off-pump (OPCAB) procedures. "
                "The device creates a stable working field on the beating heart at the target vessel. "
                "Target population: adult patients undergoing CABG. "
                "Do NOT mention ablation, energy delivery, ureteroscopy, or urological procedures. "
                "These are FORBIDDEN cross-domain terms."
            ),
            "section_target": "2.2",
        },
        {
            "row_id": "CS-3-CLINICAL-BACKGROUND",
            "title": "3 Clinical Background — Cardiac Surgery / CABG",
            "rationale": "The clinical domain is cardiac surgery, specifically coronary artery bypass grafting.",
            "required_inputs": "SOTA search results for CABG, off-pump surgery, coronary artery disease",
            "writer_instruction": (
                "Describe the clinical background of coronary artery disease (CAD) and CABG surgery. "
                "Cover: prevalence of CAD, standard surgical treatment (CABG on-pump vs off-pump OPCAB), "
                "role of cardiac tissue stabilizers in off-pump surgery, clinical outcomes, "
                "guidelines (ESC/EACTS, AHA/ACC), and alternative treatments (PCI, medical management). "
                "Clinical domain is CARDIAC SURGERY. "
                "Do NOT write about urology, ureteroscopy, stone disease, PADN, or atrial fibrillation ablation."
            ),
            "section_target": "3.1",
        },
        {
            "row_id": "CS-5-CONCLUSIONS",
            "title": "5 Conclusions — Cardiac Tissue Stabilizer",
            "rationale": "Conclusions must follow claim_support_matrix and writer_conclusion_constraints.",
            "required_inputs": "claim_support_matrix, writer_conclusion_constraints, benefit_risk_conclusion",
            "writer_instruction": (
                "Write conclusions consistent with claim_support_matrix support levels. "
                "If claims are INSUFFICIENT, state that evidence is insufficient to conclude. "
                "If claims are CAUTIOUS, use limited/conditional language. "
                "Do NOT write 'clinical data support' for INSUFFICIENT claims. "
                "Follow writer_conclusion_constraints for allowed and forbidden wording."
            ),
            "section_target": "5",
        },
    ]


def contrast_bubble_study_template_sections() -> list[dict[str, Any]]:
    """Bubble-study contrast imaging system domain — skeleton sections only."""
    return [
        {
            "row_id": "BS-2.1-DEVICE-DESC",
            "title": "2.1 Device Description — Bubble Study System",
            "rationale": "Automated agitated-saline preparation/injection system used with disposable contrast injection tubing for ultrasound bubble-study procedures.",
            "required_inputs": "device_profile.composition, device_profile.working_principle, device_profile.model_specifications, device_profile.performance_summary, IFU source text, RMF controls",
            "writer_instruction": (
                "Describe the Bubble Study System as an agitated-saline preparation and injection system "
                "used with Disposable Contrast Injection Tubing Set for c-TTE and/or c-TCD bubble-study procedures. "
                "Use IFU-extracted device composition, model variants, working principle, disposable tubing, and monitoring information. "
                "Do NOT write about stents, CABG stabilizers, pulmonary vein ablation, urology, plasma surgery, arthroscopy, or nuclear medicine software. "
                "If IFU fields are missing, state the controlled gap and do not invent device specifications."
            ),
            "section_target": "2.1",
        },
        {
            "row_id": "BS-2.2-INTENDED-PURPOSE",
            "title": "2.2 Intended Purpose — RLS/PFO Bubble Study",
            "rationale": "Clinical use is agitated-saline bubble-study assessment of suspected right-to-left shunt/PFO.",
            "required_inputs": "device_profile.intended_purpose, target_population, intended_user, anatomical_site, contraindications, IFU warnings",
            "writer_instruction": (
                "State the intended purpose in terms of IFU-defined preparation/injection of agitated saline "
                "for transthoracic echocardiographic contrast imaging or contrast-enhanced transcranial Doppler assessment. "
                "Identify the target population as patients suspected of right-to-left shunt/PFO when supported by IFU source data. "
                "Describe trained cardiac/neurology ultrasound users, Valsalva cooperation requirements, contraindications, and monitoring needs."
            ),
            "section_target": "2.2",
        },
        {
            "row_id": "BS-3-CLINICAL-BACKGROUND",
            "title": "3 Clinical Background — Agitated-Saline Bubble Study",
            "rationale": "The clinical domain is ultrasound contrast bubble-study assessment of right-to-left shunt/PFO.",
            "required_inputs": "SOTA search results, clinical guidelines, RLS/PFO diagnostic pathway literature, comparator modalities c-TTE/c-TCD/TEE",
            "writer_instruction": (
                "Describe the clinical background of right-to-left shunt and patent foramen ovale assessment. "
                "Cover the role of agitated-saline bubble study, c-TTE, c-TCD, TEE comparators, Valsalva maneuver, "
                "diagnostic concordance, shunt grading, and safety considerations. "
                "Separate SOTA context from subject-device clinical evidence, and mark unrelated ablation, stent, urology, or software literature as excluded/background only."
            ),
            "section_target": "3.1",
        },
        {
            "row_id": "BS-5-CONCLUSIONS",
            "title": "5 Conclusions — Bubble Study System",
            "rationale": "Conclusions must follow claim_support_matrix, benefit-risk closure, and PMCF/PMS controls.",
            "required_inputs": "claim_support_matrix, benefit_risk_closure_matrix, pmcf_plan_control_matrix, writer_conclusion_constraints",
            "writer_instruction": (
                "Write conclusions only to the level supported by approved claims, evidence strength, RMF, PMS/PMCF, and benefit-risk closure. "
                "If direct subject-device evidence is incomplete, state controlled uncertainty and PMCF objectives. "
                "Do NOT conclude acceptable benefit-risk or diagnostic benefit beyond the approved evidence ceiling."
            ),
            "section_target": "5",
        },
    ]


def orthopedic_plasma_electrode_template_sections() -> list[dict[str, Any]]:
    """Orthopedic RF Plasma Electrode domain — skeleton sections only."""
    return [
        {
            "row_id": "PE-2.1-DEVICE-DESC",
            "title": "2.1 Device Description — RF Plasma Surgical Electrode",
            "rationale": "Radiofrequency plasma electrode for arthroscopic/orthopedic soft tissue surgery.",
            "required_inputs": "device_profile.composition, device_profile.working_principle, device_profile.performance, document_structured_content (source_type=IFU)",
            "writer_instruction": (
                "Describe the RF plasma surgical electrode. The electrode delivers radiofrequency energy "
                "in saline to create a plasma field for soft tissue resection, ablation, coagulation, and hemostasis. "
                "Intended for arthroscopic or open joint surgery (knee, shoulder, hip). "
                "Do NOT write about cardiac ablation, PADN, pulmonary artery, atrial fibrillation, "
                "ureteroscopy, urology, urinary tract, stone burden, or endourology. "
                "These are FORBIDDEN cross-domain terms for this device. "
                "Each field must have a source anchor from the IFU."
            ),
            "section_target": "2.1",
        },
        {
            "row_id": "PE-2.2-INTENDED-PURPOSE",
            "title": "2.2 Intended Purpose — RF Plasma Electrode",
            "rationale": "Orthopedic/arthroscopic soft tissue surgery device, not cardiac or urological.",
            "required_inputs": "device_profile.intended_purpose, device_profile.target_population, device_profile.anatomical_site",
            "writer_instruction": (
                "State the intended purpose: resection, ablation, coagulation, and hemostasis of soft tissues "
                "in arthroscopic/open joint surgery under saline irrigation. "
                "The electrode is used with a compatible RF generator. "
                "Anatomical sites: knee, shoulder, hip (and other joints as IFU-specified). "
                "Do NOT mention cardiac ablation, PADN, ureteroscopy, or urological procedures."
            ),
            "section_target": "2.2",
        },
        {
            "row_id": "PE-3-CLINICAL-BACKGROUND",
            "title": "3 Clinical Background — Orthopedic / Arthroscopic Surgery",
            "rationale": "The clinical domain is orthopedic surgery, specifically arthroscopy.",
            "required_inputs": "SOTA search results for arthroscopy, RF ablation in joints, sports medicine",
            "writer_instruction": (
                "Describe the clinical background of arthroscopic joint surgery. "
                "Cover: common joint procedures (meniscectomy, cartilage debridement, synovectomy), "
                "role of RF plasma devices in arthroscopy, clinical outcomes, guidelines, "
                "and alternative techniques (mechanical shaver, conventional electrosurgery). "
                "Clinical domain is ORTHOPEDIC / ARTHROSCOPIC SURGERY. "
                "Do NOT write about cardiac ablation, pulmonary vein isolation, "
                "ureteroscopy, or stone disease."
            ),
            "section_target": "3.1",
        },
        {
            "row_id": "PE-5-CONCLUSIONS",
            "title": "5 Conclusions — RF Plasma Electrode",
            "rationale": "Conclusions must follow claim_support_matrix constraints.",
            "required_inputs": "claim_support_matrix, writer_conclusion_constraints, benefit_risk_conclusion",
            "writer_instruction": (
                "Write conclusions consistent with claim_support_matrix support levels. "
                "Do NOT write 'clinical data support' for INSUFFICIENT claims. "
                "Follow writer_conclusion_constraints for allowed and forbidden wording."
            ),
            "section_target": "5",
        },
    ]


def imaging_software_template_sections() -> list[dict[str, Any]]:
    """Medical Imaging Software domain (SaMD) — skeleton sections only."""
    return [
        {
            "row_id": "IS-2.1-DEVICE-DESC",
            "title": "2.1 Device Description — Medical Imaging Software",
            "rationale": "Software as Medical Device (SaMD) for medical image processing. No physical components.",
            "required_inputs": "device_profile, software_description, algorithm_description, document_structured_content",
            "writer_instruction": (
                "Describe the medical imaging software as a Software as Medical Device (SaMD). "
                "The product is pure software — it has NO physical components, NO sterility requirements, "
                "NO shelf life, NO biocompatibility concerns. "
                "Describe: software architecture, input (DICOM images), processing algorithms, "
                "output (processed images / quantitative results), intended use environment (PACS workstation). "
                "Do NOT write about catheters, implants, sterility, shelf life, surgical access, or endoscopic procedures. "
                "These are FORBIDDEN terms for a software-only device. "
                "Reference IEC 62304 software lifecycle classification."
            ),
            "section_target": "2.1",
        },
        {
            "row_id": "IS-2.2-INTENDED-PURPOSE",
            "title": "2.2 Intended Purpose — Imaging Software",
            "rationale": "SaMD for diagnostic image processing and analysis.",
            "required_inputs": "device_profile.intended_purpose, software_intended_use",
            "writer_instruction": (
                "State the intended purpose: medical image processing and analysis software that "
                "receives DICOM input, applies algorithms for image enhancement/quantification/analysis, "
                "and outputs processed images or quantitative measurements to assist clinical assessment. "
                "The software does NOT make independent diagnostic decisions. "
                "It is intended for use by qualified radiologists/healthcare professionals. "
                "Do NOT describe physical device attributes (sterility, shelf life, biocompatibility)."
            ),
            "section_target": "2.2",
        },
        {
            "row_id": "IS-3-CLINICAL-BACKGROUND",
            "title": "3 Clinical Background — Medical Imaging / Radiology",
            "rationale": "The clinical domain is diagnostic imaging and radiology workflow.",
            "required_inputs": "SOTA search results for medical imaging software, AI in radiology, image processing",
            "writer_instruction": (
                "Describe the clinical background of medical imaging and radiology workflow. "
                "Cover: role of image processing in diagnostic radiology, current software tools, "
                "clinical guidelines for imaging-based diagnosis, performance metrics (sensitivity, specificity). "
                "Clinical domain is MEDICAL IMAGING / RADIOLOGY. "
                "Do NOT write about interventional procedures, surgical devices, or implantables."
            ),
            "section_target": "3.1",
        },
        {
            "row_id": "IS-5-CONCLUSIONS",
            "title": "5 Conclusions — Imaging Software",
            "rationale": "Conclusions must follow claim_support_matrix.",
            "required_inputs": "claim_support_matrix, writer_conclusion_constraints, benefit_risk_conclusion",
            "writer_instruction": (
                "Write conclusions consistent with claim_support_matrix support levels. "
                "Do NOT claim clinical validation without supporting evidence. "
                "Follow writer_conclusion_constraints for allowed and forbidden wording."
            ),
            "section_target": "5",
        },
    ]


def therapeutic_catheter_template_sections() -> list[dict[str, Any]]:
    """Cardiovascular RF Ablation Catheter domain — skeleton sections.

    This domain's primary template is in pipeline.py (_therapeutic_catheter_template_sections).
    These skeleton sections provide the domain boundary contract for domain_templates.py.
    """
    return [
        {
            "row_id": "TC-2.1-DEVICE-DESC",
            "title": "2.1 Device Description — RF Ablation Catheter",
            "rationale": "Cardiovascular RF ablation catheter for PADN/pulmonary artery denervation. Device domain: cardiovascular_rf_ablation_catheter.",
            "required_inputs": "device_profile.composition, device_profile.working_principle, document_structured_content (source_type=IFU)",
            "writer_instruction": (
                "Describe the RF ablation catheter device. The device delivers radiofrequency energy "
                "via a catheter for pulmonary artery denervation (PADN) or cardiac ablation. "
                "The device is a therapeutic catheter — it enters the vasculature, delivers energy, "
                "and is single-use sterile. "
                "Do NOT write about arthroscopy, orthopedic joints, ureteroscopy, UAS, urology, "
                "stone burden, or soft tissue resection. These are FORBIDDEN cross-domain terms."
            ),
            "section_target": "2.1",
        },
        {
            "row_id": "TC-5-CONCLUSIONS",
            "title": "5 Conclusions — RF Ablation Catheter",
            "rationale": "Conclusions must follow claim_support_matrix constraints.",
            "required_inputs": "claim_support_matrix, writer_conclusion_constraints, benefit_risk_conclusion",
            "writer_instruction": (
                "Write conclusions consistent with claim_support_matrix support levels. "
                "Do NOT write 'clinical data support' for INSUFFICIENT claims."
            ),
            "section_target": "5",
        },
    ]


def surgical_ligating_clip_template_sections() -> list[dict[str, Any]]:
    """Surgical Ligating Clip domain — skeleton sections.

    This domain's primary template is in pipeline.py (_surgical_implant_ligating_clip_template_sections).
    These skeleton sections provide the domain boundary contract for domain_templates.py.
    """
    return [
        {
            "row_id": "LC-2.1-DEVICE-DESC",
            "title": "2.1 Device Description — Surgical Ligating Clip",
            "rationale": "Implantable surgical ligating clip for vessel/tissue ligation.",
            "required_inputs": "device_profile.composition, device_profile.working_principle, document_structured_content (source_type=IFU)",
            "writer_instruction": (
                "Describe the surgical ligating clip device. The device is an implantable clip "
                "for ligating blood vessels or tissue structures during surgery. "
                "It is typically titanium or polymer, single-use, sterile, and permanently implanted. "
                "Do NOT write about energy delivery, ablation, arthroscopy, or ureteroscopy. "
                "These are FORBIDDEN cross-domain terms."
            ),
            "section_target": "2.1",
        },
        {
            "row_id": "LC-5-CONCLUSIONS",
            "title": "5 Conclusions — Surgical Ligating Clip",
            "rationale": "Conclusions must follow claim_support_matrix.",
            "required_inputs": "claim_support_matrix, writer_conclusion_constraints, benefit_risk_conclusion",
            "writer_instruction": (
                "Write conclusions consistent with claim_support_matrix support levels."
            ),
            "section_target": "5",
        },
    ]


# ── Domain template dispatch ────────────────────────────────────────────────

DOMAIN_TEMPLATE_MAP: dict[str, Any] = {
    "cardiac_tissue_stabilizer": cardiac_stabilizer_template_sections,
    "contrast_imaging_bubble_study_system": contrast_bubble_study_template_sections,
    "orthopedic_rf_plasma_electrode": orthopedic_plasma_electrode_template_sections,
    "plasma_surgical_equipment": orthopedic_plasma_electrode_template_sections,
    "plasma_surgical_electrode": orthopedic_plasma_electrode_template_sections,
    "medical_imaging_software": imaging_software_template_sections,
    "nuclear_medicine_image_processing_software": imaging_software_template_sections,
    "ai_diagnostic_software": imaging_software_template_sections,
    "diagnostic_software": imaging_software_template_sections,
    "cardiovascular_rf_ablation_catheter": therapeutic_catheter_template_sections,
    "surgical_ligating_clip": surgical_ligating_clip_template_sections,
}


def get_domain_template_sections(clinical_domain: str) -> list[dict[str, Any]] | None:
    """Return domain-specific template sections for a known domain, or None."""
    builder = DOMAIN_TEMPLATE_MAP.get(clinical_domain)
    if builder:
        return builder()
    return None


def is_domain_known(clinical_domain: str) -> bool:
    """Check whether a clinical_domain has a defined template."""
    return clinical_domain in KNOWN_DOMAINS or clinical_domain in DOMAIN_TEMPLATE_MAP


def block_if_unknown(clinical_domain: str) -> dict[str, Any] | None:
    """Return a Writer block dict if the domain is unknown, else None."""
    if not clinical_domain or clinical_domain in {"generic_unknown", "unknown", ""}:
        return dict(UNKNOWN_DOMAIN_BLOCK)
    if not is_domain_known(clinical_domain):
        return {
            "writer_allowed": False,
            "block_reason": f"locked_domain '{clinical_domain}' is not in the domain template matrix. Writer generation is blocked until the domain is defined.",
            "required_action": "Owner/manufacturer must provide device domain definition and domain term matrix entry before CER authoring.",
            "fallback_template": None,
        }
    return None


# ── IFU field consumption helper ────────────────────────────────────────────


def build_ifu_grounded_device_fields(
    device_profile: dict[str, Any],
    document_structured_content: list[dict[str, Any]] | None = None,
) -> dict[str, dict[str, Any]]:
    """Build device description fields with IFU source grounding.

    For each field in IFU_FIELD_MAP, looks up document_structured_content for
    source_type=IFU entries. Returns {field_name: {text, source_anchor, confidence}}.

    Fields without IFU data get explicit data gap status (not placeholder text).
    """
    ifu_entries: dict[str, list[dict[str, Any]]] = {}
    for entry in (document_structured_content or []):
        if isinstance(entry, dict) and str(entry.get("source_type") or "").upper() in ("IFU", "SUBJECT_DEVICE_IFU"):
            # Map entry to relevant fields based on content
            text = str(entry.get("text") or entry.get("content") or "")
            source_anchor = str(entry.get("source_anchor") or entry.get("source_id") or entry.get("filename") or "")
            confidence = str(entry.get("confidence") or entry.get("extraction_confidence") or "medium")
            # Store by source for later field matching
            source = entry.get("source_id") or entry.get("filename") or "IFU"
            if source not in ifu_entries:
                ifu_entries[source] = []
            ifu_entries[source].append({
                "text": text,
                "source_anchor": source_anchor,
                "confidence": confidence,
            })

    result: dict[str, dict[str, Any]] = {}
    for field_name in IFU_FIELD_MAP:
        # First check if device_profile already has non-placeholder data
        dp_value = device_profile.get(field_name, "")
        if dp_value and isinstance(dp_value, str) and dp_value.strip() and not dp_value.startswith("Not extracted from IFU") and not dp_value.startswith("Manufacturer not extracted"):
            result[field_name] = {
                "text": dp_value.strip(),
                "source_anchor": "device_profile (IFU/source_inventory)",
                "confidence": device_profile.get("classification_confidence") or "high",
                "source": "device_profile",
            }
            continue

        # Search document_structured_content for IFU entries matching this field
        found = False
        for source, entries in ifu_entries.items():
            for entry in entries:
                text = entry["text"]
                # Simple keyword matching to associate IFU text with fields
                if _text_relates_to_field(field_name, text):
                    result[field_name] = {
                        "text": text[:2000],
                        "source_anchor": entry["source_anchor"],
                        "confidence": entry["confidence"],
                        "source": source,
                    }
                    found = True
                    break
            if found:
                break

        if not found:
            result[field_name] = {
                "text": "",
                "source_anchor": "",
                "confidence": "data_gap",
                "source": "none",
                "data_gap": True,
            }

    return result


def _text_relates_to_field(field_name: str, text: str) -> bool:
    """Simple keyword-based field-to-text relevance check.

    KNOWN LIMITATION: This is a substring-based keyword matcher, not a semantic classifier.
    False positives are possible for short keywords (e.g., "or " in intended_environment).
    The fallback for mismatched fields is that the Writer instruction still includes the
    correct field mapping (cer_section + cer_label), so the Writer agent has structural
    context to disambiguate. A planned improvement is replacing this with structured
    intake field tags (source_type + field_name in document_structured_content entries).
    This matcher is adequate for Phase 2 as a first-pass filter; gate-level validation
    (IFU consumption gate) catches major mismatches.
    """
    text_lower = text.lower()
    field_keywords: dict[str, list[str]] = {
        "composition": ["compos", "consist", "material", "component", "assembly", "part"],
        "working_principle": ["principle", "mechanism", "function", "operat", "energy", "mode of action"],
        "performance_summary": ["performance", "specification", "parameter", "output", "accuracy"],
        "sterility": ["steril", "eo", "packaging", "shelf life", "shelf-life", "expiry"],
        "model_specifications": ["model", "variant", "specification", "version", "size", "configuration"],
        "contraindications": ["contraindication", "do not use", "not intended", "contra-indication"],
        "intended_purpose": ["intended purpose", "indicated for", "intended use", "indication"],
        "target_population": ["patient", "population", "adult", "pediatric", "indicated for"],
        "intended_user": ["healthcare", "physician", "surgeon", "qualified", "professional", "clinician"],
        "intended_environment": ["environment", "hospital", "clinic", "operating room", "or ", "clinical setting"],
        "anatomical_site": ["anatomical", "site", "tissue", "joint", "vessel", "cardiac", "artery", "soft tissue"],
    }
    keywords = field_keywords.get(field_name, [field_name])
    return any(kw in text_lower for kw in keywords)
