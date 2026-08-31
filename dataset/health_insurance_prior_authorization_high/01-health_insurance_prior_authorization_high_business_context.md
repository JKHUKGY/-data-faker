# Meridian Health Plan Prior Authorization Operations - Business Context

This document is the main entry point for the `health_insurance_prior_authorization_high` dataset. It explains who this fictional company is, how it makes money, how the health insurance industry it operates in works, what role you play on the project, what business questions you need to answer, and the industry common sense and terminology you need to know before you can read the data. After reading it, a newcomer to the project should be able to follow what colleagues are talking about at their first standup.

The ER document (`02-health_insurance_prior_authorization_high_er_document.md`) covers the data itself (tables, fields, constraints, generation rules). The SQL queries document (`03-health_insurance_prior_authorization_high_sql_queries.md`) teaches you how to use SQL to ask these business questions. Both documents assume you have already read this one.

The market is North America by default. The company is based in Texas, the currency is USD, and the regulators are U.S. federal frameworks like CMS and HIPAA. English is the narrative language; the business itself is a U.S. regional health insurance company.

---

## 1. Company Profile

**Meridian Health Plan** is a fictional regional health insurance payer headquartered in Austin, Texas. It sells insurance on the ACA individual marketplace, with products organized across four metal tiers (Bronze, Silver, Gold, Platinum) and three product lines (HMO, PPO, EPO). It sells primarily in Texas and four neighboring states, with member residence roughly distributed as TX 70%, OK 8%, LA 8%, AR 7%, NM 7%.

At production scale, Meridian serves about 250,000 enrolled members. This dataset is an analytical sample deliberately scaled down from that production book of business, retaining only 400 members and 12 months of prior authorization operating history. The scale-down keeps query result numbers readable; at production scale the story logic is identical.

A few roles in the company's org structure show up repeatedly in this dataset's reports. The operations track has an Operations Director and an Operations Manager who runs the daily ops huddle. The medical track has a Medical Operations Manager and a Medical Director who handles escalated complex cases. The compliance track has an SLA Director who watches turnaround times. The appeals track has an appeals operations team. The network track has a Provider Network Manager. The executive team has the CEO, CMO (Chief Medical Officer), COO (Chief Operating Officer), and CFO. The analytics team (where you sit) produces reports for all of these people.

---

## 2. Business Model

The way a health insurance payer makes money is unlike most industries, so it is worth a minute to spell out. Meridian collects monthly premiums from members, pools that premium income into a fund, and uses that pool to pay for medical costs (claims) incurred by members. Profit is roughly "premium revenue plus investment income" minus "claims paid plus administrative cost." Put differently, the company is fundamentally running a risk pool: most members never spend all of their premium, a few high-cost members blow through theirs, and the actuarial job is to keep the whole pool's books in the black.

The core indicator of whether this business is healthy is the Medical Loss Ratio (MLR), the share of premium income that goes to medical claims. ACA rules require individual-market MLR to be at least 80%, meaning for every $100 of premium collected, at least $80 must be spent on member medical care or the difference must be rebated back to members. This rule compresses payer margins thinly, which is why controlling medical spend (rather than simply denying claims) becomes the lifeblood of operations.

On pricing, premiums scale with metal tier. In this dataset, Bronze monthly premiums run about $320, Silver about $480, Gold about $640, and Platinum about $820. Higher tiers come with lower member out-of-pocket thresholds (deductibles) and lower annual out-of-pocket maximums, which is why they cost more and cover more.

Prior Authorization (PA) is the payer's key cost-control lever. Before performing certain high-cost procedures or prescribing certain high-cost drugs, the provider must request authorization from Meridian. The review team decides whether to approve based on medical necessity and coverage policy. Approval is the company's commitment to pay for the service; denial blocks unnecessary or substandard spend at the gate. PA has to prevent overutilization without blocking legitimate care, and that balance is exactly what this dataset is built to quantify.

---

## 3. Industry Overview

U.S. health insurance is a market pulled between payers and providers on each end and squeezed between federal and state regulators in the middle. Payers (also called health plans or insurers) collect premiums, bear risk, and pay bills. Providers (hospitals, clinics, surgery centers, physicians) deliver care and bill the payer. This dataset sits on the payer side, at Meridian.

The market has a few main types of players. First are the national large payers, with massive scale and full product lines. Second are regional payers like Meridian, rooted in a few states and more dialed in to local provider networks. Third are state-licensed plans such as Blue Cross Blue Shield. Around the payers, two supporting roles matter: Pharmacy Benefit Managers (PBMs) handle the prescription drug piece, and Independent Review Organizations (IROs) provide third-party adjudication when a member appeals a denial externally.

On the regulatory side, the most important body is CMS (Centers for Medicare & Medicaid Services), which sets PA turnaround time rules (for example, urgent requests must be decided within 72 hours). HIPAA governs patient privacy and data exchange standards; the clinical notes and diagnosis codes in this dataset all qualify as HIPAA-protected health information (PHI). The ACA (Affordable Care Act) defines the individual marketplace, metal tiers, and the minimum MLR.

A few forces are currently shaping the industry and are worth knowing. First, PA reform: CMS finalized the Interoperability and Prior Authorization Final Rule in 2024, requiring payers to publish PA approval data, shorten turnaround times, and move to electronic workflows. The industry is being pushed to make PA faster and more transparent. Second, automation and AI: more and more "no-brainer approvals" are being handed to rules engines, with humans reserved for the hard cases. The auto_rule reviewer in this dataset reflects that trend. Third, public and regulatory scrutiny of denial rates: too many denials draws complaints, appeals, media, and regulator attention, and payers must be able to demonstrate their denials are well-founded rather than driven by cost cutting.

---

## 4. Project Background and Your Role

You are a data analyst at Meridian, embedded in the utilization management (UM) analytics team. You report into the UM track and your day-to-day customers are leads in operations, medical, compliance, appeals, and finance. The company has just consolidated the past 12 months of PA operations data into a payer-side operational data mart, and your job is to use it to build a standing analytical layer: daily operational reports, weekly compliance and appeals reviews, and monthly trend material for the board and executives.

Your output reaches a lot of people. The ops huddle wants the open queue and stalled requests. The SLA Director wants turnaround compliance rates. The CMO and COO want the quarterly trend of decision mix and automation share. The CFO wants authorization-to-claim conversion, leakage, and the dollar value recovered through appeals. The Provider Network Manager wants to know which providers have anomalous approval rates. These are not one-off pulls; they need to be repeatable, definitionally consistent metrics.

On time: the data is anchored to the generation day (TODAY) and covers the prior 12 months. All rolling-window reports (last 30 days, last 90 days, last 6 months) use that anchor as the reference point.

---

## 5. Business Questions to Solve

The whole dataset and its SQL queries are organized around the specific questions below. Each one can be answered by one or a few queries against the data.

**Question 1: Turnaround time and capacity.** What is our PA request volume by urgency, what is the status mix, and are we staying within the CMS turnaround time rules? Which requests are stuck in the queue past SLA without a decision? These bear directly on compliance risk and staffing.

**Question 2: Are approvals and denials fair and well-calibrated?** How much does approval rate vary across metal tiers, specialties, and in-network vs. out-of-network? Is Bronze's clearly lower approval rate by actuarial design, or is policy calibration off? Are there providers with anomalously high or low approval rates that warrant an audit?

**Question 3: Concentration of denial reasons.** How do the structured denial reason codes (CARC/RARC) distribute? Do a small number of codes explain most denials (Pareto shape)? Identifying the "vital few" codes lets us run targeted provider re-education and policy clarification.

**Question 4: Authorization-to-claim leakage.** How many approved authorizations never turn into a claim (a member got the auth but never went in for the service)? This leakage rate is the CFO's leading indicator for whether reserves are overstated.

**Question 5: Appeals workflow and overturn rates.** What share of denials get appealed, what is the flow through the multi-level appeals process (L1 internal, L2 internal, external IRO), and what is the overturn rate at each level? A high L1 overturn rate means first-pass review is making too many mistakes; a high external overturn rate means internal denial policy is too strict. Overturned denials also convert into a dollar "recovery" figure.

**Question 6: Automation effectiveness.** How many decisions did the auto_rule engine, clinical reviewers, and medical directors each handle, and what is the cost and approval mix? Is the automation share holding up and is human review actually being reserved for the hard cases?

---

## 6. Data Scope Overview

The dataset covers 12 months of PA operations history anchored at the generation day. It is a payer-side operational data mart, not an AI model evaluation log from some SaaS vendor. Every table maps to a real link in Meridian's PA business, from member insurance plans, provider network status, the PA requests themselves, the structured clinical items and unstructured clinical notes carried by the requests, the facts extracted from those notes, the decisions, the policies that were applied, the appeals those trigger, and finally the downstream claims once services are actually performed.

The data volume is intentionally small: 400 members, about 700 PA requests, and about 8,200 rows spread across 15 tables. Scope was narrowed in a few deliberate ways. Members only cover the 5 states Meridian actually sells in. Claims are modeled with a "one authorization, one claim" simplification (in real life a long-term-therapy authorization would generate multiple claims). About 70 in-flight requests are intentionally held in the open queue so that operational metrics like "open queue" and "stalled requests" have observable samples. These simplifications exist to keep the BI surface clean and the numbers intuitive.

On the time anchor, this dataset has one convention worth calling out. The generator resolves TODAY at runtime using `date.today()` and anchors all timestamps to the run day. SQL queries therefore use rolling-window expressions like `DATE('now', '-N days')` rather than hardcoded fixed dates. Each time the data is regenerated, the timeline shifts as a whole to the new "today," so rolling-window filters always return non-empty results after regeneration. Regenerating on the same day (with the fixed seed 42) produces byte-identical data; regenerating across days yields stable row counts and distributions, but specific timestamps shift with the day.

---

## 7. Industry Knowledge Primer

This section is the half-hour of background an outsider needs before reading the dataset.

**The PA end-to-end flow.** A prior authorization roughly moves through these steps. The provider submits a PA request (`pa_requests`) that carries diagnosis and procedure codes (`request_clinical_items`) plus unstructured clinical notes (`clinical_notes`). The front-end intake step extracts key structured facts from the notes (`extracted_clinical_facts`). A reviewer compares the request against payer policy and renders a decision (`pa_decisions`, recording which policy was applied). If denied, the member or provider can file an appeal (`appeals`, `appeal_letters`). If approved and the service is actually delivered, a downstream claim is generated (`claims`).

**Urgency and CMS turnaround.** PA requests are tiered into three urgencies, each with its own turnaround SLA: routine is 14 days (336 hours, CMS standard), urgent is 72 hours (CMS urgent standard), and emergent is 2 hours (internal SLA). One emergent breach can directly delay a patient's care, whereas 1 in 100 routine breaches is normal noise, so even though both count as SLA violations, the severity is worlds apart.

**Metal tier and cost sharing.** ACA uses metal tiers to express coverage richness. Bronze has the lowest premium but the highest member out-of-pocket; Platinum is the opposite. Member out-of-pocket is composed of several pieces: copay (a fixed-fee co-payment), deductible (annual out-of-pocket threshold the member pays first), and coinsurance (proportional sharing after the deductible is met). In this dataset, member out-of-pocket as a share of the allowed amount is roughly Bronze 30%, Silver 24%, Gold 17%, Platinum 13%.

**Medical coding systems.** The clinical world speaks in three code sets. CPT codes describe "what procedure was done" (e.g., 27447 is total knee replacement); ICD-10 codes describe "what condition was diagnosed" (e.g., M17.11 is primary osteoarthritis of the right knee); HCPCS codes (especially the J-codes that start with J) describe drugs and supplies (e.g., J1745 is infliximab). A PA request usually carries both diagnosis codes (why it is needed) and procedure codes (what will be done).

**Denial reason codes.** Denials are not just free text; structured reason codes sit behind them: CARC (Claim Adjustment Reason Code) and RARC (Remittance Advice Remark Code), e.g., CO-50 "Not medically necessary" or N-130 "Refer to plan benefit document." Structured codes cluster cleanly for statistics, which is the foundation of denial analysis.

**Appeals levels.** After a denial, appeals run in three levels: L1 is the first internal review, L2 is a higher-level internal review (usually handled by the Medical Director), and external review is adjudicated by an independent third-party IRO (represented in the data with level_number = 3 and is_external_review = TRUE). Each level up brings more labor cost and tighter time requirements. An overturn means the original denial was judged wrong.

**Automated review.** Not every decision needs human eyes. The auto_rule engine handles a large volume of clearly-rule-based "no-brainer approvals" at only a few dollars per decision. Clinical reviewers (clinical_reviewer) and medical directors (medical_director) handle complex cases and denials, with the latter costing much more per decision. Automation rate is a key measure of operational efficiency.

---

## 8. Glossary

The table below collects the English terms used in the ER document and SQL queries, with a layman's explanation and why each one matters in this dataset. Abbreviations are spelled out on first appearance.

| Term | Meaning (plain English) | Why it matters here |
|---|---|---|
| Prior Authorization (PA) | Pre-approval from the insurer before performing certain procedures or dispensing certain drugs | The central business object of the whole dataset |
| Payer | The payer, i.e. the insurance company that collects premiums and pays claims | Meridian is the payer; the data sits on its side |
| Provider | The service side: hospitals, clinics, physicians delivering care | The originator of PA requests |
| ACA Marketplace | The individual insurance exchange under the Affordable Care Act | Meridian's sales channel |
| Metal Tier | Bronze/Silver/Gold/Platinum, expressing coverage richness | Approval rate and out-of-pocket share both vary by tier |
| HMO / PPO / EPO | Three network management models; differ on whether out-of-network is allowed and whether referrals are required | Product line dimension |
| Premium | The monthly amount the member pays | The payer's revenue source |
| Deductible | Annual out-of-pocket threshold the member pays before insurance kicks in | Drives the member cost-share structure |
| Out-of-Pocket Max | Annual cap on member out-of-pocket; insurance covers everything above it | Key parameter of coverage richness |
| Cost-sharing | Umbrella term for member out-of-pocket (copay, deductible, coinsurance) | Q27 computes the member share |
| Coinsurance | Proportional sharing after the deductible is met | A component of out-of-pocket |
| MLR (Medical Loss Ratio) | Claims paid as a share of premium revenue; ACA requires at least 80% on individual | Explains why cost control matters |
| Utilization Management (UM) | Managing healthcare resource use via tools like PA | The function of your team |
| CPT | Procedure code, describing "what was done" (e.g., 27447 total knee replacement) | Core coding for requests and claims |
| ICD-10 | Diagnosis code, describing "what condition" (e.g., M17.11 osteoarthritis right knee) | Establishes medical necessity |
| HCPCS / J-code | Drug/supply codes; J-codes are injectables (e.g., J1745 infliximab) | Coding for drug PAs |
| DME | Durable Medical Equipment (wheelchairs, walkers, etc.) | Some HCPCS codes map to this category |
| NPI | National Provider Identifier | Provider primary key |
| CARC | Claim Adjustment Reason Code (e.g., CO-50) | Structured denial reason |
| RARC | Remittance Advice Remark Code (e.g., N-130) | Structured denial reason |
| SLA | Service Level Agreement, the time-to-decide commitment | Core constraint for compliance and operations |
| TAT (Turnaround Time) | Time from submission to decision | Materialized in the tat_hours field |
| Medical Necessity | Whether the service is clinically necessary in this case | The core test for approval |
| Step Therapy | Require trying cheaper first-line therapy before moving to expensive options | A common denial reason |
| Pended | On hold: missing info, awaiting documentation | A non-terminal decision state |
| Escalated | Escalated for further review by the medical director | Handling of complex cases |
| Partial Approval | Approving some service lines and denying others | A decision type |
| Appeal | A member or provider's request for review of a denial | Subject of Q10 through Q12 and Q28 |
| IRO | Independent Review Organization, third-party external review body | The outermost appeals level |
| Overturn | Appeal succeeds; the original denial is reversed | Measures first-pass review quality |
| Claim | The billing record after the service actually occurs | The downstream of PA |
| Billed / Allowed / Paid Amount | Billed amount / plan-allowed amount / amount actually paid | The three dollar layers of a claim |
| Member Responsibility | Member out-of-pocket dollar amount | The core of Q27 |
| Leakage | An authorization that was approved but never became a claim | Subject of Q9 |
| Auto-adjudication / auto_rule | Automated review; a rules engine renders the decision | The source of the automation rate |
| Medical Director | Senior physician who handles escalations and tough denials | A high-cost reviewer role |
| Confidence Score | The reviewer's confidence in the decision (0.55 to 0.99) | Analysis subject in Q15 |
| Coverage Policy | The document that defines when a given procedure can be approved | Basis for decisions; subject of Q21 |

---

## 9. Key Metrics and Formulas

Below are the core metrics used in this dataset's SQL queries. Definitions are pinned here so downstream queries do not each calculate their own way.

**Approval Rate** measures the share of decided requests that were approved. Note that the numerator includes partial_approved as "partially approved."

```
approval_rate = COUNT(decision IN ('approved','partial_approved')) / COUNT(all decisions)
```

**Denial Rate** is the share of decided requests that ended in denial.

```
denial_rate = COUNT(decision = 'denied') / COUNT(all decisions)
```

**Turnaround Time (TAT)** is the number of hours from submission to decision. It is already materialized in `pa_decisions.tat_hours`; queries should use it directly rather than recomputing JULIANDAY differences each time.

```
tat_hours = (decided_at - submitted_at) converted to hours
```

**SLA Breach Rate** is the share of decisions whose turnaround time exceeded the SLA window for that urgency. Whether each decision breached is already materialized in `pa_decisions.sla_breached`.

```
sla_breach_rate = COUNT(tat_hours > sla_hours) / COUNT(all decisions), grouped by urgency
```

**PA-to-Claim Conversion / Leakage** measures how many approved authorizations actually produced a claim.

```
conversion_rate = COUNT(DISTINCT claims) / COUNT(DISTINCT approved decisions)
leakage_count   = COUNT(approved decisions) - COUNT(approved decisions with a claim)
```

**Appeal / Escalation Rate** describes the shape of the appeals funnel.

```
l1_appeal_rate       = COUNT(denials with an L1 appeal) / COUNT(all denials)
l1_to_l2_escalation  = COUNT(decisions reaching L2) / COUNT(decisions with L1)
l2_to_ext_escalation = COUNT(decisions reaching external) / COUNT(decisions with L2)
```

**Overturn Rate** is the share of resolved appeals overturned at a given level.

```
overturn_rate = COUNT(overturned) / COUNT(resolved appeals), grouped by level_number
```

**Automation Rate** is the share of all decisions rendered by the auto_rule role.

```
automation_rate = COUNT(decisions by auto_rule) / COUNT(all decisions)
```

**Member Cost-share %** is member out-of-pocket as a share of the plan-allowed amount, used to verify that actuarial design held up once claims landed.

```
member_share_pct = SUM(member_responsibility_usd) / SUM(allowed_amount_usd), grouped by metal_tier
```

**Paid % of Billed** reflects the discount from billed to paid.

```
paid_pct_of_billed = SUM(paid_amount_usd) / SUM(billed_amount_usd)
```

**MoM Growth** is used for monthly volume trends.

```
mom_growth_pct = (this month volume - last month volume) / last month volume
```

**Recovery Amount from Appeals** is the sum of the expected billed amounts for the procedure codes attached to overturned denials, quantifying the operational cost of first-pass errors.

```
recovery = SUM(service_catalog.avg_billed_amount_usd) covering all CPT/HCPCS line items for overturned denials
```
