# Crestline Realty — Market Intelligence Raw Data: SQL Queries Reference

## Overview

This document provides **20 business-oriented SQL queries** designed for the `real_estate_brokerage_market_intelligence_raw_data_high` dataset (23 tables, ~328K rows). Each query answers a real question a Crestline Realty stakeholder (executive, manager, analyst, agent, ops) would actually ask. All queries are runnable directly on the SQLite database and also serve as an **acceptance test** for the analytical fidelity of the dataset.

**About dates**: all time-window queries use the literal `'2026-06-05'` (the dataset's effective "today") rather than `date('now')`, so the results are reproducible no matter when the query is run. On Redshift/Postgres, just swap the date for `current_date - interval '12 months'`.

**Companion documents**: before getting hands-on, read `01-real_estate_brokerage_market_intelligence_raw_data_high_business_context.md` (the company, industry, business questions, glossary, and metric formulas) and `02-real_estate_brokerage_market_intelligence_raw_data_high_er_document.md` (tables, fields, relationships, generation rules). This document assumes you have already read both.

---

## How to Use This Document

This document is teaching-oriented. Imagine the scenario: you're a brand-new intern on the Crestline data team. You've just finished the business-context and ER docs, and your manager hands you these 20 queries with "work through these this week." This doc walks you through them step by step.

**Each query has a fixed five-part structure**, and reading it in order teaches you both how to write and how to use the query:

1. **Business context** — who is asking, why, what decision they'll make with the answer, and why it's urgent. This ties the query back to a real person and a real decision at the company.
2. **Category / Difficulty / Business role** — three tags: SQL category (aggregation, window function, cross-domain join, …), difficulty (Basic / Intermediate / Advanced), and the role asking.
3. **Approach** — before you look at the SQL, this section walks through the thinking: which tables you touch, how the joins are set up (where LEFT JOIN is required, where fan-out leads to double-counting), the grain of the aggregation (what does one row in the output represent), why we use a CTE or a window function, and any SQLite-specific gotchas. This is the "think before you code" part.
4. **SQL** — the query itself, written in SQLite 3.x syntax, verified on the generated `.sqlite`. Dates are always literals like `'2026-06-05'`.
5. **Expected result + business takeaway** — what the result looks like (how many rows and columns, what each column means, the order-of-magnitude of key numbers), and **what the analyst should do next once they have the numbers**. Running the query is the start of analysis, not the end.

**Every query traces back to one of the business questions in the business-context document** (pricing, agent performance, market temperature, opportunity discovery, forecast & cash flow, matching & data quality). There's a "business question → query" mapping table at the end.

**SQL is meant to be read and learned from, not just run**. The Approach section explains "why it's written this way" — we recommend reading the Approach first, sketching the SQL yourself, and then comparing to ours.

---

## Query Index

| # | Title | Business role | Category | Difficulty |
|---|-------|---------------|----------|------------|
| 1 | Monthly sold volume by market | Executive | Aggregation | Basic |
| 2 | Median sale price by ZIP × property type | Analyst | Window function | Intermediate |
| 3 | Top 10 agents by GCI (trailing 12 months) | Manager | Join + aggregation | Basic |
| 4 | Days-on-market distribution by market temperature | Analyst | Aggregation | Basic |
| 5 | Stale active listings that need attention | Ops | Filter + date | Intermediate |
| 6 | Year-over-year sales change | Executive | Window function | Intermediate |
| 7 | Agent activity-to-close funnel | Manager | CTE + Join | Advanced |
| 8 | Buyer-to-listing match candidates | Ops | Join + filter | Intermediate |
| 9 | Sale-to-list ratio trend by market | Analyst | Date aggregation | Intermediate |
| 10 | Office performance scorecard | Manager | Multi-join aggregation | Intermediate |
| 11 | Listings with the most price reductions | Analyst | Subquery | Intermediate |
| 12 | Mortgage rate vs. sales volume correlation | Analyst | Cross-domain join | Advanced |
| 13 | Sales pipeline velocity by stage | Manager | Aggregation | Basic |
| 14 | Lost-deal reason analysis | Manager | Aggregation + filter | Basic |
| 15 | Agent tenure vs. commission income | Analyst | CTE + date math | Advanced |
| 16 | Duplicate contact detection | Ops | Self-join + GROUP BY | Intermediate |
| 17 | Sale prices above Zillow ZHVI | Analyst | Cross-domain join | Advanced |
| 18 | Commission payout forecast for the next 30 days | Finance | Filter + aggregation | Basic |
| 19 | Buyer-demand pressure on active listings | Ops | Join + aggregation | Intermediate |
| 20 | Crestline market-share trend by zip | Executive | Window function | Advanced |

---

## Query Details

### Query 1: Monthly Sold Volume by Market

**Business context:**
Sarah Mitchell (VP Operations) opens every weekly leadership meeting with the same chart: across the MLS markets Crestline tracks, how many homes closed each month over the trailing 12 months, broken out by market? The "2024 was down 28% from 2023" narrative comes from this query, and it's the first thing the new Market Pulse dashboard has to get right. If this number is wrong, no other analysis matters.

**Category:** Aggregation
**Difficulty:** Basic
**Business role:** Executive

**Approach:**
Closed deals live in `mls_sold_transaction`, but the sold table itself doesn't know which market it belongs to — geography lives on the property. So you join all the way up: sold → `mls_listing` (for PROPERTY_ID) → `mls_property` (for zip_id) → `geo_zip_code` → `geo_city` → `geo_county` → `geo_market`. The time window is `CLOSE_DT >= '2025-07-01'` for the trailing 12 months, and months are bucketed with `strftime('%Y-%m', CLOSE_DT)`. Group by market_code + year_month: one output row = one market for one month. No window function needed — a single GROUP BY does it, and GTV is `SUM(SALE_PRICE)`.

```sql
SELECT
    m.market_code,
    strftime('%Y-%m', s.CLOSE_DT) AS year_month,
    COUNT(*) AS sold_count,
    ROUND(SUM(s.SALE_PRICE) / 1e6, 1) AS gtv_millions
FROM mls_sold_transaction s
JOIN mls_listing l ON s.LISTING_ID = l.LISTING_ID
JOIN mls_property p ON l.PROPERTY_ID = p.PROPERTY_ID
JOIN geo_zip_code z ON p.zip_id = z.zip_id
JOIN geo_city ci ON z.city_id = ci.city_id
JOIN geo_county co ON ci.county_id = co.county_id
JOIN geo_market m ON co.market_id = m.market_id
WHERE s.CLOSE_DT >= date('2025-07-01')
GROUP BY m.market_code, year_month
ORDER BY year_month, m.market_code;
```

**Expected result:**
~36 rows (12 months × 3 markets). Bay Area has the highest GTV, PNW the lowest. 2025-26 should show a modest recovery from the 2024 trough. Drives the top KPI for executives.

---

### Query 2: Median Sale Price by ZIP × Property Type

**Business context:**
"What's the median price of a 3-bedroom condo in 94102 this quarter?" — this is the question agents ask most often. Emily Zhang's analyst team is currently answering it through ad-hoc notebooks. The drill-down view on the Market Pulse dashboard needs this number for every ZIP × property-type cell, and the NL Query layer also needs to be able to produce the equivalent SQL when an agent asks the natural-language version.

**Category:** Window function
**Difficulty:** Intermediate
**Business role:** Analyst

**Approach:**
SQLite has no built-in `median()`, so the median has to be computed by hand: within each `(zip5, PROPERTY_TYPE)` partition, use `ROW_NUMBER() OVER (... ORDER BY SALE_PRICE)` to rank sale prices, and `COUNT(*) OVER (...)` to get the partition size. Then pick the middle row (`rn = (cnt+1)/2`). That's why a window function is required — a simple GROUP BY won't do it. Pre-compute rank and count in the CTE `ranked`, then the outer query just filters. One output row = one zip × property-type cell with median price and sample size; cells with `n_sold < 5` should be flagged as low confidence on the dashboard.

```sql
WITH ranked AS (
    SELECT
        z.zip5,
        p.PROPERTY_TYPE,
        s.SALE_PRICE,
        ROW_NUMBER() OVER (PARTITION BY z.zip5, p.PROPERTY_TYPE ORDER BY s.SALE_PRICE) AS rn,
        COUNT(*) OVER (PARTITION BY z.zip5, p.PROPERTY_TYPE) AS cnt
    FROM mls_sold_transaction s
    JOIN mls_listing l ON s.LISTING_ID = l.LISTING_ID
    JOIN mls_property p ON l.PROPERTY_ID = p.PROPERTY_ID
    JOIN geo_zip_code z ON p.zip_id = z.zip_id
    WHERE s.CLOSE_DT >= date('2026-01-01')
      AND s.CLOSE_DT <  date('2026-07-01')
)
SELECT zip5, PROPERTY_TYPE, SALE_PRICE AS median_price, cnt AS n_sold
FROM ranked
WHERE rn = (cnt + 1) / 2
ORDER BY zip5, PROPERTY_TYPE;
```

**Expected result:**
~180 rows (60 zips × ~3 property types with enough data). Each cell shows median sale price + sample count. Cells with `n_sold < 5` should be marked as low-confidence on the dashboard.

---

### Query 3: Top 10 Agents by GCI (Trailing 12 Months)

**Business context:**
Rachel Torres (Bay Area Regional Manager) runs the quarterly "President's Club" rankings. The Agent Scorecard dashboard has to display the top earners over the trailing 12 months — Crestline pays bonuses to the company's top 10, and this list directly drives compensation. This query is also embedded in the automated weekly report sent to all managers.

**Category:** Join + aggregation
**Difficulty:** Basic
**Business role:** Manager

**Approach:**
GCI is the sum of commission splits aggregated per agent. Start from `crm_commission_split` (where the commission lives), join `crm_agent` for name/tier, and join `crm_office` for office. `Payout_Date__c >= date('2026-06-05','-12 months')` restricts to the trailing 12 months. Group by agent: `SUM(Agent_Take__c)` is GCI, and `COUNT(DISTINCT Transaction_Id__c)` counts deals (DISTINCT is needed because co-lists produce multiple split rows for one transaction). Order by GCI, take top 10. Note: this is **trailing 12 months**, which differs from the all-time cumulative window used in Query 15 — so the dollar amounts here will be considerably smaller.

```sql
SELECT
    a.Id              AS agent_id,
    a.First_Name__c || ' ' || a.Last_Name__c AS agent_name,
    a.Tier__c,
    o.Name            AS office,
    COUNT(DISTINCT cs.Transaction_Id__c) AS deal_count,
    ROUND(SUM(cs.Agent_Take__c), 0)      AS gci_usd
FROM crm_commission_split cs
JOIN crm_agent a ON cs.Agent_Id__c = a.Id
JOIN crm_office o ON a.Office_Id__c = o.Id
WHERE cs.Payout_Date__c >= date('2026-06-05', '-12 months')
GROUP BY a.Id
ORDER BY gci_usd DESC
LIMIT 10;
```

**Expected result:**
10 rows, all (or nearly all) SENIOR tier with hire dates in 2018-2020 (the effect of tenure-weighted Pareto). Approximate range: a single top earner at $1.4M-$2.2M; the rest at $250K-$900K. The query relies on `crm_commission_split` (whose `Agent_Id__c` is set to the owning opportunity's agent) joining to `crm_agent` and `crm_office`. Note: **this query filters on the trailing 12 months**; for each agent's all-time cumulative GCI, see Query 15 (the amounts are ~3-4x what you see here because the window spans 3.4 years).

---

### Query 4: Days-on-Market Distribution by Market Temperature

**Business context:**
The competitive-positioning AI agent (Module 4) needs to calibrate its DOM baseline by market temperature to flag stale listings. This query gives John Doe the distribution, and the AI agent's "stale listing" threshold (DOM > median × 1.5) is computed from it. It's also a data-quality smoke test: HOT zip DOM must be shorter than COOL zip DOM.

**Category:** Aggregation
**Difficulty:** Basic
**Business role:** Analyst

**Approach:**
This validates "hotter market = sells faster." All you need is `mls_listing` joined to `mls_property` and `geo_zip_code` for the temperature label, filtered to `STATUS_CD='SLD'` (only actually-closed listings), grouped by `temperature`, computing avg/min/max DOM. One output row = one temperature tier (3 rows total). No need to join the sold table because DOM lives on the listing. If the result doesn't clearly show HOT < STABLE < COOL average DOM, the generator has drifted — this query doubles as a data-quality smoke test.

```sql
SELECT
    z.temperature,
    COUNT(*)                       AS n_sold,
    ROUND(AVG(l.DOM), 1)           AS avg_dom,
    MIN(l.DOM)                     AS min_dom,
    MAX(l.DOM)                     AS max_dom
FROM mls_listing l
JOIN mls_property p ON l.PROPERTY_ID = p.PROPERTY_ID
JOIN geo_zip_code z ON p.zip_id = z.zip_id
WHERE l.STATUS_CD = 'SLD'
GROUP BY z.temperature
ORDER BY avg_dom;
```

**Expected result:**
3 rows. HOT zip average DOM ~13 days, STABLE ~41, COOL ~87. If the ordering is wrong, the data generator has drifted.

---

### Query 5: Stale Active Listings That Need Attention

**Business context:**
Rachel Torres asks every morning: "Which of my agents' active listings have been sitting on the market too long?" The "Stale Listings" widget on the Market Pulse dashboard displays this list, sorted by "how far past the zip's median DOM." Agents whose names keep appearing on this list get a Slack ping to consider a price reduction or a marketing refresh.

**Category:** Filter + date arithmetic
**Difficulty:** Intermediate
**Business role:** Ops

**Approach:**
"Stale" is a relative concept, so you first need a per-zip DOM baseline. The CTE `zip_median_dom` uses `AVG(DOM)` for sold listings as a median proxy (SQLite has no median, so avg is the proxy). The outer query only looks at `STATUS_CD='ACT'` and computes how long the listing has been on the market via `julianday('2026-06-05') - julianday(LIST_DT)`, then compares to baseline × 1.5. One output row = one stale active listing. A CTE earns its keep here because the baseline is reused per zip; the results concentrate in COOL zips.

```sql
WITH zip_median_dom AS (
    SELECT
        z.zip_id,
        ROUND(AVG(l.DOM), 0) AS median_dom_proxy
    FROM mls_listing l
    JOIN mls_property p ON l.PROPERTY_ID = p.PROPERTY_ID
    JOIN geo_zip_code z ON p.zip_id = z.zip_id
    WHERE l.STATUS_CD = 'SLD'
    GROUP BY z.zip_id
)
SELECT
    l.MLS_NUMBER,
    p.STREET_NUM || ' ' || p.STREET_NAME AS address,
    p.CITY,
    z.zip5,
    l.LIST_PRICE,
    CAST(julianday('2026-06-05') - julianday(l.LIST_DT) AS INTEGER) AS days_active,
    zmd.median_dom_proxy
FROM mls_listing l
JOIN mls_property p ON l.PROPERTY_ID = p.PROPERTY_ID
JOIN geo_zip_code z ON p.zip_id = z.zip_id
JOIN zip_median_dom zmd ON z.zip_id = zmd.zip_id
WHERE l.STATUS_CD = 'ACT'
  AND CAST(julianday('2026-06-05') - julianday(l.LIST_DT) AS INTEGER) > zmd.median_dom_proxy * 1.5
ORDER BY days_active DESC
LIMIT 25;
```

**Expected result:**
~10-30 stale listings, concentrated in COOL zips. Agents whose names keep appearing are flagged for coaching.

---

### Query 6: Year-over-Year Sales Change

**Business context:**
The quarterly board/investor deck always opens with this chart: how is each market trending YoY? This query computes the underlying data. The Crestline narrative — down 22-28% in 2024 followed by recovery — must be reproducible exactly from this query, so leadership and investors see consistent numbers.

**Category:** Window function
**Difficulty:** Intermediate
**Business role:** Executive

**Approach:**
The board wants per-market YoY trends. First, aggregate sold volume by market + year (via `strftime('%Y')`) in CTE `yearly`. Then `LAG(sold_count) OVER (PARTITION BY market_code ORDER BY year)` pulls the previous year's value for the same market, and (current - prior) / prior gives yoy_pct. The window function LAG is the key — it lets you compute "this year vs. last year" in the same row, much cleaner than a self-join. One output row = one market-year; 2024 rows should show -22% to -28%.

```sql
WITH yearly AS (
    SELECT
        m.market_code,
        CAST(strftime('%Y', s.CLOSE_DT) AS INTEGER) AS year,
        COUNT(*) AS sold_count,
        ROUND(SUM(s.SALE_PRICE) / 1e6, 1) AS gtv_millions
    FROM mls_sold_transaction s
    JOIN mls_listing l ON s.LISTING_ID = l.LISTING_ID
    JOIN mls_property p ON l.PROPERTY_ID = p.PROPERTY_ID
    JOIN geo_zip_code z ON p.zip_id = z.zip_id
    JOIN geo_city ci ON z.city_id = ci.city_id
    JOIN geo_county co ON ci.county_id = co.county_id
    JOIN geo_market m ON co.market_id = m.market_id
    GROUP BY m.market_code, year
)
SELECT
    market_code,
    year,
    sold_count,
    LAG(sold_count) OVER (PARTITION BY market_code ORDER BY year) AS prior_year,
    ROUND(100.0 * (sold_count - LAG(sold_count) OVER (PARTITION BY market_code ORDER BY year))
          / LAG(sold_count) OVER (PARTITION BY market_code ORDER BY year), 1) AS yoy_pct
FROM yearly
ORDER BY market_code, year;
```

**Expected result:**
12 rows (3 markets × 4 years). 2024 should show -22% to -28% in every market. 2025 should show a partial recovery.

---

### Query 7: Agent Activity-to-Close Funnel

**Business context:**
Marcus Rivera (Tech Lead) suspects some senior agents close a lot of deals not because they convert better, but because their outreach volume is 5x higher. This query computes the per-agent funnel: activities → opportunities → closed wons, letting managers tell whether the productivity issue is at the top of the funnel (volume) or the bottom (conversion). It gets used in 1-on-1s.

**Category:** CTE + multi-join
**Difficulty:** Advanced
**Business role:** Manager

**Approach:**
This separates "outreach volume" from "conversion rate," so we use two CTEs: `activity_stats` counts each agent's activities in the trailing 12 months, and `opp_stats` counts opportunities and how many of them closed as Closed Won. Both CTEs are joined back to `crm_agent` via LEFT JOIN — LEFT JOIN is required, otherwise agents with zero activities or zero opportunities would drop out of the result and the funnel would be incomplete. COALESCE fills NULLs as 0, and close_rate returns NULL when the denominator is 0. `ORDER BY closed_won_12m IS NULL, closed_won_12m DESC` is a trick to push agents with no wins to the bottom. One row = one active agent's full funnel.

```sql
WITH activity_stats AS (
    SELECT Agent_Id__c, COUNT(*) AS n_activities
    FROM crm_agent_activity
    WHERE Activity_Date__c >= date('2026-06-05', '-12 months')
    GROUP BY Agent_Id__c
),
opp_stats AS (
    SELECT Owner_Agent_Id__c AS agent_id,
           COUNT(*) AS n_opps,
           SUM(CASE WHEN StageName = 'Closed Won' THEN 1 ELSE 0 END) AS n_won
    FROM crm_opportunity
    WHERE CreatedDate >= date('2026-06-05', '-12 months')
    GROUP BY Owner_Agent_Id__c
)
SELECT
    a.First_Name__c || ' ' || a.Last_Name__c AS agent_name,
    a.Tier__c,
    COALESCE(act.n_activities, 0) AS activities_12m,
    COALESCE(o.n_opps, 0)         AS opportunities_12m,
    COALESCE(o.n_won, 0)          AS closed_won_12m,
    CASE WHEN o.n_opps > 0
         THEN ROUND(100.0 * o.n_won / o.n_opps, 1)
         ELSE NULL END AS close_rate_pct
FROM crm_agent a
LEFT JOIN activity_stats act ON a.Id = act.Agent_Id__c
LEFT JOIN opp_stats o ON a.Id = o.agent_id
WHERE a.IsActive__c = 1
ORDER BY closed_won_12m IS NULL, closed_won_12m DESC
LIMIT 20;
```

**Expected result:**
20 active agents with their full funnel. Top performers should show both high activity volume AND a high close rate; mid-tier agents typically have decent activity volume but lower close rates.

---

### Query 8: Buyer-to-Listing Match Candidates

**Business context:**
The listing-to-buyer matching feature (Module 3 REQ-12) needs a SQL-only quick baseline before the embedding-based recommender is built. For each active buyer with preferences, find matching listings: price band, bedroom count, preferred ZIP. This query also becomes a test fixture for the Streamlit recommender — its output is the "obviously correct" set of matches the embedding model must reproduce.

**Category:** Join + filter
**Difficulty:** Intermediate
**Business role:** Ops

**Approach:**
For each buyer with preferences, find matching listings. Start from `crm_contact`, join `mls_property` on `Preferred_Zip__c = property.ZIP` AND `Preferred_Bed_Count__c = property.BED_COUNT`, then join `mls_listing` restricted to `STATUS_CD='ACT'` with list price inside the buyer's budget band. INNER JOIN is intentional (not LEFT) — we only want actual matches; non-matches don't belong. One output row = one "buyer × candidate listing" pairing. Gotcha: ZIP is a string match, and the ~5% of dirty ZIP+4 values won't match (which is exactly what the downstream cleaning is supposed to fix), so this is just a SQL baseline; the embedding model should recall more.

```sql
SELECT
    c.Id              AS contact_id,
    c.FirstName || ' ' || c.LastName AS buyer_name,
    c.Preferred_Min_Price__c,
    c.Preferred_Max_Price__c,
    c.Preferred_Bed_Count__c,
    c.Preferred_Zip__c,
    l.MLS_NUMBER,
    l.LIST_PRICE,
    p.BED_COUNT,
    p.ZIP
FROM crm_contact c
JOIN mls_property p
  ON p.ZIP = c.Preferred_Zip__c
 AND p.BED_COUNT = c.Preferred_Bed_Count__c
JOIN mls_listing l
  ON l.PROPERTY_ID = p.PROPERTY_ID
 AND l.STATUS_CD = 'ACT'
 AND l.LIST_PRICE BETWEEN c.Preferred_Min_Price__c AND c.Preferred_Max_Price__c
WHERE c.Contact_Type__c IN ('Buyer', 'Both')
  AND c.Preferred_Min_Price__c IS NOT NULL
ORDER BY c.Id, l.LIST_PRICE
LIMIT 50;
```

**Expected result:**
A list of buyer-listing pairs, each satisfying every criterion. Most buyers have 0-3 matches; a handful have many. The recommender uses these as its "must include" set.

---

### Query 9: Sale-to-List Ratio Trend by Market (Quarterly)

**Business context:**
SLR is the best leading indicator of market warming/cooling. When SLR rises above 1.0, bidding wars are showing up; when it falls below 0.97, sellers are conceding. The competitive-positioning AI agent uses per-market SLR trend as one of its key inputs. This query also feeds the "market temperature" gauge on the Market Pulse dashboard.

**Category:** Date aggregation
**Difficulty:** Intermediate
**Business role:** Analyst

**Approach:**
SLR trend at the quarterly level. Same join chain as Query 1 from sold all the way up to `geo_market`, but this time slice time by quarter: concatenate `strftime('%Y')` with `'-Q' || ((month+2)/3)` to manually compute the quarter number. Group by market + quarter; `AVG(LIST_TO_SALE_RATIO)` is the quarter's average SLR for that market. One row = one market-quarter. Bay Area should be consistently the highest (most competition), with all markets hovering around 1.00.

```sql
SELECT
    m.market_code,
    strftime('%Y', s.CLOSE_DT) || '-Q' || ((CAST(strftime('%m', s.CLOSE_DT) AS INTEGER) + 2) / 3) AS quarter,
    COUNT(*) AS n_sold,
    ROUND(AVG(s.LIST_TO_SALE_RATIO), 4) AS avg_slr
FROM mls_sold_transaction s
JOIN mls_listing l ON s.LISTING_ID = l.LISTING_ID
JOIN mls_property p ON l.PROPERTY_ID = p.PROPERTY_ID
JOIN geo_zip_code z ON p.zip_id = z.zip_id
JOIN geo_city ci ON z.city_id = ci.city_id
JOIN geo_county co ON ci.county_id = co.county_id
JOIN geo_market m ON co.market_id = m.market_id
GROUP BY m.market_code, quarter
ORDER BY m.market_code, quarter;
```

**Expected result:**
~42 rows (3 markets × 14 quarters). Bay Area should consistently be the highest SLR (most competition). All markets should swing around 1.00 with quarter-over-quarter changes of ~3-4 basis points.

---

### Query 10: Office Performance Scorecard

**Business context:**
At the end of every month, Sarah Mitchell needs to see the office-by-office scorecard: per office, agent count, deal count, GCI, average sale price. Drives expansion decisions ("should we open another office in Bellevue?") and headcount planning. Today Emily produces this by hand — this query is the source of truth that replaces her Excel.

**Category:** Multi-join aggregation
**Difficulty:** Intermediate
**Business role:** Manager

**Approach:**
An office scorecard puts "people, deals, dollars" on a single row. Anchor on `crm_office`, LEFT JOIN active `crm_agent`, then LEFT JOIN trailing-12-month `crm_commission_split`, then LEFT JOIN `crm_transaction` for the sale price. LEFT JOIN throughout keeps offices in the result even when they haven't closed anything recently. When aggregating, use `COUNT(DISTINCT a.Id)` and `COUNT(DISTINCT cs.Transaction_Id__c)` — because one office has many agents and one transaction has many splits, multi-join fan-out will double-count without DISTINCT. One row = one office.

```sql
SELECT
    o.Name AS office,
    COUNT(DISTINCT a.Id) AS agent_count,
    COUNT(DISTINCT cs.Transaction_Id__c) AS deal_count,
    ROUND(SUM(cs.Agent_Take__c + cs.Company_Take__c) / 1e6, 2) AS gross_commission_millions,
    ROUND(AVG(t.Sale_Price__c) / 1000, 0) AS avg_sale_price_k
FROM crm_office o
LEFT JOIN crm_agent a ON a.Office_Id__c = o.Id AND a.IsActive__c = 1
LEFT JOIN crm_commission_split cs ON cs.Agent_Id__c = a.Id
    AND cs.Payout_Date__c >= date('2026-06-05', '-12 months')
LEFT JOIN crm_transaction t ON cs.Transaction_Id__c = t.Id
GROUP BY o.Id
ORDER BY gross_commission_millions IS NULL, gross_commission_millions DESC;
```

**Expected result:**
8 rows (one per office). Bay Area offices usually lead in GCI because of higher price points. The query exposes offices that are over- or under-performing relative to their agent count.

---

### Query 11: Listings with the Most Price Reductions

**Business context:**
A listing with 3 or more price reductions is a strong signal of initial overpricing. Emily wants to know which Crestline-listed properties show this pattern repeatedly, so she can debrief the pricing methodology behind them. This also feeds the AI agent's "overpriced detector" (Module 4 REQ-13).

**Category:** Subquery
**Difficulty:** Intermediate
**Business role:** Analyst

**Approach:**
Many price reductions on a listing signal that the initial price was too high. Price reductions live in `mls_listing_event_history` with `EVENT_TYPE='PRICE_CHANGE'`. We use a correlated subquery: for each listing, count its PRICE_CHANGE events, then `WHERE (subquery) >= 3` filters to listings with 3+ reductions. You could also write this as join + group by + having, but the subquery reads more directly. Order by number of reductions, then by DOM. One row = one repeatedly-reduced listing; most of them also have high DOM, confirming "repeated price cuts = slow sale."

```sql
SELECT
    l.MLS_NUMBER,
    l.LIST_PRICE AS original_price,
    (SELECT COUNT(*) FROM mls_listing_event_history h
     WHERE h.LISTING_ID = l.LISTING_ID AND h.EVENT_TYPE = 'PRICE_CHANGE') AS n_reductions,
    l.STATUS_CD,
    l.DOM
FROM mls_listing l
WHERE (SELECT COUNT(*) FROM mls_listing_event_history h
       WHERE h.LISTING_ID = l.LISTING_ID AND h.EVENT_TYPE = 'PRICE_CHANGE') >= 3
ORDER BY n_reductions DESC, l.DOM DESC
LIMIT 20;
```

**Expected result:**
~20 listings with 3 price reductions (the generator's max). Most should also have a high DOM, confirming the correlation between "repeated reductions" and "slow sale."

---

### Query 12: Mortgage Rate vs. Sales Volume Correlation

**Business context:**
The CEO's claim that "high mortgage rates killed 2024 transaction volume" needs evidence. This query joins monthly Freddie Mac data with sold volume so an analyst can visually inspect the inverse relationship. It's also a cross-domain integrity check — verifying that the macro narrative baked into the generator is actually reflected in the data.

**Category:** Cross-domain join + CTE
**Difficulty:** Advanced
**Business role:** Analyst

**Approach:**
We want to align sold volume and rates by month, but they live in different domains at different grains (sold is per-deal, rate is per-week). So we collapse each to "one row per month" in its own CTE: `monthly_sold` counts deals via `strftime('%Y-%m', CLOSE_DT)`, `monthly_rate` averages `Rate_30Y_Fixed` by month. Then we join on year_month. This is a cross-domain join (MLS × external). One row = one month; plotted as a dual-axis line chart you can see the inverse relationship — rates climbing in late 2023, volume dropping through 2024.

```sql
WITH monthly_sold AS (
    SELECT
        strftime('%Y-%m', CLOSE_DT) AS year_month,
        COUNT(*) AS sold_count
    FROM mls_sold_transaction
    GROUP BY year_month
),
monthly_rate AS (
    SELECT
        strftime('%Y-%m', Week_End_Date) AS year_month,
        AVG(Rate_30Y_Fixed) AS avg_rate
    FROM ext_freddie_mac_mortgage_rate
    GROUP BY year_month
)
SELECT
    s.year_month,
    s.sold_count,
    ROUND(r.avg_rate, 3) AS avg_30y_rate
FROM monthly_sold s
JOIN monthly_rate r ON s.year_month = r.year_month
ORDER BY s.year_month;
```

**Expected result:**
~42 monthly rows. Plotted as a dual-axis line chart: rates climbing into late 2023, sold volume falling through 2024.

---

### Query 13: Sales Pipeline Velocity by Stage

**Business context:**
Rachel Torres wants to know where opportunities are getting stuck. Counting how many opportunities currently sit in each pipeline stage exposes bottlenecks — e.g., too many "Under Contract" but few closes means deals are getting killed in inspection, which prompts manager intervention. Rendered as a funnel chart on the Agent Scorecard.

**Category:** Aggregation
**Difficulty:** Basic
**Business role:** Manager

**Approach:**
Find where the pipeline is getting stuck. Just `crm_opportunity` — group by `StageName`, count opportunities, average/sum the amount, restricted to the trailing 6 months (`CreatedDate`). The hard part isn't the aggregation, it's the sort: stages are strings, so default sort order is meaningless; use `ORDER BY CASE StageName WHEN 'Lead' THEN 1 ...` to force funnel order. One row = one stage; a healthy funnel narrows from Lead to Closed Won.

```sql
SELECT
    StageName,
    COUNT(*)                  AS opp_count,
    ROUND(AVG(Amount) / 1000, 0) AS avg_amount_k,
    ROUND(SUM(Amount) / 1e6, 1)  AS total_pipeline_millions
FROM crm_opportunity
WHERE CreatedDate >= date('2026-06-05', '-6 months')
GROUP BY StageName
ORDER BY
    CASE StageName
        WHEN 'Lead' THEN 1 WHEN 'Qualified' THEN 2 WHEN 'Showing' THEN 3
        WHEN 'Offer' THEN 4 WHEN 'Under Contract' THEN 5
        WHEN 'Closed Won' THEN 6 WHEN 'Closed Lost' THEN 7
    END;
```

**Expected result:**
7 rows in pipeline order. The funnel narrows from Lead → Closed Won as expected.

---

### Query 14: Lost-Deal Reason Analysis

**Business context:**
Why are we losing deals? Sarah wants the top reasons for lost opportunities so the company can address each systematically (e.g., "lost to competitor" dominates → market positioning problem; "financing fell through" dominates → partner-bank problem).

**Category:** Aggregation + filter
**Difficulty:** Basic
**Business role:** Manager

**Approach:**
Why we lost deals. Filter `StageName='Closed Lost'` with `Lost_Reason__c` not null, group by reason, count occurrences, average the amount, sort descending. One table, one GROUP BY — Basic. One row = one loss reason. Conclusions translate directly into actions: "lost to competitor" dominates → a market positioning problem; "financing fell through" dominates → a partner-bank problem.

```sql
SELECT
    Lost_Reason__c,
    COUNT(*) AS lost_count,
    ROUND(AVG(Amount) / 1000, 0) AS avg_lost_amount_k
FROM crm_opportunity
WHERE StageName = 'Closed Lost'
  AND Lost_Reason__c IS NOT NULL
GROUP BY Lost_Reason__c
ORDER BY lost_count DESC;
```

**Expected result:**
~6 reasons ordered by frequency. Used for root-cause action planning.

---

### Query 15: Agent Tenure vs. Commission Income

**Business context:**
HR wants to validate the hypothesis "more senior agents earn more" before approving a new tier-based commission structure. This query buckets active agents by years with the company and computes their average GCI, demonstrating the relationship empirically. Drives compensation policy.

**Category:** CTE + date math
**Difficulty:** Advanced
**Business role:** Analyst

**Approach:**
Validate "senior agents earn more." First, in CTE `agent_gci`, compute two things per active agent: `julianday` diff / 365.25 for tenure_years, and `SUM(Agent_Take__c)` for **all-time cumulative** GCI (note: no 12-month filter here, so the amount is 3-4x what Query 3 reports). The outer query CASEs tenure into buckets (0-1, 2-3, 4-5, 6+ years) and computes avg/max GCI per bucket. One row = one tenure bucket. The averages should rise monotonically and the max in the 6+ bucket should dwarf the others — that's the combined effect of tenure-weighted opportunity assignment plus tier-based commission splits.

```sql
WITH agent_gci AS (
    SELECT
        a.Id,
        CAST((julianday('2026-06-05') - julianday(a.Hire_Date__c)) / 365.25 AS INTEGER) AS tenure_years,
        a.Tier__c,
        COALESCE(SUM(cs.Agent_Take__c), 0) AS gci
    FROM crm_agent a
    LEFT JOIN crm_commission_split cs ON cs.Agent_Id__c = a.Id
    WHERE a.IsActive__c = 1
    GROUP BY a.Id
)
SELECT
    CASE
        WHEN tenure_years < 2 THEN '0-1 yr'
        WHEN tenure_years < 4 THEN '2-3 yr'
        WHEN tenure_years < 6 THEN '4-5 yr'
        ELSE '6+ yr'
    END AS tenure_bucket,
    COUNT(*) AS agent_count,
    ROUND(AVG(gci), 0) AS avg_gci,
    ROUND(MAX(gci), 0) AS max_gci
FROM agent_gci
GROUP BY tenure_bucket
ORDER BY MIN(tenure_years);
```

**Expected result:**
4 tenure buckets — this is **per-agent all-time cumulative GCI** (unlike Query 3's 12 months), so the dollar amounts are roughly 3-4x Q3's. With seed=42, approximate ranges:

| Bucket | Avg GCI | Max GCI |
|---|---|---|
| 0-1 yr | ~$150-200K | ~$300-450K |
| 2-3 yr | ~$220-280K | ~$350-450K |
| 4-5 yr | ~$250-330K | ~$500-650K |
| 6+ yr | **~$550-700K** | **~$3M-$4M** |

Pattern: averages rise monotonically and `max GCI` blows out (the 6+ year max is ~8-10x the 0-1 year max). This is the combined effect of two layers — (a) tenure-weighted opportunity Pareto routes more deals to senior agents; (b) the tiered `Commission_Split_Pct__c` lets them keep a larger share of each deal. Together, they validate the tier compensation structure empirically.

---

### Query 16: Duplicate Contact Detection

**Business context:**
Crestline's CRM has accumulated duplicate records over the years — the same buyer being captured by different agents at different open houses. The dbt staging layer must dedupe before building the Customer Intelligence Mart. This query identifies likely duplicates (same email + different Id) so they can be merged.

**Category:** Self-join / GROUP BY
**Difficulty:** Intermediate
**Business role:** Ops

**Approach:**
CRM accumulates duplicate contacts over time (same buyer captured by different agents at different open houses). The simplest dedup signal is shared email. Group by `Email`, `HAVING COUNT(*) > 1` finds the duplicates; `GROUP_CONCAT` pulls the Ids and names into one column for human review. One row = one email that appears more than once. Gotcha: filter `WHERE Email IS NOT NULL` first, or a bunch of NULLs would be incorrectly bucketed together. The slight spelling differences in the `name_variants` column are exactly what the downstream dedup logic has to handle.

```sql
SELECT
    Email,
    COUNT(*) AS occurrences,
    GROUP_CONCAT(Id, '; ') AS contact_ids,
    GROUP_CONCAT(FirstName || ' ' || LastName, ' | ') AS name_variants
FROM crm_contact
WHERE Email IS NOT NULL
GROUP BY Email
HAVING COUNT(*) > 1
ORDER BY occurrences DESC, Email
LIMIT 25;
```

**Expected result:**
~100-150 emails that appear in multiple contact records. The `name_variants` column shows minor spelling differences — exactly what the dedup logic has to handle.

---

### Query 17: Sale Prices Above Zillow ZHVI

**Business context:**
The competitive-positioning AI uses Zillow ZHVI as a market-level fair-value baseline. This query identifies properties whose sale price for the month was meaningfully above the zip's ZHVI — these are "above-market" sales, possibly indicating a hot micro-market or a property with unique appeal. The AI agent uses this list as positive examples of pricing skill.

**Category:** Cross-domain join
**Difficulty:** Advanced
**Business role:** Analyst

**Approach:**
Find sales that clearly beat Zillow's fair value. Join sold all the way down to `geo_zip_code`, then cross-domain join `ext_zillow_home_value_index`: the trick is the two join conditions — zip matches, and the month matches. Zillow is one row per month (first-of-month date), so use `date(CLOSE_DT, 'start of month')` to round the close date to the first of the month before matching to `zh.Date`. Filter `SALE_PRICE > ZHVI * 1.15` and sort by percentage above. One row = one above-market sale, most of which fall in HOT zips.

```sql
SELECT
    z.zip5,
    s.CLOSE_DT,
    s.SALE_PRICE,
    zh.ZHVI                                  AS zillow_zhvi,
    ROUND(100.0 * (s.SALE_PRICE - zh.ZHVI) / zh.ZHVI, 1) AS pct_above_zhvi
FROM mls_sold_transaction s
JOIN mls_listing l ON s.LISTING_ID = l.LISTING_ID
JOIN mls_property p ON l.PROPERTY_ID = p.PROPERTY_ID
JOIN geo_zip_code z ON p.zip_id = z.zip_id
JOIN ext_zillow_home_value_index zh
  ON zh.zip_id = z.zip_id
 AND zh.Date = date(s.CLOSE_DT, 'start of month')
WHERE s.SALE_PRICE > zh.ZHVI * 1.15
ORDER BY pct_above_zhvi DESC
LIMIT 25;
```

**Expected result:**
~25 outlier sales that beat ZHVI by 15%+. The overwhelming majority come from HOT zips (94301, 90210, etc.).

---

### Query 18: Commission Payout Forecast for the Next 30 Days

**Business context:**
Finance needs a cash-outflow forecast: how much commission needs to be paid out in the next 30 days, and to whom? Treasury uses this to plan operating cash. The Controller runs it weekly and joins it with `crm_agent` to build a payroll preview.

**Category:** Filter + aggregation
**Difficulty:** Basic
**Business role:** Finance

**Approach:**
Finance needs to forecast commission cash outflow for the next 30 days. Look at `crm_commission_split`, filter `Payout_Date__c` to `['2026-06-05', +30 days]`, group by payout date, sum the agent take and company take separately. One row = one payout date. Note: the payout date is scheduled 5-15 days after close, so this window only catches the tail end of deals that closed in late May / early June — usually a sparse output (10-20 rows). Treasury uses it to plan operating cash.

```sql
SELECT
    cs.Payout_Date__c,
    COUNT(*) AS payout_count,
    ROUND(SUM(cs.Agent_Take__c), 0) AS total_to_agents,
    ROUND(SUM(cs.Company_Take__c), 0) AS total_to_company
FROM crm_commission_split cs
WHERE cs.Payout_Date__c BETWEEN date('2026-06-05') AND date('2026-06-05', '+30 days')
GROUP BY cs.Payout_Date__c
ORDER BY cs.Payout_Date__c;
```

**Expected result:**
A daily payout schedule for the next 30 days. The Finance team uses it to confirm bank-account funding levels. Note: the dataset's effective date is 2026-06-05, so this 30-day forward window only contains payouts for deals that closed in late May / early June — typically a sparse window (10-20 rows). Running it during a denser closing period (early September, say) would naturally produce a denser payout schedule.

---

### Query 19: Buyer-Demand Pressure on Active Listings

**Business context:**
Steps 6-8 of Module 4 (opportunity identification, REQ-15) need a **buyer-demand pressure score** for each listing so the AI agent can flag "high demand but slightly overpriced" (many showings but no offers — the price just edged past the buyer's psychology) vs. "weak demand" (few showings — needs marketing intervention). This query computes the demand snapshot per active listing using the new `mls_listing_showing` table (joinable with `ext_zillow_market_temperature` for added context).

**Category:** Join + aggregation
**Difficulty:** Intermediate
**Business role:** Ops

**Approach:**
Label each active listing with a "buyer demand pressure" signal. Anchor on `mls_listing` (`STATUS_CD='ACT'`), LEFT JOIN `mls_listing_showing` — LEFT JOIN is required, otherwise listings with zero showings (which are exactly LOW_DEMAND) would be filtered out. Group by listing, count total showings, count offers via `SUM(CASE WHEN Resulted_In_Offer__c...)`, and then a CASE translates those into a demand_signal (many showings but zero offers = price slightly high; very few showings = needs marketing). `HAVING days_on_market > 7` excludes brand-new listings. One row = one active listing's demand snapshot.

```sql
SELECT
    l.MLS_NUMBER,
    p.STREET_NUM || ' ' || p.STREET_NAME AS address,
    z.zip5,
    z.temperature                    AS zip_temperature,
    l.LIST_PRICE,
    CAST(julianday('2026-06-05') - julianday(l.LIST_DT) AS INTEGER) AS days_on_market,
    COUNT(s.SHOWING_ID)              AS total_showings,
    SUM(CASE WHEN s.Resulted_In_Offer__c = 1 THEN 1 ELSE 0 END) AS offers_received,
    CASE
        WHEN COUNT(s.SHOWING_ID) >= 5 AND SUM(CASE WHEN s.Resulted_In_Offer__c = 1 THEN 1 ELSE 0 END) = 0
            THEN 'HIGH_INTEREST_NO_OFFER (price slightly high?)'
        WHEN COUNT(s.SHOWING_ID) < 2
            THEN 'LOW_DEMAND (needs marketing intervention)'
        WHEN SUM(CASE WHEN s.Resulted_In_Offer__c = 1 THEN 1 ELSE 0 END) > 0
            THEN 'OFFERS_RECEIVED'
        ELSE 'NORMAL_FUNNEL'
    END AS demand_signal
FROM mls_listing l
JOIN mls_property p ON l.PROPERTY_ID = p.PROPERTY_ID
JOIN geo_zip_code z ON p.zip_id = z.zip_id
LEFT JOIN mls_listing_showing s ON s.LISTING_ID = l.LISTING_ID
WHERE l.STATUS_CD = 'ACT'
GROUP BY l.LISTING_ID
HAVING days_on_market > 7
ORDER BY days_on_market DESC, total_showings DESC
LIMIT 30;
```

**Expected result:**
Up to 30 rows (per the LIMIT) — active listings sorted by days-on-market descending, with their demand snapshots. The `demand_signal` column feeds directly into the AI agent's recommender: `HIGH_INTEREST_NO_OFFER` are price-cut candidates; `LOW_DEMAND` need marketing changes. Drop the LIMIT to see the full set (typically 400-800 active listings).

---

### Query 20: Crestline Market-Share Trend by Zip (YoY)

**Business context:**
The CEO's narrative for the board ("we're gaining share in HOT submarkets") is currently anecdotal — nobody has actually computed Crestline's share of MLS listing inventory by zip across years. This query produces the cohort: for each (zip × year), what fraction of all listings was Crestline-branded, and how did that change YoY? Drives strategic decisions about office expansion and agent hiring.

**Category:** Window function
**Difficulty:** Advanced
**Business role:** Executive

**Approach:**
Compute Crestline's listing share per zip across years. CTE `zip_year` counts, for each (zip, year), total listings and Crestline listings (`IS_CRESTLINE_LISTING = 1`), with share = crestline/total. The outer query then `LAG(...) OVER (PARTITION BY zip5 ORDER BY year)` pulls the prior year's share, and the difference is share_change_pts. The LAG window function lets year-over-year change be computed in a single row. One row = one zip-year. Watch for HOT zips where share keeps growing (positive trend) vs. COOL zips where competitors are overtaking us.

```sql
WITH zip_year AS (
    SELECT
        z.zip5,
        z.temperature,
        CAST(strftime('%Y', l.LIST_DT) AS INTEGER) AS year,
        COUNT(*) AS total_listings,
        SUM(CASE WHEN l.IS_CRESTLINE_LISTING = 1 THEN 1 ELSE 0 END) AS crestline_listings
    FROM mls_listing l
    JOIN mls_property p ON l.PROPERTY_ID = p.PROPERTY_ID
    JOIN geo_zip_code z ON p.zip_id = z.zip_id
    WHERE l.LIST_DT >= '2023-01-01'
    GROUP BY z.zip5, z.temperature, year
)
SELECT
    zip5,
    temperature,
    year,
    total_listings,
    crestline_listings,
    ROUND(100.0 * crestline_listings / total_listings, 1) AS crestline_share_pct,
    ROUND(100.0 * crestline_listings / total_listings, 1)
      - LAG(ROUND(100.0 * crestline_listings / total_listings, 1))
          OVER (PARTITION BY zip5 ORDER BY year) AS share_change_pts
FROM zip_year
ORDER BY zip5, year;
```

**Expected result:**
~240 rows (60 zips × 4 years). The `share_change_pts` column shows YoY change in Crestline's listing share. Watch for HOT zips where Crestline is consistently gaining share (positive trend) vs. COOL zips where competitors are gaining ground.

---

## Query Category Summary

| Category | Count | Query #s |
|----------|-------|----------|
| Aggregation | 7 | 1, 3, 4, 13, 14, 18, 19 |
| Join operations | 3 | 8, 10, 19 |
| Window functions | 3 | 2, 6, 20 |
| Date/time analysis | 3 | 5, 9, 12 |
| Subqueries / CTEs | 4 | 7, 11, 15, 17 |
| Pattern / text matching | 1 | 16 |

(Note: some queries appear in multiple categories — e.g., Q19 is both a Join and an Aggregation. The total exceeds 20.)

## Business Role Coverage

| Role | Count | Query #s |
|------|-------|----------|
| Executive / C-level | 3 | 1, 6, 20 |
| Manager | 5 | 3, 7, 10, 13, 14 |
| Analyst | 7 | 2, 4, 9, 11, 12, 15, 17 |
| Ops | 4 | 5, 8, 16, 19 |
| Finance | 1 | 18 |

## Difficulty Distribution

| Difficulty | Count | Query #s |
|------------|-------|----------|
| Basic | 6 | 1, 3, 4, 13, 14, 18 |
| Intermediate | 9 | 2, 5, 6, 8, 9, 10, 11, 16, 19 |
| Advanced | 5 | 7, 12, 15, 17, 20 |

## Business Question → Query Mapping

Every query traces back to a business question listed in Section 5 of `01-...business_context.md`.

| Business question | Corresponding queries |
|-------------------|-----------------------|
| 1. Is the pricing right (Pricing) | Query 2, 11, 17 |
| 2. Who are the top-producing agents, and why (Performance) | Query 3, 7, 10, 15 |
| 3. Is the market heating up or cooling down (Market temperature) | Query 4, 5, 9 |
| 4. Where are the opportunities (Opportunity discovery) | Query 8, 19, 20 |
| 5. Where is volume headed and how will cash flow (Forecast & cash flow) | Query 1, 6, 12, 13, 18 |
| 6. Customer matching and data quality (Matching & data quality) | Query 8, 14, 16 |

---

## Notes

- All queries are written in **SQLite 3.x syntax** and tested on the generated `.sqlite` file. Date filters use the literal `'2026-06-05'` (the dataset's effective current date) rather than `date('now')`, so they return non-empty results regardless of when they run. On Redshift/Postgres, swap for `current_date - interval '12 months'`.
- The numbers in the TSV filenames indicate **table load order** (a topological sort) — they are unrelated to the query numbers here.
- The dataset's effective `CURRENT_DATE = 2026-06-05`. All time-window queries reference this date explicitly so the results stay reproducible.
- All `JOIN` paths preserve referential integrity. If a query returns 0 rows when you expected data, double-check the date filter — most of the dataset's activity falls in 2023-2026, not "now."
