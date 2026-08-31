# Search Ads 360 Intelligent Analytics Agent - Business Context

> **Dataset:** `search_ads_360_agent_large`
> **Complexity:** Large (21 tables, ~1,000,000 rows)
> **Reference Date (REFERENCE_DATE):** `2026-06-01`
> **Data Documentation:** For table structure, fields, DDL, and generation rules, see `02-search_ads_360_agent_large_er_document.md`; for SQL examples, see `03-search_ads_360_agent_large_sql_queries.md`.

This document is the "business handbook" for the entire dataset. The schema, the generated data, and all SQL queries exist to serve the company and the business problems described here. If this is your first time looking at the dataset, read this document first, then move on to the ER document and SQL queries — those two assume you already understand the company, the industry, and the terminology covered here.

Reader persona: a sharp new intern who just joined the project but has no background in search advertising. After reading this, you should be able to follow along at your first standup.

---

## 1. Company: Lumenly Ads

**Lumenly Ads** is a fictional **cross-engine search ads management platform**, headquartered in New York with operations across major US metros. It competes directly with mature third-party ad management systems like **Google Search Ads 360** and **Meta Ads Manager**.

In one sentence: **Advertisers run ads simultaneously on Google, Bing, Yahoo, DuckDuckGo, and other search engines. Each engine has its own console, which gets messy fast. Lumenly Ads consolidates all those accounts into a single back office so advertisers (or the agencies managing them) can configure campaigns, set bid strategies, manage budgets, and review conversion reports from one place.**

Company scale (orders of magnitude):

- **Customers (advertiser):** ~150 direct advertisers.
- **Agencies (agency):** ~25 third-party agencies that manage some advertisers on their behalf.
- **Managed ad accounts (engine_account):** ~300, spanning 4 search engines.
- **Managed campaigns:** ~1,550, with ~8,000 ad groups and ~80,000 keywords beneath them.
- **Performance data on the platform:** ~400K rows/day of Campaign × Device daily reports, 25K conversion events, ~180K rows of search term reports.

Organizational roles (the queries in this dataset reference the following job titles):

- Advertiser side: **Marketing Director / CMO**, **Performance Marketing Manager**, **Campaign Manager**, **Search Specialist (SEM)**, **Trading Desk / Bid Manager**, **Marketing Analytics / RevOps**.
- Lumenly Ads side / agency side: **Account Manager**, **CSM (Customer Success Manager)**, **CFO / Finance**.

---

## 2. Business Model

How Lumenly Ads makes money: **It charges a platform service fee (take-rate) on the customer's monthly ad spend**, typically **8%–20%**. The more a customer spends, the more Lumenly earns. Annual revenue comes mostly from **Mid-Market** and **Enterprise** customers, since their monthly spend dwarfs that of **SMB** customers.

Customers are split into three tiers (advertiser tier), each with very different spend levels and service models:

| Tier | Monthly Spend Range (USD) | Representative Industries | Service Model |
|------|---------------------------|---------------------------|---------------|
| **SMB** | < $1.5K | Local services, small-scale education and training | Self-serve + online support |
| **Mid-Market** | $1.5K – $30K | E-commerce retail, healthcare, automotive | Account Manager led, agency optional |
| **Enterprise** | > $30K | Financial services, real estate / home goods, B2B enterprise services | Agency mandatory, dedicated large-account manager + Quarterly Business Review (QBR) |

The unit economics intuition: Lumenly doesn't buy media itself; it's the "management layer." Revenue = customer ad spend × take rate. So the company's health rests on two things — **whether customers spend a lot (spend scale)** and **whether that spend pays off (ROAS high enough, no churn)**. If a customer's campaigns are run poorly and ROAS sits below 2x for too long, the customer churns and Lumenly's service fee revenue evaporates with them. That's why "helping the customer run good ads" is both the product's value proposition and Lumenly's own livelihood.

About **80%** of advertisers are agency-managed; the remaining **20%** are direct. Agencies layer their own fee on top of customer spend (agency_client.fee_percentage, 8%–20%). That fee shows up in the data but is not Lumenly's revenue.

---

## 3. Industry Overview: Search Advertising and Third-Party Management Platforms

If you're coming from another industry, this section gives you a mental model of what "search advertising" is as a business.

**What is search advertising?** When a user types a query into a search engine (say, "GMAT tutoring"), the few results at the top of the search results page marked "Ad" are search advertisements. Advertisers **bid** on those slots and pay **per click (CPC, cost per click)** — each click costs the advertiser money. Whoever combines a high bid with high-quality ads ranks at the top. This is a real-time auction market, and every single search is a mini-auction.

**Who are the players?**

1. **Search engines (the supply side):** They provide ad slots on the results page and earn revenue per click. In this dataset's market, the dominant engines are Google and Bing, with Yahoo and DuckDuckGo making up the rest (this dataset's 4 engines have roughly Google 40% / Bing 35% / Yahoo 15% / DuckDuckGo 10% share).
2. **Advertisers (the demand side):** Businesses that want to acquire customers, sell products, or capture leads through search ads.
3. **Agencies:** Specialized teams that run campaigns on behalf of advertisers and earn a percentage of spend.
4. **Third-party management platforms (like Lumenly Ads):** They consolidate multi-engine accounts into a single back office and provide unified campaign configuration, automated bidding, and cross-channel attribution. Lumenly belongs in this bucket.

**Regulation and compliance.** Ad placement is governed by FTC truth-in-advertising rules (no unsubstantiated superlatives, healthcare and financial ads need extra scrutiny); user data collection and conversion tracking are governed by privacy laws like CCPA and GDPR (for EU traffic). That's why a floodlight tag's (conversion tracking pixel's) lookback window and counting method need to be documented properly.

**Current macro trends.** The whole industry is shifting from **manual bidding** to **automated / smart bidding** — letting algorithms adjust bids in real time toward a conversion goal. Meanwhile, **privacy tightening** is making cross-device, cross-site user tracking harder, which is why **multi-touch attribution** has become a critical tool for measuring true channel contribution. Lumenly Ads' data model (automated bidding flags, all 6 attribution models in one table, full device-dimension coverage) was built to support both trends.

---

## 4. Project Context: Who You Are and What You're Doing

**Your role:** You are a **Marketing Analytics analyst (data analyst / BI analyst)** on Lumenly Ads' data team, serving both the platform's advertisers and the internal Account Manager team.

**Who consumes your output:** both humans and machines.

- For **human colleagues**: the Performance Manager needs a weekly performance review, the Bid Manager wants a bid-strategy comparison, the SEM Specialist wants a list of negative-keyword/add-keyword candidates, and the CMO wants a monthly marketing P&L.
- For **LLM Agents**: the optimization rules and anomaly patterns you discover manually (e.g., "pause any keyword with Quality Score < 5 and 7-day spend > $15") eventually get codified into Text-to-SQL agents and operational automation agents that run daily in production. In other words, **this dataset is a two-layer training environment: human analysts explore first, then hand the rules off to Agents to run**.

**Why now.** The platform has just finished consolidating multi-engine data and accumulated a full window of performance data (see Section 6). Leadership wants to answer the specific business questions below using this data, then automate the repeatable pieces with Agents.

---

## 5. Business Problems to Solve

The 6 problems below form the spine of the entire dataset. Every table in the ER document was designed to support them, and every SQL query was written to answer them. Each SQL query traces back to at least one of these problems.

- **Q1 Budget Gap Identification:** Which campaigns are losing impression opportunities because they're **budget-constrained** (`lost_is_budget` running high)? If we add budget, can we directly convert that into more impressions and conversions? This is the platform's core lever for getting customers to "spend more."
- **Q2 Bid Strategy Efficacy:** Does **automated bidding** actually beat **manual bidding**? For campaigns that set a Target CPA / Target ROAS, what is the actual attainment (actual vs target)? Which ones should switch strategies?
- **Q3 Keyword Quality Diagnostics:** Which keywords have **low Quality Score but high spend** (burning money)? Which keywords look fine on all three quality sub-dimensions but still get a low QS (data inconsistency, worth manual review)? Low QS pushes CPC up and eats directly into margin.
- **Q4 Search Term Mining:** Among the actual searches users typed, which ones **spent money but had zero conversions** (should be added as negative keywords to stop the bleeding)? Which ones **converted well but haven't been promoted to formal keywords** (should be added to scale up)? This is the most routine SEM optimization and the one most likely to produce immediate ROI.
- **Q5 Multi-Touch Attribution Analysis:** For a single conversion, how differently is the credit distributed across the six attribution models — **last click**, **first click**, **linear**, **time decay**, **position**, **data-driven**? A branded-keyword channel might look highly valuable under last-click attribution; would it "show its true colors" under first-click?
- **Q6 Account & Customer Portfolio Health:** Which advertisers are at high renewal risk (contracts about to expire, spend declining)? How concentrated is customer spend (how much of revenue comes from the top 10 customers)? What's the trend in agency-driven service fee revenue? These all matter for Lumenly's own business.

---

## 6. Data Scope Overview

- **Historical baseline:** 18 months (2024-12-08 → 2026-06-01), covering advertiser onboarding, account buildout, strategy setup, and the gradual formation of the organizational structure.
- **Performance data (daily_stats):** The most recent **120 days** of Campaign × Device daily reports. Each campaign's report dates are clipped to its actual active window, so not every campaign has a full 120 days.
- **Search term data (search_term_report):** The most recent **30 days**, with the quota spread evenly across each Enabled keyword. The full-corpus search terms are therefore highly long-tail with lots of unique entries.
- **Conversions and attribution:** The most recent **90 days** of conversion events, each with 2–6 touchpoints (~4 on average), covering the full pre-conversion path.
- **Status retention:** Campaigns in all three states — Enabled / Paused / Removed — are retained so analysts can do "post-mortems on paused campaigns."

**This is a frozen snapshot.** The last day of the data is `2026-06-01`. All SQL queries should treat that day as "today" and use literal `DATE('2026-06-01', ...)` for time filtering. **Never use `DATE('now')`** — the real current date is already past the data's end, so `'now'` will push the time window entirely past the data and return empty results.

In plain numbers: a few hundred advertisers, a thousand-plus campaigns, eighty thousand keywords, all supporting roughly a million rows of performance and conversion detail. See the file inventory in the ER document for the exact row count per table.

---

## 7. Industry Primer (30 Minutes Before You Touch the Data)

This section is the background a non-specialist needs before reading the data.

### 7.1 How a Single Search Ad Actually Runs (Account Hierarchy)

A search ad's configuration is a five-level tree, from coarse to fine:

1. **engine_account:** The account an advertiser opens under a specific search engine. One advertiser can have separate accounts on Google and Bing.
2. **campaign:** The top-level unit of investment, tied to one engine account, one bid strategy, and one budget. For example, "E-commerce Retail_Branded Terms_Desktop."
3. **ad_group:** A group within a campaign that bundles thematically related keywords and ad copy together.
4. **keyword:** The finest investment unit. You bid on the term "GMAT tutoring" and your ad only has a chance to appear when a user searches for it.
5. **text_ad:** The actual headline + description copy shown to users.

### 7.2 How Money Is Spent and How Performance Is Measured (The Core Metric Chain)

Each day, for each campaign, and for each device, the platform records one row of performance data. The metrics form a **causal chain**:

```
impressions → clicks → cost → conversions → conversion_value
            └ CTR     └ CPC   └ conv rate    └ ROAS / CPA
```

- A user sees the ad = one **impression**.
- A user clicks through = one **click**, and the advertiser pays the CPC.
- A fraction of those clicks complete the goal action (place an order, submit a lead) = a **conversion**.
- The value generated by a conversion (order amount, lead value) = **conversion_value**.

From this chain we derive the four most commonly used efficiency metrics: **CTR** (how often users click), **CPC** (how much each click costs), **CPA** (how much each conversion costs), **ROAS** (how many dollars you earn back per dollar spent). Formulas are in Section 9.

### 7.3 Impression Share: How Many of Your Rightful Impressions Did You Actually Get?

In an auction market, your ad doesn't show every time. **Impression share (IS)** = the impressions you actually got ÷ the impressions you were eligible for. The portion you didn't get can only be lost to two causes:

```
impression_share + lost_is_budget + lost_is_rank = 100%
   (what you got)   (lost to budget)  (lost to rank/quality)
```

- **High lost_is_budget** → budget ran out and the ad stopped serving. **Adding budget directly buys back impressions** (this is Q1).
- **High lost_is_rank** → bid too low or quality score too poor; your auction rank is too low. **Either bid up or improve ad quality**.

Decomposing impression share into these three numbers is the most direct way to decide whether a campaign needs "more budget" or "better creative."

### 7.4 Automated Bidding vs Manual Bidding

- **Manual CPC:** A human sets the max CPC for every keyword.
- **Smart Bidding:** You hand the goal to an algorithm (I want Target CPA = $12, or Target ROAS = 4x) and it adjusts bids in real time to hit the target. Common types: Enhanced CPC, Target CPA, Target ROAS, Maximize Conversions / Conversion Value / Clicks, Target Impression Share.

To judge whether a smart bidding strategy is working, look at **attainment**: is the actual CPA below the Target CPA? Did the actual ROAS hit the Target ROAS? (This is Q2.)

### 7.5 Quality Score

Search engines assign every keyword a **Quality Score (QS) on a 1–10 scale**, composed of three sub-dimensions: **expected CTR**, **ad relevance**, and **landing page experience**, each rated Below / Average / Above Average. Higher QS means you can win the same rank at a lower bid — so **low QS = hidden overspend**. That's the heart of Q3: find the keywords with high spend and low QS.

> **A built-in analytical trap in the data:** to keep the dataset simple, the three quality sub-dimensions and the QS are **sampled independently**, so you can run into "all three sub-dimensions Above Average but QS still low" rows that don't add up. This is not a bug; it's a deliberate exercise — in real platforms this kind of inconsistency usually signals a data quality issue, and analysts need to be able to spot it.

### 7.6 Search Term vs Keyword

These two are easy to confuse. A **keyword** is a term you *actively bid on*; a **search term** is what the user *actually typed*. With broad match, you might buy "English tutoring" and the user searches "best English tutoring in NYC" — that latter string is the search term.

The search term report is an SEM goldmine: real-world search terms are heavily long-tail and mostly unique. The mining actions break into two types, tracked by the `added_excluded` field:

- **Added:** this search term performs well; promote it to a formal keyword and scale it up.
- **Excluded:** this search term spent money without converting; add it as a negative keyword to stop the bleeding.
- **None:** nobody has processed it yet — waiting for analysts to mine. These are exactly what Q4 is hunting for.

> **A definitional trap in the data:** the "unprocessed" value of `added_excluded` is the **literal string `'None'`, not SQL NULL**. Filter with `= 'None'`, not `IS NULL`.

### 7.7 Multi-Touch Attribution

A single conversion typically isn't driven by one click — the user touches multiple things (saw a display, clicked social, searched the brand) before completing. **Attribution** is the problem of how to divide the credit for that conversion across the touchpoints on the path. Different models divide it differently:

| Model | How Credit Is Split | Intuition |
|-------|---------------------|-----------|
| **Last Click** | 100% to the final touchpoint | The "closer" matters most |
| **First Click** | 100% to the first touchpoint | The "opener" matters most |
| **Linear** | Equal split across all touchpoints | Everyone contributed |
| **Time Decay** | More weight the closer to conversion | Recency matters more |
| **Position Based** | 40% first, 40% last, 20% to the middle | The ends matter most |
| **Data Driven** | Algorithmic split based on data | Let the data decide |

For the same touchpoint data, the sum of credit across the six models is always exactly 1.0 (each conversion normalizes independently per model). Comparing the six models reveals which channels are "pathfinders" and which are "closers" (this is Q5).

### 7.8 Historicized Budgets (SCD2)

Budgets get adjusted repeatedly. The `campaign_budget` table uses **Slowly Changing Dimension Type 2 (SCD2)** to record every change: each budget row carries an effective interval `[effective_date_start, effective_date_end)`, and the most recent row has end = NULL meaning "still in effect."

> **A JOIN trap in the data:** to query "the budget in effect on a given day," you must match the interval with `effective_date_start <= date AND (effective_date_end IS NULL OR effective_date_end > date)`. Otherwise, the multiple historical budget rows for a single campaign **fan out** and your cost / conversion metrics will be multiplied several times over.

---

## 8. Glossary

Each term gets a plain-English explanation plus a sentence on why it matters here. English terms stay in English.

| Term | Plain English | Why It Matters Here |
|------|---------------|---------------------|
| **CPC** (Cost Per Click) | What the advertiser pays per click | The billing unit of search ads; CPC × clicks = cost |
| **CTR** (Click-Through Rate) | Clicks ÷ impressions; how compelling the ad is | Measures creative and keyword relevance; dataset average ~3.5% |
| **CPA** (Cost Per Acquisition) | What you pay to win one conversion | Investment efficiency; Q2's attainment is actual CPA vs Target CPA |
| **ROAS** (Return On Ad Spend) | Dollars earned in conversion value per dollar of ad spend | The most critical profitability metric; dataset average ~3.3x, <2x is a loss |
| **Conversion** | A user completes the goal action (order/lead/signup) | The end goal of the campaign; the unit of attribution |
| **Conversion Value** | The value generated by one conversion (order amount, lead value estimate) | The numerator of ROAS; purchase events high, lead events low |
| **Impression Share** (IS) | Actual impressions ÷ eligible impressions | Measures "how many impressions you didn't get," split into budget/rank losses |
| **Lost IS (Budget)** | Impression share lost to insufficient budget | Q1's core signal; >20% means add budget |
| **Lost IS (Rank)** | Impression share lost to low bid / poor quality | >30% means bid up or improve creative |
| **Quality Score** (QS) | A keyword's 1–10 quality rating | Low QS drives up CPC; Q3's core |
| **Keyword** | A term the advertiser actively bids on | The finest investment unit |
| **Search Term** | The exact string the user typed | Not necessarily equal to the keyword; Q4 hunts here |
| **Match Type** | How wide a keyword matches: EXACT / PHRASE / BROAD | The wider, the longer-tail and noisier the triggered search terms |
| **Negative Keyword** | A keyword that excludes unwanted search terms | Q4's "stop the bleeding" action |
| **Bid Strategy** | The bidding strategy: manual or automated | Q2's subject |
| **Target CPA / Target ROAS** | The targets a smart bidding strategy tries to hit | Attainment = actual value vs target value |
| **Impression Share %** (Target IS) | A strategy targeting "win X% of impression share" | The parameter for the Target Impression Share strategy |
| **Campaign / Ad Group / Keyword** | The three-level investment tree | Account structure |
| **Engine Account** | An advertiser's account under a specific search engine | The entry point for multi-engine aggregation |
| **Floodlight Tag** | The conversion tracking pixel in Search Ads 360 | Determines a conversion's type and lookback |
| **Lookback Window** | The conversion lookback window (7/14/30/60/90 days) | How far back a touchpoint still counts |
| **Attribution Model** | The model that decides how credit is split | The six models compared in Q5 |
| **Touchpoint** | A single contact along the conversion path (click/impression/view) | The atomic unit for attribution |
| **Assisted Conversion** | A conversion the touchpoint helped but didn't close | Measures the hidden contribution of upstream channels |
| **Take-Rate** | The platform/agency's percentage cut on spend | Lumenly's and the agencies' revenue source |
| **Advertiser Tier** | Customer segmentation: SMB / Mid-Market / Enterprise | Determines service model and spend scale |
| **SCD2** (Slowly Changing Dimension Type 2) | Records field history using effective intervals | How `campaign_budget` is historicized |
| **Reconciled Field** | A parent-table field backfilled from child-table aggregates | E.g., lifetime_cost, used for Agent self-validation |
| **Polymorphic Association** | A foreign key that points to different tables based on a type | E.g., daily_stats.entity_type/entity_id |
| **QBR** (Quarterly Business Review) | Quarterly business review | The service cadence for Enterprise customers |

---

## 9. Key Metric Formulas

The formulas below are the **canonical definitions** for every core metric in the dataset. Aggregates in the SQL queries should match these; if two places disagree, this section wins. When aggregating, always `SUM` first and then divide (sum the numerator and denominator first, then take the ratio) to avoid the bias from averaging per-row ratios.

### 9.1 Performance Metrics (Source: daily_stats)

```
CTR  (Click-Through Rate)      = SUM(clicks) / SUM(impressions)
Avg CPC (Average Cost Per Click) = SUM(cost) / SUM(clicks)
Conv Rate (Conversion Rate)    = SUM(conversions) / SUM(clicks)
CPA  (Cost Per Acquisition)    = SUM(cost) / SUM(conversions)   -- NULL when conversions=0
ROAS (Return On Ad Spend)      = SUM(conversion_value) / SUM(cost)
```

### 9.2 Impression Share Metrics (Source: daily_stats)

```
Impression Share = AVG(impression_share)
Lost IS Budget   = AVG(lost_is_budget)      -- threshold > 20% → budget-constrained, add budget
Lost IS Rank     = AVG(lost_is_rank)        -- threshold > 30% → rank/quality short, bid up or improve creative
Identity: impression_share + lost_is_budget + lost_is_rank = 100   (true for every row)
```

### 9.3 Bid and Budget Metrics

```
Target CPA Attainment  = actual_cpa / target_cpa - 1      -- negative = better than target
Target ROAS Attainment = actual_roas / target_roas - 1    -- positive = better than target
Budget Utilization     = avg_daily_spend / daily_budget   -- budget utilization rate
Automated Bid %        = COUNT(automated bid campaign) / COUNT(all campaigns)
```

> **Definition of budget utilization:** `avg_daily_spend` uses the budget row **in effect** on the reference date (matched via the SCD2 interval), and then divides the last 7 days of spend by the number of active days to get average daily spend. Normal campaigns land in 55%–95%; budget-constrained campaigns will exceed 100%.

### 9.4 Keyword Metrics (Source: keyword)

```
Avg Quality Score   = AVG(quality_score) WHERE status='Enabled'
Low QS Keyword %    = COUNT(quality_score < 6) / COUNT(*)
CPC Gap to Top      = max_cpc - top_of_page_cpc     -- distance to the top-of-page bid
```

### 9.5 Search Term Metrics (Source: search_term_report)

```
Search Term Conv Rate   = SUM(conversions) / SUM(clicks)   GROUP BY search_term
Negative Keyword Candidate = cost > 50 AND conversions = 0 AND added_excluded = 'None'
High Value Term Candidate  = conversions > 0 AND added_excluded = 'None'
```

### 9.6 Attribution Metrics (Source: attribution_path × conversion)

```
{model} Touch Value = SUM({model}_credit * conversion.conversion_value)   GROUP BY channel/dimension
  where {model} ∈ {last_click, first_click, linear, time_decay, position, data_driven}
Avg Path Length     = AVG( MAX(touchpoint_order) GROUP BY conversion_id )   -- average touchpoints ~4
Time to Conversion  = AVG(hours_before_conv) WHERE touchpoint_order = 1     -- first touch to conversion duration
```

### 9.7 Account Health Metrics (Source: advertiser × agency_client × daily_stats)

```
Active Advertiser Count = COUNT WHERE account_status = 'Active'
Customer Concentration  = SUM(Top 10 customers' spend) / SUM(all spend)
Agency Fee Revenue      = SUM(advertiser spend * agency_client.fee_percentage / 100)
Contract Expiring 30d   = COUNT WHERE contract_end BETWEEN '2026-06-01' AND '2026-07-01'
```

---

> **Next step:** Once you understand the company, the industry, and the metrics, go read `02-search_ads_360_agent_large_er_document.md` to learn how the data is organized, then use `03-search_ads_360_agent_large_sql_queries.md` to start running queries yourself.
