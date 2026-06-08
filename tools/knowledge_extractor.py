"""
V23 Knowledge Extractor — Deterministic Python, NOT LLM.
Extracts device-specific knowledge from NB observations across calibration projects.
Applies two-stage filter: occurrence (≥2 projects → CONFIRMED) + resolution (was NB CLOSED?).

Two modes:
  --mode extract: One-time extraction from all calibration projects → device_knowledge_base.json
  --mode update:  Post-project evolution — update existing knowledge base with new project data
"""

import os, re, json, sys
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict

# ============================================================
# PROJECT → DEVICE TYPE MAPPING
# ============================================================

PROJECT_DEVICE_MAP = {
    "PROJECT_012": {
        "device_type": "SPECT_CT_System",
        "device_name": "Insight NM/CT Pro (SPECT/CT)",
        "class": "IIb",
        "nb": "BSI",
    },
    "PROJECT_013": {
        "device_type": "Powered_Surgical_Stapler",
        "device_name": "Electric Surgical Stapler + Staple Cartridge",
        "class": "IIb",
        "nb": "DEKRA",
    },
    "PROJECT_017": {
        "device_type": "HF_Surgical_Generator",
        "device_name": "High Frequency Surgical Generators (Rapier RX-1A) + Electrosurgical Handpiece",
        "class": "IIb",
        "nb": "TUV",
    },
    "PROJECT_025": {
        "device_type": "Enteral_Feeding_Sets",
        "device_name": "Disposable Enteral Feeding Sets + Enteral Feeding Pump",
        "class": "IIa",
        "nb": "TUV",
    },
    "PROJECT_030": {
        "device_type": "Vascular_Catheter",
        "device_name": "PADN RF Ablation Catheter (Class III)",
        "class": "III",
        "nb": "BSI/DEKRA",
    },
    "PROJECT_031": {
        "device_type": "Insulin_Pump",
        "device_name": "Insulin Pump & Infusion Set (Class IIb/III)",
        "class": "IIb",
        "nb": "TUV_Rheinland",
    },
    "PROJECT_037": {
        "device_type": "Surgical_Gloves",
        "device_name": "Surgical Gloves (Class I/IIa)",
        "class": "I/IIa",
        "nb": "TUV_SUD",
    },
    "PROJECT_038": {
        "device_type": "Connecting_Tube",
        "device_name": "Connecting Tube / Catheter Fixation Device",
        "class": "IIa",
        "nb": "TUV",
    },
    "PROJECT_041": {
        "device_type": "Cold_Pack",
        "device_name": "Cold Pack / Thermal Therapy",
        "class": "IIa",
        "nb": "BSI",
    },
    # === Phase C Step 7 — New projects from batch DOCX extraction ===
    "PROJECT_002": {
        "device_type": "Cardiovascular_Imaging_Software",
        "device_name": "AngioPlus Core (Cardiovascular Imaging Software)",
        "class": "IIb",
        "nb": "BSI",
    },
    "PROJECT_019": {
        "device_type": "Photodynamic_Therapy_Device",
        "device_name": "Photodynamic Therapy Light Source",
        "class": "IIb",
        "nb": "BSI",
    },
    "PROJECT_023": {
        "device_type": "VAD_Controller_System",
        "device_name": "Extracorporeal VAD Controller",
        "class": "III",
        "nb": "BSI",
    },
    "PROJECT_029": {
        "device_type": "VAD_Controller_System",
        "device_name": "Pump Head and Tubing Kit (VAD Accessory)",
        "class": "III",
        "nb": "BSI",
    },
    "PROJECT_039": {
        "device_type": "Orthopedic_Joint_Implant",
        "device_name": "Knee Arthroplasty System (SX-RX01A) + Instruments + Consumables",
        "class": "III",
        "nb": "BSI",
    },
    # === V28.3 — Auto-mapped from D0 folder names (REVIEW REQUIRED) ===
    "PROJECT_004": {
        "device_type": "Wearable_Cardiac_Monitor",
        "device_name": "Wearable Cardiac Monitor / Patch ECG",
        "class": "IIb",
        "nb": "BSI",
    },
    "PROJECT_005": {
        "device_type": "Oncology_Ablation_Device",
        "device_name": "Cryoablation / Thermal Ablation System",
        "class": "IIb",
        "nb": "BSI",
    },
    "PROJECT_006": {
        "device_type": "In_Vitro_Diagnostic_Device",
        "device_name": "IVD Reagent / Analyzer System",
        "class": "IIb",
        "nb": "BSI",
    },
    "PROJECT_007": {
        "device_type": "Patient_Monitor",
        "device_name": "Multi-parameter Patient Monitor",
        "class": "IIb",
        "nb": "BSI",
    },
    "PROJECT_008": {
        "device_type": "Surgical_Instrument",
        "device_name": "Reusable Surgical Instruments",
        "class": "IIa",
        "nb": "DEKRA",
    },
    "PROJECT_009": {
        "device_type": "Occlusion_Device",
        "device_name": "Vascular Occlusion / Ligation Device",
        "class": "III",
        "nb": "BSI",
    },
    "PROJECT_010": {
        "device_type": "Dental_Implant",
        "device_name": "Dental Implant System + Abutments",
        "class": "IIb",
        "nb": "DEKRA",
    },
    "PROJECT_011": {
        "device_type": "Orthopedic_Plate",
        "device_name": "Orthopedic Bone Plate & Screw System",
        "class": "IIb",
        "nb": "DEKRA",
    },
    "PROJECT_014": {
        "device_type": "Infusion_Set",
        "device_name": "Disposable Infusion Set + IV Catheter",
        "class": "IIa",
        "nb": "TUV",
    },
    "PROJECT_015": {
        "device_type": "AI_Diagnostic_Software",
        "device_name": "AI-Assisted Medical Image Analysis Software",
        "class": "IIb",
        "nb": "BSI",
    },
    "PROJECT_016": {
        "device_type": "X_Ray_System",
        "device_name": "Mobile / Fixed X-Ray Radiography System",
        "class": "IIb",
        "nb": "BSI",
    },
    "PROJECT_018": {
        "device_type": "Rehabilitation_Device",
        "device_name": "Electric Rehabilitation / Physiotherapy Device",
        "class": "IIa",
        "nb": "DEKRA",
    },
    "PROJECT_021": {
        "device_type": "Orthopedic_Implant",
        "device_name": "Orthopedic Implant System (DMD) + Instruments",
        "class": "III",
        "nb": "DEKRA",
    },
}

# ============================================================
# CONCERN CATEGORY CLASSIFICATION (keyword-based, deterministic)
# ============================================================

CONCERN_CATEGORIES = {
    "PMCF_Plan": [
        r'PMCF', r'post.market clinical follow.up', r'post-market clinical', r'PMS plan',
        r'上市后临床', r'proactive.*data.*source', r'surveillance.*plan',
    ],
    "Clinical_Evidence_Insufficiency": [
        r'clinical.*(?:data|evidence|investigation|trial|study).*(?:insufficient|inadequate|missing|limited|lack)',
        r'(?:insufficient|inadequate|missing|limited).*(?:clinical.*(?:data|evidence|investigation))',
        r'bald statement', r'no consideration', r'not.*supported.*clinical',
        r'literature.*(?:only|alone)', r'no.*device.specific.*data',
        r'临床试验.*不足', r'临床数据.*不足',
    ],
    "Equivalence_Gap": [
        r'equivale\w+', r'predicate', r'similar device', r'Art(?:icle)?\s*61\s*\(?\s*10',
        r'MEDDEV\s*2\.7/1', r'comparison table', r'technical.*biological.*clinical.*equiv',
        r'等同', r'对比.*器械',
    ],
    "IFU_Labeling_Gap": [
        r'IFU', r'instructions for use', r'label(?:ing)?\s*(?:gap|missing|incomplete|insufficient)',
        r'contra.?indicat\w*', r'warning.*(?:missing|incomplete)', r'precaution.*(?:missing|incomplete)',
        r'GSPR\s*23\.4', r'symbol.*(?:missing|incorrect)', r'UDI',
        r'标签', r'说明书', r'警告.*缺失', r'禁忌',
    ],
    "Risk_Management_Gap": [
        r'risk\s*(?:management|analysis|assessment|evaluation|control)',
        r'ISO\s*14971', r'hazard.*(?:missing|not.*identif)', r'FMEA',
        r'residual risk', r'risk.benefit',
        r'风险管理', r'风险分析', r'风险控制',
    ],
    "Biocompatibility": [
        r'biocompat\w*', r'ISO\s*10993', r'cytotox\w*', r'sensitiz\w*', r'irritation',
        r'biological\s*(?:evaluation|safety|assessment)',
        r'patient.contacting', r'blood.contacting', r'material.*safety',
        r'生物学', r'生物相容', r'细胞毒',
    ],
    "Software_Cybersecurity": [
        r'software\s*(?:validation|verification|classification|development)',
        r'IEC\s*62304', r'cyber\w*', r'PEMS', r'ready.made software',
        r'软件', r'网络安全',
    ],
    "Sterilization_Reprocessing": [
        r'steril\w*', r'cleanliness', r'bioburden', r'pyrogen', r'endotoxin',
        r'EN\s*ISO\s*11135', r'EN\s*ISO\s*17664', r'reprocess\w*',
        r'消毒', r'灭菌', r'无菌', r'清洁',
    ],
    "GSPR_Standards_Compliance": [
        r'GSPR\s*(?:checklist|compliance|coverage)', r'general safety and performance',
        r'standard.*(?:version|edition|year).*(?:outdated|old|superseded)',
        r'EN\s*(?:60601|62366|62304|455|14683|13795|11607)', r'ISO\s*\d+',
        r'标准.*过期', r'标准.*版本',
    ],
    "Shelf_Life_Stability": [
        r'shelf\s*life', r'stability', r'aging', r'expir\w*', r'ASTM\s*F1980',
        r'有效期', r'稳定性', r'老化', r'货架',
    ],
    "Test_Verification_Gap": [
        r'test\s*(?:report|data|result).*(?:missing|incomplete|insufficient)',
        r'verification.*(?:missing|incomplete)', r'validation.*(?:missing|incomplete)',
        r'performance\s*(?:test|data).*(?:missing|incomplete)',
        r'测试.*缺失', r'验证.*不足',
    ],
    "Process_Validation": [
        r'process\s*valid\w*', r'special process', r'ISO\s*13485\s*7\.5\.2',
        r'extrusion', r'welding', r'bonding', r'molding',
        r'工艺验证', r'特殊过程', r'过程确认',
    ],
    "Benefit_Risk": [
        r'benefit.risk\s*(?:analysis|assessment|ratio|determination|conclusion)',
        r'benefit.*outweigh', r'risk.*outweigh',
        r'收益.*风险', r'获益.*风险',
    ],
    "Device_Description": [
        r'device\s*(?:description|specification|composition|variant)',
        r'principle.*operation', r'mode.*action', r'intended\s*(?:use|purpose|patient)',
        r'器械.*描述', r'产品.*描述', r'预期用途',
    ],
    "Document_Control_Admin": [
        r'sign\w*\s*(?:missing|incomplete|not.*present)', r'date.*(?:missing|not.*filled)',
        r'document\s*(?:control|number|ID|version).*(?:missing|inconsistent)',
        r'certificate.*(?:expir\w*|missing|outdated)', r'实验室资质',
        r'translation.*(?:missing|incomplete|needed)', r'中文.*翻译',
        r'签字', r'日期.*缺失', r'封面.*手签', r'文件.*日期',
    ],
    "SOTA_Currency": [
        r'state.of.the.art', r'SOTA', r'current.*literature', r'literature.*search.*date',
        r'data.*search.*end', r'superseded', r'guideline.*update',
        r'最新.*文献', r'文献.*检索.*日期',
    ],
    "Patient_Population": [
        r'patient\s*(?:population|group|stratif\w*|selection)',
        r'pregnant', r'pediatric', r'geriatric', r'contraindicated.*population',
        r'(?:all|entire|complete).*(?:populations?|indications?)',
        r'患者.*人群', r'孕妇', r'儿童', r'小儿',
    ],
    "Statistical_Methodology": [
        r'statistic\w*\s*(?:justif\w*|method|analysis|significance)',
        r'sample\s*size\s*(?:justif\w*|rationale|calculation)',
        r'zero.complaint', r'zero.event', r'confidence\s*interval', r'p.value',
        r'统计', r'样本.*量', r'显著',
    ],
    "Material_Chemical": [
        r'material\s*(?:composition|name|specification).*(?:incomplete|missing)',
        r'chemical\s*(?:composition|safety|characterization)',
        r'REACH', r'RoHS', r'phthalate', r'DEHP', r'latex', r'powder',
        r'材料.*成分', r'化学',
    ],
}

def classify_concern(text: str) -> List[str]:
    """Classify an NB observation into one or more concern categories."""
    categories = []
    for cat, patterns in CONCERN_CATEGORIES.items():
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                categories.append(cat)
                break
    if not categories:
        categories.append("General_Regulatory")
    return categories


# ============================================================
# RESOLUTION FILTER: Check if NB concern was CLOSED by evidence
# ============================================================

def is_resolved(obs: dict, crosswalk_data: Optional[dict]) -> bool:
    """Check if an NB observation was CLOSED by the manufacturer providing evidence.

    Resolution signals:
    1. Round is R2/R3/R4 (not R1) — implies the question was answered iteratively
    2. Crosswalk shows STRONG match → AI found and matched this concern
    3. Text contains 'CLOSED', 'resolved', '已关闭', '已解决', '已完成'
    """
    # V24: extended field name variants
    text = (obs.get("nb_question", "") or obs.get("question", "")
            or obs.get("text", "") or obs.get("question_text", ""))
    round_info = (obs.get("round", "") or obs.get("review_round", "")
                  or obs.get("nb_round", ""))

    # Signal 1: Later round
    if round_info and round_info.upper() in ("R2", "R3", "R4", "R5", "ROUND 2", "ROUND 3"):
        return True

    # Signal 2: Crosswalk STRONG match (if we have crosswalk data)
    # V24: handle both "details" and "results" array formats
    if crosswalk_data:
        obs_id = (obs.get("obs_id", "") or obs.get("observation_id", "") or obs.get("id", ""))
        crosswalk_items = crosswalk_data.get("details", []) or crosswalk_data.get("results", [])
        for item in crosswalk_items:
            if item.get("match_quality") == "STRONG" and item.get("match_score", 0) >= 20:
                return True

    # Signal 3: Resolution keywords
    resolution_keywords = [
        r'(?:has been|was|were|is|are)\s*(?:addressed|resolved|clarified|provided|updated|corrected|completed)',
        r'(?:已|已经|已完成|已更新|已修正|已补充|已答复|已解决)',
        r'CLOSED', r'closed', r'RESOLVED',
        r'(?:see|refer|请.*见|请.*参考).*(?:attachment|appendix|附件|附录)',
    ]
    for kw in resolution_keywords:
        if re.search(kw, text, re.IGNORECASE):
            return True

    return False


# ============================================================
# CONCERN NORMALIZATION: Group similar concerns across projects
# ============================================================

def normalize_concern(text: str, category: str) -> str:
    """Normalize a concern text to a canonical short label for cross-project grouping."""
    text_lower = text.lower()

    # --- Chinese-specific normalization (check before English, since Chinese texts fail English patterns) ---
    if re.search(r'[一-鿿]', text):
        if re.search(r'签字|签名|手签|签章|封面.*签|文件.*日期.*填', text):
            return "Document signatures/dates missing (文件签字/日期缺失)"
        if re.search(r'翻译|中文.*翻译|英文版|英文.*提供', text):
            return "Document translation incomplete (Chinese→EU languages)"
        if re.search(r'资质.*过期|资质.*最新|实验室.*资质|证书.*过期|有效期', text):
            return "Certificate or lab qualification expired/invalid"
        if re.search(r'重复|同步|蓝色标记', text):
            return "Duplicate/redundant content across documents"
        if re.search(r'物料.*名称|BOM|材料.*不全|材料.*成分|采购清单', text):
            return "BOM material names incomplete (物料信息不全)"
        if re.search(r'型号.*关系|规格.*对应|型号.*区别|型号.*差异', text):
            return "Device variant/model relationship unclear"
        if re.search(r'典型性|typical|representative.*model', text_lower):
            return "Worst-case/representative model selection rationale"
        if re.search(r'工艺.*验证|特殊.*过程|过程.*确认|process.*valid', text_lower):
            return "Special processes not all validated per ISO 13485 §7.5.2"
        if re.search(r'流程|flow.?chart|生产工艺', text_lower):
            return "Process flowchart/manufacturing process documentation gap"
        if re.search(r'测试.*报告|运输.*测试|性能.*测试|检验.*报告', text):
            return "Test report missing or incomplete"
        if re.search(r'设计.*开发|design.*development', text_lower):
            return "Design and development documentation gap"
        if re.search(r'标签.*缺失|UDI|唯一.*标识|标签.*信息', text):
            return "Label/UDI information missing"
        if re.search(r'灭菌.*方法|灭菌.*验证|无菌|消毒.*方法', text):
            return "Sterilization method/validation incomplete"
        if re.search(r'国内.*国外|标签.*拆分|区分', text):
            return "Domestic/international documentation separation needed"
        if re.search(r'市场.*国家|欧盟.*国家|market.*country|EU.*country', text_lower):
            return "Market/country listing incomplete"
        if re.search(r'包装|packing|packaging', text_lower):
            return "Packaging information/documentation missing"
        if re.search(r'警告.*缺失|注意事项.*缺失|precaution|warning.*missing', text_lower):
            return "IFU warnings/precautions missing"
        # Catch-all for Chinese: use category + first 40 chars
        return f"[CN] {category}: {text[:60]}"

    # --- English normalization (original) ---
    if category == "PMCF_Plan":
        if re.search(r'proactive.*data|proactive.*source|主动', text_lower):
            return "PMCF lacks proactive data sources"
        if re.search(r'surveillance.*plan|PMS plan.*missing', text_lower):
            return "PMS/PMCF surveillance plan insufficient"
        return "PMCF plan gap"

    elif category == "Clinical_Evidence_Insufficiency":
        if re.search(r'literature.*only|literature.*alone|仅.*文献', text_lower):
            return "Clinical evidence is literature-only, no device-specific data"
        if re.search(r'bald statement|bare assertion', text_lower):
            return "Safety claim is unsupported assertion (bald statement)"
        if re.search(r'not.*supported|insufficient.*data', text_lower):
            return "Clinical data insufficient to support claims"
        return "Clinical evidence gap"

    elif category == "Equivalence_Gap":
        if re.search(r'comparison table|comparison.*missing|无.*对比', text_lower):
            return "Equivalence comparison table missing or incomplete"
        if re.search(r'access.*not.*declared|contract.*missing|TD.*access', text_lower):
            return "Equivalence device technical documentation access not declared"
        if re.search(r'technical.*equiv|biological.*equiv|clinical.*equiv', text_lower):
            return "Equivalence demonstration incomplete (technical/biological/clinical)"
        return "Equivalence justification gap"

    elif category == "IFU_Labeling_Gap":
        if re.search(r'contra.?indicat', text_lower):
            return "IFU contraindications incomplete or inaccurate"
        if re.search(r'GSPR\s*23\.4', text_lower):
            return "IFU GSPR 23.4 sub-clauses not individually addressed"
        if re.search(r'warning.*missing|precaution.*missing|警告|注意事项', text_lower):
            return "IFU warnings/precautions missing"
        if re.search(r'symbol|符号|标记', text_lower):
            return "IFU symbols or markings incorrect"
        if re.search(r'UDI|唯一器械标识', text_lower):
            return "UDI carrier missing or incomplete"
        return "IFU/labeling gap"

    elif category == "Risk_Management_Gap":
        if re.search(r'risk.*analysis.*missing|hazard.*not.*identif', text_lower):
            return "Risk analysis incomplete — hazards not fully identified"
        if re.search(r'residual risk|剩余风险', text_lower):
            return "Residual risk evaluation insufficient"
        if re.search(r'FMEA|failure mode', text_lower):
            return "FMEA incomplete or missing"
        if re.search(r'traceab\w*', text_lower):
            return "Risk management traceability gap"
        return "Risk management gap"

    elif category == "Biocompatibility":
        if re.search(r'ISO\s*10993|标准.*10993', text_lower):
            return "ISO 10993 biocompatibility evaluation incomplete"
        if re.search(r'blood.contact|血液.*接触', text_lower):
            return "Biocompatibility for blood-contacting device not demonstrated"
        return "Biocompatibility evidence gap"

    elif category == "Software_Cybersecurity":
        if re.search(r'IEC\s*62304|软件.*生命周期', text_lower):
            return "IEC 62304 software validation incomplete"
        if re.search(r'cyber|网络', text_lower):
            return "Cybersecurity risk assessment missing or incomplete"
        if re.search(r'classification.*rationale|安全.*级别', text_lower):
            return "Software safety classification rationale missing"
        return "Software/cybersecurity gap"

    elif category == "Sterilization_Reprocessing":
        if re.search(r'steril.*valid|灭菌.*验证', text_lower):
            return "Sterilization validation incomplete"
        if re.search(r'reprocess|再处理|复用', text_lower):
            return "Reprocessing instructions incomplete or not validated"
        return "Sterilization/reprocessing gap"

    elif category == "GSPR_Standards_Compliance":
        if re.search(r'outdated|superseded|过期|旧版', text_lower):
            return "Standards referenced are outdated/superseded versions"
        if re.search(r'GSPR.*(?:checklist|check|coverage).*(?:incomplete|missing)', text_lower):
            return "GSPR checklist incomplete — clauses not individually addressed"
        if re.search(r'citation.*(?:missing|without|incomplete)', text_lower):
            return "GSPR evidence citations incomplete or unverifiable"
        return "Standards/GSPR compliance gap"

    elif category == "Shelf_Life_Stability":
        if re.search(r'real.time.*aging|实时.*老化', text_lower):
            return "Shelf life validation — real-time aging data missing"
        if re.search(r'accelerat.*aging|加速.*老化', text_lower):
            return "Shelf life — accelerated aging only, no real-time data"
        return "Shelf life/stability validation gap"

    elif category == "Process_Validation":
        if re.search(r'special process.*not.*valid|特殊.*过程.*未.*验证', text_lower):
            return "Special processes not all validated per ISO 13485 §7.5.2"
        return "Process validation gap"

    elif category == "Document_Control_Admin":
        if re.search(r'sign|签字|签名|手签', text_lower):
            return "Document signatures missing or incomplete"
        if re.search(r'date.*missing|日期.*(?:缺失|未填)', text_lower):
            return "Document dates missing or not filled"
        if re.search(r'translat\w*.*(?:missing|incomplete|needed)|翻译', text_lower):
            return "Document translation incomplete (Chinese → EU languages)"
        if re.search(r'certificate.*expir\w*|资质.*过期|证书.*过期', text_lower):
            return "Certificate or lab qualification expired"
        return "Document control/admin gap"

    elif category == "SOTA_Currency":
        if re.search(r'literature.*search.*(?:date|end).*(?:old|outdated|202\d)', text_lower):
            return "Literature search outdated — data gap between search end and CER date"
        if re.search(r'SOTA|state.of.the.art', text_lower):
            return "State-of-the-art not adequately demonstrated"
        return "SOTA currency gap"

    elif category == "Patient_Population":
        if re.search(r'(?:all|entire).*(?:population|indication).*(?:not|missing)', text_lower):
            return "Benefit-risk not stratified for all indicated populations"
        if re.search(r'pregnant|pediatric|孕妇|儿童', text_lower):
            return "Specific population (pregnant/pediatric) not addressed"
        return "Patient population coverage gap"

    elif category == "Statistical_Methodology":
        if re.search(r'zero.complaint|zero.event|零.*投诉|零.*事件', text_lower):
            return "Zero-complaint/zero-event claim not statistically justified"
        if re.search(r'sample.*size', text_lower):
            return "Sample size justification missing"
        return "Statistical methodology gap"

    elif category == "Material_Chemical":
        if re.search(r'allergen|latex|powder.*free|过敏', text_lower):
            return "Allergen/materials labeling incomplete (latex, accelerators, powder)"
        if re.search(r'material.*(?:name|composition).*(?:incomplete|missing)', text_lower):
            return "BOM material names incomplete — blocks assessment"
        return "Material/chemical characterization gap"

    else:
        # Generic fallback
        return text[:120]


# ============================================================
# CLINICAL CONTEXT LIBRARY (from published guidelines)
# ============================================================

CLINICAL_CONTEXT_LIBRARY = {
    "SPECT_CT_System": {
        "standard_of_care": "Diagnostic SPECT/CT imaging with ALARA radiation principle per IAEA SSG46",
        "key_guideline": "IAEA SSG46: Radiation Safety in Nuclear Medicine, IAEA PUB1775: Pregnancy and Radiation Protection, EN 60601-2-28 + EN 60601-2-44",
        "evidence_expectation": "Clinical validation of diagnostic accuracy (sensitivity/specificity), radiation dose characterization, software validation per IEC 62304",
        "source": "IAEA SSG46 (2023), IAEA PUB1775, ESC/EANM guidelines",
    },
    "Powered_Surgical_Stapler": {
        "standard_of_care": "Powered stapling for endoscopic tissue resection and anastomosis with staple line reinforcement per surgical society guidelines",
        "key_guideline": "EN 60601-1, EN 60601-2-2 (if HF-integrated), IEC 62304, EN 62366-1 usability, EN ISO 11607 packaging",
        "evidence_expectation": "Staple formation consistency testing across all cartridge types, tissue compression data, software safety classification per IEC 62304, battery reliability data",
        "source": "SAGES guidelines, EAES recommendations, MDCG 2020-6",
    },
    "HF_Surgical_Generator": {
        "standard_of_care": "Electrosurgery with impedance monitoring per EN 60601-2-2 for cutting and coagulation across tissue types",
        "key_guideline": "EN 60601-2-2:2017+AMD1:2023, EN 60601-1-2 EMC, IEC 62304, EN 62366-1 usability",
        "evidence_expectation": "EN 60601-2-2 compliance testing for all operating modes, clinical evaluation per MDCG 2020-6 §4.4, pacemaker/ICD interference testing, pediatric use restrictions",
        "source": "EN 60601-2-2, ESC/EHRA consensus on EMI with CIEDs, MDCG 2020-6",
    },
    "Enteral_Feeding_Sets": {
        "standard_of_care": "Enteral nutrition via ENFit-compliant connectors per ISO 80369-3 to prevent misconnection",
        "key_guideline": "ISO 80369-3 ENFit connectors, EN ISO 11607 packaging, ISO 13485 §7.5.2 special processes, ISO 10993 biocompatibility",
        "evidence_expectation": "Process validation (extrusion, welding, bonding, EO sterilization), packaging integrity, shelf life (ASTM F1980 + real-time), biocompatibility for mucosal contact",
        "source": "ISO 80369-3, ESPEN guidelines on enteral nutrition, ISO 13485",
    },
    "Vascular_Catheter": {
        "standard_of_care": "Class III cardiovascular catheter requires clinical investigation per MDR Art 61(4) unless WET exemption with ≥2yr follow-up",
        "key_guideline": "MDR Art 61(4)/(5)/(10), MDCG 2020-6, ISO 10993 full series for blood-contacting implantable, EN ISO 11135 sterilization",
        "evidence_expectation": "Clinical investigation with ≥2yr follow-up, full ISO 10993 series, mechanical testing (tensile, fatigue, kink, torque), combination device compatibility documentation",
        "source": "MDR Art 61, MDCG 2020-6, ESC/EAPCI consensus on cardiovascular device evaluation",
    },
    "Insulin_Pump": {
        "standard_of_care": "Continuous subcutaneous insulin infusion (CSII) with integrated CGM per ADA/EASD standards for Type 1 diabetes",
        "key_guideline": "EN 60601-2-24 infusion pump particular requirements, IEC 62304, EN 60601-1-8 alarm systems, MDCG 2019-16 cybersecurity",
        "evidence_expectation": "Clinical investigation or robust equivalence + PMS data, infusion accuracy per EN 60601-2-24, alarm validation (occlusion, battery, reservoir), cybersecurity risk assessment, PMCF with proactive data sources",
        "source": "ADA/EASD 2024 Standards of Care, EN 60601-2-24, MDCG 2019-16",
    },
    "Surgical_Gloves": {
        "standard_of_care": "Double gloving recommended for high-risk procedures per AORN 2024 guidelines; powder-free per FDA guidance",
        "key_guideline": "EN 455-1:2020 freedom from holes (AQL ≤1.5), EN 455-2 physical properties, EN 455-3 biological evaluation (allergen labeling), EN 455-4 shelf life, ISO 10282:2014, ASTM D3578",
        "evidence_expectation": "Clinical performance study (barrier efficacy, perforation rate), biocompatibility per ISO 10993 (mucosal/skin contact), sterilization validation (EN ISO 11135), barrier testing per EN 455-1/2, shelf life validation with real-time aging",
        "source": "AORN 2024 Guidelines, EN 455 series, ISO 10282:2014, FDA guidance on powdered gloves",
    },
    "Cold_Pack": {
        "standard_of_care": "Cold therapy for pain relief and inflammation reduction with temperature-controlled application to prevent cold burn",
        "key_guideline": "ISO 10993 biocompatibility (skin surface, limited contact), EN 60601-1 if powered, general MDR Annex I safety requirements",
        "evidence_expectation": "Thermal performance testing (temperature range, duration, consistency), material safety (gel composition, packaging integrity), biocompatibility per ISO 10993 for skin contact",
        "source": "Clinical sports medicine guidelines, ISO 10993, MDR Annex I GSPR",
    },
    "Cardiovascular_Imaging_Software": {
        "standard_of_care": "Coronary angiography quantitative analysis (QCA/QVA) per ESC guidelines for CAD diagnosis and treatment planning",
        "key_guideline": "IEC 62304 health software, EN 62366-1 usability, MDCG 2019-16 cybersecurity, MDCG 2020-1 clinical evaluation of software",
        "evidence_expectation": "Algorithm validation study (sensitivity/specificity vs reference standard), software lifecycle documentation, cybersecurity risk assessment, clinical performance study",
        "source": "ESC guidelines on coronary imaging, IEC 62304, MDCG 2019-16, MDCG 2020-1",
    },
    "Photodynamic_Therapy_Device": {
        "standard_of_care": "PDT light delivery for targeted tissue ablation with photosensitizer activation at specific wavelengths",
        "key_guideline": "IEC 60601-2-75 PDT particular requirements, IEC 60825 laser safety, EN 60601-1 general safety, ISO 10993",
        "evidence_expectation": "Wavelength accuracy validation (±5nm per IEC 60601-2-75), optical output characterization, clinical investigation with efficacy endpoints, photosensitizer compatibility data",
        "source": "IEC 60601-2-75, IEC 60825, clinical PDT guidelines",
    },
    "VAD_Controller_System": {
        "standard_of_care": "Ventricular assist device for end-stage heart failure per ISHLT guidelines; Class III implantable or extracorporeal",
        "key_guideline": "ISO 14708 implantable/active medical devices, IEC 60601-1 safety, IEC 62304 software, MDR Art 61(4) clinical investigation, EN ISO 11135 sterilization",
        "evidence_expectation": "Clinical investigation with ≥2yr follow-up, hemocompatibility per ISO 10993-4, software SOTA per IEC 62304, alarm systems per EN 60601-1-8, biocompatibility full series, PMCF registry",
        "source": "ISHLT 2023 Guidelines, ISO 14708, MDR Art 61, MDCG 2020-6",
    },
    "Orthopedic_Joint_Implant": {
        "standard_of_care": "Total joint arthroplasty for end-stage osteoarthritis per AAOS/EFORT guidelines; Class III implantable",
        "key_guideline": "ISO 21534 non-active surgical implants, ISO 14243 wear testing for knee, ISO 10993 full series, MDR Art 61(4) clinical investigation",
        "evidence_expectation": "Clinical investigation ≥2yr with survival analysis (Kaplan-Meier), wear simulation per ISO 14243, corrosion testing, debris characterization, surgical instrumentation validation, PMCF registry ≥5yr follow-up",
        "source": "AAOS/EFORT guidelines, ISO 21534, ISO 14243, MDR Art 61, MDCG 2020-6",
    },
    "Connecting_Tube": {
        "standard_of_care": "Sterile single-use connecting tubes for fluid delivery systems with Luer/ENFit connector compatibility",
        "key_guideline": "ISO 80369-7 Luer connectors, EN ISO 11135 sterilization, ISO 10993 biocompatibility, ISO 13485 §7.5.2 special processes",
        "evidence_expectation": "Process validation (extrusion, bonding, EO sterilization), biocompatibility per ISO 10993 (fluid path contact), connector compatibility and retention force testing",
        "source": "ISO 80369 series, ISO 13485, MDCG 2020-6",
    },
}


# ============================================================
# V24: DEVICE ALIAS RESOLUTION
# ============================================================

def load_device_alias_map(filepath: str = None) -> dict:
    """Load device alias map for matching project descriptions to KB slugs."""
    if filepath is None:
        filepath = os.path.join(os.path.dirname(__file__), "..", "knowledge", "device_alias_map.json")
    if not os.path.exists(filepath):
        return {"entries": []}
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def resolve_device_type(device_name: str, alias_map: dict) -> Tuple[Optional[str], str, float]:
    """
    Resolve a device name/description to a canonical knowledge base slug.
    Returns (canonical_slug, match_method, confidence).

    Match layers (in priority order):
    1. EXACT: device_name matches canonical_slug verbatim
    2. ALIAS: device_name contains an alias entry
    3. FUZZY: token overlap >= 2 between device_name and aliases
    4. NONE: no match, apply general MDR principles
    """
    if not alias_map or not alias_map.get("entries"):
        return (None, "NONE", 0.0)

    device_lower = device_name.lower()

    for entry in alias_map["entries"]:
        slug = entry["canonical_slug"]
        # Layer 1: Exact match on slug
        if slug.lower() == device_lower:
            return (slug, "EXACT", 1.0)

        # Layer 2: Exact match on alias
        for alias in entry["aliases"]:
            if alias.lower() in device_lower or device_lower in alias.lower():
                # Check negative keywords
                neg_hit = any(nk.lower() in device_lower for nk in entry.get("negative_keywords", []))
                conf = 0.75 if neg_hit else 0.90
                return (slug, "ALIAS", conf)

    # Layer 3: Fuzzy token overlap (fallback)
    best_slug = None
    best_score = 0
    device_tokens = set(re.findall(r'\w+', device_lower))

    for entry in alias_map["entries"]:
        slug = entry["canonical_slug"]
        all_aliases = [slug.lower()] + [a.lower() for a in entry["aliases"]]
        alias_tokens = set()
        for a in all_aliases:
            alias_tokens.update(re.findall(r'\w+', a))

        overlap = len(device_tokens & alias_tokens)
        if overlap > best_score:
            best_score = overlap
            best_slug = slug

    if best_score >= 2:
        return (best_slug, "FUZZY", 0.60)

    # Layer 4: No match
    return (None, "NONE", 0.0)


# ============================================================
# MAIN EXTRACTION LOGIC
# ============================================================

def load_nb_observations(filepath: str) -> List[dict]:
    """Load NB observations from a JSON file, normalizing the format."""
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    project_id = data.get("project_id", "")
    device_info = PROJECT_DEVICE_MAP.get(project_id, {})
    # V24: Resolve via alias map if device_name doesn't match KB slug directly
    # V28: Handle both old format (device=str) and new format (device=dict)
    raw_device = data.get("device", "")
    if isinstance(raw_device, dict):
        raw_device_name = raw_device.get("device_name", "") or raw_device.get("device_type", "")
    else:
        raw_device_name = str(raw_device) if raw_device else ""
    # Fallback chain
    raw_device_name = raw_device_name or data.get("device_type", "") or device_info.get("device_name", "")
    alias_map = load_device_alias_map()
    resolved_slug, match_method, alias_conf = resolve_device_type(raw_device_name, alias_map)
    if resolved_slug:
        device_info = dict(device_info)  # shallow copy to avoid mutating the global
        device_info["device_type"] = resolved_slug
        device_info["alias_match_method"] = match_method
        device_info["alias_confidence"] = alias_conf
    observations = data.get("observations", [])

    normalized = []
    for obs in observations:
        # V24: extended field name variants for cross-project compatibility
        text = (obs.get("nb_question", "") or obs.get("question", "")
                or obs.get("text", "") or obs.get("question_text", "")
                or obs.get("observation_text", ""))
        if not text or len(text.strip()) < 5:
            continue

        categories = classify_concern(text)
        category = (obs.get("category", "") or obs.get("status_category", "")
                    or obs.get("concern_category", "")
                    or (categories[0] if categories else "General_Regulatory"))

        normalized.append({
            "obs_id": (obs.get("obs_id", "") or obs.get("observation_id", "")
                       or obs.get("nb_id", "") or obs.get("id", "")),
            "project_id": project_id,
            "device_type": device_info.get("device_type", "UNKNOWN"),
            "device_name": device_info.get("device_name", ""),
            "device_class": device_info.get("class", ""),
            "nb": device_info.get("nb", ""),
            "text": text.strip(),
            "round": (obs.get("round", "") or obs.get("review_round", "")
                      or obs.get("nb_round", "")),
            "category": category,
            "ai_categories": categories,
            "source_file": (obs.get("source", "") or obs.get("source_file", "")
                            or obs.get("file_source", "")),
        })

    return normalized


def load_crosswalk(filepath: str) -> Optional[dict]:
    """Load crosswalk matrix if available."""
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None


def extract_knowledge(reports_dir: str) -> Dict[str, Any]:
    """Main extraction: read all projects, apply filters, produce knowledge base."""
    all_obs = []

    # Load all projects
    for fname in os.listdir(reports_dir):
        if not fname.endswith('_nb_observations.json'):
            continue
        fpath = os.path.join(reports_dir, fname)
        try:
            obs_list = load_nb_observations(fpath)
            project_id = obs_list[0]["project_id"] if obs_list else ""
            print(f"  Loaded {len(obs_list)} observations from {fname} ({project_id})")

            # Load crosswalk for resolution filter
            crosswalk_path = fpath.replace('_nb_observations.json', '_crosswalk_matrix.json')
            cw = load_crosswalk(crosswalk_path)

            # Tag with resolution
            for obs in obs_list:
                obs["resolved"] = is_resolved(obs, cw)

            all_obs.extend(obs_list)
        except Exception as e:
            print(f"  ERROR loading {fname}: {e}")

    print(f"\nTotal raw observations: {len(all_obs)}")

    # Filter: remove regulatory-generic (keep device-specific)
    regulatory_generic_patterns = [
        r'^(?:please\s+)?(?:provide|submit|send|attach|upload|add)\s+(?:the\s+)?(?:document|file|report|form|list|certificate)',
        r'^(?:请|麻烦)\s*(?:提供|提交|补充|上传|增加|附上)',
        r'^(?:the\s+)?(?:file|document|report)\s+(?:is|are|has|have)\s+(?:missing|not|incomplete)',
        r'^(?:pls|please)\s+(?:see|refer|check|confirm|clarify|explain|describe)',
    ]
    device_specific_obs = []
    for obs in all_obs:
        text = obs["text"]
        is_generic = any(re.search(p, text, re.IGNORECASE) for p in regulatory_generic_patterns)
        # Keep if NOT purely generic OR if it contains device-specific keywords
        has_device_context = any(kw in text.lower() for kw in [
            'glove', 'catheter', 'pump', 'insulin', 'electrode', 'stapler', 'feeding',
            'spect', 'SPECT', 'CT', 'ablation', 'surgical', 'cold pack', 'thermal',
            'infusion', 'generator', 'handpiece', 'enteral',
        ])
        if not is_generic or has_device_context:
            device_specific_obs.append(obs)

    print(f"After generic filter: {len(device_specific_obs)} device-specific observations")

    # V26: Universal MDR categories that apply across device types
    UNIVERSAL_MDR_CATEGORIES = {
        "IFU_Labeling_Gap", "Risk_Management_Gap", "Biocompatibility",
        "GSPR_Standards_Compliance", "Clinical_Evidence_Insufficiency",
        "PMCF_Plan", "Benefit_Risk", "Document_Control_Admin",
        "Software_Cybersecurity", "Sterilization_Reprocessing",
    }

    # PHASE 1: Cross-device occurrence — group same concern across ALL device types
    # This is necessary because calibration data has 1 project per device type.
    # A concern appearing in ≥2 projects (even across device types) indicates a genuine NB pattern.
    cross_device_concerns = defaultdict(list)
    for obs in device_specific_obs:
        if obs["device_type"] == "UNKNOWN":
            continue
        category = obs["category"]
        concern = normalize_concern(obs["text"], category)
        # Composite key for cross-device grouping: category + concern
        key = f"{category}|||{concern}"
        cross_device_concerns[key].append(obs)

    # V26: Universal MDR categories that apply across device types
    UNIVERSAL_MDR_CATEGORIES = {
        "IFU_Labeling_Gap", "Risk_Management_Gap", "Biocompatibility",
        "GSPR_Standards_Compliance", "Clinical_Evidence_Insufficiency",
        "PMCF_Plan", "Benefit_Risk", "Document_Control_Admin",
        "Software_Cybersecurity", "Sterilization_Reprocessing",
    }

    # V26: Cross-device category-level grouping for universal MDR categories
    # For universal categories, also group by category alone (broader matching)
    for obs in device_specific_obs:
        if obs["device_type"] == "UNKNOWN":
            continue
        category = obs["category"]
        if category in UNIVERSAL_MDR_CATEGORIES:
            # Also add to category-only grouping
            cat_key = f"UNIVERSAL|||{category}"
            cross_device_concerns[cat_key].append(obs)

    # Calculate cross-device confidence
    cross_device_confidence = {}
    for key, obs_list in cross_device_concerns.items():
        projects = list(set(o["project_id"] for o in obs_list))
        device_types_involved = list(set(o["device_type"] for o in obs_list))
        n_projects = len(projects)
        n_devices = len(device_types_involved)
        resolved_count = sum(1 for o in obs_list if o["resolved"])
        category = obs_list[0]["category"] if obs_list else ""

        # V26: Universal MDR categories get lower CONFIRMED threshold (≥2 projects, any device types)
        is_universal = category in UNIVERSAL_MDR_CATEGORIES

        if n_projects >= 3 and resolved_count >= 3:
            confidence = 0.85
            maturity = "CONFIRMED"
        elif n_projects >= 2 and resolved_count >= 2:
            confidence = 0.82
            maturity = "CONFIRMED"
        elif n_projects >= 2 and is_universal:
            confidence = 0.78
            maturity = "CONFIRMED"
        elif n_projects >= 2 and n_devices >= 2:
            confidence = 0.75
            maturity = "CONFIRMED"
        elif n_projects >= 2:
            confidence = 0.72
            maturity = "CONFIRMED"
        elif resolved_count >= 2:
            confidence = 0.72
            maturity = "OBSERVED_ONCE"
        elif resolved_count >= 1:
            confidence = 0.68
            maturity = "OBSERVED_ONCE"
        else:
            confidence = 0.60
            maturity = "OBSERVED_ONCE"

        cross_device_confidence[key] = {
            "confidence": confidence,
            "maturity": maturity,
            "n_projects": n_projects,
            "n_device_types": n_devices,
            "device_types": device_types_involved,
            "projects": projects,
            "resolved_count": resolved_count,
            "total_occurrences": len(obs_list),
        }

    # PHASE 2: Group by device_type → concern, enriched with cross-device confidence
    device_concerns = defaultdict(lambda: defaultdict(list))
    for obs in device_specific_obs:
        dt = obs["device_type"]
        if dt == "UNKNOWN":
            continue
        category = obs["category"]
        concern = normalize_concern(obs["text"], category)
        device_concerns[dt][concern].append(obs)

    # Apply occurrence filter
    knowledge_base = {}
    for device_type, concerns in device_concerns.items():
        entries = []
        for concern, obs_list in sorted(concerns.items(), key=lambda x: -len(x[1])):
            category = obs_list[0]["category"]
            key = f"{category}|||{concern}"
            cd = cross_device_confidence.get(key, {})
            # V26: Also check universal category-level key for broader cross-device matching
            universal_key = f"UNIVERSAL|||{category}"
            cd_universal = cross_device_confidence.get(universal_key, {})
            if cd_universal.get("n_projects", 0) > cd.get("n_projects", 0):
                cd = cd_universal

            projects = list(set(o["project_id"] for o in obs_list))
            n_projects = len(projects)
            n_occurrences = len(obs_list)
            resolved_count = sum(1 for o in obs_list if o["resolved"])

            # Use cross-device confidence if available and higher
            cd_projects = cd.get("projects", []) if cd else []
            cd_device_types = cd.get("device_types", []) if cd else []
            cd_n_projects = cd.get("n_projects", 0) if cd else 0

            if cd and cd_n_projects > n_projects:
                confidence = cd["confidence"]
                maturity = cd["maturity"]
                other_devices = [d for d in cd_device_types if d != device_type]
                # Merge cross-device projects into source_projects
                all_source_projects = list(set(projects + cd_projects))
            else:
                if n_projects >= 2 and resolved_count >= 2:
                    confidence = 0.85
                    maturity = "CONFIRMED"
                elif n_projects >= 2:
                    confidence = 0.80
                    maturity = "CONFIRMED"
                elif resolved_count >= 1:
                    confidence = 0.70
                    maturity = "OBSERVED_ONCE"
                else:
                    confidence = 0.65
                    maturity = "OBSERVED_ONCE"
                other_devices = []
                all_source_projects = projects

            # V26: cross_device always populated for transparency
            cross_device_info = {
                "total_projects": cd_n_projects,
                "total_device_types": cd.get("n_device_types", 1) if cd else 1,
                "other_device_types": other_devices if other_devices else [],
                "cross_device_confirmed": bool(cd and cd_n_projects > n_projects),
            }

            entries.append({
                "concern": concern,
                "category": category,
                "frequency": {
                    "projects": n_projects,
                    "total_occurrences": n_occurrences,
                    "resolved_count": resolved_count,
                },
                "cross_device": cross_device_info,
                "confidence": confidence,
                "knowledge_maturity": maturity,
                "source_projects": all_source_projects,
                "example_texts": [o["text"][:200] for o in obs_list[:3]],
            })

        if entries:
            device_info = PROJECT_DEVICE_MAP.get(
                next((k for k, v in PROJECT_DEVICE_MAP.items() if v["device_type"] == device_type), ""),
                {}
            )
            clinical = CLINICAL_CONTEXT_LIBRARY.get(device_type, {})

            knowledge_base[device_type] = {
                "device_type": device_type,
                "device_class": device_info.get("class", "") if device_info else "",
                "regulatory_focus": [e["category"] for e in entries[:5]],
                "typical_nb_concerns": entries,
                "key_standards": clinical.get("key_guideline", ""),
                "clinical_context": {
                    "standard_of_care": clinical.get("standard_of_care", ""),
                    "key_guideline": clinical.get("key_guideline", ""),
                    "evidence_expectation": clinical.get("evidence_expectation", ""),
                    "source": clinical.get("source", ""),
                },
                "knowledge_summary": {
                    "total_concerns": len(entries),
                    "confirmed_count": sum(1 for e in entries if e["knowledge_maturity"] == "CONFIRMED"),
                    "observed_once_count": sum(1 for e in entries if e["knowledge_maturity"] == "OBSERVED_ONCE"),
                    "avg_confidence": round(sum(e["confidence"] for e in entries) / len(entries), 2) if entries else 0,
                },
            }

    return {
        "schema_name": "device_knowledge_base",
        "schema_version": "v1",
        "generated_at": datetime.now().isoformat(),
        "extraction_source": f"{len(all_obs)} NB observations from {len(set(o['project_id'] for o in all_obs if o['project_id']))} calibration projects",
        "methodology": {
            "occurrence_filter": "≥2 projects for same device type + same concern → CONFIRMED (0.85). Single project → OBSERVED_ONCE (0.70).",
            "resolution_filter": "NB concern was CLOSED by manufacturer providing additional evidence → higher confidence.",
            "classification": "Keyword-based deterministic — no LLM calls.",
            "regulatory_generic_filter": "Purely administrative requests (please provide X) discarded unless device-specific context present.",
        },
        "device_types": knowledge_base,
    }


# ============================================================
# UPDATE MODE: Post-project knowledge evolution
# ============================================================

def update_knowledge(existing_path: str, new_project_nb_path: str, new_project_id: str) -> Dict[str, Any]:
    """Update an existing knowledge base with new project data."""
    with open(existing_path, 'r', encoding='utf-8') as f:
        kb = json.load(f)

    new_obs = load_nb_observations(new_project_nb_path)
    print(f"Loaded {len(new_obs)} new observations from {new_project_id}")

    device_types = kb.get("device_types", {})
    updates_log = []

    for obs in new_obs:
        dt = obs["device_type"]
        if dt == "UNKNOWN" or dt not in device_types:
            continue

        category = obs["category"]
        concern = normalize_concern(obs["text"], category)
        device_entry = device_types[dt]
        concerns = device_entry.get("typical_nb_concerns", [])

        # Find matching concern
        matched = None
        for c in concerns:
            if c["concern"] == concern:
                matched = c
                break

        if matched:
            # Re-observed — increment confidence
            old_conf = matched["confidence"]
            matched["confidence"] = min(0.95, old_conf + 0.05)
            matched["frequency"]["projects"] += 1
            matched["frequency"]["total_occurrences"] += 1
            if obs.get("resolved"):
                matched["frequency"]["resolved_count"] += 1
            if matched["knowledge_maturity"] == "OBSERVED_ONCE" and matched["frequency"]["projects"] >= 2:
                matched["knowledge_maturity"] = "CONFIRMED"
            if new_project_id not in matched["source_projects"]:
                matched["source_projects"].append(new_project_id)
            updates_log.append(f"UPDATED: {concern} confidence {old_conf}→{matched['confidence']}")
        else:
            # New concern
            concerns.append({
                "concern": concern,
                "category": obs["category"],
                "frequency": {"projects": 1, "total_occurrences": 1, "resolved_count": 1 if obs.get("resolved") else 0},
                "confidence": 0.70,
                "knowledge_maturity": "OBSERVED_ONCE",
                "source_projects": [new_project_id],
                "example_texts": [obs["text"][:200]],
            })
            updates_log.append(f"NEW: {concern}")

    # Check for dormant concerns (not observed in any project — skip for now, needs date tracking)
    now = datetime.now()
    kb["last_updated_at"] = now.isoformat()
    kb["last_updated_by_project"] = new_project_id
    kb["update_log"] = updates_log

    return kb


# ============================================================
# CLI ENTRY POINT
# ============================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="V23 Knowledge Extractor — deterministic, no LLM")
    parser.add_argument("--mode", choices=["extract", "update"], default="extract",
                        help="extract: one-time from all projects. update: post-project evolution.")
    parser.add_argument("--reports-dir", default=None,
                        help="Directory containing NB observation JSON files (extract mode)")
    parser.add_argument("--existing-kb", default=None,
                        help="Path to existing device_knowledge_base.json (update mode)")
    parser.add_argument("--new-project-nb", default=None,
                        help="Path to new project NB observations JSON (update mode)")
    parser.add_argument("--new-project-id", default=None,
                        help="New project identifier (update mode)")
    parser.add_argument("--output", default="device_knowledge_base.json",
                        help="Output path for knowledge base JSON")

    args = parser.parse_args()

    if args.mode == "extract":
        default_reports_dir = os.path.join(
            os.path.expanduser("~"), "CER-RAG", "00_knowledge_extraction_build",
            "round2_autonomous_loop", "10_reports"
        )
        env_reports_dir = os.environ.get("CER_RAG_REPORTS_DIR")
        reports_dir = args.reports_dir or env_reports_dir or default_reports_dir
        reports_dir = os.path.abspath(reports_dir)
        print(f"Extracting knowledge from: {reports_dir}")
        kb = extract_knowledge(reports_dir)

    elif args.mode == "update":
        if not all([args.existing_kb, args.new_project_nb, args.new_project_id]):
            print("ERROR: --mode update requires --existing-kb, --new-project-nb, --new-project-id")
            sys.exit(1)
        kb = update_knowledge(args.existing_kb, args.new_project_nb, args.new_project_id)

    # Write output
    output_path = args.output
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(kb, f, ensure_ascii=False, indent=2)

    device_count = len(kb.get("device_types", {}))
    total_concerns = sum(
        len(v.get("typical_nb_concerns", [])) for v in kb.get("device_types", {}).values()
    )
    print(f"\nKnowledge base written: {output_path}")
    print(f"  Device types: {device_count}")
    print(f"  Total concern entries: {total_concerns}")
    confirmed = sum(
        sum(1 for c in v.get("typical_nb_concerns", []) if c.get("knowledge_maturity") == "CONFIRMED")
        for v in kb.get("device_types", {}).values()
    )
    observed = sum(
        sum(1 for c in v.get("typical_nb_concerns", []) if c.get("knowledge_maturity") == "OBSERVED_ONCE")
        for v in kb.get("device_types", {}).values()
    )
    print(f"  CONFIRMED: {confirmed}, OBSERVED_ONCE: {observed}")
