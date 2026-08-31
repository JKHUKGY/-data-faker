# Cybersecurity - AI Compliance Audit System SQL Query Reference

## Overview

This document provides **20 business-oriented SQL queries** designed for the `cybersecurity_ai_compliance_audit_medium` dataset. Each query addresses a real question that a business stakeholder might ask.

> **Cross-database note:** All queries are written for SQLite 3.x. The table name `user` is a reserved keyword in databases such as PostgreSQL; when porting, you'll need to wrap `user` in double quotes or backticks (e.g., `"user"`). The date functions `julianday()`, `strftime()`, and `date('now')` are SQLite-specific; when porting, replace them with the equivalents in the target database.

> **Time anchor note:** The dataset uses a dynamic time anchor ("today" = the generation timestamp), so all `julianday('now')` and `date('now')` queries have proper discriminative power if you run them immediately after the generator has run.

> **Business context:** This dataset simulates a single customer tenant of the fictional company **Sentinel AI Governance** (a SaaS company headquartered in Boston that provides an AI compliance audit platform to mid-to-large enterprises). The queries below revolve around Sentinel's core daily workflows on the platform (compliance audit, risk assessment, incident response, remediation tracking, model governance). For the full company profile, business model, industry primer, role personas, and glossary, see `01-cybersecurity_ai_compliance_audit_medium_business_context.md`; for table structures and fields, see `02-cybersecurity_ai_compliance_audit_medium_er_document.md`.

---

## How to Use This Document

This document is the **most teaching-oriented** one in the dataset. The intended reader is an intern data analyst who has just finished reading the business context document and the ER document, and is about to be asked by their manager to "run through these queries this week". Use it the following way:

- **Every query has a fixed five-part structure**; if you read it straight through, you'll go from "understanding the question" all the way to "writing and using it":
  1. **Business context** — who is asking, why now, what decision the answer supports.
  2. **Category / difficulty / business role** — three tags that help you judge what SQL skill the query is practicing and whose work it belongs to.
  3. **Approach** — before looking at the SQL, walk through which tables to join and why, what aggregation grain to use, why a CTE or window function is needed, and where the SQLite pitfalls are. **This section is the real focus of learning.**
  4. **SQL** — a query that can be run directly on the generated SQLite database. We recommend reading the approach section first, then comparing it to the code.
  5. **Expected result and business takeaway** — what the result looks like (row count, column meaning, key magnitudes), and what the analyst **should do next** after getting the numbers. Producing a number is just the start of analysis, not the end.
- **Every query traces back to a business problem in section 5 of the business context document.** If you can't say which business problem a query is answering, it shouldn't be here.
- **The SQL is meant to be read and learned from, not just executed.** Pay attention to why something is a `LEFT JOIN` and not an `INNER JOIN`, why the denominator is wrapped in `NULLIF`, why you need `COUNT(DISTINCT ...)`.
- **About the time anchor:** This dataset deliberately uses a runtime `now()` dynamic anchor instead of a fixed REFERENCE_DATE literal. So `date('now')` / `julianday('now')` are preserved in queries — please **run them as soon as possible after generating the data**, otherwise as time passes Q19 and similar queries will lose discriminative power (see section 6 of the business context document for details).

---

## Business Glossary

Key terms in the compliance audit domain are commonly confused in everyday conversation; this section gives precise definitions for how they're used in this document:

| Term | Definition | Caveats |
|------|------|---------|
| **Risk Tier** | The 4-level enum on `ai_model.risk_tier`: `CRITICAL`, `HIGH`, `MEDIUM`, `LOW` | "High Risk" in this document is defined as `risk_tier IN ('CRITICAL', 'HIGH')`, consistently across all queries |
| **Risk Score** | `likelihood_score × impact_score × severity_weight`, the composite score of a single risk_assessment (0.9 – 45) | Independent of risk_tier: risk_tier is a model-level label, risk_score is a numeric value at the assessment level |
| **Coverage Rate** | Assessed controls / Total controls | Measures "is the audit done?", a **progress** indicator, independent of "is it compliant?" |
| **Compliance Rate** | COMPLIANT / **Applicable** Assessments | Measures "of what's been assessed, is it compliant?", a **health** indicator |
| **Applicable Assessment** | Assessment with `compliance_status != 'NOT_APPLICABLE'` | NOT_APPLICABLE means "this control doesn't apply to this model"; it **should not** enter the compliance-rate denominator |
| **Stale Audit** | `last_audit_date IS NULL` or older than 180 days | Core definition for Query 19 |
| **Open Incident** | `status NOT IN ('RESOLVED', 'CLOSED')` | i.e., the three states OPEN / INVESTIGATING / CONTAINED |
| **Open Remediation** | `control_status.is_terminal = 0` | i.e., the three states PENDING / IN_PROGRESS / DEFERRED |
| **Production Model** | `deployment_env = 'production'` AND `is_active = 1` | Note that `production` is all lowercase; SQL string comparison is case-sensitive |
| **MTTR** | Mean Time To Resolve = `AVG((julianday(resolved_at) - julianday(reported_at)) * 24)` hours | Only meaningful for RESOLVED/CLOSED incidents |
| **Overdue** | `due_date < date('now')` AND not completed | Also requires `is_terminal = 0` to count as "actually overdue" |

---

## Query Use-Case Index

The table below regroups the 20 queries by **real usage cadence**, so the reader knows "when should I run which query":

| Scenario | Cadence | Queries involved | Primary user |
|------|------|---------|----------|
| **Daily morning stand-up** | Daily | Q9 (high-priority backlog), Q13 (overdue list) | Ops manager, ops |
| **Weekly reporting** | Weekly | Q5 (remediation completion rate), Q10 (audit log distribution), Q4 (monthly incident trend), Q18 (assignee workload) | Ops manager, security analyst, compliance auditor |
| **Monthly review** | Monthly | Q8 (MTTR), Q15 (type×severity), Q12 (risk category assessment) | Security analyst, ops manager, analyst |
| **Quarterly compliance audit** | Quarterly | Q14 (framework coverage and compliance rate), Q19 (model audit coverage), Q2 (framework control distribution) | Compliance manager |
| **Board/exec dashboard** | Quarterly | Q1 (high-risk overview), Q17 (production risk summary), Q20 (key metrics) | Exec/C-Level |
| **Incident-triggered investigation** | Ad-hoc | Q16 (user action trace), Q11 (owner risk responsibility), Q3 (unmitigated high risk) | Compliance auditor, risk manager |
| **HR governance check** | Ad-hoc | Q7 (departmental activity) | HR manager |
| **Model launch/retirement** | Event-driven | Q1 (risk-tier check), Q19 (audit coverage check), Q6 (risk ranking) | Compliance manager, analyst |

---

## Cross-Query Consistency Conventions

To prevent readers from mistaking "stylistically slightly different queries" for inconsistent ones, the unified conventions running through all 20 queries are listed below:

| Concept | Unified expression | Appears in |
|------|---------|--------|
| "high risk" model | `risk_tier IN ('CRITICAL', 'HIGH')` | Q11, Q20 |
| "production" environment | `deployment_env = 'production'` (**all lowercase**) | Q17 |
| "unclosed" incident | `status NOT IN ('RESOLVED', 'CLOSED')` | Q20 |
| "open" remediation | `cs.is_terminal = 0` (JOIN control_status) | Q9, Q13, Q18, Q20 |
| "completed" remediation | `cs.code = 'COMPLETED'` or `status_id = 3` | Q5, Q18 |
| "unmitigated" risk | `mitigation_status = 'NOT_STARTED'` | Q3, Q17, Q20 |
| Time relative to "today" | `julianday('now')` or `date('now')` (runtime) | Q9, Q13, Q19, Q20 |
| Divide-by-zero guard | `NULLIF(denominator, 0)` | Q14, Q20 |
| Row-inflation guard | `COUNT(DISTINCT CASE WHEN ... THEN id END)` | Q11 |

If you see a query using a different formulation than the table above, that's **deliberate for that query's business question** (for example, the weighted avg_risk_score in Q11) — those differences are called out in the corresponding query's "Fix Note" or "Semantic Hint".

---

## Difficulty Ladder

The 20 queries climb from SQL fundamentals to advanced semantic traps. The table below suggests a learning path:

### Basic (7 queries) — suitable for SQL beginners

| Query | Learning point |
|-------|---------|
| Q1 High-risk model overview | Basic `GROUP BY` + `SUM(CASE WHEN)` counting |
| Q5 Remediation completion rate | Subquery for totals + percentage |
| Q7 Departmental activity | Single-table aggregation + derived activity rate |
| Q9 High-priority backlog | Multi-table JOIN + simple filter |
| Q10 Audit log distribution | Aggregation + share + `COUNT(DISTINCT)` |
| Q12 Risk category assessment | LEFT JOIN + multi-column means |
| Q15 Incident type×severity | Pivot-style multi-column SUM(CASE) |

### Intermediate (9 queries) — multi-table + date + polymorphic

| Query | Learning point |
|-------|---------|
| Q2 Framework control implementation | Multi-table JOIN + `GROUP_CONCAT(DISTINCT)` |
| Q3 Unmitigated high risk | Multi-table JOIN + condition combinations |
| Q4 Monthly trend | `strftime('%Y-%m', ...)` date bucketing |
| Q8 MTTR | `julianday(a) - julianday(b)` date difference + multi-column aggregation |
| Q11 Model owner risk | Warning: **row-inflation trap** + `COUNT(DISTINCT CASE)` fix |
| Q13 Overdue list | Date comparison + multi-table JOIN |
| Q16 User action trace | LEFT JOIN + LIMIT + time ordering |
| Q17 Production risk | Multi-condition filter + LEFT JOIN to handle nulls |
| Q19 Model audit coverage | Subquery counts + time-conditional branching |

### Advanced (4 queries) — CTE, window functions, business semantics

| Query | Learning point |
|-------|---------|
| Q6 Model risk ranking | CTE + `RANK() OVER` + scalar subquery comparison |
| Q14 Framework coverage/compliance rate | Warning: **NOT_APPLICABLE denominator trap** + dual definitions |
| Q18 Assignee workload | Multiple metrics + `RANK() OVER` ranking |
| Q20 Key metrics dashboard | Multiple scalar subqueries + `NULLIF` for divide-by-zero |

### Key Business Semantic Traps (worth chewing over repeatedly)

- **Q11 row-inflation:** When you `LEFT JOIN` a downstream table with a 1:N relationship and then use `SUM(CASE WHEN parent.col=...)`, the result is multiplied by the number of downstream rows. Fix: `COUNT(DISTINCT CASE WHEN parent.col=... THEN parent.id END)`.
- **Q11 weighted vs. equal-weight average:** `AVG(ra.risk_score)` is weighted by assessment row (models with more assessments carry more weight), not equal-weighted per model. Both semantics are defensible; pick based on the business question.
- **Q14 NOT_APPLICABLE in denominator:** "Control doesn't apply" should not be counted as "non-compliant". The compliance-rate denominator must exclude NOT_APPLICABLE, otherwise the number is artificially depressed.
- **Q19 time anchor drift:** Query 19 uses `julianday('now')` against `last_audit_date`. If the data hasn't been regenerated for 6+ months after generation, all last_audit_date values become stale and the hit rate drifts toward 100%, losing discriminative power. The dynamic anchor is used precisely to avoid this issue, but you need to **query immediately after generation** to preserve discriminative power.

---

## Query Index

| # | Title | Business role | Category | Difficulty |
|------|------|----------|------|------|
| 1 | High-risk model compliance overview | Exec | Aggregation | Basic |
| 2 | Implementation status of controls per framework | Compliance manager | Join+aggregation | Intermediate |
| 3 | Unmitigated high-risk assessment list | Risk manager | Join | Basic |
| 4 | Monthly security incident trend analysis | Security analyst | Date analysis | Intermediate |
| 5 | Remediation action completion rate stats | Ops manager | Aggregation | Basic |
| 6 | Model risk score leaderboard | Analyst | Window function | Advanced |
| 7 | Departmental user activity analysis | HR manager | Aggregation | Basic |
| 8 | Mean time to resolve incidents | Ops manager | Date analysis | Intermediate |
| 9 | High-priority open remediation actions | Ops | Join | Basic |
| 10 | Audit log action-type distribution | Compliance auditor | Aggregation | Basic |
| 11 | Model owner risk responsibility analysis | Risk manager | Join+aggregation | Intermediate |
| 12 | Comparison of assessment counts by risk category | Analyst | Aggregation | Basic |
| 13 | Overdue remediation action list | Ops manager | Join+date | Intermediate |
| 14 | Framework compliance assessment coverage and rate | Compliance manager | CTE | Advanced |
| 15 | Cross analysis of incident type and severity | Security analyst | Aggregation | Intermediate |
| 16 | User action audit trace | Compliance auditor | Join | Intermediate |
| 17 | Production model risk summary | Exec | Join+aggregation | Intermediate |
| 18 | Remediation assignee workload analysis | Ops manager | Window function | Advanced |
| 19 | Model audit coverage check | Compliance manager | Subquery | Intermediate |
| 20 | Key compliance metrics dashboard | Exec | CTE+aggregation | Advanced |

---

## Query Details

### Query 1: High-risk Model Compliance Overview

**Business context:**
The CTO or CISO needs a quick read on the overall risk posture of AI models deployed across the organization. Before a board update or quarterly compliance review, an executive needs a concise overview showing how many models exist per risk tier and the active/inactive distribution. This helps judge overall risk exposure and prioritize resource allocation.

**Category:** Aggregation
**Difficulty:** Basic
**Business role:** Exec/C-Level

**Approach:**
All the data is in the single `ai_model` table — no joins needed. The core idea is "one scan, group by `risk_tier`, count active and inactive in the same pass" — using `SUM(CASE WHEN is_active = 1 THEN 1 ELSE 0 END)` to combine two definitions into one row is cleaner than running two queries and stitching them together (`is_active` is a 0/1 integer in SQLite). The output grain is "one row per risk tier", for 4 rows total. The final `ORDER BY CASE risk_tier ...` is a key detail: default alphabetical order would put CRITICAL after HIGH, so the CASE mapping forces the business reading order CRITICAL→HIGH→MEDIUM→LOW.

```sql
-- Count AI models by risk tier and status
SELECT
    risk_tier,
    SUM(CASE WHEN is_active = 1 THEN 1 ELSE 0 END) AS active_models,
    SUM(CASE WHEN is_active = 0 THEN 1 ELSE 0 END) AS inactive_models,
    COUNT(*) AS total_models
FROM ai_model
GROUP BY risk_tier
ORDER BY
    CASE risk_tier
        WHEN 'CRITICAL' THEN 1
        WHEN 'HIGH' THEN 2
        WHEN 'MEDIUM' THEN 3
        WHEN 'LOW' THEN 4
    END;
```

**Expected result notes:**
Returns 4 rows (CRITICAL, HIGH, MEDIUM, LOW), each showing the active model count, inactive model count, and total for that risk tier. Helps the executive quickly see how many models sit in the CRITICAL and HIGH tiers.

---

### Query 2: Implementation Status of Controls per Framework

**Business context:**
The compliance manager needs to report to the audit committee on the implementation progress of controls across compliance frameworks. Different frameworks (e.g., NIST AI RMF, GDPR, HIPAA) have different control requirements, and the manager needs to know how many controls each framework defines and how they're distributed across categories. This helps identify compliance gaps and resource needs.

**Category:** Join+aggregation
**Difficulty:** Intermediate
**Business role:** Compliance manager

**Approach:**
To bring "framework" and "controls" together, join from `compliance_framework` to `compliance_control` (`framework_id` is 1:N, with multiple controls hanging off each framework). INNER JOIN is fine here because every control must belong to a framework; only "frameworks with zero controls" would be dropped, and none such exist in this dataset. The aggregation grain is two-layer (framework, category), so `GROUP BY` carries `cf.id, cf.name, cf.version, cc.category`. `GROUP_CONCAT(DISTINCT cc.priority)` collapses the priorities seen within a group into one deduplicated list, making it easy for the manager to see at a glance "what priorities are covered in this category".

```sql
-- Count controls per compliance framework and category distribution
SELECT
    cf.name AS framework_name,
    cf.version,
    cc.category,
    COUNT(*) AS control_count,
    GROUP_CONCAT(DISTINCT cc.priority) AS priorities
FROM compliance_framework cf
JOIN compliance_control cc ON cf.id = cc.framework_id
GROUP BY cf.id, cf.name, cf.version, cc.category
ORDER BY cf.name, cc.category;
```

**Expected result notes:**
Returns the count of controls per category (Governance, Data Management, etc.) within each framework, plus the list of priorities involved. The compliance manager can identify which framework/category combinations have the most controls and warrant more attention.

---

### Query 3: Unmitigated High-risk Assessment List

**Business context:**
The risk manager needs to review unmitigated high-risk items each week. When a risk score exceeds a certain threshold (e.g., 20) and the status is still NOT_STARTED, those items need immediate attention. The risk manager needs to reach out to the model owner and assessor to push the risk handling forward.

**Category:** Join
**Difficulty:** Basic
**Business role:** Risk manager

**Approach:**
Use `risk_assessment` as the main table, joining back to `ai_model` (to get the model name and risk_tier), `risk_category` (to get the category name), and `user` (to get the assessor's name). All three foreign keys are NOT NULL, so INNER JOIN is safe and won't drop rows. The filter is a conjunction of two business definitions: `risk_score >= 20` (the conventional "high risk" threshold; recall that risk_score ranges from 0.9 to 45) and `mitigation_status = 'NOT_STARTED'` (no mitigation work has begun). The output grain is "one assessment per row", sorted by `risk_score DESC` so the most dangerous items float to the top, making it easy for the risk manager to chase from top down.

```sql
-- Find assessments with high risk scores that have no mitigation started
SELECT
    ra.id AS assessment_id,
    am.model_name,
    am.risk_tier,
    rc.name AS risk_category,
    ra.risk_score,
    ra.mitigation_status,
    u.full_name AS assessor,
    ra.findings,
    ra.assessed_at
FROM risk_assessment ra
JOIN ai_model am ON ra.ai_model_id = am.id
JOIN risk_category rc ON ra.risk_category_id = rc.id
JOIN user u ON ra.assessor_id = u.id
WHERE ra.risk_score >= 20
  AND ra.mitigation_status = 'NOT_STARTED'
ORDER BY ra.risk_score DESC;
```

**Expected result notes:**
Returns assessments with risk_score ≥ 20 and status NOT_STARTED, sorted by risk score descending. Includes model name, risk category, assessor, and other info to facilitate follow-up by the risk manager.

---

### Query 4: Monthly Security Incident Trend Analysis

**Business context:**
The head of the Security Operations Center (SOC) needs to analyze monthly trends in security incidents. Knowing whether incident counts are rising or falling and which months are peaks helps adjust the security team's staffing and budget. This is also a key metric for reporting security posture to senior management.

**Category:** Date analysis
**Difficulty:** Intermediate
**Business role:** Security analyst

**Approach:**
The data is in the single `security_incident` table. The key to monthly trending is "downsampling" the date to month granularity: `strftime('%Y-%m', reported_at)` chops the timestamp into a `2026-05`-style month bucket, then `GROUP BY` that expression. Within each month bucket, four `SUM(CASE WHEN severity = ... )` expressions lay out severity horizontally as four columns, producing a pivot table (one row per month, columns are counts per severity). `strftime` is a SQLite-specific function, relying on `reported_at` being a standard ISO date string (which is exactly how the generator writes it). The final `ORDER BY month` ensures the timeline is ordered, ready to plot.

```sql
-- Count security incidents and severity distribution by month
SELECT
    strftime('%Y-%m', reported_at) AS month,
    COUNT(*) AS total_incidents,
    SUM(CASE WHEN severity = 'CRITICAL' THEN 1 ELSE 0 END) AS critical_count,
    SUM(CASE WHEN severity = 'HIGH' THEN 1 ELSE 0 END) AS high_count,
    SUM(CASE WHEN severity = 'MEDIUM' THEN 1 ELSE 0 END) AS medium_count,
    SUM(CASE WHEN severity = 'LOW' THEN 1 ELSE 0 END) AS low_count
FROM security_incident
GROUP BY strftime('%Y-%m', reported_at)
ORDER BY month;
```

**Expected result notes:**
Returns incident statistics aggregated by month, showing per-severity counts each month. The analyst can plot a trend and identify peak months and the overall security trend.

---

### Query 5: Remediation Action Completion Rate Stats

**Business context:**
The ops manager needs to report remediation execution at the weekly stand-up. They need to know how many remediation actions are completed, in-progress, pending, or deferred, in order to assess the team's execution efficiency and whether additional resources are needed. Completion rate is a key operational KPI.

**Category:** Aggregation
**Difficulty:** Basic
**Business role:** Ops manager

**Approach:**
Join `remediation_action` to `control_status` to get the human-readable status name and the `is_terminal` flag. The common pattern for computing share is to put a scalar subquery `(SELECT COUNT(*) FROM remediation_action)` in the SELECT list as the denominator — it returns the same total for every group, so `action_count * 100.0 / total` per row gives the percentage for that status (note multiplying by `100.0` triggers float division, otherwise integer division truncates to 0). The grain is "one row per status". `ORDER BY CASE cs.code ...` orders statuses by the operational attention sequence COMPLETED→IN_PROGRESS→PENDING→DEFERRED→CANCELLED, rather than alphabetical.

```sql
-- Count remediation actions per status and share
SELECT
    cs.code AS status_code,
    cs.name AS status_name,
    cs.is_terminal,
    COUNT(*) AS action_count,
    ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM remediation_action), 2) AS percentage
FROM remediation_action ra
JOIN control_status cs ON ra.status_id = cs.id
GROUP BY cs.id, cs.code, cs.name, cs.is_terminal
ORDER BY
    CASE cs.code
        WHEN 'COMPLETED' THEN 1
        WHEN 'IN_PROGRESS' THEN 2
        WHEN 'PENDING' THEN 3
        WHEN 'DEFERRED' THEN 4
        WHEN 'CANCELLED' THEN 5
    END;
```

**Expected result notes:**
Returns counts and percentages of remediation actions per status. The ops manager can quickly see the completion rate (percentage at COMPLETED) and the share of open work (PENDING + IN_PROGRESS).

---

### Query 6: Model Risk Score Leaderboard

**Business context:**
The risk analyst needs to identify the highest-risk AI models in the organization. Each model may have multiple risk assessments (for different risk categories), and the analyst needs to compute the average and maximum risk score per model, and compare against the overall average. This helps prioritize handling of high-risk models.

**Category:** Window function
**Difficulty:** Advanced
**Business role:** Analyst

**Approach:**
This problem has two steps, so a CTE breaks it apart. Step 1, `model_stats`: join `ai_model` to `risk_assessment`, then aggregate per model to compute the assessment count, average, and max risk_score (use INNER JOIN here to keep only models that have been "assessed at least once" — without an assessment there's nothing to rank). Step 2 on top of the CTE does two things: `RANK() OVER (ORDER BY avg_risk_score DESC)` ranks models, and a scalar subquery `(SELECT AVG(risk_score) FROM risk_assessment)` retrieves the global average as a comparison baseline. Why must we use a CTE instead of writing it in one step? Because the window function `RANK()` needs to run "on results already aggregated by model"; mixing `GROUP BY` aggregation and window ranking in the same level conflicts semantically. Note that `avg_risk_score` is weighted by assessment row (models with more assessments contribute each assessment to the mean). `LIMIT 15` takes only the top 15 highest-risk models.

```sql
-- Use a CTE to aggregate per model first, then apply window ranking and comparison,
-- avoiding RANK + LIMIT semantic confusion
WITH model_stats AS (
    SELECT
        am.id,
        am.model_name,
        am.risk_tier,
        am.deployment_env,
        COUNT(ra.id) AS assessment_count,
        ROUND(AVG(ra.risk_score), 2) AS avg_risk_score,
        MAX(ra.risk_score) AS max_risk_score
    FROM ai_model am
    JOIN risk_assessment ra ON am.id = ra.ai_model_id
    WHERE am.is_active = 1
    GROUP BY am.id, am.model_name, am.risk_tier, am.deployment_env
)
SELECT
    model_name,
    risk_tier,
    deployment_env,
    assessment_count,
    avg_risk_score,
    max_risk_score,
    RANK() OVER (ORDER BY avg_risk_score DESC) AS risk_rank,
    ROUND(avg_risk_score - (SELECT AVG(risk_score) FROM risk_assessment), 2) AS vs_overall_avg
FROM model_stats
ORDER BY avg_risk_score DESC
LIMIT 15;
```

**Expected result notes:**
Returns the top 15 highest-risk models, with assessment count, average and max risk score, and the difference from the overall average. Positive values indicate above average; negative values below.

---

### Query 7: Departmental User Activity Analysis

**Business context:**
The HR manager or department head needs to understand user distribution and active status across departments in the compliance system. This helps evaluate departmental engagement with compliance work and whether system permissions need cleanup (disabling inactive accounts).

**Category:** Aggregation
**Difficulty:** Basic
**Business role:** HR manager

**Approach:**
All data is in the single `user` table; group by `department`. Same "conditional counting" pattern as Q1: `SUM(CASE WHEN is_active = 1 ...)` counts active, `SUM(CASE WHEN is_active = 0 ...)` counts inactive, then active_count `* 100.0 / COUNT(*)` gives the activity rate (multiply by `100.0` to force float). One easy cognitive trap: `role` to `department` is an N:1 mapping (Engineering contains 3 roles), so grouping by `department` actually produces only 6 buckets, not 8 role buckets. The output grain is "one row per department", sorted by total user count descending.

```sql
-- Count users per department and active status
SELECT
    department,
    COUNT(*) AS total_users,
    SUM(CASE WHEN is_active = 1 THEN 1 ELSE 0 END) AS active_users,
    SUM(CASE WHEN is_active = 0 THEN 1 ELSE 0 END) AS inactive_users,
    ROUND(SUM(CASE WHEN is_active = 1 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) AS active_rate
FROM user
GROUP BY department
ORDER BY total_users DESC;
```

**Expected result notes:**
Returns user stats per department, including total count, active/inactive counts, and activity rate. Departments with low activity may warrant attention.

---

### Query 8: Mean Time to Resolve Incidents

**Business context:**
The ops manager needs to measure the security team's response efficiency. Mean Time To Resolve (MTTR) is a key SLA metric. Analyzing MTTR by incident type and severity helps identify which classes of incident are handled slowly, requiring process improvements or additional resources.

**Category:** Date analysis
**Difficulty:** Intermediate
**Business role:** Ops manager

**Approach:**
MTTR is fundamentally the difference between two timestamps. SQLite has no native "hour difference" function, so the idiom is `(julianday(resolved_at) - julianday(reported_at)) * 24` — `julianday` converts a date into a "Julian day" float, the subtraction yields days, and multiplying by 24 converts to hours. A key precondition is `WHERE resolved_at IS NOT NULL`: unresolved incidents have NULL `resolved_at`, and arithmetic on it would yield NULL and contaminate the mean, so you must filter them out first (which also matches the business definition that "MTTR only applies to resolved incidents"). Group by (incident_type, severity) as a two-layer grain, taking AVG/MIN/MAX to look at the distribution. Data comes only from the `security_incident` table; no joins needed.

```sql
-- Compute average resolution time (in hours) per incident type
SELECT
    incident_type,
    severity,
    COUNT(*) AS resolved_count,
    ROUND(AVG(
        (julianday(resolved_at) - julianday(reported_at)) * 24
    ), 1) AS avg_resolution_hours,
    ROUND(MIN(
        (julianday(resolved_at) - julianday(reported_at)) * 24
    ), 1) AS min_hours,
    ROUND(MAX(
        (julianday(resolved_at) - julianday(reported_at)) * 24
    ), 1) AS max_hours
FROM security_incident
WHERE resolved_at IS NOT NULL
GROUP BY incident_type, severity
ORDER BY avg_resolution_hours DESC;
```

**Expected result notes:**
Returns the average resolution time (hours) for resolved incidents, grouped by type and severity. The ops manager can identify incident types with high MTTR and optimize the response flow.

---

### Query 9: High-priority Open Remediation Actions

**Business context:**
The operations team needs to see the most urgent open remediation actions at every morning stand-up. P1-Critical and P2-High priority actions need to be handled first. Ops staff need to know the assignee, due date, and associated control to follow up and coordinate.

**Category:** Join
**Difficulty:** Basic
**Business role:** Ops

**Approach:**
Use `remediation_action` as the main table, joining `compliance_control` (for control_id and priority), `control_status` (to determine if it's open), and `user` (for assignee name and department). Two filters work together: `cs.is_terminal = 0` means "not yet in a terminal state" (i.e., PENDING/IN_PROGRESS/DEFERRED), and `cc.priority IN ('P1-Critical', 'P2-High')` keeps only high-priority items. `julianday(ra.due_date) - julianday('now')` computes days until due; **negative means already overdue**, giving the stand-up a clear "X days left / X days overdue" readout. Note we use the runtime `'now'` here — please run as soon as possible after generating the data.

```sql
-- Find high-priority open remediation actions
SELECT
    ra.id,
    ra.title,
    cc.control_id,
    cc.priority,
    cs.name AS status,
    u.full_name AS assigned_to,
    u.department,
    ra.due_date,
    ROUND(julianday(ra.due_date) - julianday('now'), 0) AS days_until_due
FROM remediation_action ra
JOIN compliance_control cc ON ra.control_id = cc.id
JOIN control_status cs ON ra.status_id = cs.id
JOIN user u ON ra.assigned_to_id = u.id
WHERE cs.is_terminal = 0
  AND cc.priority IN ('P1-Critical', 'P2-High')
ORDER BY cc.priority, ra.due_date;
```

**Expected result notes:**
Returns a list of high-priority (P1, P2) open remediation actions, including due date and days until due. A negative value indicates already overdue and needs immediate attention.

---

### Query 10: Audit Log Action-type Distribution

**Business context:**
The compliance auditor needs to analyze the distribution of action types in the system to spot anomalous patterns. For example, excessive DELETE operations might indicate data cleanup or potential issues, and excessive EXPORT operations may carry data exfiltration risk. This is the foundation of compliance audit analysis.

**Category:** Aggregation
**Difficulty:** Basic
**Business role:** Compliance auditor

**Approach:**
Single table `audit_log`, group by `action_type`. As in Q5, use a scalar subquery `(SELECT COUNT(*) FROM audit_log)` as the denominator to compute share. Here we add `COUNT(DISTINCT user_id)`: it answers "is this action being performed by many people or concentrated in a few hands?" — for example, if EXPORT is a small share but only one user is doing it, that's more alarming than "many people are EXPORTing". The grain is "one row per action type", sorted by log count descending so high-frequency actions appear first. This is the entry-point query for compliance forensics, and pairs with Q16 to drill down to a specific user.

```sql
-- Count audit logs per action type
SELECT
    action_type,
    COUNT(*) AS log_count,
    ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM audit_log), 2) AS percentage,
    COUNT(DISTINCT user_id) AS unique_users
FROM audit_log
GROUP BY action_type
ORDER BY log_count DESC;
```

**Expected result notes:**
Returns log count, share, and unique user count per action type. The auditor can identify high-frequency actions and anomalous patterns.

---

### Query 11: Model Owner Risk Responsibility Analysis

**Business context:**
The risk management team needs to evaluate the risk responsibility carried by each model owner. Some users may be responsible for multiple high-risk models, becoming a "single point of risk" for the organization. Identifying these users supports risk distribution and succession planning.

**Category:** Join+aggregation
**Difficulty:** Intermediate
**Business role:** Risk manager

**Approach:**
This is the most important "trap question" in the entire document. The chain is `user` → (1:N) `ai_model` → (1:N) `risk_assessment`. The second LEFT JOIN duplicates each model by its number of assessments — so if you naively write `SUM(CASE WHEN am.risk_tier = 'CRITICAL' THEN 1 ELSE 0 END)`, the same CRITICAL model is counted N times by its N assessments, and `critical_models` is severely inflated (this is row-inflation). The fix is `COUNT(DISTINCT CASE WHEN am.risk_tier = 'CRITICAL' THEN am.id END)`: no matter how many times the join duplicates rows, the same `am.id` is counted only once. Using LEFT JOIN instead of INNER is so that "models that haven't been assessed at all" still count toward `model_count`. `AVG(ra.risk_score)` is weighted by assessment row (models with more assessments carry more weight); to compute an equal-weight per-model average, you'd need to first aggregate within each model, then aggregate per owner (see the fix note below). `HAVING COUNT(DISTINCT am.id) > 1` keeps only owners with "more than one model".

```sql
-- Fix row-inflation: use COUNT(DISTINCT CASE WHEN ... END) to avoid the
-- multiplication of risk_tier sums by the number of assessment rows when
-- LEFT JOIN-ing risk_assessment
SELECT
    u.full_name AS owner_name,
    u.role,
    u.department,
    COUNT(DISTINCT am.id) AS model_count,
    COUNT(DISTINCT CASE WHEN am.risk_tier = 'CRITICAL' THEN am.id END) AS critical_models,
    COUNT(DISTINCT CASE WHEN am.risk_tier = 'HIGH' THEN am.id END) AS high_models,
    ROUND(AVG(ra.risk_score), 2) AS avg_risk_score
FROM user u
JOIN ai_model am ON u.id = am.owner_id
LEFT JOIN risk_assessment ra ON am.id = ra.ai_model_id
WHERE am.is_active = 1
GROUP BY u.id, u.full_name, u.role, u.department
HAVING COUNT(DISTINCT am.id) > 1
ORDER BY critical_models DESC, high_models DESC, model_count DESC;
```

**Expected result notes:**
Returns users with multiple active models, showing their CRITICAL and HIGH model counts and average risk score. Users with concentrated high risk warrant attention.

> **Fix note:** The naive query uses `SUM(CASE WHEN am.risk_tier = 'CRITICAL' THEN 1 ELSE 0 END)`. Under the `LEFT JOIN risk_assessment`, this gets multiplied by the assessment row count (each model multiplied by its number of assessments), so `critical_models` ends up far higher than the true value. Switching to `COUNT(DISTINCT CASE WHEN ... THEN am.id END)` ensures that no matter how many times the join duplicates, the same model id is counted only once.

> **`avg_risk_score` semantic hint (weighted vs equal-weight):** The `AVG(ra.risk_score)` in this query is a **per-assessment-row weighted average** — a model with 5 assessments and a model with 1 will contribute 5 and 1 risk_score values respectively to the mean. This reflects a "cumulative how-much-risk-assessed" view. If the business wants an "equal-weight per-model average" (each model's risk_score is first aggregated, then averaged), you need a two-layer CTE that first aggregates within model and then across owners:
> ```sql
> WITH per_model AS (
>     SELECT am.owner_id, am.id, AVG(ra.risk_score) AS model_avg_risk
>     FROM ai_model am JOIN risk_assessment ra ON am.id = ra.ai_model_id
>     WHERE am.is_active = 1 GROUP BY am.owner_id, am.id
> )
> SELECT owner_id, AVG(model_avg_risk) AS owner_equal_weight_avg FROM per_model GROUP BY owner_id;
> ```
> Both semantics are defensible; the choice depends on whether the business question is "which owner carries the largest cumulative risk volume" or "which owner's models have the highest average risk level".

---

### Query 12: Comparison of Assessment Counts by Risk Category

**Business context:**
The risk analyst needs to understand which risk categories are assessed most frequently. This reflects the organization's attention to each risk class. If some high-severity-weight categories are rarely assessed, that may indicate a blind spot needing more attention.

**Category:** Aggregation
**Difficulty:** Basic
**Business role:** Analyst

**Approach:**
To answer "which categories are assessed a lot/little", you must start from `risk_category` and use **LEFT JOIN** to `risk_assessment`, not INNER JOIN — otherwise a category that's "never been assessed" would have no matching rows and the entire row would vanish, hiding exactly the blind spot we'd most want to detect. Under LEFT JOIN, `COUNT(ra.id)` returns 0 for zero-assessment categories (`COUNT` does not count NULL), and `AVG(...)` returns NULL — both are reasonable. Group by `rc.id, rc.code, rc.name, rc.severity_weight`; the grain is "one row per risk category". Selecting `severity_weight` alongside lets the analyst spot the dangerous combination of "high weight but few assessments" at a glance.

```sql
-- Count assessments per risk category and average score
SELECT
    rc.code,
    rc.name,
    rc.severity_weight,
    COUNT(ra.id) AS assessment_count,
    ROUND(AVG(ra.risk_score), 2) AS avg_risk_score,
    ROUND(AVG(ra.likelihood_score), 2) AS avg_likelihood,
    ROUND(AVG(ra.impact_score), 2) AS avg_impact
FROM risk_category rc
LEFT JOIN risk_assessment ra ON rc.id = ra.risk_category_id
GROUP BY rc.id, rc.code, rc.name, rc.severity_weight
ORDER BY assessment_count DESC;
```

**Expected result notes:**
Returns assessment stats per risk category. Categories with high severity weights but low assessment counts may warrant additional attention.

---

### Query 13: Overdue Remediation Action List

**Business context:**
The ops manager needs to report overdue remediation actions to management each week. Overdue means risk exposure is lasting beyond expectations and could affect compliance status. Identifying overdue actions, assignees, and days overdue enables expediting and resource reallocation.

**Category:** Join+date
**Difficulty:** Intermediate
**Business role:** Ops manager

**Approach:**
Structurally almost identical to Q9 (`remediation_action` joined to `compliance_control`, `control_status`, `user`); the difference lies in the filter and the direction of the date math. "Truly overdue" requires both: `cs.is_terminal = 0` (not yet completed/cancelled) AND `ra.due_date < date('now')` (past due date). Only looking at `due_date` without checking status would include "already completed but the due date was long ago" rows — a common misjudgment — so both conditions are required. `julianday('now') - julianday(ra.due_date)` gives the number of days overdue (note the subtraction is in the opposite direction from Q9, yielding a positive value). Sort descending so the longest-overdue items rise to the top for priority follow-up.

```sql
-- Find overdue open remediation actions
SELECT
    ra.id,
    ra.title,
    cc.control_id,
    cc.priority,
    cs.name AS status,
    u.full_name AS assigned_to,
    ra.due_date,
    ROUND(julianday('now') - julianday(ra.due_date), 0) AS days_overdue
FROM remediation_action ra
JOIN compliance_control cc ON ra.control_id = cc.id
JOIN control_status cs ON ra.status_id = cs.id
JOIN user u ON ra.assigned_to_id = u.id
WHERE cs.is_terminal = 0
  AND ra.due_date < date('now')
ORDER BY days_overdue DESC;
```

**Expected result notes:**
Returns all overdue open remediation actions sorted by days overdue descending. The ops manager can prioritize the longest-overdue items.

---

### Query 14: Framework Compliance Assessment Coverage and Compliance Rate

**Business context:**
The compliance manager needs to report to the CIO on the actual assessment coverage and compliance for each framework. Two independent metrics are both critical: (1) **Assessment coverage rate** = how many controls under a framework have been assessed at least once (measures audit progress); (2) **Compliance rate** = the share of COMPLIANT conclusions among **applicable assessments** (measures compliance health). Low coverage means assessment work isn't done; high coverage with low compliance rate means many problems were found and need remediation.

> **Critical definition:** `NOT_APPLICABLE` means "this control does not apply to this model" — it's a meta-conclusion of the assessment. It **should not** enter the compliance-rate denominator — otherwise "control doesn't apply" gets misclassified as "non-compliant" and artificially depresses the rate. This query uses `applicable_assessments` (excluding NOT_APPLICABLE) as the denominator for the compliance rate, while also keeping `total_assessments` (including NOT_APPLICABLE) as a reference, so the reader can see the difference.

**Category:** CTE
**Difficulty:** Advanced
**Business role:** Compliance manager

**Approach:**
This problem requires producing two **mutually independent** metrics in a single query, so a CTE `framework_assessments` first computes all the per-framework counts in one pass. The chain is `compliance_control` **LEFT JOIN** `model_control_assessment` — LEFT is deliberate: controls that have never been assessed must still count toward `total_controls` (the denominator), otherwise coverage would be inflated. Coverage = `COUNT(DISTINCT mca.control_id) / total_controls`, measures progress; compliance rate = `compliant_count / applicable_assessments`, measures health. **The most critical definition trap:** the compliance-rate denominator uses `applicable_assessments` (excluding `NOT_APPLICABLE`), because "control doesn't apply" is not "non-compliant", and including it would artificially depress the rate. Both ratios use `NULLIF(denominator, 0)` to guard against divide-by-zero. Aggregated by framework; the grain is "one row per framework".

```sql
-- Use the model_control_assessment bridge table to directly measure each framework's
-- "assessed scope" and "compliance health"
-- Key: the denominator of compliance_rate_pct excludes NOT_APPLICABLE (not-applicable
-- controls are NOT non-compliant)
WITH framework_assessments AS (
    SELECT
        cc.framework_id,
        COUNT(DISTINCT cc.id) AS total_controls,
        COUNT(DISTINCT mca.control_id) AS assessed_controls,
        COUNT(mca.id) AS total_assessments,
        SUM(CASE WHEN mca.compliance_status != 'NOT_APPLICABLE'
                 THEN 1 ELSE 0 END) AS applicable_assessments,
        SUM(CASE WHEN mca.compliance_status = 'COMPLIANT' THEN 1 ELSE 0 END) AS compliant_count,
        SUM(CASE WHEN mca.compliance_status = 'PARTIALLY_COMPLIANT' THEN 1 ELSE 0 END) AS partial_count,
        SUM(CASE WHEN mca.compliance_status = 'NON_COMPLIANT' THEN 1 ELSE 0 END) AS non_compliant_count,
        SUM(CASE WHEN mca.compliance_status = 'NOT_APPLICABLE' THEN 1 ELSE 0 END) AS not_applicable_count
    FROM compliance_control cc
    LEFT JOIN model_control_assessment mca ON cc.id = mca.control_id
    GROUP BY cc.framework_id
)
SELECT
    cf.name AS framework_name,
    cf.version,
    fa.total_controls,
    fa.assessed_controls,
    ROUND(fa.assessed_controls * 100.0 / NULLIF(fa.total_controls, 0), 1) AS coverage_pct,
    fa.total_assessments,
    fa.applicable_assessments,
    fa.compliant_count,
    fa.partial_count,
    fa.non_compliant_count,
    fa.not_applicable_count,
    -- The compliance rate denominator uses applicable_assessments, excluding "not applicable" assessments
    ROUND(fa.compliant_count * 100.0 / NULLIF(fa.applicable_assessments, 0), 1) AS compliance_rate_pct
FROM framework_assessments fa
JOIN compliance_framework cf ON fa.framework_id = cf.id
ORDER BY coverage_pct DESC;
```

**Expected result notes:**
Returns three independent dimensions per framework: (1) Assessment coverage rate = assessed controls / total controls; (2) Applicable scope = assessment rows excluding NOT_APPLICABLE; (3) Compliance rate = COMPLIANT / applicable assessment rows. Low coverage → audit work has gaps; low compliance rate → many problems found, remediation pressure is high; high NOT_APPLICABLE share → the match between controls and models needs to be redesigned (many controls simply don't apply). Combining the three, you can distinguish three very different situations: "haven't done the assessments yet", "finished assessing and found a pile of non-compliance", and "wrong controls were chosen".

---

### Query 15: Cross Analysis of Incident Type and Severity

**Business context:**
The security analyst needs to understand the severity distribution of different incident types. For example, are PROMPT_INJECTION incidents mostly HIGH or CRITICAL? This helps shape response strategies and priorities for each incident type.

**Category:** Aggregation
**Difficulty:** Intermediate
**Business role:** Security analyst

**Approach:**
Single table `security_incident`, group by `incident_type`, lay out `severity` horizontally with four `SUM(CASE WHEN severity = ...)` columns — the classic hand-rolled pivot pattern (SQLite has no native PIVOT). Same idea as Q4, just with the grouping dimension changed from "month" to "incident type". The grain is "one row per incident type"; the last column `COUNT(*)` gives the total for that type, sorted descending. Read the table horizontally: whether a given type concentrates in CRITICAL/HIGH determines whether its response strategy should be escalated.

```sql
-- Cross analyze incident type and severity
SELECT
    incident_type,
    SUM(CASE WHEN severity = 'CRITICAL' THEN 1 ELSE 0 END) AS critical,
    SUM(CASE WHEN severity = 'HIGH' THEN 1 ELSE 0 END) AS high,
    SUM(CASE WHEN severity = 'MEDIUM' THEN 1 ELSE 0 END) AS medium,
    SUM(CASE WHEN severity = 'LOW' THEN 1 ELSE 0 END) AS low,
    COUNT(*) AS total
FROM security_incident
GROUP BY incident_type
ORDER BY total DESC;
```

**Expected result notes:**
Returns the distribution of each incident type across severities. The analyst can identify which incident types tend to be more severe and require more urgent response.

---

### Query 16: User Action Audit Trace

**Business context:**
When investigating a potential violation, the compliance auditor needs to trace all actions of a specific user. This query provides a full timeline of user actions, including action types, entities involved, and IP addresses, for forensic analysis.

**Category:** Join
**Difficulty:** Intermediate
**Business role:** Compliance auditor

**Approach:**
Use `audit_log` as the main table, INNER JOIN `user` (the acting user must exist) for name and role, then **LEFT JOIN** `ai_model`. The LEFT JOIN here is key: `audit_log.ai_model_id` is nullable (about 30% of logs are unrelated to a specific model, such as USER or REPORT actions); using INNER JOIN would swallow those rows and break the timeline. `WHERE al.user_id = 5` pins down the user under investigation, `ORDER BY al.timestamp DESC LIMIT 50` takes the latest 50 entries to reconstruct the timeline. Side note: `entity_type` + `entity_id` is a polymorphic reference, with no schema-level FK; to relate back to a real record, you must select the target table by `entity_type` at the application layer.

```sql
-- Trace a specific user's action history (example: investigate user ID 5)
SELECT
    al.timestamp,
    u.full_name,
    u.role,
    al.action_type,
    al.entity_type,
    al.entity_id,
    am.model_name,
    al.details,
    al.ip_address
FROM audit_log al
JOIN user u ON al.user_id = u.id
LEFT JOIN ai_model am ON al.ai_model_id = am.id
WHERE al.user_id = 5
ORDER BY al.timestamp DESC
LIMIT 50;
```

**Expected result notes:**
Returns detailed info for the user's most recent 50 action records. The auditor can reconstruct the user's action timeline and spot anomalous behavior.

> **Polymorphic entity_id hint:** `al.entity_id` is coordinated with `al.entity_type`. To relate back to real records by `(entity_type, entity_id)`, you must select the join target table based on `entity_type` at the application layer (there is no FK constraint at the schema level).

---

### Query 17: Production Model Risk Summary

**Business context:**
The CTO and CISO care most about the risk of AI models in production. Compared to dev and test environments, problems in production directly affect the business and customers. This query summarizes the risk posture of production models, helping executives understand the actual business risk exposure.

**Category:** Join+aggregation
**Difficulty:** Intermediate
**Business role:** Exec

**Approach:**
`ai_model` **LEFT JOIN** `risk_assessment`, filtered to production and active models, aggregated by `risk_tier`. Two filters need care: `deployment_env = 'production'` uses `production` **all lowercase**; SQLite string comparison is case-sensitive, so `'Production'` would return zero rows; `is_active = 1` excludes retired models. The LEFT JOIN lets "production but never assessed" models appear in the result (which is itself a signal the executive should care about). `COUNT(DISTINCT am.id)` counts models, `COUNT(ra.id)` counts assessments — keeping them separate prevents model count from being multiplied by assessment rows. `SUM(CASE WHEN mitigation_status = ...)` splits unmitigated/mitigated into two columns.

```sql
-- Summarize risk assessments for production-environment models
SELECT
    am.risk_tier,
    COUNT(DISTINCT am.id) AS model_count,
    COUNT(ra.id) AS total_assessments,
    ROUND(AVG(ra.risk_score), 2) AS avg_risk_score,
    SUM(CASE WHEN ra.mitigation_status = 'NOT_STARTED' THEN 1 ELSE 0 END) AS unmitigated,
    SUM(CASE WHEN ra.mitigation_status = 'MITIGATED' THEN 1 ELSE 0 END) AS mitigated
FROM ai_model am
LEFT JOIN risk_assessment ra ON am.id = ra.ai_model_id
WHERE am.deployment_env = 'production'
  AND am.is_active = 1
GROUP BY am.risk_tier
ORDER BY
    CASE am.risk_tier
        WHEN 'CRITICAL' THEN 1
        WHEN 'HIGH' THEN 2
        WHEN 'MEDIUM' THEN 3
        WHEN 'LOW' THEN 4
    END;
```

**Expected result notes:**
Returns an assessment summary per risk tier for production models, including average risk score and mitigation status distribution. Executives should focus on the number of unmitigated assessments in the CRITICAL/HIGH tiers.

---

### Query 18: Remediation Action Assignee Workload Analysis

**Business context:**
The ops manager needs to evaluate whether remediation action assignments are balanced. Some people may have been assigned too many tasks and become overloaded, while others may be relatively idle. This analysis helps rebalance the workload and ensure timely completion.

**Category:** Window function
**Difficulty:** Advanced
**Business role:** Ops manager

**Approach:**
Join `remediation_action` to `user` (assignee) and `control_status` (to determine status), aggregate by assignee. For each assignee compute three numbers: total assignments `COUNT(*)`, in-flight count `SUM(CASE WHEN cs.is_terminal = 0 ...)`, completed count `SUM(CASE WHEN cs.code = 'COMPLETED' ...)`, then derive completion rate. The highlight is the window function `RANK() OVER (ORDER BY SUM(CASE WHEN cs.is_terminal = 0 ...) DESC)`: after the group aggregation, it ranks assignees by "in-flight task count", directly answering "who is most loaded?". `HAVING COUNT(*) >= 2` filters out assignees with only one or two tasks who have no meaningful sample. The grain is "one row per assignee".

```sql
-- Analyze remediation assignee workload distribution
SELECT
    u.full_name,
    u.role,
    u.department,
    COUNT(*) AS total_assigned,
    SUM(CASE WHEN cs.is_terminal = 0 THEN 1 ELSE 0 END) AS open_actions,
    SUM(CASE WHEN cs.code = 'COMPLETED' THEN 1 ELSE 0 END) AS completed,
    ROUND(SUM(CASE WHEN cs.code = 'COMPLETED' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) AS completion_rate,
    RANK() OVER (ORDER BY SUM(CASE WHEN cs.is_terminal = 0 THEN 1 ELSE 0 END) DESC) AS workload_rank
FROM remediation_action ra
JOIN user u ON ra.assigned_to_id = u.id
JOIN control_status cs ON ra.status_id = cs.id
GROUP BY u.id, u.full_name, u.role, u.department
HAVING COUNT(*) >= 2
ORDER BY open_actions DESC;
```

**Expected result notes:**
Returns remediation stats per assignee, including total assigned, in-progress count, completed count, and completion rate. The workload ranking helps identify the most heavily loaded people.

---

### Query 19: Model Audit Coverage Check

**Business context:**
The compliance manager needs to ensure that every active model has been audited periodically. If a model has never been audited, or it's been more than 6 months since the last audit, the model needs scheduling for audit. This is an important check for continuous compliance.

> **Definition note:** This query no longer requires "model registered ≥ 6 months" for "never-audited" models — as long as `last_audit_date IS NULL`, the model lands on the to-be-audited list. This means freshly registered models also show up in the result, and the compliance manager should combine the `created_at` column to judge whether audit urgency is real. If you want to strictly filter to "models registered > 6 months that should have been audited", add `AND julianday('now') - julianday(am.created_at) > 180` to the WHERE clause.

**Category:** Subquery
**Difficulty:** Intermediate
**Business role:** Compliance manager

**Approach:**
Main table `ai_model` joined to `user` for the owner name. The core is the "or" logic in WHERE: `last_audit_date IS NULL` (never audited) **OR** `julianday('now') - julianday(last_audit_date) > 180` (more than 180 days since the last audit). `CASE WHEN last_audit_date IS NULL THEN 'Never audited' ELSE ... END` translates these two cases into human-readable labels. `assessment_count` is computed inline via a correlated subquery `(SELECT COUNT(*) FROM risk_assessment WHERE ai_model_id = am.id)`, avoiding another join that would multiply rows. `ORDER BY CASE WHEN last_audit_date IS NULL THEN 0 ELSE 1 END` pushes "never audited" to the top. This query relies on the dynamic time anchor to maintain discriminative power (the hit rate is designed at 20–30%), so be sure to run it immediately after generation.

```sql
-- Find models that need auditing (over 180 days since last audit, or never audited)
SELECT
    am.model_name,
    am.version,
    am.model_type,
    am.risk_tier,
    am.deployment_env,
    u.full_name AS owner,
    am.created_at,
    am.last_audit_date,
    CASE
        WHEN am.last_audit_date IS NULL THEN 'Never audited'
        ELSE CAST(ROUND(julianday('now') - julianday(am.last_audit_date)) AS INTEGER) || ' days ago'
    END AS audit_status,
    (SELECT COUNT(*) FROM risk_assessment WHERE ai_model_id = am.id) AS assessment_count
FROM ai_model am
JOIN user u ON am.owner_id = u.id
WHERE am.is_active = 1
  AND (
    am.last_audit_date IS NULL
    OR julianday('now') - julianday(am.last_audit_date) > 180
  )
ORDER BY
    CASE WHEN am.last_audit_date IS NULL THEN 0 ELSE 1 END,
    am.last_audit_date;
```

**Expected result notes:**
Returns a list of active models needing audit, prioritizing those never audited. The compliance manager can use this to schedule audits. Because the dataset uses a dynamic time anchor (NOW at generation time), this query's hit rate should be in the 20-30% range (about 20% never audited + about 10% stale), preserving discriminative power.

---

### Query 20: Key Compliance Metrics Dashboard

**Business context:**
The CTO or CISO needs a comprehensive compliance dashboard showing key metrics at a glance. This query aggregates key numbers across multiple dimensions for use in management weekly or monthly reports. One query returns all key metrics, making it easy to build a dashboard.

**Category:** CTE+aggregation
**Difficulty:** Advanced
**Business role:** Exec/C-Level

**Approach:**
This problem rolls up key numbers scattered across multiple tables into "one dashboard row". The pattern is to put a string of mutually independent scalar subqueries inside a CTE `metrics`, each computing one KPI (active model count, high-risk model count, unmitigated risks, unclosed incidents, in-progress/overdue remediations, non-compliant assessments…), each doing its own work without interference. The outer SELECT then lays them out and adds derived ratios (e.g., high-risk share). Each division is wrapped in `NULLIF(denominator, 0)` to guard against divide-by-zero. Keep the definitions consistent with other queries: high-risk = `risk_tier IN ('CRITICAL','HIGH')`, unclosed incident = `status NOT IN ('RESOLVED','CLOSED')`, open remediation = `is_terminal = 0`. The result is just one row, ready to feed into the dashboard card on a board weekly/monthly report.

```sql
-- Comprehensive compliance metrics dashboard
WITH metrics AS (
    SELECT
        (SELECT COUNT(*) FROM ai_model WHERE is_active = 1) AS active_models,
        (SELECT COUNT(*) FROM ai_model WHERE is_active = 1 AND risk_tier IN ('CRITICAL', 'HIGH')) AS high_risk_models,
        (SELECT COUNT(*) FROM risk_assessment) AS total_assessments,
        (SELECT COUNT(*) FROM risk_assessment WHERE mitigation_status = 'NOT_STARTED') AS unmitigated_risks,
        (SELECT COUNT(*) FROM security_incident WHERE status NOT IN ('RESOLVED', 'CLOSED')) AS open_incidents,
        (SELECT COUNT(*) FROM security_incident WHERE severity = 'CRITICAL' AND status NOT IN ('RESOLVED', 'CLOSED')) AS critical_open_incidents,
        (SELECT COUNT(*) FROM remediation_action ra JOIN control_status cs ON ra.status_id = cs.id WHERE cs.is_terminal = 0) AS open_remediations,
        (SELECT COUNT(*) FROM remediation_action ra JOIN control_status cs ON ra.status_id = cs.id WHERE cs.is_terminal = 0 AND ra.due_date < date('now')) AS overdue_remediations,
        (SELECT COUNT(DISTINCT framework_id) FROM compliance_control) AS frameworks_in_use,
        (SELECT COUNT(*) FROM user WHERE is_active = 1) AS active_users,
        (SELECT COUNT(*) FROM model_control_assessment WHERE compliance_status = 'NON_COMPLIANT') AS non_compliant_assessments
)
SELECT
    active_models AS 'Active Models',
    high_risk_models AS 'High-Risk Models',
    ROUND(high_risk_models * 100.0 / NULLIF(active_models, 0), 1) AS 'High-Risk Share (%)',
    total_assessments AS 'Total Assessments',
    unmitigated_risks AS 'Unmitigated Risks',
    open_incidents AS 'Open Incidents',
    critical_open_incidents AS 'CRITICAL Open',
    open_remediations AS 'Open Remediations',
    overdue_remediations AS 'Overdue Remediations',
    frameworks_in_use AS 'Frameworks In Use',
    active_users AS 'Active Users',
    non_compliant_assessments AS 'Non-Compliant Assessments'
FROM metrics;
```

**Expected result notes:**
Returns one row containing all key metrics. The executive can see at a glance: high-risk model share, unmitigated risks, CRITICAL unclosed incidents, overdue remediations, model-control non-compliance count, and other key indicators. All divisions wrap the denominator in `NULLIF(..., 0)` to prevent divide-by-zero.

---

## Query Category Summary

| Category | Count | Query numbers |
|------|------|----------|
| Aggregation | 5 | 1, 5, 7, 10, 12 |
| Join operations | 3 | 3, 9, 16 |
| Window functions | 2 | 6, 18 |
| Date/time analysis | 3 | 4, 8, 13 |
| Subquery / CTE | 3 | 14, 19, 20 |
| Join+aggregation | 4 | 2, 11, 15, 17 |

## Business Role Coverage

| Role | Count | Query numbers |
|------|------|----------|
| Exec/C-Level | 3 | 1, 17, 20 |
| Compliance manager | 3 | 2, 14, 19 |
| Risk manager | 2 | 3, 11 |
| Ops manager | 4 | 5, 8, 13, 18 |
| Ops | 1 | 9 |
| Analyst | 2 | 6, 12 |
| Security analyst | 2 | 4, 15 |
| Compliance auditor | 2 | 10, 16 |
| HR manager | 1 | 7 |

**Total:** 3+3+2+4+1+2+2+2+1 = 20 (each query belongs to exactly one role)

---

## Notes

- All queries are written in SQLite 3.x syntax
- The table name `user` is a reserved keyword in databases such as PostgreSQL; quote it when porting
- Date functions `julianday()`, `strftime()`, `date('now')` are SQLite-specific; when porting to other databases, replace with the target dialect's equivalents (e.g., PostgreSQL's `EXTRACT`, `AGE`, `NOW()`)
- The numbers in the TSV filenames indicate the table load order (topological sort)
- The dataset uses a dynamic time anchor: every time the generator is rerun, absolute dates update; queries run immediately after produce reasonable offsets between `julianday('now')` and the data dates
