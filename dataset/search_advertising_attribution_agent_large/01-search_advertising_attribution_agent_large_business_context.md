# Search Advertising Attribution Agent Dataset: Business Context and Industry Primer

This is the first of four documents that accompany the `search_advertising_attribution_agent_large` dataset. Its job is to put the data back into the real business it serves. The other three documents cover the data structure (`02-..._er_document.md`), example queries (`03-..._sql_queries.md`), and the data generation script (`04-..._data_generator.py`). After reading this file, someone who has never touched paid search before should be able to sit in on a team standup and follow the conversation.

The intended reader is a smart outsider, not an industry expert. Picture yourself as a new intern who just joined the team and hasn't been to the first standup yet. This document covers the company, the industry, the project, the problems being solved, and the wall of jargon all in one pass. The market is assumed to be North America by default: the company is U.S.-based, the currency is USD, the clients and cities are in North America, and the regulators are U.S. or Canadian. English is just the narration language; the business itself is North American.

---

## 1. Company Profile

The protagonist of the story is a fictional North American media agency holding group called **Lumina Reach Media Group**, headquartered in Chicago, Illinois. It does not correspond to any real company.

Lumina Reach is not a single agency but a network of agencies. It owns 15 member agencies (the `agency` table in the data), tiered into Platinum, Gold, Silver, and Standard based on service capability. Together these member agencies run paid search for 80 advertiser brands (the `advertiser` table, spanning ten industries: retail, travel, finance, healthcare, automotive, insurance, B2B SaaS, education, real estate, and food service). About 80% of those advertisers are managed by one of the network's agencies (via the `agency_client` bridge table); the remaining 20% are run in-house by the brand's own team but still funnel their data into this same group-wide reporting platform.

For a sense of scale: the entire network has a few hundred people, with a central analytics team of about a dozen at group HQ whose job is to roll up scattered execution data from member agencies into cross-portfolio views. Across the dataset's window, these 80 advertisers spend tens of millions of USD on paid search across Google Ads and Microsoft Advertising. Structurally, that breaks down to around 800 campaigns, 4,200 ad groups, and 42,000 keywords, generating well over a hundred thousand rows of daily performance data per day.

A few roles inside the organization will get named later in the queries: the group CMO (who wants the cross-portfolio industry mix and the attribution truth), member-agency account managers (who watch budget pacing on the advertisers in their book), advertiser-facing campaign managers and paid search analysts (who do day-to-day optimization), and the operations specialists who do negative-keyword reviews. The role you'll play is a data analyst on that central analytics team.

---

## 2. Business Model

How Lumina Reach makes money, in one sentence: it charges a management fee on the ad spend it manages.

The mechanics: an advertiser hands a paid-search budget of anywhere from a few thousand to a few hundred thousand dollars per month to one of the member agencies. The agency stands up the account, picks keywords, sets bid strategies, watches budget pacing, configures conversion tracking, and produces reports. In return, the agency takes a percentage of managed spend, stored in `agency_client.fee_percentage` and ranging from 8% to 20%. Clients who spend more or sit at a higher service tier negotiate different rates, and a handful pay a flat annual retainer instead of a percentage. The implication is that group revenue is directly tied to two things: how much ad spend is under management, and how well that spend is managed (because only well-managed accounts renew and grow their budgets).

The advertiser side is a separate scorecard. Advertisers don't care about the agency fee per se; they care whether every dollar of ad spend brings back enough business. They watch two efficiency metrics: CPA (cost per acquisition, total spend divided by total conversions) and ROAS (return on ad spend, conversion value divided by spend). A campaign at $50 CPA and 4.0 ROAS is healthy: every $50 spent yields $200 in customer value. A campaign at $200 CPA and 0.8 ROAS is losing money and needs intervention. An agency's value shows up in its ability to bring CPA down and ROAS up.

Order values vary dramatically across industries, and that alone separates the ROAS numbers. High-ticket verticals (real estate, finance, insurance, automotive) generate hundreds to a few thousand dollars per conversion. Low-ticket verticals (food service, retail) generate tens to a few hundred per conversion. So for the same dollar spent, a real estate advertiser will naturally show a much higher ROAS than a restaurant chain — that's not a difference in agency skill, it's the underlying economics of the vertical. Keep this in mind when you start reading cross-industry reports.

---

## 3. Search Advertising Industry Landscape

To bring someone in from another industry, start with what paid search is actually trading.

When you type a query like `cheap flights to maui` into a search engine, the engine returns two kinds of results on the same page. One is organic results, ranked by relevance algorithms and free. The other is sponsored results (labeled Ad or Sponsored), selected via a real-time auction the advertiser pays for. Search advertising is the business of those sponsored slots. The advertiser tells the engine in advance, "If someone searches this term, I'm willing to pay up to this much to show my ad." When a matching query arrives, the engine instantly runs an auction across all advertisers competing for that term, ranks them by bid times quality score, and shows the top few.

There are three parties in this market. Users want answers relevant to their query. Advertisers want clicks and conversions at a price they can absorb. The search engine wants auction revenue plus long-term goodwill (if the ads are terrible, users will leave). This dataset sits on the advertiser side — more precisely, on the side of the agency running the advertiser's campaigns.

The main player categories (no real companies named) are: the search engines themselves (the data covers Google Ads and Microsoft Advertising), media agencies like Lumina Reach, in-house brand marketing teams, and the platform vendors who provide unified management tooling. In the North American market, Google dominates; Microsoft is much smaller but has lighter bid competition, so it's often used as incremental inventory.

Regulation and compliance have become the elephant in the room over the last few years. The U.S. FTC (Federal Trade Commission) polices false and deceptive advertising. California's CCPA and a growing list of state privacy laws govern how user data is used. Browsers are phasing out third-party cookies, Apple's privacy rules have tightened, and so on — collectively called "signal loss," and they are knocking out the foundation that cross-site user tracking and deterministic attribution were built on. On top of that, the antitrust suits aimed at Google's dominance in search are forcing the industry to question its base assumptions.

A few macro forces shaping the current era are worth remembering. First, automation and AI bidding (Smart Bidding) are taking over manual bid tuning; the analyst's job is shifting from "adjust bids" to "audit whether the machine is adjusting them correctly." Second, signal loss is pushing the industry from deterministic tracking toward modeled attribution. Third, once budgets are spread across multiple engines and channels, attribution (which touchpoint actually drove the conversion?) stops being an academic question and becomes a daily budget-allocation decision. That last issue is exactly what this dataset is built around.

---

## 4. Your Role and the Project

You're a data analyst on Lumina Reach's central analytics team. You don't directly manage any one advertiser's campaigns. You sit above all the member agencies and advertisers and do cross-portfolio analysis and reporting.

Your output falls into three categories. First, cross-portfolio performance materials for the group CMO and quarterly reviews (which industries are spending the most, which agency tiers post the strongest ROAS, what's the overall efficiency trend). Second, operational dashboards for the member-agency account managers and campaign managers (budget pacing, budget-constrained campaigns, campaigns over Target CPA). Third — and the most technically interesting — attribution what-if analysis: take the same set of conversions, re-allocate credit under different attribution models, and see how the channel value ranking shifts. That third one directly drives where next quarter's budget gets reallocated.

The audience for these deliverables includes the group CMO, member-agency heads, the advertiser-facing client teams, and occasionally the advertisers themselves. Definitions have to be consistent across reports, because different people will use the same metric to make different decisions, and inconsistent definitions lead to conflicting conclusions.

The whole dataset is anchored to a fixed reference date (`REFERENCE_DATE`). All "last 7 days / 30 days" windows count back from that date, not from the actual query-execution date. That way, no matter how long ago the dataset was generated, the results are stable and reproducible. Technically, the reference date is exposed through the `v_reference_date` view, which returns the latest `report_date` in `daily_stats`.

---

## 5. The Business Questions This Project Answers

The whole dataset is built around the following five concrete questions. Each of the 20 queries in the SQL document later traces back to one of them.

**Question 1: the attribution truth.** Most advertisers default to last-click attribution — every dollar of credit for a conversion goes to the last ad the user clicked before converting. The problem is that last-click systematically undercounts upper-funnel channels (Display, Paid Social) and overcounts the "closer" channels (Paid Search, Direct). If you reallocate budgets based only on a last-click report, you can starve the very channels that started the customer journey. We need to run the same set of conversions through six attribution models and quantify how big that bias actually is. This is the project's core question, and it's where the dataset gets its name.

**Question 2: budget efficiency.** Which campaigns are leaving impressions on the table because the daily budget runs out (`lost_is_budget` is high)? Which campaigns are overspending and pacing far over 100%? The first list is the "easy money" — adding budget directly buys more impressions. The second list needs the brakes.

**Question 3: cross-engine efficiency.** The portfolio is Google-dominated (about 75% of spend), with Microsoft at about 25%. Microsoft clicks are cheaper but the conversion rate is also lower. When you put the CPA and ROAS side by side, is Microsoft actually worth more investment?

**Question 4: waste cleanup.** Which search terms spent money with zero conversions and are candidates for the negative-keyword list? Which keywords have low Quality Score and are dragging up the cost of their campaign? Which ad groups have an unhealthy broad-match overflow rate, indicating the match types are set too loose? These are all levers for clawing budget back from waste.

**Question 5: agency and portfolio structure.** Do Platinum-tier agencies really post higher ROAS than Standard-tier? What does the spend, advertiser count, and ROAS distribution look like by IAB industry? These drive talent allocation and client-portfolio decisions at the group level.

---

## 6. Data Scope at a Glance

On the time dimension, the fact data is a recent snapshot and the account structure data is a historical accumulation. `daily_stats` (daily campaign performance) covers 90 days back from the reference date. `search_term_report` (search term performance) covers 30 days back. `conversion` (conversion events) covers 90 days. The account structure (campaigns, keywords, etc.) has creation timestamps scattered across the last 18 months.

In plain numbers: 80 advertisers, around 800 campaigns, 4,200 ad groups, 42,000 keywords, and 12,500 text ads. The fact tables are larger: around 165,000 rows of daily performance, 5,000 conversion events, around 15,400 attribution touchpoints, and around 318,000 search term records. Total around 570,000 rows across 21 tables.

A few deliberate scope choices to flag up front. The whole dataset uses a single currency (USD) and a single time zone (America/Los_Angeles), because while real SA360 deployments are multi-currency and multi-time-zone, this dataset doesn't want currency conversion and time-zone alignment to distract from the teaching goals. Only two engines are modeled (Google Ads and Microsoft Advertising); the third real-world engine, Yahoo Japan, is dropped because it only serves the Japanese market, not U.S. advertisers. The market is North America only. These narrowings keep the dataset focused on the three core threads — attribution, bidding, and budgeting — without getting buried in deployment details.

Row counts per table, field semantics, and join paths are left to the ER document. This section just gives you the scope overview.

---

## 7. Industry Knowledge Primer

This is the 30-to-60 minutes of background an outsider needs before the data starts to make sense. After reading it, the jargon above and the column names in the queries later will all click.

### The Account Tree: How a Campaign Is Organized

Every advertiser's account follows the classic five-level Google Ads / SA360 structure, from top to bottom: advertiser (the company paying the bill), engine_account (one account per engine per advertiser), campaign (a budget envelope plus targeting plus status), ad group (a theme inside a campaign), and then it branches into keyword (what users search) and text ad (the text creative users see before clicking).

A concrete example helps anchor it. The advertiser is Acme Travel Co. (an online travel agency). It has one Google Ads account and one Microsoft Advertising account. Inside the Google account is a campaign called "Acme Cancun Hotels Mobile" (U.S.-only, $2,000 daily budget, using Target ROAS bidding). Inside that campaign is an ad group called "Cancun All-Inclusive Resorts." Inside that ad group sit a keyword like `all inclusive cancun` (exact match, $4.50 max bid) and a text ad. When a user searches `all inclusive cancun`, the engine matches the query to that keyword, runs an auction, and if Acme wins, shows the ad; if the user clicks, Acme pays the auction's clearing price.

### How the Money Flows

Advertisers pay per click (CPC, cost per click), not per impression. An ad that gets shown but not clicked costs nothing. The actual price paid per click is usually less than the advertiser's max bid — it's the minimum amount needed to beat the next bidder. There are also pay-per-conversion and ROI-optimized bidding variants, but the underlying billing unit is the click.

Each click charged becomes the engine's revenue, which is how Google and Microsoft make money on search. The advertiser hopes the click converts into a paying customer whose lifetime value (LTV) covers the click cost plus a reasonable margin. The agency takes a percentage of managed spend on top. All three sides get a slice.

### What Is Search Ads 360

Big advertisers rarely use only one engine. A U.S. retailer might use Google Ads for the bulk of demand and Microsoft Advertising to pick up traffic from Bing and Edge. Logging into each engine's UI separately is painful: you can't compare spend across engines, you can't reuse bid strategies, and conversion tracking has to be wired up twice.

Search Ads 360 (SA360) is Google's enterprise platform built exactly to solve this. Advertisers connect their per-engine accounts into SA360, and it becomes a unified surface for managing campaigns, delegating bidding, allocating budgets, and tracking conversions across engines. Agencies live in SA360 because they typically manage multiple advertisers on multiple engines at once. This dataset models the SA360 layer — the rolled-up cross-engine view across 80 advertisers, not the view from inside any one engine.

### Impression Share: How Much Opportunity Did I Get

Impression Share (IS) is a key diagnostic metric. It answers: of all the auctions I could have participated in, what percentage did my ad actually show in? Impression share of 70% means 30% of the opportunities slipped past.

The lost portion breaks down into two reasons. One is bid or quality (lost IS rank — you lost the rank race). The other is budget (lost IS budget — your daily budget ran out and the ad paused). The three pieces together — the share you got plus the two reasons you lost the rest — sum to roughly 100%. This breakdown matters a lot: if losses come mostly from budget, more budget directly buys more impressions; if losses come from rank, more budget won't help, you need to fix bids or quality score.

Search traffic also has finer-grained position metrics. `search_top_is` is the share of the top of the search results page above the organic listings; `search_abs_top_is` is the share of the very first position. By construction these are ordered: absolute-top share ≤ top share ≤ overall impression share. These position metrics are reported only for search traffic. They are NULL on Display, Video, Performance Max, and Shopping campaigns.

### Quality Score: The Engine's Grade for Your Keyword

Quality Score (QS) is a 1-to-10 score the engine assigns to each keyword, combining expected click-through rate, ad relevance, and landing page experience. A high score means the same bid buys a better rank and a lower actual CPC. A low score means you either spend more or rank worse.

The more competitive the vertical, the harder it is to score well. In this dataset, insurance, finance, and real estate (high-competition verticals) skew toward lower QS (averaging around 6), while B2B SaaS, education, and food service (lower-competition verticals) skew higher (averaging 7 to 8). So a question like "which industry has the most low-QS keywords" has a structural answer, not a random one.

### Match Types and Search Terms

Keywords have three match types, from strict to loose: exact match (matches only nearly identical queries), phrase match (matches queries containing the phrase), and broad match (matches whatever the engine considers related). Looser matching covers more queries but also pulls in more irrelevant, non-converting ones.

`search_term_report` logs the actual user-typed queries that triggered an ad. There's an important phenomenon here called broad-match overflow: about 15% of search-term rows can't be tied back to any existing keyword (the `keyword_id` column is NULL), because the query the engine served didn't directly hit a keyword in the account. A high overflow rate signals that match types are too loose and money is leaking to queries nobody is watching.

### Conversion Tracking and Multi-Touch Attribution

When a user completes a purchase or signup on the advertiser's site, a Floodlight tag (SA360's conversion tracking definition) fires and a conversion event lands in the `conversion` table.

A conversion is rarely the product of a single click. A user might first see a Display ad (first touch), search a brand term a few days later and click in (mid-funnel touch), and finally go directly to the URL to purchase (last touch). Attribution answers: how should the credit for this conversion be allocated across the touchpoints along the way? For every touchpoint (the `attribution_path` table), this dataset stores credit under all six attribution models:

- Last Click: 100% of the credit to the last touchpoint.
- First Click: 100% of the credit to the first touchpoint.
- Linear: every touchpoint splits the credit evenly — N touchpoints, each gets 1/N.
- Time Decay: touchpoints closer to the conversion get more credit, decaying geometrically.
- Position Based: first and last each get 40%, middle touchpoints split the remaining 20%. With only two touchpoints, it degenerates to 50/50.
- Data Driven: in this dataset, this is simulated with a normalized random value — not real DDA output — provided only so learners can write six-model comparison queries.

Every touchpoint is also constrained to the advertiser's own account subtree (no cross-advertiser touchpoints) and must fall inside the lookback window before the conversion. Path lengths skew short: about 40% of conversions have only two touchpoints, and long paths (5 to 6 touchpoints) are rare, which matches real attribution data.

### A Common Trap: Two Different "Conversion" Counts

The word "conversion" shows up at two completely different scales in this dataset, and they absolutely cannot be added or compared row-by-row. `daily_stats.conversions` is the engine's day-aggregated conversion count (the number that shows up on the reporting screen), and across 165,000 rows it adds up to the millions. The `conversion` table is the Floodlight event log: only 5,000 individual events, each with an explicit value and timestamp, used for path analysis and attribution. When you're asked "how many conversions in total," you have to pick one definition and stick with it.

---

## 8. Glossary

The English terms used across the data and the queries are spelled out below. Each entry gives the term, a plain-English explanation, and why it matters in this project. Acronyms are expanded the first time they appear.

**CPC (Cost Per Click).** What the advertiser pays for a single click. This is the billing unit of paid search — all spend ultimately rolls up from click counts multiplied by CPC.

**CPA (Cost Per Acquisition).** How much it cost to get one conversion (purchase, signup, etc.), equal to total spend divided by total conversions. The advertiser's number-one efficiency metric — a CPA that spikes triggers intervention.

**ROAS (Return On Ad Spend).** How much conversion value comes back per dollar spent, equal to conversion value divided by spend. The other half of the efficiency picture along with CPA. High-ticket verticals naturally post higher ROAS.

**CTR (Click-Through Rate).** Clicks divided by impressions. Measures how compelling the creative and keyword relevance are. Typical paid-search CTR runs from 1% to 6%.

**Impression Share (IS).** Actual impressions divided by total eligible impressions. Answers "how much of the opportunity did I get" and is the core diagnostic for whether bids and budgets are dialed in.

**Lost IS Budget / Lost IS Rank.** The two reasons the lost portion of impression share got away: budget ran out or bid/rank wasn't competitive. The breakdown decides whether throwing money at the problem will help.

**Quality Score (QS).** The 1-to-10 score the engine gives a keyword, combining expected CTR, ad relevance, and landing page experience. A higher score buys a lower actual CPC and is one of the most important keyword-optimization levers.

**Match Type.** How loose the keyword's trigger is. Exact, Phrase, or Broad. Looser matching covers more queries but pulls in more irrelevant ones.

**Bid Strategy.** The rule that decides how much to bid in each auction. Manual options include Manual CPC and Enhanced CPC. Automated options (Smart Bidding) include Target CPA, Target ROAS, Maximize Conversions, Maximize Conversion Value, Maximize Clicks, and Target Impression Share.

**Smart Bidding.** Engine-side machine-learning bidding that hits a target (e.g., Target CPA) automatically. The analyst's job becomes auditing the algorithm rather than tuning bids by hand.

**SA360 (Search Ads 360).** Google's enterprise cross-engine campaign management platform — the layer this dataset models.

**Floodlight Tag.** SA360's conversion-tracking definition. Fires when the user completes a target action and produces a conversion event. Each tag declares which attribution model the advertiser uses in production.

**Attribution Model.** The rule for distributing one conversion's credit across its touchpoints. This dataset stores six: Last Click, First Click, Linear, Time Decay, Position Based, and Data Driven.

**Lookback Window.** How many days back from the conversion a touchpoint is allowed to come from — in this dataset, one of 7, 14, 30, 60, or 90. Touchpoints can't predate the window.

**Touchpoint.** A single advertising contact (impression, click, or view) on the user's path to conversion. The touchpoints of one conversion are ordered in time, with `touchpoint_order=1` being the earliest first touch.

**Conversion.** A valuable action the user completes. Note that in this dataset the engine's day-aggregated count and the Floodlight event count differ by orders of magnitude and must not be mixed.

**Negative Keyword.** A search term the advertiser actively excludes from matching. This dataset doesn't build a separate negative-keyword table — historical exclusions are reflected in search-term rows where `added_excluded = 'Excluded'`.

**Broad-Match Overflow.** The engine served a query that doesn't match back to any stored keyword. Shows up as a search-term row with NULL `keyword_id`. About 15% of rows; an excessive rate means match types are too loose.

**Pacing.** The actual daily spend as a percentage of the daily budget. Over 100% means overspending; well below means budget-constrained or under-delivered.

**Budget Delivery.** How the daily budget is consumed over time — Standard (even pacing across the day) or Accelerated (spend as fast as possible).

**LTV (Lifetime Value).** The total value a customer generates over time. It's the ceiling that decides how much an advertiser can afford to pay per click.

**IAB (Interactive Advertising Bureau).** An ad-industry standards body. The industry taxonomy in this dataset follows its style (ten classes: retail, travel, finance, etc.).

**Engine.** The search platform where ads run. In this dataset, Google Ads and Microsoft Advertising.

---

## 9. Key Metrics and Formulas

The formulas the queries will compute are written out below in plain notation. Whenever a denominator could be zero in an aggregate, guard with `NULLIF`.

The efficiency metrics, used everywhere:

```
CTR             = clicks / impressions
avg CPC         = cost / clicks
conversion rate = conversions / clicks
CPA             = SUM(cost) / NULLIF(SUM(conversions), 0)
ROAS            = SUM(conversion_value) / NULLIF(SUM(cost), 0)
```

The impression-share group describes how much opportunity was won, how much was lost, and where it was lost:

```
impression_share + lost_is_budget + lost_is_rank ≈ 100
search_abs_top_is ≤ search_top_is ≤ impression_share
weighted impression share = SUM(impression_share × impressions) / SUM(impressions)
```

That last line is critical: impression share is an impression-weighted metric, and aggregating it across days or devices using `AVG(impression_share)` is wrong — it would treat a low-volume desktop slice the same as a high-volume mobile day.

Budget pacing:

```
pacing %        = AVG(day_cost) / NULLIF(AVG(daily_budget), 0) × 100
monthly_budget  = daily_budget × 30   (derived column, identity)
```

When you need the effective budget for a given day, take the row from `campaign_budget` with the most recent `effective_date ≤ report_date`. Don't naively join `campaign_budget` — a campaign with multiple budget versions will double-count.

The attribution group is the project's centerpiece. For every touchpoint, the six-model credit assignment is summarized below. Across all models, the per-conversion credits sum to 1:

```
last_click_credit  = 1 to the last touch, 0 elsewhere
first_click_credit = 1 to the first touch, 0 elsewhere
linear_credit      = 1 / N         (N = path length)
time_decay_credit  = 2^i / Σ 2^j   (touchpoints closer to the conversion weighted more)
position_credit    = first and last each 0.4, middle touches split 0.2; N=2 degenerates to 0.5 each
data_driven_credit = normalized random value (simulation only, not real DDA)
```

A channel's value under a given attribution model is the model's credit weighted by conversion amount and summed:

```
channel value (model) = SUM(model credit × conversion_value)   grouped by channel
```

The waste-cleanup and coverage group:

```
overflow %  = COUNT(keyword_id IS NULL) / COUNT(*) × 100        (grouped by ad group)
coverage %  = COUNT(keywords with search-term rows) / COUNT(Enabled keywords) × 100   (grouped by industry)
```

Agency revenue:

```
agency fee  = fee_percentage × managed spend
```

One last definitional rule of thumb to keep downstream SQL from contradicting itself. As noted earlier, "number of conversions" has two sources in this dataset: `daily_stats.conversions` (engine day-aggregated, in the millions) and the `conversion` table (Floodlight events, 5,000 rows). Any single query must pick one and stick with it — the two scales are different and cannot be added or compared row-by-row. Path-length, attribution-credit, and conversion-latency analyses use the `conversion` table. Spend-efficiency, CPA, and ROAS reports use `daily_stats`.
