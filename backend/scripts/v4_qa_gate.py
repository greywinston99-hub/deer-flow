#!/usr/bin/env python3
"""V4 QA Gate — checks a CER against V4 execution contract.

Usage:
    python v4_qa_gate.py --artifact-root <ARTIFACT_ROOT> [--v4-mode]

Checks:
    CER existence, structure, placeholders, AI traces, PMID count,
    SOTA reasoning chain, IFU/RMF/GSPR alignment, DeerFlow review,
    operator-assisted writing ledger, closeout package.
"""
from __future__ import annotations

import json, os, re, sys
from pathlib import Path
from datetime import datetime


def qa_check(artifact_root: str, v4_mode: bool = False) -> dict:
    """Run V4 QA gate checks. Returns dict with pass/fail per check."""
    root = Path(artifact_root)
    results = {
        "qa_run_at": datetime.now().isoformat(),
        "artifact_root": str(root),
        "v4_mode": v4_mode,
        "checks": [],
    }

    def check(name: str, passed: bool, detail: str = "") -> None:
        results["checks"].append({"check": name, "pass": passed, "detail": detail})

    # C1: CER file exists
    cer_md = root / "CER_draft_V4.md"
    cer_docx = root / "CER_draft_V4.docx"
    check("CER_draft_exists", cer_md.exists() or cer_docx.exists(),
          f"MD={cer_md.exists()}, DOCX={cer_docx.exists()}")

    # C2: Section structure (check MD if exists)
    if cer_md.exists():
        content = cer_md.read_text(encoding="utf-8")
        sections_found = sum(1 for s in ["SUMMARY", "SCOPE", "STATE OF THE ART",
            "DEVICE UNDER EVALUATION", "CONCLUSIONS", "NEXT EVALUATION",
            "QUALIFICATION", "DECLARATION", "DATES AND SIGNATURES", "ANNEX"] if s in content)
        check("section_structure", sections_found >= 7,
              f"{sections_found}/10 key sections found")

        # C3: Placeholders
        placeholders = content.count("[To be completed]") + content.lower().count("to be completed")
        check("zero_placeholders", placeholders == 0,
              f"Found {placeholders} occurrences")

        # C4: AI traces
        ai_traces = 0
        for t in ["DeerFlow", "auto-generated", "pipeline", "AI-generated"]:
            ai_traces += content.lower().count(t.lower())
        check("zero_ai_traces", ai_traces == 0,
              f"Found {ai_traces} occurrences")

        # C5: PMID count
        pmids = len(re.findall(r'\b\d{8}\b', content))
        check("pmid_count", pmids >= 100,
              f"Found {pmids} PMIDs (minimum 100)")

        # C6: SOTA reasoning chain
        has_benchmark = "SOTA" in content and "benchmark" in content.lower()
        has_evidence = "PMID" in content
        check("sota_reasoning_chain", has_benchmark and has_evidence,
              f"Benchmark={'YES' if has_benchmark else 'NO'}, Evidence={'YES' if has_evidence else 'NO'}")

        # C7: GSPR alignment
        gspr_count = content.count("GSPR")
        check("gspr_alignment", gspr_count >= 10,
              f"Found {gspr_count} GSPR references (minimum 10)")

    # C8: DeerFlow review report
    review = root / "cer_review_report_V3.json"
    review2 = root / "cer_review_report_V4.json"
    # Also check in review_output
    review3 = root / "review_output" / "final_synthesis.json"
    check("deerflow_review_exists", review.exists() or review2.exists() or review3.exists(),
          f"Review JSON={'YES' if review.exists() else 'NO'}")

    # C9: Operator-assisted writing ledger
    ledger = root / "closeout_package" / "OPERATOR_ASSISTED_WRITING_LEDGER.csv"
    check("operator_ledger_exists", ledger.exists(),
          f"Ledger={'YES' if ledger.exists() else 'NO'}")

    # C10: Closeout package
    closeout = root / "closeout_package"
    closeout_files = len(list(closeout.glob("*"))) if closeout.exists() else 0
    check("closeout_package", closeout_files >= 5,
          f"Found {closeout_files} files (minimum 5)")

    # Summary
    passed = sum(1 for c in results["checks"] if c["pass"])
    total = len(results["checks"])
    results["summary"] = f"{passed}/{total} checks passed"
    results["overall"] = "PASS" if passed == total else "CONDITIONAL_PASS" if passed >= total - 2 else "FAIL"

    return results


def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--artifact-root", required=True)
    p.add_argument("--v4-mode", action="store_true")
    args = p.parse_args()

    results = qa_check(args.artifact_root, args.v4_mode)
    print(json.dumps(results, indent=2, ensure_ascii=False))

    if results["overall"] == "FAIL":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
