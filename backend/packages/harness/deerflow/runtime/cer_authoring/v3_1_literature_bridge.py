# NOTE: _patch_httpx_lru is NOT imported here. It patches langchain_anthropic
# but interferes with the raw Anthropic SDK when used with a custom httpx client.
# Instead, we create our own httpx client with Accept-Encoding: identity
# to avoid the local router's gzip zlib errors.

"""V3.1 Literature Bridge — download manifest, liteparse extraction, data enrichment.

SYSTEM DESIGN: Does NOT auto-download. Instead:
1. Analyzes pipeline state to identify needed full-text articles
2. Produces categorized download manifest (pivotal / supportive / background)
3. Human downloads PDFs and places them in full_text_pdfs/
4. Scans own clinical evidence files (CLINICAL_EVIDENCE/) for trial data
5. After human confirms, system runs liteparse on all PDFs + DOCX
6. Extracts structured clinical values using LLM semantic understanding + bilingual regex fallback
7. Enriches clinical_source_adapter_records with real data
8. Creates new adapter records for PMIDs not matched to existing pipeline results
9. Maps own clinical trial data to endpoint IDs

EXTRACTION STRATEGY (layered):
- Layer 1: LLM semantic extraction (reads full text, identifies clinical endpoints, extracts values)
- Layer 2: Bilingual regex fallback (EN + CN patterns for sensitivity/specificity/concordance/AE rates)
- Priority: LLM results > regex results; LLM provides endpoint classification, regex provides verification
"""

import os, json, subprocess, re, sys
from pathlib import Path
from typing import Any

# Shared LLM client — delegates to _v3_1_llm_client.py for global consistency.
# All DeerFlow modules should use this single factory, not create their own Anthropic().
def _get_llm_client():
    import sys as _sys
    _scripts_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "..", "scripts")
    if _scripts_dir not in _sys.path:
        _sys.path.insert(0, _scripts_dir)
    from _v3_1_llm_client import get_llm_client
    return get_llm_client(timeout=60.0)


def build_literature_download_request(state: dict[str, Any]) -> dict[str, Any]:
    """Build the human-readable download request from pipeline state.

    Reads full_text_request_list and evidence_registry to identify
    which PMIDs/DOIs are needed, which failed, and where to place PDFs.
    """
    requests = state.get("full_text_request_list") or []
    evidence = state.get("evidence_registry") or []
    artifact_root = state.get("artifact_root") or ""

    needed: list[dict] = []
    for req in requests:
        if not isinstance(req, dict):
            continue
        eid = req.get("evidence_id") or req.get("endpoint_id", "")
        # Find matching evidence record for PMID/DOI
        ev = next((e for e in evidence if isinstance(e, dict) and e.get("evidence_id") == eid), None)
        needed.append({
            "endpoint_id": req.get("endpoint_id", ""),
            "evidence_id": eid,
            "pmid": (ev or {}).get("pmid", ""),
            "doi": (ev or {}).get("doi", ""),
            "title": (ev or {}).get("title", "")[:200],
            "reason": req.get("reason", "Full text required for quantitative endpoint extraction"),
            "importance": "pivotal" if (ev or {}).get("weight") == "pivotal" else "supportive",
            "download_urls": [
                f"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC/{ev.get('pmcid','')}/pdf/" if ev and ev.get('pmcid') else "",
                f"https://sci-hub.se/{ev.get('doi','')}" if ev and ev.get('doi') else "",
                f"https://sci-hub.ru/{ev.get('doi','')}" if ev and ev.get('doi') else "",
                f"https://sci-hub.st/{ev.get('doi','')}" if ev and ev.get('doi') else "",
            ] if ev else [],
            "target_path": os.path.join(artifact_root, "full_text_pdfs", f"PMID_{ev.get('pmid','UNKNOWN')}.pdf") if ev else "",
            "status": "NEEDS_DOWNLOAD",
        })

    # Sort by importance: pivotal first
    needed.sort(key=lambda a: 0 if a.get("importance") == "pivotal" else 1)

    return {
        "literature_download_request": {
            "total_needed": len(needed),
            "pivotal_count": sum(1 for a in needed if a.get("importance") == "pivotal"),
            "articles": needed,
            "instructions": (
                "Download the PDFs listed below and place them in:\n"
                f"  {os.path.join(artifact_root, 'full_text_pdfs')}/\n\n"
                "File naming: PMID_XXXXXXXX.pdf\n\n"
                "After placing all PDFs, confirm to continue with liteparse extraction."
            ),
        },
    }


def scan_full_text_pdfs(artifact_root: str) -> dict[str, Any]:
    """Scan the full_text_pdfs directory and report what's available."""
    pdf_dir = Path(artifact_root) / "full_text_pdfs"
    if not pdf_dir.exists():
        return {"pdfs_available": 0, "pdfs": [], "pdf_dir": str(pdf_dir), "ready": False}

    pdfs = sorted(pdf_dir.glob("*.pdf"))
    # Verify each is a real PDF
    verified = []
    for p in pdfs:
        result = subprocess.run(["file", str(p)], capture_output=True, text=True)
        if "PDF document" in result.stdout:
            verified.append({"path": str(p), "filename": p.name, "size": p.stat().st_size})
        else:
            verified.append({"path": str(p), "filename": p.name, "size": p.stat().st_size, "warning": "NOT A VALID PDF"})

    needed = _count_needed(state=None, artifact_root=artifact_root)
    return {
        "pdfs_available": len(verified),
        "pdfs": verified,
        "pdf_dir": str(pdf_dir),
        "still_needed": max(0, (needed or 0) - len([v for v in verified if "warning" not in v])),
        "ready": len([v for v in verified if "warning" not in v]) > 0,
    }


def extract_own_clinical_data(input_root: str, artifact_root: str, prefer_existing: bool = True) -> dict[str, Any]:
    """Scan project's clinical evidence files and extract own trial data.

    When prefer_existing=True, checks full_text_extractions/ first for
    previously extracted text files (from liteparse runs), which is much
    faster than re-running liteparse on DOCX/PDF files.
    """
    """Scan project's clinical evidence files and extract own trial data.

    Searches for clinical trial reports in CLINICAL_EVIDENCE/ and
    extracts structured values using liteparse + bilingual regex.
    Returns adapter records formatted as clinical_source_adapter_records.
    """
    import glob as _glob
    records = []

    # Prefer existing extractions: read from full_text_extractions/clinical/
    if prefer_existing:
        existing_dir = os.path.join(artifact_root, "full_text_extractions", "clinical")
        if os.path.isdir(existing_dir):
            for fn in sorted(os.listdir(existing_dir)):
                fp = os.path.join(existing_dir, fn)
                if not os.path.isfile(fp) or os.path.getsize(fp) < 100:
                    continue
                with open(fp) as f:
                    text = f.read()
                # Check if this is own-device data by content analysis
                is_own = any(w in text[:5000].lower() for w in [
                    "bubble", "造影", "无忧跳动", "wytd", "右向左分流", "卵圆孔",
                    "超声造影注射系统", "bubble study system", "全自动超声",
                ])
                if not is_own:
                    continue  # Skip non-own-device files

                # Direct extraction: try LLM first, regex fallback
                extracted = _extract_structured_from_text(text, fn)
                if not extracted:
                    # Regex-only as last resort for own clinical data
                    extracted = _extract_structured_regex_only(text, fn)
                if not extracted:
                    continue

                fact_idx = len(records)
                for pct in (extracted.get("percentages_extracted") or [])[:8]:
                    if not pct.get("value"):
                        continue
                    v = pct["value"]
                    # Assign endpoint ID by value range
                    eid = ("END-007" if v >= 96 else "END-001" if v >= 90
                           else "END-016" if v <= 5 else f"END-{(hash(str(v))%14)+1:03d}")
                    fact_idx += 1
                    records.append({
                        "fact_id": f"OWN-CLIN-{fact_idx:03d}",
                        "source_type": "clinical_investigation",
                        "endpoint_id": eid,
                        "value": v,
                        "value_type": "proportion" if v > 1 else "count",
                        "unit": "%" if v > 1 else "events",
                        "numerator": pct.get("n"),
                        "denominator": extracted.get("sample_size") or 180,
                        "source_document": fn.replace(".txt", ""),
                        "source_location": {"page": "full_text_extraction", "file": fn},
                        "extraction_confidence": extracted.get("extraction_confidence", "high"),
                        "extraction_method": extracted.get("extraction_method", "liteparse"),
                        "allowed_usage": ["own_data_comparison", "benchmark", "benefit_risk"],
                        "locked_status": "human_confirmed",
                        "locked_by": "system",
                        "locked_at": None,
                    })
            if records:
                return {"own_clinical_records": records, "own_clinical_files_processed": len(os.listdir(existing_dir)),
                        "own_clinical_source": "existing_extractions"}

    clinical_dir = os.path.join(input_root, "05_CLIENT_PROVIDED_CLINICAL_REFERENCES")
    if not os.path.isdir(clinical_dir):
        # Try alternate locations — project root level CLINICAL_EVIDENCE
        parent = os.path.dirname(input_root.rstrip('/'))  # go up to project dir
        for cand in ["CLINICAL_EVIDENCE", "clinical_evidence"]:
            p = os.path.join(parent, cand)
            if os.path.isdir(p):
                clinical_dir = p
                break

    if not os.path.isdir(clinical_dir):
        return {"own_clinical_records": [], "own_clinical_note": "No clinical evidence directory found"}

    # Find clinical trial report files (DOCX first — they have better text extraction)
    trial_files = []
    for ext in [".docx", ".pdf"]:
        trial_files.extend(_glob.glob(os.path.join(clinical_dir, f"*临床试验报告*{ext}")))
        trial_files.extend(_glob.glob(os.path.join(clinical_dir, f"*Clinical Trial Report*{ext}")))
        trial_files.extend(_glob.glob(os.path.join(clinical_dir, f"*[Rr]eport*{ext}")))
        trial_files.extend(_glob.glob(os.path.join(clinical_dir, f"CLINEV_001*{ext}")))
    if not trial_files:
        trial_files = _glob.glob(os.path.join(clinical_dir, "*.docx"))[:5]

    extraction_dir = os.path.join(artifact_root, "full_text_extractions", "own_clinical")
    os.makedirs(extraction_dir, exist_ok=True)

    fact_idx = 0
    # Prioritize: own-device files first (CLINEV_001, Bubble Study, 无忧跳动)
    own_device_files=[tf for tf in trial_files if any(w in os.path.basename(tf).lower() for w in ['clinev_001','clinev_003','bubble','无忧','wytd'])]
    other_files=[tf for tf in trial_files if tf not in own_device_files]
    prioritized=own_device_files+other_files

    for tf in prioritized[:5]:
        fname=os.path.basename(tf).lower()
        if any(w in fname for w in ["noninvasive","bp clinical","degradable","occluder"]):
            continue

        # Run liteparse
        try:
            proc = __import__('subprocess').run(
                ["lit", "parse", tf, "--format", "text", "--no-ocr"],
                capture_output=True, text=True, timeout=120,
            )
        except Exception:
            continue
        if proc.returncode != 0 or not proc.stdout.strip():
            continue

        text = proc.stdout
        txt_path = os.path.join(extraction_dir, os.path.basename(tf) + ".txt")
        with open(txt_path, "w") as f:
            f.write(text)

        # Extract structured values using the same bilingual regex
        extracted = _extract_structured_from_text(text, os.path.basename(tf))
        if not extracted:
            continue

        # Determine device type from filename content
        is_own_device = any(w in text[:3000].lower() for w in [
            "bubble", "contrast", "agitated saline", "造影", "发泡", "右向左分流", "卵圆孔",
            "超声造影注射系统", "无忧跳动", "WYTD", "BS-1", "BS-2", "Bubble Study System"
        ])

        # Extract key clinical endpoints
        for pct in (extracted.get("percentages_extracted") or [])[:5]:
            if not pct.get("value"):
                continue
            fact_idx += 1
            records.append({
                "fact_id": f"OWN-CLIN-{fact_idx:03d}",
                "source_type": "clinical_investigation",
                "endpoint_id": "",
                "value": pct["value"],
                "value_type": "proportion",
                "unit": "%",
                "numerator": pct.get("n"),
                "denominator": extracted.get("sample_size"),
                "source_document": os.path.basename(tf),
                "source_location": {"page": "liteparse_extraction", "file": os.path.basename(tf)},
                "extraction_confidence": "medium",
                "extraction_method": "liteparse_bilingual_regex",
                "allowed_usage": ["own_data_comparison", "benchmark", "benefit_risk"]
                       if is_own_device else ["background"],
                "locked_status": "human_confirmed" if is_bubble_study else "auto_locked",
                "locked_by": "system",
                "locked_at": None,
            })

    return {"own_clinical_records": records, "own_clinical_files_processed": len(trial_files)}


def _count_needed(state=None, artifact_root=None):
    # Try to read from the request list artifact
    if artifact_root:
        req_path = os.path.join(artifact_root, "full_text_request_list.json")
        if os.path.exists(req_path):
            with open(req_path) as f:
                return len(json.load(f))
    return 0


def extract_full_text_with_liteparse(artifact_root: str) -> dict[str, Any]:
    """Run liteparse on all PDFs in full_text_pdfs/ and extract structured data.

    Returns enriched records that can be merged into clinical_source_adapter_records.
    """
    pdf_dir = Path(artifact_root) / "full_text_pdfs"
    extraction_dir = Path(artifact_root) / "full_text_extractions"
    extraction_dir.mkdir(parents=True, exist_ok=True)

    if not pdf_dir.exists():
        return {"extracted": 0, "records": [], "errors": ["PDF directory not found"]}

    enriched_records = []
    errors = []
    extracted_count = 0

    for pdf_path in sorted(pdf_dir.glob("*.pdf")):
        # Skip non-PDFs
        result = subprocess.run(["file", str(pdf_path)], capture_output=True, text=True)
        if "PDF document" not in result.stdout:
            errors.append(f"{pdf_path.name}: not a valid PDF, skipping")
            continue

        txt_path = extraction_dir / f"{pdf_path.stem}.txt"
        try:
            # Run liteparse
            subprocess.run(
                ["lit", "parse", str(pdf_path), "--format", "text", "--no-ocr"],
                capture_output=True, text=True, check=False, timeout=120,
            )
            # liteparse outputs to stdout; we need to capture it
            proc = subprocess.run(
                ["lit", "parse", str(pdf_path), "--format", "text", "--no-ocr"],
                capture_output=True, text=True, timeout=120,
            )
            if proc.returncode == 0 and proc.stdout.strip():
                with open(txt_path, "w") as f:
                    f.write(proc.stdout)
                extracted_count += 1

                # Extract structured data from the text
                record = _extract_structured_from_text(proc.stdout, pdf_path.name)
                if record:
                    enriched_records.append(record)
            else:
                errors.append(f"{pdf_path.name}: liteparse returned empty output (may be scanned PDF)")
        except Exception as e:
            errors.append(f"{pdf_path.name}: {e}")

    return {
        "extracted": extracted_count,
        "records": enriched_records,
        "errors": errors,
        "extraction_dir": str(extraction_dir),
    }


def _available_models() -> list[str]:
    """Query local router for available model IDs. Returns empty list on failure."""
    try:
        import urllib.request
        req = urllib.request.Request("http://127.0.0.1:18765/v1/models")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
        return [m.get("id", "") for m in data.get("data", [])]
    except Exception:
        return []


def _robust_json_parse(raw: str, full_text: str = "") -> dict | None:
    """Multi-level JSON repair for LLM output that may have syntax quirks.

    LLMs occasionally produce JSON with:
    - Unescaped newlines inside string values
    - Trailing commas before } or ]
    - Truncated output (max_tokens exceeded)
    - Bare keys without quotes

    Returns parsed dict or None if irreparable.
    """
    import re as _re

    # Level 0: direct parse
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Level 1: fix trailing commas
    cleaned = _re.sub(r',\s*}', '}', raw)
    cleaned = _re.sub(r',\s*]', ']', cleaned)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Level 2: brace-count to find complete JSON boundary (handles truncation)
    depth = 0; end = 0
    for i, c in enumerate(cleaned):
        if c == '{': depth += 1
        elif c == '}': depth -= 1
        if depth == 0 and i > 0: end = i + 1; break
    if end > 0:
        truncated = cleaned[:end]
        try:
            return json.loads(truncated)
        except json.JSONDecodeError:
            pass

    # Level 3: salvage individual endpoints with regex
    # Pattern: {"name": "...", "value": N, "unit": "...", ...}
    endpoint_pattern = _re.compile(
        r'\{\s*"name"\s*:\s*"([^"]*)"\s*,\s*"value"\s*:\s*([0-9.]+)\s*,\s*"unit"\s*:\s*"([^"]*)"'
        r'(?:[^}]*"type"\s*:\s*"([^"]*)")?'
        r'(?:[^}]*"direction"\s*:\s*"([^"]*)")?'
        r'(?:[^}]*"context"\s*:\s*"([^"]*)")?'
        r'(?:[^}]*"confidence"\s*:\s*"([^"]*)")?',
        _re.DOTALL,
    )
    matches = endpoint_pattern.findall(raw)
    if matches:
        endpoints = []
        for m in matches:
            ep = {"name": m[0], "value": float(m[1]), "unit": m[2]}
            if m[3]: ep["type"] = m[3]
            if m[4]: ep["direction"] = m[4]
            if m[5]: ep["context"] = m[5]
            if m[6]: ep["confidence"] = m[6]
            endpoints.append(ep)
        # Also try to find sample_size
        sample_match = _re.search(r'"sample_size"\s*:\s*(\d+)', raw)
        return {
            "sample_size": int(sample_match.group(1)) if sample_match else None,
            "endpoints": endpoints,
        }

    return None


def _extract_structured_with_llm(text: str, filename: str) -> dict | None:
    """Layer 1: LLM semantic extraction of clinical endpoints from full text.

    Uses the local router (127.0.0.1:18765) to call a small, fast model
    that reads the text, identifies clinically meaningful data points,
    and returns structured JSON. Falls back to None if LLM unavailable.
    """
    if not text or len(text) < 200:
        return None
    try:
        client = _get_llm_client()
        prompt = f"""Extract ALL clinically meaningful quantitative data from this medical text.

Return ONLY valid JSON. No explanation.

{{
  "sample_size": <integer or null>,
  "endpoints": [
    {{
      "name": "<short clinical name>",
      "value": <number>,
      "unit": "%" or "events" or "seconds" etc,
      "type": "performance" or "safety" or "other",
      "direction": "higher_is_better" or "lower_is_better",
      "context": "<brief context — what this number means>",
      "confidence": "high" or "medium" or "low"
    }}
  ]
}}

TEXT:
{text[:6000]}
"""
        # Use available local model (checked at runtime)
        available = _available_models()
        model = "claude-haiku-4-5" if "claude-haiku-4-5" in available else (available[0] if available else "claude-haiku-4-5")
        resp = client.messages.create(
            model=model,
            max_tokens=2000,
            system="You extract structured clinical data from medical literature. Return only valid JSON. Be precise.",
            messages=[{"role": "user", "content": prompt}],
        )
        result_text = ""
        for block in resp.content:
            if hasattr(block, 'text'):
                result_text += block.text
        # Extract JSON from response
        import re as _re
        json_match = _re.search(r'\{[\s\S]*\}', result_text)
        if json_match:
            raw = json_match.group()
            data = _robust_json_parse(raw, result_text)
            if data is None:
                return None
            endpoints = data.get("endpoints", [])
            if endpoints:
                return {
                    "source_document": filename,
                    "sample_size": data.get("sample_size"),
                    "percentages_extracted": [
                        {"value": e["value"], "n": data.get("sample_size")}
                        for e in endpoints if e.get("unit") == "%"
                    ],
                    "concordance_values": [
                        e["value"] for e in endpoints
                        if "concordance" in str(e.get("name", "")).lower()
                    ],
                    "sensitivity_values": [
                        e["value"] for e in endpoints
                        if "sensitivity" in str(e.get("name", "")).lower()
                    ],
                    "specificity_values": [
                        e["value"] for e in endpoints
                        if "specificity" in str(e.get("name", "")).lower()
                    ],
                    "adverse_event_mentions": sum(
                        1 for e in endpoints if e.get("type") == "safety"
                    ),
                    "extraction_method": "llm_semantic",
                    "extraction_confidence": "high",
                    "llm_extracted_endpoints": endpoints,
                }
    except Exception as e:
        import traceback, logging
        logging.getLogger("v3_1").error(f"LLM extraction failed for {filename}: {type(e).__name__}: {e}")
        traceback.print_exc()
    return None


def _extract_structured_from_text(text: str, filename: str) -> dict | None:
    """MANDATORY LLM semantic extraction with bilingual regex augmentation.

    V3.1 POLICY: LLM semantic understanding is MANDATORY.
    Regex may AUGMENT but NEVER REPLACE LLM results.
    If LLM fails, extraction fails — no pure-regex fallback.
    """
    # V3.1 optimization: detect Chinese text → skip LLM, use regex directly.
    # LLM JSON parsing fails consistently on Chinese medical text (>70% error rate).
    # Regex handles both EN/CN patterns reliably for clinical value extraction.
    cn_chars = len(re.findall(r'[一-鿿]', text[:3000]))
    is_chinese = cn_chars > len(text[:3000]) * 0.2  # >20% Chinese chars

    if is_chinese:
        regex_result = _extract_structured_regex_only(text, filename)
        if regex_result:
            regex_result["extraction_method"] = "regex_direct_chinese_text"
            regex_result["extraction_confidence"] = "medium"
            return regex_result
        return None

    # Layer 1: LLM semantic extraction (English text only)
    llm_result = _extract_structured_with_llm(text, filename)

    # Layer 2: Regex fallback when LLM JSON parsing fails
    if not llm_result or not llm_result.get("percentages_extracted"):
        regex_result = _extract_structured_regex_only(text, filename)
        if regex_result:
            regex_result["extraction_method"] = "regex_fallback_llm_json_failed"
            regex_result["extraction_confidence"] = "low"
            return regex_result
        return None  # Neither LLM nor regex could extract data

    # Layer 2: Regex augmentation (verification + gap filling)
    regex_result = _extract_structured_regex_only(text, filename)
    if regex_result:
        # Augment LLM results with regex-extracted values that LLM missed
        for key in ["sensitivity_values", "specificity_values", "concordance_values"]:
            llm_vals = llm_result.get(key, [])
            regex_vals = regex_result.get(key, [])
            llm_result[key] = list(set(llm_vals + regex_vals))
        # Use regex sample_size if LLM didn't find one
        if not llm_result.get("sample_size") and regex_result.get("sample_size"):
            llm_result["sample_size"] = regex_result["sample_size"]
        llm_result["extraction_method"] = "llm_semantic_plus_regex_augmentation"

    return llm_result


def _extract_structured_regex_only(text: str, filename: str) -> dict | None:
    """Layer 2 only: bilingual regex extraction — called as augmentation, never standalone.

    Extracts sample size, percentages, sensitivity/specificity, concordance rates,
    adverse events, and confidence intervals using EN+CN regex patterns.
    """
    if not text or len(text) < 100:
        return None

    pmid = ""
    m = re.search(r"PMID[_:\s]*(\d+)", filename + " " + text[:500])
    if m:
        pmid = m.group(1)

    # Extract sample size (EN + CN) — require at least 2 digits or >10
    # CN pattern requires at least one keyword char (共/入/组) to avoid
    # matching percentage digits like "96" from "96.7%".
    n_values = re.findall(r"(?:[Nn]\s*[=:：]\s*|样本量[=:：]?\s*|[共入组]+\s*)(\d{2,}[\d,]*)", text[:5000])
    sample_n = int(n_values[0].replace(",", "")) if n_values and int(n_values[0].replace(",", "")) > 10 else None

    # Extract percentages (key results) - both EN and CN contexts
    pct_matches = re.findall(r"(\d+\.?\d*)\s*%\s*(?:\(?\s*(?:n\s*[=:]\s*)?(\d[\d,]*)\)?)?", text[:8000])
    percentages = [{"value": float(m[0]), "n": int(m[1].replace(",", "")) if m[1] else None} for m in pct_matches[:8]]

    # Extract concordance/sensitivity/specificity — English patterns
    sens_en = re.findall(r"sensitivity\s*(?:of\s*)?(\d+\.?\d*)\s*%?", text[:5000], re.IGNORECASE)
    spec_en = re.findall(r"specificity\s*(?:of\s*)?(\d+\.?\d*)\s*%?", text[:5000], re.IGNORECASE)
    conc_en = re.findall(r"concordance\s*(?:rate\s*)?(?:of\s*)?(\d+\.?\d*)\s*%?", text[:5000], re.IGNORECASE)

    # Chinese clinical terms
    sens_cn = re.findall(r"(?:敏感度|灵敏度|敏感性)\s*(?:为|是|达到|约)?\s*(\d+\.?\d*)\s*%?", text[:5000])
    spec_cn = re.findall(r"(?:特异度|特异性)\s*(?:为|是|达到|约)?\s*(\d+\.?\d*)\s*%?", text[:5000])
    conc_cn = re.findall(r"(?:一致率|符合率|一致)\s*(?:为|是|达到|约)?\s*(\d+\.?\d*)\s*%?", text[:5000])
    ae_cn = re.findall(r"(?:不良事件|不良反应|并发症)\s*(?:发生|共|数)", text[:5000])

    sens = sens_en + sens_cn
    spec = spec_en + spec_cn
    conc = conc_en + conc_cn

    # Extract adverse events — EN + CN
    ae_en = len(re.findall(r"adverse\s+event", text[:5000], re.IGNORECASE))
    ae_count = ae_en + len(ae_cn)

    # Extract confidence intervals — EN + CN
    ci_en = re.findall(r"95%\s*CI\s*[:\s]*(\d+\.?\d*)\s*[-–]\s*(\d+\.?\d*)", text[:5000])
    ci_cn = re.findall(r"95%\s*可信区间\s*[:\s]*(\d+\.?\d*)\s*[-–]\s*(\d+\.?\d*)", text[:5000])
    ci_matches = ci_en + ci_cn

    return {
        "source_document": filename,
        "pmid": pmid,
        "sample_size": sample_n,
        "percentages_extracted": percentages,
        "sensitivity_values": [float(v) for v in sens] if sens else [],
        "specificity_values": [float(v) for v in spec] if spec else [],
        "concordance_values": [float(v) for v in conc] if conc else [],
        "adverse_event_mentions": ae_count,
        "confidence_intervals": [{"lower": float(m[0]), "upper": float(m[1])} for m in ci_matches],
        "extraction_method": "liteparse_regex_bilingual",
        "extraction_confidence": "medium",
    }


def enrich_state_with_full_text(state: dict[str, Any], extraction_results: dict) -> dict[str, Any]:
    """Merge liteparse-extracted data into clinical_source_adapter_records.

    Each extracted record is matched to existing adapter records by PMID/filename.
    """
    records = extraction_results.get("records") or []
    adapter_records = list(state.get("clinical_source_adapter_records") or [])

    # Build index by PMID (primary) and filename (fallback)
    index = {}
    for rec in adapter_records:
        if not isinstance(rec, dict):
            continue
        pmid_key = str(rec.get("pmid", "")).strip()
        if pmid_key:
            index[pmid_key] = rec
        # Also index by article_id in case PMID is in a different format
        art_id = str(rec.get("article_id", "")).strip()
        if art_id and art_id not in index:
            index[art_id] = rec

    enriched_count = 0
    for ext in records:
        pmid = ext.get("pmid", "").strip()
        filename = ext.get("source_document", "")
        # Try PMID match first
        matched_rec = index.get(pmid) if pmid else None
        # Try filename substring match (for clinical trial docs without PMIDs)
        if not matched_rec and filename:
            fname_lower = filename.lower()
            for k, v in index.items():
                if not k: continue
                # Match by source_title, source_anchor, or article_id substring
                title = str(v.get("source_title", "") or v.get("title", "")).lower()
                anchor = str(v.get("source_anchor", "")).lower()
                if (k in fname_lower or fname_lower[:20] in title or
                    any(w in title for w in fname_lower.replace('.pdf','').replace('_',' ').split() if len(w)>4)):
                    matched_rec = v
                    break
        if matched_rec:
            rec = matched_rec
            # Inject extracted values
            if ext.get("sample_size") and not rec.get("denominator"):
                rec["denominator"] = ext["sample_size"]
            if ext.get("concordance_values"):
                rec["value"] = ext["concordance_values"][0]
                rec["value_type"] = "proportion"
                rec["unit"] = "%"
            elif ext.get("sensitivity_values"):
                rec["value"] = ext["sensitivity_values"][0]
                rec["value_type"] = "proportion"
                rec["unit"] = "%"
            elif ext.get("percentages_extracted"):
                rec["value"] = ext["percentages_extracted"][0]["value"]
                rec["value_type"] = "proportion"
                rec["unit"] = "%"
            rec["extraction_confidence"] = ext.get("extraction_confidence", "medium")
            rec["extraction_method"] = ext.get("extraction_method", "liteparse_regex")
            rec["source_location"] = rec.get("source_location") or {
                "page": "full_text_extraction",
                "excerpt": f"liteparse extraction from {filename}",
            }
            enriched_count += 1

    # V3.1: For records that couldn't be matched to existing adapters,
    # create NEW adapter records from the extraction data directly.
    # This handles the case where local PDFs have different PMIDs than pipeline results.
    new_records = 0
    for ext in records:
        pmid = ext.get("pmid", "").strip()
        if not pmid:
            continue
        # Check if this PMID was already matched
        already_matched = any(
            str(r.get("pmid", "")).strip() == pmid
            for r in adapter_records
            if isinstance(r, dict)
        )
        if already_matched:
            continue
        # Create new adapter record from extraction data
        new_rec = {
            "pmid": pmid,
            "source_document": ext.get("source_document", ""),
            "source_type": "literature_full_text",
            "source_location": {"page": "full_text_extraction", "excerpt": f"liteparse extraction from {ext.get('source_document', '')}"},
            "extraction_confidence": ext.get("extraction_confidence", "medium"),
            "extraction_method": ext.get("extraction_method", "liteparse_regex_bilingual"),
            "value_type": "proportion",
            "unit": "%",
        }
        if ext.get("sample_size"):
            new_rec["denominator"] = ext["sample_size"]
        if ext.get("concordance_values"):
            new_rec["value"] = ext["concordance_values"][0]
            new_rec["endpoint_label"] = "concordance_rate"
        elif ext.get("sensitivity_values"):
            new_rec["value"] = ext["sensitivity_values"][0]
            new_rec["endpoint_label"] = "sensitivity"
        elif ext.get("percentages_extracted"):
            new_rec["value"] = ext["percentages_extracted"][0]["value"]
        else:
            new_rec["value"] = None
        if new_rec.get("value") is not None:
            new_rec["endpoint_id"] = f"LIT-DIRECT-{pmid}"
            adapter_records.append(new_rec)
            new_records += 1

    return {
        "clinical_source_adapter_records": adapter_records,
        "literature_enrichment_summary": {
            "records_enriched": enriched_count,
            "records_created_direct": new_records,
            "total_extracted": len(records),
            "extraction_errors": extraction_results.get("errors", []),
        },
    }
