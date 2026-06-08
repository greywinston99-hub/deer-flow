"""
V28.3 — NB Data Standardizer
Convert manufacturer-internal task logs / status memos to formal NB question format.

Problem: Some NB observations in crosswalk matrices are internal task notes
(e.g., "拆分国内和国内标签--输出给王奎"), not formal regulatory questions.
This makes keyword-based crosswalk impossible regardless of language support.

Solution: Classify each NB item and convert task memos to standard NB format
based on context clues and known NB review patterns.
"""

import json, re
from pathlib import Path
from typing import Dict, List, Tuple


# ── Classification patterns ──────────────────────────────────────────────

# Task memo indicators (internal notes, not formal NB questions)
TASK_MEMO_PATTERNS = [
    r'输出给\w+',           # "输出给王奎"
    r'已提供[,，]?\s*见?\s*\d',  # "已提供，见08-1"
    r'已提供英文版',         # status update
    r'已增加[,，]?\s*见',    # "已增加，见关键工序..."
    r'已更新文件编码',       # internal action
    r'已同\w+沟通',          # "已同莱茵沟通"
    r'先提交.*再做整改',     # planning
    r'项目建议书---',        # owner assignment
    r'已做修改[,，]?\s*见附件',  # "已做修改，见附件05文件夹"
    r'增加.*典型性.*标[绿黄]',  # document markup instruction
    r'根据审核员要求',       # deferring to reviewer
]

# Status update indicators
STATUS_PATTERNS = [
    r'^已提供',              # "已提供..."
    r'^已增加',              # "已增加..."
    r'^已完成',              # "已完成..."
]

# Genuine regulatory question indicators
REGULATORY_QUESTION_PATTERNS = [
    r'[?？]',                # Has question mark
    r'需\w{2,4}[求证确说]',   # "需要确认/证明"
    r'(是否|为何|怎么|如何|怎样)',  # Question words
    r'(应当|必须|需要|要求|参考)',  # Requirement language
    r'(ISO|IEC|EN|ASTM|MDR|GSPR)\s*\d',  # Standards reference
    r'(验证|确认|评估|检测|测试)\w*$',  # Ends with validation/test
    r'第\s*\d+\.\d+\s*条',   # Clause reference
    r'(pls\.?|please|consider|confirm|provide|clarify)',  # NB request language
]


def classify_nb_item(text: str) -> Tuple[str, float]:
    """Classify an NB observation text. Returns (category, confidence)."""
    if not text or len(text.strip()) < 3:
        return ("empty", 1.0)

    text_clean = text.strip().replace('\n', ' ')

    # Check for regulatory question patterns first (highest signal)
    for pattern in REGULATORY_QUESTION_PATTERNS:
        if re.search(pattern, text_clean, re.IGNORECASE):
            return ("regulatory_question", 0.8)

    # Check for task memo patterns
    for pattern in TASK_MEMO_PATTERNS:
        if re.search(pattern, text_clean):
            return ("task_memo", 0.7)

    # Check for status updates
    for pattern in STATUS_PATTERNS:
        if re.search(pattern, text_clean):
            return ("status_update", 0.6)

    # Default: unclear/ambiguous
    return ("unclear", 0.3)


# ── Standardization mapping ─────────────────────────────────────────────

def standardize_task_memo(text: str, context: dict = None) -> str:
    """Convert a Chinese task memo to a formal NB question.

    Uses context clues from the original text and known NB review patterns
    for the device type to reconstruct the likely NB question.
    """
    text_clean = text.strip().replace('\n', ' ')

    # Pattern-based standardization
    mappings = [
        # ── Process validation ──
        (r'已增加.*关键工序验证.*特殊过程验证',
         'Please provide documented evidence of critical process validation and special process validation, including IQ/OQ/PQ records for all identified processes.'),
        (r'生产工艺流程图.*典型性',
         'Please provide the manufacturing process flow diagram with justification for the selected typicality samples.'),
        (r'挤出.*新增.*关键工序.*焊接',
         'Please provide process validation records for extrusion and ultrasonic welding, including process parameters, acceptance criteria, and validation reports.'),
        (r'精洗.*烘干.*粘接.*封口.*环氧乙烷.*解析',
         'Please provide process validation records for all manufacturing steps: cleaning, drying, bonding, sealing, EO sterilization, and desorption. Include IQ/OQ/PQ for each step.'),

        # ── Sterilization ──
        (r'灭菌验证.*环残',
         'Please provide the sterilization validation report including EO residual test results and biological indicator results per ISO 11135.'),
        (r'灭菌验证批次.*EO残留',
         'Please provide the EO residual test reports for sterilization validation batches per ISO 10993-7.'),

        # ── Cleanroom ──
        (r'洁净[生产实验室]{2,4}',
         'Please provide cleanroom qualification records including environmental monitoring data (particulate, microbial) per ISO 14644 for the stated monitoring period.'),

        # ── Design control ──
        (r'设计开发.*法规输入清单.*不同',
         'Please reconcile the discrepancy between the two design input documents. Provide a unified design input list with traceability to regulatory requirements.'),
        (r'法规输入清单',
         'Please provide the complete design input list with traceability to applicable regulatory requirements (MDR, applicable standards).'),

        # ── Documents / Certificates ──
        (r'13485.*证书.*11135',
         'Please provide the current ISO 13485:2016 certificate. Confirm whether the scope includes sterilization per ISO 11135.'),
        (r'文件编码.*替换.*引用',
         'Please update document coding references throughout the technical documentation to reflect the new document numbering system.'),

        # ── Labels / IFU ──
        (r'拆分.*国内.*标签',
         'Please provide separate domestic and international labelling. Clarify the labelling strategy for each target market.'),
        (r'标签.*输出',
         'Please provide finalized labelling for review. Labels should comply with MDR Annex I §23 and applicable symbol standards (ISO 15223-1).'),

        # ── Type test ──
        (r'型检报告.*翻译',
         'Please provide the type test report with certified English translation. Confirm the test standards applied and product configuration tested.'),

        # ── General document provision ──
        (r'已提供[,，]?\s*见?\s*\d+[-\d]*',
         'Please provide the referenced document in the technical documentation package. Confirm the document is current and controlled.'),
        (r'项目建议书.*王奎',
         'Please provide the project proposal / design initiation document for review.'),
        (r'已同莱茵沟通.*附件.*非强制英文.*文件名称.*英文',
         'Please confirm the language policy for technical documentation: confirm that document titles must be in English per NB agreement, and provide an updated document list with English titles.'),

        # ── Typicality / Representativeness ──
        (r'增加.*典型性.*标绿.*非典型.*删除',
         'Please justify the typicality selection. Mark typical configurations and remove non-typical configurations from the submission.'),
        (r'典型性.*标[绿黄].*具体文件.*附件',
         'Please provide the specific supporting documents for the marked typical configurations. Clarify how typicality was determined.'),

        # ── Aging ──
        (r'加速老化.*国内产品.*CE.*一致.*型号.*命名',
         'Please provide the accelerated aging report per ASTM F1980-21. Confirm the test article is representative of the CE-marked product; clarify any differences in model naming convention.'),

        # ── Packaging ──
        (r'11607.*11607',
         'Please provide packaging validation documentation per ISO 11607-1 and ISO 11607-2, including seal strength testing, integrity testing, and shelf-life validation.'),

        # ── Product configuration ──
        (r'泵.*泵管.*胃管',
         'Please clarify the product configuration: specify which components (pump, pump tube, stomach tube) are covered by this CE submission. Provide the system-level description.'),

        # ── English version ──
        (r'已提供英文版',
         'Please confirm all submitted documents have been provided in English. Provide a document list with language status for each file.'),

        # ── Procurement ──
        (r'采购清单.*物料名称',
         'Please provide the purchasing list / BOM with material names, specifications, and supplier information. Ensure critical suppliers are identified.'),
    ]

    for pattern, standardized in mappings:
        if re.search(pattern, text_clean):
            return standardized

    # Fallback: generic formalization
    return f'[Standardized from task memo] {text_clean}. Please provide the referenced documentation or clarify the action status.'


# ── Batch processing ─────────────────────────────────────────────────────

def standardize_crosswalk(input_path: str, output_path: str = None) -> dict:
    """Read a crosswalk matrix, standardize all NB items, write updated crosswalk.

    Returns the updated crosswalk data.
    """
    with open(input_path) as f:
        data = json.load(f)

    details = data.get('details', [])
    stats = {
        "total": len(details),
        "regulatory_question": 0,
        "task_memo": 0,
        "status_update": 0,
        "unclear": 0,
        "standardized": 0,
    }

    for item in details:
        text = item.get('nb_question', '')
        category, confidence = classify_nb_item(text)
        stats[category] = stats.get(category, 0) + 1

        # Add classification metadata
        item['nb_text_original'] = text
        item['nb_text_category'] = category
        item['nb_text_confidence'] = confidence

        # Standardize task memos and status updates
        if category in ('task_memo', 'status_update', 'unclear'):
            standardized = standardize_task_memo(text)
            item['nb_question'] = standardized
            item['nb_standardized'] = True
            stats['standardized'] += 1
        else:
            item['nb_standardized'] = False

    data['standardization_stats'] = stats

    if output_path:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"Standardized crosswalk written to: {output_path}")

    return data


# ── CLI ───────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        print("Usage: python3 nb_standardizer.py <crosswalk_matrix.json> [output.json]")
        print("  Standardizes Chinese task-memo NB items to formal NB question format.")
        sys.exit(1)

    input_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else input_path.replace('.json', '_standardized.json')

    data = standardize_crosswalk(input_path, output_path)

    stats = data.get('standardization_stats', {})
    print(f"\nResults:")
    print(f"  Total items: {stats.get('total', 0)}")
    for cat in ['regulatory_question', 'task_memo', 'status_update', 'unclear']:
        n = stats.get(cat, 0)
        if n > 0:
            print(f"  {cat}: {n}")
    print(f"  Standardized: {stats.get('standardized', 0)}")
