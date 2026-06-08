"""Phase 2B: Extract actual runtime prompts, hash them, freeze PROMPT_PACK_V1.

This script reads the actual prompt functions from the codebase, extracts
the prompt text that agents receive at runtime, computes SHA-256 hashes,
and writes PROMPT_PACK_V1 with hash manifest.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, "/Users/winstonwei/Documents/Playground/deer-flow/backend/packages/harness")

from deerflow.runtime.cer_authoring.agents import (
    _stable_prompt,
    _production_prompt,
    _review_prompt,
    PHYSICAL_AGENT_NAMES,
    PRODUCTION_AGENT_NAMES,
    REVIEW_GATE_AGENT_NAMES,
    _STABLE_SPECS,
    _PRODUCTION_SPECS,
    _REVIEW_SPECS,
)

OUTPUT_DIR = Path("/Users/winstonwei/Documents/Playground/deer-flow/docs/cer_authoring_stack_freeze/claude_team/PROMPT_PACK_V1")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def extract_prompts() -> dict:
    manifest = {"schema": "prompt_hash_manifest_v1", "freeze_date": "2026-05-15", "prompts": {}}

    # 1. Stable 1+6 physical agent prompts
    for name in PHYSICAL_AGENT_NAMES:
        prompt = _stable_prompt(name)
        h = hash_text(prompt)
        filename = f"stable_{name}.txt"
        (OUTPUT_DIR / filename).write_text(prompt, encoding="utf-8")
        manifest["prompts"][f"stable_{name}"] = {
            "prompt_type": "stable_physical_agent",
            "agent_name": name,
            "role_spec": _STABLE_SPECS.get(name, "")[:200],
            "hash": h,
            "filename": filename,
            "length_chars": len(prompt),
        }

    # 2. Production virtual agent prompts
    for name in PRODUCTION_AGENT_NAMES:
        prompt = _production_prompt(name)
        h = hash_text(prompt)
        filename = f"production_{name}.txt"
        (OUTPUT_DIR / filename).write_text(prompt, encoding="utf-8")
        manifest["prompts"][f"production_{name}"] = {
            "prompt_type": "production_virtual_agent",
            "agent_name": name,
            "role_spec": _PRODUCTION_SPECS.get(name, "")[:200],
            "hash": h,
            "filename": filename,
            "length_chars": len(prompt),
        }

    # 3. Review/gate virtual agent prompts
    for name in REVIEW_GATE_AGENT_NAMES:
        prompt = _review_prompt(name)
        h = hash_text(prompt)
        filename = f"review_{name}.txt"
        (OUTPUT_DIR / filename).write_text(prompt, encoding="utf-8")
        manifest["prompts"][f"review_{name}"] = {
            "prompt_type": "review_virtual_agent",
            "agent_name": name,
            "role_spec": _REVIEW_SPECS.get(name, "")[:200],
            "hash": h,
            "filename": filename,
            "length_chars": len(prompt),
        }

    # 4. Extract Writer-relevant template prompts from pipeline.py
    pipeline_path = Path("/Users/winstonwei/Documents/Playground/deer-flow/backend/packages/harness/deerflow/runtime/cer_authoring/pipeline.py")
    pipeline_text = pipeline_path.read_text(encoding="utf-8")

    # Extract key prompt/instruction constants
    key_patterns = {
        "writer_conclusion_instruction": r'def _writer_instruction_for_conclusion.*?return\s+"(.*?)"',
        "claim_evidence_writer_instruction": r'def _cross_evidence_writer_instruction.*?return\s+"(.*?)"',
        "insufficiency_signal_rule": r'INSUFFICIENCY_SIGNAL_RULE\s*=\s*"(.*?)"',
    }

    for label, pattern in key_patterns.items():
        m = re.search(pattern, pipeline_text, re.DOTALL)
        if m:
            text = m.group(1).strip()
            h = hash_text(text)
            filename = f"pipeline_{label}.txt"
            (OUTPUT_DIR / filename).write_text(text, encoding="utf-8")
            manifest["prompts"][f"pipeline_{label}"] = {
                "prompt_type": "pipeline_prompt_constant",
                "source": "pipeline.py",
                "hash": h,
                "filename": filename,
                "length_chars": len(text),
            }

    # 5. Domain template writer instructions
    from deerflow.runtime.cer_authoring.writer_remediation.domain_templates import (
        cardiac_stabilizer_template_sections,
        orthopedic_plasma_electrode_template_sections,
        imaging_software_template_sections,
    )

    for label, builder in [
        ("cardiac_stabilizer", cardiac_stabilizer_template_sections),
        ("plasma_electrode", orthopedic_plasma_electrode_template_sections),
        ("imaging_software", imaging_software_template_sections),
    ]:
        sections = builder()
        combined = "\n\n---\n\n".join(
            f"Section: {s.get('title', '')}\nInstruction: {s.get('writer_instruction', '')}"
            for s in sections
        )
        h = hash_text(combined)
        filename = f"domain_template_{label}.txt"
        (OUTPUT_DIR / filename).write_text(combined, encoding="utf-8")
        manifest["prompts"][f"domain_template_{label}"] = {
            "prompt_type": "domain_template_writer_instruction",
            "domain": label,
            "hash": h,
            "filename": filename,
            "length_chars": len(combined),
            "section_count": len(sections),
        }

    # 6. Harden prompt contracts — Writer constraints
    constraints = {
        "writer_must_obey_claim_support_matrix": True,
        "writer_must_obey_writer_conclusion_constraints": True,
        "writer_cannot_write_favourable_benefit_risk_unless_allowed": True,
        "writer_cannot_use_cross_domain_template_text": True,
        "writer_cannot_write_audit_artifact_into_cer_body": True,
        "qa_must_check_body_content_not_just_structure": True,
    }
    manifest["prompt_contracts"] = constraints

    return manifest


def main():
    print("Extracting runtime prompts...")
    manifest = extract_prompts()
    manifest_path = OUTPUT_DIR.parent / "PROMPT_HASH_MANIFEST.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Written: {manifest_path}")
    print(f"Prompt pack: {OUTPUT_DIR}")
    print(f"Total prompts extracted: {len(manifest['prompts'])}")

    # Print summary
    for key, info in sorted(manifest["prompts"].items()):
        print(f"  {key}: hash={info['hash']} ({info['length_chars']} chars)")


if __name__ == "__main__":
    main()
