# Traditional Media — Cinema Showtime and Concession Profitability SQL Query Set

> This document covers the `traditional_media_cinema_exhibition_yield_management_medium` dataset. For business background, see `01-traditional_media_cinema_exhibition_yield_management_medium_business_context.md`; for the data structure, see `02-traditional_media_cinema_exhibition_yield_management_medium_er_document.md`.
>
> **REFERENCE_DATE convention:** This dataset is anchored to a fixed reference date, **2026-06-30**, with a data window of **2026-04-01 through 2026-06-30**. Wherever a query below touches a date boundary, it writes the literal date directly (e.g. `'2026-06-30'`) instead of using `DATE('now')` — so the SQL in this document produces fully reproducible results no matter what day you run it.

---

## How to Use This Document

You're a newly hired BI Analyst at Lakeshore Cinemas. The 20 queries in this document are the first batch of assignments handed to you by the CFO — covering five major problem areas: concession gross margin, premium-screen profit and loss, late-night minimum attendance clauses, screen utilization, and concession attach rates. Each query has five parts:

1. **Business Context** — who is asking this question, why now, and what decision the answer will drive.
2. **Tags** — category, difficulty, and the asking role, so you can browse by skill or by business line.
3. **Approach** — before looking at the SQL, a clear walkthrough of which tables to touch, where the join pitfalls are, what the aggregation grain is, and whether a CTE or window function is needed.
4. **SQL** — code that runs directly against this dataset's SQLite database.
5. **Expected Result & Business Takeaway** — what the result looks like, which business trap it maps to, and what to do next.

Every query traces back to one of the five core business questions (Q1-Q5) listed in Section 5 of the business context document, or to a routine operational question. This SQL isn't meant to be "run once and glanced at" — it's meant to be studied. Pay attention to why each JOIN is written the way it is, and what business meaning each aggregation grain carries.

---

## Query Index

| # | Title | Business Role | SQL Category | Difficulty |
|------|------|----------|----------|------|
| 1 | Recognized concession gross margin vs. cash-adjusted gross margin | CFO | Aggregation + CTE | Intermediate |
| 2 | Breaking down loyalty redemption dilution of concession margin by theater | VP of Concessions & Merchandising | Aggregation + Join + Subquery | Intermediate |
| 3 | Does tiered redemption frequency match the "Gold ≈ 3.6x Standard" hypothesis | Director of Loyalty & Marketing | Aggregation + Join | Basic |
| 4 | Per-screen quarterly net contribution ranking for each IMAX screen | Facilities & Engineering Manager | CTE + Window Function + Join | Advanced |
| 5 | Average net contribution comparison for Premium vs. IMAX screens by market tier | BI Analyst | Aggregation + Join | Intermediate |
| 6 | Monthly fixed-cost trend by screen type | Facilities & Engineering Manager | Aggregation + Date Analysis | Basic |
| 7 | Weekend vs. weekday ticket price and occupancy comparison | VP of Film Programming | Aggregation + CTE | Intermediate |
| 8 | List of late-night "minimum guarantee" showtimes suspected of buyback padding | Regional Operations Manager | Join + Filter | Basic |
| 9 | Count of suspected padded showtimes and comp attendance by theater | Regional Operations Manager | Aggregation + CTE | Intermediate |
| 10 | Screen utilization (occupancy) ranking to identify de-installation candidates | BI Analyst | Window Function + Aggregation | Advanced |
| 11 | Overall utilization comparison, Primary vs. Secondary markets | VP of Film Programming | Aggregation + Join | Basic |
| 12 | Monthly box office and attendance trend | CFO | Date Analysis + Window Function | Advanced |
| 13 | Concession attach rate comparison by daypart | BI Analyst | Aggregation + Join + CTE | Intermediate |
| 14 | Popcorn family vs. other concession categories: sales performance | BI Analyst | Aggregation + Text Matching | Basic |
| 15 | Top 10 best-selling concession SKUs (by gross profit) | BI Analyst | Window Function + Aggregation | Intermediate |
| 16 | Quarterly box office and concession revenue summary by theater (board materials) | Concession Operations Supervisor | Aggregation + Join + Date Analysis | Intermediate |
| 17 | Per-attendee concession spend by daypart | Concession Operations Supervisor | Aggregation + Date Analysis | Intermediate |
| 18 | Film booking coverage by distributor | VP of Film Programming | Aggregation + Join | Basic |
| 19 | Cross-theater loyalty redemption share | BI Analyst | Aggregation + Join | Basic |
| 20 | Theater blended contribution ranking (box office + concession gross profit − fixed cost) | CFO | CTE + Window Function + Multi-table Join | Advanced |

---

## Query 1: Recognized Concession Gross Margin vs. Cash-Adjusted Gross Margin

**Business Context.** The CFO is putting together the "Concessions" page of the Q2 2026 board deck. Over the past several quarters, the reported concession gross margin has stayed comfortably above 70%, and it's the central proof point in the company's narrative that "we're not just selling movie tickets." But at the last leadership meeting, the VP of Concessions & Merchandising mentioned that Lakeshore Rewards redemption volume has been climbing fast over the past two years, and the CFO worries that the "concession revenue" line on the books might be inflated by loyalty redemptions that never generated any cash — if that's true, the margin the company actually collects in cash could be meaningfully lower than what the financial statements show, and the board could end up seeing a prettier story than reality. She needs both a "recognized" and a "cash" version of the number before the board deck is finalized next week. This query maps to business question Q1.

**Tags.** Category: Aggregation + CTE | Difficulty: Intermediate | Role: CFO

**Approach.** This one touches two tables at once: `concession_sale` (regular paid sales) and `loyalty_redemption` (loyalty redemptions). The key is understanding the difference between "recognized revenue" and "cash revenue" — recognized revenue books redemptions at their full `item_full_price`, while cash revenue only counts `concession_sale.gross_revenue` (redemptions generate no cash). The cost side is the same under both views: redeemed items still carry a real `item_unit_cost`. Use two CTEs to aggregate each table separately, then hand-combine the two margin figures in the final SELECT — no JOIN is needed since there's no shared dimension to connect the two tables on; each is aggregated independently and combined via a Cartesian product (multiplying two single-row CTEs is equivalent to laying them side by side).

```sql
WITH paid_sales AS (
    SELECT
        SUM(gross_revenue) AS cash_revenue,
        SUM(cogs_amount) AS cogs_from_paid,
        SUM(units_sold) AS paid_units
    FROM concession_sale
    WHERE sale_date BETWEEN '2026-04-01' AND '2026-06-30'
),
redemptions AS (
    SELECT
        SUM(item_full_price) AS phantom_revenue,
        SUM(item_unit_cost) AS cogs_from_redeemed,
        COUNT(*) AS redeemed_units
    FROM loyalty_redemption
    WHERE redemption_date BETWEEN '2026-04-01' AND '2026-06-30'
)
SELECT
    ps.cash_revenue,
    ps.cash_revenue + rd.phantom_revenue AS recognized_revenue,
    ps.cogs_from_paid + rd.cogs_from_redeemed AS total_cogs,
    ROUND(
        100.0 * ((ps.cash_revenue + rd.phantom_revenue) - (ps.cogs_from_paid + rd.cogs_from_redeemed))
        / (ps.cash_revenue + rd.phantom_revenue), 2
    ) AS recognized_margin_pct,
    ROUND(
        100.0 * (ps.cash_revenue - (ps.cogs_from_paid + rd.cogs_from_redeemed)) / ps.cash_revenue, 2
    ) AS cash_margin_pct,
    ROUND(100.0 * rd.redeemed_units / (ps.paid_units + rd.redeemed_units), 2) AS redemption_share_pct
FROM paid_sales ps, redemptions rd;
```

**Expected Result & Business Takeaway.** The result is a single row: `recognized_margin_pct` is roughly **72.6%**, `cash_margin_pct` is roughly **71.1%**, a gap of about **1.5 percentage points**; `redemption_share_pct` (redeemed units as a share of total units) is about **5.4%**. In other words, the margin shown in the financials is about 1.5 points higher than the margin the company actually collects in cash, and the entire gap comes from booking free redemptions at full price. That gap looks small, but it's happening on a line with a 70%+ margin that the company keeps almost entirely, and it compounds quarter over quarter as loyalty redemption volume grows — 1.5 percentage points multiplied across the full year's concession volume is real money that could mislead the board. The CFO should present both versions in the board deck and push finance to change the recognition convention — using `cash_margin_pct`, not `recognized_margin_pct`, as the metric management actually tracks.

---

## Query 2: Breaking Down Loyalty Redemption Dilution of Concession Margin by Theater

**Business Context.** After seeing the company-wide numbers from Query 1, the VP of Concessions & Merchandising wants to know whether the problem is concentrated in a handful of theaters — if it's really just a few managers overusing redemptions as a promotional tool, that's a targeted operational fix rather than a company-wide policy gap. She needs a theater-level ranking to find the worst offenders.

**Tags.** Category: Aggregation + Join + Subquery | Difficulty: Intermediate | Role: VP of Concessions & Merchandising

**Approach.** Like Query 1, this needs a comparison of two views, but this time grouped by `theater_id`, so both tables need to retain the `theater_id` dimension. Use two subqueries (or CTEs) to aggregate `concession_sale` and `loyalty_redemption` separately by theater, then stitch them together with a `LEFT JOIN` — a `LEFT JOIN` rather than an `INNER JOIN` is required here because, in principle, a theater could have zero redemptions this quarter (though every theater in this dataset happens to have some, writing `LEFT JOIN` is the safer habit, paired with `COALESCE` to handle NULLs). Finally, sort descending by `redemption_share` (how diluted that theater's margin is).

```sql
WITH theater_paid AS (
    SELECT theater_id, SUM(gross_revenue) AS cash_revenue, SUM(units_sold) AS paid_units
    FROM concession_sale
    GROUP BY theater_id
),
theater_redeemed AS (
    SELECT theater_id, SUM(item_full_price) AS phantom_revenue, COUNT(*) AS redeemed_units
    FROM loyalty_redemption
    GROUP BY theater_id
)
SELECT
    t.theater_name,
    t.market_tier,
    tp.cash_revenue,
    COALESCE(tr.phantom_revenue, 0) AS phantom_revenue,
    tp.paid_units,
    COALESCE(tr.redeemed_units, 0) AS redeemed_units,
    ROUND(
        100.0 * COALESCE(tr.redeemed_units, 0) / (tp.paid_units + COALESCE(tr.redeemed_units, 0)), 2
    ) AS redemption_share_pct
FROM theater_paid tp
JOIN theater t ON t.id = tp.theater_id
LEFT JOIN theater_redeemed tr ON tr.theater_id = tp.theater_id
ORDER BY redemption_share_pct DESC
LIMIT 6;
```

**Expected Result & Business Takeaway.** The result returns the 6 most diluted theaters out of the 18. It's not random noise — there's a clean break: the top 6 (most diluted) theaters are **all Secondary-market theaters**, with `redemption_share_pct` landing in the **9%-11%** range, while all 12 Primary-market theaters land in the **4%-6%** range, with no overlap between the two groups. The reason isn't hard to see: members are assigned a "home theater" at sign-up, and that assignment weighting (and hence ordinary member spend) is set based on the theater's screen count — but a Secondary-market theater's natural foot traffic (the denominator, paid concession units) is much lower than a Primary theater with the same screen count. The numerator (redemptions) falls more slowly than the denominator (paid units), which naturally inflates the dilution ratio. The VP of Concessions & Merchandising should focus first on tightening redemption rules at these 6 Secondary theaters (for example, lowering the monthly per-member redemption cap or raising the points threshold at those locations), rather than applying a blanket policy company-wide.

---

## Query 3: Does Tiered Redemption Frequency Match the "Gold ≈ 3.6x Standard" Hypothesis

**Business Context.** Every quarter, the Director of Loyalty & Marketing has to demonstrate to the CMO the return on investment of the tiered membership program (Standard/Silver/Gold). Her hypothesis is that Gold members (highest spend threshold, most perks) redeem far more often than Standard members, which would justify continuing to invest in perks that drive tier upgrades. This query tests that hypothesis against real data, and to what degree it holds.

**Tags.** Category: Aggregation + Join | Difficulty: Basic | Role: Director of Loyalty & Marketing

**Approach.** All that's needed is a single `LEFT JOIN` between `loyalty_member` and `loyalty_redemption` (a LEFT JOIN preserves members with zero redemptions this quarter, though there are very few of those in this dataset), grouped by `tier` to count members and total redemptions, then dividing redemptions by members to get average redemption frequency per member. This is a simple `GROUP BY` aggregation — no window functions or subqueries needed.

```sql
SELECT
    lm.tier,
    COUNT(DISTINCT lm.id) AS n_members,
    COUNT(lr.id) AS n_redemptions,
    ROUND(1.0 * COUNT(lr.id) / COUNT(DISTINCT lm.id), 2) AS avg_redemptions_per_member,
    ROUND(SUM(lr.item_full_price), 0) AS total_phantom_value
FROM loyalty_member lm
LEFT JOIN loyalty_redemption lr ON lr.member_id = lm.id
GROUP BY lm.tier
ORDER BY avg_redemptions_per_member DESC;
```

**Expected Result & Business Takeaway.** Three rows: `Gold` has about 767 members averaging **9.1 redemptions**; `Silver` has about 2,191 members averaging **4.6**; `Standard` has about 4,542 members averaging **2.5**. Gold members redeem roughly **3.6 times** as often as Standard members — the hypothesis holds, and the magnitude matches expectations. The Director can take this straight into the CMO readout to support continued investment in the "spend-to-auto-upgrade-to-Gold" marketing push — but should also flag for the CFO that the more Gold members redeem, the worse the cash margin dilution problem from Query 1 gets, which is a tradeoff that needs to be balanced between member-perk design and margin protection.

---

## Query 4: Per-Screen Quarterly Net Contribution Ranking for Each IMAX Screen

**Business Context.** Every year, the Facilities & Engineering Manager submits next year's screen equipment capex plan to the CFO, including whether to renew or upgrade the IMAX licensing agreements at each theater. These renewal fees aren't cheap, and if a renewing screen is consistently losing money, that budget would be better redirected to a stronger-performing theater. She needs a net contribution ranking broken out by individual screen (not theater, not the program overall), so each IMAX screen can be evaluated on its own.

**Tags.** Category: CTE + Window Function + Join | Difficulty: Advanced | Role: Facilities & Engineering Manager

**Approach.** This is the most demanding modeling exercise in the whole document. The core concept is "screen contribution" = the premium ticket revenue a screen collects above what a Standard screen would charge, minus that screen's energy and maintenance fixed costs. Step one is a CTE that computes each theater's average Standard-screen ticket price (`standard_baseline`) as the comparison benchmark — this must be grouped by `theater_id`, since Standard pricing can differ slightly across theaters depending on the weekend showtime mix, so a single company-wide benchmark won't do. Step two sums, at the screen level, `paid_attendance × (ticket_price − that theater's Standard average price)` across every `showtime`, giving premium revenue. Step three aggregates the full-quarter fixed cost per screen from `screen_monthly_cost`. Finally, `RANK() OVER (ORDER BY net contribution ASC)` ranks all the IMAX screens with the worst performers first, so the losses are immediately visible.

```sql
WITH standard_baseline AS (
    SELECT
        t.id AS theater_id,
        AVG(s.ticket_price) AS std_avg_price
    FROM showtime s
    JOIN screen sc ON sc.id = s.screen_id
    JOIN theater t ON t.id = sc.theater_id
    WHERE sc.screen_type = 'Standard'
    GROUP BY t.id
),
screen_premium_revenue AS (
    SELECT
        sc.id AS screen_id,
        sc.theater_id,
        t.market_tier,
        SUM(s.paid_attendance * (s.ticket_price - sb.std_avg_price)) AS premium_ticket_revenue
    FROM showtime s
    JOIN screen sc ON sc.id = s.screen_id
    JOIN theater t ON t.id = sc.theater_id
    JOIN standard_baseline sb ON sb.theater_id = sc.theater_id
    WHERE sc.screen_type = 'IMAX'
    GROUP BY sc.id, sc.theater_id, t.market_tier
),
screen_fixed_cost AS (
    SELECT screen_id, SUM(total_cost) AS fixed_cost
    FROM screen_monthly_cost
    GROUP BY screen_id
)
SELECT
    t.theater_name,
    spr.market_tier,
    ROUND(spr.premium_ticket_revenue, 0) AS premium_ticket_revenue,
    ROUND(sfc.fixed_cost, 0) AS fixed_cost,
    ROUND(spr.premium_ticket_revenue - sfc.fixed_cost, 0) AS net_contribution,
    RANK() OVER (ORDER BY spr.premium_ticket_revenue - sfc.fixed_cost ASC) AS worst_to_best_rank
FROM screen_premium_revenue spr
JOIN screen_fixed_cost sfc ON sfc.screen_id = spr.screen_id
JOIN theater t ON t.id = spr.theater_id
ORDER BY worst_to_best_rank;
```

**Expected Result & Business Takeaway.** The query returns all 10 IMAX screens, ranked worst to best by net contribution. The bottom three (worst) screens are all in **Secondary** markets, with `net_contribution` around **-$12,900 to -$13,300**; starting from the fourth-ranked screen, every one is a **Primary** screen, and net contribution jumps to **+$47,000 or better** — a sharp break with no gray zone. The conclusion is clear: it isn't "IMAX as a format" that's losing money, it's the IMAX screens at 3 specific Secondary-market theaters. The Facilities & Engineering Manager should flag those 3 contracts as "do not renew, or renegotiate an attendance guarantee floor," rather than questioning the IMAX upgrade program as a whole.

---

## Query 5: Average Net Contribution Comparison for Premium vs. IMAX Screens by Market Tier

**Business Context.** After finishing Query 4, you (the BI Analyst) want to zoom out and look at a broader comparison: does the Premium format (large-format recliner auditoriums) show the same "Secondary market doesn't pencil out" problem as IMAX? Or is that issue unique to IMAX? This will help the company decide whether market-tier constraints should apply the next time it expands recliner seating.

**Tags.** Category: Aggregation + Join | Difficulty: Intermediate | Role: BI Analyst

**Approach.** This is a simplified generalization of the Query 4 logic: it still needs the Standard baseline price, premium revenue, and fixed cost, but this time there's no need for window-function ranking — just group by the two dimensions `(screen_type, market_tier)` and average the net contribution. Note that `screen_type` needs to include both `'Premium'` and `'IMAX'` (`Standard` itself doesn't need to be computed, since it is the baseline and its premium is always 0).

```sql
WITH standard_baseline AS (
    SELECT t.id AS theater_id, AVG(s.ticket_price) AS std_avg_price
    FROM showtime s
    JOIN screen sc ON sc.id = s.screen_id
    JOIN theater t ON t.id = sc.theater_id
    WHERE sc.screen_type = 'Standard'
    GROUP BY t.id
),
screen_premium_revenue AS (
    SELECT
        sc.id AS screen_id,
        sc.screen_type,
        t.market_tier,
        SUM(s.paid_attendance * (s.ticket_price - sb.std_avg_price)) AS premium_ticket_revenue
    FROM showtime s
    JOIN screen sc ON sc.id = s.screen_id
    JOIN theater t ON t.id = sc.theater_id
    JOIN standard_baseline sb ON sb.theater_id = sc.theater_id
    WHERE sc.screen_type IN ('Premium', 'IMAX')
    GROUP BY sc.id, sc.screen_type, t.market_tier
),
screen_fixed_cost AS (
    SELECT screen_id, SUM(total_cost) AS fixed_cost
    FROM screen_monthly_cost
    GROUP BY screen_id
)
SELECT
    spr.screen_type,
    spr.market_tier,
    COUNT(*) AS n_screens,
    ROUND(AVG(spr.premium_ticket_revenue), 0) AS avg_premium_revenue,
    ROUND(AVG(sfc.fixed_cost), 0) AS avg_fixed_cost,
    ROUND(AVG(spr.premium_ticket_revenue - sfc.fixed_cost), 0) AS avg_net_contribution
FROM screen_premium_revenue spr
JOIN screen_fixed_cost sfc ON sfc.screen_id = spr.screen_id
GROUP BY spr.screen_type, spr.market_tier
ORDER BY spr.screen_type, spr.market_tier;
```

**Expected Result & Business Takeaway.** Three rows result (Premium only shows up under Primary, since no Secondary theater in this dataset has a Premium screen): `IMAX / Primary` averages roughly **+$53,500** in net contribution, `IMAX / Secondary` about **-$13,100**, and `Premium / Primary` about **+$44,000**. Because every Premium screen sits in a Primary market, this data alone can't directly confirm whether Premium would also lose money in a Secondary market — but it's a clear signal to the expansion team: **before approving any new Premium or IMAX screen at a Secondary theater, run the Query 4 methodology to forecast attendance first, rather than assuming "premium format = premium return."**

---

## Query 6: Monthly Fixed-Cost Trend by Screen Type

**Business Context.** The Facilities & Engineering Manager needs to report to the finance team on whether fixed costs for each screen type were stable across Q2's three months (April, May, June) or whether there was an unusual spike (for example, an equipment breakdown that drove up maintenance spend in a given month). This is routine monthly reconciliation material.

**Tags.** Category: Aggregation + Date Analysis | Difficulty: Basic | Role: Facilities & Engineering Manager

**Approach.** This only needs a single `JOIN` between `screen` and `screen_monthly_cost`, grouped by the two dimensions `screen_type` and `cost_month`. `cost_month` is already stored as the first day of the month (e.g. `2026-04-01`), so no extra date function is needed — group directly. This is one of the few examples in this dataset where the date dimension is already a ready-made grouping key.

```sql
SELECT
    sc.screen_type,
    smc.cost_month,
    COUNT(*) AS n_screens,
    ROUND(SUM(smc.energy_cost), 0) AS total_energy_cost,
    ROUND(SUM(smc.maintenance_cost), 0) AS total_maintenance_cost,
    ROUND(SUM(smc.total_cost), 0) AS total_cost
FROM screen_monthly_cost smc
JOIN screen sc ON sc.id = smc.screen_id
GROUP BY sc.screen_type, smc.cost_month
ORDER BY sc.screen_type, smc.cost_month;
```

**Expected Result & Business Takeaway.** 9 rows result (3 screen types x 3 months). `IMAX` fixed costs fluctuate between roughly **$104,000 and $107,000** per month (10 screens), `Premium` sits around **$44,000** (17 screens), and `Standard` sits around **$97,000** (65 screens). The month-to-month swing stays within ±5% for all three types, with no unusual spikes, meaning there was no major unplanned repair this quarter — this material can be handed to finance as-is for routine reconciliation, with no additional commentary needed.

---

## Query 7: Weekend vs. Weekday Ticket Price and Occupancy Comparison

**Business Context.** The VP of Film Programming wants to confirm whether the current Friday/Saturday 15% price surcharge is scaring moviegoers away — if occupancy actually drops on the pricier weekend showtimes, that would suggest the premium is set too high and should be dialed back.

**Tags.** Category: Aggregation + CTE | Difficulty: Intermediate | Role: VP of Film Programming

**Approach.** The key challenge is determining "is this Friday or Saturday" from `showtime_datetime`. SQLite's `strftime('%w', ...)` returns a day-of-week number from 0 (Sunday) to 6 (Saturday), so Friday is `5` and Saturday is `6`. A `CASE WHEN` tags every showtime as `Weekend` or `Weekday`, and then that tag is used to group and average ticket price and paid attendance. A CTE isn't strictly required here, but wrapping the "tagging" step in its own layer (subquery or CTE) makes the query more readable.

```sql
WITH labeled_showtimes AS (
    SELECT
        *,
        CASE
            WHEN CAST(strftime('%w', showtime_datetime) AS INTEGER) IN (5, 6) THEN 'Weekend (Fri/Sat)'
            ELSE 'Weekday'
        END AS day_group
    FROM showtime
)
SELECT
    day_group,
    COUNT(*) AS n_showtimes,
    ROUND(AVG(ticket_price), 2) AS avg_ticket_price,
    ROUND(AVG(paid_attendance), 1) AS avg_paid_attendance
FROM labeled_showtimes
GROUP BY day_group;
```

**Expected Result & Business Takeaway.** Two rows: `Weekday` averages a ticket price of about **$13.39** and average paid attendance of about **30.4**; `Weekend (Fri/Sat)` averages a ticket price of about **$15.39** (about 15% higher, consistent with the pricing rule) and average paid attendance of about **37.5** (up, not down — roughly 23% higher). The conclusion is that the weekend surcharge isn't scaring anyone away — if anything, weekend foot traffic is naturally higher to begin with. **The current pricing strategy is working, and the VP might even explore whether there's room to push the weekend surcharge higher still**, rather than the price cut originally feared.

---

## Query 8: List of Late-Night "Minimum Guarantee" Showtimes Suspected of Buyback Padding

**Business Context.** Last week the Regional Operations Manager received an anonymous tip from a frontline employee claiming that "for some late-night showings, the manager just buys up a stack of tickets with their own card." She needs a concrete list of showtimes to verify the claim rather than acting on rumor — if the list exists and shows a clear pattern, she'll bring the evidence to the VP of Film Programming to discuss next steps.

**Tags.** Category: Join + Filter | Difficulty: Basic | Role: Regional Operations Manager

**Approach.** No aggregation is needed here — just join `showtime` and `film_booking` and filter down to showtimes where `daypart = 'late_night'`, `has_minimum_guarantee = 1`, and `paid_attendance` is meaningfully below `minimum_attendance_per_showtime`. Showtimes where natural attendance falls short but the guarantee is still hit are the ones most likely to be padded. Use `paid_attendance < minimum_attendance_per_showtime * 0.6` as the screening threshold (natural attendance below 60% of the floor), and also display `comp_attendance` so the reader can see at a glance how many of the attendees were comps.

```sql
SELECT
    t.theater_name,
    ft.title,
    s.showtime_datetime,
    fb.minimum_attendance_per_showtime,
    s.paid_attendance,
    s.comp_attendance,
    ROUND(100.0 * s.comp_attendance / (s.paid_attendance + s.comp_attendance), 1) AS comp_share_pct
FROM showtime s
JOIN film_booking fb ON fb.id = s.film_booking_id
JOIN film_title ft ON ft.id = fb.film_id
JOIN screen sc ON sc.id = s.screen_id
JOIN theater t ON t.id = sc.theater_id
WHERE s.daypart = 'late_night'
    AND fb.has_minimum_guarantee = 1
    AND s.paid_attendance < fb.minimum_attendance_per_showtime * 0.6
ORDER BY comp_share_pct DESC
LIMIT 20;
```

**Expected Result & Business Takeaway.** The query returns a list of showtimes (this dataset has nearly 3,000 such showtimes; here we take only the top 20 by `comp_share_pct`). A typical row looks like this: `paid_attendance = 8`, `comp_attendance = 14`, `comp_share_pct ≈ 63.6%` — over 60% of the "attendees" were actually comped by the theater itself. This list confirms the employee's tip was accurate, and it's not an isolated incident but a pattern that shows up across theaters. The Regional Operations Manager can take this list straight to the VP of Film Programming to push for renegotiating minimum attendance clauses with distributors, or to adjust the late-night booking strategy for these films (for example, dropping the late-night showtime entirely and giving that screen time to better-performing slots).

---

## Query 9: Count of Suspected Padded Showtimes and Comp Attendance by Theater

**Business Context.** Having reviewed the Query 8 list, the Regional Operations Manager wants to know whether this problem is spread evenly across the 18 theaters or concentrated in a handful. That determines whether she needs to send a company-wide notice or have one-on-one conversations with a few managers.

**Tags.** Category: Aggregation + CTE | Difficulty: Intermediate | Role: Regional Operations Manager

**Approach.** This adds an aggregation layer on top of the Query 8 filter logic. First, a CTE filters down to showtimes meeting the "suspected padding" criteria (the same WHERE clause as Query 8), then the results are grouped by `theater_id` to count showtimes and total comp attendance. The CTE's job here is to separate the business rule for "what counts as padding" from the downstream aggregation logic — if the rule needs to change later (say, the threshold moves from 0.6 to 0.5), only the CTE needs updating, without touching the aggregation logic outside it.

```sql
WITH suspected_buyback AS (
    SELECT
        sc.theater_id,
        s.comp_attendance
    FROM showtime s
    JOIN film_booking fb ON fb.id = s.film_booking_id
    JOIN screen sc ON sc.id = s.screen_id
    WHERE s.daypart = 'late_night'
        AND fb.has_minimum_guarantee = 1
        AND s.paid_attendance < fb.minimum_attendance_per_showtime * 0.6
)
SELECT
    t.theater_name,
    t.market_tier,
    COUNT(*) AS n_suspected_showtimes,
    SUM(sb.comp_attendance) AS total_comp_attendance
FROM suspected_buyback sb
JOIN theater t ON t.id = sb.theater_id
GROUP BY t.theater_name, t.market_tier
ORDER BY n_suspected_showtimes DESC;
```

**Expected Result & Business Takeaway.** All 18 theaters show up in the result, each with some number of suspected padded showtimes (since this pattern is a systemic feature of how the booking contracts work, not a problem specific to individual theaters). The showtime count scales roughly with each theater's screen count and tentpole booking density, with no single theater standing out as a dramatic outlier. The conclusion: **this is a company-wide contract-execution issue, not poor management at a specific theater**. The Regional Operations Manager should send a company-wide policy notice rather than singling out individual managers for a talking-to — the real fix belongs upstream, in renegotiating terms with the distributors (see the Query 8 takeaway), not in operational-level enforcement.

---

## Query 10: Screen Utilization (Occupancy) Ranking to Identify De-installation Candidates

**Business Context.** The CFO is putting together the annual capex plan and wants to know which screens have persistently low utilization, worth considering for repurposing (for example, shrinking the auditorium to free up space for a private-screening rental business). You need to produce a company-wide screen utilization ranking.

**Tags.** Category: Window Function + Aggregation | Difficulty: Advanced | Role: BI Analyst

**Approach.** Occupancy rate = `paid_attendance / seat_capacity`, which is a showtime-level metric — it needs to be computed per showtime first, then aggregated to an average at the screen level. `RANK()` is used here instead of a plain `ORDER BY` because leadership doesn't just want a ranking, they want to know what percentile a given screen falls into across all 92 company-wide screens, which supports a uniform rule down the line (something like "bottom 10% by utilization gets flagged for conversion"), and `RANK()`'s output directly supports that kind of threshold judgment.

```sql
SELECT
    sc.id AS screen_id,
    sc.screen_type,
    t.market_tier,
    t.theater_name,
    ROUND(AVG(1.0 * s.paid_attendance / sc.seat_capacity) * 100, 1) AS avg_occupancy_pct,
    COUNT(*) AS n_showtimes,
    RANK() OVER (ORDER BY AVG(1.0 * s.paid_attendance / sc.seat_capacity) ASC) AS lowest_occupancy_rank
FROM showtime s
JOIN screen sc ON sc.id = s.screen_id
JOIN theater t ON t.id = sc.theater_id
GROUP BY sc.id, sc.screen_type, t.market_tier, t.theater_name
ORDER BY lowest_occupancy_rank
LIMIT 10;
```

**Expected Result & Business Takeaway.** The three lowest-ranked screens are all **Secondary-market IMAX screens** (average occupancy of just **3%-4%**), followed closely by a few Secondary-market Standard screens (around **12%**). This ranking closely mirrors the Query 4 net-contribution ranking, further confirming the Q2 trap — **the screens with the lowest utilization are exactly the same 3 IMAX screens with negative net contribution**. The CFO can use this to prioritize a capex review of those 3 screens specifically, rather than applying an across-the-board maintenance budget cut to every screen.

---

## Query 11: Overall Utilization Comparison, Primary vs. Secondary Markets

**Business Context.** Before finalizing the year's booking strategy, the VP of Film Programming wants to look at one macro number first: how big is the occupancy gap between Primary and Secondary markets overall, and does that gap justify a different showtime density for Secondary theaters (for example, cutting the number of showtimes rather than forcing 5 showtimes a day regardless of demand).

**Tags.** Category: Aggregation + Join | Difficulty: Basic | Role: VP of Film Programming

**Approach.** A more stripped-down version of Query 10 — no window function needed, just group by the single `market_tier` dimension and average occupancy. Two joins across three tables (`showtime`, `screen`, `theater`) are all that's required.

```sql
SELECT
    t.market_tier,
    ROUND(AVG(1.0 * s.paid_attendance / sc.seat_capacity) * 100, 1) AS avg_occupancy_pct,
    COUNT(*) AS n_showtimes,
    SUM(s.paid_attendance) AS total_paid_attendance
FROM showtime s
JOIN screen sc ON sc.id = s.screen_id
JOIN theater t ON t.id = sc.theater_id
GROUP BY t.market_tier;
```

**Expected Result & Business Takeaway.** Two rows result: `Primary` occupancy is meaningfully higher than `Secondary` (the gap is on the order of 10-15 percentage points). This isn't a surprising finding, but it gives the booking strategy a quantitative basis: the VP could consider modestly trimming showtime density at Secondary theaters (for example, cutting IMAX from 3 showtimes a day to 2) and reallocating that freed-up screen time to the more consistently well-attended Standard screens.

---

## Query 12: Monthly Box Office and Attendance Trend

**Business Context.** The CFO is preparing the "quarterly trend" page of the board deck and needs to see whether box office and attendance across April, May, and June rose, held steady, or declined month over month — and wants to tell that story using month-over-month change rates rather than raw absolute values.

**Tags.** Category: Date Analysis + Window Function | Difficulty: Advanced | Role: CFO

**Approach.** First, use `strftime('%Y-%m', ...)` to bucket showtimes into months and aggregate monthly box office and attendance. Then use the `LAG()` window function to pull in "last month's" figures and compute a month-over-month change rate in the same row — this is cleaner than writing a self join, and it's the reason this query calls for a window function rather than plain aggregation.

```sql
WITH monthly_summary AS (
    SELECT
        strftime('%Y-%m', showtime_datetime) AS year_month,
        SUM(ticket_revenue) AS total_ticket_revenue,
        SUM(paid_attendance) AS total_paid_attendance
    FROM showtime
    GROUP BY year_month
)
SELECT
    year_month,
    ROUND(total_ticket_revenue, 0) AS total_ticket_revenue,
    total_paid_attendance,
    ROUND(
        100.0 * (total_ticket_revenue - LAG(total_ticket_revenue) OVER (ORDER BY year_month))
        / LAG(total_ticket_revenue) OVER (ORDER BY year_month), 1
    ) AS revenue_mom_change_pct
FROM monthly_summary
ORDER BY year_month;
```

**Expected Result & Business Takeaway.** Three rows: April box office is about **$6.149 million**, May is about **$6.354 million** (up **+3.3%** month over month), and June is about **$5.348 million** (down **-15.8%** month over month). The visible June decline shouldn't trigger panic as a first reaction — it should be checked against the `film_booking` data. Was June simply light on new tentpole releases, making its slate weaker than April's and May's? The CFO should attribute the decline to booking-slate seasonality in the board deck, rather than framing it as "the business is deteriorating," while also flagging for the booking team whether Q3's slate strength is strong enough to pick things back up.

---

## Query 13: Concession Attach Rate Comparison by Daypart

**Business Context.** You're helping the Concession Operations Supervisor prepare next quarter's concession stocking plan, and need to determine whether matinee, prime, and late_night dayparts show a meaningfully different concession attach rate (how many concession units, on average, each paying attendee drives) — this affects counter staffing levels and stocking volume for each daypart.

**Tags.** Category: Aggregation + Join + CTE | Difficulty: Intermediate | Role: BI Analyst

**Approach.** This requires aggregating `showtime` (the source of attendance) and `concession_sale` (the source of concession units) separately by `daypart`, then dividing one aggregate by the other. There's no direct foreign key connecting these two tables (`concession_sale`'s grain is "theater x date x daypart x SKU," not showtime-level), so the correct approach is to build two independent CTEs, each aggregated by `daypart`, and then join them together using `daypart` as the join key — rather than joining the two detail tables directly, which would produce an incorrect Cartesian expansion.

```sql
WITH attendance_by_daypart AS (
    SELECT daypart, SUM(paid_attendance) AS total_attendance
    FROM showtime
    GROUP BY daypart
),
units_by_daypart AS (
    SELECT daypart, SUM(units_sold) AS total_units
    FROM concession_sale
    GROUP BY daypart
)
SELECT
    a.daypart,
    a.total_attendance,
    u.total_units,
    ROUND(1.0 * u.total_units / a.total_attendance, 3) AS attach_rate
FROM attendance_by_daypart a
JOIN units_by_daypart u ON u.daypart = a.daypart
ORDER BY attach_rate DESC;
```

**Expected Result & Business Takeaway.** Three rows result, and the attach rate is actually very close across all three dayparts, all sitting near **0.40** (meaning that on average each paying attendee drives about 0.4 concession units — plenty of attendees split a single item between friends, and some buy nothing at all, so the per-attendee figure comes in well under 1). No daypart stands out as meaningfully higher or lower. That "no difference" finding is itself useful: **concession stocking and staffing can simply be allocated in proportion to each daypart's attendance share, with no need to design separate attach-rate assumptions per daypart** — simpler than one might expect, and a reminder to the Concession Operations Supervisor not to over-engineer the scheduling rules.

---

## Query 14: Popcorn Family vs. Other Concession Categories: Sales Performance

**Business Context.** There's a saying that's circulated internally for years: "we sell popcorn, and the movie is just the excuse" (see Section 2 of the business context document). The Concession Operations Supervisor wants to test whether that line is an exaggeration — how big a share of the concession business does the popcorn family (the 4 SKUs whose `item_name` contains "Popcorn") actually account for.

**Tags.** Category: Aggregation + Text Matching | Difficulty: Basic | Role: Concession Operations Supervisor

**Approach.** Use `LIKE '%Popcorn%'` for text matching against `concession_item.item_name`, splitting the 24 SKUs into a "popcorn family" group and an "other" group, then aggregating units, revenue, and gross profit by that grouping. This is the only query in this document that uses `LIKE` pattern matching — because there's no dedicated `category` value that isolates the popcorn family directly (`category = 'Popcorn'` would achieve the same result here, but `LIKE` is used to demonstrate the pattern for when category naming isn't clean, or when you want to pull items whose name contains a certain keyword regardless of category).

```sql
SELECT
    CASE WHEN ci.item_name LIKE '%Popcorn%' THEN 'Popcorn family' ELSE 'Other' END AS product_group,
    SUM(cs.units_sold) AS total_units,
    ROUND(SUM(cs.gross_revenue), 0) AS total_revenue,
    ROUND(SUM(cs.gross_revenue - cs.cogs_amount), 0) AS total_gross_profit
FROM concession_sale cs
JOIN concession_item ci ON ci.id = cs.item_id
GROUP BY product_group;
```

**Expected Result & Business Takeaway.** Two rows result: the `Popcorn family` (just 4 SKUs) contributes about **161,000 units**, about **$1.424 million** in revenue, and about **$990,000** in gross profit; `Other` (the remaining 20 SKUs) contributes about **337,500 units**, about **$1.990 million** in revenue, and about **$1.488 million** in gross profit. The popcorn family is only 4 of the 24 SKUs (about 17% of the catalog) but delivers roughly **32%-40%** of both units and gross profit — the concentration really is high, but the "movie is just the excuse for popcorn" line is a bit of an exaggeration (popcorn doesn't quite account for half of gross profit). The Concession Operations Supervisor can use this to confirm popcorn deserves top restocking priority, but the stocking budget shouldn't be entirely weighted toward popcorn — beverages and combo packages matter too.

---

## Query 15: Top 10 Best-Selling Concession SKUs (by Gross Profit)

**Business Context.** The Concession Operations Supervisor needs a SKU-level bestseller list to use in next quarter's purchasing negotiations with suppliers — the highest-volume SKUs are the ones with the leverage to negotiate a better wholesale price.

**Tags.** Category: Window Function + Aggregation | Difficulty: Intermediate | Role: BI Analyst

**Approach.** Aggregate units and gross profit by `item_id`, then use `RANK()` to sort descending by gross profit and take the top 10. Ranking by "gross profit" rather than "units sold" is deliberate — the item that actually deserves negotiating priority is the one contributing the most to the company's bottom line, not simply the one that sells the most units. Those aren't necessarily the same SKUs (a low-price, high-volume item can sell a lot of units without necessarily contributing the most gross profit).

```sql
SELECT
    ci.item_name,
    ci.category,
    SUM(cs.units_sold) AS total_units,
    ROUND(SUM(cs.gross_revenue - cs.cogs_amount), 0) AS total_gross_profit,
    RANK() OVER (ORDER BY SUM(cs.gross_revenue - cs.cogs_amount) DESC) AS gross_profit_rank
FROM concession_sale cs
JOIN concession_item ci ON ci.id = cs.item_id
GROUP BY ci.item_name, ci.category
ORDER BY gross_profit_rank
LIMIT 10;
```

**Expected Result & Business Takeaway.** The top 10 SKUs by gross profit are returned, and the top 6 spots are taken by `Large Popcorn`, `Large Fountain Drink`, `Caramel Popcorn`, `Medium Popcorn`, `Medium Fountain Drink`, and `ICEE Frozen Drink` — because unit volume is so high on large and medium popcorn and drinks, their total gross profit ends up beating out the higher-priced but much lower-volume combo packages (the `Popcorn + Drink Combo` line lands at #7 and #9). This is a useful correction to an intuition that can easily lead people astray: **the highest-priced item on the menu is not necessarily the item that contributes the most gross profit — the high-volume basics, popcorn and fountain drinks, are the real cash cows**. Supplier negotiations should focus first on the purchase price of these core SKUs, rather than spending negotiating energy on combo packages.

---

## Query 16: Quarterly Box Office and Concession Revenue Summary by Theater (Board Materials)

**Business Context.** The Concession Operations Supervisor needs to prepare the most basic "all-theaters at a glance" table for the board deck, listing each theater's box office, concession revenue, and attendance for the quarter, to serve as the background reference table underlying every other deeper analysis.

**Tags.** Category: Aggregation + Join + Date Analysis | Difficulty: Intermediate | Role: Concession Operations Supervisor

**Approach.** This requires aggregating box office (from `showtime`, joined through `screen` to `theater`) and concession revenue (`concession_sale` already carries `theater_id` directly) separately, then stitching them together by theater. It's a three-way data-source rollup: the showtime table, the concession table, and the theater dimension table. Use two CTEs to aggregate each side independently, then join each to the `theater` master table — avoiding a multi-to-multi relationship in a single join chain that would double-count data.

```sql
WITH theater_ticket AS (
    SELECT t.id AS theater_id, SUM(s.ticket_revenue) AS ticket_revenue, SUM(s.paid_attendance) AS paid_attendance
    FROM showtime s
    JOIN screen sc ON sc.id = s.screen_id
    JOIN theater t ON t.id = sc.theater_id
    GROUP BY t.id
),
theater_concession AS (
    SELECT theater_id, SUM(gross_revenue) AS concession_revenue
    FROM concession_sale
    GROUP BY theater_id
)
SELECT
    t.theater_name,
    t.market_tier,
    ROUND(tt.ticket_revenue, 0) AS ticket_revenue,
    tt.paid_attendance,
    ROUND(tc.concession_revenue, 0) AS concession_revenue,
    ROUND(tt.ticket_revenue + tc.concession_revenue, 0) AS total_revenue
FROM theater_ticket tt
JOIN theater t ON t.id = tt.theater_id
JOIN theater_concession tc ON tc.theater_id = tt.theater_id
ORDER BY total_revenue DESC;
```

**Expected Result & Business Takeaway.** All 18 theaters are returned, sorted descending by total revenue. Primary-market theaters (especially the Chicago and Milwaukee locations) sit comfortably near the top, while Secondary-market theaters generally cluster near the bottom. This table doesn't drive a conclusion on its own — it's meant as background material for the board deck. Query 20 (blended contribution ranking) builds on this revenue table by further netting out fixed costs, to produce a ranking that's closer to "true" profitability.

---

## Query 17: Per-Attendee Concession Spend by Daypart

**Business Context.** The Concession Operations Supervisor wants to know whether matinee, prime, and late_night dayparts differ in average concession dollars spent per attendee — if one daypart shows meaningfully higher per-attendee spend, it's worth adding counter staff and prioritizing higher-margin stock during that window.

**Tags.** Category: Aggregation + Date Analysis | Difficulty: Intermediate | Role: Concession Operations Supervisor

**Approach.** Structurally similar to Query 13 (two independent CTEs aggregated by `daypart`, then joined), but this time computing "spend per attendee" (total revenue / total attendance) instead of "units per attendee." This query is kept separate because spend and unit count are two distinct things the operations team cares about — units drive stocking quantity, dollars drive profit contribution, and the two don't always move together (a daypart could have fewer units but a higher share of pricier combo purchases).

```sql
WITH attendance_by_daypart AS (
    SELECT daypart, SUM(paid_attendance) AS total_attendance
    FROM showtime
    GROUP BY daypart
),
revenue_by_daypart AS (
    SELECT daypart, SUM(gross_revenue) AS total_revenue
    FROM concession_sale
    GROUP BY daypart
)
SELECT
    a.daypart,
    a.total_attendance,
    ROUND(r.total_revenue, 0) AS total_concession_revenue,
    ROUND(r.total_revenue / a.total_attendance, 2) AS revenue_per_attendee
FROM attendance_by_daypart a
JOIN revenue_by_daypart r ON r.daypart = a.daypart
ORDER BY revenue_per_attendee DESC;
```

**Expected Result & Business Takeaway.** Three rows result, and `revenue_per_attendee` varies only slightly across the three dayparts (consistent with the attach-rate finding from Query 13, since the unit and dollar distributions are highly correlated). The takeaway is the same: **there's no need to design a differentiated concession strategy by daypart — the current practice of allocating staffing and stock in proportion to attendance is already good enough**. The Concession Operations Supervisor can put more energy toward the category and SKU optimizations surfaced in Query 14/15, rather than daypart-level optimization.

---

## Query 18: Film Booking Coverage by Distributor

**Business Context.** Every quarter, the VP of Film Programming evaluates the depth of the relationship with each major distributor to decide next quarter's negotiating priorities — the distributor with the most theater coverage and the largest number of booking contracts is usually the one worth investing the most relationship-management effort in (for example, reserving prime release slots for their upcoming titles).

**Tags.** Category: Aggregation + Join | Difficulty: Basic | Role: VP of Film Programming

**Approach.** Join `film_title` and `film_booking` on the distributor name, then group and aggregate to count films, total booking contracts, and the number of distinct theaters covered per distributor (using `COUNT(DISTINCT theater_id)`, since the same distributor's multiple films may cover the same theater more than once, and without de-duplication that would be double-counted).

```sql
SELECT
    ft.distributor_name,
    COUNT(DISTINCT ft.id) AS n_films,
    COUNT(fb.id) AS n_bookings,
    COUNT(DISTINCT fb.theater_id) AS n_theaters_covered
FROM film_title ft
JOIN film_booking fb ON fb.film_id = ft.id
GROUP BY ft.distributor_name
ORDER BY n_bookings DESC;
```

**Expected Result & Business Takeaway.** Six rows result (one for each of the 6 fictional distributors). `Northgate Media` and `Redline Entertainment` have the most booking contracts (both over 100); `Prairie Peak Studios` and `Brightwell Films` have noticeably fewer bookings (around 30-40), indicating a meaningfully smaller relationship at present — fewer films, and a higher share of non-tentpole titles. (Note: all six distributors cover all 18 theaters, because every distributor has at least one tentpole title, and tentpoles are booked chain-wide — so `n_theaters_covered` doesn't differentiate much here; the real separation is in `n_films` and `n_bookings`.) The VP of Film Programming can use this to push for better revenue-share terms with the top two distributors next quarter (given the volume of business, there's real negotiating leverage), while also evaluating whether to expand the relationship with Prairie Peak and Brightwell, or bring in a new distributor, to diversify away from over-reliance on the top two.

---

## Query 19: Cross-Theater Loyalty Redemption Share

**Business Context.** The Director of Loyalty & Marketing wants to know whether members really do redeem points "cross-theater" (for example, catching a movie at a theater near a business trip and redeeming points earned at their home theater) — this matters for whether Lakeshore Rewards should add a "nearby theaters" prompt to the loyalty card/app to boost cross-location conversion.

**Tags.** Category: Aggregation + Join | Difficulty: Basic | Role: BI Analyst

**Approach.** Compare `loyalty_redemption.theater_id` against `loyalty_member.home_theater_id` and compute the share where the two don't match. The key thing to understand here is why a `JOIN` is needed rather than answering the question directly from `loyalty_redemption` alone — "home theater" lives in the `loyalty_member` table, not in `loyalty_redemption`, so the two tables must be joined before the comparison can be made.

```sql
SELECT
    ROUND(
        100.0 * SUM(CASE WHEN lr.theater_id != lm.home_theater_id THEN 1 ELSE 0 END) / COUNT(*), 2
    ) AS cross_theater_redemption_pct,
    COUNT(*) AS total_redemptions
FROM loyalty_redemption lr
JOIN loyalty_member lm ON lm.id = lr.member_id;
```

**Expected Result & Business Takeaway.** A single row: `cross_theater_redemption_pct` is about **14.6%** — fewer than one in six redemptions happen at a theater other than the member's home theater; most redemptions still happen at the theater a member visits regularly. That share isn't dramatically high, but it isn't negligible either. The Director of Loyalty & Marketing can conclude that the upside from a "nearby theaters" prompt feature is real but limited — worth pursuing as a medium-priority app feature update, not the quarter's top priority project.

---

## Query 20: Theater Blended Contribution Ranking (Box Office + Concession Gross Profit − Fixed Cost)

**Business Context.** The board has asked the CFO to submit a theater-level blended profitability ranking next quarter, to inform decisions about opening new theaters, closing existing ones, or reallocating resources. This is the highest-level rollup of the quarter, pulling together the revenue and cost lines broken apart in every earlier query back to the theater level of management granularity.

**Tags.** Category: CTE + Window Function + Multi-table Join | Difficulty: Advanced | Role: CFO

**Approach.** This query touches the most data sources of anything in the document, combining three independent revenue/cost streams: `showtime` (box office), `concession_sale` (concession gross profit — note this needs revenue minus cost, not just revenue), and `screen_monthly_cost` (fixed cost, which needs to be joined from `screen_id` to `theater_id` before aggregating). Three CTEs independently aggregate each stream to the theater level, then three `JOIN`s stitch them together, and a final "blended contribution" metric is computed and ranked with `RANK()`. **There's a deliberate pitfall worth calling out here: joining `showtime` and `concession_sale` directly and then aggregating would create a Cartesian-product blowup, because the two tables have different grains (one is showtime-level, the other is theater/date/daypart/SKU-level) — box office totals would come out inflated by several multiples. The correct approach is exactly what's shown below: aggregate each source independently into three CTEs, each with `theater_id` as its sole grain, and then join them 1:1.**

```sql
WITH ticket_rev AS (
    SELECT t.id AS theater_id, SUM(s.ticket_revenue) AS ticket_revenue
    FROM showtime s
    JOIN screen sc ON sc.id = s.screen_id
    JOIN theater t ON t.id = sc.theater_id
    GROUP BY t.id
),
concession_profit AS (
    SELECT theater_id, SUM(gross_revenue - cogs_amount) AS concession_gross_profit
    FROM concession_sale
    GROUP BY theater_id
),
fixed_cost AS (
    SELECT sc.theater_id, SUM(smc.total_cost) AS total_fixed_cost
    FROM screen sc
    JOIN screen_monthly_cost smc ON smc.screen_id = sc.id
    GROUP BY sc.theater_id
)
SELECT
    t.theater_name,
    t.market_tier,
    ROUND(tr.ticket_revenue, 0) AS ticket_revenue,
    ROUND(cp.concession_gross_profit, 0) AS concession_gross_profit,
    ROUND(fc.total_fixed_cost, 0) AS screen_fixed_cost,
    ROUND(tr.ticket_revenue + cp.concession_gross_profit - fc.total_fixed_cost, 0) AS blended_contribution,
    RANK() OVER (ORDER BY tr.ticket_revenue + cp.concession_gross_profit - fc.total_fixed_cost DESC) AS contribution_rank
FROM ticket_rev tr
JOIN theater t ON t.id = tr.theater_id
JOIN concession_profit cp ON cp.theater_id = tr.theater_id
JOIN fixed_cost fc ON fc.theater_id = tr.theater_id
ORDER BY contribution_rank;
```

**Expected Result & Business Takeaway.** All 18 theaters are returned, ranked. The Chicago Lincoln Square theater (the company's flagship) ranks first, with blended contribution of about **$1.96 million**; the theaters at the bottom of the ranking are all Secondary-market locations, with blended contribution in the **$370,000-$520,000** range. **The critical caveat: this theater-level ranking completely hides the "3 chronically loss-making IMAX screens" problem surfaced in Query 4** — because those theaters' overall box office scale is large enough that a small screen-level loss disappears entirely once folded into the whole theater's numbers. In the board deck, the CFO should present both this theater-level ranking (which answers "should we close a particular theater") and the Query 4 screen-level ranking (which answers "should we renew the contract on a particular screen") — they serve different decisions at different levels of granularity, and neither one can substitute for the other.

---

## Business Question Cross-Reference

| Business Question | Corresponding Queries |
|----------|----------|
| Q1 True cash concession margin | Query 1, Query 2, Query 3 |
| Q2 Premium-screen per-screen profit and loss | Query 4, Query 5, Query 6, Query 10 |
| Q3 Late-night "minimum guarantee" tickets eroding true occupancy | Query 8, Query 9 |
| Q4 Screen and theater utilization | Query 10, Query 11, Query 20 |
| Q5 Daypart and concession matching | Query 13, Query 14, Query 15, Query 17 |
| Operational (not tied to a specific marquee question) | Query 7, Query 12, Query 16, Query 18, Query 19 |
</content>