# EVIDENCE SYNTHESIS METHOD POLICY

> CCD 签发 | 2026-05-12 | Evidence Intelligence Core Upgrade

## 一、三种合成方法

| 方法 | 适用条件 | 输出 |
|---|---|---|
| **Narrative Synthesis** | 异质性过高、<3 个可比研究、非量化端点 | 结构化叙述 + 方向性结论 |
| **Benchmark Synthesis** | ≥3 个可比研究、同质端点、可量化 | 范围/分布 + 中位数/均值 + 异质性描述 |
| **No Synthesis** | 仅有 1-2 个研究、严重冲突未解决、证据不可比 | 逐项列出 + 不聚合结论 |

---

## 二、方法选择流程

```text
输入: evidence 集合 (per endpoint_cluster)
  ↓
Step 1: 排除 NOT_ADMISSIBLE 证据
  ↓
Step 2: 如剩余 <1 → No Synthesis，标记为 insufficient_data
  ↓
Step 3: 检查 CRITICAL conflict → 如有 → No Synthesis，标记冲突
  ↓
Step 4: 检查可比性（endpoint, timepoint, population, procedure 维度）
  ↓
Step 5: 查看可比证据数
  ≥3 + 同质 → Benchmark Synthesis
  ≥1 + 异质 → Narrative Synthesis
  1-2 → No Synthesis（逐项列出）
```

---

## 三、Narrative Synthesis（叙述性合成）

### 3.1 适用条件

- 异质性过高（different populations, procedures, timepoints）
- < 3 个可比研究
- 端点为非量化类型（qualitative, safety events without rates）
- 证据类型混合（literature + clinical data + PMS）

### 3.2 输出格式

```text
narrative_synthesis:
  endpoint_cluster_id: str
  synthesis_method: "narrative"
  evidence_count: int
  direction_consensus: str       # consistent_positive / consistent_negative / mixed / unclear
  heterogeneity_description: str # 异质性来源
  key_findings: [str]            # 主要发现列表
  limitations: [str]             # 合成限制
  conclusion_statement: str      # 结构化结论（非自由文本）
```

### 3.3 规则

- 必须显式描述异质性来源
- 方向性结论必须标注 confidence（narrative_confidence: high/medium/low）
- 不得声称定量结论（如「平均成功率」）

---

## 四、Benchmark Synthesis（基准合成）

### 4.1 适用条件

- ≥3 个可比研究
- 端点可量化（有 value_numeric + value_unit）
- endpoint_cluster 内同质性可接受（相似 population, procedure, timepoint）
- 无 CRITICAL 冲突

### 4.2 输出格式

```text
benchmark_synthesis:
  endpoint_cluster_id: str
  synthesis_method: "benchmark"
  evidence_count: int
  benchmark_range: {min: float, max: float}
  benchmark_median: float
  benchmark_mean: float
  benchmark_iqr: {q1: float, q3: float}
  heterogeneity_index: float    # I² 或 IQR/median 比值
  subject_device_value: float|null
  subject_device_position: str  # above_benchmark / within_benchmark / below_benchmark
  benchmark_confidence: str     # high / medium / low
```

### 4.3 规则

- 不得对异质性过高（I² > 75% 或 IQR/median > 0.5）的证据做 benchmark
- 不得对不同 source_type 的证据不加区分地混合
- benchmark_confidence 按 evidence 数量和质量决定（见 SOTA spec）

---

## 五、No Synthesis（不合成）

### 5.1 适用条件

- 仅有 1-2 个研究
- 存在未解决的 CRITICAL 冲突
- 证据不可比（不同 device type, population, era）
- 仅有 low-confidence 事实

### 5.2 输出格式

```text
no_synthesis:
  endpoint_cluster_id: str
  synthesis_method: "none"
  reason: str                   # insufficient_count / unresolved_conflict / incomparable / low_quality
  individual_findings: [{evidence_id, finding_summary}]
  why_not_synthesized: str
```

### 5.3 规则

- 逐项列出每个 evidence 的发现
- 明确说明为何不合成
- 不聚合任何数值

---

## 六、禁止

| 禁止行为 | 原因 |
|---|---|
| 在冲突未解决时静默平均 | 掩盖 directional 冲突 |
| 在异质性过高时做 meta-analysis | 统计上不恰当 |
| 对不同 source_type 不区分地混合 | 监管可采信性不同 |
| 将仅有 1-2 个研究的结果称为 benchmark | 样本量不足 |
| 将 low-confidence 事实纳入 benchmark | 污染基准 |
| 在 narrative synthesis 中声称定量结论 | 方法不支持 |

---

*CCD 签发：2026-05-12*
