# Northpeak Lending AI Credit Approval Assistant Business Context

This document is the business overview for the `digital_lending_credit_approval_assistant_high` dataset. It answers everything a new hire needs to figure out in their first week on the job: what kind of company this is, how it makes money, how its industry works, what business problems this data project is meant to solve, and what a pile of lending jargon actually means. Once you've read through it, the ER document (table structures) and the SQL queries document will be much easier to follow.

For data-level details (which fields each table has, constraints, sample rows, DDL), see `02-digital_lending_credit_approval_assistant_high_er_document.md`. For specific queries and the thinking behind them, see `03-digital_lending_credit_approval_assistant_high_sql_queries.md`.

This dataset is built for the North American market. The company is based in the United States, the currency is USD, customers are spread across all U.S. states, and the regulators are American federal and state agencies. The narrative below is written in English and describes a fully U.S.-based company.

---

## 1. Company Profile

Northpeak Lending is a digital consumer lender headquartered in Charlotte, North Carolina. Charlotte is one of America's traditional banking capitals, so there's no shortage of local credit talent. Northpeak was founded in 2016 by a few former bank risk managers and a small group of engineers. Its positioning is "use a faster online experience and smarter risk models to make consumer lending quicker than traditional banks and safer than pure payday lenders."

The company currently has around 280 employees, originates roughly $1 billion in new loans across 2025, and has served tens of thousands of borrowers over its history. It is not a single-product shop: from 30-year fixed mortgages, new-car loans, and used-car loans, to unsecured personal loans, debt consolidation loans, and home equity lines of credit (HELOC), it covers most of the mainstream consumer credit categories an American household would think of. That's why this dataset contains both mortgages and personal loans, which differ dramatically in term, size, and rate.

The organizational structure that matters most for the business is the risk side and the operations side. The CEO oversees the whole company; the CFO handles funding and financial forecasting (FP&A); the CRO (Chief Risk Officer) owns credit policy and risk rules. Reporting into the CRO is the VP of Credit Risk, and beneath them sit credit risk analysts and risk policy analysts. The operations side has a Director of Operations, a Risk Operations Manager, a Fraud Operations Manager, a Document Processing Manager, and a Customer Experience Manager. There are also a Compliance Manager, compliance analysts, a regulatory reporting analyst, marketing analysts, and a data science / ML team responsible for the AI approval assistant. These roles appear repeatedly in the SQL queries document, where each query represents a specific person in a specific role asking a specific business question.

---

## 2. Business Model

Northpeak's primary way of making money is the net interest margin (NIM) — the difference between "the rate it charges customers" and "its own cost of funds." Part of the lending capital is the firm's own equity, and part comes from a warehouse line of credit it rotates through; the cost of funds runs roughly 4% to 6%. The annual percentage rates (APR) charged to customers range from 5.75% for prime borrowers to 18% for subprime borrowers, applied through risk-based pricing. On top of the spread, the origination fee collected at loan funding is another revenue stream.

Who buys these products? U.S. individual consumers with a borrowing need: people buying a house, swapping cars, consolidating several high-interest credit card balances into one lower-rate installment loan, or remodeling a home. Northpeak acquires customers through four channels — web, mobile app, branch, and partner referrals — with the two online channels making up the bulk.

The profitability of this business ultimately turns on two things. The first is whether risk pricing is accurate: if a customer with a true 10% default rate is priced as a 6% risk, the spread won't cover the bad debt and the loan loses money. The second is approval speed and fraud control: if approvals are too slow, customers go elsewhere; if fraud and compliance slip, losses and fines eat the profit. Northpeak is betting that its "AI approval assistant" can improve both at once — speeding up approvals while making risk decisions more consistent.

The entire dataset is built around this business model. Once the AI approval assistant receives a loan application, it automatically does four things: pulls a credit report from the credit bureau, evaluates the application against the risk rule library, retrieves similar historical applications, and produces an approval recommendation for the human underwriter. Low-risk applications that clear every rule are auto-approved; borderline applications are routed for manual review.

---

## 3. Industry Primer

Consumer lending is one of the largest and most heavily regulated sectors of the U.S. financial system. Its purpose is simple: take money from "people who have it today," pass it through an intermediary, and lend it to "people who need it today but can repay later." The intermediary earns the reward for managing risk and term mismatch. Buying a house, buying a car, covering a medical emergency, paying for education, or consolidating debt — nearly every U.S. household interacts with consumer lending many times in a lifetime.

Several types of players operate in this market. Large traditional banks are the biggest in volume and have the lowest cost of funds, but their products and approvals tend to be slow. Credit unions serve local members with friendlier rates. Fintech digital lenders like Northpeak compete on online experience and algorithmic underwriting — flexible, but with higher funding costs. At the bottom sit payday lenders and high-rate subprime shops with very high APRs and a great deal of regulatory controversy. Northpeak aims for the middle ground: "faster than a bank, safer than a subprime lender."

Regulation is an unavoidable backdrop in this industry. Pulling and using credit reports is governed by FCRA (Fair Credit Reporting Act); lending cannot discriminate based on protected characteristics such as race or gender, governed by ECOA / Reg B (Equal Credit Opportunity Act); loan terms and true APR must be disclosed honestly under TILA (Truth in Lending Act); mortgages must additionally meet QM / ATR rules (Qualified Mortgage / Ability to Repay), the most famous of which is the 43% DTI ceiling. The main federal regulators are CFPB (Consumer Financial Protection Bureau) and OCC (Office of the Comptroller of the Currency), while individual states have their own lending licenses and rate caps. That's why this dataset includes tables for audit logs, compliance rules, income verification, and public-record checks — items that don't appear to "make money directly" but matter just as much.

A few forces shaping the industry today are worth noting. First, AI is moving into core underwriting; AI approval assistants like Northpeak's are graduating from "helper" to "semi-automated decision maker," with regulators paying close attention to model explainability and fairness. Second, the rate environment matters: rate hikes over the past two years have pushed funding costs up and compressed margins. Third, fraud keeps getting more sophisticated — synthetic identity fraud is especially difficult to detect. Fourth, fair-lending enforcement is tightening, with regulators using data to scan for differences in approval rates across demographic groups.

---

## 4. Project Framing

You're a full-time data analyst on Northpeak's Credit Risk Analytics team, reporting directly to the VP of Credit Risk and ultimately to the CRO. Your job is not to make loans, but to turn loan data into insight that supports decisions.

Concretely, the company has built an analytics sandbox that consolidates roughly the last 18 months of applications, credit, approval, risk, fraud, and document data into a SQLite database. This sandbox has two purposes. First, it powers self-serve queries and dashboards for various business roles, answering questions like "what was last month's approval rate by product?" or "which states are over-concentrated?" Second, it underpins the AI approval assistant: the assistant needs to retrieve similar historical cases, count rule trigger rates, and compare AI confidence against actual outcomes — all running on the same data.

Your deliverable is a "business SQL query playbook" for interns and junior analysts on the team. Every query in the playbook corresponds to a real question from a real role. Each one both produces a usable business answer and serves as teaching material so newcomers learn how a competent analyst decomposes a business question and writes the SQL. This playbook also doubles as training corpus for Text-to-SQL and LLM Agent demos: natural-language-to-SQL pairs and example agent tool calls all come from here.

---

## 5. Business Questions

This data project is meant to answer five core business questions. Every SQL query downstream maps to at least one of them.

**Q1 Is approval healthy and stable?** How many applications go out per day, how many are approved, and is the approval rate jumping around abnormally? Where in the funnel do we lose the most volume? Are application counts and funded amounts growing or shrinking month over month? This is the daily thermometer the CRO and senior leaders watch, and sharp moves often signal policy drift, system glitches, or shifts in the market.

**Q2 Which products and channels are making money, and where is the geographic concentration risk?** How do different loan products compare in volume, approval rate, and average size? How much funded volume and projected interest income does each acquisition channel deliver? Is the loan book over-concentrated in a handful of states? This drives product strategy, marketing budget allocation, and regulatory reporting.

**Q3 Are our credit policies and risk rules actually predictive?** Is there a meaningful gap between the credit-score distributions of approved versus declined applications? Are DTI distributions healthy by product? Which risk rules trigger far too often or never at all? When a rule fires, is the application more likely to be declined (does the rule have predictive power)? This is the heart of the annual risk-policy review.

**Q4 Are fraud and compliance risks under control?** What's the resolution rate and turnaround time on fraud flags? Among large-balance loans, how many have not had income verified (compliance gap)? How bad is the document verification backlog? These line up directly with regulatory requirements and loss exposure.

**Q5 Can we trust the AI approval assistant?** Does the AI's stated confidence match actual approval outcomes? Does similar-case retrieval give underwriters useful historical reference points? This decides how much of the decision the company can hand over to the model.

---

## 6. Data Scope Overview

The dataset covers roughly the last 18 months of loan application activity. It is an analytical sample of Northpeak's full book, not a complete ledger. In size, it's on the order of "a few hundred applicants, close to a thousand applications, and tens of thousands of process and log records": about 500 applicants, 800 loan applications, plus credit reports, rule evaluations, approval decisions, status history, documents, and fraud flags derived from each application — 18 tables and 18,000+ rows in total.

On the product side, it covers 7 actively offered loan products, 11 loan purposes, 16 risk rules, 5 risk tiers, and 7 application statuses. Geographically, it is limited to the continental U.S. (50 states), with a uniform USD currency.

A note on the time anchor. The generator for this dataset uses relative time (anchored on "now" at generation, looking back about 18 months), and SQL queries use dynamic dates like `DATE('now')` rather than a fixed `REFERENCE_DATE` constant. The benefit is that the data is always "fresh" relative to the run day; the cost is that each regeneration yields a slightly different 18-month window, and runs across midnight are not perfectly reproducible. When reading query results, just interpret "now" as "the day the data was generated / the query was executed."

---

## 7. Industry Knowledge Primer

If you're coming from another industry, this section is the 30-minute background needed to read this data set.

**Credit scores and credit bureaus.** The core of U.S. consumer credit is the FICO score, ranging from 300 to 850. Higher scores mean lower default risk. Roughly, 740+ is considered prime, 670–739 is near-prime, 580–669 is subprime-edge, and below 580 is high risk. FICO scores are maintained independently by the three major credit bureaus — Experian, Equifax, and TransUnion — and the same person's score can differ slightly across them. During underwriting, lenders often do a "tri-merge" (pulling all three bureaus and merging) to be safer, which is why a single applicant in this dataset may have multiple credit reports from different bureaus.

**What you look at in a credit report.** Beyond the FICO score, you look at the utilization ratio (used credit divided by total credit limit — lower is better, ideally under 30%), the number of delinquent accounts, the number of inquiries in the past 6 months (a flurry of recent applications is a danger signal), public records (bankruptcies or court judgments), and the age of the oldest account (longer history equals more stable credit).

**DTI and ability to repay.** The debt-to-income ratio (DTI) equals monthly debt payments divided by monthly income, and it's the key gauge of whether a borrower can afford the loan. Regulators set a 43% DTI cap for Qualified Mortgages (QM); mortgages above that line get additional scrutiny or outright denials. 35% is a common internal warning threshold.

**Secured vs. unsecured.** Mortgages, auto loans, and HELOCs are secured loans backed by a house or vehicle: lower rates, larger amounts, longer terms (mortgages are commonly 180 or 360 months). Personal loans and debt consolidation are unsecured loans with no collateral: higher rates, smaller amounts, shorter terms (commonly 24 to 60 months).

**The loan lifecycle.** A typical application path is: submitted to in review to approved / declined to funded. Along the way the application can be cancelled or expired. Only loans that reach funded actually start generating interest income for the company. Every status transition is recorded in the approval history table for audit purposes.

**Auto vs. manual approval.** Applications with clean credit that clear every rule are decided by the system (auto-approve / auto-decline) — fast and labor-efficient. Borderline applications are routed to a human underwriter for review, or may be tagged as referred. The AI assistant's role is to surface a recommendation and similar cases for both groups, speeding up human judgment.

**Monthly payment and amortization.** The monthly payment on an installment loan is computed from the approved amount, the APR, and the term using the amortization formula. Early payments are mostly interest, while later payments are mostly principal. The company estimates expected interest income from a loan by multiplying the monthly payment by the term and subtracting the principal.

**Risk-based pricing and default.** The same product is priced at different rates for different risk tiers — that's risk-based pricing. The rate has to cover the cost of funds, operating costs, and expected default losses. If a customer segment's real default rate exceeds the assumption baked into the pricing, the company is lending at a loss — and that's exactly the kind of drift risk analytics should be flagging.

**Fraud types.** Common ones include identity fraud, income misrepresentation, address anomalies, device-linked fraud, velocity fraud (the same identity applying repeatedly in a short window), and the trickiest one — synthetic identity fraud (a fake person assembled from a mix of real and fabricated information). Northpeak applies rules and models to flag suspicious applications, then the fraud operations team verifies them one by one.

---

## 8. Glossary

Below are the terms of art that appear in the ER document and SQL queries. Each entry gives the English term, a plain-language explanation, and why it matters in this dataset.

| Term | Plain explanation | Why it matters in this dataset |
|------|-------------------|--------------------------------|
| FICO score | Personal credit score from 300 to 850; higher is better | `credit_report.fico_score`; the starting point for nearly every credit decision |
| credit bureau | Agency that maintains credit records (Experian / Equifax / TransUnion) | A single applicant may have reports from multiple bureaus; queries typically pin to one for consistency |
| tri-merge | Pulling all three bureau reports together and merging | Explains why one person can have multiple rows in `credit_report` |
| utilization ratio | Credit utilization, used / total limit; lower is better | Above 80% triggers a risk rule and is a clear warning sign |
| delinquent account | Credit account that is past due | More delinquencies means higher default risk |
| DTI (debt-to-income ratio) | Debt-to-income ratio, monthly debt / monthly income | Above 43% triggers a hard-stop rule; the QM compliance line |
| QM / ATR | Qualified Mortgage / Ability-to-Repay rule, the regulatory requirements on mortgages | The source of the 43% DTI ceiling |
| APR (annual percentage rate) | Annualized rate, the true yearly cost of borrowing | `approved_interest_rate`, the basis of spread and interest income |
| amortization | The schedule that breaks a loan's principal and interest into level monthly payments | How `monthly_payment` is computed |
| secured loan | Loan backed by collateral (mortgage / auto / HELOC) | Lower rates, larger sizes, longer terms |
| unsecured loan | Loan with no collateral (personal / debt consolidation) | Higher rates, smaller sizes, shorter terms |
| HELOC | Home equity line of credit, a revolving line secured by home equity | One of the most variable products in the dataset for term and size |
| origination | The act of issuing the loan and funding it | The company collects an origination fee; only funded loans count as truly issued |
| underwriting | Evaluating the applicant's risk and deciding whether to approve | The core action of the entire approval process |
| underwriter | Human approver / reviewer | `approval_decision.reviewer_id` records who made the decision |
| auto-decision | A system-issued approval or denial | `decision_type.is_auto` distinguishes machine vs. human decisions |
| risk-based pricing | Pricing the rate to the risk tier | Why rates span from 5.75% to 18% |
| risk score | Internal risk score (0 to 1000); higher is riskier | `approval_decision.risk_score`, mapped to a risk tier |
| risk level | Risk tier (very low to very high) | The `risk_level` table buckets risk scores |
| hard stop rule | A rule whose trigger causes an immediate decline | `risk_rule.severity = 'hard_stop'`, e.g., the credit-score floor |
| decline code | The reason code for a denial | `approval_decision.decline_codes`; required for compliance disclosure |
| delinquency / default | Past due / failure to repay | The core loss that risk management is trying to predict and contain |
| charge-off | Charging off a loan as uncollectible | The terminal state of default; eats the spread |
| velocity check | A frequency check for rapid repeat applications | A category of fraud rule |
| synthetic identity | Fake person assembled from real and fabricated data | One of the hardest fraud types to defeat |
| KYC | Know Your Customer, identity verification requirement | Background context for identity verification and audit |
| income verification | Verifying income via pay stubs / tax returns / etc. | `employment_info.is_verified`, required for high-balance loans |
| NIM (net interest margin) | Net interest margin, lending rate minus cost of funds | The company's primary profit source |
| warehouse line | A revolving credit facility used to fund loan origination | A major component of cost of funds |
| FCRA | Fair Credit Reporting Act | Governs how credit reports are pulled and used |
| ECOA / Reg B | Equal Credit Opportunity Act | Bans lending discrimination based on protected characteristics |
| TILA | Truth in Lending Act | Requires honest disclosure of rates and terms |
| CFPB | Consumer Financial Protection Bureau, the federal consumer finance regulator | The regulatory context for compliance and audit tables |
| OCC | Office of the Comptroller of the Currency, the federal bank regulator | Same as above |
| fair lending | Fair lending — no discriminatory treatment of any group | The compliance motivation behind splitting approval rates by state / demographic |

---

## 9. Key Metrics and Formulas

These are the metrics that will appear in the queries document or that readers should understand. Formulas are written in SQL-flavored pseudocode and are aligned with the generator and the queries.

**Approval rate.** Note that this dataset has two definitions of approval rate, and you need to keep them straight when reading numbers. One is based on the approval decision table:

```text
approval_rate = SUM(approval_decision.is_approved = 1) / COUNT(approval_decision.id)
```

The other is based on application status (treating both APPROVED and FUNDED as approved):

```text
approval_rate = SUM(status IN ('APPROVED','FUNDED')) / COUNT(loan_application.id)
```

The approval rate from `approval_decision` is around 60%. By status, APPROVED is around 40% and FUNDED around 10%, for a combined ~50%. The two come from different, independently generated tables, and you shouldn't force them to match — but pick one definition and stick with it within a single report.

**DTI (debt-to-income ratio).**

```text
DTI = (monthly_debt_payment / monthly_income) * 100
```

In this dataset, `loan_application.debt_to_income_ratio` is pre-computed and ranges roughly from 15% to 55%, with a mean around 35%.

**Utilization ratio.**

```text
utilization_ratio = (total_balance / total_credit_limit) * 100
```

**Monthly payment (level-payment amortization).**

```text
r = (APR / 100) / 12
monthly_payment = principal * r * (1+r)^n / ((1+r)^n - 1)
```

Where principal is the approved amount and n is the term in months.

**Estimated annual interest income.** A rough channel-revenue figure used by finance:

```text
est_annual_interest = SUM(monthly_payment * 12 * (approved_interest_rate / 100))
```

**Average time to decision.** Use SQLite's JULIANDAY to compute the elapsed hours from submission to decision:

```text
avg_hours_to_decision = AVG((JULIANDAY(decision_at) - JULIANDAY(submitted_at)) * 24)
```

**Rule trigger rate.**

```text
trigger_rate = SUM(rule_evaluation.triggered = 1) / COUNT(rule_evaluation.id)
```

The overall trigger rate is around 15%. The expectation is that hard-stop rules trigger less often (under 10%), and warning-level rules can run a bit higher.

**Rule effectiveness (decline rate when triggered).** A measure of whether a rule actually predicts denial:

```text
decline_rate_when_triggered = SUM(triggered = 1 AND is_approved = 0) / SUM(triggered = 1)
```

**Fraud flag resolution rate.**

```text
resolution_rate = SUM(fraud_flag.is_resolved = 1) / COUNT(fraud_flag.id)
```

Around 70% of flags have been resolved (the generator's design probability is 60%, but with only about 80 fraud flags total, the small sample yields an observed value closer to 70%).

**Income verification gap.** The share of high-balance loans without verified income:

```text
verification_gap_pct = SUM(is_verified = 0) / COUNT(*)   -- limited to requested_amount > 50000 and approved / funded
```

**Month-over-month growth.** Use the LAG window function to pull the previous month's value:

```text
growth_pct = (this_month - LAG(this_month) OVER (ORDER BY month)) / LAG(...) * 100
```

A healthy range is roughly 5% to 15%.

**AI confidence buckets.** Split `ai_confidence` into three tiers — low (below 0.7), medium (0.7 to 0.85), and high (above 0.85) — then look at actual approval rates within each bucket to gauge how well the model is calibrated.
