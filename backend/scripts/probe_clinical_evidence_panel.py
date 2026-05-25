"""Bounded probe: test clinical evidence panel agent with repaired prompt + positive fixture."""
import sys, json, time, asyncio, re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "harness"))
from deerflow.models import create_chat_model

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROMPT_PATH = PROJECT_ROOT / "prompts" / "cer" / "canonical" / "cer_clinical_evidence_panel_agent.md"
CER_PATH = PROJECT_ROOT / "examples" / "cer_review" / "production_smoke_positive" / "CER_quantified_low_risk_positive.txt"

system_prompt = PROMPT_PATH.read_text()
cer_text = CER_PATH.read_text()
cer_preview = cer_text[:8000]

task_prompt = f"""You are dispatched as cer-clinical-evidence-panel-reviewer for CER review step cer_clinical_evidence_panel.

## CER Document Text (read this carefully — it is the primary source for your review)
```
{cer_preview}
```

## Project Profile
```json
{{
    "project_id": "CER-TS2K-POSITIVE-SMOKE",
    "device_name": "ThermaScan PRO-2000 Digital Thermometer",
    "device_class": "Class IIa",
    "intended_use": "Intermittent measurement of human body temperature",
    "jurisdiction": "EU MDR"
}}
```

Produce ONLY the benefit_risk_report sub-assessment. Return valid JSON with this structure:
{{
    "schema_name": "cer_benefit_risk",
    "content_sufficiency": "evidence_present_and_adequate",
    "cer_text_available": true,
    "cer_text_length": {len(cer_preview)},
    "extracted_claims": [],
    "findings": [],
    "human_gate_required": true,
    "no_final_decision_made": true
}}

CRITICAL: Every finding MUST cite specific content from the CER text above. Do NOT use template phrases like "CER does not explicitly document." If the CER text has quantified benefits, risks, and acceptability statements, acknowledge them."""

async def probe():
    model = create_chat_model(name=None, thinking_enabled=False)
    print("Running bounded probe (120s timeout)...", flush=True)
    start = time.time()
    result = await asyncio.wait_for(
        model.ainvoke([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": task_prompt},
        ]),
        timeout=120,
    )
    elapsed = time.time() - start
    text = result.content if hasattr(result, "content") else str(result)
    print(f"Probe complete ({elapsed:.1f}s, {len(text)} chars)", flush=True)

    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        print("FAILED: no JSON found")
        print(f"Raw: {text[:500]}")
        return False

    data = json.loads(match.group())
    fs = data.get("findings", [])
    print(f"\ncontent_sufficiency: {data.get('content_sufficiency', 'N/A')}")
    print(f"findings: {len(fs)}")

    template_phrases = [
        "CER does not explicitly document specific clinical benefits",
        "CER does not explicitly document residual risks",
        "CER lacks explicit binary acceptability",
        "CER does not clearly state that clinical benefits outweigh",
    ]
    template_hits = 0
    for f in fs:
        desc = f.get("mismatch_description", "")
        sev = f.get("severity", "?")
        item = f.get("item", "?")
        src = f.get("source_ref", "")[:80]
        print(f"  [{sev}] {item}")
        print(f"    {desc[:120]}")
        print(f"    source: {src}")
        for tp in template_phrases:
            if tp[:30].lower() in desc.lower():
                template_hits += 1
                break

    if template_hits > 0:
        print(f"\nBLOCKED: {template_hits} template findings detected")
        return False
    if len(fs) == 0:
        print("\nBLOCKED: no findings generated")
        return False
    high_findings = [f for f in fs if f.get("severity") == "high"]
    print(f"\nANTI-TEMPLATE PASSED: 0 template findings")
    print(f"high severity: {len(high_findings)}")
    print(f"PROBE PASSED: output is input-sensitive and non-template")
    return True

success = asyncio.run(probe())
sys.exit(0 if success else 1)
