# VerdantBox 电商订阅增长营销 业务背景

本文件是 `ecommerce_subscription_growth_marketing_high` 数据集的业务背景说明，是整个数据集的总入口。Schema、SQL 查询、刻意埋进数据里的分布偏置，全都是为了服务这里描述的公司和项目。读完这一份，你就能在第一次站会之前把这家公司、这个行业、这个项目、要解决的问题和满屏的英文黑话都搞明白。

数据集的叙述语言是中文，但业务本身设定在北美。公司在北美，货币是 USD，客户在美国和加拿大，监管机构是美国和加拿大的。中文只是讲故事的语言，不改变这是一家北美公司的事实。业务术语保留英文原形（例如 ROAS、AOV、CAC、LTV），第 8 节术语表里逐个用大白话解释。

---

## 1. 公司速写

VerdantBox 是一家虚构的北美 direct-to-consumer（DTC，直面消费者）订阅制健康食品平台，总部设在美国西雅图。公司主营有机、植物基（plant-based）、功能性（functional）健康食品，覆盖美国和加拿大，把精选的常温货架商品、零食、饮料、保健补剂、冷冻餐和冷藏必需品直接寄到消费者门口，绕过传统商超的货架。

公司规模属于成长期中型 DTC 品牌（量级，非精确值）：约 200 名员工，年营收约 6,000 万到 8,000 万美元，活跃客户数在十万量级。客户可以单次下单（one-time purchase），也可以订阅 **VerdantBox+** 付费会员，享受免运费、会员专属价（member price）和限量精选盒。

跟数据集相关的组织结构是这样的。市场侧的最高负责人是 CMO（Chief Marketing Officer，首席营销官），下面挂着 VP of Growth Marketing（增长营销副总裁），再往下是 Growth Marketing 团队，团队里有 acquisition（获客）、lifecycle（生命周期）、creative（创意）、analytics（分析）几个小组。财务侧由 CFO 领衔，下设 FP&A（Financial Planning and Analysis，财务规划与分析）团队，专门盯营销花出去的每一块钱有没有回本。后面 SQL 查询里出现的 Executive、Manager、Analyst、Operations、Finance 这些角色，都对应这套组织里的真实岗位。

---

## 2. 商业模式与单位经济学

VerdantBox 的钱从两条线进来。第一条是商品零售：客户每下一单，公司赚的是「售价减去批发成本」的毛利。健康食品这个品类的目录价（list price）通常在 5 到 50 美元一件，批发成本约为目录价的 35% 到 55%，所以单品毛利率大致落在 45% 到 65% 这个区间。第二条是会员订阅：VerdantBox+ 会员按月付或按年付一笔订阅费，换来免运费、会员价和专属精选盒。

会员这条线是整个商业模式的杠杆。表面上看，会员按 member price 买东西、还免运费，单笔订单公司让出去不少利润。但会员有两个补偿机制。其一，会员篮子更大：会员一单平均买 3 到 6 件，非会员只买 1 到 3 件，所以会员的 AOV（Average Order Value，平均订单金额）明显高出一档。其二，会员复购更勤、留得更久，LTV（Lifetime Value，客户终身价值）远高于非会员。于是公司愿意花钱做 membership conversion（会员转化），用首单或试用把人钩进 VerdantBox+，再靠后续的复购把让出去的利润赚回来。

VerdantBox+ 提供两档会员：Plus 和 Plus Premium。按计费周期又分月付和年付，年付折算下来更便宜（鼓励用户锁定更长周期）。新用户先进 30 天免费试用（free trial），试用期结束后大约 62% 转为付费（trial-to-paid conversion）。这套「试用转付费再到续费」的链路，是订阅生意最核心的发动机。

营销花费是公司第三大成本项（仅次于商品成本和履约），所以「每一块营销预算的回报」是 CMO 和 CFO 每个月都要盯的数字。整个数据集的存在意义，就是把这件事量化清楚。

---

## 3. 行业速览

DTC 订阅制电商（subscription ecommerce）做的事，是把过去要去超市货架上挑的商品，变成「在线选品、订阅复购、寄到家门口」的体验。价值主张有三层：选品（帮消费者从成千上万的 SKU 里筛出值得买的）、便利（订阅自动复购，不用每次重新下单）、身份认同（有机、植物基、清洁标签这些标签本身就是卖点）。健康食品这个细分赛道，叠加了「养生消费升级」的大趋势，客单价和复购率都比普通快消高。

这个市场里的玩家大致分四类（都用泛称，不点真实公司名）：DTC 订阅盒品牌（像 VerdantBox 这样自建品牌、自建会员体系的）、综合电商平台（什么都卖的大平台）、传统商超（线下为主、线上为辅）、垂直健康食品零售商（专做保健品或有机食品的专门店）。VerdantBox 属于第一类，靠品牌、会员粘性和选品能力跟大平台的「便宜和全」打差异化。

监管和合规这块，北美健康食品 DTC 要同时应付好几套框架。食品标签和保健品归 FDA（Food and Drug Administration，美国食品药品监督管理局）管，膳食补充剂走 DSHEA 这套法规；有机认证归 USDA Organic（美国农业部有机认证）；广告宣传和「订阅自动续费」归 FTC（Federal Trade Commission，联邦贸易委员会）管，近年 FTC 推的 click-to-cancel（一键取消）和 ROSCA（限制在线续费陷阱的法案）直接影响订阅业务怎么设计退订流程；邮件营销受 CAN-SPAM 约束，短信营销受 TCPA 约束，加州用户的隐私受 CCPA 保护，加拿大那边邮件和短信受 CASL（加拿大反垃圾邮件法）管，食品安全归 CFIA 和 Health Canada。

当下塑造这个行业的几股宏观力量值得记住。一是获客越来越贵：苹果 iOS 的 ATT（App Tracking Transparency，应用追踪透明度）和整体隐私收紧，让付费社交广告的定向和归因都变难，CAC 普遍上涨。二是 retail media（零售媒体广告）和 AI 驱动的个性化在重塑投放方式。三是「订阅疲劳」：消费者订阅的东西太多，留存和反流失（reactivation）变成比拉新更划算的增长来源。这几股力量合起来，逼着像 VerdantBox 这样的公司把营销预算的每一分效率都抠出来，而抠效率的前提是把数据看明白。

---

## 4. 你的角色与项目

你是 VerdantBox **Growth Marketing 团队的数据分析师**（full-time analyst，偏 BI 方向）。你直接向 VP of Growth Marketing 汇报，同时给 CMO 的月度经营回顾（Monthly Business Review，MBR）和 CFO 那边的 FP&A 团队供数。

你手上的项目是把过去约 18 个月的营销和客户活动，做成一套能反复查询的分析底座，支撑两个固定交付物：一是每月给 CMO 的 MBR 演示材料，二是每季度给 CFO 的预算再平衡（budget reallocation）备忘录。营销团队同时在跑三类活动组合，你的分析要能同时回答「过去花的钱效果如何」和「下一季度该往哪倾斜预算」。

三类活动目标贯穿始终，后面反复出现：

- **ACQUISITION**（新客获取）。通过付费社交、搜索广告、推荐分销把新客拉进来。
- **MEMBERSHIP_CONVERSION**（会员转化）。把单次购买或试用用户推上 VerdantBox+ 付费会员。
- **REACTIVATION**（沉睡唤醒）。把 dormant（沉睡）和 churned（流失）客户唤醒回来。

你的输出不是「跑个数就完事」，而是要给出可执行的结论：哪个渠道该扩量、哪个活动该叫停、下一波 reactivation 该锁定哪些人群。下面第 5 节列的业务问题，就是这个项目要回答的核心清单。

---

## 5. 要解决的业务问题

整个数据集围绕五个具体的业务问题搭建。每个 SQL 查询都能追溯回其中至少一个。

1. **营销组合 P&L 与预算再平衡。** 三类活动目标（acquisition、conversion、reactivation）各花了多少钱、带来了多少可归因收入、ROAS 分别是多少？下个季度的预算应该往哪类目标、哪些活动倾斜？这是项目得名的招牌问题。
2. **渠道效率（Channel ROAS）。** 哪些渠道每投一块钱带回最多收入？哪些该扩量、哪些该暂停？由于归因是 campaign 级而非 channel 级，怎样用 spend-share 加权把收入合理摊到渠道上？
3. **会员经济学。** 一个 VerdantBox+ 会员到底值多少钱？会员 vs 非会员的 AOV、复购、LTV 差距有多大，足以论证 membership conversion 的预算投入吗？
4. **漏斗诊断。** 从 sent（发送）到 delivered（投递）到 engaged（互动）到 clicked（点击）到 converted（转化），哪一步流失最严重？下一轮优化该投到漏斗的哪一级？
5. **留存与唤醒。** 各注册 cohort 的留存曲线长什么样？trial-to-paid 转化是在改善还是恶化？下一波 reactivation 活动该锁定哪些「沉睡但高价值」的客户和 segment？

---

## 6. 数据范围概览

数据集锚定在一个固定的「今天」：**REFERENCE_DATE = 2026-06-01**。所有涉及「当前」「至今」「还剩几天」的语义都以这一天为基准，生成器和每条 SQL 查询里出现的也都是这个日期常量（而不是 `DATE('now')`），保证结果可复现。

时间跨度大致是 18 个月的历史活动，再加上三种时态的活动状态：已完成（COMPLETED，约 70%）、进行中（ACTIVE，约 20%，集中在最近 30 天）、已计划（PLANNED，约 10%，落在未来 30 天，有目标 segment 但还没有真实表现数据）。这种「过去 + 现在 + 未来」的混合，让数据集既能做回顾性分析，也能做前瞻性的进行中活动看板。

数据量用大白话说，是「一千个客户、五百个 SKU、五十个活动，外加上万行营销触点、订单和响应」。客户地理上约 88% 在美国、12% 在加拿大。具体的表、字段、行数请看 ER 文档 `02-ecommerce_subscription_growth_marketing_high_er_document-cn.md`，这里不展开。

需要说明一个刻意的范围决定：这是一个**采样规模**的数据集，不是生产全量。营销触点（marketing_touchpoint）只取了约一千行的样本窗口，活动预算（campaign budget）也相应缩放到几百到几千美元的量级，目的是让「每个活动的支出」能跟「这一千行触点的成本之和」大致对得上，从而让 ROAS、CAC 这些比率落在真实可信的区间里。换句话说，绝对金额是缩小的，但比率和分布是真实的。

---

## 7. 行业知识科普

这一节是一个外行在数据看得懂之前，需要花三十到六十分钟补的背景。读完你就能跟营销团队对上话。

**增长营销的生命周期漏斗。** 一个客户从陌生人到忠实会员，会经历 acquisition（获客）、activation（激活，完成首单）、retention（留存，持续复购）、reactivation（流失后唤醒）几个阶段。三类活动目标正好对应这条链路的不同位置：ACQUISITION 管前端拉新，MEMBERSHIP_CONVERSION 管中段把人升级成会员，REACTIVATION 管后端把掉队的人捞回来。客户当前处在哪个阶段，用 `lifecycle_stage` 字段刻画：new（新客）、active（活跃）、at_risk（有流失风险）、dormant（沉睡）、churned（已流失）。

**营销归因（attribution）。** 一笔订单的收入，到底该记在哪个活动头上？这就是归因要回答的问题。本数据集用的是 **last-touch 归因**：取下单前 60 天内、该客户最近一次 click 或 convert 的触点，把订单归给那个触点对应的活动。如果找不到真实触点链路，就退回到「日期窗口随机分配」（fallback）。还有一个关键点：归因做在 **campaign 级**，不是 channel 级。当一个活动同时投在 Meta 和 Google 两个渠道时，同一笔订单的收入要靠 spend-share 加权才能合理摊到各渠道（见第 9 节）。归因窗口、last-touch、spend-share 这几个概念在 SQL 查询里反复用到。

**渠道分类（owned / paid / earned）。** 营销渠道按「谁拥有、谁付钱」分三类。Owned（自有）渠道是公司自己掌握的触达方式，例如 email、push、SMS、in-app，几乎零变动成本。Paid（付费）渠道是花钱买曝光的，例如 Paid Social（Meta、TikTok）、Google Ads、YouTube、Affiliate。Earned（赚得）渠道是靠口碑自然来的，例如 Referral（推荐）。每个渠道有典型的 CPM（千次曝光成本）和 CTR（点击率），自有渠道 CPM 极低、付费渠道 CPM 高，这直接决定了不同渠道的 ROAS 排序。

**会员订阅的发动机。** 订阅生意的核心是一条状态链：trial（试用）→ active（已转付费）/ trial_ended（试用未转化）→ cancelled（已退订）。新人先进 30 天免费试用，试用期满约 62% 转付费。转付费后还会有一部分人后续退订（churn）。把试用按季度分桶看 trial-to-paid 转化率，能看出会员业务是在变好还是变坏。

**Cohort 留存分析。** 把同一个月注册的客户归为一个 cohort（同期群），追踪他们在之后每个月有多少比例回来下单，就得到留存曲线。这里有个容易踩的坑：第 0 月（注册当月）回来下单叫**激活率（activation）**，不算留存；真正的留存是第 1 月及以后。留存曲线是衡量「产品自然增长（product-led growth）」健康度最重要的单一指标。

**营销漏斗的逐级口径。** 一次营销触点（touchpoint）有两个阶段。第一阶段是投递结果（delivery_status）：delivered（成功投递）、bounced（退信）、failed（失败）。第二阶段是用户响应（response_type），这是个**终态（terminal state）**模型：open（打开）、click（点击）、dismiss（关闭）、convert（转化）四选一，互斥。关键约定：convert 隐含用户先点击过、click 隐含用户先打开过。所以算「点击及以上」时，click 的口径是 `IN ('click','convert')`，「互动及以上」是 `IN ('open','click','convert')`。这个口径在多条查询里保持一致，第 9 节会再强调一次。

---

## 8. 术语表

下面每个术语都在 ER 文档或 SQL 查询里出现过。英文术语保留原形，配一句大白话解释和一句「在这里为什么重要」。

| 术语 | 大白话解释 | 在这里为什么重要 |
|------|-----------|----------------|
| DTC（Direct-to-Consumer） | 品牌不经过中间商，直接把货卖给消费者 | VerdantBox 的基本商业形态 |
| SKU（Stock Keeping Unit） | 一个具体的可售商品单元（一个口味一个规格算一个） | product 表的每一行就是一个 SKU |
| AOV（Average Order Value） | 平均每单花多少钱 | 衡量会员 vs 非会员价值差距的核心指标 |
| LTV（Lifetime Value） | 一个客户从头到尾给公司贡献的总价值 | 判断获客成本花得值不值的标尺 |
| CAC（Customer Acquisition Cost） | 获取一个新客户平均花多少钱 | 跟 LTV 对比看活动是否回本 |
| ROAS（Return on Ad Spend） | 每花一块广告费带回多少收入 | 渠道和活动效率的头号指标 |
| CPM（Cost Per Mille） | 每一千次曝光的成本 | 决定不同渠道的成本结构 |
| CTR（Click-Through Rate） | 点击数除以曝光（或投递）数 | 衡量创意和渠道的吸引力 |
| CPL（Cost Per Lead） | 获取一个潜在客户线索的成本 | 漏斗前端效率的常见度量 |
| funnel（漏斗） | 从曝光到转化逐级收窄的过程 | 诊断每一步流失的框架 |
| attribution（归因） | 把一笔收入记到某个活动头上 | 决定 ROAS 分子怎么算 |
| last-touch（末次触点归因） | 把功劳全记给转化前最后一次有效触点 | 本数据集采用的归因口径 |
| attribution window（归因窗口） | 触点到下单之间允许的最长时间 | 本数据集设为 60 天 |
| spend-share weighting（支出占比加权） | 按各渠道在活动里的花费占比来分摊收入 | campaign 级归因摊到 channel 的标准近似 |
| cohort（同期群） | 同一时间段进来的一批客户 | 留存分析的基本分组单位 |
| retention rate（留存率） | 某个 cohort 在后续月份回来的比例 | 衡量产品自然增长健康度 |
| activation（激活率） | 注册当月就下单的比例 | 与留存区分，是漏斗第一步 |
| trial-to-paid conversion（试用转付费率） | 免费试用结束后转成付费会员的比例 | 会员业务最核心的转化指标 |
| churn（流失） | 客户停止购买或退订 | reactivation 活动的目标人群来源 |
| reactivation / win-back（唤醒 / 召回） | 把流失客户重新激活 | 三类活动目标之一 |
| lifecycle stage（生命周期阶段） | 客户当前所处的活跃程度档位 | new/active/at_risk/dormant/churned |
| segment（受众细分） | 按规则圈出来的一群目标客户 | 活动定向（targeting）的基本单位 |
| member penetration（会员渗透率） | 某群体里活跃会员所占比例 | 判断 segment 适不适合做 upsell |
| owned / paid / earned media | 自有 / 付费 / 赚得 三类媒体渠道 | 渠道成本和 ROAS 排序的根因 |
| organic（自然流量） | 没花广告费自然来的客户 | 获客渠道里的 NULL / Referral 部分 |
| engagement rate（互动率） | 投递成功后产生互动的比例 | 漏斗中段的健康度 |
| redemption rate（核销率） | 促销码被实际使用的比例 | 衡量促销好不好用 |
| frequency cap（频次上限） | 限制同一客户在一段时间内收到的触点数 | 防止用户疲劳和退订 |
| RFM（Recency, Frequency, Monetary） | 按最近购买、购买频次、消费金额给客户打分 | 受众细分的经典方法论 |
| gross margin（毛利率） | 售价减成本占售价的比例 | 商品零售这条线的盈利底色 |
| budget pacing（预算节奏） | 已花预算占比 vs 已用时间占比 | 判断活动烧钱是否过快 |
| P&L（Profit and Loss） | 损益，收入减成本的盈亏视图 | 营销组合的整体财务画像 |

---

## 9. 关键指标与公式

下面是 SQL 查询里会用到、或读者需要心里有数的指标。公式用大白话伪代码写。凡是一个指标有两种常见定义的，这里钉死一种，避免下游 SQL 各算各的。

**ROAS（广告支出回报率）**

```
ROAS = Attributed Revenue / Spend
```

分子是归因到该活动（或渠道）的订单 `total_usd` 之和，分母是 `campaign_channel.spend_to_date_usd` 之和。渠道级 ROAS 因为归因是 campaign 级，要先做 spend-share 加权（见下）。

**Spend-share 加权（campaign 级收入摊到 channel）**

```
channel_attributed_revenue = Σ over campaigns ( campaign_revenue × (channel_spend_in_campaign / campaign_total_spend) )
```

一个活动的收入，按各渠道在该活动里的花费占比，按比例摊给每个渠道。这是行业标准的近似，因为 `order.attributed_campaign_id` 只到活动粒度。

**AOV（平均订单金额）**

```
AOV = SUM(order.total_usd) / COUNT(order)
```

口径约定：只统计实际成交的订单（`order_status IN ('delivered','shipped')`），`total_usd` 含运费和税、减折扣。会员和非会员分开算时按 `is_member_at_purchase` 分组。

**LTV（客户终身价值，本数据集用的代理口径）**

```
LTV ≈ SUM(order.total_usd) per customer over all delivered/shipped orders
```

本数据集没有显式的预测 LTV 模型，用「客户历史成交总额」作为已实现 LTV 的代理。

**CAC（单个活动的获客成本）**

```
CAC = campaign_spend / new_customers_acquired_by_campaign
```

分母是 `acquisition_campaign_id` 指向该活动的客户数。只对 `objective = 'ACQUISITION'` 的活动算 CAC 才有意义。

**Trial-to-Paid 转化率**

```
Trial-to-Paid = COUNT(activation_date IS NOT NULL) / COUNT(trials_started)
```

按 `membership_subscription` 算。分子是试用期内转成付费（有 activation_date）的数量，分母是该 cohort 开始试用的总数。

**Cohort 留存率（第 n 月）**

```
retention_rate(n) = active_customers_in_month_n / cohort_size
```

`cohort_size` 是该注册月的客户总数，`month_diff = 0` 是激活（不算留存），留存只看 `month_diff >= 1`。

**漏斗各级转化率（口径钉死）**

```
delivery_rate   = delivered / sent
engagement_rate = engaged   / delivered      ，engaged   = response_type IN ('open','click','convert')
click_through   = clicked   / delivered      ，clicked   = response_type IN ('click','convert')
conversion_rate = converted / delivered      ，converted = response_type = 'convert'
```

因为 response_type 是终态模型，convert 隐含点击、click 隐含打开，所以「点击及以上」「互动及以上」都用 `IN (...)` 取并集。这个口径在 Q3、Q11、Q18 之间保持一致。

**CTR / 渠道 CTR**

```
CTR = clicks / sends      （或 clicks / delivered，视分析口径而定）
```

创意素材排行（Q18）和渠道×星期（Q11）里用的是「clicks / delivered」，与漏斗口径一致。

**Redemption rate（促销码核销率）**

```
redemption_rate = promo_code.redemption_count / promo_code.max_redemptions
```

**Member penetration（segment 会员渗透率）**

```
pct_active_members = active_members_in_segment / segment_size
```

**Budget pacing（预算节奏）**

```
pct_spent   = spend_to_date / total_budget
pct_elapsed = (REFERENCE_DATE - start_date) / (end_date - start_date)
```

当 `pct_spent` 明显高于 `pct_elapsed`（例如高出 10 个百分点以上）时，说明活动烧钱过快，需要预警。

**Days to first order（首单耗时）**

```
days_to_first_order = first_order.order_date - customer.signup_date
```

按获客渠道分组取平均，耗时短的渠道意味着注册时意图就更强、质量更高。
