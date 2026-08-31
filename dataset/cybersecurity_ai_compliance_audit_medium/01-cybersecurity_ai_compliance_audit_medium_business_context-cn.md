# 网络安全 — AI 合规审计系统 业务背景

> 本文档是 `cybersecurity_ai_compliance_audit_medium` 数据集的"出发点"。它先把虚构公司、商业模式、行业、项目、要回答的业务问题讲清楚，再做行业科普、术语表和指标公式。读完本文档，你应该能在第一次站会上跟人聊明白"我们在干什么、为什么这些数据重要"。
>
> 数据表结构、字段、分布、DDL 请见 `02-cybersecurity_ai_compliance_audit_medium_er_document-cn.md`；
> 可运行的 SQL 查询请见 `03-cybersecurity_ai_compliance_audit_medium_sql_queries-cn.md`。

---

## 1. 公司：Sentinel AI Governance

**Sentinel AI Governance**（下文简称 "Sentinel"）是一家虚构的北美 B2B SaaS 公司，总部位于美国马萨诸塞州波士顿（Boston, MA）—— 这里是网络安全与合规软件的传统聚集地。公司成立于 2021 年，正好踩在 NIST AI RMF 立项、企业开始批量把 AI/ML 模型推上生产的时间点上。

| 维度 | 设定 |
|------|------|
| 总部 | 美国马萨诸塞州波士顿（Boston, MA） |
| 成立 | 2021 年 |
| 员工 | ~150 人（工程、合规研究、客户成功、销售） |
| 年度经常性收入 | ~$28M ARR（USD） |
| 客户数 | ~80 家中大型企业租户 |
| 货币 | 美元（USD） |

Sentinel 卖的是一套 **AI 合规审计与治理平台（AI Governance Platform）**。它的定位不是再造一个 MLOps 工具或 SIEM，而是做企业内部"AI 合规的单一事实来源（Compliance Single Source of Truth）"：把原本散落在 MLOps 平台、安全工单系统、Excel 合规清单里的"模型 × 控制项 × 证据 × 整改"信息，汇聚到同一个数据底座上。这样一来，客户的 CISO 做季度董事会汇报、Compliance Manager 做框架审计、Risk Manager 追整改进度，都基于同一份事实数据。

公司层面会被本数据集查询引用的角色（都在**客户**那一侧）：CISO / CTO（看高风险敞口与未关闭 CRITICAL 事件）、Compliance Manager（看框架覆盖率与符合率）、Risk Manager（看风险评分与单点责任）。Sentinel 自己的销售和工程团队不出现在数据里。

---

## 2. 商业模式

Sentinel 的钱来自 **按租户的年度订阅（annual subscription）**，这是典型的 B2B SaaS 打法：

- **怎么收费**：按客户"被治理的生产 AI 模型数量"+"启用的合规框架数量"分档定价。一个刚起步、只治理几十个模型的中型客户大约 $60K ARR；一个治理上百个模型、横跨 6 个框架的大客户可到 $200K–$250K ARR。
- **谁来买单**：买单的是客户的 CISO 办公室或 Chief Risk Officer（CRO）预算线，因为 AI 合规已经从"工程内部的事"上升为"董事会要看的风险敞口"。
- **单位经济**：纯软件交付，gross margin 约 80%（行业典型 SaaS 区间）。新客户上线时会附带一笔一次性的 professional services（数据接入与框架映射），但收入主体是订阅 ARR。
- **续约逻辑**：监管只会越来越紧（见下文行业部分），客户一旦把治理流程跑在 Sentinel 上就很难迁出，因此净留存（net retention）高是这门生意的核心。

一句话：Sentinel 不生产合规结论，它只是把合规证据"聚合、留痕、可查询"，然后按治理规模收订阅费。

---

## 3. 行业概览：AI 治理 / GRC 软件

如果你来自别的行业，这一节帮你建立对这个市场的整体认知。

**这个行业创造什么价值。** 企业把 AI/ML 模型推上生产后，监管和董事会都会问同一个问题："你怎么证明这些模型是安全、合规、被管住的？" AI 治理（AI Governance）软件就是来回答这个问题的 —— 它把"风险识别 → 评估 → 缓解 → 治理"的全链路留痕，让企业能在审计、监管问询、安全事件发生时拿出证据。这属于更大的 **GRC（Governance, Risk, Compliance，治理 / 风险 / 合规）软件**赛道下的新兴细分。

**主要玩家类别（不点名真实公司）：**

- **AI 治理 / GRC 平台**（Sentinel 所在的位置）：聚合证据、做合规留痕。
- **MLOps / 模型可观测性厂商**：管模型训练、部署、漂移监控 —— Sentinel 从这里取数据，而不替代它。
- **安全 / SIEM 厂商**：管安全事件与日志 —— Sentinel 同样是聚合方。
- **大型审计 / 咨询机构**：提供人工合规审计服务，常常是 Sentinel 的合作方而非竞品。
- **企业自建的 Excel / Confluence 清单**：Sentinel 最常替换掉的"现状"。

**相关监管与框架。** 这是理解本数据集存在意义的关键 —— 2023–2026 是 AI 合规需求爆发期：

- **NIST AI RMF 1.0**（2023-01 发布）成为美国治理 AI 风险的事实参考框架，要求"风险识别 → 评估 → 缓解 → 治理"全链路留痕。
- **EU AI Act**（2024 通过、2026 起分阶段生效）要求高风险 AI 系统留存技术文档、风险评估、上市后监测记录。
- **California SB 1047**（2024 关于前沿模型安全的提案）给美国大企业带来"合规先行"的内部压力。
- **SR 11-7**（美联储与 OCC 的模型风险管理指引）原本只覆盖银行统计模型，但 LLM 进入信贷与反欺诈链路后被监管延伸解读到 AI 模型。
- **GDPR Article 22**（自动化决策的解释权）+ **HIPAA**（医疗数据保护）把"模型对个人数据的处理"纳入审计。
- **SOC 2 Type II**（持续运营有效性审计）对 SaaS 公司的 AI 模型留痕提出具体要求。

**正在塑造这个市场的宏观力量：** AI 采用的爆发、监管在 2023–2026 持续收紧、董事会层面对 AI 风险的关注从"零"变成"季度必看"。这些堆积起来的直接结果：每家中大型企业都需要一个"中心账本"来回答"**哪个模型，在哪个控制项下，被谁评估过，结论是什么，证据在哪里**"。

---

## 4. 项目背景：你的角色

**你是 Sentinel 客户分析团队（Customer Analytics）的一名数据分析师**，被指派支持一家具体的客户租户。你的活儿是用这家客户在 Sentinel 平台上沉淀的数据，搭出他们日常要用的合规仪表盘、审计报告和董事会指标。

你服务的对象（客户侧的相关方）映射到数据里的角色画像如下：

| Persona | 对应的 `user.role` | 关心的指标 | 常用查询 |
|---------|-------------------|-----------|---------|
| **Executive / C-Level**（CISO / CTO） | （由汇报关系隐含，非 `user` 表枚举） | 高风险模型占比、未关闭 CRITICAL 事件、整体合规率 | Q1, Q17, Q20 |
| **Compliance Manager** | Compliance Auditor（管理职） | Coverage Rate、Compliance Rate、Audit Coverage Gap | Q2, Q14, Q19 |
| **Risk Manager** | Risk Manager | NOT_STARTED 高风险数、模型所有者集中度 | Q3, Q11 |
| **Operations / Frontline** | MLOps Engineer、DevOps Engineer、Compliance Auditor（执行职） | 高优先级待办、逾期天数、完成率 | Q5, Q8, Q9, Q13, Q18 |
| **Analyst / Investigator** | Security Analyst、Data Scientist、Product Manager | 事件月度趋势、type×severity 矩阵、操作时间线 | Q4, Q6, Q10, Q12, Q15, Q16 |
| **HR / Org** | 部门管理者（外部接口） | 部门活跃率 | Q7 |

> **注：** "Executive" 不是 `user.role` 里的枚举值，而是由汇报关系隐含的高层角色，本数据集中通过查询而非数据建模来表达。

**你在交付什么。** 三类产物：(1) 合规仪表盘（季度董事会用）；(2) 框架审计报告（合规审计用）；(3) 运营周报（整改追踪用）。这些产物最终递到客户的 CISO、Compliance Manager 和 Risk Manager 手里。SQL 查询文档里的 20 个查询，就是你交付这些产物时实际要写的查询。

---

## 5. 要解决的业务问题

整个数据集和 20 个查询都是为回答下面这 6 组具体问题而存在的。每个问题都能落到具体查询上（详见 SQL 文档）。

1. **高风险模型敞口有多大？** 我们有多少 CRITICAL/HIGH 的模型？生产环境里有多少未缓解（NOT_STARTED）的风险？这是董事会最先问的一句。→ Q1、Q17、Q20
2. **各框架的合规度到哪一步了？** 对 NIST AI RMF 等框架的控制项，我们评估覆盖了多少（进度）？在适用范围内的符合率多少（健康度）？注意 NOT_APPLICABLE 不该进符合率分母。→ Q2、Q14、Q19
3. **风险集中在哪里？** 哪些模型的 risk_score 最高？哪些模型所有者名下扛着过多高风险模型，构成"单点风险"？→ Q3、Q6、Q11、Q12
4. **事件响应跟得上吗？** 平均解决时间（MTTR）多长？事件类型与严重度怎么分布？月度趋势在涨还是在降？→ Q4、Q8、Q15
5. **整改执行得怎么样？** 整改完成率多少？哪些逾期了？负责人工作量是否均衡？→ Q5、Q13、Q18
6. **能否做合规取证？** 某个用户上个月做了哪些操作（是否有可疑的 EXPORT/DELETE）？操作类型整体分布如何？→ Q10、Q16

把这 6 组问题串起来，就是一家企业 AI 治理团队的完整日常：盯敞口、追合规、控风险、应事件、催整改、留证据。

---

## 6. 数据范围概览

- **建模对象**：Sentinel 平台上**单一客户租户**的快照 —— 对应一家刚开始做 AI 治理的中型企业（或大企业的某个事业部），处在 Sentinel 客户画像的下端。
- **时间范围**：过去约 18 个月的历史活动 + 当前正在进行的事件与整改。
- **数据量（口语化）**：11 张表、约 1,400 行。30 名内部用户、50 个被治理的 AI 模型（约 12 个在 `production` 环境）、6 个框架下的 100 个控制项，外加对这些模型做过的评估、发现的事件和对应整改。
- **动态时间锚点（重要约定）**：本数据集**不使用固定的 REFERENCE_DATE 常量**，而是在生成器运行时刻以 `datetime.now()` 为"今天"，所有日期向过去回推。这样做是为了让 `julianday('now')`、`date('now')` 这类查询在"生成后立即运行"时保持判别力，不会因为时间推移而失效。代价是：每次重跑生成器，绝对日期会整体平移，但与"今天"的相对偏移保持不变。**因此请在生成数据后尽快运行 SQL 查询。**
- **刻意的范围取舍**：只建模单租户、Medium 复杂度。一些真实系统会有的实体（独立的证据/附件表、训练数据集追溯、数据主体/同意记录、组织层级、控制项映射多框架的 M:N）被有意简化掉，细节见 ER 文档的"已知简化"。

详细的逐表行数、字段分布和精确分布数字在 ER 文档里，这里只给鸟瞰。

---

## 7. 行业知识科普

这一节是外行在看懂数据前需要补的 30–60 分钟背景。

### 7.1 一个 AI 模型的"治理生命周期"

理解本数据集，关键是理解一个生产 AI 模型会经历什么：

```
注册（register）→ 风险评估（risk assessment）→ 控制项符合性评估（control assessment）
   → 部署上线（deploy）→ 持续监控（monitor）→ 出事件（incident）→ 整改（remediation）
```

数据集的 11 张表正好覆盖这条链路的每一环：`ai_model`（注册）、`risk_assessment`（风险评估）、`model_control_assessment`（控制项符合性）、`security_incident`（事件）、`remediation_action`（整改），再加上 `audit_log`（贯穿全程的操作留痕）。

### 7.2 风险评分是怎么算出来的

AI 治理里最常见的风险量化方式是"可能性 × 影响 × 类别权重"。本数据集严格采用：

```
risk_score = likelihood_score(1–5) × impact_score(1–5) × severity_weight(0.9–1.8)
```

`severity_weight` 由风险类别决定 —— 比如 `ADVERSARIAL`（对抗攻击）权重 1.8 最高，`EXPLAINABILITY`（缺乏可解释性）权重 0.9 最低。所以同样是 likelihood=4、impact=5 的两条评估，对抗攻击类的 risk_score（36）会明显高于可解释性类（18）。取值范围因此落在 0.9（1×1×0.9）到 45（5×5×1.8）之间。

### 7.3 "覆盖率"和"符合率"是两件事

这是合规审计里最容易被混淆、也是本数据集刻意要教会读者区分的一对概念：

- **Coverage Rate（评估覆盖率）= 已评估控制项 / 控制项总数。** 它衡量"审计做完了没"，是**进度**指标。覆盖率低 = 还没评完。
- **Compliance Rate（符合率）= COMPLIANT / 适用评估数。** 它衡量"已评的是否合规"，是**健康度**指标。符合率低 = 发现的问题多。

两者完全独立：覆盖率 90% 但符合率 50%，意思是"评得很全，但一评就发现一半不合规"。

> **NOT_APPLICABLE 陷阱（值得记住）：** 控制项评估有第四种结论 `NOT_APPLICABLE`（该控制项不适用于这个模型）。它**不应**进入符合率的分母 —— 否则等于把"用不上"误算成"不合规"，人为压低符合率。这是 Q14 专门要演示的口径。

### 7.4 事件响应的几个常识

- **severity（严重度）** 分 CRITICAL / HIGH / MEDIUM / LOW 四档，决定响应优先级。
- **status（状态）** 走 OPEN → INVESTIGATING → CONTAINED → RESOLVED → CLOSED 的生命周期。"未关闭事件"= 状态不在 (RESOLVED, CLOSED) 里。
- **MTTR（平均解决时间）** 是关键 SLA 指标，只对已解决的事件有意义。

### 7.5 部署环境与风险等级

- **deployment_env**：`production` / `staging` / `development` / `canary`，**全小写**。生产环境的问题直接影响业务，高管最关心 `production`。注意 SQL 比较大小写敏感。
- **risk_tier**：模型层级的风险标签 CRITICAL / HIGH / MEDIUM / LOW。它和 risk_score 是**两个独立**的东西 —— risk_tier 是模型上的标签，risk_score 是单条评估的数值。

---

## 8. 术语表（Glossary）

ER 文档和 SQL 查询里出现的术语，统一在这里解释。英文术语保留英文，括号给中文白话解释。

| 术语 | 白话解释 | 为什么在这里重要 |
|------|---------|----------------|
| **GRC** | Governance, Risk, Compliance，治理 / 风险 / 合规软件 | Sentinel 所属的大赛道 |
| **AI Governance** | AI 治理：证明 AI 系统安全、合规、可控的一整套流程 | 本数据集模拟的业务本身 |
| **MLOps** | 管理 ML 模型训练 / 部署 / 监控的工程实践 | Sentinel 从中取数据，不替代它 |
| **SIEM** | 安全信息与事件管理系统 | 安全事件的上游来源 |
| **CISO** | Chief Information Security Officer，首席信息安全官 | 数据集里"高管"persona 的典型代表 |
| **NIST AI RMF** | 美国 NIST 的 AI 风险管理框架（1.0，2023） | 数据里 6 个框架之一，事实标准 |
| **GDPR** | 欧盟通用数据保护条例 | 框架之一，含自动化决策解释权 |
| **HIPAA** | 美国健康保险流通与责任法，医疗数据保护 | 框架之一，医疗客户必备 |
| **OWASP AI Top 10** | OWASP 列出的 10 大 AI 安全漏洞 | 框架之一，偏技术安全 |
| **ISO 27001** | 国际信息安全管理标准 | 框架之一 |
| **SOC 2 Type II** | 面向 SaaS 的持续运营有效性审计标准 | 框架之一 |
| **SR 11-7** | 美联储/OCC 的模型风险管理指引 | 银行客户把它延伸到 AI 模型 |
| **EU AI Act** | 欧盟 AI 法案（2024 通过） | 推动合规需求的宏观监管 |
| **Risk Tier** | 模型层级的风险标签：CRITICAL/HIGH/MEDIUM/LOW | "高风险模型"约定为 risk_tier IN ('CRITICAL','HIGH') |
| **Risk Score** | `likelihood × impact × severity_weight`，单条评估的综合分（0.9–45） | 与 risk_tier 独立；评估层级的数值 |
| **Coverage Rate** | 已评估控制项 / 控制项总数 | 进度指标，"审计做完没" |
| **Compliance Rate** | COMPLIANT / 适用评估数 | 健康度指标，"已评的合不合规" |
| **Applicable Assessment** | `compliance_status != 'NOT_APPLICABLE'` 的评估 | 符合率分母只算这些 |
| **NOT_APPLICABLE** | 评估结论之一："该控制项不适用于此模型" | 不应进符合率分母（Q14 陷阱） |
| **Stale Audit** | `last_audit_date` 为 NULL 或距今 > 180 天 | Q19 的核心定义 |
| **Open Incident** | `status NOT IN ('RESOLVED','CLOSED')` 的事件 | 即 OPEN/INVESTIGATING/CONTAINED |
| **Open Remediation** | `control_status.is_terminal = 0` 的整改 | 即 PENDING/IN_PROGRESS/DEFERRED |
| **Production Model** | `deployment_env = 'production'` 且 `is_active = 1` | 注意 production 全小写 |
| **MTTR** | Mean Time To Resolve，平均解决时间（小时） | 仅对已 RESOLVED/CLOSED 事件有意义 |
| **Overdue** | `due_date < 今天` 且未完成（is_terminal=0） | 逾期整改 |
| **mitigation_status** | 风险评估的缓解状态：NOT_STARTED/IN_PROGRESS/MITIGATED/ACCEPTED/TRANSFERRED | NOT_STARTED = 未缓解 |
| **compliance_status** | 控制项评估结论：COMPLIANT/PARTIALLY_COMPLIANT/NON_COMPLIANT/NOT_APPLICABLE | 符合率口径的基础 |
| **MCA** | `model_control_assessment` 桥接表的简称 | "模型×控制项符合性"的核心动作记录 |
| **多态引用（polymorphic reference）** | `audit_log.(entity_type, entity_id)` 指向不同表，无 schema FK | 取证时需按 entity_type 选 join 目标 |
| **XOR 互斥** | `remediation_action` 的 incident_id 与 risk_assessment_id 恰好一个非空 | 每条整改有且仅有一个上游触发源 |
| **row-inflation** | LEFT JOIN 一对多下游表后聚合被倍乘的陷阱 | Q11 用 COUNT(DISTINCT CASE) 修复 |

> 缩写首次出现时给全称；如果你觉得这张表偏短，说明还有术语没解释 —— 但本数据集的术语基本都收录在此。

---

## 9. 关键指标与公式

下表是平台的核心 KPI。每个写明公式（用数据集里的真实字段）、解读，以及对应的 SQL 查询编号。

| KPI | 公式 | 解读 | 对应查询 |
|-----|------|------|---------|
| **Assessment Coverage Rate** | `COUNT(DISTINCT mca.control_id) / COUNT(DISTINCT cc.id)` | 框架下已评估控制项占比，衡量"审计做完没" | Q14 |
| **Compliance Rate**（适用口径） | `SUM(status=COMPLIANT) / SUM(status != NOT_APPLICABLE)` | 适用范围内的合规健康度。**分母排除 NOT_APPLICABLE** | Q14 |
| **Audit Coverage Gap** | `COUNT(active_models WHERE last_audit_date IS NULL OR julianday('now') - julianday(last_audit_date) > 180)` | 长期未审计的活跃模型数。健康值应 < 30% | Q19 |
| **MTTR**（Mean Time To Resolve） | `AVG((julianday(resolved_at) - julianday(reported_at)) * 24)` 小时 | 事件平均解决时间，关键 SLA | Q8 |
| **Remediation Completion Rate** | `SUM(status_id=3) / COUNT(*)` | 整改完成率，运营 KPI | Q5 |
| **High-Risk Model Share** | `COUNT(risk_tier IN ('CRITICAL','HIGH')) / COUNT(*)` 活跃模型 | 高风险模型占比，董事会指标 | Q1, Q17, Q20 |
| **Risk Score** | `likelihood_score × impact_score × severity_weight` | 单条评估的综合风险评分（0.9 ~ 45） | Q3, Q6, Q11, Q17 |
| **Overdue Remediation Count** | `COUNT(due_date < date('now') AND is_terminal=0)` | 逾期整改数，每周向管理层汇报 | Q13, Q20 |
| **Open Incident Count** | `COUNT(status NOT IN ('RESOLVED','CLOSED'))` | 未关闭事件数 | Q20 |
| **Owner Concentration Risk** | 单个 owner 名下 `CRITICAL + HIGH` 模型数 | 模型所有者的单点风险 | Q11 |
| **Assignee Workload** | `COUNT(*) PER assigned_to_id` | 整改负责人分配数，衡量是否过载 | Q18 |

> **口径一致性提醒：** "高风险模型"在所有查询中统一为 `risk_tier IN ('CRITICAL','HIGH')`；"production" 统一为 `deployment_env = 'production'`（全小写）；防除零统一用 `NULLIF(分母, 0)`。这些约定贯穿 20 个查询，避免同一指标出现两种算法。

---

## 10. 典型业务场景（用户故事）

下面 5 个场景把数据集"放回"真实日常工作流，帮助理解为什么 11 张表的组合能支撑这些场景：

**场景 1 · 周一晨会（运营经理）** —— "这周有多少整改逾期？谁负责得最多？高优先级里有什么紧急的？"
→ Q13（逾期清单）+ Q18（负责人工作量）+ Q9（高优先级未完成）

**场景 2 · 季度董事会（CISO 汇报）** —— "我们高风险模型占比多少？CRITICAL 事件有多少没关？未来 6 个月合规敞口在哪？"
→ Q20（关键指标仪表盘）+ Q1（高风险概览）+ Q17（生产环境风险汇总）

**场景 3 · 新框架上线（Compliance Manager）** —— "我们对 NIST AI RMF 的控制项评估覆盖了多少？符合率多少？哪些还没评？"
→ Q14（覆盖率与符合率）+ Q2（框架控制项分布）+ Q19（审计覆盖检查）

**场景 4 · 事件响应（Security Analyst）** —— "上个月 PROMPT_INJECTION 事件多少？平均多久解决？类型与严重度的关系？"
→ Q4（月度趋势）+ Q8（MTTR）+ Q15（type×severity 交叉）

**场景 5 · 合规取证（Compliance Auditor）** —— "用户 ID=5 上个月做了哪些操作？有没有未授权的 EXPORT？未缓解的高风险评估有哪些？"
→ Q16（用户操作追踪）+ Q10（操作类型分布）+ Q3（未缓解高风险）

---

读到这里，你已经知道 Sentinel 是谁、靠什么赚钱、这个行业为什么重要、你在项目里扮演什么角色、要回答哪些业务问题，以及关键术语和指标怎么算。接下来请打开 ER 文档了解**数据长什么样**，再用 SQL 文档**动手回答这些问题**。
