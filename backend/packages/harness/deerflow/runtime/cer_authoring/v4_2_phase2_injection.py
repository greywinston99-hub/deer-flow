"""V4.2 Phase 2 Injection Module — injects Phase 2 fixes into CER authoring agents.

Covers all 7 root causes from A01 WYTD engineer review:
  RC1: Dual-domain SSOT data lock (MANUFACTURER strict + LITERATURE lineage)
  RC2: Anti-hallucination protocol
  RC3: SOTA screening logic V2 (PRISMA Tier 1/2/3 fix)
  RC4: Regulatory context lock (MDR 2017/745 only)
  RC5: Output quality gates (handled by quality_gates.py in Claude Code side)
  RC6: Prompt boundary guard (anti-leakage)
  RC7: Context window truncation guard (Fact Summary Card)

Activation:
  Environment variable: CER_AUTHORING_V4.2_PHASE2=1
  (also requires CER_AUTHORING_V4_MODE=1)

Usage in pipeline:
  from _v4.2_phase2_injection import get_phase2_agent_injection
  agent_prompt += get_phase2_agent_injection(agent_role="writer")

Or inject into all agents:
  from _v4.2_phase2_injection import inject_phase2_globally
  inject_phase2_globally()
"""

from __future__ import annotations

import json, os
from pathlib import Path

_KNOWLEDGE_FILE = Path(__file__).resolve().parent / "knowledge" / "v4.2_phase2_rules.json"
_RULES: dict | None = None


def _load_rules() -> dict:
    """Load Phase 2 rules, caching in memory."""
    global _RULES
    if _RULES is not None:
        return _RULES
    try:
        _RULES = json.loads(_KNOWLEDGE_FILE.read_text())
    except Exception:
        _RULES = {}
    return _RULES


def is_phase2_enabled() -> bool:
    """Check if Phase 2 is activated."""
    return (
        os.environ.get("CER_AUTHORING_V4.2_PHASE2", "").strip() == "1"
        and os.environ.get("CER_AUTHORING_V4_MODE", "").strip() == "1"
    )


# ---------------------------------------------------------------------------
# RC1: Dual-Domain SSOT Prompt Injection
# ---------------------------------------------------------------------------

def get_ssot_dual_domain_prompt() -> str:
    """Returns the dual-domain SSOT rules for Writer Agent system prompts."""
    rules = _load_rules()
    ssot = rules.get("dual_domain_ssot", {})
    if not ssot:
        return ""

    mfr = ssot.get("manufacturer_data", {})
    lit = ssot.get("literature_data", {})

    return f"""

<v4.2_ssot_dual_domain>
## CRITICAL: Dual-Domain Numerical Data Policy (V4.2 Phase 2)

You have TWO data sources. The rules differ per source.

### DOMAIN 1 — MANUFACTURER_DATA (STRICT_LOCK)
{mfr.get("instruction", "")}

Fields under STRICT_LOCK:
{', '.join(mfr.get("fields", [])[:15])}...

### DOMAIN 2 — LITERATURE_DATA (LINEAGE_LOCK)
{lit.get("instruction", "")}

Fields under LINEAGE_LOCK:
{', '.join(lit.get("fields", [])[:10])}...

### FORBIDDEN (BOTH DOMAINS)
- DO NOT generate any number without SSOT source or PMID citation
- DO NOT modify, round, or "improve" SSOT values
- DO NOT fabricate study identifiers or statistical results
</v4.2_ssot_dual_domain>
"""


# ---------------------------------------------------------------------------
# RC2 + RC6: Anti-Hallucination + Prompt Boundary Guard
# ---------------------------------------------------------------------------

def get_anti_hallucination_prompt() -> str:
    """Returns anti-hallucination and prompt boundary rules."""
    rules = _load_rules()
    ah = rules.get("anti_hallucination_protocol", {})
    pb = rules.get("prompt_boundary_guard", {})

    hard_blocks = '\n'.join(f"- {b}" for b in ah.get("hard_blocks", []))
    required = '\n'.join(f"- {b}" for b in ah.get("required_behaviors", []))
    boundary_rules = '\n'.join(f"- {r}" for r in pb.get("rules", []))

    gap_markers = rules.get("gap_marker_standardization", {}).get("markers", {})
    markers_text = '\n'.join(f"- `{k}`: {v}" for k, v in gap_markers.items())

    return f"""

<v4.2_anti_hallucination>
## ANTI-HALLUCINATION PROTOCOL (V4.2 Phase 2)

### HARD BLOCKS (Do NOT do any of these):
{hard_blocks}

### REQUIRED BEHAVIORS:
{required}

### UNIFIED GAP MARKERS:
{markers_text}
</v4.2_anti_hallucination>

<v4.2_prompt_boundary_guard>
## PROMPT BOUNDARY GUARD (V4.2 Phase 2)
{boundary_rules}
</v4.2_prompt_boundary_guard>
"""


# ---------------------------------------------------------------------------
# RC3: SOTA Screening Logic V2
# ---------------------------------------------------------------------------

def get_sota_screening_v2_prompt() -> str:
    """Returns SOTA V2 PRISMA screening logic for SOTA/Methodology agents."""
    rules = _load_rules()
    sota = rules.get("sota_screening_v2", {})

    t1 = sota.get("tier1_technical_filters", {})
    t2 = sota.get("tier2_academic_filters", {})
    t3 = sota.get("tier3_quality_assessment", {})
    comp = sota.get("comparator_logic_fix", {})
    prisma = sota.get("prisma_flow_single_source", "")

    return f"""

<v4.2_sota_screening_v2>
## SOTA LITERATURE SCREENING LOGIC V2 (V4.2 Phase 2)

### TIER 1 — Technical Filters (NEVER EXCLUDE on metadata alone)
{t1.get("rule", "")}
- PMID/DOI missing: {t1.get("pmid_missing", "")}
- Full-text unavailable: {t1.get("fulltext_unavailable", "")}
- Non-English full-text: {t1.get("non_english_fulltext", "")}

### TIER 2 — Academic Filters (EXCLUDE on content grounds)
{t2.get("rule", "")}
- No primary data: {t2.get("no_primary_data", "")}
- Wrong population: {t2.get("wrong_population", "")}
- Wrong intervention: {t2.get("wrong_intervention", "")}
- Case report N<10: {t2.get("case_report_small_n", "")}

### TIER 3 — Quality Assessment
- High risk of bias: {t3.get("high_risk_of_bias", "")}
- Critical risk of bias: {t3.get("critical_risk_of_bias", "")}

### COMPARATOR LOGIC FIX
- Novel device (no equivalence claimed): {comp.get("novel_device_no_equivalence", "")}
- Equivalence claimed: {comp.get("equivalence_claimed", "")}

### PRISMA FLOW SINGLE SOURCE
{prisma}
</v4.2_sota_screening_v2>
"""


# ---------------------------------------------------------------------------
# RC4: Regulatory Context Lock
# ---------------------------------------------------------------------------

def get_regulatory_lock_prompt() -> str:
    """Returns MDR-only regulatory context lock for all CER agents."""
    rules = _load_rules()
    reg = rules.get("regulatory_context_lock", {})

    forbidden_lines = []
    for name, info in reg.get("forbidden_references", {}).items():
        forbidden_lines.append(f"- {name}: {info.get('reason', '')}")

    allowed_lines = '\n'.join(f"- {g}" for g in reg.get("allowed_guidance", []))

    return f"""

<v4.2_regulatory_lock>
## REGULATORY CONTEXT LOCK (V4.2 Phase 2)

### APPLICABLE REGULATION
{reg.get('applicable_regulation', 'MDR 2017/745')}

### FORBIDDEN REFERENCES (HARD BLOCK — do NOT cite any of these):
{chr(10).join(forbidden_lines)}

### ALLOWED GUIDANCE (EXHAUSTIVE):
{allowed_lines}

### GSPR SCOPE
{reg.get('gspr_scope_instruction', '')}

### GSPR LOCATION
{reg.get('gspr_location', 'MDR Annex I')}
</v4.2_regulatory_lock>
"""


# ---------------------------------------------------------------------------
# RC7: Context Window Truncation Guard — Fact Summary Card
# ---------------------------------------------------------------------------

def get_fact_summary_card_prompt(project_context: dict | None = None) -> str:
    """Returns context truncation guard with optional project facts."""
    rules = _load_rules()
    ctx = rules.get("context_window_truncation_guard", {})
    fields = ctx.get("fact_summary_card_fields", [])

    facts_text = ""
    if project_context:
        facts_text = '\n'.join(
            f"- {f}: {project_context.get(f, 'UNKNOWN')}"
            for f in fields
        )

    return f"""

<v4.2_fact_summary_card>
## FACT SUMMARY CARD (V4.2 Phase 2 — Context Truncation Prevention)

Before generating any output, verify the following facts are correct:

{facts_text if facts_text else 'Facts must be loaded from SSOT before generation.'}

CRITICAL: If any fact is UNKNOWN, flag it. Do NOT fabricate.
If context was truncated, re-inject these facts before proceeding.
</v4.2_fact_summary_card>
"""


# ---------------------------------------------------------------------------
# V4.3 ADDITIONS: RC8, RC10, RC11, RC13
# ---------------------------------------------------------------------------

def get_comparative_analysis_prompt() -> str:
    """RC8: SOTA ↔ Clinical comparative analysis requirement."""
    return """

<v4.3_comparative_analysis>
## COMPARATIVE ANALYSIS REQUIREMENT (V4.3 — Meeting M3)

After generating SOTA benchmarks AND clinical trial data, you MUST produce:

1. **Endpoint Alignment Table** — Map each clinical trial endpoint to the corresponding SOTA benchmark:
   | Clinical Endpoint | Trial Value | SOTA Benchmark | SOTA Source (PMID) | Direction | Clinical Interpretation |
   |-------------------|-------------|----------------|---------------------|-----------|------------------------|
   | Sensitivity | X% | Y-Z% | PMID:#### | Better/Comparable | ... |

2. **Comparison Narrative** — For each aligned endpoint:
   - State the SOTA benchmark range
   - State the subject device value
   - Explain whether it is better/comparable/worse
   - Provide clinical context for the difference

3. **Safety Comparison** — Compare adverse event rates between subject device and SOTA literature

CRITICAL: Do NOT describe SOTA and clinical data in separate sections without comparing them.
The comparison IS the clinical evaluation.
</v4.3_comparative_analysis>
"""


def get_data_single_appearance_prompt() -> str:
    """RC10: Each quantitative finding appears in full exactly once."""
    return """

<v4.3_data_single_appearance>
## DATA SINGLE-APPEARANCE RULE (V4.3 — Meeting M8)

Each numerical finding from the pivotal clinical trial appears IN FULL exactly ONCE:

- **§6 Clinical Data**: Full presentation of all trial results (the ONE place)
- **§1 Executive Summary**: Direction only (e.g., "showed superior sensitivity"), NOT exact numbers
- **§4 Evidence Appraisal**: Quality/risk-of-bias assessment, NOT re-reporting numbers
- **§7 Benefit-Risk**: Cross-reference format → "(see §6.2, Table 6-X)"

VIOLATION: Repeating the same number in multiple chapters (especially with different values) causes confusion and inconsistency.
</v4.3_data_single_appearance>
"""


def get_narrative_continuity_prompt() -> str:
    """RC11: Narrative continuity and endpoint-driven structure."""
    return """

<v4.3_narrative_continuity>
## NARRATIVE CONTINUITY REQUIREMENT (V4.3 — Meeting M10)

The CER must read as a COHERENT STORY, not a collection of disconnected data fragments.

### STRUCTURAL REQUIREMENTS:
1. **Chapter Transitions**: Each chapter MUST have:
   - Opening sentence linking to the previous chapter's conclusion
   - Closing sentence previewing the next chapter's purpose
2. **Endpoint-Driven Flow**: The entire report revolves around 5-10 core clinical endpoints:
   - Define these endpoints early (§2 or §3)
   - Every subsequent analysis references these SAME endpoints
   - Never introduce a new endpoint in a later chapter without defining it first
3. **No Sudden Numbers**: A quantitative claim about a metric (e.g., "CV=72%") must be:
   - Introduced as a defined endpoint
   - Benchmarked against SOTA
   - Compared with clinical trial data
   - NOT dropped into analysis without context

### ANTI-PATTERN (Avoid):
"Manual technique has 72% variability... The BS-2 system showed 97.2% sensitivity..."
→ These are unrelated statements. Connect them or separate them.

### CORRECT PATTERN:
"Manual technique variability (CV 72%) limits diagnostic reproducibility [PMID]. In contrast, the BS-2 automated system reduced intra-patient CV to 7.9% in BS-CER-001, representing an 89% improvement in reproducibility."
</v4.3_narrative_continuity>
"""


def get_multidb_citation_prompt() -> str:
    """RC13: Multi-database citation convention with P-/E-/C- prefixes."""
    return """

<v4.3_multidb_citation>
## LITERATURE CITATION CONVENTION (V4.3 — Meeting M14)

### DATABASE-SPECIFIC PREFIXES:
- `P-001, P-002, ...` = PubMed articles
- `E-001, E-002, ...` = EMBASE articles
- `C-001, C-002, ...` = Cochrane Library articles

### USAGE:
- Cite literature as `[P-042]` or `[E-018]` in text
- Provide PMID/DOI in parentheses after the first citation: `[P-042, PMID: 32097410]`
- This convention PROVES multi-database coverage
- All PMID-only citations become untraceable for EMBASE/Cochrane articles

### PRISMA FLOW REQUIREMENT:
Present literature counts per database in the PRISMA diagram:
| Database | Records Identified | After Dedup | Included |
|----------|-------------------|-------------|----------|
| PubMed   | XXX | XXX | P-001 – P-XXX |
| EMBASE   | XXX | XXX | E-001 – E-XXX |
| Cochrane | XXX | XXX | C-001 – C-XXX |

### ABBREVIATIONS GLOSSARY:
Include an Abbreviations section (§0 or Appendix) explaining:
- P-XXX = PubMed reference XXX
- E-XXX = EMBASE reference XXX
- C-XXX = Cochrane reference XXX
- FACT-XXX = Manufacturer factual claim reference
</v4.3_multidb_citation>
"""


# ---------------------------------------------------------------------------
# Composite Injection Functions (Updated V4.3)
# ---------------------------------------------------------------------------

def get_phase2_agent_injection(agent_role: str = "writer", project_context: dict | None = None) -> str:
    """Returns the complete Phase 2 prompt injection for a given agent role.

    Args:
        agent_role: One of 'writer', 'sota', 'evidence_appraisal', 'intake', 'lead', 'all'
        project_context: Optional dict of project facts for Fact Summary Card

    Returns:
        Combined Phase 2 prompt string to append to agent system prompt.
    """
    if not is_phase2_enabled():
        return ""

    parts = []

    # ALL agents get regulatory lock + prompt boundary guard + anti-hallucination
    if agent_role in ("writer", "sota", "evidence_appraisal", "intake", "lead", "all"):
        parts.append(get_regulatory_lock_prompt())
        parts.append(get_anti_hallucination_prompt())

    # Writer agents get SSOT dual-domain rules
    if agent_role in ("writer", "lead", "all"):
        parts.append(get_ssot_dual_domain_prompt())

    # SOTA/Methodology agents get SOTA V2 screening logic
    if agent_role in ("sota", "intake", "all"):
        parts.append(get_sota_screening_v2_prompt())

    # All agents get fact summary card
    if agent_role in ("writer", "sota", "evidence_appraisal", "intake", "lead", "all"):
        parts.append(get_fact_summary_card_prompt(project_context))

    # ═══ V4.3 ADDITIONS ═══

    # Writer agents get comparative analysis requirement (RC8)
    if agent_role in ("writer", "lead", "all"):
        parts.append(get_comparative_analysis_prompt())

    # Writer agents get data single-appearance rule (RC10)
    if agent_role in ("writer", "lead", "all"):
        parts.append(get_data_single_appearance_prompt())

    # Writer agents get narrative continuity rules (RC11)
    if agent_role in ("writer", "lead", "all"):
        parts.append(get_narrative_continuity_prompt())

    # SOTA/Methodology agents get multi-DB citation convention (RC13)
    if agent_role in ("sota", "intake", "all"):
        parts.append(get_multidb_citation_prompt())

    return '\n'.join(parts)


def get_phase2_summary() -> dict:
    """Return summary of Phase 2 module state."""
    rules = _load_rules()
    return {
        "enabled": is_phase2_enabled(),
        "version": rules.get("version", "unknown"),
        "source": rules.get("source", ""),
        "components": {
            "dual_domain_ssot": bool(rules.get("dual_domain_ssot")),
            "regulatory_lock": bool(rules.get("regulatory_context_lock")),
            "sota_screening_v2": bool(rules.get("sota_screening_v2")),
            "anti_hallucination": bool(rules.get("anti_hallucination_protocol")),
            "prompt_boundary": bool(rules.get("prompt_boundary_guard")),
            "context_truncation": bool(rules.get("context_window_truncation_guard")),
            "gap_markers": bool(rules.get("gap_marker_standardization")),
        }
    }


# ---------------------------------------------------------------------------
# Integration Hook — call from pipeline startup
# ---------------------------------------------------------------------------

def inject_phase2_if_enabled(agent_configs: dict | None = None) -> dict:
    """Called by pipeline to activate Phase 2 globally.

    Returns status dict that can be logged.
    """
    if not is_phase2_enabled():
        return {"phase2_active": False, "reason": "env not set"}

    rules = _load_rules()
    return {
        "phase2_active": True,
        "version": rules.get("version"),
        "rules_file": str(_KNOWLEDGE_FILE),
        "components": get_phase2_summary()["components"],
    }


# Quick test when run directly
if __name__ == "__main__":
    os.environ["CER_AUTHORING_V4_MODE"] = "1"
    os.environ["CER_AUTHORING_V4.2_PHASE2"] = "1"

    print("=== Phase 2 Injection Module ===\n")
    print(f"Enabled: {is_phase2_enabled()}")
    print(f"\n--- Writer Agent Injection ---\n")
    print(get_phase2_agent_injection("writer", {"project_name": "Bubble Study System", "manufacturer_name": "WYTD Medical"}))
    print("\n--- Summary ---")
    import json as _j
    print(_j.dumps(get_phase2_summary(), indent=2))
