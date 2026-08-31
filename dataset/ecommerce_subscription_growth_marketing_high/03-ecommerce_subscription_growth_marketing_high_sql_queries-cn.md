# VerdantBox 电商订阅增长营销 SQL 查询参考

> 业务背景, 行业科普, 术语表请见 `01-ecommerce_subscription_growth_marketing_high_business_context-cn.md`；表结构与字段含义请见 `02-ecommerce_subscription_growth_marketing_high_er_document-cn.md`.

## 概述

本文档提供为 `ecommerce_subscription_growth_marketing_high` 数据集设计的 **20 个业务向 SQL 查询**。每个查询都对应 VerdantBox 的增长营销、分析、运营、财务、高管团队在持续运转 acquisition / membership conversion / reactivation 三类活动组合时会问到的真实问题，并且每个查询都能追溯回业务背景文档第 5 节列出的某个业务问题。

所有查询基于 **SQLite 3.25+** 设计（窗口函数支持必需）。日期算术里的「今天」一律硬编码为 `REFERENCE_DATE = 2026-06-01`（与生成器的 `TODAY` 常量一致），不使用 `DATE('now')`，以保证结果可复现。生产环境替换成 `date('now')` 即可。

> ⚠️ **表名 `order` 是 SQL 保留字。** 所有引用此表的裸 SQL 都必须加引号：`"order"`（SQLite / PostgreSQL）或 `` `order` ``（MySQL）。SQLAlchemy 会自动加引号，但手写 SQL 不加会报错。

---

## 如何使用本文档

本文档是一份教学型材料，假想的读者是一名刚读完业务背景文档和 ER 文档、即将被经理派去跑这些查询的实习分析师。建议你像做项目交接一样逐题往下读，而不是把它当成 SQL 速查表来翻。

每个查询固定由五段组成，对应一次完整的「拿到问题到给出结论」的思考过程：

1. **业务背景**：谁在问、为什么是现在问、答案要支撑什么决策。
2. **类别 / 难度 / 业务角色**：这道题的 SQL 技术类别、难度档位，以及在公司里由哪个角色发起。
3. **解题思路**：在看到 SQL 之前先想清楚要碰哪些表、join 怎么搭、聚合的粒度是什么、为什么用 CTE 或窗口函数、有没有 SQLite 特有的坑。
4. **SQL**：可直接在生成的 SQLite 库上运行的查询代码。
5. **预期结果与业务结论**：结果长什么样、关键数字对应哪个业务陷阱，以及分析师拿到数字后该采取的下一步动作。

把每道题读完，你应该不仅会写这段 SQL，还能向经理解释「这个 join 为什么是 LEFT JOIN」「这个数字意味着公司接下来该做什么」。这才是这份文档真正的目的。

---

## 查询索引

| # | 标题 | 业务角色 | 类别 | 难度 |
|---|-------|---------------|----------|------------|
| 1 | 按目标拆分的活动组合 P&L | Executive | CTE + Aggregation | Basic |
| 2 | 渠道 ROAS 排行榜 | Manager | CTE + Join + Aggregation | Intermediate |
| 3 | 完整营销漏斗转化率 | Analyst | CTE + Aggregation | Intermediate |
| 4 | 会员 vs 非会员订单经济学 | Finance | Aggregation | Basic |
| 5 | 月度获客 Cohort 留存 | Analyst | CTE + Date Math | Advanced |
| 6 | 按 LTV 排序的 Top 20 客户 | Analyst | Join + Aggregation | Basic |
| 7 | 进行中活动实时看板 | Operations | CTE + Join | Basic |
| 8 | 促销码核销效率 | Manager | Aggregation | Basic |
| 9 | 会员驱动收入 Top 商品 | Manager | Multi-Join | Intermediate |
| 10 | 唤醒名单：沉睡高价值候选客户 | Manager | Subquery + Join | Intermediate |
| 11 | 星期几 × 渠道表现 | Analyst | Date Function + Aggregation | Intermediate |
| 12 | 每活动的获客成本（CAC） | Finance | CTE + Join | Advanced |
| 13 | 受众细分重叠矩阵 | Analyst | Self-Join + CTE | Advanced |
| 14 | 按获客渠道的首单耗时 | Analyst | Date Difference | Intermediate |
| 15 | 按注册 Cohort 的 Trial-to-Paid 转化 | Analyst | CTE + Join | Advanced |
| 16 | 触点频次上限审计 | Operations | Self-Join + CTE | Intermediate |
| 17 | 超支节奏告警的活动 | Operations | CTE + Filter | Basic |
| 18 | 创意素材 CTR 排行榜 | Manager | Join + Aggregation | Intermediate |
| 19 | 地理收入热力图 | Executive | Aggregation | Basic |
| 20 | 细分 AOV 排名（含会员渗透率） | Analyst | CTE + Window Function | Intermediate |

---

## 查询详情

### 查询 1：按目标拆分的活动组合 P&L

**业务背景：**
CMO 在月度经营回顾上需要一眼看清营销组合的整体表现：每类活动目标（Acquisition、Membership Conversion、Reactivation）分别花了多少钱、带来了多少可归因的 gross revenue。这个数字框定了下个季度预算再平衡的所有后续讨论。

**类别：** CTE + Aggregation
**难度：** Basic
**业务角色：** Executive

**解题思路：**
这题要把「支出」和「归因收入」对齐到活动粒度，再按 objective 汇总。支出来自 `campaign_channel`（一个活动挂多个渠道，先 GROUP BY campaign_id 求和），归因收入来自 `"order".attributed_campaign_id`（先按 campaign 求和）。两个 CTE 各自聚合好之后，用 `campaign` 表做主表、两次 LEFT JOIN 挂上去，最后按 `objective` 分组。这里 LEFT JOIN 不能换成 INNER：否则没有花费或没有归因收入的活动会整条消失，objective 维度的合计就会算少。ROAS 用 `SUM(revenue) / NULLIF(SUM(spend), 0)` 防止除零。

```sql
WITH spend_per_campaign AS (
    SELECT campaign_id, SUM(spend_to_date_usd) AS spend,
           SUM(channel_budget_usd) AS budget
    FROM campaign_channel
    GROUP BY campaign_id
),
revenue_per_campaign AS (
    SELECT attributed_campaign_id AS campaign_id, SUM(total_usd) AS revenue
    FROM "order"
    WHERE attributed_campaign_id IS NOT NULL
    GROUP BY attributed_campaign_id
)
SELECT
    c.objective,
    COUNT(DISTINCT c.id)                              AS campaign_count,
    ROUND(SUM(spc.budget), 2)                         AS total_budget,
    ROUND(SUM(spc.spend), 2)                          AS total_spend,
    ROUND(SUM(COALESCE(rpc.revenue, 0)), 2)           AS attributed_revenue,
    ROUND(SUM(COALESCE(rpc.revenue, 0))
        / NULLIF(SUM(spc.spend), 0), 3)               AS roas
FROM campaign c
LEFT JOIN spend_per_campaign spc ON spc.campaign_id = c.id
LEFT JOIN revenue_per_campaign rpc ON rpc.campaign_id = c.id
GROUP BY c.objective
ORDER BY total_spend DESC;
```

**预期结果说明：**
三行（每个 objective 一行），展示各目标的总预算、实际支出、归因收入和最终的 ROAS。一般 ACQUISITION 的 ROAS 比 REACTIVATION 低（转化新客比唤醒老客更难），MEMBERSHIP_CONVERSION 居中。

---

### 查询 2：渠道 ROAS 排行榜

**业务背景：**
绩效营销经理想知道哪些付费渠道每花一块钱带回最多收入。这决定了下次预算重分配：把表现好的渠道扩量、把表现差的暂停。

**注意事项：** `order.attributed_campaign_id` 是 **campaign 级** 的 last-touch 归因，不是 channel 级。当一个活动同时投放在多个渠道（例如 Meta + Google）时，同一个订单的收入会被该活动的每个渠道分享。我们用每渠道在活动支出中的占比对收入做加权（spend-share 加权），这是行业标准的近似方法。

**类别：** CTE + Join + Aggregation
**难度：** Intermediate
**业务角色：** Manager

**解题思路：**
难点在于归因是 campaign 级，没法直接说「这笔收入来自 Meta 还是 Google」。所以先用两个 CTE 算出每个活动的总支出和总归因收入，再在 `channel_share` 里求每个渠道在所属活动里的支出占比 `ch_spend / campaign_spend`，用这个占比把活动收入按比例摊给渠道，这就是 spend-share 加权。最后 JOIN `channel_type` 把渠道名带出来、按渠道聚合。revenue 那一路用 LEFT JOIN，是因为有的活动还没有归因订单但仍有支出，不能丢。`HAVING SUM(ch_spend) > 0` 滤掉零支出渠道，避免 ROAS 出现噪声。

```sql
WITH spend_per_campaign AS (
    SELECT campaign_id, SUM(spend_to_date_usd) AS campaign_spend
    FROM campaign_channel
    GROUP BY campaign_id
),
revenue_per_campaign AS (
    SELECT attributed_campaign_id AS campaign_id, SUM(total_usd) AS rev,
           COUNT(*) AS attributed_orders
    FROM "order"
    WHERE attributed_campaign_id IS NOT NULL
    GROUP BY attributed_campaign_id
),
channel_share AS (
    SELECT
        cc.channel_id,
        cc.campaign_id,
        cc.spend_to_date_usd                                          AS ch_spend,
        cc.spend_to_date_usd / NULLIF(spc.campaign_spend, 0)          AS spend_share,
        COALESCE(rpc.rev, 0)                                          AS campaign_rev,
        COALESCE(rpc.attributed_orders, 0)                            AS campaign_orders
    FROM campaign_channel cc
    JOIN spend_per_campaign spc       ON spc.campaign_id = cc.campaign_id
    LEFT JOIN revenue_per_campaign rpc ON rpc.campaign_id = cc.campaign_id
)
SELECT
    ct.channel_name,
    ct.channel_category,
    ROUND(SUM(cs.ch_spend), 2)                                        AS total_spend,
    ROUND(SUM(cs.campaign_rev * cs.spend_share), 2)                   AS attributed_revenue,
    ROUND(SUM(cs.campaign_rev * cs.spend_share)
        / NULLIF(SUM(cs.ch_spend), 0), 2)                             AS roas,
    ROUND(SUM(cs.campaign_orders * cs.spend_share), 1)                AS attributed_orders_share
FROM channel_share cs
JOIN channel_type ct ON ct.id = cs.channel_id
GROUP BY ct.id, ct.channel_name, ct.channel_category
HAVING SUM(cs.ch_spend) > 0
ORDER BY roas DESC;
```

**预期结果说明：**
渠道按 ROAS 排序。自有渠道（email、push）由于近乎零的变动成本通常占据榜首。付费渠道中，TikTok 和 Meta 在 acquisition 场景靠前，Google Ads 在高意图搜索场景表现突出。

---

### 查询 3：完整营销漏斗转化率

**业务背景：**
增长分析师在准备季度漏斗回顾。她需要标准的 email/push 漏斗：sent → delivered → engaged → clicked → converted，每一步都给出转化率。流失最严重的那一步就是下一轮优化投入的方向。

**注意：** 本 schema 中 `response_type` 是触点的 **终态**（terminal state）—— `convert` 隐含用户先点击了，`click` 隐含用户先打开了。计算"互动等级"时用的是"此状态或更高"。

**类别：** CTE + Aggregation
**难度：** Intermediate
**业务角色：** Analyst

**解题思路：**
漏斗的分子和分母必须落在同一总体里，否则转化率会失真。`funnel` CTE 在 `marketing_touchpoint` 上算 sent 和 delivered；`responses` CTE 在 `touchpoint_response` 上算各级响应，但要 JOIN 回 touchpoint 并限定 `delivery_status = 'delivered'`，保证只统计「投递成功的触点」产生的响应。因为 response_type 是终态模型，engaged 用 `IN ('open','click','convert')`、clicked 用 `IN ('click','convert')` 取并集（convert 隐含点击、click 隐含打开）。两个 CTE 没有公共维度，用 CROSS JOIN 拼成一行即可。

```sql
WITH funnel AS (
    SELECT
        COUNT(*) AS sent,
        SUM(CASE WHEN delivery_status = 'delivered' THEN 1 ELSE 0 END) AS delivered
    FROM marketing_touchpoint
),
responses AS (
    -- 限制到对应触点已投递成功的响应，确保分子分母在同一总体里
    SELECT
        SUM(CASE WHEN tr.response_type IN ('open','click','convert') THEN 1 ELSE 0 END) AS engaged,
        SUM(CASE WHEN tr.response_type IN ('click','convert')        THEN 1 ELSE 0 END) AS clicked,
        SUM(CASE WHEN tr.response_type = 'convert'                   THEN 1 ELSE 0 END) AS converted
    FROM touchpoint_response tr
    JOIN marketing_touchpoint mt ON mt.id = tr.touchpoint_id
    WHERE mt.delivery_status = 'delivered'
)
SELECT
    f.sent,
    f.delivered,
    r.engaged,
    r.clicked,
    r.converted,
    ROUND(100.0 * f.delivered  / NULLIF(f.sent, 0), 2)        AS delivery_rate_pct,
    ROUND(100.0 * r.engaged    / NULLIF(f.delivered, 0), 2)   AS engagement_rate_pct,
    ROUND(100.0 * r.clicked    / NULLIF(f.delivered, 0), 2)   AS click_through_rate_pct,
    ROUND(100.0 * r.converted  / NULLIF(f.delivered, 0), 2)   AS conversion_rate_pct
FROM funnel f CROSS JOIN responses r;
```

**预期结果说明：**
单行结果，暴露整个漏斗和逐级转化率。用它作为基线来给下一个活动设定目标。

---

### 查询 4：会员 vs 非会员订单经济学

**业务背景：**
财务团队想量化一个 VerdantBox+ 会员的价值。通过对比会员和非会员的 AOV、订单频次代理指标、总收入贡献，他们才能给 CFO 论证 membership conversion 活动的预算合理性。

**类别：** Aggregation
**难度：** Basic
**业务角色：** Finance

**解题思路：**
一句 GROUP BY 就够，关键在分组键和过滤口径。按 `is_member_at_purchase` 分成会员/非会员两组，过滤 `order_status IN ('delivered','shipped')` 只算实际成交。AOV 用 `AVG(total_usd)`，每买家收入用 `SUM(total_usd) / COUNT(DISTINCT customer_id)`。要注意 AOV 和「每买家收入」是两个不同口径：前者按订单平均、后者按人平均，会员复购更勤，所以后者的差距会比前者更大。单表聚合，不需要 join。

```sql
SELECT
    CASE WHEN is_member_at_purchase THEN 'Member' ELSE 'Non-Member' END AS buyer_type,
    COUNT(*)                                              AS order_count,
    COUNT(DISTINCT customer_id)                           AS unique_buyers,
    ROUND(AVG(total_usd), 2)                              AS avg_order_value,
    ROUND(SUM(total_usd), 2)                              AS gross_revenue,
    ROUND(SUM(total_usd) / COUNT(DISTINCT customer_id), 2) AS revenue_per_buyer
FROM "order"
WHERE order_status IN ('delivered', 'shipped')
GROUP BY is_member_at_purchase
ORDER BY buyer_type;
```

**预期结果说明：**
两行结果。会员 AOV（约 $225）明显高于非会员（约 $120），高出约 85%，由「会员篮子 3-6 件 vs 非会员 1-3 件 × 会员折扣价」共同驱动；会员每买家收入差距更大（复购更勤）。这组数字直接验证 membership conversion 投入的合理性，与 ER 文档「会员 AOV 溢价」陷阱一致。

---

### 查询 5：月度获客 Cohort 留存

**业务背景：**
留存分析师构建标准 cohort 留存曲线：每月获取的客户中，有多少比例在**后续的每一个**月份回来下单。这是 product-led growth 健康度最重要的单项诊断指标。

**重要说明：** 在 cohort 留存分析中，**第 0 月**（注册月本身）是 *激活率*，不是留存。本查询限制 `month_diff >= 1`，输出只包含真正的留存（注册之后的月份）。

**类别：** CTE + Date Math
**难度：** Advanced
**业务角色：** Analyst

**解题思路：**
cohort 分析的骨架是「注册月 × 下单月」的网格。先用 `strftime('%Y-%m', signup_date)` 给每个客户打 cohort 标签，再把订单也按月归桶。`month_diff` 用「年差 × 12 + 月差」算日历月距离（SQLite 没有现成的月差函数，要拆 substr 手算）。最关键的陷阱：`month_diff = 0` 是激活不是留存，所以外层 `WHERE month_diff >= 1`。`active_customers` 要用 `COUNT(DISTINCT customer_id)`，防止一个客户当月多单被重复计数。最后除以 cohort_size 得到留存率。

```sql
WITH cohorts AS (
    SELECT
        c.id AS customer_id,
        strftime('%Y-%m', c.signup_date) AS signup_month
    FROM customer c
),
order_months AS (
    SELECT
        o.customer_id,
        strftime('%Y-%m', o.order_date) AS order_month
    FROM "order" o
    WHERE o.order_status IN ('delivered', 'shipped')
),
cohort_orders AS (
    SELECT
        c.signup_month,
        om.order_month,
        -- signup_month 与 order_month 的日历月差
        (CAST(substr(om.order_month, 1, 4) AS INT) - CAST(substr(c.signup_month, 1, 4) AS INT)) * 12
        + (CAST(substr(om.order_month, 6, 2) AS INT) - CAST(substr(c.signup_month, 6, 2) AS INT)) AS month_diff,
        COUNT(DISTINCT c.customer_id) AS active_customers
    FROM cohorts c
    JOIN order_months om ON om.customer_id = c.customer_id
    GROUP BY c.signup_month, om.order_month
)
SELECT
    co.signup_month,
    co.month_diff,
    co.order_month,
    co.active_customers,
    cs.cohort_size,
    ROUND(100.0 * co.active_customers / cs.cohort_size, 2) AS retention_pct
FROM cohort_orders co
JOIN (
    SELECT signup_month, COUNT(*) AS cohort_size
    FROM cohorts
    GROUP BY signup_month
) cs ON cs.signup_month = co.signup_month
WHERE co.month_diff >= 1
ORDER BY co.signup_month, co.month_diff;
```

**预期结果说明：**
一个长方形 cohort × month_diff 网格（第 1 月起）。把它看作一个三角阵：每行是一个注册 cohort，右边的列展示该 cohort 在后续日历月的留存率。看哪些 cohort 留存得更好 —— 它们背后的活动就是要复制的成功配方。如果想看激活率（第 0 月），去掉 `month_diff >= 1` 过滤并单独标注。

---

### 查询 6：按 LTV 排序的 Top 20 客户

**业务背景：**
CRM 分析师在准备 VIP 触达名单。Top 消费者需要白手套服务 —— 新品提前购、专属客服线、惊喜礼物。名单仅筛选实际完成订单的客户（不算取消的）。

**类别：** Join + Aggregation
**难度：** Basic
**业务角色：** Analyst

**解题思路：**
标准的「客户 join 订单再聚合」。`customer` 和 `"order"` 用 INNER JOIN（只保留有成交订单的客户），过滤 `order_status IN ('delivered','shipped')`，按客户 GROUP BY，`SUM(total_usd)` 就是已实现 LTV，排序取 Top 20。GROUP BY 要带上所有非聚合的 SELECT 列。这里没有 fan-out 风险，因为订单对客户是多对一，聚合的对象正是订单本身。

```sql
SELECT
    c.id            AS customer_id,
    c.first_name || ' ' || c.last_name AS full_name,
    c.country,
    c.state_or_province,
    c.lifecycle_stage,
    COUNT(o.id)     AS total_orders,
    ROUND(SUM(o.total_usd), 2) AS lifetime_spend_usd,
    ROUND(AVG(o.total_usd), 2) AS avg_order_value
FROM customer c
JOIN "order" o ON o.customer_id = c.id
WHERE o.order_status IN ('delivered', 'shipped')
GROUP BY c.id, c.first_name, c.last_name, c.country, c.state_or_province, c.lifecycle_stage
ORDER BY lifetime_spend_usd DESC
LIMIT 20;
```

**预期结果说明：**
按 LTV 排序的 Top 20 客户，附带订单数和 AOV。预期会高度偏态 —— 头部 20 个客户可能占总收入相当大的比例（典型的长尾 Pareto 模式）。

---

### 查询 7：进行中活动实时看板

**业务背景：**
活动运营团队每天早上都要看一遍所有正在进行的活动：预算花了多少、还剩几天、累计发送了多少触点。这是每日 standup 的标准视图。

**类别：** CTE + Join
**难度：** Basic
**业务角色：** Operations

**解题思路：**
看板要把活动的「花了多少」和「发了多少触点」并排展示。两个 CTE 分别在 `campaign_channel` 上聚合支出、在 `marketing_touchpoint` join `campaign_channel` 上数触点。主表 `campaign` 用 LEFT JOIN 挂这两个 CTE，因为进行中的活动可能还没有任何触点。`days_remaining` 用 `julianday(end_date) - julianday('2026-06-01')` 算，REFERENCE_DATE 用字面量而非 `DATE('now')`。`WHERE status = 'ACTIVE'` 只看进行中，再按剩余天数升序排出紧迫度。

```sql
WITH cc_agg AS (
    SELECT campaign_id, SUM(spend_to_date_usd) AS spend
    FROM campaign_channel
    GROUP BY campaign_id
),
tp_agg AS (
    SELECT cc.campaign_id, COUNT(*) AS touchpoints_sent
    FROM marketing_touchpoint mt
    JOIN campaign_channel cc ON cc.id = mt.campaign_channel_id
    GROUP BY cc.campaign_id
)
SELECT
    c.campaign_code,
    c.campaign_name,
    c.objective,
    c.owner_name,
    c.start_date,
    c.end_date,
    CAST(julianday(c.end_date) - julianday('2026-06-01') AS INT) AS days_remaining,
    ROUND(c.total_budget_usd, 2)                                   AS budget,
    ROUND(COALESCE(cc_agg.spend, 0), 2)                            AS spend_to_date,
    ROUND(100.0 * COALESCE(cc_agg.spend, 0)
        / NULLIF(c.total_budget_usd, 0), 1)                        AS budget_consumed_pct,
    COALESCE(tp_agg.touchpoints_sent, 0)                           AS touchpoints_sent
FROM campaign c
LEFT JOIN cc_agg ON cc_agg.campaign_id = c.id
LEFT JOIN tp_agg ON tp_agg.campaign_id = c.id
WHERE c.status = 'ACTIVE'
ORDER BY days_remaining ASC;
```

**预期结果说明：**
每个正在进行的活动一行，按紧迫度升序（剩余天数升序）排列。用它来识别相对于已用时间花钱过快或过慢的活动。

---

### 查询 8：促销码核销效率

**业务背景：**
促销经理评估哪些"活动-促销"组合真的有效。每个 promo 都有 `max_redemptions` 上限：如果 `redemption_count` 接近上限说明促销好用；如果接近 0，说明要么门槛太苛刻要么投放不到位。

**类别：** Aggregation
**难度：** Basic
**业务角色：** Manager

**解题思路：**
要把促销码定义（`promo_code`）、所属活动（`campaign`）和实际核销（`promo_redemption`）三者拼起来。`promo_code` JOIN `campaign` 是多对一，再 LEFT JOIN `promo_redemption`，因为有的码一次都没核销过，不能丢。按促销码 GROUP BY，核销率 = `redemption_count / max_redemptions`，实际折扣 = `SUM(discount_applied_usd)`。这里的 `redemption_count` 是表里已经 reconcile 好的冗余字段，可以直接用，不必再去 count 一遍明细。

```sql
SELECT
    pc.code,
    c.campaign_name,
    c.objective,
    pc.discount_type,
    pc.discount_value,
    pc.max_redemptions,
    pc.redemption_count,
    ROUND(100.0 * pc.redemption_count / NULLIF(pc.max_redemptions, 0), 1) AS redemption_pct,
    ROUND(SUM(pr.discount_applied_usd), 2) AS actual_discount_given
FROM promo_code pc
JOIN campaign c ON c.id = pc.campaign_id
LEFT JOIN promo_redemption pr ON pr.promo_code_id = pc.id
GROUP BY pc.id, pc.code, c.campaign_name, c.objective, pc.discount_type,
         pc.discount_value, pc.max_redemptions, pc.redemption_count
ORDER BY redemption_pct DESC;
```

**预期结果说明：**
按核销率排序的促销码榜单。结合 campaign 的 objective，可以看出哪种类型的促销（百分比减、固定金额减、免运费）对哪种活动类型最有效。

---

### 查询 9：会员驱动收入 Top 商品

**业务背景：**
品类经理想搞清楚会员最喜欢哪些 SKU。会员驱动收入告诉商品团队下一次会员专属上新该 feature 哪些商品、会员购物高峰期该备哪些库存。

**类别：** Multi-Join
**难度：** Intermediate
**业务角色：** Manager

**解题思路：**
这是一条四表连接：`product` 接 `product_category`（带出分类名），再接 `order_item`（购买明细行），再接 `"order"`（用来筛会员单）。过滤 `o.is_member_at_purchase = 1` 且成交状态。聚合粒度是 SKU：`SUM(quantity)` 数销量、`SUM(line_total_usd)` 算会员收入、`COUNT(DISTINCT customer_id)` 数独立会员买家。order_item 对 product 是多对一，不会重复计 product，但 `COUNT(DISTINCT customer_id)` 仍要 DISTINCT，避免一个客户买多单时被算成多个买家。

```sql
SELECT
    p.sku,
    p.product_name,
    p.brand,
    pc.category_name,
    SUM(oi.quantity)                           AS units_sold_to_members,
    ROUND(SUM(oi.line_total_usd), 2)           AS member_revenue,
    ROUND(AVG(oi.unit_price_usd), 2)           AS avg_member_price,
    COUNT(DISTINCT o.customer_id)              AS unique_member_buyers
FROM product p
JOIN product_category pc ON pc.id = p.category_id
JOIN order_item oi ON oi.product_id = p.id
JOIN "order" o ON o.id = oi.order_id
WHERE o.is_member_at_purchase = 1
  AND o.order_status IN ('delivered', 'shipped')
GROUP BY p.id, p.sku, p.product_name, p.brand, pc.category_name
ORDER BY member_revenue DESC
LIMIT 15;
```

**预期结果说明：**
按会员归因收入排序的 Top 15 SKU。把这份名单与 `is_winner = 1` 的创意素材结合，就能策划下一次会员专属活动。

---

### 查询 10：唤醒名单 —— 沉睡高价值候选客户

**业务背景：**
生命周期营销经理在为下一次 reactivation 活动准备受众。最合适的目标是当前处于 dormant 或 at_risk 但历史 LTV 高于平均（>$200）的客户 —— 他们值得给更深的折扣去唤醒。

**类别：** Subquery + Join
**难度：** Intermediate
**业务角色：** Manager

**解题思路：**
目标是「dormant 或 at_risk 且 LTV > 200」的客户。先用一个子查询在 `"order"` 上按客户聚合出 `lifetime_spend` 和 `last_order_date`，并用 `HAVING SUM(total_usd) > 200` 在子查询内部就把高价值客户筛出来（在子查询里过滤比拉到外层更高效）。再 JOIN 回 `customer`，用 `WHERE lifecycle_stage IN ('dormant','at_risk')` 限定沉睡人群。`days_since_last_order` 用 REFERENCE_DATE 减最后下单日。最后按 LTV 降序取 50 人，直接喂给下一个 REACTIVATION 活动。

```sql
SELECT
    c.id,
    c.first_name || ' ' || c.last_name AS full_name,
    c.email,
    c.lifecycle_stage,
    ROUND(spend.lifetime_spend, 2) AS lifetime_spend,
    spend.last_order_date,
    CAST(julianday('2026-06-01') - julianday(spend.last_order_date) AS INT) AS days_since_last_order,
    c.email_subscribed,
    c.sms_subscribed
FROM customer c
JOIN (
    SELECT
        customer_id,
        SUM(total_usd)                AS lifetime_spend,
        MAX(DATE(order_date))         AS last_order_date
    FROM "order"
    WHERE order_status IN ('delivered', 'shipped')
    GROUP BY customer_id
    HAVING SUM(total_usd) > 200
) spend ON spend.customer_id = c.id
WHERE c.lifecycle_stage IN ('dormant', 'at_risk')
ORDER BY lifetime_spend DESC
LIMIT 50;
```

**预期结果说明：**
最多 50 个 dormant/at_risk 且 LTV >$200 的客户名单，按 LTV 降序。把它丢进下一个 REACTIVATION 活动的 `target_segment` 即可。

---

### 查询 11：星期几 × 渠道表现

**业务背景：**
渠道分析师在调优发送时段策略。按"星期几 × 渠道"看触点投递和响应，可以找出每个自有渠道的最佳发送窗口（例如 push 在周日打开率最高）。

**类别：** Date Function + Aggregation
**难度：** Intermediate
**业务角色：** Analyst

**解题思路：**
要按「渠道 × 星期几」交叉看互动。`marketing_touchpoint` JOIN `campaign_channel` JOIN `channel_type` 拿到渠道名，再 LEFT JOIN `touchpoint_response`，因为有的触点没有任何响应，不能丢。`strftime('%w', sent_at)` 取星期几（0 是周日），用 CASE 转成可读缩写。过滤 `delivery_status = 'delivered'` 只看投递成功的触点。engaged 和 clicked 的口径与 Q3 保持一致，用 `IN (...)` 取并集。按渠道和星期 GROUP BY，分母统一用 `COUNT(mt.id)`（发送数）。

```sql
-- 与 Query 3 / Query 18 保持一致："click = IN('click','convert')"
SELECT
    ct.channel_name,
    CASE strftime('%w', mt.sent_at)
        WHEN '0' THEN 'Sun'
        WHEN '1' THEN 'Mon'
        WHEN '2' THEN 'Tue'
        WHEN '3' THEN 'Wed'
        WHEN '4' THEN 'Thu'
        WHEN '5' THEN 'Fri'
        WHEN '6' THEN 'Sat'
    END                                              AS day_of_week,
    COUNT(mt.id)                                     AS sends,
    SUM(CASE WHEN tr.response_type IN ('open','click','convert') THEN 1 ELSE 0 END) AS engagements,
    SUM(CASE WHEN tr.response_type IN ('click','convert') THEN 1 ELSE 0 END)        AS clicks,
    ROUND(100.0 * SUM(CASE WHEN tr.response_type IN ('open','click','convert') THEN 1 ELSE 0 END)
        / NULLIF(COUNT(mt.id), 0), 2)                AS engagement_rate_pct,
    ROUND(100.0 * SUM(CASE WHEN tr.response_type IN ('click','convert') THEN 1 ELSE 0 END)
        / NULLIF(COUNT(mt.id), 0), 2)                AS click_rate_pct
FROM marketing_touchpoint mt
JOIN campaign_channel cc ON cc.id = mt.campaign_channel_id
JOIN channel_type ct ON ct.id = cc.channel_id
LEFT JOIN touchpoint_response tr ON tr.touchpoint_id = mt.id
WHERE mt.delivery_status = 'delivered'
GROUP BY ct.channel_name, day_of_week
ORDER BY ct.channel_name, day_of_week;
```

**预期结果说明：**
适合直接做 heatmap 的结果表：每行是一个（渠道、星期）组合，附带 engagement rate。用它锁定营销日历中的最佳发送窗口。

---

### 查询 12：每活动的获客成本（CAC）

**业务背景：**
FP&A 团队需要每个 acquisition 活动的单位经济学。每个活动：花费 ÷（活动窗口内获取的净新客数）= 有效 CAC。与 LTV 基准对比就能看出哪些活动正在回本。

**类别：** CTE + Join
**难度：** Advanced
**业务角色：** Finance

**解题思路：**
CAC = 花费 / 新客数，再叠加首单收入看回本速度。三个 CTE 分别算：活动支出（`campaign_channel` 聚合）、活动获客数（`customer` 按 `acquisition_campaign_id` 计数）、首单收入（`customer` join 首单 `o.is_first_order = 1`）。主表 `campaign` 对支出和获客用 INNER JOIN（算 CAC 必须两者都有），对首单收入用 LEFT JOIN。过滤 `objective = 'ACQUISITION'`（只有获客活动算 CAC 才有意义），再加 `new_customers > 0` 和 `spend > 0` 防止除零。按 CAC 升序，越靠前越高效。

```sql
WITH campaign_spend AS (
    SELECT
        campaign_id,
        SUM(spend_to_date_usd) AS spend
    FROM campaign_channel
    GROUP BY campaign_id
),
campaign_acquisitions AS (
    SELECT
        acquisition_campaign_id AS campaign_id,
        COUNT(*) AS new_customers
    FROM customer
    WHERE acquisition_campaign_id IS NOT NULL
    GROUP BY acquisition_campaign_id
),
first_order_revenue AS (
    SELECT
        c.acquisition_campaign_id AS campaign_id,
        SUM(o.total_usd) AS first_order_revenue
    FROM customer c
    JOIN "order" o ON o.customer_id = c.id AND o.is_first_order = 1
    WHERE c.acquisition_campaign_id IS NOT NULL
    GROUP BY c.acquisition_campaign_id
)
SELECT
    c.campaign_code,
    c.campaign_name,
    c.objective,
    ROUND(cs.spend, 2)                                       AS spend,
    ca.new_customers                                         AS new_customers,
    ROUND(cs.spend / NULLIF(ca.new_customers, 0), 2)         AS cac,
    ROUND(COALESCE(fr.first_order_revenue, 0), 2)            AS first_order_revenue,
    ROUND(COALESCE(fr.first_order_revenue, 0)
        / NULLIF(cs.spend, 0), 2)                            AS first_order_roas
FROM campaign c
JOIN campaign_spend cs ON cs.campaign_id = c.id
JOIN campaign_acquisitions ca ON ca.campaign_id = c.id
LEFT JOIN first_order_revenue fr ON fr.campaign_id = c.id
WHERE c.objective = 'ACQUISITION'
  AND ca.new_customers > 0
  AND cs.spend > 0
ORDER BY cac ASC;
```

**预期结果说明：**
按 CAC 升序排列的 acquisition 活动（最低 = 最高效）。`first_order_roas ≥ 0.5` 的活动通常被认为是可持续的 —— 因为剩余的回本会在 LTV 周期内由复购完成。

---

### 查询 13：受众细分重叠矩阵

**业务背景：**
受众策略分析师在 Q3 计划前整合 segment 池。她怀疑很多 segment 重度重叠 —— 对重叠 segment 同时投活动既浪费预算又造成用户疲劳。本查询输出 Top 10 大 segment 的两两重叠人数。

**类别：** Self-Join + CTE
**难度：** Advanced
**业务角色：** Analyst

**解题思路：**
要算 Top 10 大 segment 两两之间共享多少客户。先用 CTE 取成员数最多的 10 个 segment。核心是 `customer_segment_membership` 的自连接：m1 和 m2 在同一个 customer_id 上 join，就得到「同时属于两个 segment」的客户。用 `t2.segment_id > t1.segment_id` 这个条件保证每对只算一次、且不和自己配对（否则会出现 A-B 和 B-A 两份、以及 A-A 自配）。按 segment 对 GROUP BY，`COUNT(DISTINCT m1.customer_id)` 就是重叠人数。自连接是表达「同一实体两两关系」的标准手法。

```sql
WITH top_segments AS (
    SELECT segment_id, COUNT(*) AS members
    FROM customer_segment_membership
    GROUP BY segment_id
    ORDER BY members DESC
    LIMIT 10
)
SELECT
    s1.segment_name AS segment_a,
    s2.segment_name AS segment_b,
    COUNT(DISTINCT m1.customer_id) AS overlap_customers
FROM top_segments t1
JOIN audience_segment s1 ON s1.id = t1.segment_id
JOIN customer_segment_membership m1 ON m1.segment_id = t1.segment_id
JOIN customer_segment_membership m2 ON m2.customer_id = m1.customer_id
JOIN top_segments t2 ON t2.segment_id = m2.segment_id AND t2.segment_id > t1.segment_id
JOIN audience_segment s2 ON s2.id = t2.segment_id
GROUP BY s1.segment_name, s2.segment_name
ORDER BY overlap_customers DESC
LIMIT 25;
```

**预期结果说明：**
重叠最多的 Top 25 segment pair。用它来合并或去重 segment —— 例如"Email Engaged Non-Members"和"Push Opted-In"可能重叠 60%+，就不该在同一个活动里分别 targeting。

---

### 查询 14：按获客渠道的首单耗时

**业务背景：**
生命周期分析师研究新客从注册到首单的转化速度，按获客渠道拆分。首单耗时短的渠道质量更高（注册时就已经有意图）。

**类别：** Date Difference
**难度：** Intermediate
**业务角色：** Analyst

**解题思路：**
按获客渠道看注册到首单的平均天数。`customer` JOIN `channel_type`（拿渠道名）JOIN `"order"` 并限定 `o.is_first_order = 1`，保证每个客户只取它的首单。天数用 `julianday(order_date) - julianday(signup_date)`，分别取 AVG、MIN、MAX。`HAVING COUNT(DISTINCT customer_id) >= 10` 滤掉样本太小的渠道，避免均值不稳。这里 INNER JOIN order 会自动排除从没下过单的客户，而这正是我们想要的（只看已激活客户）。

```sql
SELECT
    ct.channel_name,
    COUNT(DISTINCT c.id) AS acquired_customers,
    ROUND(AVG(julianday(DATE(o.order_date)) - julianday(c.signup_date)), 1) AS avg_days_to_first_order,
    ROUND(MIN(julianday(DATE(o.order_date)) - julianday(c.signup_date)), 1) AS min_days,
    ROUND(MAX(julianday(DATE(o.order_date)) - julianday(c.signup_date)), 1) AS max_days
FROM customer c
JOIN channel_type ct ON ct.id = c.acquisition_channel_id
JOIN "order" o ON o.customer_id = c.id AND o.is_first_order = 1
GROUP BY ct.channel_name
HAVING COUNT(DISTINCT c.id) >= 10
ORDER BY avg_days_to_first_order ASC;
```

**预期结果说明：**
按平均首单耗时排序的渠道。Search / Google Ads 类高意图渠道通常居首，社交发现型渠道靠后。

---

### 查询 15：按注册 Cohort 的 Trial-to-Paid 转化

**业务背景：**
会员业务负责人想知道 trial 转 paid 的转化率是在改善还是在恶化。把试用开始时间按季度分桶，对比各季度的转化率，能暴露宏观趋势 —— 例如 Q4 上的某个项目调整把转化率提升了 8 个百分点。

**类别：** CTE + Join
**难度：** Advanced
**业务角色：** Analyst

**解题思路：**
把试用按季度分桶看转化趋势。用一个 CTE 给每条 `membership_subscription` 算 `cohort_quarter`：`strftime('%Y', trial_start_date)` 拼上「(月份 + 2) / 3」算出季度（SQLite 没有 quarter 函数，要自己手算）。外层按季度 GROUP BY，转化数用 `activation_date IS NOT NULL` 计数，转化率 = 转化数 / 试用总数。再用 `SUM(CASE WHEN ...)` 模式分别统计 active、cancelled 的数量。按季度排序，就能看出 trial-to-paid 是逐季在升、在降还是持平。

```sql
WITH cohorts AS (
    SELECT
        id,
        customer_id,
        trial_start_date,
        activation_date,
        status,
        strftime('%Y', trial_start_date) || '-Q' ||
            CAST((CAST(strftime('%m', trial_start_date) AS INT) + 2) / 3 AS TEXT) AS cohort_quarter
    FROM membership_subscription
)
SELECT
    cohort_quarter,
    COUNT(*)                                                          AS trials_started,
    SUM(CASE WHEN activation_date IS NOT NULL THEN 1 ELSE 0 END)      AS converted_to_paid,
    SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END)                AS still_active,
    SUM(CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END)             AS later_cancelled,
    ROUND(100.0 * SUM(CASE WHEN activation_date IS NOT NULL THEN 1 ELSE 0 END)
        / NULLIF(COUNT(*), 0), 2)                                     AS trial_to_paid_pct
FROM cohorts
GROUP BY cohort_quarter
ORDER BY cohort_quarter;
```

**预期结果说明：**
每个季度一行，展示该季度的试用量、转化数、留在 active 状态的数量、转化率。看趋势 —— 是在升、降、还是持平？

---

### 查询 16：触点频次上限审计

**业务背景：**
合规 / 运营团队要执行一个频次上限：任何客户在同一活动 14 天内收到的触点不能超过 5 次，避免用户疲劳和退订。本查询列出违规者。

**类别：** Self-Join + CTE
**难度：** Intermediate
**业务角色：** Operations

**解题思路：**
要找出「同一客户在同一活动 14 天内收到超过 5 次触点」的违规者。SQLite 不支持窗口 RANGE 子句里的 INTERVAL，所以改用关联自连接：t1 和 t2 在相同 customer_id 加 campaign_id 上 join，条件是 `t2.sent_at <= t1.sent_at AND julianday(t1) - julianday(t2) <= 14`，这样对每个 t1 就能数出它「前 14 天内」的触点数。先用一个 CTE 把 touchpoint 经 `campaign_channel` 关联到 campaign。外层 `WHERE sends_in_prior_14d > 5` 筛违规，按客户加活动聚合取最大窗口值。这是生产级的滚动窗口写法，不是占位。

```sql
-- SQLite 在 RANGE 子句里不支持 INTERVAL 语法。改用自连接计算 14 天滚动窗口，再聚合违规者。
WITH tp_with_campaign AS (
    SELECT mt.id, mt.customer_id, cc.campaign_id, mt.sent_at
    FROM marketing_touchpoint mt
    JOIN campaign_channel cc ON cc.id = mt.campaign_channel_id
),
rolling_counts AS (
    SELECT
        t1.id          AS tp_id,
        t1.customer_id,
        t1.campaign_id,
        t1.sent_at,
        COUNT(t2.id)   AS sends_in_prior_14d
    FROM tp_with_campaign t1
    JOIN tp_with_campaign t2
      ON t2.customer_id = t1.customer_id
     AND t2.campaign_id = t1.campaign_id
     AND t2.sent_at <= t1.sent_at
     AND julianday(t1.sent_at) - julianday(t2.sent_at) <= 14
    GROUP BY t1.id, t1.customer_id, t1.campaign_id, t1.sent_at
)
SELECT
    rc.customer_id,
    c.campaign_code,
    c.campaign_name,
    MAX(rc.sends_in_prior_14d) AS max_14d_window_sends
FROM rolling_counts rc
JOIN campaign c ON c.id = rc.campaign_id
WHERE rc.sends_in_prior_14d > 5
GROUP BY rc.customer_id, c.campaign_code, c.campaign_name
ORDER BY max_14d_window_sends DESC
LIMIT 30;
```

**预期结果说明：**
Top 30 个违反 5 次触点上限的"客户–活动"组合。把这份名单推到 Lifecycle Ops 队列里审查。

---

### 查询 17：超支节奏告警的活动

**业务背景：**
活动运营需要识别哪些活动正在把预算烧得过快 —— 即"已用预算占比 显著高于 已用时间占比"的活动。这些活动要么需要追加预算，要么需要设置日均上限。

**类别：** CTE + Filter
**难度：** Basic
**业务角色：** Operations

**解题思路：**
要找出「花钱比时间快」的活动。`pacing` CTE 一次算出两个百分比：`pct_spent = spend / budget`，`pct_elapsed = (今天 - start) / (end - start)`，后者用 `MAX(0, MIN(100, ...))` clamp 到 0 到 100，防止 start 在未来或 end 已过的边缘情形把比例算飞。支出来自 `campaign_channel` 聚合的 CTE，用 LEFT JOIN 挂上来。外层 `WHERE pct_spent > pct_elapsed + 10` 干净地筛出超支 10 个百分点以上的活动，按超支幅度降序。只看 `status = 'ACTIVE'` 的进行中活动。

```sql
-- pct_elapsed 被 clamp 到 [0, 100]，防止 ACTIVE 活动的 start_date 在未来或 end_date 已过的边缘情形。
-- pacing CTE 把两个百分比一次性算出来，外层 WHERE 就能干净地过滤。
WITH cc_agg AS (
    SELECT campaign_id, SUM(spend_to_date_usd) AS spend
    FROM campaign_channel
    GROUP BY campaign_id
),
pacing AS (
    SELECT
        c.id, c.campaign_code, c.campaign_name, c.objective, c.status,
        c.start_date, c.end_date, c.total_budget_usd,
        COALESCE(cc_agg.spend, 0)                                          AS spend,
        ROUND(100.0 * COALESCE(cc_agg.spend, 0) / c.total_budget_usd, 1)   AS pct_spent,
        MAX(0.0, MIN(100.0, ROUND(100.0 *
            (julianday('2026-06-01') - julianday(c.start_date))
            / NULLIF(julianday(c.end_date) - julianday(c.start_date), 0), 1))) AS pct_elapsed
    FROM campaign c
    LEFT JOIN cc_agg ON cc_agg.campaign_id = c.id
    WHERE c.status = 'ACTIVE'
)
SELECT
    campaign_code,
    campaign_name,
    objective,
    status,
    start_date,
    end_date,
    ROUND(total_budget_usd, 2) AS total_budget,
    ROUND(spend, 2)            AS spend,
    pct_spent,
    pct_elapsed
FROM pacing
WHERE pct_spent > pct_elapsed + 10
ORDER BY (pct_spent - pct_elapsed) DESC;
```

**预期结果说明：**
"花钱节奏 比 时间节奏 快 10 个百分点以上"的进行中活动。这些活动要在预算耗尽前紧急决策。

---

### 查询 18：创意素材 CTR 排行榜

**业务背景：**
创意负责人在回顾哪些创意素材 click-per-send 表现最好。结论会用来推 A/B 测试的胜出结论、把胜出创意更大范围铺开。

**类别：** Join + Aggregation
**难度：** Intermediate
**业务角色：** Manager

**解题思路：**
按创意素材算 click-per-send。`creative_asset` LEFT JOIN `marketing_touchpoint`，并且把 `delivery_status = 'delivered'` 放进 join 条件而不是 WHERE，这样没有任何投递触点的素材也能保留下来（CTR 显示 0 而非消失）。再 LEFT JOIN `touchpoint_response`。CTR = clicks / sends，clicks 口径 `IN ('click','convert')` 与 Q3、Q11 一致。按素材 GROUP BY，`HAVING COUNT(mt.id) >= 5` 滤掉曝光太少的素材。把 `is_winner` 和高 CTR 交叉对比，能验证 A/B 测试有没有选错 winner。

```sql
-- "click" 定义为 IN ('click','convert')，与 Query 3 / Query 11 保持一致 ——
-- 'convert' 类触点隐含用户先点击了。
SELECT
    ca.id                                          AS asset_id,
    ca.asset_name,
    ca.asset_type,
    ca.target_emotion,
    ca.cta_text,
    ca.is_winner,
    COUNT(mt.id)                                   AS sends,
    SUM(CASE WHEN tr.response_type IN ('click','convert') THEN 1 ELSE 0 END) AS clicks,
    ROUND(100.0 * SUM(CASE WHEN tr.response_type IN ('click','convert') THEN 1 ELSE 0 END)
        / NULLIF(COUNT(mt.id), 0), 2)              AS ctr_pct
FROM creative_asset ca
LEFT JOIN marketing_touchpoint mt ON mt.creative_asset_id = ca.id
    AND mt.delivery_status = 'delivered'
LEFT JOIN touchpoint_response tr ON tr.touchpoint_id = mt.id
GROUP BY ca.id, ca.asset_name, ca.asset_type, ca.target_emotion,
         ca.cta_text, ca.is_winner
HAVING COUNT(mt.id) >= 5
ORDER BY ctr_pct DESC
LIMIT 20;
```

**预期结果说明：**
按 CTR 排序的 Top 20 创意。把 `is_winner` 与高 CTR 做交叉对比 —— 如果不匹配，说明 A/B 测试可能选错了 winner（也可能因为 winner 是按转化率而非 CTR 评的）。

---

### 查询 19：地理收入热力图

**业务背景：**
区域 GM 想快速看一下美国各州和加拿大各省的收入分布。结果会用于区域营销预算分配和履约中心规划。

**类别：** Aggregation
**难度：** Basic
**业务角色：** Executive

**解题思路：**
按国家加州/省看收入分布。`customer` LEFT JOIN `"order"`，并把成交状态过滤放进 join 条件，这样没有任何订单的地区也会出现在结果里（收入显示 0 而非整行消失）。按 `country, state_or_province` GROUP BY，用 `COUNT(DISTINCT)` 分别数客户和订单，`SUM(total_usd)` 算收入，再除以客户数得人均收入。这里用 LEFT JOIN 而非 INNER 的关键，正是为了让小地区不被静默丢掉。最后按 gross revenue 降序排出区域榜单。

```sql
SELECT
    c.country,
    c.state_or_province AS region,
    COUNT(DISTINCT c.id)            AS customer_count,
    COUNT(DISTINCT o.id)            AS order_count,
    ROUND(SUM(o.total_usd), 2)      AS gross_revenue,
    ROUND(AVG(o.total_usd), 2)      AS avg_order_value,
    ROUND(SUM(o.total_usd) / COUNT(DISTINCT c.id), 2) AS revenue_per_customer
FROM customer c
LEFT JOIN "order" o ON o.customer_id = c.id
    AND o.order_status IN ('delivered', 'shipped')
GROUP BY c.country, c.state_or_province
ORDER BY gross_revenue DESC;
```

**预期结果说明：**
按 gross revenue 排序的区域排行。在美国预计 CA、NY、TX、WA、MA、FL 居首；加拿大省份排名靠后（占客户基数的 12%）。

---

### 查询 20：细分 AOV 排名（含会员渗透率）

**业务背景：**
资深受众分析师在为下一波活动计划提案，需要为 segment 选择做辩护。最强的 segment 同时具备高 AOV 和高会员渗透率 —— 这些 segment 上 premium 报价最容易共鸣。窗口函数用于在每个 `segment_type` 内排名。

**类别：** CTE + Window Function
**难度：** Intermediate
**业务角色：** Analyst

**解题思路：**
这题有个经典的 join fan-out 陷阱：如果直接把 segment、order、membership 三表 join 再聚合，一个客户的多张订单会让他被重复计成多个 active member，会员渗透率就虚高。所以先用 `customer_metrics` CTE 在客户粒度聚合（每客户一行：lifetime_spend、order_count、is_active_member），把 fan-out 消化在这一层。再在 `seg_metrics` 里把 segment join 到客户指标上聚合，AOV = 总花费 / 总订单数，会员渗透率 = active members / segment size。最后用 `RANK() OVER (PARTITION BY segment_type ORDER BY avg_order_value DESC)` 在每个 segment_type 内部排名。窗口函数是「组内排名」的正确工具，比自连接计数干净得多。

```sql
-- 在汇总到 segment 之前，先按 customer 级聚合（每个客户一行），
-- 避免"一个客户多个订单会被算多次 active member"的 join fan-out 问题。
WITH customer_metrics AS (
    SELECT
        c.id AS customer_id,
        COALESCE(SUM(CASE WHEN o.order_status IN ('delivered','shipped')
                          THEN o.total_usd END), 0) AS lifetime_spend,
        COUNT(CASE WHEN o.order_status IN ('delivered','shipped')
                   THEN o.id END) AS order_count,
        MAX(CASE WHEN ms.status = 'active' THEN 1 ELSE 0 END) AS is_active_member
    FROM customer c
    LEFT JOIN "order" o ON o.customer_id = c.id
    LEFT JOIN membership_subscription ms ON ms.customer_id = c.id
    GROUP BY c.id
),
seg_metrics AS (
    SELECT
        s.id                                       AS segment_id,
        s.segment_name,
        s.segment_type,
        COUNT(DISTINCT csm.customer_id)            AS segment_size,
        SUM(cm.order_count)                        AS order_count,
        ROUND(SUM(cm.lifetime_spend)
            / NULLIF(SUM(cm.order_count), 0), 2)   AS avg_order_value,
        ROUND(SUM(cm.lifetime_spend), 2)           AS total_revenue,
        ROUND(100.0 * SUM(cm.is_active_member)
            / NULLIF(COUNT(DISTINCT csm.customer_id), 0), 1) AS pct_active_members
    FROM audience_segment s
    JOIN customer_segment_membership csm ON csm.segment_id = s.id
    JOIN customer_metrics cm ON cm.customer_id = csm.customer_id
    GROUP BY s.id, s.segment_name, s.segment_type
)
SELECT
    segment_type,
    segment_name,
    segment_size,
    order_count,
    avg_order_value,
    total_revenue,
    pct_active_members,
    RANK() OVER (PARTITION BY segment_type ORDER BY avg_order_value DESC) AS rank_within_type
FROM seg_metrics
WHERE segment_size >= 10
ORDER BY segment_type, rank_within_type
LIMIT 50;
```

**预期结果说明：**
每个 segment_type 内部按 AOV 排序的 segment 名单。结合 `pct_active_members` 找出"既挣钱又会员浓度高"的 segment —— 这些是 upsell 活动的首选目标。

---

## 查询类别汇总

一个查询可能属于多个类别 —— count 列是显著使用该模式的查询数。

| 类别 | 数量 | 查询编号 |
|----------|-------|---------------|
| Aggregation | 5 | 1, 4, 8, 11, 19 |
| Join Operations | 5 | 6, 9, 10, 14, 18 |
| Window Functions | 1 | 20 |
| Date/Time Analysis | 4 | 5, 11, 14, 17 |
| Subqueries/CTEs | 9 | 1, 2, 3, 5, 7, 12, 13, 15, 17, 20 |
| Self-Join | 2 | 13, 16 |
| Multi-table Joins (≥3) | 4 | 9, 13, 18, 20 |

## 业务角色覆盖

| 角色 | 数量 | 查询编号 |
|------|-------|---------------|
| Executive / C-Level | 2 | 1, 19 |
| Manager | 5 | 2, 8, 9, 10, 18 |
| Analyst | 7 | 3, 5, 6, 11, 13, 14, 15, 20 |
| Operations | 3 | 7, 16, 17 |
| Finance | 2 | 4, 12 |

## 难度分布

| 难度 | 数量 | 查询编号 |
|------------|-------|---------------|
| Basic | 7 | 1, 4, 6, 7, 8, 17, 19 |
| Intermediate | 9 | 2, 3, 9, 10, 11, 14, 16, 18, 20 |
| Advanced | 4 | 5, 12, 13, 15 |

---

## 注释

- 所有查询使用 SQLite 3.25+ 语法（Q20 必须用到窗口函数）。
- 裸 SQL 中 `"order"` 必须加引号 —— 它是 SQL 保留字。SQLAlchemy 会自动加引号；手写 SQL 必须自己加。
- 查询稍作调整即可适配其他数据库（PostgreSQL、MySQL）—— 保留字引号风格不同：`"order"`（SQLite / PostgreSQL）vs `` `order` ``（MySQL）。
- 日期算术查询里的"今天"硬编码为 `2026-06-01`（与生成器的 `TODAY` 常量保持一致，保证可复现）—— 在生产环境替换为 `date('now')`。
- Query 16 用关联自连接实现 14 天滚动频次审计（SQLite 不接受 `RANGE` 子句中的 `INTERVAL`）。`julianday(t1) - julianday(t2) <= 14` 过滤是真正的生产形态 —— 不是 placeholder。
- "click" 的定义在 Q3、Q11、Q18 之间保持一致：`click = response_type IN ('click', 'convert')`。`convert` 类响应隐含客户先点击了（终态响应模型）。
- Q2（Channel ROAS）使用 spend-share 加权，因为 `attributed_campaign_id` 是 campaign 粒度。真正的 channel 级归因需要 touchpoint 级 last-touch 链路。
