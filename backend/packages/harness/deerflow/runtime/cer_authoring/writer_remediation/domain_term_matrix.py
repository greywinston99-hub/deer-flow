"""Domain Term Matrix V1 — Embedded authoritative data for Gate 1 device domain consistency.

This module is the runnable version of DOMAIN_TERM_MATRIX_V1.md. It maps
device_domain values from device_profile.json to forbidden/allowed/required/ambiguous
term lists and exception context rules.

CCD | 2026-05-15 | Authoritative for Gate 1
"""

from __future__ import annotations

# Map from device_profile.json `device_domain` field values to matrix domain keys.
DEVICE_DOMAIN_TO_MATRIX_DOMAIN: dict[str, str] = {
    "cardiac_tissue_stabilizer": "cardiac_tissue_stabilizer",
    "plasma_surgical_electrode": "orthopedic_rf_plasma_electrode",
    "orthopedic_rf_plasma_electrode": "orthopedic_rf_plasma_electrode",
    "medical_imaging_software": "medical_imaging_software",
    "ai_diagnostic_software": "medical_imaging_software",
    "diagnostic_software": "medical_imaging_software",
    "cardiovascular_rf_ablation_catheter": "cardiovascular_rf_ablation_catheter",
    "urology_uas": "urology_uas",
}


DOMAIN_TERM_MATRIX: dict[str, dict] = {
    "cardiac_tissue_stabilizer": {
        "label": "Cardiac Tissue Stabilizer",
        "description": (
            "心脏组织固定器。CABG/off-pump 冠脉搭桥术中通过负压吸附或机械压迫"
            "稳定靶血管区域。不进入体内腔道，不含能量输出，不涉及泌尿系统。"
        ),
        "required_terms": [
            "cardiac tissue stabilizer", "tissue stabilizer", "heart stabilizer",
            "coronary artery bypass", "CABG", "OPCAB", "off-pump", "beating heart",
            "anastomosis", "target vessel", "myocardial revascularization",
            "sternotomy", "thoracotomy", "cardiac surgery", "suction stabilization",
            "mechanical stabilization",
        ],
        "allowed_terms": [
            "coronary artery disease", "CAD", "left anterior descending", "LAD",
            "internal mammary artery", "saphenous vein graft", "cardiopulmonary bypass",
            "CPB", "conversion to CPB", "hemodynamic stability", "graft patency",
            "perioperative", "median sternotomy",
        ],
        "forbidden_terms": [
            "ureteroscope", "UAS", "ureteral access sheath", "urinary tract",
            "ureter", "renal insufficiency", "stone burden", "urolithiasis",
            "hydrophilic coating", "endourology", "urological endoscopy",
            "percutaneous nephrolithotomy", "PCNL", "flexible ureteroscopy",
            "fURS", "suction sheath", "negative-pressure access sheath",
            "guidewire",
        ],
        "ambiguous_terms": [
            "stabilizer", "suction", "negative pressure",
        ],
        "exception_contexts": [
            "excluded", "not applicable", "differs from", "unlike", "in contrast to",
        ],
        "section_scope": [
            "SUMMARY", "DEVICE DESCRIPTION", "INTENDED PURPOSE",
            "CLINICAL BACKGROUND", "DEVICE UNDER EVALUATION", "CONCLUSIONS",
            "1.", "2.1", "2.2", "3.1", "3.2", "3.3", "3.4", "3.5",
            "3.6", "3.7", "3.8", "4.1", "4.2", "4.3", "4.4", "4.5",
            "4.6", "4.7", "5.",
        ],
        "annex_excluded": True,
    },
    "orthopedic_rf_plasma_electrode": {
        "label": "Orthopedic RF Plasma Electrode",
        "description": (
            "射频等离子手术电极。关节镜/开放手术下，利用射频能量在生理盐水中"
            "产生等离子场，对软组织进行切除、消融、凝固和止血。涉及关节腔"
            "（膝、肩、髋等），不涉及泌尿系统、心脏介入、神经外科。"
        ),
        "required_terms": [
            "radiofrequency", "RF", "plasma", "electrode", "arthroscopy",
            "arthroscopic", "joint", "soft tissue", "resection", "ablation",
            "coagulation", "hemostasis", "saline", "thermal", "knee", "shoulder",
            "hip", "meniscus", "cartilage", "synovial", "ligament",
        ],
        "allowed_terms": [
            "orthopedic", "sports medicine", "articular", "chondral",
            "debridement", "lavage", "shaver", "irrigation", "saline irrigation",
            "thermal injury", "collateral damage", "depth of penetration",
        ],
        "forbidden_terms": [
            "ureteral access sheath", "ureteroscope", "urolithiasis",
            "urinary tract", "renal insufficiency", "stone burden",
            "endourology", "cardiac ablation", "PADN", "pulmonary artery",
            "atrial fibrillation", "pulmonary vein", "catheter ablation",
            "guidewire", "endoscopic access sheath", "UAS",
        ],
        "ambiguous_terms": [
            "ablation", "resection", "electrode",
        ],
        "exception_contexts": [
            "excluded", "not applicable", "differs from", "unlike", "in contrast to",
        ],
        "section_scope": [
            "SUMMARY", "DEVICE DESCRIPTION", "INTENDED PURPOSE",
            "CLINICAL BACKGROUND", "DEVICE UNDER EVALUATION", "CONCLUSIONS",
            "1.", "2.1", "2.2", "3.1", "3.2", "3.3", "3.4", "3.5",
            "3.6", "3.7", "3.8", "4.1", "4.2", "4.3", "4.4", "4.5",
            "4.6", "4.7", "5.",
        ],
        "annex_excluded": True,
    },
    "medical_imaging_software": {
        "label": "Medical Imaging Software",
        "description": (
            "医学影像处理软件。Software as Medical Device。接收 DICOM 影像输入，"
            "执行图像处理/分析算法，输出处理后的图像或量化结果。纯软件产品，"
            "无物理器械、无患者接触。"
        ),
        "required_terms": [
            "medical imaging software", "image processing", "DICOM", "PACS",
            "workstation", "software", "algorithm", "image analysis",
            "visualization", "rendering", "quantification", "segmentation",
            "registration", "diagnostic", "screening", "detection", "radiology",
        ],
        "allowed_terms": [
            "CT", "MRI", "X-ray", "ultrasound", "mammography", "AI",
            "deep learning", "CNN", "FDA 510k", "MDR", "IEC 62304",
            "software lifecycle", "SIL", "SOUP",
        ],
        "forbidden_terms": [
            "catheter", "implant", "sterile", "shelf life", "biocompatibility",
            "surgical access", "endoscopic", "ureteroscope",
            "cardiac ablation", "PADN", "pulmonary artery",
            "atrial fibrillation", "pulmonary vein", "ureteral access sheath",
            "urolithiasis", "urinary tract", "stone burden",
            "guidewire", "UAS", "endourology",
        ],
        "ambiguous_terms": [
            "clinical data", "device",
        ],
        "exception_contexts": [
            "excluded", "not applicable", "differs from", "unlike", "in contrast to",
        ],
        "section_scope": [
            "SUMMARY", "DEVICE DESCRIPTION", "INTENDED PURPOSE",
            "CLINICAL BACKGROUND", "DEVICE UNDER EVALUATION", "CONCLUSIONS",
            "1.", "2.1", "2.2", "3.1", "3.2", "3.3", "3.4", "3.5",
            "3.6", "3.7", "3.8", "4.1", "4.2", "4.3", "4.4", "4.5",
            "4.6", "4.7", "5.",
        ],
        "annex_excluded": True,
    },
    "cardiovascular_rf_ablation_catheter": {
        "label": "Cardiovascular RF Ablation Catheter (CAL-001 baseline)",
        "description": "PADN 肺动脉射频消融导管。CAL-001 校准基线。",
        "required_terms": [
            "radiofrequency", "ablation", "catheter", "PADN",
            "pulmonary artery", "cardiac",
        ],
        "allowed_terms": [
            "atrial fibrillation", "pulmonary vein", "arrhythmia",
            "electrophysiology",
        ],
        "forbidden_terms": [
            "joint", "arthroscopy", "orthopedic", "ureteroscope",
            "urological", "soft tissue resection",
            "ureteral", "ureteroscopy", "flexible ureteroscopy",
            "urology", "urinary tract", "urinary", "nephroscope",
            "guidewire", "urolithiasis", "endourology",
            "lithotripsy", "intrarenal", "renal pelvis", "renal",
            "stone burden", "endoscope", "endoscopic",
            "access sheath", "suction sheath", "UAS", "fURS",
            "PCNL", "percutaneous nephrolithotomy",
            "ureteral access sheath", "negative-pressure access sheath",
            "ureteric",
        ],
        "ambiguous_terms": [
            "ablation", "catheter",
        ],
        "exception_contexts": [
            "excluded", "not applicable", "differs from", "unlike", "in contrast to",
        ],
        "section_scope": [
            "SUMMARY", "DEVICE DESCRIPTION", "INTENDED PURPOSE",
            "CLINICAL BACKGROUND", "DEVICE UNDER EVALUATION", "CONCLUSIONS",
            "1.", "2.1", "2.2", "3.1", "3.2", "3.3", "3.4", "3.5",
            "3.6", "3.7", "3.8", "4.1", "4.2", "4.3", "4.4", "4.5",
            "4.6", "4.7", "5.",
        ],
        "annex_excluded": True,
    },
    "urology_uas": {
        "label": "Urology UAS (CAL-001 baseline domain)",
        "description": "Ureteral access sheath — urology domain.",
        "required_terms": [
            "ureteral access sheath", "UAS", "ureteroscope", "urinary tract",
            "urology", "endourology",
        ],
        "allowed_terms": [
            "guidewire", "hydrophilic coating", "suction sheath",
            "flexible ureteroscopy", "stone burden", "renal insufficiency",
        ],
        "forbidden_terms": [
            "cardiac tissue stabilizer", "CABG", "coronary artery bypass",
            "sternotomy", "cardiac ablation", "PADN", "pulmonary artery",
            "atrial fibrillation", "joint", "arthroscopy", "orthopedic",
        ],
        "ambiguous_terms": [
            "sheath", "access",
        ],
        "exception_contexts": [
            "excluded", "not applicable", "differs from", "unlike", "in contrast to",
        ],
        "section_scope": [
            "SUMMARY", "DEVICE DESCRIPTION", "INTENDED PURPOSE",
            "CLINICAL BACKGROUND", "DEVICE UNDER EVALUATION", "CONCLUSIONS",
            "1.", "2.1", "2.2", "3.1", "3.2", "3.3", "3.4", "3.5",
            "3.6", "3.7", "3.8", "4.1", "4.2", "4.3", "4.4", "4.5",
            "4.6", "4.7", "5.",
        ],
        "annex_excluded": True,
    },
}


def resolve_domain(device_domain: str) -> str | None:
    """Map a device_profile `device_domain` value to a matrix domain key.

    Returns None if the domain cannot be resolved, meaning Gate 1 cannot run.
    """
    if not device_domain:
        return None
    direct = DEVICE_DOMAIN_TO_MATRIX_DOMAIN.get(device_domain)
    if direct:
        return direct
    if device_domain in DOMAIN_TERM_MATRIX:
        return device_domain
    return None


def get_forbidden_terms(domain_key: str) -> list[str]:
    entry = DOMAIN_TERM_MATRIX.get(domain_key)
    if not entry:
        return []
    return list(entry.get("forbidden_terms", []))


def get_exception_contexts(domain_key: str) -> list[str]:
    entry = DOMAIN_TERM_MATRIX.get(domain_key)
    if not entry:
        return []
    return list(entry.get("exception_contexts", []))


def get_ambiguous_terms(domain_key: str) -> list[str]:
    entry = DOMAIN_TERM_MATRIX.get(domain_key)
    if not entry:
        return []
    return list(entry.get("ambiguous_terms", []))


def get_required_terms(domain_key: str) -> list[str]:
    entry = DOMAIN_TERM_MATRIX.get(domain_key)
    if not entry:
        return []
    return list(entry.get("required_terms", []))
