import os, csv, re

BASE = '/Users/winstonwei/CER-RAG/Source/项目文件夹_L1_CER_NB_PROJECTS_FOR_DEERFLOW'
OUT = '/Users/winstonwei/Documents/Playground/deer-flow/BIGDP2026_6_CDE90/assets'

EXCLUDED = {'PROJECT_001_项目复盘'}
EXCLUDED_KEYWORDS = ['项目复盘']

projects = sorted([d for d in os.listdir(BASE) if d.startswith('PROJECT_') and os.path.isdir(os.path.join(BASE, d))])

inventory_rows = []
for proj in projects:
    proj_path = os.path.join(BASE, proj)
    is_excluded = proj in EXCLUDED or any(kw in proj for kw in EXCLUDED_KEYWORDS)

    files = []
    for root, dirs, filenames in os.walk(proj_path):
        for f in filenames:
            files.append(os.path.join(root, f))

    pdfs = [f for f in files if f.lower().endswith('.pdf')]
    docxs = [f for f in files if f.lower().endswith('.docx')]

    cer_files = [f for f in files if re.search(r'CER|临床评价|Clinical Evaluation|临床评估', os.path.basename(f), re.I)]
    sota_files = [f for f in files if re.search(r'SOTA|State.of.Art|文献分析|现状分析', os.path.basename(f), re.I)]
    lit_files = [f for f in files if re.search(r'literature|文献|检索|search|pubmed|pmid|protocol', os.path.basename(f), re.I)]

    ae_files = [f for f in files if re.search(r'AE|adverse|不良事件|safety|安全性', os.path.basename(f), re.I)]
    endpoint_files = [f for f in files if re.search(r'endpoint|终点|efficacy|有效性|primary|secondary', os.path.basename(f), re.I)]
    subgroup_files = [f for f in files if re.search(r'subgroup|sub.group|子组|分组|stratified', os.path.basename(f), re.I)]
    denom_files = [f for f in files if re.search(r'denominator|分母|sample|population|enrolled|N=', os.path.basename(f), re.I)]
    benchmark_files = [f for f in files if re.search(r'benchmark|comparator|对照|对比|equivalence', os.path.basename(f), re.I)]
    claim_files = [f for f in files if re.search(r'claim|宣称|支持|support|benefit.risk', os.path.basename(f), re.I)]
    followup_files = [f for f in files if re.search(r'follow|随访|follow.up|FU|长期', os.path.basename(f), re.I)]

    clinical_docx = [f for f in docxs if re.search(r'clinical|data|result|outcome|table|表|safety|efficacy|AE|endpoint', os.path.basename(f), re.I)]
    clinical_pdf = [f for f in pdfs if re.search(r'clinical|data|result|outcome|table|表|safety|efficacy|AE|endpoint', os.path.basename(f), re.I)]

    name_lower = proj.lower()
    if any(k in name_lower for k in ['支架', 'stent']): device_type = 'stent'
    elif any(k in name_lower for k in ['瓣膜', 'valve']): device_type = 'heart_valve'
    elif any(k in name_lower for k in ['导管', 'catheter']): device_type = 'catheter'
    elif any(k in name_lower for k in ['起搏器', 'pacemaker']): device_type = 'pacemaker'
    elif any(k in name_lower for k in ['血糖', 'glucose', '微泰', '三诺']): device_type = 'glucose_monitor'
    elif any(k in name_lower for k in ['软件', 'software', 'ai']): device_type = 'software'
    elif any(k in name_lower for k in ['刀', 'knife', '消融', 'ablation', '海杰亚']): device_type = 'ablation_system'
    elif any(k in name_lower for k in ['影像', 'imaging', '超声', 'ultrasound', '普爱']): device_type = 'imaging'
    elif any(k in name_lower for k in ['植入', 'implant', '心擎', '健世']): device_type = 'implant_device'
    elif any(k in name_lower for k in ['透析', 'dialysis', '三鑫']): device_type = 'dialysis'
    elif any(k in name_lower for k in ['肺', 'lung', '肺盾']): device_type = 'lung_device'
    elif any(k in name_lower for k in ['眼科', 'eye', '巨目']): device_type = 'ophthalmic'
    elif any(k in name_lower for k in ['口腔', 'dental', '臣诺']): device_type = 'dental'
    else: device_type = 'medical_device'

    inventory_rows.append({
        'project_id': proj,
        'project_name': proj.replace('PROJECT_', '').replace('_', ' '),
        'source_path': proj_path,
        'device_type': device_type,
        'has_CER': 'yes' if len(cer_files) > 0 else 'no',
        'has_SOTA': 'yes' if len(sota_files) > 0 else 'no',
        'has_literature_pack': 'yes' if len(lit_files) >= 3 else ('maybe' if len(lit_files) > 0 else 'no'),
        'has_fulltext_pdf': 'yes' if len(pdfs) > 50 else 'maybe',
        'has_DOCX_tables': 'yes' if len(clinical_docx) > 0 else 'no',
        'has_PDF_tables': 'yes' if len(clinical_pdf) > 0 else 'no',
        'has_clinical_data_tables': 'yes' if len(clinical_docx) + len(clinical_pdf) > 3 else ('maybe' if len(clinical_docx) + len(clinical_pdf) > 0 else 'no'),
        'has_endpoint_tables': 'yes' if len(endpoint_files) > 0 else 'no',
        'has_AE_tables': 'yes' if len(ae_files) > 0 else 'no',
        'has_followup_data': 'yes' if len(followup_files) > 0 else 'maybe',
        'has_subgroup_data': 'yes' if len(subgroup_files) > 0 else 'no',
        'has_denominator_examples': 'yes' if len(denom_files) > 0 else 'maybe',
        'has_benchmark_data': 'yes' if len(benchmark_files) > 0 else 'no',
        'has_claim_support_data': 'yes' if len(claim_files) > 0 else 'no',
        'has_validation_value': 'unknown',
        'dataset_role': 'exclude' if is_excluded else 'unknown',
        'selection_reason': 'excluded_master_index' if is_excluded else '',
        'evidence_basis': '',
        'confidence': 'high',
        'notes': 'files=%d, pdf=%d, docx=%d, cer=%d, sota=%d' % (len(files), len(pdfs), len(docxs), len(cer_files), len(sota_files))
    })

# Scoring
for r in inventory_rows:
    if r['dataset_role'] == 'exclude':
        continue
    score = 0
    if r['has_CER'] == 'yes': score += 3
    if r['has_SOTA'] == 'yes': score += 2
    if r['has_literature_pack'] == 'yes': score += 2
    if r['has_AE_tables'] == 'yes': score += 2
    if r['has_endpoint_tables'] == 'yes': score += 2
    if r['has_clinical_data_tables'] == 'yes': score += 2
    if r['has_subgroup_data'] == 'yes': score += 1
    if r['has_denominator_examples'] == 'yes': score += 1
    if r['has_benchmark_data'] == 'yes': score += 1
    if r['has_claim_support_data'] == 'yes': score += 1
    total = int(r['notes'].split(',')[0].split('=')[1])
    if total > 5000: score += 2
    elif total > 3000: score += 1
    r['_score'] = score

candidates = [r for r in inventory_rows if r['dataset_role'] != 'exclude']
candidates.sort(key=lambda x: x['_score'], reverse=True)

selection_plan = {'calibration': 8, 'stress': 3, 'holdout': 3, 'special_evidence': 1}
for role, count in selection_plan.items():
    for r in candidates:
        if r['dataset_role'] == 'unknown' and count > 0:
            r['dataset_role'] = role
            r['selection_reason'] = 'score=%d, rich_clinical_data' % r['_score']
            r['has_validation_value'] = 'high' if role in ('calibration', 'holdout', 'special_evidence') else 'medium'
            count -= 1

headers = ['project_id','project_name','source_path','device_type','has_CER','has_SOTA','has_literature_pack','has_fulltext_pdf','has_DOCX_tables','has_PDF_tables','has_clinical_data_tables','has_endpoint_tables','has_AE_tables','has_followup_data','has_subgroup_data','has_denominator_examples','has_benchmark_data','has_claim_support_data','has_validation_value','dataset_role','selection_reason','evidence_basis','confidence','notes']

with open(os.path.join(OUT, 'CDE90_PROJECT_SOURCE_INVENTORY.csv'), 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=headers)
    w.writeheader()
    for r in inventory_rows:
        row = {h: r.get(h, '') for h in headers}
        w.writerow(row)

cal = [r for r in inventory_rows if r['dataset_role'] == 'calibration']
stress = [r for r in inventory_rows if r['dataset_role'] == 'stress']
hold = [r for r in inventory_rows if r['dataset_role'] == 'holdout']
spec = [r for r in inventory_rows if r['dataset_role'] == 'special_evidence']
print("Inventory written: %d projects" % len(inventory_rows))
print("  Excluded: %d" % sum(1 for r in inventory_rows if r['dataset_role'] == 'exclude'))
print("  Calibration (%d): %s" % (len(cal), [r['project_id'] for r in cal]))
print("  Stress (%d): %s" % (len(stress), [r['project_id'] for r in stress]))
print("  Holdout (%d): %s" % (len(hold), [r['project_id'] for r in hold]))
print("  Special (%d): %s" % (len(spec), [r['project_id'] for r in spec]))
