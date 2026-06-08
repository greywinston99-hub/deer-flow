#!/usr/bin/env python3
"""V4 Operator-Assisted Writing Ledger — records Claude Code writing assistance.

Usage:
    python v4_operator_ledger.py record \
      --artifact-root <ARTIFACT_ROOT> \
      --section "<SECTION>" \
      --action-type "<TYPE>" \
      --source-basis "<BASIS>" \
      --deerflow-artifact "<ARTIFACT>" \
      [--new-evidence] [--re-review-required]

    python v4_operator_ledger.py check \
      --artifact-root <ARTIFACT_ROOT>
"""
from __future__ import annotations

import argparse, csv, os, sys, uuid
from datetime import datetime, timezone
from pathlib import Path


LEDGER_HEADER = [
    "entry_id", "timestamp", "section", "action_type",
    "source_basis", "deerflow_artifact_basis",
    "new_evidence_introduced", "re_review_required",
    "reverse_upgrade_candidate"
]


def ledger_path(artifact_root: str) -> Path:
    return Path(artifact_root) / "closeout_package" / "OPERATOR_ASSISTED_WRITING_LEDGER.csv"


def record_entry(artifact_root: str, section: str, action_type: str,
                 source_basis: str, deerflow_artifact: str,
                 new_evidence: bool = False, re_review: bool = True) -> str:
    """Record an assisted writing entry to the ledger."""
    path = ledger_path(artifact_root)
    path.parent.mkdir(parents=True, exist_ok=True)

    entry_id = f"OAW-{uuid.uuid4().hex[:6].upper()}"
    timestamp = datetime.now(timezone.utc).isoformat()

    # Auto-detect reverse upgrade candidate
    upgrade_map = {
        "regenerate_section": "Writer section regeneration quality",
        "embed_table": "DU-002: Writer native table embedding",
        "add_pmid_citation": "Writer PMID citation density",
        "fix_structure": "DU-005: Section structure detection",
        "apply_engineer_template": "DU-004: Writer prompt engineering templates",
        "add_quantitative_data": "DU-003: PDF ingestion + quantitative extraction",
        "fix_header_format": "DU-005: Markdown header formatting",
        "clean_ai_traces": "Writer output AI trace removal",
        "expand_section": "Writer section depth/completeness",
    }
    upgrade = upgrade_map.get(action_type, f"Writer capability gap: {action_type}")

    row = [entry_id, timestamp, section, action_type, source_basis,
           deerflow_artifact, str(new_evidence), str(re_review), upgrade]

    file_exists = path.exists()
    with open(path, "a", newline="") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(LEDGER_HEADER)
        writer.writerow(row)

    print(f"[V4-LEDGER] Recorded {entry_id}: {action_type} in {section}")
    return entry_id


def check_ledger(artifact_root: str) -> dict:
    """Check that a ledger exists and has entries."""
    path = ledger_path(artifact_root)
    result = {"ledger_exists": path.exists(), "entry_count": 0, "status": "MISSING"}

    if path.exists():
        with open(path) as f:
            reader = csv.DictReader(f)
            entries = list(reader)
            result["entry_count"] = len(entries)
            result["status"] = "PRESENT" if entries else "EMPTY"
            # Check all entries have required fields
            missing = []
            for e in entries:
                for h in LEDGER_HEADER:
                    if h not in e or not e[h]:
                        missing.append(f"{e.get('entry_id','?')}: missing {h}")
            result["validation_errors"] = missing
            result["valid"] = len(missing) == 0

    return result


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command")

    rec = sub.add_parser("record")
    rec.add_argument("--artifact-root", required=True)
    rec.add_argument("--section", required=True)
    rec.add_argument("--action-type", required=True)
    rec.add_argument("--source-basis", required=True)
    rec.add_argument("--deerflow-artifact", required=True)
    rec.add_argument("--new-evidence", action="store_true")
    rec.add_argument("--re-review-required", action="store_true", default=True)

    chk = sub.add_parser("check")
    chk.add_argument("--artifact-root", required=True)

    args = parser.parse_args()

    if args.command == "record":
        record_entry(args.artifact_root, args.section, args.action_type,
                     args.source_basis, args.deerflow_artifact,
                     args.new_evidence, args.re_review_required)
    elif args.command == "check":
        import json
        result = check_ledger(args.artifact_root)
        print(json.dumps(result, indent=2))
        if not result["ledger_exists"] or result["entry_count"] == 0:
            return 1
        if not result.get("valid", False):
            return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
