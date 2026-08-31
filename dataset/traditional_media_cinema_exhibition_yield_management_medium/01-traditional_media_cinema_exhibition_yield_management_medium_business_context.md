# Traditional Media — Cinema Exhibition Showtime & Concession Profitability Business Context

> This document is the business context for the `traditional_media_cinema_exhibition_yield_management_medium` dataset, and it answers the question "what kind of company is this, what business is it in, and what problem are we trying to solve?" For the data structure, see `02-traditional_media_cinema_exhibition_yield_management_medium_er_document.md`; for the SQL queries, see `03-traditional_media_cinema_exhibition_yield_management_medium_sql_queries.md`.
>
> Intended reader: you're a sharp new hire who just joined the project — you don't need to be a cinema industry veteran. By the end of this document, you should be able to walk into your first stand-up and talk knowledgeably about the company's business, the industry, and the questions this analysis is meant to answer.

---

## 1. Company Profile

**Lakeshore Cinemas** is a regional cinema exhibition chain headquartered in Chicago, Illinois. The company was formed in 2006 through a merger of several independent single-screen theaters and has since expanded steadily across the Midwest. It now operates **18 theaters and 92 screens** across five states — Illinois, Wisconsin, Indiana, Ohio, and Michigan — covering both a primary market like the Chicago metro area and secondary markets such as Peoria, Fort Wayne, and Green Bay.

Company profile (order of magnitude, not exact figures):

- **Size:** roughly 450 employees, mostly hourly workers in projection, concession counters, and ticketing, plus around 60 full-time management staff.
- **Revenue:** annual revenue on the order of $95 million, the vast majority of it from box office; concession revenue is much smaller in absolute dollars. But concession barely gets split with distributors and carries a **gross margin** above 60%, so its contribution to **profit** far outweighs its share of revenue — which is exactly why "is the concession gross margin on the books actually real?" (Q1) is the question management cares about most.
- **Loyalty program:** the **Lakeshore Rewards** loyalty program is free to join for all moviegoers, who earn points on ticket and concession purchases that can be redeemed for popcorn, drinks, and other concession items. This dataset covers roughly 7,500 members active during Q2 2026.
- **Market tiering:** internally, the 18 theaters are split into **Primary (12 theaters)** and **Secondary (6 theaters)** market tiers, which drive programming strategy, concession stocking, and capex decisions.

Roles relevant to this analysis (the SQL queries reference these people by title):

| Title | What they care about |
|------|----------|
| CFO | The true cash margin on concessions; quarterly board materials |
| VP of Concessions & Merchandising | Concession pricing, stocking, redemption cost |
| VP of Film Programming | Film booking agreements with distributors, showtime scheduling |
| Director of Loyalty & Marketing | Redemption behavior and acquisition performance for Lakeshore Rewards |
| Regional Operations Manager | Day-to-day operations of theaters in Primary/Secondary markets |
| Facilities & Engineering Manager | Energy and maintenance spend on screen equipment |
| Concession Operations Supervisor | Concession stocking and staff scheduling by daypart |

---

## 2. Business Model

Lakeshore Cinemas earns revenue from two lines, and the profit logic behind each is completely different:

1. **Box office revenue:** moviegoers buy a ticket to see a film. Ticket price varies by screen type (Standard, Premium recliner auditoriums, IMAX), by daypart (matinee, prime, or late_night), and by weekend pricing. Box office is a "high revenue, low margin" business — a substantial share of that revenue has to be paid out to distributors as film rental, and this dataset doesn't model that revenue-share detail; it only tracks the box office and showtime operations the theater itself retains.
2. **Concession revenue:** popcorn, drinks, candy, and similar retail items. Concession revenue is much smaller in absolute dollars than box office, but its gross margin usually runs **above 60%**, and it's almost entirely exempt from distributor revenue-share — so every dollar of concession revenue converts to profit at a much higher rate than a dollar of box office revenue. That's why concession sits at the center of the exhibition chain's **profit structure**, even though it's not the biggest line on the revenue statement. There's an old industry saying: "we sell popcorn, and the movie is the excuse to sell popcorn" — an obvious exaggeration, but one that captures a real truth about cinema chain finances: **profit** tends to hide in high-margin concession, not in box office revenue that has to be split with distributors. That's exactly why whether the concession gross margin on the books is real (Q1) is the number-one question in this analysis.

The Lakeshore Rewards loyalty program is the thread connecting these two lines: free enrollment, points earned on spend, points redeemable for concession items. Management's working assumption is that "the loyalty program drives repeat visits, and the incremental box office and concession spend it generates is worth the cost of giving away free redemptions." Whether that assumption **actually holds** is one of the things this analysis needs to test — because redemptions happen inside the high-margin concession line, and if redemption volume is understated or mis-accounted for, an apparently "healthy" concession margin on paper could be an illusion.

Unit economics, order of magnitude: a standard ticket runs about $12.5; a medium popcorn runs about $7-8 and costs roughly $2.5-3 to produce. Screens themselves are also a source of capex and ongoing operating cost — IMAX screens especially, where equipment licensing fees and lamp/laser and lens maintenance run far above a standard screen. That fixed cost is often left out of the intuitive "ticket premium looks like a good deal" judgment.

---

## 3. Industry Primer: North American Cinema Exhibition

If you're coming from a different industry, this section gets you up to speed on what running a movie theater business is actually like.

**What value this industry creates.** The exhibitor sits at the end of the film industry value chain closest to the audience: a studio/production company makes the film, a distributor sells the print and screening rights to exhibitors, and the exhibitor provides the venue, equipment, projection, and in-theater experience, earning a contractually agreed share of box office (typically only 40%-50% in the opening week, rising in later weeks). That means **the part of the business where the exhibitor truly sets its own price and keeps the full margin is concession**, not the movie ticket itself, which has to be split with the distributor.

**Main categories of players (no real companies named).**

- **National mega-chains:** thousands of screens, strong negotiating leverage, and access to better revenue-share terms and first-run booking.
- **Regional chains (like Lakeshore Cinemas):** tens to a few hundred screens, deeply rooted in a specific regional market, sustaining repeat visits through localized operations and loyalty programs.
- **Independent art-house theaters:** small-scale, focused on art films and repertory screenings, with a business model quite different from mainstream commercial exhibition.
- **Premium-experience theaters:** built around recliner seating, in-theater dining, IMAX/4DX, and other differentiated experiences that command a higher ticket premium.

**Regulatory and compliance context.** The exhibition industry isn't heavily regulated overall, but a few rules still apply: fire and building safety codes (which vary by city/county), ADA (Americans with Disabilities Act) requirements for accessible seating, labor law governing hourly staff scheduling and minimum wage, and **film booking agreements** with distributors — these last ones aren't government regulation but industry commercial practice, though they carry real constraints on how a theater schedules its showtimes (see Section 7).

**Current macro forces.** Streaming has pulled away a share of moviegoing demand, especially for mid-budget adult dramas; exhibitors increasingly lean on "event" tentpole films and premium-experience auditoriums (IMAX, Premium) to drive box office; and concession and loyalty programs have become the key narrative for exhibitors proving they're "not just selling movie tickets." These pressures are why "are our premium screens actually profitable" and "is our concession margin actually healthy" are questions the board asks every single quarter.

---

## 4. Project Framing: What You're Doing

You're the newly hired **BI Analyst** at Lakeshore Cinemas, reporting directly to the **CFO**, and preparing the **Q2 2026 quarterly operating review** materials for the VP of Concessions & Merchandising, the VP of Film Programming, and the board.

At the last executive meeting, the CFO raised three questions that have been keeping her up at night: has the concession gross margin, which has looked great on paper for years, been hiding the true cost of loyalty redemptions? Are the IMAX screens the company has spent heavily upgrading actually profitable, screen by screen? The VP of Film Programming mentioned that "late-night occupancy has been holding up well" — is that number padded with something that shouldn't be there? Your job is to use the complete Q2 2026 (April 1 through June 30, 91 days) showtime, concession, and loyalty data to work through each of these questions with SQL and produce conclusions that can go straight into the board deck.

Deliverables: a Q2 operating review deck, a proposal to revise concession pricing and redemption policy, a recommended screen capex list, and a showtime adjustment list for the programming and operations teams. All analysis is anchored to a fixed reference date, **REFERENCE_DATE = 2026-06-30** (see Section 6).

---

## 5. Business Questions This Project Answers

The entire dataset is designed to answer the five core business questions below. The first three (Q1-Q3) each correspond to a **deliberately embedded data trap** in the ER document; the last two (Q4-Q5) are **operational analysis findings** built on the same data, without an additional embedded trap. All five questions have corresponding queries in the SQL query document.

1. **Q1 True Concession Cash Margin (Concession Cash Margin vs Recognized Margin):** are free redemptions from Lakeshore Rewards being booked as "normal sales revenue" in the reported concession margin? If you strip out the "phantom revenue" from redemptions and look only at cash actually received, how much does the margin drop?
2. **Q2 Premium Screen Profitability (Premium Screen Contribution):** does the ticket price premium on IMAX and Premium screens actually cover their higher energy and maintenance costs? Which specific screens are losing money on an ongoing basis, simply masked by the profits of other screens?
3. **Q3 Late-Night "Buyback Ticket" Distortion of Occupancy (Late-Night Buyback Inflation):** some distribution agreements for popular tentpole films require a minimum attendance count per showing — how much of late-night occupancy is actually theater-purchased comp/buyback tickets rather than real moviegoers?
4. **Q4 Screen & Theater Utilization (Screen Utilization & Rationalization):** which screens and theaters have persistently low showtime utilization, and should programming, screen type conversion, or even closure be considered?
5. **Q5 Daypart Concession Alignment:** what patterns exist between occupancy and concession spend per head / sales mix across different dayparts (matinee/prime/late_night), and what does that mean for concession stocking and hourly staff scheduling?

Beyond these five marquee questions, the dataset also supports a range of operational analyses: monthly box office and concession trends, theater-level comparisons, member-tier spending behavior, top concession SKU rankings, and similar questions used for day-to-day operations and financial planning.

---

## 6. Data Scope Overview

- **Time span:** the complete set of showtime, concession, and loyalty activity for Q2 2026 (2026-04-01 through 2026-06-30, 91 days), all anchored to a fixed reference date, **REFERENCE_DATE = 2026-06-30**. Every "today / current snapshot" concept is computed relative to this date rather than the system's actual current time, so that repeated runs and repeated queries produce consistent, reproducible results.
- **Data volume (order of magnitude, plain terms):** 18 theaters, 92 screens, 70 films, roughly 490 film booking agreements, roughly 38,000 showtimes, roughly 21,000 concession sale line items, 7,500 active members, roughly 28,000 loyalty redemption records — about 97,000 rows in total.
- **Deliberate scope decisions:**
  - **Single-quarter snapshot:** the dataset covers only Q2 2026, avoiding cross-year noise from film slate changes and pricing adjustments, so the analysis can focus on the internal relationships among showtimes, concession, and loyalty.
  - **No film rental revenue-share detail:** the box office split and settlement cycle between exhibitor and distributor is a separate business process (belonging to the distributor's side) and is out of scope for this dataset, which focuses only on the box office and operating costs the exhibitor itself retains.
  - **Loyalty program modeled as "active members" only:** Lakeshore Rewards has far more than 7,500 registered users, but this dataset only models members with actual spend or redemption activity during the quarter, to avoid diluting the analysis with a large number of dormant accounts that never use their points.

(This section doesn't list individual tables; see the ER document for the schema.)

---

## 7. Industry Knowledge Primer

Roughly thirty minutes of background a newcomer needs before this data will make sense. It's easiest to follow the life of a movie, from booking to the credits rolling.

**1) What a film booking agreement is.** An exhibitor can't just show whatever it wants. Before a film opens, the exhibitor signs a **film booking agreement** with the distributor, specifying how long a given screen will run the film and any additional terms. For **tentpole films**, distributors often attach a **minimum attendance clause**: a requirement that attendance at each showing not fall below some threshold (say, 20 people), or the exhibitor risks consequences like a reduced future booking allocation. This clause exists to guarantee the distributor's box office exposure, but it also creates a gray area — see point 3 below.

**2) Screen types and dayparts.** Screens come in three tiers: **Standard**, **Premium** (large-format recliner auditoriums), and **IMAX**, with ticket price rising by tier. A day's showtimes are grouped into three **daypart** buckets by start time: **matinee** (before noon), **prime** (evening, from late afternoon into the night), and **late_night** (after 11 pm). Natural occupancy varies a lot by daypart — prime is typically highest, late_night typically lowest.

**3) Comp tickets / buyback tickets and the gray area around minimum attendance clauses.** Theaters occasionally give away a small number of comp tickets for promotions or employee perks, which is normal and represents a very small share of attendance. But when natural attendance at a late-night showing of a tentpole film falls well short of the minimum attendance required by the booking agreement, some theater managers choose to "buy back" a batch of tickets themselves (the company pays for them, and the buyer is effectively the theater itself) to push attendance above the threshold. That produces a noticeable anomaly in reported occupancy and comp ticket share — exactly the pattern Q3 is designed to surface.

**4) Loyalty program and point redemption.** Lakeshore Rewards members earn points for every dollar spent, and points can be redeemed 1:1 for free concession items (like a medium popcorn). From the company's perspective, that "free" concession item still incurs a **real cost of goods sold (COGS)**, but generates **no real cash revenue**. If the finance system books that redemption as a "normal sale" (i.e., recognizing revenue at the item's regular retail price), the reported gross margin will look healthier than reality — this is the core trap in Q1.

**5) The hidden fixed costs of a screen.** Every screen, IMAX especially, carries monthly fixed costs for energy (laser/lamp light source, air conditioning) and maintenance (equipment service contracts, lens calibration). That spend doesn't scale linearly with the number of showtimes — it's a "you pay it whether anyone shows up or not" fixed cost. An IMAX auditorium in a secondary market with a small audience base may not cover that fixed cost even though the ticket premium looks attractive on paper — this is the core trap in Q2.

**6) Occupancy and utilization.** **Occupancy rate** = paid attendance for a given showtime / screen seat capacity, a measure of a single showtime's performance. **Utilization** looks at a longer period (say, a quarter) and aggregates showtime and occupancy performance for a screen or theater, and is the basis for capex and de-installation decisions.

---

## 8. Glossary

Every piece of jargon that appears in the ER document or the SQL queries, explained in plain language, along with why it matters for this project. Terms are kept in their original English form throughout.

| Term | Plain-language explanation | Why it matters here |
|------|----------|----------------------|
| Exhibitor | A company that operates movie theaters and runs film screenings | Lakeshore Cinemas' industry identity |
| Film booking | The booking agreement between an exhibitor and a distributor | Determines which film runs on which screen for how long, and whether a minimum attendance clause applies |
| Minimum attendance clause | A "minimum headcount per showing" term in a booking agreement | The contractual source of the Q3 trap |
| Comp ticket / buyback ticket | A free ticket or a ticket the theater buys back itself | The key field Q3 uses to detect inflated occupancy |
| Daypart | The time bucket a showtime falls into: matinee / prime / late_night | The core dimension driving natural occupancy differences |
| Matinee | Lower-priced showings before noon | Natural occupancy is typically lower |
| Prime | Showings from late afternoon into the evening | Natural occupancy is typically highest |
| Late night | Showings after 11 pm | Where the Q3 trap concentrates |
| Occupancy rate | Occupancy rate = paid attendance / seat capacity, measured per showtime | The basic showtime performance metric |
| Screen utilization | Screen utilization, aggregating showtimes and occupancy over a quarter | The basis for Q4 de-installation / re-programming decisions |
| Screen type | Screen type: Standard / Premium / IMAX | Determines the ticket price tier and the fixed-cost tier |
| Market tier | Theater market tier: Primary / Secondary | The Q2 trap concentrates in secondary-market IMAX auditoriums |
| Concession | Popcorn, drinks, candy, and other retail items | A small share of revenue but very high margin and almost fully retained, making it key to exhibitor profit; Q1 tests whether its reported margin is diluted by redemptions |
| COGS (Cost of Goods Sold) | The raw-material cost of concession items | One denominator input to the true margin calculation |
| Gross margin | Gross margin = (revenue − COGS) / revenue | Q1 compares the "recognized" and "cash" versions |
| Recognized revenue | Revenue booked by the finance system (may include phantom redemption revenue) | The "inflated" side of the Q1 trap |
| Cash revenue | Revenue actually received in cash (excludes redemptions) | The "real" side of the Q1 trap |
| Loyalty program | The loyalty program, i.e. Lakeshore Rewards | The mechanism linking member spend to concession redemption |
| Redemption | A member redeeming points for a concession item | The direct source of the Q1 trap |
| Redemption share | Redemption share = redeemed units / (paid units + redeemed units) | Measures how much redemption volume is diluting the margin |
| Screen contribution | Screen contribution = ticket price premium revenue − that screen's energy and maintenance cost | Used in Q2 to identify unprofitable premium screens |
| Energy cost | A screen's monthly energy spend | Part of the Q2 fixed cost |
| Maintenance cost | A screen's monthly maintenance spend (including IMAX licensing/lens upkeep) | Part of the Q2 fixed cost, especially high for IMAX |
| Tentpole film | A major event film a distributor is betting heavily on | Usually comes with a minimum attendance clause |
| Attach rate | Concession attach strength, calculated in this project as "concession units ÷ paid attendance" (units per person), not "share of attendees who bought concession" | The core concept in the Q5 daypart-concession alignment analysis |

---

## 9. Key Metrics and Formulas

Below are the metrics used in the SQL queries, or that a reader should know about. Formulas are written as plain SQL-style pseudocode, with notes on inputs and conventions.

**Concession margin (Q1)**

```
recognized_concession_revenue = SUM(concession_sale.gross_revenue) + SUM(loyalty_redemption.item_full_price × 1)
                                 -- Redemptions are booked into recognized revenue at "full price" -- this is the practice this project is designed to test
cash_concession_revenue       = SUM(concession_sale.gross_revenue)
                                 -- Redemptions generate no cash; true cash revenue excludes them
total_concession_cogs         = SUM(concession_sale.cogs_amount) + SUM(loyalty_redemption.item_unit_cost)
                                 -- Redeemed items still incur a real cost
recognized_margin  = (recognized_concession_revenue − total_concession_cogs) / recognized_concession_revenue
cash_margin        = (cash_concession_revenue − total_concession_cogs) / cash_concession_revenue
margin_gap         = recognized_margin − cash_margin       -- positive value = how many percentage points the recognized margin overstates the true margin
redemption_share   = COUNT(loyalty_redemption rows = redeemed units) / (SUM(concession_sale.units_sold) + COUNT(loyalty_redemption rows = redeemed units))
                     -- Paid side uses SUM(units_sold), since concession_sale is an aggregated table where one row can contain multiple units; the redemption table has one unit per row, so it uses COUNT(*)
```

**Premium screen contribution (Q2)**

```
premium_ticket_revenue(screen) = SUM(showtime.paid_attendance × (showtime.ticket_price − standard_baseline_price))
                                  -- The portion of ticket revenue this screen earns above the standard-screen baseline
screen_fixed_cost(screen)      = SUM(screen_monthly_cost.energy_cost + screen_monthly_cost.maintenance_cost)
screen_net_contribution(screen) = premium_ticket_revenue(screen) − screen_fixed_cost(screen)
                                   -- A negative value means this screen's ticket premium doesn't cover its fixed cost
```

**Late-night buyback tickets (Q3)**

```
comp_share(daypart, has_minimum_guarantee) = SUM(showtime.comp_attendance) / SUM(showtime.paid_attendance + showtime.comp_attendance)
```

**Occupancy and utilization (Q4/Q5)**

```
occupancy_rate(showtime) = showtime.paid_attendance / screen.seat_capacity
screen_utilization(screen, period) = AVG(occupancy_rate) OVER (all showtimes for this screen during the period)
```

**Concession attach rate (Q5)**

```
attach_rate(daypart) = SUM(concession_sale.units_sold WHERE daypart) / SUM(showtime.paid_attendance WHERE daypart)
                        -- An approximate metric aggregated by daypart, not matched at the individual-attendee level
```

> **Convention notes (to keep downstream SQL consistent):**
> - `recognized_concession_revenue` is the deliberately flawed "reported convention" in this dataset — it books member redemptions into revenue at full price. The SQL queries always show both `recognized_margin` and `cash_margin` side by side; don't rely on just one of them.
> - `standard_baseline_price` is the average current-period ticket price for Standard screens within the same theater, used as the baseline for computing the "premium" (grouped only by theater, not by daypart — ticket price only varies by screen type and weekend, not by daypart, which keeps this convention consistent with Query 4/5).
> - `screen_net_contribution` only accounts for the "ticket premium" portion, and excludes shared costs allocated to the screen such as rent and labor — a conservative but sufficiently revealing approximation.
> - The normal baseline for `comp_share` is around 2% (promotional comps, employee perks); Q3 is looking for combinations that deviate noticeably from that baseline (late-night showings × booking agreements with a minimum attendance clause).
