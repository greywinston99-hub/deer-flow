# CODEX BATCH INSTRUCTIONS — Spiral Architecture Correction

> CCD 签发 | 2026-05-11 | Phase 0 complete。分批下发。

## BATCH 0 — COMPLETE。8 specs frozen。

## BATCH 1 — Structural Guard Only (Codex, after owner approval)

Scope: Prevent Writer when reasoning chain not ready。NOT: evidence spiral, agent prompts, new gates。

1.1 — Writer 后移 (graph.py): `cer_writing` after `pre_writer_readiness_gate`。
1.2 — G46 gate (graph.py+gates.py): per PRE_WRITER_READINESS_CONTRACT。
1.3 — writer_guard edge (graph.py): G46 PASS→Writer, FAIL→compromise。
1.4 — controlled_compromise node (graph.py+pipeline.py): terminal non-CER path。

Acceptance: PASS path unchanged。FAIL path = no Writer, no CER draft。Existing tests pass。

## BATCH 2 — Evidence Loop + Retrieval Depth (Codex)

2.1 — 5-pool model (pipeline.py): remove 40-cap。
2.2 — Spiral loop (graph.py+pipeline.py): max 3 rounds, REWORK→sota_search。
2.3 — G42 per-claim sufficiency gate (gates.py)。
2.4 — Loop state lineage (state.py+pipeline.py)。

## BATCH 3 — Hard Gate Routing (Codex)

3.1 — G39-G45 gates (gates.py)。
3.2 — Routing map (graph.py): REWORK→exact upstream, BLOCKED→compromise。
3.3 — Gate signal contract (state.py+gates.py)。

## BATCH 4 — Agent Realignment (Codex)

4.1 — Agent insufficiency signals (agents.py)。
4.2 — Writer conditional consumption (agents.py+pipeline.py)。
4.3 — Prompt realignment (agents.py): insufficient→signal, not force output。

## BATCH 5 — Integration Validation (CCD)

Synthetic negative + PILOT-01 + CAL/HOLD regression + pilot resume decision。

---

*CCD 签发：2026-05-11 | Owner approval required before Batch 1*
