# Cloud Provider Customer Success Management SQL Query Reference

> **Business context and glossary:** `01-cloud_provider_customer_success_medium_business_context.md`
> **Data structure (ER):** `02-cloud_provider_customer_success_medium_er_document.md`
> **Database file:** `cloud_provider_customer_success_medium.sqlite`
> **All queries are compatible with SQLite 3.x.** Reference "today" (REFERENCE_DATE) = `2026-06-20`.
> **Fictional company:** NimbusScale, Inc. (mid-market cloud infrastructure provider, PaaS + AI/ML inference)

---

## 1. Overview

This document provides 20 business-oriented SQL queries designed for the `cloud_provider_customer_success_medium` dataset. Each query solves a realistic question someone inside NimbusScale (a CSM, a sales leader, an analyst, a CFO) might ask, and the set is meant for AI Agent + Text-to-SQL project demos.

The queries are organized along two complementary axes. First, by 5 business themes (see the business-theme map below), answering the question "what can you learn from this dataset?" Second, by a sequential 1-to-20 numbering (see the query index and the query details below), which serves as the standard reference order.

---

## 2. How to Use This Document

This document is written for a new intern on the NimbusScale Customer Success Operations team. It assumes you have already read the `01` business context document (so you know what the company is, what tiers and health scores are, what renewals are about) and the `02` ER document (so you know which tables, fields, and foreign keys exist). Your manager has just handed you this query collection and said, "Work through these this week."

Every query follows the same five-part structure. Reading through it teaches you how a real analyst thinks through a problem:

1. **Business context** explains who is asking, why they are asking now, and what decision the answer supports.
2. **Category / Difficulty / Business role** are three tags that tell you at a glance what SQL technique is being practiced, how hard it is, and which role it serves.
3. **Approach** walks you through which tables to touch, how the joins line up, what granularity to aggregate at, why you need a CTE or window function, and the pitfalls (fan-out, divide-by-zero, NULL semantics) to avoid, all before you see any SQL.
4. **SQL code** is the actual query you can paste into the SQLite database and run.
5. **Expected results and business takeaway** describe what the output should look like, the rough magnitude of the key numbers, and what the analyst is supposed to do once they have the result.

Two conventions apply throughout. First, the dataset is anchored to a fixed `REFERENCE_DATE = 2026-06-20`, so anywhere "today" is needed, treat it as that date for reproducibility (the generator uses the run date as its anchor internally, but the magnitudes per tier stay consistent). Second, every query traces back to one of the business questions listed in `01`. The SQL is meant to be read and learned from, not just executed.

---

## 3. Business Glossary

These terms run through every query. A Text-to-SQL agent should treat this table as the canonical mapping between business language and the dataset's column names:

| Term | Definition | Implementation in this dataset |
|------|------------|--------------------------------|
| **CSM** | Customer Success Manager -- the person responsible for customer health, renewal, and expansion | `csm` table; `customer.csm_id` FK |
| **Tier** | Account level (`Enterprise` / `Business` / `Pro` / `Basic`) | `account_tier` table; `customer.account_tier_id` |
| **Tier specialization** | The customer level a CSM is qualified to serve | `csm.tier_specialization` ∈ {Enterprise, Mid-Market, SMB} |
| **Active customer** | Has at least one subscription that is not {churned, expired} | `customer.is_active = 1` (derived field) |
| **Health score** | 0-to-100 composite; lower means higher churn risk | `health_score.overall_score` = 0.4 * usage + 0.3 * engagement + 0.3 * support |
| **Health baseline** (internal) | The customer's implicit "health tendency," driving ticket count and sub-scores | Not persisted; affects `support_tickets_count` and sub-scores |
| **Low health** | Customer needs intervention | `overall_score < 60` |
| **Churn risk** | Composite risk flag | Low health OR usage drop OR pending renewal -- see Q12 |
| **QBR** | Quarterly Business Review (formal quarterly business meeting) | `interaction_log` rows where `interaction_type.name = 'QBR Meeting'` |
| **Committed spend** | Contractual monthly minimum spend | `subscription.monthly_committed_spend` |
| **Actual spend** | Real spend based on metered usage | `usage_metrics.total_spend` (compute + storage + network + ai_ml) |
| **Overage** | Amount actual spend exceeds committed | `actual - committed > 0` |
| **Pending Renewal** | Contract is near expiration and renewal decision is still open | `subscription.status = 'pending_renewal'` |
| **Churn** | Customer cancels their subscription early | `subscription.status = 'churned'` |
| **Expansion opportunity** | Healthy customer + sustained usage growth -- an upsell target | High health score + positive growth trend (see Q15) |
| **AI/ML user** | A customer using AI/ML services in their latest month | The customer's latest `month_year` row has `usage_metrics.ai_ml_spend > 0` |
| **Latest score (per-customer MAX)** | Each customer's own latest health snapshot | Correlated subquery: `score_date = (SELECT MAX(score_date) FROM health_score WHERE customer_id = hs.customer_id)` |

---

## 4. Business-Theme Map

The 20 queries cluster into 5 themes, mirroring the actual day-to-day work of the NimbusScale CSM team:

### Customer Health Monitoring

Verify the inverse relationship between support tickets and health, track AI/ML adoption across the customer base, and monitor sentiment trends in customer interactions.

| Query | Title | Difficulty |
|-------|-------|------------|
| Q11 | AI/ML service adoption rate | Basic |
| Q14 | Support tickets vs. health score correlation | Intermediate |
| Q18 | Customer sentiment trend analysis | Intermediate |

### Renewal Risk Management

Identify renewal-risk customers (low health + contract nearing expiration), build a churn-risk report, inventory contracts expiring in the next 30/60/90 days, and track QBR completion as a renewal-readiness signal.

| Query | Title | Difficulty |
|-------|-------|------------|
| Q3 | Low-health customers up for renewal | Intermediate |
| Q12 | Churn-risk customer identification | Advanced |
| Q17 | Upcoming contract expiration alerts | Basic |
| Q19 | Quarterly QBR completion status | Intermediate |

### Expansion Opportunity

Track per-customer spend trends and identify healthy, steadily growing customers as upsell candidates.

| Query | Title | Difficulty |
|-------|-------|------------|
| Q4 | Customer monthly spend trend | Intermediate |
| Q15 | Expansion opportunity identification | Advanced |

### CSM Team Operations

Operational queries used by the ops manager and CSM team leads: task throughput, work queue, and workload balance.

| Query | Title | Difficulty |
|-------|-------|------------|
| Q6 | CSM task completion rate | Basic |
| Q9 | High-priority open tasks | Basic |
| Q16 | CSM workload distribution | Intermediate |

### Portfolio Analytics & Executive Reporting

C-level, analyst, finance, and Customer-360 queries. Includes the full customer snapshot the CSM uses before a customer meeting.

| Query | Title | Difficulty |
|-------|-------|------------|
| Q1 | Customer count distribution by tier | Basic |
| Q2 | Customers with usage drop greater than 20% | Advanced |
| Q5 | Spend ranking by region | Intermediate |
| Q7 | Customers with the biggest health-score swings | Advanced |
| Q8 | Enterprise customer average spend analysis | Intermediate |
| Q10 | Customer interaction frequency analysis | Intermediate |
| Q13 | Customer distribution and spend by industry | Basic |
| Q20 | Customer 360 view | Advanced |

---

## 5. Query Index

| # | Title | Business role | Category | Difficulty |
|---|-------|---------------|----------|------------|
| 1 | Customer count distribution by tier | Executive | Aggregation | Basic |
| 2 | Customers with usage drop greater than 20% | CSM Manager | Window function | Advanced |
| 3 | Low-health customers up for renewal | CSM Manager | Joins | Intermediate |
| 4 | Customer monthly spend trend | Analyst | Window function | Intermediate |
| 5 | Spend ranking by region | Executive | Aggregation + Joins | Intermediate |
| 6 | CSM task completion rate | Operations | Aggregation | Basic |
| 7 | Customers with the biggest health-score swings | CSM Manager | Window function | Advanced |
| 8 | Enterprise customer average spend analysis | Finance | CTE + Aggregation | Intermediate |
| 9 | High-priority open tasks | Operations | Joins | Basic |
| 10 | Customer interaction frequency analysis | Analyst | Aggregation + Date | Intermediate |
| 11 | AI/ML service adoption rate | Executive | CTE + Aggregation | Basic |
| 12 | Churn-risk customer identification | CSM Manager | CTE + Joins | Advanced |
| 13 | Customer distribution and spend by industry | Analyst | Aggregation | Basic |
| 14 | Support tickets vs. health-score correlation | Analyst | CTE + Aggregation | Intermediate |
| 15 | Expansion opportunity identification | CSM Manager | CTE + Window | Advanced |
| 16 | CSM workload distribution | Operations | CTE + Joins | Intermediate |
| 17 | Upcoming contract expiration alerts | Operations | Date range | Basic |
| 18 | Customer sentiment trend analysis | Analyst | Aggregation + Date | Intermediate |
| 19 | Quarterly QBR completion status | Operations | Joins + Date | Intermediate |
| 20 | Customer 360 view | CSM | CTE + Multi-table joins | Advanced |

---

## 6. Query Details

### Query 1: Customer count distribution by tier

**Business context:**
The VP of Sales needs to understand the current customer-portfolio composition at the quarterly business review. They want to see customer counts and percentages across Enterprise, Business, Pro, and Basic, to decide whether to adjust the customer-acquisition strategy or to push for upgrades within a specific tier.

**Category:** Aggregation query
**Difficulty:** Basic
**Business role:** Executive / C-level

**Approach:**
This only needs two tables: customer and account_tier. GROUP BY tier to count customers, then use the window function `SUM(COUNT(c.id)) OVER()` to grab the grand total in the same aggregation and compute the percentage, saving an extra subquery. `WHERE c.is_active = 1` excludes customers whose subscriptions are all churned/expired, so "portfolio composition" reflects the book of business we are actively serving. Ordering by `account_tier.monthly_min_spend` descending puts Enterprise at the top naturally. No CTE or window partitioning is needed; one aggregation does the job.

```sql
SELECT
    t.name AS tier_name,
    COUNT(c.id) AS customer_count,
    ROUND(COUNT(c.id) * 100.0 / SUM(COUNT(c.id)) OVER(), 2) AS percentage
FROM customer c
JOIN account_tier t ON c.account_tier_id = t.id
WHERE c.is_active = 1
GROUP BY t.id, t.name
ORDER BY t.monthly_min_spend DESC;
```

**Expected results:**
Returns 4 rows showing the active customer count per tier. Roughly Enterprise 15%, Business 30%, Pro 35%, Basic 20%. A small number of customers with all subscriptions churned are filtered out by `is_active=0`.

Business takeaway: This is the opening slide of the quarterly review. If a high-value tier is significantly under-target, the VP of Sales uses this to decide whether to double down on acquisition for that tier or to push lower-tier customers to upgrade.

---

### Query 2: Customers with usage drop greater than 20%

**Business context:**
The CSM team lead needs to spot customers whose usage dropped meaningfully last week at the Monday standup. A usage drop is often a leading indicator of churn. They need a quick list of "customers whose last month's usage dropped more than 20% vs. the prior month" so they can hand the team a prioritized follow-up list.

**Category:** Window function
**Difficulty:** Advanced
**Business role:** CSM Manager

**Approach:**
The core idea is month-over-month for the same customer, using `LAG(total_spend) OVER (PARTITION BY customer_id ORDER BY month_year)` to grab last month's value. `PARTITION BY customer_id` is mandatory; without it the window bleeds across customers and you would attribute someone else's previous month to this customer. Pre-compute `prev_month_spend` in a CTE, then JOIN customer / csm / account_tier in the outer layer to add names and tier. Use `NULLIF(prev, 0)` to protect against divide-by-zero from a first month or zero spend, and require the change to be less than -0.20. The first month for each customer has a NULL `prev`, which the WHERE clause naturally excludes.

```sql
WITH monthly_changes AS (
    SELECT
        customer_id,
        month_year,
        total_spend,
        LAG(total_spend) OVER (PARTITION BY customer_id ORDER BY month_year) AS prev_month_spend
    FROM usage_metrics
)
SELECT
    c.id AS customer_id,
    c.company_name,
    csm.name AS csm_name,
    t.name AS tier,
    mc.month_year,
    ROUND(mc.prev_month_spend, 2) AS prev_spend,
    ROUND(mc.total_spend, 2) AS current_spend,
    ROUND((mc.total_spend - mc.prev_month_spend) / NULLIF(mc.prev_month_spend, 0) * 100, 2) AS change_pct
FROM monthly_changes mc
JOIN customer c ON mc.customer_id = c.id
JOIN csm ON c.csm_id = csm.id
JOIN account_tier t ON c.account_tier_id = t.id
WHERE mc.prev_month_spend IS NOT NULL
  AND mc.prev_month_spend > 0
  AND (mc.total_spend - mc.prev_month_spend) / NULLIF(mc.prev_month_spend, 0) < -0.20
ORDER BY change_pct ASC
LIMIT 20;
```

**Expected results:**
Returns customers with the biggest usage drops, sorted by percentage drop. For example, a customer who spent $50,000 last month and only $35,000 this month (a 30% drop) needs immediate attention. The `NULLIF` guard prevents divide-by-zero from producing NULL instead of an exception.

---

### Query 3: Low-health customers up for renewal

**Business context:**
At the start of each month, the Director of Customer Success needs to identify customers whose contract expires within 90 days and whose health score is below 60. These are the highest-risk renewals and need an executive visit or a tailored save plan immediately.

**Category:** Join query
**Difficulty:** Intermediate
**Business role:** CSM Manager

**Approach:**
This query has to align two things: the renewal window and each customer's own latest health snapshot. subscription provides the pending_renewal status and contract end date; health_score provides the score. The catch is that a customer has multiple health snapshots, so you need a correlated subquery `hs.score_date = (SELECT MAX(score_date) ... WHERE customer_id = c.id)` to keep only that customer's most recent snapshot. Otherwise old snapshots leak in and inflate or distort the result. All three filters (pending_renewal, the 90-day window, latest score < 60) are mandatory and together pin down the truly high-risk renewals.

```sql
SELECT
    c.id AS customer_id,
    c.company_name,
    csm.name AS csm_name,
    t.name AS tier,
    s.contract_end_date,
    JULIANDAY(s.contract_end_date) - JULIANDAY('now') AS days_to_renewal,
    s.monthly_committed_spend,
    hs.overall_score AS health_score,
    hs.notes AS health_notes
FROM customer c
JOIN subscription s ON c.id = s.customer_id
JOIN csm ON c.csm_id = csm.id
JOIN account_tier t ON c.account_tier_id = t.id
JOIN health_score hs ON c.id = hs.customer_id
WHERE s.status = 'pending_renewal'
  AND s.contract_end_date BETWEEN DATE('now') AND DATE('now', '+90 days')
  AND hs.score_date = (SELECT MAX(score_date) FROM health_score WHERE customer_id = c.id)
  AND hs.overall_score < 60
ORDER BY s.contract_end_date ASC, hs.overall_score ASC;
```

**Expected results:**
Returns pending_renewal customers expiring within 90 days whose latest health is below 60, sorted by expiration date and then by score, both ascending. Each customer is matched against its own latest score (per-customer MAX). Typically only a handful of customers hit all three conditions.

Business takeaway: This is the Director of Customer Success's "save list" for the month. The top entries get an executive visit or a custom save plan immediately, and the smaller days_to_renewal is, the more urgent it is.

---

### Query 4: Customer monthly spend trend

**Business context:**
A finance analyst building the quarterly revenue forecast needs to see a specific large customer's spend trend over the last 6 months. They want monthly totals plus month-over-month growth to judge whether revenue is stable or sliding, and to adjust the forecasting model accordingly.

**Category:** Window function
**Difficulty:** Intermediate
**Business role:** Analyst

**Approach:**
This is a single-customer time-series analysis using `LAG(total_spend)` for month-over-month growth. Because the WHERE already pins down to a single customer (`c.id = 51`), the window has only one partition, but you still need `PARTITION BY c.id` plus `ORDER BY month_year` to guarantee the previous row is picked up correctly by month. Listing compute / storage / ai_ml / total separately makes it easy to see which line is growing or shrinking. `NULLIF` protects the first month from divide-by-zero. To analyze a different customer, just swap the id in the WHERE clause.

```sql
SELECT
    c.company_name,
    um.month_year,
    ROUND(um.compute_spend, 2) AS compute,
    ROUND(um.storage_spend, 2) AS storage,
    ROUND(um.ai_ml_spend, 2) AS ai_ml,
    ROUND(um.total_spend, 2) AS total,
    ROUND(
        (um.total_spend - LAG(um.total_spend) OVER (PARTITION BY c.id ORDER BY um.month_year))
        / NULLIF(LAG(um.total_spend) OVER (PARTITION BY c.id ORDER BY um.month_year), 0) * 100,
    2) AS mom_growth_pct
FROM usage_metrics um
JOIN customer c ON um.customer_id = c.id
WHERE c.id = 51  -- Replace with any customer ID (example: an Enterprise customer)
ORDER BY um.month_year;
```

**Expected results:**
Returns 6 months (or fewer, depending on created_at) of spend detail and MoM growth for the chosen customer. NULLIF protects the first month from divide-by-zero.

Business takeaway: The finance analyst uses this to decide whether this large customer's revenue is stable or sliding. If mom_growth_pct is negative for several months in a row, mark the customer down in the forecast and flag the CSM to intervene.

---

### Query 5: Spend ranking by region

**Business context:**
The Regional Sales Director needs customer counts and total spend per AWS region over the last 6 months to set next quarter's sales targets. This helps them identify high-growth regions (such as APAC) and underperforming ones, and allocate sales and marketing resources accordingly.

**Category:** Aggregation + Joins
**Difficulty:** Intermediate
**Business role:** Executive

**Approach:**
region -> customer -> usage_metrics is a two-level one-to-many. When aggregating by region, the customer count must use `COUNT(DISTINCT c.id)`. Otherwise the multiple monthly rows in usage_metrics will count the same customer six times and inflate the headcount. The WHERE limits to the last 6 months and active customers, so the ranking reflects recent spend by the currently active book of business. Note that customers created this month with no usage rows yet will be silently dropped by the INNER JOIN, which is correct business behavior (no usable history for a brand-new customer).

```sql
SELECT
    r.code AS region_code,
    r.name AS region_name,
    r.continent,
    COUNT(DISTINCT c.id) AS customer_count,
    ROUND(SUM(um.total_spend), 2) AS total_spend_6m,
    ROUND(AVG(um.total_spend), 2) AS avg_monthly_spend_per_record
FROM region r
JOIN customer c ON r.id = c.primary_region_id
JOIN usage_metrics um ON c.id = um.customer_id
WHERE c.is_active = 1
  AND um.month_year >= DATE('now', '-6 months', 'start of month')
GROUP BY r.id, r.code, r.name, r.continent
ORDER BY total_spend_6m DESC;
```

**Expected results:**
Returns customer counts and spend totals per region over the last 6 months. us-east-1 usually has the most customers; APAC may show the fastest growth.

Business takeaway: The Regional Sales Director uses this to allocate next quarter's sales and marketing resources, shifting headcount toward regions with fewer customers but accelerating spend.

---

### Query 6: CSM task completion rate

**Business context:**
The ops manager reports weekly to the VP on the CSM team's task throughput. They need counts and percentages by status (open, in_progress, completed, cancelled) to assess team execution and whether the workload is sustainable.

**Category:** Aggregation query
**Difficulty:** Basic
**Business role:** Operations

**Approach:**
The simplest single-table aggregation. GROUP BY status on csm_task and use `SUM(COUNT(*)) OVER()` to compute the percentage. The CASE in ORDER BY puts the result in the order the business cares about (completed -> in_progress -> open -> cancelled) instead of alphabetical. No joins, perfect for practicing the "aggregation plus window-based percentage" pattern.

```sql
SELECT
    status,
    COUNT(*) AS task_count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 2) AS percentage
FROM csm_task
GROUP BY status
ORDER BY
    CASE status
        WHEN 'completed' THEN 1
        WHEN 'in_progress' THEN 2
        WHEN 'open' THEN 3
        WHEN 'cancelled' THEN 4
    END;
```

**Expected results:**
Returns 4 rows. In a healthy state, completed should be 40%+. If open and in_progress pile up, it suggests the team needs more capacity.

---

### Query 7: Customers with the biggest health-score swings

**Business context:**
At the weekly team meeting, the CSM team needs to identify the customers whose health scores moved the most. A big drop demands urgent intervention; a big increase may be an expansion opportunity.

**Category:** Window function
**Difficulty:** Advanced
**Business role:** CSM Manager

**Approach:**
Structurally identical to Q2, just with overall_score instead of total_spend, measuring health rather than spend. The CTE uses `LAG(overall_score)` to grab each customer's previous snapshot score; the outer layer takes the top 15 by `ABS(change)`. Absolute change is what we want here, because both big rises (expansion signals) and big drops (churn signals) deserve attention. `PARTITION BY customer_id` is mandatory, and the first snapshot's prev_score is NULL and must be filtered out.

```sql
WITH score_changes AS (
    SELECT
        customer_id,
        score_date,
        overall_score,
        LAG(overall_score) OVER (PARTITION BY customer_id ORDER BY score_date) AS prev_score
    FROM health_score
)
SELECT
    c.id AS customer_id,
    c.company_name,
    csm.name AS csm_name,
    t.name AS tier,
    sc.score_date,
    sc.prev_score,
    sc.overall_score AS current_score,
    sc.overall_score - sc.prev_score AS score_change
FROM score_changes sc
JOIN customer c ON sc.customer_id = c.id
JOIN csm ON c.csm_id = csm.id
JOIN account_tier t ON c.account_tier_id = t.id
WHERE sc.prev_score IS NOT NULL
ORDER BY ABS(sc.overall_score - sc.prev_score) DESC
LIMIT 15;
```

**Expected results:**
Returns the 15 customers with the largest absolute health-score change between adjacent snapshots (with positive or negative score_change). Big drops trigger a churn-root-cause investigation; big rises trigger an expansion review.

Business takeaway: At the weekly meeting, the CSM manager uses this list to split the work. Customers with a sharply negative score_change get an intervention scheduled this week; customers with a sharply positive score get handed to sales for an upsell review.

---

### Query 8: Enterprise customer average spend analysis

**Business context:**
The CFO is preparing a board update and needs the actual vs. committed spend for Enterprise customers (the highest-value cohort).

**Category:** CTE + Aggregation
**Difficulty:** Intermediate
**Business role:** Finance

**Approach:**
The biggest pitfall is that both subscription and usage_metrics are one-to-many off customer, so a direct JOIN creates a subscription × usage cartesian fan-out and doubles the spend. The right approach is to pre-aggregate each side to customer granularity in its own CTE: take AVG over usage to get average actual spend, and SUM over active subscriptions to get total committed spend, then align by customer_id. The denominator uses SUM (not MAX) because a customer may have multiple active contracts, while actual spend covers all of the customer's services together. Finally, restrict to active Enterprise customers.

```sql
WITH usage_summary AS (
    SELECT customer_id,
           AVG(total_spend) AS avg_actual_spend,
           COUNT(*) AS months_data
    FROM usage_metrics
    GROUP BY customer_id
),
active_sub AS (
    -- A customer can have multiple active subscriptions. SUM gives the total committed spend across all their contracts.
    -- (avg_actual_spend from usage_metrics already covers all the customer's services, so the denominator must be SUM, not MAX.)
    SELECT customer_id,
           SUM(monthly_committed_spend) AS committed
    FROM subscription
    WHERE status = 'active'
    GROUP BY customer_id
)
SELECT
    c.company_name,
    ROUND(asub.committed, 2) AS committed,
    ROUND(us.avg_actual_spend, 2) AS avg_actual_spend,
    ROUND(us.avg_actual_spend - asub.committed, 2) AS overage,
    ROUND((us.avg_actual_spend / NULLIF(asub.committed, 0) - 1) * 100, 2) AS overage_pct,
    us.months_data
FROM customer c
JOIN account_tier t ON c.account_tier_id = t.id
JOIN usage_summary us ON c.id = us.customer_id
JOIN active_sub asub ON c.id = asub.customer_id
WHERE t.name = 'Enterprise'
  AND c.is_active = 1
ORDER BY avg_actual_spend DESC;
```

**Expected results:**
One row per Enterprise customer (each side is pre-aggregated in a CTE to avoid the subscription × usage_metrics fan-out); a positive overage_pct means actual spend exceeded committed.

---

### Query 9: High-priority open tasks

**Business context:**
Every morning, the CSM team lead needs to check which high-priority or critical tasks are still open. These typically involve urgent items for important customers, and delays can lead to churn or escalations.

**Category:** Join query
**Difficulty:** Basic
**Business role:** Operations

**Approach:**
A straightforward work-queue query. Join csm_task to customer and csm to pick up names, then filter `priority IN ('high','critical')` and `status IN ('open','in_progress')`. The sort uses CASE to pin critical to the top, then by due_date ascending so the most urgent tasks are at the top. A negative `days_until_due` means the task is already overdue, which is the red-flag signal for the team lead.

```sql
SELECT
    task.id AS task_id,
    c.company_name,
    csm.name AS csm_name,
    task.task_type,
    task.title,
    task.priority,
    task.status,
    task.due_date,
    JULIANDAY(task.due_date) - JULIANDAY('now') AS days_until_due
FROM csm_task task
JOIN customer c ON task.customer_id = c.id
JOIN csm ON c.csm_id = csm.id
WHERE task.priority IN ('high', 'critical')
  AND task.status IN ('open', 'in_progress')
ORDER BY
    CASE task.priority WHEN 'critical' THEN 1 ELSE 2 END,
    task.due_date ASC;
```

**Expected results:**
Returns all open high/critical tasks, sorted by urgency and then by due date. A negative days_until_due means the task is overdue.

---

### Query 10: Customer interaction frequency analysis

**Business context:**
The customer success ops analyst evaluating team effectiveness needs to understand interaction frequency with each customer. Too few interactions and customers feel ignored; too many often means a customer with a lot of problems.

**Category:** Aggregation + Date
**Difficulty:** Intermediate
**Business role:** Analyst

**Approach:**
The key trick is placing the "last 90 days" date filter inside the `LEFT JOIN ... ON` clause, not in the WHERE. That way customers with zero interactions in the last 90 days are still kept, with an interaction count of 0, instead of being filtered out. Aggregate by customer for interaction count, positive/negative sentiment counts, and last interaction time. If the date filter were in WHERE, silent customers would disappear entirely, and silent customers are exactly the ones who most need to be surfaced, so the LEFT JOIN plus the condition placement are deliberate.

```sql
SELECT
    c.company_name,
    t.name AS tier,
    COUNT(il.id) AS interaction_count,
    ROUND(COUNT(il.id) * 30.0 / 90, 2) AS monthly_avg,
    SUM(CASE WHEN il.sentiment = 'positive' THEN 1 ELSE 0 END) AS positive_count,
    SUM(CASE WHEN il.sentiment = 'negative' THEN 1 ELSE 0 END) AS negative_count,
    MAX(il.interaction_date) AS last_interaction
FROM customer c
JOIN account_tier t ON c.account_tier_id = t.id
LEFT JOIN interaction_log il ON c.id = il.customer_id
    AND il.interaction_date >= DATE('now', '-90 days')
WHERE c.is_active = 1
GROUP BY c.id, c.company_name, t.name
ORDER BY interaction_count DESC;
```

**Expected results:**
Returns the last-90-days interaction stats for each active customer. Enterprise typically averages 3 to 5 per month.

Business takeaway: A high-value customer whose interaction_count is close to 0 is an "ignored" signal, and the CS ops analyst should remind the owning CSM to reach out proactively. A customer with a high negative_count needs a satisfaction-root-cause check.

---

### Query 11: AI/ML service adoption rate

**Business context:**
The VP of Product wants to understand AI/ML service penetration across the customer base, to assess AI product market acceptance and identify customers who have not yet adopted AI services.

**Category:** CTE + Aggregation
**Difficulty:** Basic
**Business role:** Executive

**Approach:**
First, in the CTE, use a correlated subquery `month_year = (SELECT MAX(month_year) ... WHERE customer_id = um.customer_id)` to pick each customer's own latest month, and tag it with a CASE expression marking "AI/ML user" vs. "Non AI/ML user" (`ai_ml_spend > 0`). The outer query just needs to GROUP BY that tag and split into two cohorts. Tagging in the CTE keeps the outer aggregation clean and avoids stacking CASE statements inside the GROUP BY.

```sql
WITH latest_usage AS (
    -- per-customer MAX: pick each customer's own latest usage month
    SELECT
        um.customer_id,
        um.total_spend,
        um.ai_ml_spend,
        CASE WHEN um.ai_ml_spend > 0 THEN 'AI/ML user' ELSE 'Non AI/ML user' END AS segment
    FROM usage_metrics um
    WHERE um.month_year = (
        SELECT MAX(month_year) FROM usage_metrics WHERE customer_id = um.customer_id
    )
)
SELECT
    segment,
    COUNT(DISTINCT customer_id) AS customer_count,
    ROUND(AVG(total_spend), 2) AS avg_total_spend,
    ROUND(AVG(ai_ml_spend), 2) AS avg_ai_ml_spend
FROM latest_usage
GROUP BY segment
ORDER BY customer_count DESC;
```

**Expected results:**
Returns 2 rows: "AI/ML user" and "Non AI/ML user". The former is about 60% (per the generator config), and its avg_total_spend is typically higher, confirming the cross-sell value.

---

### Query 12: Churn-risk customer identification

**Business context:**
The Director of Customer Success builds a "churn risk report" at the end of each month. The report combines several signals (low health, declining usage, high ticket volume, upcoming renewal) to identify the customers most likely to churn.

**Category:** CTE + Joins
**Difficulty:** Advanced
**Business role:** CSM Manager

**Approach:**
This is the flagship multi-signal query. Three CTEs each handle one piece, all pre-aggregated to customer granularity: latest_health takes each customer's latest composite score, usage_trend takes the last 3 months of spend and average ticket count, and pending_renewals takes the nearest pending renewal date. They are LEFT JOINed back to customer (LEFT, because not every customer has all three signals, and INNER would drop people). A nested CASE then assigns Critical / High / Medium / Low based on thresholds. The WHERE does a coarse pre-filter (health < 70 or pending renewal) to shrink the result, and the ORDER BY repeats the same CASE logic so the riskiest customers float to the top.

```sql
WITH latest_health AS (
    -- per-customer latest score (correlated subquery; pick the customer's own MAX(score_date))
    SELECT hs.customer_id, hs.overall_score
    FROM health_score hs
    WHERE hs.score_date = (
        SELECT MAX(score_date) FROM health_score WHERE customer_id = hs.customer_id
    )
),
usage_trend AS (
    SELECT
        customer_id,
        SUM(total_spend) AS recent_spend,
        AVG(support_tickets_count) AS avg_tickets
    FROM usage_metrics
    WHERE month_year >= DATE('now', '-3 months', 'start of month')
    GROUP BY customer_id
),
pending_renewals AS (
    SELECT customer_id, MIN(contract_end_date) AS renewal_date
    FROM subscription
    WHERE status = 'pending_renewal'
    GROUP BY customer_id
)
SELECT
    c.id AS customer_id,
    c.company_name,
    t.name AS tier,
    csm.name AS csm_name,
    lh.overall_score AS health_score,
    ROUND(ut.recent_spend, 2) AS recent_3m_spend,
    ROUND(ut.avg_tickets, 1) AS avg_monthly_tickets,
    pr.renewal_date,
    CASE
        WHEN lh.overall_score < 50 AND ut.avg_tickets > 5 AND pr.renewal_date IS NOT NULL THEN 'Critical'
        WHEN lh.overall_score < 60 AND (ut.avg_tickets > 3 OR pr.renewal_date IS NOT NULL) THEN 'High'
        WHEN lh.overall_score < 70 THEN 'Medium'
        ELSE 'Low'
    END AS risk_level
FROM customer c
JOIN account_tier t ON c.account_tier_id = t.id
JOIN csm ON c.csm_id = csm.id
LEFT JOIN latest_health lh ON c.id = lh.customer_id
LEFT JOIN usage_trend ut ON c.id = ut.customer_id
LEFT JOIN pending_renewals pr ON c.id = pr.customer_id
WHERE c.is_active = 1
  AND (lh.overall_score < 70 OR pr.renewal_date IS NOT NULL)
ORDER BY
    CASE
        WHEN lh.overall_score < 50 AND ut.avg_tickets > 5 AND pr.renewal_date IS NOT NULL THEN 1
        WHEN lh.overall_score < 60 THEN 2
        ELSE 3
    END,
    lh.overall_score ASC;
```

**Expected results:**
Every active customer at risk of churn, sorted by risk level. Critical needs an immediate visit; High needs follow-up this week.

---

### Query 13: Customer distribution and spend by industry

**Business context:**
A market strategy analyst preparing the annual market report needs the industry distribution of customers. Which industries have the most customers? Which ones spend the most?

**Category:** Aggregation query
**Difficulty:** Basic
**Business role:** Analyst

**Approach:**
Structurally identical to Q5, just switching the grouping key from region to industry. After joining customer to usage_metrics, aggregate by industry, and use `COUNT(DISTINCT c.id)` for customer count to avoid amplification from multiple monthly rows. `ai_ml_pct` is `SUM(ai_ml_spend) / SUM(total_spend)` to give the industry-level AI penetration, with `NULLIF` on the denominator to guard zero. The window again restricts to the last 6 months.

```sql
SELECT
    c.industry,
    COUNT(DISTINCT c.id) AS customer_count,
    ROUND(SUM(um.total_spend), 2) AS total_spend_6m,
    ROUND(AVG(um.total_spend), 2) AS avg_monthly_spend_per_record,
    ROUND(SUM(um.ai_ml_spend) / NULLIF(SUM(um.total_spend), 0) * 100, 2) AS ai_ml_pct
FROM customer c
JOIN usage_metrics um ON c.id = um.customer_id
WHERE c.is_active = 1
  AND um.month_year >= DATE('now', '-6 months', 'start of month')
GROUP BY c.industry
ORDER BY total_spend_6m DESC;
```

**Expected results:**
Returns customer counts and spend totals per industry over the last 6 months. Technology and Financial Services usually top the spend list.

Business takeaway: The market strategy analyst uses this to figure out which industries NimbusScale has the most penetration in, and industries with a high ai_ml_pct become priority markets for AI product expansion.

---

### Query 14: Support tickets vs. health-score correlation

**Business context:**
The support ops manager wants to test the hypothesis that support ticket volume is inversely correlated with customer health. If the correlation is strong, ticket count can be folded into the health-score model.

**Category:** CTE + Aggregation
**Difficulty:** Intermediate
**Business role:** Analyst

**Approach:**
The goal is to validate "more tickets means lower health." First, recent_metrics computes each customer's average tickets over the last 3 months; latest_health picks each customer's latest composite score; the two CTEs each aggregate first and then JOIN, which prevents a cross fan-out between the multi-month usage rows and the multi-snapshot health rows. The outer layer buckets by ticket volume (0-2 / 2-5 / 5+) and computes average health per bucket. If the generator genuinely lets ticket volume drive support_score downward, average health should fall monotonically as the bucket goes up, and the hypothesis is confirmed in the data.

```sql
WITH recent_metrics AS (
    SELECT
        customer_id,
        AVG(support_tickets_count) AS avg_tickets
    FROM usage_metrics
    WHERE month_year >= DATE('now', '-3 months', 'start of month')
    GROUP BY customer_id
),
latest_health AS (
    SELECT hs.customer_id, hs.overall_score
    FROM health_score hs
    WHERE hs.score_date = (
        SELECT MAX(score_date) FROM health_score WHERE customer_id = hs.customer_id
    )
)
SELECT
    CASE
        WHEN rm.avg_tickets < 2 THEN '0-2 tickets'
        WHEN rm.avg_tickets < 5 THEN '2-5 tickets'
        ELSE '5+ tickets'
    END AS ticket_range,
    COUNT(*) AS customer_count,
    ROUND(AVG(lh.overall_score), 1) AS avg_health_score,
    MIN(lh.overall_score) AS min_health_score,
    MAX(lh.overall_score) AS max_health_score
FROM recent_metrics rm
JOIN latest_health lh ON rm.customer_id = lh.customer_id
GROUP BY ticket_range
ORDER BY avg_health_score DESC;
```

**Expected results:**
The "0-2 tickets" bucket has an average health of ~85+; "5+ tickets" sits around 55-60, confirming the hypothesis. The generator inversely drives each customer's `support_tickets_count` off the implicit health baseline, so the correlation is a real signal in the data, not a coincidence.

---

### Query 15: Expansion opportunity identification

**Business context:**
Each quarter, the sales director needs to identify customers with expansion potential: sustained usage growth, high health score, multi-service adoption, and recent positive interactions.

**Category:** CTE + Window function
**Difficulty:** Advanced
**Business role:** CSM Manager

**Approach:**
Four CTEs each grab one piece: usage_growth uses LAG to compute month-over-month per row, growth_rate averages the growth rate per customer (more robust to single-month noise), latest_health takes the latest score, and latest_metrics takes the latest month's service count and AI spend. The outer query JOINs everything and uses CASE on combined thresholds (e.g., health >= 80 and growth > 10%) to assign Hot / Warm / Potential, keeping only candidates with positive growth and health >= 65. Using the average growth rate rather than a single month avoids being thrown off by a one-month spike.

```sql
WITH usage_growth AS (
    SELECT
        customer_id,
        total_spend,
        LAG(total_spend) OVER (PARTITION BY customer_id ORDER BY month_year) AS prev_spend,
        month_year
    FROM usage_metrics
),
growth_rate AS (
    SELECT
        customer_id,
        AVG((total_spend - prev_spend) / NULLIF(prev_spend, 0)) AS avg_growth_rate
    FROM usage_growth
    WHERE prev_spend IS NOT NULL AND prev_spend > 0
    GROUP BY customer_id
),
latest_health AS (
    SELECT hs.customer_id, hs.overall_score
    FROM health_score hs
    WHERE hs.score_date = (
        SELECT MAX(score_date) FROM health_score WHERE customer_id = hs.customer_id
    )
),
latest_metrics AS (
    SELECT um.customer_id, um.active_services_count, um.ai_ml_spend
    FROM usage_metrics um
    WHERE um.month_year = (
        SELECT MAX(month_year) FROM usage_metrics WHERE customer_id = um.customer_id
    )
)
SELECT
    c.id AS customer_id,
    c.company_name,
    t.name AS tier,
    csm.name AS csm_name,
    lh.overall_score AS health_score,
    ROUND(gr.avg_growth_rate * 100, 2) AS avg_growth_pct,
    lm.active_services_count,
    ROUND(lm.ai_ml_spend, 2) AS ai_ml_spend,
    CASE
        WHEN lh.overall_score >= 80 AND gr.avg_growth_rate > 0.1 THEN 'Hot'
        WHEN lh.overall_score >= 70 AND gr.avg_growth_rate > 0.05 THEN 'Warm'
        ELSE 'Potential'
    END AS opportunity_tier
FROM customer c
JOIN account_tier t ON c.account_tier_id = t.id
JOIN csm ON c.csm_id = csm.id
JOIN growth_rate gr ON c.id = gr.customer_id
JOIN latest_health lh ON c.id = lh.customer_id
JOIN latest_metrics lm ON c.id = lm.customer_id
WHERE c.is_active = 1
  AND gr.avg_growth_rate > 0
  AND lh.overall_score >= 65
ORDER BY
    CASE
        WHEN lh.overall_score >= 80 AND gr.avg_growth_rate > 0.1 THEN 1
        WHEN lh.overall_score >= 70 AND gr.avg_growth_rate > 0.05 THEN 2
        ELSE 3
    END,
    gr.avg_growth_rate DESC
LIMIT 20;
```

**Expected results:**
Returns the customers with the most expansion potential, sorted by opportunity heat. `NULLIF` handles the first-month null; the `per-customer MAX` handles the latest-per-customer data.

---

### Query 16: CSM workload distribution

**Business context:**
The ops director needs to see, for workforce planning, the customer count, portfolio quality, and workload of each CSM. Each CSM has a tier_specialization, so the load by specialization can be evaluated.

**Category:** CTE + Joins
**Difficulty:** Intermediate
**Business role:** Operations

**Approach:**
Drive the query off the csm table with `LEFT JOIN customer ... AND c.is_active = 1`, so an active CSM with zero active customers still shows up (workforce planning needs to see idle people). The portfolio and task_summary CTEs each pre-aggregate to customer granularity, preventing a cross fan-out in the same JOIN between multi-month usage rows and multi-task csm_task rows, which would double-count portfolio spend. `WHERE csm.is_active = 1` filters out the 2 departed CSMs and returns 13 rows. Per-tier customer counts are computed with `SUM(CASE WHEN t.name = ...)`, the classic row-to-column pivot.

```sql
WITH portfolio AS (
    SELECT customer_id, SUM(total_spend) AS portfolio_spend
    FROM usage_metrics
    WHERE month_year >= DATE('now', '-6 months', 'start of month')
    GROUP BY customer_id
),
task_summary AS (
    SELECT customer_id, COUNT(*) AS open_tasks
    FROM csm_task
    WHERE status IN ('open', 'in_progress')
    GROUP BY customer_id
)
SELECT
    csm.name AS csm_name,
    csm.tier_specialization,
    COUNT(DISTINCT c.id) AS customer_count,
    SUM(CASE WHEN t.name = 'Enterprise' THEN 1 ELSE 0 END) AS enterprise_count,
    SUM(CASE WHEN t.name = 'Business' THEN 1 ELSE 0 END) AS business_count,
    SUM(CASE WHEN t.name = 'Pro' THEN 1 ELSE 0 END) AS pro_count,
    SUM(CASE WHEN t.name = 'Basic' THEN 1 ELSE 0 END) AS basic_count,
    ROUND(COALESCE(SUM(p.portfolio_spend), 0), 2) AS total_portfolio_spend_6m,
    COALESCE(SUM(ts.open_tasks), 0) AS open_tasks
FROM csm
LEFT JOIN customer c ON c.csm_id = csm.id AND c.is_active = 1
LEFT JOIN account_tier t ON c.account_tier_id = t.id
LEFT JOIN portfolio p ON c.id = p.customer_id
LEFT JOIN task_summary ts ON c.id = ts.customer_id
WHERE csm.is_active = 1
GROUP BY csm.id, csm.name, csm.tier_specialization
ORDER BY csm.tier_specialization, total_portfolio_spend_6m DESC;
```

**Expected results:**
One row per CSM with portfolio breakdown, 6-month portfolio spend, and current open tasks. An Enterprise CSM typically owns 4 to 7 high-value customers; an SMB CSM owns 10 to 13 Pro/Basic customers. The `portfolio` and `task_summary` CTEs pre-aggregate first, which avoids the usage × csm_task fan-out, so portfolio_spend does not get multiplied by the task count.

---

### Query 17: Upcoming contract expiration alerts

**Business context:**
Finance and legal need a weekly list of contracts expiring in the next 30/60/90 days so they can prep renewal paperwork and legal review.

**Category:** Date range query
**Difficulty:** Basic
**Business role:** Operations

**Approach:**
Join subscription to customer / csm / account_tier and filter contract_end_date inside the next 90 days, with status not in churned/expired. Use `JULIANDAY` subtraction for days remaining, then CASE to bucket into within 30 / 30-60 / 60-90 days of urgency. ORDER BY expiration date ascending puts the soonest expirations at the top. Contracts with `auto_renewal = FALSE` have no auto-renewal safety net, so they deserve extra attention.

```sql
SELECT
    c.company_name,
    t.name AS tier,
    csm.name AS csm_name,
    s.contract_end_date,
    JULIANDAY(s.contract_end_date) - JULIANDAY('now') AS days_remaining,
    CASE
        WHEN JULIANDAY(s.contract_end_date) - JULIANDAY('now') <= 30 THEN 'Within 30 days'
        WHEN JULIANDAY(s.contract_end_date) - JULIANDAY('now') <= 60 THEN '30-60 days'
        ELSE '60-90 days'
    END AS urgency,
    s.monthly_committed_spend,
    s.auto_renewal
FROM subscription s
JOIN customer c ON s.customer_id = c.id
JOIN csm ON c.csm_id = csm.id
JOIN account_tier t ON c.account_tier_id = t.id
WHERE s.contract_end_date BETWEEN DATE('now') AND DATE('now', '+90 days')
  AND s.status NOT IN ('churned', 'expired')
ORDER BY s.contract_end_date ASC;
```

**Expected results:**
Returns contracts expiring in the next 90 days, bucketed by urgency. Contracts with auto_renewal = FALSE need extra attention.

---

### Query 18: Customer sentiment trend analysis

**Business context:**
The customer experience manager wants to understand overall customer sentiment trends. Aggregating sentiment tags (positive/neutral/negative) on interactions reveals how satisfaction is moving.

**Category:** Aggregation + Date
**Difficulty:** Intermediate
**Business role:** Analyst

**Approach:**
For interaction_log, use `strftime('%Y-%m', interaction_date)` to bucket interactions by month, then use `SUM(CASE WHEN sentiment = ...)` for conditional counts, giving each month's positive / neutral / negative composition and percentages. SQLite has no native month-truncation function, so strftime is the standard approach. Order by month descending and limit to the last 6 months to make the trend (improving or worsening) easy to read.

```sql
SELECT
    strftime('%Y-%m', il.interaction_date) AS month,
    COUNT(*) AS total_interactions,
    SUM(CASE WHEN il.sentiment = 'positive' THEN 1 ELSE 0 END) AS positive,
    SUM(CASE WHEN il.sentiment = 'neutral' THEN 1 ELSE 0 END) AS neutral,
    SUM(CASE WHEN il.sentiment = 'negative' THEN 1 ELSE 0 END) AS negative,
    ROUND(SUM(CASE WHEN il.sentiment = 'positive' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) AS positive_pct,
    ROUND(SUM(CASE WHEN il.sentiment = 'negative' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) AS negative_pct
FROM interaction_log il
GROUP BY strftime('%Y-%m', il.interaction_date)
ORDER BY month DESC
LIMIT 6;
```

**Expected results:**
Returns the sentiment distribution for the last 6 months. A positive_pct of 40%+ is healthy.

Business takeaway: The customer experience manager watches the trend rather than any single month. If negative_pct climbs for several consecutive months, it indicates a systemic decline in satisfaction and should trigger a cross-team experience review.

---

### Query 19: Quarterly QBR completion status

**Business context:**
The VP of Customer Success requires every Enterprise and Business customer to have at least one QBR (Quarterly Business Review) per quarter. Operations needs to check QBR completion over the last 90 days.

**Category:** Joins + Date
**Difficulty:** Intermediate
**Business role:** Operations

**Approach:**
First, the CTE recent_qbrs aggregates interactions where `interaction_type.name = 'QBR Meeting'` in the last 90 days, by customer (count + last date). The outer query drives off customer with `LEFT JOIN` against this CTE: customers who have not done a QBR have qbr_count NULL, which COALESCE turns into 0 and labels as 'Not Scheduled'. LEFT JOIN is the soul of this query. Switching it to INNER would only leave customers who have done a QBR, missing exactly the "no QBR" customers we most need to chase. The scope is restricted to active Enterprise / Business customers.

```sql
-- Note: "last 90 days" approximates "this quarter" (SQLite quarter math is awkward; this demo uses the simplification)
WITH recent_qbrs AS (
    SELECT
        il.customer_id,
        COUNT(*) AS qbr_count,
        MAX(il.interaction_date) AS last_qbr_date
    FROM interaction_log il
    JOIN interaction_type it ON il.interaction_type_id = it.id
    WHERE it.name = 'QBR Meeting'
      AND il.interaction_date >= DATE('now', '-90 days')
    GROUP BY il.customer_id
)
SELECT
    c.company_name,
    t.name AS tier,
    csm.name AS csm_name,
    COALESCE(q.qbr_count, 0) AS qbr_last_90d,
    q.last_qbr_date,
    CASE
        WHEN q.qbr_count > 0 THEN 'Completed'
        ELSE 'Not Scheduled'
    END AS qbr_status
FROM customer c
JOIN account_tier t ON c.account_tier_id = t.id
JOIN csm ON c.csm_id = csm.id
LEFT JOIN recent_qbrs q ON c.id = q.customer_id
WHERE c.is_active = 1
  AND t.name IN ('Enterprise', 'Business')
ORDER BY
    CASE WHEN q.qbr_count > 0 THEN 1 ELSE 0 END,
    t.monthly_min_spend DESC;
```

**Expected results:**
Returns all active Enterprise/Business customers requiring a QBR, with completion status. Not Scheduled customers need to be scheduled immediately.

---

### Query 20: Customer 360 view

**Business context:**
Before a customer meeting, a CSM needs to quickly absorb the full picture: basics, spend trends, health, recent interactions, open tasks. The "one-page" customer snapshot.

**Category:** CTE + Multi-table joins
**Difficulty:** Advanced
**Business role:** CSM

**Approach:**
The one-page customer snapshot. Each of six dimensions gets its own CTE pre-aggregated to customer granularity: latest-month usage, 6-month usage trend, latest health, last-90-days interactions, open tasks, and active_sub (use SUM/MIN to roll up multiple contracts and avoid fan-out). The outer query `LEFT JOIN`s all of them onto customer, so any missing piece does not drop the row, just shows NULL for the missing fields. `WHERE c.id = 51` pins to a single customer; change the id to change the customer. This is the actual query behind the Customer 360 Agent.

```sql
WITH latest_usage AS (
    SELECT um.customer_id, um.total_spend AS latest_spend, um.compute_spend, um.storage_spend, um.ai_ml_spend, um.active_services_count
    FROM usage_metrics um
    WHERE um.month_year = (
        SELECT MAX(month_year) FROM usage_metrics WHERE customer_id = um.customer_id
    )
),
usage_trend AS (
    SELECT customer_id,
           AVG(total_spend) AS avg_6m_spend,
           SUM(total_spend) AS total_6m_spend
    FROM usage_metrics
    WHERE month_year >= DATE('now', '-6 months', 'start of month')
    GROUP BY customer_id
),
latest_health AS (
    SELECT hs.customer_id, hs.overall_score, hs.usage_score, hs.engagement_score, hs.support_score, hs.notes
    FROM health_score hs
    WHERE hs.score_date = (
        SELECT MAX(score_date) FROM health_score WHERE customer_id = hs.customer_id
    )
),
recent_interactions AS (
    SELECT customer_id, COUNT(*) AS interaction_count_90d, MAX(interaction_date) AS last_interaction
    FROM interaction_log
    WHERE interaction_date >= DATE('now', '-90 days')
    GROUP BY customer_id
),
open_tasks AS (
    SELECT customer_id, COUNT(*) AS open_task_count, MIN(due_date) AS nearest_due_date
    FROM csm_task
    WHERE status IN ('open', 'in_progress')
    GROUP BY customer_id
),
active_sub AS (
    -- Roll up all of the customer's active subscriptions: SUM the monthly committed spend, take MIN of contract end (prioritize the nearest expiration)
    SELECT customer_id,
           SUM(monthly_committed_spend) AS monthly_committed_spend,
           MIN(contract_end_date) AS contract_end_date,
           MAX(status) AS status
    FROM subscription
    WHERE status = 'active'
    GROUP BY customer_id
)
SELECT
    c.id AS customer_id,
    c.company_name,
    c.industry,
    c.employee_count,
    t.name AS tier,
    r.name AS primary_region,
    csm.name AS csm_name,
    c.created_at AS customer_since,
    asub.contract_end_date,
    asub.monthly_committed_spend,
    asub.status AS subscription_status,
    ROUND(lu.latest_spend, 2) AS latest_month_spend,
    ROUND(ut.avg_6m_spend, 2) AS avg_monthly_spend_6m,
    lu.active_services_count,
    ROUND(lu.ai_ml_spend, 2) AS ai_ml_spend,
    lh.overall_score AS health_score,
    lh.usage_score,
    lh.engagement_score,
    lh.support_score,
    lh.notes AS health_notes,
    COALESCE(ri.interaction_count_90d, 0) AS interactions_90d,
    ri.last_interaction,
    COALESCE(ot.open_task_count, 0) AS open_tasks,
    ot.nearest_due_date AS next_task_due
FROM customer c
JOIN account_tier t ON c.account_tier_id = t.id
JOIN region r ON c.primary_region_id = r.id
JOIN csm ON c.csm_id = csm.id
LEFT JOIN active_sub asub ON c.id = asub.customer_id
LEFT JOIN latest_usage lu ON c.id = lu.customer_id
LEFT JOIN usage_trend ut ON c.id = ut.customer_id
LEFT JOIN latest_health lh ON c.id = lh.customer_id
LEFT JOIN recent_interactions ri ON c.id = ri.customer_id
LEFT JOIN open_tasks ot ON c.id = ot.customer_id
WHERE c.id = 51  -- Replace with the target customer ID (example: an Enterprise customer)
LIMIT 1;
```

**Expected results:**
Returns the full picture for the specified customer (a single row, because active_sub is already pre-aggregated via a subquery). A CSM can grasp the customer state in 30 seconds.

---

## 7. Query Category Summary

| Category | Count | Query numbers |
|----------|-------|---------------|
| Aggregation queries | 5 | 1, 6, 11, 13, 14 |
| Join operations | 5 | 3, 5, 9, 17, 19 |
| Window functions | 4 | 2, 4, 7, 15 |
| Date/time analysis | 3 | 10, 17, 18 |
| CTE composite queries | 7 | 8, 11, 12, 14, 15, 16, 20 |

---

## 8. Business Role Coverage

| Role | Count | Query numbers |
|------|-------|---------------|
| Executive / C-level | 3 | 1, 5, 11 |
| CSM Manager | 5 | 2, 3, 7, 12, 15 |
| Analyst | 5 | 4, 10, 13, 14, 18 |
| Operations | 5 | 6, 9, 16, 17, 19 |
| Finance | 1 | 8 |
| CSM | 1 | 20 |

---

## 9. Difficulty Distribution

| Difficulty | Count | Query numbers |
|------------|-------|---------------|
| Basic | 6 | 1, 6, 9, 11, 13, 17 |
| Intermediate | 9 | 3, 4, 5, 8, 10, 14, 16, 18, 19 |
| Advanced | 5 | 2, 7, 12, 15, 20 |

---

## 10. Notes

- All queries use SQLite 3.x syntax
- Date functions (JULIANDAY, strftime) are SQLite-specific; substitute equivalents on other databases
- The customer IDs in Q4 and Q20 can be replaced with any real target
- Query 11 tags each row's segment in the CTE so the outer GROUP BY can split into two cohorts directly
- Queries 8 / 16 / 20 pre-aggregate each side in a CTE to avoid the subscription / csm_task fan-out
- Queries 3 / 12 / 14 / 15 / 20 all use per-customer MAX (correlated subquery) for the latest score, so they do not miss rows even when different customers have different latest score dates
