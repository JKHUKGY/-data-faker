# Stratosend Demand Generation and Marketing Operations Business Context

> **Dataset:** `b2b_saas_demand_generation_high`
> **Complexity:** High (16 tables, approximately 118,000 rows)
> **Market:** North America (currency USD)
> **REFERENCE_DATE ("today"):** `2026-06-01`
> Data-layer details (table schemas, fields, DDL, data-generation rules) live in `02-b2b_saas_demand_generation_high_er_document.md`. Concrete SQL examples live in `03-b2b_saas_demand_generation_high_sql_queries.md`.

This document is the opening chapter of the whole dataset. It first explains who Stratosend (the fictional company) is, how it makes money, and how its industry works. It then describes what role you play inside the company and which business questions you need to answer. Finally, it lays out, once and for all, the terms and metric formulas that will keep showing up in the tables and queries. After reading this, a new hire should be able to follow what everyone is talking about at their first standup.

---

## 1. Company Snapshot

**Stratosend** is a fictional North American B2B SaaS company headquartered in Denver, Colorado. Founded in 2018 by a few former SREs (Site Reliability Engineers) and platform engineers, the company sells an **API Observability Platform**. Think of the kinds of tools on the market that focus on monitoring API performance, error rates, latency, and service dependencies: when a company's production APIs slow down or start throwing errors, Stratosend helps the engineering team pinpoint which service or which call chain is at fault within minutes, instead of spending hours digging through logs.

The company is at growth stage (order of magnitude): roughly 200 employees, about 2,000 companies (accounts) in the book, with about 280 of them already converted to paying customers, and annual recurring revenue (ARR) in the tens of millions of USD. Revenue is split across three customer tiers, and the tier determines the sales motion, the typical deal size, and the length of the sales cycle.

| Tier | Customer Profile | Deal Size (USD) | Sales Motion |
|------|-----------------|-----------------|--------------|
| **SMB** | Fewer than 100 employees | $5K to $25K | Self-serve with light follow-up |
| **Mid-Market** | 100 to 1,000 employees | $25K to $100K | AE-led sales |
| **Enterprise** | More than 1,000 employees | $100K to $500K+ | Multi-stakeholder POC, 6-to-12-month sales cycle |

The org structure most relevant to this dataset (these titles will show up in the SQL queries as business roles):

- **Executive team:** CEO, CMO (Chief Marketing Officer), CFO (Chief Financial Officer), CRO (Chief Revenue Officer).
- **Marketing team:** VP Marketing, Demand Gen Manager (runs inbound campaigns), Content Marketing (whitepapers and webinars), Field Marketing (in-person events), Marketing Ops (data and tool stack), ABM Lead.
- **Sales team:** VP Sales, SDR/BDR (first-touch outreach and qualification), AE_SMB / AE_Mid / AE_Enterprise (closers by tier), and the Managers of each team.
- **Revenue Operations (RevOps):** Sits across Marketing and Sales, owns attribution, forecasting, and pipeline analytics. This is the team you sit on.

---

## 2. Business Model

Stratosend makes its money from **subscription fees**. Customers sign annual (sometimes multi-year) contracts and pay an annual recurring revenue (ARR) amount in exchange for the right to use the platform over the term of the contract. Pricing has two components: a per-seat fee (number of engineers using the platform) and a usage fee (number of monitored hosts and volume of ingested data). The more the customer uses, the bigger the bill — the classic SaaS "land and expand" path: sign a small deal in one department, prove the value, then expand to the rest of the company.

Who buys? Almost always an **engineering organization**, not a procurement-led process. A single deal usually involves several roles: the engineers who actually use the product day to day (Champion and Influencer), the engineering manager who holds the budget (Economic Buyer), the VP of Engineering or CTO who makes the final call (Decision Maker), and the security, procurement, or legal person who has to sign off (Blocker). The higher the tier, the more people get involved — Enterprise deals routinely need 5 to 7 stakeholders to nod yes before they close.

How does the company actually make money? From a unit-economics standpoint, three things matter most:

- **Gross margin is high.** The marginal cost of delivering software is low, and SaaS gross margins are typically 75% to 85%. Stratosend's main cost is not delivery — it is customer acquisition.
- **CAC has to pay back.** The dollars the company spends on marketing campaigns and sales headcount (CAC, Customer Acquisition Cost) have to be earned back from subscription revenue within a reasonable window. The healthy target is 18-month payback for SMB customers and 24-month payback for Enterprise.
- **Renewal and expansion drive long-term value.** A single customer's lifetime value (LTV) depends on how many years they renew and how much they expand. The ratio of LTV to CAC (LTV/CAC) is the headline metric for whether growth is sustainable.

That is why every dollar spent on marketing and sales has to earn its keep. Stratosend asks this question every day, and that is the reason this dataset exists.

---

## 3. Industry Overview

If you come from a different industry, this section gives you a quick read on what the API observability market actually does.

**What the industry produces.** Modern software is stitched together out of hundreds or thousands of services that call each other (microservices). Whenever any link in that chain slows down or errors out, the user sees a spinning page or an error message. The job of an observability tool is to collect three classes of signals that those services emit at runtime (metrics, logs, and traces) so engineers can answer "where is it broken right now, why, and how big is the blast radius." It maps directly to one hard number, MTTR (mean time to repair): the better the tool, the shorter the time from incident to fix, and the less money the company loses to downtime.

**Major categories of players (without naming real companies).** The market roughly splits into a few camps: legacy APM (application performance management) vendors, log management specialists, distributed tracing tools, infrastructure monitoring vendors, and "full-stack observability" suites that try to do all of it inside one platform. Stratosend takes the focused route — its specialty is the API layer: performance, errors, and dependency graphs.

**Relevant compliance frameworks.** This industry does not have a dedicated regulator the way finance or healthcare does. But because the tool plugs into the customer's production systems and data, **security and privacy compliance** is a hard gate for Enterprise procurement. The usual suspects are SOC 2 Type II and ISO 27001 (security certifications), and on the privacy side, CCPA in California, PIPEDA in Canada, and GDPR for any European customers. That is also why every deal has a Blocker role (security or legal) running a risk review.

**Forces shaping the industry today.** First, the OpenTelemetry open standard is unifying how data is collected, which lowers the switching cost between vendors and intensifies competition. Second, AI-driven anomaly detection has become a major selling point — everyone wants to be first to surface the incident automatically. Third, "observability cost explosion" has become a customer pain point: the more data you ingest, the bigger the bill, so customers are starting to count pennies and trim usage, which puts pressure on vendor revenue expansion. Fourth, platform consolidation is accelerating — customers want one platform instead of seven point tools. After this section, you should be able to hold a conversation with an engineer or a salesperson.

---

## 4. Your Role and the Project

You are a **data analyst on the Revenue Operations (RevOps) team** at Stratosend, reporting directly to the head of RevOps. RevOps is unusual because it sits across both Marketing and Sales — it does not pick a side, and its job is to use data to tell the full story of "how a stranger turns into a lead and that lead turns into closed revenue."

Your day-to-day output has two flavors:

- **Maintain the standardized BI dashboards.** The company has a three-tier dashboard system: a strategic layer for executives (quarterly Marketing P&L, pipeline health, CFO unit economics, etc.), an operational layer for managers (daily funnel, SDR capacity, active campaign tracking, etc.), and an exploratory layer for the analysts themselves. The SQL behind those dashboards is what you write.
- **Answer ad-hoc business questions.** The CMO wants to know which channel to cut from the budget before the quarterly review; the VP Sales wants to know on Monday morning whether the pipeline is enough to hit quota; the CFO wants CAC broken down by channel. These questions cannot be answered by a fixed dashboard widget, so they land on your desk as a one-off analysis.

These outputs ultimately feed into quarterly business reviews (QBRs) and board-prep materials. In other words, the queries you write are not academic exercises — they will literally become the chart the CMO shows the board, or the number the VP Sales uses to decide whether to staff up SDRs in a hurry.

---

## 5. Business Questions to Answer

The whole project revolves around five concrete business questions. The data distributions embedded in the ER document, and every query in the SQL document, can be traced back to one of these.

- **Q1 Where does the funnel leak (Funnel Leakage).** Going from Lead to MQL to SQL to Opportunity to Closed-Won, what is the conversion rate at each step? Which step bleeds the most volume? Is lead quality decaying by source channel or by quarter? This is the project's flagship question.
- **Q2 Which campaigns and channels actually generate revenue (Attribution).** Using W-shaped multi-touch attribution and comparing it against the simpler first-touch and last-touch models, which campaign types and lead sources produce the highest influenced pipeline and ROI? Which deserve more budget, and which should be cut?
- **Q3 Is pipeline health and the forecast trustworthy (Pipeline & Forecast).** Does the current open pipeline cover the team's quota (the classic 3x coverage rule)? How fast is each stage moving? How many opps have gone stale or slipped repeatedly (close date pushed again and again)? What is the weighted forecast by stage probability?
- **Q4 Sales productivity and SLAs (Sales Productivity).** Are SDRs completing first-touch outreach within 24 hours after a lead becomes an MQL (SLA compliance)? How does reply rate decay across the steps of an outbound sequence? What is the quota attainment ranking by AE? How long does it take a new sales hire to land their first deal (ramp time)?
- **Q5 Engagement effectiveness on ABM strategic accounts (ABM).** For Tier-1 target accounts, are we covering enough stakeholders (stakeholder coverage)? Which target accounts have gone untouched for too long? How much higher is win rate on ABM accounts versus non-ABM? How many accounts produced a second expansion deal?

---

## 6. Data Scope at a Glance

This dataset is a point-in-time snapshot of Stratosend's CRM plus marketing automation systems, anchored at **REFERENCE_DATE = 2026-06-01** (any "today" or "last 30 days" semantics are calculated relative to this date).

- **Time span:** 18 months of history, from 2024-12-08 to 2026-06-01. It also includes currently in-flight ACTIVE campaigns and PLANNED campaigns for the next 30 days (planning metadata only, no engagement data yet).
- **Data volume (in plain English):** About two thousand companies, eight thousand leads, three-thousand-plus contacts, sixteen-hundred-plus sales opportunities, plus a handful of event-level wide tables (about 45,000 lead scoring events, 30,000 sales emails, 18,000 content engagements). Roughly 118,000 rows total across 16 tables.
- **Deliberate scope choices:** Market focus is North America. About 72% of customers are in the United States, and the rest are spread across Canada, the United Kingdom, Germany, Australia, France, etc., but the narrative and regulatory baseline default to North America. The whole dataset covers only Stratosend itself — no competitor data, no external market data mixed in.

The fields, row counts, and dependencies of each individual table are not covered here — see the ER document for that.

---

## 7. Industry Primer

This section is the thirty-minute primer an outsider needs before the data starts to make sense. After this, the glossary and metric formulas will go down much more smoothly.

**Demand Generation Funnel.** Customer acquisition in B2B SaaS is a stage-gated funnel where each level is a qualification gate:

1. **Lead:** Any prospective buyer who has left their contact information (downloaded a whitepaper, signed up for a webinar, filled out a demo request). The very top of the funnel — biggest in volume, most variable in quality.
2. **MQL (Marketing Qualified Lead):** A lead whose behavior is active enough that marketing has decided sales should follow up. How is that decided? Lead scoring.
3. **SQL (Sales Qualified Lead):** Note that SQL here is *not* the query language — it stands for "Sales Qualified Lead." It is a lead that an SDR has spoken with, confirmed has real need and budget, and is worth handing off to an AE.
4. **Opportunity (opp for short):** A real deal in the sales process, with an amount and an expected close date.
5. **Closed-Won / Closed-Lost:** The final outcome of the deal.

**Lead Scoring.** The system attaches points to every lead behavior (visited the pricing page +20, downloaded a piece of content +15, attended a webinar +30, unsubscribed -50, etc.). The instant the cumulative score crosses the threshold (100 points in this dataset) for the first time, that lead is promoted to MQL — captured in the field `mql_date`.

**ARR and MRR.** ARR (Annual Recurring Revenue) is the headline metric for subscription SaaS — the amount of contracted revenue that can be recognized on a repeating basis over one year. MRR is the monthly version of the same thing (ARR ÷ 12). All amounts in this dataset are expressed as ARR.

**Seven-stage sales pipeline (Sales Stages).** Opps move through these stages, and each one has a standard win probability (used for weighted forecasting):

| Stage | Meaning | Standard Win Probability |
|-------|---------|--------------------------|
| Discovery | Initial contact, scoping needs | 10% |
| Demo | Product demonstration | 25% |
| Evaluation/POC | Evaluation or proof of concept | 40% |
| Proposal | Pricing proposal | 60% |
| Negotiation | Commercial negotiation | 80% |
| Closed-Won | Won | 100% |
| Closed-Lost | Lost | 0% |

**Sales roles.** The SDR (Sales Development Rep) owns the top of the funnel: first-touch outreach and qualification, moving Leads into MQL and SQL. SDRs typically do not carry a revenue quota. The AE (Account Executive) owns the bottom of the funnel: from demo to close, carries an annual ARR quota, and is segmented by customer tier (AE_SMB / AE_Mid / AE_Enterprise).

**Five-persona B2B buyer framework (Buyer Personas).** A B2B deal is not decided by any one person. The data describes the buying committee with five personas:

| Persona | Role in the Deal |
|---------|------------------|
| Champion | The internal advocate driving adoption (usually a senior engineer or Tech Lead) |
| Economic Buyer | The person holding the budget (engineering manager or director) |
| Decision Maker | The person making the final call (VP Engineering or CTO) |
| Influencer | The person using it day to day and shaping opinion (DevOps or SRE) |
| Blocker | The person who can tap the brakes (security, procurement, legal) |

**Attribution Models.** A deal usually crosses many marketing touches on the way in. How do you divide the credit? Three common algorithms. **First-touch** gives all credit to the very first touch, **Last-touch** gives all credit to the very last touch — both are too extreme. **W-shaped** is the B2B compromise: it splits credit into first touch 30%, the touch that converted the lead to MQL 30%, the last touch before opp creation 30%, and the remaining 10% is spread evenly across any other influencers along the path. Q2 is fundamentally about using W-shaped attribution to correct for first-touch bias.

**ABM (Account-Based Marketing).** The opposite of "spray and pray for leads." In ABM, you first hand-pick a set of high-value target accounts, then concentrate fire by reaching multiple stakeholders inside each one with precision outreach. Accounts are tiered Tier 1 / Tier 2 / Tier 3 by priority. Two things measure ABM effectiveness: how many distinct personas you have covered inside each account (stakeholder coverage), and how long it has been since each target account had any touch (no-touch days).

**Gated Content.** Some marketing content (ebooks, whitepapers) is only downloadable after filling out a form. That form fill creates a new lead, hence "gated." Ungated content (blog posts) is freely accessible, generates no leads, but does nurture existing ones.

---

## 8. Glossary

Every term that shows up in the ER document and SQL queries is defined here once. Each entry gives the original English term, a plain-language explanation, and why it matters in this dataset.

| Term | Plain-Language Explanation | Why It Matters |
|------|----------------------------|----------------|
| **ARR** (Annual Recurring Revenue) | Subscription revenue that can be recognized on a repeating basis within one year | The currency of every amount in this dataset; the base unit for revenue, quota, and forecast |
| **MRR** (Monthly Recurring Revenue) | The monthly version of ARR (ARR ÷ 12) | Needed when computing CAC payback on a monthly basis |
| **Lead** | A prospective buyer who has left contact information | The top-of-funnel entity; the starting point of every conversion |
| **MQL** (Marketing Qualified Lead) | A lead active enough to merit sales follow-up | The marketing-to-sales handoff; the second funnel gate |
| **SQL** (Sales Qualified Lead) | A lead an SDR has confirmed has need and budget (not the query language) | The third funnel gate; the last checkpoint before entering the sales process |
| **Opportunity / Opp** | A real deal with an amount and an expected close date | The core revenue entity; pipeline and forecast both build on it |
| **Account** | A prospective or current customer company | The container for multi-stakeholder selling; an account holds many contacts and opps |
| **Contact** | A specific individual at an account that sales has reached | The primary contact on an opp; created by lead conversion or by direct outreach |
| **SDR / BDR** (Sales / Business Development Rep) | The sales rep who does first-touch outreach and qualification | Responsible for pushing Leads into MQL and SQL; the protagonist of SLA and sequence metrics |
| **AE** (Account Executive) | The quota-carrying sales rep responsible for closing | Owns pipeline and quota attainment; segmented by customer tier |
| **RevOps** (Revenue Operations) | The data and process team that spans Marketing and Sales | Your team; owns attribution, forecasting, and pipeline analytics |
| **Demand Gen** (Demand Generation) | Continuously manufacturing demand and leads through marketing campaigns | The marketing team's core function; the home of campaign performance |
| **ICP** (Ideal Customer Profile) | The portrait of the ideal target customer | The yardstick for deciding whether a lead is worth pursuing or should be disqualified |
| **Persona** | The archetypal role a buyer plays in the buying committee | The five-role framework (Champion etc.); the dimension for ABM stakeholder coverage |
| **Lead Scoring** | Cumulative points scored on a lead based on behavior | Crossing 100 points promotes the lead to MQL; determines `mql_date` |
| **CAC** (Customer Acquisition Cost) | The average cost of acquiring one new customer | The core unit-economics number; too high means acquisition is not profitable |
| **CPL** (Cost Per Lead) | The average cost of acquiring one lead | The yardstick for channel efficiency; varies sharply by lead source |
| **LTV** (Lifetime Value) | Total value a customer contributes over their lifetime | Looked at next to CAC to judge whether growth is sustainable |
| **LTV/CAC** | The ratio of lifetime value to acquisition cost | The headline SaaS health metric, generally targeted above 3 |
| **Payback Period** | Number of months for subscription revenue to recover CAC | What the CFO cares about for capital efficiency; SMB target is within 18 months |
| **Pipeline** | The total amount across all open opps | The reservoir for future revenue; its health is measured by coverage |
| **Pipeline Coverage** | Ratio of open pipeline to quota | The classic 3x rule; below 3x means you need to refill the pipeline fast |
| **Win Rate** | Share of closed opps that were won | The core sales-effectiveness number; defined as Wins ÷ (Wins + Losses) |
| **Sales Cycle** | Duration from opp creation to closed-won | Varies hugely by tier (SMB short, Enterprise long) |
| **Stage Velocity** | Number of days an opp spends in each stage | Used to find bottleneck stages and improve throughput |
| **Stale Opportunity** | An open opp with no stage transition for more than 30 days | A leading indicator that the deal will eventually be lost |
| **Slipped Deal** | An opp whose expected close date keeps being pushed | The reason forecasts go bad; detected from historical snapshots |
| **Weighted Forecast** | Pipeline forecast weighted by each stage's win probability | Closer to the realistically closable amount than raw pipeline |
| **Quota / Quota Attainment** | An AE's annual quota / their attainment rate | The core measure of sales-rep productivity |
| **Attribution** | The act of dividing closed-deal credit across marketing touches | Drives where the budget goes; splits into first-touch / last-touch / W-shaped |
| **Influenced Pipeline** | The pipeline amount of any account that was touched by a campaign | A wider measure of true campaign influence than first-touch alone |
| **ABM** (Account-Based Marketing) | Precision marketing aimed at a selected list of high-value accounts | The core of Q5; corresponds to target_account_list |
| **Target Account** | A strategic account on the ABM list | The is_target_account field; skewed toward Mid and Enterprise |
| **Tier 1/2/3** | Priority tiers for ABM target accounts | Drives resource allocation and outreach cadence |
| **Stakeholder Coverage** | Number of distinct personas reached inside a target account | The ABM-depth metric; broader coverage means higher win odds |
| **SLA** (Service Level Agreement) | Here: the commitment to follow up within 24 hours after MQL | The core SDR productivity number; faster follow-up means better conversion |
| **Sequence / Cadence** | A multi-step automated outbound email series | The unit of organization for sales_email; reply rate decays across the steps |
| **Open / Click / Reply / Bounce Rate** | Email open / click / reply / bounce ratios | Outbound health metrics; the fields are cumulative (click implies open) |
| **Gated Content** | Content that requires a form fill to access | Gated produces leads; ungated only nurtures |
| **NAICS** (North American Industry Classification System) | The North American industry classification code | The industry table uses it to tag customer industries |
| **NRR** (Net Revenue Retention) | Net revenue retention after expansion and churn | Measures whether existing customers grow or shrink; expressed indirectly here via expansion opps |

---

## 9. Key Metrics and Formulas

These are the core metrics that get computed over and over again in the SQL queries. The formulas are expressed in SQL-flavored pseudocode. Whenever a single metric has two common definitions, this document fixes one of them — so that downstream queries do not each invent their own and disagree.

### 9.1 Funnel Metrics (Q1)

```text
Lead -> MQL Rate   = COUNT(lead WHERE mql_date IS NOT NULL) / COUNT(lead)
MQL -> SQL Rate    = COUNT(lead WHERE sql_date IS NOT NULL) / COUNT(lead WHERE mql_date IS NOT NULL)
Overall Lead->Won  = COUNT(distinct leads that produced a won opp) / COUNT(lead)
Disqualification Rate = COUNT(lead WHERE status='disqualified') / COUNT(lead)
MQL Aging (days)   = handled: AVG(sql_date - mql_date); unhandled: REFERENCE_DATE - mql_date
```

Convention: whether a lead is an MQL is always determined by `mql_date IS NOT NULL`, not by the `status` field — because once a lead crosses MQL, its status keeps moving forward (sql / converted).

### 9.2 Campaign and Content Metrics (Q2)

```text
Cost per MQL       = campaign.spend_to_date_usd / (number of MQLs first-touched by this campaign)
Influenced Pipeline = SUM(opp.amount_usd)  -- the opp's account has any membership in this campaign
Pipeline ROI       = Influenced Pipeline / campaign.spend_to_date_usd
Spend Utilization  = spend_to_date_usd / total_budget_usd
Plan Achievement (MQL) = actual MQL count / campaign.target_mql_count
```

Convention: Cost per MQL uses the **first-touch** definition (`lead.source_campaign_id`), because it measures the leads the campaign itself directly pulled in. Influenced Pipeline uses the broader **account-level influence** definition. The two cannot be mixed.

### 9.3 Pipeline and Forecast Metrics (Q3)

```text
Open Pipeline      = SUM(opp.amount_usd) WHERE opportunity_stage.is_closed = 0
Weighted Forecast  = SUM(opp.amount_usd * opportunity_stage.typical_win_probability_pct / 100)  -- open opps only
Win Rate           = Wins / (Wins + Losses)   -- excludes open opps
Average Deal Size  = AVG(opp.amount_usd) WHERE is_won = 1
Median Sales Cycle = MEDIAN(actual_close_date - created_at) WHERE is_won = 1
Coverage Ratio     = Open Pipeline / SUM(active AE quota_usd)
Stale Rate         = COUNT(open opp WHERE MAX(transitioned_at) < REFERENCE_DATE - 30) / COUNT(open opp)
```

Convention: the Win Rate denominator only counts closed opps (won + lost) and excludes open opps — otherwise in-flight deals would dilute the rate.

### 9.4 Sales Productivity Metrics (Q4)

```text
Quota Attainment   = SUM(won opp.amount_usd) / sales_rep.quota_usd
Open / Click / Reply / Bounce Rate = SUM(corresponding boolean field) / COUNT(sales_email)
SLA Compliance     = COUNT(MQL WHERE first SDR email within 24 hours after mql_date) / COUNT(MQL)
Sequence Step Decay = SUM(replied) / COUNT(*)  GROUP BY sequence_step
Ramp Time (days)   = MIN(won opp.actual_close_date) - sales_rep.hire_date
```

### 9.5 Attribution and Unit-Economics Metrics (Q2 and CFO view)

```text
First-touch Pipeline (per source) = SUM(won opp.amount_usd) GROUP BY opp.source_id
W-shaped Credit (per campaign)    = SUM(opp.amount_usd * campaign_member.attribution_credit_pct / 100)
Blended CAC        = SUM(campaign.spend_to_date_usd) / COUNT(distinct won account)
CAC Payback (months) = CAC / (avg_arr / 12)
LTV/CAC            = (avg_arr * assumed retention years) / CAC
```

### 9.6 ABM Metrics (Q5)

```text
Stakeholder Coverage = COUNT(DISTINCT contact.persona)  -- per target account
No-Touch Days        = REFERENCE_DATE - MAX(engaged_at or sent_at)  -- per target account
Tier-1 ABM Win Rate  = Wins / Opps  -- Tier-1 target accounts only
Account Expansion    = COUNT(account WHERE COUNT(won opp) > 1)
```

A fuller BI dictionary for these formulas (with source tables and subject-area assignments) is expanded in the KPI dictionary section of the ER document. Only the core definitions needed to read the queries are listed here.
