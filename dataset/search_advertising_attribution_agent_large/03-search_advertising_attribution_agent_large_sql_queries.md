# Search Advertising Attribution Agent Dataset: SQL Query Reference

## Overview

This document provides **20 business-oriented SQL queries** for the `search_advertising_attribution_agent_large` dataset. The accompanying business context, industry primer, and glossary live in `01-search_advertising_attribution_agent_large_business_context.md`, and the table structure and data generation rules live in `02-search_advertising_attribution_agent_large_er_document.md`.

## How to Use This Document

This document is written for one specific reader: the intern analyst who just finished reading the business context and ER documents and is about to be handed these queries by a manager. Read straight through and you'll see how a real analyst moves from a business question to SQL to a decision — not just a snippet that runs.

Every query follows the same five-section layout:

- **Business context:** who's asking, why now, and what decision the answer will drive.
- **Category / difficulty / business role:** the SQL technique being practiced, the difficulty, and the role most likely to ask the question.
- **Approach:** before reading the SQL, think through which tables you'll touch, how you'll join them, what grain you'll aggregate to, why you'd reach for a CTE or window function, and whether there's a SQLite-specific gotcha. This section is the key to actually understanding the question.
- **SQL:** the query, runnable directly against the generated SQLite database.
- **Expected result description:** what the result looks like, which numbers map to which business traps, and what the analyst should do next.

Two global reminders. First, every time window is anchored to the `v_reference_date` view (which returns `MAX(daily_stats.report_date)`); queries use literal offsets back from that value rather than `DATE('now')`, so the results are reproducible no matter how long ago the dataset was generated. Second, every query traces back to one of the business questions listed in the business-context document (attribution truth, budget efficiency, cross-engine efficiency, waste cleanup, agency and portfolio structure). The SQL is meant to be read and learned from, not just executed.

## Global Conventions

The following conventions are used consistently across all queries; they are stated once here and not repeated inside each query.

1. **Reference date / "recent" windows.** All time-window filters are anchored to the `v_reference_date` view, which exposes `MAX(daily_stats.report_date)` (see ER document §5.2). Queries do not use `DATE('now')` directly. The project-standard "recent" windows are:
   - `"last 7 days"` ⇒ `report_date >= DATE((SELECT reference_date FROM v_reference_date), '-7 days')`
   - `"last 14 days"` ⇒ `… '-14 days'`
   - `"last 30 days"` ⇒ `… '-30 days'`
2. **"Active" entities.** A campaign / ad / keyword is "active" when `status = 'Enabled'`; an advertiser is "active" when `account_status = 'Active'`; an agency_client relationship is "active" when `is_active = 1`. **For keyword / ad_group aggregation queries on "active" advertisers, the parent campaign and ad_group are also filtered to `status = 'Enabled'`**, so that paused or removed parents don't contribute to the aggregate.
3. **CPA / ROAS.** `CPA = SUM(cost) / NULLIF(SUM(conversions), 0)`; `ROAS = SUM(conversion_value) / NULLIF(SUM(cost), 0)`.
4. **Resolving the in-effect `campaign_budget`.** To find the budget in effect on date D, take the row with the latest `effective_date ≤ report_date`. Queries that join `campaign_budget` to `daily_stats` **must** use this pattern (see the correlated subqueries in Query 4 and Query 15) to avoid double-counting when a campaign has multiple budget versions.
5. **Three sources of "conversion" data.** The term "conversion" appears in 3 places in this dataset, at 3 different grains and 3 different magnitudes. They **cannot be directly compared**; each query picks one and sticks with it.
   - **`daily_stats.conversions`** — engine-reported day aggregate (grain: campaign × day × device). 90-day total is in the millions. Used by Queries **1, 2, 3, 5, 6, 7, 9, 17, 19**.
   - **`conversion` table (5,000 rows)** — Floodlight event log: one row per real event, with an explicit `conversion_value` and timestamp. Used by Queries **12, 13, 14, 18** (path length, attribution credit, conversion latency).
   - **`search_term_report.conversions`** — engine-reported day aggregate (grain: search term × day) — same definition as `daily_stats` but at finer grain. Used by Query **10** for negative-keyword candidates.
   - Queries **4, 8, 11, 15, 16, 20** do not aggregate any conversion column.
6. **`search_*_is` on non-Search campaigns.** `search_impr_share`, `search_top_is`, and `search_abs_top_is` are NULL in `daily_stats` rows for Display / Video / Performance Max / Shopping campaigns. Query 16 filters `campaign_type = 'Search'`; queries that aggregate `impression_share` include all campaign types.

## Query Index

| # | Title | Business role | Category | Difficulty |
|---|---|---|---|---|
| 1 | Top advertisers by 30-day spend | Executive | Join + aggregation | Basic |
| 2 | Industry portfolio overview | Executive | Join + aggregation | Basic |
| 3 | Day-over-day spend trend | Manager | Window function | Intermediate |
| 4 | Campaign spend vs budget (fan-out safe) | Manager | CTE + subquery | Advanced |
| 5 | Campaigns over Target CPA | Analyst | CTE + Join | Intermediate |
| 6 | Device-level CTR and CPA | Analyst | Aggregation + Join | Basic |
| 7 | Engine performance comparison | Analyst | Aggregation + Join | Basic |
| 8 | Quality Score distribution by industry | Analyst | Aggregation + Join | Intermediate |
| 9 | Low-QS keywords inside high-spend campaigns | Analyst | Cross-level Join | Advanced |
| 10 | High-cost zero-conversion search terms | Operations | LEFT JOIN + aggregation | Basic |
| 11 | Broad-match overflow share | Analyst | NULL handling + aggregation | Intermediate |
| 12 | First-touch vs last-touch channel mix | Analyst | CTE + aggregation | Advanced |
| 13 | Conversion path-length distribution | Analyst | Subquery + aggregation | Intermediate |
| 14 | Channel value under each attribution model | Executive | Aggregation + Join | Intermediate |
| 15 | Budget-constrained campaigns | Manager | CTE + subquery | Advanced |
| 16 | Campaigns holding top page positions (Search-only, impression-weighted) | Manager | Weighted aggregation | Intermediate |
| 17 | Agency portfolio performance by tier | Executive | Join + aggregation | Intermediate |
| 18 | Conversion latency by first-touch channel | Analyst | CTE + Join | Intermediate |
| 19 | Week-over-week CPA diagnostic | Manager | CTE + CASE + date arithmetic | Advanced |
| 20 | Keyword coverage in search-term report | Operations | LEFT JOIN + aggregation | Basic |

---

## Queries

### Query 1: Top advertisers by 30-day spend

**Business context:**
An executive is prepping the weekly stakeholder review and wants a rough number: who were the top-spending advertisers over the last 30 days, what industry are they in, and how efficient was the spend? This is the first slide in almost every business review, used to allocate attention across clients.

**Category:** Join + aggregation
**Difficulty:** Basic
**Business role:** Executive

**Approach:**
Start from `advertiser`, join `industry` for the industry name, then join `campaign` and `daily_stats` to attribute spend back to the advertiser. An advertiser has many campaigns, and each campaign has many days × devices of `daily_stats`, so the join fans out; `GROUP BY a.id` collapses it back to advertiser grain so we can SUM spend and conversions. CPA and ROAS must be computed by SUMming numerator and denominator separately before dividing (with `NULLIF` to protect against divide-by-zero) — you can never compute the per-row CPA and then average, because that's a wrong weighting. The time window uses `v_reference_date` to look back 30 days. One GROUP BY + ORDER BY + LIMIT 10 is enough. Maps to the business question of portfolio overview.

```sql
-- Top 10 advertisers by spend in the last 30 days, with CPA and ROAS.
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

**Expected result description:**
10 rows, one per advertiser, ordered by spend. Spend ranges from a few hundred thousand dollars at the top to about $50,000 at #10. CPA / ROAS should be reasonable (CPA $50–$300, ROAS 1.0–8.0) and visibly differ across industries.

---

### Query 2: Industry portfolio overview

**Business context:**
The agency CMO wants a one-page industry breakdown: which IAB verticals do we spend the most on, how many active advertisers and campaigns sit in each vertical, and which verticals post the strongest ROAS? This drives talent allocation and decisions about which verticals deserve case-study marketing investment.

**Category:** Join + aggregation
**Difficulty:** Basic
**Business role:** Executive

**Approach:**
Same join chain as Query 1, but aggregate up one level to industry. Join from `industry` through `advertiser`, `campaign`, and `daily_stats`. There's one trap to watch: because of `daily_stats` fan-out, the same advertiser and campaign appear many times in the join output, so `advertiser_count` and `campaign_count` must use `COUNT(DISTINCT ...)` or they'll be wildly overcounted. After aggregating to industry grain, note that CPA is driven mainly by competition (CPC and conversion rate) while ROAS is driven mainly by industry order value — the two orderings won't match, and that's a useful teaching contrast. Maps to the business question of portfolio structure.

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

**Expected result description:**
10 rows — one per IAB industry. `advertiser_count` and `campaign_count` only count entities that ran in the window. Because conversion value is sampled per industry range, real estate / finance / insurance / automotive show the highest average conversion value and ROAS, while food service / retail show the lowest. CPA is driven mainly by competition (auction CPC + conversion rate) rather than order value, so its ordering doesn't fully match the value ordering — a useful teaching point.

---

### Query 3: Day-over-day spend trend

**Business context:**
A campaign manager noticed an anomaly on yesterday's spend dashboard and wants to see daily spend and the day-over-day delta for the last two weeks to confirm whether the spike is a single-day event or a trend shift.

**Category:** Window function (LAG)
**Difficulty:** Intermediate
**Business role:** Manager

**Approach:**
First, a CTE aggregates `daily_stats` by `report_date` into total daily spend, collapsing the campaign and device dimensions. Why must we aggregate first? Because the outer layer uses `LAG(daily_spend) OVER (ORDER BY report_date)` to fetch the previous day's value, and LAG strictly steps back one row — it needs exactly one row per date, otherwise LAG will fetch a different device-row on the same day and the delta will be wrong. The first row has no prior value, so `spend_delta` and `spend_delta_pct` are NULL by definition — that's expected. Maps to the business question of budget efficiency and day-to-day monitoring.

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

**Expected result description:**
14 rows ordered by date. The first row's `spend_delta` and `spend_delta_pct` are NULL. Day-of-week seasonality shows up as a weak weekly pattern; ±15–30% day-over-day swings are normal; anything beyond that is anomalous.

---

### Query 4: Campaign spend vs budget (fan-out safe)

**Business context:**
A campaign manager wants to know which campaigns spend the most relative to their daily budget — finding both the over-spenders (pacing out of control) and the under-spenders (wasted budget). This query exposed a fan-out bug in a retired version of the dataset: campaigns with multiple `campaign_budget` rows would double-count their spend when joined naively.

**Category:** CTE + correlated subquery
**Difficulty:** Advanced
**Business role:** Manager

**Approach:**
The hard part is that `campaign_budget` is versioned — a campaign can have multiple budget revisions. If you join `campaign_budget` straight into `daily_stats`, every campaign row fans out once per budget version and spend is double-counted. The correct pattern is a correlated subquery: for every `daily_stats` row, pick the latest `effective_date <= report_date` (`ORDER BY effective_date DESC LIMIT 1`). After resolving the in-effect budget, aggregate first to the campaign-day grain to collapse the device rows, then per campaign average daily spend over average daily budget to compute pacing. The order of those two aggregation steps is the heart of the query. Maps to the business question of budget efficiency.

```sql
-- The correlated subquery resolves "which budget is in effect on this report_date":
-- pick the latest row with effective_date <= report_date. Without this pattern, a
-- straight join from campaign_budget into daily_stats double-counts spend on any
-- campaign that has more than one budget version.
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

**Expected result description:**
20 campaigns ordered by `pacing_pct` (≈ avg daily spend / avg daily budget × 100). Values over 100% mean over-pacing relative to plan; under 50% indicates budget-constrained headroom. The `per_campaign_day` CTE aggregates device-level rows to campaign-day grain before averaging, which is what makes the per-campaign average meaningful.

---

### Query 5: Campaigns over Target CPA

**Business context:**
A paid-search analyst is auditing Smart Bidding performance: the advertiser asked for `Target CPA`, but the actual numbers don't match. The analyst needs to know which campaigns are using a Target CPA strategy and how their actual CPA compares to the target.

**Category:** CTE + Join
**Difficulty:** Intermediate
**Business role:** Analyst

**Approach:**
In the CTE, join `campaign` to its bound `bid_strategy` to fetch `target_cpa`, then join `daily_stats` to compute actual spend and conversions, and filter `bid_strategy.target_cpa IS NOT NULL` so only campaigns truly on a Target CPA strategy are included. After aggregating to campaign grain to get `actual_cpa`, the outer query filters `actual_cpa > target_cpa` and computes the over-target percentage. The comparison sits in the outer layer (not in `WHERE`) because `actual_cpa` is an aggregate — it can only be compared after aggregation. Maps to the business question of bid-strategy auditing.

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

**Expected result description:**
Up to 20 campaigns with `actual_cpa > target_cpa`. `over_target_pct` is the percentage overshoot; anything above 30% means Smart Bidding isn't hitting the target, and the campaign deserves intervention (loosen the target, broaden the audience, or switch bid strategy).

---

### Query 6: Device-level CTR and CPA

**Business context:**
A media analyst is reviewing whether mobile or desktop is more efficient at the portfolio level. The simplest cut is to compare CTR, CPA, and ROAS by device for the last 30 days.

**Category:** Aggregation + Join
**Difficulty:** Basic
**Business role:** Analyst

**Approach:**
The most straightforward query in the set: `daily_stats` joins `device`, GROUP BY device. The key point is that CTR must be computed as `SUM(clicks) / SUM(impressions)`, not `AVG(ctr)` — any rate metric requires summing numerator and denominator separately before dividing; per-row rates averaged together are biased by low-volume rows. Same for CPA / ROAS. The generator applies fixed device multipliers, so we expect Mobile to carry the most impressions, Desktop to have the highest conversion rate and therefore the lowest CPA, and Tablet to be under 10% of share — that's a designed structure, not noise. Maps to the business question of device efficiency.

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

**Expected result description:**
3 rows (Mobile, Desktop, Tablet). The generator's device multipliers make the distribution match industry benchmarks: Mobile carries about 60% of impressions, Desktop's conversion rate is about 2× Mobile's so Desktop posts the lowest CPA, and Tablet is a distant third with under 10% share.

---

### Query 7: Engine performance comparison

**Business context:**
A paid-search analyst at a multi-engine agency wants to compare the click cost and conversion volume between the two North American engines (Google Ads and Microsoft Advertising). The portfolio is Google-dominated; the question is whether Microsoft's CPA is competitive.

**Category:** Aggregation + Join
**Difficulty:** Basic
**Business role:** Analyst

**Approach:**
Join `engine_account` to `campaign` to `daily_stats`, grouped by `engine_type`. `active_campaigns` uses `COUNT(DISTINCT c.id)` so `daily_stats` fan-out doesn't multi-count campaigns. The two columns to focus on are `avg_cpc` and `cpa`: Microsoft's CPC is notably below Google's (about 80%), but the conversion rate is also about 12% lower; the two opposing effects cancel and the engines end up at comparable CPA. The takeaway is that engines differ on cost dynamics, not on conversion quality. Maps to the business question of cross-engine efficiency.

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

**Expected result description:**
2 rows. Google Ads carries about 75% of impressions and spend; Microsoft Advertising about 25%. Microsoft Advertising's average CPC is notably lower (about 80% of Google's) but its conversion rate is about 12% lower, so the two engines end up with comparable CPA. ROAS is also similar — engines differ on cost dynamics, not on conversion quality.

---

### Query 8: Quality Score distribution by industry

**Business context:**
A search analyst wants to know whether keyword Quality Score varies by industry — competitive verticals (insurance, finance) tend to have more keywords below QS 6. This guides which industries to prioritize for QS improvement work.

**Category:** Aggregation + Join
**Difficulty:** Intermediate
**Business role:** Analyst

**Approach:**
`keyword` joins all the way up through `ad_group`, `campaign`, `advertiser`, and `industry` to tag each keyword with its industry, then aggregates Quality Score by industry. The bucket counts (QS less than 5, 5 to 7, more than 7) use `SUM(CASE WHEN ... THEN 1 ELSE 0 END)` — the standard SQL trick for building a histogram. Following the "active" convention, all three levels are filtered to `status = 'Enabled'`, so paused or removed entities don't pollute the distribution. As expected, high-competition industries (insurance, finance, real estate) skew toward lower average QS and a higher share of low-QS keywords; low-competition industries (B2B SaaS, education, food service) skew the other way. Maps to the business question of waste cleanup.

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

**Expected result description:**
10 rows — one per industry, sorted descending by low-QS share. Only Enabled keywords under Enabled ad groups under Enabled campaigns are counted (per the "active" convention). The generator biases QS by industry competitiveness: insurance / finance / real estate draw from a left-shifted distribution (average QS around 6.1, about 35–37% below 6); low-competition B2B SaaS / education / food service draw from a right-shifted distribution (average QS around 7.5, about 10% below 6). Other industries land in the middle (around 6.9 average, about 18% below 6).

---

### Query 9: Low-QS keywords inside high-spend campaigns

**Business context:**
A senior analyst is hunting for the worst-performing keywords: low-QS keywords that sit inside campaigns with real spend. **Important caveat:** `daily_stats` is at campaign grain, not keyword grain, so this query can't compute *keyword-level* spend; it surfaces low-QS keywords whose *host campaign* spent more than $5,000 in the last 30 days. The actionable reading is "these campaigns with this much budget running through them contain this batch of low-QS keywords — fix the landing pages or ad-relevance signals on these keywords first."

**Category:** Cross-level Join
**Difficulty:** Advanced
**Business role:** Analyst

**Approach:**
The critical realization for this query is that `daily_stats` is campaign-grain, not keyword-grain, so it can't compute spend at the keyword level — only the spend of the keyword's host campaign. `keyword` joins `campaign` and then `daily_stats`; every keyword row fans out across all performance rows of its host campaign, and `GROUP BY` per keyword followed by SUM is actually "host campaign spend," which is why the column is named `host_campaign_spend_30d` deliberately, to keep readers from misreading it as keyword-level spend. Filter to low QS (less than 6) and use `HAVING` to require campaign spend over $5,000. Maps to the business question of waste cleanup.

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

**Expected result description:**
Up to 30 low-QS keywords whose host campaign spent more than $5,000 in the last 30 days. The column is named `host_campaign_spend_30d` (not `keyword_spend_30d`) because `daily_stats` is campaign-grain — this dollar figure is the host campaign's spend, not the keyword's. Use as a prioritization list for quality-improvement work.

---

### Query 10: High-cost zero-conversion search terms

**Business context:**
A campaign operations specialist runs a weekly "negative keyword review": search terms that spent budget without producing any conversions. These are candidates for the negative-keyword exclusion list, reclaiming budget for queries that do convert.

**Category:** LEFT JOIN + aggregation
**Difficulty:** Basic
**Business role:** Operations

**Approach:**
`search_term_report` LEFT JOINs `keyword` because about 15% of search-term rows are broad-match overflow (`keyword_id` is NULL); only a LEFT JOIN keeps those rows. An INNER JOIN would silently drop exactly the overflow terms that most need excluding — losing the answer. Aggregate by search term, and use `HAVING SUM(conversions) = 0 AND SUM(cost) > 50` to surface "burned budget, zero conversions." When `matched_keyword` is NULL in the result, that's a useful signal in itself: pure broad-match leaks often dominate this candidate list. Maps to the business question of waste cleanup.

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

**Expected result description:**
Up to 30 search terms with more than $50 spent and zero conversions in the last 14 days. `matched_keyword` may be NULL — meaning the term was broad-match overflow (no stored keyword matched it directly), which is itself a useful signal: pure broad-match leaks tend to dominate this list.

---

### Query 11: Broad-match overflow share

**Business context:**
A paid-search analyst wants to know how much of the search-term impressions come from broad-match overflow versus from queries that mapped to a stored keyword. An ad group with a disproportionate overflow share signals that the match-type strategy is too loose.

**Category:** NULL handling + aggregation
**Difficulty:** Intermediate
**Business role:** Analyst

> **Portability note:** the `HAVING overflow_pct > 20` clause references a `SELECT` alias, which SQLite accepts but strict ANSI SQL does not. See the Notes at the bottom for a portable rewrite.

**Approach:**
The core trick is `SUM(CASE WHEN str.keyword_id IS NULL THEN 1 ELSE 0 END)` to count overflow rows, divided by `COUNT(*)` for the overflow share, grouped by campaign and ad group. This is the classic NULL-handling problem: `keyword_id IS NULL` marks queries the engine served that didn't match back to any stored keyword. Note that `HAVING overflow_pct > 20` references a SELECT alias — SQLite allows it, but strict ANSI does not (see the Notes for a portable rewrite). `overflow_cost_30d` uses the same CASE pattern to isolate the overflow spend. Maps to the business question of waste cleanup.

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

**Expected result description:**
Ad groups where more than 20% of search-term rows are broad-match overflow. `overflow_cost_30d` shows the actual dollars flowing to non-keyword-matched queries. The generator averages about 15% overflow, so this list naturally skews toward ad groups with elevated overflow rates.

---

### Query 12: First-touch vs last-touch channel mix

**Business context:**
The CMO wants to know whether the brand's last-touch attribution is masking the upper-funnel channels that kick off the customer journey. The classic answer is a side-by-side: what share of conversions does each channel claim as the first touch vs the last touch?

**Category:** CTE + aggregation
**Difficulty:** Advanced
**Business role:** Analyst

**Approach:**
First, a CTE computes per `conversion` the `MIN(touchpoint_order)` (first-touch index) and `MAX(touchpoint_order)` (last-touch index); then join back to `attribution_path` to keep only the rows at those two indices, and label each as first / last / single. Why one CTE with labels rather than two CTEs each LEFT-JOINed? Because joining two CTEs together by channel silently produces a Cartesian product and inflates the counts. The `single` label handles the case where a path has only one touchpoint, where first and last are the same row (this dataset's path lengths start at 2, but the safeguard is still there). Maps to the business question of attribution truth.

```sql
-- Single-CTE pattern that derives both first and last touch per conversion at once.
-- Avoids the "two CTEs each LEFT JOIN" pattern, which silently fans out by channel.
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

**Expected result description:**
6 rows (one per channel). Either percentage column should sum to roughly 100% across all channels. Display and Paid Social typically post a higher first-touch share than last-touch share (their upper-funnel role); Paid Search and Direct typically show the opposite.

---

### Query 13: Conversion path-length distribution

**Business context:**
A marketing analyst wants the touchpoint-count distribution: how many conversions are "single-touch" vs "multi-touch," and how long is a typical path? This indicates whether multi-touch attribution is worth operationalizing.

**Category:** Subquery + aggregation
**Difficulty:** Intermediate
**Business role:** Analyst

**Approach:**
The inner subquery computes per `conversion` the `MAX(touchpoint_order)` to get the path length; the outer query GROUPs BY path length and counts conversions. The percentage uses the `COUNT(*) * 100.0 / SUM(COUNT(*)) OVER ()` trick (aggregating on top of an aggregate via a window function), which avoids writing a second subquery for the total. The generator samples path length from a truncated geometric distribution (weights `[40, 30, 15, 10, 5]` for N = 2 to 6), so 2-touchpoint paths should dominate (about 40%) and 6-touchpoint paths should be rare. Maps to the business question of attribution truth.

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

**Expected result description:**
5 rows covering path lengths 2 through 6 (the generator never produces path length = 1). The generator samples from a truncated geometric distribution with weights `[40, 30, 15, 10, 5]`, so 2-touchpoint paths dominate (about 40%) and 6-touchpoint paths are rare (about 5%) — close to the real-world pattern where most conversions are short paths.

---

### Query 14: Channel value under each attribution model

**Business context:**
An executive wants to see how channel valuation shifts with the attribution model: paid search's share under last-click is almost always higher than under data-driven, and the executive wants to quantify the gap.

**Category:** Aggregation + Join
**Difficulty:** Intermediate
**Business role:** Executive

**Approach:**
`attribution_path` joins `conversion` to pick up each conversion's value and joins `channel` to pick up the channel name. The six value columns each multiply one model's credit by `conversion_value` and sum — a single scan produces channel valuation under all six models. Because this dataset biases channels by touchpoint position (Display and Paid Social favor first touches; Paid Search and Direct favor last touches), the last-click model visibly overcredits Paid Search and Direct, while the first-click model overcredits Display and Social — exactly the classic last-click lower-funnel bias. Note that the `data_driven` column is a simulated random value and should not be read as actual DDA output. Maps to the business question of attribution truth.

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

**Expected result description:**
6 rows (one per channel). The 6 value columns are credit weighted by conversion amount and summed. Because the channel mix in this dataset is biased by touchpoint position (Display / Paid Social skew first-touch; Paid Search / Direct skew last-touch), last-click notably overcredits Paid Search and Direct, and first-click notably overcredits Display and Paid Social — the classic last-click "lower-funnel bias" is observable.

> **Caveat about `data_driven_value`.** In this dataset, `data_driven_credit` is a per-touchpoint normalized random value, not the output of a real DDA model. The column exists so learners can write six-model comparison queries; do not interpret the absolute `data_driven_value` figures as "what the data-driven model would say."

---

### Query 15: Budget-constrained campaigns

**Business context:**
A campaign manager wants to identify campaigns losing impression share due to budget — the ones where adding budget would directly buy more impressions. This is the "easy money" list for the weekly optimization meeting.

**Category:** CTE + correlated subquery
**Difficulty:** Advanced
**Business role:** Manager

**Approach:**
The skeleton is the same as Query 4 (correlated subquery for daily in-effect budget, then aggregate to campaign-day grain), but the metric of interest is now `lost_is_budget` (impression share lost to budget). After aggregating to campaign grain, compute the 7-day average `lost_is_budget` and `HAVING avg_lost_is_budget > 15` to surface campaigns that consistently lose impressions to budget. The generator biases `lost_is_budget` upward when daily spend approaches the in-effect budget, so this list naturally surfaces campaigns hitting their daily cap — the "add budget, get more impressions" list for the optimization meeting. Maps to the business question of budget efficiency.

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

**Expected result description:**
Up to 20 Enabled campaigns with a 7-day average `lost_is_budget` above 15. Because the generator biases `lost_is_budget` upward when spend approaches the in-effect budget, this list naturally surfaces campaigns hitting their daily budget cap.

---

### Query 16: Campaigns holding top page positions (Search-only, impression-weighted)

**Business context:**
A campaign manager wants to see which Search campaigns dominate the search results page (high `search_top_is`) — these are the "premium real estate" healthy campaigns whose budget and bidding are dialed in. The opposite list (low share) is the next slide.

**Category:** Aggregation + Join + weighted average
**Difficulty:** Intermediate
**Business role:** Manager

**Approach:**
Two things matter. First, `search_*_is` is only populated on Search campaigns (NULL on non-Search rows), so the query must filter `campaign_type = 'Search'` to keep NULLs out of the aggregate. Second, impression share is an impression-weighted metric — all three position metrics must be computed as `SUM(IS × impressions) / SUM(impressions)`, not `AVG(IS)`, otherwise a low-volume desktop slice gets the same weight as a high-volume mobile day and the average becomes distorted. By construction, `abs_top_is <= top_is <= impression_share`, so the three columns are naturally ordered. `HAVING` requires impression volume above 10,000 to filter out small-sample noise. Maps to the business questions of budget efficiency and position health.

```sql
-- Impression share is an impression-weighted metric; SUM(IS × impressions) /
-- SUM(impressions) is the correct way to aggregate across days and devices.
-- A plain AVG(IS) would weight a low-volume desktop slice the same as a
-- high-volume mobile day.
-- search_*_is is NULL on non-Search rows, so a campaign_type filter is required.
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

**Expected result description:**
20 Search campaigns with strong absolute top-of-page impression share. The three position metrics are impression-weighted (so a high-volume mobile day outweighs a near-zero desktop day). By construction, `abs_top_is ≤ top_is ≤ impression_share`, so the three columns are ordered.

---

### Query 17: Agency portfolio performance by tier

**Business context:**
An agency executive wants to see performance by agency tier — do Platinum-tier agencies post better ROAS than Standard-tier? This is the KPI question for the agency parent company's quarterly review.

**Category:** Join + aggregation
**Difficulty:** Intermediate
**Business role:** Executive

**Approach:**
Join `agency` to `agency_client` (the bridge table) and then to `campaign` and `daily_stats`, grouped by `tier_level`. Filter `ac.is_active = 1` to count only currently active agency relationships. Because `agency_client` is currently used as 1:N and carries `UNIQUE(agency_id, advertiser_id)`, the bridge won't fan out the advertiser. The generator biases agency-to-advertiser assignment by `tier_level × company_size` (Platinum / Gold lean Enterprise / Mid-Market), so `total_spend` is largest at the high tiers; however, within each tier, CPA and ROAS still drift with the industry mix — the ordering is monotonic by spend but non-monotonic by ROAS, a useful teaching point: the largest agency tier is not automatically the most efficient. Maps to the business question of agency and portfolio structure.

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

-- Note: this query attributes spend to the *current* active agency (ac.is_active = 1).
-- It does not bound the spend window by the agency_client contract dates. In a real
-- audit, a campaign that switched agencies during the window would attribute early
-- spend to the previous agency; here it is all attributed to the current one.
```

**Expected result description:**
4 rows (Platinum / Gold / Silver / Standard). Platinum and Gold agencies manage more Enterprise / Mid-Market advertisers (the generator biases agency-to-advertiser assignment by `tier_level × company_size`), so `total_spend` is largest there. Within each tier, CPA and ROAS still drift with the industry mix; the ordering is monotonic by `total_spend` but non-monotonic by ROAS — a useful teaching point: "the largest agency tier is not automatically the most efficient."

---

### Query 18: Conversion latency by first-touch channel

**Business context:**
A marketing analyst wants to understand how long it takes for a user to convert after the first touch, broken down by channel. Long latency means that channel is playing an upper-funnel role; short latency means it's a closer.

**Category:** CTE + Join
**Difficulty:** Intermediate
**Business role:** Analyst

**Approach:**
First, a subquery computes per `conversion` the `MIN(touchpoint_order)` (first-touch index); join back to `attribution_path` to keep only the first-touch row, pull `hours_before_conv` and `days_before_conv`, then aggregate average latency by first-touch channel. By construction, `hours_before_conv` is bounded by the conversion's Floodlight tag `lookback_window`, so `max_days_to_conv` tops out at 90. Channels that more often play the first-touch role have a higher average hours-before-conversion (they appear higher in the table), signaling an upper-funnel role; short latency means a closer role. Maps to the business question of attribution truth.

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

**Expected result description:**
6 rows. By construction, `hours_before_conv` is bounded by the conversion's tag `lookback_window`, so `max_days_to_conv` tops out at 90. Channels that more often play the first-touch role have a higher average hours-before-conversion (they appear at the top of the table).

---

### Query 19: Week-over-week CPA diagnostic

**Business context:**
An agency manager noticed that last week's CPA is up versus the prior week and wants to decompose it: is CPC creeping up, CTR softening, or conversion rate collapsing? This is the classic "why did CPA move?" diagnostic.

**Category:** CTE + CASE + date arithmetic
**Difficulty:** Advanced
**Business role:** Manager

**Approach:**
A `CASE` tags each `daily_stats` day as `this_week` or `last_week` (based on `report_date` relative to the reference date); the CTE aggregates spend, avg_cpc, ctr, conv_rate, and cpa per period. The final layer uses `MAX(CASE WHEN period = ... THEN ... END)` to pivot the two weeks' metrics side by side into a single row — a common SQL row-to-column transformation. With the two weeks side by side, the analyst can mechanically decompose the CPA change into CPC, CTR, and conversion-rate factors: for example, CPC up 10% and conversion rate down 5% gives roughly +15% CPA. If none of those three factors moved but CPA did, the change is from a shift in the mix of high- vs low-CPA campaigns within the portfolio. Maps to the business questions of cross-engine efficiency and budget diagnostics.

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

**Expected result description:**
A single row containing this week's and last week's values for spend, CPA, CPC, CTR, and conv_rate. This decomposition lets the analyst attribute the CPA change to specific factors: for example, CPC up 10% and conv_rate down 5% gives a mechanical CPA rise of about 15%. If only CPA moves while CPC / CTR / conv_rate are flat, the cause is a shift in the mix of high- vs low-CPA campaigns within the portfolio.

---

### Query 20: Keyword coverage in search-term report

**Business context:**
A search ops specialist wants to know how many Enabled keywords actually have search-term data in the last 30 days. A keyword with no search-term rows is either newly added, paused at the engine layer, or sitting in a low-volume vertical — all worth flagging.

**Category:** LEFT JOIN + aggregation
**Difficulty:** Basic
**Business role:** Operations

**Approach:**
`keyword` joins up to industry, then LEFT JOIN to a subquery counting "how many search-term rows each keyword has." The LEFT JOIN is essential: it preserves keywords with zero search-term rows, which are precisely the coverage gaps we're looking for; an INNER JOIN would silently drop them and the coverage rate would be artificially inflated. The subquery filters `keyword_id IS NOT NULL` (counting only rows that mapped back to a stored keyword). Group by industry; `coverage_pct` is the share of Enabled keywords with at least one matched search-term row. Because each keyword is sampled across roughly 5 days and the overflow rate is only 15%, the probability that all of a keyword's sampled rows are overflow is extremely small, so coverage by industry should sit near 99% — anything notably lower indicates a real search-term tracking gap. Maps to the business questions of waste cleanup and data quality.

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

**Expected result description:**
10 rows (one per industry). `coverage_pct` is the share of Enabled keywords that have at least one matched `search_term_report` row (with `keyword_id` non-NULL) in the last 30 days. The stratified sampler produces about 5 days × 1–2 rows of search terms per keyword, of which about 15% have NULL `keyword_id` (broad-match overflow). The probability that all ~7 sampled rows for one keyword **all** turn out to be broad-match overflow is `0.15^7 ≈ 1.7e-6`, so coverage by industry should sit at the high 99%s. A noticeably lower `coverage_pct` here indicates a real search-term tracking gap, not the row-level broad-match overflow rate.

---

## Query Category Summary

Each query is counted once under its primary technique.

| Category | Count | Query numbers |
|---|---:|---|
| Aggregation + simple Join | 6 | 1, 2, 6, 7, 14, 17 |
| Window function | 1 | 3 |
| CTE / correlated subquery | 6 | 4, 5, 12, 15, 18, 19 |
| Cross-level / multi-table Join | 2 | 8, 9 |
| LEFT JOIN + aggregation | 2 | 10, 20 |
| NULL handling + aggregation | 1 | 11 |
| Subquery + aggregation | 1 | 13 |
| Weighted aggregation | 1 | 16 |
| Total | **20** | |

## Business Role Coverage

| Role | Count | Queries |
|---|---:|---|
| Executive | 4 | 1, 2, 14, 17 |
| Manager | 5 | 3, 4, 15, 16, 19 |
| Analyst | 9 | 5, 6, 7, 8, 9, 11, 12, 13, 18 |
| Operations | 2 | 10, 20 |
| **Total** | **20** | |

## Difficulty Distribution

| Difficulty | Count | Queries |
|---|---:|---|
| Basic | 6 | 1, 2, 6, 7, 10, 20 |
| Intermediate | 9 | 3, 5, 8, 11, 13, 14, 16, 17, 18 |
| Advanced | 5 | 4, 9, 12, 15, 19 |
| **Total** | **20** | |

---

## Notes

- All queries are written for SQLite 3.x.
- All time-window queries reference `v_reference_date`. After regenerating the dataset, the view automatically re-anchors to the new max date — no query rewrite needed.
- Boolean columns (`is_active`, `is_automated`) can be compared with `= 1` or `= 0`. The loader normalizes both `0/1` and `true/false` TSV representations to SQLite integers.
- Queries that aggregate `search_*_is` columns (only Query 16) must filter `campaign_type = 'Search'` — these columns are NULL on Display / Video / Performance Max / Shopping rows.
- `keyword` is a reserved word in PostgreSQL / Oracle / SQL Server. SQLite accepts it unquoted; when porting to other dialects, quote it as `"keyword"` (or alias with `keyword AS k` and reference `k`).
- **In strict SQL, `HAVING` cannot reference a `SELECT` alias.** Query 11 has `HAVING overflow_pct > 20`, which works in SQLite because it resolves `SELECT` aliases before evaluating `HAVING`. PostgreSQL and Oracle don't allow this — when porting, repeat the expression (`HAVING SUM(CASE WHEN keyword_id IS NULL THEN 1 ELSE 0 END) * 100.0 / COUNT(*) > 20`), or wrap the inner aggregate in a CTE and filter in the outer `WHERE`.
