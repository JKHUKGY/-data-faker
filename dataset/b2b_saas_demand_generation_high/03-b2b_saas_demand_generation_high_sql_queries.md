# B2B SaaS - Demand Generation SQL Query Reference

> Companion documents: business context lives in `01-b2b_saas_demand_generation_high_business_context.md`; table schemas and the ER diagram live in `02-b2b_saas_demand_generation_high_er_document.md`.
> All queries are compatible with SQLite 3.x. Reference "today" = `2026-06-01`.
> Database file: `b2b_saas_demand_generation_high.sqlite`

## Overview

This document provides **50 SQL queries** designed to comprehensively demonstrate the analytical coverage of the Stratosend B2B SaaS demand-generation dataset.

Following the guidance in the BI Blueprint section of the ER document, the queries are split into two pedagogical categories:

| Category | Count | Style | Purpose |
|----------|-------|-------|---------|
| **Dashboard-style** (D1–D15) | 15 (30%) | Snapshot, aggregation-heavy, fixed metrics | Each query corresponds to one L2/L3 dashboard widget |
| **Business-question-style** (B1–B35) | 35 (70%) | Diverse, exploratory, technique-rich | Each query answers one standalone ad-hoc analysis question |

## How to Use This Document

This document is written for interns and junior analysts who have just joined Stratosend. It assumes you have already read the business context document (`01-...business_context.md`) and the ER document (`02-...er_document.md`), and you know what the company sells, what the funnel looks like, and how the 16 tables hang together. Now your manager has handed you this document and said, "Go through these queries this week." It is not a script collection to copy-paste and run, but project hand-off material that walks you through how to think.

Each query corresponds to a real business question from the business context document: a CMO is doing a quarterly budget review, an SDR Manager just noticed reply rates dropped, a RevOps analyst needs to reconcile slipped deals before the forecast meeting. The value of a query is not the table it returns — it is the decision that table supports. As you read, treat the SQL as something to understand and learn from, not just a command to execute. Understanding *why* someone joined this way or *why* they used a CTE here is far more important than memorizing the syntax.

To that end, each query is organized into the same five sections, each with its own role:

- **Business Context**: Who is asking, why, what decision the answer supports, why it is urgent right now.
- **Category / Difficulty / Role**: Three labels indicating which SQL techniques the query uses, how hard it is, and which role it serves.
- **Approach**: Before showing you the code, the approach walks you through the thinking. Which tables to touch, how to build the joins, where the traps are (fan-out duplication, cardinality errors, whether to use LEFT or INNER), what a row of output represents, why a window function or CTE is appropriate. After reading the approach, the SQL will make sense.
- **SQL**: The query itself, ready to run against the database.
- **Expected Result and Business Conclusion**: First a description of the result shape (number of rows, columns, order of magnitude), then what the analyst should *do* with it. Producing a number is the start of analysis, not the end.

A note on dates: the entire dataset is anchored at the fixed reference date `2026-06-01`. Every query writes that date as a literal (e.g. `DATE('2026-06-01', '-30 days')`), not `DATE('now')`. This way the results are stable no matter which day you run them, which makes it easy to compare against the order-of-magnitude expectations in this document. Only in a production system would you swap it for `DATE('now')`.

## Query Index

### Dashboard-style queries (D1–D15)

| # | Title | Dashboard | Role | Category | Difficulty |
|---|-------|-----------|------|----------|------------|
| D1 | Quarterly Marketing P&L by Channel | CMO Quarterly P&L | CMO | CTE + Aggregation | Intermediate |
| D2 | Open Pipeline and Coverage by Stage | VP Sales Pipeline Health | VP Sales | Aggregation + Subquery | Intermediate |
| D3 | Blended CAC and Payback by Channel | CFO Unit Economics | CFO | CTE + Aggregation | Advanced |
| D4 | Quarterly Lead Cohort Maturation | CRO Cohort | CRO | CTE + Date Bucketing | Advanced |
| D5 | 12-Month Rolling Win-Rate Trend | Executive Win Rate | Executive | Window Function | Advanced |
| D6 | Daily Funnel Snapshot (Last 30 Days) | Daily Funnel | Demand Gen Manager | Date Bucketing | Basic |
| D7 | SDR 30-Day Productivity Board | SDR Productivity | SDR Manager | Aggregation + Join | Intermediate |
| D8 | AE Open Pipeline Board | AE Pipeline | VP Sales | Aggregation + Join | Intermediate |
| D9 | Active Campaign Plan vs Actual Tracker | Active Campaign Tracker | Demand Gen Manager | Multi-Join + Aggregation | Intermediate |
| D10 | This Week's Hot Content | Content Heatmap | Content Marketing | Aggregation + Date Filter | Basic |
| D11 | ABM Tier-1 7-Day Engagement Pulse | ABM Pulse | ABM Lead | Multi-Join + Date | Intermediate |
| D12 | Stale Opportunity Alerts (30+ Days) | Stale Opp Alert | VP Sales | Date Difference | Basic |
| D13 | MQL Aging Buckets | MQL Aging | Marketing Ops | Date Bucketing | Basic |
| D14 | Manager Team Rollup (Self-Join FK) | Manager Rollup | VP Sales | Self-Join | Intermediate |
| D15 | Today's Weighted Forecast | Forecast | RevOps | Aggregation | Basic |

### Business-question-style queries (B1–B35)

| # | Title | Subject Area | Role | Category | Difficulty |
|---|-------|--------------|------|----------|------------|
| B1 | Full Funnel: Lead → MQL → SQL → Opp → Won | A Demand | VP Marketing | CTE + Aggregation | Intermediate |
| B2 | MQL Aging by Source | A Demand | Marketing Ops | Date Math + Aggregation | Intermediate |
| B3 | Lead-Score Deciles and Win Rate | A Demand | Marketing Ops | CTE + NTILE | Advanced |
| B4 | Disqualification Reason × Source Matrix | A Demand | Marketing Ops | Pivot + Aggregation | Intermediate |
| B5 | Persona × Seniority Conversion Matrix | A Demand | Marketing Ops | Pivot + Aggregation | Intermediate |
| B6 | Multi-Visit Lead Behavior Lift | A Demand | Analyst | Window + Filter | Advanced |
| B7 | Lead Source Quality Decay by Quarter | A Demand | Analyst | CTE + Date Bucketing | Advanced |
| B8 | Top Campaigns by Influenced Pipeline | B Campaign | Demand Gen Manager | Multi-Join + Aggregation | Intermediate |
| B9 | End-to-End Webinar Funnel | B Campaign | Content Marketing | CTE + Multi-Join | Advanced |
| B10 | Campaign Type ROI Comparison | B Campaign | Demand Gen Manager | Aggregation + Join | Intermediate |
| B11 | First-Touch Winning Campaign Analysis | B Campaign | Demand Gen Manager | Multi-Join + Aggregation | Intermediate |
| B12 | Content Asset Influence on Won Pipeline | B Content | Content Marketing | Multi-Join + Aggregation | Advanced |
| B13 | Content Topic × Persona Affinity | B Content | Content Marketing | Pivot + Aggregation | Intermediate |
| B14 | Gated vs Ungated Content Conversion Lift | B Content | Marketing Ops | CTE + Aggregation | Intermediate |
| B15 | Email_Blast Re-engagement of Dormant Leads | B Campaign | Demand Gen Manager | Date Difference + Filter | Advanced |
| B16 | Sales Cycle by Tier (Median + p90) | C Pipeline | VP Sales | Aggregation + Percentile | Intermediate |
| B17 | Stage-to-Stage Conversion + Median Stage Days | C Pipeline | VP Sales | Self-Join + CTE | Advanced |
| B18 | Won/Lost Reason Matrix by Competitor and Industry | C Pipeline | RevOps | Pivot + Aggregation | Intermediate |
| B19 | Stage Regression Detection (Opps Moving Backward) | C Pipeline | RevOps | Self-Join | Advanced |
| B20 | Forecast Variance — Forecast vs Actual | C Pipeline | RevOps | Date Math + Aggregation | Advanced |
| B21 | Slipped Opportunities — Close Date Pushed 2+ Times | C Pipeline | RevOps | Aggregation on history | Advanced |
| B22 | Open Pipeline Concentration Risk | C Pipeline | VP Sales | Window + Cumulative | Advanced |
| B23 | SDR SLA Compliance — MQL → First Email Within 24 Hours | D Productivity | SDR Manager | Date Difference + Self-Join | Advanced |
| B24 | AE Quota Attainment Ranking | D Productivity | VP Sales | Aggregation + Join | Basic |
| B25 | SDR Sequence-Step Funnel Decay | D Productivity | SDR Manager | Aggregation by step | Basic |
| B26 | Reply Sentiment Distribution by Sales Rep | D Productivity | SDR Manager | Pivot + Aggregation | Intermediate |
| B27 | Manager Team Rollup (Won ARR via Self-Join FK) | D Productivity | VP Sales | Self-Join + Aggregation | Intermediate |
| B28 | Rep Ramp Analysis (Hire → First Won Deal) | D Productivity | VP Sales | Date Difference + Join | Intermediate |
| B29 | First-Touch vs Last-Touch vs W-Shaped Attribution | E Attribution | RevOps | CTE + Window | Advanced |
| B30 | Source × Tier Win-Rate Pivot Matrix | E Attribution | Demand Gen Manager | Pivot + Aggregation | Intermediate |
| B31 | CAC Payback by Channel | E Attribution | CFO | CTE + Aggregation | Advanced |
| B32 | Influenced Pipeline Hidden in W-Shaped Attribution | E Attribution | RevOps | Multi-Join + Filter | Advanced |
| B33 | ABM Multi-Stakeholder Coverage Depth | F ABM | ABM Lead | Multi-Join + Aggregation | Intermediate |
| B34 | ABM vs Non-ABM Win Rate Comparison | F ABM | VP Sales | Aggregation + Filter | Basic |
| B35 | Account Expansion — Customers with Multiple Wins | F ABM | RevOps | Aggregation + HAVING | Intermediate |

---

## Attribution Dimension Glossary

The word "channel" is heavily overloaded in marketing analytics. The queries below use four *different* dimensions — do not join them as if they were the same:

| Dimension | Source Field | Cardinality | Example Values | Used By |
|-----------|--------------|-------------|----------------|---------|
| `campaign_type`     | `campaign.campaign_type`     | 8 | `Webinar`, `Paid_Search`, `ABM_Sequence`, … | D1 spend and pipeline, B10 |
| `campaign_code`     | `campaign.campaign_code`     | ~80 | `WBR-202505-059`, `ABM-202501-057`, … | B29 (all 3 CTEs), B11 |
| `source_code`       | `lead_source.source_code`    | 10 | `PAID_SEARCH_GOOGLE`, `WEBINAR_HOSTED`, … | D3, B30, B31 |
| `source_category`   | `lead_source.source_category`| 4 | `Inbound`, `Outbound`, `Partner`, `Event` | — (reference only) |

Rule of thumb: pick one dimension per query and use it consistently. An early draft of D1 mixed `campaign_type` and `source_category` in a `FULL OUTER JOIN`, which produced rows that could never match — the revised version below uses `campaign_type` end-to-end.

---

# Dashboard-Style Queries (D1–D15)

Each query drives one dashboard widget. They tend to be aggregation-heavy and snapshot-oriented.

---

## D1: Quarterly Marketing P&L by Channel

**Dashboard:** CMO Quarterly P&L

**Business Context:** Each quarter the CMO reviews marketing spend versus pipeline produced and decides how to reallocate the budget for next quarter. The question is: for every dollar spent in each channel (lead source), how much **influenced pipeline ARR** did it produce? Channels with weak ROI get cut; channels with strong ROI get more budget. This widget on the CMO dashboard shows the trend across the past 6 quarters.

**Category:** CTE + Aggregation
**Difficulty:** Intermediate
**Business Role:** CMO

**Approach:** This query needs to align two things at the "quarter × channel" grain: how much was spent, and how much Won ARR came back. Spend comes from the `campaign` table (using `campaign_type` as channel). Pipeline has to be joined from `opportunity` back through `lead`, and then through `lead.source_campaign_id` to `campaign`, so every Won deal can be tagged with a campaign_type. The two sides have different grains (one bucketed by campaign start date, one by actual close date), so we aggregate each in its own CTE (`spend` and `pipeline`) and then stitch them together by `(qtr, channel)`. The trap: about 30% of opps are direct outbound with `source_lead_id IS NULL` and cannot be attributed to a campaign — the INNER JOIN naturally excludes them (intentional; see the Note). We would normally use `FULL OUTER JOIN` to preserve both "spend with no Won" and "Won with no spend" channels, but older SQLite versions do not support it, so we emulate full outer with the portable "LEFT JOIN ... UNION ALL ... WHERE IS NULL" pattern. Quarter bucketing uses STRFTIME to map the month into Q1–Q4.

```sql
-- Channel = campaign_type here. Only lead-sourced Wins can be attributed
-- back to a campaign (direct-outbound opps with source_lead_id NULL are
-- excluded — see note).
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
-- Portable equivalent of FULL OUTER JOIN spend ⨝ pipeline
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

> Note: About 30% of opps are direct-outbound (`source_lead_id IS NULL`) and have no campaign attribution. They are excluded from `pipeline` by design — campaign ROI only compares campaign-influenced Wins against campaign spend. To include them, you could add an "Outbound" bucket using `lead_source.source_category` and union it in, but be aware the channel dimensions are not directly comparable.

> SQLite Note: The original version used `FULL OUTER JOIN` (requires SQLite 3.39+). The version above uses the portable `LEFT JOIN … UNION ALL LEFT JOIN … WHERE … IS NULL` pattern, which works in any SQL dialect.

**Expected Result:** ~30–50 rows (6 quarters × 5–10 channels). Each row shows quarterly spend vs Won ARR for one channel, plus a `roi_ratio`. Top winners are typically `Webinar`, `ABM_Sequence`, and `Conference_Event` (ROI 1–5x); weaker performers are often `Paid_Social` and `Content_Syndication`.

---

## D2: Open Pipeline and Coverage by Stage

**Dashboard:** VP Sales Pipeline Health

**Business Context:** Every Monday the VP Sales opens this dashboard to assess whether the team has enough open pipeline to hit quota. The classic SaaS rule of thumb is "3x coverage" — open pipeline should be ≥ 3× remaining quota. If coverage drops below 3x, an urgent SDR push is needed.

**Category:** Aggregation + Subquery
**Difficulty:** Intermediate
**Business Role:** VP Sales

**Approach:** The core task is to aggregate open pipeline (`opportunity` join `opportunity_stage` where `is_closed = 0`) by stage and then compare it against the team's total quota. Quota comes from `sales_rep` but at a different grain (a scalar), so a separate `quota` CTE sums every active AE's `quota_usd` into one number. The two CTEs are joined with an unconditional `FROM pipe p, quota q` cross-product (quota has only one row, so this is a safe cross join that hands the same total quota to every stage row). One row of output = one sales stage. Note the intentional distinction between two coverage ratios: `stage_coverage_ratio` is that stage's open ARR / total quota, while `total_coverage_ratio` uses the window function `SUM(...) OVER ()` to add up the open ARR across all stages and divide by quota, producing the classic 3x coverage KPI (same value on every row). The weighted ARR multiplies by `typical_win_probability_pct` to reflect each stage's different odds of closing.

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

**Expected Result:** 5 rows (Discovery, Demo, Eval/POC, Proposal, Negotiation). Each row shows opp count, open ARR, win-probability-weighted ARR, and two coverage views: `stage_coverage_ratio` (that stage's open ARR / total team quota — by stage) and `total_coverage_ratio` (the classic "3x coverage" KPI: all open ARR / total team quota — same value on every row). The 3x rule of thumb applies to `total_coverage_ratio`; the per-stage values just show where the pipeline is concentrated. Most pipeline typically sits in Discovery (60–70% of open opps).

---

## D3: Blended CAC and Payback by Channel

**Dashboard:** CFO Unit Economics

**Business Context:** The CFO needs to know the cost to acquire each customer, broken down by channel. Blended CAC = total spend in the channel / number of new logos. Payback period (months) = CAC / monthly ARR. A healthy SaaS target is SMB payback < 18 months and Enterprise payback < 24 months.

**Category:** CTE + Aggregation
**Difficulty:** Advanced
**Business Role:** CFO

**Approach:** CAC takes "total spend per channel" and divides by "new logos from that channel" — numerator and denominator are at different grains, so each must be aggregated separately and then joined; you cannot compute them in one big join (or spend would be multiplied by the number of Won rows). `channel_spend` estimates the spend proxy using `lead_source.typical_cost_per_lead_usd × COUNT(lead)` (because actual campaign spend is not tagged by source), and uses LEFT JOIN lead so sources with zero leads survive. `channel_wins` takes Won opps and counts distinct accounts (`COUNT(DISTINCT account_id)`) per `source_code` so that one customer with multiple Wins is not counted as multiple new logos. The two CTEs are joined by source_code with LEFT JOIN, so channels that had spend but no Wins still appear (their CAC will be NULL because the denominator is 0, guarded by NULLIF). For payback period, the denominator is monthly ARR (Won ARR / logos / 12); every division is wrapped in NULLIF to guard against zero division. Finally, `ORDER BY cac_usd IS NULL, cac_usd ASC` emulates NULLS LAST so channels with uncomputable CAC sink to the bottom.

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
  -- Spend allocated to source: proxy with
  -- lead_source.typical_cost_per_lead × lead count when actual
  -- campaign spend is not tagged by source.
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
-- Portable ASC "NULLS LAST" (works on SQLite < 3.30)
ORDER BY cac_usd IS NULL, cac_usd ASC;
```

**Expected Result:** 10 rows (one per lead source). Lowest CAC is typically `OUTBOUND_SDR` (only sunk cost) and `PARTNER_REFERRAL` (essentially free). Highest CAC is `CONFERENCE_EVENT`, because CPL is high. Payback periods vary widely — channels with single high-ARR Wins (Enterprise-skewed) can pay back faster even with a high CAC.

---

## D4: Quarterly Lead Cohort Maturation

**Dashboard:** CRO Cohort

**Business Context:** The CRO wants to see how lead cohorts mature over time — does the Q1 cohort, with 6 months of nurturing, outperform the Q4 cohort with only 2 months? This widget shows, per lead-creation quarter: total leads, share that became MQLs, share SQLs, share Won — all observed as of TODAY. Older cohorts have more time to convert.

**Category:** CTE + Date Bucketing
**Difficulty:** Advanced
**Business Role:** CRO

**Approach:** This is a cohort-maturation question. The key is to "bucket leads by creation quarter and observe how far down the funnel they have reached by today." The `lead_cohort` CTE computes the quarter bucket from `created_at` and also materializes several boolean flags (`mql_date IS NOT NULL`, `sql_date IS NOT NULL`, whether status is converted) right there, because those state fields are already reconciled on the `lead` table and we do not have to revisit the event tables. Won is the special case — it requires joining `opportunity` to `opportunity_stage` (`is_won = 1`) and looking back at `source_lead_id`, so a separate `opp_wins` CTE collects the distinct winning lead ids. Critically the cohort and opp_wins must be joined with LEFT JOIN, not INNER, otherwise leads that never closed (the vast majority) would be dropped, the denominator would collapse, and each cohort's conversion rate would be massively overstated. One row of output = one cohort quarter, with absolute counts and percentages for each stage. Older cohorts should show higher % Won because they had more time to mature — exactly the trend the CRO wants to see.

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

**Expected Result:** ~6 rows (one row per quarter in the past 18 months). Older cohorts (2024-Q4, 2025-Q1) should show higher % Won than newer ones (2026-Q1, 2026-Q2), because they had more time to mature. Lead→MQL rates should be roughly consistent across cohorts; Lead→Won is lower for newer cohorts.

---

## D5: 12-Month Rolling Win-Rate Trend

**Dashboard:** Executive Win Rate

**Business Context:** A single-line trend chart for the executive team showing whether the team's overall win rate is improving or deteriorating. The metric is win rate on closed opportunities, computed in a 90-day rolling window, plotted over the past 12 months.

**Category:** Window Function
**Difficulty:** Advanced
**Business Role:** Executive

**Approach:** This query only touches `opportunity` and `opportunity_stage`. The `closed` CTE first pulls opps that closed within the last 365 days and have an `actual_close_date` (the lower bound uses the literal `DATE('2026-06-01', '-365 days')`). Then `monthly` aggregates the closed count and won count by month. The real trick is in the outer query: the window function `SUM(...) OVER (ORDER BY yr_month ROWS BETWEEN 2 PRECEDING AND CURRENT ROW)` computes a 3-month rolling sum, and the rolling win rate is computed by dividing those rolling sums. We use the window function rather than a self-join because monthly data is naturally ordered, and a sliding window covers it in a single clause — a self-join would be more verbose. One row = one month, with both the raw monthly win rate and the rolling rate so executives can see the trend without being distracted by single-month noise. Don't forget to wrap the rolling division in NULLIF in case a window has no closed opps.

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

**Expected Result:** ~12 rows, one per month. Each row includes the raw monthly win rate and the 3-month rolling win rate (smoother). Expect a ~18–25% win-rate trend; the rolling line will be smoother than the monthly bars. Over the year you should see a gradual improvement or deterioration trend.

---

## D6: Daily Funnel Snapshot (Last 30 Days)

**Dashboard:** Daily Funnel

**Business Context:** Every morning the Demand Gen Manager checks how many leads / MQLs / SQLs / opportunities came in yesterday and compares them to the 30-day average. If yesterday is meaningfully off-trend, it triggers an investigation (e.g., paid search outage, broken form).

**Category:** Date Bucketing
**Difficulty:** Basic
**Business Role:** Demand Gen Manager

**Approach:** The four funnel stages (lead / MQL / SQL / opp) live in different date columns: lead intake uses `lead.created_at`, MQL uses `lead.mql_date`, SQL uses `lead.sql_date`, and opp uses `opportunity.created_at`. Their "date keys" have different semantics, so you cannot bucket by four dates in a single GROUP BY. The fix is to compute four per-day CTEs and stitch them into a wide table by LEFT JOIN on date. The trap is that on any given day you might have leads but no MQLs, so after stitching you must `COALESCE(..., 0)` to fill missing days with 0; otherwise NULLs look like missing data. Here `leads_per_day` is the master that the other three LEFT JOIN onto, because the day series of new leads is the most complete. One row = one day, with four columns for that day's stage additions, sorted by date descending so the most recent days are visible first.

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

**Expected Result:** ~30 rows (one per day for the past month). New leads typically 10–30/day; new MQLs ~5–10/day; new SQLs ~0–3/day; new opps ~1–4/day. A spike or trough on any given day suggests something abnormal upstream.

---

## D7: SDR 30-Day Productivity Board

**Dashboard:** SDR Productivity

**Business Context:** The SDR Manager monitors each SDR's output over the past 30 days. Key metrics per SDR: emails sent, reply rate, MQLs handled, and **SLA compliance** = the share of assigned MQLs that received the SDR's first email within 24 hours of becoming an MQL. If reply rate drops or SLA slips, immediate intervention is needed.

**Category:** Aggregation + Join
**Difficulty:** Intermediate
**Business Role:** SDR Manager

**Approach:** Each SDR has two classes of metrics with different sources, so we split them into two CTEs. `sdr_emails` aggregates the last 30 days of sends, opens, and replies from `sales_email` by sender. `sdr_mqls` is more involved — it computes SLA compliance, i.e. "of the MQLs assigned to this SDR, how many received this SDR's first email within 24 hours of becoming an MQL." That requires a nested subquery to find each (lead, sender) pair's earliest email timestamp `MIN(sent_at)`, then LEFT JOIN back to lead, using `JULIANDAY` to check whether the date diff is ≤ 1 day. LEFT JOIN is essential: even if some MQL never received an email, we must keep it in the denominator, or the compliance rate will be artificially inflated. The outer query starts from `sales_rep` and left-joins both CTEs so SDRs with zero output still appear on the board (filled with COALESCE 0). One row = one active SDR. Note JULIANDAY is more reliable for date subtraction than string comparison.

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
    -- SLA: assigned SDR sent the lead a first sales_email within 24 hours
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

**Expected Result:** 12 rows (one per active SDR). Top SDRs may send 1,000–2,000 emails in 30 days with reply rates of 2–4%. In this dataset, `sla_compliance_pct` lands in the 30–55% range across the SDR team (the generator does not specifically inject 24-hour MQL touch signals), so when comparing relatively, treat **>50% as the top quartile** and **<35% as a coaching red flag**. A real SaaS company with SLA-enforced workflow tooling would target >80%. The bottom performers may also show <500 emails or <1% reply rate — each of those is its own independent red flag.

---

## D8: AE Open Pipeline Board

**Dashboard:** AE Pipeline

**Business Context:** The VP Sales tracks each AE's open pipeline: the number of opps owned, total open ARR, distribution by stage, and how many are "stale" (no transition in 30+ days). Stale opps tend to be lost in the end.

**Category:** Aggregation + Join
**Difficulty:** Intermediate
**Business Role:** VP Sales

**Approach:** Each AE has two groups of numbers — an open-pipeline summary and a stale-opp count. They are at different grains, and forcing them into a single join will scramble the row counts, so split them into `ae_pipeline` (per owner: open opp count, open ARR, late-stage count) and `ae_stale`. Detecting stale opps requires the latest transition timestamp per opp, so `ae_stale` first uses a nested subquery `MAX(transitioned_at) GROUP BY opportunity_id` to find each opp's most recent transition, then filters to opps with no movement for more than 30 days, and counts `COUNT(DISTINCT opp.id)` per owner (DISTINCT prevents join fan-out from double-counting). The outer query starts from `sales_rep` and LEFT JOINs both CTEs so AEs with no open pipeline still appear (filled with 0), then computes the stale percentage. One row = one active AE. Date lower-bounds use a literal as usual.

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

**Expected Result:** ~24 rows (one per active AE). AE_Enterprise reps dominate ARR (large deals); AE_SMB has more opps but smaller amounts. A stale_pct >25% is a strong intervention signal.

---

## D9: Active Campaign Plan vs Actual Tracker

**Dashboard:** Active Campaign Tracker

**Business Context:** The Demand Gen Manager tracks ACTIVE-status campaigns to ensure they are pacing to plan (`target_mql_count`, `target_pipeline_usd`). If a campaign is 50% through its run-time but has only delivered 20% of its MQL target, it is underperforming.

> Influenced Pipeline Note: This query uses **first-touch attribution** (`lead.source_campaign_id`), which is the right lens for *plan vs actual* progress — only leads the campaign genuinely sourced count toward its own targets. For account-level cross-campaign influence (anyone inside the account touched by the campaign at any time), see B8 / B10 / B12 and the "Influenced Pipeline" entry in ER §11.2 KPI Dictionary. The two definitions are not interchangeable and produce different numbers.

**Category:** Multi-Join + Aggregation
**Difficulty:** Intermediate
**Business Role:** Demand Gen Manager

**Approach:** This query places "plan" (target fields) and "actual" (three definitions) side by side for ACTIVE campaigns. Plan values come straight from the `campaign` table. Actual has three pieces at three different grains, so we split them into three CTEs: `camp_actuals` computes member counts and percent of time elapsed (using `JULIANDAY` to compare the current date against start and end); `camp_mqls` counts actual MQLs; `camp_pipeline` computes influenced pipeline. The classic trap in the MQL piece is that members can join via either the lead path or the contact path (XOR FK), and we have to cover both. So we use `COUNT(DISTINCT COALESCE('L'||l.id, 'C'||ct.lead_id))` to prefix the two id spaces and avoid collisions between lead.id and the lead_id of a contact. For the influenced pipeline piece, we use account_id to converge both member paths, then join to opps created at that account *after* the member engagement. Because campaign-to-campaign_member is one-to-many, each definition must be cleanly aggregated in its own CTE and then LEFT JOINed back to `camp_actuals`. Mixing all three in a single join would fan out and double-count. One row = one ACTIVE campaign.

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
    -- % of time elapsed
    100.0 * (JULIANDAY('2026-06-01') - JULIANDAY(c.start_date))
          / NULLIF(JULIANDAY(c.end_date) - JULIANDAY(c.start_date), 0) AS pct_time_elapsed
  FROM campaign c
  LEFT JOIN campaign_member cm ON cm.campaign_id = c.id
  WHERE c.status = 'ACTIVE'
  GROUP BY c.id
),
camp_mqls AS (
  -- Counts MQLs reached by this campaign via either the lead path or the contact path.
  -- (The old version only counted lead.source_campaign_id and missed ~25% of
  -- campaign_members joined via contact_id.)
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
  -- Pipeline reached via account: both lead and contact paths converge to account_id.
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

**Expected Result:** ~20–25 rows (ACTIVE campaigns). The interesting comparison is `pct_of_mql_target` vs `pct_time_elapsed` — for a campaign pacing to plan, the two should be roughly equal; a campaign whose MQL progress lags by more than 30 percentage points is underperforming.

---

## D10: This Week's Hot Content

**Dashboard:** Content Heatmap

**Business Context:** The Content Marketing Manager wants to see which assets received the most engagement this week — download counts, average dwell time, and which persona consumed each asset. This drives next week's content amplification strategy.

**Category:** Aggregation + Date Filter
**Difficulty:** Basic
**Business Role:** Content Marketing

**Approach:** This is a straightforward join + aggregation that only touches `content_asset` and `content_engagement`. INNER JOIN is correct because an asset with no engagement this week should not appear on the hot list — we do not need LEFT JOIN to preserve zero-engagement assets. The date filter lives in the WHERE clause using `DATE('2026-06-01', '-7 days')` to bound to the last 7 days. One row = one asset, sorted by engagement count descending, top 20. There is a data-modeling gotcha to remember: `download` and `share` events have `time_on_page_seconds = 0`, so when computing average dwell time you must filter to `CASE WHEN engagement_type IN ('view','replay')` to keep the instant events out of the AVG, otherwise the average is dragged down by all those zeros. Downloads and views are counted separately with conditional sums.

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

**Expected Result:** Top 20 assets by 7-day engagement count. Typically dominated by ebooks/whitepapers on hot topics (API Observability, Kubernetes Monitoring). Average dwell time for view-type engagements is usually 200–600 seconds.

---

## D11: ABM Tier-1 7-Day Engagement Pulse

**Dashboard:** ABM Pulse

**Business Context:** Every Monday the ABM Lead checks: among Tier-1 target accounts, which had a touch in the last 7 days and which have gone 14+ days untouched. Long-untouched Tier-1 accounts are a crisis — outreach must be restarted.

**Category:** Multi-Join + Date
**Difficulty:** Intermediate
**Business Role:** ABM Lead

**Approach:** The hard part is that "touches" are scattered across three event tables (`campaign_member`, `content_engagement`, `sales_email`), and each can be attached to either a lead or a contact via the XOR FK, so an account's last-touch timestamp comes from up to six paths. We use `UNION ALL` to combine the six branches into a unified touch stream (each row = account id + touch timestamp), then take `MAX(touch_dt)` per account to get `acct_last_touch`. The `abm_accounts` CTE filters Tier-1 target accounts, then LEFT JOINs this last-touch CTE. LEFT is critical because "never touched" cold accounts are exactly what the ABM Lead most wants to see — an INNER join would drop them. `days_since_touch` is computed with JULIANDAY, and a CASE bucket sorts into HOT / WARM / COLD bands. The sort uses `days_since_touch IS NOT NULL, ... DESC` to push NULLs (never touched) to the top. One row = one Tier-1 account.

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
    -- Campaign-member touches (both XOR branches)
    SELECT c.account_id, cm.engaged_at AS touch_dt
    FROM contact c
    JOIN campaign_member cm ON cm.contact_id = c.id
    UNION ALL
    SELECT l.account_id, cm.engaged_at AS touch_dt
    FROM lead l
    JOIN campaign_member cm ON cm.lead_id = l.id
    UNION ALL
    -- Content engagement touches (both XOR branches)
    SELECT c.account_id, ce.engaged_at AS touch_dt
    FROM contact c
    JOIN content_engagement ce ON ce.contact_id = c.id
    UNION ALL
    SELECT l.account_id, ce.engaged_at AS touch_dt
    FROM lead l
    JOIN content_engagement ce ON ce.lead_id = l.id
    UNION ALL
    -- Sales-email touches (both XOR branches)
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
-- Portable DESC "NULLS FIRST" (works on SQLite < 3.30)
ORDER BY days_since_touch IS NOT NULL, days_since_touch DESC
LIMIT 50;
```

**Expected Result:** ~50 Tier-1 ABM accounts sorted by `days_since_touch` (worst first). The cold accounts at the top are urgent action items; HOT/WARM rows are healthy. Typical distribution: 60% HOT, 25% WARM, 15% COLD.

---

## D12: Stale Opportunity Alerts (30+ Days)

**Dashboard:** Stale Opp Alert

**Business Context:** The AE Manager / VP Sales runs this every week. Any open opportunity with no stage_transition for 30+ days is at risk. The owning AE must either advance it or close it. (SDRs typically hand off at SQL and no longer manage stage hygiene.)

**Category:** Date Difference
**Difficulty:** Basic
**Business Role:** VP Sales

**Approach:** We want to find "open opps that have had no stage transition in 30+ days." Starting from `opportunity`, join `opportunity_stage` (filter `is_closed = 0`), then join `account` and `sales_rep` to surface the company name and AE, and finally join `stage_transition` for the transition records. Because one opp has many transitions (one-to-many), we `GROUP BY o.id` and take `MAX(st.transitioned_at)` to get the most recent transition; otherwise one opp would produce many rows. The stale day count is `JULIANDAY('2026-06-01') - JULIANDAY(MAX(...))`, placed in the `HAVING` clause (not WHERE) because it depends on the aggregate. INNER JOIN on stage_transition is safe here because every opp has at least one initial transition record. One row = one stale open opp, sorted by stale days descending.

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

**Expected Result:** ~30–60 stale open opps. Those with the highest days_since_transition (90+) are the most urgent. Multiple stale opps under the same AE often indicate a load or motivation problem.

---

## D13: MQL Aging Buckets

**Dashboard:** MQL Aging

**Business Context:** Marketing Ops wants to see the unworked-MQL inventory bucketed by age. Fresh MQLs (0–7 days) are normal; old MQLs (30+ days) indicate a bottleneck at the SDR-conversion stage.

**Category:** Date Bucketing
**Difficulty:** Basic
**Business Role:** Marketing Ops

**Approach:** This query touches only `lead` and the logic is straightforward: take leads still in `mql` status (i.e., not yet promoted to SQL or disqualified), bucket them by "days since becoming an MQL," and count. The age is `JULIANDAY('2026-06-01') - JULIANDAY(mql_date)`, CAST to an integer and wrapped in a CASE that cuts it into five bands. The WHERE clause filters both `mql_date IS NOT NULL` and `status = 'mql'`; the second filter is critical because it makes sure we count only the "unworked" MQL inventory and exclude leads that have already moved forward. GROUP BY directly on the CASE-derived `age_bucket` works — no CTE or window function needed. The only subtlety is the sort: buckets are strings, and lexicographic order is wrong, so a final CASE maps each bucket to 1–5 so the result shows newest-to-oldest. One row = one age bucket.

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
  AND status = 'mql'  -- still in MQL status (not yet SQL or disqualified)
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

**Expected Result:** 5 buckets. A healthy distribution concentrates most MQLs in 0–14d. A heavy '60+d STALE' bucket indicates an SDR-capacity problem.

---

## D14: Manager Team Rollup (Won ARR via Self-Join FK)

**Dashboard:** Manager Rollup

**Business Context:** The VP Sales reviews each Manager's team-level performance: the sum of Won ARR across all their direct reports. This query practices the `sales_rep.manager_id` self-referencing FK.

**Category:** Self-Join
**Difficulty:** Intermediate
**Business Role:** VP Sales

**Approach:** This one practices the `sales_rep.manager_id` self-FK: every AE's manager_id points to another row in the same table. The goal is to roll Won ARR up from AEs to their manager. The biggest trap is trying to do it in one shot: if you join `opportunity` twice (once for won, once for open), you get a Cartesian product and amounts double. The correct approach is to first clean each AE's won/open ARR in an `ae_metrics` CTE (one row per AE, computed with a single join + CASE aggregation), then roll that result up by `manager_id` to the manager. The outer query starts from `sales_rep` with role = Manager, LEFT JOINs ae_metrics, so managers with no reports or reports with no results still appear (filled with 0). Note that `manager_id` links AEs to managers, while a manager's own `manager_id` is NULL. One row = one manager.

```sql
-- Aggregate per AE first to avoid the Cartesian fan-out of a double join
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

**Expected Result:** 4 rows (one per Manager). Each row shows team size, total Won ARR, and total open ARR for direct reports. NA-East and NA-West managers typically dominate.

> Note: Earlier versions joined `opportunity` twice (once for won, once for open) — that produces a row-inflating Cartesian product. The CTE above aggregates per AE first and then rolls up to manager, which is the correct pattern for "two aggregations on the same table."

---

## D15: Today's Weighted Forecast

**Dashboard:** Forecast

**Business Context:** RevOps publishes a daily forecast = Σ (open opportunity ARR × stage win probability). This is the most basic forecasting heuristic, used as a sanity check against more sophisticated models.

**Category:** Aggregation
**Difficulty:** Basic
**Business Role:** RevOps

**Approach:** The weighted forecast is "for every open opp, the amount × that stage's win probability," summed up. So the core is `opportunity` join `opportunity_stage` (filter `is_closed = 0`), GROUP BY stage `s.id`, multiplied by `typical_win_probability_pct / 100` for the weighted value. We want not just per-stage detail but also a grand-total row, so we `UNION ALL` the same aggregation a second time without grouping, hard-code a 'TOTAL' label, and give it `stage_order = 99` so it sorts last. This is the idiomatic way to add a total row in SQLite (no ROLLUP). One row = one stage (plus a total row). This query is simple enough that no CTE or window function is needed — two aggregations unioned is enough.

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

**Expected Result:** 5 stage rows + 1 total row. The Negotiation stage (80% probability) contributes disproportionately to the weighted forecast despite having the fewest opps. The total weighted forecast is typically 30–50% of total open ARR.

---

# Business-Question-Style Queries (B1–B35)

These queries answer diverse ad-hoc analysis questions. They are richer in technique and can uncover deeper relationships in the data.

---

## B1: Full Funnel — Lead → MQL → SQL → Opp → Won

**Business Context:** The VP Marketing wants a unified view of where leads die in the funnel. The drop-off rate at each stage helps identify bottlenecks.

**Category:** CTE + Aggregation
**Difficulty:** Intermediate
**Business Role:** VP Marketing

**Approach:** The first four levels of the full funnel (Total / MQL / SQL / Converted) can all be computed from the `lead` table alone using the reconciled date and status fields with conditional counts, so the `funnel` CTE gathers all four numbers in one pass. The last level (Won) requires joining back to `opportunity` to find the source leads of winning opps, so the `wins` CTE separately takes `COUNT(DISTINCT source_lead_id)`. The DISTINCT matters because one lead might be associated with multiple Won opps. We arrange the result as a vertical funnel using `UNION ALL` to stack rows; each row's conversion percentage is computed against the previous level (MQL→SQL divides by MQL count, not by total), so each segment's true drop-off is visible. The "five scalars stacked as five rows" shape is more intuitive than a pivot here. One row = one funnel level.

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

**Expected Result:** 5 rows showing the funnel. Lead→MQL ~35%, MQL→SQL ~20%, SQL→Converted ~75%, Converted→Won ~25%. The largest single drop-off is MQL→SQL — the SDR qualification bottleneck.

---

## B2: MQL Aging by Source

**Business Context:** Marketing Ops wants to know whether some lead sources produce MQLs that age into SQLs faster. A faster MQL→SQL conversion suggests higher source quality.

**Category:** Date Math + Aggregation
**Difficulty:** Intermediate
**Business Role:** Marketing Ops

**Approach:** This measures MQL quality per source by joining `lead` to `lead_source`, filtering to leads that have become MQLs (`mql_date IS NOT NULL`), and grouping by `source_code`. Two core metrics: the MQL→SQL rate is `COUNT(sql_date) / COUNT(id)` (counting a column auto-skips NULLs, so `COUNT(l.sql_date)` is exactly the number of MQLs that progressed to SQL — a clean trick); the aging speed is `AVG(JULIANDAY(sql_date) - JULIANDAY(mql_date))`, the average days from MQL to SQL. INNER JOIN lead_source is fine because source_id is non-null. `HAVING mql_count >= 5` filters out sources with too few samples to be statistically meaningful. One row = one lead source.

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

**Expected Result:** One row per source (with ≥ 5 MQLs). `INBOUND_DEMO_REQUEST` and `INBOUND_FREE_TRIAL` typically convert fastest (5–10 days, high rate); `CONTENT_SYNDICATION` is slowest with the lowest rate.

---

## B3: Lead Score Deciles and Win Rate

**Business Context:** Marketing Ops wants to validate the lead-scoring model. If the model works, leads in the top decile by score should have a substantially higher win rate than the bottom decile. This query uses NTILE to compute win rate by score decile.

**Category:** CTE + NTILE
**Difficulty:** Advanced
**Business Role:** Marketing Ops

**Approach:** The way to validate a scoring model is to cut leads into ten equal score buckets and see whether win rate increases monotonically across the deciles. First the `lead_with_won` CTE marks each lead with a Won flag by LEFT JOINing a deduplicated subquery of source leads of Won opps. LEFT is required — INNER would leave only winning leads and the win rate would be meaningless. Filter `lead_score > 0` to exclude never-scored leads. Then the `deciles` CTE uses the window function `NTILE(10) OVER (ORDER BY lead_score)` to split leads into 10 equal buckets — exactly what NTILE is built for, and much harder to do by hand while keeping bucket sizes equal. The outer query aggregates by decile to compute win rate, with the min/max score range for each bucket. One row = one decile, sorted descending so the top bucket appears first.

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

**Expected Result:** 10 rows (deciles 1–10). Decile 10 (highest score) should show the highest win rate (~5–10%), and decile 1 the lowest (~0–1%). A monotonically increasing trend validates the scoring model.

---

## B4: Disqualification Reason × Source Matrix

**Business Context:** Marketing Ops uses this to identify which lead sources bring in the wrong type of lead. If `CONTENT_SYNDICATION` shows a high share of "Not ICP," that is a targeting problem.

**Category:** Pivot + Aggregation
**Difficulty:** Intermediate
**Business Role:** Marketing Ops

**Approach:** This is a row-to-column pivot designed to show "which source contributes which disqualification reason." We only touch `lead` joined to `lead_source`, filter `status = 'disqualified'`, and group by source_code. SQLite has no native PIVOT, so we use a set of `SUM(CASE WHEN disqualified_reason = '...' THEN 1 ELSE 0 END)` to lay each reason out as a column — the standard SQLite pivot pattern. One row = one source, columns are the per-reason counts plus a total. No LEFT JOIN is needed because we only care about disqualified leads, and source_id is non-null. Read the result horizontally (which reason dominates a source) and vertically (which sources dominate a reason).

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

**Expected Result:** ~10 rows. Used to spot issues — for example, if `PAID_SEARCH_GOOGLE` shows high `not_icp`, the SEM keyword strategy needs sharpening.

---

## B5: Persona × Seniority Conversion Matrix

**Business Context:** Marketing Ops wants to understand which buyer profiles actually convert. A persona × seniority grid showing Lead→Won rates reveals which ICP we fit best.

**Category:** Pivot + Aggregation
**Difficulty:** Intermediate
**Business Role:** Marketing Ops

**Approach:** We want to see which "persona × seniority" combination converts best. First, `lead_outcomes` tags every lead with its persona, seniority, and a Won flag — the Won flag again comes from LEFT JOINing a deduplicated source-lead subquery of winning opps (LEFT to keep non-winning leads in the denominator). Then we group by persona and seniority. This is fundamentally a 2D matrix, but the generator strongly binds each persona to one seniority (see Expected Result), so only the diagonal-ish cells survive the `HAVING COUNT(*) >= 20` sample-size threshold — the rest get filtered out for being too thin. One row = one persona-seniority pair with enough samples, sorted by win rate descending.

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

**Expected Result:** ~6–9 cells. The full 5×5 matrix has 25 logical combinations, but generator rule §4.7 strongly binds each persona to one seniority (Champion-Manager, Economic Buyer-Director, Decision Maker-VP, Influencer-IC, Blocker-Director), so off-diagonal cells fail to clear the `HAVING COUNT(*) >= 20` filter. The visible rows are essentially the diagonal: Champion-Manager, EB-Director, DM-VP, Influencer-IC, Blocker-Director. The Blocker row should show near-zero win rate (they do not drive deals; they block them). To see the full matrix, lower the HAVING threshold to 5.

---

## B6: Multi-Visit Lead Behavior Lift

**Business Context:** Hypothesis: leads with multiple scoring events within 7 days convert at a higher rate than single-event leads. This query validates the "engagement intensity" signal.

**Category:** Window + Filter
**Difficulty:** Advanced
**Business Role:** Analyst

**Approach:** The hypothesis is that leads with multiple high-intent scoring events within 7 days convert better. First, `multi_visit` picks leads from `lead_scoring_event` who triggered strong-intent events like `multiple_visits_7d`, `page_visit_pricing`, or `pricing_calc_used` (deduplicated). Then `lead_outcomes` uses two LEFT JOINs: one tags whether a lead is in the multi-visit set, the other tags whether it won. Both must be LEFT JOIN because we want to split all leads into Multi-Visit vs Single-Visit groups — any INNER would drop leads that did not win or did not multi-visit, breaking the control. Finally we group by `visit_class` and compare win rates. Although tagged Window + Filter, this actually relies on the DISTINCT subset + LEFT JOIN flag pattern, simple and clear. One row = one visit class (two rows total).

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

**Expected Result:** 2 rows. Multi-visit leads should show a win rate 3–5x higher than single-visit leads, validating the "engagement intensity matters" hypothesis.

---

## B7: Lead Source Quality Decay by Quarter

**Business Context:** Hypothesis: source rankings drift over time. The #1 source in Q1 may be #4 in Q4. This query computes win rate per source per quarter.

**Category:** CTE + Date Bucketing
**Difficulty:** Advanced
**Business Role:** Analyst

**Approach:** This query examines whether each source's win rate drifts by quarter. `lead_q` buckets every lead by its `created_at` quarter and joins `lead_source` for the source_code. `wins` gathers the distinct winning source leads. The two are LEFT JOINed by lead id (preserving non-winning leads in the denominator), then grouped by both "quarter × source" dimensions. The grouping is 2D, so one row = "one source in one quarter," different from B2 (only by source) which has only a one-dimensional grouping. `HAVING lead_count >= 20` filters out thin cells that could otherwise show artificially high 100% win rates from a few accidental wins. Quarter bucketing uses STRFTIME as usual. Read it by fixing a source and tracking its win rate across quarters to see whether it is stable.

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

**Expected Result:** ~40–60 rows (6 quarters × ~10 sources, minus low-count cells). Sources with stable high win rates across quarters are sustainable; ones with volatile swings are unreliable channels.

---

## B8: Top Campaigns by Influenced Pipeline

**Business Context:** The Demand Gen Manager wants to celebrate (and double down on) the campaigns that influenced the most Won pipeline. Influenced pipeline = sum of Won opp ARR for any account that had at least one campaign_member record on this campaign.

**Category:** Multi-Join + Aggregation
**Difficulty:** Intermediate
**Business Role:** Demand Gen Manager

**Approach:** Influenced pipeline is account-level: any account with a campaign_member record on a campaign that later closes counts as influenced by that campaign. The chain is campaign → campaign_member → (lead or contact's) account → that account's Won opps. The big trap: when the same account has multiple members on the same campaign that all join to the same opp, the join fans out and SUMming amounts double-counts. So `camp_opp` first does `SELECT DISTINCT campaign_id, opp_id, amount` to dedupe (campaign × opp) pairs, then the outer query SUMs amount. Do *not* take the shortcut of writing `SUM(DISTINCT amount)` because two opps with coincidentally identical amounts would be wrongly collapsed. `o.created_at >= cm.engaged_at` enforces the causal ordering of "influence" (the touch must precede the opp). One row = one campaign, sorted by influenced Won ARR descending, top 20.

```sql
-- Dedupe (campaign × opp) in a CTE first, then SUM.
-- Avoid SUM(DISTINCT amount) because it silently drops opps with the same amount.
WITH camp_opp AS (
  SELECT DISTINCT c.id AS campaign_id, o.id AS opp_id, o.amount_usd
  FROM campaign c
  JOIN campaign_member cm ON cm.campaign_id = c.id
  LEFT JOIN lead l    ON l.id = cm.lead_id
  LEFT JOIN contact ct ON ct.id = cm.contact_id
  JOIN account a ON a.id = COALESCE(l.account_id, ct.account_id)
  JOIN opportunity o ON o.account_id = a.id
                     AND o.created_at >= cm.engaged_at        -- influence requires touch before opp
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

**Expected Result:** Top 20 campaigns by Won ARR. ABM_Sequence and Conference_Event campaigns typically lead because they target high-value accounts. Webinar campaigns also appear often due to strong mid-funnel influence.

---

## B9: End-to-End Webinar Funnel

**Business Context:** Content Marketing wants to measure the full lifecycle of a single webinar: registration → attendance → MQL → SQL → opp → Won. Drop-offs at each step help tune webinar quality and the follow-up sequence.

**Category:** CTE + Multi-Join
**Difficulty:** Advanced
**Business Role:** Content Marketing

**Approach:** The complete webinar lifecycle (registered → attended → MQL → opp → Won) spans many tables at different grains, so we split into four CTEs each computing its own piece, then LEFT JOIN them back onto a `webinars` master (LEFT preserves webinars where some stage is zero). `members` counts registered/attended/no-show from `campaign_member` by member_role. `mqls` counts MQL-equivalent participants — and again we hit the XOR path: the member may be a lead (check mql_date directly) or a contact (look back at the lead it links to via an EXISTS subquery), so `COUNT(DISTINCT COALESCE('L'||l.id, 'C'||ct.id))` prefixes both id spaces. `opps` converges members into opps via account_id, counting opps and Won ARR. The training point here is "an end-to-end funnel: aggregate each level separately, then join back to the primary key." Never try to compute all levels in a single big join — fan-out will get every number wrong. One row = one webinar campaign.

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
  -- Counts MQL-equivalent attendees via the lead path or contact path (contact's lead has mql_date)
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
  -- Reach opportunity via account_id (both lead and contact paths converge to account).
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

**Expected Result:** One row per webinar (~15 rows). Typical webinar funnel: 100 registered → 60% attended → 20% MQL → 5% opp → 1–2% Won. Top webinars convert better at every step.

---

## B10: Campaign Type ROI Comparison

**Business Context:** The Demand Gen Manager wants a head-to-head matchup: Webinar vs Paid Search vs ABM Sequence vs Conference — which type is the most efficient at turning each dollar of spend into Won ARR?

**Category:** Aggregation + Join
**Difficulty:** Intermediate
**Business Role:** Demand Gen Manager

**Approach:** This is B8's "aggregate-by-type" version: both influenced pipeline and spend roll up to the `campaign_type` dimension, and we compare ROI across types. Same dedupe trap as B8: `type_opp` first uses `SELECT DISTINCT campaign_type, opp_id, amount` to dedupe (type × opp) so the same account with multiple touches does not double-count amounts. Spend is at a different grain, so a separate `type_spend` CTE sums `spend_to_date_usd` by type and counts campaigns. The two CTEs are joined by campaign_type with LEFT JOIN (starting from type_spend so types with spend but no Won still appear; ROI becomes 0 because the numerator is 0). We only look at `status = 'COMPLETED'` campaigns because only fully-run campaigns produce a fair ROI. One row = one campaign type, sorted by ROI descending.

```sql
-- Step 1: dedupe (campaign_type × opp) first to prevent row inflation from multi-touch accounts.
-- Step 2: aggregate spend separately, then join in the SELECT.
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

**Expected Result:** 8 rows (one per campaign type). ABM_Sequence and Webinar usually lead with ROI 5–10x; Paid_Social and Content_Syndication often show weaker ROI of 1–2x.

---

## B11: First-Touch Winning Campaign Analysis

**Business Context:** The Demand Gen Manager asks: among Won deals, what was the lead's first-touch campaign? This is the "first-touch attribution" lens — crediting the campaign that *brought the buyer into* Stratosend.

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

**Expected Result:** Top 20 first-touch winning campaigns. Provides a useful contrast with B8 (influenced pipeline). First-touch winners tend to be high-intent inbound campaigns (demo request, free trial) and effective ABM sequences.

---

## B12: Content Asset Influence on Won Pipeline

**Business Context:** Content Marketing wants to know which content is most often consumed by buyers who eventually close. If certain whitepapers correlate strongly with wins, they deserve more promotion.

**Category:** Multi-Join + Aggregation
**Difficulty:** Advanced
**Business Role:** Content Marketing

```sql
-- Dedupe (asset × opp) first to avoid the SUM(DISTINCT amount) anti-pattern.
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

**Expected Result:** Top 20 winning content assets. Typically dominated by mid-funnel content: case studies, analyst reports, deep ebooks. Less common: blog posts (top of funnel, less influence).

---

## B13: Content Topic × Persona Affinity

**Business Context:** Content Marketing wants to confirm which topics resonate with which personas. If "Kubernetes Monitoring" engagements are 80% Champions and "Cost Optimization" engagements are 80% CFOs, content distribution can be targeted by persona.

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

**Expected Result:** ~13 rows (one per topic_tag). "API Observability" and "Distributed Tracing" tend to attract Champions/Influencers; "SLO/SLI Practices" attracts Economic Buyers.

---

## B14: Gated vs Ungated Content Conversion Lift

**Business Context:** Marketing Ops debates whether gating content (requiring a form fill) is worth the friction it creates. This query measures: among engagers, are gated-content engagers more likely to become MQLs than ungated-content engagers?

**Category:** CTE + Aggregation
**Difficulty:** Intermediate
**Business Role:** Marketing Ops

```sql
WITH gated_engagers AS (
  -- Separate the two id namespaces with a string prefix (matches ER §5 guidance).
  -- Avoid the `id + N` offset trick — it collides as soon as the smaller id space exceeds N.
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

**Expected Result:** 2 rows. Expected: gated-content engagers have a higher MQL rate (the form-fill action itself produces a lead and indicates intent). Trade-off: gating reduces total engagement volume.

---

## B15: Email_Blast Re-engagement of Dormant Leads

**Business Context:** Demand Gen wants to see whether email reactivation campaigns work for leads that have been dormant 90+ days. Does sending an Email_Blast cause dormant leads to re-engage (a scoring event appearing again after silence)?

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

**Expected Result:** A single-row summary showing the total dormant-then-blast leads, how many had no events in the prior 90 days, and how many produced an event within 14 days after the blast. A 10–25% reactivation rate is healthy.

---

## B16: Sales Cycle by Tier (Median + p90)

**Business Context:** The VP Sales wants to see the sales-cycle distribution by tier. The median tells you the typical case; p90 reveals the worst case (Enterprise outliers can exceed 12 months).

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

**Expected Result:** 3 rows (SMB, Mid, Enterprise). SMB median ~60–90 days, Mid ~120–160, Enterprise ~200–300. The Enterprise max will show big outliers (year-long deals).

---

## B17: Stage-to-Stage Conversion + Median Stage Days

**Business Context:** The VP Sales wants to find pipeline bottlenecks. Which stage has the worst pass-through rate? Which takes the longest? Combined view = "which stage is dragging us down?"

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

**Expected Result:** 4 rows (Disc→Demo, Demo→Eval, Eval→Proposal, Proposal→Negot). The lowest conversion is often at Eval→Proposal (technical evaluations fail). Average days is highest at Evaluation/POC.

---

## B18: Won/Lost Reason Matrix by Competitor and Industry

**Business Context:** RevOps wants to find patterns. Do we lose to Datadog more in Fintech? To Honeycomb more in Mid-Market? A matrix reveals systemic competitive weaknesses.

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

**Expected Result:** ~12 rows (one per industry). Fintech / SaaS / Healthcare Tech typically lead in loss volume. Datadog is the most frequent competitor across industries.

---

## B19: Stage Regression Detection (Opps Moving Backward)

**Business Context:** RevOps wants to flag opportunities whose stage moved *backward* in their lifecycle — for example, from Demo back to Discovery. This is a major risk signal: despite stage labels changing, the deal has not actually moved forward.

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
WHERE sf.stage_order > st.stage_order  -- backward transition
  AND st.is_closed = 0  -- still open after the regression
ORDER BY t1.transitioned_at DESC;
```

**Expected Result:** This depends on data generation: under the current logic, regressions are rare (they only happen if explicitly generated). Many production datasets show 5–10% of opps regress at least once. Treat this query as a template — swap in your own regression-generation logic when needed.

---

## B20: Forecast Variance — Forecast vs Actual

**Business Context:** RevOps audits team forecast accuracy. For Closed-Won deals, compare the `expected_close_date` *at creation* (first transition) against the `actual_close_date` — how often does the forecast slip, and by how much?

**Category:** Date Math + Aggregation
**Difficulty:** Advanced
**Business Role:** RevOps

```sql
WITH initial_expected_close AS (
  -- The expected_close_date at the first transition (i.e. opportunity creation)
  SELECT
    t.opportunity_id,
    t.expected_close_date_at_transition AS initial_expected_close
  FROM stage_transition t
  WHERE t.from_stage_id IS NULL  -- creation transition
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

**Expected Result:** A single row. Typically 30–50% of Wons close on time or early, 30% slip within 30 days, 20–30% slip by more than a month. Average slip is usually positive (deals slip more than they accelerate).

---

## B21: Slipped Opportunities — Close Date Pushed 2+ Times

**Business Context:** RevOps wants to flag deals whose `expected_close_date` was moved multiple times during their progression. These are extreme high-risk for being lost or stalling.

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
  HAVING COUNT(DISTINCT expected_close_date_at_transition) >= 3  -- 3+ distinct values means 2+ slips
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
WHERE s.is_closed = 0  -- still open
ORDER BY times_slipped DESC, total_slip_days DESC
LIMIT 50;
```

**Expected Result:** Open opps whose close date has slipped 2+ times. Enterprise deals tend to dominate (long sales cycles, more chances to slip).

---

## B22: Open Pipeline Concentration Risk

**Business Context:** The VP Sales wants to assess pipeline concentration risk. Is open ARR spread across many AEs, or concentrated in 2–3 megadeals owned by 1 AE? Concentration = the risk if those few deals slip.

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
WHERE rank_in_pipe <= 20  -- top 20 opps
ORDER BY rank_in_pipe;
```

**Expected Result:** Top 20 opps by amount. `cum_pct_of_pipe` shows how much of the open pipeline they concentrate. If the top 5 = 50% of pipeline, that is high risk.

---

## B23: SDR SLA Compliance — MQL → First Email Within 24 Hours

**Business Context:** The SDR team has an SLA: every MQL must receive a first SDR email within 24 hours of becoming an MQL. A compliance rate below 80% triggers SDR Manager intervention.

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

**Expected Result:** ~12 rows (one per SDR with ≥ 5 MQLs). Compliance below 70% is a major problem; above 90% is excellent. Sorted ascending so the bottom performers appear first.

---

## B24: AE Quota Attainment Ranking

**Business Context:** The VP Sales reviews each quarter: who is hitting quota and who is not? Quota attainment = YTD Won ARR / quota. The leaderboard drives bonuses and PIPs.

**Category:** Aggregation + Join
**Difficulty:** Basic
**Business Role:** VP Sales

```sql
-- Use CASE inside SUM rather than is_won as a JOIN condition, otherwise
-- the LEFT JOIN keeps non-won opps (with NULL stage), and SUM also counts them.
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

**Expected Result:** ~24 AEs ranked by attainment %. Some will be > 100% (President's Club level); others < 50% (PIP risk). Enterprise AEs swing the most because a single deal can take them from 0% to 200%.

---

## B25: SDR Sequence-Step Funnel Decay

**Business Context:** The SDR Manager wants to see at which step in the sequence the reply rate collapses. Step-1 reply rate is the baseline; steps 4–7 should decay gracefully rather than fall off a cliff.

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
WHERE bounced = 0  -- exclude bounces
GROUP BY sequence_step
ORDER BY sequence_step;
```

**Expected Result:** 7 rows (steps 1–7). Open rate should decay smoothly from ~35% to ~15%. Reply rate similarly. A cliff drop at any step suggests the sequence content for that step is broken.

---

## B26: Reply Sentiment Distribution by Sales Rep

**Business Context:** Beyond reply *rate*, the SDR Manager cares about reply *quality*. A rep with a 5% reply rate but all `not_interested` is worse than one with a 2% reply rate but 50% `positive`. This query shows each rep's sentiment distribution.

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

**Expected Result:** ~30 reps. Top performers have 25%+ of replies labeled positive; bottom performers have positive < 10% (mostly not_interested). Surfaces reps whose reply rate is OK but whose messaging needs sharpening.

---

## B27: Manager Team Rollup (Won ARR via Self-Join FK)

**Business Context:** The VP Sales rolls up Won ARR by manager via the `sales_rep.manager_id` self-join FK, broken down further by role within the team.

**Category:** Self-Join + Aggregation
**Difficulty:** Intermediate
**Business Role:** VP Sales

```sql
-- Same pattern as B24: put is_won inside a CASE in SUM, not as a JOIN condition.
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

**Expected Result:** ~16 rows (4 managers × 4 report roles). Shows team composition and revenue contribution by role. The AE_Enterprise row under each manager typically dominates revenue.

---

## B28: Rep Ramp Analysis (Hire → First Won Deal)

**Business Context:** The VP Sales wants to know: how long does it take a new AE after hire to close their first deal? Industry benchmark is 90 days for SMB and 180 days for Enterprise. Reps significantly above the benchmark may need coaching.

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

**Expected Result:** ~20 rows (active AEs with at least one Won). Fast starters (SMB) often < 60 days; Enterprise ramp may be 120–300 days. AEs with NULL first_won_date (no win yet) are excluded — flag them separately.

---

## B29: First-Touch vs Last-Touch vs W-Shaped Attribution

**Business Context:** RevOps wants to compare three attribution models on the same set of Won opportunities. Different models assign credit to different channels — leadership needs the comparison to choose the "official" model.

**Category:** CTE + Window
**Difficulty:** Advanced
**Business Role:** RevOps

```sql
-- All three attribution CTEs key on campaign_code, so the comparison is apples-to-apples.
-- (Previously first_touch keyed on lead_source.source_code while last_touch and
-- w_shaped keyed on campaign.campaign_code — the dimensions did not match,
-- and the output columns were essentially independent.)
WITH won_opps AS (
  SELECT o.id, o.amount_usd, o.source_lead_id, o.account_id, o.actual_close_date
  FROM opportunity o
  JOIN opportunity_stage s ON s.id = o.current_stage_id
  WHERE s.is_won = 1
),
-- First touch: the campaign tagged on the source lead (NULL for direct outbound)
first_touch AS (
  SELECT
    c.campaign_code,
    SUM(wo.amount_usd) AS first_touch_arr_usd
  FROM won_opps wo
  JOIN lead l ON l.id = wo.source_lead_id
  JOIN campaign c ON c.id = l.source_campaign_id
  GROUP BY c.campaign_code
),
-- Last touch: the campaign of the last campaign_member on the account before close
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
-- W-shaped: weighted credit per campaign. attribution_credit_pct already encodes
-- the W-shaped (30 / 30 / 30 / 10) split per Won-opp path.
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
-- Portable equivalent of a three-way FULL OUTER JOIN: build the universe of campaign_codes,
-- then LEFT JOIN every attribution view.
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

**Expected Result:** A multi-row table comparing the 3 attribution models per source. Often there are large differences: first-touch over-credits high-lead-volume sources; last-touch over-credits demo-request-style sources; W-shaped is more balanced.

---

## B30: Source × Tier Win-Rate Pivot Matrix

**Business Context:** Demand Gen wants win rate as a matrix: for each lead source × each account tier, what is the opp win rate? Identify *best combinations* (for example, Partner Referral × Enterprise might reach 60%).

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

**Expected Result:** 10 rows (one per source). Useful for finding hidden gems — small-volume sources with high Enterprise win rates are candidates for additional investment.

---

## B31: CAC Payback by Channel

**Business Context:** The CFO wants the most rigorous version of D3 — per-channel CAC, payback, and comparison against the SaaS Magic Number heuristic.

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

**Expected Result:** ~7–9 rows (channels with at least 1 win). Payback < 12 months is excellent; > 24 months is concerning. Free channels (PARTNER_REFERRAL, OUTBOUND_SDR) have low CAC because there is no lead cost.

---

## B32: Influenced Pipeline Hidden in W-Shaped Attribution

**Business Context:** RevOps suspects that some campaigns receive zero credit under first-touch attribution but significant credit under W-shaped attribution — these are "hidden influencers" that are more valuable than the raw funnel shows.

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

**Expected Result:** Top 20 "hidden influencer" campaigns — they get W-shaped credit but no first-touch closed deals. They are the assists in basketball; they do not source but they help close.

---

## B33: ABM Multi-Stakeholder Coverage Depth

**Business Context:** The ABM Lead measures how many distinct buyer personas have been touched inside each target account. Best practice: Tier-1 accounts should have ≥3 personas engaged.

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

**Expected Result:** 3 rows (Tier 1, 2, 3). Tier-1 accounts should show the deepest coverage (highest avg_distinct_personas and pct_with_3plus_personas). If Tier-1 is below 50% on 3+ personas, the ABM strategy needs sharpening.

---

## B34: ABM vs Non-ABM Win Rate Comparison

**Business Context:** The VP Sales / ABM Lead wants empirical proof that ABM works. ABM target accounts should show both a higher win rate and a higher average deal size than non-target accounts.

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

**Expected Result:** 2 rows. ABM Target accounts should have higher win rates and larger average deal size (because ABM focuses on Mid/Enterprise). The total ARR comparison shows whether ABM is moving the business in absolute terms.

---

## B35: Account Expansion — Customers with Multiple Wins

**Business Context:** RevOps wants to find existing customers who have already won multiple opportunities — these are expansion / upsell candidates. Going further: identify those whose most recent Win is recent (renewal window).

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

**Expected Result:** Multi-win accounts. Given the 18-month time window of the dataset, this subset is small — but enough to demonstrate. A 6-to-12-month window since the last win flags expansion timing.

---

## Query Category Summary

| Category | Count | Query IDs |
|----------|-------|-----------|
| Aggregation | 12 | D2, D6, D10, D13, D15, B1, B2, B4, B10, B24, B25, B34 |
| Join Operations | 10 | D7, D8, D9, D11, D14, B5, B8, B11, B12, B13 |
| Window Functions | 5 | D5, B6, B19, B22, B29 |
| Date/Time Analysis | 9 | D6, D12, D13, B2, B7, B15, B16, B20, B28 |
| Subqueries / CTEs | 14 | D1, D3, D4, B1, B3, B7, B9, B14, B15, B17, B21, B23, B29, B31 |
| Self-Join | 4 | D14, B17, B19, B27 |
| Pivot | 6 | B4, B5, B13, B18, B26, B30 |
| HAVING / Filter | 6 | B5, B11, B22, B23, B33, B35 |

> Categories overlap — a single query can appear in multiple buckets (e.g. B5 is both Pivot and HAVING/Filter), so the column counts do not need to add to 50.

## Business Role Coverage

| Role | Count | Query IDs |
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

## Difficulty Distribution

| Level | Count | Query IDs |
|-------|-------|-----------|
| Basic | 8 | D6, D10, D12, D13, D15, B24, B25, B34 |
| Intermediate | 24 | D1, D2, D7, D8, D9, D11, D14, B1, B2, B4, B5, B8, B10, B11, B13, B14, B16, B18, B26, B27, B28, B30, B33, B35 |
| Advanced | 18 | D3, D4, D5, B3, B6, B7, B9, B12, B15, B17, B19, B20, B21, B22, B23, B29, B31, B32 |

---

## Notes

- All queries are designed for SQLite 3.x. Where SQLite lacks a feature (e.g. native percentile), idiomatic workarounds are used.
- Some queries assume the reconciled invariants of the dataset — for example, that `lead.lead_score` equals the sum of its scoring events. The generator guarantees this.
- For production deployment, queries should be wrapped in materialized views (the ADS layer described in the ER document) rather than re-executed every dashboard refresh.
- "Today" in the queries is uniformly hard-coded as `'2026-06-01'` to match the generator's `TODAY` constant. In a live system, replace this with `DATE('now')`.

---

End of SQL queries document.
