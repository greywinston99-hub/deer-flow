# BIGDP2026.6V_2 — Asset Preparation Spec

**Purpose:** Define all materials that must be gathered BEFORE any code implementation begins.
**Rule:** No Batch B code work starts until Controller Resource Readiness Review passes.

---

## A0–A4: Resource Preparation Execution Model

### Role Boundaries

| Role | Responsibility | NOT Responsibility |
|:---|:---|:---|
| **Owner** | Provide candidate project scope; authorize access to locked feedback; confirm which projects can be used for calibration/stress/holdout; answer yes/no selection questions | Manually organize files; label data; write manifests; search directories |
| **Controller (CCD)** | Design resource selection strategy; define suitability scoring; recommend resource combinations; set readiness criteria; generate Owner questions; final review | Execute file scanning; modify code; run pipeline |
| **Claude Code** | Local file scanning (read-only); candidate inventory generation; manifest/CSV/JSON creation; file type identification; resource pack materialization; directory indexing | Modify DeerFlow code; start patches; run full pipeline; enter Batch B implementation |

### Five-Phase Execution

**A0 — Resource Selection Strategy (Controller)**
- Output: `resource_planning/RESOURCE_SELECTION_STRATEGY.md`
- Defines: what makes a project suitable for calibration vs stress vs holdout; which defect classes each project type can cover; scoring criteria
- No file scanning yet

**A1 — Local Resource Discovery & Inventory (Claude Code, read-only)**
- Output: `resource_planning/CANDIDATE_PROJECT_INVENTORY.csv`
- Actions: scan candidate directories; identify project folders; detect file types; generate manifest; mark confidence levels
- Constraints: read-only; no code changes; no pipeline execution; no guessing content from filenames alone

**A2 — Owner Selection & Authorization (Owner)**
- Output: answers to `resource_planning/RESOURCE_GAP_QUESTIONS_FOR_OWNER.md`
- Actions: select calibration/stress/holdout projects; authorize locked feedback access; confirm project availability
- Owner only answers yes/no/select questions — no forms, no data entry

**A3 — Resource Pack Materialization (Claude Code, read-only + file copy)**
- Output: populated `BIGDP2026_6V2/assets/` directories with manifests, indices, and (where authorized) copied/linked files
- Actions: generate asset pack manifests; copy or index authorized files into asset directories; create README per pack
- Constraints: no DeerFlow code modification; no pipeline execution

**A4 — Controller Resource Readiness Review (Controller)**
- Output: READY / NOT_READY verdict per Core Required Asset
- Gates Batch B start
- Updated `ACCEPTANCE_CHECKLIST.md` Section A0

### Current Phase: A0 (Resource Selection Strategy)
Claude Code may execute A1 (directory scanning + inventory) upon Controller authorization.
Claude Code MUST NOT enter Batch B code implementation.

---

## Required Asset Packages

### 1a. 法规资源包 — Minimal Regulatory Core（P0，必须 READY）
**路径：** `BIGDP2026_6V2/assets/01_regulatory/minimal_core/`
**内容：**
- MDR Annex XIV 临床评价要求（§1-§6）
- MEDDEV 2.7/1 Rev.4 临床评价指南
- ISO 14155:2020 临床试验规范（endpoint 定义、AE 分类）
**用途：** Endpoint 语义分类规则来源、数据溯源标准、AE vs treatment_failure 区分标准
**访问级别：** 可进入系统输入 → 用于 rulebook 规则引用
**优先级：** **Core Required** — Batch B 开始前必须 READY

### 1b. 法规资源包 — Extended Regulatory Pack（Supplementary，P2）
**路径：** `BIGDP2026_6V2/assets/01_regulatory/extended/`
**内容：**
- MDCG 2020-5 等效性指南 / MDCG 2020-6 临床证据要求 / MDCG 2020-13 临床评价评估报告模板
- ISO 14971:2019 风险管理（risk/benefit 框架）
- IMDRF 不良事件编码（terminology for AE classification）
**用途：** 补充规则细节、NB 审核标准参考
**访问级别：** 可进入系统输入
**优先级：** Supplementary — Batch C 前 READY 即可

### 2. 真实项目资源包（Real Project Pack）
**路径：** `BIGDP2026_6V2/assets/02_real_projects/`
**内容：**
- 至少 2 个已完成或进行中的 CER 项目的完整输入（含 IFU、源文献列表、检索记录、筛选记录）
- 其中至少 1 个是 iTClamp 类项目（因为 10 个工程师反馈中有多个来自该领域）
- 项目输出：系统生成的 CER 报告 + SOTA 报告 + 工程师标注的问题版本
**用途：** Gold set 建立、defect 复现、fixture 来源、regression lock 基线
**访问级别：** 可进入系统输入 → 但 locked feedback 版本不进入 Writer

### 3. 工程师反馈包（Engineer Feedback Pack）
**路径：** `BIGDP2026_6V2/assets/03_engineer_feedback/`
**内容：**
- 10 类问题的原始反馈文档（含具体 PMID、错误描述、正确值）
- 工程师标注的"正确版本"（如果已提供）
- 反馈来源项目上下文（设备类型、适应症、检索策略）
**用途：** Defect class mapping、gold label 建立、acceptance criteria 定义
**访问级别：** **Locked feedback** — 不进入 Writer 输入。用于校准和 test fixture 生成。

### 4. NB Feedback 包（Notified Body Feedback Pack）
**路径：** `BIGDP2026_6V2/assets/04_nb_feedback/`
**内容：**
- 如可用：NB 审核意见（CER review findings、nonconformity reports）
- NB 常见缺陷模式（defect patterns from notified body reviews）
- NB 对文献质量、数据溯源、endpoint 分类的期望标准
**用途：** 补充 defect classes 的分类维度、验收标准的 NB 视角
**访问级别：** **Locked feedback** — 用于校准系统标准，不进入项目输入

### 5. Final Accepted Files 包
**路径：** `BIGDP2026_6V2/assets/05_accepted_outputs/`
**内容：**
- 已通过工程师验收的 CER 最终版本（如有）
- 已通过验收的 SOTA 报告
- 已通过验收的文献筛选表
- 已通过验收的 endpoint 表
**用途：** Gold standard for comparison、regression lock baseline
**访问级别：** **Locked feedback** — 用于 calibration 和 acceptance baseline

### 6. Full-Text / Clinical Data 包
**路径：** `BIGDP2026_6V2/assets/06_fulltext_clinical/`
**内容：**
- 工程师反馈中涉及的 PMID 列表
- 每篇文献的 availability status：Full-text obtained / Abstract only / Unobtainable
- 已获得的 full-text PDF
- 从 full-text 中提取的 clinical data points（endpoint values, N, CI, p-values）
**用途：** Gold set for PMID-trace validation、data extraction accuracy verification
**访问级别：** Full-text PDF → 可进入系统输入；Clinical data extract → **Locked feedback**（用于校准，防止系统直接复制）

### 7. Expert Labels 包
**路径：** `BIGDP2026_6V2/assets/07_expert_labels/`
**内容（需要法规专家标注）：**
- Endpoint classification labels（每个 endpoint：safety/efficacy/performance/usability）
- AE vs treatment failure vs inadequate hemostasis labels（针对 iTClamp 类项目）
- Claim classification labels（clinical/performance/warning/non-clinical）
- Evidence support type labels（direct/indirect/equivalent/manufacturer/PMS）
- Conclusion strength labels（strong/moderate/limited/not_supported）
- Comparator benchmark acceptable range labels
- Denominator/subgroup correct assignment labels
**用途：** Gold labels for semantic test generation、rulebook accuracy validation
**访问级别：** **Locked feedback** — 仅用于 calibration 和 test fixture gold standard

### 8. Manual Search Gold Set
**路径：** `BIGDP2026_6V2/assets/08_manual_search_gold/`
**内容：**
- 工程师手动检索的完整记录（检索词、数据库、日期、命中数、筛选过程）
- 手动筛选的 inclusion/exclusion 决策（每篇文献的排除原因）
- 手动检索 vs AI 检索的对比矩阵
**用途：** Retrieval recall measurement、screening accuracy validation、检索审计 gate design
**访问级别：** **Locked feedback** — 用于校准检索和筛选 gate

### 9. Denominator / Subgroup Gold Labels
**路径：** `BIGDP2026_6V2/assets/09_denominator_gold/`
**内容：**
- 工程师反馈中涉及的 PMID 的正确 denominator 分配
- 每个数据点的正确样本量（总样本 vs 子组样本）
- 正确比例计算（分子/分母对应关系）
**用途：** Denominator checker design、semantic test for subgroup detection
**访问级别：** **Locked feedback** — 用于校准 denominator validator

### 10. SOTA Accounting Gold Ledger
**路径：** `BIGDP2026_6V2/assets/10_sota_accounting_gold/`
**内容：**
- 工程师核实的正确 SOTA 数字（文章数、检索词组数、records、fulltext、evidence count）
- SOTA 报告中每个数字的推导路径
- 与 AI 生成版本的差异对照表
**用途：** SOTA accounting consistency checker design
**访问级别：** **Locked feedback** — 用于校准 SOTA validator

---

## 资源用途分类

| 用途 | 资源包 |
|:---|:---|
| **可进入系统输入** | 法规资源包、真实项目输入、Full-text PDF |
| **仅用于校准（不进入 Writer）** | 工程师反馈包、NB feedback、Final accepted files、Clinical data extract、Expert labels、Manual search gold、Denominator gold、SOTA accounting gold |
| **Locked feedback** | 工程师反馈包、NB feedback、Final accepted files、Expert labels、Manual search gold、Denominator gold、SOTA accounting gold |
| **生成 semantic tests 的 gold standard** | Expert labels、Manual search gold、Denominator gold、SOTA accounting gold |

---

## 准备就绪判定

**Core Required Assets（Batch B 启动条件 — ALL 必须 READY）：**
- [ ] 01a Minimal Regulatory Core（MDR Annex XIV + MEDDEV + ISO 14155）
- [ ] 02 真实项目资源包（Engineer Feedback 关联项目）
- [ ] 03 工程师反馈包
- [ ] 06 Full-Text / Clinical Data 包
- [ ] 07a Minimal Endpoint / AE Expert Labels（至少 DC-6 相关）
- [ ] 08 Manual Search Gold Set
- [ ] 09 Denominator Gold Labels
- [ ] 10 SOTA Accounting Gold Ledger

**Supplementary Assets（Batch C 前 READY 即可，不阻塞 Batch B）：**
- [ ] 01b Extended Regulatory Pack（MDCG 2020-5/6/13, ISO 14971, IMDRF）
- [ ] 04 NB Feedback Pack
- [ ] 05 Final Accepted Files
- [ ] 07 Full Expert Labels（完整版）

**Batch B 启动条件：** 8 个 Core Required Assets 全部标记为 READY。
