# Kestrel Compute Power Dataset SQL Query Collection

This document covers the `utilities_datacenter_power_procurement_demand_response_high` dataset. The company background, industry primer, and glossary live in `01-utilities_datacenter_power_procurement_demand_response_high_business_context.md`, and the table structure and field definitions live in `02-utilities_datacenter_power_procurement_demand_response_high_er_document.md`. We recommend reading those two documents in order before working through this one.

The dataset is anchored to a fixed reference date, `REFERENCE_DATE = 2026-06-30`, which is also the last day of Kestrel's FY2026 fiscal year. Anywhere a query needs "today" or a fiscal-year boundary, it uses a literal date string rather than `DATE('now')`. That way the results are identical no matter when the query is run.

---

## 1. How to Use This Document

These twenty queries are the first assignment VP of Energy Strategy Dana Whitfield handed you. The deliverable is the FY2027 energy budget review memo for the September board meeting, and these queries are the evidence chain behind every conclusion in that memo.

Each query has five parts. **Business Context** explains who's asking, why now, and what decision the answer will drive. **Tags** mark the SQL category, difficulty, and the role it corresponds to. **Approach** walks through the reasoning before you look at the SQL, spelling out which tables you'll touch, where the join structure has traps, what grain the aggregation runs at, and why a CTE or window function is needed here. **SQL** is code you can run directly. **Expected Result and Business Takeaway** describes the shape and real-world magnitude of the result, and what the next action should be once you have the number.

That last part is the whole point. Getting a number out is not the end of the analysis, it's the starting point. Every query's takeaway spells out the next action, and that action is the actual output of this work.

Several of the twenty questions come in pairs. One gives "the number everyone has always believed," followed immediately by one that gives "the real number once you account for the cost everyone was ignoring." Q4 and Q5 are a pair, and so are Q9 and Q10. This pairing isn't for show — it recreates one of the most common scenes in real analytics work: a long-cited metric whose methodology was wrong from the start.

---

## 2. Query Index

| No. | Title | Business Role | SQL Category | Difficulty |
| :-- | :--- | :--- | :--- | :--- |
| Q1 | FY2026 electricity spend overview across six sites | CFO Helen Okafor | Aggregation + outer join | Basic |
| Q2 | Bill structure breakdown — where the money actually goes | CFO Helen Okafor | Aggregation + window function | Basic |
| Q3 | Demand response program enrollment and committed capacity | Demand Response Manager Priya Raghavan | Join + aggregation | Basic |
| Q4 | Demand response settlement revenue ranking | Demand Response Manager Priya Raghavan | Multi-table join + aggregation | Intermediate |
| Q5 | The real net benefit of demand response | VP of Energy Strategy Dana Whitfield | CTE + multi-table join | Advanced |
| Q6 | Which sites and which events are losing money | VP of Energy Strategy Dana Whitfield | CTE + correlated subquery | Intermediate |
| Q7 | Screening for suspected baseline inflation events | Demand Response Manager Priya Raghavan | Join + ratio filter | Intermediate |
| Q8 | Recomputing with a clean baseline — how much was overstated | VP of Energy Strategy Dana Whitfield | Multi-level CTE | Advanced |
| Q9 | Monthly wind PPA vs. simple average market price | Power Procurement Manager Marcus Ellery | CTE + aggregation | Basic |
| Q10 | The true generation-weighted PPA price gap | Power Procurement Manager Marcus Ellery | CTE + weighted aggregation | Advanced |
| Q11 | Does more wind output mean lower prices | Energy Data Analyst | CASE bucketing + window function | Intermediate |
| Q12 | Locating the monthly billing demand peak interval | Energy Data Analyst | Window function RANK | Intermediate |
| Q13 | What that burn-in test actually cost | Director of Data Center Operations Tom Brennan | Multi-level CTE + counterfactual | Advanced |
| Q14 | 4CP forecast retrospective | Grid Operations Specialist Luis Ferrer | Date arithmetic + interval matching | Intermediate |
| Q15 | The financial cost of missing a 4CP call | CFO Helen Okafor | CTE + counterfactual | Intermediate |
| Q16 | What we were doing when prices spiked | Energy Data Analyst | Window function LAG + bucketing | Intermediate |
| Q17 | Wet bulb temperature and cooling load | Energy Data Analyst | Time-aligned join + bucketing | Intermediate |
| Q18 | Evaluation methodology across three supply contract types | Power Procurement Manager Marcus Ellery | Aggregation + classification | Basic |
| Q19 | Customers with the largest SLA credit exposure | COO Rafael Duarte | Aggregation + HAVING | Basic |
| Q20 | Who makes the curtailment call, and is it the right call | VP of Energy Strategy Dana Whitfield | Text matching + aggregation | Intermediate |

---

## 3. Q1 FY2026 Electricity Spend Overview Across Six Sites

### Business Context

While preparing board materials, CFO Helen Okafor made a simple request: give me one table showing how much each of the six sites spent on electricity, how much energy each used, and at what price. She wants to see the baseline picture clearly before deciding which direction to dig further.

The request looks simple, but there's a specific motive behind it. Companywide electricity spend in FY2026 was $205 million, a sizable jump from FY2025, and there are two competing explanations inside management: one says market prices rose, the other says it's just natural growth from newly commissioned sites. This table needs to be able to separate the two.

The answer will decide how the FY2027 budget gets structured: if the price differential is the main driver, the budget should be built site by site; if it's mostly volume growth, a single companywide budget will do.

### Tags

Aggregation + outer join / Basic / CFO

### Approach

You only need three tables: `site`, `iso_market`, and `energy_invoice`. The key is to use `LEFT JOIN` rather than `INNER JOIN` when pulling in invoices: the New Albany East site didn't go live until September 2025, so if it happens to be missing an invoice for some month, an `INNER JOIN` would silently drop that site's entire row — and we specifically need to see that it only has 10 months of invoices. Selecting `COUNT(i.id)` makes that gap explicit in the output.

The aggregation grain is one row per site. Don't compute the blended rate with `AVG(i.blended_rate_usd_per_kwh)` — that's a simple average of twelve monthly rates, giving every month equal weight, even though monthly usage varies a lot. The correct approach is to sum the dollar amounts and the energy volumes separately and then divide, which effectively weights by consumption. The two methods differ by nearly 5% at ALB1.

No CTE or window function needed here — a single `GROUP BY` does the job.

### SQL

```sql
SELECT
    s.site_code,
    s.site_name,
    m.code AS iso,
    s.contracted_capacity_mw,
    COUNT(i.id) AS invoice_months,
    ROUND(SUM(i.total_energy_mwh), 0) AS total_mwh,
    ROUND(SUM(i.total_amount_usd), 0) AS total_usd,
    -- 先求和再相除, 等价于按用电量加权. 直接 AVG(blended_rate) 会给小月份过高权重
    ROUND(SUM(i.total_amount_usd) / (SUM(i.total_energy_mwh) * 1000), 5) AS blended_usd_per_kwh
FROM site s
JOIN iso_market m ON m.id = s.iso_market_id
LEFT JOIN energy_invoice i
    ON i.site_id = s.id
    AND i.billing_period_end <= '2026-06-30'
GROUP BY s.id
ORDER BY total_usd DESC;
```

### Expected Result and Business Takeaway

Six rows, one per site.

| site_code | iso | capacity_mw | invoice_months | total_mwh | total_usd | blended_usd_per_kwh |
| :--- | :-- | :-- | :-- | :-- | :-- | :-- |
| CMH1 | PJM | 95 | 12 | 454,376 | 63,024,433 | 0.13871 |
| ABI1 | ERCOT | 110 | 12 | 825,817 | 40,000,389 | 0.04844 |
| ALB1 | PJM | 60 | 10 | 277,873 | 36,076,902 | 0.12983 |
| CID1 | MISO | 50 | 12 | 370,234 | 29,680,728 | 0.08017 |
| TPL1 | ERCOT | 75 | 12 | 449,195 | 22,897,485 | 0.05097 |
| FAR1 | MISO | 30 | 12 | 170,818 | 13,265,331 | 0.07766 |

The most striking line is the CMH1 vs. ABI1 comparison. The Columbus site has 15 MW less capacity than Abilene, uses only 55% as much energy, and yet costs 58% more. The blended rate is 0.13871 vs. 0.04844 — a 2.9x difference. The two Ohio sites together account for 48.4% of companywide electricity spend but only 28.7% of total consumption.

That directly answers Helen's question: the increase isn't a volume problem, it's a structural one. The money is concentrated at the two PJM sites.

Next action: break down CMH1's bill to see how much of that 0.13871 rate isn't energy cost at all. That's Q2.

---

## 4. Q2 Bill Structure Breakdown — Where the Money Actually Goes

### Business Context

Q1 surfaced a 3x rate gap, and Helen's next question is what's driving it. Her assumption is that PJM wholesale energy prices are simply higher, so the gap is all in energy cost. If that's true, there's nothing to do but relocate sites, and this line of inquiry ends there.

VP of Energy Strategy Dana Whitfield doesn't buy that assumption. She believes a large chunk of the PJM bill isn't energy cost at all — it's a fixed charge based on peak power draw, and that piece can be managed down. The two of them couldn't settle it in the budget meeting, so it needs data.

The answer decides whether FY2027 gets a peak-shaving initiative: if demand-related charges are a large share of the bill, the investment is worth making; if the bill is basically all energy cost, it's wasted effort.

### Tags

Aggregation + window function / Basic / CFO

### Approach

You'll need four tables: `energy_invoice_line`, `energy_invoice`, `site`, and `iso_market`. The line-item amounts live in the line table, but market attribution has to be joined all the way back to `iso_market`, so this is a four-table chain.

The tricky part is computing the percentage share. Each charge category's amount needs to be divided by the total for its own market, not the companywide total, otherwise ERCOT and PJM numbers aren't comparable. A window function is the cleanest way to do this: `SUM(SUM(l.amount_usd)) OVER (PARTITION BY m.code)`. The double `SUM` looks odd but the logic is clear — the inner `SUM` produces the subtotal from `GROUP BY`, and the outer window function sums those subtotals again by market. Without a window function, you'd need a subquery to compute each market's total and join it back in, doubling the code length.

The aggregation grain is one row per market and charge category.

### SQL

```sql
SELECT
    m.code AS iso,
    l.charge_category,
    ROUND(SUM(l.amount_usd), 0) AS amount_usd,
    -- 内层 SUM 是分组小计, 外层窗口函数在小计上按市场再求和, 得到该市场的总额
    ROUND(SUM(l.amount_usd) * 100.0 / SUM(SUM(l.amount_usd)) OVER (PARTITION BY m.code), 1)
    AS pct_of_iso_total
FROM energy_invoice_line l
JOIN energy_invoice i ON i.id = l.energy_invoice_id
JOIN site s           ON s.id = i.site_id
JOIN iso_market m     ON m.id = s.iso_market_id
WHERE i.billing_period_end <= '2026-06-30'
GROUP BY m.code, l.charge_category
ORDER BY m.code, amount_usd DESC;
```

### Expected Result and Business Takeaway

Around eighteen rows, since the three markets don't have the same number of charge categories.

| iso | charge_category | amount_usd | pct_of_iso_total |
| :-- | :--- | :-- | :-- |
| ERCOT | ENERGY | 48,069,782 | 76.4 |
| ERCOT | TRANSMISSION | 3,221,580 | 5.1 |
| MISO | ENERGY | 23,266,991 | 54.2 |
| MISO | DEMAND | 10,179,091 | 23.7 |
| PJM | ENERGY | 46,359,265 | 46.8 |
| PJM | DEMAND | 25,456,220 | 25.7 |
| PJM | TRANSMISSION | 9,009,964 | 9.1 |
| PJM | CAPACITY | 6,827,863 | 6.9 |

Dana won this argument. ERCOT's bill is 76.4% Energy Charge, with everything else a rounding error by comparison. PJM is only 46.8% Energy Charge, while `DEMAND` alone accounts for 25.7%, or $25.46 million; add in `TRANSMISSION` and `CAPACITY`, which are also billed off the same billing demand figure, and the three together make up 41.7% of the PJM bill, or $41.29 million.

In other words, more than 40% of the electricity cost at those two PJM sites has nothing to do with how much energy is consumed — it depends entirely on how high the power draw spiked. That's a cost that's decoupled from energy usage, which means it can be optimized separately.

Next action: figure out exactly how that billing demand figure gets set, and whether it's being driven by a handful of isolated moments. This thread continues in Q12 and Q13.

---

## 5. Q3 Demand Response Program Enrollment and Committed Capacity

### Business Context

Every July, Demand Response Manager Priya Raghavan has to re-file enrolled capacity for the next program year with the ISOs, and the FY2027 filing window closes in mid-August. Before she starts drafting, she needs a current-state table: how many programs are we in, how much capacity is enrolled at which sites for each, and which baseline method each one uses.

This table has a secondary use too. While prepping for an audit, Finance found a long-standing zero-dollar receivable line related to DR that they suspect points to a bad enrollment record. Priya needs to double-check that the enrollment list is clean.

### Tags

Join + aggregation / Basic / Demand Response Manager

### Approach

Three tables: `dr_program`, `dr_enrollment`, `site`, plus `iso_market` for the market code.

The easiest place to get this wrong is where the filter condition sits. `dr_enrollment` has one legacy record with `is_active = 0` and zero committed capacity. If you put `e.is_active = 1` in the `WHERE` clause, a program whose enrollments have all lapsed would disappear entirely; putting it in the `ON` clause of the `LEFT JOIN` instead keeps the program visible with zero committed capacity. The latter is what Priya wants, since she needs to see the complete program list.

`GROUP_CONCAT` concatenates site codes into a single column, saving a manual lookup step. SQLite's `GROUP_CONCAT` takes the separator as its second argument, which differs from MySQL's `SEPARATOR` keyword syntax — worth not mixing up.

### SQL

```sql
SELECT
    p.program_code,
    m.code AS iso,
    p.program_type,
    p.baseline_method,
    COUNT(e.id)                           AS enrolled_sites,
    ROUND(SUM(e.enrolled_capacity_mw), 1) AS total_committed_mw,
    GROUP_CONCAT(s.site_code, ', ')       AS sites
FROM dr_program p
JOIN iso_market m ON m.id = p.iso_market_id
-- is_active 过滤放在 ON 里而不是 WHERE 里, 保证没有有效注册的项目也不会整行消失
LEFT JOIN dr_enrollment e ON e.dr_program_id = p.id AND e.is_active = 1
LEFT JOIN site s          ON s.id = e.site_id
GROUP BY p.id
ORDER BY total_committed_mw DESC;
```

### Expected Result and Business Takeaway

Six rows, one per program.

| program_code | iso | program_type | baseline_method | sites | total_committed_mw |
| :--- | :-- | :--- | :--- | :--- | :-- |
| ERCOT-4CP-AVOID | ERCOT | TRANSMISSION_AVOIDANCE | FIRM_SERVICE_LEVEL | ABI1, TPL1 | 100.0 |
| ERCOT-ERS-10 | ERCOT | EMERGENCY | AVG_10_BUSINESS_DAYS | ABI1, TPL1 | 17.0 |
| PJM-ELRP | PJM | EMERGENCY | AVG_10_BUSINESS_DAYS | CMH1, ALB1 | 15.0 |
| ERCOT-CLR-RRS | ERCOT | ECONOMIC | METER_BEFORE_AFTER | ABI1, TPL1 | 12.5 |
| PJM-CP | PJM | CAPACITY | FIRM_SERVICE_LEVEL | CMH1, ALB1 | 11.0 |
| MISO-LMR | MISO | CAPACITY | METER_BEFORE_AFTER | CID1, FAR1 | 7.5 |

Two things stand out. First, the 4CP avoidance program's committed capacity of 100 MW is more than double all the other programs combined, yet it only fires four times a year, two hours each time. This program's economics are fundamentally different from the other five, and every subsequent DR revenue analysis has to treat it separately.

Second, two of the six programs use the `AVG_10_BUSINESS_DAYS` baseline, totaling 32 MW committed. This is widely recognized as the most gameable baseline methodology in the industry, and Q7 digs into it specifically.

As for that zero-dollar receivable line in Finance: the enrollment filtered out by `is_active = 1` was Cedar Rapids registered under an ERCOT program, but Cedar Rapids is actually in MISO. It was a registration error from that year, deactivated partway through FY2026. Tell Finance they can close out this account.

Next action: how much did these enrollments actually earn in FY2026 settlement. See Q4.

---

## 6. Q4 Demand Response Settlement Revenue Ranking

### Business Context

This is the table Priya builds every quarter, and it's also the only table she's used to report DR results to management for the past two years. With FY2026 closed, she needs to break the full-year settlement revenue down by program and site for the annual summary.

Some context: DR programs have always been treated internally as pure upside. The equipment's already there, the grid needs load shed occasionally, the ISO pays for it — sounds like free money. One of Priya's annual goals is DR settlement revenue, and hitting it directly affects her team's performance review.

### Tags

Multi-table join + aggregation / Intermediate / Demand Response Manager

### Approach

Start from `dr_event_participation` and chain joins to `dr_event`, `dr_program`, `dr_enrollment`, and `site` — five tables. The chain is a bit long because site information isn't on the participation record directly; it's determined indirectly through the enrollment record, which is a normal cost of normalized modeling.

The critical filter condition is `pr.program_type <> 'TRANSMISSION_AVOIDANCE'`. The 4CP avoidance program doesn't generate a capacity payment — its payoff shows up in next year's transmission bill instead. Including it here would make it look like an unprofitable program when it isn't. Excluding it keeps this table focused purely on paid DR program revenue.

The aggregation grain is one row per program and site. `capacity_payment_usd`, `energy_payment_usd`, and `penalty_usd` are broken out separately because they mean fundamentally different things: capacity payment is guaranteed, energy payment depends on actual delivered reduction, and penalty is a clawback when curtailment falls short.

### SQL

```sql
SELECT
    pr.program_code,
    s.site_code,
    COUNT(*)                                AS participations,
    ROUND(SUM(p.delivered_reduction_mw), 1) AS total_delivered_mw,
    ROUND(AVG(p.performance_ratio), 2)      AS avg_performance,
    ROUND(SUM(p.capacity_payment_usd), 0)   AS capacity_usd,
    ROUND(SUM(p.energy_payment_usd), 0)     AS energy_usd,
    ROUND(SUM(p.penalty_usd), 0)            AS penalty_usd,
    ROUND(SUM(p.total_settlement_usd), 0)   AS settlement_usd
FROM dr_event_participation p
JOIN dr_event ev      ON ev.id = p.dr_event_id
JOIN dr_program pr    ON pr.id = ev.dr_program_id
JOIN dr_enrollment en ON en.id = p.dr_enrollment_id
JOIN site s           ON s.id = en.site_id
-- 4CP 躲避不产生结算收入, 它的回报在下一年的输电费上, 混进来会失真
WHERE pr.program_type <> 'TRANSMISSION_AVOIDANCE'
GROUP BY pr.program_code, s.site_code
ORDER BY settlement_usd DESC;
```

### Expected Result and Business Takeaway

Ten rows, one per program-site combination.

| program_code | site_code | participations | total_delivered_mw | avg_performance | settlement_usd |
| :--- | :-- | :-- | :-- | :-- | :-- |
| ERCOT-ERS-10 | ABI1 | 14 | 228.7 | 1.35 | 800,513 |
| PJM-ELRP | CMH1 | 11 | 147.0 | 1.48 | 443,423 |
| ERCOT-CLR-RRS | ABI1 | 9 | 180.7 | 1.84 | 439,837 |
| PJM-CP | CMH1 | 6 | 93.0 | 2.00 | 403,200 |
| ERCOT-ERS-10 | TPL1 | 14 | 135.2 | 1.73 | 325,249 |
| MISO-LMR | CID1 | 13 | 51.3 | 0.88 | 258,438 |
| ERCOT-CLR-RRS | TPL1 | 9 | 96.1 | 1.96 | 174,518 |
| PJM-CP | ALB1 | 3 | 29.9 | 1.95 | 168,000 |
| MISO-LMR | FAR1 | 13 | 31.9 | 0.82 | 159,191 |
| PJM-ELRP | ALB1 | 4 | 32.3 | 1.34 | 109,574 |

Total settlement revenue for the year is $3,281,943 (roughly $3.28 million), all ten rows positive, with only $7,275 in penalties. Most sites average well above 1.0 on performance ratio, meaning actual delivered reduction typically exceeds committed amounts. From this table, DR looks like an unimpeachable business, and Abilene is the clear standout, contributing $1.24 million.

This is the entire picture management has seen for the past two years. The numbers aren't wrong, and the methodology isn't miscalculated — the problem is that this table only accounts for the money coming in.

Next action: work out what the curtailed compute is actually worth, and put it on the same table. That's Q5, and it's the single most important query in this whole memo.

---

## 7. Q5 The Real Net Benefit of Demand Response

### Business Context

After reviewing Q4, Dana Whitfield asked a question: what's actually running on the load we're curtailing.

That question matters because Kestrel isn't curtailing pumps or electric furnaces — it's curtailing GPU clusters mid-training. Interrupt an eleven-day pretraining job, and you don't just lose the hours of the interruption itself; you also lose everything computed between the last checkpoint and the interruption point, unrecoverable. The dataset's pretraining jobs checkpoint every 300 minutes, and average rollback runs close to half that interval — meaning a two-hour curtailment actually costs closer to four hours.

The business team has assigned an internal opportunity-cost rate per job type, stored in `compute_job.internal_cost_usd_per_gpu_hour`, defined as "the revenue this GPU-hour would have generated if it hadn't been interrupted." The `curtailed_workload` table already computes the loss for every individual interruption.

The answer directly shapes the FY2027 DR filing: keep filing at current levels, or pull committed capacity out of certain sites.

### Tags

CTE + multi-table join / Advanced / VP of Energy Strategy

### Approach

The core of this problem is aligning two amounts from completely different sources to the same grain, so computing them in two separate CTEs and joining at the end is the cleanest approach.

The first CTE computes settlement revenue, following the same path as Q4, but rolled up to site grain. The second CTE computes compute cost, starting from `curtailed_workload` and joining `curtailment_action` to get the site.

There's a filter condition you absolutely must get right here: `c.curtailment_type = 'DR_EVENT'`. There are three types of curtailment action overall — besides DR-event-triggered curtailment, there's also 4CP avoidance and pure economic curtailment. Cost from the latter two has nothing to do with DR settlement revenue; including it would inflate cost by upwards of two million dollars and push the conclusion toward a wildly wrong extreme. This is the easiest place to trip up on this question.

The two CTEs must be joined with `LEFT JOIN`, not `INNER JOIN`. In principle every site with settlement should have a matching curtailment record, but if a particular site happened to have no jobs running during a given event, it simply won't appear in the cost CTE — an `INNER JOIN` would drop that site's entire row, which happens to be exactly the case with the highest net benefit. Use `LEFT JOIN` with `COALESCE` to guard against this.

Finally, sort by net benefit ascending, so the biggest losses appear first.

### SQL

```sql
WITH settlement AS (
    SELECT
        s.id   AS site_id,
        s.site_code,
        SUM(p.total_settlement_usd) AS settlement_usd
    FROM dr_event_participation p
    JOIN dr_event ev      ON ev.id = p.dr_event_id
    JOIN dr_program pr    ON pr.id = ev.dr_program_id
    JOIN dr_enrollment en ON en.id = p.dr_enrollment_id
    JOIN site s           ON s.id = en.site_id
    WHERE pr.program_type <> 'TRANSMISSION_AVOIDANCE'
    GROUP BY s.id
),
compute_cost AS (
    -- 只统计 DR_EVENT 类削减. ECONOMIC 与 4CP_AVOIDANCE 各有各的账,
    -- 混进来会虚增成本两百多万美元, 把结论推到错误的方向
    SELECT
        c.site_id,
        SUM(w.opportunity_cost_usd) AS opportunity_usd,
        SUM(w.sla_credit_usd)       AS sla_credit_usd,
        SUM(w.lost_gpu_hours)       AS lost_gpu_hours
    FROM curtailed_workload w
    JOIN curtailment_action c ON c.id = w.curtailment_action_id
    WHERE c.curtailment_type = 'DR_EVENT'
    GROUP BY c.site_id
)
SELECT
    st.site_code,
    si.primary_workload_type,
    ROUND(st.settlement_usd, 0)                 AS settlement_usd,
    ROUND(COALESCE(cc.lost_gpu_hours, 0), 0)    AS lost_gpu_hours,
    ROUND(COALESCE(cc.opportunity_usd, 0), 0)   AS opportunity_usd,
    ROUND(COALESCE(cc.sla_credit_usd, 0), 0)    AS sla_credit_usd,
    ROUND(st.settlement_usd
        - COALESCE(cc.opportunity_usd, 0)
        - COALESCE(cc.sla_credit_usd, 0), 0)  AS net_benefit_usd
FROM settlement st
JOIN site si              ON si.id = st.site_id
LEFT JOIN compute_cost cc ON cc.site_id = st.site_id
ORDER BY net_benefit_usd;
```

### Expected Result and Business Takeaway

Six rows, one per site, sorted by net benefit ascending.

| site_code | workload_type | settlement_usd | lost_gpu_hours | opportunity_usd | sla_credit_usd | net_benefit_usd |
| :--- | :--- | :-- | :-- | :-- | :-- | :-- |
| ABI1 | TRAINING | 1,240,350 | 497,529 | 1,561,080 | 95,690 | -416,419 |
| CID1 | TRAINING | 258,438 | 135,916 | 426,672 | 35,085 | -203,319 |
| FAR1 | MIXED | 159,191 | 63,401 | 187,698 | 31,327 | -59,835 |
| ALB1 | MIXED | 277,574 | 62,270 | 152,178 | 32,552 | 92,844 |
| TPL1 | MIXED | 499,767 | 130,551 | 391,150 | 6,978 | 101,639 |
| CMH1 | INFERENCE | 846,623 | 165,423 | 396,395 | 73,787 | 376,442 |

Companywide totals: settlement revenue of $3.28 million, compute opportunity cost plus SLA credit of $3.39 million, for a real net benefit of **negative $109,000**. The $3.28 million profit that's been reported for the past two years is actually a loss on a net basis.

But the total isn't the most useful piece of information here — the distribution is. The `primary_workload_type` column tells the story clearly: the two sites running long-cycle training jobs (ABI1, CID1) are net negative $620,000 combined, while CMH1, which runs online inference, is net positive $376,400. The same DR program is two completely different businesses depending on the type of site it runs on.

The reason is buried in the `lost_gpu_hours` column. Compare it against settlement revenue and the gap becomes clear: ABI1 only recoups $2.49 in settlement per GPU-hour sacrificed ($1,240,350 divided by 497,529), while the actual cost per GPU-hour is $3.14; CMH1 recoups $5.12 per GPU-hour sacrificed ($846,623 divided by 165,423), with a cost of only $2.40. The two sites curtail a similar amount of load on an energy basis, but ABI1 pays out roughly three times as many GPU-hours as CMH1. The reason is that ABI1 runs pretraining jobs with a 300-minute checkpoint interval, so every interruption also costs a large chunk of rollback on top of the interval itself, while online inference jobs can simply drop traffic and reconnect it later at zero rollback cost.

Next action: this isn't about exiting DR, it's about relocating where DR happens. Draft an FY2027 filing adjustment that brings ABI1 and CID1's committed capacity down to near zero and shifts the freed-up allocation to CMH1 and ALB1. Before submitting, use Q6 to confirm this isn't being driven by a handful of extreme events.

---

## 8. Q6 Which Sites and Which Events Are Losing Money

### Business Context

Dana didn't sign off immediately after seeing Q5's conclusion. Her specific concern: the full-year loss could be driven by two or three particularly bad events — say, one that happened to coincide with a 4,000-GPU job. If that's what's going on, the right fix is "adjust scheduling to avoid large jobs," not "exit DR at this site."

Telling the two scenarios apart requires looking at how the losses are distributed: are they concentrated in a handful of events, or is nearly every event losing money.

This distinction determines the nature of the plan: the former is an operational fix, the latter is a strategic exit.

### Tags

CTE + correlated subquery / Intermediate / VP of Energy Strategy

### Approach

The grain needs to drop down to "one event at one site." Settlement amounts are already at this grain (one row in `dr_event_participation` is one event plus one enrollment), but compute cost lives in `curtailed_workload` and needs to be matched using both the `dr_event_id` and `site_id` fields on `curtailment_action` together to align correctly.

A correlated subquery is more straightforward here than another CTE, because the match condition spans two fields — writing it as a CTE and joining would require handling null join keys. The `COALESCE(SUM(...), 0)` inside the correlated subquery ensures an event with no interrupted jobs returns 0 instead of NULL, otherwise the subsequent subtraction would turn the whole row into NULL — one of the most common silent errors in SQL.

Note that `site` is joined twice in the CTE (aliased `s` and `si`) so the outer query can pull both the site code and the workload type. A single join would technically be enough; keeping two aliases just makes the source of each field obvious at a glance.

The outer query aggregates by site, counting negative-net events and their share of the total. That share is what answers Dana's question.

### SQL

```sql
WITH per_event AS (
    SELECT
        ev.id           AS event_id,
        ev.event_code,
        pr.program_code,
        s.site_code,
        si.primary_workload_type,
        p.total_settlement_usd,
        -- 用 dr_event_id 和 site_id 两个字段一起匹配才能对齐到 "一次事件在一座园区"
        -- COALESCE 兜住没有任务被中断的情况, 否则后面减法会整行变 NULL
        (SELECT COALESCE(SUM(w.opportunity_cost_usd + w.sla_credit_usd), 0)
        FROM curtailed_workload w
        JOIN curtailment_action c ON c.id = w.curtailment_action_id
        WHERE c.dr_event_id = ev.id
            AND c.site_id     = s.id
            AND c.curtailment_type = 'DR_EVENT') AS compute_cost_usd
    FROM dr_event_participation p
    JOIN dr_event ev      ON ev.id = p.dr_event_id
    JOIN dr_program pr    ON pr.id = ev.dr_program_id
    JOIN dr_enrollment en ON en.id = p.dr_enrollment_id
    JOIN site s           ON s.id = en.site_id
    JOIN site si          ON si.id = s.id
    WHERE pr.program_type <> 'TRANSMISSION_AVOIDANCE'
)
SELECT
    site_code,
    primary_workload_type,
    COUNT(*) AS participations,
    SUM(CASE WHEN total_settlement_usd - compute_cost_usd < 0 THEN 1 ELSE 0 END) AS negative_events,
    ROUND(SUM(CASE WHEN total_settlement_usd - compute_cost_usd < 0 THEN 1 ELSE 0 END)
        * 100.0 / COUNT(*), 1)                          AS negative_pct,
    ROUND(MIN(total_settlement_usd - compute_cost_usd), 0) AS worst_event_usd,
    ROUND(AVG(total_settlement_usd - compute_cost_usd), 0) AS avg_net_usd
FROM per_event
GROUP BY site_code
ORDER BY avg_net_usd;
```

### Expected Result and Business Takeaway

Six rows.

| site_code | workload_type | participations | negative_events | negative_pct | worst_event_usd | avg_net_usd |
| :--- | :--- | :-- | :-- | :-- | :-- | :-- |
| ABI1 | TRAINING | 23 | 18 | 78.3 | -72,169 | -18,105 |
| CID1 | TRAINING | 13 | 12 | 92.3 | -28,684 | -15,640 |
| FAR1 | MIXED | 13 | 9 | 69.2 | -17,246 | -4,603 |
| TPL1 | MIXED | 23 | 9 | 39.1 | -23,969 | 4,419 |
| ALB1 | MIXED | 7 | 3 | 42.9 | -21,880 | 13,263 |
| CMH1 | INFERENCE | 17 | 6 | 35.3 | -20,401 | 22,144 |

Dana's concern is ruled out. 92.3% of CID1's events are net negative, and 78.3% of ABI1's — this isn't a handful of extreme events, it's systemic. Across the six sites, 57 of 96 total participations lost money (this only counts non-4CP paid DR participation; the 8 4CP participations are already excluded by `program_type <> 'TRANSMISSION_AVOIDANCE'`).

CMH1 looks very different by comparison: 65% of its events are profitable, averaging $22,144 net per event. Its worst event lost $20,401 — nowhere near ABI1's worst of $72,169.

The conclusion shifts from "operational fix" to "strategic realignment": ABI1 and CID1 should exit paid DR programs, with their committed capacity transferred to CMH1 and ALB1. A rough calculation using averages shows that shifting ABI1's 21 MW commitment to CMH1 could move FY2027's net benefit from negative $109,000 to a positive $600,000 or more.

Next action: write this recommendation into section two of the memo. But before submitting, there's a thornier question to resolve first: whether the curtailment volumes reported to the ISO are even credible in the first place. See Q7.

---

## 9. Q7 Screening for Suspected Baseline Inflation Events

### Business Context

Priya heard something at an industry conference: a certain ISO ran a retrospective audit last year, recalculating curtailment volumes for multiple participants and clawing back seven-figure settlement amounts. The audit's entry point was the baseline — specifically, checking whether load spiked unusually in the days leading up to an event.

That got her uneasy. Of the six programs Kestrel participates in, two use the `AVG_10_BUSINESS_DAYS` baseline — meaning the average load over the same time window across the ten prior business days is used as the reference point. This methodology has a well-known weakness: use a bit more power in the days leading up to an event, and the baseline rises with it, inflating the reported curtailment — and it's entirely compliant, because no rule prohibits using more electricity.

The question is whether anyone at Kestrel has actually been doing this. The dispatch system is automated, but the dispatch strategy is set by people. Priya needs to check this herself before an ISO comes knocking.

Two diagnostic fields already exist in the data for exactly this purpose: `pre_event_3day_avg_mw` and `pre_event_30day_avg_mw`. They don't feed into settlement — they exist purely for this kind of audit.

### Tags

Join + ratio filter / Intermediate / Demand Response Manager

### Approach

The idea itself is simple: compute the ratio of the two diagnostic fields, and flag anything above a threshold. The hard part is picking the threshold and deciding which programs to look at.

Only look at `AVG_10_BUSINESS_DAYS` programs, since the other two baseline methods aren't sensitive to pre-event behavior over the last three days. `METER_BEFORE_AFTER` takes one hour before and after the event, and `FIRM_SERVICE_LEVEL` takes a same-time-window average over the prior thirty days — a three-day anomaly spread across thirty days only moves the average by a percentage point or so. Including them would just dilute the signal.

Use a threshold of 1.06. Under normal operation, load has seasonal and week-to-week variation, and a 3–4% gap between the 3-day and 30-day averages is common — but anything over 6% needs an explanation.

Watch the denominator when dividing. In this dataset, `pre_event_30day_avg_mw` is never zero (every site is operating whenever an event occurs), so dividing directly is safe. On a different dataset you'd want a `NULLIF` guard.

Listing `baseline_mw`, `delivered_reduction_mw`, and `settlement_usd` together lets every flagged record show exactly how much money is at stake.

### SQL

```sql
SELECT
    pr.program_code,
    pr.baseline_method,
    s.site_code,
    ev.event_code,
    DATE(ev.event_start)                                         AS event_date,
    p.pre_event_3day_avg_mw,
    p.pre_event_30day_avg_mw,
    ROUND(p.pre_event_3day_avg_mw / p.pre_event_30day_avg_mw, 4) AS inflation_ratio,
    p.baseline_mw,
    p.delivered_reduction_mw,
    ROUND(p.total_settlement_usd, 0)                             AS settlement_usd
FROM dr_event_participation p
JOIN dr_event ev      ON ev.id = p.dr_event_id
JOIN dr_program pr    ON pr.id = ev.dr_program_id
JOIN dr_enrollment en ON en.id = p.dr_enrollment_id
JOIN site s           ON s.id = en.site_id
-- 只有这种基线算法会被事件前三天的行为影响, 另外两种天然免疫
WHERE pr.baseline_method = 'AVG_10_BUSINESS_DAYS'
    AND p.pre_event_3day_avg_mw / p.pre_event_30day_avg_mw >= 1.06
ORDER BY inflation_ratio DESC;
```

### Expected Result and Business Takeaway

Around ten rows, concentrated entirely at TPL1 and CMH1.

| program_code | site_code | event_code | event_date | 3day_mw | 30day_mw | inflation_ratio | settlement_usd |
| :--- | :-- | :--- | :--- | :-- | :-- | :-- | :-- |
| PJM-ELRP | CMH1 | PJM-ELRP-FY26-11 | 2026-06-29 | 63.130 | 55.072 | 1.1463 | 40,521 |
| ERCOT-ERS-10 | TPL1 | ERCOT-ERS-10-FY26-11 | 2026-06-11 | 60.445 | 53.989 | 1.1196 | 24,000 |
| PJM-ELRP | CMH1 | PJM-ELRP-FY26-09 | 2026-06-01 | 57.835 | 52.188 | 1.1082 | 42,727 |
| ERCOT-ERS-10 | TPL1 | ERCOT-ERS-10-FY26-12 | 2026-06-19 | 61.021 | 55.245 | 1.1046 | 24,000 |

The ten flagged records total $337,283 in settlement, 117.1 MW of credited curtailment, and an average inflation ratio of 1.0922.

The distribution is telling. A meaningful share of events on the two `AVG_10_BUSINESS_DAYS` programs got flagged, while not a single event on the other two baseline methods was flagged — their ratios all stayed within 1.03. If this were natural variation, all three baseline methods should show similar distributions. The fact that they don't tells you this isn't random noise.

There's another detail worth noting: six of the flagged events cluster in June 2026 — the last month of the fiscal year. That timing is hard to explain as coincidence.

Next action: these records can't be labeled as violations on their own, since using more electricity doesn't break any rule. But Priya needs to know the exposure if the ISO recomputes with a clean baseline. See Q8.

---

## 10. Q8 Recomputing With a Clean Baseline — How Much Was Overstated

### Business Context

Q7 flagged ten suspicious records totaling $337,000. But that $337,000 is the full settlement amount for those events — not the amount that would need to be paid back. The real exposure is "how much less the curtailment would be worth once recomputed with a clean baseline."

Dana needs a specific number for the board, and one that can hold up under questioning: how exactly was this exposure figure derived.

This number also has a more practical use. If the exposure is only a few tens of thousands of dollars, an internal correction to dispatch strategy is enough; if it's six figures, proactive disclosure to the ISO is warranted, because self-reporting and getting caught by an audit are two very different outcomes.

### Tags

Multi-level CTE / Advanced / VP of Energy Strategy

### Approach

The core idea is constructing a counterfactual baseline. The logic goes like this: the existing `baseline_mw` was calculated off load that had already been inflated, and the size of the inflation can be estimated using the ratio `pre_event_3day_avg_mw / pre_event_30day_avg_mw`. So dividing `baseline_mw` by that ratio (equivalent to multiplying by its reciprocal) gives you "roughly what the baseline would have been if the three days before the event hadn't been anomalous."

This is an estimate, not an exact recomputation — a true recomputation would require pulling the interval-level load for every one of the ten prior business days and recalculating the average from scratch. But as an estimate of the order of magnitude of the exposure it holds up, and the logic is simple enough to explain to the board in a single sentence.

The first CTE, `flagged`, reuses Q7's screening condition and computes the corrected baseline along the way. The second CTE, `recomputed`, subtracts actual metered load from the corrected baseline to get the corrected delivered reduction — this must be wrapped in `MAX(0, ...)`, since the corrected baseline can end up lower than actual metered load, and delivered reduction can't be negative. SQLite's `MAX` with two arguments is a scalar function, not an aggregate — unlike some other dialects — which is exactly what's needed here.

Finally, aggregate by site to report credited volume, corrected volume, overstated volume, and overstatement percentage.

### SQL

```sql
WITH flagged AS (
    SELECT
        p.id,
        s.site_code,
        p.baseline_mw,
        p.actual_metered_mw,
        p.delivered_reduction_mw,
        p.total_settlement_usd,
        p.pre_event_3day_avg_mw / p.pre_event_30day_avg_mw AS inflation_ratio,
        -- 把基线按灌水比例还原回去, 得到 "事件前三天没有异常时" 的估计基线
        p.baseline_mw * (p.pre_event_30day_avg_mw / p.pre_event_3day_avg_mw) AS corrected_baseline_mw
    FROM dr_event_participation p
    JOIN dr_event ev      ON ev.id = p.dr_event_id
    JOIN dr_program pr    ON pr.id = ev.dr_program_id
    JOIN dr_enrollment en ON en.id = p.dr_enrollment_id
    JOIN site s           ON s.id = en.site_id
    WHERE pr.baseline_method = 'AVG_10_BUSINESS_DAYS'
        AND p.pre_event_3day_avg_mw / p.pre_event_30day_avg_mw >= 1.06
),
recomputed AS (
    SELECT
        site_code,
        delivered_reduction_mw,
        -- 修正基线可能低于实测负载, 削减量不能为负. SQLite 的双参数 MAX 是标量函数
        MAX(0, corrected_baseline_mw - actual_metered_mw) AS corrected_delivered_mw,
        total_settlement_usd
    FROM flagged
)
SELECT
    site_code,
    COUNT(*)                                                       AS flagged_participations,
    ROUND(SUM(delivered_reduction_mw), 1)                          AS claimed_mw,
    ROUND(SUM(corrected_delivered_mw), 1)                          AS corrected_mw,
    ROUND(SUM(delivered_reduction_mw - corrected_delivered_mw), 1) AS overstated_mw,
    ROUND(SUM(delivered_reduction_mw - corrected_delivered_mw) * 100.0
        / SUM(delivered_reduction_mw), 1)                        AS overstated_pct,
    ROUND(SUM(total_settlement_usd), 0)                            AS settlement_at_risk_usd
FROM recomputed
GROUP BY site_code
ORDER BY overstated_mw DESC;
```

### Expected Result and Business Takeaway

Two rows, TPL1 and CMH1.

| site_code | flagged_participations | claimed_mw | corrected_mw | overstated_mw | overstated_pct | settlement_at_risk_usd |
| :--- | :-- | :-- | :-- | :-- | :-- | :-- |
| CMH1 | 6 | 82.1 | 51.6 | 30.5 | 37.2 | 241,283 |
| TPL1 | 4 | 35.0 | 15.3 | 19.6 | 56.1 | 96,000 |

Combined across both sites: credited curtailment of 117.1 MW, 66.9 MW after correction, 50.1 MW overstated — an overstatement rate of roughly 43%. Total settlement amount involved is $337,000, and applying the overstatement ratio puts the exposure at roughly $140,000.

TPL1's 56.1% overstatement rate is especially striking: more than half of the credited curtailment on those events came from an inflated baseline, not from actually using less power.

$140,000 falls into the "needs proactive action but isn't a disaster" range. The cost of self-reporting is repayment plus a compliance review; the cost of getting caught by an audit is repayment plus penalties plus heightened scrutiny for years to come.

Next action: three things. First, change the dispatch strategy's pre-event load scheduling rules — that's the root cause. Second, build a monthly monitor that turns Q7's ratio into an alert, flagging automatically above 1.06. Third, draft a proactive disclosure package covering these ten FY2026 records, to be co-signed by Legal and Dana before submitting to the ISO.

---

## 11. Q9 Monthly Wind PPA vs. Simple Average Market Price

### Business Context

Power Procurement Manager Marcus Ellery produces a monthly PPA settlement comparison showing the gap between the Longhorn Ridge 150 MW wind PPA's strike price and that month's average market price. This table is his main evidence for demonstrating PPA value to management, and it's also the argument he used last year to push through renewal of two other solar PPAs.

The FY2027 renewal window opens next January. The Longhorn Ridge contract still has nine years left, but it includes a five-year renegotiation clause, and next January is the first exercise window. Marcus needs to decide whether to exercise it or leave the contract as-is.

His judgment so far has rested on: a strike price of $28.50/MWh, a West Texas node annual average price of $35.47, a savings of $6.97/MWh, annual generation of 367,000 MWh, and total savings north of $2.5 million. Looks like a good deal — no need to renegotiate.

### Tags

CTE + aggregation / Basic / Power Procurement Manager

### Approach

Two datasets at different grains need to be aligned to monthly: `lmp_interval_price` is 15-minute grain, and `ppa_generation_hourly` is hourly grain. Aggregate each to monthly in its own CTE first, then join on year-month.

The relationship between node and contract goes through `site_id`: `pricing_node.site_id` points to a site, and `supply_contract.site_id` also points to a site, and the two meet at the same site. This is a somewhat non-obvious but essential join path in the data model.

Use `STRFTIME('%Y-%m', ...)` to extract year-month. SQLite has neither `DATE_TRUNC` nor `EXTRACT`; date handling generally relies on `STRFTIME`, whose format string matches C's `strftime`.

The market average price here uses `AVG(lmp_usd_per_mwh)` — a simple average across every 15-minute interval in the month, with every interval weighted equally. This is exactly the method Marcus has always used. Keep that in mind — Q10 comes back to address it.

### SQL

```sql
WITH monthly_market AS (
    SELECT
        n.site_id,
        STRFTIME('%Y-%m', l.interval_start) AS ym,
        AVG(l.lmp_usd_per_mwh)              AS simple_avg_lmp
    FROM lmp_interval_price l
    JOIN pricing_node n ON n.id = l.pricing_node_id
    GROUP BY n.site_id, ym
),
monthly_gen AS (
    SELECT
        g.supply_contract_id,
        STRFTIME('%Y-%m', g.observed_at) AS ym,
        SUM(g.generation_mwh)            AS gen_mwh
    FROM ppa_generation_hourly g
    GROUP BY g.supply_contract_id, ym
)
SELECT
    mg.ym,
    ROUND(mg.gen_mwh, 0)                       AS ppa_mwh,
    c.strike_price_usd_per_mwh                 AS strike,
    ROUND(mm.simple_avg_lmp, 2)                AS market_simple_avg,
    ROUND((mm.simple_avg_lmp - c.strike_price_usd_per_mwh) * mg.gen_mwh, 0) AS apparent_saving_usd
FROM monthly_gen mg
JOIN supply_contract c ON c.id = mg.supply_contract_id
-- 节点与合约通过 site_id 碰头, 这是数据模型里不太直观但必须走的路径
JOIN monthly_market mm ON mm.site_id = c.site_id AND mm.ym = mg.ym
WHERE c.contract_code = 'PPA-LHR-WIND-01'
ORDER BY mg.ym;
```

### Expected Result and Business Takeaway

Twelve rows, one per month.

| ym | ppa_mwh | strike | market_simple_avg | apparent_saving_usd |
| :--- | :-- | :-- | :-- | :-- |
| 2025-07 | 30,429 | 28.50 | 60.31 | 968,072 |
| 2025-08 | 24,985 | 28.50 | 54.95 | 660,779 |
| 2025-12 | 26,954 | 28.50 | 40.72 | 329,270 |
| 2026-02 | 33,870 | 28.50 | 20.12 | -283,955 |
| 2026-03 | 40,857 | 28.50 | 12.79 | -641,694 |
| 2026-04 | 40,571 | 28.50 | 10.65 | -724,018 |
| 2026-05 | 39,594 | 28.50 | 14.09 | -570,409 |

The answer is hiding right in this table — Marcus just hasn't looked at it from this angle. Look at the relationship between the two columns: the four highest-generation months (February through May 2026, each between 34,000 and 40,000 MWh) are exactly the four lowest-market-price months (10.65 to 20.12 dollars per MWh), and the "savings" for these months are all negative. Meanwhile, July and August, the two months with the biggest apparent savings, have the lowest generation of the year.

In other words, this contract buys heavily when electricity is cheap and barely buys anything when electricity is expensive. The "$2.5 million saved" conclusion built on the annual average treats every month as equally weighted, which it isn't.

Next action: recompute using a generation-weighted average to get the true price gap. See Q10.

---

## 12. Q10 The True Generation-Weighted PPA Price Gap

### Business Context

Q9's monthly table got Marcus wondering whether the whole methodology is off. But he needs a number he can put directly into the renewal recommendation — and it needs to work across all three variable-generation PPAs at once, because if the wind PPA has a problem, the two solar PPAs need to be reviewed together with it.

The industry term for this concept is shape risk: the electricity you're actually buying is concentrated in the hours when the plant's output is highest, and if those hours happen to coincide with the lowest market prices, a comparison built on the annual average price is simply wrong. The correct methodology is a generation-weighted market price.

This number directly determines next January's renegotiation decision, spans a nine-year contract term, and is Marcus's most consequential call of the year.

### Tags

CTE + weighted aggregation / Advanced / Power Procurement Manager

### Approach

The key step is aggregating the 15-minute price data up to hourly first, so it can be aligned one-to-one with hourly generation data. Joining 15-minute data directly against hourly data would produce a 4x row-count blow-up; the weighted result would happen to still be correct (since all four intervals within an hour carry equal weight), but the row blow-up would make the subsequent `SUM(generation_mwh)` come out 4x too high, throwing off annual generation entirely. This is the easiest place to trip up on this question.

The `hourly_price` CTE uses `STRFTIME('%Y-%m-%d %H', ...)` to build an hour key, compressing prices down to hourly grain. The `simple_avg` CTE preserves Q9's simple-average methodology, so the two methods can sit side by side on the same row and the gap is immediately visible.

The weighted average is written as `SUM(generation_mwh * hourly_lmp) / SUM(generation_mwh)`. Note this can't be written as `AVG(generation_mwh * hourly_lmp)` — that computes something else entirely.

The last two columns exist for decision-making purposes: `apparent_saving_usd` is the conclusion under the wrong methodology, `true_net_cost_usd` is the conclusion under the correct one — a positive value means the PPA is actually more expensive than just buying on the market.

All three contracts are computed together, with the solar PPAs serving as a natural control group.

### SQL

```sql
WITH hourly_price AS (
    -- 必须先把 15 分钟电价压到小时. 直接和小时级发电量 join 会产生四倍行数膨胀,
    -- 加权价碰巧还对, 但 SUM(generation_mwh) 会变成四倍, 年发电量直接错掉
    SELECT
        n.site_id,
        STRFTIME('%Y-%m-%d %H', l.interval_start) AS hour_key,
        AVG(l.lmp_usd_per_mwh)                    AS hourly_lmp
    FROM lmp_interval_price l
    JOIN pricing_node n ON n.id = l.pricing_node_id
    GROUP BY n.site_id, hour_key
),
simple_avg AS (
    SELECT n.site_id, AVG(l.lmp_usd_per_mwh) AS simple_avg_lmp
    FROM lmp_interval_price l
    JOIN pricing_node n ON n.id = l.pricing_node_id
    GROUP BY n.site_id
)
SELECT
    c.contract_code,
    c.contract_type,
    s.site_code,
    c.strike_price_usd_per_mwh AS strike,
    ROUND(sa.simple_avg_lmp, 2) AS market_simple_avg,
    ROUND(SUM(g.generation_mwh * hp.hourly_lmp) / SUM(g.generation_mwh), 2) AS market_gen_weighted,
    ROUND(SUM(g.generation_mwh), 0) AS annual_mwh,
    ROUND((sa.simple_avg_lmp - c.strike_price_usd_per_mwh) * SUM(g.generation_mwh), 0)
    AS apparent_saving_usd,
    ROUND(SUM(g.generation_mwh) * c.strike_price_usd_per_mwh
        - SUM(g.generation_mwh * hp.hourly_lmp), 0) AS true_net_cost_usd
FROM ppa_generation_hourly g
JOIN supply_contract c ON c.id = g.supply_contract_id
JOIN site s            ON s.id = c.site_id
JOIN hourly_price hp   ON hp.site_id  = c.site_id
    AND hp.hour_key = STRFTIME('%Y-%m-%d %H', g.observed_at)
JOIN simple_avg sa     ON sa.site_id = c.site_id
GROUP BY c.id
ORDER BY true_net_cost_usd DESC;
```

### Expected Result and Business Takeaway

Three rows, one per variable-generation PPA.

| contract_code | type | strike | market_simple_avg | market_gen_weighted | annual_mwh | apparent_saving_usd | true_net_cost_usd |
| :--- | :--- | :-- | :-- | :-- | :-- | :-- | :-- |
| PPA-LHR-WIND-01 | WIND_PPA | 28.50 | 35.47 | 25.54 | 367,498 | 2,560,062 | 1,088,973 |
| PPA-BUC-SOLAR-01 | SOLAR_PPA | 38.90 | 45.09 | 49.56 | 74,259 | 459,894 | -791,768 |
| PPA-BLK-SOLAR-01 | SOLAR_PPA | 31.75 | 39.37 | 48.59 | 139,168 | 1,060,405 | -2,343,603 |

The wind row gives a clear answer. Simple average price of 35.47, generation-weighted average of 25.54, a gap of $9.93/MWh. The strike price of 28.50 is above the weighted average, meaning this contract actually costs $1,088,973 more than just buying on the market. Under Marcus's original methodology, the conclusion was $2.56 million in savings. The two numbers differ by $3.65 million, with opposite signs.

The two solar PPAs form a perfect control group. Their generation-weighted averages (49.56 and 48.59) are actually higher than their simple averages (45.09 and 39.37), because the hours with the most sunshine tend to be exactly the hours with the highest power demand and highest prices. So the solar PPAs' shape value is positive — the two contracts genuinely save $791,800 and $2,343,600.

The conclusion isn't "all PPAs are traps," it's "the wind PPA at this West Texas node is a trap, but solar isn't." The difference comes down to whether the generation shape and the price shape move together or in opposite directions.

Next action: the January renegotiation window must be exercised, with the goal of restructuring Longhorn Ridge's settlement from as generated to something with a shape adjustment, or simply reducing volume. The recommendation should include Q11's chart as a mechanistic explanation, since the board needs to understand why this happens, not just the result.

---

## 13. Q11 Does More Wind Output Mean Lower Prices

### Business Context

You showed Dana the Q10 conclusion, and her reaction was: this will get challenged, because it's counterintuitive. Someone on the board is going to ask why locking in a cheap wind price is a bad thing.

Answering that requires showing the mechanism, not just handing over a weighted average. The mechanism is this: West Texas wind capacity is extremely dense, and when it's windy, hundreds of turbines run at full output simultaneously, pushing the local node's marginal price down very low or even negative; when the wind stops, prices spike, but that's exactly when your PPA can't deliver a single megawatt-hour.

This table needs to quantify that mechanism and go into the recommendation's appendix.

### Tags

CASE bucketing + window function / Intermediate / Energy Data Analyst

### Approach

Bucket by capacity factor and look at the average price in each bucket. If the mechanism holds, price should decrease monotonically as the output bucket rises.

Start with a CTE that compresses node prices to hourly, same rationale as Q10. Then use `CASE WHEN` to split into five buckets by `capacity_factor_pct`. The bucket boundaries need to be meaningful: below 10% is essentially no wind, above 55% is full output, and the three middle buckets cover normal operating range.

The `pct_of_annual_gen` column uses the window function `SUM(SUM(generation_mwh)) OVER ()`. An empty `OVER ()` means no partitioning — summing across all grouped results, i.e., total annual generation. This is much cleaner than nesting another subquery.

The last column, `negative_price_hours`, counts how many hours in each bucket had negative prices. This column is more persuasive than the average, because negative pricing is a binary, unambiguous fact.

### SQL

```sql
WITH hourly_price AS (
    SELECT
        STRFTIME('%Y-%m-%d %H', l.interval_start) AS hour_key,
        AVG(l.lmp_usd_per_mwh)                    AS hourly_lmp
    FROM lmp_interval_price l
    JOIN pricing_node n ON n.id = l.pricing_node_id
    WHERE n.node_code = 'HB_WEST_ABI'
    GROUP BY hour_key
),
bucketed AS (
    SELECT
        CASE
        WHEN g.capacity_factor_pct <  10 THEN '1. 0-10 pct 几乎无风'
        WHEN g.capacity_factor_pct <  25 THEN '2. 10-25 pct 小风'
        WHEN g.capacity_factor_pct <  40 THEN '3. 25-40 pct 常态'
        WHEN g.capacity_factor_pct <  55 THEN '4. 40-55 pct 大风'
        ELSE                                  '5. 55 pct 以上 满发'
        END AS cf_bucket,
        hp.hourly_lmp,
        g.generation_mwh
    FROM ppa_generation_hourly g
    JOIN supply_contract c ON c.id = g.supply_contract_id
    JOIN hourly_price hp   ON hp.hour_key = STRFTIME('%Y-%m-%d %H', g.observed_at)
    WHERE c.contract_code = 'PPA-LHR-WIND-01'
)
SELECT
    cf_bucket,
    COUNT(*)                      AS hours,
    ROUND(AVG(hourly_lmp), 2)     AS avg_lmp,
    ROUND(SUM(generation_mwh), 0) AS gen_mwh,
    -- 空的 OVER () 表示在全部分组上求和, 得到全年总发电量
    ROUND(SUM(generation_mwh) * 100.0 / SUM(SUM(generation_mwh)) OVER (), 1) AS pct_of_annual_gen,
    SUM(CASE WHEN hourly_lmp < 0 THEN 1 ELSE 0 END) AS negative_price_hours
FROM bucketed
GROUP BY cf_bucket
ORDER BY cf_bucket;
```

### Expected Result and Business Takeaway

Five rows, one per bucket. (Bucket labels in the raw output are in Chinese: "几乎无风" = almost no wind, "小风" = light wind, "常态" = normal, "大风" = strong wind, "满发" = full output.)

| cf_bucket | hours | avg_lmp | gen_mwh | pct_of_annual_gen | negative_price_hours |
| :--- | :-- | :-- | :-- | :-- | :-- |
| 1. 0-10 pct almost no wind | 470 | 83.07 | 4,744 | 1.3 | 0 |
| 2. 10-25 pct light wind | 2,700 | 62.38 | 74,074 | 20.2 | 0 |
| 3. 25-40 pct normal | 3,419 | 30.86 | 159,180 | 43.3 | 2 |
| 4. 40-55 pct strong wind | 1,888 | 2.09 | 110,823 | 30.2 | 805 |
| 5. above 55 pct full output | 283 | -22.04 | 18,676 | 5.1 | 282 |

The monotonic relationship holds perfectly, and the magnitude is striking. From almost no wind to full output, the average price falls from $83.07/MWh all the way down to negative $22.04 — a swing of over $100.

The most important row is the last two buckets combined: strong wind and full output together contribute 35.3% of annual generation, but the average price during those hours is $2.09 in one bucket and negative $22.04 in the other. In other words, more than a third of the PPA's electricity is bought when market prices are near zero or negative, and Kestrel is paying $28.50/MWh for it.

In the full-output bucket, 282 of 283 hours had negative prices — nearly one-to-one. This isn't a matter of probability, it's physical inevitability.

Now look at the first bucket the other way: during the 470 hours when the price is $83.07/MWh, the PPA supplies only 1.3% of annual generation. Exactly when cheap electricity is needed most, this contract can't help.

Next action: this table goes directly into the renewal recommendation as Appendix A. It should also be shared with the site-selection team, because it illustrates a broader point: signing a fixed-price PPA at a wind-rich node needs a structure with shape adjustment built in, not a simple as generated arrangement.

---

## 14. Q12 Locating the Monthly Billing Demand Peak Interval

### Business Context

Q2 showed that the two PJM sites have over 40% of their electricity bill tied to billing demand charges. Director of Data Center Operations Tom Brennan got a request from Dana to figure out exactly what's driving that billing demand figure.

Tom's instinct is that it simply reflects the site's normal operating level and can't be pushed down: there are only so many machines, and power draw is whatever it is at full load. If that's true, the only lever is turning away business, which obviously isn't worth it.

But if billing demand is actually being set by a handful of isolated moments that are far from normal operating levels, that's an entirely different story.

### Tags

Window function RANK / Intermediate / Director of Data Center Operations

### Approach

Billing demand is drawn from the single highest 15-minute interval of the month, so you need to find the monthly Top N. This is a textbook window function scenario: `RANK() OVER (PARTITION BY month ORDER BY power DESC)`.

Use `RANK` rather than `ROW_NUMBER`, because if there's a tie for the highest value, we want both to be marked rank 1 — that itself would be a signal worth flagging (suggesting the site may have hit some kind of ceiling).

Once ranked, the top 3 need to be pivoted into columns on the same row for easy comparison. Conditional aggregation with `MAX(CASE WHEN rk = 1 THEN ... END)` is the standard SQL technique for this kind of pivot. `MAX` here isn't computing a maximum — it's extracting the single non-null value out of a group.

The last column, `gap_1_to_2_mw`, is the crux of this question: how much higher is the top value than the second-highest. If this gap stays small consistently, the peak is a natural product of continuous operation; if a large gap suddenly appears in one month, that month's peak is an isolated event.

The date filter uses `< '2026-07-01'` rather than `<= '2026-06-30'`, because `interval_start` is a full datetime with hour and minute — using `<=` would drop every interval after midnight on June 30 itself.

### SQL

```sql
WITH cmh_intervals AS (
    SELECT
        m.interval_start,
        m.metered_demand_mw,
        STRFTIME('%Y-%m', m.interval_start) AS ym
    FROM interval_meter_reading m
    JOIN site s ON s.id = m.site_id
    WHERE s.site_code = 'CMH1'
        -- interval_start 带时分, 用 <= '2026-06-30' 会漏掉当天零点之后的全部区间
        AND m.interval_start < '2026-07-01'
),
ranked AS (
    SELECT
        ym,
        interval_start,
        metered_demand_mw,
        RANK() OVER (PARTITION BY ym ORDER BY metered_demand_mw DESC) AS rk
    FROM cmh_intervals
)
SELECT
    ym,
    -- 条件聚合做行转列, MAX 在这里只是 "取出组里唯一的非空值"
    MAX(CASE WHEN rk = 1 THEN interval_start END)              AS peak_interval,
    ROUND(MAX(CASE WHEN rk = 1 THEN metered_demand_mw END), 3) AS peak_1_mw,
    ROUND(MAX(CASE WHEN rk = 2 THEN metered_demand_mw END), 3) AS peak_2_mw,
    ROUND(MAX(CASE WHEN rk = 3 THEN metered_demand_mw END), 3) AS peak_3_mw,
    ROUND(MAX(CASE WHEN rk = 1 THEN metered_demand_mw END)
        - MAX(CASE WHEN rk = 2 THEN metered_demand_mw END), 3) AS gap_1_to_2_mw
FROM ranked
WHERE rk <= 3
GROUP BY ym
ORDER BY ym;
```

### Expected Result and Business Takeaway

Twelve rows, one per month.

| ym | peak_interval | peak_1_mw | peak_2_mw | peak_3_mw | gap_1_to_2_mw |
| :--- | :--- | :-- | :-- | :-- | :-- |
| 2025-07 | 2025-07-03 15:00 | 82.569 | 82.390 | 82.380 | 0.179 |
| 2025-08 | 2025-08-14 15:45 | 88.638 | 87.977 | 82.813 | 0.661 |
| 2025-09 | 2025-09-11 15:00 | 71.834 | 71.630 | 70.721 | 0.204 |
| 2025-11 | 2025-11-09 12:15 | 67.331 | 66.151 | 65.755 | 1.180 |
| 2026-02 | 2026-02-22 14:00 | 66.391 | 66.213 | 66.023 | 0.178 |
| 2026-05 | 2026-05-30 15:30 | 77.609 | 77.360 | 77.166 | 0.249 |

Tom's instinct is partly right and partly wrong. Most months, the top and second-highest values are only a few tenths of an MW apart — the peak really is a natural byproduct of normal operation and can't be pushed down.

But August is an exception, and a decisive one. August's peak of 88.638 MW occurred in the single interval 2025-08-14 15:45, 6 MW above the next-highest month (July at 82.569 MW). More tellingly, within August there's a 5.2 MW gap between the third-ranked value (82.813 MW) and the top two, while every other month's spread from first to third stays under 1.2 MW. That points to the first two August intervals (15:30 and 15:45, exactly 30 minutes apart) being an isolated event, not normal operation.

Cross-checking against the operations log, that 30-minute window was a full-load burn-in test on a newly arrived batch of GB200 racks.

A 30-minute test set the highest demand figure for the entire fiscal year. And AEP Ohio's tariff has an 85% demand ratchet clause, meaning this peak acts like a floor propping up the bill for the following 11 months.

Next action: figure out exactly what that test cost. See Q13.

---

## 15. Q13 What That Burn-In Test Actually Cost

### Business Context

Tom needs a concrete dollar figure to convince the infrastructure team to change its testing procedure. Saying "burn-in tests push up billing demand" isn't enough — engineering will just say the test is necessary.

To make that conversation productive, two questions need answers: how much did this one test cost in total, and is there an alternative approach that doesn't compromise the test's purpose. This query handles the first question.

The dollar amount needs to be broken into two pieces. One is the extra billing demand charge on the August bill itself. The other is more hidden — it comes from the ratchet clause: this peak becomes the floor for billing demand in the following months, so even a month with low usage still gets billed at that floor.

### Tags

Multi-level CTE + counterfactual / Advanced / Director of Data Center Operations

### Approach

This is a counterfactual analysis. The task is to compute "what would the bill have been if that test hadn't happened," and subtract that from the actual bill.

Step one: construct the counterfactual August peak. Exclude the two burn-in intervals and recompute August's maximum. Use `NOT IN` to exclude the two specific timestamps.

Step two: construct the counterfactual ratchet floor. Take the peaks across all twelve months, substitute the counterfactual value for August, take the maximum, and multiply by the ratchet percentage. A `CASE WHEN` inside the subquery does the substitution — cleaner than computing first and correcting afterward.

Step three: compute the two cost differences. August's own difference is (actual peak minus counterfactual peak) times the demand rate. The ratchet difference is the sum, across every ratchet-bound month, of (actual billing demand minus counterfactual billing demand), times the demand rate. The counterfactual billing demand itself also needs to take the greater of "that month's actual metered peak" and "the counterfactual ratchet floor," so there's another layer of `MAX` involved.

This query has quite a few CTE layers, but each one does exactly one thing — splitting it out this way is much more readable than nesting subqueries.

### SQL

```sql
WITH cmh_invoice AS (
    SELECT i.*,
        t.demand_charge_usd_per_kw_month AS demand_rate,
        t.demand_ratchet_pct             AS ratchet_pct
    FROM energy_invoice i
    JOIN site s            ON s.id = i.site_id
    JOIN tariff_schedule t ON t.id = s.tariff_schedule_id
    WHERE s.site_code = 'CMH1'
),
aug_without_burnin AS (
    -- 反事实: 剔除 burn-in 那两个区间之后, 八月的峰值会是多少
    SELECT MAX(m.metered_demand_mw) * 1000 AS peak_kw
    FROM interval_meter_reading m
    JOIN site s ON s.id = m.site_id
    WHERE s.site_code = 'CMH1'
        AND STRFTIME('%Y-%m', m.interval_start) = '2025-08'
        AND m.interval_start NOT IN ('2025-08-14 15:30:00.000000',
            '2025-08-14 15:45:00.000000')
),
counterfactual_floor AS (
    -- 没有 burn-in 的话, 全年最高需量是各月峰值的最大值 (八月换成反事实值)
    SELECT MAX(peak_kw) * (SELECT ratchet_pct FROM cmh_invoice LIMIT 1) / 100.0 AS floor_kw
    FROM (
        SELECT CASE WHEN STRFTIME('%Y-%m', billing_period_start) = '2025-08'
            THEN (SELECT peak_kw FROM aug_without_burnin)
            ELSE metered_peak_demand_kw END AS peak_kw
        FROM cmh_invoice
    )
)
SELECT
    ROUND((SELECT MAX(metered_peak_demand_kw) FROM cmh_invoice), 2)  AS actual_annual_peak_kw,
    ROUND((SELECT peak_kw FROM aug_without_burnin), 2)               AS aug_peak_without_burnin_kw,
    ROUND((SELECT MAX(billing_demand_kw) FROM cmh_invoice
        WHERE is_ratchet_binding = 1), 2)                       AS actual_ratchet_floor_kw,
    ROUND((SELECT floor_kw FROM counterfactual_floor), 2)            AS counterfactual_floor_kw,
    (SELECT COUNT(*) FROM cmh_invoice WHERE is_ratchet_binding = 1)  AS ratchet_bound_months,
    ROUND(((SELECT MAX(metered_peak_demand_kw) FROM cmh_invoice)
            - (SELECT peak_kw FROM aug_without_burnin)) * 18.20, 0)     AS august_extra_usd,
    ROUND((SELECT SUM(billing_demand_kw
                - MAX(metered_peak_demand_kw,
                    (SELECT floor_kw FROM counterfactual_floor)))
        FROM cmh_invoice WHERE is_ratchet_binding = 1) * 18.20, 0) AS ratchet_extra_usd;
```

### Expected Result and Business Takeaway

One row.

| Field | Value |
| :--- | :-- |
| actual_annual_peak_kw | 88,637.67 |
| aug_peak_without_burnin_kw | 82,813.00 |
| actual_ratchet_floor_kw | 75,342.02 |
| counterfactual_floor_kw | 70,391.05 |
| ratchet_bound_months | 8 |
| august_extra_usd | 106,009 |
| ratchet_extra_usd | 681,401 |

That 30-minute burn-in test directly cost an extra $106,000 on the August bill, and indirectly raised the ratchet floor for the following 8 months by roughly 4,951 kW, adding up to $681,000 in cumulative overpayment. Total: roughly **$787,000**.

Put another way: a 30-minute test, at an average cost of $26,000 per minute.

And it's essentially money spent for nothing. The purpose of a burn-in test is to verify that new racks are stable under full load — it doesn't need to happen at 3:45 in the afternoon, and it doesn't need to stack on top of the rest of the site's load.

Next action: three recommendations for the memo to the infrastructure team. First, move all burn-in and stress tests to the 2 a.m.–5 a.m. low-load window — this alone would eliminate most of the incremental peak. Second, enforce a temporary power cap on the rest of the data hall during testing, to keep total site power from exceeding the month's existing peak. Third, add a hard rule in the DCIM system requiring Tom's personal sign-off for any operation that would push the 15-minute average power above the month's existing peak. Implementation cost for all three combined is under $50,000.

---

## 16. Q14 4CP Forecast Retrospective

### Business Context

Grid Operations Specialist Luis Ferrer is responsible for 4CP avoidance at the two Texas sites. The mechanics: ERCOT picks the single highest-demand 15-minute interval statewide in each month from June through September, and Kestrel's average usage during those four moments determines its transmission bill for the entire following year.

The problem is nobody knows in advance which 15-minute interval will be the peak. Every afternoon, Luis watches ERCOT's load forecast and judges whether today is likely to produce the month's peak; if so, he notifies both sites four hours ahead of time and drops load to a minimum during a window centered on the predicted peak, an hour on either side.

The FY2027 operating plan needs to be finalized in August, so Luis first needs to review FY2026's track record: how accurate were the forecasts, and was the window wide enough.

### Tags

Date arithmetic + interval matching / Intermediate / Grid Operations Specialist

### Approach

All the data lives in a single table, `dr_event`, so no join is needed, but three fields need to be understood clearly. `predicted_peak_interval_start` is Luis's forecast ahead of time, `iso_actual_peak_interval_start` is the actual peak ERCOT later confirmed, and `kestrel_coincident_demand_mw` is Kestrel's usage at the moment of that actual peak. `event_start` through `event_end` is the actual curtailment window that was executed.

Two things need to be computed. First, how many minutes off the forecast was — use `JULIANDAY` to convert both timestamps to Julian day numbers (fractional days), subtract, and multiply by 1440 to get minutes. SQLite has no `DATEDIFF`, so this is the standard approach. The result should be cast with `CAST AS INTEGER`, otherwise you'll get a trailing string of floating-point digits.

Second, determine hit or miss: did the actual peak fall inside the curtailment window, which `BETWEEN` handles directly. The closed-interval semantics of `BETWEEN` are exactly right here, since a peak landing precisely on the window boundary still counts as a hit.

Only 4CP-type events populate these three fields — the other 53 records are all NULL, so filtering on `trigger_reason` is required.

### SQL

```sql
SELECT
    ev.event_code,
    DATE(ev.event_start)              AS event_date,
    ev.predicted_peak_interval_start  AS predicted_peak,
    ev.iso_actual_peak_interval_start AS iso_actual_peak,
    -- SQLite 没有 DATEDIFF, 用 JULIANDAY 相减乘 1440 得到分钟数
    CAST(ROUND((JULIANDAY(ev.iso_actual_peak_interval_start)
                - JULIANDAY(ev.predicted_peak_interval_start)) * 1440) AS INTEGER)
    AS forecast_miss_minutes,
    ev.event_start                    AS curtail_window_start,
    ev.event_end                      AS curtail_window_end,
    CASE WHEN ev.iso_actual_peak_interval_start BETWEEN ev.event_start AND ev.event_end
    THEN 'HIT' ELSE 'MISS' END   AS outcome,
    ROUND(ev.kestrel_coincident_demand_mw, 1) AS coincident_demand_mw
FROM dr_event ev
-- 只有 4CP 类事件才填这三个字段, 其余 53 条全是 NULL
WHERE ev.trigger_reason = 'FORECAST_4CP_PEAK'
ORDER BY ev.event_start;
```

### Expected Result and Business Takeaway

Five rows: four events from the 2025 4CP season plus the first event of the 2026 4CP season.

| event_code | predicted_peak | iso_actual_peak | miss_minutes | outcome | coincident_mw |
| :--- | :--- | :--- | :-- | :--- | :-- |
| ERCOT-4CP-AVOID-2025-06 | 2025-06-24 16:45 | 2025-06-24 17:00 | 15 | HIT | 23.6 |
| ERCOT-4CP-AVOID-2025-07 | 2025-07-14 15:30 | 2025-07-14 16:00 | 30 | HIT | 24.7 |
| ERCOT-4CP-AVOID-2025-08 | 2025-08-01 16:45 | 2025-08-01 18:00 | 75 | MISS | 163.9 |
| ERCOT-4CP-AVOID-2025-09 | 2025-09-04 17:45 | 2025-09-04 18:00 | 15 | HIT | 19.6 |
| ERCOT-4CP-AVOID-2026-06 | 2026-06-26 18:00 | 2026-06-26 18:15 | 15 | HIT | 22.2 |

Four out of five calls were hits. All four hits had a forecast miss of 30 minutes or less, and the actual peak landed squarely inside the curtailment window, holding coincident demand down to 19.6–24.7 MW.

August was off by 75 minutes. The curtailment window ran from 15:45 to 17:45, but the actual peak occurred at 18:00 — 15 minutes past the window's end. By that point both Texas sites had already resumed normal operation, and coincident demand hit 163.9 MW — seven times the level of the other four events.

Worth noting why it missed: it wasn't the wrong day — the day was correct — it was that the timing of the day's peak was underestimated. On August 1st, evening temperatures didn't drop off as quickly as expected, keeping cooling load elevated, and the peak came more than an hour later than the historical pattern would suggest.

One more detail: the four hits had misses of 15, 30, 15, and 15 minutes, against a window radius of 60 minutes on either side. In other words, all four had substantial margin — the window wasn't just barely holding. The one miss, at 75 minutes, was only 15 minutes beyond the window radius.

Next action: widen the curtailment window from 60 minutes on either side to 90 minutes. Based on FY2026's miss distribution, 90 minutes would have covered all five events. The cost is one extra hour of curtailment per event, which is trivial compared to the cost of a miss. See Q15 for the specific dollar figures.

---

## 17. Q15 The Financial Cost of Missing a 4CP Call

### Business Context

CFO Helen Okafor pushed back on the 4CP program during a budget meeting. Her exact words: it's just four hours a year, how much impact can it really have — is it worth having someone watch it every single day?

Luis needs a number that answers her question and does double duty: justifying the value of this role, and justifying the proposal to widen the window. The most persuasive approach is to quantify the actual cost of the FY2026 miss.

This number also flows directly into the FY2027 budget: transmission cost is billed based on the prior year's 4CP result, so the 2025 miss shows up on the bill paid in FY2027.

### Tags

CTE + counterfactual / Intermediate / CFO

### Approach

Another counterfactual question, but simpler than Q13. The logic: actual 4CP average demand is the average of the four events; if August had also been a hit, that event's coincident demand should have been in line with the other three, so substitute the average of the hit events in its place.

The first CTE isolates the four events of the 2025 4CP season. The date range needs to be `>= '2025-06-01' AND < '2025-10-01'`, because the June 2026 event belongs to the next 4CP season — including it would turn four months into five and throw off the average. This is the easiest place to get this wrong, and the mistake produces a result that still looks perfectly plausible, making it hard to catch.

It also computes an `is_hit` flag, reusing Q14's `BETWEEN` logic.

The second CTE computes the actual average, and the third computes the average restricted to hits only. The final step joins the two single-row results with a cross join (`FROM actual a, hit_only h`). Since each CTE produces exactly one row, a cross join is the most direct way to combine them — no join condition needed.

The transmission rate of $58 per kW per year is Oncor's industrial rate, hardcoded into the query. Watch the unit conversion: demand is in MW while the rate is per kW, so multiply by 1000.

### SQL

```sql
WITH season_2025 AS (
    -- 只圈 2025 年 4CP 季的四个月. 2026 年 6 月那次属于下一季,
    -- 混进来会把四个月算成五个月, 而且结果看起来还挺合理, 很难发现
    SELECT
        event_code,
        kestrel_coincident_demand_mw AS mw,
        CASE WHEN iso_actual_peak_interval_start BETWEEN event_start AND event_end
        THEN 1 ELSE 0 END AS is_hit
    FROM dr_event
    WHERE trigger_reason = 'FORECAST_4CP_PEAK'
        AND event_start >= '2025-06-01'
        AND event_start <  '2025-10-01'
),
actual AS (
    SELECT AVG(mw) AS avg_mw,
        COUNT(*) AS months,
        SUM(CASE WHEN is_hit = 1 THEN 1 ELSE 0 END) AS hits
    FROM season_2025
),
hit_only AS (
    SELECT AVG(mw) AS avg_hit_mw FROM season_2025 WHERE is_hit = 1
)
SELECT
    a.months                                          AS four_cp_months,
    a.hits                                            AS forecast_hits,
    a.months - a.hits                                 AS forecast_misses,
    ROUND(a.avg_mw, 2)                                AS actual_4cp_avg_mw,
    ROUND(h.avg_hit_mw, 2)                            AS counterfactual_avg_mw,
    -- 需量单位是 MW, 费率是每 kW 每年, 所以乘 1000
    ROUND(a.avg_mw * 1000 * 58.0, 0)                  AS actual_transmission_usd,
    ROUND(h.avg_hit_mw * 1000 * 58.0, 0)              AS counterfactual_transmission_usd,
    ROUND((a.avg_mw - h.avg_hit_mw) * 1000 * 58.0, 0) AS cost_of_the_miss_usd
FROM actual a, hit_only h;
```

### Expected Result and Business Takeaway

One row.

| Field | Value |
| :--- | :-- |
| four_cp_months | 4 |
| forecast_hits | 3 |
| forecast_misses | 1 |
| actual_4cp_avg_mw | 57.97 |
| counterfactual_avg_mw | 22.66 |
| actual_transmission_usd | 3,362,362 |
| counterfactual_transmission_usd | 1,314,319 |
| cost_of_the_miss_usd | 2,048,043 |

A single 75-minute forecast miss cost **$2,048,000**.

The mechanics: 4CP averages across four months, so any single month's miss gets diluted across all four — but the base numbers are large enough that it still hurts. 163.9 MW versus roughly 22 MW is a 140 MW gap, which spreads to 35 MW once averaged across four months, and 35 MW times $58/kW/year comes out to about $2 million.

This also answers Helen's question. This role only has four truly critical hours a year, but those four hours are worth over $3 million in transmission cost, and the swing between a hit and a miss runs into seven figures. The savings from the three hits (relative to a baseline of never avoiding 4CP at all, with demand running at 163.9 MW) far exceed the cost of running the whole program.

Next action: approve both of Luis's proposals. First, widen the curtailment window from 60 minutes to 90 minutes on either side — based on FY2026's miss distribution, this would have covered all five events. The incremental cost is one extra hour of compute opportunity cost per event; using the ABI1/TPL1 job mix, that's roughly $120,000 per event, or under $500,000 across four events — clearly worthwhile against a $2 million risk exposure. Second, on days in August and September when evening temperatures drop off slowly, add a second forecast check at 5 p.m. that can trigger a temporary window extension.

---

## 18. Q16 What We Were Doing When Prices Spiked

### Business Context

The Abilene site settles all of its energy charges at real-time price, with no retail fixed-price contract as a backstop. That means Kestrel is directly exposed to ERCOT's price spikes, which can run into the thousands of dollars per MWh.

The automated dispatch system has a rule: if real-time price exceeds $240/MWh, trigger economic curtailment and proactively stop some jobs. This rule was configured two years ago and has never been reviewed since.

Dana wants to know how well this rule is actually performing in practice: are we really curtailing during price spikes, by how much, and are we doing the opposite during negative-price periods — using more power than usual.

### Tags

Window function LAG + bucketing / Intermediate / Energy Data Analyst

### Approach

Prices and site load need to be aligned to the same moment, so `lmp_interval_price` and `interval_meter_reading` are joined on both `site_id` and `interval_start`. Both tables are at 15-minute grain with perfectly aligned timestamps, so they match one-to-one without any aggregation needed.

The `LAG` window function pulls the previous interval's price, used to compute the size of the price jump. This column exists to show how volatile ERCOT prices can be: a jump of several thousand dollars from one interval to the next means the automated rule's response speed is critical.

Bucketing uses `CASE WHEN`, with boundaries at 0 (the negative-price line), 50 (typical upper bound), 240 (the economic curtailment threshold), and 1000 (true spike territory). Every one of these boundaries has business meaning — they're not arbitrary cutoffs.

`curtailed_pct` is computed as `SUM(is_curtailed) * 100.0 / COUNT(*)` — note the `100.0` rather than `100`, otherwise SQLite performs integer division and every result comes out zero. This is a very common trap.

The last column computes actual energy spend per bucket, using load times 0.25 hours times price.

### SQL

```sql
WITH abi AS (
    SELECT
        l.interval_start,
        l.lmp_usd_per_mwh,
        m.metered_demand_mw,
        m.is_curtailed,
        LAG(l.lmp_usd_per_mwh) OVER (ORDER BY l.interval_start) AS prev_lmp
    FROM lmp_interval_price l
    JOIN pricing_node n ON n.id = l.pricing_node_id
    -- 两张表都是 15 分钟粒度且时间戳对齐, 可以直接一对一 join
    JOIN interval_meter_reading m
        ON m.site_id        = n.site_id
        AND m.interval_start = l.interval_start
    WHERE n.node_code = 'HB_WEST_ABI'
),
bucketed AS (
    SELECT
        CASE
        WHEN lmp_usd_per_mwh <    0 THEN '1. 负电价'
        WHEN lmp_usd_per_mwh <   50 THEN '2. 0 到 50'
        WHEN lmp_usd_per_mwh <  240 THEN '3. 50 到 240'
        WHEN lmp_usd_per_mwh < 1000 THEN '4. 240 到 1000'
        ELSE                             '5. 1000 以上'
        END AS price_bucket,
        lmp_usd_per_mwh,
        metered_demand_mw,
        is_curtailed,
        lmp_usd_per_mwh - prev_lmp AS lmp_jump
    FROM abi
    WHERE prev_lmp IS NOT NULL
)
SELECT
    price_bucket,
    COUNT(*)                       AS intervals,
    ROUND(AVG(lmp_usd_per_mwh), 2) AS avg_lmp,
    ROUND(AVG(metered_demand_mw), 2) AS avg_load_mw,
    -- 必须写 100.0 而不是 100, 否则 SQLite 走整数除法, 结果全是 0
    ROUND(SUM(is_curtailed) * 100.0 / COUNT(*), 1) AS curtailed_pct,
    ROUND(MAX(lmp_jump), 0)        AS max_jump_from_prev_interval,
    ROUND(SUM(metered_demand_mw * 0.25 * lmp_usd_per_mwh), 0) AS energy_cost_usd
FROM bucketed
GROUP BY price_bucket
ORDER BY price_bucket;
```

### Expected Result and Business Takeaway

Five rows. (Bucket labels: "负电价" = negative price, "0 到 50" = 0 to 50, "50 到 240" = 50 to 240, "240 到 1000" = 240 to 1000, "1000 以上" = above 1000.)

| price_bucket | intervals | avg_lmp | avg_load_mw | curtailed_pct | max_jump | energy_cost_usd |
| :--- | :-- | :-- | :-- | :-- | :-- | :-- |
| 1. negative price | 6,303 | -18.12 | 92.74 | 0.1 | 86 | -2,638,794 |
| 2. 0 to 50 | 17,771 | 26.08 | 94.11 | 0.5 | 108 | 10,933,145 |
| 3. 50 to 240 | 10,918 | 70.11 | 95.40 | 1.3 | 136 | 18,273,714 |
| 4. 240 to 1000 | 3 | 875.66 | 98.35 | 33.3 | 929 | 64,823 |
| 5. above 1000 | 44 | 2,849.10 | 96.80 | 47.7 | 4,563 | 2,992,590 |

Three findings.

First, performance during negative-price periods is strong. There are 6,303 intervals a year (18%) with negative prices, and during those windows the site averages 92.74 MW, close to full load, with a curtailment rate of just 0.1%. As a result, this bucket's energy cost is negative $2.64 million — Kestrel actually nets $2.64 million by using power during these periods. Nothing needs to change here.

Second, the response during spike periods is inadequate. The above-$1,000 bucket has 44 intervals with a curtailment rate of only 47.7% — more than half of those spike intervals still had the site running close to full load. Those 44 intervals total 11 hours and cost $2.99 million — nearly a tenth of ABI1's entire annual energy spend.

Third, the size of the price jumps explains why. In the highest bucket, the jump from the prior interval to the spike interval averaged $4,563/MWh. The automated rule only fires after the price has already crossed the threshold, and ERCOT spikes often complete within one or two intervals — by the time the system reacts, curtailment is already too late.

Next action: change the economic curtailment rule from "react after the fact" to "warn ahead of time." ERCOT's real-time pricing has leading indicators, such as operating reserve margin and the five-minute pre-clearing price. We recommend incorporating both signals for early detection, with a goal of raising the curtailment rate in the above-$1,000 bucket from 47.7% to above 80%. That said, review Q20 before moving forward, since the economics of economic curtailment itself are worth questioning.

---

## 19. Q17 Wet Bulb Temperature and Cooling Load

### Business Context

There's a pending item in the FY2027 capital budget: converting the Columbus site from air cooling to liquid cooling, budgeted at $42 million. The project's main selling point is reduced cooling energy use, but Helen has pushed back on the infrastructure team's savings estimate, arguing it's based on vendor-supplied parameters rather than Kestrel's own operating data.

Dana asked you to cross-check it with existing data. Conveniently, there are two sites with comparable operating conditions but different cooling methods: Columbus is air-cooled, Abilene is liquid-cooled. If liquid cooling's cooling-energy share is indeed noticeably lower, and if that advantage widens as temperature rises, then the vendor's estimate is directionally correct.

### Tags

Time-aligned join + bucketing / Intermediate / Energy Data Analyst

### Approach

The challenge is that the two tables are at different grains: `weather_observation` is hourly, `interval_meter_reading` is 15-minute. Meter data needs to be aggregated to hourly first, otherwise one weather record would match four meter records, quadruple-counting every hour. Averages would happen to come out correct anyway, but `COUNT(*)` would come out 4x too high, which is an immediate giveaway that something's wrong.

Once aggregated to hourly, join on an hour key generated with `STRFTIME('%Y-%m-%d %H', ...)`. Note the `hourly_load` CTE needs `WHERE m.metered_demand_mw > 0` to exclude zero-load readings from before ALB1 went live. This query only looks at CMH1 and ABI1, but this habit avoids trouble if the query gets extended later.

Cooling overhead percentage should use `AVG(cooling_mw) / AVG(it_mw)`, not `AVG(cooling_mw / it_mw)`. The former is "total cooling load divided by total IT load," the latter is "the average of hourly ratios." The two can diverge when IT load is volatile, and the former is the number engineering actually cares about.

Bucket by wet bulb temperature into five ranges, with boundaries at 40, 55, 65, and 75 degrees Fahrenheit. 55 degrees is roughly the inflection point where cooling systems start visibly struggling.

### SQL

```sql
WITH hourly_load AS (
    -- 必须先把 15 分钟计量聚合到小时, 否则一条气象记录会匹配四条计量记录,
    -- 平均值碰巧还对, 但 COUNT(*) 会变成四倍
    SELECT
        m.site_id,
        STRFTIME('%Y-%m-%d %H', m.interval_start) AS hour_key,
        AVG(m.it_load_mw)      AS it_mw,
        AVG(m.cooling_load_mw) AS cooling_mw
    FROM interval_meter_reading m
    WHERE m.metered_demand_mw > 0
    GROUP BY m.site_id, hour_key
)
SELECT
    s.site_code,
    s.cooling_type,
    CASE
    WHEN w.wet_bulb_temp_f < 40 THEN '1. 40F 以下'
    WHEN w.wet_bulb_temp_f < 55 THEN '2. 40 到 55F'
    WHEN w.wet_bulb_temp_f < 65 THEN '3. 55 到 65F'
    WHEN w.wet_bulb_temp_f < 75 THEN '4. 65 到 75F'
    ELSE                              '5. 75F 以上'
    END AS wet_bulb_bucket,
    COUNT(*)                     AS hours,
    ROUND(AVG(hl.cooling_mw), 3) AS avg_cooling_mw,
    -- 总冷却除以总 IT, 不是每小时比值再平均. 前者才是工程上的能耗开销比
    ROUND(AVG(hl.cooling_mw) * 100.0 / AVG(hl.it_mw), 1) AS cooling_overhead_pct
FROM weather_observation w
JOIN site s ON s.id = w.site_id
JOIN hourly_load hl
    ON hl.site_id  = w.site_id
    AND hl.hour_key = STRFTIME('%Y-%m-%d %H', w.observed_at)
WHERE s.site_code IN ('CMH1', 'ABI1')
GROUP BY s.site_code, wet_bulb_bucket
ORDER BY s.site_code, wet_bulb_bucket;
```

### Expected Result and Business Takeaway

Ten rows, five buckets each for the two sites.

| site_code | cooling_type | wet_bulb_bucket | hours | avg_cooling_mw | cooling_overhead_pct |
| :--- | :--- | :--- | :-- | :-- | :-- |
| ABI1 | LIQUID_COOLED | 1. below 40F | 2,635 | 5.361 | 6.2 |
| ABI1 | LIQUID_COOLED | 3. 55 to 65F | 1,172 | 6.768 | 7.8 |
| ABI1 | LIQUID_COOLED | 5. above 75F | 1,544 | 12.535 | 14.4 |
| CMH1 | AIR_COOLED | 1. below 40F | 4,163 | 5.090 | 11.5 |
| CMH1 | AIR_COOLED | 3. 55 to 65F | 1,486 | 6.671 | 15.0 |
| CMH1 | AIR_COOLED | 5. above 75F | 342 | 14.745 | 27.2 |

The vendor's direction is correct, and the advantage is even bigger than they claimed. At the low-temperature bucket, liquid cooling overhead is 6.2% versus air cooling's 11.5%, a 5.3-point gap; at the high-temperature bucket, it's 14.4% versus 27.2%, a 12.8-point gap. Liquid cooling's advantage isn't fixed — it widens as temperature rises, because air-cooled systems lose efficiency much faster at high wet bulb temperatures.

But there's a question Helen will immediately raise: Columbus only experiences 342 hours a year with wet bulb temperature above 75 degrees Fahrenheit — 3.9% of the year — while Abilene has 1,544 hours. The bucket where liquid cooling's advantage is largest only shows up for about two weeks a year in Columbus. Weighted by actual hours, Columbus's annual energy savings post-conversion would come out noticeably lower than an estimate extrapolated from Abilene's data.

Next action: hand this table back to the infrastructure team and require them to redo the payback calculation using Columbus's own wet bulb temperature distribution (not industry averages or Abilene data), with the measured overhead ratio for each cooling type at each temperature bucket as an input parameter. Until the revised estimate comes back, recommend holding the $42 million capital project out of the FY2027 budget.

---

## 20. Q18 Evaluation Methodology Across Three Supply Contract Types

### Business Context

After the Q10 PPA review conclusion came out, Marcus realized there's a more fundamental problem: the company now has eleven supply contracts across four types, and he's been evaluating all of them with the same methodology. The wind PPA lesson shows that methodology is wrong for at least one contract type — what about the others?

Before drafting the FY2027 procurement strategy, he needs to nail down the evaluation framework first: what methodology should each contract type be evaluated with, which numbers can be compared directly, and which can't.

### Tags

Aggregation + classification / Basic / Power Procurement Manager

### Approach

Aggregate from `supply_contract` by contract type. Two supporting pieces of information are needed: the average market price at each site's node (computed from `lmp_interval_price`), and actual delivered generation for the variable-output contracts (computed from `ppa_generation_hourly`).

Both supporting pieces are precomputed as CTEs and then joined in, which is far faster than writing them as correlated subqueries — the price table has 210,000 rows, and a correlated subquery would rescan it for every single contract.

Watch the PPA generation CTE closely: only three of the eleven contracts have generation records, the other eight don't, so it must be a `LEFT JOIN` with `COALESCE`, otherwise those eight contracts would disappear entirely.

The last column isn't a computed value — it's a plain-language evaluation note. Writing it directly into the SQL, rather than leaving it as a manual annotation, means this table can be dropped straight into the procurement strategy document with every row self-explanatory.

### SQL

```sql
WITH node_price AS (
    SELECT n.site_id, AVG(l.lmp_usd_per_mwh) AS avg_market_lmp
    FROM lmp_interval_price l
    JOIN pricing_node n ON n.id = l.pricing_node_id
    GROUP BY n.site_id
),
ppa_realised AS (
    SELECT c.site_id,
        c.contract_type,
        SUM(g.generation_mwh) AS mwh
    FROM ppa_generation_hourly g
    JOIN supply_contract c ON c.id = g.supply_contract_id
    GROUP BY c.id
)
SELECT
    c.contract_type,
    COUNT(DISTINCT c.id)                      AS contracts,
    ROUND(AVG(c.strike_price_usd_per_mwh), 2) AS avg_strike,
    ROUND(AVG(np.avg_market_lmp), 2)          AS avg_node_market_price,
    ROUND(SUM(COALESCE(pr.mwh, 0)), 0)        AS ppa_delivered_mwh,
    CASE WHEN c.contract_type IN ('WIND_PPA', 'SOLAR_PPA')
    THEN '有逐小时出力, 需要按出力加权评估'
    WHEN c.contract_type = 'RETAIL_FIXED'
    THEN '固定到户价, 含输配, 不可与批发价直接比'
    ELSE '随行就市, 无锁价' END           AS evaluation_note
FROM supply_contract c
JOIN node_price np ON np.site_id = c.site_id
-- 只有三份合约有发电记录, 必须 LEFT JOIN 否则另外八份会整行消失
LEFT JOIN ppa_realised pr ON pr.site_id = c.site_id AND pr.contract_type = c.contract_type
GROUP BY c.contract_type
ORDER BY avg_strike DESC;
```

### Expected Result and Business Takeaway

Four rows, one per contract type.

| contract_type | contracts | avg_strike | avg_node_market_price | ppa_delivered_mwh | evaluation_note |
| :--- | :-- | :-- | :-- | :-- | :--- |
| RETAIL_FIXED | 4 | 54.63 | 40.34 | 0 | Fixed delivered price, includes T&D — not directly comparable to wholesale |
| SOLAR_PPA | 2 | 35.33 | 42.23 | 213,427 | Has hourly generation — needs generation-weighted evaluation |
| WIND_PPA | 1 | 28.50 | 35.47 | 367,498 | Has hourly generation — needs generation-weighted evaluation |
| WHOLESALE_INDEX | 4 | 0.00 | 36.24 | 0 | Floats with market — no fixed strike price |

The most important thing this table does is warn against a natural but wrong instinct: putting `avg_strike` and `avg_node_market_price` side by side is tempting, but comparing within a single contract type is meaningful, comparing across types is not.

The `RETAIL_FIXED` row looks like the worst deal at first glance — a strike price of 54.63, far above the market average of 40.34, as if it were signed $14/MWh too high. But retail fixed price is a delivered price that already bundles in transmission and distribution charges, while the market average is a pure wholesale figure that excludes T&D. Comparing a T&D-inclusive price against a T&D-exclusive price is guaranteed to be wrong. A fair comparison requires adding the equivalent T&D cost onto the market average — for the two Ohio sites, that works out to roughly $20/MWh — after which the retail fixed contracts actually look like a good deal.

The `WHOLESALE_INDEX` row has a strike price of zero because there simply is no strike price — it floats entirely with the market. This row shouldn't be part of any price comparison at all.

The only truly apples-to-apples comparison is between the two PPAs, and even then it has to use Q10's generation-weighted methodology, not the simple averages shown in this table.

Next action: write this evaluation framework into section one of the procurement strategy document as the baseline methodology for every future contract review. Specifically: variable-generation PPAs are always evaluated on a generation-weighted market price basis; retail fixed contracts get T&D cost added to the market benchmark before comparison; wholesale index exposure isn't evaluated on price at all, only on its share of total risk exposure.

---

## 21. Q19 Customers With the Largest SLA Credit Exposure

### Business Context

COO Rafael Duarte received a complaint letter forwarded by the sales team. Cascade Vision Systems, the company's third-largest customer, is on a RESERVED long-term contract with an explicit availability commitment in the agreement. Their letter lists multiple job interruptions during FY2026, demands an explanation, and hints that pricing will be renegotiated at renewal.

Rafael needs two things: what actually happened with this customer's interruptions, and how large similar exposure is across other customers. Because if this is a widespread issue, it isn't just one complaint letter — it's a systemic risk heading into renewal season.

Some context: participating in demand response means proactively interrupting customer jobs, and RESERVED-tier customers are contractually owed an SLA credit when interrupted. That cost has always been booked under cost of service, and never viewed side by side with DR revenue.

### Tags

Aggregation + HAVING / Basic / COO

### Approach

Start from `curtailed_workload`, join `compute_job` to get customer name and contract tier, and join `curtailment_action` to get timing for the fiscal-year filter.

Group by customer plus contract tier. Why include `contract_tier`: the same customer might have both RESERVED and ON_DEMAND jobs at once, with very different credit rates — mixing them together would hide which contract type the problem is actually in.

`HAVING SUM(w.sla_credit_usd) > 0` filters out SPOT-tier customers. SPOT contracts explicitly state jobs can be preempted with no credit owed, so leaving them in would just add noise. Note this condition has to go in `HAVING`, not `WHERE`, since it operates on the aggregated result.

`COUNT(DISTINCT w.id)` and `COUNT(DISTINCT j.id)` give interruption count and affected job count separately, since one job can be interrupted multiple times.

The `avg_rollback_min` column is explanatory: it shows why some customers' losses are especially large.

### SQL

```sql
SELECT
    j.customer_name,
    j.contract_tier,
    COUNT(DISTINCT w.id)                         AS interruptions,
    COUNT(DISTINCT j.id)                         AS jobs_affected,
    ROUND(SUM(w.lost_gpu_hours), 0)              AS lost_gpu_hours,
    ROUND(SUM(w.opportunity_cost_usd), 0)        AS opportunity_cost_usd,
    ROUND(SUM(w.sla_credit_usd), 0)              AS sla_credit_usd,
    ROUND(AVG(w.checkpoint_rollback_minutes), 0) AS avg_rollback_min
FROM curtailed_workload w
JOIN compute_job j        ON j.id = w.compute_job_id
JOIN curtailment_action c ON c.id = w.curtailment_action_id
WHERE c.action_start >= '2025-07-01'
    AND c.action_start <  '2026-07-01'
GROUP BY j.customer_name, j.contract_tier
-- 条件作用在聚合结果上, 必须写 HAVING. SPOT 档位不产生赔付, 顺便过滤掉
HAVING SUM(w.sla_credit_usd) > 0
ORDER BY sla_credit_usd DESC
LIMIT 12;
```

### Expected Result and Business Takeaway

Twelve rows.

| customer_name | tier | interruptions | jobs_affected | lost_gpu_hours | opportunity_cost_usd | sla_credit_usd | avg_rollback_min |
| :--- | :--- | :-- | :-- | :-- | :-- | :-- | :-- |
| Cascade Vision Systems | RESERVED | 18 | 11 | 105,094 | 323,394 | 99,839 | 100 |
| Lumen Protein Systems | RESERVED | 30 | 14 | 93,537 | 288,083 | 88,860 | 91 |
| Ardent Robotics | RESERVED | 22 | 10 | 79,532 | 242,294 | 75,555 | 83 |
| Cobalt Therapeutics | RESERVED | 30 | 11 | 69,555 | 209,993 | 66,077 | 71 |
| Helix Frontier Labs | RESERVED | 24 | 10 | 65,791 | 199,729 | 62,501 | 65 |
| Ember Molecular | ON_DEMAND | 10 | 5 | 63,103 | 198,704 | 22,086 | 150 |

Cascade Vision's complaint is well-founded. They were interrupted 18 times in FY2026, affecting 11 jobs, losing 105,000 GPU-hours, for which Kestrel paid out $99,839 in SLA credit.

But what should really catch Rafael's attention is the answer to his second question: this isn't an isolated incident. All of the top eleven are RESERVED customers, with combined SLA credit around $625,000. And RESERVED is precisely the tier with the longest contract terms, the lowest unit price, and the customers most worth retaining. We're trading these highest-value customers' service experience for demand response revenue.

The `avg_rollback_min` column explains where the losses come from: the top customers average 65 to 100 minutes of rollback, meaning they mostly run training jobs with long checkpoint intervals — every interruption costs more than an hour of wasted compute on top of the interruption itself.

Comparing this figure against Q5 needs care with methodology: of the $625,000 in SLA credit here, only the portion tied to `curtailment_type = 'DR_EVENT'` is already counted in Q5's cost side — SLA credit from economic (ECONOMIC) and 4CP curtailment isn't included in Q5 at all. In other words, Q5's DR net benefit already looks bad, and it doesn't even fully capture all of these customers' credits. And what Q5 captures even less of is renewal risk, which could end up costing far more than the credits themselves.

Next action: two things. First, the response to Cascade Vision shouldn't just address the credit — it should proactively state that we've already decided to adjust DR strategy and commit to removing their jobs from the curtailment pool starting FY2027, which is worth more to them than a refund. Second, add a hard constraint in the dispatch system: RESERVED-tier jobs never enter the DR curtailment candidate pool — only ON_DEMAND and SPOT can be curtailed. This constraint will reduce curtailable capacity and needs to be sized alongside Q5's filing adjustment plan.

---

## 22. Q20 Who Makes the Curtailment Call, and Is It the Right Call

### Business Context

This is the closing section of the memo. Dana needs to answer a more fundamental question in the last part: is curtailment, as a practice, actually being done well.

Four types of actors issue curtailment instructions at Kestrel: the automated dispatch system firing on preset rules, the Demand Response Manager making manual calls after receiving an ISO notice, the Grid Operations Specialist handling 4CP avoidance, and the VP herself stepping in directly in special circumstances. All four use different judgment criteria, respond at different speeds, and naturally produce different outcomes.

Dana wants to see this broken out by decision source: what's the attainment rate for each, and — most critically — what's the relationship between "energy cost saved" and "compute lost" for each category of curtailment.

### Tags

Text matching + aggregation / Intermediate / VP of Energy Strategy

### Approach

Aggregate from `curtailment_action` as the primary table, grouped along two dimensions: `decision_made_by` and `curtailment_type`.

Compute cost needs to be rolled up from `curtailed_workload`. This has to be pre-aggregated to one row per `curtailment_action_id` in a subquery before joining back to the main table. Joining the detail table directly and then aggregating would double-count fields on `curtailment_action` (like `energy_cost_avoided_usd`) — if one curtailment action interrupted eight jobs, the energy savings would get counted eight times. This is a classic fan-out error in aggregate queries.

Attainment rate is `achieved_reduction_mw / target_reduction_mw`, with the denominator wrapped in `NULLIF` to guard against division by zero.

The `decision_made_by` filter uses `LIKE` for pattern matching. This field could technically be filtered with `IN` against four exact values, but `LIKE` is used because this field stores job titles, and future variants like "Senior Demand Response Manager" could show up — pattern matching is more robust against that.

The last column, `energy_side_net_usd`, is the crux of this question: energy savings minus compute loss, purely evaluating whether each curtailment action was worth it on its own energy-side terms.

### SQL

```sql
SELECT
    c.decision_made_by,
    c.curtailment_type,
    COUNT(*) AS actions,
    ROUND(AVG(c.achieved_reduction_mw / NULLIF(c.target_reduction_mw, 0)), 3) AS avg_attainment,
    ROUND(AVG(c.duration_minutes), 0)                   AS avg_duration_min,
    ROUND(AVG(c.market_price_at_action_usd_per_mwh), 2) AS avg_price_at_action,
    ROUND(SUM(c.energy_cost_avoided_usd), 0)            AS energy_avoided_usd,
    ROUND(COALESCE(SUM(wl.cost), 0), 0)                 AS compute_cost_usd,
    ROUND(SUM(c.energy_cost_avoided_usd) - COALESCE(SUM(wl.cost), 0), 0) AS energy_side_net_usd
FROM curtailment_action c
-- 必须先聚合成一行再 join. 直接 join 明细表会让 energy_cost_avoided_usd
-- 按被打断的任务数重复计算, 一次削减打断八个任务就会被算八遍
LEFT JOIN (
    SELECT curtailment_action_id,
        SUM(opportunity_cost_usd + sla_credit_usd) AS cost
    FROM curtailed_workload
    GROUP BY curtailment_action_id
) wl ON wl.curtailment_action_id = c.id
WHERE c.decision_made_by LIKE '%Manager%'
    OR c.decision_made_by LIKE '%Scheduler%'
    OR c.decision_made_by LIKE '%Specialist%'
    OR c.decision_made_by LIKE '%VP%'
GROUP BY c.decision_made_by, c.curtailment_type
ORDER BY actions DESC;
```

### Expected Result and Business Takeaway

Six rows.

| decision_made_by | type | actions | avg_attainment | avg_price | energy_avoided_usd | compute_cost_usd | energy_side_net_usd |
| :--- | :--- | :-- | :-- | :-- | :-- | :-- | :-- |
| Automated Scheduler | DR_EVENT | 52 | 0.964 | 94.71 | 88,912 | 1,847,692 | -1,758,780 |
| Automated Scheduler | ECONOMIC | 33 | 1.000 | 1,334.64 | 301,559 | 1,318,646 | -1,017,087 |
| Demand Response Manager | DR_EVENT | 31 | 0.947 | 83.25 | 41,434 | 874,304 | -832,870 |
| Grid Operations Specialist | 4CP_AVOIDANCE | 8 | 0.995 | 55.83 | 44,630 | 2,495,115 | -2,450,485 |
| Grid Operations Specialist | DR_EVENT | 9 | 0.941 | 75.04 | 18,413 | 363,371 | -344,958 |
| VP of Energy Strategy | DR_EVENT | 4 | 1.014 | 56.85 | 6,658 | 305,224 | -298,566 |

There's not much to say about the attainment column — all four decision sources land between 0.94 and 1.01, so execution isn't the issue.

The last column is where the problem is, and it reveals something nobody had systematically looked at before: **every single type of curtailment is a loss on a pure energy-side basis**. That's not surprising — curtailment saves energy cost while losing compute, and compute's per-unit value is already far higher than electricity's. Whether curtailment is worth doing was never about the energy savings alone — it depends on whatever revenue or avoided cost sits outside the energy line.

Looking at each category against that standard:

DR-event-triggered curtailment runs a net energy-side loss of $3.24 million, but it earns $3.28 million in DR settlement revenue in return, so overall it roughly breaks even (this is Q5's conclusion). 4CP avoidance runs a net energy-side loss of $2.45 million, but it avoids $2.05 million in incremental transmission cost, and the three hits, measured against a baseline of no avoidance at all, save far more than that — so it's worthwhile (Q15).

What genuinely doesn't hold up is the `Automated Scheduler` row under `ECONOMIC`. Economic curtailment generates no settlement revenue and avoids no transmission cost — its only benefit is the $302,000 in energy savings. And its compute cost is $1.32 million. **Net loss of $1.02 million, with nothing on the other side to offset it.**

This rule, configured two years ago with the logic "shut down when price exceeds $240/MWh," may well have made sense at the time. But that was when the company was still primarily an HPC hosting business, when compute's per-unit value was much lower. After the pivot to AI training, GPU-hour opportunity cost has risen several times over, and this rule's threshold has never been touched.

Working backward to find the break-even point: for economic curtailment to be worthwhile, the price has to be high enough that the energy savings cover the compute loss. Given the current ABI1/TPL1 job mix, curtailing 1 MW for an hour costs roughly $1,340 in compute, while the energy saved is price times 1 MWh. That means the trigger threshold should be above $1,300/MWh, not $240.

Next action: immediately raise the economic curtailment trigger threshold from $240 to $1,400/MWh — a one-line configuration change expected to recover roughly $900,000 in FY2027. At the same time, change the threshold to be derived dynamically from `internal_cost_usd_per_gpu_hour` rather than hardcoded as a constant, so the threshold automatically tracks whenever the business side adjusts GPU pricing. This recommendation should be called out separately in the memo's executive summary, since it's the single highest ROI item across all twenty analyses.

---

## 23. Business Questions to Query Mapping

| Business Question | Corresponding Queries |
| :--- | :--- |
| Q1 Is demand response actually profitable | Q3, Q4, Q5, Q6, Q19, Q20 |
| Q2 Is the curtailment volume reported to the ISO credible | Q7, Q8 |
| Q3 Is the wind PPA an asset or a liability | Q9, Q10, Q11, Q18 |
| Q4 Which part of the electricity bill can actually be reduced | Q1, Q2, Q12, Q13, Q17 |
| Q5 How costly is a 4CP avoidance miss | Q14, Q15, Q16 |

Once all twenty queries have been run, the memo's five conclusions all have supporting evidence. Ranked by dollar impact, the priority order is: widen the 4CP window (risk exposure of $2.05 million), adjust the economic curtailment threshold (recoverable $1.02 million), reschedule burn-in testing (savings of $787,000), shift DR committed capacity from training sites to inference sites (improvement of $700,000), and renegotiate the wind PPA (annualized $1.09 million, though it requires negotiation). Added together, the improvable opportunity for FY2027 exceeds $5 million, while implementation cost across all five items is under $600,000.
