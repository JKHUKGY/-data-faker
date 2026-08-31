# Fintech — Real-Time Fraud & AML Platform (NovaRisk AI) — Business Context

> **Important note about the company:** *NovaRisk AI* is a fictional company invented for this dataset. The business model, product shape, and data shapes are inspired by real-world AI-native fraud and AML SaaS players (DataVisor, Feedzai, Featurespace, Hawk AI), but no real data from any real company appears here. All company names, personal names, transactions, and filings are synthetic.

> This document is the "onboarding brief" for the dataset. After reading it, you should be able to make sense of the other three documents even if you have no background in financial fraud:
> - `02-fintech_real_time_fraud_aml_platform_high_er_document.md` — table structure, fields, generation rules, DDL
> - `03-fintech_real_time_fraud_aml_platform_high_sql_queries.md` — 20 business SQL queries
> - `04-fintech_real_time_fraud_aml_platform_high_data_generator.py` — the data generator
>
> The intended reader is a **smart outsider**: assume you just joined this project and need to get the company, industry, project, and jargon straight before your first standup.

---

## 1. The Company: Who NovaRisk AI Is

NovaRisk AI is a **B2B SaaS** company headquartered in New York City, with an engineering and data science branch in Toronto. What it does fits in one sentence: **it sits in the middle of a bank's transaction stream, and when a payment is in flight, it tells the bank within one second whether to "let it through or block it."**

Company profile (order-of-magnitude, not precise):

- **Founded:** around 2019, by two former payments risk engineers and a graph machine-learning researcher.
- **Headcount:** about 180 people; nearly half are engineers, data scientists, and fraud domain experts.
- **Customer count:** 12 paying institutional customers (banks, credit unions, fintechs, BNPL lenders, payment processors).
- **Revenue scale:** annual recurring revenue (ARR) of roughly $8M, made up of the annual contract values of those 12 customers (each one ranging from $240K to $1.2M).
- **Market:** the main battleground is North America (US + Canada). The customer roster includes one Singapore payment processor (EquatorPay) and one Canadian bank (RiverGate Bank); the remaining ten are US-based.

The key roles inside the company that show up in this dataset's queries:

| Role | Abbrev. | What they care about |
|---|---|---|
| Chief Risk Officer | CRO | Which customers are most exposed in high-risk corridors, and whether CDD risk ratings actually predict fraud |
| Chief Financial Officer | CFO | Revenue concentration, top-customer ARR, and the compute cost of Vera AI |
| Fraud Operations Manager | Fraud Ops Manager | Rule false-positive rates, analyst case-closing speed, overdue high-priority cases |
| SRE / Platform Lead | SRE Lead | Whether the real-time scoring API's p99 latency is breaching SLA |
| Compliance Manager | Compliance Manager | SAR filing counts, sanctions list hits, structuring patterns |

---

## 2. The Business Model: How NovaRisk Makes Money

NovaRisk is a **B2B SaaS** company. Its customers are **not** consumers — they are banks, credit unions, fintechs, BNPL lenders, and payment processors. In other words, ordinary people will never know NovaRisk exists; they only see "Transfer complete" or "We need to verify your identity" inside their bank's app.

Each customer signs a **multi-year contract** with NovaRisk, with annual contract value (ACV) of roughly **$240K – $1.2M** (this lives in the `client_institution.annual_contract_value_usd` field), priced as a subscription + usage hybrid. In return, the customer gets the full platform:

1. **Real-time scoring API** — the customer POSTs a transaction and NovaRisk POSTs back a 0–999 risk score plus a recommended action, all within 100 milliseconds.
2. **Model marketplace** — ML models that NovaRisk trains, both **unsupervised** (no fraud labels needed; finds coordinated attack rings by clustering anomalous behavior) and **supervised** (trained on confirmed fraud labels).
3. **Rules engine** — analysts can hand-write hard rules like "decline any wire > $10K on a device less than 24 hours old going to a high-risk country."
4. **Case management workbench** — analysts triage alerts, bundle them into cases, and file SARs.
5. **Conversational AI agent (codename "Vera")** — analysts ask questions in natural language ("show me yesterday's transactions over $5K from new devices"), no SQL or rule-writing required.
6. **Data Consortium** — anonymized fraud signals shared across all NovaRisk customers: a device fingerprint flagged for fraud at Bank A will trigger a warning the next time Bank B sees it.

**Why banks buy this instead of building it themselves:**

- A typical mid-size bank doesn't have 500 ML engineers and a graph anomaly research team.
- A bank's fraud team is usually 40 people, not 4,000 — they need a force multiplier.
- The savings are quantifiable: a human-written SAR used to take an analyst about **21 hours**; with Vera drafting the first cut, it now takes about **2 hours**. Across a few thousand SARs a year, the labor savings alone cover the contract fee.

That's why every row where `sar_report.ai_drafted = TRUE` matters — it is direct evidence of billable value.

**Unit-economics shorthand (order of magnitude):** software gross margins are high (the typical SaaS 75%–85% range), and the biggest variable cost is the LLM inference compute behind Vera. That's also why the CFO wants to allocate token cost down to specific AI sub-agents and tools (see business question Q8).

---

## 3. Industry Overview: What the Real-Time Fraud & AML Market Actually Does

If you come from a different industry, this section gives you enough to hold a conversation about this market.

**What problem does this industry actually solve?** Every time someone swipes a card, sends a Zelle transfer, opens an online bank account, or checks out via BNPL (buy-now-pay-later), **some bank or fintech has to make a yes/no decision in under a second**: is this a real customer doing a real thing, or is somebody trying to steal money or launder dirty cash?

Three things make that decision hard:

- **Good traffic is huge.** The US alone sees billions of payments a day, and customers expect approval in seconds. Slow it down, or wrongly decline one, and the customer experience takes a hit.
- **Bad actors hide inside the good ones.** Roughly **1 in 1,000 transactions is fraudulent**, and missing that 0.1% can wipe out a small bank's annual profit.
- **Regulators are watching.** Regulators require banks to file paperwork (a SAR) every time they spot suspected money laundering, and to run identity checks (KYC) at account opening. Fines for getting it wrong can run into the hundreds of millions.

**Main player categories** (no real names):

- **AI-native fraud SaaS vendors** — companies like NovaRisk, leaning on unsupervised / graph ML, selling real-time scoring + case management.
- **Legacy rules-engine vendors** — older fraud systems built around human-written rules, steadily losing ground to the AI-native players.
- **In-house bank teams** — large banks have their own risk departments, but most mid-size institutions buy rather than build.
- **Payment networks and processors** — card networks and processors have their own layer of risk controls, complementary to third-party SaaS.

**Relevant regulators and compliance frameworks** (mostly North American):

| Body / Framework | What it is |
|---|---|
| **FinCEN** | US Financial Crimes Enforcement Network — the agency that receives SARs |
| **OFAC** | US Office of Foreign Assets Control — maintains the sanctions (SDN) list |
| **FINTRAC** | Canada's Financial Transactions and Reports Analysis Centre — the Canadian counterpart to FinCEN |
| **BSA / AML** | Bank Secrecy Act / Anti-Money Laundering rules — require banks to monitor and report suspicious activity |
| **KYC / CDD** | Know Your Customer / Customer Due Diligence requirements at account opening |
| **FATF** | Financial Action Task Force — sets international AML standards |
| **FCA / EU AMLR** | UK Financial Conduct Authority / EU Anti-Money Laundering Regulation (in force from 2027) — relevant when serving cross-border customers |

**The macro forces shaping this market right now:**

- **The AI arms race.** Attackers use stolen identities, AI-generated deepfakes, stolen device fingerprints, mule accounts, "structuring" splits, and share playbooks with each other quickly. Defenders have to use AI to keep up.
- **Tightening regulation.** AML rules around the world keep getting stricter; SAR filing volumes grow every year, and the human cost can't scale — that's exactly the commercial opening for AI-drafted SARs.
- **Shared intelligence.** Any single bank only sees its own traffic, but fraud rings hit many institutions at once — so the data consortium becomes a key moat.

---

## 4. Project Context: Who You Are on This Project

**You are a data analyst at NovaRisk (intern or full-time, either works). You report to the head of the Data & Analytics team and provide horizontal support to the CRO, CFO, Fraud Ops, and Compliance teams.**

Your job is not to change models or write rules. Instead, you use the data that has actually landed this quarter to **answer specific business questions from each department**. The deliverables look like:

- Quarterly risk review materials for the CRO (high-risk corridor exposure, CDD rating effectiveness).
- Board-deck data for the CFO (revenue concentration, AI compute cost).
- Operational dashboards for Fraud Ops (rule false-positive rate, analyst productivity, alert trends).
- Compliance tracking for the Compliance team (SAR filings, sanctions hits, structuring precedents).
- SLA monitoring snapshots for SRE (p50/p95/p99 latency).

The 20 SQL queries behind these deliverables live in document `03`. Every query traces back to one of the business questions listed in Section 5 below.

---

## 5. The Business Questions This Project Answers

Below are the core questions the project is built to answer. Each one is a **concrete decision or query**, not a vague goal. Together they form the spine of the ER document and the SQL queries.

- **Q1 — Is the real-time scoring API holding its SLA?** What are the p50/p95/p99 latencies right now? Are we creeping up to the 100ms red line? (maps to query Q1)
- **Q2 — How concentrated is revenue?** How do the top customers rank by ACV? What share of ARR do the top 3 represent? What happens if we lose one? (maps to queries Q2, Q19)
- **Q3 — Which detection rules should be retired?** Which rules fire a flood of alerts that are all false positives and burn analyst time? (maps to query Q5)
- **Q4 — Are there coordinated attack rings?** Is a single device being secretly shared by multiple "unrelated" accounts, possibly across multiple banks? (maps to query Q7)
- **Q5 — Does the CDD risk rating set at onboarding actually predict fraud?** Do HIGH-rated customers really show higher confirmed-fraud rates than LOW-rated ones? If not, the CDD model is broken. (maps to query Q11)
- **Q6 — Is the challenger model safe to promote?** What's the gap between champion and challenger decline rates? Only a small gap is safe to roll forward. (maps to query Q14)
- **Q7 — Which customers are most exposed in high-risk corridors?** Whose money flows the most into sanctioned countries, and could trigger a regulator inquiry? (maps to query Q8)
- **Q8 — Is the AI agent (Vera) cost-effective and reliable?** Which sub-agent / tool burns the most tokens? How often do analysts actually accept its output? (maps to query Q13)

The document also includes a batch of **operational queries** (daily transaction / alert trends, decision-mix distribution, SAR efficiency, overdue cases, etc.) — even when not called out by a specific question above, they're the standard fare of a day-to-day operations dashboard.

---

## 6. Data Scope at a Glance

- **Reference date (REFERENCE_DATE):** `2026-06-05`. Every "today / current snapshot" semantic is anchored to this date — the generator, SQL queries, and ER document all agree on it, so results are reproducible.
- **Simulated time window:** a **90-day quarter** ending on 2026-06-05. Transactions, alerts, cases, and SARs all fall inside this window, while "birth times" like customer contract starts and end-user onboarding can run earlier (sometimes years back).
- **Data volume (in plain English):** 20 tables, totaling about **4,540 rows**. That includes 12 institutional customers, about 600 end users, about 800 accounts, about 800 transactions and their scoring events, about 140 alerts, about 30 investigation cases, and about 9 SARs. This is a **High** complexity dataset: there are dimension tables, derived rollups, time-series fan-out, and several cross-table business invariants, but per-table row counts stay small so the story remains explainable.
- **Deliberate scoping decisions:**
  - Simulate **one quarter** only, not several years — so the alert → case → SAR lifecycle plays out within a single readable window.
  - Currency is normalized to **USD**: `amount_usd` is always the USD equivalent at the time of the transaction, while `currency` keeps the original currency (about 85% are USD, because the customer base skews US).
  - The high-risk corridor flag is simplified to a single **boolean** (real AML systems use a 3- or 4-tier sanctions tier), and the target is for roughly 5% of transactions to land in a high-risk corridor.

Table-level structure, fields, foreign keys, and generation rules live in document `02`; this section just gives you the scope at a glance, not a table list.

---

## 7. Industry Primer: The 30-Minute Background You Need Before Reading the Data

### 7.1 How "real-time scoring" actually happens

When a customer taps "Send $500" in their bank's app, the bank's backend pauses for about 80 milliseconds and asks NovaRisk's API: *"Customer 12345, device fingerprint abc…, 2:00 AM, sending $500 from a checking account to a counterparty in Lagos — what's the risk score?"* NovaRisk replies with a **number from 0 to 999** and a **recommended action**. The bank's app then either approves, asks for face ID, or blocks. The customer never sees NovaRisk in the flow.

### 7.2 How the score maps to a decision

The scoring engine outputs 0–999, which is then bucketed into four actions on fixed thresholds:

| Score range | Decision | What the bank UI does |
|---|---|---|
| < 400 | **APPROVE** | Let it through |
| 400 – 599 | **STEP_UP** | Require extra verification (face ID / SMS code) |
| 600 – 799 | **REVIEW** | Hold for human review |
| ≥ 800 | **DECLINE** | Block outright |

**The alert threshold is 600** — i.e. any time the final score lands in the REVIEW band (or an enabled rule fires), an alert is created.

### 7.3 From one transaction to one regulator filing: the data lifeline

This dataset is not a handful of isolated tables — it is the **end-to-end activity trace** of 12 customers over one quarter:

```
Sign contract (client_institution) → Bank onboards end user (end_user, runs KYC)
   → User opens account (account) → User logs in and creates a session (device_session)
   → User taps "Send" → transaction created (transaction)
   → Scoring engine returns in <100ms (risk_score_event)
   → Score ≥ 600 or a rule fires → alert created (alert)
   → Analyst groups some alerts → investigation case (investigation_case)
   → Money-laundering confirmed → SAR filed with FinCEN (sar_report)
   → Analyst talks to Vera (the AI agent) the entire time (agent_interaction_log)
```

The implied time arrow runs left to right: a transaction must happen after the account was opened, which must happen after the user was onboarded, which must happen after the customer signed. The generator enforces this strictly, so the data reads like real history instead of randomly scattered rows.

### 7.4 The lifecycle of alerts and cases

- **Alerts (alert)** mostly start in `OPEN`, get triaged to `IN_REVIEW`, and then close as either false positive (`CLOSED_FALSE_POSITIVE`) or confirmed fraud (`CLOSED_CONFIRMED_FRAUD`), or get `ESCALATED` into a case. **Only alerts in `ESCALATED` or `CLOSED_CONFIRMED_FRAUD` ever end up in a case** — most alerts never become cases, which matches reality.
- **Investigation cases (investigation_case)** move from `OPEN` to either `SAR_FILED` (a regulator filing was submitted) or `CLOSED_NO_ACTION` (closed for lack of evidence).

### 7.5 The core money-laundering playbooks

- **Structuring:** breaking a single large amount (say $30K) into multiple deposits each just under the $10K reporting threshold, to dodge automatic reporting. One of the most common narrative patterns in SARs.
- **Mule account:** an account, knowingly or unknowingly, used to relay laundered funds; usually shows "one in, immediately one out."
- **Account takeover:** a legitimate account hijacked by an attacker. A classic signal is VPN use plus a geolocation that doesn't match the country on file.
- **Deepfake onboarding:** AI-generated fake identities used to slip through the KYC face/document check at account opening.

### 7.6 How models go live: champion vs challenger

Each customer has two models deployed at the same time: a **champion** carrying about 85% of production traffic, and a **challenger** mirroring about 15% for A/B testing. The MLOps team compares the two on decline rate; only when the gap is small enough does the challenger get promoted to champion.

### 7.7 Why a shared device is a red flag

Every device has a **fingerprint** — a hash of signals like browser version, fonts, screen size, and OS. If one physical device is shared across ten supposedly "unrelated" accounts, that's a classic signature of an organized fraud ring. If that same device shows up at **multiple banks**, the signal is even stronger — and that is exactly where the Data Consortium pays off.

---

## 8. Glossary

English terms are kept in their industry-standard form, with a plain-English gloss in parentheses plus why it matters in this dataset.

| Term | Plain English | Why it matters here |
|---|---|---|
| **AML** (Anti-Money Laundering) | The full set of rules and processes for monitoring and reporting suspicious money flows | Half the platform's value sits on the AML side (screening, SARs) |
| **KYC** (Know Your Customer) | Verifying a customer's real identity at account opening | `end_user.kyc_status` records the verification outcome |
| **CDD** (Customer Due Diligence) | Assigning a risk rating at onboarding based on the customer's profile | `customer_risk_rating` comes from CDD; Q11 checks whether it actually predicts fraud |
| **SAR** (Suspicious Activity Report) | The compliance filing banks submit to regulators about suspicious activity | The `sar_report` table; AI-drafted SARs are a core selling point |
| **FinCEN** | US Financial Crimes Enforcement Network — the SAR recipient | The `filing_reference` prefix is literally `FINCEN-` |
| **OFAC / SDN List** | US sanctions agency / its list of sanctioned persons and entities | One of the values in `sanctions_watchlist.list_source` |
| **PEP** (Politically Exposed Person) | A politically exposed person, requiring enhanced review | `end_user.is_pep_match`, plus an internal PEP list |
| **BSA** (Bank Secrecy Act) | The legal foundation of US AML supervision | Explains why banks are obligated to monitor and report |
| **FATF / FINTRAC** | International AML standards body / Canadian counterpart to FinCEN | Provides compliance context for cross-border and Canadian customers |
| **ACH** | The US Automated Clearing House — the bank-to-bank batch transfer network | Shows up as `ach_push` / `ach_pull` in `transaction_type` |
| **Wire** | A real-time, large-value cross-bank or cross-border transfer | A high-risk transaction type; high alert share |
| **BNPL** (Buy-Now-Pay-Later) | Pay over time at checkout | One of the customer types in the dataset (OneTap BNPL) |
| **Structuring** | Splitting a large deposit into many small ones below the reporting threshold | Q20 searches SAR narratives for this term |
| **Mule account** | An account used to relay laundered funds | A fraud type (`mule_account`) |
| **Account takeover** | A legitimate account hijacked by an attacker | A fraud type; VPN + geo mismatch is the classic signal |
| **Card-not-present** | Online card-number fraud where the physical card isn't present | The main fraud type for card_purchase |
| **Deepfake onboarding** | Using an AI-generated fake identity to slip through KYC | The highest-severity fraud type |
| **Device fingerprint** | A unique hash computed from device signals | The core signal for ring detection (Q7) |
| **Emulator** | A non-physical device, often used for batch fraud | `device.is_emulator`; a red flag |
| **Champion / Challenger** | Production model / A/B-tested challenger model | `ml_model.is_champion`; Q14 compares them |
| **A/B test** | Routing a slice of traffic to a new approach for controlled comparison | About 15% of traffic goes to the challenger model |
| **False Positive (FP) / True Positive (TP)** | Alerted but actually fine / actually fraud | `is_true_positive`; Q5 computes the rule false-positive rate |
| **SLA** (Service Level Agreement) | A service-level commitment — here, <100ms p99 latency | Q1 checks whether the scoring API meets it |
| **p50 / p95 / p99** | Median / 95th / 99th-percentile latency | How fast "the vast majority of requests" actually are |
| **Latency** | The round-trip milliseconds an API call takes | The `latency_ms` field |
| **ARR / ACV** | Annual recurring revenue / annual contract value | The basis for revenue concentration analysis (Q2, Q19) |
| **Data Consortium** | The cross-customer shared, anonymized fraud signal pool | The moat for cross-institution ring detection |
| **Step-up auth** | An extra identity verification step | The action corresponding to a STEP_UP decision |
| **High-risk corridor** | A money flow lane into sanctioned or high-risk countries | `is_high_risk_corridor`; Q8 |
| **top_feature / Explainability** | The most influential feature / a model's explainability output | `risk_score_event.top_feature` |

---

## 9. Key Metrics and Formulas

Below are the metrics that appear in the SQL queries or that a reader needs to know. The notation is plain-English pseudocode — enough to get the point across.

**SLA latency percentiles (Q1)**
```
p99_latency = sort all latency_ms ascending, then take the value at the 99th percentile position
pct_over_100ms_sla = COUNT(latency_ms > 100) / COUNT(*)
-- Green-light condition: p99 ≤ 100ms in production
```

**Rule false-positive rate (Q5)**
```
fp_rate = false_positives / (false_positives + true_positives)
-- Only count alerts that have been adjudicated (is_true_positive IS NOT NULL)
-- Deliberately exclude pure-ML alerts (detection_rule_id IS NULL), since the question is "which rule should we retire"
```

**Confirmed-fraud count per 1,000 transactions (Q11)**
```
confirmed_fraud_per_1k_txn = SUM(confirmed fraud alerts) / SUM(transactions) * 1000
-- Group by customer_risk_rating (LOW/MEDIUM/HIGH)
-- Ideally this should rise monotonically from LOW → MEDIUM → HIGH
```

**Champion vs challenger decline-rate gap (Q14)**
```
decline_rate = COUNT(decision = 'DECLINE') / COUNT(*)   -- Use rate, not absolute counts (traffic shares differ)
decline_rate_gap = challenger_decline_rate - champion_decline_rate
-- Positive = challenger is stricter; negative = looser; small |gap| is safe to promote
```

**Revenue concentration (Q2, Q19)**
```
pct_of_total_arr  = client_ACV / SUM(ACV of all active customers)
cumulative_pct    = running total of ACV sorted descending / total_ARR
-- The top-3 cumulative share is the key concentration-risk number (about 41% in this dataset)
```

**Daily alert rate (Q9)**
```
alert_rate = COUNT(DISTINCT alerts today) / COUNT(DISTINCT transactions today)
```

**High-risk corridor exposure (Q8)**
```
high_risk_exposure_usd = SUM(amount_usd) WHERE is_high_risk_corridor = 1   -- Group by customer
```

**True 7-calendar-day rolling alerts (Q16)**
```
rolling_7d_alerts = sum of alerts over the current day and the previous 6 "calendar days" (including 0-alert quiet days)
-- Must use a calendar cross join to fill 0s; otherwise quiet days get skipped and trend collapses to nothing are hidden
```

**Analyst mean case-closing duration (Q6)**
```
avg_hours_to_close = AVG( hours between closed_at and opened_at ) WHERE closed_at IS NOT NULL
```

**AI agent cost and acceptance rate (Q13)**
```
total_tokens   = SUM(tokens_used)                          -- Group by agent_name + tool_called
approval_rate  = AVG(human_approved)                       -- about 92% overall
```

**AI-drafted share of SARs**
```
ai_drafted_share = COUNT(ai_drafted = TRUE) / COUNT(*)     -- about 80%, the productivity evidence for NovaRisk's auto-drafting product
```
