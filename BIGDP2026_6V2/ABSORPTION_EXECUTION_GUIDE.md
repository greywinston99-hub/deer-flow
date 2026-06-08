# BIGDP2026.6V_2 — 吸收执行与能力判断指南

**前提：** Owner 已按 `OWNER_EXTRACTION_SPEC.md` 完成 15–20 个项目的资产提取，产出物放在 `assets/` 目录下。
**用途：** 回答三个问题——怎么吸收、吸收到什么程度、怎么判断系统能力。

---

## 一、怎么吸收：从资产到代码的 6 步链路

资产不是直接"喂给系统"的。每条资产经过 6 步转化才成为系统能力。

### 链路图

```
assets/ 目录中的 CSV/原文
        │
        ▼
Step 1 ─ 质量门验证（Controller）
        │  11 项检查：source_quote 非空、holdout 未污染、duplicate 检查...
        │  产出：PASS / FAIL per CSV
        ▼
Step 2 ─ 资产分类（Claude Code，read-only）
        │  每条数据标记：absorption_type / closure_level / locked_boundary
        │  产出：ASSET_ABSORPTION_CONTRACT.csv（回填完成）
        ▼
Step 3 ─ 规则归纳（Claude Code + Controller review）
        │  从 calibration 项目的 gold/expert 数据中归纳确定性规则
        │  产出：新增 rulebook entries + decision table updates
        │  检查：每条规则可追溯到至少 1 个 calibration 项目的具体数据点
        ▼
Step 4 ─ Fixture 生成（Claude Code）
        │  从正例/负例中生成 JSON fixtures
        │  产出：每个 DC ≥1 个 fixture（正例 + 负例）
        │  检查：fixture 中的 PMID/数值可追溯到资产 CSV 中的具体行
        ▼
Step 5 ─ Runtime 落地（Claude Code）
        │  fixture → test → code → gate/validator/classifier
        │  产出：修改后的 gates.py / pipeline.py / 新 validator 模块
        │  检查：所有新 tests pass + 基线 tests 不退化
        ▼
Step 6 ─ Writer QA + Holdout 验证（Claude Code + Controller）
        │  holdout 项目 dry-run → 检查 DC 是否复发
        │  产出：validation report + scorecard
```

### 每步谁做、产出什么

| 步骤 | 执行者 | 输入 | 产出 | 验收方式 |
|:--:|:---|:---|:---|:---|
| 1 | Controller | assets/ CSV 文件 | 质量门 PASS/FAIL | 11 项检查全部 PASS 或标记 exemption |
| 2 | Claude Code | 通过质量门的 CSV | ASSET_ABSORPTION_CONTRACT.csv | 每条数据有 absorption_type |
| 3 | Claude Code | calibration 数据 | rulebook 更新 | 新规则可追溯到具体数据点 |
| 4 | Claude Code | 正例+负例 | JSON fixtures | fixture 值可追溯到 CSV 行 |
| 5 | Claude Code | fixtures + rules | 代码 + tests | pytest 全绿 |
| 6 | Claude Code + Controller | holdout 项目 | validation report | DC 不复发 |

### 什么不能跳

- **Step 1 不能跳。** 未通过质量门的数据进入吸收 = garbage in, garbage out。
- **Step 4 不能跳。** 没有 fixture 的规则 = 无法测试的规则 = 死规则。
- **Step 6 不能跳。** 没有 holdout 验证的升级 = 不知道是否过拟合。

---

## 二、吸收到什么程度：DC 闭合层级

不是所有 DC 都能达到同样的吸收深度。用 6 级闭合层级衡量。

### 闭合层级定义

| 层级 | 含义 | 能支撑的 score | 需要什么证据 |
|:---|:---|:--:|:---|
| **FULLY_CLOSED** | gold/expert 资产 + rule + fixture + test + runtime + holdout 验证 | 满分 | 5 项证据全部具备 |
| **DERIVED_VALIDATION** | NB feedback 或 accepted CER 反向推导的规则 | 近满分（−1~2 分） | source 可追溯 + before/after 存在 + holdout 验证通过 |
| **HEURISTIC_ONLY** | 从 CLAUDE.md 等归纳的通用规则，无 project-specific gold | 中等（−2~4 分） | 规则有法规依据 + synthetic fixture 测试通过 |
| **SYNTHETIC_ONLY** | 只有 synthetic fixture，无真实项目数据 | 低分（−4~6 分） | fixture 逻辑正确但未在真实数据上验证 |
| **ASSET_BLOCKED** | 资产缺失无法闭合 | 0 分（或仅结构分） | — |
| **NOT_IMPLEMENTED** | 未开始 | 0 分 | — |

### 每个 DC 的目标闭合层级

| DC | 理想目标 | 最可能实际达到 | 取决于什么资产 |
|:---|:---|:---|:---|
| DC-1 检索召回 | FULLY_CLOSED | HEURISTIC_ONLY | Manual search gold 不存在→无法 FULLY_CLOSED |
| DC-2 检索可复现 | FULLY_CLOSED | FULLY_CLOSED | 这是结构性检查，不依赖 gold labels |
| DC-3 筛选规则 | FULLY_CLOSED | DERIVED_VALIDATION | Screening gold labels NOT_FOUND→可从 NB feedback 反向推导 |
| DC-4 PMID 溯源 | FULLY_CLOSED | DERIVED_VALIDATION | PMID verification set NOT_FOUND→从 accepted CER 中反推 |
| DC-5 全文策略 | FULLY_CLOSED | FULLY_CLOSED | Fulltext mapping 可补充 |
| DC-6 Endpoint 语义 | FULLY_CLOSED | DERIVED_VALIDATION | Expert labels PARTIAL→从 NB comments + CLAUDE.md 补充 |
| DC-7 Comparator | FULLY_CLOSED | HEURISTIC_ONLY | Comparator gold NOT_FOUND→CI 计算是结构性，但 range 需要 gold |
| DC-8 跨章节一致性 | FULLY_CLOSED | FULLY_CLOSED | 结构性检查，不依赖 gold labels |
| DC-9 SOTA accounting | FULLY_CLOSED | DERIVED_VALIDATION | SOTA gold ledger NOT_FOUND→可从 CER 原文中反推数字 |
| DC-10 分母 | FULLY_CLOSED | HEURISTIC_ONLY | Denominator gold NOT_FOUND→可从已知错误模式 + 重算验证 |
| DC-11 Writer | FULLY_CLOSED | DERIVED_VALIDATION | Writer output PARTIAL→用 historical CER text 代替 |

### 吸收程度判定

吸收完成后，用闭合层级矩阵总结：

```
DC-1:  HEURISTIC_ONLY    (manual search gold NOT_FOUND)
DC-2:  FULLY_CLOSED      (结构性检查)
DC-3:  DERIVED_VALIDATION (NB feedback 反向推导)
...
```

全部 11 个 DC 的闭合层级决定了最终 score——见 `SCORE_CAP_RULES.md`。

---

## 三、怎么判断系统能力：三层判断

### 第一层：代码与测试层（Batch B/C/D 每步验收）

**问题：** 代码写对了吗？

**判断方式：**
- 每个 DC 对应的 tests 全部 pass
- 基线 BIGDP2026.6 tests 不退化（542→不减少）
- 新代码有 runtime wiring（被 gates.py / graph.py 调用）

**何时判断：** 每个 Batch 完成时。产出 `BATCH_X_TEST_REPORT.md`。

### 第二层：闭合层级层（Batch B/C/D 汇总）

**问题：** 每个 DC 被吸收到什么深度？

**判断方式：**
- 11 个 DC 的闭合层级矩阵
- 每个 DC 有 rule + fixture + test + runtime + (writer QA 或 holdout) 中的几项

**何时判断：** Batch D 完成时。产出 `DC_CLOSURE_LEVEL_MATRIX.csv`。

### 第三层：能力分数层（Final Scorecard）

**问题：** 系统整体达到了什么专家能力水平？

**判断方式：**
- 12 维度 × 100 分 scorecard
- 每个维度的分数 = 满分 × (该维度 DC 的闭合层级折扣)
- 分数必须有证据支撑——不能凭空给分

**何时判断：** Final closeout。产出 `EXPERT_CAPABILITY_SCORECARD.md`。

### 能力判断的硬规则

| 如果... | 则... |
|:---|:---|
| 任何 DC 标记为 FULLY_CLOSED 但没有 holdout 验证 | 降级为 DERIVED_VALIDATION |
| 任何 DC 标记为 DERIVED_VALIDATION 但没有 source 追溯 | 降级为 HEURISTIC_ONLY |
| 任何 DC 标记为 HEURISTIC_ONLY 但没有 synthetic fixture test | 降级为 SYNTHETIC_ONLY |
| 任何 DC 没有 test | 标记为 ASSET_BLOCKED 或 NOT_IMPLEMENTED |
| holdout 项目验证中任何 DC 复发 | 该 DC 降一级 |
| 基线测试退化 | 停止，修复回归 |

### 最终能力判定语句

系统能力不是一句话，而是一个结构化结论：

```
BIGDP2026.6V_2 系统专家能力：
- Score: 78/100 (Path B)
- FULLY_CLOSED: 3/11 DC (DC-2, DC-5, DC-8)
- DERIVED_VALIDATION: 5/11 DC (DC-3, DC-4, DC-6, DC-9, DC-11)
- HEURISTIC_ONLY: 2/11 DC (DC-1, DC-7, DC-10)
- ASSET_BLOCKED: 1/11 DC (DC-1 — manual search gold NOT_FOUND)
- Holdout 验证: 通过 (2/2 holdout 项目无 DC 复发)
- 已知限制: Endpoint 语义分类为 heuristic（缺 expert labels）；检索 recall 无法 gold-verify（缺 manual search）
- 下一次升级建议: 获取 ≥3 个项目的 manual search gold + endpoint expert labels → 可冲击 90+
```

---

## 四、吸收执行检查清单

从资产提取完成到吸收完成，逐项打勾：

### 质量门（Controller）

- [ ] Q1. 所有 CSV 的 source_file_path 非空
- [ ] Q2. gold/expert 级别数据的 source_quote_or_anchor 非空
- [ ] Q3. 所有数据有 evidence_level
- [ ] Q4. 所有数据有 dataset_role（calibration/stress/holdout）
- [ ] Q5. holdout 项目数据未出现在 calibration 规则源中
- [ ] Q6. 同一 PMID/endpoint/claim 无重复冲突
- [ ] Q7. DC 覆盖配额全部达到（Section 三）

### 规则归纳（Claude Code → Controller review）

- [ ] R1. 每个 DC 至少有 1 条新规则
- [ ] R2. 每条规则可追溯到 ≥1 个 calibration 项目的具体数据点
- [ ] R3. 规则不含 locked feedback 的具体内容
- [ ] R4. Controller 审阅通过

### Fixture 生成（Claude Code）

- [ ] F1. 每个 DC ≥1 个正例 fixture + ≥1 个负例 fixture
- [ ] F2. Fixture 中的 PMID/数值可追溯到 CSV 行
- [ ] F3. Fixture 不包含 holdout 项目数据
- [ ] F4. Synthetic fixture 标记为 synthetic

### Runtime 落地（Claude Code）

- [ ] T1. 所有新 tests pass
- [ ] T2. 基线 tests 不退化
- [ ] T3. 新代码被 gates.py 或 graph.py 调用（grep 确认）
- [ ] T4. Architecture fit check：新代码未破坏 G46 链路

### Holdout 验证（Claude Code + Controller）

- [ ] H1. ≥2 个 holdout 项目 dry-run 完成
- [ ] H2. 11 个 DC 在 holdout 项目中无复发
- [ ] H3. 如有复发 → 对应 DC 降一级 + 记录原因
- [ ] H4. Holdout 验证报告完成

### 最终（Controller）

- [ ] FINAL1. Scorecard 完成（12 维度有证据支撑）
- [ ] FINAL2. DC 闭合层级矩阵完成
- [ ] FINAL3. 能力判定语句完成
- [ ] FINAL4. PHASE_STATUS 更新为最终状态
- [ ] FINAL5. 如分数 < 100 → 列出阻塞项和下一次升级建议
