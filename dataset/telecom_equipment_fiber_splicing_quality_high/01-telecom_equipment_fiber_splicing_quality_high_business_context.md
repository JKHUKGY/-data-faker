# Fiber Splicing Quality and Cost Control Dataset Business Context

NorthArc Photonics Manufacturing is a fiber connector manufacturer based in Hillsboro, Oregon, specializing in pre-terminated patch cables and MTP trunk cable. Spun off from Intel's optical components division in 2014, the company now employs roughly 250 people and posted FY 2025 revenue of $80M USD. NorthArc runs a 14,000-square-foot Class 10K cleanroom assembly plant in Hillsboro, where 12 fusion splicers run three shifts a day, staffed by 30 splice operators plus 8 QA engineers — this splicing line is the production bottleneck for the entire plant.

You joined the company 6 months ago as Senior Manufacturing Analyst, reporting directly to VP of Operations Marcus Reed (who spent the previous 15 years at Corning). Earlier this year, CFO Linda Chen committed to a $1.2M cost-reduction KPI, driven by the fact that the company's largest datacenter customers (code-named DC-Alpha and DC-Bravo — every customer you'll see in this dataset is code-named) pushed unit prices down 8%, while splice-stage yield has visibly eroded over the last two quarters. Marcus handed the first move to you: a project called the Phase 1 Operations Cost Take-Out Plan, due at the end of Q3. The deliverable is a recommendation memo for the CFO and COO plus a live dashboard running on Tableau, and it needs to surface at least $700K in annualized savings.

This entire dataset was assembled for that project. It contains the full 12 months (2025-06 to 2026-06) of splicing production data from the Hillsboro plant, anchored to REFERENCE_DATE = 2026-06-15. Your job is to find money hiding in this data.

---

## 1. The Company, NorthArc Photonics

The company does exactly one thing: assemble optical fiber and connectors into ready-to-plug cables, sold to three types of customers. NorthArc doesn't draw fiber (that's Corning, Sumitomo) and doesn't build active optical components (that's Lumentum, Coherent). NorthArc handles the piece in between — the industry calls it cable assembly. It sounds simple, but splice loss has to stay within the customer's spec, or the entire cable gets scrapped. That's why the quality data matters so much.

The plant's org structure is flat:

```
CEO (David Park)
 ├── VP Operations (Marcus Reed)         ← your boss
 │    ├── Production Manager (Sarah Klein)
 │    │    ├── Day Shift Lead
 │    │    ├── Swing Shift Lead
 │    │    └── Night Shift Lead
 │    ├── Manufacturing Analytics (your seat, headcount of 1)
 │    └── QA Engineering Manager (Tom Vasquez)
 ├── VP Engineering (Priya Shah)
 ├── CFO (Linda Chen)
 └── VP Sales (Jorge Ramirez)
```

Marcus's instructions to you were blunt: the data needs to prove where the plant is bleeding money, not read like an academic report. Every finding needs an action attached, and every action needs a dollar figure.

---

## 2. Business Model and Unit Economics

NorthArc doesn't sell datacenter solutions — it sells piece parts. A 12-fiber MTP-MTP trunk cable might list at $48; an LC duplex FTTH drop cable might list at $7. Customers place one-time orders via PO, with volumes ranging from a few hundred to tens of thousands of units. There's no subscription, no take-rate — this is pure manufacturing unit economics.

The gross margin structure looks roughly like this (using a 12F MTP trunk as the example):

```
Selling price (ASP)            $48.00
   Fiber materials              $11.00   23%
   Connectors + housing          $9.00   19%
   Labor (splicing + testing
          + packaging)           $7.50   16%
   Equipment depreciation +
          power + consumables    $3.20    7%
   Rework + scrap                $4.10    9%   ← this is the line you need to cut
   Overhead (management + plant) $5.20   11%
Gross margin                    $8.00   17%
```

Datacenter customers (55% of revenue) squeeze unit price the hardest but order the largest volumes. FTTH operators (30% of revenue) pay acceptable prices but hold loose specs. Enterprise network customers (15% of revenue) order small volumes but pay premium prices. Splice loss tolerance varies widely across these customer segments — Q5 below goes into this in more detail.

The company's contribution margin runs around 35%. The $1.2M the CFO wants to claw back comes out of cost-of-goods (not from cutting SG&A headcount), since there's almost nothing left to cut in SG&A — the real fat is that 9% rework cost line in manufacturing cost. 9% is high for the industry (top-tier plants get this down to 4–5%), which is exactly what gives this project room to quantify savings.

---

## 3. Industry Overview, Fiber Connector Manufacturing

Fiber connector manufacturing is a modest but stable link in the telecom infrastructure value chain. The global market runs around $4B USD, with North America accounting for $1.2B, tracking hyperscale datacenter and FTTH buildout growth — and accelerating further the last couple of years on the back of AI cluster optical interconnect demand (400G, 800G optics).

The major players fall into four tiers. Tier one is integrated OEMs (unnamed here, but think companies with $500M+ revenue that draw their own fiber and build their own components). Tier two is contract manufacturers (where NorthArc sits). Tier three is large distributors doing their own assembly (think CDW, Anixter). Tier four is low-cost factories out of Asia, selling to SMBs and Amazon Marketplace, with inconsistent quality.

On the regulatory side, this niche is relatively lightly regulated in North America. The main standards to meet are Telcordia GR-326 (the general spec for FTTH connectors), the IEC 61753 series (fiber performance specs), and IPC-A-610 (assembly workmanship). Customer audits are far stricter than any government inspection — hyperscale customers run a source audit once a year, reviewing your SPC charts (statistical process control), your first-pass yield, and your calibration logs. A single audit that turns up a batch quality problem can get you dropped from the AVL (approved vendor list) outright.

A few macro forces have shaped the industry over the last three years: (1) AI training clusters have pushed fiber density inside datacenters up by an order of magnitude, driving a surge in demand for high-density MPO/MTP connectors; (2) federal BEAD program subsidies for FTTH have operators laying fiber out to small towns, driving FTTH drop cable volume up while compressing unit price; (3) labor costs have climbed, with skilled splice operator hourly wages rising from $22 in 2020 to $31 today; (4) hyperscale customers are pushing Total Cost of Ownership negotiations — you can no longer just sell a cable, you have to bundle in SLAs, RMA (return material authorization) turnaround, and traceability.

---

## 4. Your Role and This Project

Your title is Senior Manufacturing Analyst, and you're the only manufacturing analyst at the company. It looks like a junior role but carries outsized responsibility. Your job is to translate what the production line generates into dollar figures and tell Marcus where the money is leaking.

You previously did yield engineering at Intel, so you know wafer fab SPC cold, but fiber splicing was new to you — it took three weeks on the floor watching operators work before it clicked. This business-context glossary is essentially the memo you wrote for yourself along the way.

Scope of the Phase 1 project:

Step one, understand the current state. Use 12 months of production data to chart the splice loss distribution, reject rate trends, and yield variance across equipment, shifts, operators, fiber batches, and customer order specs. This step is data exploration.

Step two, find the eight biggest cost sinks. Marcus handed you eight suspicions he'd picked up from the floor (you'll see them in the next section) and asked you to confirm or refute each one with data, with a quantified annualized loss figure attached.

Step three, attach an action recommendation to every confirmed sink, estimate ROI, and rank them. For example: "Switch electrode replacement on all fusion splicers from failure-triggered to proactive replacement every 1,800 splices, one-time investment of $X, annual savings of $Y, ROI in 8 months" — that's the shape of conclusion you're after.

Step four, write the above up as a 12-page memo for the CFO, plus a Tableau dashboard for the Production Manager's daily use.

Timeline: you received the data in early June 2026, and the memo is due by the end of September. This dataset is the data foundation for steps one and two.

---

## 5. The Eight Business Questions the Project Must Answer

These are the eight hypotheses Marcus threw at you in the kickoff meeting. Each one needs a yes-or-no answer plus a dollar figure. All eight run through the SQL queries document that follows this one.

**Q1. The overview — where is the money leaking**
Over the past 12 months, on a fiscal-year basis, what is the total reject cost of the splicing process? Broken down by root cause (electrode wear / equipment calibration overdue / operator mismatch / batch quality / shift variance / over-spec rejection / ignored alerts / repeated retries), how many dollars does each account for?

**Q2. Electrode replacement strategy**
The plant's current electrode replacement strategy is reactive (replace only when an alert fires). Does the data show that "reject rate rises significantly once splice count exceeds 2,000"? If the plant switched to condition-based preventive replacement (proactive replacement every 1,800 splices), what would the annualized savings be?

**Q3. Night-shift quality degradation**
The floor has been reporting more rejects on the night shift. How much does reject rate actually differ across shifts in the data? If a $80K/year floating senior supervisor were added to the night shift, how much reject cost would that recover?

**Q4. Skill mismatch on multi-core splicing**
Multi-core fiber (used in 400G/800G optics) is significantly harder to splice than single-core, but the current scheduling assigns operators randomly, without regard to skill level. How much does reject rate on multi-core splicing differ across operator skill levels? If multi-core work were restricted to senior-level operators and above, what would the annualized savings be?

**Q5. Over-quality — a spec-relaxation opportunity on FTTH orders**
The internal SOP judges every splice against the strictest 0.05 dB threshold as a reject cutoff. But the actual FTTH customer spec is 0.30 dB, meaning a large volume of product that would pass at the customer's site is being scrapped internally. If splices were judged dynamically against the customer order's actual spec, how many fewer units would need rework each month?

**Q6. Downstream impact of ignored AI alerts**
The plant rolled out a splice-loss prediction and alerting system last year. When an alert fires, the operator can choose to redo the splice, adjust parameters, or ignore the alert. What is the downstream reject rate for alerts that get ignored? What would the annualized savings be if the system's alert recommendations were enforced (hard-blocked by the system)?

**Q7. Equipment calibration overdue**
The current calibration SOP calls for recalibration every 90 days, but enforcement is loose — roughly 30% of equipment runs overdue. How much does reject rate differ between overdue and on-schedule equipment? If the SOP were tightened to a 60-day cycle, what would the annualized savings be?

**Q8. Recall risk — bad batch MFG-2024-038**
QA reported last week that a batch is suspected of having abnormal cladding-diameter variance. What is this batch's actual reject rate? How many units have already shipped? How many customer complaints have come in? Does this warrant a customer notification and recall?

Each Q maps to an actual distribution bias planted in the dataset (the "business traps" section of the ER document that follows will list the expected magnitude for each), and the SQL queries document will run 2 to 3 queries per Q to pull out the answer.

---

## 6. Data Scope

Time window: 2025-06-16 through 2026-06-15, a full 12 months. REFERENCE_DATE is anchored at 2026-06-15 — this is the project's data freeze point. Every "as of today" or "last 30 days" calculation in the SQL queries is relative to this date.

Geographic scope: Hillsboro plant only. The company also runs a small packaging-only plant in Phoenix, which is not included in this dataset.

Business scope: fusion splicing process only. The upstream connector polishing step and downstream finished-cable testing (insertion loss test, return loss test) are out of scope — they'll be picked up in Phase 2.

Data volume: 18 tables, roughly 220,000 total rows. The main fact table, splice_record, has about 50,000 rows (roughly 140 splices a day over 12 months); splice_attempt has about 55,000 rows (most splices succeed on the first try, but some need 2 to 3 retries). Dimension tables are small: 12 customers, 12 pieces of equipment, 30 operators.

Explicitly excluded from scope: Phoenix plant data (too small to matter); polishing and testing processes (Phase 2 scope); sensitive HR fields (the only compensation detail is an hourly_rate field on the operator table — no bonus or detailed performance records).

---

## 7. Thirty-Minute Primer, How Fiber Splicing Works

If you've never worked in fiber manufacturing before, this section is the bare minimum you need to hold a conversation with plant staff. Marcus walked you through this himself on your first week on the floor.

### What fiber actually looks like

The core of a fiber strand is a glass filament about the thickness of a human hair (roughly 250 microns in diameter), built from three layers. Innermost is the core, the part that actually carries light — for single-mode fiber, the core diameter is only 9 microns. Around that is the cladding, also glass, with a lower refractive index than the core, which is what confines the light to the core; standard diameter is 125 microns. Outermost is the coating, a polymer layer protecting the glass, standard diameter 245 microns. Manufacturers ship fiber wound on a 30-centimeter plastic reel — one reel is called a spool, typically 25 kilometers of fiber.

Fiber spec depends on the model. The most common is G.652.D single-mode fiber, used for long-haul transmission. High-density datacenter applications use G.657.A1 bend-insensitive single-mode fiber, which tolerates a tighter bend radius. Multimode fiber, OM4 and OM5, is used for short runs (inside buildings). NorthArc's business is about 70% single-mode, 30% multimode. There's also multi-core fiber (4-core, 7-core), used in 400G/800G high-density optical modules — low volume but high unit price, and also the hardest to splice.

### The splicing motion

Fusion splicing aligns the end faces of two fiber strands and fuses them together with an electric arc. The whole operation takes 90 seconds to 3 minutes and follows these steps:

1. Strip the coating. Use a stripper tool to strip 3 centimeters of coating off the end of each fiber, exposing the 125-micron cladding.
2. Clean. Wipe off residual coating debris with a lint-free wipe dipped in isopropyl alcohol.
3. Cleave the end face. Use a cleaver (a mechanical cleaving tool) to produce a perpendicular end face. Cleave angle must stay within 0.5 degrees — angle deviation directly degrades splice quality.
4. Load into the splicer. Place both fibers into the fusion splicer's V-groove, end faces facing each other.
5. Auto-alignment. The splicer's built-in camera system (CCD) detects core offset between the two fibers and uses motors to fine-tune alignment until X/Y offset is under 0.1 micron.
6. Prefusion. A brief low-energy arc burns off any minor burrs on the end faces.
7. Arc fuse. A high-energy arc (~12.5 mW, lasting about 1 second) fuses the two end faces together.
8. Estimate the loss. The splicer's LID (Loss Estimation by Deformation) algorithm estimates splice loss, in dB, based on the shape of the fused joint. This estimate is what's recorded as predicted_loss_db.
9. Protect the splice. Slide on a splice protector (a heat-shrink sleeve) and heat it to set.

If the predicted loss exceeds the threshold, the splicer prompts a retry, and the operator decides whether to re-cleave and re-splice or accept the current result. A splice gets a maximum of 3 attempts; if the third attempt still fails, it's logged as a reject.

Splice loss is the metric that determines whether a cable passes. NorthArc's internal SOP holds every splice to ≤ 0.05 dB. World-class performance for single-mode fiber is 0.02 dB, typical plant performance is 0.05 dB, and FTTH customers will accept up to 0.30 dB.

### Factors that affect splice loss

Roughly in order of importance:

| Factor | How it affects loss | Degree of plant control |
|------|---------|------------------|
| Core alignment error | A 0.5 μm offset can double the loss | High (equipment auto-aligns, but electrode wear destabilizes alignment) |
| Cleave angle | Beyond 0.5° increases scattering | High (depends on how worn the cleaver blade is) |
| Electrode condition | Aged electrodes produce an unstable arc, causing fusion temperature drift | High (proactive replacement strategy) |
| Fiber cladding diameter variance | An incoming-batch issue; deviation beyond ±0.5 μm makes alignment difficult | Medium (depends on supplier QC) |
| Ambient humidity | > 60% humidity makes end faces prone to moisture absorption | Medium (cleanroom control) |
| Operator skill | Stripping and cleaning technique affects residue | Medium (training + scheduling) |
| Multi-core fiber difficulty | Aligning multiple cores simultaneously increases difficulty exponentially | Medium (skill matching) |

Every one of these factors maps to one or more fields in the dataset, and your SQL will need to isolate each factor's contribution.

### Electrodes, the cheapest and most consequential part in the plant

Every fusion splicer holds a pair of tungsten electrodes, which generate the arc. A pair of electrodes lists for about $180, but has a limited lifespan (typically 1,500 to 2,500 splices), because the arc gradually vaporizes the tungsten — the surface pits over time and the electric field distribution stops being symmetric. Aged electrodes cause arc temperature drift, which directly drives splice loss up.

NorthArc's current electrode replacement strategy is reactive: wait until the splicer's self-diagnostic reports an "electrode condition warning" before replacing. The problem is that this alert threshold is set by the equipment manufacturer, and it typically doesn't fire until the electrode is already badly worn. Marcus suspects a meaningful share of the plant's rejects are actually a hidden consequence of over-worn electrodes. That's exactly what Q2 needs to answer.

---

## 8. Key Glossary

These terms come up repeatedly in the ER document and the SQL queries document.

**Splice Loss**: the optical power attenuation caused by a single fusion splice, measured in dB. 0.02 dB means 99.5% of the light passes through; 0.10 dB means 97.7% passes through. On long-haul datacenter links, splice loss accumulates across multiple splices, so the lower each individual splice loss, the better.

**dB** (Decibel): a logarithmic unit measuring optical power ratio. Rough conversions: 0.1 dB ≈ 2.3% power loss, 0.5 dB ≈ 10.9% loss, 1.0 dB ≈ 20.6% loss. All loss values in the dataset are positive numbers — the larger the number, the greater the loss.

**FTTH** (Fiber To The Home): the buildout model where operators run fiber all the way to a residential endpoint. Spec is comparatively loose — a splice on a drop cable segment can be accepted up to 0.30 dB.

**Hyperscale Datacenter**: operators like AWS, Google, and Meta running massive-scale datacenters. Internal fiber connection density is extremely high and spec is extremely tight, with single-splice loss typically required to be ≤ 0.05 dB.

**MTP / MPO**: Multi-fiber Push-On connectors, packing 8, 12, or 24 fibers into a single connector head — the most common form factor in datacenters.

**LC** / **SC** / **FC**: three single-fiber connector form factors. LC is the smallest and now the mainstream choice; SC is older but still in use; FC is used in industrial settings.

**Cleave Angle**: the deviation of the fiber end face from perpendicular to the fiber axis, measured in degrees. Standard is < 0.5°, excellent is < 0.3°.

**Cladding**: the outer glass layer of the fiber, standard diameter 125 microns.

**MFD** (Mode Field Diameter): the effective diameter of the light field inside single-mode fiber, standard around 10.4 microns. MFD varies slightly by fiber model, and splicing two fibers with mismatched MFD produces higher loss.

**Cleaver**: the mechanical cleaving tool. A single blade lasts roughly 24,000 cleaves.

**Electrode**: the pair of tungsten electrodes inside a fusion splicer that generate the arc. Lifespan is 1,500 to 2,500 splices.

**LID** (Loss Estimation by Deformation): the splicer's built-in splice-loss estimation algorithm. It estimates loss from the post-fusion deformation image rather than a true OTDR measurement, and typically deviates from actual loss by ±0.005 dB.

**OTDR** (Optical Time Domain Reflectometer): the instrument that actually measures splice loss directly, but it's expensive and slow, so it's typically used only for QA spot-checks, not on every splice.

**First-Pass Yield (FPY)**: the share of splices that succeed on the first attempt. NorthArc currently runs about 88%; industry-leading plants run about 95%.

**Reject Rate**: the share of splices that still fail after up to 3 attempts. Currently about 2.5%.

**Quality Grade**: NorthArc's internal four-tier splice classification. A = loss ≤ 0.02 dB, B = ≤ 0.05 dB, C = ≤ 0.08 dB, Reject = > 0.08 dB.

**Splice Attempt**: a single attempt at a splice. Each splice_record maps to 1 to 3 splice_attempt rows.

**Job**: a production batch corresponding to a sub-task of a customer PO. A job is completed by one operator on one piece of equipment and contains anywhere from a few dozen to a few hundred splices.

**SPC** (Statistical Process Control): using control charts to monitor key process parameters.

**AVL** (Approved Vendor List): a customer's list of approved suppliers. A single major quality incident can get you dropped from it.

**RMA** (Return Material Authorization): the approval number a customer must obtain before returning goods.

**SOP** (Standard Operating Procedure).

**BOM** (Bill of Materials). In this dataset, fiber_batch and consumable_price provide the BOM cost.

---

## 9. Key Metrics and Formulas

The metrics below recur throughout the dashboard and the SQL queries. Their definitions are pinned down here to keep downstream calculations consistent.

**First-Pass Yield (FPY)**

```
FPY = COUNT(splice_record WHERE attempt_count = 1 AND final_grade != 'Reject')
      / COUNT(splice_record)
```

This counts only records where attempt_count = 1 and the result is not a Reject — i.e., "passed on the first try." NorthArc's current FPY is about 88%.

**Reject Rate**

```
Reject Rate = COUNT(splice_record WHERE final_grade = 'Reject')
              / COUNT(splice_record)
```

This is the final reject rate (still failing after all 3 attempts). Currently about 2.5%.

**Cost Per Splice (CPS)**

```
CPS = SUM(splice_attempt.material_cost_usd + labor_cost_usd 
          + machine_cost_usd + consumable_cost_usd)
      / COUNT(DISTINCT splice_record.splice_id)
```

The full cost of every splice is allocated at the attempt level, then averaged by splice_record. Note the denominator is not the number of attempts — a splice that gets retried multiple times shouldn't have its unit cost cut in half.

**Rework Cost Per Splice**

```
Rework Cost = SUM(splice_attempt.material_cost_usd + labor_cost_usd 
                  + machine_cost_usd + consumable_cost_usd
                  WHERE attempt_number > 1)
              / COUNT(splice_record)
```

The full cost of the 2nd and 3rd attempts, spread across all splice_record rows. This is the headline number for Q1.

**Annualized Loss Per Cost Driver**

```
Annualized Loss(driver) = (incremental reject count + incremental retry count)
                          * unit cost
                          * (365 / number of days in the dataset)
```

Every Q (Q2 through Q8) uses this formula to estimate "if driver X were eliminated, how much would be saved per year." Unit cost is about $13 per reject (materials + labor + equipment depreciation + amortized customer-trust risk) and $4 per retry (mainly materials + time).

**Electrode Cost Per Splice**

```
Electrode Cost = electrode_pair_price_usd / electrode_lifetime_splices
```

Calculated as $180 / 2000 ≈ $0.09 per splice, and rolled into consumable_cost_usd.

**Quality Grade Distribution**

```
Grade Mix = COUNT(quality_grade = X) / COUNT(*)
            for X in (A, B, C, Reject)
```

Target distribution: A 75%, B 18%, C 4.5%, Reject 2.5%.

**AI Alert Compliance Rate**

```
Alert Compliance = COUNT(quality_alert WHERE outcome = 'resolved')
                   / COUNT(quality_alert WHERE outcome IS NOT NULL)
```

Currently ~75% resolved, ~15% ignored, ~10% escalated. Q6 needs to work out the downstream loss attributable to that ignored 15%.

**Equipment Electrode Count**

```
electrode_count_at_splice = COUNT(splice_attempt
                                  WHERE equipment_id = E
                                  AND attempt_ts BETWEEN last_replacement_ts AND splice_ts)
```

How many splices the current electrode pair has already performed as of a given splice. This is the primary breakdown dimension for Q2.

**Splice Loss Spec Compliance, By Customer**

```
Customer Spec Compliance = COUNT(final_loss_db <= order.loss_threshold_db)
                           / COUNT(*)
                           grouped by customer.segment
```

Judged against the actual spec on the customer order, rather than the internal 0.05 SOP threshold. This is the core measure for Q5.

Every metric here appears at least once in the SQL queries document; the 03 document will not redefine them.
