# Fintech — SMB Lending Pipeline SQL Query Reference

## Overview

This document provides **20 business-facing SQL queries** for the `fintech_smb_lending_pipeline_medium` dataset. Each query corresponds to a question a Pacific Bridge Lending stakeholder would genuinely raise when analyzing the lending business, risk management, and portfolio performance. For business background, company roles, industry primer, and glossary, see `01-fintech_smb_lending_pipeline_medium_business_context.md`. For table structure and field meanings, see `02-fintech_smb_lending_pipeline_medium_er_document.md`.

> **Reference-date convention.** The dataset is anchored to a fixed `REFERENCE_DATE = 2026-06-03`. Queries that need "today" use the literal `'2026-06-03'` instead of `DATE('now')`, so results are independent of execution time and reproducible. If you re-anchor the dataset to a different reference date, replace this literal in every query below.

## How to Use This Document

This document is written for an intern / new analyst who has just finished reading the business background document (`01-...business_context.md`) and the ER document (`02-...er_document.md`) and is about to start the analysis. Treat it as a project handover: the manager has handed you these 20 questions, and you'll work through them one by one this week, understanding why each is written the way it is.

Every query is organized in the same **five-section** structure:

1. **Business context** — who is asking, why, what decision the answer will support, and why it's urgent now.
2. **Category / difficulty / business role** — three quick tags so you can see which type of SQL you're practicing and which role in the company it corresponds to.
3. **Approach** — before you see the SQL, this section explains which tables to touch, how to join them, what aggregation grain to use, why a CTE / window function / subquery is (or isn't) used, and which SQLite-specific gotchas to avoid. This section is the main learning content.
4. **SQL code** — runnable directly against the SQLite database the generator produces.
5. **Expected output** — what the result set looks like, which key numbers correspond to which embedded business trap, and what to do next once you have the results.

Two usage tips:

- **Every query maps back to a business question.** A "business question → query" cross-reference appears at the end of the document; before reading any SQL, decide which of Q1–Q5 it is meant to answer.
- **SQL here is meant to be read and learned from, not just run.** The approach section explains "why it's written this way." The real skill is in seeing the direction of the joins, the grain of the aggregation, and the choice of convention — not just in getting numbers out.

---

## Query Index

| # | Title | Business Role | Category | Difficulty |
|---|------|----------|------|------|
| 1 | Risk-Grade Pricing Alignment Analysis | Executive | Aggregation + Join | Intermediate |
| 2 | Industry Portfolio Concentration Dashboard | Manager | Aggregation + Join | Intermediate |
| 3 | Approval Leakage — False Negative Analysis | Analyst | Subquery + Join | Advanced |
| 4 | Early Warning Signals Before Default | Analyst | CTE + Join | Advanced |
| 5 | Customer Lifecycle Value Comparison | Executive | Aggregation + Join | Intermediate |
| 6 | Monthly Application Volume Trends | Operations | Date Aggregation | Basic |
| 7 | Loan Officer Performance Scorecard | Manager | Aggregation + Join | Intermediate |
| 8 | Repayment Behavior Cohort Analysis | Analyst | CTE + Aggregation | Advanced |
| 9 | Top 10 High-Risk Active Loans | Operations | Join + Subquery | Intermediate |
| 10 | Default Recovery Rate by Risk Grade | Finance | Aggregation + Join | Intermediate |
| 11 | Regional Application Volume and Conversion Rate | Finance | Aggregation + Join | Basic |
| 12 | Repeat-Customer Retention Metrics | Manager | CTE + Join | Advanced |
| 13 | Portfolio Vintage Analysis | Analyst | Date + Aggregation | Intermediate |
| 14 | Late Payment Trend Analysis | Operations | Date Aggregation | Intermediate |
| 15 | Loan Amount vs. Credit Score Correlation | Analyst | Aggregation | Basic |
| 16 | Risk-Grade Repricing Opportunities | Manager | Subquery + Join | Advanced |
| 17 | Monthly Cash Flow Projection | Finance | Aggregation + Date | Intermediate |
| 18 | Application Processing Time Analysis | Operations | Date Calculation | Basic |
| 19 | Industry-Specific Default Patterns | Executive | CTE + Aggregation | Advanced |
| 20 | Customer Segmentation by LTV | Executive | CTE + Window Function | Advanced |

---

## Queries

### Query 1: Risk-Grade Pricing Alignment Analysis

**Business context:**
The Chief Risk Officer needs to verify whether loan pricing (interest rate) accurately reflects the actual default risk of each risk grade. In the quarterly risk review, she suspects that certain grades may be underpriced — the rate charged isn't enough to cover the risk being taken on. This analysis compares the default rate assumed by the pricing model against the actual observed default rate. A gap means either a profit opportunity (overcharging) or a loss (undercharging). This is the foundation for consulting project Q1 and directly affects profit targets.

**Category:** Aggregation + Join
**Difficulty:** Intermediate
**Business role:** Executive

**Approach:**
This query needs to align the implied default rate (hard-coded as a pricing assumption in the `risk_grade` table) with the actual default rate (derived from `loan` and `default_event`) at grade-level granularity. First, `JOIN loan ON risk_grade.id = loan.risk_grade_id` to hang each loan onto its grade, then `LEFT JOIN default_event ON loan.id = de.loan_id` to flag the defaulted ones. Critical point: this step must be a LEFT JOIN — switching to INNER JOIN would drop every non-defaulted loan, leaving the denominator with only defaulted loans, which would produce a 100% actual default rate. Aggregation grain is "one row per grade." Actual default rate = `COUNT(default_event.id) / COUNT(loan.id)` (COUNT counts only non-NULL values, so the numerator automatically counts only defaults). No CTE or window function needed — a single GROUP BY does it.

```sql
-- Compare implied vs actual default rates by risk grade to identify pricing misalignment
SELECT
    rg.grade_code,
    rg.grade_name,
    rg.interest_rate,
    rg.implied_default_rate AS pricing_assumption_pct,
    COUNT(l.id) AS total_loans,
    COUNT(de.id) AS defaulted_loans,
    ROUND(100.0 * COUNT(de.id) / COUNT(l.id), 2) AS actual_default_rate_pct,
    ROUND(rg.implied_default_rate - (100.0 * COUNT(de.id) / COUNT(l.id)), 2) AS pricing_gap_pct
FROM risk_grade rg
JOIN loan l ON rg.id = l.risk_grade_id
LEFT JOIN default_event de ON l.id = de.loan_id
GROUP BY rg.id, rg.grade_code, rg.grade_name, rg.interest_rate, rg.implied_default_rate
ORDER BY pricing_gap_pct ASC;
```

**Expected output:**
One row per risk grade showing total loan count, default count, actual vs. implied default rate, and pricing gap. In this dataset `pricing_gap_pct = implied − actual`, so a negative gap means the grade is *underpriced* (actual defaults exceed the model assumption). Expected output: Grade C shows a clear negative gap (~−4pp; actual ~10% vs. implied 6.0%) — this is exactly why the analysis exists: to expose the major pricing mismatch. Grades A and B are priced within ±1pp of implied; Grade D is about 2pp underpriced; Grade E is within ±1pp. Combined with Grade C making up ~28% of the portfolio, this quantifies the underpriced exposure the CRO needs to address through repricing or tightening Grade C underwriting.

---

### Query 2: Industry Portfolio Concentration Dashboard

**Business context:**
The portfolio manager is preparing materials for the quarterly board meeting and needs to report on portfolio diversification and concentration risk. The board is particularly worried about exposure to cyclical industries like restaurants and hospitality, especially post-pandemic. If any single industry experiences a systemic shock, concentrated exposure could trigger cascading defaults. This query identifies which industries dominate the outstanding portfolio and computes concentration risk metrics to guide "appetite for new applications in concentrated industries."

**Category:** Aggregation + Join
**Difficulty:** Intermediate
**Business role:** Manager

**Approach:**
To look at portfolio concentration from the industry angle, four tables need to be chained: `industry → customer → application → loan → default_event`. Use LEFT JOIN from application to loan because rejected applications have no matching loan, but we still need to count them in the "applications" denominator. Share-of-total uses scalar subqueries `(SELECT COUNT(*) FROM application)` and `(SELECT SUM(outstanding_balance) FROM loan)` for global denominators — note the subquery denominators are "whole-table" totals, at a different grain than the outer per-industry numerator, which is exactly what computing a share requires. `COUNT(DISTINCT a.id)` / `COUNT(DISTINCT l.id)` use DISTINCT because when a loan pairs with multiple default rows, the multi-table join fans out and inflates row counts. DISTINCT prevents double-counting. Ordering by outstanding balance descending puts the most concentrated industries first.

```sql
-- Calculate portfolio concentration by industry with exposure and default metrics
SELECT
    i.industry_name,
    COUNT(DISTINCT a.id) AS total_applications,
    ROUND(100.0 * COUNT(DISTINCT a.id) / (SELECT COUNT(*) FROM application), 2) AS pct_of_applications,
    COUNT(DISTINCT l.id) AS total_loans,
    ROUND(SUM(l.outstanding_balance), 2) AS total_outstanding,
    ROUND(100.0 * SUM(l.outstanding_balance) / (SELECT SUM(outstanding_balance) FROM loan), 2) AS pct_of_portfolio,
    COUNT(de.id) AS defaults,
    ROUND(100.0 * COUNT(de.id) / COUNT(DISTINCT l.id), 2) AS industry_default_rate_pct,
    i.default_rate_baseline AS historical_baseline_pct
FROM industry i
JOIN customer c ON i.id = c.industry_id
JOIN application a ON c.id = a.customer_id
LEFT JOIN loan l ON a.id = l.application_id
LEFT JOIN default_event de ON l.id = de.loan_id
GROUP BY i.id, i.industry_name, i.default_rate_baseline
ORDER BY total_outstanding DESC;
```

**Expected output:**
Returns metrics per industry: applications, loans, outstanding balance, default rate. In this dataset Restaurant makes up ~18% of applications and ~18% of outstanding balance; combined with Hospitality (~9%), the cyclical "restaurants + hotels" cluster represents ~27% of the portfolio — the single-shock concentration the board is worried about. The query also compares actual default rate to each industry's historical baseline (Restaurant 9.5%, Hospitality 12.4%, Construction 11.3%, etc.) to surface industries underperforming expectations. Supports Q2 (portfolio concentration) and informs industry-level lending caps or pricing adjustments.

---

### Query 3: Approval Leakage — False Negative Analysis

**Business context:**
The VP of Credit is worried about lost revenue from rejecting creditworthy applicants (false negatives). During a review of rejected applications, the team noticed that some rejected applicants had credit profiles similar to — or better than — approved customers who were performing well. Each wrong rejection means lost interest income, potentially hundreds of thousands of dollars per year at scale. This analysis identifies "looks-like-a-good-customer" rejected applications using credit-score, revenue, and headcount thresholds, quantifying the opportunity cost of over-conservative underwriting.

**Category:** Subquery + Join
**Difficulty:** Advanced
**Business role:** Analyst

**Approach:**
The idea is "compute the average profile of successful borrowers first, then go look for applicants in the rejected pool who resemble them." Step one: a CTE `successful_profile` averages credit score, revenue, and employee count across customers whose loans are CURRENT or PAID_OFF, collapsing to a single row. Step two: join application with customer, then `CROSS JOIN successful_profile` (it's a single row, so CROSS JOIN broadcasts those averages onto every application), and filter on `status_code='REJECTED'` plus the three threshold conditions (credit score ≥ mean − 30, revenue ≥ mean × 0.7, employees ≥ mean × 0.6). Those are the "false negative" candidates. `LIMIT 50` truncates for manual review by the underwriting committee; to estimate the total leakage volume, remove LIMIT and count rows. A CTE earns its keep here because that single-row average is referenced by every application — writing it as a CTE is cleaner than repeating the subquery inline.

```sql
-- Identify rejected applications with customer profiles matching successful borrowers
WITH successful_profile AS (
    SELECT
        AVG(c.credit_score) AS avg_credit_score,
        AVG(c.annual_revenue) AS avg_revenue,
        AVG(c.employee_count) AS avg_employees
    FROM loan l
    JOIN customer c ON l.customer_id = c.id
    JOIN loan_status ls ON l.current_status_id = ls.id
    WHERE ls.status_code IN ('CURRENT', 'PAID_OFF')
)
SELECT
    a.application_number,
    c.business_name,
    c.credit_score,
    c.annual_revenue,
    c.employee_count,
    a.requested_amount,
    a.rejection_reason,
    ROUND(c.credit_score - sp.avg_credit_score, 0) AS credit_score_vs_avg,
    ROUND(c.annual_revenue - sp.avg_revenue, 0) AS revenue_vs_avg
FROM application a
JOIN customer c ON a.customer_id = c.id
JOIN loan_status ls ON a.status_id = ls.id
CROSS JOIN successful_profile sp
WHERE ls.status_code = 'REJECTED'
  AND c.credit_score >= sp.avg_credit_score - 30
  AND c.annual_revenue >= sp.avg_revenue * 0.7
  AND c.employee_count >= sp.avg_employees * 0.6
ORDER BY c.credit_score DESC
LIMIT 50;
```

**Expected output:**
Returns up to 50 rejected applications whose customer profile (credit score, revenue, employee count) approaches or exceeds successful borrowers. Each row represents one potential false negative. Across the full rejected pool (~780 applications), about 15-20% satisfy all three thresholds — the false-negative candidate pool — but `LIMIT 50` returns only the top 50 by credit score for manual review. **To estimate total leakage volume and revenue impact, remove the LIMIT and count rows;** the LIMIT here is only so the underwriting committee can skim the result set. Supports Q3 (approval leakage) and provides specific applications for manual review and model recalibration.

---

### Query 4: Early Warning Signals Before Default

**Business context:**
The Collections Manager wants to roll out a proactive outreach program that intervenes before a loan defaults. Historically the company only started action after the loan was 90+ DPD, by which time recovery is already hard. This analysis looks at repayment behavior in the months before default to identify early-warning patterns like increased lateness and partial payments. If the team can detect deterioration 3+ months ahead, it can offer restructuring options, reducing losses and preserving the customer relationship.

**Category:** CTE + Join
**Difficulty:** Advanced
**Business role:** Analyst

**Approach:**
To examine repayment deterioration in the 90 days before default, three tables need to be joined: `default_event` (for the default date), `payment` (actual repayment behavior), and `repayment_schedule` (the scheduled amount, used to compute paid-to-scheduled ratio). CTE `default_loan_payments` first flattens "every payment in the 0–90 day window before default" and computes `pct_of_scheduled` (paid / scheduled) and `days_before_default`. Note: the scheduled amount uses `rs.scheduled_payment` (per-installment) rather than `loan.monthly_payment`, so rounding differences in the last installment don't contaminate the percentage. The outer query aggregates per loan: average lateness, max lateness, count of problem payments, with `HAVING payments_in_90_days_prior >= 2` filtering out loans with too little evidence. A CTE is used here to separate "time-window filter + derived columns" from "aggregation" into two clean logical steps.

```sql
-- Analyze payment behavior patterns in the 3 months before defaults.
-- Uses rs.scheduled_payment (per-installment) rather than l.monthly_payment so
-- the % calculation is robust to last-installment rounding differences.
WITH default_loan_payments AS (
    SELECT
        de.loan_id,
        de.default_date,
        p.payment_date,
        p.installment_number,
        p.days_late,
        p.payment_amount,
        rs.scheduled_payment,
        ROUND(100.0 * p.payment_amount / rs.scheduled_payment, 2) AS pct_of_scheduled,
        JULIANDAY(de.default_date) - JULIANDAY(p.payment_date) AS days_before_default
    FROM default_event de
    JOIN payment p ON de.loan_id = p.loan_id
    JOIN repayment_schedule rs ON p.loan_id = rs.loan_id AND p.installment_number = rs.installment_number
    WHERE JULIANDAY(de.default_date) - JULIANDAY(p.payment_date) BETWEEN 0 AND 90
)
SELECT
    loan_id,
    default_date,
    COUNT(*) AS payments_in_90_days_prior,
    AVG(days_late) AS avg_days_late,
    MAX(days_late) AS max_days_late,
    AVG(pct_of_scheduled) AS avg_pct_paid,
    COUNT(CASE WHEN days_late > 10 THEN 1 END) AS late_payment_count,
    COUNT(CASE WHEN pct_of_scheduled < 95 THEN 1 END) AS partial_payment_count
FROM default_loan_payments
GROUP BY loan_id, default_date
HAVING payments_in_90_days_prior >= 2
ORDER BY max_days_late DESC, avg_pct_paid ASC
LIMIT 20;
```

**Expected output:**
Returns aggregated repayment metrics for defaulted loans in the 90 days before default: average lateness, max lateness, paid-to-scheduled ratio, problem payment count. In this dataset, defaulted loans average ~12.5 days late and ~90% paid-to-scheduled in the final 3 installments, versus ~4 days and ~98.5% for the broader population — the deterioration is plainly visible. About ~70% of defaults show clear warning signals (`default_event.had_early_warning` flag tracks the same group). Loans with `avg_days_late > 10` or `avg_pct_paid < 90%` are strong candidates for early intervention. Supports Q4 (early warning signals) and informs the build of a predictive monitoring dashboard.

---

### Query 5: Customer Lifecycle Value Comparison

**Business context:**
The CEO is reviewing customer acquisition strategy and budget allocation. The marketing team wants to invest heavily in digital advertising to acquire new customers, but the CFO argues that doubling down on repeat business from existing customers is likely more profitable. This analysis compares repeat customers (those with multiple loans) against new customers on key metrics: default rate, average loan amount, approval rate. Understanding lifecycle value differences helps the executive team decide how to split the $2M annual marketing budget.

**Category:** Aggregation + Join
**Difficulty:** Intermediate
**Business role:** Executive

**Approach:**
The tricky part is that "customer-level metrics" and "loan-level metrics" aggregate at different grains and cannot be combined in a single GROUP BY. A customer with multiple loans must count their credit score once, otherwise it gets weighted by loan count in the average. So use two CTEs: `customer_agg` aggregates customer count and average credit score by `is_repeat_customer` (grain = customer); `loan_agg` aggregates application count, loan count, default count, and amounts at the same dimension (grain = loan, with LEFT JOIN to keep customers without loans). Finally the two CTEs are joined on `is_repeat_customer` to produce two rows (repeat vs. new) for comparison. Computing the two grains separately and joining is the standard technique to avoid double-counting.

```sql
-- Compare performance metrics between repeat and first-time customers.
-- Customer-level metrics (count, credit score) are computed in a CTE keyed by
-- customer so a multi-loan customer's credit score isn't double-counted in
-- the average. Loan/default metrics come from a separate aggregate.
WITH customer_agg AS (
    SELECT
        is_repeat_customer,
        COUNT(*) AS total_customers,
        ROUND(AVG(credit_score), 0) AS avg_credit_score
    FROM customer
    GROUP BY is_repeat_customer
),
loan_agg AS (
    SELECT
        c.is_repeat_customer,
        COUNT(DISTINCT a.id) AS total_applications,
        COUNT(DISTINCT l.id) AS total_loans,
        COUNT(de.id) AS defaults,
        ROUND(AVG(l.approved_amount), 2) AS avg_loan_amount,
        ROUND(SUM(l.outstanding_balance), 2) AS total_outstanding
    FROM customer c
    LEFT JOIN application a ON c.id = a.customer_id
    LEFT JOIN loan l ON a.id = l.application_id
    LEFT JOIN default_event de ON l.id = de.loan_id
    GROUP BY c.is_repeat_customer
)
SELECT
    ca.is_repeat_customer,
    CASE WHEN ca.is_repeat_customer = 1 THEN 'Repeat Customer' ELSE 'First-Time Customer' END AS customer_type,
    ca.total_customers,
    la.total_applications,
    la.total_loans,
    ROUND(100.0 * la.total_loans / la.total_applications, 2) AS approval_rate_pct,
    la.avg_loan_amount,
    la.total_outstanding,
    la.defaults,
    ROUND(100.0 * la.defaults / la.total_loans, 2) AS default_rate_pct,
    ca.avg_credit_score
FROM customer_agg ca
JOIN loan_agg la USING (is_repeat_customer)
ORDER BY ca.is_repeat_customer DESC;
```

**Expected output:**
Returns two rows comparing repeat vs. new customers across all key metrics. In this dataset, repeat customers default at ~5% versus new customers at ~11% (roughly a 2x gap), have markedly higher credit scores (~50–80 points higher), and take larger average loans. Repeat customers are only ~12% of the customer base but drive a disproportionate share of low-risk volume. Supports Q5 (customer lifecycle value) and supports shifting marketing budget from acquisition toward retention.

---

### Query 6: Monthly Application Volume Trends

**Business context:**
The Operations Director needs to plan headcount for the underwriting team. Application volume has seasonal swings; understaffing during peak months causes slow decisions (hurting customer experience), while overstaffing during slow months wastes payroll budget. This query analyzes monthly application volume and approval rate over the past 2 years to identify patterns. These insights help the director schedule vacations during slow months, hire temporary contractors for peaks, and set realistic SLA targets for application processing.

**Category:** Date Aggregation
**Difficulty:** Basic
**Business role:** Operations

**Approach:**
The simplest type: time-series aggregation. Just join `application` with `loan_status` (to get the status name) and bucket applications by month with `strftime('%Y-%m', application_date)`. Approved / rejected counts use conditional aggregation `COUNT(CASE WHEN ... THEN 1 END)` (CASE returns NULL when the condition fails, COUNT ignores NULL, so this is conditional counting). `strftime` is a SQLite-specific date formatting function. One GROUP BY does the job — no need to join the loan fact table.

```sql
-- Track monthly application volume and approval rates over time
SELECT
    strftime('%Y-%m', a.application_date) AS month,
    COUNT(*) AS total_applications,
    COUNT(CASE WHEN ls.status_code = 'APPROVED' THEN 1 END) AS approved,
    COUNT(CASE WHEN ls.status_code = 'REJECTED' THEN 1 END) AS rejected,
    ROUND(100.0 * COUNT(CASE WHEN ls.status_code = 'APPROVED' THEN 1 END) / COUNT(*), 2) AS approval_rate_pct,
    ROUND(SUM(a.requested_amount), 2) AS total_requested_amount
FROM application a
JOIN loan_status ls ON a.status_id = ls.id
WHERE a.application_date IS NOT NULL
GROUP BY strftime('%Y-%m', a.application_date)
ORDER BY month ASC;
```

**Expected output:**
Returns a monthly time series: application count, approved/rejected count, approval rate, total requested amount. Can reveal seasonal patterns (e.g., Q1 slow, Q4 strong) plus any sudden shifts suggesting a policy change or economic cycle. The operations team uses it for 3–6 month headcount planning and to benchmark current performance against history.

---

### Query 7: Loan Officer Performance Scorecard

**Business context:**
The head of underwriting runs a quarterly performance review of all loan officers. She needs objective metrics to evaluate each officer's portfolio quality, productivity, and risk management. Strong performers should be rewarded and given more complex applications; underperformers may need extra training. This scorecard tracks application volume, approval rate, average loan amount, and default rate per officer. High approval combined with high defaults suggests lending may be too loose; extremely low approval suggests underwriting may be too tight.

**Category:** Aggregation + Join
**Difficulty:** Intermediate
**Business role:** Manager

**Approach:**
Per-officer performance scorecard. Join `loan_officer` with `application` (all the applications that officer touched), then LEFT JOIN to loan and default_event — LEFT is required because most applications have no matching loan (rejected) or no default (didn't default), but we need to keep those as denominators. Approval rate = `COUNT(loan.id) / COUNT(application.id)`; default rate uses `NULLIF(COUNT(loan.id), 0)` to prevent divide-by-zero. `HAVING applications_processed >= 10` filters out officers with too few applications for stable metrics. Aggregation grain is "one row per officer."

```sql
-- Generate performance scorecard for each loan officer
SELECT
    lo.employee_id,
    lo.first_name || ' ' || lo.last_name AS officer_name,
    lo.region,
    COUNT(a.id) AS applications_processed,
    COUNT(l.id) AS loans_approved,
    ROUND(100.0 * COUNT(l.id) / COUNT(a.id), 2) AS approval_rate_pct,
    ROUND(AVG(l.approved_amount), 2) AS avg_loan_size,
    ROUND(SUM(l.outstanding_balance), 2) AS total_portfolio_balance,
    COUNT(de.id) AS defaults,
    ROUND(100.0 * COUNT(de.id) / NULLIF(COUNT(l.id), 0), 2) AS default_rate_pct
FROM loan_officer lo
JOIN application a ON lo.id = a.loan_officer_id
LEFT JOIN loan l ON a.id = l.application_id
LEFT JOIN default_event de ON l.id = de.loan_id
GROUP BY lo.id, lo.employee_id, lo.first_name, lo.last_name, lo.region
HAVING applications_processed >= 10
ORDER BY applications_processed DESC;
```

**Expected output:**
One row per loan officer showing productivity (application volume), risk appetite (approval rate), portfolio size, and credit quality (default rate). The manager looks for a balanced profile: 70–75% approval + <10% default is a strong performer. Outliers in either direction warrant discussion. This data drives compensation decisions, regional assignments, and training priorities.

---

### Query 8: Repayment Behavior Cohort Analysis

**Business context:**
The analytics team is building a predictive model to identify loans at risk of default. One hypothesis: payment behavior patterns in the first 6 months (on-time / late / partial) have strong predictive power for long-term outcomes. This cohort analysis groups loans by early payment behavior and tracks default rate per cohort. If the data shows loans with a single late payment in the first 6 installments default at 3x the rate, the team can trigger proactive intervention immediately instead of waiting for multiple missed payments.

**Category:** CTE + Aggregation
**Difficulty:** Advanced
**Business role:** Analyst

**Approach:**
To validate the "first 6 installments predict default" hypothesis, the work breaks into three steps. CTE1 `early_payment_behavior` looks only at `installment_number <= 6`, counting on-time, late, and partial payments per loan, with `HAVING COUNT(*) >= 3` ensuring at least 3 installments are observable. CTE2 `cohort_classification` uses CASE to bin each loan into Perfect / Mostly On-Time / Problematic cohorts. Finally the cohort label is joined back to loan and default_event to compute default rate per cohort. Two CTEs are used because "compute behavior metrics → classify based on them → aggregate default rate" is three steps at three different grains, and chained CTEs keep each step independent and readable.

```sql
-- Analyze default rates by early payment behavior cohorts
WITH early_payment_behavior AS (
    SELECT
        p.loan_id,
        COUNT(*) AS payments_made,
        SUM(CASE WHEN p.days_late = 0 THEN 1 ELSE 0 END) AS on_time_count,
        SUM(CASE WHEN p.days_late > 0 THEN 1 ELSE 0 END) AS late_count,
        AVG(CASE WHEN p.days_late > 0 THEN p.days_late END) AS avg_late_days,
        SUM(CASE WHEN p.payment_amount < l.monthly_payment * 0.95 THEN 1 ELSE 0 END) AS partial_count
    FROM payment p
    JOIN loan l ON p.loan_id = l.id
    WHERE p.installment_number <= 6
    GROUP BY p.loan_id
    HAVING COUNT(*) >= 3
),
cohort_classification AS (
    SELECT
        loan_id,
        CASE
            WHEN late_count = 0 AND partial_count = 0 THEN 'Perfect'
            WHEN late_count <= 1 AND partial_count = 0 THEN 'Mostly On-Time'
            ELSE 'Problematic'
        END AS cohort
    FROM early_payment_behavior
)
SELECT
    cc.cohort,
    COUNT(DISTINCT l.id) AS total_loans,
    COUNT(de.id) AS defaults,
    ROUND(100.0 * COUNT(de.id) / COUNT(DISTINCT l.id), 2) AS default_rate_pct,
    ROUND(AVG(l.approved_amount), 2) AS avg_loan_amount
FROM cohort_classification cc
JOIN loan l ON cc.loan_id = l.id
LEFT JOIN default_event de ON l.id = de.loan_id
GROUP BY cc.cohort
ORDER BY default_rate_pct DESC;
```

**Expected output:**
Returns the default rate for the three repayment-behavior cohorts: Perfect (all on time), Mostly On-Time (at most 1 late), Problematic (2+ late or partial payments). Expect Problematic loans to default at 15-25%, dramatically higher than Perfect loans at 2-4%. This validates the "early warning" hypothesis and provides thresholds for auto-alerts in a monitoring system.

---

### Query 9: Top 10 High-Risk Active Loans

**Business context:**
The Chief Credit Officer needs to review the highest-risk exposures in the current portfolio at the weekly risk committee — typically large loans already showing late-payment signals, or high-risk-grade loans with significant outstanding balance. The committee discusses whether to raise reserves, reach out to borrowers, or consider selling loans to reduce concentration. This query identifies the top 10 loans by "risk-weighted exposure (balance × risk score)" requiring immediate attention.

**Category:** Join + Subquery
**Difficulty:** Intermediate
**Business role:** Operations

**Approach:**
Find the 10 highest-risk loans in the active portfolio. The main query joins loan with customer, industry, risk_grade, and loan_status to pull display fields, filtering on `status_code='CURRENT'` and balance > $50K. Risk-weighted exposure uses `outstanding_balance × implied_default_rate` as an expected-loss approximation. Recent payment behavior uses a **correlated subquery**: an inner subquery takes the loan's `MAX(installment_number) - 2` so we average `days_late` over only the last 3 installments. Correlated subqueries execute once per row; here, with `LIMIT 10` and a balance prefilter, the cost is acceptable. Order by expected loss descending, take the top 10.

```sql
-- Identify the highest risk outstanding loans requiring immediate attention
SELECT
    l.loan_number,
    c.business_name,
    i.industry_name,
    rg.grade_code AS risk_grade,
    l.outstanding_balance,
    l.disbursement_date,
    ROUND((JULIANDAY('2026-06-03') - JULIANDAY(l.disbursement_date)) / 30, 0) AS months_since_disbursement,
    (SELECT AVG(p2.days_late)
     FROM payment p2
     WHERE p2.loan_id = l.id AND p2.installment_number >=
           (SELECT MAX(p3.installment_number) - 2 FROM payment p3 WHERE p3.loan_id = l.id)
    ) AS avg_days_late_last_3,
    ls.status_name,
    ROUND(l.outstanding_balance * rg.implied_default_rate / 100, 2) AS expected_loss_amount
FROM loan l
JOIN customer c ON l.customer_id = c.id
JOIN industry i ON c.industry_id = i.id
JOIN risk_grade rg ON l.risk_grade_id = rg.id
JOIN loan_status ls ON l.current_status_id = ls.id
WHERE ls.status_code = 'CURRENT'
  AND l.outstanding_balance > 50000
ORDER BY expected_loss_amount DESC, avg_days_late_last_3 DESC
LIMIT 10;
```

**Expected output:**
Returns the 10 loans with the highest expected-loss exposure, computed as outstanding_balance × implied_default_rate. Includes recent payment behavior (average lateness on the last 3 installments) to flag loans already showing warning signals. Each listed loan represents a concentrated risk that may require provisioning, credit monitoring, or proactive outreach. The committee uses it to prioritize collections effort and to populate the investor risk update.

---

### Query 10: Default Recovery Rate by Risk Grade

**Business context:**
The CFO is preparing financial statements and needs to estimate the loss provision for the current loan portfolio. Loss provision depends on both default probability (which varies by risk grade) and loss severity (how much can be recovered after default). This query computes recovery rate per risk grade, showing the share of defaulted balance ultimately recovered via collections, asset disposition, and legal process. Low recovery rate means high required provisions, affecting the company's capital requirements and profitability.

**Category:** Aggregation + Join
**Difficulty:** Intermediate
**Business role:** Finance

**Approach:**
Only look at defaulted loans, so start from `default_event` (which by nature contains only default records), INNER JOIN loan and risk_grade to bring in the grade. Aggregate per grade: recovery rate = `SUM(recovery_amount) / SUM(outstanding_at_default)`, loss severity = `SUM(loss_amount) / SUM(outstanding_at_default)`. The two are complementary (sum to 1). Note this is amount-weighted (SUM/SUM) rather than averaging per-loan ratios, so large defaults have a more realistic impact on portfolio recovery rate. Grain is "one row per grade"; ordering by `rg.id` produces A→E order.

```sql
-- Calculate recovery rates on defaulted loans by risk grade
SELECT
    rg.grade_code,
    rg.grade_name,
    COUNT(de.id) AS total_defaults,
    ROUND(SUM(de.outstanding_at_default), 2) AS total_exposure_at_default,
    ROUND(SUM(de.recovery_amount), 2) AS total_recovered,
    ROUND(SUM(de.loss_amount), 2) AS total_net_loss,
    ROUND(100.0 * SUM(de.recovery_amount) / SUM(de.outstanding_at_default), 2) AS recovery_rate_pct,
    ROUND(100.0 * SUM(de.loss_amount) / SUM(de.outstanding_at_default), 2) AS loss_severity_pct,
    ROUND(AVG(de.recovery_amount), 2) AS avg_recovery_per_default,
    ROUND(AVG(de.loss_amount), 2) AS avg_loss_per_default
FROM default_event de
JOIN loan l ON de.loan_id = l.id
JOIN risk_grade rg ON l.risk_grade_id = rg.id
GROUP BY rg.id, rg.grade_code, rg.grade_name
ORDER BY rg.id;
```

**Expected output:**
Per risk grade, returns default count, exposure at default, recovery amount, net loss, recovery rate, and loss severity. In this dataset recovery rates form a clean monotonic gradient: Grade A recovers ~54% (good collateral, cooperative borrowers), B ~48%, C ~38%, D ~32%, E ~23% (limited assets, adversarial). Loss severity inverts the gradient (A ~46% → E ~77%). The CFO computes provisions per grade as `default_rate × loss_severity`; the sharp jump in severity at D/E explains why those tiers need both higher pricing and tighter loss reserves.

---

### Query 11: Regional Application Volume and Conversion Rate

**Business context:**
The Marketing Director is analyzing the loan pipeline's volume sources. Pacific Bridge assigns each loan officer to a California region (Northern CA, Southern CA, Bay Area, Central Valley); this query uses the loan officer's region as a proxy for "customer region" because `loan_officer.region` is a clean enum while `customer.city` is free text and hard to aggregate. Output quantifies application volume, conversion (approval) rate, and default rate per region — these are the inputs needed (combined with externally tracked marketing spend) to compute customer acquisition cost (CAC). The query itself doesn't compute CAC because the dataset has no region-level marketing spend.

**Category:** Aggregation + Join
**Difficulty:** Basic
**Business role:** Finance

**Approach:**
Use loan-officer region as a proxy for customer region because `loan_officer.region` is a clean enum while `customer.city` is free text and hard to roll up. From loan_officer join application, then LEFT JOIN loan / default_event to preserve rejected and non-defaulted denominators. Conversion rate = `COUNT(DISTINCT loan) / COUNT(DISTINCT application)`. DISTINCT prevents fan-out double-counting. Aggregate by region, order by total volume descending. Key point: this query produces only the CAC **denominator** (application volume), not CAC itself — the dataset doesn't include region-level marketing spend.

```sql
-- Analyze application and loan volume by loan officer region (proxy for customer region)
SELECT
    lo.region,
    COUNT(DISTINCT a.id) AS total_applications,
    COUNT(DISTINCT l.id) AS approved_loans,
    ROUND(100.0 * COUNT(DISTINCT l.id) / COUNT(DISTINCT a.id), 2) AS conversion_rate_pct,
    ROUND(AVG(l.approved_amount), 2) AS avg_loan_size,
    ROUND(SUM(l.approved_amount), 2) AS total_loan_volume,
    COUNT(de.id) AS defaults,
    ROUND(100.0 * COUNT(de.id) / NULLIF(COUNT(DISTINCT l.id), 0), 2) AS default_rate_pct
FROM loan_officer lo
JOIN application a ON lo.id = a.loan_officer_id
LEFT JOIN loan l ON a.id = l.application_id
LEFT JOIN default_event de ON l.id = de.loan_id
GROUP BY lo.region
ORDER BY total_loan_volume DESC;
```

**Expected output:**
Per region, returns: application volume, conversion rate (approval %), average loan size, total loan volume, default rate. High volume with low conversion may indicate loose lead quality or overly tight underwriting; high default may need risk-adjusted pricing. The marketing team uses `total_applications` as the denominator, divided by region-level marketing spend pulled from an external system, to get true customer acquisition cost. This query provides the denominator.

---

### Query 12: Repeat-Customer Retention Metrics

**Business context:**
The Customer Success team wants to roll out a retention program targeting "customers whose loans are about to mature." If the company can convert 30% of maturing loans into renewals or new loans, the repeat-customer base will grow significantly — and since repeat customers default at ~5% versus new at ~11%, the lifecycle economics are dramatically different. This query identifies customers who had a loan paid off in the last 12 months but haven't submitted a new application in the last 6 months — the retention opportunity pool.

> **Cohort definition note:** this query *operationally* defines "retention opportunity" as `most recent PAID_OFF maturity date within 12 months AND no application in the last 6 months`. This is different from the `customer.is_repeat_customer` tier flag used in Q5 / Q20 (set by marketing at onboarding). The two populations overlap but aren't identical.

**Category:** CTE + Join
**Difficulty:** Advanced
**Business role:** Manager

**Approach:**
Find "took out a loan but didn't come back" retention-opportunity customers. CTE1 `completed_loans` pulls each customer with a PAID_OFF loan and their most recent maturity date. CTE2 `recent_applications` pulls customers who applied in the last 6 months (using `DATE('2026-06-03', '-6 months')` anchored to the reference date). The main query LEFT JOINs the two and uses `CASE WHEN ra.customer_id IS NOT NULL THEN 'Re-engaged' ELSE 'Dormant'` to label whether they've re-engaged, and filters to most recent maturity within 12 months. LEFT JOIN + IS NULL check is the standard pattern for "in A but not in B." Note: "retention opportunity" here is an operational definition (PAID_OFF within last 12 months and no application in last 6 months), different from the `is_repeat_customer` flag — the two populations overlap but aren't identical.

```sql
-- Identify customers who completed a loan but haven't returned for repeat business.
-- Dates are anchored to REFERENCE_DATE '2026-06-03' for deterministic results.
WITH completed_loans AS (
    SELECT
        c.id AS customer_id,
        c.business_name,
        c.industry_id,
        MAX(l.maturity_date) AS last_maturity_date,
        COUNT(l.id) AS total_loans_taken
    FROM customer c
    JOIN loan l ON c.id = l.customer_id
    JOIN loan_status ls ON l.current_status_id = ls.id
    WHERE ls.status_code = 'PAID_OFF'
    GROUP BY c.id, c.business_name, c.industry_id
),
recent_applications AS (
    SELECT DISTINCT customer_id
    FROM application
    WHERE application_date >= DATE('2026-06-03', '-6 months')
)
SELECT
    cl.customer_id,
    cl.business_name,
    i.industry_name,
    cl.last_maturity_date,
    ROUND((JULIANDAY('2026-06-03') - JULIANDAY(cl.last_maturity_date)) / 30, 0) AS months_since_completion,
    cl.total_loans_taken,
    CASE WHEN ra.customer_id IS NOT NULL THEN 'Re-engaged' ELSE 'Dormant' END AS status
FROM completed_loans cl
JOIN industry i ON cl.industry_id = i.id
LEFT JOIN recent_applications ra ON cl.customer_id = ra.customer_id
WHERE cl.last_maturity_date >= DATE('2026-06-03', '-12 months')
ORDER BY cl.last_maturity_date ASC;
```

**Expected output:**
Returns customers who successfully paid off a loan in the last 12 months and labels whether they've recently applied again. "Dormant" customers are the retention opportunity pool — they've already proven they're good borrowers (loan paid off) but aren't being kept warm. The Customer Success team sends personalized offers (larger amount, better rate) to dormant customers to drive repeat business. Converting 100 dormant customers could deliver $15-20M of new loan volume.

---

### Query 13: Portfolio Vintage Analysis

**Business context:**
The Investment Committee reviews loan performance by origination cohort (vintage) to understand how credit quality and pricing have evolved over time. Loans originated in different periods are influenced by economic conditions, underwriting policy changes, and risk appetite shifts, and behave differently. This vintage analysis aggregates loans by origination quarter and tracks default rate, showing whether recent underwriting is tighter or looser. Deteriorating vintage performance is an early warning of systemic credit quality issues.

**Category:** Date + Aggregation
**Difficulty:** Intermediate
**Business role:** Analyst

**Approach:**
Cohort performance by origination quarter (vintage). SQLite's `strftime` has no `%Q` (quarter) specifier, so quarter must be computed from month: `(CAST(strftime('%m', date) AS INTEGER) - 1) / 3 + 1`, then concatenated with year to produce labels like `2024-Q1`. From loan join loan_status, LEFT JOIN default_event to preserve non-defaulted loans. Group by the computed `origination_quarter` and compute default rate and payoff rate. Key point: recent quarters have insufficient maturity and not enough repayment time, so default rate is naturally lower — comparing **trend** (quarter-over-quarter at the same maturity) matters more than absolute level.

```sql
-- Analyze loan performance by origination vintage (quarter).
-- SQLite has no %Q strftime format specifier — quarter number is computed
-- explicitly from the month: ((month - 1) / 3) + 1.
SELECT
    strftime('%Y', l.disbursement_date) || '-Q' ||
        ((CAST(strftime('%m', l.disbursement_date) AS INTEGER) - 1) / 3 + 1) AS origination_quarter,
    COUNT(l.id) AS loans_originated,
    ROUND(SUM(l.approved_amount), 2) AS total_volume,
    ROUND(AVG(l.approved_amount), 2) AS avg_loan_size,
    ROUND(AVG(l.interest_rate), 2) AS avg_interest_rate,
    COUNT(de.id) AS defaults,
    ROUND(100.0 * COUNT(de.id) / COUNT(l.id), 2) AS default_rate_pct,
    ROUND(SUM(CASE WHEN ls.status_code = 'PAID_OFF' THEN 1 ELSE 0 END) * 100.0 / COUNT(l.id), 2) AS payoff_rate_pct
FROM loan l
JOIN loan_status ls ON l.current_status_id = ls.id
LEFT JOIN default_event de ON l.id = de.loan_id
GROUP BY origination_quarter
ORDER BY origination_quarter DESC;
```

**Expected output:**
Returns per-quarter cohorts: originations, average loan characteristics, default rate, payoff rate. Recent quarters have limited maturity (insufficient repayment time), so default rates look low — trend matters more than absolute level. If 2024-Q1 shows 12% default at the same maturity at which 2023-Q1 was 8%, that signals deteriorating credit quality. The committee uses it to judge whether current underwriting standards are sufficient or need to be tightened.

---

### Query 14: Late Payment Trend Analysis

**Business context:**
The Collections Manager tracks late-payment rate month by month to detect early portfolio stress before defaults materialize. A rise in lateness (even just 5-15 days) typically leads default by 6-12 months, giving the team an intervention window. This trend analysis shows the monthly late-payment share and average days late, and whether the situation is improving or deteriorating. Rising late rates may signal economic headwinds affecting borrowers and may call for tighter underwriting or additional collections headcount.

**Category:** Date Aggregation
**Difficulty:** Intermediate
**Business role:** Operations

**Approach:**
Track late-payment rate by month. payment joins repayment_schedule on the **two-column key** `loan_id + installment_number` to pick up the scheduled amount for partial-payment detection. Bucket by month with `strftime('%Y-%m', payment_date)`, late buckets via conditional aggregation (0 days / 1–15 days / 16–30 days). Partial-payment rate = share where actual < scheduled × 0.95. `WHERE payment_date >= DATE('2026-06-03', '-12 months')` anchors to the reference date for a trailing 12-month window. The two-column join is critical — joining only on `loan_id` would cross-multiply each loan's many schedule rows against its many payment rows (fan-out), giving completely wrong counts.

```sql
-- Track late payment rates and severity trends by month. Anchored to
-- REFERENCE_DATE '2026-06-03'.
SELECT
    strftime('%Y-%m', p.payment_date) AS payment_month,
    COUNT(*) AS total_payments,
    COUNT(CASE WHEN p.days_late = 0 THEN 1 END) AS on_time,
    COUNT(CASE WHEN p.days_late BETWEEN 1 AND 15 THEN 1 END) AS late_1_15_days,
    COUNT(CASE WHEN p.days_late BETWEEN 16 AND 30 THEN 1 END) AS late_16_30_days,
    ROUND(100.0 * COUNT(CASE WHEN p.days_late > 0 THEN 1 END) / COUNT(*), 2) AS late_payment_rate_pct,
    ROUND(AVG(CASE WHEN p.days_late > 0 THEN p.days_late END), 2) AS avg_days_late_when_late,
    ROUND(100.0 * SUM(CASE WHEN p.payment_amount < rs.scheduled_payment * 0.95 THEN 1 ELSE 0 END) / COUNT(*), 2) AS partial_payment_rate_pct
FROM payment p
JOIN repayment_schedule rs ON p.loan_id = rs.loan_id AND p.installment_number = rs.installment_number
WHERE p.payment_date >= DATE('2026-06-03', '-12 months')
GROUP BY payment_month
ORDER BY payment_month ASC;
```

**Expected output:**
Returns a monthly time series: payment counts by lateness bucket and partial-payment rate. The collections team looks for trends: if the late rate climbs from 25% to 35% over 3 months, it's a portfolio stress signal that demands action. Conversely, falling late rates indicate improving portfolio health. This feeds the monthly executive dashboard and drives collections team staffing.

---

### Query 15: Loan Amount vs. Credit Score Correlation

**Business context:**
The underwriting team is reviewing the loan-amount policy. The current policy permits loans up to 2x annual revenue, but the team suspects large loans to low-credit-score borrowers underperform. This analysis examines the relationship between approved amount, customer credit score, and default outcome. If the data shows borrowers with credit score <680 default at 20%+ when borrowing >$300K, then the policy should add a credit-score requirement to the loan-amount formula, not just rely on revenue.

**Category:** Aggregation
**Difficulty:** Basic
**Business role:** Analyst

**Approach:**
Do a "credit score × loan amount" crosstab. loan joins customer for the credit score, LEFT JOIN default_event to keep non-defaulted loans. Two CASE expressions bucket credit score into 4 bands and loan amount into 4 bands, then `GROUP BY` the two derived columns to produce up to 16 cells, each with a default rate. This is the classic "use CASE for dynamic bucketing, then aggregate." SQLite allows referencing SELECT aliases directly in GROUP BY, which saves restating the CASE.

```sql
-- Analyze relationship between loan amounts, credit scores, and default rates
SELECT
    CASE
        WHEN c.credit_score < 640 THEN 'Below 640'
        WHEN c.credit_score BETWEEN 640 AND 679 THEN '640-679'
        WHEN c.credit_score BETWEEN 680 AND 719 THEN '680-719'
        WHEN c.credit_score >= 720 THEN '720+'
    END AS credit_score_bucket,
    CASE
        WHEN l.approved_amount < 100000 THEN 'Under $100K'
        WHEN l.approved_amount BETWEEN 100000 AND 199999 THEN '$100K-$199K'
        WHEN l.approved_amount BETWEEN 200000 AND 299999 THEN '$200K-$299K'
        WHEN l.approved_amount >= 300000 THEN '$300K+'
    END AS loan_size_bucket,
    COUNT(l.id) AS loan_count,
    ROUND(AVG(l.approved_amount), 2) AS avg_loan_amount,
    COUNT(de.id) AS defaults,
    ROUND(100.0 * COUNT(de.id) / COUNT(l.id), 2) AS default_rate_pct
FROM loan l
JOIN customer c ON l.customer_id = c.id
LEFT JOIN default_event de ON l.id = de.loan_id
GROUP BY credit_score_bucket, loan_size_bucket
ORDER BY credit_score_bucket, loan_size_bucket;
```

**Expected output:**
Returns the credit-score × loan-amount crosstab with default rate per cell. Expected pattern: large loans ($300K+) to low-credit-score (<680) borrowers default disproportionately (15-20%), while large loans to high-credit-score (720+) borrowers perform well (3-5%). This informs implementing tiered loan-amount caps by credit score, e.g. <640 cap $150K, 640-719 cap $250K, 720+ cap $500K.

---

### Query 16: Risk-Grade Repricing Opportunities

**Business context:**
The Relationship Manager wants to identify active borrowers whose *current* credit profile is better than where their loan was originally graded — either the original underwriting was conservative, or the customer's credit profile has been refreshed since funding. These customers may qualify for refinancing at a lower rate, generating goodwill and preventing competitors from picking them off with refi offers. A customer originally priced at Grade C (9.5% rate) whose current score has reached Grade B (7.5%) saves several thousand dollars a year on a $200K loan.

> **Schema note:** the dataset only stores each customer's *current* `credit_score` (one value per customer); there's no historical time series. This query therefore detects borrowers whose current `credit_score` exceeds the upper bound of the grade their loan was assigned. If you re-run the query a few months later, the same set will be detected again unless `credit_score` is updated.

**Category:** Subquery + Join
**Difficulty:** Advanced
**Business role:** Manager

**Approach:**
Find repricing candidates whose current credit score has surpassed the upper bound of their original grade. The main table is loan, joined to customer (for current credit score), risk_grade (for original grade's rate), and loan_status (filtering on CURRENT). The "currently qualified grade / rate" is a **scalar subquery**: `(SELECT grade_code FROM risk_grade WHERE c.credit_score BETWEEN min AND max)` — looking up what grade the current score now qualifies for. Filter on `credit_score > rg_current.max_credit_score + 10` — score at least 10 points above the original grade's upper bound. Potential annual savings = balance × rate differential. Note: the dataset stores only customers' **current** credit score (no historical time series), so this detects scores currently above the original grade's ceiling. Re-running months later would hit the same set again.

```sql
-- Identify borrowers whose current credit profile qualifies for better risk grade
SELECT
    l.loan_number,
    c.business_name,
    c.credit_score AS current_credit_score,
    rg_current.grade_code AS loan_risk_grade,
    rg_current.interest_rate AS current_rate,
    (SELECT rg2.grade_code
     FROM risk_grade rg2
     WHERE c.credit_score BETWEEN rg2.min_credit_score AND rg2.max_credit_score) AS qualified_grade,
    (SELECT rg2.interest_rate
     FROM risk_grade rg2
     WHERE c.credit_score BETWEEN rg2.min_credit_score AND rg2.max_credit_score) AS qualified_rate,
    l.outstanding_balance,
    l.term_months,
    ROUND(l.outstanding_balance * (rg_current.interest_rate -
          (SELECT rg2.interest_rate FROM risk_grade rg2
           WHERE c.credit_score BETWEEN rg2.min_credit_score AND rg2.max_credit_score)) / 100, 2) AS potential_annual_savings
FROM loan l
JOIN customer c ON l.customer_id = c.id
JOIN risk_grade rg_current ON l.risk_grade_id = rg_current.id
JOIN loan_status ls ON l.current_status_id = ls.id
WHERE ls.status_code = 'CURRENT'
  AND l.outstanding_balance > 50000
  AND c.credit_score > rg_current.max_credit_score + 10
ORDER BY potential_annual_savings DESC
LIMIT 30;
```

**Expected output:**
Returns current loans whose customers' credit score exceeds the upper bound of their original risk grade by at least 10 points, indicating they qualify for a better grade. Shows potential annual interest savings after refinancing. Customers with savings >$2,000 are high-priority outreach targets. The Relationship Manager calls these customers to offer refinancing, boosting retention and sending the signal that "Pacific Bridge rewards good repayment behavior."

---

### Query 17: Monthly Cash Flow Projection

**Business context:**
The CFO needs to forecast monthly cash inflows from loan repayments for the next 12 months in order to manage the company's liquidity and funding needs. Pacific Bridge funds loans through a line of credit, which requires maintaining a minimum cash reserve. By projecting expected repayments on the existing portfolio, the CFO can determine when to draw on the credit line, when to repay, and how much room remains for new originations. Missed cash forecasts can lead to liquidity squeezes or expensive emergency borrowing.

**Category:** Aggregation + Date
**Difficulty:** Intermediate
**Business role:** Finance

**Approach:**
Project cash flow for the next 12 months. Use `repayment_schedule` directly (it represents scheduled receivables, i.e., expected inflows), joined to loan / loan_status to keep only `CURRENT` loans (paid-off and defaulted loans no longer contribute cash flow). `WHERE due_date BETWEEN '2026-06-03' AND '+12 months'` takes the forward window. Aggregate `SUM(scheduled_payment)` by month and split into principal / interest portions. Grain is "one row per future month." Key point: use the schedule table, not the actual `payment` table, because we're projecting "future receivables" and the future has no actual payment records yet.

```sql
-- Project expected monthly cash inflows from scheduled loan repayments.
-- Anchored to REFERENCE_DATE '2026-06-03'. Only CURRENT loans contribute —
-- the DISBURSED status code exists in the lookup but isn't used in this
-- dataset (loans transition directly to CURRENT after disbursement).
SELECT
    strftime('%Y-%m', rs.due_date) AS month,
    COUNT(DISTINCT rs.loan_id) AS loans_with_payments_due,
    COUNT(rs.id) AS total_installments_due,
    ROUND(SUM(rs.scheduled_payment), 2) AS expected_total_payment,
    ROUND(SUM(rs.principal_portion), 2) AS expected_principal,
    ROUND(SUM(rs.interest_portion), 2) AS expected_interest,
    ROUND(AVG(rs.scheduled_payment), 2) AS avg_payment_per_loan
FROM repayment_schedule rs
JOIN loan l ON rs.loan_id = l.id
JOIN loan_status ls ON l.current_status_id = ls.id
WHERE rs.due_date BETWEEN DATE('2026-06-03') AND DATE('2026-06-03', '+12 months')
  AND ls.status_code = 'CURRENT'
GROUP BY month
ORDER BY month ASC;
```

**Expected output:**
Returns a 12-month forward projection of expected payments, split into principal and interest components, showing expected total inflows and the number of active loans. The CFO compares it against committed new originations (outflows) to compute net cash position. If any month shows net negative cash, the company needs to arrange funding in advance. The projection is updated weekly as new loans are funded and old loans mature.

---

### Query 18: Application Processing Time Analysis

**Business context:**
The VP of Operations set a "respond to loan applications within 7 business days" target. Slow turnaround hurts customer satisfaction and increases the risk that applicants take their business to a competitor. This analysis measures time from application submission to decision, identifying bottlenecks. If certain officers or industries consistently take longer, the operations team can investigate whether the cause is complexity, workload imbalance, or inefficiency. Cutting turnaround from 10 days to 5 days is expected to lift the "approved → funded" conversion rate by 15%.

**Category:** Date Calculation
**Difficulty:** Basic
**Business role:** Operations

**Approach:**
Measure application processing time. application joins loan_officer, processing days = `JULIANDAY(decision_date) - JULIANDAY(application_date)` (`JULIANDAY` converts a date to a subtractable Julian day number — the standard SQLite approach for date differences). SLA compliance uses conditional counting `COUNT(CASE WHEN diff <= 7 THEN 1 END)`. `WHERE decision_date IS NOT NULL` excludes undecided applications, `HAVING >= 20` filters out officers with too-small samples. Aggregate per officer, order by average duration descending to surface the slowest first.

```sql
-- Measure application processing times from submission to decision
SELECT
    lo.employee_id,
    lo.first_name || ' ' || lo.last_name AS officer_name,
    COUNT(a.id) AS applications_processed,
    ROUND(AVG(JULIANDAY(a.decision_date) - JULIANDAY(a.application_date)), 1) AS avg_days_to_decision,
    MIN(JULIANDAY(a.decision_date) - JULIANDAY(a.application_date)) AS min_days,
    MAX(JULIANDAY(a.decision_date) - JULIANDAY(a.application_date)) AS max_days,
    COUNT(CASE WHEN JULIANDAY(a.decision_date) - JULIANDAY(a.application_date) <= 7 THEN 1 END) AS within_sla,
    ROUND(100.0 * COUNT(CASE WHEN JULIANDAY(a.decision_date) - JULIANDAY(a.application_date) <= 7 THEN 1 END) / COUNT(a.id), 2) AS sla_compliance_pct
FROM application a
JOIN loan_officer lo ON a.loan_officer_id = lo.id
WHERE a.decision_date IS NOT NULL
  AND a.application_date IS NOT NULL
GROUP BY lo.id, lo.employee_id, lo.first_name, lo.last_name
HAVING applications_processed >= 20
ORDER BY avg_days_to_decision DESC;
```

**Expected output:**
Per loan officer, returns turnaround metrics: average/min/max days from application to decision and SLA compliance rate. Officers with `avg_days_to_decision > 10` or SLA compliance < 70% need training or workload rebalancing. The operations team tracks this monthly and sets individual performance targets. Industry benchmark is 5-7 days; Pacific Bridge targets 90%+ SLA compliance.

---

### Query 19: Industry-Specific Default Patterns

**Business context:**
The CRO is preparing for an investor meeting and needs to explain the portfolio's industry exposure and associated risks. Investors are particularly worried about cyclical industries like restaurants and hospitality that struggled in the pandemic. This query analyzes default rate, loss severity, and concentration per industry, enabling the CRO to articulate which industries carry the most risk and what actions are being taken (industry caps, higher pricing, enhanced monitoring). Demonstrating active risk management reassures investors and stabilizes funding cost.

**Category:** CTE + Aggregation
**Difficulty:** Advanced
**Business role:** Executive

**Approach:**
Deep dive into default and loss patterns by industry. The CTE `industry_performance` chains `industry → customer → loan → default_event` (LEFT JOIN on loan and default to preserve industries with no loans or no defaults), aggregating per industry: loan count, exposure, default count, and losses. The outer query then computes each industry's share of the portfolio (using `(SELECT SUM(current_outstanding) FROM industry_performance)` to reference the CTE itself for the global denominator) and the deviation `actual default rate − historical baseline`. Putting the aggregation in a CTE and the share-of-total in the outer query is necessary because the share calculation needs the per-industry exposures as an intermediate result before computing the global total.

```sql
-- Deep dive into default patterns and losses by industry
WITH industry_performance AS (
    SELECT
        i.industry_name,
        i.default_rate_baseline,
        COUNT(DISTINCT l.id) AS total_loans,
        ROUND(SUM(l.approved_amount), 2) AS total_originated,
        ROUND(SUM(l.outstanding_balance), 2) AS current_outstanding,
        COUNT(de.id) AS defaults,
        ROUND(100.0 * COUNT(de.id) / COUNT(DISTINCT l.id), 2) AS actual_default_rate_pct,
        ROUND(SUM(de.loss_amount), 2) AS total_losses,
        ROUND(AVG(de.loss_amount), 2) AS avg_loss_per_default
    FROM industry i
    JOIN customer c ON i.id = c.industry_id
    LEFT JOIN loan l ON c.id = l.customer_id
    LEFT JOIN default_event de ON l.id = de.loan_id
    GROUP BY i.id, i.industry_name, i.default_rate_baseline
)
SELECT
    industry_name,
    default_rate_baseline AS historical_baseline_pct,
    total_loans,
    current_outstanding,
    ROUND(100.0 * current_outstanding / (SELECT SUM(current_outstanding) FROM industry_performance), 2) AS pct_of_portfolio,
    defaults,
    actual_default_rate_pct,
    ROUND(actual_default_rate_pct - default_rate_baseline, 2) AS performance_vs_baseline,
    total_losses,
    avg_loss_per_default
FROM industry_performance
WHERE total_loans > 0
ORDER BY current_outstanding DESC;
```

**Expected output:**
Returns comprehensive per-industry performance metrics: current exposure, actual default rate vs. historical baseline, total losses, average loss per default. Industries with actual default materially above baseline (e.g., Hospitality at 15% vs. 12.4% baseline) are underperforming and may need pricing adjustments or exposure caps. The CRO uses this to demonstrate to investors that the company understands industry risk and actively manages concentration.

---

### Query 20: Customer Segmentation by LTV

**Business context:**
The CEO wants to roll out a tiered customer service model — high-value customers get white-glove service (dedicated account manager, priority processing), low-value customers go through self-service channels. This segmentation computes each customer's lifetime value (LTV) from total borrowed volume, interest paid, and default history. Customers with $500K+ total borrowing and zero defaults are "Platinum"; single-loan customers under $100K are "Standard." This guides resource allocation across the Relationship Management and Customer Success teams.

**Category:** CTE + Window Function
**Difficulty:** Advanced
**Business role:** Executive

**Approach:**
Customer segmentation. CTE1 `customer_metrics` aggregates per customer: loan count, total borrowed, estimated lifetime interest, default count, completion rate. CTE2 `customer_ltv` adds `lifetime_value_score = total borrowed + estimated interest − defaults × 50000`. Finally a window function `NTILE(10) OVER (ORDER BY lifetime_value_score DESC)` divides customers into deciles by LTV, and a CASE assigns Platinum / Gold / Silver / Standard tiers. NTILE is a window function — it assigns each row a "which decile" label without collapsing rows, which GROUP BY can't do. Note: estimated interest uses a simple-interest approximation that overstates true amortized interest by about 2x; valid only for relative ranking, not actual interest accounting.

```sql
-- Segment customers by lifetime value and assign tiers
WITH customer_metrics AS (
    SELECT
        c.id AS customer_id,
        c.business_name,
        c.is_repeat_customer,
        COUNT(DISTINCT l.id) AS total_loans,
        ROUND(SUM(l.approved_amount), 2) AS total_borrowed,
        -- Rough lifetime-interest estimate using simple interest on the
        -- original principal — overstates true amortized interest by roughly
        -- 2x for typical 3-year loans. Acceptable for relative LTV ranking
        -- but not for actual interest accounting.
        ROUND(SUM(l.approved_amount * l.interest_rate / 100 * l.term_months / 12), 2) AS estimated_lifetime_interest,
        COUNT(de.id) AS defaults,
        ROUND(SUM(CASE WHEN ls.status_code = 'PAID_OFF' THEN 1 ELSE 0 END) * 100.0 / COUNT(l.id), 2) AS completion_rate_pct,
        ROUND(AVG(l.interest_rate), 2) AS avg_interest_rate
    FROM customer c
    LEFT JOIN loan l ON c.id = l.customer_id
    LEFT JOIN loan_status ls ON l.current_status_id = ls.id
    LEFT JOIN default_event de ON l.id = de.loan_id
    GROUP BY c.id, c.business_name, c.is_repeat_customer
    HAVING total_loans > 0
),
customer_ltv AS (
    SELECT
        *,
        ROUND(total_borrowed + estimated_lifetime_interest - (defaults * 50000), 2) AS lifetime_value_score
    FROM customer_metrics
)
SELECT
    customer_id,
    business_name,
    total_loans,
    total_borrowed,
    estimated_lifetime_interest,
    defaults,
    lifetime_value_score,
    CASE
        WHEN lifetime_value_score >= 500000 AND defaults = 0 THEN 'Platinum'
        WHEN lifetime_value_score >= 250000 AND defaults = 0 THEN 'Gold'
        WHEN lifetime_value_score >= 100000 OR is_repeat_customer = 1 THEN 'Silver'
        ELSE 'Standard'
    END AS customer_tier,
    NTILE(10) OVER (ORDER BY lifetime_value_score DESC) AS ltv_decile
FROM customer_ltv
ORDER BY lifetime_value_score DESC
LIMIT 100;
```

**Expected output:**
Returns the top 100 customers ranked by lifetime value score (total borrowed + interest − default losses), assigned to customer tiers (Platinum/Gold/Silver/Standard). Platinum customers (top 5-10%) get a dedicated account manager and proactive refinancing offers; Standard tier uses digital self-service. This segmentation drives resource allocation in the Customer Success team and also determines who's invited to exclusive events, early access to new products, and other VIP perks.

---

## Category Summary

Each query has one "primary category" tag (the SQL feature it mainly demonstrates). Most queries combine multiple techniques — the counts below reflect the primary category labeled at each query's header.

| Category | Count | Query numbers |
|----------|-------|---------------|
| Aggregation (+ Join) | 8 | 1, 2, 5, 7, 10, 11, 15, 19 |
| CTE (+ Join / Aggregation) | 4 | 4, 8, 12, 20 |
| Subquery (+ Join) | 2 | 3, 16 |
| Join + Subquery | 1 | 9 |
| Date / Time Aggregation | 4 | 6, 13, 14, 17 |
| Date Calculation | 1 | 18 |

## Business Role Coverage

| Role | Count | Query numbers |
|------|-------|---------------|
| Executive / C-Level | 4 | 1, 5, 19, 20 |
| Manager | 4 | 2, 7, 12, 16 |
| Analyst | 5 | 3, 4, 8, 13, 15 |
| Operations | 4 | 6, 9, 14, 18 |
| Finance | 3 | 10, 11, 17 |

## Difficulty Distribution

| Difficulty | Count | Query numbers |
|------------|-------|---------------|
| Basic | 4 | 6, 11, 15, 18 |
| Intermediate | 9 | 1, 2, 5, 7, 9, 10, 13, 14, 17 |
| Advanced | 7 | 3, 4, 8, 12, 16, 19, 20 |

---

## Notes

- All queries are written for SQLite 3.x syntax
- Date calculations use `JULIANDAY()` and `strftime()` functions (SQLite-specific)
- To port to PostgreSQL: replace `JULIANDAY()` differences with date subtraction and `strftime()` with `TO_CHAR()`
- To port to MySQL: use `DATEDIFF()` and `DATE_FORMAT()`
- TSV files referenced by the queries are numbered in topological order (01-10), which is also the safe load order
- All currency amounts are in USD, with 2 decimal places
- The queries are designed to answer the 5 core business questions of the Pacific Bridge Lending consulting project
