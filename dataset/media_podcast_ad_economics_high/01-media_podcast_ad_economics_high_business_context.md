# Business Context: StreamCast Media Podcast Ad Economics

> **Dataset:** `media_podcast_ad_economics_high`
> **Complexity:** High (13 tables, ~138,000 rows)
> **Market:** North America (United States, currency USD)
> **Reference "Today" (REFERENCE_DATE):** 2026-06-21 (data covers the most recent 60 days)
> **Companion docs:** Data structure in `02-media_podcast_ad_economics_high_er_document.md`; SQL queries in `03-media_podcast_ad_economics_high_sql_queries.md`

---

## How to Use This Document

This document is the "onboarding handbook" for the entire dataset. It **does not cover table schemas or column types** (that lives in the ER document); it covers exactly one thing: **what business the company you're about to analyze is actually in, and what jargon and accounting conventions show up in that business.**

Suggested reading order:

1. Start with **Sections 1-5** (company, business model, industry, project, business questions) — to build a mental model of "who I'm working for and what problem I'm solving."
2. Then read **Section 6** (data scope) — so you know what this batch of data covers and what it doesn't.
3. **Section 7** (industry primer) is a crash course for anyone with zero exposure to digital advertising / podcasting. Read it in 30 minutes and you'll be able to talk shop with colleagues.
4. Use **Section 8 Glossary** and **Section 9 Metrics Formulas** as a dictionary — when you hit an English acronym you don't know in the ER document or SQL, flip back here.

After reading this document, you should be able to tell someone in your own words: how StreamCast makes money, why mid-roll ad slots are the most expensive, what a second-price auction is, and why "cramming in more ads" is a double-edged sword.

---

## 1. The Company: Who Is StreamCast Media

**StreamCast Media** is a **Programmatic Podcast Ad Platform** headquartered in **Brooklyn, New York, USA**. It **does not produce podcast content** itself; instead, it provides 150+ independent podcast shows with the tech stack and sales channel needed to "turn listener attention into money." Real-world comparables: Spotify's Megaphone, Acast, Art19, Audacy — but StreamCast is a **fictional company**, and everything in this dataset is simulated.

One-line positioning: StreamCast is the **"ad-exchange middleman for the podcast world"** — one end plugged into **the supply side (podcast hosts)**, the other end plugged into **the demand side (brand advertisers)**, matching the two sides via real-time auctions and taking a cut. In ad-tech jargon, this role is called an **SSP (Supply-Side Platform)**.

**Company size (order of magnitude):**

| Dimension | Magnitude |
|------|------|
| Employees | ~120 |
| Partnered podcast shows | 150+ |
| Monthly listener reach | Millions |
| Annual ad transaction volume | Tens of millions of USD |
| Founded | ~6 years ago |

**Origin story (one sentence):** StreamCast was founded with the goal of giving **independent podcast hosts** — those who lack the resources to build their own ad-sales teams — access to programmatic demand that was previously only available to the big networks, using technology to monetize the ad inventory of "long-tail content."

**The org chart, as it relates to your analytical work:**

| Role | What they care about |
|------|---------|
| **CFO / Finance** | Total platform revenue, net take, total creator payouts |
| **VP of Monetization** | Pricing strategy, fill rate, inventory utilization — many of your reports ultimately roll up to this person |
| **Revenue Operations (RevOps) team** | Day-to-day operational metrics, dashboards — **the team you report directly to** |
| **Account Executive (AE)** | Renewal rate and budget pacing for the advertisers they personally own |
| **Content Partnerships BD** | Which kinds of shows to sign; whether host RPMs are competitive |
| **Pricing / Auction team** | Whether the auction mechanism is healthy, whether floor prices are set correctly |
| **UX / Retention team** | Whether ads are driving listeners away |

---

## 2. The Business Model: How StreamCast Makes Money

StreamCast's core revenue is the **ad take-rate**. The full monetization flow:

```
1. Advertiser tops up budget on the platform and sets targeting goals
   (e.g., "reach 25-34 year olds in CA/NY who listen to tech podcasts")
        │
        ▼
2. Listener opens the app, hits an ad slot (pre-roll / mid-roll / post-roll)
        │
        ▼
3. Platform fires a real-time bid (RTB) within 50 ms; every matching advertiser submits a CPM
        │
        ▼
4. Highest bidder wins the slot, but pays "second-highest bid + $0.01" (second-price auction)
        │
        ▼
5. Ad is dynamically inserted into the podcast stream and played to the listener
        │
        ▼
6. Platform bills the advertiser, keeps 30% as platform commission, and pays out 70% to the host on a weekly/monthly settlement cycle
```

**Revenue formula (memorize this):**

```
Total Platform Revenue (daily) = SUM(winning CPM per impression) ÷ 1000
Platform Net Revenue           = Total Revenue × 30%   (platform take)
Creator Payout                 = Total Revenue × 70%   (host take)
```

**Unit economics:**

- **Fixed 30% / 70% take-rate split** — this is the industry convention used by Spotify, Acast, and others; StreamCast follows suit.
- Revenue is driven entirely by two levers: **how many impressions you sell (volume)** × **how much each impression sells for (eCPM)**.
- Therefore, StreamCast's profit ultimately depends on three things: **whether the fill rate is high (don't leave inventory empty), whether unit prices are set correctly (don't sell valuable inventory cheap), and whether listeners get driven off by ads (churn = future inventory disappears)**.

**Who the buyers are:** Advertisers span several verticals — SaaS, FinTech, CPG, E-commerce, Automotive, Healthcare, and more. Different verticals chase different audiences: SaaS/FinTech fixate on `Tech_Enthusiast` / `Finance_Savvy` segments; CPG goes after `Foodie` / `Health_Conscious`.

**The four eternal tensions in this business** (the highest-leverage areas for data analysis):

| Tension | Pull A | Pull B | How data helps |
|------|--------|--------|--------------|
| Revenue vs. Experience | More ads → more revenue | More ads → annoyed listeners → churn | Find the sweet spot of ads-per-episode with the highest ROI |
| Fill Rate vs. Unit Price | Higher CPM → more per impression | Higher CPM → advertisers balk → unsold inventory | Dynamic pricing: high in peak hours, discounted in lulls |
| Targeting vs. Scale | Targeted audience → higher conversion | Targeted audience → smaller reach → budget can't be spent | Measure whether targeting premiums deliver proportional returns |
| Platform vs. Creators | Platform wants a bigger cut | Creators need 70% to stay in business | Help hosts see "which content types have the highest RPM" |

---

## 3. Industry Overview: The Programmatic Podcast Ad Business

If you're coming in from another industry, this section orients you on what this market is actually doing.

**What value does this industry create?**
Traditional podcast ads were **host-read** plus **baked into the audio file**. Re-listen to a three-year-old episode and you'd hear the same ads from three years ago — the advertiser can't keep paying, can't target, can't measure. The programmatic podcast ad industry uses **DAI (Dynamic Ad Insertion)** to turn ad slots into "blank placeholders" that get filled in real time, on every playback, with whatever ad won the auction at that moment. This delivers three revolutions: **back-catalog episodes can keep generating revenue, ads can be targeted to specific audiences, and the same inventory can be resold and measured over and over.**

**Player categories in the industry** (using generic terms, no naming names):

| Role | What they do | Where StreamCast sits |
|------|--------|----------------|
| **SSP (Supply-Side Platform)** | Helps publishers/hosts sell ad inventory | **← StreamCast is an SSP** |
| **DSP (Demand-Side Platform)** | Helps advertisers programmatically buy inventory and optimize bids | Tool that advertisers use |
| **Podcast hosting platform** | Stores and distributes audio; provides DAI capability | Upstream / sometimes integrated |
| **Ad network** | Bundles a batch of inventory and sells it to advertisers | Competitor / complement |
| **Measurement & attribution** | Measures conversions driven by ads | Third-party vendor |

**North American regulation and industry norms** (which you may cite in reports):

- **FTC (Federal Trade Commission):** Polices false advertising; has endorsement guides covering sponsored content / host-read promotions.
- **CCPA / CPRA (California Consumer Privacy Act):** Restricts how platforms collect and use listener data — this is why the `listener` table can only store anonymous UUIDs, not real identities.
- **COPPA (Children's Online Privacy Protection Act):** Special restrictions for content aimed at children under 13.
- **IAB Tech Lab standards (VAST, etc.):** Industry self-regulatory technical specs that standardize ad delivery and counting conventions.
- **Canada:** PIPEDA (privacy) and CASL (anti-spam marketing) — applicable when expanding into the Canadian market.

**Macro forces shaping the industry right now:**

1. **Big-tech consolidation:** Streaming giants keep acquiring podcast ad-tech, putting mid-tier platforms under "get acquired or get squeezed out" pressure.
2. **Baked-in → DAI shift:** Dynamic insertion has become mainstream; programmatic share grows year over year.
3. **Tightening privacy + cookie deprecation:** As third-party identifiers go away, platforms are pushed toward **contextual targeting** and **first-party data** (the listener segments in `listener_segment` are exactly this kind of first-party data asset).
4. **AI infiltration:** AI is being used for ad matching, dynamic creative generation, and bid optimization — opening up new ways to balance the "targeting vs. scale" trade-off.

---

## 4. Project Background: Your Role and Deliverables

**Who you are:** You're a **BI / Data Analyst Intern on the Revenue Operations team** at StreamCast, reporting directly to the RevOps Manager (whose manager is the VP of Monetization).

**What you don't need to know:** You don't need to understand how ad-serving algorithms are actually written, and you don't need to know how to produce a podcast.

**What you absolutely need to know:** Be able to explain every business metric crisply — trade-offs like "high CPM = company makes more, but listener experience may suffer" should roll off your tongue.

**Your day-to-day work falls into three buckets:**

1. **Respond to ad-hoc data requests** — the sales director asks, "what was the actual CPM on tech-podcast mid-rolls last week?" and you write the SQL.
2. **Maintain standing dashboards** — the 9 AM daily "fill-rate monitor" and the "advertiser budget burn alerts"; when something breaks, you triage it.
3. **Produce deep-dive analytical reports** — before the Q3 strategy meeting, the CFO wants a "which advertisers are at churn risk" early-warning report; you scope it, run it, draw insights, and recommend actions, end-to-end.

**Who consumes your deliverables:** the VP of Monetization (pricing and inventory decisions), the CFO (revenue forecasts), the sales director and AEs (pitch-deck ammo, renewal plays), Content Partnerships BD (signing pipeline), and the UX / Retention team (anti-ad-fatigue strategy).

---

## 5. The Business Questions This Project Has to Answer

The five questions below are the "main plot" of this dataset. The table schemas in the ER document, the data distributions baked into the generator, and the queries in the SQL document all exist to answer them.

**Q1. Is the mid-roll floor price set too low? Which inventory is being seriously underpriced and should be marked up?**
The industry "consensus" is that mid-roll is the most valuable slot (highest completion rate), with floors set at 1.67× the pre-roll price ($25 vs $15). But if actual clearing prices come in well above the floor, the platform is "leaving money on the table." → Addressed by SQL Query 1 and Query 6.

**Q2. Why are overnight and weekend ad slots heavily unsold? How much revenue can dynamic pricing recover?**
Listeners don't actually listen less during off-peak hours, yet fill rate drops noticeably — that's wasted inventory and lost revenue. Can we lower the floor in slow periods and attract budget-sensitive mid- and small-tier advertisers to fill the gap? → Addressed by Query 2 and Query 4.

**Q3 / Q4. Does the targeting premium on high-value audience segments actually deliver proportional returns?**
Segments like `Tech_Enthusiast` make CPMs run 30-50% higher than untargeted buys; is the extra spend worth it to the advertiser? And can the platform use this data as ammo for the sales pitch? → Addressed by Query 3 (platform's view) and Query 9 (advertiser's view).

**Q5. At what ad frequency does fatigue kick in and start driving listeners away?**
When the same listener gets carpet-bombed by the same advertiser, they start skipping aggressively or even churning. Where should the frequency cap be set? → Addressed by Query 17 and Query 19.

**Q6. Is the second-price auction mechanism being executed correctly (no bugs causing overcharges)?**
In theory, the winner should pay "second-highest bid + $0.01." If the average overcharge is well above $0.05, there's a bug in the billing code and advertisers will complain. → Addressed by Query 22.

**Secondary questions** (also covered by queries): advertiser budget burn and pacing health (Query 5, Query 23), per-campaign / per-creative ROI (Query 7, Query 8, Query 11), host RPM peer benchmarking (Query 13~16), industry and show-category growth trends (Query 25, Query 26).

---

## 6. Data Scope Overview

- **Time window:** Treats `REFERENCE_DATE = 2026-06-21` as "today"; data covers the most recent **60 days** (roughly 2026-04-22 ~ 2026-06-21). All SQL queries use the **literal date `'2026-06-21'`** rather than `DATE('now')`, to guarantee reproducible results.
- **Data volume (in plain English):** ~50 shows, ~200 episodes, 40 advertisers, ~98 campaigns, ~244 creatives, 5,000 listeners, ~10K audience-segment rows, 15K listening sessions, ~18K ad impressions, ~87K bid log entries, ~1,800 daily settlement rows — totaling about **138K rows**.
- **Intentional scope choices:**
  - **Only ad monetization is modeled; subscription fees are not.** The fact that premium listeners and members-only shows "produce no ad revenue" is reflected in the data, but the subscription fees themselves are out of scope.
  - **Market is restricted to North America (US).** Listener geography uses US state codes (CA/NY/TX/...); currency is USD.
  - **Listeners are fully anonymized.** For CCPA compliance, the `listener` table only carries UUIDs, no real identities.
  - **This is a 60-day sample slice.** As a result, the absolute spend on any single campaign is often only a few to a few dozen dollars — when analyzing, **focus on ratio metrics (completion rate, CPCV, burn rate); don't get hung up on absolute dollar amounts**.

> For the actual tables, columns, foreign keys, and data distributions, see `02-..._er_document.md`. This section just gives you a high-level feel for "how big this batch of data is and what it covers."

---

## 7. Industry Primer (Podcast Ad 101)

If you've never touched digital advertising or the podcast industry, master these 5 concepts and everything else in the data will click.

### 7.1 The Three Ad Slot Types

| Position | Common name | Typical length | Listener completion rate | Base CPM | Why it's worth that |
|------|---------|---------|------------|----------|----------------|
| **Pre-roll** | Opening ad | 15-30 sec | ~88% | $15 | Listener just opened the app; attention is peak |
| **Mid-roll** | In-episode ad | 30-60 sec | ~95% | **$25** (most expensive) | Listener is already invested; won't abandon the second half just to skip an ad |
| **Post-roll** | Closing ad | 15-30 sec | ~42% | $8 (cheapest) | Many people quit once the main content ends; reach is lowest |

**Why is mid-roll the most valuable?** Because listeners have already invested 10+ minutes, **sunk cost** keeps them from abandoning the second half over a single ad → completion rate is highest → the ad message lands intact. This is the most lucrative inventory in the whole business; platform, host, and advertiser all have their eyes on it.

### 7.2 Real-Time Bidding (RTB)

The moment a listener is about to hit an ad slot (typically within 50-100 ms), the platform: packages the listener profile (age, region, interest segments, listening history) → broadcasts it to every interested advertiser → each advertiser decides whether to bid and how much → highest bidder wins, ad is inserted and played. **The whole flow is automated; no human is in the loop on individual transactions.**

### 7.3 Second-Price (Vickrey) Auction

This is **the core mechanism of the entire digital ad industry**; you have to understand it cold:

- **Scenario:** 5 advertisers bid on the same slot. Bids: A $30 / B $25 / C $20 / D $15 / E $10.
- **Winner:** A (highest bid).
- **Actually paid:** **$25.01** (second-highest bid + $0.01) — **not $30**!

**Why is it designed this way?** To get advertisers to **bid their true willingness to pay** without having to game "how much higher do I need to be than #2." This is Nobel-Prize-level mechanism design, theoretically driving the market to optimal efficiency. As an analyst, what you watch is whether the platform is **actually** billing at the second price (see fields `winning_bid_cpm` vs. `actual_charge_cpm`).

### 7.4 Dynamic Ad Insertion (DAI)

The old way baked ads into the audio file; DAI turns ad slots into blank placeholders that get filled in real time with whatever ad won the auction at playback. In the same episode, listener A hears a Nike ad while listener B hears a McDonald's ad. This is what lets **back-catalog episodes keep monetizing, lets ads be targeted, and lets inventory be resold** — it's the technical bedrock of this business.

### 7.5 The Three-Way Relationship

```
[Advertiser]          [StreamCast platform]          [Podcast host]          [Listener]
   ↓                          ↑                            ↓                      ↓
budget $$$  →  auction matching + 30% take  →  70% payout  ←  attention + listening time
```

The platform has to keep both ends happy: advertisers (the money side) and hosts (the supply side); **listener experience is the shared moat** — if listeners leave, the inventory evaporates.

---

## 8. Glossary

The "lingua franca" of the digital ad industry. Every meeting, deck, and email uses these English acronyms; you have to memorize them. Each entry = **English term + plain-English explanation + why it matters in this dataset**.

### 8.1 Pricing and Monetization

| Term | Full name | Plain English | Why it matters |
|------|------|--------|-----------|
| **CPM** | Cost Per Mille | How much the advertiser pays per 1,000 ad plays (= the platform's selling price) | The base unit of platform revenue; runs through nearly every query |
| **eCPM** | effective CPM | The **actual average clearing price** after auction and second-price discounting | Reflects the true market value of inventory better than the "floor price" (Q1/Q6) |
| **RPM** | Revenue Per Mille | How much the **host nets** per 1,000 **episode plays** (after the 30% take) | The host-side monetization efficiency; ranges from low double digits to a few tens of dollars (Q13/Q14) |
| **Base CPM** | Floor price / base CPM | The minimum opening bid the platform sets for each slot type; bids cannot go below this | The reference line for pricing decisions (Q1/Q6) |
| **Take Rate** | Take rate | The share of total revenue the platform keeps (fixed at 30% here) | Platform net revenue = Total Revenue × take rate |

> **CPM vs. RPM is the most-confused pair:** CPM is **the price of an ad slot** (paid by the advertiser); RPM is **a show's monetization efficiency** (netted by the host). Sell an ad at CPM = $20 → minus 30% → host nets $14 → with ~1.5 ads per play, RPM ≈ $9-14 per 1,000 plays.

### 8.2 Performance and Returns

| Term | Full name | Plain English | Why it matters |
|------|------|--------|-----------|
| **Completion Rate** | Completion rate | Share of listeners who listened all the way through an ad | Reflects ad quality + listener stickiness (Q1/Q8) |
| **Skip Rate** | Skip rate | Share who skipped through the ad midway | The higher, the more annoying the ad (Q17/Q18) |
| **CTR** | Click-Through Rate | Share who clicked the ad's link (~0.5-1.5% for podcasts) | Measures ad appeal; this dataset models `was_clicked` |
| **Conversion Rate** | Conversion rate | Share who actually ordered / signed up after the ad | The ultimate outcome; `converted` is modeled |
| **CPA** | Cost Per Acquisition | How many dollars it takes to acquire one new customer | The advertiser's ultimate KPI (Q7) |
| **CPCV** | Cost Per Completed View | How many dollars it takes to get one person to **listen all the way through** an ad | A stricter performance metric than CPM (Q8/Q11) |
| **ROAS** | Return On Ad Spend | How many dollars of revenue you earn back per $1 of ad spend | How advertisers judge whether the spend was worth it (SaaS healthy line ≈ ROAS 3) |
| **LTV** | Lifetime Value | How much revenue one customer contributes over their lifetime | Used to judge whether a given CPA is worth it (LTV/CPA > 3 is usually safe) |

### 8.3 Inventory and Auction

| Term | Full name | Plain English | Why it matters |
|------|------|--------|-----------|
| **Fill Rate** | Fill rate | Whether ad slots are sitting empty (filled count ÷ available count) | Inventory utilization; healthy value is 90%+ (Q2/Q4) |
| **Inventory** | Ad inventory | Total number of ad slots available over some time window | The platform's "shelf space" = play count × ad slots per episode |
| **Win Rate** | Win rate | Out of N bids submitted, how many an advertiser won | Used by advertisers to tune bid strategy (Q10/Q12) |
| **Bidders per Auction** | Bidders per auction | Average number of advertisers competing in a single auction | 6+ = seller's market; <2 = inventory is underpriced (Q21) |
| **Bid Spread** | Bid spread | Highest bid minus lowest bid in a single auction | The wider, the more disagreement on valuation and the more useful the auction (Q21) |
| **Audience Match Score** | Targeting match score (0-1) | How well the listener fits the advertiser's targeting criteria | Drives bid premiums (Q9) |
| **Pacing** | Pacing | Spreading budget evenly across the campaign window | Too fast and it burns out early; too slow and it doesn't get spent (Q23) |

### 8.4 Mechanisms and Industry Concepts

| Term | Full name | Plain English |
|------|------|--------|
| **RTB** | Real-Time Bidding | An automated ad auction completed within 50 ms |
| **DAI** | Dynamic Ad Insertion | Inserting ads in real time at playback (lets back-catalog episodes re-monetize) |
| **SSP** | Supply-Side Platform | The programmatic selling platform used by publishers/hosts (StreamCast is an SSP) |
| **DSP** | Demand-Side Platform | The programmatic buying platform used by advertisers |
| **CTA** | Call To Action | The "order now / visit the site" prompt in the ad |
| **Second-Price Auction** | Second-price / Vickrey auction | Winner pays second-highest bid + $0.01, incentivizing honest bidding |
| **Frequency Cap** | Frequency cap | Caps how many times one listener sees the same advertiser within a window |
| **Ad Fatigue** | Ad fatigue | After hearing the same ad too many times, listeners get annoyed and skip rates rise |
| **Brand Safety** | Brand safety | Preventing ads from showing up next to unsuitable content |
| **Competitor Exclusion** | Competitor exclusion | Advertisers demand not to appear in the same episode as competitors (e.g., Coke vs. Pepsi) |
| **Premium (ad-free)** | Ad-free membership | Premium listeners / members-only shows generate no ad impressions |

---

## 9. Key Metrics and Formulas

This section defines the canonical computation for every important metric in this dataset. **Where two conventions could be used, this section picks one explicitly** — so that different queries don't produce inconsistent numbers.

### 9.1 Platform Monetization

```
Total Revenue                = SUM(ad_impression.actual_charge_cpm) / 1000
Platform Net Revenue         = Total Revenue × 30%
Creator Payout               = Total Revenue × 70%
eCPM (actual avg clearing)   = AVG(ad_impression.actual_charge_cpm)
                              ( = Total Revenue / impression count × 1000, equivalent)
RPM (host net per 1K plays)  = (Creator Payout / play_session count) × 1000
```

> **Fill Rate has two conventions — always declare which one you're using:**
> - **Settlement convention (`revenue_settlement.fill_rate`):** Denominator = ad slots **actually reached** by the listener (mid/post-rolls the listener didn't reach don't count). Skews high.
> - **On-the-fly convention (Query 2 / Query 4):** Denominator = **all "session-slot pairs"** (including slots the listener didn't reach). Skews low.
> Both are ≤ 100%, but the conventions differ; when comparing across queries, you must spell out which one you used.

### 9.2 Advertiser Performance

```
Spend (campaign already spent) = SUM(actual_charge_cpm) / 1000   (limited to that campaign)
Budget Utilization %           = Spend / window_budget_usd × 100
                                ( Use window_budget_usd, NOT total_budget_usd;
                                  otherwise under a 60-day sample, utilization is ~0%, see ER doc note )
Completion Rate                = SUM(was_completed) / COUNT(*)
Skip Rate                      = SUM(was_skipped) / COUNT(*)
CPCV                           = Spend / SUM(was_completed)
CTR                            = SUM(was_clicked) / COUNT(*)
Conversion Rate                = SUM(converted) / COUNT(*)
CPA                            = Spend / SUM(converted)   ( NULL when SUM(converted) = 0 )
Win Rate (per campaign)        = SUM(won_auction) / COUNT(*)   (over ad_auction_log)
```

### 9.3 Host / Show

```
Plays per Episode    = COUNT(play_session)   (grouped by episode)
Avg Completion %     = AVG(play_session.completion_percentage)
Daily RPM            = revenue_settlement.rpm
Category RPM bench   = avg / min / max RPM within the same category
                       ( Note: SQLite has no native PERCENTILE_CONT; medians/percentiles need NTILE or external calc )
```

### 9.4 Auction Market

```
Avg Bidders per Auction = COUNT(ad_auction_log) / COUNT(DISTINCT impression_id)
Bid Spread (per auction)= MAX(bid_cpm) - MIN(bid_cpm)
Winner's Savings        = winning_bid_cpm - actual_charge_cpm
Second-Price Premium    = actual_charge_cpm - second-highest bid   ( should be ≈ $0.01 )
```

### 9.5 Listener Experience

```
Ad Frequency         = COUNT(ad_impression) / distinct listener count   (per time window)
Ad Fatigue Score     = same-advertiser impression count × skip_rate
Premium Conversion   = is_premium_subscriber listener count / total listener count
```

---

**Version:** v2.0 (0.2.1 spec)
**Last updated:** 2026-06-21
