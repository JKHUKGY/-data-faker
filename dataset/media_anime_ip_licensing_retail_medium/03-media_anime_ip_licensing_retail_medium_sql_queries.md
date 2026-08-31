# Media & Entertainment — Anime IP Merchandise Licensing & Retail Sell-Through Analysis SQL Query Reference

## Overview

This document provides **20 business-facing SQL queries** for the `media_anime_ip_licensing_retail_medium` dataset. Each query mirrors a question that a stakeholder at Ember & Ash Licensing Group would genuinely ask while managing an anime IP licensing portfolio, auditing royalties, or monitoring channel compliance. For business context, company roles, industry background, and a glossary, see `01-media_anime_ip_licensing_retail_medium_business_context.md`; for table structure and column meanings, see `02-media_anime_ip_licensing_retail_medium_er_document.md`.

> **Reference date convention.** The dataset is anchored to a fixed `REFERENCE_DATE = 2026-06-30`. Queries that need "today" use the literal `'2026-06-30'` rather than `DATE('now')`, so results are reproducible and independent of execution time. If you re-anchor the dataset to a different reference date, replace this literal everywhere it appears below.

## How to Use This Document

This document is written for a new data analyst who has just finished reading the business context document (`01-...business_context.md`) and the ER document (`02-...er_document.md`) and is ready to start analyzing. Think of it as a project handoff: the VP of Licensing has handed you these 20 questions, and your job this week is to work through them one by one and understand why they're written the way they are.

Every query follows the same **five-part structure**:

1. **Business context** — who's asking, why they're asking, what decision the answer needs to support, and why it's urgent right now.
2. **Category / Difficulty / Business role** — three quick tags that help you gauge what kind of SQL this exercises and which role at the company it maps to.
3. **Approach** — before you look at the SQL, this section walks through which tables you'll need to touch, how to join them, what grain to aggregate to, why (or why not) to use a CTE / window function / subquery, and which SQLite-specific pitfalls to avoid. This section is the real learning content.
4. **SQL code** — runnable directly against the SQLite database produced by the generator.
5. **Expected result notes** — what the result set looks like, which key numbers map to which business trap, and what to do next once you have the results.

Two usage notes:

- **Every query maps back to a business question.** There's a "business question → query" mapping table at the end of the document; think through which of Q1–Q5 a query is answering before you read the SQL.
- **SQL here is meant to be read and learned from, not just run.** The Approach sections explain "why it's written this way"; the real skill is in understanding the direction of each join, the grain of each aggregation, and the choice of measurement basis — not just getting a number to come out.

---

## Query Index

| # | Title | Business Role | Category | Difficulty |
|---|------|----------|------|------|
| 1 | Retail sell-through ranking by IP x category | Retail Channel Analyst | Aggregation + Join | Intermediate |
| 2 | Licensee royalty underreporting leaderboard | Royalty Audit Specialist | Aggregation + Join | Intermediate |
| 3 | Popularity-to-sell-through lag: premiere event alignment | Retail Channel Analyst | CTE + Date Analysis | Advanced |
| 4 | Unauthorized channel distribution detection | Director of Royalty Compliance | Join + Aggregation | Intermediate |
| 5 | Minimum guarantee pacing tracker | Licensing Manager | CTE + Aggregation | Advanced |
| 6 | Account manager portfolio load dashboard | Director of Licensing | Aggregation + Join | Basic |
| 7 | Compliance score vs. audit outcome consistency check | Royalty Audit Specialist | Aggregation + Join | Intermediate |
| 8 | Category royalty rate deviation from benchmark | Licensing Manager | Aggregation | Basic |
| 9 | Licensee brand name vs. signed category mismatch detection | VP of Licensing | Pattern Matching + Join | Intermediate |
| 10 | Quarterly new-agreement signing pace trend | VP of Licensing | Date Aggregation | Basic |
| 11 | Top 10 near-threshold unconfirmed underreport risk agreements | Royalty Audit Specialist | CTE + Window Function | Advanced |
| 12 | Post-launch sell-through ramp curve | Retail Channel Analyst | Date + Aggregation | Intermediate |
| 13 | Territory scope vs. minimum guarantee scale relationship | Senior Licensing Manager | Aggregation | Basic |
| 14 | Top 5 best- / worst-selling SKUs | Retail Channel Analyst | Window Function | Intermediate |
| 15 | Renewal decision list for agreements expiring in the next 6 months | Licensing Manager | CTE + Date Analysis | Intermediate |
| 16 | Composite licensee risk scorecard | Director of Royalty Compliance | CTE + Aggregation | Advanced |
| 17 | Online vs. offline channel sell-through comparison | Retail Channel Analyst | Aggregation + Join | Basic |
| 18 | Royalty report submission timeliness analysis | Royalty Audit Specialist | Date Calculation | Basic |
| 19 | IP popularity tier vs. agreement scale relationship | VP of Licensing | Aggregation + Join | Intermediate |
| 20 | Composite renewal priority score | VP of Licensing | CTE + Window Function | Advanced |

---

## Query Bodies

### Query 1: Retail sell-through ranking by IP x category

**Business context:**
The Retail Channel Analyst is preparing materials for the quarterly portfolio review. The VP of Licensing wants to know: among the 117 license agreements signed in the past year-plus, which "IP x category" combinations are genuinely selling through at retail and deserve priority renewal at longer terms or broader scope when they come up for renewal, and which combinations have been persistently weak and should be considered for non-renewal. This is the opening slide of the entire quarterly review deck; every renewal recommendation that follows needs to trace back to this ranking table.

**Category:** Aggregation + Join
**Difficulty:** Intermediate
**Business Role:** Retail Channel Analyst

**Approach:**
The analysis grain here is "one row per IP x category," but the raw sales data in `pos_sell_through` is at the "SKU x channel x week" grain, so you need to pass through four layers of JOIN — `anime_ip → license_agreement → product_sku → pos_sell_through` — to roll weekly sales records up to IP x category, then join `product_category` once more to get the category name. Because one IP can be licensed to multiple categories through different agreements, you need `GROUP BY ai.id, pc.id` rather than just `GROUP BY ai.id` to preserve the category dimension. INNER JOIN is safe throughout here — as long as a SKU exists, it necessarily joins all the way back to an IP and a category, so there are no orphan rows that need protecting with a LEFT JOIN. No window function or subquery is needed; a single GROUP BY + ORDER BY gets it done.

```sql
-- Rank IP x category combinations by total sell-through volume and revenue
SELECT
    ai.title,
    pc.category_name,
    ai.popularity_tier,
    SUM(p.units_sold) AS total_units_sold,
    ROUND(SUM(p.net_wholesale_revenue_usd), 2) AS total_wholesale_revenue
FROM anime_ip ai
JOIN license_agreement la ON la.anime_ip_id = ai.id
JOIN product_category pc ON pc.id = la.product_category_id
JOIN product_sku s ON s.license_agreement_id = la.id
JOIN pos_sell_through p ON p.product_sku_id = s.id
GROUP BY ai.id, pc.id
ORDER BY total_units_sold DESC
LIMIT 10;
```

**Expected result notes:**
Each row in the result set is one IP x category combination, sorted descending by total volume. The top 10 are almost entirely dominated by the **Collectible Trading Cards** category — `Petalfall` (a breakout-tier IP) ranks first with about 106,000 units and roughly $821,000 in wholesale revenue, followed closely by `Sakura Static`, `Whispering Gears`, and `Rustlight`, all above 70,000 units. This isn't a coincidence: the trading card category's baseline repeat-purchase frequency (the generator's `CATEGORY_BASE_WEEKLY_UNITS`) is inherently much higher than other categories. The Retail Channel Analyst should recommend that, on the renewal priority list, trading card IP combinations get longer terms or broader channel scope on renewal; management should also be reminded that this ranking naturally favors high-frequency repeat-purchase categories, so "which IP is most worth investing in" should be evaluated within a category, not by comparing raw unit totals across categories.

---

### Query 2: Licensee royalty underreporting leaderboard

**Business context:**
Every quarter, the Royalty Audit Specialist has to produce a list of "suspected underreporting licensees" for the Director of Royalty Compliance. The company recently upgraded its audit process — instead of just spot-checking, it now uses retail point-of-sale data to back into what each licensee "should" owe in royalties and compares that against what they actually self-reported. She needs a list ranked by variance magnitude to determine whether the problem is isolated one-off mistakes by individual licensees, or a systematic pattern across a whole group of them.

**Category:** Aggregation + Join
**Difficulty:** Intermediate
**Business Role:** Royalty Audit Specialist

**Approach:**
The core of this query is aggregating `royalty_audit_finding.variance_pct` (the "POS-derived royalty vs. self-reported royalty" variance percentage, already computed at generation time) by licensee. The path is `licensee → license_agreement → royalty_report → royalty_audit_finding`, and all four tables can be strictly INNER JOINed following the FK chain — because `royalty_audit_finding` and `royalty_report` are enforced as a 1:1 relationship, there are no orphan rows and no LEFT JOIN is needed. The aggregation grain is "one row per licensee," using `AVG(variance_pct)` to see the average magnitude of the discrepancy, and `SUM(CASE WHEN audit_status='confirmed_underreport' THEN 1 ELSE 0 END)` to count exactly how many times this licensee has been formally determined to be underreporting. `ORDER BY avg_variance_pct DESC` puts the largest discrepancies first.

```sql
-- Rank licensees by average royalty variance (POS-derived vs self-reported)
SELECT
    l.company_name,
    l.risk_tier,
    ROUND(l.compliance_score, 1) AS compliance_score,
    COUNT(raf.id) AS n_reports_audited,
    ROUND(AVG(raf.variance_pct), 2) AS avg_variance_pct,
    SUM(CASE WHEN raf.audit_status = 'confirmed_underreport' THEN 1 ELSE 0 END) AS n_confirmed_underreport,
    ROUND(SUM(raf.variance_usd), 2) AS total_underreported_royalty_usd
FROM licensee l
JOIN license_agreement la ON la.licensee_id = l.id
JOIN royalty_report rr ON rr.license_agreement_id = la.id
JOIN royalty_audit_finding raf ON raf.royalty_report_id = rr.id
GROUP BY l.id
ORDER BY avg_variance_pct DESC
LIMIT 10;
```

**Expected result notes:**
The result is not "isolated mistakes" — the top 7 are uniformly `risk_tier = 'risk'` licensees, with average variance ranging 12.2%-14.1% and confirmed_underreport counts ranging from 4 to 13 findings, with **Mcclain, Miller and Henderson Merch Studio** alone underreporting roughly $10,086 in cumulative royalties. Starting at rank 8, the numbers drop off sharply to the `clean` group's 0.5%-0.7% (normal reporting noise). This cliff confirms something important: underreporting is not randomly distributed — it's concentrated among a small group of licensees that already have low compliance scores (compliance_score < 50). Portfolio-wide, 17.9% of 369 reports were confirmed_underreport and 10.0% were flagged_for_review. Total POS-derived royalty ($1,443,655) exceeds total self-reported royalty ($1,381,232) by roughly $62,000 — that's about 4.32% of the POS-derived figure (using POS-derived royalty as the denominator, the same convention `variance_pct` uses), or about 4.52% if you instead use the self-reported figure as the denominator. Both numbers are correct — they're just different denominators, so don't mix them when quoting this gap. The audit specialist's next step: launch formal audit conversations with the top 7, and add stricter audit-right clauses in the next round of renewal negotiations.

---

### Query 3: Popularity-to-sell-through lag: premiere event alignment

**Business context:**
When a new season of an anime premieres, streaming popularity spikes immediately, but the Retail Channel Analyst has noticed that merchandise sales don't rise the same week — licensees and retailers alike complain that "the restock is arriving too late." The VP of Licensing wants to know exactly how long that lag is, so licensees can be told in advance to start restocking before the premiere, rather than waiting until sales data has already proven "this one's a hit" before ramping production. The question this query needs to answer with data: from popularity peak at premiere to a clear rise in retail sell-through, how many weeks does it typically take?

**Category:** CTE + Date Analysis
**Difficulty:** Advanced
**Business Role:** Retail Channel Analyst

**Approach:**
This is the easiest query in the entire document to get wrong. The **intuitive approach** — separately finding, for each IP, the single "highest popularity week" across its entire tracked history, then finding the "highest sales week" and comparing the two — is wrong: an IP's SKUs are added continuously over the two-year tracking window, so later weeks naturally have more SKUs on shelf, and the globally highest-selling week is very likely just the week with the most SKUs on sale at the time, with nothing to do with popularity. That's a hidden confounder. The correct approach is **event alignment**: treat each premiere week as "week 0," include only SKUs that were **already on shelf at premiere time** (`launch_date <= premiere_week`, excluding products that launched later and have nothing to do with this premiere), and re-align sales for the 4-16 weeks before and after the premiere by "weeks relative to premiere" (`weeks_since_premiere`), then average. The first CTE, `premieres`, identifies all premiere weeks; the second CTE, `eligible_skus`, identifies the SKUs that were already on shelf at premiere time; the third CTE, `event_aligned_sales`, computes the relative week number as a `JULIANDAY` difference divided by 7 and rounded — you must convert to `JULIANDAY` before subtracting; you cannot do arithmetic directly on `DATE`-typed values. Finally, group by `weeks_since_premiere` and average — wherever the peak lands is the lag.

```sql
-- Align retail sales to premiere-week zero point to detect the popularity-to-sales lag
WITH premieres AS (
    SELECT anime_ip_id, week_start_date AS premiere_week
    FROM streaming_popularity_index
    WHERE is_season_premiere_week = 1
),
eligible_skus AS (
    -- Map each product SKU to its IP and launch date (the shelf-time filter is applied in the JOIN below)
    SELECT s.id AS sku_id, la.anime_ip_id, s.launch_date
    FROM product_sku s
    JOIN license_agreement la ON la.id = s.license_agreement_id
),
event_aligned_sales AS (
    SELECT
        CAST(ROUND((JULIANDAY(p.week_start_date) - JULIANDAY(pr.premiere_week)) / 7.0) AS INTEGER) AS weeks_since_premiere,
        p.units_sold
    FROM premieres pr
    JOIN eligible_skus es
        -- keep only SKUs already on shelf at premiere time (excludes later unrelated launches)
        ON es.anime_ip_id = pr.anime_ip_id AND es.launch_date <= pr.premiere_week
    JOIN pos_sell_through p ON p.product_sku_id = es.sku_id
    WHERE p.week_start_date BETWEEN date(pr.premiere_week, '-28 days') AND date(pr.premiere_week, '+112 days')
)
SELECT
    weeks_since_premiere,
    ROUND(AVG(units_sold), 2) AS avg_weekly_units,
    COUNT(*) AS n_sku_weeks
FROM event_aligned_sales
GROUP BY weeks_since_premiere
ORDER BY weeks_since_premiere;
```

**Expected result notes:**
The result is a "relative week → average sales" curve. Sales hold a flat baseline of about 33-40 units/week from week -3 through week +5 around the premiere, start climbing at week 6, and peak at **weeks 8-10** (roughly 55-60 units/week, about 50%-75% above baseline), before gradually settling back down to a lower plateau after week 12. This confirms the supply chain lag exists, and it lands at **roughly 6-10 weeks** — compared to the company's current practice of "wait for popularity to show up, then chase production," this means licensees should start ramping production in the first week after a premiere is confirmed, rather than waiting two months for sales data to prove itself. **Note:** this analysis is only meaningful for breakout / mainstream tier IP, since only those have clear premiere events within the tracking window; niche-tier IP have no premiere spike and this methodology doesn't apply to them.

---

### Query 4: Unauthorized channel distribution detection

**Business context:**
The Director of Royalty Compliance recently received a complaint from a retailer: a licensee whose contract only authorizes "specialty store + convention pop-up" channels has product showing up in bulk on e-commerce marketplaces, priced well below the specialty-store price, undercutting the channel pricing structure. She needs a systematic list of unauthorized distribution rather than discovering problems reactively after a retailer complains — the data itself should be able to proactively surface every record of "sold into a channel the contract never authorized."

**Category:** Join + Aggregation
**Difficulty:** Intermediate
**Business Role:** Director of Royalty Compliance

**Approach:**
The core technique here is **LEFT JOIN + `WHERE ... IS NULL`**, the standard SQL pattern for an anti-join — determining that a record has no matching row in another table. Each `pos_sell_through` record is traced through `product_sku → license_agreement` to its agreement, then LEFT JOINed against `license_agreement_channel` on a **compound condition** (both `license_agreement_id` and `retail_channel_id` must match) — if that channel is genuinely within the agreement's authorized scope, `lac.id` will have a value; if there's no match (unauthorized), `lac.id` is NULL. `WHERE lac.id IS NULL` precisely isolates every unauthorized sales record. This LEFT JOIN must never be swapped for an INNER JOIN — that would filter out every unauthorized record outright, making the query result look "fully compliant" when it isn't. That's the crux of the trap: without this JOIN, unauthorized revenue would quietly get counted as "compliant revenue."

```sql
-- Detect POS sales occurring in channels not authorized by the license agreement
SELECT
    l.company_name,
    l.risk_tier,
    rc.channel_name AS unauthorized_channel,
    COUNT(*) AS n_weeks_with_unauthorized_sales,
    SUM(p.units_sold) AS total_unauthorized_units,
    ROUND(SUM(p.net_wholesale_revenue_usd), 2) AS total_unauthorized_revenue
FROM pos_sell_through p
JOIN product_sku s ON s.id = p.product_sku_id
JOIN license_agreement la ON la.id = s.license_agreement_id
JOIN licensee l ON l.id = la.licensee_id
JOIN retail_channel rc ON rc.id = p.retail_channel_id
LEFT JOIN license_agreement_channel lac
    ON lac.license_agreement_id = la.id AND lac.retail_channel_id = p.retail_channel_id
WHERE lac.id IS NULL
GROUP BY l.id, rc.id
ORDER BY total_unauthorized_revenue DESC
LIMIT 10;
```

**Expected result notes:**
The results are uniformly `risk_tier = 'risk'` licensees, and the unauthorized channels are **almost entirely online** — mostly **E-commerce Marketplace**, with about a quarter falling under **Direct-to-Consumer Online** (when an agreement already authorizes the e-commerce channel, leakage shows up on the DTC-online channel instead, which is why a row like Blake and Sons Toys, at roughly $31,000, appears under DTC-online). The top offender, **Mcclure, Ward and Lee Merch Studio**, has 135 week-instances and roughly $61,000 in unauthorized online sales on its own. Across the whole portfolio, about 6.85% of the `risk` group's POS records (about 6.6% of its revenue) occur in unauthorized channels, versus only about 0.59% for the `clean` group (normal noise level). This confirms the compliance director's instinct: e-commerce marketplaces, with their low barrier to entry and hard-to-trace supply chains, are the most common leakage point for unauthorized distribution. Next step: launch formal channel compliance conversations with the top offenders, and consider making the e-commerce channel a separately priced authorization option in renewal agreements, instead of leaving it a gray area.

---

### Query 5: Minimum guarantee pacing tracker

**Business context:**
At the end of every quarter, the Licensing Manager needs to run a "health check" across her contract portfolio — which agreements have royalty progress falling behind the time-based pace of the minimum guarantee (MG), signaling a need to reassess terms before the next renewal negotiation, or even consider non-renewal. Last quarter, one agreement reached its end date and the company only then discovered the licensee had paid only a fraction of the full-term minimum guarantee — nobody had been tracking the installment pace, and the window to intervene early had already closed. This query is about systematizing that "early warning."

**Category:** CTE + Aggregation
**Difficulty:** Advanced
**Business Role:** Licensing Manager

**Approach:**
The minimum guarantee is a "total contract-term amount," so you can't directly compare cumulative royalty as of `REFERENCE_DATE` against it — an agreement with half its term still remaining will naturally only have accumulated a fraction of the minimum guarantee, and that alone doesn't indicate a problem. The correct approach is **time-based proration**: first compute the "fraction of the contract elapsed so far," `elapsed_fraction = (REFERENCE_DATE − contract_start_date) / (contract_end_date − contract_start_date)`, multiply by the minimum guarantee to get `prorated_mg_target` ("how much should have been paid by now"), then divide actual cumulative royalty (`SUM(reported_royalty_due_usd)`, aggregated per agreement in a CTE called `royalty_to_date`) by that target to get `pacing_ratio`. `MIN(1.0, ...)` prevents an agreement that has run its full term from having an `elapsed_fraction` over 1. Only `contract_status = 'active'` agreements are included, since agreements that have already expired or terminated shouldn't still be judged on "catching up" — this filter condition is easy for a newcomer to miss, and missing it lets an expired agreement's `elapsed_fraction` sit permanently at 1.0, distorting the "behind pace" judgment.

**Another edge case that's easy to miss:** an active agreement that was signed recently and hasn't even completed its first 91-day reporting cycle yet has no row at all in `royalty_to_date`, so `pacing_ratio` would naturally compute to 0 — but that's a very different thing from "genuinely selling poorly and truly falling behind." It shouldn't be lumped into the "behind pace" warning list. That's why `royalty_to_date` needs to be a `JOIN`, not a `LEFT JOIN`: a `LEFT JOIN` would keep these "not yet due for a report" agreements in the result (backfilled to 0 via `COALESCE(..., 0)`), mixing them in with agreements that are genuinely delinquent; switching to `JOIN` means only agreements that have already submitted at least one report make it into the `pacing` CTE, so `pacing_ratio` only reflects agreements that "paid, but not enough," not agreements that "haven't come due yet."

```sql
-- Track cumulative royalty progress against the prorated minimum guarantee target
WITH royalty_to_date AS (
    SELECT license_agreement_id, SUM(reported_royalty_due_usd) AS cumulative_royalty_usd
    FROM royalty_report
    GROUP BY license_agreement_id
),
pacing AS (
    SELECT
        la.id,
        la.agreement_number,
        ai.title,
        l.company_name,
        la.minimum_guarantee_usd,
        rtd.cumulative_royalty_usd,
        MIN(1.0, CAST((JULIANDAY('2026-06-30') - JULIANDAY(la.contract_start_date)) AS REAL)
            / (JULIANDAY(la.contract_end_date) - JULIANDAY(la.contract_start_date))) AS elapsed_fraction
    FROM license_agreement la
    JOIN anime_ip ai ON ai.id = la.anime_ip_id
    JOIN licensee l ON l.id = la.licensee_id
    JOIN royalty_to_date rtd ON rtd.license_agreement_id = la.id
    -- JOIN (not LEFT JOIN): excludes newly signed agreements that haven't submitted a single report yet,
    -- otherwise their cumulative_royalty_usd would be COALESCEd to 0 and mixed in with genuinely delinquent agreements
    WHERE la.contract_status = 'active'
)
SELECT
    agreement_number,
    title,
    company_name,
    ROUND(minimum_guarantee_usd, 0) AS minimum_guarantee_usd,
    ROUND(minimum_guarantee_usd * elapsed_fraction, 0) AS prorated_mg_target,
    ROUND(cumulative_royalty_usd, 0) AS cumulative_royalty_usd,
    ROUND(cumulative_royalty_usd / NULLIF(minimum_guarantee_usd * elapsed_fraction, 0), 2) AS pacing_ratio
FROM pacing
WHERE cumulative_royalty_usd / NULLIF(minimum_guarantee_usd * elapsed_fraction, 0) < 0.40
ORDER BY pacing_ratio ASC
LIMIT 10;
```

**Expected result notes:**
Of 117 agreements, 99 are `active`, and **94 of those have submitted at least one royalty report** (the remaining 5 are too new to have completed their first reporting cycle, and are excluded by the `JOIN`). Of those 94, **21 (about 22.3%)** have a `pacing_ratio` below 0.40 — the amount of royalty they should have paid by now, proportional to elapsed time, has actually only been about 40% delivered. The agreements at the very top have `pacing_ratio` as low as 0-0.03 (for example, `LA-00005` has a minimum guarantee of $19,039, should have paid roughly $6,346 by now, and has actually paid only $20). This isn't random noise: more than a fifth of active agreements that have "had a fair chance to prove themselves" are on track to fall short of the minimum guarantee. The Licensing Manager's next step: evaluate each of these 21 individually — is the IP itself not popular enough (a case for non-renewal), or is the licensee failing to execute (a case for tightening terms or switching licensees on renewal) — and route them into the appropriate response track rather than waiting until the end date to find out there's a problem. The remaining 5 "too new to have a report yet" agreements don't mean there's no problem — it just can't be assessed yet, and they should be placed on a separate watch list, to be evaluated once their first report comes in, rather than treated as risk agreements right now.

---

### Query 6: Account manager portfolio load dashboard

**Business context:**
Ahead of the team's annual performance review, the Director of Licensing wants to understand exactly how many agreements and how much minimum guarantee exposure each account manager is carrying. This isn't just a workload-distribution question — if one manager's agreement count is far higher than peers, it may mean their portfolio is more likely to miss a renewal window or an audit warning simply because attention is spread too thin.

**Category:** Aggregation + Join
**Difficulty:** Basic
**Business Role:** Director of Licensing

**Approach:**
This is the most straightforward query in the set: LEFT JOIN `account_manager` to `license_agreement`, then group by manager to count total agreements, active agreements, and total minimum guarantee under management. LEFT JOIN is used instead of INNER JOIN so that even if a manager currently has zero agreements, they still show up in the results as 0 rather than disappearing entirely — any of the 8 account managers showing "zero" is information management needs to see. `SUM(CASE WHEN ... THEN 1 ELSE 0 END)` is the standard conditional-count pattern, and it's cleaner here than running a separate subquery to count active agreements.

```sql
-- Portfolio load per account manager: total agreements, active count, MG exposure
SELECT
    am.first_name || ' ' || am.last_name AS manager_name,
    am.title,
    am.region_focus,
    COUNT(la.id) AS total_agreements,
    SUM(CASE WHEN la.contract_status = 'active' THEN 1 ELSE 0 END) AS active_agreements,
    ROUND(SUM(la.minimum_guarantee_usd), 0) AS total_mg_managed_usd
FROM account_manager am
LEFT JOIN license_agreement la ON la.account_manager_id = am.id
GROUP BY am.id
ORDER BY total_agreements DESC;
```

**Expected result notes:**
Across 8 account managers, agreement counts range from 11 to 18, and MG exposure under management ranges from about $141,000 to about $347,000. **Meagan Romero** (Director of Licensing) carries the heaviest load, with 18 agreements and roughly $325,000 in exposure; **Caitlin Mcdonald** carries the least, with 11 agreements and roughly $150,000. This dashboard by itself doesn't say anything directly about performance — load needs to be cross-referenced with the results of Query 5 (MG pacing) and Query 2 (royalty audits): only when a manager is carrying a heavy load **and** her agreements show broadly low pacing_ratios is there a real signal worth flagging; agreement count alone tells you little.

---

### Query 7: Compliance score vs. audit outcome consistency check

**Business context:**
The Royalty Audit Specialist wants to verify something: does the internal `compliance_score` the company assigns to each licensee (a qualitative assessment based on historical partnership record) actually predict whether audits will find problems? If the two are disconnected — high-scoring companies still getting caught underreporting — the scoring system needs to be redesigned; if they're highly consistent, the score can be used as a screening criterion for prioritizing audits, saving unnecessary audit cost.

**Category:** Aggregation + Join
**Difficulty:** Intermediate
**Business Role:** Royalty Audit Specialist

**Approach:**
Use `CASE WHEN` to bucket the continuous `compliance_score` into readable bands ("80-100 High," "66-79 Medium," etc.), then aggregate audit outcomes by band. This is **not** simply grouping by the `risk_tier` field — this query deliberately re-buckets from the **raw `compliance_score`** rather than trusting the label the system already assigned, so it can independently verify whether "the score itself" is consistent with "audit outcomes," rather than circularly proving "companies labeled risk_tier are indeed risky." After `GROUP BY compliance_band`, order by `MIN(l.compliance_score) DESC` so bands appear from highest to lowest score, rather than in alphabetical or insertion order, which would be meaningless here.

```sql
-- Verify whether the internal compliance_score actually predicts audit outcomes
SELECT
    CASE
        WHEN l.compliance_score >= 80 THEN '80-100 (High)'
        WHEN l.compliance_score >= 66 THEN '66-79 (Medium)'
        WHEN l.compliance_score >= 50 THEN '50-65 (Low)'
        ELSE 'Below 50 (Very Low)'
    END AS compliance_band,
    COUNT(raf.id) AS n_reports,
    ROUND(AVG(raf.variance_pct), 2) AS avg_variance_pct,
    ROUND(100.0 * SUM(CASE WHEN raf.audit_status = 'confirmed_underreport' THEN 1 ELSE 0 END) / COUNT(raf.id), 1) AS pct_confirmed_underreport
FROM licensee l
JOIN license_agreement la ON la.licensee_id = l.id
JOIN royalty_report rr ON rr.license_agreement_id = la.id
JOIN royalty_audit_finding raf ON raf.royalty_report_id = rr.id
GROUP BY compliance_band
ORDER BY MIN(l.compliance_score) DESC;
```

**Expected result notes:**
Only three bands show up, not four — no licensee falls into the "50-65 (Low)" band in the current data (the 8 `risk`-group licensees in this dataset happen to all cluster between 35-48 points, with a clear gap from the `clean` group's 70-98 range and no "middle ground" companies). The "80-100" and "66-79" bands both show average variance around 0.1% with 0% confirmed_underreport; the "Below 50" band shows an average variance as high as 13.05%, with 64.1% confirmed underreporting. The conclusion is clear: the compliance score **does** predict audit outcomes, and predicts them strongly — nearly a binary split rather than a smooth gradient. The audit specialist can confidently use `compliance_score < 50` as the screening threshold for a "priority audit" list, freeing up routine spot-check resources for high-scoring licensees.

> **Robustness note:** the fact that "results only have three bands, with all 8 risk companies landing exactly in the 35-48 range" is a specific outcome of the current fixed seed `RANDOM_SEED = 42`, not a hard constraint. The generator's sampling range for `risk`-group licensees' `compliance_score` is actually **35-65** (see the `licensee.compliance_score` column definition in the ER document), so it's entirely possible in principle to produce a licensee that lands in the `50-65 (Low)` bucket, which would give a fourth band. This dataset uses a fixed seed for reproducibility, and this doesn't happen under the current seed; but if anyone changes the seed in the future, the "no middle-ground companies" statement needs to be re-checked. The audit threshold itself (`compliance_score < 50`) is unaffected — only the "exactly three bands" observation is seed-dependent.

---

### Query 8: Category royalty rate deviation from benchmark

**Business context:**
The Licensing Manager team wants to know how much negotiating room actually exists between the royalty rates they land on and the category benchmark. One manager has reported that "trading cards are getting harder and harder to negotiate above benchmark" — this query checks whether that claim holds up in the data, informing the rate ranges for the next round of standard contract templates.

**Category:** Aggregation
**Difficulty:** Basic
**Business Role:** Licensing Manager

**Approach:**
A simple JOIN + GROUP BY: average `license_agreement.royalty_rate_pct` by category, and subtract `product_category.benchmark_royalty_rate_pct` to get the deviation. No traps here — this is a warm-up query, and the point is building the habit of, when you get an average, immediately asking whether it's above or below some benchmark, rather than looking at the average in isolation.

```sql
-- Compare negotiated royalty rates against the category benchmark
SELECT
    pc.category_name,
    pc.benchmark_royalty_rate_pct,
    COUNT(la.id) AS n_agreements,
    ROUND(AVG(la.royalty_rate_pct), 2) AS avg_actual_rate,
    ROUND(AVG(la.royalty_rate_pct) - pc.benchmark_royalty_rate_pct, 2) AS avg_deviation_pp,
    ROUND(MIN(la.royalty_rate_pct), 2) AS min_rate,
    ROUND(MAX(la.royalty_rate_pct), 2) AS max_rate
FROM product_category pc
JOIN license_agreement la ON la.product_category_id = pc.id
GROUP BY pc.id
ORDER BY avg_deviation_pp DESC;
```

**Expected result notes:**
All six categories' average actual rates hover close to benchmark, with deviations ranging from -0.31pp to +0.42pp — the **Collectible Trading Cards** category actually averages **below** benchmark by 0.31pp (11.69% vs. a 12.00% benchmark), confirming the manager's claim: negotiating leverage in the trading card category is weaker, possibly because the supply side (licensees willing to make trading cards) is relatively abundant, leaving Ember & Ash with less leverage than usual. The **Toys & Action Figures** category actually averages slightly above benchmark (+0.42pp), the best negotiating room of the six. This result can be fed directly into the rate ranges for the next round of standard contract templates.

---

### Query 9: Licensee brand name vs. signed category mismatch detection

**Business context:**
The VP of Licensing has noticed that, across the agreements signed in recent years, quite a few licensees are expanding beyond their own "flagship category" — a company called "XXX Toys" starts signing apparel or home goods agreements. This isn't necessarily bad (it signals diversification), but the VP wants to understand the scale of this trend, to decide whether it's worth a dedicated discussion at the next channel strategy meeting on whether to encourage licensees to expand across categories.

**Category:** Pattern Matching + Join
**Difficulty:** Intermediate
**Business Role:** VP of Licensing

**Approach:**
This one uses `LIKE` for text pattern matching — licensee `company_name` values often carry category-flavored suffixes (like "... Toys," "... Apparel Co.," "... Home Goods," "... Collectibles"), a deliberate naming convention baked into the generator, not a coincidence. Use patterns like `company_name LIKE '%Toys%'` to identify the "category implied by the name," then compare that against the `product_category` actually signed in `license_agreement` — a mismatch between implied category and signed category is a "cross-category expansion" record. The four `LIKE` conditions are joined with `OR`, one per brand naming pattern; note the `%` wildcard needs to be on both sides, since these keywords can appear anywhere in the brand name (e.g., "Toys" at the end of "Blake and Sons Toys").

```sql
-- Detect licensees signing agreements outside the product category implied by their brand name
SELECT
    l.company_name,
    pc.category_name AS signed_category,
    COUNT(*) AS n_agreements,
    ROUND(SUM(la.minimum_guarantee_usd), 0) AS total_mg_usd
FROM licensee l
JOIN license_agreement la ON la.licensee_id = l.id
JOIN product_category pc ON pc.id = la.product_category_id
WHERE
    (l.company_name LIKE '%Toys%' AND pc.category_code != 'toys_action_figures')
    OR (l.company_name LIKE '%Apparel%' AND pc.category_code != 'apparel')
    OR (l.company_name LIKE '%Home Goods%' AND pc.category_code != 'home_goods_decor')
    OR (l.company_name LIKE '%Collectibles%' AND pc.category_code != 'collectible_trading_cards')
GROUP BY l.id, pc.id
ORDER BY total_mg_usd DESC
LIMIT 10;
```

**Expected result notes:**
Let's be clear on the counting basis first, so the numbers don't seem to disagree if you copy this query as-is: this query aggregates by `GROUP BY l.id, pc.id` (licensee x category), returning **51 rows** of combinations in practice (the `LIMIT 10` only shows the top 10 by minimum guarantee); the underlying total count of "cross-category" **agreements** is **65** — the same (licensee x category) combination can have more than one agreement under it, so the agreement count (65) is higher than the combination row count (51). Both numbers are correct; they're just different units of measure. The top-ranked combination is **Rodriguez, Figueroa and Sanchez Apparel Co.** — despite the name saying "Apparel," they've signed 3 Collectible Trading Cards agreements, totaling roughly $107,000 in minimum guarantee. This shows cross-category expansion is already a phenomenon of real scale, not scattered isolated cases. The VP of Licensing can use this to conclude: rather than treating this as a "brand positioning drift" problem to correct, it's better framed as a signal that the licensee ecosystem is naturally diversifying, worth a formal discussion at the channel strategy meeting on whether to design bundled contract terms for "multi-category licensees."

---

### Query 10: Quarterly new-agreement signing pace trend

**Business context:**
Every quarter, the VP of Licensing has to report the pace of licensing signings to company leadership. She wants to know whether the number of new agreements and total committed minimum guarantee over recent quarters is accelerating, slowing, or holding steady — this trend directly feeds into next year's revenue forecast and team hiring plans.

**Category:** Date Aggregation
**Difficulty:** Basic
**Business Role:** VP of Licensing

**Approach:**
Group by the calendar quarter of `signed_date`. SQLite has no built-in "get quarter" function, so the standard approach is to combine `strftime('%Y', ...)` for the year with `(CAST(strftime('%m', ...) AS INTEGER) - 1) / 3 + 1`, using integer division to map month (1-12) to quarter (1-4) — since `strftime('%m', ...)` returns a string, you have to `CAST` it to `INTEGER` before doing integer division; doing arithmetic directly on the string in SQLite produces unexpected results (the string gets implicitly converted, but it's error-prone, and an explicit `CAST` is safer). This is a basic but very commonly used date-bucketing pattern.

```sql
-- Quarterly trend of new agreement signings and committed minimum guarantees
SELECT
    strftime('%Y', signed_date) || '-Q' || ((CAST(strftime('%m', signed_date) AS INTEGER) - 1) / 3 + 1) AS signing_quarter,
    COUNT(*) AS n_agreements_signed,
    ROUND(SUM(minimum_guarantee_usd), 0) AS total_mg_committed_usd
FROM license_agreement
GROUP BY signing_quarter
ORDER BY signing_quarter;
```

**Expected result notes:**
Signing pace holds fairly steady from 2024-Q3 through 2025-Q4, at roughly 14-21 new agreements and about $260,000-$320,000 in committed minimum guarantee per quarter, with 2026-Q1 showing only 5 agreements and about $92,000 — but that's not a real slowdown, it's an artifact of the data window being truncated near REFERENCE_DATE (2026-06-30); agreements signed in 2026-Q1 and beyond simply haven't had time to accumulate enough history yet. The VP should flag this explicitly when reporting, so leadership doesn't misread "data window truncation" as a genuine business signal of slowing sign-ups.

---

### Query 11: Top 10 near-threshold unconfirmed underreport risk agreements

**Business context:**
The Royalty Audit Specialist doesn't want to only look at agreements already formally judged `confirmed_underreport` (variance ≥12%) — those are already in the process pipeline. She'd rather get ahead of the agreements whose variance is **close to but hasn't yet crossed** the 12% threshold (currently `flagged_for_review` or `within_tolerance`, but with a variance that's already sizable) — these are the agreements most likely to cross the threshold next quarter, and getting ahead of them now saves the cost of a later formal audit.

**Category:** CTE + Window Function
**Difficulty:** Advanced
**Business Role:** Royalty Audit Specialist

**Approach:**
First, a CTE aggregates agreements that haven't yet been judged confirmed_underreport (`WHERE raf.audit_status != 'confirmed_underreport'`) by agreement, computing the average variance `avg_variance_pct`, then a window function `RANK() OVER (ORDER BY AVG(variance_pct) DESC)` ranks them by variance magnitude. `RANK()` is used instead of `ROW_NUMBER()` here because if two agreements have exactly the same average variance, they should get the same rank (`RANK()` skips ranks after a tie) rather than being arbitrarily split into different ranks — `ROW_NUMBER()` would force distinct numbers, hiding the fact that "these two agreements are actually equally worth watching." A window function can legally coexist with `GROUP BY` in the same CTE: `GROUP BY` first aggregates down to one row per agreement, then the window function ranks the already-aggregated result set — this is the standard "aggregate first, then window" pattern.

```sql
-- Rank agreements not yet formally flagged, by variance proximity to the underreport threshold
WITH agreement_variance AS (
    SELECT
        la.agreement_number,
        l.company_name,
        l.compliance_score,
        ai.title,
        ROUND(AVG(raf.variance_pct), 2) AS avg_variance_pct,
        RANK() OVER (ORDER BY AVG(raf.variance_pct) DESC) AS variance_rank
    FROM license_agreement la
    JOIN licensee l ON l.id = la.licensee_id
    JOIN anime_ip ai ON ai.id = la.anime_ip_id
    JOIN royalty_report rr ON rr.license_agreement_id = la.id
    JOIN royalty_audit_finding raf ON raf.royalty_report_id = rr.id
    WHERE raf.audit_status != 'confirmed_underreport'
    GROUP BY la.id
)
SELECT agreement_number, company_name, compliance_score, title, avg_variance_pct, variance_rank
FROM agreement_variance
WHERE variance_rank <= 10
ORDER BY variance_rank;
```

**Expected result notes:**
The top 10 agreements cluster with average variance between **10.58%-11.96%** — all hugging the 12% confirmed_underreport threshold without having formally crossed it yet. The top-ranked agreement, `LA-00081` (**Abbott-Munoz Merch Studio**, compliance score 37.94), sits at 11.96% variance, just 0.04 percentage points shy of being formally judged underreporting. Compliance scores on this list are broadly low (35-48 range), and it's nearly all names from the already-known `risk` licensee group — meaning this isn't a batch of "newly discovered suspects," but rather other agreements under the same high-risk licensees that just haven't crossed the threshold yet. The audit specialist's next step: get ahead of these 10 agreements with proactive conversations now, rather than waiting passively for next quarter's automated determination.

---

### Query 12: Post-launch sell-through ramp curve

**Business context:**
The Retail Channel Analyst needs to write a reference guide for licensees on "roughly how long it takes for a new product to ramp up after launch," to help them plan initial stocking quantities and restock cadence, avoiding either overstocking the first batch and tying up inventory, or understocking and missing the early sales window. She needs to chart a typical "weeks since launch → average units sold" curve from historical data.

**Category:** Date + Aggregation
**Difficulty:** Intermediate
**Business Role:** Retail Channel Analyst

**Approach:**
For every `pos_sell_through` record, compute how many weeks its `week_start_date` is past the owning SKU's `launch_date` — again, convert to `JULIANDAY` before subtracting, divide by 7, and `CAST` to an integer. Grouping by this "weeks since launch" (`weeks_since_launch`) and averaging sales gives you a lifecycle curve aggregated across all SKUs. No CTE or window function is needed here; it's a direct JOIN + GROUP BY. SQLite's `GROUP BY` can reference an alias defined in `SELECT` directly (like `GROUP BY weeks_since_launch` below), so you don't need to repeat the expression — but `WHERE` can't do that, since `WHERE` is evaluated before `SELECT`'s aliases take effect. So to filter the range of `weeks_since_launch`, you have to rewrite the full date-difference expression again inside `WHERE`; you can't just write `WHERE weeks_since_launch BETWEEN 0 AND 20`.

```sql
-- Build the average sell-through curve by weeks since SKU launch
SELECT
    CAST((JULIANDAY(p.week_start_date) - JULIANDAY(s.launch_date)) / 7 AS INTEGER) AS weeks_since_launch,
    COUNT(*) AS n_sku_weeks,
    ROUND(AVG(p.units_sold), 2) AS avg_units_sold
FROM pos_sell_through p
JOIN product_sku s ON s.id = p.product_sku_id
WHERE CAST((JULIANDAY(p.week_start_date) - JULIANDAY(s.launch_date)) / 7 AS INTEGER) BETWEEN 0 AND 20
GROUP BY weeks_since_launch
ORDER BY weeks_since_launch;
```

**Expected result notes:**
The curve shape is very clear: week 0 after launch averages only about 2.5 units sold (distribution barely underway, channels not fully stocked yet), then climbs week over week — about 10.1 units by week 1, about 26.5 units by week 4, and **stabilizing around week 8** at a full-speed level of roughly 43-44 units/week, holding steady in that range afterward (longer-horizon data outside this query's window shows it doesn't start slowly decaying until around week 30). Practical advice for licensees: initial stocking doesn't need to be sized for "full speed" — the first 8 weeks are a natural ramp period by design; the real priority is confirming the restock plan by around weeks 6-8, so supply doesn't fall short once full-speed demand hits.

---

### Query 13: Territory scope vs. minimum guarantee scale relationship

**Business context:**
Negotiating territory scope terms with a new client, the Senior Licensing Manager gets asked, "how much would adding Canada raise the minimum guarantee?" She wants to give an order-of-magnitude answer backed by historical data, rather than a gut-feel quote.

**Category:** Aggregation
**Difficulty:** Basic
**Business Role:** Senior Licensing Manager

**Approach:**
A simple `GROUP BY territory`, comparing average minimum guarantee and average royalty rate across the three territory scopes (`US`, `CANADA`, `US_CANADA`). No JOIN is needed — the `license_agreement` table already contains every column required. This is a classic "provide a reference number for negotiation" basic query, where the emphasis is on presenting the result in a business-meaningful order, not on any particular technique.

```sql
-- Compare average minimum guarantee and royalty rate by territory scope
SELECT
    territory,
    COUNT(*) AS n_agreements,
    ROUND(AVG(minimum_guarantee_usd), 0) AS avg_mg_usd,
    ROUND(AVG(royalty_rate_pct), 2) AS avg_royalty_rate_pct
FROM license_agreement
GROUP BY territory
ORDER BY avg_mg_usd DESC;
```

**Expected result notes:**
`US_CANADA` (both countries) averages about $18,920 in minimum guarantee, `US` (US only) about $13,710, and `CANADA` (Canada only) about $3,554 — the wider the territory scope, the larger the minimum guarantee, which broadly matches intuition (bigger market coverage means higher expected sales, which pushes the guarantee up too). Average royalty rates across the three scopes (9.25%-9.48%) show almost no difference, indicating the royalty rate is mainly driven by category, not territory scope. The Senior Licensing Manager can now answer: expanding a US-only license to US and Canada carries roughly a 35% upside on minimum guarantee, and the royalty rate itself doesn't need to be adjusted.

---

### Query 14: Top 5 best- / worst-selling SKUs

**Business context:**
The Retail Channel Analyst needs to rank restock priorities for next quarter, while also identifying slow-moving SKUs worth considering for discontinuation, freeing up shelf space and production capacity for products that are genuinely selling through. She needs a "look at both ends" list: the top 5 best sellers and the bottom 5 worst.

**Category:** Window Function
**Difficulty:** Intermediate
**Business Role:** Retail Channel Analyst

**Approach:**
Use two `RANK()` window functions running in opposite directions — one ranking by average weekly units descending (`rank_top`), one ascending (`rank_bottom`) — computed together in a single CTE, avoiding having to write two nearly identical queries and manually splice them together. `HAVING COUNT(p.id) >= 10` filters out SKUs that haven't been on the market long enough to have enough weeks of sales to reliably reflect true sell-through (otherwise a SKU that's only been launched for two weeks and happened to spike or flop would distort the ranking due to a too-small sample). Finally, `UNION ALL` stitches the two ends together, with a `bucket` column labeling TOP vs. BOTTOM for readability.

```sql
-- Rank SKUs by average weekly sell-through velocity, both ends of the distribution
WITH sku_perf AS (
    SELECT
        s.sku_code,
        s.sku_name,
        pc.category_name,
        ROUND(AVG(p.units_sold), 2) AS avg_weekly_units,
        RANK() OVER (ORDER BY AVG(p.units_sold) DESC) AS rank_top,
        RANK() OVER (ORDER BY AVG(p.units_sold) ASC) AS rank_bottom
    FROM product_sku s
    JOIN license_agreement la ON la.id = s.license_agreement_id
    JOIN product_category pc ON pc.id = la.product_category_id
    JOIN pos_sell_through p ON p.product_sku_id = s.id
    GROUP BY s.id
    HAVING COUNT(p.id) >= 10
)
SELECT sku_code, sku_name, category_name, avg_weekly_units, 'TOP' AS bucket FROM sku_perf WHERE rank_top <= 5
UNION ALL
SELECT sku_code, sku_name, category_name, avg_weekly_units, 'BOTTOM' AS bucket FROM sku_perf WHERE rank_bottom <= 5
ORDER BY bucket, avg_weekly_units DESC;
```

**Expected result notes:**
The BOTTOM 5 all come from three low-frequency categories — Home Goods & Decor, Stationery & Office, and Accessories & Bags (averaging 2.5-5.6 units/week); the TOP 5 are all Collectible Trading Cards (averaging 98.3-106.7 units/week). This reinforces the conclusion from Query 1 — the difference in repeat-purchase frequency between categories dwarfs the difference between SKUs within the same category. When giving restock recommendations, the analyst should compare SKU rankings **within a category** (e.g., only compare the best-selling SKUs within Home Goods against each other), rather than mixing SKUs from different categories on the same leaderboard — otherwise low-frequency categories will always sit at the bottom, obscuring genuinely meaningful differences within them.

---

### Query 15: Renewal decision list for agreements expiring in the next 6 months

**Business context:**
Every quarter, the Licensing Manager team needs to prepare a list of "agreements coming up for expiration," along with each agreement's recent sell-through performance, so they can proactively reach out to licensees before the renewal window closes, rather than scrambling once an agreement has already lapsed. This query needs to combine "which agreements expire soon" with "how well have they been selling lately" into a single table.

**Category:** CTE + Date Analysis
**Difficulty:** Intermediate
**Business Role:** Licensing Manager

**Approach:**
First, a CTE, `recent_sales`, computes each agreement's cumulative sales over the trailing 12 weeks (84 days), using `date('2026-06-30', '-84 days')` for the date offset — SQLite's `date()` function supports this `'-N days'` modifier syntax. The main query filters for agreements with `contract_status = 'active'` and `contract_end_date` falling within the next 180 days of `REFERENCE_DATE`, then LEFT JOINs the recent-sales CTE — LEFT JOIN, not INNER JOIN, is required here, because some soon-to-expire agreements may have absolutely no sales in the trailing 12 weeks (their SKUs are no longer being restocked), and these "zero sales, expiring soon" agreements are exactly the ones most in need of being seen — an INNER JOIN would drop them outright. `COALESCE(rs.units_last_12w, 0)` explicitly converts NULL to 0, avoiding hard-to-sort blank values in the result.

```sql
-- Agreements expiring within 6 months, joined with recent sell-through for renewal triage
WITH recent_sales AS (
    SELECT s.license_agreement_id, SUM(p.units_sold) AS units_last_12w
    FROM pos_sell_through p
    JOIN product_sku s ON s.id = p.product_sku_id
    WHERE p.week_start_date > date('2026-06-30', '-84 days')
    GROUP BY s.license_agreement_id
)
SELECT
    la.agreement_number,
    ai.title,
    l.company_name,
    la.contract_end_date,
    COALESCE(rs.units_last_12w, 0) AS units_last_12w
FROM license_agreement la
JOIN anime_ip ai ON ai.id = la.anime_ip_id
JOIN licensee l ON l.id = la.licensee_id
LEFT JOIN recent_sales rs ON rs.license_agreement_id = la.id
WHERE la.contract_status = 'active'
  AND la.contract_end_date <= date('2026-06-30', '+180 days')
ORDER BY units_last_12w DESC
LIMIT 10;
```

**Expected result notes:**
**29** active agreements expire within the next 6 months. Recent 12-week sell-through varies enormously — the top-ranked `LA-00094` (**Rustlight**, held by Davis and Sons Collectibles) sold 11,200 units in the trailing 12 weeks and is a clear priority renewal candidate; further down the full list (best viewed by running the query without `LIMIT`), some agreements show zero units sold in the past 12 weeks, and their renewal negotiations should be deprioritized or dropped outright. The Licensing Manager's next step: sort these 29 agreements into "priority renewal," "watch," and "not recommended for renewal" tiers based on trailing-12-week sales, attach each one's Query 5 minimum guarantee pacing as supporting evidence, and submit the full set to the next renewal decision meeting.

---

### Query 16: Composite licensee risk scorecard

**Business context:**
The Director of Royalty Compliance wants a single "spot the highest-concern licensee at a glance" scorecard, instead of flipping through three separate reports (royalty variance, unauthorized distribution, compliance score). She wants royalty underreporting magnitude and unauthorized-distribution revenue share combined into one single "composite risk score," used to decide where next quarter's audit resources should be prioritized.

**Category:** CTE + Aggregation
**Difficulty:** Advanced
**Business Role:** Director of Royalty Compliance

**Approach:**
This query wraps the two aggregation pipelines behind Query 2 (royalty variance) and Query 4 (unauthorized distribution) into their own CTEs — `audit_summary` and `channel_summary` — then attaches both to the `licensee` table with `LEFT JOIN`. The `LEFT JOIN` is required, because not every licensee necessarily has any unauthorized-distribution records; `channel_summary` may have no row for a given licensee, in which case `pct_unauthorized_revenue` should show as 0, not cause the whole row to vanish from the result. Finally, the two independent metrics — `avg_variance_pct` and `pct_unauthorized_revenue` — are simply added together to produce `combined_risk_score`. This is a simplified composite metric that assumes the two risk dimensions carry equal weight, purely for teaching clarity; a real production environment might re-weight them based on historical audit cost or loss amounts.

```sql
-- Composite risk score combining royalty variance and unauthorized channel exposure
WITH audit_summary AS (
    SELECT la.licensee_id, AVG(raf.variance_pct) AS avg_variance_pct
    FROM license_agreement la
    JOIN royalty_report rr ON rr.license_agreement_id = la.id
    JOIN royalty_audit_finding raf ON raf.royalty_report_id = rr.id
    GROUP BY la.licensee_id
),
channel_summary AS (
    SELECT
        la.licensee_id,
        ROUND(100.0 * SUM(CASE WHEN lac.id IS NULL THEN p.net_wholesale_revenue_usd ELSE 0 END) / SUM(p.net_wholesale_revenue_usd), 2) AS pct_unauthorized_revenue
    FROM pos_sell_through p
    JOIN product_sku s ON s.id = p.product_sku_id
    JOIN license_agreement la ON la.id = s.license_agreement_id
    LEFT JOIN license_agreement_channel lac
        ON lac.license_agreement_id = la.id AND lac.retail_channel_id = p.retail_channel_id
    GROUP BY la.licensee_id
)
SELECT
    l.company_name,
    l.risk_tier,
    ROUND(l.compliance_score, 1) AS compliance_score,
    ROUND(a.avg_variance_pct, 2) AS avg_royalty_variance_pct,
    COALESCE(c.pct_unauthorized_revenue, 0) AS pct_unauthorized_revenue,
    ROUND(a.avg_variance_pct + COALESCE(c.pct_unauthorized_revenue, 0), 2) AS combined_risk_score
FROM licensee l
JOIN audit_summary a ON a.licensee_id = l.id
LEFT JOIN channel_summary c ON c.licensee_id = l.id
ORDER BY combined_risk_score DESC
LIMIT 10;
```

**Expected result notes:**
The result shows an unmistakably clean cliff: the top 7 composite risk scores all belong to `risk_tier = 'risk'` licensees (scores 14.76-25.37), then drop sharply at rank 8 to the `clean` group's 1.38-2.57 range. **Williams and Sons Toys** has the highest composite score (25.37 = 13.61% royalty variance + 11.76% unauthorized-distribution revenue share), and is the top priority for next quarter's audit resources. This scorecard confirms an important business insight: royalty underreporting and unauthorized distribution — two seemingly independent compliance issues — co-occur at a very high rate within this small group of licensees in this portfolio. A low compliance score isn't a case of "unlucky, got caught once" — it's a systemic, multi-dimensional problem, and the compliance director should treat these 7 as a "priority monitoring list" rather than handling the two issue types separately.

---

### Query 17: Online vs. offline channel sell-through comparison

**Business context:**
The Retail Channel Analyst wants to know how the company's overall sell-through volume splits between online channels (e-commerce, direct-to-consumer online) and offline channels (big-box chains, specialty stores, convention pop-ups), to inform next year's channel expansion budget allocation — should the company keep doubling down on offline, or expand online channel authorization?

**Category:** Aggregation + Join
**Difficulty:** Basic
**Business Role:** Retail Channel Analyst

**Approach:**
A direct `pos_sell_through JOIN retail_channel`, grouped by `channel_type` (`online`/`offline`) to total up sales volume, revenue, and the average sales per record. `COUNT(DISTINCT rc.id)` shows how many specific channels sit under each category, helping the reader understand how much of "offline has a bigger total" is simply due to offline having more channels to begin with (3 vs. 2), rather than any single channel being more efficient.

```sql
-- Compare total sell-through volume between online and offline channel types
SELECT
    rc.channel_type,
    COUNT(DISTINCT rc.id) AS n_channels,
    SUM(p.units_sold) AS total_units,
    ROUND(SUM(p.net_wholesale_revenue_usd), 0) AS total_revenue,
    ROUND(AVG(p.units_sold), 2) AS avg_weekly_units_per_row
FROM pos_sell_through p
JOIN retail_channel rc ON rc.id = p.retail_channel_id
GROUP BY rc.channel_type;
```

**Expected result notes:**
Offline channels (3 combined) total roughly 1,016,000 units sold and about $11.26 million in revenue; online channels (2 combined) total roughly 608,000 units and about $6.99 million. But **average sales per record are nearly identical** (about 35.4 units/row offline vs. about 34.9 units/row online) — meaning the total volume gap comes mainly from offline simply having more channels and licensees preferring offline channel selection more often (recall the generator's `CHANNEL_SELECTION_WEIGHTS`: big_box_retail and specialty_retail carry noticeably higher weight than e-commerce), rather than offline actually "selling faster" per channel. Recommendation for the channel expansion budget: online channel efficiency isn't actually weaker — if current channel authorization coverage skews low online, expanding online channel authorization has real incremental potential, rather than just cannibalizing existing offline sales.

---

### Query 18: Royalty report submission timeliness analysis

**Business context:**
The Royalty Audit Specialist has noticed that licensees submit royalty reports at wildly inconsistent times — some file soon after the reporting period ends, others wait until right up against the deadline. She wants to understand the overall distribution of submission timeliness across the company, to decide whether the standard contract template's submission deadline should be tightened from its current default grace period.

**Category:** Date Calculation
**Difficulty:** Basic
**Business Role:** Royalty Audit Specialist

**Approach:**
Compute the number of days between `report_submitted_date` and `report_period_end_date` (again, converting to `JULIANDAY` before subtracting), grouped by day count, producing a histogram of submission timeliness. This is a pure date-calculation query with no JOIN required, and the point is practicing "subtract two dates to get a day count," a basic operation used in almost every time-series analysis.

```sql
-- Distribution of days between report period end and actual submission
SELECT
    CAST(JULIANDAY(report_submitted_date) - JULIANDAY(report_period_end_date) AS INTEGER) AS submission_lag_days,
    COUNT(*) AS n_reports
FROM royalty_report
GROUP BY submission_lag_days
ORDER BY submission_lag_days;
```

**Expected result notes:**
Submission lag is distributed between 15-45 days, averaging about 30.5 days, roughly evenly spread across that range, with no obvious clustering around the deadline. This suggests the current submission deadline is fairly generous and isn't creating unnecessary pressure, but it also means Ember & Ash waits an average of about a month to get last quarter's royalty data — if the company wants to speed up cash flow turnover, it could consider tightening the default submission deadline from the current 45-day cap to around 30 days, while monitoring whether that pushes up the rate of late submissions.

---

### Query 19: IP popularity tier vs. agreement scale relationship

**Business context:**
While putting together next year's IP recruitment strategy, the VP of Licensing wants to test a hypothesis: is the company over-concentrating resources on a handful of breakout-tier IP, at the expense of clearly under-investing in niche-tier IP? This will shape whether the company should actively expand into more long-tail niche IP next year to diversify risk.

**Category:** Aggregation + Join
**Difficulty:** Intermediate
**Business Role:** VP of Licensing

**Approach:**
Group by `anime_ip.popularity_tier`, counting how many IPs fall into each tier, how many agreements have been signed, the average number of agreements per IP, and average minimum guarantee scale. `COUNT(DISTINCT ai.id)` and `COUNT(la.id)` separately count two different grains — "number of IPs" and "number of agreements" — and dividing one by the other produces the derived metric "average agreements attracted per IP." This is a classic pattern of dividing two COUNTs at different grains to get a ratio.

```sql
-- Compare agreement volume and MG scale across IP popularity tiers
SELECT
    ai.popularity_tier,
    COUNT(DISTINCT ai.id) AS n_ips,
    COUNT(la.id) AS n_agreements,
    ROUND(1.0 * COUNT(la.id) / COUNT(DISTINCT ai.id), 1) AS avg_agreements_per_ip,
    ROUND(AVG(la.minimum_guarantee_usd), 0) AS avg_mg_usd
FROM anime_ip ai
JOIN license_agreement la ON la.anime_ip_id = ai.id
GROUP BY ai.popularity_tier
ORDER BY avg_mg_usd DESC;
```

**Expected result notes:**
Breakout-tier IP (5 titles) average **7.2** agreements per IP and roughly $21,772 average minimum guarantee; mainstream-tier (13 titles) average 5.5 agreements and roughly $14,455; niche-tier (6 titles) average only **1.7** agreements and roughly $6,778. The gap is real, but not as extreme as the VP feared — niche-tier IP still attract close to 2 agreements on average, not zero. This supports a balanced conclusion: the company's resources genuinely do skew toward breakout tier (reasonably so, given stronger sell-through evidence), but the niche-tier IP portfolio still retains a basic level of diversification exposure. There's no need for a drastic recruitment strategy shift — a moderate increase in niche-tier IP signings could be considered as a risk hedge, rather than a large-scale pivot.

---

### Query 20: Composite renewal priority score

**Business context:**
Ahead of the annual licensing portfolio strategy meeting, the VP of Licensing needs a single list that merges three independent dimensions — "selling well or not" (Query 1), "reporting royalty honestly or not" (Query 2), and "keeping pace with the minimum guarantee or not" (Query 5) — into one unified priority ranking, rather than making the meeting attendees mentally weigh three separate reports themselves. This is the closing slide of the entire quarterly review deck, directly determining which agreements make the "priority renewal" candidate list.

**Category:** CTE + Window Function
**Difficulty:** Advanced
**Business Role:** VP of Licensing

**Approach:**
This query packages three independent dimensions — total sell-through volume (`sku_perf`), average royalty variance (`audit_summary`), and minimum guarantee pacing (`pacing`, reusing the proration logic from Query 5) — into their own CTEs, then uses the `NTILE(4)` window function to split each dimension separately into four quartile buckets (rather than just summing raw values, since the three dimensions have completely different units: volume is a unit count, variance is a percentage, and pacing is a ratio — summing them directly would be meaningless). Sell-through volume is bucketed descending (higher sales = lower, better quartile number), royalty variance ascending (smaller variance = lower, healthier quartile number), and MG pacing descending (higher pacing = lower, better quartile number) — the three `NTILE` orderings are deliberately kept consistent with the semantics "lower quartile number = better performance," otherwise summing them into `renewal_priority_score` would lose all meaning. Finally, the three quartile numbers are added together; a lower score means better overall performance across all three dimensions, and higher renewal priority. This is a simplified multi-metric composite scoring approach, and using quartiles in place of raw values is a common, robust technique when there's no clear weighting scheme available.

**The same edge case as Query 5 is even trickier here:** a newly signed agreement that hasn't submitted a royalty report yet, if joined to `audit_summary` and `pacing` via `LEFT JOIN` and backfilled with `COALESCE(..., 0)`, produces a self-contradictory result — the missing `avg_variance_pct` gets backfilled to 0, which in `audit_health_quartile` reads as "zero variance, fully compliant" and lands in the best quartile; but the missing `pacing_ratio` also gets backfilled to 0, which in `mg_pacing_quartile` reads as "zero progress, worst performance" and lands in the worst quartile. The same "not enough data accumulated yet" agreement gets two contradictory readings across two dimensions of this composite score. The fix is to change the `LEFT JOIN`s for `audit_summary` and `pacing` to plain `JOIN`s, and drop the `COALESCE` fallback along with them — that way only agreements that have already submitted at least one report make it into the `composite` CTE and get scored; newly signed agreements, same as in Query 5, should go on the watch list first, rather than showing up directly on the composite scoring leaderboard.

```sql
-- Composite renewal priority score combining sell-through, audit health, and MG pacing
WITH sku_perf AS (
    SELECT s.license_agreement_id, SUM(p.units_sold) AS total_units
    FROM pos_sell_through p JOIN product_sku s ON s.id = p.product_sku_id
    GROUP BY s.license_agreement_id
),
audit_summary AS (
    SELECT la.id AS agreement_id, AVG(raf.variance_pct) AS avg_variance_pct
    FROM license_agreement la
    JOIN royalty_report rr ON rr.license_agreement_id = la.id
    JOIN royalty_audit_finding raf ON raf.royalty_report_id = rr.id
    GROUP BY la.id
),
pacing AS (
    SELECT la.id AS agreement_id,
        SUM(rr.reported_royalty_due_usd) / NULLIF(la.minimum_guarantee_usd * MIN(1.0,
            CAST((JULIANDAY('2026-06-30') - JULIANDAY(la.contract_start_date)) AS REAL)
            / (JULIANDAY(la.contract_end_date) - JULIANDAY(la.contract_start_date))), 0) AS pacing_ratio
    FROM license_agreement la
    JOIN royalty_report rr ON rr.license_agreement_id = la.id
    GROUP BY la.id
),
composite AS (
    SELECT
        la.agreement_number,
        ai.title,
        l.company_name,
        COALESCE(sp.total_units, 0) AS total_units_sold,
        NTILE(4) OVER (ORDER BY COALESCE(sp.total_units, 0) DESC) AS sell_through_quartile,
        NTILE(4) OVER (ORDER BY au.avg_variance_pct ASC) AS audit_health_quartile,
        NTILE(4) OVER (ORDER BY pc.pacing_ratio DESC) AS mg_pacing_quartile
    FROM license_agreement la
    JOIN anime_ip ai ON ai.id = la.anime_ip_id
    JOIN licensee l ON l.id = la.licensee_id
    LEFT JOIN sku_perf sp ON sp.license_agreement_id = la.id
    JOIN audit_summary au ON au.agreement_id = la.id
    JOIN pacing pc ON pc.agreement_id = la.id
    -- audit_summary / pacing use JOIN (not LEFT JOIN): excludes newly signed agreements that
    -- haven't submitted a report yet, avoiding self-contradictory scores across the two quartile buckets (see Approach above)
    WHERE la.contract_status = 'active'
)
SELECT
    agreement_number, title, company_name, total_units_sold,
    sell_through_quartile, audit_health_quartile, mg_pacing_quartile,
    (sell_through_quartile + audit_health_quartile + mg_pacing_quartile) AS renewal_priority_score
FROM composite
ORDER BY renewal_priority_score ASC
LIMIT 10;
```

**Expected result notes:**
94 active agreements that have "submitted at least one royalty report" are the ones being scored (newly signed agreements have been excluded and put on the watch list separately). The lowest (best) score is 3 — all three dimensions ranked in the top quartile — occurring on 3 agreements: `LA-00042` (Ember Knights: Genesis), `LA-00075` (Wildfire Dorm), and `LA-00054` (Skybound Mariners), the clearest, most uncontroversial priority renewal candidates. Agreements scoring 4 are cases where "one dimension is slightly weak but overall still healthy" — for example, `LA-00085` (**Whispering Gears**, held by Rodriguez, Figueroa and Sanchez Apparel Co.) has total sales as high as about 79,570 units, but ranks in the second quartile on `audit_health_quartile`, a reminder for the VP to consider tightening audit terms with this licensee as part of the renewal, rather than a simple binary "renew or don't renew" call. This leaderboard is the core agenda for the quarterly review meeting: the lowest-scoring agreements go straight into renewal negotiation, while the highest-scoring ones (a score of 12, bottom quartile on all three dimensions) should be the focus of a discussion on whether to end the partnership at expiration.

---

## Business Question Mapping Table

| Business Question | Corresponding Query |
|----------|----------|
| Q1 Content Sell-Through & Renewal Priority | Query 1, Query 14, Query 20 |
| Q2 Royalty Audit & Underreporting Risk | Query 2, Query 7, Query 11, Query 16 |
| Q3 Popularity-to-Sell-Through Lag | Query 3, Query 12 |
| Q4 Unauthorized Distribution Compliance | Query 4, Query 16 |
| Q5 Minimum Guarantee Pacing Tracking | Query 5, Query 15, Query 20 |
| Operations & Portfolio Management (not a standalone marquee question, but supports day-to-day decisions) | Query 6, Query 8, Query 9, Query 10, Query 13, Query 17, Query 18, Query 19 |
</content>
