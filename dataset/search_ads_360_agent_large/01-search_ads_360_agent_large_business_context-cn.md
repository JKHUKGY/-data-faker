# Search Ads 360 智能分析 Agent - 业务背景

> **数据集:** `search_ads_360_agent_large`
> **复杂度:** Large (21 张表, ~1,000,000 行)
> **参考当前日期 (REFERENCE_DATE):** `2026-06-01`
> **数据文档:** 表结构, 字段, DDL, 生成规则请见 `02-search_ads_360_agent_large_er_document-cn.md`;SQL 示例请见 `03-search_ads_360_agent_large_sql_queries-cn.md`。

本文档是整个数据集的"业务说明书"。schema、生成的数据、以及所有 SQL 查询都是为了服务这里描述的公司和它要解决的业务问题。如果你是第一次接触这个数据集,请先读完本文档,再去看 ER 文档和 SQL 查询 —— 那两份文档假设你已经理解了这里讲的公司、行业和术语。

读者画像: 一个刚加入项目、聪明但不懂搜索广告的实习生。读完本文档,你应该能在第一次站会上听懂同事在聊什么。

---

## 1. 公司: Lumenly Ads

**Lumenly Ads** 是一家虚构的 **跨引擎搜索广告聚合管理平台 (cross-engine search ads management platform)**,总部位于上海,业务覆盖中国大陆主要城市。它直接对标 **Google Search Ads 360** 与 **Meta Ads Manager** 这类成熟的第三方广告管理系统。

一句话讲清楚它是做什么的: **广告主在 Google、Baidu、Bing、360 等多个搜索引擎上同时投广告,每个引擎都有自己的后台,管理起来很碎。Lumenly Ads 把这些账户接管到一个统一后台里,让广告主(或代他们打理的代理商)在一个地方配置 campaign、设出价策略、管预算、看转化报告。**

公司规模 (数量级):

- **客户 (advertiser):** ~150 个直接广告主。
- **代理商 (agency):** ~25 家第三方代理商,帮一部分广告主打理账户。
- **管理的广告账户 (engine_account):** ~300 个,横跨 4 个搜索引擎。
- **管理的 campaign:** ~1,550 个,下挂 ~8,000 个广告组、~80,000 个关键词。
- **平台沉淀的效果数据:** 每日 Campaign × 设备级日报 ~40 万行,转化事件 2.5 万条,搜索词报告 ~18 万行。

组织结构 (本数据集的查询会按角色 / 头衔引用以下岗位):

- 广告主侧: **Marketing Director / CMO**、**Performance Marketing Manager**、**Campaign Manager**、**Search Specialist (SEM)**、**Trading Desk / Bid Manager**、**Marketing Analytics / RevOps**。
- Lumenly Ads 侧 / 代理商侧: **Account Manager**、**CSM (Customer Success Manager)**、**CFO / Finance**。

---

## 2. 商业模式

Lumenly Ads 怎么赚钱: **按客户的月度广告消费额收取平台服务费 (take-rate)**,典型费率 **8%–20%**。客户在平台上花得越多,Lumenly 抽成越多。年度营收主要来自 **Mid-Market** 与 **Enterprise** 两类客户,因为它们的月消费量级远高于 **SMB**。

客户分三层 (advertiser tier),消费量级和服务模式各不相同:

| 层级 | 月消费区间 (CNY) | 代表行业 | 服务模式 |
|------|-----------------|---------|---------|
| **SMB** | < ¥10K | 本地生活、教育培训中小机构 | 自助服务 + 在线客服 |
| **Mid-Market** | ¥10K – ¥200K | 电商零售、医疗健康、汽车交通 | Account Manager 主导,代理商可选 |
| **Enterprise** | > ¥200K | 金融服务、房产家居、B2B 企业服务 | 代理商必选,大账户经理 + 季度业务回顾 (QBR) |

单位经济 (unit economics) 的直觉: Lumenly 自己不买流量,它是"管理层",收入 = 客户广告消费 × 费率。因此公司的健康度取决于两件事 —— **客户花得多不多 (消费规模)**,以及 **客户花得值不值 (ROAS 高不高,续约不流失)**。如果客户的广告投得一塌糊涂、ROAS 长期低于 2x,客户会流失,Lumenly 的服务费收入也跟着蒸发。所以"帮客户把广告投好"既是产品价值,也是公司自己的生意。

约 **80%** 的广告主由代理商管理 (agency-managed),其余 **20%** 是直客 (direct)。代理商按客户消费额再收一道服务费 (agency_client.fee_percentage, 8%–20%),这部分体现在数据里,但不是 Lumenly 的收入。

---

## 3. 行业概览: 搜索广告与第三方管理平台

如果你来自别的行业,这一节帮你建立对"搜索广告"这门生意的整体认知。

**搜索广告 (search advertising) 是什么。** 当用户在搜索引擎里输入一个词(比如"雅思培训"),搜索结果页顶部那几条带"广告"标记的链接,就是搜索广告。广告主为这些位置 **竞价 (bidding)**,按 **点击付费 (CPC, cost per click)** —— 用户点一次,广告主付一次钱。谁出价高、广告质量好,谁就排在前面。这是一个实时拍卖市场,每一次搜索都是一场微型拍卖。

**这个行业里有哪些玩家。**

1. **搜索引擎 (流量方):** 提供搜索结果页广告位,靠点击收费。中国市场主流是 Baidu、360,叠加 Google、Bing(本数据集 4 个引擎的份额约为 Baidu 40% / Google 35% / Bing 15% / 360 10%)。
2. **广告主 (需求方):** 想通过搜索广告获客、卖货、收留资的企业。
3. **代理商 (agency):** 帮广告主打理投放的专业团队,按消费抽佣。
4. **第三方管理平台 (如 Lumenly Ads):** 把多引擎账户聚合到一个后台,提供统一的 campaign 配置、自动出价、跨渠道归因分析。Lumenly 属于这一类。

**监管与合规。** 广告投放受《中华人民共和国广告法》约束(禁止"最佳/第一/国家级"等绝对化用语、医疗与金融类广告需资质审查);用户数据采集与转化跟踪受《个人信息保护法 (PIPL)》《数据安全法》约束,这也是为什么 floodlight tag(转化跟踪代码)的 lookback window 和 counting method 需要被规范记录。

**当下的宏观趋势。** 整个行业正在从 **手动出价 (manual bidding)** 转向 **自动出价 (automated / smart bidding)** —— 让算法根据转化目标实时调价;同时 **隐私收紧** 让跨设备、跨站点的用户追踪变难,**多触点归因 (multi-touch attribution)** 因此成为衡量渠道真实贡献的关键工具。Lumenly Ads 的数据模型(自动出价标志、6 种归因模型同表、设备维度全覆盖)正是为了支撑这两个趋势。

---

## 4. 项目背景: 你是谁, 你在做什么

**你的角色:** 你是 Lumenly Ads 数据团队的 **Marketing Analytics 分析师 (data analyst / BI analyst)**,服务于平台上的广告主和内部的 Account Manager 团队。

**你的产出对象:** 既有人类同事,也有机器。

- 给 **人类同事**: Performance Manager 要每周效果复盘,Bid Manager 要出价策略对比,SEM Specialist 要否定词/加词清单,CMO 要月度营销 P&L。
- 给 **LLM Agent**: 你手工探索出来的优化规则和异常模式(比如"Quality Score < 5 且 7 日花费 > 100 的关键词应暂停"),最终会被沉淀成 Text-to-SQL Agent 和自动化运营 Agent 的逻辑,在生产环境里每天自动跑。换句话说,**这个数据集是一个"人类分析师先探索、再把规则交给 Agent 落地"的双层训练环境**。

**为什么是现在。** 平台刚把多引擎数据打通、把效果数据沉淀满了一个完整的窗口(详见第 6 节),管理层希望用这批数据回答下面一组具体的业务问题,并把其中可重复的部分交给 Agent 自动化。

---

## 5. 要解决的业务问题

下面 6 个问题是整个数据集的脊柱。ER 文档里的表为它们而设计,SQL 查询为它们而写。每个 SQL 查询都能追溯到其中至少一个问题。

- **Q1 预算缺口识别 (Budget Gap):** 哪些 campaign 因为 **预算不足** 而损失了展示机会(`lost_is_budget` 偏高)?这些 campaign 加预算能直接换来更多展示和转化吗?这是平台帮客户"花更多钱"的核心抓手。
- **Q2 出价策略效果 (Bid Strategy Efficacy):** **自动出价 (automated bidding)** 真的比 **手动出价** 好吗?设了 Target CPA / Target ROAS 的 campaign,实际达成率(actual vs target)如何?哪些该换策略?
- **Q3 关键词质量诊断 (Keyword Quality):** 哪些关键词 **Quality Score 低但花费高**(在烧钱)?哪些关键词三个质量子维度都不错、QS 却偏低(数据不自洽,值得人工核查)?低 QS 会推高 CPC,直接吃利润。
- **Q4 搜索词挖掘 (Search Term Mining):** 用户实际搜的词里,哪些 **花了钱却零转化**(应加为否定关键词,止血)?哪些 **转化好却还没被加为正式关键词**(应加词,放量)?这是 SEM 最日常、最能立刻产生 ROI 的优化动作。
- **Q5 多归因模型转化分析 (Multi-Touch Attribution):** 同样一笔转化,在 **末次点击 (last click)**、**首次点击 (first click)**、**线性 (linear)**、**时间衰减 (time decay)**、**位置 (position)**、**数据驱动 (data-driven)** 六种归因模型下,功劳分给不同渠道的结果差多少?品牌词渠道在末次点击下看着很值钱,换成首次点击会不会"原形毕露"?
- **Q6 账户与客户组合健康 (Account Health):** 哪些广告主续约风险高(合同临近到期、消费下滑)?客户消费集中度多高(Top 10 客户贡献多少营收)?代理商带来的服务费收入趋势如何?这关系到 Lumenly 自己的生意。

---

## 6. 数据范围概览

- **历史基线:** 18 个月 (2024-12-08 → 2026-06-01),覆盖广告主接入、账户搭建、策略设置等组织结构的形成过程。
- **效果数据 (daily_stats):** 最近 **120 天** 的 Campaign × 设备级日报。每个 campaign 的报告日期被裁剪到它的实际生效区间内,所以不是每个 campaign 都有满 120 天。
- **搜索词数据 (search_term_report):** 最近 **30 天**,配额均摊到每个启用 (Enabled) 关键词,故全库搜索词高度长尾、大量唯一。
- **转化与归因:** 最近 **90 天** 的 conversion 事件,每条带 2–6 个 touchpoint(平均 ~4),覆盖完整的转化前路径。
- **状态保留:** Enabled / Paused / Removed 三种状态的 campaign 全部保留,以便做"被暂停 campaign 的复盘"。

**这是一个冻结快照 (frozen snapshot)。** 数据的最后一天就是 `2026-06-01`。所有 SQL 查询都以这一天为"今天",用字面量 `DATE('2026-06-01', ...)` 做时间过滤,**绝不用 `DATE('now')`** —— 真实当前日期已经晚于数据末日,用 `'now'` 会让时间窗整体落在数据之后、返回空结果。

数据量级用大白话说: 几百个广告主、上千个 campaign、八万个关键词,撑起约一百万行效果与转化明细。具体每张表的行数见 ER 文档的文件清单。

---

## 7. 行业知识科普 (看懂数据前的 30 分钟)

这一节是外行看懂这批数据前需要补的背景。

### 7.1 一次搜索广告是怎么跑起来的 (账户层级)

搜索广告的配置是一棵树,从粗到细一共五层:

1. **engine_account (引擎账户):** 广告主在某个搜索引擎下开的账户。一个广告主可以在 Google、Baidu 上各开一个。
2. **campaign (广告系列):** 投放的最大单位,绑定一个引擎账户、一个出价策略、一份预算。比如"电商零售_品牌词_PC端"。
3. **ad_group (广告组):** campaign 下的分组,把主题相近的关键词和广告文案放一起。
4. **keyword (关键词):** 最细的投放单位。你为"雅思培训"这个词出价,用户搜它时你的广告才有机会展示。
5. **text_ad (文字广告):** 真正展示给用户的标题 + 描述文案。

### 7.2 钱是怎么花出去、效果怎么算的 (核心指标链)

每一天、每个 campaign、每种设备,平台都会记一行效果数据。指标之间是一条 **因果链**:

```
展示 (impressions) → 点击 (clicks) → 花费 (cost) → 转化 (conversions) → 转化价值 (conversion_value)
                  └ CTR              └ CPC          └ 转化率           └ ROAS / CPA
```

- 用户看到广告 = 一次 **展示 (impression)**。
- 用户点进来 = 一次 **点击 (click)**,广告主按 CPC 付费。
- 点击里有一部分最终完成了目标动作(下单、留资)= **转化 (conversion)**。
- 转化带来的价值(订单金额、留资价值)= **conversion_value**。

由这条链派生出四个最常用的效率指标: **CTR**(点得勤不勤)、**CPC**(点一次多贵)、**CPA**(换一个转化多贵)、**ROAS**(花一块钱赚回几块)。公式见第 9 节。

### 7.3 展示份额: 你拿到了多少本该属于你的展示 (impression share)

竞价市场里,你的广告不是每次都能展示。**展示份额 (impression share, IS)** = 你实际拿到的展示 ÷ 你本来有资格拿到的展示。没拿到的那部分,只有两个原因:

```
impression_share + lost_is_budget + lost_is_rank = 100%
   (你拿到的)      (因预算丢的)      (因排名/质量丢的)
```

- **lost_is_budget 高** → 预算不够,钱花光了就停展示。**加预算就能直接换回展示**(对应 Q1)。
- **lost_is_rank 高** → 出价太低或质量得分太差,拍卖排名上不去。**要么提价、要么改善广告质量**。

这三个数字的拆解,是判断一个 campaign"该加预算还是该改素材"的最直接依据。

### 7.4 自动出价 vs 手动出价 (bidding)

- **手动出价 (Manual CPC):** 人工给每个关键词设最高点击出价。
- **自动出价 (Smart Bidding):** 把目标交给算法(我要 Target CPA = ¥80,或 Target ROAS = 4x),算法实时调价去逼近目标。常见类型: Enhanced CPC、Target CPA、Target ROAS、Maximize Conversions / Conversion Value / Clicks、Target Impression Share。

判断一个自动出价策略好不好,看 **达成率**: 实际 CPA 是否压到了 Target CPA 以下,实际 ROAS 是否达到了 Target ROAS(对应 Q2)。

### 7.5 质量得分 (Quality Score)

搜索引擎给每个关键词打一个 **1–10 的质量得分 (Quality Score, QS)**,由三个子维度合成: **预期点击率 (expected CTR)**、**广告相关性 (ad relevance)**、**落地页体验 (landing page experience)**,每个子维度取值 Below / Average / Above Average。QS 越高,同样的排名你出价可以更低 —— 所以 **低 QS = 隐性多花钱**。这也是 Q3 的核心:揪出高花费低 QS 的关键词。

> **数据里的一个练习陷阱:** 本数据集为简化,三个质量子维度与 QS 是 **独立采样** 的,可能出现"三个子维度都 Above Average、QS 却很低"的不自洽行。这不是 bug,而是刻意留的分析练习题 —— 真实平台里这种不一致往往意味着数据质量问题,分析师需要能把它们查出来。

### 7.6 搜索词 vs 关键词 (search term vs keyword)

这两个词很容易混。**关键词 (keyword)** 是你 *主动出价* 的词;**搜索词 (search term)** 是用户 *实际输入* 的词。在广泛匹配 (broad match) 下,你买了"英语培训",用户搜"上海英语培训哪家好"也可能触发你的广告 —— 后者就是一条搜索词。

搜索词报告是 SEM 的金矿: 真实搜索词高度长尾、大量唯一。挖掘动作有两类,用 `added_excluded` 字段记录:

- **加词 (Added):** 这个搜索词表现好,提升为正式关键词去放量。
- **否定 (Excluded):** 这个搜索词花了钱没转化,加为否定关键词去止血。
- **None:** 还没人处理过,等分析师挖掘 —— 这是 Q4 要找的对象。

> **数据里的口径陷阱:** `added_excluded` 的"未处理"是 **字面量字符串 `'None'`,不是 SQL NULL**。过滤时用 `= 'None'` 而不是 `IS NULL`。

### 7.7 多触点归因 (multi-touch attribution)

一笔转化往往不是一次点击促成的,而是用户多次接触(看了展示、点了社交、搜了品牌词)后才完成。**归因 (attribution)** 解决的问题是:这笔转化的功劳 (credit) 该怎么分给路径上的各个触点 (touchpoint)。不同模型分法不同:

| 模型 | 功劳怎么分 | 直觉 |
|------|-----------|------|
| **Last Click** | 全给最后一个触点 | "临门一脚"最重要 |
| **First Click** | 全给第一个触点 | "把人领进门"最重要 |
| **Linear** | 所有触点平分 | 大家都有功 |
| **Time Decay** | 越靠近转化权重越大 | 近因更重要 |
| **Position Based** | 首末各 40%,中间分 20% | 两头最重要 |
| **Data Driven** | 算法按数据分配 | 让数据说话 |

同一份触点数据,六个模型的功劳之和都恒等于 1.0(每笔转化每个模型独立归一)。对比这六个模型,能看出哪个渠道是"开路先锋"、哪个是"临门一脚"(对应 Q5)。

### 7.8 历史化预算 (SCD2)

预算会被反复调整。`campaign_budget` 用 **缓慢变化维度第二型 (Slowly Changing Dimension Type 2, SCD2)** 记录每一次调整: 每条预算带一个生效区间 `[effective_date_start, effective_date_end)`,最新一条的 end 为 NULL 表示"至今生效"。

> **数据里的 JOIN 陷阱:** 查"某天生效的预算"必须用区间匹配 `effective_date_start <= 日期 AND (effective_date_end IS NULL OR effective_date_end > 日期)`,否则一个 campaign 的多条历史预算会 **一对多扇出 (fan-out)**,把花费、转化等指标重复计算放大好几倍。

---

## 8. 术语表 (Glossary)

每个术语给一句大白话解释 + 一句"在这里为什么重要"。英文术语保持英文。

| 术语 | 大白话解释 | 为什么在这里重要 |
|------|-----------|----------------|
| **CPC** (Cost Per Click) | 用户点一次广告,广告主付的钱 | 搜索广告的计费方式,CPC × 点击数 = 花费 |
| **CTR** (Click-Through Rate) | 点击 ÷ 展示,广告吸不吸引人 | 衡量素材和关键词相关性,本数据集均值 ~3.5% |
| **CPA** (Cost Per Acquisition) | 换一个转化要花多少钱 | 评估投放效率;Q2 的达成率就看实际 CPA vs Target CPA |
| **ROAS** (Return On Ad Spend) | 花一块钱广告费赚回几块转化价值 | 最核心的盈利指标,本数据集均值 ~3.3x,<2x 算亏 |
| **Conversion** | 用户完成了目标动作(下单/留资/注册) | 投放的最终目的;归因分析的对象 |
| **Conversion Value** | 一次转化带来的价值(订单额、留资估值) | ROAS 的分子;购买类高、留资类低 |
| **Impression Share** (IS) | 实际展示 ÷ 有资格的展示 | 衡量"还有多少展示没拿到",拆成 budget/rank 两类损失 |
| **Lost IS (Budget)** | 因预算不足丢掉的展示份额 | Q1 的核心信号,>20% 说明该加预算 |
| **Lost IS (Rank)** | 因出价低/质量差丢掉的展示份额 | >30% 说明该提价或改素材 |
| **Quality Score** (QS) | 关键词的 1–10 质量评分 | 低 QS 推高 CPC;Q3 的核心 |
| **Keyword** | 广告主主动出价的词 | 投放的最细单位 |
| **Search Term** | 用户实际输入的搜索词 | 可能不等于关键词;Q4 挖掘对象 |
| **Match Type** | 关键词的匹配宽度: EXACT / PHRASE / BROAD | 越宽触发的搜索词越长尾、越杂 |
| **Negative Keyword** | 否定关键词,屏蔽不想要的搜索词 | Q4 的"止血"动作 |
| **Bid Strategy** | 出价策略,手动或自动 | Q2 的研究对象 |
| **Target CPA / Target ROAS** | 自动出价要逼近的目标值 | 达成率 = 实际值 vs 目标值 |
| **Impression Share %** (Target IS) | 以"拿到 X% 展示份额"为目标的出价策略 | Target Impression Share 策略的参数 |
| **Campaign / Ad Group / Keyword** | 投放层级: 系列 → 组 → 词 | 账户结构的三级树 |
| **Engine Account** | 广告主在某搜索引擎下的账户 | 多引擎聚合的入口 |
| **Floodlight Tag** | Search Ads 360 里的转化跟踪代码(类似 pixel) | 决定一笔转化算哪种类型、回溯多少天 |
| **Lookback Window** | 转化回溯窗口(7/14/30/60/90 天) | 转化前多久的触点还算数 |
| **Attribution Model** | 归因模型,决定功劳怎么分 | Q5 的六个对比对象 |
| **Touchpoint** | 转化路径上的一次接触(点击/展示/浏览) | 归因的最小单位 |
| **Assisted Conversion** | 辅助转化: 参与了路径但不是临门一脚 | 衡量上游渠道的隐形贡献 |
| **Take-Rate** | 平台/代理按消费额抽成的比例 | Lumenly 和代理商的收入来源 |
| **Advertiser Tier** | 客户分层: SMB / Mid-Market / Enterprise | 决定服务模式和消费量级 |
| **SCD2** (Slowly Changing Dimension Type 2) | 用生效区间记录字段历史变化 | campaign_budget 的历史化方式 |
| **Reconciled Field** | 由子表聚合回填的父表字段 | 如 lifetime_cost,供 Agent 自校验 |
| **Polymorphic Association** | 多态关联: 一个外键按 type 指向不同表 | daily_stats.entity_type/entity_id |
| **QBR** (Quarterly Business Review) | 季度业务回顾 | Enterprise 客户的服务节奏 |

---

## 9. 关键指标公式

下列公式是数据集中所有核心指标的 **规范定义**。SQL 查询里出现的聚合都应与这里一致;若两处口径打架,以本节为准。聚合时统一用 `SUM` 后再相除(先汇总分子分母,再做比值),避免对"每行比率"取平均带来的偏差。

### 9.1 效果指标 (来源: daily_stats)

```
CTR  (点击率)       = SUM(clicks) / SUM(impressions)
Avg CPC (平均点击成本) = SUM(cost) / SUM(clicks)
Conv Rate (转化率)   = SUM(conversions) / SUM(clicks)
CPA  (单次转化成本)  = SUM(cost) / SUM(conversions)        -- conversions=0 时为 NULL
ROAS (广告支出回报)  = SUM(conversion_value) / SUM(cost)
```

### 9.2 展示份额指标 (来源: daily_stats)

```
Impression Share = AVG(impression_share)
Lost IS Budget   = AVG(lost_is_budget)      -- 阈值 > 20% → 预算受限, 该加预算
Lost IS Rank     = AVG(lost_is_rank)        -- 阈值 > 30% → 排名/质量不足, 该提价或改素材
恒等式: impression_share + lost_is_budget + lost_is_rank = 100   (每行成立)
```

### 9.3 出价与预算指标

```
Target CPA Attainment  = actual_cpa / target_cpa - 1      -- 负值 = 优于目标
Target ROAS Attainment = actual_roas / target_roas - 1    -- 正值 = 优于目标
Budget Utilization     = avg_daily_spend / daily_budget   -- 预算使用率
Automated Bid %        = COUNT(自动出价 campaign) / COUNT(全部 campaign)
```

> **预算使用率口径:** `avg_daily_spend` 取参考日当天 **生效** 的那一条预算(用 SCD2 区间匹配),再用近 7 日花费 ÷ 活跃天数得到日均花费。普通 campaign 使用率落在 55%–95%,预算受限 campaign 会 >100%。

### 9.4 关键词指标 (来源: keyword)

```
Avg Quality Score   = AVG(quality_score) WHERE status='Enabled'
Low QS Keyword %    = COUNT(quality_score < 6) / COUNT(*)
CPC Gap to Top      = max_cpc - top_of_page_cpc     -- 离页首出价还差多少
```

### 9.5 搜索词指标 (来源: search_term_report)

```
Search Term Conv Rate   = SUM(conversions) / SUM(clicks)   GROUP BY search_term
Negative Keyword Candidate = cost > 50 AND conversions = 0 AND added_excluded = 'None'
High Value Term Candidate  = conversions > 0 AND added_excluded = 'None'
```

### 9.6 归因指标 (来源: attribution_path × conversion)

```
{model} Touch Value = SUM({model}_credit * conversion.conversion_value)   GROUP BY 渠道/维度
  其中 {model} ∈ {last_click, first_click, linear, time_decay, position, data_driven}
Avg Path Length     = AVG( MAX(touchpoint_order) GROUP BY conversion_id )   -- 平均触点数 ~4
Time to Conversion  = AVG(hours_before_conv) WHERE touchpoint_order = 1     -- 首触到转化时长
```

### 9.7 账户健康指标 (来源: advertiser × agency_client × daily_stats)

```
Active Advertiser Count = COUNT WHERE account_status = 'Active'
Customer Concentration  = SUM(Top 10 客户花费) / SUM(全部花费)
Agency Fee Revenue      = SUM(广告主花费 * agency_client.fee_percentage / 100)
Contract Expiring 30d   = COUNT WHERE contract_end BETWEEN '2026-06-01' AND '2026-07-01'
```

---

> **下一步:** 理解了公司、行业和指标之后,去看 `02-search_ads_360_agent_large_er_document-cn.md` 了解数据怎么组织,再用 `03-search_ads_360_agent_large_sql_queries-cn.md` 动手查询。
