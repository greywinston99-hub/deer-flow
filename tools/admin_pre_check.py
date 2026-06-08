"""
V23 Admin Pre-Check Layer — Deterministic Python, NOT LLM.
V28 Upgrade — Hybrid mode: regex fast-screening + optional LLM deep review.
Runs BEFORE EC. Checks document completeness: signatures, dates, certificates,
file enumeration, document control, version consistency. Outputs structured JSON.

Regex checks are fast pattern matching (6 dimensions, 30+ patterns).
LLM channel is invoked via --mode llm for files missed or flagged by regex.
LLM uses tools=[] JSON-only mode to read files and produce evidence-anchored findings.
All checks are advisory. No terminal judgments.
"""

import os, re, json, sys
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

# ============================================================
# CHECK 1: SIGNATURE CHECK
# ============================================================

SIGNATURE_PATTERNS = [
    r'(?i)sign(?:ed|ature)[\s:]*[_\-\s]*(?:by)?[\s:]*',
    r'(?i)authori[sz]ed\s+(?:by|signature)[\s:]*',
    r'(?i)approved\s+(?:by|signature)[\s:]*',
    r'(?i)reviewed\s+by[\s:]*',
    r'(?i)drafted\s+by[\s:]*',
    r'签字[：:]\s*',
    r'签名[：:]\s*',
    r'审批[：:]\s*',
    r'/s/\s*',
]

SIGNATURE_PLACEHOLDER_PATTERNS = [
    r'\[sign(?:ature)?\]',
    r'\[sign(?:ed)?\s*by\]',
    r'_{3,}',  # Underline placeholders
    r'\.{3,}', # Dot placeholders
    r'（签字）',
    r'\(sign(?:ature)?\)',
    r'<sign(?:ature)?>',
]

def check_signatures(text: str) -> Dict[str, Any]:
    """Check for signature blocks and placeholder signatures."""
    has_signature_block = False
    matched_patterns = []
    for pattern in SIGNATURE_PATTERNS:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            has_signature_block = True
            matched_patterns.append(matches[0][:80])

    has_placeholder = False
    placeholder_matches = []
    for pattern in SIGNATURE_PLACEHOLDER_PATTERNS:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            has_placeholder = True
            placeholder_matches.append(str(matches[0])[:80])

    if not has_signature_block:
        status = "WARNING"
        detail = "No signature block detected in document."
    elif has_placeholder:
        status = "FAIL"
        detail = f"Placeholder signature found — document may be unsigned draft. Placeholders: {placeholder_matches[:3]}"
    else:
        status = "PASS"
        detail = "Signature block(s) detected, no placeholders found."

    return {
        "check_type": "signature",
        "status": status,
        "has_signature_block": has_signature_block,
        "has_placeholder": has_placeholder,
        "signature_block_count": len(matched_patterns),
        "detail": detail,
    }


# ============================================================
# CHECK 2: DATE CHECK
# ============================================================

DATE_PATTERNS = [
    (r'(\d{4})[-/](\d{1,2})[-/](\d{1,2})', 'ISO'),           # 2024-01-15
    (r'(\d{1,2})[-/](\d{1,2})[-/](\d{4})', 'US'),            # 01/15/2024
    (r'(\d{4})年(\d{1,2})月(\d{1,2})日', 'Chinese'),          # 2024年1月15日
    (r'(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+(\d{4})', 'EU'),  # 15 Jan 2024
    (r'(?:effective|issue|approval|revision)\s*(?:date)?[:\s]*(\d{4}[-/]\d{1,2}[-/]\d{1,2})', 'Labelled'),
]

def parse_date(date_str: str, fmt: str, groups: tuple) -> Optional[datetime]:
    """Parse a date from regex groups."""
    try:
        if fmt == 'ISO':
            return datetime(int(groups[0]), int(groups[1]), int(groups[2]))
        elif fmt == 'US':
            return datetime(int(groups[2]), int(groups[0]), int(groups[1]))
        elif fmt == 'Chinese':
            return datetime(int(groups[0]), int(groups[1]), int(groups[2]))
        elif fmt == 'EU':
            months = {'jan':1,'feb':2,'mar':3,'apr':4,'may':5,'jun':6,
                      'jul':7,'aug':8,'sep':9,'oct':10,'nov':11,'dec':12}
            month = months.get(groups[1].lower()[:3], 1)
            return datetime(int(groups[2]), month, int(groups[0]))
        elif fmt == 'Labelled':
            parts = groups[0].split('-') if '-' in groups[0] else groups[0].split('/')
            return datetime(int(parts[0]), int(parts[1]), int(parts[2]))
    except (ValueError, IndexError):
        return None
    return None

def check_dates(text: str) -> Dict[str, Any]:
    """Extract dates and check for staleness, missing dates, future dates."""
    found_dates = []
    staleness_flags = []
    missing_flags = []
    future_flags = []

    now = datetime.now()
    three_years_ago = now - timedelta(days=3*365)

    for pattern, fmt in DATE_PATTERNS:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            dt = parse_date(match.group(0), fmt, match.groups())
            if dt:
                found_dates.append(dt.isoformat()[:10])
                if dt < three_years_ago:
                    staleness_flags.append(f"Date {dt.isoformat()[:10]} is >3 years old")
                if dt > now:
                    future_flags.append(f"Date {dt.isoformat()[:10]} is in the future")

    # Check for document date specifically
    has_document_date = any(
        re.search(p, text, re.IGNORECASE)
        for p in [r'(?:effective|issue|document)\s*date', r'生效日期', r'文件日期']
    )
    if not has_document_date and not found_dates:
        missing_flags.append("No document date detected")

    if not found_dates:
        status = "WARNING"
        detail = "No dates detected in document."
    elif staleness_flags or future_flags:
        status = "WARNING"
        detail = "; ".join(staleness_flags + future_flags)
    elif missing_flags:
        status = "WARNING"
        detail = "; ".join(missing_flags)
    else:
        status = "PASS"
        detail = f"{len(found_dates)} date(s) found, all recent."

    return {
        "check_type": "date",
        "status": status,
        "dates_found": len(found_dates),
        "oldest_date": min(found_dates) if found_dates else None,
        "staleness_flags": staleness_flags,
        "future_flags": future_flags,
        "detail": detail,
    }


# ============================================================
# CHECK 3: CERTIFICATE CHECK
# ============================================================

CERT_PATTERNS = {
    'ISO_13485': [r'(?:EN\s*)?ISO\s*13485[:/\s]*\d*', r'ISO13485'],
    'CE_Certificate': [r'CE\s*(?:certif|mark|MDD|MDR)', r'CE\s*\d{4,}'],
    'MDR_Certificate': [r'(?:EU\s*)?MDR\s*(?:2017/745|certif)', r'MDR\s*certificate'],
    'FDA_Clearance': [r'FDA\s*(?:510\s*\(?\s*k\s*\)?|clear\w+|approv\w+)'],
    'NMPA_Registration': [r'NMPA|CFDA|国械注', r'注册证编号'],
    'ISO_9001': [r'ISO\s*9001'],
}

CERT_EXPIRY_PATTERNS = [
    r'(?:expir\w*|valid\s+until|expiry)\s*(?:date)?[:\s]*(\d{4}[-/]\d{1,2}[-/]\d{1,2})',
    r'有效期[至到][：:\s]*(\d{4}[-/年]\d{1,2}[-/月]\d{1,2})',
]

def check_certificates(text: str) -> Dict[str, Any]:
    """Detect certificate references and check for expiration information."""
    certs_found = {}
    for cert_name, patterns in CERT_PATTERNS.items():
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                certs_found[cert_name] = len(matches)

    expiry_matches = []
    for pattern in CERT_EXPIRY_PATTERNS:
        matches = re.findall(pattern, text, re.IGNORECASE)
        expiry_matches.extend(matches)

    now = datetime.now()
    expired_certs = []
    for exp_str in expiry_matches:
        try:
            parts = re.split(r'[-/年月]', exp_str)
            if len(parts) >= 3:
                dt = datetime(int(parts[0]), int(parts[1]), int(parts[2]))
                if dt < now:
                    expired_certs.append(exp_str)
        except (ValueError, IndexError):
            pass

    if not certs_found:
        status = "WARNING"
        detail = "No regulatory certificates detected in document."
    elif expired_certs:
        status = "FAIL"
        detail = f"Expired certificate(s) found: {expired_certs}"
    elif not expiry_matches:
        status = "WARNING"
        detail = f"{len(certs_found)} certificate type(s) found but no expiration dates detected."
    else:
        status = "PASS"
        detail = f"{len(certs_found)} certificate type(s) found with expiration dates."

    return {
        "check_type": "certificate",
        "status": status,
        "certificates_detected": certs_found,
        "expired_certificates": expired_certs,
        "detail": detail,
    }


# ============================================================
# CHECK 4: FILE ENUMERATION
# ============================================================

FILE_REFERENCE_PATTERNS = [
    r'(?:see|refer\s+to|see\s+also|cf\.?|参照|参见|详见|见)\s+(?:file|document|appendix|annex|section|附件|附录|文件|章节)?\s*[:\s]*([A-Za-z0-9_\-一-鿿]+\.(?:pdf|docx?|xlsx?|txt))',
    r'(?:Appendix|Annex|附件|附录)\s+([A-Z0-9][A-Za-z0-9_\-\s]*)',
    r'(?:file|document)\s*(?:number|no\.?|#)?[:\s]*([A-Z0-9][A-Za-z0-9_\-]+)',
]

def check_file_enumeration(text: str, source_files: List[str]) -> Dict[str, Any]:
    """Check files referenced in document against files actually present."""
    referenced_files = set()
    for pattern in FILE_REFERENCE_PATTERNS:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            ref = match.group(1).strip() if match.lastindex else match.group(0)
            if len(ref) > 3:
                referenced_files.add(ref)

    # Simple matching: check if any part of referenced file name appears in source files
    source_filenames = {os.path.basename(f).lower() for f in source_files}
    missing_files = []
    for ref in referenced_files:
        ref_lower = ref.lower()
        # Check if any source file contains this reference
        found = any(ref_lower in sf or sf in ref_lower for sf in source_filenames)
        if not found:
            missing_files.append(ref)

    if not referenced_files:
        status = "PASS"
        detail = "No cross-file references detected to verify."
    elif missing_files:
        status = "WARNING"
        detail = f"{len(missing_files)}/{len(referenced_files)} referenced files not found in source package."
    else:
        status = "PASS"
        detail = f"All {len(referenced_files)} referenced files found in source package."

    return {
        "check_type": "file_enumeration",
        "status": status,
        "files_referenced": len(referenced_files),
        "missing_files": missing_files[:20],
        "detail": detail,
    }


# ============================================================
# CHECK 5: DOCUMENT CONTROL
# ============================================================

DOC_CONTROL_PATTERNS = {
    'revision': [r'(?:rev(?:ision)?|版本|ver(?:sion)?)[\s.:]*([A-Z0-9][\w.]*)'],
    'approval': [r'(?:approv\w+|authori[sz]\w+|审批|批准)[\s:]*(?:by|人)?[\s:]*'],
    'effective_date': [r'(?:effective|生效|实施)\s*date[:\s]*'],
    'document_id': [r'(?:doc(?:ument)?\s*(?:no|number|id|#)|文件编号)[\s:]*([A-Z0-9][\w\-]+)'],
}

def check_document_control(text: str) -> Dict[str, Any]:
    """Check for document control elements: revision, approval, date, ID."""
    control_found = {}
    missing_controls = []

    for control_name, patterns in DOC_CONTROL_PATTERNS.items():
        found = any(re.search(p, text, re.IGNORECASE) for p in patterns)
        control_found[control_name] = found
        if not found:
            missing_controls.append(control_name)

    score = sum(1 for v in control_found.values() if v)

    if score == 4:
        status = "PASS"
        detail = "All document control elements present (revision, approval, date, ID)."
    elif score >= 2:
        status = "WARNING"
        detail = f"Missing document control elements: {missing_controls}"
    else:
        status = "FAIL"
        detail = f"Critical document control elements missing: {missing_controls}"

    return {
        "check_type": "document_control",
        "status": status,
        "elements_found": control_found,
        "missing_elements": missing_controls,
        "detail": detail,
    }


# ============================================================
# CHECK 6: VERSION CONSISTENCY
# ============================================================

VERSION_PATTERNS = [
    r'(?:ver(?:sion)?|rev(?:ision)?|版)[\s.:]*([A-Za-z0-9][\w.]*)',
    r'V(\d+[.]?\d*)',
    r'Rev(?:ision)?[\s.]*([A-Z0-9][\w.]*)',
]

def check_version_consistency(text: str, source_files: List[str]) -> Dict[str, Any]:
    """Detect multiple versions of the same document in the source package."""
    # Extract document base names (strip version/date suffixes)
    source_basenames = [os.path.basename(f) for f in source_files]

    # Group files by likely base name (ignoring version/date patterns)
    def normalize_name(name: str) -> str:
        """Strip common version/date patterns to find base name."""
        n = re.sub(r'[\s._-]*(?:V|ver|rev|version|revision)[\s._-]*\d+[.\d]*', '', name, flags=re.IGNORECASE)
        n = re.sub(r'[\s._-]*\d{4}[\s._-]*\d{1,2}[\s._-]*\d{1,2}', '', n)
        n = re.sub(r'[\s._-]*\d{8}', '', n)
        n = re.sub(r'[\s._-]*(?:副本|copy|final|draft|旧|old|new|更新|最新)[\s._-]*', '', n, flags=re.IGNORECASE)
        return os.path.splitext(n)[0].strip(' _.-').lower()

    groups = {}
    for fname in source_basenames:
        key = normalize_name(fname)
        if len(key) < 3:
            continue
        groups.setdefault(key, []).append(fname)

    multi_version_docs = {k: v for k, v in groups.items() if len(v) >= 2}

    # Extract versions from document text
    versions_found = []
    for pattern in VERSION_PATTERNS:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            ver = match.group(1) if match.lastindex else match.group(0)
            if ver and len(ver) > 0:
                versions_found.append(ver)

    unique_versions = list(set(versions_found))

    if not multi_version_docs and len(unique_versions) <= 1:
        status = "PASS"
        detail = "No multiple versions detected in source package."
    elif multi_version_docs and len(unique_versions) <= 1:
        status = "WARNING"
        detail = f"Multiple versions of same document found: {list(multi_version_docs.keys())[:5]}. No version identifiers extracted from text."
    elif len(unique_versions) > 1:
        status = "WARNING"
        detail = f"Multiple versions detected: {unique_versions[:5]}. Verify latest version is clearly identified."
    else:
        status = "WARNING"
        detail = f"Multiple document versions present: {list(multi_version_docs.keys())[:5]}."

    return {
        "check_type": "version_consistency",
        "status": status,
        "multi_version_docs": {k: v for k, v in list(multi_version_docs.items())[:10]},
        "versions_found_in_text": unique_versions[:10],
        "detail": detail,
    }


# ============================================================
# MAIN: Run all checks on a file
# ============================================================

def run_admin_pre_check(filepath: str, source_files: Optional[List[str]] = None) -> Dict[str, Any]:
    """Run all 5 administrative pre-checks on a single file."""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            text = f.read(100000)  # First 100K chars
    except Exception as e:
        return {"file": filepath, "error": str(e), "checks": []}

    results = {
        "file": os.path.basename(filepath),
        "filepath": filepath,
        "character_count": len(text),
        "checks": [
            check_signatures(text),
            check_dates(text),
            check_certificates(text),
            check_file_enumeration(text, source_files or []),
            check_document_control(text),
            check_version_consistency(text, source_files or []),
        ]
    }

    # Summary
    results["summary"] = {
        "total_checks": len(results["checks"]),
        "pass": sum(1 for c in results["checks"] if c["status"] == "PASS"),
        "warning": sum(1 for c in results["checks"] if c["status"] == "WARNING"),
        "fail": sum(1 for c in results["checks"] if c["status"] == "FAIL"),
    }

    return results


def run_admin_pre_check_batch(file_dir: str) -> Dict[str, Any]:
    """Run admin pre-check on all text files in a directory."""
    source_files = []
    for root, dirs, files in os.walk(file_dir):
        for fname in files:
            if not fname.startswith('.'):
                source_files.append(os.path.join(root, fname))

    all_results = []
    for fpath in sorted(source_files):
        if not fpath.endswith(('.txt', '.md')):
            continue  # Only process text files (EC output); skip binary source files
        result = run_admin_pre_check(fpath, source_files)
        all_results.append(result)

    # Aggregate summary
    total_pass = sum(1 for r in all_results if r.get("summary", {}).get("fail", 0) == 0)
    total_warn = sum(1 for r in all_results if r.get("summary", {}).get("fail", 0) == 0 and r.get("summary", {}).get("warning", 0) > 0)
    total_fail = sum(1 for r in all_results if r.get("summary", {}).get("fail", 0) > 0)

    return {
        "project_id": os.path.basename(file_dir),
        "total_files_checked": len(all_results),
        "files_pass": total_pass,
        "files_warning": total_warn,
        "files_fail": total_fail,
        "per_file_results": all_results,
        "generated_at": datetime.now().isoformat(),
        "note": "V28 Admin Pre-Check — hybrid regex+LLM. All findings are advisory. Human verification required.",
    }


# ============================================================
# V28 UPGRADE: LLM Deep Review Channel
# ============================================================

LLM_REVIEW_PROMPT_TEMPLATE = """You are a CER document administrative completeness reviewer.
Review the following file for 6 dimensions. Output JSON ONLY — no markdown, no explanation.

FILE: {filename}
CONTENT (first {char_limit} chars):
{content}

DIMENSIONS TO CHECK:
1. DIM-1 Signature Block: Is there a real signed approval or just template boilerplate? Quote evidence.
2. DIM-2 Date Declaration: Are dates effective dates or references? Any stale (>3yr) or future dates? Quote evidence.
3. DIM-3 Certificate Reference: Are referenced certificates traceable (number, body, dates)? Any expired? Quote evidence.
4. DIM-4 File Enumeration: Are referenced files present? Any dangling references? List missing files.
5. DIM-5 Document Control: Document ID, revision, approval, effective date present and consistent? Quote evidence.
6. DIM-6 Version Consistency: Multiple versions? Latest clearly identified? Cross-references correct? Quote evidence.

OUTPUT FORMAT:
{{"findings": [{{"finding_id": "ADMIN-LLM-DIM-X-NNN", "dimension": "DIM-X", "regex_status": "{regex_status}", "llm_finding": "CONFIRMED|OVERRIDE|NEW_FINDING|NO_ISSUE", "severity": "CRITICAL|MAJOR|MINOR|INFO", "description": "...", "evidence_excerpt": "...", "regulatory_anchor": "...", "recommendation": "..."}}], "summary": {{"total_dimensions": 6, "issues_found": N, "critical": N, "major": N, "minor": N}}}}"""


def create_llm_review_task(filepath: str, regex_result: dict, char_limit: int = 8000) -> dict:
    """Create an LLM review task packet for a single file flagged by regex pre-screening.

    This task is consumed by the DeerFlow cer-admin-precheck-reviewer subagent
    (prompts/cer/canonical/cer_admin_precheck_agent.md) which runs with tools=[] in JSON-only mode.
    """
    try:
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read(char_limit)
    except Exception as e:
        return {"file": filepath, "error": str(e)}

    # Build regex status summary
    regex_statuses = []
    for check in regex_result.get("checks", []):
        if check["status"] in ("WARNING", "FAIL"):
            regex_statuses.append(f"{check['check_type']}={check['status']}")

    regex_status_str = "; ".join(regex_statuses) if regex_statuses else "PASS"

    prompt = LLM_REVIEW_PROMPT_TEMPLATE.format(
        filename=os.path.basename(filepath),
        char_limit=char_limit,
        content=content,
        regex_status=regex_status_str,
    )

    return {
        "task_type": "admin_precheck_llm_review",
        "file": os.path.basename(filepath),
        "filepath": filepath,
        "regex_summary": regex_result.get("summary", {}),
        "regex_status": regex_status_str,
        "prompt": prompt,
        "subagent": "cer-admin-precheck-reviewer",
        "subagent_config": {
            "tools": [],
            "disallowed_tools": [],
            "max_turns": 30,
            "timeout_seconds": 600,
            "output_format": "json_only",
        },
        "generated_at": datetime.now().isoformat(),
    }


def create_llm_review_batch(file_dir: str, per_file_results: list, only_flagged: bool = True) -> dict:
    """Create LLM review task packets for all flagged files in a batch run.

    Args:
        file_dir: Source directory
        per_file_results: Results from run_admin_pre_check_batch
        only_flagged: If True, only create tasks for files with WARNING/FAIL regex results

    Returns:
        Batch LLM task packet
    """
    tasks = []
    for result in per_file_results:
        summary = result.get("summary", {})
        is_flagged = summary.get("warning", 0) > 0 or summary.get("fail", 0) > 0

        if only_flagged and not is_flagged:
            continue

        task = create_llm_review_task(result.get("filepath", ""), result)
        if "error" not in task:
            tasks.append(task)

    return {
        "schema": "admin_precheck_llm_batch",
        "version": "v1",
        "project_id": os.path.basename(file_dir),
        "total_files_flagged": len(tasks),
        "tasks": tasks,
        "generated_at": datetime.now().isoformat(),
        "instructions": "Feed each task.prompt to cer-admin-precheck-reviewer subagent. Merge LLM findings with regex results. Output merged report.",
    }


def merge_regex_llm_results(regex_results: dict, llm_results: dict) -> dict:
    """Merge regex pre-screening results with LLM deep review findings.

    LLM findings can: CONFIRM regex (increase confidence), OVERRIDE regex (regex was wrong),
    or add NEW_FINDING (regex missed this).
    """
    merged = dict(regex_results)
    merged["llm_review_applied"] = True
    merged["llm_findings_summary"] = llm_results.get("summary", {})

    # Map file findings for merging
    llm_by_file = {}
    for finding in llm_results.get("findings", []):
        fname = finding.get("file", "")
        if fname not in llm_by_file:
            llm_by_file[fname] = []
        llm_by_file[fname].append(finding)

    # Merge into per-file results
    for file_result in merged.get("per_file_results", []):
        fname = file_result.get("file", "")
        llm_findings = llm_by_file.get(fname, [])
        file_result["llm_findings"] = llm_findings
        file_result["llm_findings_count"] = len(llm_findings)

        # Update summary: OVERRIDE can change FAIL→PASS
        overrides = sum(1 for f in llm_findings if f.get("llm_finding") == "OVERRIDE")
        new_findings = sum(1 for f in llm_findings if f.get("llm_finding") == "NEW_FINDING")
        file_result["llm_overrides"] = overrides
        file_result["llm_new_findings"] = new_findings

    merged["generated_at"] = datetime.now().isoformat()
    merged["note"] = "V28 Admin Pre-Check — hybrid regex+LLM. LLM findings supplement regex. All advisory."

    return merged


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python admin_pre_check.py <file_or_directory> [--mode regex|llm|hybrid] [--output report.json]")
        print("Modes:")
        print("  regex  — Fast regex pre-screening only (6 dimensions, deterministic)")
        print("  llm    — Generate LLM review task packet for files flagged by regex")
        print("  hybrid — Run regex, then generate LLM tasks for flagged files (default)")
        sys.exit(1)

    target = sys.argv[1]
    mode = "hybrid"
    output_path = "admin_pre_check_report.json"

    # Parse flags
    args = sys.argv[2:]
    i = 0
    while i < len(args):
        if args[i] == "--mode" and i + 1 < len(args):
            mode = args[i + 1]
            i += 2
        elif args[i] == "--output" and i + 1 < len(args):
            output_path = args[i + 1]
            i += 2
        else:
            i += 1

    # Step 1: Regex pre-screening (always runs)
    if os.path.isdir(target):
        regex_result = run_admin_pre_check_batch(target)
    else:
        regex_result = run_admin_pre_check(target)

    if mode == "regex":
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(regex_result, f, ensure_ascii=False, indent=2)
        s = regex_result.get("summary", regex_result)
        if isinstance(s, dict):
            print(f"Regex pre-check complete. Pass={s.get('pass',0)} Warn={s.get('warning',0)} Fail={s.get('fail',0)}")
        else:
            print(f"Regex pre-check complete. {regex_result.get('total_files_checked', 1)} file(s).")
        print(f"Report: {output_path}")
        sys.exit(0)

    # Step 2: LLM task generation (for llm and hybrid modes)
    per_file = regex_result.get("per_file_results", [regex_result])
    llm_batch = create_llm_review_batch(target, per_file, only_flagged=True)

    llm_output = output_path.replace(".json", "_llm_tasks.json")
    with open(llm_output, 'w', encoding='utf-8') as f:
        json.dump(llm_batch, f, ensure_ascii=False, indent=2)

    if mode == "llm":
        print(f"LLM task packet generated: {llm_batch['total_files_flagged']} files flagged for LLM review")
        print(f"Tasks: {llm_output}")
        print(f"Next: Feed tasks to cer-admin-precheck-reviewer subagent")
        sys.exit(0)

    # Step 3: Hybrid — output both regex report and LLM task packet
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(regex_result, f, ensure_ascii=False, indent=2)

    s = regex_result.get("summary", regex_result)
    if isinstance(s, dict) and "total_files_checked" not in regex_result:
        print(f"Admin pre-check (hybrid) complete.")
        print(f"  Regex: Pass={s.get('pass',0)} Warn={s.get('warning',0)} Fail={s.get('fail',0)}")
    elif "total_files_checked" in regex_result:
        print(f"Admin pre-check (hybrid) complete. {regex_result['total_files_checked']} files checked.")
        print(f"  Pass={regex_result.get('files_pass',0)} Warn={regex_result.get('files_warning',0)} Fail={regex_result.get('files_fail',0)}")
    print(f"  LLM tasks: {llm_batch['total_files_flagged']} files flagged → {llm_output}")
    print(f"  Regex report: {output_path}")
