"""
Phase C Step 8 — STRONG Baseline Automation
Post-run hook: after DeerFlow review completes, auto-extract findings,
run deterministic entailment crosswalk vs NB observations, write strong_baseline.json.
No LLM calls — keyword-overlap entailment with regulatory category matching.
"""

import json, os, re, sys
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from typing import Dict, List, Any, Optional, Tuple


# ============================================================
# FINDING EXTRACTION
# ============================================================

def extract_findings(run_dir: Path) -> List[dict]:
    """Extract AI review findings from run directory artifacts."""
    findings = []

    # Look for review output files
    review_files = []
    for pattern in ["review_package.json", "review_report.json", "candidate_findings.json",
                    "findings.json", "review_output.json"]:
        for f in run_dir.rglob(pattern):
            if f.is_file():
                review_files.append(f)

    for fpath in review_files:
        try:
            data = json.loads(fpath.read_text(encoding="utf-8", errors="ignore"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue

        # Extract findings from various known structures
        candidates = (
            data.get("findings", []) or
            data.get("candidate_findings", []) or
            data.get("results", []) or
            data.get("gaps", []) or
            data.get("issues", []) or
            []
        )

        # Also check if the data is a list directly
        if isinstance(data, list):
            candidates = data

        for item in candidates:
            if isinstance(item, dict):
                text = (item.get("finding", "") or item.get("description", "")
                        or item.get("text", "") or item.get("content", "")
                        or item.get("gap_description", "") or item.get("concern", ""))
                severity = (item.get("severity", "") or item.get("risk_level", "")
                           or item.get("priority", "") or item.get("impact", ""))
                category = (item.get("category", "") or item.get("type", "")
                           or item.get("classification", ""))
                finding_id = (item.get("id", "") or item.get("finding_id", "")
                             or item.get("gap_id", ""))
                if text and len(str(text)) > 30:
                    findings.append({
                        "finding_id": str(finding_id),
                        "text": str(text)[:1000],
                        "severity": str(severity),
                        "category": str(category),
                        "source_file": str(fpath.name),
                    })

    # ── V28.4: CEP panel_summary extraction ──
    # CEP sub-agents produce structured panel_summary with sub_assessments
    # rather than discrete findings.  Extract assessment metadata as
    # lightweight findings for crosswalk matching.
    for panel_file in run_dir.rglob("panel_summary.json"):
        try:
            data = json.loads(panel_file.read_text(encoding="utf-8", errors="ignore"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue

        # Extract from sub_assessments
        sub = data.get("sub_assessments", {})
        for sa_name, sa in sub.items():
            if not isinstance(sa, dict):
                continue
            hg = sa.get("human_gate_required", False)
            status = sa.get("status", "")
            anchor = sa.get("regulatory_anchor", "")
            dim = sa.get("dimension", "")

            # Build finding text from structured assessment
            text_parts = [f"CEP {sa_name} assessment"]
            if status:
                text_parts.append(f"status: {status}")
            if hg:
                text_parts.append(f"human gate required: {sa.get('human_gate_ref', '')}")
            if anchor:
                text_parts.append(f"regulatory: {anchor}")

            findings.append({
                "finding_id": f"CEP-{sa.get('sub_assessment_id', sa_name)}",
                "text": ". ".join(text_parts),
                "severity": "HIGH" if hg else "MEDIUM",
                "category": f"CEP_{sa_name}",
                "source_file": str(panel_file.name),
            })

        # Also check top-level findings (rarely populated but check anyway)
        top_findings = data.get("findings", [])
        if isinstance(top_findings, list):
            for item in top_findings:
                if isinstance(item, dict):
                    text = (item.get("finding", "") or item.get("description", "")
                            or item.get("text", "") or "")
                    if text and len(str(text)) > 30:
                        findings.append({
                            "finding_id": str(item.get("finding_id", item.get("id", ""))),
                            "text": str(text)[:1000],
                            "severity": str(item.get("severity", "MEDIUM")),
                            "category": "CEP",
                            "source_file": str(panel_file.name),
                        })

    # ── V28.4: CEP sub-report extraction ──
    # Individual sub-reports (benefit_risk_report.json, sota_literature_report.json,
    # etc.) may contain discrete gap descriptions
    for report_pattern in ["benefit_risk_report.json", "sota_literature_report.json",
                           "evidence_adequacy_report.json", "equivalence_report.json",
                           "pms_pmcf_report.json"]:
        for report_file in run_dir.rglob(report_pattern):
            try:
                data = json.loads(report_file.read_text(encoding="utf-8", errors="ignore"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue

            # Check for gap_list, findings, gaps
            for key in ["gap_list", "findings", "gaps", "identified_gaps", "inconsistencies"]:
                items = data.get(key, [])
                if isinstance(items, list):
                    for item in items:
                        if isinstance(item, dict):
                            text = (item.get("description", "") or item.get("gap_description", "")
                                    or item.get("finding", "") or item.get("text", ""))
                            if text and len(str(text)) > 30:
                                findings.append({
                                    "finding_id": str(item.get("gap_id", item.get("id", ""))),
                                    "text": str(text)[:1000],
                                    "severity": str(item.get("severity", "MEDIUM")),
                                    "category": f"CEP_{report_pattern.replace('.json','')}",
                                    "source_file": str(report_file.name),
                                })

            # Check for raw assessment dict (common in scaffold stubs)
            for assess_key in ["assessment", "overall_assessment", "conclusion"]:
                val = data.get(assess_key, "")
                if isinstance(val, str) and len(val) > 30:
                    findings.append({
                        "finding_id": f"CEP-{report_pattern.replace('.json','')}-{assess_key}",
                        "text": f"CEP {report_pattern.replace('.json','')}: {val[:800]}",
                        "severity": "MEDIUM",
                        "category": f"CEP_{report_pattern.replace('.json','')}",
                        "source_file": str(report_file.name),
                    })
                    break  # One assessment per report

    return findings


# ============================================================
# NB OBSERVATION LOADING
# ============================================================

def load_nb_observations(project_id: str) -> List[dict]:
    """Load NB observations for a project."""
    # Extract numeric project ID
    match = re.search(r'PROJECT_(\d+)', project_id)
    if not match:
        return []
    pid = match.group(1)

    # Look in standard locations
    search_paths = [
        Path.home() / f"CER-RAG/00_knowledge_extraction_build/round2_autonomous_loop/10_reports/{pid}_nb_observations.json",
        Path.home() / f"CER-RAG/00_knowledge_extraction_build/round2_autonomous_loop/10_reports/{pid}_crosswalk_matrix.json",
    ]

    for sp in search_paths:
        if sp.exists():
            try:
                data = json.loads(sp.read_text(encoding="utf-8", errors="ignore"))
                if "crosswalk_matrix.json" in str(sp):
                    # Extract NB observations from crosswalk details
                    return [
                        {"nb_id": d.get("nb_id", ""), "text": d.get("nb_question", ""),
                         "category": d.get("nb_category", ""), "round": d.get("nb_round", "")}
                        for d in data.get("details", [])
                    ]
                else:
                    # Direct NB observations
                    obs = data.get("observations", [])
                    return [
                        {"nb_id": o.get("obs_id", o.get("nb_id", o.get("id", ""))),
                         "text": o.get("nb_question", o.get("text", o.get("question", ""))),
                         "category": o.get("category", ""), "round": o.get("round", "")}
                        for o in obs
                    ]
            except Exception:
                pass

    return []


# ============================================================
# V28.3: BILINGUAL KEYWORD LAYER — Chinese → English term mapping
# ============================================================

# Chinese regulatory/manufacturing keywords mapped to English equivalents.
# Each Chinese term (1-4 chars) maps to an English keyword used in the
# regulatory keyword bonus set below.  This bridges the language gap for
# projects where NB observations are in Chinese but AI findings are in English.
_CN_KEYWORD_MAP: Dict[str, str] = {
    # ── Process Validation (ISO 13485 §7.5.2) ──
    "过程验证": "process_validation",
    "工序验证": "process_validation",
    "关键工序": "critical_process",
    "特殊过程": "special_process",
    "过程确认": "process_validation",
    "焊接": "welding",
    "粘接": "bonding",
    "封口": "sealing",
    "挤出": "extrusion",
    "精洗": "cleaning",
    "烘干": "drying",
    "解析": "desorption",
    # ── Sterilization ──
    "灭菌验证": "sterilization_validation",
    "灭菌": "sterilization",
    "环氧乙烷": "eo_sterilization",
    "环残": "residual",
    "生物指示剂": "biological_indicator",
    "辐照": "irradiation",
    # ── Cleanroom / Environment ──
    "洁净车间": "cleanroom",
    "洁净实验室": "cleanroom",
    "洁净": "cleanroom",
    "生产车间": "production_facility",
    # ── Design Control (ISO 13485 §7.3) ──
    "设计输入": "design_input",
    "设计输出": "design_output",
    "设计验证": "design_verification",
    "设计确认": "design_validation",
    "设计开发": "design_development",
    "设计追溯": "design_traceability",
    "追溯矩阵": "traceability_matrix",
    "追溯": "traceability",
    # ── Documents / Records ──
    "技术文件": "technical_documentation",
    "文件清单": "document_list",
    "文件编码": "document_coding",
    "已提供英文版": "english_provided",
    "英文版": "english_version",
    "已提供": "provided",
    # ── Aging / Packaging ──
    "加速老化": "accelerated_aging",
    "老化": "aging",
    "包装验证": "packaging_validation",
    "包装": "packaging",
    "封口验证": "seal_validation",
    # ── Standards (exact matches) ──
    "13485": "iso_13485",
    "11607": "iso_11607",
    "11135": "iso_11135",
    "11137": "iso_11137",
    "10993": "iso_10993",
    "14971": "iso_14971",
    "62304": "iec_62304",
    "60601": "iec_60601",
    "f1980": "astm_f1980",
    # ── Labels / IFU ──
    "标签": "label",
    "说明书": "ifu",
    "国内标签": "domestic_label",
    # ── Purchasing / Supply Chain ──
    "采购清单": "purchasing_list",
    "采购": "purchasing",
    "物料名称": "material_name",
    "物料": "material",
    "供应商": "supplier",
    # ── General Regulatory ──
    "典型性": "typicality",
    "型检报告": "type_test_report",
    "型检": "type_test",
    "证书": "certificate",
    "测试": "test",
    "检验": "inspection",
    "报告": "report",
    "翻译件": "translation",
    "整改": "corrective_action",
    "莱茵": "tuv",  # TÜV Rheinland
    # ── Product-specific ──
    "泵管": "pump_tube",
    "营养泵": "feeding_pump",
    "胃管": "stomach_tube",
    "手套": "glove",
    "导管": "catheter",
}


def _extract_cn_keywords(text: str) -> set[str]:
    """Scan Chinese NB text for known regulatory keywords, return mapped English terms.

    Chinese text has no spaces between words, so we use substring matching
    against the CN_KEYWORD_MAP dictionary (longest match first to avoid
    partial matches like "灭菌" capturing inside "灭菌验证").
    """
    if not text:
        return set()

    text_lower = text.lower()
    found: set[str] = set()

    # Sort by key length descending so longer phrases match first
    for cn_term in sorted(_CN_KEYWORD_MAP, key=len, reverse=True):
        if cn_term.lower() in text_lower:
            found.add(_CN_KEYWORD_MAP[cn_term])

    # Also extract any standalone ISO/ASTM numbers and English acronyms
    # that may appear inside Chinese text
    for m in re.findall(r'\b(?:ISO|IEC|EN|ASTM|MDR|GSPR|IFU|CER|PMS|PMCF|QMS|PRRC|UDI|DHF|CAPA|NB|NCR)\b',
                        text, re.IGNORECASE):
        found.add(m.lower())

    for m in re.findall(r'\b\d{4,6}\b', text):
        found.add(f"std_{m}")

    return found


# ============================================================
# ENTAILMENT CROSSWALK (deterministic keyword-overlap)
# ============================================================

def compute_overlap_score(finding: dict, nb_obs: dict) -> Tuple[float, List[str]]:
    """Compute keyword overlap score between finding and NB observation.

    V28.3: Bilingual support — Chinese NB text is mapped to English
    regulatory keywords via _CN_KEYWORD_MAP before overlap computation.
    """
    finding_raw = str(finding.get("text", "")).lower()
    nb_raw = str(nb_obs.get("text", "")).lower()

    # ── English keyword extraction (unchanged) ──
    finding_text = set(re.findall(r'\w+', finding_raw))
    nb_text = set(re.findall(r'\w+', nb_raw))

    # ── V28.3: Chinese keyword injection ──
    # If NB text has Chinese characters, extract mapped English keywords
    # and add them to the nb_text set.  Underscored compounds like
    # "process_validation" are split so they can overlap with the
    # space-separated tokens from the English finding text.
    has_cjk = bool(re.search(r'[一-鿿]', nb_raw))
    if has_cjk:
        cn_terms = _extract_cn_keywords(nb_raw)
        for t in cn_terms:
            for part in t.split('_'):
                nb_text.add(part)  # inject each component word

    if not finding_text or not nb_text:
        return 0.0, []

    # Remove stopwords
    stopwords = {"the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
                 "have", "has", "had", "do", "does", "did", "will", "would", "shall",
                 "should", "may", "might", "can", "could", "to", "of", "in", "for",
                 "on", "with", "at", "by", "from", "as", "or", "and", "not", "no",
                 "this", "that", "these", "those", "it", "its", "please", "provide",
                 "the", "and", "that", "have", "for", "not", "with", "you", "this",
                 "but", "his", "from", "they", "say", "her", "she", "will", "one",
                 "all", "would", "there", "their", "what", "out", "about", "who",
                 "get", "which", "when", "make", "can", "like", "just", "into",
                 "than", "then", "also", "very", "been", "being", "does", "each",
                 "some", "such", "other", "only", "over", "more", "after", "our"}
    finding_terms = finding_text - stopwords
    nb_terms = nb_text - stopwords

    if not finding_terms or not nb_terms:
        return 0.0, []

    overlap = finding_terms & nb_terms
    jaccard = len(overlap) / len(finding_terms | nb_terms) if (finding_terms | nb_terms) else 0

    # ── V28.3: Bilingual direct-match bonus ──
    # When NB text is Chinese (has_cjk=True), the Jaccard similarity against
    # English finding text is structurally low even after CN→EN keyword
    # injection (3 mapped keywords in a 50+ term set → ~0.06 Jaccard).
    # Instead, count how many CN→EN mapped keywords appear directly in the
    # finding text and award a tiered bilingual bonus.  This reflects the
    # semantic strength of cross-lingual regulatory-term matching.
    bilingual_bonus = 0.0
    if has_cjk:
        cn_terms_set = _extract_cn_keywords(nb_raw)
        finding_text_str = str(finding.get("text", "")).lower()
        # Count CN→EN keyword hits.  Underscored compounds like
        # "process_validation" are split into components ["process","validation"];
        # ALL components must appear in the finding text for a hit.
        cn_hits = 0
        for t in cn_terms_set:
            parts = t.split('_')
            if all(p in finding_text_str for p in parts):
                cn_hits += 1
        if cn_hits >= 4:
            bilingual_bonus = 0.35
        elif cn_hits >= 3:
            bilingual_bonus = 0.25
        elif cn_hits >= 2:
            bilingual_bonus = 0.18
        elif cn_hits >= 1:
            bilingual_bonus = 0.10

    # Bonus for regulatory keywords (V28.3: expanded with CN→EN mapped terms)
    reg_keywords = {"clinical", "risk", "biocompat", "steril", "label", "ifu", "pmcf",
                    "software", "cyber", "standard", "iso", "iec", "mdr", "safety",
                    "performance", "benefit", "evidence", "trial", "study", "validation",
                    "verification", "design", "manufacturing", "process", "material",
                    "test", "report", "document", "gaps", "cer", "pms", "usability",
                    # V28.3: CN→EN mapped terms for bilingual matching
                    "sterilization", "cleanroom", "packaging", "traceability",
                    "purchasing", "certificate", "welding", "bonding", "sealing",
                    "extrusion", "aging", "accelerated_aging", "eo_sterilization",
                    "irradiation", "desorption", "supplier", "inspection",
                    "corrective_action", "type_test", "typicality",
                    "iso_13485", "iso_11607", "iso_11135", "iso_11137",
                    "iso_10993", "iso_14971", "iec_62304", "iec_60601",
                    "astm_f1980", "design_input", "design_output",
                    "design_verification", "design_validation",
                    "process_validation", "critical_process", "special_process",
                    "packaging_validation", "seal_validation",
                    "traceability_matrix", "design_development",
                    "technical_documentation", "english_version",
                    "domestic_label", "purchasing_list", "material_name",
                    "pump_tube", "feeding_pump", "stomach_tube",
                    "catheter", "glove", "biological_indicator",
                    "production_facility", "document_coding", "document_list",
                    "translation", "tuv", "cleaning", "drying",
                    }
    reg_overlap = overlap & reg_keywords

    # Category bonus
    cat_bonus = 0.0
    if finding.get("category") and nb_obs.get("category"):
        if finding["category"].lower() == nb_obs["category"].lower():
            cat_bonus = 0.15

    score = jaccard * 0.5 + (len(reg_overlap) / max(len(overlap), 1)) * 0.35 + cat_bonus + bilingual_bonus
    return min(1.0, score), list(overlap)


def classify_match(score: float, overlap_count: int = 0) -> str:
    """Classify match quality from composite score.

    V28.3: Simplified to score-only thresholds.  The composite score already
    incorporates Jaccard, regulatory keyword bonus, category bonus, and
    bilingual keyword bonus — overlap_count is redundant and penalises
    cross-lingual matches where text overlap is structurally zero.
    """
    if score >= 0.50:
        return "STRONG"
    elif score >= 0.30:
        return "MODERATE"
    elif score >= 0.15:
        return "WEAK"
    else:
        return "NO_MATCH"


# ============================================================
# MAIN CROSSWALK
# ============================================================

def run_crosswalk(findings: List[dict], nb_observations: List[dict]) -> Dict[str, Any]:
    """Run full crosswalk analysis between AI findings and NB observations."""
    if not findings or not nb_observations:
        return {
            "total_findings": len(findings),
            "total_nb_observations": len(nb_observations),
            "match_distribution": {"STRONG": 0, "MODERATE": 0, "WEAK": 0, "NO_MATCH": 0},
            "strong_rate": 0.0,
            "error": "Insufficient data for crosswalk" if not nb_observations else "No findings to crosswalk",
            "details": [],
        }

    details = []
    match_counts = {"STRONG": 0, "MODERATE": 0, "WEAK": 0, "NO_MATCH": 0}

    for finding in findings:
        best_match = None
        best_score = 0.0
        best_overlap = []

        for nb_obs in nb_observations:
            score, overlap = compute_overlap_score(finding, nb_obs)
            if score > best_score:
                best_score = score
                best_overlap = overlap
                best_match = nb_obs

        quality = classify_match(best_score, len(best_overlap))
        match_counts[quality] += 1

        details.append({
            "finding_id": finding.get("finding_id", ""),
            "finding_text": str(finding.get("text", ""))[:200],
            "finding_category": finding.get("category", ""),
            "best_nb_id": best_match.get("nb_id", "") if best_match else "",
            "best_nb_text": str(best_match.get("text", ""))[:200] if best_match else "",
            "best_nb_category": best_match.get("category", "") if best_match else "",
            "score": round(best_score, 3),
            "overlap_terms": best_overlap[:10],
            "match_quality": quality,
        })

    total = len(findings)
    # Also mark unmatched NB observations
    matched_nb_ids = {d["best_nb_id"] for d in details if d["best_nb_id"]}
    unmatched_nb = [
        {"nb_id": o.get("nb_id", ""), "text": str(o.get("text", ""))[:200]}
        for o in nb_observations if o.get("nb_id", "") not in matched_nb_ids
    ]

    return {
        "total_findings": total,
        "total_nb_observations": len(nb_observations),
        "matched_nb_observations": len(matched_nb_ids),
        "unmatched_nb_observations": len(unmatched_nb),
        "match_distribution": match_counts,
        "strong_rate": round(match_counts["STRONG"] / total, 3) if total > 0 else 0.0,
        "strong_moderate_rate": round((match_counts["STRONG"] + match_counts["MODERATE"]) / total, 3) if total > 0 else 0.0,
        "details": details[:100],  # Cap at 100 for readability
        "unmatched_nb_observations_preview": unmatched_nb[:20],
    }


# ============================================================
# POST-RUN HOOK
# ============================================================

def compute_strong_baseline(run_dir: Path) -> Dict[str, Any]:
    """Main entry point: compute STRONG baseline for a completed review run."""
    status = {}
    status_path = run_dir / "status.json"
    if status_path.exists():
        try:
            status = json.loads(status_path.read_text())
        except json.JSONDecodeError:
            pass

    project_id = status.get("project_id", run_dir.parent.name)

    # Extract findings
    findings = extract_findings(run_dir)

    # Load NB observations
    nb_observations = load_nb_observations(project_id)

    # Run crosswalk
    crosswalk = run_crosswalk(findings, nb_observations)

    # Build report
    report = {
        "schema": "strong_baseline",
        "version": "v1",
        "generated_at": datetime.now().isoformat(),
        "run_dir": str(run_dir),
        "project_id": project_id,
        "review_engine": status.get("review_engine", "unknown"),
        "findings_extracted": len(findings),
        "nb_observations_loaded": len(nb_observations),
        "crosswalk": crosswalk,
        "strong_baseline_score": crosswalk.get("strong_rate", 0.0),
        "interpretation": _interpret_baseline(crosswalk.get("strong_rate", 0.0)),
    }

    # Write to run directory
    output_path = run_dir / "strong_baseline.json"
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2))

    return report


def _interpret_baseline(strong_rate: float) -> str:
    """Interpret the STRONG baseline score."""
    if strong_rate >= 0.50:
        return "EXCELLENT: AI findings strongly align with ≥50% of NB concerns. Review engine demonstrates high clinical-regulatory reasoning."
    elif strong_rate >= 0.30:
        return "GOOD: AI findings show moderate-to-strong alignment with ≥30% of NB concerns. Useful as first-pass screening."
    elif strong_rate >= 0.15:
        return "ADEQUATE: AI findings show some alignment. Suitable as supplementary input; human review required."
    else:
        return "DEVELOPMENT: AI findings show weak alignment with NB concerns. Review engine needs improvement for this device class."


# ============================================================
# CLI
# ============================================================

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 strong_baseline.py <run_dir> [--json]")
        sys.exit(1)

    run_dir = Path(sys.argv[1]).expanduser().resolve()
    if not run_dir.exists():
        print(json.dumps({"error": f"Run directory not found: {run_dir}"}))
        sys.exit(1)

    report = compute_strong_baseline(run_dir)
    output_flag = "--json" in sys.argv
    if output_flag:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        cw = report.get("crosswalk", {})
        dist = cw.get("match_distribution", {})
        print(f"STRONG Baseline: {report['project_id']}")
        print(f"  Findings: {report['findings_extracted']} | NB Obs: {report['nb_observations_loaded']}")
        print(f"  STRONG: {dist.get('STRONG', 0)} | MODERATE: {dist.get('MODERATE', 0)} | WEAK: {dist.get('WEAK', 0)} | NO_MATCH: {dist.get('NO_MATCH', 0)}")
        print(f"  Strong Rate: {report['strong_baseline_score']:.1%}")
        print(f"  Interpretation: {report['interpretation']}")
        print(f"  Output: {run_dir / 'strong_baseline.json'}")
