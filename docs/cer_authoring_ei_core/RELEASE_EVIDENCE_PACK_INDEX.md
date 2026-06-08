# RELEASE_EVIDENCE_PACK_INDEX

> CCD 签发 | 2026-05-10 | V2.3 Release Evidence

## 一、Calibration Evidence

| 项目 | Baseline | Gate Pass | Key Artifacts |
|---|---|---|---|
| CAL-001 | PRE-FREEZE | 4 gates failed (original) | Intake audit + lineage note B |
| CAL-002 | V2.3 | 43/44 (97.7%) | 3-run cross-version comparison |
| CAL-003 | V2.3 | 43/44 (97.7%) | 6-version defect arc (0%→97.7%) |

## 二、Holdout Evidence

| 项目 | Baseline | Gate Pass | Key Artifacts |
|---|---|---|---|
| HOLD-001 | V2.3 | 43/44 (97.7%) | 76 locked files classified |
| HOLD-002 | V2.3 | 42/44 (95.5%) | 157 locked files classified |

## 三、Cross-Project Validation

| Gate | CAL-001 | CAL-002 | CAL-003 | HOLD-001 | HOLD-002 |
|---|---|---|---|---|---|
| G30 | ❌→✅ | ✅ | ✅ | ✅ | ✅ |
| G33 | ❌→✅ | ✅ | ✅ | ✅ | ✅ |
| G38 | ❌→✅ | ✅ | ✅ | ✅ | ✅ |
| G1c/G1d | ✅ | ✅ | ✅ | ✅ | ✅ |

## 四、CCD Controller Files

41 files in `/Users/winstonwei/CER-RAG/CER编写系统升级前-CCD/` covering:
- Project master status
- Phase gate register
- Baseline version ledger
- Calibration asset ledger
- Decision log (43 entries)
- 8 Phase acceptance audit reports
- 4 intake audit reports
- Aggregate root cause matrices
- Repair briefs
- Readiness assessments

## 五、Codex Deliverables

- phase0_contracts.py (Phase 0)
- calibration_delta_analyzer.py (Phase 0.2)
- pipeline.py IFU/device_type/SOTA/BR/attachment fixes
- 49+ tests

---

*CCD 签发：2026-05-10*
