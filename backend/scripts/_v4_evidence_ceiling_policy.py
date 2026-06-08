"""V4 Evidence Ceiling Policy — defines how evidence quality is handled.

When full-text PDFs are available: evidence_ceiling = STRONG
When only title/abstract: evidence_ceiling = MODERATE
When no evidence: evidence_ceiling = LIMITED — CER blocked until evidence provided

This policy is read by the evidence_sufficiency_gate (G42) in V4 mode.
"""
from __future__ import annotations

import os
from pathlib import Path


def determine_evidence_ceiling(artifact_root: str) -> dict:
    """Determine the evidence ceiling based on available data."""
    root = Path(artifact_root)
    pdf_dir = root / "full_text_pdfs"
    full_text_count = len(list(pdf_dir.glob("*.pdf"))) if pdf_dir.exists() else 0
    
    # Count evidence records with full-text status
    full_text_available = full_text_count > 0

    if full_text_count >= 50:
        ceiling = "STRONG"
        note = f"{full_text_count} full-text PDFs available. Evidence appraisal based on full-text content."
    elif full_text_count > 0:
        ceiling = "MODERATE_TO_STRONG"
        note = f"{full_text_count} full-text PDFs available ({full_text_count} < 50 minimum for STRONG). Supplement with title/abstract evidence."
    else:
        ceiling = "MODERATE"
        note = "No full-text PDFs available. Evidence appraisal based on title/abstract screening. Full-text retrieval recommended before final CER submission."
    
    return {
        "evidence_ceiling": ceiling,
        "full_text_pdf_count": full_text_count,
        "note": note,
        "degraded_mode": ceiling in ("MODERATE", "MODERATE_TO_STRONG"),
        "recommendation": "Acquire full-text PDFs for PMIDs in evidence registry" if full_text_count < 50 else None,
    }


# This policy is NOT BLOCKS_STABLE_V4 — it DEGRADES_V4_QUALITY
# Classification: DEGRADES_V4_QUALITY
# Rationale: Without PDF ingestion, evidence stays at title/abstract level.
# CER is still structurally complete and DeFflow Review can still PASS.
# But evidence quality ceiling is MODERATE not STRONG.
# Mitigation: Transparent evidence ceiling labeling + PMCF recommendation for full-text acquisition.
