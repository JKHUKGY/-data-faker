# Media & Entertainment — Anime IP Merchandise Licensing & Retail Sell-Through Analysis: Business Context

> This document is the business-context write-up for the `media_anime_ip_licensing_retail_medium` dataset. Its job is to answer "what kind of company is this, what business is it in, and what problem are we solving." For the data structure, see `02-media_anime_ip_licensing_retail_medium_er_document.md`; for SQL queries, see `03-media_anime_ip_licensing_retail_medium_sql_queries.md`.
>
> Assumed reader: you're a smart new hire who just joined the project. You don't need to know anything about the anime industry or consumer-product licensing going in. By the end of this document, you should be able to explain the company's business, its industry, and the questions this analysis is meant to answer at your first stand-up.

---

## 1. Company Profile

**Ember & Ash Licensing Group** is a fictional North American entertainment-IP licensing agency headquartered in El Segundo, California, founded in 2016. It doesn't manufacture anything and doesn't own any anime copyrights — its business is being the middleman: on behalf of anime rights holders, it licenses anime IP to manufacturers willing to produce merchandise (licensees) across the North American market, and takes a cut of those manufacturers' wholesale sales.

Company profile (order of magnitude, not exact figures):

- **Headcount:** roughly 45 people, including a team of licensing managers (who own licensee relationships and contract negotiations), a retail channel analytics team, a royalty audit team, plus legal and finance.
- **Revenue:** across the company's entire portfolio (not just anime — it also handles a small amount of other entertainment IP) and its entire book of historical contracts, **gross royalty flow received from licensees** runs on the order of $60 million — this is gross flow-through, not net income. Most of it gets passed along to anime rights holders under the master licensing agreements (see Section 6); Ember & Ash's own retained commission revenue is far smaller than this headline figure.
- **Scope of this dataset:** it focuses on a representative analytical slice of the company's **anime category** that has been active over roughly the last 22 months — 24 anime IP titles, 32 licensees, 117 license agreements. This is not the company's full ledger across every category and every historical contract; it's a representative sample built to support anime-category renewal decisions, audits, and channel-compliance calls (see Section 6, "Data Scope," for details).
- **Geography:** licensees are headquartered in major U.S. and Canadian cities (Los Angeles, New York, Chicago, Toronto, Vancouver, Denver, and others), and their retail sales footprint spans both the U.S. and Canada.

Roles relevant to this analysis (SQL queries reference these people by title):

| Title | What They Care About |
|------|----------|
| VP of Licensing | Overall IP portfolio strategy, renewal/termination decisions, annual licensing revenue targets |
| Licensing Manager / Senior Licensing Manager | Licensee relationships and renewal negotiations for their own book of contracts |
| Director of Licensing | Cross-manager portfolio performance, escalation of problem contracts |
| Retail Channel Analyst | Retail sell-through performance by category/channel, channel licensing compliance |
| Royalty Audit Specialist | Gaps between licensee self-reported royalties and audit-derived royalties from actual sell-through |
| Director of Royalty Compliance | Audit policy design, escalation of unauthorized-channel sales and underreporting |

---

## 2. Business Model

Ember & Ash makes money as a **royalty licensing agency**: it doesn't manufacture, doesn't hold inventory, and doesn't sell directly to consumers. It earns revenue through licensing plus a cut of sales.

Here's how the process works:

1. Ember & Ash signs a **license agreement** with a licensee (typically a North American manufacturer or distributor in toys, apparel, collectible trading cards, or similar categories), granting merchandising rights to a given anime IP within a defined product category, retail channel scope, and territory, usually for a term of 12 to 36 months.
2. The licensee pays Ember & Ash a share of the wholesale revenue it earns selling merchandise to retailers, based on the contract's **royalty rate** (roughly 7% to 12% of net wholesale sales). (That 7%–12% range is the **category benchmark**; the actual rate on any given contract will flex above or below the benchmark depending on negotiation, so actual rates across the full dataset fall in roughly the 5.5%–13.5% range.)
3. Most contracts also carry a **minimum guarantee (MG)** — regardless of how well the licensee's products actually sell, they owe at least this much in royalties over the life of the contract. This is Ember & Ash's protection against downside risk. (Note this is the **total floor for the entire contract term** — to judge whether a given contract is "on pace" at any point in time, you can't just compare cumulative royalties directly to this total; you first have to prorate it by how much of the contract term has elapsed. See the MG proration logic in Sections 7 and 9.)
4. Each "contract quarter" (a 91-day period counted from the contract start date, not a calendar quarter), the licensee self-reports net sales and royalties owed, Ember & Ash collects payment, and then passes along its agreed share to the anime rights holder.

At the unit-economics level, the price a piece of merchandise is sold wholesale from manufacturer to retailer follows the consumer-products industry convention of a **"keystone" markup** — wholesale price is roughly 50% of the manufacturer's suggested retail price (MSRP). Royalties are calculated only on **net wholesale sales**, not on what the end consumer actually pays at retail. This "wholesale vs. retail" distinction is the first thing you need to understand before any dollar figure in this dataset will make sense.

So the company's profitability ultimately comes down to three things:

1. **Picking the right IP and the right categories** — betting on anime that will take off, renewing portfolios that keep selling, and cutting ones that don't.
2. **Whether royalties are being collected correctly** — whether licensees are honestly reporting their real sales.
3. **Whether licensees are staying in bounds** — whether they're quietly selling into channels the contract doesn't authorize.

---

## 3. Industry Primer: North American Entertainment IP Merchandise Licensing

If you're coming from a different industry, this section will get you up to speed on how this business works.

**What value does this industry create?** Entertainment IP — anime, film, games — commands enormous fan bases, but rights holders themselves typically aren't good at, or interested in, directly manufacturing physical goods like toys or apparel. That requires an entirely different supply chain, tooling and factories, and retail-channel relationships. A **licensing agent** fills that gap: it understands IP and fan culture on one side, and consumer-product manufacturing and retail distribution on the other, and connects the two. It also handles contract negotiation, brand-tone gatekeeping, and the piece that's easiest to overlook but just as important — **royalty auditing**.

**Categories of players (no real companies named).**

- **IP owner / licensor:** the anime studio or the holder of its North American distribution rights. Owns the IP but typically doesn't want to manage the day-to-day contract details of dozens of manufacturers.
- **Licensing agent:** a middleman like Ember & Ash, managing a portfolio of licensees on the rights holder's behalf and earning a royalty cut.
- **Licensee:** the manufacturer or distributor that actually makes the product, specialized by category (toys, apparel, collectible cards, home goods, etc.).
- **Retailer:** big-box chains, specialty stores, e-commerce platforms, and the like, which buy wholesale from licensees and sell to consumers.

**Regulatory and compliance framework (North America).** Consumer-product licensing doesn't have a dedicated federal regulator the way finance or healthcare does, but it's still governed by a few general frameworks:

- **CPSC (Consumer Product Safety Commission):** safety standards for toys and children's products, which especially affect SKUs aimed at kids.
- **Trademark and copyright law:** a license agreement is fundamentally permission to use copyright- or trademark-protected IP assets; using it outside the contract's bounds is infringement.
- **State consumer-protection laws and Canadian equivalents:** baseline compliance requirements for advertising and product labeling.
- **Audit rights under contract law:** nearly every license agreement grants the agent the right to audit the licensee's sales records — this is the contractual basis for the "royalty audit" line of business that this dataset is built around.

**Macro forces at play right now.** The North American anime audience has grown quickly over the past few years, driving up the size of the merchandise market. At the same time, e-commerce channels have made "gray-market resale" and "unauthorized channel leakage" harder to track — even retailers themselves often don't know which supply chain a given batch of product actually came from. Because the licensee self-reporting system is inherently "grading your own homework," there's a built-in incentive to underreport, which is why royalty auditing has become an increasingly important function for licensing agents.

---

## 4. Project Framing: What You're Doing

You're a **newly hired data analyst** at Ember & Ash — the company's first dedicated data role — reporting directly to the **VP of Licensing**, while also supporting the licensing manager team, retail channel analysts, and royalty audit specialists.

Before you arrived, these three lines of business (renewal decisions, channel compliance, and royalty audits) each made judgment calls off of scattered data in spreadsheets and emails, with no unified analytical framework. The VP's mandate to you is to bring together roughly 22 months of license agreement, retail sell-through (POS), and royalty self-report/audit data, use SQL to answer five core business questions clearly, and produce findings that can directly support quarterly portfolio reviews and licensee renewal negotiations.

Deliverables: a quarterly IP portfolio review deck, a renewal-priority list, a list of royalty-audit issues, and a channel-compliance escalation list. All analysis is anchored to a fixed reference date, **REFERENCE_DATE = 2026-06-30** (see Section 6 for details).

---

## 5. Business Questions This Project Answers

The entire dataset is designed to answer the five core business questions below. Each question maps to a corresponding data trap or data signal in the ER document, and a corresponding query in the SQL queries document.

1. **Q1 Sell-Through & Renewal Priority:** Which "IP x category" combinations have the strongest retail sell-through and deserve priority renewal at longer terms or broader scope? Which combinations have been persistently weak and should be cut when their contracts expire?
2. **Q2 Royalty Audit & Underreporting Risk:** How much does a licensee's self-reported royalty differ from the royalty derived from actual retail-terminal POS data? Which licensees are systematically underreporting?
3. **Q3 Popularity-to-Sell-Through Lag:** After an anime title peaks in streaming popularity (say, a new season premiere), how long does it take before that shows up as a meaningful lift in retail merchandise sales? What does that lag mean for restocking plans?
4. **Q4 Unauthorized Channel Compliance:** Are any licensees selling into retail channels not covered by their license agreement? Is that revenue getting miscounted as "compliant revenue," distorting performance evaluation?
5. **Q5 Minimum Guarantee Pacing:** Which active contracts have cumulative royalty progress lagging behind their time-prorated minimum guarantee (MG) target, and need to be reassessed before renewal negotiations?

Beyond these five marquee questions, the dataset also supports a range of operational analyses — licensee portfolio health, channel authorization coverage, licensing manager contract-load distribution, category royalty-rate comparisons — used to answer day-to-day operational and portfolio-management questions.

---

## 6. Data Scope Overview

- **Time span:** license agreement signing dates fall within roughly a 22-month window (from about 680 days before REFERENCE_DATE to about 150 days before it). Streaming popularity indices are tracked for an additional six-plus months beyond that, covering roughly **2 years and 105 weekly data points** in total (a 104-week window before REFERENCE_DATE, inclusive of both endpoints), because Ember & Ash needs to start tracking popularity before an anime title takes off in order to judge whether it's worth licensing. All "today / current snapshot" semantics are anchored to the fixed reference date **REFERENCE_DATE = 2026-06-30**.
- **Data volume (order of magnitude, plain terms):** 24 anime IP titles, 32 licensees, 117 license agreements, roughly 750 merchandise SKUs, roughly 46,000 rows of weekly retail-terminal sell-through records, roughly 370 royalty self-reports with matching audit results — about 51,000 rows in total.
- **Deliberate scoping decisions:**
  - **Anime category only:** the company also licenses a small amount of non-anime IP, which isn't included here, to avoid mixing business logic across categories.
  - **Only recently signed / active contracts from the last ~22 months:** this is not the company's full historical book of contracts — it's the "active portfolio" slice that's most relevant to current analysis.
  - **No modeling of downstream rights-holder pass-through:** after Ember & Ash collects royalties from a licensee, it passes a portion along to the anime rights holder under its own master licensing agreement — but that step is out of scope for this dataset. The dataset covers the "licensee → Ember & Ash" leg only, not the "Ember & Ash → anime rights holder" leg.

(This section doesn't list specific tables; see the ER document for table structure.)

---

## 7. Industry Knowledge Primer

About half an hour's worth of background you'll need before this data will make sense. It's easiest to understand by walking through "the life of a license agreement."

**1) The six stages of a license agreement.**

```
Signed → Contract Start → Product Development & SKU Launch
   → Retail Sell-Through (POS) → Quarterly Royalty Self-Report → Audit
```

- **Signed:** Ember & Ash and the licensee agree on the IP, category, channel scope, territory, royalty rate, and minimum guarantee, and sign the contract.
- **Contract start:** the contract's effective start date is typically 1–2 months after signing, giving both sides time for legal and logistics prep.
- **Product development and SKU launch:** the licensee designs, prototypes, and manufactures the product. It typically takes another 2–4 months from contract start before a SKU is actually on shelves.
- **Retail sell-through:** merchandise sells week over week through authorized retail channels, generating POS (point of sale) records.
- **Quarterly royalty self-report:** within 15–45 days after each "contract quarter" ends (a 91-day period counted from the contract start date, not a calendar quarter), the licensee calculates its net sales and reports the royalty it owes.
- **Audit:** Ember & Ash uses independent retail data (POS) to back into the "true" royalty owed and compares it against the licensee's self-reported figure to flag discrepancies.

**2) Royalty rate and minimum guarantee.** The royalty rate is the share of a licensee's net wholesale sales owed to Ember & Ash, and industry norms vary by category (collectible cards and toys, which have high repeat-purchase rates and moderate price points, typically run 10%–12%; home goods and stationery, which are more competitive and thin-margin, typically run only 7%–9%). Keep in mind these ranges are **category benchmarks** — the actual rate on any individual contract will flex roughly ±1.5pp above or below the benchmark, so actual rates across the full dataset fall in roughly the 5.5%–13.5% range. Don't force the benchmark value onto any specific contract when analyzing real rates. The **minimum guarantee (MG)** is the royalty floor a licensee must pay over the life of the contract regardless of how well or poorly their products sell — essentially Ember & Ash's hedge against the risk that a given IP just doesn't sell. The minimum guarantee is typically **prorated** by the fraction of time elapsed since contract start: however much of the contract term has elapsed is the fraction of the minimum guarantee that should have been paid in cumulatively by now.

**3) Wholesale vs. retail, and the "keystone" markup.** **Wholesale price is roughly 50% of MSRP** — a convention the industry calls "keystone" markup. Royalties are calculated only on net wholesale sales, and understanding this matters — don't mistake MSRP for the royalty calculation base.

**4) Three dimensions of license scope.** A license agreement simultaneously restricts three things: **product category** (toys only, not apparel), **retail channel** (big-box chains and specialty stores only, no e-commerce), and **territory** (U.S. only, or U.S. and Canada both). Together, these three dimensions define the boundary of "compliant sales" — crossing any one of them constitutes unauthorized channel leakage.

**5) POS and sell-through rate.** POS (point of sale) data is the actual sales record at the retail terminal, and it's a different thing from "the licensee shipping product to a retailer" — a licensee's shipments could just be sitting unsold in a retailer's warehouse. **Sell-through rate** measures "how fast product moves once it's on the shelf," which is the key indicator of whether an IP x category combination is genuinely popular — a far better read on real market demand than shipment volume.

**6) Streaming popularity index and retail lag.** When an anime title heats up on streaming platforms (say, a spike in search volume and watch time from a new season premiere), that doesn't show up on retail shelves instantly — retailers need to see the popularity signal, place reorders, and let the supply chain work through the restocking process, which typically means a **lag of several weeks** before it shows up as an actual sales increase. Understanding this lag is what determines whether Ember & Ash should be pushing licensees to stock up as soon as a title starts heating up, rather than waiting.

**7) Self-reporting and audits.** A licensee's royalty report is fundamentally "grading their own homework" — they're both the party selling the product and the party calculating and reporting the numbers, which creates a built-in incentive to underreport (report less in sales = owe less in royalties). The value of an audit is using an independent data source the licensee can't manipulate (retail-terminal POS) to back into what they "should" owe, and catching the gap between the self-reported number and the real one.

---

## 8. Glossary

Every piece of jargon that shows up in the ER document or the SQL queries gets a plain-language explanation here, plus a note on why it matters for this project. Terms are kept in their original English form throughout.

| Term | Plain-Language Explanation | Why It Matters Here |
|------|----------|----------------------|
| Licensor | The rights holder — the party that owns the IP | Ember & Ash manages the licensee portfolio on the licensor's behalf |
| Licensing agent | The middleman connecting the licensor and licensees | Ember & Ash's own business-model position |
| Licensee | The company that actually manufactures/sells the merchandise | The core entity of the `licensee` table, and the driver behind traps 2 and 4 |
| License agreement | The licensing contract | The `license_agreement` table — the core record of contract terms |
| Royalty | The fee paid to the rights holder as a share of sales | The core financial concept underlying the entire dataset |
| Royalty rate | The royalty percentage | The key parameter determining royalty owed |
| Minimum guarantee (MG) | The floor for royalty payments over the contract term | The core metric for Q5 |
| Proration / prorated | Scaling a total by elapsed time | MG pacing progress must be prorated by elapsed contract time — you can't compare cumulative totals directly |
| Territory | Geographic scope (U.S., Canada, or both) | One of the three dimensions of license scope |
| Product category | Category (toys, apparel, cards, etc.) | One of the three dimensions of license scope, and also a driver of royalty-rate differences |
| Retail channel | Retail channel (big-box, specialty, e-commerce, etc.) | One of the three dimensions of license scope, and the core dimension for Q4's unauthorized-channel analysis |
| Channel authorization | Which channels a contract permits sales through | The basis for judging whether Q4's unauthorized sales occurred |
| MSRP | Manufacturer's Suggested Retail Price | Not the royalty calculation base — a common mistake for newcomers |
| Wholesale price | The price a manufacturer sells to a retailer at | The actual base for royalty calculations |
| Keystone markup | The wholesale-to-retail "half-off" markup convention (wholesale price ≈ 50% of MSRP) | Explains how `wholesale_price_usd` values are derived |
| Net wholesale sales | Net wholesale sales revenue | The base used to calculate the royalty rate |
| POS (Point of Sale) | Retail-terminal sales data | The "independent source of truth" for audits and sell-through analysis |
| Sell-through rate | How fast product moves once it's on the shelf | The key metric for judging whether an IP x category combination deserves renewal in Q1 |
| SKU (Stock Keeping Unit) | The smallest unit of inventory — a single specific product | The granularity of the `product_sku` table |
| Royalty report | The royalty flow a licensee self-reports each quarter | The "self-reported" side of trap 2 |
| Royalty audit | Verifying self-reported figures using independent data | The "verification" side of trap 2 |
| Variance | The gap between self-reported and audit-derived figures | The core metric of audit conclusions |
| Streaming popularity index | This dataset's weekly streaming popularity index (0–100 scale) | The leading indicator for the Q3 lag analysis |
| Season premiere | A new season's premiere | The typical event that triggers a popularity spike |
| Lag / lead time | The lag period | The core concept for Q3 — how many weeks a popularity peak leads a retail sales peak |
| Compliance score | A licensee's compliance score (0–100) | An internal field on the `licensee` table that drives the cohort split behind traps 2 and 4 |

---

## 9. Key Metrics and Formulas

Below are the metrics used in the SQL queries, or that readers should be aware of. Formulas are written as plain-language, SQL-style pseudocode, with notes on inputs and conventions.

**Sell-Through and Renewal**

```
weekly_sell_through_units(sku, channel, week) = pos_sell_through.units_sold        -- finest grain
total_units(ip, category)  = SUM(units_sold) aggregated by IP x category            -- used in Q1
total_revenue(ip, category) = SUM(net_wholesale_revenue_usd) aggregated by IP x category -- used in Q1
```

**Royalty Audit**

```
pos_derived_net_sales(agreement, period) = SUM(net_wholesale_revenue_usd)
    WHERE product_sku.license_agreement_id = agreement
      AND week_start_date IN [period_start, period_end)                             -- across all channels, regardless of authorization
pos_derived_royalty  = pos_derived_net_sales × royalty_rate_pct / 100
variance_usd  = pos_derived_royalty − reported_royalty_due_usd                       -- positive = suspected underreporting
variance_pct  = variance_usd / pos_derived_royalty × 100
```

**Minimum Guarantee Pacing (MG pacing)**

```
elapsed_fraction = (REFERENCE_DATE − contract_start_date) / (contract_end_date − contract_start_date)  -- capped at 1.0
prorated_mg_target = minimum_guarantee_usd × elapsed_fraction
cumulative_royalty_owed = SUM(reported_royalty_due_usd) across all submitted royalty reports for the contract
pacing_ratio = cumulative_royalty_owed / prorated_mg_target
```

**Unauthorized Channel Leakage**

```
is_authorized(agreement, channel) = EXISTS(license_agreement_channel WHERE license_agreement_id=agreement AND retail_channel_id=channel)
unauthorized_revenue_share = SUM(net_wholesale_revenue_usd WHERE NOT is_authorized) / SUM(net_wholesale_revenue_usd)  -- aggregated by licensee
```

**Popularity-to-Sell-Through Lag (Event Alignment Method)**

```
relative_week(event, week) = ROUND((week − event.premiere_week) / 7 days)
avg_units(relative_week) = AVG(units_sold) aggregated by relative_week, across all premiere events -- used in Q3, to find which relative_week the peak lands on
```

> **Convention notes (to avoid conflicting downstream SQL):**
> - In royalty audits, `pos_derived_net_sales` is summed **across all channels** (authorized or not), because the audit's concern is "how much did the licensee actually sell and how much royalty do they owe," not "was it sold compliantly" — that's a separate question answered by Q4.
> - `pacing_ratio` is only meaningful for contracts where `contract_status = 'active'`; expired or terminated contracts shouldn't be held to a "catch-up" standard anymore.
> - `elapsed_fraction` is always capped at 1.0 — once a contract has ended, "amount owed to date" can't keep accumulating indefinitely.
> - The royalty quarter (`report_period_start_date` / `report_period_end_date`) is a **contract quarter** (a 91-day period counted from `contract_start_date`), not a calendar quarter. Comparing "which quarter" across different contracts is meaningless — comparisons only make sense by period number within a single contract.
