# Vanguard Esports Commercial Operations Health Review: Business Context

## 1. The Company: Vanguard Esports

Vanguard Esports is a fictional esports organization headquartered in Los Angeles, California. It was founded in 2018 by a retired professional shooter-game player and an investor who had previously worked in traditional sports agency representation. Today the club employs around 60 people across players, coaching staff, commercial teams, content teams, and back-office operations. The organization runs three sub-teams:

- **Vanguard Fracture** — the flagship first team, competing in FPCT Americas (the Fracture Protocol Championship Tour, Americas region).
- **Vanguard Aetherlane** — the first team competing in the North American Aetherlane professional league.
- **Vanguard Academy** — the Fracture Protocol development squad, competing at the Ascendant Circuit tier. Its role is to develop and feed young talent up to Vanguard Fracture, and its budget is meaningfully smaller than either of the two first teams.

The club generates roughly $18M in annual revenue, primarily from sponsorships (about 60% of revenue), with tournament prize money and merchandise sales making up the remaining 40% combined. Organizationally, the CEO (one of the co-founders) owns overall strategy and league relationships. The CFO reports to the CEO and owns financial planning, budgeting, and reporting. The COO runs day-to-day commercial operations and has three direct reports: the Head of Partnerships (who owns sponsorship deals), the General Manager of Esports (who owns player contracts and competitive performance, and who in turn oversees the Player Payments Coordinator, responsible for actually disbursing player salaries and prize splits), and the Head of Content (who owns content and streaming). You are the newly hired Commercial Operations Analyst in the COO's office, reporting directly to the COO.

## 2. Business Model: Three Revenue Lines, One Opaque Cost Line

Vanguard Esports earns revenue from three lines:

1. **Sponsorship**: Brands (energy drinks, gaming peripherals, fintech, betting-adjacent brands, and others) pay the club an annual sponsorship fee in exchange for jersey ad placement, in-broadcast logo exposure, and player social media appearances, among other rights. Most sponsorship contracts are priced and billed against a "committed annual exposure hours" figure rather than actual delivered exposure — and that mismatch is one of the central problems this review is meant to surface.
2. **Prize Money**: When a team places in a league or third-party tournament, the tournament organizer (the league operator or a third-party event company) pays prize money to the club. The club then forwards a share to the relevant players, per the prize split percentage written into each player's contract, within an agreed window after the club receives the payout.
3. **Merchandise**: Team jerseys, hoodies, and assorted merch are sold through the online store and at pop-up booths at live events. Gross margin fluctuates with discounting intensity and the team's popularity.

The largest cost item is **player contracts**: each player signs a fixed annual salary (sometimes including a signing bonus), typically for a one- to three-year term. Industry convention is "renew when performance is good, but salary almost never gets cut mid-contract even when performance is bad" — because player contracts are guaranteed. Short of letting a contract lapse at term end, unilaterally cutting a player's pay mid-contract is essentially unheard of in the industry, and doing so would badly damage the relationship with the player's agent. That means once a player's performance slips partway through a contract, the club can't reprice until the contract expires — and in the meantime, this "high salary, low output" cost mismatch keeps quietly eating into profit. Financial reporting, meanwhile, tends to track only coarse metrics like total salary spend over total revenue, which never surfaces which specific player is the drag.

## 3. Project Background: A Board-Level Margin Question Triggers a Commercial Operations Review

In the first half of 2026, Vanguard Fracture made the FPCT Americas playoffs — the club's best season in three years by competitive results. But while preparing Q2 financials, the CFO noticed something troubling: despite the strong on-field results and only modest year-over-year revenue growth, EBITDA margin had actually dropped about 4 percentage points versus the same period last year. Around the same time, the General Manager of Esports received formal complaint emails from two player agencies, reporting that their players' prize-split payouts were "arriving later and later," and in one case, "arrived for less than the amount the contract called for." These two developments prompted the board to ask a pointed question at the July quarterly meeting: "Performance is up — so where's the money going?"

The COO has asked the Commercial Operations Analyst (that's you) to deliver a complete commercial operations health review within three weeks, to be presented directly to the board. The review needs to cover four areas: whether sponsor exposure billing matches actual delivery, whether player salaries have become disconnected from recent performance, the relationship between merchandise gross margin health and team performance / fan engagement, and whether prize-split payments are being made on time and in full per contract. This review is the project this dataset is built to support.

## 4. Industry Overview: How Professional Esports Organizations Monetize

Professional esports grew out of game-streaming and online-tournament culture, and over the past decade it has evolved a commercial structure that increasingly resembles traditional professional sports (like football or basketball): leagues issue franchise slots, and clubs build rosters, sign players, court sponsors, and sell merchandise. That said, esports differs from traditional sports in a few key ways:

1. **Revenue leans heavily on sponsorship rather than ticketing and broadcast rights.** Broadcast revenue for most esports leagues is far smaller than in traditional sports leagues, so commercial teams at esports clubs put disproportionate energy into landing sponsorships and managing sponsor rights.
2. **Exposure billing lacks a unified third-party audit standard.** Traditional sports advertising (stadium signage, for example) has relatively mature third-party measurement bodies behind it. Logo exposure inside esports broadcasts, by contrast, is still often tracked with rough internal estimates by many clubs, or simply billed as a flat fee against a "committed" number of hours, with little incentive or tooling to reconcile after the fact.
3. **Player contracts are guaranteed, and mobility is more constrained.** Most esports leagues have borrowed the salary cap concept from traditional sports (a league-set ceiling on a team's total annual player salary spend), but transfer windows and free-agency rules tend to be more restrictive than in traditional sports, leaving little room to swap players mid-season. That makes the "performance is declining but the contract is locked in" mismatch especially common in esports.
4. **The prize-distribution chain is long, and compliance discipline varies.** Prize money flows from the tournament organizer to the club, and then from the club to individual players, passing through multiple transfers and tax handling steps along the way. Financial processes at small and mid-sized clubs are often less mature than at established traditional-sports agencies, so late payments and split-percentage errors do occasionally happen — and when they do, they can trigger public complaints from players and agents that damage the club's recruiting reputation.

## 5. The 4 Business Questions You Need to Answer

As the Commercial Operations Analyst, you have three weeks to reach conclusions that support the COO's July board presentation. The following four questions each correspond to a deliverable finding:

- **Q1 — Sponsor exposure billing gap**: Does each sponsorship deal's "committed annual exposure hours" match the "measured exposure hours" recorded from broadcasts? Which sponsors are actually getting meaningfully less exposure than their contract promises — meaning the club is exposed to the risk of "charging full price while under-delivering"? Do billing terms need to be recalculated at renewal?
- **Q2 — Salary vs. performance disconnect**: Which players have shown a clear performance decline over the trailing 6 months relative to their historical peak, while salary has stayed untouched because of a long-term locked-in contract, creating a "high salary, low output" cost mismatch? How much time is left on these players' contracts, and do they need to be repriced at the next renewal window?
- **Q3 — Merch gross margin vs. team performance / fan engagement**: Does merchandise gross margin systematically move with swings in recent team performance? During slumps, is the team leaning on heavier discounting just to hold sales volume steady — quietly eroding margin underneath what looks like flat total revenue?
- **Q4 — Prize-split payment compliance**: Are players' prize splits being paid in full and on time, per the percentage and deadline specified in their contracts? Are late or underpaid cases concentrated in a particular team or a particular part of the finance process, and which part most urgently needs fixing to avoid reputational risk?

## 6. Data Scope at a Glance

To keep the analysis tractable and internally consistent, this dataset scopes the data to Vanguard Esports' three sub-teams over the two full seasons from 2024-07-01 through the analysis anchor date REFERENCE_DATE = 2026-06-30 (roughly 24 months) of commercial and competitive operations data. These two years span the club's full arc, from an unremarkable stretch of performance to making the 2026 playoffs, which is enough runway to observe how salary, sponsorship, merch, and prize payments each move as competitive performance rises and falls.

The dataset contains 14 tables and roughly 15,000 rows in total, covering 3 teams, about 20 registered players and their contracts, 10 sponsors, 12 sponsorship deals, 24 tournaments (including regular-season splits, playoffs, and outside invitationals), about 470 matches with corresponding individual player stats, about 570 broadcast sessions, about 2,500 measured sponsor-exposure log records, 25 merch SKUs, about 9,000 merch sales, about 23 prize pool payouts, and about 115 individual player prize distribution records. (A handful of group-stage exits and poor tournament finishes earn no share of prize money and generate no `prize_pool_payout` record, so the count of prize payouts runs a bit lower than the total tournament count.)

## 7. Crash Course: What You Need to Know to Read This Data

**Tournament and season format.** The North American professional leagues for Fracture Protocol and Aetherlane typically run two "splits" per year, each consisting of a round-robin regular season followed by playoffs. After some splits, there's also a cross-region annual championship event (the "champions" or "worlds"-level event). Each row in the `tournament` table represents one such event, and the `tier` field distinguishes event level (S-tier is a league's official top-level event, A-tier is a secondary league or a large invitational, B-tier is a smaller open tournament).

**How exposure billing works.** Most sponsorship contracts (the `sponsorship_deal` table) are priced as a single flat fee against "committed annual exposure hours" (`committed_annual_exposure_hours`) — the brand pays a fixed annual sponsorship fee in exchange for the club's "commitment" that its logo will appear on-broadcast for that many hours. In theory, the club's content team should measure actual on-broadcast hours from stream recordings (that's exactly what the `sponsor_exposure_log` table captures — after-the-fact measurement), but this reconciliation work is labor-intensive and has no enforced process behind it, so many clubs either skip it, or do it but never actually compare it back against the contracted commitment.

**Player contracts and the salary cap.** Most North American esports leagues, following traditional sports, impose a salary cap (the `team.salary_cap_usd` field) — a ceiling on a single team's total player salary spend, intended to stop deep-pocketed clubs from cornering the market on top talent. Once a player contract (the `player_contract` table) is signed, salary is typically guaranteed for the life of the contract (it doesn't get cut mid-term even if performance declines), and the only chance to reprice is at renewal. That means there's often a gap of a year or more between "noticing performance has declined" and "actually being able to adjust salary."

**Individual performance rating.** To measure individual player performance rather than just team win/loss, esports organizations commonly compute a composite score for each player in each match (`player_match_stat.performance_rating`), blending kills, deaths, assists, and other granular stats. The value floats around 1.0: 1.0 represents "performing at the expected average level," meaningfully above 1.0 means the player carried the match, and meaningfully below 1.0 means the player was a drag on the team. In this dataset, this rating is the core basis for identifying "performance decline."

**The prize-split payment chain.** After a team places in a tournament, the tournament organizer first pays the prize money to the club (there's typically a delay between `prize_pool_payout.organizer_payout_date` and `org_received_date`), and the club then forwards each player's contracted share (`player_contract.prize_split_pct`) within the deadline specified in the contract — usually within 30 days of the club receiving the payout — as an individual `player_prize_distribution` record. A delay or a miscalculated split anywhere along this chain ultimately shows up as a mismatch between when/how much a player actually gets paid versus what the contract promised.

## 8. Glossary

| Term | Explanation | Why it matters |
|------|------|------------|
| FPCT (Fracture Protocol Championship Tour) | Fracture Protocol's official professional league system | The top-tier competition system Vanguard Fracture competes in, which caps its prize money and sponsorship value ceiling |
| franchise slot | A fixed competitive slot the league grants a club, similar to a franchise spot in traditional sports | The asset base of the club's business, and the precondition for sponsors being willing to pay |
| salary cap | The league-set ceiling on a team's total annual player salary spend | The reference point for judging "is this salary reasonable" in the Q2 analysis |
| exposure hours | The cumulative time a sponsor's logo appears on-broadcast | The core unit of measurement in the Q1 analysis, split into a "committed" figure and a "measured" figure |
| performance rating | A composite score blending kills/deaths/assists and other stats, floating around 1.0 | The core metric used in Q2 to determine "performance decline" |
| guaranteed contract | A player contract whose salary doesn't get adjusted mid-term due to a performance decline | Explains why the "salary vs. performance disconnect" in Q2 persists for so long without being corrected |
| prize split | The percentage of team prize money a given player is entitled to, per their contract | The contractual baseline used in Q4 to judge "was this paid in full" |
| prize pool | The total prize amount set for a tournament, distributed to competing teams by placement | The tournament's total pool sits in `tournament.total_prize_pool_usd`; the amount a given team actually wins sits in `prize_pool_payout.gross_prize_awarded_usd`, which is the base used to compute each player's prize split |
| Bo1 / Bo3 / Bo5 | Best-of-1/3/5, the match format determining how many games decide a result | The `match_result.format` field; explains why some matches have only one game logged and others have several |
| IGL (In-Game Leader) | The tactical/shot-calling role responsible for in-match decisions on a Fracture Protocol roster | One of the roles in `roster_player.role_position`; an IGL's performance decline tends to drag the whole team down harder |
| Academy team | A development-league team, whose purpose is to develop young talent and feed it up to the first team | Explains why Vanguard Academy's budget and salaries run well below the two first teams |
| MVP (Most Valuable Player) | The standout performer in a given match | The `player_match_stat.was_mvp` field; a secondary indicator of a player's standout moments |
| gross margin | (Sales revenue - cost) / sales revenue | The core metric for assessing merch health in the Q3 analysis |

## 9. Key Metrics and Formulas

```
Sponsor Exposure Delivery Rate
  = Annualized measured exposure / committed_annual_exposure_hours
  where Annualized measured exposure
     = SUM(sponsor_exposure_log.measured_exposure_hours WHERE sponsorship_deal_id = X)
       / effective years of that contract within the data window
  Note: the committed figure is a "per year" exposure-hours number, while measured exposure is
  the sum of all measurement records across the contract's full effective period (which may span
  more than a year, or less than one). So the raw measured total must first be divided by
  "effective years" (= (MIN(contract_end_date, REFERENCE_DATE) - contract_start_date) converted
  to years) to annualize it onto a "per year" basis before dividing by the committed figure, so
  the two are comparable on the same basis. Effective years is computed as a julianday day-count
  difference / 365.25; this is the exact annualization formula used in Query 1/3.
  Below 100% means actual exposure fell short of the commitment; below roughly 80% is treated as
  a gap significant enough to warrant scrutiny.

Trailing 6-Month Performance Rating
  = AVG(player_match_stat.performance_rating)
    WHERE roster_player_id = X AND match_result.match_date
          BETWEEN REFERENCE_DATE - 6 months AND REFERENCE_DATE

Peak-Window Performance Rating
  = AVG(player_match_stat.performance_rating)
    WHERE roster_player_id = X AND match_result.match_date
          BETWEEN REFERENCE_DATE - 18 months AND REFERENCE_DATE - 12 months

Performance Decline (as a percentage)
  = (Trailing 6-Month Performance Rating - Peak-Window Performance Rating) / Peak-Window Performance Rating
  A larger negative value means a more pronounced decline; combine this with the number of months
  remaining until that player's contract_end_date to judge whether "salary should be adjusted but
  can't be because the contract is locked in."

Merch Gross Margin
  = SUM(merch_sale.quantity * (unit_price_paid_usd - merch_sku.unit_cost_usd))
    / SUM(merch_sale.quantity * unit_price_paid_usd)
  Group by the team's trailing 60-day win rate bucket to see whether gross margin is
  meaningfully lower during slumps than during hot form.

Trailing 60-Day Win Rate
  = COUNT(match_result WHERE team_id = X AND result = 'win'
          AND match_date BETWEEN target date - 60 days AND target date)
    / COUNT(match_result WHERE team_id = X
          AND match_date BETWEEN target date - 60 days AND target date)

Prize Distribution Lateness (in days)
  = player_prize_distribution.paid_date - (prize_pool_payout.org_received_date + 30 days)
  A positive value means the payout exceeded the contracted 30-day window; a larger value means a
  more serious delay.

Prize Distribution Fulfillment Rate
  = player_prize_distribution.actual_paid_amount_usd
    / player_prize_distribution.contracted_amount_usd
  Below 100% means the actual amount paid was less than what the contract entitled the player to
  (an underpayment).
```
