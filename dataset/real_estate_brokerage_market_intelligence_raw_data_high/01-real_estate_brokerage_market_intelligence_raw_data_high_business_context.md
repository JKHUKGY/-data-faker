# Crestline Realty — Market Intelligence Raw Data: Business Context

> This document is the business context for the dataset `real_estate_brokerage_market_intelligence_raw_data_high`.
> It answers the "**why**": what kind of company this is, how it makes money, how its industry works, and what problem this data project is trying to solve.
> The "**what**" — table structures, fields, generation rules — lives in `02-real_estate_brokerage_market_intelligence_raw_data_high_er_document.md`.
> Runnable analytical queries live in `03-real_estate_brokerage_market_intelligence_raw_data_high_sql_queries.md`.

The intended reader is a brand-new intern or analyst on the project: no real estate background required, but after one read they should be able to follow the lingo at their first standup. The market is North America (California and Washington State in the US), the currency is USD, and the regulators are the US DRE, NAR, CFPB, etc.

---

## 1. The Company: Crestline Realty

**Crestline Realty** is a fictional mid-sized residential real estate brokerage headquartered in San Francisco, CA. It helps regular people buy and sell homes. It does **not** own homes itself — it is a licensed intermediary.

Size (order-of-magnitude, not a precise financial statement):

- **About 200 licensed real estate agents**, spread across three regional markets.
- **8 offices** covering the Bay Area, Southern California, and the Pacific Northwest (mostly the Seattle metro).
- Roughly **2,500–3,000 home transactions** closed per year.
- In each region it covers, Crestline's true on-the-street market share is only **2–3%** — it is a "challenger," not a market leader. The competitors are big names like Compass, Coldwell Banker, Keller Williams, Redfin, Berkshire Hathaway HomeServices, Sotheby's, RE/MAX, and Side.

Crestline's leadership is betting on one thing: **gain share by giving agents better data and tools**, instead of outspending or out-scaling the competition. That is the reason the "market intelligence platform" project behind this dataset exists.

Key people who show up repeatedly in the later SQL queries (company org chart):

| Role | Name | Responsibility |
|------|------|----------------|
| CEO | (unnamed) | Pitches the growth story to the board; cares about market-share trends |
| VP of Operations | Sarah Mitchell | Runs the weekly leadership meeting; watches deal volume, office scorecards, and lost-deal reasons |
| Bay Area Regional Manager | Rachel Torres | Manages front-line agents; tracks stale listings, pipeline velocity, and the quarterly "President's Club" rankings |
| Analytics Lead | Emily Zhang | Leads the analyst team on ad-hoc data pulls; in the middle of migrating Excel workflows to dashboards |
| Tech Lead | Marcus Rivera | Owns the data platform, natural-language querying, and AI analytics |
| Finance / Controller | (unnamed) | Builds commission payout cash-flow forecasts and payroll previews |

---

## 2. The Business Model: Commission, and Only Commission

Crestline's revenue is **100% commission**. Understanding this economic model is the key to understanding the dataset, because almost every table is tracking "a potential commission-generating transaction, and where it currently sits in the pipeline."

A typical closed deal splits its money like this:

1. When a home closes, a percentage commission is charged on the **sale price**, usually **5%–6%**. On a $1.2M home, the gross commission is roughly $60K–$72K.
2. That total is normally **split 50/50 between the listing agent and the buyer agent**. So each "side" gets about 2.5%–3%.
3. Each side's commission is then **split between the agent and the brokerage** (the commission split). A junior agent might keep 65%–72% with the brokerage keeping the rest; a senior agent might keep 80%–88%. That is what the `Commission_Split_Pct__c` field means in the data.

The brutal part of this model: **if the home doesn't close, nobody gets a dime**. Showing a property 20 times and then having the deal fall apart means those 20 showings were sunk cost. So a brokerage naturally cares about two things:

- **Conversion efficiency**: from lead to closed deal, how much does each layer of the funnel leak?
- **Unit economics**: is a given agent's output (deals × average price × split %) enough to justify the company resources they consume?

Order-of-magnitude on unit economics: average home prices of $700K–$1.2M with ~2.75% per side means **each closed deal brings the company roughly $20K–$35K in gross commission**, and more than half of that gets paid out to the agent. A top-producing senior agent can drive several hundred thousand dollars of GCI (see glossary) per year, while a long-tail junior agent might close only one or two deals all year. This **extremely uneven production distribution** — a small number of agents driving most of the revenue — is industry-standard and is deliberately baked into the data.

---

## 3. Industry Primer: How Residential Real Estate Brokerage Works

If you're coming from another industry, this section gets you to a point where you can hold a conversation with your coworkers about this market.

### What value the industry creates

Residential real estate brokerage matches "people who want to sell a home" with "people who want to buy one." The core problem it solves is **information asymmetry and trust**: sellers don't know what their home is worth, how to market it, or which buyers are real. Buyers don't know what's on the market, whether the price is fair, or how to negotiate and close. A licensed agent provides pricing guidance, marketing exposure, scheduling showings, negotiating, and steering the multi-week closing process (escrow). The payoff is the commission at closing.

### Main categories of players (no real names called out)

- **National chain brokerages**: largest, strongest brand, national coverage via franchise or company-owned offices.
- **Tech-driven brokerages**: lead with their app, instant valuations, and online workflows.
- **Regional independents**: like Crestline — go deep on a few metros, win on local relationships and service quality.
- **iBuyers / discount brokerages**: use algorithms to make fast all-cash offers, or compete on lower commissions.

### Regulatory framework (North America)

- **State licensing**: every agent must hold a license in the state they operate in. In California, the **DRE (Department of Real Estate)** issues licenses; the license number is what appears in the data as `DRE#####`. Washington State licenses via its Department of Licensing.
- **NAR (National Association of Realtors)**: the industry's self-regulatory body. It runs the local MLSs and sets the code of ethics. Agents who can call themselves "Realtors" are NAR members.
- **Fair Housing Act**: bans discrimination in buying, selling, and renting based on race, religion, sex, etc.
- **RESPA (Real Estate Settlement Procedures Act)**: regulates closing/settlement procedures and prohibits illegal kickbacks.
- **CFPB (Consumer Financial Protection Bureau)**: oversees consumer protection on mortgage-related matters.

### Macro forces shaping the industry right now

- **Mortgage rate shock**: between 2022 and 2023, the Fed's hiking cycle drove 30-year fixed mortgage rates from ~3% to a peak of ~7.79% in October 2023. More expensive borrowing froze transaction volumes.
- **Lock-in effect**: many homeowners are locked into 3% mortgages from earlier years and are unwilling to sell and take on a new 7% loan. The result is collapsing listing inventory — but **prices have barely fallen** (low volume, stable prices).
- **Commission rule changes**: the 2024 NAR settlement changed how buyer-side commissions are disclosed and negotiated. Industry-wide commission rates are under pressure.
- **AI and data**: natural-language data querying, listing-to-buyer smart matching, and automated market reports are becoming the new competitive front for brokerages — and that's exactly where Crestline is placing its bet.

### A deal from start to finish (the source of nearly every row in the dataset)

1. **A homeowner decides to sell**, hires a listing agent. The agent visits the home, recommends a price, signs a listing agreement, and **enters the home into the MLS** (see next section). → This produces one row in `mls_listing` with status `ACT` (Active).
2. **Other agents' buyers discover the listing**, schedule **showings**. → This produces rows in `mls_listing_showing`.
3. **When interest is cold the seller does a price reduction** to attract attention. → This creates a `PRICE_CHANGE` event in `mls_listing_event_history`.
4. **A buyer makes an offer**, the parties agree and sign a contract, and the listing status flips from `ACT` to `PND` (Pending). → Enters a 30–45 day escrow period: inspection, loan approval, title search.
5. **Closing completes**, status flips to `SLD` (Sold), money changes hands, and the agent receives the commission a week or two after closing. → This produces a row in `mls_sold_transaction`.
6. **Sometimes the deal falls through**: inspection issues, the loan doesn't fund, the seller backs out. Status flips back to Active, or becomes `EXP` (Expired) or `WTH` (Withdrawn). **Roughly 15%–25% of listings never actually close.**

### Three kinds of data sources: MLS, CRM, External

The key to understanding this dataset is understanding that it stitches together three fundamentally different kinds of data:

- **MLS (Multiple Listing Service) — public, market-wide.** A regional, **industry-shared** "all properties currently for sale" database operated by the local Realtors association. It is **not owned by any single brokerage**. When an agent lists a home, they must enter it into the MLS so other agents in the region can bring their buyers to see it. Key implication: when Crestline pulls MLS data, it sees **every listing from every brokerage in the region** — both its own (about 30% of the dataset) and competitors' (about 70%). That's why you can compute things like "our market share in a given zip" or "how our pricing compares to the competition's."
- **CRM (Customer Relationship Management system; Salesforce-style in this dataset) — private, Crestline-only.** The opposite of MLS: this is Crestline's own private data — captured leads, follow-up activity, sales pipeline, agent activity logs, internal commission accounting. **Competitors cannot see it.** The CRM is where Crestline's competitive advantage lives.
- **External — public, macro context.** Internal data tells you what Crestline did; external data tells you **what the rest of the world was doing at the same time**. If sales dipped in a given quarter, was that a Crestline problem, or was it because mortgage rates spiked to 7.79%? Without external context you can't tell. The four external sources used here: Zillow Home Value Index (ZHVI), Zillow Market Temperature, Freddie Mac mortgage rates, Census/BLS demographics, and Walk Score.

Joining these three together is what turns "raw operational data" into **market intelligence**.

---

## 4. Project Background: The Market Intelligence Platform

**Your role**: you're an analyst / BI engineer on Crestline's data team (intern or full-time, either works). You report to the Tech Lead (Marcus Rivera) and the Analytics Lead (Emily Zhang). Your work ultimately serves the VP of Operations (Sarah Mitchell) and the CEO.

**What you're building**: an internal data product called the **Market Intelligence Platform**. The goal is to ingest the three categories of raw data above (MLS / CRM / External) into a warehouse (the project assumes AWS Redshift with three raw schemas: `raw_mls`, `raw_crm`, `raw_external`), clean and model it with dbt, and ultimately power a set of analytics and AI capabilities.

This dataset is the **raw data layer** of that platform. It deliberately stays **source-faithful** — it preserves MLS-style field names (`LIST_PRICE`, `STATUS_CD`, `DOM`), Salesforce-style suffixes (`__c`, `LastModifiedDate`), source-system status codes (`ACT`/`PND`/`SLD`), and a small amount of real dirty data (ZIP+4 formatting, near-duplicate contacts, brokerage-name spelling variants). That way the downstream dbt staging layer has real cleaning, standardization, and cross-domain joins to do, and dbt tests have something meaningful to assert.

The platform supports several workstreams (called Module 1–4 internally). They help you understand who each query serves:

- **Module 1 — dbt modeling and tests**: turn raw into staging → intermediate → mart, e.g., agent-performance mart, customer-intelligence mart.
- **Module 2 — BI dashboards and the weekly auto-report**: the Market Pulse dashboard, the Agent Scorecard, the auto-generated weekly market report pipeline.
- **Module 3 — Natural-language querying and smart matching**: let agents query the database in plain English; recommend listing-buyer matches via embeddings.
- **Module 4 — Daily competitive-positioning AI analysis**: an AI agent that scans the market every day, flags overpriced or stale listings, and surfaces opportunities.

**Deliverables**: leadership dashboards, the quarterly deck for the board and investors, the auto-generated weekly report for managers, and cash-flow forecasts for Finance.

---

## 5. Business Problems to Solve

The entire platform and this dataset exist to answer the following questions — questions Crestline really does ask. Every SQL query in the queries document later on traces back to one of these.

1. **Is the pricing right (Pricing)**: when we list a 3BR in Palo Alto at $2.4M, is that the right price? What did comparable homes in the same zip and property type sell for last quarter? Which listings keep getting price-reduced, indicating we systematically priced too high? Which sale prices come in well above Zillow's fair value — i.e., positive examples of our pricing skill?
2. **Who are the top-producing agents, and why (Performance)**: among our 200 agents, who has the highest GCI? Is it because their conversion rate is higher, or just because they make 5x more outreach calls? Does income really rise with tenure (should we re-tune the tier commission structure based on that)?
3. **Is the market heating up or cooling down (Market temperature)**: how is days-on-market and sale-to-list ratio trending in a given zip? Should we tell sellers to "list now" or "wait six months"?
4. **Where are the opportunities (Opportunity discovery)**: are there zips where we have few listings but buyer demand is strong (lots of showings)? Those are places to hire more agents or open a new office. Is our share of listings in each zip trending up or down year over year?
5. **Where is volume headed and how will cash flow (Forecast & cash flow)**: with rates parked at 6.7%, what's the deal-volume forecast for next quarter? How much commission needs to be paid out in the next 30 days, and to whom?
6. **Customer matching and data quality (Matching & data quality)**: for each of the 5,000 buyer contacts in CRM, which currently active listings are they likely interested in? How many duplicate contacts in CRM do we need to dedupe before building the mart? Why are we losing deals?

Answering nearly every one of these questions requires **joining data across the MLS / CRM / External domains**. That is exactly why the dataset is organized this way.

---

## 6. Data Scope Overview

- **Time window**: 2023-01-01 to 2026-06-05, about **3.4 years / 42 months** of history.
- **REFERENCE_DATE (the effective "today") = 2026-06-05**. In the data, "today," "currently active," and "the last 12 months" all anchor to this date. All SQL queries use the literal `'2026-06-05'` rather than `date('now')`, to keep results reproducible.
- **Geography**: 3 markets (Bay Area / SoCal / PNW), 12 counties, 30 cities, **60 zip codes** (~20 per market). Each zip is pre-tagged with a temperature label of HOT / STABLE / COOL that drives realistic differences in days-on-market and sale-to-list ratio. 60 zips is the sweet spot for analysis: enough to demo a zip-level dashboard, while keeping the total row count around ~330K and the generation time within minutes.
- **Data volume**: **23 tables, around 328,000 rows**. The biggest tables are showings (~72K), listing events (~65K), agent activity (~50K), listings (~40K), and properties / walk scores (~25K each).
- **Crestline's share in the data**: to give internal analytics enough sample size, **~30% of the in-scope MLS listings carry Crestline branding**, with the remaining ~70% coming from 8 competitors. (Note: this 30% is an in-scope share chosen for analytical convenience and is different from the 2–3% true on-the-street share mentioned in Section 1 — the latter is Crestline's actual competitive position in the broader market.)
- **Deliberate scope choices**: residential only, no commercial; US / USD only; macro rates only, no loan-level data; no infrastructure logs, no dbt models themselves, no dashboard configs (those are project deliverables, not raw data).
- **Deliberate dirty data**: ZIP+4 formatting (~5%), NULL email/phone, mixed phone formats, near-duplicate contacts (~3%), 5 spelling variants for the Crestline brokerage name, stray whitespace/casing issues. The point is to give the downstream cleaning layer real work to do.

---

## 7. Glossary (English term + plain-English explanation)

For every piece of jargon that shows up in the ER document or the SQL queries, here's a one-line plain-English explanation plus a one-line "why it matters here."

| Term | Plain-English | Why it matters in this dataset |
|------|---------------|--------------------------------|
| **MLS** (Multiple Listing Service) | A regional database of all properties currently for sale, shared among agents and run by the local Realtors association. | The source of the `mls_*` tables; contains the entire market (including competitors), which is the basis for computing market share and comparable prices. |
| **CRM** (Customer Relationship Management) | The company's own customer/sales-management system — Salesforce-style here. | The source of the `crm_*` tables; private to Crestline and the seat of its competitive advantage. |
| **agent / listing agent / buyer agent** | A licensed real estate agent; representing the seller and the buyer, respectively. | `crm_agent`, the various `*_AGENT_LICENSE` fields; commissions and performance hang off the agent. |
| **brokerage** | A brokerage firm (such as Crestline) that employs agents and shares commissions with them. | `LISTING_OFFICE_NAME`, `crm_office`; the key for telling us-vs-competitor apart. |
| **DRE number** | A California real estate license number (issued by the Department of Real Estate). | `License_Number__c` and `LISTING_AGENT_LICENSE` are joined on it to bridge MLS ↔ CRM. |
| **listing** | A single listing event (a particular home being put on the market at a particular time). | `mls_listing`; one home can be listed multiple times, so listing ≠ property. |
| **property** | A physical property (address + physical attributes), persistent across multiple listings. | `mls_property`; the parent entity of a listing. |
| **DOM** (Days on Market) | How many days a listing sits on the market before it closes or comes off. | The core market-heat metric; HOT zips have low DOM, COOL zips have high DOM. |
| **list price / sale price** | The asking price / the final closing price. | Their ratio is the SLR, which shows which side of the table holds the leverage. |
| **SLR** (Sale-to-List Ratio) | Sale price ÷ list price. >1 means buyers are bidding it up; <1 means the seller gave ground. | `LIST_TO_SALE_RATIO`; the best leading indicator of market temperature. |
| **status code (ACT/PND/SLD/EXP/WTH)** | Listing status: Active / Pending / Sold / Expired / Withdrawn. | `STATUS_CD`; the source-faithful enum from the source system, which dbt must standardize. |
| **escrow** | The 30–45 day period between signing the contract and closing (inspection, loan approval, title search). | `mls_pending_sale`; the gap between contract and close. |
| **contingency** | A clause in the contract that lets a party walk away (e.g., if the inspection fails or the loan doesn't fund). | `CONTINGENCIES`; a risk marker on pending homes. |
| **pending** | The state of having a signed contract while waiting for closing. | `mls_pending_sale` is a snapshot as of REFERENCE_DATE. |
| **lead / contact / opportunity** | A lead / a contact record / a specific sales opportunity (with a pipeline stage). | `crm_contact`, `crm_opportunity`; the three granularities of the sales funnel. |
| **pipeline stage** | An opportunity's stage in the funnel: Lead → Qualified → Showing → Offer → Under Contract → Closed Won/Lost. | `StageName`; the basis for pipeline velocity and conversion analysis. |
| **Closed Won / Closed Lost** | An opportunity that won (closed deal) / lost (dead). | A win produces a transaction; a loss carries a `Lost_Reason__c`. |
| **GCI** (Gross Commission Income) | The total commission an agent (or an office) takes home over a period. | The core metric for agent rankings and tier compensation policy. |
| **commission split** | The proportion in which the agent and the brokerage divide one commission. | `Commission_Split_Pct__c`, `crm_commission_split`; senior agents keep more. |
| **tier (JUNIOR/MID/SENIOR)** | The agent's seniority tier, which determines their split. | `Tier__c`; correlates positively with tenure and income. |
| **tenure** | The number of years an agent has been with the company. | Computed from `Hire_Date__c`; a key driver of production and split. |
| **co-list** | Two agents jointly representing one transaction and splitting the commission. | `crm_commission_split` will have two rows for one transaction in ~10% of cases. |
| **showing** | A single in-person viewing of a home with a client. | `mls_listing_showing`; the buyer-demand signal source. |
| **price reduction** | The seller dropping the price. | A `PRICE_CHANGE` event in `mls_listing_event_history`; a signal of overpricing. |
| **ZHVI** (Zillow Home Value Index) | Zillow's index of the typical home value for an area. | `ext_zillow_home_value_index`; the market-level fair-value baseline. |
| **market temperature** | Whether a zip is currently hot (bidding wars) or cold (concessions). | The HOT/STABLE/COOL tag on the zip, plus `ext_zillow_market_temperature`. |
| **PMMS** (Primary Mortgage Market Survey) | The weekly Freddie Mac mortgage-rate survey. | `ext_freddie_mac_mortgage_rate`; the macro factor explaining volume swings. |
| **mortgage rate (30Y fixed)** | The 30-year fixed mortgage rate — the core cost of homebuying. | `Rate_30Y_Fixed`; the 7.79% peak in October 2023 explains the 2024 volume drop. |
| **lock-in effect** | Homeowners locked into low-rate old mortgages, unwilling to sell and take on a high-rate new mortgage. | Explains why 2024 volumes dropped while ZHVI still grew ~4% YoY. |
| **financing type (CASH/CONVENTIONAL/FHA/VA/JUMBO)** | How the buyer is paying / financing. | `FINANCING_TYPE`; the cash share reflects how high-end the market segment is. |
| **Walk Score** | A walkability/transit/bike-friendliness score for an address (0–100). | `ext_walk_score`; urban-core addresses score high. |
| **DGT / GTV (Gross Transaction Value)** | Total dollar value of homes sold during a period. | The dollar denomination for volume dashboards (`SUM(SALE_PRICE)`). |
| **source-faithful** | The data preserves the source system as-is (including dirty data), without pre-cleaning. | The design principle of the entire raw layer — so that dbt has real work to do. |

---

## 8. Key Metrics and Formulas

The following metrics either show up in the SQL queries or are things readers need to have in mind. Definitions are spelled out here to avoid downstream teams computing the same metric two different ways.

```
# Market temperature
DOM (Days on Market)        = STATUS_DT - LIST_DT             # Units: days; per listing
SLR (Sale-to-List Ratio)    = SALE_PRICE / LIST_PRICE         # >1 = over asking, <1 = concession
                                                              # Dataset is layered by temperature: HOT~1.04, STABLE~1.00, COOL~0.96

# Deal volume
GTV (Gross Transaction Value) = SUM(SALE_PRICE)               # Total dollar value of closes for a period/group
sold_count                    = COUNT(closed listings)         # Number of homes closed
median_sale_price             = median, grouped by (zip, property_type)

# Year-over-year
YoY % = 100 * (current period - same period last year) / same period last year   # Use LAG() window for prior year

# Commission (core — note the three-layer split)
Gross_Commission = Sale_Price * Commission_Rate_Pct / 100     # Gross commission per side; rate is 2.5%–3.0% per side
Agent_Take       = Gross_Commission * Split_Pct               # Agent's keep; Split by tier 0.65–0.88
Company_Take     = Gross_Commission * (1 - Split_Pct)         # Company's keep
GCI (per agent)  = SUM(Agent_Take over window)                # Agent commission income; Q3 uses trailing 12 months, Q15 uses all-time cumulative

# Market share
Crestline_Share_Pct (zip, year) = 100 * crestline_listings / total_listings   # Listing share for a zip in a year
                                                              # crestline_listings = count of listings where IS_CRESTLINE_LISTING is true

# Sales funnel
close_rate_pct   = 100 * closed_won / total_opportunities     # Opportunity win rate
demand_signal    = tag an active listing based on showings count and offers count
                   (HIGH_INTEREST_NO_OFFER / LOW_DEMAND / OFFERS_RECEIVED / NORMAL_FUNNEL)

# Stale listing rule (Module 4 threshold)
is_stale = (REFERENCE_DATE - LIST_DT) > zip_median_DOM * 1.5  # Past 1.5x the zip's median DOM is stale
```

Definitional conventions (to avoid ambiguity):

- **Always state the time window for GCI**: Query 3 (Top GCI) uses **trailing 12 months** (filtered by `Payout_Date__c`); Query 15 (tenure vs. income) uses **agent all-time cumulative** (3.4 years), so Q15's absolute dollar figures are roughly 3–4x Q3's. The same agent appearing with different numbers in the two queries is a window difference, not a data contradiction.
- **Agent attribution on commission_split**: the primary split row hangs off the opportunity's **owner agent** (not a random agent), so the tenure-weighted production signal flows through all the way to the GCI ranking.
- **Market share uses listing count, not dollar volume**: Query 20's share is computed as a share of "number of listings," reflecting how many seller engagements Crestline won in a given zip.
- **SQLite has no built-in median function**: medians are computed by hand with `ROW_NUMBER() / COUNT()` window functions (see Query 2).

---

> After reading this business context, you should be able to answer: who Crestline is, how it makes its money from commission, how the residential brokerage industry runs, why MLS/CRM/External data need to be joined, and what the 6 categories of business questions this platform is meant to answer. Next, go to `02-...er_document.md` to see how these questions map to specific tables and fields, then on to `03-...sql_queries.md` to see how an analyst pulls them out one query at a time.
