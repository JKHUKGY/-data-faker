# Cybersecurity — AI Compliance Audit System Business Context

> This document is the "starting point" for the `cybersecurity_ai_compliance_audit_medium` dataset. It first walks through the fictional company, its business model, its industry, the project, and the business questions to answer. Then it covers industry background, glossary, and metric formulas. Once you finish reading, you should be able to walk into your first stand-up and have a clear conversation about "what we're doing and why this data matters."
>
> For table schemas, fields, distributions, and DDL, see `02-cybersecurity_ai_compliance_audit_medium_er_document.md`;
> For runnable SQL queries, see `03-cybersecurity_ai_compliance_audit_medium_sql_queries.md`.

---

## 1. Company: Sentinel AI Governance

**Sentinel AI Governance** (referred to below as "Sentinel") is a fictional North American B2B SaaS company headquartered in Boston, MA — a traditional hub for cybersecurity and compliance software. The company was founded in 2021, right at the moment when NIST AI RMF was being drafted and enterprises were beginning to push AI/ML models into production at scale.

| Dimension | Setting |
|------|------|
| Headquarters | Boston, MA, USA |
| Founded | 2021 |
| Employees | ~150 (engineering, compliance research, customer success, sales) |
| Annual Recurring Revenue | ~$28M ARR (USD) |
| Customers | ~80 mid-to-large enterprise tenants |
| Currency | US Dollars (USD) |

Sentinel sells an **AI Compliance Audit and Governance Platform (AI Governance Platform)**. Its positioning is not to build yet another MLOps tool or SIEM, but to be the enterprise's internal "Compliance Single Source of Truth" for AI: it consolidates "model × control × evidence × remediation" information that was previously scattered across MLOps platforms, security ticketing systems, and Excel compliance checklists into a single data foundation. This way, when a customer's CISO does the quarterly board report, the Compliance Manager runs a framework audit, or the Risk Manager tracks remediation progress, all of them work from the same source of truth.

The roles referenced in this dataset's queries (all on the **customer** side) are: CISO / CTO (looking at high-risk exposure and unclosed CRITICAL incidents), Compliance Manager (looking at framework coverage and compliance rates), Risk Manager (looking at risk scores and single-point ownership). Sentinel's own sales and engineering teams do not appear in the data.

---

## 2. Business Model

Sentinel's revenue comes from **per-tenant annual subscriptions** — the standard B2B SaaS playbook:

- **How they charge**: Pricing tiers are based on the customer's "number of governed production AI models" + "number of enabled compliance frameworks". A mid-size customer that's just getting started and only governs a few dozen models is around $60K ARR; a large customer governing hundreds of models across 6 frameworks can hit $200K–$250K ARR.
- **Who pays**: Budget comes from the customer's CISO office or Chief Risk Officer (CRO) line, because AI compliance has graduated from "an engineering internal matter" into "board-level risk exposure".
- **Unit economics**: Pure software delivery, gross margin around 80% (standard SaaS range). New customer onboarding includes a one-time professional services fee (data ingestion and framework mapping), but the bulk of revenue is subscription ARR.
- **Renewal logic**: Regulation only gets tighter (see industry section below). Once a customer has their governance workflow running on Sentinel, it's hard to migrate away, so high net retention is the core of this business.

In one sentence: Sentinel doesn't produce compliance conclusions — it just "aggregates, preserves, and makes queryable" the compliance evidence, then charges a subscription based on governance scale.

---

## 3. Industry Overview: AI Governance / GRC Software

If you're coming from another industry, this section gives you the big-picture view of this market.

**What value does this industry create?** Once an enterprise puts AI/ML models into production, regulators and the board ask the same question: "How do you prove these models are safe, compliant, and under control?" AI Governance software exists to answer that question — it preserves a paper trail across the full chain of "risk identification → assessment → mitigation → governance", so the enterprise can produce evidence during audits, regulatory inquiries, and security incidents. This is an emerging sub-segment of the larger **GRC (Governance, Risk, Compliance) software** category.

**Main player categories (no real names mentioned):**

- **AI Governance / GRC platforms** (where Sentinel sits): aggregate evidence, maintain compliance records.
- **MLOps / model observability vendors**: handle model training, deployment, drift monitoring — Sentinel pulls data from them rather than replacing them.
- **Security / SIEM vendors**: handle security events and logs — Sentinel is also an aggregator here.
- **Large audit / consulting firms**: provide human-led compliance audit services, often as Sentinel's partners rather than competitors.
- **Internal Excel / Confluence checklists**: the "status quo" that Sentinel most often replaces.

**Relevant regulations and frameworks.** This is the key to understanding why this dataset exists — 2023–2026 is the boom period for AI compliance demand:

- **NIST AI RMF 1.0** (released January 2023) has become the de facto reference framework for governing AI risk in the US, requiring a full chain of "risk identification → assessment → mitigation → governance".
- **EU AI Act** (passed in 2024, phased rollout starting 2026) requires high-risk AI systems to retain technical documentation, risk assessments, and post-market monitoring records.
- **California SB 1047** (2024 proposal on frontier model safety) created internal "compliance-first" pressure for large US enterprises.
- **SR 11-7** (Federal Reserve and OCC's Model Risk Management guidance) originally covered only banking statistical models, but after LLMs entered credit and fraud-detection workflows, regulators have extended the interpretation to AI models.
- **GDPR Article 22** (right to explanation for automated decisions) + **HIPAA** (healthcare data protection) bring "how models process personal data" into audit scope.
- **SOC 2 Type II** (continuous operating effectiveness audit) imposes specific requirements on SaaS companies for AI model record-keeping.

**Macro forces shaping this market:** the explosion of AI adoption, the steady tightening of regulation in 2023–2026, and the shift in board-level attention to AI risk from "zero" to "must-see every quarter". The cumulative result: every mid-to-large enterprise needs a "central ledger" to answer "**which model, under which control, was assessed by whom, with what conclusion, and where is the evidence**".

---

## 4. Project Background: Your Role

**You are a data analyst on Sentinel's Customer Analytics team**, assigned to support one specific customer tenant. Your job is to use the data this customer has accumulated on the Sentinel platform to build the compliance dashboards, audit reports, and board metrics they use every day.

The personas you serve (on the customer side) map to roles in the data as follows:

| Persona | Corresponding `user.role` | Metrics they care about | Common queries |
|---------|-------------------|-----------|---------|
| **Executive / C-Level** (CISO / CTO) | (Implied by reporting hierarchy, not enumerated in the `user` table) | High-risk model share, unclosed CRITICAL incidents, overall compliance rate | Q1, Q17, Q20 |
| **Compliance Manager** | Compliance Auditor (managerial level) | Coverage Rate, Compliance Rate, Audit Coverage Gap | Q2, Q14, Q19 |
| **Risk Manager** | Risk Manager | Count of NOT_STARTED high-risk items, model owner concentration | Q3, Q11 |
| **Operations / Frontline** | MLOps Engineer, DevOps Engineer, Compliance Auditor (executor level) | High-priority backlog, days overdue, completion rate | Q5, Q8, Q9, Q13, Q18 |
| **Analyst / Investigator** | Security Analyst, Data Scientist, Product Manager | Monthly incident trend, type×severity matrix, action timeline | Q4, Q6, Q10, Q12, Q15, Q16 |
| **HR / Org** | Department managers (external interface) | Departmental activity rate | Q7 |

> **Note:** "Executive" is not an enumerated value in `user.role`; it's an implied senior role derived from reporting relationships, and is expressed in this dataset through queries rather than data modeling.

**What you're delivering.** Three types of artifacts: (1) compliance dashboards (for quarterly board reviews); (2) framework audit reports (for compliance audits); (3) operational weekly reports (for remediation tracking). These artifacts ultimately land in the hands of the customer's CISO, Compliance Manager, and Risk Manager. The 20 queries in the SQL queries document are the actual queries you'll write to deliver these artifacts.

---

## 5. Business Problems to Solve

The entire dataset and all 20 queries exist to answer the following 6 groups of specific questions. Each maps to specific queries (see the SQL document for details).

1. **How big is our high-risk model exposure?** How many CRITICAL/HIGH-risk models do we have? How many unmitigated (NOT_STARTED) risks in production? This is the first question the board asks. → Q1, Q17, Q20
2. **Where do we stand on framework compliance?** For controls in frameworks like NIST AI RMF, how much have we assessed (progress)? And what's the compliance rate within applicable scope (health)? Note that NOT_APPLICABLE should not enter the compliance-rate denominator. → Q2, Q14, Q19
3. **Where does the risk concentrate?** Which models have the highest risk_score? Which model owners are carrying too many high-risk models, creating a "single-point risk"? → Q3, Q6, Q11, Q12
4. **Is incident response keeping up?** What's the mean time to resolve (MTTR)? How are incident types and severities distributed? Is the monthly trend going up or down? → Q4, Q8, Q15
5. **How is remediation execution going?** What's the remediation completion rate? Which items are overdue? Is the workload balanced across assignees? → Q5, Q13, Q18
6. **Can we support compliance forensics?** What actions did a particular user take last month (any suspicious EXPORT/DELETE)? What's the overall distribution of action types? → Q10, Q16

Put these 6 groups together and you have the complete daily workflow of an enterprise AI governance team: watching exposure, tracking compliance, controlling risk, responding to incidents, chasing remediation, and preserving evidence.

---

## 6. Data Scope Overview

- **Modeled entity**: A snapshot of a **single customer tenant** on the Sentinel platform — corresponding to a mid-size enterprise (or a business unit of a larger enterprise) that's just getting started with AI governance, sitting at the lower end of Sentinel's customer profile.
- **Time range**: Roughly 18 months of historical activity + currently in-progress incidents and remediations.
- **Data volume (in plain terms)**: 11 tables, about 1,400 rows. 30 internal users, 50 governed AI models (about 12 in `production`), 100 controls across 6 frameworks, plus the assessments performed on these models, the incidents discovered, and the corresponding remediations.
- **Dynamic time anchor (important convention)**: This dataset **does not use a fixed REFERENCE_DATE constant**. Instead, at generator runtime, it uses `datetime.now()` as "today" and computes all dates as offsets back into the past. This is done so that queries using `julianday('now')`, `date('now')`, etc., retain their discriminative power when "run immediately after generation" — they won't lose meaning as time passes. The trade-off: each time you rerun the generator, the absolute dates shift uniformly, but the relative offsets to "today" stay the same. **So please run the SQL queries as soon as possible after generating the data.**
- **Deliberate scope trade-offs**: Only a single tenant is modeled, at Medium complexity. Some entities that real systems would have (a separate evidence/attachment table, training-data lineage, data subject/consent records, organizational hierarchy, M:N mapping of controls to multiple frameworks) have been intentionally simplified out. Details are in the "Known Simplifications" section of the ER document.

Detailed per-table row counts, field distributions, and precise distribution numbers are in the ER document — only the bird's-eye view is given here.

---

## 7. Industry Background Primer

This section gives outsiders the 30–60 minutes of background needed to understand the data.

### 7.1 The "Governance Lifecycle" of an AI Model

The key to understanding this dataset is understanding what a production AI model goes through:

```
register → risk assessment → control compliance assessment
   → deploy → continuous monitoring → incident → remediation
```

The 11 tables of the dataset cover exactly each step of this chain: `ai_model` (registration), `risk_assessment` (risk assessment), `model_control_assessment` (control compliance), `security_incident` (incidents), `remediation_action` (remediation), plus `audit_log` (the action audit trail that runs across everything).

### 7.2 How Risk Scores Are Calculated

The most common risk-quantification method in AI governance is "likelihood × impact × category weight". This dataset strictly uses:

```
risk_score = likelihood_score(1–5) × impact_score(1–5) × severity_weight(0.9–1.8)
```

`severity_weight` is determined by the risk category — for example, `ADVERSARIAL` (adversarial attacks) has the highest weight at 1.8, while `EXPLAINABILITY` (lack of explainability) has the lowest at 0.9. So for two assessments both with likelihood=4 and impact=5, the adversarial-attack risk_score (36) is significantly higher than the explainability one (18). The value range therefore spans from 0.9 (1×1×0.9) to 45 (5×5×1.8).

### 7.3 "Coverage Rate" vs. "Compliance Rate" Are Two Different Things

This is the most commonly confused pair of concepts in compliance auditing, and one the dataset is specifically designed to teach readers to distinguish:

- **Coverage Rate (Assessment Coverage Rate) = Assessed controls / Total controls.** It measures "are we done auditing?", a **progress** metric. Low coverage = not finished assessing.
- **Compliance Rate = COMPLIANT / Applicable assessments.** It measures "of what's been assessed, is it compliant?", a **health** metric. Low compliance rate = lots of problems found.

The two are completely independent: 90% coverage with 50% compliance means "we've assessed everything thoroughly, but half of what we assessed isn't compliant".

> **NOT_APPLICABLE trap (worth remembering):** Control assessments have a fourth conclusion, `NOT_APPLICABLE` (this control doesn't apply to this model). It **should not** enter the compliance-rate denominator — otherwise you're misclassifying "doesn't apply" as "non-compliant" and artificially depressing the compliance rate. This is the convention Q14 is specifically designed to demonstrate.

### 7.4 A Few Common-Sense Notes on Incident Response

- **severity** is one of CRITICAL / HIGH / MEDIUM / LOW, determining response priority.
- **status** follows the lifecycle OPEN → INVESTIGATING → CONTAINED → RESOLVED → CLOSED. "Unclosed incident" = status NOT IN (RESOLVED, CLOSED).
- **MTTR (Mean Time To Resolve)** is the key SLA metric, only meaningful for already-resolved incidents.

### 7.5 Deployment Environments and Risk Tiers

- **deployment_env**: `production` / `staging` / `development` / `canary`, **all lowercase**. Problems in production directly impact the business; executives care most about `production`. Note that SQL string comparison is case-sensitive.
- **risk_tier**: a model-level risk label of CRITICAL / HIGH / MEDIUM / LOW. It and risk_score are **two independent** things — risk_tier is a label on the model, risk_score is the numeric value of a single assessment.

---

## 8. Glossary

Terms that appear in the ER document and SQL queries are explained here in one place. English terms are kept in English, with a plain-language explanation in parentheses.

| Term | Plain explanation | Why it matters here |
|------|---------|----------------|
| **GRC** | Governance, Risk, Compliance software | The broader market Sentinel belongs to |
| **AI Governance** | The full set of processes that prove AI systems are safe, compliant, and controlled | The business this dataset simulates |
| **MLOps** | Engineering practices for managing ML model training/deployment/monitoring | Sentinel pulls data from MLOps, doesn't replace it |
| **SIEM** | Security Information and Event Management system | Upstream source of security incidents |
| **CISO** | Chief Information Security Officer | The typical "executive" persona in this dataset |
| **NIST AI RMF** | NIST AI Risk Management Framework (1.0, 2023) | One of the 6 frameworks in the data; the de facto standard |
| **GDPR** | EU General Data Protection Regulation | One of the frameworks; includes right to explanation for automated decisions |
| **HIPAA** | US Health Insurance Portability and Accountability Act, healthcare data protection | One of the frameworks; required for healthcare customers |
| **OWASP AI Top 10** | OWASP's list of the top 10 AI security vulnerabilities | One of the frameworks; focused on technical security |
| **ISO 27001** | International information security management standard | One of the frameworks |
| **SOC 2 Type II** | SaaS-oriented continuous operating effectiveness audit standard | One of the frameworks |
| **SR 11-7** | Federal Reserve/OCC Model Risk Management guidance | Banking customers extend it to AI models |
| **EU AI Act** | EU AI Act (passed 2024) | Macro regulation driving compliance demand |
| **Risk Tier** | Model-level risk label: CRITICAL/HIGH/MEDIUM/LOW | "High-risk model" is defined as risk_tier IN ('CRITICAL','HIGH') |
| **Risk Score** | `likelihood × impact × severity_weight`, the composite score of a single assessment (0.9–45) | Independent of risk_tier; numeric value at the assessment level |
| **Coverage Rate** | Assessed controls / Total controls | Progress metric, "is the audit done?" |
| **Compliance Rate** | COMPLIANT / Applicable assessments | Health metric, "is what was assessed compliant?" |
| **Applicable Assessment** | Assessment with `compliance_status != 'NOT_APPLICABLE'` | Only these count in the compliance-rate denominator |
| **NOT_APPLICABLE** | One of the assessment conclusions: "this control doesn't apply to this model" | Should not enter the compliance-rate denominator (Q14 trap) |
| **Stale Audit** | `last_audit_date` is NULL or older than 180 days | Core definition for Q19 |
| **Open Incident** | Incident with `status NOT IN ('RESOLVED','CLOSED')` | i.e., OPEN/INVESTIGATING/CONTAINED |
| **Open Remediation** | Remediation with `control_status.is_terminal = 0` | i.e., PENDING/IN_PROGRESS/DEFERRED |
| **Production Model** | `deployment_env = 'production'` AND `is_active = 1` | Note: production is all lowercase |
| **MTTR** | Mean Time To Resolve, in hours | Only meaningful for RESOLVED/CLOSED incidents |
| **Overdue** | `due_date < today` AND not completed (is_terminal=0) | Overdue remediation |
| **mitigation_status** | Risk assessment's mitigation status: NOT_STARTED/IN_PROGRESS/MITIGATED/ACCEPTED/TRANSFERRED | NOT_STARTED = not mitigated |
| **compliance_status** | Control assessment conclusion: COMPLIANT/PARTIALLY_COMPLIANT/NON_COMPLIANT/NOT_APPLICABLE | Basis for compliance-rate definitions |
| **MCA** | Shorthand for the `model_control_assessment` bridge table | The core action record for "model × control compliance" |
| **Polymorphic reference** | `audit_log.(entity_type, entity_id)` points to different tables, no schema-level FK | For forensics, you must pick the join target based on entity_type |
| **XOR mutual exclusion** | In `remediation_action`, exactly one of incident_id and risk_assessment_id is non-NULL | Each remediation has one and only one upstream trigger |
| **row-inflation** | The trap of getting multiplied rows when LEFT JOIN-ing a one-to-many downstream table and aggregating | Q11 fixes this with COUNT(DISTINCT CASE) |

> Acronyms are spelled out on first appearance; if you feel this table is short, that means there's a term not explained — but essentially all of this dataset's terms are captured here.

---

## 9. Key Metrics and Formulas

The table below lists the platform's core KPIs. Each one comes with a formula (using actual fields from the dataset), interpretation, and the corresponding SQL query number.

| KPI | Formula | Interpretation | Corresponding query |
|-----|------|------|---------|
| **Assessment Coverage Rate** | `COUNT(DISTINCT mca.control_id) / COUNT(DISTINCT cc.id)` | Share of controls assessed under a framework, measures "is the audit done?" | Q14 |
| **Compliance Rate** (applicable scope) | `SUM(status=COMPLIANT) / SUM(status != NOT_APPLICABLE)` | Compliance health within applicable scope. **Denominator excludes NOT_APPLICABLE** | Q14 |
| **Audit Coverage Gap** | `COUNT(active_models WHERE last_audit_date IS NULL OR julianday('now') - julianday(last_audit_date) > 180)` | Count of long-unaudited active models. Healthy value should be < 30% | Q19 |
| **MTTR** (Mean Time To Resolve) | `AVG((julianday(resolved_at) - julianday(reported_at)) * 24)` hours | Mean incident resolution time, key SLA | Q8 |
| **Remediation Completion Rate** | `SUM(status_id=3) / COUNT(*)` | Remediation completion rate, operational KPI | Q5 |
| **High-Risk Model Share** | `COUNT(risk_tier IN ('CRITICAL','HIGH')) / COUNT(*)` of active models | Share of high-risk models, board-level metric | Q1, Q17, Q20 |
| **Risk Score** | `likelihood_score × impact_score × severity_weight` | Composite risk score per assessment (0.9 ~ 45) | Q3, Q6, Q11, Q17 |
| **Overdue Remediation Count** | `COUNT(due_date < date('now') AND is_terminal=0)` | Count of overdue remediations, reported weekly to management | Q13, Q20 |
| **Open Incident Count** | `COUNT(status NOT IN ('RESOLVED','CLOSED'))` | Count of unclosed incidents | Q20 |
| **Owner Concentration Risk** | Count of `CRITICAL + HIGH` models under a single owner | Single-point risk on the model owner | Q11 |
| **Assignee Workload** | `COUNT(*) PER assigned_to_id` | Number of remediations per assignee, measures overload | Q18 |

> **Definition consistency reminder:** "High-risk model" is uniformly defined as `risk_tier IN ('CRITICAL','HIGH')` across all queries; "production" is uniformly `deployment_env = 'production'` (all lowercase); divide-by-zero protection uniformly uses `NULLIF(denominator, 0)`. These conventions run through all 20 queries to prevent the same metric from being computed in two different ways.

---

## 10. Typical Business Scenarios (User Stories)

The 5 scenarios below put the dataset back into real daily workflows, to help explain why the combination of 11 tables can support these scenarios:

**Scenario 1 · Monday morning stand-up (Ops Manager)** — "How many remediations are overdue this week? Who's carrying the most? What urgent items are in the high-priority bucket?"
→ Q13 (overdue list) + Q18 (assignee workload) + Q9 (open high-priority items)

**Scenario 2 · Quarterly board meeting (CISO briefing)** — "What's our high-risk model share? How many CRITICAL incidents are still open? Where's the compliance exposure for the next 6 months?"
→ Q20 (key metrics dashboard) + Q1 (high-risk overview) + Q17 (production risk summary)

**Scenario 3 · New framework rollout (Compliance Manager)** — "What's our assessment coverage on NIST AI RMF controls? What's the compliance rate? What's still unassessed?"
→ Q14 (coverage and compliance rates) + Q2 (framework control distribution) + Q19 (audit coverage check)

**Scenario 4 · Incident response (Security Analyst)** — "How many PROMPT_INJECTION incidents last month? What's the average time to resolve? What's the relationship between type and severity?"
→ Q4 (monthly trend) + Q8 (MTTR) + Q15 (type×severity cross)

**Scenario 5 · Compliance forensics (Compliance Auditor)** — "What actions did user ID=5 take last month? Any unauthorized EXPORT? What unmitigated high-risk assessments are out there?"
→ Q16 (user action trace) + Q10 (action type distribution) + Q3 (unmitigated high risk)

---

By the time you've read this far, you know who Sentinel is, how it makes money, why this industry matters, what role you play in the project, what business questions you need to answer, and how the key terms and metrics are defined. Next, open the ER document to learn **what the data looks like**, then use the SQL document to **actually answer these questions**.
