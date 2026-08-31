# Fiber Splicing Quality and Cost Control Dataset SQL Queries Reference

This document accompanies the `telecom_equipment_fiber_splicing_quality_high` dataset. For business background, company structure, the eight business questions, and the glossary, see `01-telecom_equipment_fiber_splicing_quality_high_business_context.md`. For table structure, field definitions, and the expected magnitude of the embedded business traps, see `02-telecom_equipment_fiber_splicing_quality_high_er_document.md`.

`REFERENCE_DATE` is anchored at `2026-06-15`. Every query in this document passes that date in as a literal rather than using `DATE('now')`, so results stay consistent across runs.

---

## 1. How to use this document

This document is the SQL task list Marcus (VP Operations) handed you in week two of your kickoff. There are 20 queries total, and your job this week is to run every one of them and turn the results into a 12-page memo for the CFO. These 20 queries aren't a SQL syntax exercise — they exist to prove or disprove eight cost-take-out hypotheses. Each one maps to a specific dollar number, and each one has to end with an answer to "what's the next action."

Every query has five beats.

First, **Business Context**: who wants this data, why now, and what decision the answer feeds into. This is the opening of that section in your memo.

Second, **Tags**: query category (aggregation / join / window function / CTE, etc.), difficulty, and business role — so a reader can size it up quickly.

Third, **Approach**: think through, before you write any SQL, which tables you need to join, how to join them, why it's a LEFT join and not an INNER join, what grain the GROUP BY needs to land on, and whether you need a CTE or a window function. This section is your mentor walking you through the thinking, not a line-by-line translation of the SQL.

Fourth, **SQL**: the actual query. Every query here has already been verified to run on SQLite.

Fifth, **Expected Result and Next Step**: the shape of data you should expect to see, the key magnitudes, and what you (as the analyst) do next once you have this result.

Every query maps back to Q1 through Q8 in document 01. There's a mapping table at the end of this document.

---

## 2. Query Index

| # | Title | Maps to | Business Role | Difficulty |
|------|------|--------|----------|------|
| 1 | Splicing Process Cost and Quality Grade Overview | Q1 | CFO + VP Operations | Basic |
| 2 | Reject Cost Broken Down by Root-Cause Driver | Q1 | VP Operations | Advanced |
| 3 | Monthly FPY and Reject Rate Trend | Q1 | Production Manager | Intermediate |
| 4 | Electrode Usage Count Buckets vs. Reject Rate | Q2 | Manufacturing Analyst | Intermediate |
| 5 | ROI Estimate for a Proactive Electrode Replacement Policy | Q2 | VP Operations | Advanced |
| 6 | Reject Rate and Volume Contribution by Shift | Q3 | Production Manager | Basic |
| 7 | Night-Shift Floating Supervisor ROI | Q3 | VP Operations | Intermediate |
| 8 | Skill Level x Fiber Spec Reject Cross-Tab | Q4 | Production Manager | Intermediate |
| 9 | ROI Estimate for Multi-Core Rescheduling | Q4 | VP Operations | Advanced |
| 10 | Spec Compliance Gap by Customer Segment | Q5 | CFO + VP Sales | Intermediate |
| 11 | Cost Savings from Re-Grading Against Actual Customer Spec | Q5 | CFO | Advanced |
| 12 | AI Alert Outcome vs. Downstream Reject Linkage | Q6 | QA Engineering Manager | Intermediate |
| 13 | Shift Breakdown of Ignored Alerts and Enforcement ROI | Q6 | VP Operations | Advanced |
| 14 | Equipment Calibration Overdue Days vs. Reject Rate | Q7 | Production Manager | Basic |
| 15 | Scope of Quality Impact from Bad Batch MFG-2024-038 | Q8 | QA Engineering Manager | Intermediate |
| 16 | Tracing Customer Complaints Back to Batches | Q8 | QA Engineering Manager | Advanced |
| 17 | Equipment Maintenance Priority Board | Operations | Production Manager | Intermediate |
| 18 | Daily Volume, FPY, Reject Rate, 3-Week Moving Average | Operations | VP Operations | Advanced |
| 19 | Deviation Analysis: QA Audit vs. Operator Self-Grading | Operations | QA Engineering Manager | Intermediate |
| 20 | Composite Operator Performance Ranking | Operations | Production Manager | Advanced |

---

## 3. Query 1: Splicing Process Cost and Quality Grade Overview

**Business Context**

CFO Linda Chen wants the big picture first at the monthly BoD prep meeting: total splice count over 12 months, total cost, the grade mix, the blended reject rate, and FPY. She wants to know where the baseline sits — no detail, no breakdown yet. This result becomes the first chart in your memo. This one maps to Q1.

**Tags**

Category: Aggregation query. Difficulty: Basic. Role: CFO + VP Operations.

**Approach**

You only need `splice_record` here — no joins required. attempt_count = 1 and grade != Reject is your first-pass yield. Using SUM(CASE WHEN ...) to compute all four grade buckets in one pass is a lot more efficient than running four separate COUNTs. Note the denominator is COUNT(\*), not COUNT(splice_id) — splice_id is a NOT NULL primary key so the two are equivalent, but COUNT(\*) reads more clearly.

Cost comes from `splice_attempt` — a straight SUM gets you the 12-month process total. splice_attempt is N:1 against splice_record, because a single splice can have multiple attempts, so the SUM has to happen at the attempt grain. Don't join up to splice_record first and then SUM, or you'll double-count.

**SQL**

```sql
WITH grade_stats AS (
    SELECT
        COUNT(*) AS total_splices,
        SUM(CASE WHEN final_grade = 'A' THEN 1 ELSE 0 END) AS grade_a,
        SUM(CASE WHEN final_grade = 'B' THEN 1 ELSE 0 END) AS grade_b,
        SUM(CASE WHEN final_grade = 'C' THEN 1 ELSE 0 END) AS grade_c,
        SUM(CASE WHEN final_grade = 'Reject' THEN 1 ELSE 0 END) AS reject_count,
        SUM(CASE WHEN attempt_count = 1 AND final_grade != 'Reject' THEN 1 ELSE 0 END) AS first_pass_pass
    FROM splice_record
    WHERE completed_ts BETWEEN '2025-06-16' AND '2026-06-15'
),
cost_stats AS (
    SELECT SUM(total_cost_usd) AS total_cost_usd
    FROM splice_attempt
    WHERE attempt_ts BETWEEN '2025-06-16' AND '2026-06-15'
)
SELECT
    g.total_splices,
    g.grade_a,
    ROUND(g.grade_a * 100.0 / g.total_splices, 2) AS grade_a_pct,
    g.grade_b,
    ROUND(g.grade_b * 100.0 / g.total_splices, 2) AS grade_b_pct,
    g.grade_c,
    ROUND(g.grade_c * 100.0 / g.total_splices, 2) AS grade_c_pct,
    g.reject_count,
    ROUND(g.reject_count * 100.0 / g.total_splices, 2) AS reject_rate_pct,
    ROUND(g.first_pass_pass * 100.0 / g.total_splices, 2) AS first_pass_yield_pct,
    ROUND(c.total_cost_usd, 2) AS total_cost_usd,
    ROUND(c.total_cost_usd / g.total_splices, 4) AS avg_cost_per_splice_usd
FROM grade_stats g, cost_stats c;
```

**Expected Result and Next Step**

One row. Key numbers: total splices around 50,000, grade A around 75%, grade B around 18%, grade C around 4.5%, reject around 2.5%, FPY around 88%, total_cost around $125K to $135K, avg_cost_per_splice around $2.50. If FPY comes in below 90% or reject rate above 3%, that puts the plant in the lower-middle of the industry (top-tier plants run FPY 95%+, reject under 1%), and the next 19 queries need to break that gap down driver by driver.

---

## 4. Query 2: Reject Cost Broken Down by Root-Cause Driver

**Business Context**

VP Operations Marcus wants to show "what each of your 8 hypotheses is worth in dollars" at the Phase 1 kickoff review meeting. This is the core evidence behind the budget ask you're bringing to the CFO. Each driver (electrode wear / shift / skill x multi-core mismatch / calibration overdue / bad batch / ignored alerts) needs its own dollar number, and they should sum to something close to the reject_total from Q1. This is the anchor query for the whole project, and it maps to Q1.

**Tags**

Category: CTE + UNION ALL. Difficulty: Advanced. Role: VP Operations.

**Approach**

Each driver maps to an estimate of "extra" reject attributable to some subset of splices. Take the electrode-wear driver, for example: take the reject count among splices with electrode_count > 2000, subtract what the baseline reject rate would predict for a subset that size, and the difference is "the reject count attributable to electrode wear." This "actual minus baseline" pattern is the attributable-risk idea from econometrics.

Every driver follows the same pattern: filter down to the splice subset that belongs to this driver, compute that subset's actual reject rate against the overall baseline, then multiply the difference by the subset size and the unit cost. Unit cost follows the business-context convention of $13 per reject (materials + labor + equipment depreciation + amortized customer-trust risk).

Stack the 8 driver subqueries into one table with UNION ALL. Note that the driver sets aren't mutually exclusive (a single splice could be both night-shift and past electrode life), so the driver-level dollar totals will sum to more than the total reject cost — that's expected. What you're writing in the memo is "the amount recoverable if this class of problem were eliminated," not a non-overlapping allocation of the total.

**SQL**

```sql
WITH baseline AS (
    SELECT
        COUNT(*) AS total_splices,
        SUM(CASE WHEN final_grade = 'Reject' THEN 1 ELSE 0 END) * 1.0 / COUNT(*) AS reject_rate
    FROM splice_record
    WHERE completed_ts BETWEEN '2025-06-16' AND '2026-06-15'
),
electrode_wear AS (
    SELECT
        'electrode_wear' AS driver,
        COUNT(DISTINCT sa.splice_id) AS subset_splices,
        SUM(CASE WHEN sr.final_grade = 'Reject' THEN 1 ELSE 0 END) AS subset_rejects
    FROM splice_attempt sa
    JOIN splice_record sr ON sa.splice_id = sr.splice_id
    WHERE sa.attempt_number = 1
      AND sa.equipment_electrode_count > 2000
      AND sa.attempt_ts BETWEEN '2025-06-16' AND '2026-06-15'
),
night_shift AS (
    SELECT
        'night_shift' AS driver,
        COUNT(*) AS subset_splices,
        SUM(CASE WHEN final_grade = 'Reject' THEN 1 ELSE 0 END) AS subset_rejects
    FROM splice_record
    WHERE shift_id = 'SH-N'
      AND completed_ts BETWEEN '2025-06-16' AND '2026-06-15'
),
skill_mismatch AS (
    SELECT
        'skill_multicore_mismatch' AS driver,
        COUNT(*) AS subset_splices,
        SUM(CASE WHEN sr.final_grade = 'Reject' THEN 1 ELSE 0 END) AS subset_rejects
    FROM splice_record sr
    JOIN operator o ON sr.operator_id = o.operator_id
    JOIN fiber_spool fsp ON sr.left_spool_id = fsp.spool_id
    JOIN fiber_spec fs ON fsp.spec_id = fs.spec_id
    WHERE fs.mode_type = 'multi_core'
      AND o.skill_level IN ('junior', 'intermediate')
      AND sr.completed_ts BETWEEN '2025-06-16' AND '2026-06-15'
),
calibration_overdue AS (
    SELECT
        'calibration_overdue' AS driver,
        COUNT(*) AS subset_splices,
        SUM(CASE WHEN sr.final_grade = 'Reject' THEN 1 ELSE 0 END) AS subset_rejects
    FROM splice_record sr
    JOIN equipment e ON sr.equipment_id = e.equipment_id
    WHERE julianday(sr.completed_ts) - julianday(e.last_calibration_date) > 90
      AND sr.completed_ts BETWEEN '2025-06-16' AND '2026-06-15'
),
bad_batch AS (
    SELECT
        'bad_batch_MFG_2024_038' AS driver,
        COUNT(*) AS subset_splices,
        SUM(CASE WHEN sr.final_grade = 'Reject' THEN 1 ELSE 0 END) AS subset_rejects
    FROM splice_record sr
    JOIN fiber_spool fsp ON sr.left_spool_id = fsp.spool_id
    WHERE fsp.batch_id = 'MFG-2024-038'
      AND sr.completed_ts BETWEEN '2025-06-16' AND '2026-06-15'
),
alert_ignored AS (
    SELECT
        'ai_alert_ignored' AS driver,
        COUNT(DISTINCT sr.splice_id) AS subset_splices,
        SUM(CASE WHEN sr.final_grade = 'Reject' THEN 1 ELSE 0 END) AS subset_rejects
    FROM splice_record sr
    JOIN splice_attempt sa ON sr.splice_id = sa.splice_id
    JOIN quality_alert qa ON sa.attempt_id = qa.attempt_id
    WHERE qa.outcome = 'ignored'
      AND sr.completed_ts BETWEEN '2025-06-16' AND '2026-06-15'
),
combined AS (
    SELECT * FROM electrode_wear
    UNION ALL SELECT * FROM night_shift
    UNION ALL SELECT * FROM skill_mismatch
    UNION ALL SELECT * FROM calibration_overdue
    UNION ALL SELECT * FROM bad_batch
    UNION ALL SELECT * FROM alert_ignored
)
SELECT
    c.driver,
    c.subset_splices,
    c.subset_rejects,
    ROUND(c.subset_rejects * 100.0 / c.subset_splices, 2) AS subset_reject_rate_pct,
    ROUND(b.reject_rate * 100, 2) AS baseline_reject_rate_pct,
    -- Attributable reject count: actual subset rejects minus what baseline would predict
    ROUND(c.subset_rejects - c.subset_splices * b.reject_rate, 0) AS attributable_rejects,
    -- Convert to an annualized dollar figure at $13 / reject
    ROUND((c.subset_rejects - c.subset_splices * b.reject_rate) * 13.0, 0) AS attributable_cost_usd
FROM combined c, baseline b
ORDER BY attributable_cost_usd DESC;
```

**Expected Result and Next Step**

6 rows, sorted by attributable_cost descending. Expect: electrode_wear ~$180K, skill_multicore_mismatch ~$145K, ai_alert_ignored ~$130K, calibration_overdue ~$105K, night_shift ~$70K, bad_batch_MFG_2024_038 ~$50K. That's roughly $680K to $730K combined — close to the CFO's $700K target, which is the chart Marcus needs for BoD prep. Next step: move into Q2 through Q8 to break each driver down further and attach a concrete action recommendation to each.

---

## 5. Query 3: Monthly FPY and Reject Rate Trend

**Business Context**

Production Manager Sarah Klein reports on production-line health to Marcus every month. She needs to see whether monthly FPY and reject rate are trending worse. If FPY drops more than 1 percentage point for two consecutive months, that triggers an immediate floor investigation. This query is the single most important chart on Sarah's dashboard. Maps to Q1.

**Tags**

Category: Date grouping + window function. Difficulty: Intermediate. Role: Production Manager.

**Approach**

Slice by month using `strftime('%Y-%m', completed_ts)`. FPY is computed as the share of records where attempt_count = 1 AND final_grade != 'Reject'. SQLite doesn't directly support PERCENT_RANK for a month-over-month need like this, but `LAG(...) OVER(ORDER BY month)` to grab last month's FPY and compute the change is the cleanest approach. Note that the ORDER BY inside LAG has to be the month field, not a row_number — otherwise the cross-month ordering can get scrambled.

**SQL**

```sql
WITH monthly AS (
    SELECT
        strftime('%Y-%m', completed_ts) AS month,
        COUNT(*) AS splices,
        SUM(CASE WHEN attempt_count = 1 AND final_grade != 'Reject' THEN 1 ELSE 0 END) AS fpy_pass,
        SUM(CASE WHEN final_grade = 'Reject' THEN 1 ELSE 0 END) AS rejects
    FROM splice_record
    WHERE completed_ts BETWEEN '2025-06-16' AND '2026-06-15'
    GROUP BY strftime('%Y-%m', completed_ts)
)
SELECT
    month,
    splices,
    ROUND(fpy_pass * 100.0 / splices, 2) AS fpy_pct,
    ROUND(rejects * 100.0 / splices, 2) AS reject_rate_pct,
    ROUND(
        fpy_pass * 100.0 / splices
        - LAG(fpy_pass * 100.0 / splices) OVER(ORDER BY month),
        2
    ) AS fpy_mom_change_pp
FROM monthly
ORDER BY month;
```

**Expected Result and Next Step**

12 rows (12 months). FPY should hover around 88%, reject rate around 2.5%. Check whether fpy_mom_change_pp shows two consecutive months of more than a 1pp drop. If it does, Sarah needs to debrief with whichever shift lead was on duty that month. This query is the routine EKG of the production line — no news is good news here.

---

## 6. Query 4: Electrode Usage Count Buckets vs. Reject Rate

**Business Context**

Marcus wants you to prove — or disprove — the Q2 hypothesis: "the higher the splice_count, the more worn the electrode, and the higher the reject rate." If the data shows a sharp nonlinear curve, the case for proactive electrode replacement holds up. If the curve is flat, the hypothesis is disproved and this item drops off the ROI list. This is the first key query for Q2.

**Tags**

Category: CASE bucketing + aggregation. Difficulty: Intermediate. Role: Manufacturing Analyst (you).

**Approach**

Group directly on splice_attempt by electrode_count bucket. The bucket boundaries — 1000 / 1800 / 2200 / 2600 — are chosen because the manufacturer's recommended life is 2000 splices, and you want to see whether the inflection point actually sits near 2000. Only look at attempt_number = 1, excluding retries (retries are a different driver's story). Attempt-level reject is judged with attempt_grade = 'Reject', which is a field native to splice_attempt, so no join to splice_record is needed here.

**SQL**

```sql
SELECT
    CASE
        WHEN equipment_electrode_count < 1000 THEN '1. 0 to 1000'
        WHEN equipment_electrode_count < 1800 THEN '2. 1000 to 1800'
        WHEN equipment_electrode_count < 2200 THEN '3. 1800 to 2200'
        WHEN equipment_electrode_count < 2600 THEN '4. 2200 to 2600'
        ELSE '5. 2600+'
    END AS electrode_count_bucket,
    COUNT(*) AS attempts,
    SUM(CASE WHEN attempt_grade = 'Reject' THEN 1 ELSE 0 END) AS rejects,
    ROUND(
        SUM(CASE WHEN attempt_grade = 'Reject' THEN 1 ELSE 0 END) * 100.0 / COUNT(*),
        2
    ) AS reject_rate_pct,
    ROUND(AVG(actual_loss_db), 4) AS avg_loss_db,
    ROUND(AVG(actual_loss_db) FILTER (WHERE 1=0), 4) AS placeholder_unused
FROM splice_attempt
WHERE attempt_number = 1
  AND attempt_ts BETWEEN '2025-06-16' AND '2026-06-15'
GROUP BY electrode_count_bucket
ORDER BY electrode_count_bucket;
```

**Expected Result and Next Step**

5 rows. reject_rate_pct should show a sharp, nonlinear climb: 1.2 → 1.8 → 4.5 → 9.0 → 17.0. avg_loss_db should also climb monotonically. This curve is the smoking gun for the proactive-electrode-replacement case. The inflection point lands between 1800 and 2200, consistent with the manufacturer's 2000-splice spec. Next step: Q2-2 uses this curve to estimate ROI.

---

## 7. Query 5: ROI Estimate for a Proactive Electrode Replacement Policy

**Business Context**

The curve from Q4 confirms electrode wear is the biggest driver. Now Marcus wants the ROI: if the plant switches to "replace proactively every 1800 splices," what's the incremental annual electrode cost, how much reject cost gets recovered, what's the net savings, and how long is the payback period? You hand this number to the CFO to decide whether to approve the new SOP. Maps to Q2.

**Tags**

Category: Multiple CTEs + arithmetic. Difficulty: Advanced. Role: VP Operations.

**Approach**

Under the new policy, replacement count = total_attempts / 1800. The old policy's actual replacement count comes straight from the electrode_replacement table. The difference times $180 is the incremental cost. Recovered rejects = (attempt count where electrode_count > 1800) x (that bucket's reject rate minus the reject rate for the < 1800 bucket). Recovered dollars = recovered rejects x $13.

Build "new policy cost," "recovered cost," and "net savings" out as CTEs and output everything in the final SELECT.

**SQL**

```sql
WITH attempt_stats AS (
    SELECT
        COUNT(*) AS total_attempts,
        SUM(CASE WHEN equipment_electrode_count > 1800 THEN 1 ELSE 0 END) AS attempts_above_1800,
        SUM(CASE WHEN equipment_electrode_count > 1800 AND attempt_grade = 'Reject' THEN 1 ELSE 0 END) AS rejects_above_1800,
        SUM(CASE WHEN equipment_electrode_count <= 1800 AND attempt_grade = 'Reject' THEN 1 ELSE 0 END) AS rejects_below_1800,
        SUM(CASE WHEN equipment_electrode_count <= 1800 THEN 1 ELSE 0 END) AS attempts_below_1800
    FROM splice_attempt
    WHERE attempt_number = 1
      AND attempt_ts BETWEEN '2025-06-16' AND '2026-06-15'
),
old_replacements AS (
    SELECT COUNT(*) AS old_replacement_count
    FROM electrode_replacement
    WHERE replacement_ts BETWEEN '2025-06-16' AND '2026-06-15'
),
calc AS (
    SELECT
        a.total_attempts,
        -- Annual replacement count under the new policy
        CAST(a.total_attempts * 1.0 / 1800 AS INTEGER) AS new_replacement_count,
        o.old_replacement_count,
        -- Reject rate in the high-wear bucket
        a.rejects_above_1800 * 1.0 / a.attempts_above_1800 AS rate_high,
        -- Reject rate in the low-wear bucket
        a.rejects_below_1800 * 1.0 / a.attempts_below_1800 AS rate_low,
        a.attempts_above_1800,
        a.rejects_above_1800
    FROM attempt_stats a, old_replacements o
)
SELECT
    total_attempts,
    old_replacement_count,
    new_replacement_count,
    new_replacement_count - old_replacement_count AS extra_replacements,
    ROUND((new_replacement_count - old_replacement_count) * 180.0, 2) AS extra_electrode_cost_usd,
    ROUND(rate_high * 100, 2) AS rate_high_pct,
    ROUND(rate_low * 100, 2) AS rate_low_pct,
    -- If the high-wear bucket dropped to the low-wear rate, how many rejects would be avoided
    ROUND(attempts_above_1800 * (rate_high - rate_low), 0) AS avoided_rejects,
    ROUND(attempts_above_1800 * (rate_high - rate_low) * 13.0, 0) AS avoided_reject_cost_usd,
    -- Net savings = recovered reject cost minus incremental electrode cost
    ROUND(
        attempts_above_1800 * (rate_high - rate_low) * 13.0
        - (new_replacement_count - old_replacement_count) * 180.0,
        0
    ) AS net_annual_savings_usd
FROM calc;
```

**Expected Result and Next Step**

One row. extra_replacements around 60 to 80 pairs (incremental electrode cost around $12K), avoided_rejects around 14,000 (roughly attempts_above_1800 x a 5-point gap), avoided_reject_cost around $180K, net_annual_savings around $165K. Payback period under a month. Next step: Marcus takes this result along with the Q4 curve to the BoD to request switching the SOP to proactive replacement every 1800 splices.

---

## 8. Query 6: Reject Rate and Volume Contribution by Shift

**Business Context**

The floor has been saying "the night shift has more rejects" for a while, but nobody has ever quantified it. Sarah needs the data to confirm or kill that story, because if it's real, adding a senior supervisor to the night shift is going into the Q3 wage budget. Maps to Q3.

**Tags**

Category: Simple aggregation. Difficulty: Basic. Role: Production Manager.

**Approach**

Group by shift_id, count splices, count rejects, compute reject_rate, and also compute each shift's volume share (using the SUM total as the denominator). No joins needed here at all. About as close to a no-brainer as this document gets.

**SQL**

```sql
SELECT
    sh.shift_name,
    sr.shift_id,
    COUNT(*) AS splices,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 2) AS volume_share_pct,
    SUM(CASE WHEN sr.final_grade = 'Reject' THEN 1 ELSE 0 END) AS rejects,
    ROUND(
        SUM(CASE WHEN sr.final_grade = 'Reject' THEN 1 ELSE 0 END) * 100.0 / COUNT(*),
        2
    ) AS reject_rate_pct,
    ROUND(
        SUM(CASE WHEN sr.final_grade = 'Reject' THEN 1 ELSE 0 END) * 100.0
        / SUM(SUM(CASE WHEN sr.final_grade = 'Reject' THEN 1 ELSE 0 END)) OVER(),
        2
    ) AS reject_share_pct
FROM splice_record sr
JOIN shift sh ON sr.shift_id = sh.shift_id
WHERE sr.completed_ts BETWEEN '2025-06-16' AND '2026-06-15'
GROUP BY sr.shift_id, sh.shift_name
ORDER BY sr.shift_id;
```

**Expected Result and Next Step**

3 rows. Expect: Day reject 1.8%, Swing 2.5%, Night 4.2%. Night accounts for 25% of volume but 42% of reject share. The rumor checks out. Next step: Q7 works out the ROI on adding a night-shift supervisor.

---

## 9. Query 7: Night-Shift Floating Supervisor ROI

**Business Context**

Marcus wants to know whether adding an $80K/year senior supervisor to the night shift will pay for itself. The supervisor's job would be to walk the floor and handle anomalies in real time, pulling the night shift's reject rate closer to swing-shift levels. Assuming night reject rate can drop from 4.2% to 2.5% (swing-shift level), how much reject cost is recovered? What's the ROI? Maps to Q3.

**Tags**

Category: Multiple CTEs + ROI calculation. Difficulty: Intermediate. Role: VP Operations.

**Approach**

Night-shift splice count x (4.2% minus 2.5%) gives you the recoverable reject count. Multiply by the $13 unit cost to get the recoverable dollar figure. The supervisor costs $80K/year (including benefits and a 1.4x loading factor). The ratio of those two numbers is your ROI.

Don't hardcode 4.2% and 2.5% in the actual SQL — compute them directly from splice_record so the conclusion updates automatically if the underlying data changes. Use CTEs to compute the swing reject rate and the night reject rate separately, then do the arithmetic.

**SQL**

```sql
WITH night AS (
    SELECT
        COUNT(*) AS night_splices,
        SUM(CASE WHEN final_grade = 'Reject' THEN 1 ELSE 0 END) AS night_rejects
    FROM splice_record
    WHERE shift_id = 'SH-N'
      AND completed_ts BETWEEN '2025-06-16' AND '2026-06-15'
),
swing AS (
    SELECT
        SUM(CASE WHEN final_grade = 'Reject' THEN 1 ELSE 0 END) * 1.0 / COUNT(*) AS swing_rate
    FROM splice_record
    WHERE shift_id = 'SH-S'
      AND completed_ts BETWEEN '2025-06-16' AND '2026-06-15'
)
SELECT
    n.night_splices,
    n.night_rejects,
    ROUND(n.night_rejects * 100.0 / n.night_splices, 2) AS night_reject_rate_pct,
    ROUND(s.swing_rate * 100, 2) AS swing_reject_rate_pct,
    -- Recoverable reject count if night shift is pulled to swing-shift level
    ROUND(n.night_rejects - n.night_splices * s.swing_rate, 0) AS avoidable_night_rejects,
    -- Recovered cost
    ROUND((n.night_rejects - n.night_splices * s.swing_rate) * 13.0, 0) AS avoidable_cost_usd,
    -- Annual cost of adding a supervisor
    80000 AS supervisor_annual_cost_usd,
    -- Net savings
    ROUND((n.night_rejects - n.night_splices * s.swing_rate) * 13.0 - 80000, 0) AS net_savings_usd,
    -- ROI ratio
    ROUND((n.night_rejects - n.night_splices * s.swing_rate) * 13.0 / 80000.0, 2) AS roi_ratio
FROM night n, swing s;
```

**Expected Result and Next Step**

One row. avoidable_night_rejects around 200 to 250, avoidable_cost around $90K to $110K, net_savings around $25K, roi_ratio around 1.3 to 1.4. A modest positive return, not a blowout. Marcus's read: the supervisor isn't just about reject cost — it should also help night-shift morale and retention, so the overall call is to approve. Next step: draft the supervisor job description and submit it to HR.

---

## 10. Query 8: Skill Level x Fiber Spec Reject Cross-Tab

**Business Context**

The current scheduling policy lets any multi_core_certified operator take multi-core jobs, regardless of skill level. Sarah suspects junior operators who've picked up the multi-core cert are actually performing poorly at it. This query is a 4x3 cross-tab to find the riskiest cell. Maps to Q4.

**Tags**

Category: Cross-tab + multi-table JOIN. Difficulty: Intermediate. Role: Production Manager.

**Approach**

You need splice_record + operator + fiber_spool + fiber_spec, four tables. The key thing is not to INNER JOIN in a way that duplicates splice rows. A splice has both a left_spool and a right_spool, and in most cases they're the same spec, so taking the left_spool's spec is representative enough for the whole splice. Follow the path left_spool_id → fiber_spool → fiber_spec, then group by skill_level x mode_type and use SUM(CASE) to compute the reject rate for each cell.

Add a splice count column too, so small cell sizes don't mislead anyone reading the cross-tab.

**SQL**

```sql
SELECT
    o.skill_level,
    fs.mode_type,
    COUNT(*) AS splices,
    SUM(CASE WHEN sr.final_grade = 'Reject' THEN 1 ELSE 0 END) AS rejects,
    ROUND(
        SUM(CASE WHEN sr.final_grade = 'Reject' THEN 1 ELSE 0 END) * 100.0 / COUNT(*),
        2
    ) AS reject_rate_pct
FROM splice_record sr
JOIN operator o ON sr.operator_id = o.operator_id
JOIN fiber_spool fsp ON sr.left_spool_id = fsp.spool_id
JOIN fiber_spec fs ON fsp.spec_id = fs.spec_id
WHERE sr.completed_ts BETWEEN '2025-06-16' AND '2026-06-15'
GROUP BY o.skill_level, fs.mode_type
ORDER BY
    CASE o.skill_level
        WHEN 'junior' THEN 1
        WHEN 'intermediate' THEN 2
        WHEN 'senior' THEN 3
        WHEN 'expert' THEN 4
    END,
    CASE fs.mode_type
        WHEN 'single' THEN 1
        WHEN 'multi' THEN 2
        WHEN 'multi_core' THEN 3
    END;
```

**Expected Result and Next Step**

12 rows (4 skill levels x 3 modes). Key cells: junior x multi_core ~25%, intermediate x multi_core ~12%, senior x multi_core ~3%, expert x multi_core ~2%. Single-core stays at 1 to 2% across every skill level. The data holds up — the mismatch is concentrated in multi-core work. Next step: Q9 estimates the ROI of rescheduling.

---

## 11. Query 9: ROI Estimate for Multi-Core Rescheduling

**Business Context**

Marcus has decided to push a new policy: multi-core jobs go only to senior and expert operators, and junior and intermediate operators no longer take multi-core work. You need to estimate: how many rejects get recovered annually, but also whether this creates a capacity bottleneck for senior and expert operators, and whether additional training budget is needed. Maps to Q4.

**Tags**

Category: Multiple CTEs + counterfactual calculation. Difficulty: Advanced. Role: VP Operations.

**Approach**

The counterfactual: take the multi-core splices currently done by junior and intermediate operators and reassign them to the senior/expert reject rate, then compute the recovered reject count. But you also need to check whether senior and expert operators currently have the capacity to absorb this extra work. Compare the senior + expert operators' current multi-core workload against the total multi-core workload. If senior + expert currently only cover 70% of multi-core volume, absorbing the remaining 30% means a 30% increase in their workload — which could mean overtime or new hires.

Write two CTEs: one for the current state of junior + intermediate on multi-core (rate_low_skill), one for the current state of senior + expert on multi-core (rate_high_skill). The counterfactual shifts splice volume from the former to the latter and re-computes rejects using rate_high_skill.

**SQL**

```sql
WITH low_skill_mc AS (
    SELECT
        COUNT(*) AS low_mc_splices,
        SUM(CASE WHEN sr.final_grade = 'Reject' THEN 1 ELSE 0 END) AS low_mc_rejects
    FROM splice_record sr
    JOIN operator o ON sr.operator_id = o.operator_id
    JOIN fiber_spool fsp ON sr.left_spool_id = fsp.spool_id
    JOIN fiber_spec fs ON fsp.spec_id = fs.spec_id
    WHERE fs.mode_type = 'multi_core'
      AND o.skill_level IN ('junior', 'intermediate')
      AND sr.completed_ts BETWEEN '2025-06-16' AND '2026-06-15'
),
high_skill_mc AS (
    SELECT
        COUNT(*) AS high_mc_splices,
        SUM(CASE WHEN sr.final_grade = 'Reject' THEN 1 ELSE 0 END) * 1.0 / COUNT(*) AS high_mc_rate
    FROM splice_record sr
    JOIN operator o ON sr.operator_id = o.operator_id
    JOIN fiber_spool fsp ON sr.left_spool_id = fsp.spool_id
    JOIN fiber_spec fs ON fsp.spec_id = fs.spec_id
    WHERE fs.mode_type = 'multi_core'
      AND o.skill_level IN ('senior', 'expert')
      AND sr.completed_ts BETWEEN '2025-06-16' AND '2026-06-15'
)
SELECT
    l.low_mc_splices,
    l.low_mc_rejects,
    ROUND(l.low_mc_rejects * 100.0 / l.low_mc_splices, 2) AS low_skill_mc_reject_pct,
    h.high_mc_splices,
    ROUND(h.high_mc_rate * 100, 2) AS high_skill_mc_reject_pct,
    -- Counterfactual: expected reject count after shifting low-skill multi-core work to high-skill operators
    ROUND(l.low_mc_splices * h.high_mc_rate, 0) AS counterfactual_rejects,
    -- Avoided reject count
    ROUND(l.low_mc_rejects - l.low_mc_splices * h.high_mc_rate, 0) AS avoided_rejects,
    -- Recovered cost
    ROUND((l.low_mc_rejects - l.low_mc_splices * h.high_mc_rate) * 13.0, 0) AS avoided_cost_usd,
    -- Check whether senior + expert need to absorb extra load, incremental capacity demand (%)
    ROUND(l.low_mc_splices * 100.0 / h.high_mc_splices, 1) AS extra_capacity_load_pct
FROM low_skill_mc l, high_skill_mc h;
```

**Expected Result and Next Step**

One row. avoided_rejects around 11,000, avoided_cost around $145K. extra_capacity_load around 40% (senior + expert would need to take on 40% more multi-core workload than they currently carry). Decision: train 4 additional senior operators over the year at a training cost of $40K, netting roughly $105K in savings. Next step: HR kicks off the senior training program, and scheduling adds a hard constraint blocking junior and intermediate operators from multi-core jobs.

---

## 12. Query 10: Spec Compliance Gap by Customer Segment

**Business Context**

VP Sales Jorge is discussing an idea with the CFO: relax the internal reject threshold on FTTH orders to the customer's actual spec (0.30 dB) instead of the blanket 0.05 dB. The CFO wants to see the data first: what's the current internal reject rate by segment, and what's the compliance rate if judged against the customer's actual spec (i.e., final_loss_db <= order.loss_threshold_db), and how big is the gap between the two. Maps to Q5.

**Tags**

Category: Multi-table JOIN + dual-standard comparison. Difficulty: Intermediate. Role: CFO + VP Sales.

**Approach**

You need splice_record + splice_job + customer_order + customer, four tables, following the path splice_record → splice_job → customer_order → customer. Then group by customer.segment and compute two measures.

Measure A (internal reject): the share where final_grade = 'Reject'.
Measure B (customer spec compliance): the share where final_loss_db <= order.loss_threshold_db.

The gap between them (B minus (1 minus A)) is the volume of product that got wrongly written off by the internal SOP even though the customer would actually accept it.

**SQL**

```sql
SELECT
    c.segment,
    COUNT(*) AS splices,
    SUM(CASE WHEN sr.final_grade = 'Reject' THEN 1 ELSE 0 END) AS internal_rejects,
    ROUND(
        SUM(CASE WHEN sr.final_grade = 'Reject' THEN 1 ELSE 0 END) * 100.0 / COUNT(*),
        2
    ) AS internal_reject_rate_pct,
    -- Share passing under the customer's actual spec
    SUM(CASE WHEN sr.final_loss_db <= co.loss_threshold_db THEN 1 ELSE 0 END) AS customer_spec_passes,
    ROUND(
        SUM(CASE WHEN sr.final_loss_db <= co.loss_threshold_db THEN 1 ELSE 0 END) * 100.0 / COUNT(*),
        2
    ) AS customer_spec_pass_rate_pct,
    -- Count of splices rejected internally but that the customer would actually accept (the over-quality count)
    SUM(
        CASE
            WHEN sr.final_grade = 'Reject' AND sr.final_loss_db <= co.loss_threshold_db THEN 1
            ELSE 0
        END
    ) AS over_quality_count,
    ROUND(
        SUM(
            CASE
                WHEN sr.final_grade = 'Reject' AND sr.final_loss_db <= co.loss_threshold_db THEN 1
                ELSE 0
            END
        ) * 100.0 / COUNT(*),
        2
    ) AS over_quality_rate_pct
FROM splice_record sr
JOIN splice_job j ON sr.job_id = j.job_id
JOIN customer_order co ON j.order_id = co.order_id
JOIN customer c ON co.customer_id = c.customer_id
WHERE sr.completed_ts BETWEEN '2025-06-16' AND '2026-06-15'
GROUP BY c.segment
ORDER BY over_quality_rate_pct DESC;
```

**Expected Result and Next Step**

3 rows (one per segment). hyperscale: internal_reject 3.0%, customer_spec_pass 96.5% (near-zero gap — customer spec is already strict); enterprise: internal_reject 2.5%, customer_spec_pass 99%, over_quality 0.5%; **ftth: internal_reject 2.5%, customer_spec_pass 99.8%, over_quality 2.2%**. FTTH has the largest over_quality volume — it's the biggest opportunity to relax the spec. Next step: Q11 puts a concrete cost-savings number on relaxing the spec.

---

## 13. Query 11: Cost Savings from Re-Grading Against Actual Customer Spec

**Business Context**

Turn the Q10 finding into a dollar number for the CFO. If FTTH orders were reject-graded against 0.30 dB instead of 0.05 dB, how many fewer units get reworked per year, how many fewer retries happen, and how much attempt cost is saved? This number goes straight into the memo and would trigger an SOP revision. Maps to Q5.

**Tags**

Category: CTE + multi-source cost rollup. Difficulty: Advanced. Role: CFO.

**Approach**

The cost impact of over-quality splices isn't just reject cost — it also includes the cost of the retry attempts. If a splice hit final_grade = Reject after attempt 2, but the customer's actual spec would have accepted it, then attempt 2 was pure waste (under the new spec, attempt 1 alone should have been accepted). The extra cost for this class of splice equals the sum of total_cost_usd for attempts 2 and 3.

First use a CTE to flag which splices are "over-quality" (internally rejected but customer-spec pass), then sum total_cost across all attempt_number > 1 attempts for those splices. That's the money relaxing the SOP would save.

Note that the cost of attempt_number = 1 is unavoidable regardless of SOP (the first splice attempt has to happen either way), so it can't be counted as savings.

**SQL**

```sql
WITH over_quality_splices AS (
    SELECT sr.splice_id
    FROM splice_record sr
    JOIN splice_job j ON sr.job_id = j.job_id
    JOIN customer_order co ON j.order_id = co.order_id
    JOIN customer c ON co.customer_id = c.customer_id
    WHERE c.segment = 'ftth_carrier'
      AND sr.final_grade = 'Reject'
      AND sr.final_loss_db <= co.loss_threshold_db
      AND sr.completed_ts BETWEEN '2025-06-16' AND '2026-06-15'
),
waste_cost AS (
    SELECT
        COUNT(DISTINCT sa.splice_id) AS over_quality_splice_count,
        COUNT(*) AS wasted_attempts,
        ROUND(SUM(sa.total_cost_usd), 2) AS wasted_attempt_cost_usd
    FROM splice_attempt sa
    JOIN over_quality_splices oqs ON sa.splice_id = oqs.splice_id
    WHERE sa.attempt_number > 1
),
reject_cost AS (
    -- This batch of splices also carries downstream cost from being internally flagged as reject
    -- (rework, material waste, inbound audit). Unit cost $13, consistent with Q2.
    SELECT
        COUNT(*) AS over_quality_splices,
        COUNT(*) * 13.0 AS downstream_reject_cost_usd
    FROM over_quality_splices
)
SELECT
    rc.over_quality_splices,
    wc.wasted_attempts,
    wc.wasted_attempt_cost_usd,
    rc.downstream_reject_cost_usd,
    ROUND(wc.wasted_attempt_cost_usd + rc.downstream_reject_cost_usd, 2) AS total_annual_savings_usd
FROM waste_cost wc, reject_cost rc;
```

**Expected Result and Next Step**

One row. over_quality_splices around 800 to 1100, wasted_attempts around 1500 (most with 1 to 2 extra attempts), wasted_attempt_cost around $4K, downstream_reject_cost around $13K, total around $17K. The number isn't huge, but the cost to implement is nearly zero (just an SOP document change), so the ROI is very high. Next step: QA Manager Tom drafts the SOP revision adding `dynamic_threshold = order.loss_threshold_db` logic, targeting rollout within 8 weeks.

---

## 14. Query 12: AI Alert Outcome vs. Downstream Reject Linkage

**Business Context**

Tom (QA Engineering Manager) has long suspected there's a real cost to operators ignoring AI alerts. He wants data proving that alerts with outcome = ignored really do lead to a higher downstream reject rate. If the gap is significant, he'll push to add a "hard stop" to the alert system (forcing the operator to choose reclean or escalate when an alert fires, removing the option to ignore it). Maps to Q6.

**Tags**

Category: Multi-table JOIN + aggregation. Difficulty: Intermediate. Role: QA Engineering Manager.

**Approach**

quality_alert hangs off splice_attempt, not directly off splice_record. To trace from alert.outcome to splice_record.final_grade, you have to walk alert → attempt → splice_record. INNER JOIN is correct here, since every alert links to exactly one attempt and, through it, exactly one splice. Group by outcome and compute the reject rate.

Note that a single splice can have multiple alerts (all 3 attempts could each trigger one). Counting the same splice multiple times across outcomes is fine here, since outcome is an attempt-level attribute — just be aware that DISTINCT splice count and alert count aren't the same thing.

**SQL**

```sql
SELECT
    qa.outcome,
    COUNT(*) AS alert_count,
    COUNT(DISTINCT sr.splice_id) AS distinct_splices,
    SUM(CASE WHEN sr.final_grade = 'Reject' THEN 1 ELSE 0 END) AS downstream_rejects,
    ROUND(
        SUM(CASE WHEN sr.final_grade = 'Reject' THEN 1 ELSE 0 END) * 100.0 / COUNT(*),
        2
    ) AS downstream_reject_rate_pct,
    ROUND(AVG(sr.final_loss_db), 4) AS avg_final_loss_db
FROM quality_alert qa
JOIN splice_attempt sa ON qa.attempt_id = sa.attempt_id
JOIN splice_record sr ON sa.splice_id = sr.splice_id
WHERE qa.alert_ts BETWEEN '2025-06-16' AND '2026-06-15'
GROUP BY qa.outcome
ORDER BY downstream_reject_rate_pct DESC;
```

**Expected Result and Next Step**

3 rows (resolved, ignored, escalated). Expect: ignored 35%, escalated 8%, resolved 3%. The downstream reject rate for ignored alerts is roughly 11x that of resolved ones. The data clearly backs up Tom's suspicion. Next step: Q13 works out the ROI on a hard stop, and Tom takes it to Product / IT as a build request.

---

## 15. Query 13: Shift Breakdown of Ignored Alerts and Enforcement ROI

**Business Context**

Q12 proved that ignored alerts carry a high downstream reject rate, but not whether that's evenly distributed. Marcus wants to know which shift ignores the most alerts. If it's concentrated on the night shift, the Q7 supervisor hire and an alert hard stop might need to be rolled out in two stages. If it's evenly spread, going straight to the hard stop is enough on its own. This query also produces the annualized ROI of enforcement. Maps to Q6.

**Tags**

Category: Two-dimensional GROUP BY + counterfactual calculation. Difficulty: Advanced. Role: VP Operations.

**Approach**

Two-dimensional grouping: shift_id x outcome. Compute each shift's ignored_share (the share of that shift's total alerts that were ignored). Then run the counterfactual: if all ignored alerts were forced to become resolved, those splices' expected reject rate should drop to the resolved-outcome level, so recovered rejects = ignored count x (ignored_rate minus resolved_rate).

Note that after GROUP BY shift x outcome, `SUM(SUM(...)) OVER (PARTITION BY shift)` is used to get each outcome's share within its own shift. SQLite supports this "aggregate then window" pattern.

**SQL**

```sql
WITH alert_by_shift_outcome AS (
    SELECT
        sr.shift_id,
        qa.outcome,
        COUNT(*) AS alerts,
        SUM(CASE WHEN sr.final_grade = 'Reject' THEN 1 ELSE 0 END) AS downstream_rejects
    FROM quality_alert qa
    JOIN splice_attempt sa ON qa.attempt_id = sa.attempt_id
    JOIN splice_record sr ON sa.splice_id = sr.splice_id
    WHERE qa.alert_ts BETWEEN '2025-06-16' AND '2026-06-15'
    GROUP BY sr.shift_id, qa.outcome
),
shift_distribution AS (
    SELECT
        shift_id,
        outcome,
        alerts,
        downstream_rejects,
        ROUND(alerts * 100.0 / SUM(alerts) OVER(PARTITION BY shift_id), 2) AS outcome_share_within_shift_pct,
        ROUND(downstream_rejects * 100.0 / alerts, 2) AS outcome_reject_rate_pct
    FROM alert_by_shift_outcome
),
ignored_savings AS (
    -- If ignored alerts' reject rate were pulled down to the resolved level, how many rejects would each shift recover
    SELECT
        a.shift_id,
        a.alerts AS ignored_alerts,
        a.downstream_rejects AS ignored_rejects,
        r.outcome_reject_rate_pct AS resolved_rate_pct,
        ROUND(
            a.downstream_rejects - a.alerts * r.outcome_reject_rate_pct / 100.0,
            0
        ) AS avoidable_rejects,
        ROUND(
            (a.downstream_rejects - a.alerts * r.outcome_reject_rate_pct / 100.0) * 13.0,
            0
        ) AS avoidable_cost_usd
    FROM alert_by_shift_outcome a
    JOIN shift_distribution r
        ON a.shift_id = r.shift_id AND r.outcome = 'resolved'
    WHERE a.outcome = 'ignored'
)
SELECT * FROM shift_distribution
ORDER BY shift_id, outcome;
```

Follow it up with a summary query:

```sql
WITH alert_by_shift_outcome AS (
    SELECT
        sr.shift_id,
        qa.outcome,
        COUNT(*) AS alerts,
        SUM(CASE WHEN sr.final_grade = 'Reject' THEN 1 ELSE 0 END) AS downstream_rejects
    FROM quality_alert qa
    JOIN splice_attempt sa ON qa.attempt_id = sa.attempt_id
    JOIN splice_record sr ON sa.splice_id = sr.splice_id
    WHERE qa.alert_ts BETWEEN '2025-06-16' AND '2026-06-15'
    GROUP BY sr.shift_id, qa.outcome
),
resolved_rate AS (
    SELECT
        shift_id,
        downstream_rejects * 1.0 / alerts AS resolved_rate
    FROM alert_by_shift_outcome
    WHERE outcome = 'resolved'
)
SELECT
    a.shift_id,
    a.alerts AS ignored_alerts,
    a.downstream_rejects AS ignored_rejects_actual,
    ROUND(a.alerts * r.resolved_rate, 0) AS ignored_rejects_if_forced,
    ROUND(a.downstream_rejects - a.alerts * r.resolved_rate, 0) AS avoidable_rejects,
    ROUND((a.downstream_rejects - a.alerts * r.resolved_rate) * 13.0, 0) AS avoidable_cost_usd
FROM alert_by_shift_outcome a
JOIN resolved_rate r ON a.shift_id = r.shift_id
WHERE a.outcome = 'ignored'
ORDER BY avoidable_cost_usd DESC;
```

**Expected Result and Next Step**

First table: 9 rows (3 shifts x 3 outcomes). Key cell: Night x ignored share around 28%, Day x ignored share around 5%. Second table: 3 rows (enforcement savings by shift). Night avoidable around $90K, Swing around $25K, Day around $10K — roughly $125K total. Next step: Marcus takes Q12 + Q13 together to the CIO to request a 24-hour hard stop (alerts must be resolved via reclean or escalate, with the ignore button removed), targeting rollout within 4 weeks.

---

## 16. Query 14: Equipment Calibration Overdue Days vs. Reject Rate

**Business Context**

Sarah suspects equipment that's overdue for calibration produces less stable quality. The SOP calls for calibration every 90 days, but enforcement is loose. This query buckets equipment by days-since-calibration and checks how the reject rate moves. If the data backs it up, the proposal to shorten the SOP to 60 days has real leverage. Maps to Q7.

**Tags**

Category: Date functions + aggregation. Difficulty: Basic. Role: Production Manager.

**Approach**

`julianday(REFERENCE_DATE) - julianday(equipment.last_calibration_date)` gives you the day count. But this is equipment-level data, not splice-level. A given splice's calibration status is determined by whatever last_calibration_date its equipment had at that moment. As a simplification, just compare equipment's current last_calibration_date against REFERENCE_DATE (assuming no recalibration happened after the most recent one on record, consistent with how the dataset was generated).

Bucket every splice by its equipment's day count, then group and compute the reject rate.

**SQL**

```sql
SELECT
    CASE
        WHEN julianday('2026-06-15') - julianday(e.last_calibration_date) <= 60 THEN '1. <=60 days'
        WHEN julianday('2026-06-15') - julianday(e.last_calibration_date) <= 90 THEN '2. 60 to 90 days'
        WHEN julianday('2026-06-15') - julianday(e.last_calibration_date) <= 120 THEN '3. 90 to 120 days'
        ELSE '4. 120+ days'
    END AS calibration_age_bucket,
    COUNT(DISTINCT e.equipment_id) AS equipment_count,
    COUNT(*) AS splices,
    SUM(CASE WHEN sr.final_grade = 'Reject' THEN 1 ELSE 0 END) AS rejects,
    ROUND(
        SUM(CASE WHEN sr.final_grade = 'Reject' THEN 1 ELSE 0 END) * 100.0 / COUNT(*),
        2
    ) AS reject_rate_pct
FROM splice_record sr
JOIN equipment e ON sr.equipment_id = e.equipment_id
WHERE sr.completed_ts BETWEEN '2025-06-16' AND '2026-06-15'
GROUP BY calibration_age_bucket
ORDER BY calibration_age_bucket;
```

**Expected Result and Next Step**

4 rows. Reject rate should climb monotonically from 1.5% to 5.5%. The gap between over-90-days and under-90-days is clear. Next step: Marcus proposes shortening the SOP to 60 days, and needs to confirm with the maintenance team whether calibration capacity can support it (a single calibration takes 2.5 hours). Run the same ROI formula as Q5: 12 machines x 4 extra calibrations/year, at a cost of $480 x 4 x 12 = $23K, against roughly $90K in recovered cost — a 4x ROI. Approve.

---

## 17. Query 15: Scope of Quality Impact from Bad Batch MFG-2024-038

**Business Context**

QA Engineering Manager Tom received a notice last week from SumiOptics: "batch MFG-2024-038 exceeded our internal cladding-variance control limit, but was released to you as acceptable at the time." Tom needs to know how much of this batch was actually used, which customer orders it landed on, and whether it lines up with any customer complaints that have come in. This query is the first step in the recall assessment. Maps to Q8.

**Tags**

Category: Multi-table JOIN + filtering. Difficulty: Intermediate. Role: QA Engineering Manager.

**Approach**

Start from fiber_batch, find every fiber_spool under that batch, then find splice_record rows where either left_spool_id or right_spool_id matches (a splice uses both a left and right spool, and either one matching counts as "touched by this batch"). An OR condition is cleaner here than a UNION.

Then join to customer to see the distribution of affected customers, and also join customer_complaint to check whether any complaints line up.

**SQL**

```sql
SELECT
    fb.batch_id,
    fb.supplier_name,
    fb.cladding_diameter_std_dev_um,
    fb.qc_release_status,
    COUNT(DISTINCT sr.splice_id) AS impacted_splices,
    SUM(CASE WHEN sr.final_grade = 'Reject' THEN 1 ELSE 0 END) AS rejects,
    ROUND(
        SUM(CASE WHEN sr.final_grade = 'Reject' THEN 1 ELSE 0 END) * 100.0
            / NULLIF(COUNT(DISTINCT sr.splice_id), 0),
        2
    ) AS reject_rate_pct,
    COUNT(DISTINCT co.order_id) AS impacted_orders,
    COUNT(DISTINCT co.customer_id) AS impacted_customers,
    GROUP_CONCAT(DISTINCT c.customer_code) AS customer_codes
FROM fiber_batch fb
JOIN fiber_spool fsp ON fb.batch_id = fsp.batch_id
JOIN splice_record sr
    ON (sr.left_spool_id = fsp.spool_id OR sr.right_spool_id = fsp.spool_id)
JOIN splice_job j ON sr.job_id = j.job_id
JOIN customer_order co ON j.order_id = co.order_id
JOIN customer c ON co.customer_id = c.customer_id
WHERE fb.batch_id = 'MFG-2024-038'
  AND sr.completed_ts BETWEEN '2025-06-16' AND '2026-06-15'
GROUP BY fb.batch_id, fb.supplier_name, fb.cladding_diameter_std_dev_um, fb.qc_release_status;
```

**Expected Result and Next Step**

One row. impacted_splices around 280, reject_rate around 12% (vs. a 2.5% baseline), impacted_orders around 5, impacted_customers 1 to 2 (mainly FTTH-CCom). customer_codes lists the affected customer codes. Next step: Q16 cross-references this batch against customer_complaint to decide whether a customer notification process needs to start.

---

## 18. Query 16: Tracing Customer Complaints Back to Batches

**Business Context**

Tom needs to produce a "should we issue a customer notification" decision memo for CEO David Park. The key facts: how many customer_complaint records tie back to batch MFG-2024-038, what severities they carry, and how much cost_impact has already accumulated. If the count of high + critical complaints exceeds 5, or cost_impact exceeds $30K, legal guidance is to issue a customer notification. Maps to Q8.

**Tags**

Category: Multi-table JOIN + conditional aggregation. Difficulty: Advanced. Role: QA Engineering Manager.

**Approach**

Start from customer_complaint and filter on linked_batch_id = 'MFG-2024-038'. Group by severity and sum both count and cost_impact. But you also need to check unlinked complaints (linked_batch_id is NULL, but the complaint_date overlaps the batch's usage window and complaint_type = high_loss_in_field) — these are "possibly also caused by this batch but QA never traced it" risk.

Use UNION ALL to present "confirmed attribution" and "suspected attribution" as two separate columns, so the decision-maker has room to weigh both.

**SQL**

```sql
WITH confirmed AS (
    SELECT
        'confirmed_to_MFG-2024-038' AS category,
        cc.severity,
        COUNT(*) AS complaint_count,
        ROUND(SUM(cc.cost_impact_usd), 2) AS total_cost_impact_usd
    FROM customer_complaint cc
    WHERE cc.linked_batch_id = 'MFG-2024-038'
    GROUP BY cc.severity
),
suspected AS (
    SELECT
        'suspected_unlinked' AS category,
        cc.severity,
        COUNT(*) AS complaint_count,
        ROUND(SUM(cc.cost_impact_usd), 2) AS total_cost_impact_usd
    FROM customer_complaint cc
    WHERE cc.linked_batch_id IS NULL
      AND cc.complaint_type IN ('high_loss_in_field', 'early_failure')
      AND cc.complaint_date BETWEEN '2025-12-01' AND '2026-06-15'
    GROUP BY cc.severity
),
combined AS (
    SELECT * FROM confirmed
    UNION ALL
    SELECT * FROM suspected
)
SELECT
    category,
    severity,
    complaint_count,
    total_cost_impact_usd
FROM combined
ORDER BY
    category,
    CASE severity
        WHEN 'critical' THEN 1
        WHEN 'high' THEN 2
        WHEN 'medium' THEN 3
        WHEN 'low' THEN 4
    END;
```

**Expected Result and Next Step**

Roughly 4 to 6 rows. Key finding: confirmed_to_MFG-2024-038 has 6 high-severity complaints, with a combined cost_impact around $50K to $60K — over the customer-notification threshold. Next step: Tom drafts the notification, reviews it with Legal and Sales within 24 hours before sending to FTTH-CCom, and simultaneously opens a supplier corrective action with SumiOptics.

---

## 19. Query 17: Equipment Maintenance Priority Board

**Business Context**

Every Monday morning, Sarah opens the standup with an equipment status table: which machines are approaching calibration deadline, which have crossed 10,000 cumulative splices and need a full teardown inspection, and which have had elevated rejects recently. She uses this to set that week's priorities. Maps to NorthArc's day-to-day operations.

**Tags**

Category: CTE + CASE-based sorting. Difficulty: Intermediate. Role: Production Manager.

**Approach**

Augment the equipment table with 30-day recent reject stats (using a LEFT JOIN so machines currently in maintenance status don't get dropped). Use CASE to assign a priority label to each machine: calibration overdue > recent reject elevated > high cumulative splice count > normal. Sort ascending by priority number, and within the same priority, descending by recent reject rate.

**SQL**

```sql
WITH recent_perf AS (
    SELECT
        equipment_id,
        COUNT(*) AS recent_splices,
        ROUND(AVG(final_loss_db), 4) AS recent_avg_loss,
        SUM(CASE WHEN final_grade = 'Reject' THEN 1 ELSE 0 END) AS recent_rejects,
        ROUND(
            SUM(CASE WHEN final_grade = 'Reject' THEN 1 ELSE 0 END) * 100.0 / COUNT(*),
            2
        ) AS recent_reject_rate_pct
    FROM splice_record
    WHERE completed_ts BETWEEN date('2026-06-15', '-30 days') AND '2026-06-15'
    GROUP BY equipment_id
)
SELECT
    e.equipment_id,
    e.model,
    e.location,
    e.status,
    e.last_calibration_date,
    CAST(julianday('2026-06-15') - julianday(e.last_calibration_date) AS INTEGER) AS days_since_cal,
    e.total_splice_count,
    COALESCE(rp.recent_splices, 0) AS recent_splices,
    COALESCE(rp.recent_reject_rate_pct, 0) AS recent_reject_rate_pct,
    CASE
        WHEN e.status = 'maintenance' THEN 'IN_MAINTENANCE'
        WHEN julianday('2026-06-15') - julianday(e.last_calibration_date) > 90 THEN 'P1_CAL_OVERDUE'
        WHEN COALESCE(rp.recent_reject_rate_pct, 0) > 5 THEN 'P2_QUALITY_ALERT'
        WHEN e.total_splice_count > 8000 THEN 'P3_HIGH_USAGE'
        ELSE 'OK'
    END AS priority
FROM equipment e
LEFT JOIN recent_perf rp ON e.equipment_id = rp.equipment_id
ORDER BY
    CASE
        WHEN e.status = 'maintenance' THEN 1
        WHEN julianday('2026-06-15') - julianday(e.last_calibration_date) > 90 THEN 2
        WHEN COALESCE(rp.recent_reject_rate_pct, 0) > 5 THEN 3
        WHEN e.total_splice_count > 8000 THEN 4
        ELSE 5
    END,
    recent_reject_rate_pct DESC;
```

**Expected Result and Next Step**

12 rows (all equipment). You should see 3 to 4 machines land in P1_CAL_OVERDUE, 1 to 2 in P2_QUALITY_ALERT, 1 in IN_MAINTENANCE, and the rest OK. Sarah schedules calibrations for the week; P2 machines get an additional technician diagnostic pass.

---

## 20. Query 18: Daily Volume, FPY, Reject Rate, 3-Week Moving Average

**Business Context**

This is Marcus's standard chart for monthly board prep: daily volume with a 3-week moving average of the reject rate layered on top. The moving average smooths out single-day noise so the trend is visible. This chart is a fixture in the BoD deck. Maps to NorthArc's day-to-day operations.

**Tags**

Category: Date aggregation + window function. Difficulty: Advanced. Role: VP Operations.

**Approach**

Group by day to compute daily_splices, daily_fpy, and daily_reject_rate. Then use `AVG(...) OVER (ORDER BY day ROWS BETWEEN 20 PRECEDING AND CURRENT ROW)` to compute a 3-week (21-day) moving average.

SQLite supports this window syntax, but watch the distinction between ROWS and RANGE. ROWS counts by row, RANGE counts by value range — on daily data, the two only diverge if there are missing dates. Assuming no missing days, ROWS is the right choice.

**SQL**

```sql
WITH daily AS (
    SELECT
        DATE(completed_ts) AS day,
        COUNT(*) AS splices,
        SUM(CASE WHEN attempt_count = 1 AND final_grade != 'Reject' THEN 1 ELSE 0 END) AS fpy_pass,
        SUM(CASE WHEN final_grade = 'Reject' THEN 1 ELSE 0 END) AS rejects
    FROM splice_record
    WHERE completed_ts BETWEEN '2025-06-16' AND '2026-06-15'
    GROUP BY DATE(completed_ts)
)
SELECT
    day,
    splices,
    ROUND(fpy_pass * 100.0 / splices, 2) AS fpy_pct,
    ROUND(rejects * 100.0 / splices, 2) AS reject_rate_pct,
    ROUND(
        AVG(rejects * 100.0 / splices)
            OVER (ORDER BY day ROWS BETWEEN 20 PRECEDING AND CURRENT ROW),
        2
    ) AS reject_rate_3w_avg_pct,
    ROUND(
        AVG(splices)
            OVER (ORDER BY day ROWS BETWEEN 20 PRECEDING AND CURRENT ROW),
        0
    ) AS splices_3w_avg
FROM daily
ORDER BY day;
```

**Expected Result and Next Step**

Around 360 rows (one year). Check whether reject_rate_3w_avg holds steady around 2.5%. If some stretch of the year (for example, 2025-12 through 2026-02, which lines up with the bad-batch window) spikes above 4%, that's the dramatic high point of the data story. Marcus uses this chart as the anchor for BoD slide 5.

---

## 21. Query 19: Deviation Analysis: QA Audit vs. Operator Self-Grading

**Business Context**

Tom wants to know how far off operators' self-assessed quality_grade is from QA's OTDR-based re-audit. If the grade_match rate falls below 90%, trust in internal data erodes, and that undermines the whole Tableau dashboard. This also surfaces any systematic bias in the LID algorithm. Maps to NorthArc's day-to-day operations.

**Tags**

Category: Aggregation + JOIN. Difficulty: Intermediate. Role: QA Engineering Manager.

**Approach**

Look directly at the qa_audit table. For samples where grade_match = False, classify whether the operator's self_grade was too lenient (actual result was worse) or too strict (actual result was better). Use SIGN(variance_db) to tell them apart: variance > 0 means QA measured worse than the self-grade, variance < 0 means QA measured better.

Slicing by operator surfaces individual operators who are systematically too lenient or too strict — useful material for a performance conversation.

**SQL**

```sql
SELECT
    o.operator_id,
    o.name,
    o.skill_level,
    COUNT(*) AS audited,
    SUM(CASE WHEN qa.grade_match THEN 1 ELSE 0 END) AS matches,
    ROUND(
        SUM(CASE WHEN qa.grade_match THEN 1 ELSE 0 END) * 100.0 / COUNT(*),
        2
    ) AS match_rate_pct,
    SUM(CASE WHEN qa.variance_db > 0.01 THEN 1 ELSE 0 END) AS operator_overgraded,
    SUM(CASE WHEN qa.variance_db < -0.01 THEN 1 ELSE 0 END) AS operator_undergraded,
    ROUND(AVG(qa.variance_db), 5) AS avg_variance_db
FROM qa_audit qa
JOIN splice_record sr ON qa.splice_id = sr.splice_id
JOIN operator o ON sr.operator_id = o.operator_id
WHERE qa.audit_ts BETWEEN '2025-06-16' AND '2026-06-15'
GROUP BY o.operator_id, o.name, o.skill_level
HAVING COUNT(*) >= 10
ORDER BY match_rate_pct ASC
LIMIT 20;
```

**Expected Result and Next Step**

20 rows, sorted ascending by match_rate (worst first). Overall match_rate should land between 92% and 96%. If any operator's match_rate falls below 85%, Tom has a conversation with Sarah — either retrain the operator, or bump that operator's mandatory QA re-audit rate from 5% up to 20%.

---

## 22. Query 20: Composite Operator Performance Ranking

**Business Context**

Sarah runs quarterly operator performance reviews. Ranking by reject rate alone always penalizes junior operators; ranking by volume alone always penalizes experts working multi-core jobs. A fair ranking needs a z-score-normalized, multi-dimensional weighting. This feeds HR's raise and promotion decisions. Maps to NorthArc's day-to-day operations.

**Tags**

Category: Multiple CTEs + window functions. Difficulty: Advanced. Role: Production Manager.

**Approach**

Three dimensions: volume (splices), quality (reject_rate, lower is better), and first-pass rate (FPY). Rank each dimension within skill_level (not across the whole workforce), since expectations differ by skill level. In SQLite, use RANK() OVER (PARTITION BY skill_level ORDER BY ...). Sum the three ranks together, ascending, to get the composite score.

Add HAVING COUNT(*) >= 100 so operators with too small a sample don't make the leaderboard.

**SQL**

```sql
WITH stats AS (
    SELECT
        sr.operator_id,
        o.name,
        o.skill_level,
        COUNT(*) AS splices,
        SUM(CASE WHEN sr.final_grade = 'Reject' THEN 1 ELSE 0 END) AS rejects,
        SUM(CASE WHEN sr.attempt_count = 1 AND sr.final_grade != 'Reject' THEN 1 ELSE 0 END) AS fpy_pass
    FROM splice_record sr
    JOIN operator o ON sr.operator_id = o.operator_id
    WHERE sr.completed_ts BETWEEN '2025-06-16' AND '2026-06-15'
    GROUP BY sr.operator_id, o.name, o.skill_level
    HAVING COUNT(*) >= 100
),
ranked AS (
    SELECT
        operator_id,
        name,
        skill_level,
        splices,
        ROUND(rejects * 100.0 / splices, 2) AS reject_rate_pct,
        ROUND(fpy_pass * 100.0 / splices, 2) AS fpy_pct,
        RANK() OVER (PARTITION BY skill_level ORDER BY splices DESC) AS volume_rank,
        RANK() OVER (PARTITION BY skill_level ORDER BY rejects * 1.0 / splices ASC) AS quality_rank,
        RANK() OVER (PARTITION BY skill_level ORDER BY fpy_pass * 1.0 / splices DESC) AS fpy_rank
    FROM stats
)
SELECT
    operator_id,
    name,
    skill_level,
    splices,
    reject_rate_pct,
    fpy_pct,
    volume_rank,
    quality_rank,
    fpy_rank,
    volume_rank + quality_rank + fpy_rank AS composite_score
FROM ranked
ORDER BY skill_level, composite_score ASC;
```

**Expected Result and Next Step**

Grouped by skill_level. Within each group, the lowest composite_score (i.e., ranking well on all three dimensions) is that quarter's MVP. Sarah gives the top 20% a 5% raise and puts the bottom 20% into additional training.

---

## 23. Business Question to Query Mapping Table

| Business Question | Corresponding Queries |
|----------|----------|
| Q1 Overview, where is the money leaking | Q1, Q2, Q3 |
| Q2 Electrode replacement policy | Q4, Q5 |
| Q3 Night-shift quality degradation | Q6, Q7 |
| Q4 Multi-core skill mismatch | Q8, Q9 |
| Q5 Over-quality / spec relaxation | Q10, Q11 |
| Q6 AI alerts ignored | Q12, Q13 |
| Q7 Calibration overdue | Q14 |
| Q8 Recall risk, MFG-2024-038 | Q15, Q16 |
| Day-to-day operations | Q17, Q18, Q19, Q20 |

Every business question has at least one query behind it, and the major questions (Q1, Q2, Q3, Q4, Q5, Q6) each get two. Q7 and Q8 have fewer because they're single-point verification and a recall assessment, respectively. The 4 day-to-day operations queries cover Sarah's and Marcus's weekly standup inputs.

---

## 24. Notes

All SQL has been verified against SQLite 3.x. A few notes on SQLite-specific syntax used throughout:

- `julianday(date)` returns the number of days since the start of the Julian calendar; subtracting two julianday values to get a day count is more reliable than subtracting dates directly.
- `strftime('%Y-%m', ts)` slices a datetime into a year-month string, and is more portable than `EXTRACT(MONTH FROM ...)` (the PostgreSQL way of doing it).
- Both `JULIANDAY` and `STRFTIME` accept string dates (ISO 8601 format) directly, with no need to cast to DATE first.
- `GROUP_CONCAT(DISTINCT col)` is SQLite's string aggregation function; the PostgreSQL equivalent is `STRING_AGG`.
- Moving averages use `AVG(...) OVER (ORDER BY ... ROWS BETWEEN N PRECEDING AND CURRENT ROW)`, supported in SQLite 3.25+.
- All date literals use ISO format `YYYY-MM-DD` or `YYYY-MM-DD HH:MM:SS`. SQLite has no strict date type, but string literals combined with julianday work consistently throughout.

Every query maps back to a business question. If new queries get added later, keep following the same order — business question first, SQL second — rather than bolting on SQL just to pad the count.
