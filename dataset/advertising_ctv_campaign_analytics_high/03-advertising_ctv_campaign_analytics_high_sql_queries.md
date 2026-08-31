# Vantage Media CTV Ad Campaign Analytics SQL Query Reference

> Business context, company profile, industry primer, and glossary are in `01-advertising_ctv_campaign_analytics_high_business_context.md`. Table structure, field meanings, and data generation rules are in `02-advertising_ctv_campaign_analytics_high_er_document.md`.

This document provides 20 business-oriented SQL queries designed against the `advertising_ctv_campaign_analytics_high` dataset. Each query solves a real question that a business stakeholder might raise, simulating the actual analysis scenarios at the fictional AdTech SaaS company Vantage Media (whose flagship product is Booking Copilot, an AutoML-driven CTV media buying optimization platform).

---

## 1. How to Use This Document

This document is written for you (a new data analysis intern at Vantage Media). You've already read the business context document and the ER document, and your manager has handed you this query list saying "run these this week and make sure you understand each one." It is not a "set of SQL you can run," it is teaching material: SQL is meant to be read and learned, not just executed.

**Every query follows the same five-section structure**, and reading through them in order walks you through the thought process of a real analyst:

- **Business context**: who is asking, why are they asking now, what decision is the answer going to support. Anchors each query to a specific person and a specific decision.
- **Category / Difficulty / Business role**: three tags that help you tell which kind of SQL skill the query practices, how hard it is, and which role inside the company it serves.
- **Approach**: before you even look at the SQL, think through which tables you need, how to JOIN them, what the aggregation grain is, why you would (or would not) use a CTE or window function, and what gotchas SQLite has. This section is the core teaching value of the document.
- **SQL code**: queries that can be run directly on the generated SQLite database. Key clauses have inline comments.
- **Expected result and business conclusion**: what the result set looks like, which key numbers correspond to which seeded distribution from the business context document, and what the analyst should do next once they have the numbers. Getting numbers out is the start, not the end, of analysis.

**About the reference date (AS_OF_DATE = `2025-10-31`).** The dataset covers 2025-05-01 to 2025-10-31. All queries that mention "last N days" or "past X weeks" use the fixed string `'2025-10-31'` as "today" rather than `DATE('now')`. This keeps results stable and reproducible when run on historical data, so a query won't return an empty set just because the real current date drifted.

**Every query traces back to a business question.** Section 5 of the business context document lists four core business problems (media buying blind spot, customer variance, attribution puzzle, data quality) plus the AutoML model monitoring product line. There's a mapping table at the end of this document tying all 20 queries back to those problems. If a query can't be tied back to a business need, it doesn't belong here.

> **Dataset scale:** 50,000 placements + 42,350 performance records + 50,000 ML predictions (each carries 1 clearance classifier + 1 paired ROAS regressor, across 3 generations in shadow scoring). Supports the full AutoML training + shadow scoring evaluation + BI monitoring stack.

---

## 2. Query Index

| # | Title | Business role | Category | Difficulty |
|------|------|----------|------|------|
| 1 | Network clearance rate ranking analysis | Operations | Aggregation + sorting | Basic |
| 2 | ML model clearance prediction accuracy evaluation | Analyst | Aggregation + join | Intermediate |
| 3 | High-risk placement identification (clearance probability < 0.65) | Manager | Join + filter | Basic |
| 4 | ROAS predicted vs actual comparison | Analyst | Join + computed field | Intermediate |
| 5 | Data quality alert trend analysis (past 30 days) | Operations | Date range + aggregation | Basic |
| 6 | Top 10 advertisers by ROAS | Executive | Aggregation + sorting | Basic |
| 7 | Q4 sports network preemption rate analysis | Manager | Date filter + aggregation | Intermediate |
| 8 | Attribution method impact on ROAS comparison | Analyst | Join + grouping | Intermediate |
| 9 | Correlation between booking lead time and clearance rate | Analyst | Aggregation + grouping | Intermediate |
| 10 | Data source SLA compliance analysis | Operations | Join + date math | Intermediate |
| 11 | Daily placement booking volume trend | Manager | Date aggregation | Basic |
| 12 | Quantifying budget waste from preemption | Finance | Aggregation + computation | Intermediate |
| 13 | User action audit (top active users in last 7 days) | Operations | Aggregation + sorting | Basic |
| 14 | Model version iteration effectiveness comparison | Executive | Window function + aggregation | Advanced |
| 15 | Campaign ROI analysis (end-to-end) | Finance | CTE + multi-table join | Advanced |
| 16 | Network monthly clearance rate trend (time series) | Analyst | Window function + dates | Intermediate |
| 17 | P0 data quality incident mean time to resolve (MTTR) | Manager | Date math + aggregation | Intermediate |
| 18 | Clearance prediction distribution histogram | Analyst | Aggregation + CASE + window function | Intermediate |
| 19 | Advertiser name fuzzy search | Operations | Text matching | Basic |
| 20 | Cross network-type ROAS comparison (subquery) | Executive | Subquery + aggregation | Advanced |

---

## 3. Query Details

### Query 1: Network Clearance Rate Ranking Analysis

**Business context:**
Media buying manager Sarah needs to look at the actual clearance rate performance of TV and streaming networks before her weekly planning meeting, so she can decide which networks to prioritize for next week's bookings. Low-clearance networks (like ESPN) cause many bookings to be preempted, wasting team time and customer budget. She needs a simple ranked list showing which networks are most reliable (high clearance) and which are most risky (low clearance).

**Category:** Aggregation + sorting
**Difficulty:** Basic
**Business role:** Operations / Manager

**Approach:**

This query only needs two tables: the fact table `ad_placement` provides each booking's status, and the dimension table `network` provides network names and types. One INNER JOIN on `network_id` is enough. The clearance rate caliber is the key thing: the denominator only counts resolved bookings (status is cleared or preempted), so exclude status='pending' in the WHERE clause, otherwise unresolved slots would drag the rate down. The clearance rate itself is computed with the `AVG(CASE WHEN status='cleared' THEN 1.0 ELSE 0.0 END)` trick, which is cleaner than COUNT-then-divide. The aggregation grain is "one network per row," so GROUP BY network name and type, no CTE or window function needed. Sort by clearance rate ascending so the riskiest networks float to the top.

```sql
-- Aggregate actual clearance rate by network, sorted ascending
-- Note: aligned with Q9/Q14/Q16/Q18 — only count resolved placements (cleared/preempted),
-- excluding pending status where the outcome is not yet confirmed.
SELECT
    n.network_name AS network_name,
    n.network_type AS network_type,
    COUNT(*) AS total_bookings,
    SUM(CASE WHEN a.status = 'cleared' THEN 1 ELSE 0 END) AS actual_aired,
    SUM(CASE WHEN a.status = 'preempted' THEN 1 ELSE 0 END) AS preempted_count,
    ROUND(AVG(CASE WHEN a.status = 'cleared' THEN 1.0 ELSE 0.0 END), 4) AS actual_clearance_rate
FROM ad_placement a
JOIN network n ON a.network_id = n.id
WHERE a.status IN ('cleared', 'preempted')
GROUP BY n.network_name, n.network_type
ORDER BY actual_clearance_rate ASC
LIMIT 15;
```

**Expected result:**
The result set shows total bookings, actual aired, preempted count, and clearance rate per network. Sports networks like ESPN and ESPN2 will appear at the top of the list (lowest clearance rate, ~55-65%), while non-live networks like HGTV, Hulu, and Pluto TV will appear at the bottom (clearance rate >90%). The manager can adjust booking strategy accordingly, reducing reliance on high-risk networks.

---

### Query 2: ML Model Clearance Prediction Accuracy Evaluation

**Business context:**
The data science team lead needs to evaluate the accuracy of the latest deployed ML model (v2.3.1) on clearance prediction. They need to know the accuracy when the model predicts "will clear" (predicted_clearance_prob >= 0.5) and "will be preempted" (< 0.5), and how this compares to prior model versions. This metric directly affects whether the team needs to retrain the model or adjust feature engineering. The current product bar is **88% accuracy** — this is because the baseline (always predict the majority class) already gets ~85% in an imbalanced setting where ~85% of data is cleared, so the model must significantly beat baseline (>3pp) to be product-worthy; only once that bar is cleared will product expose prediction scores to the media buying team as a decision aid.

**Category:** Aggregation + join + conditional logic
**Difficulty:** Intermediate
**Business role:** Analyst

**Approach:**

This query aligns predictions (`prediction_result`) with ground truth (`ad_placement.status`) and then computes a confusion matrix per model version. Three tables: the prediction table joins to ground truth via `placement_id` and to the model version via `model_version_id`. There's a trap to avoid: `model_version_id` only points to clearance classifiers (ids 1/2/3), but the model_version table also contains roas regressors (ids 4/5/6) mixed in, so add `mv.model_type='clearance_classifier'` to lock the scope, aligned with Q14. Use a CTE to first label each prediction as True Positive / False Positive / False Negative / True Negative (whether predicted prob is >=0.5 cross-tabbed against whether actual is cleared), then aggregate by version in the outer query — splitting it into two layers makes the logic clearer. Aggregation grain is "one model version per row." Note that shadow scoring has all three generations scoring the same data, so each version's sample size is similar (about 16,600), making the comparison fair.

```sql
-- Evaluate model prediction accuracy (confusion matrix)
WITH prediction_evaluation AS (
    SELECT
        p.prediction_code,
        p.predicted_clearance_prob,
        CASE
            WHEN a.status = 'cleared' THEN 1
            WHEN a.status = 'preempted' THEN 0
            ELSE NULL
        END AS actual_cleared,
        CASE
            WHEN p.predicted_clearance_prob >= 0.5 AND a.status = 'cleared' THEN 'True Positive'
            WHEN p.predicted_clearance_prob >= 0.5 AND a.status = 'preempted' THEN 'False Positive'
            WHEN p.predicted_clearance_prob < 0.5 AND a.status = 'cleared' THEN 'False Negative'
            WHEN p.predicted_clearance_prob < 0.5 AND a.status = 'preempted' THEN 'True Negative'
        END AS prediction_outcome,
        mv.version_code AS model_version
    FROM prediction_result p
    JOIN ad_placement a ON p.placement_id = a.id
    JOIN model_version mv ON p.model_version_id = mv.id
    WHERE a.status IN ('cleared', 'preempted')
      AND mv.model_type = 'clearance_classifier'  -- aligned with Q14 caliber, explicitly evaluating classifiers only
)
SELECT
    model_version,
    COUNT(*) AS total_predictions,
    SUM(CASE WHEN prediction_outcome IN ('True Positive', 'True Negative') THEN 1 ELSE 0 END) AS correct_predictions,
    ROUND(AVG(CASE WHEN prediction_outcome IN ('True Positive', 'True Negative') THEN 1.0 ELSE 0.0 END), 4) AS accuracy,
    SUM(CASE WHEN prediction_outcome = 'True Positive' THEN 1 ELSE 0 END) AS TP,
    SUM(CASE WHEN prediction_outcome = 'False Positive' THEN 1 ELSE 0 END) AS FP,
    SUM(CASE WHEN prediction_outcome = 'False Negative' THEN 1 ELSE 0 END) AS FN,
    SUM(CASE WHEN prediction_outcome = 'True Negative' THEN 1 ELSE 0 END) AS TN
FROM prediction_evaluation
GROUP BY model_version
ORDER BY model_version DESC;
```

**Expected result:**
The result set shows accuracy and confusion matrix per model version (shadow scoring on the same data distribution, with n ≈ **16,600** per version):

| Version | Accuracy | TP | FP | FN | TN |
|---|---|---|---|---|---|
| v2.1.5 | ~86.0% | ~13,900 | ~2,030 | ~270 | ~470 |
| v2.2.0 | ~85.8% | ~13,900 | ~2,070 | ~270 | ~430 |
| v2.3.1 | ~85.6% | ~13,900 | ~2,100 | ~270 | ~410 |

**Business conclusion**: All three versions **fail to clear the 88% product bar** (all about 86.0%, off by 2pp). This means even the newest model only beats the "always predict cleared" majority-class baseline (~85.5%) by ~0.5pp, **so prediction scores cannot yet be formally exposed to the media buying team as a decision aid** — the team needs to keep optimizing (e.g., introducing new features, upgrading model architecture, oversampling the preempted class).

**Why are the three versions essentially flat?** With the data scaled up to 50K, the larger sample size means noise smoothing converges to a tiny range, and the three versions' `predicted_clearance_prob` means/variances converge; meanwhile **extreme class imbalance (cleared accounts for 85%)** lets the majority-class baseline dominate overall accuracy, and narrowing model_noise cannot break through this ceiling. **This is the actual real-world pain point Vantage Media's data science team faces right now — they should shift to the algorithm layer (class weighting / focal loss / resampling) rather than continuing to tune hyperparameters.**

**Confusion matrix interpretation:** The imbalanced data (cleared ~85%) makes the model heavily skewed toward predicting the majority class — TP is much larger than TN, FP (preempted misclassified as cleared) is significantly more than FN. If the business cares about "identifying high-risk slots that will be preempted," the better metric is **Recall on preempted** = TN / (TN + FP) ≈ 18% (rather than overall accuracy), and that's where v2 should focus its optimization. This also matches the progressive narrative in Q14: narrowing noise alone cannot solve class imbalance — algorithmic changes are needed.

---

### Query 3: High-Risk Placement Identification (Clearance Probability < 0.65)

**Business context:**
The media buying team lead needs to look at all "high-risk placements" — those with predicted clearance probability below 0.65 — for today and the coming 7 days every morning. These placements have over a 35% chance of being preempted, so the lead needs to discuss the risk with the customer or consider switching to a more reliable network and daypart. This list lets the team shift from "reactive firefighting" to "proactive risk management," reducing customer complaints and budget waste.

**Category:** Join + filter
**Difficulty:** Basic
**Business role:** Manager

**Approach:**

This is a detail-list query, no aggregation — the output is "high-risk slots that need a human to walk through one by one." The main table is `ad_placement`, joined to the prediction table via `placement_id` to get predicted clearance probability, then to advertiser, network, daypart to translate codes into human-readable names. The filter has two layers of meaning: `predicted_clearance_prob < 0.65` picks slots the model thinks are risky, and `status='pending'` picks slots whose outcome is not yet confirmed and where intervention is still possible (already cleared or preempted slots have no intervention value). The date window uses fixed reference date `'2025-10-29'` plus 7 days, simulating the lead looking at the coming week from that day. Because pending slots only appear at the end of the snapshot, this list is naturally short (about 80 records), which is exactly the design intent of the Manager view — "few but high-stakes, contact customers one by one."

```sql
-- Identify high-risk placements (clearance probability < 0.65)
SELECT
    a.placement_code AS placement_code,
    adv.advertiser_name AS advertiser,
    n.network_name AS network,
    d.daypart_name AS daypart,
    DATE(a.scheduled_air_time) AS scheduled_air_date,
    a.booked_cpm AS booked_cpm,
    p.predicted_clearance_prob AS predicted_clearance_prob,
    p.predicted_roas AS predicted_roas,
    p.confidence_level AS confidence_level,
    ROUND((1 - p.predicted_clearance_prob) * 100, 1) || '%' AS preemption_risk
FROM ad_placement a
JOIN prediction_result p ON a.id = p.placement_id
JOIN advertiser adv ON a.advertiser_id = adv.id
JOIN network n ON a.network_id = n.id
JOIN daypart d ON a.daypart_id = d.id
WHERE p.predicted_clearance_prob < 0.65
  AND a.status = 'pending'
  -- Reference date: use data snapshot cutoff '2025-10-31', simulating the lead's view when "today" is 10/29
  AND DATE(a.scheduled_air_time) BETWEEN DATE('2025-10-29') AND DATE('2025-10-29', '+7 days')
ORDER BY p.predicted_clearance_prob ASC, a.scheduled_air_time ASC
LIMIT 50;
```

**Expected result:**
The result set lists all high-risk placements, sorted ascending by clearance probability. The pending queue in this dataset has **~250 records** (only appearing at the snapshot tail 2025-10-29 → 2025-10-31), of which about **~80 records** match "low predicted clearance + still pending." This is precisely the Manager view's design intent — a small set of high-risk events that need to be handled one by one with the customer. NFL primetime slots on ESPN/ESPN2/FOX will appear at the top (clearance probability 0.30-0.55).

---

### Query 4: ROAS Predicted vs Actual Comparison

**Business context:**
The product team needs to show executives the value of the "ML-driven ROAS prediction" feature. They need to compute MAPE (Mean Absolute Percentage Error) between predicted ROAS and actual ROAS, broken down by advertiser category. If MAPE is below 25%, the prediction is reliable enough to serve as a customer decision aid; if MAPE is above 35%, the model needs improvement. This result directly drives whether the product roadmap doubles down on ROAS prediction.

**Category:** Join + computed field + aggregation
**Difficulty:** Intermediate
**Business role:** Analyst

**Approach:**

This query computes MAPE for ROAS predictions, broken down by advertiser category. The chain is `prediction_result` via `placement_id` to `ad_placement`, then to `performance_actual` for actual ROAS, then via advertiser to advertiser_category. INNER JOIN to performance_actual has an implicit effect: only cleared slots have an actual, so the sample is automatically restricted to aired slots, which matches "only compute error on predictions that have ground truth." MAPE uses `AVG(ABS(predicted_roas - roas) / roas)`, with `NULLIF(roas, 0)` and `WHERE roas > 0` as a double safety net to avoid divide-by-zero. Aggregation grain is "one category per row." Watch out for an interpretation trap: because `predicted_roas` is anchored to actual ROAS plus versioned noise at generation time, MAPE across categories will be quite close, and category differences won't show up in this query. To see the real gradient, group by model version (roas regressor) instead, and you'll see the 12% → 8% → 5% drop.

```sql
-- ROAS prediction accuracy analysis (MAPE)
SELECT
    ac.category_name AS advertiser_category,
    COUNT(*) AS sample_size,
    ROUND(AVG(p.predicted_roas), 2) AS avg_predicted_roas,
    ROUND(AVG(pa.roas), 2) AS avg_actual_roas,
    ROUND(AVG(ABS(p.predicted_roas - pa.roas)), 2) AS mean_absolute_error,
    ROUND(AVG(ABS(p.predicted_roas - pa.roas) / NULLIF(pa.roas, 0)) * 100, 2) || '%' AS MAPE
FROM prediction_result p
JOIN ad_placement a ON p.placement_id = a.id
JOIN performance_actual pa ON a.id = pa.placement_id
JOIN advertiser adv ON a.advertiser_id = adv.id
JOIN advertiser_category ac ON adv.category_id = ac.id
WHERE pa.roas > 0  -- exclude ROAS = 0 samples to keep MAPE stable
GROUP BY ac.category_name
ORDER BY sample_size DESC;
```

**Expected result:**
The result set shows ROAS prediction error per advertiser category. Overall MAPE lands around ~7-10% (v2.3.1 dominant), meeting the business "MAPE < 25%" target.

> **Interpretation caveat:** Because `predicted_roas` is anchored to `actual_roas` + versioned noise at generation time (see "Model prediction error narrows by version" in the ER document for the design simplification), MAPE across all categories is roughly uniform, landing in the narrow range of ~8% ± 1pp. **The category × network dimension differences are not visible in this query** — because the error in `predicted_roas` is determined only by `model_noise`, independent of category.
>
> If you want to see **MAPE differences by model version**, add the `mv.version_code` dimension to this query — you'll see v2.1.5 ~12% / v2.2.0 ~8% / v2.3.1 ~5% (this is where model_noise actually shows its effect in the generator). But within each version, categories remain uniform.
>
> If you want to see the **category × network ROAS matrix differences** ("Health on HGTV 1.2-1.8x but on ESPN 0.5-0.9x"), query `performance_actual.roas` directly — that's where the generator's ROAS_MATRIX actually lands, see ER doc data generation rule 4.

---

### Query 5: Data Quality Alert Trend Analysis (Past 30 Days)

**Business context:**
The data engineering team lead needs to present data quality status at the monthly ops review. He needs to count, day by day over the past 30 days, how many P0/P1/P2 data quality alerts were triggered, and the resolution rate. If P0 alerts (severe issues that block downstream) appear frequently, upstream data source quality is deteriorating and conversations with vendors need to start. This trend chart helps the team tell whether data quality is improving or getting worse.

**Category:** Date range + aggregation + grouping
**Difficulty:** Basic
**Business role:** Operations

**Approach:**

This query draws the daily DQ trend, broken out by severity. Two tables: `data_quality_log` is the result of each check, joined to `data_quality_rule` to get severity (P0/P1/P2). Aggregation grain is "one day one severity per row," so GROUP BY uses `DATE(run_timestamp)` and severity. Failure count and alert count are computed using conditional aggregation (SUM CASE) in the same scan. Average resolution time is a time difference, and SQLite has no native hour-difference function, so use `(JULIANDAY(resolved_at) - JULIANDAY(run_timestamp)) * 24` to convert Julian day difference to hours, and only compute it on resolved records (resolved_at not null), using CASE to exclude unresolved ones from the average. The date window uses `DATE('2025-10-31', '-30 days')` to look back 30 days.

```sql
-- Data quality alert trend (by severity)
SELECT
    DATE(l.run_timestamp) AS date,
    r.severity AS severity,
    COUNT(*) AS check_count,
    SUM(CASE WHEN l.status = 'failed' THEN 1 ELSE 0 END) AS failure_count,
    SUM(CASE WHEN l.alert_fired THEN 1 ELSE 0 END) AS alert_count,
    SUM(CASE WHEN l.resolved_at IS NOT NULL THEN 1 ELSE 0 END) AS resolved_count,
    ROUND(AVG(CASE WHEN l.resolved_at IS NOT NULL
                   THEN (JULIANDAY(l.resolved_at) - JULIANDAY(l.run_timestamp)) * 24
                   ELSE NULL END), 2) AS avg_resolution_hours
FROM data_quality_log l
JOIN data_quality_rule r ON l.rule_id = r.id
-- Reference date: data snapshot cutoff '2025-10-31', looking back 30 days
WHERE l.run_timestamp >= DATE('2025-10-31', '-30 days')
GROUP BY DATE(l.run_timestamp), r.severity
ORDER BY DATE(l.run_timestamp) DESC, r.severity ASC;
```

**Expected result:**
The result set shows alerts per day per severity. P0 alerts should be very rare (< 5 per month), P1 alerts occasional (10-20 per month), and P2 alerts more common. Average resolution time should be within 2-4 hours (target < 2 hours for P0, < 4 hours for P1).

---

### Query 6: Top 10 Advertisers by ROAS

**Business context:**
The CEO needs to show, at the quarterly board meeting, "which customers' TV ad campaigns are most effective." The CFO cares about how much revenue each ad dollar invested by the customer brought back. High-ROAS customers are the company's premium accounts and worth deepening relationships with; low-ROAS customers may need to optimize their campaign strategy or pricing. This Top 10 list is one of the core indicators of company customer health, directly affecting renewal and growth strategy.

**Category:** Aggregation + sorting
**Difficulty:** Basic
**Business role:** Executive

**Approach:**

This query ranks advertisers by ROAS. Four tables chained together: advertiser to category for industry, to ad_placement for all slots this customer has, then to performance_actual for spend and revenue. INNER JOIN to performance_actual means we only count aired (cleared) slots, which is the right caliber for computing real returns. There's an important SQL teaching point here: ROAS has two formulas. `AVG(roas)` averages per-record ROAS, which is skewed by small orders with extreme values; `SUM(revenue)/SUM(spend)` is the spend-weighted overall ROAS, which is the true return the CFO cares about. List both for comparison, but sort by the overall ROAS. `HAVING COUNT(DISTINCT a.id) >= 10` filters out customers with too few campaigns whose sample isn't trustworthy.

```sql
-- Top 10 advertisers with the best ROAS performance
SELECT
    adv.advertiser_name AS advertiser,
    ac.category_name AS industry_category,
    COUNT(DISTINCT a.id) AS placements_count,
    ROUND(SUM(pa.spend_usd), 2) AS total_spend_usd,
    ROUND(SUM(pa.attributed_revenue_usd), 2) AS total_attributed_revenue_usd,
    ROUND(AVG(pa.roas), 2) AS avg_roas,
    ROUND(SUM(pa.attributed_revenue_usd) / SUM(pa.spend_usd), 2) AS overall_roas
FROM advertiser adv
JOIN advertiser_category ac ON adv.category_id = ac.id
JOIN ad_placement a ON adv.id = a.advertiser_id
JOIN performance_actual pa ON a.id = pa.placement_id
-- Note: performance_actual.finalized_at is already NOT NULL in the schema,
-- so no extra filter needed; the JOIN already keeps only placements with attribution data.
GROUP BY adv.advertiser_name, ac.category_name
HAVING COUNT(DISTINCT a.id) >= 10  -- at least 10 placements
ORDER BY overall_roas DESC
LIMIT 10;
```

**Expected result:**
The result set shows the top 10 advertisers by ROAS. Health & Wellness and Apparel customers on streaming platforms may hit ROAS of 1.6-2.0x. Finance customers in NBC/CBS primetime see 1.2-1.5x ROAS. These customers are the company's star accounts and should be prioritized.

---

### Query 7: Q4 Sports Network Preemption Rate Analysis

**Business context:**
The media buying manager has to be especially careful with sports networks (ESPN, FOX) during Q4 (October-December) because of their high preemption risk. Large live events like NFL regular season and playoffs cause inventory on these networks to be preempted frequently. The manager needs to quantify that risk: what is the actual preemption rate on sports networks in Q4? How much worse is it than Q3? This data helps the team decide whether to reduce reliance on sports networks, or set aside a "reserve budget" for customers to absorb preemptions.

**Category:** Date filter + aggregation + comparison
**Difficulty:** Intermediate
**Business role:** Manager

**Approach:**

This query puts the same set of sports networks' Q3 and Q4 preemption rates side by side, to see how much the NFL season pushed them up. First a CTE `quarterly_stats` computes preemption rate for each network in each quarter, scoped to the three networks most directly affected by NFL (ESPN/ESPN2/FOX), with quarter derived from `strftime('%m', scheduled_air_date)`. The quarter check casts the month to an integer (CAST AS INTEGER) before comparing — that's the common pattern in SQLite for dealing with strftime's string result. The outer query does a row-to-column pivot: `MAX(CASE WHEN quarter='Q3' THEN preemption_rate END)` and the matching Q4 version collapse two rows (Q3 row, Q4 row) into one row with two columns, so the worsening can be computed by subtraction. Final aggregation grain is "one network per row." Note that Q3 already includes the impact of the September kickoff, so the Q3-to-Q4 delta is the additional worsening from deeper season (October's dense game schedule).

```sql
-- Q4 sports network preemption rate analysis (compared to Q3)
-- Scope: sports-leaning networks directly affected by NFL Regular Season per ER doc = ESPN/ESPN2/FOX
WITH quarterly_stats AS (
    SELECT
        n.network_name AS network_name,
        CASE
            WHEN CAST(strftime('%m', a.scheduled_air_date) AS INTEGER) BETWEEN 7 AND 9 THEN 'Q3'
            WHEN CAST(strftime('%m', a.scheduled_air_date) AS INTEGER) BETWEEN 10 AND 12 THEN 'Q4'
        END AS quarter,
        COUNT(*) AS total_bookings,
        SUM(CASE WHEN a.status = 'preempted' THEN 1 ELSE 0 END) AS preempted_count,
        ROUND(AVG(CASE WHEN a.status = 'preempted' THEN 1.0 ELSE 0.0 END), 4) AS preemption_rate
    FROM ad_placement a
    JOIN network n ON a.network_id = n.id
    WHERE n.network_code IN ('ESPN', 'ESPN2', 'FOX')
      AND a.status IN ('cleared', 'preempted')
      AND CAST(strftime('%m', a.scheduled_air_date) AS INTEGER) BETWEEN 7 AND 12
    GROUP BY n.network_name, quarter
)
SELECT
    network_name,
    MAX(CASE WHEN quarter = 'Q3' THEN preemption_rate END) AS q3_preemption_rate,
    MAX(CASE WHEN quarter = 'Q4' THEN preemption_rate END) AS q4_preemption_rate,
    ROUND(MAX(CASE WHEN quarter = 'Q4' THEN preemption_rate END) - MAX(CASE WHEN quarter = 'Q3' THEN preemption_rate END), 4) AS worsening_delta
FROM quarterly_stats
GROUP BY network_name
ORDER BY q4_preemption_rate DESC;
```

**Expected result:**
The result set shows sports networks' preemption rate rising significantly in Q4. Note: Q3 already includes the impact of the NFL kickoff in September (the NFL season window 9/5 → 10/31 is explicitly defined in the dataset).

| Network | Q3 Preemption Rate | Q4 Preemption Rate | Worsening Delta |
|------|----------|----------|---------|
| ESPN | ~23% | ~57% | +34 pp |
| ESPN2 | ~25% | ~63% | +38 pp |
| FOX | ~20% | ~54% | +34 pp |

The Q3 → Q4 preemption rate delta lands in the 30-40 percentage point range, with per-network differences coming from the random NFL penalty (uniform 0.15-0.20) plus network baseline clearance rate variation. The manager can use this to warn customers, and in particular recommend a +50% reserve budget for placements during October's dense sports schedule.

---

### Query 8: Attribution Method Impact on ROAS Comparison

**Business context:**
The data analyst needs to evaluate whether the ROAS data from different attribution partners is consistent. AttributionPro uses pixel matching (precise), Nielsen uses panel extrapolation (estimation), ImpactTracker uses IP matching (medium precision). If the three partners report ROAS differences greater than 30% on the same set of placements, there's a systematic bias in attribution methods that needs to be calibrated with partners. This analysis helps the team judge which partner's data is more reliable and whether a vendor change is needed.

**Category:** Join + grouping + aggregation
**Difficulty:** Intermediate
**Business role:** Analyst

**Approach:**

This query compares whether the four attribution partners report consistent ROAS. Only two tables needed: `performance_actual` provides each performance record, joined to `attribution_partner` for partner name and attribution method. One GROUP BY (partner + method) is enough — no CTE or window function needed. What makes this query work is a clean control: because partners are randomly assigned to placements, the four partners cover the same underlying campaign distribution, so the ROAS differences are purely from systematic bias in attribution method (pixel / IP / panel), not from one partner happening to land on good slots. When you see two pixel partners with almost identical ROAS, you can confirm the difference is from method, not vendor. Listing AVG, MIN, MAX side by side intuitively shows the spread within each method.

```sql
-- Comparison of ROAS across attribution methods
SELECT
    ap.partner_name AS attribution_partner,
    ap.attribution_method AS attribution_method,
    COUNT(*) AS sample_size,
    ROUND(AVG(pa.roas), 2) AS avg_roas,
    ROUND(MIN(pa.roas), 2) AS min_roas,
    ROUND(MAX(pa.roas), 2) AS max_roas,
    ROUND(AVG(pa.attributed_conversions), 1) AS avg_conversions,
    ROUND(AVG(pa.attribution_window_days), 1) AS avg_attribution_window_days
FROM performance_actual pa
JOIN attribution_partner ap ON pa.attribution_partner_id = ap.id
GROUP BY ap.partner_name, ap.attribution_method
ORDER BY avg_roas DESC;
```

**Expected result:**
The result set shows the comparison of 4 attribution partners sorted descending by average ROAS (the data generator overlays an *attribution method coefficient* on each `performance_actual.roas`: `pixel_match ×1.10` / `ip_match ×1.00` / `panel_extrapolation ×0.80`, producing a stable gradient at the partner dimension):

| Attribution Partner | Attribution Method | Avg ROAS (approx) |
|--------------|----------|----------------|
| ConversionPixel | pixel_match | ~1.32 |
| AttributionPro | pixel_match | ~1.32 |
| ImpactTracker | ip_match | ~1.20 |
| Nielsen Digital | panel_extrapolation | ~0.96 |

**Business conclusion:** Pixel matching (precise pixel match) systematically reports the highest ROAS (~1.32x), IP matching sits in the middle (~1.20x), and **panel extrapolation (Nielsen panel) systematically underestimates ROAS** (~0.96x, about 27% below pixel). The fact that the two pixel partners agree confirms that the difference comes from the *method*, not from individual vendors. This >30% caliber gap is a reminder: cross-partner ROAS comparisons must first be normalized by attribution method, otherwise some campaigns will be incorrectly flagged as "unprofitable."

> **Methodological caveat:** The four partners' `attribution_partner_id` are randomly assigned to placements, so they cover the *same distribution* of underlying campaigns — the ROAS differences come purely from attribution method coefficients, with no selection bias. This is exactly the clean control needed to demonstrate "systematic bias in attribution method." Per-network_type average ROAS is unaffected (the weighted average of the 4 partner method coefficients = 1.00).

---

### Query 9: Correlation Between Booking Lead Time and Clearance Rate

**Business context:**
The data analyst, while optimizing ML model features, needs to verify whether "booking lead time" is a valid predictor of clearance rate. The business hypothesis is: placements booked 30-60 days in advance are more likely to be preempted (because the network hasn't yet locked in what programming will run in that slot), while placements booked 3-7 days in advance have higher clearance rate (because the slot is already determined). This analysis helps the team decide whether to encourage customers to "book late" to lift clearance rate, or to give more weight to the booking_lead_days feature in the ML model.

**Category:** Aggregation + grouping + trend analysis
**Difficulty:** Intermediate
**Business role:** Analyst

**Approach:**

This query verifies a business hypothesis: book earlier, get preempted more. Only one table (`ad_placement`) is needed, no JOIN. The core technique is using CASE to bucket continuous `booking_lead_days` into 5 buckets (within 7 days, 8-14 days, and so on). SQLite cannot reference SELECT-clause column aliases in GROUP BY, so the bucketing CASE expression must be written twice — once in SELECT and once in GROUP BY (the content must match exactly). Clearance rate is again computed via `AVG(CASE WHEN cleared)`, and like Q1 only counts resolved slots. Ordering is a small trap: sorting directly by the bucket text gives lexicographic order (scrambled), so use `ORDER BY MIN(booking_lead_days)` to keep the buckets in real day order, so you can see the monotonic decline in clearance rate.

```sql
-- Correlation analysis between booking lead time and clearance rate
SELECT
    CASE
        WHEN a.booking_lead_days <= 7 THEN '<=7 days'
        WHEN a.booking_lead_days <= 14 THEN '8-14 days'
        WHEN a.booking_lead_days <= 30 THEN '15-30 days'
        WHEN a.booking_lead_days <= 60 THEN '31-60 days'
        ELSE '>60 days'
    END AS booking_lead_time,
    COUNT(*) AS total_bookings,
    SUM(CASE WHEN a.status = 'cleared' THEN 1 ELSE 0 END) AS actual_aired,
    ROUND(AVG(CASE WHEN a.status = 'cleared' THEN 1.0 ELSE 0.0 END), 4) AS clearance_rate,
    ROUND(AVG(a.booked_cpm), 2) AS avg_cpm
FROM ad_placement a
WHERE a.status IN ('cleared', 'preempted')
GROUP BY
    CASE
        WHEN a.booking_lead_days <= 7 THEN '<=7 days'
        WHEN a.booking_lead_days <= 14 THEN '8-14 days'
        WHEN a.booking_lead_days <= 30 THEN '15-30 days'
        WHEN a.booking_lead_days <= 60 THEN '31-60 days'
        ELSE '>60 days'
    END
ORDER BY MIN(a.booking_lead_days) ASC;
```

**Expected result:**
The result set shows 5 lead-time buckets, with clearance rate **monotonically declining** as lead time increases (the data generator applies a tiered clearance adjustment on booking_lead_days: ≤7 +7.5pp / 8-14 +3.5pp / 15-30 +0.5pp / 31-60 -3pp / >60 -6pp (weighted mean ≈ +2.1pp, comparable to the prior single ≤7 +5pp tier, keeping overall clearance rate ~85%), and adds 75/90 days to the lead-day distribution so that the `>60 days` bucket is non-empty):

| Booking Lead Time | Total Bookings | Clearance Rate (approx) |
|------------|----------|-------------|
| <=7 days | ~16,850 | ~0.899 |
| 8-14 days | ~7,800 | ~0.863 |
| 15-30 days | ~11,950 | ~0.835 |
| 31-60 days | ~8,070 | ~0.805 |
| >60 days | ~5,090 | ~0.787 |

Placements booked within 7 days have the highest clearance rate (~90%), and those booked more than 60 days out the lowest (~79%), forming a clear monotonic decline. This validates the business hypothesis — lead time is a valid predictor of clearance rate, and this feature should be strengthened in the ML model. The team can also recommend customers "book late" on critical placements to lower preemption risk.

---

### Query 10: Data Source SLA Compliance Analysis

**Business context:**
The data ops team needs to report SLA compliance to upstream data vendors (TV networks, attribution partners) weekly. For example, ESPN commits to delivering the prior day's air log by 6 a.m. with a 2-hour tolerance (SLA threshold). If ESPN has been late past 8 a.m. on more than 10% of days in the past 30 days, that's a serious SLA breach to escalate to vendor management. This analysis helps the team quantify vendor reliability and provides data for renewal negotiations.

**Category:** Join + date math + aggregation
**Difficulty:** Intermediate
**Business role:** Operations

**Approach:**

This query computes the past-30-day SLA compliance rate for each data source. The two tables logically correspond via `source_name` (no hard foreign key between them, just a convention-based equijoin). The direction of the JOIN and the placement of the predicate are the key teaching points here: use `data_source_sla LEFT JOIN ingestion_metadata`, and put the 30-day date filter in the ON clause, not the WHERE clause. If you put it in WHERE, a data source that hasn't had any recent ingestion at all gets filtered out because all its right-hand columns are NULL; putting it in ON keeps that source visible and shows a compliance rate of 0%, which is exactly the signal ops needs to see. Compliance is judged from the difference between the actual arrival time and the "expected arrival time on the day," using `julianday(ingested_at) - julianday(ingestion_date) - expected_delivery_hour/24.0` times 24 to convert to hours, which correctly handles cross-day delays.

```sql
-- Data source SLA compliance analysis
-- SLA definition: actual arrival time vs ("expected arrival time on the day") within sla_threshold_hours
-- Actual arrival uses ingested_at (absolute datetime), expected = date(ingestion_date) + expected_delivery_hour
-- Use julianday to compute the hour difference, correctly handling cross-day delays.
-- Reference date: '2025-10-31', looking back 30 days
SELECT
    sla.source_name AS data_source,
    sla.source_type AS source_type,
    sla.expected_delivery_hour AS expected_delivery_hour,
    sla.sla_threshold_hours AS sla_threshold_hours,
    COUNT(im.id) AS ingestion_days,
    SUM(CASE
        WHEN (julianday(im.ingested_at)
              - julianday(im.ingestion_date) - sla.expected_delivery_hour / 24.0
             ) * 24 <= sla.sla_threshold_hours
        THEN 1 ELSE 0
    END) AS sla_compliant_days,
    ROUND(
        SUM(CASE
            WHEN (julianday(im.ingested_at)
                  - julianday(im.ingestion_date) - sla.expected_delivery_hour / 24.0
                 ) * 24 <= sla.sla_threshold_hours
            THEN 1.0 ELSE 0.0
        END) / NULLIF(COUNT(im.id), 0),
        4
    ) AS sla_compliance_rate
FROM data_source_sla sla
-- Predicate in ON clause keeps data sources with no recent ingestion (SLA = 0% rather than dropped)
LEFT JOIN ingestion_metadata im
       ON sla.source_name = im.source_name
      AND im.ingestion_date >= DATE('2025-10-31', '-30 days')
GROUP BY sla.source_name, sla.source_type, sla.expected_delivery_hour, sla.sla_threshold_hours
ORDER BY sla_compliance_rate ASC;
```

**Expected result:**
The result set shows past-30-day SLA compliance per data source (2025-10-01 → 2025-10-31):

| Data Source | Ingestion Days | SLA Compliance Rate |
|--------|---------|----------|
| Nielsen Panel Data | ~23 | ~100% (panel data has a 48h grace window, high latency tolerance) |
| AttributionPro API | ~20 | ~85% (typical attribution API performance) |
| ESPN Delivery Log | ~25 | ~64% (Q4 NFL period network log peak, latency obvious) |
| NBC Delivery Log | ~21 | ~52% (similar to ESPN, needs vendor follow-up) |
| Hulu Impression Feed | ~24 | ~0% (**known historical mismatch between configured SLA and actual upstream delivery time**; SLA configured at expected=4h but vendor actually delivers around noon — a classic "business ops and data governance need to align" scenario) |

The Hulu row at 0% is a **real pain-point case** currently on the Vantage Media ops team: the data governance team signed the SLA template 12 months ago, but Hulu's actual delivery rhythm is around noon, and the SLA was never corrected. Exactly this kind of "config detached from reality" ops issue is what BI alerts + quarterly vendor reviews are meant to catch.

---

### Query 11: Daily Placement Booking Volume Trend

**Business context:**
The business development manager needs to monitor the company's growth trend. Daily placement booking volume is an important leading indicator — if bookings keep growing, customer demand is strong; if bookings are declining, churn or market competition may be intensifying. This trend chart is shown at weekly management meetings to help the CEO judge whether the company is on track. In particular, Q4 (peak season) bookings should grow 30-40% over Q3.

**Category:** Date aggregation + trend analysis
**Difficulty:** Basic
**Business role:** Manager

**Approach:**

This query plots the daily booking trend line, a leading indicator of business health. Just one table (`ad_placement`), aggregated to the day with `DATE(scheduled_air_date)`. Gross media buy is `SUM(booked_cpm * booked_impressions / 1000)` (CPM is per thousand impressions, so divide by 1000). A caliber reminder: what's being computed is the customer's total spend (gross media buy), not the platform's net revenue — the platform still needs to multiply by the take-rate (10% to 15%). The date window uses fixed reference date with 60 days back and 30 days forward. That 30 days forward (November) is empty in this dataset because the snapshot ends at 10-31; this is a deliberate "snapshot semantics" choice, since in a production environment that section would have booked-but-not-yet-aired future placements.

```sql
-- Daily placement booking volume trend
-- Reference date: '2025-10-31' (data snapshot cutoff); look back 60 days + look forward 30 days
-- Naming convention: gross media buy is the advertiser's total spend, not the platform's net revenue;
-- the platform's take-rate is typically 10-15% and needs to be converted separately.
SELECT
    DATE(a.scheduled_air_date) AS air_date,
    COUNT(*) AS bookings,
    SUM(a.booked_impressions) AS total_booked_impressions,
    ROUND(SUM(a.booked_cpm * a.booked_impressions / 1000), 2) AS gross_media_buy_usd
FROM ad_placement a
WHERE DATE(a.scheduled_air_date) >= DATE('2025-10-31', '-60 days')
  AND DATE(a.scheduled_air_date) <= DATE('2025-10-31', '+30 days')
GROUP BY DATE(a.scheduled_air_date)
ORDER BY DATE(a.scheduled_air_date) ASC;
```

**Expected result:**
The result set shows daily bookings and gross media buy. The actual coverage is 2025-09-01 → 2025-10-31 (61 days):
- September: ~253 bookings/day / ~$0.41M media buy/day
- October: ~358 bookings/day / ~$0.57M media buy/day (**Q4 booking +40% by design**)
- Monthly totals: September 7,605 (~$12.2M) / October **11,095** (~$17.7M)
- The forward 30 days (November) is empty in this dataset because the snapshot ends 2025-10-31. **In production** this November stretch would have booked-but-not-yet-aired future placements; this dataset deliberately omits them to keep "snapshot cutoff" semantics clean.

Weekdays are typically higher than weekends. This trend chart is used for business health monitoring.

---

### Query 12: Quantifying Undelivered Opportunity Cost from Preemption

**Business context:**
The CFO needs to explain to the board "why the company is investing in ML prediction." The metric to quantify is not a real cash loss (preempted slots aren't billed per spec) but the **undelivered opportunity cost** — these impressions that were locked but never aired could have been converted into advertiser campaigns and platform revenue. If the average potential gross media buy per preempted slot is ~$1,600 and there are ~900 preemptions per month, that's ~$1.5M of unrealized GMV. Reducing preventable preemption by 30% through ML prediction recovers ~$450K of billable capacity per month — that's the basis of the ROI calculation.

**Category:** Aggregation + computation + financial analysis
**Difficulty:** Intermediate
**Business role:** Finance

**Approach:**

This query computes the undelivered opportunity cost from preemption for the CFO, aggregated by month. Only one table (`ad_placement`), filtered to `status='preempted'`, aggregated by month via `strftime('%Y-%m', scheduled_air_date)`. Think carefully about the opportunity cost caliber: preempted slots are not billed to customers, so this is not a real cash loss but rather "the gross media buy that would have been generated if the slots had aired normally," estimated as `booked_cpm * booked_impressions / 1000`. This is a deliberately different concept from "actual loss" — used to compute ROI for the ML investment: if the model can flag preventable preemptions in advance, some of this opportunity cost is recoverable. October's number will be especially large because Q4 booking uplift and NFL peak compound on top of each other.

```sql
-- Quantifying undelivered opportunity cost from preemption
-- Note: in CTV, preempted placements are typically not billed to the advertiser, so what's computed here is
-- "the gross media buy that would have been generated if the slot had aired normally" (opportunity cost), not real loss.
SELECT
    strftime('%Y-%m', a.scheduled_air_date) AS month,
    COUNT(*) AS preempted_count,
    ROUND(SUM(a.booked_cpm * a.booked_impressions / 1000), 2) AS undelivered_opportunity_cost_usd,
    ROUND(AVG(a.booked_cpm * a.booked_impressions / 1000), 2) AS avg_per_slot_opportunity_cost,
    SUM(a.booked_impressions) AS undelivered_impressions
FROM ad_placement a
WHERE a.status = 'preempted'
GROUP BY strftime('%Y-%m', a.scheduled_air_date)
ORDER BY month DESC;
```

**Expected result:**
The result set shows the undelivered opportunity cost from preemption by month:

| Month | Preempted Count | Undelivered Opportunity Cost | Avg per Slot |
|------|---------|---------------|---------|
| 2025-05 | ~884 | ~$1.45M | ~$1.6K |
| 2025-06 | ~853 | ~$1.37M | ~$1.6K |
| 2025-07 | ~921 | ~$1.48M | ~$1.6K |
| 2025-08 | ~876 | ~$1.43M | ~$1.6K |
| 2025-09 | ~1,081 | ~$1.84M | ~$1.7K (NFL kickoff worsening) |
| 2025-10 | **~2,783** | **~$4.55M** | ~$1.6K (Q4 +40% + NFL peak double hit) |

October alone has ~$4.5M in undelivered opportunity cost — this is the **core KPI for AutoML Booking Copilot ROI**. The CFO estimates from here: even if ML prediction reduces preventable preemption by 25% (a typical baseline → optimized model lift), October recovers ~$1.1M of billable capacity, and **a full-year rolling estimate is in the $8-10M range** — enough to support R&D investment in the AutoML platform and data science team.

---

### Query 13: User Action Audit (Top Active Users in Past 7 Days)

**Business context:**
The security team needs to monitor user activity on the platform to identify abnormal behavior. For example, if a user creates/cancels many placement bookings in a short time, they may be probing for system vulnerabilities or acting maliciously. This audit report lists the top users by action count in the past 7 days and their main action types. If something looks anomalous (a user executes 500 modify_booking calls in a day), it needs immediate investigation.

**Category:** Aggregation + sorting + date filter
**Difficulty:** Basic
**Business role:** Operations

**Approach:**

This query is the security audit perspective, finding the most active users in the last 7 days. Only the `user_action` table, aggregated by `user_name`. Besides total action count, conditional aggregation (SUM CASE) splits each user's book / modify / cancel / view_analytics counts into separate columns, so anomalous patterns (e.g., someone with a strangely high cancel ratio) are visible at a glance. Date filter uses `DATETIME('2025-10-31', '-7 days')` — note DATETIME instead of DATE here because action_timestamp is a timestamp with hours/minutes/seconds. Finally, sort by total action count descending and take the top 20. Structurally simple but operationally common.

```sql
-- Audit of the most active users in the past 7 days
SELECT
    ua.user_name AS user_name,
    COUNT(*) AS total_actions,
    SUM(CASE WHEN ua.action_type = 'book_placement' THEN 1 ELSE 0 END) AS book_actions,
    SUM(CASE WHEN ua.action_type = 'modify_booking' THEN 1 ELSE 0 END) AS modify_actions,
    SUM(CASE WHEN ua.action_type = 'cancel_booking' THEN 1 ELSE 0 END) AS cancel_actions,
    SUM(CASE WHEN ua.action_type = 'view_analytics' THEN 1 ELSE 0 END) AS view_analytics_actions,
    MAX(ua.action_timestamp) AS last_action_time
FROM user_action ua
-- Reference date: data snapshot cutoff '2025-10-31', looking back 7 days
WHERE ua.action_timestamp >= DATETIME('2025-10-31', '-7 days')
GROUP BY ua.user_name
ORDER BY total_actions DESC
LIMIT 20;
```

**Expected result:**
The result set shows the top 20 most active users. Under normal conditions, media buyers (e.g., sarah_chen) should have many book and view actions. If a user's cancel-action ratio is anomalously high (>50%), it needs investigation.

---

### Query 14: Model Version Iteration Effectiveness Comparison (Window Function)

**Business context:**
The CDO needs to show the CEO "whether the data science team's model iteration work has been valuable." They need a clean comparison table showing the accuracy lift of each model version over the previous version. If v2.3.1 only delivers 1% accuracy lift over v2.2.0, marginal returns are diminishing and R&D priorities may need to shift; if it lifts 5%, the investment is paying off. This analysis uses window functions to compute period-over-period growth and is a demonstration of advanced SQL skills.

**Category:** Window function + aggregation + comparison
**Difficulty:** Advanced
**Business role:** Executive

**Approach:**

This query uses window functions to compute version-to-version lift on model accuracy. First a CTE `model_performance` computes the clearance prediction accuracy per version (caliber aligned with Q2, locked to classifiers via `model_type='clearance_classifier'`). The outer query uses `LAG(accuracy) OVER (ORDER BY deployed_at, model_version)` to get the previous version's accuracy and subtracts to get the lift. Adding `model_version` as a secondary sort key in ORDER BY is a small detail: if two versions are deployed on the same day, this ensures LAG's result is stable and reproducible. Aggregation grain is "one version per row." The business conclusion here is counterintuitive: all three generations are essentially flat in accuracy because class imbalance has locked in the ceiling. The end of the query also includes a snippet that applies the same logic to the roas regressor (joining via `roas_model_version_id`), and that thread does show MAPE monotonically declining.

```sql
-- Model version iteration effectiveness comparison (with period-over-period lift)
WITH model_performance AS (
    SELECT
        mv.version_code AS model_version,
        mv.deployed_at AS deployed_at,
        COUNT(*) AS prediction_count,
        ROUND(AVG(CASE
            WHEN (p.predicted_clearance_prob >= 0.5 AND a.status = 'cleared') OR
                 (p.predicted_clearance_prob < 0.5 AND a.status = 'preempted')
            THEN 1.0 ELSE 0.0
        END), 4) AS clearance_prediction_accuracy
    FROM prediction_result p
    JOIN ad_placement a ON p.placement_id = a.id
    JOIN model_version mv ON p.model_version_id = mv.id
    WHERE a.status IN ('cleared', 'preempted')
      AND mv.model_type = 'clearance_classifier'
    GROUP BY mv.version_code, mv.deployed_at
)
SELECT
    model_version,
    deployed_at,
    prediction_count,
    clearance_prediction_accuracy,
    LAG(clearance_prediction_accuracy) OVER (ORDER BY deployed_at, model_version) AS prev_version_accuracy,
    ROUND(clearance_prediction_accuracy - LAG(clearance_prediction_accuracy) OVER (ORDER BY deployed_at, model_version), 4) AS accuracy_lift,
    ROUND((clearance_prediction_accuracy - LAG(clearance_prediction_accuracy) OVER (ORDER BY deployed_at, model_version)) /
          LAG(clearance_prediction_accuracy) OVER (ORDER BY deployed_at, model_version) * 100, 2) || '%' AS lift_percent
FROM model_performance
-- ORDER BY tiebreaker (model_version) ensures stable LAG output when multiple versions deploy the same day
ORDER BY deployed_at DESC, model_version DESC;
```

**Expected result:**
The result set shows that the binary clearance accuracy of all three versions is essentially flat (~86%): v2.1.5 ~86.0%, v2.2.0 ~85.8%, v2.3.1 ~85.6% (each version n ≈ 16,600). **This is a deliberately negative narrative** — at the 50K sample scale, noise smoothing makes the three versions' prediction distributions converge, but **class imbalance (85% cleared)** locks overall accuracy in at the majority-class baseline, and noise narrowing cannot break through.

**CDO recommendation:** Stop tuning hyperparameters on the clearance classifier — the next generation should:
1. Switch loss function (focal loss / class-weighted cross-entropy) to push the model harder on the preempted class
2. Apply oversampling (SMOTE) or undersampling to the training set
3. Bring in new features (real-time NFL schedule, weekly network programming structure, advertiser historical preemption rate)
4. Shift investment to the ROAS regression task (Q4 shows MAPE has dropped 12% → 5%, marginal returns are still available)

> **Shadow scoring note:** All three model versions are loaded simultaneously, and each placement is scored by a randomly chosen version. `model_version.deployed_at` is when that version became primary, but all versions do backtesting evaluation. This makes version comparisons rest on same-distribution data, avoiding the "old version only saw easy data, new version only saw hard data" confound. This **multi-version-live + same-distribution-backtesting** is exactly the key BI capability Vantage Media's AutoML platform uses to show customers "we're continuously evaluating every candidate model."

> **ROAS Regressor comparison:** This query only looks at the clearance classifier (joined via `p.model_version_id`).
> Every prediction also carries a paired **ROAS regressor**, recorded in `prediction_result.roas_model_version_id`
> (v2.1.5-roas/id4 → v2.2.0-roas/id5 → v2.3.1-roas/id6). To see the ROAS regression version iteration effect,
> attach the snippet below to performance_actual and compute MAPE per regressor version — you'll see a **monotonic decline of 12% → 8% → 5%**:
>
> ```sql
> SELECT mv.version_code,
>        ROUND(AVG(ABS(p.predicted_roas - pa.roas) / pa.roas) * 100, 2) AS roas_mape_pct
> FROM prediction_result p
> JOIN performance_actual pa ON p.placement_id = pa.placement_id
> JOIN model_version mv ON p.roas_model_version_id = mv.id   -- note: join on roas_model_version_id
> WHERE pa.roas > 0 AND mv.model_type = 'roas_regressor'
> GROUP BY mv.version_code ORDER BY mv.version_code;
> ```
>
> Marginal returns are still available on this thread, so the AutoML team should keep optimizing the ROAS model and pause clearance model iteration.

---

### Query 15: Campaign ROI Analysis (End-to-End CTE)

**Business context:**
The finance director needs to compute full ROI (return on investment) for each campaign. This requires aggregating actual spend and attributed revenue across all placements under the campaign, then computing ROI = (revenue - cost) / cost. If a campaign has negative ROI (cost > revenue), the campaign has failed and the cause needs to be investigated. This query uses CTEs to compute in layers — first aggregating at placement level, then at campaign level — which is a classic pattern for complex financial analysis.

**Category:** CTE + multi-table join + financial calculation
**Difficulty:** Advanced
**Business role:** Finance

**Approach:**

This is an end-to-end financial analysis, with CTEs splitting it into two layers. The CTE `campaign_spend` first aggregates each campaign's budget, booked placement count, actual spend, attributed revenue, and conversions to the campaign grain. The chain is campaign to advertiser, then LEFT JOIN ad_placement, then LEFT JOIN performance_actual. LEFT JOIN here is mandatory rather than INNER: some campaigns may have no placements at all, and some placements may be preempted and have no actual — INNER JOIN would drop those campaigns entirely and distort the denominator. Combine with `COALESCE(..., 0)` to fill NULL spend and revenue as 0. The outer query then computes ROI = (revenue - spend) / spend, ROAS, and budget remaining percentage, with all divisions wrapped in `NULLIF(..., 0)` to prevent divide-by-zero. The budget remaining percentage is a meaningful real range, because the generator back-derives budget from planned placement spend, so most campaigns land inside budget, with a few slightly over.

```sql
-- Campaign ROI end-to-end analysis
WITH campaign_spend AS (
    SELECT
        c.campaign_code,
        c.campaign_name,
        adv.advertiser_name,
        c.budget_usd AS budget,
        COUNT(DISTINCT a.id) AS placements_booked,
        SUM(CASE WHEN a.status = 'cleared' THEN 1 ELSE 0 END) AS actual_aired,
        SUM(COALESCE(pa.spend_usd, 0)) AS actual_spend,
        SUM(COALESCE(pa.attributed_revenue_usd, 0)) AS attributed_revenue,
        SUM(COALESCE(pa.attributed_conversions, 0)) AS total_conversions
    FROM campaign c
    JOIN advertiser adv ON c.advertiser_id = adv.id
    LEFT JOIN ad_placement a ON c.id = a.campaign_id
    LEFT JOIN performance_actual pa ON a.id = pa.placement_id
    GROUP BY c.campaign_code, c.campaign_name, adv.advertiser_name, c.budget_usd
)
SELECT
    campaign_code AS campaign_code,
    campaign_name AS campaign_name,
    advertiser_name AS advertiser,
    budget,
    placements_booked,
    actual_aired,
    ROUND(actual_spend, 2) AS actual_spend,
    ROUND(attributed_revenue, 2) AS attributed_revenue,
    total_conversions,
    ROUND((attributed_revenue - actual_spend) / NULLIF(actual_spend, 0), 2) AS ROI,
    ROUND(attributed_revenue / NULLIF(actual_spend, 0), 2) AS ROAS,
    ROUND((budget - actual_spend) / NULLIF(budget, 0) * 100, 1) || '%' AS budget_remaining_pct
FROM campaign_spend
WHERE actual_spend > 0
ORDER BY ROI DESC
LIMIT 20;
```

**Expected result:**
The result set shows ROI per campaign. Successful campaigns should have ROI of 0.2-0.8 (i.e., 20-80% return) and ROAS of 1.2-1.8x. Failed campaigns have negative ROI and require finance to engage with the customer.

**Budget remaining pct**: The data generator back-derives `budget_usd` from each campaign's planned placement spend (Σ booked_cpm×booked_impressions/1000) × uniform 0.9-1.4, so this column is a **meaningful real range**: average budget ~$226K, average actual spend ~$170K, **median budget remaining pct ~27%** (most campaigns within budget), range about -7% to +88%; a small fraction (~2%) slightly overspends due to higher-than-expected clearance (remaining < 0), corresponding to the ER `DQR-009 Campaign Budget Overrun` "occasional overrun alert" design intent. The finance team uses this to identify campaigns approaching or breaching budget.

> **Budget caliber:** `campaign.budget_usd` (mean ~$226K) is back-derived by placement volume, and placements are allocated by `advertiser.total_budget_usd` (§1.2 customer tier, mean ~$1.42M/year) weighted, so the sum of all campaign budgets per customer (6 months) is about half their annual budget magnitude (median ~0.53×), and a single campaign budget almost never exceeds the customer's annual budget — Q6/Q15/Q19 stay self-consistent when surfacing customer budget alongside spend.

---

### Query 16: Network Monthly Clearance Rate Trend (Time Series + Window Function)

**Business context:**
The data analyst needs to provide data support for the product team's "network clearance rate trend forecast" feature. They need to show each network's clearance rate trend over the past 6 months along with month-over-month change. If a network's clearance rate keeps declining (e.g., ESPN dropped from 75% in July to 58% in October), the risk on that network is rising and the ML model should adjust weights accordingly. This time-series analysis uses window functions for month-over-month change.

**Category:** Window function + date aggregation + trend analysis
**Difficulty:** Intermediate
**Business role:** Analyst

**Approach:**

This query does time-series trending, looking at each network's clearance rate by month with month-over-month change. First a CTE `monthly_clearance` aggregates clearance rate at the "network + month" grain (month from `strftime('%Y-%m', scheduled_air_date)`), again only counting resolved slots. The key piece is the window function `LAG(clearance_rate) OVER (PARTITION BY network ORDER BY month)`: PARTITION BY network keeps the month-over-month comparison within the same network (so ESPN's prior month isn't compared against HGTV); ORDER BY month decides what "previous" means. After getting last month's clearance rate, subtract to get the month-over-month change, then translate via CASE into improving / worsening / flat arrows. Aggregation grain is "one network one month per row." ESPN will clearly trend down in September and October (NFL), while HGTV is stable year-round.

```sql
-- Network monthly clearance rate trend (time series)
WITH monthly_clearance AS (
    SELECT
        n.network_name AS network,
        strftime('%Y-%m', a.scheduled_air_date) AS month,
        COUNT(*) AS bookings,
        SUM(CASE WHEN a.status = 'cleared' THEN 1 ELSE 0 END) AS cleared_count,
        ROUND(AVG(CASE WHEN a.status = 'cleared' THEN 1.0 ELSE 0.0 END), 4) AS clearance_rate
    FROM ad_placement a
    JOIN network n ON a.network_id = n.id
    WHERE a.status IN ('cleared', 'preempted')
    GROUP BY n.network_name, strftime('%Y-%m', a.scheduled_air_date)
)
SELECT
    network,
    month,
    bookings,
    cleared_count,
    clearance_rate,
    LAG(clearance_rate) OVER (PARTITION BY network ORDER BY month) AS prev_month_clearance_rate,
    ROUND(clearance_rate - LAG(clearance_rate) OVER (PARTITION BY network ORDER BY month), 4) AS mom_change,
    CASE
        WHEN clearance_rate > LAG(clearance_rate) OVER (PARTITION BY network ORDER BY month) THEN 'up improving'
        WHEN clearance_rate < LAG(clearance_rate) OVER (PARTITION BY network ORDER BY month) THEN 'down worsening'
        ELSE 'flat'
    END AS trend
FROM monthly_clearance
ORDER BY network, month DESC;
```

**Expected result:**
The result set shows clearance rate trend per network per month. ESPN should show a clear decline in September-October (start of NFL season), flagged as "down worsening." HGTV stays stable year-round, flagged as "flat."

---

### Query 17: P0 Data Quality Incident Mean Time to Resolve (MTTR)

**Business context:**
The data engineering director needs to report "data quality incident response speed" at the quarterly OKR review. The company target is to keep MTTR (Mean Time To Resolve) on P0 incidents (severe issues that block downstream) within 2 hours. They need to compute MTTR for all P0 incidents in the past 90 days, broken down by rule type. If a particular rule type (e.g., "attribution data latency check") consistently exceeds MTTR target, the response workflow or auto-remediation logic needs to be improved.

**Category:** Date math + aggregation + filter
**Difficulty:** Intermediate
**Business role:** Manager

**Approach:**

This query specifically computes MTTR for P0 (most severe) data quality incidents. Two tables: `data_quality_log` JOIN `data_quality_rule`, filtered to `severity='P0'` and `status IN ('failed','warning')` (passed has no resolution time concept). MTTR like Q5 uses `(JULIANDAY(resolved_at) - JULIANDAY(run_timestamp)) * 24` to convert to hours, with CASE only counting resolved records and excluding unresolved ones from the average. Besides AVG, MAX is also taken so the director can see whether the worst case is out of control. Aggregation grain is "one rule per row," so the slow check types can be pinpointed. Date window uses the fixed reference date looking back 90 days, covering the whole data window. Resolution rate should be close to 100%.

```sql
-- P0 data quality incident mean time to resolve (MTTR)
SELECT
    r.rule_name AS rule_name,
    r.severity AS severity,
    COUNT(*) AS incident_count,
    SUM(CASE WHEN l.resolved_at IS NOT NULL THEN 1 ELSE 0 END) AS resolved_count,
    ROUND(AVG(CASE
        WHEN l.resolved_at IS NOT NULL
        THEN (JULIANDAY(l.resolved_at) - JULIANDAY(l.run_timestamp)) * 24
        ELSE NULL
    END), 2) AS avg_resolution_hours,
    ROUND(MAX(CASE
        WHEN l.resolved_at IS NOT NULL
        THEN (JULIANDAY(l.resolved_at) - JULIANDAY(l.run_timestamp)) * 24
        ELSE NULL
    END), 2) AS max_resolution_hours,
    ROUND(AVG(CASE WHEN l.resolved_at IS NOT NULL THEN 1.0 ELSE 0.0 END), 4) AS resolution_rate
FROM data_quality_log l
JOIN data_quality_rule r ON l.rule_id = r.id
WHERE r.severity = 'P0'
  AND l.status IN ('failed', 'warning')
  -- Reference date: data snapshot cutoff '2025-10-31', looking back 90 days covers the whole data window
  AND l.run_timestamp >= DATETIME('2025-10-31', '-90 days')
GROUP BY r.rule_name, r.severity
ORDER BY avg_resolution_hours DESC;
```

**Expected result:**
The result set shows MTTR per P0 rule. Most P0 incidents should resolve within 1-2 hours. If MTTR for a rule exceeds 4 hours, the engineering director needs to step in to optimize the workflow. Resolution rate should be close to 100%.

---

### Query 18: Clearance Prediction Distribution Histogram

**Business context:**
The product manager needs to show a "clearance prediction distribution" chart in the UI to help users understand "what range most placements' clearance probability concentrate in." For example, if 60% of placements have predicted clearance probability between 0.8-1.0 (high reliability), the platform is choosing high-quality inventory; if 30% are in the 0.4-0.6 range (high-risk zone), the selection strategy needs improvement. This query produces the data source for the histogram, aggregated by probability bucket.

**Category:** Aggregation + CASE bucketing
**Difficulty:** Intermediate
**Business role:** Analyst

**Approach:**

This query gives the product manager a histogram of predicted clearance probability. `prediction_result` JOIN `ad_placement`, with CASE bucketing `predicted_clearance_prob` into 5 probability buckets (extreme high risk through extreme low risk). Like Q9, the bucketing CASE has to be written twice — once in SELECT and once in GROUP BY. The highlight is using a window function for the percentage: `COUNT(*) * 100.0 / SUM(COUNT(*)) OVER ()`. Here `SUM(COUNT(*)) OVER ()` is the "aggregate-over-window" pattern — first GROUP BY computes each bucket's count (COUNT(*)), then an empty window OVER () sums all buckets as the denominator, computing each bucket's share of the whole in one step without needing a subquery. Only counts resolved slots, and sorts by the lower bound of the probability bucket.

```sql
-- Clearance prediction distribution histogram data
SELECT
    CASE
        WHEN p.predicted_clearance_prob < 0.2 THEN '0.0-0.2 (extreme high risk)'
        WHEN p.predicted_clearance_prob < 0.4 THEN '0.2-0.4 (high risk)'
        WHEN p.predicted_clearance_prob < 0.6 THEN '0.4-0.6 (medium risk)'
        WHEN p.predicted_clearance_prob < 0.8 THEN '0.6-0.8 (low risk)'
        ELSE '0.8-1.0 (extreme low risk)'
    END AS clearance_prob_bucket,
    COUNT(*) AS placements,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) AS share_pct,
    ROUND(AVG(p.predicted_roas), 2) AS avg_predicted_roas,
    SUM(CASE WHEN a.status = 'cleared' THEN 1 ELSE 0 END) AS actual_cleared_count,
    ROUND(AVG(CASE WHEN a.status = 'cleared' THEN 1.0 ELSE 0.0 END), 4) AS actual_clearance_rate
FROM prediction_result p
JOIN ad_placement a ON p.placement_id = a.id
WHERE a.status IN ('cleared', 'preempted')
GROUP BY
    CASE
        WHEN p.predicted_clearance_prob < 0.2 THEN '0.0-0.2 (extreme high risk)'
        WHEN p.predicted_clearance_prob < 0.4 THEN '0.2-0.4 (high risk)'
        WHEN p.predicted_clearance_prob < 0.6 THEN '0.4-0.6 (medium risk)'
        WHEN p.predicted_clearance_prob < 0.8 THEN '0.6-0.8 (low risk)'
        ELSE '0.8-1.0 (extreme low risk)'
    END
ORDER BY MIN(p.predicted_clearance_prob) ASC;
```

**Expected result:**
The result set shows placement distribution across 5 clearance probability buckets (n ≈ 49,748 cleared+preempted):

| Bucket | Count | Share |
|------|-----|------|
| 0.0-0.2 (extreme high risk) | 0 | 0% (this dataset's model_noise constraint doesn't produce extreme values) |
| 0.2-0.4 (high risk) | ~710 | ~1.4% |
| 0.4-0.6 (medium risk) | ~2,200 | ~4.4% |
| 0.6-0.8 (low risk) | ~9,990 | ~20.1% |
| 0.8-1.0 (extreme low risk) | **~36,840** | **~74.1%** |

This distribution gives the product manager a clear signal: **~74% of bookings are low risk**, meaning Vantage Media's recommendation engine has already filtered most high-risk slots out for the buyer; what actually needs ML intervention in decisions is about 12,900 (~26%) medium-and-low-risk slots. This is also why Booking Copilot **only highlights slots with clearance rate < 0.65 as warnings in the UI** (see Q3).

---

### Query 19: Advertiser Name Fuzzy Search

**Business context:**
The customer success team needs to quickly look up advertiser information in the CRM system. Because advertiser names may have multiple spellings or abbreviations (e.g., "Luminary Health" vs "Luminary" vs "LumHealth"), the team needs fuzzy search. The user inputs a partial keyword (e.g., "Lum"), and the system returns all matching advertisers and their basic information. This is a simple LIKE query, but extremely common in real business use.

**Category:** Text matching + join
**Difficulty:** Basic
**Business role:** Operations

**Approach:**

This is a fuzzy search feature commonly seen in CRM. The main table advertiser connects to category for industry, then LEFT JOIN campaign and ad_placement to count this customer's campaigns and placements. LEFT JOIN is used so that even customers with no campaigns yet still appear in the search results (with campaign count and placement count showing 0), rather than being filtered out by an INNER JOIN. Fuzzy matching uses `WHERE advertiser_name LIKE '%Health%'`, where the percent signs are wildcards — in actual use replace with the user's keyword. Because one customer connects to many campaigns and many placements producing row fanout, counting campaigns and placements must use `COUNT(DISTINCT c.id)` and `COUNT(DISTINCT a.id)` to dedupe, otherwise the count is inflated by the JOIN.

```sql
-- Advertiser name fuzzy search
SELECT
    adv.advertiser_code AS advertiser_code,
    adv.advertiser_name AS advertiser_name,
    ac.category_name AS industry_category,
    adv.total_budget_usd AS total_budget,
    DATE(adv.onboarded_at) AS onboarded_date,
    COUNT(DISTINCT c.id) AS campaign_count,
    COUNT(DISTINCT a.id) AS placement_count
FROM advertiser adv
JOIN advertiser_category ac ON adv.category_id = ac.id
LEFT JOIN campaign c ON adv.id = c.advertiser_id
LEFT JOIN ad_placement a ON adv.id = a.advertiser_id
WHERE adv.advertiser_name LIKE '%Health%'  -- replace with the actual search keyword
GROUP BY adv.advertiser_code, adv.advertiser_name, ac.category_name,
         adv.total_budget_usd, adv.onboarded_at
ORDER BY adv.advertiser_name ASC;
```

**Expected result:**
The result set returns all advertisers whose name contains "Health", along with their campaign count and placement count. The customer success manager can quickly locate the target customer.

---

### Query 20: Cross Network-Type ROAS Comparison (Subquery)

**Business context:**
The CEO needs to answer at the strategic planning meeting: "Should we focus on linear TV or streaming platforms?" This requires comparing ROAS performance across network types (linear cable, linear broadcast, streaming). If streaming's average ROAS is 30% higher than linear TV, the company should invest more in streaming. This query uses subqueries to compute ROAS per network type and compare side by side — an important basis for executive decision-making.

**Category:** Subquery + aggregation + comparison
**Difficulty:** Advanced
**Business role:** Executive

**Approach:**

This query answers the CEO's "linear TV or streaming?" question. Use two CTEs: `network_type_performance` computes spend, revenue, and overall ROAS per network type (linear_cable / linear_broadcast / streaming_avod); `platform_total` computes the platform-wide overall ROAS as the baseline. Chain is ad_placement to network for type, to performance_actual for spend/revenue. Again emphasize the two ROAS calibers: average ROAS (AVG) is sensitive to small orders, while overall ROAS (SUM revenue / SUM spend) is the spend-weighted true return — strategic decisions use the latter. The final column "relative to platform" uses each type's overall ROAS compared against the spend-weighted platform overall ROAS (pulled via subquery), not against the arithmetic mean of the three type overall ROAS values — this baseline choice directly affects the conclusion and is the easiest thing to get wrong in this query.

```sql
-- Cross network-type ROAS comparison
-- Design notes:
-- 1) "Average ROAS" is the row-level mean(roas), biased by small orders
-- 2) "Overall ROAS" = SUM(revenue) / SUM(spend) is spend-weighted, the true return the CFO cares about
-- 3) "Relative to platform" uses the *spend-weighted platform overall ROAS* as the baseline
--    (not the arithmetic mean of the 3 network types' overall ROAS)
WITH network_type_performance AS (
    SELECT
        n.network_type AS network_type,
        COUNT(DISTINCT a.id) AS placement_count,
        SUM(pa.spend_usd) AS total_spend,
        SUM(pa.attributed_revenue_usd) AS total_revenue,
        SUM(pa.attributed_conversions) AS total_conversions,
        ROUND(AVG(pa.roas), 2) AS avg_roas,
        ROUND(SUM(pa.attributed_revenue_usd) / NULLIF(SUM(pa.spend_usd), 0), 2) AS overall_roas
    FROM ad_placement a
    JOIN network n ON a.network_id = n.id
    JOIN performance_actual pa ON a.id = pa.placement_id
    GROUP BY n.network_type
),
platform_total AS (
    SELECT
        SUM(pa.attributed_revenue_usd) / NULLIF(SUM(pa.spend_usd), 0) AS platform_overall_roas
    FROM performance_actual pa
)
SELECT
    network_type,
    placement_count,
    ROUND(total_spend, 2) AS total_spend_usd,
    ROUND(total_revenue, 2) AS total_revenue_usd,
    total_conversions,
    avg_roas,
    overall_roas,
    ROUND((overall_roas - (SELECT platform_overall_roas FROM platform_total)) /
          (SELECT platform_overall_roas FROM platform_total) * 100, 2) || '%' AS relative_to_platform
FROM network_type_performance
ORDER BY overall_roas DESC;
```

**Expected result:**
The result set compares the three network types. streaming_avod's overall ROAS should land in 1.5-1.7x, 20-30% higher than linear_cable's 1.2-1.4x. The CEO can use this to set strategic priorities.

---

## 4. Query Category Summary

Note: a query can belong to multiple categories (e.g., Q16 uses both window functions and CTEs); the "Count" column below tallies by primary category.

| Category | Count | Query numbers |
|------|------|----------|
| Aggregation queries | 5 | 1, 5, 6, 11, 13 |
| Join operations | 5 | 3, 4, 8, 10, 19 |
| Window functions | 3 | 14, 16, 18 |
| Date/time analysis | 3 | 7, 9, 17 |
| Subquery/CTE | 6 | 2, 7, 14, 15, 16, 20 |
| Text matching | 1 | 19 |
| Computed fields (derived metrics) | 6 | 4, 9, 11, 12, 15, 20 |

## 5. Business Role Coverage

Each query is assigned to one primary role; Q18's primary role is Analyst (used by product/data teams), and the Manager view is in Q3.

| Role | Count | Query numbers |
|------|------|----------|
| Executive / C-Level | 3 | 6, 14, 20 |
| Manager | 4 | 3, 7, 11, 17 |
| Analyst | 6 | 2, 4, 8, 9, 16, 18 |
| Operations | 5 | 1, 5, 10, 13, 19 |
| Finance | 2 | 12, 15 |

## 6. Difficulty Distribution

| Difficulty | Count | Query numbers |
|------|------|----------|
| Basic | 7 | 1, 3, 5, 6, 11, 13, 19 |
| Intermediate | 10 | 2, 4, 7, 8, 9, 10, 12, 16, 17, 18 |
| Advanced | 3 | 14, 15, 20 |

---

## 7. Query to Business Problem Mapping

Every query traces back to the core business problems listed in §5 of the business context document. The four business problems plus the AutoML model monitoring product line collectively cover all 20 queries.

| Business Problem | Queries |
|----------|----------|
| Media buying blind spot (clearance / preemption / opportunity cost) | Q1, Q3, Q7, Q9, Q11, Q12, Q16 |
| Customer variance (ROAS by customer / category / network) | Q4, Q6, Q15, Q19, Q20 |
| Attribution puzzle (systematic bias in attribution method) | Q8 |
| Data quality black holes (DQ alerts / SLA / MTTR / audit) | Q5, Q10, Q13, Q17 |
| AutoML model monitoring (product line) | Q2, Q14, Q18 |

---

## 8. Notes

- All queries are written in SQLite 3.x syntax
- Queries can be lightly adapted for other databases (PostgreSQL, MySQL, Snowflake)
- The numbers in TSV file names indicate table load order (topological)
- It is recommended to run the "data integrity verification" queries in the ER document before analysis
- Date functions use SQLite's `DATE()`, `DATETIME()`, `strftime()` syntax

---

**Document version:** 2.1 (0.2.1 spec restructure: added "How to use this document" intro + an "Approach" section for each query + business problem mapping table; SQL logic unchanged)
**Generation date:** 2026-06-22
**Applies to dataset:** advertising_ctv_campaign_analytics_high (Vantage Media · Booking Copilot)
**Total queries:** 20
**Core ML use cases:** Clearance Prediction (binary classification) + ROAS Prediction (regression)
**Shadow Scoring:** 3 model generations live concurrently (clearance classifier + paired ROAS regressor), n ≈ 16,600 per generation
