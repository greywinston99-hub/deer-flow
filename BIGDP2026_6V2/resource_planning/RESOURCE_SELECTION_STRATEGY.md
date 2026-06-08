# BIGDP2026.6V_2 — Resource Selection Strategy

**Phase:** A0 — Resource Selection Strategy
**Controller:** BIGDP2026.6V_2 Controller
**Date:** 2026-06-08

---

## 1. Why Not "More Projects"?

本轮资源准备的目标不是积累项目数量，而是确保每个已知工程师反馈缺陷类都有对应的真实校准素材。10 类缺陷分布于 CER 全流程（S3 检索 → S5 数据提取 → S6 endpoint → S11 推理整合 → S12 Writer），单个项目通常只暴露其中 2–4 类。因此需要**按缺陷覆盖选择项目组合**，而非随机收集。

## 2. Project Suitability by Defect Class

| Defect Class | Best Project Type | Why |
|:---|:---|:---|
| DC-1 检索召回不足 | 已有工程师手动检索记录的项目 | 需要 manual search gold 对比 AI 检索 |
| DC-2 检索不可复现 | 系统运行过完整检索的项目 | 需要 search_run_registry 或检索日志 |
| DC-3 小样本误纳入 | 文献池中包含 case report (N<10) 的项目 | 需要筛选记录 + 原文 PMID |
| DC-4 数据不可溯源 | 系统生成了具体数据点的项目 | 需要 PMID 列表 + abstract/full-text |
| DC-5 全文不可得仍生成数据 | 文献池中有 abstract-only 的项目 | 需要 fulltext availability mapping |
| DC-6 endpoint 语义错误 | 设备有"装置弃用→替代疗法"场景的项目（如止血类） | iTClamp / 血管闭合器类 |
| DC-7 comparator benchmark 缺失 | 有明确替代疗法（止血带、缝线、缝钉）的项目 | 止血/闭合器类 |
| DC-8 上下文不一致 | 系统输出了多章节 CER 的项目 | 需要完整 CER output |
| DC-9 SOTA accounting 不一致 | 系统生成了 SOTA 报告的项目 | 需要 SOTA output + gold ledger |
| DC-10 denominator 混用 | 文献中有 subgroup analysis 的项目 | 需要 clinical data + denominator gold |

## 3. Project Categories

### Calibration Projects（3 个）
**用途：** 用于规则归纳、semantic test 生成、expert label 校准。
**特征：** 资料完整度高；至少有系统输出 + 工程师反馈或 accepted output；可对比 AI vs 正确版本。
**选择标准：** 资料完整度 > 60%；至少有 1 个项目的缺陷覆盖 ≥ 4 classes。

### Stress Projects（1–2 个）
**用途：** 测试系统在资料不完整/质量差的情况下的行为。
**特征：** fulltext 缺失多；边缘文献多；endpoint 语义模糊。
**选择标准：** 资料完整度 < 40%；用于验证 gate 是否正确 BLOCK（而非 PASS）。

### Holdout Projects（2 个）
**用途：** 最终 dry-run 验证。不在校准阶段使用，防止过拟合。
**特征：** 资料较完整；不同设备类型（避免与 calibration 项目相同 domain）。
**选择标准：** 资料完整度 > 50%；未被用于 calibration。

## 4. Suitability Scoring

每项目按以下维度评分（0–3 per dimension）：

| Dimension | 0 | 1 | 2 | 3 |
|:---|:---|:---|:---|:---|
| Input completeness | 无输入文件 | IFU only | IFU + RMF + GSPR | 完整 EP-001~005 |
| Pipeline output | 无输出 | 部分节点输出 | 完整 authoring artifacts | 完整 CER + SOTA + review |
| Engineer feedback | 无 | 口头反馈 | 标注了问题的文档 | 问题文档 + 正确值 |
| NB feedback | 无 | 简评 | 部分 NB findings | 完整 NB review + nonconformity |
| Accepted output | 无 | 旧版本 | 修订版本 | 最终验收版本含 diff |
| Fulltext availability | 无 PDF | < 30% PMID | 30–70% PMID | > 70% PMID |
| Unique defect coverage | 0 classes | 1–2 classes | 3–4 classes | 5+ classes |

**Score ≥ 14 → Calibration candidate；Score 6–13 → Stress candidate if fulltext < 30%；Score ≥ 10 → Holdout candidate if not used for calibration。**

## 5. Owner's Minimal Decisions

Owner 只需要做这些决策：
1. 从候选列表中确认 3 个 calibration、1–2 个 stress、2 个 holdout 项目
2. 授权 Controller + Claude Code 读取 locked feedback（NB/engineer）用于校准，确认这些不进入 Writer 输入
3. 授权 Claude Code 扫描指定项目目录并生成 manifest
4. 确认文件索引/引用模式（copy to assets/ vs symlink vs path reference only）
5. 确认是否有项目不能用于 calibration（例如客户合同限制）

## 6. What Blocks Batch B

以下任何一项缺失 → Batch B 无法启动：
- 无 calibration 项目含 engineer feedback → DC-1/2/4/5/8/9/10 无法校准
- 无 iTClamp/止血类项目 → DC-3/6/7 无法校准
- 无 manual search gold → DC-1/2 无法验证
- 无 fulltext availability data → DC-5 无法验证
- 无 denominator gold labels → DC-10 无法验证
- Owner 未授权 locked feedback 访问 → gold labels 无法建立
