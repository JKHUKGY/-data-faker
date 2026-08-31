# VerdantBox Ecommerce Subscription Growth Marketing — SQL Query Reference

> For business context, industry background, and glossary, see `01-ecommerce_subscription_growth_marketing_high_business_context.md`. For table structure and column meanings, see `02-ecommerce_subscription_growth_marketing_high_er_document.md`.

## Overview

This document provides **20 business-driven SQL queries** designed for the `ecommerce_subscription_growth_marketing_high` dataset. Each query maps to a real question that VerdantBox's growth-marketing, analytics, operations, finance, and executive teams routinely ask as they run the acquisition / membership conversion / reactivation campaign mix, and every query traces back to one of the business questions listed in Section 5 of the business-context document.

All queries are designed for **SQLite 3.25+** (window-function support is required). The "today" referenced in date arithmetic is hard-coded as `REFERENCE_DATE = 2026-06-01` (matching the generator's `TODAY` constant) instead of `DATE('now')`, to make results reproducible. In production, swap it for `date('now')`.

> WARNING: **The table name `order` is a SQL reserved word.** Every raw-SQL reference to it must be quoted: `"order"` (SQLite / PostgreSQL) or `` `order` `` (MySQL). SQLAlchemy quotes it automatically, but unquoted hand-written SQL will fail.

---

## How to Use This Document

This document is a teaching reference. The intended reader is an intern analyst who has just finished the business-context document and the ER document, and is about to be handed these queries by their manager. Read each one start-to-finish like a project handoff, not as a SQL cheatsheet.

Every query has the same five-part structure, modeling one full "question to conclusion" thought process:

1. **Business context:** who is asking, why now, and what decision the answer feeds into.
2. **Category / difficulty / business role:** the SQL technique bucket, the difficulty tier, and which role in the company would originate this question.
3. **Solution approach:** before looking at the SQL, work out which tables you'll touch, how the joins fit together, the grain of the aggregation, why you reach for a CTE or window function, and any SQLite-specific gotchas.
4. **SQL:** runnable query code against the generated SQLite database.
5. **Expected result and business takeaway:** what the result looks like, which embedded business trap the key numbers tie to, and the next action an analyst should take once they have those numbers.

After reading one of these end-to-end, you should be able to not only write the SQL but also explain to your manager "why this join has to be a LEFT JOIN" and "what this number means for what we should do next." That is the real point of this document.

---

## Query Index

| # | Title | Business Role | Category | Difficulty |
|---|-------|---------------|----------|------------|
| 1 | Campaign-mix P&L by Objective | Executive | CTE + Aggregation | Basic |
| 2 | Channel ROAS Leaderboard | Manager | CTE + Join + Aggregation | Intermediate |
| 3 | Full Marketing-Funnel Conversion | Analyst | CTE + Aggregation | Intermediate |
| 4 | Member vs Non-Member Order Economics | Finance | Aggregation | Basic |
| 5 | Monthly Acquisition Cohort Retention | Analyst | CTE + Date Math | Advanced |
| 6 | Top 20 Customers by LTV | Analyst | Join + Aggregation | Basic |
| 7 | Active-Campaign Live Dashboard | Operations | CTE + Join | Basic |
| 8 | Promo-Code Redemption Efficiency | Manager | Aggregation | Basic |
| 9 | Top Products by Member-Driven Revenue | Manager | Multi-Join | Intermediate |
| 10 | Win-Back List: Dormant High-Value Candidates | Manager | Subquery + Join | Intermediate |
| 11 | Day-of-Week × Channel Performance | Analyst | Date Function + Aggregation | Intermediate |
| 12 | Customer Acquisition Cost (CAC) per Campaign | Finance | CTE + Join | Advanced |
| 13 | Audience-Segment Overlap Matrix | Analyst | Self-Join + CTE | Advanced |
| 14 | Days to First Order by Acquisition Channel | Analyst | Date Difference | Intermediate |
| 15 | Trial-to-Paid Conversion by Signup Cohort | Analyst | CTE + Join | Advanced |
| 16 | Touchpoint Frequency-Cap Audit | Operations | Self-Join + CTE | Intermediate |
| 17 | Campaigns Flagged for Budget-Pacing Overrun | Operations | CTE + Filter | Basic |
| 18 | Creative-Asset CTR Leaderboard | Manager | Join + Aggregation | Intermediate |
| 19 | Geographic Revenue Heatmap | Executive | Aggregation | Basic |
| 20 | Segment AOV Ranking (with Member Penetration) | Analyst | CTE + Window Function | Intermediate |

---

## Query Details

### Query 1: Campaign-mix P&L by Objective

**Business context:**
At the monthly business review, the CMO needs a one-glance read on the marketing mix: how much each objective (Acquisition, Membership Conversion, Reactivation) spent, and how much attributed gross revenue each one returned. This number frames every downstream conversation about next quarter's budget reallocation.

**Category:** CTE + Aggregation
**Difficulty:** Basic
**Business role:** Executive

**Solution approach:**
We need to line up "spend" and "attributed revenue" at the campaign grain, then roll up by objective. Spend comes from `campaign_channel` (a campaign has many channels, so GROUP BY campaign_id first); attributed revenue comes from `"order".attributed_campaign_id` (sum by campaign first). Once each CTE is aggregated, use `campaign` as the driver and LEFT JOIN both CTEs on top of it, then GROUP BY `objective`. The LEFT JOINs cannot become INNERs here — otherwise any campaign with no spend or no attributed revenue would silently disappear, and the objective-level totals would be understated. ROAS uses `SUM(revenue) / NULLIF(SUM(spend), 0)` to guard against divide-by-zero.

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

**Expected result:**
Three rows (one per objective), each showing total budget, actual spend, attributed revenue, and ROAS. Typically, ACQUISITION ROAS is lower than REACTIVATION ROAS (it is harder to convert net-new customers than to win back lapsed ones), with MEMBERSHIP_CONVERSION sitting in between.

---

### Query 2: Channel ROAS Leaderboard

**Business context:**
The performance-marketing manager wants to know which paid channels return the most revenue per dollar spent. This drives the next budget rebalance: scale up the winners, pause the losers.

**Note:** `order.attributed_campaign_id` is **campaign-level** last-touch attribution, not channel-level. When one campaign runs across multiple channels (e.g., Meta + Google), the order's revenue has to be shared across each of that campaign's channels. We use the channel's share of the campaign's spend to weight the revenue split (spend-share weighting), which is the industry-standard approximation.

**Category:** CTE + Join + Aggregation
**Difficulty:** Intermediate
**Business role:** Manager

**Solution approach:**
The hard part is that attribution is campaign-level — we can't say directly "this revenue came from Meta or from Google." So we use two CTEs to compute per-campaign total spend and total attributed revenue, then in `channel_share` compute each channel's share `ch_spend / campaign_spend` within its campaign, and use that share to apportion campaign revenue to channels — that's spend-share weighting. Finally we JOIN `channel_type` to get channel names, and group by channel. The revenue branch uses LEFT JOIN because some campaigns still have spend but no attributed orders yet, and we don't want to drop them. `HAVING SUM(ch_spend) > 0` filters out zero-spend channels to avoid noisy ROAS values.

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

**Expected result:**
Channels sorted by ROAS. Owned channels (email, push) typically dominate the top, thanks to their near-zero variable cost. Among paid channels, TikTok and Meta lead on acquisition use cases, and Google Ads excels in high-intent search.

---

### Query 3: Full Marketing-Funnel Conversion

**Business context:**
The growth analyst is prepping the quarterly funnel review. She needs the standard email/push funnel: sent → delivered → engaged → clicked → converted, with the conversion rate between each step. Whichever step has the steepest drop is where the next round of optimization budget should land.

**Note:** In this schema, `response_type` is the **terminal state** of a touchpoint — `convert` implies the user already clicked, and `click` implies the user already opened. When computing "engagement tiers," we use "this state or higher."

**Category:** CTE + Aggregation
**Difficulty:** Intermediate
**Business role:** Analyst

**Solution approach:**
The numerator and denominator must live in the same population, otherwise the conversion rates are distorted. The `funnel` CTE computes sent and delivered against `marketing_touchpoint`; the `responses` CTE computes per-stage responses against `touchpoint_response`, but joins back to touchpoint and restricts to `delivery_status = 'delivered'` so we only count responses from successfully delivered touches. Because `response_type` is a terminal-state model, engaged uses `IN ('open','click','convert')` and clicked uses `IN ('click','convert')` to take the union (convert implies click, click implies open). The two CTEs have no shared dimension, so a CROSS JOIN is enough to fuse them into one row.

```sql
WITH funnel AS (
    SELECT
        COUNT(*) AS sent,
        SUM(CASE WHEN delivery_status = 'delivered' THEN 1 ELSE 0 END) AS delivered
    FROM marketing_touchpoint
),
responses AS (
    -- Restrict to responses tied to successfully delivered touchpoints,
    -- so numerator and denominator stay in the same population.
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

**Expected result:**
A single row exposing the full funnel and the step-by-step conversion rates. Use it as the baseline against which to set targets for the next campaign.

---

### Query 4: Member vs Non-Member Order Economics

**Business context:**
The finance team wants to quantify what a VerdantBox+ member is actually worth. By comparing member vs non-member AOV, an order-frequency proxy, and total revenue contribution, they can justify the membership-conversion campaign budget to the CFO.

**Category:** Aggregation
**Difficulty:** Basic
**Business role:** Finance

**Solution approach:**
One GROUP BY is enough — what matters is the group key and the filter. Group by `is_member_at_purchase` to split members vs non-members, and filter `order_status IN ('delivered','shipped')` to count only realized orders. AOV uses `AVG(total_usd)`; revenue-per-buyer uses `SUM(total_usd) / COUNT(DISTINCT customer_id)`. Note that AOV and "revenue per buyer" are two different lenses: the former averages by order, the latter by buyer. Members reorder more often, so the gap on the latter is wider than on the former. Single-table aggregation, no joins needed.

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

**Expected result:**
Two rows. Member AOV (~$225) is meaningfully higher than non-member (~$120), about 85% higher, driven by the combination of "member basket 3–6 items vs non-member 1–3 items × member discount pricing"; the revenue-per-buyer gap is even larger (because members repeat more often). These numbers directly validate spend on membership-conversion campaigns, and align with the "member AOV premium" trap in the ER document.

---

### Query 5: Monthly Acquisition Cohort Retention

**Business context:**
The retention analyst is building the standard cohort retention curve: of customers acquired in each month, what share comes back to place an order in **each subsequent** month. This is the single most important diagnostic for product-led-growth health.

**Important:** In cohort retention analysis, **month 0** (the signup month itself) is *activation*, not retention. This query restricts to `month_diff >= 1`, so the output only contains true retention (months after signup).

**Category:** CTE + Date Math
**Difficulty:** Advanced
**Business role:** Analyst

**Solution approach:**
The skeleton of cohort analysis is a "signup month × order month" grid. First we tag each customer with `strftime('%Y-%m', signup_date)` as a cohort label, then bucket their orders by month. `month_diff` is computed as "year diff × 12 + month diff" to get calendar-month distance (SQLite has no built-in month-diff function, so we substr it out by hand). The key trap: `month_diff = 0` is activation, not retention, so the outer `WHERE month_diff >= 1`. `active_customers` uses `COUNT(DISTINCT customer_id)` to prevent multi-order customers in one month from being counted twice. Finally we divide by cohort_size to get the retention rate.

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
        -- Calendar-month difference between signup_month and order_month
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

**Expected result:**
A rectangular cohort × month_diff grid (starting from month 1). Read it as a triangular matrix: each row is a signup cohort, and the columns to the right show that cohort's retention in subsequent calendar months. Look at which cohorts retain better — the campaigns behind them are the success patterns to copy. To see activation (month 0), remove the `month_diff >= 1` filter and label it separately.

---

### Query 6: Top 20 Customers by LTV

**Business context:**
The CRM analyst is building the VIP outreach list. Top spenders need white-glove service — early access to new launches, a dedicated support line, surprise-and-delight gifts. The list filters to customers with realized orders only (excludes cancellations).

**Category:** Join + Aggregation
**Difficulty:** Basic
**Business role:** Analyst

**Solution approach:**
Standard "customer joined to orders, then aggregate." `customer` INNER JOIN `"order"` (keep only customers with realized orders), filter `order_status IN ('delivered','shipped')`, GROUP BY customer, and `SUM(total_usd)` is realized LTV. Order by it descending and LIMIT 20. The GROUP BY needs to include every non-aggregated SELECT column. There's no fan-out risk here because orders are many-to-one with customer, and the aggregation grain is orders themselves.

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

**Expected result:**
Top 20 customers by LTV, with order count and AOV attached. Expect a highly skewed distribution — the top 20 customers likely capture a sizeable share of total revenue (a classic long-tail Pareto pattern).

---

### Query 7: Active-Campaign Live Dashboard

**Business context:**
The campaign-operations team scans every active campaign every morning: how much budget has burned, how many days are left, how many touchpoints have been sent. This is the standard view at daily standup.

**Category:** CTE + Join
**Difficulty:** Basic
**Business role:** Operations

**Solution approach:**
The dashboard puts "how much spent" and "how many touchpoints sent" side by side per campaign. Two CTEs: one aggregates spend on `campaign_channel`, the other joins `marketing_touchpoint` to `campaign_channel` and counts touchpoints. `campaign` is the driver and LEFT JOINs both CTEs, because active campaigns may not have any touchpoints yet. `days_remaining` uses `julianday(end_date) - julianday('2026-06-01')`, with REFERENCE_DATE as a literal rather than `DATE('now')`. `WHERE status = 'ACTIVE'` keeps only in-flight campaigns, and we sort by days remaining ascending to push the urgent ones to the top.

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

**Expected result:**
One row per active campaign, sorted by urgency (days remaining ascending). Use it to spot campaigns burning too fast or too slow relative to the time elapsed.

---

### Query 8: Promo-Code Redemption Efficiency

**Business context:**
The promotions manager evaluates which "campaign × promo" combinations actually work. Each promo has a `max_redemptions` cap: if `redemption_count` approaches the cap, the promo is doing its job; if it's near zero, either the threshold is too strict or the reach is insufficient.

**Category:** Aggregation
**Difficulty:** Basic
**Business role:** Manager

**Solution approach:**
Stitch together the promo definition (`promo_code`), its owning campaign (`campaign`), and actual redemptions (`promo_redemption`). `promo_code` JOIN `campaign` is many-to-one, then LEFT JOIN `promo_redemption` because some codes were never redeemed and we don't want to drop them. GROUP BY promo code, with redemption rate = `redemption_count / max_redemptions` and actual dollars given up = `SUM(discount_applied_usd)`. `redemption_count` is a pre-reconciled redundant column on the table, so we can use it directly without re-counting the detail rows.

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

**Expected result:**
Promo codes ranked by redemption rate. Crossed with the campaign's objective, this shows which discount type (percent off, fixed dollar off, free shipping) pairs best with which campaign type.

---

### Query 9: Top Products by Member-Driven Revenue

**Business context:**
The category manager wants to know which SKUs members love most. Member-driven revenue tells the product team which items to feature in the next member-exclusive launch, and what to stock for the member shopping peak.

**Category:** Multi-Join
**Difficulty:** Intermediate
**Business role:** Manager

**Solution approach:**
This is a four-table join: `product` to `product_category` (for the category name), to `order_item` (line items), to `"order"` (to filter for member orders). Filter `o.is_member_at_purchase = 1` and realized statuses. Aggregation grain is SKU: `SUM(quantity)` for units, `SUM(line_total_usd)` for member revenue, `COUNT(DISTINCT customer_id)` for unique member buyers. order_item is many-to-one with product, so there's no risk of double-counting product rows, but `COUNT(DISTINCT customer_id)` still needs DISTINCT to avoid counting one customer as multiple buyers when they place multiple orders.

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

**Expected result:**
Top 15 SKUs by attributed member revenue. Combine this list with `is_winner = 1` creative assets to plan the next member-exclusive campaign.

---

### Query 10: Win-Back List — Dormant High-Value Candidates

**Business context:**
The lifecycle-marketing manager is building the audience for the next reactivation campaign. The sweet-spot target is customers currently in dormant or at_risk status whose historical LTV is above average (> $200) — they earn a deeper discount to win back.

**Category:** Subquery + Join
**Difficulty:** Intermediate
**Business role:** Manager

**Solution approach:**
Target is "customers in dormant or at_risk with LTV > $200." Use a subquery on `"order"` to aggregate per-customer `lifetime_spend` and `last_order_date`, with `HAVING SUM(total_usd) > 200` filtering high-value customers inside the subquery (more efficient than pushing it to the outer query). Then JOIN back to `customer` with `WHERE lifecycle_stage IN ('dormant','at_risk')` to scope to sleepers. `days_since_last_order` is REFERENCE_DATE minus the last order date. Order by LTV descending, take the top 50, and feed it straight into the next REACTIVATION campaign.

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

**Expected result:**
Up to 50 dormant/at_risk customers with LTV > $200, ordered by LTV descending. Drop the list directly into the `target_segment` for the next REACTIVATION campaign.

---

### Query 11: Day-of-Week × Channel Performance

**Business context:**
The channel analyst is tuning send-time strategy. Looking at delivery and response by "day of week × channel" reveals the best send window per owned channel (e.g., push has the highest open rate on Sundays).

**Category:** Date Function + Aggregation
**Difficulty:** Intermediate
**Business role:** Analyst

**Solution approach:**
Cross-tab engagement by channel × day of week. `marketing_touchpoint` JOIN `campaign_channel` JOIN `channel_type` to get channel names, then LEFT JOIN `touchpoint_response` because some touchpoints have no response and we don't want to drop them. `strftime('%w', sent_at)` returns day of week (0 is Sunday), and a CASE turns it into a readable abbreviation. Filter `delivery_status = 'delivered'` to look only at successfully delivered touchpoints. The engaged and clicked definitions stay consistent with Q3, using `IN (...)` for the union. Group by channel and day of week, with the denominator standardized to `COUNT(mt.id)` (sends).

```sql
-- Consistent with Query 3 / Query 18: "click = IN('click','convert')".
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

**Expected result:**
A result set ready to drop into a heatmap: one row per (channel, day) combination with engagement rate. Use it to lock in the best send windows on the marketing calendar.

---

### Query 12: Customer Acquisition Cost (CAC) per Campaign

**Business context:**
The FP&A team needs unit economics for each acquisition campaign. Per campaign: spend ÷ (net new customers acquired within the campaign window) = effective CAC. Compared against an LTV benchmark, this shows which campaigns are actually paying back.

**Category:** CTE + Join
**Difficulty:** Advanced
**Business role:** Finance

**Solution approach:**
CAC = spend / new customers, augmented with first-order revenue to gauge payback speed. Three CTEs: campaign spend (aggregated on `campaign_channel`), customers acquired (count on `customer.acquisition_campaign_id`), and first-order revenue (`customer` joined to first orders where `o.is_first_order = 1`). `campaign` is the driver and INNER JOINs spend and acquisitions (CAC requires both), and LEFT JOINs first-order revenue. Filter `objective = 'ACQUISITION'` (CAC only makes sense for acquisition campaigns), plus `new_customers > 0` and `spend > 0` to guard against divide-by-zero. Sort by CAC ascending — the top is the most efficient.

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

**Expected result:**
Acquisition campaigns sorted by CAC ascending (lowest = most efficient). Campaigns with `first_order_roas ≥ 0.5` are typically considered sustainable — the remaining payback is expected to come from repeat purchases over the LTV cycle.

---

### Query 13: Audience-Segment Overlap Matrix

**Business context:**
The audience-strategy analyst is consolidating the segment pool ahead of the Q3 plan. She suspects many segments overlap heavily — running campaigns against overlapping segments wastes budget and causes user fatigue. This query outputs pairwise overlap counts among the Top 10 largest segments.

**Category:** Self-Join + CTE
**Difficulty:** Advanced
**Business role:** Analyst

**Solution approach:**
We want pairwise customer overlap among the Top 10 largest segments. First use a CTE to pick the 10 segments with the most members. The core move is a self-join on `customer_segment_membership`: m1 and m2 join on the same customer_id, giving us "customers who belong to both segments." The predicate `t2.segment_id > t1.segment_id` ensures each pair is counted once and a segment doesn't pair with itself (otherwise we'd get both A-B and B-A, plus A-A self-pairs). Group by segment pair, with `COUNT(DISTINCT m1.customer_id)` as the overlap count. Self-join is the standard technique for "pairwise relationships within one entity."

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

**Expected result:**
Top 25 most-overlapping segment pairs. Use it to merge or dedupe segments — for example, "Email Engaged Non-Members" and "Push Opted-In" might overlap by 60%+, in which case they should not be separately targeted by the same campaign.

---

### Query 14: Days to First Order by Acquisition Channel

**Business context:**
The lifecycle analyst studies how quickly new customers convert from signup to first order, broken out by acquisition channel. Shorter time-to-first-order = higher-quality channel (intent was already there at signup).

**Category:** Date Difference
**Difficulty:** Intermediate
**Business role:** Analyst

**Solution approach:**
Average days from signup to first order, by acquisition channel. `customer` JOIN `channel_type` (for channel name) JOIN `"order"` filtered to `o.is_first_order = 1`, so we get exactly one order per customer (their first). Days = `julianday(order_date) - julianday(signup_date)`, with AVG, MIN, MAX. `HAVING COUNT(DISTINCT customer_id) >= 10` filters out channels with too small a sample to keep the average stable. The INNER JOIN to order naturally excludes customers who never ordered, which is what we want (only look at activated customers).

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

**Expected result:**
Channels sorted by average days-to-first-order. High-intent channels like Search / Google Ads typically lead, with social-discovery channels behind.

---

### Query 15: Trial-to-Paid Conversion by Signup Cohort

**Business context:**
The membership business lead wants to know whether trial-to-paid conversion is improving or deteriorating. Bucketing trial starts by quarter and comparing conversion rates across quarters surfaces macro trends — for example, a Q4 program tweak that lifted conversion by 8 percentage points.

**Category:** CTE + Join
**Difficulty:** Advanced
**Business role:** Analyst

**Solution approach:**
Bucket trials by quarter to inspect the conversion trend. A CTE tags each `membership_subscription` row with `cohort_quarter`: `strftime('%Y', trial_start_date)` concatenated with "(month + 2) / 3" to compute the quarter (SQLite has no quarter function, so we compute it manually). The outer query GROUPs BY quarter, counts conversions via `activation_date IS NOT NULL`, and conversion rate = conversions / total trials. Use the `SUM(CASE WHEN ...)` pattern to also tally active and cancelled. Order by quarter — you can see whether trial-to-paid is climbing, falling, or flat by quarter.

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

**Expected result:**
One row per quarter, showing trial volume, conversions, the number still active, and the conversion rate. Look at the trend — is it climbing, falling, or flat?

---

### Query 16: Touchpoint Frequency-Cap Audit

**Business context:**
The compliance / operations team enforces a frequency cap: a customer must not receive more than 5 touchpoints from the same campaign within any 14-day window, to prevent fatigue and unsubscribes. This query lists the violators.

**Category:** Self-Join + CTE
**Difficulty:** Intermediate
**Business role:** Operations

**Solution approach:**
We want to find "the same customer receiving more than 5 touchpoints from the same campaign within a 14-day window." SQLite doesn't support `INTERVAL` in the window's RANGE clause, so we use a correlated self-join instead: t1 and t2 join on the same customer_id and campaign_id with the predicate `t2.sent_at <= t1.sent_at AND julianday(t1) - julianday(t2) <= 14`, so for each t1 we can count how many touchpoints occurred in its "prior 14 days." A CTE first lifts touchpoints to campaign via `campaign_channel`. The outer `WHERE sends_in_prior_14d > 5` filters violators, then we aggregate by customer + campaign and take the max window value. This is production-grade rolling-window SQL, not a placeholder.

```sql
-- SQLite does not support INTERVAL syntax in RANGE clauses. Use a self-join
-- to compute the 14-day rolling window, then aggregate violators.
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

**Expected result:**
Top 30 "customer–campaign" combinations that exceeded the 5-touch cap. Push the list onto the Lifecycle Ops queue for review.

---

### Query 17: Campaigns Flagged for Budget-Pacing Overrun

**Business context:**
Campaign operations needs to flag campaigns that are burning budget too fast — i.e., "% budget spent significantly exceeds % time elapsed." These either need a budget increase or a daily cap.

**Category:** CTE + Filter
**Difficulty:** Basic
**Business role:** Operations

**Solution approach:**
We want campaigns that are spending faster than time is elapsing. The `pacing` CTE computes both percentages at once: `pct_spent = spend / budget` and `pct_elapsed = (today - start) / (end - start)`, with `MAX(0, MIN(100, ...))` to clamp the latter to [0, 100] and guard against edge cases where start is in the future or end has passed. Spend comes from a `campaign_channel`-aggregated CTE, attached via LEFT JOIN. The outer `WHERE pct_spent > pct_elapsed + 10` cleanly filters to campaigns overspending by more than 10 percentage points, sorted by overrun magnitude descending. Only `status = 'ACTIVE'` campaigns are in scope.

```sql
-- pct_elapsed is clamped to [0, 100] to guard against ACTIVE campaigns whose start_date is in
-- the future or whose end_date has passed. The pacing CTE computes both percentages at once,
-- so the outer WHERE can filter cleanly.
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

**Expected result:**
Active campaigns "spending pace exceeds time pace by more than 10 percentage points." These need urgent decisions before the budget runs out.

---

### Query 18: Creative-Asset CTR Leaderboard

**Business context:**
The creative lead is reviewing which assets have the best click-per-send. The conclusions feed the A/B-test winner roll-ups and the scale-up of winning creatives.

**Category:** Join + Aggregation
**Difficulty:** Intermediate
**Business role:** Manager

**Solution approach:**
Click-per-send by creative asset. `creative_asset` LEFT JOIN `marketing_touchpoint`, with `delivery_status = 'delivered'` in the join condition (not the WHERE), so assets with no delivered touchpoints still survive (CTR shows 0 instead of disappearing). Then LEFT JOIN `touchpoint_response`. CTR = clicks / sends, where clicks uses `IN ('click','convert')` consistent with Q3 and Q11. GROUP BY asset, with `HAVING COUNT(mt.id) >= 5` to filter out assets with too few impressions. Crossing `is_winner` against high CTR validates whether the A/B test picked the right winner.

```sql
-- "click" is defined as IN ('click','convert'), consistent with Query 3 / Query 11 —
-- a 'convert' touch implies the user clicked first.
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

**Expected result:**
Top 20 creatives by CTR. Cross-reference `is_winner` against high CTR — mismatches suggest the A/B test may have picked the wrong winner (or, alternatively, the winner was chosen by conversion rate rather than CTR).

---

### Query 19: Geographic Revenue Heatmap

**Business context:**
The regional GM wants a quick read on the revenue distribution across U.S. states and Canadian provinces. The output drives regional marketing budget allocation and fulfillment-center planning.

**Category:** Aggregation
**Difficulty:** Basic
**Business role:** Executive

**Solution approach:**
Revenue distribution by country and state/province. `customer` LEFT JOIN `"order"`, with the realized-status filter placed in the join condition so regions with no orders still appear in the result (revenue shows 0 instead of the row disappearing). GROUP BY `country, state_or_province`, use `COUNT(DISTINCT)` separately for customers and orders, `SUM(total_usd)` for revenue, and divide by customer count for revenue per customer. The reason for LEFT JOIN instead of INNER is exactly so small regions are not silently dropped. Sort by gross revenue descending to get the regional leaderboard.

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

**Expected result:**
Regions ranked by gross revenue. In the U.S., expect CA, NY, TX, WA, MA, FL near the top; Canadian provinces will rank lower (they make up 12% of the customer base).

---

### Query 20: Segment AOV Ranking (with Member Penetration)

**Business context:**
The senior audience analyst is preparing the proposal for the next campaign wave and needs to defend the segment selection. The strongest segments have both high AOV and high member penetration — premium offers resonate best on those. Window functions are used to rank within each `segment_type`.

**Category:** CTE + Window Function
**Difficulty:** Intermediate
**Business role:** Analyst

**Solution approach:**
This query has a classic join fan-out trap: if you join segment, order, and membership directly and aggregate, a customer's multiple orders will double-count them as multiple active members and inflate member penetration. So we first aggregate at customer grain in `customer_metrics` (one row per customer: lifetime_spend, order_count, is_active_member), digesting the fan-out at that layer. Then in `seg_metrics` we join segment to those customer metrics and aggregate, with AOV = total spend / total orders, and member penetration = active members / segment size. Finally we use `RANK() OVER (PARTITION BY segment_type ORDER BY avg_order_value DESC)` to rank within each segment_type. The window function is the right tool for "rank within groups," much cleaner than self-join counting.

```sql
-- Aggregate at customer grain (one row per customer) before rolling up to segment,
-- to avoid the join fan-out where "one customer with many orders is counted as
-- many active members."
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

**Expected result:**
Segments ranked by AOV within each segment_type. Pair with `pct_active_members` to find segments that are both lucrative and member-dense — these are the prime targets for upsell campaigns.

---

## Query Category Summary

A single query may belong to multiple categories — the count column tallies queries that meaningfully use that pattern.

| Category | Count | Query IDs |
|----------|-------|-----------|
| Aggregation | 5 | 1, 4, 8, 11, 19 |
| Join Operations | 5 | 6, 9, 10, 14, 18 |
| Window Functions | 1 | 20 |
| Date/Time Analysis | 4 | 5, 11, 14, 17 |
| Subqueries/CTEs | 9 | 1, 2, 3, 5, 7, 12, 13, 15, 17, 20 |
| Self-Join | 2 | 13, 16 |
| Multi-table Joins (≥3) | 4 | 9, 13, 18, 20 |

## Business Role Coverage

| Role | Count | Query IDs |
|------|-------|-----------|
| Executive / C-Level | 2 | 1, 19 |
| Manager | 5 | 2, 8, 9, 10, 18 |
| Analyst | 7 | 3, 5, 6, 11, 13, 14, 15, 20 |
| Operations | 3 | 7, 16, 17 |
| Finance | 2 | 4, 12 |

## Difficulty Distribution

| Difficulty | Count | Query IDs |
|------------|-------|-----------|
| Basic | 7 | 1, 4, 6, 7, 8, 17, 19 |
| Intermediate | 9 | 2, 3, 9, 10, 11, 14, 16, 18, 20 |
| Advanced | 4 | 5, 12, 13, 15 |

---

## Notes

- All queries use SQLite 3.25+ syntax (Q20 requires window functions).
- In raw SQL, `"order"` must be quoted — it is a SQL reserved word. SQLAlchemy quotes it automatically; hand-written SQL must do so explicitly.
- Queries can be adapted to other databases (PostgreSQL, MySQL) with minor tweaks — reserved-word quoting differs: `"order"` (SQLite / PostgreSQL) vs `` `order` `` (MySQL).
- The "today" in date-arithmetic queries is hard-coded as `2026-06-01` (matching the generator's `TODAY` constant for reproducibility) — replace with `date('now')` in production.
- Query 16 uses a correlated self-join to implement the 14-day rolling frequency audit (SQLite does not accept `INTERVAL` in `RANGE` clauses). The `julianday(t1) - julianday(t2) <= 14` filter is the real production form — not a placeholder.
- The "click" definition stays consistent across Q3, Q11, Q18: `click = response_type IN ('click', 'convert')`. A `convert` response implies the customer clicked first (terminal-state response model).
- Q2 (Channel ROAS) uses spend-share weighting because `attributed_campaign_id` is at the campaign grain. True channel-level attribution would require a touchpoint-level last-touch chain.
