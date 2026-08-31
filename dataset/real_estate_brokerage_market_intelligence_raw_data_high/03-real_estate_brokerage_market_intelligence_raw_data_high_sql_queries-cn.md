# Crestline 房地产经纪 — 市场情报原始数据：SQL 查询参考

## 概览

本文档提供 **20 条业务导向的 SQL 查询**，针对 `real_estate_brokerage_market_intelligence_raw_data_high` 数据集（23 张表、~328K 行）设计。每条查询回答一个 Crestline Realty stakeholder（高管、经理、分析师、agent、运营）会真实问出来的现实问题。所有查询都直接在 SQLite 数据库上跑得通，同时作为数据集分析保真度的**验收测试**。

**关于日期**：所有时间窗口查询使用字面量 `'2026-06-05'`（数据集的有效"当前日期"）而不是 `date('now')`，这样无论何时运行结果都可重现。在 Redshift/Postgres 上把日期换成 `current_date - interval '12 months'` 即可。

**配套文档**：动手前请先读 `01-real_estate_brokerage_market_intelligence_raw_data_high_business_context-cn.md`（公司、行业、业务问题、术语表、指标公式）和 `02-real_estate_brokerage_market_intelligence_raw_data_high_er_document-cn.md`（表、字段、关系、生成规则）。本文档假设你已经读过这两份。

---

## 如何使用本文档

这份文档是教学型的。设想场景：你是 Crestline 数据团队的新实习生，已经读完业务背景和 ER 文档，经理把这 20 条查询丢给你说"这周把它们做一遍"。这份文档就是手把手带你做。

**每条查询固定有五段**，照着读你既能学会写、也能学会用：

1. **业务背景** — 谁在问、为什么问、答案要拿去做什么决定、为什么现在急着要。把查询绑回到公司里某个真实的人和某个真实的决定。
2. **类别 / 难度 / 业务角色** — 三个标签：SQL 类别（聚合、窗口函数、跨域 Join……）、难度（Basic / Intermediate / Advanced）、提问的角色。
3. **解题思路** — 在你看 SQL 之前，先讲清楚思路：要碰哪些表、join 怎么搭（哪里必须 LEFT JOIN、哪里会 fan-out 重复计数）、聚合的粒度（一行输出代表什么）、为什么用 CTE / 窗口函数、SQLite 有什么坑。这一段是"自己动手前先想明白"的部分。
4. **SQL** — 查询本身，用 SQLite 3.x 语法，在生成的 `.sqlite` 上验证过。日期都用字面量 `'2026-06-05'`。
5. **预期结果 + 业务结论** — 结果长什么样（几行几列、各列含义、关键数值量级），以及**拿到数之后分析师下一步该做什么**。跑出查询只是分析的开始，不是结束。

**每条查询都能追溯到业务背景文档里的某个业务问题**（定价、agent 业绩、市场温度、机会发现、预测与现金流、客户匹配与数据质量）。文档末尾有"业务问题 → 查询"映射表。

**SQL 是用来读和学的，不只是拿来跑的**。解题思路解释了"为什么这样写"，建议先读思路、自己想一遍怎么写，再对照 SQL。

---

## 查询索引

| # | 标题 | 业务角色 | 类别 | 难度 |
|---|-------|---------------|----------|------------|
| 1 | 按 market 的月度成交量 | 高管 | 聚合 | Basic |
| 2 | 按 ZIP × 房型的中位成交价 | 分析师 | 窗口函数 | Intermediate |
| 3 | GCI 前 10 名 Agent（trailing 12 个月） | 经理 | Join + 聚合 | Basic |
| 4 | 按市场温度的 Days-on-Market 分布 | 分析师 | 聚合 | Basic |
| 5 | 需要关注的陈旧 Active Listings | 运营 | 过滤 + 日期 | Intermediate |
| 6 | 销量同比变化 | 高管 | 窗口函数 | Intermediate |
| 7 | Agent 活动到成交率漏斗 | 经理 | CTE + Join | Advanced |
| 8 | 买方-Listing 匹配候选 | 运营 | Join + 过滤 | Intermediate |
| 9 | 按 market 的 Sale-to-List 比率趋势 | 分析师 | 日期聚合 | Intermediate |
| 10 | Office 业绩计分卡 | 经理 | 多 Join 聚合 | Intermediate |
| 11 | 降价次数最多的 Listings | 分析师 | 子查询 | Intermediate |
| 12 | 抵押贷款利率 vs 成交量相关性 | 分析师 | 跨域 Join | Advanced |
| 13 | 销售管道按 Stage 的速率 | 经理 | 聚合 | Basic |
| 14 | 失单原因分析 | 经理 | 聚合 + 过滤 | Basic |
| 15 | Agent 资历 vs 佣金收入 | 分析师 | CTE + 日期计算 | Advanced |
| 16 | 重复 Contact 检测 | 运营 | 自连接 + GROUP BY | Intermediate |
| 17 | 成交价高于 Zillow ZHVI 的房产 | 分析师 | 跨域 Join | Advanced |
| 18 | 未来 30 天佣金 Payout 预测 | 财务 | 过滤 + 聚合 | Basic |
| 19 | 在售 Listing 的买方需求压力 | 运营 | Join + 聚合 | Intermediate |
| 20 | Crestline 按 Zip 的市场份额趋势 | 高管 | 窗口函数 | Advanced |

---

## 查询详情

### Query 1：按 Market 的月度成交量

**业务背景：**
Sarah Mitchell（运营 VP）每周领导层会议都用同一张图开场：在 Crestline 跟踪的 MLS 市场，过去 12 个月每月成交多少套房子，按 market 拆分？"2024 比 2023 跌 28%"的叙事就是从这条查询里来的，也是新 Market Pulse dashboard 必须最先做对的事。如果这个数错了，其他分析都没意义。

**类别：** 聚合
**难度：** Basic
**业务角色：** 高管

**解题思路：**
成交事件在 `mls_sold_transaction`，但它本身不知道属于哪个 market —— 地理信息挂在 property 上。所以要从 sold 一路 join 上去：sold → `mls_listing`（拿 PROPERTY_ID）→ `mls_property`（拿 zip_id）→ `geo_zip_code` → `geo_city` → `geo_county` → `geo_market`。时间窗口用 `CLOSE_DT >= '2025-07-01'` 取过去 12 个月，月份用 `strftime('%Y-%m', CLOSE_DT)` 切桶。按 market_code + year_month 分组，一行输出 = 一个 market 的一个月；不需要窗口函数，一次 GROUP BY 搞定，GTV 用 `SUM(SALE_PRICE)`。

```sql
SELECT
    m.market_code,
    strftime('%Y-%m', s.CLOSE_DT) AS year_month,
    COUNT(*) AS sold_count,
    ROUND(SUM(s.SALE_PRICE) / 1e6, 1) AS gtv_millions
FROM mls_sold_transaction s
JOIN mls_listing l ON s.LISTING_ID = l.LISTING_ID
JOIN mls_property p ON l.PROPERTY_ID = p.PROPERTY_ID
JOIN geo_zip_code z ON p.zip_id = z.zip_id
JOIN geo_city ci ON z.city_id = ci.city_id
JOIN geo_county co ON ci.county_id = co.county_id
JOIN geo_market m ON co.market_id = m.market_id
WHERE s.CLOSE_DT >= date('2025-07-01')
GROUP BY m.market_code, year_month
ORDER BY year_month, m.market_code;
```

**预期结果：**
~36 行（12 月 × 3 market）。Bay Area GTV 最高，PNW 最低。2025-26 相对 2024 谷底应有小幅回升。用于驱动高管头部 KPI。

---

### Query 2：按 ZIP × 房型的中位成交价

**业务背景：**
"94102 三居室 condo 这季度中位价多少？" — 这是 agent 问得最多的问题。Emily Zhang 的分析师团队目前靠 ad-hoc notebook 回答。Market Pulse dashboard 的下钻视图需要对每个 ZIP × property-type 单元格都算这个数，NL Query 层在 agent 输入自然语言版本时也得能产出等价 SQL。

**类别：** 窗口函数
**难度：** Intermediate
**业务角色：** 分析师

**解题思路：**
SQLite 没有内置 `median()`，所以中位数要手算：在每个 `(zip5, PROPERTY_TYPE)` 分区里用 `ROW_NUMBER() OVER (... ORDER BY SALE_PRICE)` 给成交价排序，同时用 `COUNT(*) OVER (...)` 拿到分区总数，最后挑出排在正中间那一行（`rn = (cnt+1)/2`）。这就是为什么必须用窗口函数而不是简单 GROUP BY。先在 CTE `ranked` 里把排名和计数算好，主查询只做筛选。一行输出 = 一个 zip×房型 的中位价 + 样本数；`n_sold < 5` 的格子在 dashboard 上要标低置信度。

```sql
WITH ranked AS (
    SELECT
        z.zip5,
        p.PROPERTY_TYPE,
        s.SALE_PRICE,
        ROW_NUMBER() OVER (PARTITION BY z.zip5, p.PROPERTY_TYPE ORDER BY s.SALE_PRICE) AS rn,
        COUNT(*) OVER (PARTITION BY z.zip5, p.PROPERTY_TYPE) AS cnt
    FROM mls_sold_transaction s
    JOIN mls_listing l ON s.LISTING_ID = l.LISTING_ID
    JOIN mls_property p ON l.PROPERTY_ID = p.PROPERTY_ID
    JOIN geo_zip_code z ON p.zip_id = z.zip_id
    WHERE s.CLOSE_DT >= date('2026-01-01')
      AND s.CLOSE_DT <  date('2026-07-01')
)
SELECT zip5, PROPERTY_TYPE, SALE_PRICE AS median_price, cnt AS n_sold
FROM ranked
WHERE rn = (cnt + 1) / 2
ORDER BY zip5, PROPERTY_TYPE;
```

**预期结果：**
~180 行（60 zip × 约 3 个数据足够的房型）。每个单元格显示中位成交价 + 样本数。`n_sold < 5` 的单元格在 dashboard 上应标记为低置信度。

---

### Query 3：GCI 前 10 名 Agent（Trailing 12 个月）

**业务背景：**
Rachel Torres（Bay Area Regional Manager）季度跑一次"总裁俱乐部"排名。Agent Scorecard dashboard 必须能呈现过去 12 个月的 top earners — Crestline 给公司 top 10 发奖金，这个名单直接驱动薪酬。这条查询也嵌入了自动化的周报，发给所有 manager。

**类别：** Join + 聚合
**难度：** Basic
**业务角色：** 经理

**解题思路：**
GCI 是把佣金明细按 agent 加总。从 `crm_commission_split` 出发（佣金落在这张表），join `crm_agent` 拿姓名/tier、join `crm_office` 拿办公室。`Payout_Date__c >= date('2026-06-05','-12 months')` 限定过去 12 个月。按 agent 分组，`SUM(Agent_Take__c)` 是 GCI，`COUNT(DISTINCT Transaction_Id__c)` 数成交笔数（用 DISTINCT 是因为 co-list 会让一笔交易出现多条 split）。排序取 top 10。注意这里是 **trailing 12 个月**，和 Query 15 的全期累计口径不同，金额会小一截。

```sql
SELECT
    a.Id              AS agent_id,
    a.First_Name__c || ' ' || a.Last_Name__c AS agent_name,
    a.Tier__c,
    o.Name            AS office,
    COUNT(DISTINCT cs.Transaction_Id__c) AS deal_count,
    ROUND(SUM(cs.Agent_Take__c), 0)      AS gci_usd
FROM crm_commission_split cs
JOIN crm_agent a ON cs.Agent_Id__c = a.Id
JOIN crm_office o ON a.Office_Id__c = o.Id
WHERE cs.Payout_Date__c >= date('2026-06-05', '-12 months')
GROUP BY a.Id
ORDER BY gci_usd DESC
LIMIT 10;
```

**预期结果：**
10 行，全部（或几乎全部）SENIOR 等级、入职日 2018-2020（tenure-weighted Pareto 的效果）。大致范围：单一 top earner $1.4M-$2.2M；其余 $250K-$900K。查询依赖 `crm_commission_split`（其 `Agent_Id__c` 设置为每笔交易的 opportunity owner）与 `crm_agent`、`crm_office` 关联。注意：**本查询过滤的是过去 12 个月**；如果想要每个 agent 全期累计 GCI，看 Query 15（数值是这里的 ~3-4 倍，因为窗口覆盖 3.4 年）。

---

### Query 4：按市场温度的 Days-on-Market 分布

**业务背景：**
竞争力定位 AI agent（Module 4）需要按市场温度校准 DOM baseline 来标记陈旧 listing。这条查询给 John Doe 提供分布，AI agent 的"stale listing"阈值（DOM > 中位数 × 1.5）就是基于此计算的。同时也是数据质量冒烟测试：HOT zip 的 DOM 必须比 COOL zip 短。

**类别：** 聚合
**难度：** Basic
**业务角色：** 分析师

**解题思路：**
这题验证"市场越热卖得越快"。只需要 `mls_listing` join `mls_property` join `geo_zip_code` 拿到温度标签，过滤 `STATUS_CD='SLD'`（只看真正成交的），按 `temperature` 分组算 DOM 的 avg/min/max。一行输出 = 一个温度档（共 3 行）。不需要 join 成交表，因为 DOM 就在 listing 上。如果结果里 HOT 的平均 DOM 不是明显小于 COOL，说明生成器漂移了——这条查询也是数据质量冒烟测试。

```sql
SELECT
    z.temperature,
    COUNT(*)                       AS n_sold,
    ROUND(AVG(l.DOM), 1)           AS avg_dom,
    MIN(l.DOM)                     AS min_dom,
    MAX(l.DOM)                     AS max_dom
FROM mls_listing l
JOIN mls_property p ON l.PROPERTY_ID = p.PROPERTY_ID
JOIN geo_zip_code z ON p.zip_id = z.zip_id
WHERE l.STATUS_CD = 'SLD'
GROUP BY z.temperature
ORDER BY avg_dom;
```

**预期结果：**
3 行。HOT zip 平均 DOM ~13 天，STABLE ~41，COOL ~87。如果顺序错了，说明数据生成器漂移了。

---

### Query 5：需要关注的陈旧 Active Listings

**业务背景：**
Rachel Torres 每天早上问："我手下 agent 哪些 active listing 在市场上挂太久了？" Market Pulse dashboard 的"Stale Listings" widget 显示这个列表，按"相对 zip 中位 DOM 超出多少"排序。名字反复出现在这个列表上的 agent 会被 Slack 提醒考虑降价或重新营销。

**类别：** 过滤 + 日期算术
**难度：** Intermediate
**业务角色：** 运营

**解题思路：**
"陈旧"是相对概念，要先有每个 zip 的 DOM 基准。CTE `zip_median_dom` 用该 zip 已成交 listing 的 `AVG(DOM)` 作为中位数的近似基准（SQLite 没有 median，用 avg 代理）。主查询只看 `STATUS_CD='ACT'` 的在售房源，用 `julianday('2026-06-05') - julianday(LIST_DT)` 算它已经挂了多少天，再和基准 × 1.5 比较。一行输出 = 一个超期在售 listing。CTE 在这里值得用，因为基准要按 zip 复用；结果集中在 COOL zip。

```sql
WITH zip_median_dom AS (
    SELECT
        z.zip_id,
        ROUND(AVG(l.DOM), 0) AS median_dom_proxy
    FROM mls_listing l
    JOIN mls_property p ON l.PROPERTY_ID = p.PROPERTY_ID
    JOIN geo_zip_code z ON p.zip_id = z.zip_id
    WHERE l.STATUS_CD = 'SLD'
    GROUP BY z.zip_id
)
SELECT
    l.MLS_NUMBER,
    p.STREET_NUM || ' ' || p.STREET_NAME AS address,
    p.CITY,
    z.zip5,
    l.LIST_PRICE,
    CAST(julianday('2026-06-05') - julianday(l.LIST_DT) AS INTEGER) AS days_active,
    zmd.median_dom_proxy
FROM mls_listing l
JOIN mls_property p ON l.PROPERTY_ID = p.PROPERTY_ID
JOIN geo_zip_code z ON p.zip_id = z.zip_id
JOIN zip_median_dom zmd ON z.zip_id = zmd.zip_id
WHERE l.STATUS_CD = 'ACT'
  AND CAST(julianday('2026-06-05') - julianday(l.LIST_DT) AS INTEGER) > zmd.median_dom_proxy * 1.5
ORDER BY days_active DESC
LIMIT 25;
```

**预期结果：**
~10-30 个陈旧 listing，集中在 COOL zip。名字反复出现的 agent 标记为需要培训。

---

### Query 6：销量同比变化

**业务背景：**
董事会季度投资人 deck 总用这张图开场：每个 market YoY 趋势如何？这条查询计算图表的底层数据。Crestline 的叙事 — 2024 跌 22-28% 然后复苏 — 必须能从这条查询精确重现，让领导层和投资人看到一致的数字。

**类别：** 窗口函数
**难度：** Intermediate
**业务角色：** 高管

**解题思路：**
董事会要看每个 market 的 YoY 趋势。先在 CTE `yearly` 里把成交量按 market + 年份（`strftime('%Y')`）聚合好，再用 `LAG(sold_count) OVER (PARTITION BY market_code ORDER BY year)` 取出同一 market 的去年值，相减除以去年值得到 yoy_pct。窗口函数 LAG 是这里的关键——它让"今年 vs 去年"在同一行里就能算，比自连接干净得多。一行输出 = 一个 market 的一年；2024 行应显示 -22% 到 -28%。

```sql
WITH yearly AS (
    SELECT
        m.market_code,
        CAST(strftime('%Y', s.CLOSE_DT) AS INTEGER) AS year,
        COUNT(*) AS sold_count,
        ROUND(SUM(s.SALE_PRICE) / 1e6, 1) AS gtv_millions
    FROM mls_sold_transaction s
    JOIN mls_listing l ON s.LISTING_ID = l.LISTING_ID
    JOIN mls_property p ON l.PROPERTY_ID = p.PROPERTY_ID
    JOIN geo_zip_code z ON p.zip_id = z.zip_id
    JOIN geo_city ci ON z.city_id = ci.city_id
    JOIN geo_county co ON ci.county_id = co.county_id
    JOIN geo_market m ON co.market_id = m.market_id
    GROUP BY m.market_code, year
)
SELECT
    market_code,
    year,
    sold_count,
    LAG(sold_count) OVER (PARTITION BY market_code ORDER BY year) AS prior_year,
    ROUND(100.0 * (sold_count - LAG(sold_count) OVER (PARTITION BY market_code ORDER BY year))
          / LAG(sold_count) OVER (PARTITION BY market_code ORDER BY year), 1) AS yoy_pct
FROM yearly
ORDER BY market_code, year;
```

**预期结果：**
12 行（3 market × 4 年）。2024 在所有 market 应显示 -22% 到 -28%。2025 应显示部分复苏。

---

### Query 7：Agent 活动到成交率漏斗

**业务背景：**
Marcus Rivera（Tech Lead）怀疑有些资深 agent 成交多不是因为他们 close 得更好，而是因为他们的外联次数多 5 倍。这条查询计算 per-agent 漏斗：activities → opportunities → closed wons，让 manager 判断 agent 的生产力问题是在漏斗顶端（活动量）还是底端（转化率）。用在 1-on-1 上。

**类别：** CTE + 多 Join
**难度：** Advanced
**业务角色：** 经理

**解题思路：**
这题要把"活动量"和"转化率"拆开看，所以分两个 CTE：`activity_stats` 数每个 agent 过去 12 个月的活动数，`opp_stats` 数机会数和其中 Closed Won 数。再把两个 CTE 用 LEFT JOIN 挂回 `crm_agent`——必须 LEFT JOIN，否则零活动或零机会的 agent 会整行消失，漏斗就不完整。用 COALESCE 把 NULL 补成 0，close_rate 在分母为 0 时返回 NULL。`ORDER BY closed_won_12m IS NULL, closed_won_12m DESC` 是把没有成交的 agent 排到最后的小技巧。一行 = 一个 active agent 的完整漏斗。

```sql
WITH activity_stats AS (
    SELECT Agent_Id__c, COUNT(*) AS n_activities
    FROM crm_agent_activity
    WHERE Activity_Date__c >= date('2026-06-05', '-12 months')
    GROUP BY Agent_Id__c
),
opp_stats AS (
    SELECT Owner_Agent_Id__c AS agent_id,
           COUNT(*) AS n_opps,
           SUM(CASE WHEN StageName = 'Closed Won' THEN 1 ELSE 0 END) AS n_won
    FROM crm_opportunity
    WHERE CreatedDate >= date('2026-06-05', '-12 months')
    GROUP BY Owner_Agent_Id__c
)
SELECT
    a.First_Name__c || ' ' || a.Last_Name__c AS agent_name,
    a.Tier__c,
    COALESCE(act.n_activities, 0) AS activities_12m,
    COALESCE(o.n_opps, 0)         AS opportunities_12m,
    COALESCE(o.n_won, 0)          AS closed_won_12m,
    CASE WHEN o.n_opps > 0
         THEN ROUND(100.0 * o.n_won / o.n_opps, 1)
         ELSE NULL END AS close_rate_pct
FROM crm_agent a
LEFT JOIN activity_stats act ON a.Id = act.Agent_Id__c
LEFT JOIN opp_stats o ON a.Id = o.agent_id
WHERE a.IsActive__c = 1
ORDER BY closed_won_12m IS NULL, closed_won_12m DESC
LIMIT 20;
```

**预期结果：**
20 个 active agent 的完整漏斗。Top performer 应同时展示高活动量 AND 高成交率；中等 tier 通常活动量还可以但成交率较低。

---

### Query 8：买方-Listing 匹配候选

**业务背景：**
房源-客户匹配功能（Module 3 REQ-12）在 embedding-based recommender 构建之前需要一个仅靠 SQL 的快速基线。对每个有偏好的 active 买家，找符合的 listing：价格范围、卧室数、偏好 ZIP。这条查询也成为 Streamlit recommender 的测试 fixture — 其结果是 embedding 模型必须重现的"显然正确"的匹配。

**类别：** Join + 过滤
**难度：** Intermediate
**业务角色：** 运营

**解题思路：**
对每个有偏好的买家找匹配 listing。从 `crm_contact` 出发，按 `Preferred_Zip__c = property.ZIP` 且 `Preferred_Bed_Count__c = property.BED_COUNT` join `mls_property`，再 join `mls_listing` 限定 `STATUS_CD='ACT'` 且挂牌价落在买家预算区间内。这里故意用 INNER JOIN（不是 LEFT）——只要真正配上的对，没匹配的不要。一行输出 = 一个"买家 × 候选 listing"配对。坑：ZIP 是字符串匹配，~5% 的 ZIP+4 脏数据会匹配不上（这正是下游要清洗的），所以这只是 SQL 基线，embedding 模型要能召回更多。

```sql
SELECT
    c.Id              AS contact_id,
    c.FirstName || ' ' || c.LastName AS buyer_name,
    c.Preferred_Min_Price__c,
    c.Preferred_Max_Price__c,
    c.Preferred_Bed_Count__c,
    c.Preferred_Zip__c,
    l.MLS_NUMBER,
    l.LIST_PRICE,
    p.BED_COUNT,
    p.ZIP
FROM crm_contact c
JOIN mls_property p
  ON p.ZIP = c.Preferred_Zip__c
 AND p.BED_COUNT = c.Preferred_Bed_Count__c
JOIN mls_listing l
  ON l.PROPERTY_ID = p.PROPERTY_ID
 AND l.STATUS_CD = 'ACT'
 AND l.LIST_PRICE BETWEEN c.Preferred_Min_Price__c AND c.Preferred_Max_Price__c
WHERE c.Contact_Type__c IN ('Buyer', 'Both')
  AND c.Preferred_Min_Price__c IS NOT NULL
ORDER BY c.Id, l.LIST_PRICE
LIMIT 50;
```

**预期结果：**
买家-listing 配对列表，每条都满足所有标准。大部分买家有 0-3 个匹配；少数有很多。Recommender 用这些作为"必须包含"集合。

---

### Query 9：按 Market 的 Sale-to-List 比率趋势（季度）

**业务背景：**
SLR 是市场升温/降温的最佳前瞻指标。SLR 涨到 1.0 以上时正在出现 bidding war；跌到 0.97 以下时卖家在让步。竞争力定位 AI agent 把每个 market 的 SLR 趋势作为关键输入之一。这条查询也喂给 Market Pulse dashboard 的"市场温度"仪表。

**类别：** 日期聚合
**难度：** Intermediate
**业务角色：** 分析师

**解题思路：**
SLR 趋势按季度看。和 Query 1 一样从 sold 一路 join 到 `geo_market`，但这次把时间切成季度：用 `strftime('%Y')` 拼上 `'-Q' || ((月份+2)/3)` 手动算季度号。按 market + quarter 分组，`AVG(LIST_TO_SALE_RATIO)` 是该季度该 market 的平均 SLR。一行 = 一个 market 的一个季度。Bay Area 应持续最高（竞争最激烈），所有 market 在 1.00 附近小幅波动。

```sql
SELECT
    m.market_code,
    strftime('%Y', s.CLOSE_DT) || '-Q' || ((CAST(strftime('%m', s.CLOSE_DT) AS INTEGER) + 2) / 3) AS quarter,
    COUNT(*) AS n_sold,
    ROUND(AVG(s.LIST_TO_SALE_RATIO), 4) AS avg_slr
FROM mls_sold_transaction s
JOIN mls_listing l ON s.LISTING_ID = l.LISTING_ID
JOIN mls_property p ON l.PROPERTY_ID = p.PROPERTY_ID
JOIN geo_zip_code z ON p.zip_id = z.zip_id
JOIN geo_city ci ON z.city_id = ci.city_id
JOIN geo_county co ON ci.county_id = co.county_id
JOIN geo_market m ON co.market_id = m.market_id
GROUP BY m.market_code, quarter
ORDER BY m.market_code, quarter;
```

**预期结果：**
~42 行（3 market × 14 季度）。Bay Area 应持续是最高 SLR（竞争最激烈）。所有 market 应在 1.00 附近波动，季度变化幅度 ~3-4 分。

---

### Query 10：Office 业绩计分卡

**业务背景：**
每个月末，Sarah Mitchell 要看 office-by-office 计分卡：每个办公室的 agent 数、成交数、GCI、平均成交价。驱动扩张决策（要不要在 Bellevue 再开一家？）和人员规划。目前由 Emily 手工出，这条查询是替代她 Excel 的真相来源。

**类别：** 多 Join 聚合
**难度：** Intermediate
**业务角色：** 经理

**解题思路：**
office 计分卡要把"人、单、钱"凑到一行。以 `crm_office` 为主表，LEFT JOIN active `crm_agent`、再 LEFT JOIN 过去 12 个月的 `crm_commission_split`、再 LEFT JOIN `crm_transaction` 拿成交价。全程 LEFT JOIN 是为了让暂时没成交的 office 也留在结果里。聚合时用 `COUNT(DISTINCT a.Id)` 和 `COUNT(DISTINCT cs.Transaction_Id__c)`——因为一个 office 多个 agent、一笔交易多条 split，多重 join 会 fan-out，不去重就会重复计数。一行 = 一个 office。

```sql
SELECT
    o.Name AS office,
    COUNT(DISTINCT a.Id) AS agent_count,
    COUNT(DISTINCT cs.Transaction_Id__c) AS deal_count,
    ROUND(SUM(cs.Agent_Take__c + cs.Company_Take__c) / 1e6, 2) AS gross_commission_millions,
    ROUND(AVG(t.Sale_Price__c) / 1000, 0) AS avg_sale_price_k
FROM crm_office o
LEFT JOIN crm_agent a ON a.Office_Id__c = o.Id AND a.IsActive__c = 1
LEFT JOIN crm_commission_split cs ON cs.Agent_Id__c = a.Id
    AND cs.Payout_Date__c >= date('2026-06-05', '-12 months')
LEFT JOIN crm_transaction t ON cs.Transaction_Id__c = t.Id
GROUP BY o.Id
ORDER BY gross_commission_millions IS NULL, gross_commission_millions DESC;
```

**预期结果：**
8 行（每办公室一行）。Bay Area office 因价格点更高通常 GCI 领先。查询揭露哪些 office 相对其 agent 数表现超预期。

---

### Query 11：降价次数最多的 Listings

**业务背景：**
降价 3 次以上的 listing 是初始定价错误的强信号。Emily 想知道哪些 Crestline-listed 房产反复出现这种情况，以便复盘背后的定价方法论。这也喂给 AI agent 的"overpriced 检测器"（Module 4 REQ-13）。

**类别：** 子查询
**难度：** Intermediate
**业务角色：** 分析师

**解题思路：**
降价次数多的 listing 是初始定价偏高的信号。降价记录在 `mls_listing_event_history` 里、`EVENT_TYPE='PRICE_CHANGE'`。这里用相关子查询：对每个 listing 数它有多少条 PRICE_CHANGE 事件，再用 `WHERE (子查询) >= 3` 过滤出降价 ≥3 次的。也可以写成 join + group by + having，但子查询读起来更直白。按降价次数、再按 DOM 排序。一行 = 一个反复降价的 listing；它们多数同时 DOM 偏高，印证"反复降价 = 卖得慢"。

```sql
SELECT
    l.MLS_NUMBER,
    l.LIST_PRICE AS original_price,
    (SELECT COUNT(*) FROM mls_listing_event_history h
     WHERE h.LISTING_ID = l.LISTING_ID AND h.EVENT_TYPE = 'PRICE_CHANGE') AS n_reductions,
    l.STATUS_CD,
    l.DOM
FROM mls_listing l
WHERE (SELECT COUNT(*) FROM mls_listing_event_history h
       WHERE h.LISTING_ID = l.LISTING_ID AND h.EVENT_TYPE = 'PRICE_CHANGE') >= 3
ORDER BY n_reductions DESC, l.DOM DESC
LIMIT 20;
```

**预期结果：**
~20 个降价 3 次的 listing（生成器最大值）。大部分应同时有较高 DOM，确认"反复降价"与"卖得慢"之间的相关性。

---

### Query 12：抵押贷款利率 vs 销售量相关性

**业务背景：**
CEO 那句"高利率杀死了 2024 的交易量"需要证据。这条查询按月把 Freddie Mac 抵押数据与成交量 join 起来，让分析师可视化检查反向关系。也是一个跨域完整性检查，验证生成器里嵌入的宏观叙事确实反映在数据里。

**类别：** 跨域 Join + CTE
**难度：** Advanced
**业务角色：** 分析师

**解题思路：**
要把成交量和利率按月对齐，但它们在不同的域、不同的粒度（成交是逐笔，利率是逐周）。所以分别用两个 CTE 把它们都压成"每月一行"：`monthly_sold` 按 `strftime('%Y-%m', CLOSE_DT)` 数成交量，`monthly_rate` 按月对 `Rate_30Y_Fixed` 求平均。再用 year_month 做 join。这是一次跨域（MLS × external）连接。一行 = 一个月；画成双轴线图能看到利率在 2023 末抬头、成交量 2024 下沉的反向关系。

```sql
WITH monthly_sold AS (
    SELECT
        strftime('%Y-%m', CLOSE_DT) AS year_month,
        COUNT(*) AS sold_count
    FROM mls_sold_transaction
    GROUP BY year_month
),
monthly_rate AS (
    SELECT
        strftime('%Y-%m', Week_End_Date) AS year_month,
        AVG(Rate_30Y_Fixed) AS avg_rate
    FROM ext_freddie_mac_mortgage_rate
    GROUP BY year_month
)
SELECT
    s.year_month,
    s.sold_count,
    ROUND(r.avg_rate, 3) AS avg_30y_rate
FROM monthly_sold s
JOIN monthly_rate r ON s.year_month = r.year_month
ORDER BY s.year_month;
```

**预期结果：**
~42 个月度行。可视化为双轴线图：利率上升进入 2023 末期，成交量在 2024 下沉。

---

### Query 13：销售管道按 Stage 的速率

**业务背景：**
Rachel Torres 想知道机会卡在哪里。统计每个管道 stage 当前有多少机会能暴露瓶颈 — 比如太多"Under Contract"但成交少，意味着 deal 被 inspection 问题搞砸了，促使 manager 干预。在 Agent Scorecard 上以漏斗图形式呈现。

**类别：** 聚合
**难度：** Basic
**业务角色：** 经理

**解题思路：**
看管道在哪一段卡住。只用 `crm_opportunity` 一张表，按 `StageName` 分组数机会数、算平均/总金额，限定过去 6 个月（`CreatedDate`）。难点不在聚合，而在排序：stage 是文字，默认排序没有业务意义，所以用 `ORDER BY CASE StageName WHEN 'Lead' THEN 1 ...` 把它按漏斗顺序强制排好。一行 = 一个 stage；正常漏斗应从 Lead 到 Closed Won 逐级收窄。

```sql
SELECT
    StageName,
    COUNT(*)                  AS opp_count,
    ROUND(AVG(Amount) / 1000, 0) AS avg_amount_k,
    ROUND(SUM(Amount) / 1e6, 1)  AS total_pipeline_millions
FROM crm_opportunity
WHERE CreatedDate >= date('2026-06-05', '-6 months')
GROUP BY StageName
ORDER BY
    CASE StageName
        WHEN 'Lead' THEN 1 WHEN 'Qualified' THEN 2 WHEN 'Showing' THEN 3
        WHEN 'Offer' THEN 4 WHEN 'Under Contract' THEN 5
        WHEN 'Closed Won' THEN 6 WHEN 'Closed Lost' THEN 7
    END;
```

**预期结果：**
7 行按管道顺序。漏斗从 Lead → Closed Won 如预期收窄。

---

### Query 14：失单原因分析

**业务背景：**
我们为什么在丢 deal？Sarah 想要 lost opportunity 的 top 原因，让公司系统性解决每一个（比如"被竞品赢走"占多数 = 市场定位问题；"贷款下不来"占多数 = 合作银行问题）。

**类别：** 聚合 + 过滤
**难度：** Basic
**业务角色：** 经理

**解题思路：**
我们为什么丢单。过滤 `StageName='Closed Lost'` 且 `Lost_Reason__c` 非空，按原因分组数频次、算平均金额，降序排。一张表、一次 GROUP BY，Basic。一行 = 一个失单原因。结论直接指向行动："被竞品赢走"占多数是市场定位问题，"贷款下不来"占多数是合作银行问题。

```sql
SELECT
    Lost_Reason__c,
    COUNT(*) AS lost_count,
    ROUND(AVG(Amount) / 1000, 0) AS avg_lost_amount_k
FROM crm_opportunity
WHERE StageName = 'Closed Lost'
  AND Lost_Reason__c IS NOT NULL
GROUP BY Lost_Reason__c
ORDER BY lost_count DESC;
```

**预期结果：**
~6 行原因按频率排序。用于根因行动规划。

---

### Query 15：Agent 资历 vs 佣金收入

**业务背景：**
HR 想验证"资历越深的 agent 收入越高"这一假设，再批准新的 tier-based 佣金结构。这条查询把 active agent 按年限分桶，计算他们的平均 GCI，用经验数据展示这层关系。驱动薪酬政策。

**类别：** CTE + 日期计算
**难度：** Advanced
**业务角色：** 分析师

**解题思路：**
验证"资历越深收入越高"。先在 CTE `agent_gci` 里对每个 active agent 算两样东西：用 `julianday` 差除以 365.25 得到 tenure_years，用 `SUM(Agent_Take__c)` 得到**全期累计** GCI（注意：这里没有 12 个月过滤，所以金额是 Query 3 的 3-4 倍）。主查询用 CASE 把 tenure 分桶（0-1/2-3/4-5/6+ 年），按桶算 avg/max GCI。一行 = 一个 tenure 桶。均值应单调上升，且 6+ 年桶的 max 远超其它桶——这是 tenure-weighted 派单 + tier 分成两层效应叠加的结果。

```sql
WITH agent_gci AS (
    SELECT
        a.Id,
        CAST((julianday('2026-06-05') - julianday(a.Hire_Date__c)) / 365.25 AS INTEGER) AS tenure_years,
        a.Tier__c,
        COALESCE(SUM(cs.Agent_Take__c), 0) AS gci
    FROM crm_agent a
    LEFT JOIN crm_commission_split cs ON cs.Agent_Id__c = a.Id
    WHERE a.IsActive__c = 1
    GROUP BY a.Id
)
SELECT
    CASE
        WHEN tenure_years < 2 THEN '0-1 yr'
        WHEN tenure_years < 4 THEN '2-3 yr'
        WHEN tenure_years < 6 THEN '4-5 yr'
        ELSE '6+ yr'
    END AS tenure_bucket,
    COUNT(*) AS agent_count,
    ROUND(AVG(gci), 0) AS avg_gci,
    ROUND(MAX(gci), 0) AS max_gci
FROM agent_gci
GROUP BY tenure_bucket
ORDER BY MIN(tenure_years);
```

**预期结果：**
4 个 tenure 桶 — 这里是**每个 agent 全期累计 GCI**（不像 Query 3 是 12 个月），所以绝对金额比 Q3 报的大约高 3-4 倍。seed=42 生成的大致区间：

| 桶 | 平均 GCI | 最大 GCI |
|---|---|---|
| 0-1 年 | ~$150-200K | ~$300-450K |
| 2-3 年 | ~$220-280K | ~$350-450K |
| 4-5 年 | ~$250-330K | ~$500-650K |
| 6+ 年 | **~$550-700K** | **~$3M-$4M** |

规律：均值单调上升 + `max GCI` 拉开大差距（6+ 年的最大值是 0-1 年最大值的 ~8-10 倍）。这是两层效应叠加 — (a) tenure-weighted opportunity Pareto 让资深 agent 拿更多 deal；(b) tier 分阶的 `Commission_Split_Pct__c` 让他们从每笔 deal 拿到更大比例。两者结合，用经验数据验证了 tier 薪酬结构。

---

### Query 16：重复 Contact 检测

**业务背景：**
Crestline 的 CRM 多年累积了重复记录 — 同一个买家被不同 agent 在不同 open house 抓取。dbt staging 层在构建 Customer Intelligence Mart 之前必须去重。这条查询识别可能的重复（同 email + 不同 Id），方便合并。

**类别：** 自连接 / GROUP BY
**难度：** Intermediate
**业务角色：** 运营

**解题思路：**
CRM 多年累积重复 contact（同一买家被不同 agent 在不同 open house 抓到）。最简单的去重信号是 email 相同。按 `Email` 分组、`HAVING COUNT(*) > 1` 找出重复，用 `GROUP_CONCAT` 把这些记录的 Id 和姓名拼到一列里方便人工核对。一行 = 一个出现多次的 email。坑：先 `WHERE Email IS NOT NULL` 排除空邮箱，否则一堆 NULL 会被错误归并。`name_variants` 列里的拼写微差正是下游 dedup 逻辑要处理的。

```sql
SELECT
    Email,
    COUNT(*) AS occurrences,
    GROUP_CONCAT(Id, '; ') AS contact_ids,
    GROUP_CONCAT(FirstName || ' ' || LastName, ' | ') AS name_variants
FROM crm_contact
WHERE Email IS NOT NULL
GROUP BY Email
HAVING COUNT(*) > 1
ORDER BY occurrences DESC, Email
LIMIT 25;
```

**预期结果：**
~100-150 个 email 出现在多条 contact 记录里。`name_variants` 列显示拼写微差 — 正是去重逻辑要处理的情况。

---

### Query 17：成交价高于 Zillow ZHVI 的房产

**业务背景：**
竞争力定位 AI 把 Zillow ZHVI 作为市场级别公允价值 baseline。这条查询识别成交月份显著高于本 zip ZHVI 的房产 — 这些是"超市场价"成交，可能意味着 micro-market 火热或房产有特殊卖点。AI agent 用这个列表作为定价能力的正样本。

**类别：** 跨域 Join
**难度：** Advanced
**业务角色：** 分析师

**解题思路：**
找成交价显著高于 Zillow 公允价的房产。从 sold 一路 join 到 `geo_zip_code`，再跨域 join `ext_zillow_home_value_index`：关键是两个 join 条件——zip 对上、且月份对上。Zillow 是每月一行（月初日期），所以用 `date(CLOSE_DT, 'start of month')` 把成交日归一到月初再和 `zh.Date` 匹配。过滤 `SALE_PRICE > ZHVI * 1.15`，按超出比例降序。一行 = 一笔超市场价成交，绝大多数落在 HOT zip。

```sql
SELECT
    z.zip5,
    s.CLOSE_DT,
    s.SALE_PRICE,
    zh.ZHVI                                  AS zillow_zhvi,
    ROUND(100.0 * (s.SALE_PRICE - zh.ZHVI) / zh.ZHVI, 1) AS pct_above_zhvi
FROM mls_sold_transaction s
JOIN mls_listing l ON s.LISTING_ID = l.LISTING_ID
JOIN mls_property p ON l.PROPERTY_ID = p.PROPERTY_ID
JOIN geo_zip_code z ON p.zip_id = z.zip_id
JOIN ext_zillow_home_value_index zh
  ON zh.zip_id = z.zip_id
 AND zh.Date = date(s.CLOSE_DT, 'start of month')
WHERE s.SALE_PRICE > zh.ZHVI * 1.15
ORDER BY pct_above_zhvi DESC
LIMIT 25;
```

**预期结果：**
~25 笔比 ZHVI 高出 15%+ 的离群成交。绝大多数来自 HOT zip（94301、90210 等）。

---

### Query 18：未来 30 天佣金 Payout 预测

**业务背景：**
财务需要预测现金流出：未来 30 天有多少佣金要 payout、给谁？Treasury 用这个规划运营资金。Controller 每周跑一次，与 `crm_agent` join 出来组成 payroll 预览。

**类别：** 过滤 + 聚合
**难度：** Basic
**业务角色：** 财务

**解题思路：**
财务要预测未来 30 天的佣金现金流出。只看 `crm_commission_split`，过滤 `Payout_Date__c` 落在 `['2026-06-05', +30 天]`，按 payout 日期分组，分别加总给 agent 的钱和给公司的钱。一行 = 一个 payout 日。注意：payout 日是 close + 5-15 天的前瞻排程，所以这个窗口里看到的是 5 月底/6 月初成交的尾款，通常比较稀疏（10-20 行）。这是 Treasury 排运营资金用的。

```sql
SELECT
    cs.Payout_Date__c,
    COUNT(*) AS payout_count,
    ROUND(SUM(cs.Agent_Take__c), 0) AS total_to_agents,
    ROUND(SUM(cs.Company_Take__c), 0) AS total_to_company
FROM crm_commission_split cs
WHERE cs.Payout_Date__c BETWEEN date('2026-06-05') AND date('2026-06-05', '+30 days')
GROUP BY cs.Payout_Date__c
ORDER BY cs.Payout_Date__c;
```

**预期结果：**
未来 30 天的每日 payout 排程。财务团队用来确认银行账户资金水平。注意：数据集有效日期是 2026-06-05，这个 30 天向前窗口只会显示 5 月底 / 6 月初成交的 deal 的 payout — 通常是稀疏窗口（10-20 行）。如果换到成交更密集的时段（如 9 月初跑），自然会显示更密的 payout 排程。

---

### Query 19：在售 Listing 的买方需求压力

**业务背景：**
Module 4 第 6-8 步（机会识别，REQ-15）需要每个 listing 的**买方需求压力评分**，让 AI agent 能标记"高需求但定价稍偏高"（很多看房但没出价 — 暗示价格刚刚超 buyer 心理）vs"需求弱"（看房少 — 需要营销干预）。这条查询使用新的 `mls_listing_showing` 表（可与 `ext_zillow_market_temperature` 联合获得 context）计算每个 active listing 的需求快照。

**类别：** Join + 聚合
**难度：** Intermediate
**业务角色：** 运营

**解题思路：**
给每个在售 listing 打"买方需求压力"标签。以 `mls_listing`（`STATUS_CD='ACT'`）为主，LEFT JOIN `mls_listing_showing`——必须 LEFT JOIN，否则一次看房都没有的房源（正是 LOW_DEMAND）会被过滤掉。按 listing 分组，数 showings 总数、用 `SUM(CASE WHEN Resulted_In_Offer__c...)` 数 offer 数，再用一个 CASE 把它们翻译成 demand_signal（看房多但零 offer = 价格略高；看房极少 = 需营销）。`HAVING days_on_market > 7` 排掉刚挂出来的。一行 = 一个 active listing 的需求快照。

```sql
SELECT
    l.MLS_NUMBER,
    p.STREET_NUM || ' ' || p.STREET_NAME AS address,
    z.zip5,
    z.temperature                    AS zip_temperature,
    l.LIST_PRICE,
    CAST(julianday('2026-06-05') - julianday(l.LIST_DT) AS INTEGER) AS days_on_market,
    COUNT(s.SHOWING_ID)              AS total_showings,
    SUM(CASE WHEN s.Resulted_In_Offer__c = 1 THEN 1 ELSE 0 END) AS offers_received,
    CASE
        WHEN COUNT(s.SHOWING_ID) >= 5 AND SUM(CASE WHEN s.Resulted_In_Offer__c = 1 THEN 1 ELSE 0 END) = 0
            THEN 'HIGH_INTEREST_NO_OFFER (price slightly high?)'
        WHEN COUNT(s.SHOWING_ID) < 2
            THEN 'LOW_DEMAND (needs marketing intervention)'
        WHEN SUM(CASE WHEN s.Resulted_In_Offer__c = 1 THEN 1 ELSE 0 END) > 0
            THEN 'OFFERS_RECEIVED'
        ELSE 'NORMAL_FUNNEL'
    END AS demand_signal
FROM mls_listing l
JOIN mls_property p ON l.PROPERTY_ID = p.PROPERTY_ID
JOIN geo_zip_code z ON p.zip_id = z.zip_id
LEFT JOIN mls_listing_showing s ON s.LISTING_ID = l.LISTING_ID
WHERE l.STATUS_CD = 'ACT'
GROUP BY l.LISTING_ID
HAVING days_on_market > 7
ORDER BY days_on_market DESC, total_showings DESC
LIMIT 30;
```

**预期结果：**
最多 30 行（LIMIT 限制）— 按 days-on-market 降序的 active listing 及其需求快照。`demand_signal` 列直接喂给 AI agent 的推荐引擎：`HIGH_INTEREST_NO_OFFER` 是降价候选；`LOW_DEMAND` 需要改营销。去掉 LIMIT 可看到全集（通常 400-800 个 active listing）。

---

### Query 20：Crestline 按 Zip 的市场份额趋势（YoY）

**业务背景：**
CEO 给董事会的叙事（"我们在 HOT 子市场份额在增长"）目前是道听途说 — 没人真正算过 Crestline 在 MLS 挂牌库存中按 zip 跨年的实际份额。这条查询出 cohort：对每个 (zip × year)，所有挂牌中有多少比例是 Crestline 品牌的，YoY 变化多少？驱动办公室扩张和 agent 招聘的战略决策。

**类别：** 窗口函数
**难度：** Advanced
**业务角色：** 高管

**解题思路：**
算 Crestline 在每个 zip 跨年的挂牌份额。CTE `zip_year` 对每个 (zip, year) 数总挂牌数和其中 `IS_CRESTLINE_LISTING` 为真的数，份额 = crestline/total。主查询再用 `LAG(...) OVER (PARTITION BY zip5 ORDER BY year)` 取出去年的份额，相减得到 share_change_pts。窗口函数 LAG 让同比变化在一行里算出来。一行 = 一个 zip 的一年。关注 HOT zip 里份额持续上涨（正趋势）vs COOL zip 被竞品反超的地方。

```sql
WITH zip_year AS (
    SELECT
        z.zip5,
        z.temperature,
        CAST(strftime('%Y', l.LIST_DT) AS INTEGER) AS year,
        COUNT(*) AS total_listings,
        SUM(CASE WHEN l.IS_CRESTLINE_LISTING = 1 THEN 1 ELSE 0 END) AS crestline_listings
    FROM mls_listing l
    JOIN mls_property p ON l.PROPERTY_ID = p.PROPERTY_ID
    JOIN geo_zip_code z ON p.zip_id = z.zip_id
    WHERE l.LIST_DT >= '2023-01-01'
    GROUP BY z.zip5, z.temperature, year
)
SELECT
    zip5,
    temperature,
    year,
    total_listings,
    crestline_listings,
    ROUND(100.0 * crestline_listings / total_listings, 1) AS crestline_share_pct,
    ROUND(100.0 * crestline_listings / total_listings, 1)
      - LAG(ROUND(100.0 * crestline_listings / total_listings, 1))
          OVER (PARTITION BY zip5 ORDER BY year) AS share_change_pts
FROM zip_year
ORDER BY zip5, year;
```

**预期结果：**
~240 行（60 zip × 4 年）。`share_change_pts` 列显示 Crestline 挂牌份额的同比变化。关注 HOT zip 中 Crestline 持续增长份额（正趋势）vs COOL zip 中竞争对手反超的地方。

---

## 查询类别汇总

| 类别 | 数量 | 查询号 |
|----------|-------|---------------|
| 聚合 | 7 | 1, 3, 4, 13, 14, 18, 19 |
| Join 操作 | 3 | 8, 10, 19 |
| 窗口函数 | 3 | 2, 6, 20 |
| 日期/时间分析 | 3 | 5, 9, 12 |
| 子查询/CTE | 4 | 7, 11, 15, 17 |
| 模式/文本匹配 | 1 | 16 |

（注：有些查询会出现在多个类别 — 比如 Q19 既是 Join 也是聚合。汇总数大于 20。）

## 业务角色覆盖

| 角色 | 数量 | 查询号 |
|------|-------|---------------|
| 高管 / C-Level | 3 | 1, 6, 20 |
| 经理 | 5 | 3, 7, 10, 13, 14 |
| 分析师 | 7 | 2, 4, 9, 11, 12, 15, 17 |
| 运营 | 4 | 5, 8, 16, 19 |
| 财务 | 1 | 18 |

## 难度分布

| 难度 | 数量 | 查询号 |
|------------|-------|---------------|
| Basic | 6 | 1, 3, 4, 13, 14, 18 |
| Intermediate | 9 | 2, 5, 6, 8, 9, 10, 11, 16, 19 |
| Advanced | 5 | 7, 12, 15, 17, 20 |

## 业务问题 → 查询映射

每条查询都追溯到 `01-...business_context-cn.md` 第 5 节列出的业务问题。

| 业务问题 | 对应查询 |
|----------|----------|
| 1. 定价是否合理（Pricing） | Query 2, 11, 17 |
| 2. 谁是高产 agent、为什么（Performance） | Query 3, 7, 10, 15 |
| 3. 市场是在升温还是降温（Market temperature） | Query 4, 5, 9 |
| 4. 机会在哪里（Opportunity discovery） | Query 8, 19, 20 |
| 5. 未来量怎么走、现金怎么排（Forecast & cash flow） | Query 1, 6, 12, 13, 18 |
| 6. 客户匹配与数据质量（Matching & data quality） | Query 8, 14, 16 |

---

## 备注

- 所有查询用 **SQLite 3.x 语法**写，在生成的 `.sqlite` 文件上测试通过。日期过滤用字面量 `'2026-06-05'`（数据集的有效当前日期）而不是 `date('now')`，这样无论何时运行都返回非空结果。在 Redshift/Postgres 上换成 `current_date - interval '12 months'` 即可。
- TSV 文件名里的数字表示**表加载顺序**（拓扑排序）— 与这里的查询编号无关。
- 数据集的有效 `CURRENT_DATE = 2026-06-05`。所有时间窗口查询都明确引用这个日期，保持结果可重现。
- 所有 `JOIN` 路径保持引用完整性。如果某条查询在你预期有数据时返回 0 行，检查日期过滤 — 数据集大部分活动发生在 2023-2026，不是"现在"。
