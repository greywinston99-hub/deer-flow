"""V4 Table Templates — provides standard CER table schemas for writer output.

In V4 mode, these table templates are injected into writer context so that
key structured data (claims, SOTA benchmarks, evidence appraisal, PRISMA,
GSPR conformity) appears in the CER as formatted tables rather than prose.
"""
from __future__ import annotations

V4_TABLE_TEMPLATES = {
    "claim_ledger": {
        "title": "Claim Ledger",
        "columns": ["Claim ID", "Claim Type", "Claim Text", "Supporting Evidence", "Strength"],
        "section": "§2 or §4.5",
    },
    "sota_benchmark_matrix": {
        "title": "SOTA Benchmark Matrix",
        "columns": ["Benchmark ID", "Endpoint", "Corresponding Claim", "SOTA Value Range", "Evidence Source (PMID)"],
        "section": "§3.6 or §3.7",
    },
    "prisma_flow": {
        "title": "PRISMA 2020 Flow Diagram",
        "columns": ["Phase", "Records"],
        "rows": [
            ["Records identified from databases", "{database_records}"],
            ["Records after deduplication", "{deduplicated_records}"],
            ["Title/Abstract screened", "{title_abstract_screened}"],
            ["Records excluded", "{title_abstract_excluded}"],
            ["Full-text assessed", "{full_text_assessed}"],
            ["Full-text excluded", "{full_text_excluded}"],
            ["SOTA studies included", "{sota_included}"],
        ],
        "section": "§4.4.2",
    },
    "evidence_appraisal": {
        "title": "Evidence Appraisal Summary",
        "columns": ["Evidence ID", "PMID", "Title", "Appraisal Score", "Evidence Level", "Supporting Claim(s)"],
        "section": "§4.5",
    },
    "gspr_conformity": {
        "title": "GSPR Conformity Summary",
        "columns": ["GSPR", "Requirement", "Applicable Evidence", "Conformity Determination"],
        "section": "§4.7",
    },
    "benefit_risk_ledger": {
        "title": "Benefit-Risk Ledger",
        "columns": ["Claim ID", "Clinical Benefit", "Residual Risk", "Risk Control Measure", "Acceptability"],
        "section": "§5",
    },
    "vigilance_summary": {
        "title": "Vigilance Database Search Summary",
        "columns": ["Database", "Search Date", "Records Retrieved", "Relevant Records", "Key Findings"],
        "section": "§4.6",
    },
    "similar_devices": {
        "title": "Similar Devices Comparison",
        "columns": ["Attribute", "MSoft (Device Under Evaluation)", "GE Xeleris 1.1", "Siemens syngo.via", "Philips IntelliSpace", "Hermes Medical"],
        "section": "§2.4 or §4.2",
    },
    "standards_conformance": {
        "title": "Standards Conformance",
        "columns": ["Standard", "Application", "Evidence Reference", "Claim Support"],
        "section": "§4.3.1",
    },
    "clinical_indications": {
        "title": "Clinical Indications (9-Domain)",
        "columns": ["Domain", "Procedure Category", "Specific Applications", "Supporting Evidence (PMID)"],
        "section": "§2.2.2",
    },
}


def get_v4_table_template(table_name: str) -> dict | None:
    """Get a V4 table template by name."""
    return V4_TABLE_TEMPLATES.get(table_name)


def get_all_v4_templates() -> dict:
    """Get all V4 table templates."""
    return V4_TABLE_TEMPLATES


def render_table_from_data(template_name: str, **data) -> str:
    """Render a markdown table from a template with data substitution."""
    tmpl = V4_TABLE_TEMPLATES.get(template_name)
    if not tmpl:
        return ""

    cols = tmpl["columns"]
    header = "| " + " | ".join(cols) + " |\n"
    sep = "|" + "|".join([":---"] * len(cols)) + "|\n"
    md = f"**{tmpl['title']}**\n\n{header}{sep}"

    if "rows" in tmpl:
        for row in tmpl["rows"]:
            # Substitute {variables} with data values
            rendered_row = [str(r).format(**data) for r in row]
            md += "| " + " | ".join(rendered_row) + " |\n"

    return md


# Smoke test
if __name__ == "__main__":
    print(f"V4 Table Templates: {len(V4_TABLE_TEMPLATES)} templates loaded")
    for name, tmpl in V4_TABLE_TEMPLATES.items():
        print(f"  {name}: {tmpl['title']} ({len(tmpl['columns'])} cols) → {tmpl['section']}")
    
    # Render PRISMA with test data
    prisma = render_table_from_data("prisma_flow",
        database_records="753", deduplicated_records="708",
        title_abstract_screened="778", title_abstract_excluded="278",
        full_text_assessed="500", full_text_excluded="354", sota_included="146")
    print(f"\nPRISMA table rendered ({len(prisma)} chars):\n{prisma[:300]}...")
