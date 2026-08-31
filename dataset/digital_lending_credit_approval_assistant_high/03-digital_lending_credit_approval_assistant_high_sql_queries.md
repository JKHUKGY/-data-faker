# Northpeak Lending AI Credit Approval Assistant SQL Query Playbook

This document is the SQL query playbook for the `digital_lending_credit_approval_assistant_high` dataset. It contains 20 business-oriented SQL queries. For business background, industry primer, and glossary, see `01-digital_lending_credit_approval_assistant_high_business_context.md`. For table structures and field meanings, see `02-digital_lending_credit_approval_assistant_high_er_document.md`.

---

## 1. Document Overview

Every query comes from a real Northpeak Lending role asking a real question in a real situation, and the result directly supports a business decision. The document serves three purposes at once: training corpus for Text-to-SQL, tool definitions for an LLM agent, and teaching material for analysts.

A note about the time anchor: this dataset is built on relative time and has no fixed `REFERENCE_DATE` constant, so the queries use SQLite's `DATE('now')` to read the current date dynamically rather than a hard-coded date literal. Treat "now" as "the day the query was executed." If you need strictly reproducible results, you can swap `DATE('now', '-30 days')` and similar expressions for fixed dates, but this playbook keeps the dynamic form to mirror how production dashboards actually run.

All queries target the SQLite database produced by the generator and use SQLite 3.x syntax (`DATE()`, `JULIANDAY()`, `strftime()`, etc.).

---

## 2. How to Use This Document

Imagine you've just joined Northpeak's Credit Risk Analytics team as an intern and your manager hands you this document, saying, "Work through these queries this week." This section tells you how to read it.

Each query is organized into the same five sections. Read them in order:

1. Business context. Who's asking, why they're asking now, and what decision the answer must support. Understand the question first; then look at the SQL.
2. Category / difficulty / business role. Three tags that help you see what SQL skills the query covers, how hard it is, and which role in the company it maps to.
3. Solution approach. Before looking at the SQL, understand which tables to touch, how to JOIN them, the grain of the aggregation, why a CTE or window function is needed, and what the pitfalls are. This is the core teaching content — if you understand it, you can write the SQL on your own.
4. SQL code. Ready to run against the database.
5. Expected results and business takeaway. What the result looks like, the ballpark of key numbers, and what the analyst should do with it. Remember: producing the result is the start of analysis, not the end.

Each query corresponds to at least one of the business questions (Q1 through Q5) from the business context document; a full mapping appears at the end. SQL is for reading and learning, not just running — when you see a LEFT JOIN, CTE, or window function, take an extra second to ask "why that one?"

---

## 3. Query Index

| # | Title | Business role | Category | Difficulty |
|---|-------|---------------|----------|------------|
| 1 | Daily Approval Rate Trend | Chief Risk Officer | Aggregation + Date | Intermediate |
| 2 | Product Performance Dashboard | Product Manager | Aggregation + Join | Basic |
| 3 | High-Risk Applications This Week | Risk Operations Manager | Join + Filter | Basic |
| 4 | Underwriter Workload Distribution | Director of Operations | Aggregation | Basic |
| 5 | Credit Score Distribution by Decision | Credit Risk Analyst | Aggregation + Join | Intermediate |
| 6 | Top Decline Reasons | Compliance Analyst | Aggregation + String | Intermediate |
| 7 | Average Time to Decision | Customer Experience Manager | Aggregation + Date | Intermediate |
| 8 | Revenue Forecast by Channel | FP&A Analyst | Aggregation + Join | Basic |
| 9 | Fraud Flag Resolution Rate | Fraud Operations Manager | Aggregation | Basic |
| 10 | Agent Similar-Case Lookup | AI Credit Assistant | Subquery + Join | Intermediate |
| 11 | Rule Trigger Frequency Analysis | Risk Policy Analyst | Aggregation + Join | Intermediate |
| 12 | Income Verification Gap Analysis | Compliance Manager | CTE + Join | Advanced |
| 13 | DTI Analysis by Product | Credit Risk Analyst | Aggregation + Conditional | Advanced |
| 14 | Application Funnel Conversion | CEO / COO | CTE | Advanced |
| 15 | Loan Volume by State | Regulatory Reporting Analyst | Aggregation + Join | Basic |
| 16 | Document Verification Backlog | Document Processing Manager | Filter + Join | Basic |
| 17 | AI Confidence vs. Actual Outcome | Data Science / ML Engineer | Join + Aggregation | Intermediate |
| 18 | Month-over-Month Application Growth | CEO / CFO | Window function | Advanced |
| 19 | Repeat Applicant Analysis | Marketing Analyst | Subquery + CTE | Intermediate |
| 20 | Risk Rule Effectiveness Analysis | Risk Policy Analyst | CTE + Join | Advanced |

---

## 4. Query Details

### Query 1: Daily Approval Rate Trend

**Business context:**
The first thing the Chief Risk Officer (CRO) checks every morning is the approval rate. Approval rate is the thermometer of a lending business: a sudden spike can mean the underwriting team or auto rules have loosened up; a sudden drop can mean a system failure, a miscalibrated policy change, or a market shift. The number shows up in the daily standup and the executive dashboard.

The CRO cares less about one day's number than about the trend: were there any unusual day-over-day jumps in the last 30 days? If a day's approval rate is more than 10 percentage points above or below its neighbors, she needs to call the underwriting lead immediately to find out what happened and, if necessary, roll back the rule change. This query maps to business question Q1 (Is approval healthy and stable?).

**Category / Difficulty / Role:** Aggregation + date analysis; Intermediate; Chief Risk Officer (CRO, CEO).

**Solution approach:**
You only need one table, `approval_decision`, with no joins. There are two tricky bits. One is daily aggregation: use `DATE(decision_at)` to truncate the timestamp to the day, then `GROUP BY` it. The other is computing the rate: approval is a boolean, so use `SUM(CASE WHEN is_approved = 1 THEN 1 ELSE 0 END)` to count approvals, divide by `COUNT(*)`, and multiply by 100 for percent. Be sure to multiply by `100.0` (float), not `100`, or SQLite's integer division will drop the decimals. Limit to the last 30 days with `decision_at >= DATE('now', '-30 days')`.

**SQL:**

```sql
-- Daily approval rate for the past 30 days
SELECT
    DATE(decision_at) AS decision_date,
    COUNT(*) AS total_decisions,
    SUM(CASE WHEN is_approved = 1 THEN 1 ELSE 0 END) AS approved_count,
    ROUND(100.0 * SUM(CASE WHEN is_approved = 1 THEN 1 ELSE 0 END) / COUNT(*), 2) AS approval_rate_pct
FROM approval_decision
WHERE decision_at >= DATE('now', '-30 days')
GROUP BY DATE(decision_at)
ORDER BY decision_date DESC;
```

**Expected result and business takeaway:**
One row per day, with total decisions, approval count, and approval percent. The overall approval rate should hover around 60% (the `approval_decision` definition). If a day's `approval_rate_pct` deviates from the overall average by more than 10 percentage points, the CRO will flag it in the standup, ask whether it's noise or real policy drift, and freeze related rule changes if needed.

---

### Query 2: Product Performance Dashboard

**Business context:**
The product manager is preparing the monthly product review and needs to report which loan products are performing well. She cares about three dimensions: application volume, approval rate, and average size. They directly affect product strategy, pricing, and where marketing budget is steered.

If a product has high volume but a low approval rate, customer acquisition and risk may be mismatched — wasting marketing dollars. If a product has a high approval rate but low volume, maybe it deserves more promotion. This query maps to business question Q2 (Which products and channels make money?).

**Category / Difficulty / Role:** Aggregation + join; Basic; Product Manager.

**Solution approach:**
Start from `loan_application`, join `loan_product` for the product name, and join `application_status` for the status code. Group by product. Use `COUNT` for volume and `SUM(CASE ...)` for approvals, treating both APPROVED and FUNDED as approved (this uses the status-based definition, not the `approval_decision` one — the two differ). Use `AVG` for average amounts, separately for requested and approved. INNER JOIN is fine here because every application has a product and a status.

**SQL:**

```sql
-- Loan product performance summary
SELECT
    p.name AS product_name,
    COUNT(la.id) AS application_count,
    SUM(CASE WHEN s.code = 'APPROVED' OR s.code = 'FUNDED' THEN 1 ELSE 0 END) AS approved_count,
    ROUND(100.0 * SUM(CASE WHEN s.code IN ('APPROVED', 'FUNDED') THEN 1 ELSE 0 END) / COUNT(*), 2) AS approval_rate,
    ROUND(AVG(la.requested_amount), 2) AS avg_requested_amount,
    ROUND(AVG(la.approved_amount), 2) AS avg_approved_amount
FROM loan_application la
JOIN loan_product p ON la.product_id = p.id
JOIN application_status s ON la.status_id = s.id
GROUP BY p.id, p.name
ORDER BY application_count DESC;
```

**Expected result and business takeaway:**
One row per product. Personal loans (PERSONAL) lead in volume (about 25%) with the smallest average size; mortgages have lower volume but the largest averages. The status-based approval rate hovers around 50%. The product manager uses this to decide which product to feature next quarter and which needs repricing or tighter eligibility. If a product's approval rate is clearly below its peers, it goes onto the product-review remediation list.

---

### Query 3: High-Risk Applications This Week

**Business context:**
The Risk Operations Manager starts each day by checking the high-risk queue: applications the automated system has tagged as high risk that have not yet been worked. Missing any of them can cause fraud losses or compliance issues.

She needs a sorted-by-risk-score list with applicant name, amount, and the AI recommendation, so she can dispatch the most urgent items to her team. This query maps to business question Q3 (risk policy) and day-to-day risk operations.

**Category / Difficulty / Role:** Join + filter; Basic; Risk Operations Manager.

**Solution approach:**
This is a typical multi-table join with filters. From `loan_application`, join `approval_decision` (for risk score and AI recommendation), `risk_level` (for tier name), `applicant` (for the applicant's full name), `loan_product` (for the product name), and `application_status` (for filtering). Three filters: risk tier is HIGH or VERY_HIGH; status is still PENDING or IN_REVIEW (undecided); submitted in the last 7 days. Sort by risk score descending and `LIMIT 20` for the most dangerous batch. Use `||` to concatenate first and last name.

**SQL:**

```sql
-- High-risk applications needing review this week
SELECT
    la.application_number,
    a.first_name || ' ' || a.last_name AS applicant_name,
    p.name AS product_name,
    la.requested_amount,
    ad.risk_score,
    rl.name AS risk_level,
    ad.ai_recommendation,
    la.submitted_at
FROM loan_application la
JOIN approval_decision ad ON la.id = ad.application_id
JOIN risk_level rl ON ad.risk_level_id = rl.id
JOIN applicant a ON la.applicant_id = a.id
JOIN loan_product p ON la.product_id = p.id
JOIN application_status s ON la.status_id = s.id
WHERE rl.code IN ('HIGH', 'VERY_HIGH')
  AND s.code IN ('PENDING', 'IN_REVIEW')
  AND la.submitted_at >= DATE('now', '-7 days')
ORDER BY ad.risk_score DESC
LIMIT 20;
```

**Expected result and business takeaway:**
Up to 20 rows of high-risk pending items, ordered by risk score. Because the data uses relative time and the 7-day window is narrow, the actual row count may be small or even empty (depending on when generation ran). The manager uses this list to dispatch the day's reviews — highest-risk first. If this queue stays long over time, it suggests either insufficient staffing or overly sensitive auto rules and should be escalated.

---

### Query 4: Underwriter Workload Distribution

**Business context:**
The Director of Operations needs the workload of manual underwriting spread evenly across the team. A single overloaded underwriter leads to burnout and delays; meanwhile, large differences in approval rates across underwriters can indicate inconsistent standards or a need for training.

This query supports staffing decisions and workflow tweaks, and feeds the quarterly team retrospective. It maps to the operations side of business question Q1 (Is approval healthy?).

**Category / Difficulty / Role:** Aggregation; Basic; Director of Operations.

**Solution approach:**
Look only at manual decisions, so join `decision_type` and filter `is_auto = 0`, and also exclude rows with a null `reviewer_id`. Group by `reviewer_id` and count total reviews, approvals, and denials, then compute approval rate per underwriter. The aggregation grain is "one row per underwriter." Note that `reviewer_id` only has a value for manual decisions (NULL for automated ones), so the `IS NOT NULL` filter is essential.

**SQL:**

```sql
-- Underwriter workload from manual decisions
SELECT
    ad.reviewer_id AS underwriter,
    COUNT(*) AS total_reviews,
    SUM(CASE WHEN ad.is_approved = 1 THEN 1 ELSE 0 END) AS approvals,
    SUM(CASE WHEN ad.is_approved = 0 THEN 1 ELSE 0 END) AS declines,
    ROUND(100.0 * SUM(CASE WHEN ad.is_approved = 1 THEN 1 ELSE 0 END) / COUNT(*), 2) AS approval_rate
FROM approval_decision ad
JOIN decision_type dt ON ad.decision_type_id = dt.id
WHERE dt.is_auto = 0
  AND ad.reviewer_id IS NOT NULL
GROUP BY ad.reviewer_id
ORDER BY total_reviews DESC;
```

**Expected result and business takeaway:**
One row per underwriter (`reviewer_id` resembling UW1001 through UW1020), with review count and approval rate. Workload should be roughly balanced. If someone's review count is far above the average, the Director should rebalance assignments; if someone's approval rate deviates significantly from the group (say, more than 20 points above average), arrange a peer review or training to keep standards consistent.

---

### Query 5: Credit Score Distribution by Decision

**Business context:**
The credit risk analyst wants to verify that the credit policy is doing what it's supposed to: approved applicants should have noticeably higher FICO scores than declined ones. If the two distributions overlap heavily, the credit score isn't doing its job as a discriminator, or strong applicants are being wrongly declined.

This is a routine check in the quarterly credit policy review. It maps to business question Q3 (Are credit policies and risk rules predictive?).

**Category / Difficulty / Role:** Aggregation + join; Intermediate; Credit Risk Analyst.

**Solution approach:**
The credit score lives in `credit_report` and the decision lives in `approval_decision`. The two are connected indirectly through `loan_application` and `applicant`, so we need a four-table join: `loan_application` to `approval_decision`, to `applicant`, then to `credit_report`. The key gotcha is that one applicant can have multiple credit reports (tri-merge); a naive join would double-count. Pin to a single bureau with `WHERE cr.bureau = 'Experian'` to keep the apples-to-apples comparison clean. Group by `is_approved` and look at min, average, and max FICO score per group.

**SQL:**

```sql
-- Credit score percentiles by approval decision
SELECT
    CASE WHEN ad.is_approved = 1 THEN 'Approved' ELSE 'Declined' END AS decision,
    COUNT(*) AS count,
    MIN(cr.fico_score) AS min_score,
    ROUND(AVG(cr.fico_score), 0) AS avg_score,
    MAX(cr.fico_score) AS max_score
FROM loan_application la
JOIN approval_decision ad ON la.id = ad.application_id
JOIN applicant a ON la.applicant_id = a.id
JOIN credit_report cr ON a.id = cr.applicant_id
WHERE cr.bureau = 'Experian'  -- pin to one bureau for consistency
GROUP BY ad.is_approved
ORDER BY decision;
```

**Expected result and business takeaway:**
Two rows (Approved, Declined), each with min / average / max FICO. In theory, the approved group should have a higher average score. But note: in this dataset, the approval outcome and the FICO score are generated independently, so the difference may be modest. The analyst uses this to judge the discriminatory power of the credit policy. If the gap is too small, raise the question "is the credit-score threshold actually doing anything?" at the review, and look at this alongside Q11 and Q20.

---

### Query 6: Top Decline Reasons

**Business context:**
The compliance analyst wants to understand why applications are being declined. The distribution of decline reasons reveals whether the policy is too tight, whether something is stuck in the document flow, or whether a category of customer is being systematically excluded (a fair lending concern).

This query feeds product optimization and supplies material for the fair-lending self-review. It maps to business question Q3 (risk policy).

**Category / Difficulty / Role:** Aggregation + string processing; Intermediate; Compliance Analyst.

**Solution approach:**
The decline reason lives in `approval_decision.decline_codes` as a comma-separated string of codes. Use a CTE to filter to declined records (`is_approved = 0`) with a non-null decline-code string, then group by the whole `decline_codes` string and count. For the percentage, use a subquery `(SELECT COUNT(*) FROM decline_reasons)` as the denominator. We treat the whole string as one group rather than splitting individual codes — splitting would require a recursive CTE; we keep it simple. Sort by count and take the top 10.

**SQL:**

```sql
-- Top decline reason analysis
WITH decline_reasons AS (
    SELECT
        ad.application_id,
        ad.decline_codes,
        ad.decision_reason
    FROM approval_decision ad
    WHERE ad.is_approved = 0
      AND ad.decline_codes IS NOT NULL
)
SELECT
    decline_codes,
    COUNT(*) AS occurrence_count,
    ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM decline_reasons), 2) AS pct_of_declines
FROM decline_reasons
GROUP BY decline_codes
ORDER BY occurrence_count DESC
LIMIT 10;
```

**Expected result and business takeaway:**
Up to 10 rows of decline-code combinations and their shares of all declines. Because the decline codes are random combinations from a small set, the distribution is fairly dispersed. The compliance analyst uses it to find the most common decline patterns. If a combination is unusually high, dig in to see whether a rule is too tight or a customer segment is being declined en masse, and submit a fair-lending review if warranted.

---

### Query 7: Average Time to Decision

**Business context:**
The Customer Experience Manager treats "time from submission to decision" as a key metric. The faster the decision, the higher the conversion and satisfaction. She wants to find slow products and channels and pinpoint bottlenecks in the approval flow.

Slow steps usually mean a manual-review backlog or a document hold-up. This query maps to business question Q1 (approval health and efficiency).

**Category / Difficulty / Role:** Aggregation + date arithmetic; Intermediate; Customer Experience Manager.

**Solution approach:**
For time deltas, SQLite's `JULIANDAY` turns timestamps into floating-point days (Julian dates); subtract and multiply by 24 to get hours. Start from `loan_application`, join `loan_product` for the product name, group by product and channel, and compute average, min, and max decision time. Filter `decision_at IS NOT NULL`, since undecided applications would pollute the average. Note that SQLite has no built-in `DATEDIFF`; subtracting `JULIANDAY` values is the standard approach.

**SQL:**

```sql
-- Average submission-to-decision time by product and channel
SELECT
    p.name AS product_name,
    la.channel,
    COUNT(*) AS decision_count,
    ROUND(AVG(
        (JULIANDAY(la.decision_at) - JULIANDAY(la.submitted_at)) * 24
    ), 2) AS avg_hours_to_decision,
    ROUND(MIN(
        (JULIANDAY(la.decision_at) - JULIANDAY(la.submitted_at)) * 24
    ), 2) AS min_hours,
    ROUND(MAX(
        (JULIANDAY(la.decision_at) - JULIANDAY(la.submitted_at)) * 24
    ), 2) AS max_hours
FROM loan_application la
JOIN loan_product p ON la.product_id = p.id
WHERE la.decision_at IS NOT NULL
GROUP BY p.name, la.channel
ORDER BY product_name, avg_hours_to_decision;
```

**Expected result and business takeaway:**
One row per product-channel combination with decision time. The generator sets decision time at 1 to 72 hours after submission, so the average lands around one to two days. The Customer Experience Manager uses it to find the slowest combinations. If a product-channel combination has a noticeably higher average, work with operations and product to break down where time is being spent and set an SLA target.

---

### Query 8: Revenue Forecast by Channel

**Business context:**
The FP&A analyst forecasts interest income by acquisition channel for budgeting and marketing ROI analysis. Whichever channel brings in the most funded volume and interest is the one the marketing budget should lean toward.

This is a key input to the quarterly budget. It maps to business question Q2 (product and channel profitability).

**Category / Difficulty / Role:** Aggregation + join; Basic; FP&A Analyst.

**Solution approach:**
Only funded (FUNDED) loans count as real revenue, so join `application_status` and filter `code = 'FUNDED'`, and exclude rows where `approved_amount` is null. Group by channel, sum funded count and amount, average the rate, sum monthly payments, and use monthly payment times 12 times rate to estimate annual interest. The estimated interest is order-of-magnitude only, not a precise financial number.

**SQL:**

```sql
-- Projected monthly interest income by channel
SELECT
    la.channel,
    COUNT(*) AS funded_loans,
    SUM(la.approved_amount) AS total_funded_amount,
    ROUND(AVG(la.approved_interest_rate), 2) AS avg_rate,
    ROUND(SUM(la.monthly_payment), 2) AS total_monthly_payment,
    ROUND(SUM(la.monthly_payment * 12 * (la.approved_interest_rate / 100)), 2) AS est_annual_interest
FROM loan_application la
JOIN application_status s ON la.status_id = s.id
WHERE s.code = 'FUNDED'
  AND la.approved_amount IS NOT NULL
GROUP BY la.channel
ORDER BY total_funded_amount DESC;
```

**Expected result and business takeaway:**
One row per channel with funded amount and estimated annual interest. Web typically leads in funded volume; branch may have larger average loans. The FP&A analyst uses this to allocate next quarter's marketing budget toward whichever channel yields the highest interest return per acquisition dollar, and feeds the figures into the revenue forecast model.

---

### Query 9: Fraud Flag Resolution Rate

**Business context:**
The Fraud Operations Manager tracks how quickly fraud flags are resolved. Unresolved flags hold up funding and create backlogs; a high resolution rate combined with a low false-positive rate is what shows fraud detection is working.

She wants to see resolution rate and average resolution time broken down by flag type and severity, to spot staffing or process issues. It maps to business question Q4 (fraud and compliance risk).

**Category / Difficulty / Role:** Aggregation; Basic; Fraud Operations Manager.

**Solution approach:**
Only `fraud_flag` is needed. Group by `flag_type` and `severity`, count total with `COUNT`, count resolved with `SUM(CASE ...)`, and divide for the rate. For average resolution time, use `JULIANDAY(resolved_at) - JULIANDAY(flagged_at)`, but only for resolved rows — use `CASE WHEN is_resolved = 1 THEN ... ELSE NULL END` inside the `AVG`; `AVG` ignores NULL automatically. This is the standard trick for "average over a subset."

**SQL:**

```sql
-- Fraud flag resolution metrics by type
SELECT
    flag_type,
    severity,
    COUNT(*) AS total_flags,
    SUM(CASE WHEN is_resolved = 1 THEN 1 ELSE 0 END) AS resolved_count,
    ROUND(100.0 * SUM(CASE WHEN is_resolved = 1 THEN 1 ELSE 0 END) / COUNT(*), 2) AS resolution_rate,
    ROUND(AVG(
        CASE WHEN is_resolved = 1
        THEN JULIANDAY(resolved_at) - JULIANDAY(flagged_at)
        ELSE NULL END
    ), 2) AS avg_days_to_resolve
FROM fraud_flag
GROUP BY flag_type, severity
ORDER BY total_flags DESC;
```

**Expected result and business takeaway:**
One row per "type + severity" combination with resolution rate and average days to resolve. The overall resolution rate is about 70% (the generator's design probability is 60%, but with only about 80 fraud flags total the small sample fluctuates). Because the fraud-flag table is small, each combination has very few rows. The manager uses this to find high-severity types that resolve slowly and reassign staff; types with persistently low resolution rates need a check of whether the detection rules are over-firing.

---

### Query 10: Agent Similar-Case Lookup

**Business context:**
When the AI approval assistant handles a new application, it pulls up similar historical cases to give the underwriter a "what did we do with similar applicants and how did it turn out?" reference. This is the core RAG-style decision-support action.

This query is an example tool call for the AI agent. It maps to business question Q5 (Can we trust the AI assistant?).

**Category / Difficulty / Role:** Subquery + join; Intermediate; AI Credit Assistant.

**Solution approach:**
Start from `similar_case` and pin to the current application via `source_application_id`. Then join to the similar-application side (`similar_application_id` to `loan_application`) and pull the similar app's product, amount, approval result (join `approval_decision`), and FICO (join `applicant` then `credit_report`). Use `cr.bureau = 'Experian'` to avoid duplication from multiple credit reports. Sort by similarity descending and take the top 5. The `WHERE sc.source_application_id = 1` is a placeholder — the Agent substitutes the actual application ID at runtime.

**SQL:**

```sql
-- Find similar historical cases for a given application
-- Replace :application_id with the actual ID
SELECT
    sc.similarity_score,
    similar_la.application_number AS similar_app_number,
    p.name AS product_name,
    similar_la.requested_amount,
    CASE WHEN ad.is_approved = 1 THEN 'Approved' ELSE 'Declined' END AS outcome,
    ad.decision_reason,
    cr.fico_score,
    sc.matching_factors
FROM similar_case sc
JOIN loan_application similar_la ON sc.similar_application_id = similar_la.id
JOIN approval_decision ad ON similar_la.id = ad.application_id
JOIN loan_product p ON similar_la.product_id = p.id
JOIN applicant a ON similar_la.applicant_id = a.id
JOIN credit_report cr ON a.id = cr.applicant_id
WHERE sc.source_application_id = 1  -- replace with the actual application ID
  AND cr.bureau = 'Experian'
ORDER BY sc.similarity_score DESC
LIMIT 5;
```

**Expected result and business takeaway:**
Up to 5 rows of similar historical applications, each with similarity, outcome, decision reason, and FICO. The Agent uses these to produce a one-line summary for the underwriter, e.g., "Found 5 similar cases; 4 were approved at similar credit profiles." The underwriter treats it as a reference, but the final decision is still made by a human or the main rules — high similarity does not imply the outcome should match.

---

### Query 11: Rule Trigger Frequency Analysis

**Business context:**
The Risk Policy Analyst needs to review which risk rules fire often and which almost never do. Rules that never fire may be obsolete; rules that fire almost every time may be too broad and effectively useless.

This is a standard part of the annual risk-policy review. It maps to business question Q3 (Are the rules well-calibrated?).

**Category / Difficulty / Role:** Aggregation + join; Intermediate; Risk Policy Analyst.

**Solution approach:**
From `rule_evaluation`, join `risk_rule` for the rule name and metadata. Group by rule, count total evaluations and triggered counts, and divide for the trigger rate. The grain is "one row per rule." List the display fields explicitly in `GROUP BY` (SQLite is lenient, but being explicit is clearer). No window function is needed — a single group-by aggregation does it.

**SQL:**

```sql
-- Rule trigger frequency and impact
SELECT
    rr.rule_code,
    rr.name AS rule_name,
    rr.category,
    rr.severity,
    COUNT(*) AS total_evaluations,
    SUM(CASE WHEN re.triggered = 1 THEN 1 ELSE 0 END) AS times_triggered,
    ROUND(100.0 * SUM(CASE WHEN re.triggered = 1 THEN 1 ELSE 0 END) / COUNT(*), 2) AS trigger_rate
FROM rule_evaluation re
JOIN risk_rule rr ON re.rule_id = rr.id
GROUP BY rr.id, rr.rule_code, rr.name, rr.category, rr.severity
ORDER BY times_triggered DESC;
```

**Expected result and business takeaway:**
One row per rule with its trigger rate. Because the generator uses a uniform 15% trigger probability across every rule, all rules will show trigger rates around 15% — not the realistic shape in which hard-stop rules trigger especially rarely. The analyst should recognize that this is a data simplification. On real data, they would flag rules with a 0% or near-100% trigger rate for retirement or tightening in the annual policy review.

---

### Query 12: Income Verification Gap Analysis

**Business context:**
Compliance requires that loans above a certain amount have income verified. The Compliance Manager needs to find applications "above $50K, approved or funded, with unverified income" — potential compliance gaps a regulator would zero in on.

When gaps are found, fix them or document an exception. It maps to business question Q4 (compliance risk).

**Category / Difficulty / Role:** CTE + join; Advanced; Compliance Manager.

**Solution approach:**
Use a CTE to filter to "high-value decided" applications: from `loan_application`, join `applicant`, `employment_info` (for `is_verified`), `loan_product`, and `application_status`, filter on amount > 50K and status APPROVED or FUNDED. Then aggregate on the CTE: group by product and count verified, unverified, and the unverified share. The CTE separates the complex filtering logic from the aggregation logic, making the query much easier to read.

**SQL:**

```sql
-- Applications that may need income verification
WITH verification_required AS (
    SELECT
        la.id AS application_id,
        la.application_number,
        la.requested_amount,
        ei.is_verified,
        ei.annual_income,
        p.name AS product_name
    FROM loan_application la
    JOIN applicant a ON la.applicant_id = a.id
    JOIN employment_info ei ON a.id = ei.applicant_id
    JOIN loan_product p ON la.product_id = p.id
    JOIN application_status s ON la.status_id = s.id
    WHERE la.requested_amount > 50000
      AND s.code IN ('APPROVED', 'FUNDED')
)
SELECT
    product_name,
    COUNT(*) AS total_high_value,
    SUM(CASE WHEN is_verified = 1 THEN 1 ELSE 0 END) AS verified_count,
    SUM(CASE WHEN is_verified = 0 THEN 1 ELSE 0 END) AS unverified_count,
    ROUND(100.0 * SUM(CASE WHEN is_verified = 0 THEN 1 ELSE 0 END) / COUNT(*), 2) AS verification_gap_pct
FROM verification_required
GROUP BY product_name
ORDER BY verification_gap_pct DESC;
```

**Expected result and business takeaway:**
One row per product with the unverified share among high-value loans. Since the overall income-verified rate is about 70%, the unverified gap sits around 30%. The Compliance Manager prioritizes follow-up verification on the products with the largest gaps. If a product's gap stays above the internal threshold, it triggers remediation and goes into the compliance report.

---

### Query 13: DTI Analysis by Product

**Business context:**
The Credit Risk Analyst wants to look at DTI distribution by product to see whether any product is attracting over-leveraged borrowers. Regulators set a 43% DTI ceiling for Qualified Mortgages, and a product with too many loans above that line raises a flag for policy violations or excessive exceptions.

This is the basis for setting and reviewing DTI thresholds. It maps to business question Q3 (credit policy).

**Category / Difficulty / Role:** Aggregation + conditional bucketing; Advanced; Credit Risk Analyst.

**Solution approach:**
From `loan_application`, join `loan_product` and group by product. In addition to average, min, and max DTI, the key move is three `SUM(CASE WHEN ...)` columns that bucket DTI into three tiers: under 30%, 30%-43%, over 43%. This "conditional counting bucket" pattern is the standard way to build distribution tables in SQLite, which has no `WIDTH_BUCKET`. Filter out null DTI rows.

**SQL:**

```sql
-- DTI distribution analysis by product
SELECT
    p.name AS product_name,
    COUNT(*) AS app_count,
    ROUND(AVG(la.debt_to_income_ratio), 2) AS avg_dti,
    ROUND(MIN(la.debt_to_income_ratio), 2) AS min_dti,
    ROUND(MAX(la.debt_to_income_ratio), 2) AS max_dti,
    SUM(CASE WHEN la.debt_to_income_ratio <= 30 THEN 1 ELSE 0 END) AS dti_under_30,
    SUM(CASE WHEN la.debt_to_income_ratio > 30 AND la.debt_to_income_ratio <= 43 THEN 1 ELSE 0 END) AS dti_30_to_43,
    SUM(CASE WHEN la.debt_to_income_ratio > 43 THEN 1 ELSE 0 END) AS dti_over_43
FROM loan_application la
JOIN loan_product p ON la.product_id = p.id
WHERE la.debt_to_income_ratio IS NOT NULL
GROUP BY p.name
ORDER BY avg_dti DESC;
```

**Expected result and business takeaway:**
One row per product showing the DTI distribution. Because DTI is uniformly distributed from 15% to 55% in this dataset, all products will have an average around 35%, and the share above 43% will also be similar. On real data, the analyst would focus on products where `dti_over_43` is unusually high. In this dataset, the conclusion should emphasize the bucketing technique rather than the literal numbers.

---

### Query 14: Application Funnel Conversion

**Business context:**
The CEO and COO track the application funnel to see where applicants are getting stuck and where they drop off. This is a key metric for investor updates and operations improvement plans.

Shape changes in the funnel trigger deeper dives into operational efficiency. It maps to business question Q1 (Is approval healthy?).

**Category / Difficulty / Role:** CTE; Advanced; CEO / COO.

**Solution approach:**
First, a CTE `status_counts` aggregates counts by status. Then a second CTE `total_apps` computes the total. The main query `CROSS JOIN`s them to compute the share by status. The `CROSS JOIN` is reasonable because `total_apps` has only one row, broadcasting the total across each row. Use `CASE` to map status codes to friendly funnel-stage labels, and use `CASE` in `ORDER BY` to enforce a custom stage order (rather than alphabetical). This is a classic multi-CTE-plus-custom-sort pattern.

**SQL:**

```sql
-- Application funnel analysis
WITH status_counts AS (
    SELECT
        s.code AS status_code,
        s.name AS status_name,
        COUNT(*) AS count
    FROM loan_application la
    JOIN application_status s ON la.status_id = s.id
    GROUP BY s.id, s.code, s.name
),
total_apps AS (
    SELECT SUM(count) AS total FROM status_counts
)
SELECT
    sc.status_name,
    sc.count,
    ROUND(100.0 * sc.count / ta.total, 2) AS pct_of_total,
    CASE sc.status_code
        WHEN 'PENDING' THEN 'Stage 1: Pending Review'
        WHEN 'IN_REVIEW' THEN 'Stage 2: In Review'
        WHEN 'APPROVED' THEN 'Stage 3: Approved'
        WHEN 'FUNDED' THEN 'Stage 4: Funded'
        WHEN 'DECLINED' THEN 'Exit: Declined'
        WHEN 'CANCELLED' THEN 'Exit: Cancelled'
        ELSE 'Other'
    END AS funnel_stage
FROM status_counts sc
CROSS JOIN total_apps ta
ORDER BY
    CASE sc.status_code
        WHEN 'PENDING' THEN 1
        WHEN 'IN_REVIEW' THEN 2
        WHEN 'APPROVED' THEN 3
        WHEN 'FUNDED' THEN 4
        ELSE 5
    END;
```

**Expected result and business takeaway:**
One row per status with its share of all applications. The expected shares match the generator weights: APPROVED ~40%, DECLINED ~25%, FUNDED ~10%, the rest 5%-10% each. The CEO uses this to gauge funnel health; if PENDING plus IN_REVIEW is too high a share, it means approval capacity isn't keeping up and the team needs more headcount or higher automation.

---

### Query 15: Loan Volume by State

**Business context:**
The Regulatory Reporting Analyst tabulates loan volume by state for regulatory reports and geographic concentration-risk analysis. Some states have state-specific lending regulations, and an oversized share in a single state means concentration risk.

This is a routine report covering both compliance and risk. It maps to business question Q2 (geographic concentration).

**Category / Difficulty / Role:** Aggregation + join; Basic; Regulatory Reporting Analyst.

**Solution approach:**
From `loan_application`, join `applicant` for state and `application_status` for status. Group by `state`, count applications and approvals, sum approved amount, and average loan size. Filter out null state rows. Sort by total approved amount and take the top 15 states. This is a standard "aggregate by geography" query.

**SQL:**

```sql
-- Loan volume by state
SELECT
    a.state,
    COUNT(la.id) AS application_count,
    SUM(CASE WHEN s.code IN ('APPROVED', 'FUNDED') THEN 1 ELSE 0 END) AS approved_count,
    SUM(la.approved_amount) AS total_approved_amount,
    ROUND(AVG(la.approved_amount), 2) AS avg_loan_amount
FROM loan_application la
JOIN applicant a ON la.applicant_id = a.id
JOIN application_status s ON la.status_id = s.id
WHERE a.state IS NOT NULL
GROUP BY a.state
ORDER BY total_approved_amount DESC
LIMIT 15;
```

**Expected result and business takeaway:**
The top 15 states by loan volume. Because states are uniformly sampled from 50, the distribution is fairly flat — you won't see the real-world pile-up in the big states (CA, TX, FL, NY). The analyst uses it for the regulatory report. In production, if any state's share exceeds 25%, the risk report should call out geographic concentration and evaluate hedges.

---

### Query 16: Document Verification Backlog

**Business context:**
The Document Processing Manager monitors the document-verification backlog. Verification delays directly slow funding and hurt customer satisfaction. She wants to see which document types have the most pending items and the longest backlogs.

When the backlog crosses a threshold, expedite or add staff. It maps to business question Q4 (operations and compliance).

**Category / Difficulty / Role:** Filter + join; Basic; Document Processing Manager.

**Solution approach:**
From `document`, join `loan_application` and then `application_status`, and filter to "document status is pending and application is still in PENDING / IN_REVIEW." Group by document type, count pending items, find the earliest upload, and use `JULIANDAY('now') - JULIANDAY(uploaded_at)` to compute average backlog in days. The key point is the double filter: both document status and application status, so we only count documents that are truly stuck.

**SQL:**

```sql
-- Documents pending verification
SELECT
    d.doc_type,
    COUNT(*) AS pending_count,
    MIN(d.uploaded_at) AS oldest_upload,
    ROUND(AVG(JULIANDAY('now') - JULIANDAY(d.uploaded_at)), 1) AS avg_days_pending
FROM document d
JOIN loan_application la ON d.application_id = la.id
JOIN application_status s ON la.status_id = s.id
WHERE d.verification_status = 'pending'
  AND s.code IN ('PENDING', 'IN_REVIEW')
GROUP BY d.doc_type
ORDER BY pending_count DESC;
```

**Expected result and business takeaway:**
One row per document type with the pending count and average backlog days. Income statements and bank statements typically have the longest queues. The manager expedites the oldest items. For types with persistently high average backlog days, either add staff or push for OCR-based auto-verification to lighten the load.

---

### Query 17: AI Confidence vs. Actual Outcome

**Business context:**
The data science team checks model calibration by comparing AI confidence against the actual approval result. High-confidence recommendations should map to clear outcomes; otherwise the model is drifting and needs retraining.

This is a foundational check on AI trust. It maps to business question Q5 (Can the AI assistant be trusted?).

**Category / Difficulty / Role:** Join + aggregation; Intermediate; Data Science / ML Engineer.

**Solution approach:**
Only `approval_decision` is needed. Use `CASE` to bucket `ai_confidence` into three tiers — low (<0.7), medium (0.7-0.85), and high (>0.85) — then group by the bucket and look at approval rate and average confidence per bucket. The trick is "first build a bucket column with CASE, then GROUP BY that column." Filter out null confidence rows.

**SQL:**

```sql
-- AI confidence score accuracy analysis
SELECT
    CASE
        WHEN ad.ai_confidence < 0.7 THEN 'Low (<70%)'
        WHEN ad.ai_confidence < 0.85 THEN 'Medium (70-85%)'
        ELSE 'High (>85%)'
    END AS confidence_bucket,
    COUNT(*) AS total_decisions,
    SUM(CASE WHEN ad.is_approved = 1 THEN 1 ELSE 0 END) AS approvals,
    ROUND(100.0 * SUM(CASE WHEN ad.is_approved = 1 THEN 1 ELSE 0 END) / COUNT(*), 2) AS approval_rate,
    ROUND(AVG(ad.ai_confidence), 3) AS avg_confidence
FROM approval_decision ad
WHERE ad.ai_confidence IS NOT NULL
GROUP BY confidence_bucket
ORDER BY avg_confidence;
```

**Expected result and business takeaway:**
Three rows (low / medium / high confidence buckets), each with its approval rate. Ideally, the approval rate would differ clearly across buckets. In this dataset, confidence and outcome are generated independently, so each bucket's approval rate may land near 60% — and that itself is an example of an "uncalibrated model" signal. The data science team uses this to judge whether retraining is needed. In production, if the high-confidence bucket has the same approval rate as the low-confidence one, the model needs a rebuild.

---

### Query 18: Month-over-Month Application Growth

**Business context:**
The CEO and CFO track month-over-month growth to read business direction. This metric goes to the board and investors, and a sustained decline triggers a strategy review.

Growth trend is a core input to funding and strategy decisions. It maps to business question Q1 (business health).

**Category / Difficulty / Role:** Window function; Advanced; CEO / CFO.

**Solution approach:**
A CTE aggregates by month (`strftime('%Y-%m', submitted_at)`) — applications, approvals, funded volume. The main query uses the window function `LAG(...) OVER (ORDER BY month)` to fetch the previous month's value, then computes "(this month - last month) / last month" for the growth rate. The window function is the right tool here because it references neighboring rows without a self-join. Note that the denominator may be zero or null (no previous month for the first month), so the growth columns will be NULL in those rows — expected.

**SQL:**

```sql
-- Month-over-month application and approval growth
WITH monthly_stats AS (
    SELECT
        strftime('%Y-%m', submitted_at) AS month,
        COUNT(*) AS applications,
        SUM(CASE WHEN s.code IN ('APPROVED', 'FUNDED') THEN 1 ELSE 0 END) AS approvals,
        SUM(approved_amount) AS approved_volume
    FROM loan_application la
    JOIN application_status s ON la.status_id = s.id
    GROUP BY strftime('%Y-%m', submitted_at)
)
SELECT
    month,
    applications,
    approvals,
    approved_volume,
    LAG(applications) OVER (ORDER BY month) AS prev_month_apps,
    ROUND(100.0 * (applications - LAG(applications) OVER (ORDER BY month)) /
          LAG(applications) OVER (ORDER BY month), 2) AS app_growth_pct,
    ROUND(100.0 * (approved_volume - LAG(approved_volume) OVER (ORDER BY month)) /
          LAG(approved_volume) OVER (ORDER BY month), 2) AS volume_growth_pct
FROM monthly_stats
ORDER BY month DESC
LIMIT 12;
```

**Expected result and business takeaway:**
Up to 12 rows, one month each, with application count, funded volume, and their month-over-month growth rates. Because applications are roughly evenly distributed across the 18 months, growth rates will oscillate around zero with no strong trend. The CEO uses this to tell the business story externally; in production, two or more consecutive months of decline kicks off a strategy review.

---

### Query 19: Repeat Applicant Analysis

**Business context:**
Marketing and risk both want to understand repeat-applicant behavior. Repeat customers cost less to acquire, but repeated applications can also be a credit-seeking warning sign.

This query serves both customer-value analysis for marketing and early warnings for risk. It maps to business question Q2 (customers and channels).

**Category / Difficulty / Role:** Subquery + CTE; Intermediate; Marketing Analyst.

**Solution approach:**
A CTE aggregates per `applicant_id`: number of applications, first and last submission, and approved count. The main query then uses `CASE` to bucket applicants into "single / 2 applications / 3+" and aggregates by bucket: number of applicants, total applications, and average approval rate. This is a "first aggregate by entity, then bucket by the aggregate" two-layer pattern, and the CTE keeps the two layers cleanly separated.

**SQL:**

```sql
-- Repeat applicant analysis
WITH applicant_apps AS (
    SELECT
        applicant_id,
        COUNT(*) AS application_count,
        MIN(submitted_at) AS first_app,
        MAX(submitted_at) AS last_app,
        SUM(CASE WHEN s.code IN ('APPROVED', 'FUNDED') THEN 1 ELSE 0 END) AS approved_count
    FROM loan_application la
    JOIN application_status s ON la.status_id = s.id
    GROUP BY applicant_id
)
SELECT
    CASE
        WHEN application_count = 1 THEN 'Single application'
        WHEN application_count = 2 THEN '2 applications'
        WHEN application_count >= 3 THEN '3 or more applications'
    END AS applicant_type,
    COUNT(*) AS applicant_count,
    SUM(application_count) AS total_applications,
    ROUND(AVG(approved_count * 1.0 / application_count), 2) AS avg_approval_rate
FROM applicant_apps
GROUP BY applicant_type
ORDER BY applicant_count DESC;
```

**Expected result and business takeaway:**
Three rows (single / 2 / 3+). With 800 applications spread across 500 applicants, a meaningful share of applicants have multiple applications. The marketing analyst checks whether repeat customers have a healthy approval rate. If the "3+" group's approval rate is markedly lower, that group may be shopping around for credit, and the risk team should add monitoring.

---

### Query 20: Risk Rule Effectiveness Analysis

**Business context:**
The risk-policy team evaluates whether rules have predictive power: when a rule fires, is the application actually more likely to be declined? If firing and decline are uncorrelated, the rule is window dressing and should be adjusted or retired.

This is the most rigorous piece of analysis in the annual risk-policy review. It maps to business question Q3 (Are the risk rules effective?).

**Category / Difficulty / Role:** CTE + join; Advanced; Risk Policy Analyst.

**Solution approach:**
A CTE stitches each rule evaluation to its application's final approval result: `rule_evaluation` joins `risk_rule`, `loan_application`, and `approval_decision`. The main query groups by rule and computes two key numbers — trigger count and "triggered and declined" count — and divides them for the "decline rate when triggered." A "not triggered but declined" column is added for contrast. `NULLIF(..., 0)` guards against division by zero when trigger count is zero. `HAVING triggered_count > 0` filters out rules that never fired.

**SQL:**

```sql
-- Evaluate rule effectiveness: do triggered rules correlate with declines?
WITH rule_outcomes AS (
    SELECT
        re.rule_id,
        rr.rule_code,
        rr.name AS rule_name,
        rr.severity,
        re.triggered,
        ad.is_approved
    FROM rule_evaluation re
    JOIN risk_rule rr ON re.rule_id = rr.id
    JOIN loan_application la ON re.application_id = la.id
    JOIN approval_decision ad ON la.id = ad.application_id
)
SELECT
    rule_code,
    rule_name,
    severity,
    SUM(CASE WHEN triggered = 1 THEN 1 ELSE 0 END) AS triggered_count,
    SUM(CASE WHEN triggered = 1 AND is_approved = 0 THEN 1 ELSE 0 END) AS triggered_and_declined,
    ROUND(100.0 * SUM(CASE WHEN triggered = 1 AND is_approved = 0 THEN 1 ELSE 0 END) /
          NULLIF(SUM(CASE WHEN triggered = 1 THEN 1 ELSE 0 END), 0), 2) AS decline_rate_when_triggered,
    SUM(CASE WHEN triggered = 0 AND is_approved = 0 THEN 1 ELSE 0 END) AS not_triggered_but_declined
FROM rule_outcomes
GROUP BY rule_id, rule_code, rule_name, severity
HAVING triggered_count > 0
ORDER BY triggered_count DESC;
```

**Expected result and business takeaway:**
One row per rule with its "decline rate when triggered." Note the business trap called out in the ER document: in this dataset, rule triggering and the actual outcome are generated independently, so the decline rate when triggered comes out close to the overall decline rate (~40%) rather than the 90%+ you'd see for a real hard-stop rule. This is exactly an example of "what a rule with no predictive power looks like in the data." On real data, the analyst would flag any hard-stop rule with a decline-rate-when-triggered below 50% as suspicious and submit it for review; in this dataset, treat it as a teaching example for spotting ineffective rules.

---

## 5. Business Question and Query Mapping

Each query maps back to at least one business question from the business context document.

| Business question | Corresponding queries |
|-------------------|----------------------|
| Q1 Is approval healthy and stable? | Queries 1, 4, 7, 14, 18 |
| Q2 Product / channel profitability and geographic concentration | Queries 2, 8, 15, 19 |
| Q3 Are credit policies and risk rules effective? | Queries 5, 6, 11, 13, 20 |
| Q4 Fraud and compliance risk | Queries 3, 9, 12, 16 |
| Q5 Is the AI approval assistant trustworthy? | Queries 10, 17 |

---

## 6. Coverage Summary

SQL technique coverage:

| Category | Count | Query numbers |
|----------|-------|---------------|
| Aggregation queries | 5 | 2, 4, 8, 9, 15 |
| Join operations | 5 | 2, 3, 10, 11, 17 |
| Window functions | 1 | 18 |
| Date / time analysis | 3 | 1, 7, 16 |
| Subquery / CTE | 6 | 6, 12, 14, 18, 19, 20 |
| Conditional bucketing / string | 3 | 5, 6, 13 |

Business role coverage:

| Role level | Count | Query numbers |
|------------|-------|---------------|
| Executive (C-level) | 3 | 1, 14, 18 |
| Manager / Director | 6 | 2, 4, 9, 12, 16, 3 |
| Analyst / IC | 8 | 5, 6, 8, 11, 13, 15, 19, 20 |
| Operations / Specialist | 1 | 7 |
| Agent / Model | 2 | 10, 17 |

Difficulty distribution:

| Difficulty | Count | Query numbers |
|------------|-------|---------------|
| Basic | 7 | 2, 3, 4, 8, 9, 15, 16 |
| Intermediate | 8 | 1, 5, 6, 7, 10, 11, 17, 19 |
| Advanced | 5 | 12, 13, 14, 18, 20 |

---

## 7. Notes

All queries are written in SQLite 3.x syntax, with date functions `DATE()`, `JULIANDAY()`, and `strftime()`. The dataset uses relative time, so the queries take the current date dynamically with `DATE('now')`; for strictly reproducible results, substitute a fixed date string. Query 10 takes a parameter (`source_application_id`); when testing, replace the placeholder `1` with an actual application ID. In production, add indexes on commonly filtered columns such as `decision_at`, `submitted_at`, and `status_id`.
