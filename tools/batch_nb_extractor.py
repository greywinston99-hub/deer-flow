"""
Phase C Step 7 — Batch NB Observation Extractor
Extracts NB observations from MDF 5004 DOCX files across D0 pipeline projects.
Deterministic — no LLM calls. Creates _nb_observations.json for knowledge_extractor.py.
"""

import os, re, json, sys, zipfile, xml.etree.ElementTree as ET
from datetime import datetime
from collections import defaultdict
from typing import Dict, List, Any, Optional, Tuple

# ============================================================
# DEVICE TYPE RESOLUTION (alias-aware, from device_alias_map.json)
# ============================================================

def load_alias_map(path: str) -> dict:
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def resolve_device_type(text: str, alias_map: dict) -> Tuple[Optional[str], str, float]:
    """Resolve device type from text using alias map. Returns (slug, matched_alias, confidence)."""
    text_lower = text.lower()
    entries = alias_map.get("entries", [])

    # Layer 1: Exact slug match
    for entry in entries:
        if entry["canonical_slug"].lower() in text_lower:
            return entry["canonical_slug"], entry["canonical_slug"], 1.0

    # Layer 2: Alias match
    best_match = None
    best_confidence = 0.0
    for entry in entries:
        for alias in entry["aliases"]:
            if alias.lower() in text_lower:
                # Negative keyword check
                has_negative = any(
                    nk.lower() in text_lower
                    for nk in entry.get("negative_keywords", [])
                )
                conf = 0.75 if has_negative else 0.90
                if conf > best_confidence:
                    best_confidence = conf
                    best_match = (entry["canonical_slug"], alias, conf)

    if best_match:
        return best_match

    # Layer 3: Fuzzy token overlap
    for entry in entries:
        alias_tokens = set()
        for alias in entry["aliases"]:
            alias_tokens.update(alias.lower().split())
        text_tokens = set(text_lower.split())
        overlap = alias_tokens & text_tokens
        if len(overlap) >= 2:
            return entry["canonical_slug"], f"fuzzy:{','.join(list(overlap)[:3])}", 0.60

    return None, "", 0.0


# ============================================================
# DOCX TEXT EXTRACTION
# ============================================================

def extract_docx_text(filepath: str) -> str:
    """Extract all text from a DOCX file."""
    try:
        with zipfile.ZipFile(filepath) as z:
            xml_content = z.read('word/document.xml')
        tree = ET.fromstring(xml_content)
        texts = []
        for t in tree.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t'):
            if t.text:
                texts.append(t.text)
        return '\n'.join(texts)
    except Exception as e:
        return f"EXTRACTION_ERROR: {e}"


# ============================================================
# NB QUESTION PARSING (MDF 5004 + general formats)
# ============================================================

def extract_questions_from_text(text: str) -> List[dict]:
    """Parse individual NB questions from MDF 5004 or general format DOCX text."""
    questions = []

    # Pattern 1: MDF 5004 format — Q#: or numbered questions
    mdf_pattern = re.compile(
        r'(?:^|\n)\s*(?:Q|Question\s*|Ref\.?\s*)?(\d+)[\.\):]\s*(.+?)(?=(?:\n\s*(?:Q|Question\s*|Ref\.?\s*)?\d+[\.\):])|\n\s*Manufacturer\s*Response|\Z)',
        re.IGNORECASE | re.DOTALL
    )

    # Pattern 2: BSI MDF table format — questions in review form
    bsi_pattern = re.compile(
        r'(?:Review\s*Questions?|Clause|Requirement|Ref)[^.]*?[.:]\s*(.+?)(?=(?:Review\s*Questions?|Clause|Requirement|Ref)|Manufacturer\s*Response|$)',
        re.IGNORECASE | re.DOTALL
    )

    # Pattern 3: Simple Q&A format
    simple_qa = re.findall(
        r'(?:^|\n)(?:Q\d*|Question)\s*[.:]\s*(.+?)(?=\n\s*(?:Q\d*|Question|A\d*|Answer|Response)\s*[.:]|\n\s*$)',
        text, re.IGNORECASE | re.DOTALL
    )

    # Try MDF pattern first
    matches = list(mdf_pattern.finditer(text))
    if len(matches) >= 3:
        for m in matches:
            q_num = m.group(1)
            q_text = m.group(2).strip()
            if len(q_text) > 20:  # Minimum question length
                questions.append({
                    "question_number": int(q_num),
                    "text": q_text[:500],
                    "source_format": "MDF_5004",
                })

    # Fall back to simple Q&A
    if len(questions) < 3:
        for i, q_text in enumerate(simple_qa):
            if len(q_text.strip()) > 20:
                questions.append({
                    "question_number": i + 1,
                    "text": q_text.strip()[:500],
                    "source_format": "simple_qa",
                })

    return questions


# ============================================================
# CONCERN CATEGORY CLASSIFICATION (keyword-based, deterministic)
# ============================================================

CATEGORY_PATTERNS = {
    "IFU_Labeling_Gap": [
        r'IFU|label|instruction|manual|labelling|标识|标签|说明书',
        r'information\s*for\s*use|user\s*manual|package\s*insert',
    ],
    "Clinical_Evidence_Insufficiency": [
        r'clinical\s*(?:data|evidence|trial|study|investigation|evaluation)',
        r'clinical\s*benefit|safety\s*profile|performance\s*data',
        r'PMCF|post[\s-]market\s*clinical|临床|试验|随访',
        r'equivalence|SOTA|state\s*of\s*the\s*art|literature',
        r'clinical\s*review|clinical\s*report|CER',
    ],
    "Risk_Management_Gap": [
        r'risk\s*(?:analysis|assessment|management|control|mitigation)',
        r'hazard|harm|FMEA|FTA|risk/benefit|风险',
        r'ISO\s*14971|residual\s*risk',
    ],
    "Biocompatibility": [
        r'biocompat|biological\s*(?:evaluation|assessment|safety|testing)',
        r'ISO\s*10993|cytotox|sensitization|irritation|endotoxin',
        r'生物相容|细胞毒|致敏',
    ],
    "GSPR_Standards_Compliance": [
        r'GSPR|general\s*safety\s*and\s*performance',
        r'standard\s*(?:compliance|conformity)|harmonised\s*standard',
        r'IEC\s*\d|EN\s*\d|ISO\s*\d|ASTM\s*\d',
        r'基本要求|标准符合',
    ],
    "Software_Cybersecurity": [
        r'software|firmware|IEC\s*62304|cyber|SOTA|SOM|SOP',
        r'algorithm|validation|verification.*software|软件',
    ],
    "Sterilization_Reprocessing": [
        r'steril|reprocess|clean|disinfect|autoclave|ETO|gamma',
        r'sterile\s*barrier|packaging\s*integrity|shelf\s*life',
        r'灭菌|消毒|清洗|重复使用',
    ],
    "Usability_Human_Factors": [
        r'usability|human\s*factor|IEC\s*62366|ergonomic',
        r'user\s*interface|user\s*error|use\s*error|可用性|人因',
    ],
    "General_Regulatory": [
        r'classification|notified\s*body|technical\s*documentation',
        r'declaration\s*of\s*conformity|CE\s*mark|MDR|UDI|EUDAMED',
        r'quality\s*(?:system|management)|ISO\s*13485|QMS',
        r'vigilance|adverse\s*event|incident\s*report|PMS',
    ],
    "Electrical_Safety_EMC": [
        r'EMC|electromagnetic|EMI|IEC\s*60601|electrical\s*safety',
        r'leakage\s*current|dielectric|insulation|grounding',
    ],
    "Manufacturing_Process_Control": [
        r'manufacturing|process\s*(?:validation|control|capability)',
        r'production|assembly|incoming\s*inspection|supplier',
        r'生产工艺|过程确认|进货检验',
    ],
    "Design_Verification_Validation": [
        r'design\s*(?:verification|validation|review|control|input|output)',
        r'design\s*change|design\s*history|DHF|设计',
        r'specification|requirement.*verif|test\s*report',
    ],
    "Material_Chemical_Characterization": [
        r'material\s*characterization|chemical\s*(?:analysis|composition)',
        r'leachable|extractable|DEHP|phthalate|latex|PVC',
        r'材料|化学表征',
    ],
    "Mechanical_Physical_Performance": [
        r'mechanical\s*(?:test|strength|property|performance)',
        r'physical\s*(?:test|property)|tensile|fatigue|wear|durability',
        r'机械|物理|强度|疲劳|耐久',
    ],
    "Device_Specific_Clinical": [
        r'specific\s*(?:device|product)\s*(?:performance|safety|test)',
        r'intended\s*(?:use|purpose|patient)|target\s*population',
        r'indication|contraindication|precaution|warning',
    ],
    "Equivalence_Justification": [
        r'equivalence|equivalent\s*device|predicate|substantial',
        r'comparable|similar\s*device|参照|等同|对比',
    ],
}

def classify_question(text: str) -> Tuple[str, float]:
    """Classify NB question into concern category. Returns (category, confidence)."""
    text_lower = text.lower()
    scores = defaultdict(float)

    for category, patterns in CATEGORY_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, text_lower):
                scores[category] += 1.0

    if not scores:
        return "General_Regulatory", 0.30

    best_category = max(scores, key=scores.get)
    max_score = scores[best_category]
    confidence = min(0.95, 0.40 + max_score * 0.15)

    return best_category, confidence


# ============================================================
# MAIN EXTRACTION
# ============================================================

def extract_project_nb(project_dir: str, project_id: str, alias_map: dict) -> Optional[dict]:
    """Extract NB observations from a single project's NB_QUESTIONS DOCX files."""
    nbq_dir = os.path.join(project_dir, "02_NB_BENCHMARK_ORIGINAL", "NB_QUESTIONS")
    if not os.path.isdir(nbq_dir):
        return None

    docx_files = sorted([f for f in os.listdir(nbq_dir) if f.endswith('.docx')])
    if not docx_files:
        return None

    all_questions = []
    project_device_type = "UNKNOWN"
    device_name = ""
    nb_type = "UNKNOWN"

    for fname in docx_files:
        fpath = os.path.join(nbq_dir, fname)
        text = extract_docx_text(fpath)

        if text.startswith("EXTRACTION_ERROR"):
            continue

        # Extract manufacturer and device info
        mfr_match = re.search(r'Manufacturer\s+(.+?)(?:\n|Title)', text[:500])
        device_match = re.search(r'Title\s*(?:of\s*)?File\s*(?:\(device\))?\s*(.+?)(?:\n|BSI|Reviewer)', text[:1000])

        if mfr_match and not device_name:
            mfr = mfr_match.group(1).strip()
        if device_match:
            device_name = device_match.group(1).strip()[:200]

        # Resolve device type
        if project_device_type == "UNKNOWN":
            slug, alias, conf = resolve_device_type(text[:5000], alias_map)
            if slug:
                project_device_type = slug

        # Detect NB type
        if "BSI" in text[:1000]:
            nb_type = "BSI"
        elif "TUV" in text[:1000] or "TÜV" in text[:1000]:
            nb_type = "TUV"
        elif "DEKRA" in text[:1000]:
            nb_type = "DEKRA"

        # Extract questions
        questions = extract_questions_from_text(text)
        all_questions.extend(questions)

    if not all_questions:
        return None

    # Build observations
    observations = []
    category_dist = defaultdict(int)

    for q in all_questions:
        category, conf = classify_question(q["text"])
        category_dist[category] += 1

        observations.append({
            "text": q["text"],
            "question_number": q.get("question_number", 0),
            "category": category,
            "classification_confidence": conf,
            "source_file": q.get("source_format", "unknown"),
            "device_type": project_device_type,
            "project_id": project_id,
        })

    return {
        "project_id": project_id,
        "project_name": os.path.basename(project_dir),
        "device": {
            "device_type": project_device_type,
            "device_name": device_name,
        },
        "nb_type": nb_type,
        "nb_source": f"{len(docx_files)} DOCX files from NB_QUESTIONS",
        "total_nb_observations": len(observations),
        "category_distribution": dict(category_dist),
        "observations": observations,
        "extraction_method": "batch_nb_extractor_v1 (deterministic DOCX parsing)",
        "extracted_at": datetime.now().isoformat(),
    }


# ============================================================
# BATCH RUNNER
# ============================================================

def run_batch_extraction(base_dir: str, alias_map_path: str, output_dir: str) -> List[str]:
    """Run batch extraction on all D0 pipeline projects."""
    alias_map = load_alias_map(alias_map_path)
    os.makedirs(output_dir, exist_ok=True)

    created_files = []
    skipped = []
    errors = []

    for d in sorted(os.listdir(base_dir)):
        if not d.startswith("PROJECT_"):
            continue

        project_dir = os.path.join(base_dir, d)
        if not os.path.isdir(project_dir):
            continue

        # Extract project ID (PROJECT_XXX)
        pid = "_".join(d.split("_")[:2])

        # Skip projects that already have NB observation JSONs
        existing = os.path.join(output_dir, f"{pid.split('_')[1]}_nb_observations.json")
        if os.path.exists(existing):
            skipped.append(pid)
            continue

        print(f"  Processing {pid}...", end=" ")

        try:
            result = extract_project_nb(project_dir, pid, alias_map)
            if result:
                output_path = os.path.join(output_dir, f"{pid.split('_')[1]}_nb_observations.json")
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)
                print(f"OK ({result['total_nb_observations']} obs, device={result['device']['device_type']})")
                created_files.append((pid, result))
            else:
                print("NO_QUESTIONS_FOUND")
                skipped.append(pid)
        except Exception as e:
            print(f"ERROR: {e}")
            errors.append((pid, str(e)))

    print(f"\n=== Batch Extraction Summary ===")
    print(f"Created: {len(created_files)} projects")
    for pid, result in created_files:
        print(f"  {pid}: {result['total_nb_observations']} obs → {result['device']['device_type']}")
    print(f"Skipped (existing/no data): {len(skipped)}")
    print(f"Errors: {len(errors)}")

    return created_files


if __name__ == "__main__":
    base_dir = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser(
        "~/CER-RAG/Source/项目文件夹_L1_CER_NB_PROJECTS_FOR_DEERFLOW"
    )
    alias_map_path = sys.argv[2] if len(sys.argv) > 2 else os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "knowledge", "device_alias_map.json"
    )
    output_dir = sys.argv[3] if len(sys.argv) > 3 else os.path.expanduser(
        "~/CER-RAG/00_knowledge_extraction_build/round2_autonomous_loop/10_reports"
    )

    print(f"Batch NB Extractor — Phase C Step 7")
    print(f"Base: {base_dir}")
    print(f"Alias map: {alias_map_path}")
    print(f"Output: {output_dir}")
    print()

    run_batch_extraction(base_dir, alias_map_path, output_dir)
