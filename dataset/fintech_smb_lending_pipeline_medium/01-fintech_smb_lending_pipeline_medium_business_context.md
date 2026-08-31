# Fintech — SMB Lending Pipeline Business Context

> This document is the business background for the `fintech_smb_lending_pipeline_medium` dataset. It answers "what kind of company is this, what business does it run, and what problems is it trying to solve." For the data structure, see `02-fintech_smb_lending_pipeline_medium_er_document.md`. For SQL queries, see `03-fintech_smb_lending_pipeline_medium_sql_queries.md`.
>
> Reader profile: you are a sharp new hire who just joined the project. You don't need to be a finance veteran. After reading this document, you should be able to walk into your first standup and intelligently discuss the company's business, the industry, and the questions this analysis is trying to answer.

---

## 1. Company Profile

**Pacific Bridge Lending** is a mid-sized fintech company headquartered in Oakland, in California's San Francisco Bay Area. It focuses on **lending to SMBs (Small and Medium-sized Businesses)**. It is not a bank — it's a non-bank lender that "underwrites with data and funds faster than a bank can."

Company profile (order-of-magnitude figures, not exact):

- **Customers:** roughly 800 active borrowing businesses. The typical customer is a local restaurant, retail shop, technology services firm, construction contractor, or hotel with annual revenue between $200K and $10M.
- **Origination volume:** several hundred million dollars originated cumulatively over the past two years (individual loans of $50K to $500K), translating to an annual origination volume in the $200M–$300M range.
- **Headcount:** around 50 people, including ~20 loan officers, an underwriting team, a collections team, a finance team, and the executive team.
- **Geography:** business is currently concentrated in a single state — California. Customers are distributed across Los Angeles, San Francisco, San Diego, Sacramento, San Jose, Fresno, Oakland, Bakersfield, Anaheim, and Riverside.

The internal roles relevant to this analysis (SQL queries will name these people by title):

| Title | Role description | What they care about |
|------|------|----------|
| CEO | Chief Executive Officer | Customer acquisition strategy, marketing budget allocation, customer segmentation |
| CFO | Chief Financial Officer | Cash flow forecasting, loss provisioning, liquidity |
| CRO (Chief Risk Officer) | Chief Risk Officer | Risk-based pricing, portfolio concentration, investor communication |
| Chief Credit Officer | Chief Credit Officer | High-risk exposure on the books, the weekly risk committee |
| VP of Underwriting | VP of Underwriting | Approval leakage, loan officer performance |
| VP of Operations | VP of Operations | Application processing time, SLAs, headcount planning |
| Marketing Director | Marketing Director | Regional conversion rates, customer acquisition cost |
| Collections Manager | Collections Manager | Early warning signals, delinquency trends |
| Relationship Manager | Relationship Manager | Repricing / refinancing opportunities, customer retention |
| Investment Committee | Investment Committee | Vintage performance, tightness of underwriting standards |

---

## 2. Business Model

Pacific Bridge's revenue model is straightforward: **it earns the interest spread**.

The company uses its own capital plus a **warehouse line of credit** to fund loans, then lends the money out to small businesses at a higher rate, pocketing the spread between "lending rate" and "cost of funds."

- The lending rate to customers ranges from **5.5% to 16.0%**, depending on risk grade.
- The company's own cost of funds is roughly **4%**.
- So the gross spread on each loan is in the range of **1.5pp to 12pp** (pp = percentage point).
- Once a borrower defaults, the loss eats directly into that gross spread — and can eat into principal as well.

So the company's profitability ultimately depends on just two things:

1. **Whether risk pricing is accurate** — does the rate charged cover the real default risk?
2. **Whether defaults are spotted early** — can the company intervene before a borrower fully blows up, keeping losses small and recoveries high?

On unit economics: the average loan is around $200K, with a term of 12 to 60 months, repaid in equal monthly amortizing installments. A correctly priced loan that pays off on time contributes a few percentage points of net spread; a defaulted loan can lose more than half the principal (depending on recovery rate). The whole business is "using many small positive spreads to offset a few large default losses."

---

## 3. Industry Primer: SMB Lending in North America

If you come from a different industry, this section gets you up to speed on SMB lending.

**What the industry creates.** Small businesses (restaurants, retail shops, technology services firms, construction contractors) routinely need a chunk of growth capital: buying equipment, opening a new location, replenishing working capital, or surviving a slow season. Traditional banks often don't like this business — the loan amounts are small, the company's financials are messy, due-diligence costs are high, and the returns are disproportionately low. Fintech lenders fill that gap by using data-driven underwriting and faster approvals (days rather than weeks).

**Main player categories (no real companies named).**

- **Traditional banks and credit unions:** lowest cost of funds, but slow approval and high bar.
- **SBA lenders:** lend under U.S. Small Business Administration guarantee programs. Lower rates but heavy paperwork.
- **Online / fintech lenders:** like Pacific Bridge — fast, flexible, higher rates, serving customers banks won't touch.
- **Merchant Cash Advance (MCA) providers:** buy a discounted share of future revenue. Effective cost is extremely high — the most expensive tier of the market.

**Regulatory and compliance framework (North America).** SMB lending sits under multiple layers of regulation:

- **ECOA (Equal Credit Opportunity Act) and Reg B:** prohibit credit discrimination based on race, gender, and other protected classes.
- **FCRA (Fair Credit Reporting Act):** governs how credit reports may be pulled and used.
- **CFPB (Consumer Financial Protection Bureau):** the federal-level consumer and small-business finance regulator.
- **OCC, FDIC:** prudential regulators of the banking system (non-bank lenders touch this indirectly via partner banks).
- **State-level regulators:** in California, the **DFPI (Department of Financial Protection and Innovation)** licenses and regulates lenders.
- **KYC / BSA / AML:** anti-money-laundering and "know your customer" requirements.
- (Canadian counterpart: federal FCAC and OSFI plus provincial consumer protection laws — this dataset defaults to the U.S. California market.)

**Macro forces right now.** Rising interest rates have driven up the cost of warehouse funding, compressing spreads. The fintech industry is consolidating. AI-driven underwriting is changing how risk is assessed. Post-pandemic, credit quality in cyclical industries (restaurants, hotels) is still being watched closely. Credit overall is tightening. All of this makes "is pricing accurate" and "is concentration too high" things the executive team has to monitor every quarter.

---

## 4. Project Frame: What You're Doing

You are a **data analyst** at Pacific Bridge, pulled into a **quarterly portfolio review** project that reports directly to the **CRO (Chief Risk Officer)**, while also producing materials for the CFO, the Investment Committee, and the board.

The company just closed a quarter, and management has a stack of unresolved questions: are Grade C loans actually underpriced? Is the portfolio too concentrated in restaurants and hotels? Is underwriting rejecting good customers? Are there identifiable warning signals before defaults? Are repeat customers really worth more than new ones? Your job is to use the past ~22 months of complete lending data and answer these questions one by one in SQL — producing conclusions that can go straight into board and investor materials.

Deliverables: the quarterly risk review deck, a pricing-adjustment proposal, an investor risk update, and actionable hit lists for the operations and collections teams. All analysis is anchored to the fixed reference date **REFERENCE_DATE = 2026-06-03** (see section 6).

---

## 5. Business Questions This Project Aims to Answer

The entire dataset is engineered to answer the five core business questions below. Each one has a corresponding deliberately embedded data trap in the ER document and a matching query in the SQL queries document.

1. **Q1 Risk Pricing Alignment:** Does the actual default rate of each risk grade match the implied default rate baked into pricing? Specifically — is Grade C risk underestimated and underpriced?
2. **Q2 Portfolio Concentration:** Is our outstanding portfolio over-concentrated in certain cyclical industries (especially restaurants + hotels)? Could a single-industry shock trigger a cascade of defaults?
3. **Q3 Approval Leakage / False Negatives:** Are we wrongly rejecting a batch of applicants whose profiles look just as good as already-approved top customers? How much interest revenue do these false negatives cost us each year?
4. **Q4 Early Warning Signals:** In the months before a default, is there measurable deterioration in repayment behavior (rising delinquency, partial payments)? Can we catch it 3 months early and intervene?
5. **Q5 Customer Lifecycle Value:** How do repeat customers compare to new customers on default rate, loan size, and approval rate? Should marketing dollars go to acquisition or retention?

Beyond these five marquee questions, the dataset also supports a battery of operational analyses: monthly application volume trends, loan officer performance scorecards, regional conversion rates, application processing time SLAs, monthly cash flow forecasts, vintage cohort analysis, and more — covering day-to-day operations and financial planning.

---

## 6. Data Scope Overview

- **Time span:** roughly 22 months of application activity, all anchored to the fixed reference date **REFERENCE_DATE = 2026-06-03**. Every "today / current snapshot" notion (outstanding balance, whether the loan has matured, months since some event) is calculated against this date rather than the system clock — so multiple runs and multiple queries give identical, reproducible results.
- **Data volume (order of magnitude, in plain English):** about 800 customers, ~3,000 applications, ~2,230 loans, ~81K repayment schedule rows, ~24K actual payments, ~190 default events — about 110K rows total.
- **Deliberate scope choices:**
  - **Single state (California):** all customers are in California, eliminating multi-state regulatory noise and geographic confounds so the analysis can focus on risk and pricing.
  - **Single product line:** only SMB-targeted term amortizing loans. No credit cards, lines of credit, or other products.
  - **Personal guarantor credit:** SMB lending at this scale typically underwrites against the **personal credit score (FICO-style) of the legal entity's guarantor**, rather than commercial credit bureau scores like Paydex or Intelliscore. The dataset is modeled accordingly.

(This section does not list specific tables; see the ER document for the schema.)

---

## 7. Industry Background Primer

Roughly the half hour of background a non-specialist needs before reading this data. Easiest to understand as "the life of a loan."

**1) The seven stages of the lending pipeline.**

```
application → underwriting/decision → disbursement
   → monthly repayment → (possibly) default → collections/recovery → payoff/charge-off
```

- **Application:** the customer submits a desired amount and term; a loan officer takes the file.
- **Underwriting:** the underwriting team uses credit score and other factors to decide APPROVED or REJECTED.
- **Disbursement:** once approved, the funds are wired to the customer and the loan is officially "on the books."
- **Repayment:** the customer repays in monthly installments per the amortization schedule.
- **Default:** after enough consecutive missed payments (industry standard is **90 DPD**), the loan is declared in default.
- **Recovery:** after default, the lender pursues collections, collateral disposition, and legal process to recover some of the principal.
- **Payoff / charge-off:** either fully repaid (PAID_OFF) or losses confirmed.

**2) Credit scores and risk grades.** Each borrower has a **FICO-style credit score (300–850)**. Pacific Bridge maps that score to one of **five risk grades, A through E**: A (Prime, best) to E (Deep Subprime, worst). Lower grade means higher default risk and therefore higher pricing.

| Grade | Name | Score range | Rate | Implied default rate (pricing assumption) |
|------|------|------------|------|--------------------------|
| A | Prime | 720–850 | 5.5% | 3.0% |
| B | Near Prime | 680–719 | 7.5% | 6.0% |
| C | Standard | 640–679 | 9.5% | 6.0% |
| D | Subprime | 600–639 | 12.5% | 13.0% |
| E | Deep Subprime | 300–599 | 16.0% | 18.0% |

**3) Amortization.** The monthly payment is constant, but the split between "interest portion" and "principal portion" shifts over time: early payments are mostly interest, later payments are mostly principal. The **outstanding balance** is how much principal is still unpaid. This dataset uses the standard closed-form amortization formula to compute each loan's outstanding balance as of REFERENCE_DATE.

**4) Default-related concepts.**

- **DPD (Days Past Due):** how many days late a payment is.
- **Default:** industry convention is to declare default at **90 DPD**.
- **Recovery and recovery rate:** amount recovered after default / outstanding balance at default.
- **Loss severity / LGD:** 1 − recovery rate. The fraction of each dollar of defaulted exposure ultimately lost.

**5) Whether pricing is aligned.** Compare each grade's **actual default rate** against its **implied default rate**. If actual > implied, pricing is underpriced — the rate charged doesn't cover the risk, and the lender is losing money on those loans.

**6) Vintage / cohort analysis.** Group loans by origination quarter and track each cohort's default behavior over time. Recently originated loans haven't been through a full cycle yet, so naturally their defaults look low — what matters is the **trend**, not the absolute level.

**7) Warehouse financing.** Pacific Bridge doesn't lend out depositor money. Instead, it draws on a revolving line of credit (the warehouse line) from a large financial institution, and uses that to fund loans. The line carries a minimum cash reserve requirement. So the CFO must forecast cash flow to make sure there's money to service the warehouse line and money to keep funding new loans.

**8) Seasonality and cyclical industries.** Application volume has seasonal swings (e.g., Q4 strong, Q1 weak), which drives headcount planning. Restaurants and hotels are **cyclical industries** that get hit first in a downturn — so the larger the portfolio exposure to those segments, the higher the systemic risk.

---

## 8. Glossary

Each piece of jargon that appears in the ER document or the SQL queries gets a plain-English line here, plus a note on why it matters in this project. Terms are kept in their original English form.

| Term | Plain-English meaning | Why it matters in this project |
|------|----------|----------------------|
| SMB (Small and Medium-sized Business) | Small and medium-sized businesses — this company's customer base | The whole business revolves around lending to SMBs |
| FICO score | A 300–850 personal credit score | Determines which risk grade a customer is mapped into |
| Risk grade (A–E) | Risk tier derived by bucketing credit scores | Core dimension for pricing and default-rate analysis |
| Implied default rate | The default rate the pricing model **assumes** | Q1 compares it against the actual default rate |
| Actual default rate | The default rate **observed** in the data = defaults / loans | The other half of Q1; reveals pricing gaps |
| Pricing gap | implied − actual. Negative = underpriced | Q1's headline metric; Grade C is roughly −4pp |
| DPD (Days Past Due) | Days past due | 90 DPD is the default-declaration threshold |
| Default | A borrower seriously delinquent and declared in default | The source of loss; central to multiple queries |
| Charge-off | Accounting recognition that the receivable is uncollectible | Finance action related to default |
| Recovery rate | Share recovered post-default = recovered / defaulted exposure | Q10 looks at recovery strength by grade |
| Loss severity / LGD | Loss severity = 1 − recovery rate | The CFO uses it to size expected-loss provisions |
| EAD (Exposure at Default) | Exposure at the moment of default (outstanding balance) | One term in the expected-loss formula |
| Outstanding balance | Principal still unpaid | Foundation of portfolio exposure, concentration, cash flow |
| Amortization | Equal monthly payments split into principal + interest | Determines how the repayment schedule and outstanding balance are computed |
| Monthly payment / installment | The single monthly payment owed | The unit on which scheduled vs. actual repayment is compared |
| Disbursement | Loan funding — wiring the money to the customer | The start of the loan lifecycle |
| Maturity date | Expected final payment date | Used to judge whether a loan should be paid off |
| Term (months) | Loan term in months (12/24/36/48/60) | Drives monthly payment and amortization pace |
| Origination | Loan origination (going on the books) | Vintage analysis groups by origination quarter |
| Vintage | A cohort grouped by origination time | Q13 looks at underwriting quality by vintage |
| Cohort | A group sharing some common attribute | Early-repayment-behavior cohorts (Q8) |
| Warehouse line | Warehouse credit facility used to fund lending | Determines cost of funds and cash flow constraints |
| Interest spread / NIM | Spread / net interest margin | The company's core source of profit |
| Approval rate | Approval rate = approved / applied | Overall measure of underwriting tightness |
| Conversion rate | Conversion rate (application → funded) | Regional and marketing efficiency (Q11) |
| False negative / Approval leakage | Wrongly rejecting a good customer | Q3's subject; the revenue we leave on the table |
| Early warning | Behavioral signals ahead of default | Q4's subject; the basis for early intervention |
| Repeat customer | Repeat customer (a tier flag set at onboarding) | Q5/Q20 separate new vs. repeat performance |
| LTV (Lifetime Value) | Customer lifetime value | Q20 customer segmentation |
| CAC (Customer Acquisition Cost) | Customer acquisition cost | Q11 supplies the denominator (application volume) |
| DTI (Debt-to-Income) | Debt-to-income ratio | A common reason for rejection |
| DSCR (Debt Service Coverage Ratio) | Debt service coverage ratio | Real-world underwriting uses it; simplified out of this dataset |
| Collateral | Collateral | Affects recovery rate |
| EIN / tax_id | Federal Employer Identification Number (business tax ID) | The customer's unique identifier |
| ECOA / Reg B | Equal Credit Opportunity Act | The compliance floor against discriminatory underwriting |
| FCRA | Fair Credit Reporting Act | Governs use of credit reports |
| CFPB / OCC / FDIC / DFPI / SBA | North American financial regulators at various levels | Regulatory backdrop of the industry |
| KYC / BSA / AML | AML and customer due diligence | Lending intake compliance |
| SLA (Service Level Agreement) | Service level agreement (e.g., decision within 7 business days) | Q18 measures processing time |
| ACH | Automated Clearing House (U.S. bank transfer) | One of the main repayment methods |
| NTILE / decile | Equal-bucket ranking (decile = tenths) | Q20 uses window functions for customer tiering |

---

## 9. Key Metrics and Formulas

Below are the metrics used in SQL queries — or that the reader should know. Formulas use plain notation (SQL-style pseudocode) with notes on inputs and conventions.

**Default and pricing**

```
actual_default_rate(grade) = COUNT(defaulted_loans) / COUNT(loans)        -- by grade
pricing_gap(grade)         = implied_default_rate − actual_default_rate    -- negative = underpriced
```

**Recovery and loss**

```
recovery_rate  = SUM(recovery_amount)   / SUM(outstanding_at_default)
loss_severity  = SUM(loss_amount)       / SUM(outstanding_at_default)  = 1 − recovery_rate
expected_loss  = outstanding_balance × implied_default_rate            -- per-loan expected loss, approximate
```

**Amortization (convention: standard equal-monthly-payment)**

```
r = annual_interest_rate / 100 / 12
monthly_payment    = P × r × (1+r)^n / ((1+r)^n − 1)        -- P=principal, n=number of periods
outstanding_balance(k) = P × (1+r)^k − monthly_payment × ((1+r)^k − 1) / r   -- remaining principal after k payments (closed form)
```

**Approval and operations**

```
approval_rate     = COUNT(approved_applications) / COUNT(applications)
conversion_rate   = COUNT(approved_loans) / COUNT(applications)            -- by region (Q11)
days_to_decision  = decision_date − application_date
sla_compliance    = COUNT(days_to_decision ≤ 7) / COUNT(applications)      -- SLA = 7 business days (Q18)
late_payment_rate = COUNT(payments WHERE days_late > 0) / COUNT(payments)  -- late-payment rate (Q14)
```

**Customer and portfolio**

```
repeat_default_lift = default_rate(first_time) / default_rate(repeat)      -- roughly 2x (Q5)
concentration(industry) = SUM(outstanding_balance WHERE industry) / SUM(outstanding_balance)  -- portfolio share (Q2/Q19)
ltv_score = total_borrowed + estimated_lifetime_interest − (defaults × 50000)  -- for relative ranking only (Q20)
estimated_lifetime_interest = SUM(approved_amount × interest_rate/100 × term_months/12)  -- simple-interest approximation, overstates true amortized interest by ~2x, only used for relative ranking
```

> **Convention notes (to keep downstream SQL from arguing with itself):**
> - Default rate is uniformly computed as "defaulted loan count / loan count," not dollar-weighted.
> - `is_repeat_customer` is a **marketing / loyalty tier flag set at onboarding**, not a statistic derived from loan count. It correlates positively with "having multiple loans" but is not equivalent (see the customer table notes in the ER document). The "retention opportunity" group in Q12 uses a different **operational definition** (PAID_OFF in the last 12 months and no application in the last 6 months); the two populations overlap but aren't the same.
> - `expected_loss` uses `implied_default_rate` (the pricing assumption), not the actual default rate, because it represents "the expected loss the original pricing model should have provisioned for."
> - `estimated_lifetime_interest` inside `ltv_score` uses a simple-interest approximation that overstates true amortized interest by roughly 2x. It is only valid for **relative** customer ranking, not actual interest accounting.
