# DOMAIN TERM MATRIX V1

> CCD | 2026-05-15 | Authoritative for Gate 1

## Domain: cardiac_tissue_stabilizer

心脏组织固定器。CABG/off-pump 冠脉搭桥术中通过负压吸附或机械压迫稳定靶血管区域。不进入体内腔道，不含能量输出，不涉及泌尿系统。

**Required Terms**（正文中至少出现其中几个）：
`cardiac tissue stabilizer`, `tissue stabilizer`, `heart stabilizer`, `coronary artery bypass`, `CABG`, `OPCAB`, `off-pump`, `beating heart`, `anastomosis`, `target vessel`, `myocardial revascularization`, `sternotomy`, `thoracotomy`, `cardiac surgery`, `suction stabilization`, `mechanical stabilization`

**Allowed Terms**（可出现，中性）：
`coronary artery disease`, `CAD`, `left anterior descending`, `LAD`, `internal mammary artery`, `saphenous vein graft`, `cardiopulmonary bypass`, `CPB`, `conversion to CPB`, `hemodynamic stability`, `graft patency`, `perioperative`, `median sternotomy`

**Forbidden Terms**（出现即 Gate 1 HARD FAIL）：
`ureteroscope`, `UAS`, `ureteral access sheath`, `urinary tract`, `ureter`, `renal insufficiency`, `stone burden`, `urolithiasis`, `hydrophilic coating`, `endourology`, `urological endoscopy`, `percutaneous nephrolithotomy`, `PCNL`, `flexible ureteroscopy`, `fURS`, `suction sheath`, `negative-pressure access sheath`, `guidewire`（除非在明确排除性上下文中）

**Ambiguous Terms**（触发 Warning，不 HARD FAIL）：
`stabilizer`（可能是骨科或神经外科），`suction`（可能是泌尿），`negative pressure`（多域共用）

**Exception Contexts**（forbidden term 出现但不触发 HARD FAIL）：
- 句子包含 `excluded` `not applicable` `differs from` `unlike` `in contrast to`
- 明确作为非本设备域的对比说明
- 在 Annex 检索策略描述中说明排除逻辑

**Section Scope**：Gate 1 扫描 Summary（§1）、Device Description（§2.1）、Intended Purpose（§2.2）、Clinical Background（§3.1-3.8）、Device Under Evaluation（§4）、Conclusions（§5）。Annex 不在扫描范围。

---

## Domain: orthopedic_rf_plasma_electrode

射频等离子手术电极。关节镜/开放手术下，利用射频能量在生理盐水中产生等离子场，对软组织进行切除、消融、凝固和止血。涉及关节腔（膝、肩、髋等），不涉及泌尿系统、心脏介入、神经外科。

**Required Terms**：
`radiofrequency`, `RF`, `plasma`, `electrode`, `arthroscopy`, `arthroscopic`, `joint`, `soft tissue`, `resection`, `ablation`, `coagulation`, `hemostasis`, `saline`, `thermal`, `knee`, `shoulder`, `hip`, `meniscus`, `cartilage`, `synovial`, `ligament`

**Allowed Terms**：
`orthopedic`, `sports medicine`, `articular`, `chondral`, `debridement`, `lavage`, `shaver`, `irrigation`, `saline irrigation`, `thermal injury`, `collateral damage`, `depth of penetration`

**Forbidden Terms**（出现即 Gate 1 HARD FAIL）：
`ureteral access sheath`, `ureteroscope`, `urolithiasis`, `urinary tract`, `renal insufficiency`, `stone burden`, `endourology`, `cardiac ablation`, `PADN`, `pulmonary artery`, `atrial fibrillation`, `pulmonary vein`, `catheter ablation`, `guidewire`（同上），`endoscopic access sheath`, `UAS`

**Ambiguous Terms**：
`ablation`（心脏消融共用），`resection`（肿瘤外科共用），`electrode`（心电图共用）

**Exception Contexts**：同 cardiac_tissue_stabilizer。

**Section Scope**：同 cardiac_tissue_stabilizer。

---

## Domain: medical_imaging_software

医学影像处理软件。Software as Medical Device。接收 DICOM 影像输入，执行图像处理/分析算法，输出处理后的图像或量化结果。纯软件产品，无物理器械、无患者接触。

**Required Terms**：
`medical imaging software`, `image processing`, `DICOM`, `PACS`, `workstation`, `software`, `algorithm`, `image analysis`, `visualization`, `rendering`, `quantification`, `segmentation`, `registration`, `diagnostic`, `screening`, `detection`, `radiology`

**Allowed Terms**：
`CT`, `MRI`, `X-ray`, `ultrasound`, `mammography`, `AI`, `deep learning`, `CNN`, `FDA 510k`, `MDR`, `IEC 62304`, `software lifecycle`, `SIL`, `SOUP`

**Forbidden Terms**（出现即 Gate 1 HARD FAIL）：
任何物理器械术语在没有明确排除上下文中出现：`catheter` `implant` `sterile` `shelf life` `biocompatibility` `surgical access` `endoscopic` `ureteroscope` 等。具体：软件报告不应写物理器械的 2.1 模板（composition/sterility/variants 等物理属性）。

**Ambiguous Terms**：
`clinical data`（软件临床试验 vs 器械临床数据），`device`（SaMD 在 MDR 下是 device，但≠物理器械）

**Exception Contexts**：同 cardiac_tissue_stabilizer。

**Section Scope**：同 cardiac_tissue_stabilizer。

---

## Domain: cardiovascular_rf_ablation_catheter

用于 CAL-001 校准基线。PADN 肺动脉射频消融导管。不在此次三项目 pilot 中但保留 domain 定义作为 matrix 完整性的参考。

**Forbidden Terms**（基线参考）：
`joint`, `arthroscopy`, `orthopedic`, `ureteroscope`, `urological`, `soft tissue resection`

---

## Gate 1 判定逻辑

```
for each section in [Summary, 2.1, 2.2, 3.1-3.8, 4.x, 5]:
    for each forbidden_term in domain.forbidden_terms:
        if forbidden_term found in section:
            if context is NOT an exception_context:
                → HARD FAIL
                → record: section, term, surrounding text
                → stop scan (first fail is sufficient)

if any ambiguous_term found without required_term nearby:
    → WARNING (does not block, recorded in gate report)

if required_term match rate < 30%:
    → WARNING (does not block, suggests domain mismatch)
```

---

*CCD 签发：2026-05-15*
