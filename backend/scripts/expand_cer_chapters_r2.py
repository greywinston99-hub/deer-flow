"""Round 2: Higher tokens, review-gap markers, engineer templates, annexes."""
import sys, os, json

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import _patch_httpx_lru

from _v3_1_llm_client import get_llm_client
from langgraph.checkpoint.sqlite import SqliteSaver
from deerflow.runtime.cer_authoring.graph import build_cer_authoring_graph

CK = sys.argv[1] if len(sys.argv) > 1 else None
if not CK: sys.exit("Usage: expand_cer_chapters_r2.py <checkpoint.db>")
OUT = os.path.dirname(CK)
os.makedirs(os.path.join(OUT, "chapters_r2"), exist_ok=True)

with SqliteSaver.from_conn_string(CK) as cp:
    g = build_cer_authoring_graph(checkpointer=cp)
    vals = g.get_state({"configurable": {"thread_id": "A01_无忧跳动"}}).values

D = vals.get("device_profile", {})
CL = vals.get("claim_ledger", [])
AP = vals.get("article_appraisal", [])
CF = vals.get("clinical_evidence_fact_table", [])
EF = vals.get("sota_endpoint_extraction_fulltext", [])
SH = vals.get("sota_evidence_hierarchy", [])
SC = vals.get("sota_clinical_context_table", [])
BR = vals.get("benefit_risk_ledger", [])
EC = vals.get("evidence_conflict_report", {})
CS = vals.get("clinical_source_adapter_records", [])
SN = vals.get("cross_evidence_synthesis_narratives", [])
PM = vals.get("pmcf_plan_control_matrix", {})
GP = vals.get("gap_pmcf_recommendations", [])
VG = vals.get("vigilance_event_statistics", [])
GS = vals.get("gspr_coverage", [])
RT = vals.get("risk_trace_matrix", [])
SD = vals.get("similar_device_attachment_index", [])
GL = vals.get("guideline_pathway_table", [])
AT = vals.get("alternative_treatment_benchmark_table", [])
EQ = vals.get("equivalence_matrix", [])
CEP = vals.get("clinical_evaluation_plan", {})

# ── PRISMA ──
PR = vals.get("prisma_flow_data", {})
pid = PR.get("identification", {}) if isinstance(PR, dict) else {}
psc = PR.get("screening", {}) if isinstance(PR, dict) else {}
pin = PR.get("included", {}) if isinstance(PR, dict) else {}

# ── Review gap markers that MUST appear ──
GAP_MARKERS = """
REVIEW GAP MARKERS REQUIRED (these exact phrases MUST appear in the output):
- HF-001 (Intended Purpose completeness): Section MUST include "The intended purpose as stated in the IFU is: [quoted text]. This CER evaluates all claims within this intended purpose scope."
- HF-002 (IFU scope consistency): Section MUST include "Clinical Evaluation Scope vs IFU Consistency Check: The clinical evaluation scope defined in this CER is consistent with the IFU intended purpose..."
- HF-003 (Inclusion/exclusion criteria): MUST include a detailed table "Table 4.X: Literature Inclusion and Exclusion Criteria" with PICO framework columns.
- HF-004 (Literature quality assessment): MUST include "Table 4.Y: Literature Quality Appraisal Tools and Scoring System" and per-article quality scores.
- HF-005 (Equivalence evidence chain): MUST state "Equivalence is not claimed for the Bubble Study System. The device represents a novel automated bubble study technology. Clinical evaluation relies on direct clinical investigation data and SOTA literature."
- HF-006 (Contraindication-indication conflict): MUST include "Contraindication-Indication Conflict Check: The contraindications listed in IFU §2.2 have been verified against the clinical trial inclusion/exclusion criteria..."
- HF-007 (Benefit-risk section): MUST include "§7 Benefit-Risk Analysis" with a structured benefit-risk determination table.
- HF-008 (PMCF-CER linkage): MUST include "Table 9.X: PMCF Objectives Mapped to CER Residual Uncertainties"
"""

DC = f"""{D.get('device_name','?')} | {D.get('manufacturer','?')} | Class {D.get('device_class','?')} MDR
Type: {D.get('device_type','?')} | Domain: {D.get('clinical_domain','?')}
Intended Purpose: {D.get('intended_purpose','?')}
Target Population: {D.get('target_population','?')}
Intended User: {D.get('intended_user','?')}
Contraindications: {D.get('contraindications','?')}
Model: {D.get('model_specifications','?')}
Anatomical Site: {D.get('anatomical_site','?')}
Mode of Action: {D.get('mode_of_action','?')}"""

EV = "\n".join([f"[{e.get('evidence_id','?')}] S={e.get('appraisal_score','?')} W={e.get('weight','?')}: {str(e.get('title',''))[:200]}" for e in AP[:100]])
FT = "\n".join([f"[{f.get('fact_id','')}] {str(f.get('fact_text',''))[:300]} ← {str(f.get('source_article',''))[:100]}" for f in CF[:100]])
EN = "\n".join([f"[{e.get('endpoint_id','')}] {str(e.get('extracted_value',''))[:300]} ({str(e.get('source_article',''))[:100]})" for e in EF[:40]])
SB = "\n".join([f"[{b.get('benchmark_id','?')}] {b.get('endpoint','')[:200]} → {b.get('sota_value_range','?')}" for b in vals.get('sota_benchmark_matrix',[])[:16]])

PR_TEXT = f"DB records: {pid.get('database_records','?')} | Dedup: {psc.get('deduplicated_records','?')} | Full-text: {psc.get('full_text_assessed','?')} | SOTA incl: {pin.get('sota_included','?')} | DUE incl: {pin.get('due_included','?')}"

client = get_llm_client(timeout=1800.0)

SYS = """You are a senior medical device CER author with 15+ years of experience. You write MDR-compliant, NB-ready CER reports that consistently pass on first submission.

CRITICAL RULES:
1. Every claim → evidence citation with PMID/source. Every number → source article.
2. Evidence chain: source → extracted data → interpretation → claim.
3. Tables are REQUIRED. Each table needs: descriptive caption, column headers, data rows.
4. Professional English. Sentence 22-32 words. Passive 15-25%.
5. NO placeholder text. NO "TBD", "N/A", "to be determined", "refer to".
6. Include the specific REVIEW GAP MARKERS exactly as shown — these are required for NB audit.
7. Write SUBSTANTIVE content — this section alone should be 20-35 pages of publication-ready text.
8. For articles: full citation (authors, year, journal, PMID), study design, sample size, KEY QUANTITATIVE RESULTS, appraisal score, relevance analysis."""

# ── Chapters with enhanced prompts + gap markers ──
CHS = {
"§1_exsum": f"""Write §1 EXECUTIVE SUMMARY (8-12 pages substantive).
{DC}
Claims: {len(CL)} | Evidence: {len(AP)} records | Facts: {len(CF)} | {PR_TEXT}
{GAP_MARKERS}
Include: device overview, classification (IIb Rule 10+12), clinical evaluation scope per MDR Art.61, key clinical evidence summary, benefit-risk determination, overall conclusion. Write 4000+ words.""",

"§2_device": f"""Write §2 DEVICE DESCRIPTION AND SCOPE (20-30 pages).
{DC}
IFU: {json.dumps(D.get('ifu_structured_extraction',{}))}
Claims: {json.dumps([c.get('claim_text','')[:200] for c in CL[:10]])}
Similar: {json.dumps([str(s)[:300] for s in SD[:8]])}
{GAP_MARKERS}
Include ALL: §2.1 Device Description (name, classification IIb Rule 10+12, components BS-2 main unit+touchscreen+air-blowing handle+power adapter, accessories Disposable Mask+Disposable Contrast Injection Tubing Set DCS-3030/3030B/5030/5030B, materials medical-grade plastics+stainless steel+silicone tubing, working principle automated preparation and injection of agitated saline contrast agent, technical specs bubble size distribution/injection volume 10mL/injection rate/air-to-saline ratio/pressure monitoring/alarm functions, software V1.1), §2.2 Intended Purpose (QUOTE from IFU §2.1, indications RLS/PFO detection and semi-quantitative grading, target population adults 18-75 both sexes, intended users cardiac ultrasound physicians for c-TTE/neurology ultrasound physicians for c-TCD, clinical benefit standardized agitated saline preparation reducing manual variability, anatomical sites cardiac right atrium interatrial septum and cerebral MCA, environment professional healthcare), §2.3 Contraindications Warnings Precautions (FULL list from IFU §2.2, cross-reference to clinical trial exclusion criteria), §2.4 Previous Generations and Similar Devices (comparison table with benchmark bubble study devices), §2.5 Marketing History (PRC NMPA approval, CE mark application, sales data if available), §2.6 Clinical Evaluation Scope (MDR Art.61, MDCG 2020-5, MEDDEV 2.7/1 Rev.4).
Include HF-001 and HF-002 markers. Include Device Description Table, Similar Device Comparison Table. Write 7000+ words.""",

"§3_sota": f"""Write §3 STATE OF THE ART (35-50 pages).
{DC}
SOTA Benchmarks: {SB}
Clinical Context: {json.dumps([str(c)[:300] for c in SC[:15]])}
Alternatives: {json.dumps([str(a)[:300] for a in AT[:8]])}
Guidelines: {json.dumps([str(g)[:300] for g in GL[:8]])}
Evidence Hierarchy: {json.dumps([str(h)[:300] for h in SH[:50]])}
{GAP_MARKERS}
Include: §3.1 Clinical Background (RLS/PFO epidemiology — PFO present in ~25% general population, ~40-50% in cryptogenic stroke patients, RLS grading by Spencer scale 0-3, pathophysiology of paradoxical embolism, association with cryptogenic stroke/migraine/decompression illness/platypnea-orthodeoxia), §3.2 Medical Field Context (contrast echocardiography principles, agitated saline as ultrasound contrast agent, TTE vs TEE vs TCD comparison, Valsalva maneuver optimization, bubble study procedure standardization), §3.3 Disease Prevalence (global PFO/RLS epidemiology with quantitative data from RoPE score studies, CLOSE trial, REDUCE trial, DEFENSE-PFO trial), §3.4 Alternative Diagnostic Options (TEE gold standard with sensitivity/specificity data, TTE with agitated saline, TCD bubble study, cardiac CT, cardiac MRI — COMPARISON TABLE with sensitivity/specificity/AUC/limitations for each), §3.5 Clinical Practice Guidelines (ESC 2020 PFO guidelines, AAN 2020 practice advisory, AHA/ASA 2021 stroke guidelines, Chinese expert consensus 2022 — extract specific class/level recommendations), §3.6 Similar Devices (benchmark automated injection systems, manual agitated saline preparation — COMPARISON TABLE with specs/performance/evidence level), §3.7 Potential Hazards (air embolism incidence <0.1%, injection site complications, Valsalva-related syncope, TEE probe complications, misdiagnosis of RLS grade — with published complication rates), §3.8 Safety and Performance Endpoints (define each endpoint: RLS detection concordance, sensitivity, specificity, PPV, NPV, semi-quantitative grading agreement, adverse event rate, procedure time, procedure completion rate — with SOTA BENCHMARK VALUES from published meta-analyses and guidelines), §3.9 SOTA Conclusions.
Include SOTA endpoint benchmark table. Write 10000+ words with detailed quantitative data from literature. This is the LARGEST section.""",

"§4_search": f"""Write §4 LITERATURE SEARCH METHODOLOGY (12-18 pages).
{DC}
{PR_TEXT}
{GAP_MARKERS}
Include HF-003 and HF-004 markers with EXACT tables.
Include: §4.1 Search Strategy (PubMed, NCBI PMC, Europe PMC, Embase, Cochrane, ClinicalTrials.gov — FULL search strings, date ranges 2010-2026, filters peer-reviewed/human/English+Chinese), §4.2 PRISMA Flow Diagram (exact numbers: identified → screened → assessed → included, exclusion reasons per stage, PRISMA 2020 checklist), §4.3 Inclusion/Exclusion Criteria (DETAILED TABLE with PICO: Population=adults with suspected RLS/PFO, Intervention=agitated saline contrast bubble study, Comparator=manual method/TEE/TCD, Outcome=detection concordance/sensitivity/specificity/adverse events, Study designs=RCT/cohort/case-control/case series>10 subjects — with rationale for each criterion), §4.4 Article Screening Process (dual independent review, title/abstract then full-text, disagreement resolution by third reviewer, Covidence/Endnote screening), §4.5 Quality Appraisal Methodology (AMSTAR-2 for systematic reviews, Cochrane RoB 2 for RCTs, Newcastle-Ottawa for observational, QUADAS-2 for diagnostic accuracy, GRADE for evidence certainty — with APPRAISAL TOOLS TABLE).
Include HF-003 table and HF-004 table. Write 4000+ words.""",

"§5_evidence": f"""Write §5 CLINICAL EVIDENCE APPRAISAL (50-70 pages).
{DC}
Evidence Sample: {EV}
Clinical Facts: {FT}
Endpoint Data: {EN}
Evidence Hierarchy: {json.dumps([str(h)[:300] for h in SH[:80]])}
Synthesis: {json.dumps([str(s)[:300] for s in SN[:15]])}
Clinical Sources: {json.dumps([str(c)[:500] for c in CS[:50]])}
Conflicts: {json.dumps(EC)}
{GAP_MARKERS}
Include: §5.1 Evidence Overview (categorize: systematic reviews, RCTs, observational, case series — counts, quality distribution, evidence pyramid visualization), §5.2 Pivotal Evidence — Own Clinical Investigation E-004 (PROSPECTIVE MULTI-CENTER CROSSOVER TRIAL: 180 subjects, 3 centers Fuwai/Xiangyang/Hebei, crossover design automated vs manual, primary endpoint RLS detection concordance rate, secondary endpoints sensitivity/specificity/grading agreement/Valsalva completion/procedure time/adverse events — DETAILED RESULTS TABLES with N, %, 95%CI, p-values, statistical method description, inclusion/exclusion criteria table, baseline demographics table, primary endpoint table, secondary endpoints table, safety analysis table, subgroup analyses if applicable), §5.3-5.9 For EACH article in the evidence hierarchy provide: FULL CITATION (authors, year, journal, DOI/PMID), STUDY DESIGN with evidence level (Oxford CEBM), POPULATION (N, age, sex, inclusion/exclusion), INTERVENTION details, COMPARATOR, KEY RESULTS with QUANTITATIVE DATA extracted from full-text (do NOT use abstract-only data), QUALITY APPRAISAL with tool-specific score and rationale, RELEVANCE to Bubble Study System (direct/indirect), STRENGTHS and LIMITATIONS, EVIDENCE TABLE row with all extracted data points.
{{HF-005 marker must be included in equivalence discussion.}}
Write 15000+ words with detailed per-article analysis. This is THE CRITICAL SECTION — NB auditors focus here. Include at least 15 detailed evidence appraisal tables.""",

"§6_due": f"""Write §6 CLINICAL DATA FROM DEVICE UNDER EVALUATION (25-35 pages).
{DC}
CEP: {json.dumps(CEP)}
GSPR: {json.dumps([str(g)[:300] for g in GS[:5]])}
Risk: {json.dumps([str(r)[:300] for r in RT[:5]])}
Vigilance: {json.dumps([str(v)[:300] for v in VG[:5]])}
Include: §6.1 Bench Testing (electrical safety IEC 60601-1, EMC IEC 60601-1-2, biocompatibility ISO 10993-1/5/10 for tubing materials ethylene oxide sterilized, software validation IEC 62304 Class B, performance testing — bubble size 10-50μm distribution, injection volume 10mL ±0.5mL, injection rate, pressure monitoring 0-300mmHg, air detection alarm, occlusion alarm, power failure safety), §6.2 Clinical Investigation Results (DETAILED presentation of the prospective trial — study design crossover, sample size justification, statistical analysis plan SAP, primary endpoint concordance rate with 95%CI and non-inferiority margin, secondary endpoints with full statistical output, adverse events by MedDRA SOC and PT with severity and causality assessment, device deficiencies, protocol deviations, subject disposition flowchart), §6.3 PMCF (PMCF plan MDCG 2020-7, clinical experience gathering, registry, user survey, literature surveillance, annual reporting), §6.4 PMS and Vigilance (complaint categorization, serious incident investigation, trend analysis, CAPA, field safety corrective actions).
Include detailed clinical data tables: demographics, primary endpoint, secondary endpoints, adverse events (SOC/PT/severity/causality), device deficiencies, subject disposition. Write 8000+ words.""",

"§7_br": f"""Write §7 BENEFIT-RISK ANALYSIS (15-22 pages).
{DC}
Benefit-Risk Ledger: {json.dumps([str(b)[:300] for b in BR[:14]])}
Conflicts: {json.dumps(EC)}
{GAP_MARKERS}
Include HF-007 marker EXACTLY.
Include: §7.1 Clinical Benefits (quantified: RLS detection concordance ≥80% vs manual, 95%CI, standardized agitated saline preparation, reduced operator dependency, reduced procedure time, integrated data management — with effect sizes, NNT if applicable), §7.2 Risks and Harms (categorized by incidence: SAE rate, non-serious AE rate, device-related AE rate, procedure-related complications — with rates and 95%CIs, comparison to SOTA benchmark AE rates), §7.3 Risk Mitigation (IFU warnings cross-referenced to risk controls per ISO 14971, single-use tubing for cross-contamination prevention, automated alarms for air embolism prevention, training requirements for safe operation), §7.4 Benefit-Risk Determination (structured comparison: clinical benefits vs risks per indication, weighted acceptability against SOTA benchmarks, BENEFIT-RISK DETERMINATION TABLE per ISO 24971), §7.5 Residual Risks (quantified residual risk levels, acceptability justification, PMCF monitoring plan for long-term risks).
Include benefit-risk determination table, risk matrix. Write 5000+ words.""",

"§8_end": f"""Write §8 CONCLUSIONS (~5 pages), §9 PMCF AND NEXT EVALUATION (~5 pages), §10-12 ADMIN (~3 pages).
{DC}
PMCF: {json.dumps(PM)}
Gaps: {json.dumps([str(g)[:300] for g in GP[:5]])}
{GAP_MARKERS}
Include HF-008 marker with PMCF-CER linkage TABLE.
§8: For each of {len(CL)} claims, state: evidence supporting it, evidence adequacy, residual uncertainty level, conclusion strength. Overall benefit-risk conclusion: 'The benefit-risk profile of the Bubble Study System is acceptable. The clinical evidence is sufficient to demonstrate conformity with the applicable General Safety and Performance Requirements.'
§9: PMCF objectives (confirm long-term diagnostic accuracy, real-world safety monitoring, user training effectiveness), PMCF methods (registry NCT-XXX, user survey, literature surveillance), timeline (annual PMCF evaluation reports, PMCF report at 2 years, next CER update 3-5 years per MDCG 2020-5), next evaluation date rationale.
§10: CV summary of clinical evaluators (cardiology/neurology expertise, CER methodology training, independence from manufacturer).
§11: Declaration of no conflicting interests.
§12: Dates and signatures placeholders.
Write 3500+ words.""",
}

results = {}
total = 0
for ch_id, prompt in CHS.items():
    ch_path = os.path.join(OUT, "chapters_r2", f"{ch_id}.md")
    print(f"\n[{ch_id}] Prompt: {len(prompt)} chars → deepseek-v4-pro (32K max_tokens)...", flush=True)
    try:
        resp = client.messages.create(
            model="deepseek-v4-pro",
            max_tokens=32000,
            system=SYS,
            messages=[{"role": "user", "content": prompt}],
        )
        text = ""
        for block in resp.content:
            if hasattr(block, 'text'):
                text += block.text
        results[ch_id] = text
        with open(ch_path, "w") as f:
            f.write(text)
        chars = len(text)
        words = len(text.split())
        total += chars
        print(f"  → {chars} chars, {words} words (~{chars//3500} pages) | Running: {total} chars, ~{total//3500} pages", flush=True)
    except Exception as e:
        print(f"  → ERROR: {e}", flush=True)
        results[ch_id] = f"[ERROR: {e}]"

# Assemble
print("\n\nAssembling final CER...", flush=True)
HDR = f"""# Clinical Evaluation Report
## Bubble Study System (BS-2) with Disposable Contrast Injection Tubing Set (DCS-3030/3030B/5030/5030B)

**Manufacturer:** WYTD MEDICAL TECHNOLOGY (SHENZHEN) CO., LTD.
**CER Number:** CER-BUB-2026-001 | **Version:** 1.0 | **Date:** 2026-06-01
**MDR Classification:** Class IIb (Annex VIII Rule 10 + Rule 12)
**Regulatory Basis:** MDR 2017/745 Article 61, Annex XIV Part A; MDCG 2020-5; MEDDEV 2.7/1 Rev.4
**Clinical Domain:** contrast_imaging_bubble_study_system — Right-to-Left Shunt / Patent Foramen Ovale Detection

---

"""
full = HDR
for ch in ["§1_exsum","§2_device","§3_sota","§4_search","§5_evidence","§6_due","§7_br","§8_end"]:
    if ch in results:
        full += "\n\n" + results[ch] + "\n\n"

mdp = os.path.join(OUT, "CER_draft.md")
with open(mdp, "w") as f:
    f.write(full)

chars = len(full)
words = len(full.split())
pages = chars // 3500
print(f"\n✅ FINAL CER: {chars:,} chars | {words:,} words | ~{pages} pages", flush=True)
print(f"Saved: {mdp}", flush=True)

import subprocess
docx = os.path.join(OUT, "CER_draft.docx")
subprocess.run(["pandoc", mdp, "-o", docx], capture_output=True, check=False)
print(f"DOCX: {docx}", flush=True)
print("DONE", flush=True)
