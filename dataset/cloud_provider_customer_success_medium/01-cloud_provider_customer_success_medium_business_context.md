# NimbusScale Customer Success Management: Business Context

> **Dataset:** `cloud_provider_customer_success_medium`
> **Fictional company:** NimbusScale, Inc.
> **Market:** North America (Seattle HQ, billing currency USD)
> **Reference "today" (REFERENCE_DATE):** `2026-06-20`
> **Companion documents:** Data structure in `02-cloud_provider_customer_success_medium_er_document.md`, queries in `03-cloud_provider_customer_success_medium_sql_queries.md`

This document is the opening act for the whole dataset. It first lays out what kind of company NimbusScale is, how it makes money, and how the cloud-infrastructure-plus-customer-success industry actually works, before getting to the business problems you need to solve. Every piece of jargon that shows up in the ER document and SQL queries has a plain-English explanation in the glossary here. After reading this, an intern joining the project on day one should be able to hold their own in the first standup.

---

## 1. Company Profile

NimbusScale, Inc. is a fictional mid-market cloud infrastructure provider based in North America. It was founded in 2019, headquartered in Seattle, Washington, with regional offices in Frankfurt, Tokyo, and Sao Paulo. In a market dominated by the three "hyperscalers" (the industry shorthand for the giant cloud vendors), NimbusScale deliberately stakes out a narrower lane: "mid-market plus AI-friendly." Its customers are companies with 50 to 100,000 employees, and NimbusScale bundles **compute, storage, network, and AI/ML inference** into a single contract, a single bill, and a single CSM point of contact. What it really sells is peace of mind.

The company has roughly 150 paying customers worldwide, and its revenue is built on **subscription ARR**, billed monthly against a contractually agreed `monthly_committed_spend`. NimbusScale is a mid-sized company (revenue in the tens of millions of USD, headcount in the low hundreds). One historical quirk: the company's email domain `@cloudprovider.com` is the original domain from before the brand was rolled out, and it stuck around. That is why CSM email addresses look like `firstname.lastname.<id>@cloudprovider.com`.

The org-chart roles that matter for this dataset (and that the SQL queries call out by title) are:

- **CRO / VP of Sales** and **Regional Sales Director** care about portfolio mix, regional spend rankings, and expansion opportunities.
- **CFO / Finance** cares about committed vs. actual spend for Enterprise customers, i.e., the revenue-recognition view.
- **VP of Customer Success** and **Director of Customer Success** care about renewal risk and QBR completion.
- **CSM Manager** and **Ops Director / Ops Manager** care about team throughput, work queues, and whether CSM workloads are balanced.
- **VP of Product** cares about adoption of AI/ML services.
- **The CSM personally** needs a "Customer 360" snapshot before any customer meeting.

Your role at NimbusScale is spelled out in Section 4.

---

## 2. Business Model

NimbusScale makes money in a very straightforward way: it sells subscriptions and collects subscription fees. A customer signs a contract with NimbusScale that locks in a `monthly_committed_spend` (the floor for monthly revenue). Whatever the customer actually consumes across compute, storage, network, and AI/ML gets metered and rolled up into `total_spend`. When actual consumption exceeds the committed floor, the difference is called **overage**, which is the upside on revenue and the single biggest signal sales loves to see for an upsell.

Customers are grouped into four **tiers (account levels)** by size and ability to pay. Each tier maps to a different annual contract value (ACV), a different sales motion, and a different intensity of CSM service. This table is the key to understanding the whole dataset:

| Tier | Employee count | Annual Contract Value (ACV) | Sales motion | CSM service model |
|------|----------------|------------------------------|--------------|---------------------|
| **Enterprise** | 5,000 to 100,000 | $600K to $6M | Strategic AE plus Solutions Architect (SA) | High-touch CSM, roughly 1:5, named owner |
| **Business** | 500 to 10,000 | $120K to $960K | Mid-Market AE | Mid-Market CSM, roughly 1:15 |
| **Pro** | 50 to 1,000 | $12K to $180K | Inside sales plus self-serve | Pooled Mid-Market / SMB CSMs |
| **Basic** | 5 to 100 | $1.2K to $36K | Self-serve, PLG | SMB CSM, tech-touch only when risk surfaces |

The margin structure is classic SaaS / cloud reseller: high-tier customers pay more per seat and get bigger discounts (Enterprise discounts run 10% to 30%, Basic gets almost none), but they bring in steady, large-ticket ARR. Low-tier customers pay less per seat but show up in volume, and self-serve keeps the cost-to-serve down. Profit ultimately hinges on two things: **renewal rate** (holding onto existing ARR) and **expansion rate** (growing new ARR inside existing accounts). That is exactly why NimbusScale invests in a 15-person customer success team rather than treating a signed contract as the finish line.

---

## 3. Industry Overview

If you come from a different industry, this section will get you up to speed on the "cloud infrastructure plus customer success" business.

**What this market sells.** Cloud infrastructure providers carve up the servers, disks, network, and GPUs sitting in their data centers and rent them out by the unit, so customers can run apps and AI models without buying any hardware themselves. A **mid-market specialist** like NimbusScale lives between two extremes: on one end, the hyperscalers, who do everything themselves at enormous scale; on the other, niche tools that do exactly one thing. The mid-market pitch is to bundle multiple resources together and assign a real person (the CSM) to help customers get value out of them, in exchange for the customer paying a premium and renewing for years.

**What customer success actually is.** In a subscription business, signing the contract is the start of revenue, not the end. Every customer can choose not to renew next year, so retaining and expanding existing customers beats chasing new logos. That is what customer success exists for: the **CSM (Customer Success Manager)** watches account health, intervenes ahead of renewal, and surfaces expansion opportunities when an account is growing. The standard tooling stack in this industry is **Gainsight (health scores and CTAs) plus Salesforce (accounts and contracts) plus Zendesk (support tickets)**, and NimbusScale's internal data model is shaped directly after that stack.

**Who regulates this, and what does compliance look like.** Cloud providers worry less about financial licensing and more about data security and privacy. **SOC 2** and **ISO 27001** are non-negotiable audits during enterprise procurement; serving California users brings **CCPA / CPRA**; serving Europe brings **GDPR**; serving Canadian customers brings **PIPEDA**; healthcare workloads require **HIPAA**, and payments require **PCI DSS**. These obligations are why NimbusScale has to operate data centers in multiple geographic regions, and they are why there is a `region` table in the schema.

**The macro winds right now.** Three forces are reshaping this market. First, **AI/ML inference demand is exploding**, and GPU capacity has become the new growth engine; whoever makes it easiest for customers to adopt AI captures the expansion hook. Second, **FinOps pressure**: customers are scrutinizing every dollar of cloud spend, and a drop in usage is often the leading edge of a budget cut and an eventual churn. Third, the **"efficient growth" era**: since 2022, capital markets stopped rewarding pure new-logo growth and started obsessing over **NRR (net revenue retention)**, which forces every SaaS company to take customer success seriously.

---

## 4. Project Background

You are the **data analyst / BI engineer** sitting inside NimbusScale's Customer Success Operations (CS Ops) team. You are effectively the team's first dedicated data hire, reporting directly to the Director of Customer Success and pulling ad-hoc numbers for Sales, Finance, and Product on the side. Your job is not to ship one fixed dashboard but to take the customer-success data scattered across Gainsight / Salesforce / Zendesk and assemble it into a clean analytics foundation that supports three concrete deliverables:

1. **Training corpus for a Text-to-SQL agent.** Business stakeholders ask questions in plain English (e.g., "Which Enterprise customers had their usage drop more than 20% last month?"), and the agent generates the right SQL. Every reference query needs a clear anchor: who asks it, when, and why.
2. **LLM Customer-360 agent.** Before a CSM jumps on a customer call or meeting, an AI assistant pulls the full picture for that account: subscription status, latest health score, recent interactions, open tasks, all on a single page.
3. **RAG renewal playbook.** When building a renewal strategy, retrieve historical customers with a similar industry, tier, and health-score trajectory as comparable cases.

These deliverables feed renewal decisions for the Director and VP of Customer Success, revenue forecasts for the CFO, and expansion plans for the sales org. The 20 reference SQL queries in the `03` document are the first batch of "worked examples" on top of this foundation, and each one ties back to one of the business questions described below.

---

## 5. The Business Questions This Dataset Answers

The dataset is built around five specific questions. Each one can be answered by one or a few of the SQL queries, and each one has a corresponding signal baked into the data distribution.

1. **Renewal risk: which customers are about to churn?** Find customers whose contract expires within 90 days and whose latest health score is below 60, so leadership can step in with an executive visit or a save plan. This is the dataset's headline question, addressed by Q3, Q12, Q17, and Q19.
2. **Drivers of health: are support tickets really negatively correlated with health?** If we can show that customers with more tickets have lower health, ticket volume can be folded into the health-score model. Addressed by Q14.
3. **Expansion opportunities: which customers are worth upselling?** Find customers with steadily growing usage, high health, broad service adoption, and positive recent interactions, then hand them to sales. Addressed by Q4 and Q15.
4. **CSM workload: is the team keeping up, and is the load balanced?** Look at each active CSM by tier specialization to see customer count, portfolio quality, and open task volume, then decide whether to hire or rebalance. Addressed by Q6, Q9, and Q16.
5. **Committed vs. actual spend: are we counting Enterprise revenue correctly?** Compare committed vs. actual spend for each Enterprise customer, see how big the overage is, and feed the result into finance's revenue recognition and the pricing review. Addressed by Q8.

The remaining queries (Q1 portfolio mix, Q2 usage drop, Q5 regional ranking, Q7 health volatility, Q10 interaction frequency, Q11 AI/ML adoption, Q13 industry distribution, Q18 sentiment trend, Q20 Customer 360) are the standard operational and leadership-reporting views that support those five core questions.

---

## 6. Data Scope at a Glance

The data is anchored to `REFERENCE_DATE = 2026-06-20` as "today," so every "last N days / N months" filter is computed relative to that date and the results stay reproducible.

The volume is a Medium dataset: roughly 150 customers, about 170 subscriptions, roughly 790 rows of monthly usage (covering the last 6 months), about 427 health-score snapshots (one per customer for each of the last 3 months), plus 300 CSM tasks and 400 interaction records, for a total of about 2,290 rows spread across 11 tables.

A few intentional scoping choices:

- **Usage covers only the last 6 months; health covers only the last 3 months.** Customer success works on a short analysis window anyway. Usage data from years ago is not useful for renewal decisions.
- **Currency is uniformly USD.** The company sits in North America with global customers, but contracts and invoices are all denominated in dollars.
- **Customer count is deliberately capped at around 150.** This is a teaching / demo dataset; small and clean works better than large and messy for Text-to-SQL and Customer 360 demos.
- **Customers created this month have no usage data yet.** Customers whose creation date falls within the last month are excluded from `usage_metrics` due to time-series constraints. That mirrors business reality: a freshly signed account simply has no usable history yet. Aggregations that inner-join through `usage_metrics` (Q5, Q13, Q14, Q15) naturally drop these new customers from their results.

Field-level details for each table, row counts, foreign keys, and the deliberately embedded distribution traps are all documented in the `02` ER document.

---

## 7. Industry Background Crash Course

This section is the half-hour primer an outsider needs before diving into customer-success data. Once you read it, the SQL queries stop being an exercise in syntax and start meaning something.

### Subscription Economics: ARR, NRR, GRR

The lifeblood of any subscription company is **recurring revenue**. **ARR (Annual Recurring Revenue)** is the annualized sum of every active subscription. At NimbusScale, it is approximately `monthly_committed_spend × 12`. The related terms are **MRR (Monthly Recurring Revenue)** and **ACV (Annual Contract Value)**.

Retention rates are the company's vital signs. **GRR (Gross Revenue Retention)** measures how much of last year's ARR is left a year later, before counting any expansion. Both churn and downgrades drag it down, and the ceiling is 100%. **NRR (Net Revenue Retention)** adds expansion back in on top of GRR. A healthy SaaS company has NRR above 100%, which means "even if we close no new business, we still grow on the back of existing customers." NimbusScale's entire customer success team has KPIs that ultimately roll up to NRR.

### How Health Scores Are Calculated

The **health score** is a 0-to-100 composite, where lower means higher churn risk. It is not a gut feel: it is a weighted blend of three sub-scores:

```
overall_score = round(0.4 × usage_score + 0.3 × engagement_score + 0.3 × support_score)
```

`usage_score` tracks usage trends, `engagement_score` tracks how often the customer interacts with the CSM, and `support_score` tracks the support experience. One key detail: **the sub-scores drive the overall score, not the other way around**. And `support_score` is explicitly dragged down by the customer's average ticket volume. More tickets means a worse support experience and a lower score. That causal chain is what makes business question 2 (tickets vs. health) provable from the data.

### CSM Service Models: High-Touch, Pooled, Tech-Touch

Not every customer gets their own dedicated CSM. **High-touch** is the Enterprise treatment: one CSM owns four or five accounts, runs the quarterly QBRs, and is personally accountable for renewal. **Pooled** is how mid-market customers like the Pro tier are served, where a group of CSMs share a book of accounts and lean on digital touchpoints. **Tech-touch** is the Basic tier model, where automation does the day-to-day and a human only steps in when a health alert fires. NimbusScale's 15 CSMs are split by **tier specialization** into Enterprise (4 people), Mid-Market (6 people), and SMB (5 people), and customers can only be assigned to an active CSM with the matching specialization.

### What a QBR Is

A **QBR (Quarterly Business Review)** is a formal quarterly meeting between the CSM and the customer's executives. It reviews usage, realigns on goals, and is the single most important relationship event leading into a renewal. Whether an Enterprise or Business customer has had a QBR in the last 90 days is a direct read on renewal readiness (this is what Q19 checks).

### Early Warning Signs of Churn

A CSM's job, day to day, is essentially a race against churn. The most reliable early signals are: **a sudden month-over-month drop in usage** (the leading edge of a FinOps-driven budget cut), **a persistent decline in health score**, **a spike in support tickets**, and **a contract that has slipped into `pending_renewal` status without any forward motion**. The churn-risk report in business question 1 (Q12) combines these signals into a single score.

### AI/ML Adoption Is the Expansion Hook

In today's market, whether a customer has actually started using NimbusScale's AI/ML inference services (`ai_ml_spend > 0`) is a strong signal of expansion potential. Customers who have adopted AI/ML tend to spend more overall, stick around longer, and are easier to upsell into additional services (this is what Q11 measures).

---

## 8. Glossary

Every term below shows up in either the ER document or the SQL queries. Terms are kept in English (that is how the industry talks), with a one-line plain explanation and why it matters in this dataset.

| Term | One-line explanation | Why it matters here |
|------|----------------------|---------------------|
| **CSM (Customer Success Manager)** | The person responsible for customer health, renewal, and expansion | `csm` table; customer is attached to a CSM via `customer.csm_id` |
| **Customer Success** | The function that helps customers get value post-sale, in order to retain and grow revenue | The business theme of the entire dataset |
| **Tier** | Account level (Enterprise / Business / Pro / Basic), based on customer size and spend | `account_tier` table; `customer.account_tier_id` |
| **Tier specialization** | The customer level a CSM is qualified to serve (Enterprise / Mid-Market / SMB) | `csm.tier_specialization`, drives customer assignment |
| **ACV (Annual Contract Value)** | The dollar value of a contract per year | Approximately `monthly_committed_spend × 12` |
| **ARR (Annual Recurring Revenue)** | Annualized sum across all active subscriptions | The ultimate scorecard for renewal and expansion |
| **MRR (Monthly Recurring Revenue)** | The monthly version of ARR | Sum of `subscription.monthly_committed_spend` |
| **NRR (Net Revenue Retention)** | Percentage of last year's ARR remaining after expansion. Above 100% is healthy | The customer success team's North Star metric |
| **GRR (Gross Revenue Retention)** | Last year's ARR retention before expansion, capped at 100% | Measures how bad churn is |
| **Churn** | Customer cancels their subscription early | `subscription.status = 'churned'` |
| **Health score** | 0 to 100 composite health metric, lower means higher risk | `health_score.overall_score` |
| **Health baseline (internal)** | The customer's implicit "health tendency," which drives both ticket counts and sub-scores | Not persisted, used only inside the generator |
| **QBR (Quarterly Business Review)** | Formal quarterly meeting between CSM and customer executives | `interaction_type.name = 'QBR Meeting'` |
| **CTA (Call To Action)** | An action item assigned to a CSM in Gainsight | Mapped to the `csm_task` table in this dataset |
| **Committed spend** | Contractually agreed monthly minimum spend | `subscription.monthly_committed_spend` |
| **Actual spend** | Real spend based on metered usage | `usage_metrics.total_spend` |
| **Overage** | Amount actual spend exceeds committed spend | `actual - committed > 0` |
| **Pending renewal** | Contract is near expiration and the renewal decision is still open | `subscription.status = 'pending_renewal'` |
| **Auto-renewal** | Whether the contract renews automatically at expiration | `subscription.auto_renewal` |
| **Expansion / Upsell** | Selling more into an existing customer to grow ARR | The goal of Q4 and Q15 |
| **Onboarding** | The process of getting a new customer up and running | `csm_task.task_type = 'onboarding'` |
| **AI/ML adoption** | Whether the customer is using AI/ML inference services | Latest month's `usage_metrics.ai_ml_spend > 0` |
| **FinOps** | Cloud cost governance, the discipline of spending cloud dollars carefully | Explains why a usage drop is an early churn signal |
| **PLG (Product-Led Growth)** | Growth driven by self-serve trials rather than sales reps | The acquisition motion for Basic tier |
| **Sentiment** | The emotional tag on a single interaction (positive / neutral / negative) | `interaction_log.sentiment` |
| **MoM growth (Month over Month)** | Growth rate of this month vs. last month | Computed with `LAG()` in Q2, Q4, and Q15 |
| **Region** | Cloud data-center region (AWS-style codes like us-east-1) | `region` table; `customer.primary_region_id` |
| **AE (Account Executive)** | The salesperson responsible for closing the deal | Drives the sales motion for each tier |
| **SA (Solutions Architect)** | A technical role that pairs with the AE on solution design | Part of the Enterprise sales motion |
| **Hyperscaler** | The giant cloud vendors, the scale tier NimbusScale deliberately avoids | Explains NimbusScale's market positioning |

---

## 9. Key Metrics and Formulas

The metrics below either appear directly in the SQL queries or are assumed knowledge for the reader. Each one is written in a plain-arithmetic form with a stated convention, so that different queries do not compute the same metric in subtly different ways.

**Composite health score.** A weighted blend of the sub-scores: usage gets 40%, engagement and support get 30% each:

```
overall_score = round(0.4 × usage_score + 0.3 × engagement_score + 0.3 × support_score)
```

**Inverse relationship between support score and ticket volume.** The support sub-score is dragged down by the average monthly ticket count (per the generator), and that is the source of the negative correlation in business question 2:

```
support_score ≈ 95 - 6 × avg_monthly_tickets + noise
monthly ticket expectation μ = 1 + 7 × (100 - health_baseline) / 55
```

**Overage and overage percentage.** Actual average spend minus committed spend; the denominator uses the sum of committed spend across all of the customer's active subscriptions, to avoid one-to-many fan-out:

```
overage     = avg_actual_spend - committed_spend
overage_pct = (avg_actual_spend / committed_spend - 1) × 100
```

**Month-over-Month (MoM) growth.** This month vs. last month; the first month returns NULL because there is no prior month to compare against:

```
mom_growth_pct = (this_month total_spend - last_month total_spend) / last_month total_spend × 100
```

**Revenue retention (conceptual).** These numbers are not stored directly in the data, but you need to know how they are calculated to understand the business:

```
GRR = (starting ARR - churned ARR - downgraded ARR) / starting ARR
NRR = (starting ARR - churned ARR - downgraded ARR + expansion ARR) / starting ARR
```

**AI/ML adoption rate.** Decided by whether each customer has any AI/ML spend in their latest month:

```
ai_ml_adoption = customers whose latest-month ai_ml_spend > 0 / total customers
```

**Interaction frequency (monthly average).** Interaction count over the last 90 days, normalized to a monthly figure:

```
monthly_avg_interactions = interaction_count × 30 / 90
```

**Renewal window and health thresholds (shared conventions).** These cutoffs are reused across multiple queries and are declared here for consistency:

- Renewal window: `contract_end_date BETWEEN REFERENCE_DATE AND REFERENCE_DATE + 90 days`
- Low health (needs intervention): `overall_score < 60`
- Expansion candidate health thresholds: `>= 65` qualifies, `>= 70` is Warm, `>= 80` is Hot
- Ticket buckets: `< 2` is low, `2 to 5` is medium, `5+` is high
