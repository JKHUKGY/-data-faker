# Ember Realms Saga Player Economy & Third-Party Top-Up Channel Health: SQL Queries

This document covers 20 SQL queries for the `gaming_f2p_whale_monetization_medium`
dataset. For business background, the company story, and the five core business
questions, see `01-gaming_f2p_whale_monetization_medium_business_context.md`; for
table structure and field definitions, see
`02-gaming_f2p_whale_monetization_medium_er_document.md`.

**About REFERENCE_DATE.** This dataset is anchored to `2026-06-30`. Anywhere a
query needs "today," it uses the literal date `'2026-06-30'` instead of
`DATE('now')` — that way the results are fully reproducible no matter when the
query is actually run.

## How to use this document

You're a newly hired Game Economy Analyst at Pinnacle Peak Games, and this
document is the first batch of assignments your manager (the Director of Live
Operations) has handed you. Every query has five parts:

1. **Business context**: who is asking this question, why now, and what decision
   the answer will drive.
2. **Tags**: SQL technique category / difficulty / asking role.
3. **Approach**: before you look at the SQL, a plain-language walkthrough of
   which tables to join, what grain to aggregate at, and which traps to avoid
   (for example, whether joining in the wrong direction causes double counting).
4. **SQL**: a query you can run directly against the generated SQLite database.
5. **Expected result and business conclusion**: what the output looks like, what
   the numbers mean, and what you should do next after seeing this result.

Each of the 20 queries traces back to one of the five business questions (Q1-Q5)
in the business context document, or supports day-to-day operational monitoring.
The SQL itself is meant to be learned, not just run — read the "Approach" section
before looking at the SQL, rather than reverse-engineering the approach from the
SQL.

## Query index

| # | Title | Business role | SQL category | Difficulty |
|------|------|----------|----------|------|
| 1 | Whale revenue concentration overview | VP of Monetization & Publishing | Aggregation | Basic |
| 2 | Purchase frequency and average order value by payer tier | CFO | Aggregation | Basic |
| 3 | Lifetime spend leaderboard and percentile ranking | VP of Monetization & Publishing | Window Function | Intermediate |
| 4 | Actual gacha drop rates vs. disclosed probability, pool by pool | Senior Game Economy Analyst | Join + Aggregation | Intermediate |
| 5 | Standard pool vs. limited pool overall drop rate comparison | Head of Game Design | Aggregation | Basic |
| 6 | Live-Ops event calendar and stacking detection | Senior Game Economy Analyst | Window Function + Date/Time | Basic |
| 7 | Average order value changes during stacked-event windows | Live Ops Program Manager | Join + Aggregation | Intermediate |
| 8 | Event-fatigue retention comparison (dose-response analysis) | Director of Live Operations | CTE + Aggregation | Advanced |
| 9 | Paid price as a percent of list price, by payment channel | Senior Game Economy Analyst | Join + Aggregation | Basic |
| 10 | Refund/chargeback incidence rate by payment channel | Senior Game Economy Analyst | Join + Aggregation | Intermediate |
| 11 | Out-of-region redemption rate for discount codes (leaked vs. normal) | Senior Game Economy Analyst | Join + Subquery | Intermediate |
| 12 | High-risk transaction detail related to top-up agents / sock-puppet accounts | Trust & Safety Analyst | Join + Pattern Matching | Intermediate |
| 13 | Risk rate for account groups sharing a device fingerprint | Trust & Safety Lead | CTE + Aggregation | Advanced |
| 14 | Roster of suspected fraud ring members | Trust & Safety Lead | Subquery | Basic |
| 15 | Monthly revenue trend with 3-month moving average | CFO | Window Function + Date/Time | Intermediate |
| 16 | Support ticket category distribution and SLA performance | Player Support Manager | Aggregation | Basic |
| 17 | 30-day retention curve by install-month cohort | Senior Game Economy Analyst | CTE + Date/Time | Intermediate |
| 18 | Acquisition channel quality comparison | Senior Game Economy Analyst | Join + Aggregation | Intermediate |
| 19 | Revenue by billing region and share from arbitrage regions | CFO | Join + Aggregation | Basic |
| 20 | Combined scorecard for the five traps | VP of Monetization & Publishing | CTE + Subquery | Advanced |

---

## Query 1: Whale revenue concentration overview

**Business context**

The VP of Monetization & Publishing is presenting to the CEO next week on "who
actually carries this business." She's heard the Live Ops team casually mention
that "roughly 1% of players account for most of the revenue," but she's never
seen the exact numbers. If that claim holds up, it means the company should
seriously consider building something like a dedicated "key account manager"
retention program for this small group, rather than pushing the same events at
everyone equally. This query maps to Q1 in the business context document.

**Tags**: Aggregation | Basic | VP of Monetization & Publishing

**Approach**

This only needs the `player` and `iap_transaction` tables. `player.player_segment`
was already assigned during data generation using exact headcounts
(whale/dolphin/minnow/non_payer), so there's no need to write your own
percentile logic — just `GROUP BY` this column directly. Use `LEFT JOIN`, not
`INNER JOIN` — non_payer players have zero rows in `iap_transaction`, and an
`INNER JOIN` would silently drop that entire tier from the result, making it
look like there are no non-paying players at all. The denominator for the
percentage should come from a scalar subquery (no `GROUP BY`) that pulls total
revenue across the whole database — you can't divide within the grouped result
set directly. Also, because the `LEFT JOIN` produces all-NULL
`paid_price_usd` values for non_payer, the numerator's `SUM(t.paid_price_usd)`
must be wrapped in `COALESCE(..., 0)` — otherwise the non_payer row's
`pct_of_revenue` would show up as NULL instead of 0%, making it look like the
metric is broken or the data is missing.

**SQL**

```sql
SELECT
    p.player_segment,
    COUNT(DISTINCT p.id) AS player_count,
    ROUND(100.0 * COUNT(DISTINCT p.id) / (SELECT COUNT(*) FROM player), 2) AS pct_of_players,
    ROUND(COALESCE(SUM(t.paid_price_usd), 0), 2) AS total_revenue_usd,
    ROUND(100.0 * COALESCE(SUM(t.paid_price_usd), 0) / (SELECT SUM(paid_price_usd) FROM iap_transaction), 2) AS pct_of_revenue
FROM player p
LEFT JOIN iap_transaction t ON t.player_id = p.id
GROUP BY p.player_segment
ORDER BY total_revenue_usd DESC;
```

**Expected result and business conclusion**

4 rows, one per payer tier. Whales are just 1% of all players but drive about
65.8% of revenue; dolphins are 3% of players and drive about 28.4%; minnows are
6% and drive about 5.7%; non_payers are 90% of players and drive 0%. The top 4%
(whales + dolphins combined) account for more than 90% of revenue. Next step:
recommend the VP approve a dedicated retention process for whales (for example,
priority manual review of anomalous behavior, a dedicated support channel),
because if this group churns, the revenue hit is a cliff, not a gradual slope.

---

## Query 2: Purchase frequency and average order value by payer tier

**Business context**

The CFO wants to dig one level deeper into the revenue gap from Query 1: are
whales buying more often, buying more expensive items each time, or both? The
answer determines which direction next quarter's pricing strategy should push.

**Tags**: Aggregation | Basic | CFO

**Approach**

This time we only care about players who have made at least one transaction, so
`INNER JOIN` is sufficient (unlike Query 1, which needed to preserve
non_payers). The key is computing two ratios side by side: transactions per
player (total transactions / distinct player count) and average order value
(`AVG(paid_price_usd)`) — you need both numbers together to see where the
revenue gap actually comes from.

**SQL**

```sql
SELECT
    p.player_segment,
    COUNT(DISTINCT p.id) AS paying_players,
    COUNT(t.id) AS tx_count,
    ROUND(1.0 * COUNT(t.id) / COUNT(DISTINCT p.id), 1) AS avg_tx_per_player,
    ROUND(AVG(t.paid_price_usd), 2) AS avg_tx_value_usd
FROM player p
JOIN iap_transaction t ON t.player_id = p.id
GROUP BY p.player_segment
ORDER BY avg_tx_value_usd DESC;
```

**Expected result and business conclusion**

3 rows (whale/dolphin/minnow — non_payer has no transactions, so it doesn't
appear). Whales have both the highest transaction frequency (about 117 per
player) and the highest average order value (about $67.90); dolphins average
about 50 transactions with an order value around $22.80; minnows average about
14 transactions with an order value around $8.20. This tells us the whale
revenue advantage comes from buying more often *and* buying more expensive
items — not just one factor. Next step: the product team could design
higher-priced tiers targeted at whales (building on the existing Ultimate Shard
Vault), while pushing subscription-style products (Monthly VIP Pass / Battle
Pass Premium) toward dolphins to raise their purchase frequency.

---

## Query 3: Lifetime spend leaderboard and percentile ranking

**Business context**

The VP of Monetization & Publishing wants a concrete "top 10 players" list, not
just a tier-level summary — she wants to check whether any of these
high-value players have gone quiet for a long time and are worth a dedicated
retention effort.

**Tags**: Window Function | Intermediate | VP of Monetization & Publishing

**Approach**

Using the `RANK()` window function ordered by `lifetime_spend_usd` descending
has an advantage over a plain `ORDER BY` + `LIMIT`: if there's a tie (two
players with the exact same lifetime spend), `RANK()` gives them the same rank
instead of arbitrarily breaking the tie — which fits business intuition better
than `ROW_NUMBER()` when the dataset is small and duplicate amounts are
possible. Percentile is computed as rank divided by total player count.

**SQL**

```sql
SELECT
    id AS player_id,
    player_segment,
    lifetime_spend_usd,
    RANK() OVER (ORDER BY lifetime_spend_usd DESC) AS spend_rank,
    ROUND(100.0 * RANK() OVER (ORDER BY lifetime_spend_usd DESC) / (SELECT COUNT(*) FROM player), 2) AS percentile_from_top
FROM player
ORDER BY lifetime_spend_usd DESC
LIMIT 10;
```

**Expected result and business conclusion**

10 rows, all with `player_segment = 'whale'`, with lifetime spend starting
around $15,200 and decreasing from there; `percentile_from_top` stays within
0.2% for all of them. Next step: hand this list to the Player Support Manager
to cross-check these 10 players' recent `last_active_date` and
`churn_risk_score` values (both fields live directly on the `player` table —
see the `player` table definition in the ER document), and kick off a
one-on-one retention outreach for any top-tier player already showing signs of
churn.

---

## Query 4: Actual gacha drop rates vs. disclosed probability, pool by pool

**Business context**

You (the Game Economy Analyst) received a summary of player complaints escalated
from Trust & Safety, including a handful of scattered comments along the lines
of "it feels like the limited pool never drops anything good." Before escalating
this formally to the Head of Game Design, you need to verify it yourself: across
the 8 gacha pools, is the actual Legendary drop rate meaningfully below the
officially disclosed probability in any of them? This is the most sensitive
query in the entire dataset — if confirmed, it's not just a data problem, it's a
player-trust problem. Maps to Q2 in the business context document.

**Tags**: Join + Aggregation | Intermediate | Senior Game Economy Analyst

**Approach**

The `gacha_pool` table only stores the officially disclosed probability; what a
player actually pulled is recorded in `gacha_pull_log.result_rarity`, so you
need to `JOIN` the two tables, aggregate the actual Legendary share by
`gacha_pool.id`, and subtract the disclosed value from the actual value to get
the "gap" (in percentage points, pp — not the gap as a fraction of the
disclosed value). It's essential to group by pool `id`, not by `pool_type`
(standard vs. limited) — if you aggregate by `pool_type` first, the 2 honest
pools among the 5 limited pools will average out the 3 problematic ones,
masking which specific pools are the issue (Query 5 demonstrates this trap
directly).

**SQL**

```sql
SELECT
    gp.pool_name,
    gp.pool_type,
    gp.disclosed_legendary_prob_pct AS disclosed_pct,
    COUNT(gpl.id) AS total_pulls,
    SUM(CASE WHEN gpl.result_rarity = 'Legendary' THEN 1 ELSE 0 END) AS legendary_count,
    ROUND(100.0 * SUM(CASE WHEN gpl.result_rarity = 'Legendary' THEN 1 ELSE 0 END) / COUNT(gpl.id), 2) AS actual_pct,
    ROUND(
        100.0 * SUM(CASE WHEN gpl.result_rarity = 'Legendary' THEN 1 ELSE 0 END) / COUNT(gpl.id)
        - gp.disclosed_legendary_prob_pct,
        2
    ) AS gap_pp
FROM gacha_pool gp
JOIN gacha_pull_log gpl ON gpl.gacha_pool_id = gp.id
GROUP BY gp.id
ORDER BY gap_pp ASC;
```

**Expected result and business conclusion**

8 rows, sorted from the most negative gap to the most positive. The top 3
limited pools (Anniversary Celebration Banner at about -2.25pp, Frostbound
Knight Rate-Up Banner at about -1.59pp, Ember Queen Rate-Up Banner at about
-1.58pp) all show gaps larger than 1.5 percentage points; the remaining 5 pools
(2 limited pools plus 3 standard pools) all fall within ±0.5 percentage points,
consistent with normal sampling noise. Next step: flag these 3 pools for
immediate escalation to the Head of Game Design and legal review; the other 5
don't need escalation.

---

## Query 5: Standard pool vs. limited pool overall drop rate comparison

**Business context**

The Head of Game Design's first reaction is "we've never systematically
manipulated the limited pools," and wants to look at the coarsest possible
comparison — standard pools overall vs. limited pools overall — to decide
whether further digging is even warranted.

**Tags**: Aggregation | Basic | Head of Game Design

**Approach**

Nearly the same `JOIN` as Query 4, except `GROUP BY gp.pool_type` instead of
`GROUP BY gp.id`. The whole point of this query is to demonstrate exactly how
much its own conclusion is "correct but not actionable enough."

There's also a fan-out weighting detail worth calling out up front: once
`gacha_pool` is joined to `gacha_pull_log`, each pool's row gets duplicated
once per pull, so `AVG(gp.disclosed_legendary_prob_pct)` actually produces a
**pull-count-weighted** average of the disclosed probability, not a simple
arithmetic mean across pools. For example, if 3 standard pools disclose 2.0% /
3.0% / 5.0%, the simple average is (2.0+3.0+5.0)/3 = 3.33%, but because the
three pools don't have equal pull volumes, the weighted `avg_disclosed_pct`
comes out to about 3.19%. That's not a bug — it's just something to keep in
mind if you try to sanity-check it against a simple average and the numbers
don't line up (if you actually want a simple average, deduplicate `gacha_pool`
first, then take the mean).

**SQL**

```sql
SELECT
    gp.pool_type,
    ROUND(AVG(gp.disclosed_legendary_prob_pct), 2) AS avg_disclosed_pct,
    COUNT(gpl.id) AS total_pulls,
    ROUND(100.0 * SUM(CASE WHEN gpl.result_rarity = 'Legendary' THEN 1 ELSE 0 END) / COUNT(gpl.id), 2) AS avg_actual_pct
FROM gacha_pool gp
JOIN gacha_pull_log gpl ON gpl.gacha_pool_id = gp.id
GROUP BY gp.pool_type;
```

**Expected result and business conclusion**

2 rows. `standard` pools show a disclosed average of about 3.19% vs. an actual
rate of about 3.44% — essentially matching. `limited_rateup` pools show a
disclosed average of about 3.13% vs. an actual rate of about 2.07%, an overall
gap of roughly 1.06 percentage points. This overall gap does hint that
"something's off with limited pools in aggregate," but it can't tell you which
specific pools need fixing — 2 of the 5 limited pools are completely honest, and
if you only looked at this summary table and went to hold "the limited-pool
team" accountable, you'd unfairly implicate the designers of the Shadowfang
Assassin and Golden Phoenix pools, which are both clean. Next step: go back to
the pool-by-pool results in Query 4 to pinpoint the 3 specific problem pools
before taking any action — don't stop at this summary table.

---

## Query 6: Live-Ops event calendar and stacking detection

**Business context**

You need to start verifying the claim that "events are scheduled too close
together." The first step is to walk through the full-year event calendar and
confirm which events actually meet the definition of "stacked" (starting less
than 7 days after the previous one ends), rather than relying on impressions.

**Tags**: Window Function + Date/Time | Basic | Senior Game Economy Analyst

**Approach**

Use `LAG()` ordered by `start_date` to pull the previous event's end date, then
compute the day gap with `julianday()` to independently derive the gap between
each event and the one before it, and cross-check it against the existing
`live_ops_event.is_stacked_event` flag. This query isn't hard on its own, but
it's foundational for Query 7 and Query 8 — you need to confirm the "stacked"
definition holds up before the downstream retention analysis means anything.

**SQL**

```sql
SELECT
    id,
    event_name,
    event_type,
    start_date,
    end_date,
    is_stacked_event,
    LAG(end_date) OVER (ORDER BY start_date) AS previous_event_end_date,
    julianday(start_date) - julianday(LAG(end_date) OVER (ORDER BY start_date)) AS gap_days_from_previous
FROM live_ops_event
ORDER BY start_date;
```

**Expected result and business conclusion**

30 rows, in chronological order. Any row where `gap_days_from_previous` is less
than 7 should have `is_stacked_event` set to 1 (true); rows at 7 or above
should be 0 (false) — this query itself serves as an independent check on the
`is_stacked_event` flag. Across the full year's 30 events, 8 are flagged as
stacked, clustered into 4 consecutive small groups. Next step: once the flags
are confirmed correct, pass the `id` values for these 8 events into Query 7
and Query 8 for further analysis.

---

## Query 7: Average order value changes during stacked-event windows

**Business context**

The Live Ops Program Manager wants to check the most direct question first: do
players actually spend more during stacked-event windows? This is the first
step in validating the hypothesis that "events drive short-term revenue" — it
doesn't yet touch on downstream retention.

**Tags**: Join + Aggregation | Intermediate | Live Ops Program Manager

**Approach**

To determine whether a transaction's `transaction_date` falls inside any
"stacked-event window," the most natural approach is a correlated subquery with
`EXISTS` — for each transaction, check whether there exists at least one
stacked event whose date range contains that transaction's date. Don't use a
plain `JOIN` followed by `GROUP BY transaction.id` — if a transaction happened
to fall in the overlap of two stacked-event windows (theoretically rare but not
impossible), a `JOIN` would double-count it. `EXISTS` naturally means "at least
one match, counted once," which is safer here.

Once you compute average order value, calculating ARPPU (revenue per paying
player) alongside it reveals a counterintuitive trap: if you naively compare
"total revenue inside the window / distinct paying players inside the window"
against "total revenue outside the window / distinct paying players outside the
window," the raw ARPPU outside the window actually comes out *higher* — not
because payment efficiency is better outside the window, but because only 8 of
the 30 events are stacked events, so the "inside window" period covers just 72
calendar days total, while the "outside window" period covers the remaining 469
calendar days between launch and REFERENCE_DATE. The observation-window lengths
on the two sides of the comparison aren't remotely equal. The correct approach
is to normalize both sides' ARPPU by the number of calendar days in their
respective windows (i.e., ARPPU / days) — only then is it a fair comparison of
payment efficiency.

**SQL**

```sql
WITH stacked_windows AS (
    SELECT start_date, end_date FROM live_ops_event WHERE is_stacked_event = 1
),
tx_flagged AS (
    SELECT
        t.*,
        EXISTS (
            SELECT 1 FROM stacked_windows sw
            WHERE t.transaction_date BETWEEN sw.start_date AND sw.end_date
        ) AS in_stacked_window
    FROM iap_transaction t
)
SELECT
    in_stacked_window,
    COUNT(*) AS tx_count,
    COUNT(DISTINCT player_id) AS paying_players,
    ROUND(AVG(paid_price_usd), 2) AS avg_tx_value_usd,
    ROUND(SUM(paid_price_usd) / COUNT(DISTINCT player_id), 2) AS raw_arppu_usd,
    ROUND(
        SUM(paid_price_usd) / COUNT(DISTINCT player_id)
        / (CASE WHEN in_stacked_window THEN 72.0 ELSE 469.0 END),
        3
    ) AS arppu_per_day_usd
FROM tx_flagged
GROUP BY in_stacked_window;
```

`72.0` and `469.0` are, respectively, the total number of days covered by the
8 stacked-event windows across the whole year, and the number of days remaining
in the full observation period (541 days, from the launch date `2025-01-06` to
`REFERENCE_DATE` `2026-06-30`) after subtracting those 72 days. Both numbers
can be verified by hand against the Query 6 results; they're hardcoded here as
literals, following the same principle as `REFERENCE_DATE` elsewhere in this
document — constants are written as fixed literals to guarantee
reproducibility.

**Expected result and business conclusion**

2 rows. Transactions falling inside stacked-event windows (about 3,869
transactions, 369 paying players) have an average order value of about $41.96;
transactions outside those windows (about 13,804 transactions, 499 paying
players) average about $32.06 — roughly 31% higher inside the stacked windows.
But if you only look at `raw_arppu_usd` (about $439.94 inside the window vs.
about $886.94 outside), you'd wrongly conclude that "payment efficiency is
higher outside the window" — this is exactly the pitfall the glossary warns
about when it says ARPPU can be inflated by an illusion of event-driven
prosperity: what gets inflated isn't the un-normalized raw ARPPU, it's the
day-normalized `arppu_per_day_usd`. Once normalized, the window-inside rate is
about $6.11/day vs. about $1.89/day outside — payment efficiency during
stacked windows is roughly 3.2x higher. Next step: this confirms the first half
of the hypothesis that "stacked events do raise short-term order value and
payment efficiency" — but that's only one side of the coin, and you still need
to look at Query 8's retention data to determine whether this is a case of
"borrowing from tomorrow" — an illusion of prosperity paid for with future
churn.

---

## Query 8: Event-fatigue retention comparison (dose-response analysis)

**Business context**

The Director of Live Operations needs to give a final answer for the board
materials in two weeks: are high-frequency stacked events a net positive, or
are they eating into player retention? This is the single most important query
in the entire document — it directly determines whether next quarter's event
schedule needs to be tightened up. Maps to Q3 in the business context document.

**Tags**: CTE + Aggregation | Advanced | Director of Live Operations

**Approach**

The easiest trap in this query is picking the wrong control group. If you
directly compare "players who participated in 2+ stacked events" against
"players who never participated in any stacked event," you get a
counterintuitive result: the latter group appears to retain *worse* — because
simply having the opportunity to participate in 2 stacked events requires a
player to have stuck around long enough for that to happen in the first place,
which naturally selects for longer-tenured players (survivorship bias). This
bias is larger than the fatigue effect itself and would completely distort the
conclusion. The correct control group is a dose-response design: both groups
must have already participated in at least 1 stacked event (so both groups
share the same precondition of "survived long enough to hit a stacked event"),
and then you compare players who participated in 2 or more against those who
participated in exactly 1, looking at whether either group shows activity 30
days after their last stacked event ended. Also watch for right censoring: if
a player's last stacked event ended fewer than 45 days before REFERENCE_DATE,
there isn't yet a full observation window to determine "is the player still
active 30 days later," so these not-yet-observable players must be filtered
out — otherwise they would artificially drag down the retention rate for both
groups.

**SQL**

```sql
WITH stacked_exposure AS (
    SELECT
        ep.player_id,
        COUNT(*) AS stacked_count,
        MAX(loe.end_date) AS last_stacked_end
    FROM event_participation ep
    JOIN live_ops_event loe ON loe.id = ep.live_ops_event_id
    WHERE loe.is_stacked_event = 1
    GROUP BY ep.player_id
    HAVING COUNT(*) >= 1
)
SELECT
    CASE WHEN se.stacked_count >= 2 THEN 'exposed_2plus_fatigue_eligible' ELSE 'exposed_1_control' END AS cohort,
    COUNT(*) AS player_count,
    SUM(CASE WHEN p.last_active_date >= date(se.last_stacked_end, '+30 days') THEN 1 ELSE 0 END) AS active_30d_later,
    ROUND(
        100.0 * SUM(CASE WHEN p.last_active_date >= date(se.last_stacked_end, '+30 days') THEN 1 ELSE 0 END) / COUNT(*),
        1
    ) AS pct_active_30d_later
FROM stacked_exposure se
JOIN player p ON p.id = se.player_id
WHERE date(se.last_stacked_end, '+45 days') <= '2026-06-30'
GROUP BY cohort;
```

**Expected result and business conclusion**

2 rows. The control group that participated in exactly 1 stacked event (about
977 players) shows about 34.5% still active 30 days later; the group that
participated in 2 or more (about 403 players) drops to about 23.6% — a gap of
roughly 11 percentage points. Next step: recommend the Director of Live
Operations raise the minimum gap between any two events on next quarter's
calendar from the occasional 3-4 days seen currently to at least 10 days.
Trading the short-term order-value lift confirmed in Query 7 for an 11
percentage-point retention loss is very likely not a good trade.

---

## Query 9: Paid price as a percent of list price, by payment channel

**Business context**

The first-pass material escalated from Trust & Safety suggests "some players
appear to be buying Aether Shards through unofficial channels at noticeably
below-market prices." Before chasing down who's involved, you need to confirm
with data how much lower the actual paid price is relative to official list
price, broken down by payment channel. Maps to Q4 in the business context
document.

**Tags**: Join + Aggregation | Basic | Senior Game Economy Analyst

**Approach**

`iap_transaction` already stores both `list_price_usd` (the official list price
converted for the player's region) and `paid_price_usd` (the actual amount
received), so you just need to group by channel type and authorization status
and average the ratio `paid_price_usd / list_price_usd` — no extra subquery
needed.

**SQL**

```sql
SELECT
    cp.channel_type,
    cp.is_authorized,
    COUNT(*) AS tx_count,
    ROUND(100.0 * AVG(t.paid_price_usd / t.list_price_usd), 1) AS avg_paid_pct_of_list
FROM iap_transaction t
JOIN channel_partner cp ON cp.id = t.channel_partner_id
GROUP BY cp.channel_type, cp.is_authorized
ORDER BY avg_paid_pct_of_list;
```

**Expected result and business conclusion**

4 rows. Unauthorized third-party top-up resellers (`third_party_agent`,
`is_authorized=false`) average paid prices at only about 71.4% of official list
price; the official app store, official web store, and officially authorized
regional billing partners all sit around 106%-110% of list price (slightly
above 100% because premium-priced transactions during stacked events pull the
average up — see Query 7). Next step: 71.4% is essentially the answer to "how
does an unauthorized reseller make money" — they buy in bulk from low-price
regions at roughly 30% below official price, then resell to players in other
regions, pocketing the spread, while the company loses out on the payment
processing cut it would normally earn through official channels.

---

## Query 10: Refund/chargeback incidence rate by payment channel

**Business context**

Underpricing is only half of the top-up-reseller problem — the Trust & Safety
Lead is more concerned with whether transactions from these channels also
trigger a disproportionate share of refunds or chargebacks afterward, since
chargebacks saddle the company with extra bank fees and reputation damage.

**Tags**: Join + Aggregation | Intermediate | Senior Game Economy Analyst

**Approach**

You must `LEFT JOIN` `refund_chargeback_risk_event` onto `iap_transaction`
here, not `INNER JOIN` — the vast majority of transactions never trigger any
risk event at all, and an `INNER JOIN` would drop all those "clean"
transactions, severely understating the denominator (`tx_count`) and inflating
the calculated risk rate by several times. Both numerator and denominator
should use `COUNT(DISTINCT ...)`, because in principle a single transaction
could map to more than one risk record (though in this dataset it's capped at
one per transaction) — `DISTINCT` is the safer default.

**SQL**

```sql
SELECT
    cp.channel_name,
    cp.is_authorized,
    COUNT(DISTINCT t.id) AS tx_count,
    COUNT(DISTINCT r.id) AS risk_events,
    ROUND(100.0 * COUNT(DISTINCT r.id) / COUNT(DISTINCT t.id), 1) AS risk_rate_pct
FROM iap_transaction t
JOIN channel_partner cp ON cp.id = t.channel_partner_id
LEFT JOIN refund_chargeback_risk_event r ON r.iap_transaction_id = t.id
GROUP BY cp.id
ORDER BY risk_rate_pct DESC;
```

**Expected result and business conclusion**

10 rows, one per payment channel. The 5 unauthorized top-up-reseller channels
sit in roughly the 17%-23% risk-rate range (combined across all 5 it's about
20.5%), far above the official app store (also output per channel — Apple and
Google each fall around 2.0%-2.4%) and the official web store (about 2.7%).
Watch the grain here: this query's `GROUP BY cp.id` outputs one row per
channel, so the 2 officially authorized regional billing partners each get
their own row (SEA Regional Billing Partner at about 6.1%, LatAm Regional
Billing Partner at about 2.0%), rather than being merged into a single "about
4.2%" row — 4.2% is the combined baseline for these two partners once
aggregated by `is_authorized`; broken out per channel, each partner only has
about 100 transactions, so the risk rate naturally swings around that baseline.
Next step: write "official channels run a 2%-3% baseline risk rate" into the
Trust & Safety monitoring playbook as the internal normal range, and trigger
automatic manual review for any channel whose risk rate exceeds 3x that
baseline (like these 5 unauthorized resellers).

---

## Query 11: Out-of-region redemption rate for discount codes (leaked vs. normal)

**Business context**

The marketing team recently noticed that a handful of discount codes originally
intended only for Southeast Asia / Latin America markets are being redeemed at
an unusually high volume. You need to verify whether these codes have leaked
outside their target region and are being exploited for arbitrage.

**Tags**: Join + Subquery | Intermediate | Senior Game Economy Analyst

**Approach**

A discount code's "target region" is stored in
`discount_code.intended_region_scope` (a full country-name string). A player's
actual billing region requires two joins (`player -> region_price_tier`) to
resolve to a full country name; comparing the two strings with `<>` flags
"out-of-scope redemptions." This concept only applies to region-specific codes
where `intended_region_scope IS NOT NULL` — global email-marketing codes or
influencer codes need to be filtered out with `WHERE` first, otherwise they'd
be wrongly flagged as "entirely out of scope" (because `NULL <> anything`
evaluates to `NULL` in SQL, so they wouldn't actually get counted by the `SUM`
`CASE WHEN` branch, but they also shouldn't be part of this analysis to begin
with — it's cleaner to exclude them up front).

**SQL**

```sql
SELECT
    dc.leaked_beyond_scope,
    COUNT(*) AS redemptions,
    SUM(CASE WHEN rpt.country_name <> dc.intended_region_scope THEN 1 ELSE 0 END) AS out_of_scope_count,
    ROUND(100.0 * SUM(CASE WHEN rpt.country_name <> dc.intended_region_scope THEN 1 ELSE 0 END) / COUNT(*), 1) AS out_of_scope_pct
FROM iap_transaction t
JOIN discount_code dc ON dc.id = t.discount_code_id
JOIN player p ON p.id = t.player_id
JOIN region_price_tier rpt ON rpt.id = p.region_price_tier_id
WHERE dc.intended_region_scope IS NOT NULL
GROUP BY dc.leaked_beyond_scope;
```

**Expected result and business conclusion**

2 rows. The 4 confirmed-leaked discount codes (`leaked_beyond_scope=1`) show
about 72.1% of their redemptions happening outside the target region; the
other 15 normal region-specific codes (`leaked_beyond_scope=0`) show an
out-of-region redemption rate of only about 5.7%, consistent with normal
incidental cross-region travel/VPN noise. Next step: deactivate these 4 leaked
codes immediately, and use the same "out-of-scope redemption rate" metric to
audit every currently active region-specific promo code, prioritizing review
of any code above a 15%-20% out-of-scope rate.

---

## Query 12: High-risk transaction detail related to top-up agents / sock-puppet accounts

**Business context**

The Trust & Safety Analyst needs a list of individual transactions they can
review one by one — the board materials need a summary, but actually acting on
this (for example, contacting the issuing bank to dispute a chargeback)
requires drilling down to specific transactions.

**Tags**: Join + Pattern Matching | Intermediate | Trust & Safety Analyst

**Approach**

`refund_chargeback_risk_event.risk_note` is an enumerated field, but you can use
`LIKE` for keyword matching to isolate the two categories related to top-up
agents (`agent`) and sock-puppet account rings (`multi_account`), as opposed to
plain `genuine_dissatisfaction`. This way, even if `risk_note` picks up new,
more granular subcategories in the future (say, `agent_sourced_dispute_v2`),
this query will still catch them as long as the category name still contains
the keyword `agent`, without needing to update an enum value list every time.

**SQL**

```sql
SELECT
    r.id AS risk_event_id,
    p.id AS player_id,
    p.player_segment,
    cp.channel_name,
    t.paid_price_usd,
    r.event_type,
    r.risk_note,
    r.resolution_status
FROM refund_chargeback_risk_event r
JOIN iap_transaction t ON t.id = r.iap_transaction_id
JOIN player p ON p.id = r.player_id
JOIN channel_partner cp ON cp.id = t.channel_partner_id
WHERE r.risk_note LIKE '%agent%' OR r.risk_note LIKE '%multi_account%'
ORDER BY t.paid_price_usd DESC
LIMIT 20;
```

**Expected result and business conclusion**

20 rows, sorted from highest to lowest transaction amount, each one a specific
risky transaction you can cross-check to see whether `channel_name` clusters
around those 5 unauthorized reseller channels, and how many rows still show
`resolution_status = 'pending'`. Next step: flag records that are still
`pending` and involve larger amounts as this week's priority list, and hand
them to the Trust & Safety team to contact the issuing banks and verify each
one individually.

---

## Query 13: Risk rate for account groups sharing a device fingerprint

**Business context**

The Trust & Safety Lead needs to prove to the company that "this isn't just a
handful of individual players having second thoughts about refunds — it's
organized ring activity." The most direct evidence is a cluster of accounts
sharing a single device fingerprint, where that cluster's refund/chargeback
rate is far above normal. Maps to Q5 in the business context document.

**Tags**: CTE + Aggregation | Advanced | Trust & Safety Lead

**Approach**

Start with a CTE that finds every `device_fingerprint_hash` shared by 2 or
more players (`GROUP BY ... HAVING COUNT(*) >= 2`) — this step is itself the
"ring detection" logic. Then left-join this CTE against the full player table
to split players into a "ring member" group and a "unique device" group, and
compute the risk-event rate for each. Again, use `LEFT JOIN`, not `INNER JOIN`
(same reasoning as Query 10), and be especially careful with
`COUNT(DISTINCT ...)` — a single player can have multiple transactions and
multiple risk records, and a plain `COUNT(*)` without `DISTINCT` would count
the Cartesian product of "multiple transactions × multiple risk records,"
severely overstating the risk rate.

**SQL**

```sql
WITH device_groups AS (
    SELECT device_fingerprint_hash, COUNT(*) AS ring_size
    FROM player
    GROUP BY device_fingerprint_hash
    HAVING COUNT(*) >= 2
)
SELECT
    CASE WHEN dg.ring_size IS NOT NULL THEN 'shared_device_ring' ELSE 'unique_device' END AS cohort,
    COUNT(DISTINCT p.id) AS player_count,
    COUNT(DISTINCT t.id) AS tx_count,
    COUNT(DISTINCT r.id) AS risk_events,
    ROUND(100.0 * COUNT(DISTINCT r.id) / NULLIF(COUNT(DISTINCT t.id), 0), 1) AS risk_rate_pct
FROM player p
LEFT JOIN device_groups dg ON dg.device_fingerprint_hash = p.device_fingerprint_hash
LEFT JOIN iap_transaction t ON t.player_id = p.id
LEFT JOIN refund_chargeback_risk_event r ON r.iap_transaction_id = t.id
GROUP BY cohort;
```

**Expected result and business conclusion**

2 rows. Players sharing a device fingerprint as part of a ring (10 groups, 48
players total) show a risk-event rate of about 47.4%, roughly 19x the baseline
for players on unique devices (about 2.5%). Next step: a nearly 19x gap like
this is more than enough for the Trust & Safety Lead to bring a formal proposal
to legal and the risk committee for a batch ban plus dispute-recovery action,
rather than handling accounts one at a time.

---

## Query 14: Roster of suspected fraud ring members

**Business context**

Query 13 proved that "rings" as a whole show an abnormal risk rate, but actually
executing a ban requires a specific per-account roster for the Trust & Safety
Lead to review and act on one by one.

**Tags**: Subquery | Basic | Trust & Safety Lead

**Approach**

Use a subquery to first find every `device_fingerprint_hash` value shared by 2
or more accounts, then filter the `player` table down to just those ring
members with `WHERE device_fingerprint_hash IN (...)`, grouping and sorting by
fingerprint so it's easy to review one ring at a time.

**SQL**

```sql
SELECT
    p.id AS player_id,
    p.device_fingerprint_hash,
    p.install_date,
    p.player_segment,
    p.lifetime_spend_usd,
    p.churn_risk_score
FROM player p
WHERE p.device_fingerprint_hash IN (
    SELECT device_fingerprint_hash FROM player GROUP BY device_fingerprint_hash HAVING COUNT(*) >= 2
)
ORDER BY p.device_fingerprint_hash, p.id;
```

**Expected result and business conclusion**

48 rows, split across 10 device-fingerprint groups of 4-5 accounts each. Most of
these accounts are `non_payer` (zero lifetime spend); only a small handful have
actually paid, showing up as `minnow` or `dolphin`. This is a textbook
sock-puppet ring shape: **a large number of never-activated, dormant sock
accounts alongside a small number of paying "operator" accounts.** The paying
accounts are the ones actually generating refunds/chargebacks (running a
buy-then-refund arbitrage play); the mass of dormant accounts are simply
standby sock puppets, ready to be promoted the moment an operator account gets
banned. So when reviewing this list, don't just look at whether
`lifetime_spend_usd` is high — sharing a device fingerprint is itself the ring
signal. Next step: hand this to the Trust & Safety Lead for a group-by-group
ban (paying accounts and dormant accounts together), and freeze any pending
refund requests in the meantime.

---

## Query 15: Monthly revenue trend with 3-month moving average

**Business context**

The CFO wants a revenue trend chart for the board materials. Raw monthly
revenue is fairly noisy (driven by event scheduling), and she wants a smoother
trend line to judge the overall direction.

**Tags**: Window Function + Date/Time | Intermediate | CFO

**Approach**

First use a CTE to aggregate transactions into monthly revenue, then compute a
3-month moving average with
`AVG() OVER (ORDER BY year_month ROWS BETWEEN 2 PRECEDING AND CURRENT ROW)` —
you need to aggregate first and window second; windowing directly over
transaction-level detail would produce a moving average with no meaningful
grain.

**SQL**

```sql
WITH monthly AS (
    SELECT
        strftime('%Y-%m', transaction_date) AS year_month,
        SUM(paid_price_usd) AS revenue
    FROM iap_transaction
    GROUP BY year_month
)
SELECT
    year_month,
    ROUND(revenue, 2) AS revenue_usd,
    ROUND(AVG(revenue) OVER (ORDER BY year_month ROWS BETWEEN 2 PRECEDING AND CURRENT ROW), 2) AS moving_avg_3mo_usd
FROM monthly
ORDER BY year_month;
```

**Expected result and business conclusion**

Roughly 18 rows (covering 2025-01 through 2026-06). April 2025 shows a clear
**early revenue spike** (about $24,570), coinciding with the Ember Queen
Rate-Up Banner limited event window; but note this is just a **local high**
during the game's first few months post-launch, not the all-time monthly peak —
as the user base grows, monthly revenue in 2026 runs generally higher. The
3-month moving average smooths out this early spike and reveals an overall
upward revenue trend across the year. Next step: put this moving-average trend
chart in the "overall health" section of the board materials, and keep the raw
monthly numbers in an appendix for anyone who wants to dig into individual
event effects.

---

## Query 16: Support ticket category distribution and SLA performance

**Business context**

The Player Support Manager reviews the ticket dashboard weekly to see which
issue categories are piling up and which ones have the worst resolution times,
in order to decide where to shift next week's support staffing.

**Tags**: Aggregation | Basic | Player Support Manager

**Approach**

A straightforward `GROUP BY category`, computing average resolution time, the
count of high-priority tickets, and average satisfaction score all together —
looking at these three metrics side by side tells you whether "this category
has a lot of tickets" and "this category is handled poorly" are actually the
same problem or two different ones.

**SQL**

```sql
SELECT
    category,
    COUNT(*) AS ticket_count,
    ROUND(AVG(resolution_time_hours), 1) AS avg_resolution_hours,
    SUM(CASE WHEN priority = 'high' THEN 1 ELSE 0 END) AS high_priority_count,
    ROUND(AVG(csat_score), 2) AS avg_csat
FROM support_ticket
GROUP BY category
ORDER BY ticket_count DESC;
```

**Expected result and business conclusion**

5 rows. `general_bug` has the highest ticket count but skews low priority;
`billing_dispute` and `gacha_odds_complaint` (probability complaints) don't
have the highest volume, but are worth watching closely alongside the Query 4
findings — if `gacha_odds_complaint` tickets cluster during the active windows
of the Ember Queen / Frostbound Knight / Anniversary limited pools, that's
evidence the problem uncovered in Query 4 is already surfacing on the support
side. Next step: recommend the support team tag `gacha_odds_complaint` tickets
by pool as a separate metric, providing an independent corroborating source
for the Query 4 findings.

---

## Query 17: 30-day retention curve by install-month cohort

**Business context**

The Senior Game Economy Analyst (that's you, in a future quarter's standard
report) needs a baseline retention curve as a reference point for every
downstream retention analysis (including Query 8) — without knowing what
"normal" retention looks like, there's no way to judge whether the 11
percentage-point gap caused by stacked events is a big deal or a small one.

**Tags**: CTE + Date/Time | Intermediate | Senior Game Economy Analyst

**Approach**

Bucket players into install-month cohorts using
`strftime('%Y-%m', install_date)`, and use
`julianday(last_active_date) - julianday(install_date) >= 30` to determine
whether a player "survived 30 days" (i.e., their last recorded activity is at
least 30 days after their install date). `WHERE install_date <= '2026-05-31'`
excludes recently installed players who haven't yet had a full 30 days —
otherwise these players would get wrongly counted as "not retained," dragging
down the retention rate for the most recent months. With `REFERENCE_DATE` at
`2026-06-30`, the cutoff needs to be exactly `2026-05-31` to guarantee a full
30-day observation window (May 31 + 30 days = June 30, exactly enough) — one
day earlier would needlessly exclude a day's worth of legitimately observable
installs.

**SQL**

```sql
WITH cohort AS (
    SELECT id, strftime('%Y-%m', install_date) AS install_month, install_date, last_active_date
    FROM player
    WHERE install_date <= '2026-05-31'
)
SELECT
    install_month,
    COUNT(*) AS installs,
    SUM(CASE WHEN julianday(last_active_date) - julianday(install_date) >= 30 THEN 1 ELSE 0 END) AS retained_30d,
    ROUND(
        100.0 * SUM(CASE WHEN julianday(last_active_date) - julianday(install_date) >= 30 THEN 1 ELSE 0 END) / COUNT(*),
        1
    ) AS retention_30d_pct
FROM cohort
GROUP BY install_month
ORDER BY install_month;
```

**Expected result and business conclusion**

About 17 rows (one per install month). The overall 30-day retention rate
fluctuates roughly between 29% and 55%, which serves as the game's "normal"
retention baseline. Next step: use this baseline as the reference point for the
Query 8 conclusion — the fatigue-exposed cohort dropping from the control
group's 34.5% to 23.6% is actually below the normal level even for "players who
had already made it to at least one event and were therefore more engaged,"
confirming the fatigue effect is real rather than data noise.

---

## Query 18: Acquisition channel quality comparison

**Business context**

Marketing needs to reallocate the user acquisition (UA) budget next quarter,
and the Senior Game Economy Analyst needs to determine which acquisition
channel actually brings in players who go on to spend money, rather than just
looking at install volume.

**Tags**: Join + Aggregation | Intermediate | Senior Game Economy Analyst

**Approach**

`player.acquisition_channel` is already an attribute on each player, so install
counts don't require any extra `JOIN`; to compute revenue per install, sum the
pre-computed snapshot field `lifetime_spend_usd` by channel. Payer conversion
rate is computed with a `CASE WHEN player_segment != 'non_payer'` conditional
count, with no need to join `iap_transaction`.

**SQL**

```sql
SELECT
    p.acquisition_channel,
    COUNT(DISTINCT p.id) AS installs,
    COUNT(DISTINCT CASE WHEN p.player_segment != 'non_payer' THEN p.id END) AS paying_players,
    ROUND(
        100.0 * COUNT(DISTINCT CASE WHEN p.player_segment != 'non_payer' THEN p.id END) / COUNT(DISTINCT p.id),
        2
    ) AS payer_conversion_pct,
    ROUND(SUM(p.lifetime_spend_usd) / COUNT(DISTINCT p.id), 2) AS avg_revenue_per_install_usd
FROM player p
GROUP BY p.acquisition_channel
ORDER BY avg_revenue_per_install_usd DESC;
```

**Expected result and business conclusion**

7 rows, one per acquisition channel (Organic - App Store Search / Organic -
Word of Mouth / Meta Ads UA / TikTok Ads UA / Google UAC / AppLovin Network /
Influencer Partnership). Since payer tier is assigned independently at random
(with no deliberate correlation to acquisition channel), conversion rate and
revenue per install should come out roughly similar across channels, varying
only within normal sampling noise. Next step: if any channel shows a
noticeably higher install share but a noticeably lower
`avg_revenue_per_install_usd`, that's a signal marketing may want to trim
budget for that channel — but they should confirm the pattern over a longer
time window first, to avoid a single-quarter noise-driven misjudgment.

---

## Query 19: Revenue by billing region and share from arbitrage regions

**Business context**

The CFO wants to see the company's revenue geography, and in particular how
much of the revenue pie comes from the "arbitrage hotspot" regions (Turkey,
Argentina, and similar) — this determines how much impact any official pricing
adjustment in those regions would have.

**Tags**: Join + Aggregation | Basic | CFO

**Approach**

Starting from `region_price_tier`, `LEFT JOIN` down through `player` and
`iap_transaction` (both joins need to be `LEFT JOIN`, to preserve regions with
zero transactions), and aggregate revenue and player count by region.

**SQL**

```sql
SELECT
    rpt.country_name,
    rpt.is_arbitrage_source_region,
    COUNT(DISTINCT p.id) AS player_count,
    ROUND(COALESCE(SUM(t.paid_price_usd), 0), 2) AS total_revenue_usd
FROM region_price_tier rpt
LEFT JOIN player p ON p.region_price_tier_id = rpt.id
LEFT JOIN iap_transaction t ON t.player_id = p.id
GROUP BY rpt.id
ORDER BY total_revenue_usd DESC;
```

**Expected result and business conclusion**

10 rows, one per billing region. Non-arbitrage regions like the United States
and Canada together account for the bulk of revenue; the 6 arbitrage-hotspot
regions (Brazil, Turkey, Argentina, the Philippines, India, Indonesia)
together contribute a relatively smaller revenue share, but not a small share
of player count — this is exactly the economic foundation of the top-up
reseller supply chain: these regions have plenty of players but low official
prices, creating a natural price gap to exploit. Next step: include this as
background data alongside the Query 9 / Query 10 findings in the board
materials, to help non-operations board members understand why the top-up
reseller problem shows up specifically in these regions.

---

## Query 20: Combined scorecard for the five traps

**Business context**

The VP of Monetization & Publishing wants a scorecard on the first page of the
board materials that condenses the most important numbers from the previous 19
queries into 4 rows, with the details unpacked on later pages.

**Tags**: CTE + Subquery | Advanced | VP of Monetization & Publishing

**Approach**

Reuse the core logic of earlier queries in 4 independent CTEs (whale revenue
share from Query 1, the worst limited-pool gap from Query 4, the unauthorized
reseller channel risk rate from Query 10, and the fraud-ring risk rate from
Query 13), with each CTE returning a single scalar value, then stitch the 4
single values together into one vertical scorecard using `UNION ALL`. The
advantage of this structure is that each metric's calculation logic is
independently testable and won't interfere with the others by being crammed
into one giant query.

**SQL**

```sql
WITH whale_share AS (
    SELECT ROUND(
        100.0 * SUM(CASE WHEN p.player_segment = 'whale' THEN t.paid_price_usd ELSE 0 END) / SUM(t.paid_price_usd),
        1
    ) AS metric_value
    FROM iap_transaction t
    JOIN player p ON p.id = t.player_id
),
gacha_worst_gap AS (
    SELECT ROUND(MIN(actual_pct - disclosed_pct), 2) AS metric_value
    FROM (
        SELECT
            gp.disclosed_legendary_prob_pct AS disclosed_pct,
            100.0 * SUM(CASE WHEN gpl.result_rarity = 'Legendary' THEN 1 ELSE 0 END) / COUNT(gpl.id) AS actual_pct
        FROM gacha_pool gp
        JOIN gacha_pull_log gpl ON gpl.gacha_pool_id = gp.id
        WHERE gp.pool_type = 'limited_rateup'
        GROUP BY gp.id
    )
),
agent_risk_rate AS (
    SELECT ROUND(100.0 * COUNT(DISTINCT r.id) / COUNT(DISTINCT t.id), 1) AS metric_value
    FROM iap_transaction t
    JOIN channel_partner cp ON cp.id = t.channel_partner_id
    LEFT JOIN refund_chargeback_risk_event r ON r.iap_transaction_id = t.id
    WHERE cp.is_authorized = 0
),
fraud_ring_risk_rate AS (
    SELECT ROUND(100.0 * COUNT(DISTINCT r.id) / COUNT(DISTINCT t.id), 1) AS metric_value
    FROM player p
    JOIN iap_transaction t ON t.player_id = p.id
    LEFT JOIN refund_chargeback_risk_event r ON r.iap_transaction_id = t.id
    WHERE p.device_fingerprint_hash IN (
        SELECT device_fingerprint_hash FROM player GROUP BY device_fingerprint_hash HAVING COUNT(*) >= 2
    )
)
SELECT 'Q1 巨鲸(前1%)收入占比(%)' AS trap_metric, metric_value FROM whale_share
UNION ALL
SELECT 'Q2 最差限定池概率缺口(pp)', metric_value FROM gacha_worst_gap
UNION ALL
SELECT 'Q4 未授权代充渠道风险事件率(%)', metric_value FROM agent_risk_rate
UNION ALL
SELECT 'Q5 设备指纹团伙风险事件率(%)', metric_value FROM fraud_ring_risk_rate;
```

**Expected result and business conclusion**

4 rows, at a glance: whale revenue share about 65.8%; worst limited-pool
probability gap about -2.25 percentage points; unauthorized reseller channel
risk-event rate about 20.5%; device-fingerprint ring risk-event rate about
47.4%. Next step: these 4 numbers are the core takeaway for page one of the
board materials, each paired with a one-line "recommended action" (dedicated
retention for whales / pool-probability remediation / reseller-channel
crackdown / fraud-ring account bans), with the following pages expanding into
each area's full analysis (the complete results from Query 1, 4, 10, and 13,
respectively).

## Business question to query mapping

| Business question | Corresponding queries |
|----------|----------|
| Q1 Whale dependency | Query 1, Query 2, Query 3, Query 20 |
| Q2 Gacha probability disclosure gap | Query 4, Query 5, Query 20 |
| Q3 Live-Ops event false prosperity | Query 6, Query 7, Query 8, Query 17 |
| Q4 Top-up reseller / discount channel arbitrage | Query 9, Query 10, Query 11, Query 12, Query 19, Query 20 |
| Q5 Refund fraud rings | Query 12, Query 13, Query 14, Query 20 |
| Operational monitoring (not tied to one specific Q, but supports day-to-day review) | Query 15, Query 16, Query 18 |
</content>
