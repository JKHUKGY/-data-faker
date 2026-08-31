# B2B SaaS - 需求生成 SQL 查询参考

> 配套文档：业务背景见 `01-b2b_saas_demand_generation_high_business_context-cn.md`，表结构与 ER 图见 `02-b2b_saas_demand_generation_high_er_document-cn.md`。
> 所有查询均兼容 SQLite 3.x。参考"今天" = `2026-06-01`。
> 数据库文件：`b2b_saas_demand_generation_high.sqlite`

## 概述

本文档提供 **50 条 SQL 查询**，旨在全面展示 Stratosend B2B SaaS 需求生成数据集的分析覆盖面。

按照 ER 文档 BI Blueprint 一节的指引，查询被划分为两个教学类别：

| Category | 数量 | 风格 | 用途 |
|----------|-------|-------|---------|
| **Dashboard 风格** (D1–D15) | 15 (30%) | 快照式、聚合密集、固定指标 | 每条查询对应一个 L2/L3 dashboard widget |
| **业务问题风格** (B1–B35) | 35 (70%) | 多样、探索性、技巧丰富 | 每条查询回答一个独立的临时分析问题 |

## 如何使用本文档

这份文档是写给刚加入 Stratosend 的实习生或初级分析师的。假设你已经读过业务背景文档 (`01-...business_context-cn.md`) 和 ER 文档 (`02-...er_document-cn.md`)，知道公司卖什么、漏斗长什么样、16 张表怎么互相挂钩。现在经理把这份文档丢给你，说"这周先把这些 query 过一遍"。它不是一份让你复制粘贴去跑的脚本集合，而是一份带你学怎么思考的项目交接材料。

每条 query 都对应业务背景文档里的某个真实业务问题：某个 CMO 要做季度预算复盘，某个 SDR Manager 发现回复率掉了，某个 RevOps 要在预测会前核对滑期交易。query 的价值不在于跑出一张表，而在于这张表能支撑哪个决策。读的时候请把 SQL 当作要读懂、要学会的对象，而不只是要执行的命令。看明白别人为什么这么 join、为什么在这里用 CTE，比记住语法重要得多。

为此，每条 query 都按固定的五段来组织，五段各有分工：

- **业务背景**：谁在问、为什么问、答案要支撑什么决策、为什么现在急着要。
- **类别 / 难度 / 角色**：三个标签，告诉你这条 query 用到哪类 SQL 技巧、难度多高、服务于哪个岗位。
- **解题思路**：在你看到代码之前，先带你走一遍思路。要碰哪些表、join 怎么搭、哪里有坑 (扇出重复、基数错误、该用 LEFT 还是 INNER)、一行输出代表什么、为什么该用窗口函数或 CTE。读完这一段，再看 SQL 你就知道它在干什么了。
- **SQL**：查询本身，可以直接对数据库跑。
- **期望结果与业务结论**：先描述结果长什么样 (几行、几列、数量级)，再说分析师拿到结果后该做什么。跑出数字只是分析的起点，不是终点。

关于日期约定：整个数据集锚定在固定的参考日 `2026-06-01`。每条 query 都把这个日期写成字面量 (例如 `DATE('2026-06-01', '-30 days')`)，而不是用 `DATE('now')`。这样无论你哪天跑，结果都一样，方便对照本文档里给出的期望数量级。线上系统里才需要把它换成 `DATE('now')`。

## 查询索引

### Dashboard 风格查询 (D1–D15)

| # | 标题 | Dashboard | Role | Category | Difficulty |
|---|-------|-----------|------|----------|------------|
| D1 | 按渠道的季度市场 P&L | CMO Quarterly P&L | CMO | CTE + Aggregation | Intermediate |
| D2 | 按阶段的开放管道及覆盖率 | VP Sales Pipeline Health | VP Sales | Aggregation + Subquery | Intermediate |
| D3 | 按渠道的混合 CAC 及回收期 | CFO Unit Economics | CFO | CTE + Aggregation | Advanced |
| D4 | 季度 Lead Cohort 成熟度 | CRO Cohort | CRO | CTE + Date Bucketing | Advanced |
| D5 | 12 个月滚动胜率趋势 | Executive Win Rate | Executive | Window Function | Advanced |
| D6 | 每日漏斗快照（过去 30 天） | Daily Funnel | Demand Gen Manager | Date Bucketing | Basic |
| D7 | SDR 30 天产能看板 | SDR Productivity | SDR Manager | Aggregation + Join | Intermediate |
| D8 | AE 开放管道看板 | AE Pipeline | VP Sales | Aggregation + Join | Intermediate |
| D9 | 活跃 campaign 计划 vs 实际跟踪 | Active Campaign Tracker | Demand Gen Manager | Multi-Join + Aggregation | Intermediate |
| D10 | 本周热门内容 | Content Heatmap | Content Marketing | Aggregation + Date Filter | Basic |
| D11 | ABM Tier-1 7 天互动脉搏 | ABM Pulse | ABM Lead | Multi-Join + Date | Intermediate |
| D12 | 停滞 opportunity 告警（30 天+） | Stale Opp Alert | VP Sales | Date Difference | Basic |
| D13 | MQL 老化分桶 | MQL Aging | Marketing Ops | Date Bucketing | Basic |
| D14 | 经理团队汇总（自连接 FK） | Manager Rollup | VP Sales | Self-Join | Intermediate |
| D15 | 今日加权预测 | Forecast | RevOps | Aggregation | Basic |

### 业务问题风格查询 (B1–B35)

| # | 标题 | 主题领域 | Role | Category | Difficulty |
|---|-------|--------------|------|----------|------------|
| B1 | 完整漏斗：Lead → MQL → SQL → Opp → Won | A Demand | VP Marketing | CTE + Aggregation | Intermediate |
| B2 | 按来源的 MQL 老化 | A Demand | Marketing Ops | Date Math + Aggregation | Intermediate |
| B3 | Lead 评分十分位与胜率 | A Demand | Marketing Ops | CTE + NTILE | Advanced |
| B4 | 取消资格原因 × 来源矩阵 | A Demand | Marketing Ops | Pivot + Aggregation | Intermediate |
| B5 | Persona × 资历转化矩阵 | A Demand | Marketing Ops | Pivot + Aggregation | Intermediate |
| B6 | 多次访问 lead 行为提升 | A Demand | Analyst | Window + Filter | Advanced |
| B7 | Lead 来源质量随季度衰减 | A Demand | Analyst | CTE + Date Bucketing | Advanced |
| B8 | 按影响管道的顶尖 campaign | B Campaign | Demand Gen Manager | Multi-Join + Aggregation | Intermediate |
| B9 | Webinar 端到端漏斗 | B Campaign | Content Marketing | CTE + Multi-Join | Advanced |
| B10 | Campaign 类型 ROI 对比 | B Campaign | Demand Gen Manager | Aggregation + Join | Intermediate |
| B11 | 首次触点制胜 campaign 分析 | B Campaign | Demand Gen Manager | Multi-Join + Aggregation | Intermediate |
| B12 | 内容资产对 Won 管道的影响 | B Content | Content Marketing | Multi-Join + Aggregation | Advanced |
| B13 | 内容主题 × Persona 亲和度 | B Content | Content Marketing | Pivot + Aggregation | Intermediate |
| B14 | 门控 vs 非门控内容转化提升 | B Content | Marketing Ops | CTE + Aggregation | Intermediate |
| B15 | Email_Blast 对沉默 lead 的激活 | B Campaign | Demand Gen Manager | Date Difference + Filter | Advanced |
| B16 | 按 Tier 的销售周期（中位数 + p90） | C Pipeline | VP Sales | Aggregation + Percentile | Intermediate |
| B17 | 阶段间转化 + 阶段停留中位天数 | C Pipeline | VP Sales | Self-Join + CTE | Advanced |
| B18 | 按竞争对手与行业的赢/输原因矩阵 | C Pipeline | RevOps | Pivot + Aggregation | Intermediate |
| B19 | 阶段倒退检测（Opp 向后流转） | C Pipeline | RevOps | Self-Join | Advanced |
| B20 | 预测偏差——预测 vs 实际 | C Pipeline | RevOps | Date Math + Aggregation | Advanced |
| B21 | 滑期 opportunity——预计关闭日期推迟 2 次以上 | C Pipeline | RevOps | Aggregation on history | Advanced |
| B22 | 开放管道集中度风险 | C Pipeline | VP Sales | Window + Cumulative | Advanced |
| B23 | SDR SLA 合规——MQL → 首封邮件 24 小时内 | D Productivity | SDR Manager | Date Difference + Self-Join | Advanced |
| B24 | AE 配额完成率排名 | D Productivity | VP Sales | Aggregation + Join | Basic |
| B25 | SDR Sequence 步骤漏斗衰减 | D Productivity | SDR Manager | Aggregation by step | Basic |
| B26 | 按销售代表的回复情感分布 | D Productivity | SDR Manager | Pivot + Aggregation | Intermediate |
| B27 | 经理团队汇总（通过自连接 FK 的 Won ARR） | D Productivity | VP Sales | Self-Join + Aggregation | Intermediate |
| B28 | 销售代表起步分析（入职 → 首单成交） | D Productivity | VP Sales | Date Difference + Join | Intermediate |
| B29 | 首次触点 vs 末次触点 vs W 形归因 | E Attribution | RevOps | CTE + Window | Advanced |
| B30 | 来源 × Tier 胜率透视矩阵 | E Attribution | Demand Gen Manager | Pivot + Aggregation | Intermediate |
| B31 | 按渠道的 CAC 回收期 | E Attribution | CFO | CTE + Aggregation | Advanced |
| B32 | 隐藏在 W 形归因中的影响管道 | E Attribution | RevOps | Multi-Join + Filter | Advanced |
| B33 | ABM 多干系人覆盖深度 | F ABM | ABM Lead | Multi-Join + Aggregation | Intermediate |
| B34 | ABM vs 非 ABM 胜率对比 | F ABM | VP Sales | Aggregation + Filter | Basic |
| B35 | 账户扩展——拥有多次 Won 的客户 | F ABM | RevOps | Aggregation + HAVING | Intermediate |

---

## 归因维度术语表

"channel" 一词在营销分析中被过度重载。下述查询使用四个 *不同* 的维度——切勿把它们当作同一个维度连接：

| 维度 | 来源字段 | 基数 | 示例值 | 使用方 |
|-----------|---------------|-------------|----------------|---------|
| `campaign_type`     | `campaign.campaign_type`     | 8 | `Webinar`, `Paid_Search`, `ABM_Sequence`, … | D1 spend 与 pipeline、B10 |
| `campaign_code`     | `campaign.campaign_code`     | ~80 | `WBR-202505-059`, `ABM-202501-057`, … | B29（全部 3 个 CTE）、B11 |
| `source_code`       | `lead_source.source_code`    | 10 | `PAID_SEARCH_GOOGLE`, `WEBINAR_HOSTED`, … | D3、B30、B31 |
| `source_category`   | `lead_source.source_category`| 4 | `Inbound`, `Outbound`, `Partner`, `Event` | — （仅供参考） |

经验法则：每条查询只挑一个维度并贯彻到底。早期 D1 草稿曾在 `FULL OUTER JOIN` 中混用 `campaign_type` 与 `source_category`，产生了永远无法匹配的行——下面的修订版本端到端都使用 `campaign_type`。

---

# Dashboard 风格查询 (D1–D15)

每条查询驱动一个 dashboard widget。它们通常聚合密集、面向快照。

---

## D1: 按渠道的季度市场 P&L

**Dashboard:** CMO Quarterly P&L

**业务背景：** CMO 每季度回顾市场投入与产生的管道，决定下季度的预算重分配。问题是：在某个渠道（lead source）上花的每一美元，产生了多少 **影响管道 ARR**？ROI 弱的渠道砍掉；ROI 强的渠道追加预算。CMO dashboard 上的这个 widget 展示过去 6 个季度的趋势。

**Category:** CTE + Aggregation
**Difficulty:** Intermediate
**Business Role:** CMO

**解题思路：** 这题要把两件事对齐到「季度 × 渠道」粒度：花了多少钱，和赚回多少 Won ARR。支出从 `campaign` 表来 (按 `campaign_type` 当 channel)，管道则要从 `opportunity` 一路 join 回 `lead`、再到 `lead.source_campaign_id` 对应的 `campaign`，才能给每笔 Won 贴上 campaign_type 标签。两边粒度不同 (一个按 campaign 起始日分季度，一个按 opp 实际成交日分季度)，所以分别用 `spend` 和 `pipeline` 两个 CTE 各自聚合，再按 `(qtr, channel)` 拼起来。坑在于约 30% 的 opp 是 `source_lead_id IS NULL` 的直接外呼，没有 campaign 可归因，这里的 INNER JOIN 会自然把它们排除掉 (这是有意的，见 Note)。本该用 `FULL OUTER JOIN` 才能既保留只有支出没有 Won 的渠道、又保留只有 Won 没有支出的渠道，但 SQLite 老版本不支持，所以用「LEFT JOIN ... UNION ALL ... WHERE IS NULL」这个可移植写法模拟出全外连接。季度桶用 STRFTIME 把月份换算成 Q1 到 Q4。

```sql
-- 此处 Channel = campaign_type。只有源自 lead 的 Won 才可归因到
-- campaign（source_lead_id 为 NULL 的直接外呼 opp 被排除——见 note）。
WITH spend AS (
  SELECT
    STRFTIME('%Y', c.start_date) || '-Q' ||
      ((CAST(STRFTIME('%m', c.start_date) AS INT) - 1) / 3 + 1) AS qtr,
    c.campaign_type AS channel,
    SUM(c.spend_to_date_usd) AS spend_usd
  FROM campaign c
  WHERE c.status = 'COMPLETED'
  GROUP BY qtr, c.campaign_type
),
pipeline AS (
  SELECT
    STRFTIME('%Y', o.actual_close_date) || '-Q' ||
      ((CAST(STRFTIME('%m', o.actual_close_date) AS INT) - 1) / 3 + 1) AS qtr,
    c.campaign_type AS channel,
    SUM(o.amount_usd) AS won_arr_usd
  FROM opportunity o
  JOIN opportunity_stage s ON s.id = o.current_stage_id
  JOIN lead l ON l.id = o.source_lead_id
  JOIN campaign c ON c.id = l.source_campaign_id
  WHERE s.is_won = 1
  GROUP BY qtr, c.campaign_type
)
-- FULL OUTER JOIN spend ⨝ pipeline 的可移植等价写法
SELECT
  s.qtr AS quarter,
  s.channel,
  ROUND(s.spend_usd, 0) AS spend_usd,
  ROUND(COALESCE(p.won_arr_usd, 0), 0) AS won_arr_usd,
  CASE WHEN s.spend_usd > 0
       THEN ROUND(COALESCE(p.won_arr_usd, 0) / s.spend_usd, 2)
       ELSE NULL END AS roi_ratio
FROM spend s
LEFT JOIN pipeline p ON s.qtr = p.qtr AND s.channel = p.channel
UNION ALL
SELECT
  p.qtr AS quarter,
  p.channel,
  0 AS spend_usd,
  ROUND(p.won_arr_usd, 0) AS won_arr_usd,
  NULL AS roi_ratio
FROM pipeline p
LEFT JOIN spend s ON s.qtr = p.qtr AND s.channel = p.channel
WHERE s.qtr IS NULL
ORDER BY quarter DESC, won_arr_usd DESC;
```

> Note：约 30% 的 opp 为直接外呼（`source_lead_id IS NULL`），没有 campaign 归因。它们按设计在 `pipeline` 中被排除——campaign ROI 只比较 campaign 影响的 Won 与 campaign 支出。如果要包含这部分，可以用 `lead_source.source_category` 加一个 "Outbound" 桶并 union 进来，但要注意 channel 维度并不直接可比。

> SQLite Note：原版本写作 `FULL OUTER JOIN`（需 SQLite 3.39+）。上面这版用的是可移植的 `LEFT JOIN … UNION ALL LEFT JOIN … WHERE … IS NULL` 模式，在任何 SQL 方言下都能跑。

**预期结果说明：** ~30–50 行（6 季度 × 5–10 个渠道）。每行展示某渠道的季度支出 vs Won ARR，外加一个 `roi_ratio`。Top winners 通常是 `Webinar`、`ABM_Sequence` 和 `Conference_Event`（ROI 1–5x）；表现较差的常是 `Paid_Social` 和 `Content_Syndication`。

---

## D2: 按阶段的开放管道及覆盖率

**Dashboard:** VP Sales Pipeline Health

**业务背景：** 每周一 VP Sales 打开此 dashboard 评估团队是否有足够的开放管道完成配额。经典 SaaS 经验法则是 "3x coverage"——开放管道应 ≥ 3× 剩余配额。如果覆盖率跌破 3x，就需要紧急的 SDR 行动。

**Category:** Aggregation + Subquery
**Difficulty:** Intermediate
**Business Role:** VP Sales

**解题思路：** 核心是把开放管道 (`opportunity` join `opportunity_stage` 取 `is_closed = 0`) 按阶段聚合，再去跟团队总配额比。配额来自 `sales_rep`，但它是另一个粒度 (一个标量)，所以单独用一个 `quota` CTE 把所有在职 AE 的 `quota_usd` 加成一个数。两个 CTE 用无条件的 `FROM pipe p, quota q` 做笛卡尔积拼接 (quota 只有一行，所以这是安全的交叉连接，让每个阶段行都能拿到那个总配额)。一行输出代表一个销售阶段。这里有意区分两个覆盖率：`stage_coverage_ratio` 是该阶段开放 ARR / 总配额，而 `total_coverage_ratio` 用窗口函数 `SUM(...) OVER ()` 把所有阶段的开放 ARR 加总再除配额，得到经典的 3x coverage KPI (每行同值)。加权 ARR 乘的是 `typical_win_probability_pct`，体现各阶段不同的成单概率。

```sql
WITH pipe AS (
  SELECT
    s.stage_name,
    s.stage_order,
    COUNT(o.id) AS opp_count,
    SUM(o.amount_usd) AS open_arr_usd,
    SUM(o.amount_usd * s.typical_win_probability_pct / 100.0) AS weighted_arr_usd
  FROM opportunity o
  JOIN opportunity_stage s ON s.id = o.current_stage_id
  WHERE s.is_closed = 0
  GROUP BY s.stage_name, s.stage_order
),
quota AS (
  SELECT SUM(quota_usd) AS total_quota_usd
  FROM sales_rep
  WHERE is_active = 1 AND role IN ('AE_SMB','AE_Mid','AE_Enterprise')
)
SELECT
  p.stage_name,
  p.opp_count,
  ROUND(p.open_arr_usd, 0) AS open_arr_usd,
  ROUND(p.weighted_arr_usd, 0) AS weighted_arr_usd,
  ROUND(p.open_arr_usd / NULLIF(q.total_quota_usd, 0), 2) AS stage_coverage_ratio,
  ROUND(SUM(p.open_arr_usd) OVER () / NULLIF(q.total_quota_usd, 0), 2) AS total_coverage_ratio
FROM pipe p, quota q
ORDER BY p.stage_order;
```

**预期结果说明：** 5 行（Discovery、Demo、Eval/POC、Proposal、Negotiation）。每行展示 opp 数、开放 ARR、按胜率加权的 ARR，以及两种覆盖率视图：`stage_coverage_ratio`（该阶段的开放 ARR / 团队总配额——按阶段拆分）和 `total_coverage_ratio`（经典 "3x coverage" KPI：所有开放 ARR / 团队总配额——每行同一数值）。3x 经验值针对的是 `total_coverage_ratio`；按阶段的数值只是显示管道集中在哪。通常大量管道集中在 Discovery（占开放 opp 的 60–70%）。

---

## D3: 按渠道的混合 CAC 及回收期

**Dashboard:** CFO Unit Economics

**业务背景：** CFO 需要知道获取每个客户的成本，并按渠道拆分。混合 CAC = 渠道总支出 / 新 logo 数量。回收期（月）= CAC / 月 ARR。健康 SaaS 的目标是 SMB 回收期 < 18 个月，Enterprise 回收期 < 24 个月。

**Category:** CTE + Aggregation
**Difficulty:** Advanced
**Business Role:** CFO

**解题思路：** CAC 要把「每个渠道的总支出」除以「该渠道带来的新 logo 数」，所以分子分母来自两个不同粒度，必须先各自聚合再 join，不能在一个大 join 里硬算 (否则支出会被 Won 的行数重复乘进去)。`channel_spend` 用 `lead_source.typical_cost_per_lead_usd × COUNT(lead)` 估算支出代理 (因为实际 campaign 支出没有按 source 打标签)，注意这里是 LEFT JOIN lead，让没有 lead 的来源也保留下来。`channel_wins` 从 Won opp 里按 `source_code` 数独立 account (`COUNT(DISTINCT account_id)`) 作为新 logo，避免一个客户多次 Won 被算成多个新 logo。两个 CTE 按 source_code 用 LEFT JOIN 拼接，保证有支出但没 Won 的渠道不会消失 (它的 CAC 会因为分母为 0 而被 NULLIF 挡成 NULL)。回收期把月 ARR (Won ARR / logo / 12) 当分母，所有除法都套 NULLIF 防零除。最后用 `ORDER BY cac_usd IS NULL, cac_usd ASC` 模拟 NULLS LAST，把无法算 CAC 的渠道排到末尾。

```sql
WITH won AS (
  SELECT
    o.id AS opp_id,
    o.amount_usd,
    o.account_id,
    o.source_id,
    ls.source_code,
    ls.source_category
  FROM opportunity o
  JOIN opportunity_stage s ON s.id = o.current_stage_id
  JOIN lead_source ls ON ls.id = o.source_id
  WHERE s.is_won = 1
),
channel_spend AS (
  -- 分配到 source 的支出：当实际 campaign 支出未按 source 打标签时，
  -- 用 lead_source.typical_cost_per_lead × lead 数量作为代理。
  SELECT
    ls.source_code,
    ls.source_category,
    ls.typical_cost_per_lead_usd * COUNT(l.id) AS spend_proxy_usd
  FROM lead_source ls
  LEFT JOIN lead l ON l.source_id = ls.id
  GROUP BY ls.id
),
channel_wins AS (
  SELECT source_code, COUNT(DISTINCT account_id) AS new_logos,
         SUM(amount_usd) AS won_arr_usd
  FROM won GROUP BY source_code
)
SELECT
  cs.source_code,
  cs.source_category,
  ROUND(cs.spend_proxy_usd, 0) AS spend_proxy_usd,
  COALESCE(cw.new_logos, 0) AS new_logos,
  ROUND(COALESCE(cw.won_arr_usd, 0), 0) AS won_arr_usd,
  ROUND(cs.spend_proxy_usd / NULLIF(cw.new_logos, 0), 0) AS cac_usd,
  ROUND((cs.spend_proxy_usd / NULLIF(cw.new_logos, 0)) /
        NULLIF(cw.won_arr_usd / NULLIF(cw.new_logos, 0) / 12, 0), 1) AS payback_months
FROM channel_spend cs
LEFT JOIN channel_wins cw ON cw.source_code = cs.source_code
-- 可移植的 ASC "NULLS LAST"（在 SQLite < 3.30 也能用）
ORDER BY cac_usd IS NULL, cac_usd ASC;
```

**预期结果说明：** 10 行（每个 lead source 一行）。最低 CAC 通常是 `OUTBOUND_SDR`（只算沉没成本）和 `PARTNER_REFERRAL`（基本免费）。最高 CAC 是 `CONFERENCE_EVENT`，因为 CPL 高。回收期差异很大——单 Won 高 ARR（偏 Enterprise）的渠道即便 CAC 高也能更快回本。

---

## D4: 季度 Lead Cohort 成熟度

**Dashboard:** CRO Cohort

**业务背景：** CRO 想看 lead cohort 如何随时间成熟——经过 6 个月培育后的 Q1 cohort，比经过 2 个月的 Q4 cohort 表现更好吗？此 widget 针对每个 lead 创建季度展示：总 lead 数、成为 MQL 的比例、SQL 比例、Won 比例——全部以 TODAY 为观测点。更老的 cohort 有更多时间转化。

**Category:** CTE + Date Bucketing
**Difficulty:** Advanced
**Business Role:** CRO

**解题思路：** 这是一道 cohort 成熟度题，关键是「按 lead 的创建季度分组，观测它们到今天为止走到了漏斗哪一步」。`lead_cohort` CTE 用 `created_at` 算出季度桶，同时把几个布尔标志 (`mql_date IS NOT NULL`、`sql_date IS NOT NULL`、status 是否已转 contact) 直接物化出来，因为这些状态字段都已对账在 `lead` 表上，不必再回事件表。Won 比较特殊，要靠 `opportunity` join `opportunity_stage` (`is_won = 1`) 反查 `source_lead_id`，所以单独做一个 `opp_wins` CTE 取去重的中标 lead。这里必须用 LEFT JOIN 把 cohort 和 opp_wins 拼起来，不能 INNER，否则没成单的 lead (绝大多数) 会被剔掉，分母塌掉，每个 cohort 的转化率会被严重高估。一行输出代表一个季度 cohort，列是各阶段的绝对数和占比。老 cohort 因为有更多时间成熟，% Won 应当更高，这正是 CRO 想看的趋势。

```sql
WITH lead_cohort AS (
  SELECT
    id,
    STRFTIME('%Y', created_at) || '-Q' ||
      ((CAST(STRFTIME('%m', created_at) AS INT) - 1) / 3 + 1) AS cohort_q,
    status,
    mql_date IS NOT NULL AS is_mql,
    sql_date IS NOT NULL AS is_sql,
    status = 'converted_to_contact' AS is_converted
  FROM lead
),
opp_wins AS (
  SELECT DISTINCT o.source_lead_id AS lead_id
  FROM opportunity o
  JOIN opportunity_stage s ON s.id = o.current_stage_id
  WHERE s.is_won = 1 AND o.source_lead_id IS NOT NULL
),
cohort_summary AS (
  SELECT
    lc.cohort_q,
    COUNT(*) AS lead_count,
    SUM(CASE WHEN lc.is_mql THEN 1 ELSE 0 END) AS mql_count,
    SUM(CASE WHEN lc.is_sql THEN 1 ELSE 0 END) AS sql_count,
    SUM(CASE WHEN lc.is_converted THEN 1 ELSE 0 END) AS converted_count,
    SUM(CASE WHEN ow.lead_id IS NOT NULL THEN 1 ELSE 0 END) AS won_count
  FROM lead_cohort lc
  LEFT JOIN opp_wins ow ON ow.lead_id = lc.id
  GROUP BY lc.cohort_q
)
SELECT
  cohort_q,
  lead_count,
  mql_count,
  ROUND(100.0 * mql_count / lead_count, 1) AS pct_mql,
  sql_count,
  ROUND(100.0 * sql_count / lead_count, 1) AS pct_sql,
  converted_count,
  ROUND(100.0 * converted_count / lead_count, 1) AS pct_converted,
  won_count,
  ROUND(100.0 * won_count / lead_count, 2) AS pct_won
FROM cohort_summary
ORDER BY cohort_q;
```

**预期结果说明：** ~6 行（过去 18 个月里每个季度一行）。更老的 cohort（2024-Q4、2025-Q1）的 % Won 应高于更新的（2026-Q1、2026-Q2），因为它们有更多时间成熟。Lead→MQL 率在各 cohort 间应大致一致；Lead→Won 在新 cohort 中较低。

---

## D5: 12 个月滚动胜率趋势

**Dashboard:** Executive Win Rate

**业务背景：** 给高管团队的单线趋势图，展示团队整体胜率是改善还是恶化。指标是已关闭 opportunity 中的胜率，采用 90 天滚动窗口计算，绘制过去 12 个月。

**Category:** Window Function
**Difficulty:** Advanced
**Business Role:** Executive

**解题思路：** 这题只碰 `opportunity` 和 `opportunity_stage` 两张表，先用 `closed` CTE 把过去 365 天内已关闭、且有 `actual_close_date` 的 opp 拉出来 (日期下界用字面量 `DATE('2026-06-01', '-365 days')`)。然后 `monthly` 按月聚合出每月已关闭数和中标数。真正的技巧在最外层：用窗口函数 `SUM(...) OVER (ORDER BY yr_month ROWS BETWEEN 2 PRECEDING AND CURRENT ROW)` 算 3 个月滑动汇总，再相除得到平滑后的滚动胜率。之所以用窗口函数而不是自连接，是因为月度数据天然有序，滑动窗口一句就能搞定，写自连接反而笨重。一行输出代表一个月，既给原始月度胜率，也给滚动胜率，让高管看趋势时不被单月噪声干扰。滚动除法记得套 NULLIF 防某段窗口内没有已关闭单导致的零除。

```sql
WITH closed AS (
  SELECT
    o.id,
    o.actual_close_date,
    s.is_won
  FROM opportunity o
  JOIN opportunity_stage s ON s.id = o.current_stage_id
  WHERE s.is_closed = 1
    AND o.actual_close_date IS NOT NULL
    AND o.actual_close_date >= DATE('2026-06-01', '-365 days')
),
monthly AS (
  SELECT
    STRFTIME('%Y-%m', actual_close_date) AS yr_month,
    COUNT(*) AS closed_count,
    SUM(CASE WHEN is_won = 1 THEN 1 ELSE 0 END) AS won_count
  FROM closed
  GROUP BY yr_month
)
SELECT
  yr_month,
  closed_count,
  won_count,
  ROUND(100.0 * won_count / closed_count, 1) AS win_rate_pct,
  SUM(closed_count) OVER (ORDER BY yr_month
                          ROWS BETWEEN 2 PRECEDING AND CURRENT ROW) AS rolling_3mo_closed,
  SUM(won_count) OVER (ORDER BY yr_month
                       ROWS BETWEEN 2 PRECEDING AND CURRENT ROW) AS rolling_3mo_won,
  ROUND(100.0 * SUM(won_count) OVER (ORDER BY yr_month
                                     ROWS BETWEEN 2 PRECEDING AND CURRENT ROW)
        / NULLIF(SUM(closed_count) OVER (ORDER BY yr_month
                                         ROWS BETWEEN 2 PRECEDING AND CURRENT ROW), 0), 1)
    AS rolling_3mo_win_rate_pct
FROM monthly
ORDER BY yr_month;
```

**预期结果说明：** ~12 行，每月一行。每行包含原始月度胜率和 3 个月滚动胜率（更平滑）。期望 ~18–25% 的胜率趋势；滚动线会比月度柱更平滑。整年应能看到渐进的改善或恶化趋势。

---

## D6: 每日漏斗快照（过去 30 天）

**Dashboard:** Daily Funnel

**业务背景：** 每天早上，Demand Gen Manager 检查昨天进来多少 lead / MQL / SQL / opportunity，与过去 30 天平均值比较。如果昨天明显偏离趋势，就触发调查（例如付费搜索宕机、表单坏了）。

**Category:** Date Bucketing
**Difficulty:** Basic
**Business Role:** Demand Gen Manager

**解题思路：** 漏斗四个阶段 (lead / MQL / SQL / opp) 的日期来自不同字段：lead 进库用 `lead.created_at`，MQL 用 `lead.mql_date`，SQL 用 `lead.sql_date`，opp 用 `opportunity.created_at`。它们的「日期键」语义不同，没法在一次 GROUP BY 里同时按四个日期分组，所以分别做四个按天聚合的 CTE，再用日期 LEFT JOIN 拼成一张宽表。坑在于某一天可能只有 lead 没有 MQL，所以拼接后要用 `COALESCE(..., 0)` 把缺失的天数补成 0，不然那天会显示 NULL 看起来像没数据。这里以 `leads_per_day` 为主表左连其余三个，是因为有新 lead 的天数最全；输出每行代表一天，四列是当天各阶段的新增量，按日期倒序方便看最近的趋势。

```sql
WITH leads_per_day AS (
  SELECT DATE(created_at) AS dt, COUNT(*) AS new_leads
  FROM lead
  WHERE DATE(created_at) >= DATE('2026-06-01', '-30 days')
  GROUP BY dt
),
mqls_per_day AS (
  SELECT mql_date AS dt, COUNT(*) AS new_mqls
  FROM lead
  WHERE mql_date IS NOT NULL
    AND mql_date >= DATE('2026-06-01', '-30 days')
  GROUP BY mql_date
),
sqls_per_day AS (
  SELECT sql_date AS dt, COUNT(*) AS new_sqls
  FROM lead
  WHERE sql_date IS NOT NULL
    AND sql_date >= DATE('2026-06-01', '-30 days')
  GROUP BY sql_date
),
opps_per_day AS (
  SELECT DATE(created_at) AS dt, COUNT(*) AS new_opps
  FROM opportunity
  WHERE DATE(created_at) >= DATE('2026-06-01', '-30 days')
  GROUP BY dt
)
SELECT
  COALESCE(l.dt, m.dt, s.dt, o.dt) AS dt,
  COALESCE(l.new_leads, 0) AS new_leads,
  COALESCE(m.new_mqls, 0) AS new_mqls,
  COALESCE(s.new_sqls, 0) AS new_sqls,
  COALESCE(o.new_opps, 0) AS new_opps
FROM leads_per_day l
LEFT JOIN mqls_per_day m ON l.dt = m.dt
LEFT JOIN sqls_per_day s ON l.dt = s.dt
LEFT JOIN opps_per_day o ON l.dt = o.dt
ORDER BY dt DESC;
```

**预期结果说明：** ~30 行（过去一个月每天一行）。新 lead 通常 10–30/天；新 MQL ~5–10/天；新 SQL ~0–3/天；新 opp ~1–4/天。某一天的尖峰或低谷暗示上游活动异常。

---

## D7: SDR 30 天产能看板

**Dashboard:** SDR Productivity

**业务背景：** SDR Manager 监控每位 SDR 过去 30 天的产出。每位 SDR 的关键指标：发送邮件数、回复率、处理的 MQL 数，以及 **SLA 合规** = 在成为 MQL 后 24 小时内收到 SDR 首封邮件的已分配 MQL 比例。如果回复率下降或 SLA 下滑，需要立即干预。

**Category:** Aggregation + Join
**Difficulty:** Intermediate
**Business Role:** SDR Manager

**解题思路：** 每位 SDR 有两类指标，来源不同，所以拆成两个 CTE。`sdr_emails` 从 `sales_email` 按发件人聚合近 30 天的发送、打开、回复数。`sdr_mqls` 更绕：它要算 SLA 合规，即「分配给这位 SDR 的 MQL 中，有多少在成为 MQL 后 24 小时内收到了这位 SDR 发的首封邮件」。这需要一个内嵌子查询先求出每个 (lead, sender) 组合的首封邮件时间 `MIN(sent_at)`，再 LEFT JOIN 回 lead，用 `JULIANDAY` 算两个日期差是否 ≤ 1 天。LEFT JOIN 是关键：哪怕某 MQL 从没收到邮件，也要保留它进分母，否则合规率会虚高。最外层从 `sales_rep` 出发左连这两个 CTE，保证零产出的 SDR 也出现在看板上 (用 COALESCE 补 0)。一行代表一位在职 SDR。注意 JULIANDAY 处理日期减法，比直接字符串比较可靠。

```sql
WITH sdr_emails AS (
  SELECT
    sender_rep_id,
    COUNT(*) AS emails_sent_30d,
    SUM(CASE WHEN opened = 1 THEN 1 ELSE 0 END) AS opens,
    SUM(CASE WHEN replied = 1 THEN 1 ELSE 0 END) AS replies
  FROM sales_email
  WHERE DATE(sent_at) >= DATE('2026-06-01', '-30 days')
  GROUP BY sender_rep_id
),
sdr_mqls AS (
  SELECT
    l.assigned_sdr_id,
    COUNT(*) AS mqls_assigned,
    -- SLA：指定 SDR 在 24 小时内给该 lead 发送的首封 sales_email
    SUM(CASE WHEN first_touch.first_email_at IS NOT NULL
             AND JULIANDAY(first_touch.first_email_at) - JULIANDAY(l.mql_date) <= 1
             THEN 1 ELSE 0 END) AS mqls_touched_within_24h
  FROM lead l
  LEFT JOIN (
    SELECT recipient_lead_id, sender_rep_id, MIN(sent_at) AS first_email_at
    FROM sales_email
    WHERE recipient_lead_id IS NOT NULL
    GROUP BY recipient_lead_id, sender_rep_id
  ) first_touch
    ON first_touch.recipient_lead_id = l.id
   AND first_touch.sender_rep_id = l.assigned_sdr_id
  WHERE l.mql_date IS NOT NULL
    AND l.mql_date >= DATE('2026-06-01', '-30 days')
    AND l.assigned_sdr_id IS NOT NULL
  GROUP BY l.assigned_sdr_id
)
SELECT
  sr.id,
  sr.first_name || ' ' || sr.last_name AS sdr_name,
  sr.region,
  COALESCE(se.emails_sent_30d, 0) AS emails_sent_30d,
  COALESCE(se.opens, 0) AS opens,
  COALESCE(se.replies, 0) AS replies,
  ROUND(100.0 * COALESCE(se.replies, 0) / NULLIF(se.emails_sent_30d, 0), 1) AS reply_rate_pct,
  COALESCE(sm.mqls_assigned, 0) AS mqls_assigned_30d,
  ROUND(100.0 * COALESCE(sm.mqls_touched_within_24h, 0)
        / NULLIF(sm.mqls_assigned, 0), 1) AS sla_compliance_pct
FROM sales_rep sr
LEFT JOIN sdr_emails se ON se.sender_rep_id = sr.id
LEFT JOIN sdr_mqls sm ON sm.assigned_sdr_id = sr.id
WHERE sr.role = 'SDR' AND sr.is_active = 1
ORDER BY emails_sent_30d DESC;
```

**预期结果说明：** 12 行（每位活跃 SDR 一行）。Top SDR 可能在 30 天内发 1000–2000 封邮件，回复率 2–4%。在此数据集中，`sla_compliance_pct` 在 SDR 团队范围内落在 30–55%（generator 没有专门注入 24 小时 MQL 触达信号），因此在相对排名时把 **>50% 视为前四分位** 而 **<35% 视为辅导红旗**。真实 SaaS 通过 SLA 强制的工作流工具会以 >80% 为目标。垫底者还可能呈现 <500 封邮件或 <1% 回复率——这两个本身也是独立的红旗。

---

## D8: AE 开放管道看板

**Dashboard:** AE Pipeline

**业务背景：** VP Sales 关注每位 AE 的开放管道：拥有的 opp 数量、总开放 ARR、按阶段的分布，以及多少是"停滞"的（30 天+ 无 transition）。停滞 opp 容易最终丢失。

**Category:** Aggregation + Join
**Difficulty:** Intermediate
**Business Role:** VP Sales

**解题思路：** 每位 AE 要算两组数：开放管道概况，和停滞 opp 数。两者粒度不同，硬塞进一个 join 会把行数搞乱，所以分成 `ae_pipeline` (按 owner 聚合开放 opp 数、开放 ARR、晚期阶段数) 和 `ae_stale` 两个 CTE。停滞的判定要看每个 opp 最后一次阶段流转的时间，所以 `ae_stale` 里先用一个内嵌子查询 `MAX(transitioned_at) GROUP BY opportunity_id` 把每个 opp 的最后流转时间求出来，再过滤出超过 30 天没动的开放 opp，按 owner 数出 `COUNT(DISTINCT opp.id)` (用 DISTINCT 防 join 扇出重复计数)。最外层从 `sales_rep` 出发 LEFT JOIN 这两个 CTE，让没有任何开放管道的 AE 也显示出来 (补 0)，然后算停滞占比。一行代表一位在职 AE。日期下界同样用字面量。

```sql
WITH ae_pipeline AS (
  SELECT
    o.owner_ae_id,
    COUNT(o.id) AS open_opp_count,
    SUM(o.amount_usd) AS open_arr_usd,
    SUM(CASE WHEN s.stage_name IN ('Negotiation','Proposal') THEN 1 ELSE 0 END) AS late_stage_count
  FROM opportunity o
  JOIN opportunity_stage s ON s.id = o.current_stage_id
  WHERE s.is_closed = 0
  GROUP BY o.owner_ae_id
),
ae_stale AS (
  SELECT
    o.owner_ae_id,
    COUNT(DISTINCT o.id) AS stale_count
  FROM opportunity o
  JOIN opportunity_stage s ON s.id = o.current_stage_id
  JOIN (
    SELECT opportunity_id, MAX(transitioned_at) AS last_transition_at
    FROM stage_transition GROUP BY opportunity_id
  ) lt ON lt.opportunity_id = o.id
  WHERE s.is_closed = 0
    AND DATE(lt.last_transition_at) < DATE('2026-06-01', '-30 days')
  GROUP BY o.owner_ae_id
)
SELECT
  sr.id AS ae_id,
  sr.first_name || ' ' || sr.last_name AS ae_name,
  sr.role,
  sr.region,
  sr.quota_usd,
  COALESCE(ap.open_opp_count, 0) AS open_opp_count,
  ROUND(COALESCE(ap.open_arr_usd, 0), 0) AS open_arr_usd,
  COALESCE(ap.late_stage_count, 0) AS late_stage_count,
  COALESCE(ast.stale_count, 0) AS stale_count,
  ROUND(100.0 * COALESCE(ast.stale_count, 0)
        / NULLIF(ap.open_opp_count, 0), 1) AS stale_pct
FROM sales_rep sr
LEFT JOIN ae_pipeline ap ON ap.owner_ae_id = sr.id
LEFT JOIN ae_stale ast ON ast.owner_ae_id = sr.id
WHERE sr.role LIKE 'AE_%' AND sr.is_active = 1
ORDER BY open_arr_usd DESC;
```

**预期结果说明：** ~24 行（每位活跃 AE 一行）。AE_Enterprise 代表会在 ARR 上占主导（大单）；AE_SMB 的 opp 多但金额小。stale_pct >25% 是强干预信号。

---

## D9: 活跃 campaign 计划 vs 实际跟踪

**Dashboard:** Active Campaign Tracker

**业务背景：** Demand Gen Manager 跟踪 ACTIVE 状态的 campaign，确保它们正按计划达成目标（`target_mql_count`、`target_pipeline_usd`）。如果某个 campaign 跑完 50% 的运行时间却只完成 20% 的 MQL 目标，就是表现不佳。

> 影响管道 Note：此查询使用 **首次触点归因**（`lead.source_campaign_id`），这是 *计划 vs 实际* 进度的正确视角——只有 campaign 真正引入的 lead 才会算到它自己的目标。要看跨 campaign 的账户级影响（任何在该账户内、任意时刻接触过该 campaign 的人），见 B8 / B10 / B12 以及 ER 文档 §11.2 KPI Dictionary 中 "Influenced Pipeline" 一条。两种定义不可互换，得出的数字也会不同。

**Category:** Multi-Join + Aggregation
**Difficulty:** Intermediate
**Business Role:** Demand Gen Manager

**解题思路：** 这条要把 ACTIVE campaign 的「计划」(目标字段) 和「实际」(三类口径) 并排放。计划值直接来自 `campaign` 表。实际值有三块，粒度互不相同，所以拆成三个 CTE：`camp_actuals` 算成员数和已过时间百分比 (用 `JULIANDAY` 比当前日和起止日)；`camp_mqls` 数实际 MQL；`camp_pipeline` 算影响管道。MQL 这块有个经典坑：成员可能通过 lead 路径或 contact 路径加入 (XOR 外键)，要把两条路径都覆盖，所以用 `COUNT(DISTINCT COALESCE('L'||l.id, 'C'||ct.lead_id))` 给两个 id 空间加前缀去重，避免 lead.id 和 contact 关联的 lead.id 撞车。影响管道这块用 account_id 把成员的两条路径汇聚，再 join 到该 account 在成员互动之后创建的 opp。这里 campaign 与 campaign_member 之间是一对多，所以每个口径都先在自己的 CTE 里聚合干净，再回到 `camp_actuals` 上 LEFT JOIN，绝不能把三类一锅 join，否则会扇出重复。一行代表一个 ACTIVE campaign。

```sql
WITH camp_actuals AS (
  SELECT
    c.id AS campaign_id,
    c.campaign_name,
    c.campaign_type,
    c.start_date,
    c.end_date,
    c.target_mql_count,
    c.target_pipeline_usd,
    c.total_budget_usd,
    c.spend_to_date_usd,
    COUNT(DISTINCT cm.id) AS members_count,
    -- 已过时间 %
    100.0 * (JULIANDAY('2026-06-01') - JULIANDAY(c.start_date))
          / NULLIF(JULIANDAY(c.end_date) - JULIANDAY(c.start_date), 0) AS pct_time_elapsed
  FROM campaign c
  LEFT JOIN campaign_member cm ON cm.campaign_id = c.id
  WHERE c.status = 'ACTIVE'
  GROUP BY c.id
),
camp_mqls AS (
  -- 计入通过 lead 路径或 contact 路径触及该 campaign 的 MQL。
  -- （旧版本只算 lead.source_campaign_id，漏掉了约 25% 通过 contact_id
  -- 加入的 campaign_member。）
  SELECT
    c.id AS campaign_id,
    COUNT(DISTINCT COALESCE('L'||l.id, 'C'||ct.lead_id)) AS mqls_attributed
  FROM campaign c
  JOIN campaign_member cm ON cm.campaign_id = c.id
  LEFT JOIN lead l    ON l.id = cm.lead_id    AND l.mql_date    IS NOT NULL
  LEFT JOIN contact ct ON ct.id = cm.contact_id AND ct.lead_id   IS NOT NULL
  LEFT JOIN lead l2   ON l2.id = ct.lead_id    AND l2.mql_date  IS NOT NULL
  WHERE c.status = 'ACTIVE'
    AND (l.id IS NOT NULL OR l2.id IS NOT NULL)
  GROUP BY c.id
),
camp_pipeline AS (
  -- 通过 account 触达的管道：lead 路径和 contact 路径最终都落到 account_id。
  SELECT
    c.id AS campaign_id,
    SUM(o.amount_usd) AS influenced_pipeline_usd
  FROM campaign c
  JOIN campaign_member cm ON cm.campaign_id = c.id
  LEFT JOIN lead l    ON l.id = cm.lead_id
  LEFT JOIN contact ct ON ct.id = cm.contact_id
  JOIN account a ON a.id = COALESCE(l.account_id, ct.account_id)
  JOIN opportunity o ON o.account_id = a.id
                     AND o.created_at >= cm.engaged_at
  WHERE c.status = 'ACTIVE'
  GROUP BY c.id
)
SELECT
  ca.campaign_id,
  ca.campaign_name,
  ca.campaign_type,
  ROUND(ca.pct_time_elapsed, 0) AS pct_time_elapsed,
  ca.members_count,
  ca.target_mql_count,
  COALESCE(cm.mqls_attributed, 0) AS mqls_actual,
  ROUND(100.0 * COALESCE(cm.mqls_attributed, 0)
        / NULLIF(ca.target_mql_count, 0), 0) AS pct_of_mql_target,
  ROUND(ca.target_pipeline_usd, 0) AS target_pipeline_usd,
  ROUND(COALESCE(cp.influenced_pipeline_usd, 0), 0) AS pipeline_actual_usd,
  ROUND(100.0 * COALESCE(cp.influenced_pipeline_usd, 0)
        / NULLIF(ca.target_pipeline_usd, 0), 0) AS pct_of_pipeline_target,
  ROUND(100.0 * ca.spend_to_date_usd / NULLIF(ca.total_budget_usd, 0), 0) AS pct_budget_spent
FROM camp_actuals ca
LEFT JOIN camp_mqls cm ON cm.campaign_id = ca.campaign_id
LEFT JOIN camp_pipeline cp ON cp.campaign_id = ca.campaign_id
ORDER BY ca.pct_time_elapsed DESC;
```

**预期结果说明：** ~20–25 行（ACTIVE campaign）。有趣的对比是 `pct_of_mql_target` vs `pct_time_elapsed`——两者对于按计划推进的 campaign 应该大致相等；MQL 进度滞后超过 30 个百分点的 campaign 即为表现不佳。

---

## D10: 本周热门内容

**Dashboard:** Content Heatmap

**业务背景：** Content Marketing Manager 想知道本周哪些资产获得最多互动——下载量、平均停留时长，以及每个资产被哪个 persona 消费。这驱动下周的内容放大策略。

**Category:** Aggregation + Date Filter
**Difficulty:** Basic
**Business Role:** Content Marketing

**解题思路：** 这是一道直接的 join + 聚合，只碰 `content_asset` 和 `content_engagement`。用 INNER JOIN 是对的，因为本周没有任何互动的资产本来就不该上热门榜，不需要 LEFT JOIN 把零互动资产保留下来。日期过滤放在 WHERE 里用 `DATE('2026-06-01', '-7 days')` 卡近 7 天。一行代表一个资产，按互动数倒序取前 20。这里有一个数据建模上的坑要记住：`download` 和 `share` 事件的 `time_on_page_seconds` 被设成 0，所以算平均停留时长时必须用 `CASE WHEN engagement_type IN ('view','replay')` 把瞬时事件挡在 AVG 外面，否则平均停留会被一堆 0 拉低。下载量和浏览量则用条件求和分别统计。

```sql
SELECT
  ca.id,
  ca.asset_name,
  ca.asset_type,
  ca.topic_tag,
  ca.target_persona,
  COUNT(ce.id) AS engagements_7d,
  SUM(CASE WHEN ce.engagement_type = 'download' THEN 1 ELSE 0 END) AS downloads_7d,
  SUM(CASE WHEN ce.engagement_type = 'view' THEN 1 ELSE 0 END) AS views_7d,
  ROUND(AVG(CASE WHEN ce.engagement_type IN ('view','replay')
                 THEN ce.time_on_page_seconds END), 0) AS avg_dwell_seconds
FROM content_asset ca
JOIN content_engagement ce ON ce.content_asset_id = ca.id
WHERE DATE(ce.engaged_at) >= DATE('2026-06-01', '-7 days')
GROUP BY ca.id
ORDER BY engagements_7d DESC
LIMIT 20;
```

**预期结果说明：** 按 7 天互动数排名的前 20 个资产。通常被热门话题（API Observability、Kubernetes Monitoring）的 ebook/whitepaper 主导。view 类型互动的平均停留时间通常为 200–600 秒。

---

## D11: ABM Tier-1 7 天互动脉搏

**Dashboard:** ABM Pulse

**业务背景：** ABM Lead 每周一查看：Tier-1 目标账户中，谁在过去 7 天有触点，谁已经 14 天+ 未被触及。Tier-1 账户长时间不触及是紧急情况——必须重启外联。

**Category:** Multi-Join + Date
**Difficulty:** Intermediate
**Business Role:** ABM Lead

**解题思路：** 难点是「触点」分散在三张事件表 (`campaign_member`、`content_engagement`、`sales_email`)，而每张表又因为 XOR 外键既能挂 lead 又能挂 contact，于是一个账户的最后触达时间要从六条路径里取最大值。这里用 `UNION ALL` 把六个分支拼成一个统一的触点流 (每条记录是账户 id 加触达时间)，再按 account 取 `MAX(touch_dt)` 得到 `acct_last_touch`。先用 `abm_accounts` 把 Tier-1 目标账户筛出来，再 LEFT JOIN 这个最后触点 CTE，LEFT 很关键，因为「从未被触达」的冷账户恰恰是 ABM Lead 最该看的，INNER 会把它们丢掉。`days_since_touch` 用 JULIANDAY 算天数差，再用 CASE 分成 HOT / WARM / COLD 几档。排序用 `days_since_touch IS NOT NULL, ... DESC` 把 NULL (从未触达) 顶到最前面。一行代表一个 Tier-1 账户。

```sql
WITH abm_accounts AS (
  SELECT DISTINCT tal.account_id, tal.list_name, tal.tier
  FROM target_account_list tal
  WHERE tal.tier = 'Tier 1'
),
acct_last_touch AS (
  SELECT a.id AS account_id,
    MAX(DATE(touch_dt)) AS last_touch_date
  FROM account a
  LEFT JOIN (
    -- Campaign-member 触点（两个 XOR 分支）
    SELECT c.account_id, cm.engaged_at AS touch_dt
    FROM contact c
    JOIN campaign_member cm ON cm.contact_id = c.id
    UNION ALL
    SELECT l.account_id, cm.engaged_at AS touch_dt
    FROM lead l
    JOIN campaign_member cm ON cm.lead_id = l.id
    UNION ALL
    -- Content engagement 触点（两个 XOR 分支）
    SELECT c.account_id, ce.engaged_at AS touch_dt
    FROM contact c
    JOIN content_engagement ce ON ce.contact_id = c.id
    UNION ALL
    SELECT l.account_id, ce.engaged_at AS touch_dt
    FROM lead l
    JOIN content_engagement ce ON ce.lead_id = l.id
    UNION ALL
    -- Sales-email 触点（两个 XOR 分支）
    SELECT c.account_id, se.sent_at AS touch_dt
    FROM contact c
    JOIN sales_email se ON se.recipient_contact_id = c.id
    UNION ALL
    SELECT l.account_id, se.sent_at AS touch_dt
    FROM lead l
    JOIN sales_email se ON se.recipient_lead_id = l.id
  ) touches ON touches.account_id = a.id
  GROUP BY a.id
)
SELECT
  ab.account_id,
  acc.company_name,
  acc.account_tier,
  acc.industry_id,
  alt.last_touch_date,
  CAST(JULIANDAY('2026-06-01') - JULIANDAY(alt.last_touch_date) AS INT) AS days_since_touch,
  CASE
    WHEN alt.last_touch_date >= DATE('2026-06-01','-7 days') THEN 'HOT (touched <=7d)'
    WHEN alt.last_touch_date >= DATE('2026-06-01','-14 days') THEN 'WARM'
    WHEN alt.last_touch_date IS NULL THEN 'COLD (never touched)'
    ELSE 'COLD (14+d no touch) — ALERT'
  END AS engagement_status
FROM abm_accounts ab
JOIN account acc ON acc.id = ab.account_id
LEFT JOIN acct_last_touch alt ON alt.account_id = ab.account_id
-- 可移植的 DESC "NULLS FIRST"（在 SQLite < 3.30 也能用）
ORDER BY days_since_touch IS NOT NULL, days_since_touch DESC
LIMIT 50;
```

**预期结果说明：** ~50 个 Tier-1 ABM 账户按 `days_since_touch` 排序（最差在前）。顶部的冷账户是紧急行动项；HOT/WARM 行是健康的。典型分布：60% HOT、25% WARM、15% COLD。

---

## D12: 停滞 opportunity 告警（30 天+）

**Dashboard:** Stale Opp Alert

**业务背景：** AE Manager / VP Sales 每周跑此查询。任何 30 天+ 无 stage_transition 的开放 opportunity 都有风险。拥有它的 AE 必须要么推进它要么关掉它。（SDR 通常在 SQL 时移交，此后不再管理阶段卫生。）

**Category:** Date Difference
**Difficulty:** Basic
**Business Role:** VP Sales

**解题思路：** 要找的是「30 天以上没有任何阶段流转的开放 opp」。从 `opportunity` 出发 join `opportunity_stage` (筛 `is_closed = 0`)，再 join `account`、`sales_rep` 把公司名和 AE 名带出来，最后 join `stage_transition` 取流转记录。因为一个 opp 有多条流转记录 (一对多)，所以要 `GROUP BY o.id` 再用 `MAX(st.transitioned_at)` 取最近一次流转时间，否则会一个 opp 出多行。停滞天数用 `JULIANDAY('2026-06-01') - JULIANDAY(MAX(...))` 算，放在 `HAVING` 里过滤 (而不是 WHERE)，因为它依赖聚合结果。这里用 INNER JOIN stage_transition 是安全的，因为每个 opp 至少有一条初始流转记录，不会漏。一行代表一个停滞的开放 opp，按停滞天数倒序。

```sql
SELECT
  o.id AS opp_id,
  o.opportunity_name,
  a.company_name,
  s.stage_name,
  o.amount_usd,
  sr.first_name || ' ' || sr.last_name AS ae_name,
  DATE(o.created_at) AS opp_created,
  DATE(MAX(st.transitioned_at)) AS last_transition_date,
  CAST(JULIANDAY('2026-06-01') - JULIANDAY(MAX(st.transitioned_at)) AS INT) AS days_since_transition,
  o.expected_close_date
FROM opportunity o
JOIN opportunity_stage s ON s.id = o.current_stage_id
JOIN account a ON a.id = o.account_id
JOIN sales_rep sr ON sr.id = o.owner_ae_id
JOIN stage_transition st ON st.opportunity_id = o.id
WHERE s.is_closed = 0
GROUP BY o.id
HAVING days_since_transition >= 30
ORDER BY days_since_transition DESC;
```

**预期结果说明：** ~30–60 个停滞的开放 opp。days_since_transition 较大（90+）的最紧急。同一 AE 名下多个停滞 opp 通常说明其负载或动力存在问题。

---

## D13: MQL 老化分桶

**Dashboard:** MQL Aging

**业务背景：** Marketing Ops 想看按年龄分类的未处理 MQL 库存。新鲜 MQL（0-7 天）是正常的；老 MQL（30 天+）说明 SDR 转化处存在瓶颈。

**Category:** Date Bucketing
**Difficulty:** Basic
**Business Role:** Marketing Ops

**解题思路：** 这条只碰 `lead` 一张表，逻辑很直白：把仍处于 `mql` 状态 (即还没被 SDR 转成 SQL 也没被取消资格) 的 lead，按「成为 MQL 至今的天数」分桶计数。年龄用 `JULIANDAY('2026-06-01') - JULIANDAY(mql_date)` 算，再 CAST 成整数，包在 CASE 里切成五档。WHERE 里同时卡 `mql_date IS NOT NULL` 和 `status = 'mql'` 很关键，后者保证只数「未处理」的 MQL 库存，不把已经往下走的 lead 算进来。GROUP BY 直接对 CASE 算出的 `age_bucket` 分组就行，不需要 CTE 或窗口函数。唯一要注意的是排序：桶是字符串，字母序会乱，所以用一个 CASE 把桶映射成 1 到 5 再排，让结果按年龄从新到老呈现。一行代表一个年龄桶。

```sql
SELECT
  CASE
    WHEN CAST(JULIANDAY('2026-06-01') - JULIANDAY(mql_date) AS INT) <= 7   THEN '0-7d (fresh)'
    WHEN CAST(JULIANDAY('2026-06-01') - JULIANDAY(mql_date) AS INT) <= 14  THEN '8-14d'
    WHEN CAST(JULIANDAY('2026-06-01') - JULIANDAY(mql_date) AS INT) <= 30  THEN '15-30d'
    WHEN CAST(JULIANDAY('2026-06-01') - JULIANDAY(mql_date) AS INT) <= 60  THEN '31-60d'
    ELSE '60+d (STALE)'
  END AS age_bucket,
  COUNT(*) AS unworked_mql_count,
  ROUND(AVG(lead_score), 0) AS avg_lead_score
FROM lead
WHERE mql_date IS NOT NULL
  AND status = 'mql'  -- 仍在 MQL 状态（尚未 SQL 或取消资格）
GROUP BY age_bucket
ORDER BY
  CASE age_bucket
    WHEN '0-7d (fresh)' THEN 1
    WHEN '8-14d' THEN 2
    WHEN '15-30d' THEN 3
    WHEN '31-60d' THEN 4
    ELSE 5
  END;
```

**预期结果说明：** 5 个桶。健康的分布会把大多数 MQL 集中在 0-14d。'60+d STALE' 桶过重说明 SDR 容量有问题。

---

## D14: 经理团队汇总（通过自连接 FK 的 Won ARR）

**Dashboard:** Manager Rollup

**业务背景：** VP Sales 审视每位 Manager 的团队级表现：所有直属下属的 Won ARR 总和。本查询练习 `sales_rep.manager_id` 自连接 FK。

**Category:** Self-Join
**Difficulty:** Intermediate
**Business Role:** VP Sales

**解题思路：** 这条练的是 `sales_rep.manager_id` 自引用 FK：每个 AE 有个 manager_id 指向同表的另一行。目标是把每位 manager 下属的 Won ARR 加总到 manager 这一层。最大的坑是想一步到位：如果直接对 `opportunity` 同时做 won 和 open 两次 join，会产生笛卡尔积让金额翻倍。正确做法是先在 `ae_metrics` CTE 里把每个 AE 的 won/open ARR 用一次 join 加 CASE 聚合干净 (一个 AE 一行)，再把这个结果按 `manager_id` roll up 到 manager。外层从 `sales_rep` 取 role 为 Manager 的行，LEFT JOIN ae_metrics，让暂时没有下属或下属没业绩的 manager 也显示 (补 0)。注意这里 `manager_id` 关联 AE，而 manager 自己的 `manager_id` 是 NULL。一行代表一位 manager。

```sql
-- 先按 AE 聚合以避免双连接的笛卡尔积膨胀
WITH ae_metrics AS (
  SELECT
    r.manager_id,
    r.id AS rep_id,
    SUM(CASE WHEN s.is_won = 1 THEN o.amount_usd ELSE 0 END) AS won_arr,
    SUM(CASE WHEN s.is_closed = 0 THEN o.amount_usd ELSE 0 END) AS open_arr,
    SUM(CASE WHEN s.is_won = 1 THEN 1 ELSE 0 END) AS won_cnt
  FROM sales_rep r
  LEFT JOIN opportunity o ON o.owner_ae_id = r.id
  LEFT JOIN opportunity_stage s ON s.id = o.current_stage_id
  WHERE r.is_active = 1
  GROUP BY r.id
)
SELECT
  m.id AS manager_id,
  m.first_name || ' ' || m.last_name AS manager_name,
  m.region AS manager_region,
  COUNT(ae.rep_id) AS team_size,
  COALESCE(SUM(ae.won_cnt), 0) AS won_opp_count,
  ROUND(COALESCE(SUM(ae.won_arr), 0), 0) AS team_won_arr_usd,
  ROUND(COALESCE(SUM(ae.open_arr), 0), 0) AS team_open_arr_usd
FROM sales_rep m
LEFT JOIN ae_metrics ae ON ae.manager_id = m.id
WHERE m.role = 'Manager'
GROUP BY m.id
ORDER BY team_won_arr_usd DESC;
```

**预期结果说明：** 4 行（每位 Manager 一行）。每行展示团队规模、Won ARR 总和、直属下属的开放 ARR 总和。NA-East 与 NA-West 的 manager 通常占主导。

> Note：早期版本对 `opportunity` 做了两次 JOIN（一次为 won，一次为 open）——这会导致行膨胀的笛卡尔积。上面 CTE 先按 AE 聚合，再 roll up 到 manager，是"同一表上两个聚合"的正确模式。

---

## D15: 今日加权预测

**Dashboard:** Forecast

**业务背景：** RevOps 发布每日预测 = Σ（开放 opportunity ARR × 阶段胜率）。这是最基础的预测启发式方法，用作对更复杂模型的合理性检查。

**Category:** Aggregation
**Difficulty:** Basic
**Business Role:** RevOps

**解题思路：** 加权预测就是「每个开放 opp 的金额 × 其阶段的成单概率」之和，所以核心是 `opportunity` join `opportunity_stage` (筛 `is_closed = 0`)，按阶段 `GROUP BY s.id` 聚合，乘 `typical_win_probability_pct / 100` 得到加权值。要的不只是各阶段明细，还要一个总计行，所以用 `UNION ALL` 把同样的聚合再跑一遍但不分组，硬写一个 'TOTAL' 标签并给它 `stage_order = 99` 让它排在最后。这是 SQLite 里加汇总行的惯用手法 (没有 ROLLUP)。一行代表一个阶段 (外加一行总计)。这条够简单，不需要 CTE 或窗口，两个聚合 UNION 起来即可。

```sql
SELECT
  s.stage_name,
  s.stage_order,
  COUNT(o.id) AS opp_count,
  ROUND(SUM(o.amount_usd), 0) AS open_arr_usd,
  s.typical_win_probability_pct,
  ROUND(SUM(o.amount_usd * s.typical_win_probability_pct / 100.0), 0) AS weighted_forecast_usd
FROM opportunity o
JOIN opportunity_stage s ON s.id = o.current_stage_id
WHERE s.is_closed = 0
GROUP BY s.id
UNION ALL
SELECT
  'TOTAL' AS stage_name,
  99 AS stage_order,
  COUNT(o.id) AS opp_count,
  ROUND(SUM(o.amount_usd), 0) AS open_arr_usd,
  NULL AS typical_win_probability_pct,
  ROUND(SUM(o.amount_usd * s.typical_win_probability_pct / 100.0), 0) AS weighted_forecast_usd
FROM opportunity o
JOIN opportunity_stage s ON s.id = o.current_stage_id
WHERE s.is_closed = 0
ORDER BY stage_order;
```

**预期结果说明：** 5 个阶段行 + 1 个总计行。Negotiation 阶段（80% 概率）的 opp 数量虽最少，却对加权预测贡献不成比例。总加权预测通常为总开放 ARR 的 30–50%。

---

# 业务问题风格查询 (B1–B35)

这些查询回答多样化的临时分析问题。在技巧上更丰富，能挖掘数据中更深的关系。

---

## B1: 完整漏斗 — Lead → MQL → SQL → Opp → Won

**业务背景：** VP Marketing 想要一张关于 lead 在漏斗哪里死掉的统一视图。每一阶段的流失率帮助识别瓶颈。

**Category:** CTE + Aggregation
**Difficulty:** Intermediate
**Business Role:** VP Marketing

**解题思路：** 完整漏斗的前四级 (Total / MQL / SQL / Converted) 都能在 `lead` 一张表里靠对账好的日期和状态字段用条件计数算出来，所以 `funnel` CTE 一次扫表就把四个数全统计了。最后一级 Won 需要回 `opportunity` 反查中标的源 lead，单独做 `wins` CTE 取 `COUNT(DISTINCT source_lead_id)`，去重很重要，因为一个 lead 可能关联多个 Won opp。把结果摆成纵向漏斗用的是 `UNION ALL` 逐行拼接，每一行的转化率分母是上一级而不是总量 (MQL→SQL 除以 MQL 数，不是除以 total)，这样才能看出每一段的真实流失。这种「五个标量摆成五行」的形状用 UNION ALL 比 pivot 更直观。一行代表漏斗的一个层级。

```sql
WITH funnel AS (
  SELECT
    COUNT(*) AS total_leads,
    SUM(CASE WHEN mql_date IS NOT NULL THEN 1 ELSE 0 END) AS mql_count,
    SUM(CASE WHEN sql_date IS NOT NULL THEN 1 ELSE 0 END) AS sql_count,
    SUM(CASE WHEN status = 'converted_to_contact' THEN 1 ELSE 0 END) AS converted_count
  FROM lead
),
wins AS (
  SELECT COUNT(DISTINCT o.source_lead_id) AS won_lead_count
  FROM opportunity o
  JOIN opportunity_stage s ON s.id = o.current_stage_id
  WHERE s.is_won = 1 AND o.source_lead_id IS NOT NULL
)
SELECT
  'Total Leads' AS stage, f.total_leads AS count, NULL AS conv_pct FROM funnel f
UNION ALL
SELECT 'MQL', f.mql_count, ROUND(100.0 * f.mql_count / f.total_leads, 1) FROM funnel f
UNION ALL
SELECT 'SQL', f.sql_count, ROUND(100.0 * f.sql_count / f.mql_count, 1) FROM funnel f
UNION ALL
SELECT 'Converted', f.converted_count, ROUND(100.0 * f.converted_count / f.sql_count, 1) FROM funnel f
UNION ALL
SELECT 'Won', w.won_lead_count, ROUND(100.0 * w.won_lead_count / f.converted_count, 1)
FROM funnel f, wins w;
```

**预期结果说明：** 5 行展示漏斗。Lead→MQL ~35%，MQL→SQL ~20%，SQL→Converted ~75%，Converted→Won ~25%。最大的单一掉队是 MQL→SQL——SDR 资格审核瓶颈。

---

## B2: 按来源的 MQL 老化

**业务背景：** Marketing Ops 想知道是否有些 lead 来源产生的 MQL 更快老化为 SQL。MQL→SQL 转化快的来源质量更高。

**Category:** Date Math + Aggregation
**Difficulty:** Intermediate
**Business Role:** Marketing Ops

**解题思路：** 这条衡量每个来源的 MQL 质量，要从 `lead` join `lead_source`，只看已成 MQL 的 lead (`mql_date IS NOT NULL`)，按 `source_code` 聚合。两个核心指标：MQL→SQL 转化率用 `COUNT(sql_date) / COUNT(id)` 算 (COUNT 一个列会自动跳过 NULL，所以 `COUNT(l.sql_date)` 恰好就是成为 SQL 的数量，这是个干净的小技巧)；老化速度用 `AVG(JULIANDAY(sql_date) - JULIANDAY(mql_date))` 算从 MQL 到 SQL 的平均天数。INNER JOIN lead_source 没问题，因为 source_id 非空。`HAVING mql_count >= 5` 过滤掉样本太小、统计不可靠的来源。一行代表一个 lead source。

```sql
SELECT
  ls.source_code,
  ls.source_category,
  COUNT(l.id) AS mql_count,
  COUNT(l.sql_date) AS became_sql,
  ROUND(100.0 * COUNT(l.sql_date) / COUNT(l.id), 1) AS mql_to_sql_pct,
  ROUND(AVG(JULIANDAY(l.sql_date) - JULIANDAY(l.mql_date)), 1) AS avg_days_mql_to_sql
FROM lead l
JOIN lead_source ls ON ls.id = l.source_id
WHERE l.mql_date IS NOT NULL
GROUP BY ls.source_code
HAVING mql_count >= 5
ORDER BY mql_to_sql_pct DESC;
```

**预期结果说明：** 每个来源一行（≥ 5 个 MQL）。`INBOUND_DEMO_REQUEST` 和 `INBOUND_FREE_TRIAL` 通常转化最快（5–10 天，比例高）；`CONTENT_SYNDICATION` 最慢，比例最低。

---

## B3: Lead 评分十分位与胜率

**业务背景：** Marketing Ops 要验证 lead 评分模型。如果模型有效，顶部十分位评分的 lead 胜率应显著高于底部十分位。此查询用 NTILE 按评分十分位计算胜率。

**Category:** CTE + NTILE
**Difficulty:** Advanced
**Business Role:** Marketing Ops

**解题思路：** 验证评分模型的思路是「按分数把 lead 切成十等份，看胜率是否随十分位单调上升」。先在 `lead_with_won` CTE 里给每个 lead 打 Won 标志，方法是 LEFT JOIN 一个去重的中标源 lead 子查询 (`source_lead_id` 来自 Won opp)，LEFT 是必须的，否则只剩中标 lead，胜率就失真了。过滤 `lead_score > 0` 排除从没打过分的 lead。然后 `deciles` CTE 用窗口函数 `NTILE(10) OVER (ORDER BY lead_score)` 把 lead 按分数均分成 10 桶,这正是 NTILE 的标准用法,手写分桶很难保证每桶数量相等。最外层按十分位聚合算胜率,并带出每桶的分数区间。一行代表一个评分十分位,按十分位倒序让最高分桶排最前。

```sql
WITH lead_with_won AS (
  SELECT
    l.id,
    l.lead_score,
    CASE WHEN ow.lead_id IS NOT NULL THEN 1 ELSE 0 END AS is_won
  FROM lead l
  LEFT JOIN (
    SELECT DISTINCT o.source_lead_id AS lead_id
    FROM opportunity o
    JOIN opportunity_stage s ON s.id = o.current_stage_id
    WHERE s.is_won = 1 AND o.source_lead_id IS NOT NULL
  ) ow ON ow.lead_id = l.id
  WHERE l.lead_score > 0
),
deciles AS (
  SELECT
    id,
    lead_score,
    is_won,
    NTILE(10) OVER (ORDER BY lead_score) AS score_decile
  FROM lead_with_won
)
SELECT
  score_decile,
  MIN(lead_score) AS min_score,
  MAX(lead_score) AS max_score,
  COUNT(*) AS lead_count,
  SUM(is_won) AS won_count,
  ROUND(100.0 * SUM(is_won) / COUNT(*), 2) AS win_rate_pct
FROM deciles
GROUP BY score_decile
ORDER BY score_decile DESC;
```

**预期结果说明：** 10 行（十分位 1–10）。十分位 10（最高分）应显示最高胜率（~5–10%），十分位 1 最低（~0–1%）。单调递增的趋势可验证评分模型有效。

---

## B4: 取消资格原因 × 来源矩阵

**业务背景：** Marketing Ops 用此识别哪些 lead 来源带来错误类型的 lead。如果 `CONTENT_SYNDICATION` 的 "Not ICP" 占比高，那就是定位问题。

**Category:** Pivot + Aggregation
**Difficulty:** Intermediate
**Business Role:** Marketing Ops

**解题思路：** 这是一道把行转列的 pivot 题，目的是看「哪个来源贡献了哪种取消资格原因」。只碰 `lead` join `lead_source`，过滤 `status = 'disqualified'`，按 source_code 分组。SQLite 没有原生 PIVOT，所以用一组 `SUM(CASE WHEN disqualified_reason = '...' THEN 1 ELSE 0 END)` 手动把每个原因摊成一列,这是 SQLite 做透视的标准模式。一行代表一个来源,列是各取消原因的计数,外加一个总取消数。这里不需要 LEFT JOIN,因为只关心已经被取消资格的 lead,且 source_id 非空。读这张表是横向比 (某来源里哪种原因最多) 加纵向比 (某种原因主要来自哪些来源)。

```sql
SELECT
  ls.source_code,
  COUNT(*) AS total_disqualified,
  SUM(CASE WHEN l.disqualified_reason = 'Not ICP' THEN 1 ELSE 0 END) AS not_icp,
  SUM(CASE WHEN l.disqualified_reason = 'No budget' THEN 1 ELSE 0 END) AS no_budget,
  SUM(CASE WHEN l.disqualified_reason = 'Wrong contact' THEN 1 ELSE 0 END) AS wrong_contact,
  SUM(CASE WHEN l.disqualified_reason = 'Already a customer' THEN 1 ELSE 0 END) AS already_customer,
  SUM(CASE WHEN l.disqualified_reason = 'Company too small' THEN 1 ELSE 0 END) AS too_small,
  SUM(CASE WHEN l.disqualified_reason = 'Competitor incumbent' THEN 1 ELSE 0 END) AS competitor
FROM lead l
JOIN lead_source ls ON ls.id = l.source_id
WHERE l.status = 'disqualified'
GROUP BY ls.source_code
ORDER BY total_disqualified DESC;
```

**预期结果说明：** ~10 行。用于定位问题：例如，如果 `PAID_SEARCH_GOOGLE` 的 `not_icp` 高，说明 SEM 关键字策略需要打磨。

---

## B5: Persona × 资历转化矩阵

**业务背景：** Marketing Ops 想理解哪些买家画像真的会转化。一张 persona × seniority 的网格展示 Lead→Won 转化率，揭示我们最适配的 ICP。

**Category:** Pivot + Aggregation
**Difficulty:** Intermediate
**Business Role:** Marketing Ops

**解题思路：** 想看哪种「persona × seniority」组合最容易成单。先在 `lead_outcomes` CTE 里给每个 lead 贴上 persona、seniority 和 Won 标志,Won 标志同样靠 LEFT JOIN 去重的中标源 lead 子查询得到 (LEFT 保留没成单的 lead 进分母)。然后按 persona 和 seniority 两列分组算胜率。这本质是个二维矩阵,但要注意 generator 规则强烈地把每种 persona 绑到一种 seniority (见期望结果说明),所以 25 种组合里只有对角线上的几个能通过 `HAVING COUNT(*) >= 20` 的样本量门槛,其余格子样本太少会被滤掉。一行代表一个有足够样本的 persona-seniority 组合,按胜率倒序。

```sql
WITH lead_outcomes AS (
  SELECT
    l.persona,
    l.seniority,
    l.id AS lead_id,
    CASE WHEN ow.lead_id IS NOT NULL THEN 1 ELSE 0 END AS is_won
  FROM lead l
  LEFT JOIN (
    SELECT DISTINCT o.source_lead_id AS lead_id
    FROM opportunity o
    JOIN opportunity_stage s ON s.id = o.current_stage_id
    WHERE s.is_won = 1 AND o.source_lead_id IS NOT NULL
  ) ow ON ow.lead_id = l.id
)
SELECT
  persona,
  seniority,
  COUNT(*) AS lead_count,
  SUM(is_won) AS won_count,
  ROUND(100.0 * SUM(is_won) / COUNT(*), 2) AS win_rate_pct
FROM lead_outcomes
GROUP BY persona, seniority
HAVING COUNT(*) >= 20
ORDER BY win_rate_pct DESC;
```

**预期结果说明：** ~6-9 个格子。完整的 5×5 矩阵有 25 种逻辑组合，但 generator 规则 §4.7 强烈偏向把每种 persona 绑到一种 seniority 上（Champion-Manager、Economic Buyer-Director、Decision Maker-VP、Influencer-IC、Blocker-Director），所以对角线之外的格子达不到 `HAVING COUNT(*) >= 20` 过滤。可见的行基本就是对角线：Champion-Manager、EB-Director、DM-VP、Influencer-IC、Blocker-Director。Blocker 行的胜率应接近 0（他们不推动交易；他们阻碍交易）。要看完整矩阵，请把 HAVING 阈值降到 5。

---

## B6: 多次访问 lead 行为提升

**业务背景：** 假设：7 天内出现多个评分事件的 lead 比单事件 lead 转化率更高。本查询验证"互动强度"信号。

**Category:** Window + Filter
**Difficulty:** Advanced
**Business Role:** Analyst

**解题思路：** 假设是「7 天内有多个高意图评分事件的 lead 转化更好」。先用 `multi_visit` CTE 从 `lead_scoring_event` 里挑出触发过 `multiple_visits_7d`、`page_visit_pricing`、`pricing_calc_used` 这类强意图事件的 lead (去重)。再在 `lead_outcomes` 里用两个 LEFT JOIN：一个标 lead 是否属于多次访问组,一个标它是否成单。两个都得是 LEFT JOIN,因为我们要把全体 lead 都分成 Multi-Visit 和 Single-Visit 两类,任何一个 INNER 都会把没成单或没多访问的 lead 砍掉,破坏对照组。最后按 `visit_class` 分两组比胜率。这里虽然挂了 Window + Filter 标签,实际靠的是 DISTINCT 子集加 LEFT JOIN 标记的写法,简单清晰。一行代表一个访问类别 (共两行)。

```sql
WITH multi_visit AS (
  SELECT DISTINCT lead_id
  FROM lead_scoring_event
  WHERE event_type IN ('multiple_visits_7d', 'page_visit_pricing', 'pricing_calc_used')
),
lead_outcomes AS (
  SELECT
    l.id AS lead_id,
    CASE WHEN mv.lead_id IS NOT NULL THEN 'Multi-Visit' ELSE 'Single-Visit' END AS visit_class,
    CASE WHEN ow.lead_id IS NOT NULL THEN 1 ELSE 0 END AS is_won
  FROM lead l
  LEFT JOIN multi_visit mv ON mv.lead_id = l.id
  LEFT JOIN (
    SELECT DISTINCT o.source_lead_id AS lead_id
    FROM opportunity o
    JOIN opportunity_stage s ON s.id = o.current_stage_id
    WHERE s.is_won = 1 AND o.source_lead_id IS NOT NULL
  ) ow ON ow.lead_id = l.id
)
SELECT
  visit_class,
  COUNT(*) AS lead_count,
  SUM(is_won) AS won_count,
  ROUND(100.0 * SUM(is_won) / COUNT(*), 2) AS win_rate_pct
FROM lead_outcomes
GROUP BY visit_class;
```

**预期结果说明：** 2 行。多次访问 lead 的胜率应比单次访问 lead 高 3–5 倍，验证"互动强度很重要"的假设。

---

## B7: Lead 来源质量随季度衰减

**业务背景：** 假设：来源排名会随时间漂移。Q1 的 #1 来源可能是 Q4 的 #4。此查询计算每季度每来源的胜率。

**Category:** CTE + Date Bucketing
**Difficulty:** Advanced
**Business Role:** Analyst

**解题思路：** 这条要看每个来源的胜率是否随季度漂移。`lead_q` CTE 把每个 lead 按 `created_at` 分到季度桶,并 join `lead_source` 带出 source_code。`wins` CTE 取去重的中标源 lead。两者按 lead id LEFT JOIN (保留没成单的 lead 进分母),再按「季度 × 来源」两维分组算胜率。注意分组粒度是二维的,所以一行代表「某季度的某来源」,这和 B2 (只按来源) 的区别就在多了时间维度。`HAVING lead_count >= 20` 滤掉样本太小的格子,免得几个 lead 的偶然成单造成 100% 的假高胜率。季度桶照例用 STRFTIME 把月换算成 Q。读法是固定一个来源沿季度看它的胜率稳不稳。

```sql
WITH lead_q AS (
  SELECT
    l.id,
    ls.source_code,
    STRFTIME('%Y', l.created_at) || '-Q' ||
      ((CAST(STRFTIME('%m', l.created_at) AS INT) - 1) / 3 + 1) AS cohort_q
  FROM lead l
  JOIN lead_source ls ON ls.id = l.source_id
),
wins AS (
  SELECT DISTINCT o.source_lead_id AS lead_id
  FROM opportunity o
  JOIN opportunity_stage s ON s.id = o.current_stage_id
  WHERE s.is_won = 1 AND o.source_lead_id IS NOT NULL
)
SELECT
  lq.cohort_q,
  lq.source_code,
  COUNT(lq.id) AS lead_count,
  SUM(CASE WHEN w.lead_id IS NOT NULL THEN 1 ELSE 0 END) AS won_count,
  ROUND(100.0 * SUM(CASE WHEN w.lead_id IS NOT NULL THEN 1 ELSE 0 END) / COUNT(lq.id), 2) AS win_rate_pct
FROM lead_q lq
LEFT JOIN wins w ON w.lead_id = lq.id
GROUP BY lq.cohort_q, lq.source_code
HAVING lead_count >= 20
ORDER BY lq.cohort_q DESC, win_rate_pct DESC;
```

**预期结果说明：** ~40–60 行（6 季度 × ~10 来源，减去低计数格子）。在各季度间稳定高胜率的来源才是可持续的；表现波动剧烈的是不可靠渠道。

---

## B8: 按影响管道的顶尖 campaign

**业务背景：** Demand Gen Manager 想庆祝（并加码）影响最多 Won 管道的 campaign。影响管道 = 该账户在此 campaign 上至少有一条 campaign_member 记录的 Won opp 的 ARR 总和。

**Category:** Multi-Join + Aggregation
**Difficulty:** Intermediate
**Business Role:** Demand Gen Manager

**解题思路：** 影响管道是账户级口径：只要某账户在某 campaign 上有过 campaign_member 记录,且之后该账户成单,就算这个 campaign 影响了那笔 Won。链路是 campaign → campaign_member → (lead 或 contact 的) account → 该 account 的 Won opp。最大的坑是同一账户里同一个 campaign 可能有多个成员,join 到同一笔 opp 上会扇出多行,直接 SUM 金额会重复计数。所以先在 `camp_opp` CTE 里用 `SELECT DISTINCT campaign_id, opp_id, amount` 把 (campaign × opp) 去重成唯一对,再在外层 SUM 金额。不能图省事写 `SUM(DISTINCT amount)`,因为两笔金额恰好相同的 opp 会被误删一笔。`o.created_at >= cm.engaged_at` 保证「影响」的因果顺序 (触点要早于 opp)。一行代表一个 campaign,按影响 Won ARR 倒序取前 20。

```sql
-- 先在 CTE 里去重 (campaign × opp)，再 SUM。避免 SUM(DISTINCT amount)，
-- 因为它会悄悄丢掉金额恰好相同的 opp。
WITH camp_opp AS (
  SELECT DISTINCT c.id AS campaign_id, o.id AS opp_id, o.amount_usd
  FROM campaign c
  JOIN campaign_member cm ON cm.campaign_id = c.id
  LEFT JOIN lead l    ON l.id = cm.lead_id
  LEFT JOIN contact ct ON ct.id = cm.contact_id
  JOIN account a ON a.id = COALESCE(l.account_id, ct.account_id)
  JOIN opportunity o ON o.account_id = a.id
                     AND o.created_at >= cm.engaged_at        -- 影响要求触点早于 opp
  JOIN opportunity_stage s ON s.id = o.current_stage_id
  WHERE s.is_won = 1
)
SELECT
  c.id AS campaign_id,
  c.campaign_name,
  c.campaign_type,
  c.start_date,
  COUNT(co.opp_id) AS influenced_won_opps,
  ROUND(COALESCE(SUM(co.amount_usd), 0), 0) AS influenced_won_arr_usd,
  ROUND(c.spend_to_date_usd, 0) AS campaign_spend_usd,
  ROUND(COALESCE(SUM(co.amount_usd), 0) / NULLIF(c.spend_to_date_usd, 0), 1) AS roi_ratio
FROM campaign c
LEFT JOIN camp_opp co ON co.campaign_id = c.id
GROUP BY c.id
HAVING influenced_won_opps > 0
ORDER BY influenced_won_arr_usd DESC
LIMIT 20;
```

**预期结果说明：** 按 Won ARR 排名的前 20 个 campaign。ABM_Sequence 和 Conference_Event campaign 通常领先，因为它们瞄准高价值账户。Webinar campaign 也常出现，因其中漏斗影响力强。

---

## B9: Webinar 端到端漏斗

**业务背景：** Content Marketing 想度量某个 webinar 的完整生命周期：注册 → 出席 → 成为 MQL → 成为 SQL → opp → Won。每一步的掉队帮助调整 webinar 质量和跟进 sequence。

**Category:** CTE + Multi-Join
**Difficulty:** Advanced
**Business Role:** Content Marketing

**解题思路：** webinar 的完整生命周期 (注册 → 出席 → MQL → opp → Won) 跨多张表,每一级的粒度不同,所以拆成四个 CTE 各算各的,最后以 `webinars` 为主表逐个 LEFT JOIN 拼起来 (LEFT 保证某些环节为 0 的 webinar 也保留)。`members` 从 `campaign_member` 按 member_role 数注册/出席/缺席。`mqls` 要数成为 MQL 的参与者,这里又遇到 XOR 路径:成员可能是 lead (直接看 mql_date),也可能是 contact (要回头看它关联的 lead 有没有 mql_date,用 EXISTS 子查询判断),所以用 `COUNT(DISTINCT COALESCE('L'||l.id, 'C'||ct.id))` 加前缀去重跨两个 id 空间。`opps` 通过 account_id 把成员汇聚到机会上,数 opp 和 Won ARR。这道题的训练点就是「一个端到端漏斗,每级单独聚合再 join 回主键」,千万别想用一条大 join 把所有级别一次算出来,扇出会让数全错。一行代表一个 webinar campaign。

```sql
WITH webinars AS (
  SELECT id, campaign_name FROM campaign WHERE campaign_type = 'Webinar'
),
members AS (
  SELECT
    cm.campaign_id,
    COUNT(*) AS registered,
    SUM(CASE WHEN cm.member_role = 'attended' THEN 1 ELSE 0 END) AS attended,
    SUM(CASE WHEN cm.member_role = 'no_show' THEN 1 ELSE 0 END) AS no_show
  FROM campaign_member cm
  JOIN webinars w ON w.id = cm.campaign_id
  GROUP BY cm.campaign_id
),
mqls AS (
  -- 通过 lead 路径或 contact 路径（contact 关联的 lead 已有 mql_date）计算 MQL 等价的出席者
  SELECT cm.campaign_id,
         COUNT(DISTINCT COALESCE('L'||l.id, 'C'||ct.id)) AS mql_count
  FROM campaign_member cm
  JOIN webinars w ON w.id = cm.campaign_id
  LEFT JOIN lead l    ON l.id = cm.lead_id    AND l.mql_date IS NOT NULL
  LEFT JOIN contact ct ON ct.id = cm.contact_id
                       AND EXISTS (SELECT 1 FROM lead lx
                                    WHERE lx.id = ct.lead_id
                                      AND lx.mql_date IS NOT NULL)
  WHERE l.id IS NOT NULL OR ct.id IS NOT NULL
  GROUP BY cm.campaign_id
),
opps AS (
  -- 通过 account_id 触达 opportunity（lead 路径 + contact 路径都汇聚到 account）。
  SELECT cm.campaign_id,
         COUNT(DISTINCT o.id) AS opp_count,
         SUM(CASE WHEN s.is_won = 1 THEN o.amount_usd ELSE 0 END) AS won_arr
  FROM campaign_member cm
  JOIN webinars w ON w.id = cm.campaign_id
  LEFT JOIN lead l    ON l.id = cm.lead_id
  LEFT JOIN contact ct ON ct.id = cm.contact_id
  JOIN account a ON a.id = COALESCE(l.account_id, ct.account_id)
  JOIN opportunity o ON o.account_id = a.id
                     AND o.created_at >= cm.engaged_at
  JOIN opportunity_stage s ON s.id = o.current_stage_id
  GROUP BY cm.campaign_id
)
SELECT
  w.id AS campaign_id, w.campaign_name,
  COALESCE(m.registered, 0) AS registered,
  COALESCE(m.attended, 0) AS attended,
  ROUND(100.0 * COALESCE(m.attended, 0) / NULLIF(m.registered, 0), 1) AS attend_pct,
  COALESCE(mq.mql_count, 0) AS mql_count,
  COALESCE(op.opp_count, 0) AS opp_count,
  ROUND(COALESCE(op.won_arr, 0), 0) AS won_arr_usd
FROM webinars w
LEFT JOIN members m ON m.campaign_id = w.id
LEFT JOIN mqls mq ON mq.campaign_id = w.id
LEFT JOIN opps op ON op.campaign_id = w.id
ORDER BY won_arr_usd DESC;
```

**预期结果说明：** 每个 webinar 一行（~15 行）。典型 webinar 漏斗：100 注册 → 60% 出席 → 20% MQL → 5% opp → 1–2% Won。顶尖 webinar 在每一步转化都更好。

---

## B10: Campaign 类型 ROI 对比

**业务背景：** Demand Gen Manager 想要正面对决：Webinar vs Paid Search vs ABM Sequence vs Conference——哪种类型在每美元支出转化为 Won ARR 上最高效？

**Category:** Aggregation + Join
**Difficulty:** Intermediate
**Business Role:** Demand Gen Manager

**解题思路：** 这是 B8 的「按类型汇总」版:把影响管道和支出都聚合到 `campaign_type` 这一维,比较每种类型的 ROI。和 B8 一样的去重坑:`type_opp` 先用 `SELECT DISTINCT campaign_type, opp_id, amount` 把 (类型 × opp) 去重,免得同账户多触点把金额重复 SUM。支出是另一个粒度,所以单独的 `type_spend` CTE 按类型加总 `spend_to_date_usd` 并数 campaign 个数。两个 CTE 按 campaign_type 用 LEFT JOIN 拼接 (从 type_spend 出发,保证有支出但零 Won 的类型也出现,ROI 会因分子为 0 而是 0)。这里只看 `status = 'COMPLETED'` 的 campaign,因为只有跑完的活动算 ROI 才公平。一行代表一种 campaign 类型,按 ROI 倒序。

```sql
-- Step 1：先对 (campaign_type × opp) 去重，避免单账户多触点导致行膨胀。
-- Step 2：单独聚合支出，然后在 SELECT 中 join。
WITH type_opp AS (
  SELECT DISTINCT c.campaign_type, o.id AS opp_id, o.amount_usd
  FROM campaign c
  JOIN campaign_member cm ON cm.campaign_id = c.id
  LEFT JOIN lead l    ON l.id = cm.lead_id
  LEFT JOIN contact ct ON ct.id = cm.contact_id
  JOIN account a ON a.id = COALESCE(l.account_id, ct.account_id)
  JOIN opportunity o ON o.account_id = a.id
                     AND o.created_at >= cm.engaged_at
  JOIN opportunity_stage s ON s.id = o.current_stage_id
  WHERE c.status = 'COMPLETED' AND s.is_won = 1
),
type_spend AS (
  SELECT campaign_type,
         COUNT(*) AS campaign_count,
         SUM(spend_to_date_usd) AS total_spend_usd
  FROM campaign WHERE status = 'COMPLETED' GROUP BY campaign_type
)
SELECT
  ts.campaign_type,
  ts.campaign_count,
  ROUND(ts.total_spend_usd, 0) AS total_spend_usd,
  COUNT(tp.opp_id) AS influenced_won_opps,
  ROUND(COALESCE(SUM(tp.amount_usd), 0), 0) AS won_arr_usd,
  ROUND(COALESCE(SUM(tp.amount_usd), 0) / NULLIF(ts.total_spend_usd, 0), 2) AS roi_ratio
FROM type_spend ts
LEFT JOIN type_opp tp ON tp.campaign_type = ts.campaign_type
GROUP BY ts.campaign_type
ORDER BY roi_ratio DESC;
```

**预期结果说明：** 8 行（每种 campaign 类型一行）。ABM_Sequence 和 Webinar 通常领先，ROI 5–10x；Paid_Social 和 Content_Syndication 经常 ROI 较弱，1–2x。

---

## B11: 首次触点制胜 campaign 分析

**业务背景：** Demand Gen Manager 问：在 Won 的交易中，lead 的首次触点是哪个 campaign？这是"首次触点归因"视角——把功劳归给 *把买家引入* Stratosend 的那个 campaign。

**Category:** Multi-Join + Aggregation
**Difficulty:** Intermediate
**Business Role:** Demand Gen Manager

```sql
SELECT
  c.id AS campaign_id,
  c.campaign_name,
  c.campaign_type,
  COUNT(DISTINCT o.id) AS won_opp_count,
  ROUND(SUM(o.amount_usd), 0) AS won_arr_usd,
  ROUND(AVG(o.amount_usd), 0) AS avg_deal_size_usd
FROM opportunity o
JOIN opportunity_stage s ON s.id = o.current_stage_id
JOIN lead l ON l.id = o.source_lead_id
JOIN campaign c ON c.id = l.source_campaign_id
WHERE s.is_won = 1
GROUP BY c.id
HAVING won_opp_count >= 1
ORDER BY won_arr_usd DESC
LIMIT 20;
```

**预期结果说明：** 前 20 个首次触点制胜 campaign。与 B8（影响管道）形成有用对照。首次触点 winner 常是高意图的 inbound campaign（demo request、free trial）和有效的 ABM sequence。

---

## B12: 内容资产对 Won 管道的影响

**业务背景：** Content Marketing 想知道哪些内容最常被最终成交的买家消费。如果某些 whitepaper 与成交强相关，就应该加大推广力度。

**Category:** Multi-Join + Aggregation
**Difficulty:** Advanced
**Business Role:** Content Marketing

```sql
-- 先去重 (asset × opp) 以避免 SUM(DISTINCT amount) 反模式。
WITH asset_opp AS (
  SELECT DISTINCT ca.id AS asset_id, o.id AS opp_id, o.amount_usd
  FROM content_asset ca
  JOIN content_engagement ce ON ce.content_asset_id = ca.id
  LEFT JOIN lead l    ON l.id = ce.lead_id
  LEFT JOIN contact ct ON ct.id = ce.contact_id
  JOIN account a ON a.id = COALESCE(l.account_id, ct.account_id)
  JOIN opportunity o ON o.account_id = a.id
                     AND o.created_at >= ce.engaged_at
  JOIN opportunity_stage s ON s.id = o.current_stage_id
  WHERE s.is_won = 1
)
SELECT
  ca.id, ca.asset_name, ca.asset_type, ca.topic_tag,
  (SELECT COUNT(*) FROM content_engagement ce2 WHERE ce2.content_asset_id = ca.id) AS total_engagements,
  COUNT(ao.opp_id) AS won_opp_engagements,
  ROUND(COALESCE(SUM(ao.amount_usd), 0), 0) AS influenced_won_arr_usd
FROM content_asset ca
LEFT JOIN asset_opp ao ON ao.asset_id = ca.id
GROUP BY ca.id
ORDER BY influenced_won_arr_usd DESC
LIMIT 20;
```

**预期结果说明：** 前 20 个制胜内容资产。通常被中漏斗内容主导：case study、分析师报告、深度 ebook。较少见：博客文章（顶漏斗，影响较低）。

---

## B13: 内容主题 × Persona 亲和度

**业务背景：** Content Marketing 想确认哪些主题与哪些 persona 共鸣。如果 "Kubernetes Monitoring" 互动中 80% 是 Champion，而 "Cost Optimization" 80% 是 CFO，内容分发就可按 persona 定向。

**Category:** Pivot + Aggregation
**Difficulty:** Intermediate
**Business Role:** Content Marketing

```sql
SELECT
  ca.topic_tag,
  COUNT(ce.id) AS total_engagements,
  SUM(CASE WHEN COALESCE(l.persona, c.persona) = 'Champion' THEN 1 ELSE 0 END) AS champion_count,
  SUM(CASE WHEN COALESCE(l.persona, c.persona) = 'Economic Buyer' THEN 1 ELSE 0 END) AS econ_buyer_count,
  SUM(CASE WHEN COALESCE(l.persona, c.persona) = 'Decision Maker' THEN 1 ELSE 0 END) AS decision_maker_count,
  SUM(CASE WHEN COALESCE(l.persona, c.persona) = 'Influencer' THEN 1 ELSE 0 END) AS influencer_count,
  SUM(CASE WHEN COALESCE(l.persona, c.persona) = 'Blocker' THEN 1 ELSE 0 END) AS blocker_count
FROM content_engagement ce
JOIN content_asset ca ON ca.id = ce.content_asset_id
LEFT JOIN lead l ON l.id = ce.lead_id
LEFT JOIN contact c ON c.id = ce.contact_id
GROUP BY ca.topic_tag
ORDER BY total_engagements DESC;
```

**预期结果说明：** ~13 行（每个 topic_tag 一行）。"API Observability" 和 "Distributed Tracing" 倾向于吸引 Champion/Influencer；"SLO/SLI Practices" 吸引 Economic Buyer。

---

## B14: 门控 vs 非门控内容转化提升

**业务背景：** Marketing Ops 辩论内容门控（要求填表）是否值得带来摩擦。此查询衡量：在互动者中，门控内容互动者成为 MQL 的比例是否高于非门控内容？

**Category:** CTE + Aggregation
**Difficulty:** Intermediate
**Business Role:** Marketing Ops

```sql
WITH gated_engagers AS (
  -- 用字符串前缀把两个 id 命名空间区分开（匹配 ER 文档 §5 的指引）。
  -- 避免 `id + N` 偏移技巧——一旦较小的 id 空间超过 N 就会冲突。
  SELECT DISTINCT
    CASE WHEN ca.is_gated = 1 THEN 'gated' ELSE 'ungated' END AS gate_class,
    COALESCE('L' || ce.lead_id, 'C' || ce.contact_id) AS person_key,
    ce.lead_id
  FROM content_engagement ce
  JOIN content_asset ca ON ca.id = ce.content_asset_id
)
SELECT
  ge.gate_class,
  COUNT(DISTINCT ge.person_key) AS unique_engagers,
  COUNT(DISTINCT CASE WHEN l.mql_date IS NOT NULL THEN ge.person_key END) AS mql_count,
  ROUND(100.0 * COUNT(DISTINCT CASE WHEN l.mql_date IS NOT NULL THEN ge.person_key END)
         / NULLIF(COUNT(DISTINCT ge.person_key), 0), 2) AS mql_rate_pct
FROM gated_engagers ge
LEFT JOIN lead l ON l.id = ge.lead_id
GROUP BY ge.gate_class;
```

**预期结果说明：** 2 行。期望：门控内容互动者有更高的 MQL 率（因为填表动作本身就产生了 lead 并体现了意图）。权衡：门控会减少总互动量。

---

## B15: Email_Blast 对沉默 lead 的激活

**业务背景：** Demand Gen 想看邮件激活 campaign 对沉默 90 天+ 的 lead 是否有效。发送 Email_Blast 是否让沉默的 lead 重新互动（沉寂后又出现评分事件）？

**Category:** Date Difference + Filter
**Difficulty:** Advanced
**Business Role:** Demand Gen Manager

```sql
WITH dormant_then_email AS (
  SELECT
    cm.lead_id,
    cm.engaged_at AS reactivation_touch
  FROM campaign_member cm
  JOIN campaign c ON c.id = cm.campaign_id
  WHERE c.campaign_type = 'Email_Blast'
    AND cm.lead_id IS NOT NULL
),
prior_score_event AS (
  SELECT
    dte.lead_id,
    dte.reactivation_touch,
    MAX(lse.occurred_at) AS last_event_before
  FROM dormant_then_email dte
  LEFT JOIN lead_scoring_event lse ON lse.lead_id = dte.lead_id
    AND lse.occurred_at < dte.reactivation_touch
  GROUP BY dte.lead_id, dte.reactivation_touch
),
post_score_event AS (
  SELECT
    dte.lead_id,
    dte.reactivation_touch,
    MIN(lse.occurred_at) AS first_event_after
  FROM dormant_then_email dte
  JOIN lead_scoring_event lse ON lse.lead_id = dte.lead_id
    AND lse.occurred_at > dte.reactivation_touch
  GROUP BY dte.lead_id, dte.reactivation_touch
)
SELECT
  COUNT(*) AS leads_reactivated,
  COUNT(CASE WHEN JULIANDAY(p.reactivation_touch) - JULIANDAY(pre.last_event_before) > 90
             THEN 1 END) AS dormant_90d_then_blast,
  COUNT(CASE WHEN JULIANDAY(p.reactivation_touch) - JULIANDAY(pre.last_event_before) > 90
                  AND JULIANDAY(post.first_event_after) - JULIANDAY(p.reactivation_touch) < 14
             THEN 1 END) AS reactivated_within_14d,
  ROUND(100.0 * COUNT(CASE WHEN JULIANDAY(p.reactivation_touch) - JULIANDAY(pre.last_event_before) > 90
                  AND JULIANDAY(post.first_event_after) - JULIANDAY(p.reactivation_touch) < 14
             THEN 1 END)
        / NULLIF(COUNT(CASE WHEN JULIANDAY(p.reactivation_touch) - JULIANDAY(pre.last_event_before) > 90 THEN 1 END), 0), 1)
    AS reactivation_rate_pct
FROM dormant_then_email p
LEFT JOIN prior_score_event pre USING (lead_id, reactivation_touch)
LEFT JOIN post_score_event post USING (lead_id, reactivation_touch);
```

**预期结果说明：** 单行汇总，展示总 dormant-then-blast lead 数、其中过去 90 天无事件的数量，以及 blast 后 14 天内产生事件的数量。10–25% 的激活率算健康。

---

## B16: 按 Tier 的销售周期（中位数 + p90）

**业务背景：** VP Sales 想看按 tier 的销售周期分布。中位数告诉你典型情况；p90 揭示最差情况（Enterprise 离群值可能超过 12 个月）。

**Category:** Aggregation + Percentile
**Difficulty:** Intermediate
**Business Role:** VP Sales

```sql
WITH won_with_cycle AS (
  SELECT
    a.account_tier,
    CAST(JULIANDAY(o.actual_close_date) - JULIANDAY(DATE(o.created_at)) AS INT) AS cycle_days
  FROM opportunity o
  JOIN opportunity_stage s ON s.id = o.current_stage_id
  JOIN account a ON a.id = o.account_id
  WHERE s.is_won = 1 AND o.actual_close_date IS NOT NULL
),
ranked AS (
  SELECT
    account_tier,
    cycle_days,
    ROW_NUMBER() OVER (PARTITION BY account_tier ORDER BY cycle_days) AS rn,
    COUNT(*) OVER (PARTITION BY account_tier) AS n
  FROM won_with_cycle
)
SELECT
  account_tier,
  MAX(n) AS won_count,
  MIN(cycle_days) AS min_days,
  ROUND(AVG(cycle_days), 0) AS avg_days,
  MAX(CASE WHEN rn = (n + 1) / 2 THEN cycle_days END) AS median_days,
  MAX(CASE WHEN rn = (n * 9) / 10 THEN cycle_days END) AS p90_days,
  MAX(cycle_days) AS max_days
FROM ranked
GROUP BY account_tier
ORDER BY avg_days;
```

**预期结果说明：** 3 行（SMB、Mid、Enterprise）。SMB 中位数 ~60–90 天，Mid ~120–160，Enterprise ~200–300。Enterprise 的 max 会显示巨大的离群值（年度级交易）。

---

## B17: 阶段间转化 + 阶段停留中位天数

**业务背景：** VP Sales 想找管道瓶颈。哪个阶段通过率最差？哪个阶段耗时最长？综合视图 = "哪个阶段在拖累我们？"

**Category:** Self-Join + CTE
**Difficulty:** Advanced
**Business Role:** VP Sales

```sql
WITH stage_visits AS (
  SELECT
    t.opportunity_id,
    s.stage_name,
    s.stage_order,
    t.transitioned_at,
    t.days_in_previous_stage
  FROM stage_transition t
  JOIN opportunity_stage s ON s.id = t.to_stage_id
),
ever_in_stage AS (
  SELECT
    stage_name,
    stage_order,
    COUNT(DISTINCT opportunity_id) AS opp_count_ever,
    AVG(days_in_previous_stage) AS avg_days_in_prev_stage
  FROM stage_visits
  GROUP BY stage_name, stage_order
)
SELECT
  curr.stage_name AS from_stage,
  next.stage_name AS to_stage,
  curr.opp_count_ever AS opps_in_from,
  next.opp_count_ever AS opps_in_to,
  ROUND(100.0 * next.opp_count_ever / NULLIF(curr.opp_count_ever, 0), 1) AS conversion_pct,
  ROUND(next.avg_days_in_prev_stage, 0) AS avg_days_in_from
FROM ever_in_stage curr
JOIN ever_in_stage next ON next.stage_order = curr.stage_order + 1
WHERE curr.stage_order BETWEEN 1 AND 4
ORDER BY curr.stage_order;
```

**预期结果说明：** 4 行（Disc→Demo、Demo→Eval、Eval→Proposal、Proposal→Negot）。最低转化常出现在 Eval→Proposal（技术评估失败）。平均天数在 Evaluation/POC 最高。

---

## B18: 按竞争对手与行业的赢/输原因矩阵

**业务背景：** RevOps 想找规律。在 Fintech 我们更常输给 Datadog 吗？在 Mid-Market 更常输给 Honeycomb 吗？矩阵揭示系统性的竞争弱点。

**Category:** Pivot + Aggregation
**Difficulty:** Intermediate
**Business Role:** RevOps

```sql
SELECT
  ind.industry_name,
  COUNT(*) AS lost_count,
  SUM(CASE WHEN o.won_lost_reason LIKE '%Datadog%' THEN 1 ELSE 0 END) AS lost_to_datadog,
  SUM(CASE WHEN o.won_lost_reason LIKE '%New Relic%' THEN 1 ELSE 0 END) AS lost_to_newrelic,
  SUM(CASE WHEN o.won_lost_reason LIKE '%Honeycomb%' THEN 1 ELSE 0 END) AS lost_to_honeycomb,
  SUM(CASE WHEN o.won_lost_reason = 'Budget Cut' THEN 1 ELSE 0 END) AS lost_to_budget,
  SUM(CASE WHEN o.won_lost_reason = 'Champion Left' THEN 1 ELSE 0 END) AS lost_to_champ_left,
  SUM(CASE WHEN o.won_lost_reason = 'Project Postponed' THEN 1 ELSE 0 END) AS lost_to_postponement,
  SUM(CASE WHEN o.won_lost_reason = 'No Decision' THEN 1 ELSE 0 END) AS lost_to_indecision
FROM opportunity o
JOIN opportunity_stage s ON s.id = o.current_stage_id
JOIN account a ON a.id = o.account_id
JOIN industry ind ON ind.id = a.industry_id
WHERE s.stage_name = 'Closed-Lost'
GROUP BY ind.industry_name
ORDER BY lost_count DESC;
```

**预期结果说明：** ~12 行（每个行业一行）。Fintech / SaaS / Healthcare Tech 通常在丢单数量上居首。Datadog 是各行业最常见的竞争对手。

---

## B19: 阶段倒退检测（Opp 向后流转）

**业务背景：** RevOps 想标记生命周期中阶段 *向后* 移动的 opportunity——例如从 Demo 退回 Discovery。这是重大风险信号：尽管阶段标记改变，交易并未向前推进。

**Category:** Self-Join
**Difficulty:** Advanced
**Business Role:** RevOps

```sql
SELECT
  t1.opportunity_id,
  o.opportunity_name,
  a.company_name,
  sf.stage_name AS from_stage,
  st.stage_name AS to_stage,
  DATE(t1.transitioned_at) AS regression_date,
  o.amount_usd
FROM stage_transition t1
JOIN opportunity_stage sf ON sf.id = t1.from_stage_id
JOIN opportunity_stage st ON st.id = t1.to_stage_id
JOIN opportunity o ON o.id = t1.opportunity_id
JOIN account a ON a.id = o.account_id
WHERE sf.stage_order > st.stage_order  -- 向后流转
  AND st.is_closed = 0  -- 倒退之后仍然开放
ORDER BY t1.transitioned_at DESC;
```

**预期结果说明：** 这取决于数据生成：在当前逻辑下倒退很少（只有显式生成时才会发生）。许多生产数据集会显示 5–10% 的 opp 至少倒退一次。把这条查询作为模板用——必要时用自定义倒退生成逻辑替换。

---

## B20: 预测偏差——预测 vs 实际

**业务背景：** RevOps 审核团队预测准确度。对 Closed-Won 交易，比较 *创建时*（首次 transition）的 `expected_close_date` 与 `actual_close_date`——预测多频繁、滑了多少？

**Category:** Date Math + Aggregation
**Difficulty:** Advanced
**Business Role:** RevOps

```sql
WITH initial_expected_close AS (
  -- 首次 transition（即 opportunity 创建）时的 expected_close_date
  SELECT
    t.opportunity_id,
    t.expected_close_date_at_transition AS initial_expected_close
  FROM stage_transition t
  WHERE t.from_stage_id IS NULL  -- 创建 transition
),
won_opps AS (
  SELECT o.id, o.amount_usd, o.actual_close_date
  FROM opportunity o
  JOIN opportunity_stage s ON s.id = o.current_stage_id
  WHERE s.is_won = 1
)
SELECT
  COUNT(*) AS won_opp_count,
  ROUND(AVG(JULIANDAY(actual_close_date) - JULIANDAY(initial_expected_close)), 1) AS avg_slip_days,
  SUM(CASE WHEN actual_close_date <= initial_expected_close THEN 1 ELSE 0 END) AS on_or_early,
  SUM(CASE WHEN actual_close_date > initial_expected_close
            AND actual_close_date <= DATE(initial_expected_close, '+30 days')
            THEN 1 ELSE 0 END) AS slipped_30d,
  SUM(CASE WHEN actual_close_date > DATE(initial_expected_close, '+30 days') THEN 1 ELSE 0 END) AS slipped_more_than_30d
FROM won_opps w
JOIN initial_expected_close iec ON iec.opportunity_id = w.id;
```

**预期结果说明：** 单行。通常 30–50% 的 Won 按时或提前关闭，30% 滑 30 天内，20–30% 滑超过一个月。平均滑期通常为正（交易延期多于提前）。

---

## B21: 滑期 opportunity — 预计关闭日期推迟 2 次以上

**业务背景：** RevOps 想标记 `expected_close_date` 在管道推进期间被多次移动的交易。这些交易极高风险会丢失或停滞。

**Category:** Aggregation on history
**Difficulty:** Advanced
**Business Role:** RevOps

```sql
WITH close_date_changes AS (
  SELECT
    opportunity_id,
    COUNT(DISTINCT expected_close_date_at_transition) AS distinct_close_dates,
    MIN(expected_close_date_at_transition) AS earliest_close_date,
    MAX(expected_close_date_at_transition) AS latest_close_date
  FROM stage_transition
  GROUP BY opportunity_id
  HAVING COUNT(DISTINCT expected_close_date_at_transition) >= 3  -- 3+ 个不同值代表 2+ 次滑期
)
SELECT
  cdc.opportunity_id,
  o.opportunity_name,
  a.company_name,
  a.account_tier,
  s.stage_name AS current_stage,
  o.amount_usd,
  cdc.distinct_close_dates - 1 AS times_slipped,
  cdc.earliest_close_date AS initial_close_date,
  cdc.latest_close_date AS current_close_date,
  CAST(JULIANDAY(cdc.latest_close_date) - JULIANDAY(cdc.earliest_close_date) AS INT) AS total_slip_days
FROM close_date_changes cdc
JOIN opportunity o ON o.id = cdc.opportunity_id
JOIN account a ON a.id = o.account_id
JOIN opportunity_stage s ON s.id = o.current_stage_id
WHERE s.is_closed = 0  -- 仍然开放
ORDER BY times_slipped DESC, total_slip_days DESC
LIMIT 50;
```

**预期结果说明：** 关闭日期滑过 2+ 次的开放 opp。Enterprise 交易倾向于占主导（销售周期长、滑期机会更多）。

---

## B22: 开放管道集中度风险

**业务背景：** VP Sales 想评估管道集中度风险。开放 ARR 是分散在很多 AE 之间，还是集中在 1 个 AE 的 2-3 个超大单中？集中 = 那几个单滑期时的风险。

**Category:** Window + Cumulative
**Difficulty:** Advanced
**Business Role:** VP Sales

```sql
WITH ranked AS (
  SELECT
    o.id AS opp_id,
    a.company_name,
    o.amount_usd,
    s.stage_name,
    sr.first_name || ' ' || sr.last_name AS ae_name,
    RANK() OVER (ORDER BY o.amount_usd DESC) AS rank_in_pipe,
    SUM(o.amount_usd) OVER (ORDER BY o.amount_usd DESC
                            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS cum_arr,
    SUM(o.amount_usd) OVER () AS total_open_arr
  FROM opportunity o
  JOIN opportunity_stage s ON s.id = o.current_stage_id
  JOIN account a ON a.id = o.account_id
  JOIN sales_rep sr ON sr.id = o.owner_ae_id
  WHERE s.is_closed = 0
)
SELECT
  opp_id,
  company_name,
  ROUND(amount_usd, 0) AS amount_usd,
  stage_name,
  ae_name,
  rank_in_pipe,
  ROUND(100.0 * cum_arr / total_open_arr, 1) AS cum_pct_of_pipe
FROM ranked
WHERE rank_in_pipe <= 20  -- 前 20 个 opp
ORDER BY rank_in_pipe;
```

**预期结果说明：** 按金额排名的前 20 个 opp。`cum_pct_of_pipe` 显示开放管道总额中有多少集中在它们身上。如果前 5 名 = 50% 的管道，那就是高风险。

---

## B23: SDR SLA 合规 — MQL → 首封邮件 24 小时内

**业务背景：** SDR 团队有一条 SLA：每个 MQL 必须在成为 MQL 后 24 小时内收到第一封 SDR 邮件。合规率低于 80% 会触发 SDR Manager 干预。

**Category:** Date Difference + Self-Join
**Difficulty:** Advanced
**Business Role:** SDR Manager

```sql
WITH mql_leads AS (
  SELECT id AS lead_id, mql_date, assigned_sdr_id
  FROM lead
  WHERE mql_date IS NOT NULL
    AND assigned_sdr_id IS NOT NULL
),
first_sdr_email AS (
  SELECT
    se.recipient_lead_id AS lead_id,
    MIN(se.sent_at) AS first_email_at
  FROM sales_email se
  WHERE se.recipient_lead_id IS NOT NULL
  GROUP BY se.recipient_lead_id
)
SELECT
  sr.id AS sdr_id,
  sr.first_name || ' ' || sr.last_name AS sdr_name,
  COUNT(ml.lead_id) AS mqls_assigned,
  SUM(CASE WHEN JULIANDAY(fse.first_email_at) - JULIANDAY(ml.mql_date) <= 1
            THEN 1 ELSE 0 END) AS compliant_within_24h,
  ROUND(100.0 * SUM(CASE WHEN JULIANDAY(fse.first_email_at) - JULIANDAY(ml.mql_date) <= 1
            THEN 1 ELSE 0 END) / COUNT(ml.lead_id), 1) AS sla_compliance_pct
FROM mql_leads ml
LEFT JOIN first_sdr_email fse ON fse.lead_id = ml.lead_id
JOIN sales_rep sr ON sr.id = ml.assigned_sdr_id
WHERE sr.role = 'SDR'
GROUP BY sr.id
HAVING COUNT(ml.lead_id) >= 5
ORDER BY sla_compliance_pct ASC;
```

**预期结果说明：** ~12 行（拥有 ≥ 5 个 MQL 的每位 SDR 一行）。合规率低于 70% 为重大问题；高于 90% 为优秀。按升序排序，故底部表现者排在前面。

---

## B24: AE 配额完成率排名

**业务背景：** VP Sales 每季度审视：谁在完成配额，谁没有？配额完成率 = YTD Won ARR / 配额。排行榜驱动奖金和 PIP。

**Category:** Aggregation + Join
**Difficulty:** Basic
**Business Role:** VP Sales

```sql
-- 在 SUM 里用 CASE 而不是把 is_won 当 JOIN 条件，否则
-- LEFT JOIN 会保留非 won 的 opp（stage 为 NULL），SUM 也会把它们计入。
SELECT
  sr.id AS ae_id,
  sr.first_name || ' ' || sr.last_name AS ae_name,
  sr.role,
  sr.region,
  ROUND(sr.quota_usd, 0) AS quota_usd,
  ROUND(COALESCE(SUM(CASE WHEN s.is_won = 1 THEN o.amount_usd ELSE 0 END), 0), 0) AS won_arr_usd,
  ROUND(100.0 * COALESCE(SUM(CASE WHEN s.is_won = 1 THEN o.amount_usd ELSE 0 END), 0)
        / NULLIF(sr.quota_usd, 0), 1) AS attainment_pct,
  SUM(CASE WHEN s.is_won = 1 THEN 1 ELSE 0 END) AS won_count
FROM sales_rep sr
LEFT JOIN opportunity o ON o.owner_ae_id = sr.id
LEFT JOIN opportunity_stage s ON s.id = o.current_stage_id
WHERE sr.role LIKE 'AE_%' AND sr.is_active = 1
GROUP BY sr.id
ORDER BY attainment_pct DESC;
```

**预期结果说明：** ~24 位 AE 按完成率 % 排名。有些将 > 100%（President's Club 级别）；有些 < 50%（PIP 风险）。Enterprise AE 波动最大，因为单笔交易可让其从 0% 飙升到 200%。

---

## B25: SDR Sequence 步骤漏斗衰减

**业务背景：** SDR Manager 想看在 sequence 的哪一步回复率崩塌。第 1 步回复率是基线；第 4-7 步应优雅衰减，而不是悬崖式下跌。

**Category:** Aggregation by step
**Difficulty:** Basic
**Business Role:** SDR Manager

```sql
SELECT
  sequence_step,
  COUNT(*) AS emails_at_step,
  SUM(opened) AS opens,
  SUM(clicked) AS clicks,
  SUM(replied) AS replies,
  ROUND(100.0 * SUM(opened) / COUNT(*), 1) AS open_rate_pct,
  ROUND(100.0 * SUM(clicked) / COUNT(*), 1) AS click_rate_pct,
  ROUND(100.0 * SUM(replied) / COUNT(*), 1) AS reply_rate_pct
FROM sales_email
WHERE bounced = 0  -- 排除退信
GROUP BY sequence_step
ORDER BY sequence_step;
```

**预期结果说明：** 7 行（步骤 1-7）。打开率应从 ~35% 平滑衰减到 ~15%。回复率类似。任何步骤的悬崖式下跌都说明该步的 sequence 内容已经坏了。

---

## B26: 按销售代表的回复情感分布

**业务背景：** 除了回复 *率*，SDR Manager 还在意回复 *质量*。一位代表回复率 5% 但全是 `not_interested`，比另一位回复率 2% 但 50% `positive` 的更差。此查询展示每位代表的情感分布。

**Category:** Pivot + Aggregation
**Difficulty:** Intermediate
**Business Role:** SDR Manager

```sql
SELECT
  sr.id AS rep_id,
  sr.first_name || ' ' || sr.last_name AS rep_name,
  COUNT(se.id) AS total_emails,
  SUM(CASE WHEN se.replied = 1 THEN 1 ELSE 0 END) AS total_replies,
  SUM(CASE WHEN se.reply_sentiment = 'positive' THEN 1 ELSE 0 END) AS positive,
  SUM(CASE WHEN se.reply_sentiment = 'neutral' THEN 1 ELSE 0 END) AS neutral,
  SUM(CASE WHEN se.reply_sentiment = 'negative' THEN 1 ELSE 0 END) AS negative,
  SUM(CASE WHEN se.reply_sentiment = 'not_interested' THEN 1 ELSE 0 END) AS not_interested,
  SUM(CASE WHEN se.reply_sentiment = 'auto_reply' THEN 1 ELSE 0 END) AS auto_reply,
  ROUND(100.0 * SUM(CASE WHEN se.reply_sentiment = 'positive' THEN 1 ELSE 0 END)
         / NULLIF(SUM(CASE WHEN se.replied = 1 THEN 1 ELSE 0 END), 0), 1) AS pct_positive_of_replies
FROM sales_email se
JOIN sales_rep sr ON sr.id = se.sender_rep_id
WHERE sr.role IN ('SDR','AE_SMB','AE_Mid','AE_Enterprise')
GROUP BY sr.id
HAVING total_emails >= 100
ORDER BY pct_positive_of_replies DESC;
```

**预期结果说明：** ~30 位销售代表。Top 表现者回复中有 25%+ 是 positive；垫底者 positive < 10%（大多是 not_interested）。揭示那些回复率虽然 OK 但消息话术需要打磨的代表。

---

## B27: 经理团队汇总（通过自连接 FK 的 Won ARR）

**业务背景：** VP Sales 通过 `sales_rep.manager_id` 自连接 FK 按 manager 汇总 Won ARR。同时按团队内角色细分。

**Category:** Self-Join + Aggregation
**Difficulty:** Intermediate
**Business Role:** VP Sales

```sql
-- 与 B24 同样的模式：把 is_won 放在 SUM 内的 CASE 中，不要作为 JOIN 条件。
SELECT
  m.id AS manager_id,
  m.first_name || ' ' || m.last_name AS manager_name,
  m.region,
  r.role AS report_role,
  COUNT(DISTINCT r.id) AS report_count,
  SUM(CASE WHEN s.is_won = 1 THEN 1 ELSE 0 END) AS won_opp_count,
  ROUND(COALESCE(SUM(CASE WHEN s.is_won = 1 THEN o.amount_usd ELSE 0 END), 0), 0) AS won_arr_usd
FROM sales_rep m
JOIN sales_rep r ON r.manager_id = m.id
LEFT JOIN opportunity o ON o.owner_ae_id = r.id
LEFT JOIN opportunity_stage s ON s.id = o.current_stage_id
WHERE m.role = 'Manager'
GROUP BY m.id, r.role
ORDER BY manager_name, won_arr_usd DESC;
```

**预期结果说明：** ~16 行（4 个 manager × 4 种下属 role）。展示团队组成 + 各 role 的营收贡献。每位 manager 名下的 AE_Enterprise 行通常营收占主导。

---

## B28: 销售代表起步分析（入职 → 首单成交）

**业务背景：** VP Sales 想知道：新 AE 入职多久后才能成交第一单？行业基准是 SMB 90 天，Enterprise 180 天。明显高于基准的代表可能需要辅导。

**Category:** Date Difference + Join
**Difficulty:** Intermediate
**Business Role:** VP Sales

```sql
WITH first_won AS (
  SELECT
    o.owner_ae_id,
    MIN(o.actual_close_date) AS first_won_date
  FROM opportunity o
  JOIN opportunity_stage s ON s.id = o.current_stage_id
  WHERE s.is_won = 1
  GROUP BY o.owner_ae_id
)
SELECT
  sr.id AS ae_id,
  sr.first_name || ' ' || sr.last_name AS ae_name,
  sr.role,
  sr.hire_date,
  fw.first_won_date,
  CAST(JULIANDAY(fw.first_won_date) - JULIANDAY(sr.hire_date) AS INT) AS days_to_first_win
FROM sales_rep sr
LEFT JOIN first_won fw ON fw.owner_ae_id = sr.id
WHERE sr.role LIKE 'AE_%'
  AND sr.is_active = 1
  AND fw.first_won_date IS NOT NULL
ORDER BY days_to_first_win;
```

**预期结果说明：** ~20 行（至少有一单 Won 的活跃 AE）。快速起步者（SMB）常 < 60 天；Enterprise 起步可能 120-300 天。first_won_date 为 NULL 的 AE（还没成交）被排除——单独标记。

---

## B29: 首次触点 vs 末次触点 vs W 形归因

**业务背景：** RevOps 想为同一组 Won opportunity 比较三种归因模型。不同模型会把功劳分给不同的渠道——领导层需要这一对比来选定"官方"模型。

**Category:** CTE + Window
**Difficulty:** Advanced
**Business Role:** RevOps

```sql
-- 三个归因 CTE 全部以 campaign_code 为键，使比较是同类对同类。
-- （之前 first_touch 用 lead_source.source_code 为键，
-- last_touch 与 w_shaped 用 campaign.campaign_code 为键——维度不匹配，
-- 产出的列基本互相独立。）
WITH won_opps AS (
  SELECT o.id, o.amount_usd, o.source_lead_id, o.account_id, o.actual_close_date
  FROM opportunity o
  JOIN opportunity_stage s ON s.id = o.current_stage_id
  WHERE s.is_won = 1
),
-- 首次触点：source lead 上标记的 campaign（直接外呼为 NULL）
first_touch AS (
  SELECT
    c.campaign_code,
    SUM(wo.amount_usd) AS first_touch_arr_usd
  FROM won_opps wo
  JOIN lead l ON l.id = wo.source_lead_id
  JOIN campaign c ON c.id = l.source_campaign_id
  GROUP BY c.campaign_code
),
-- 末次触点：账户在关闭前最后一条 campaign_member 对应的 campaign
last_touch AS (
  SELECT
    cm_latest.campaign_code,
    SUM(wo.amount_usd) AS last_touch_arr_usd
  FROM won_opps wo
  JOIN (
    SELECT
      COALESCE(l.account_id, c.account_id) AS account_id,
      camp.campaign_code,
      cm.engaged_at,
      ROW_NUMBER() OVER (
        PARTITION BY COALESCE(l.account_id, c.account_id)
        ORDER BY cm.engaged_at DESC
      ) AS rn_desc
    FROM campaign_member cm
    LEFT JOIN lead l ON l.id = cm.lead_id
    LEFT JOIN contact c ON c.id = cm.contact_id
    JOIN campaign camp ON camp.id = cm.campaign_id
  ) cm_latest ON cm_latest.account_id = wo.account_id AND cm_latest.rn_desc = 1
  GROUP BY cm_latest.campaign_code
),
-- W 形：每 campaign 的加权 credit。attribution_credit_pct 已经按
-- 每条 Won-opp 路径编码了 W 形（30 / 30 / 30 / 10）的分配。
w_shaped AS (
  SELECT
    c.campaign_code,
    SUM(cm.attribution_credit_pct / 100.0 * wo.amount_usd) AS w_arr_usd
  FROM won_opps wo
  JOIN account a ON a.id = wo.account_id
  JOIN campaign_member cm
    ON cm.contact_id IN (SELECT id FROM contact WHERE account_id = a.id)
    OR cm.lead_id    IN (SELECT id FROM lead    WHERE account_id = a.id)
  JOIN campaign c ON c.id = cm.campaign_id
  WHERE cm.attribution_credit_pct > 0
  GROUP BY c.campaign_code
)
-- 三重 FULL OUTER JOIN 的可移植等价写法：先构造 campaign_code 全集，
-- 再 LEFT JOIN 每个归因视图。
,all_codes AS (
  SELECT campaign_code FROM first_touch
  UNION SELECT campaign_code FROM last_touch
  UNION SELECT campaign_code FROM w_shaped
)
SELECT
  ac.campaign_code,
  ROUND(COALESCE(ft.first_touch_arr_usd, 0), 0) AS first_touch_arr,
  ROUND(COALESCE(lt.last_touch_arr_usd, 0), 0)  AS last_touch_arr,
  ROUND(COALESCE(ws.w_arr_usd, 0), 0)           AS w_shaped_arr
FROM all_codes ac
LEFT JOIN first_touch ft ON ft.campaign_code = ac.campaign_code
LEFT JOIN last_touch  lt ON lt.campaign_code = ac.campaign_code
LEFT JOIN w_shaped    ws ON ws.campaign_code = ac.campaign_code
ORDER BY first_touch_arr DESC;
```

**预期结果说明：** 多行表，每个来源对比 3 种归因模型。常常差异巨大：首次触点过度归功 lead 量大的来源；末次触点过度归功 demo-request 类来源；W 形更均衡。

---

## B30: 来源 × Tier 胜率透视矩阵

**业务背景：** Demand Gen 想把胜率看作矩阵：对每个 lead source × 每个账户 tier，opp 胜率是多少？识别 *最佳组合*（例如 Partner Referral × Enterprise 可能达到 60%）。

**Category:** Pivot + Aggregation
**Difficulty:** Intermediate
**Business Role:** Demand Gen Manager

```sql
SELECT
  ls.source_code,
  COUNT(*) AS opp_count,
  ROUND(100.0 * SUM(CASE WHEN s.is_won=1 AND a.account_tier='SMB' THEN 1 ELSE 0 END)
        / NULLIF(SUM(CASE WHEN a.account_tier='SMB' THEN 1 ELSE 0 END), 0), 1) AS smb_win_rate_pct,
  ROUND(100.0 * SUM(CASE WHEN s.is_won=1 AND a.account_tier='Mid' THEN 1 ELSE 0 END)
        / NULLIF(SUM(CASE WHEN a.account_tier='Mid' THEN 1 ELSE 0 END), 0), 1) AS mid_win_rate_pct,
  ROUND(100.0 * SUM(CASE WHEN s.is_won=1 AND a.account_tier='Enterprise' THEN 1 ELSE 0 END)
        / NULLIF(SUM(CASE WHEN a.account_tier='Enterprise' THEN 1 ELSE 0 END), 0), 1) AS enterprise_win_rate_pct,
  SUM(CASE WHEN a.account_tier='SMB' THEN 1 ELSE 0 END) AS smb_opps,
  SUM(CASE WHEN a.account_tier='Mid' THEN 1 ELSE 0 END) AS mid_opps,
  SUM(CASE WHEN a.account_tier='Enterprise' THEN 1 ELSE 0 END) AS ent_opps
FROM opportunity o
JOIN opportunity_stage s ON s.id = o.current_stage_id
JOIN account a ON a.id = o.account_id
JOIN lead_source ls ON ls.id = o.source_id
GROUP BY ls.source_code
ORDER BY opp_count DESC;
```

**预期结果说明：** 10 行（每个来源一行）。用于发现隐藏宝藏——总量小但 Enterprise 胜率高的来源是值得加码的候选。

---

## B31: 按渠道的 CAC 回收期

**业务背景：** CFO 想要 D3 最严谨的版本——每渠道的 CAC、回收期，以及与 SaaS Magic Number 启发式的对比。

**Category:** CTE + Aggregation
**Difficulty:** Advanced
**Business Role:** CFO

```sql
WITH channel_metrics AS (
  SELECT
    ls.source_code,
    ls.typical_cost_per_lead_usd,
    COUNT(DISTINCT l.id) AS leads,
    COUNT(DISTINCT CASE WHEN l.mql_date IS NOT NULL THEN l.id END) AS mqls,
    COUNT(DISTINCT o.id) AS opps,
    SUM(CASE WHEN s.is_won = 1 THEN 1 ELSE 0 END) AS wins,
    SUM(CASE WHEN s.is_won = 1 THEN o.amount_usd ELSE 0 END) AS won_arr_usd
  FROM lead_source ls
  LEFT JOIN lead l ON l.source_id = ls.id
  LEFT JOIN opportunity o ON o.source_lead_id = l.id
  LEFT JOIN opportunity_stage s ON s.id = o.current_stage_id
  GROUP BY ls.source_code, ls.typical_cost_per_lead_usd
)
SELECT
  source_code,
  leads,
  mqls,
  opps,
  wins,
  ROUND(won_arr_usd, 0) AS won_arr_usd,
  ROUND(typical_cost_per_lead_usd * leads, 0) AS implied_spend_usd,
  ROUND(typical_cost_per_lead_usd * leads / NULLIF(wins, 0), 0) AS cac_usd,
  ROUND((typical_cost_per_lead_usd * leads / NULLIF(wins, 0))
         / NULLIF((won_arr_usd / wins) / 12, 0), 1) AS payback_months
FROM channel_metrics
WHERE wins > 0
ORDER BY payback_months ASC;
```

**预期结果说明：** ~7-9 行（至少有 1 单 win 的渠道）。回收期 < 12 个月为优；> 24 个月令人担忧。免费渠道（PARTNER_REFERRAL、OUTBOUND_SDR）因无 lead 成本而 CAC 低。

---

## B32: 隐藏在 W 形归因中的影响管道

**业务背景：** RevOps 怀疑某些 campaign 在首次触点归因下毫无 credit，但在 W 形归因下却获得显著 credit——这些是"隐藏影响者"，比原始漏斗显示的更有价值。

**Category:** Multi-Join + Filter
**Difficulty:** Advanced
**Business Role:** RevOps

```sql
WITH w_credit_by_camp AS (
  SELECT
    c.id AS campaign_id,
    c.campaign_name,
    c.campaign_type,
    SUM(cm.attribution_credit_pct) AS total_credit_pct,
    SUM(cm.attribution_credit_pct / 100.0 * o.amount_usd) AS w_shaped_arr_usd
  FROM campaign c
  JOIN campaign_member cm ON cm.campaign_id = c.id
  JOIN account a ON a.id = COALESCE(
    (SELECT account_id FROM lead WHERE id = cm.lead_id),
    (SELECT account_id FROM contact WHERE id = cm.contact_id)
  )
  JOIN opportunity o ON o.account_id = a.id
  JOIN opportunity_stage s ON s.id = o.current_stage_id
  WHERE s.is_won = 1 AND cm.attribution_credit_pct > 0
  GROUP BY c.id
),
first_touch_count AS (
  SELECT
    c.id AS campaign_id,
    COUNT(DISTINCT o.id) AS first_touch_won_count
  FROM campaign c
  LEFT JOIN lead l ON l.source_campaign_id = c.id
  LEFT JOIN opportunity o ON o.source_lead_id = l.id
  LEFT JOIN opportunity_stage s ON s.id = o.current_stage_id AND s.is_won = 1
  GROUP BY c.id
)
SELECT
  wcb.campaign_id,
  wcb.campaign_name,
  wcb.campaign_type,
  COALESCE(ftc.first_touch_won_count, 0) AS first_touch_wins,
  ROUND(wcb.w_shaped_arr_usd, 0) AS w_shaped_arr_usd
FROM w_credit_by_camp wcb
LEFT JOIN first_touch_count ftc ON ftc.campaign_id = wcb.campaign_id
WHERE COALESCE(ftc.first_touch_won_count, 0) = 0
  AND wcb.w_shaped_arr_usd > 0
ORDER BY w_shaped_arr_usd DESC
LIMIT 20;
```

**预期结果说明：** 前 20 个"隐藏影响者" campaign——它们在 W 形下获得 credit，但没有从首次触点 lead 成交。它们就像篮球中的助攻；不源出但帮助促成成交。

---

## B33: ABM 多干系人覆盖深度

**业务背景：** ABM Lead 衡量每个目标账户中已被触及的不同买家 persona 数。最佳实践：Tier-1 账户 ≥3 个 persona 已互动。

**Category:** Multi-Join + Aggregation
**Difficulty:** Intermediate
**Business Role:** ABM Lead

```sql
WITH target_account_personas AS (
  SELECT
    tal.account_id,
    tal.tier,
    a.company_name,
    COUNT(DISTINCT c.persona) AS distinct_personas_touched,
    COUNT(DISTINCT c.id) AS distinct_contacts
  FROM target_account_list tal
  JOIN account a ON a.id = tal.account_id
  LEFT JOIN contact c ON c.account_id = tal.account_id
  GROUP BY tal.account_id, tal.tier
)
SELECT
  tier,
  COUNT(*) AS target_account_count,
  ROUND(AVG(distinct_personas_touched), 1) AS avg_distinct_personas,
  ROUND(AVG(distinct_contacts), 1) AS avg_distinct_contacts,
  SUM(CASE WHEN distinct_personas_touched >= 3 THEN 1 ELSE 0 END) AS multi_persona_accounts,
  ROUND(100.0 * SUM(CASE WHEN distinct_personas_touched >= 3 THEN 1 ELSE 0 END) / COUNT(*), 1)
    AS pct_with_3plus_personas
FROM target_account_personas
GROUP BY tier
ORDER BY tier;
```

**预期结果说明：** 3 行（Tier 1、2、3）。Tier-1 账户应有最深的覆盖（最高的 avg_distinct_personas 与 pct_with_3plus_personas）。如果 Tier-1 在 3+ persona 上低于 50%，ABM 策略需要打磨。

---

## B34: ABM vs 非 ABM 胜率对比

**业务背景：** VP Sales / ABM Lead 想要 ABM 起作用的实证。ABM 目标账户的胜率和平均交易金额都应高于非目标账户。

**Category:** Aggregation + Filter
**Difficulty:** Basic
**Business Role:** VP Sales

```sql
SELECT
  CASE WHEN a.is_target_account = 1 THEN 'ABM Target' ELSE 'Non-ABM' END AS account_class,
  COUNT(o.id) AS opp_count,
  SUM(CASE WHEN s.is_won = 1 THEN 1 ELSE 0 END) AS won_count,
  ROUND(100.0 * SUM(CASE WHEN s.is_won = 1 THEN 1 ELSE 0 END) / NULLIF(COUNT(o.id), 0), 1) AS win_rate_pct,
  ROUND(AVG(CASE WHEN s.is_won = 1 THEN o.amount_usd END), 0) AS avg_won_deal_usd,
  ROUND(SUM(CASE WHEN s.is_won = 1 THEN o.amount_usd ELSE 0 END), 0) AS total_won_arr_usd
FROM account a
JOIN opportunity o ON o.account_id = a.id
JOIN opportunity_stage s ON s.id = o.current_stage_id
GROUP BY account_class;
```

**预期结果说明：** 2 行。ABM Target 账户的胜率和平均交易金额都应更高（因为 ABM 聚焦 Mid/Enterprise）。总 ARR 对比说明 ABM 是否在绝对量上推动了业务。

---

## B35: 账户扩展 — 拥有多次 Won 的客户

**业务背景：** RevOps 想找已经赢得多次 opportunity 的现有客户——这些是 expansion / upsell 候选。更进一步：识别最近一次 Won 较新的（续约窗口）。

**Category:** Aggregation + HAVING
**Difficulty:** Intermediate
**Business Role:** RevOps

```sql
SELECT
  a.id AS account_id,
  a.company_name,
  a.account_tier,
  COUNT(o.id) AS won_opp_count,
  ROUND(SUM(o.amount_usd), 0) AS total_arr_won_usd,
  MIN(o.actual_close_date) AS first_win_date,
  MAX(o.actual_close_date) AS latest_win_date,
  CAST(JULIANDAY('2026-06-01') - JULIANDAY(MAX(o.actual_close_date)) AS INT) AS days_since_last_win
FROM account a
JOIN opportunity o ON o.account_id = a.id
JOIN opportunity_stage s ON s.id = o.current_stage_id
WHERE s.is_won = 1
GROUP BY a.id
HAVING won_opp_count >= 2
ORDER BY won_opp_count DESC, total_arr_won_usd DESC
LIMIT 30;
```

**预期结果说明：** 多次中标的账户。鉴于数据集的 18 个月时间窗口，这个子集较小——但足以演示。距离上次 win 6-12 个月的窗口标记 expansion 时机。

---

## 查询类别汇总

| Category | 数量 | 查询 ID |
|----------|-------|-----------|
| Aggregation | 12 | D2, D6, D10, D13, D15, B1, B2, B4, B10, B24, B25, B34 |
| Join Operations | 10 | D7, D8, D9, D11, D14, B5, B8, B11, B12, B13 |
| Window Functions | 5 | D5, B6, B19, B22, B29 |
| Date/Time Analysis | 9 | D6, D12, D13, B2, B7, B15, B16, B20, B28 |
| Subqueries / CTEs | 14 | D1, D3, D4, B1, B3, B7, B9, B14, B15, B17, B21, B23, B29, B31 |
| Self-Join | 4 | D14, B17, B19, B27 |
| Pivot | 6 | B4, B5, B13, B18, B26, B30 |
| HAVING / Filter | 6 | B5, B11, B22, B23, B33, B35 |

> 类别会重叠——一条查询可以同时出现在多个桶中（例如 B5 既是 Pivot 也是 HAVING/Filter），因此列计数无需累加到 50。

## Business Role 覆盖

| Role | 数量 | 查询 ID |
|------|-------|-----------|
| CMO | 1 | D1 |
| CFO | 2 | D3, B31 |
| CRO | 1 | D4 |
| Executive | 1 | D5 |
| VP Sales | 11 | D2, D8, D12, D14, B16, B17, B22, B24, B27, B28, B34 |
| VP Marketing | 1 | B1 |
| Demand Gen Manager | 7 | D6, D9, B8, B10, B11, B15, B30 |
| Content Marketing | 4 | D10, B9, B12, B13 |
| SDR Manager | 4 | D7, B23, B25, B26 |
| ABM Lead | 2 | D11, B33 |
| Marketing Ops | 6 | D13, B2, B3, B4, B5, B14 |
| RevOps | 8 | D15, B18, B19, B20, B21, B29, B32, B35 |
| Analyst | 2 | B6, B7 |

## 难度分布

| Level | 数量 | 查询 ID |
|-------|-------|-----------|
| Basic | 8 | D6, D10, D12, D13, D15, B24, B25, B34 |
| Intermediate | 24 | D1, D2, D7, D8, D9, D11, D14, B1, B2, B4, B5, B8, B10, B11, B13, B14, B16, B18, B26, B27, B28, B30, B33, B35 |
| Advanced | 18 | D3, D4, D5, B3, B6, B7, B9, B12, B15, B17, B19, B20, B21, B22, B23, B29, B31, B32 |

---

## 备注

- 所有查询都为 SQLite 3.x 设计。当 SQLite 缺少某项功能（例如原生 percentile）时，使用惯用的变通写法。
- 部分查询假定数据集中已对齐的不变式——例如 `lead.lead_score` 等于评分事件之和。Generator 保证这一点。
- 生产部署时，查询应包装在物化视图中（ER 文档中描述的 ADS 层），而不是每次刷新 dashboard 时重新执行。
- 查询中的"今天"统一硬编码为 `'2026-06-01'`，以匹配 generator 的 `TODAY` 常量。线上系统中请替换为 `DATE('now')`。

---

SQL 查询文档结束。
