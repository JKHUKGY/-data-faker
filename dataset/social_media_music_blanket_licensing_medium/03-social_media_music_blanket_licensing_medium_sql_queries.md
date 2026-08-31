# SQL Query Documentation

This document covers the `social_media_music_blanket_licensing_medium` dataset. See `01-social_media_music_blanket_licensing_medium_business_context.md` for business context and `02-social_media_music_blanket_licensing_medium_er_document.md` for the data model.

## REFERENCE_DATE Convention

Every "today / current snapshot" concept in this dataset is anchored to a fixed reference date, **`2026-06-30`**. Anywhere a query needs "the current date," that date is hard-coded as a literal instead of using `DATE('now')` — that way the results are identical and reproducible no matter who reruns these queries, or when.

## How to Use This Document

You've just joined ReelWave's Rights & Licensing Compliance team, and the Director has handed you these 20 questions as your onboarding assignment for the week. Each question has five fixed parts:

1. **Business Context** — who is asking this question, why now, and what decision the answer supports.
2. **Tags** — SQL category, difficulty, and the business role asking the question.
3. **Approach** — before writing any SQL, think through which tables to join, what grain to aggregate at, and any join traps to watch for.
4. **SQL** — a query you can run directly against the generated SQLite database.
5. **Expected Results and Conclusions** — what the results should look like, which business question they map to, and what to do next.

Every question traces back to one of the business problems (Q1-Q4) listed in Section 5 of the business context document. These SQL queries aren't just meant to be run — they're a demonstration of how a real analyst thinks through this kind of problem.

## Query Index

| # | Title | Business Role | SQL Category | Difficulty |
|------|------|----------|----------|----------|
| 1 | Current-month label catalog usage share vs. contracted assumption | Rights & Licensing Compliance Officer | Join + Aggregation | Basic |
| 2 | Trailing 3-month average share drift ranking | Director of Rights Compliance | Window Function | Intermediate |
| 3 | Effective rate calculation and ranking by label | VP of Finance (FP&A) | CTE | Intermediate |
| 4 | MFN clause breach detection | General Counsel | CTE + Subquery | Advanced |
| 5 | Rights conflict flag status distribution | Rights & Licensing Compliance Officer | Aggregation | Basic |
| 6 | SLA-overdue flag count and revenue exposure | Director of Rights Compliance | Date/Time + Aggregation | Intermediate |
| 7 | Sampling-driven rights conflicts by source label | Head of Label Relations | Join (Self-Join) | Basic |
| 8 | Top 10 longest-overdue rights conflicts | Rights & Licensing Compliance Officer | Window Function | Intermediate |
| 9 | Creator Fund effective payout rate by spike-window alignment status | Creator Fund Program Manager | CTE + Aggregation | Advanced |
| 10 | Week-over-week payout change for a single split-week case | Creator Fund Program Manager | Window Function (LAG) | Intermediate |
| 11 | Total Creator Fund spend broken down by creator tier | Creator Fund Program Manager | Aggregation | Basic |
| 12 | Daily view curve vs. weekly payout for a single viral remix | Rights & Licensing Compliance Officer | Join + Date/Time | Intermediate |
| 13 | Label portfolio structure overview | Head of Label Relations | Aggregation | Basic |
| 14 | Cumulative contract payments actually made vs. amount owed on a pro-rata time basis | VP of Finance (FP&A) | Join + Date/Time | Intermediate |
| 15 | Catalog composition: official tracks vs. UGC remixes | Rights & Licensing Compliance Officer | Aggregation | Basic |
| 16 | Top 5 / bottom 5 labels by share drift | Director of Rights Compliance | Window Function | Intermediate |
| 17 | Quarterly compliance risk priority list | Director of Rights Compliance | CTE (multi-table rollup) | Advanced |
| 18 | Keyword pattern matching on remix sound titles | Rights & Licensing Compliance Officer | Pattern Matching | Basic |
| 19 | Monthly trend of platform-wide attributable catalog usage | Head of Label Relations | Date/Time Trend | Basic |
| 20 | Renewal priority list (approaching expiration + share drift) | Head of Label Relations | CTE + Window Function | Advanced |

---

## Query 1: Current-month label catalog usage share vs. contracted assumption

**Business Context**

You're the Rights & Licensing Compliance Officer, and the Director has asked you to prepare the first slide for next week's quarterly compliance review: put each label's "how much they're actually being used right now" side by side with "how much we assumed they'd be used at contract signing." This is the single most important table in the whole report — if the gap is large, every subsequent discussion about renewals, back payments, and revenue exposure will revolve around it. It's the end of the quarter, which is exactly the right time to look back at the past month of data.

**Tags**: Join + Aggregation | Basic | Rights & Licensing Compliance Officer

**Approach**

Which label a given video "used" depends on one of two scenarios: the video directly uses that label's official track, or the video uses a UGC remix sampled from that label's official track. So the first step is a CTE that "unpacks" the `sound` table into a list of "sounds attributable to a label" — using `UNION ALL` to combine "official tracks themselves" with "remixes that sample an official track" (found by tracing `source_sound_id` back to the source official track and then to its `primary_label_id`). Second, join this list against `sound_monthly_usage` and sum the current month's `video_count` by label. Third, compute the total "attributable catalog" volume for the month as the denominator, divide to get the actual share, and subtract `label_blanket_license.usage_share_assumption_pct` to get the drift. No window function is needed here — one GROUP BY plus one CROSS JOIN (to fetch the total) is sufficient.

**SQL**

```sql
WITH label_sound AS (
    SELECT
        s.id AS sound_id,
        s.primary_label_id AS label_id
    FROM sound s
    WHERE s.sound_type = 'official_track'

    UNION ALL

    SELECT
        r.id AS sound_id,
        o.primary_label_id AS label_id
    FROM sound r
    JOIN sound o
        ON r.source_sound_id = o.id
    WHERE r.sound_type = 'ugc_remix'
),
month_usage AS (
    SELECT
        ls.label_id,
        SUM(smu.video_count) AS label_video_count
    FROM label_sound ls
    JOIN sound_monthly_usage smu
        ON smu.sound_id = ls.sound_id
    WHERE smu.usage_month = '2026-06-01'
    GROUP BY ls.label_id
),
total AS (
    SELECT SUM(label_video_count) AS total_video_count
    FROM month_usage
)
SELECT
    l.label_name,
    l.label_tier,
    lbl.usage_share_assumption_pct,
    ROUND(mu.label_video_count * 100.0 / t.total_video_count, 2) AS actual_usage_share_pct,
    ROUND(mu.label_video_count * 100.0 / t.total_video_count - lbl.usage_share_assumption_pct, 2) AS drift_pp
FROM month_usage mu
JOIN label l
    ON l.id = mu.label_id
JOIN label_blanket_license lbl
    ON lbl.label_id = l.id
CROSS JOIN total t
ORDER BY drift_pp DESC;
```

**Expected Results and Business Conclusions**

The result is 20 rows (one per label). A positive `drift_pp` means the label is "being used more and more while its annual fee stays flat"; a negative one means "being used less and less while its fee hasn't come down." The labels at the top of the list (roughly 5 "growth"-type labels) should show `drift_pp` between +1 and +4.5 percentage points, the labels at the bottom (roughly 4 "decline"-type labels) between -2 and -4.8 percentage points, and the remaining roughly 11 (including all 3 major labels) within ±1 percentage point. Next step: add the labels with the largest `drift_pp` magnitude to the renewal negotiation priority list (Query 20 produces a more structured version of this) and prepare to re-cost their annual fees in the next round of negotiations.

---

## Query 2: Trailing 3-month average share drift ranking

**Business Context**

After reviewing Query 1's single-month snapshot, the Director of Rights Compliance is worried that any given month's numbers could reflect a one-off fluctuation, and has asked you to recompute using a trailing 3-month average to confirm that the labels at the top aren't there because of "one lucky month," but reflect a sustained trend. This ranking will go directly into next week's briefing to the General Counsel.

**Tags**: Window Function | Intermediate | Director of Rights Compliance

**Approach**

The approach is similar to Query 1, but this time aggregate by both label and month, then use the window function `SUM(...) OVER (PARTITION BY usage_month)` to compute "each month's own total" (you can't use a single global total, since the overall pie grows month over month). Once you have each label's share for each month, average across labels with `AVG` to get the 3-month average actual share, then rank with `RANK() OVER (ORDER BY drift_pp DESC)`. Note that `WHERE usage_month IN (...)` needs the exact first-of-month dates for these 3 months; SQLite stores dates as strings, so you need the full format like `'2026-04-01'` for an exact match.

**SQL**

```sql
WITH label_sound AS (
    SELECT
        s.id AS sound_id,
        s.primary_label_id AS label_id
    FROM sound s
    WHERE s.sound_type = 'official_track'

    UNION ALL

    SELECT
        r.id AS sound_id,
        o.primary_label_id AS label_id
    FROM sound r
    JOIN sound o
        ON r.source_sound_id = o.id
    WHERE r.sound_type = 'ugc_remix'
),
monthly_share AS (
    SELECT
        ls.label_id,
        smu.usage_month,
        SUM(smu.video_count) AS label_video_count,
        SUM(SUM(smu.video_count)) OVER (PARTITION BY smu.usage_month) AS month_total_video_count
    FROM label_sound ls
    JOIN sound_monthly_usage smu
        ON smu.sound_id = ls.sound_id
    WHERE smu.usage_month IN ('2026-04-01', '2026-05-01', '2026-06-01')
    GROUP BY ls.label_id, smu.usage_month
),
label_avg_share AS (
    SELECT
        label_id,
        AVG(label_video_count * 100.0 / month_total_video_count) AS avg_share_pct
    FROM monthly_share
    GROUP BY label_id
)
SELECT
    l.label_name,
    l.label_tier,
    lbl.usage_share_assumption_pct,
    ROUND(las.avg_share_pct, 2) AS avg_actual_share_pct_last3m,
    ROUND(las.avg_share_pct - lbl.usage_share_assumption_pct, 2) AS drift_pp,
    RANK() OVER (ORDER BY las.avg_share_pct - lbl.usage_share_assumption_pct DESC) AS growth_rank
FROM label_avg_share las
JOIN label l
    ON l.id = las.label_id
JOIN label_blanket_license lbl
    ON lbl.label_id = l.id
ORDER BY drift_pp DESC;
```

**Expected Results and Business Conclusions**

The result is 20 rows. `growth_rank = 1` through `5` should consistently correspond to the same labels that showed the fastest share growth in Query 1, with numbers close to the single-month snapshot (confirming this is a sustained trend rather than a one-off). Next step: labels in the top 5 of `growth_rank` whose annual fees haven't been adjusted yet become candidates for a fee renegotiation next quarter; the labels at the bottom (decline-type) become candidates for "consider lowering the annual fee or the share assumption at renewal."

---

## Query 3: Effective rate calculation and ranking by label

**Business Context**

While preparing an annual budget retrospective, the VP of Finance (FP&A) wants to know the "implied unit price" the company is actually paying under blanket licensing — converting each contract's annual fee into "how much we're willing to pay for each percentage point of catalog share we secure" — so it can be compared apples-to-apples across labels and across contract years.

**Tags**: CTE | Intermediate | VP of Finance (FP&A)

**Approach**

The math itself isn't complicated — annual fee divided by the share assumption gives the effective rate — but it's broken out into its own CTE because Query 4's MFN detection needs to reuse the exact same "effective rate" definition. Putting the calculation in a CTE rather than inline in the SELECT guarantees both queries agree on what "effective rate" means, eliminating the risk of two conflicting definitions.

**SQL**

```sql
WITH effective_rate AS (
    SELECT
        lbl.label_id,
        lbl.has_mfn_clause,
        lbl.usage_share_assumption_pct,
        lbl.annual_license_fee_usd,
        lbl.annual_license_fee_usd / lbl.usage_share_assumption_pct AS effective_rate_per_point_usd
    FROM label_blanket_license lbl
)
SELECT
    l.label_name,
    l.label_tier,
    er.has_mfn_clause,
    er.usage_share_assumption_pct,
    er.annual_license_fee_usd,
    ROUND(er.effective_rate_per_point_usd, 0) AS effective_rate_per_point_usd
FROM effective_rate er
JOIN label l
    ON l.id = er.label_id
ORDER BY effective_rate_per_point_usd DESC;
```

**Expected Results and Business Conclusions**

The result is 20 rows, sorted from highest to lowest effective rate. The pattern isn't simply "major > mid > indie" — the real differentiator is **whether the label has MFN protection**:

- The 4 labels with MFN protection and normally priced contracts (2 majors + 2 mid-size labels) have the highest effective rates overall, roughly $840K to $960K per share point — because the MFN clause locks in "our rate can't be worse than anyone else's," these labels get systematically pulled up to the top of the field, and a mid-size label with MFN can easily out-rank some major labels.
- **Northline Aggregator** (an independent aggregator with no MFN protection) breaks into the upper ranks on the strength of an aggressive negotiated rate, at roughly $800K per point.
- **Titan Sound Group** (a major with MFN protection), however, sits at only about $750K per point — below Northline — which is exactly the MFN breach signal Query 4 is built to catch.
- The remaining mid-size labels and independent aggregators without MFN protection are generally lower (roughly $280K to $620K per point).

In other words, the top of the ranking is a mix of "MFN-protected labels + Northline," not a strict function of label size. Next step: hand this ranking to Query 4 for MFN compliance detection.

---

## Query 4: MFN clause breach detection

**Business Context**

Last week the General Counsel received an email from Titan Sound Group's legal team vaguely mentioning they'd "like to revisit our rate terms." The General Counsel suspects this may be laying the groundwork for a breach-of-contract claim, and has asked the Rights & Licensing Compliance team to run the numbers themselves before next week's formal reply: is there any label with MFN (most-favored-nation) protection that is actually receiving a worse effective rate than a label signed later without MFN protection? If so, the team needs to immediately assess the potential retroactive make-good exposure.

**Tags**: CTE + Subquery | Advanced | General Counsel

**Approach**

Determining whether the MFN clause has been breached comes down to two steps: first, find "the highest effective rate among all labels without MFN protection" (via a subquery's `MAX(...)`); second, check every label that does have MFN protection to see whether its own effective rate is lower than the maximum found in step one. If it is, that label should have been "topped up" to that maximum under its MFN clause, but the contract doesn't reflect it — that's a breach. This reuses the `effective_rate` CTE defined in Query 3, adds a `non_mfn_max` CTE holding the highest effective rate among non-MFN labels, and finally filters with `WHERE has_mfn_clause = 1 AND effective_rate_per_point_usd < max_rate` to surface the actual breaches, along with the annualized make-good exposure ("the rate they should have received" minus "the rate they're actually receiving," multiplied by that label's share assumption).

**SQL**

```sql
WITH effective_rate AS (
    SELECT
        lbl.label_id,
        lbl.has_mfn_clause,
        lbl.usage_share_assumption_pct,
        lbl.annual_license_fee_usd / lbl.usage_share_assumption_pct AS effective_rate_per_point_usd
    FROM label_blanket_license lbl
),
non_mfn_max AS (
    SELECT MAX(effective_rate_per_point_usd) AS max_rate
    FROM effective_rate
    WHERE has_mfn_clause = 0
)
SELECT
    l.label_name,
    l.label_tier,
    ROUND(er.effective_rate_per_point_usd, 0) AS own_effective_rate_usd,
    ROUND(nm.max_rate, 0) AS max_non_mfn_rate_usd,
    ROUND(nm.max_rate - er.effective_rate_per_point_usd, 0) AS rate_shortfall_per_point_usd,
    ROUND((nm.max_rate - er.effective_rate_per_point_usd) * er.usage_share_assumption_pct, 0) AS annual_exposure_usd
FROM effective_rate er
JOIN label l
    ON l.id = er.label_id
CROSS JOIN non_mfn_max nm
WHERE er.has_mfn_clause = 1
  AND er.effective_rate_per_point_usd < nm.max_rate
ORDER BY annual_exposure_usd DESC;
```

**Expected Results and Business Conclusions**

The result should be exactly **1 row**: Titan Sound Group. Its effective rate (roughly $750K per point) is lower than Northline Aggregator's (an independent aggregator with no MFN protection that negotiated a higher rate later, roughly $800K per point), and `annual_exposure_usd` should land in the $700K-$800K range. Next step: this is a genuine breach-of-contract risk that needs to be escalated to the General Counsel immediately, to decide whether to proactively offer a rate-adjustment amendment or wait for a claim — delaying only lengthens the lookback period and widens the exposure.

---

## Query 5: Rights conflict flag status distribution

**Business Context**

You're the Rights & Licensing Compliance Officer, and every Monday you refresh the team's "rights conflict dashboard." The first thing to do today is get a clear picture of how many pending flags are currently backlogged and how they're distributed across statuses.

**Tags**: Aggregation | Basic | Rights & Licensing Compliance Officer

**Approach**

This is the simplest question in the set — group by `resolution_status`, count, and sum up the share and total revenue-at-risk for each category. The only thing to watch is that the denominator for "share of total" should come from a separate subquery total rather than reaching for something more elaborate like `COUNT(*) OVER ()`. With five statuses and a few dozen records, a subquery is plenty — no need for a window function here.

**SQL**

```sql
SELECT
    resolution_status,
    COUNT(*) AS flag_count,
    ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM rights_conflict_flag), 1) AS pct_of_total,
    ROUND(SUM(revenue_at_risk_usd), 2) AS total_revenue_at_risk_usd
FROM rights_conflict_flag
GROUP BY resolution_status
ORDER BY flag_count DESC;
```

**Expected Results and Business Conclusions**

The result is 5 rows, corresponding to the statuses `open`, `under_review`, `cleared`, `takedown`, and `licensed_retroactively`. `open` plus `under_review` together account for roughly 43% — meaning over four in ten flags haven't finished moving through the process. Next step: pull out the `open` flags with the highest `revenue_at_risk_usd` and prioritize audit resources against them (use alongside Query 8).

---

## Query 6: SLA-overdue flag count and revenue exposure

**Business Context**

Every quarter, the Director of Rights Compliance has to report to the General Counsel on whether the team's internal 30-day processing SLA is actually being met. This isn't just a process-efficiency question — the slower resolution takes, the greater the legal exposure that the platform "knowingly kept collecting ad revenue despite a known rights risk."

**Tags**: Date/Time Analysis + Aggregation | Intermediate | Director of Rights Compliance

**Approach**

"Overdue" needs to be computed two different ways, not with a single formula: for records that have already been resolved, compare `resolved_date - flagged_date` against 30 days; for records that are still unresolved (`open` or `under_review`), `resolved_date` is null, so the only option is to measure how long they've been sitting by subtracting `flagged_date` from the reference date `2026-06-30`. This uses SQLite's `JULIANDAY()` function to convert dates to Julian day numbers and subtract them to get a day count. A `CASE WHEN` sorts records into three states in an `sla_bucket` field, and then those are aggregated.

**SQL**

```sql
SELECT
    CASE
        WHEN resolution_status IN ('open', 'under_review')
             AND (JULIANDAY('2026-06-30') - JULIANDAY(flagged_date)) > sla_days_target
            THEN 'overdue_still_open'
        WHEN resolved_date IS NOT NULL
             AND (JULIANDAY(resolved_date) - JULIANDAY(flagged_date)) > sla_days_target
            THEN 'overdue_resolved_late'
        ELSE 'within_sla'
    END AS sla_bucket,
    COUNT(*) AS flag_count,
    ROUND(SUM(revenue_at_risk_usd), 2) AS revenue_at_risk_usd
FROM rights_conflict_flag
GROUP BY sla_bucket
ORDER BY revenue_at_risk_usd DESC;
```

**Expected Results and Business Conclusions**

The result is 3 rows. `overdue_still_open` and `overdue_resolved_late` combined should account for 60%-65% of flags, with a combined `revenue_at_risk_usd` in the $200K-$220K range. Next step: if the overdue share exceeds 40%, the next quarterly compliance report should include a request to the General Counsel for additional audit headcount, rather than continuing to try to "chew through" the backlog at the current pace.

---

## Query 7: Sampling-driven rights conflicts by source label

**Business Context**

At recent renewal negotiations, the Head of Label Relations has noticed label representatives making comments like "your platform is full of pirated remixes of our songs, and you're clearly not enforcing this closely enough." He wants to know whether the data actually backs that up — specifically, which labels' official tracks are most likely to get "caught up" in rights conflicts via UGC remixes.

**Tags**: Join (Self-Join) | Basic | Head of Label Relations

**Approach**

`rights_conflict_flag.remix_sound_id` points to the remix itself; to trace which label's track that remix "got in trouble over," you need two joins: first from `rights_conflict_flag` to `sound` (to get the remix row), then a second join back to the `sound` table using the remix's `source_sound_id` (to get the official track it sampled), and finally from that official track's `primary_label_id` to `label`. This is a classic "table joined to itself" scenario — the two occurrences of the `sound` table need distinct aliases (`remix` and `official`) or the SQL engine won't be able to tell which row you mean.

**SQL**

```sql
SELECT
    l.label_name,
    l.label_tier,
    COUNT(rcf.id) AS conflict_count,
    ROUND(SUM(rcf.revenue_at_risk_usd), 2) AS total_revenue_at_risk_usd
FROM rights_conflict_flag rcf
JOIN sound remix
    ON remix.id = rcf.remix_sound_id
JOIN sound official
    ON official.id = remix.source_sound_id
JOIN label l
    ON l.id = official.primary_label_id
GROUP BY l.id
ORDER BY conflict_count DESC;
```

**Expected Results and Business Conclusions**

The row count equals the number of labels with at least one official track that has been sampled into a flagged rights conflict (no more than 20 rows), sorted by conflict count descending. Next step: share the top labels on this list with the Head of Label Relations, so he can proactively mention "we're already stepping up our auditing here" in renewal negotiations rather than waiting to be complained to.

---

## Query 8: Top 10 longest-overdue rights conflicts

**Business Context**

You (the Rights & Licensing Compliance Officer) just saw the overall overdue rate in Query 6, and now need a concrete case list — exactly which records have been sitting the longest, so you can assign them to team members to work through before the end of the day.

**Tags**: Window Function | Intermediate | Rights & Licensing Compliance Officer

**Approach**

Resolved and unresolved records use different formulas for "days overdue" (as in Query 6); this query uses the same `CASE WHEN` expression to compute a unified `days_open`, then ranks each record with `RANK() OVER (ORDER BY days_open DESC)`, and finally limits the output to the top ten with `LIMIT 10`. A window function is used instead of a plain `ORDER BY ... LIMIT 10` so the result keeps an `overdue_rank` column, letting team members refer to records by rank when talking to each other, rather than a set of unnumbered rows.

**SQL**

```sql
SELECT
    rcf.remix_sound_id,
    s.title,
    rcf.conflict_type,
    rcf.flagged_date,
    rcf.resolution_status,
    rcf.resolved_date,
    ROUND(
        CASE
            WHEN rcf.resolved_date IS NOT NULL
                THEN JULIANDAY(rcf.resolved_date) - JULIANDAY(rcf.flagged_date)
            ELSE JULIANDAY('2026-06-30') - JULIANDAY(rcf.flagged_date)
        END, 0
    ) AS days_open,
    RANK() OVER (
        ORDER BY
            CASE
                WHEN rcf.resolved_date IS NOT NULL
                    THEN JULIANDAY(rcf.resolved_date) - JULIANDAY(rcf.flagged_date)
                ELSE JULIANDAY('2026-06-30') - JULIANDAY(rcf.flagged_date)
            END DESC
    ) AS overdue_rank
FROM rights_conflict_flag rcf
JOIN sound s
    ON s.id = rcf.remix_sound_id
ORDER BY days_open DESC
LIMIT 10;
```

**Expected Results and Business Conclusions**

The result is 10 rows, with `days_open` decreasing from the largest value; the longest few should be well past the 30-day SLA (some possibly over 100 days). Next step: assign these 10 records, split by `resolution_status`, to the team members responsible for "unauthorized sampling" and "duplicate rights claims" respectively, and push for at least one status update on each by end of day.

---

## Query 9: Creator Fund effective payout rate by spike-window alignment status

**Business Context**

The Creator Fund Program Manager has recently received DMs from several top creators complaining — "my video clearly went more viral than the one last month, so why did I earn less this time?" She suspects this is related to the Creator Fund's calendar-week settlement rule, and wants to first validate it with data: do sounds whose spike window "falls entirely within one week" actually earn a different payout rate than sounds whose spike window "spans two weeks"?

**Tags**: CTE + Aggregation | Advanced | Creator Fund Program Manager

**Approach**

The key here is grouping the comparison correctly: `sound.spike_week_alignment` already splits the 120 tracked trending sounds into `aligned` and `split_across_weeks`, so it's just a matter of grouping `creator_fund_weekly_payout` by this field and aggregating. The "effective payout rate" can't simply be computed as `payout_usd / weekly_view_count` per row and then averaged — that would over-weight weeks with low view counts. The correct approach is to sum `payout_usd` and `weekly_view_count` separately for each group, and then divide, giving an "overall" payout rate per thousand views where high-view weeks naturally carry more weight, more accurately reflecting how the money is actually distributed. Remember to restrict to `WHERE s.is_trending_monitored = 1`, so sounds without an alignment-status tag don't form a stray `NULL` group and skew the comparison.

**SQL**

```sql
SELECT
    s.spike_week_alignment,
    COUNT(DISTINCT s.id) AS sound_count,
    SUM(cfwp.weekly_view_count) AS total_views,
    ROUND(SUM(cfwp.payout_usd), 2) AS total_payout_usd,
    ROUND(SUM(cfwp.payout_usd) * 1000.0 / SUM(cfwp.weekly_view_count), 4) AS payout_rate_per_1000_views
FROM creator_fund_weekly_payout cfwp
JOIN sound s
    ON s.id = cfwp.remix_sound_id
WHERE s.is_trending_monitored = 1
GROUP BY s.spike_week_alignment;
```

**Expected Results and Business Conclusions**

The result is 2 rows. The `aligned` group's `payout_rate_per_1000_views` should be around $1.14-$1.25, while the `split_across_weeks` group should be roughly 28%-30% lower (around $0.80-$0.90). Next step: this confirms the creators' complaints have a data basis — the Creator Fund Program Manager should push the product team to move from calendar-week settlement to a "rolling 7-day window anchored to each creator's own video," or at minimum offer a one-time make-good payment for split-week cases.

---

## Query 10: Week-over-week payout change for a single split-week case

**Business Context**

The Creator Fund Program Manager wants a concrete, persuasive example to bring to the product team, rather than just an abstract percentage. She's asked you to pick the most affected split-week sound and lay out its week-by-week view counts and payouts as chart material for a one-page slide.

**Tags**: Window Function (LAG) | Intermediate | Creator Fund Program Manager

**Approach**

Start with a CTE that picks the most representative sound from all `split_across_weeks` sounds by ranking on total cumulative payout (highest payout, meaning it genuinely went viral, but still got shortchanged by the rule). Once that sound is selected, use `LAG(payout_usd) OVER (ORDER BY week_start_date)` to get "last week's payout" and compare it to the current week, making it easy to see exactly how much the payout dropped at the week boundary. No `PARTITION BY` is needed here, since the `WHERE` clause already narrows the scope to a single `remix_sound_id`.

**SQL**

```sql
WITH top_split_sound AS (
    SELECT cfwp.remix_sound_id
    FROM creator_fund_weekly_payout cfwp
    JOIN sound s
        ON s.id = cfwp.remix_sound_id
    WHERE s.spike_week_alignment = 'split_across_weeks'
    GROUP BY cfwp.remix_sound_id
    ORDER BY SUM(cfwp.payout_usd) DESC
    LIMIT 1
)
SELECT
    s.title,
    cfwp.week_start_date,
    cfwp.weekly_view_count,
    cfwp.payout_usd,
    LAG(cfwp.payout_usd) OVER (ORDER BY cfwp.week_start_date) AS prev_week_payout_usd,
    ROUND(
        cfwp.payout_usd - LAG(cfwp.payout_usd) OVER (ORDER BY cfwp.week_start_date),
        2
    ) AS wow_change_usd
FROM creator_fund_weekly_payout cfwp
JOIN sound s
    ON s.id = cfwp.remix_sound_id
WHERE cfwp.remix_sound_id = (SELECT remix_sound_id FROM top_split_sound)
ORDER BY cfwp.week_start_date;
```

**Expected Results and Business Conclusions**

The result is a row for every settlement week this sound has had, from launch through the reference date. Around the two weeks when it went viral, `weekly_view_count` should show a clear spike, but the corresponding jump in `payout_usd` will be smaller than expected because it got "diluted" across the week boundary. Next step: fold this case into the proposal for the product team, alongside the aggregate stats from Query 9.

---

## Query 11: Total Creator Fund spend broken down by creator tier

**Business Context**

Every quarter, the Creator Fund Program Manager has to report to Finance on the actual spending mix of the Creator Fund — how much went to top-tier, mid-tier, and long-tail creators respectively — to judge whether this budget is really advancing the goal of "supporting more everyday creators," rather than being swallowed almost entirely by top-tier accounts.

**Tags**: Aggregation | Basic | Creator Fund Program Manager

**Approach**

A standard group-and-aggregate: group by `creator.creator_tier`, sum `payout_usd`, and also compute per-creator average payout to check against the question of whether top-tier creators are earning a disproportionate share. The only thing to watch for is `COUNT(DISTINCT c.id)` — since a single creator can have multiple remixes and multiple weekly payout records, failing to de-duplicate would inflate the creator count.

**SQL**

```sql
SELECT
    c.creator_tier,
    COUNT(DISTINCT c.id) AS creator_count,
    ROUND(SUM(cfwp.payout_usd), 2) AS total_payout_usd,
    ROUND(SUM(cfwp.payout_usd) / COUNT(DISTINCT c.id), 2) AS avg_payout_per_creator_usd
FROM creator_fund_weekly_payout cfwp
JOIN creator c
    ON c.id = cfwp.creator_id
GROUP BY c.creator_tier
ORDER BY total_payout_usd DESC;
```

**Expected Results and Business Conclusions**

The result is 3 rows (top / mid / long_tail). `avg_payout_per_creator_usd` should be far higher for the top tier than for long_tail creators, which matches the expected "platform effects naturally concentrate at the top" pattern — this on its own is not a trap, just the current state of operations. Next step: use this as background context for the "underpayment from split-week alignment" issue surfaced in Query 9/10 — if long-tail creators already earn less to begin with, the extra loss from the split-week rule affects them proportionally more, which is worth including in the proposal.

---

## Query 12: Daily view curve vs. weekly payout for a single viral remix

**Business Context**

You need to run an internal training session for the Director of Rights Compliance, using a concrete example to explain clearly "why calendar-week settlement systematically underpays certain creators." An abstract percentage isn't intuitive enough, so you want to find a genuinely viral sound and lay its daily view curve alongside its corresponding weekly payouts.

**Tags**: Join + Date/Time | Intermediate | Rights & Licensing Compliance Officer

**Approach**

First, use a CTE to pick out the sound that is both `split_across_weeks` and has the highest single-day peak view count — that guarantees the example is representative (split across weeks) and genuinely viral (impressive numbers, persuasive for training). Then use `UNION ALL` to combine this sound's "daily view detail" (from `sound_daily_viral_window`) with its "weekly payout detail" (from `creator_fund_weekly_payout`) into a single result set, using a `granularity` column to distinguish the two grains, sorted by date so the two interleave. This lets readers see directly: on certain days, views spiked hard, but the spike straddled two different `week_start_date` values, so no single week's payout alone looks especially high.

**SQL**

```sql
WITH top_viral_sound AS (
    SELECT s.id AS sound_id
    FROM sound s
    JOIN sound_daily_viral_window sdw
        ON sdw.sound_id = s.id
    WHERE s.spike_week_alignment = 'split_across_weeks'
    GROUP BY s.id
    ORDER BY MAX(sdw.daily_view_count) DESC
    LIMIT 1
)
SELECT
    'daily' AS granularity,
    usage_date AS period_start,
    daily_view_count AS view_count,
    NULL AS payout_usd
FROM sound_daily_viral_window
WHERE sound_id = (SELECT sound_id FROM top_viral_sound)

UNION ALL

SELECT
    'weekly' AS granularity,
    week_start_date AS period_start,
    weekly_view_count AS view_count,
    payout_usd
FROM creator_fund_weekly_payout
WHERE remix_sound_id = (SELECT sound_id FROM top_viral_sound)

ORDER BY period_start, granularity;
```

**Expected Results and Business Conclusions**

The result mixes daily and weekly rows, with `payout_usd` populated only on rows where `granularity = 'weekly'`. Looking closely at the dates reveals that the peak in views clusters over a handful of days spanning a Friday through the following Monday, straddling two `week_start_date` values. Next step: turn this into a one-page comparison chart, as concrete supporting evidence for Query 9's conclusion, for use in internal training and the product proposal.

---

## Query 13: Label portfolio structure overview

**Business Context**

The Head of Label Relations has just taken over this portfolio and wants a "portfolio health check" first — the count, average share assumption, MFN coverage, and total annual fee for each of the three label tiers — as background for every subsequent detailed analysis.

**Tags**: Aggregation | Basic | Head of Label Relations

**Approach**

Group by `label_tier`, joining `label` to `label_blanket_license` to compute the average share assumption, MFN coverage count, and total annual fee. Since `has_mfn_clause` is stored as 0/1, `SUM(CASE WHEN has_mfn_clause = 1 THEN 1 ELSE 0 END)` directly counts how many labels in each tier have MFN protection, no extra subquery needed.

**SQL**

```sql
SELECT
    l.label_tier,
    COUNT(*) AS label_count,
    ROUND(AVG(lbl.usage_share_assumption_pct), 2) AS avg_usage_share_assumption_pct,
    SUM(CASE WHEN lbl.has_mfn_clause = 1 THEN 1 ELSE 0 END) AS mfn_protected_count,
    ROUND(SUM(lbl.annual_license_fee_usd), 0) AS total_annual_fee_usd
FROM label l
JOIN label_blanket_license lbl
    ON lbl.label_id = l.id
GROUP BY l.label_tier
ORDER BY total_annual_fee_usd DESC;
```

**Expected Results and Business Conclusions**

The result is 3 rows (major / mid_size / indie_aggregator). The `major` tier should have the fewest labels (`label_count` of 3) but the highest `total_annual_fee_usd`, with `mfn_protected_count` equal to 3 (all major labels carry MFN); the `mid_size` tier should have `mfn_protected_count` of 2; the `indie_aggregator` tier should have 0. Next step: present alongside every subsequent detailed analysis as portfolio structure background for the Head of Label Relations.

---

## Query 14: Cumulative contract payments actually made vs. amount owed on a pro-rata time basis

**Business Context**

While reconciling cash flow, the VP of Finance (FP&A) wants to confirm whether each contract's actual cumulative payments roughly match the proportion of the contract term that's elapsed — if a contract "hasn't paid what it should have by now," that could indicate a stuck finance process; if it has "paid too much," that could indicate a duplicate payment or a calculation error.

**Tags**: Join + Date/Time | Intermediate | VP of Finance (FP&A)

**Approach**

First, use a CTE to roll up each contract's `license_fee_payment` records into a cumulative amount paid and a count of payments made. Then compute `JULIANDAY('2026-06-30') - JULIANDAY(contract_start_date)` to get how many days the contract has been active, divide by 365 to get the "fraction of the year elapsed," and multiply by `annual_license_fee_usd` to get "the amount that, on a pro-rata time basis, should theoretically have been paid by now." Subtracting the two gives `variance_usd`, where a positive value means overpaid and a negative value means underpaid.

**SQL**

```sql
WITH paid AS (
    SELECT
        license_id,
        SUM(amount_paid_usd) AS cumulative_paid_usd,
        COUNT(*) AS payments_made
    FROM license_fee_payment
    GROUP BY license_id
)
SELECT
    l.label_name,
    lbl.contract_start_date,
    lbl.annual_license_fee_usd,
    p.cumulative_paid_usd,
    p.payments_made,
    ROUND(
        (JULIANDAY('2026-06-30') - JULIANDAY(lbl.contract_start_date)) / 365.0 * lbl.annual_license_fee_usd,
        0
    ) AS expected_cumulative_paid_usd,
    ROUND(
        p.cumulative_paid_usd
            - (JULIANDAY('2026-06-30') - JULIANDAY(lbl.contract_start_date)) / 365.0 * lbl.annual_license_fee_usd,
        0
    ) AS variance_usd
FROM paid p
JOIN label_blanket_license lbl
    ON lbl.id = p.license_id
JOIN label l
    ON l.id = lbl.label_id
ORDER BY variance_usd;
```

**Expected Results and Business Conclusions**

The result is 20 rows. Since `license_fee_payment` covers every quarterly payment from each contract's signing date through today, `expected_cumulative_paid_usd` (pro-rata amount owed) and `cumulative_paid_usd` (actual amount paid) are on a consistent basis, so `variance_usd` won't show the kind of million-dollar systematic negative gap you'd get from something like "an old contract that only retained the last 2 years of payment history."

One thing worth understanding: quarterly license fees are paid **in arrears** (a quarter has to close and settle before it's paid), so the reference date will always fall partway through a quarter that hasn't settled yet, meaning actual payments will naturally lag slightly behind the pro-rata "amount owed by day count." `variance_usd` will generally be a **small negative value**, with a magnitude capped at roughly **one quarter's worth of annual fee** (`annual_license_fee_usd / 4`) for that contract. Major labels have high annual fees (tens of millions of dollars), so this "one quarter of lag" translates to a larger absolute dollar figure (possibly hundreds of thousands or even one to two million dollars) — but relative to contract size, this is still within normal range and doesn't indicate a missed payment.

`variance_usd` may also show up as a **small positive value** (a handful of contracts in this dataset, the largest around $430K). This isn't "overpayment" — it's a discretization residual from computing each quarterly installment as `annual fee / 4` while actual calendar quarters don't line up exactly with `365/4` days, compounded by the ±1% noise applied to each payment. As long as the positive variance stays within **one quarter's annual fee**, it's just as normal as a small negative variance.

Next step: the standard applies symmetrically in both directions — what actually needs to be escalated to Finance for individual review is any contract where `variance_usd`'s absolute value **clearly exceeds one quarter's annual fee** for that contract: a positive variance far beyond one quarter's fee could indicate a duplicate payment, and a negative variance far beyond it could indicate a missed payment or a stuck process. Conversely, anything whose absolute value still falls within one quarter's annual fee (regardless of sign, and regardless of how large the absolute dollar amount looks for a major label) is normal lag or noise and doesn't need individual review.

---

## Query 15: Catalog composition: official tracks vs. UGC remixes

**Business Context**

You (the Rights & Licensing Compliance Officer) are running onboarding training for a new team member, and the first step is giving them an intuitive feel for what the "Sounds" catalog is made of — the split between official tracks and user remixes, and the genre distribution.

**Tags**: Aggregation | Basic | Rights & Licensing Compliance Officer

**Approach**

A basic `GROUP BY sound_type, genre` with a count, no traps — the simplest question in the whole document, deliberately reserved for someone just getting familiar with the table structure.

**SQL**

```sql
SELECT
    sound_type,
    genre,
    COUNT(*) AS sound_count
FROM sound
GROUP BY sound_type, genre
ORDER BY sound_type, sound_count DESC;
```

**Expected Results and Business Conclusions**

The result is roughly 14 rows (2 sound types × 7 genres). `official_track` totals roughly 400, `ugc_remix` totals roughly 200, and Pop should be the most represented genre in both categories. Next step: none — this is a pure background table, meant to build intuition about the size and shape of the catalog.

---

## Query 16: Top 5 / bottom 5 labels by share drift

**Business Context**

The Director of Rights Compliance needs a single page for the weekly team meeting laying out clearly "which labels' share has grown the most, and which have dropped the most" — no need to see the full 20-label list, just the two extremes.

**Tags**: Window Function | Intermediate | Director of Rights Compliance

**Approach**

This reuses the share drift calculation from Query 1, but this time needs to pull "the 5 with the largest gains" and "the 5 with the largest losses" simultaneously. This is done inside a single CTE using `RANK() OVER` twice — once ordering by drift descending (to find the biggest gains) and once ascending (to find the biggest losses) — then combining the rows where `growth_rank <= 5` and `decline_rank <= 5` with `UNION ALL`. Note that if there were fewer than 10 labels, these two groups could overlap, but this dataset has 20 labels, so the two groups won't overlap.

**SQL**

```sql
WITH label_sound AS (
    SELECT
        s.id AS sound_id,
        s.primary_label_id AS label_id
    FROM sound s
    WHERE s.sound_type = 'official_track'

    UNION ALL

    SELECT
        r.id AS sound_id,
        o.primary_label_id AS label_id
    FROM sound r
    JOIN sound o
        ON r.source_sound_id = o.id
    WHERE r.sound_type = 'ugc_remix'
),
month_usage AS (
    SELECT
        ls.label_id,
        SUM(smu.video_count) AS label_video_count
    FROM label_sound ls
    JOIN sound_monthly_usage smu
        ON smu.sound_id = ls.sound_id
    WHERE smu.usage_month = '2026-06-01'
    GROUP BY ls.label_id
),
total AS (
    SELECT SUM(label_video_count) AS total_video_count
    FROM month_usage
),
drift AS (
    SELECT
        l.label_name,
        lbl.usage_share_assumption_pct,
        ROUND(mu.label_video_count * 100.0 / t.total_video_count, 2) AS actual_share_pct,
        ROUND(mu.label_video_count * 100.0 / t.total_video_count - lbl.usage_share_assumption_pct, 2) AS drift_pp,
        RANK() OVER (ORDER BY mu.label_video_count * 100.0 / t.total_video_count - lbl.usage_share_assumption_pct DESC) AS growth_rank,
        RANK() OVER (ORDER BY mu.label_video_count * 100.0 / t.total_video_count - lbl.usage_share_assumption_pct ASC) AS decline_rank
    FROM month_usage mu
    JOIN label l
        ON l.id = mu.label_id
    JOIN label_blanket_license lbl
        ON lbl.label_id = l.id
    CROSS JOIN total t
)
SELECT label_name, usage_share_assumption_pct, actual_share_pct, drift_pp, 'growth' AS bucket
FROM drift
WHERE growth_rank <= 5

UNION ALL

SELECT label_name, usage_share_assumption_pct, actual_share_pct, drift_pp, 'decline' AS bucket
FROM drift
WHERE decline_rank <= 5

ORDER BY drift_pp DESC;
```

**Expected Results and Business Conclusions**

The result is 10 rows, with the first 5 being the labels with the largest gains (`drift_pp` positive and large) and the last 5 being the labels with the largest losses (`drift_pp` negative with a large absolute value). Next step: use directly as the first slide in the weekly team meeting.

---

## Query 17: Quarterly compliance risk priority list

**Business Context**

At quarter-end, the Director of Rights Compliance needs to roll the signals from Trap 1 (share drift), Trap 2 (unresolved rights conflicts), and Trap 4 (MFN breach) into a single table — a "which labels most need our attention this quarter" priority list for the General Counsel, rather than handing over three separate reports.

**Tags**: CTE (multi-table rollup) | Advanced | Director of Rights Compliance

**Approach**

This is the most comprehensive question in the entire document, requiring three independent CTEs, each computing one signal, then `LEFT JOIN`ed onto the main `label` table (`LEFT JOIN` is used because not every label has unresolved rights conflicts; an `INNER JOIN` would drop labels with "no issues at all," when those labels should actually appear on the list, just with a risk value of 0). The `mfn_check` CTE reuses the MFN breach logic from Query 4, but this time computes a boolean flag rather than a specific dollar amount. The final sort puts labels with an MFN breach at the very top (the most urgent compliance risk), then sorts by the absolute value of share drift and unresolved revenue-at-risk in turn.

**SQL**

```sql
WITH label_sound AS (
    SELECT
        s.id AS sound_id,
        s.primary_label_id AS label_id
    FROM sound s
    WHERE s.sound_type = 'official_track'

    UNION ALL

    SELECT
        r.id AS sound_id,
        o.primary_label_id AS label_id
    FROM sound r
    JOIN sound o
        ON r.source_sound_id = o.id
    WHERE r.sound_type = 'ugc_remix'
),
month_usage AS (
    SELECT
        ls.label_id,
        SUM(smu.video_count) AS label_video_count
    FROM label_sound ls
    JOIN sound_monthly_usage smu
        ON smu.sound_id = ls.sound_id
    WHERE smu.usage_month = '2026-06-01'
    GROUP BY ls.label_id
),
total AS (
    SELECT SUM(label_video_count) AS total_video_count
    FROM month_usage
),
drift AS (
    SELECT
        l.id AS label_id,
        ROUND(mu.label_video_count * 100.0 / t.total_video_count - lbl.usage_share_assumption_pct, 2) AS drift_pp
    FROM month_usage mu
    JOIN label l
        ON l.id = mu.label_id
    JOIN label_blanket_license lbl
        ON lbl.label_id = l.id
    CROSS JOIN total t
),
conflict_summary AS (
    SELECT
        o.primary_label_id AS label_id,
        COUNT(*) AS open_conflict_count,
        ROUND(SUM(rcf.revenue_at_risk_usd), 2) AS open_revenue_at_risk_usd
    FROM rights_conflict_flag rcf
    JOIN sound remix
        ON remix.id = rcf.remix_sound_id
    JOIN sound o
        ON o.id = remix.source_sound_id
    WHERE rcf.resolution_status IN ('open', 'under_review')
    GROUP BY o.primary_label_id
),
mfn_check AS (
    SELECT
        lbl.label_id,
        CASE
            WHEN lbl.has_mfn_clause = 1
                 AND lbl.annual_license_fee_usd / lbl.usage_share_assumption_pct <
                     (SELECT MAX(annual_license_fee_usd / usage_share_assumption_pct)
                      FROM label_blanket_license
                      WHERE has_mfn_clause = 0)
                THEN 1
            ELSE 0
        END AS mfn_breach_flag
    FROM label_blanket_license lbl
)
SELECT
    l.label_name,
    l.label_tier,
    COALESCE(d.drift_pp, 0) AS usage_share_drift_pp,
    COALESCE(cs.open_conflict_count, 0) AS open_conflict_count,
    COALESCE(cs.open_revenue_at_risk_usd, 0) AS open_revenue_at_risk_usd,
    mc.mfn_breach_flag
FROM label l
LEFT JOIN drift d
    ON d.label_id = l.id
LEFT JOIN conflict_summary cs
    ON cs.label_id = l.id
JOIN mfn_check mc
    ON mc.label_id = l.id
ORDER BY mc.mfn_breach_flag DESC, ABS(COALESCE(d.drift_pp, 0)) DESC, open_revenue_at_risk_usd DESC;
```

**Expected Results and Business Conclusions**

The result is 20 rows (one per label). The first row should be Titan Sound Group (`mfn_breach_flag = 1`), followed by the rest sorted by share drift magnitude and unresolved conflict exposure. Next step: this table is itself the quarterly compliance risk list to send to the General Counsel — the top 3-5 rows are the highest-priority items that must be addressed this quarter.

---

## Query 18: Keyword pattern matching on remix sound titles

**Business Context**

While organizing the UGC remix list, you want to quickly find every sound whose title contains typical remix keywords like "remix," "freestyle," "sped up," or "slowed" — as a starting point for a sample audit of unauthorized sampling, since these keywords often hint that a sound is likely derived from an original track.

**Tags**: Pattern Matching | Basic | Rights & Licensing Compliance Officer

**Approach**

A standard `LIKE`-based fuzzy match, chaining several keywords together with `OR`. Since SQLite's `LIKE` is case-insensitive for ASCII letters by default, no extra `LOWER()` wrapping is needed. Restricting to `sound_type = 'ugc_remix'` avoids accidentally pulling in official track titles (which in theory shouldn't contain these keywords, but adding the condition is more rigorous and better matches the analytical intent).

**SQL**

```sql
SELECT
    title,
    sound_type,
    release_date
FROM sound
WHERE sound_type = 'ugc_remix'
  AND (
        title LIKE '%remix%'
        OR title LIKE '%freestyle%'
        OR title LIKE '%sped up%'
        OR title LIKE '%slowed%'
      )
ORDER BY release_date DESC;
```

**Expected Results and Business Conclusions**

The row count depends on how many remix titles actually contain these keywords, sorted from most to least recent release date. Next step: cross-reference this list against the `rights_conflict_flag` table to see whether any records with obvious "remix keywords" have never been flagged — a good starting point for the next round of audit sampling.

---

## Query 19: Monthly trend of platform-wide attributable catalog usage

**Business Context**

While preparing the annual business review, the Head of Label Relations wants to see how the platform's overall "attributable to a label" usage volume has trended over the past 18 months, as background before discussing individual labels' share gains and losses.

**Tags**: Date/Time Trend | Basic | Head of Label Relations

**Approach**

This reuses the "which sounds are attributable to a label" CTE logic from Query 1, but this time groups by `usage_month` instead of by label, to see the overall trend. This is a basic time-series aggregation question, meant to give readers the background that "the denominator itself is also growing" before they get into questions involving percentage share.

**SQL**

```sql
WITH label_sound AS (
    SELECT
        s.id AS sound_id
    FROM sound s
    WHERE s.sound_type = 'official_track'

    UNION ALL

    SELECT
        r.id AS sound_id
    FROM sound r
    WHERE r.sound_type = 'ugc_remix'
      AND r.source_sound_id IS NOT NULL
)
SELECT
    smu.usage_month,
    SUM(smu.video_count) AS total_labeled_video_count,
    SUM(smu.view_count) AS total_labeled_view_count
FROM sound_monthly_usage smu
JOIN label_sound ls
    ON ls.sound_id = smu.sound_id
GROUP BY smu.usage_month
ORDER BY smu.usage_month;
```

**Expected Results and Business Conclusions**

The result is 18 rows (2025-01 through 2026-06, one per month), with `total_labeled_video_count` showing a steady month-over-month upward trend (roughly a 30%-40% cumulative increase over the 18 months). Next step: use as background chart material for the annual business review, illustrating that "an individual label's declining share doesn't necessarily mean its absolute usage is shrinking — it may just mean the overall pie is growing faster than that label."

---

## Query 20: Renewal priority list (approaching expiration + share drift)

**Business Context**

The Head of Label Relations needs to plan next quarter's renewal negotiation calendar, and wants a combined list that prioritizes labels whose contract is "approaching expiration" and whose share has "drifted significantly," rather than sorting mechanically by expiration date alone — a label with only 2 months left on its contract but almost no share change is less urgent than one with 8 months left whose share has already drifted by 4 percentage points.

**Tags**: CTE + Window Function | Advanced | Head of Label Relations

**Approach**

Building on Query 1's share drift calculation, add a computed `months_to_renewal` (contract end date minus the reference date, converted to months). Priority ordering uses a compound `CASE WHEN` as the primary sort key — labels expiring "within 12 months" as a group are ranked ahead of those expiring "beyond 12 months" — and within each tier, sort by the absolute value of share drift descending, generating a single unified `renewal_priority_rank` with `RANK() OVER`. This "tier first, then sort" approach more closely mirrors real business prioritization logic than sorting on a single dimension alone.

**SQL**

```sql
WITH label_sound AS (
    SELECT
        s.id AS sound_id,
        s.primary_label_id AS label_id
    FROM sound s
    WHERE s.sound_type = 'official_track'

    UNION ALL

    SELECT
        r.id AS sound_id,
        o.primary_label_id AS label_id
    FROM sound r
    JOIN sound o
        ON r.source_sound_id = o.id
    WHERE r.sound_type = 'ugc_remix'
),
month_usage AS (
    SELECT
        ls.label_id,
        SUM(smu.video_count) AS label_video_count
    FROM label_sound ls
    JOIN sound_monthly_usage smu
        ON smu.sound_id = ls.sound_id
    WHERE smu.usage_month = '2026-06-01'
    GROUP BY ls.label_id
),
total AS (
    SELECT SUM(label_video_count) AS total_video_count
    FROM month_usage
),
drift AS (
    SELECT
        l.label_name,
        lbl.contract_end_date,
        ROUND(mu.label_video_count * 100.0 / t.total_video_count - lbl.usage_share_assumption_pct, 2) AS drift_pp,
        (JULIANDAY(lbl.contract_end_date) - JULIANDAY('2026-06-30')) / 30.0 AS months_to_renewal
    FROM month_usage mu
    JOIN label l
        ON l.id = mu.label_id
    JOIN label_blanket_license lbl
        ON lbl.label_id = l.id
    CROSS JOIN total t
)
SELECT
    label_name,
    contract_end_date,
    ROUND(months_to_renewal, 1) AS months_to_renewal,
    drift_pp,
    RANK() OVER (
        ORDER BY
            CASE WHEN months_to_renewal <= 12 THEN 1 ELSE 2 END,
            ABS(drift_pp) DESC
    ) AS renewal_priority_rank
FROM drift
ORDER BY renewal_priority_rank
LIMIT 10;
```

**Expected Results and Business Conclusions**

The result is 10 rows; the label at `renewal_priority_rank = 1` should satisfy both conditions — "expiring within 12 months" and "large share drift" — simultaneously. Next step: hand this list directly to the Head of Label Relations to schedule into next quarter's renewal negotiation calendar, with the top 3 given the earliest negotiation slots.

---

## Business Problem Cross-Reference

| Business Problem | Corresponding Queries |
|----------|----------|
| Q1 Catalog usage share drift | Query 1, Query 2, Query 16, Query 19, Query 20 |
| Q2 UGC unauthorized sampling compliance audit | Query 5, Query 6, Query 7, Query 8, Query 18 |
| Q3 Creator Fund viral-window misalignment | Query 9, Query 10, Query 11, Query 12 |
| Q4 MFN clause compliance audit | Query 3, Query 4, Query 17 |
| Operational background | Query 13, Query 14, Query 15 |
</content>
