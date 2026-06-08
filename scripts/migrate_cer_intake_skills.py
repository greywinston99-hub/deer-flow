#!/usr/bin/env python3
"""Migrate CER Intake prompts to DeerFlow skills/public/ system.

Usage:
    cd /Users/winstonwei/Documents/Playground/deer-flow
    python3 scripts/migrate_cer_intake_skills.py
"""

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PROMPTS_DIR = REPO_ROOT / "prompts" / "cer" / "intake"
SKILLS_DIR = REPO_ROOT / "skills" / "public" / "cer-intake"
EXTENSIONS_CONFIG = REPO_ROOT / "extensions_config.json"

SKILL_MAPPING = {
    "file_inventory_agent.md": {
        "name": "cer-intake-file-inventory",
        "description": "Enumerate all submitted raw files with metadata and cryptographic identity for CER intake.",
        "allowed_tools": "ls, bash",
    },
    "dedupe_agent.md": {
        "name": "cer-intake-dedupe",
        "description": "Deduplicate evidence pack files by SHA-256 checksum for CER intake.",
        "allowed_tools": "bash, read_file",
    },
    "document_parsing_agent.md": {
        "name": "cer-intake-document-parsing",
        "description": "Extract text from PDF, DOCX, XLSX and TXT files for CER intake.",
        "allowed_tools": "bash, read_file",
    },
    "pdf_readability_agent.md": {
        "name": "cer-intake-pdf-readability",
        "description": "Assess PDF readability, text extractability and OCR requirements for CER intake.",
        "allowed_tools": "read_file, ls, bash",
    },
    "document_type_detection_agent.md": {
        "name": "cer-intake-document-type-detection",
        "description": "Detect document types and assign Evidence Pack classifications for CER intake.",
        "allowed_tools": "read_file, ls, bash",
    },
    "evidence_classification_agent.md": {
        "name": "cer-intake-evidence-classification",
        "description": "Perform final EP classification per file with confidence assessment for CER intake.",
        "allowed_tools": "read_file, ls, bash",
    },
    "evidence_completeness_agent.md": {
        "name": "cer-intake-evidence-completeness",
        "description": "Assess evidence pack completeness against MDR 2017/745 requirements for CER intake.",
        "allowed_tools": "read_file, ls, bash, write_file",
    },
    "citation_locator_agent.md": {
        "name": "cer-intake-citation-locator",
        "description": "Trace citations and verify source locations across evidence documents for CER intake.",
        "allowed_tools": "read_file, ls, bash, write_file",
    },
    "human_gate_packet_writer.md": {
        "name": "cer-intake-human-gate-packet",
        "description": "Compile structured human review packets for gate decisions in CER intake.",
        "allowed_tools": "read_file, ls, bash, write_file",
    },
    "intake_qa_agent.md": {
        "name": "cer-intake-qa",
        "description": "Perform post-lock QA checks on the locked evidence pack for CER intake.",
        "allowed_tools": "read_file, ls, bash, write_file",
    },
    "orchestrator_agent.md": {
        "name": "cer-intake-orchestrator",
        "description": "Orchestrate the end-to-end CER Raw Project Intake pipeline across all stages.",
        "allowed_tools": "read_file, ls, bash, write_file",
    },
}


def migrate():
    if not PROMPTS_DIR.exists():
        print(f"Prompts directory not found: {PROMPTS_DIR}")
        return

    SKILLS_DIR.mkdir(parents=True, exist_ok=True)

    # Load existing extensions config
    if EXTENSIONS_CONFIG.exists():
        config = json.loads(EXTENSIONS_CONFIG.read_text(encoding="utf-8"))
    else:
        config = {"mcpServers": {}, "skills": {}}

    if "skills" not in config:
        config["skills"] = {}

    for filename, meta in SKILL_MAPPING.items():
        src = PROMPTS_DIR / filename
        if not src.exists():
            print(f"  SKIP (not found): {filename}")
            continue

        skill_dir = SKILLS_DIR / meta["name"]
        skill_dir.mkdir(parents=True, exist_ok=True)
        skill_file = skill_dir / "SKILL.md"

        # Read original content
        original_content = src.read_text(encoding="utf-8")

        # Build YAML frontmatter
        frontmatter = f"""---
name: {meta["name"]}
description: {meta["description"]}
license: proprietary
allowed-tools: {meta["allowed_tools"]}
---

"""

        # Combine frontmatter + original content
        skill_content = frontmatter + original_content
        skill_file.write_text(skill_content, encoding="utf-8")
        print(f"  CREATED: {skill_file.relative_to(REPO_ROOT)}")

        # Register in extensions_config.json
        config["skills"][meta["name"]] = {"enabled": True}

    # Write extensions config
    EXTENSIONS_CONFIG.write_text(
        json.dumps(config, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"\n  UPDATED: {EXTENSIONS_CONFIG.relative_to(REPO_ROOT)}")
    print(f"\nMigration complete. {len(SKILL_MAPPING)} skills created.")


if __name__ == "__main__":
    migrate()
