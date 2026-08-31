# Stratosend 需求生成与营销运营业务背景

> **数据集:** `b2b_saas_demand_generation_high`
> **复杂度:** 高 (16 张表, 约 118,000 行)
> **市场:** 北美 (货币 USD)
> **REFERENCE_DATE (参考"今天"):** `2026-06-01`
> 数据层细节 (表结构, 字段, DDL, 数据生成规则) 请见 `02-b2b_saas_demand_generation_high_er_document-cn.md`。具体 SQL 示例请见 `03-b2b_saas_demand_generation_high_sql_queries-cn.md`。

本文档是整个数据集的"开场白"。它先讲清楚 Stratosend 这家虚构公司是谁、靠什么赚钱、所在行业怎么运转,再讲清楚你在这家公司里扮演什么角色、要回答哪些业务问题,最后把所有会在表和查询里反复出现的术语和指标公式一次性讲明白。读完它,一个刚加入项目的新人应该能在第一次站会上听懂大家在聊什么。

---

## 1. 公司速写

**Stratosend** 是一家虚构的北美 B2B SaaS 公司,总部位于美国科罗拉多州丹佛 (Denver, Colorado)。公司由几位前 SRE (网站可靠性工程师) 和平台工程师在 2018 年创立,卖的是一套 **API 可观测性平台 (API Observability Platform)**。你可以把它想象成市面上那些专注监控 API 性能、错误率、延迟和服务依赖关系的工具:当一家公司的线上 API 变慢或报错时,Stratosend 帮工程团队在几分钟内定位是哪个服务、哪条调用链出了问题,而不是花几个小时翻日志。

公司规模属于成长期 (order of magnitude): 大约 200 名员工,客户名册里有约 2,000 家公司 (account),其中已成交的付费客户约 280 家,年度经常性收入 (ARR) 在数千万美元的量级。营收按三个客户层级 (tier) 划分,层级决定了销售模式、单笔合同规模和销售周期长度。

| 层级 | 客户画像 | 单笔订单规模 (USD) | 销售模式 |
|------|----------|----------------|----------|
| **SMB** | 员工 100 人以下 | $5K 到 $25K | 自助服务加轻度跟进 |
| **Mid-Market** | 员工 100 到 1,000 人 | $25K 到 $100K | AE 主导销售 |
| **Enterprise** | 员工 1,000 人以上 | $100K 到 $500K 以上 | 多干系人 POC, 6 到 12 个月销售周期 |

和这份数据相关的组织架构 (这些头衔会在 SQL 查询里以业务角色出现):

- **高管层:** CEO, CMO (首席营销官), CFO (首席财务官), CRO (首席营收官)。
- **市场团队 (Marketing):** VP Marketing, Demand Gen Manager (需求生成经理, 管入站营销活动), Content Marketing (内容营销, 做白皮书和网络研讨会), Field Marketing (线下展会), Marketing Ops (营销运营, 管数据和工具栈), ABM Lead (ABM 负责人)。
- **销售团队 (Sales):** VP Sales, SDR/BDR (做首次触达和资格筛查), AE_SMB / AE_Mid / AE_Enterprise (按层级负责成交), 以及各团队的 Manager。
- **营收运营 (Revenue Operations, RevOps):** 横跨市场和销售,负责归因、预测和管道分析。这是你所在的团队。

---

## 2. 商业模式

Stratosend 赚的是**订阅费**。客户按年 (有时按多年) 签约,支付一笔年度经常性收入 (ARR),换取在合同期内持续使用平台的权利。定价由两部分组成:一部分是按席位 (使用平台的工程师人数),另一部分是按用量 (监控的主机数量和接入的数据量)。客户用得越多,账单越大,这就是 SaaS 典型的 land and expand (先小后大) 路径: 先签一个部门的小单,用出价值后再扩展到全公司。

谁来买?买家几乎全是**工程组织**而不是采购部门主导。一笔交易里通常涉及多个角色: 真正天天用产品的工程师 (Champion 和 Influencer)、掌握预算的工程经理 (Economic Buyer)、最终拍板的 VP Engineering 或 CTO (Decision Maker),以及负责合规和合同的安全或采购或法务 (Blocker)。层级越高,卷入的人越多,Enterprise 单子常常要 5 到 7 个干系人点头才能成。

钱怎么挣的,从单位经济 (unit economics) 角度看有三件事最关键:

- **毛利率高。** 软件交付的边际成本低,SaaS 毛利率通常在 75% 到 85%。Stratosend 主要的成本不在交付,而在获客。
- **获客成本要能回本。** 公司花在营销活动和销售人力上的钱 (CAC, 获客成本) 必须能被客户后续的订阅费在合理时间内赚回来。健康的目标是 SMB 客户 18 个月内回本, Enterprise 客户 24 个月内回本。
- **续约和扩展决定长期价值。** 单个客户的生命周期价值 (LTV) 取决于它续约几年、扩展多少。LTV 和 CAC 的比值 (LTV/CAC) 是衡量增长是否可持续的核心指标。

这就是为什么营销和销售的每一块钱花得值不值,是这家公司天天要算的账,也是这份数据集存在的理由。

---

## 3. 行业概览

如果你来自别的行业,这一节帮你快速理解 API 可观测性这个市场在做什么。

**这个行业创造什么价值。** 现代软件由成百上千个互相调用的服务 (microservices) 拼成,任何一个环节变慢或出错,用户看到的就是页面转圈或报错。可观测性工具的作用,是把这些服务运行时产生的三类信号 (指标 metrics、日志 logs、链路追踪 traces) 收集起来,让工程师能回答"现在哪里出问题了、为什么、影响多大"。它直接对应一个硬指标 MTTR (平均修复时间): 工具越好,故障从发生到修复的时间越短,公司因宕机损失的钱就越少。

**主要玩家类别 (不点名真实公司)。** 这个市场大致分几类: 老牌的 APM (应用性能管理) 厂商、专做日志管理的平台、专做分布式链路追踪的工具、做基础设施监控的厂商,以及试图把这些全做进一个平台的"全栈可观测性"套件。Stratosend 走的是聚焦路线,主打 API 这一层的性能、错误和依赖图。

**相关的合规框架。** 这个行业本身不像金融或医疗那样有专门的行业监管机构,但因为工具要接入客户的生产系统和数据,**安全和隐私合规**是 Enterprise 客户采购时的硬门槛。常见的有 SOC 2 Type II 和 ISO 27001 (安全认证),以及数据隐私法规: 美国加州的 CCPA、加拿大的 PIPEDA、面向欧洲客户时的 GDPR。这也是为什么交易里总有一个 Blocker 角色 (安全或法务) 要过一遍风险评审。

**当下塑造这个行业的几股力量。** 第一,OpenTelemetry 这套开源标准正在统一数据采集方式,降低了客户更换厂商的门槛,竞争更激烈。第二,AI 驱动的异常检测成了卖点,大家都在比谁能更早自动发现问题。第三,"可观测性成本爆炸"成了客户的痛点: 数据量越大账单越高,客户开始精打细算、压缩用量,这给厂商的营收扩展带来压力。第四,平台整合 (consolidation) 在加速,客户更想用一个平台而不是七个工具。读完这一节,你应该能在和工程师或销售聊天时接得上话。

---

## 4. 你的角色与项目

你是 Stratosend **营收运营 (RevOps) 团队的一名数据分析师**,直接向 RevOps 负责人汇报。RevOps 这个团队的特殊之处在于它横跨市场和销售两边,谁也不偏袒,专门用数据把"从一个陌生 lead 到一笔成交营收"这条完整链路讲清楚。

你的日常产出有两类:

- **维护标准化 BI 仪表盘。** 公司有一套分三层的仪表盘体系: 给高管看的战略层 (季度营销 P&L、管道健康、CFO 单位经济等),给经理看的运营层 (每日漏斗、SDR 产能、活跃 campaign 跟踪等),以及给分析师自己用的探索层。这些仪表盘背后的 SQL 就是你写的。
- **回答临时性的业务问题 (ad-hoc analysis)。** CMO 在季度评审前想知道哪个渠道该砍预算; VP Sales 周一早上想知道管道够不够完成配额; CFO 想知道按渠道拆分的获客成本。这些没法用固定仪表盘控件回答的问题,落到你头上做一次性分析。

这些产出最终服务于季度业务评审 (QBR) 和董事会材料准备。换句话说,你写的查询不是练习题,而是真的会变成 CMO 给董事会汇报时那张图、或者 VP Sales 决定要不要紧急加派 SDR 的那个数字。

---

## 5. 要解决的业务问题

整个项目围绕五个具体的业务问题展开。后面 ER 文档里埋的数据分布、以及 SQL 文档里的每一条查询,都能追溯回其中某一个。

- **Q1 漏斗在哪里漏 (Funnel Leakage)。** 从 Lead 到 MQL 到 SQL 到 Opportunity 再到 Closed-Won,每一步的转化率是多少?哪一步流失最严重?lead 的质量是否随来源渠道或随季度在衰减?这是项目的招牌问题。
- **Q2 哪些 campaign 和渠道真正带来营收 (Attribution)。** 用 W-shaped 多触点归因,对比只看首次触点 (first-touch) 或末次触点 (last-touch) 的简单归因,到底哪些 campaign 类型和 lead source 产生的影响管道 (influenced pipeline) 和 ROI 最高?哪些该追加预算,哪些该砍掉?
- **Q3 管道健康度和预测是否可信 (Pipeline & Forecast)。** 当前的 open pipeline 够不够覆盖团队配额 (经典的 3x coverage 法则)?各阶段推进速度如何?有多少 opp 已经停滞 (stale) 或反复滑期 (slipped, 成交日期一推再推)?按胜率加权的预测是多少?
- **Q4 销售团队产能与 SLA (Sales Productivity)。** SDR 是否在 lead 成为 MQL 后 24 小时内完成首次跟进 (SLA 合规)?外呼 sequence 各步的回复率怎么衰减?各 AE 的配额达成率排名如何?新销售从入职到第一单要多久 (ramp time)?
- **Q5 ABM 战略客户的互动效果 (ABM)。** 对 Tier-1 目标客户,我们是否覆盖了足够多的干系人 (stakeholder coverage)?哪些目标客户已经很久没人碰了?ABM 客户的胜率比非 ABM 高多少?有多少客户产生了二次扩展 (account expansion)?

---

## 6. 数据范围速览

这份数据集是 Stratosend 的 CRM 加营销自动化系统在某一时点的快照,锚定在 **REFERENCE_DATE = 2026-06-01** (所有"今天""过去 30 天"之类的语义都以这一天为准)。

- **时间跨度:** 18 个月的历史,从 2024-12-08 到 2026-06-01。此外还包含正在进行的 ACTIVE 营销活动,以及未来 30 天的 PLANNED 营销活动 (只有计划元数据,没有互动数据)。
- **数据量 (用大白话说):** 大约两千家公司、八千个 lead、三千多个 contact、一千六百多个销售机会 (opportunity),再加上几张事件级的大表 (约 4.5 万条 lead 评分事件、3 万封销售邮件、1.8 万条内容互动)。合计约 11.8 万行,分布在 16 张表里。
- **刻意的范围选择:** 市场聚焦北美。约 72% 的客户在美国,其余分布在加拿大、英国、德国、澳大利亚、法国等地,但叙事和监管参照都以北美为默认。整份数据只覆盖 Stratosend 一家公司,不掺杂竞品或外部市场数据。

具体每张表的字段、行数和依赖关系不在这里展开,请看 ER 文档。

---

## 7. 行业知识科普

这一节是一个外行在看懂数据前需要的三十分钟背景。读完它,后面的术语表和指标公式会顺很多。

**需求生成漏斗 (Demand Generation Funnel)。** B2B SaaS 的获客是一条逐级筛选的漏斗,每一级都是一道"资格门":

1. **Lead (线索):** 任何留下联系方式的潜在买家个人 (下载了白皮书、报名了网络研讨会、填了 demo 申请)。漏斗最顶端,数量最大,质量参差。
2. **MQL (Marketing Qualified Lead, 市场合格线索):** 行为足够活跃、被市场判定值得销售跟进的 lead。怎么判定?靠 lead scoring。
3. **SQL (Sales Qualified Lead, 销售合格线索):** 注意,这里的 SQL 不是查询语言,而是"销售合格线索"。指 SDR 打过招呼、确认确实有需求和预算、值得转给 AE 的 lead。
4. **Opportunity (销售机会, 简称 opp):** 一个真正进入销售流程、有金额有预期成交日期的交易。
5. **Closed-Won / Closed-Lost (赢单 / 输单):** 交易的最终结局。

**Lead Scoring (线索评分)。** 系统给 lead 的每个行为打分 (访问定价页 +20 分,下载内容 +15 分,参加网络研讨会 +30 分,退订 -50 分等)。累计分数第一次越过阈值 (本数据集是 100 分) 的那一刻,这个 lead 就升级为 MQL,对应字段 `mql_date`。

**ARR 与 MRR。** ARR (Annual Recurring Revenue, 年度经常性收入) 是订阅制 SaaS 的命脉指标,指一年内可重复确认的合同金额。MRR 是它的月度版本 (ARR ÷ 12)。本数据集的金额一律用 ARR 表示。

**七阶段销售流程 (Sales Stages)。** opp 在这些阶段间推进,每个阶段有一个标准胜率 (用于加权预测):

| 阶段 | 含义 | 标准胜率 |
|------|------|----------|
| Discovery | 初步接触, 摸需求 | 10% |
| Demo | 产品演示 | 25% |
| Evaluation/POC | 评估或概念验证 | 40% |
| Proposal | 报价提案 | 60% |
| Negotiation | 商务谈判 | 80% |
| Closed-Won | 赢单 | 100% |
| Closed-Lost | 输单 | 0% |

**销售角色分工。** SDR (Sales Development Rep) 负责漏斗前段: 首次触达和资格筛查,把 Lead 推成 MQL 和 SQL,通常没有营收配额。AE (Account Executive) 负责后段: 从 demo 到成交,背着年度 ARR 配额,并按客户层级分工 (AE_SMB / AE_Mid / AE_Enterprise)。

**B2B 五角色买家框架 (Buyer Personas)。** 一笔 B2B 交易不是一个人说了算,数据里用五个 persona 刻画买方决策单元:

| Persona | 在交易中的角色 |
|---------|----------------|
| Champion | 内部推动采纳的人 (通常是高级工程师或 Tech Lead) |
| Economic Buyer | 掌握预算的人 (工程经理或总监) |
| Decision Maker | 最终拍板的人 (VP Engineering 或 CTO) |
| Influencer | 日常使用并施加影响的人 (DevOps 或 SRE) |
| Blocker | 可能踩刹车的人 (安全, 采购, 法务) |

**归因模型 (Attribution Models)。** 一笔成交往往经过很多个营销触点,功劳怎么分?有三种常见算法。**First-touch (首次触点)** 把全部功劳给第一个触点,**Last-touch (末次触点)** 全给最后一个触点,两者都太极端。**W-shaped (W 型)** 是 B2B 常用的折中: 把功劳拆成首次触点 30%、转成 MQL 的那个触点 30%、创建 opp 前最后一个触点 30%,剩下 10% 平摊给路径上其它影响者。Q2 的核心就是用 W 型去纠正 first-touch 的偏差。

**ABM (Account-Based Marketing, 基于客户的营销)。** 和"广撒网钓 lead"相反,ABM 是先圈定一批高价值目标客户 (target account),再集中火力围着这些客户里的多个干系人做精准触达。客户按优先级分 Tier 1 / Tier 2 / Tier 3。衡量 ABM 效果看两件事: 一个客户里覆盖了几个不同 persona (stakeholder coverage),以及目标客户多久没被碰过 (no-touch days)。

**Gated Content (门控内容)。** 有些营销内容 (电子书、白皮书) 需要填表单才能下载,这一填就产生了一个新 lead,所以叫"门控"。非门控内容 (博客) 直接看,不产生 lead,但能培育已有 lead。

---

## 8. 术语表

ER 文档和 SQL 查询里出现的术语,在这里一次讲清。每条给出英文原词、一句大白话解释,以及它在本数据集里为什么重要。

| 术语 | 大白话解释 | 为什么重要 |
|------|------------|------------|
| **ARR** (Annual Recurring Revenue) | 一年内可重复确认的订阅收入 | 本数据集所有金额的口径; 是营收、配额、预测的基础单位 |
| **MRR** (Monthly Recurring Revenue) | ARR 的月度版 (ARR ÷ 12) | 计算 CAC 回收期时按月折算要用到 |
| **Lead** | 留下联系方式的潜在买家个人 | 漏斗最顶端的实体, 一切转化的起点 |
| **MQL** (Marketing Qualified Lead) | 行为活跃到值得销售跟进的 lead | 市场和销售的交接点; 漏斗第二级门槛 |
| **SQL** (Sales Qualified Lead) | 经 SDR 确认有需求有预算的 lead (不是查询语言) | 漏斗第三级门槛; 真正进入销售流程前的最后一关 |
| **Opportunity / Opp** | 有金额有预期成交日的真实交易 | 核心营收实体; 管道和预测都基于它 |
| **Account** | 一家潜在或已成交的客户公司 | 多干系人销售的容器; 一个 account 下挂多个 contact 和 opp |
| **Contact** | account 下被销售触达的具体个人 | opp 的主要联系人; 由 lead 转化或直接外呼建立 |
| **SDR / BDR** (Sales / Business Development Rep) | 做首次触达和资格筛查的销售 | 负责把 Lead 推成 MQL 和 SQL; SLA 和 sequence 指标的主角 |
| **AE** (Account Executive) | 背配额、负责成交的销售 | 管道归属和配额达成的主体; 按客户层级分工 |
| **RevOps** (Revenue Operations) | 横跨市场和销售的数据与流程团队 | 你所在的团队; 负责归因、预测、管道分析 |
| **Demand Gen** (Demand Generation) | 用营销活动持续制造需求和 lead | 市场团队的核心职能; campaign 表现的归属 |
| **ICP** (Ideal Customer Profile) | 最理想的目标客户画像 | 判断 lead 是否值得追、是否该 disqualify 的标尺 |
| **Persona** | 买家在决策单元里的角色原型 | 五角色框架 (Champion 等); ABM 干系人覆盖的维度 |
| **Lead Scoring** | 按行为给 lead 累计打分 | 累计过 100 分即成 MQL; 决定 mql_date |
| **CAC** (Customer Acquisition Cost) | 获取一个新客户的平均成本 | 单位经济的核心; 太高说明获客不划算 |
| **CPL** (Cost Per Lead) | 获取一个 lead 的平均成本 | 渠道效率对标; 按 lead source 不同差异很大 |
| **LTV** (Lifetime Value) | 一个客户生命周期内贡献的总价值 | 和 CAC 配对看增长是否可持续 |
| **LTV/CAC** | 生命周期价值与获客成本的比值 | SaaS 健康度黄金指标, 通常目标 3 以上 |
| **Payback Period** | 用订阅收入赚回 CAC 所需的月数 | CFO 关心的回本速度; SMB 目标 18 个月内 |
| **Pipeline** | 所有未关闭 opp 的金额合计 | 未来营收的蓄水池; 健康度看覆盖率 |
| **Pipeline Coverage** | open pipeline 与配额的比值 | 经典 3x 法则; 低于 3x 要紧急补管道 |
| **Win Rate** | 已关闭 opp 中赢单的比例 | 销售效率的核心; 口径为 Wins ÷ (Wins + Losses) |
| **Sales Cycle** | 从创建 opp 到赢单的时长 | 按层级差异巨大 (SMB 短, Enterprise 长) |
| **Stage Velocity** | opp 在每个阶段停留的天数 | 找出卡点阶段, 优化推进速度 |
| **Stale Opportunity** | 30 天以上没有阶段流转的 open opp | 容易最终丢失的危险信号 |
| **Slipped Deal** | 预期成交日反复推迟的 opp | 预测不可信的来源; 用历史快照检测 |
| **Weighted Forecast** | 按阶段胜率加权的管道预测 | 比裸 pipeline 更接近真实可成交金额 |
| **Quota / Quota Attainment** | AE 的年度配额 / 达成率 | 销售产能考核的核心 |
| **Attribution** | 把成交功劳分配给营销触点 | 决定预算往哪投; 分 first-touch / last-touch / W-shaped |
| **Influenced Pipeline** | 被某 campaign 触达过的客户的管道金额 | 衡量 campaign 真实影响力, 比首触点更宽 |
| **ABM** (Account-Based Marketing) | 围着选定的高价值客户做精准营销 | Q5 的核心; 对应 target_account_list |
| **Target Account** | 被列入 ABM 名单的战略客户 | is_target_account 字段; 偏向 Mid 和 Enterprise |
| **Tier 1/2/3** | ABM 目标客户的优先级分级 | 资源投入和触达频率的依据 |
| **Stakeholder Coverage** | 一个目标客户里触达的不同 persona 数 | ABM 深度指标; 覆盖越全成单概率越高 |
| **SLA** (Service Level Agreement) | 此处指 MQL 后 24 小时内跟进的承诺 | SDR 产能考核; 跟进越快转化越好 |
| **Sequence / Cadence** | 多步骤的自动化外呼邮件序列 | sales_email 的组织单位; 各步回复率衰减 |
| **Open / Click / Reply / Bounce Rate** | 邮件打开 / 点击 / 回复 / 退信比例 | 外呼健康度; 字段为累计型 (点击蕴含打开) |
| **Gated Content** | 需填表才能获取的门控内容 | 门控产生 lead, 非门控只做培育 |
| **NAICS** (North American Industry Classification System) | 北美行业分类代码 | industry 表用它给客户行业打标签 |
| **NRR** (Net Revenue Retention) | 含扩展和流失的净收入留存率 | 衡量老客户价值增减; 本数据集以扩展 opp 间接体现 |

---

## 9. 关键指标与公式

下面是会在 SQL 查询里反复计算的核心指标。公式用 SQL 风格的伪代码表示。凡是同一指标存在两种常见口径的,这里明确选定一种,以免下游查询各算各的对不上。

### 9.1 漏斗指标 (对应 Q1)

```text
Lead -> MQL Rate   = COUNT(lead WHERE mql_date IS NOT NULL) / COUNT(lead)
MQL -> SQL Rate    = COUNT(lead WHERE sql_date IS NOT NULL) / COUNT(lead WHERE mql_date IS NOT NULL)
Overall Lead->Won  = COUNT(won opp 来源的 distinct lead) / COUNT(lead)
Disqualification Rate = COUNT(lead WHERE status='disqualified') / COUNT(lead)
MQL Aging (days)   = 已处理: AVG(sql_date - mql_date); 未处理: REFERENCE_DATE - mql_date
```

口径约定: 一个 lead 是否为 MQL 一律以 `mql_date IS NOT NULL` 判断,而不是看 `status` 字段,因为 lead 越过 MQL 后状态会继续往后走 (sql / converted)。

### 9.2 Campaign 与内容指标 (对应 Q2)

```text
Cost per MQL       = campaign.spend_to_date_usd / (该 campaign 首触带来的 MQL 数)
Influenced Pipeline = SUM(opp.amount_usd)  -- opp 的 account 上有该 campaign 的任意成员
Pipeline ROI       = Influenced Pipeline / campaign.spend_to_date_usd
Spend Utilization  = spend_to_date_usd / total_budget_usd
Plan Achievement (MQL) = 实际 MQL 数 / campaign.target_mql_count
```

口径约定: Cost per MQL 用**首次触点**口径 (`lead.source_campaign_id`), 因为它衡量的是 campaign 自己直接拉来的 lead; 而 Influenced Pipeline 用更宽的**账户级影响**口径。两者不可混用。

### 9.3 管道与预测指标 (对应 Q3)

```text
Open Pipeline      = SUM(opp.amount_usd) WHERE opportunity_stage.is_closed = 0
Weighted Forecast  = SUM(opp.amount_usd * opportunity_stage.typical_win_probability_pct / 100)  -- 仅 open opp
Win Rate           = Wins / (Wins + Losses)   -- 不含 open opp
Average Deal Size  = AVG(opp.amount_usd) WHERE is_won = 1
Median Sales Cycle = MEDIAN(actual_close_date - created_at) WHERE is_won = 1
Coverage Ratio     = Open Pipeline / SUM(active AE quota_usd)
Stale Rate         = COUNT(open opp WHERE MAX(transitioned_at) < REFERENCE_DATE - 30) / COUNT(open opp)
```

口径约定: Win Rate 的分母只算已关闭 opp (赢 + 输), 不把 open opp 算进去, 否则胜率会被在途交易稀释。

### 9.4 销售生产力指标 (对应 Q4)

```text
Quota Attainment   = SUM(won opp.amount_usd) / sales_rep.quota_usd
Open / Click / Reply / Bounce Rate = SUM(对应布尔字段) / COUNT(sales_email)
SLA Compliance     = COUNT(MQL WHERE 首封 SDR 邮件在 mql_date 后 24 小时内) / COUNT(MQL)
Sequence Step Decay = SUM(replied) / COUNT(*)  GROUP BY sequence_step
Ramp Time (days)   = MIN(won opp.actual_close_date) - sales_rep.hire_date
```

### 9.5 归因与单位经济指标 (对应 Q2 和 CFO 视角)

```text
First-touch Pipeline (per source) = SUM(won opp.amount_usd) GROUP BY opp.source_id
W-shaped Credit (per campaign)    = SUM(opp.amount_usd * campaign_member.attribution_credit_pct / 100)
Blended CAC        = SUM(campaign.spend_to_date_usd) / COUNT(distinct won account)
CAC Payback (months) = CAC / (avg_arr / 12)
LTV/CAC            = (avg_arr * 假设留存年数) / CAC
```

### 9.6 ABM 指标 (对应 Q5)

```text
Stakeholder Coverage = COUNT(DISTINCT contact.persona)  -- 每个目标 account
No-Touch Days        = REFERENCE_DATE - MAX(engaged_at 或 sent_at)  -- 每个目标 account
Tier-1 ABM Win Rate  = Wins / Opps  -- 仅限 Tier-1 目标客户
Account Expansion    = COUNT(account WHERE COUNT(won opp) > 1)
```

这些公式的完整 BI 字典 (含数据来源表和主题域归属) 在 ER 文档的 KPI 字典一节有更细的展开, 此处只列读懂查询所必需的核心定义。
