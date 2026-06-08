# BIGDP2026.6 — Phase 7 Dry-Run Procedure

**Purpose:** Validate BIGDP2026.6 on a real CER project before production release.
**Prerequisite:** BIGDP2026.6 ACCEPTED by Controller (D-008).
**Executor:** Controller or delegated CER engineer.

---

## Step 1: Select Test Project

Choose ONE real CER project:
- Class IIa or IIb device (not Class III for initial dry-run)
- Complete intake package available (RMF + IFU + TD)
- Preferably a project that has been previously processed (pre-upgrade baseline exists for comparison)

---

## Step 2: Pre-Run Verification

```bash
cd /Users/winstonwei/Documents/Playground/deer-flow
bash BIGDP2026_6/deploy_verify.sh
```

Must show: `ALL 25 CHECKS PASSED`

---

## Step 3: Run Authoring Pipeline

```bash
cd /Users/winstonwei/Documents/Playground/deer-flow
.venv/bin/python3 backend/scripts/run_cer_authoring.py \
  --project <project_dir> \
  --artifact-root <project_dir>/artifacts
```

---

## Step 4: Verify G46 Writer Release Board

After the pipeline reaches G46:

1. Check `pre_writer_readiness_gate_report.status`:
   - Must be `PASS` (not `REWORK_REQUIRED` or `BLOCKED`)
   - If `REWORK_REQUIRED`: check which conditions failed
   - If `BLOCKED`: stop and diagnose — this should not happen for a standard project

2. Verify all 3 expert ledgers are populated:
   ```bash
   cat <project_dir>/CER_EVIDENCE_PACKAGE/CER_INPUT_PACKAGE.json | python3 -c "
   import json, sys
   pkg = json.load(sys.stdin)
   p4 = pkg.get('phase4_evidence_consolidation', {})
   print('CER_REASONING_LEDGER claims:', len(p4.get('cer_reasoning_ledger', {}).get('claims', [])))
   print('IFU_EVOLUTION_LEDGER claims:', len(p4.get('ifu_claim_evolution_ledger', {}).get('claims', [])))
   print('BENCHMARK_TRACE endpoints:', len(p4.get('benchmark_derivation_trace', {}).get('endpoints', [])))
   "
   ```

---

## Step 5: Verify Claude Code Handoff

```bash
python3 BIGDP2026_6/repairs/writer_package_validator.py \
  <project_dir>/CER_EVIDENCE_PACKAGE/CER_INPUT_PACKAGE.json
```

Must exit 0 with: `CER_INPUT_PACKAGE validation PASSED — Writer may proceed.`

---

## Step 6: Spot-Check Expert Reasoning Quality

Open `CER_REASONING_LEDGER` in the package and verify:

1. Each claim has `conclusion_strength` — not null, not placeholder
2. Claims with `evidence_support_type: indirect` have `conclusion_strength ≤ moderate`
3. Claims with `evidence_support_type: manufacturer` have `conclusion_strength: limited`
4. `gap_disposition` is set for all claims
5. `IFU_CLAIM_EVOLUTION_LEDGER` shows 5-stage evolution per claim
6. `BENCHMARK_DERIVATION_TRACE` has `acceptability_rationale` per endpoint

---

## Step 7: Compare Against Pre-Upgrade Baseline

If a pre-upgrade run exists:
1. Compare `CER_INPUT_PACKAGE.json` structure — new ledger keys present
2. Compare `package_schema_version` — must be `"1.0.0"`
3. Compare G46 report — conditions list now includes `CER_REASONING_LEDGER`, `IFU_CLAIM_EVOLUTION_LEDGER`, `BENCHMARK_DERIVATION_TRACE`

---

## Step 8: Record Results

Document in:
```
BIGDP2026_6/PHASE7_DRY_RUN_RESULTS_<project>_<date>.md
```

Include:
- Project name and device class
- Pipeline run time
- G46 status and per-condition breakdown
- Ledger quality assessment (Step 6)
- Handoff validator result
- Any anomalies or regressions
- Comparison against pre-upgrade baseline (if available)

---

## Acceptance Criteria (J Section)

| Item | Check |
|:---|:---|
| J.1 | Real CER project selected |
| J.2 | Full pipeline executed |
| J.3 | G46 returns PASS only when conditions genuinely met |
| J.4 | CER_REASONING_LEDGER populated with non-placeholder data |
| J.5 | IFU_CLAIM_EVOLUTION_LEDGER traces ≥3 claims through 5 stages |
| J.6 | BENCHMARK_DERIVATION_TRACE has per-endpoint acceptability rationale |
| J.7 | Exported package passes Claude Code handoff validator |
| J.8 | Output quality compared against pre-upgrade baseline |
| J.9 | No regression in existing test paths |
| J.10 | All P0/P1/Ledger items PASS or DEFERRED with rationale |
