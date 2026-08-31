# Business Context: MaterniFlow OB Ward Scheduling POC

> **Dataset:** `healthcare_obstetrics_ward_scheduling_medium`
> **Complexity:** Medium (11 tables, ~500 rows)
> **Market:** North America (United States, USD)
> **Reference date (REFERENCE_DATE):** `2026-02-13 08:00` (Demo anchor)
> **Role of this document:** This is the "why" of the dataset — the company, the industry, the project, the business problem, industry primer, glossary, and metric formulas all live here. Table structures and field definitions live in `02-..._er_document.md`; queries live in `03-..._sql_queries.md`.

---

## Table of Contents

1. [One-line Overview](#1-one-line-overview)
2. [Beat 1 Company Profile](#2-beat-1-company-profile)
3. [Beat 2 Business Model](#3-beat-2-business-model)
4. [Beat 3 Industry Primer](#4-beat-3-industry-primer)
5. [Beat 4 Project Framing](#5-beat-4-project-framing)
6. [Beat 5 Business Problems to Solve](#6-beat-5-business-problems-to-solve)
7. [Beat 6 Data Scope Overview](#7-beat-6-data-scope-overview)
8. [Beat 7 Industry Knowledge Primer](#8-beat-7-industry-knowledge-primer)
9. [Beat 8 Glossary](#9-beat-8-glossary)
10. [Beat 9 Key Metrics & Formulas](#10-beat-9-key-metrics--formulas)

---

## 1. One-line Overview

**Halcyon Health Analytics** is a mid-size healthcare data consultancy headquartered in Austin, Texas, that specializes in "narrow-scope, tangible" AI deployments for hospitals. It is currently delivering a Proof-of-Concept (POC) called **MaterniFlow** — an **AI-assisted obstetrics ward scheduling assistant** — to **Cedar Ridge Women's Health**, a regional OB/GYN hospital chain serving the Pacific Northwest (Portland, Oregon metro area).

You are the **founding data hire** Halcyon embedded on this POC: you design the data model, generate the sandbox data, and write the SQL toolkit the AI agent calls behind the scenes. You report directly to the engagement lead. Every artifact you ship is aimed at the **demo day** moment when a Cedar Ridge front-line nurse can look at the screen and say, "This AI actually understands what's happening on the ward." This dataset is the **sandbox** for that POC.

> Tone reminder: this document is written in English, but the company, client, cities, currency, and regulators are all **North American**. Clinical jargon (LOS, EDD, VBAC, NICU, etc.) is kept in its original English form and explained in plain language in the [Glossary](#9-beat-8-glossary).

---

## 2. Beat 1 Company Profile

### 2.1 The Vendor — Your Company, Halcyon Health Analytics

| Dimension | Setting |
|------|------|
| Company name | **Halcyon Health Analytics** (fictional, not any real company) |
| Headquarters | Austin, Texas, USA |
| Company type | Healthcare data + AI solution consulting |
| Size | ~70 employees (data engineers, clinical informatics consultants, AI engineers, delivery managers) |
| Annual revenue | ~$15M range (mostly consulting fees + follow-on implementation contracts) |
| Customer base | North American small-to-mid hospitals and regional health systems (those not yet on top-tier Epic/Cerner-class platforms, or who want a lightweight augmentation on top of one) |
| Positioning in one line | "Use a low-cost, low-risk small POC to prove AI capability, then win the larger implementation contract." |

Halcyon doesn't sell a giant HIS (Hospital Information System) and doesn't replace the hospital's existing EMR (Electronic Medical Record). Its playbook: find one **mundane, high-frequency, error-prone** pain point at a hospital, prove with a bounded demo that "AI can hit high enough accuracy within this boundary," and then convert that trust into a larger contract.

### 2.2 The Client — Cedar Ridge Women's Health

| Dimension | Setting |
|------|------|
| Client name | **Cedar Ridge Women's Health** (fictional) |
| Type | Regional **OB/GYN hospital chain** (Maternity & OB/GYN) |
| Location | Portland, Oregon metro area, serving the Pacific Northwest |
| Size | 6 hospitals, several thousand beds combined, tens of thousands of births per year |
| Role in the project | Sets the problem, provides the budget, evaluates accuracy. The POC's executive decision-makers are the VP of Nursing and the CMIO (Chief Medical Information Officer). |

This POC builds a sandbox for **just one OB ward at one Cedar Ridge hospital**. What the client wants to verify is not "Can AI handle massive data volumes?" but "Can AI hit high enough accuracy within a bounded scope?" Only after the POC clears the accuracy threshold does the project move to the next stage: connecting to the real EMR and rolling out to all six hospitals.

### 2.3 Who Shows Up in the Queries (Cast of Roles)

The SQL queries downstream will call out specific **job titles**. They all come from real ward and project roles at the two companies above:

- **Charge Nurse**: the front-line ward commander — runs handoff, hunts for open beds, dispatches work.
- **Attending Physician**: leads rounds, sets clinical direction, watches over high-risk patients.
- **Nurse Manager / Department Manager**: owns scheduling and staffing load.
- **OR Coordinator**: schedules C-sections and inductions, rooms and times.
- **Quality Analyst**: validates AI prediction accuracy (the person defending LOS accuracy at the POC review).
- **MFM Specialist** (Maternal-Fetal Medicine Specialist): owns the highest-risk patients (multiples, preterm).
- **CMIO / VP of Nursing**: client-side executives — final sign-off on POC acceptance.

---

## 3. Beat 2 Business Model

How Halcyon makes money, in one line: **Sell consulting delivery, use a small POC to hook a large contract, eventually land in per-bed / per-hospital software subscription.**

| Revenue stage | Form | Typical magnitude (USD) | Notes |
|---------|------|--------------|------|
| 1. POC stage (this dataset) | Fixed-price consulting fee | $80K – $150K | One-shot, low-risk. Deliverables: sandbox + demo + acceptance report. This is the current project. |
| 2. Implementation stage | Project-based implementation contract | $0.5M – $2M | After POC passes: connect to real EMR (HL7/FHIR), roll out across multiple hospitals. |
| 3. Operations stage | SaaS subscription (per bed / per hospital) | $X per bed per month, recurring revenue | Long-term license + maintenance after model goes live. |

**The unit economics**: the POC itself is barely profitable (fixed price, people-heavy) — it's **part of customer acquisition cost (CAC)**. Halcyon's real profit comes from stages 2 and 3. Once Cedar Ridge trusts MaterniFlow and rolls it out across all six hospitals' OB wards, that's where the high-margin recurring revenue lives. So the demo-day question — "Did the AI answer accurately?" — directly determines whether a multi-million-dollar follow-on contract gets signed. That's why **every plant in this dataset is engineered to be SQL-verifiable** — there is no tolerance for the AI miscounting a single patient in front of the nurses on demo day.

**Why customers buy**: the pain point of OB ward scheduling is "lots of little things, happening constantly, easy to forget when tracked in someone's head." Legacy CMS-like (content-management) systems only display raw data — they don't do the aggregation + threshold logic that answers "How many clean labor beds are open right now?" MaterniFlow sells the time-saving value of "freeing the nurse from repeated lookups."

---

## 4. Beat 3 Industry Primer

### 4.1 What This Industry Does

US hospital IT is a **trillion-dollar** market, but extremely fragmented. Large hospitals are mostly locked into two or three giant EMR platforms (no names here). Small-to-mid hospitals and regional chains still have a long tail of "last-mile" lightweight needs that sit outside those platforms — ward scheduling, bed management, shift handoff summaries, staffing coverage — and these day-to-day operational tasks are often still run on Excel, whiteboards, or barebones in-house apps. Consultancies like Halcyon eat in that gap: "too small for the giants to bother with, but hurts the hospital every day."

Obstetrics (OB) is a particularly good fit for a POC because:

- **Standardized workflow**: a mother's journey from admission → labor → delivery → postpartum → discharge is a bounded, well-defined state machine — easy to model.
- **Fast tempo, low tolerance for error**: missing a high-risk patient can mean a sentinel event, so the value of "seeing the ward clearly" is immediately quantifiable.
- **Hard resource constraints**: labor rooms, delivery rooms (OR), anesthesiologists, NICU beds are all scarce — scheduling conflicts happen daily.

### 4.2 Major Player Categories (no real names)

| Category | Role |
|------|------|
| Large EMR / EHR platforms | The hospital's "OS" — owns the chart, orders, billing. Comprehensive but heavy and expensive to customize. |
| Bed / patient-flow software vendors | Mid-size vendors focused on bed management and patient flow. |
| Healthcare data / AI consultancies | This is Halcyon — lightweight, deployable augmentations. |
| Hospital in-house IT | Large hospitals have one; small-to-mid chains usually don't, which is why they outsource to Halcyon. |

### 4.3 Regulation & Compliance (North America)

Healthcare data is heavily regulated; even a POC like MaterniFlow can't ignore it:

- **HIPAA** (Health Insurance Portability and Accountability Act): the bedrock US law for patient privacy and data security. The POC uses **synthetic / fake data** (this dataset) precisely so the team can validate capability without touching real PHI (Protected Health Information).
- **HITECH**: HIPAA's digital-era reinforcement, covering electronic health information security.
- **The Joint Commission (TJC)**: the hospital accreditation body; has explicit standards for obstetric safety and hand-off communication — which is the compliance backdrop for demo scenario 1 (handoff).
- **CMS** (Centers for Medicare & Medicaid Services): runs Medicare/Medicaid reimbursement and quality reporting; indirectly determines payer mix (see Glossary).
- **FDA SaMD** (Software as a Medical Device): once AI enters **clinical decision-making** (prescribing, diagnosing), it can be regulated as a medical device. **MaterniFlow deliberately confines its scope to "read-only + visibility + simple alerts"; it does not diagnose or prescribe**, which keeps it outside SaMD's high regulatory cost.
- If the chain ever expands to Canadian hospitals, the corresponding regulators are **Health Canada** and provincial privacy laws (e.g., PIPEDA).

### 4.4 Macro Trends Right Now

- **Nursing shortage**: North American nursing capacity is chronically tight, so any tool that "frees nurses from repetitive lookups" has hard demand.
- **AI entering the ward**: generative AI makes "nurse asks in natural language → AI calls SQL tools to answer" feasible — and that's MaterniFlow's technical bet.
- **Interoperability standards (HL7 / FHIR)**: mature EMR data-exchange standards mean third parties like Halcyon will eventually be able to plug in legally to real data.
- **Value-based care**: reimbursement is increasingly tied to quality and efficiency, which pushes hospitals to pay for tools that "shorten LOS and reduce scheduling conflicts."

---

## 5. Beat 4 Project Framing

### 5.1 Your Role

You are Halcyon's **founding data hire**, deployed onto the MaterniFlow POC. You have three deliverables:

1. **Data sandbox**: a ~500-row SQLite database + TSVs that simulates the current state of a real OB ward.
2. **Query toolkit**: 20 business-problem-oriented SQL queries that serve as the AI agent's "tool calls."
3. **Acceptance materials**: artifacts that let the client's IT team audit, after the demo, that "every AI answer can be reconciled to real data in the schema."

You report directly to the **engagement lead**. The demo-day audience is Cedar Ridge's **Charge Nurse, Nurse Manager, and CMIO**.

### 5.2 This Is a POC, Not a Production System

**MaterniFlow** is a Proof of Concept; it is **not** a production system in operation, and it is **not** a full hospital HIS. It answers exactly one question:

> *"In a bounded data volume and bounded scenario, can AI handle a CMS-style ward-scheduling task with high enough accuracy?"*

That's why the dataset is intentionally kept at ~500 rows: the client wants to validate "Can AI hit **high enough accuracy** within a **bounded scope**?" — not "Can AI handle massive volumes?" The intentional benefits at this size: accuracy is interpretable (500 rows can be hand-audited end-to-end), demos run instantly (single-file SQLite), and the focus stays on business logic, not data engineering.

### 5.3 POC → Larger-Project Evolution Path (future scope, not in this dataset)

| Expansion direction | Additional data involved |
|---------|--------------|
| Real EMR integration | HL7 / FHIR interfaces, ICD-10 codes, medication records |
| Multi-hospital aggregation | hospital table, network-level dashboard, inter-hospital transfers |
| Newborn data | newborn table, Apgar scores, detailed NICU monitoring |
| Billing & insurance | encounter, charge, payer authorization |
| Quality reporting | core measures, CMS reports, SCIP indicators |
| Clinical decision support | medication suggestions, automated CTG interpretation, auto-plotted partograms |

The POC's scope in one line: **Read-only + ward view + simple alerts. No writes, no diagnoses, no prescriptions.**

---

## 6. Beat 5 Business Problems to Solve

The POC validates 5 core scenarios — all things a Cedar Ridge front-line nurse needs to answer every day, but which are mundane and error-prone. Each scenario maps to several queries in `03-..._sql_queries.md`.

| # | Scenario | Business problem (in nurse-speak) | What this question really tests | Corresponding queries |
|---|------|---------------------|--------------|---------|
| **P1** | **Shift Handover** | "I'm coming on shift now — how many patients are on the ward, and what stage is each one in?" | Does the AI **count and categorize status** correctly? | Q1, Q5, Q6, Q14 |
| **P2** | **Room Availability** | "Are there any open beds in the labor room right now? Which ones are actually clean?" | Can the AI correctly distinguish all **4 bed statuses** (not just a binary occupied/free)? | Q2, Q10, Q18 |
| **P3** | **LOS Prediction** | "When is this patient likely to discharge? When does her bed free up?" | Does the AI's postpartum LOS prediction **respect clinical patterns** (vaginal short, C-section longer)? | Q9, Q13, Q17 |
| **P4** | **High-Risk Alert** | "Is anyone on the ward trending up on blood pressure right now? Do I need to page the doctor?" | Can the AI detect a **trend** in hypertension (not just a single threshold crossing)? | Q3, Q7, Q16 |
| **P5** | **Order Scheduling** | "That 9 AM C-section tomorrow — which OR is it in? Is the anesthesiologist lined up?" | Can the AI detect **resource conflicts** (room / anesthesiologist double-booking)? | Q4, Q14, Q19 |

Note all 5 are **CMS-like tasks**: query + simple calculation + threshold alerting. They explicitly do **not** include clinical decisions, order generation, or medication recommendation — those are high-risk actions. This is the client's explicit boundary for the POC: verify "AI helps humans **see clearly**," not "AI helps humans **decide**."

To make all 5 questions SQL-verifiable in only ~500 rows, the data generator **deterministically** plants several "plot points" (see the business-trap declarations in the ER document). Examples: two high-risk patients with BP trending `125 → 131 → 137 → 143`, crossing the 140 threshold (P4); one C-section scheduled for 09:00 tomorrow (P5); one labor-room bed in cleaning status (P2). These plants are what allow the queries to produce the expected results.

---

## 7. Beat 6 Data Scope Overview

| Dimension | Setting | Reason |
|------|------|------|
| Time anchor | `REFERENCE_DATE = 2026-02-13 08:00` (Demo anchor, Friday 8 AM) | Every "now / today" is anchored to it; runs are reproducible |
| Time span | Demo day + 3 days back (history) + 1 day forward (tomorrow's scheduled orders) | Enough to show "just happened" and "about to happen" |
| Physical scope | **1** OB ward, ~20 rooms, ~32 beds | Single-ward sandbox; focus on bounded-scope accuracy |
| Patient pool | 50 patients (covering the full range of pregnancy risk) | Hand-auditable end-to-end |
| Current census | 16 admissions = **15 active + 1 discharged** | The 15 actives cover all 5 in-house stages; the 1 discharged provides a LOS baseline |
| Time-series data | ~3–10 labor progress entries and ~1–12 vital sign entries per active admission | Simulates cervical checks and monitoring sampling while staying small |
| Total | 11 tables, ~500 rows, SQLite < 200 KB | Medium complexity |
| Currency | USD | North American market |

**Deliberate scope decisions**: single ward, single snapshot, synthetic data (no real PHI). The dataset deliberately **excludes** newborn data, billing, multi-hospital, and real EMR fields — these are all future scope, deferred until the POC passes. The detailed table list and row counts live in `02-..._er_document.md`; this document does not enumerate tables.

---

## 8. Beat 7 Industry Knowledge Primer

An engineer without a healthcare background should be able to read this section and understand the ER document and the SQL that follow. This is the "30-minute onboarding" for the whole dataset.

### 8.1 The Lifecycle of an Admission (the admission state machine)

An OB admission moves through 6 stages from admit to discharge — this is the central axis of the dataset:

```
admitted → in_labor → delivered → postpartum → ready_for_discharge → discharged
admitted    in labor    just delivered  recovering   discharge order written   discharged
```

| Stage | Clinical meaning | Typical room | Counted in active census? |
|------|---------|------------|---------------------|
| `admitted` | Admitted but not yet in active labor | triage / labor | Yes |
| `in_labor` | Active labor, cervix dilating | labor (labor room) | Yes |
| `delivered` | Just delivered (≤2h) | delivery (OR) / labor | Yes |
| `postpartum` | Postpartum recovery (24–72h) | postpartum recovery room | Yes |
| `ready_for_discharge` | Discharge order written, awaiting actual discharge | postpartum | Yes |
| `discharged` | Already discharged | none (bed freed) | **No** |

**Active census (number of patients in house)** = all admissions except `discharged`. This is the answer to the very first question at handoff: "How many patients do we have right now?" (see metric formulas).

### 8.2 How to Read Labor Progress (the clinical concepts)

Labor progress is tracked by nurses doing periodic cervical exams, recorded against four indicators that together estimate "how much longer until delivery":

| Term | Meaning | Key threshold |
|------|------|---------|
| **Cervical dilation** | How wide the cervix is open, 0–10 cm | 10 cm = fully dilated, second stage (pushing) begins |
| **Effacement** | How thin the cervix has become, 0–100% | 100% = fully effaced |
| **Station** | Position of the fetal head relative to the ischial spines, -3 to +3 | +3 ≈ about to deliver |
| **Membrane** | The amniotic sac | `ruptured` (water broken) → typically delivers within 24h |

Rule of thumb: **dilation ≥ 8 cm + already ruptured ≈ delivery within 1–2 hours**. This is the basis for predicting "when does the labor room free up?" (P2, P3).

### 8.3 How Pregnancy Risk Is Assessed (risk_level derivation)

Each patient has a `risk_level` (low / medium / high). It's not entered by hand — it's derived from **risk factor accumulation**:

- Age ≥ 35 (**AMA**, Advanced Maternal Age): +1
- Multiples (twins / triplets, `fetus_count > 1`): +2 (multiples are OB's highest-alert category — preterm rate 60%+)
- Preterm tendency (`gestational_weeks < 37`): +1
- Prior C-section + planned **VBAC** this time: +1 (risk of uterine rupture)
- Each complication: +1

Total: **0 → low, 1–2 → medium, ≥3 → high**. High-risk patients are the focus of attending rounds and MFM consults (P4).

### 8.4 Delivery Mode & Length of Stay (LOS patterns)

| Delivery mode | English | Postpartum LOS (typical) |
|---------|------|------------------------|
| Vaginal | Vaginal delivery | 24–48 hours |
| C-section | C-section (Cesarean) | 72–96 hours (surgical recovery takes longer) |
| Vaginal after prior C-section | **VBAC** | A *planned* category; the actual delivery lands as either vaginal or C-section |

**Key convention**: in this dataset, `predicted_los_hours` refers to **postpartum** length of stay (measured from `delivery_time`, not including pre-delivery in-house time). LOS prediction accuracy (P3) is one of the numbers the client cares about most — if the AI predicts 40 hours for a C-section, it has failed to detect the delivery mode.

### 8.5 Ward Physical Layout (room → bed) and Bed Statuses

A ward has 5 functional room types; underneath rooms sit beds (a postpartum room can contain multiple beds):

| `room_type` | English | Use |
|-------------|------|------|
| `labor` | Labor room | Labor progress monitoring for vaginal delivery |
| `delivery` | Delivery room / OR | Surgical room for C-sections or complex deliveries |
| `postpartum` | Postpartum recovery room | Postpartum observation |
| `nicu` | Neonatal ICU | Preterm or critical newborns |
| `triage` | Triage | Pre-admission evaluation |

Beds have **4 statuses** — this is the core difficulty of P2, where a simple occupied/free binary is not enough:

- `available` (ready for next patient), `occupied` (patient inside), `cleaning` (last patient just left, being cleaned, ~30–60 min, **not yet usable**), `maintenance` (out of service for equipment work).

Legacy CMS uses a single boolean `is_occupied`, which treats "cleaning" as "free" and causes scheduling collisions. The POC has to prove that AI can correctly parse all 4 statuses.

### 8.6 Who Works in the Ward (provider and shift)

5 clinical roles + title conventions:

| `role` | English | Title | Per shift |
|--------|------|------|---------|
| `attending` | Attending physician | `Dr.` | 1 per shift |
| `resident` | Resident (in training) | `Dr.` | 1 per shift |
| `nurse` | Registered Nurse (RN) | `RN` | day 3 / night 2 |
| `midwife` | Certified Nurse-Midwife (CNM) | `CNM` | 1 per shift |
| `anesthesiologist` | Anesthesiologist | `Dr.` | 1 per shift |

The ward runs 24/7, split into `day` (07:00–19:00) and `night` (19:00–07:00) shifts. **Anesthesiologist being a separate role is critical**: C-sections and epidurals can only be scheduled when an anesthesiologist is on duty (P5).

### 8.7 Alerts and Thresholds

One of MaterniFlow's **outputs** is automatic alerts. When a vital sign crosses a threshold, an alert is derived:

| Indicator | warning | critical |
|------|---------|----------|
| `bp_systolic` (systolic BP) | ≥ 140 | ≥ 160 |
| `bp_diastolic` (diastolic BP) | ≥ 90 | ≥ 110 |
| `fetal_heart_rate` (FHR) | <110 or >160 | <100 or >180 |
| `temperature` (°F) | ≥ 100.4 | ≥ 101.5 |

There are 4 alert categories: `high_bp`, `abnormal_fhr`, `fever`, `preterm_risk`. The signature moment of the POC (P4): the legacy system only fires when BP ≥ 140 at a single reading, **missing the gradual upward trend**; the AI has to recognize a sequence like "125→131→137→143" — an early sign of pregnancy-induced hypertension that the single-threshold approach can't catch.

### 8.8 Payer Mix

US healthcare is sensitive to insurance type — it affects billing and resource allocation:

- **commercial** (commercial insurance): higher per-encounter reimbursement, needs detailed documentation.
- **Medicaid** (government low-income insurance, proper noun, capitalized): longer reimbursement cycles but high volume.
- **self_pay** (self-pay): requires up-front deposit.

This dataset's payer mix is roughly commercial 55% / Medicaid 35% / self_pay 10%, reflecting the US childbearing-age insurance distribution (the Finance Analyst's "P-cross-section" view).

---

## 9. Beat 8 Glossary

Every English jargon term that appears in the ER document or SQL gets a plain-language explanation here, plus one line on "why it matters here." Acronyms are spelled out on first appearance.

### 9.1 OB Clinical Terms

| English term | Plain-language explanation | Why it matters here |
|---------|-----------|--------------|
| **Obstetrics (OB)** | The specialty of pregnancy and delivery | The specialty covered by the whole dataset |
| **Maternity ward** | OB inpatient ward | The POC's physical boundary |
| **Admission** | One complete inpatient stay (admit to discharge) | The central fact table; all events hang off it |
| **Length of Stay (LOS)** | Time spent inpatient | The prediction target for P3; in this dataset specifically refers to **postpartum** LOS |
| **Gravida (G)** | Total number of pregnancies (including this one) | Written together with Para as e.g. "G2/P1"; distinguishes nullipara from multipara |
| **Para (P)** | Prior deliveries (pregnancies reaching ≥20 weeks) | P0 = nullipara (longer labor); P≥1 = multipara |
| **EDD (Estimated Due Date)** | Estimated due date | P-cross-section: patients within a week of due date need an early confirmation call |
| **Gestational weeks** | Current gestational age (e.g., 38.4 = 38 weeks + 2.8 days) | <37 = preterm, >42 = post-term; drives EDD and risk |
| **Cervical dilation** | Cervix opening, 0–10 cm | Primary indicator of "how much longer until delivery" (P2/P3) |
| **Effacement** | Cervical thinning, 0–100% | Auxiliary labor-progress indicator |
| **Station** | Fetal head descent, -3 to +3 | +3 ≈ about to deliver |
| **Membrane** | Amniotic sac | Once `ruptured` (water broken), delivery usually within 24h |
| **Fetal Heart Rate (FHR)** | Fetal heart rate, normal 110–160 bpm | Abnormal values trigger `abnormal_fhr` alerts |
| **Vaginal delivery** | Vaginal birth | Shorter LOS (24–48h) |
| **C-section (Cesarean section)** | Cesarean section | Surgical delivery, longer LOS (72–96h), needs OR + anesthesiologist |
| **VBAC (Vaginal Birth After Cesarean)** | Vaginal birth after a prior C-section | Standalone high-attention category; risk of uterine rupture |
| **Induction** | Induction of labor (artificially started) | Needs labor room + attending; can be scheduled (P5) |
| **Epidural** | Epidural anesthesia (pain control during labor) | Bedside procedure; needs anesthesiologist |
| **GBS (Group B Streptococcus)** | Routine late-pregnancy screen | Positive cases need intrapartum antibiotic prophylaxis |
| **Preeclampsia** | Pregnancy-induced hypertension syndrome | Tied to the BP upward trend (P4) |
| **Gestational hypertension** | Pregnancy-induced high blood pressure | High-risk complication |
| **Gestational diabetes** | Pregnancy-induced diabetes | Common complication; affects nutrition consult |
| **Placenta previa** | Placenta covering the cervix | Bleeding risk; often requires C-section |
| **Oligohydramnios / Polyhydramnios** | Too little / too much amniotic fluid | Complication category |
| **Intrauterine Growth Restriction (IUGR)** | Restricted fetal growth in utero | High-risk complication |
| **AMA (Advanced Maternal Age)** | Maternal age ≥ 35 | risk_factor +1 |
| **NICU (Neonatal Intensive Care Unit)** | Neonatal ICU | For multiples / preterm, NICU bed availability is essential (P2) |
| **MFM (Maternal-Fetal Medicine)** | High-risk pregnancy sub-specialty | Multiples and preterm cases are consulted with the MFM Specialist |

### 9.2 Care Team and Operations Terms

| English term | Plain-language explanation | Why it matters here |
|---------|-----------|--------------|
| **Attending** | Attending physician (top clinical authority) | Rounds, sets direction |
| **Resident** | Resident physician (in training) | Front-line execution |
| **Nurse (RN, Registered Nurse)** | Registered nurse | Daily backbone of the ward |
| **Charge Nurse** | Lead nurse on shift | Front-line commander: handoff, bed-hunting, dispatch |
| **Midwife (CNM, Certified Nurse-Midwife)** | Certified nurse-midwife | Catches vaginal deliveries |
| **Anesthesiologist** | Anesthesiologist | Required for C-section / epidural |
| **Triage** | Pre-admission triage | Pre-admission evaluation |
| **Shift handover** | Shift change (day ↔ night) | P1; The Joint Commission has compliance standards for this |
| **Census** | Number of patients in house | First line at handoff |
| **OR (Operating Room)** | Operating room (i.e., delivery room) | Where C-sections happen |
| **Order (medical order)** | Medical order (test / procedure / medication) | The scheduling target in P5 |

### 9.3 Industry and IT Terms

| English term | Plain-language explanation | Why it matters here |
|---------|-----------|--------------|
| **POC (Proof of Concept)** | Small pilot project | The nature of this dataset's project |
| **EMR / EHR (Electronic Medical/Health Record)** | Electronic health record | The hospital's core system; the POC does not connect to it yet |
| **HIS (Hospital Information System)** | Hospital information system | MaterniFlow is not one; it's only a lightweight augmentation |
| **HL7 / FHIR** | Healthcare data exchange standards | Future interface for connecting to a real EMR |
| **HIPAA** | US patient privacy and data security law | Using fake data in the POC is precisely how the team avoids real PHI |
| **PHI (Protected Health Information)** | Protected health information | The dataset is synthetic — no real PHI |
| **SaMD (Software as a Medical Device)** | Software regulated as a medical device | MaterniFlow draws the "no diagnosis" line to stay outside this regulation |
| **CMS (Centers for Medicare & Medicaid Services)** | US federal Medicare/Medicaid agency | Owns reimbursement and quality reporting |
| **CMIO (Chief Medical Information Officer)** | Top medical informatics executive | Client-side POC sign-off authority |
| **The Joint Commission (TJC)** | Hospital accreditation body | Sets compliance standards for shift handoff |
| **Payer mix** | Insurance type distribution | The Finance Analyst's concern |
| **CMS-like (content management)** | Content-management style (query + display, no decisions) | The essence of the POC scope boundary |

---

## 10. Beat 9 Key Metrics & Formulas

The metrics below all appear in `03-..._sql_queries.md`. Formulas are written in SQL-style pseudocode; anywhere "today" is needed, the literal `'2026-02-13'` (= REFERENCE_DATE) is used, never `DATE('now')`.

### 10.1 Census and Beds

```
-- Active census: the first sentence at handoff
Active Census = COUNT(admission WHERE status != 'discharged')

-- Beds per status per room type (P2): cleaning/maintenance cannot be lumped into "unavailable"
Beds By Status(room_type) = COUNT(bed) GROUP BY status   -- available/occupied/cleaning/maintenance

-- Bed utilization (P2, operations view)
Bed Utilization % = occupied_beds / total_beds * 100

-- "How many beds will be usable in 30 minutes" (counts cleaning as soon-to-be-available)
Available Soon = COUNT(bed WHERE status IN ('available', 'cleaning'))
```

### 10.2 Length of Stay (LOS) — convention is "postpartum"

```
-- Predicted postpartum LOS (measured from delivery, excludes pre-delivery time)
Predicted Postpartum LOS = predicted_los_hours
    where: c_section ∈ [72, 96] hours, vaginal ∈ [24, 48] hours

-- Actual postpartum LOS (discharged admissions only)
Actual Postpartum LOS = (actual_discharge_time - delivery_time) converted to hours

-- LOS prediction error (the headline number for P3)
Avg Absolute Error = AVG(ABS(Actual Postpartum LOS - Predicted Postpartum LOS))
Within 12h Rate    = COUNT(|actual - predicted| <= 12) / COUNT(*)
```

> Important convention: both predicted and actual LOS are measured **from `delivery_time`** so they're comparable. Do not compare "total stay (admit→discharge)" against "postpartum prediction" — they're different.

### 10.3 Risk and Alerts

```
-- Risk-level derivation (see 8.3)
risk_factors = (age>=35 ? 1:0) + (fetus_count>1 ? 2:0) + (gest_weeks<37 ? 1:0)
             + (prior=c_section AND planned=vbac ? 1:0) + COUNT(complications)
risk_level   = risk_factors==0 ? 'low' : (risk_factors<=2 ? 'medium' : 'high')

-- BP trend (P4): use the LAG window function to compute each reading's change from the previous one
Systolic Change = bp_systolic - LAG(bp_systolic) OVER (PARTITION BY admission ORDER BY recorded_at)
    consecutive positives = upward trend; even if every single point is < critical, the trend should fire
    
-- Fever threshold (North American OB convention)
FEVER = temperature >= 100.4 °F   -- (= 38.0 °C)
```

### 10.4 EDD and Scheduling

```
-- Estimated due date (deterministic derivation)
EDD = REFERENCE_DATE + (40 - gestational_weeks) * 7 days

-- Days until due (P-cross-section)
Days Until Due = julianday(edd) - julianday('2026-02-13')

-- Order completion rate (P5)
Completion Rate(order_type) = COUNT(status='completed') / COUNT(*) * 100
```

### 10.5 Workload and Structure

```
-- Provider current workload (a provider counts if they are the attending OR the primary nurse)
Provider Workload = COUNT(DISTINCT admission WHERE attending_provider_id = P OR primary_nurse_id = P
                                            AND status != 'discharged')

-- Payer mix (P-cross-section)
Payer Mix % = COUNT(*) / SUM(COUNT(*)) OVER () * 100  GROUP BY insurance_type

-- Complication frequency (P-cross-section): in SQLite, use LIKE for pattern matching on a JSON field
Complication Frequency = COUNT(complications LIKE '%<name>%')  counted per complication
```

---

> Suggested next reading order: table structure & fields → `02-..._er_document.md`; queries & solution approaches → `03-..._sql_queries.md`; data generation logic → `04-..._data_generator.py`.
