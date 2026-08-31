# Property & Casualty — Commercial Underwriting SQL Query Reference

> Companion documents: business background `01-property_casualty_commercial_underwriting_high_business_context.md`, data structure `02-property_casualty_commercial_underwriting_high_er_document.md`
> All queries are compatible with SQLite 3.x. Reference "today" (REFERENCE_DATE) = `2026-06-21`
> Database file: `property_casualty_commercial_underwriting_high.sqlite`

## Overview

This document provides **50 SQL queries** designed to comprehensively cover the InsightUnderwriter AI Agent's data needs for renewal decisions, claims analysis, risk identification, and similar scenarios.

Each query comes with a **business background** section: **who would ask the question, in what circumstances, and what decision the answer drives**. Even readers without an insurance background can use this context to understand the core operating logic of the insurance business.

Following the BI blueprint guidance in Section 15 of the ER document, queries fall into two categories:

| Category | Count | Style | Use |
|----------|-------|-------|-----|
| **Dashboard-style** (D1–D15) | 15 (30%) | Snapshot, aggregation-heavy, fixed metrics | Each backs one L2/L3 dashboard control |
| **Business-question-style** (B1–B35) | 35 (70%) | Varied, exploratory | Each answers one standalone ad-hoc question |

## How to Use This Document

**Target reader:** This document is written for **an intern who has just finished reading the business context and ER documents, and is about to be sent off by the manager to run these queries**. If you still can't articulate what Loss Ratio, Reserve, Broker, or Underwriter mean, please go back to `01-..._business_context.md` (business background + glossary + metric formulas) and `02-..._er_document.md` (schema + field meanings), then come back.

**The five-part structure of each query** — each query is organized into the five parts below, read them in order:

1. **Business background** — who's asking, why they're asking now, what decision the answer drives. Understand the "why" first, then look at the "how".
2. **Category / Difficulty / Role** — the SQL techniques used, the difficulty level, and which role in the company actually uses this query.
3. **Approach** — before looking at the SQL, understand which tables to touch, how the joins are built (why LEFT instead of INNER), the granularity of the aggregation, why a CTE / window function is used, and what traps exist (fan-out / double counting / NULL semantics). **This part is the teaching focus; once you understand it, reading the SQL becomes much easier.**
4. **SQL code** — runnable as-is against the SQLite database.
5. **Expected result + business takeaway** — how many rows and columns, what each column means, what magnitude the key numbers should land at, and **what the analyst should do next** after getting the result. Producing a number is the start of analysis, not the end.

**REFERENCE_DATE convention:** The dataset is anchored to a fixed "today" = `2026-06-21`. Every query involving "days since today" or "last N years" uses a **literal date** (e.g., `'2026-06-21'` or `DATE('2026-06-21', '-12 months')`), and **never `DATE('now')`**, so results stay reproducible and match the expectations in this document regardless of when you run it.

**Every query maps to a business question:** At the end of the document, there's a "business question → query" cross-reference. Every query traces back to one of the 5 business questions listed in Section 5 of the business context document (is risk pricing accurate; who should we raise prices on / decline / keep; are renewal decisions accurate; are there fraud / out-of-control signals in claims; payment and external risk early-warning).

**SQL is meant to be read and studied, not just executed:** The same business question often has multiple ways to be written. This document picks the form **that would actually be used in production and that avoids common traps (e.g., policy×claim fan-out double-counting premium)**. When you see `> Fix the fan-out` / `> Convention note` / `> SQLite dialect tip` callouts, read them carefully — those are real-project pitfalls.

## Query Index

### Dashboard-style (D1–D15)

| # | Title | Dashboard | Role | Category | Difficulty |
|---|-------|-----------|------|----------|------------|
| D1 | Monthly trend of company-level Loss Ratio | CFO quarterly P&L | CFO/CEO | CTE + time bucketing | Intermediate |
| D2 | Renewal retention and churn analysis | Renewal health | VP Underwriting | Pivot aggregation | Intermediate |
| D3 | Broker channel contribution analysis | Channel contribution | Director of Distribution | Multi-table JOIN + aggregation | Intermediate |
| D4 | Renewal expiry calendar (next 60 days) | Renewal expiry | Underwriting Manager | Date filter | Basic |
| D5 | High-risk claim early warning (repeated reserve increases) | Claims warning | Claims Manager | Aggregation + HAVING | Intermediate |
| D6 | Underwriter monthly quota attainment | Underwriter productivity | Underwriting Manager | Aggregation + JOIN | Intermediate |
| D7 | Payment-delinquent client warning | Finance warning | Finance Manager | Aggregation + JOIN | Intermediate |
| D8 | Site inspection remediation overdue list | Risk control tracking | Risk Control Manager | Date arithmetic | Basic |
| D9 | Fraud signal heat map (by company) | Anti-fraud monitor | Anti-Fraud Analyst | RAG aggregation | Intermediate |
| D10 | Composite renewal-decision assistant (single company 360°) | Renewal decision assistant | Underwriter | CTE multi-table JOIN | Advanced |
| D11 | Industry-benchmark comparison dashboard | Industry benchmarking | Underwriting Manager | JOIN + aggregation | Intermediate |
| D12 | Regulatory penalty distribution (by agency + year) | Compliance monitor | Director of Compliance | Pivot aggregation | Intermediate |
| D13 | Tracking of credit-downgraded companies | Rating monitor | Director of Finance | Window function | Advanced |
| D14 | Premium slippage alert (≥ 3 endorsements within a year) | Premium monitor | Underwriting Manager | Aggregation + HAVING | Intermediate |
| D15 | Adjuster open caseload | Claims productivity | Claims Manager | Aggregation + JOIN | Basic |

### Business-question-style (B1–B35)

| # | Title | Subject Area | Role | Category | Difficulty |
|---|-------|--------------|------|----------|------------|
| B1 | Client basic profile + locations overview | A Customer Profile | Underwriter | JOIN | Basic |
| B2 | Annual financial-health trend (LAG year-over-year) | A Customer Profile | Financial Analyst | Window function | Intermediate |
| B3 | Credit rating change history timeline | A Customer Profile | Financial Analyst | Window function | Intermediate |
| B4 | High debt-ratio company list (Top 50) | A Customer Profile | Risk Control Manager | Aggregation + sort | Basic |
| B5 | Companies with dual signals: financial deterioration + high loss ratio | A Customer Profile | Underwriting Manager | CTE + multi-table | Advanced |
| B6 | Top premium clients ranking (Top 25) | B Policy & Underwriting | CEO/CRO | Aggregation + sort | Basic |
| B7 | Premium share by line of business | B Policy & Underwriting | VP Underwriting | Aggregation | Basic |
| B8 | Policy endorsement frequency distribution | B Policy & Underwriting | Underwriting Manager | Aggregation + bucketing | Basic |
| B9 | Full premium-history trace for a single policy | B Policy & Underwriting | Underwriter | Window function | Intermediate |
| B10 | Renewal-decision accuracy (decision vs. subsequent loss ratio) | B Policy & Underwriting | Underwriting Manager | CTE + multi-table | Advanced |
| B11 | Risk score vs. actual loss ratio correlation | B Policy & Underwriting | Actuary/Analyst | CTE + bucketing | Advanced |
| B12 | Direct vs. broker channel quality comparison | B Policy & Underwriting | Director of Distribution | Aggregation + comparison | Intermediate |
| B13 | 3-year cumulative loss ratio per company | C Claims | Underwriter | Aggregation + JOIN | Basic |
| B14 | Average close days (by line) | C Claims | Claims Manager | Date arithmetic + aggregation | Intermediate |
| B15 | Top 30 large claims | C Claims | Claims Director | Sort + JOIN | Basic |
| B16 | Incident-to-report lag analysis (moral hazard signal) | C Claims | Anti-Fraud Analyst | Date arithmetic + bucketing | Intermediate |
| B17 | Dangerous claims with repeated reserve increases | C Claims | Claims Manager | Aggregation + window | Advanced |
| B18 | Claim status distribution (per company) | C Claims | Underwriter | Pivot aggregation | Intermediate |
| B19 | Declined-claims analysis | C Claims | Claims Director | Aggregation + JOIN | Intermediate |
| B20 | Cross-year loss-ratio trend per company (Window) | C Claims | Underwriting Manager | Window function | Advanced |
| B21 | Per-company fraud signal stats (RAG) | D Unstructured | Anti-Fraud Analyst | Aggregation + JOIN | Intermediate |
| B22 | Loss-amount comparison: claims with vs. without attorney involvement | D Unstructured | Legal | Subquery + comparison | Intermediate |
| B23 | signal_tag × claim_type matrix | D Unstructured | Risk Analyst | Pivot | Intermediate |
| B24 | Hazard remediation overdue list | D Unstructured | Risk Control Manager | Date arithmetic + CASE | Intermediate |
| B25 | Communication author activity (XOR pattern) | D Unstructured | Data Analyst | XOR + aggregation | Intermediate |
| B26 | Client payment-behavior grading buckets | E Payment | Finance Manager | CASE + aggregation | Intermediate |
| B27 | Severely late clients list + in-force premium | E Payment | Credit Risk | JOIN + aggregation | Intermediate |
| B28 | Accounts-receivable aging analysis | E Payment | Finance Manager | Date bucketing | Intermediate |
| B29 | Payment behavior vs. loss-ratio correlation | E Payment | RevOps | CTE + aggregation | Advanced |
| B30 | Industry risk tier vs. average loss ratio | F External | Actuary | JOIN | Basic |
| B31 | Regulatory penalty density ranking (per company) | F External | Compliance Manager | Aggregation + sort | Basic |
| B32 | Subsequent loss ratio for credit-downgraded companies | F External | RevOps | CTE + multi-table | Advanced |
| B33 | Policy portfolio of high-fine companies | F External | Compliance Manager | JOIN + aggregation | Intermediate |
| B34 | Top N companies with largest deviation from industry benchmark | F External | VP Underwriting | JOIN + sort | Intermediate |
| B35 | Multi-dimensional composite risk score ranking | F External | Underwriting Manager | Big composite CTE | Advanced |

---

## Dimension Glossary

The word "risk" appears throughout the insurance business; the queries below distinguish **4 different dimensions** of risk:

| Dimension | Source Field | Cardinality | Meaning |
|-----------|--------------|-------------|---------|
| `company.risk_tier` | Company table | 4 (Low/Medium/High/Very High) | Company-level coarse classification by industry and size |
| `company_location.location_risk_level` | Location table | 3 (Low/Medium/High) | Physical risk grade of a single location |
| `risk_assessment.risk_score` | Assessment table | 0–100 | Underwriter's fine-grained score for a single policy |
| `industry_benchmark.avg_loss_ratio` | Benchmark table | industry × year | Industry-average loss ratio, for benchmarking |

Rule of thumb: each query focuses on only one dimension to avoid confusion.

---

# Dashboard-style queries (D1–D15)

Each query drives one dashboard control: aggregation-heavy, snapshot-oriented.

---

## D1: Monthly trend of company-level Loss Ratio

**Dashboard:** CFO quarterly P&L

**Business background:** The CFO/CEO checks once a month: "Is our underwriting business making money overall?" The single most important metric is **Loss Ratio (paid losses ÷ premium)**. Once this rate exceeds 70% for 3 consecutive months, it's an alert (because adding the 30% expense ratio puts the Combined Ratio over the 100% breakeven line). This query outputs Loss Ratio aggregated by month so you can spot inflection points.

**Category:** CTE + time bucketing
**Difficulty:** Intermediate
**Role:** CFO / CEO

**Approach:** This one aggregates monthly premium (`invoice` by `invoice_date`) and monthly paid losses (`claim` by `incident_date`) separately at the "year-month" grain, then divides. Note that the two numbers come from two unrelated tables on two different date conventions (premium uses invoice date; losses use incident date), so you absolutely cannot join them onto the same row and compute — otherwise premium gets multiplied by the number of claim rows (fan-out). The correct approach is two CTEs that each GROUP BY month independently, then a `LEFT JOIN` using premium months as the base to attach losses — LEFT JOIN rather than INNER because some months may have no losses, but those months still need to keep the premium in the denominator, otherwise that month's loss_ratio would vanish. Each output row represents one month. SQLite uses `STRFTIME('%Y-%m', ...)` to extract the month, `NULLIF(denominator,0)` to guard against divide-by-zero, and `COALESCE` to convert NULL (no losses) into 0.

```sql
WITH monthly_premium AS (
  SELECT STRFTIME('%Y-%m', invoice_date) AS month,
         SUM(amount_due_cny) AS premium_billed
  FROM invoice
  WHERE invoice_date >= '2024-06-01'   -- start of data window (HISTORY_START = TODAY-730 = 2024-06-21)
  GROUP BY 1
),
monthly_loss AS (
  SELECT STRFTIME('%Y-%m', incident_date) AS month,
         SUM(paid_amount_cny) AS losses_paid,
         COUNT(*) AS claim_count
  FROM claim
  WHERE incident_date >= '2024-06-01' AND paid_amount_cny > 0
  GROUP BY 1
)
SELECT mp.month,
       ROUND(mp.premium_billed, 0) AS premium_billed_cny,
       ROUND(COALESCE(ml.losses_paid, 0), 0) AS losses_paid_cny,
       COALESCE(ml.claim_count, 0) AS claim_count,
       ROUND(COALESCE(ml.losses_paid, 0) * 1.0 / NULLIF(mp.premium_billed, 0), 3) AS loss_ratio
FROM monthly_premium mp
LEFT JOIN monthly_loss ml ON ml.month = mp.month
ORDER BY mp.month;
```

**Expected result:** About 25 rows (covering 2024-06 through 2026-06; since the data starts at 2024-06-21, it's not a full 30 months). Each month's loss_ratio typically swings in 0.2–0.7 (this company's loss ratio is generally healthy on paper). If a month suddenly jumps to 0.85+, drill down to see which industry or which large clients had losses.

---

## D2: Renewal retention and churn analysis

**Dashboard:** Renewal health

**Business background:** Renewal season (every June / December) is the most stressful time for the VP of Underwriting. **A renewal rate < 60% means brokers are moving clients to competitors**, and next year's premium base will shrink. This query outputs the distribution of renewal decisions over the past 12 months: Renew / Conditional Renew / Decline, along with the average premium change, reflecting the underwriting department's retention health.

**Category:** Pivot aggregation
**Difficulty:** Intermediate
**Role:** VP Underwriting

**Approach:** This one only touches a single table, `renewal_decision` — all needed fields (decision, premium_change_pct, decision_date) are already there, no dimension table needs to be joined, so one GROUP BY decision suffices. Each output row is one renewal decision type (Renew / Conditional Renew / Decline). The trick isn't the join but the "percentage" column: to compute each decision's share of the total, the denominator is the total count of decisions. This uses the window function `SUM(COUNT(*)) OVER ()` — COUNT first computes the per-decision count within each group, then the outer `SUM(...) OVER ()` sums all groups into a total, computing pct in one pass without a subquery for the total. `decision_date >= DATE('2026-06-21', '-12 months')` anchors the window to "12 months back from today" to keep results reproducible.

```sql
SELECT decision,
       COUNT(*) AS decision_count,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS pct,
       ROUND(AVG(premium_change_pct), 2) AS avg_premium_change_pct,
       ROUND(MIN(premium_change_pct), 2) AS min_change,
       ROUND(MAX(premium_change_pct), 2) AS max_change
FROM renewal_decision
WHERE decision_date >= DATE('2026-06-21', '-12 months')
GROUP BY decision
ORDER BY decision_count DESC;
```

**Expected result:** 3 rows. Design target: Renew ~65% / Conditional Renew ~25% / Decline ~10%. "Renew" averages 5–10% price increases; "Conditional Renew" typically 20–30%. If "Decline" exceeds 15%, that's an alert (client quality is declining overall).

---

## D3: Broker channel contribution analysis

**Dashboard:** Channel contribution

**Business background:** 80% of commercial insurance comes through the broker channel. The Director of Distribution wants to know **which brokers send us lots of good business**, and which only send "junk" (high-loss-ratio business). This query rolls up in-force premium per broker plus the actual loss ratio of business they brought in, used for annual broker tiering / commission adjustments.

**Category:** Multi-table JOIN + aggregation
**Difficulty:** Intermediate
**Role:** Director of Distribution

**Approach:** The classic trap with broker-level loss ratio is directly joining `broker → policy → claim` and then `SUM(premium)`: a policy with N claims has its `current_annual_premium_cny` accumulated N times (in practice inflating premium by ~56%), making the broker_loss_ratio denominator artificially high and the metric systematically understated. The correct approach is to split premium and losses into two independent CTEs computed separately — `broker_premium` aggregates premium per broker using `COUNT(DISTINCT policy_id)` and `SUM(premium)` to ensure each policy is counted once; `broker_claims` independently joins claim per broker and aggregates paid losses. Finally `broker JOIN broker_premium` (only show brokers with policies) plus `LEFT JOIN broker_claims` (brokers with no losses should record 0 rather than be dropped), with `COALESCE` filling NULL to 0. Each output row represents one broker. `broker_id IS NOT NULL` excludes direct-written policies (which have no broker).

```sql
WITH broker_premium AS (   -- first aggregate premium per broker, each policy counted only once
  SELECT p.broker_id,
         COUNT(DISTINCT p.policy_id) AS policy_count,
         SUM(p.current_annual_premium_cny) AS total_premium_cny
  FROM policy p
  WHERE p.broker_id IS NOT NULL
  GROUP BY p.broker_id
),
broker_claims AS (         -- independently aggregate paid losses per broker; avoids premium being inflated by claim row count
  SELECT p.broker_id,
         SUM(cl.paid_amount_cny) AS total_paid_claims_cny
  FROM policy p
  JOIN claim cl ON cl.policy_id = p.policy_id
  WHERE p.broker_id IS NOT NULL
  GROUP BY p.broker_id
)
SELECT b.broker_id, b.broker_firm, b.tier,
       bp.policy_count,
       ROUND(bp.total_premium_cny, 0) AS total_premium_cny,
       ROUND(COALESCE(bc.total_paid_claims_cny, 0), 0) AS total_paid_claims_cny,
       ROUND(COALESCE(bc.total_paid_claims_cny, 0) * 1.0
             / NULLIF(bp.total_premium_cny, 0), 3) AS broker_loss_ratio,
       b.commission_rate,
       ROUND(bp.total_premium_cny * b.commission_rate, 0) AS commission_payout_cny
FROM broker b
JOIN broker_premium bp ON bp.broker_id = b.broker_id
LEFT JOIN broker_claims bc ON bc.broker_id = b.broker_id
WHERE b.is_active = 1
ORDER BY broker_loss_ratio DESC;
```

> **Fix the fan-out:** The naive form `broker LEFT JOIN policy LEFT JOIN claim` followed by `SUM(p.current_annual_premium_cny)`
> **multiplies each policy's premium by N** (where N = its claim count) — in practice inflating premium by about 56% —
> blowing up the loss-ratio denominator and systematically understating the ratio.
> Here we first aggregate premium per policy in a subquery, then independently subquery the losses, eliminating double-counting entirely.

**Expected result:** ~55 rows. Sorted by broker_loss_ratio DESC, brokers at the top are the "junk" ones (business from this channel has the worst loss ratio). Combined with commission payout for ROI: brokers with high commission and high loss ratio are ones we're "paying to lose money on".

---

## D4: Renewal expiry calendar (next 60 days)

**Dashboard:** Renewal expiry

**Business background:** The underwriting manager needs to know **30–60 days in advance** which policies are about to expire, so the team can begin pre-screening. Missing the renewal on a large policy and the client may be poached by a competitor. This query lists every in-force policy expiring in the next 60 days, sorted ASC by expiry date, along with client name, premium size, and current underwriter.

**Category:** Date filter
**Difficulty:** Basic
**Role:** Underwriting Manager

**Approach:** This is a pure detail query — no aggregation, each output row represents a policy about to expire. Three tables: `policy` provides the expiry date and premium, `company` provides the client name and industry (INNER JOIN here because every policy belongs to exactly one company), `underwriter` provides the current underwriter's name. The window uses `expiration_date BETWEEN '2026-06-21' AND DATE('2026-06-21', '+60 days')` for the next 60 days; `status = '有效'` (In-force) excludes already-terminated policies. `days_to_expire` uses `JULIANDAY(expiry) - JULIANDAY('today')` to compute the day difference — this is SQLite's standard idiom for date intervals, returning a floating-point days value. Sorting by `expiration_date ASC` puts the soonest-expiring at the top so the manager can prioritize.

```sql
SELECT p.policy_id, p.policy_number,
       c.company_name, c.industry, c.risk_tier,
       p.policy_type,
       p.expiration_date,
       JULIANDAY(p.expiration_date) - JULIANDAY('2026-06-21') AS days_to_expire,
       ROUND(p.current_annual_premium_cny, 0) AS annual_premium_cny,
       u.full_name AS underwriter_name,
       u.role AS underwriter_role
FROM policy p
JOIN company c ON c.company_id = p.company_id
JOIN underwriter u ON u.underwriter_id = p.underwriter_id
WHERE p.status = '有效'
  AND p.expiration_date BETWEEN '2026-06-21' AND DATE('2026-06-21', '+60 days')
ORDER BY p.expiration_date ASC;
```

**Expected result:** About 250–350 rows (policies expiring within 60 days). Focus on high-premium policies with days_to_expire < 14 (annual_premium > CNY 300K). These are the priority items the renewal manager has to "personally watch".

---

## D5: High-risk claim early warning (repeated reserve increases)

**Dashboard:** Claims warning

**Business background:** Repeated upward revisions of the reserve are **the strongest signal that things are going badly** — the case is getting worse, the other side is escalating to litigation, medical costs are exploding. The claims manager checks this dashboard daily, pulling out cases where the reserve has been adjusted ≥ 3 times for manual review, deciding whether to add reinsurance, file a preemptive suit, or proactively settle.

**Category:** Aggregation + HAVING
**Difficulty:** Intermediate
**Role:** Claims Manager

**Approach:** This one starts from `claim`, follows `policy → company` to get the client name, joins `claim_adjuster` for the adjuster name, then joins `claim_reserve` to see each claim's reserve adjustments. Fan-out here is intentional: a single claim has multiple rows in `claim_reserve` (one per adjustment), and that's exactly what we want to count. So GROUP BY claim, then `COUNT(cr.reserve_id)` to count adjustments, and `MIN/MAX(reserve_amount_cny)` to grab the initial and latest reserve and compute growth. Definition matters: `reserve_adjustment_count` counts "adjustment rows (including initial set-up)" — the threshold `>= 3` is equivalent to at least 2 upward revisions after the initial setting; it's counting adjustments, not strictly "upward revisions". HAVING must come after GROUP BY to filter on aggregated results (WHERE can't). `status IN ('已立案','调查中','定损中')` limits to "open" cases — paid claims no longer need reserve adjustments and are excluded. Each output row represents one high-risk claim.

```sql
SELECT cl.claim_id, cl.claim_number,
       c.company_name, cl.claim_type, cl.status,
       cl.incident_date,
       COUNT(cr.reserve_id) AS reserve_adjustment_count,
       ROUND(MIN(cr.reserve_amount_cny), 0) AS initial_reserve_cny,
       ROUND(MAX(cr.reserve_amount_cny), 0) AS current_reserve_cny,
       ROUND(MAX(cr.reserve_amount_cny) - MIN(cr.reserve_amount_cny), 0) AS reserve_growth_cny,
       a.full_name AS adjuster_name
FROM claim cl
JOIN policy p ON p.policy_id = cl.policy_id
JOIN company c ON c.company_id = p.company_id
JOIN claim_adjuster a ON a.adjuster_id = cl.adjuster_id
JOIN claim_reserve cr ON cr.claim_id = cl.claim_id
WHERE cl.status IN ('已立案', '调查中', '定损中')   -- unified "open/active" definition (see KPI dictionary 16.3); Paid ≈ awaiting close, no need for more reserves, so excluded
GROUP BY cl.claim_id, cl.claim_number, c.company_name, cl.claim_type,
         cl.status, cl.incident_date, a.full_name
HAVING reserve_adjustment_count >= 3
ORDER BY reserve_growth_cny DESC
LIMIT 30;
```

> **Convention note:** `reserve_adjustment_count = COUNT(cr.reserve_id)` is the **count of reserve adjustment rows (including initial set-up)** for that claim,
> and the threshold `>= 3` equates to "at least 2 more adjustments after the initial setting" (consistent with ER 15.2). It counts adjustments, not strictly "upward revisions";
> if you only want to look at amount growth trajectories see B17 (`latest/initial > 1.5`).

**Expected result:** Usually 20–30 rows. Cases with reserve_growth_cny > CNY 500K are **must-intervene** red signals (the reserve has grown by 500K+, meaning the initial estimate was off by at least 500K).

---

## D6: Underwriter monthly quota attainment

**Dashboard:** Underwriter productivity

**Business background:** The underwriting manager checks monthly: **of my 35 underwriters, who hit their quota and who's seriously behind**. Falling behind might be due to disengagement, or due to being assigned a hard-to-write large account (which takes longer). End-of-month, anyone under 80% attainment needs a conversation or workload adjustment.

**Category:** Aggregation + JOIN
**Difficulty:** Intermediate
**Role:** Underwriting Manager

**Approach:** This one uses `underwriter` as the main table and `LEFT JOIN policy` to count each underwriter's bound policies for the month. Using LEFT JOIN rather than INNER is critical: an underwriter who didn't bind a single policy this month still needs to appear in the list (attainment 0%); INNER would erase them entirely. The trickiest part is what "this month" means: you can't hard-code `'2026-06'`, because all policies have `bound_at = effective_date - 7~30 days` and `effective_date ≤ TODAY-30`, so the most recent bind month is actually 2026-05, and hard-coding June would make the whole dashboard show all zeros. So we use a subquery `STRFTIME('%Y-%m', MAX(bound_at))` to automatically pick "the most recent month with bindings", and put this month condition in the LEFT JOIN's ON, not WHERE (putting it in WHERE would erroneously drop people who didn't bind anything). Each output row represents one underwriter. Attainment uses `NULLIF(quota,0)` to guard against divide-by-zero; sorting uses `col IS NULL, col DESC` to emulate `NULLS LAST` for older SQLite versions.

```sql
SELECT u.underwriter_id, u.full_name, u.role, u.region,
       u.monthly_quota_policies,
       COUNT(p.policy_id) AS bound_policy_count_this_month,
       ROUND(100.0 * COUNT(p.policy_id) /
             NULLIF(u.monthly_quota_policies, 0), 1) AS quota_attainment_pct,
       ROUND(SUM(p.current_annual_premium_cny), 0) AS premium_bound_this_month_cny
FROM underwriter u
LEFT JOIN policy p ON p.underwriter_id = u.underwriter_id
                  AND STRFTIME('%Y-%m', p.bound_at) =
                      (SELECT STRFTIME('%Y-%m', MAX(bound_at)) FROM policy)
WHERE u.is_active = 1 AND u.role <> '核保经理'
GROUP BY u.underwriter_id, u.full_name, u.role, u.region, u.monthly_quota_policies
ORDER BY quota_attainment_pct IS NULL, quota_attainment_pct DESC;
```

> **About what "this month" picks up:** the naive form hard-codes `'2026-06'`, but every policy has `bound_at = effective_date - 7~30 days`,
> and `effective_date ≤ TODAY-30`, so the latest bind month is **2026-05**; hard-coding 2026-06 would make the dashboard **all zeros**.
> The fix here uses subquery `MAX(bound_at)` to auto-pick "the latest month that has bindings", and remains valid as the data evolves.
> Sorting uses `col IS NULL, col DESC` to emulate `NULLS LAST` (per the dialect notes at the end, compatible with older SQLite versions).

**Expected result:** 35 rows (5 managers excluded). Attainment > 100% is excellent, 80–100% normal, < 80% needs attention. Senior underwriters have a quota of 8 policies/month, junior underwriters 3/month — attainment is normalized for comparison. Mid-month snapshots (e.g., today is day 21 of the next month) commonly show low attainment, which is normal.

---

## D7: Payment-delinquent client warning

**Dashboard:** Finance warning

**Business background:** Clients more than 30 days overdue have **a higher probability of eventually defaulting**. The finance manager needs to look at the "priority delinquency list" daily for targeted collections. These clients also affect renewal decisions (underwriters check this list at renewal).

**Category:** Aggregation + JOIN
**Difficulty:** Intermediate
**Role:** Finance Manager

**Approach:** This one rolls up overdue invoices per company; each output row is a company with overdue receivables. The chain is `company → policy → invoice`, and INNER JOIN here is intentional to drop companies without overdue invoices — we only care about debtors. `WHERE i.status = '逾期' AND i.due_date < '2026-06-21'` narrows to truly overdue invoices, then GROUP BY company. Days late uses `JULIANDAY('2026-06-21') - JULIANDAY(due_date)`; `MAX(...)` grabs the worst invoice (longest unpaid), `AVG(...)` the average lateness. Note `max_days_overdue > 30` filters on the aggregated MAX value, so it must go in HAVING not WHERE. Sort by total overdue DESC so the finance manager focuses on the biggest debtors first.

```sql
SELECT c.company_id, c.company_name, c.industry, c.risk_tier,
       COUNT(i.invoice_id) AS overdue_invoice_count,
       ROUND(SUM(i.amount_due_cny), 0) AS overdue_amount_cny,
       MAX(JULIANDAY('2026-06-21') - JULIANDAY(i.due_date)) AS max_days_overdue,
       ROUND(AVG(JULIANDAY('2026-06-21') - JULIANDAY(i.due_date)), 1) AS avg_days_overdue
FROM company c
JOIN policy p ON p.company_id = c.company_id
JOIN invoice i ON i.policy_id = p.policy_id
WHERE i.status = '逾期'
  AND i.due_date < '2026-06-21'
GROUP BY c.company_id, c.company_name, c.industry, c.risk_tier
HAVING max_days_overdue > 30
ORDER BY overdue_amount_cny DESC
LIMIT 50;
```

**Expected result:** Usually 30–50 rows. Clients with max_days_overdue > 90 will basically need to go through legal collection. Combined with the `c.risk_tier='High Risk'` label, bump up the priority.

---

## D8: Site inspection remediation overdue list

**Dashboard:** Risk control tracking

**Business background:** After a site inspection finds hazards, the client must complete remediation within an agreed timeframe (typically 60–90 days). **Locations that miss the remediation deadline are usually subject to conditional renewal** or decline at renewal. This query identifies locations where hazards were found > 90 days ago and remediation is still "Not Started".

**Category:** Date arithmetic
**Difficulty:** Basic
**Role:** Risk Control Manager

**Approach:** This one starts from `site_inspection`, joins `company_location` for the location name and city, then joins `company` for the company name; each output row represents one inspection record that found hazards but isn't yet fully remediated. No aggregation; the core logic is all in the `CASE`: use `JULIANDAY('2026-06-21') - JULIANDAY(inspection_date)` for days since inspection, then bucket into urgency_level based on "Not Started over 90 days" / "In Progress over 180 days". The WHERE clause's `hazards_identified IS NOT NULL` is a SQLite NULL-semantics point — only show records where hazards were actually found, while NULL means no hazards, so you can't use `= ''` or similar to filter; `remediation_status IN ('未开始','进行中')` excludes already-completed remediation. Sorted DESC by days since, putting the oldest delays first.

```sql
SELECT c.company_name, cl.location_name, cl.city, cl.province,
       si.inspection_date,
       si.hazards_identified,
       si.remediation_status,
       JULIANDAY('2026-06-21') - JULIANDAY(si.inspection_date) AS days_since_inspection,
       CASE
         WHEN si.remediation_status = '未开始'
              AND JULIANDAY('2026-06-21') - JULIANDAY(si.inspection_date) > 90
              THEN '严重: 超 90 天未整改'
         WHEN si.remediation_status = '进行中'
              AND JULIANDAY('2026-06-21') - JULIANDAY(si.inspection_date) > 180
              THEN '警告: 整改进度过慢'
         ELSE '正常'
       END AS urgency_level
FROM site_inspection si
JOIN company_location cl ON cl.location_id = si.location_id
JOIN company c ON c.company_id = cl.company_id
WHERE si.hazards_identified IS NOT NULL
  AND si.remediation_status IN ('未开始', '进行中')
ORDER BY days_since_inspection DESC
LIMIT 50;
```

**Expected result:** 30–50 rows. "Severe" level locations are the priorities for remediation — notify the broker to push the client. "Warning" level locations should be scheduled for re-inspection.

---

## D9: Fraud signal heat map (by company)

**Dashboard:** Anti-fraud monitor

**Business background:** Once the RAG agent is trained, the anti-fraud analyst sweeps daily through **the frequency of `fraud_signal` or `attorney_involvement` communications by company recently**. Companies with abnormally high frequency go on the priority watchlist; their claims processing gets a stricter review going forward.

**Category:** RAG aggregation
**Difficulty:** Intermediate
**Role:** Anti-Fraud Analyst

**Approach:** This one walks `company → policy → claim → claim_communication` across four tables to attribute each claim communication to a company; each output row represents one company's fraud-signal profile. The longer the chain, the more fan-out risk: one company has multiple policies, each with multiple claims, each with multiple communications. So "claim count" must use `COUNT(DISTINCT cl.claim_id)` to de-duplicate, otherwise it gets inflated by the communication row count. Counts for each signal use `SUM(CASE WHEN signal_tag = '...' THEN 1 ELSE 0 END)` conditional counting — in a single scan, horizontally pivot the different tags into separate columns. `comm_date >= DATE('2026-06-21', '-12 months')` limits the window to the last 12 months. `HAVING fraud_signals + attorney_signals >= 3` filters the aggregated result to keep only companies with enough signals; sorting uses `fraud_signals + attorney_signals * 2` to give attorney involvement double weight (it's more serious than fraud signal alone).

```sql
SELECT c.company_id, c.company_name, c.industry,
       COUNT(DISTINCT cl.claim_id) AS total_claims,
       SUM(CASE WHEN cc.signal_tag = 'fraud_signal' THEN 1 ELSE 0 END) AS fraud_signals,
       SUM(CASE WHEN cc.signal_tag = 'attorney_involvement' THEN 1 ELSE 0 END) AS attorney_signals,
       SUM(CASE WHEN cc.signal_tag = 'dispute_escalation' THEN 1 ELSE 0 END) AS dispute_signals,
       ROUND(100.0 * SUM(CASE WHEN cc.signal_tag = 'fraud_signal' THEN 1 ELSE 0 END)
             / NULLIF(COUNT(cc.comm_id), 0), 2) AS fraud_signal_pct
FROM company c
JOIN policy p ON p.company_id = c.company_id
JOIN claim cl ON cl.policy_id = p.policy_id
JOIN claim_communication cc ON cc.claim_id = cl.claim_id
WHERE cc.comm_date >= DATE('2026-06-21', '-12 months')
GROUP BY c.company_id, c.company_name, c.industry
HAVING fraud_signals + attorney_signals >= 3
ORDER BY (fraud_signals + attorney_signals * 2) DESC
LIMIT 30;
```

**Expected result:** Usually 20–30 rows. Weighted sort `fraud_signals + attorney_signals * 2` (attorney involvement is more serious than a fraud signal). The top 10 companies should be escalated to the anti-fraud committee.

---

## D10: Composite renewal-decision assistant (single company 360°)

**Dashboard:** Renewal decision assistant ⭐ Core query

**Business background:** This is the **core SQL of the InsightUnderwriter AI Agent** — for a given company, pull every dimension needed for the renewal decision and produce a recommendation. The underwriter uses this output as a first draft and manually reviews before making the final call.

**Category:** CTE multi-table JOIN
**Difficulty:** Advanced
**Role:** Underwriter

**Approach:** This is the most complex query in the document. For a single company (`company_id = 1`), pull every dimension needed for a renewal decision and finally output 1 row with a 360° profile + AI recommendation. The challenge is that these dimensions live in six or seven unrelated tables (financials, loss_run, claim signals, payments, regulatory, credit). If you join them all directly, every pair of one-to-many relationships does a Cartesian product, exploding amounts to astronomical figures. The right approach is to build a CTE per dimension, each pre-aggregated to "one row for this company", then `company_profile LEFT JOIN` to stitch these single-row results horizontally. LEFT JOIN because some dimensions may be missing data (e.g., this company has never been hit with regulatory action) — if missing, keep the main row and use `COALESCE` to fill NULL with 0, rather than dropping the row. Each CTE pushes `WHERE company_id = 1` down, shrinking data before aggregating. The final `CASE` translates multi-dimensional signals into ai_recommendation. In production, replace `= 1` with a parameter to run in batch.

```sql
WITH company_profile AS (
  SELECT company_id, company_name, industry, risk_tier,
         employee_count, founded_year,
         total_active_premium_cny, total_paid_claims_cny
  FROM company WHERE company_id = 1
),
fin_latest AS (
  SELECT company_id, MAX(fiscal_year) AS latest_year,
         (SELECT revenue_cny FROM company_financial
          WHERE company_id = 1 ORDER BY fiscal_year DESC LIMIT 1) AS latest_revenue,
         (SELECT debt_to_equity_ratio FROM company_financial
          WHERE company_id = 1 ORDER BY fiscal_year DESC LIMIT 1) AS latest_debt_ratio
  FROM company_financial WHERE company_id = 1
  GROUP BY company_id
),
loss_3y AS (
  SELECT company_id,
         SUM(total_premium_cny) AS prem_3y,
         SUM(total_losses_cny)  AS loss_3y,
         ROUND(SUM(total_losses_cny) * 1.0 / NULLIF(SUM(total_premium_cny), 0), 3) AS lr_3y
  FROM loss_run WHERE company_id = 1 AND year >= 2023
  GROUP BY company_id
),
risk_signals AS (
  SELECT p.company_id,
         COUNT(DISTINCT CASE WHEN cl.status = '已拒赔' THEN cl.claim_id END) AS rejected_count,
         COUNT(DISTINCT CASE WHEN cc.signal_tag IN ('fraud_signal','attorney_involvement')
                             THEN cc.comm_id END) AS hi_risk_signals
  FROM policy p
  LEFT JOIN claim cl ON cl.policy_id = p.policy_id
  LEFT JOIN claim_communication cc ON cc.claim_id = cl.claim_id
  WHERE p.company_id = 1
  GROUP BY p.company_id
),
pay_behavior AS (
  SELECT p.company_id,
         ROUND(AVG(pm.days_late), 1) AS avg_days_late,
         SUM(CASE WHEN pm.days_late > 30 THEN 1 ELSE 0 END) AS severe_late_count
  FROM policy p
  JOIN invoice i ON i.policy_id = p.policy_id
  JOIN payment pm ON pm.invoice_id = i.invoice_id
  WHERE p.company_id = 1
  GROUP BY p.company_id
),
reg_summary AS (
  SELECT company_id,
         COUNT(*) AS reg_violations,
         SUM(fine_amount_cny) AS total_fines_cny
  FROM regulatory_filing
  WHERE company_id = 1 AND filing_date >= DATE('2026-06-21', '-3 years')
  GROUP BY company_id
),
credit_latest AS (
  SELECT company_id, credit_rating, rating_change, report_date
  FROM third_party_report
  WHERE company_id = 1
  ORDER BY report_date DESC LIMIT 1
)
SELECT cp.company_name, cp.industry, cp.risk_tier,
       fl.latest_revenue, fl.latest_debt_ratio,
       lo.lr_3y AS loss_ratio_3y, lo.prem_3y, lo.loss_3y,
       rs.rejected_count, rs.hi_risk_signals,
       pb.avg_days_late, pb.severe_late_count,
       COALESCE(rg.reg_violations, 0) AS reg_violations,
       COALESCE(rg.total_fines_cny, 0) AS total_fines_cny,
       cr.credit_rating, cr.rating_change,
       CASE
         WHEN lo.lr_3y > 1.0 OR rs.hi_risk_signals > 5
              OR cr.credit_rating IN ('BB','B','CCC') THEN '建议拒保'
         WHEN lo.lr_3y > 0.85 OR pb.severe_late_count > 2
              OR COALESCE(rg.reg_violations, 0) > 3 THEN '建议有条件续保'
         WHEN lo.lr_3y > 0.70 THEN '建议续保 + 涨价 15-25%'
         WHEN lo.lr_3y > 0.55 THEN '建议续保 + 涨价 5-10%'
         ELSE '建议续保 + 维持价格 (优质客户)'
       END AS ai_recommendation
FROM company_profile cp
LEFT JOIN fin_latest fl ON fl.company_id = cp.company_id
LEFT JOIN loss_3y lo ON lo.company_id = cp.company_id
LEFT JOIN risk_signals rs ON rs.company_id = cp.company_id
LEFT JOIN pay_behavior pb ON pb.company_id = cp.company_id
LEFT JOIN reg_summary rg ON rg.company_id = cp.company_id
LEFT JOIN credit_latest cr ON cr.company_id = cp.company_id;
```

**Expected result:** 1 row. LEFT JOINing the 6 CTE results produces a complete 360° profile for this company + AI recommendation. In production, change `WHERE company_id = 1` to a parameter to batch-generate recommendations for all expiring policies.

---

## D11: Industry-benchmark comparison dashboard

**Dashboard:** Industry benchmarking

**Business background:** Is a single company's loss ratio of 75% high or low? **You must compare it to industry benchmarks**. 75% in construction is below average and excellent, but 75% in financial services is far above average and dangerous. This query batch-outputs each company's actual LR vs. industry-average deviation.

**Category:** JOIN + aggregation
**Difficulty:** Intermediate
**Role:** Underwriting Manager

**Approach:** This one places each company's actual loss ratio next to its industry's benchmark loss ratio; each output row is one loss_run record (company × year × line). `loss_run` is already pre-aggregated, so no need to touch the claim detail. The key join is `loss_run JOIN company` (to get the industry) then `LEFT JOIN industry_benchmark ON ib.industry = c.industry AND ib.year = lr.year` — LEFT JOIN because some industry/year combinations may not have benchmark data, and we still want to keep the company row (variance NULL in that case). When joining benchmarks, match both industry and year — matching only on industry causes one company to attach to all years' benchmarks (fan-out). `WHERE lr.year = 2025` locks in the year. The CASE buckets based on how many times the industry mean the company's LR is.

```sql
SELECT c.company_name, c.industry, lr.year, lr.policy_type,
       lr.loss_ratio AS company_lr,
       ib.avg_loss_ratio AS industry_avg_lr,
       ROUND((lr.loss_ratio - ib.avg_loss_ratio) * 100, 2) AS variance_pct,
       CASE
         WHEN lr.loss_ratio > ib.avg_loss_ratio * 1.30 THEN '严重高于行业'
         WHEN lr.loss_ratio > ib.avg_loss_ratio * 1.10 THEN '略高于行业'
         WHEN lr.loss_ratio < ib.avg_loss_ratio * 0.80 THEN '优于行业'
         ELSE '行业平均水平'
       END AS classification
FROM loss_run lr
JOIN company c ON c.company_id = lr.company_id
LEFT JOIN industry_benchmark ib ON ib.industry = c.industry AND ib.year = lr.year
WHERE lr.year = 2025
ORDER BY variance_pct DESC
LIMIT 50;
```

**Expected result:** 50 rows. The top 10 by variance are companies that **must be repriced or declined** (LR far above industry). The bottom 10 are the **premium accounts to retain at all costs**.

---

## D12: Regulatory penalty distribution (by agency + year)

**Dashboard:** Compliance monitor

**Business background:** The Director of Compliance needs to know **which regulators our client base keeps getting in trouble with**. If 70% of penalties cluster at the Ministry of Emergency Management, it means insured clients are heavily concentrated in high-hazard industries and the risk-control strategy needs to strengthen "workplace safety" re-inspections.

**Category:** Pivot aggregation
**Difficulty:** Intermediate
**Role:** Director of Compliance

**Approach:** This one only needs `regulatory_filing`, cross-aggregating penalties by "agency × year"; each output row is the penalty summary for one agency in one year. The year is extracted by `STRFTIME('%Y', filing_date)` — SQLite's standard idiom for year extraction. `COUNT(*)` counts penalty filings, `COUNT(DISTINCT company_id)` counts the number of companies involved (the same company can be penalized multiple times by the same agency, so DISTINCT is needed to reflect "how many companies got hit"), `SUM/AVG(fine_amount_cny)` for fine totals and averages, and `SUM(CASE WHEN resolution_status = '进行中' THEN 1 ELSE 0 END)` for the count still unresolved. `WHERE filing_date >= '2024-01-01'` limits to recent years. GROUP BY the two keys, ORDER BY year DESC and fines DESC.

```sql
SELECT agency,
       STRFTIME('%Y', filing_date) AS year,
       COUNT(*) AS violation_count,
       COUNT(DISTINCT company_id) AS company_count,
       ROUND(SUM(fine_amount_cny), 0) AS total_fines_cny,
       ROUND(AVG(fine_amount_cny), 0) AS avg_fine_cny,
       SUM(CASE WHEN resolution_status = '进行中' THEN 1 ELSE 0 END) AS unresolved_count
FROM regulatory_filing
WHERE filing_date >= '2024-01-01'
GROUP BY agency, year
ORDER BY year DESC, total_fines_cny DESC;
```

**Expected result:** About 20–25 rows (7 agencies × 3 years). Focus on agencies with a high unresolved share (our clients are not cooperating with remediation), and agencies with the highest average fine (a single heavy penalty suggests a severe violation).

---

## D13: Tracking of credit-downgraded companies

**Dashboard:** Rating monitor

**Business background:** Credit rating downgrades typically **lead financial-statement blowups by 3–6 months**. The Director of Finance needs to closely watch downgraded clients: are receivables on their current policies still collectible? Should we trigger contract terms immediately and suspend new underwriting?

**Category:** Window function
**Difficulty:** Advanced
**Role:** Director of Finance

**Approach:** This one finds companies whose "latest report shows a downgrade" in `third_party_report`. The challenge is that each company has multiple historical reports, and we need both the latest one and the rating change relative to the previous report. One CTE with two window functions handles it: `LAG(credit_rating) OVER (PARTITION BY company_id ORDER BY report_date)` pulls the previous rating onto each report's row; `ROW_NUMBER() OVER (PARTITION BY company_id ORDER BY report_date DESC)` numbers each company's reports time-DESC, with `rn = 1` being the latest. Outer join `company` for company name and in-force premium; WHERE filters `rn = 1 AND rating_change = '下调' AND credit_rating IN (...)`; each output row is one company whose latest rating was downgraded to investment-grade borderline or below. We use window functions instead of GROUP BY because we want to preserve per-report detail (especially prev_rating), not aggregate. Sort by in-force premium DESC to prioritize the largest exposures.

```sql
WITH ranked AS (
  SELECT tpr.company_id, tpr.report_date, tpr.credit_rating, tpr.rating_change,
         LAG(tpr.credit_rating, 1) OVER (
           PARTITION BY tpr.company_id ORDER BY tpr.report_date
         ) AS prev_rating,
         ROW_NUMBER() OVER (
           PARTITION BY tpr.company_id ORDER BY tpr.report_date DESC
         ) AS rn
  FROM third_party_report tpr
)
SELECT c.company_name, c.industry, c.risk_tier,
       r.report_date AS latest_report_date,
       r.prev_rating AS previous_rating,
       r.credit_rating AS current_rating,
       r.rating_change,
       ROUND(c.total_active_premium_cny, 0) AS at_risk_premium_cny,
       ROUND(c.total_paid_claims_cny, 0) AS historic_claims_paid_cny
FROM ranked r
JOIN company c ON c.company_id = r.company_id
WHERE r.rn = 1
  AND r.rating_change = '下调'
  AND r.credit_rating IN ('BBB', 'BB', 'B', 'CCC')
ORDER BY c.total_active_premium_cny DESC
LIMIT 30;
```

**Expected result:** Usually 20–30 rows. Companies with high at_risk_premium (in-force premium > CNY 500K) are the priority — if the client implodes, this premium may become bad debt, and they may not have cash to cover the deductible on future claims.

---

## D14: Premium slippage alert (≥ 3 endorsements within a year)

**Dashboard:** Premium monitor

**Business background:** "Premium slippage" is a special signal designed for InsightUnderwriter — a policy repeatedly repriced over a short window indicates **the initial risk assessment was off**, or **the client's business is shifting rapidly**. Both cases call for a full re-underwriting at renewal (analogous to the "stage_transition slip" signal in B2B SaaS).

**Category:** Aggregation + HAVING
**Difficulty:** Intermediate
**Role:** Underwriting Manager

**Approach:** This one identifies policies whose premium was repeatedly endorsed within a year. Main table is `policy_premium_history` (one row per premium change); join `policy` and `company` only for policy number and company name — those don't affect aggregation granularity. After GROUP BY policy: `COUNT(*) FILTER (WHERE change_event_type = '批改')` counts only "Endorsement" events (excluding initial bind etc.); `MIN/MAX(new_premium_cny)` get the low and high points of the premium over this period to compute premium_swing and percent swing. `changed_at >= DATE('2026-06-21', '-12 months')` limits to the past year. `HAVING endorsement_count >= 3` filters to policies endorsed repeatedly; each output row is one such policy. SQLite note: `FILTER (WHERE ...)` requires 3.30+; older versions must rewrite as `SUM(CASE WHEN ... THEN 1 ELSE 0 END)`. Divisor uses `NULLIF(...,0)` to guard against zero.

```sql
SELECT pph.policy_id, p.policy_number, c.company_name, p.policy_type,
       COUNT(*) FILTER (WHERE pph.change_event_type = '批改') AS endorsement_count,
       ROUND(MIN(pph.new_premium_cny), 0) AS min_premium_cny,
       ROUND(MAX(pph.new_premium_cny), 0) AS max_premium_cny,
       ROUND(MAX(pph.new_premium_cny) - MIN(pph.new_premium_cny), 0) AS premium_swing_cny,
       ROUND((MAX(pph.new_premium_cny) - MIN(pph.new_premium_cny))
             * 100.0 / NULLIF(MIN(pph.new_premium_cny), 0), 1) AS swing_pct
FROM policy_premium_history pph
JOIN policy p ON p.policy_id = pph.policy_id
JOIN company c ON c.company_id = p.company_id
WHERE pph.changed_at >= DATE('2026-06-21', '-12 months')
GROUP BY pph.policy_id, p.policy_number, c.company_name, p.policy_type
HAVING endorsement_count >= 3
ORDER BY swing_pct DESC
LIMIT 30;
```

**Expected result:** Usually 15–30 rows. Policies with swing_pct > 30% **must be fully re-underwritten at renewal**. The underwriter on those policies should also be reviewed (frequent large pricing misses on initial bind).

---

## D15: Adjuster open caseload

**Dashboard:** Claims productivity

**Business background:** Every adjuster has a case_load_capacity ceiling (15–35 cases). The claims manager checks this dashboard daily; anyone with **active cases > 80% of capacity** stops getting new assignments, otherwise quality drops and incorrect payments creep in.

**Category:** Aggregation + JOIN
**Difficulty:** Basic
**Role:** Claims Manager

**Approach:** This one uses `claim_adjuster` as the main table and `LEFT JOIN claim` to count active cases per adjuster; each output row is one adjuster. LEFT JOIN rather than INNER is critical: an adjuster with no active cases should still appear (utilization 0%) so the manager can route new cases to them; INNER would erase idle people entirely, giving the opposite of what we want. The "active" definition `cl.status IN ('已立案','调查中','定损中')` must go in the LEFT JOIN's ON, not WHERE — putting it in WHERE would erroneously drop adjusters with no active cases (because their joined claim rows are all NULL and would be filtered out). `COUNT(cl.claim_id)` doesn't count NULLs from LEFT JOIN, so idle people correctly get 0. The CASE flags full-load based on `case_load_capacity`.

```sql
SELECT a.adjuster_id, a.full_name, a.specialty_claim_type, a.region,
       a.case_load_capacity,
       COUNT(cl.claim_id) AS active_case_count,
       ROUND(100.0 * COUNT(cl.claim_id) / a.case_load_capacity, 1) AS utilization_pct,
       CASE
         WHEN COUNT(cl.claim_id) >= a.case_load_capacity THEN '满负荷'
         WHEN COUNT(cl.claim_id) >= a.case_load_capacity * 0.8 THEN '接近满负荷'
         ELSE '正常'
       END AS workload_status
FROM claim_adjuster a
LEFT JOIN claim cl ON cl.adjuster_id = a.adjuster_id
                  AND cl.status IN ('已立案', '调查中', '定损中')   -- unified "open/active" definition (see KPI dictionary 16.3)
GROUP BY a.adjuster_id, a.full_name, a.specialty_claim_type,
         a.region, a.case_load_capacity
ORDER BY utilization_pct DESC;
```

**Expected result:** 25 rows. Prioritize handling "full" and "near full" adjusters; route new cases to "normal" colleagues. People chronically at "full" should be reviewed for whether training is lacking or specialty doesn't match.

---

# Business-question-style queries (B1–B35)

Each solves one ad-hoc analytical question; more exploratory.

---

## B1: Client basic profile + locations overview

**Subject area:** A Customer Profile

**Business background:** When an underwriter receives a renewal application, the first thing to do is understand "who is this client". This query pulls the company's basic profile + all operating locations + each location's property value and risk level. The underwriter needs a feel for it — is this a single-office company or a multi-province conglomerate?

**Category:** JOIN
**Difficulty:** Basic
**Role:** Underwriter

**Approach:** This one pulls a profile + all-locations overview for a single company (`company_id = 1`), outputting 1 row. `company` has a one-to-many to `company_location` (one company, many locations), so we `LEFT JOIN` and GROUP BY company to fold multiple locations back into one row — LEFT rather than INNER so that a company with zero registered locations still shows up (with location-related aggregations being 0/NULL). `COUNT(cl.location_id)` counts locations, `SUM(property_value_cny)` totals property value to see exposure, `GROUP_CONCAT(DISTINCT province)` concatenates the covered provinces into a string (SQLite-specific function; PostgreSQL equivalent is `STRING_AGG`), and `SUM(CASE WHEN location_risk_level='高' THEN 1 ELSE 0 END)` is a conditional count of high-risk locations. Because we only look at one company, no other companies' locations leak in; a single GROUP BY suffices.

```sql
SELECT c.company_id, c.company_name, c.industry, c.risk_tier,
       c.employee_count, c.founded_year,
       COUNT(cl.location_id) AS location_count,
       ROUND(SUM(cl.property_value_cny), 0) AS total_property_value_cny,
       GROUP_CONCAT(DISTINCT cl.province) AS provinces_covered,
       SUM(CASE WHEN cl.location_risk_level = '高' THEN 1 ELSE 0 END) AS high_risk_locations
FROM company c
LEFT JOIN company_location cl ON cl.company_id = c.company_id
WHERE c.company_id = 1
GROUP BY c.company_id;
```

**Expected result:** 1 row. total_property_value reflects the property exposure size the underwriter must evaluate. high_risk_locations > 0 calls for targeted endorsements on the policy.

---

## B2: Annual financial-health trend (LAG year-over-year)

**Subject area:** A Customer Profile

**Business background:** Financial deterioration often precedes claim spikes. This query outputs a single company's recent 5-year year-over-year financial changes: revenue up/down, debt ratio up/down, net profit up/down. **Companies negative for 2 years in a row** need extra care at renewal.

**Category:** Window function
**Difficulty:** Intermediate
**Role:** Financial Analyst

**Approach:** This one only touches `company_financial`, looking at one company's (`company_id = 1`) year-over-year financial changes; each output row is one fiscal year. The core is the window function `LAG(revenue_cny) OVER (ORDER BY fiscal_year)` — it pulls the previous year's revenue onto the current row, letting us compute YoY growth within the same row without self-joining the table to find "the previous year". Growth denominator uses `NULLIF(LAG(...),0)` to guard against zero previous-year revenue. We use a window function instead of GROUP BY because we want to keep each year's detail rows for trend comparison, not aggregate to a single number. Profit margin `net_profit / revenue` works the same. ORDER BY fiscal_year DESC puts the latest year at the top, easy to read the recent trend at a glance.

```sql
SELECT fiscal_year,
       ROUND(revenue_cny, 0) AS revenue,
       LAG(revenue_cny) OVER (ORDER BY fiscal_year) AS prev_revenue,
       ROUND((revenue_cny - LAG(revenue_cny) OVER (ORDER BY fiscal_year))
             * 100.0 / NULLIF(LAG(revenue_cny) OVER (ORDER BY fiscal_year), 0), 2) AS revenue_growth_pct,
       ROUND(debt_to_equity_ratio, 3) AS debt_ratio,
       ROUND(net_profit_cny, 0) AS net_profit,
       ROUND(net_profit_cny * 100.0 / NULLIF(revenue_cny, 0), 2) AS profit_margin_pct
FROM company_financial
WHERE company_id = 1
ORDER BY fiscal_year DESC;
```

**Expected result:** 3–5 rows. A healthy company has revenue_growth_pct > 5% and profit_margin_pct > 5%. Consecutive years of negative profit_margin = high risk.

---

## B3: Credit rating change history timeline

**Subject area:** A Customer Profile

**Business background:** Just looking at "current rating BBB" is limited information; you need to see **the trajectory**: from A down to BBB is deteriorating; from BB up to BBB is improving. Window functions pull each rating and the previous one onto the same row so you can see the change easily.

**Category:** Window function
**Difficulty:** Intermediate
**Role:** Financial Analyst

**Approach:** This one only touches `third_party_report`, lining up a single company's (`company_id = 1`) credit-rating history as a timeline; each output row is one report. Like B2, it relies on the window function `LAG(...) OVER (ORDER BY report_date)` to pull the previous rating and report date onto the current row, letting us see both "what rating it changed from to what" and compute days between two reports `JULIANDAY(current) - JULIANDAY(prev)` in the same row. LAG returns NULL on the first row (no prior record), and the date diff is also NULL — that's normal (start of the timeline). Window function instead of GROUP BY because the goal is to keep per-record detail to see the evolution, not aggregate. ORDER BY report_date ASC so the timeline runs early-to-late.

```sql
SELECT report_date, credit_rating, rating_change, report_source,
       LAG(credit_rating, 1) OVER (ORDER BY report_date) AS previous_rating,
       LAG(report_date, 1) OVER (ORDER BY report_date) AS previous_date,
       JULIANDAY(report_date) - JULIANDAY(LAG(report_date, 1) OVER (ORDER BY report_date)) AS days_between
FROM third_party_report
WHERE company_id = 1
ORDER BY report_date;
```

**Expected result:** Usually 2–4 rows. Frequent rating changes (intervals < 90 days) reflect the rating agency's uncertainty about the company — itself a risk signal.

---

## B4: High debt-ratio company list (Top 50)

**Subject area:** A Customer Profile

**Business background:** Companies with debt-to-equity > 1.5 are considered "financially stretched" in insurance; their ability to pay needs extra scrutiny at renewal. This query lists the 50 most dangerous companies.

**Category:** Aggregation + sort
**Difficulty:** Basic
**Role:** Risk Control Manager

**Approach:** This one lists the 50 companies with the highest debt ratio. The key trap is that "each company has multiple years of records in `company_financial`; we can only take the most recent year". If we joined without restricting the year, each company would appear multiple times (one row per year) and the list would be polluted by history. Here we use a correlated subquery `cf.fiscal_year = (SELECT MAX(fiscal_year) FROM company_financial WHERE company_id = c.company_id)` in the join's ON condition to lock each company to its own latest fiscal year — note the inner `company_id = c.company_id` correlates with the outer company, ensuring "each gets its own latest year". `WHERE debt_to_equity_ratio > 1.5` filters to stretched ones; each output row is one such company. No GROUP BY needed because after join, it's already one row per company; ORDER BY debt ratio DESC and LIMIT 50.

```sql
SELECT c.company_id, c.company_name, c.industry, c.risk_tier,
       cf.fiscal_year, cf.debt_to_equity_ratio,
       ROUND(cf.revenue_cny, 0) AS revenue,
       ROUND(cf.total_liabilities_cny, 0) AS total_liab,
       ROUND(c.total_active_premium_cny, 0) AS active_premium
FROM company c
JOIN company_financial cf ON cf.company_id = c.company_id
  AND cf.fiscal_year = (
    SELECT MAX(fiscal_year) FROM company_financial WHERE company_id = c.company_id
  )
WHERE cf.debt_to_equity_ratio > 1.5
ORDER BY cf.debt_to_equity_ratio DESC
LIMIT 50;
```

**Expected result:** 50 rows (most dangerous first). Companies with active_premium > CNY 500K should be escalated to the risk committee immediately.

---

## B5: Companies with dual signals: financial deterioration + high loss ratio

**Subject area:** A Customer Profile

**Business background:** **Two independent signals firing simultaneously = severe red alert**. A company both financially deteriorating (rising debt ratio / declining net profit) AND already running a high loss ratio — that's the classic precursor to "client about to refuse to pay / abscond". This CTE query filters on both dimensions simultaneously.

**Category:** CTE + multi-table
**Difficulty:** Advanced
**Role:** Underwriting Manager

```sql
WITH latest_fin AS (
  SELECT company_id, debt_to_equity_ratio, net_profit_cny
  FROM company_financial cf
  WHERE fiscal_year = (
    SELECT MAX(fiscal_year) FROM company_financial WHERE company_id = cf.company_id
  )
),
loss_summary AS (
  SELECT company_id,
         ROUND(SUM(total_losses_cny) * 1.0 / NULLIF(SUM(total_premium_cny), 0), 3) AS lr_avg
  FROM loss_run WHERE year >= 2024
  GROUP BY company_id
)
SELECT c.company_id, c.company_name, c.industry,
       lf.debt_to_equity_ratio, lf.net_profit_cny,
       ls.lr_avg,
       ROUND(c.total_active_premium_cny, 0) AS active_premium
FROM company c
JOIN latest_fin lf ON lf.company_id = c.company_id
JOIN loss_summary ls ON ls.company_id = c.company_id
WHERE lf.debt_to_equity_ratio > 1.2
  AND lf.net_profit_cny < 0
  AND ls.lr_avg > 0.80
ORDER BY ls.lr_avg DESC, lf.debt_to_equity_ratio DESC
LIMIT 30;
```

**Expected result:** Usually 5–15 rows (dual filter, not many). These are the "must discuss" list for the underwriting committee.

---

## B6: Top premium clients ranking (Top 25)

**Subject area:** B Policy & Underwriting

**Business background:** The CEO monthly meeting wants to know **who our cash cows are**. **What share do the top 10 clients contribute** reflects "client concentration risk" — too concentrated (top 10 > 30%) means losing any one major client deals a real blow.

**Category:** Aggregation + sort
**Difficulty:** Basic
**Role:** CEO / CRO

```sql
SELECT c.company_id, c.company_name, c.industry, c.risk_tier,
       COUNT(DISTINCT p.policy_id) AS active_policy_count,
       ROUND(c.total_active_premium_cny, 0) AS total_active_premium_cny,
       ROUND(100.0 * c.total_active_premium_cny
             / SUM(c.total_active_premium_cny) OVER (), 2) AS pct_of_book
FROM company c
LEFT JOIN policy p ON p.company_id = c.company_id AND p.status = '有效'
WHERE c.total_active_premium_cny > 0
GROUP BY c.company_id, c.company_name, c.industry, c.risk_tier,
         c.total_active_premium_cny
ORDER BY c.total_active_premium_cny DESC
LIMIT 25;
```

**Expected result:** 25 rows. Look at cumulative pct_of_book: Top 10 cumulative > 30% is the concentration warning line; Top 25 cumulative > 50% is the danger line.

---

## B7: Premium share by line of business

**Subject area:** B Policy & Underwriting

**Business background:** Corporate strategy looks at product mix. **Commercial Property 60% / Liability 30% / Other 10%** is a typical "property-heavy, liability-light" mix. The VP of Underwriting needs to decide whether to push liability product lines next year.

**Category:** Aggregation
**Difficulty:** Basic
**Role:** VP Underwriting

```sql
SELECT policy_type,
       COUNT(*) AS policy_count,
       ROUND(SUM(current_annual_premium_cny), 0) AS total_premium_cny,
       ROUND(100.0 * SUM(current_annual_premium_cny)
             / SUM(SUM(current_annual_premium_cny)) OVER (), 2) AS pct_of_total,
       ROUND(AVG(current_annual_premium_cny), 0) AS avg_premium_per_policy
FROM policy
WHERE status = '有效'
GROUP BY policy_type
ORDER BY total_premium_cny DESC;
```

**Expected result:** 8 rows (the 8 lines). pct_of_total shows the product mix; avg_premium shows single-policy scale (property usually larger).

---

## B8: Policy endorsement frequency distribution

**Subject area:** B Policy & Underwriting

**Business background:** Endorsement frequency is an inverse indicator of underwriting quality — a policy endorsed repeatedly mid-term usually means the initial risk assessment wasn't thorough enough. This query outputs the distribution of "0 / 1 / 2 / 3+ endorsements" policies.

**Category:** Aggregation + bucketing
**Difficulty:** Basic
**Role:** Underwriting Manager

```sql
SELECT bucket,
       COUNT(*) AS policy_count,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS pct
FROM (
  SELECT p.policy_id,
         CASE
           WHEN endorsement_count = 0 THEN '0 (无批改)'
           WHEN endorsement_count = 1 THEN '1 次'
           WHEN endorsement_count = 2 THEN '2 次'
           ELSE '3+ 次 (异常)'
         END AS bucket
  FROM policy p
  LEFT JOIN (
    SELECT policy_id, COUNT(*) AS endorsement_count
    FROM policy_endorsement GROUP BY policy_id
  ) pe ON pe.policy_id = p.policy_id
)
GROUP BY bucket
ORDER BY bucket;
```

**Expected result:** 4 rows. "3+ (abnormal)" should be < 10%; otherwise the underwriting process needs rework.

---

## B9: Full premium-history trace for a single policy

**Subject area:** B Policy & Underwriting

**Business background:** When an underwriter is renewing a policy, they're often asked "Why did this policy go up 30% last year?". This query pulls the full premium_history for that policy from initial bind to the latest adjustment, using a window function to show cumulative change at each step.

**Category:** Window function
**Difficulty:** Intermediate
**Role:** Underwriter

```sql
SELECT change_event_type, changed_at,
       ROUND(previous_premium_cny, 0) AS prev,
       ROUND(new_premium_cny, 0) AS new,
       ROUND(change_amount_cny, 0) AS delta,
       change_pct,
       change_reason,
       ROUND(SUM(change_amount_cny) OVER (
         ORDER BY changed_at ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
       ), 0) AS cumulative_change_cny
FROM policy_premium_history
WHERE policy_id = 1
ORDER BY changed_at;
```

**Expected result:** Usually 2–5 rows (1 initial bind + 0–4 endorsements). cumulative_change_cny shows the running total of changes from start to current.

---

## B10: Renewal-decision accuracy (decision vs. subsequent loss ratio)

**Subject area:** B Policy & Underwriting

**Business background:** **Were the renewal decisions right?** For clients we "renewed + repriced up" at the time, did the loss ratio actually drop afterward? For clients we declined, did they get picked up by competitors and have more frequent losses? This CTE analysis helps the underwriting department back-test the decision model.

**Category:** CTE + multi-table
**Difficulty:** Advanced
**Role:** Underwriting Manager

```sql
WITH dec AS (   -- de-dup to (company, decision): same company + same decision counted once, to avoid loss_run being doubled
  SELECT DISTINCT p.company_id, rd.decision
  FROM renewal_decision rd
  JOIN policy p ON p.policy_id = rd.policy_id
  WHERE rd.decision_date BETWEEN '2025-01-01' AND '2025-12-31'   -- decision year (earliest renewal decision in this dataset is 2025-05)
),
lr_next AS (    -- subsequent (next-year) losses: aggregate loss_run per company first into single row, then JOIN to the decision set; don't multiply by decision count
  SELECT company_id,
         SUM(total_losses_cny) AS post_loss,
         SUM(total_premium_cny) AS post_prem
  FROM loss_run
  WHERE year = 2026                                              -- underwriting year after the decision
  GROUP BY company_id
)
SELECT d.decision,
       COUNT(DISTINCT d.company_id) AS company_count,
       ROUND(SUM(lr.post_prem), 0) AS subsequent_premium_cny,
       ROUND(SUM(lr.post_loss), 0) AS subsequent_losses_cny,
       ROUND(SUM(lr.post_loss) * 1.0 / NULLIF(SUM(lr.post_prem), 0), 3) AS subsequent_loss_ratio
FROM dec d
JOIN lr_next lr ON lr.company_id = d.company_id
GROUP BY d.decision
ORDER BY subsequent_loss_ratio DESC;
```

> **Date window (important):** In this dataset policies have `effective_date ≥ 2024-06-21` and 365-day terms, so the earliest expiry is 2025-06,
> meaning **renewal decisions first appear in 2025** (no 2024 decisions). So the decision window uses **2025** and subsequent losses use underwriting year **2026**,
> semantics: "2025 renewal decisions → 2026 subsequent loss ratio"; otherwise the query silently returns empty.
> **Fan-out fix:** `dec` is de-duped to (company, decision); `loss_run` is first aggregated per company into a single row and then JOINed, so totals don't inflate with decision count.

**Expected result:** 3 rows (3 decision outcomes). Ideal case: "Renew" group has lower subsequent LR (premium clients); "Conditional Renew" sits in between (showing "conditions" worked); "Decline" group has fewer samples — note decisions are per policy, so if only some of a company's policies were declined while others remain in force, the company can still appear in 2026 loss_run, so the "Decline" group may not be empty.

---

## B11: Risk score vs. actual loss ratio correlation

**Subject area:** B Policy & Underwriting

**Business background:** **Are the underwriters' risk scores actually predictive?** If high-scored (risky) policies do have high subsequent losses, and low-scored (safe) ones do have low losses — the scoring model is working. If there's no correlation at all, the scoring is essentially guesswork.

**Category:** CTE + bucketing
**Difficulty:** Advanced
**Role:** Actuary / Data Analyst

```sql
WITH policy_risk AS (
  SELECT p.policy_id, p.current_annual_premium_cny,
         ROUND(AVG(ra.risk_score), 0) AS avg_risk_score
  FROM policy p
  JOIN risk_assessment ra ON ra.policy_id = p.policy_id
  GROUP BY p.policy_id, p.current_annual_premium_cny
),
policy_loss AS (
  SELECT p.policy_id, COALESCE(SUM(cl.paid_amount_cny), 0) AS total_paid
  FROM policy p
  LEFT JOIN claim cl ON cl.policy_id = p.policy_id
  GROUP BY p.policy_id
)
SELECT
  CASE
    WHEN pr.avg_risk_score < 40 THEN '低风险 (0-39)'
    WHEN pr.avg_risk_score < 60 THEN '中低 (40-59)'
    WHEN pr.avg_risk_score < 75 THEN '中高 (60-74)'
    ELSE '高风险 (75-100)'
  END AS risk_band,
  COUNT(*) AS policy_count,
  ROUND(AVG(pr.avg_risk_score), 1) AS avg_score,
  ROUND(AVG(pl.total_paid * 1.0 / NULLIF(pr.current_annual_premium_cny, 0)), 3) AS avg_loss_ratio
FROM policy_risk pr
JOIN policy_loss pl ON pl.policy_id = pr.policy_id
GROUP BY risk_band
ORDER BY avg_score;
```

**Expected result:** 4 rows. Ideal: avg_loss_ratio rises monotonically with risk_band (Low 0.3 → Mid-Low 0.5 → Mid-High 0.7 → High 0.9). If all bands show similar LR (all around 0.6), the scoring system has failed and needs retraining.

---

## B12: Direct vs. broker channel quality comparison

**Subject area:** B Policy & Underwriting

**Business background:** About 15% of policies are direct (broker_id IS NULL), the rest through brokers. **Direct clients are usually higher quality** (those who come to you proactively often have well-defined needs and are good accounts), but volume is small. This query quantifies and compares loss ratio and renewal rate across the two channels.

**Category:** Aggregation + comparison
**Difficulty:** Intermediate
**Role:** Director of Distribution

```sql
WITH pol AS (   -- one row per policy (with its paid-loss total), to avoid policy×claim fan-out
  SELECT p.policy_id,
         CASE WHEN p.broker_id IS NULL THEN '直销' ELSE '经纪渠道' END AS channel,
         p.current_annual_premium_cny,
         (SELECT COALESCE(SUM(cl.paid_amount_cny), 0)
          FROM claim cl WHERE cl.policy_id = p.policy_id) AS paid_cny
  FROM policy p
  WHERE p.status IN ('有效', '已到期')
)
SELECT channel,
       COUNT(*) AS policy_count,
       ROUND(SUM(current_annual_premium_cny), 0) AS total_premium_cny,
       ROUND(SUM(paid_cny), 0) AS total_paid_cny,
       ROUND(SUM(paid_cny) * 1.0
             / NULLIF(SUM(current_annual_premium_cny), 0), 3) AS channel_loss_ratio,
       ROUND(AVG(current_annual_premium_cny), 0) AS avg_premium_per_policy
FROM pol
GROUP BY channel;
```

> **Fan-out fix:** Naive `policy LEFT JOIN claim` then `SUM/AVG(p.current_annual_premium_cny)` gets inflated by claim row count,
> making `channel_loss_ratio` denominator artificially high and `avg_premium_per_policy` distorted. Here we pre-aggregate each policy's paid losses with a correlated subquery at policy grain, ensuring each policy's premium is counted exactly once.

**Expected result:** 2 rows. Typical: direct LR ~0.55, broker channel LR ~0.70. If direct LR is also high = clients coming in directly are also low quality, possibly because pricing is too loose.

---

## B13: 3-year cumulative loss ratio per company

**Subject area:** C Claims

**Business background:** Core data for renewal decisions. **Companies with 3-year cumulative LR > 80% are almost certain to be declined**. This query outputs each company's 3-year total premium, total losses, and cumulative LR — the single most frequently pulled query for underwriters.

**Category:** Aggregation + JOIN
**Difficulty:** Basic
**Role:** Underwriter

```sql
SELECT c.company_id, c.company_name, c.industry, c.risk_tier,
       SUM(lr.total_premium_cny) AS prem_3y,
       SUM(lr.total_losses_cny)  AS loss_3y,
       ROUND(SUM(lr.total_losses_cny) * 1.0
             / NULLIF(SUM(lr.total_premium_cny), 0), 3) AS loss_ratio_3y,
       SUM(lr.claim_frequency) AS claim_count_3y
FROM company c
JOIN loss_run lr ON lr.company_id = c.company_id
WHERE lr.year >= 2023
GROUP BY c.company_id, c.company_name, c.industry, c.risk_tier
HAVING loss_ratio_3y > 0
ORDER BY loss_ratio_3y DESC
LIMIT 30;
```

**Expected result:** 30 rows (worst first). loss_ratio_3y > 1.0 = three years of losses paid out exceed premium collected, almost certainly a decline.

---

## B14: Average close days (by line)

**Subject area:** C Claims

**Business background:** **Different lines have different claim complexity**. Simple property damage (burnt machinery, swap it out) can close in 30 days; bodily injury (employee hurt) can take 6 months due to medical timelines. The claims manager uses this to see which lines are slow and whether staffing is right.

**Category:** Date arithmetic + aggregation
**Difficulty:** Intermediate
**Role:** Claims Manager

```sql
WITH closed_claims AS (
  SELECT cl.claim_id, cl.claim_type, cl.reported_date,
         MAX(ce.event_date) AS closed_at
  FROM claim cl
  JOIN claim_event ce ON ce.claim_id = cl.claim_id
  WHERE cl.status = '已结案' AND ce.event_type = '结案归档'
  GROUP BY cl.claim_id, cl.claim_type, cl.reported_date
)
SELECT claim_type,
       COUNT(*) AS closed_count,
       ROUND(AVG(JULIANDAY(closed_at) - JULIANDAY(reported_date)), 1) AS avg_days_to_close,
       ROUND(MIN(JULIANDAY(closed_at) - JULIANDAY(reported_date)), 1) AS min_days,
       ROUND(MAX(JULIANDAY(closed_at) - JULIANDAY(reported_date)), 1) AS max_days
FROM closed_claims
GROUP BY claim_type
ORDER BY avg_days_to_close DESC;
```

**Expected result:** ~9 rows (9 claim_types). Lines with avg_days_to_close > 150 should consider adding dedicated adjusters.

---

## B15: Top 30 large claims

**Subject area:** C Claims

**Business background:** **Large claims (paid > CNY 1M)** are events management must pay attention to, requiring post-mortems: could it have been avoided? Should there be reinsurance? This query pulls the 30 biggest claims for the annual CEO review.

**Category:** Sort + JOIN
**Difficulty:** Basic
**Role:** Claims Director

```sql
SELECT cl.claim_id, cl.claim_number, c.company_name, c.industry,
       cl.claim_type, cl.incident_date, cl.status,
       ROUND(cl.loss_amount_cny, 0) AS loss_amount,
       ROUND(cl.paid_amount_cny, 0) AS paid_amount,
       ROUND(cl.paid_amount_cny * 100.0 / NULLIF(cl.loss_amount_cny, 0), 1) AS pay_ratio_pct,
       a.full_name AS adjuster_name
FROM claim cl
JOIN policy p ON p.policy_id = cl.policy_id
JOIN company c ON c.company_id = p.company_id
JOIN claim_adjuster a ON a.adjuster_id = cl.adjuster_id
WHERE cl.paid_amount_cny > 1000000
ORDER BY cl.paid_amount_cny DESC
LIMIT 30;
```

**Expected result:** 30 rows. pay_ratio_pct close to 100% means nearly full payout (no adjustment cuts); < 70% means significant cuts (possibly partial denial).

---

## B16: Incident-to-report lag analysis (moral hazard signal)

**Subject area:** C Claims

**Business background:** **A reporting lag > 7 days carries moral hazard** — the client might be gathering evidence, coordinating stories, or even self-resolving and then filing. This query outputs the reporting-lag distribution to identify anomalous claims.

**Category:** Date arithmetic + bucketing
**Difficulty:** Intermediate
**Role:** Anti-Fraud Analyst

```sql
SELECT
  CASE
    WHEN JULIANDAY(reported_date) - JULIANDAY(incident_date) = 0 THEN '当日报案'
    WHEN JULIANDAY(reported_date) - JULIANDAY(incident_date) <= 1 THEN '1 天内'
    WHEN JULIANDAY(reported_date) - JULIANDAY(incident_date) <= 3 THEN '2-3 天'
    WHEN JULIANDAY(reported_date) - JULIANDAY(incident_date) <= 7 THEN '4-7 天'
    WHEN JULIANDAY(reported_date) - JULIANDAY(incident_date) <= 14 THEN '8-14 天 (警戒)'
    ELSE '> 14 天 (高风险)'
  END AS reporting_lag,
  COUNT(*) AS claim_count,
  ROUND(AVG(loss_amount_cny), 0) AS avg_loss,
  ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS pct
FROM claim
GROUP BY reporting_lag
ORDER BY MIN(JULIANDAY(reported_date) - JULIANDAY(incident_date));
```

**Expected result:** 6 rows. "> 14 days" usually < 5%; if abnormally high, investigate whether there's a systemic reporting impediment (e.g., slow internal claims processes).

---

## B17: Dangerous claims with repeated reserve increases

**Subject area:** C Claims

**Business background:** Similar to D5 but focused on **magnitude of growth** rather than frequency. **A reserve going from CNY 100K to CNY 1M** (10×) is far worse than "from CNY 800K to CNY 1M" (25%). Window functions show the growth trajectory.

**Category:** Aggregation + window
**Difficulty:** Advanced
**Role:** Claims Manager

```sql
WITH reserve_journey AS (
  SELECT cr.claim_id, cr.reserve_date, cr.reserve_amount_cny,
         FIRST_VALUE(cr.reserve_amount_cny) OVER (
           PARTITION BY cr.claim_id ORDER BY cr.reserve_date
         ) AS initial_reserve,
         LAST_VALUE(cr.reserve_amount_cny) OVER (
           PARTITION BY cr.claim_id ORDER BY cr.reserve_date
           ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
         ) AS latest_reserve,
         COUNT(*) OVER (PARTITION BY cr.claim_id) AS adjustment_count
  FROM claim_reserve cr
)
SELECT DISTINCT rj.claim_id, cl.claim_number, c.company_name,
       cl.status,
       ROUND(rj.initial_reserve, 0) AS initial_reserve,
       ROUND(rj.latest_reserve, 0) AS latest_reserve,
       ROUND(rj.latest_reserve / NULLIF(rj.initial_reserve, 0), 2) AS multiplier,
       rj.adjustment_count
FROM reserve_journey rj
JOIN claim cl ON cl.claim_id = rj.claim_id
JOIN policy p ON p.policy_id = cl.policy_id
JOIN company c ON c.company_id = p.company_id
WHERE rj.adjustment_count >= 2
  AND rj.latest_reserve / NULLIF(rj.initial_reserve, 0) > 1.5
ORDER BY multiplier DESC
LIMIT 25;
```

**Expected result:** 25 rows. multiplier > 3 is a severe case, typically meaning the case is out of control (litigation expanded or medical costs ballooned).

---

## B18: Claim status distribution (per company)

**Subject area:** C Claims

**Business background:** A company's "open case" share reflects claims-handling health. **Open cases > 30%** indicates processing backlog or disputes. At renewal, underwriters look not only at historic paid amounts but also at the potential payout from open cases.

**Category:** Pivot aggregation
**Difficulty:** Intermediate
**Role:** Underwriter

```sql
SELECT c.company_name, c.industry,
       COUNT(*) AS total_claims,
       SUM(CASE WHEN cl.status = '已结案' THEN 1 ELSE 0 END) AS closed,
       SUM(CASE WHEN cl.status = '已支付' THEN 1 ELSE 0 END) AS paid,
       SUM(CASE WHEN cl.status IN ('调查中','定损中','已立案') THEN 1 ELSE 0 END) AS open,
       SUM(CASE WHEN cl.status = '已拒赔' THEN 1 ELSE 0 END) AS rejected,
       ROUND(100.0 * SUM(CASE WHEN cl.status IN ('调查中','定损中','已立案') THEN 1 ELSE 0 END)
             / COUNT(*), 1) AS open_pct
FROM company c
JOIN policy p ON p.company_id = c.company_id
JOIN claim cl ON cl.policy_id = p.policy_id
GROUP BY c.company_id, c.company_name, c.industry
HAVING total_claims >= 5
ORDER BY open_pct DESC
LIMIT 30;
```

**Expected result:** 30 rows (sorted by open share). Companies with open_pct > 40% should have "potential payout from open cases" added to the decision model at renewal.

---

## B19: Declined-claims analysis

**Subject area:** C Claims

**Business background:** Decline is the outcome no one wants — the client is unhappy and the insurer may get sued. **Why did we decline? Which lines have the highest decline rate?** Use this query to back-test decline patterns and improve wording to avoid unnecessary disputes.

**Category:** Aggregation + JOIN
**Difficulty:** Intermediate
**Role:** Claims Director

```sql
SELECT cl.claim_type, p.policy_type,
       COUNT(*) AS rejected_count,
       ROUND(AVG(cl.loss_amount_cny), 0) AS avg_loss_amount,
       ROUND(SUM(cl.loss_amount_cny), 0) AS total_avoided_payout
FROM claim cl
JOIN policy p ON p.policy_id = cl.policy_id
WHERE cl.status = '已拒赔'
GROUP BY cl.claim_type, p.policy_type
ORDER BY rejected_count DESC
LIMIT 25;
```

**Expected result:** 25 rows. total_avoided_payout is the money "saved" by declining, but balance is needed — too many declines means the policy wording is restrictive, and the market may see us as "hard to collect from" and lose clients.

---

## B20: Cross-year loss-ratio trend per company (Window)

**Subject area:** C Claims

**Business background:** Looking at 2024 LR of 80% in isolation isn't the worst, but going from 50% (2022) → 65% (2023) → 80% (2024) all the way up is **a deteriorating trend**, more dangerous than a high single point. Window function shows YoY change.

**Category:** Window function
**Difficulty:** Advanced
**Role:** Underwriting Manager

```sql
WITH yearly AS (
  SELECT company_id, year,
         ROUND(SUM(total_losses_cny) * 1.0 / NULLIF(SUM(total_premium_cny), 0), 3) AS lr
  FROM loss_run
  GROUP BY company_id, year
)
SELECT c.company_name, c.industry,
       y.year, y.lr,
       LAG(y.lr) OVER (PARTITION BY y.company_id ORDER BY y.year) AS prev_lr,
       ROUND(y.lr - LAG(y.lr) OVER (PARTITION BY y.company_id ORDER BY y.year), 3) AS yoy_change
FROM yearly y
JOIN company c ON c.company_id = y.company_id
WHERE y.company_id = 1
ORDER BY y.year;
```

**Expected result:** Usually 3–5 rows (one company's annual LR trend). Two consecutive years with yoy_change > 0.15 is a "must raise rates or decline" signal at renewal.

---

## B21: Per-company fraud signal stats (RAG)

**Subject area:** D Unstructured

**Business background:** This query is the core training-label source for the RAG agent. **Count, per company, how often fraud_signal communications appear historically**, and aggregate the most common sub-tag — when later fine-tuning the LLM, this is the ground truth for "anomalous company vs. normal company".

**Category:** Aggregation + JOIN
**Difficulty:** Intermediate
**Role:** Anti-Fraud Analyst

```sql
SELECT c.company_id, c.company_name, c.industry,
       COUNT(cc.comm_id) AS fraud_comm_count,
       COUNT(DISTINCT cc.claim_id) AS affected_claim_count,
       GROUP_CONCAT(DISTINCT cc.sub_tag) AS sub_tags_seen
FROM company c
JOIN policy p ON p.company_id = c.company_id
JOIN claim cl ON cl.policy_id = p.policy_id
JOIN claim_communication cc ON cc.claim_id = cl.claim_id
WHERE cc.signal_tag = 'fraud_signal'
GROUP BY c.company_id, c.company_name, c.industry
HAVING fraud_comm_count >= 2
ORDER BY fraud_comm_count DESC
LIMIT 30;
```

**Expected result:** Usually 25–30 rows. Focus on companies with affected_claim_count > 3 (multiple cases showing fraud signals = systemic problem).

---

## B22: Loss-amount comparison: claims with vs. without attorney involvement

**Subject area:** D Unstructured

**Business background:** **How much higher is the average payout on attorney-involved cases compared to typical cases?** This data is critical for the legal department's "litigation cost vs. settlement cost" estimates. If attorney cases pay 50% more, proactive settlement is usually the better deal.

**Category:** Subquery + comparison
**Difficulty:** Intermediate
**Role:** Legal

```sql
SELECT category,
       COUNT(*) AS claim_count,
       ROUND(AVG(paid_amount_cny), 0) AS avg_paid,
       ROUND(AVG(loss_amount_cny), 0) AS avg_loss_reported,
       ROUND(AVG(paid_amount_cny) * 100.0 / NULLIF(AVG(loss_amount_cny), 0), 1) AS pay_rate_pct
FROM (
  SELECT cl.claim_id, cl.paid_amount_cny, cl.loss_amount_cny,
    CASE WHEN EXISTS (
      SELECT 1 FROM claim_communication cc
      WHERE cc.claim_id = cl.claim_id AND cc.signal_tag = 'attorney_involvement'
    ) THEN '有律师介入' ELSE '无律师介入' END AS category
  FROM claim cl
  WHERE cl.status IN ('已结案', '已支付', '已拒赔')
)
GROUP BY category;
```

**Expected result:** 2 rows. Expect "with attorney involvement" avg_paid 30–50% higher, and pay_rate_pct also higher (the insurer dares not push back on adjustments when lawyers are involved).

---

## B23: signal_tag × claim_type matrix

**Subject area:** D Unstructured

**Business background:** **Which lines are most prone to fraud?** Property damage cases tend to see "inflated loss"; bodily injury tends to see "exaggerated medical bills". This matrix helps the risk analyst target anti-fraud resources precisely.

**Category:** Pivot
**Difficulty:** Intermediate
**Role:** Risk Analyst

```sql
SELECT cl.claim_type,
       SUM(CASE WHEN cc.signal_tag = 'fraud_signal' THEN 1 ELSE 0 END) AS fraud,
       SUM(CASE WHEN cc.signal_tag = 'dispute_escalation' THEN 1 ELSE 0 END) AS dispute,
       SUM(CASE WHEN cc.signal_tag = 'attorney_involvement' THEN 1 ELSE 0 END) AS attorney,
       SUM(CASE WHEN cc.signal_tag = 'settlement_negotiation' THEN 1 ELSE 0 END) AS settlement,
       SUM(CASE WHEN cc.signal_tag = 'investigation_note' THEN 1 ELSE 0 END) AS investigation,
       SUM(CASE WHEN cc.signal_tag = 'normal_cooperative' THEN 1 ELSE 0 END) AS normal,
       COUNT(*) AS total
FROM claim cl
JOIN claim_communication cc ON cc.claim_id = cl.claim_id
GROUP BY cl.claim_type
ORDER BY fraud DESC;
```

**Expected result:** 9 rows (9 claim_types). Look at the fraud column for which lines are highest — those are the anti-fraud priority lines.

---

## B24: Hazard remediation overdue list

**Subject area:** D Unstructured

**Business background:** Similar to D8, but B24 doesn't just look at "Not Started"; "In Progress over 6 months" also counts as overdue. **These are clients who "must complete remediation before renewal"**.

**Category:** Date arithmetic + CASE
**Difficulty:** Intermediate
**Role:** Risk Control Manager

```sql
SELECT c.company_name, cl.city, cl.location_name,
       si.inspection_date, si.hazards_identified, si.remediation_status,
       JULIANDAY('2026-06-21') - JULIANDAY(si.inspection_date) AS days_since,
       CASE
         WHEN si.remediation_status = '未开始'
              AND JULIANDAY('2026-06-21') - JULIANDAY(si.inspection_date) > 60 THEN '严重逾期'
         WHEN si.remediation_status = '进行中'
              AND JULIANDAY('2026-06-21') - JULIANDAY(si.inspection_date) > 180 THEN '进度过慢'
         ELSE '正常'
       END AS verdict
FROM site_inspection si
JOIN company_location cl ON cl.location_id = si.location_id
JOIN company c ON c.company_id = cl.company_id
WHERE si.hazards_identified IS NOT NULL
  AND si.remediation_status IN ('未开始', '进行中')
  AND JULIANDAY('2026-06-21') - JULIANDAY(si.inspection_date) > 60
ORDER BY days_since DESC;
```

**Expected result:** Usually 30–80 rows (overdue locations). verdict='Severely Overdue' should be contacted immediately.

---

## B25: Communication author activity (XOR pattern)

**Subject area:** D Unstructured

**Business background:** This query demonstrates handling XOR fields — **count how many communications each underwriter/adjuster has written**. Use the 'U'||id / 'A'||id prefix trick to unify the ID space.

**Category:** XOR + aggregation
**Difficulty:** Intermediate
**Role:** Data Analyst

```sql
WITH unified AS (
  SELECT CASE WHEN author_underwriter_id IS NOT NULL
              THEN 'U' || author_underwriter_id
              ELSE 'A' || author_adjuster_id END AS author_key,
         CASE WHEN author_underwriter_id IS NOT NULL THEN 'Underwriter'
              ELSE 'Adjuster' END AS author_role,
         comm_id, signal_tag
  FROM claim_communication
)
SELECT author_key, author_role,
       COUNT(*) AS comm_count,
       SUM(CASE WHEN signal_tag = 'fraud_signal' THEN 1 ELSE 0 END) AS fraud_comms,
       SUM(CASE WHEN signal_tag = 'attorney_involvement' THEN 1 ELSE 0 END) AS attorney_comms
FROM unified
GROUP BY author_key, author_role
ORDER BY comm_count DESC
LIMIT 30;
```

**Expected result:** 30 rows. Adjusters usually lead (since most comms are drafted by adjusters). People with a high fraud_comms share are anti-fraud experts and could be assigned harder cases.

---

## B26: Client payment-behavior grading buckets

**Subject area:** E Payment

**Business background:** Bucket client payment behavior into 4 grades: **Excellent / Good / Fair / Poor** — can be used as a plus/minus factor at renewal.

**Category:** CASE + aggregation
**Difficulty:** Intermediate
**Role:** Finance Manager

```sql
WITH cust_pay AS (
  SELECT c.company_id, c.company_name,
         COUNT(pm.payment_id) AS payment_count,
         AVG(pm.days_late) AS avg_days_late,
         SUM(CASE WHEN pm.days_late > 30 THEN 1 ELSE 0 END) AS severe_late_count
  FROM company c
  JOIN policy p ON p.company_id = c.company_id
  JOIN invoice i ON i.policy_id = p.policy_id
  JOIN payment pm ON pm.invoice_id = i.invoice_id
  GROUP BY c.company_id, c.company_name
  HAVING payment_count >= 4
)
SELECT
  CASE
    WHEN avg_days_late <= 0 AND severe_late_count = 0 THEN '优秀'
    WHEN avg_days_late <= 7 AND severe_late_count <= 1 THEN '良好'
    WHEN avg_days_late <= 20 THEN '一般'
    ELSE '差'
  END AS payment_grade,
  COUNT(*) AS company_count,
  ROUND(AVG(avg_days_late), 1) AS bucket_avg_days_late
FROM cust_pay
GROUP BY payment_grade
ORDER BY bucket_avg_days_late;
```

**Expected result:** 4 rows. "Excellent" clients should dominate (>50%). Export the "Poor" list for collections and renewal teams.

---

## B27: Severely late clients list + in-force premium

**Subject area:** E Payment

**Business background:** **Clients who owe a lot of premium but still have large policies in force — highest risk**. If we don't collect, that premium becomes bad debt; if delinquency persists across renewal, regulators may treat it as de facto credit sales.

**Category:** JOIN + aggregation
**Difficulty:** Intermediate
**Role:** Credit Risk

```sql
SELECT c.company_name, c.industry,
       COUNT(DISTINCT i.invoice_id) AS overdue_invoices,
       ROUND(SUM(i.amount_due_cny), 0) AS total_overdue_cny,
       ROUND(c.total_active_premium_cny, 0) AS active_premium_at_risk
FROM company c
JOIN policy p ON p.company_id = c.company_id
JOIN invoice i ON i.policy_id = p.policy_id
WHERE i.status = '逾期'
GROUP BY c.company_id, c.company_name, c.industry,
         c.total_active_premium_cny
HAVING total_overdue_cny > 50000
ORDER BY total_overdue_cny DESC
LIMIT 50;
```

**Expected result:** 50 rows. Clients with total_overdue / active_premium > 30% are "owe premium worth 30% of their in-force book" — danger zone.

---

## B28: Accounts-receivable aging analysis

**Subject area:** E Payment

**Business background:** Must-have metric for the monthly finance report: **AR by aging bucket** (0–30 days / 30–60 / 60–90 / 90–180 / > 180). Anything > 90 days needs bad-debt provisioning.

**Category:** Date bucketing
**Difficulty:** Intermediate
**Role:** Finance Manager

```sql
SELECT
  CASE
    WHEN JULIANDAY('2026-06-21') - JULIANDAY(due_date) <= 0 THEN '未到期'
    WHEN JULIANDAY('2026-06-21') - JULIANDAY(due_date) <= 30 THEN '0-30 天'
    WHEN JULIANDAY('2026-06-21') - JULIANDAY(due_date) <= 60 THEN '30-60 天'
    WHEN JULIANDAY('2026-06-21') - JULIANDAY(due_date) <= 90 THEN '60-90 天'
    WHEN JULIANDAY('2026-06-21') - JULIANDAY(due_date) <= 180 THEN '90-180 天 (准坏账)'
    ELSE '> 180 天 (坏账风险)'
  END AS aging_bucket,
  COUNT(*) AS invoice_count,
  ROUND(SUM(amount_due_cny), 0) AS total_amount_cny
FROM invoice
WHERE status IN ('待支付', '逾期')
GROUP BY aging_bucket
ORDER BY MIN(JULIANDAY('2026-06-21') - JULIANDAY(due_date));
```

**Expected result:** 6 rows. The "> 180 days" bucket should be fully provisioned as bad debt (per accounting standards).

---

## B29: Payment behavior vs. loss-ratio correlation

**Subject area:** E Payment

**Business background:** **Industry experience: clients who pay late are often also clients with high loss ratios**. Validate this assumption. If the correlation is strong, "payment behavior" can be used as an input feature in the risk score.

**Category:** CTE + aggregation
**Difficulty:** Advanced
**Role:** RevOps

```sql
WITH pay_band AS (
  SELECT c.company_id,
         CASE
           WHEN AVG(pm.days_late) <= 0 THEN '准时'
           WHEN AVG(pm.days_late) <= 15 THEN '略晚'
           WHEN AVG(pm.days_late) <= 45 THEN '中度逾期'
           ELSE '严重逾期'
         END AS pay_band
  FROM company c
  JOIN policy p ON p.company_id = c.company_id
  JOIN invoice i ON i.policy_id = p.policy_id
  JOIN payment pm ON pm.invoice_id = i.invoice_id
  GROUP BY c.company_id
  HAVING COUNT(pm.payment_id) >= 4
),
lr_band AS (
  SELECT company_id,
         ROUND(SUM(total_losses_cny) * 1.0 / NULLIF(SUM(total_premium_cny), 0), 3) AS lr_3y
  FROM loss_run
  WHERE year >= 2023
  GROUP BY company_id
)
SELECT pb.pay_band,
       COUNT(*) AS company_count,
       ROUND(AVG(lb.lr_3y), 3) AS avg_loss_ratio
FROM pay_band pb
JOIN lr_band lb ON lb.company_id = pb.company_id
GROUP BY pb.pay_band
ORDER BY avg_loss_ratio;
```

**Expected result:** 4 rows. Expect: "On-time" clients LR ~0.60, "Severely Late" clients LR ~0.85 — validates the hypothesis. If LRs are similar across buckets, the hypothesis fails.

---

## B30: Industry risk tier vs. average loss ratio

**Subject area:** F External

**Business background:** Validate the relationship between `risk_tier` and actual loss ratio. This data can be used to calibrate the actuarial "risk tier → premium multiplier" model.

**Category:** JOIN
**Difficulty:** Basic
**Role:** Actuary

```sql
SELECT c.industry, c.risk_tier,
       COUNT(DISTINCT c.company_id) AS company_count,
       ROUND(AVG(lr.loss_ratio), 3) AS avg_loss_ratio
FROM company c
JOIN loss_run lr ON lr.company_id = c.company_id
WHERE lr.year >= 2024
GROUP BY c.industry, c.risk_tier
ORDER BY c.industry, c.risk_tier;
```

**Expected result:** ~40 rows (10 industries × 4 tiers). Within an industry, LR should rise monotonically with risk_tier.

---

## B31: Regulatory penalty density ranking (per company)

**Subject area:** F External

**Business background:** Companies with the most cumulative penalties are compliance high-risk. This list should be shared with underwriters — at renewal, the latest penalty status must be checked.

**Category:** Aggregation + sort
**Difficulty:** Basic
**Role:** Compliance Manager

```sql
SELECT c.company_name, c.industry,
       COUNT(rf.filing_id) AS violation_count,
       ROUND(SUM(rf.fine_amount_cny), 0) AS total_fines_cny,
       GROUP_CONCAT(DISTINCT rf.agency) AS agencies_involved,
       SUM(CASE WHEN rf.resolution_status = '进行中' THEN 1 ELSE 0 END) AS unresolved_count
FROM company c
JOIN regulatory_filing rf ON rf.company_id = c.company_id
GROUP BY c.company_id, c.company_name, c.industry
ORDER BY violation_count DESC
LIMIT 30;
```

**Expected result:** 30 rows. violation_count > 5 is extremely high risk; basically should be declined.

---

## B32: Subsequent loss ratio for credit-downgraded companies

**Subject area:** F External

**Business background:** **Does a credit downgrade really predict a higher loss ratio?** If it does, credit monitoring is a valid early-warning system.

**Category:** CTE + multi-table
**Difficulty:** Advanced
**Role:** RevOps

```sql
WITH downgraded AS (
  SELECT DISTINCT company_id,
         MIN(report_date) AS first_downgrade_date
  FROM third_party_report
  WHERE rating_change = '下调'
    AND report_date BETWEEN '2024-01-01' AND '2024-12-31'
  GROUP BY company_id
),
post_lr AS (
  SELECT lr.company_id,
         ROUND(SUM(lr.total_losses_cny) * 1.0 / NULLIF(SUM(lr.total_premium_cny), 0), 3) AS lr_2025
  FROM loss_run lr WHERE lr.year = 2025
  GROUP BY lr.company_id
),
control_group AS (
  SELECT c.company_id
  FROM company c
  WHERE c.company_id NOT IN (SELECT company_id FROM downgraded)
)
SELECT '评级下调企业 2025 LR' AS metric,
       ROUND(AVG(pl.lr_2025), 3) AS avg_lr,
       COUNT(*) AS company_count
FROM downgraded d
JOIN post_lr pl ON pl.company_id = d.company_id
UNION ALL
SELECT '对照组 (未下调) 2025 LR' AS metric,
       ROUND(AVG(pl.lr_2025), 3) AS avg_lr,
       COUNT(*) AS company_count
FROM control_group cg
JOIN post_lr pl ON pl.company_id = cg.company_id;
```

**Expected result:** 2-row comparison. If "downgraded companies" avg_lr is meaningfully higher than the "control group", credit monitoring is validated.

---

## B33: Policy portfolio of high-fine companies

**Subject area:** F External

**Business background:** **For companies with cumulative fines > CNY 500K**, what active policies do we still have with them? Pull the list immediately to assess total exposure.

**Category:** JOIN + aggregation
**Difficulty:** Intermediate
**Role:** Compliance Manager

```sql
WITH high_fine AS (
  SELECT company_id, SUM(fine_amount_cny) AS total_fine
  FROM regulatory_filing
  WHERE filing_date >= DATE('2026-06-21', '-3 years')
  GROUP BY company_id
  HAVING total_fine > 500000
)
SELECT c.company_name, c.industry,
       ROUND(hf.total_fine, 0) AS total_fines_3y,
       COUNT(p.policy_id) AS active_policy_count,
       ROUND(SUM(p.current_annual_premium_cny), 0) AS active_premium_cny
FROM high_fine hf
JOIN company c ON c.company_id = hf.company_id
LEFT JOIN policy p ON p.company_id = c.company_id AND p.status = '有效'
GROUP BY c.company_id, c.company_name, c.industry, hf.total_fine
ORDER BY total_fines_3y DESC;
```

**Expected result:** Usually 20–40 rows. Companies with active_premium > CNY 300K are joint compliance + underwriting focus.

---

## B34: Top N companies with largest deviation from industry benchmark

**Subject area:** F External

**Business background:** Similar to D11, but focused on **the extremes of deviation**. Extreme positive (well above industry) → adjust immediately; extreme negative (well below industry) → benchmark case for market expansion.

**Category:** JOIN + sort
**Difficulty:** Intermediate
**Role:** VP Underwriting

```sql
WITH variance AS (
  SELECT c.company_id, c.company_name, c.industry,
         lr.loss_ratio AS company_lr,
         ib.avg_loss_ratio AS industry_avg,
         lr.loss_ratio - ib.avg_loss_ratio AS abs_var
  FROM loss_run lr
  JOIN company c ON c.company_id = lr.company_id
  JOIN industry_benchmark ib ON ib.industry = c.industry AND ib.year = lr.year
  WHERE lr.year = 2025
)
SELECT * FROM (
  SELECT '极差客户 (偏高)' AS category, * FROM variance ORDER BY abs_var DESC LIMIT 15
)
UNION ALL
SELECT * FROM (
  SELECT '标杆客户 (偏低)' AS category, * FROM variance ORDER BY abs_var ASC LIMIT 15
);
```

> **SQLite dialect tip:** In compound queries (UNION ALL), only the very last SELECT can directly carry `ORDER BY/LIMIT`.
> So we wrap each branch's `ORDER BY ... LIMIT 15` in a subquery `SELECT * FROM (...)`; otherwise SQLite errors with
> `ORDER BY clause should come after UNION ALL not before`.

**Expected result:** 30 rows (15 in each group). The "benchmark clients" list can be used by sales for "renewal discount" retention offers.

---

## B35: Multi-dimensional composite risk score ranking

**Subject area:** F External

**Business background:** Ultimate risk score. **Combining 5 dimensions — financial, losses, compliance, credit, fraud signals** — generate a 0–100 composite risk score, used as a baseline feature for the renewal-decision AI model.

**Category:** Big composite CTE
**Difficulty:** Advanced
**Role:** Underwriting Manager

```sql
WITH fin_score AS (
  SELECT company_id,
         CASE WHEN MAX(debt_to_equity_ratio) > 2.0 THEN 20
              WHEN MAX(debt_to_equity_ratio) > 1.5 THEN 12
              WHEN MAX(debt_to_equity_ratio) > 1.0 THEN 6
              ELSE 0 END AS fin_pts
  FROM company_financial GROUP BY company_id
),
loss_score AS (
  SELECT company_id,
         CASE WHEN AVG(loss_ratio) > 1.0 THEN 30
              WHEN AVG(loss_ratio) > 0.85 THEN 20
              WHEN AVG(loss_ratio) > 0.70 THEN 10
              ELSE 0 END AS loss_pts
  FROM loss_run WHERE year >= 2023 GROUP BY company_id
),
reg_score AS (
  SELECT company_id,
         CASE WHEN COUNT(*) >= 5 THEN 20
              WHEN COUNT(*) >= 3 THEN 12
              WHEN COUNT(*) >= 1 THEN 5
              ELSE 0 END AS reg_pts
  FROM regulatory_filing
  WHERE filing_date >= DATE('2026-06-21', '-3 years')
  GROUP BY company_id
),
credit_score AS (
  SELECT company_id,
         CASE WHEN credit_rating IN ('BB','B','CCC') THEN 15
              WHEN credit_rating IN ('BBB') THEN 8
              ELSE 0 END AS credit_pts
  FROM third_party_report tpr
  WHERE report_date = (
    SELECT MAX(report_date) FROM third_party_report WHERE company_id = tpr.company_id
  )
),
fraud_score AS (
  SELECT p.company_id,
         CASE WHEN COUNT(cc.comm_id) >= 5 THEN 15
              WHEN COUNT(cc.comm_id) >= 2 THEN 8
              WHEN COUNT(cc.comm_id) >= 1 THEN 3
              ELSE 0 END AS fraud_pts
  FROM policy p
  LEFT JOIN claim cl ON cl.policy_id = p.policy_id
  LEFT JOIN claim_communication cc ON cc.claim_id = cl.claim_id
    AND cc.signal_tag IN ('fraud_signal', 'attorney_involvement')
  GROUP BY p.company_id
)
SELECT c.company_name, c.industry,
       COALESCE(f.fin_pts, 0) AS fin_pts,
       COALESCE(l.loss_pts, 0) AS loss_pts,
       COALESCE(r.reg_pts, 0) AS reg_pts,
       COALESCE(cs.credit_pts, 0) AS credit_pts,
       COALESCE(fr.fraud_pts, 0) AS fraud_pts,
       (COALESCE(f.fin_pts,0) + COALESCE(l.loss_pts,0) + COALESCE(r.reg_pts,0)
        + COALESCE(cs.credit_pts,0) + COALESCE(fr.fraud_pts,0)) AS composite_risk_score
FROM company c
LEFT JOIN fin_score f ON f.company_id = c.company_id
LEFT JOIN loss_score l ON l.company_id = c.company_id
LEFT JOIN reg_score r ON r.company_id = c.company_id
LEFT JOIN credit_score cs ON cs.company_id = c.company_id
LEFT JOIN fraud_score fr ON fr.company_id = c.company_id
ORDER BY composite_risk_score DESC
LIMIT 50;
```

**Expected result:** 50 rows. composite_risk_score is out of 100; > 60 should go to the renewal underwriting committee, > 80 should almost always be declined. Look at each sub-score to see "which dimension is this company's risk in".

---

## Query Category Statistics

| Category | Count | Query IDs |
|----------|-------|-----------|
| Aggregation | 17 | D1, D4, D6, D7, D9, D12, D15, B1, B4, B6, B7, B8, B13, B19, B27, B30, B31 |
| JOIN operations | 14 | D3, D11, B1, B3, B11, B12, B13, B14, B15, B19, B21, B22, B27, B33 |
| Window functions | 6 | D13, B2, B3, B9, B17, B20 |
| Date bucketing/arithmetic | 7 | D1, D4, D8, B14, B16, B24, B28 |
| Subquery/CTE | 11 | D1, D10, B5, B10, B11, B22, B26, B29, B32, B33, B35 |
| Pivot | 3 | B18, B23, B25 |
| Advanced (CTE + Window combined) | 10 | D10, D13, B5, B10, B11, B17, B20, B29, B32, B35 |

> Note: the above is **capability-dimension coverage**; the same query can belong to multiple categories (e.g., using both JOIN and aggregation), so row counts sum to more than 50.

## Role Coverage

| Role | Query Count | IDs |
|------|-------------|-----|
| CEO / CFO / CRO | 3 | D1, B6, D13 |
| Underwriting Manager / VP | 12 | D2, D4, D6, D11, D14, B5, B8, B10, B20, B30, B34, B35 |
| Underwriter | 5 | D10, B1, B9, B13, B18 |
| Claims Manager / Director | 7 | D5, D15, B14, B15, B17, B19, D9 |
| Anti-Fraud / Risk / Compliance | 7 | D8, D9, D12, B16, B21, B24, B31 |
| Finance / RevOps | 6 | D7, B26, B27, B28, B29, B32 |
| Distribution / Legal / Actuary | 5 | D3, B11, B12, B22, B30 |

## Difficulty Distribution

| Difficulty | Count | IDs |
|------------|-------|-----|
| Basic | 12 | D4, D8, D15, B1, B4, B6, B7, B8, B13, B15, B30, B31 |
| Intermediate | 28 | D1, D2, D3, D5, D6, D7, D9, D11, D12, D14, B2, B3, B9, B12, B14, B16, B18, B19, B21, B22, B23, B24, B25, B26, B27, B28, B33, B34 |
| Advanced | 10 | D10, D13, B5, B10, B11, B17, B20, B29, B32, B35 |

---

## SQLite Dialect Notes

- Date arithmetic uses `JULIANDAY()` and `DATE(..., '-N months/years')`, which are SQLite-specific. In PostgreSQL replace with `EXTRACT(EPOCH FROM ...)` or `INTERVAL`.
- `GROUP_CONCAT()` is a SQLite function; in PostgreSQL use `STRING_AGG()`.
- Window functions require SQLite 3.25.0+ (post-2018-09).
- The `FILTER (WHERE ...)` clause requires SQLite 3.30+; otherwise substitute `CASE WHEN ... THEN 1 END`.
- `NULLS LAST` in SQLite is emulated via `ORDER BY col IS NULL, col`.

## Integration with the InsightUnderwriter AI Agent

These queries' roles in the AI Agent architecture:

1. **Text2SQL Agent training:** Use these 50 queries as (natural-language question → SQL) training pairs. After thousands of additional human-authored pairs, fine-tune a dedicated Text2SQL model.
2. **RAG Agent triggering:** When D9 / D10 / B21 / B22 etc. return high-risk signals, trigger RAG retrieval over `claim_communication.content` for detail.
3. **Decision-synthesis Agent:** Use the output of D10 / B35 as the core evidence in the recommendation.
4. **Data validation:** When new data is loaded, run these queries as regression tests (verify no breaking changes in key KPIs).

Typical workflow example (analogous to ER document 17.8):
- User asks: "Should we renew Company 1?"
- AI orchestrates: invokes D10 (composite 360°) + B35 (composite risk score) + D9 (fraud heat map)
- Output: recommendation + data citations + key risk points

---

**End of SQL queries document.**
