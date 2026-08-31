# 业务背景: MaterniFlow 妇产科病房调度 POC

> **数据集:** `healthcare_obstetrics_ward_scheduling_medium`
> **复杂度:** 中等 (11 张表, ~500 行)
> **市场:** 北美 (美国, USD)
> **参考日 (REFERENCE_DATE):** `2026-02-13 08:00` (Demo 起点)
> **本文档的角色:** 数据集的"为什么" — 公司, 行业, 项目, 业务问题, 行业科普, 术语表, 指标公式都在这里. 表结构与字段定义见 `02-..._er_document-cn.md`, 查询见 `03-..._sql_queries-cn.md`.

---

## 目录

1. [一句话概览](#1-一句话概览)
2. [Beat 1 公司画像](#2-beat-1-公司画像)
3. [Beat 2 商业模式](#3-beat-2-商业模式)
4. [Beat 3 行业普及](#4-beat-3-行业普及)
5. [Beat 4 项目框架](#5-beat-4-项目框架)
6. [Beat 5 要解决的业务问题](#6-beat-5-要解决的业务问题)
7. [Beat 6 数据范围概览](#7-beat-6-数据范围概览)
8. [Beat 7 行业知识科普](#8-beat-7-行业知识科普)
9. [Beat 8 术语表](#9-beat-8-术语表)
10. [Beat 9 关键指标与公式](#10-beat-9-关键指标与公式)

---

## 1. 一句话概览

**Halcyon Health Analytics** 是一家总部位于美国得州 Austin 的中型医疗数据咨询公司, 专门给医院做"小切口、看得见摸得着"的 AI 落地项目. 它正在给一家区域性妇产科连锁医院 **Cedar Ridge Women's Health** (太平洋西北, 俄勒冈州 Portland 都会区) 交付一个叫 **MaterniFlow** 的概念验证 (POC, Proof of Concept) —— 一个 **AI 辅助妇产科病房调度助手**.

你是 Halcyon 派驻这个 POC 的**数据负责人 (founding data hire)**: 设计数据模型、生成沙盘数据、写出供 AI agent 在背后调用的 SQL 工具集, 直接向项目交付负责人 (engagement lead) 汇报. 你的全部工作, 都是为了在**演示日**让 Cedar Ridge 的一线护士看到: "这个 AI 真的能把病房状态看清楚." 本数据集就是这个 POC 的**沙盘 (sandbox)**.

> 写作口吻提醒: 本文档用中文讲述, 但公司、客户、城市、货币、监管机构全部是**北美**的. 业务术语 (如 LOS, EDD, VBAC, NICU) 一律保留英文原词, 在 [术语表](#9-beat-8-术语表) 里逐条用大白话解释.

---

## 2. Beat 1 公司画像

### 2.1 乙方 — 你所在的公司 Halcyon Health Analytics

| 维度 | 设定 |
|------|------|
| 公司名 | **Halcyon Health Analytics** (虚构, 非任何真实公司) |
| 总部 | 美国得克萨斯州 Austin |
| 公司类型 | 医疗数据 + AI 解决方案咨询 (healthcare solution consulting) |
| 规模 | ~70 名员工 (数据工程师、临床信息学顾问、AI 工程师、项目交付) |
| 年营收 | ~1500 万美元量级 (以咨询项目费 + 后续实施合同为主) |
| 客户群 | 北美中小型医院与区域连锁医疗集团 (尚未上 Epic/Cerner 级别大平台、或想在大平台之外做轻量增强的医院) |
| 一句话定位 | "用一个低成本、低风险的小型 POC 证明 AI 能力, 再争取后续更大的实施合同." |

Halcyon 不卖一个庞大的 HIS (Hospital Information System), 也不取代医院现有的 EMR (Electronic Medical Record). 它的打法是: 找到医院一个**琐碎、高频、容易出错**的具体痛点, 用一个有限边界的 demo 证明 "AI 在这个边界内能做到足够高的精度", 然后把这份信任放大成更大的项目.

### 2.2 甲方 — 客户 Cedar Ridge Women's Health

| 维度 | 设定 |
|------|------|
| 客户名 | **Cedar Ridge Women's Health** (虚构) |
| 类型 | 区域性**妇产科 / 妇科连锁医院** (Maternity & OB/GYN hospital chain) |
| 所在地 | 俄勒冈州 Portland 都会区, 覆盖太平洋西北 |
| 规模 | 6 家分院, 合计数千张床, 每年接生数万例 |
| 在项目中的位置 | 出题 + 出预算 + 评估精度. POC 的甲方决策人是护理副总 (VP of Nursing) 与首席医疗信息官 (CMIO) |

本 POC 只针对 Cedar Ridge **其中一家分院的一个妇产科病房 (ward)** 建沙盘. 甲方想验证的不是 "AI 能不能处理海量数据", 而是 "AI 能不能在一个有限边界内做到足够高的精度". POC 通过精度阈值后, 才会进入对接真实 EMR、扩到全部分院的更大项目阶段.

### 2.3 谁出现在查询里 (角色名录)

后续 SQL 查询会按**职位**点名, 这些职位都来自上面两家公司的真实病房 / 项目角色:

- **Charge Nurse** (总责护士 / 班长): 病房一线指挥, 交班、找床、派活都是她.
- **Attending Physician** (主治医师): 查房、定临床方向, 关心高危产妇.
- **Nurse Manager / Department Manager** (护士长 / 科室经理): 管排班与人手负载.
- **OR Coordinator** (手术室协调员): 排剖宫产、引产的时间与房间.
- **Quality Analyst** (质量分析师): 校验 AI 预测准不准 (LOS 准确度的答辩人).
- **MFM Specialist** (母胎医学专家): 盯多胎、早产等最高危的产妇.
- **CMIO / VP of Nursing**: 甲方决策层, POC 验收的最终拍板人.

---

## 3. Beat 2 商业模式

Halcyon 怎么赚钱, 一句话: **卖咨询交付, 用小 POC 钓大合同, 最终落到按床 / 按院的软件订阅.**

| 收入阶段 | 形态 | 典型量级 (USD) | 说明 |
|---------|------|--------------|------|
| 1. POC 阶段 (本数据集) | 固定价咨询费 | $80K – $150K | 一次性, 低风险. 交付沙盘 + demo + 验收报告. 就是当前这个项目. |
| 2. 实施阶段 | 项目制实施合同 | $0.5M – $2M | POC 过关后, 接真实 EMR (HL7/FHIR)、扩到多分院. |
| 3. 运营阶段 | SaaS 订阅 (按床位 / 按分院) | 每床每月 $X, 经常性收入 | 模型上线后的长期 license + 维护. |

**单位经济学的逻辑**: POC 本身几乎不赚钱 (固定价、人力密集), 它是**获客成本 (customer acquisition cost) 的一部分**. Halcyon 真正的利润来自阶段 2、3 —— 一旦 Cedar Ridge 信任了 MaterniFlow, 把模型铺到 6 家分院的所有妇产科病房, 才是高毛利的经常性收入. 所以 POC 演示日 "AI 答得准不准" 直接决定后续几百万美元合同能不能签下来. 这就是为什么本数据集里**每一个埋点都被精心设计成可被 SQL 验证** —— 演示当天容不得 AI 在护士面前算错一个人头.

**为什么客户愿意买**: 妇产科病房调度的痛点是 "琐碎、高频、靠人脑记容易漏". 旧的 content-management 式 (CMS-like) 系统只会显示原始数据, 不会替护士做 "现在有几张干净的 labor 床" 这种**聚合 + 阈值判断**. MaterniFlow 卖的就是 "把护士从重复检索里解放出来" 的省时价值.

---

## 4. Beat 3 行业普及

### 4.1 这个行业在做什么

美国医院 IT 是个**万亿美元级别**的市场, 但极度碎片化. 大医院多被两三家巨头 EMR 平台垄断 (本文不点名真实公司), 中小医院与区域连锁则在巨头平台之外留有大量 "最后一公里" 的轻量需求 —— 病房调度、床位管理、交班简报、排班覆盖, 这些日常运营动作往往还在用 Excel、白板、或功能简陋的内部系统. Halcyon 这类咨询公司就吃这块 "巨头看不上、但医院天天痛" 的缝隙市场.

妇产科 (Obstetrics, 简称 OB) 是其中一个特别适合做 POC 的科室, 因为:

- **流程标准化**: 产妇从入院 → 产程 → 分娩 → 产后 → 出院, 是一条边界清晰的状态机, 容易建模.
- **节奏快、容错低**: 一个高危产妇被漏看可能就是医疗事故, "看清楚病房" 的价值立刻可量化.
- **资源约束硬**: labor room、delivery room (OR)、麻醉师、NICU 床位都是稀缺资源, 调度冲突天天发生.

### 4.2 主要玩家类别 (不点名真实公司)

| 类别 | 角色 |
|------|------|
| 大型 EMR / EHR 平台 | 医院的 "操作系统", 管病历、医嘱、计费. 功能全但笨重、定制贵. |
| 病房 / 床位管理软件商 | 专做 bed management、patient flow 的中型厂商. |
| 医疗数据 / AI 咨询公司 | 即 Halcyon 这类, 做轻量、可落地的增强. |
| 医院自建 IT 团队 | 大医院有, 中小连锁通常没有, 才需要外包给 Halcyon. |

### 4.3 监管与合规 (北美)

医疗数据是高度受监管的领域, MaterniFlow 即使只是 POC 也绕不开:

- **HIPAA** (Health Insurance Portability and Accountability Act): 美国患者隐私与数据安全的根本大法. POC 用的是**合成 / 假数据** (本数据集), 正是为了在不碰真实 PHI (Protected Health Information) 的前提下验证能力.
- **HITECH**: HIPAA 的数字化补强, 管电子健康信息的安全.
- **The Joint Commission (TJC)**: 医院认证机构, 对产科安全、交班流程 (hand-off communication) 有明确标准 —— 这正是 demo 场景 1 (交班) 的合规背景.
- **CMS** (Centers for Medicare & Medicaid Services): 管 Medicare / Medicaid 报销与质量上报, 间接决定了 payer mix (见术语表).
- **FDA SaMD** (Software as a Medical Device): 一旦 AI 介入**临床决策** (开药、诊断), 就可能被监管为医疗器械. **MaterniFlow 刻意把边界划在 "只读 + 看清楚 + 简单告警", 不诊断、不开药**, 正是为了避开 SaMD 的高监管成本.
- 若扩到加拿大分院, 对应监管为 **Health Canada** 与各省隐私法 (如 PIPEDA).

### 4.4 当下的宏观趋势

- **护士短缺 (nursing shortage)**: 北美护理人力长期紧张, "把护士从重复检索里解放出来" 的工具有强刚需.
- **AI 进病房**: 生成式 AI 让 "护士自然语言提问 → AI 调用 SQL 工具回答" 成为可能, 这正是 MaterniFlow 的技术押注.
- **互操作标准化 (HL7 / FHIR)**: EMR 数据交换标准成熟, 让 Halcyon 这类第三方未来能合规接入真实数据.
- **价值医疗 (value-based care)**: 报销与质量、效率挂钩, 推动医院愿意为 "缩短 LOS、减少调度冲突" 的工具买单.

---

## 5. Beat 4 项目框架

### 5.1 你的角色

你是 Halcyon 的**数据负责人 (founding data hire)**, 被派到 MaterniFlow POC. 你的交付物有三件:

1. **数据沙盘**: 一份 ~500 行的 SQLite 数据库 + TSV, 模拟一个真实妇产科病房此刻的状态.
2. **查询工具集**: 20 条业务问题导向的 SQL, 作为 AI agent 背后的 "tool calls".
3. **验收材料**: 让甲方 IT 团队事后审计 "每一条 AI 回答都对得上 schema 里的真实数据".

你直接向**项目交付负责人 (engagement lead)** 汇报, 演示日的最终听众是 Cedar Ridge 的 **Charge Nurse、Nurse Manager 和 CMIO**.

### 5.2 这是 POC, 不是生产系统

**MaterniFlow** 是一个概念验证, **不是**上线运行的生产系统, 也**不是**完整的医院 HIS. 它只回答一个具体问题:

> *"在数据量不大、场景不复杂的前提下, AI 能不能把一个 content-management 式的病房调度任务做得足够准?"*

这就是为什么数据刻意保持 ~500 行小体量: 客户想验证的是 "AI 能不能在**有限边界**内做到**足够高的精度**", 而不是 "AI 能不能处理海量数据". 精度可解释 (500 条能人工全量复核)、演示速度快 (SQLite 单机)、聚焦业务而非数据工程, 是这个尺寸的刻意好处.

### 5.3 POC → 更大项目的演化路径 (future scope, 本数据集不含)

| 扩展方向 | 涉及的额外数据 |
|---------|--------------|
| 真实 EMR 接入 | HL7 / FHIR 接口、ICD-10 编码、用药记录 |
| 多分院汇总 | hospital 表、network-level dashboard、跨院转诊 |
| 婴儿数据 | newborn 表、Apgar 评分、NICU 详细监护 |
| 计费与保险 | encounter、charge、payer authorization |
| 质量上报 | core measure、CMS 报告、SCIP 指标 |
| 临床决策支持 | 用药建议、CTG 自动判读、产程图自动绘制 |

本 POC 的边界一句话: **只读 + 病房视图 + 简单告警, 不写、不诊断、不开药.**

---

## 6. Beat 5 要解决的业务问题

POC 要验证 5 个核心场景 —— 都是 Cedar Ridge 一线护士日常要回答、但琐碎易错的问题. 每个问题都映射到 `03-..._sql_queries-cn.md` 里的若干查询.

| # | 场景 | 业务问题 (护士口语版) | 这道题在问什么 | 对应查询 |
|---|------|---------------------|--------------|---------|
| **P1** | **Shift Handover** 交班简报 | "我现在接班, 病房里有多少人? 都在哪个阶段?" | AI 的**计数与状态分类**全对吗? | Q1, Q5, Q6, Q14 |
| **P2** | **Room Availability** 房间余量 | "现在 labor room 还有空床位吗? 哪几个干净的?" | AI 能正确**分辨 4 种床位状态** (不能简单二分) 吗? | Q2, Q10, Q18 |
| **P3** | **LOS Prediction** 出院预测 | "这个产妇估计什么时候出院? 床什么时候腾出来?" | AI 的产后 LOS 预测**符合临床规律** (顺产短、剖宫产长) 吗? | Q9, Q13, Q17 |
| **P4** | **High-Risk Alert** 高危预警 | "现在病房里有谁血压一直在涨? 要不要叫医生?" | AI 能识别**趋势性**高血压 (不止单点阈值) 吗? | Q3, Q7, Q16 |
| **P5** | **Order Scheduling** 医嘱安排 | "明天 9 点那台剖宫产排哪间 OR? 麻醉师对得上吗?" | AI 能检出**资源冲突** (房间 / 麻醉师) 吗? | Q4, Q14, Q19 |

注意这 5 个都是 **CMS-like (内容管理式) 任务**: 查询 + 简单计算 + 阈值告警, **不涉及**临床决策、医嘱生成、用药推荐这种高风险动作. 这是甲方对 POC 边界的明确约束 —— 验证 "AI 帮人**看清楚**", 而非 "AI 帮人**决定**".

为了让这 5 个问题在 ~500 行里都能被 SQL 验证, 数据生成器**确定性地**埋了几个 "剧情点" (详见 ER 文档的业务陷阱声明), 例如: 两例血压沿 `125 → 131 → 137 → 143` 上升越过 140 的高危产妇 (P4)、一台明天 09:00 的剖宫产 (P5)、一张 labor 房的 cleaning 床 (P2). 这些埋点是查询能跑出预期结果的前提.

---

## 7. Beat 6 数据范围概览

| 维度 | 设定 | 理由 |
|------|------|------|
| 时间锚点 | `REFERENCE_DATE = 2026-02-13 08:00` (Demo 起点, 周五早 8 点) | 所有 "现在 / 今天" 都以它为准, 多次运行结果一致 |
| 时间跨度 | Demo 当天 + 前 3 天 (历史) + 后 1 天 (明日 scheduled order) | 够演示 "刚发生的" 与 "马上要发生的" |
| 物理范围 | **1 个**妇产科 ward, ~20 间房, ~32 张床 | 单病房沙盘, 聚焦边界内精度 |
| 患者池 | 50 个 patient (覆盖各类妊娠风险) | 人工可全量复核 |
| 当前住院 | 16 个 admission = **15 active + 1 discharged** | 15 个 active 覆盖全部 5 个在院阶段, 1 个 discharged 作 LOS 基线 |
| 时序数据 | 每位住院产妇 ~3-10 条 labor progress, ~1-12 条 vital sign | 模拟内诊与监护采样, 但保持小体量 |
| 总量 | 11 张表, ~500 行, SQLite < 200 KB | medium 复杂度 |
| 货币 | USD | 北美市场 |

**刻意的范围决策**: 单病房、单快照、合成数据 (无真实 PHI). 数据**不含** newborn、计费、跨院、真实 EMR 字段 —— 这些都是 future scope, 留到 POC 过关后. 详细的表清单与行数见 `02-..._er_document-cn.md`, 本文不枚举表.

---

## 8. Beat 7 行业知识科普

一个非医疗背景的工程师, 读完这一节就能看懂后面的 ER 文档与 SQL. 这是理解整个数据集的 "30 分钟入门".

### 8.1 一次住院的生命周期 (admission 状态机)

妇产科一次住院, 从入院到出院走过 6 个阶段, 这是整个数据集的主轴:

```
admitted → in_labor → delivered → postpartum → ready_for_discharge → discharged
 已入院     产程中      刚分娩       产后恢复       待出院 (医嘱已下)        已出院
```

| 阶段 | 临床含义 | 通常在哪种房 | 计入 active census? |
|------|---------|------------|---------------------|
| `admitted` | 入院但还没临产 | triage / labor | 是 |
| `in_labor` | 产程中, 宫口已开 | labor (待产室) | 是 |
| `delivered` | 刚分娩 (≤2h) | delivery (OR) / labor | 是 |
| `postpartum` | 产后恢复 (24-72h) | postpartum (产后恢复室) | 是 |
| `ready_for_discharge` | 待出院, 出院医嘱已下 | postpartum | 是 |
| `discharged` | 已出院 | 无 (床已腾空) | **否** |

**active census (在院人数)** = 除 `discharged` 外的所有 admission. 这是交班第一句话 "现在病房里有多少人" 的答案 (见指标公式).

### 8.2 产程怎么读 (labor progress 的临床概念)

产程进展靠护士定期 "内诊" 记录, 用四个指标判断 "还有多久生":

| 名词 | 含义 | 关键阈值 |
|------|------|---------|
| **Cervical dilation** (宫口开大) | 子宫颈口张开程度, 0-10 cm | 10 cm = 开全, 可进入第二产程 (用力期) |
| **Effacement** (宫颈消失度) | 子宫颈变薄程度, 0-100% | 100% = 完全变薄 |
| **Station** (胎头下降位置) | 胎头相对坐骨棘的位置, -3 到 +3 | +3 ≈ 即将娩出 |
| **Membrane** (胎膜 / 羊膜囊) | 包绕胎儿的水囊 | `ruptured` (破水) 后通常 24h 内分娩 |

经验法则: **宫口 ≥ 8 cm + 已破水 ≈ 1-2 小时内娩出**. 这是预测 "labor room 什么时候腾出来" 的依据 (P2、P3).

### 8.3 妊娠风险怎么判 (risk_level 派生逻辑)

每位产妇有一个 `risk_level` (low / medium / high), 不是随便填的, 而是按**风险因子累加**派生:

- 年龄 ≥ 35 (**AMA**, 高龄产妇): +1
- 多胎 (双胎 / 三胎, `fetus_count > 1`): +2 (多胎是产科最高警觉, 早产率 60%+)
- 早产倾向 (`gestational_weeks < 37`): +1
- 既往剖宫产 + 本次计划 **VBAC**: +1 (有子宫破裂风险)
- 每条并发症 (complication): +1

累加结果: **0 → low, 1-2 → medium, ≥3 → high**. 高危产妇是 attending 查房和 MFM 会诊的重点 (P4).

### 8.4 分娩方式与住院时长 (LOS 规律)

| 分娩方式 | 英文 | 产后住院时长 (LOS) 经验值 |
|---------|------|------------------------|
| 顺产 | Vaginal delivery | 24-48 小时 |
| 剖宫产 | C-section (Cesarean) | 72-96 小时 (手术恢复更久) |
| 剖宫产后阴道分娩 | **VBAC** | 是一个 *计划* 类别; 真分娩时落地为顺产或剖宫产 |

**关键口径**: 本数据集的 `predicted_los_hours` 指**产后**住院时长 (从 `delivery_time` 起算, 不含产前在院时间). LOS 预测准不准 (P3) 是甲方最关心的数字之一 —— AI 若把剖宫产预测成 40 小时, 说明它没识别出分娩方式.

### 8.5 病房的物理结构 (room → bed) 与床位状态

一个 ward 分 5 种功能房, 房下面是床 (床的粒度更细, 一间产后房可有多张床):

| `room_type` | 中文 | 用途 |
|-------------|------|------|
| `labor` | 待产室 | 自然分娩的产程观察 |
| `delivery` | 分娩间 / OR | 剖宫产或复杂分娩的手术室 |
| `postpartum` | 产后恢复室 | 产后观察 |
| `nicu` | 新生儿重症室 | 早产 / 危重新生儿 |
| `triage` | 预检分诊 | 入院前评估 |

床位有 **4 种状态**, 这是 P2 的核心难点 —— 不能简单按 "占 / 空" 二分:

- `available` (可立即收下一位)、`occupied` (有人)、`cleaning` (上一位刚走, 清洁中 ~30-60min, **还不能用**)、`maintenance` (设备维护停用).

旧 CMS 只用一个 boolean `is_occupied`, 常把 "清洁中" 当成 "空着", 造成调度冲突. POC 要证明 AI 能正确解析这 4 态.

### 8.6 谁在病房里干活 (provider 与 shift)

5 种医护角色 + 头衔约定:

| `role` | 中文 | 头衔 | 单班配置 |
|--------|------|------|---------|
| `attending` | 主治医师 | `Dr.` | 1 人/班 |
| `resident` | 住院医师 (培训中) | `Dr.` | 1 人/班 |
| `nurse` | 注册护士 (RN) | `RN` | day 3 人 / night 2 人 |
| `midwife` | 助产士 (CNM) | `CNM` | 1 人/班 |
| `anesthesiologist` | 麻醉医师 | `Dr.` | 1 人/班 |

病房 24/7 运行, 分 `day` (07:00-19:00) 和 `night` (19:00-07:00) 两班. **麻醉师单列很关键**: 剖宫产、硬膜外麻醉 (epidural) 必须有麻醉师在岗才能排 (P5).

### 8.7 告警与阈值 (alert)

MaterniFlow 的**输出之一**是自动告警. 当 vital sign 越过阈值时派生一条 alert:

| 指标 | warning | critical |
|------|---------|----------|
| `bp_systolic` (收缩压) | ≥ 140 | ≥ 160 |
| `bp_diastolic` (舒张压) | ≥ 90 | ≥ 110 |
| `fetal_heart_rate` (胎心率) | <110 或 >160 | <100 或 >180 |
| `temperature` (体温, °F) | ≥ 100.4 | ≥ 101.5 |

告警有 4 类: `high_bp`、`abnormal_fhr`、`fever`、`preterm_risk`. POC 的精彩点 (P4): 旧系统只在某次 BP ≥ 140 时报警, **漏掉缓慢上升趋势**; AI 要能看出 "125→131→137→143" 这种连续上升 —— 这是单点阈值法识别不了的早期妊娠期高血压征兆.

### 8.8 保险结构 (payer mix)

美国医疗对保险类型敏感, 影响计费与资源配置:

- **commercial** (商业保险): 单次报销高、需细化 documentation.
- **Medicaid** (政府低收入医保, 专有名词首字母大写): 报销周期长但量大.
- **self_pay** (自费): 需预收押金.

本数据集 payer mix ≈ commercial 55% / Medicaid 35% / self_pay 10%, 反映美国育龄人群的保险结构 (Finance Analyst 的 P-横向视图).

---

## 9. Beat 8 术语表

每个在 ER 文档或 SQL 里出现的英文 jargon, 这里给一句大白话解释 + 一句 "为什么这里重要". 首字母缩写在首次出现时给全称.

### 9.1 妇产科临床术语

| 英文术语 | 大白话解释 | 为什么这里重要 |
|---------|-----------|--------------|
| **Obstetrics (OB)** | 妇产科, 管怀孕到分娩 | 整个数据集的科室 |
| **Maternity ward** | 产科病房 | POC 的物理边界 |
| **Admission** | 一次完整住院 (入院到出院) | 核心事实表, 所有事件挂在它下面 |
| **Length of Stay (LOS)** | 住院时长 | P3 的预测目标; 本数据集特指**产后** LOS |
| **Gravida (G)** | 妊娠总次数 (含本次) | 与 Para 一起写成 "G2/P1", 判断初产 / 经产 |
| **Para (P)** | 既往分娩次数 (孕 ≥20 周) | P0 = 初产妇 (产程更长), P≥1 = 经产妇 |
| **EDD (Estimated Due Date)** | 预产期 | P-横向: 一周内到期的产妇要提前预约确认 |
| **Gestational weeks** | 当前孕周 (如 38.4 = 38 周 +2.8 天) | <37 早产, >42 过期; 决定 EDD 与风险 |
| **Cervical dilation** | 宫口开大, 0-10 cm | 判断 "还有多久生" 的首要指标 (P2/P3) |
| **Effacement** | 宫颈消失度, 0-100% | 产程进展的辅助指标 |
| **Station** | 胎头下降位置, -3 ~ +3 | +3 ≈ 即将娩出 |
| **Membrane** | 胎膜 / 羊膜囊 | `ruptured` (破水) 后通常 24h 内分娩 |
| **Fetal Heart Rate (FHR)** | 胎心率, 正常 110-160 bpm | 异常触发 `abnormal_fhr` 告警 |
| **Vaginal delivery** | 顺产 | LOS 较短 (24-48h) |
| **C-section (Cesarean section)** | 剖宫产 | 手术分娩, LOS 较长 (72-96h), 需 OR + 麻醉师 |
| **VBAC (Vaginal Birth After Cesarean)** | 剖宫产后阴道分娩 | 独立高关注类别, 有子宫破裂风险 |
| **Induction** | 引产 (人工诱发产程) | 需 labor room + attending, 可预约 (P5) |
| **Epidural** | 硬膜外麻醉 (无痛分娩) | 床边操作, 需麻醉师 |
| **GBS (Group B Streptococcus)** | B 族链球菌, 孕晚期常规筛查 | positive 需产时抗生素预防 |
| **Preeclampsia** | 先兆子痫 (妊娠高血压综合征) | 与 BP 上升趋势相关 (P4) |
| **Gestational hypertension** | 妊娠期高血压 | 高危并发症 |
| **Gestational diabetes** | 妊娠期糖尿病 | 常见并发症, 影响营养会诊 |
| **Placenta previa** | 前置胎盘 | 出血风险, 多需剖宫产 |
| **Oligohydramnios / Polyhydramnios** | 羊水过少 / 过多 | 并发症类别 |
| **Intrauterine Growth Restriction (IUGR)** | 胎儿宫内生长受限 | 高危并发症 |
| **AMA (Advanced Maternal Age)** | 高龄产妇 (≥35 岁) | risk_factor +1 |
| **NICU (Neonatal Intensive Care Unit)** | 新生儿重症监护室 | 多胎 / 早产必须确保 NICU 有床 (P2) |
| **MFM (Maternal-Fetal Medicine)** | 母胎医学 (高危妊娠专科) | 多胎、早产会诊找 MFM Specialist |

### 9.2 医护与运营术语

| 英文术语 | 大白话解释 | 为什么这里重要 |
|---------|-----------|--------------|
| **Attending** | 主治医师 (顶级临床责任人) | 查房、定方向 |
| **Resident** | 住院医师 (培训中) | 一线执行 |
| **Nurse (RN, Registered Nurse)** | 注册护士 | 病房日常主力 |
| **Charge Nurse** | 总责护士 / 班长 | 一线指挥, 交班、找床、派活 |
| **Midwife (CNM, Certified Nurse-Midwife)** | 认证助产士 | 接顺产 |
| **Anesthesiologist** | 麻醉医师 | 剖宫产 / epidural 必备 |
| **Triage** | 预检分诊 | 入院前评估 |
| **Shift handover** | 交班 (day ↔ night) | P1; Joint Commission 有合规标准 |
| **Census** | 在院人数 | 交班第一句话 |
| **OR (Operating Room)** | 手术室 (即 delivery room) | 剖宫产场所 |
| **Order (medical order)** | 医嘱 (检查 / 手术 / 用药指令) | P5 的调度对象 |

### 9.3 行业与 IT 术语

| 英文术语 | 大白话解释 | 为什么这里重要 |
|---------|-----------|--------------|
| **POC (Proof of Concept)** | 概念验证 (小型先导项目) | 本数据集的项目性质 |
| **EMR / EHR (Electronic Medical/Health Record)** | 电子病历 | 医院的核心系统, POC 暂不接 |
| **HIS (Hospital Information System)** | 医院信息系统 | MaterniFlow 不是它, 只是轻量增强 |
| **HL7 / FHIR** | 医疗数据交换标准 | 未来接真实 EMR 的接口 |
| **HIPAA** | 美国患者隐私与数据安全法 | POC 用假数据正是为避开真实 PHI |
| **PHI (Protected Health Information)** | 受保护的健康信息 | 本数据集是合成数据, 无真实 PHI |
| **SaMD (Software as a Medical Device)** | 作为医疗器械的软件 | MaterniFlow 划界 "不诊断" 以避开此监管 |
| **CMS (Centers for Medicare & Medicaid Services)** | 美国联邦医保机构 | 管报销与质量上报 |
| **CMIO (Chief Medical Information Officer)** | 首席医疗信息官 | 甲方 POC 验收决策人 |
| **The Joint Commission (TJC)** | 医院认证机构 | 对交班流程有合规标准 |
| **Payer mix** | 保险结构 (各类保险占比) | Finance Analyst 的关注点 |
| **CMS-like (content management)** | 内容管理式 (查询 + 展示, 不做决策) | POC 边界的本质 |

---

## 10. Beat 9 关键指标与公式

下列指标都会在 `03-..._sql_queries-cn.md` 出现. 公式用 SQL 风格伪代码; 凡需 "今天" 的地方一律用字面量 `'2026-02-13'` (= REFERENCE_DATE), 不用 `DATE('now')`.

### 10.1 在院与床位

```
-- 在院人数 (active census): 交班第一句话的答案
Active Census = COUNT(admission WHERE status != 'discharged')

-- 某类房间各状态床位数 (P2): 不能把 cleaning/maintenance 合并进"不可用"
Beds By Status(room_type) = COUNT(bed) GROUP BY status   -- available/occupied/cleaning/maintenance

-- 床位使用率 (P2 运营版)
Bed Utilization % = occupied_beds / total_beds * 100

-- "30 分钟后能用多少" (把 cleaning 也算进来)
Available Soon = COUNT(bed WHERE status IN ('available', 'cleaning'))
```

### 10.2 住院时长 (LOS) — 口径统一为"产后"

```
-- 预测产后 LOS (从分娩起算, 不含产前在院时间)
Predicted Postpartum LOS = predicted_los_hours
    其中: c_section ∈ [72, 96] 小时, vaginal ∈ [24, 48] 小时

-- 实际产后 LOS (仅已出院 admission)
Actual Postpartum LOS = (actual_discharge_time - delivery_time) 换算成小时

-- LOS 预测误差 (P3 答辩数字)
Avg Absolute Error = AVG(ABS(Actual Postpartum LOS - Predicted Postpartum LOS))
Within 12h Rate    = COUNT(|actual - predicted| <= 12) / COUNT(*)
```

> 口径约定 (重要): 预测与实际**都从 `delivery_time` 起算**, 同口径才可比. 不要拿 "总时长 (admit→discharge)" 去对标 "产后预测".

### 10.3 风险与告警

```
-- 风险等级派生 (见 8.3)
risk_factors = (age>=35 ? 1:0) + (fetus_count>1 ? 2:0) + (gest_weeks<37 ? 1:0)
             + (prior=c_section AND planned=vbac ? 1:0) + COUNT(complications)
risk_level   = risk_factors==0 ? 'low' : (risk_factors<=2 ? 'medium' : 'high')

-- 血压趋势 (P4): 用窗口函数 LAG 算每次与上次的差
Systolic Change = bp_systolic - LAG(bp_systolic) OVER (PARTITION BY admission ORDER BY recorded_at)
    连续为正 = 上升趋势; 即使每个单点都 < critical, 趋势也该报警

-- 体温发热判定 (北美产科公认界值)
FEVER = temperature >= 100.4 °F   -- (= 38.0 °C)
```

### 10.4 预产期与排程

```
-- 预产期 (确定性推导)
EDD = REFERENCE_DATE + (40 - gestational_weeks) * 7 天

-- 距预产天数 (P-横向)
Days Until Due = julianday(edd) - julianday('2026-02-13')

-- 医嘱完成率 (P5)
Completion Rate(order_type) = COUNT(status='completed') / COUNT(*) * 100
```

### 10.5 工作量与结构

```
-- 医护当前负载 (一个 provider 同时是 attending 或 primary_nurse 都算)
Provider Workload = COUNT(DISTINCT admission WHERE attending_provider_id = P OR primary_nurse_id = P
                                            AND status != 'discharged')

-- 保险结构 (payer mix, P-横向)
Payer Mix % = COUNT(*) / SUM(COUNT(*)) OVER () * 100  GROUP BY insurance_type

-- 并发症频次 (P-横向): SQLite 下用 LIKE 对 JSON 字段做模式匹配
Complication Frequency = COUNT(complications LIKE '%<name>%')  逐个并发症统计
```

---

> 下一步阅读顺序: 表结构与字段 → `02-..._er_document-cn.md`; 查询与解题思路 → `03-..._sql_queries-cn.md`; 数据生成逻辑 → `04-..._data_generator-cn.py`.
