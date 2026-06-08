"""Targeted expansion of §3 SOTA and §5 Evidence to reach 150+ pages."""
import sys, os, json

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import _patch_httpx_lru

from _v3_1_llm_client import get_llm_client
from langgraph.checkpoint.sqlite import SqliteSaver
from deerflow.runtime.cer_authoring.graph import build_cer_authoring_graph

CK = sys.argv[1] if len(sys.argv) > 1 else None
if not CK: sys.exit("Usage: expand_key_chapters.py <checkpoint.db>")
OUT = os.path.dirname(CK)

with SqliteSaver.from_conn_string(CK) as cp:
    g = build_cer_authoring_graph(checkpointer=cp)
    vals = g.get_state({"configurable": {"thread_id": "A01_无忧跳动"}}).values

D = vals.get("device_profile", {})
AP = vals.get("article_appraisal", [])
CF = vals.get("clinical_evidence_fact_table", [])
EF = vals.get("sota_endpoint_extraction_fulltext", [])
SH = vals.get("sota_evidence_hierarchy", [])
SC = vals.get("sota_clinical_context_table", [])
CS = vals.get("clinical_source_adapter_records", [])
SN = vals.get("cross_evidence_synthesis_narratives", [])
SB = vals.get("sota_benchmark_matrix", [])
GL = vals.get("guideline_pathway_table", [])
AT = vals.get("alternative_treatment_benchmark_table", [])
SD = vals.get("similar_device_attachment_index", [])

DC = f"""{D.get('device_name','?')} | {D.get('manufacturer','?')} | Class {D.get('device_class','?')}
Type: {D.get('device_type','?')}
Intended Purpose: {D.get('intended_purpose','?')}
Target Population: {D.get('target_population','?')}
Anatomical Site: {D.get('anatomical_site','?')}
Mode of Action: {D.get('mode_of_action','?')}
Contraindications: {D.get('contraindications','?')}"""

# Evidence data for detailed appraisal
EV = "\n".join([f"[{e.get('evidence_id','?')}] S={e.get('appraisal_score','?')} W={e.get('weight','?')}: {str(e.get('title',''))[:200]}" for e in AP[:100]])
FT = "\n".join([f"[{f.get('fact_id','')}] {str(f.get('fact_text',''))[:400]} ← {str(f.get('source_article',''))[:100]}" for f in CF[:100]])
EN = "\n".join([f"[{e.get('endpoint_id','')}] {str(e.get('extracted_value',''))[:400]}" for e in EF[:50]])
SH_T = "\n".join([str(h)[:400] for h in SH[:100]])
CS_T = "\n".join([str(c)[:500] for c in CS[:80]])
SN_T = "\n".join([str(s)[:400] for s in SN[:15]])

client = get_llm_client(timeout=1800.0)

SYS = """You are a senior medical device CER author. Write SUBSTANTIVE, publication-ready content following MDR 2017/745 and MDCG 2020-5.

CRITICAL RULES:
1. Every claim → evidence with source. Every number → PMID/source article.
2. Evidence chain: source → extracted data → interpretation → claim.
3. Professional English, 22-32 word sentences, 15-25% passive.
4. NO placeholder text. NO "TBD" or "N/A".
5. Include DETAILED TABLES with descriptive captions, column headers, and data rows.
6. For each article: FULL citation (authors, year, journal, PMID), study design, sample size, KEY QUANTITATIVE RESULTS, appraisal score, relevance.
7. Generate AS MUCH content as possible — this section must be comprehensive and detailed."""

# ── §3 SOTA EXPANSION ──
ch3_prompt = f"""Write §3 STATE OF THE ART (35-50 pages of SUBSTANTIVE content).

{DC}
SOTA Benchmarks: {json.dumps([str(b)[:300] for b in SB[:16]])}
Clinical Context: {json.dumps([str(c)[:400] for c in SC[:15]])}
Alternatives: {json.dumps([str(a)[:400] for a in AT[:8]])}
Guidelines: {json.dumps([str(g)[:400] for g in GL[:8]])}
Evidence Hierarchy: {SH_T}

Write ALL of these subsections with FULL detail:

§3.1 CLINICAL BACKGROUND AND DISEASE OVERVIEW (8-10 pages)
- Patent Foramen Ovale (PFO): embryology, anatomy of fossa ovalis, prevalence in general population (~25% autopsy series by Hagen PT et al., Mayo Clin Proc 1984, PMID:6694527), PFO size classification (small <2mm, medium 2-4mm, large ≥4mm)
- Right-to-Left Shunt (RLS): pathophysiological mechanisms, spontaneous vs provoked RLS, Valsalva maneuver augmentation, RLS grading by Spencer scale (Grade 0: no microbubbles, Grade 1: <10, Grade 2: 10-30, Grade 3: >30, Grade 4: 'curtain' effect)
- Clinical significance: PFO and cryptogenic stroke (PFO found in ~40-50% cryptogenic stroke patients vs ~25% general population, Lechat P et al., NEJM 1988, PMID:3344007; Webster MW et al., Lancet 1988), RoPE score for PFO-attributable stroke risk (Kent DM et al., Neurology 2013, PMID:23884037)
- Other PFO-associated conditions: migraine with aura (Anzola GP et al., Neurology 2006), decompression illness in divers (Torti SR et al., Eur Heart J 2004), platypnea-orthodeoxia syndrome, high-altitude pulmonary edema
- Epidemiology: PFO prevalence by age group (34% age<30, 25% age 30-80, 20% age>80), RLS prevalence in stroke populations (CLOSE trial Mas JL et al., NEJM 2017 PMID:28891473; REDUCE trial Sondergaard L et al., Lancet 2017 PMID:28935199; DEFENSE-PFO Lee PH et al., JACC 2018 PMID:29389070; RESPECT trial Saver JL et al., NEJM 2017 PMID:28891472), Chinese PFO epidemiology data
- Pathophysiology of paradoxical embolism: Virchow's triad adaptation, thrombus formation in PFO tunnel, Valsalva-induced RLS, atrial septal aneurysm as risk multiplier
- Natural history: annual stroke recurrence risk 0.5-1.5% on medical therapy alone, meta-analysis data from PFO closure trials

§3.2 RELATED MEDICAL FIELD AND CLINICAL CONTEXT (5-8 pages)
- Contrast echocardiography: principles of ultrasound contrast detection, microbubble physics (size 10-50μm, resonance frequency, acoustic impedance), agitated saline as contrast agent (preparation technique: 9mL saline + 1mL air + 0.5-1mL patient blood, agitated between 2 syringes via 3-way stopcock, immediate IV bolus), agitated saline vs commercial ultrasound contrast agents (e.g. Optison, Definity — comparison table)
- Transthoracic echocardiography (TTE): apical 4-chamber view, subcostal view, contrast appearance timing (3-5 cardiac cycles for RLS), advantages (non-invasive, widely available), limitations (poor acoustic windows, body habitus, lung disease)
- Transesophageal echocardiography (TEE): gold standard for PFO anatomical assessment, multiplane imaging, contrast bubble visualization, advantages (superior image quality), limitations (semi-invasive, sedation required, Valsalva feasibility reduced)
- Transcranial Doppler (TCD): unilateral or bilateral MCA insonation, embolic signal detection (high-intensity transient signals HITS), Spencer grading, advantages (non-invasive, quantitative), limitations (~10% inadequate temporal windows, cannot localize shunt)
- Comparison Table: c-TTE vs c-TEE vs c-TCD — sensitivity, specificity, gold standard reference, advantages, limitations, contraindications, cost, procedure time (with published data citations)

§3.3 MEDICAL CONDITIONS AND DISEASE PREVALENCE (5-8 pages)
- Global PFO prevalence data: meta-analysis by Mattle HP et al. (Cerebrovasc Dis 2008), systematic review by Homma S et al. (JACC 2005)
- Cryptogenic stroke epidemiology: global incidence 0.5-1.0/1000 person-years, proportion PFO-attributable ~40-50%, age-stratified data
- Chinese PFO/RLS epidemiology: published Chinese data from multi-center studies, comparison to Western populations
- Risk stratification: RoPE score calculator (age, hypertension, diabetes, prior stroke/TIA, smoking, cortical vs deep infarct, 10 items → score 0-10), PFO-Associated Stroke Causal Likelihood (PASCAL) classification
- Subgroup analyses: age <60 vs ≥60, PFO size effect modification, atrial septal aneurysm interaction

§3.4 ALTERNATIVE DIAGNOSTIC OPTIONS (6-10 pages)
- COMPREHENSIVE COMPARISON TABLE: TEE (gold standard), c-TTE with agitated saline, c-TCD bubble study, cardiac CT angiography, cardiac MRI, invasive cardiac catheterization with oximetry — columns: technique, sensitivity (with 95%CI), specificity, AUC, advantages, limitations, contraindications, procedure time, cost, radiation exposure, evidence level
- Medical therapy alternatives: antiplatelet (aspirin, clopidogrel), anticoagulation (warfarin, DOACs) — efficacy data from PFO closure trials, annual stroke recurrence rates
- PFO closure devices: Amplatzer PFO Occluder (FDA approved 2016), Gore Cardioform Septal Occluder, other devices — comparison table with procedural success rates, closure rates, complication rates, long-term outcomes from RESPECT/CLOSE/REDUCE/DEFENSE-PFO trials
- Clinical decision algorithms: AHA/ASA 2021 secondary stroke prevention algorithm, ESC 2020 PFO management pathway, PFO-Associated Stroke Causal Likelihood (PASCAL) classification-guided management

§3.5 CLINICAL PRACTICE GUIDELINES (6-8 pages)
- ESC 2020 Guidelines for PFO Management (Pristipino C et al., Eur Heart J 2019 PMID:30137238): Class I/IIa/IIb/III recommendations with evidence levels — extract ALL bubble-study-relevant recommendations
- AHA/ASA 2021 Guideline for Secondary Stroke Prevention (Kleindorfer DO et al., Stroke 2021 PMID:34024117): PFO closure recommendations, diagnostic workup algorithm
- AAN 2020 Practice Advisory (Messe SR et al., Neurology 2020 PMID:32253354): PFO closure for secondary stroke prevention, patient selection criteria
- Chinese Expert Consensus on PFO Management (2022): diagnosis, management algorithms, bubble study standardization recommendations
- EACVI/ASE Recommendations for Echocardiography in Stroke (2017): bubble study protocol, reporting standards
- COMPARISON TABLE: Guideline recommendations across societies — diagnostic method, shunt grading, PFO closure indications, medical therapy, follow-up, evidence levels

§3.6 SIMILAR DEVICES AND BENCHMARK COMPARISON (5-8 pages)
- Manual agitated saline preparation (current standard): technique, published concordance rates, inter-operator variability (Cohen's κ data from published studies), limitations
- Semi-automated devices: any published data on automated injection systems for bubble studies — COMPARISON TABLE: device name, manufacturer, regulatory status, key features, published performance data, limitations
- Benchmark performance values: manual method concordance rates from systematic reviews and meta-analyses — sensitivity 85-95%, specificity 90-98% for RLS detection depending on comparator (TEE gold standard), grading agreement κ 0.6-0.8
- Injection delivery systems: contrast injectors for echocardiography (e.g. ultrasound contrast agent delivery systems) — comparison to agitated saline systems, regulatory classification differences

§3.7 POTENTIAL HAZARDS AND KNOWN COMPLICATIONS (5-8 pages)
- Air embolism: incidence <0.1% with proper technique, pathophysiology of cerebral air embolism, case reports and systematic review data (Romero JR et al., Stroke 2009)
- Injection site complications: pain, hematoma, infection, venous thromboembolism — incidence rates from published series
- Valsalva maneuver risks: syncope, blood pressure changes, cardiac arrhythmia provocation, retinal hemorrhage (rare)
- TEE-specific complications: esophageal injury, aspiration, sedation-related events, dental trauma
- TCD limitations: inadequate temporal windows (8-20% prevalence by age/sex/race), operator dependency
- Misdiagnosis: false-positive (intrapulmonary shunt, 5-10%), false-negative (inadequate Valsalva, delayed contrast arrival), inter-observer variability in shunt grading (κ data)
- COMPLICATION RATES TABLE: complication type, incidence, 95%CI, severity, source studies

§3.8 SAFETY AND PERFORMANCE ENDPOINTS (6-10 pages)
- For EACH endpoint, provide: definition, measurement method, SOTA benchmark value with source, acceptance criterion
- Diagnostic accuracy endpoints: RLS detection concordance rate (benchmark ≥80% vs manual method), sensitivity for RLS detection (benchmark 85-95% vs TEE gold standard), specificity (benchmark ≥90%), PPV, NPV, semi-quantitative grading agreement (Cohen's κ benchmark ≥0.7)
- Safety endpoints: serious adverse event rate (benchmark <1%), device-related AE rate (benchmark <0.5%), procedure-related complication rate (benchmark <2%), air embolism incidence (benchmark <0.01%)
- Procedural endpoints: procedure completion rate (benchmark ≥95%), procedure time (benchmark <5 minutes for injection+imaging), Valsalva maneuver completion rate (benchmark ≥90%), inadequate image quality rate (benchmark <10%)
- User endpoints: user satisfaction, learning curve (cases to proficiency), inter-operator variability
- SOTA ENDPOINT BENCHMARK TABLE: endpoint, SOTA benchmark value, 95%CI if available, source study (PMID), acceptance criterion for Bubble Study System

§3.9 STATE OF THE ART CONCLUSIONS (3-5 pages)
- Summary of current SOTA for RLS/PFO detection
- Gaps in current clinical practice (manual variability, operator dependency, standardization challenges)
- How the Bubble Study System addresses these gaps (automated preparation, standardized protocol, reduced variability)
- Clinical need justification for an automated bubble study system
- Reference to clinical evaluation endpoints defined in §3.8

Write 15000+ words total. Include at LEAST 8 detailed tables with citations. Every numerical value MUST cite the source PMID or author-year."""

ch5_prompt = f"""Write §5 CLINICAL EVIDENCE APPRAISAL (50-70 pages of SUBSTANTIVE per-article analysis).

{DC}
Evidence Registry: {EV}
Clinical Facts: {FT}
Endpoint Full-Text Data: {EN}
Evidence Hierarchy: {SH_T}
Clinical Source Records: {CS_T}
Synthesis Narratives: {SN_T}

§5.1 EVIDENCE OVERVIEW AND CATEGORIZATION (5-8 pages)
- Total evidence base: {len(AP)} records identified, categorized by:
  * Study design: systematic reviews/meta-analyses (n=?), randomized controlled trials (n=?), prospective cohort studies (n=?), retrospective cohort studies (n=?), case-control studies (n=?), case series (n=?), clinical practice guidelines (n=?), expert consensus (n=?)
  * Evidence level (Oxford CEBM): Level 1a/1b/2a/2b/3a/3b/4/5 with counts
  * Quality appraisal: high quality (score ≥70%, n=?), moderate quality (score 50-70%, n=?), low quality (score 30-50%, n=?), very low quality (score <30%, n=?)
  * Relevance: directly relevant to Bubble Study System (n=?), indirectly relevant (n=?), background only (n=?)
- Evidence pyramid visualization (text-based)
- Evidence weight distribution: pivotal (n=?), supportive (n=?), background (n=?)
- Evidence sufficiency assessment for each of the {len(vals.get('claim_ledger',[]))} claims

§5.2 PIVOTAL CLINICAL EVIDENCE — OWN CLINICAL INVESTIGATION (15-25 pages)
- E-004: Prospective, Multi-center, Cross-over Controlled Clinical Trial of the Bubble Study System
- FULL DETAILED PRESENTATION:
  * Study identification: Protocol No. WYTD-YY-A03, Version 1.1, Date, Registration No. (if applicable)
  * Study design: prospective, multi-center (3 centers), cross-over design (automated vs manual, within-subject comparison), single-arm with each subject serving as own control
  * Study objectives: Primary — demonstrate non-inferiority of Bubble Study System automated agitated saline RLS detection concordance vs manual method (target ≥80%). Secondary — sensitivity, specificity, semi-quantitative shunt grading agreement, Valsalva maneuver completion rate, procedure time, adverse events
  * Sample size justification: 180 subjects, power calculation (α=0.05 two-sided, β=0.20, non-inferiority margin 10%, expected concordance 85%), accounting for 10% dropout
  * Study centers: Fuwai Hospital (Beijing), Xiangyang Central Hospital (Hubei), Hebei Medical University First Hospital (Shijiazhuang)
  * Inclusion criteria (FULL list): age 18-75, clinically suspected RLS/PFO, able to complete c-TTE and/or c-TCD, able to perform Valsalva maneuver, informed consent
  * Exclusion criteria (FULL list): severe cardiac/hepatic/renal/pulmonary impairment, malignant tumors, hematological/autoimmune diseases, carotid artery stenosis, congenital VA dysplasia, absent temporal window, pregnancy/lactation, consciousness/cognitive disorders, atherosclerotic stroke, severe multi-organ failure, intellectual disability, epilepsy, psychiatric disorders, 3-month participation in other trials
  * DEMOGRAPHICS TABLE: characteristic, automated-first group (n=XX), manual-first group (n=XX), total (N=180), p-value
  * PRIMARY ENDPOINT RESULTS TABLE: detection method, concordant pairs (n), discordant pairs (n), concordance rate (%), 95%CI, non-inferiority p-value
  * SECONDARY ENDPOINTS TABLE: endpoint, automated method result, manual method result, difference/ratio, 95%CI, p-value — for sensitivity, specificity, PPV, NPV, grading agreement (Cohen's κ), Valsalva completion rate, procedure time (mean±SD, minutes), procedure completion rate
  * ADVERSE EVENTS TABLE: MedDRA SOC, PT, automated method (n, %), manual method (n, %), severity (mild/moderate/severe), causality (definite/probable/possible/unlikely/unrelated), SAE (yes/no)
  * DEVICE DEFICIENCIES TABLE: deficiency type, count, impact on procedure, corrective action
  * SUBJECT DISPOSITION FLOWCHART: screened → enrolled → randomized → completed → analyzed
  * Statistical methods: paired analysis for crossover design, McNemar's test for concordance, Cohen's κ for agreement, Wilson score method for CIs, pre-specified non-inferiority margin
  * Strengths: prospective design, multi-center, within-subject crossover controls for confounders, adequate power, standardized protocol
  * Limitations: single-arm (no parallel comparator group), unblinded (impossible to blind automated vs manual), Chinese population only (generalizability), pre-market clinical investigation (limited real-world evidence)
  * Quality appraisal: level of evidence 2b (individual crossover RCT), quality score [from appraisal], risk of bias assessment (Cochrane RoB 2 domains)

§5.3 SYSTEMATIC REVIEWS AND META-ANALYSES (10-15 pages)
For EACH systematic review/meta-analysis in the evidence hierarchy, provide the same detailed appraisal format:
  * Full citation, PMID, study design per AMSTAR-2, research question, databases searched, date range, number of included studies, total N, key findings (pooled estimates with 95%CI and I² heterogeneity), AMSTAR-2 quality rating (high/moderate/low/critically low), relevance to Bubble Study System, strengths and limitations

§5.4 CLINICAL PRACTICE GUIDELINES AND CONSENSUS STATEMENTS (5-8 pages)
For each guideline: society, year, key recommendations relevant to bubble study/PFO/RLS, class of recommendation, level of evidence, AGREE II quality assessment, impact on CER conclusions

§5.5 OBSERVATIONAL STUDIES AND CLINICAL REGISTRIES (8-12 pages)
For each observational study: full citation, study design per Newcastle-Ottawa Scale, population (N, demographics), key results with quantitative data, NOS quality score (selection/comparability/exposure or outcome), relevance

§5.6 SIMILAR BENCHMARK DEVICE EVALUATIONS (5-8 pages)
Published evaluations of automated/semi-automated agitated saline devices, comparison to Bubble Study System

§5.7 EXCLUDED EVIDENCE WITH RATIONALE (3-5 pages)
Key excluded articles (from PRISMA flow): article citation, exclusion reason (detailed, not just generic), why data could not be used

§5.8 CLINICAL DATA SUMMARY TABLE (COMPREHENSIVE) (5-8 pages)
Master evidence table: article, PMID, study design, evidence level, N, population, key findings (quantitative), quality score, relevance, contribution to which claim(s)

§5.9 ADVERSE EVENTS ACROSS STUDIES (3-5 pages)
Pooled safety analysis: AE type, incidence across studies, comparison to SOTA benchmarks

§5.10 OVERALL CLINICAL EVIDENCE CONCLUSION (3-5 pages)
- Evidence sufficiency per claim
- Overall evidence quality assessment
- Evidence gaps identified
- How PMCF addresses residual uncertainties

Write 20000+ words. For EACH article: FULL citation, PMID, study design, sample size, KEY QUANTITATIVE RESULTS extracted from full-text (NOT abstract-only), quality appraisal with tool and score, relevance analysis. Include at LEAST 15 detailed tables."""

# ── Generate ──
results = {}
for ch_id, prompt, label in [
    ("§3_sota_expanded", ch3_prompt, "§3 STATE OF THE ART (target 35-50p)"),
    ("§5_evidence_expanded", ch5_prompt, "§5 EVIDENCE APPRAISAL (target 50-70p)"),
]:
    ch_path = os.path.join(OUT, "chapters_r2", f"{ch_id}.md")
    print(f"\n[{label}] Prompt: {len(prompt)} chars → deepseek-v4-pro (32K)...", flush=True)
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
        print(f"  → {chars:,} chars | {len(text.split()):,} words | ~{chars//3500} pages", flush=True)
    except Exception as e:
        print(f"  → ERROR: {e}", flush=True)
        results[ch_id] = f"[ERROR: {e}]"

# Assemble with existing chapters
print("\nAssembling complete CER from R2 + expanded key chapters...", flush=True)
r2_dir = os.path.join(OUT, "chapters_r2")

# Read R2 chapters
r2_chapters = {}
for ch in ["§1_exsum","§2_device","§4_search","§6_due","§7_br","§8_end"]:
    path = os.path.join(r2_dir, f"{ch}.md")
    if os.path.exists(path):
        with open(path) as f:
            r2_chapters[ch] = f.read()

# Build final CER
HDR = f"""# Clinical Evaluation Report
## Bubble Study System (BS-2) with Disposable Contrast Injection Tubing Set (DCS-3030/3030B/5030/5030B)

**Manufacturer:** WYTD MEDICAL TECHNOLOGY (SHENZHEN) CO., LTD.
**CER Number:** CER-BUB-2026-001 | **Version:** 2.0 | **Date:** 2026-06-01
**MDR Classification:** Class IIb (Annex VIII Rule 10 + Rule 12)
**Regulatory Basis:** MDR 2017/745 Article 61, Annex XIV Part A; MDCG 2020-5; MEDDEV 2.7/1 Rev.4
**Clinical Domain:** Right-to-Left Shunt / Patent Foramen Ovale Detection

---

## Table of Contents
1. Executive Summary
2. Device Description and Scope
3. State of the Art
4. Literature Search Methodology
5. Clinical Evidence Appraisal
6. Clinical Data from Device Under Evaluation
7. Benefit-Risk Analysis
8. Conclusions
9. PMCF and Next Evaluation
10. Qualification of Evaluators
11. Declaration of Interest
12. Dates and Signatures
Annexes (separate volume)
---

"""

order = [
    ("§1_exsum", "§1 EXECUTIVE SUMMARY"),
    ("§2_device", "§2 DEVICE DESCRIPTION AND SCOPE"),
    ("§3_sota_expanded", "§3 STATE OF THE ART"),
    ("§4_search", "§4 LITERATURE SEARCH METHODOLOGY"),
    ("§5_evidence_expanded", "§5 CLINICAL EVIDENCE APPRAISAL"),
    ("§6_due", "§6 CLINICAL DATA FROM DEVICE UNDER EVALUATION"),
    ("§7_br", "§7 BENEFIT-RISK ANALYSIS"),
    ("§8_end", "§8-12 CONCLUSIONS, PMCF, AND ADMINISTRATIVE SECTIONS"),
]

full = HDR
for ch_id, heading in order:
    content = results.get(ch_id) or r2_chapters.get(ch_id, "")
    if content:
        full += f"\n\n## {heading}\n\n{content}\n\n"

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

# Show chapter breakdown
print("\n=== Chapter Breakdown ===")
for ch_id, heading in order:
    content = results.get(ch_id) or r2_chapters.get(ch_id, "")
    if content:
        c = len(content)
        p = c // 3500
        print(f"  {heading}: {c:,} chars (~{p} pages)")
print("DONE", flush=True)
