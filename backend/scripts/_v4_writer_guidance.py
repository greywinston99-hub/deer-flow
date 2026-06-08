"""V4 Writer Guidance Loader — makes V4 writing standards available to pipeline.

When CER_AUTHORING_V4_MODE=1, this module loads V4 writer guidance and
makes it available as a Python dict for writer agents to reference.

Usage:
    from _v4_writer_guidance import get_v4_guidance
    guidance = get_v4_guidance()
    if guidance:
        print(guidance["templates"]["device_description"]["pattern"])
"""
from __future__ import annotations

import json, os
from pathlib import Path


def get_v4_guidance() -> dict | None:
    """Load V4 writer guidance if V4 mode is enabled."""
    if os.environ.get("CER_AUTHORING_V4_MODE", "").strip() != "1":
        return None

    # Find knowledge dir relative to this script
    script_dir = Path(__file__).resolve().parent
    knowledge_path = script_dir.parent / "packages" / "harness" / "deerflow" / \
                     "runtime" / "cer_authoring" / "knowledge" / "v4_writer_guidance.json"

    if not knowledge_path.exists():
        return None

    with open(knowledge_path) as f:
        return json.load(f)


def get_v4_section_requirements(section: str) -> dict:
    """Get V4 requirements for a specific CER section."""
    guidance = get_v4_guidance()
    if not guidance:
        return {}
    return guidance.get("section_requirements", {}).get(section, {})


def get_v4_evidence_rules() -> dict:
    """Get V4 evidence quality rules."""
    guidance = get_v4_guidance()
    if not guidance:
        return {}
    return guidance.get("evidence_rules", {})


def get_v4_template(template_name: str) -> dict:
    """Get a specific V4 writing template."""
    guidance = get_v4_guidance()
    if not guidance:
        return {}
    return guidance.get("templates", {}).get(template_name, {})


# Quick smoke test when run directly
if __name__ == "__main__":
    os.environ["CER_AUTHORING_V4_MODE"] = "1"
    g = get_v4_guidance()
    if g:
        print(f"[V4] Writer guidance loaded: {g['version']}")
        print(f"[V4] Templates: {len(g['templates'])} writing templates")
        print(f"[V4] Sections: {len(g['section_requirements'])} defined")
        print(f"[V4] Evidence rules: {len(g['evidence_rules'])} rules")
        print(f"[V4] Quality gates: {len(g['quality_gates'])} gates")
    else:
        print("[V4] Failed to load guidance")
