# Vantage Media's CTV Ad Campaign Analytics Business Context

This document is the entry point for the entire dataset. What it answers is not "what fields are in the tables," but rather "who this company is, how it makes money, why this dataset exists, and what jargon an outsider needs to learn first before they can make sense of the ER document and SQL queries that follow." If you are a new intern on the project, read this first, then move on to `02-advertising_ctv_campaign_analytics_high_er_document.md` (the data model) and `03-advertising_ctv_campaign_analytics_high_sql_queries.md` (query practice).

The company is fictional. The market is set in North America, the currency is USD, the cities are North American cities, and the regulators are US and Canadian agencies. The narrative is in English, the business is a North American company, and all industry terms are kept in their original English form, with the glossary explaining each one.

---

## 1. Company Profile

**Vantage Media** is a fictional AdTech (advertising technology) SaaS company headquartered in New York City, with a second office in Los Angeles (close to the Hollywood media and entertainment ecosystem). Founded in 2019, the company is laser-focused on one specific thing: helping brands place ads on **Connected TV (CTV)** and automating that whole process.

Its customers are almost entirely **DTC (Direct-to-Consumer) brands**. These brands sell things like supplements, fintech apps, streaming subscriptions, auto insurance, and direct-to-home e-commerce goods, and historically have bought their digital ads on Facebook and Google. When they want to extend their budget onto the TV screen (Hulu, Peacock, linear cable TV), they discover that traditional TV media buying is an old-school relationship-driven business that they cannot navigate on their own. Vantage Media exists to fill that gap: using software plus data science to let a DTC marketing manager who knows nothing about TV buying purchase TV ad inventory the same way they would buy digital ads.

Company scale is roughly at this order of magnitude (treat these as ballpark numbers, not precise financials):

| Dimension | Order of magnitude |
|------|------|
| Employees | Around 80 (Trading Desk, AutoML Platform, Customer Success, Data Engineering, RevOps — five teams) |
| Active customers (advertisers) | Around 120 DTC brands |
| Average customer annual media budget | About 1.3M USD, spread across three tiers (SMB / Mid-Market / Enterprise) |
| Network coverage | 15 TV and streaming networks (cable, broadcast, streaming) |

Internally the company is organized into five functional teams. The Trading Desk handles actual order placement and reacts to surprise changes. The AutoML Platform team consists of data scientists and ML engineers who build the models that power the flagship Booking Copilot product. Customer Success owns renewals and business reviews. Data Engineering maintains the upstream data pipelines. RevOps & BI does cross-team attribution, forecasting, and pipeline analysis. The role names that show up in the SQL queries later (Trading Desk Lead, Data Science Lead, CDO, CFO, Media Buyer) all come from this org structure.

---

## 2. Business Model

Vantage Media's revenue is stitched together from three streams, and understanding these three streams is enough to read every money-related metric in the rest of the dataset.

The first stream is the **media-fee take-rate**. When a customer buys TV ad inventory through the platform, the platform takes a 10% to 15% commission on the media spend. This is the bulk of revenue. So "how much media the customer spent" (gross media buy) directly drives platform revenue, and the queries later on (Q11, Q12, Q15) that compute media-buy amounts are essentially computing the base on which platform revenue is calculated. One caliber distinction to keep in mind: media-buy amount is the customer's total spend, not the platform's net revenue — to get net revenue you still need to multiply by the take-rate.

The second stream is the **Platform fee (platform subscription)**. Customers pay an annual software fee, similar to a typical SaaS subscription. This stream is relatively stable.

The third stream is the **AutoML module add-on fee**. This is where Vantage Media differentiates. The base platform just helps you place orders, but if a customer wants the smart prediction power of Booking Copilot (predicting whether a given inventory slot will be preempted, what the expected return is), they pay extra. Mid-Market and Enterprise customers in particular are willing to pay for customized models.

Customers fall into three tiers by annual media budget, and the tier directly drives the sales model and service level:

| Tier | Annual budget (USD) | Sales model | AutoML service level |
|------|------------------|----------|-----------------|
| SMB | 200K to 500K | Self-serve platform + email support | Shared multi-tenant model, weekly refresh |
| Mid-Market | 500K to 1.5M | AE-led, monthly business review | Semi-custom model, daily refresh + shadow scoring |
| Enterprise | 1.5M to 5M+ | Account Director, 6 to 9 month POC | Dedicated model + customer's own conversion data for training + real-time rescoring |

The key to understanding unit economics is this: the platform's profit ultimately depends on whether customers keep putting budget into CTV, which in turn depends on whether customers can actually make money on CTV (i.e., whether their ROAS is high enough). So Vantage Media's product is aligned with customer interest: the better the platform is at steering customers away from inventory that will be preempted and toward networks with high returns, the higher customer ROAS goes, the more budget they're willing to commit, and the more take-rate revenue the platform earns.

---

## 3. Industry Overview: CTV and AdTech

If you're coming from another industry, this section gives you a top-down picture of the CTV advertising business.

TV advertising is going through a major migration. In the past, watching TV meant sitting in front of a TV set at a scheduled time, watching **linear TV (traditional TV broadcast on a programming schedule)**, with ads inserted at fixed break points. Now more and more people watch shows via streaming apps (Hulu, Peacock, Pluto TV, and similar apps installed on a TV set), and this way of watching content on a TV screen over the internet is called **CTV (Connected TV)**. CTV ads combine the immersive big-screen feel of TV with the targetability and measurability of digital, which is why ad budgets are flowing into this space.

The players in this market fall into a few buckets. The **advertiser** is the side paying for the ads — in this dataset, DTC brands. The **network** is the side selling inventory, including linear cable channels (cable, e.g., ESPN, HGTV, TBS), linear broadcast networks (e.g., NBC, CBS, ABC, FOX), and streaming platforms (streaming AVOD, e.g., Hulu, Peacock, Pluto TV). Sitting in between are companies like Vantage Media — **media buying / AdTech platforms** — and dedicated **attribution partners** that measure conversions.

There's a fundamental difference between TV ads and digital ads: **TV ads have no click**. On the web, when you click an ad there's a click record, and you can trace it straight through to the purchase. But TV ads are watched, not clicked, so "how many conversions did this campaign actually drive" is a chronic, hard problem. The industry uses **attribution** as an approximation, with common methods including pixel match, IP match, and panel extrapolation — and the precision of these methods varies widely. This is exactly what Q8 in this dataset is designed to investigate.

On the regulatory front, CTV ads in North America are constrained by several lines. The **FTC (Federal Trade Commission)** polices ad truthfulness and anti-fraud. The **FCC (Federal Communications Commission)** governs broadcast TV content and transmission. On privacy, **CCPA / CPRA (California Consumer Privacy Act and its amendment)** and **VPPA (Video Privacy Protection Act)** restrict how viewing and targeting data can be used, which is part of why CTV attribution leans on indirect methods like pixel and panel. Industry self-regulation bodies like **IAB (Interactive Advertising Bureau)** and **MRC (Media Rating Council)** define measurement standards, and **Nielsen** is the long-established ratings and audience measurement firm — in this dataset, Nielsen Digital is one of the attribution partners.

At the macro level, three forces are shaping the industry. First, budget continues to shift from linear TV to CTV, and streaming ad inventory is growing fast. Second, measurement and attribution standardization is moving forward at the same time that privacy compliance is tightening, so measurement is both harder and more important. Third, AI and AutoML are entering media-buying decisions, shifting the field from "place orders based on relationships and experience" to "place orders based on model predictions." Vantage Media is betting on that third force.

---

## 4. Project Background and Your Role

You are a **data analyst (BI / RevOps)** at Vantage Media, reporting directly to the head of RevOps, and you also get pulled into ad-hoc projects by Trading Desk, Data Science, and Data Engineering. The job in front of you isn't to write a one-off report — it's to turn this body of CTV campaign data into a reusable set of analytical queries that support decisions at the strategic, tactical, and operational levels.

Your work goes out to different people. For the CEO, CFO, and CDO, you produce monthly and quarterly strategic overviews (media-buy trends, AutoML ROI, return comparison across network types). For the Trading Desk Lead, Data Science Lead, and Data Engineering Lead, you produce daily operational dashboards (network clearance monitoring, high-risk-slot alerts, model accuracy monitoring, data quality cockpit). For fellow analysts and data scientists, you produce on-demand exploratory queries (attribution method comparison, booking lead time correlation, end-to-end campaign ROI).

The 20 queries in `03-advertising_ctv_campaign_analytics_high_sql_queries.md` are the concrete landing point of this analysis. Each query is tagged with the role it serves and the business question it answers, and you can treat it as "a checklist of tasks your manager gave you this week" and work through them one by one.

Aside from analysts like you, there are several other roles inside the company that show up repeatedly in the data — understanding them helps you read the audit-style tables (booking_history, user_action):

| Role | What they do | Main tables they touch |
|------|----------|--------------|
| Media Buyer | Books placements, handles adjustments after preemption | ad_placement, booking_history, user_action |
| Trading Desk Lead | Monitors same-day preemption rate, adjusts the coming week's strategy | ad_placement, network_clearance_history |
| Data Scientist | Trains and evaluates AutoML models, does feature engineering | prediction_result, model_version, performance_actual |
| Data Engineer | Maintains data pipelines, responds to data quality alerts | ingestion_metadata, data_quality_log, alert_notification |

On the customer side there's also a decision chain (the classic 5-persona model in B2B sales): the Champion is the growth marketing manager pushing CTV trials at the customer; the Economic Buyer is the VP Marketing who holds the budget; the Decision Maker is the CMO who owns channel strategy; the Influencer is the data scientist or analyst who evaluates model effectiveness; and the Blocker is the procurement or legal person who polices contracts and compliance. This chain explains why Enterprise customer POCs take 6 to 9 months.

---

## 5. Business Problems to Solve

The dataset is built around four specific business problems. Each one corresponds to a deliberately seeded data distribution in the ER document and to several queries in the SQL document.

**Problem one: media buying blind spot.** Before quoting a customer, buyers don't have forward-looking data — they don't know which slots will be preempted, and they can't quantify expected ROAS. A preemption means the customer's booked slot never aired, which is pure opportunity cost. Rough estimate is about 7,000 preempted placements per month, totaling 30M to 50M USD in undelivered opportunity cost. This is the core pain point that the Booking Copilot product is meant to address, and it maps to Q1, Q3, Q7, Q12.

**Problem two: customer variance is too large; a one-size-fits-all model fails.** For the same network, returns vary completely across customer industries. Health brands on ESPN see ROAS around 0.7x, but on HGTV they see 1.5x. Auto brands see the opposite (sports content actually works for auto ads). A global model averages these differences away and produces predictions nobody is happy with. This is exactly the fundamental motivation for Vantage Media to build custom AutoML models per customer, mapping to Q4, Q6, Q8, Q20.

**Problem three: the attribution puzzle.** Since TV ads have no clicks, conversions have to be estimated by 4 third-party attribution partners (AttributionPro, Nielsen Digital, ImpactTracker, ConversionPixel) using different methods (pixel, IP, panel), with very different precision. If you don't first normalize across attribution methods, cross-partner ROAS comparisons will lead you to wrong conclusions. This maps to Q8.

**Problem four: data quality black holes.** Data comes from more than 10 upstream sources (TV network logs, streaming logs, attribution partner APIs), with frequent latency, duplicates, and missing data, all of which directly poison ML training feature quality. The company uses a set of data quality rules and an alerting mechanism to guard against this, mapping to Q5, Q10, Q13, Q17.

In addition to these four business problems, the dataset is also designed to support one specific product narrative: **Booking Copilot AutoML model monitoring**. This is the company's story for CDOs and customers, demonstrating "our models are continuously improving." It maps to Q2, Q14, Q18 and the shadow scoring concept covered in detail in the knowledge primer below. Worth noting: this thread also hides a counterintuitive conclusion (see Q2 / Q14): for the clearance binary classifier, accuracy is essentially flat across the three model generations because the class is extremely imbalanced; what's actually improving is the regression error on ROAS. This tells the data science team to redirect their effort toward solving class imbalance instead of continuing to tune hyperparameters.

---

## 6. Data Scope Overview

The data snapshot is anchored at **AS_OF_DATE = 2025-10-31**. All SQL queries that involve "last N days" or "the past few weeks" use the fixed date string `'2025-10-31'` as the reference point, not `DATE('now')`, so query results on historical data stay stable and reproducible.

Active business data covers **2025-05-01 to 2025-10-31, six months total**. On top of that there is a separate 2024-11 to 2025-04 ML training feature lookback window (via the network_clearance_history table); this window deliberately predates the active window, which is standard practice in ML to avoid time leakage (compute features in a historical window and do prediction/evaluation in a separate window).

In plain English, the data volume looks like this: 120 advertisers, 400 campaigns, 50K placement bookings (the core fact table), 42K actual performance records (only aired placements get one), 50K ML prediction records (every placement gets one), plus various audit, ops, and config tables, totaling roughly 164K rows — landing in the High complexity tier.

A few deliberate scoping decisions are worth flagging upfront. First, the data covers only 6 months rather than a full year, because this window straddles the Q3 off-peak and Q4 peak (including NFL season), which is enough to surface seasonality without being redundant. Second, the market is restricted to North America (USD, North American networks, North American regulators) with no other regions mixed in. Third, only three model versions are kept (v2.1.5, v2.2.0, v2.3.1), which is enough to tell the iteration story.

The specific fields, constraints, sample data, and seeded data-distribution traps for each table are all in the ER document — they aren't expanded on here.

---

## 7. Industry Knowledge Primer

This section is the half-hour background an outsider needs before reading the data. It walks through "one campaign from booking to settlement" in order.

**Step one: how inventory is priced and booked.** TV ads are priced by **CPM (Cost Per Mille, cost per thousand impressions)** — that is, how much you pay per thousand people who see the ad. The total price of a slot = CPM × impressions / 1000. Buyers place orders some number of days before the ad airs, and that lead is called the **booking lead time**. Within a single break, multiple ads run back-to-back, and an ad's position within the break is called its **break position**. The time of day that an ad airs is divided into **dayparts**, typically early morning, daytime, early fringe, primetime (the golden window, most expensive), and late night. CPM in primetime is typically 30% or more higher than in daytime.

**Step two: whether the slot actually airs.** This is the most critical and counterintuitive point in CTV buying. Booking a slot doesn't guarantee it airs — the network may at the last minute reallocate your slot to more valuable content (especially live sports), which is called **preemption**. Successful airing is called **clearance**. The fraction of slots that air at a given network is the **clearance rate**, and the preempted fraction is the **preemption rate**. Networks with heavy live programming (sports-heavy ESPN) have low and volatile clearance rates, while lifestyle networks like HGTV and streaming platforms have high and stable clearance rates. The most classic seasonal shock is **NFL season (September through end of October)**, during which clearance rates at ESPN, ESPN2, and FOX drop by 15 to 20 percentage points because so much inventory gets handed over to live games.

Clearance rate is also correlated with booking lead time: the earlier you book, the less certain the programming for that slot is, so the more likely it gets preempted; the later you book (within 7 days), the more settled the programming is, so clearance is actually higher. This is the hypothesis Q9 tests.

**Step three: how to measure return after airing.** Once an ad airs, you need to measure the conversions and revenue it drove. The core metric is **ROAS (Return On Ad Spend)** = attributed revenue / spend. ROAS of 1.5x means every $1 spent brought back $1.50 in revenue. Since TV has no clicks, conversion counts have to be estimated by attribution partners, and different **attribution methods** have different precision: pixel match uses pixel postbacks, is the most accurate, and tends to slightly overestimate; IP match correlates via IP addresses and sits in the middle; panel extrapolation extrapolates a sample panel to the population and systematically underestimates. There's also attribution latency — partners need time to get complete data, called the **attribution window**, plus the partner's own processing delay.

**Step four: how AutoML enters the decision.** Vantage Media's product, **Booking Copilot**, uses a model to predict two numbers for each candidate slot before the buyer quotes, and overlays them in the buyer UI: clearance probability (will this slot be preempted, a binary classification task) and expected ROAS (a regression task). The most important features driving the prediction (top features) are also surfaced to the buyer, like a simplified SHAP explanation.

There's a key product differentiator hidden in here called **shadow scoring**. Vantage Media doesn't run just one fixed model; instead it keeps 3 generations of model versions live at the same time, all scoring the same batch of inventory. The primary version drives live decisions, while the others run backtesting (backtesting) in the background. This way when you compare versions, everyone is looking at the same data, avoiding the "the old version only saw easy data, the new version only saw hard data" confound. Model quality is measured with two metrics: classification tasks look at **AUC-ROC** (ranking quality) and accuracy; regression tasks look at **MAPE (Mean Absolute Percentage Error)**.

There's an important lesson that runs through the whole dataset hidden here: because the clearance binary task has extreme class imbalance (about 85% of slots clear), a naive "always predict cleared" baseline gets about 85% accuracy, so all three model generations end up flat at roughly the same accuracy, and you can't break through that noise floor just by tuning hyperparameters. What is monotonically improving is the MAPE on the ROAS regressor (from 12% down to 8% down to 5%). This tells the team to shift to algorithmic interventions (class weighting, focal loss, resampling) to address imbalance, rather than continuing to tune hyperparameters on the clearance model. Q2 and Q14 are the queries that tell this story.

**Step five: how to make the data trustworthy.** Everything above stands on top of data quality. The company runs a set of **data quality rules** that automatically check upstream data every day, with rules tiered by severity into P0 (a severe issue that blocks downstream), P1, and P2. Check results land in a data quality log, and when an alert is triggered it is sent to the on-call engineer via Slack or email. The metric for response speed is **MTTR (Mean Time To Resolve)**. Upstream data sources also have delivery **SLAs (Service Level Agreements)** that specify what time each day they must deliver by and how much delay is tolerated, and SLA compliance rate is a key vendor management metric.

---

## 8. Glossary

This is a plain-English explainer for every piece of jargon that shows up in the dataset. Terms are kept in their original English form, and you can come back here to look them up when these words show up in the ER document and SQL queries that follow.

| Term | Plain-English explanation | Why it matters here |
|------|--------------|------------------|
| CTV (Connected TV) | Watching content on a TV screen over the internet (streaming apps) | The entire vehicle for the company's business |
| Linear TV | Traditional TV broadcast on a programming schedule | The old form contrasted with CTV; both cable and broadcast in this dataset are linear |
| AVOD (Ad-supported Video On Demand) | Free on-demand streaming supported by ads | Business model of Hulu, Peacock, Pluto TV; high clearance rate |
| DTC (Direct-to-Consumer) | Brands that sell directly to consumers, bypassing channels | Vantage Media's customers are entirely of this kind |
| AdTech | Advertising technology, using software and data to drive ad placement | The industry the company is in |
| Media Buying | Media purchasing, i.e., buying ad inventory | The core action the platform performs for customers |
| Trading Desk | The purchasing team responsible for placing orders and real-time adjustments | Internal team, corresponds to the Media Buyer role |
| advertiser | Advertiser, the brand customer paying for the ads | A dimension table; 120 in this dataset |
| network | The TV or streaming platform selling inventory | Dimension table; 15 in total across three types |
| network_type | Network type, split into linear_cable / linear_broadcast / streaming_avod | Critical dimension that drives clearance rate and ROAS |
| campaign | A customer's campaign, one round of investment with a budget and schedule | placements hang off of campaigns |
| placement | A specific ad airing (one ad on one network in one daypart on one day) | The core fact table; 50K records |
| CPM (Cost Per Mille) | Cost per thousand impressions | The pricing unit for TV ads |
| impressions | Impressions, the number of times the ad was seen | The denominator in CPM pricing |
| booked CPM / booked impressions | The CPM and impressions agreed at booking time | Inputs to compute the media-buy amount |
| gross media buy | Media buy amount, the customer's total spend | The base for the platform's take-rate, not the platform's net revenue |
| take-rate | The percentage the platform takes from the media fee (10% to 15%) | The platform's main revenue source |
| clearance | The slot successfully aired | The positive class for the binary classification task |
| preemption | The slot was preempted and did not air | Source of opportunity cost; the core thing the product predicts |
| clearance rate | Clearance rate, the share of resolved slots that aired | The core metric for measuring network reliability |
| daypart | The time of day the ad airs (primetime, daytime, etc.) | Affects CPM and audience |
| primetime | The golden hours (8pm to 11pm), most expensive | CPM lift of 30% |
| break position | The ad's position within the commercial break | A feature of the placement |
| booking lead time | Booking lead time, days from order to airing | Correlates with clearance rate (Q9) |
| NFL season | NFL football season (September through end of October) | Seasonal shock that crashes sports network clearance rates |
| ROAS (Return On Ad Spend) | Return on ad spend = revenue / spend | The core metric for campaign performance |
| AOV (Average Order Value) | Average order value | Used to back-derive conversion counts from revenue |
| CPA (Cost Per Acquisition) | Cost per acquisition = spend / conversions | The other face of performance measurement |
| conversion | Conversion, the actual purchase or signup driven by the ad | The source of ROAS's numerator |
| attribution | Attribution, the act of assigning a conversion to a specific ad | Since TV has no click, can only be estimated |
| pixel match | Attribution via pixel postback, the most precise | Slightly overestimates ROAS (Q8) |
| IP match | Attribution via IP address correlation, medium precision | Middle-of-the-pack ROAS (Q8) |
| panel extrapolation | Extrapolation from a sample panel to the population | Systematically underestimates ROAS (Q8) |
| attribution window | Attribution window, days to wait for conversion data to settle | Drives attribution latency |
| attribution partner | A third party providing attribution data | 4 of them in this dataset |
| AutoML | Automated machine learning that handles features, model selection, and tuning | An engineering lever for product differentiation |
| Booking Copilot | Vantage Media's flagship ML product | Surfaces predictions to buyers before they place an order |
| clearance classifier | Binary classifier that predicts clearance probability | One class in model_version |
| ROAS regressor | Regression model that predicts ROAS | The other class in model_version |
| shadow scoring | Multiple model versions scoring the same data simultaneously | Lets version comparisons rest on the same data distribution |
| backtesting | Evaluating a model retrospectively on historical data | The evaluation mode used in shadow scoring |
| AUC-ROC | Ranking quality metric for binary classifiers (0.5 to 1) | Measurement for classification models |
| MAPE (Mean Absolute Percentage Error) | Mean absolute percentage error | Measurement for regression models (ROAS) |
| confidence level | Prediction confidence (low / medium / high) | An assistive signal to the buyer |
| top features | The most important features for a single prediction | Simplified SHAP, surfaced to buyers |
| class imbalance | Class imbalance, where positive and negative classes are skewed | Root cause of the clearance accuracy ceiling |
| recall / precision | Recall / precision | More meaningful than accuracy in imbalanced settings |
| SLA (Service Level Agreement) | Service Level Agreement, contractual delivery timing | Upstream data source management |
| MTTR (Mean Time To Resolve) | Mean time to resolve | Speed of data quality response |
| data quality rule | Data quality check rule | Guards ML training data |
| P0 / P1 / P2 | Severity tiers for data quality issues | P0 is the most severe, blocking downstream |
| ingestion | Data ingestion into the warehouse | The point at which upstream data enters the platform |
| z-score anomaly | Anomaly detection via standard scores | One type of data quality rule |

---

## 9. Key Metrics and Formulas

Below are the core metric definitions that the SQL queries will use. When two definitions are both common, this section pins down one specific caliber, so that different queries don't return mutually contradictory numbers. Formulas are written in SQL-flavored pseudocode.

**Media buying metrics.**

```
Clearance Rate    = SUM(status = 'cleared') / COUNT(status IN ('cleared','preempted'))
Preemption Rate   = SUM(status = 'preempted') / COUNT(status IN ('cleared','preempted'))
Gross Media Buy   = SUM(booked_cpm * booked_impressions / 1000)
Average Lead Time = AVG(booking_lead_days)
Preemption Opportunity Cost
                  = SUM(booked_cpm * booked_impressions / 1000) WHERE status = 'preempted'
```

Clearance rate and preemption rate are always computed only on resolved placements (cleared or preempted), excluding the pending status whose outcome is still uncertain. This caliber agreement runs through Q1, Q7, Q9, Q14, Q16, Q18 — be consistent or the clearance rates across queries won't reconcile.

**Performance and attribution metrics.**

```
ROAS (placement level)     = attributed_revenue_usd / spend_usd
ROAS (spend-weighted)      = SUM(attributed_revenue_usd) / SUM(spend_usd)
CPA                        = SUM(spend_usd) / SUM(attributed_conversions)
Attribution Lag (hours)    = AVG(finalized_at - scheduled_air_time)
```

ROAS has two computation methods. Per-row average (AVG(roas)) is sensitive to small orders and easily skewed by a few extreme values; spend-weighted (SUM(revenue)/SUM(spend)) is the true aggregate return the CFO cares about. Queries that drive strategic decisions (Q6, Q20) prefer the spend-weighted caliber and will list both for comparison.

**AutoML model monitoring metrics.**

```
Clearance Accuracy       = AVG((pred >= 0.5 AND status='cleared') OR (pred < 0.5 AND status='preempted'))
Recall on preempted      = TN / (TN + FP)   the fraction of true preempted that were correctly predicted as low clearance
ROAS MAPE                = AVG(ABS(predicted_roas - roas) / roas) * 100
```

In an imbalanced setting, overall accuracy is locked in by the majority class and is of limited value. What actually measures "can the model catch high-risk slots that will be preempted" is Recall on preempted. This is the point Q2 and Q14 keep hammering. Lower ROAS MAPE is better, and in this dataset MAPE for the three regressor generations decreases monotonically (about 12% to 8% to 5%).

**Data quality and ops metrics.**

```
DQ Pass Rate         = SUM(status = 'passed') / COUNT(*)
MTTR (hours)         = AVG(resolved_at - run_timestamp)
SLA Compliance Rate  = fraction of arrivals no later than (expected_delivery_hour + sla_threshold_hours)
DQ Resolution Rate   = SUM(resolved_at IS NOT NULL) / SUM(alert_fired = 1)
```

These metrics support Q5, Q10, Q17. SLA compliance rate has to be computed using an absolute time difference (julianday in hours) to correctly handle cross-day delays — see Q10 in the SQL document for the exact formulation.
