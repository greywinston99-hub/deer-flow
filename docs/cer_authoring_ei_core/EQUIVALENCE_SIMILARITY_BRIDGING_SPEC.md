# EQUIVALENCE / SIMILARITY BRIDGING SPEC

> CCD 签发 | 2026-05-12 | Evidence Intelligence Core Upgrade

## 一、与 V2 的关系

本 spec 在 V2 `SIMILAR_COMPETITOR_EVIDENCE_SPEC.md` 的基础上增加推理层的桥接逻辑。V2 定义了关系分类、可比性评分、allowed-use 规则。本 spec 定义如何从这些分类中推导声明。

---

## 二、四种设备关系的桥接推理

### 2.1 Equivalent Device（等效设备）

**前提条件**：equivalence rationale 已成立（技术/生物/临床 ≥2 each，总 comparability_band = HIGH）

| 维度 | 规则 |
|---|---|
| **可桥接到** | Safety claims, Performance claims（在 equivalence scope 内） |
| **不可桥接到** | Equivalence scope 外的声明 |
| **桥接强度上限** | MODERATE（除非有 subject device direct evidence 补充 → 可至 STRONG） |
| **需要额外前提** | Equivalence rationale 文档 + 等效范围声明 |
| **等效论证失败时** | equivalent_device → 降级为 similar_device（按 similar rules）或 NOT_ADMISSIBLE（如无 comparability） |

**推理链**：
```text
equivalent_device evidence
  → 检查 equivalence rationale 是否成立
    YES → 在 equivalence scope 内可用，max MODERATE
    NO  → 降级为 similar_device，按 similar rules
```

### 2.2 Similar Device（相似设备）

| 维度 | 规则 |
|---|---|
| **可桥接到** | Clinical context, SOTA benchmark, Risk context |
| **不可桥接到** | Direct clinical benefit claims for subject device |
| **桥接强度上限** | CAUTIOUS |
| **需要额外前提** | 必须引用设备差异 + 限制条件 |
| **可用于什么声明** | SOTA 基准（分析可比设备的表现范围）、风险上下文（可比设备报告的风险类型） |

**推理链**：
```text
similar_device evidence
  → 可用于 SOTA benchmark（source_type = ADMISSIBLE for SOTA Context）
  → 可用于 Risk context（CONDITIONAL：仅提供背景，非独立风险估计）
  → 不可用于 subject device safety/performance claims（NOT_ADMISSIBLE）
```

### 2.3 Competitor Device（竞品设备）

| 维度 | 规则 |
|---|---|
| **可桥接到** | SOTA benchmark only |
| **不可桥接到** | 任何 subject device 的 safety, performance, benefit claims |
| **桥接强度上限** | 仅可用于 SOTA 背景基准 |
| **需要额外前提** | 必须披露 competitive relationship |
| **竞品数据能否暗示性能预期** | 仅可在「背景基准」中作为数据点，不可单独引用做比较 |

**推理链**：
```text
competitor_device evidence
  → 仅可用于 SOTA benchmark（ADMISSIBLE for SOTA Context）
  → 不可用于任何 subject device claim（NOT_ADMISSIBLE for all claim types）
  → 在 SOTA 中标注数据来源限制
```

### 2.4 Previous Generation Device（前代设备）

| 维度 | 规则 |
|---|---|
| **可桥接到** | Clinical context, Risk context |
| **不可桥接到** | Direct performance claims（除非有改进对比数据） |
| **桥接强度上限** | 有改进对比数据 → MODERATE；无数据 → CAUTIOUS |
| **需要额外前提** | 改进对比数据 + improvement trace |

**推理链**：
```text
previous_gen_device evidence
  → 有改进对比数据：
      可支撑「相对于前代改进」的声明（max MODERATE）
  → 无改进对比数据：
      仅可用于 clinical/risk context（CAUTIOUS）
```

---

## 三、桥接推理输出

每个 indirect evidence 的桥接推理输出：

```text
bridging_assessment:
  evidence_id: str
  device_relationship: str
  comparability_band: str
  bridge_to_claim_types: [str]        # 可桥接到的声明类型
  forbidden_claim_types: [str]        # 不可桥接的类型
  max_conclusion_strength: str        # 通过此证据可达到的最高结论强度
  bridging_conditions: [str]          # 桥接须满足的条件
  bridging_limitations: [str]         # 桥接限制
  rationale: str                      # 桥接理由
```

---

## 四、结论强度上限规则

| 证据组合 | 最高结论强度 |
|---|---|
| 仅有 equivalent_device 证据 | MODERATE |
| equivalent_device + subject_device 证据 | STRONG（如 subject device 证据本身足够） |
| 仅有 similar_device 证据 | CAUTIOUS |
| 仅有 competitor_device 证据 | INSUFFICIENT（对 subject device claims） |
| 仅有 previous_gen 证据（有改进数据） | MODERATE |
| 仅有 previous_gen 证据（无改进数据） | CAUTIOUS |
| subject_device + similar + competitor（混合） | 按 subject_device 的强度决定 |

---

## 五、禁止

- ❌ 将 equivalent_device 证据用于 equivalence scope 外的声明
- ❌ 在 equivalence rationale 未成立时使用 equivalent 路径
- ❌ 将 competitor 数据用于 subject device 的性能或安全性声明
- ❌ 将 similar device 数据当作 direct evidence for subject device
- ❌ 桥接时不注明设备差异和限制条件
- ❌ 将 bridged 证据的结论称为「证实」

---

*CCD 签发：2026-05-12*
