# Prior Authorization Operations Business SQL Queries

**Dataset:** `health_insurance_prior_authorization_high`
**Engine:** SQLite (all queries are SQLite-compatible)
**Total queries:** 30
**Reference date (TODAY):** Resolved at generation time via `date.today()`. The generator re-anchors timestamps to the system day every time, so `DATE('now', '-N days')` filters always return non-empty results when executed shortly after regeneration.

For business background, company profile, industry primer, and glossary, see `01-health_insurance_prior_authorization_high_business_context.md`. For table schema, fields, and generation rules, see `02-health_insurance_prior_authorization_high_er_document.md`. This document assumes you have read both.

---

## 1. How to Use This Document

This document is written for an intern who has just finished reading the business context and ER document and is about to be sent off by their manager to run these queries. It is not just a list of SQL snippets but a teaching aid: each item first explains why the question is being asked and how to think about it, then provides the SQL, and finally tells you what to do once the numbers come back.

Each query follows the same five-part structure, and we recommend reading them in order:

- **Business context** explains who is asking, what scenario triggered the question, and what decision the answer will drive. This section ties the query back to the real business.
- **Category / difficulty / business role** are three tags that help you quickly judge which SQL technique the query exercises, how hard it is, and which job role it serves.
- **Approach** walks you through which tables to touch, how the joins line up, what aggregation grain to use, why CTEs and window functions are (or aren't) used, and any SQLite pitfalls to watch for, all before you see the SQL. After reading this section, you should be able to write something close to the answer yourself.
- **SQL** is the runnable query body, executable directly against the generated SQLite database.
- **Expected result** first describes the shape and key magnitudes of the result set (those magnitudes correspond to the business traps stated in the ER document), then points out what the analyst should do next. Getting numbers out is the beginning of analysis, not the end.

Two conventions run through the whole document. First, every time filter is written as a rolling window with `DATE('now', '-N days')` rather than a hardcoded date, because the generator anchors data to the run day, so queries always have data after regeneration. Second, every query traces back to one of the business questions listed in the business context document; a question-to-query mapping table is at the end.

---

## 2. Query Index

| # | Title | Category | Difficulty | Role |
|---|---|---|---|---|
|  1 | Daily PA request volume by status | Aggregation + Date | Basic | Operations |
|  2 | Approval rate by metal tier | Join + Aggregation | Basic | Executive |
|  3 | Top N denial codes (JSON unpack) | Aggregation + JSON | Intermediate | Analyst |
|  4 | Reviewer productivity by role | Join + Aggregation | Basic | Manager |
|  5 | Average turnaround hours by urgency | Join + Aggregation + Date | Intermediate | Manager |
|  6 | SLA breach rate by urgency | Join + Aggregation | Intermediate | Operations |
|  7 | Provider approval-rate outliers | Join + Aggregation | Intermediate | Manager |
|  8 | In-network vs out-of-network approval rate | Join + Aggregation | Basic | Finance |
|  9 | PA -> Claim conversion rate (leakage analysis) | Join + Aggregation | Intermediate | Finance |
| 10 | Appeal volume by level | Aggregation | Basic | Operations |
| 11 | Overturn rate by appeal level | Aggregation | Basic | Manager |
| 12 | Multi-level appeals funnel | CTE + Aggregation | Advanced | Analyst |
| 13 | Denial heatmap by specialty | Join + Aggregation | Intermediate | Analyst |
| 14 | Top 10 procedure codes by request volume | Join + Aggregation | Basic | Operations |
| 15 | Confidence quantiles by decision | Window (NTILE) | Intermediate | Analyst |
| 16 | Monthly PA volume trend + MoM growth | Window (LAG) | Intermediate | Executive |
| 17 | 6-month decision-mix drift | CTE + Window | Advanced | Executive |
| 18 | Open request aging + SLA risk | Date + Join | Intermediate | Operations |
| 19 | Members with multiple submissions (chronic-condition cohort) | Subquery | Basic | Analyst |
| 20 | Reviewer workload balance | CTE + Window (RANK) | Advanced | Manager |
| 21 | Policy citation rate by category | Join + JSON | Intermediate | Analyst |
| 22 | Members with coverage ending soon | Date + Join | Intermediate | Operations |
| 23 | Auto-rule vs human decision outcomes | Join + Aggregation | Intermediate | Executive |
| 24 | Clinical note type distribution | Aggregation + Subquery | Basic | Operations |
| 25 | Low-confidence extracted facts (QA review) | Join + Filter | Basic | Analyst |
| 26 | Top 10 providers by authorized paid amount | Join + Aggregation | Intermediate | Finance |
| 27 | Member cost-share % by metal tier | Join + Aggregation | Intermediate | Finance |
| 28 | Appeal recovery amount (overturned denials) | CTE + Join | Advanced | Finance |
| 29 | Stalled requests still undecided past SLA | Date + Subquery | Advanced | Operations |
| 30 | Denial reason Pareto (cumulative %) | Window + JSON | Advanced | Analyst |

---

## 3. Query Body

### Query 1: Daily PA request volume by status

**Category:** Aggregation + Date
**Difficulty:** Basic
**Business role:** Operations

**Business context:**
The operations team runs this report at 8:00 AM every day to size up the day's review queue. Volume spikes (Monday mornings, the day after a long holiday) directly drive staffing for the day; status mix signals whether enough cases are clearing or whether they are piling up in `pending` / `in_review`. Persistent drift in status mix gets escalated to the Operations Director.

**Approach:**
This one only touches `pa_requests`; no joins needed. The key is the aggregation grain: group by "day plus status," so each row represents one status on one day. Use `DATE(submitted_at)` to truncate the timestamp to the date (dropping HMS), then GROUP BY it together with `status`. WHERE uses `DATE('now', '-30 days')` to take a rolling 30-day window. Sort by date descending, then volume descending, so operations can scan from the most recent peaks. No CTE or window function needed; one GROUP BY does it.

**SQL:**
```sql
SELECT
    DATE(submitted_at)            AS submission_date,
    status,
    COUNT(*)                      AS request_count
FROM pa_requests
WHERE submitted_at >= DATE('now', '-30 days')
GROUP BY DATE(submitted_at), status
ORDER BY submission_date DESC, request_count DESC;
```

**Expected result:**
A daily breakdown over the last 30 days. Status values come from the `pa_requests.status` enum: `approved` / `denied` / `pended` / `appealed` / `withdrawn` (`pending` / `in_review` are rarer because the generator suppresses old in-flight requests). At about ~2 per status per day, a typical day yields 4-8 rows.

---

### Query 2: Approval rate by metal tier

**Category:** Join + Aggregation
**Difficulty:** Basic
**Business role:** Executive

**Business context:**
Approval rate by metal tier feeds Meridian's quarterly product review. Lower tiers (Bronze) usually have a stricter medical-necessity bar than Platinum; any tier whose approval rate differs from the others by more than 10 percentage points triggers an investigation into whether the cause is policy calibration drift or anomalous provider behavior.

**Approach:**
`metal_tier` lives on `plans`, while decisions live on `pa_decisions`, so you need to join all the way through `pa_decisions` -> `pa_requests` -> `members` -> `plans`, chaining four tables. The aggregation grain is one row per metal tier. Approval should include `partial_approved` in the numerator (a partial approval is still an approval), so use conditional aggregation like `SUM(CASE WHEN decision IN ('approved','partial_approved') ...)`. INNER JOIN works throughout because every decision must have a matching request, member, and plan.

**SQL:**
```sql
SELECT
    pl.metal_tier,
    COUNT(*)                                                          AS total_decisions,
    SUM(CASE WHEN d.decision IN ('approved', 'partial_approved')
             THEN 1 ELSE 0 END)                                       AS approved,
    SUM(CASE WHEN d.decision = 'denied' THEN 1 ELSE 0 END)            AS denied,
    ROUND(100.0 * SUM(CASE WHEN d.decision IN ('approved', 'partial_approved')
                           THEN 1 ELSE 0 END) / COUNT(*), 2)          AS approval_rate_pct
FROM pa_decisions d
JOIN pa_requests  r  ON d.request_id = r.request_id
JOIN members      m  ON r.member_id  = m.member_id
JOIN plans        pl ON m.plan_id    = pl.plan_id
GROUP BY pl.metal_tier
ORDER BY approval_rate_pct DESC;
```

**Expected result:**
Four rows (Bronze / Silver / Gold / Platinum). Approval rate skews by tier as designed: Bronze ~50%, Silver ~61%, Gold ~68%, Platinum ~84%.

---

### Query 3: Top N denial codes (JSON unpack)

**Category:** Aggregation + JSON
**Difficulty:** Intermediate
**Business role:** Analyst

**Business context:**
Denial codes (CARC/RARC) are the **structured** reasons behind denials. Unlike the free-text `decision_reason_text`, they cluster cleanly. The denial management analyst publishes this leaderboard monthly: any code exceeding 10% of denial volume becomes a candidate for provider re-education or policy clarification.

**Approach:**
`denial_codes_json` is a JSON array stored as TEXT; one denial may carry 1 to 2 codes. To count by code, you first need to unpack the array into rows, which is exactly what SQLite's `json_each` is for: write `FROM pa_decisions d, json_each(d.denial_codes_json) je` for an implicit cross join, and each array element becomes a row. WHERE filters out `denial_codes_json IS NULL` non-denial rows and then limits to a 6-month window. Group by `je.value` (the unpacked code) and count. Use `SUM(COUNT(*)) OVER ()` as an unpartitioned window to get the grand total in the denominator, saving you a second subquery.

**SQL:**
```sql
SELECT
    je.value                                  AS denial_code,
    COUNT(*)                                  AS occurrences,
    ROUND(100.0 * COUNT(*) /
          SUM(COUNT(*)) OVER (), 2)           AS pct_of_total
FROM pa_decisions d, json_each(d.denial_codes_json) je
WHERE d.denial_codes_json IS NOT NULL
  AND d.decided_at >= DATE('now', '-6 months')
GROUP BY je.value
ORDER BY occurrences DESC;
```

**Expected result:**
~9 rows (one per CARC/RARC code). The head code (e.g., `N-130`) typically accounts for ~15-18% of denial-code mentions; the long tail is ~5-10% each.

---

### Query 4: Reviewer productivity by role

**Category:** Join + Aggregation
**Difficulty:** Basic
**Business role:** Manager

**Business context:**
The Medical Operations Manager tracks the number of decisions rendered by each reviewer role to measure the automation rate. `auto_rule` costs about $2 per decision; `medical_director` costs about $80. A sustained rise in the medical director share means either rule coverage is shrinking or case complexity is climbing, and both need a response.

**Approach:**
`role` lives on `reviewers`; decisions live on `pa_decisions`; join the two on `reviewer_id`. The aggregation grain is one row per role. `COUNT(d.decision_id)` gives the decision count per role; the role-by-role share is computed using `SUM(COUNT(...)) OVER ()` to get group and grand total in a single scan. INNER JOIN is fine here because we only care about roles that actually rendered decisions in the window; if you also wanted to surface zero-productivity active reviewers, you would switch to LEFT JOIN (Query 20 does that).

**SQL:**
```sql
SELECT
    rv.role,
    COUNT(d.decision_id)                                              AS decisions,
    ROUND(100.0 * COUNT(d.decision_id) /
          SUM(COUNT(d.decision_id)) OVER (), 2)                       AS pct_of_total,
    ROUND(AVG(d.confidence_score), 3)                                 AS avg_confidence,
    SUM(CASE WHEN d.decision IN ('approved', 'partial_approved')
             THEN 1 ELSE 0 END)                                       AS approved_count,
    ROUND(100.0 * SUM(CASE WHEN d.decision IN ('approved', 'partial_approved')
                           THEN 1 ELSE 0 END) / COUNT(d.decision_id), 2)
                                                                      AS approval_rate_pct
FROM reviewers rv
JOIN pa_decisions d ON d.reviewer_id = rv.reviewer_id
WHERE d.decided_at >= DATE('now', '-90 days')
GROUP BY rv.role
ORDER BY decisions DESC;
```

**Expected result:**
Four roles. `clinical_reviewer` and `auto_rule` dominate (~60% + ~30%). `medical_director` and `external_reviewer` are smaller in volume but show the lowest approval rates because they handle the hard cases escalated to them.

---

### Query 5: Average turnaround hours by urgency

**Category:** Join + Aggregation + Date
**Difficulty:** Intermediate
**Business role:** Manager

**Business context:**
Turnaround time vs SLA is the headline operational metric. The SLA Director publishes it weekly. Any urgency tier whose average exceeds 50% of its SLA window triggers a process review.

**Approach:**
Turnaround is already materialized in `pa_decisions.tat_hours`, so you can `AVG` / `MIN` / `MAX` it directly without recomputing `JULIANDAY` differences each time, which is both faster and less error-prone. Three-table join: `pa_requests` supplies urgency, `pa_decisions` supplies tat_hours, and `sla_config` supplies the SLA window for the urgency. The grain is one row per urgency. Use a `CASE` in ORDER BY to sort emergent / urgent / routine in business-importance order rather than alphabetical.

**SQL:**
```sql
-- Use pa_decisions.tat_hours (materialized turnaround field) to avoid recomputing JULIANDAY differences.
SELECT
    r.urgency,
    sla.sla_hours,
    COUNT(*)                  AS decided_requests,
    ROUND(AVG(d.tat_hours), 2) AS avg_hours_to_decide,
    ROUND(MIN(d.tat_hours), 2) AS min_hours,
    ROUND(MAX(d.tat_hours), 2) AS max_hours
FROM pa_requests   r
JOIN pa_decisions  d   ON d.request_id = r.request_id
JOIN sla_config    sla ON sla.urgency  = r.urgency
WHERE r.submitted_at >= DATE('now', '-90 days')
GROUP BY r.urgency, sla.sla_hours
ORDER BY
    CASE r.urgency
        WHEN 'emergent' THEN 1
        WHEN 'urgent'   THEN 2
        WHEN 'routine'  THEN 3
    END;
```

**Expected result:**
Three rows. `emergent` averages near 1 hour (SLA = 2); `urgent` averages 30-50 hours (SLA = 72); `routine` averages 100-200 hours (SLA = 336).

---

### Query 6: SLA breach rate by urgency

**Category:** Join + Aggregation
**Difficulty:** Intermediate
**Business role:** Operations

**Business context:**
A single `emergent` breach can directly delay a patient's care; 1 in 100 routine breaches is normal noise. This report drives operational escalation and is reviewed at the daily ops huddle.

**Approach:**
Whether a row breached is already materialized as the boolean `pa_decisions.sla_breached`, so the breach count is `SUM(CASE WHEN sla_breached ...)`, and the breach rate is just that divided by the total decision count. The join shape is the same as the previous query (requests plus decisions plus sla_config), and the grain is one row per urgency. Selecting `sla_hours` together with the rate shows readers the underlying time standard behind the denominator. Sort by breach rate descending so the worst urgency tier is at the top.

**SQL:**
```sql
-- Use pa_decisions.sla_breached (materialized breach flag).
SELECT
    r.urgency,
    sla.sla_hours,
    COUNT(*)                                              AS total_decisions,
    SUM(CASE WHEN d.sla_breached THEN 1 ELSE 0 END)       AS breaches,
    ROUND(100.0 * SUM(CASE WHEN d.sla_breached THEN 1 ELSE 0 END)
                / COUNT(*), 2)                            AS breach_rate_pct
FROM pa_requests  r
JOIN pa_decisions d   ON d.request_id = r.request_id
JOIN sla_config   sla ON sla.urgency  = r.urgency
WHERE r.submitted_at >= DATE('now', '-90 days')
GROUP BY r.urgency, sla.sla_hours
ORDER BY breach_rate_pct DESC;
```

**Expected result:**
The generator injects a ~10% breach long tail by design. Per-urgency breach rates should fall in the 8-12% range.

---

### Query 7: Provider approval-rate outliers

**Category:** Join + Aggregation
**Difficulty:** Intermediate
**Business role:** Manager

**Business context:**
The Provider Network Manager looks for two kinds of outliers: abnormally low approval rates (poor documentation, overspecialist prescribing, suspected fraud) and abnormally high approval rates (potential rubber-stamping risk worth auditing). Both ends get follow-up.

**Approach:**
Start from `providers`, join `pa_requests`, then `pa_decisions`; the grain is one row per provider. There is a key statistical trap here: rates on small samples are unreliable (a provider with 2 decisions has an approval rate that is either 0% or 100%), so use `HAVING COUNT(d.decision_id) >= 5` to filter out low-volume providers and keep only the statistically meaningful ones. Sort ascending by approval rate to push the lowest outliers to the top, and `LIMIT 20` keeps the list manageable. To surface the other extreme, flip the sort direction.

**SQL:**
```sql
SELECT
    p.npi,
    p.provider_name,
    p.specialty,
    p.in_network,
    COUNT(d.decision_id)                                              AS total_decisions,
    SUM(CASE WHEN d.decision IN ('approved', 'partial_approved')
             THEN 1 ELSE 0 END)                                       AS approved,
    ROUND(100.0 * SUM(CASE WHEN d.decision IN ('approved', 'partial_approved')
                           THEN 1 ELSE 0 END) / COUNT(d.decision_id), 2)
                                                                      AS approval_rate_pct
FROM providers     p
JOIN pa_requests   r ON r.provider_npi = p.npi
JOIN pa_decisions  d ON d.request_id   = r.request_id
WHERE r.submitted_at >= DATE('now', '-180 days')
GROUP BY p.npi, p.provider_name, p.specialty, p.in_network
HAVING COUNT(d.decision_id) >= 5
ORDER BY approval_rate_pct ASC, total_decisions DESC
LIMIT 20;
```

**Expected result:**
The 20 providers with at least 5 decisions in the last 180 days. The lowest approval rates (often 30-45%) are flagged for follow-up; the list naturally tilts toward out-of-network providers and specialties like Oncology / Pain Management.

---

### Query 8: In-network vs out-of-network approval rate

**Category:** Join + Aggregation
**Difficulty:** Basic
**Business role:** Finance

**Business context:**
Finance tracks the in-network vs OON approval rate gap to estimate cost exposure: OON approvals trigger balance-billing complaints and higher allowed amounts. A gap greater than 15 percentage points triggers a network adequacy review.

**Approach:**
Same three-table join as the previous query (providers plus requests plus decisions), but the aggregation grain becomes just `in_network`, so the result is two rows: one for in-network, one for out-of-network. Use conditional aggregation to compute the approval / denial counts and approval rate for each, and also surface the average confidence for comparison. Booleans are stored as 0/1 in SQLite, so you can GROUP BY directly and sort descending to put in-network (1) on top.

**SQL:**
```sql
SELECT
    p.in_network,
    COUNT(d.decision_id)                                              AS total_decisions,
    SUM(CASE WHEN d.decision IN ('approved', 'partial_approved')
             THEN 1 ELSE 0 END)                                       AS approved,
    SUM(CASE WHEN d.decision = 'denied' THEN 1 ELSE 0 END)            AS denied,
    ROUND(100.0 * SUM(CASE WHEN d.decision IN ('approved', 'partial_approved')
                           THEN 1 ELSE 0 END) / COUNT(d.decision_id), 2)
                                                                      AS approval_rate_pct,
    ROUND(AVG(d.confidence_score), 3)                                 AS avg_confidence
FROM providers     p
JOIN pa_requests   r ON r.provider_npi = p.npi
JOIN pa_decisions  d ON d.request_id   = r.request_id
WHERE r.submitted_at >= DATE('now', '-180 days')
GROUP BY p.in_network
ORDER BY p.in_network DESC;
```

**Expected result:**
Two rows. 85% of providers are in-network, so the in-network row carries about 85% of the decision volume and shows a higher approval rate than the OON row.

---

### Query 9: PA -> Claim conversion rate (leakage analysis)

**Category:** Join + Aggregation
**Difficulty:** Intermediate
**Business role:** Finance

**Business context:**
"PA approved but no claim ever filed" is leakage: the member was authorized but never actually received the service. Some leakage is normal (scheduling delays, members changing their minds); persistently high leakage signals pre-auth fatigue or provider gaming. The CFO uses this as a leading indicator that reserves may be overstated.

**Approach:**
Leakage is defined as "approved but no claim produced," which requires `LEFT JOIN claims`: start from approved decisions and left-join claims; rows that fail to match are the leakage. Swapping INNER for LEFT here is vital because we are precisely trying to count decisions with no claim; INNER would delete them and force leakage to 0. Use `COUNT(DISTINCT ...)` to guard against duplicate counts from one-to-many relationships. The whole query returns one summary row: approved decision count, claim count, conversion rate, and leakage count.

**SQL:**
```sql
SELECT
    COUNT(DISTINCT d.decision_id)                                     AS approved_decisions,
    COUNT(DISTINCT c.claim_id)                                        AS claims_filed,
    ROUND(100.0 * COUNT(DISTINCT c.claim_id) /
                  COUNT(DISTINCT d.decision_id), 2)                   AS conversion_pct,
    COUNT(DISTINCT d.decision_id) - COUNT(DISTINCT c.decision_id)     AS leakage_count
FROM pa_decisions d
LEFT JOIN claims  c ON c.decision_id = d.decision_id
WHERE d.decision     IN ('approved', 'partial_approved')
  AND d.decided_at   >= DATE('now', '-180 days');
```

**Expected result:**
A single summary row. Approved decisions ~300; claims ~180; conversion rate ~60%; leakage ~120 decisions.

---

### Query 10: Appeal volume by level

**Category:** Aggregation
**Difficulty:** Basic
**Business role:** Operations

**Business context:**
Appeals operations sizes case load by level: level-1 is internal review, level-2 is medical director review, and external is the Independent Review Organization (IRO). Each level has different staffing and SLA demands.

**Approach:**
This query touches only `appeals`; no joins. Group by `level_number` and `appeal_level` (the integer handles correct sorting, the text reads well), so each row represents one appeal level. Use conditional aggregation to break out pending / upheld / overturned outcomes per level, making in-flight vs resolved visible at a glance. WHERE limits to the last 180 days. Sort ascending by `level_number` to read the funnel narrowing from L1 outward.

**SQL:**
```sql
SELECT
    level_number,
    appeal_level,
    COUNT(*)                                                AS total_appeals,
    SUM(CASE WHEN outcome = 'pending'    THEN 1 ELSE 0 END) AS still_open,
    SUM(CASE WHEN outcome = 'upheld'     THEN 1 ELSE 0 END) AS upheld,
    SUM(CASE WHEN outcome = 'overturned' THEN 1 ELSE 0 END) AS overturned
FROM appeals
WHERE submitted_at >= DATE('now', '-180 days')
GROUP BY level_number, appeal_level
ORDER BY level_number;
```

**Expected result:**
Three rows, reflecting the escalation funnel shape. L1 dominates (~100 cases), L2 ~25, external review ~10. The `still_open` column shows in-flight appeals not yet resolved, typically ~5-10% per level, triaged weekly by the appeals team.

---

### Query 11: Overturn rate by appeal level

**Category:** Aggregation
**Difficulty:** Basic
**Business role:** Manager

**Business context:**
An overturn means the original denial was wrong. L1 overturn rate higher than external review -> first-pass reviewers need training; external overturn rate higher -> internal denial policy is too strict.

**Approach:**
Still single-table `appeals`. The difference from the previous query is the denominator: overturn rate is only meaningful on resolved appeals, so the WHERE clause must filter out `outcome = 'pending'` in-flight cases, otherwise unresolved cases inflate the denominator and the rate is understated. Group by level. `overturn_rate = SUM(overturned) / COUNT(*)`. `overturned` is a convenience boolean; SUMing it directly gives the overturned count.

**SQL:**
```sql
-- appeal_level (text) and level_number (integer) coexist; the integer column sorts naturally and the text column reads intuitively.
SELECT
    level_number,
    appeal_level,
    COUNT(*)                                          AS resolved_appeals,
    SUM(CASE WHEN overturned THEN 1 ELSE 0 END)       AS overturned,
    ROUND(100.0 * SUM(CASE WHEN overturned THEN 1 ELSE 0 END)
                / COUNT(*), 2)                        AS overturn_rate_pct
FROM appeals
WHERE outcome <> 'pending'
GROUP BY level_number, appeal_level
ORDER BY level_number;
```

**Expected result:**
Three rows. Overturn rates on the generated data are roughly: L1 ~35%, L2 ~25%, external ~18%.

---

### Query 12: Multi-level appeals funnel

**Category:** CTE + Aggregation
**Difficulty:** Advanced
**Business role:** Analyst

**Business context:**
The analyst draws the "denial -> L1 -> L2 -> external" funnel and computes each step's share of total denials. This helps the appeals team plan staffing and estimate recovery-amount distributions.

**Approach:**
This query needs to flatten "one denial up to three appeal rows" into "one denial, one row" before the funnel math, so it uses two CTEs. The first CTE `denials` pulls all denied decisions. The second CTE `levels` LEFT JOINs appeals on those decisions, then uses `MAX(CASE WHEN level_number = N ...)` to collapse the multi-row appeals per decision into has_l1 / has_l2 / has_ext 0/1 flags; this step avoids the duplicate counting that one-to-many joins would cause. The outer query SUMs those flags into per-level conversion rates and uses `NULLIF(denominator, 0)` to guard against divide-by-zero. The LEFT JOIN is mandatory; otherwise denials that no one appealed would be dropped. The result is a one-row funnel summary.

**SQL:**
```sql
WITH denials AS (
    SELECT decision_id FROM pa_decisions WHERE decision = 'denied'
),
levels AS (
    SELECT
        d.decision_id,
        MAX(CASE WHEN a.level_number = 1       THEN 1 ELSE 0 END) AS has_l1,
        MAX(CASE WHEN a.level_number = 2       THEN 1 ELSE 0 END) AS has_l2,
        MAX(CASE WHEN a.is_external_review = 1 THEN 1 ELSE 0 END) AS has_ext,
        MAX(CASE WHEN a.overturned             THEN 1 ELSE 0 END) AS any_overturned
    FROM denials d
    LEFT JOIN appeals a ON a.decision_id = d.decision_id
    GROUP BY d.decision_id
)
SELECT
    COUNT(*)                                                          AS total_denials,
    SUM(has_l1)                                                       AS appealed_l1,
    SUM(has_l2)                                                       AS escalated_l2,
    SUM(has_ext)                                                      AS escalated_external,
    SUM(any_overturned)                                               AS ever_overturned,
    ROUND(100.0 * SUM(has_l1)         / COUNT(*), 2)                  AS l1_appeal_rate_pct,
    ROUND(100.0 * SUM(has_l2)         / NULLIF(SUM(has_l1), 0), 2)    AS l1_to_l2_escalation_pct,
    ROUND(100.0 * SUM(has_ext)        / NULLIF(SUM(has_l2), 0), 2)    AS l2_to_ext_escalation_pct,
    ROUND(100.0 * SUM(any_overturned) / COUNT(*), 2)                  AS overall_overturn_rate_pct
FROM levels;
```

**Expected result:**
A single summary row. Out of ~140 denials, ~60% file an L1 appeal (`l1_appeal_rate_pct`); ~25-30% of those escalate to L2 (`l1_to_l2_escalation_pct`; the internal escalation gate fires at 50% probability, but ~35% of L1 cases are overturned and ~5-10% remain pending, both of which end the chain), and ~25-35% of L2 reach external review (`l2_to_ext_escalation_pct`). Overall overturn rate ~25%.

---

### Query 13: Denial heatmap by specialty

**Category:** Join + Aggregation
**Difficulty:** Intermediate
**Business role:** Analyst

**Business context:**
Where are denials concentrated? The analyst slices decision mix by provider specialty to identify whether a particular specialty (e.g., Pain Management, Oncology) is driving denial volume. This drives specialty-by-specialty policy clarification and provider outreach.

**Approach:**
`specialty` lives on `providers`; decisions live on `pa_decisions`; bridge them through `pa_requests`, making it a three-table join. Grain is one row per specialty, with conditional aggregation breaking approved / partial / denied / pended into columns to form a "specialty x decision type" heatmap. Use `HAVING COUNT >= 10` to filter out specialties with samples too small to be reliable. Sort by denial rate descending to push the most denial-heavy specialties to the top.

**SQL:**
```sql
SELECT
    p.specialty,
    COUNT(d.decision_id)                                              AS total_decisions,
    SUM(CASE WHEN d.decision = 'approved'         THEN 1 ELSE 0 END)  AS approved,
    SUM(CASE WHEN d.decision = 'partial_approved' THEN 1 ELSE 0 END)  AS partial,
    SUM(CASE WHEN d.decision = 'denied'           THEN 1 ELSE 0 END)  AS denied,
    SUM(CASE WHEN d.decision = 'pended'           THEN 1 ELSE 0 END)  AS pended,
    ROUND(100.0 * SUM(CASE WHEN d.decision = 'denied' THEN 1 ELSE 0 END)
                / COUNT(d.decision_id), 2)                            AS denial_rate_pct
FROM providers    p
JOIN pa_requests  r ON r.provider_npi = p.npi
JOIN pa_decisions d ON d.request_id   = r.request_id
GROUP BY p.specialty
HAVING COUNT(d.decision_id) >= 10
ORDER BY denial_rate_pct DESC;
```

**Expected result:**
Up to 10 rows for the specialties with at least 10 decisions. Denial rates typically fall in the 20-40% range.

---

### Query 14: Top 10 procedure codes by request volume

**Category:** Join + Aggregation
**Difficulty:** Basic
**Business role:** Operations

**Business context:**
Operations management wants to know which procedure codes dominate PA volume; this leaderboard determines which policies need the most aggressive automation rules. Codes appearing in more than 5% of requests are high-leverage automation targets.

**Approach:**
`request_clinical_items` is the bridging table between requests and codes; to pull the code description, join `service_catalog`, but note that this table has a composite primary key, so the join condition must include both `service_code` and `code_type` columns; missing one will produce mis-matches. Use `COUNT(DISTINCT i.request_id)` instead of `COUNT(*)`, because the same code may attach multiple times to a single request and we want to count "how many requests used this code." WHERE keeps only CPT / HCPCS (procedures and drugs), excluding ICD diagnosis codes. The denominator uses a subquery `(SELECT COUNT(*) FROM pa_requests)` to fetch total requests; `LIMIT 10` keeps the leaderboard at top ten.

**SQL:**
```sql
SELECT
    sc.service_code,
    sc.code_type,
    sc.description,
    sc.category,
    COUNT(DISTINCT i.request_id)                                      AS request_count,
    ROUND(100.0 * COUNT(DISTINCT i.request_id) /
          (SELECT COUNT(*) FROM pa_requests), 2)                      AS pct_of_all_requests
FROM request_clinical_items i
JOIN service_catalog sc
     ON sc.service_code = i.service_code
    AND sc.code_type    = i.code_type
WHERE sc.code_type IN ('CPT', 'HCPCS')
GROUP BY sc.service_code, sc.code_type, sc.description, sc.category
ORDER BY request_count DESC
LIMIT 10;
```

**Expected result:**
Top 10 procedure codes by request attachment. The head is typically high-volume codes like `27447` (total knee replacement) and `J1745` (infliximab), each accounting for about 3% of all requests.

---

### Query 15: Confidence quantiles by decision

**Category:** Window (NTILE)
**Difficulty:** Intermediate
**Business role:** Analyst

**Business context:**
Reviewers attach a confidence score to each decision. The analyst checks whether the quantile distribution matches the decision type, for example, `pended` and `escalated` quantiles should be lower than `approved`. Mismatches mean the confidence rubric is drifting.

**Approach:**
To inspect confidence quantiles **within each decision type**, you need the window function `NTILE(4)`, and crucially `PARTITION BY decision`: this way quartiles are sliced inside each decision type rather than across the entire table. The CTE `ranked` tags each row with a quartile number 1 to 4. The outer query then uses `MAX(CASE WHEN quartile = k ...)` to extract the upper bound of each quantile as p25 / p50 / p75 columns (a common workaround when SQLite lacks a native PERCENTILE function). Grain is one row per decision type, sorted by p50 descending to make it easy to see which decision type carries the highest confidence.

**SQL:**
```sql
WITH ranked AS (
    SELECT
        decision,
        confidence_score,
        NTILE(4) OVER (PARTITION BY decision ORDER BY confidence_score) AS quartile
    FROM pa_decisions
    WHERE decided_at >= DATE('now', '-90 days')
)
SELECT
    decision,
    COUNT(*)                                                          AS decisions,
    ROUND(MAX(CASE WHEN quartile = 1 THEN confidence_score END), 3)   AS p25_max,
    ROUND(MAX(CASE WHEN quartile = 2 THEN confidence_score END), 3)   AS p50_max,
    ROUND(MAX(CASE WHEN quartile = 3 THEN confidence_score END), 3)   AS p75_max,
    ROUND(MAX(confidence_score), 3)                                   AS max_score
FROM ranked
GROUP BY decision
ORDER BY p50_max DESC;
```

**Expected result:**
Five rows. `approved` typically has p50 around 0.90; `escalated` / `pended` around 0.65-0.75.

---

### Query 16: Monthly PA volume trend + MoM growth

**Category:** Window (LAG)
**Difficulty:** Intermediate
**Business role:** Executive

**Business context:**
The CEO's monthly board deck opens with month-over-month PA volume. Stable double-digit MoM growth drives capacity expansion pacing; an unexpected single-month drop (more than 15%) triggers a market-share review.

**Approach:**
First, the CTE `monthly` uses `strftime('%Y-%m', submitted_at)` to bucket requests into months and count them (SQLite has no DATE_TRUNC, so month bucketing is via strftime). For the MoM, you need "last month's volume," which is exactly what the `LAG` window function delivers: `LAG(request_count) OVER (ORDER BY month)` fetches the previous row's value. MoM growth = (this month minus last month) / last month, with the denominator wrapped in `NULLIF(..., 0)` to avoid division by zero in the first month. Grain is one row per month, sorted descending.

**SQL:**
```sql
WITH monthly AS (
    SELECT
        strftime('%Y-%m', submitted_at)                AS month,
        COUNT(*)                                       AS request_count
    FROM pa_requests
    GROUP BY strftime('%Y-%m', submitted_at)
)
SELECT
    month,
    request_count,
    LAG(request_count) OVER (ORDER BY month)           AS prev_month,
    ROUND(100.0 *
          (request_count - LAG(request_count) OVER (ORDER BY month)) /
          NULLIF(LAG(request_count) OVER (ORDER BY month), 0), 2)     AS mom_growth_pct
FROM monthly
ORDER BY month DESC;
```

**Expected result:**
~12 monthly rows. About 50-70 requests per month; at this moderate volume, MoM growth swings within plus or minus 20%.

---

### Query 17: 6-month decision-mix drift

**Category:** CTE + Window
**Difficulty:** Advanced
**Business role:** Executive

**Business context:**
The CMO watches whether the approved/denied/pended mix drifts over time. A sustained quarter-over-quarter rise in the denial share suggests policy tightening or shifting provider behavior; a falling pended share means reviewers are more decisive.

**Approach:**
This query is a three-step process chained via three CTEs: `decided` tags decisions by month, `counts` aggregates by "month plus decision type," and `month_totals` then computes per-month totals. With those totals you can compute each decision type's share of its month. For MoM change in that share, use `LAG`, and **must** `PARTITION BY decision` so each decision type only compares to its own prior month, not its neighbor. Grain is "month x decision type"; data volume is 6 months times up to 5 decision types. This kind of layered transformation reads much cleaner as CTEs than as nested subqueries.

**SQL:**
```sql
WITH decided AS (
    SELECT
        strftime('%Y-%m', d.decided_at) AS month,
        d.decision
    FROM pa_decisions d
    WHERE d.decided_at >= DATE('now', '-6 months')
),
counts AS (
    SELECT month, decision, COUNT(*) AS n
    FROM decided GROUP BY month, decision
),
month_totals AS (
    SELECT month, SUM(n) AS total FROM counts GROUP BY month
)
SELECT
    c.month,
    c.decision,
    c.n,
    mt.total,
    ROUND(100.0 * c.n / mt.total, 2)                                  AS pct_of_month,
    ROUND(100.0 * c.n / mt.total
          - LAG(ROUND(100.0 * c.n / mt.total, 2))
                OVER (PARTITION BY c.decision ORDER BY c.month), 2)   AS mom_share_change_pct
FROM counts c
JOIN month_totals mt ON mt.month = c.month
ORDER BY c.month DESC, c.decision;
```

**Expected result:**
A long-ish table (6 months x up to 5 decision types). `pct_of_month` should hug long-run averages (approved ~60%, denied ~25%); `mom_share_change_pct` shows the period-over-period drift in percentage points.

---

### Query 18: Open request aging + SLA risk

**Category:** Date + Join
**Difficulty:** Intermediate
**Business role:** Operations

**Business context:**
The 9:00 AM ops standup uses this report to triage stalled requests. Anything over 50% of SLA is marked AT_RISK; anything over 100% is BREACH. The list is sorted worst-first, and the Operations Director assigns owners on the spot.

**Approach:**
This query targets open requests that are not yet decided (`status IN ('pending','in_review')`), so they have no `pa_decisions` row and no materialized tat to use; you must compute wait time on the fly: `(JULIANDAY('now') - JULIANDAY(submitted_at)) * 24` to get hours. Join `sla_config` to pull the urgency's SLA window, then use a `CASE` to bucket each request into ON_TRACK / AT_RISK (past half SLA) / BREACH (past SLA). Joining `providers` is just to surface the provider name on the triage list. Sort by hours waiting descending so the oldest is on top.

**SQL:**
```sql
SELECT
    r.request_id,
    r.member_id,
    p.provider_name,
    r.urgency,
    sla.sla_hours,
    r.submitted_at,
    ROUND((JULIANDAY('now') - JULIANDAY(r.submitted_at)) * 24.0, 1)   AS hours_pending,
    CASE
        WHEN (JULIANDAY('now') - JULIANDAY(r.submitted_at)) * 24.0
                > sla.sla_hours              THEN 'BREACH'
        WHEN (JULIANDAY('now') - JULIANDAY(r.submitted_at)) * 24.0
                > sla.sla_hours * 0.5        THEN 'AT_RISK'
        ELSE 'ON_TRACK'
    END                                                               AS sla_status
FROM pa_requests r
JOIN providers   p   ON p.npi      = r.provider_npi
JOIN sla_config  sla ON sla.urgency = r.urgency
WHERE r.status IN ('pending', 'in_review')
ORDER BY hours_pending DESC;
```

**Expected result:**
~70 currently open requests (the generator reserves a live queue: ~50 routine / ~15 urgent / ~5 emergent). Of those, about 35-40 are on-track, ~25-30 are at-risk (past half SLA), and ~5-10 are in breach.

---

### Query 19: Members with multiple submissions (chronic-condition cohort)

**Category:** Subquery
**Difficulty:** Basic
**Business role:** Analyst

**Business context:**
Members submitting PAs multiple times within a year are often chronic-condition patients, well-suited for case management enrollment. The clinical operations analyst hands this list to the case management team for proactive outreach.

**Approach:**
"3 or more submissions in a year" is naturally expressed as a subquery: aggregate by `member_id` in the subquery with `HAVING COUNT(*) >= 3` to surface high-frequency members, then join that result set back to `members` and `plans` to add name and tier. This "aggregate first, decorate later" two-step pattern is cleaner than grouping and joining all at once in the main query. Grain is one row per member, sorted by request count descending; `LIMIT 50` returns the most active batch.

**SQL:**
```sql
SELECT
    m.member_id,
    m.first_name || ' ' || m.last_name        AS member_name,
    pl.metal_tier,
    cnt.request_count
FROM (
    SELECT member_id, COUNT(*) AS request_count
    FROM pa_requests
    WHERE submitted_at >= DATE('now', '-365 days')
    GROUP BY member_id
    HAVING COUNT(*) >= 3
) cnt
JOIN members m  ON m.member_id = cnt.member_id
JOIN plans   pl ON pl.plan_id  = m.plan_id
ORDER BY cnt.request_count DESC, m.member_id
LIMIT 50;
```

**Expected result:**
About 50 members with 3 or more submissions in the last year, the high-utilization / chronic cohort that surfaces from the power-law distribution. The most active members may show 8-15 submissions.

---

### Query 20: Reviewer workload balance

**Category:** CTE + Window (RANK)
**Difficulty:** Advanced
**Business role:** Manager

**Business context:**
The manager ranks reviewers within each role by decision count to identify overload (top 5 vs bottom 5). Sustained imbalance leads to burnout; auto-rule "reviewers" can also be ranked to evaluate which rule version covers the most cases.

**Approach:**
First, the CTE `per_reviewer` computes each active reviewer's decision count and average confidence. There is an easy-to-miss pitfall here: the date filter must be inside the `LEFT JOIN ... ON` clause, not the WHERE, otherwise the LEFT JOIN gets degraded into an INNER JOIN by the WHERE, and zero-productivity reviewers in the window vanish, which is exactly what we want to see (zero workload is also information). The outer query uses two window functions: `RANK() OVER (PARTITION BY role ...)` for in-role ranking, and `PERCENT_RANK()` for the relative position. Grain is one row per active reviewer.

**SQL:**
```sql
WITH per_reviewer AS (
    SELECT
        rv.reviewer_id,
        rv.reviewer_name,
        rv.role,
        COUNT(d.decision_id)                            AS decisions,
        ROUND(AVG(d.confidence_score), 3)               AS avg_conf
    FROM reviewers rv
    LEFT JOIN pa_decisions d
        ON d.reviewer_id = rv.reviewer_id
       AND d.decided_at  >= DATE('now', '-90 days')
    WHERE rv.active = 1
    GROUP BY rv.reviewer_id, rv.reviewer_name, rv.role
)
SELECT
    role,
    reviewer_id,
    reviewer_name,
    decisions,
    avg_conf,
    RANK()      OVER (PARTITION BY role ORDER BY decisions DESC) AS rank_in_role,
    PERCENT_RANK() OVER (PARTITION BY role ORDER BY decisions)   AS pct_rank_in_role
FROM per_reviewer
ORDER BY role, decisions DESC;
```

**Expected result:**
~28 rows (one per active reviewer). Inside the `clinical_reviewer` role, the top reviewer may handle 40+ decisions while the tail handles fewer than 10, classic material for a workload rebalance.

---

### Query 21: Policy citation rate by category

**Category:** Join + JSON
**Difficulty:** Intermediate
**Business role:** Analyst

**Business context:**
When a decision row's `applied_policy_id` points to a policy, that policy is considered "cited." Tracking citation rate by clinical category exposes gaps: if `behavioral_health` decisions never match any policy, either the policy library lacks coverage or the matching logic is broken.

**Approach:**
To answer "which categories of policies are never used," you must `LEFT JOIN`: start from `payer_policies` and left-join `pa_decisions`, so categories never cited by any decision still appear in the result with a citation count of 0, which is exactly the gap we are looking for. Group on the `payer_policies.category` column directly rather than fragilely parsing `policy_id` strings. `json_array_length(cpt_codes_json)` opportunistically counts how many procedure-code slots each category's policies cover. Grain is one row per clinical category, sorted by citation count descending.

**SQL:**
```sql
-- Use payer_policies.category directly (no fragile parsing of policy_id).
SELECT
    pp.category,
    COUNT(DISTINCT pp.policy_id)                          AS policies_in_catalog,
    SUM(json_array_length(pp.cpt_codes_json))             AS covered_procedure_slots,
    COUNT(d.decision_id)                                  AS decisions_applied
FROM payer_policies pp
LEFT JOIN pa_decisions d ON d.applied_policy_id = pp.policy_id
GROUP BY pp.category
ORDER BY decisions_applied DESC;
```

**Expected result:**
One row per category. `orthopedic` and `cardiac` usually dominate `decisions_applied` because the catalog's CPT mix leans toward those two.

---

### Query 22: Members with coverage ending soon

**Category:** Date + Join
**Difficulty:** Intermediate
**Business role:** Operations

**Business context:**
A member whose coverage ends in the next 60 days and who has open PAs is at high risk: once coverage lapses the request gets denied for non-compliance. Member services proactively reaches out for renewal or extension. This list goes to the retention team every Friday.

**Approach:**
The base table is `members`, join `plans` for the tier, then `LEFT JOIN pa_requests` to attach pending requests. Note that the "only count pending / in_review" condition must live inside the LEFT JOIN's ON clause so members with no open requests still appear in the list (open_requests count of 0) rather than being filtered out. WHERE uses `plan_end_date BETWEEN DATE('now') AND DATE('now','+60 days')` to capture members ending within 60 days. Grain is one row per member, sorted by end date then open-request count so the retention team can prioritize the most urgent cases.

**SQL:**
```sql
SELECT
    m.member_id,
    m.first_name || ' ' || m.last_name                                AS member_name,
    pl.metal_tier,
    m.plan_end_date,
    CAST(JULIANDAY(m.plan_end_date) - JULIANDAY('now') AS INTEGER)    AS days_until_end,
    COUNT(r.request_id)                                               AS open_requests
FROM members m
JOIN plans   pl ON pl.plan_id   = m.plan_id
LEFT JOIN pa_requests r
       ON r.member_id = m.member_id
      AND r.status IN ('pending', 'in_review')
WHERE m.plan_end_date BETWEEN DATE('now') AND DATE('now', '+60 days')
GROUP BY m.member_id, m.first_name, m.last_name, pl.metal_tier, m.plan_end_date
ORDER BY m.plan_end_date, open_requests DESC;
```

**Expected result:**
A handful of members ending within 60 days. The retention team prioritizes members with open requests.

---

### Query 23: Auto-rule vs human decision outcomes

**Category:** Join + Aggregation
**Difficulty:** Intermediate
**Business role:** Executive

**Business context:**
The COO reports on automation effectiveness quarterly. The expected picture: the auto-rule engine takes a large share of "no-brainer approvals," while humans handle the hard cases (denied / pended). If the automation share drops below 30%, it triggers an investment review.

**Approach:**
The key trick is to use `CASE WHEN rv.role = 'auto_rule' THEN 'automated' ELSE 'human' END` to bucket the four reviewer roles into two groups: "automated" and "human." Use it in both SELECT and GROUP BY (SQLite allows grouping by an expression). Join `pa_decisions` to `reviewers` to pull the role. Conditional aggregation spreads each group's approved / denied / pended counts across columns to validate the "automated handles the easy, humans gnaw the hard" hypothesis. The result is two rows.

**SQL:**
```sql
SELECT
    CASE WHEN rv.role = 'auto_rule' THEN 'automated' ELSE 'human' END AS reviewer_group,
    COUNT(d.decision_id)                                              AS decisions,
    SUM(CASE WHEN d.decision IN ('approved', 'partial_approved')
             THEN 1 ELSE 0 END)                                       AS approved,
    SUM(CASE WHEN d.decision = 'denied' THEN 1 ELSE 0 END)            AS denied,
    SUM(CASE WHEN d.decision IN ('pended', 'escalated')
             THEN 1 ELSE 0 END)                                       AS pended_or_escalated,
    ROUND(100.0 * SUM(CASE WHEN d.decision IN ('approved', 'partial_approved')
                           THEN 1 ELSE 0 END) / COUNT(d.decision_id), 2)
                                                                      AS approval_rate_pct,
    ROUND(AVG(d.confidence_score), 3)                                 AS avg_confidence
FROM pa_decisions d
JOIN reviewers    rv ON rv.reviewer_id = d.reviewer_id
GROUP BY CASE WHEN rv.role = 'auto_rule' THEN 'automated' ELSE 'human' END
ORDER BY decisions DESC;
```

**Expected result:**
Two rows. `automated` handles 30-40% of decisions and skews approval; the `human` group works on a tougher case mix.

---

### Query 24: Clinical note type distribution

**Category:** Aggregation + Subquery
**Difficulty:** Basic
**Business role:** Operations

**Business context:**
Operations checks documentation habits to identify providers missing critical supporting documents at PA submission. If `physician_letter` shows up on less than 90% of requests, providers are skipping the most important document type.

**Approach:**
The body is a single GROUP BY on `clinical_notes` by `note_type`. There are two distinct counts to keep separate here: `COUNT(*)` gives the total note count (one request may have multiple notes of the same type), while `COUNT(DISTINCT request_id)` gives "how many requests carried this note type," which is what occurrence rate should use. The denominator is total requests, fetched via the subquery `(SELECT COUNT(*) FROM pa_requests)`. Grain is one row per note type, sorted by note count descending.

**SQL:**
```sql
SELECT
    note_type,
    COUNT(*)                                                          AS note_count,
    COUNT(DISTINCT request_id)                                        AS requests_with_type,
    ROUND(100.0 * COUNT(DISTINCT request_id) /
          (SELECT COUNT(*) FROM pa_requests), 2)                      AS pct_of_requests
FROM clinical_notes
GROUP BY note_type
ORDER BY note_count DESC;
```

**Expected result:**
Five rows (one per note type). `physician_letter` shows up on the most requests; `referral` is typically the least common.

---

### Query 25: Low-confidence extracted facts (QA review)

**Category:** Join + Filter
**Difficulty:** Basic
**Business role:** Analyst

**Business context:**
The QA analyst spot-checks fact extractions with confidence below 0.80 to calibrate the extraction rule book and identify documentation quality issues. Done every Wednesday.

**Approach:**
This is a filtering query, not an aggregation. Join `extracted_clinical_facts` to `pa_requests` so the spot-check list surfaces each fact's parent request urgency and status, helping QA prioritize. Two filter conditions: `confidence < 0.80` locks onto low-confidence facts, and `extracted_at >= DATE('now','-30 days')` limits to the last month. Sort ascending by confidence so the least reliable ones are first; `LIMIT 50` controls the sample size.

**SQL:**
```sql
SELECT
    ecf.fact_id,
    ecf.request_id,
    ecf.fact_category,
    ecf.fact_key,
    ecf.fact_value,
    ROUND(ecf.confidence, 3)                                          AS confidence,
    r.urgency,
    r.status
FROM extracted_clinical_facts ecf
JOIN pa_requests              r ON r.request_id = ecf.request_id
WHERE ecf.confidence < 0.80
  AND ecf.extracted_at >= DATE('now', '-30 days')
ORDER BY ecf.confidence ASC, ecf.extracted_at DESC
LIMIT 50;
```

**Expected result:**
Up to 50 low-confidence facts. Most fall in the `prior_treatment` or `contraindication` categories because free-text documentation is most ambiguous in those two.

---

### Query 26: Top 10 providers by authorized paid amount

**Category:** Join + Aggregation
**Difficulty:** Intermediate
**Business role:** Finance

**Business context:**
Finance focuses on actual *paid* amounts (not just request volume) by provider. The top 10 typically capture ~40% of payments and are managed as strategic accounts. A double-digit MoM drop in a top-10 provider's payments is a churn signal.

**Approach:**
This one follows real dollars, so the chain is the longest: `providers` -> `pa_requests` -> `pa_decisions` -> `claims`, four tables, are all needed to attribute payment dollars to a provider. `WHERE claim_status = 'paid'` counts only actual paid claims. Group by provider; `SUM(paid_amount_usd)` is the core metric, and you can opportunistically compute paid-to-billed (`paid / billed`) to see the discount level. `COUNT(DISTINCT claim_id)` guards against duplicate counts from joins. Sort by total paid descending and `LIMIT 10` for the strategic accounts.

**SQL:**
```sql
SELECT
    p.npi,
    p.provider_name,
    p.specialty,
    COUNT(DISTINCT c.claim_id)                                        AS claims,
    ROUND(SUM(c.paid_amount_usd), 2)                                  AS total_paid_usd,
    ROUND(SUM(c.billed_amount_usd), 2)                                AS total_billed_usd,
    ROUND(SUM(c.paid_amount_usd) /
          NULLIF(SUM(c.billed_amount_usd), 0) * 100.0, 2)             AS paid_pct_of_billed
FROM providers     p
JOIN pa_requests   r ON r.provider_npi = p.npi
JOIN pa_decisions  d ON d.request_id   = r.request_id
JOIN claims        c ON c.decision_id  = d.decision_id
WHERE c.claim_status = 'paid'
GROUP BY p.npi, p.provider_name, p.specialty
ORDER BY total_paid_usd DESC
LIMIT 10;
```

**Expected result:**
The 10 providers with the largest payment totals. The head is usually hospitals or surgical centers because per-claim amounts are larger.

---

### Query 27: Member cost-share % by metal tier

**Category:** Join + Aggregation
**Difficulty:** Intermediate
**Business role:** Finance

**Business context:**
Bronze members carry the largest member share of allowed amount; Platinum members the smallest. Finance verifies that the actuarial design held up after claims landed. If Gold member share looks just like Silver, that signals a benefits-config bug or anomalous utilization pattern.

**Approach:**
Start from `claims`, join `members`, then `plans` to pull the metal tier. `WHERE claim_status = 'paid'` keeps only settled claims. Group by tier; the core metric is `member_share_pct = SUM(member_responsibility_usd) / SUM(allowed_amount_usd)`. Note that you must sum first then divide (aggregate-level ratio), not average per-claim ratios, otherwise small claims will skew the result. Grain is one row per tier; sort by share descending so Bronze sits on top and Platinum at the bottom.

**SQL:**
```sql
SELECT
    pl.metal_tier,
    COUNT(c.claim_id)                                                 AS claims,
    ROUND(SUM(c.allowed_amount_usd), 2)                               AS total_allowed,
    ROUND(SUM(c.paid_amount_usd), 2)                                  AS plan_paid,
    ROUND(SUM(c.member_responsibility_usd), 2)                        AS member_share,
    ROUND(100.0 * SUM(c.member_responsibility_usd) /
                  NULLIF(SUM(c.allowed_amount_usd), 0), 2)            AS member_share_pct_of_allowed
FROM claims c
JOIN members m  ON m.member_id = c.member_id
JOIN plans   pl ON pl.plan_id  = m.plan_id
WHERE c.claim_status = 'paid'
GROUP BY pl.metal_tier
ORDER BY member_share_pct_of_allowed DESC;
```

**Expected result:**
Four rows. Bronze members `member_share_pct` is highest (~30%); Platinum is lowest (~13%); Silver ~24%; Gold ~17%.

---

### Query 28: Appeal recovery amount (overturned denials)

**Category:** CTE + Join
**Difficulty:** Advanced
**Business role:** Finance

**Business context:**
When a denial is overturned, the member / provider ultimately received the treatment that was originally blocked. Finance estimates the "recovery amount" by summing the expected billed amounts of the CPT codes on those decisions. This number quantifies the operational cost of first-pass errors and is the headline metric for the appeals function.

**Approach:**
Two CTEs. The first, `overturned`, uses `DISTINCT decision_id` to pull all overturned denials (DISTINCT is needed because a single decision may be recorded as overturned across multiple levels and deduping prevents double counting). The second, `overturned_items`, joins those decisions back to `request_clinical_items`, keeping only CPT / HCPCS procedure line items. The outer query joins `service_catalog` on the composite key (service_code plus code_type) to pull each code's `avg_billed_amount_usd`, and SUMs to get the expected recovery amount. The result is a single summary row: overturned denial count, line item count, total recovery, average per line item.

**SQL:**
```sql
WITH overturned AS (
    SELECT DISTINCT a.decision_id
    FROM appeals a
    WHERE a.overturned = 1
),
overturned_items AS (
    SELECT
        o.decision_id,
        i.service_code,
        i.code_type
    FROM overturned o
    JOIN pa_decisions d ON d.decision_id = o.decision_id
    JOIN request_clinical_items i ON i.request_id = d.request_id
    WHERE i.code_type IN ('CPT', 'HCPCS')
)
SELECT
    COUNT(DISTINCT oi.decision_id)                                    AS overturned_denials,
    COUNT(*)                                                          AS line_items,
    ROUND(SUM(sc.avg_billed_amount_usd), 2)                           AS estimated_recovery_billed_usd,
    ROUND(AVG(sc.avg_billed_amount_usd), 2)                           AS avg_line_item_value_usd
FROM overturned_items oi
JOIN service_catalog sc
     ON sc.service_code = oi.service_code
    AND sc.code_type    = oi.code_type;
```

**Expected result:**
A single summary row. ~20-30 overturned denials, yielding a recovery amount in the hundreds of thousands of dollars (depending on CPT mix).

---

### Query 29: Stalled requests still undecided past SLA

**Category:** Date + Subquery
**Difficulty:** Advanced
**Business role:** Operations

**Business context:**
This is the worst-case operational scenario: open requests (`pending` or `in_review`) whose hours-pending has already exceeded the SLA for their urgency. The generator injects a ~10% "stalled" tail into the live queue, so this report usually returns 5-10 rows; each one is a compliance exposure that gets escalated to the medical director and opens a CAPA ticket.

(Note: for *decided* requests, breach status is already materialized in `pa_decisions.sla_breached`. This query handles the orthogonal scenario of undecided requests, so it computes hours-pending on the fly.)

**Approach:**
This query is sibling to Query 18 but keeps only the worst bucket: open requests whose wait time has already exceeded their own SLA. Because the request is not yet decided and has no materialized tat, wait time is computed on the fly as `(JULIANDAY('now') - JULIANDAY(submitted_at)) * 24`, and compared against `sla_config.sla_hours` in WHERE for a hard filter. Add a computed `hours_over_sla` column (how many hours over) for sorting. A correlated subquery `(SELECT COUNT(*) FROM clinical_notes ...)` opportunistically pulls each request's note count to help triage judge whether documentation is complete. Sort by hours over SLA descending so the worst offenders are on top.

**SQL:**
```sql
SELECT
    r.request_id,
    r.member_id,
    p.provider_name,
    p.specialty,
    r.urgency,
    sla.sla_hours,
    r.submitted_at,
    ROUND((JULIANDAY('now') - JULIANDAY(r.submitted_at)) * 24.0, 1)   AS hours_pending,
    ROUND((JULIANDAY('now') - JULIANDAY(r.submitted_at)) * 24.0
          - sla.sla_hours, 1)                                         AS hours_over_sla,
    (SELECT COUNT(*) FROM clinical_notes cn
       WHERE cn.request_id = r.request_id)                            AS note_count
FROM pa_requests r
JOIN providers   p   ON p.npi      = r.provider_npi
JOIN sla_config  sla ON sla.urgency = r.urgency
WHERE r.status IN ('pending', 'in_review')
  AND (JULIANDAY('now') - JULIANDAY(r.submitted_at)) * 24.0 > sla.sla_hours
ORDER BY hours_over_sla DESC;
```

**Expected result:**
Typically 5-10 stalled requests, sorted by hours over SLA descending. The mix leans `routine` (largest base), and a few `emergent` cases may surface at the top of the list; every `emergent` is highest priority because its SLA is only 2 hours.

---

### Query 30: Denial reason Pareto (cumulative %)

**Category:** Window + JSON
**Difficulty:** Advanced
**Business role:** Analyst

**Business context:**
The Pareto principle says ~80% of denials are explained by ~20% of denial codes. The analyst confirms this and identifies the "vital few" codes as targets for provider re-education. The cumulative percentage tells the team where the 80% line lands.

**Approach:**
The core of a Pareto chart is the "cumulative percentage," which requires an ordered running-sum window function. The first CTE `denial_counts` unpacks `denial_codes_json` with `json_each` and counts by code. In the second CTE `ranked`: `pct_of_total` uses the unpartitioned window `SUM(occurrences) OVER ()` as the denominator; the cumulative share uses `SUM(occurrences) OVER (ORDER BY occurrences DESC ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)`, an ordered running sum that traces the Pareto curve; `ROW_NUMBER()` produces the rank. The outer query uses `CASE WHEN cumulative_pct <= 80 THEN 'vital_few' ELSE 'trivial_many'` to draw the line between vital few and trivial many. Grain is one row per denial code, sorted by rank ascending.

**SQL:**
```sql
WITH denial_counts AS (
    SELECT
        je.value                                       AS denial_code,
        COUNT(*)                                       AS occurrences
    FROM pa_decisions d, json_each(d.denial_codes_json) je
    WHERE d.denial_codes_json IS NOT NULL
    GROUP BY je.value
),
ranked AS (
    SELECT
        denial_code,
        occurrences,
        ROUND(100.0 * occurrences /
              SUM(occurrences) OVER (), 2)             AS pct_of_total,
        ROUND(100.0 *
              SUM(occurrences) OVER (ORDER BY occurrences DESC
                                     ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
              / SUM(occurrences) OVER (), 2)           AS cumulative_pct,
        ROW_NUMBER() OVER (ORDER BY occurrences DESC)  AS rank
    FROM denial_counts
)
SELECT
    rank,
    denial_code,
    occurrences,
    pct_of_total,
    cumulative_pct,
    CASE WHEN cumulative_pct <= 80.0 THEN 'vital_few'
         ELSE 'trivial_many' END                       AS pareto_class
FROM ranked
ORDER BY rank;
```

**Expected result:**
9 rows (one per CARC/RARC code). Denial code weights follow the designed Pareto shape: `N-130` (~30%) and `CO-50` (~21%) together account for ~50% of all denial-code mentions; the top 4 codes cumulatively hit ~80%; the remaining 5 are the long tail.

---

## 4. Query Coverage Summary

### By category

| Category | Query numbers | Count | % |
|---|---|---|---|
| Aggregation (including Date variants) | 1, 10, 11, 24 | 4 | 13% |
| Join + Aggregation | 2, 4, 5, 6, 7, 8, 9, 13, 14, 22, 23, 26, 27 | 13 | 43% |
| Window function | 15, 16, 17, 20, 30 | 5 | 17% |
| CTE | 12, 17, 20, 28 | 4 | 13% |
| Subquery | 19, 29 | 2 | 7% |
| JSON unnest | 3, 21, 30 | 3 | 10% |
| Date analysis | 1, 5, 6, 16, 17, 18, 22, 29 | 8 | 27% |

*(Some queries fall into more than one category, so the total exceeds 30.)*

### By difficulty

| Difficulty | Query numbers | Count | % |
|---|---|---|---|
| Basic        | 1, 2, 4, 8, 10, 11, 14, 19, 24, 25 | 10 | 33% |
| Intermediate | 3, 5, 6, 7, 9, 13, 15, 16, 18, 21, 22, 23, 26, 27 | 14 | 47% |
| Advanced     | 12, 17, 20, 28, 29, 30 | 6 | 20% |

### By business role

| Role | Query numbers | Count | % |
|---|---|---|---|
| Executive  | 2, 16, 17, 23 | 4 | 13% |
| Manager    | 4, 5, 7, 11, 20 | 5 | 17% |
| Analyst    | 3, 12, 13, 15, 19, 21, 25, 30 | 8 | 27% |
| Operations | 1, 6, 10, 14, 18, 22, 24, 29 | 8 | 27% |
| Finance    | 8, 9, 26, 27, 28 | 5 | 17% |

### By business question

Each query traces back to one of the business questions listed in section 5 of `01-..._business_context.md`. The table below gives the mapping.

| Business question | Corresponding queries |
|---|---|
| Question 1: turnaround time and capacity (SLA, open queue) | 1, 5, 6, 18, 22, 29 |
| Question 2: are approvals and denials fair and well-calibrated | 2, 7, 8, 13 |
| Question 3: concentration of denial reasons | 3, 30 |
| Question 4: authorization-to-claim leakage | 9, 26, 27 |
| Question 5: appeals workflow and overturn rates | 10, 11, 12, 28 |
| Question 6: automation effectiveness | 4, 20, 23 |
| Operations / quality support (no single mapped question) | 14, 15, 16, 17, 19, 21, 24, 25 |

---

**End of SQL queries document**
