# CityPulse 311 Service Request Intelligence Platform Business Context

This document describes the business context for the dataset `govtech_saas_service_request_intelligence_large`. After reading it, you should be able to talk like a brand-new analyst on the CityPulse analytics team at your first stand up: know how the company makes money, who the customers are, what role our product plays inside a city government, what the five business questions you are about to answer actually mean, and what each piece of English jargon (311, SLA, FCR, NPS, ARR) is really referring to.

Data details (which tables exist, what each table is for, field types, sample rows) live in the same directory in `govtech_saas_service_request_intelligence_large_er_document.md`. SQL queries and analytical methods live in `govtech_saas_service_request_intelligence_large_sql_queries.md`. This document is only about the business and the industry, not the table schemas.

---

## 1. Company Introduction

CityPulse is a Govtech SaaS company headquartered in Austin, Texas, founded in 2014. Its main business is providing an end-to-end "311 service request" management platform to mid-sized cities and county governments across North America. "311" is the non-emergency municipal hotline that North American cities set up as a sibling number to 911 (emergency response): residents can use any channel - phone, mobile app, website, email, social media (city accounts on Twitter/X and Facebook) - to report things like potholes, missed trash pickup, broken streetlights, tree branches on power lines, stray animals, noise complaints - the kind of stuff that "does not need a cop or a fire truck, but does need the city to fix it." CityPulse sells the system that takes in, classifies, routes, dispatches, and tracks that entire ticket flow.

The company is currently sized roughly as follows: 252 full-time employees, around $50M ARR in FY2025 (matching the sum of `arr_usd` across the 120 active contracts in the dataset), 120 city and county customers (98 US cities, 8 US counties, 14 Canadian cities), and the platform handles roughly 10M resident service requests per year in actual production. Note: this dataset is a **sampled subset** of the platform's real traffic (about 1M requests across 36 months, or roughly 330K per year), not the full volume, so "10M per year" describes the platform's overall scale, and the order-of-magnitude gap to the dataset row count is expected. Customer size ranges from small towns of 50K residents (Burlington, VT) up to flagship large cities pushing 1M (Austin, TX, around 980K, also where CityPulse is headquartered; Winnipeg is around 750K) - but CityPulse does not serve mega-cities like New York City, Los Angeles, or Toronto, because those cities typically build their own systems or buy from Tier 1 vendors (Accenture, Tyler Technologies).

Organizationally, the CEO is Linda Park, with six lines underneath: Engineering, Product, Customer Success, Data, Go to Market, and Finance. The people directly relevant to your work: CDO Marcus Chen runs the Data group, which contains Data Science (NLP models, led by Director Priya Iyer), Analytics (your group, led by Director Tom Brennan), and Data Platform. VP of Customer Success Rachel Wong owns all tenant relationships, and her team is the ultimate consumer of many of the "customer health" questions in the SQL queries document. CRO Daniel Ortega runs sales and renewals, so any analysis related to churn risk or ARR retention eventually lands on his desk.

---

## 2. Business Model

CityPulse sells subscription SaaS. Each customer city signs a 12-month or 36-month contract, priced by "city population tier + modular add-ons." The base platform modules (intake, routing, SLA tracking, resident lookup portal) are mandatory; the AI Insight Pack (auto-classification model, sentiment analysis, duplicate request detection), Field Mobile Pack (phone-based app for field crews), and Analytics Pack (BI dashboards) are optional.

Contract ACV (Annual Contract Value) ranges roughly: small cities of 50K to 150K population fall between $120K and $250K; mid-sized cities of 150K to 400K fall between $250K and $600K; larger cities above 400K fall between $600K and $1.2M (the largest flagship cities like Austin, pushing 1M population, sit at the upper end of this band). With add-on modules, median ACV is around $320K, and each of the top 10 accounts has ACV above $800K. Gross margin runs between 72% and 78% (standard SaaS band), but within that, "AI Insight Pack has near-zero marginal cost and high renewal" has been the core growth engine for the company over the past three years, so leadership cares deeply about how that module is actually performing.

Revenue is recognized ratably over the subscription term. Customer contracts typically include a one-time implementation fee ($120K to $400K, depending on how complex it is to integrate with the customer's existing systems), which is recognized at implementation milestone and is not part of the ARR figure. Net Revenue Retention (NRR) is one of the company's North Star metrics; in FY2025 it was 112%, driven primarily by "customers sign the base pack first, then add the AI Insight Pack in year two." Gross Logo Retention is 94%, meaning about 7 customer cities churn per year (usually after a mayoral transition triggers a new RFP cycle, or because of a budget freeze).

Beyond subscription pricing, the platform has a category of hidden revenue: every year about 6 to 10 customers commission CityPulse's "Professional Services" team to build custom reports, billed hourly ($300/hour), which together total roughly $2M per year. This is not in ARR but contributes positively to cash flow.

---

## 3. Industry Overview

Govtech (government technology) refers to the segment that sells modern software methods into government. A few things to understand up front about Govtech versus enterprise SaaS:

First, customer decision cycles are long. Municipal procurement goes through an RFP (Request For Proposal) process; the average time from initiation to signature is 9 to 14 months. Internally the customer has to clear a budget committee, get a City Council vote, and sometimes hold a public comment period. That means CityPulse has long sales cycles, but once a customer signs, the cost of leaving is also high (data migration, re-educating residents, rewriting departmental workflows), so industry NRR is generally above 100% and churn is low.

Second, customers are highly homogeneous but also highly fragmented. Every North American city's municipal departments look broadly similar (Streets, Sanitation, Parks, Code Enforcement, Utilities), but every city has different names, different department splits, different SLA standards, and different code conventions. That is why CityPulse's core product features are a "configurable routing rule engine" and "tenant-isolated metadata."

Third, regulatory and transparency requirements are high. Many North American states and provinces require cities to publish 311 data openly. Boston, Chicago, and New York all have open data portals where 311 data is downloadable as csv/json. This is a double-edged sword for CityPulse: on one hand, customers must give residents a way to "look up the status of their own request" (CityPulse provides a citizen portal); on the other hand, open data makes it easy for competitors to benchmark. Relevant laws and compliance frameworks include FOIA (US federal, citizens have the right to request government records), state-level Open Records Acts (each state has its own version), Canadian FIPPA (Freedom of Information and Protection of Privacy Act, Ontario's version being the most well-known), and GDPR-like state laws when resident personal information is involved (CCPA in California, BIPA in Illinois, etc.). The CityPulse platform must comply with all of these natively, so "which fields are publicly visible, which are visible only to city staff, which must be deleted" is built as a tenant-level configuration.

Fourth, the current macro trends in the industry: (1) AI replacing manual classification. In the past, a 311 call center needed a dozen call takers to listen to a resident's description and manually pick a category and department; now every major vendor sells NLP auto-classification models, and CityPulse's AI Insight Pack plays in exactly this space. (2) Channel shift from voice to digital. Ten years ago, 70% of 311 requests came in by phone; today it's below 35%, and the share from mobile apps and social media grows about 15% per year. (3) M&A. Tyler Technologies, Granicus, and OpenGov - the Tier 1 vendors - collectively closed 11 Govtech acquisitions in the past three years, leaving mid-sized vendors (like CityPulse) to choose between being acquired or expanding into adjacent categories (permitting, procurement).

---

## 4. Project Background and Your Role

You are a Senior Data Analyst at CityPulse, reporting directly to Director of Analytics Tom Brennan. You've been with the company two years, and you have read-only access to data across every tenant on the platform (internally called the cross tenant view). Today is early June 2026, and the company is preparing the Q3 Quarterly Business Review (QBR). CEO Linda has handed CDO Marcus Chen a cross-quarter assignment: "Is the AI Insight Pack actually delivering the value we promised customers when we sold it?" That assignment has cascaded down and landed on you, becoming the analysis you'll be leading over the next few weeks.

The specific asks behind this analysis come from three different stakeholder angles. First, the CEO cares about the commercial question: if the AI Insight Pack's real impact is not a strong selling point, will it get cut at renewal time and hurt NRR? Second, the CDO cares about the model quality itself: what is our classifier's actual accuracy across different customer cities, which cities are performing badly, and why? Third, VP of Customer Success Rachel cares about customer operations: which customers are seeing SLA performance degrade, and what early-warning signals should we act on before it becomes a renewal problem?

The deeper pain point: the CityPulse platform contains a large amount of "unstructured text" signal (the request descriptions residents submit, the work order notes field crews write, the complaint narratives residents send when they escalate to council), but today nearly all operational metrics and model evaluations only use structured fields (auto category, stated_severity, channel, dept_id, sla_breach_flag). Marcus has long suspected that "there is a systematic gap between the structured fields and the text," but no one has ever quantified it systematically. This QBR is a legitimate opportunity to put concrete numbers behind that suspicion.

Your deliverables are three: an 8-page deck for Linda (executive conclusions plus business recommendations), a technical memo for Marcus and Priya (model quality diagnostics, including recommended directions for improvement), and an early-warning customer list for Rachel (top 20 tenants ranked by risk). The deck's deadline is July 18, 2026, six weeks from today.

The data you can pull from covers all tenants on the platform for the past 36 months, anchored to `REFERENCE_DATE = 2026-06-01`. All "today," "current," and "snapshot" SQL queries use this literal date - not `DATE('now')` - to guarantee reproducible results.

---

## 5. Business Questions

The five questions below are the core questions you will answer. Each one has a corresponding query in the SQL queries document that directly reveals it, and a corresponding "data trap" in the ER document that defines it as a contract at the generation layer.

Question 1: How many requests is the auto-classifier mis-routing into "Other," and how much damage does that misclassification do to SLA performance? CityPulse's auto-classifier currently dumps about 8% of requests into the `Other / Uncategorized` bucket, and by default the platform routes those into the customer city's "general inquiry queue," which has a 5 business day SLA (vs. 1-2 business days for department-specific queues). The suspicion: a meaningful share of that 8% actually contains strong keywords like pothole, streetlight, or graffiti in the text, and the model should have caught them. If true, those requests are being mis-routed onto the slow SLA track, which is exactly what gets thrown at CityPulse's AI Insight Pack in churn conversations.

Question 2: How much does the resident's stated severity (stated_severity) diverge from the true severity implied by the description text, and how serious are the downstream consequences for divergent requests? CityPulse asks residents to pick one of four at submission time: Low, Medium, High, Emergency. But many residents (especially those submitting through IVR or social media) write things like "gas leak," "live wire," "fire," "smoke," "child injured," or "leaking" in the description while still selecting only Medium or High. Those requests get sent to a normal-priority queue based on the structured field, the actual severity doesn't match, and they often end up reopened or escalated.

Question 3: Of the requests that look like they were "closed within 24 hours, on time," how many are fake closures - meaning the same address gets reported again within 30 days? Field crews have a KPI ("first touch resolution rate") that's tied to bonus, so they have an incentive to "close fast" after the first site visit, even if the problem isn't really fixed. If the same-address recurrence rate within 30 days is high, our "on-time resolution rate" overstates true performance.

Question 4: Which text features predict that a resident will eventually escalate to a city council complaint? City Council complaints (residents write to their council member, the council member forwards to the city, and the council member's office demands a root cause report from CityPulse's customer) are small in volume (around 0.4% of total request volume), but the political cost is enormous, and they're a key factor in whether the city council supports renewing CityPulse at contract time. We suspect that when residents write things like "third time this month," "fed up," "I will contact my councilman," "going to the news," or "lawyer" in the original description, the probability of subsequent escalation is materially higher than baseline. If true, we can give the customer city's Customer Success team a "complaint early-warning" feature.

Question 5: For the same global classification model, how much does actual accuracy vary across different customer cities, and what factors explain those differences? CityPulse's model is trained on aggregated data from all customers, but when deployed in different cities, local vocabulary (Quebec's French-English mixed usage, Deep South US slang, West Coast tech-industry jargon) all affect recognition quality. If certain cities have classifier accuracy materially below the median, their SLA performance will be dragged down too. Identifying that set of cities drives two things: (a) Customer Success proactively intervenes to avoid renewal risk; (b) the Data Science team fine-tunes or builds local vocabularies for those cities.

---

## 6. Data Scope

The dataset covers 36 months of platform operations, anchored at `REFERENCE_DATE = 2026-06-01`, so the time range is 2023-06-01 to 2026-06-01. All "today," "this month," and "last quarter" expressions in SQL are resolved as literal values based on this fixed anchor date - `DATE('now')` is not allowed.

Overall volumes (all order of magnitude, not exact): approximately 120 tenant cities, 500K registered resident accounts, 150K known addresses, 80K municipal assets (streetlights, fire hydrants, trash bins, intersection IDs, and other objects a request can reference), 25K municipal staff accounts, 1M service requests, 4M request lifecycle events (created/assigned/in_progress/closed/reopened), 600K work orders, 1M work order notes, 1M model prediction records, around 210K SLA breach records, around 5K city council complaint records, and 4K tenant monthly health snapshots. Total row count is around 10M, which lands solidly in the "millions and above" Large-complexity range.

Deliberate scope cuts: not included are (1) billing and contract finance data (Finance uses Salesforce and NetSuite, not on this platform), (2) the actual GPS tracks of field crews (privacy-sensitive, some customers prohibit collection), (3) GIS layers uploaded by customer cities themselves (large volume, not needed for this analysis). Geographic scope is North America (US + Canada), currency USD. Resident description text is primarily English; Quebec cities include some French/English mixed usage (used to trigger the tenant-level model accuracy variance trap in Question 5).

---

## 7. Industry Knowledge Primer

The next 30 to 60 minutes of reading is the "default industry knowledge" you need before doing this analysis. Both the code and the model rest on these conventions.

The 311 end-to-end flow has six stages, from resident to field work: (1) Intake: the resident submits through phone, website, mobile app, social media, email, or walk-in, and the system records the original description and metadata. (2) Classification: an auto model or a human call taker tags the request with a category (one of 66 fine-grained categories like pothole, streetlight, sanitation, noise complaint, plus a catch-all Other for a total of 67) and an initial priority. (3) Routing: the system uses the tenant's "category to department" mapping to route the request to the right department (Streets, Parks, Code Enforcement, Sanitation, Utilities, Animal Services, etc.). (4) Assignment: inside the department, the supervisor assigns to a specific crew or inspector and generates a work order (WO). (5) Field Work: the crew goes on site to handle it, writes work order notes on the mobile app (CityPulse Field Mobile Pack), and closes the work order. (6) Closure: the system or a human closes the service request and notifies the resident.

The specific meaning of SLA: each tenant city configures an SLA target (in business days) per category - for example, pothole is 2 business days, streetlight is 5 business days, illegal dumping is 3 business days. If the business-day gap from created_at to closed_at exceeds the SLA target, that counts as a breach. Note it's business days, skipping weekends and municipal holidays. The CityPulse platform stores each customer's holiday calendar in tenant configuration, so the definition of a business day on the same calendar date may differ between Austin and Toronto.

The state machine transitions for a request: created -> classified (has a category) -> assigned (assigned to a department) -> in_progress (field work in progress) -> closed (closed) is the main path. There are some branches: within 30 days after closed, the same request can be reopened (either proactively, or because the resident reports it again and the system links it), at which point it goes back to in_progress; after assigned, it can move to on_hold (field cannot proceed - waiting on weather, waiting on equipment), and from on_hold it can move back to in_progress or directly to closed. Every state transition leaves a row in the `request_events` table.

A few common resident behaviors: the same resident sometimes submits the same issue two or three times in one day (from different channels, or because they forgot they already submitted), and the system runs duplicate detection to mark the later ones as duplicate, but duplicate detection is not perfect. The cases duplicate detection misses become the "multiple requests at the same address" signal, which is the basis for Question 3 (fake closures).

How the NLP auto-classification model works: the CityPulse Data Science team maintains a text classification model (a fine-tuned BERT multi-class classifier). The input is the request description (description_text) plus some metadata (channel, asset_type), and the output is a softmax probability distribution over 67 classes. The top-1 class is taken as `predicted_category`, and if the top-1 probability falls below the 0.45 threshold, it falls back to Other. The prediction is written to the `model_predictions` table; however, the `auto_category` actually used in the request table may have been manually overridden by a call taker or supervisor, so `auto_category` does not necessarily equal `predicted_category`. When `auto_category` doesn't match the factual category (`ground_truth_category`, labeled after the fact by auditors on a subset), that's the definition of a misclassification.

---

## 8. Key Terminology

| Term | Plain-English Meaning | Relevance in This Dataset |
|------|----------------------|----------------------------|
| 311 | North American non-emergency municipal hotline, the sibling to 911 | The business core of the entire dataset |
| Tenant | A single customer city or county on the CityPulse platform | One row per tenant in the tenants table; cross-tenant analysis is your job |
| Service Request (SR) | One request record submitted by a resident; the platform's core entity | service_requests table |
| Work Order (WO) | The ticket dispatched to a field crew; one SR maps to 0 or 1 WO | work_orders table |
| SLA (Service Level Agreement) | "Must be closed within N business days" set per category per tenant | sla_policies table, sla_breach_log table |
| Breach | SLA overrun, i.e. actual business days to close exceeds the agreed target | sla_breach_log.is_breach |
| FCR (First Contact Resolution) | The first site visit resolves the issue, no second visit needed | The core metric for Question 3 |
| Reopen | A closed request gets reopened within 30 days | request_events with event_type = reopened |
| Repeat at Address | More than one request at the same address within 30 days; a true unresolved signal | Question 3, detected with window functions |
| Stated Severity | The severity the resident picked at submission (Low/Medium/High/Emergency) | service_requests.stated_severity |
| Text Implied Severity | True severity inferred from keywords in the description | The core conflict source for Question 2 |
| Channel | Submission channel (web, mobile_app, ivr, social, email, walk_in) | intake_channels table |
| Auto Category | The category written to the request record (model prediction or human override) | service_requests.auto_category |
| Predicted Category | The raw top-1 class output by the NLP model | model_predictions.predicted_category |
| Ground Truth Category | The true category labeled post-hoc by audit (covers a sampled subset only) | model_predictions.ground_truth_category |
| Model Confidence | The softmax probability of the NLP model's top-1 class | model_predictions.confidence_score |
| City Council Complaint | A resident bypasses 311 and complains directly to a council member, or the council member's office forwards a formal complaint | citizen_complaints table; the target variable for Question 4 |
| Tenant Health Snapshot | A monthly per-tenant operational health snapshot (SLA, NPS, renewal risk, etc.) | tenant_health_snapshots table |
| ARR | Annual Recurring Revenue | tenant_subscriptions.arr_usd; one of CityPulse's North Stars |
| NRR | Net Revenue Retention, including expansion | Derived metric from tenant_subscriptions |
| AI Insight Pack | CityPulse's AI module (auto-classification, sentiment analysis, duplicate detection) | tenant_subscriptions.has_ai_insight_pack |
| RFP | Request For Proposal, the procurement-process bid document for government | Industry context, not in this dataset |
| FOIA | Freedom of Information Act, the US federal public information disclosure law | Platform compliance constraint, not in tables |
| Code Enforcement | The city's "violations enforcement" department - handles building violations, illegal vending, tall grass, etc. | A dept_type value in the departments table |
| IVR | Interactive Voice Response, the phone voice menu system | A channel in intake_channels; the lowest-quality text |
| call taker | The human agent who picks up calls at the 311 center | The role that manually overrides auto_category; not a table |

---

## 9. Key Metrics and Formulas

The metrics below appear repeatedly in the SQL queries document. They have a single canonical definition here to keep downstream SQL from fighting itself.

SLA Breach Rate (by request): the share of requests closed within a period that were breaches.

```
SLA Breach Rate = COUNT(SR WHERE is_breach = 1 AND closed_in_period) / COUNT(SR WHERE closed_in_period)
```

How `is_breach` is computed: the number of "business days" between created_at and closed_at, minus the category's SLA target in days, greater than 0 means breach. To keep things simple in this dataset, "business day" is approximated as "calendar day skipping Saturday and Sunday," without subtracting public holidays (this is an intentional approximation; the real platform does subtract holidays).

Reopen Rate: the share of closed requests that get reopened within 30 days.

```
Reopen Rate = COUNT(SR WHERE reopened_within_30d) / COUNT(SR WHERE closed_in_period)
```

Repeat at Address Rate: among closed and SLA-met requests, the share where the same address gets a new request (different request_id) within 30 days. This is different from Reopen Rate: a reopen is the same SR being reopened; repeat at address is a brand new SR.

```
Repeat at Address Rate = COUNT(SR WHERE closed_in_period AND is_breach=0 AND new_SR_within_30d_same_address) 
                       / COUNT(SR WHERE closed_in_period AND is_breach=0)
```

Classifier Accuracy (tenant-level): the share of `model_predictions` rows where `predicted_category = ground_truth_category`, computed only on the subset where ground_truth is non-null.

```
Classifier Accuracy = COUNT(MP WHERE predicted_category = ground_truth_category) 
                    / COUNT(MP WHERE ground_truth_category IS NOT NULL)
```

Other Misroute Rate: among requests with `auto_category = 'Other'`, the share whose description text actually contains strong keywords (pothole, streetlight, graffiti, trash, noise, tree). This is the metric for Question 1.

```
Other Misroute Rate = COUNT(SR WHERE auto_category='Other' AND description matches keyword)
                    / COUNT(SR WHERE auto_category='Other')
```

Council Escalation Rate: the share of SRs created in a period that produce a citizen_complaints record within 60 days.

```
Council Escalation Rate = COUNT(SR WHERE has_complaint_within_60d) / COUNT(SR created_in_period)
```

ARR per Tenant: the current ARR per tenant, summed from `arr_usd` of currently active contracts in `tenant_subscriptions`.

```
ARR per Tenant = SUM(tenant_subscriptions.arr_usd WHERE is_active = 1)
```

NRR (Net Revenue Retention, monthly): the ARR change ratio for the subset of customers active both in the current month and 12 months ago.

```
NRR_t = SUM(ARR_t for tenants active at both t and t-12m) 
      / SUM(ARR_{t-12m} for same tenants)
```

NPS Proxy: the `nps_score` in tenant_health_snapshots monthly snapshots, range -100 to +100. This dataset has no actual NPS survey; we reverse-engineer a proxy score from a composite of "that month's SLA breach rate, council escalation rate, reopen rate for that tenant," computed by the generator and written into the snapshot table. Treat it as real NPS.

All metrics default to `REFERENCE_DATE = 2026-06-01` as the anchor. "Trailing 12 months" means 2025-06-01 to 2026-05-31; "current quarter" means 2026-04-01 to 2026-06-30; "prior quarter" means 2026-01-01 to 2026-03-31.
