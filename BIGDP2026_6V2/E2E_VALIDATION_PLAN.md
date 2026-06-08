# BIGDP2026.6V_2 — E2E Validation Plan

**Status:** READY | **Prerequisites:** ALL MET

---

## Pre-Flight (已完成)

- [x] 562/562 tests pass
- [x] 25/25 deploy checks pass
- [x] Working tree clean
- [x] All code committed

---

## E2E Validation Steps

### Step 1: Select Validation Project
Choose one:
- **Option A:** PROJECT_042 (安徽巨目, Class IIa 验光仪) — IFU/RMF/GSPR 齐全
- **Option B:** Synthetic VasoSeal Pro X (Class IIb) — 已有一轮试运行

### Step 2: Run Pipeline
```bash
cd /Users/winstonwei/Documents/Playground/deer-flow
.venv/bin/python3 BIGDP2026_6/end_to_end_synthetic_run.py
```

### Step 3: Verify Outputs
Check generated files for:
- `CER_REASONING_LEDGER` — 每条声明有 conclusion_strength
- `IFU_CLAIM_EVOLUTION_LEDGER` — 5 阶段演变，营销语言标记
- `BENCHMARK_DERIVATION_TRACE` — 每终点有 acceptability_rationale
- `G46_REPORT` — 0 个无声 PASS
- `CER_INPUT_PACKAGE` — 3 个账本嵌入，package_schema_version: 1.0.0

### Step 4: Run Validators
```bash
python3 BIGDP2026_6/repairs/writer_package_validator.py \
  BIGDP2026_6/phase7_dry_run_output/CER_INPUT_PACKAGE.json
```

### Step 5: Expert Logic Checks
- [ ] Weak evidence → not strong (DC-6)
- [ ] IFU overclaim → flagged (DC-3)
- [ ] Fallback benchmark → limitation (DC-7)
- [ ] Denominator n_events ≤ n_total (DC-10)
- [ ] Pivotal without fulltext → BLOCKED (DC-5)
- [ ] N<10 case report → excluded (DC-3)

### Step 6: Record Results
Create `E2E_VALIDATION_RESULTS.md` with pass/fail per check.
