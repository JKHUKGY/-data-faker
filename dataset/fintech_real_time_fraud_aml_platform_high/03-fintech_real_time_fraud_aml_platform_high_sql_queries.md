# Fintech — Real-Time Fraud & AML Platform (NovaRisk AI) — SQL Query Reference

## Overview

20 business-driven SQL queries against the `fintech_real_time_fraud_aml_platform_high` dataset. Every query maps to a business question in the business-context document and has been verified runnable on the packaged SQLite database.

- **Business context, industry primer, glossary, and metric formulas** are in `01-fintech_real_time_fraud_aml_platform_high_business_context.md`.
- **Table structure, fields, generation rules, and DDL** are in `02-fintech_real_time_fraud_aml_platform_high_er_document.md`.
- Because `transaction` is a SQLite reserved word, this document always writes it as `"transaction"` with double quotes.
- **Reference date (REFERENCE_DATE) = `2026-06-05`.** The dataset is anchored to this fixed date, and every query hard-codes it as a literal string (e.g. `JULIANDAY('2026-06-05')`) rather than using `DATE('now')` — that way results are reproducible no matter when you run them.

### How to Use This Document

This document is teaching-oriented. Imagine you're a brand-new intern analyst who just finished reading the business context and ER document, and the manager has handed you these 20 queries with "get them done this week."

**Every query has the same five fixed sections — read them in order:**

1. **Business Context** — who is asking, why, what decision the answer supports, and why now. Grounds the query in a real role and a real moment.
2. **Category / Difficulty / Business Role** — three labels that tell you at a glance which SQL skill it exercises, how hard it is, and which job function it serves.
3. **Approach** — *before* you see the SQL, this section walks through which tables to touch, how to wire the joins, where the traps are (fan-out, double counting, LEFT vs INNER), what the aggregation grain is, and why a CTE or window function is needed. This is the learning section.
4. **SQL** — code that runs as-is against the packaged database. Read it, understand it, don't just run it.
5. **Expected Result + Business Takeaway** — what the result looks like (rows, column meaning, expected magnitudes), and what the analyst should do next once the numbers are in. Getting the result is the start of the analysis, not the end.

**Suggested workflow:** read the business context to nail down *why*; read the approach section and sketch the query skeleton in your head; try writing the SQL yourself; then check your version against the provided SQL and the expected results. Every query traces back to a business question in the business-context document (Q1–Q8).

---

## Query Index

| # | Title | Business Role | Category | Difficulty |
|---|-------|---------------|----------|------------|
| 1 | Real-time scoring SLA snapshot (p50/p95/p99) | Operations | Aggregation + Window | Medium |
| 2 | Top revenue customers by contract value | Executive | Aggregation | Beginner |
| 3 | Decision distribution per customer | Manager | Join + Aggregation | Beginner |
| 4 | Alert volume by fraud type | Analyst | Join + Aggregation | Beginner |
| 5 | False-positive rate by detection rule | Manager | Aggregation + Filter | Medium |
| 6 | Average investigation time per analyst | Manager | Date Diff + Aggregation | Medium |
| 7 | Coordinated attack ring detection (shared device fingerprints) | Analyst | CTE / Graph style | Advanced |
| 8 | High-risk corridor exposure per customer | Executive | Aggregation + Filter | Beginner |
| 9 | Daily transaction and alert trend | Analyst | Date / Time series | Medium |
| 10 | Top-5 SAR-filing analysts per customer | Manager | Window Function (top-N per group) | Medium |
| 11 | Customer risk rating vs actual fraud rate | Analyst | CTE + Aggregation | Advanced |
| 12 | SAR narratives that hit the sanctions watchlist | Operations | Inner join on nullable FK | Medium |
| 13 | Vera AI agent tool usage and cost | Finance | Aggregation | Beginner |
| 14 | Champion vs challenger model decision drift | Analyst | CTE + Conditional Aggregation | Advanced |
| 15 | Top-10 accounts by DECLINE-blocked amount | Operations | Aggregation + Sort | Beginner |
| 16 | True 7-calendar-day rolling alert rate per customer | Analyst | Recursive CTE + Window | Advanced |
| 17 | VPN sessions whose country doesn't match the account country | Operations | Join | Medium |
| 18 | High-priority cases open more than 14 days | Manager | Date Diff + Filter | Medium |
| 19 | Revenue concentration: top-3 customer share | Finance | CTE + Window | Advanced |
| 20 | Pattern search for "structuring" in SAR narratives | Operations | LIKE / Pattern | Beginner |

---

## Queries

### Query 1: Real-Time Scoring SLA Snapshot (p50 / p95 / p99)

**Business Context:**
The SRE Lead needs a one-glance check every morning before standup to confirm the real-time scoring API is still meeting the <100ms p99 latency commitment. If p99 is creeping above 100ms, they page the on-call engineer to investigate.

**Category:** Aggregation + Window Function
**Difficulty:** Medium
**Business Role:** Operations

**Approach:**
This query only needs the `latency_ms` column from `risk_score_event`. The wrinkle is that SQLite has no `PERCENTILE_CONT`, so we use `ROW_NUMBER() OVER (ORDER BY latency_ms)` to rank every row (`rn`), then `COUNT(*) OVER ()` to grab the total row count `n`, then `MAX(CASE WHEN rn = CAST(n*0.99 AS INT) ...)` to "pick out" the value at the target percentile row. One output row summarizes platform-wide latency. The SLA-breach rate is computed by a separate scalar subquery — don't mix it into the window, or the denominator will be affected by window row counts.

```sql
-- SQLite doesn't have PERCENTILE_CONT, so we approximate by ordering rows and grabbing the row at the target percentile.
WITH ranked AS (
    SELECT
        latency_ms,
        ROW_NUMBER() OVER (ORDER BY latency_ms)         AS rn,
        COUNT(*)    OVER ()                              AS n
    FROM risk_score_event
)
SELECT
    (SELECT COUNT(*) FROM risk_score_event)                   AS total_scored,
    ROUND((SELECT AVG(latency_ms) FROM risk_score_event), 1)  AS avg_latency_ms,
    MAX(CASE WHEN rn = CAST(n * 0.50 AS INTEGER) THEN latency_ms END) AS p50_latency_ms,
    MAX(CASE WHEN rn = CAST(n * 0.95 AS INTEGER) THEN latency_ms END) AS p95_latency_ms,
    MAX(CASE WHEN rn = CAST(n * 0.99 AS INTEGER) THEN latency_ms END) AS p99_latency_ms,
    ROUND(
        (SELECT SUM(CASE WHEN latency_ms > 100 THEN 1.0 ELSE 0 END) FROM risk_score_event) /
        (SELECT COUNT(*) FROM risk_score_event),
        4
    )                                                          AS pct_over_100ms_sla
FROM ranked;
```

**Expected Result:**
One row containing the total scored event count plus p50 / p95 / p99 latency and SLA-breach rate. In this dataset, p50 ≈ 100ms and p99 ≈ 175ms; the green-light condition is for production p99 to stay ≤ 100ms.

---

### Query 2: Top Revenue Customers by Contract Value

**Business Context:**
The CFO needs a quick view of NovaRisk's largest paying customers. Used for board reporting and to prioritize Customer Success resources — losing one of the top-3 customers would meaningfully dent ARR.

**Category:** Aggregation
**Difficulty:** Beginner
**Business Role:** Executive

**Approach:**
The easiest one in the set: `client_institution` joined to `industry_vertical` to pick up the vertical name, sorted by `annual_contract_value_usd` desc, top 5. `WHERE is_active = 1` filters out churned customers. Contract tenure in days is computed as `JULIANDAY('2026-06-05') - JULIANDAY(contract_start_date)` — note that the reference date is hard-coded as a literal rather than `DATE('now')`, so the results stay reproducible. No aggregation or window functions needed.

```sql
SELECT
    ci.legal_name,
    iv.code                                AS vertical,
    ci.annual_contract_value_usd,
    ROUND(JULIANDAY('2026-06-05') - JULIANDAY(ci.contract_start_date)) AS days_tenure
FROM client_institution ci
JOIN industry_vertical iv ON iv.id = ci.industry_vertical_id
WHERE ci.is_active = 1
ORDER BY ci.annual_contract_value_usd DESC
LIMIT 5;
```

**Expected Result:**
Five customers ranked by ACV, along with their vertical and contract tenure in days. Skyline National Bank ($1.2M) typically sits at the top.

---

### Query 3: Decision Distribution per Customer

**Business Context:**
A Customer Success Manager preparing a Quarterly Business Review (QBR) needs to show the customer how their APPROVE / REVIEW / DECLINE / STEP_UP decisions are distributed. Banks care a lot about this — too many DECLINEs hurts customer experience; too many APPROVEs means fraud is slipping through.

**Category:** Join + Aggregation
**Difficulty:** Beginner
**Business Role:** Manager

**Approach:**
The decision value (decision_id) lives on `risk_score_event`, but "customer" has to be joined back via `transaction → account → client_institution` (the scoring event doesn't carry the customer directly). Then join `risk_decision_dim` to translate decision_id into the human-readable APPROVE/REVIEW/.... One output row = one customer × one decision's event count. GROUP BY all three columns `ci.id, ci.legal_name, rd.code` so that every non-aggregate column in SELECT also appears in GROUP BY (this also runs cleanly in Postgres strict mode).

```sql
SELECT
    ci.id                                  AS client_id,
    ci.legal_name,
    rd.code                                AS decision,
    COUNT(*)                               AS event_count
FROM risk_score_event rse
JOIN "transaction" t  ON t.id  = rse.transaction_id
JOIN account a        ON a.id  = t.source_account_id
JOIN client_institution ci ON ci.id = a.client_institution_id
JOIN risk_decision_dim rd  ON rd.id = rse.decision_id
GROUP BY ci.id, ci.legal_name, rd.code
ORDER BY ci.legal_name, event_count DESC;
```

**Expected Result:**
For each of the 12 customers, event counts across the four decision buckets. APPROVE is usually dominant (~60-70%), DECLINE is the smallest slice (~5-8%). Exact ratios will shift slightly with the post-boost score distribution (see ER document §7.3).

---

### Query 4: Alert Volume by Fraud Type

**Business Context:**
A fraud analyst preparing the weekly threat briefing needs to know which fraud types (wire fraud, account takeover, deepfake onboarding, etc.) generated the most alerts this quarter. That answer drives where the team focuses next week.

**Category:** Join + Aggregation
**Difficulty:** Beginner
**Business Role:** Analyst

**Approach:**
Two-table join: `alert` joined to `fraud_type_dim`. One output row = total alert count for one fraud type. Carry `severity_weight` out alongside for interpretive sorting. GROUP BY both `code` and `severity_weight` (they're 1:1, so grouping on both doesn't change the grain). This is beginner-level aggregation with no fan-out risk, because `alert` references `fraud_type_dim` directly as a many-to-one.

```sql
SELECT
    ft.code                                AS fraud_type,
    ft.severity_weight,
    COUNT(*)                               AS alert_count
FROM alert al
JOIN fraud_type_dim ft ON ft.id = al.fraud_type_id
GROUP BY ft.code, ft.severity_weight
ORDER BY alert_count DESC;
```

**Expected Result:**
9 fraud types sorted by alert volume. Wire fraud and card_not_present typically lead, since they correspond to the most common transaction types.

---

### Query 5: False-Positive Rate by Detection Rule

**Business Context:**
The Fraud Ops Manager needs to decide which rules to retire. A rule that fires thousands of alerts that all turn out to be false positives is worse than no rule at all — it burns analyst time. This query ranks rules by FP rate so the manager can act.

**Category:** Aggregation + Filter
**Difficulty:** Medium
**Business Role:** Manager

**Approach:**
The core idea is to look only at "alerts fired by rules," so use an INNER JOIN between `alert` and `detection_rule` (which automatically excludes pure-ML alerts where `detection_rule_id IS NULL`). FP rate = false positives / adjudicated alerts, computed with `SUM(CASE WHEN is_true_positive = 0 …)` and `NULLIF(…)` for divide-by-zero protection. `WHERE is_true_positive IS NOT NULL` keeps the denominator from including alerts that haven't been adjudicated yet (status OPEN/IN_REVIEW/ESCALATED). `HAVING alerts_raised >= 3` filters out rules with tiny samples, so we don't draw a "100% FP" conclusion from one or two alerts.

```sql
SELECT
    dr.rule_code,
    dr.threshold_score,
    COUNT(*)                                                          AS alerts_raised,
    SUM(CASE WHEN al.is_true_positive = 0 THEN 1 ELSE 0 END)          AS false_positives,
    SUM(CASE WHEN al.is_true_positive = 1 THEN 1 ELSE 0 END)          AS true_positives,
    ROUND(
        SUM(CASE WHEN al.is_true_positive = 0 THEN 1.0 ELSE 0 END) /
        NULLIF(SUM(CASE WHEN al.is_true_positive IS NOT NULL THEN 1 ELSE 0 END), 0),
        3
    )                                                                  AS fp_rate
FROM alert al
JOIN detection_rule dr ON dr.id = al.detection_rule_id
WHERE al.is_true_positive IS NOT NULL
GROUP BY dr.rule_code, dr.threshold_score
HAVING alerts_raised >= 3
ORDER BY fp_rate DESC, alerts_raised DESC;
```

**Expected Result:**
Rules sorted from highest false-positive rate to lowest. `VPN_PLUS_GEO_MISMATCH` and `CARD_TESTING_BURST` are typically the noisiest — candidates for threshold tuning or retirement.

> **Scope note:** this query *deliberately* excludes pure-ML alerts (`detection_rule_id IS NULL`). The question is "which rule should I retire," so only count rule-fired alerts. To audit pure-ML quality, change the INNER JOIN to a `GROUP BY` that buckets `rule IS NULL` separately.

---

### Query 6: Average Investigation Time per Analyst

**Business Context:**
The Fraud Ops Manager wants to know which analysts are the fastest investigators (hours from case open to case close). Used for performance review and to identify who needs more training.

**Category:** Date Diff + Aggregation
**Difficulty:** Medium
**Business Role:** Manager

**Approach:**
`investigation_case` joined to `analyst`, restricted to closed cases (`WHERE closed_at IS NOT NULL`). Investigation duration is computed as `(JULIANDAY(closed_at) - JULIANDAY(opened_at)) * 24` hours and then averaged. One output row = one analyst. `HAVING closed_cases >= 1` guarantees at least one sample before they appear. Ascending sort puts the fastest at the top — but when interpreting, remember that "fast" can mean either skilled (good) or skipping due diligence (bad).

```sql
SELECT
    an.id                                                          AS analyst_id,
    an.full_name,
    an.seniority,
    COUNT(ic.id)                                                   AS closed_cases,
    ROUND(AVG((JULIANDAY(ic.closed_at) - JULIANDAY(ic.opened_at)) * 24), 1) AS avg_hours_to_close
FROM investigation_case ic
JOIN analyst an ON an.id = ic.assigned_analyst_id
WHERE ic.closed_at IS NOT NULL
GROUP BY an.id, an.full_name, an.seniority
HAVING closed_cases >= 1
ORDER BY avg_hours_to_close ASC;
```

**Expected Result:**
Analysts ranked by case-close speed. You can spot fast learners (good) and analysts possibly skipping due diligence (bad).

---

### Query 7: Coordinated Attack Ring Detection (Shared Device Fingerprints)

**Business Context:**
The signature ability of unsupervised ML is **coordinated attack ring detection** — many "unrelated" accounts that are actually being operated from the same device. A fraud analyst suspects a ring spanning three of this bank's customers. This query lists every device used by more than one end_user in the last 90 days, ranked by how many users sit behind that device.

**Category:** Self-Join / Subquery (graph style)
**Difficulty:** Advanced
**Business Role:** Analyst

**Approach:**
This is a graph-style problem. First, in CTE `device_user_pairs`, **deduplicate** (device, user, customer) triples (`SELECT DISTINCT`), or multiple sessions from one user on one device would double-count and inflate the distinct-user count. Then aggregate per device with `COUNT(DISTINCT end_user_id)` (how many users sit behind it) and `COUNT(DISTINCT client_institution_id)` (how many banks it spans). `HAVING distinct_users >= 2` keeps only shared devices. The strongest signal is a device that spans 2+ banks — which is exactly the value the Data Consortium delivers and that a single bank can't see on its own.

```sql
WITH device_user_pairs AS (
    SELECT DISTINCT
        ds.device_id,
        ds.end_user_id,
        eu.client_institution_id
    FROM device_session ds
    JOIN end_user eu ON eu.id = ds.end_user_id
)
SELECT
    d.id                                  AS device_id,
    d.fingerprint_hash,
    d.device_type,
    d.is_emulator,
    COUNT(DISTINCT dup.end_user_id)       AS distinct_users,
    COUNT(DISTINCT dup.client_institution_id) AS distinct_clients
FROM device_user_pairs dup
JOIN device d ON d.id = dup.device_id
GROUP BY d.id
HAVING distinct_users >= 2
ORDER BY distinct_users DESC, distinct_clients DESC
LIMIT 25;
```

**Expected Result:**
A list of devices used by 2+ end_users. The strongest signal: a device driving 3+ accounts across 2+ different banks — very likely a fraud ring (the cross-institution view is exactly the Data Consortium's value proposition).

---

### Query 8: High-Risk Corridor Exposure per Customer

**Business Context:**
NovaRisk's CRO needs to know which client institutions are most exposed in high-risk corridors (Iran, North Korea, Syria, Belarus, Russia, Myanmar). These require enhanced AML review and may trigger regulator inquiries.

**Category:** Aggregation + Filter
**Difficulty:** Beginner
**Business Role:** Executive

**Approach:**
Join `transaction → account → client_institution` back to the customer, filter `WHERE is_high_risk_corridor = 1` for corridor traffic only, then `SUM(amount_usd)` per customer. One output row = corridor exposure per customer. Large banks naturally sit at the top (more traffic); the real red flag is a small customer with disproportionate exposure, so interpret the numbers against the customer's total traffic, not just the absolute amount. `is_high_risk_corridor` is a boolean, so the filter is cheap.

```sql
SELECT
    ci.id                                    AS client_id,
    ci.legal_name,
    COUNT(*)                                 AS high_risk_txn_count,
    ROUND(SUM(t.amount_usd), 2)              AS high_risk_exposure_usd,
    ROUND(AVG(t.amount_usd), 2)              AS avg_amount_usd
FROM "transaction" t
JOIN account a ON a.id = t.source_account_id
JOIN client_institution ci ON ci.id = a.client_institution_id
WHERE t.is_high_risk_corridor = 1
GROUP BY ci.id, ci.legal_name
ORDER BY high_risk_exposure_usd DESC;
```

**Expected Result:**
Customers ranked by total USD exposure to high-risk countries. The top of this list will be your biggest banks (more traffic), but a small customer with disproportionate exposure is a red flag worth a phone call to verify.

---

### Query 9: Daily Transaction and Alert Trend

**Business Context:**
A data analyst building a weekly fraud-ops dashboard needs day-by-day transaction count, alert count, and alert rate. Sudden spikes typically correlate with fraud waves (e.g. weekend card-testing bursts).

**Category:** Date / Time series + Aggregation
**Difficulty:** Medium
**Business Role:** Analyst

**Approach:**
Time-series problem. `transaction` LEFT JOIN `alert` — LEFT because the vast majority of transactions have no alert; switching to INNER would erase entire "no-alert days" and distort the trend. Truncate the timestamp to day with `DATE(initiated_at)`, and use `COUNT(DISTINCT t.id)` and `COUNT(DISTINCT al.id)` to count transactions and alerts separately. `COUNT(DISTINCT)` is mandatory: one transaction can carry multiple alerts, and a plain `COUNT(*)` would double-count due to the join fan-out. GROUP BY day, sort ascending.

```sql
SELECT
    DATE(t.initiated_at)                                       AS day,
    COUNT(DISTINCT t.id)                                       AS txn_count,
    COUNT(DISTINCT al.id)                                      AS alert_count,
    ROUND(COUNT(DISTINCT al.id) * 1.0 / COUNT(DISTINCT t.id), 4) AS alert_rate
FROM "transaction" t
LEFT JOIN alert al ON al.transaction_id = t.id
WHERE t.initiated_at >= DATE('2026-05-01')
GROUP BY DATE(t.initiated_at)
ORDER BY day;
```

**Expected Result:**
One row per day in May/June 2026, with transaction count, alert count, and alert rate. Alert rate generally hovers in the 15-25% range, but some days may spike.

---

### Query 10: Top-5 SAR-Filing Analysts per Customer

**Business Context:**
The Compliance Manager wants to recognize and reward analysts who actually push cases all the way to a regulator filing — the highest-value activity on the team. A window function ranks the best filers per customer; we keep the top 5 per customer.

**Category:** Window Function (RANK + top-N per group)
**Difficulty:** Medium
**Business Role:** Manager

**Approach:**
Classic top-N-per-group problem, solved with a window function. First compute each analyst's SAR count in CTE `analyst_sar` — use LEFT JOIN all the way from `analyst → investigation_case → sar_report`, otherwise an analyst who's never filed a SAR would disappear before they could even be counted (the outer `WHERE sar_count > 0` would still drop them at the end, but LEFT ensures `COUNT(sar.id)` is computed correctly for every analyst). Then use `RANK() OVER (PARTITION BY client ORDER BY sar_count DESC)` to rank within each customer; the outer `WHERE rank_in_client <= 5` keeps the top 5 per group. SARs are rare in this snapshot (~9 total), so only a few customers have results.

```sql
WITH analyst_sar AS (
    SELECT
        an.id              AS analyst_id,
        an.full_name,
        ci.legal_name      AS client,
        COUNT(sar.id)      AS sar_count
    FROM analyst an
    JOIN client_institution ci ON ci.id = an.client_institution_id
    LEFT JOIN investigation_case ic ON ic.assigned_analyst_id = an.id
    LEFT JOIN sar_report sar         ON sar.case_id = ic.id
    GROUP BY an.id, an.full_name, ci.legal_name
),
ranked AS (
    SELECT
        client,
        full_name,
        sar_count,
        RANK() OVER (PARTITION BY client ORDER BY sar_count DESC) AS rank_in_client
    FROM analyst_sar
    WHERE sar_count > 0
)
SELECT *
FROM ranked
WHERE rank_in_client <= 5
ORDER BY client, rank_in_client;
```

**Expected Result:**
Top-5 analysts per customer ranked by SAR filings. In the current dataset (only 9 SARs in this snapshot), only a handful of customers return any rows at all.

---

### Query 11: Customer Risk Rating vs Actual Fraud Rate

**Business Context:**
The model-risk team wants to validate whether the CDD (Customer Due Diligence) risk rating assigned at onboarding (LOW/MEDIUM/HIGH) actually predicts who later commits fraud. If HIGH-rated customers show the same confirmed-fraud rate as LOW-rated ones, the CDD model is broken.

**Category:** CTE + Aggregation
**Difficulty:** Advanced
**Business Role:** Analyst

**Approach:**
This query aligns the onboarding-time `customer_risk_rating` with after-the-fact actual fraud. CTE `user_fraud` chains LEFT JOIN all the way from `end_user` to `account → transaction → alert`, counting transactions and confirmed-fraud alerts per user — **LEFT JOIN the whole chain**, or users with no transactions / no alerts would be dropped and the fraud rate would be wildly overestimated. Then the outer query aggregates by rating and computes "confirmed fraud per 1,000 transactions" to normalize for scale (absolute counts aren't comparable, because user counts and transaction volumes differ a lot across ratings). Ideally this metric rises monotonically from LOW → MEDIUM → HIGH; if it doesn't, the CDD model has no predictive power and needs to be rebuilt.

```sql
WITH user_fraud AS (
    SELECT
        eu.id,
        eu.customer_risk_rating,
        COUNT(DISTINCT t.id)                                  AS txn_count,
        COUNT(DISTINCT CASE WHEN al.is_true_positive = 1 THEN al.id END) AS confirmed_fraud_alerts
    FROM end_user eu
    LEFT JOIN account a ON a.end_user_id = eu.id
    LEFT JOIN "transaction" t ON t.source_account_id = a.id
    LEFT JOIN alert al ON al.transaction_id = t.id
    GROUP BY eu.id
)
SELECT
    customer_risk_rating,
    COUNT(*)                                                                          AS users,
    SUM(txn_count)                                                                    AS total_txns,
    SUM(confirmed_fraud_alerts)                                                       AS total_confirmed_fraud,
    ROUND(SUM(confirmed_fraud_alerts) * 1.0 / NULLIF(SUM(txn_count), 0) * 1000, 3)    AS confirmed_fraud_per_1k_txn
FROM user_fraud
GROUP BY customer_risk_rating
ORDER BY confirmed_fraud_per_1k_txn DESC;
```

**Expected Result:**
Three rows, one per rating. Ideally fraud-per-1k-txn rises monotonically from LOW → MEDIUM → HIGH; if it doesn't, the CDD model needs to be rebuilt.

---

### Query 12: SAR Narratives that Hit the Sanctions Watchlist

**Business Context:**
The AML Compliance Officer needs all SARs that were filed because of a sanctions-watchlist hit, along with the matched entity name. These need extra-careful review, and if the watchlist updates they may need to be refiled.

**Category:** Inner Join (on a nullable FK — to select only the hits)
**Difficulty:** Medium
**Business Role:** Operations

**Approach:**
The canonical use of an INNER JOIN on a nullable foreign key: `sar_report` joined to `sanctions_watchlist ON sw.id = sar.watchlist_match_id`. Because it's an INNER JOIN, SARs with `watchlist_match_id IS NULL` are automatically excluded — which is exactly what we want: "only SARs with a watchlist hit." One output row = one watchlist-hit SAR paired with the matched entity. No aggregation needed; sort by `filed_at` desc so the Compliance Officer sees the newest first.

```sql
SELECT
    sar.filing_reference,
    sar.filed_at,
    sar.total_reported_amount_usd,
    sw.list_source,
    sw.listed_name,
    sw.risk_tier
FROM sar_report sar
JOIN sanctions_watchlist sw ON sw.id = sar.watchlist_match_id
ORDER BY sar.filed_at DESC;
```

**Expected Result:**
SARs paired with the sanctions-watchlist entity that triggered them. Some SARs inherit the watchlist match from the underlying alert; others get assigned one at filing time. SARs with `watchlist_match_id IS NULL` are excluded.

---

### Query 13: Vera AI Agent Tool Usage and Cost

**Business Context:**
Finance wants to attribute LLM compute cost down to Vera's four sub-agents and the specific tools they call. If the Investigation agent's `graph_link_explore` tool is consuming the most tokens, that's where to invest in caching or model distillation.

**Category:** Aggregation
**Difficulty:** Beginner
**Business Role:** Finance

**Approach:**
Single-table aggregation: `agent_interaction_log` GROUP BY both `agent_name` and `tool_called`. Each output row = invocation count, avg/total tokens, avg latency, and approval rate for one (sub-agent, tool) combination. Approval rate is computed with `AVG(CASE WHEN human_approved = 1 THEN 1.0 ELSE 0 END)` (booleans cast to 0/1 then averaged). Sort by `total_tokens` desc, so the most-expensive tools float to the top — those are the priority targets for caching or distillation.

```sql
SELECT
    agent_name,
    tool_called,
    COUNT(*)                          AS invocations,
    ROUND(AVG(tokens_used), 0)        AS avg_tokens,
    SUM(tokens_used)                  AS total_tokens,
    ROUND(AVG(latency_ms), 0)         AS avg_latency_ms,
    ROUND(AVG(CASE WHEN human_approved = 1 THEN 1.0 ELSE 0 END), 3) AS approval_rate
FROM agent_interaction_log
GROUP BY agent_name, tool_called
ORDER BY total_tokens DESC;
```

**Expected Result:**
Tools sorted by total token consumption. Investigation tools dominate, because cases drive the most usage. Approval rate across all tools is about 92%.

---

### Query 14: Champion vs Challenger Model Decision Drift

**Business Context:**
The MLOps team is A/B-testing a new "challenger" model against the production "champion." Most transactions are routed to the champion, but about 15% of traffic is mirrored to the challenger. They want the two models' decline rates per customer side by side — if the challenger declines significantly more (or less) than the champion, that's the signal needed for a promotion decision.

**Category:** CTE + Conditional Aggregation + Join
**Difficulty:** Advanced
**Business Role:** Analyst

**Approach:**
Advanced conditional aggregation. CTE `scored` labels every scored event with its customer (via `ml_model → transaction → account → client_institution`) and its champion/challenger role; CTE `agg` then counts decisions per (customer × role). The final query puts the champion row and challenger row for the same customer side by side via a self-join (LEFT JOIN on `client_id`) and computes the decline-rate gap. **The key is rates, not absolute counts** — traffic shares are roughly 85/15, so raw counts aren't comparable. Customer rows with very small `challenger_n` should be flagged for cautious interpretation.

```sql
-- For each customer, pull champion-vs-challenger decision counts, then compute the decline-rate gap.
-- Note: traffic shares differ (~85/15), so look at RATES, not raw counts.
WITH scored AS (
    SELECT
        ci.id              AS client_id,
        ci.legal_name      AS client,
        CASE WHEN m.is_champion = 1 THEN 'champion' ELSE 'challenger' END AS model_role,
        m.model_family,
        rd.code            AS decision
    FROM risk_score_event rse
    JOIN ml_model m            ON m.id  = rse.ml_model_id
    JOIN risk_decision_dim rd  ON rd.id = rse.decision_id
    JOIN "transaction" t       ON t.id  = rse.transaction_id
    JOIN account a             ON a.id  = t.source_account_id
    JOIN client_institution ci ON ci.id = a.client_institution_id
),
agg AS (
    SELECT
        client_id,
        client,
        model_role,
        COUNT(*)                                                    AS n,
        SUM(CASE WHEN decision = 'DECLINE' THEN 1 ELSE 0 END)       AS declines,
        SUM(CASE WHEN decision = 'REVIEW'  THEN 1 ELSE 0 END)       AS reviews,
        SUM(CASE WHEN decision = 'APPROVE' THEN 1 ELSE 0 END)       AS approves
    FROM scored
    GROUP BY client_id, client, model_role
)
SELECT
    ch.client,
    ch.n                                AS champion_n,
    cl.n                                AS challenger_n,
    ROUND(ch.declines * 1.0 / NULLIF(ch.n, 0), 4) AS champion_decline_rate,
    ROUND(cl.declines * 1.0 / NULLIF(cl.n, 0), 4) AS challenger_decline_rate,
    ROUND(
        (cl.declines * 1.0 / NULLIF(cl.n, 0)) -
        (ch.declines * 1.0 / NULLIF(ch.n, 0)),
        4
    )                                   AS decline_rate_gap
FROM (SELECT * FROM agg WHERE model_role = 'champion')   ch
LEFT JOIN (SELECT * FROM agg WHERE model_role = 'challenger') cl
       ON cl.client_id = ch.client_id
ORDER BY ABS(COALESCE(decline_rate_gap, 0)) DESC;
```

**Expected Result:**
One row per customer. A positive `decline_rate_gap` means the challenger is *stricter* than the champion; a negative value means looser. The MLOps team watches the absolute-value gap — a small gap (e.g. ±2pp) is safe to promote; a large gap flags a model-behavior change worth investigating. Some customers' `challenger_n` may be very small in the current sample — those rows need cautious interpretation.

---

### Query 15: Top-10 Accounts by DECLINE-Blocked Amount

**Business Context:**
An ops analyst wants the 10 accounts hit hardest in dollar terms by DECLINEs. These are either chronic fraud victims (a good thing — DECLINE blocked the loss) or false-positive victims (a bad thing — the bank needs to fix this before the customer churns).

**Category:** Aggregation + Sort
**Difficulty:** Beginner
**Business Role:** Operations

**Approach:**
`transaction` joined to `risk_score_event` joined to `risk_decision_dim`, with `AND rd.code = 'DECLINE'` directly in the join condition to keep only declined transactions. Then join `account → end_user → client_institution` to pick up the account holder and customer name. Aggregate `SUM(amount_usd)` per account, sort desc, top 10. One output row = total declined amount per account. The results may include chronic fraud victims (good, DECLINE blocked the loss) or false-positive victims (bad, fix before churn) — manual review is needed to tell them apart.

```sql
SELECT
    a.id                                  AS account_id,
    a.account_number_masked,
    eu.full_name,
    ci.legal_name                         AS client,
    COUNT(*)                              AS declined_txn_count,
    ROUND(SUM(t.amount_usd), 2)           AS declined_amount_usd
FROM "transaction" t
JOIN risk_score_event rse ON rse.transaction_id = t.id
JOIN risk_decision_dim rd ON rd.id = rse.decision_id AND rd.code = 'DECLINE'
JOIN account a   ON a.id = t.source_account_id
JOIN end_user eu ON eu.id = a.end_user_id
JOIN client_institution ci ON ci.id = a.client_institution_id
GROUP BY a.id, a.account_number_masked, eu.full_name, ci.legal_name
ORDER BY declined_amount_usd DESC
LIMIT 10;
```

**Expected Result:**
The 10 most-blocked accounts together with their total DECLINE dollar amount. A starting point for analyst outreach and false-positive review.

---

### Query 16: True 7-Calendar-Day Rolling Alert Rate per Customer

**Business Context:**
The Fraud Ops Manager runs an ongoing monitoring dashboard. For each customer, what is the rolling 7-day alert count versus last week? A sudden 2x jump signals a wave of fraud hitting that bank. This query must sum across **7 consecutive calendar days**, not "the last 7 days that had at least one alert" — the latter hides quiet days that should pull the trend toward zero.

**Category:** Recursive CTE (calendar) + Window Function
**Difficulty:** Advanced
**Business Role:** Analyst

**Approach:**
The hardest query of the set. The key trap: if you window only over "days that had alerts," quiet days get skipped entirely and the 7-day rolling sum can never decay to zero. The fix: a recursive CTE (`WITH RECURSIVE calendar`) generates a complete 90-day calendar, `CROSS JOIN` it to all customers to materialize a "customer × day" grid, then LEFT JOIN actual alerts and `COALESCE(…, 0)` to fill quiet days with 0. Only then does `SUM(…) OVER (PARTITION BY client ORDER BY day ROWS BETWEEN 6 PRECEDING AND CURRENT ROW)` equal a true 7-calendar-day rolling sum. Finally, only show the last 3 weeks to keep the dashboard readable.

```sql
-- Generate a calendar (90 days), cross join with all customers, left join alerts,
-- and fill quiet days with 0. This makes ROWS BETWEEN 6 PRECEDING equivalent to a
-- true 7-calendar-day rolling sum (including 0-alert days).
WITH RECURSIVE calendar(day) AS (
    SELECT DATE('2026-03-08')
    UNION ALL
    SELECT DATE(day, '+1 day') FROM calendar WHERE day < DATE('2026-06-05')
),
daily AS (
    SELECT
        ci.id                                AS client_id,
        ci.legal_name                        AS client,
        DATE(al.raised_at)                   AS day,
        COUNT(*)                             AS alert_count
    FROM alert al
    JOIN "transaction" t        ON t.id  = al.transaction_id
    JOIN account a              ON a.id  = t.source_account_id
    JOIN client_institution ci  ON ci.id = a.client_institution_id
    GROUP BY ci.id, ci.legal_name, DATE(al.raised_at)
),
filled AS (
    SELECT
        ci.id                                AS client_id,
        ci.legal_name                        AS client,
        c.day                                AS day,
        COALESCE(d.alert_count, 0)           AS alert_count
    FROM client_institution ci
    CROSS JOIN calendar c
    LEFT JOIN daily d
           ON d.client_id = ci.id AND d.day = c.day
)
SELECT
    client,
    day,
    alert_count,
    SUM(alert_count) OVER (
        PARTITION BY client
        ORDER BY day
        ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
    ) AS rolling_7d_alerts
FROM filled
WHERE day >= DATE('2026-05-15')   -- last 3 weeks for dashboard readability
ORDER BY client, day;
```

**Expected Result:**
Per-customer daily alert count plus a true 7-calendar-day trailing sum. Quiet days are explicitly shown as 0, so a 7-day sum dropping to 0 unambiguously means "no alerts at all last week" — not "no rows for last week in the table."

---

### Query 17: VPN Sessions Whose Country Doesn't Match the Account Country

**Business Context:**
An ops analyst doing pattern hunting wants every session where the user logged in via VPN and the IP-geolocated country doesn't match the account's registered country. The false-positive rate is high, but historically this is a strong signal for account takeover. (`device_session` doesn't carry sub-country geolocation, so we compare at country level; a true state-level comparison would need an IP-to-state lookup outside this dataset.)

**Category:** Join + Filter
**Difficulty:** Medium
**Business Role:** Operations

**Approach:**
`device_session` joined to `end_user`, filtered to `is_vpn = 1 AND geo_country <> eu.country`. One output row = one suspicious session. Note that the comparison is only at the **country grain** (no state-level IP geo in this table), so it's a coarse filter: lots of false positives, but historically VPN + geo mismatch is a strong account-takeover signal. Sort by `session_started_at` desc, top 50, for human step-up auth review.

```sql
SELECT
    ds.id                                AS session_id,
    eu.full_name,
    eu.country                           AS account_country,
    ds.geo_country                       AS session_country,
    ds.ip_address,
    ds.session_started_at
FROM device_session ds
JOIN end_user eu ON eu.id = ds.end_user_id
WHERE ds.is_vpn = 1
  AND ds.geo_country <> eu.country
ORDER BY ds.session_started_at DESC
LIMIT 50;
```

**Expected Result:**
Up to 50 sessions where a VPN was used and the geo country doesn't match the user's registered country. Each row is a candidate for step-up auth review.

---

### Query 18: High-Priority Cases Open More than 14 Days

**Business Context:**
The Compliance Lead wants every CRITICAL or HIGH priority case that's been open for more than 14 days without being closed. These get escalated to the Chief Compliance Officer. SLA breach territory.

**Category:** Date Diff + Filter
**Difficulty:** Medium
**Business Role:** Manager

**Approach:**
`investigation_case` joined to three dimension/entity tables: customer, case status, and analyst. Three filter conditions: `priority IN ('HIGH','CRITICAL')`, `closed_at IS NULL` (still open), and opened more than 14 days ago (`JULIANDAY('2026-06-05') - JULIANDAY(opened_at) > 14`). One output row = one overdue high-priority open case, with the assigned analyst's name so the lead can call them directly. The reference date is hard-coded as a literal to keep results reproducible. No aggregation.

```sql
SELECT
    ic.id                                                  AS case_id,
    ci.legal_name                                          AS client,
    cs.code                                                AS status,
    ic.priority,
    ic.opened_at,
    ROUND(JULIANDAY('2026-06-05') - JULIANDAY(ic.opened_at)) AS days_open,
    an.full_name                                           AS assigned_to,
    ic.total_exposure_usd
FROM investigation_case ic
JOIN client_institution ci ON ci.id = ic.client_institution_id
JOIN case_status_dim cs    ON cs.id = ic.case_status_id
JOIN analyst an            ON an.id = ic.assigned_analyst_id
WHERE ic.priority IN ('HIGH', 'CRITICAL')
  AND ic.closed_at IS NULL
  AND (JULIANDAY('2026-06-05') - JULIANDAY(ic.opened_at)) > 14
ORDER BY days_open DESC;
```

**Expected Result:**
A short list of overdue high-priority cases. The assigned analyst's name is also listed so the lead can call them directly.

---

### Query 19: Revenue Concentration — Top-3 Customer Share

**Business Context:**
The CFO's question to the board: how concentrated is NovaRisk's revenue? If 3 customers = 50% of ARR, that's serious concentration risk. Computed with a CTE plus a window function.

**Category:** CTE + Window Function
**Difficulty:** Advanced
**Business Role:** Finance

**Approach:**
CTE + window function. In CTE `ranked`, use `SUM(…) OVER ()` (empty window = whole table) to compute total ARR, and `RANK() OVER (ORDER BY ACV DESC)` to rank customers. The outer query computes each customer's share and uses `SUM(…) OVER (ORDER BY rk)` as a running total to compute the cumulative percentage. Reading the cumulative column tells you at a glance what the top-3 share is — about 41% in this dataset, which is on the high side and worth a concentration-risk callout in the board deck. The difference between `SUM() OVER ()` and `SUM() OVER (ORDER BY …)` (whole-table vs running total) is the testing point.

```sql
WITH ranked AS (
    SELECT
        legal_name,
        annual_contract_value_usd,
        SUM(annual_contract_value_usd) OVER ()                                              AS total_arr,
        RANK() OVER (ORDER BY annual_contract_value_usd DESC)                               AS rk
    FROM client_institution
    WHERE is_active = 1
)
SELECT
    legal_name,
    annual_contract_value_usd,
    ROUND(annual_contract_value_usd * 100.0 / total_arr, 2) AS pct_of_total_arr,
    ROUND(SUM(annual_contract_value_usd) OVER (ORDER BY rk) * 100.0 / total_arr, 2)
                                                            AS cumulative_pct
FROM ranked
ORDER BY rk;
```

**Expected Result:**
Each customer's share of total ARR plus cumulative percentage. Used to identify concentration risk — in this dataset the top-3 account for roughly **41%** of ARR (Skyline National Bank + Meridian Card Services + EquatorPay).

---

### Query 20: Pattern Search for "structuring" in SAR Narratives

**Business Context:**
An audit team is studying regulator enforcement memos about structuring (chopping deposits into amounts below the $10K reporting threshold). They need every SAR whose narrative mentions structuring.

**Category:** Pattern matching (LIKE)
**Difficulty:** Beginner
**Business Role:** Operations

**Approach:**
The simplest text-match query: single-table `sar_report`, `WHERE LOWER(narrative_summary) LIKE '%structuring%'`. `LOWER()` makes it case-insensitive. Use `SUBSTR(narrative_summary, 1, 200)` to grab an excerpt and keep output manageable. One output row = one SAR mentioning structuring. The audit team uses it to gather precedent before meeting with the regulator. Note that `LIKE '%…%'` with wildcards on both sides forces a full-table scan, but the table only has ~9 rows, so performance isn't a concern.

```sql
SELECT
    sar.filing_reference,
    sar.filed_at,
    sar.total_reported_amount_usd,
    sar.ai_drafted,
    SUBSTR(sar.narrative_summary, 1, 200) AS narrative_excerpt
FROM sar_report sar
WHERE LOWER(sar.narrative_summary) LIKE '%structuring%'
ORDER BY sar.filed_at DESC;
```

**Expected Result:**
All SARs whose narrative contains "structuring," with a 200-character excerpt. The audit team uses this to gather precedent before meeting with the regulator.

---

## Query Category Summary

| Category | Count | Query numbers |
|----------|-------|---------------|
| Aggregation | 4 | 2, 4, 13, 15 |
| Join Operations | 4 | 3, 8, 12, 17 |
| Window Functions | 4 | 1, 10, 16, 19 |
| Date/Time Analysis | 3 | 6, 9, 18 |
| Subqueries / CTEs | 4 | 7, 11, 14, 19 |
| Pattern / Text | 1 | 20 |

(Total > 20 because some queries belong to multiple categories — e.g. Q19 uses both a CTE and a window function.)

## Business Role Coverage

| Role | Count | Query numbers |
|------|-------|---------------|
| Executive | 2 | 2, 8 |
| Manager | 5 | 3, 5, 6, 10, 18 |
| Analyst | 6 | 4, 7, 9, 11, 14, 16 |
| Operations | 5 | 1, 12, 15, 17, 20 |
| Finance | 2 | 13, 19 |

## Difficulty Distribution

| Difficulty | Count | Query numbers |
|------------|-------|---------------|
| Beginner | 7 | 2, 3, 4, 8, 13, 15, 20 |
| Medium | 8 | 1, 5, 6, 9, 10, 12, 17, 18 |
| Advanced | 5 | 7, 11, 14, 16, 19 |

---

## Notes

- All queries have been verified against the packaged SQLite database (`fintech_real_time_fraud_aml_platform_high.sqlite`).
- The `transaction` table must always be double-quoted (`"transaction"`) because it's a SQLite reserved word.
- **Postgres / strict-SQL portability**: every non-aggregate column in SELECT also appears in GROUP BY (SQLite is lenient here, Postgres is not). Other portability swaps: `JULIANDAY()` → `EXTRACT(EPOCH FROM ...)` or `AGE()`, boolean literals (`1`/`0` → `TRUE`/`FALSE`), and `DATE(col, '+1 day')` → `col + INTERVAL '1 day'`.
