# Medical Devices: Orthopedic Implant Tracking Business Context

> This document is the business charter for the dataset. It explains who the company is, how it makes money, how its industry operates, what questions this database is meant to answer, and all the industry terminology you need to make sense of the data. For the data structures themselves (tables, fields, generation rules, business traps), see `02-medical_devices_orthopedic_implant_tracking_high_er_document.md`; for hands-on SQL exercises, see `03-medical_devices_orthopedic_implant_tracking_high_sql_queries.md`.

Picture the reader of this document as an analyst who just joined the team. By the time you finish it, you should be able to walk into your first standup and talk shop about "the notification SLA on a Class I recall" or "why consignment inventory doesn't count toward tied-up capital" without looking lost.

---

## 1. Company Snapshot

**MAOHN (MidAtlantic Orthopedic Health Network)** is a fictional non-profit regional hospital group headquartered in the U.S. Mid-Atlantic region (roughly Maryland, Virginia, and Pennsylvania). The group operates **12 acute care hospitals**, ranging in size from a 50-bed community hospital to an 800-bed regional center.

MAOHN performs about **6,000 orthopedic procedures per year**, of which roughly two-thirds involve at least one implantable device, including total hip and total knee replacements, fracture fixation (plates, bone screws, intramedullary nails), and spinal fusion. This is a hospital system with deep orthopedic specialization: it doesn't manufacture its own devices. Instead, it buys implants from the major national manufacturers, puts them into patients, and then carries lifelong traceability responsibility for those devices.

The C-suite shows up by name throughout this dataset, because many of the queries are built for them:

- **CFO (Chief Financial Officer)** watches costs, especially per-case implant cost.
- **CMO (Chief Medical Officer)** owns clinical safety and recall response.
- **CCO (Chief Compliance Officer)** signs off on FDA audits and data integrity.
- **VP of Supply Chain** manages procurement, inventory, and consignment agreements.
- **VP of Surgical Services** manages physician credentialing, surgical scheduling, and clinical data.
- The **Director of Clinical Quality** and the **Medical Director** own adverse event surveillance and peer review.

The key fact that every downstream model is derived from: **this database belongs to MAOHN, the hospital system. It does not belong to the device manufacturers, to a GPO, to the FDA, or to a third-party UDI compliance SaaS vendor.** Whenever you see "cost," it's a cost the hospital paid. Whenever you see "recall response," it's the hospital's obligation as the first-line responder for patient safety.

---

## 2. Business Model

Like most U.S. hospital systems, MAOHN earns revenue on a **per-visit / per-case basis**, paid by various payers. The payer mix for the orthopedic line of business looks roughly like this:

| Payer | Share of Orthopedic Revenue (typical) |
|---|---|
| Medicare and Medicare Advantage | ~55% |
| Commercial insurance (BCBS, UnitedHealthcare, Aetna, Cigna) | ~30% |
| Medicaid | ~10% |
| Self-pay and other | ~5% |

Here's the point that anyone outside healthcare gets backwards, and it's worth stating clearly: **for an implant procedure, the implant device itself is a cost line, not a revenue line.** Medicare does not pay you more because you used a more expensive prosthesis; it pays a bundled amount based on the DRG (Diagnosis Related Group). For example, MS-DRG 470 covers "major joint replacement without complications," and the bundled payment is already supposed to cover the prosthesis. In other words, revenue is fixed, and the more expensive the implant, the thinner the hospital's margin.

That leads directly to MAOHN's core economics: **every dollar saved on device procurement falls almost entirely to the bottom line.** Within the total cost of an orthopedic inpatient stay, the implant accounts for 40% to 60%, which makes it both the single largest line item and the most compressible one. That's why **implant cost control consistently ranks in the CFO's top three priorities**, and it's why this database models contracted pricing and consignment in such detail. You can't control what you can't see, and seeing it means being able to trace "which serial number, on which date, under which contract price" all the way through.

---

## 3. Industry Overview

Orthopedic implants are a heavily regulated medical-device business. From an outsider's view, the industry shakes out like this.

**What value does this industry create.** Device manufacturers design, produce, sterilize, and distribute the metal and polymer components that get implanted permanently or semi-permanently into the human body (acetabular cups, femoral stems, knee prostheses, spinal rods and pedicle screws, plates and screws for fracture fixation, and so on). Hospitals are the buyer and the user. They are responsible for placing the device correctly and for tracking it for the entire time it lives inside the patient. When something goes wrong with a device (fracture, loosening, infection, design defect), the chain of responsibility runs through both the manufacturer and the hospital.

**Who the major players are.** Upstream sits the device manufacturer (this dataset uses real company names like Stryker, Zimmer Biomet, and DePuy Synthes as sample data, but the MAOHN organization itself is fictional). In the middle, you often see a GPO (Group Purchasing Organization) negotiating volume discount contracts on behalf of hospitals. Downstream sits the hospital and the surgeon. One thing that's peculiar to this market is that orthopedic purchasing is heavily **surgeon-driven**: surgeons have strong brand preferences (the industry term is "physician preference item"), which limits the hospital's leverage when negotiating price.

**Who regulates it.** The core U.S. regulator is the **FDA (Food and Drug Administration)**. The regulations that touch this dataset directly include: device marketing authorization (510(k), PMA, De Novo, HDE, and similar pathways), mandatory UDI (Unique Device Identification) labeling and the GUDID database, mandatory adverse event reporting (21 CFR Part 803, the MDR rule), the Quality System Regulation (21 CFR Part 820), and the electronic records / electronic signatures rule (21 CFR Part 11). The Canadian counterpart is **Health Canada**. This dataset assumes the North American market, with currency in USD.

**Current macro trends.** A few forces are pushing the industry at once: UDI compliance has shifted from "recommended" to "mandatory," which pushes traceability burden down to the hospital; consolidation among GPOs and hospital systems has shifted a bit of pricing leverage back toward the buyer; joint replacement is migrating from inpatient settings to ambulatory surgery centers (ASCs); and real-world evidence and device registries are getting more attention from both regulators and payers. MAOHN's decision to build this registry rides on that last trend.

---

## 4. Project Background and Your Role

You're an analyst on MAOHN's data team, serving the executives and business owners named above directly. The system you're working with is the **orthopedic implant registry**. It is not the hospital's transactional system; it is a **downstream analytical mart** that gets refreshed nightly from five upstream source systems and is specifically built to answer cross-system, cross-hospital analytical questions.

Your typical deliverables fall into a few buckets:

- **Cost dashboards** for the CFO and finance team (implant spend by hospital and by fiscal year).
- **Recall response worklists** for the CMO, CCO, and recall coordinators (which patients have an affected device in their body, has notification been sent, has it been acknowledged).
- **Quality and outcomes reports** for the Clinical Quality Committee (adverse event rates, revision rates, FDA MDR submission packages).
- **Inventory and contract compliance analysis** for the VP of Supply Chain (inventory nearing expiration, turnover rates, whether actual paid prices match the contract).

The reason this system exists separately, rather than being a set of queries running directly against Epic EHR or the ERP, is that the following four things can't be done by any single upstream system on its own. These four things define the four pillars of this project:

1. **FDA Part 11 plus UDI compliance traceability.** Every implanted device must be traceable from the manufacturer lot all the way down to the specific patient, and a full audit log must be retained. This is a hard requirement of 21 CFR Part 820 and Part 803.
2. **Recall response within SLA.** When the FDA or a manufacturer issues a recall, MAOHN has a regulatory window to pull affected stock off the shelves, identify every patient who already has an affected unit implanted, and complete patient notification. The windows are 3 days for Class I, 30 days for Class II, and 60 days for Class III. Miss it and you get fined, and you get sued.
3. **Cost per case control.** Implants are 40% to 60% of the total cost of an orthopedic inpatient stay. The supply chain team needs to be able to drill into "what did this exact serial number cost us, which units are on consignment, and which ones got wasted because they expired or were recalled."
4. **Adverse event and long-term clinical outcome surveillance.** Used both for FDA MDR submissions and for continuous improvement reviews by the hospital's quality committee.

---

## 5. Business Questions to Answer

The entire dataset is designed around the following five business questions. Each one is answered by one or more SQL queries (specific numbering lives in document `03`); here we just explain the questions themselves.

**Question 1, and the headline question for this whole project: when a recall hits, can we find and notify every affected patient within SLA?** Recalls come in two scopes: lot-level (just a bad lot) and full-product-level (an entire product line). Design-defect recalls tend to be product-level, and missing one of those is a regulatory incident. We need to be able to pull, at any moment, "every implanted patient touched by every currently active recall," flagged with who hasn't been notified, who has been notified but hasn't acknowledged, and which ones are already past SLA.

**Question 2: how much did each hospital spend on implants, by year?** This is the CFO's recurring spend rollup. The trap is that price is not a single fixed number: the same product traded at different prices over time and across contract types (GPO, Direct, Consignment). The correct rule is to use the contract price that was in effect at the **point in time the unit was received**, not the current catalog price.

**Question 3: are we actually paying the prices our contracts promised?** Procurement audits whether GPO contract pricing is being honored. If, for some manufacturer under some contract type, the realized discount has been chronically below the industry benchmark, that's money leaking out the door, and the contract needs to be renegotiated.

**Question 4: which devices and which surgeons have worse clinical outcomes?** The clinical quality team monitors adverse event rates (counted per surgery, not per implant), revision rates, and outliers at the manufacturer and surgeon level under a single, consistent definition. These numbers feed the vendor scorecard, physician peer review, and FDA MDR submissions.

**Question 5: is inventory being wasted, and is turnover healthy?** Supply chain wants to find high-value inventory expiring within 90 days, identify hospitals with low turnover and high capital tied up, and make sure lots that recently failed QC haven't quietly slipped into stock and been used.

Beyond these five marquee questions, the dataset also supports a batch of everyday operational queries: rolling 12-month surgery volume trends, surgeon volume rankings, average operative time by procedure, FDA approval rates by submission pathway, prediction of pending high-value submissions, and so on. None of these is anyone's top KPI, but somebody runs them every day.

---

## 6. Data Scope Overview

This dataset is intentionally smaller than a real registry, to keep it teachable. A few key boundaries:

- **Time horizon.** All dates are anchored to a fixed reference point, `REFERENCE_DATE = 2026-06-01` (called `NOW` in the generator). Surgery, procurement, and inventory events cover roughly the prior 2 years; manufacturing lots and price history go back roughly 5 to 6 years before that. Fixing the reference point keeps query results reproducible, so the answer doesn't change just because today's date moves forward.
- **Data volume.** 20 tables, totaling about 14,000 rows. The scale is "a few hundred patients, a few thousand surgeries, two to three thousand inventory units, tens of thousands of event log rows," not the millions you'd see in a real hospital.
- **Scope cuts.** Single hospital system (12 hospitals), single specialty (orthopedics), North American market, currency in USD. There's no model of HIPAA consent, no normalized allergy or comorbidity tables, and the audit log is illustrative rather than a complete transaction-level trace. These cuts are deliberate and are meant to keep the SQL patterns visible instead of buried under compliance boilerplate. The full list of trade-offs lives in the "Known Limitations" section of the `02` ER document.

It's worth emphasizing: the data is synthetic, but the distributions are calibrated to industry norms. Class II dominates the recall mix, Minor severity dominates the adverse event mix, 510(k) approval rates hover around 90%, and the consignment share is meaningfully higher for high-value categories. These intentionally seeded distributional patterns (the "business traps") are exactly what the SQL queries are designed to surface.

---

## 7. Industry Background Primer

This is the 30 to 60 minutes of background you need if you're new to the industry. Feel free to skim if you already know it.

### UDI: a device's ID badge

**UDI (Unique Device Identification)** is the FDA-mandated device labeling system. It has two parts:

- **UDI-DI (Device Identifier)**: identifies "which product model is this." Every device of the same model shares the same DI. This dataset uses the GS1 GTIN-14 format (14 digits, with leading zeros).
- **UDI-PI (Production Identifier)**: identifies "which specific physical device this is." It's composed of the lot number, serial number, expiration date, and similar fields.

In a barcode, these pieces are tagged with GS1 Application Identifiers (AIs): `(01)` precedes the GTIN, `(10)` precedes the lot, `(21)` precedes the serial number. This dataset's `inventory.udi_pi` field is assembled in the form `(01){UDI-DI}(10){lot}(21){serial}`. One-sentence summary: DI tells you "what it is," PI tells you "which one." Recalls depend on this system to pinpoint the right lot or the right unit.

### Lot and serial number

Devices are produced in **lots (or batches)**, with a lot containing anywhere from tens to hundreds of units. Each physical unit then has its own unique **serial number**. A lot-level recall affects an entire batch; single-unit traceability requires resolving down to the serial number. In MAOHN's `inventory` table, each row is one physical unit, the serial number is globally unique, and once implanted, the unit is gone forever.

### Consignment and purchase

High-value orthopedic implants are commonly placed on **consignment**: the manufacturer puts the stock on the hospital's shelf, but title still belongs to the manufacturer until the device is actually used in a procedure, at which point the hospital is invoiced. About 60% of high-value implants (hip, knee, spine, shoulder) are on consignment. This has an important financial implication: consignment inventory does not tie up hospital capital, because it hasn't been purchased yet. So when you compute "capital tied up," you must exclude consignment units. A **purchase** unit, by contrast, was paid for up front and sits on the shelf with cash already committed to it.

### DRG bundled payment

**DRG (Diagnosis Related Group)** is Medicare's bundled payment mechanism: a fixed payment is set per diagnosis group, regardless of what the hospital actually spent. **MS-DRG** is the specific Medicare version (e.g., MS-DRG 470 = major joint replacement without complications). The DRG bundle is the regulatory root cause of the "implant is a cost, not revenue" rule.

### The three recall classes and their SLAs

The FDA classifies device recalls into three tiers by risk, each with its own response window (the SLAs this dataset uses):

| Class | Risk meaning | Notification SLA |
|---|---|---|
| Class I | Could cause serious injury or death | 3 days |
| Class II | Could cause temporary or reversible harm | 30 days |
| Class III | Unlikely to cause harm | 60 days |

Once MAOHN receives a recall, it must complete notification of the affected patients, hospitals, and surgeons within that window. This dataset models "did notification beat SLA" as a metric that can be computed directly in SQL.

### FDA marketing authorization pathways

To go on the market legally, a device must clear an FDA pathway:

- **510(k)**: the most common one. The applicant proves "substantial equivalence" to a legally marketed predicate. Shorter cycle (typically 3 to 6 months) and high approval rate (about 90%).
- **PMA (Premarket Approval)**: the strictest. Used for high-risk devices, requires clinical trials, and runs significantly longer.
- **De Novo**: for novel low-to-moderate-risk devices with no predicate.
- **HDE (Humanitarian Device Exemption)**: a special pathway for rare-disease devices.

### A few clinical and operational identifiers and scores

- **NPI (National Provider Identifier)**: every U.S. provider's 10-digit national identifier.
- **MRN (Medical Record Number)**: the chart number; unique within a single hospital, but not across hospitals.
- **ASA score**: pre-anesthesia assessment of overall patient condition, scored 1 through 6 (higher is worse).
- **CPT code**: identifies what surgical procedure was performed. **ICD-10 code**: identifies what the diagnosis was.
- **Trauma level**: a hospital's tier for handling major trauma. Level I handles the most severe cases, with capability decreasing as the number rises.

### Adverse event reporting: MDR and MAUDE

When a device-related adverse event occurs (infection, loosening, fracture, etc.), the hospital may have to file an **MDR (Medical Device Report)** with the FDA. These reports flow into the FDA's public database, **MAUDE**. The `adverse_event` table in this dataset is the source material for MDR filings.

### Data tiers: raw, silver, gold

The dataset is deliberately built in three tiers, so you can practice both "query the raw events" and "just read the precomputed current state":

- **Raw (the bronze tier)**: append-only event streams, and the single source of truth. For example, `inventory_movement` records every physical action, and `pricing_history` records every price change.
- **Silver**: the "current state" caches derived from raw. For example, `inventory.status` and `inventory.location` are both computed back from the latest movement record.
- **Gold**: pre-aggregated analytical views, defined in the SQL document as `CREATE VIEW`, designed to be hit directly by dashboards.

When silver and raw seem to disagree, raw always wins. The generator builds raw first and derives silver from it, so the two layers don't drift apart in structure.

### Pricing history as SCD2

Prices change over time and across contracts. They're modeled using **SCD2 (Slowly Changing Dimension Type 2)**: each price record carries an effective range (`effective_date` to `end_date`), and `end_date IS NULL` means the price is still in effect. To find "what was the price on the day this unit was received," you look up the price record whose range contains that date.

---

## 8. Glossary

The terms used across the dataset are explained here in one place. Industry terms stay in English (that's how they're written in the industry), followed by a plain-language explanation and a one-liner on why they matter here.

| Term | Plain meaning | Why it matters here |
|---|---|---|
| **UDI** | Unique Device Identification, the FDA-mandated device "ID badge" system | Foundation of recall and traceability |
| **UDI-DI** | The "which product model is this" part | Used to pinpoint a full-product recall |
| **UDI-PI** | The "which specific unit is this" part (includes lot and serial) | Used for single-unit traceability |
| **GUDID** | The FDA's Global UDI Database | Source of reference data for product and manufacturer |
| **GS1 / GTIN / AI** | A globally adopted barcode standard; GTIN is a 14-digit product number; AI is the prefix like `(01)(10)(21)` inside a barcode | The rule for assembling the `udi_pi` field |
| **lot (batch)** | A batch of devices produced together | Scope of a lot-level recall |
| **serial number** | Unique identifier for one physical unit | Each unit can only be implanted once |
| **consignment** | Stock sits on the hospital's shelf but title belongs to the manufacturer; you pay only on use | Consignment doesn't count as tied-up capital |
| **purchase** | Hospital pays up front and brings the stock in | Cash is committed and sitting on the shelf |
| **GPO** | Group Purchasing Organization; negotiates volume discounts for hospitals | The thing being audited in contract pricing compliance |
| **DRG / MS-DRG** | Medicare's bundled payment grouping | Regulatory root cause of "implant is a cost, not revenue" |
| **payer** | The party paying for the visit (Medicare, commercial insurance, etc.) | Drives the revenue mix |
| **510(k) / PMA / De Novo / HDE** | The four FDA pathways to market | The `submission_type` in `regulatory_submission` |
| **recall class** | The FDA's I / II / III recall risk tiers | Drives whether the notification SLA is 3, 30, or 60 days |
| **SLA** | Service level agreement; here, the required response window | Whether recall response is on time |
| **MDR** | Medical Device Report filed with the FDA | The destination of `adverse_event` rows |
| **MAUDE** | The public FDA database containing MDRs | Reference source for quality review packages |
| **NPI** | A U.S. provider's 10-digit national ID | `surgeon.npi_number` |
| **MRN** | Medical record number, unique within a single hospital | `patient.mrn` |
| **ASA score** | Pre-anesthesia condition score (1 to 6) | Reflects baseline patient risk |
| **CPT code** | Identifies the procedure performed | `surgery.procedure_code` |
| **ICD-10 code** | Identifies the diagnosis | `surgery.diagnosis_code` |
| **trauma level** | Tier of hospital trauma response capability | `hospital.trauma_level` |
| **revision** | A follow-up surgery to redo a previous implant procedure | Revision rate is a core outcome metric |
| **point in time price** | The contract price in effect on the date a unit was received | The correct way to value cost |
| **SCD2** | Price history modeled with effective date ranges | The structure of `pricing_history` |
| **raw / silver / gold** | Raw event layer / current-state layer / pre-aggregated view layer | The dataset's tiering logic |
| **EHR** | Electronic Health Record system (Epic, in this dataset) | Upstream source of clinical data |
| **ERP** | Enterprise Resource Planning system (Workday, in this dataset) | Upstream source of procurement and inventory |
| **SIS** | Surgical Information System | Upstream source of implant-in-surgery events |
| **21 CFR Part 11 / 803 / 820** | FDA regulations on electronic records / adverse event reporting / quality systems | The compliance basis for this system |

---

## 9. Key Metrics and Formulas

These metrics appear throughout the SQL queries. We pin down a single definition and formula for each one here, so different queries don't compute mutually inconsistent numbers. Where a metric has more than one common formulation, this dataset commits to one and uses it everywhere.

**Adverse event rate.** The agreed definition is **events per 100 surgeries**, not per 100 implants. A surgery that used many implants and had one event is one affected surgery, not N.

```
adverse_event_rate = surgeries_with_event / total_surgeries * 100
```

**Recall SLA compliance.** Compare "days from recall publication to notification sent" against the SLA days for that recall class.

```
days_to_notify = notification_date - recall_date
over_SLA = days_to_notify > sla_days   (Class I = 3, Class II = 30, Class III = 60)
```

**Point in time contract price.** A unit's cost is the price record that was in effect on the day the unit was received.

```
unit_cost = pricing_history.contracted_price_usd
where  effective_date <= inventory.received_date
 and   (end_date IS NULL OR end_date > inventory.received_date)
```

**Cost per case.** First sum the point-in-time cost of every implant used in a given surgery, then roll up at the hospital or fiscal year level. Aggregate at the surgery level first, otherwise a one-to-many join will inflate "average implants per surgery."

```
cost_per_surgery = SUM(unit_cost for each unit used in that surgery)
```

**Inventory turnover.** Used units as a share of all inventory units for that hospital.

```
turnover = used_units / total_units * 100
```

**Capital tied up.** Only count purchased, still-available inventory. Exclude consignment units, because they haven't been bought yet.

```
capital_tied_up = SUM(contracted_price_usd WHERE status = 'Available' AND NOT is_consignment)
```

**2-year revision rate.** The flagship orthopedic outcomes metric. The denominator is each patient's first (non-revision) implant surgery (the index case), and the numerator is how many of those went on to a revision within 730 days.

```
revision_rate = index_cases_revised_within_730_days / total_index_cases * 100
```

**FDA approval rate.** `Withdrawn` (voluntary withdrawal) is excluded from the denominator, since withdrawn is not the same as denied.

```
approval_rate = Approved / (Approved + Pending + Denied) * 100
```

**Contract discount rate.** The discount of the actual paid price relative to the list price (MSRP).

```
discount_pct = (list_price_usd - contracted_price_usd) / list_price_usd * 100
```

**Lot QC status.** A lot is considered "QC passed" if and only if its most recent conclusive result (`Pass` or `Fail`; `Conditional` does not count as conclusive) is `Pass`. This status is computed at query time, not stored as a fixed boolean column.
