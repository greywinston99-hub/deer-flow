# BIGDP2026.6V_2 — Recommended Resource Set

**Phase:** A0 — Controller recommendation (NOT yet Owner-authorized)
**Status:** PROPOSED — awaiting Owner selection (A2)

---

## Golden Feedback Pack（1 个）

### GOLD-001: 南驰 iTClamp Engineer Feedback Pack
**候选项目：** CAND-001 — `108.江苏南驰`
**推荐理由：**
- 工程师反馈中明确提到了 iTClamp、具体 PMID（31539432, 32209132, 30635996）
- Strongest Golden Feedback Pack candidate; may cover all 10 defect classes if Owner confirms source and deep scan verifies artifacts
- 有工程师反馈原始文档 + 具体错误描述
- 止血/闭合器类设备 — endpoint 语义、comparator benchmark、denominator 场景最丰富
**需要 Owner 确认：**
- 该项目确实是工程师反馈来源
- 授权读取工程师反馈原始文档
- 授权读取该项目完整输入（IFU/RMF/GSPR/literature）
**Current confidence:** MEDIUM（文件夹结构确认，内容未采样）
**缺失资料：**
- Manual search gold（需要工程师提供检索记录）
- Denominator gold labels（需要工程师标注）
- SOTA accounting gold ledger（需要工程师核实）
- Expert endpoint labels（需要 Domain Expert 标注）
**是否可先作为候选：** ✅ 是。高优先级深扫描。

---

## Calibration Projects（3 个）

### CAL-001: CER-PJT-0502（DeerFlow Pipeline 项目）
**候选项目：** CAND-003
**推荐理由：**
- 有完整 EP-001~005 输入结构 + round_001/artifacts
- DeerFlow pipeline 完整运行过 — 有 search artifacts、CER_REVIEW_REPORT
- 适合验证 DC-1/2（检索 recall + reproducibility）、DC-8/9（consistency + SOTA accounting）
**需要 Owner 确认：** 可用于 calibration
**Current confidence:** HIGH（content sampled — EP structure confirmed）
**缺失资料：** Engineer feedback（未发现该项目的工程师反馈文件）；SOTA gold ledger
**缺陷覆盖：** DC-1, DC-2, DC-4, DC-8, DC-9

### CAL-002: 北京海杰亚（微波消融）
**候选项目：** CAND-002
**推荐理由：**
- 不同设备类型（消融 vs 止血）— 验证系统在不同 clinical domain 的表现
- 有 PROJECT_FILE_MANIFEST.csv + STAGING — 资料较完整
- 消融设备 endpoint 语义清晰（消融成功率 / 并发症率）— 适合 DC-6 calibration
**需要 Owner 确认：** 可用于 calibration
**Current confidence:** MEDIUM（manifest 结构确认，设备类型推断）
**缺失资料：** Pipeline output、engineer feedback、expert labels
**缺陷覆盖：** DC-4, DC-5, DC-6, DC-8, DC-10

### CAL-003: CER-PJT-0424
**候选项目：** CAND-004
**推荐理由：**
- 与 CAL-001 类似但有不同 project_id — 可能不同设备类型
- 提供第二个 pipeline 运行项目的 calibration baseline
**需要 Owner 确认：** 设备类型是什么？可用于 calibration？
**Current confidence:** MEDIUM（EP 结构确认，内容未知）
**缺失资料：** Pipeline round artifacts、engineer feedback、device type
**缺陷覆盖：** DC-1, DC-2, DC-4, DC-8, DC-9

---

## Stress Projects（2 个）

### STR-001: CER-D11 Pilot Smoke
**候选项目：** CAND-010
**推荐理由：**
- PILOT/SMOKE — 暗示资料可能不完整，适合 stress test
- 测试系统在输入不完整时的 gate 行为（是否正确 BLOCK 而非 PASS）
**需要 Owner 确认：** 该项目中输入完整度如何？是否适合 stress？
**Current confidence:** LOW（仅文件夹名称推断）
**缺失资料：** 几乎全部
**缺陷覆盖：** DC-4, DC-5, DC-10（通过注入不完整数据模拟）

### STR-002: Stress candidate from remaining 183 projects
**推荐理由：**
- 从 188 个项目中选取一个资料完整度 < 40% 的作为 stress test
- 设备类型应与 calibration 项目不同（避免 domain overfitting）
**需要 Owner 确认：** 推荐一个"资料不全但已知设备类型"的项目
**Current confidence:** N/A（未选定）
**缺失资料：** 待选定后评估

---

## Holdout Projects（2 个）

### HLD-001: CER-PJT-0003
**候选项目：** CAND-005
**推荐理由：**
- 不同于 CAL-001/003 的 project_id — 避免 calibration/holdout 重叠
- 有 EP 输入结构 — 资料可用于最终 dry-run
**需要 Owner 确认：** 设备类型 + 可用于 holdout
**Current confidence:** MEDIUM
**缺陷覆盖：** DC-4, DC-8, DC-10

### HLD-002: CER-D6 Real Project
**候选项目：** CAND-011
**推荐理由：**
- REAL-PROJECT iteration — 暗示是较成熟的真实项目
- 适合作最终 dry-run 验证
**需要 Owner 确认：** 可用作 holdout？
**Current confidence:** LOW（仅文件夹名称推断）
**缺陷覆盖：** 待确认

---

## Regulatory Pack

| Pack | Priority | Status |
|:---|:---|:---|
| Minimal Regulatory Core（MDR Annex XIV + MEDDEV + ISO 14155） | Core | 待 Owner 确认路径或由 Controller 从公开源获取 |
| Extended Regulatory Pack（MDCG 2020-5/6/13 + ISO 14971 + IMDRF） | Supplementary | 同上 |

---

## Summary

| Set | Count | Candidates | Confidence |
|:---|:---:|:---|:---|
| Golden Feedback Pack | 1 | CAND-001 | MEDIUM |
| Calibration | 3 | CAND-003, CAND-002, CAND-004 | 1 HIGH, 2 MEDIUM |
| Stress | 2 | CAND-010 + TBD | 1 LOW, 1 TBD |
| Holdout | 2 | CAND-005, CAND-011 | 1 MEDIUM, 1 LOW |
| **Total** | **8** | | |

**这些是推荐，不是已确认授权。所有项目需 Owner 在 A2 阶段确认。**
