# Crestline 房地产经纪 — 市场情报原始数据：业务背景

> 本文档是数据集 `real_estate_brokerage_market_intelligence_raw_data_high` 的业务背景说明。
> 它回答"**为什么**"：这是一家什么公司、靠什么赚钱、所在行业怎么运转、这个数据项目要解决什么问题。
> 表结构、字段、生成规则等"**是什么**"的内容见 `02-real_estate_brokerage_market_intelligence_raw_data_high_er_document-cn.md`；
> 可直接运行的分析查询见 `03-real_estate_brokerage_market_intelligence_raw_data_high_sql_queries-cn.md`。

读这份文档的人，假设是刚加入项目的实习生或新分析师：不要求懂房地产，但读完这一份就能在第一次站会上听懂同事说的行话。全程默认市场是北美（美国加州 + 华盛顿州），货币是 USD，监管机构是美国的 DRE、NAR、CFPB 等。

---

## 1. 这家公司：Crestline Realty

**Crestline Realty** 是一家虚构的中等规模住宅地产经纪公司（residential real estate brokerage），总部在加州旧金山（San Francisco, CA）。它帮普通人买房和卖房，自己**不拥有**房子，是一个持牌的中间人。

规模（都是数量级，不是精确财报数字）：

- **约 200 名持牌经纪人（real estate agent）**，分布在三个区域市场。
- **8 个办公室**，覆盖 Bay Area（湾区）、Southern California（南加州）、Pacific Northwest（太平洋西北，主要是西雅图都会区）。
- 每年大约成交 **2,500–3,000 笔**房屋交易。
- 在所覆盖的每个区域里，Crestline 的真实街头市场份额只有 **2–3%** —— 它是一个"挑战者"，不是龙头。竞争对手是 Compass、Coldwell Banker、Keller Williams、Redfin、Berkshire Hathaway HomeServices、Sotheby's、RE/MAX、Side 这些大牌。

Crestline 的管理层赌的是一件事：**靠"给经纪人更好的数据和工具"来抢份额**，而不是靠砸广告或拼规模。这就是本数据集背后那个"市场情报平台"项目存在的原因。

会在后面 SQL 查询里反复出现的关键人物（公司组织架构）：

| 角色 | 姓名 | 职责 |
|------|------|------|
| CEO | （未具名） | 对董事会讲增长故事，关心市场份额趋势 |
| VP of Operations（运营副总裁） | Sarah Mitchell | 每周领导层例会的主持人，盯成交量、office 计分卡、失单原因 |
| Bay Area Regional Manager（湾区区域经理） | Rachel Torres | 管一线 agent，盯陈旧 listing、管道速率、季度"总裁俱乐部"排名 |
| Analytics Lead（分析团队负责人） | Emily Zhang | 带分析师做 ad-hoc 取数，正在把 Excel 流程搬到 dashboard |
| Tech Lead（技术负责人） | Marcus Rivera | 负责数据平台、自然语言取数、AI 分析 |
| Finance / Controller（财务/主计长） | （未具名） | 做佣金 payout 现金流预测、payroll 预览 |

---

## 2. 商业模式：佣金，且只有佣金

Crestline 的钱**全部来自佣金（commission）**。理解这套经济模型是理解整个数据集的关键，因为几乎每张表都在追踪"一笔可能产生佣金的交易，现在走到哪一步了"。

一笔典型成交的钱是这样分的：

1. 房子成交时，按**成交价**收一个百分比佣金，通常 **5%–6%**。一栋 $1.2M 的房子，总佣金大约 $60K–$72K。
2. 这笔总佣金一般在**卖方经纪人（listing agent）和买方经纪人（buyer agent）之间 50/50 平分**。所以每一"边（side）"大约拿 2.5%–3%。
3. 每一边的佣金再在**经纪人和经纪公司之间拆分（commission split）**。资历浅的初级经纪人可能留 65%–72%，公司拿剩下的；资深经纪人能留 80%–88%。这就是数据里 `Commission_Split_Pct__c` 字段的含义。

这套模型很残酷的地方在于：**房子不成交，谁都拿不到一分钱**。带了 20 次看房、谈崩了，那 20 次的时间就是沉没成本。所以经纪公司天然关心两件事——

- **转化效率**：从一个 lead 走到 closed deal，漏斗每一层漏掉多少？
- **单位经济**：一个 agent 的产出（成交量 × 客单价 × 分成比例）够不够养活他占用的公司资源？

单位经济的量级感：均价 $700K–$1.2M 的房子、每边 ~2.75% 佣金，意味着**每笔成交给公司带来的毛佣金（gross commission）大约 $20K–$35K**，其中一大半还要分给 agent。一个高产的资深 agent 一年能贡献的 GCI（见术语表）可达几十万美元，长尾的初级 agent 可能一年只成交一两单。这种**极度不均的产出分布**（少数 agent 贡献大部分收入）是行业常态，也是数据里刻意复刻的特征。

---

## 3. 行业科普：住宅地产经纪是怎么运转的

如果你来自别的行业，这一节让你能和同事讨论这个市场。

### 这个行业创造什么价值

住宅地产经纪行业撮合"想卖房的人"和"想买房的人"。它解决的核心问题是**信息不对称和信任**：卖家不知道自己的房子该卖多少、怎么营销、买家靠不靠谱；买家不知道市场上有什么、价格合不合理、怎么谈判和过户。持牌经纪人提供定价建议、营销曝光、看房安排、谈判、以及把控几十天的过户流程（escrow）。报酬就是成交时的佣金。

### 主要玩家类别（不点名真实公司）

- **全国连锁经纪公司**：规模最大，品牌响，靠加盟或自营覆盖全国。
- **科技驱动型经纪公司**：主打 app、即时估价、线上流程。
- **区域独立经纪公司**：像 Crestline 这样，深耕几个都会区，靠本地关系和服务质量。
- **iBuyer / 折扣经纪**：用算法快速报价收房或压低佣金。

### 监管框架（北美）

- **State licensing（州牌照）**：每个经纪人必须持有所在州的牌照。加州由 **DRE（Department of Real Estate）**发牌，牌照号就是数据里的 `DRE#####`；华盛顿州由 Department of Licensing 管。
- **NAR（National Association of Realtors，全美房地产经纪人协会）**：行业自律组织，运营各地的 MLS、制定职业道德准则。称得上 "Realtor" 的经纪人是 NAR 会员。
- **Fair Housing Act（公平住房法）**：禁止在买卖、租赁中基于种族、宗教、性别等歧视。
- **RESPA（Real Estate Settlement Procedures Act）**：规范过户结算流程、禁止违规回扣。
- **CFPB（Consumer Financial Protection Bureau）**：监管按揭贷款相关的消费者保护。

### 当下塑造这个行业的宏观力量

- **按揭利率（mortgage rate）冲击**：2022–2023 美联储加息把 30 年固定利率从 ~3% 推到 2023 年 10 月峰值 ~7.79%。借钱变贵直接冻结了成交量。
- **Lock-in 效应（锁定效应）**：很多房主锁定了 3% 的老贷款，不愿卖房去背 7% 的新贷款，导致挂牌库存枯竭，**房价却没怎么跌**（量缩价稳）。
- **佣金规则变化**：2024 年 NAR 和解案改变了买方佣金的展示和谈判方式，全行业的佣金率正面临压力。
- **AI 与数据**：自然语言取数、房源-客户智能匹配、自动化市场报告正在成为经纪公司的新竞争点——这正是 Crestline 押注的方向。

### 一笔成交从头到尾（数据集里几乎每一行的来源）

1. **房主决定卖房**，找一个 listing agent。经纪人上门看房、给定价建议、签挂牌协议，把房子**录入 MLS**（见下一节）。→ 产生 `mls_listing` 一行，状态 `ACT`（Active 在售）。
2. **其他经纪人的买家发现这个挂牌**，安排**看房（showing）**。→ 产生 `mls_listing_showing` 行。
3. **冷门时卖家降价（price reduction）** 吸引关注。→ 产生 `mls_listing_event_history` 的 `PRICE_CHANGE` 事件。
4. **买家出 offer**，谈妥后签合同，状态从 `ACT` 翻成 `PND`（Pending 待过户）。→ 进入 30–45 天的 escrow：检查、批贷、查产权。
5. **过户完成**，状态翻成 `SLD`（Sold 已成交），钱到位，过户后一两周经纪人拿到佣金。→ 产生 `mls_sold_transaction` 行。
6. **有时交易黄了**：检查出问题、贷款下不来、卖家反悔。状态翻回 Active，或变成 `EXP`（Expired 挂牌过期）/ `WTH`（Withdrawn 撤回）。**大约 15%–25% 的挂牌从未真正成交**。

### 三种数据源：MLS、CRM、外部数据

理解这个数据集，关键是理解它把三类性质完全不同的数据拼在一起：

- **MLS（Multiple Listing Service，多重挂牌服务）—— 公开、全市场。** 这是一个按区域划分、**行业共享**的"所有在售房产"数据库，由本地 Realtor 协会运营，**不属于任何单个经纪公司**。经纪人挂牌时必须录入 MLS，区域内其他经纪人才能带买家来看。关键推论：Crestline 拉 MLS 数据时，看到的是**整个区域所有经纪公司的挂牌**——自家的（约占数据集 30%）和竞争对手的（约 70%）都在里面。这就是为什么能算"我们在某个 zip 的市场份额"或"竞争对手定价比我们高还是低"。
- **CRM（Customer Relationship Management，客户关系管理系统，本数据集是 Salesforce 风格）—— 私有、仅 Crestline。** 和 MLS 相反，这是 Crestline 自己的私密数据：抓到的 leads、跟进的客户、销售管道、agent 活动日志、内部佣金核算。**竞争对手看不到**。CRM 是 Crestline 竞争优势的所在。
- **外部数据（External）—— 公开、宏观 context。** 内部数据告诉你 Crestline 做了什么；外部数据告诉你**周围世界同期在做什么**。如果某季度销量下滑，是 Crestline 的问题，还是因为利率被推到 7.79%？没有外部 context 判断不了。四个外部数据源：Zillow 房价指数（ZHVI）、Zillow 市场温度、Freddie Mac 按揭利率、Census/BLS 人口经济、Walk Score 步行评分。

把三者 join 起来，"原始运营数据"才变成**市场情报（market intelligence）**。

---

## 4. 项目背景：市场情报平台

**你的角色**：你是 Crestline 数据团队的一名分析师 / BI 工程师（实习或全职皆可），向 Tech Lead（Marcus Rivera）和 Analytics Lead（Emily Zhang）汇报，服务对象一路向上到 VP Operations（Sarah Mitchell）和 CEO。

**你在搭什么**：一个叫 **Market Intelligence Platform（市场情报平台）** 的内部数据产品。它的目标是把上面那三类原始数据（MLS / CRM / External）汇入数仓（项目设定是 AWS Redshift 的三个 raw schema：`raw_mls`、`raw_crm`、`raw_external`），再用 dbt 清洗建模，最终支撑一系列分析和 AI 能力。

本数据集就是这个平台的**原始数据层（Raw Data Layer）**。它刻意保持 **source-faithful（保留源系统原貌）**——保留 MLS 风格字段名（`LIST_PRICE`、`STATUS_CD`、`DOM`）、Salesforce 风格后缀（`__c`、`LastModifiedDate`）、源系统状态码（`ACT`/`PND`/`SLD`），以及少量真实的脏数据（ZIP+4 格式、近似重复 contact、经纪公司名拼写变体）。这样下游的 dbt staging 层才有真实的清洗、标准化、跨域 join 的活儿可干，dbt tests 才有意义。

平台要支撑的几条工作线（项目里称 Module 1–4），帮助你理解每个查询服务于谁：

- **Module 1 — dbt 建模与测试**：把 raw 清洗成 staging → intermediate → mart，比如 agent 业绩 mart、客户情报 mart。
- **Module 2 — BI dashboard 与自动周报**：Market Pulse dashboard、Agent Scorecard、自动生成的每周市场报告 pipeline。
- **Module 3 — 自然语言取数与智能匹配**：让 agent 用大白话问数据库；房源-客户 embedding 匹配推荐。
- **Module 4 — 每日竞争力定位 AI 分析**：AI agent 每天扫描市场，标记定价偏高/陈旧 listing、识别机会。

**交付物**：领导层的 dashboard、给董事会和投资人的季度 deck、给 manager 的自动周报、给财务的现金流预测。

---

## 5. 要解决的业务问题

整个平台和这份数据集，都是为了回答下面这几个 Crestline 真实会问出来的问题。后面 SQL 查询文档里的每一条查询，都能追溯到这里的某个问题。

1. **定价是否合理（Pricing）**：当我们把 Palo Alto 一栋 3BR 挂 $2.4M，定价对吗？同 zip 同房型上季度可比房子卖了多少？哪些 listing 反复降价，说明初始定价系统性偏高？哪些成交价显著高于 Zillow 公允价，是定价能力的正样本？
2. **谁是高产 agent，为什么（Performance）**：200 个 agent 里谁 GCI 最高？是因为转化率高，还是单纯外联次数多 5 倍？资历越深收入是否真的越高（要不要据此调整 tier 佣金结构）？
3. **市场是在升温还是降温（Market temperature）**：某个 zip 的 days-on-market 和 sale-to-list ratio 趋势如何？该建议卖家"现在挂牌"还是"再等半年"？
4. **机会在哪里（Opportunity discovery）**：有没有哪些 zip 我们 listing 很少但买方需求旺盛（看房多）？那是该招更多 agent、再开 office 的地方。Crestline 在各 zip 的挂牌份额逐年涨还是跌？
5. **未来量怎么走、现金怎么排（Forecast & cash flow）**：利率横盘在 6.7% 的背景下，下季度成交量预期如何？未来 30 天有多少佣金要 payout、给谁？
6. **客户匹配与数据质量（Matching & data quality）**：CRM 里 5,000 个买方 contact，每个对当前哪些 active listing 感兴趣？CRM 里有多少重复 contact 需要在建 mart 前去重？我们为什么在丢 deal？

回答以上几乎每一个问题，都需要**跨 MLS / CRM / External 三个域 join 数据**。这正是数据集这样组织的原因。

---

## 6. 数据范围概览

- **时间窗口**：2023-01-01 到 2026-06-05，约 **3.4 年 / 42 个月**的历史。
- **REFERENCE_DATE（有效"当前日期"）= 2026-06-05**。数据里所有"今天"、"当前 active"、"过去 12 个月"的语义都锚定到这一天；所有 SQL 查询用字面量 `'2026-06-05'` 而不是 `date('now')`，保证结果可重现。
- **地理**：3 个 market（Bay Area / SoCal / PNW）、12 个 county、30 个 city、**60 个 zip code**（每个 market 约 20 个）。每个 zip 预先打上温度标签 HOT / STABLE / COOL，驱动 days-on-market 和 sale-to-list ratio 的真实差异。选 60 个 zip 是分析甜区：够多到能演示 zip 级别 dashboard，又能把总行数压在 ~33 万、生成时间控制在分钟内。
- **数据量**：**23 张表，约 328,000 行**。最大的几张表是看房（~72K）、挂牌事件（~65K）、agent 活动（~50K）、挂牌（~40K）、房产和 walk score（各 ~25K）。
- **Crestline 在数据中的占比**：为了让内部分析有足够样本，数据集里 **~30% 的在范围 MLS 挂牌带 Crestline 品牌**，其余 ~70% 来自 8 家竞争对手。（注意：这 30% 是数据集为分析方便设定的范围内占比，和第 1 节说的 2–3% 真实街头份额是两回事——后者是 Crestline 在整个大市场的竞争地位。）
- **刻意的范围取舍**：只做住宅、不做商业地产；只做美国 / USD；只有宏观利率、没有贷款级数据；不建模基础设施日志、dbt 模型本身、dashboard 配置（那些是项目交付物，不是 raw data）。
- **刻意的脏数据**：ZIP+4 格式（~5%）、NULL email/phone、电话格式混杂、近似重复 contact（~3%）、Crestline 经纪公司名 5 种拼写变体、空白/大小写异常。目的是给下游清洗层留真实的活。

---

## 7. 术语表（英文术语 + 中文 layman 解释）

每个会在 ER 文档或 SQL 查询里出现的行话，这里给一句大白话解释 + 一句"在这里为什么重要"。

| 术语 | 大白话解释 | 在本数据集里为什么重要 |
|------|-----------|----------------------|
| **MLS** (Multiple Listing Service) | 区域内经纪人共享的"所有在售房产"数据库，由 Realtor 协会运营。 | `mls_*` 表的来源；包含全市场（含竞争对手）挂牌，是算市场份额和可比价的基础。 |
| **CRM** (Customer Relationship Management) | 公司自己的客户/销售管理系统，这里是 Salesforce 风格。 | `crm_*` 表的来源；仅 Crestline 私有，是公司竞争优势所在。 |
| **agent / listing agent / buyer agent** | 持牌房地产经纪人；分别代表卖方和买方的那一位。 | `crm_agent`、各种 `*_AGENT_LICENSE` 字段；佣金和业绩都挂在 agent 上。 |
| **brokerage** | 经纪公司（如 Crestline），雇佣 agent、和 agent 分佣金。 | `LISTING_OFFICE_NAME`、`crm_office`；区分自家 vs 竞争对手的关键。 |
| **DRE number** | 加州房地产牌照号（Department of Real Estate 发）。 | `License_Number__c` 与 `LISTING_AGENT_LICENSE` 用它做 MLS↔CRM 跨域 join。 |
| **listing** | 一次挂牌事件（某房子某次被放到市场上卖）。 | `mls_listing`；同一房子可被多次挂牌，所以 listing ≠ property。 |
| **property** | 物理房产（地址 + 物理属性），跨多次挂牌持久存在。 | `mls_property`；listing 的父实体。 |
| **DOM** (Days on Market) | 一个挂牌在市场上挂了多少天才成交/下架。 | 市场冷热的核心指标；HOT zip DOM 短，COOL zip 长。 |
| **list price / sale price** | 挂牌价 / 最终成交价。 | 两者之比就是 SLR，反映议价方向。 |
| **SLR** (Sale-to-List Ratio) | 成交价 ÷ 挂牌价。>1 是抢着买（加价成交），<1 是卖家让步。 | `LIST_TO_SALE_RATIO`；市场温度的最佳前瞻指标。 |
| **status code (ACT/PND/SLD/EXP/WTH)** | 挂牌状态：在售 / 待过户 / 已成交 / 过期 / 撤回。 | `STATUS_CD`；source-faithful 的源系统枚举，dbt 要标准化。 |
| **escrow** | 签合同到过户之间的 30–45 天履约期（检查、批贷、查产权）。 | `mls_pending_sale`、contract→close 的时间差。 |
| **contingency** | 合同里的解约条件（如检查不过、贷款下不来可退出）。 | `CONTINGENCIES`；待过户房源的风险标记。 |
| **pending** | 已签合同、等待过户关闭的状态。 | `mls_pending_sale` 是 REFERENCE_DATE 的当前快照。 |
| **lead / contact / opportunity** | 线索 / 联系人档案 / 一个具体的销售机会（带管道阶段）。 | `crm_contact`、`crm_opportunity`；销售漏斗的三个粒度。 |
| **pipeline stage** | 机会在销售漏斗里的阶段：Lead→Qualified→Showing→Offer→Under Contract→Closed Won/Lost。 | `StageName`；管道速率和转化率分析的基础。 |
| **Closed Won / Closed Lost** | 机会赢单成交 / 输单告吹。 | 赢单产生 transaction；输单带 `Lost_Reason__c`。 |
| **GCI** (Gross Commission Income) | 一个 agent（或 office）在一段时间内拿到的佣金总额。 | agent 业绩排名、tier 薪酬政策的核心指标。 |
| **commission split** | agent 和公司怎么分一笔佣金的比例。 | `Commission_Split_Pct__c`、`crm_commission_split`；资深 agent 留成更高。 |
| **tier (JUNIOR/MID/SENIOR)** | agent 的资历层级，决定分成比例。 | `Tier__c`；和 tenure、收入正相关。 |
| **tenure** | agent 入职至今的年限。 | 由 `Hire_Date__c` 算出；驱动产出和分成的关键变量。 |
| **co-list** | 两个 agent 共同代理同一笔交易，分一笔佣金。 | `crm_commission_split` 出现一笔交易两行的情况（~10%）。 |
| **showing** | 一次带客户实地看房。 | `mls_listing_showing`；买方需求信号的来源。 |
| **price reduction** | 卖家降价。 | `mls_listing_event_history` 的 `PRICE_CHANGE` 事件；定价偏高的信号。 |
| **ZHVI** (Zillow Home Value Index) | Zillow 算的某地区典型房价指数。 | `ext_zillow_home_value_index`；市场级公允价 baseline。 |
| **market temperature** | 某 zip 当前是热（抢购）还是冷（让步）。 | zip 的 HOT/STABLE/COOL 标签和 `ext_zillow_market_temperature`。 |
| **PMMS** (Primary Mortgage Market Survey) | Freddie Mac 每周发布的按揭利率调查。 | `ext_freddie_mac_mortgage_rate`；解释成交量波动的宏观因子。 |
| **mortgage rate (30Y fixed)** | 30 年固定按揭利率，购房成本的核心。 | `Rate_30Y_Fixed`；2023-10 峰值 7.79% 解释 2024 量缩。 |
| **lock-in effect** | 房主锁定低利率老贷款，不愿卖房换高利率新贷款。 | 解释为何 2024 量缩但 ZHVI 仍年涨 ~4%。 |
| **financing type (CASH/CONVENTIONAL/FHA/VA/JUMBO)** | 买家用什么方式付款/贷款。 | `FINANCING_TYPE`；现金占比反映市场高端程度。 |
| **Walk Score** | 一个地址的步行/通勤/骑行友好度评分（0–100）。 | `ext_walk_score`；城市核心区评分高。 |
| **DGT / GTV (Gross Transaction Value)** | 一段时间内成交房产的总成交额。 | 成交量 dashboard 的金额口径（`SUM(SALE_PRICE)`）。 |
| **source-faithful** | 数据保留源系统原貌（含脏数据），不预先清洗。 | 整个 raw 层的设计原则，让 dbt 有活干。 |

---

## 8. 关键指标与公式

下面是会在 SQL 查询里出现、或读者需要心里有数的指标。给出口径，避免下游对同一指标算出两套数。

```
# 市场冷热
DOM (Days on Market)        = STATUS_DT - LIST_DT             # 单位：天；按 listing
SLR (Sale-to-List Ratio)    = SALE_PRICE / LIST_PRICE         # >1 加价成交，<1 让步成交
                                                              # 数据集按温度分层：HOT~1.04, STABLE~1.00, COOL~0.96

# 成交规模
GTV (Gross Transaction Value) = SUM(SALE_PRICE)               # 一段时间/一个分组的总成交额
sold_count                    = COUNT(已成交 listing)          # 成交套数
median_sale_price             = 按 (zip, property_type) 分组求中位数

# 同比
YoY % = 100 * (本期值 - 去年同期值) / 去年同期值                # 用 LAG() 窗口函数取去年同期

# 佣金（核心，注意三层拆分）
Gross_Commission = Sale_Price * Commission_Rate_Pct / 100     # 每一边的毛佣金；rate 每边 2.5%–3.0%
Agent_Take       = Gross_Commission * Split_Pct               # agent 留成；Split 按 tier 0.65–0.88
Company_Take     = Gross_Commission * (1 - Split_Pct)         # 公司留成
GCI (per agent)  = SUM(Agent_Take 在窗口内)                    # agent 佣金收入；Q3 用 trailing 12 月，Q15 用全期累计

# 市场份额
Crestline_Share_Pct (zip, year) = 100 * crestline_listings / total_listings   # 在某 zip 某年的挂牌份额
                                                              # crestline_listings = IS_CRESTLINE_LISTING 为真的挂牌数

# 销售漏斗
close_rate_pct   = 100 * closed_won / total_opportunities     # 机会赢单率
demand_signal    = 按 showings 数和 offers 数给 active listing 打需求标签
                   (HIGH_INTEREST_NO_OFFER / LOW_DEMAND / OFFERS_RECEIVED / NORMAL_FUNNEL)

# 陈旧 listing 判定（Module 4 阈值）
is_stale = (REFERENCE_DATE - LIST_DT) > zip_median_DOM * 1.5  # 超过本 zip 中位 DOM 的 1.5 倍即陈旧
```

口径约定（避免歧义）：

- **GCI 的时间窗口要说清楚**：Query 3（Top GCI）用的是 **trailing 12 个月**（按 `Payout_Date__c` 过滤）；Query 15（资历 vs 收入）用的是 **agent 全期累计**（3.4 年），所以 Q15 的绝对金额大约是 Q3 的 3–4 倍。同一个 agent 在两个查询里数字不同，是窗口不同，不是数据矛盾。
- **commission_split 的 agent 归属**：主分成行挂在该机会的 **owner agent** 上（不是随机 agent），这样 tenure-weighted 的产出信号能一路传导到 GCI 排名。
- **市场份额用挂牌数（listing count），不是成交额**：Query 20 的份额是按"挂牌数量占比"算的，反映的是 Crestline 在某 zip 拿到了多少卖方委托。
- **median 在 SQLite 里没有内置函数**：中位数用 `ROW_NUMBER() / COUNT()` 窗口函数手算（见 Query 2）。

---

> 读完这份业务背景，你应该能回答：Crestline 是谁、靠佣金赚钱、所在的住宅经纪行业怎么运转、为什么要把 MLS/CRM/External 三类数据拼起来、这个平台要回答哪 6 类业务问题。接下来去 `02-...er_document-cn.md` 看这些问题落到哪些表和字段，再去 `03-...sql_queries-cn.md` 看分析师怎么一条条把它们查出来。
