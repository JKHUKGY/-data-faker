# Search Ads 360 智能分析 Agent - SQL 查询参考

> **数据集:** `search_ads_360_agent_large`
> **业务背景 / 行业科普 / 术语表 / 指标公式:** 请见 `01-search_ads_360_agent_large_business_context-cn.md`
> **表结构 / 字段 / 约束 / DDL:** 请见 `02-search_ads_360_agent_large_er_document-cn.md`
> **参考当前日期 (REFERENCE_DATE):** `2026-06-01`

本文档收录 28 条覆盖 Lumenly Ads 全部核心业务场景的 SQL 查询,既是 **Text-to-SQL Agent 的参考语料**,也是 **新分析师的实操练习册**。

---

## 如何使用本文档

**这份文档是写给谁的。** 假设你是刚加入 Lumenly Ads 数据团队的实习分析师,已经读完了业务背景文档(知道公司是做什么的、6 个业务问题是什么)和 ER 文档(知道有哪些表、怎么 JOIN)。你的 manager 把这份文档丢给你,说"这周把这些查询都过一遍"。

**每条查询有五段,按固定顺序排列:**

1. **业务背景** —— 谁在问、为什么问、答案要拿去做什么决策、为什么是现在。先搞清楚问题,再写 SQL。
2. **类别 / 难度 / 角色** —— 三个标签。类别说明用到的 SQL 技术,难度分 Basic / Intermediate / Advanced,角色对应业务背景文档里的岗位。
3. **解题思路** —— 在你看 SQL 之前,先讲清楚要碰哪些表、JOIN 怎么搭、聚合的粒度是什么、哪里有坑。读完这段,你应该已经能在脑子里把 SQL 拼个八九不离十。
4. **SQL** —— 可直接在生成的 SQLite 库上运行的查询。这些 SQL 是用来读、用来学的,不只是用来跑的。
5. **期望结果 + 业务结论** —— 结果长什么样(行数、列含义、关键量级),以及拿到结果后分析师 **下一步该做什么**。跑出数字只是分析的开始,不是结束。

**两条全局约定 (务必牢记):**

- **固定参考日:** 本数据集是 **冻结快照**,数据末日 = `2026-06-01`。所有时间过滤 **必须** 以 `DATE('2026-06-01', ...)` 为基准,**绝不用 `DATE('now', ...)`** —— 真实今天已晚于数据末日,用 `'now'` 会让时间窗整体落空,返回空结果。
- **每条查询都能追溯到一个业务问题。** 文档末尾有"业务问题 → 查询"映射表。如果一条查询找不到对应的业务问题,它就不该出现在这里。

**查询索引:**

| 编号 | 标题 | 业务角色 | SQL 类别 | 难度 | 业务问题 |
|------|------|----------|----------|------|----------|
| 1.1 | 列出所有广告主 | Marketing Analyst | Join | Basic | 索引 |
| 1.2 | 金牌代理商管理的客户 | Account Manager | Join + 过滤 | Basic | Q6 |
| 1.3 | 广告系列层级与广告组数 | Campaign Manager | LEFT JOIN + 聚合 | Basic | 运营 |
| 2.1 | 上周花费 Top 5 广告系列 | Performance Manager | 聚合 + Join | Basic | Q1 |
| 2.2 | 设备维度效果对比 | Performance Analyst | 聚合 + Join | Intermediate | 设备维度 |
| 2.3 | 各行业广告效果 | CMO | 聚合 + 多 Join | Intermediate | Q6 |
| 2.4 | 每日花费转化趋势 | Performance Manager | 时间序列聚合 | Basic | 运营 |
| 3.1 | 各出价策略效果对比 | Bid Manager | 聚合 + 多 Join | Intermediate | Q2 |
| 3.2 | Target CPA 达成分析 | Bid Manager | CTE + 派生指标 | Intermediate | Q2 |
| 3.3 | Target ROAS 达成分析 | Trading Desk | CTE + 派生指标 | Intermediate | Q2 |
| 4.1 | 因预算损失的展示份额 | Media Planner | 聚合 + HAVING | Intermediate | Q1 |
| 4.2 | 页首展示份额分析 | Search Specialist | 聚合 | Intermediate | 展示份额 |
| 5.1 | 质量得分分布 | Search Specialist | 聚合 + 子查询 | Basic | Q3 |
| 5.2 | 高花费低质量关键词 | Search Specialist | Join + 过滤 | Basic | Q3 |
| 5.3 | 匹配类型分布 | SEM Specialist | 聚合 + Join | Basic | Q3 |
| 6.1 | 高转化搜索词 | SEM Specialist | 聚合 + HAVING | Intermediate | Q4 |
| 6.2 | 高花费零转化搜索词 | SEM Specialist | 聚合 + HAVING | Intermediate | Q4 |
| 6.3 | 搜索词匹配类型效果 | SEM Specialist | 聚合 | Intermediate | Q4 |
| 7.1 | 各归因模型渠道价值 | Marketing Analytics | 多 Join + 聚合 | Advanced | Q5 |
| 7.2 | 转化路径长度分析 | Marketing Analytics | 子查询 + 窗口函数 | Intermediate | Q5 |
| 7.3 | 首次 vs 末次触点渠道 | Marketing Analytics | 多 CTE + LEFT JOIN | Advanced | Q5 |
| 7.4 | 转化前平均时间 | Marketing Analytics | 聚合 + 过滤 | Intermediate | Q5 |
| 8.1 | 预算使用率 | Media Planner | CTE + SCD2 Join | Advanced | Q1 |
| 8.2 | 预算不足的广告系列 | Media Planner | SCD2 Join + HAVING | Advanced | Q1 |
| 9.1 | 广告主健康度检查 | CSM / Account Manager | CTE + CASE | Advanced | Q6 |
| 9.2 | 优化机会识别 | Campaign Manager | 聚合 + CASE | Intermediate | Q1 / Q3 |
| 10.1 | 诊断 CPA 上涨原因 | Performance Manager | 多步 + 条件透视 | Advanced | Q2 / 运营 |
| 10.2 | 归因模型对比分析 | Marketing Analytics | 多 Join + 派生 | Advanced | Q5 |

---

## 1. 基础查询

### 1.1 查询所有广告主信息

**业务背景:** 你刚拿到 Lumenly Ads 的数据库访问权限,manager 让你先"熟悉一下客户盘子"。第一步永远是把核心实体表打开看看 —— 广告主 (advertiser) 是这个平台的中心实体,所有 campaign、花费、转化都挂在它下面。这条查询不解决具体决策,但它是你后续所有分析的起点: 先认识有哪些客户、各属于什么行业、什么规模、什么消费档位。

**类别 / 难度 / 角色:** Join | Basic | Marketing Analyst

**解题思路:** 只需要 `advertiser` 一张主表,加一个 `industry` 维度表把 `industry_id` 翻译成中文行业名。这是最基础的"事实表 JOIN 维度表"模式: 广告主表存的是行业的外键(数字),要看人话得 JOIN 维度表。用 INNER JOIN 即可,因为每个广告主都有合法的 `industry_id`(NOT NULL 外键)。按 id 排序保证结果稳定。

```sql
-- 自然语言: "列出所有广告主的基本信息"
SELECT
    a.advertiser_code,
    a.company_name,
    i.name AS industry,
    a.company_size,
    a.monthly_spend_tier,
    a.primary_goal,
    a.account_status
FROM advertiser a
JOIN industry i ON a.industry_id = i.id
ORDER BY a.id;
```

**期望结果 + 业务结论:** 返回 150 行,每行一个广告主,带行业、规模 (SMB/Mid-Market/Enterprise)、月消费档、主要目标、账户状态。你会看到 SMB 约占一半、Active 状态约 85%。这只是热身: 下一步可以按 `company_size` 或 `account_status` 分组计数,快速建立对客户结构的整体感觉,为后面的健康度分析 (9.1) 打底。

### 1.2 查询代理商管理的客户

**业务背景:** Lumenly Ads 的 Account Manager 想知道"金牌 (Gold) 代理商手里都攥着哪些客户"。代理商分 Gold / Silver / Bronze / Standard 四级,Gold 代理商通常服务的是大客户、收的服务费也更高。这条查询帮 Account Manager 摸清头部代理商的客户构成,为续约谈判和资源倾斜提供依据 —— 这关系到业务问题 Q6 (客户组合健康)。

**类别 / 难度 / 角色:** Join + 过滤 | Basic | Account Manager

**解题思路:** 这是一条"穿三张表"的链式 JOIN: `agency`(代理商)→ `agency_client`(代理-客户合同,M:N 关联表)→ `advertiser`(客户),再带上 `industry` 翻译行业。关键是理解 `agency_client` 是个 **桥表 (bridge table)**,它把代理商和广告主多对多地连起来,合同期、费率都在它身上。过滤条件有两个: `tier_level = 'Gold'` 只看金牌代理商,`is_active = 1` 只看仍在生效的合同(避免把已流失客户算进来)。

```sql
-- 自然语言: "金牌代理商管理了哪些客户？"
SELECT
    ag.agency_name,
    ag.tier_level,
    a.company_name AS client_name,
    i.name AS industry,
    ac.fee_percentage,
    ac.contract_start
FROM agency ag
JOIN agency_client ac ON ag.id = ac.agency_id
JOIN advertiser a ON ac.advertiser_id = a.id
JOIN industry i ON a.industry_id = i.id
WHERE ag.tier_level = 'Gold'
    AND ac.is_active = 1
ORDER BY ag.agency_name, a.company_name;
```

**期望结果 + 业务结论:** 返回若干行(Gold 代理商约占 10%,故行数不多),每行是"某金牌代理商 — 某客户 — 行业 — 费率 — 合同起始"。重点看 `fee_percentage` 的分布: 如果某 Gold 代理商手里全是高费率大客户,它就是平台的战略伙伴,续约时要重点维护;如果费率普遍偏低,可能有重新议价空间。

### 1.3 查询广告系列层级结构

**业务背景:** Campaign Manager 在做账户结构盘点,想快速看出"哪些 campaign 搭得最复杂"(下挂广告组最多)。广告组数量是 campaign 复杂度的代理指标 —— 组越多,通常意味着关键词分得越细、管理成本越高。这条查询帮他识别需要重点关注或可能需要精简的复杂 campaign。

**类别 / 难度 / 角色:** LEFT JOIN + 聚合 | Basic | Campaign Manager

**解题思路:** 主表是 `campaign`,要数每个 campaign 下挂多少 `ad_group`。这里必须用 **LEFT JOIN** 而不是 INNER JOIN: 有的 campaign 可能一个广告组都还没建,用 INNER JOIN 会把这些"空壳 campaign"直接剔除,导致盘点遗漏。聚合用 `COUNT(ag.id)`(数子表主键)而不是 `COUNT(*)`,这样没有广告组的 campaign 会得到 0 而不是 1。GROUP BY 要带上所有非聚合的 SELECT 列。

```sql
-- 自然语言: "查看广告系列及其广告组数量"
SELECT
    c.campaign_code,
    c.campaign_name,
    c.campaign_type,
    c.status,
    COUNT(ag.id) AS ad_group_count
FROM campaign c
LEFT JOIN ad_group ag ON c.id = ag.campaign_id
GROUP BY c.id, c.campaign_code, c.campaign_name, c.campaign_type, c.status
ORDER BY ad_group_count DESC
LIMIT 20;
```

**期望结果 + 业务结论:** 返回广告组最多的 20 个 campaign,每个 campaign 通常挂 3–8 个广告组。如果某个 campaign 的 `ad_group_count` 明显高于其他(比如 >15),值得 Campaign Manager 进去看看是不是结构臃肿、关键词重复;如果某些 Enabled 的 campaign 广告组数为 0,那是配置遗漏,要补建。

---

## 2. 效果分析查询

### 2.1 广告系列效果汇总

**业务背景:** 每周一早会,Performance Manager 要回答 CMO 的第一个问题: "上周钱都花哪儿了?" 最直接的答案就是"上周花费最多的 5 个 campaign"。花费 Top N 是所有效果复盘的入口 —— 钱花在哪里,优化的注意力就该先放在哪里。这条查询对应业务问题 Q1(预算与花费),是每周运营节奏的固定动作。

**类别 / 难度 / 角色:** 聚合 + Join | Basic | Performance Marketing Manager

**解题思路:** 核心事实表是 `daily_stats`,它存每日每 campaign 每设备的效果。**这里有本数据集最重要的一个坑: `daily_stats` 是多态表,JOIN campaign 时必须显式带 `AND ds.entity_type = 'Campaign'`** —— 即使当前只有 Campaign 一种实体类型,也要养成这个习惯,否则未来扩展到广告组级数据时会算错。JOIN 链是 `daily_stats → campaign → advertiser`。时间窗用 `report_date >= DATE('2026-06-01', '-7 days')` 取最近 7 天。CPA 用 `SUM(cost)/NULLIF(SUM(conversions),0)` 防止除零。按总花费降序取前 5。

```sql
-- 自然语言: "上周花费最多的5个广告系列是哪些？"
SELECT
    c.campaign_name,
    a.company_name AS advertiser,
    SUM(ds.impressions) AS total_impressions,
    SUM(ds.clicks) AS total_clicks,
    ROUND(SUM(ds.cost), 2) AS total_cost,
    ROUND(SUM(ds.conversions), 2) AS total_conversions,
    ROUND(SUM(ds.cost) / NULLIF(SUM(ds.conversions), 0), 2) AS cpa
FROM daily_stats ds
JOIN campaign c ON ds.entity_id = c.id AND ds.entity_type = 'Campaign'
JOIN advertiser a ON c.advertiser_id = a.id
WHERE ds.report_date >= DATE('2026-06-01', '-7 days')
GROUP BY c.id, c.campaign_name, a.company_name
ORDER BY total_cost DESC
LIMIT 5;
```

**期望结果 + 业务结论:** 返回 5 行,花费最高的 campaign 排在最前,带展示、点击、花费、转化、CPA。重点看这 5 个高花费 campaign 的 CPA: 如果某个 campaign 花得多但 CPA 远高于整体均值 (~¥165),它就是本周优化的头号目标 —— 下一步钻到 4.1 / 8.2 看是不是预算/出价问题,或到 5.2 看关键词质量。

### 2.2 按设备类型分析效果

**业务背景:** Performance Analyst 注意到整体 CPA 在波动,怀疑是不是某个设备端拖了后腿。移动端、桌面端、平板端的用户行为差异巨大: 移动端流量大但转化往往更浅,桌面端转化深但流量小。这条查询把效果按设备拆开,帮分析师判断"要不要按设备调整出价系数"。

**类别 / 难度 / 角色:** 聚合 + Join | Intermediate | Performance Analyst

**解题思路:** `daily_stats` JOIN `device` 维度表,按设备名分组。同样要带 `entity_type = 'Campaign'` 谓词。这里 CTR / CPA / ROAS 三个比率指标都遵循"先 SUM 再相除"的口径(不是对每行比率取平均),分母用 `NULLIF` 防零。时间窗取最近 30 天,样本量足够稳定。注意: device 的 JOIN 用 `ds.device_id`,这是带 FK 约束的常规外键,不是多态字段。

```sql
-- 自然语言: "移动端和桌面端的转化成本差异有多大？"
SELECT
    d.name AS device,
    SUM(ds.impressions) AS impressions,
    SUM(ds.clicks) AS clicks,
    ROUND(SUM(ds.clicks) * 100.0 / NULLIF(SUM(ds.impressions), 0), 2) AS ctr_pct,
    ROUND(SUM(ds.cost), 2) AS cost,
    ROUND(SUM(ds.conversions), 2) AS conversions,
    ROUND(SUM(ds.cost) / NULLIF(SUM(ds.conversions), 0), 2) AS cpa,
    ROUND(SUM(ds.conversion_value) / NULLIF(SUM(ds.cost), 0), 2) AS roas
FROM daily_stats ds
JOIN device d ON ds.device_id = d.id
WHERE ds.entity_type = 'Campaign'
    AND ds.report_date >= DATE('2026-06-01', '-30 days')
GROUP BY d.id, d.name
ORDER BY cost DESC;
```

**期望结果 + 业务结论:** 返回 3 行 (Mobile / Desktop / Tablet)。Mobile 花费占比最高 (~55% 展示份额),Desktop 次之,Tablet 最小。横向对比三端的 CPA 和 ROAS: 如果 Mobile 的 CPA 明显高于 Desktop,说明移动端在烧钱,下一步可以建议对 Mobile 下调出价系数,或针对移动端优化落地页。这条结果常被沉淀成"设备表现对比"仪表盘。

### 2.3 按行业分析广告效果

**业务背景:** CMO 要在季度品类回顾上汇报"哪些行业的客户投得最值"。Lumenly Ads 横跨 10 个行业(电商、教育、金融……),不同行业的获客成本天差地别 —— 金融的 CPA 可能是电商的好几倍。这条查询按行业聚合效果,帮 CMO 判断平台的行业结构是否健康、哪些行业值得投入更多销售资源去拉新客户。对应业务问题 Q6。

**类别 / 难度 / 角色:** 聚合 + 多 Join | Intermediate | CMO / Marketing Director

**解题思路:** JOIN 链最长: `daily_stats → campaign → advertiser → industry`,把效果一路上卷到行业粒度。仍需 `entity_type = 'Campaign'` 谓词。`COUNT(DISTINCT a.id)` 数出每个行业有多少活跃广告主(用 DISTINCT 避免被 daily_stats 的一对多扇出重复计数 —— 这是聚合查询里最常见的错误)。CPA、ROAS 照例先 SUM 再相除。

```sql
-- 自然语言: "各行业的平均CPA是多少？"
SELECT
    i.name AS industry,
    COUNT(DISTINCT a.id) AS advertiser_count,
    ROUND(SUM(ds.cost), 2) AS total_cost,
    ROUND(SUM(ds.conversions), 2) AS total_conversions,
    ROUND(SUM(ds.cost) / NULLIF(SUM(ds.conversions), 0), 2) AS avg_cpa,
    ROUND(SUM(ds.conversion_value) / NULLIF(SUM(ds.cost), 0), 2) AS avg_roas
FROM daily_stats ds
JOIN campaign c ON ds.entity_id = c.id AND ds.entity_type = 'Campaign'
JOIN advertiser a ON c.advertiser_id = a.id
JOIN industry i ON a.industry_id = i.id
WHERE ds.report_date >= DATE('2026-06-01', '-30 days')
GROUP BY i.id, i.name
ORDER BY total_cost DESC;
```

**期望结果 + 业务结论:** 返回 10 行(每个行业一行),按总花费降序。`advertiser_count` 一列要特别留意 —— 它是用 DISTINCT 数出来的真实广告主数,而不是被扇出放大的数字。对比各行业的 avg_roas: ROAS 明显偏低的行业,要么是该行业本身难做,要么是平台在该行业的客户投放能力弱,CMO 据此决定下季度的行业拓展优先级。

### 2.4 效果趋势分析

**业务背景:** Performance Manager 每天盯大盘,需要一张"过去两周每日花费与转化走势"来感知节奏 —— 是平稳、在涨、还是某天突然异常。趋势图是最早暴露问题的地方: 某天花费暴涨而转化没跟上,往往意味着出价失控或预算被恶意消耗。

**类别 / 难度 / 角色:** 时间序列聚合 | Basic | Performance Marketing Manager

**解题思路:** 这是最纯粹的时间序列聚合: 不 JOIN 任何维度表,直接对 `daily_stats` 按 `report_date` 分组。只需带 `entity_type = 'Campaign'` 谓词 + 14 天时间窗。按日期升序排列,结果天然就是一条时间线。这类查询是"看趋势"的基础,后续可在 BI 工具里直接画成折线。

```sql
-- 自然语言: "过去两周的每日花费和转化趋势"
SELECT
    ds.report_date,
    SUM(ds.impressions) AS impressions,
    SUM(ds.clicks) AS clicks,
    ROUND(SUM(ds.cost), 2) AS cost,
    ROUND(SUM(ds.conversions), 2) AS conversions,
    ROUND(SUM(ds.cost) / NULLIF(SUM(ds.conversions), 0), 2) AS cpa
FROM daily_stats ds
WHERE ds.entity_type = 'Campaign'
    AND ds.report_date >= DATE('2026-06-01', '-14 days')
GROUP BY ds.report_date
ORDER BY ds.report_date;
```

**期望结果 + 业务结论:** 返回 14 行(每天一行),花费和转化大体平稳。重点看 cpa 列有没有某天突然跳高: 如果某天 CPA 明显偏离基线,下一步直接拿那天去 10.1 做根因诊断(拆 CPC / CTR / 转化率)。这条查询本身就是 D6"每日效果快照"仪表盘的数据底座。

---

## 3. 出价策略分析

### 3.1 各出价策略效果对比

**业务背景:** Bid Manager 要回答一个长期争论: "自动出价 (smart bidding) 到底比手动出价好多少?" 平台支持 8 种出价策略,其中 7 种是自动的。如果自动出价的 CPA / ROAS 系统性优于手动,就该推动更多客户迁移到自动出价 —— 这既提升客户效果,也降低人工调价的运营成本。直接对应业务问题 Q2。

**类别 / 难度 / 角色:** 聚合 + 多 Join | Intermediate | Trading Desk / Bid Manager

**解题思路:** 要把效果按"出价策略类型"聚合,JOIN 链是 `daily_stats → campaign → bid_strategy → bid_strategy_type`。`bid_strategy_type` 上有个关键的 `is_automated` 布尔标志,把它放进 GROUP BY 就能直接对比自动 vs 手动。`COUNT(DISTINCT c.id)` 数 campaign 数避免扇出。注意: 这里用 INNER JOIN bid_strategy,意味着没绑定出价策略的少数 campaign 会被排除 —— 这是合理的,因为我们就是要分析"用了策略的"campaign。

```sql
-- 自然语言: "不同出价策略的转化效果如何？"
SELECT
    bst.name AS strategy_type,
    bst.is_automated,
    COUNT(DISTINCT c.id) AS campaign_count,
    ROUND(SUM(ds.cost), 2) AS total_cost,
    ROUND(SUM(ds.conversions), 2) AS total_conversions,
    ROUND(SUM(ds.cost) / NULLIF(SUM(ds.conversions), 0), 2) AS avg_cpa,
    ROUND(SUM(ds.conversion_value) / NULLIF(SUM(ds.cost), 0), 2) AS avg_roas
FROM daily_stats ds
JOIN campaign c ON ds.entity_id = c.id AND ds.entity_type = 'Campaign'
JOIN bid_strategy bs ON c.bid_strategy_id = bs.id
JOIN bid_strategy_type bst ON bs.strategy_type_id = bst.id
WHERE ds.report_date >= DATE('2026-06-01', '-30 days')
GROUP BY bst.id, bst.name, bst.is_automated
ORDER BY total_cost DESC;
```

**期望结果 + 业务结论:** 返回最多 8 行(每种策略类型一行),带 `is_automated` 标志。把自动 (is_automated=1) 和手动 (=0) 两组的加权 CPA / ROAS 各自汇总对比,就能给出"自动出价整体优于/劣于手动"的结论。注意本数据集策略类型是随机分配的,效果差异主要来自抽样,结论应作为方法演示而非真实业务定论。下一步可对表现最差的策略类型钻取到 3.2 / 3.3 看具体 campaign 的达成率。

### 3.2 目标CPA达成分析

**业务背景:** 设了 Target CPA 的 campaign,Bid Manager 最关心的是"算法有没有把成本压到目标线以下"。如果一批 campaign 的实际 CPA 长期高于 Target CPA,说明出价目标设得不现实,或者关键词/落地页质量拖累了转化。Bid Manager 需要一张"超标排行榜"来安排本周的调优顺序。对应业务问题 Q2。

**类别 / 难度 / 角色:** CTE + 派生指标 | Intermediate | Trading Desk / Bid Manager

**解题思路:** 分两步,用 CTE 让逻辑清晰。CTE `campaign_performance` 先算出每个设了 `target_cpa` 的 campaign 在最近 7 天的实际 CPA(JOIN campaign → bid_strategy → daily_stats,过滤 `target_cpa IS NOT NULL`)。外层再筛出 `actual_cpa > target_cpa` 的,并算超标百分比 `(actual - target)/target * 100`。用 CTE 的好处是: 派生指标 actual_cpa 在 CTE 里算一次,外层可以直接拿来比较和再计算,避免把一长串聚合表达式写两遍。

```sql
-- 自然语言: "哪些广告系列的CPA超过了目标值？"
WITH campaign_performance AS (
    SELECT
        c.id AS campaign_id,
        c.campaign_name,
        a.company_name,
        bs.target_cpa,
        ROUND(SUM(ds.cost), 2) AS total_cost,
        ROUND(SUM(ds.conversions), 2) AS total_conversions,
        ROUND(SUM(ds.cost) / NULLIF(SUM(ds.conversions), 0), 2) AS actual_cpa
    FROM campaign c
    JOIN advertiser a ON c.advertiser_id = a.id
    JOIN bid_strategy bs ON c.bid_strategy_id = bs.id
    JOIN daily_stats ds ON c.id = ds.entity_id AND ds.entity_type = 'Campaign'
    WHERE bs.target_cpa IS NOT NULL
        AND ds.report_date >= DATE('2026-06-01', '-7 days')
    GROUP BY c.id, c.campaign_name, a.company_name, bs.target_cpa
)
SELECT
    company_name,
    campaign_name,
    target_cpa,
    actual_cpa,
    ROUND((actual_cpa - target_cpa) / target_cpa * 100, 1) AS over_target_pct,
    total_cost,
    total_conversions
FROM campaign_performance
WHERE actual_cpa > target_cpa
ORDER BY over_target_pct DESC
LIMIT 20;
```

**期望结果 + 业务结论:** 返回最多 20 个超标 campaign,按超标百分比降序。`over_target_pct` 越大,问题越严重。Bid Manager 据此排优先级: 超标 50%+ 的 campaign 先处理 —— 要么调高 Target CPA(承认目标定低了),要么暂停高 CPA 关键词。这张表通常作为"出价策略效果看板 (告警阈值: 达成率 <80%)"的核心。

### 3.3 目标ROAS达成分析

**业务背景:** 和 Target CPA 对应,设了 Target ROAS 的 campaign(多见于电商客户),Trading Desk 关心的是"回报率有没有达标"。ROAS 没达标意味着广告花的钱没换回足够的转化价值,继续投就是亏损。Trading Desk 需要找出"未达标且差距最大"的 campaign,决定是降预算止损还是调整出价目标。对应业务问题 Q2。

**类别 / 难度 / 角色:** CTE + 派生指标 | Intermediate | Trading Desk / Bid Manager

**解题思路:** 结构和 3.2 镜像对称,只是把 target_cpa 换成 target_roas,把"超标"换成"未达标"。CTE `campaign_roas` 算出每个设了 `target_roas` 的 campaign 的实际 ROAS = `SUM(conversion_value)/SUM(cost)`。外层筛 `actual_roas < target_roas`,算缺口百分比 `(target - actual)/target * 100`(注意方向: ROAS 是越高越好,所以缺口是 target 减 actual)。

```sql
-- 自然语言: "ROAS低于目标的广告系列有哪些？"
WITH campaign_roas AS (
    SELECT
        c.id AS campaign_id,
        c.campaign_name,
        a.company_name,
        bs.target_roas,
        ROUND(SUM(ds.cost), 2) AS total_cost,
        ROUND(SUM(ds.conversion_value), 2) AS total_value,
        ROUND(SUM(ds.conversion_value) / NULLIF(SUM(ds.cost), 0), 2) AS actual_roas
    FROM campaign c
    JOIN advertiser a ON c.advertiser_id = a.id
    JOIN bid_strategy bs ON c.bid_strategy_id = bs.id
    JOIN daily_stats ds ON c.id = ds.entity_id AND ds.entity_type = 'Campaign'
    WHERE bs.target_roas IS NOT NULL
        AND ds.report_date >= DATE('2026-06-01', '-7 days')
    GROUP BY c.id, c.campaign_name, a.company_name, bs.target_roas
)
SELECT
    company_name,
    campaign_name,
    target_roas,
    actual_roas,
    ROUND((target_roas - actual_roas) / target_roas * 100, 1) AS below_target_pct,
    total_cost,
    total_value
FROM campaign_roas
WHERE actual_roas < target_roas
ORDER BY below_target_pct DESC
LIMIT 20;
```

**期望结果 + 业务结论:** 返回最多 20 个未达标 campaign,按缺口百分比降序。`below_target_pct` 接近 100% 的 campaign 几乎没产生转化价值,是止损首选。Trading Desk 的下一步: 缺口大但花费也大的 campaign 优先降预算或暂停;缺口大但花费小的可以再观察一周。

---

## 4. 展示份额分析

### 4.1 因预算损失的展示份额

**业务背景:** 这是 Lumenly Ads 帮客户"花更多钱"的最直接抓手,也是业务问题 Q1 的核心。Media Planner 要找出那些"明明有需求、却因为预算上限而被迫少展示"的 campaign —— 它们的 `lost_is_budget`(因预算损失的展示份额)很高。对这些 campaign 加预算,几乎可以立刻换来更多展示和转化,是确定性最高的增长动作。

**类别 / 难度 / 角色:** 聚合 + HAVING | Intermediate | Media Planner

**解题思路:** 对 `daily_stats` 按 campaign 聚合三个展示份额指标的均值: `impression_share`(拿到的)、`lost_is_budget`(因预算丢的)、`lost_is_rank`(因排名丢的)—— 这三者每行相加恒等于 100。关键在 **HAVING**: 先 GROUP BY 算出每个 campaign 的平均 `lost_is_budget`,再用 `HAVING AVG(ds.lost_is_budget) > 20` 把"预算损失超过 20%"的筛出来。为什么用 HAVING 不用 WHERE: 因为筛选条件作用在聚合结果(平均值)上,WHERE 只能过滤聚合前的原始行。

```sql
-- 自然语言: "哪些广告系列因预算限制损失了超过20%的展示份额？"
SELECT
    c.campaign_name,
    a.company_name,
    ROUND(AVG(ds.impression_share), 1) AS avg_impr_share,
    ROUND(AVG(ds.lost_is_budget), 1) AS avg_lost_budget,
    ROUND(AVG(ds.lost_is_rank), 1) AS avg_lost_rank,
    ROUND(SUM(ds.cost), 2) AS total_cost
FROM daily_stats ds
JOIN campaign c ON ds.entity_id = c.id AND ds.entity_type = 'Campaign'
JOIN advertiser a ON c.advertiser_id = a.id
WHERE ds.report_date >= DATE('2026-06-01', '-7 days')
GROUP BY c.id, c.campaign_name, a.company_name
HAVING AVG(ds.lost_is_budget) > 20
ORDER BY avg_lost_budget DESC
LIMIT 20;
```

**期望结果 + 业务结论:** 返回 `lost_is_budget` 超 20% 的 campaign(约 15% 的 campaign 被设计成"预算受限",故会有可观行数),按预算损失降序。这些就是加预算的候选名单。Media Planner 的下一步动作很明确: 拿这份名单去和客户/Account Manager 谈加预算,并用 8.1 / 8.2 交叉验证它们的预算使用率确实 >100%。

### 4.2 页首展示份额分析

**业务背景:** 对品牌词或高意向词,"排在搜索结果页首" 至关重要 —— 用户往往只点前几条。Search Specialist 想知道哪些 campaign 的页首展示份额最高,以及高页首份额是否真的换来了更高的 CTR 和更低的 CPA。这关系到出价策略里"要不要为页首位置多付钱"的判断。

**类别 / 难度 / 角色:** 聚合 | Intermediate | Search Specialist

**解题思路:** 对 `daily_stats` 按 campaign 聚合两个页首指标: `search_abs_top_is`(绝对页首,即第一条)和 `search_top_is`(页首区域)。这两个指标在数据里满足 `abs_top ≤ top ≤ impression_share` 的有序关系。同时算 CTR 和 CPA 看页首位置的"性价比"。这是一条纯聚合查询,无 HAVING,按绝对页首份额降序取前 20。

```sql
-- 自然语言: "页首展示份额最高的广告系列"
SELECT
    c.campaign_name,
    a.company_name,
    ROUND(AVG(ds.search_abs_top_is), 1) AS avg_abs_top_is,
    ROUND(AVG(ds.search_top_is), 1) AS avg_top_is,
    ROUND(SUM(ds.clicks) * 100.0 / NULLIF(SUM(ds.impressions), 0), 2) AS ctr_pct,
    ROUND(SUM(ds.cost) / NULLIF(SUM(ds.conversions), 0), 2) AS cpa
FROM daily_stats ds
JOIN campaign c ON ds.entity_id = c.id AND ds.entity_type = 'Campaign'
JOIN advertiser a ON c.advertiser_id = a.id
WHERE ds.report_date >= DATE('2026-06-01', '-7 days')
GROUP BY c.id, c.campaign_name, a.company_name
ORDER BY avg_abs_top_is DESC
LIMIT 20;
```

**期望结果 + 业务结论:** 返回页首份额最高的 20 个 campaign,带 CTR 和 CPA。交叉判断: 如果高页首份额的 campaign CTR 也高、CPA 也合理,说明为页首付的溢价是值的;如果页首份额高但 CPA 也高,说明在为不该抢页首的通用词过度付费,Search Specialist 应建议下调这些词的页首出价目标。

---

## 5. 关键词分析

### 5.1 质量得分分布

**业务背景:** Quality Score (QS, 1–10) 是搜索广告的"信用分": QS 越低,同样的排名要付越高的 CPC。Search Specialist 在做月度质量复盘,第一步要看整个账户的 QS 分布 —— 低分关键词占比多高,直接决定了账户有多少"隐性多付的钱"。这是业务问题 Q3 的起点。

**类别 / 难度 / 角色:** 聚合 + 子查询 | Basic | Search Specialist

**解题思路:** 只用 `keyword` 一张表,按 `quality_score` 分组计数。亮点是 SELECT 里的 **标量子查询**: `(SELECT COUNT(*) FROM keyword WHERE status='Enabled')` 算出启用关键词总数作为分母,这样每个分数档的占比就是"该档数量 ÷ 启用总数"。只统计 `status = 'Enabled'` 的关键词,因为暂停/删除的词不再花钱,不影响当前账户质量。

```sql
-- 自然语言: "质量得分低于6的关键词有多少？"
SELECT
    k.quality_score,
    COUNT(*) AS keyword_count,
    ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM keyword WHERE status = 'Enabled'), 2) AS percentage
FROM keyword k
WHERE k.status = 'Enabled'
GROUP BY k.quality_score
ORDER BY k.quality_score;
```

**期望结果 + 业务结论:** 返回按分数 (3–10) 排列的分布表,每档带数量和占比。把 quality_score < 6 的几档占比加起来,就是"低质量关键词占比"。如果这个比例超过 30%(D10 仪表盘的告警阈值),说明账户质量堪忧,Search Specialist 下一步用 5.2 揪出"高花费 + 低 QS"的具体词去优化或暂停。

### 5.2 高花费低质量关键词

**业务背景:** 知道了低 QS 占比,接下来要落到具体的词。Search Specialist 要找的是"既花钱多 (max_cpc 高)、质量又差 (QS < 6)"的关键词 —— 这类词是账户里最该动手的对象: 低 QS 推高它们的实际 CPC,高出价又让它们持续烧钱。直接对应 Q3 的优化动作。

**类别 / 难度 / 角色:** Join + 过滤 | Basic | Search Specialist

**解题思路:** `keyword` JOIN `match_type` 翻译匹配类型,过滤三个条件: `status = 'Enabled'`(还在花钱)、`quality_score < 6`(质量差)、`max_cpc > 5`(出价高)。把三个质量子维度 (expected_ctr / ad_relevance / landing_page_exp) 一并查出来,方便判断 QS 低是哪个环节拖的。这是一条直白的"过滤 + 排序"查询,无聚合。

```sql
-- 自然语言: "哪些关键词质量得分低但花费高？"
-- 注意: daily_stats 目前只存储 Campaign 级别数据，此查询为示例
SELECT
    k.keyword_text,
    mt.name AS match_type,
    k.quality_score,
    k.expected_ctr,
    k.ad_relevance,
    k.landing_page_exp,
    k.max_cpc
FROM keyword k
JOIN match_type mt ON k.match_type_id = mt.id
WHERE k.status = 'Enabled'
    AND k.quality_score < 6
    AND k.max_cpc > 5
ORDER BY k.max_cpc DESC
LIMIT 30;
```

**期望结果 + 业务结论:** 返回最多 30 个"高出价低质量"关键词,按 max_cpc 降序。逐行看三个质量子维度: 如果 landing_page_exp 是 Below Average,优化落地页;如果 ad_relevance 差,改广告文案。对短期内改不动的,直接下调 max_cpc 或暂停。注意数据里三个子维度是独立采样的,可能出现"子维度都不错但 QS 仍 <6"的行 —— 这正是值得人工核查的数据不一致点 (Q3 的练习题)。

### 5.3 匹配类型分布

**业务背景:** 关键词的匹配类型 (EXACT 完全 / PHRASE 短语 / BROAD 广泛) 决定了它能触发多宽的搜索词。SEM Specialist 想了解账户的匹配类型结构: 广泛匹配多意味着覆盖广但杂、需要更多否定词维护;完全匹配多意味着精准但覆盖窄。这关系到搜索词挖掘 (Q4) 的工作量预估。

**类别 / 难度 / 角色:** 聚合 + Join | Basic | SEM Specialist

**解题思路:** `keyword` JOIN `match_type`,按匹配类型分组,数关键词数并算平均 QS 和平均 max_cpc。只看 Enabled 关键词。这条查询帮你建立"账户里三种匹配类型各占多少、质量和出价有无差异"的整体认知,是一条结构盘点型聚合。

```sql
-- 自然语言: "各匹配类型的关键词数量分布"
SELECT
    mt.name AS match_type,
    COUNT(*) AS keyword_count,
    ROUND(AVG(k.quality_score), 1) AS avg_quality_score,
    ROUND(AVG(k.max_cpc), 2) AS avg_max_cpc
FROM keyword k
JOIN match_type mt ON k.match_type_id = mt.id
WHERE k.status = 'Enabled'
GROUP BY mt.id, mt.name
ORDER BY keyword_count DESC;
```

**期望结果 + 业务结论:** 返回 3 行 (EXACT / PHRASE / BROAD)。看广泛匹配 (BROAD) 的占比: 占比越高,搜索词报告里的长尾噪声越多,SEM 需要投入越多精力做否定词维护 (6.2)。如果广泛匹配的平均 QS 明显低于完全匹配,可考虑把部分广泛匹配词收紧为短语匹配。

---

## 6. 搜索词分析

### 6.1 高转化搜索词

**业务背景:** 搜索词报告是 SEM 的金矿。SEM Specialist 每周要从用户实际搜索的长尾词里淘出"转化率特别高、但还没被加为正式关键词"的词 —— 把它们扶正,可以放量获取更精准的流量。这是业务问题 Q4 的"开源"一侧(加词)。

**类别 / 难度 / 角色:** 聚合 + HAVING | Intermediate | SEM Specialist

**解题思路:** `search_term_report` JOIN `keyword`(看是哪个种子词触发的),按 `search_term` 聚合。先用 WHERE 过滤 `clicks > 0`(没点击的词谈不上转化率),再 GROUP BY 搜索词,用 `HAVING SUM(conversions) > 0` 只保留真正产生转化的词。转化率 = `SUM(conversions)/SUM(clicks)`,按它降序。注意 WHERE 和 HAVING 的分工: WHERE 在分组前过滤原始行,HAVING 在分组后过滤聚合结果。

```sql
-- 自然语言: "转化率最高的搜索词有哪些？"
SELECT
    str.search_term,
    k.keyword_text AS matched_keyword,
    str.match_type_used,
    SUM(str.impressions) AS impressions,
    SUM(str.clicks) AS clicks,
    ROUND(SUM(str.cost), 2) AS cost,
    ROUND(SUM(str.conversions), 2) AS conversions,
    ROUND(SUM(str.conversions) * 100.0 / NULLIF(SUM(str.clicks), 0), 2) AS conv_rate_pct
FROM search_term_report str
JOIN keyword k ON str.keyword_id = k.id
WHERE str.report_date >= DATE('2026-06-01', '-7 days')
    AND str.clicks > 0
GROUP BY str.search_term, k.keyword_text, str.match_type_used
HAVING SUM(str.conversions) > 0
ORDER BY conv_rate_pct DESC
LIMIT 30;
```

**期望结果 + 业务结论:** 返回转化率最高的 30 个搜索词。由于真实搜索词高度长尾(仅 ~30% 有点击的词才转化),能进这张表的都是"以小博大"的好词。SEM 的下一步: 把这些词里 `added_excluded='None'`(还没处理)的扶正为完全匹配关键词,单独建组放量。这条对应"高价值搜索词"仪表盘。

### 6.2 高花费无转化搜索词

**业务背景:** 这是 Q4 的"止血"一侧,也是搜索词挖掘里最高频的动作。广泛匹配会让广告触发一堆不相关的搜索词,它们点了、花了钱、却从不转化。SEM Specialist 每两周要把这些"高花费零转化"的词揪出来加为否定关键词,堵住漏钱的口子。这是整个数据集最具代表性的优化场景之一。

**类别 / 难度 / 角色:** 聚合 + HAVING | Intermediate | SEM Specialist

**解题思路:** 结构和 6.1 对称,但目标相反。关键过滤是 `str.added_excluded = 'None'` —— **只看尚未处理的词,避免重复推荐已经加过否定的词**。这里要特别记住数据陷阱: "未处理"是 **字面量字符串 `'None'`,不是 SQL NULL**,所以用 `= 'None'` 而非 `IS NULL`。GROUP BY 搜索词后,用 `HAVING SUM(conversions) = 0 AND SUM(cost) > 50` 筛出"零转化且累计花费超 50 元"的词。

```sql
-- 自然语言: "哪些搜索词花费高但没有转化？建议添加为否定关键词"
-- 只看尚未处理 (added_excluded='None') 的搜索词, 避免重复推荐已处理过的
SELECT
    str.search_term,
    k.keyword_text AS matched_keyword,
    SUM(str.impressions) AS impressions,
    SUM(str.clicks) AS clicks,
    ROUND(SUM(str.cost), 2) AS cost
FROM search_term_report str
JOIN keyword k ON str.keyword_id = k.id
WHERE str.report_date >= DATE('2026-06-01', '-14 days')
    AND str.added_excluded = 'None'
GROUP BY str.search_term, k.keyword_text
HAVING SUM(str.conversions) = 0 AND SUM(str.cost) > 50
ORDER BY cost DESC
LIMIT 30;
```

**期望结果 + 业务结论:** 返回浪费钱最多的 30 个搜索词,按累计花费降序。这就是本周的否定关键词候选清单。SEM 的下一步: 逐个判断这些词是否真的与业务无关(有些零转化只是样本小),确认后加为否定关键词。在生产环境里,这一步会交给 Weekly Optimization Agent 每周自动生成清单 + 推送到 campaign。

### 6.3 搜索词到关键词匹配分析

**业务背景:** SEM Specialist 想从更高层评估"匹配类型的健康度": 广泛匹配触发的搜索词,整体效果(CPA)是不是真的比完全匹配差?如果广泛匹配的 CPA 系统性偏高,说明它带来的长尾流量质量低,需要更严的否定词策略或收紧匹配类型。

**类别 / 难度 / 角色:** 聚合 | Intermediate | SEM Specialist

**解题思路:** 直接对 `search_term_report` 按 `match_type_used`(实际触发的匹配类型,是字符串字段不是 FK)分组。`COUNT(DISTINCT str.search_term)` 数每种匹配类型触发了多少个不同的搜索词 —— 广泛匹配的 distinct 数应该明显最高(因为它最杂)。CPA 照例先 SUM 再相除。无需 JOIN,单表聚合即可。

```sql
-- 自然语言: "广泛匹配触发的搜索词效果如何？"
SELECT
    str.match_type_used,
    COUNT(DISTINCT str.search_term) AS unique_terms,
    SUM(str.impressions) AS impressions,
    SUM(str.clicks) AS clicks,
    ROUND(SUM(str.cost), 2) AS cost,
    ROUND(SUM(str.conversions), 2) AS conversions,
    ROUND(SUM(str.cost) / NULLIF(SUM(str.conversions), 0), 2) AS cpa
FROM search_term_report str
WHERE str.report_date >= DATE('2026-06-01', '-7 days')
GROUP BY str.match_type_used
ORDER BY cost DESC;
```

**期望结果 + 业务结论:** 返回 3 行 (EXACT / PHRASE / BROAD),`unique_terms` 一列直观显示广泛匹配的搜索词多样性最高。对比三者 CPA: 若广泛匹配 CPA 偏高,SEM 应加强对广泛匹配 campaign 的否定词维护节奏,或把高消费广泛匹配词降级为短语匹配。

---

## 7. 归因分析

### 7.1 不同归因模型下的渠道价值

**业务背景:** 这是业务问题 Q5 的旗舰查询,也是 Marketing Analytics 团队最常被 CMO 问到的: "我们的钱花在哪个渠道才真正带来转化?" 答案取决于用哪种归因模型。末次点击会把功劳全给"临门一脚"的渠道(常是品牌词/直接访问),首次点击会奖励"开路"的渠道(常是展示/社交)。把六个模型并排放一起,渠道的真实贡献才看得清。

**类别 / 难度 / 角色:** 多 Join + 聚合 | Advanced | Marketing Analytics / RevOps

**解题思路:** 核心是 `attribution_path`(每个转化的每个触点一行)JOIN `conversion`(取转化价值)JOIN `channel`(取渠道名)。每个触点在 6 种模型下各有一个 credit(权重),且每个 conversion 下每个模型的 credit 之和恒为 1.0。**渠道价值 = 该模型的 credit × 转化价值**,所以六列分别是 `SUM(xxx_credit * c.conversion_value)`。按渠道分组,一次查询同时算出 6 个模型的渠道价值 —— 这正是把 6 个模型放进同一张表的设计红利,不用切 6 次数据源。

```sql
-- 自然语言: "分析不同归因模型下各渠道的价值 (credit × 转化价值)"
-- 价值 = 归因 credit × conversion.conversion_value (KPI §11.6 口径)
SELECT
    ch.name AS channel,
    ROUND(SUM(ap.last_click_credit * c.conversion_value), 2) AS last_click,
    ROUND(SUM(ap.first_click_credit * c.conversion_value), 2) AS first_click,
    ROUND(SUM(ap.linear_credit * c.conversion_value), 2) AS linear,
    ROUND(SUM(ap.time_decay_credit * c.conversion_value), 2) AS time_decay,
    ROUND(SUM(ap.position_credit * c.conversion_value), 2) AS position,
    ROUND(SUM(ap.data_driven_credit * c.conversion_value), 2) AS data_driven
FROM attribution_path ap
JOIN conversion c ON ap.conversion_id = c.id
JOIN channel ch ON ap.channel_id = ch.id
GROUP BY ch.id, ch.name
ORDER BY last_click DESC;
```

**期望结果 + 业务结论:** 返回 6 行(每个渠道一行),6 列分别是 6 个模型下的渠道价值。横向读一行就能看出同一渠道在不同模型下的价值差异。关键洞察: 对某个渠道,如果 `first_click` 远大于 `last_click`,说明它是"开路先锋"(早期拉新),用末次点击会严重低估它的价值 —— CMO 不该因为它末次点击数字难看就砍预算。这条结果是"归因模型对比"仪表盘的底座。

### 7.2 转化路径长度分析

**业务背景:** Marketing Analytics 想回答"用户平均要被触达几次才会转化"。路径长度直接影响营销策略: 如果大多数转化只需 1–2 个触点,说明决策链短、可以激进收割;如果普遍要 4–6 个触点,说明要靠多轮培育,不能只看末次点击。

**类别 / 难度 / 角色:** 子查询 + 窗口函数 | Intermediate | Marketing Analytics / RevOps

**解题思路:** 两层结构。内层子查询先按 `conversion_id` 分组,用 `MAX(touchpoint_order)` 算出每笔转化的路径长度(因为 touchpoint_order 从 1 连续编号,最大值就是触点总数)。外层再按路径长度分组,数有多少笔转化是这个长度。亮点是 `SUM(COUNT(*)) OVER ()` 这个 **窗口函数**: 它在不破坏分组的情况下算出"所有转化的总数"作为分母,从而得到每个路径长度的占比 —— 比再写一个子查询取总数更简洁。

```sql
-- 自然语言: "用户平均需要多少次触点才会转化？"
SELECT
    path_length,
    COUNT(*) AS conversion_count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 2) AS percentage
FROM (
    SELECT
        conversion_id,
        MAX(touchpoint_order) AS path_length
    FROM attribution_path
    GROUP BY conversion_id
) path_lengths
GROUP BY path_length
ORDER BY path_length;
```

**期望结果 + 业务结论:** 返回路径长度 2–6 的分布(平均 ~4 个触点),每个长度带转化数和占比。如果分布集中在 4–6,说明 Lumenly 的客户多为"需要多轮培育"的品类,Marketing Analytics 应建议 CMO 在评估渠道时务必用多触点模型而非末次点击,否则会系统性低估上游渠道。

### 7.3 首次触点 vs 末次触点渠道分析

**业务背景:** 承接 7.1 的洞察,Marketing Analytics 要做一张更聚焦的对比: 每个渠道作为"首次触点"出现的次数 vs 作为"末次触点"出现的次数。一个渠道如果首触多、末触少,它就是典型的"拉新渠道";反之是"收割渠道"。这张图能直接指导预算在"拉新"和"收割"之间的分配。

**类别 / 难度 / 角色:** 多 CTE + LEFT JOIN | Advanced | Marketing Analytics / RevOps

**解题思路:** 这是本文档最考验 CTE 组织能力的查询。两个 CTE: `first_touch` 取每笔转化 `touchpoint_order = 1` 的触点;`last_touch` 取每笔转化触点序号最大的那个(需先用子查询求出每个 conversion 的 `MAX(touchpoint_order)`,再 JOIN 回去定位末次触点行)。最后以 `channel` 为主表 **LEFT JOIN** 两个 CTE —— 用 LEFT JOIN 是为了保证每个渠道都出现(哪怕它从没当过首触或末触),否则该渠道会从对比里凭空消失。两个占比的分母用标量子查询取各自的转化总数。

```sql
-- 自然语言: "首次触点和末次触点的渠道分布有何差异？"
WITH first_touch AS (
    SELECT
        conversion_id,
        channel_id
    FROM attribution_path
    WHERE touchpoint_order = 1
),
last_touch AS (
    SELECT
        ap.conversion_id,
        ap.channel_id
    FROM attribution_path ap
    INNER JOIN (
        SELECT conversion_id, MAX(touchpoint_order) AS max_order
        FROM attribution_path
        GROUP BY conversion_id
    ) max_touch ON ap.conversion_id = max_touch.conversion_id
        AND ap.touchpoint_order = max_touch.max_order
)
SELECT
    ch.name AS channel,
    COUNT(DISTINCT ft.conversion_id) AS first_touch_count,
    COUNT(DISTINCT lt.conversion_id) AS last_touch_count,
    ROUND(COUNT(DISTINCT ft.conversion_id) * 100.0 /
        (SELECT COUNT(DISTINCT conversion_id) FROM first_touch), 2) AS first_touch_pct,
    ROUND(COUNT(DISTINCT lt.conversion_id) * 100.0 /
        (SELECT COUNT(DISTINCT conversion_id) FROM last_touch), 2) AS last_touch_pct
FROM channel ch
LEFT JOIN first_touch ft ON ch.id = ft.channel_id
LEFT JOIN last_touch lt ON ch.id = lt.channel_id
GROUP BY ch.id, ch.name
ORDER BY first_touch_count DESC;
```

**期望结果 + 业务结论:** 返回 6 行渠道,每行带首触次数/占比、末触次数/占比。对比两个占比列: 首触占比 > 末触占比的渠道(可能是 Display / Social)是拉新主力;反之(可能是 Paid Search / Direct)是收割主力。Marketing Analytics 据此建议: 别用末次点击 KPI 去考核拉新渠道,否则会把最该投的上游渠道砍掉。

### 7.4 转化前的平均时间

**业务背景:** Marketing Analytics 想量化"销售周期长短": 用户从第一次接触到最终转化,平均隔多久?不同首触渠道带来的用户,决策速度可能差很多 —— 搜索来的用户可能当天就转化,展示触达的用户可能要酝酿两周。这影响归因回溯窗口 (lookback window) 的设置和再营销节奏。

**类别 / 难度 / 角色:** 聚合 + 过滤 | Intermediate | Marketing Analytics / RevOps

**解题思路:** `attribution_path` JOIN `channel`,只看 `touchpoint_order = 1` 的首次触点(因为我们要量的是"从首次接触算起"的时长)。`hours_before_conv` 字段记录了该触点发生在转化前多少小时,直接对它取 `AVG`。按首触渠道分组,就能比较不同渠道的平均决策时长。这是一条"过滤到特定触点 + 聚合"的查询。

```sql
-- 自然语言: "用户从首次接触到转化平均需要多长时间？"
SELECT
    ch.name AS first_touch_channel,
    ROUND(AVG(ap.hours_before_conv), 1) AS avg_hours_to_conversion,
    ROUND(AVG(ap.days_before_conv), 1) AS avg_days_to_conversion,
    COUNT(DISTINCT ap.conversion_id) AS conversion_count
FROM attribution_path ap
JOIN channel ch ON ap.channel_id = ch.id
WHERE ap.touchpoint_order = 1
GROUP BY ch.id, ch.name
ORDER BY avg_hours_to_conversion DESC;
```

**期望结果 + 业务结论:** 返回 6 行渠道,带平均转化时长(小时/天)和转化数。决策时长最长的渠道,需要更长的 lookback window 才能正确归因,否则它带来的转化会因为超出回溯窗口而被漏算。Marketing Analytics 据此为不同渠道/floodlight tag 设置合理的回溯窗口。

---

## 8. 预算分析

### 8.1 预算使用情况

**业务背景:** Media Planner 要回答"客户的预算到底用得满不满"。预算使用率 = 实际日均花费 ÷ 当日生效预算。使用率长期低于 60% 说明预算给多了(可下调释放),接近或超过 100% 说明预算卡住了花费(可上调放量)。这是 Q1 预算优化的量化基础。

**类别 / 难度 / 角色:** CTE + SCD2 Join | Advanced | Media Planner

**解题思路:** 难点在 `campaign_budget` 是 **历史化表 (SCD2)**: 一个 campaign 有多条带生效区间的预算记录。**绝不能直接 JOIN,否则一个 campaign 会被它的多条历史预算一对多扇出,花费被重复计算放大数倍。** 正确做法是只取"参考日当天生效"的那一条,用区间匹配 `effective_date_start <= '2026-06-01' AND (effective_date_end IS NULL OR effective_date_end > '2026-06-01')`。CTE 里先把当日预算和近 7 天日均花费 (`SUM(cost)/COUNT(DISTINCT report_date)`) 算出来,外层再相除得使用率。

```sql
-- 自然语言: "各广告系列的预算使用率是多少？"
WITH budget_usage AS (
    SELECT
        c.id AS campaign_id,
        c.campaign_name,
        a.company_name,
        cb.daily_budget,
        ROUND(SUM(ds.cost) / COUNT(DISTINCT ds.report_date), 2) AS avg_daily_spend
    FROM campaign c
    JOIN advertiser a ON c.advertiser_id = a.id
    -- 取参考日当天生效的那一条预算 (历史化区间匹配), 避免一对多扇出
    JOIN campaign_budget cb ON c.id = cb.campaign_id
        AND cb.effective_date_start <= DATE('2026-06-01')
        AND (cb.effective_date_end IS NULL OR cb.effective_date_end > DATE('2026-06-01'))
    JOIN daily_stats ds ON c.id = ds.entity_id AND ds.entity_type = 'Campaign'
    WHERE ds.report_date >= DATE('2026-06-01', '-7 days')
    GROUP BY c.id, c.campaign_name, a.company_name, cb.daily_budget
)
SELECT
    campaign_name,
    company_name,
    daily_budget,
    avg_daily_spend,
    ROUND(avg_daily_spend / daily_budget * 100, 1) AS budget_usage_pct
FROM budget_usage
ORDER BY budget_usage_pct DESC
LIMIT 20;
```

**期望结果 + 业务结论:** 返回使用率最高的 20 个 campaign。由于数据里预算被锚定到实际花费,普通 campaign 使用率落在 55%–95%,预算受限 campaign 会 >100%。使用率 >100% 的就是被预算卡住的 campaign,Media Planner 应优先为它们加预算(并和 4.1 的高 `lost_is_budget` 名单交叉验证);使用率特别低的可以回收部分预算调配给前者。

### 8.2 预算不足的广告系列

**业务背景:** 8.1 看的是使用率,这条更直接 —— 用"因预算损失的展示份额 (`lost_is_budget`)"这个引擎自己给出的信号来锁定预算不足的 campaign,并且只看 Enabled 的(暂停的没意义)。两个信号(使用率 >100% 和 lost_is_budget 高)互相印证,才是稳健的加预算依据。对应 Q1。

**类别 / 难度 / 角色:** SCD2 Join + HAVING | Advanced | Media Planner

**解题思路:** 和 8.1 一样用 SCD2 区间匹配取当日预算,但这次直接在 GROUP BY 后用 `HAVING AVG(ds.lost_is_budget) > 20` 锁定"平均预算损失超 20%"的 campaign。额外加 `c.status = 'Enabled'` 过滤掉非活跃 campaign。同时输出 `avg_daily_spend`,方便估算加预算的量级。这条把"竞争信号 (lost_is_budget)"和"预算/花费"放在一起,是预算缺口分析的标准形态。

```sql
-- 自然语言: "哪些广告系列预算可能不足？"
SELECT
    c.campaign_name,
    a.company_name,
    cb.daily_budget,
    ROUND(AVG(ds.lost_is_budget), 1) AS avg_lost_is_budget,
    ROUND(SUM(ds.cost) / COUNT(DISTINCT ds.report_date), 2) AS avg_daily_spend
FROM campaign c
JOIN advertiser a ON c.advertiser_id = a.id
-- 取参考日当天生效的那一条预算 (历史化区间匹配), 避免一对多扇出
JOIN campaign_budget cb ON c.id = cb.campaign_id
    AND cb.effective_date_start <= DATE('2026-06-01')
    AND (cb.effective_date_end IS NULL OR cb.effective_date_end > DATE('2026-06-01'))
JOIN daily_stats ds ON c.id = ds.entity_id AND ds.entity_type = 'Campaign'
WHERE ds.report_date >= DATE('2026-06-01', '-7 days')
    AND c.status = 'Enabled'
GROUP BY c.id, c.campaign_name, a.company_name, cb.daily_budget
HAVING AVG(ds.lost_is_budget) > 20
ORDER BY avg_lost_is_budget DESC
LIMIT 20;
```

**期望结果 + 业务结论:** 返回预算损失最严重的 20 个活跃 campaign,带当日预算、平均预算损失、日均花费。这是一份可直接执行的加预算工单: 对每个 campaign,加预算的量级可参考 `avg_daily_spend / (1 - lost_is_budget%)` 粗估。生产环境里这份清单由 Daily Health Check Agent 自动生成并推送给负责人。

---

## 9. 综合诊断查询

### 9.1 广告主健康度检查

**业务背景:** Account Manager / CSM 要为季度业务回顾 (QBR) 准备一张"客户健康度一览表",一眼看出每个大客户是健康、一般还是需要关注。健康度差的客户续约风险高,需要提前介入。这是把效果指标 (ROAS) 和竞争指标 (lost_is_budget) 合成一个业务判断的综合查询,对应业务问题 Q6。

**类别 / 难度 / 角色:** CTE + CASE | Advanced | CSM / Account Manager

**解题思路:** CTE `advertiser_metrics` 把广告主的多维指标一次性算齐: campaign 数、总花费、转化、CPA、ROAS、平均展示份额、平均预算损失(JOIN 链 advertiser → campaign → daily_stats,只看 Active 广告主)。外层用 **CASE 表达式** 把这些数字翻译成业务标签: ROAS≥4 且预算损失<10% → Healthy;ROAS≥2 且损失<30% → Moderate;否则 Needs Attention。CASE 是把"分析师的判断规则"固化进 SQL 的标准手段。

```sql
-- 自然语言: "给我一个广告主的全面健康度报告"
WITH advertiser_metrics AS (
    SELECT
        a.id AS advertiser_id,
        a.company_name,
        i.name AS industry,
        COUNT(DISTINCT c.id) AS campaign_count,
        ROUND(SUM(ds.cost), 2) AS total_cost,
        ROUND(SUM(ds.conversions), 2) AS total_conversions,
        ROUND(SUM(ds.conversion_value), 2) AS total_value,
        ROUND(SUM(ds.cost) / NULLIF(SUM(ds.conversions), 0), 2) AS cpa,
        ROUND(SUM(ds.conversion_value) / NULLIF(SUM(ds.cost), 0), 2) AS roas,
        ROUND(AVG(ds.impression_share), 1) AS avg_impr_share,
        ROUND(AVG(ds.lost_is_budget), 1) AS avg_lost_budget
    FROM advertiser a
    JOIN industry i ON a.industry_id = i.id
    JOIN campaign c ON a.id = c.advertiser_id
    JOIN daily_stats ds ON c.id = ds.entity_id AND ds.entity_type = 'Campaign'
    WHERE ds.report_date >= DATE('2026-06-01', '-7 days')
        AND a.account_status = 'Active'
    GROUP BY a.id, a.company_name, i.name
)
SELECT
    company_name,
    industry,
    campaign_count,
    total_cost,
    total_conversions,
    cpa,
    roas,
    avg_impr_share,
    avg_lost_budget,
    CASE
        WHEN roas >= 4 AND avg_lost_budget < 10 THEN 'Healthy'
        WHEN roas >= 2 AND avg_lost_budget < 30 THEN 'Moderate'
        ELSE 'Needs Attention'
    END AS health_status
FROM advertiser_metrics
ORDER BY total_cost DESC
LIMIT 20;
```

**期望结果 + 业务结论:** 返回花费最高的 20 个活跃广告主,每行带一个 health_status 标签。重点盯"花费大但 Needs Attention"的客户 —— 它们既是营收主力,又面临效果风险,是最高优先级的客户成功干预对象。Account Manager 据此安排 QBR 议程和续约保卫战。

### 9.2 优化机会识别

**业务背景:** Campaign Manager 要一份"每日待办": 在花了真金白银的活跃 campaign 里,系统自动给出每个该做什么动作(加预算、提质量、查定向、优化 CPA)。这把分散在前面几节的诊断逻辑(预算损失、排名损失、零转化、高 CPA)合并成一个一站式的行动清单,横跨 Q1 和 Q3。

**类别 / 难度 / 角色:** 聚合 + CASE | Intermediate | Campaign Manager

**解题思路:** 对活跃 campaign 聚合花费、转化、CPA、预算损失、排名损失,用一个 **多分支 CASE** 把诊断规则编码成建议: 预算损失>20% → 加预算;排名损失>30% → 提出价/质量;零转化但花费>100 → 查定向;CPA>200 → 优化 CPA;否则 → 监控。CASE 的分支是 **按顺序短路** 的,所以最严重/最优先的条件要放前面。用 `HAVING cost > 100` 过滤掉花费太小、不值得动作的 campaign。

```sql
-- 自然语言: "识别需要优化的广告系列"
SELECT
    c.campaign_name,
    a.company_name,
    c.status,
    ROUND(SUM(ds.cost), 2) AS cost,
    ROUND(SUM(ds.conversions), 2) AS conversions,
    ROUND(SUM(ds.cost) / NULLIF(SUM(ds.conversions), 0), 2) AS cpa,
    ROUND(AVG(ds.lost_is_budget), 1) AS lost_budget,
    ROUND(AVG(ds.lost_is_rank), 1) AS lost_rank,
    CASE
        WHEN AVG(ds.lost_is_budget) > 20 THEN 'Increase Budget'
        WHEN AVG(ds.lost_is_rank) > 30 THEN 'Improve Bids/Quality'
        WHEN SUM(ds.conversions) = 0 AND SUM(ds.cost) > 100 THEN 'Review Targeting'
        WHEN SUM(ds.cost) / NULLIF(SUM(ds.conversions), 0) > 200 THEN 'Optimize CPA'
        ELSE 'Monitor'
    END AS recommendation
FROM campaign c
JOIN advertiser a ON c.advertiser_id = a.id
JOIN daily_stats ds ON c.id = ds.entity_id AND ds.entity_type = 'Campaign'
WHERE ds.report_date >= DATE('2026-06-01', '-7 days')
    AND c.status = 'Enabled'
GROUP BY c.id, c.campaign_name, a.company_name, c.status
HAVING cost > 100
ORDER BY cost DESC
LIMIT 30;
```

**期望结果 + 业务结论:** 返回 30 个花费靠前的活跃 campaign,每个带一条明确的 recommendation。Campaign Manager 可以直接按建议分类批量处理: 所有 'Increase Budget' 的走加预算流程,所有 'Review Targeting' 的逐个查定向。这条查询是把人类经验规则交给 Agent 自动化执行的最佳范例 —— CASE 里的阈值就是 Agent 的决策逻辑。

---

## 10. Agent 场景查询

### 10.1 诊断CPA上涨原因

**业务背景:** 这是 Text-to-SQL Agent 最典型的任务: 客户/Performance Manager 抛来一句模糊的"为什么我的转化成本上周涨了这么多?",Agent 要把它拆成一套可执行的诊断步骤。CPA 上涨永远是三个原因之一: CPC 涨了(变贵)、CTR 跌了(点击少)、或转化率跌了(点了不转)。这条多步查询演示了根因分析 (root-cause analysis) 的标准套路。

**类别 / 难度 / 角色:** 多步 + 条件透视 | Advanced | Performance Marketing Manager

**解题思路:** 三步走,层层下钻。第一步用 CTE + CASE 把最近 14 天切成"本周/上周"两段,确认 CPA 确实涨了、涨了多少。第二步把 CPC / CTR / 转化率 也按周拆开,定位是哪个分量在恶化(`CASE WHEN report_date >= ... THEN 'This Week' ELSE 'Last Week'` 是 SQLite 里做"条件透视"的常用手法)。第三步用 `SUM(CASE WHEN ... THEN cost ELSE 0 END)` 这种 **条件聚合** 把本周/上周 CPA 压到同一行,算出每个 campaign 的环比,用 `HAVING this_week_cpa > last_week_cpa * 1.2` 锁定涨幅超 20% 的元凶 campaign。

```sql
-- 自然语言: "为什么我的转化成本上周涨了这么多？"
-- 第一步: 确认CPA变化
WITH weekly_cpa AS (
    SELECT
        CASE
            WHEN ds.report_date >= DATE('2026-06-01', '-7 days') THEN 'This Week'
            ELSE 'Last Week'
        END AS period,
        SUM(ds.cost) AS cost,
        SUM(ds.conversions) AS conversions,
        SUM(ds.cost) / NULLIF(SUM(ds.conversions), 0) AS cpa
    FROM daily_stats ds
    WHERE ds.entity_type = 'Campaign'
        AND ds.report_date >= DATE('2026-06-01', '-14 days')
    GROUP BY period
)
SELECT
    period,
    ROUND(cost, 2) AS cost,
    ROUND(conversions, 2) AS conversions,
    ROUND(cpa, 2) AS cpa
FROM weekly_cpa
ORDER BY period DESC;

-- 第二步: 分析CPC变化
SELECT
    CASE
        WHEN ds.report_date >= DATE('2026-06-01', '-7 days') THEN 'This Week'
        ELSE 'Last Week'
    END AS period,
    ROUND(SUM(ds.cost) / NULLIF(SUM(ds.clicks), 0), 2) AS avg_cpc,
    ROUND(SUM(ds.clicks) / NULLIF(SUM(ds.impressions), 0) * 100, 2) AS ctr_pct,
    ROUND(SUM(ds.conversions) / NULLIF(SUM(ds.clicks), 0) * 100, 2) AS conv_rate_pct
FROM daily_stats ds
WHERE ds.entity_type = 'Campaign'
    AND ds.report_date >= DATE('2026-06-01', '-14 days')
GROUP BY period
ORDER BY period DESC;

-- 第三步: 识别CPA上涨最多的广告系列
SELECT
    c.campaign_name,
    ROUND(SUM(CASE WHEN ds.report_date >= DATE('2026-06-01', '-7 days') THEN ds.cost ELSE 0 END) /
        NULLIF(SUM(CASE WHEN ds.report_date >= DATE('2026-06-01', '-7 days') THEN ds.conversions ELSE 0 END), 0), 2) AS this_week_cpa,
    ROUND(SUM(CASE WHEN ds.report_date < DATE('2026-06-01', '-7 days') THEN ds.cost ELSE 0 END) /
        NULLIF(SUM(CASE WHEN ds.report_date < DATE('2026-06-01', '-7 days') THEN ds.conversions ELSE 0 END), 0), 2) AS last_week_cpa
FROM daily_stats ds
JOIN campaign c ON ds.entity_id = c.id AND ds.entity_type = 'Campaign'
WHERE ds.report_date >= DATE('2026-06-01', '-14 days')
GROUP BY c.id, c.campaign_name
HAVING this_week_cpa > last_week_cpa * 1.2
ORDER BY (this_week_cpa - last_week_cpa) DESC
LIMIT 10;
```

**期望结果 + 业务结论:** 第一步输出两行(本周/上周 CPA)确认变化方向;第二步输出两行定位是 CPC/CTR/转化率哪个分量恶化;第三步输出最多 10 个环比涨幅超 20% 的元凶 campaign。三步连起来就是一份完整的根因报告。Performance Manager 拿到第三步的 campaign 名单后,直接钻到 5.2(关键词质量)或 4.1(预算)做针对性修复。这正是 Agent 自动化诊断要复刻的推理链。

### 10.2 归因模型对比分析

**业务背景:** 这是 7.1 的"决策增强版",直接服务于一个具体决策: 哪些渠道被末次点击模型系统性低估了?Marketing Analytics 不只想看六个模型的数字,还想要一个直接量化"首次 vs 末次差异"的指标,好一眼挑出"被低估的拉新渠道"递给 CMO。

**类别 / 难度 / 角色:** 多 Join + 派生 | Advanced | Marketing Analytics / RevOps

**解题思路:** 在 7.1 的基础上,只保留 last/first/linear/data_driven 四个关键模型,并新增一个 **派生比较列** `first_vs_last_diff_pct = (first_click_value - last_click_value)/last_click_value * 100`。这个百分比正值越大,说明该渠道在首次点击下的价值远超末次点击 —— 即它是被末次点击严重低估的上游渠道。JOIN 结构和 7.1 相同 (attribution_path → conversion → channel)。

```sql
-- 自然语言: "帮我分析一下不同归因模型下的渠道价值"
SELECT
    ch.name AS channel,
    ROUND(SUM(ap.last_click_credit * c.conversion_value), 2) AS last_click_value,
    ROUND(SUM(ap.first_click_credit * c.conversion_value), 2) AS first_click_value,
    ROUND(SUM(ap.linear_credit * c.conversion_value), 2) AS linear_value,
    ROUND(SUM(ap.data_driven_credit * c.conversion_value), 2) AS data_driven_value,
    ROUND((SUM(ap.first_click_credit * c.conversion_value) -
           SUM(ap.last_click_credit * c.conversion_value)) /
        NULLIF(SUM(ap.last_click_credit * c.conversion_value), 0) * 100, 1) AS first_vs_last_diff_pct
FROM attribution_path ap
JOIN conversion c ON ap.conversion_id = c.id
JOIN channel ch ON ap.channel_id = ch.id
GROUP BY ch.id, ch.name
ORDER BY data_driven_value DESC;

-- 洞察: 如果首次点击价值远高于末次点击，说明该渠道在用户决策早期发挥重要作用
```

**期望结果 + 业务结论:** 返回 6 行渠道,带四个模型的价值和一个 `first_vs_last_diff_pct` 比较列。`first_vs_last_diff_pct` 为高正值的渠道,就是被末次点击低估的拉新渠道 —— Marketing Analytics 应在 CMO 的预算评审上专门为它们正名,避免它们因末次点击数字难看而被砍预算。这是把分析直接转化为预算决策的收口查询。

---

## 11. 业务问题 → 查询映射

下表把 28 条查询回扣到业务背景文档里的 6 个业务问题,确保每条查询都有据可依。

| 业务问题 | 对应查询 |
|----------|----------|
| **Q1 预算缺口识别** | 2.1, 4.1, 8.1, 8.2, 9.2 |
| **Q2 出价策略效果** | 3.1, 3.2, 3.3, 10.1 |
| **Q3 关键词质量诊断** | 5.1, 5.2, 5.3, 9.2 |
| **Q4 搜索词挖掘** | 6.1, 6.2, 6.3 |
| **Q5 多归因模型转化分析** | 7.1, 7.2, 7.3, 7.4, 10.2 |
| **Q6 账户与客户组合健康** | 1.2, 2.3, 9.1 |
| **运营 / 索引类 (支撑性)** | 1.1, 1.3, 2.2, 2.4, 4.2 |

---

## 12. 使用说明

### 12.1 数据库连接

```python
import sqlite3
import pandas as pd

# 连接数据库
conn = sqlite3.connect('search_ads_360_agent_large.sqlite')

# 执行查询
df = pd.read_sql_query("SELECT * FROM advertiser LIMIT 10", conn)
print(df)

conn.close()
```

### 12.2 Text-to-SQL 示例

用户输入: "上周花费最多的广告系列是什么？"

Agent 生成的 SQL:
```sql
SELECT
    c.campaign_name,
    a.company_name,
    ROUND(SUM(ds.cost), 2) AS total_cost
FROM daily_stats ds
JOIN campaign c ON ds.entity_id = c.id AND ds.entity_type = 'Campaign'
JOIN advertiser a ON c.advertiser_id = a.id
WHERE ds.report_date >= DATE('2026-06-01', '-7 days')
GROUP BY c.id, c.campaign_name, a.company_name
ORDER BY total_cost DESC
LIMIT 5;
```

---

## 13. 注意事项

1. **固定参考日 (重要)**: 本数据集是**冻结快照**, 数据末日 = `2026-06-01` (daily_stats / search_term_report / conversion 的最大日期均为此日)。所有时间过滤**必须以 `DATE('2026-06-01', ...)` 为基准**, **不要用 `DATE('now', ...)`** —— 真实当前日期已晚于数据末日, 用 `'now'` 会让时间窗整体落在数据之后, 返回空结果。
2. **NULL 处理**: 使用 `NULLIF()` 避免除零错误
3. **性能优化**: 对于大数据量查询，建议添加适当的 WHERE 条件限制时间范围
4. **实体类型**: `daily_stats` 表使用 `entity_type` 字段区分不同层级的数据, JOIN 时必须显式带 `entity_type='Campaign'`
5. **预算历史化**: `campaign_budget` 是 SCD2, JOIN 时需用 `effective_date_start <= 基准日 AND (effective_date_end IS NULL OR effective_date_end > 基准日)` 区间匹配, 否则会一对多扇出
6. **搜索词优化标记**: `search_term_report.added_excluded` 取值 `'None'` (未处理) / `'Added'` / `'Excluded'`, "未处理"是字面量字符串 `'None'` 而非 SQL NULL
