# EXTRACTION MODEL A/B TEST PLAN

> CCD | 2026-05-15 | Phase 3A

## Test Design

**Task**: IFU 2.1 device description field extraction. Input = raw IFU text. Output = structured fields (composition, working principle, performance, variants, sterility) with source anchors.

**Candidates**: kimi-code (current baseline), kimi API, MiniMax M2.7 highspeed.

DeepSeek V4 Pro excluded from extraction test — reserved for reasoning/writing tasks. Extraction needs speed and structured output reliability over fluency.

## Test Input

Standard IFU text (use CAL-001 PADN catheter IFU or pilot IFU files). Same input for all 3 models.

## Scoring Dimensions

| Dimension | Weight | How Scored |
|-----------|--------|-----------|
| Structured JSON validity | 25% | Valid JSON, all required fields present, correct types |
| Field presence | 25% | How many expected fields populated (not null/empty) |
| Source anchor correctness | 20% | Source page/document reference matches actual IFU |
| Content fidelity | 15% | Extracted text matches IFU source (no hallucination) |
| Latency | 10% | Extraction time per IFU |
| Timeout rate | 5% | % of extractions exceeding time budget |

## Failure Criteria

Hallucinated content (device attribute not in IFU) → immediate disqualification. Model must not invent device characteristics.

## Recommended

kimi-k2.6-code for extraction. Structured output task, not writing. Current model validated through pipeline. Switch only if candidate beats it on ≥2 dimensions with no hallucination. MiniMax considered only if latency improvement is significant and no hallucination detected.

---

*CCD 签发：2026-05-15*
