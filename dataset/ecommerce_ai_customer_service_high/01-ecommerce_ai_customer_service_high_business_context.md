# Business Context — NestMart AI Customer Service Ticket Processing System

> **Dataset:** `ecommerce_ai_customer_service_high`
> **Complexity:** High (20 tables, ~25,700 rows)
> **Market:** North America (US / Canada, currency USD)
> **Reference date (fixed "today"):** `2024-12-01`
> **Companion documents:** Data structure in `02-ecommerce_ai_customer_service_high_er_document.md`; query examples in `03-ecommerce_ai_customer_service_high_sql_queries.md`; data generator in `04-ecommerce_ai_customer_service_high_data_generator.py`.

This document is the "onboarding manual" for the entire dataset. It first walks through the company, the industry, and the project, then layers on industry background, a glossary, and metric formulas, so that someone new to the project — who knows neither e-commerce customer service nor Prompt evaluation — can read it and be able to hold a real conversation with the team within a few hours. The three documents that follow (data structure, SQL queries, generator) all assume you have read this one.

---

## Table of Contents

1. [Company: Who is NestMart](#1-company-who-is-nestmart)
2. [Business Model: Where the Money Comes From](#2-business-model-where-the-money-comes-from)
3. [Industry Overview: E-commerce Customer Service and AI Agents](#3-industry-overview-e-commerce-customer-service-and-ai-agents)
4. [Project Background: What You Do at NestMart](#4-project-background-what-you-do-at-nestmart)
5. [Business Questions This Project Must Answer](#5-business-questions-this-project-must-answer)
6. [Data Scope Overview](#6-data-scope-overview)
7. [Industry Background Primer](#7-industry-background-primer)
8. [Glossary](#8-glossary)
9. [Key Metrics and Formulas](#9-key-metrics-and-formulas)

---

## 1. Company: Who is NestMart

**NestMart** is a fictional North American e-commerce platform headquartered in Austin, Texas, focused on mid-to-high-end home and living goods. It sells four main categories: bedding (sheet sets, down comforters, memory pillows), kitchen goods (cast iron cookware, knife sets, storage jars), home organization (storage bins, organizer racks, shoe racks), and lighting (desk lamps, floor lamps, mood lighting). You can think of it as a "mid-sized vertical e-commerce player specializing in home goods" — more focused than a general marketplace, broader than a single-brand store.

Scale, in rough orders of magnitude (not exact figures): annual GMV roughly $300M to $500M, several hundred thousand active buyers, a few hundred full-time employees. The company both stocks its own products (NestMart Original, about 70% of live SKUs) and lets third-party merchants list goods on the platform (about 30%). This "first-party + third-party" hybrid structure directly drives the core fork in customer service decisions (it will keep coming up): **refunds on first-party items are decided by the platform, while refunds on third-party items are decided by the merchant.**

The roles in the org that matter for this dataset:

- **VP of CX (VP of Customer Experience)**: The most senior leader of the support center, cares about SLA compliance, AI automation rate, and customer satisfaction.
- **VP of Engineering**: Tech leader for the AI customer service system, cares about accuracy, rule violation rate, token cost, and ROI on Prompt iteration.
- **Support / Operations Manager**: Watches the daily ticket queue, VIP prioritization, and timeout alerts.
- **Quality Manager**: Runs weekly QA, auditing whether AI decisions violated business rules.
- **Annotation Manager**: Manages the annotation team's throughput, consistency, and arbitration queue.

> NestMart is a fictional company with no relationship to any real business. The market is North America: currency is USD, customers are North American consumers, and the relevant regulators include the US FTC, state consumer protection laws, Canada's PIPEDA, and so on (see §3).

---

## 2. Business Model: Where the Money Comes From

NestMart's revenue stands on two legs:

1. **Retail margin on first-party goods.** The platform sources home goods itself, marks them up, and sells them to consumers, earning the gross margin between cost and retail price. Home-goods retail margins typically run 30% to 50%.
2. **Platform commission (take-rate) on third-party merchants.** Third-party merchants list their goods on NestMart, and the platform takes a percentage of GMV as commission, typically 8% to 15%.

In this business model, **support cost is a real and serious leak in profit.** Home-goods e-commerce has a modest average order value (most orders in this dataset are between \$25 and \$300), but returns, shipping disputes, and quality complaints are not rare. If every ticket had to be handled by a human agent (a single seat costs about \$150/day and averages about 8 minutes per ticket), the support center would quickly become a cost center.

That is exactly why NestMart launched its "AI-first, human-as-fallback" customer service overhaul in the second half of 2024: **let an AI customer service agent handle the bulk of routine tickets (refunds, shipping lookups, policy questions) in seconds, and escalate only the hard cases — high dollar amount, fraud suspicion, VIP complaints — to a human.** After going live, the AI auto-handle rate measured at about **85%**, with the remaining ~15% escalated. AI cost per ticket (token spend) is under \$0.01, while a human handles one for about \$4.69 — two orders of magnitude apart. That math is what many queries in this dataset are meant to make explicit.

Unit-economics cheat sheet: first-party gross margin 30%–50%, third-party take-rate 8%–15%, AI cost per ticket < \$0.01, human cost per ticket ≈ \$4.69 (estimated as \$150/day ÷ ~32 tickets/day).

---

## 3. Industry Overview: E-commerce Customer Service and AI Agents

If you come from another industry, this section gets you up to speed on the two overlapping fields NestMart sits in: **e-commerce retail** and **AI customer service (Conversational AI / AI Agent)**.

**What e-commerce as a business actually does.** An e-commerce platform matches buyers and sellers and earns retail margin or platform commission. The value it creates is "stitching products, logistics, payments, and after-sales into one smooth shopping experience." The major player types fall into three buckets (no real companies named): general marketplaces, vertical-category platforms (NestMart belongs here, specializing in home goods), and brand-owned direct-to-consumer sites. Home goods as a category has a moderate AOV, a return rate sensitive to "photo-vs-reality mismatch" and "shipping damage," and strong seasonality (Black Friday / Cyber Monday at year-end drive a surge in ticket volume).

**Why after-sales support is the pain point.** E-commerce post-purchase issues cluster into a few buckets: did-not-receive (shipping disputes), arrived damaged / wrong item, want to return / exchange, quality complaints, and policy questions. These tickets are high volume, highly repetitive, and time-sensitive (especially VIPs). The traditional fix is to throw more human seats at it — expensive and hard to staff overnight or at peak.

**What AI customer service is disrupting.** Since 2023, large language models (LLMs) have moved "have AI read the ticket and decide what to do" from concept to production-ready. A modern AI customer service stack breaks ticket processing into a multi-step pipeline (recognize intent → extract information → decide action → generate reply), with each step driven by an LLM prompt. The hard part isn't getting it to run, it's getting it to run accurately, run compliantly, and continuously prove that it really is improving — which is what brings in **Prompt engineering** and **model evaluation**, the two disciplines that form the spine of this dataset.

**Regulation and compliance (North America).** As a North American e-commerce player, NestMart operates under these frameworks:

- **FTC (Federal Trade Commission)**: Polices unfair / deceptive business practices, including refund promises, auto-renewal, and false advertising. When the AI auto-approves or denies refunds, those actions must line up with the publicly stated policy, or it could amount to a deceptive practice.
- **State consumer protection laws + CCPA/CPRA (California privacy law)**: Constrain how customer data is collected and used; customers have a right to deletion and access. Tickets contain personal information, so handling must be compliant.
- **Canada's PIPEDA + Competition Bureau**: Privacy and competition compliance for Canadian customers.
- **Emerging AI governance**: There is currently no hard-binding "AI customer service law" in North America, but the FTC has repeatedly stated that AI decisions must be explainable and non-discriminatory, and NIST AI RMF (Risk Management Framework) is the industry's self-regulatory benchmark. This is also why NestMart insists on persisting a `reasoning` / `rationale` trail for every AI decision and running rule-compliance audits.

**Macro forces at play right now**: first, AI is pushing customer service from "cost center" toward "automation + data asset"; second, consumer expectations on return convenience keep rising (no-questions-asked returns are now table stakes); third, platforms compete harder on after-sales experience.

---

## 4. Project Background: What You Do at NestMart

**This dataset captures everything that "Alex," a graduate student in data science, produced and touched during a 6-month internship in NestMart's Customer Experience (CX) department.**

Alex's internship is unusual: he straddles three roles single-handedly, which is why this one dataset contains business operations data, AI system output data, and AI evaluation data all at once.

| Role | What he did | Main deliverables |
|------|-------------|-------------------|
| **ML Engineer** | Analyzed the intent classifier's confusion matrix and identified the most-confused intent pairs | Confusion matrix analysis, per-intent accuracy report |
| **AI Engineer (Prompt Engineer)** | Iterated on LLM prompts (intent recognition + decision strategy), designed an LLM-as-Judge evaluation pipeline, ran A/B tests | Prompt version library, evaluation reports, A/B comparisons |
| **Data Analyst** | Built BI dashboards for support managers and execs (SLA, ticket trends, VIP priority, category complaints, risk alerts) | A tiered BI dashboard stack |

**Audience and timeline of the deliverables.** Alex's final delivery goes to the VP of CX and the VP of Engineering: a write-up that proves "the AI customer service system hits accuracy targets, has rule violations under control, and saves a lot of money compared to humans," plus a BI dashboard stack for ongoing monitoring. Key timeline of the internship:

| Date | Event | Data trace |
|------|-------|------------|
| Early Oct 2024 | Joined, assembled a 10-person annotation team | `annotator.joined_date` |
| Mid-Oct to early Nov 2024 | Wrote annotation SOP (v2), ran dual annotation on a stratified sample of ~500 tickets, established Ground Truth | `annotation_ground_truth` |
| 2024-11-01 | AI customer service v1 Prompt went live in production (Step1 + Step3) | `prompt_version` |
| All of Nov 2024 | AI handled ~5,000 real tickets, producing Step1 / Step3 outputs | `raw_ticket`, `step1/step3_*_output` |
| 2024-11-10 | First full evaluation: accuracy 81%, rule violation rate 12% | `evaluation_run` |
| 2024-11-12 to 11-28 | Continuous Prompt iteration (v2→v5) + CI/CD auto-evaluation, accuracy up to 90.5%, violation rate down to 3% | `evaluation_run`, `prompt_comparison` |
| End of Nov 2024 | BI dashboard demo for the VPs | All fact tables |

**What that BI dashboard stack looks like (the project deliverable).** Alex organized the dashboards into three tiers by "audience × frequency":

- **L3 Strategic tier** (audience: VPs, weekly): AI customer service weekly report, Prompt iteration journey (v1→v5 accuracy line chart, violation-rate downward curve, token cost trend).
- **L2 Operations tier** (audience: managers / QA / annotation lead, daily / hourly): daily ticket dashboard, channel quality monitoring, rule-violation heatmap, annotation team performance.
- **L1 Analysis tier** (audience: ML engineers / analysts, ad hoc): deep confusion-matrix analysis, high-risk user profiles.

The 20 queries in the follow-up `03-..._sql_queries.md` are the SQL behind this dashboard stack.

---

## 5. Business Questions This Project Must Answer

The entire project is built around the following **concrete questions**. Each one maps to SQL queries and reflects what a VP would actually ask.

- **Q1 — Is AI intent recognition accurate? Which two intents are most often confused?** When AI misclassifies a ticket, every downstream decision is wrong. We need to quantify overall accuracy, per-intent accuracy, and use a confusion matrix to identify the intent pair that "most needs fixing" (for example, "did-not-receive" being misclassified as "refund request"). *(Maps to queries Q2, Q3, Q19)*
- **Q2 — Are the AI's handling decisions compliant? Which business rule is violated most often, and how severe are the consequences?** When AI auto-approves refunds / hands off to merchants / escalates to humans, it must not violate the seven business rules R001–R007. The biggest fear is the AI unilaterally approving a refund on a third-party merchant's item (violates R002). We need to count violation frequency and severity by rule. *(Maps to queries Q4, Q13)*
- **Q3 — How much improvement does each Prompt iteration actually bring? Is the improvement real or noise, and is it worth shipping?** The team has gone through 5 Prompt versions, and we need to use A/B comparison to quantify the accuracy gain and violation-rate drop for each version, plus assess statistical significance to support the "ship-to-prod or not" call. *(Maps to queries Q2, Q12, Q20)*
- **Q4 — Are VIPs and high-value customers actually getting priority service? Are SLAs being met?** Gold / Platinum customers get a 24-hour SLA, regular customers get 48 hours. We need to monitor VIP ticket share, SLA compliance, and escalation rate. *(Maps to queries Q1, Q14, Q16)*
- **Q5 — Fraud risk for high-frequency refund users, and exactly how much money does AI save vs humans?** Users with ≥3 refunds in 30 days should trigger an alert (R004 anti-fraud); separately we need to quantify AI token cost vs human cost to prove the ROI on AI investment. *(Maps to queries Q6, Q7)*
- **Q6 (foundational) — Is the evaluation benchmark itself trustworthy?** All accuracy numbers sit on top of human-annotated Ground Truth. If the annotation is inconsistent, the evaluation is built on sand. We need to monitor dual-annotation agreement (Cohen's Kappa) and the arbitration queue. *(Maps to queries Q5, Q17)*

---

## 6. Data Scope Overview

- **Time anchor.** This dataset is **a static snapshot of November 2024**: ticket submission timestamps (`submitted_at`) all fall between 2024-11-01 and 11-30. Any calculation that needs "today" (waiting days, backlog age, last 7 days, etc.) uses the fixed reference date **`REFERENCE_DATE = 2024-12-01`**, not the real system date — so query results are reproducible. Upstream data (user registration, order placement) is older: user registrations span 2022-01 to 2024-09, and orders span 2024-09 to 10, preserving the temporal order "order before ticket, annotation after ticket, evaluation after annotation."
- **Volume in plain English.** A few hundred users in a loyalty program, a few hundred SKUs, two thousand orders, expanding out into **five thousand tickets**; each ticket produces one Step1 and one Step3 AI output; about 500 of those tickets are sampled for human annotation (dual annotation → ~1,000 rows), and then evaluated 6 times (each run ~500 tickets → ~3,000 evaluation detail rows each). 20 tables total, about **25,700 rows** in all.
- **Deliberate scope cuts (and why).**
  - The 4-step AI pipeline **persists only Step 1 (intent recognition) and Step 3 (decision strategy)**; Step 2 (information extraction) and Step 4 (reply generation) are treated as internal intermediates and not stored. This was a scope agreed between the intern and the Tech Lead, focused on the two highest-value questions: "is the classification right" and "is the decision compliant."
  - The **true intent of a ticket only covers 7 main intents** (did-not-receive, damaged, refund, exchange, quality complaint, shipping inquiry, policy question). The two other main intents in the taxonomy (wrong item received, service complaint) and 3 sub-intents **never appear as the true intent of a ticket**, but they do appear in the confusion matrix as "predicted values the AI / annotator got wrong" (i.e., they are "classes things get mistaken for," not "classes that real tickets actually belong to").
  - The 500-ticket evaluation sample is a **stratified random sample** of the 5,000 tickets, stratified by true intent so the proportions match the full set.
- **This is a working slice, not the company's full database.** The row counts above represent Alex's working dataset during the internship (one month, sampled annotation), and do not reflect the true scale of the NestMart platform (the real platform has buyers in the hundreds of thousands). When reading "expected results" of queries, use this dataset's order of magnitude as the reference.

Detailed data structure (20 tables, fields, foreign keys, distributions, DDL) is in `02-ecommerce_ai_customer_service_high_er_document.md`.

---

## 7. Industry Background Primer

This section is the "30-minute background" an outsider needs before reading this dataset. Four parts: the AI customer service pipeline, intent classification, model evaluation, and data annotation.

### 7.1 The 4-Step AI Customer Service Pipeline

Modern AI customer service is not "one giant model decides everything in one shot"; instead, the task is broken into a multi-step chain, with each step focused on one thing and each driven by its own Prompt:

```
Step 1 Intent Recognition → Step 2 Information Extraction → Step 3 Decision Strategy → Step 4 Reply Generation
  ★persisted                  (not persisted)                  ★persisted                  (not persisted)
```

- **Step 1 Intent Recognition**: Reads the ticket text and outputs main intent, sub-intent, sentiment, urgency. This is the entry point to the entire chain — get it wrong and everything downstream is wrong.
- **Step 3 Decision Strategy**: Takes the intent + user context (loyalty tier, refund history) + order context (amount, merchant type, shipping status), layers on the seven business rules R001–R007, and outputs the handling action (refund / exchange / reship / hand off to merchant / escalate to human) + reasoning + rule-check result.

The underlying model NestMart uses is **Claude 3.5 Sonnet** (invoked via AWS Bedrock), with `temperature = 0.0` to keep decisions reproducible.

### 7.2 Intent Classification and "Decision Rules"

Ticket intent is the foundation for everything that comes after. NestMart defines 12 intents (9 main + 3 sub). Recognizing the intent isn't enough — the AI still has to follow business rules to decide the action. NestMart's 7 decision rules (in priority order, lower number matches first):

| Rule | Name | Trigger condition | Expected action |
|------|------|-------------------|-----------------|
| **R001** | First-party 7-day no-questions-asked refund | First-party AND received ≤7 days ago AND refund request | Auto-approve refund |
| **R002** | Third-party merchant hand-off | Third-party merchant item | Hand off to merchant |
| **R003** | High-amount requires human review | Order amount > \$225 | Escalate to human |
| **R004** | High-frequency refund user escalation | ≥3 refunds in 30 days | Escalate to human (anti-fraud) |
| **R005** | Don't mark as lost while in transit | In-transit AND claims didn't receive | Hold decision, wait for shipping update |
| **R006** | VIP shipping dispute priority full refund | Gold / Platinum AND did-not-receive | Priority full refund |
| **R007** | Damage requires photo evidence | Damage complaint AND no attachment | Request evidence |

> The "7-day no-questions-asked return" (R001) is a **voluntary return policy** of NestMart's first-party goods, not legally required — there is no federal mandatory return-window law in North America, return windows are set by the merchant. NestMart uses this as a differentiator, which is also why it only applies to first-party goods; third-party items follow the merchant's own return policy (R002).

### 7.3 Model Evaluation: How to Prove the AI Really is Getting Better

This is the most "engineering-heavy" part of the dataset. Evaluating an AI customer service system has two complementary approaches:

1. **Reference-based evaluation (with ground truth)**: Compare AI output against human-annotated "Ground Truth" row by row, compute Accuracy, Precision, Recall. Answers "is the classification right."
2. **Reference-free / LLM-as-Judge evaluation (without ground truth)**: For things that don't have a single correct answer (e.g., "is the reasoning sound," "is the reply complete"), use a stronger LLM as the "judge" to score the output. Answers "how good is the quality."

NestMart runs an evaluation every time the Prompt is updated (some triggered manually, some triggered automatically by a code commit, i.e. CI/CD Evaluation), computing metrics on the same annotated sample set. Placing two versions side by side is an **A/B test**; assessing whether the improvement is sampling noise is the **statistical significance** check.

The **Confusion Matrix** is the core tool for iterating on Prompts: a "true intent × predicted intent" grid, where the diagonal is correct and off-diagonal is wrong. Watch the cells with the highest off-diagonal counts and you know "which two intents are most often confused," then target the Prompt to fix it. In this dataset, the most characteristic v1 Prompt error was misclassifying "did-not-receive" as "refund request" — because users describing a non-delivery often mention "refund" in the same breath. After v2 added an instruction to "read the entire message before classifying," that misclassification dropped sharply.

### 7.4 Data Annotation: The Foundation of Evaluation

All accuracy numbers rest on "ground truth," and ground truth comes from human annotation. NestMart's annotation workflow:

- From the 5,000 tickets, take a **stratified sample** of ~500, with each one **independently annotated by 2 annotators** (dual annotation), for cross-check.
- Whether the two annotators agree is measured by **agreement rate (IAA)** and **Cohen's Kappa** (Kappa adjusts out the "random guessing might accidentally agree" effect; ≥0.75 is good, ≥0.9 is excellent).
- Samples where the two disagree go to a senior **arbitrator** who makes the final call.
- Annotation SOP changes are versioned (everything in this dataset is v2).

The quality of annotation directly determines whether the evaluation is trustworthy — so even though it's the "foundation," it's something Alex has to monitor continuously.

---

## 8. Glossary

The glossary below is the new-hire dictionary. English terms stay in English (that's how the industry says them), followed by a plain-English explanation.

### 8.1 Customer Service Industry Terms

| Term (English) | Plain explanation | Why it matters in this dataset |
|----------------|-------------------|--------------------------------|
| **Ticket** | A single customer support request record | `raw_ticket` is the largest table and the starting point for almost all analyses |
| **Intent** | The core ask in a ticket, like "refund" or "did-not-receive" | Output of Step1, determines every downstream decision |
| **Sentiment** | The user's current mood: satisfied / neutral / frustrated / angry | Affects whether urgent handling is needed |
| **Urgency** | Ticket priority: low / medium / high; high must be handled within 1 hour | Determines queue priority |
| **SLA** (Service Level Agreement) | Time-to-resolution commitment: VIP 24 hours, regular 48 hours | SLA compliance is a core operations KPI |
| **CSAT** (Customer Satisfaction Score) | Customer satisfaction rating (1–5) | Not directly collected in this dataset, but can be inferred from sentiment + outcome |
| **AHT** (Average Handling Time) | Average time to handle one ticket | AI ~2 seconds vs human ~8 minutes — the key cost-savings comparison |
| **FCR** (First Contact Resolution) | Share of tickets fully resolved on first submission | Measures service efficiency |
| **Escalation** | When AI is uncertain or hits a "must-be-human" rule, hand off to a human agent | `escalate_to_human` field, ~15% |
| **First-Party vs Third-Party** | First-party refund authority sits with the platform; third-party sits with the merchant | The most critical fork in Step3 decisions (R002) |
| **7-Day Return Policy** | NestMart's voluntary return window on first-party goods | Trigger condition for rule R001 |

### 8.2 AI / LLM Engineering Terms

| Term (English) | Plain explanation | Why it matters in this dataset |
|----------------|-------------------|--------------------------------|
| **Prompt / System Prompt** | The instruction template written for the LLM | `prompt_version.prompt_content`, iterated by version |
| **Prompt Engineering** | Improving output quality by tweaking the Prompt (adding examples, tuning descriptions, adding constraints) | The change from v1→v2 is a textbook example |
| **Pipeline / Chain** | Breaking one task into a chain of multiple steps | NestMart's 4-step pipeline |
| **Token** | The smallest unit of LLM text processing (about 0.75 English words) | Base unit for billing and latency |
| **Latency** | Model inference latency (milliseconds) | `latency_ms`, AI performance metric |
| **Temperature** | Sampling temperature; 0.0 = deterministic, 1.0 = diverse | Customer service decisions use 0.0 to stay reproducible |
| **Few-shot** | Including a few examples in the Prompt to guide the model | v4 Prompt introduced few-shot |
| **RAG** (Retrieval-Augmented Generation) | Retrieve relevant context first, then generate the reply | Used in Step2, not persisted in this dataset |
| **LLM-as-Judge** | Use one (stronger) LLM to score another LLM's output | The `judge_*_score` family of fields |
| **Reference-based / Reference-free Evaluation** | Evaluation with / without a ground-truth answer | The two types are complementary (see §7.3) |
| **CI/CD Evaluation** | Evaluation pipeline triggered automatically by a Prompt change | `triggered_by = 'github_push'` |

### 8.3 Data Annotation and Model Evaluation Terms

| Term (English) | Plain explanation | Why it matters in this dataset |
|----------------|-------------------|--------------------------------|
| **Ground Truth** (GT) | The human-labeled "correct answer," the reference baseline for evaluation | `annotation_ground_truth` |
| **Dual Annotation** | Same ticket independently labeled by 2 people | Used for consistency checks |
| **IAA** (Inter-Annotator Agreement) | How consistently multiple annotators label the same batch | `annotation_agreement.is_agreement` |
| **Cohen's Kappa** (κ) | Two-annotator consistency statistic that excludes chance agreement | ≥0.75 good, ≥0.9 excellent |
| **Arbitration** | When two annotators disagree, a senior arbitrator decides | `role = 'arbitrator'` |
| **Accuracy / Precision / Recall / F1** | Accuracy / precision / recall / harmonic mean | Standard classification quality metrics |
| **Confusion Matrix** | An N×N table of true label × predicted label | The tool for finding the most-confused intent pair |
| **A/B Test** | Run two versions over the same sample set and see which is better | `prompt_comparison` |
| **Statistical Significance** | Whether the improvement is a real difference or sampling noise | `is_significant` field |
| **Baseline vs Experiment** | In a comparison, the old version is the baseline, the new one the experiment | v1 = baseline, v2 = experiment |
| **Rule Violation Rate** | Share of AI decisions that violate R001–R007 | `step3_rule_violation_rate` |

---

## 9. Key Metrics and Formulas

Below are the core metrics used in SQL queries — or that readers should know. Formulas are written in SQL-style pseudocode. Anything involving "today" uses the fixed reference date `'2024-12-01'`.

### 9.1 Customer Service Operations Metrics

| Metric | Formula (pseudo-SQL) | Notes |
|--------|----------------------|-------|
| **Daily Ticket Volume** | `COUNT(ticket_id) GROUP BY DATE(submitted_at)` | New tickets per day |
| **VIP Ticket Share** | `COUNT(*) WHERE tier IN ('vip_gold','vip_platinum') / COUNT(*)` | VIP ticket share, target 15%–25% |
| **SLA Compliance Rate** | `Determined by "handling time": (step3.processed_at − submitted_at) ≤ SLA threshold`; VIP 24h, regular 48h | **Based on handling time, not ticket age.** AI handles in seconds, so the AI portion is close to 100% |
| **Avg Handling Time (AHT)** | `AVG(step3.processed_at − raw_ticket.submitted_at)` | Average handling time |
| **Escalation Rate** | `SUM(escalate_to_human) / COUNT(*)` | Escalation rate, ~15% |
| **Category Complaint Rate** | `COUNT(ticket) / COUNT(order) GROUP BY category` | Complaint rate per category |
| **High-Risk User Count** | `COUNT(*) WHERE refund_count_30days >= 3` | Count of users triggering R004 high-frequency refund |

### 9.2 AI System Performance and Cost Metrics

| Metric | Formula | Notes |
|--------|---------|-------|
| **Avg Latency** | `AVG(latency_ms)` | Step1 / Step3 average latency |
| **Token Cost per Ticket** | `(output_tokens / 1000) × $0.015` | Claude 3.5 Sonnet output price ≈ \$0.015 / 1K tokens |
| **AI Auto-Handle Rate** | `1 − SUM(escalate_to_human) / COUNT(*)` | Target >75%, measured ~85% |
| **AI vs Human Cost Comparison** | AI per ticket ≈ \$0.005–0.01; human per ticket ≈ `$150 daily / daily volume` ≈ \$4.69 | Proves AI ROI |

### 9.3 AI Quality Evaluation Metrics

| Metric | Formula | Notes |
|--------|---------|-------|
| **Step1 Accuracy** | `SUM(is_correct) / COUNT(*)` | Overall intent recognition accuracy |
| **Per-Intent Accuracy** | `SUM(is_correct) / COUNT(*) GROUP BY true_intent` | Per-intent accuracy, find the weak intents |
| **Step3 Rule Violation Rate** | `SUM(NOT rule_check_passed) / COUNT(*)` | Rule violation rate, v1 = 12% → v5 = 3% |
| **LLM Judge Avg Score** | `AVG(judge_reasoning_score)` or `AVG(judge_overall_quality)` | Judge average score (1–5) |
| **Confusion Top-N Pairs** | `WHERE true_label != predicted_label ORDER BY count DESC LIMIT N` | Most-confused intent pairs |
| **A/B Improvement Pct** | `(experiment_value − baseline_value) / baseline_value × 100` | A/B improvement percentage |

### 9.4 Annotation Quality Metrics

| Metric | Formula | Notes |
|--------|---------|-------|
| **IAA Rate** | `SUM(is_agreement) / COUNT(*)` | Dual-annotation agreement rate, ~95% |
| **Cohen's Kappa (per annotator)** | `annotator.agreement_rate` | Per-annotator agreement, ≥0.75 is good |
| **Avg Annotator Confidence** | `AVG(annotator_confidence)` | Average annotation confidence (1–3) |
| **Pending Arbitration Count** | `COUNT(*) WHERE resolution_status = 'pending'` | Backlog of cases awaiting arbitration |

---

> After reading this business context, you should be able to answer: how NestMart makes money, why they're investing in AI customer service, how AI customer service is evaluated, and what you (Alex) need to deliver. Next, please read `02-ecommerce_ai_customer_service_high_er_document.md` to see what the data looks like.
