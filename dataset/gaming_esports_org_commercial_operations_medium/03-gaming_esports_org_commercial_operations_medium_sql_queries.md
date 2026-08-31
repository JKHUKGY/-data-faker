# Vanguard Esports Commercial Operations Health Review: SQL Query Documentation

This document covers the 20 SQL analysis questions for the
`gaming_esports_org_commercial_operations_medium` dataset. For the business
context, org structure, and the four core business questions, see
`01-gaming_esports_org_commercial_operations_medium_business_context.md`.
For table structure and field definitions, see
`02-gaming_esports_org_commercial_operations_medium_er_document.md`.

**REFERENCE_DATE convention**: this dataset is anchored to `2026-06-30` as
its analysis reference date. Everywhere a query needs "today," it uses the
literal date `'2026-06-30'` instead of `DATE('now')`, so the queries produce
the same results no matter when they're run.

## How to Use This Document

You're the newly hired Commercial Operations Analyst at Vanguard Esports,
and the COO has split the next three weeks of review work into these 20
questions, delivered in batches. Each question has five parts:

1. **Business Context**: who's asking, why they're asking, and what
   decision the answer will feed into.
2. **Tags**: three short labels — category, difficulty, and the asking role.
3. **Approach**: before you look at the SQL, a walkthrough of which tables
   to join, what grain to aggregate at, and the common pitfalls.
4. **SQL Code**: a query you can run directly against the SQLite database
   produced by this dataset's generator.
5. **Expected Result & Business Conclusion**: what the result looks like,
   what the numbers mean for the business, and what the analyst should do
   next after seeing it.

Every question traces back to one of the four business questions from the
business context file (Q1 sponsor exposure billing gap, Q2 salary-versus-
performance disconnect, Q3 merch gross margin tied to win rate, Q4 prize
distribution payment compliance), plus a handful of operational queries for
grounding. The SQL here is meant to be learned from, not just run — read
the "Approach" section first, work through the join logic in your head, and
only then check it against the code.

## Query Index

| # | Title | Business Role | SQL Category | Difficulty |
|------|------|----------|----------|------|
| 1 | Sponsor deal exposure delivery rate ranking | Head of Partnerships | Aggregation + Join | Basic |
| 2 | Annual sponsorship revenue at risk from exposure-gap deals | CFO | Aggregation + CASE | Intermediate |
| 3 | Exposure delivery rate split by sponsorship scope | Head of Partnerships | Join + Group By | Intermediate |
| 4 | Player trailing 6-month performance vs. historical peak | GM of Esports | CTE + Aggregation | Advanced |
| 5 | Salary-versus-recent-performance mismatch ranking | GM of Esports | CTE + Window Function | Advanced |
| 6 | Legacy star vs. rest-of-roster salary/performance correlation comparison | GM of Esports | Aggregation + Window Function (NTILE) | Intermediate |
| 7 | Remaining contract months for declining players | GM of Esports | Date arithmetic | Basic |
| 8 | Team trailing 60-day win rate vs. concurrent merch gross margin | Commercial Operations Analyst | Correlated Subquery + CTE | Advanced |
| 9 | Merch revenue/margin comparison: slump vs. hot form | Commercial Operations Analyst | CASE + Aggregation | Intermediate |
| 10 | Distribution of discount depth during slumps | Commercial Operations Analyst | Aggregation | Basic |
| 11 | Late/underpaid prize distribution records by team | GM of Esports | Aggregation + Join | Intermediate |
| 12 | Ranking of prize distribution payment delay days | Player Payments Coordinator | Window Function (RANK) | Intermediate |
| 13 | Total shortfall amount summary | CFO | Aggregation | Basic |
| 14 | Distribution of days from organizer payout to club receipt | Player Payments Coordinator | Date arithmetic + Aggregation | Basic |
| 15 | Tournament placement distribution by team | GM of Esports | Aggregation | Basic |
| 16 | Top 10 broadcast sessions by peak viewership | Head of Content | Order By + Join | Basic |
| 17 | MVP count leaderboard vs. salary | GM of Esports | Aggregation + Window Function | Intermediate |
| 18 | Merch category revenue/margin contribution share | Commercial Operations Analyst | Aggregation | Basic |
| 19 | Sponsorship value split by contract naming keyword (Global vs. team-scoped) | Head of Partnerships | Pattern Matching (LIKE) | Basic |
| 20 | Board summary scorecard: all four questions on one page | COO | CTE combining multiple subqueries | Advanced |

---

## Query 1: Sponsor Deal Exposure Delivery Rate Ranking

### Business Context

Every quarter, the Head of Partnerships needs to prepare for renewal
negotiations with brand partners, but the club has never systematically
compared "exposure hours committed in the contract" against "exposure hours
actually measured by the content team." This review makes that comparison
the top priority: if a deal is delivering meaningfully below what was
promised, the club needs to either make up the exposure or renegotiate
pricing at renewal time — otherwise it becomes a PR crisis the moment the
sponsor notices on their own. This question maps to business question Q1.

### Tags

Category: Aggregation + Join · Difficulty: Basic · Role: Head of Partnerships

### Approach

You need the `sponsorship_deal` and `sponsor_exposure_log` tables, grouped
by `sponsorship_deal_id`, summing `measured_exposure_hours`. Because deals
cover different numbers of calendar years (some less than a year, some more
than two), simply dividing the sum by `committed_annual_exposure_hours`
would distort the result — you first need to "annualize" the sum (divide by
the number of effective years the contract spans within the data window),
then divide by the committed value to get a delivery percentage. Using
`julianday` to compute the day count and convert it to years is the
standard SQLite way to handle date differences.

### SQL

```sql
SELECT
    sd.deal_name,
    sd.committed_annual_exposure_hours AS committed_hours,
    ROUND(
        SUM(sel.measured_exposure_hours)
        / ((julianday(MIN(sd.contract_end_date, '2026-06-30')) - julianday(sd.contract_start_date)) / 365.25),
        1
    ) AS actual_annualized_hours,
    ROUND(
        100.0 * SUM(sel.measured_exposure_hours)
        / (sd.committed_annual_exposure_hours
           * ((julianday(MIN(sd.contract_end_date, '2026-06-30')) - julianday(sd.contract_start_date)) / 365.25)),
        1
    ) AS delivery_pct
FROM sponsorship_deal sd
JOIN sponsor_exposure_log sel ON sel.sponsorship_deal_id = sd.id
GROUP BY sd.id
ORDER BY delivery_pct;
```

### Expected Result & Business Conclusion

The result is 12 rows, one per deal, sorted from lowest delivery rate to
highest. The bottom three (lowest to highest) — `StreakBet Gaming
Partnership`, `GridForge Fracture Protocol Hardware Deal`, and `TitanEnergy
Global Partnership` — all land in roughly the 68%-70% range (approximately
68.7%, 69.1%, and 70.1% respectively), a clear break from the other 9 deals
(delivery rates roughly 94%-106%). Next step: flag these 3 deals for a
"must verify before renewal negotiations" list and hand it to the Head of
Partnerships to decide whether to make up the exposure shortfall or
reprice.

---

## Query 2: Annual Sponsorship Revenue at Risk from Exposure-Gap Deals

### Business Context

Identifying which deals are under-delivering on exposure is only step one —
what the CFO actually cares about is how big a financial problem this is.
If the gap deals only account for 5% of total sponsorship value, this can
stay a lower priority; if they account for a large chunk, it needs to be
escalated to the CEO immediately. The CFO wants Query 1's findings
converted into a dollar figure and entered into the Q3 quarterly risk
register. This question also maps to Q1.

### Tags

Category: Aggregation + CASE · Difficulty: Intermediate · Role: CFO

### Approach

There's no need to recompute the delivery rate here — instead, flag the 3
known gap deals directly on `sponsorship_deal` using `CASE WHEN` (the
delivery rate calculation was already validated in Query 1; here, to keep
the focus on the financial view, the deals are enumerated by name directly
rather than redoing the annualization math), then group by that flag and
sum `annual_value_usd`. This is a classic "classify first, then aggregate"
pattern: the `CASE WHEN` sits in the `GROUP BY` grouping key rather than as
a display column in `SELECT`.

### SQL

```sql
SELECT
    CASE
        WHEN sd.deal_name IN (
            'TitanEnergy Global Partnership',
            'GridForge Fracture Protocol Hardware Deal',
            'StreakBet Gaming Partnership'
        ) THEN 'exposure_gap_deal'
        ELSE 'healthy_deal'
    END AS deal_health,
    COUNT(*) AS deal_count,
    SUM(sd.annual_value_usd) AS total_annual_value_usd,
    ROUND(100.0 * SUM(sd.annual_value_usd) / (SELECT SUM(annual_value_usd) FROM sponsorship_deal), 1) AS pct_of_total_sponsorship_value
FROM sponsorship_deal sd
GROUP BY deal_health;
```

### Expected Result & Business Conclusion

The result is two rows. The 3 gap deals total roughly $1.46M in annual
sponsorship value, about 42% of the total sponsorship value across all 12
deals. That's not "a minor blemish on a couple of contracts" — it's large
enough to affect this quarter's sponsorship revenue quality rating. Next
step: the CFO flags this $1.46M as "exposure delivery risk exposure,"
enters it into the quarterly risk register, and requires the Head of
Partnerships to bring a remediation plan before the next renewal window.

---

## Query 3: Exposure Delivery Rate Split by Sponsorship Scope

### Business Context

The Head of Partnerships wants to know whether the exposure gap is
concentrated in club-wide sponsorships (where `team_id` is null) — which
would suggest they're easier to overlook — or whether the problem also
shows up in team-scoped deals. That determines whether the fix belongs in
the content team's global exposure-measurement process, or in a specific
team's own broadcast operations.

### Tags

Category: Join + Group By · Difficulty: Intermediate · Role: Head of Partnerships

### Approach

Use whether `sponsorship_deal.team_id` is null as the grouping dimension,
with `CASE WHEN team_id IS NULL THEN 'org-wide' ELSE 'team-scoped' END`,
and compute the average delivery rate for each group. This reuses Query
1's delivery rate logic (annualized commitment vs. annualized measured
hours) wrapped in an inner subquery, with an outer layer that groups by
sponsorship scope and averages — a "compute the detail metric first, then
roll it up" two-layer structure.

### SQL

```sql
WITH deal_delivery AS (
    SELECT
        sd.id,
        sd.team_id,
        100.0 * SUM(sel.measured_exposure_hours)
        / (sd.committed_annual_exposure_hours
           * ((julianday(MIN(sd.contract_end_date, '2026-06-30')) - julianday(sd.contract_start_date)) / 365.25)) AS delivery_pct
    FROM sponsorship_deal sd
    JOIN sponsor_exposure_log sel ON sel.sponsorship_deal_id = sd.id
    GROUP BY sd.id
)
SELECT
    CASE WHEN team_id IS NULL THEN 'org_wide_deal' ELSE 'team_scoped_deal' END AS deal_scope,
    COUNT(*) AS deal_count,
    ROUND(AVG(delivery_pct), 1) AS avg_delivery_pct,
    ROUND(MIN(delivery_pct), 1) AS min_delivery_pct
FROM deal_delivery
GROUP BY deal_scope;
```

### Expected Result & Business Conclusion

The result is two rows. Gap deals show up in both club-wide and
team-scoped sponsorships (`TitanEnergy Global Partnership` is club-wide,
while `GridForge` and `StreakBet` are team-scoped), and both groups have a
minimum delivery rate in the 68%-70% range. That means the issue isn't tied
to one scope or the other — it's the systemic absence of a unified
post-delivery verification process, and any deal, regardless of scope, can
fall through the cracks. Next step: recommend the content team build a
quarterly exposure reconciliation process for all sponsorship deals
regardless of scope, rather than tightening review on just one category.

---

## Query 4: Player Trailing 6-Month Performance vs. Historical Peak

### Business Context

As the GM of Esports prepares next season's renewal budget, they want to
know which players' current form no longer matches their historical price
tag. Relying purely on the coaching staff's gut impression risks being
swayed by a "this guy used to be great" halo effect, so the analysis needs
to lean on objective `performance_rating` data instead. This question maps
to business question Q2, and also lays the groundwork for the next several
salary-related questions.

### Tags

Category: CTE + Aggregation · Difficulty: Advanced · Role: GM of Esports

### Approach

You need average performance ratings across two time windows: "trailing 6
months" (`match_date >= 6 months before REFERENCE_DATE`) and a "historical
peak window" (18 months before REFERENCE_DATE through 12 months before
REFERENCE_DATE). Use two independent CTEs to aggregate each window
separately, then join them on `roster_player_id` and subtract to compute
the decline. The pitfall here: if you try to split the two windows with a
single `CASE WHEN` inside one `GROUP BY`, the denominators get easy to mix
up (the two windows usually have different match counts), so aggregating
each window independently in its own CTE and then joining is the safer
approach.

### SQL

```sql
WITH recent_window AS (
    SELECT pms.roster_player_id, AVG(pms.performance_rating) AS recent_rating
    FROM player_match_stat pms
    JOIN match_result mr ON mr.id = pms.match_result_id
    WHERE mr.match_date >= date('2026-06-30', '-6 months')
    GROUP BY pms.roster_player_id
),
peak_window AS (
    SELECT pms.roster_player_id, AVG(pms.performance_rating) AS peak_rating
    FROM player_match_stat pms
    JOIN match_result mr ON mr.id = pms.match_result_id
    WHERE mr.match_date BETWEEN date('2026-06-30', '-18 months') AND date('2026-06-30', '-12 months')
    GROUP BY pms.roster_player_id
)
SELECT
    rp.gamertag,
    t.team_name,
    ROUND(pw.peak_rating, 2) AS peak_rating,
    ROUND(rw.recent_rating, 2) AS recent_rating,
    ROUND(100.0 * (rw.recent_rating - pw.peak_rating) / pw.peak_rating, 1) AS pct_change
FROM roster_player rp
JOIN team t ON t.id = rp.team_id
JOIN recent_window rw ON rw.roster_player_id = rp.id
JOIN peak_window pw ON pw.roster_player_id = rp.id
ORDER BY pct_change
LIMIT 10;
```

### Expected Result & Business Conclusion

The results are sorted from the largest decline to the smallest
(`ORDER BY pct_change` ascending, so the most negative comes first). The
top 4 players — Thornquil, Hollowmere, Zenithrax, and Wraithcall, in that
order — show a trailing 6-month performance rating roughly 30%-35% below
their historical peak, a clear break from the rest of the roster (most of
whom decline by less than 5%, and some of whom actually improved). The
exact ordering here only reflects decline magnitude — it doesn't imply
anything about salary size or review priority (it's the set of four that
matters, and the precise ranking may shift slightly with rating noise).
Next step: flag these 4 players as top priorities for renewal-window
review, and hand them off to Query 5 to check whether their salaries have
already become mismatched as a result.

---

## Query 5: Salary-Versus-Recent-Performance Mismatch Ranking

### Business Context

Query 4 identified players in decline — but decline by itself isn't the
problem. The problem is decline without a matching salary adjustment. The
GM of Esports needs a clear list of players whose salary no longer matches
their recent performance and whose contracts aren't yet up for
renegotiation, so next season's salary budget and renewal priorities can
be planned ahead of time.

### Tags

Category: CTE + Window Function · Difficulty: Advanced · Role: GM of Esports

### Approach

Building on Query 4, join in `player_contract` to bring in salary and
contract expiration data. Use `RANK() OVER (ORDER BY pct_change ASC)` to
rank players by decline magnitude, so the ranking updates automatically as
new player data comes in without touching the SQL. Also compute the months
remaining between `contract_end_date` and REFERENCE_DATE, to gauge how
long this mismatch will persist before there's a chance to correct it.

### SQL

```sql
WITH recent_window AS (
    SELECT pms.roster_player_id, AVG(pms.performance_rating) AS recent_rating
    FROM player_match_stat pms
    JOIN match_result mr ON mr.id = pms.match_result_id
    WHERE mr.match_date >= date('2026-06-30', '-6 months')
    GROUP BY pms.roster_player_id
),
peak_window AS (
    SELECT pms.roster_player_id, AVG(pms.performance_rating) AS peak_rating
    FROM player_match_stat pms
    JOIN match_result mr ON mr.id = pms.match_result_id
    WHERE mr.match_date BETWEEN date('2026-06-30', '-18 months') AND date('2026-06-30', '-12 months')
    GROUP BY pms.roster_player_id
)
SELECT
    rp.gamertag,
    pc.annual_salary_usd,
    ROUND(rw.recent_rating, 2) AS recent_rating,
    ROUND(100.0 * (rw.recent_rating - pw.peak_rating) / pw.peak_rating, 1) AS pct_change,
    pc.contract_end_date,
    CAST((julianday(pc.contract_end_date) - julianday('2026-06-30')) / 30 AS INTEGER) AS months_remaining,
    RANK() OVER (ORDER BY (rw.recent_rating - pw.peak_rating) / pw.peak_rating ASC) AS decline_rank
FROM roster_player rp
JOIN player_contract pc ON pc.roster_player_id = rp.id
JOIN recent_window rw ON rw.roster_player_id = rp.id
JOIN peak_window pw ON pw.roster_player_id = rp.id
ORDER BY decline_rank
LIMIT 6;
```

### Expected Result & Business Conclusion

The top 4 in the ranking (Thornquil, Hollowmere, Zenithrax, Wraithcall) all
sit near the top of their salary bands, with annual salaries between
$105,000 and $650,000, and more than 18 months remaining on their
contracts — yet they're the four players with the largest decline on the
whole roster. This is direct evidence of a guaranteed-contract,
high-salary-low-output mismatch. Next step: the GM of Esports adds this
list to next season's budget planning, launches a performance-improvement
plan for these 4 players or considers negotiating an early buyout, rather
than passively waiting for the contracts to expire in 2028.

---

## Query 6: Legacy Star vs. Rest-of-Roster Salary/Performance Correlation Comparison

### Business Context

For the board materials, the CFO needs to establish whether the
salary-versus-performance disconnect is isolated to these 4 individuals or
a symptom of a broken salary system overall. If the rest of the roster
still shows a reasonably positive relationship between salary and recent
performance once these 4 are excluded, that means the salary system itself
is fine — it's just these 4 contracts that need individual handling, not a
wholesale rework of the compensation framework.

### Tags

Category: Aggregation + Window Function (NTILE) · Difficulty: Intermediate · Role: GM of Esports

### Approach

Split players into two groups based on whether they're on the "decline
list" (the 4 legacy stars, enumerated directly by `gamertag`, whose
identity was already confirmed in Query 4/5). Within each group, compute
the average recent performance rating for the top and bottom salary
quantiles, and use "is the high-salary group's performance meaningfully
higher than the low-salary group's" as a coarse stand-in for a strict
Pearson correlation coefficient (SQLite has no built-in `CORR` function).
This is a common teaching workaround: approximating the statistical
concept of "correlation" with a grouped comparison.

### SQL

```sql
WITH recent_rating AS (
    SELECT pms.roster_player_id, AVG(pms.performance_rating) AS recent_rating
    FROM player_match_stat pms
    JOIN match_result mr ON mr.id = pms.match_result_id
    WHERE mr.match_date >= date('2026-06-30', '-6 months')
    GROUP BY pms.roster_player_id
),
tagged AS (
    SELECT
        rp.gamertag,
        CASE WHEN rp.gamertag IN ('Zenithrax', 'Wraithcall', 'Thornquil', 'Hollowmere')
             THEN 'legacy_star' ELSE 'rest_of_roster' END AS player_group,
        pc.annual_salary_usd,
        rr.recent_rating,
        NTILE(2) OVER (PARTITION BY
            CASE WHEN rp.gamertag IN ('Zenithrax', 'Wraithcall', 'Thornquil', 'Hollowmere')
                 THEN 'legacy_star' ELSE 'rest_of_roster' END
            ORDER BY pc.annual_salary_usd) AS salary_half
    FROM roster_player rp
    JOIN player_contract pc ON pc.roster_player_id = rp.id
    JOIN recent_rating rr ON rr.roster_player_id = rp.id
)
SELECT
    player_group,
    salary_half,
    COUNT(*) AS player_count,
    ROUND(AVG(annual_salary_usd), 0) AS avg_salary,
    ROUND(AVG(recent_rating), 2) AS avg_recent_rating
FROM tagged
GROUP BY player_group, salary_half
ORDER BY player_group, salary_half;
```

### Expected Result & Business Conclusion

The result is four rows. Within the `rest_of_roster` group, the higher
salary half (`salary_half=2`) has a noticeably higher average recent
performance rating than the lower salary half — salary and performance
move in the same direction. The `legacy_star` group, with only 4 players,
all high-salary but underperforming recently, no longer shows that same
positive relationship across its two salary tiers. This confirms the
disconnect is confined to these 4 contracts rather than a flaw in the
overall salary system design. Next step: the CFO can state in the board
materials that this is an isolated issue rather than a systemic one, and
narrow the remediation scope to just these 4 contracts.

---

## Query 7: Remaining Contract Months for Declining Players

### Business Context

The GM of Esports needs to know when these "high-salary, low-output"
players' contracts can earliest be renegotiated. If there's still a long
runway left, the cost mismatch can't simply be waited out and early
renegotiation needs to be considered; if the contracts are close to
expiring, the club can wait for the natural renewal window.

### Tags

Category: Date arithmetic · Difficulty: Basic · Role: GM of Esports

### Approach

Pull `contract_end_date` and `last_renegotiation_date` directly from
`player_contract` for the 4 legacy stars, and use SQLite's `julianday`
function to compute the days remaining until REFERENCE_DATE, then divide
by 30 to convert to months. This is basic date arithmetic — no window
functions or subqueries needed.

### SQL

```sql
SELECT
    rp.gamertag,
    pc.last_renegotiation_date,
    pc.contract_end_date,
    CAST((julianday(pc.contract_end_date) - julianday('2026-06-30')) / 30 AS INTEGER) AS months_remaining
FROM roster_player rp
JOIN player_contract pc ON pc.roster_player_id = rp.id
WHERE rp.gamertag IN ('Zenithrax', 'Wraithcall', 'Thornquil', 'Hollowmere')
ORDER BY months_remaining;
```

### Expected Result & Business Conclusion

4 rows, with months remaining ranging from 18 to 23, and each player's
last renegotiation date falling between September and December 2025 —
right around when their performance decline started to become visible.
This means the club signed these players to long-term deals right when the
decline was just starting and the data signal was still weak — a textbook
case of renewal timing landing in the murkiest possible window. Next step:
since all four contracts have more than 18 months remaining and natural
expiration is a long way off, the GM of Esports should initiate early
renegotiation or add performance clauses this quarter, rather than waiting
passively.

---

## Query 8: Team Trailing 60-Day Win Rate vs. Concurrent Merch Gross Margin

### Business Context

The Commercial Operations Analyst (that's you) needs to test a hypothesis:
does merch gross margin actually move with a team's recent win rate? If
that relationship holds, finance can't rely on total merch revenue alone
to judge whether the merch business is healthy — stable-looking revenue
could be masking margin that's being significantly eroded during a slump.
This question maps to business question Q3, and is the most technically
demanding question in this review.

### Tags

Category: Correlated Subquery + CTE · Difficulty: Advanced · Role: Commercial Operations Analyst

### Approach

Every `merch_sale` row needs to know "what was this team's win rate over
the 60 days leading up to this particular sale?" This can't be done with a
simple `GROUP BY`, because "the trailing 60 days" is a window computed
relative to each individual sale's date — it requires a correlated
subquery: for each row of `merch_sale`, the subquery looks back at
`match_result` for the same `team_id` with `match_date` falling in the
`[sale date - 60 days, sale date]` range, and computes the win rate. Only
team-scoped merch items (where `merch_sku.team_id` is not null) are
processed, since club-wide merchandise can't be attributed to a single
team. Once the win rate is computed, bucket it into "hot form" (>= 0.55),
"mid form," and "slump form" (< 0.35), and compare gross margin across
buckets. Correlated subqueries like this are fine on a small dataset, but
it's worth flagging: at millions of rows, this should be rewritten as a
precomputed "win rate time series" table joined in, rather than a
row-by-row correlated subquery.

### SQL

```sql
WITH sale_context AS (
    SELECT
        ms.id AS sale_id,
        ms.quantity,
        ms.unit_price_paid_usd,
        msk.unit_cost_usd,
        (
            SELECT CAST(SUM(CASE WHEN mr.result = 'win' THEN 1 ELSE 0 END) AS FLOAT) / COUNT(*)
            FROM match_result mr
            WHERE mr.team_id = msk.team_id
              AND mr.match_date BETWEEN date(ms.sale_date, '-60 days') AND ms.sale_date
        ) AS trailing_winrate
    FROM merch_sale ms
    JOIN merch_sku msk ON msk.id = ms.merch_sku_id
    WHERE msk.team_id IS NOT NULL
)
SELECT
    CASE
        WHEN trailing_winrate >= 0.55 THEN 'hot_form'
        WHEN trailing_winrate < 0.35 THEN 'slump_form'
        ELSE 'mid_form'
    END AS team_form_bucket,
    COUNT(*) AS sale_count,
    ROUND(AVG(trailing_winrate), 2) AS avg_trailing_winrate,
    ROUND(SUM(quantity * unit_price_paid_usd), 0) AS total_revenue_usd,
    ROUND(SUM(quantity * unit_price_paid_usd) / COUNT(*), 1) AS avg_revenue_per_sale_usd,
    ROUND(100.0 * SUM(quantity * (unit_price_paid_usd - unit_cost_usd)) / SUM(quantity * unit_price_paid_usd), 1) AS gross_margin_pct
FROM sale_context
WHERE trailing_winrate IS NOT NULL
GROUP BY team_form_bucket
ORDER BY avg_trailing_winrate;
```

### Expected Result & Business Conclusion

The result is three rows (slump, mid, and hot form). Gross margin during
hot form is roughly 50.5%, dropping to roughly 37% during slumps — a gap
of about 13.5 percentage points. But looking at "average amount per sale,"
hot form is about $164 versus about $146 during slumps — only about 11%
lower. In other words, during slumps the team is propping up unit sales
and headline revenue with heavier discounting, but the profitability of
each individual transaction is being squeezed hard. Next step: recommend
that financial reporting show merch gross margin alongside merch revenue,
tracked by trailing team form bucket, rather than relying on year-over-year
revenue alone.

---

## Query 9: Merch Revenue/Margin Comparison: Slump vs. Hot Form (by Team)

### Business Context

For the board materials, the COO wants a team-by-team table that makes it
immediately visible which team's merch business is most sensitive to win
rate. Query 8 established that the overall relationship exists; this
question breaks it down to the team level, helping the COO judge whether
one team in particular — say, Vanguard Academy, with its smaller fan base —
is disproportionately sensitive to form swings and needs its own inventory
and pricing strategy.

### Tags

Category: CASE + Aggregation · Difficulty: Intermediate · Role: COO

### Approach

Reuse Query 8's correlated-subquery win rate logic, but this time group by
both `team_id` and form bucket instead of form bucket alone. That gives
every team a "slump" row and a "non-slump" row, making a side-by-side
comparison straightforward.

### SQL

```sql
WITH sale_context AS (
    SELECT
        msk.team_id,
        ms.quantity,
        ms.unit_price_paid_usd,
        msk.unit_cost_usd,
        (
            SELECT CAST(SUM(CASE WHEN mr.result = 'win' THEN 1 ELSE 0 END) AS FLOAT) / COUNT(*)
            FROM match_result mr
            WHERE mr.team_id = msk.team_id
              AND mr.match_date BETWEEN date(ms.sale_date, '-60 days') AND ms.sale_date
        ) AS trailing_winrate
    FROM merch_sale ms
    JOIN merch_sku msk ON msk.id = ms.merch_sku_id
    WHERE msk.team_id IS NOT NULL
)
SELECT
    t.team_name,
    CASE WHEN trailing_winrate < 0.35 THEN 'slump_form' ELSE 'non_slump_form' END AS form_bucket,
    COUNT(*) AS sale_count,
    ROUND(SUM(quantity * unit_price_paid_usd), 0) AS total_revenue_usd,
    ROUND(100.0 * SUM(quantity * (unit_price_paid_usd - unit_cost_usd)) / SUM(quantity * unit_price_paid_usd), 1) AS gross_margin_pct
FROM sale_context sc
JOIN team t ON t.id = sc.team_id
WHERE trailing_winrate IS NOT NULL
GROUP BY t.team_name, form_bucket
ORDER BY t.team_name, form_bucket;
```

### Expected Result & Business Conclusion

The result is 6 rows (3 teams, each split into two buckets). All three
teams show a gross margin during slumps more than 10 percentage points
below their non-slump margin, meaning this isn't a quirk of one team — it's
a club-wide merch pricing habit ("discount to clear inventory during
slumps"). Next step: the COO can require all 3 teams to adopt a uniform
"cap discounting during slumps" inventory policy, rather than letting each
team handle it independently.

---

## Query 10: Distribution of Discount Depth During Slumps

### Business Context

Before proposing a cap on slump-period discounting to leadership, the
Commercial Operations Analyst first needs to establish exactly how deep
current slump-period discounting actually goes, so the recommendation can
be concrete and actionable rather than a vague "we're discounting too
much."

### Tags

Category: Aggregation · Difficulty: Basic · Role: Commercial Operations Analyst

### Approach

No correlated subquery needed here — just a basic distributional summary
(average, minimum, maximum) of `merch_sale.discount_pct`, split into two
groups based on whether the discount exceeds 25%. This is the simplest
aggregation query in the whole document, a fitting wrap-up to the "slump
problem" series and a segue into the prize payment topic that starts with
Query 11.

### SQL

```sql
SELECT
    CASE WHEN discount_pct > 25 THEN 'heavy_discount' ELSE 'normal_discount' END AS discount_tier,
    COUNT(*) AS sale_count,
    ROUND(AVG(discount_pct), 1) AS avg_discount_pct,
    ROUND(MIN(discount_pct), 1) AS min_discount_pct,
    ROUND(MAX(discount_pct), 1) AS max_discount_pct
FROM merch_sale
GROUP BY discount_tier;
```

### Expected Result & Business Conclusion

The result is two rows. The "heavy discount" group (over 25%) averages
roughly a 30% discount, peaking near 45% — a level that's approaching half
off list price. Next step: recommend setting the discount cap policy at
25%, with any promotion exceeding that threshold requiring joint approval
from merchandising and finance, rather than being left to the discretion of
store or online operations.

---

## Query 11: Late/Underpaid Prize Distribution Records by Team

### Business Context

Neither of the two agency complaint emails the General Manager of Esports
received named a specific team or player. Before responding to the
agencies formally, the club needs to verify internally where the problem
actually lies, so it doesn't unfairly pin blame on an innocent team or
overlook the team that's actually the source of the problem. This question
maps to business question Q4.

### Tags

Category: Aggregation + Join · Difficulty: Intermediate · Role: GM of Esports

### Approach

Join `player_prize_distribution` to `team` through `prize_pool_payout`,
and group by team to count total distribution records along with the count
and share where `payment_status` is not equal to `on_time`. Note that
`player_prize_distribution` itself has no `team_id` — you must go through
the `prize_pool_payout` intermediate table to get team information; skip
that join and the query will fail outright.

### SQL

```sql
SELECT
    t.team_name,
    COUNT(*) AS total_distributions,
    SUM(CASE WHEN ppd.payment_status != 'on_time' THEN 1 ELSE 0 END) AS problem_count,
    ROUND(100.0 * SUM(CASE WHEN ppd.payment_status != 'on_time' THEN 1 ELSE 0 END) / COUNT(*), 1) AS problem_pct
FROM player_prize_distribution ppd
JOIN prize_pool_payout ppo ON ppo.id = ppd.prize_pool_payout_id
JOIN team t ON t.id = ppo.team_id
GROUP BY t.team_name
ORDER BY problem_pct DESC;
```

### Expected Result & Business Conclusion

The result is three rows. `Vanguard Academy`'s problem-record share is
roughly 40%, far higher than `Vanguard Fracture` (roughly 7.5%) and
`Vanguard Aetherlane` (roughly 2.5%). That strongly suggests both agency
complaints trace back to Vanguard Academy players — the problem is heavily
concentrated in one team rather than spread club-wide. Next step: the GM
of Esports should prioritize a conversation with Vanguard Academy's Player
Payments Coordinator to pinpoint exactly where in that team's prize
distribution process things are breaking down.

---

## Query 12: Ranking of Prize Distribution Payment Delay Days

### Business Context

Once the problem team is identified, the Player Payments Coordinator (the
role that actually handles prize distributions, reporting to the GM of
Esports) needs a specific list of which record was late and by how many
days, in order to verify case by case whether this is a process problem or
an individual mistake.

### Tags

Category: Window Function (RANK) · Difficulty: Intermediate · Role: Player Payments Coordinator

### Approach

Compute each distribution record's delay in days using
`julianday(paid_date) - julianday(due_date)` (a negative number means
early payment), then rank from largest delay to smallest with
`RANK() OVER (ORDER BY ... DESC)`. A window function is used instead of
plain `ORDER BY` plus `LIMIT` because the ranking itself (which position a
record occupies) is useful later when cross-referencing against other
lists — keeping the rank in the result set is clearer than relying purely
on row order.

### SQL

```sql
SELECT
    rp.gamertag,
    t.team_name,
    ppd.contracted_amount_usd,
    ppd.actual_paid_amount_usd,
    CAST(julianday(ppd.paid_date) - julianday(ppd.due_date) AS INTEGER) AS days_late,
    RANK() OVER (ORDER BY julianday(ppd.paid_date) - julianday(ppd.due_date) DESC) AS lateness_rank
FROM player_prize_distribution ppd
JOIN roster_player rp ON rp.id = ppd.roster_player_id
JOIN prize_pool_payout ppo ON ppo.id = ppd.prize_pool_payout_id
JOIN team t ON t.id = ppo.team_id
ORDER BY lateness_rank
LIMIT 10;
```

### Expected Result & Business Conclusion

The top several results all show delays of over 50 days (the contracted
payment term is 30 days), and `Vanguard Academy` shows up repeatedly in
the `team_name` column, corroborating Query 11's conclusion. Next step: go
through every record in this list with a delay of more than 45 days and
verify the payment documentation case by case, to determine whether this
is a systemic process delay or human oversight, and prioritize
compensating these players.

---

## Query 13: Total Shortfall Amount Summary

### Business Context

Beyond lateness, some records also show the wrong amount paid
(`underpaid` or `late_and_underpaid`). The CFO needs to know the total
amount owed to players so this quarter's financial accrual can set aside
the right reserve for this "payable but unpaid" liability, rather than
having it surface as a surprise expense next quarter.

### Tags

Category: Aggregation · Difficulty: Basic · Role: CFO

### Approach

Filter directly on the two `payment_status` values that include
"underpaid" (`underpaid` and `late_and_underpaid`), and sum "contracted
amount minus actual amount paid" across those records to get the total
amount owed. This is a single-table aggregation that requires no join,
since `player_prize_distribution` already stores both the contracted and
actual-paid amount fields on the same row.

### SQL

```sql
SELECT
    COUNT(*) AS underpaid_record_count,
    ROUND(SUM(contracted_amount_usd - actual_paid_amount_usd), 2) AS total_shortfall_usd
FROM player_prize_distribution
WHERE payment_status IN ('underpaid', 'late_and_underpaid');
```

### Expected Result & Business Conclusion

The result is one row: roughly 10-12 underpaid records, totaling roughly
$5,000-$5,200 in shortfall. While the absolute dollar amount is small
(the prize pool itself is limited in size), leaving it uncorrected risks a
much bigger cost — if an agency notices that the contracted amount doesn't
match what was actually paid, the resulting trust damage far outweighs a
few thousand dollars. Next step: the CFO approves this amount as a "player
prize distribution compensation reserve" and requires finance to close the
gap within two weeks.

---

## Query 14: Distribution of Days from Organizer Payout to Club Receipt

### Business Context

Before pinning the blame entirely on internal club process, the Player
Payments Coordinator wants to rule out one possibility first: maybe the
tournament organizer itself is slow to pay out, dragging down the whole
chain, and the club is unfairly taking the blame. This question isolates
the first leg of the chain (organizer to club) and measures it separately
from the downstream player-payment leg.

### Tags

Category: Date arithmetic + Aggregation · Difficulty: Basic · Role: Player Payments Coordinator

### Approach

The `prize_pool_payout` table has both `organizer_payout_date` (when the
organizer initiates payment) and `org_received_date` (when the club
actually receives it) — subtracting one from the other gives the number of
days for this leg of the chain. Group by `tier` (tournament level) to see
whether payouts are simply slower for a particular tournament tier.

### SQL

```sql
SELECT
    t.tier,
    COUNT(*) AS payout_count,
    ROUND(AVG(julianday(ppo.org_received_date) - julianday(ppo.organizer_payout_date)), 1) AS avg_days_to_receive
FROM prize_pool_payout ppo
JOIN tournament t ON t.id = ppo.tournament_id
GROUP BY t.tier
ORDER BY avg_days_to_receive DESC;
```

### Expected Result & Business Conclusion

All three tournament tiers (S/A/B) show an average receipt time between 2
and 12 days, with no large gap between tiers — and all are far below the
45-plus-day delays seen at the player payment stage in Query 12. That
means the bottleneck isn't "the organizer pays slowly" — it's the internal
process between when the club receives the money and when it's passed
along to players. Next step: focus remediation squarely on the club's
internal prize distribution process, with no need to push on tournament
organizers.

---

## Query 15: Tournament Placement Distribution by Team

### Business Context

The GM of Esports needs a basic competitive results overview to open the
board materials — before discussing whether salaries are justified, board
members need a straightforward picture of how each of the three teams has
actually performed competitively. This is a grounding operational query,
not tied directly to any specific trap, but it provides context for the
analysis that follows.

### Tags

Category: Aggregation · Difficulty: Basic · Role: GM of Esports

### Approach

The `prize_pool_payout.placement` field records the final placement for
each tournament entry. Group by team and count championships (1st place),
top-2 finishes, top-4 finishes, and finishes below the top 4 — a
straightforward grouped count. Note that of 24 tournaments, 1 ended in a
group-stage elimination with no prize at all, so no `prize_pool_payout`
row was generated for it — meaning the three teams' `total_tournaments`
sums to 23, not 24.

### SQL

```sql
SELECT
    t.team_name,
    SUM(CASE WHEN ppo.placement = 1 THEN 1 ELSE 0 END) AS champion_finishes,
    SUM(CASE WHEN ppo.placement <= 2 THEN 1 ELSE 0 END) AS top2_finishes,
    SUM(CASE WHEN ppo.placement BETWEEN 3 AND 4 THEN 1 ELSE 0 END) AS top4_finishes,
    SUM(CASE WHEN ppo.placement > 4 THEN 1 ELSE 0 END) AS below_top4_finishes,
    COUNT(*) AS total_tournaments
FROM prize_pool_payout ppo
JOIN team t ON t.id = ppo.team_id
GROUP BY t.team_name
ORDER BY champion_finishes DESC;
```

### Expected Result & Business Conclusion

Across the three rows, `Vanguard Fracture` has the most championship (1st
place) finishes, consistent with the business context file's narrative
that "2026 marked the team's best playoff run in three years." Next step:
use this table as the opening background slide in the board materials,
setting up the central tension that follows — improved competitive results
paired with declining profitability.

---

## Query 16: Top 10 Broadcast Sessions by Peak Viewership

### Business Context

The Head of Content wants to know which broadcast sessions over the past
two seasons drew the largest live audiences, to prove to sponsors that the
club's content genuinely delivers reach — and to have leverage for the
next round of sponsorship pricing negotiations.

### Tags

Category: Order By + Join · Difficulty: Basic · Role: Head of Content

### Approach

Sort `broadcast_session.peak_viewers` directly and take the top 10, with a
join to `match_result` to pull in tournament stage information. Note that
`match_result_id` can be null, so a `LEFT JOIN` is needed rather than a
plain `JOIN` — otherwise non-match content broadcasts could be
unintentionally excluded (even though the highest-peak-viewership sessions
tend to be match broadcasts, writing `LEFT JOIN` is the safer habit).

### SQL

```sql
SELECT
    t.team_name,
    bs.broadcast_date,
    mr.stage,
    bs.average_viewers,
    bs.peak_viewers
FROM broadcast_session bs
JOIN team t ON t.id = bs.team_id
LEFT JOIN match_result mr ON mr.id = bs.match_result_id
ORDER BY bs.peak_viewers DESC
LIMIT 10;
```

### Expected Result & Business Conclusion

The top 10 sessions are almost entirely concentrated in the `playoffs` or
`grand_final` stages, with peak viewership in the 80,000-120,000 range,
and mostly belonging to the club's two top teams, `Vanguard Fracture` and
`Vanguard Aetherlane`. Next step: the Head of Content uses this list as
evidence of a "playoff-window premium" and recommends structuring
sponsorship deals with tiered pricing by tournament stage, rather than a
single flat rate all year.

---

## Query 17: MVP Count Leaderboard vs. Salary

### Business Context

The GM of Esports wants a quick sanity check: do the players with the most
MVP awards also have salaries to match their frequency of standout
performances? This cross-checks the "decline list" from Query 4/5 — a
player with a high MVP count but a comparatively low salary could be an
undervalued renewal opportunity, while the reverse (low MVP count, high
salary) is another confirmation of a high-salary-low-output signal.

### Tags

Category: Aggregation + Window Function · Difficulty: Intermediate · Role: GM of Esports

### Approach

Count occurrences of `was_mvp = true` grouped by `roster_player_id`, join
in salary information, and rank with `RANK()` ordered by MVP count — a
single query that answers both "ranking" and "salary comparison" at once.

### SQL

```sql
SELECT
    rp.gamertag,
    pc.annual_salary_usd,
    COUNT(*) AS mvp_count,
    RANK() OVER (ORDER BY COUNT(*) DESC) AS mvp_rank
FROM player_match_stat pms
JOIN roster_player rp ON rp.id = pms.roster_player_id
JOIN player_contract pc ON pc.roster_player_id = rp.id
WHERE pms.was_mvp = 1
GROUP BY rp.gamertag
ORDER BY mvp_rank
LIMIT 10;
```

### Expected Result & Business Conclusion

Among the players with the most MVP awards are decline-list regulars like
Thornquil, Zenithrax, and Hollowmere (confirming they genuinely had plenty
of standout moments historically, so their original salary pricing was
justified) — but also a player like Graniteshade, earning under $100,000 a
year yet tied for 3rd in MVP count with Zenithrax (whose salary is over
$600,000), making Graniteshade an undervalued renewal candidate. Next
step: the GM of Esports should pull out this "high MVP count, low salary"
subset as a separate list, marked as priority raise-and-renew candidates
next season.

---

## Query 18: Merch Category Revenue/Margin Contribution Share

### Business Context

The Commercial Operations Analyst needs to explain, in the review
materials, exactly which merch categories are driving profitability, so
the merchandising team can prioritize selection and stocking for next
season instead of restocking everything indiscriminately.

### Tags

Category: Aggregation · Difficulty: Basic · Role: Commercial Operations Analyst

### Approach

Group by `merch_sku.category` and roll up revenue and gross margin — a
standard "category contribution" aggregation query with no complex
cross-table logic.

### SQL

```sql
SELECT
    msk.category,
    COUNT(*) AS sale_count,
    ROUND(SUM(ms.quantity * ms.unit_price_paid_usd), 0) AS total_revenue_usd,
    ROUND(100.0 * SUM(ms.quantity * (ms.unit_price_paid_usd - msk.unit_cost_usd)) / SUM(ms.quantity * ms.unit_price_paid_usd), 1) AS gross_margin_pct
FROM merch_sale ms
JOIN merch_sku msk ON msk.id = ms.merch_sku_id
GROUP BY msk.category
ORDER BY total_revenue_usd DESC;
```

### Expected Result & Business Conclusion

The `jersey` category leads revenue share by a wide margin, outpacing the
other three categories combined, while gross margins across all four
categories cluster in the 44%-47% range with little variation. Next step:
merchandising should keep weighting next season's inventory and marketing
budget toward jerseys, while applying the discount caps suggested by
Queries 8/9/10 uniformly across all categories.

---

## Query 19: Sponsorship Value Split by Contract Naming Keyword (Global vs. Team-Scoped)

### Business Context

The Head of Partnerships wants a quick gut check: do club-wide contracts
with "Global" in the name carry a meaningfully higher average value than
team-scoped deals? If so, it suggests "upgrading more brand partners from
team-scoped to club-wide sponsorship" is a commercial direction worth
pushing.

### Tags

Category: Pattern Matching (LIKE) · Difficulty: Basic · Role: Head of Partnerships

### Approach

Use `LIKE '%Global%'` to match the keyword in deal names, splitting the 12
deals into two groups and averaging annual sponsorship value for each.
This is the only question in the document that uses `LIKE` for text
matching — worth flagging that classifying by a naming-convention keyword
only works if the naming convention itself is consistent enough (in this
dataset, club-wide deals are deliberately named with "Global" as a
commercial naming convention, not a coincidence).

### SQL

```sql
SELECT
    CASE WHEN sd.deal_name LIKE '%Global%' THEN 'org_wide_global_deal' ELSE 'team_scoped_deal' END AS deal_naming_pattern,
    COUNT(*) AS deal_count,
    ROUND(AVG(sd.annual_value_usd), 0) AS avg_annual_value_usd
FROM sponsorship_deal sd
GROUP BY deal_naming_pattern;
```

### Expected Result & Business Conclusion

The result is two rows. Club-wide deals with "Global" in the name average
roughly $420,000 in annual value, versus roughly $194,000 for team-scoped
deals — the former is more than twice the latter. Next step: in the next
round of commercial negotiations, the Head of Partnerships should
prioritize pitching existing team-scoped sponsors on upgrading to
club-wide sponsorship, as a clear lever for growing total sponsorship
value.

---

## Query 20: Board Summary Scorecard: All Four Questions on One Page

### Business Context

At the July board meeting, the COO needs to put the key numbers for all
four business questions on a single page, rather than making board members
flip through 19 separate tables. This is the final query of the entire
review, rolling the key figures from each of the four previously verified
traps into a single row.

### Tags

Category: CTE combining multiple subqueries · Difficulty: Advanced · Role: COO

### Approach

Each of the four business questions gets its own independent CTE, and each
CTE returns exactly one summary row (count and dollar exposure of
exposure-gap sponsorship deals; count and total salary of salary-mismatched
players; merch gross margin gap in percentage points; count and total
shortfall of problem prize distribution records). Because every CTE
returns exactly one row, they can be stitched into a single row with a
comma-separated implicit `CROSS JOIN`, without an explicit `JOIN ON`
condition — a practical technique for a "combine several independent
single-row summaries into one dashboard row" scenario, but only safe when
each CTE is guaranteed to return exactly one row; otherwise you risk an
unexpected Cartesian-product blowup. The `merch_margin_gap` CTE reuses the
"bucket by team trailing 60-day win rate" correlated-subquery pattern from
Query 8, computing the hot-form and slump-form margins live and
subtracting them, rather than hardcoding a fixed number — so this column
automatically tracks the data even if the dataset is regenerated later and
the calibration constants change, instead of silently going stale.

### SQL

```sql
WITH sponsor_exposure_gap AS (
    SELECT
        COUNT(*) AS n_rigged_deals,
        SUM(annual_value_usd) AS value_at_risk_usd
    FROM sponsorship_deal
    WHERE deal_name IN ('TitanEnergy Global Partnership', 'GridForge Fracture Protocol Hardware Deal', 'StreakBet Gaming Partnership')
),
salary_performance_gap AS (
    SELECT
        COUNT(*) AS n_legacy_stars,
        SUM(pc.annual_salary_usd) AS salary_at_risk_usd
    FROM roster_player rp
    JOIN player_contract pc ON pc.roster_player_id = rp.id
    WHERE rp.gamertag IN ('Zenithrax', 'Wraithcall', 'Thornquil', 'Hollowmere')
),
merch_sale_context AS (
    SELECT
        ms.quantity,
        ms.unit_price_paid_usd,
        msk.unit_cost_usd,
        (
            SELECT CAST(SUM(CASE WHEN mr.result = 'win' THEN 1 ELSE 0 END) AS FLOAT) / COUNT(*)
            FROM match_result mr
            WHERE mr.team_id = msk.team_id
              AND mr.match_date BETWEEN date(ms.sale_date, '-60 days') AND ms.sale_date
        ) AS trailing_winrate
    FROM merch_sale ms
    JOIN merch_sku msk ON msk.id = ms.merch_sku_id
    WHERE msk.team_id IS NOT NULL
),
merch_margin_gap AS (
    SELECT
        ROUND(
            100.0 * SUM(CASE WHEN trailing_winrate >= 0.55 THEN quantity * (unit_price_paid_usd - unit_cost_usd) END)
                / NULLIF(SUM(CASE WHEN trailing_winrate >= 0.55 THEN quantity * unit_price_paid_usd END), 0)
            - 100.0 * SUM(CASE WHEN trailing_winrate < 0.35 THEN quantity * (unit_price_paid_usd - unit_cost_usd) END)
                / NULLIF(SUM(CASE WHEN trailing_winrate < 0.35 THEN quantity * unit_price_paid_usd END), 0),
            1
        ) AS margin_gap_pp
    FROM merch_sale_context
),
prize_payment_gap AS (
    SELECT
        COUNT(*) AS n_late_or_underpaid,
        ROUND(SUM(contracted_amount_usd - actual_paid_amount_usd), 2) AS shortfall_usd
    FROM player_prize_distribution
    WHERE payment_status != 'on_time'
)
SELECT * FROM sponsor_exposure_gap, salary_performance_gap, merch_margin_gap, prize_payment_gap;
```

### Expected Result & Business Conclusion

The result is a single row with eight columns: 3 gap deals / roughly $1.46M
in risk exposure; 4 salary-mismatched players / roughly $2.047M in salary
exposure; a merch gross margin gap of roughly 13.5 percentage points; and
18 problem prize distribution records / roughly $5,085 in shortfall. Next
step: the COO drops this single row directly onto the first page of the
board deck, with a detail chart for each of the four questions (pulled
from the results of Query 1, 5, 8, and 11 respectively), forming the
executive summary for the entire review.

---

## Business Question to Query Mapping

| Business Question | Corresponding Queries |
|----------|----------|
| Q1 Sponsor exposure billing gap | Query 1, 2, 3, 19, 20 |
| Q2 Salary-versus-performance disconnect | Query 4, 5, 6, 7, 17, 20 |
| Q3 Merch gross margin tied to win rate | Query 8, 9, 10, 18, 20 |
| Q4 Prize distribution payment compliance | Query 11, 12, 13, 14, 20 |
| Operational background (not tied to a specific trap) | Query 15, 16 |
