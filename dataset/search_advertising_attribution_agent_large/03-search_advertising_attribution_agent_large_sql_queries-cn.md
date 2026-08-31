# 搜索广告归因分析 Agent 数据集: SQL 查询参考

## 概览

本文档为 `search_advertising_attribution_agent_large` 数据集提供
**20 个面向业务的 SQL 查询**。配套的业务背景、行业科普和术语表见
`01-search_advertising_attribution_agent_large_business_context-cn.md`，
表结构和数据生成规则见 `02-search_advertising_attribution_agent_large_er_document-cn.md`。

## 如何使用本文档

本文档写给一个具体的读者：刚读完业务背景文档和 ER 文档、即将被经理派去
做这些查询的实习分析师。照着读，你能学到一个真实分析师是怎么从业务问题
一步步走到 SQL、再走到决策的，而不只是抄一段能跑的代码。

每个查询都按统一的五段式组织：

- **业务背景**：谁在问、为什么现在问、答案会驱动什么决策。
- **类别 / 难度 / 业务角色**：这道题练的 SQL 技巧、难度，以及最可能提出它的角色。
- **解题思路**：在看 SQL 之前，先想清楚要碰哪些表、怎么 join、聚合到什么粒度、为什么用 CTE 或窗口函数、有没有 SQLite 特有的坑。这一段是把题读懂的关键。
- **SQL**：可以直接在生成的 SQLite 库上运行的查询。
- **预期结果描述**：结果长什么样、关键数字对应哪个业务陷阱、分析师下一步该做什么。

两个全局提醒。第一，所有时间窗口都锚定在 `v_reference_date` 视图（它取
`MAX(daily_stats.report_date)`），查询里用字面量回溯而不是 `DATE('now')`，
这样无论数据集多久前生成，结果都可复现。第二，每个查询都能追溯到业务背景
文档里列出的某个业务问题（归因真相、预算效率、跨引擎效率、浪费治理、代理
与组合结构）。SQL 是用来读和学的，不只是拿来跑的。

## 全局约定

下列约定在所有查询中一致使用；写在这里一次，单个查询内不再重复解释。

1. **参考日期 / "近期"窗口。** 所有时间窗口过滤都锚定在
   `v_reference_date` 视图，它暴露 `MAX(daily_stats.report_date)`
   （见 ER 文档 §5.2）。查询不直接用 `DATE('now')`。项目标准"近期"窗口为：
   - `"最近 7 天"` ⇒ `report_date >= DATE((SELECT reference_date FROM v_reference_date), '-7 days')`
   - `"最近 14 天"` ⇒ `… '-14 days'`
   - `"最近 30 天"` ⇒ `… '-30 days'`
2. **"活跃"实体。** campaign / ad / keyword "活跃" = `status = 'Enabled'`；
   advertiser "活跃" = `account_status = 'Active'`；agency_client 关系
   "活跃" = `is_active = 1`。**对于"活跃"广告主的 keyword / ad_group 聚合
   查询，还会过滤父 campaign 和 ad_group 为 `status = 'Enabled'`**，
   这样暂停或已删除的父级不会贡献到聚合。
3. **CPA / ROAS。** `CPA = SUM(cost) / NULLIF(SUM(conversions), 0)`；
   `ROAS = SUM(conversion_value) / NULLIF(SUM(cost), 0)`。
4. **`campaign_budget` 在效解析。** 要找日期 D 当时生效的预算，取
   `effective_date ≤ report_date` 中最新的那一行。`campaign_budget` join
   到 `daily_stats` 的查询**必须**用这个模式（关联子查询见 Query 4
   和 15），避免一个 campaign 有多版预算时双重计数。
5. **三种"conversion"数据来源。** 本数据集里 "conversion" 一词出现在 3
   个地方，3 种粒度、3 种量级。它们**不可直接对比**；单个查询里挑一种
   坚持用。
   - **`daily_stats.conversions`** —— 引擎上报的日聚合（按
     campaign × 日 × device 粒度）。90 天总量级在百万级。被
     Query **1, 2, 3, 5, 6, 7, 9, 17, 19** 使用。
   - **`conversion` 表（5,000 行）** —— Floodlight 事件日志：一行一个
     真实事件，带显式 `conversion_value` 和时间戳。被 Query **12, 13,
     14, 18** 使用（路径长度、归因信用、转化时延）。
   - **`search_term_report.conversions`** —— 引擎上报的日聚合（按
     搜索词 × 日 粒度）—— 与 `daily_stats` 同口径，但粒度更细。
     Query **10** 用它做否定关键词候选。
   - Query **4, 8, 11, 15, 16, 20** 不聚合任何 conversion 列。
6. **非 Search campaign 的 `search_*_is`。** `search_impr_share`、
   `search_top_is`、`search_abs_top_is` 在 `daily_stats` 的 Display /
   Video / Performance Max / Shopping 行上是 NULL。Query 16 过滤
   `campaign_type = 'Search'`；聚合 `impression_share` 的查询则包括所有
   campaign 类型。

## 查询索引

| # | 标题 | 业务角色 | 类别 | 难度 |
|---|---|---|---|---|
| 1 | 30 天花费 Top 广告主 | 高管 | Join + 聚合 | Basic |
| 2 | 行业组合概览 | 高管 | Join + 聚合 | Basic |
| 3 | 日环比花费趋势 | 经理 | 窗口函数 | Intermediate |
| 4 | Campaign 花费 vs 预算（fan-out 安全） | 经理 | CTE + 子查询 | Advanced |
| 5 | 超出 Target CPA 目标的 campaign | 分析师 | CTE + Join | Intermediate |
| 6 | 设备级 CTR 和 CPA | 分析师 | 聚合 + Join | Basic |
| 7 | 引擎表现对比 | 分析师 | 聚合 + Join | Basic |
| 8 | 按行业的 Quality Score 分布 | 分析师 | 聚合 + Join | Intermediate |
| 9 | 高花费 campaign 中的低 QS 关键词 | 分析师 | 跨层 Join | Advanced |
| 10 | 高成本零转化搜索词 | 运营 | LEFT JOIN + 聚合 | Basic |
| 11 | 广泛匹配溢出占比 | 分析师 | NULL 处理 + 聚合 | Intermediate |
| 12 | 首触 vs 末触渠道组合 | 分析师 | CTE + 聚合 | Advanced |
| 13 | 转化路径长度分布 | 分析师 | 子查询 + 聚合 | Intermediate |
| 14 | 各归因模型下的渠道价值 | 高管 | 聚合 + Join | Intermediate |
| 15 | 受预算约束的 campaign | 经理 | CTE + 子查询 | Advanced |
| 16 | 占据首页位置的 campaign（仅 Search、按展示加权） | 经理 | 加权聚合 | Intermediate |
| 17 | 按代理等级的代理组合表现 | 高管 | Join + 聚合 | Intermediate |
| 18 | 按首触渠道的转化时延 | 分析师 | CTE + Join | Intermediate |
| 19 | 周环比 CPA 诊断 | 经理 | CTE + CASE + 日期算术 | Advanced |
| 20 | 搜索词报表中的关键词覆盖率 | 运营 | LEFT JOIN + 聚合 | Basic |

---

## 查询

### Query 1: 30 天花费 Top 广告主

**业务背景：**
高管在准备每周干系人评审，想要拿到大致数字：过去 30 天花费最多的
广告主是谁、所在行业、花费的转化效率如何？这是几乎所有业务评审的
第一张幻灯片，用来在客户之间分配关注度。

**类别：** Join + 聚合
**难度：** Basic
**业务角色：** 高管

**解题思路：**
从 `advertiser` 出发，join `industry` 拿行业名，再 join `campaign` 和
`daily_stats` 把花费摊到广告主。一个广告主有多个 campaign、每个 campaign
又有多日多设备的 `daily_stats`，所以 join 之后行数会扇出；用
`GROUP BY a.id` 把它们重新收拢回广告主粒度，再 SUM 聚合花费和转化。
CPA / ROAS 必须先 SUM 分子和分母再相除（配 `NULLIF` 防除零），绝不能
先算每行的 cpa 再求平均，那是错误的加权。时间窗口用 `v_reference_date`
回溯 30 天。一次 GROUP BY 加 ORDER BY 加 LIMIT 10 就够了。对应业务问题：
组合结构概览。

```sql
-- 过去 30 天花费 Top 10 广告主，附带 CPA 和 ROAS。
SELECT
    a.company_name,
    i.name AS industry,
    ROUND(SUM(ds.cost), 2)                                          AS total_spend,
    ROUND(SUM(ds.conversions), 2)                                   AS total_conversions,
    ROUND(SUM(ds.cost) / NULLIF(SUM(ds.conversions), 0), 2)         AS cpa,
    ROUND(SUM(ds.conversion_value) / NULLIF(SUM(ds.cost), 0), 2)    AS roas
FROM advertiser a
JOIN industry i  ON i.id = a.industry_id
JOIN campaign  c ON c.advertiser_id = a.id
JOIN daily_stats ds ON ds.campaign_id = c.id
WHERE ds.report_date >= DATE((SELECT reference_date FROM v_reference_date), '-30 days')
GROUP BY a.id, a.company_name, i.name
ORDER BY total_spend DESC
LIMIT 10;
```

**预期结果描述：**
10 行，每广告主一行，按花费排序。花费范围从顶部的几十万美元到第 10
名的五万左右。CPA / ROAS 应当合理（CPA $50–$300，ROAS 1.0–8.0）且在
行业间有差异。

---

### Query 2: 行业组合概览

**业务背景：**
代理公司 CMO 想要一页纸的行业分布：我们在哪些 IAB 垂直行业上花费最多、
每个垂直行业有多少活跃广告主和 campaign、哪些垂直 ROAS 最强？这驱动
人才分配和哪些行业值得做案例研究营销投入。

**类别：** Join + 聚合
**难度：** Basic
**业务角色：** 高管

**解题思路：**
和 Query 1 同一条链，但聚合粒度上移到行业。从 `industry` join 到
`advertiser`、`campaign`、`daily_stats`。这里有个必须小心的坑：因为
`daily_stats` 的扇出，同一个广告主或 campaign 会在 join 结果里出现很多次，
所以 `advertiser_count` 和 `campaign_count` 一定要用 `COUNT(DISTINCT ...)`，
否则会被严重高估。聚合到行业粒度后，留意 CPA 主要由竞争（CPC 和转化率）
驱动、ROAS 主要由行业客单价驱动，两者排序不一致，这正是一个有用的教学
对照。对应业务问题：组合结构。

```sql
SELECT
    i.name                                                       AS industry,
    COUNT(DISTINCT a.id)                                         AS advertiser_count,
    COUNT(DISTINCT c.id)                                         AS campaign_count,
    ROUND(SUM(ds.cost), 2)                                       AS total_spend,
    ROUND(SUM(ds.conversions), 2)                                AS total_conversions,
    ROUND(SUM(ds.cost) / NULLIF(SUM(ds.conversions), 0), 2)      AS cpa,
    ROUND(SUM(ds.conversion_value) / NULLIF(SUM(ds.cost), 0), 2) AS roas
FROM industry i
JOIN advertiser a   ON a.industry_id = i.id
JOIN campaign  c    ON c.advertiser_id = a.id
JOIN daily_stats ds ON ds.campaign_id = c.id
WHERE ds.report_date >= DATE((SELECT reference_date FROM v_reference_date), '-30 days')
GROUP BY i.id, i.name
ORDER BY total_spend DESC;
```

**预期结果描述：**
10 行 —— 每 IAB 行业一行。`advertiser_count` 和 `campaign_count` 只计入
窗口内有投放的实体。转化价值按行业范围采样，所以地产 / 金融 / 保险 /
汽车呈现最高的平均转化价值和 ROAS，餐饮 / 零售最低。CPA 主要由竞争
（拍卖 CPC + 转化率）驱动而非客单价，所以它的排序与价值排序不完全一致 ——
这是一个有用的教学要点。

---

### Query 3: 日环比花费趋势

**业务背景：**
某 campaign 经理发现昨天的花费看板有异常，想看最近两周的每日花费及
日环比变化，以确认尖峰是单日事件还是趋势变化。

**类别：** 窗口函数（LAG）
**难度：** Intermediate
**业务角色：** 经理

**解题思路：**
先用一个 CTE 把 `daily_stats` 按 `report_date` 聚合成每日总花费，消掉
campaign 和 device 两个维度。为什么非得先聚合？因为外层要用
`LAG(daily_spend) OVER (ORDER BY report_date)` 取前一天的值，而 LAG 是
严格按行往前取一行，必须保证每个日期只剩一行，否则 LAG 取到的是同一天
的另一条设备记录，环比就错了。第一行没有前值，`spend_delta` 和
`spend_delta_pct` 自然是 NULL，属正常。对应业务问题：预算效率与日常监控。

```sql
WITH daily AS (
    SELECT
        ds.report_date,
        ROUND(SUM(ds.cost), 2)        AS daily_spend,
        ROUND(SUM(ds.conversions), 2) AS daily_conversions
    FROM daily_stats ds
    WHERE ds.report_date >= DATE((SELECT reference_date FROM v_reference_date), '-14 days')
    GROUP BY ds.report_date
)
SELECT
    report_date,
    daily_spend,
    daily_conversions,
    ROUND(daily_spend - LAG(daily_spend) OVER (ORDER BY report_date), 2)
        AS spend_delta,
    ROUND(
        (daily_spend - LAG(daily_spend) OVER (ORDER BY report_date))
        / NULLIF(LAG(daily_spend) OVER (ORDER BY report_date), 0) * 100, 1
    ) AS spend_delta_pct
FROM daily
ORDER BY report_date;
```

**预期结果描述：**
按日期排序的 14 行。第一行的 `spend_delta` 和 `spend_delta_pct` 为
NULL。星期几季节性会呈现弱周性模式；单日 ±15-30% 百分比变化属正常；
超出则属异常。

---

### Query 4: Campaign 花费 vs 预算（fan-out 安全）

**业务背景：**
某 campaign 经理想知道哪些 campaign 相对其日预算花费最多 —— 找出过投
（节奏失控）和欠投（预算浪费）的 campaign。这个查询在已退役数据集
中曾是 fan-out bug：直接 join 时，有多版 `campaign_budget` 的 campaign
会双重计数花费。

**类别：** CTE + 关联子查询
**难度：** Advanced
**业务角色：** 经理

**解题思路：**
这题的难点在 `campaign_budget` 是版本化的，一个 campaign 可能有多版预算。
如果直接把 `campaign_budget` join 到 `daily_stats`，每条投放行会按预算版本
数扇出，花费被重复累计。正确做法是用关联子查询，对每行 `daily_stats` 取
`effective_date <= report_date` 里最新的那一版预算（`ORDER BY effective_date
DESC LIMIT 1`）。拿到在效预算后，先聚合到 campaign 加日的粒度把设备行收起来，
再对 campaign 求平均日花费除以平均日预算算 pacing。两层聚合的先后顺序是这
题的精髓。对应业务问题：预算效率。

```sql
-- 关联子查询解析"在该 report_date 当天生效的预算"：选 effective_date
-- ≤ report_date 中最新的那一行。没有这个写法的话，把 campaign_budget
-- 直接 join 到 daily_stats 会对任何有多版预算的 campaign 双重计数。
WITH effective_budget AS (
    SELECT
        ds.campaign_id,
        ds.report_date,
        ds.cost,
        (
            SELECT cb.daily_budget
            FROM   campaign_budget cb
            WHERE  cb.campaign_id = ds.campaign_id
              AND  cb.effective_date <= ds.report_date
            ORDER BY cb.effective_date DESC
            LIMIT 1
        ) AS daily_budget
    FROM daily_stats ds
    WHERE ds.report_date >= DATE((SELECT reference_date FROM v_reference_date), '-7 days')
),
per_campaign_day AS (
    SELECT
        campaign_id,
        report_date,
        SUM(cost)       AS day_cost,
        MAX(daily_budget) AS daily_budget
    FROM effective_budget
    WHERE daily_budget IS NOT NULL
    GROUP BY campaign_id, report_date
)
SELECT
    c.campaign_name,
    a.company_name,
    ROUND(AVG(pc.daily_budget), 2)                                          AS daily_budget,
    ROUND(AVG(pc.day_cost), 2)                                              AS avg_daily_spend,
    ROUND(AVG(pc.day_cost) / NULLIF(AVG(pc.daily_budget), 0) * 100, 1)      AS pacing_pct
FROM per_campaign_day pc
JOIN campaign   c ON c.id = pc.campaign_id
JOIN advertiser a ON a.id = c.advertiser_id
GROUP BY c.id, c.campaign_name, a.company_name
ORDER BY pacing_pct DESC
LIMIT 20;
```

**预期结果描述：**
按 `pacing_pct` 排序的 20 个 campaign（≈ 平均日花费 / 平均日预算 × 100）。
值 > 100% 表示超出计划过投；< 50% 表示预算受限的容量缺口。
`per_campaign_day` CTE 先把设备级行聚合到 campaign-日 粒度再平均，
这是让 per-campaign 平均值有意义的关键。

---

### Query 5: 超出 Target CPA 目标的 campaign

**业务背景：**
某付费搜索分析师在审计 Smart Bidding 表现：广告主要求用 `Target CPA`，
但实际情况完全不一样。分析师需要知道哪些 campaign 在用 Target CPA
策略，以及它们的实际 CPA 相对目标值是什么样。

**类别：** CTE + Join
**难度：** Intermediate
**业务角色：** 分析师

**解题思路：**
先在 CTE 里把 `campaign` join 到它绑定的 `bid_strategy` 拿 `target_cpa`，
再 join `daily_stats` 算实际花费和转化，过滤 `bid_strategy.target_cpa IS
NOT NULL`，只看真正用了 Target CPA 策略的 campaign。聚合到 campaign 粒度
得到 `actual_cpa` 之后，外层再过滤 `actual_cpa > target_cpa` 并算超出
百分比。把这个比较放外层（而不是塞进 WHERE）是因为 `actual_cpa` 是聚合
结果，只有聚合完才能比。对应业务问题：出价策略审计。

```sql
WITH campaign_actuals AS (
    SELECT
        c.id            AS campaign_id,
        c.campaign_name,
        a.company_name,
        bs.target_cpa,
        ROUND(SUM(ds.cost), 2)                                  AS total_cost,
        ROUND(SUM(ds.conversions), 2)                           AS total_conv,
        ROUND(SUM(ds.cost) / NULLIF(SUM(ds.conversions), 0), 2) AS actual_cpa
    FROM campaign c
    JOIN advertiser   a   ON a.id = c.advertiser_id
    JOIN bid_strategy bs  ON bs.id = c.bid_strategy_id
    JOIN daily_stats  ds  ON ds.campaign_id = c.id
    WHERE bs.target_cpa IS NOT NULL
      AND ds.report_date >= DATE((SELECT reference_date FROM v_reference_date), '-7 days')
    GROUP BY c.id, c.campaign_name, a.company_name, bs.target_cpa
)
SELECT
    company_name,
    campaign_name,
    target_cpa,
    actual_cpa,
    ROUND((actual_cpa - target_cpa) / target_cpa * 100, 1) AS over_target_pct,
    total_cost,
    total_conv
FROM campaign_actuals
WHERE actual_cpa > target_cpa
ORDER BY over_target_pct DESC
LIMIT 20;
```

**预期结果描述：**
最多 20 个 `actual_cpa > target_cpa` 的 campaign。`over_target_pct` 是
超出百分比；> 30% 表示 Smart Bidding 无法兑现目标，campaign 值得干预
（放宽目标、扩大受众、或切换出价策略）。

---

### Query 6: 设备级 CTR 和 CPA

**业务背景：**
某媒介分析师在评审组合层面手机还是桌面更高效。最简单的切法是按
设备对比过去 30 天的 CTR、CPA、ROAS。

**类别：** 聚合 + Join
**难度：** Basic
**业务角色：** 分析师

**解题思路：**
最直接的一题：`daily_stats` join `device`，按设备 `GROUP BY`。要点在 CTR
要用 `SUM(clicks) / SUM(impressions)` 而不是 `AVG(ctr)`，凡是率指标都得先把
分子分母各自加总再相除，逐行求率再平均会被低量行带偏。CPA / ROAS 同理。
生成器给三种设备加了固定倍数，所以预期 Mobile 展示最多、Desktop 转化率
最高因而 CPA 最低、Tablet 占比不到 10%，这是设计出来的结构而非噪声。对应
业务问题：设备效率。

```sql
SELECT
    d.name                                                       AS device,
    SUM(ds.impressions)                                          AS impressions,
    SUM(ds.clicks)                                               AS clicks,
    ROUND(SUM(ds.clicks) * 100.0 / NULLIF(SUM(ds.impressions), 0), 2) AS ctr_pct,
    ROUND(SUM(ds.cost), 2)                                       AS cost,
    ROUND(SUM(ds.conversions), 2)                                AS conversions,
    ROUND(SUM(ds.cost) / NULLIF(SUM(ds.conversions), 0), 2)      AS cpa,
    ROUND(SUM(ds.conversion_value) / NULLIF(SUM(ds.cost), 0), 2) AS roas
FROM daily_stats ds
JOIN device d ON d.id = ds.device_id
WHERE ds.report_date >= DATE((SELECT reference_date FROM v_reference_date), '-30 days')
GROUP BY d.id, d.name
ORDER BY cost DESC;
```

**预期结果描述：**
3 行（Mobile、Desktop、Tablet）。生成器应用设备倍数让分布匹配行业基准：
Mobile 承载 ~60% 的展示量，Desktop 的转化率大约是 Mobile 的 2 倍，
所以 Desktop 的 CPA 最低，Tablet 远远第三、占比 < 10%。

---

### Query 7: 引擎表现对比

**业务背景：**
某多引擎代理的付费搜索分析师想对比两家北美引擎（Google Ads、
Microsoft Advertising）的点击成本和转化量。组合被 Google 主导，
问题是 Microsoft 的 CPA 是否有竞争力。

**类别：** 聚合 + Join
**难度：** Basic
**业务角色：** 分析师

**解题思路：**
从 `engine_account` join `campaign` 再 join `daily_stats`，按 `engine_type`
分组。`active_campaigns` 用 `COUNT(DISTINCT c.id)` 防止 `daily_stats` 扇出
把 campaign 重复计数。重点看 `avg_cpc` 和 `cpa` 两列：Microsoft 的 CPC
明显低于 Google（约 80%），但转化率也低约 12%，两个反向效应抵消后两家
引擎的 CPA 反而接近。结论是引擎之间差在成本动态，不在成交质量。对应业务
问题：跨引擎效率。

```sql
SELECT
    ea.engine_type,
    COUNT(DISTINCT c.id)                                         AS active_campaigns,
    SUM(ds.impressions)                                          AS impressions,
    SUM(ds.clicks)                                               AS clicks,
    ROUND(SUM(ds.cost), 2)                                       AS cost,
    ROUND(SUM(ds.cost) / NULLIF(SUM(ds.clicks), 0), 2)           AS avg_cpc,
    ROUND(SUM(ds.cost) / NULLIF(SUM(ds.conversions), 0), 2)      AS cpa,
    ROUND(SUM(ds.conversion_value) / NULLIF(SUM(ds.cost), 0), 2) AS roas
FROM engine_account ea
JOIN campaign    c  ON c.engine_account_id = ea.id
JOIN daily_stats ds ON ds.campaign_id = c.id
WHERE ds.report_date >= DATE((SELECT reference_date FROM v_reference_date), '-30 days')
GROUP BY ea.engine_type
ORDER BY cost DESC;
```

**预期结果描述：**
2 行。Google Ads 承载 ~75% 的展示和花费；Microsoft Advertising ~25%。
Microsoft Advertising 的平均 CPC 显著更低（约为 Google 的 80%），但
转化率也低 ~12%，所以两家引擎的 CPA 最终相近。ROAS 同样接近 ——
两家引擎差在成本动态，而非成交质量。

---

### Query 8: 按行业的 Quality Score 分布

**业务背景：**
某搜索分析师想知道关键词 Quality Score 是否随行业变化 —— 竞争激烈的
垂直（保险、金融）往往有更多 QS < 6 的关键词。这指导优先在哪些行业
投入 QS 改善工作。

**类别：** 聚合 + Join
**难度：** Intermediate
**业务角色：** 分析师

**解题思路：**
`keyword` 一路往上 join 到 `ad_group`、`campaign`、`advertiser`、`industry`，
把每个关键词的行业标出来，再按行业聚合 Quality Score。分桶计数（QS 小于 5、
5 到 7、大于 7）用 `SUM(CASE WHEN ... THEN 1 ELSE 0 END)` 实现，这是 SQL 里
做直方图的标准手法。按"活跃"约定，三层都过滤 `status = 'Enabled'`，免得暂停
或已删除的实体污染分布。预期高竞争行业（保险、金融、地产）平均 QS 偏低、低
QS 占比高，低竞争行业（B2B SaaS、教育、餐饮）反之。对应业务问题：浪费治理。

```sql
SELECT
    i.name AS industry,
    COUNT(*) AS keyword_count,
    ROUND(AVG(k.quality_score), 2) AS avg_qs,
    SUM(CASE WHEN k.quality_score <  5 THEN 1 ELSE 0 END) AS qs_below_5,
    SUM(CASE WHEN k.quality_score BETWEEN 5 AND 7 THEN 1 ELSE 0 END) AS qs_5_to_7,
    SUM(CASE WHEN k.quality_score >  7 THEN 1 ELSE 0 END) AS qs_above_7,
    ROUND(SUM(CASE WHEN k.quality_score < 5 THEN 1 ELSE 0 END) * 100.0
          / COUNT(*), 1) AS pct_below_5
FROM keyword  k
JOIN ad_group ag ON ag.id = k.ad_group_id
JOIN campaign c  ON c.id  = ag.campaign_id
JOIN advertiser a ON a.id = c.advertiser_id
JOIN industry  i  ON i.id = a.industry_id
WHERE k.status  = 'Enabled'
  AND ag.status = 'Enabled'
  AND c.status  = 'Enabled'
GROUP BY i.id, i.name
ORDER BY pct_below_5 DESC;
```

**预期结果描述：**
10 行 —— 每行业一行，按低 QS 关键词占比降序。只计入 Enabled
campaign 下 Enabled ad group 下的 Enabled keyword（按"活跃"约定）。
生成器按行业竞争度偏置 QS：保险 / 金融 / 地产 从左移分布抽取
（平均 QS ~6.1，~35-37% < 6）；低竞争的 B2B SaaS / 教育 / 餐饮 从
右移分布抽取（平均 QS ~7.5，~10% < 6）。其他行业居中（~6.9 平均、
~18% < 6）。

---

### Query 9: 高花费 campaign 中的低 QS 关键词

**业务背景：**
某高级分析师在搜寻表现最差的关键词：处于真有花费的 campaign 内的
低 QS 关键词。**重要提示：** `daily_stats` 是 campaign 粒度而非 keyword
粒度，所以这个查询无法计算 *keyword 级* 花费；它呈现的是过去 30 天
*所在 campaign* 花费 > $5,000 的低 QS 关键词。可执行的解读是
"这些有这么多预算在跑的 campaign 里包含这批低 QS 关键词 ——
优先修这些关键词的落地页或广告相关性信号。"

**类别：** 跨层 Join
**难度：** Advanced
**业务角色：** 分析师

**解题思路：**
这题最关键的认知是 `daily_stats` 是 campaign 粒度，不是 keyword 粒度，所以
它算不出关键词级花费，只能算关键词所在 campaign 的花费。`keyword` join 到
`campaign` 再 join `daily_stats`，每个关键词行会扇出到所在 campaign 的所有
投放行，`GROUP BY` 关键词后 SUM 得到的其实是"宿主 campaign 的花费"，列名
特意叫 `host_campaign_spend_30d` 来提醒这一点，不要误读成关键词花费。过滤
低 QS（小于 6），`HAVING` 卡 campaign 花费大于 5000 美元。对应业务问题：
浪费治理。

```sql
SELECT
    k.keyword_text,
    mt.name                                              AS match_type,
    k.quality_score,
    k.expected_ctr,
    k.ad_relevance,
    k.landing_page_exp,
    ROUND(SUM(ds.cost), 2)                               AS host_campaign_spend_30d,
    ROUND(SUM(ds.conversions), 2)                        AS host_campaign_conv_30d
FROM keyword k
JOIN match_type mt ON mt.id = k.match_type_id
JOIN ad_group   ag ON ag.id = k.ad_group_id
JOIN campaign   c  ON c.id  = ag.campaign_id
JOIN daily_stats ds ON ds.campaign_id = c.id
WHERE k.status  = 'Enabled'
  AND ag.status = 'Enabled'
  AND c.status  = 'Enabled'
  AND k.quality_score < 6
  AND ds.report_date >= DATE((SELECT reference_date FROM v_reference_date), '-30 days')
GROUP BY k.id, k.keyword_text, mt.name, k.quality_score,
         k.expected_ctr, k.ad_relevance, k.landing_page_exp
HAVING SUM(ds.cost) > 5000
ORDER BY host_campaign_spend_30d DESC
LIMIT 30;
```

**预期结果描述：**
最多 30 个低 QS 关键词，所在 campaign 在过去 30 天花费 > $5,000。
列名是 `host_campaign_spend_30d`（不是 "keyword_spend_30d"），因为
`daily_stats` 是 campaign 粒度 —— 这个钱数是关键词所属 campaign 的
花费，不是关键词级花费。用作质量改善工作的优先级清单。

---

### Query 10: 高成本零转化搜索词

**业务背景：**
某 campaign 运营专员每周做一次"否定关键词复盘"：花掉预算却没产生
转化的搜索词。这些是否定关键词排除列表的候选词，把预算夺回给那些
能转化的词。

**类别：** LEFT JOIN + 聚合
**难度：** Basic
**业务角色：** 运营

**解题思路：**
`search_term_report` 用 `LEFT JOIN keyword`，因为约 15% 的搜索词是广泛匹配
溢出（`keyword_id` 为 NULL），只有 LEFT JOIN 才能保住这些行；换成 INNER
JOIN 会把最该被排除的溢出词直接丢掉，正好弄丢了答案。按搜索词聚合，
`HAVING SUM(conversions) = 0 AND SUM(cost) > 50` 筛出"烧了钱却零转化"的词。
结果里 `matched_keyword` 为 NULL 本身就是个有用信号：纯广泛匹配漏出往往
主导这张否定关键词候选清单。对应业务问题：浪费治理。

```sql
SELECT
    str.search_term,
    k.keyword_text                                       AS matched_keyword,
    str.match_type_used,
    SUM(str.impressions)                                 AS impressions,
    SUM(str.clicks)                                      AS clicks,
    ROUND(SUM(str.cost), 2)                              AS cost,
    str.added_excluded
FROM search_term_report str
LEFT JOIN keyword k ON k.id = str.keyword_id
WHERE str.report_date >= DATE((SELECT reference_date FROM v_reference_date), '-14 days')
GROUP BY str.search_term, k.keyword_text, str.match_type_used, str.added_excluded
HAVING SUM(str.conversions) = 0
   AND SUM(str.cost) > 50
ORDER BY cost DESC
LIMIT 30;
```

**预期结果描述：**
最多 30 个在过去 14 天花费 > $50 且零转化的搜索词。
`matched_keyword` 可能为 NULL —— 说明该词是广泛匹配溢出（没有任何存储
关键词直接匹配它），这本身是个有用信号：纯广泛匹配漏出往往主导这个清单。

---

### Query 11: 广泛匹配溢出占比

**业务背景：**
某付费搜索分析师想知道搜索词展示有多少来自广泛匹配溢出，相对匹配到
存储关键词的部分。某个 ad group 的溢出占比过高，说明匹配类型策略
过于宽松。

**类别：** NULL 处理 + 聚合
**难度：** Intermediate
**业务角色：** 分析师

> **可移植性说明：** `HAVING overflow_pct > 20` 子句引用 `SELECT`
> 别名，SQLite 接受但严格 ANSI SQL 不接受。可移植写法见底部 Notes 段。

**解题思路：**
核心是用 `SUM(CASE WHEN str.keyword_id IS NULL THEN 1 ELSE 0 END)` 数出溢出
行数，除以 `COUNT(*)` 得到溢出占比，按 campaign 加 ad_group 分组。这是典型
的 NULL 处理题：`keyword_id IS NULL` 标识引擎服务了查询却匹配不回任何已存
关键词。注意 `HAVING overflow_pct > 20` 引用了 SELECT 别名，SQLite 允许，
但严格 ANSI 不允许（可移植写法见文末 Notes）。`overflow_cost_30d` 用同样的
CASE 求和把溢出花费单独拎出来。对应业务问题：浪费治理。

```sql
SELECT
    c.campaign_name,
    ag.ad_group_name,
    COUNT(*)                                                    AS total_term_rows,
    SUM(CASE WHEN str.keyword_id IS NULL THEN 1 ELSE 0 END)     AS overflow_rows,
    ROUND(
        SUM(CASE WHEN str.keyword_id IS NULL THEN 1 ELSE 0 END) * 100.0
        / COUNT(*), 1
    )                                                           AS overflow_pct,
    ROUND(SUM(str.cost), 2)                                     AS cost_30d,
    ROUND(
        SUM(CASE WHEN str.keyword_id IS NULL THEN str.cost ELSE 0 END), 2
    )                                                           AS overflow_cost_30d
FROM search_term_report str
JOIN ad_group ag ON ag.id = str.ad_group_id
JOIN campaign c  ON c.id = str.campaign_id
WHERE str.report_date >= DATE((SELECT reference_date FROM v_reference_date), '-30 days')
GROUP BY c.id, ag.id, c.campaign_name, ag.ad_group_name
HAVING overflow_pct > 20
ORDER BY overflow_cost_30d DESC
LIMIT 20;
```

**预期结果描述：**
超过 20% 搜索词行为广泛匹配溢出的 ad group。`overflow_cost_30d` 显示
实际流向非关键词匹配查询的金额。生成器平均 ~15% 溢出，所以这个清单
偏向溢出率升高的 ad group。

---

### Query 12: 首触 vs 末触渠道组合

**业务背景：**
CMO 想知道品牌的末触归因是否掩盖了启动用户旅程的上漏斗渠道。经典
回答是并列对比：每个渠道作为首触 vs 末触的转化占比是多少？

**类别：** CTE + 聚合
**难度：** Advanced
**业务角色：** 分析师

**解题思路：**
先用一个 CTE 求每个 `conversion` 的 `MIN(touchpoint_order)`（首触序号）和
`MAX(touchpoint_order)`（末触序号），再 join 回 `attribution_path` 只取这
两个序号的行，并打上 first / last / single 标签。为什么用一个 CTE 加标签，
而不是写两个 CTE 各 LEFT JOIN？因为两个 CTE 再按 channel join 会悄悄产生
笛卡尔积，让计数虚高。`single` 标签专门处理路径只有一个触点、首末同体的
情形（虽然本数据集路径长度至少为 2）。对应业务问题：归因真相。

```sql
-- 单 CTE 模式同时解出每个 conversion 的首触和末触。避免"两个 CTE 各
-- LEFT JOIN"那种会按渠道悄悄产生 Cartesian 的写法。
WITH conversion_bounds AS (
    SELECT
        conversion_id,
        MIN(touchpoint_order) AS first_order,
        MAX(touchpoint_order) AS last_order
    FROM attribution_path
    GROUP BY conversion_id
),
labeled AS (
    SELECT
        ap.conversion_id,
        ap.channel_id,
        CASE
            WHEN ap.touchpoint_order = cb.first_order AND ap.touchpoint_order = cb.last_order
                 THEN 'single'
            WHEN ap.touchpoint_order = cb.first_order THEN 'first'
            WHEN ap.touchpoint_order = cb.last_order  THEN 'last'
        END AS position
    FROM attribution_path ap
    JOIN conversion_bounds cb ON cb.conversion_id = ap.conversion_id
    WHERE ap.touchpoint_order IN (cb.first_order, cb.last_order)
)
SELECT
    ch.name AS channel,
    SUM(CASE WHEN position IN ('first', 'single') THEN 1 ELSE 0 END) AS first_touches,
    SUM(CASE WHEN position IN ('last',  'single') THEN 1 ELSE 0 END) AS last_touches,
    ROUND(
        SUM(CASE WHEN position IN ('first', 'single') THEN 1 ELSE 0 END) * 100.0
        / (SELECT COUNT(DISTINCT conversion_id) FROM attribution_path), 1
    ) AS first_touch_pct,
    ROUND(
        SUM(CASE WHEN position IN ('last',  'single') THEN 1 ELSE 0 END) * 100.0
        / (SELECT COUNT(DISTINCT conversion_id) FROM attribution_path), 1
    ) AS last_touch_pct
FROM labeled
JOIN channel ch ON ch.id = labeled.channel_id
GROUP BY ch.id, ch.name
ORDER BY first_touches DESC;
```

**预期结果描述：**
6 行（每渠道一行）。两列百分比跨渠道加起来都接近 100%。Display 和
Paid Social 的首触占比通常大于末触占比（上漏斗角色）；Paid Search
和 Direct 通常反过来。

---

### Query 13: 转化路径长度分布

**业务背景：**
某营销分析师想要触点数分布：有多少转化是"单触"vs"多触"、典型路径
有多长？这指导多触点归因是否值得运营化。

**类别：** 子查询 + 聚合
**难度：** Intermediate
**业务角色：** 分析师

**解题思路：**
内层子查询对每个 `conversion` 求 `MAX(touchpoint_order)` 得到这条路径的长度，
外层按路径长度 `GROUP BY` 数转化数。占比用
`COUNT(*) * 100.0 / SUM(COUNT(*)) OVER ()` 这个"在聚合之上再开窗"的技巧算，
省得再写一个子查询去求总数。生成器按截断几何分布采样路径长度（权重
`[40, 30, 15, 10, 5]` 对应 N 等于 2 到 6），所以 2 触点应主导（约 40%）、
6 触点稀有。对应业务问题：归因真相。

```sql
SELECT
    path_length,
    COUNT(*)                                                   AS conversion_count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 1)         AS pct_of_conversions
FROM (
    SELECT conversion_id, MAX(touchpoint_order) AS path_length
    FROM attribution_path
    GROUP BY conversion_id
) per_conversion
GROUP BY path_length
ORDER BY path_length;
```

**预期结果描述：**
路径长度 2 到 6 共 5 行（生成器不产 path = 1）。生成器按截断几何分布
采样，权重 `[40, 30, 15, 10, 5]`，所以 2 触点主导（~40%）、6 触点稀有
（~5%）—— 接近现实归因中大多数转化都是短路径的模式。

---

### Query 14: 各归因模型下的渠道价值

**业务背景：**
某高管想看渠道估值如何随归因模型变化：付费搜索在末触归因下的份额
几乎总是比数据驱动下的份额高，高管想量化这个差距。

**类别：** 聚合 + Join
**难度：** Intermediate
**业务角色：** 高管

**解题思路：**
`attribution_path` join `conversion` 拿每笔转化的金额、join `channel` 拿渠道名。
六个价值列分别是六种归因模型的信用乘以 `conversion_value` 再求和，一次扫描
就把所有模型下的渠道估值都算出来。因为本数据集的渠道按触点位置偏置（Display
和 Paid Social 偏首触、Paid Search 和 Direct 偏末触），末触模型会明显高估
Paid Search 和 Direct，首触模型则高估 Display 和 Social，这正是末触报表经典
的下漏斗偏差。注意 `data_driven` 列是模拟随机数，别当真实 DDA 模型解读。
对应业务问题：归因真相。

```sql
SELECT
    ch.name AS channel,
    ROUND(SUM(ap.last_click_credit  * c.conversion_value), 2) AS last_click_value,
    ROUND(SUM(ap.first_click_credit * c.conversion_value), 2) AS first_click_value,
    ROUND(SUM(ap.linear_credit      * c.conversion_value), 2) AS linear_value,
    ROUND(SUM(ap.time_decay_credit  * c.conversion_value), 2) AS time_decay_value,
    ROUND(SUM(ap.position_credit    * c.conversion_value), 2) AS position_value,
    ROUND(SUM(ap.data_driven_credit * c.conversion_value), 2) AS data_driven_value
FROM attribution_path ap
JOIN conversion c  ON c.id  = ap.conversion_id
JOIN channel    ch ON ch.id = ap.channel_id
GROUP BY ch.id, ch.name
ORDER BY data_driven_value DESC;
```

**预期结果描述：**
6 行（每渠道一行）。6 列价值是按金额加权的信用之和。因为本数据集的
渠道组合按触点位置偏置（Display / Paid Social 偏首触；Paid Search /
Direct 偏末触），末触显著高估 Paid Search 和 Direct，首触显著高估
Display 和 Paid Social —— 末触报表经典的"下漏斗偏差"可以被观察到。

> **关于 `data_driven_value` 的说明。** 本数据集中
> `data_driven_credit` 是每触点的归一化随机，不是真实 DDA 模型的输出。
> 这列存在是为了让学习者能写 6 模型对比查询；不要把
> `data_driven_value` 的绝对数解读为"数据驱动模型会说什么"。

---

### Query 15: 受预算约束的 campaign

**业务背景：**
某 campaign 经理想识别因为预算而损失展示份额的 campaign —— 那些加预算
就能直接买到更多展示的。这是每周优化会上的"轻松赚钱"清单。

**类别：** CTE + 关联子查询
**难度：** Advanced
**业务角色：** 经理

**解题思路：**
骨架和 Query 4 一样（关联子查询取每天的在效预算、先聚合到 campaign 加日），
但这题关心的指标换成 `lost_is_budget`（因预算损失的展示份额）。聚合到
campaign 粒度后求 7 天平均 `lost_is_budget`，`HAVING avg_lost_is_budget > 15`
筛出经常因预算而丢展示的 campaign。生成器在日花费接近在效预算时把
`lost_is_budget` 向上偏置，所以这张清单天然对应那些撞到日预算上限的 campaign，
也就是优化会上"加预算就能直接买到更多展示"的轻松赚钱清单。对应业务问题：
预算效率。

```sql
WITH effective_budget AS (
    SELECT
        ds.campaign_id,
        ds.report_date,
        ds.cost,
        ds.lost_is_budget,
        (
            SELECT cb.daily_budget
            FROM   campaign_budget cb
            WHERE  cb.campaign_id = ds.campaign_id
              AND  cb.effective_date <= ds.report_date
            ORDER BY cb.effective_date DESC
            LIMIT 1
        ) AS daily_budget
    FROM daily_stats ds
    WHERE ds.report_date >= DATE((SELECT reference_date FROM v_reference_date), '-7 days')
),
per_campaign_day AS (
    SELECT campaign_id, report_date,
           SUM(cost)                AS day_cost,
           AVG(lost_is_budget)      AS day_lost_budget,
           MAX(daily_budget)        AS daily_budget
    FROM effective_budget
    WHERE daily_budget IS NOT NULL
    GROUP BY campaign_id, report_date
)
SELECT
    c.campaign_name,
    a.company_name,
    ROUND(AVG(pc.daily_budget), 2)                                    AS daily_budget,
    ROUND(AVG(pc.day_cost), 2)                                        AS avg_daily_spend,
    ROUND(AVG(pc.day_lost_budget), 1)                                 AS avg_lost_is_budget,
    ROUND(AVG(pc.day_cost) / NULLIF(AVG(pc.daily_budget), 0) * 100, 1) AS pacing_pct
FROM per_campaign_day pc
JOIN campaign   c ON c.id = pc.campaign_id
JOIN advertiser a ON a.id = c.advertiser_id
WHERE c.status = 'Enabled'
GROUP BY c.id, c.campaign_name, a.company_name
HAVING avg_lost_is_budget > 15
ORDER BY avg_lost_is_budget DESC
LIMIT 20;
```

**预期结果描述：**
最多 20 个 Enabled campaign，过去 7 天平均 `lost_is_budget` > 15。
生成器在花费接近在效预算时向上偏置 `lost_is_budget`，所以这个清单
天然呈现碰到日预算上限的 campaign。

---

### Query 16: 占据首页位置的 campaign（仅 Search、按展示加权）

**业务背景：**
某 campaign 经理想知道哪些 Search campaign 占据搜索结果页（高
`search_top_is`）—— 这些是"黄金位置"健康 campaign，预算和出价都到位。
对立清单（低份额）是下一张幻灯片。

**类别：** 聚合 + Join + 加权平均
**难度：** Intermediate
**业务角色：** 经理

**解题思路：**
两个要点。第一，`search_*_is` 只在 Search campaign 上有值（非 Search 行为
NULL），所以必须先过滤 `campaign_type = 'Search'`，否则聚合会被 NULL 干扰。
第二，展示份额是个按展示量加权的指标，三个位置指标都要用
`SUM(IS × impressions) / SUM(impressions)` 做加权平均，而不是 `AVG(IS)`，
否则低量的桌面切片会和高量的手机日等权重，平均值失真。构造上
`abs_top_is <= top_is <= impression_share`，所以三列天然有序。`HAVING` 卡
展示量大于 10000 去掉小样本噪声。对应业务问题：预算效率与位置健康。

```sql
-- impression share 是按 impression 的指标；SUM(IS × impressions) /
-- SUM(impressions) 是按展示加权的平均，这才是跨日 / 跨设备聚合的正确
-- 算法。纯 AVG(IS) 会把低量桌面切片和高量手机日同等对待。
-- search_*_is 在非 Search 行上为 NULL，所以必须加 campaign_type 过滤。
SELECT
    c.campaign_name,
    a.company_name,
    ROUND(
        SUM(ds.search_abs_top_is * ds.impressions) * 1.0
        / NULLIF(SUM(ds.impressions), 0), 1
    )                                                                  AS avg_abs_top_is,
    ROUND(
        SUM(ds.search_top_is * ds.impressions) * 1.0
        / NULLIF(SUM(ds.impressions), 0), 1
    )                                                                  AS avg_top_is,
    ROUND(
        SUM(ds.impression_share * ds.impressions) * 1.0
        / NULLIF(SUM(ds.impressions), 0), 1
    )                                                                  AS avg_impr_share,
    ROUND(SUM(ds.clicks) * 100.0 / NULLIF(SUM(ds.impressions), 0), 2)  AS ctr_pct
FROM daily_stats ds
JOIN campaign   c ON c.id = ds.campaign_id
JOIN advertiser a ON a.id = c.advertiser_id
WHERE c.campaign_type = 'Search'
  AND ds.report_date >= DATE((SELECT reference_date FROM v_reference_date), '-7 days')
GROUP BY c.id, c.campaign_name, a.company_name
HAVING SUM(ds.impressions) > 10000
ORDER BY avg_abs_top_is DESC
LIMIT 20;
```

**预期结果描述：**
20 个绝对页首展示份额强的 Search campaign。三个位置指标按展示加权
（所以高量手机日比近零桌面日权重大）。构造上
`abs_top_is ≤ top_is ≤ impression_share`，所以三列有序。

---

### Query 17: 按代理等级的代理组合表现

**业务背景：**
某代理高管想按代理等级看表现 —— Platinum 代理的 ROAS 比 Standard 好
吗？这是代理母公司季度评审的 KPI 问题。

**类别：** Join + 聚合
**难度：** Intermediate
**业务角色：** 高管

**解题思路：**
`agency` join `agency_client`（桥接表）再 join `campaign`、`daily_stats`，
按 `tier_level` 分组。过滤 `ac.is_active = 1` 只算当前在册的代理关系。这里
`agency_client` 当前是 1:N 使用且有 `UNIQUE(agency_id, advertiser_id)`，所以
桥接不会重复扇出广告主。生成器按代理等级乘以广告主公司规模偏置分配
（Platinum / Gold 偏向 Enterprise / Mid-Market），所以 `total_spend` 在高等级
最大；但每个等级内部 CPA / ROAS 还随行业组合波动，按花费排序单调、按 ROAS
排序却不单调，这是个有用的教学点：最大的代理等级不会自动最有效率。对应
业务问题：代理与组合结构。

```sql
SELECT
    ag.tier_level,
    COUNT(DISTINCT ag.id)                                       AS agency_count,
    COUNT(DISTINCT ac.advertiser_id)                            AS advertiser_count,
    ROUND(SUM(ds.cost), 2)                                       AS total_spend,
    ROUND(SUM(ds.conversions), 2)                                AS total_conversions,
    ROUND(SUM(ds.cost) / NULLIF(SUM(ds.conversions), 0), 2)      AS cpa,
    ROUND(SUM(ds.conversion_value) / NULLIF(SUM(ds.cost), 0), 2) AS roas
FROM agency ag
JOIN agency_client ac ON ac.agency_id     = ag.id
JOIN campaign      c  ON c.advertiser_id  = ac.advertiser_id
JOIN daily_stats   ds ON ds.campaign_id   = c.id
WHERE ac.is_active = 1
  AND c.status     = 'Enabled'
  AND ds.report_date >= DATE((SELECT reference_date FROM v_reference_date), '-30 days')
GROUP BY ag.tier_level
ORDER BY total_spend DESC;

-- 注：本查询把花费记到*当前*在册代理（ac.is_active = 1）上。它没有
-- 按 agency_client 合同日期窗口约束花费窗口。真实审计中，窗口期内
-- 换过代理的 campaign，早期花费应记到上一家代理；这里全部记到当前那家。
```

**预期结果描述：**
4 行（Platinum / Gold / Silver / Standard）。Platinum 和 Gold 代理管理
更多 Enterprise / Mid-Market 广告主（生成器按 `tier_level × company_size`
偏置代理 → 广告主分配），所以 `total_spend` 最大。每个等级内 CPA / ROAS
仍随行业组合不同；按 `total_spend` 排序单调，但按 ROAS 排序不单调 ——
一个有用的教学要点："最大的代理等级不会自动最有效率"。

---

### Query 18: 按首触渠道的转化时延

**业务背景：**
某营销分析师想了解用户在首触之后多久才转化、按渠道分组。长时延说明
该渠道扮演上漏斗角色；短时延说明它扮演临门一脚角色。

**类别：** CTE + Join
**难度：** Intermediate
**业务角色：** 分析师

**解题思路：**
先用一个子查询求每个 `conversion` 的 `MIN(touchpoint_order)`（首触序号），
join 回 `attribution_path` 只取首触行，拿它的 `hours_before_conv` 和
`days_before_conv`，再按首触渠道聚合平均时延。构造上 `hours_before_conv`
受该转化所属 Floodlight 标签的 `lookback_window` 限制，所以 `max_days_to_conv`
最多 90。更常扮演首触的渠道，平均转化前小时数更高（排在表头），说明它在
旅程里偏上漏斗角色；短时延则偏临门一脚。对应业务问题：归因真相。

```sql
WITH first_touch AS (
    SELECT
        ap.conversion_id,
        ap.channel_id,
        ap.hours_before_conv,
        ap.days_before_conv
    FROM attribution_path ap
    JOIN (
        SELECT conversion_id, MIN(touchpoint_order) AS first_order
        FROM attribution_path
        GROUP BY conversion_id
    ) fo ON fo.conversion_id = ap.conversion_id AND ap.touchpoint_order = fo.first_order
)
SELECT
    ch.name                                AS first_touch_channel,
    COUNT(*)                               AS conversion_count,
    ROUND(AVG(ft.hours_before_conv), 1)    AS avg_hours_to_conv,
    ROUND(AVG(ft.days_before_conv), 2)     AS avg_days_to_conv,
    MAX(ft.days_before_conv)               AS max_days_to_conv
FROM first_touch ft
JOIN channel ch ON ch.id = ft.channel_id
GROUP BY ch.id, ch.name
ORDER BY avg_hours_to_conv DESC;
```

**预期结果描述：**
6 行。构造上 `hours_before_conv` 受 conversion 所属 tag 的
`lookback_window` 限制，所以 `max_days_to_conv` 最多 90。更频繁作为
首触的渠道，平均转化前小时数更高（排在表头）。

---

### Query 19: 周环比 CPA 诊断

**业务背景：**
代理经理发现上周 CPA 看起来比前一周高，想要分解：是 CPC 抬升、CTR
疲软、还是转化率崩了？这是经典的"为什么 CPA 动了？"诊断。

**类别：** CTE + CASE + 日期算术
**难度：** Advanced
**业务角色：** 经理

**解题思路：**
用 `CASE` 把 `daily_stats` 的每一天打上 `this_week` 或 `last_week` 标签
（基于 `report_date` 相对参考日期的回溯），在 CTE 里分别聚合 spend、avg_cpc、
ctr、conv_rate、cpa。最后一层用 `MAX(CASE WHEN period = ... THEN ... END)`
把两周的指标透视成一行并排，这是 SQL 里常见的行转列手法。这样并排之后，
分析师就能把 CPA 的变化机械地分解到 CPC、CTR、转化率三个因子上：比如 CPC
涨 10%、转化率降 5%，CPA 大致上涨 15%。如果三个因子都没动而 CPA 动了，那
就是组合内高低 CPA campaign 的占比发生了切换。对应业务问题：跨引擎效率与
预算诊断。

```sql
WITH base AS (
    SELECT
        CASE
            WHEN ds.report_date > DATE((SELECT reference_date FROM v_reference_date), '-7 days')
                THEN 'this_week'
            WHEN ds.report_date > DATE((SELECT reference_date FROM v_reference_date), '-14 days')
                THEN 'last_week'
        END AS period,
        ds.cost,
        ds.clicks,
        ds.impressions,
        ds.conversions
    FROM daily_stats ds
    WHERE ds.report_date > DATE((SELECT reference_date FROM v_reference_date), '-14 days')
),
agg AS (
    SELECT
        period,
        ROUND(SUM(cost), 2)                                       AS spend,
        ROUND(SUM(cost) / NULLIF(SUM(clicks), 0), 2)              AS avg_cpc,
        ROUND(SUM(clicks) * 100.0 / NULLIF(SUM(impressions), 0), 2) AS ctr_pct,
        ROUND(SUM(conversions) * 100.0 / NULLIF(SUM(clicks), 0), 2) AS conv_rate_pct,
        ROUND(SUM(cost) / NULLIF(SUM(conversions), 0), 2)         AS cpa
    FROM base
    WHERE period IS NOT NULL
    GROUP BY period
)
SELECT
    MAX(CASE WHEN period = 'this_week' THEN spend END)         AS this_week_spend,
    MAX(CASE WHEN period = 'last_week' THEN spend END)         AS last_week_spend,
    MAX(CASE WHEN period = 'this_week' THEN cpa END)           AS this_week_cpa,
    MAX(CASE WHEN period = 'last_week' THEN cpa END)           AS last_week_cpa,
    MAX(CASE WHEN period = 'this_week' THEN avg_cpc END)       AS this_week_cpc,
    MAX(CASE WHEN period = 'last_week' THEN avg_cpc END)       AS last_week_cpc,
    MAX(CASE WHEN period = 'this_week' THEN ctr_pct END)       AS this_week_ctr,
    MAX(CASE WHEN period = 'last_week' THEN ctr_pct END)       AS last_week_ctr,
    MAX(CASE WHEN period = 'this_week' THEN conv_rate_pct END) AS this_week_conv_rate,
    MAX(CASE WHEN period = 'last_week' THEN conv_rate_pct END) AS last_week_conv_rate
FROM agg;
```

**预期结果描述：**
一行，包含本周和上周的 spend、CPA、CPC、CTR、conv_rate 数值。
这个分解让分析师能把 CPA 变化归因到具体因子：比如 CPC 涨 10%、
conv-rate 降 5%，CPA 机械上涨 ≈ 15%。如果只有 CPA 动了而 CPC / CTR /
conv-rate 都没动，原因就是组合内高 CPA 和低 CPA campaign 之间的占比
切换。

---

### Query 20: 搜索词报表中的关键词覆盖率

**业务背景：**
某搜索运营专员想知道过去 30 天有多少 Enabled 关键词真的有搜索词数据。
没有搜索词行的关键词要么是刚添加、要么在引擎层暂停、要么属低量
垂直 —— 都值得标记出来。

**类别：** LEFT JOIN + 聚合
**难度：** Basic
**业务角色：** 运营

**解题思路：**
`keyword` 往上 join 到行业，再 `LEFT JOIN` 一个"每个关键词有多少条搜索词
记录"的子查询。用 LEFT JOIN 是关键：要保留那些一条搜索词记录都没有的关键词，
它们正是覆盖缺口；INNER JOIN 会把它们悄悄丢掉，覆盖率就虚高了。子查询里
过滤 `keyword_id IS NOT NULL`（只数真正匹配回关键词的行）。按行业聚合，
`coverage_pct` 是有记录的关键词占 Enabled 关键词的比例。因为每个关键词采样
约 5 天、溢出率才 15%，全溢出的概率极低，所以各行业覆盖率应都接近 99%，
明显偏低就说明真有搜索词跟踪缺口。对应业务问题：浪费治理与数据质量。

```sql
SELECT
    i.name                                                      AS industry,
    COUNT(*)                                                    AS enabled_keywords,
    SUM(CASE WHEN str_counts.row_count > 0 THEN 1 ELSE 0 END)   AS keywords_with_terms,
    ROUND(
        SUM(CASE WHEN str_counts.row_count > 0 THEN 1 ELSE 0 END) * 100.0
        / COUNT(*), 1
    )                                                           AS coverage_pct
FROM keyword k
JOIN ad_group ag  ON ag.id = k.ad_group_id
JOIN campaign  c  ON c.id  = ag.campaign_id
JOIN advertiser a ON a.id  = c.advertiser_id
JOIN industry  i  ON i.id  = a.industry_id
LEFT JOIN (
    SELECT keyword_id, COUNT(*) AS row_count
    FROM search_term_report
    WHERE keyword_id IS NOT NULL
      AND report_date >= DATE((SELECT reference_date FROM v_reference_date), '-30 days')
    GROUP BY keyword_id
) str_counts ON str_counts.keyword_id = k.id
WHERE k.status  = 'Enabled'
  AND ag.status = 'Enabled'
  AND c.status  = 'Enabled'
GROUP BY i.id, i.name
ORDER BY coverage_pct;
```

**预期结果描述：**
10 行（每行业一行）。`coverage_pct` 是过去 30 天至少有一条匹配
`search_term_report` 行（且 `keyword_id` 非 NULL）的 Enabled 关键词占比。
分层采样器对每个关键词产 ~5 天 × 1–2 行搜索词，其中 ~15% 行的
`keyword_id` 为 NULL（广泛匹配溢出）。某关键词所有 ~7 行采样**全部**都
是广泛匹配溢出的概率是 `0.15^7 ≈ 1.7e-6`，所以各行业的 `coverage_pct`
应该都在 99% 高位。这里出现明显更低的 coverage_pct 表示真的有搜索词
跟踪缺口，而不是行级广泛匹配溢出占比的事。

---

## 查询类别汇总

每个查询按主要技巧计入一次。

| 类别 | 数量 | 查询编号 |
|---|---:|---|
| 聚合 + 简单 Join | 6 | 1, 2, 6, 7, 14, 17 |
| 窗口函数 | 1 | 3 |
| CTE / 关联子查询 | 6 | 4, 5, 12, 15, 18, 19 |
| 跨层 / 多表 Join | 2 | 8, 9 |
| LEFT JOIN + 聚合 | 2 | 10, 20 |
| NULL 处理 + 聚合 | 1 | 11 |
| 子查询 + 聚合 | 1 | 13 |
| 加权聚合 | 1 | 16 |
| 合计 | **20** | |

## 业务角色覆盖

| 角色 | 数量 | 查询 |
|---|---:|---|
| 高管 | 4 | 1, 2, 14, 17 |
| 经理 | 5 | 3, 4, 15, 16, 19 |
| 分析师 | 9 | 5, 6, 7, 8, 9, 11, 12, 13, 18 |
| 运营 | 2 | 10, 20 |
| **合计** | **20** | |

## 难度分布

| 难度 | 数量 | 查询 |
|---|---:|---|
| Basic | 6 | 1, 2, 6, 7, 10, 20 |
| Intermediate | 9 | 3, 5, 8, 11, 13, 14, 16, 17, 18 |
| Advanced | 5 | 4, 9, 12, 15, 19 |
| **合计** | **20** | |

---

## Notes

- 所有查询为 SQLite 3.x 编写。
- 所有时间窗口查询引用 `v_reference_date`。重新生成数据集后，视图
  自动重新锚定到新的 max 日期 —— 查询不需要重写。
- 布尔列（`is_active`, `is_automated`）可以用 `= 1` 或 `= 0` 比较。
  加载器把 `0/1` 和 `true/false` 两种 TSV 表示都规范化为 SQLite
  整数存储。
- 聚合 `search_*_is` 列的查询（只有 Query 16）必须过滤
  `campaign_type = 'Search'` —— 这列在 Display / Video / Performance
  Max / Shopping 行上为 NULL。
- `keyword` 在 PostgreSQL / Oracle / SQL Server 中是保留字。SQLite
  接受不带引号；移植到其他方言时，引用为 `"keyword"`（或用
  `keyword AS k` 然后引用 `k`）。
- **严格 SQL 中 `HAVING` 不能引用 `SELECT` 别名。** Query 11 有
  `HAVING overflow_pct > 20`，在 SQLite 中可用因为它在 `HAVING`
  之前求值 `SELECT` 别名。PostgreSQL 和 Oracle 不行 —— 移植时把表达式
  重复一遍（`HAVING SUM(CASE WHEN keyword_id IS NULL THEN 1 ELSE 0
  END) * 100.0 / COUNT(*) > 20`），或者把内层聚合包进 CTE 后在外层
  `WHERE` 加过滤。
