# Fintech Consumer Credit Card Lifecycle: Business Context

> This document is the business background for the `fintech_credit_card_lifecycle_high` dataset. Its job is to answer "what kind of company is this, what business is it in, and what problems is it trying to solve." The data structure lives in `02-fintech_credit_card_lifecycle_high_er_document.md`, and the SQL queries live in `03-fintech_credit_card_lifecycle_high_sql_queries.md`.
>
> If you read an analysis (say, "underwriting calibration," "transactor profitability," or "vintage deterioration") and have no idea what it means, there is a long tutorial written specifically for outsiders: `05-fintech_credit_card_lifecycle_high_analytics_primer.md`. It walks through all 8 analyses one by one, starting from "what is this, why does it matter, how do you calculate it" all the way to "what does it look like in our data."
>
> Reader assumption: you're a smart new hire who just joined the project, not a credit card industry veteran. After reading this document, you should be able to talk intelligently at your first standup about this company's business, its industry, and the questions this analysis needs to answer.

---

## 1. Company Profile

**Keystone Card Company** is a mid-sized **consumer credit card issuer** headquartered in Irvine, CA. It is not a payment network (not Visa/Mastercard), nor is it a tech vendor selling software to banks. It's the company that **issues its own cards, makes its own approval decisions, and eats its own bad debt**. The company behind the card in your wallet is playing this exact role.

Keystone's DNA is "let data make the decisions." It believes every card offer (who gets it, what credit line, what APR, what rewards) should be personalized by statistical models rather than handed out with a one-size-fits-all rule. This "data-driven card issuing" playbook has been the most successful strategy in the US credit card industry over the past thirty years.

Company profile (order of magnitude, not precise figures):

- **Cardholder accounts:** roughly 8,900 accounts on the books, with customers spread across California (annual incomes ranging from $20K to over $100K).
- **Lending scale:** outstanding revolving balances in the tens of millions of dollars, with revenue coming from interest and swipe fees.
- **Employees:** roughly 300, spanning underwriting, risk, marketing/acquisitions, data science (Card Intelligence), collections, finance, and product teams.
- **Geography:** currently concentrated in a single state, California, with applicants spread across cities like Los Angeles, San Diego, San Jose, San Francisco, Sacramento, Fresno, and Irvine.

Roles at the company relevant to this analysis (the SQL queries reference these people by title):

| Title | What They Care About |
|------|----------|
| CEO | Growth, product portfolio, overall profitability |
| CFO | Product P&L, loss provisions, rewards cost, cost of funds |
| CRO (Chief Risk Officer) | Portfolio quality, vintage loss curves, underwriting standards |
| Chief Credit Officer | Underwriting policy, credit line management (CLI) |
| CMO | Acquisition, campaign ROI, channel quality |
| VP of Underwriting | Approval rates, underwriting standards, risk segmentation |
| VP of Acquisitions | Funnel conversion, acquisition cost, bonus campaigns |
| VP of Portfolio Management | Utilization, exposure, repricing |
| Head of Card Intelligence | Performance and calibration of underwriting/response/attrition models |
| Collections Manager | Delinquency buckets, roll rate, early warning signals |
| Product Manager | Customer segments and profitability by card product |
| Data Analyst / Data Scientist | That's you — using data to answer everyone else's questions above |

---

## 2. Business Model

Keystone makes money on three legs of revenue, minus three buckets of cost.

**Three revenue legs:**

1. **Interest.** If a customer doesn't pay their balance in full, the remaining revolving balance accrues interest at the APR (annual percentage rate). This is the issuer's single biggest revenue source. APR ranges from roughly 15% to 30% depending on risk.
2. **Interchange (swipe fees).** Every time a customer swipes their card, the merchant's side pays a fee to the issuer, roughly 1.5% to 2.1% of the transaction amount. The more a customer swipes, the more Keystone earns, and this revenue carries no credit risk.
3. **Fees.** Annual fees ($95 to $395 for premium cards), late fees, cash advance fees, and so on.

**Three cost buckets:**

1. **Rewards (cashback/points).** To encourage spending, many cards give back 1% to 2.5% in rewards. This is a direct cash cost.
2. **Charge-off (write-off losses).** When a customer simply can't pay back what they owe, the company has to write off that balance as a loss. This is the biggest risk-related cost.
3. **Acquisition and operating costs.** Marketing outreach, signup bonuses, headcount, and so on.

So Keystone's profit ultimately comes down to balancing two things: **is risk priced accurately** (do the interest and interchange collected cover bad debt and rewards), and **are the right products matched to the right customers** (giving high-margin products to people who spend and pay interest, and not handing high-rewards cards to people who are just gaming the system).

**A counterintuitive unit-economics point:** a customer who pays their balance in full every month and never pays interest (the industry calls this a Transactor) is not necessarily a good customer for the issuer. They contribute interchange (roughly 1.8%) but claim rewards (potentially 2%+) and pay no interest. On a high-rewards card, this kind of customer can actually **lose the company money**. The real profit engine is the Revolver — the customer who carries a balance and dutifully pays interest month after month. This counterintuitive fact sits at the core of several analyses in this dataset (Transactor profitability and the product ladder P&L, see Section 5, Business Questions, corresponding to SQL queries Q12, Q19, Q11).

---

## 3. Industry Primer: US Consumer Credit Card Issuing

If you're coming from a different industry, this section will get you up to speed quickly on how card issuing works as a business.

**What value does this industry create?** Credit cards give consumers two things: payment convenience (no need to carry cash) and short-term credit (spend now, pay later, or even pay in installments). For merchants, it expands spending. For issuers, it's a business built on "using scaled, small-margin spreads and fees to cover the default losses of a minority of customers." The US is the most developed credit card market in the world, with high per-capita card ownership and revolving balance volume.

**Main player categories (no real companies named).**

- **Large full-service issuers:** banks that also issue cards, with a full product lineup and low cost of funds.
- **Data-driven specialist issuers:** companies like Keystone that lean on statistical modeling and personalized offers with fast iteration, and are especially competitive in the near-prime and subprime segments.
- **Co-brand card issuers:** partner with airlines, retailers, or hotels to issue co-branded cards, sourcing customers through the partner's loyalty membership base.
- **Fintech upstarts:** focus on mobile-first experiences, secured cards to help people build credit, or newer forms like Buy Now Pay Later (BNPL).

**Regulatory and compliance framework (North America).** Issuers are subject to multiple layers of regulation.

- **CARD Act (2009):** governs credit card pricing, rate increases, and fee disclosure to protect consumers.
- **TILA (Truth in Lending Act) and Reg Z:** require clear disclosure of APR, fees, and other credit terms.
- **ECOA (Equal Credit Opportunity Act) and Reg B:** prohibit credit discrimination based on race, gender, and similar factors. Underwriting models must be able to demonstrate they don't produce discriminatory outcomes.
- **FCRA (Fair Credit Reporting Act):** governs how credit reports are pulled and used (this is where the FICO score comes from).
- **CFPB (Consumer Financial Protection Bureau):** the federal consumer financial regulator, watching pricing fairness and collections practices.
- **CECL (Current Expected Credit Loss):** an accounting standard requiring issuers to provision forward-looking for expected losses. This is exactly why vintage loss curves (Vintage Deterioration, corresponding to SQL query Q16) flow directly into the financial statements.
- (Canadian equivalent: FCAC and provincial consumer protection regulations. This dataset defaults to the US, California market.)

**Current macro forces.** Interest rate conditions are pushing up issuers' cost of funds; a rewards arms race keeps driving rewards costs higher; AI and machine learning are reshaping underwriting and fraud detection; regulators are demanding more on pricing fairness and model explainability; and economic cycle swings make "are underwriting standards quietly loosening during good times" a question risk officers have to revisit every quarter. All of this keeps "is pricing accurate, are customers matched to the right products, is underwriting drifting" as questions leadership keeps coming back to.

---

## 4. Project Framing: What You're Doing

You are a **Data Analyst** at Keystone (you might carry the title Business Analyst, or Data Scientist — the two roles share the same dataset at Keystone). You've been pulled into a **quarterly portfolio and acquisition review** project, supporting the CRO, CFO, CMO, and the Head of Card Intelligence across the board.

The company just closed out a quarter, and leadership has a pile of open questions. Has the underwriting model already broken down in certain segments? Are marketing channels that look cheap on acquisition cost actually bringing in the worst customers? Are the premium rewards cards actually profitable? Will 0% promo APRs expiring trigger a wave of delinquency? Is raising credit lines for high-utilization customers helping them or hurting the company? Are big signup bonuses breeding a population of bonus hunters? Are underwriting standards quietly loosening? Your job is to use roughly 24 months of complete credit card lifecycle data to answer these questions one by one, using SQL.

Deliverables: a portfolio quality report for the board and investors, channel budget recommendations for the CMO, a product P&L for product and finance, model calibration findings for the data science team, and an actionable checklist for operations and collections. All analyses are anchored to a fixed reference date, **REFERENCE_DATE = 2026-06-30** (see Section 6 for details).

This project is deliberately designed to feed two audiences at once. The **Business Analyst** uses SQL across the full acquisition-to-charge-off funnel to answer business questions (pricing, ROI, concentration, P&L). The **Data Scientist** can model and validate directly from the data: underwriting scores sitting next to actual charge-off outcomes let you plot ROC curves, compute AUC, and build confusion matrices; time series, vintage cohorts, and binary labels are all readily available.

---

## 5. Business Questions This Project Answers

The entire dataset is designed to answer the eight core business questions below. Each one has a corresponding deliberately embedded data trap in the ER document, and a corresponding query in the SQL queries document. To avoid confusion with the SQL query numbering (Q1 through Q20 in the SQL document), the business questions here are identified by **name** rather than number, with the corresponding SQL query numbers given in parentheses. Anywhere else in this document that says "Qn," it always refers to the SQL query numbering in `03`.

1. **Underwriting Model Calibration:** Does our live underwriting risk score (underwriting_score) actually rank-order risk? It looks fine in aggregate, but has it already broken down in one particular segment (Subprime), just masked by the overall numbers? This one is for the Data Scientist to answer using ROC/AUC/confusion matrices. (corresponding to SQL queries Q3, Q4)
2. **Channel Adverse Selection:** Which marketing channel looks cheap on acquisition cost but actually brings in the worst customers (highest charge-off rate)? Are we allocating marketing budget based on the wrong metric (CPA)? (corresponding to SQL queries Q6, Q7)
3. **Transactor Profitability:** Are Transactors — customers who pay in full every month — actually losing money for us on high-rewards cards? Which customers on which products are contributing profit, and which are draining it? (corresponding to SQL queries Q12, Q19)
4. **Promo APR Cliff:** Do accounts acquired via 0% promotional offers fall into delinquency en masse once the promo expires? Can this risk be predicted and intervened on ahead of time? (corresponding to SQL query Q13)
5. **CLI Adverse Selection:** Is our strategy of raising credit lines for "high-utilization customers" rewarding good customers, or handing more leverage to the riskiest ones? (corresponding to SQL query Q9)
6. **Bonus Churner Negative LTV:** Are large signup bonuses breeding "bonus hunters" who take the money and run, leaving the company with negative lifetime value? (corresponding to SQL query Q15)
7. **Vintage Deterioration:** Are our underwriting standards quietly loosening, causing recently opened accounts to go bad faster than older ones? (corresponding to SQL queries Q16, Q17)
8. **Product Ladder Profitability:** Which of our 6 card products is actually the most profitable? Does the intuitive assumption (premium cards are most profitable) hold up? (corresponding to SQL queries Q11, Q12, Q19)

Beyond these eight marquee questions, the dataset also supports a range of operational analyses: acquisition funnel conversion, response model validation, approval rates by tier, utilization distribution, delinquency bucket snapshots, interchange breakdown by category, champion/challenger comparisons, monthly account-opening trends, and more — useful for everyday operational and financial planning questions.

---

## 6. Data Scope Overview

- **Time span:** roughly 24 months of credit card lifecycle activity, all anchored to a fixed reference date, **REFERENCE_DATE = 2026-06-30**. All notions of "current snapshot," "account age (months_on_book)," and "how many months ago" are computed relative to this date rather than the system's current time, so that repeated runs and queries produce consistent, reproducible results.
- **Data volume (order of magnitude, plain terms):** roughly 8,900 accounts, roughly 89,000 rows of monthly statements, roughly 31,000 sampled transactions, 20,000 prescreen offers, 18,000 each of applicants and applications, plus a set of lifecycle event tables, totaling roughly 194,000 rows.
- **Deliberate scoping decisions:**
  - **Single state (California):** all applicants are in California, avoiding cross-state regulatory and geographic noise so the analysis can stay focused on risk, pricing, and customer segments.
  - **Single product category:** consumer credit cards only, with 6 products forming a ladder from secured to premium. No mortgages, auto loans, deposits, or other banking products.
  - **Sampled transactions:** the `transaction` table doesn't store every single real swipe (that would run into the millions), but rather a sampled subset, used for MCC and interchange structure analysis. The complete economic picture at the account level lives in `statement` (monthly billing statements).
  - **One application per applicant:** each applicant corresponds to exactly one application, simplifying away the complexity of "the same person applying multiple times."

(This section does not enumerate specific tables; see the ER document for table structure.)

---

## 7. Industry Knowledge Primer

About half an hour's worth of background you'll need before this data will make sense to an outsider. It's best understood by following "the life of a card."

**1) Stages of the credit card lifecycle.**

Marketing reaches out first, sending prescreen offers or running digital ads to potential customers. Anyone who responds submits an application. Underwriting decides whether to approve or reject based on FICO and other factors, and if approved, assigns a credit line and APR. Once the customer activates, the account is opened. From there, a statement is generated every month: how much was spent, how much was paid, how much interest accrued. Along the way, the account may get a credit line increase (CLI) and earn rewards. If it stays delinquent for roughly 180 days straight, the account gets charged off. Customers may also close their account voluntarily (attrition).

**2) FICO score and risk tiers.** Every applicant has a **FICO credit score (300 to 850)**, calculated by the credit bureau based on payment history. Keystone maps FICO to **five risk tiers, A through E**: A (Superprime, best) down to E (Deep-Subprime, worst). The lower the tier, the higher the default risk, and so the higher the APR charged. This mapping lives in the ER document's `credit_band` table.

**3) APR, Revolver, and Transactor.** APR (annual percentage rate) is the interest rate charged on any balance not paid in full. Someone who pays their balance in full every month is called a **Transactor** (pays no interest); someone who carries a balance is called a **Revolver** (pays interest). This distinction is the key to understanding issuer profitability: Revolvers contribute interest, Transactors only contribute interchange.

**4) Interchange and rewards.** Interchange is the fee the merchant side pays the issuer on every swipe (roughly 1.5% to 2.1%). Rewards are the cash or points the issuer gives back to the customer (0% to 2.5%). When the rewards rate approaches or exceeds the interchange rate, the swipe business alone starts losing money and has to be subsidized by interest or annual fees.

**5) Delinquency, charge-off, and recovery.** DPD (Days Past Due) measures how long a debt has gone unpaid. Delinquency rolls progressively deeper (30 to 60 to 90 days...), and at around 180 days (DPD180) the account is charged off (a loss is recognized on the books). After charge-off, collections may still recover some of the balance. Net loss = charged-off balance minus recovery amount.

**6) Vintage (cohort) analysis.** Accounts are grouped by "quarter opened" (one quarter equals one vintage/cohort), and each group's performance is tracked as it ages. Accounts opened recently haven't finished their full default cycle yet, so a low absolute charge-off count is normal — you have to compare charge-off rates **at the same account age** (say, both measured at months_on_book=6) to fairly compare underwriting quality across different time periods.

**7) Credit Line Increase (CLI) and utilization.** Utilization = balance / credit limit, measuring how close a customer is to maxing out their credit line. A CLI lets good customers spend more, but if it's given to someone who's already maxed out, it may just be adding leverage to risk.

**8) Underwriting score, ROC, and confusion matrix.** At underwriting time, the model assigns each application a risk score (underwriting_score). To evaluate whether this model is any good, data scientists line the score up against the actual outcome (whether the account charged off): plot an ROC curve to see discriminative power, compute AUC (0.5 is a coin flip, 1.0 is perfect), or build a confusion matrix. A model with a good overall AUC doesn't necessarily mean it works for every subgroup — and that's exactly the core of the underwriting model calibration question (corresponding to SQL queries Q3, Q4).

---

## 8. Glossary

For every piece of jargon that shows up in the ER document or the SQL queries, here's a plain-language explanation, plus "why it matters in this project." Terms are kept in English throughout. For a deeper, longer explanation, see the `05` analytics primer.

| Term | Plain-Language Explanation | Why It Matters Here |
|------|----------|----------------------|
| Credit card issuer | A company that issues its own cards and eats its own bad debt | This is exactly Keystone's role |
| FICO score | A personal credit score from 300 to 850 | Determines which risk tier an applicant is assigned to |
| Credit band (A to E) | Risk tiers derived from FICO score buckets | The core dimension for pricing, underwriting, and charge-off analysis |
| Underwriting | The decision process for whether to approve, and how much credit line/APR to grant | The source of decisions in the application table |
| underwriting_score | The underwriting risk model score (0 to 999, higher is safer) | The central figure in the Q3, Q4 calibration analysis and ROC/AUC |
| APR (Annual Percentage Rate) | The annualized interest rate charged on unpaid balances | Pricing for interest revenue |
| Revolver | A customer who carries a balance and pays interest | The issuer's profit engine |
| Transactor | A customer who pays in full every month and pays no interest | May actually lose money on high-rewards cards (Q12) |
| Interchange | The fee merchants pay the issuer on every swipe | One of the three revenue legs, broken down by MCC (Q14) |
| Rewards | Cash/points/miles given back to customers | A major cost, can eat into interchange (Q19) |
| MCC (Merchant Category Code) | Merchant category code | Determines interchange rate and spending mix |
| Annual fee | Yearly card fee | Helps premium cards offset rewards costs |
| DPD (Days Past Due) | Number of days a payment is overdue | The basis for roll rate and early warning |
| Delinquency | Overdue payment status | The general term for delinquency buckets (dpd_bucket) |
| Charge-off | Recognizing a balance as unrecoverable on the books | The biggest risk cost, and the core outcome label in many queries |
| Recovery | Amount recovered after charge-off | Net loss = charged-off balance minus recovery |
| EAD (Exposure at Default) | Exposure amount at the point of default (the charged-off balance) | An input to loss calculations |
| Vintage / Cohort | A group of accounts opened in the same quarter | Q16 tracks how underwriting quality changes over time |
| Months on book (MOB) | Account age, months since the account was opened | Used for vintage curves and early warning |
| Utilization | Utilization rate = balance / credit limit | High utilization contributes both interest and risk |
| CLI (Credit Line Increase) | Raising a customer's credit line | The subject of the Q9 adverse-selection analysis |
| Prescreen | Buying a list from a credit bureau and mailing pre-approved offers | The starting point of the marketing funnel (prescreen_offer table) |
| Response model | A model predicting who will respond to an offer | Used for the Q2 confusion matrix |
| Signup bonus | A bonus for opening a new card | Large bonuses can breed churners (Q15) |
| Bonus churner | Someone who takes the signup bonus and then closes the account | The source of negative LTV |
| Attrition | Account closure/churn | Split into voluntary and involuntary (attrition_event table) |
| LTV (Lifetime Value) | Customer lifetime value | Used in Q15 to identify which customers are unprofitable |
| Champion / Challenger | The steady-state default offer vs. an experimental new offer | Compared for quality in Q18 |
| Promo APR / Balance transfer | Promotional interest rate / balance transfer | The mechanism behind the Q13 promo cliff |
| Approval rate | Approval rate = approvals / applications | An overall gauge of underwriting looseness or tightness |
| Charge-off rate | Charge-off rate = charged-off accounts / total accounts | The core measure of portfolio quality |
| ROC / AUC | The curve and area used to evaluate a classifier's discriminative power | Used in Q3, Q4 to calibrate the underwriting model |
| Confusion matrix | A 2x2 table of predicted vs. actual outcomes | Used to evaluate underwriting/response models |
| CECL | The forward-looking expected credit loss accounting standard | Flows vintage losses directly into the financial statements |
| CFPB / CARD Act / Reg Z / ECOA | US credit card regulations | The compliance baseline for underwriting and pricing |

---

## 9. Key Metrics and Formulas

Below are the metrics used in the SQL queries, or that readers should know. Formulas are written in plain, SQL-style pseudocode, with notes on inputs and conventions. For more detailed derivations and examples, see the `05` analytics primer.

**Underwriting and risk**

```
approval_rate       = COUNT(decision='APPROVED') / COUNT(applications)          -- by tier or time period
chargeoff_rate      = COUNT(account_status='CHARGED_OFF') / COUNT(accounts)      -- core portfolio quality metric
co_rate_by_mob6     = COUNT(CHARGED_OFF AND months_on_book<=6) / COUNT(accounts) -- vintage curve (Q16)
net_loss            = charged_off_balance_usd - recovery_amount_usd             -- net loss per charge-off
```

**Per-account and product P&L**

```
account_margin      = SUM(interest_charged + interchange_revenue + fees_charged - rewards_earned)  -- summed monthly across statements
account_contribution= account_margin - signup_bonus_usd - net_loss             -- full per-account contribution (Q12)
product_pnl         = SUM over accounts of account_contribution                 -- by product (Q11)
net_interchange     = SUM(interchange_revenue) - SUM(rewards_earned)            -- rewards erosion (Q19)
```

> **Convention notes (to keep downstream SQL consistent):**
> - `chargeoff_rate` is uniformly calculated as "number of charged-off accounts / number of accounts," not weighted by dollar amount.
> - "Revenue" in the per-account P&L includes interest, interchange, and fees; "cost" includes rewards, net charge-off loss, and signup bonus. Interest charged (`interest_charged_usd`) is 0 for a Transactor in a normal repayment month (interest only starts accruing once a Transactor stops paying in full and slides toward delinquency and charge-off) — this is exactly the root cause behind trap 3 (Transactor profitability).
> - Vintage comparisons must hold account age fixed (e.g., months_on_book <= 6); otherwise recent cohorts will look artificially "better" simply because they're younger.
> - A higher `underwriting_score` means the model considers the applicant safer, so a healthy model should show "higher score, lower charge-off rate."

**Marketing and acquisition**

```
response_rate       = COUNT(responded=1) / COUNT(prescreen_offer)               -- broken down by model tier (Q2)
activation_rate     = COUNT(accounts) / COUNT(approved applications)            -- funnel conversion (Q1)
net_loss_per_booked = SUM(net_loss by channel) / COUNT(accounts by channel)     -- true channel cost (Q7)
avg_ltv             = AVG(account_margin - signup_bonus)                        -- by attrition reason (Q15)
```

**Utilization and delinquency**

```
utilization_pct     = statement_balance_usd / credit_limit_usd * 100           -- uses latest statement (Q8)
dpd30plus_rate      = COUNT(days_past_due>=30) / COUNT(statements)              -- viewed by account age for promo cliff (Q13)
```
