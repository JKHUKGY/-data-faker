# VerdantBox Ecommerce Subscription Growth Marketing — Business Context

This file is the business context for the `ecommerce_subscription_growth_marketing_high` dataset, and it is the main entry point into the whole dataset. The schema, the SQL queries, and the distribution biases deliberately baked into the data all exist to serve the company and the project described here. Read this document once and you will walk into your first standup knowing the company, the industry, the project, the questions to answer, and the wall of marketing jargon you will be reading.

The dataset is written in English, and the business itself is set in North America. The company is North American, the currency is USD, the customers are in the United States and Canada, and the regulators are U.S. and Canadian. Business terms are kept in their standard industry form (e.g., ROAS, AOV, CAC, LTV), and Section 8 explains each one in plain English.

---

## 1. Company Snapshot

VerdantBox is a fictional North American direct-to-consumer (DTC) subscription health-food platform, headquartered in Seattle. The company sells organic, plant-based, and functional health foods to customers in the United States and Canada, shipping a curated mix of shelf-stable goods, snacks, beverages, supplements, frozen meals, and refrigerated essentials straight to consumers' doors, bypassing traditional grocery shelves.

The company is a mid-stage growth DTC brand (order of magnitude, not exact figures): roughly 200 employees, annual revenue in the $60M–$80M range, and active customers in the low six figures. Customers can place a one-time purchase or subscribe to the paid **VerdantBox+** membership, which gives them free shipping, member pricing, and limited-run curated boxes.

The org structure relevant to this dataset looks like this. On the marketing side, the top of the org chart is the CMO (Chief Marketing Officer), with a VP of Growth Marketing reporting in, and underneath that VP sits the Growth Marketing team, which is split into acquisition, lifecycle, creative, and analytics pods. On the finance side, the CFO leads an FP&A (Financial Planning and Analysis) team whose job is to make sure every marketing dollar spent actually pays back. The Executive, Manager, Analyst, Operations, and Finance roles you will see later in the SQL queries all map to real seats in this org.

---

## 2. Business Model and Unit Economics

VerdantBox makes money in two ways. The first is product retail: for every order a customer places, the company earns the gross margin between the sticker price and the wholesale cost. In the health-food category, list prices typically land between $5 and $50 per item, and wholesale cost runs about 35% to 55% of list, so item-level gross margins sit in the 45%–65% range. The second is membership subscriptions: VerdantBox+ members pay a monthly or annual fee in exchange for free shipping, member pricing, and exclusive curated boxes.

Membership is the leverage point of the whole business model. On the surface, members buy at the member price and get free shipping, which means the company gives up a chunk of margin on each member order. But members come with two compensating behaviors. First, members carry bigger baskets: a typical member order contains 3 to 6 items, versus 1 to 3 for non-members, which means member AOV (Average Order Value) is meaningfully higher. Second, members reorder more often and stick around longer, so member LTV (Lifetime Value) is far above non-member LTV. That is why the company is willing to spend on membership conversion — pulling customers into VerdantBox+ via a first order or free trial, then earning back the margin given up through repeat purchases.

VerdantBox+ comes in two tiers: Plus and Plus Premium. Each tier has a monthly and an annual billing option, and the annual plan works out cheaper per month (to encourage longer lock-in). New users enter a 30-day free trial first, and roughly 62% convert to paid when the trial ends (trial-to-paid conversion). This loop of "trial to paid to renewal" is the core engine of a subscription business.

Marketing spend is the company's third-largest cost line (behind COGS and fulfillment), which is why "return on each marketing dollar" is a number the CMO and CFO look at every single month. The whole point of this dataset is to quantify that.

---

## 3. Industry Primer

DTC subscription ecommerce takes products that historically lived on a grocery shelf and turns them into an "online curation, subscription reorder, doorstep delivery" experience. The value proposition has three layers: curation (helping the customer pick winners out of thousands of SKUs), convenience (the subscription reorders automatically, no need to repeat the purchase decision), and identity (labels like organic, plant-based, and clean-label are themselves part of why people buy). Health food as a niche piggybacks on the broader "wellness premiumization" trend, which pushes order values and repeat rates above typical CPG levels.

The players in this market roughly split into four buckets (described in generic terms, no real company names): DTC subscription-box brands (like VerdantBox — owned brand, owned membership), large general ecommerce platforms (sell everything to everyone), traditional brick-and-mortar grocers (offline-first, online as an add-on), and vertical health-food retailers (specialty stores for supplements or organic groceries). VerdantBox sits in the first bucket and differentiates against the giants' "cheap and broad" play through brand, membership stickiness, and curation.

On regulation and compliance, North American health-food DTC has to juggle several overlapping frameworks. Food labeling and dietary supplements are regulated by the FDA (Food and Drug Administration), with supplements specifically governed by DSHEA; organic certification runs through USDA Organic; advertising claims and subscription auto-renewal fall under the FTC (Federal Trade Commission), and the FTC's recent "click-to-cancel" rule and the ROSCA statute directly affect how subscription cancellation flows have to be designed; email marketing is governed by CAN-SPAM, SMS marketing by TCPA, California customer privacy by CCPA. On the Canadian side, email and SMS fall under CASL (Canada's Anti-Spam Law), and food safety is handled by CFIA and Health Canada.

A few macro forces are shaping the industry right now and are worth keeping in mind. First, acquisition keeps getting more expensive: Apple's iOS ATT (App Tracking Transparency) and the broader privacy crackdown have made paid-social targeting and attribution harder, and CAC has risen across the board. Second, retail media and AI-driven personalization are reshaping how brands deploy spend. Third, "subscription fatigue" is real: consumers are subscribed to too many things, so retention and reactivation have become more cost-effective sources of growth than pure new-customer acquisition. Together, these forces push a company like VerdantBox to wring efficiency out of every marketing dollar — and getting efficient starts with having the data right.

---

## 4. Your Role and the Project

You are a **data analyst on the Growth Marketing team at VerdantBox** (full-time, BI-leaning). You report directly into the VP of Growth Marketing, and you also supply numbers to the CMO's Monthly Business Review (MBR) and to the FP&A team under the CFO.

The project on your plate is to take roughly the last 18 months of marketing and customer activity and turn it into a queryable analytics base that supports two recurring deliverables: a monthly MBR deck for the CMO, and a quarterly budget-reallocation memo for the CFO. The marketing team is simultaneously running three different objective types, and your analysis has to answer both "how did the spend pay back so far" and "where should we tilt the budget next quarter."

Three campaign objectives run through everything that follows:

- **ACQUISITION**. Pull net-new customers in via paid social, paid search, and affiliate/referral.
- **MEMBERSHIP_CONVERSION**. Upgrade one-time buyers or trial users to paid VerdantBox+ membership.
- **REACTIVATION**. Win back dormant and churned customers.

Your output is not "run the numbers and stop." It is actionable conclusions: which channels to scale up, which campaigns to kill, which audience to target with the next reactivation push. The business questions in Section 5 are the core list this project has to answer.

---

## 5. Business Questions to Solve

The whole dataset is built around five concrete business questions. Every SQL query traces back to at least one of them.

1. **Marketing-mix P&L and budget reallocation.** Across the three objectives (acquisition, conversion, reactivation), how much did we spend, how much attributed revenue did we earn, and what was the ROAS on each? Where should next quarter's budget tilt — which objective, which campaigns? This is the signature question that gives the project its name.
2. **Channel efficiency (Channel ROAS).** Which channels return the most revenue per dollar spent? Which to scale, which to pause? Since attribution is at the campaign level (not the channel level), how do we use spend-share weighting to fairly allocate revenue down to channels?
3. **Membership economics.** What is a VerdantBox+ member actually worth? How big is the AOV / repeat-rate / LTV gap between members and non-members, and is it big enough to justify the membership-conversion budget?
4. **Funnel diagnostics.** From sent → delivered → engaged → clicked → converted, where is the biggest drop-off? Which funnel step should the next round of optimization target?
5. **Retention and reactivation.** What do the retention curves look like for each signup cohort? Is trial-to-paid conversion getting better or worse? Which "dormant but high-value" customers and segments should the next reactivation campaign target?

---

## 6. Data Scope Overview

The dataset is anchored to a fixed "today": **REFERENCE_DATE = 2026-06-01**. Anything that means "current," "to date," or "days remaining" is computed against this date, and that exact date constant shows up in the generator and in every SQL query (instead of `DATE('now')`), so results are fully reproducible.

The time window is roughly 18 months of historical activity, plus three campaign-status tenses: COMPLETED (~70%), ACTIVE (~20%, concentrated in the last 30 days), and PLANNED (~10%, falling in the next 30 days, with target segments defined but no real performance data yet). This past + present + future mix lets the dataset support both retrospective analysis and a forward-looking view of in-flight campaigns.

In rough terms, the data volume is "about a thousand customers, five hundred SKUs, fifty campaigns, plus tens of thousands of touchpoints, orders, and responses." Customers are roughly 88% U.S. and 12% Canada by geography. Exact tables, columns, and row counts are in the ER document `02-ecommerce_subscription_growth_marketing_high_er_document.md` — not repeated here.

One deliberate scoping decision worth flagging: this is a **sampled** dataset, not a production-scale dump. Marketing touchpoints (`marketing_touchpoint`) are capped at a sample window of about a thousand rows, and campaign budgets are scaled down accordingly to the hundreds-to-thousands-of-dollars range, so that "spend per campaign" roughly ties to "sum of cost across the touchpoints in this sample." That keeps ROAS, CAC, and other ratios inside believable industry ranges. In other words, absolute dollar amounts are shrunk, but ratios and distributions are realistic.

---

## 7. Industry Background You Need

This section is the 30-to-60 minutes of background a non-marketer needs before the data makes sense. After reading it, you will be able to keep up with the marketing team.

**The growth-marketing lifecycle funnel.** A customer goes from stranger to loyal member through acquisition, activation (first order completed), retention (continued repeat purchase), and reactivation (won back after churning). The three campaign objectives map neatly to different points on this chain: ACQUISITION handles the front end (new customers), MEMBERSHIP_CONVERSION sits in the middle (upgrade buyers into members), and REACTIVATION covers the back end (rescue customers who dropped off). The current stage of any individual customer is captured by the `lifecycle_stage` field, with values new, active, at_risk, dormant, and churned.

**Marketing attribution.** Which campaign should get credit for a given order's revenue? That is the question attribution answers. This dataset uses **last-touch attribution**: take the most recent click or convert touchpoint for that customer within the 60 days before the order, and assign the order to the campaign behind that touchpoint. If no real touchpoint chain can be found, the model falls back to "random assignment within the date window." One more important point: attribution happens at the **campaign** level, not the channel level. When a single campaign runs on both Meta and Google, the order's revenue has to be split across channels via spend-share weighting (see Section 9). Attribution window, last-touch, and spend-share weighting all come up repeatedly in the SQL queries.

**Channel taxonomy (owned / paid / earned).** Marketing channels split into three buckets based on "who owns it, who pays for it." Owned channels are reach the company controls directly — email, push, SMS, in-app — and they have near-zero variable cost. Paid channels are where you buy attention — Paid Social (Meta, TikTok), Google Ads, YouTube, Affiliate. Earned channels grow through word-of-mouth — Referral. Each channel has a characteristic CPM (cost per mille) and CTR (click-through rate); owned channels have very low CPM and paid channels have high CPM, and that gap directly drives how channels rank on ROAS.

**The membership-subscription engine.** The core of a subscription business is a status chain: trial → active (converted to paid) / trial_ended (didn't convert) → cancelled (churned out of paid). New users enter a 30-day free trial, and about 62% convert to paid when the trial ends. After conversion, some share will eventually churn out. Bucketing trials by start quarter and tracking trial-to-paid by cohort is how you tell whether the membership engine is getting healthier or sicker over time.

**Cohort retention analysis.** Group customers who signed up in the same month into a cohort, then track what share of them comes back to place an order in each subsequent month, and you get a retention curve. One common trap to flag: orders placed in month 0 (the signup month itself) are **activation**, not retention; "retention" only counts month 1 and later. The retention curve is the single most important indicator of product-led growth health.

**Marketing-funnel stages and definitions.** A marketing touchpoint has two stages. Stage one is the delivery result (`delivery_status`): delivered, bounced, or failed. Stage two is the user response (`response_type`), which is a **terminal-state** model: open, click, dismiss, or convert — pick exactly one, mutually exclusive. Key convention: `convert` implies the user already clicked, and `click` implies the user already opened. So when you compute "click and above," click is defined as `IN ('click','convert')`, and "engagement and above" is `IN ('open','click','convert')`. This convention is kept consistent across multiple queries — Section 9 hammers it again.

---

## 8. Glossary

Each term below appears in the ER document or the SQL queries. Industry terms are kept in their standard form, with a plain-English explanation and a note on why it matters in this dataset.

| Term | Plain-English explanation | Why it matters here |
|------|---------------------------|---------------------|
| DTC (Direct-to-Consumer) | A brand selling straight to consumers, no middleman | The basic business shape of VerdantBox |
| SKU (Stock Keeping Unit) | One specific sellable product unit (each flavor × size combo is its own SKU) | Each row in the product table is one SKU |
| AOV (Average Order Value) | Average dollars spent per order | Core metric for the member vs. non-member value gap |
| LTV (Lifetime Value) | Total value a customer contributes over their lifetime with the company | The yardstick for whether acquisition cost is worth it |
| CAC (Customer Acquisition Cost) | Average cost to acquire one new customer | Compared against LTV to judge campaign payback |
| ROAS (Return on Ad Spend) | Revenue earned per dollar of ad spend | The number-one metric for channel and campaign efficiency |
| CPM (Cost Per Mille) | Cost per thousand impressions | Drives the cost structure differences across channels |
| CTR (Click-Through Rate) | Clicks divided by impressions (or sends/delivered) | Measures how compelling a creative or channel is |
| CPL (Cost Per Lead) | Cost to acquire one lead | Common upper-funnel efficiency metric |
| Funnel | The progressive narrowing from impression to conversion | Framework for diagnosing drop-off at each step |
| Attribution | Assigning a revenue event to a specific campaign | Determines how the ROAS numerator gets computed |
| Last-touch attribution | Give full credit to the last valid touchpoint before conversion | The attribution rule used in this dataset |
| Attribution window | The max allowed time between touchpoint and order | Set to 60 days in this dataset |
| Spend-share weighting | Allocate revenue across channels in proportion to each channel's spend on the campaign | Standard way to push campaign-level attribution down to the channel level |
| Cohort | A group of customers who came in during the same time window | The basic grouping unit for retention analysis |
| Retention rate | Share of a cohort returning in a later month | Indicator of product-led growth health |
| Activation | Share of a cohort that placed an order in the signup month itself | Distinct from retention; this is the first step of the funnel |
| Trial-to-paid conversion | Share of free-trial users who become paying members | The single most important metric for the membership engine |
| Churn | A customer stops buying or cancels their subscription | Source population for reactivation campaigns |
| Reactivation / win-back | Bringing churned customers back to active status | One of the three campaign objectives |
| Lifecycle stage | The customer's current activity-level bucket | new / active / at_risk / dormant / churned |
| Segment | A defined group of target customers selected by rule | The basic unit of campaign targeting |
| Member penetration | Share of a group that is currently an active member | Tells you whether a segment is a good upsell target |
| Owned / paid / earned media | The three-way classification of marketing channels | The root cause of cost and ROAS differences across channels |
| Organic | Customers who came in without paid advertising | The NULL / Referral portion of the acquisition channel field |
| Engagement rate | Share of successfully delivered touches that get any engagement | Health indicator for the middle of the funnel |
| Redemption rate | Share of issued promo codes actually used | Tells you whether a promo is working |
| Frequency cap | A limit on how many touchpoints one customer can receive in a window | Prevents fatigue and unsubscribes |
| RFM (Recency, Frequency, Monetary) | Scoring customers by how recently, how often, and how much they bought | Classic methodology for audience segmentation |
| Gross margin | (Price minus cost) divided by price | The profit floor of the retail line of business |
| Budget pacing | % of budget spent vs. % of campaign duration elapsed | Tells you whether a campaign is burning too fast |
| P&L (Profit and Loss) | The income-statement view of revenue minus costs | The overall financial picture of the marketing mix |

---

## 9. Key Metrics and Formulas

Below are the metrics that SQL queries use, or that the reader needs to have in mind. Formulas are written in plain-English pseudocode. Wherever a metric has two common definitions, we pin down exactly one here so downstream SQL doesn't drift.

**ROAS (Return on Ad Spend)**

```
ROAS = Attributed Revenue / Spend
```

The numerator is the sum of `total_usd` across orders attributed to the campaign (or channel); the denominator is the sum of `campaign_channel.spend_to_date_usd`. Channel-level ROAS needs spend-share weighting first (see below), because attribution is at the campaign grain.

**Spend-share weighting (pushing campaign-level revenue down to channels)**

```
channel_attributed_revenue = Σ over campaigns ( campaign_revenue × (channel_spend_in_campaign / campaign_total_spend) )
```

For each campaign, the revenue is split across channels in proportion to each channel's share of that campaign's spend. This is the industry-standard approximation, since `order.attributed_campaign_id` only resolves to the campaign level.

**AOV (Average Order Value)**

```
AOV = SUM(order.total_usd) / COUNT(order)
```

Definition: only count orders that actually transacted (`order_status IN ('delivered','shipped')`); `total_usd` includes shipping and tax, minus discounts. To compare members vs. non-members, group by `is_member_at_purchase`.

**LTV (Lifetime Value — proxy used in this dataset)**

```
LTV ≈ SUM(order.total_usd) per customer over all delivered/shipped orders
```

This dataset doesn't carry an explicit predictive LTV model, so we use "the customer's total realized revenue to date" as a proxy for realized LTV.

**CAC (Customer Acquisition Cost — per campaign)**

```
CAC = campaign_spend / new_customers_acquired_by_campaign
```

The denominator is the count of customers whose `acquisition_campaign_id` points to that campaign. CAC only makes sense for campaigns where `objective = 'ACQUISITION'`.

**Trial-to-Paid conversion**

```
Trial-to-Paid = COUNT(activation_date IS NOT NULL) / COUNT(trials_started)
```

Computed against `membership_subscription`. The numerator is trials that converted to paid (i.e., have an `activation_date`); the denominator is the total trials started in that cohort.

**Cohort retention rate (month n)**

```
retention_rate(n) = active_customers_in_month_n / cohort_size
```

`cohort_size` is the total customer count in the signup month. `month_diff = 0` is activation (not retention); retention only counts `month_diff >= 1`.

**Funnel-stage conversion rates (pinned definitions)**

```
delivery_rate   = delivered / sent
engagement_rate = engaged   / delivered      , engaged   = response_type IN ('open','click','convert')
click_through   = clicked   / delivered      , clicked   = response_type IN ('click','convert')
conversion_rate = converted / delivered      , converted = response_type = 'convert'
```

Because `response_type` is a terminal-state model — convert implies clicked, click implies opened — "click and above" and "engagement and above" both use `IN (...)` set membership. This is kept consistent across Q3, Q11, and Q18.

**CTR / channel CTR**

```
CTR = clicks / sends      (or clicks / delivered, depending on the analytical lens)
```

Creative-asset rankings (Q18) and channel × day-of-week (Q11) both use "clicks / delivered," consistent with the funnel definitions.

**Redemption rate (promo codes)**

```
redemption_rate = promo_code.redemption_count / promo_code.max_redemptions
```

**Member penetration (segment-level)**

```
pct_active_members = active_members_in_segment / segment_size
```

**Budget pacing**

```
pct_spent   = spend_to_date / total_budget
pct_elapsed = (REFERENCE_DATE - start_date) / (end_date - start_date)
```

When `pct_spent` is meaningfully higher than `pct_elapsed` (say, more than 10 percentage points higher), the campaign is burning too fast and should be flagged.

**Days to first order**

```
days_to_first_order = first_order.order_date - customer.signup_date
```

Averaged by acquisition channel. A shorter time-to-first-order means signups from that channel arrive with higher intent and tend to be higher quality.
