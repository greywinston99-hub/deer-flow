# BIGDP2026.6V_2 — Absorption Workflow

**Purpose:** 8-step process to absorb project assets (regulatory, project, engineer feedback, expert labels) into system capabilities (code, gate, artifact, test, validator). This is NOT a CER execution workflow.

**Core principle:** 不允许吸收只停留在 Markdown / YAML / 文档。Hard acceptance 问题必须最终落地到 code / gate / artifact / test / writer constraint / validation proof。

---

## Step 0：前期资料准备（拆分为 6 个子步骤）

**这是资产吸收流程的一部分，不是 CER 执行流程，不是 Owner 手工拆包，也不是 Claude Code 代码 patch。**

### Step 0.1 — Candidate Discovery（Controller + Claude Code）
**Owner:** Controller 定义搜索范围 → Claude Code 执行本地扫描
**Input:** Candidate directory paths（`/Users/winstonwei/CER-RAG/`、deer-flow artifacts）
**Output:** Candidate project list with basic metadata
**Action:** Claude Code 扫描目录结构，识别项目文件夹，提取可推断的元数据。不猜测文件内容。

### Step 0.2 — Resource Inventory（Claude Code, read-only）
**Owner:** Claude Code
**Input:** Candidate project list from Step 0.1
**Output:** `CANDIDATE_PROJECT_INVENTORY.csv` with file-type detection, defect coverage candidates, suitability scoring, confidence levels
**Action:** 检测 IFU/RMF/GSPR/CER/SOTA/全文/NB feedback/工程师反馈/最终验收版本的文件存在性。标记 confidence 级别。

### Step 0.3 — Resource Suitability Scoring（Controller）
**Owner:** Controller
**Input:** Inventory CSV from Step 0.2
**Output:** `RECOMMENDED_RESOURCE_SET.md` with calibration/stress/holdout assignments
**Action:** Controller 根据覆盖缺陷类型、资料完整度、文件可访问性评分，提出推荐资源组合。

### Step 0.4 — Owner Selection（Owner）
**Owner:** Owner（最小输入）
**Input:** `RESOURCE_GAP_QUESTIONS_FOR_OWNER.md`（yes/no/select 问题）+ `RECOMMENDED_RESOURCE_SET.md`
**Output:** Owner 确认的项目列表 + 授权决定
**Action:** Owner 回答最少关键问题，确认 calibration/stress/holdout 分配，授权 locked feedback 访问。

### Step 0.5 — Resource Pack Materialization（Claude Code, read-only + file ops）
**Owner:** Claude Code
**Input:** Owner-authorized project list + `ASSET_PREPARATION_SPEC.md` 定义的资源包结构
**Output:** 资产包就绪：manifests、索引、文件副本/引用、README per pack
**Action:** Claude Code 生成每个资源包的 manifest，在授权范围内复制或索引文件到 `assets/` 目录。不得修改 DeerFlow 代码。

### Step 0.6 — Resource Readiness Review（Controller）
**Owner:** Controller
**Input:** 就绪的资源包
**Output:** READY / NOT_READY per Core Required Asset；更新 `ACCEPTANCE_CHECKLIST.md` A0
**Action:** Controller 逐项验证 8 个 Core Required Assets。全部 READY → 授权进入 Batch B。

**不能跳过的原因:** 没有 gold set 就没有校准基准；没有法规源就没有规则来源；没有 Owner 授权就不能访问 locked feedback。

---

## Step 1：工程师反馈 / NB Feedback 原子化

**Owner:** Controller → Defect Map
**Input:** Asset 03（工程师反馈）、04（NB feedback）
**Output:** `ENGINEER_FEEDBACK_DEFECT_MAP.md`（10 defect classes）
**Action:**
- 每个反馈拆成：原始描述 → CER 阶段 → 系统缺口 → 覆盖状态 → 升级方向
- 分类为：retrieval / screening / data extraction / endpoint / benchmark / consistency / accounting / denominator
- 每个 class 标记：hard acceptance (yes/no)、所需金标、runtime landing、fixture 需求
**不能跳过的原因:** 没有缺陷分类就无法设计针对性修复

---

## Step 2：证据重建与 Gold Set 建立

**Owner:** Controller / Domain Expert
**Input:** Asset 02（真实项目）、05（accepted outputs）、06（full-text）、08（manual search gold）、09（denominator gold）、10（SOTA gold）
**Output:** Gold sets for: retrieval recall, screening decisions, PMID traceability, full-text availability, denominator correctness, SOTA accounting
**Action:**
- 重建"正确版本"的检索记录、筛选决策、数据提取
- 建立 manual search vs AI search 对比矩阵
- 每个 PMID 标记：data exists in abstract? / fulltext available? / correct denominator? / correct endpoint class?
**不能跳过的原因:** gold set 是 semantic test 的基础；没有 gold set 的 test 只能测结构不能测正确性

---

## Step 3：专家判断标注

**Owner:** Domain Expert / Regulatory Reviewer
**Input:** Asset 07（expert labels spec）+ Step 2 gold sets
**Output:** Labeled data for: endpoint classification, claim classification, AE vs treatment_failure, comparator benchmark acceptability, conclusion strength
**Action:**
- 法规专家标注每个 endpoint 的正确语义类
- 标注每个 claim 的正确分类和证据支撑水平
- 标注 AE / treatment_failure / inadequate_hemostasis 区分
- 标注 comparator benchmark acceptable range
**不能跳过的原因:** 专家标注是规则归纳的输入；没有标注的规则是臆测

---

## Step 4：规则 / SOP / 决策表归纳

**Owner:** Controller + Domain Expert
**Input:** Step 1 defect map + Step 2 gold sets + Step 3 expert labels + Asset 01 法规
**Output:** New rules in `EXPERT_REASONING_RULEBOOK.yaml`、new decision tables、updated SOP
**Action:**
- 从 gold set 中归纳检索筛选规则（N<10 → EXCLUDE, 无检索词 → REWORK）
- 从法规中归纳 endpoint 语义规则（ISO 14155 AE definition → classification logic）
- 从 expert labels 归纳 comparator benchmark 规则（有数据必须有 CI）
- 从工程师反馈归纳 data traceability 规则（无 PMID → BLOCKED）
- 新增 decision tables: `SCREENING_RULES.yaml`, `ENDPOINT_SEMANTICS.yaml`, `DATA_TRACEABILITY_RULES.yaml`
**不能跳过的原因:** 规则是 runtime 的输入；规则必须来自 gold evidence，不能凭空编写

---

## Step 5：Fixtures / Semantic Tests 生成

**Owner:** Controller → Test Design
**Input:** Step 1 defect classes + Step 2 gold sets + Step 4 rules
**Output:** JSON fixtures + pytest test files
**Action:**
- 每个 defect class → 至少 1 个 fixture（从真实项目场景提取）
- 每个 fixture → 1 个 semantic test（assert 预期行为）
- Fixture 格式：输入 state snapshot + 预期 gate/validator 输出
**不能跳过的原因:** fixture-driven tests 是 acceptance 的证据；没有 test 的规则是 dead code

---

## Step 6：Runtime Landing 设计

**Owner:** Controller → Implementation Spec
**Input:** Step 4 rules + Step 5 tests
**Output:** Per-defect implementation spec（哪个文件、哪个函数、哪个 gate、什么接口）
**Action:**
- 每个 defect class 指定 runtime landing point
- 设计 gate 接口：输入 state keys、输出 gate report fields、路由逻辑
- 设计 validator 接口：输入数据、输出 validation report
- 确认与现有 graph / gate 系统的兼容性（不破坏 G46 链路）
**不能跳过的原因:** 没有 landing spec 的规则是漂浮物；runtime integration 是吸收流程的硬要求

---

## Step 7：最终落地为代码能力

**Owner:** Claude Code Implementer
**Input:** Step 6 implementation specs + Step 4 rules + Step 5 tests
**Output:** Modified `gates.py`, `graph.py`, `pipeline.py`；New `validators/`, `classifiers/` modules；New test files
**Action:**
- Clause Code 实现：gates, validators, classifiers, checkers
- 接入 DAG：新 gate 注册到 graph、edge 正确
- 运行所有 test（existing + new）→ all pass
- **这是吸收流程的终点。**
**不能跳过的原因:** 一切吸收最终必须落地为可执行的代码

---

## Step 8：回归验证与能力锁定

**Owner:** Controller → Final Acceptance
**Input:** Step 7 code + all tests + dry-run output
**Output:** Updated `ACCEPTANCE_CHECKLIST.md`（全部 PASS）、`PHASE_STATUS.md`（ACCEPTED）、Regression lock
**Action:**
- 运行 full test suite（BIGDP2026.6 500 tests + V_2 new tests）→ all pass
- 端到端 dry-run 至少 1 个真实项目
- 10 defect classes 逐项复验：不复发
- Controller 签字
**不能跳过的原因:** 没有回归验证的升级是不可信的
