# Property & Casualty — Commercial Underwriting: Business Context

> **Dataset:** `property_casualty_commercial_underwriting_high`
> **Complexity:** High (24 tables, ~116,000 rows)
> **Reference "today":** 2026-06-21 (data covers the most recent 24 months of business operations)
> **Companion documents:** Data structure in `02-..._er_document.md`, SQL queries in `03-..._sql_queries.md`, data generator in `04-..._data_generator.py`

This file is the "business manual" for the entire dataset. It first explains **what kind of company DingAn Commercial Insurance is, how it makes money, and how the industry works**, then describes **the role you play in the company and the business questions you need to answer**, and finally uses a **glossary + metric formulas** to teach you the "common language" of the insurance industry in one shot. After reading this document, even if you had zero insurance background coming in, you'll be able to follow the 24 tables in the ER document and the 50 queries in the SQL document.

> **Market note:** This dataset portrays a **mid-sized domestic (Mainland China) commercial property/casualty insurer**, with currency in Chinese yuan (CNY). The regulators, cities, and credit rating agencies referenced are all domestic Chinese entities. This is the existing business setting of the dataset; this document faithfully follows it rather than rewriting it.

---

## 1. Company Profile: Who Is DingAn Commercial Insurance

**DingAn Commercial Insurance Co., Ltd.** is a fictional mid-sized domestic **Property & Casualty (P&C)** insurer headquartered in Shanghai, with business covering the North, East, South, West, and Central regions of China. It **does not write personal auto, and does not write life insurance** — it only serves **business clients**: factories, office buildings, construction sites, restaurant chains, logistics parks, hospitals, and so on. In the real market, its peers are the commercial lines of the major P&C carriers (such as Ping An P&C commercial lines, PICC P&C, CPIC P&C, China United).

**Business scale (matching this dataset):**

| Metric | Scale |
|--------|-------|
| Insured corporate clients | 1,000 firms (small-to-large mid-market, 20 – 8,000 employees) |
| Total policies | ~3,100 (about 3 per client, including in-force / expired / cancelled) |
| Annualized in-force premium | About CNY 500M – 1B |
| Underwriters | 40 (5 managers + 35 line underwriters) |
| Claim adjusters | 25 |
| Partner insurance brokerages | 60 |

**Org structure (roles that show up in the queries):** The C-suite includes the CEO, CFO, and CRO (Chief Risk Officer); middle management includes the VP of Underwriting, Director of Distribution, Director of Compliance, and Director of Finance; the front line includes underwriting managers, claims managers, risk-control managers, finance managers, and the corresponding line underwriters, claim adjusters, and analysts. These titles will appear repeatedly under "business role" in the SQL queries — every query is a question that a specific role would ask in a specific scenario.

---

## 2. Business Model: How DingAn Makes Money

The profit formula for an insurance company is much plainer than for an internet company, but every line item is a deep subject:

```
Insurer Net Profit = Earned Premium
                   − Incurred Losses
                   − Operating Expenses
                   + Investment Income
```

The piece **Earned Premium − Incurred Losses − Operating Expenses** is called **Underwriting Profit** — it's the scorecard for the insurer's "main business". In simplified terms, whether underwriting makes money comes down to just two things, and **both are the underwriter's responsibility**:

```
1. Is the premium priced right?   Too low  → can't cover losses → loss
                                  Too high → clients lost to rivals → no business
2. Should we even write this?     Take a high-risk client → frequent claims → loss
                                  Decline a good client   → missed revenue
```

**Pricing mechanism:** DingAn quotes business at **"base premium × risk-tier multiplier"**. The base premium depends on the line of business and limit (CNY 30K – 800K range in this dataset), then multiplied by the company's risk tier (low risk 0.8×, medium 1.0×, high 1.4×, very high 1.9×). A handful of high-risk large accounts can reach ~CNY 1.5M/year. The insurer earns the **difference between "premium collected" and "claims paid out + operating costs"** — whether that spread is healthy depends entirely on the quality of underwriting decisions.

**Unit economics (industry benchmark):** The Expense Ratio at domestic P&C insurers typically runs 25% – 30% of premium. So once the Loss Ratio exceeds about 70%, adding expenses pushes the total past the 100% breakeven line (see Combined Ratio in Section 9). That's why 70% is the single most important red line in an underwriter's head.

---

## 3. Industry Primer: How the Commercial P&C Market Works

If you come from another industry, this section is what lets you "talk shop" with colleagues.

**What value does this industry create?** Anything can happen during business operations — a factory fire, a product injury, a construction accident, a business interruption, a director getting sued. If any of these hit, paying it out of pocket could bankrupt the company. Commercial insurance **pools** the risks of tens of thousands of firms: everyone pays premium in normal times, and the unlucky few who suffer losses get paid from this pool. The insurer's craft is **pricing each firm's risk accurately**, so good clients don't overpay and bad risks don't get a free ride.

**Main types of players (without naming real companies):**

- **Carrier / Insurer:** the entity that takes on risk, collects premium, and pays claims — DingAn in this dataset.
- **Broker (Insurance Broker):** the intermediary that represents the **insured business**, shops prices across multiple insurers, negotiates terms, and submits applications. 80%+ of commercial business comes in through brokers.
- **Adjuster / Loss Assessor:** the professional who does on-site loss assessment after a claim; can be an internal employee of the insurer or a third-party adjusting firm.
- **Reinsurer:** the "insurance company for insurance companies" — the carrier sells off slices of very large policies to spread the risk further (not modeled in this dataset).
- **Rating / Credit Agencies:** third parties that score the financial health of companies (such as China Chengxin International, Dagong Global).

**Regulatory and compliance framework (domestic):** Commercial P&C is regulated by the **National Financial Regulatory Administration (NFRA)** — covering policy wording, solvency, and market conduct. The insured companies themselves are regulated by various agencies, and those enforcement records are an important external signal for underwriting: **Ministry of Emergency Management** (workplace safety), **Ministry of Ecology and Environment** (environmental), **State Administration for Market Regulation** (product quality), **National Fire and Rescue Administration** (fire safety), **State Taxation Administration**, **Ministry of Human Resources and Social Security** (labor and employment), etc.

**Macro forces shaping the industry right now:**

1. **Underwriting margins under pressure:** Industry Combined Ratios mostly sit in 97% – 102%, meaning underwriting is wafer-thin or even slightly loss-making; profits depend more and more on investment income and tighter risk control.
2. **Data and AI transformation:** Renewal underwriting is highly repetitive fetch-and-judge work, and is being reshaped by Text2SQL, RAG, and decision-synthesis AI agents — which is the very reason this dataset exists.
3. **Risk-mix shift:** New risks like climate catastrophes, cyber, and D&O are rising. Traditional historical-experience-based pricing is increasingly inadequate.

---

## 4. Project Framing: Who You Are and What You Deliver

**Your role:** You are an **Underwriting Operations Analyst intern** at DingAn, reporting directly to the **Underwriting Manager (Chief Underwriter)**. Your day-to-day work falls into three buckets:

1. **Batch data prep during renewal season.** Every June and December is a renewal peak; underwriters have to decide within 30 days whether to renew several hundred policies and how much to move premium up or down. They'll ask you to "pull this company's loss experience for the last 3 years and benchmark it against the industry" — that's your SQL.
2. **Data pulls for deep-dive case investigations.** When a policy has an unusual claim amount, or a claim communication contains a keyword like "attorney letter", the underwriter will ask you to "pull every claim detail, payment history, and regulatory record for this company over the last 2 years".
3. **Helping build the InsightUnderwriter AI Agent.** The company is going through an AI transformation, and wants AI agents to automatically produce a first draft of the two work types above. Your job is to feed the AI, write prompts, and compare AI output against human output.

**What you deliver:** SQL query results, renewal analysis worksheets, and training/validation data for the AI agent. The final audience is the underwriting manager and the VP of Underwriting; some aggregated metrics roll up to the CFO/CRO quarterly risk review.

**The InsightUnderwriter AI Agent is the project's north star.** The goal is to build an AI agent that plays the underwriter role and produces a draft renewal recommendation in 5 minutes. It's a pipeline of 4 sub-agents:

| Sub-Agent | Responsibility | Main Data Sources |
|-----------|----------------|-------------------|
| **Text2SQL Agent** | Pull company profile, 3-year financial trend, historical policies + claims, payment behavior, unremediated hazards | All 24 tables |
| **RAG Agent** | From claim communications, retrieve fraud / dispute / attorney signals; from site inspections, retrieve hazards | `claim_communication`, `site_inspection` |
| **External Data Agent** | Pull regulatory penalties, third-party credit ratings, industry benchmarks | `regulatory_filing`, `third_party_report`, `industry_benchmark` |
| **Decision Synthesis Agent** | Combine the above and output a Renew / Conditional Renew / Decline recommendation + premium change % + key risk points | All of the above |

> **Important boundary:** The AI agent only produces the **first draft**. The final call always rests with the human underwriter (this is also a regulatory requirement). This dataset is the cold-start training data and business-logic validation set for that AI agent.

**What this dataset deliberately does NOT cover** (honest disclosure, for complexity control): personal-level data protection compliance (PII masking), reinsurance contracts and cessions, the actuarial pricing model itself, and cross-insurer credit-sharing platforms.

---

## 5. The Business Questions to Answer

The entire dataset — schema, data distributions, SQL queries — exists to answer the following specific questions. Every query in the SQL document traces back to one of these.

1. **Is the risk pricing right?** Do the risk scores (risk_score) and risk tiers (risk_tier) that underwriters assigned to policies and companies actually match the loss ratios those policies/companies subsequently produced? If high-scored ones don't have losses and low-scored ones constantly have losses, the pricing model has failed. (Corresponds to queries B11, B30, B35)
2. **Which clients should we raise prices on, decline, or fight to keep?** Use 3-year cumulative Loss Ratio, deviation from industry benchmark, and financial deterioration signals to bucket clients into "premium retain / raise rates / conditional renew / decline". (Corresponds to D2, D10, D11, B5, B13, B34)
3. **Are renewal decisions accurate?** For clients who got "renewed + repriced up" or "declined" last year, did their subsequent loss ratios actually change as expected? Used to back-test and calibrate the decision model. (Corresponds to B10, B20, B32)
4. **Are there fraud / dispute / out-of-control signals in claims?** From unstructured claim communications, identify fraud_signal, attorney_involvement, dispute_escalation; from repeated reserve increases, identify out-of-control cases. (Corresponds to D5, D9, B16, B17, B21, B22)
5. **What do client payment behavior and external risk signals tell us?** Are payment delinquency, regulatory penalties, and credit rating downgrades useful as early warning indicators for renewal risk? (Corresponds to D7, D12, D13, B27, B29, B31)

---

## 6. Data Scope Overview

- **Time window:** With `REFERENCE_DATE = 2026-06-21` as "today", data spans the most recent **24 months** (history starts 2024-06-21). All "days since today" / "last N years" calculations are anchored to this fixed date so results are reproducible.
- **Volume in plain language:** A thousand companies, three thousand+ policies, three thousand+ claims, nearly twenty thousand claim communications, ten thousand+ invoices — about 116,000 rows total, spread across 24 tables.
- **Underwriting-year convention:** The loss-ratio rollup table (`loss_run`) uses an **underwriting-year** convention, covering UY 2024 / 2025 / 2026. All claims on a policy are credited to the underwriting year of its effective date.
- **Deliberate scope choices:** Commercial P&C only, no personal lines; modeled up to the underwriter's "use human experience to adjust price" step, no actuarial engine; no reinsurance and no PII masking. These tradeoffs keep complexity in the "high" bucket while preserving the renewal-underwriting storyline end-to-end.

> The full table list, fields, foreign keys, and DDL all live in the ER document (`02-..._er_document.md`); this file does not duplicate them.

---

## 7. Industry Knowledge Primer (Underwriting 101)

Before looking at any table, internalize these 5 most fundamental concepts. If you can explain them in your own words to someone else, the rest of the data falls into place quickly.

### 7.1 What Is an Underwriter

**In plain language:** An underwriter is the person who **decides whether to write the risk and at what price**. Analogy: when you apply for a credit card, someone in the back office reviews your credit, decides whether to approve, and sets the limit — that's a personal-finance underwriter. A commercial insurance underwriter does the same thing, except the subject is a business, the amounts are policies worth millions, and the decision is based on dozens of data dimensions. One underwriter handles 50 – 100 policies per month; senior underwriters can reach 150. The AI agent's goal is to compress the initial analysis on each policy from 30 minutes to 3 minutes.

### 7.2 What Is a Broker (Insurance Broker)

**In plain language:** A broker represents the **client (the insured business)**, shopping prices across multiple insurers, negotiating terms, and submitting applications. 80%+ of commercial business comes in through brokers, not directly from companies. Why: a large business's insurance needs are complex (Property + GL + Workers' Comp + D&O + Business Interruption — a whole bouquet of lines), brokers are on first-name terms with all the major carriers and can pick the best fit, and broker commissions are paid by the insurer (5% – 20%), so they're "free" to the client.

For the underwriter, brokers are both a **traffic source** and the **first line of risk filtering**: good brokers don't send junk, bad brokers slip in "rescue" submissions (companies just hit by a loss and scrambling for a new carrier). So DingAn rates its brokers: Strategic Partner / Important Partner / General Partner (`broker.tier`).

### 7.3 Underwriter vs. Claim Adjuster

New hires mix these up most often, but they are **two completely different roles**:

| Dimension | Underwriter | Claim Adjuster / Loss Assessor |
|-----------|-------------|--------------------------------|
| When they work | **Before binding** + **before renewal** | **After a loss occurs** |
| Core question | "Should we write this? At what price?" | "Is the loss real? How much should we pay?" |
| Main output | Underwriting opinion + quote | Loss adjustment report + payment calculation |
| Data sources | Financials, industry benchmarks, credit reports, loss history | On-site inspection, witness statements, repair invoices, medical records |
| In the dataset | `underwriter` table | `claim_adjuster` table |

### 7.4 The Life Cycle of a Commercial Policy

A commercial policy doesn't end the moment it's signed — it keeps generating data for 365 days, and that process data is the most valuable information available come renewal time:

```
T−30 days  Application submitted (by broker) → underwriting assessment → quote → client accepts → bind
T 0   days  Policy effective (effective_date)
            Simultaneously generated: policy_coverage (covered items), policy_premium_history (initial booking),
                                      invoice (4 quarterly invoices), possibly site_inspection (on-site survey)
T mid       Loss occurs → claim: claim filed → claim_event status advances → claim_communication (main RAG source)
                                → claim_reserve adjustments → final payment
T mid       Endorsement: extend coverage / change address / add or remove exclusions → also writes policy_premium_history
T+365 days  Policy expires → underwriter reviews → renewal_decision (Renew / Conditional / Decline)
```

### 7.5 Renewal: The Underwriter's Most Important Job

**Why is renewal more important than new business?** New-business information is limited (only what the broker provides), so most of the call is industry experience. Renewal information is rich (a full year of actual loss data + communication records), so you can price much more precisely. There are 3 possible renewal outcomes:

| Decision | Share | Typical Trigger | What It Means for the Client |
|----------|-------|-----------------|------------------------------|
| **Renew** | ~65% | Loss ratio < 70%, sound financials, no large open claims | Small premium adjustment (±10%) |
| **Conditional Renew** | ~25% | Loss ratio 70% – 90%, fixable hazards exist | Client must make changes (complete remediation / raise deductible / add restrictive endorsements) to renew |
| **Decline** | ~10% | Loss ratio > 100%, multiple lawsuits, severe regulatory action, financial deterioration | Client has to find another carrier |

---

## 8. Glossary

The "common language" of the industry. For each term we give the **English term + plain-language explanation + why it matters in this dataset**. It's OK if you don't get it on first read, but eventually you should be able to use these words off the cuff.

### 8.1 Roles and Channels

| Term | Plain Language | Why It Matters |
|------|----------------|----------------|
| **Underwriter** | The person who decides whether to write and at what premium | Whether the company is profitable boils down to underwriting decision quality; ties to policy / renewal_decision / risk_assessment |
| **Broker** | The intermediary who represents the client and shops insurers for them | 80%+ of business; tier rating affects allocation |
| **Claim Adjuster / Loss Assessor** | After a loss, does on-site assessment and calculates payment | Decides what actually gets paid; ties to claim / claim_communication |
| **Carrier / Insurer** | The entity that takes risk, collects premium, pays claims | DingAn itself in this dataset |

### 8.2 Policy and Underwriting

| Term | Plain Language | Why It Matters |
|------|----------------|----------------|
| **Policy** | A 1-year insurance contract | Core revenue entity; `policy` table |
| **Premium** | What the client pays the insurer each year | Revenue source; `current_annual_premium_cny` |
| **Coverage Limit** | The most that gets paid out | Cap on risk exposure |
| **Deductible** | The amount the client absorbs before insurance pays | High deductible = cheaper premium + fewer small claims; bargaining chip at renewal |
| **Premium Rate** | Annual premium ÷ limit × 1000, the price per unit of limit | Lets you compare pricing across policies |
| **Endorsement** | Mid-term change to the policy (change address / add or drop coverage) | Frequent endorsements = initial assessment was off; a risk signal |
| **Renewal** | Decision at policy expiry whether to write again | The underwriter's most important job |
| **Bind** | The official issuance of the policy after underwriting approval | `bound_at` is 7–30 days earlier than effective_date |

### 8.3 Claims and Loss

| Term | Plain Language | Why It Matters |
|------|----------------|----------------|
| **Claim** | Client's request for payment after a loss | `claim` table; a policy has 0–4 claims |
| **Loss Amount** | What the client claims they lost | `loss_amount_cny`; can be inflated |
| **Paid Amount** | What's actually paid after adjustment | `paid_amount_cny`; typically 60%–98% of the reported figure |
| **Reserve** | The amount the insurer sets aside for open claims not yet fully paid | Repeated upward revisions = strongest signal that the case is going sideways; `claim_reserve` |
| **Claim Frequency** | Claim count ÷ policy count | High frequency = management problem (human-factor risk) |
| **Severity** | Average loss amount per claim | Measures the "intensity" of risk |
| **Reporting Lag** | reported_date − incident_date in days | > 7 days = moral hazard (possibly fabricating evidence) |

### 8.4 Risk and External Signals

| Term | Plain Language | Why It Matters |
|------|----------------|----------------|
| **Risk Tier** | Company-level coarse classification: Low / Medium / High / Very High | Drives the base premium multiplier; `company.risk_tier` |
| **Risk Score** | Policy-level fine-grained 0–100 score, higher = riskier | Assigned by underwriter; `risk_assessment.risk_score` |
| **Credit Rating** | Third-party financial health grade (AAA ~ CCC) | Successive downgrades = financial deterioration; `third_party_report` |
| **Debt-to-Equity Ratio** | Liabilities ÷ equity; > 1 caution, > 2 red line | Financial stress signal. Note: this field is "liabilities/equity", not "liabilities/total assets" |
| **Loss Run** | Loss-ratio ledger aggregated by company × underwriting year × line of business | The single most-queried table for renewal decisions; `loss_run` |
| **Industry Benchmark** | Industry-average loss ratio / frequency / premium range | A single firm's loss ratio is only meaningful when compared to industry |
| **Subcontractor** | A specialized contractor hired by a general contractor | Subcontractor accidents are paid by the general contractor's policy; a risk signal for construction lines |

### 8.5 RAG Signal Tags (Claim Communication Classification)

`claim_communication.signal_tag` is the labeled data prepared for the RAG agent, with 6 categories:

| Tag | Plain Language | Why It Matters |
|-----|----------------|----------------|
| **normal_cooperative** | Routine cooperation, nothing unusual | Negative-sample baseline (~40%) |
| **investigation_note** | Notes from the investigation/evidence-gathering process | Flags investigation activity (~20%) |
| **fraud_signal** | Fraud-risk indicator | The RAG agent's main training target (~12%) |
| **dispute_escalation** | Dispute escalation | Dispute early warning (~12%) |
| **settlement_negotiation** | Settlement negotiation in progress | Tracks settlements (~10%) |
| **attorney_involvement** | Attorneys involved | High-risk, often means litigation (~6%) |

---

## 9. Key Metrics and Formulas

Below are all the core metrics used in the SQL queries, or that the reader should know. Formulas are written in SQL-style pseudocode, with definition conventions called out (inconsistent definitions will cause downstream SQL to disagree with itself).

### 9.1 Loss and Profitability Core

**Loss Ratio** — the single most important KPI in the entire industry:

```
Loss Ratio = Total Losses (Paid / Incurred) / Total Premium
```

Definition convention: this dataset uniformly uses the **paid** convention (`SUM(claim.paid_amount_cny) / SUM(policy.current_annual_premium_cny)`); declined and still-open claims contribute zero paid. The `loss_run` table is already pre-aggregated under this convention. Tiered interpretation:

| Loss Ratio | Meaning | Underwriter Response |
|-----------|---------|----------------------|
| < 50% | Excellent client | Renew + consider a price cut |
| 50% – 70% | Good client | Renew, minor adjustment |
| 70% – 90% | Borderline, edge of unprofitable | Renew + raise price 10%–25% + add conditions |
| 90% – 110% | Already losing money | Conditional renew + big increase 30%+ |
| > 110% | Heavy loss | Decline (unless strategic) |

**Combined Ratio** — does the core underwriting business actually make money:

```
Combined Ratio = Loss Ratio + Expense Ratio
                 (loss)       (expense, typically 25%–30%)
```

> Combined Ratio > 100% = underwriting on its own is losing money (relying on investment income to bail you out); < 100% = underwriting itself is profitable = a healthy insurer. Domestic P&C is generally 97% – 102%. This is the underlying reason 70% loss ratio is the watershed: 70% loss + 30% expense = 100%, exactly breakeven.

### 9.2 Customer and Financial

```
Client total in-force premium = SUM(policy.current_annual_premium_cny WHERE status='in_force')
Client cumulative paid losses = SUM(claim.paid_amount_cny  joined via policy.company_id)
Debt-to-Equity Ratio          = total_liabilities_cny / (total_assets_cny − total_liabilities_cny)
Net Profit Margin             = net_profit_cny / revenue_cny
3-year cumulative Loss Ratio  = SUM(loss_run.total_losses_cny) / SUM(loss_run.total_premium_cny)  WHERE year >= start_year
Industry-benchmark deviation  = loss_run.loss_ratio − industry_benchmark.avg_loss_ratio   (same industry, same year)
```

### 9.3 Underwriting Operations

```
Renewal rate              = COUNT(decision='Renew') / COUNT(*)                     from renewal_decision
Decline rate              = COUNT(decision='Decline') / COUNT(*)                   from renewal_decision
Average renewal premium change = AVG(premium_change_pct WHERE decision IN ('Renew','Conditional Renew'))
Premium slippage (count)  = COUNT(policy_premium_history WHERE change_event_type='Endorsement') PER policy_id
Quota attainment          = COUNT(policies bound this month) / underwriter.monthly_quota_policies
```

> **Two different definitions of Claim Frequency (be careful):** `industry_benchmark.avg_claim_frequency` is a **rate** (claim count / policy count), used for benchmarking; whereas `loss_run.claim_frequency` is an **absolute count**. They have different units and cannot be subtracted or directly compared.

### 9.4 Claims and Cycle Time

```
Severity              = AVG(claim.loss_amount_cny)
Paid ratio            = paid_amount_cny / loss_amount_cny    (how much the adjuster cut)
Average close days    = AVG( MAX(claim_event.event_date WHERE type='Closed/Archived') − claim.reported_date )
Open (active) claims  = COUNT(claim WHERE status IN ('Filed','Investigating','Adjusting'))
Reporting lag         = reported_date − incident_date    (> 7 days = moral hazard)
Reserve growth mult.  = latest_reserve / initial_reserve   (> 1.5 risky, > 3 out of control)
```

> Definition convention: "open / active" is uniformly defined as status ∈ {Filed, Investigating, Adjusting}; "Paid" ≈ awaiting close, while "Closed / Declined" are already wrapped up and excluded from open (D5 / D15 / B18 are consistent on this).

### 9.5 Payment and External Risk

```
On-time payment rate   = COUNT(payment WHERE days_late <= 0) / COUNT(*)
Average days late      = AVG(payment.days_late WHERE days_late > 0)
Total receivables      = SUM(invoice.amount_due_cny WHERE status IN ('Pending','Overdue'))
Regulatory penalty cnt = COUNT(regulatory_filing WHERE filing_date >= REFERENCE_DATE − N years)
Rating downgrade cnt   = COUNT(third_party_report WHERE rating_change='Downgrade')
Fraud signal rate      = COUNT(claim_communication WHERE signal_tag='fraud_signal') / COUNT(*)
Hazard remediation     = COUNT(site_inspection WHERE remediation_status='Completed') / COUNT(hazards_identified IS NOT NULL)
```

---

> Having read this document, you now have the full picture of DingAn's business, the basic industry vocabulary, and the metric language. Next up: **data structure (tables / fields / foreign keys / DDL / business traps) in `02-..._er_document.md`, and the 50 business SQL queries in `03-..._sql_queries.md`.**
