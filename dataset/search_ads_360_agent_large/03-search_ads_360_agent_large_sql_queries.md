# Search Ads 360 Intelligent Analytics Agent - SQL Query Reference

> **Dataset:** `search_ads_360_agent_large`
> **Business context / industry primer / glossary / metric formulas:** see `01-search_ads_360_agent_large_business_context.md`
> **Table structure / fields / constraints / DDL:** see `02-search_ads_360_agent_large_er_document.md`
> **Reference Date (REFERENCE_DATE):** `2026-06-01`

This document collects 28 SQL queries covering all core Lumenly Ads business scenarios. It doubles as **reference corpus for the Text-to-SQL Agent** and as a **hands-on practice workbook for new analysts**.

---

## How to Use This Document

**Who this document is for.** Assume you are a new intern analyst who just joined the Lumenly Ads data team. You've already read the business context (you know what the company does and what the 6 business problems are) and the ER document (you know the tables and how to JOIN them). Your manager hands you this and says "work through all of these this week."

**Each query has five parts in a fixed order:**

1. **Business context** — who's asking, why they're asking, what decision the answer will inform, why now. Understand the problem before writing SQL.
2. **Category / difficulty / role** — three labels. Category names the SQL techniques used, difficulty is Basic / Intermediate / Advanced, and role maps to a job title from the business context doc.
3. **Approach** — before you look at the SQL, this section walks through which tables you'll touch, how to set up the JOINs, the grain of aggregation, and where the gotchas are. After reading this you should be able to draft most of the SQL in your head.
4. **SQL** — a query you can run directly on the generated SQLite database. The SQL is meant to be read and learned from, not just executed.
5. **Expected results + business takeaway** — what the result looks like (row count, column meaning, key magnitudes) and **what the analyst should do next** with it. Getting a number is the start of analysis, not the end.

**Two global conventions (remember these):**

- **Fixed reference date:** this dataset is a **frozen snapshot**, the last day of data = `2026-06-01`. All time filters **must** be anchored to `DATE('2026-06-01', ...)`. **Never use `DATE('now', ...)`** — the real today is already past the data's end, so `'now'` will push the time window past the data and return empty results.
- **Every query traces back to a business problem.** There's a "business problem -> query" map at the end of the document. If a query doesn't map to a business problem, it shouldn't be here.

**Query index:**

| # | Title | Business Role | SQL Category | Difficulty | Business Problem |
|---|-------|---------------|--------------|------------|------------------|
| 1.1 | List all advertisers | Marketing Analyst | Join | Basic | Index |
| 1.2 | Clients managed by Gold agencies | Account Manager | Join + filter | Basic | Q6 |
| 1.3 | Campaign hierarchy and ad group count | Campaign Manager | LEFT JOIN + aggregate | Basic | Ops |
| 2.1 | Top 5 spending campaigns last week | Performance Manager | Aggregate + Join | Basic | Q1 |
| 2.2 | Device-dimension performance comparison | Performance Analyst | Aggregate + Join | Intermediate | Device dimension |
| 2.3 | Industry-level ad performance | CMO | Aggregate + multi-Join | Intermediate | Q6 |
| 2.4 | Daily spend and conversion trend | Performance Manager | Time-series aggregate | Basic | Ops |
| 3.1 | Bid strategy performance comparison | Bid Manager | Aggregate + multi-Join | Intermediate | Q2 |
| 3.2 | Target CPA attainment analysis | Bid Manager | CTE + derived metric | Intermediate | Q2 |
| 3.3 | Target ROAS attainment analysis | Trading Desk | CTE + derived metric | Intermediate | Q2 |
| 4.1 | Impression share lost to budget | Media Planner | Aggregate + HAVING | Intermediate | Q1 |
| 4.2 | Top-of-page impression share analysis | Search Specialist | Aggregate | Intermediate | Impression share |
| 5.1 | Quality Score distribution | Search Specialist | Aggregate + subquery | Basic | Q3 |
| 5.2 | High-cost low-QS keywords | Search Specialist | Join + filter | Basic | Q3 |
| 5.3 | Match-type distribution | SEM Specialist | Aggregate + Join | Basic | Q3 |
| 6.1 | High-conversion search terms | SEM Specialist | Aggregate + HAVING | Intermediate | Q4 |
| 6.2 | High-cost zero-conversion search terms | SEM Specialist | Aggregate + HAVING | Intermediate | Q4 |
| 6.3 | Search term match-type effectiveness | SEM Specialist | Aggregate | Intermediate | Q4 |
| 7.1 | Per-channel value across attribution models | Marketing Analytics | Multi-Join + aggregate | Advanced | Q5 |
| 7.2 | Conversion path length analysis | Marketing Analytics | Subquery + window function | Intermediate | Q5 |
| 7.3 | First-touch vs last-touch channels | Marketing Analytics | Multi-CTE + LEFT JOIN | Advanced | Q5 |
| 7.4 | Average time to conversion | Marketing Analytics | Aggregate + filter | Intermediate | Q5 |
| 8.1 | Budget utilization | Media Planner | CTE + SCD2 Join | Advanced | Q1 |
| 8.2 | Budget-constrained campaigns | Media Planner | SCD2 Join + HAVING | Advanced | Q1 |
| 9.1 | Advertiser health check | CSM / Account Manager | CTE + CASE | Advanced | Q6 |
| 9.2 | Optimization opportunity identification | Campaign Manager | Aggregate + CASE | Intermediate | Q1 / Q3 |
| 10.1 | Diagnose why CPA rose | Performance Manager | Multi-step + conditional pivot | Advanced | Q2 / Ops |
| 10.2 | Attribution model comparison | Marketing Analytics | Multi-Join + derived | Advanced | Q5 |

---

## 1. Basic Queries

### 1.1 List All Advertisers

**Business context:** You just got access to the Lumenly Ads database, and your manager tells you to "get familiar with the customer base." Step one is always to open the core entity tables and look — the advertiser is the central entity in this platform; every campaign, dollar of spend, and conversion hangs off of it. This query doesn't drive a specific decision, but it's the starting point for every analysis that follows: first understand which customers exist, what industries they're in, what size, what spend tier.

**Category / difficulty / role:** Join | Basic | Marketing Analyst

**Approach:** You need only the `advertiser` master table plus the `industry` dimension table to translate `industry_id` into the industry name. This is the most basic "fact-table JOIN dimension-table" pattern: the advertiser table stores the industry's foreign key (a number) — to see it in plain English, JOIN the dimension table. An INNER JOIN works because every advertiser has a valid `industry_id` (NOT NULL foreign key). Sort by id to keep the result stable.

```sql
-- Natural language: "List the basic info for every advertiser"
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

**Expected results + business takeaway:** 150 rows, one per advertiser, with industry, size (SMB/Mid-Market/Enterprise), monthly spend tier, primary goal, and account status. You'll see SMB is roughly half and Active is about 85%. This is just a warm-up: next, group by `company_size` or `account_status` to count and quickly build a feel for the customer mix — that lays the groundwork for the later health-check analysis (9.1).

### 1.2 Clients Managed by Agencies

**Business context:** A Lumenly Ads Account Manager wants to know "which customers are held by the Gold-tier agencies." Agencies fall into Gold / Silver / Bronze / Standard, and Gold agencies typically serve the largest customers and charge higher service fees. This query helps the Account Manager understand the client mix at the top of the agency funnel, which feeds renewal negotiations and resource allocation — and ties back to business problem Q6 (customer portfolio health).

**Category / difficulty / role:** Join + filter | Basic | Account Manager

**Approach:** This is a "three-table chain" JOIN: `agency` (the agency) -> `agency_client` (the agency-client contract, M:N bridge) -> `advertiser` (the client), plus `industry` to translate the industry. The key is recognizing that `agency_client` is a **bridge table** that connects agencies and advertisers many-to-many; contract dates and fee percentages live on it. The two filters are `tier_level = 'Gold'` for Gold-only agencies and `is_active = 1` for contracts still in effect (so you don't include churned customers).

```sql
-- Natural language: "Which clients are managed by Gold-tier agencies?"
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

**Expected results + business takeaway:** A handful of rows (Gold agencies are ~10% of all agencies, so the row count is small), each showing "Gold agency — client — industry — fee — contract start." Pay particular attention to the distribution of `fee_percentage`: if a Gold agency holds a portfolio of high-fee large customers, it's a strategic partner the platform should protect at renewal; if its fees skew low, there may be room to renegotiate.

### 1.3 Campaign Hierarchy Structure

**Business context:** A Campaign Manager is doing an account-structure audit and wants to spot "which campaigns have the most complex structure" (the most ad groups beneath them). Ad group count is a proxy for campaign complexity — more groups usually mean more granular keyword targeting and higher management overhead. This query identifies complex campaigns that may need attention or simplification.

**Category / difficulty / role:** LEFT JOIN + aggregate | Basic | Campaign Manager

**Approach:** The driver table is `campaign`, and you need to count how many `ad_group` rows hang off each campaign. You **must** use a **LEFT JOIN** here, not an INNER JOIN: some campaigns may have no ad groups yet, and an INNER JOIN would silently drop those "empty shells," leaving holes in your audit. Aggregate with `COUNT(ag.id)` (counting the child PK) instead of `COUNT(*)` so campaigns with no ad groups get 0, not 1. The GROUP BY must include every non-aggregated SELECT column.

```sql
-- Natural language: "Show campaigns and their ad group counts"
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

**Expected results + business takeaway:** The 20 campaigns with the most ad groups, typically 3–8 per campaign. If a particular campaign's `ad_group_count` is well above the rest (say, >15), it's worth the Campaign Manager digging in to check for bloat or duplicate keywords. If any Enabled campaign has zero ad groups, that's a config gap that needs filling in.

---

## 2. Performance Analysis Queries

### 2.1 Campaign Performance Summary

**Business context:** At Monday morning standup, the Performance Manager has to answer the CMO's first question: "Where did the money go last week?" The most direct answer is "the 5 campaigns with the highest spend last week." Top-N by spend is the entry point for every performance review — the money goes here, so the optimization attention should go here first. This corresponds to business problem Q1 (budget and spend) and is a fixed weekly ritual.

**Category / difficulty / role:** Aggregate + Join | Basic | Performance Marketing Manager

**Approach:** The core fact table is `daily_stats`, which stores per-day-per-campaign-per-device performance. **Here's the dataset's most important gotcha: `daily_stats` is a polymorphic table, and when JOINing campaign you must explicitly include `AND ds.entity_type = 'Campaign'`** — even though Campaign is currently the only entity type, get into this habit, because once the data expands to the ad group level your numbers will be wrong otherwise. The JOIN chain is `daily_stats -> campaign -> advertiser`. Use `report_date >= DATE('2026-06-01', '-7 days')` for the last 7 days. CPA uses `SUM(cost)/NULLIF(SUM(conversions),0)` to guard against divide-by-zero. Order by total cost descending and limit 5.

```sql
-- Natural language: "What were the top 5 spending campaigns last week?"
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

**Expected results + business takeaway:** 5 rows with the highest-spending campaign at the top, including impressions, clicks, cost, conversions, and CPA. Focus on the CPA for these 5: if one of them spends a lot but has a CPA far above the overall average (~¥165), that's the top optimization target for the week — next, drill into 4.1 / 8.2 to see if it's a budget/bid issue, or into 5.2 for keyword quality.

### 2.2 Performance Analysis by Device Type

**Business context:** A Performance Analyst notices the overall CPA is fluctuating and suspects one of the devices is dragging things down. Mobile, Desktop, and Tablet behave very differently: mobile traffic is large but conversions tend to be shallower, while desktop conversions go deeper on smaller volumes. This query splits performance by device so the analyst can judge "should we adjust bid modifiers by device?"

**Category / difficulty / role:** Aggregate + Join | Intermediate | Performance Analyst

**Approach:** `daily_stats` JOIN `device` dimension, group by device name. Always include the `entity_type = 'Campaign'` predicate. CTR / CPA / ROAS all follow the "SUM first, then divide" convention (not averaging per-row ratios), with `NULLIF` guarding against zero. Use a 30-day window for sample stability. Note: the device JOIN uses `ds.device_id`, which is a normal foreign key with an FK constraint, not the polymorphic field.

```sql
-- Natural language: "How much do conversion costs differ between mobile and desktop?"
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

**Expected results + business takeaway:** 3 rows (Mobile / Desktop / Tablet). Mobile spend share is highest (~55% impression share), Desktop second, Tablet smallest. Compare CPA and ROAS across the three: if Mobile CPA is materially higher than Desktop, mobile is burning money — next, suggest lowering the mobile bid modifier or optimizing the mobile landing page. This result often becomes the "Device Performance Comparison" dashboard.

### 2.3 Performance by Industry

**Business context:** The CMO has to report at the quarterly category review on "which industries' customers get the best return." Lumenly Ads spans 10 industries (e-commerce, education, financial services, etc.), and acquisition costs vary wildly — financial CPAs can be several times higher than e-commerce. This query aggregates performance to the industry level so the CMO can judge whether the platform's industry mix is healthy and which industries warrant more sales investment for new acquisition. This ties to business problem Q6.

**Category / difficulty / role:** Aggregate + multi-Join | Intermediate | CMO / Marketing Director

**Approach:** The longest JOIN chain: `daily_stats -> campaign -> advertiser -> industry`, rolling performance all the way up to the industry grain. Still need the `entity_type = 'Campaign'` predicate. `COUNT(DISTINCT a.id)` counts how many active advertisers each industry has (use DISTINCT to avoid the daily_stats one-to-many fan-out inflating the count — this is the most common mistake in aggregate queries). CPA and ROAS follow the SUM-then-divide rule.

```sql
-- Natural language: "What's the average CPA per industry?"
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

**Expected results + business takeaway:** 10 rows (one per industry), sorted by total spend. Pay special attention to `advertiser_count` — the DISTINCT ensures it's a real advertiser count, not an inflated fan-out figure. Compare avg_roas across industries: industries with low ROAS are either inherently tough or industries where the platform's customers underperform; the CMO uses this to prioritize next quarter's industry expansion.

### 2.4 Performance Trend Analysis

**Business context:** The Performance Manager watches the overall numbers daily and needs a "daily spend and conversion trend for the past two weeks" to sense the rhythm — is it flat, climbing, or did something spike on a particular day? Trend charts are where problems show up first: a day where spend explodes but conversions don't follow usually points to bid runaway or malicious budget consumption.

**Category / difficulty / role:** Time-series aggregate | Basic | Performance Marketing Manager

**Approach:** The purest time-series aggregate: no dimension table joins, just group `daily_stats` by `report_date`. Only need the `entity_type = 'Campaign'` predicate + 14-day window. Sort by date ascending so the result naturally reads as a timeline. This kind of query is the foundation of "trend watching" and can be plotted directly as a line chart in a BI tool.

```sql
-- Natural language: "Daily spend and conversion trend for the past two weeks"
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

**Expected results + business takeaway:** 14 rows (one per day), spend and conversions roughly flat. Watch the cpa column for a sudden jump: if some day's CPA is clearly off baseline, drill into 10.1 for root-cause diagnosis (decompose into CPC / CTR / conversion rate). This query is itself the data backbone of the D6 "Daily Performance Snapshot" dashboard.

---

## 3. Bid Strategy Analysis

### 3.1 Bid Strategy Performance Comparison

**Business context:** The Bid Manager has to settle a long-running debate: "How much better is automated bidding (smart bidding) than manual bidding, really?" The platform supports 8 bid strategies, 7 of which are automated. If automated bidding systematically outperforms manual on CPA / ROAS, the move is to push more customers onto automated bidding — that improves customer outcomes and cuts the human labor of bid management. This is business problem Q2 directly.

**Category / difficulty / role:** Aggregate + multi-Join | Intermediate | Trading Desk / Bid Manager

**Approach:** Aggregate performance by "bid strategy type"; the JOIN chain is `daily_stats -> campaign -> bid_strategy -> bid_strategy_type`. There's a critical `is_automated` boolean flag on `bid_strategy_type`; putting it into the GROUP BY gives you a direct automated-vs-manual comparison. `COUNT(DISTINCT c.id)` counts campaigns and avoids fan-out. Note: using INNER JOIN on bid_strategy means the small number of campaigns without a strategy bound are excluded — that's reasonable because we specifically want to analyze "campaigns that use a strategy."

```sql
-- Natural language: "How do different bid strategies perform on conversions?"
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

**Expected results + business takeaway:** Up to 8 rows (one per strategy type), with the `is_automated` flag. Aggregate the weighted CPA / ROAS for each side (is_automated=1 vs =0) to conclude "automated bidding is on the whole better/worse than manual." Note that in this dataset strategy types are assigned randomly, so the performance difference is sampling-driven — treat the conclusion as a method demonstration rather than a real business verdict. Next, drill into 3.2 / 3.3 on the worst-performing strategy type to see the specific campaign attainment.

### 3.2 Target CPA Attainment Analysis

**Business context:** For campaigns that have a Target CPA set, the Bid Manager's top concern is "did the algorithm actually pull cost below the target line?" If a batch of campaigns has actual CPA persistently above the Target CPA, either the bid target is unrealistic or keyword/landing-page quality is dragging conversions. The Bid Manager needs an "over-target leaderboard" to prioritize this week's tuning. Ties to business problem Q2.

**Category / difficulty / role:** CTE + derived metric | Intermediate | Trading Desk / Bid Manager

**Approach:** Two steps; use a CTE for clarity. The CTE `campaign_performance` first computes the actual CPA over the last 7 days for every campaign that has a `target_cpa` set (JOIN campaign -> bid_strategy -> daily_stats, filtering `target_cpa IS NOT NULL`). The outer query then picks `actual_cpa > target_cpa` and computes the over-target percent `(actual - target)/target * 100`. The CTE pays off because the derived metric actual_cpa is computed once inside it and reused in the outer comparison and re-calculation — no need to write the long aggregate expression twice.

```sql
-- Natural language: "Which campaigns have CPA above their target?"
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

**Expected results + business takeaway:** Up to 20 over-target campaigns, sorted by over-target percent descending. The bigger `over_target_pct`, the more severe the issue. The Bid Manager prioritizes from there: handle 50%+ overshoots first — either raise the Target CPA (admit the target was set too low) or pause the high-CPA keywords. This view typically powers the "Bid Strategy Effectiveness" dashboard (alert threshold: attainment <80%).

### 3.3 Target ROAS Attainment Analysis

**Business context:** The mirror image of Target CPA: for campaigns with a Target ROAS (common for e-commerce customers), the Trading Desk cares about "is the return on ad spend hitting target?" Falling short on ROAS means the ad dollars aren't bringing in enough conversion value, and continuing to invest is a loss. The Trading Desk needs to find "below target with the largest gap" campaigns and decide whether to cut budget to stem losses or adjust the ROAS target. Ties to business problem Q2.

**Category / difficulty / role:** CTE + derived metric | Intermediate | Trading Desk / Bid Manager

**Approach:** Mirror-symmetric to 3.2 — swap target_cpa for target_roas and "over-target" for "below target." The CTE `campaign_roas` computes the actual ROAS = `SUM(conversion_value)/SUM(cost)` for every campaign with a `target_roas`. The outer query filters `actual_roas < target_roas` and computes the gap percent `(target - actual)/target * 100` (note the direction: ROAS is higher-is-better, so the gap is target minus actual).

```sql
-- Natural language: "Which campaigns have ROAS below their target?"
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

**Expected results + business takeaway:** Up to 20 below-target campaigns, sorted by gap percent descending. Campaigns with `below_target_pct` near 100% are essentially producing no conversion value — they're the first to cut. The Trading Desk's next step: big gap + big spend = cut budget or pause first; big gap + small spend = watch for another week.

---

## 4. Impression Share Analysis

### 4.1 Impression Share Lost to Budget

**Business context:** This is Lumenly Ads' most direct lever for getting customers to "spend more," and it's the core of business problem Q1. The Media Planner needs to find campaigns where "demand exists, but the budget cap forced fewer impressions" — these campaigns have high `lost_is_budget`. Adding budget to them almost immediately buys more impressions and more conversions, so this is the highest-certainty growth move.

**Category / difficulty / role:** Aggregate + HAVING | Intermediate | Media Planner

**Approach:** Aggregate the average of three impression-share metrics per campaign: `impression_share` (won), `lost_is_budget` (lost to budget), `lost_is_rank` (lost to rank) — these three sum to 100 on every row. The key is **HAVING**: first GROUP BY to compute each campaign's average `lost_is_budget`, then `HAVING AVG(ds.lost_is_budget) > 20` to filter those whose budget loss exceeds 20%. Why HAVING and not WHERE: the filter applies to the aggregated result (the average), and WHERE can only filter pre-aggregation rows.

```sql
-- Natural language: "Which campaigns lost more than 20% impression share to budget?"
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

**Expected results + business takeaway:** Campaigns with `lost_is_budget` over 20% (about 15% of campaigns are designed as "budget-constrained," so expect a meaningful row count), sorted by budget loss. This is the candidate list for adding budget. The Media Planner's next step is clear: take the list to the customer/Account Manager to negotiate a budget increase, and cross-validate with 8.1 / 8.2 to confirm utilization is indeed >100%.

### 4.2 Top-of-Page Impression Share Analysis

**Business context:** For brand terms and high-intent terms, "ranking at the top of the search results page" matters a lot — users tend to click only the first few results. A Search Specialist wants to know which campaigns have the highest top-of-page impression share, and whether high top-of-page share actually translates into higher CTR and lower CPA. This informs the bid strategy decision "should we pay extra for top placement?"

**Category / difficulty / role:** Aggregate | Intermediate | Search Specialist

**Approach:** Aggregate two top-of-page metrics per campaign from `daily_stats`: `search_abs_top_is` (absolute top, i.e. position #1) and `search_top_is` (top region). In the data these satisfy the ordering `abs_top ≤ top ≤ impression_share`. Also compute CTR and CPA to measure the "price-performance" of top placement. This is a pure aggregate query without HAVING, sorted by absolute top share descending, limit 20.

```sql
-- Natural language: "Campaigns with the highest top-of-page impression share"
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

**Expected results + business takeaway:** 20 campaigns with the highest top-of-page share, with CTR and CPA. Cross-judge: if the high-share campaigns also have high CTR and a reasonable CPA, the top-of-page premium is justified; if top-of-page share is high but CPA is also high, the budget is overpaying for generic terms that shouldn't be fighting for top placement — the Search Specialist should recommend dialing back the top-of-page bid targets for those terms.

---

## 5. Keyword Analysis

### 5.1 Quality Score Distribution

**Business context:** Quality Score (QS, 1–10) is a search ad's "credit score": the lower the QS, the higher the CPC you pay for the same rank. The Search Specialist is doing a monthly quality review, and step one is to look at the QS distribution across the account — the share of low-QS keywords directly determines how much "hidden overpayment" the account has. This is the starting point for business problem Q3.

**Category / difficulty / role:** Aggregate + subquery | Basic | Search Specialist

**Approach:** Just the `keyword` table, grouped by `quality_score`. The highlight is the **scalar subquery** in the SELECT: `(SELECT COUNT(*) FROM keyword WHERE status='Enabled')` computes the total enabled keyword count as the denominator, so each score bin's percentage is "bin count ÷ enabled total." Only count `status = 'Enabled'` keywords because paused/removed ones don't spend money and don't reflect current account quality.

```sql
-- Natural language: "How many keywords have Quality Score below 6?"
SELECT
    k.quality_score,
    COUNT(*) AS keyword_count,
    ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM keyword WHERE status = 'Enabled'), 2) AS percentage
FROM keyword k
WHERE k.status = 'Enabled'
GROUP BY k.quality_score
ORDER BY k.quality_score;
```

**Expected results + business takeaway:** A distribution table sorted by score (3–10) with count and percentage. Sum the percentages for quality_score < 6 to get the "low-quality keyword share." If that share exceeds 30% (the D10 dashboard's alert threshold), the account quality is in trouble; the Search Specialist's next step is to use 5.2 to drill into "high-cost + low-QS" specific keywords to optimize or pause.

### 5.2 High-Cost Low-Quality Keywords

**Business context:** Now that we know the low-QS share, the next step is to land on specific keywords. The Search Specialist is looking for "high spend (max_cpc high) and low quality (QS < 6)" keywords — these are the most actionable targets in the account: low QS pushes their effective CPC up, and high bids keep them burning money. Directly maps to Q3's optimization actions.

**Category / difficulty / role:** Join + filter | Basic | Search Specialist

**Approach:** `keyword` JOIN `match_type` to translate the match type, filter on three conditions: `status = 'Enabled'` (still spending), `quality_score < 6` (low quality), `max_cpc > 5` (high bid). Return all three quality sub-dimensions (expected_ctr / ad_relevance / landing_page_exp) to help diagnose which dimension is pulling QS down. This is a plain "filter + sort" query, no aggregation.

```sql
-- Natural language: "Which keywords have low quality but high cost?"
-- Note: daily_stats currently only stores Campaign-level data; this query is illustrative
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

**Expected results + business takeaway:** Up to 30 "high-bid low-quality" keywords, sorted by max_cpc descending. Walk through the three sub-dimensions row by row: if landing_page_exp is Below Average, fix the landing page; if ad_relevance is poor, rewrite ad copy. For things that can't be fixed quickly, lower max_cpc or pause. Note that in the data the three sub-dimensions are sampled independently, so you may see rows "where the sub-dimensions look fine but QS is still <6" — these are exactly the data-inconsistency rows worth manual review (Q3's exercise).

### 5.3 Match Type Distribution

**Business context:** A keyword's match type (EXACT / PHRASE / BROAD) determines how widely it can trigger search terms. The SEM Specialist wants to understand the account's match-type structure: lots of broad-match means wide coverage but noise — more negative-keyword maintenance is needed; lots of exact-match means precision but narrow reach. This informs the workload estimate for search-term mining (Q4).

**Category / difficulty / role:** Aggregate + Join | Basic | SEM Specialist

**Approach:** `keyword` JOIN `match_type`, group by match type, count keywords, average QS, and average max_cpc. Look only at Enabled keywords. This query builds an overall picture of "how the three match types are distributed in the account, and whether quality and bids differ." It's a structural audit aggregate.

```sql
-- Natural language: "Keyword count distribution per match type"
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

**Expected results + business takeaway:** 3 rows (EXACT / PHRASE / BROAD). Look at the broad match (BROAD) share: the higher it is, the noisier the long-tail in the search term report, and the more effort SEM needs to put into negative-keyword maintenance (6.2). If broad-match's average QS is meaningfully lower than exact-match's, consider tightening some broad-match keywords down to phrase match.

---

## 6. Search Term Analysis

### 6.1 High-Conversion Search Terms

**Business context:** The search term report is an SEM goldmine. Every week, the SEM Specialist needs to dig out the long-tail terms with "particularly high conversion rates that haven't been promoted to formal keywords" — promoting them captures more targeted traffic. This is the "expansion" side of business problem Q4 (add keywords).

**Category / difficulty / role:** Aggregate + HAVING | Intermediate | SEM Specialist

**Approach:** `search_term_report` JOIN `keyword` (to see which seed keyword triggered it), aggregate by `search_term`. First filter `clicks > 0` in WHERE (you can't talk about conversion rate with no clicks), then GROUP BY search term, then `HAVING SUM(conversions) > 0` to keep only terms that actually converted. Conversion rate = `SUM(conversions)/SUM(clicks)`, sort descending. Note WHERE vs HAVING: WHERE filters pre-grouping rows; HAVING filters post-aggregation results.

```sql
-- Natural language: "Which search terms have the highest conversion rate?"
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

**Expected results + business takeaway:** The 30 search terms with the highest conversion rates. Because real-world search terms are heavily long-tail (only ~30% of clicked terms convert), the ones in this list are "high-leverage" wins. SEM's next step: promote the ones with `added_excluded='None'` (not yet processed) to exact-match keywords and put them in their own ad group to scale. This corresponds to the "High-Value Search Terms" dashboard.

### 6.2 High-Cost No-Conversion Search Terms

**Business context:** This is the "stop the bleeding" side of Q4 and the highest-frequency action in search term mining. Broad match causes ads to trigger on a pile of irrelevant search terms — they get clicks, they cost money, they never convert. Every two weeks the SEM Specialist needs to surface these "high-cost zero-conversion" terms and add them as negative keywords to plug the money leak. It's one of the most representative optimization scenarios in the entire dataset.

**Category / difficulty / role:** Aggregate + HAVING | Intermediate | SEM Specialist

**Approach:** Structurally symmetric to 6.1 but with the opposite goal. The critical filter is `str.added_excluded = 'None'` — **only look at unprocessed terms to avoid re-recommending things that already have a negative**. Remember the data trap: "unprocessed" is the **literal string `'None'`, not SQL NULL**, so use `= 'None'`, not `IS NULL`. After GROUP BY search term, use `HAVING SUM(conversions) = 0 AND SUM(cost) > 50` to find "zero conversions with cumulative cost over 50."

```sql
-- Natural language: "Which search terms cost a lot but didn't convert? Suggest adding as negative keywords"
-- Only look at unprocessed (added_excluded='None') terms to avoid duplicate recommendations
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

**Expected results + business takeaway:** The 30 most wasteful search terms, sorted by cumulative cost descending. This is the week's negative-keyword candidate list. SEM's next step: review each one to confirm it's really off-business (some zero-conversion entries just have small samples); after confirmation, add them as negative keywords. In production this gets handed to the Weekly Optimization Agent, which auto-generates the list and pushes it to the campaigns.

### 6.3 Search Term to Keyword Match Analysis

**Business context:** A higher-level question for the SEM Specialist: "How healthy is each match type as a whole?" Are search terms triggered by broad match really worse on CPA than exact match? If broad match's CPA is systematically high, the long-tail traffic it brings in is low-quality and needs either stricter negative-keyword policy or tighter match types.

**Category / difficulty / role:** Aggregate | Intermediate | SEM Specialist

**Approach:** Aggregate `search_term_report` directly by `match_type_used` (the actually triggered match type — a string field, not an FK). `COUNT(DISTINCT str.search_term)` counts how many distinct search terms each match type triggered — broad match's distinct count should be by far the highest (because it's the noisiest). CPA follows SUM-then-divide. No JOIN needed; single-table aggregate.

```sql
-- Natural language: "How well do search terms triggered by broad match perform?"
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

**Expected results + business takeaway:** 3 rows (EXACT / PHRASE / BROAD); the `unique_terms` column intuitively shows broad match having the most search-term diversity. Compare CPA across the three: if broad-match CPA is high, SEM should raise the cadence of negative-keyword maintenance on broad-match campaigns or demote high-spend broad-match keywords down to phrase match.

---

## 7. Attribution Analysis

### 7.1 Per-Channel Value Across Attribution Models

**Business context:** This is the flagship query for business problem Q5 and the question the Marketing Analytics team gets asked most by the CMO: "Where does our money actually convert?" The answer depends on which attribution model you use. Last-click hands all the credit to the "closer" channel (often brand terms / direct), and first-click rewards the "opener" channel (often display / social). Putting all six models side by side is the only way to see a channel's true contribution.

**Category / difficulty / role:** Multi-Join + aggregate | Advanced | Marketing Analytics / RevOps

**Approach:** The core is `attribution_path` (one row per touchpoint per conversion) JOIN `conversion` (for conversion value) JOIN `channel` (for channel name). Each touchpoint has a credit (weight) under each of the 6 models, and each model's credit sum per conversion is exactly 1.0. **Channel value = the model's credit × the conversion value**, so the six output columns are each `SUM(xxx_credit * c.conversion_value)`. Group by channel; one query computes the per-channel value across all 6 models simultaneously — this is the design payoff of putting all six models in one table, no need to swap data sources six times.

```sql
-- Natural language: "Compare per-channel value across attribution models (credit × conversion value)"
-- Value = attribution credit × conversion.conversion_value (KPI §11.6 convention)
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

**Expected results + business takeaway:** 6 rows (one per channel), 6 columns for the per-channel value under each model. Reading one row across reveals how that channel's value swings between models. The key insight: for a given channel, if `first_click` is much bigger than `last_click`, it's a "pathfinder" (early prospecting) and last-click would severely undervalue it — the CMO shouldn't cut its budget just because its last-click number looks ugly. This result is the foundation of the "Attribution Model Comparison" dashboard.

### 7.2 Conversion Path Length Analysis

**Business context:** Marketing Analytics wants to answer "how many touches does a user need on average before converting?" Path length directly shapes marketing strategy: if most conversions need only 1–2 touchpoints, the decision chain is short and you can harvest aggressively; if they typically need 4–6 touchpoints, you have to nurture across multiple rounds and can't only look at last-click.

**Category / difficulty / role:** Subquery + window function | Intermediate | Marketing Analytics / RevOps

**Approach:** Two-layer structure. The inner subquery groups by `conversion_id` and uses `MAX(touchpoint_order)` to compute each conversion's path length (since touchpoint_order is numbered 1..N consecutively, the max equals the touchpoint count). The outer query then groups by path length and counts conversions at that length. The highlight is the `SUM(COUNT(*)) OVER ()` **window function**: without breaking the grouping, it computes "total conversions across all" as the denominator, giving you the per-length percentage — cleaner than writing another subquery for the total.

```sql
-- Natural language: "On average, how many touchpoints does a user need before converting?"
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

**Expected results + business takeaway:** The path length distribution for 2–6 (average ~4 touchpoints), with conversion count and percentage per length. If the distribution clusters at 4–6, that means Lumenly's customers are mostly "needs multi-round nurturing" categories, and Marketing Analytics should advise the CMO to use multi-touch models rather than last-click for channel evaluation — otherwise upstream channels will be systematically undervalued.

### 7.3 First-Touch vs Last-Touch Channel Analysis

**Business context:** Following on from 7.1's insight, Marketing Analytics wants a sharper comparison: how often does each channel appear as the "first touchpoint" vs as the "last touchpoint"? A channel with many first-touches and few last-touches is a classic "prospecting channel"; the opposite is a "harvesting channel." That picture directly guides budget allocation between prospecting and harvesting.

**Category / difficulty / role:** Multi-CTE + LEFT JOIN | Advanced | Marketing Analytics / RevOps

**Approach:** The most CTE-organization-heavy query in this document. Two CTEs: `first_touch` takes each conversion's `touchpoint_order = 1` row; `last_touch` takes the maximum-ordered touchpoint per conversion (first find `MAX(touchpoint_order)` per conversion in a subquery, then JOIN back to locate the last-touch row). Finally, with `channel` as the driver, **LEFT JOIN** both CTEs — LEFT JOIN ensures every channel shows up (even if it was never a first-touch or last-touch); otherwise the channel would vanish from the comparison. The two percentage denominators come from scalar subqueries of the per-side conversion totals.

```sql
-- Natural language: "How does the channel distribution differ between first-touch and last-touch?"
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

**Expected results + business takeaway:** 6 channel rows, each with first-touch and last-touch counts and percentages. Compare the two percentage columns: channels with first-touch % > last-touch % (likely Display / Social) are the prospecting workhorses; the opposite (likely Paid Search / Direct) are the harvesting workhorses. Marketing Analytics' recommendation: don't measure prospecting channels with a last-click KPI, or you'll cut exactly the upstream channels you should be investing in.

### 7.4 Average Time to Conversion

**Business context:** Marketing Analytics wants to quantify "sales cycle length": from the user's first touch to final conversion, how long does it take on average? Users from different first-touch channels may decide on very different timescales — a search-driven user might convert the same day, while a display-touched user might take two weeks to make up their mind. This drives the attribution lookback window setting and the remarketing cadence.

**Category / difficulty / role:** Aggregate + filter | Intermediate | Marketing Analytics / RevOps

**Approach:** `attribution_path` JOIN `channel`, but only look at `touchpoint_order = 1` first-touch rows (we're measuring time "from first contact"). The `hours_before_conv` field records how many hours before the conversion the touchpoint happened — just take `AVG` on it. Group by first-touch channel to compare average decision time across channels. This is a "filter to a specific touchpoint + aggregate" query.

```sql
-- Natural language: "How long on average does it take from first touch to conversion?"
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

**Expected results + business takeaway:** 6 channel rows with average time to conversion (hours/days) and conversion count. The channels with the longest decision time need a longer lookback window to attribute correctly — otherwise the conversions they generate fall outside the lookback window and are uncounted. Marketing Analytics uses this to set reasonable lookback windows per channel / floodlight tag.

---

## 8. Budget Analysis

### 8.1 Budget Utilization

**Business context:** The Media Planner wants to answer "are customers actually fully utilizing their budgets?" Budget utilization = actual avg daily spend ÷ the budget in effect that day. Utilization persistently below 60% means budget is over-allocated (it can be dialed down and freed up); approaching or above 100% means budget is capping spend (it should be raised to scale up). This is the quantitative foundation for Q1's budget optimization.

**Category / difficulty / role:** CTE + SCD2 Join | Advanced | Media Planner

**Approach:** The hard part is that `campaign_budget` is a **historicized table (SCD2)**: a campaign has multiple budget records with effective intervals. **Never JOIN it directly, or each campaign's multiple historical budgets will fan out one-to-many and the cost will be multiplied several times.** The correct approach is to take only the row "in effect on the reference date," matching the interval `effective_date_start <= '2026-06-01' AND (effective_date_end IS NULL OR effective_date_end > '2026-06-01')`. The CTE computes the in-effect budget and the 7-day average daily spend (`SUM(cost)/COUNT(DISTINCT report_date)`); the outer query divides them to get utilization.

```sql
-- Natural language: "What's the budget utilization per campaign?"
WITH budget_usage AS (
    SELECT
        c.id AS campaign_id,
        c.campaign_name,
        a.company_name,
        cb.daily_budget,
        ROUND(SUM(ds.cost) / COUNT(DISTINCT ds.report_date), 2) AS avg_daily_spend
    FROM campaign c
    JOIN advertiser a ON c.advertiser_id = a.id
    -- Take only the budget row in effect on the reference date (historicized interval match), avoiding one-to-many fan-out
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

**Expected results + business takeaway:** The top 20 campaigns by utilization. Because the data anchors budgets to actual spend, normal campaigns land in 55%–95% utilization, and budget-constrained ones exceed 100%. Campaigns over 100% are the ones bottlenecked by budget, and the Media Planner should prioritize adding budget for them (and cross-validate with the high `lost_is_budget` list from 4.1). Campaigns with especially low utilization can have some budget reclaimed and redirected to the former group.

### 8.2 Budget-Constrained Campaigns

**Business context:** 8.1 looks at utilization; this one is more direct — it locks in budget-constrained campaigns using the engine's own signal ("impression share lost to budget", `lost_is_budget`), restricted to Enabled campaigns only (paused ones don't matter). The two signals (utilization >100% and high lost_is_budget) corroborate each other and form a robust basis for adding budget. Ties to Q1.

**Category / difficulty / role:** SCD2 Join + HAVING | Advanced | Media Planner

**Approach:** Same SCD2 interval match as 8.1 to pull the day's budget, but this time use `HAVING AVG(ds.lost_is_budget) > 20` after GROUP BY to lock onto campaigns whose average budget loss exceeds 20%. Also add `c.status = 'Enabled'` to filter out inactive campaigns. Output `avg_daily_spend` as well so you can estimate how much budget to add. This pairs the "competitive signal (lost_is_budget)" with "budget/spend" — the standard form of a budget-gap analysis.

```sql
-- Natural language: "Which campaigns might be budget-constrained?"
SELECT
    c.campaign_name,
    a.company_name,
    cb.daily_budget,
    ROUND(AVG(ds.lost_is_budget), 1) AS avg_lost_is_budget,
    ROUND(SUM(ds.cost) / COUNT(DISTINCT ds.report_date), 2) AS avg_daily_spend
FROM campaign c
JOIN advertiser a ON c.advertiser_id = a.id
-- Take only the budget row in effect on the reference date (historicized interval match), avoiding one-to-many fan-out
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

**Expected results + business takeaway:** The 20 most budget-constrained active campaigns, with their daily budget, average budget loss, and average daily spend. This is a directly actionable budget-increase ticket: for each campaign, the budget delta can be roughly estimated as `avg_daily_spend / (1 - lost_is_budget%)`. In production this list is auto-generated by the Daily Health Check Agent and pushed to the owner.

---

## 9. Composite Diagnostic Queries

### 9.1 Advertiser Health Check

**Business context:** Account Manager / CSM needs a "customer health overview" for the quarterly business review (QBR) — one glance to see which large customers are healthy, average, or needing attention. Customers with poor health are renewal risks and need proactive intervention. This composite query rolls performance metrics (ROAS) and competitive metrics (lost_is_budget) into a business judgment; it maps to business problem Q6.

**Category / difficulty / role:** CTE + CASE | Advanced | CSM / Account Manager

**Approach:** The CTE `advertiser_metrics` computes the multi-dimensional metrics per advertiser in one pass: campaign count, total cost, conversions, CPA, ROAS, avg impression share, avg lost_is_budget (JOIN chain advertiser -> campaign -> daily_stats, filtered to Active advertisers). The outer query uses a **CASE expression** to translate the numbers into business labels: ROAS≥4 and lost_is_budget<10% -> Healthy; ROAS≥2 and loss<30% -> Moderate; otherwise Needs Attention. CASE is the standard way to bake "analyst judgment rules" into SQL.

```sql
-- Natural language: "Give me a comprehensive advertiser health report"
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

**Expected results + business takeaway:** The 20 highest-spending active advertisers, each tagged with a health_status. Focus on "high-spend but Needs Attention" — they are both revenue mainstays and at performance risk, the highest-priority customer success targets. The Account Manager uses this to set the QBR agenda and renewal defense plan.

### 9.2 Optimization Opportunity Identification

**Business context:** The Campaign Manager wants a "daily to-do": for active campaigns that are actually spending real money, the system should automatically recommend what to do (add budget, raise quality, review targeting, optimize CPA). This consolidates the scattered diagnostic logic from earlier sections (budget loss, rank loss, zero conversion, high CPA) into a one-stop action list, spanning Q1 and Q3.

**Category / difficulty / role:** Aggregate + CASE | Intermediate | Campaign Manager

**Approach:** Aggregate spend, conversions, CPA, budget loss, and rank loss per active campaign; use a **multi-branch CASE** to encode the diagnostic rules into a recommendation: budget loss >20% -> add budget; rank loss >30% -> bid/quality; zero conversion but spend >100 -> review targeting; CPA >200 -> optimize CPA; otherwise -> monitor. CASE branches **short-circuit in order**, so the most severe / highest-priority conditions go first. Use `HAVING cost > 100` to filter out campaigns with too little spend to be worth acting on.

```sql
-- Natural language: "Identify campaigns that need optimization"
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

**Expected results + business takeaway:** The top 30 active campaigns by spend, each with a clear recommendation. The Campaign Manager can batch-process by category: handle all 'Increase Budget' through the budget-increase flow, review targeting for all 'Review Targeting', etc. This query is the prime example of taking human expert rules and handing them to an Agent for automated execution — the thresholds in the CASE are the Agent's decision logic.

---

## 10. Agent Scenario Queries

### 10.1 Diagnose Why CPA Rose

**Business context:** This is the most typical Text-to-SQL Agent task: a customer / Performance Manager throws out a vague "why did my conversion cost jump so much last week?", and the Agent has to break it into an executable diagnostic flow. A rising CPA always comes from one of three causes: CPC went up (more expensive), CTR dropped (fewer clicks), or conversion rate dropped (clicks didn't convert). This multi-step query demonstrates the standard root-cause analysis pattern.

**Category / difficulty / role:** Multi-step + conditional pivot | Advanced | Performance Marketing Manager

**Approach:** Three steps, drilling down progressively. Step 1 uses CTE + CASE to split the last 14 days into "this week / last week" segments and confirm CPA indeed rose, and by how much. Step 2 breaks CPC / CTR / conversion rate apart by week to identify which component is deteriorating (the `CASE WHEN report_date >= ... THEN 'This Week' ELSE 'Last Week'` pattern is the SQLite-friendly way to do a "conditional pivot"). Step 3 uses `SUM(CASE WHEN ... THEN cost ELSE 0 END)` **conditional aggregation** to put this-week and last-week CPA on the same row per campaign, computes the week-over-week change, and uses `HAVING this_week_cpa > last_week_cpa * 1.2` to lock onto the culprit campaigns whose rise exceeds 20%.

```sql
-- Natural language: "Why did my conversion cost jump so much last week?"
-- Step 1: confirm the CPA change
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

-- Step 2: analyze CPC change
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

-- Step 3: identify campaigns where CPA rose the most
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

**Expected results + business takeaway:** Step 1 returns two rows (this-week / last-week CPA) to confirm the direction; Step 2 returns two rows to pinpoint which of CPC/CTR/conv rate worsened; Step 3 returns up to 10 culprit campaigns with a >20% WoW rise. The three steps together form a complete root-cause report. After receiving the step-3 list, the Performance Manager drills into 5.2 (keyword quality) or 4.1 (budget) for targeted fixes. This is exactly the reasoning chain an automated Agent diagnostic should replicate.

### 10.2 Attribution Model Comparison Analysis

**Business context:** This is 7.1's "decision-enhanced" version, serving a concrete decision: which channels are systematically undervalued by last-click? Marketing Analytics doesn't just want to see six models' numbers — they want a direct metric quantifying "first vs last difference" so they can hand the CMO a pick-list of "undervalued prospecting channels."

**Category / difficulty / role:** Multi-Join + derived | Advanced | Marketing Analytics / RevOps

**Approach:** Building on 7.1, keep only the four key models (last/first/linear/data_driven) and add a **derived comparison column** `first_vs_last_diff_pct = (first_click_value - last_click_value)/last_click_value * 100`. The larger this percent is positive, the more first-click value exceeds last-click value — meaning that channel is the upstream prospecting channel most undervalued by last-click. JOIN structure is the same as 7.1 (attribution_path -> conversion -> channel).

```sql
-- Natural language: "Help me analyze per-channel value across attribution models"
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

-- Insight: if first-click value is much higher than last-click, the channel plays a key role earlier in the user decision
```

**Expected results + business takeaway:** 6 channel rows with four models' values and a `first_vs_last_diff_pct` comparison column. Channels with a large positive `first_vs_last_diff_pct` are the upstream prospecting channels undervalued by last-click — Marketing Analytics should defend them by name at the CMO's budget review, so they don't get cut just because last-click numbers look ugly. This is the close-the-loop query that converts analysis directly into a budget decision.

---

## 11. Business Problem -> Query Mapping

The table below maps the 28 queries back to the 6 business problems in the business context document, ensuring every query has a justified place.

| Business Problem | Corresponding Queries |
|------------------|----------------------|
| **Q1 Budget Gap Identification** | 2.1, 4.1, 8.1, 8.2, 9.2 |
| **Q2 Bid Strategy Efficacy** | 3.1, 3.2, 3.3, 10.1 |
| **Q3 Keyword Quality Diagnostics** | 5.1, 5.2, 5.3, 9.2 |
| **Q4 Search Term Mining** | 6.1, 6.2, 6.3 |
| **Q5 Multi-Touch Attribution Analysis** | 7.1, 7.2, 7.3, 7.4, 10.2 |
| **Q6 Account & Customer Portfolio Health** | 1.2, 2.3, 9.1 |
| **Operational / Index (supporting)** | 1.1, 1.3, 2.2, 2.4, 4.2 |

---

## 12. Usage Notes

### 12.1 Database Connection

```python
import sqlite3
import pandas as pd

# Connect to the database
conn = sqlite3.connect('search_ads_360_agent_large.sqlite')

# Run a query
df = pd.read_sql_query("SELECT * FROM advertiser LIMIT 10", conn)
print(df)

conn.close()
```

### 12.2 Text-to-SQL Example

User input: "What were the top spending campaigns last week?"

SQL the Agent generates:
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

## 13. Caveats

1. **Fixed reference date (important)**: this dataset is a **frozen snapshot**, the last day of data = `2026-06-01` (the max date in daily_stats / search_term_report / conversion is all that day). All time filters **must be anchored to `DATE('2026-06-01', ...)`**; **don't use `DATE('now', ...)`** — the real current date is already past the data's end, so `'now'` will push the time window past the data and return empty results.
2. **NULL handling**: use `NULLIF()` to avoid divide-by-zero errors.
3. **Performance**: for large-data queries, restrict the time range with appropriate WHERE clauses.
4. **Entity type**: the `daily_stats` table uses `entity_type` to distinguish data levels; always include `entity_type='Campaign'` explicitly in JOINs.
5. **Budget historicization**: `campaign_budget` is SCD2; JOIN with `effective_date_start <= reference date AND (effective_date_end IS NULL OR effective_date_end > reference date)` interval matching, or you'll get one-to-many fan-out.
6. **Search term optimization flag**: `search_term_report.added_excluded` takes values `'None'` (unprocessed) / `'Added'` / `'Excluded'`; "unprocessed" is the literal string `'None'`, not SQL NULL.
