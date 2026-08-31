# Media Industry - Podcast Ad Economics SQL Query Reference

> **Business context / industry primer / glossary / metric formulas:** `01-media_podcast_ad_economics_high_business_context.md` (recommended reading before you dive into the SQL)
> **Data structure / ER diagram / DDL:** `02-media_podcast_ad_economics_high_er_document.md`
> **Database:** `media_podcast_ad_economics_high.sqlite`
> **SQL dialect:** SQLite 3.x
> **Reference "Today" (REFERENCE_DATE):** 2026-06-21 (every query uses the literal date `'2026-06-21'`, not `DATE('now')`, to guarantee reproducibility)

---

## A Note to the Intern: How to Use This Document

You're a **data analyst intern** on the Revenue Operations team at StreamCast Media. Your mentor tells you: **"These 27 SQL queries are the 'muscle memory' you'll use over and over for the next 3 months. Copy them, modify them, understand the business behind them — and you'll have graduated."**

Each query has **five sections**, **read them in this order**:

1. **Business Context** — **Read this first**! Understand "who's asking the question, why, and what they want to do with the data." Without grasping the business, the SQL is just meaningless characters.
2. **Industry Primer / Category-Difficulty-Role** — Adds industry common sense for non-intuitive metrics, plus labels the SQL category, difficulty, and business role.
3. **Approach** — **Read this before the SQL.** It tells you: which tables to JOIN, the aggregation grain (what one row represents), what pitfalls to avoid (double counting / when to use LEFT JOIN / divide-by-zero / multi-value targeting matches), and why a CTE or window function is used here. Get the plan straight in your head and the SQL stops looking like alphabet soup.
4. **SQL Code** — Actually runnable SQL (SQLite dialect).
5. **Result Interpretation + Business Conclusion** — Once you have the data, which numbers are "healthy" and which are "red alerts," and what action to take next.

> ⚠️ **Important reminder:** The data behind these queries is fake, so specific numeric values won't perfectly match real-world business. **Focus on the methodology, don't memorize the numbers.**

---

## Company Background Quick Recap (3-minute version)

If you've forgotten the background from the ER document, here's a quick refresher:

- **StreamCast Media** is a US podcast ad platform serving 150+ podcast shows
- **How it makes money:** advertisers slot pre-roll/mid-roll/post-roll ads into shows → platform takes 30% → host takes 70%
- **Core mechanism:** every time a listener plays a show, real-time bidding (RTB) is run → second-price clearing (Vickrey auction)
- **Three-party interests:** the platform wants high fill rate and high CPM; advertisers want low CPA and high ROI; hosts want high RPM
- **Core tension:** more ads = more revenue vs. worse listener experience

**Core metrics cheat sheet:**
- **CPM** = cost per mille (the unit price the advertiser pays)
- **RPM** = revenue per mille (the unit price the host nets)
- **Fill Rate** = the ad slot fill rate
- **Completion Rate** = ad completion rate
- **CPA** = cost per acquisition

---

## Index of 27 Queries

Grouped into 6 business themes.

### Theme A: Revenue Optimization

> Audience: platform ops, sales strategy, CFO
> Core question: how do we sell ads for higher total revenue?

| # | Title | Role | Difficulty |
|---|------|------|------|
| 1 | Performance by ad slot type | Platform ops | Intermediate |
| 2 | Peak vs. off-peak fill rate analysis | Platform analyst | Advanced |
| 3 | CPM ranking by high-value listener segments | Platform strategy | Intermediate |
| 4 | Inventory utilization by day of week | Platform ops | Intermediate |
| 5 | Advertiser budget burn alerts | Platform sales | Advanced |
| 6 | Identifying underpriced ad slots | Platform strategy | Advanced |

### Theme B: Advertiser ROI

> Audience: advertisers, account executives (AEs)
> Core question: is the advertiser getting their money's worth?

| # | Title | Role | Difficulty |
|---|------|------|------|
| 7 | Per-campaign ROI dashboard | Advertiser | Intermediate |
| 8 | Creative performance comparison (A/B test) | Advertiser | Advanced |
| 9 | Audience targeting effectiveness | Advertiser | Advanced |
| 10 | Bid amount vs. win rate correlation | Advertiser | Intermediate |
| 11 | Cost per completed view (CPCV) analysis | Advertiser | Intermediate |
| 12 | Competitor bidding behavior insights | Advertiser | Advanced |

### Theme C: Creator Monetization

> Audience: podcast hosts, content partnerships BD
> Core question: how much can the host earn, and how can they earn more?

| # | Title | Role | Difficulty |
|---|------|------|------|
| 13 | RPM benchmarking by show category | Host | Intermediate |
| 14 | Per-episode deep dive | Host | Intermediate |
| 15 | Host monthly revenue trend | Host | Advanced |
| 16 | Content optimization (length / publish day) | Host | Advanced |

### Theme D: Listener Experience

> Audience: platform UX team, retention team
> Core question: don't drive the listeners away!

| # | Title | Role | Difficulty |
|---|------|------|------|
| 17 | Ad fatigue detection | Platform UX | Advanced |
| 18 | Skip rate analysis by creative attributes | Platform UX | Intermediate |
| 19 | Optimal ad frequency recommendation | Platform UX | Advanced |
| 20 | Listener segment satisfaction scoring | Platform UX | Advanced |

### Theme E: Auction Dynamics

> Audience: platform auction system, pricing strategy team
> Core question: is the auction mechanism running healthy?

| # | Title | Role | Difficulty |
|---|------|------|------|
| 21 | Auction competition intensity heatmap | Platform analyst | Advanced |
| 22 | Second-price auction efficiency validation | Platform analyst | Intermediate |
| 23 | Budget pacing effectiveness | Platform analyst | Advanced |
| 24 | Bid elasticity analysis | Platform analyst | Advanced |

### Theme F: Strategic Insights

> Audience: platform leadership, strategy team
> Core question: where do we bet next quarter?

| # | Title | Role | Difficulty |
|---|------|------|------|
| 25 | Emerging advertiser industry trends | Platform strategy | Intermediate |
| 26 | Show category growth forecast | Platform strategy | Advanced |
| 27 | Listener behavior shift detection | Platform strategy | Advanced |

---

# Query Body

---

## Query 1: Performance by Ad Slot Type

**Business context:**
StreamCast's VP of Monetization needs supporting data for Q2 pricing strategy. **The industry "consensus"** is that mid-roll is the most valuable slot (highest completion rate → advertisers want it more), so the base CPM is set at 1.67× pre-roll ($25 vs $15). But the VP suspects the actual market values mid-roll even higher than the official price — that is, **is the floor set too low?** This query compares pre/mid/post-roll across actual clearing price, completion rate, and skip rate, and uses data to answer that pricing question.

**Industry knowledge:**
- **Base CPM:** the platform's "minimum opening bid" for each slot type; advertisers cannot bid below this
- **Actual clearing price (eCPM, effective CPM):** the real average selling price after the auction completes
- If **eCPM significantly > Base CPM**, the market is willing to pay well above the floor, and **the platform is leaving money on the table** (= time to raise the floor)

**Category:** Revenue Optimization
**Difficulty:** Intermediate
**Business role:** Platform ops

**Approach:**
Hit three tables: `ad_slot_template → episode_ad_slot → ad_impression`, aggregate by slot template. INNER JOIN is fine here because we only care about "impressions that actually cleared" (unsold slots are out of scope). Remember `ad_impression` is an **event-level table** — one row = one impression — so `COUNT/AVG` aggregate at the "impression" grain; `GROUP BY` on slot template rolls pre/mid/post each into one row. Use `SUM(CASE WHEN boolean THEN 1 ELSE 0 END) / COUNT(*)` to compute completion and skip rates. No CTE or window function needed — a single `GROUP BY` does the job. The analysis is about comparing `avg_realized_cpm` (actual clearing price) against `base_cpm_rate` (the floor).

```sql
-- Compare actual market performance of the 3 ad slot types
SELECT
    ast.slot_type,
    ast.slot_name,
    ast.base_cpm_rate AS current_base_cpm,
    COUNT(ai.id) AS total_impressions,
    ROUND(AVG(ai.actual_charge_cpm), 2) AS avg_realized_cpm,
    ROUND(AVG(ai.winning_bid_cpm), 2) AS avg_winning_bid,
    ROUND(100.0 * SUM(CASE WHEN ai.was_completed THEN 1 ELSE 0 END) / COUNT(ai.id), 1) AS completion_rate_pct,
    ROUND(100.0 * SUM(CASE WHEN ai.was_skipped THEN 1 ELSE 0 END) / COUNT(ai.id), 1) AS skip_rate_pct,
    ROUND(AVG(ai.ad_duration_played_sec), 1) AS avg_duration_played_sec,
    ROUND(SUM(ai.actual_charge_cpm / 1000.0), 2) AS total_revenue_usd
FROM ad_slot_template ast
JOIN episode_ad_slot eas ON ast.id = eas.slot_template_id
JOIN ad_impression ai ON eas.id = ai.ad_slot_id
GROUP BY ast.id, ast.slot_type, ast.slot_name, ast.base_cpm_rate
ORDER BY avg_realized_cpm DESC;
```

**Result interpretation:**
Returns 3 rows (one per slot type). **Expected pattern (actual magnitudes in this dataset):**
- **Mid-roll** eCPM ~$31-34 (about +25-35% over the $25 floor), high completion → confirms "mid-roll is the most expensive" and clearly has pricing headroom
- **Pre-roll** eCPM ~$18-20, relatively high completion → slightly above the $15 floor, stable performer
- **Post-roll** eCPM ~$9-10, lowest completion → low reach, sits close to the $8 floor

**How to brief the business:** "Mid-roll clears about 30% above the floor; recommend raising the floor from $25 to roughly $30 to lift overall revenue. Post-roll is sitting near floor and performing as expected — leave it alone."

---

## Query 2: Peak vs. Off-Peak Fill Rate Analysis

**Business context:**
The ops manager has noticed that **a lot of overnight / late-night ad slots are going unsold** (low fill rate), meaning **wasted inventory = lost revenue**. At the same time, advertisers constantly complain that daytime peak CPMs are too high to win. She wants to know: **can we use "dynamic pricing" — drop the CPM floor overnight and attract mid-tier and small advertisers to fill the gap?** This query slices fill rate across all 24 hours and identifies the potential revenue upside in off-peak hours.

**Industry knowledge:**
- **Fill Rate** = ads actually sold ÷ available ad slots
- A healthy fill rate is ≥ 90%. Anything under 70% means significant inventory waste
- **Dynamic pricing** is a core strategy on Google AdSense and Meta's ad platform — high prices at peak, discounts off-peak

**Category:** Revenue Optimization
**Difficulty:** Advanced
**Business role:** Platform analyst

**Approach:**
We need to compute "of the slots that were reached, how many cleared" — denominator and numerator need to be built separately. First JOIN `play_session → podcast_episode → episode_ad_slot` to get "session × slot pairs" as the **denominator** (one row per slot reached by listening), then `LEFT JOIN ad_impression` (with the `ai.play_session_id = ps.id` condition) as the **numerator**. **Here LEFT JOIN cannot be swapped for INNER JOIN**, or the unsold slots would be dropped and fill rate would always be 100%. The CTE `hourly_potential` aggregates by hour (`strftime('%H', ...)`); the outer query layers on demand_tier bands and an estimate of "how much we'd gain by lifting fill rate to 90%." Grain = one row per hour, 24 rows total.

```sql
-- Analyze fill rate and revenue by hour of day, identifying off-peak opportunities
WITH hourly_potential AS (
    SELECT
        CAST(strftime('%H', ps.session_start_time) AS INTEGER) AS hour_of_day,
        -- Denominator is "session-slot pairs" (one row per slot reached by listening), NOT distinct slot definitions,
        -- otherwise one slot played by N sessions would push fill_rate way above 100%.
        COUNT(eas.id) AS total_slots_available,
        COUNT(ai.id) AS slots_filled,
        ROUND(100.0 * COUNT(ai.id) / COUNT(eas.id), 1) AS fill_rate_pct,
        ROUND(AVG(ai.actual_charge_cpm), 2) AS avg_cpm,
        ROUND(SUM(ai.actual_charge_cpm / 1000.0), 2) AS revenue_generated
    FROM play_session ps
    JOIN podcast_episode pe ON ps.episode_id = pe.id
    JOIN episode_ad_slot eas ON pe.id = eas.episode_id
    LEFT JOIN ad_impression ai ON eas.id = ai.ad_slot_id
        AND ai.play_session_id = ps.id
    GROUP BY hour_of_day
)
SELECT
    hour_of_day,
    total_slots_available,
    slots_filled,
    (total_slots_available - slots_filled) AS unfilled_slots,
    fill_rate_pct,
    avg_cpm,
    revenue_generated,
    CASE
        WHEN fill_rate_pct < 70 THEN 'Off-Peak (low fill)'
        WHEN fill_rate_pct >= 70 AND fill_rate_pct < 85 THEN 'Moderate'
        ELSE 'Peak (high demand)'
    END AS demand_tier,
    -- Estimate: how much more revenue if fill rate were lifted to 90%
    ROUND((total_slots_available * 0.90 - slots_filled) * (avg_cpm / 1000.0), 2) AS potential_revenue_gain
FROM hourly_potential
ORDER BY hour_of_day;
```

**Result interpretation:**
Returns 24 rows. The fill_rate here is "**of the slots that were reached, what share actually had an ad clear**" (denominator is session-slot pairs, so it's always ≤ 100%):
- **Peak hours** (7-9 AM commute, 12-1 PM lunch, 6-10 PM evening) → relatively high fill rate, higher CPM as well
- **Off-peak hours** (1-5 AM) → lower fill rate, more empty inventory
- `potential_revenue_gain` is **the most important column** — it estimates the extra revenue if off-peak fill rate were lifted to 90%
- ⚠️ Note: many mid/post-rolls are never reached because the listener didn't get that far, so overall fill rate won't appear full — this is exactly the "play progress drives inventory" effect

**Business recommendation:** "Recommend cutting CPM floors by 20-30% between 1-5 AM to attract budget-sensitive e-commerce advertisers. Estimated monthly upside $XX,XXX."

---

## Query 3: CPM Ranking by High-Value Listener Segments

**Business context:**
The sales director is preparing a Q2 pitch deck for SaaS and FinTech advertisers. He needs data to prove: **"Our platform's Tech_Enthusiast listener segment is genuinely valuable"** — not just talk. This query sorts CPM by listener segment and uses data to tell advertisers "if you want this high-quality audience, you'll need to pay more."

**Industry knowledge:**
- **Listener Segment:** an interest tag the platform assigns to listeners based on listening history (e.g., Tech_Enthusiast / Health_Conscious)
- **Premium Audience:** these audiences have strong purchasing power and high conversion rates, so advertisers will pay more for them
- **Programmatic Guaranteed (PG):** a "guaranteed-volume targeted audience" deal directly signed between the platform and major advertisers — doesn't go through the open auction, fixed price

**Category:** Revenue Optimization
**Difficulty:** Intermediate
**Business role:** Platform strategy

**Approach:**
Chain `listener_segment → listener → play_session → ad_impression`, aggregate by `segment_name`. **Be aware of one pitfall**: a single listener can belong to 1-3 segments, so after the JOIN the same impression will be counted once under each of its segments — this is **intentional** (we're measuring "what is this audience type's advertising worth?") but it means `total_impressions` is a count at the segment grain, not a deduplicated impression count. Listener count uses `COUNT(DISTINCT l.id)` so it's not inflated by segment count. `HAVING total_impressions >= 100` filters out tiny-sample segments; `ORDER BY avg_cpm DESC` ranks the most valuable audiences.

```sql
-- Rank the most monetizable audiences by listener segment
SELECT
    ls.segment_name,
    COUNT(DISTINCT l.id) AS listener_count,
    COUNT(ai.id) AS total_impressions,
    ROUND(AVG(ai.actual_charge_cpm), 2) AS avg_cpm,
    ROUND(AVG(ai.winning_bid_cpm), 2) AS avg_winning_bid,
    ROUND(100.0 * SUM(CASE WHEN ai.was_completed THEN 1 ELSE 0 END) / COUNT(ai.id), 1) AS completion_rate_pct,
    ROUND(SUM(ai.actual_charge_cpm / 1000.0), 2) AS total_revenue_generated,
    ROUND(SUM(ai.actual_charge_cpm / 1000.0) / COUNT(DISTINCT l.id), 2) AS revenue_per_listener
FROM listener_segment ls
JOIN listener l ON ls.listener_id = l.id
JOIN play_session ps ON l.id = ps.listener_id
JOIN ad_impression ai ON ps.id = ai.play_session_id
GROUP BY ls.segment_name
HAVING total_impressions >= 100  -- at least 100 impressions for statistical significance
ORDER BY avg_cpm DESC
LIMIT 15;
```

**Result interpretation:**
- **Tech_Enthusiast** and **Finance_Savvy** → CPM $25-35 (SaaS/FinTech fight over them)
- **Fitness_Oriented** and **Health_Conscious** → CPM $20-28 (chased by health-consumer brands)
- `revenue_per_listener` tells sales: "every Tech_Enthusiast listener generates $X per year, so the CAC ceiling for acquiring this listener type is $X × retention years"

---

## Query 4: Inventory Utilization by Day of Week

**Business context:**
The inventory planning team wants to figure out: **"why don't advertisers buy on weekends?"** Listeners don't reduce listening on weekends, but fill rate drops noticeably below weekdays (~80% vs 95%). Should we run a weekend promo? This query compares weekdays vs. weekends to inform pricing and sales strategy.

**Industry knowledge:**
- **B2B advertisers** prefer weekday delivery (their targets are business folks, whose minds are "off work" on weekends)
- **Retail / e-commerce** typically buys Monday-Wednesday, since weekend shoppers don't make purchase decisions until Thursday
- **Weekend unsold inventory** is actually an opportunity for DTC (Direct-to-Consumer) brands

**Category:** Revenue Optimization
**Difficulty:** Intermediate
**Business role:** Platform ops

**Approach:**
Structurally identical to Query 2, just swap the grouping dimension from "hour" to "day of week" (`strftime('%w', ...)` returns 0=Sunday). Same trick: `play_session → episode_ad_slot` for "session-slot pairs" as denominator, `LEFT JOIN ad_impression` as numerator, **LEFT JOIN cannot become INNER**. Use `CASE strftime('%w')` to map numbers to English day names for readability, but `GROUP BY` on the numeric `day_num` (string names sort incorrectly). Grain = 7 rows, one per day. Focus is on the weekday vs. weekend fill rate gap.

```sql
-- Analyze fill rate, CPM, and revenue by day of week
SELECT
    CASE CAST(strftime('%w', ps.session_start_time) AS INTEGER)
        WHEN 0 THEN 'Sunday'
        WHEN 1 THEN 'Monday'
        WHEN 2 THEN 'Tuesday'
        WHEN 3 THEN 'Wednesday'
        WHEN 4 THEN 'Thursday'
        WHEN 5 THEN 'Friday'
        WHEN 6 THEN 'Saturday'
    END AS day_of_week,
    CAST(strftime('%w', ps.session_start_time) AS INTEGER) AS day_num,
    -- Same as Query 2: denominator is "session-slot pairs", avoid deduping to slot definitions which causes >100%
    COUNT(eas.id) AS total_slots,
    COUNT(ai.id) AS filled_slots,
    ROUND(100.0 * COUNT(ai.id) / COUNT(eas.id), 1) AS fill_rate_pct,
    ROUND(AVG(ai.actual_charge_cpm), 2) AS avg_cpm,
    ROUND(SUM(ai.actual_charge_cpm / 1000.0), 2) AS total_revenue,
    COUNT(DISTINCT ps.listener_id) AS unique_listeners
FROM play_session ps
JOIN episode_ad_slot eas ON ps.episode_id = eas.episode_id
LEFT JOIN ad_impression ai ON eas.id = ai.ad_slot_id AND ps.id = ai.play_session_id
GROUP BY day_num
ORDER BY day_num;
```

**Result interpretation:**
- Monday-Thursday fill rate 85-95%; weekends 70-80% → weekend inventory waste is clear
- **Recommendation:** offer a 15% CPM discount on Saturdays to attract retail/e-com advertisers "stocking up before weekend promos"

---

## Query 5: Advertiser Budget Burn Alerts

**Business context:**
**An AE's core KPI is renewal rate.** If an advertiser is about to burn through their budget, the AE must proactively reach out **3 days in advance** to discuss renewal/upsize, or the campaign auto-pauses → platform loses revenue + advertiser churns. This query runs every morning and auto-generates the AE's work list.

**Industry knowledge:**
- **Account Manager (AE):** owns renewal and growth for a set of key advertisers
- **Renewal:** existing customer re-signs
- **Upsell:** existing customer adds budget
- **Pacing Burn Rate:** the budget consumption rate, usually computed as "average daily spend"

**Category:** Revenue Optimization
**Difficulty:** Advanced
**Business role:** Platform sales

**Approach:**
Chain `ad_campaign → advertiser`, then `LEFT JOIN ad_creative → ad_impression` to accumulate per-campaign actual spend (`SUM(actual_charge_cpm)/1000`). **The most critical pitfall: use `window_budget_usd`, not `total_budget_usd`** — the latter is an advertiser-level large commitment, and under a 60-day sample, spend is only a few dozen dollars while remaining budget would last tens of thousands of days, causing the whole query to return empty and never alert. The CTE `campaign_spending` first computes spend, daily spend, and remaining budget; the outer query computes `days_until_exhaustion = remaining / daily` and tiers it. `WHERE end_date >= '2026-06-21'` keeps only active campaigns, then filters to those exhausting within 7 days. Grain = one row per campaign.

```sql
-- Identify campaigns about to exhaust budget (risk of pausing within 3 days)
-- Use window_budget_usd (budget actually deployed in this 60-day window, matching real delivery magnitude),
-- NOT total_budget_usd (advertiser-level large commitment) — otherwise per-campaign spend is just a few dozen USD
-- → days_until_exhaustion balloons to tens of thousands of days → nothing ever alerts and the whole query returns empty.
WITH campaign_spending AS (
    SELECT
        ac.id AS campaign_id,
        ac.campaign_name,
        a.company_name,
        a.account_manager_email,
        ac.window_budget_usd,
        ac.end_date,
        ROUND(SUM(ai.actual_charge_cpm / 1000.0), 2) AS spent_to_date,
        ROUND(ac.window_budget_usd - SUM(ai.actual_charge_cpm / 1000.0), 2) AS remaining_budget,
        COUNT(ai.id) AS total_impressions,
        ROUND(COUNT(ai.id) * 1.0 /
            NULLIF((JULIANDAY('2026-06-21') - JULIANDAY(ac.start_date)), 0), 0) AS avg_daily_impressions,
        ROUND(SUM(ai.actual_charge_cpm / 1000.0) /
            NULLIF((JULIANDAY('2026-06-21') - JULIANDAY(ac.start_date)), 0), 2) AS avg_daily_spend
    FROM ad_campaign ac
    JOIN advertiser a ON ac.advertiser_id = a.id
    LEFT JOIN ad_creative acr ON ac.id = acr.campaign_id
    LEFT JOIN ad_impression ai ON acr.id = ai.creative_id
    WHERE ac.end_date >= DATE('2026-06-21')  -- active campaigns only
    GROUP BY ac.id, ac.campaign_name, a.company_name, a.account_manager_email, ac.window_budget_usd, ac.end_date
)
SELECT
    campaign_name,
    company_name,
    account_manager_email,
    window_budget_usd,
    spent_to_date,
    remaining_budget,
    ROUND(100.0 * spent_to_date / window_budget_usd, 1) AS budget_used_pct,
    avg_daily_spend,
    ROUND(remaining_budget / NULLIF(avg_daily_spend, 0), 1) AS days_until_exhaustion,
    CASE
        WHEN remaining_budget / NULLIF(avg_daily_spend, 0) <= 1 THEN 'URGENT: under 1 day'
        WHEN remaining_budget / NULLIF(avg_daily_spend, 0) <= 3 THEN 'HIGH: 1-3 days'
        WHEN remaining_budget / NULLIF(avg_daily_spend, 0) <= 7 THEN 'MEDIUM: 3-7 days'
        ELSE 'LOW: >7 days'
    END AS urgency_level
FROM campaign_spending
WHERE remaining_budget > 0
    AND remaining_budget / NULLIF(avg_daily_spend, 0) <= 7
ORDER BY days_until_exhaustion ASC;
```

**Result interpretation:**
- **URGENT** items need an AE phone call same day, or they'll pause tomorrow
- **HIGH** is the ideal upsell window — the customer has seen the results data but hasn't felt budget pressure yet
- Budget and spend use `window_budget_usd` (budget deployed in this 60-day window), matching actual delivery magnitude, so small absolute values are normal; **focus on `budget_used_pct` and `days_until_exhaustion`**.
- **Sales script (example):** "Your campaign has burned ~90% of its window budget; at the current daily spend it'll run out in 1-2 days. ROI numbers look solid — recommend adding budget now to extend delivery."

---

## Query 6: Identifying Underpriced Ad Slots

**Business context:**
The pricing strategy team suspects certain popular shows have **floor prices set too low**. The logic: if a slot gets 8-10 bidders every time and the winning bid is 2× the floor, the market is more than willing to pay more → raise the floor. This query finds slots with the highest "actual clearing / floor" ratio as candidates for a price hike.

**Industry knowledge:**
- **Pricing Gap:** actual clearing price minus floor. The wider the gap, the more underpriced the floor
- **Bidders per Auction:** more bidders = fiercer competition
- **Floor Price Lift:** raising the floor directly lifts winning bids, because anything below the new floor is auto-eliminated

**Category:** Revenue Optimization
**Difficulty:** Advanced
**Business role:** Platform strategy

**Approach:**
This query has a **double-counting trap**: if impression-level metrics (eCPM, impression count) directly JOIN `ad_auction_log`, they'll be inflated 2-6× by "2-6 bids per impression." So split into two CTEs: `imp_stats` computes eCPM / impression count on the `podcast → ... → ad_impression` chain only (no auction log), `bid_stats` separately computes average bidders per auction on `ad_auction_log`, then the outer query JOINs the two CTEs on `(podcast_id, slot_template_id)`. Grain = show × slot type. `HAVING COUNT(ai.id) >= 50` filters small samples; sort by underpriced amount (`underpriced_pct`) and take the top 20.

```sql
-- Identify ad slots where actual CPM is well above the floor
-- Key: impression-level metrics (imp_stats) don't JOIN auction logs; auction-level metrics (bid_stats) are computed separately,
-- otherwise ad_auction_log's 2-6 rows per impression would inflate total_impressions / missed_revenue by 2-6x.
WITH imp_stats AS (
    SELECT
        p.id AS podcast_id,
        p.podcast_name,
        p.category,
        ast.id AS slot_template_id,
        ast.slot_type,
        ast.base_cpm_rate,
        COUNT(ai.id) AS total_impressions,
        ROUND(AVG(ai.actual_charge_cpm), 2) AS avg_realized_cpm,
        ROUND(AVG(ai.winning_bid_cpm), 2) AS avg_winning_bid
    FROM podcast p
    JOIN podcast_episode pe ON p.id = pe.podcast_id
    JOIN episode_ad_slot eas ON pe.id = eas.episode_id
    JOIN ad_slot_template ast ON eas.slot_template_id = ast.id
    JOIN ad_impression ai ON eas.id = ai.ad_slot_id
    GROUP BY p.id, p.podcast_name, p.category, ast.id, ast.slot_type, ast.base_cpm_rate
    HAVING COUNT(ai.id) >= 50
),
bid_stats AS (
    SELECT
        pe.podcast_id,
        eas.slot_template_id,
        COUNT(aal.id) * 1.0 / COUNT(DISTINCT aal.impression_id) AS avg_bidders_per_auction
    FROM ad_auction_log aal
    JOIN ad_impression ai ON aal.impression_id = ai.id
    JOIN episode_ad_slot eas ON ai.ad_slot_id = eas.id
    JOIN podcast_episode pe ON eas.episode_id = pe.id
    GROUP BY pe.podcast_id, eas.slot_template_id
)
SELECT
    s.podcast_name,
    s.category,
    s.slot_type,
    s.base_cpm_rate AS current_floor,
    s.avg_realized_cpm,
    s.avg_winning_bid,
    ROUND(b.avg_bidders_per_auction, 1) AS avg_bidders_per_auction,
    ROUND((s.avg_realized_cpm - s.base_cpm_rate), 2) AS pricing_gap,
    ROUND(100.0 * (s.avg_realized_cpm - s.base_cpm_rate) / s.base_cpm_rate, 1) AS underpriced_pct,
    ROUND((s.avg_realized_cpm - s.base_cpm_rate) * s.total_impressions / 1000.0, 2) AS missed_revenue_usd,
    CASE
        WHEN s.avg_realized_cpm > s.base_cpm_rate * 1.5 THEN 'SEVERE underprice: raise 30-50%'
        WHEN s.avg_realized_cpm > s.base_cpm_rate * 1.25 THEN 'MODERATE underprice: raise 15-25%'
        WHEN s.avg_realized_cpm > s.base_cpm_rate * 1.1 THEN 'MILD underprice: raise 5-10%'
        ELSE 'Price OK'
    END AS pricing_recommendation
FROM imp_stats s
JOIN bid_stats b ON s.podcast_id = b.podcast_id AND s.slot_template_id = b.slot_template_id
WHERE s.avg_realized_cpm > s.base_cpm_rate * 1.1
ORDER BY underpriced_pct DESC
LIMIT 20;
```

**Result interpretation:**
- Tech mid-roll is usually **the most severely underpriced** (SaaS advertisers go crazy bidding for it)
- Example: "AI Unplugged" mid-roll floor $25, actual clearing $38, 6.5 average bidders → safely raise to $30-32 without losing volume
- `missed_revenue_usd` quantifies the loss: "if we don't raise prices, we lose $XX,XXX per month"

---

## Query 7: Per-Campaign ROI Dashboard

**Business context:**
Advertiser SquareSpace invested $50K into podcast ads, and their marketing director needs to answer the CFO at the monthly review: **"Was this money well spent?"** This query gives a full ROI snapshot for a single campaign at a glance: how much spent / how many people reached / completion rate / estimated conversions / estimated CPA.

**Industry knowledge:**
- **Budget Utilization:** actual spend / total budget. 100% = perfectly burned; > 100% = overspent (won't happen, the platform auto-caps); < 80% = budget can't be deployed (targeting too narrow or bids too low)
- **Estimated Conversion Rate:** industry benchmark — 2% of users who fully listen to an ad will become customers. This is **the industry rule of thumb**
- **Target CPA:** the advertiser's max acceptable cost per acquisition. Below this = positive ROI

**Category:** Advertiser ROI
**Difficulty:** Intermediate
**Business role:** Advertiser

**Approach:**
Chain `ad_campaign → advertiser → ad_creative → ad_impression`, `WHERE` locks to a single campaign name (use a curated name the generator forces in, guaranteeing rows return). Grain = a single-row summary. Use `SUM(CASE WHEN boolean...)` for completion/skip counts; CPCV and estimated CPA can have zero denominators, so wrap in `NULLIF(..., 0)` to prevent divide-by-zero. Budget utilization uses `window_budget_usd`. **Focus on ratio-type metrics** (completion rate, CPCV, estimated CPA vs target_cpa), don't obsess over absolute dollar amounts — under a 60-day sample, a single campaign just doesn't spend that much.

```sql
-- Single-campaign performance dashboard (ROI assessment)
SELECT
    ac.campaign_name,
    a.company_name AS advertiser,
    ac.start_date,
    ac.end_date,
    ac.window_budget_usd,
    ROUND(SUM(ai.actual_charge_cpm / 1000.0), 2) AS total_spent_usd,
    ROUND(100.0 * SUM(ai.actual_charge_cpm / 1000.0) / ac.window_budget_usd, 1) AS budget_utilized_pct,
    COUNT(ai.id) AS total_impressions,
    SUM(CASE WHEN ai.was_completed THEN 1 ELSE 0 END) AS completed_impressions,
    ROUND(100.0 * SUM(CASE WHEN ai.was_completed THEN 1 ELSE 0 END) / COUNT(ai.id), 1) AS completion_rate_pct,
    SUM(CASE WHEN ai.was_skipped THEN 1 ELSE 0 END) AS skipped_impressions,
    ROUND(100.0 * SUM(CASE WHEN ai.was_skipped THEN 1 ELSE 0 END) / COUNT(ai.id), 1) AS skip_rate_pct,
    ROUND(AVG(ai.actual_charge_cpm), 2) AS avg_cpm_paid,
    ROUND(SUM(ai.actual_charge_cpm / 1000.0) / NULLIF(SUM(CASE WHEN ai.was_completed THEN 1 ELSE 0 END), 0), 2) AS cost_per_completed_view,
    -- Estimated conversions (using the 2% completion→conversion benchmark)
    ROUND(SUM(CASE WHEN ai.was_completed THEN 1 ELSE 0 END) * 0.02, 0) AS estimated_conversions,
    ROUND(SUM(ai.actual_charge_cpm / 1000.0) / NULLIF(SUM(CASE WHEN ai.was_completed THEN 1 ELSE 0 END) * 0.02, 0), 2) AS estimated_cpa
FROM ad_campaign ac
JOIN advertiser a ON ac.advertiser_id = a.id
JOIN ad_creative acr ON ac.id = acr.campaign_id
JOIN ad_impression ai ON acr.id = ai.creative_id
WHERE ac.campaign_name = 'SquareSpace - Website Builder Promotion'  -- swap in the actual campaign name
GROUP BY ac.id, ac.campaign_name, a.company_name, ac.start_date, ac.end_date, ac.window_budget_usd;
```

**Result interpretation:**
- Single-row summary. **What to look at:** completion rate (>75% is good) / CPCV (lower is better) / estimated CPA vs target_cpa.
- ⚠️ **Magnitude reminder:** this dataset is a 60-day sample; a single campaign typically delivers only **a few hundred to a few thousand impressions**, with absolute spend in the single to double digits of dollars. `budget_utilized_pct` uses `window_budget_usd` (window-deployed budget), so it'll land in a meaningful range; still, **focus on ratio metrics (completion rate / CPCV / CPA); don't fixate on absolute amounts**.
- Sample reading: "Completion rate ~80%, CPCV ~$0.02, estimated CPA at 2% completion→conversion is well below target CPA → delivery is healthy, can scale budget."
- For **actual conversions** instead of the 2% rule-of-thumb, use the `SUM(converted)` column (this dataset models clicks/conversions).

---

## Query 8: Creative Performance Comparison (A/B Test)

**Business context:**
Nike is running 15-second, 30-second, and 60-second creative variants simultaneously as an A/B test. Their media lead has to decide: **"Which version do we double down on next?"** 15s has the highest completion rate but conveys little info; 60s is information-rich but often skipped. This query uses CPCV (cost per completed view) as the unifying yardstick for an objective recommendation.

**Industry knowledge:**
- **A/B testing:** running multiple creative variants in parallel to see which performs best
- **Cost per Completion (CPCV):** = total spend / completed listens. **Closer to true effectiveness than CPM**, because CPM includes water (impressions that weren't listened through)
- **Scale:** the digital ad term for "scaling up" — shifting the winning creative's budget share from 20% to 80%

**Category:** Advertiser ROI
**Difficulty:** Advanced
**Business role:** Advertiser

**Approach:**
Chain `ad_creative → ad_campaign → ad_impression`, `WHERE` locks to one campaign, aggregate by creative for A/B comparison. The CTE `creative_performance` first computes each creative's completion rate and CPCV; the outer query uses the window function `RANK() OVER (ORDER BY cost_per_completion ASC)` to rank efficiency, then a `CASE` for "scale/keep testing/pause" recommendations. Grain = one row per creative. The RANK window function is more direct than self-joins or subqueries. CPCV's denominator uses `NULLIF` to prevent zero.

```sql
-- Compare creative performance within a campaign
WITH creative_performance AS (
    SELECT
        acr.creative_name,
        acr.duration_sec,
        acr.has_call_to_action,
        COUNT(ai.id) AS total_impressions,
        SUM(CASE WHEN ai.was_completed THEN 1 ELSE 0 END) AS completed_impressions,
        ROUND(100.0 * SUM(CASE WHEN ai.was_completed THEN 1 ELSE 0 END) / COUNT(ai.id), 1) AS completion_rate_pct,
        ROUND(AVG(ai.ad_duration_played_sec), 1) AS avg_duration_played,
        ROUND(SUM(ai.actual_charge_cpm / 1000.0), 2) AS total_cost,
        ROUND(AVG(ai.actual_charge_cpm), 2) AS avg_cpm,
        ROUND(SUM(ai.actual_charge_cpm / 1000.0) / NULLIF(SUM(CASE WHEN ai.was_completed THEN 1 ELSE 0 END), 0), 2) AS cost_per_completion
    FROM ad_creative acr
    JOIN ad_campaign ac ON acr.campaign_id = ac.id
    JOIN ad_impression ai ON acr.id = ai.creative_id
    WHERE ac.campaign_name = 'Nike - Running Shoes Spring Launch'  -- swap in the actual campaign name
    GROUP BY acr.id, acr.creative_name, acr.duration_sec, acr.has_call_to_action
)
SELECT
    creative_name,
    duration_sec,
    has_call_to_action,
    total_impressions,
    completed_impressions,
    completion_rate_pct,
    avg_duration_played,
    avg_cpm,
    total_cost,
    cost_per_completion,
    RANK() OVER (ORDER BY cost_per_completion ASC) AS efficiency_rank,
    CASE
        WHEN completion_rate_pct >= 85 AND cost_per_completion <= 0.02 THEN 'WINNER: scale up'
        WHEN completion_rate_pct >= 70 AND cost_per_completion <= 0.03 THEN 'GOOD: keep testing'
        WHEN completion_rate_pct < 60 OR cost_per_completion > 0.04 THEN 'PAUSE: poor performance'
        ELSE 'AVERAGE: keep watching'
    END AS recommendation
FROM creative_performance
ORDER BY efficiency_rank;
```

**Result interpretation:**
- **Typical winner:** 30s + CTA → completion 75-85%, CPCV $0.02-0.025
- **15s** completion 90%+ but low information density, weak conversion
- **60s** completion 60-70%; unless the product is complex (e.g., SaaS), not worth it

---

## Query 9: Audience Targeting Effectiveness

**Business context:**
Robinhood (FinTech) ran a precision-targeted campaign for "ages 25-34, Tech_Enthusiast, CA/NY only," but the targeting premium pushed CPM 30% higher than untargeted. They want to verify: **does that 30% premium actually deliver a proportional lift in effectiveness?** This query splits impressions into "full match / partial match / no match" tiers and compares performance.

**Industry knowledge:**
- **Targeting:** restricting ads to specific audiences
- **Targeting Premium:** the higher unit price for precise audiences
- **Reach:** more precise targeting → smaller addressable audience → budget might not get spent
- **Incremental Lift:** the extra effectiveness gained from the extra spend

**Category:** Advertiser ROI
**Difficulty:** Advanced
**Business role:** Advertiser

**Approach:**
We need to JOIN each impression to both the campaign's targeting criteria (`ad_creative → ad_campaign`) and the listener's actual attributes (`play_session → listener`), `WHERE` locks to one advertiser. **Key technique: multi-value comma-separated targeting needs the "wrap with commas + LIKE" trick** — `(',' || target || ',') LIKE ('%,' || value || ',%')` — so that multi-value fields like "25-34,35-44" and "US-CA,US-NY" match correctly (a naive `=` whole-string compare would miss). The CTE computes a per-impression "match score" (age hit + geo hit = 0/1/2); the outer query groups into "full / partial / no match" tiers and compares completion rate, skip rate, and CPCV. Grain = campaign × match tier.

```sql
-- Evaluate targeting effectiveness: compare "full match" vs "no match" impression performance
WITH impression_targeting_match AS (
    SELECT
        ai.id AS impression_id,
        ac.campaign_name,
        ac.target_segment_age,
        ac.target_segment_geo,
        l.age_group,
        l.location_state,
        -- Use "wrap with commas + LIKE" for comma-separated multi-value membership tests,
        -- correctly handling multi-value fields like "25-34,35-44" / "US-CA,US-NY" (old whole-string equality would miss).
        (CASE
            WHEN ac.target_segment_age IS NOT NULL
                 AND (',' || ac.target_segment_age || ',') LIKE ('%,' || l.age_group || ',%')
            THEN 1 ELSE 0
         END)
        +
        (CASE
            WHEN ac.target_segment_geo IS NOT NULL
                 AND (',' || ac.target_segment_geo || ',') LIKE ('%,US-' || l.location_state || ',%')
            THEN 1 ELSE 0
         END) AS targeting_match_score,
        ai.actual_charge_cpm,
        ai.was_completed,
        ai.was_skipped
    FROM ad_impression ai
    JOIN ad_creative acr ON ai.creative_id = acr.id
    JOIN ad_campaign ac ON acr.campaign_id = ac.id
    JOIN advertiser a ON ac.advertiser_id = a.id
    JOIN play_session ps ON ai.play_session_id = ps.id
    JOIN listener l ON ps.listener_id = l.id
    WHERE a.company_name = 'Robinhood'  -- swap in the actual advertiser (FinTech, has age+geo targeting)
)
SELECT
    campaign_name,
    CASE
        WHEN targeting_match_score = 0 THEN 'No match (untargeted)'
        WHEN targeting_match_score = 1 THEN 'Partial match (1 criterion)'
        WHEN targeting_match_score >= 2 THEN 'Full match (2+ criteria)'
    END AS targeting_alignment,
    COUNT(impression_id) AS total_impressions,
    ROUND(AVG(actual_charge_cpm), 2) AS avg_cpm,
    ROUND(100.0 * SUM(CASE WHEN was_completed THEN 1 ELSE 0 END) / COUNT(impression_id), 1) AS completion_rate_pct,
    ROUND(100.0 * SUM(CASE WHEN was_skipped THEN 1 ELSE 0 END) / COUNT(impression_id), 1) AS skip_rate_pct,
    ROUND(SUM(actual_charge_cpm / 1000.0) / NULLIF(SUM(CASE WHEN was_completed THEN 1 ELSE 0 END), 0), 3) AS cost_per_completion
FROM impression_targeting_match
GROUP BY campaign_name, targeting_alignment
ORDER BY campaign_name, targeting_match_score DESC;
```

**Result interpretation:**
- **Full match** should show 15-25% higher completion and 20-35% lower skip vs. "no match"
- If **CPCV (full match) ≈ CPCV (no match)** → targeting premium isn't delivering proportional returns → loosen targeting to cut cost

---

## Query 10: Bid Amount vs. Win Rate Correlation

**Business context:**
Advertisers' DSPs perform **bid shading** — bidding the lowest possible price that still wins. This query plots the "bid → win rate" curve, helping the DSP algorithm find the optimal bid point.

**Industry knowledge:**
- **Bid Shading:** an algorithm that, based on historical data, shades bids "down to the market clearing price" — still wins but saves money
- **Marginal Cost / Marginal Win Rate:** for every extra $1 bid, how many additional percentage points of win rate do you gain?
- **Sweet Spot:** the bid range with the highest marginal win rate

**Category:** Advertiser ROI
**Difficulty:** Intermediate
**Business role:** Advertiser

**Approach:**
This query only uses `ad_auction_log` (bids and whether-won are both there; no JOIN needed). The CTE `bid_buckets` slices `bid_cpm` into price tiers; the outer query computes `win_rate = SUM(won_auction) / COUNT(*)` per tier. Grain = one row per price tier. `won_auction` is boolean (stored as 0/1 in SQLite); use `CASE WHEN ... THEN 1 ELSE 0 END` to sum. `ORDER BY min_bid` arranges tiers low to high so you can read the "bid → win rate" curve directly and find the sweet spot where marginal win rate is steepest.

```sql
-- Analyze the relationship between bid amount and win rate
WITH bid_buckets AS (
    SELECT
        campaign_id,
        CASE
            WHEN bid_cpm < 10 THEN '$0-10'
            WHEN bid_cpm < 15 THEN '$10-15'
            WHEN bid_cpm < 20 THEN '$15-20'
            WHEN bid_cpm < 25 THEN '$20-25'
            WHEN bid_cpm < 30 THEN '$25-30'
            ELSE '$30+'
        END AS bid_range,
        bid_cpm,
        won_auction
    FROM ad_auction_log
)
SELECT
    bid_range,
    COUNT(*) AS total_bids,
    SUM(CASE WHEN won_auction THEN 1 ELSE 0 END) AS auctions_won,
    ROUND(100.0 * SUM(CASE WHEN won_auction THEN 1 ELSE 0 END) / COUNT(*), 1) AS win_rate_pct,
    ROUND(AVG(bid_cpm), 2) AS avg_bid_in_range,
    ROUND(MIN(bid_cpm), 2) AS min_bid,
    ROUND(MAX(bid_cpm), 2) AS max_bid
FROM bid_buckets
GROUP BY bid_range
ORDER BY min_bid;
```

**Result interpretation:**
- Low tier ($0-10) → win rate <15% (below market clearing price)
- Mid tier ($15-20) → win rate 40-60% (efficiency sweet spot)
- High tier ($30+) → win rate 85-95% but expensive
- **Optimal bid:** the tier where win rate climbs steeply for each $1 increment (e.g., $18-22)

---

## Query 11: Cost per Completed View (CPCV) Analysis

**Business context:**
HelloFresh (grocery e-commerce) has set: **"I'll pay $0.05 per completed view."** They want to identify the shows with the lowest CPCV and shift budget there.

**Industry knowledge:**
- **CPCV (Cost per Completed View):** closer to "true effectiveness" than CPM, because unfinished plays don't count
- **Quality Scoring:** a show's "ad monetization quality," determined by completion rate
- **Budget Reallocation:** industry standard — weekly budget reallocation across shows based on CPCV

**Category:** Advertiser ROI
**Difficulty:** Intermediate
**Business role:** Advertiser

**Approach:**
Long chain: `ad_impression → ad_creative → ad_campaign → advertiser` for the advertiser, plus `ad_impression → play_session → podcast_episode → podcast` for the show; `WHERE` locks to one advertiser, aggregating by "advertiser × campaign × show." Grain = one row per show. CPCV = spend / completed count, with `NULLIF` to prevent zero and `ROUND(...,4)` for 4 decimal places (small amounts). **`HAVING total_impressions >= 5` is deliberately low**: under a 60-day sample, the impression volume for "single advertiser × single show" is small; a high threshold would return empty. `ORDER BY cost_per_completed_view ASC` finds the most efficient inventory sources.

```sql
-- Compute CPCV to identify the most efficient inventory sources
SELECT
    a.company_name AS advertiser,
    ac.campaign_name,
    p.podcast_name,
    p.category AS podcast_category,
    COUNT(ai.id) AS total_impressions,
    SUM(CASE WHEN ai.was_completed THEN 1 ELSE 0 END) AS completed_views,
    ROUND(100.0 * SUM(CASE WHEN ai.was_completed THEN 1 ELSE 0 END) / COUNT(ai.id), 1) AS completion_rate_pct,
    ROUND(SUM(ai.actual_charge_cpm / 1000.0), 2) AS total_cost_usd,
    ROUND(SUM(ai.actual_charge_cpm / 1000.0) / NULLIF(SUM(CASE WHEN ai.was_completed THEN 1 ELSE 0 END), 0), 4) AS cost_per_completed_view,
    CASE
        WHEN SUM(ai.actual_charge_cpm / 1000.0) / NULLIF(SUM(CASE WHEN ai.was_completed THEN 1 ELSE 0 END), 0) <= 0.03 THEN 'EXCELLENT: invest more'
        WHEN SUM(ai.actual_charge_cpm / 1000.0) / NULLIF(SUM(CASE WHEN ai.was_completed THEN 1 ELSE 0 END), 0) <= 0.05 THEN 'GOOD: maintain'
        WHEN SUM(ai.actual_charge_cpm / 1000.0) / NULLIF(SUM(CASE WHEN ai.was_completed THEN 1 ELSE 0 END), 0) <= 0.08 THEN 'AVERAGE: monitor'
        ELSE 'POOR: reduce or pause'
    END AS efficiency_rating
FROM ad_impression ai
JOIN ad_creative acr ON ai.creative_id = acr.id
JOIN ad_campaign ac ON acr.campaign_id = ac.id
JOIN advertiser a ON ac.advertiser_id = a.id
JOIN play_session ps ON ai.play_session_id = ps.id
JOIN podcast_episode pe ON ps.episode_id = pe.id
JOIN podcast p ON pe.podcast_id = p.id
WHERE a.company_name = 'HelloFresh'  -- swap in the actual advertiser
GROUP BY a.company_name, ac.campaign_name, p.podcast_name, p.category
HAVING total_impressions >= 5  -- under a 60-day sample, single-advertiser × single-show impression volume is low; keep threshold low to ensure rows return
ORDER BY cost_per_completed_view ASC;
```

**Result interpretation:**
- **High-stickiness shows** (true crime / business) → CPCV $0.02-0.035 → invest more
- **Low-stickiness shows** (background music type) → CPCV $0.06-0.10 → reduce

---

## Query 12: Competitor Bidding Behavior Insights

**Business context:**
Strategic advertiser Coca-Cola wants **competitive intelligence**: are Pepsi and Dr. Pepper bidding on the same podcast inventory? How high are they bidding? If Pepsi bids 20% higher than us, either we raise our bid or we find differentiated inventory. This query breaks down auction participation by CPG (fast-moving consumer goods) advertisers.

**Industry knowledge:**
- **Share of Voice (SOV):** the share of wins within same-industry auctions — reflects "voice share"
- **Competitive Intelligence:** B2B marketing intelligence
- **Differentiated Inventory:** inventory competitors aren't fighting for (e.g., niche categories)

**Category:** Advertiser ROI
**Difficulty:** Advanced
**Business role:** Advertiser

**Approach:**
Chain `ad_auction_log → ad_campaign → advertiser`, `WHERE` locks to one industry (CPG). The CTE `competitor_bids` flattens all peer bids; the outer query aggregates by advertiser to compute win rate, average bid, and second-place bid. **Auction participation must use `COUNT(DISTINCT impression_id)`** — one auction has multiple bid rows in the log, so without dedup, participation is overcounted. `AVG(CASE WHEN bid_rank=2 THEN bid_cpm END)` averages only second-place bids (the CASE returns NULL for non-matches and AVG ignores NULLs). `HAVING ≥50 auctions` filters small samples, ranking who's using money to suppress competitors.

```sql
-- Analyze competitive bidding behavior within the same industry
WITH competitor_bids AS (
    SELECT
        a.company_name AS advertiser,
        a.industry_vertical,
        aal.impression_id,
        aal.bid_cpm,
        aal.won_auction,
        aal.bid_rank
    FROM ad_auction_log aal
    JOIN ad_campaign ac ON aal.campaign_id = ac.id
    JOIN advertiser a ON ac.advertiser_id = a.id
    WHERE a.industry_vertical = 'CPG'  -- focus on CPG industry
)
SELECT
    advertiser,
    COUNT(DISTINCT impression_id) AS auctions_participated,
    COUNT(CASE WHEN won_auction THEN 1 END) AS auctions_won,
    ROUND(100.0 * COUNT(CASE WHEN won_auction THEN 1 END) / COUNT(DISTINCT impression_id), 1) AS win_rate_pct,
    ROUND(AVG(bid_cpm), 2) AS avg_bid_cpm,
    ROUND(AVG(CASE WHEN won_auction THEN bid_cpm END), 2) AS avg_winning_bid,
    ROUND(AVG(CASE WHEN bid_rank = 2 THEN bid_cpm END), 2) AS avg_second_place_bid,
    ROUND(MIN(bid_cpm), 2) AS min_bid,
    ROUND(MAX(bid_cpm), 2) AS max_bid
FROM competitor_bids
GROUP BY advertiser
HAVING auctions_participated >= 50
ORDER BY win_rate_pct DESC;
```

**Result interpretation:**
- Coca-Cola win rate 58% / avg bid $22; Pepsi win rate 48% / avg bid $19 → Coca-Cola is **using money to suppress competitors**
- New entrant Olipop win rate 35% / avg bid $28 → willing to pay high but targeting is off

---

## Query 13: RPM Benchmarking by Show Category

**Business context:**
The host of "Tech Explained" has an RPM of roughly $28 (the host nets $28 per 1,000 plays); they have no idea if that's high or low. This query gives the average and range for similar shows, helping the host see where they stand in the industry.
(Note: RPM is "host net per 1,000 plays" — typically **a few tens of dollars**, not hundreds or thousands. Don't confuse it with "total monthly revenue.")

**Industry knowledge:**
- **RPM (Revenue Per Mille):** the host's view — how much the host nets per 1,000 plays
- **Benchmarking:** compare against shows in the same category — don't compare across categories (Tech vs. Comedy is meaningless)
- **Percentile:** P50 = median, P75 = "better than 75% of peers"

**Category:** Creator Monetization
**Difficulty:** Intermediate
**Business role:** Host

**Approach:**
Chain `podcast → podcast_episode → play_session`, then `LEFT JOIN ad_impression`. **LEFT JOIN is critical**: RPM's denominator is "play count" — sessions with no ad sold also need to be included, or RPM is inflated. `WHERE p.is_premium = 0` excludes members-only shows. Two-level aggregation: CTE `podcast_metrics` first computes per-show RPM (host payout = revenue × 0.70; RPM = payout / plays × 1000); the outer query then aggregates by `category` for avg/min/max. **SQLite has no native `PERCENTILE_CONT`**, so we only return the range — for true median/percentile you'd need `NTILE` or external computation (noted in the comment).

```sql
-- Benchmark RPM by show category
WITH podcast_metrics AS (
    SELECT
        p.id AS podcast_id,
        p.podcast_name,
        p.category,
        COUNT(DISTINCT ps.id) AS total_play_sessions,
        COUNT(ai.id) AS total_ad_impressions,
        ROUND(SUM(ai.actual_charge_cpm / 1000.0), 2) AS total_ad_revenue,
        ROUND(SUM(ai.actual_charge_cpm / 1000.0) * 0.70, 2) AS creator_payout_70pct,
        ROUND((SUM(ai.actual_charge_cpm / 1000.0) * 0.70) / NULLIF(COUNT(DISTINCT ps.id), 0) * 1000, 2) AS rpm
    FROM podcast p
    JOIN podcast_episode pe ON p.id = pe.podcast_id
    JOIN play_session ps ON pe.id = ps.episode_id
    LEFT JOIN ad_impression ai ON ps.id = ai.play_session_id
    WHERE p.is_premium = 0
    GROUP BY p.id, p.podcast_name, p.category
    HAVING total_play_sessions >= 100
)
SELECT
    category,
    COUNT(podcast_id) AS podcasts_in_category,
    ROUND(AVG(rpm), 2) AS avg_rpm,
    ROUND(MIN(rpm), 2) AS min_rpm,
    ROUND(MAX(rpm), 2) AS max_rpm,
    ROUND(AVG(rpm) - MIN(rpm), 2) AS rpm_range,
    -- Note: SQLite doesn't natively support PERCENTILE_CONT; in production use NTILE or external computation
    ROUND(AVG(total_ad_revenue), 2) AS avg_total_revenue_per_podcast
FROM podcast_metrics
GROUP BY category
ORDER BY avg_rpm DESC;
```

**Result interpretation:**
- RPM magnitude = **tens of dollars per 1,000 plays** (CPM ~$15-30 × ~1.5 ads/play × 70% share), not hundreds or thousands.
- **Technology / Business** usually the highest (SaaS/FinTech bidding pushes CPM up); **Comedy / Entertainment** lower (advertiser premium is small).
- The SQL gives avg / min / max range; SQLite has no native PERCENTILE_CONT — for true median / 75th percentile, use NTILE or compute externally. Hosts can start by gauging "my RPM vs. category max" to see how far behind the leaders they are.

---

## Query 14: Per-Episode Deep Dive

**Business context:**
The host wants to figure out **"which content types make the most money."** For example, is the "ChatGPT explained" episode making 3× what others make? If so, double down on AI topics next season.

**Industry knowledge:**
- **Content Analytics:** using data to guide content direction
- **Halo Effect:** a hot-topic episode brings both traffic and high CPM

**Category:** Creator Monetization
**Difficulty:** Intermediate
**Business role:** Host

**Approach:**
Chain `podcast → podcast_episode → play_session` `LEFT JOIN ad_impression`, `WHERE` locks to one show, aggregate by episode. Grain = one row per episode. **Pitfall: after LEFT JOIN, one session "doubles up" because it has multiple impressions**, so plays must use `COUNT(DISTINCT ps.id)`; otherwise plays get inflated by ad count and RPM gets crushed. RPM = host payout / distinct plays × 1000. `ORDER BY rpm DESC` finds the most lucrative topics — focus on **relative differences** between episodes, not absolute values.

```sql
-- Rank episodes by revenue to identify content monetization patterns
SELECT
    p.podcast_name,
    pe.episode_number,
    pe.title,
    pe.publish_date,
    pe.duration_seconds / 60 AS duration_minutes,
    COUNT(DISTINCT ps.id) AS total_plays,
    COUNT(ai.id) AS total_ad_impressions,
    ROUND(AVG(ps.completion_percentage), 1) AS avg_completion_pct,
    ROUND(AVG(ai.actual_charge_cpm), 2) AS avg_cpm,
    ROUND(SUM(ai.actual_charge_cpm / 1000.0), 2) AS gross_ad_revenue,
    ROUND(SUM(ai.actual_charge_cpm / 1000.0) * 0.70, 2) AS creator_earnings_70pct,
    ROUND((SUM(ai.actual_charge_cpm / 1000.0) * 0.70) / NULLIF(COUNT(DISTINCT ps.id), 0) * 1000, 2) AS rpm
FROM podcast p
JOIN podcast_episode pe ON p.id = pe.podcast_id
JOIN play_session ps ON pe.id = ps.episode_id
LEFT JOIN ad_impression ai ON ps.id = ai.play_session_id
WHERE p.podcast_name = 'Tech Explained'
GROUP BY p.podcast_name, pe.episode_number, pe.title, pe.publish_date, pe.duration_seconds
ORDER BY rpm DESC
LIMIT 20;
```

**Result interpretation:**
- Per-episode RPM magnitude is the same **tens of dollars per 1,000 plays**; the **relative differences** between episodes are what matter (e.g., an AI-topic episode at RPM ~$35, vs. a typical episode at ~$20).
- **Content strategy:** which topic types consistently produce higher RPM (usually AI/Tech) → focus on these next season.

---

## Query 15: Host Monthly Revenue Trend

**Business context:**
The host wants to see **monthly revenue growth trends**: are they growing MoM (Month-over-Month) by 10%? Stagnant? Did Q4 boost CPM by 25% during the holiday rush?

**Industry knowledge:**
- **MoM (Month-over-Month):** this month vs. last month
- **YoY (Year-over-Year):** this month vs. the same month last year
- **Q4 Seasonality:** Nov-Dec retail season pushes CPMs up 15-30% across all digital ad platforms

**Category:** Creator Monetization
**Difficulty:** Advanced
**Business role:** Host

**Approach:**
Use the aggregate table `revenue_settlement → podcast` directly (no need to drop back to impressions — settlement is already a real aggregate); `WHERE` locks to one show. The CTE aggregates by month (`DATE(settlement_date, 'start of month')` rolls up to month); the outer query uses the window function `LAG(creator_earnings) OVER (ORDER BY month)` to grab last month's value for MoM growth. Grain = one row per month. **LAG is the standard tool for MoM** — far cleaner than a self-join; growth-rate denominator uses `NULLIF` to handle a zero previous month.

```sql
-- Monthly revenue trend + growth rate
WITH monthly_revenue AS (
    SELECT
        p.podcast_name,
        DATE(rs.settlement_date, 'start of month') AS month,
        SUM(rs.total_impressions) AS total_impressions,
        ROUND(SUM(rs.total_revenue_usd), 2) AS gross_revenue,
        ROUND(SUM(rs.podcast_payout_usd), 2) AS creator_earnings,
        ROUND(AVG(rs.avg_cpm), 2) AS avg_cpm,
        ROUND(AVG(rs.rpm), 2) AS avg_rpm,
        ROUND(AVG(rs.fill_rate), 3) AS avg_fill_rate
    FROM revenue_settlement rs
    JOIN podcast p ON rs.podcast_id = p.id
    WHERE p.podcast_name = 'Tech Explained'
    GROUP BY p.podcast_name, month
)
SELECT
    podcast_name,
    month,
    total_impressions,
    gross_revenue,
    creator_earnings,
    avg_cpm,
    avg_rpm,
    avg_fill_rate,
    LAG(creator_earnings) OVER (ORDER BY month) AS prev_month_earnings,
    ROUND(creator_earnings - LAG(creator_earnings) OVER (ORDER BY month), 2) AS earnings_change,
    ROUND(100.0 * (creator_earnings - LAG(creator_earnings) OVER (ORDER BY month)) /
        NULLIF(LAG(creator_earnings) OVER (ORDER BY month), 0), 1) AS growth_rate_pct
FROM monthly_revenue
ORDER BY month DESC;
```

**Result interpretation:**
- Growing shows: MoM 5-15%
- Mature shows: stable ±5%, with Q4 spike
- Declining shows: investigate — content aging? advertisers moving away?

---

## Query 16: Content Optimization (Length / Publish Day)

**Business context:**
The host wants **data-driven content suggestions**. For example: do episodes over 45 minutes have 20% lower completion? Do Monday-released episodes get 30% more plays than Friday's? This query slices by length tier and publish day to recommend the best combination.

**Industry knowledge:**
- **Duration Tradeoff:** shorter episodes have higher completion but fewer ad slots; longer episodes have more slots but lower completion
- **Publishing Cadence:** industry best practice — publish weekday mornings to catch commuter listeners

**Category:** Creator Monetization
**Difficulty:** Advanced
**Business role:** Host

**Approach:**
Chain `podcast_episode → podcast → play_session` `LEFT JOIN ad_impression`, `WHERE` locks to one show. The CTE `episode_analysis` tags each episode with two attributes: length bucket (`CASE` on `duration_seconds`) and publish day of week (`strftime('%w', publish_date)`); the outer query aggregates by length bucket and uses a **correlated subquery** `(SELECT AVG(rpm) FROM episode_analysis)` to pull the global average RPM as the baseline for "strong/weak/average" recommendations. Grain = one row per length bucket. Plays again use `COUNT(DISTINCT ps.id)` to avoid LEFT JOIN doubling.

```sql
-- Content optimization recommendations by length bucket + publish day
WITH episode_analysis AS (
    SELECT
        pe.id AS episode_id,
        CASE
            WHEN pe.duration_seconds < 1200 THEN '<20 min'
            WHEN pe.duration_seconds < 1800 THEN '20-30 min'
            WHEN pe.duration_seconds < 2700 THEN '30-45 min'
            WHEN pe.duration_seconds < 3600 THEN '45-60 min'
            ELSE '>60 min'
        END AS duration_bucket,
        CASE CAST(strftime('%w', pe.publish_date) AS INTEGER)
            WHEN 0 THEN 'Sunday' WHEN 1 THEN 'Monday' WHEN 2 THEN 'Tuesday'
            WHEN 3 THEN 'Wednesday' WHEN 4 THEN 'Thursday'
            WHEN 5 THEN 'Friday' WHEN 6 THEN 'Saturday'
        END AS publish_day,
        COUNT(DISTINCT ps.id) AS total_plays,
        ROUND(AVG(ps.completion_percentage), 1) AS avg_completion_pct,
        COUNT(ai.id) AS total_impressions,
        ROUND(SUM(ai.actual_charge_cpm / 1000.0) * 0.70, 2) AS creator_earnings,
        ROUND((SUM(ai.actual_charge_cpm / 1000.0) * 0.70) / NULLIF(COUNT(DISTINCT ps.id), 0) * 1000, 2) AS rpm
    FROM podcast_episode pe
    JOIN podcast p ON pe.podcast_id = p.id
    JOIN play_session ps ON pe.id = ps.episode_id
    LEFT JOIN ad_impression ai ON ps.id = ai.play_session_id
    WHERE p.podcast_name = 'Tech Explained'
    GROUP BY pe.id, duration_bucket, publish_day
)
SELECT
    duration_bucket,
    COUNT(episode_id) AS episodes,
    ROUND(AVG(total_plays), 0) AS avg_plays_per_episode,
    ROUND(AVG(avg_completion_pct), 1) AS avg_completion_pct,
    ROUND(AVG(rpm), 2) AS avg_rpm,
    ROUND(SUM(creator_earnings), 2) AS total_earnings,
    CASE
        WHEN AVG(rpm) >= (SELECT AVG(rpm) FROM episode_analysis) * 1.1 THEN 'STRONG: keep this length'
        WHEN AVG(rpm) <= (SELECT AVG(rpm) FROM episode_analysis) * 0.9 THEN 'WEAK: consider adjusting'
        ELSE 'AVERAGE: hold steady'
    END AS recommendation
FROM episode_analysis
GROUP BY duration_bucket
ORDER BY avg_rpm DESC;
```

**Result interpretation:**
- **30-45 min** is typically the highest-RPM bucket — long enough to fit mid-roll, not so long that people quit
- **<20 min** has the highest completion but few ad slots
- **>60 min** completion drops to 60%; back-half slots go empty

---

## Query 17: Ad Fatigue Detection

**Business context:**
The UX team suspects **some listeners are being carpet-bombed by the same advertiser** to the point of disgust, leading to aggressive skipping and even churn risk. Example: a listener who heard 8 Geico ads in two weeks may have hit the breaking point. This query flags those high-risk listeners.

**Industry knowledge:**
- **Ad Fatigue:** the psychological aversion listeners develop from repeated exposure to the same ad
- **Frequency Cap:** limiting the number of times one advertiser can hit one listener (industry best practice is 3×/week/advertiser)
- **Churn Risk:** annoyance → stops opening the app → churns

**Category:** Listener Experience
**Difficulty:** Advanced
**Business role:** Platform UX

**Approach:**
Long chain `listener → play_session → ad_impression → ad_creative → ad_campaign → advertiser`, aggregate by "listener × advertiser" to find those getting carpet-bombed. `WHERE ai.impression_time >= DATE('2026-06-21','-14 days')` restricts to the last 14 days. Grain = one row per listener × advertiser. `HAVING total_impressions_from_advertiser >= 5` filters to high frequency; the outer query then uses `WHERE skip_rate >= 0.5` to lock in the "high frequency + high skip" fatigue signal. `MAX(impression_time)` with `JULIANDAY` computes days-since-today. `CASE` tiers into severe/high/medium/normal with frequency-cut recommendations.

```sql
-- Identify listeners likely to be experiencing ad fatigue
WITH listener_ad_exposure AS (
    SELECT
        l.id AS listener_id,
        l.listener_uuid,
        a.company_name AS advertiser,
        COUNT(DISTINCT ps.id) AS sessions_with_this_advertiser,
        COUNT(ai.id) AS total_impressions_from_advertiser,
        ROUND(AVG(CASE WHEN ai.was_skipped THEN 1.0 ELSE 0.0 END), 2) AS skip_rate,
        MAX(ai.impression_time) AS last_impression_time,
        ROUND(JULIANDAY('2026-06-21') - JULIANDAY(MAX(ai.impression_time)), 1) AS days_since_last_ad
    FROM listener l
    JOIN play_session ps ON l.id = ps.listener_id
    JOIN ad_impression ai ON ps.id = ai.play_session_id
    JOIN ad_creative acr ON ai.creative_id = acr.id
    JOIN ad_campaign ac ON acr.campaign_id = ac.id
    JOIN advertiser a ON ac.advertiser_id = a.id
    WHERE ai.impression_time >= DATE('2026-06-21', '-14 days')
    GROUP BY l.id, l.listener_uuid, a.company_name
    HAVING total_impressions_from_advertiser >= 5
)
SELECT
    listener_uuid,
    advertiser,
    sessions_with_this_advertiser,
    total_impressions_from_advertiser,
    skip_rate,
    days_since_last_ad,
    CASE
        WHEN total_impressions_from_advertiser >= 12 AND skip_rate >= 0.7 THEN 'SEVERE: block for 30 days'
        WHEN total_impressions_from_advertiser >= 8 AND skip_rate >= 0.6 THEN 'HIGH: cut frequency 50%'
        WHEN total_impressions_from_advertiser >= 5 AND skip_rate >= 0.5 THEN 'MEDIUM: cut frequency 25%'
        ELSE 'Normal'
    END AS fatigue_level
FROM listener_ad_exposure
WHERE skip_rate >= 0.5
ORDER BY total_impressions_from_advertiser DESC, skip_rate DESC
LIMIT 100;
```

**Result interpretation:**
- **Severe cases:** immediately block that advertiser platform-wide for 30 days
- **Platform action:** global rule — "max 3 exposures per single advertiser per listener per 7 days"

---

## Query 18: Skip Rate Analysis by Creative Attributes

**Business context:**
The UX team wants to produce **a "creative best practices guide"** for advertisers: does 60s have twice the skip rate of 30s? Do creatives without a CTA get skipped more? Once the data is in, send the guide to advertisers: "Make creatives this way for best results."

**Industry knowledge:**
- **Creative Best Practices:** creative-production guidance the platform shares with advertisers
- **CTA (Call to Action):** prompts like "visit xxx.com now" or "order now and get $50 off"
- Industry consensus: **30 seconds with a CTA is the overall best**

**Category:** Listener Experience
**Difficulty:** Intermediate
**Business role:** Platform UX

**Approach:**
Chain `ad_creative → ad_impression`, aggregate by the combination of `(duration_sec, has_call_to_action)`. Grain = one row per length × CTA combination. No CTE needed — a single `GROUP BY` does it. Skip and completion rates use boolean `SUM/COUNT`. `HAVING total_impressions >= 50` filters small samples; `ORDER BY skip_rate_pct ASC` puts the lowest-skip combinations first (usually 30s + CTA) — that's the "creative best practices" guidance to ship to advertisers.

```sql
SELECT
    acr.duration_sec,
    acr.has_call_to_action,
    COUNT(ai.id) AS total_impressions,
    SUM(CASE WHEN ai.was_skipped THEN 1 ELSE 0 END) AS skipped_impressions,
    ROUND(100.0 * SUM(CASE WHEN ai.was_skipped THEN 1 ELSE 0 END) / COUNT(ai.id), 1) AS skip_rate_pct,
    SUM(CASE WHEN ai.was_completed THEN 1 ELSE 0 END) AS completed_impressions,
    ROUND(100.0 * SUM(CASE WHEN ai.was_completed THEN 1 ELSE 0 END) / COUNT(ai.id), 1) AS completion_rate_pct,
    ROUND(AVG(ai.ad_duration_played_sec), 1) AS avg_seconds_listened,
    ROUND(AVG(ai.actual_charge_cpm), 2) AS avg_cpm_paid
FROM ad_creative acr
JOIN ad_impression ai ON acr.id = ai.creative_id
GROUP BY acr.duration_sec, acr.has_call_to_action
HAVING total_impressions >= 50
ORDER BY skip_rate_pct ASC;
```

**Result interpretation:**
- 30s + CTA: skip 32-38%, completion 65-72% ← **best**
- 60s without CTA: skip 58-68% ← **worst**

---

## Query 19: Optimal Ad Frequency Recommendation

**Business context:**
The strategy team needs to decide where to set the **frequency cap**. Is the current "max 5 ads per hour" too many? Will it drive listeners away? Too few and we leave money on the table. This query finds the inflection point on the "ad frequency → listener engagement" curve.

**Industry knowledge:**
- **Frequency Cap:** an industry-standard practice, balancing revenue with experience
- **Sweet Spot:** where marginal revenue gain = marginal experience loss
- **Diminishing Returns:** adding one more ad: incremental revenue < experience loss

**Category:** Listener Experience
**Difficulty:** Advanced
**Business role:** Platform UX

**Approach:**
Chain `listener → play_session` `LEFT JOIN ad_impression`. The CTE `listener_ad_frequency` first computes per-listener "ads per session," along with completion rate, skip rate, and revenue generated; the outer query aggregates by frequency bucket to find the inflection. `WHERE` limits to last 30 days and `is_premium_subscriber=0` (premium gets no ads). **LEFT JOIN ensures "listened but no ad received" sessions are included in the denominator**, otherwise frequency is overstated. `HAVING total_sessions >= 5` stabilizes per-listener samples. Grain: inner = one row per listener, outer = one row per frequency bucket. Find the sweet spot where "incremental revenue < experience loss" to set the frequency cap.

```sql
WITH listener_ad_frequency AS (
    SELECT
        l.id AS listener_id,
        COUNT(ps.id) AS total_sessions,
        COUNT(ai.id) AS total_ads_heard,
        ROUND(COUNT(ai.id) * 1.0 / NULLIF(COUNT(ps.id), 0), 2) AS ads_per_session,
        ROUND(AVG(ps.completion_percentage), 1) AS avg_episode_completion_pct,
        ROUND(AVG(CASE WHEN ai.was_skipped THEN 1.0 ELSE 0.0 END), 2) AS avg_ad_skip_rate,
        ROUND(SUM(ai.actual_charge_cpm / 1000.0), 2) AS revenue_generated
    FROM listener l
    JOIN play_session ps ON l.id = ps.listener_id
    LEFT JOIN ad_impression ai ON ps.id = ai.play_session_id
    WHERE ps.session_start_time >= DATE('2026-06-21', '-30 days')
        AND l.is_premium_subscriber = 0
    GROUP BY l.id
    HAVING total_sessions >= 5
)
SELECT
    CASE
        WHEN ads_per_session < 2 THEN '0-2 ads/session'
        WHEN ads_per_session < 3 THEN '2-3 ads/session'
        WHEN ads_per_session < 4 THEN '3-4 ads/session'
        WHEN ads_per_session < 5 THEN '4-5 ads/session'
        ELSE '5+ ads/session'
    END AS frequency_tier,
    COUNT(listener_id) AS listener_count,
    ROUND(AVG(ads_per_session), 2) AS avg_ads_per_session,
    ROUND(AVG(avg_episode_completion_pct), 1) AS avg_completion_pct,
    ROUND(AVG(avg_ad_skip_rate), 2) AS avg_skip_rate,
    ROUND(AVG(revenue_generated), 2) AS avg_revenue_per_listener,
    ROUND(SUM(revenue_generated), 2) AS total_revenue_in_tier
FROM listener_ad_frequency
GROUP BY frequency_tier
ORDER BY avg_ads_per_session;
```

**Result interpretation:**
- **Sweet spot is 2-4 ads/session** — revenue and experience balanced
- 5+ ads: tiny revenue lift but skip rate jumps to 55%+
- **Recommendation:** set frequency cap at 3-3.5 ads/session

---

## Query 20: Listener Segment Satisfaction Scoring

**Business context:**
The retention team needs to identify **which listener cohorts are churning**. If "Tech_Enthusiast" listeners suddenly see completion rates drop and skip rates rise, that may be a leading indicator of churn. This query produces a "health score" per segment.

**Industry knowledge:**
- **Composite Score:** weights multiple metrics into a single score for ranking
- **Cohort Retention:** retention measured by cohort, not individual

**Category:** Listener Experience
**Difficulty:** Advanced
**Business role:** Platform UX

**Approach:**
Chain `listener_segment → listener → play_session` `LEFT JOIN ad_impression`. The CTE `segment_engagement` computes per-segment completion rate, sessions per listener, ad skip rate, and avg listening hours; the outer query uses a **weighted formula** to combine them into one "satisfaction score": completion × 40 + frequency tier × 30 + (1 − skip rate) × 30. Grain = one row per segment. `WHERE` limits to last 30 days; `HAVING listener_count >= 50` filters small cohorts. Use `CASE` to bucket "healthy / watch / risk" and identify segments that are churning.

```sql
WITH segment_engagement AS (
    SELECT
        ls.segment_name,
        COUNT(DISTINCT l.id) AS listener_count,
        COUNT(DISTINCT ps.id) AS total_sessions,
        ROUND(AVG(ps.completion_percentage), 1) AS avg_completion_pct,
        ROUND(COUNT(DISTINCT ps.id) * 1.0 / NULLIF(COUNT(DISTINCT l.id), 0), 1) AS sessions_per_listener,
        ROUND(AVG(CASE WHEN ai.was_skipped THEN 1.0 ELSE 0.0 END), 2) AS avg_ad_skip_rate,
        ROUND(AVG(l.total_listening_hours), 1) AS avg_listening_hours
    FROM listener_segment ls
    JOIN listener l ON ls.listener_id = l.id
    JOIN play_session ps ON l.id = ps.listener_id
    LEFT JOIN ad_impression ai ON ps.id = ai.play_session_id
    WHERE ps.session_start_time >= DATE('2026-06-21', '-30 days')
    GROUP BY ls.segment_name
    HAVING listener_count >= 50
)
SELECT
    segment_name,
    listener_count,
    sessions_per_listener,
    avg_completion_pct,
    avg_ad_skip_rate,
    avg_listening_hours,
    -- Satisfaction score: completion 40% + frequency 30% + ad tolerance 30%
    ROUND(
        (avg_completion_pct / 100.0) * 40 +
        (CASE WHEN sessions_per_listener >= 10 THEN 30
              WHEN sessions_per_listener >= 5 THEN 20
              ELSE 10 END) +
        ((1 - avg_ad_skip_rate) * 30),
    1) AS satisfaction_score,
    CASE
        WHEN (avg_completion_pct / 100.0) * 40 +
             (CASE WHEN sessions_per_listener >= 10 THEN 30 WHEN sessions_per_listener >= 5 THEN 20 ELSE 10 END) +
             ((1 - avg_ad_skip_rate) * 30) >= 75 THEN 'HEALTHY'
        WHEN (avg_completion_pct / 100.0) * 40 +
             (CASE WHEN sessions_per_listener >= 10 THEN 30 WHEN sessions_per_listener >= 5 THEN 20 ELSE 10 END) +
             ((1 - avg_ad_skip_rate) * 30) >= 60 THEN 'WATCH trend'
        ELSE 'AT RISK: intervene'
    END AS segment_health
FROM segment_engagement
ORDER BY satisfaction_score DESC;
```

**Result interpretation:**
- Healthy segments: Tech_Enthusiast, Finance_Savvy
- At-risk: possibly Frequent_Traveler (less business travel) — launch a targeted retention push

---

## Query 21: Auction Competition Intensity Heatmap

**Business context:**
The market analysis team wants to visualize **competition intensity across inventory types**. Tech mid-roll averages 8 bidders (brutal); Comedy post-roll only 2 (inventory underpriced).

**Industry knowledge:**
- **Seller's Market:** scarce inventory, platform has the upper hand
- **Buyer's Market:** abundant inventory, advertisers have the upper hand
- **Bid Spread:** wider spread = more disagreement on valuation, higher auction efficiency

**Category:** Auction Dynamics
**Difficulty:** Advanced
**Business role:** Platform analyst

**Approach:**
Chain `ad_impression → ad_auction_log`, then loop back to `episode_ad_slot → ad_slot_template` for slot type and `play_session → podcast_episode → podcast` for show category. The CTE `auction_competition` **must first compute bidders, max bid, min bid, and spread per impression (`GROUP BY ai.id`)**; mixing across impressions would be wrong. The outer query then aggregates by "category × slot type." `COUNT(DISTINCT campaign_id)` is the bidder count per auction. Grain: inner = one row per impression, outer = one row per (category, slot). `CASE` tiers competition into brutal / strong / average / weak — a heatmap.

```sql
WITH auction_competition AS (
    SELECT
        p.category AS podcast_category,
        ast.slot_type,
        ai.id AS impression_id,
        COUNT(DISTINCT aal.campaign_id) AS bidder_count,
        MAX(aal.bid_cpm) AS highest_bid,
        MIN(aal.bid_cpm) AS lowest_bid,
        MAX(aal.bid_cpm) - MIN(aal.bid_cpm) AS bid_spread
    FROM ad_impression ai
    JOIN ad_auction_log aal ON ai.id = aal.impression_id
    JOIN episode_ad_slot eas ON ai.ad_slot_id = eas.id
    JOIN ad_slot_template ast ON eas.slot_template_id = ast.id
    JOIN play_session ps ON ai.play_session_id = ps.id
    JOIN podcast_episode pe ON ps.episode_id = pe.id
    JOIN podcast p ON pe.podcast_id = p.id
    GROUP BY p.category, ast.slot_type, ai.id
)
SELECT
    podcast_category,
    slot_type,
    COUNT(impression_id) AS total_auctions,
    ROUND(AVG(bidder_count), 1) AS avg_bidders_per_auction,
    ROUND(AVG(highest_bid), 2) AS avg_winning_bid,
    ROUND(AVG(lowest_bid), 2) AS avg_floor_bid,
    ROUND(AVG(bid_spread), 2) AS avg_bid_spread,
    CASE
        WHEN AVG(bidder_count) >= 6 THEN 'BRUTAL: 6+ bidders (seller market)'
        WHEN AVG(bidder_count) >= 4 THEN 'STRONG: 4-5 bidders (balanced)'
        WHEN AVG(bidder_count) >= 2 THEN 'AVERAGE: 2-3 bidders (buyer market)'
        ELSE 'WEAK: <2 bidders (inventory underpriced)'
    END AS competition_intensity
FROM auction_competition
GROUP BY podcast_category, slot_type
ORDER BY avg_bidders_per_auction DESC;
```

**Result interpretation:**
- **Mid-roll** has the most bidders (most-in-demand by design) → mostly "BRUTAL (6+)" or "STRONG"; combined with the highest eCPM → biggest pricing headroom.
- **Post-roll** has the fewest bidders → mostly "AVERAGE (2-3) buyer market"; low reach, sales can expand into DTC advertisers to fill it.
- Note: this dataset models bidder count by slot demand (mid 4-8 / pre 2-6 / post 2-4), so the "mid is most-demanded" and "mid is most valuable" narratives are consistent.

---

## Query 22: Second-Price Auction Efficiency Validation

**Business context:**
The product team needs to validate that **the second-price auction code has no bugs**. In theory the winner should pay "second price + $0.01." If average overcharge is well above $0.05, the code is overcharging → advertiser complaints.

**Industry knowledge:**
- **Vickrey Auction:** second-price auction; proposed by 1996 Nobel laureate William Vickrey
- **Truthful Bidding:** the second-price mechanism lets advertisers "bid their true valuation" — they won't overpay anyway
- **Efficient Allocation:** optimal resource allocation — those who truly value it most get it

**Category:** Auction Dynamics
**Difficulty:** Intermediate
**Business role:** Platform analyst

**Approach:**
Uses only `ad_impression → ad_auction_log`. The CTE `auction_pricing` uses `MAX(CASE WHEN bid_rank=1/2 THEN bid_cpm END)` to "pivot" the first and second prices into two columns per impression, and tags each auction as single- or multi-bidder. The outer query aggregates by auction type to verify that "actual charge − second price" ≈ $0.01. Grain: inner = one row per impression, outer = one row each for single-bidder / multi-bidder. **Key: only judge overcharge for multi-bidder auctions** — single-bidder auctions have no second price (`second_bid` is NULL) and are billed at a discount on the winning bid, so they don't participate in the overcharge check. Healthy value: overcharge ≈ $0.01.

```sql
WITH auction_pricing AS (
    SELECT
        ai.id AS impression_id,
        MAX(CASE WHEN aal.bid_rank = 1 THEN aal.bid_cpm END) AS first_bid,
        MAX(CASE WHEN aal.bid_rank = 2 THEN aal.bid_cpm END) AS second_bid,
        ai.winning_bid_cpm,
        ai.actual_charge_cpm,
        CASE
            WHEN COUNT(DISTINCT aal.campaign_id) = 1 THEN 'Single_Bidder'
            ELSE 'Multi_Bidder'
        END AS auction_type
    FROM ad_impression ai
    JOIN ad_auction_log aal ON ai.id = aal.impression_id
    GROUP BY ai.id, ai.winning_bid_cpm, ai.actual_charge_cpm
)
SELECT
    auction_type,
    COUNT(impression_id) AS total_auctions,
    ROUND(AVG(first_bid), 2) AS avg_winning_bid,
    ROUND(AVG(second_bid), 2) AS avg_second_bid,
    ROUND(AVG(actual_charge_cpm), 2) AS avg_actual_charge,
    ROUND(AVG(first_bid - actual_charge_cpm), 2) AS avg_winner_savings,
    -- Only compute "overcharge" for multi-bidder auctions; single-bidder has no second price (second_bid is NULL)
    ROUND(AVG(CASE WHEN auction_type = 'Multi_Bidder' THEN actual_charge_cpm - second_bid END), 2) AS avg_overpayment_vs_second,
    ROUND(100.0 * AVG(first_bid - actual_charge_cpm) / NULLIF(AVG(first_bid), 0), 1) AS pct_savings_for_winner,
    CASE
        WHEN auction_type = 'Single_Bidder' THEN 'Single-bidder: no second price, not evaluated'
        WHEN AVG(actual_charge_cpm - second_bid) BETWEEN 0 AND 0.05 THEN 'HEALTHY: billed at second price'
        WHEN AVG(actual_charge_cpm - second_bid) > 0.05 THEN 'ANOMALY: overcharging!'
        ELSE 'WARN: check logic'
    END AS auction_health
FROM auction_pricing
GROUP BY auction_type;
```

**Result interpretation:**
- Multi-bidder: `avg_overpayment_vs_second` should be $0.01-0.02 (normal)
- Single-bidder: no second price → billed at a 10% discount on the winning bid

---

## Query 23: Budget Pacing Effectiveness

**Business context:**
Advertisers use budget pacing to **spend evenly** across the campaign window. The platform needs to assess the algorithm: are any campaigns burning too fast (50% spent in 10 days)? Or too slow (only 20% spent in 50 days)?

**Industry knowledge:**
- **Pacing Algorithm:** an industry-standard algorithm balancing "burn out too early, no volume" vs. "don't burn out, waste budget"
- **Pacing Variance:** actual spend % minus time elapsed %. > +15 = burning too fast; < -15 = burning too slow

**Category:** Auction Dynamics
**Difficulty:** Advanced
**Business role:** Platform analyst

**Approach:**
Chain `ad_campaign → advertiser` `LEFT JOIN ad_creative → ad_impression`. The CTE `campaign_pacing` simultaneously computes "time elapsed %" (using `JULIANDAY` for day ratios) and "budget spent %"; the outer query computes `pacing_variance = spent% − elapsed%` and tiers it. **Budget uses `window_budget_usd`**, otherwise the spend rate is always ~0% and every campaign gets flagged "burning too slow." `WHERE` keeps only active campaigns crossing today, with `days_elapsed >= 3` (too new = meaningless). Grain = one row per campaign. `ORDER BY ABS(variance) DESC` puts the biggest deviations first.

```sql
WITH campaign_pacing AS (
    SELECT
        ac.id AS campaign_id,
        ac.campaign_name,
        a.company_name,
        ac.start_date,
        ac.end_date,
        ac.window_budget_usd,
        (JULIANDAY(ac.end_date) - JULIANDAY(ac.start_date) + 1) AS total_days,
        (JULIANDAY('2026-06-21') - JULIANDAY(ac.start_date) + 1) AS days_elapsed,
        ROUND(100.0 * (JULIANDAY('2026-06-21') - JULIANDAY(ac.start_date) + 1) /
            (JULIANDAY(ac.end_date) - JULIANDAY(ac.start_date) + 1), 1) AS pct_time_elapsed,
        ROUND(SUM(ai.actual_charge_cpm / 1000.0), 2) AS spent_to_date,
        -- Use window_budget_usd (window-deployed budget) to get a meaningful burn %, otherwise always ~0% → everything flagged "burning too slow"
        ROUND(100.0 * SUM(ai.actual_charge_cpm / 1000.0) / ac.window_budget_usd, 1) AS pct_budget_spent
    FROM ad_campaign ac
    JOIN advertiser a ON ac.advertiser_id = a.id
    LEFT JOIN ad_creative acr ON ac.id = acr.campaign_id
    LEFT JOIN ad_impression ai ON acr.id = ai.creative_id
    WHERE ac.start_date <= DATE('2026-06-21')
        AND ac.end_date >= DATE('2026-06-21')
    GROUP BY ac.id, ac.campaign_name, a.company_name, ac.start_date, ac.end_date, ac.window_budget_usd
)
SELECT
    campaign_name,
    company_name,
    total_days AS campaign_duration_days,
    days_elapsed,
    pct_time_elapsed,
    window_budget_usd,
    spent_to_date,
    pct_budget_spent,
    ROUND(pct_budget_spent - pct_time_elapsed, 1) AS pacing_variance,
    CASE
        WHEN pct_budget_spent > pct_time_elapsed + 15 THEN 'BURNING TOO FAST: early-exhaustion risk'
        WHEN pct_budget_spent > pct_time_elapsed + 8 THEN 'slightly fast'
        WHEN pct_budget_spent < pct_time_elapsed - 15 THEN 'BURNING TOO SLOW: budget will not deploy'
        WHEN pct_budget_spent < pct_time_elapsed - 8 THEN 'slightly slow'
        ELSE 'pacing on track'
    END AS pacing_status
FROM campaign_pacing
WHERE days_elapsed >= 3
ORDER BY ABS(pct_budget_spent - pct_time_elapsed) DESC;
```

**Result interpretation:**
- Burning too fast → reduce bid aggressiveness
- Burning too slow → raise bids or loosen targeting

---

## Query 24: Bid Elasticity Analysis

**Business context:**
Adobe wants to run a bid adjustment experiment: **going from $20 to $24 (+20%), how many more auctions can we win?** This query plots the "bid → win rate" elasticity curve.

**Industry knowledge:**
- **Elasticity:** an econ concept — output change rate / input change rate
- **Marginal Win Rate:** additional win-rate gained per extra $1 bid
- **Diminishing Returns:** beyond a certain point, adding more money has little effect

**Category:** Auction Dynamics
**Difficulty:** Advanced
**Business role:** Platform analyst

**Approach:**
Chain `ad_auction_log → ad_campaign → advertiser`, `WHERE` locks to one advertiser. The CTE `bid_performance_buckets` computes win rate per bid bucket; the outer query uses window function `LAG() OVER (ORDER BY avg_bid_in_bucket)` to grab the prior bucket's win rate and bid, computing "marginal elasticity = win-rate gain / bid increase." Grain = one row per bid bucket. **LAG is the key tool for computing marginal elasticity** (offsetting adjacent buckets and subtracting). Elasticity denominator uses `NULLIF` to prevent zero. The bucket with the highest elasticity = the best place to raise bids; once elasticity drops sharply = no point adding more.

```sql
WITH bid_performance_buckets AS (
    SELECT
        ac.advertiser_id,
        a.company_name,
        aal.campaign_id,
        CASE
            WHEN aal.bid_cpm < 15 THEN '$0-15'
            WHEN aal.bid_cpm < 20 THEN '$15-20'
            WHEN aal.bid_cpm < 25 THEN '$20-25'
            WHEN aal.bid_cpm < 30 THEN '$25-30'
            ELSE '$30+'
        END AS bid_bucket,
        ROUND(AVG(aal.bid_cpm), 2) AS avg_bid_in_bucket,
        COUNT(*) AS total_bids,
        SUM(CASE WHEN aal.won_auction THEN 1 ELSE 0 END) AS auctions_won,
        ROUND(100.0 * SUM(CASE WHEN aal.won_auction THEN 1 ELSE 0 END) / COUNT(*), 1) AS win_rate_pct
    FROM ad_auction_log aal
    JOIN ad_campaign ac ON aal.campaign_id = ac.id
    JOIN advertiser a ON ac.advertiser_id = a.id
    WHERE a.company_name = 'Adobe'
    GROUP BY ac.advertiser_id, a.company_name, aal.campaign_id, bid_bucket
)
SELECT
    company_name,
    bid_bucket,
    avg_bid_in_bucket,
    total_bids,
    auctions_won,
    win_rate_pct,
    LAG(win_rate_pct) OVER (ORDER BY avg_bid_in_bucket) AS prev_bucket_win_rate,
    ROUND(win_rate_pct - LAG(win_rate_pct) OVER (ORDER BY avg_bid_in_bucket), 1) AS win_rate_gain,
    ROUND((avg_bid_in_bucket - LAG(avg_bid_in_bucket) OVER (ORDER BY avg_bid_in_bucket)), 2) AS bid_increase,
    ROUND((win_rate_pct - LAG(win_rate_pct) OVER (ORDER BY avg_bid_in_bucket)) /
        NULLIF((avg_bid_in_bucket - LAG(avg_bid_in_bucket) OVER (ORDER BY avg_bid_in_bucket)), 0), 2) AS win_rate_elasticity
FROM bid_performance_buckets
ORDER BY avg_bid_in_bucket;
```

**Result interpretation:**
- Highest elasticity range (~$22-24) = the most cost-effective bid hike
- Above $28, elasticity collapses → adding more money is pointless

---

## Query 25: Emerging Advertiser Industry Trends

**Business context:**
The sales strategy team wants to find **the next industry to push into for advertiser acquisition**. Which industry has rapidly rising **month-over-month (MoM)** spend? Which is declining? This query identifies fast-growing industries.
(Note: in real business, quarterly QoQ is more common, but this dataset only has 60 days, so MoM is the best we can do; the methodology is the same.)

**Industry knowledge:**
- **MoM (Month-over-Month):** this month vs. last month (when data span is sufficient, swap to QoQ for quarterly)
- **Vertical:** an advertiser's industry segment
- **Sales Resource Allocation:** the sales org reallocates reps toward fast-growing verticals

**Category:** Strategic Insights
**Difficulty:** Intermediate
**Business role:** Platform strategy

**Approach:**
Chain `ad_impression → ad_creative → ad_campaign → advertiser`; the CTE `monthly_spend` aggregates spend by "industry × month." The outer query uses `LAG() OVER (PARTITION BY industry_vertical ORDER BY month)` to compute MoM. **`PARTITION BY` keeps each industry's MoM independent** — no cross-contamination. **Why MoM, not QoQ**: this dataset has only 60 days (~3 calendar months), so QoQ would fall in the same quarter and LAG would be all NULL — methodology unchanged, swap to QoQ when the data span allows. Grain = industry × month. `CASE` tiers into breakout / high growth / declining.

```sql
-- Note: this dataset has only 60 days (~3 calendar months), so QoQ would fall in the same quarter →
-- LAG would be all NULL. Switched to MoM, which produces 2-3 comparison points within the 60-day window.
WITH monthly_spend AS (
    SELECT
        a.industry_vertical,
        DATE(ai.impression_time, 'start of month') AS month,
        ROUND(SUM(ai.actual_charge_cpm / 1000.0), 2) AS total_spend,
        COUNT(DISTINCT ac.advertiser_id) AS active_advertisers,
        COUNT(ai.id) AS total_impressions
    FROM ad_impression ai
    JOIN ad_creative acr ON ai.creative_id = acr.id
    JOIN ad_campaign ac ON acr.campaign_id = ac.id
    JOIN advertiser a ON ac.advertiser_id = a.id
    GROUP BY a.industry_vertical, month
)
SELECT
    industry_vertical,
    month AS current_month,
    total_spend AS current_month_spend,
    active_advertisers,
    LAG(total_spend) OVER (PARTITION BY industry_vertical ORDER BY month) AS prev_month_spend,
    ROUND(total_spend - LAG(total_spend) OVER (PARTITION BY industry_vertical ORDER BY month), 2) AS spend_change,
    ROUND(100.0 * (total_spend - LAG(total_spend) OVER (PARTITION BY industry_vertical ORDER BY month)) /
        NULLIF(LAG(total_spend) OVER (PARTITION BY industry_vertical ORDER BY month), 0), 1) AS growth_rate_pct,
    CASE
        WHEN 100.0 * (total_spend - LAG(total_spend) OVER (PARTITION BY industry_vertical ORDER BY month)) /
            NULLIF(LAG(total_spend) OVER (PARTITION BY industry_vertical ORDER BY month), 0) >= 50 THEN 'BREAKOUT: prioritize expansion'
        WHEN 100.0 * (total_spend - LAG(total_spend) OVER (PARTITION BY industry_vertical ORDER BY month)) /
            NULLIF(LAG(total_spend) OVER (PARTITION BY industry_vertical ORDER BY month), 0) >= 20 THEN 'HIGH GROWTH: invest'
        WHEN 100.0 * (total_spend - LAG(total_spend) OVER (PARTITION BY industry_vertical ORDER BY month)) /
            NULLIF(LAG(total_spend) OVER (PARTITION BY industry_vertical ORDER BY month), 0) <= -20 THEN 'DECLINING: investigate'
        ELSE 'STABLE'
    END AS trend_status
FROM monthly_spend
WHERE month >= DATE('2026-06-21', '-6 months')
ORDER BY month DESC, growth_rate_pct DESC;
```

**Result interpretation:**
- SaaS / FinTech typically growing 40-80%
- Emerging verticals like AI Tools / Web3 could be 150%+
- For declining verticals — separate macro effects (the whole industry is hurting) from platform-specific issues (we lost share to competitors)

---

## Query 26: Show Category Growth Forecast

**Business context:**
The content partnerships team wants to forecast **which show categories to sign next year**. Is Tech saturated? Is Mental Health the next blue ocean? This query forecasts revenue 6 months out based on historical trends.

**Industry knowledge:**
- **Compound Growth:** MoM × 6 rather than simple linear extrapolation
- **Creator Recruitment:** the content BD team's signing list shapes what the platform looks like 2 years from now

**Category:** Strategic Insights
**Difficulty:** Advanced
**Business role:** Platform strategy

**Approach:**
Use the aggregate `revenue_settlement → podcast`; the CTE aggregates by "category × month." This is **the most window-function-dense query in the whole doc**: the outer query first uses multiple `LAG(total_revenue, 1/2)` to grab revenue from 1 and 2 months back, then wraps the MoM formula inside `AVG(...) OVER (PARTITION BY category ROWS BETWEEN 2 PRECEDING AND CURRENT ROW)` for a 3-month moving average growth. Grain = category × month. Note: SQLite supports this "LAG nested inside AVG OVER" pattern, but be careful that each window has `PARTITION BY category`. Sort by 3-month average growth to set signing priorities.

```sql
WITH monthly_category_revenue AS (
    SELECT
        p.category,
        DATE(rs.settlement_date, 'start of month') AS month,
        COUNT(DISTINCT p.id) AS podcast_count,
        SUM(rs.total_impressions) AS total_impressions,
        ROUND(SUM(rs.total_revenue_usd), 2) AS total_revenue,
        ROUND(AVG(rs.avg_cpm), 2) AS avg_cpm,
        ROUND(AVG(rs.fill_rate), 3) AS avg_fill_rate
    FROM revenue_settlement rs
    JOIN podcast p ON rs.podcast_id = p.id
    GROUP BY p.category, month
)
SELECT
    category,
    podcast_count,
    month AS latest_month,
    total_revenue AS current_month_revenue,
    LAG(total_revenue, 1) OVER (PARTITION BY category ORDER BY month) AS prev_month_revenue,
    LAG(total_revenue, 2) OVER (PARTITION BY category ORDER BY month) AS two_months_ago_revenue,
    ROUND(100.0 * (total_revenue - LAG(total_revenue, 1) OVER (PARTITION BY category ORDER BY month)) /
        NULLIF(LAG(total_revenue, 1) OVER (PARTITION BY category ORDER BY month), 0), 1) AS mom_growth_pct,
    ROUND(AVG(100.0 * (total_revenue - LAG(total_revenue, 1) OVER (PARTITION BY category ORDER BY month)) /
        NULLIF(LAG(total_revenue, 1) OVER (PARTITION BY category ORDER BY month), 0))
        OVER (PARTITION BY category ROWS BETWEEN 2 PRECEDING AND CURRENT ROW), 1) AS three_month_avg_growth_pct,
    CASE
        WHEN AVG(100.0 * (total_revenue - LAG(total_revenue, 1) OVER (PARTITION BY category ORDER BY month)) /
            NULLIF(LAG(total_revenue, 1) OVER (PARTITION BY category ORDER BY month), 0))
            OVER (PARTITION BY category ROWS BETWEEN 2 PRECEDING AND CURRENT ROW) >= 10 THEN 'HIGH PRIORITY: aggressive recruitment'
        WHEN AVG(100.0 * (total_revenue - LAG(total_revenue, 1) OVER (PARTITION BY category ORDER BY month)) /
            NULLIF(LAG(total_revenue, 1) OVER (PARTITION BY category ORDER BY month), 0))
            OVER (PARTITION BY category ROWS BETWEEN 2 PRECEDING AND CURRENT ROW) >= 5 THEN 'MEDIUM PRIORITY: maintain pipeline'
        ELSE 'STABLE: opportunistic signing'
    END AS recruitment_strategy
FROM monthly_category_revenue
WHERE month >= DATE('2026-06-21', '-6 months')
ORDER BY three_month_avg_growth_pct DESC;
```

**Result interpretation:**
- High-growth: Tech / Finance 12-18% MoM → invest heavily to sign top creators
- Mature: News 3-5% → don't actively pursue

---

## Query 27: Listener Behavior Shift Detection

**Business context:**
The product strategy team needs **early warning of listener behavior shifts**. For example: playback-speed adoption suddenly jumps 10pp → listeners want efficiency → should we ship "auto-speed-up"? Smart speaker share rising → optimize voice UX.

**Industry knowledge:**
- **Behavior Shift Detection:** statistical methods to detect significant KPI changes
- **Product Roadmap Implications:** these shifts directly shape next quarter's product direction

**Category:** Strategic Insights
**Difficulty:** Advanced
**Business role:** Platform strategy

**Approach:**
Main table `play_session` `LEFT JOIN ad_impression`. The CTE `behavior_trends` aggregates monthly: playback-speed share, device-type shares, ad skip rate, etc. The outer query uses `LAG()` to compare to the prior month and `CASE` to trigger alerts. `WHERE` limits to last 6 months. Grain = one row per month. Share metrics use `SUM(CASE WHEN ... THEN 1 ELSE 0 END) / COUNT(*)` (e.g., `playback_speed > 1.0` for the accelerated-playback share). Any metric whose month-over-month jump exceeds the threshold (completion ±5pp / playback speed ±8pp / skip rate ±0.1) triggers an alert — early warning for the product roadmap.

```sql
WITH behavior_trends AS (
    SELECT
        DATE(ps.session_start_time, 'start of month') AS month,
        COUNT(DISTINCT ps.id) AS total_sessions,
        ROUND(AVG(ps.completion_percentage), 1) AS avg_completion_pct,
        ROUND(100.0 * SUM(CASE WHEN ps.playback_speed > 1.0 THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct_accelerated_playback,
        ROUND(100.0 * SUM(CASE WHEN ps.device_type = 'mobile' THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct_mobile,
        ROUND(100.0 * SUM(CASE WHEN ps.device_type = 'smart_speaker' THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct_smart_speaker,
        ROUND(100.0 * SUM(CASE WHEN ps.device_type = 'desktop' THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct_desktop,
        ROUND(AVG(CASE WHEN ai.was_skipped THEN 1.0 ELSE 0.0 END), 2) AS avg_ad_skip_rate
    FROM play_session ps
    LEFT JOIN ad_impression ai ON ps.id = ai.play_session_id
    WHERE ps.session_start_time >= DATE('2026-06-21', '-6 months')
    GROUP BY month
)
SELECT
    month,
    total_sessions,
    avg_completion_pct,
    LAG(avg_completion_pct) OVER (ORDER BY month) AS prev_month_completion,
    ROUND(avg_completion_pct - LAG(avg_completion_pct) OVER (ORDER BY month), 1) AS completion_change,
    pct_accelerated_playback,
    LAG(pct_accelerated_playback) OVER (ORDER BY month) AS prev_month_accelerated,
    ROUND(pct_accelerated_playback - LAG(pct_accelerated_playback) OVER (ORDER BY month), 1) AS accelerated_change,
    pct_mobile,
    pct_smart_speaker,
    pct_desktop,
    avg_ad_skip_rate,
    CASE
        WHEN ABS(avg_completion_pct - LAG(avg_completion_pct) OVER (ORDER BY month)) >= 5 THEN 'ALERT: completion rate shift'
        WHEN ABS(pct_accelerated_playback - LAG(pct_accelerated_playback) OVER (ORDER BY month)) >= 8 THEN 'ALERT: playback speed shift'
        WHEN ABS(avg_ad_skip_rate - LAG(avg_ad_skip_rate) OVER (ORDER BY month)) >= 0.1 THEN 'ALERT: ad tolerance shift'
        ELSE 'stable'
    END AS behavior_alert
FROM behavior_trends
ORDER BY month DESC;
```

**Result interpretation:**
- Playback speed 28% → 38% (+10pp) → product should consider an auto-speed-up feature
- Smart speakers 18% → 26% → bump voice UX optimization priority
- Skip rate 0.42 → 0.53 (+11pp) → ad fatigue platform-wide → urgent frequency cut

---

# Wrap-Up: Core Mental Models Every Intern Should Have

After reading these 27 queries, you should have internalized:

### 1. Three-Way Interest Asymmetry

| Role | Wants | Fears |
|------|------|--------|
| Platform | Big revenue | Listener churn, advertiser pullout |
| Advertiser | High conversion / low CPA | Money spent with no results |
| Host | High RPM | Platform takes too much, listeners leave |
| Listener | No ads / good experience | Annoying ads / repeated ads |

### 2. Core Trade-offs Are Always Present
- **Fill rate vs. price:** sell out and prices crash; don't sell and inventory goes to waste
- **Ad frequency vs. listener experience:** more ads = more revenue, too many ads = skipping
- **Precise targeting vs. reach:** too narrow and the budget can't be spent, too broad and you waste money

### 3. The Three Basic Analytical Moves
1. **Diagnose** — what's the current state? Q1, Q2, Q4
2. **Benchmark** — how do we compare to peers? Q13
3. **Forecast** — where's it heading? Q15, Q26

### 4. Business Speak vs. Technical Speak

| Technical language | Business language (how to phrase it to PMs / execs) |
|---------|--------------------------------------|
| "avg_realized_cpm is 50% above base_cpm_rate" | "The market is paying way more than our floor on this slot; recommend a 30% price increase" |
| "fill_rate is 65%" | "We're failing to sell 1/3 of overnight slots, losing $X thousand per day" |
| "win_rate_elasticity = 4.6 at $20" | "At a $20 bid, each extra $1 wins us 4.6% more auctions" |

---

**Version:** v1.0
**Last updated:** 2026-06-21

> 💡 **Next step:** Treat this document as a dictionary you keep flipping through. Every time you finish an ad-hoc data request, come back and see how the similar query was written — **reuse + adapt** is 10× faster than writing from scratch.
