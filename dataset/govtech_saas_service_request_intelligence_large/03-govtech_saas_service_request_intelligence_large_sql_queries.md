# CityPulse 311 Dataset SQL Query Handbook

This document contains the 20 SQL queries that accompany the `govtech_saas_service_request_intelligence_large` dataset. Business background is in `govtech_saas_service_request_intelligence_large_business_context.md`; table structures and field definitions are in `govtech_saas_service_request_intelligence_large_er_document.md`.

Every query uses the literal date `'2026-06-01'` as "today" (`REFERENCE_DATE`). `DATE('now')` is not allowed, so results are reproducible. Every query runs directly against the SQLite database produced by the generator.

## 1. How to Use This Document

You are an intern who just joined the CityPulse analytics group. Director of Analytics Tom Brennan has handed you these 20 queries and told you to work through them this week - this is both onboarding and material gathering for the Q3 QBR (Quarterly Business Review).

Each query follows a fixed five-section template, in this order:

1. *Business context*: who's asking, why they're asking, and which decision the answer feeds into. If you don't understand this part, the SQL output won't mean anything.
2. *Tags*: category, difficulty, business role. Three short tags so you can filter by topic or by role.
3. *Approach*: before reading the SQL, think clearly about which tables you need, how to join them, what the aggregation grain is, and why a CTE is preferred over a subquery. This is the most important section in the document.
4. *SQL*: directly runnable SQLite code.
5. *Expected results and business takeaway*: what you should see after running, what range counts as normal, and what to do next once you have the result.

Each query maps back to one of the five business questions from the business context document (Q1 Other classification drift, Q2 stated-severity text divergence, Q3 first-touch quick close masking, Q4 escalation language predicting complaints, Q5 tenant-level model accuracy) or falls into the "operational routine" bucket; a mapping table is at the end.

---

## 2. Query Index

| # | Title | Business Role | SQL Category | Difficulty |
|------|------|----------|----------|------|
| Q1 | Requests classified as Other but containing strong keywords, and the SLA impact | Senior Analyst | Pattern + Aggregation | Intermediate |
| Q2 | Reopen rate of requests where stated severity contradicts emergency keywords | Senior Analyst | Pattern + Aggregation | Intermediate |
| Q3 | Identifying requests closed within 24 hours but with same-address recurrence within 30 days | Director of Analytics | Window Function | Advanced |
| Q4 | The predictive power of escalation language on council complaints | VP of Customer Success | Pattern + Subquery | Intermediate |
| Q5 | Per-tenant classifier accuracy linked to SLA | CDO | Aggregation + Join | Intermediate |
| Q6 | SLA performance comparison: Other routed to general queue | Senior Analyst | Aggregation + Join | Basic |
| Q7 | Monthly request volume and channel mix trends | Senior Analyst | Aggregation + Date | Basic |
| Q8 | Top 20 tenants with the worst SLA breach rate | VP of Customer Success | Aggregation + Join | Basic |
| Q9 | Severity-selection accuracy comparison across channels | Director of Data Science | Aggregation + Pattern | Intermediate |
| Q10 | ARR by city size and AI Insight Pack penetration | CRO | Aggregation + Join | Basic |
| Q11 | Model accuracy stratified by vocab_drift_level | CDO | Aggregation + RANK | Intermediate |
| Q12 | True "on-time resolution rate" recomputed after subtracting 30-day recurrence | Director of Analytics | CTE + Join | Advanced |
| Q13 | Council complaint escalation channel breakdown for escalation-language requests | VP of Customer Success | Pattern + EXISTS | Intermediate |
| Q14 | Reopen timing distribution and cohort analysis | Senior Analyst | Date + Aggregation | Intermediate |
| Q15 | Top 10 by category_group request volume | Senior Analyst | Aggregation + Join | Basic |
| Q16 | Estimated total SLA loss from Other misroutes (by tenant) | CDO | CTE + Pattern | Advanced |
| Q17 | Drop in classifier accuracy for French vocab tenants | Director of Data Science | CTE + Join | Intermediate |
| Q18 | Top staff users by throughput and SLA performance | Senior Analyst | Subquery + Join | Intermediate |
| Q19 | Categories with the highest reopen rates | Senior Analyst | Window + Aggregation | Intermediate |
| Q20 | 12 core metrics tenant health dashboard | CEO (submitted by Senior Analyst) | Aggregation | Basic |

---

## 3. Q1 Requests classified as Other but containing strong keywords, and the SLA impact

Business context:

Your direct manager Tom Brennan put this as your first onboarding question. CDO Marcus Chen has long suspected that the classifier is being too "conservative" with the Other category: the model falls everything back to Other whenever confidence is low, and Other always routes to the `is_general_queue = 1` department on every tenant. That department's SLA target is usually 5 business days, much slower than the 1 to 2 days for specialized departments. If a meaningful portion of the Other bucket actually belongs to one of six top-level categories (pothole, streetlight, illegal_dumping, graffiti, noise_complaint, tree), then those requests are being "misrouted" onto the slow track, and poor SLA performance is inevitable. Tom wants you to size the magnitude first, then decide whether to write a memo to Marcus about adjusting the model confidence threshold.

This corresponds to business question 1 (Other classification drift). What you expect to see: the strong-keyword subset of Other accounts for about 12% of total Other volume; that subset's SLA breach rate is materially higher than non-Other's, creating about an ~8pp gap (Other ~0.29 vs. non-Other ~0.21).

Tags: Pattern Matching, Aggregation, Intermediate, Senior Analyst.

Approach:

This question compares "Other category" against "non-Other category" SLA breach rates, then further splits the Other bucket into "description contains strong keywords" and "doesn't." The core tables are `service_requests` plus `request_descriptions` plus `service_categories` (to get the `is_other` flag), then LEFT JOIN `sla_breach_log` to detect breaches (note it must be LEFT JOIN because sla_breach_log only contains breached requests; an INNER JOIN would drop non-breached requests and break the denominator). The aggregation grain is a 2x2 table over (Other or not, has strong keyword or not). Keyword search uses `LOWER(...) LIKE` for case insensitivity.

```sql
WITH labeled AS (
    SELECT
        sr.request_id,
        sc.is_other,
        CASE
            WHEN LOWER(rd.description_text) LIKE '%pothole%'
              OR LOWER(rd.description_text) LIKE '%hole in road%'
              OR LOWER(rd.description_text) LIKE '%streetlight%'
              OR LOWER(rd.description_text) LIKE '%street light%'
              OR LOWER(rd.description_text) LIKE '%graffiti%'
              OR LOWER(rd.description_text) LIKE '%illegal dumping%'
              OR LOWER(rd.description_text) LIKE '%dumped%'
              OR LOWER(rd.description_text) LIKE '%noise%'
              OR LOWER(rd.description_text) LIKE '%tree limb%'
              OR LOWER(rd.description_text) LIKE '%fallen tree%'
            THEN 1 ELSE 0
        END AS has_strong_keyword,
        CASE WHEN sbl.breach_id IS NOT NULL THEN 1 ELSE 0 END AS is_breach
    FROM service_requests sr
    JOIN service_categories sc ON sc.category_id = sr.auto_category_id
    JOIN request_descriptions rd ON rd.request_id = sr.request_id
    LEFT JOIN sla_breach_log sbl ON sbl.request_id = sr.request_id
    WHERE sr.created_at >= '2025-06-01'
      AND sr.created_at < '2026-06-01'
      AND sr.closed_at IS NOT NULL
)
SELECT
    is_other,
    has_strong_keyword,
    COUNT(*) AS request_count,
    SUM(is_breach) AS breach_count,
    ROUND(1.0 * SUM(is_breach) / COUNT(*), 3) AS sla_breach_rate
FROM labeled
GROUP BY is_other, has_strong_keyword
ORDER BY is_other, has_strong_keyword;
```

Expected results and business takeaway:

4 rows (counts below are for the trailing 12-month window `created_at >= '2025-06-01'`, about 1/3 of the full 36 months; measured values in parentheses). `(is_other=0, has_strong_keyword=0)` is the largest block, about 190K closed requests (measured 191,223), breach rate around 0.21. `(is_other=0, has_strong_keyword=1)` is about 110K (measured 111,144; these are correctly classified regular requests whose descriptions happen to contain strong keywords, e.g. actual pothole reports as Streets requests), breach rate similar to above (around 0.21). `(is_other=1, has_strong_keyword=0)` is about 23K (measured 22,955, the truly unclassifiable Other), breach rate around 0.29 (the Other channel is just slower). `(is_other=1, has_strong_keyword=1)` is the critical block, about 3,100 (measured 3,100), breach rate around 0.29, about 8pp above non-Other.

What this tells Tom: `auto_category = Other` is about 26K in the window (about 80K across the full 36 months, around 8% of total). About 12% of that (about 3,000 in the window, about 9,600 across the full set) is requests the model could have classified correctly but missed (descriptions explicitly contain strong keywords). Those requests get routed to the slow channel and drag down overall SLA. Next step: write a one-page memo to Marcus and Priya recommending lowering the NLP model's fallback threshold from 0.45 to 0.35, and checking whether the six top-level categories' token vocabularies cover the common misspellings from IVR transcription.

---

## 4. Q2 Reopen rate of requests where stated severity contradicts emergency keywords

Business context:

Tom asks you to follow up Q1 by looking in the severity direction. CityPulse asks residents to pick one of four severity levels at submission - Low / Medium / High / Emergency - but residents' judgment of severity often runs counter to instinct: truly urgent things (a gas smell at home, a downed power line, a child bitten by a stray dog) sometimes get tagged "Medium" because they "don't feel like an emergency"; conversely, minor things (loud music next door at night) get tagged "High" because the resident is fed up. This bias is invisible to the structured fields, but the emergency keywords in the text (gas leak, live wire, fire, smoke, child injured, leaking) expose it. We look at requests where stated_severity is Low / Medium but the description contains an emergency keyword and check whether their reopen rate is materially higher than baseline, because these "miscatergorized to the normal queue" requests often still have the underlying issue after field treatment.

This corresponds to business question 2. What you expect to see: the emergency-keyword subset has a reopen rate around 24%, baseline around 5%, lift of about 5x. (The generator sets that subset's reopen probability to 0.25; with the 'leaking' contamination removed from normal templates, the emergency-keyword hits are a clean injected subset and the measured value stays stable around 0.24.)

Tags: Pattern Matching, Aggregation, Intermediate, Senior Analyst.

Approach:

Reopen detection uses the `request_events` table to check whether an event_type = 'reopened' exists. One way is EXISTS subquery; another is LEFT JOIN then COUNT. LEFT JOIN here is both more readable and faster. Restrict the SRs to stated_severity in ('low', 'medium'), then split into two groups by "description contains emergency keyword," and compute reopen rate for each. Make sure the time window leaves room for reopens to happen; here we use closed requests over the past 12 months (2025-06-01 to 2026-06-01).

```sql
WITH base AS (
    SELECT
        sr.request_id,
        sr.stated_severity,
        CASE
            WHEN LOWER(rd.description_text) LIKE '%gas leak%'
              OR LOWER(rd.description_text) LIKE '%live wire%'
              OR LOWER(rd.description_text) LIKE '%fire%'
              OR LOWER(rd.description_text) LIKE '%smoke%'
              OR LOWER(rd.description_text) LIKE '%child injured%'
              OR LOWER(rd.description_text) LIKE '%kid hurt%'
              OR LOWER(rd.description_text) LIKE '%leaking%'
            THEN 1 ELSE 0
        END AS has_emergency_keyword
    FROM service_requests sr
    JOIN request_descriptions rd ON rd.request_id = sr.request_id
    WHERE sr.stated_severity IN ('low', 'medium')
      AND sr.created_at >= '2025-06-01'
      AND sr.created_at < '2026-06-01'
      AND sr.closed_at IS NOT NULL
),
reopens AS (
    SELECT DISTINCT request_id
    FROM request_events
    WHERE event_type = 'reopened'
      AND event_at >= '2025-06-01'
      AND event_at < '2026-07-01'
)
SELECT
    b.has_emergency_keyword,
    COUNT(*) AS closed_request_count,
    SUM(CASE WHEN r.request_id IS NOT NULL THEN 1 ELSE 0 END) AS reopened_count,
    ROUND(
        1.0 * SUM(CASE WHEN r.request_id IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*),
        3
    ) AS reopen_rate
FROM base b
LEFT JOIN reopens r ON r.request_id = b.request_id
GROUP BY b.has_emergency_keyword
ORDER BY b.has_emergency_keyword;
```

Expected results and business takeaway:

2 rows (trailing 12 months, low/med subset). `has_emergency_keyword = 0` is about 220K rows (measured 221,974), reopen rate around 0.05 (measured 0.048). `has_emergency_keyword = 1` is about 24K rows (measured 24,280), reopen rate around 0.24 (measured 0.241). Lift around 5x. (Across the full 36 months, the corresponding row counts are roughly 670K / 75K.)

These ~24K requests are the single most compelling group when CityPulse tells customers the "AI Insight Pack value story": they're the misrouted urgent requests the model alone can identify but currently doesn't, and the platform could theoretically use text to elevate their priority earlier, reducing reopens and downstream escalations. Next step: take this lift number into the QBR deck on page 3, paired with a product recommendation - "run an emergency-keyword scan on description at intake, and auto-prompt supervisor to re-assess severity."

---

## 5. Q3 Identifying requests closed within 24 hours but with same-address recurrence within 30 days

Business context:

Tom leaves this for day three because it's the most technically challenging question, but also the one the CityPulse team cares about most. VP of Field Operations Practice (a vertical group inside Customer Success) Andrea Chu mentioned at the last customer retro that a 311 director at a customer city had complained: "Your SLA numbers look great, but the trash report near my house comes back every three months while your reports say 95% resolved on time." Tom suspects the field crew's "first touch close" KPI is driving the behavior: crews close out tickets fast on site to hit KPI, but the problem isn't really fixed, and the resident files a slightly different report within 30 days.

This corresponds to business question 3. What you expect to see: about 28% of requests closed within 24 hours and meeting SLA have a same-address recurrence within 30 days, vs. about 20% for non-quick-close requests, putting the quick-close group about 8pp above the non-quick-close. (The absolute level is high because 36 months and 1M requests concentrated on 150K addresses means random clustering alone contributes about a 20% same-address 30-day collision baseline; the trap's observable signal is the ~8pp the quick-close group sits above baseline.)

Tags: Window Function, Advanced, Director of Analytics.

Approach:

The core of this question is "another new request at the same address within 30 days." Same-address detection uses address_id equality, and we require the next request to have a different request_id and not be in a duplicate relationship. The window function `LEAD` can return the next request's time when ordered by (address_id, created_at), but only matters when there is a next row in the same address partition, so use `PARTITION BY address_id ORDER BY created_at`. Note address_id may be NULL (anonymous addresses or walk-ins that didn't record an address); exclude those rows or NULL values will incorrectly group together. The "closed within 24 hours" check uses `julianday(closed_at) - julianday(created_at) <= 1.0`.

```sql
WITH base AS (
    SELECT
        sr.request_id,
        sr.address_id,
        sr.created_at,
        sr.closed_at,
        CASE
            WHEN sr.closed_at IS NOT NULL
             AND julianday(sr.closed_at) - julianday(sr.created_at) <= 1.0
            THEN 1 ELSE 0
        END AS is_quick_close,
        CASE WHEN sbl.breach_id IS NULL THEN 1 ELSE 0 END AS is_on_time
    FROM service_requests sr
    LEFT JOIN sla_breach_log sbl ON sbl.request_id = sr.request_id
    WHERE sr.address_id IS NOT NULL
      AND sr.is_duplicate = 0
      AND sr.closed_at IS NOT NULL
      AND sr.created_at >= '2025-06-01'
      AND sr.created_at < '2026-05-01'
),
with_next AS (
    SELECT
        request_id,
        address_id,
        created_at,
        closed_at,
        is_quick_close,
        is_on_time,
        LEAD(created_at) OVER (
            PARTITION BY address_id
            ORDER BY created_at
        ) AS next_request_at_same_address
    FROM base
)
SELECT
    is_quick_close,
    COUNT(*) AS closed_on_time_count,
    SUM(
        CASE
            WHEN next_request_at_same_address IS NOT NULL
             AND julianday(next_request_at_same_address) - julianday(closed_at) <= 30
            THEN 1 ELSE 0
        END
    ) AS repeat_within_30d,
    ROUND(
        1.0 * SUM(
            CASE
                WHEN next_request_at_same_address IS NOT NULL
                 AND julianday(next_request_at_same_address) - julianday(closed_at) <= 30
                THEN 1 ELSE 0
            END
        ) / COUNT(*),
        3
    ) AS repeat_at_address_rate
FROM with_next
WHERE is_on_time = 1
GROUP BY is_quick_close
ORDER BY is_quick_close;
```

Expected results and business takeaway:

2 rows (11-month window where `created_at` in ['2025-06-01','2026-05-01'), address non-null, is_duplicate=0, on-time). `is_quick_close = 0` is about 116K (measured 116,223), repeat_at_address_rate around 0.22. `is_quick_close = 1` is about 108K (measured 107,873), repeat_at_address_rate around 0.30. The absolute level is high (because 1M requests concentrated on 150K addresses naturally produces ~22% same-address 30-day collisions), but the quick-close group sits about 8.1pp above the non-quick-close group (0.302 vs. 0.221) - that's the trap's observable signal. (Note: after the fix, all quick-closed requests are on-time, so the two group sizes are close.)

This is the "hidden failure rate" Tom is looking for. Next step: Tom asks you to hardcode this query into a "shadow SLA" metric and send Rachel Wong a weekly top-10 worst tenants list, so she can talk to those cities' 311 directors and adjust the crew KPI design (e.g. change "first touch close" into "first touch close without 30-day recurrence"). This number also shows up in the QBR deck on page 5 as the argument for "a new metric the product should provide to customers."

---

## 6. Q4 The predictive power of escalation language on council complaints

Business context:

VP of Customer Success Rachel Wong asked Marcus a specific question this week: "Do we have an early signal that flags a request before the resident escalates to city council, so my CSM team can step in inside the customer city proactively?" Marcus handed the question to you. Your hypothesis is that residents typically leave breadcrumbs in their 311 descriptions before they escalate: phrases like "third time this month," "fed up," "going to the news," "I will contact my councilman," or "lawyer" are themselves pre-escalation signals. The question is how much lift this text feature produces against final council escalation, and whether it justifies the product team adding a text-scan layer at intake.

This corresponds to business question 4. What you expect to see: requests with escalation language have about an 8% probability of council escalation within 60 days, vs. about 0.3% for those without - lift of about 25x.

Tags: Pattern Matching, Subquery (EXISTS), Intermediate, VP of Customer Success.

Approach:

Escalation detection uses an EXISTS check on the `citizen_complaints` table for a record referencing this request_id, with `filed_at` within 60 days of `service_requests.created_at`. EXISTS subquery is the most natural form here and more efficient than LEFT JOIN + DISTINCT. Text scan uses LOWER LIKE across 5 escalation phrases. The output is 2 rows, but the business value lies in the lift multiple.

```sql
SELECT
    has_escalation_phrase,
    COUNT(*) AS request_count,
    SUM(escalated_within_60d) AS escalated_count,
    ROUND(1.0 * SUM(escalated_within_60d) / COUNT(*), 4) AS council_escalation_rate
FROM (
    SELECT
        sr.request_id,
        CASE
            WHEN LOWER(rd.description_text) LIKE '%third time%'
              OR LOWER(rd.description_text) LIKE '%fed up%'
              OR LOWER(rd.description_text) LIKE '%contact my councilman%'
              OR LOWER(rd.description_text) LIKE '%going to the news%'
              OR LOWER(rd.description_text) LIKE '%get a lawyer%'
              OR LOWER(rd.description_text) LIKE '%my lawyer%'
            THEN 1 ELSE 0
        END AS has_escalation_phrase,
        CASE
            WHEN EXISTS (
                SELECT 1 FROM citizen_complaints cc
                WHERE cc.primary_request_id = sr.request_id
                  AND julianday(cc.filed_at) - julianday(sr.created_at) <= 60
            ) THEN 1 ELSE 0
        END AS escalated_within_60d
    FROM service_requests sr
    JOIN request_descriptions rd ON rd.request_id = sr.request_id
    WHERE sr.created_at >= '2025-06-01'
      AND sr.created_at < '2026-04-01'
) t
GROUP BY has_escalation_phrase
ORDER BY has_escalation_phrase;
```

Expected results and business takeaway:

2 rows (10-month window where `created_at` in ['2025-06-01','2026-04-01')). `has_escalation_phrase = 0` is about 270K rows, escalation rate around 0.003 (0.3%). `has_escalation_phrase = 1` is about 8,000 rows, escalation rate around 0.08 (8%). Lift around 25x; no need to run Fisher exact - the result is significant either way. (Across the full 36 months, the row counts are roughly 800K / 24K.)

Next step: this lift is the core data Rachel needs to tell the customer story at QBR. Recommend that Product add "escalation language scan" as an AI Insight Pack v3 feature, flagging these requests immediately on intake and notifying the customer's 311 director, while CityPulse's own CSM team uses high-volume escalation tenants as a monthly health-review risk-watch list.

---

## 7. Q5 Per-tenant classifier accuracy linked to SLA

Business context:

Marcus Chen issues a direct order this time: prepare a table listing each tenant's classifier accuracy on the audited subset, alongside the same period's SLA breach rate. What he wants to see is whether low-accuracy cities also have poor SLA - using a scatter plot to prove "model quality directly affects customer operational output." This story will eventually be fed to CEO Linda for the "AI Insight Pack value realization" pitch at QBR.

This corresponds to business question 5. What you expect to see: most tenants' accuracy falls between 0.85 and 0.92, while the 10 vocab_drift_level = 'high' tenants sit between 0.72 and 0.78; at the same time, those 10 tenants average about 8 percentage points higher SLA breach rate than the median.

Tags: Aggregation + Join, Intermediate, CDO.

Approach:

We need to align two derived metrics at the tenant grain: classifier accuracy from `model_predictions` on the `is_audited = 1` subset (share where predicted_category_id equals ground_truth_category_id), and SLA breach rate from joining `sla_breach_log` with `service_requests`. The aggregation grain for both is tenant_id, so two subqueries followed by a JOIN works. CTEs let the two aggregations be written cleanly side by side. Restrict to closed requests, otherwise the SLA breach denominator is distorted.

```sql
WITH accuracy_by_tenant AS (
    SELECT
        sr.tenant_id,
        COUNT(*) AS audited_count,
        SUM(
            CASE WHEN mp.predicted_category_id = mp.ground_truth_category_id THEN 1 ELSE 0 END
        ) AS correct_count,
        ROUND(
            1.0 * SUM(
                CASE WHEN mp.predicted_category_id = mp.ground_truth_category_id THEN 1 ELSE 0 END
            ) / COUNT(*),
            3
        ) AS classifier_accuracy
    FROM model_predictions mp
    JOIN service_requests sr ON sr.request_id = mp.request_id
    WHERE mp.is_audited = 1
      AND mp.predicted_at >= '2025-06-01'
      AND mp.predicted_at < '2026-06-01'
    GROUP BY sr.tenant_id
),
sla_by_tenant AS (
    SELECT
        sr.tenant_id,
        COUNT(*) AS closed_count,
        SUM(CASE WHEN sbl.breach_id IS NOT NULL THEN 1 ELSE 0 END) AS breach_count,
        ROUND(
            1.0 * SUM(CASE WHEN sbl.breach_id IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*),
            3
        ) AS sla_breach_rate
    FROM service_requests sr
    LEFT JOIN sla_breach_log sbl ON sbl.request_id = sr.request_id
    WHERE sr.closed_at IS NOT NULL
      AND sr.created_at >= '2025-06-01'
      AND sr.created_at < '2026-06-01'
    GROUP BY sr.tenant_id
)
SELECT
    t.tenant_id,
    t.tenant_code,
    t.tenant_name,
    t.vocab_drift_level,
    a.classifier_accuracy,
    s.sla_breach_rate,
    a.audited_count,
    s.closed_count
FROM tenants t
JOIN accuracy_by_tenant a ON a.tenant_id = t.tenant_id
JOIN sla_by_tenant s ON s.tenant_id = t.tenant_id
ORDER BY a.classifier_accuracy ASC;
```

Expected results and business takeaway:

120 rows (note this is all 120 tenants, not 85: `model_predictions` has an audited subset even for tenants without the AI Pack, simulating "the model runs in sandbox but isn't wired into the production router," so raw accuracy covers all tenants; only tenant_health_snapshots.classifier_accuracy is NULL for those without the pack). The top 10 rows (the lowest accuracy 10) should all be vocab_drift_level = 'high', with accuracy between 0.72 and 0.78 (measured 0.717 to 0.777, lowest sherbrooke_qc 0.717, highest jackson_ms 0.777; ranks 11 and 12 are the first mediums at around 0.82), and SLA breach rate around 0.30 (vs. global median around 0.21).

Next step: export this table as a CSV and feed it to Marcus's scatter plot; separately pull these 10 tenants' names into a sub-list and schedule a meeting with Director of Data Science Priya Iyer to discuss "localized fine tunes" for these cities (a fr_CA training subset for French cities, a region-tagged subcorpus for Deep South cities). These tenants are also the first tier on Rachel's "renewal risk watch list."

---

## 8. Q6 SLA performance comparison: Other routed to general queue

Business context:

Following the chain from Q1: Other requests do route to the `is_general_queue = 1` department, so what's the actual SLA target for those departments, what's the actual processing time, and how do they compare to specialized departments (e.g. Streets, Sanitation)? You write a relatively simple query for Tom to use in his weekly sync with Rachel.

This corresponds to business question 1.

Tags: Aggregation + Join, Basic, Senior Analyst.

Approach:

Split service_requests into two groups by whether routed_dept is the general_queue, then compute SLA breach rate and average actual_business_days. Tables involved: `service_requests`, `departments`, `sla_breach_log`. Only closed requests count. LEFT JOIN sla_breach_log since non-breached requests have no row there.

```sql
SELECT
    d.is_general_queue,
    COUNT(*) AS closed_request_count,
    SUM(CASE WHEN sbl.breach_id IS NOT NULL THEN 1 ELSE 0 END) AS breach_count,
    ROUND(
        1.0 * SUM(CASE WHEN sbl.breach_id IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*),
        3
    ) AS sla_breach_rate,
    ROUND(AVG(sbl.actual_business_days), 2) AS avg_actual_business_days_for_breached,
    ROUND(AVG(julianday(sr.closed_at) - julianday(sr.created_at)), 2) AS avg_calendar_days
FROM service_requests sr
JOIN departments d ON d.dept_id = sr.routed_dept_id
LEFT JOIN sla_breach_log sbl ON sbl.request_id = sr.request_id
WHERE sr.closed_at IS NOT NULL
  AND sr.created_at >= '2025-06-01'
  AND sr.created_at < '2026-06-01'
GROUP BY d.is_general_queue
ORDER BY d.is_general_queue;
```

Expected results and business takeaway:

2 rows (trailing 12-month window). `is_general_queue = 0` is about 300K rows, breach rate around 0.21, avg_calendar_days around 3 to 4. `is_general_queue = 1` is about 26K rows, breach rate around 0.29, avg_calendar_days around 5 to 6 (general queue has a target of 5 business days and a higher breach share, so processing duration is noticeably longer). The `avg_actual_business_days_for_breached` column also shows general queue higher (around 8 vs. specialized departments at 5 to 6).

Next step: bring this number into the weekly meeting and remind Customer Success to actively distinguish "specialized department" from "general queue" when discussing SLA performance with customers, to prevent customers from treating aggregate SLA as a sole KPI at renewal.

---

## 9. Q7 Monthly request volume and channel mix trends

Business context:

Simplest operations question. Tom asks you to report at the Monday morning standup on "platform traffic trends over the past 12 months," with an eye on whether the channel mix is shifting (voice down, mobile / social up).

Not directly tied to one of the five business questions, but this is the opening slide of the QBR deck and a standing chart on the monthly CRO dashboard.

Tags: Aggregation + Date, Basic, Senior Analyst.

Approach:

Aggregate request_id counts by (month, channel_code) two-dimensionally. `strftime('%Y-%m', created_at)` extracts the month. Join `intake_channels` for friendly `channel_code`. Order by month and read channel shares laterally.

```sql
SELECT
    strftime('%Y-%m', sr.created_at) AS month_label,
    ic.channel_code,
    COUNT(*) AS request_count
FROM service_requests sr
JOIN intake_channels ic ON ic.channel_id = sr.channel_id
WHERE sr.created_at >= '2025-06-01'
  AND sr.created_at < '2026-06-01'
GROUP BY month_label, ic.channel_code
ORDER BY month_label, ic.channel_code;
```

Expected results and business takeaway:

12 months × 6 channels = 72 rows. Monthly web volume around 25,000, mobile_app around 23,000 with slight month-over-month growth, ivr around 18,000 with slight month-over-month decline, social around 8,000, email around 6,000, walk_in around 2,500. Overall monthly trend is steady, with a slight seasonal lift in April (spring city cleanup season).

Next step: this chart goes straight into QBR deck page 1, calling out that customer cities' operational pressure peaks in spring and early fall (leaf season, pothole-repair season).

---

## 10. Q8 Top 20 tenants with the worst SLA breach rate

Business context:

The fixed table Rachel Wong wants every Tuesday morning: the 20 customer cities with the worst SLA breach rate over the past 30 days, which she hands off to the corresponding CSMs to follow up. Note she wants the rolling past 30 days, not month-to-date.

Not directly tied to a business question, but the weekly operational core input for Rachel's team.

Tags: Aggregation + Join, Basic, VP of Customer Success.

Approach:

Aggregate the past 30 days' closed requests' breach rate by tenant. Set a denominator threshold of at least 50 to keep small-population cities (only tens of thousands of residents and maybe a dozen requests in 30 days) from landing on the worst list due to chance.

```sql
SELECT
    t.tenant_id,
    t.tenant_code,
    t.tenant_name,
    t.size_tier,
    COUNT(*) AS closed_request_count,
    SUM(CASE WHEN sbl.breach_id IS NOT NULL THEN 1 ELSE 0 END) AS breach_count,
    ROUND(
        1.0 * SUM(CASE WHEN sbl.breach_id IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*),
        3
    ) AS sla_breach_rate
FROM tenants t
JOIN service_requests sr ON sr.tenant_id = t.tenant_id
LEFT JOIN sla_breach_log sbl ON sbl.request_id = sr.request_id
WHERE sr.closed_at IS NOT NULL
  AND sr.closed_at >= '2026-05-01'
  AND sr.closed_at < '2026-06-01'
GROUP BY t.tenant_id, t.tenant_code, t.tenant_name, t.size_tier
HAVING COUNT(*) >= 50
ORDER BY sla_breach_rate DESC, breach_count DESC
LIMIT 20;
```

Expected results and business takeaway:

20 rows. The top 5 likely include several vocab_drift_level = 'high' tenants (Quebec-series, Deep South-series), with breach rate in the 0.30 to 0.40 range. The other 15 rows are normally-distributed tenants that have fluctuated to the top occasionally, with breach rate between 0.28 and 0.30.

Next step: Rachel sends a "weekly SLA anomaly watch" email to each of the top 20 CSMs, asking them to proactively raise the issue at their customer city's weekly meeting.

---

## 11. Q9 Severity-selection accuracy comparison across channels

Business context:

Director of Data Science Priya Iyer mentions in her 1:1 with you that she suspects IVR's accuracy on resident-stated severity is much lower than web, due to speech-to-text loss and colloquial resident speech. This affects whether she should add a channel feature to the model card. Help her quickly quantify this.

This corresponds to business question 2.

Tags: Aggregation + Pattern, Intermediate, Director of Data Science.

Approach:

Define "severity selection is accurate" as: stated_severity is high or emergency when the description contains an emergency keyword; stated_severity is low or medium when it doesn't. Then aggregate this 0/1 indicator's mean by channel. The trick here is that "accurate" is a mix of two mutually exclusive subsets per group, which a CASE expression handles - no UNION needed.

```sql
WITH labeled AS (
    SELECT
        ic.channel_code,
        sr.stated_severity,
        CASE
            WHEN LOWER(rd.description_text) LIKE '%gas leak%'
              OR LOWER(rd.description_text) LIKE '%live wire%'
              OR LOWER(rd.description_text) LIKE '%fire%'
              OR LOWER(rd.description_text) LIKE '%smoke%'
              OR LOWER(rd.description_text) LIKE '%child injured%'
              OR LOWER(rd.description_text) LIKE '%kid hurt%'
              OR LOWER(rd.description_text) LIKE '%leaking%'
            THEN 1 ELSE 0
        END AS has_emergency_keyword
    FROM service_requests sr
    JOIN request_descriptions rd ON rd.request_id = sr.request_id
    JOIN intake_channels ic ON ic.channel_id = sr.channel_id
    WHERE sr.created_at >= '2025-12-01'
      AND sr.created_at < '2026-06-01'
)
SELECT
    channel_code,
    COUNT(*) AS request_count,
    SUM(
        CASE
            WHEN has_emergency_keyword = 1 AND stated_severity IN ('high', 'emergency') THEN 1
            WHEN has_emergency_keyword = 0 AND stated_severity IN ('low', 'medium') THEN 1
            ELSE 0
        END
    ) AS consistent_count,
    ROUND(
        1.0 * SUM(
            CASE
                WHEN has_emergency_keyword = 1 AND stated_severity IN ('high', 'emergency') THEN 1
                WHEN has_emergency_keyword = 0 AND stated_severity IN ('low', 'medium') THEN 1
                ELSE 0
            END
        ) / COUNT(*),
        3
    ) AS consistency_rate
FROM labeled
GROUP BY channel_code
ORDER BY consistency_rate DESC;
```

Expected results and business takeaway:

6 rows. web and mobile_app are between 0.86 and 0.88, email around 0.84, social around 0.78 (short text, lots of hashtags), ivr between 0.70 and 0.74 (transcription loss), walk_in around 0.85 (call_taker fills in severity on the resident's behalf).

Next step: Priya adds a channel feature to the model card so the model is more aggressive about overriding stated_severity with text-derived severity on IVR requests. CityPulse Product can also use this data to decide whether to add a "real-time emergency-keyword listener" module on IVR.

---

## 12. Q10 ARR by city size and AI Insight Pack penetration

Business context:

The most common thing CRO Daniel Ortega does at QBR is break ARR down by size_tier × pack penetration. He wants to see: what's the AI Insight Pack penetration on large cities (theoretically should be close to 100%), and what is it on small cities (theoretically 50% to 70%). This is a standing question he runs every quarter.

Not directly tied to a business question, but a standing CRO dashboard question.

Tags: Aggregation + Join, Basic, CRO.

Approach:

Aggregate tenant count and ARR total along (size_tier, has_ai_insight_pack) two dimensions. Only active contracts.

```sql
SELECT
    t.size_tier,
    ts.has_ai_insight_pack,
    COUNT(*) AS tenant_count,
    ROUND(SUM(ts.arr_usd), 0) AS total_arr_usd,
    ROUND(AVG(ts.arr_usd), 0) AS avg_arr_usd
FROM tenants t
JOIN tenant_subscriptions ts ON ts.tenant_id = t.tenant_id
WHERE ts.is_active = 1
GROUP BY t.size_tier, ts.has_ai_insight_pack
ORDER BY t.size_tier, ts.has_ai_insight_pack DESC;
```

Expected results and business takeaway:

Up to 6 rows (3 size_tiers × has_ai_insight_pack 0/1), with actual landings of: large cities 17 tenants, all enabled (17/17 = 100%, because the large city sample is small and the 95% penetration target is rounded up), avg_arr around $900K; medium cities 74 tenants, 62 enabled (84%), avg_arr around $420K; small cities 29 tenants, 17 enabled (59%), avg_arr around $180K. Total ARR across the 120 active contracts is around $52M (measured 51.9M). Note that medium is over-represented because many cities in the 180K-210K population range fall into medium by definition (≥150K).

Next step: prepare a supplemental data slice for Daniel's next-year budget proposal, focused on the AI Insight Pack upgrade opportunity in the small tier (penetration only about 60%, the lowest of the three bands), estimating the incremental ARR if penetration goes from 60% to 80%.

---

## 13. Q11 Model accuracy stratified by vocab_drift_level

Business context:

Continuing the Q5 story. After seeing the Q5 scatter plot, Marcus asks you to group tenants by vocab_drift_level (low / medium / high) and produce an accuracy summary per group, also cross-tabbed by size_tier. He wants to know whether large + high vocab drift tenants are the biggest drag.

This corresponds to business question 5.

Tags: Aggregation + Window (RANK), Intermediate, CDO.

Approach:

First group by (vocab_drift_level, size_tier) two-dimensionally to compute the mean accuracy and tenant count per group, then use RANK within vocab_drift_level by accuracy ascending. This question demonstrates the "rank within group after GROUP BY" pattern using OVER.

```sql
WITH per_tenant_accuracy AS (
    SELECT
        sr.tenant_id,
        ROUND(
            1.0 * SUM(
                CASE WHEN mp.predicted_category_id = mp.ground_truth_category_id THEN 1 ELSE 0 END
            ) / COUNT(*),
            3
        ) AS accuracy
    FROM model_predictions mp
    JOIN service_requests sr ON sr.request_id = mp.request_id
    WHERE mp.is_audited = 1
      AND mp.predicted_at >= '2025-06-01'
      AND mp.predicted_at < '2026-06-01'
    GROUP BY sr.tenant_id
),
joined AS (
    SELECT
        t.tenant_id,
        t.vocab_drift_level,
        t.size_tier,
        pta.accuracy
    FROM tenants t
    JOIN per_tenant_accuracy pta ON pta.tenant_id = t.tenant_id
)
SELECT
    vocab_drift_level,
    size_tier,
    COUNT(*) AS tenant_count,
    ROUND(AVG(accuracy), 3) AS avg_accuracy,
    MIN(accuracy) AS min_accuracy,
    MAX(accuracy) AS max_accuracy,
    RANK() OVER (
        PARTITION BY vocab_drift_level
        ORDER BY AVG(accuracy) ASC
    ) AS rank_within_drift_level
FROM joined
GROUP BY vocab_drift_level, size_tier
ORDER BY vocab_drift_level, avg_accuracy ASC;
```

Expected results and business takeaway:

9 rows (3 drift levels × 3 size tiers). vocab_drift_level = 'high' has avg_accuracy in the 0.70 to 0.75 range across all three size tiers; vocab_drift_level = 'medium' is 0.83 to 0.86; vocab_drift_level = 'low' is 0.87 to 0.90. Size has little impact on accuracy; vocab drift is the dominant factor.

Next step: this table confirms the "vocab drift is key" hypothesis from the Q5 scatter. Marcus takes it to align with Priya: next quarter, the Data Science team should be doing dialect/vocabulary-stratified modeling, not size-stratified modeling.

---

## 14. Q12 True "on-time resolution rate" recomputed after subtracting 30-day recurrence

Business context:

Tom gives you "the hardest question": Q3 exposed that the 24-hour quick-close group has about 28% same-address recurrence (vs. 20% for non-quick-close). If we also count "same-address recurrence within 30 days" as a failure across all requests, and recompute the true on-time resolution rate, how much lower is the new metric than the currently reported on-time rate? This number directly affects how much customers can trust CityPulse's reporting.

This corresponds to business question 3.

Tags: CTE + Join + Window, Advanced, Director of Analytics.

Approach:

This needs three labels: (a) is on_time (i.e. not breached), (b) has same-address recurrence within 30 days, (c) "true" on-time = on_time AND NOT repeated. Then aggregate two rates per tenant: reported (just (a)) and true (just (c)). Output the difference. Window function LAG/LEAD identifies the next request at the same address, same as Q3. The CTE allows the two rates to JOIN at the tenant grain.

```sql
WITH base AS (
    SELECT
        sr.tenant_id,
        sr.request_id,
        sr.address_id,
        sr.created_at,
        sr.closed_at,
        CASE WHEN sbl.breach_id IS NULL THEN 1 ELSE 0 END AS is_on_time
    FROM service_requests sr
    LEFT JOIN sla_breach_log sbl ON sbl.request_id = sr.request_id
    WHERE sr.closed_at IS NOT NULL
      AND sr.address_id IS NOT NULL
      AND sr.is_duplicate = 0
      AND sr.created_at >= '2025-06-01'
      AND sr.created_at < '2026-05-01'
),
with_next AS (
    SELECT
        b.*,
        LEAD(created_at) OVER (
            PARTITION BY address_id
            ORDER BY created_at
        ) AS next_request_at_same_address
    FROM base b
),
labeled AS (
    SELECT
        tenant_id,
        is_on_time,
        CASE
            WHEN next_request_at_same_address IS NOT NULL
             AND julianday(next_request_at_same_address) - julianday(closed_at) <= 30
            THEN 1 ELSE 0
        END AS has_repeat_within_30d
    FROM with_next
)
SELECT
    t.tenant_id,
    t.tenant_code,
    t.tenant_name,
    COUNT(*) AS total_requests,
    ROUND(1.0 * SUM(is_on_time) / COUNT(*), 3) AS reported_on_time_rate,
    ROUND(
        1.0 * SUM(CASE WHEN is_on_time = 1 AND has_repeat_within_30d = 0 THEN 1 ELSE 0 END)
        / COUNT(*),
        3
    ) AS true_on_time_rate,
    ROUND(
        1.0 * SUM(is_on_time) / COUNT(*)
        - 1.0 * SUM(CASE WHEN is_on_time = 1 AND has_repeat_within_30d = 0 THEN 1 ELSE 0 END)
        / COUNT(*),
        3
    ) AS gap
FROM labeled l
JOIN tenants t ON t.tenant_id = l.tenant_id
GROUP BY t.tenant_id, t.tenant_code, t.tenant_name
HAVING COUNT(*) >= 500
ORDER BY gap DESC
LIMIT 30;
```

Expected results and business takeaway:

About 30 rows. reported_on_time_rate is between 0.72 and 0.85, and true_on_time_rate is 0.18 to 0.25 lower than reported (because same-address 30-day recurrence baseline is itself high). The top 10 gaps concentrate on high-volume large tenants since the same-address clustering effect is more pronounced. Even after subtracting the natural clustering (~20pp is baseline noise), the relative loss to true on-time rate from the quick-close group can still be read from the cross-group comparison.

Next step: this is the most impactful page in the QBR deck. Remind Linda and Daniel: the "on-time resolution rate" we've been sending customer cities in the monthly report dashboard is overstated. We need to add "true on-time resolution rate" as an optional second metric in the next iteration; otherwise we'll be on the defensive when customers discover this themselves.

---

## 15. Q13 Council complaint escalation channel breakdown for escalation-language requests

Business context:

Q4 gave a single lift number (overall escalation probability for with vs. without escalation language). What Rachel wants next: within the requests that actually escalated, what's the composition across escalation_channel (council_letter, news_media, lawyer_letter, social_viral)? Does the escalation-language subset lean toward a specific channel? This affects which type of risk Product should prioritize alerting on when the scanner fires.

This corresponds to business question 4. Note it's a "channel breakdown" follow-up to Q4: Q4 gives the overall escalation rate and lift; Q13 gives the channel composition. The "escalation" definition must be consistent across both (both restricted to 60 days after created_at), so this query's LEFT JOIN also has the 60-day constraint.

Tags: Pattern + EXISTS + Aggregation, Intermediate, VP of Customer Success.

Approach:

Take Q4's "escalate to council" and break it down by escalation_channel. Align the has_escalation_phrase label and escalation_channel at the SR grain (LEFT JOIN restricted to 60 days, same definition as Q4), then aggregate by (has_escalation_phrase, escalation_channel). Rows where escalation_channel is NULL (no escalation requests) are kept, but bucketed as 'no_escalation' on display. `pct_within_phrase_group` uses a window function to compute "channel share within the same has_escalation_phrase group," so you can directly read the channel-composition difference between escalation-language and non-escalation-language subsets.

```sql
WITH labeled AS (
    SELECT
        sr.request_id,
        sr.created_at,
        CASE
            WHEN LOWER(rd.description_text) LIKE '%third time%'
              OR LOWER(rd.description_text) LIKE '%fed up%'
              OR LOWER(rd.description_text) LIKE '%contact my councilman%'
              OR LOWER(rd.description_text) LIKE '%going to the news%'
              OR LOWER(rd.description_text) LIKE '%get a lawyer%'
              OR LOWER(rd.description_text) LIKE '%my lawyer%'
            THEN 1 ELSE 0
        END AS has_escalation_phrase
    FROM service_requests sr
    JOIN request_descriptions rd ON rd.request_id = sr.request_id
    WHERE sr.created_at >= '2025-06-01'
      AND sr.created_at < '2026-04-01'
),
joined AS (
    SELECT
        l.request_id,
        l.has_escalation_phrase,
        COALESCE(cc.escalation_channel, 'no_escalation') AS escalation_channel
    FROM labeled l
    LEFT JOIN citizen_complaints cc
        ON cc.primary_request_id = l.request_id
       -- Match Q4's definition: only count complaints filed within 60 days of created
       AND julianday(cc.filed_at) - julianday(l.created_at) <= 60
)
SELECT
    has_escalation_phrase,
    escalation_channel,
    COUNT(*) AS request_count,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (PARTITION BY has_escalation_phrase), 2) AS pct_within_phrase_group
FROM joined
GROUP BY has_escalation_phrase, escalation_channel
ORDER BY has_escalation_phrase, escalation_channel;
```

Expected results and business takeaway:

Up to 10 rows (2 has_escalation_phrase values × up to 5 escalation_channel values including no_escalation). In each phrase group the vast majority is still `no_escalation` (about 92% in the escalation-language group, about 99.7% in the non-language group, since escalation is itself a small-probability event). Within the small share that actually escalates, the channel composition is roughly council_letter ~60%, news_media ~15%, lawyer_letter ~15%, social_viral ~10%; the escalation-language subset's total escalation count (= 1 - no_escalation share) is materially larger than the non-language group's - that's the channel-level manifestation of Q4's lift. `pct_within_phrase_group` lets you see the channel distribution difference between the two groups at a glance.

Next step: keep "contact my councilman" as a standalone strongest signal, since it has the highest lift in the council_letter escalation category. Product should configure a high-priority alert specifically when the scanner hits this phrase.

---

## 16. Q14 Reopen timing distribution and cohort analysis

Business context:

You want to figure something out for yourself: how long after closure are reopens most likely? Within 24 hours? 2 to 7 days? Or 8 to 30 days? (By business rule, reopens can only happen within 30 days of close; any further re-report is treated as a brand-new request, not a reopen.) This affects how long CityPulse's "reopen monitoring window" should be set, and whether to add a shorter immediate-alert.

Not directly tied to a business question, but an operational question Product cares about.

Tags: Date Analysis + Aggregation, Intermediate, Senior Analyst.

Approach:

For each reopen event, compute the difference between its event_at and the corresponding service_request's most recent closed event_at. We need to pull the reopened event and the previous closed event from request_events and difference them. SQLite doesn't have a native "previous event" concept; use the LAG window function over (request_id, event_at).

```sql
WITH events_ordered AS (
    SELECT
        request_id,
        event_type,
        event_at,
        LAG(event_at) OVER (PARTITION BY request_id ORDER BY event_at) AS prev_event_at,
        LAG(event_type) OVER (PARTITION BY request_id ORDER BY event_at) AS prev_event_type
    FROM request_events
    WHERE event_at >= '2025-06-01'
      AND event_at < '2026-06-01'
),
reopens_with_gap AS (
    SELECT
        request_id,
        event_at AS reopened_at,
        prev_event_at AS last_closed_at,
        CAST(julianday(event_at) - julianday(prev_event_at) AS INTEGER) AS days_since_close
    FROM events_ordered
    WHERE event_type = 'reopened'
      AND prev_event_type = 'closed'
)
SELECT
    CASE
        WHEN days_since_close <= 1 THEN '0_1_day'
        WHEN days_since_close <= 7 THEN '2_7_days'
        WHEN days_since_close <= 30 THEN '8_30_days'
        WHEN days_since_close <= 90 THEN '31_90_days'
        ELSE 'over_90_days'
    END AS days_bucket,
    COUNT(*) AS reopen_count,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS pct_of_reopens
FROM reopens_with_gap
GROUP BY days_bucket
ORDER BY
    CASE days_bucket
        WHEN '0_1_day' THEN 1
        WHEN '2_7_days' THEN 2
        WHEN '8_30_days' THEN 3
        WHEN '31_90_days' THEN 4
        ELSE 5
    END;
```

Expected results and business takeaway:

3 non-empty buckets (business rule: reopens only happen within 30 days of close, so 31_90_days and over_90_days are always 0 and don't appear in the result). Reopen delay is front-weighted (denser closer to close): 0_1_day around 27% (residents see crew leave but the issue is still there, so they reopen immediately), 2_7_days around 25%, 8_30_days around 48%. Conclusion: the 30-day window by design covers 100% of reopens, but the first two days alone contribute over a quarter.

Next step: use this distribution to tell Product that the current 30-day reopen monitoring window covers all reopens and is reasonable, but a "close + 48 hours alert" feature should be added for supervisors (since the first two days contribute about 25% of reopens, and that's the most rescuable batch).

---

## 17. Q15 Top 10 by category_group request volume

Business context:

Simplest question. Tom asks you to prepare "most common request top-level categories on the platform over the past 12 months" for deck page 2.

Not directly tied to a business question; a standard deck page.

Tags: Aggregation + Join, Basic, Senior Analyst.

Approach:

Aggregate SR count by category_group and take top 10. Note there are only 8 category_groups, so the result is actually 8 rows sorted by count.

```sql
SELECT
    sc.category_group,
    COUNT(*) AS request_count,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS share_pct
FROM service_requests sr
JOIN service_categories sc ON sc.category_id = sr.auto_category_id
WHERE sr.created_at >= '2025-06-01'
  AND sr.created_at < '2026-06-01'
GROUP BY sc.category_group
ORDER BY request_count DESC
LIMIT 10;
```

Expected results and business takeaway:

8 rows (actual category_group count). Streets ~24.5%, Sanitation ~21%, Utilities ~18%, Parks ~10.5%, Code ~8.4%, Other ~8.0%, Animal ~5%, Noise ~4%. (After the fix, Other is back to ~8% and no longer inflated to 14% by sampling leakage; Code and Other are nearly tied.)

Next step: this is the bar chart on deck page 2. After Tom sees it, he'll have you pull the Other column out separately for page 3 to set up the Q1 story.

---

## 18. Q16 Estimated total SLA loss from Other misroutes (by tenant)

Business context:

After looking at Q1's data, Marcus wants to know: if the Other-class strong-keyword subset had been correctly routed, how many SLA breaches could be avoided? This estimate is the number that goes on Linda's QBR deck page titled "Potential ROI from AI Insight Pack improvements." Compute it per tenant, find the top 10 by ROI, and those become CityPulse's priority fine-tuning targets.

This corresponds to business question 1 and is a downstream application of Q1.

Tags: CTE + Pattern + Aggregation, Advanced, CDO.

Approach:

Per tenant: count Other-class requests containing strong keywords (the "rescuable pool"), estimate the SLA breach rate if those requests had been correctly classified (use non-Other breach rate as proxy), and multiply the difference against current Other-class breach rate times pool size to get "avoidable breaches." Rank tenants and take top 10.

```sql
WITH classified AS (
    SELECT
        sr.tenant_id,
        sr.request_id,
        sc.is_other,
        CASE
            WHEN LOWER(rd.description_text) LIKE '%pothole%'
              OR LOWER(rd.description_text) LIKE '%hole in road%'
              OR LOWER(rd.description_text) LIKE '%streetlight%'
              OR LOWER(rd.description_text) LIKE '%street light%'
              OR LOWER(rd.description_text) LIKE '%graffiti%'
              OR LOWER(rd.description_text) LIKE '%illegal dumping%'
              OR LOWER(rd.description_text) LIKE '%dumped%'
              OR LOWER(rd.description_text) LIKE '%noise%'
              OR LOWER(rd.description_text) LIKE '%tree limb%'
              OR LOWER(rd.description_text) LIKE '%fallen tree%'
            THEN 1 ELSE 0
        END AS has_strong_keyword,
        CASE WHEN sbl.breach_id IS NOT NULL THEN 1 ELSE 0 END AS is_breach
    FROM service_requests sr
    JOIN service_categories sc ON sc.category_id = sr.auto_category_id
    JOIN request_descriptions rd ON rd.request_id = sr.request_id
    LEFT JOIN sla_breach_log sbl ON sbl.request_id = sr.request_id
    WHERE sr.closed_at IS NOT NULL
      AND sr.created_at >= '2025-06-01'
      AND sr.created_at < '2026-06-01'
),
rates AS (
    SELECT
        tenant_id,
        SUM(CASE WHEN is_other = 1 AND has_strong_keyword = 1 THEN 1 ELSE 0 END) AS misroute_pool,
        SUM(CASE WHEN is_other = 1 AND has_strong_keyword = 1 AND is_breach = 1 THEN 1 ELSE 0 END) AS misroute_breach_count,
        SUM(CASE WHEN is_other = 0 THEN is_breach ELSE 0 END) * 1.0
            / NULLIF(SUM(CASE WHEN is_other = 0 THEN 1 ELSE 0 END), 0) AS non_other_breach_rate,
        SUM(CASE WHEN is_other = 1 THEN is_breach ELSE 0 END) * 1.0
            / NULLIF(SUM(CASE WHEN is_other = 1 THEN 1 ELSE 0 END), 0) AS other_breach_rate
    FROM classified
    GROUP BY tenant_id
)
SELECT
    t.tenant_id,
    t.tenant_code,
    t.tenant_name,
    r.misroute_pool,
    ROUND(r.other_breach_rate, 3) AS other_breach_rate,
    ROUND(r.non_other_breach_rate, 3) AS non_other_breach_rate,
    ROUND(
        r.misroute_pool * (r.other_breach_rate - r.non_other_breach_rate),
        1
    ) AS avoidable_breaches
FROM rates r
JOIN tenants t ON t.tenant_id = r.tenant_id
WHERE r.misroute_pool >= 20
ORDER BY avoidable_breaches DESC
LIMIT 10;
```

Expected results and business takeaway:

Up to 10 rows (constrained by `misroute_pool >= 20`; only high-volume large cities qualify since a single tenant's Other strong-keyword pool is typically only a few dozen to about 100 over a 12-month window). The top 1 tenant is likely the highest-volume large city with AI Insight Pack enabled; `misroute_pool` is in the tens to over a hundred, `other_breach_rate - non_other_breach_rate` is about 0.08 (0.29 vs. 0.21), so `avoidable_breaches` is around 5 to 15 (in the 12-month window). The top 10 sum to about 60 to 120 avoidable breaches. Roughly 3x that across the full 36 months.

Next step: the absolute number isn't huge, but what Marcus cares about is "this is free money you can capture purely by tuning the threshold," with near-zero marginal cost. Recommend A/B testing the new threshold on these 10 tenants immediately.

---

## 19. Q17 Drop in classifier accuracy for French vocab tenants

Business context:

Continuing the Marcus / Priya story. Priya wants to look specifically at how much lower Quebec-series cities' (has_french_vocab = 1) classifier accuracy is compared to other cities of the same size, since this number determines whether she'll build a French fine-tune sub-model for this group.

This corresponds to business question 5.

Tags: CTE + Join + Aggregation, Intermediate, Director of Data Science.

Approach:

Group by has_french_vocab, controlling for size_tier, and compare accuracy. Uses a CTE to compute per-tenant accuracy, then joins tenants for grouping.

```sql
WITH per_tenant_accuracy AS (
    SELECT
        sr.tenant_id,
        1.0 * SUM(
            CASE WHEN mp.predicted_category_id = mp.ground_truth_category_id THEN 1 ELSE 0 END
        ) / COUNT(*) AS accuracy,
        COUNT(*) AS audited_count
    FROM model_predictions mp
    JOIN service_requests sr ON sr.request_id = mp.request_id
    WHERE mp.is_audited = 1
      AND mp.predicted_at >= '2025-06-01'
      AND mp.predicted_at < '2026-06-01'
    GROUP BY sr.tenant_id
)
SELECT
    t.has_french_vocab,
    t.size_tier,
    COUNT(*) AS tenant_count,
    ROUND(AVG(pta.accuracy), 3) AS avg_accuracy,
    ROUND(MIN(pta.accuracy), 3) AS min_accuracy,
    ROUND(MAX(pta.accuracy), 3) AS max_accuracy
FROM tenants t
JOIN per_tenant_accuracy pta ON pta.tenant_id = t.tenant_id
GROUP BY t.has_french_vocab, t.size_tier
ORDER BY t.has_french_vocab DESC, t.size_tier;
```

Expected results and business takeaway:

6 rows. The 4 `has_french_vocab=1` tenants spread across large and medium tiers, with accuracy around 0.70 to 0.74. The same-size `has_french_vocab=0` tenants don't all have vocab_drift_level = high (only the 6 Deep South cities are high), so their accuracy overall is 0.85 to 0.88. Gap is about 15pp.

Next step: send Priya a proposal recommending a fr_CA fine-tune subset, training on the past 24 months of Quebec-series tenant descriptions, with an expected lift of at least 10pp in accuracy.

---

## 20. Q18 Top staff users by throughput and SLA performance

Business context:

You're a bit curious yourself: in staff_users, which staff handle the most requests, and how does their SLA performance look? This is somewhat like an internal "personal KPI board," but Tom reminds you not to send this to customer cities - it's for CityPulse internal use only.

Not directly tied to a business question; an internal exploration.

Tags: Subquery + Join, Intermediate, Senior Analyst.

Approach:

Find each request's earliest assigned staff via request_assignments, then aggregate by staff_id. SLA performance comes from LEFT JOIN on sla_breach_log. One staff handles many requests, so group by staff_id.

```sql
WITH first_assignment AS (
    SELECT
        request_id,
        staff_id,
        MIN(assigned_at) AS first_assigned_at
    FROM request_assignments
    WHERE staff_id IS NOT NULL
      AND assigned_at >= '2025-06-01'
      AND assigned_at < '2026-06-01'
    GROUP BY request_id, staff_id
),
joined AS (
    SELECT
        fa.staff_id,
        fa.request_id,
        CASE WHEN sbl.breach_id IS NOT NULL THEN 1 ELSE 0 END AS is_breach
    FROM first_assignment fa
    LEFT JOIN sla_breach_log sbl ON sbl.request_id = fa.request_id
)
SELECT
    su.staff_id,
    su.staff_name,
    su.role,
    d.dept_name,
    t.tenant_code,
    COUNT(*) AS handled_count,
    SUM(j.is_breach) AS breach_count,
    ROUND(1.0 * SUM(j.is_breach) / COUNT(*), 3) AS breach_rate
FROM joined j
JOIN staff_users su ON su.staff_id = j.staff_id
JOIN departments d ON d.dept_id = su.dept_id
JOIN tenants t ON t.tenant_id = su.tenant_id
GROUP BY su.staff_id, su.staff_name, su.role, d.dept_name, t.tenant_code
HAVING COUNT(*) >= 100
ORDER BY handled_count DESC
LIMIT 20;
```

Expected results and business takeaway:

20 rows. The top names are usually supervisor roles in large cities, each handling 1,000 to 3,000 requests over 12 months, with breach rates between 0.15 and 0.30 - close to their tenant's overall level (no particular outliers).

Next step: archive this table, and Director Tom uses it during quarterly internal ops review to cross-check "is workload distribution balanced across customer cities."

---

## 21. Q19 Categories with the highest reopen rates

Business context:

Tom wants to see which categories' requests are most likely to be reopened - this affects whether CityPulse should recommend "set longer SLA on these categories so field crews have time to resolve in one pass" when discussing SLA configuration with customers.

Not directly tied to a business question, but related to traps 2 and 3.

Tags: Window + Aggregation, Intermediate, Senior Analyst.

Approach:

Aggregate reopen rate by category, then use RANK to sort and output top 10. Reopen detection uses the request_events table.

```sql
WITH category_stats AS (
    SELECT
        sc.category_id,
        sc.category_code,
        sc.category_group,
        COUNT(DISTINCT sr.request_id) AS total_closed,
        COUNT(DISTINCT
            CASE WHEN re.event_type = 'reopened' THEN sr.request_id END
        ) AS reopened_count
    FROM service_requests sr
    JOIN service_categories sc ON sc.category_id = sr.auto_category_id
    LEFT JOIN request_events re
        ON re.request_id = sr.request_id
       AND re.event_type = 'reopened'
       AND re.event_at >= '2025-06-01'
       AND re.event_at < '2026-07-01'
    WHERE sr.closed_at IS NOT NULL
      AND sr.created_at >= '2025-06-01'
      AND sr.created_at < '2026-06-01'
    GROUP BY sc.category_id, sc.category_code, sc.category_group
),
ranked AS (
    SELECT
        category_id,
        category_code,
        category_group,
        total_closed,
        reopened_count,
        ROUND(1.0 * reopened_count / total_closed, 3) AS reopen_rate,
        RANK() OVER (ORDER BY 1.0 * reopened_count / total_closed DESC) AS rk
    FROM category_stats
    WHERE total_closed >= 500
)
SELECT *
FROM ranked
WHERE rk <= 10
ORDER BY rk;
```

Expected results and business takeaway:

10 rows. The top are likely illegal_dumping, abandoned_vehicle, noise_complaint, tree_limb (these are categories where the problem easily "comes back as it was" after field treatment), with reopen rate between 0.10 and 0.18. pothole in the Streets group is actually lower (one patch lasts a while).

Next step: hand this list to Customer Success, and during quarterly reviews with customers whose volume is concentrated in these categories, proactively suggest "loosen the SLA on high-reopen categories like illegal_dumping, or introduce a secondary follow-up inspection."

---

## 22. Q20 12 core metrics tenant health dashboard

Business context:

The last question. Linda wants a 12 core metrics × 4 representative tenants comparison table on the last page of the QBR deck, to feed directly to the board. You prepare this table. The 4 representative tenants are: City of Austin (large + healthy + low drift), Ville de Québec (large + high vocab drift), City of Plano (medium + average + low drift), City of Burlington (small). (Note: Mesa has a population of about 510K, which by definition is large, so here we use Plano as the medium representative rather than Mesa.)

Not directly tied to a business question; the deck's closing page.

Tags: Aggregation, Basic, CEO (submitted by Senior Analyst).

Approach:

Pull a single monthly snapshot row from `tenant_health_snapshots` and JOIN tenants for display. This table is aggregated and written by the generator after all fact tables are produced, so SELECT directly - no recomputation needed. Note we pick **2026-03-01**, a **fully-settled month**, rather than the most recent 2026-05: because the one or two months before the anchor 2026-06-01 contain "long-duration breaches" that haven't closed yet, which systematically lowers the most recent month's sla_breach_rate (every real operational dashboard has this recency bias); a fully-settled month better represents steady state.

```sql
SELECT
    t.tenant_code,
    t.tenant_name,
    t.size_tier,
    t.vocab_drift_level,
    ths.request_count,
    ROUND(ths.sla_breach_rate, 3) AS sla_breach_rate,
    ROUND(ths.reopen_rate, 3) AS reopen_rate,
    ROUND(ths.repeat_at_address_rate, 3) AS repeat_at_address_rate,
    ROUND(ths.classifier_accuracy, 3) AS classifier_accuracy,
    ROUND(ths.council_escalation_rate, 4) AS council_escalation_rate,
    ths.nps_score,
    ths.churn_risk_band
FROM tenant_health_snapshots ths
JOIN tenants t ON t.tenant_id = ths.tenant_id
WHERE ths.snapshot_month = '2026-03-01'
  AND t.tenant_code IN ('austin_tx', 'quebec_qc', 'plano_tx', 'burlington_vt')
ORDER BY
    CASE t.tenant_code
        WHEN 'austin_tx' THEN 1
        WHEN 'quebec_qc' THEN 2
        WHEN 'plano_tx' THEN 3
        WHEN 'burlington_vt' THEN 4
    END;
```

Expected results and business takeaway:

4 rows (2026-03 monthly snapshot, reproducible under fixed seed):

| tenant | size/drift | request_count | sla_breach_rate | reopen_rate | repeat_at_address_rate | classifier_accuracy | council_escalation_rate | nps_score | churn_risk_band |
|--------|-----------|---------------|-----------------|-------------|------------------------|---------------------|-------------------------|-----------|------------------|
| Austin | large / low | 968 | 0.191 | 0.064 | 0.238 | 0.909 | 0.0031 | 38 | **low** |
| Québec | large / high | 509 | 0.301 | 0.057 | 0.282 | 0.722 | 0.0020 | -10 | **high** |
| Plano | medium / low | 286 | 0.210 | 0.091 | 0.232 | 0.803 | 0.0035 | 27 | **medium** |
| Burlington | small / low | 46 | 0.304 | 0.091 | 0.310 | 0.909 | 0.0000 | -14 | **high** |

The story is clear: Austin (healthy large city) is churn low; Québec (high vocab drift) is the real problem - classifier_accuracy only 0.722 (lowest in the cohort, i.e. the trap 5 laggard), combined with the highest SLA breach, lands churn at high; Plano represents the medium-average and lands at medium. Burlington is an interesting teaching point: with only 46 tickets per month, a single month's SLA wobble to 0.30 pushes churn to high, but its classifier_accuracy is 0.909 - so its high band is "small-sample monthly noise + occasional SLA," not a model-quality issue - reminding analysts not to overreact to single-month metrics on small tenants.

> Notes (two post-fix definitions): (1) `reopen_rate` / `repeat_at_address_rate` are now genuinely aggregated values that can be cross-validated against the fact tables using Q14 / Q19 / Q3 - they're no longer a synthetic function of sla. (2) Taking 2026-03 instead of the most recent month avoids the "long-duration unsettled breaches near the anchor" recency bias; the three churn_risk_band values (low/medium/high) all have real distribution on the platform, rather than everything being medium as in the old version.

Next step: this is the last page of the deck. Linda wraps up with this page at QBR and jumps to Q&A. Be ready to answer the board's "why is Quebec so bad?" - the answer is the combination of Q11 and Q17 data (vocab drift causes classifier accuracy to drop to 0.72).

---

## 23. Business Question to Query Mapping

| Business Question | Corresponding Queries |
|----------|----------|
| Q1 Other classification drift | Q1, Q6, Q16 |
| Q2 Stated severity text-implied divergence | Q2, Q9 |
| Q3 First-touch quick close masking | Q3, Q12 |
| Q4 Escalation language predicting complaints | Q4, Q13 |
| Q5 Tenant-level model accuracy variance | Q5, Q11, Q17 |
| Operational routine (no direct mapping) | Q7, Q8, Q10, Q14, Q15, Q18, Q19, Q20 |

Each query maps to at least one business question or operational concern. The operational routine questions aren't direct counterparts to any of the five business questions, but they're all standing queries that CityPulse roles (CRO, VP CS, Director of Analytics) run daily, and their inclusion makes this handbook practical rather than just "a demo collection of five traps."
