# Healthcare - OB Ward Scheduling SQL Query Reference

> Business context / company / industry / glossary: `01-healthcare_obstetrics_ward_scheduling_medium_business_context.md`
> Table structure / fields / DDL: `02-healthcare_obstetrics_ward_scheduling_medium_er_document.md`
> All queries are compatible with **SQLite 3.x** (uses `julianday()` for date arithmetic).
> Reference "current time" (`REFERENCE_DATE`) = `2026-02-13 08:00` (Demo anchor). Everywhere "today" is needed, this **literal date** is used, never `DATE('now')`, so results are reproducible.
> Database file: `healthcare_obstetrics_ward_scheduling_medium.sqlite`

---

## Overview

### This Is Not a BI Query Set — It's a POC Acceptance Checklist

This document lists **20 business-problem-oriented SQL queries**. The goal is **not** to cover generic BI scenarios; it's to answer the **specific business questions the vendor (IT consultancy) needs to prove to the client (OB hospital chain) on POC demo day**.

| Dimension | This dataset | Typical BI query set |
|------|---------|--------------|
| Data scale | ~500 rows, POC sandbox | Millions to billions |
| User role | Front-line Charge Nurse + Attending + Ward Manager (1–2 people) | Executive + analyst + data scientist |
| When queried | **Live, during operations** (handoff, bed-finding, scheduling surgery) | **Retrospective analysis** (this quarter's trend, KPIs) |
| Purpose | Replace the nurse's manual lookups in the legacy CMS | Decision support |
| Tolerance for error | **Extremely low** — missing one high-risk patient is a sentinel event | Moderate — directionally correct is fine |

### How to Read This Document

This document is written for a **new data intern at Halcyon**: you've already read `01-..._business_context.md` (know the company, industry, 5 business problems) and `02-..._er_document.md` (know the schema). Now your manager drops these 20 queries on you and says "walk through them this week." Read them like this:

1. **Each query is a project handoff**, following a fixed five-section template — reading them as such will teach you how a real analyst thinks about a problem:
   - **Business background** — who's asking, why, what decision the answer informs, why it's urgent (mapped to business problems P1–P5).
   - **Category / Difficulty / Business role** — three tags that tell you what technique this SQL uses, how hard it is, and which job title it serves.
   - **Approach** — *before* showing the SQL, this explains which tables are touched, why this particular join / aggregation / window function is used, what one result row represents, and what traps to watch (fan-out, NULL, case sensitivity). This section is the most important teaching content in the document.
   - **SQL** — runnable code. Dates are literal `'2026-02-13'`.
   - **Expected result + business takeaway** — what the result looks like (row count, column meaning, key magnitudes), and **what to do next** once you have the number (running the query is the start of analysis, not the end).

2. **Each query traces back to a business problem.** A "Business problem → query" mapping table is at the end. If you can't see which business problem a query corresponds to, go back to the `01` document.

3. **SQL is for reading and learning, not just running.** Focus on the "why this way" in the `Approach` section — for example, why is it `LEFT JOIN` and not `INNER JOIN`, why does census exclude `discharged`, why is LOS measured from `delivery_time`.

4. **On demo day, the nurse won't see SQL.** She'll just ask naturally ("Any beds open in labor?"), and the AI agent calls the corresponding query behind the scenes. The value of this document is so the client's IT team can **audit after the fact**: every AI answer maps to real data in the schema.

### Queries Mapped to Demo Scenarios

On POC demo day, the vendor walks the client's front-line nurses through **5 demo scenarios**. Each scenario corresponds to 2–5 SQL queries. The AI agent doesn't show SQL directly but **depends on** these queries as tool calls behind the scenes to answer the nurse's natural-language questions.

| Demo scenario | Queries involved |
|----------|---------|
| 1️⃣ Shift Handover | Q1, Q5, Q6, Q14 |
| 2️⃣ Room Availability | Q2, Q10, Q18 |
| 3️⃣ Length-of-Stay prediction | Q9, Q13, Q17 |
| 4️⃣ High-Risk Alert | Q3, Q7, Q16 |
| 5️⃣ Order Scheduling | Q4, Q14, Q19 |
| (Cross-cutting analysis) | Q8, Q11, Q12, Q15, Q20 |

### Query Index

| # | Title | Business role | Category | Difficulty | Demo scenario |
|---|------|---------|------|------|----------|
| 1 | Current ward population by status | Charge Nurse | Aggregation | Basic | 1 |
| 2 | Bed availability by room type | Charge Nurse | Join | Basic | 2 |
| 3 | Current high-risk inpatient roster | Attending Physician | Join | Intermediate | 4 |
| 4 | Scheduled procedures in the next 48 hours | OR Coordinator | Join | Basic | 5 |
| 5 | Patients close to delivery (labor progress) | Charge Nurse | Window Function | Intermediate | 1, 2 |
| 6 | Unacknowledged alerts summary | Charge Nurse | Join | Basic | 1, 4 |
| 7 | High-risk patient BP trend | Attending Physician | Window Function | Advanced | 4 |
| 8 | Current provider workload | Department Manager | Aggregation | Intermediate | Cross-cutting |
| 9 | Average LOS by delivery method | Quality Analyst | Aggregation | Intermediate | 3 |
| 10 | Bed utilization by room type | Operations Manager | Subquery | Intermediate | 2 |
| 11 | Patients due within a week | Scheduling Coordinator | Date Analysis | Basic | Cross-cutting |
| 12 | Insurance mix among current inpatients | Finance Analyst | Aggregation | Basic | Cross-cutting |
| 13 | Labor duration by parity + delivery method | Quality Analyst | CTE | Advanced | 3 |
| 14 | Shift coverage report | Nurse Manager | Join | Intermediate | 1, 5 |
| 15 | Complications distribution | Clinical Director | Aggregation | Intermediate | Cross-cutting |
| 16 | Patients with abnormal recent vital signs | Clinical Nurse | Window + Filter | Intermediate | 4 |
| 17 | LOS prediction accuracy (predicted vs actual) | Quality Analyst | CTE | Advanced | 3 |
| 18 | Multiple-gestation tracking + NICU capacity | MFM Specialist | Join + Subquery | Intermediate | 2, 4 |
| 19 | Completion rate by order type | Operations Analyst | Aggregation | Intermediate | 5 |
| 20 | Admission distribution by day of week × shift | Capacity Planner | Date Analysis | Intermediate | Cross-cutting |

---

## Queries

### Q1: Current Ward Population by Status

**Business background:**
**The opening move of Demo scenario 1 (Shift Handover).** At 7 AM, night → day shift change, the incoming charge nurse walks up to the nurses' station and her first question is: "*How many patients do we have right now, and what stage is each one in?*" This query is **the opening line of the entire POC demo** — the AI agent must return accurate headcounts within 1 second, because they are the baseline for every downstream scheduling action. Missing even one status leaves the incoming nurse blindsided.

**Category:** Aggregation
**Difficulty:** Basic
**Business Role:** Charge Nurse

**Approach:**
Only the `admission` table is needed, no joins. Group by `status` and `COUNT(*)`. The key piece is `WHERE status != 'discharged'` to exclude discharged patients (census only counts patients in house). The `percentage` column uses the "aggregate + window" combo `SUM(COUNT(*)) OVER ()` to get the global total as the denominator, computing each status's share in a single GROUP BY — this is a pattern SQLite supports. Finally, `CASE` orders the statuses by clinical progression (admitted → … → ready_for_discharge) rather than alphabetically, so it reads naturally to a nurse. One row = one in-house status and its count.

```sql
-- Summarize current inpatient count by admission status
SELECT
    status,
    COUNT(*) AS patient_count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 1) AS percentage
FROM admission
WHERE status != 'discharged'
GROUP BY status
ORDER BY
    CASE status
        WHEN 'admitted' THEN 1
        WHEN 'in_labor' THEN 2
        WHEN 'delivered' THEN 3
        WHEN 'postpartum' THEN 4
        WHEN 'ready_for_discharge' THEN 5
    END;
```

**Expected result:**
Returns 5 rows (skipping `discharged`; this dataset also has 1 discharged row that is excluded from the count), one status with its count per row. This dataset's distribution: 4 admitted, 4 in_labor, 2 delivered, 3 postpartum, 2 ready_for_discharge (15 active total). The `percentage` column gives the nurse a quick read on labor bottlenecks — e.g., a high in_labor share means the OR will be busy in the next 2–4 hours.

---

### Q2: Bed Availability by Room Type

**Business background:**
**The core query of Demo scenario 2 (Room Availability).** The ER just called: "I have a patient with 5-minute contractions, sending her over now — any labor rooms open?" The charge nurse needs to answer **within 3 seconds**. The legacy CMS only shows totals; it doesn't distinguish `cleaning` (still being cleaned, not usable) from `available` (truly usable). The POC must prove the AI can correctly **distinguish all 4 statuses** — this is the very first pain point the client's front-line nurses called out.

**Category:** Join
**Difficulty:** Basic
**Business Role:** Charge Nurse

**Approach:**
Need to join `room` to `bed` (`JOIN bed ON room.room_id = b.room_id`) because bed status lives in `bed` and room type lives in `room`. Group by `room_type`, then use "conditional COUNT" `COUNT(CASE WHEN b.status = 'xxx' THEN 1 END)` to pivot the 4 bed statuses into 4 columns — this is a common way to do row-to-column pivoting without a subquery. **Intentionally do not** collapse `cleaning` / `maintenance` into "unavailable" because the charge nurse needs to see cleaning separately (usable again in ~30 minutes). An INNER JOIN is fine here — every bed has a room, no rows are lost. One row = the full bed-status picture for one room type.

```sql
-- Bed status distribution per room type
SELECT
    r.room_type,
    COUNT(CASE WHEN b.status = 'available' THEN 1 END) AS available_beds,
    COUNT(CASE WHEN b.status = 'occupied' THEN 1 END) AS occupied_beds,
    COUNT(CASE WHEN b.status = 'cleaning' THEN 1 END) AS cleaning_beds,
    COUNT(CASE WHEN b.status = 'maintenance' THEN 1 END) AS maintenance_beds,
    COUNT(*) AS total_beds
FROM room r
JOIN bed b ON r.room_id = b.room_id
GROUP BY r.room_type
ORDER BY r.room_type;
```

**Expected result:**
5 rows, one per room_type (`labor` / `delivery` / `postpartum` / `nicu` / `triage`). On demo day, labor rooms are usually full; you check `cleaning_beds` to see if any frees up in ~30 minutes. `postpartum` typically has spare capacity for patients moving over from delivery.

> Note: this query **intentionally** does not collapse `cleaning + maintenance` into "unavailable" — the charge nurse needs to see the "one bed will be usable in 20 minutes" signal to schedule.

---

### Q3: Current High-Risk Inpatient Roster

**Business background:**
**The opening move of Demo scenario 4 (High-Risk Alert).** Before morning rounds, the attending wants a list of patients who **must be the focus today**. The high-risk classification comes from `ob_profile.risk_level = 'high'`, with triggers including: AMA / multiples / preterm / prior C-section with planned VBAC / multiple complications. This query feeds the attending's rounds-routing plan — sort by ascending gestational weeks (preterm-risk first), minimizing back-and-forth.

**Category:** Join
**Difficulty:** Intermediate
**Business Role:** Attending Physician

**Approach:**
Start from `admission`, INNER JOIN `patient` and `ob_profile` for demographics and clinical info (both always exist), then **LEFT JOIN** `bed` and `room` for location. Location uses LEFT because some inpatients may have a null `current_bed_id` (e.g., just admitted to triage with no bed yet); INNER would drop them — and dropping a high-risk patient is a sentinel event. Filter on `status != 'discharged'` (in-house only) + `risk_level = 'high'`. Sort by `gestational_weeks ASC` so the earliest gestation (highest preterm risk) is at the top, helping the attending plan rounds. One row = one current high-risk inpatient.

```sql
-- All current high-risk inpatients with location and complications
SELECT
    p.name AS patient_name,
    p.age,
    ob.risk_level,
    ob.gestational_weeks,
    ob.fetus_count,
    ob.complications,
    a.status AS current_status,
    r.room_number,
    b.bed_label
FROM admission a
JOIN patient p ON a.patient_id = p.patient_id
JOIN ob_profile ob ON a.ob_id = ob.ob_id
LEFT JOIN bed b ON a.current_bed_id = b.bed_id
LEFT JOIN room r ON b.room_id = r.room_id
WHERE a.status != 'discharged'
    AND ob.risk_level = 'high'
ORDER BY ob.gestational_weeks ASC;
```

**Expected result:**
~4–6 rows (idx2 / idx3 / idx4 are **deterministically** marked high-risk, with a few more from random sampling — this dataset has 6 actual high-risk admissions). Sorted by `gestational_weeks ASC`, the **first row is a 34.2-week twin** (idx4, with preterm_risk), followed by two rising-BP high-risk patients (with Preeclampsia / IUGR, etc.). The `complications` column is a JSON array — the attending sees specific complication types at a glance and can decide whether to consult MFM (Maternal-Fetal Medicine).

---

### Q4: Scheduled Procedures in the Next 48 Hours

**Business background:**
**The core of Demo scenario 5 (Order Scheduling).** The OR (Operating Room) coordinator schedules today + tomorrow's procedures each morning at 7 AM. She needs to see: what time, which patient, which OR, who's the surgeon, who's the anesthesiologist. This query feeds her morning briefing directly, and **the POC's future scope adds automatic conflict detection** (e.g., two C-sections double-booked into the same delivery room at the same time).

**Category:** Join
**Difficulty:** Basic
**Business Role:** OR Coordinator

**Approach:**
With `medical_order` as the main table, JOIN `admission` → `patient` for the patient name, JOIN `provider` for surgeon / owner, then **LEFT JOIN** `room`. Room uses LEFT because some orders (like induction) aren't tied to an OR — `assigned_room_id` is NULL, and INNER would drop them. The time window uses two **literal** boundaries `scheduled_time >= '2026-02-13 08:00:00' AND < '2026-02-15 08:00:00'` to bracket "next 48 hours" — never `DATE('now')`, to keep the demo reproducible. `status = 'scheduled'` includes only the ones not yet executed. One row = one planned procedure.

```sql
-- Scheduled orders (C-section / induction / etc.) in the next 48 hours
SELECT
    o.scheduled_time,
    o.order_type,
    o.priority,
    p.name AS patient_name,
    r.room_number,
    prov.name AS assigned_provider,
    o.notes
FROM medical_order o
JOIN admission a ON o.admission_id = a.admission_id
JOIN patient p ON a.patient_id = p.patient_id
LEFT JOIN room r ON o.assigned_room_id = r.room_id
JOIN provider prov ON o.assigned_provider_id = prov.provider_id
WHERE o.status = 'scheduled'
    AND o.scheduled_time >= datetime('2026-02-13 08:00:00')
    AND o.scheduled_time < datetime('2026-02-15 08:00:00')
ORDER BY o.scheduled_time;
```

**Expected result:**
~2 rows (tomorrow 09:00 c_section + tomorrow 14:00 induction, deliberately planted). c_section must have `assigned_room_id` pointing at a delivery-type room; induction is typically done in the labor room on the spot, so it can be NULL. Priority defaults to `routine`; the POC could extend to `emergency` (handle on arrival) later.

> Note: in a real clinical setting `datetime('now')` is dynamic, but this POC uses a fixed reference time for demo reproducibility.

---

### Q5: Patients Close to Delivery (Labor Progress)

**Business background:**
**Used by Demo scenario 1 (handoff) + scenario 2 (Room Availability).** The charge nurse wants to predict: **which labor rooms will free up in the next 2 hours?** Clinical experience: dilation ≥ 8 cm + ruptured membranes ≈ delivery within 1–2 hours. This query takes each in_labor patient's **latest** labor_progress, sorted by dilation descending. The AI agent uses the result to reason: "Emily is at 8 cm now, her L-202 should free up around 10:00 for that new ER patient."

**Category:** Window Function
**Difficulty:** Intermediate
**Business Role:** Charge Nurse

**Approach:**
The trick: each patient has multiple `labor_progress` rows, and we want the latest. Standard idiom: use the window function `ROW_NUMBER() OVER (PARTITION BY admission_id ORDER BY recorded_at DESC)` to number rows per patient most-recent-first, then `WHERE rn = 1` outer filter selects the latest. After getting the latest exam, JOIN back to `admission` / `patient`, then LEFT JOIN `bed` / `room` for location (bed can be null). Keep only `status IN ('admitted','in_labor')` (still pregnant), sort by `cervical_dilation_cm DESC` — largest dilation = closest to delivery, on top. CTE + window is clearer and faster than correlated subqueries. One row = one laboring patient's latest progress.

```sql
-- Each admission's latest labor progress, sorted by dilation desc
WITH latest_progress AS (
    SELECT
        lp.*,
        ROW_NUMBER() OVER (
            PARTITION BY lp.admission_id
            ORDER BY lp.recorded_at DESC
        ) AS rn
    FROM labor_progress lp
)
SELECT
    p.name AS patient_name,
    r.room_number,
    lp.cervical_dilation_cm,
    lp.station,
    lp.membrane_status,
    lp.recorded_at AS last_check,
    a.status
FROM latest_progress lp
JOIN admission a ON lp.admission_id = a.admission_id
JOIN patient p ON a.patient_id = p.patient_id
LEFT JOIN bed b ON a.current_bed_id = b.bed_id
LEFT JOIN room r ON b.room_id = r.room_id
WHERE lp.rn = 1
    AND a.status IN ('admitted', 'in_labor')
ORDER BY lp.cervical_dilation_cm DESC;
```

**Expected result:**
~5–8 rows. The top row should be a patient at ~8 cm dilation + ruptured (delivery in 1–2 hours); the bottom rows are admitted patients at 1–2 cm + intact (no delivery for 8–12 hours).

---

### Q6: Unacknowledged Alerts Summary

**Business background:**
**The most serious step in Demo scenario 1 handoff.** The outgoing nurse must hand off every **unacknowledged alert** to the incoming nurse — nothing can fall through the cracks. Each alert represents an event that **may affect maternal/fetal safety**; critical-severity alerts require immediate page to the attending. At this demo moment the dataset has 2 unacknowledged high_bp warnings (on idx2 / idx3) and 1 preterm_risk that's already been acknowledged — this query should return only the first two.

**Category:** Join
**Difficulty:** Basic
**Business Role:** Charge Nurse

**Approach:**
With `alert` as the main table, JOIN `admission` / `patient` for the patient, LEFT JOIN `bed` / `room` for location (bed can be null). Core filter is `acknowledged = 0` — SQLite stores booleans as 0/1, so write `= 0` not `= false`. Sort with `CASE al.severity WHEN 'critical' THEN 1 ELSE 2 END` to push critical to the top (severity is a string, so it doesn't sort "critical-first" naturally), then within the same severity sort by `triggered_at DESC`, newest first. One row = one alert awaiting nurse acknowledgement. This snapshot has only 2 unacknowledged high_bp; the acknowledged preterm_risk doesn't appear.

```sql
-- All unacknowledged alerts + patient location + severity ordering
SELECT
    al.alert_type,
    al.severity,
    al.message,
    al.triggered_at,
    p.name AS patient_name,
    r.room_number,
    b.bed_label,
    a.status AS patient_status
FROM alert al
JOIN admission a ON al.admission_id = a.admission_id
JOIN patient p ON a.patient_id = p.patient_id
LEFT JOIN bed b ON a.current_bed_id = b.bed_id
LEFT JOIN room r ON b.room_id = r.room_id
WHERE al.acknowledged = 0
ORDER BY
    CASE al.severity WHEN 'critical' THEN 1 ELSE 2 END,
    al.triggered_at DESC;
```

**Expected result:**
2 rows (carefully controlled in this dataset), both high_bp warning. The message field reads narratively, e.g., "Blood pressure trending upward: 125 → 131 → 137 → 143 mmHg systolic" — directly readable to the nurse without needing to re-query vital_sign. If a critical row ever shows up, the POC's next iteration can layer in an "auto-page attending" action.

---

### Q7: High-Risk Patient BP Trend

**Business background:**
**Demo scenario 4's proof that "the AI is smarter than a single-threshold rule."** The legacy CMS only fires when BP ≥ 140 on a single reading, **missing the gradual upward trend** — an early sign of pregnancy-induced hypertension (PIH/Preeclampsia). The POC must prove the AI can recognize a **continuous upward** pattern like "125 → 131 → 137 → 143" even when no individual reading would qualify as critical. This query uses `LAG()` to compute the delta between consecutive readings, showing the attending the full trajectory.

**Category:** Window Function
**Difficulty:** Advanced
**Business Role:** Attending Physician

**Approach:**
This is a "trend detection" query — the trick is putting each patient's consecutive BP readings on the same row so you can subtract. Use the window function `LAG(bp_systolic) OVER (PARTITION BY admission_id ORDER BY recorded_at)` to grab the "previous" reading; outer-level `bp_systolic - prev_systolic` gives the change. The CTE `bp_readings` precomputes the LAG; the outer query joins to patient / room and uses `CASE` to attach threshold labels (CRITICAL / WARNING / Normal-but-watch). `WHERE bp_systolic >= 130 OR bp_diastolic >= 85` filters obvious normals, focusing on trajectories worth watching. One row = one BP reading of one patient + the delta vs the previous reading. Consecutive positive `systolic_change` = upward trend — exactly what a single-threshold approach can't see.

```sql
-- BP time series + delta from previous + threshold classification
WITH bp_readings AS (
    SELECT
        vs.admission_id,
        vs.recorded_at,
        vs.bp_systolic,
        vs.bp_diastolic,
        LAG(vs.bp_systolic) OVER (
            PARTITION BY vs.admission_id ORDER BY vs.recorded_at
        ) AS prev_systolic,
        LAG(vs.bp_diastolic) OVER (
            PARTITION BY vs.admission_id ORDER BY vs.recorded_at
        ) AS prev_diastolic
    FROM vital_sign vs
)
SELECT
    p.name AS patient_name,
    r.room_number,
    br.recorded_at,
    br.bp_systolic,
    br.bp_diastolic,
    br.bp_systolic - br.prev_systolic AS systolic_change,
    CASE
        WHEN br.bp_systolic >= 160 THEN 'CRITICAL'
        WHEN br.bp_systolic >= 140 THEN 'WARNING'
        ELSE 'Normal-but-watch'
    END AS bp_status
FROM bp_readings br
JOIN admission a ON br.admission_id = a.admission_id
JOIN patient p ON a.patient_id = p.patient_id
LEFT JOIN bed b ON a.current_bed_id = b.bed_id
LEFT JOIN room r ON b.room_id = r.room_id
WHERE br.bp_systolic >= 130 OR br.bp_diastolic >= 85
ORDER BY p.name, br.recorded_at;
```

**Expected result:**
~6–10 rows (all the vitals for the planted high-BP patients). Consecutive positive `systolic_change` = upward trend — the POC reviewers will be staring at this column to verify the AI catches it.

---

### Q8: Current Provider Workload

**Business background:**
**A cross-cutting support query.** The department manager wants to see at the morning huddle: which attending / nurse has the most patients? Is anyone overloaded, or sitting underutilized? The POC validates that the AI can correctly aggregate across both `attending_provider_id` and `primary_nurse_id`.

**Category:** Aggregation
**Difficulty:** Intermediate
**Business Role:** Department Manager

**Approach:**
A provider can be either `attending_provider_id` or `primary_nurse_id`, so the JOIN condition uses `OR` to count both roles. Start from `provider`, **LEFT JOIN** `admission` (some providers currently have no patients; INNER would make them vanish), then LEFT JOIN `ob_profile` for risk_level. `WHERE is_active = 1 AND (a.status IS NULL OR a.status != 'discharged')` — note that for unmatched LEFT JOIN rows `status` is NULL, so you must explicitly let `IS NULL` through, otherwise `!= 'discharged'` evaluates to false on NULL and erases idle providers. `COUNT(DISTINCT a.admission_id)` prevents double counting from the OR join. One row = one active provider and their current load.

```sql
-- Each provider's current patient count + how many are high-risk
SELECT
    prov.name AS provider_name,
    prov.role,
    COUNT(DISTINCT a.admission_id) AS current_patients,
    SUM(CASE WHEN ob.risk_level = 'high' THEN 1 ELSE 0 END) AS high_risk_patients
FROM provider prov
LEFT JOIN admission a ON (
    a.attending_provider_id = prov.provider_id
    OR a.primary_nurse_id = prov.provider_id
)
LEFT JOIN ob_profile ob ON a.ob_id = ob.ob_id
WHERE prov.is_active = 1
    AND (a.status IS NULL OR a.status != 'discharged')
GROUP BY prov.provider_id, prov.name, prov.role
ORDER BY prov.role, current_patients DESC;
```

**Expected result:**
~15 rows (all active providers). Attendings typically have 3–4 patients each; nurses 2–3 each. If one nurse has 4 high_risk patients while another has only 1 low-risk, the manager will rebalance.

---

### Q9: Average LOS by Delivery Method

**Business background:**
**Demo scenario 3 (LOS prediction) baseline.** Clinical experience for LOS: vaginal 24–48h, C-section 72–96h. The Quality Analyst uses this query to **validate that the AI model's predictions land in the reasonable range**. If the AI predicts 40 hours for a C-section, the model has failed to detect `delivery_method = c_section`.

**Category:** Aggregation
**Difficulty:** Intermediate
**Business Role:** Quality Analyst

**Approach:**
Only the `admission` table. Group by `delivery_method_actual` — use the **actual** method, not the planned one, to avoid mis-attributing "planned vaginal turned emergency C-section" to vaginal. `avg_predicted` simply averages `predicted_los_hours`; `avg_actual` uses `(julianday(actual_discharge_time) - julianday(delivery_time)) * 24` for actual postpartum hours, but only discharged patients have `actual_discharge_time`, so wrap it in `CASE WHEN ... IS NOT NULL` (not-yet-discharged don't contribute to the actual mean). **Unified convention**: predicted and actual are both measured from `delivery_time`, so postpartum LOS is comparable. One row = one actual delivery method's LOS comparison.

```sql
-- Compare "predicted postpartum LOS" vs "actual postpartum LOS" by actual delivery method
-- Unified convention: both measured from delivery_time (predicted_los_hours is postpartum)
SELECT
    a.delivery_method_actual AS delivery_method,
    COUNT(*) AS delivered_count,
    ROUND(AVG(a.predicted_los_hours), 1) AS avg_predicted_postpartum_los_hours,
    ROUND(AVG(
        CASE WHEN a.actual_discharge_time IS NOT NULL
            THEN (julianday(a.actual_discharge_time) - julianday(a.delivery_time)) * 24
        END
    ), 1) AS avg_actual_postpartum_los_hours,
    SUM(CASE WHEN a.actual_discharge_time IS NOT NULL THEN 1 ELSE 0 END) AS discharged_count
FROM admission a
WHERE a.delivery_method_actual IS NOT NULL
GROUP BY a.delivery_method_actual
ORDER BY avg_predicted_postpartum_los_hours DESC;
```

**Expected result:**
~2 rows (actual delivery method is only `vaginal` / `c_section` — VBAC is a *planned* category and lands as vaginal or C-section in reality, **never** appearing as actual). c_section's predicted postpartum LOS (72–96h) is clearly longer than vaginal (24–48h). `avg_actual_postpartum_los_hours` has values only for **discharged** admissions (this snapshot has 1 discharged c_section, actual postpartum LOS ≈ 84h, close to the prediction). **The convention is now unified on postpartum LOS (measured from delivery)** — no more mixing "pre-delivery in-house time" into the mean, and no more comparing "total stay" against "postpartum prediction."

---

### Q10: Bed Utilization by Room Type

**Business background:**
**An extension supporting Demo scenario 2.** The Operations Manager cares about structural questions: is the labor room running > 85% occupied long-term (capacity bottleneck, time to add beds)? Is postpartum running < 60% (over-provisioned)? The POC demonstrates the AI can produce operations-level KPIs from a single data source.

**Category:** Subquery / Aggregation
**Difficulty:** Intermediate
**Business Role:** Operations Manager

**Approach:**
Same source as Q2 — start from `bed JOIN room` — but compute "rates" here. `occupied_beds` is a conditional sum `SUM(CASE WHEN b.status='occupied' THEN 1 ELSE 0 END)`, divided by `COUNT(*)` gives `utilization_pct` — multiply by `100.0` (with decimal point) to force floating-point division, otherwise SQLite integer division truncates to 0. `available_soon` counts `available` + `cleaning` together (cleaning is usable in ~30 min) — a practical aggregate for the charge nurse. Sort by `utilization_pct DESC` so the tightest room type (usually labor) is on top, exposing capacity bottlenecks. One row = one room type's utilization picture.

```sql
-- Each room type's occupancy + soon-available count (including cleaning)
SELECT
    r.room_type,
    COUNT(*) AS total_beds,
    SUM(CASE WHEN b.status = 'occupied' THEN 1 ELSE 0 END) AS occupied_beds,
    ROUND(
        SUM(CASE WHEN b.status = 'occupied' THEN 1 ELSE 0 END) * 100.0 / COUNT(*),
        1
    ) AS utilization_pct,
    SUM(CASE WHEN b.status IN ('available', 'cleaning') THEN 1 ELSE 0 END) AS available_soon
FROM bed b
JOIN room r ON b.room_id = r.room_id
GROUP BY r.room_type
ORDER BY utilization_pct DESC;
```

**Expected result:**
5 rows; labor type typically has the highest utilization_pct (~80–100%), NICU usually low (~25%) since this dataset has few preterm scenarios. `available_soon` counts cleaning — this is the "how many beds are usable in 30 minutes" number the charge nurse cares about.

---

### Q11: Patients Due Within a Week

**Business background:**
**The Scheduling Coordinator's appointment view.** OB differs from clinic — mothers don't all come "when due"; some are **scheduled for induction / C-section**, others go into spontaneous labor. The scheduling coordinator takes this list and calls each one: "Your induction is booked for the 9th at 9 AM, confirmed?" High-risk patients also get a dedicated bed reserved.

**Category:** Date Analysis
**Difficulty:** Basic
**Business Role:** Scheduling Coordinator

**Approach:**
Start from `patient JOIN ob_profile` for the EDD; the trick is "excluding patients already admitted." Use **LEFT JOIN admission ... AND a.status != 'discharged'** then `WHERE a.admission_id IS NULL` — this is the classic "anti-join" pattern, keeping only patients with no in-house record. Note the `status != 'discharged'` condition must live in the `ON` clause, not `WHERE`; otherwise the LEFT JOIN degrades to INNER JOIN and the anti-join breaks. The date window uses `edd BETWEEN '2026-02-13' AND date('2026-02-13','+7 days')`; `days_until_due` is the `julianday` delta. One row = one patient due within a week and not yet admitted.

```sql
-- EDD within next 7 days, not yet admitted
SELECT
    p.name AS patient_name,
    p.phone,
    ob.edd AS due_date,
    ob.gestational_weeks,
    ob.planned_delivery_method,
    ob.risk_level,
    ob.fetus_count,
    ROUND(julianday(ob.edd) - julianday('2026-02-13'), 1) AS days_until_due
FROM patient p
JOIN ob_profile ob ON p.patient_id = ob.patient_id
LEFT JOIN admission a ON p.patient_id = a.patient_id AND a.status != 'discharged'
WHERE a.admission_id IS NULL
    AND ob.edd BETWEEN date('2026-02-13') AND date('2026-02-13', '+7 days')
ORDER BY ob.edd;
```

**Expected result:**
~12–14 rows (about 13 in actual measurement). `edd` is deterministically derived from `gestational_weeks`; patients at ~39–40 weeks have EDD falling within the next 7 days, so hits are plentiful — minus the currently-admitted (filtered out via `a.admission_id IS NULL`). Patients with EDD ≤ 3 days are "high priority" — they can go into labor any moment, scheduling needs to reserve a bed. high-risk + planned c_section must have OR time pre-confirmed.

---

### Q12: Insurance Mix Among Current Inpatients

**Business background:**
**The Finance Analyst's payer-mix view.** US healthcare is sensitive to **insurance type**: Medicaid has longer reimbursement cycles but high volume; commercial has higher per-encounter reimbursement but requires more detailed documentation; self_pay requires up-front deposits. This query tells Finance "roughly what the weekend's bill structure will look like." Attendings might also use it on demo day — Medicaid patients often have different prenatal visit cadence.

**Category:** Aggregation
**Difficulty:** Basic
**Business Role:** Finance Analyst

**Approach:**
Join `admission` with `patient` (for insurance) and `ob_profile` (for risk), in-house only (`status != 'discharged'`). Group by `insurance_type`, `COUNT(*)` for patients, window `SUM(COUNT(*)) OVER ()` for the denominator to compute share (same idiom as Q1). `high_risk_count` is a conditional sum to also report the high-risk subset within each insurance type. **Case-sensitivity trap**: `insurance_type` value `Medicaid` is capitalized (US government program proper noun); SQLite comparison is case-sensitive — writing `'medicaid'` will miss rows. One row = one insurance type's in-house composition.

```sql
-- Current inpatients by insurance_type + high-risk count
SELECT
    p.insurance_type,
    COUNT(*) AS patient_count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 1) AS percentage,
    SUM(CASE WHEN ob.risk_level = 'high' THEN 1 ELSE 0 END) AS high_risk_count
FROM admission a
JOIN patient p ON a.patient_id = p.patient_id
JOIN ob_profile ob ON a.ob_id = ob.ob_id
WHERE a.status != 'discharged'
GROUP BY p.insurance_type
ORDER BY patient_count DESC;
```

**Expected result:**
3 rows (`commercial` / `Medicaid` / `self_pay`). The in-house ratio is close to the total patient pool (~55/35/10). If `high_risk_count` is unusually high in Medicaid, Finance will talk to Clinical about whether additional case-management resources are needed.

---

### Q13: Labor Duration by Parity + Delivery Method

**Business background:**
**The Quality Analyst's clinical efficiency metric.** Classic clinical knowledge: **first-time mothers (P0)** average 12–18h of labor; **multiparous (P≥1)** average 6–8h. If a period's data deviates significantly, the clinical pathway may be off (e.g., too-early induction actually prolongs labor). The POC uses this query to show the AI can do **multi-dimensional grouped aggregations** — both para and planned_delivery_method.

**Category:** CTE
**Difficulty:** Advanced
**Business Role:** Quality Analyst

**Approach:**
First, the CTE `labor_times` computes each admission's labor span: `MIN(lp.recorded_at)` as labor start, `delivery_time` as end. The **INNER JOIN labor_progress** means only deliveries that actually had cervical exam records are counted (pure planned C-sections that never entered labor are excluded — an intentional design choice, since labor duration only makes sense for "actual labor"). The outer query groups by (`para = 0` first-time / else multiparous) × `delivery_method_actual`, computing AVG / MIN / MAX of labor hours via `julianday` delta × 24. One row = one (parity × delivery method) combination. Note that under small-sample + scenario-driven data, the textbook first/multipara gap will not reproduce; this query's value is in demonstrating multi-dimensional aggregation.

```sql
-- Labor duration for delivered admissions (first labor_progress → delivery_time)
-- Grouped by (first-time/experienced) × actual delivery method
WITH labor_times AS (
    SELECT
        a.admission_id,
        MIN(lp.recorded_at) AS labor_start,
        a.delivery_time,
        ob.para,
        a.delivery_method_actual
    FROM admission a
    JOIN labor_progress lp ON a.admission_id = lp.admission_id
    JOIN ob_profile ob ON a.ob_id = ob.ob_id
    WHERE a.delivery_time IS NOT NULL
    GROUP BY a.admission_id
)
SELECT
    CASE WHEN lt.para = 0 THEN 'First-time mom'
         ELSE 'Experienced mom' END AS parity,
    lt.delivery_method_actual,
    COUNT(*) AS deliveries,
    ROUND(AVG((julianday(lt.delivery_time) - julianday(lt.labor_start)) * 24), 1) AS avg_labor_hours,
    ROUND(MIN((julianday(lt.delivery_time) - julianday(lt.labor_start)) * 24), 1) AS min_labor_hours,
    ROUND(MAX((julianday(lt.delivery_time) - julianday(lt.labor_start)) * 24), 1) AS max_labor_hours
FROM labor_times lt
GROUP BY
    CASE WHEN lt.para = 0 THEN 'First-time mom'
         ELSE 'Experienced mom' END,
    lt.delivery_method_actual;
```

**Expected result:**
~3–5 rows. Measured by **actual** delivery method (`delivery_method_actual`) rather than planned, to avoid mis-attributing "planned vaginal turned emergency C-section" to vaginal.

> ⚠️ **About the labor-duration magnitudes:** the "first-time 12–18h, multiparous 6–8h" cited in the business background above is a **real clinical norm**, but in this POC labor span = `delivery_time − MIN(recorded_at)`, and these two timestamps are determined by each admission's **scenario parameters** (`hours_ago` / `delivered_hours_ago`), **independent of `para`**. So in this ~500-row sandbox, every group lands in ~5–8h and **will not** reproduce the textbook first/multipara gap. This is the inevitable result of a **small-sample + scenario-driven** setup, not a query bug — the query's value is in demonstrating that the **schema supports para × delivery_method multi-dimensional aggregation**; the statistical pattern will appear once it's plugged into a real EMR.

> Note: this query uses INNER JOIN to `labor_progress`, so **purely scheduled C-sections (not yet in labor, no exam records) do not appear** — for example, idx13's "C-section tomorrow" in this dataset is still `admitted` with no labor_progress, so it's not counted. Only deliveries that actually experienced labor are measured. This is an intentional choice (labor duration only makes sense for actual labor).

---

### Q14: Shift Coverage Report

**Business background:**
**Needed for Demo scenario 1 (handoff) + scenario 5 (Order Scheduling).** The nurse manager needs to confirm: are all shifts in the next 3 days **fully staffed**? Any shifts missing an anesthesiologist? If a C-section is scheduled for tomorrow 09:00 but no anesthesiologist is on the day shift, the POC must catch this **resource gap**.

**Category:** Join
**Difficulty:** Intermediate
**Business Role:** Nurse Manager

**Approach:**
`shift JOIN provider`, then group by (`shift_date`, `shift_type`), one row per shift. Use `GROUP_CONCAT(DISTINCT CASE WHEN p.role = 'xxx' THEN p.name END)` to concatenate per-role names — CASE picks only one role's names within the group, GROUP_CONCAT aggregates the list. Simultaneously use `COUNT(DISTINCT CASE WHEN p.role = 'xxx' THEN p.provider_id END)` to count per-role headcount, used to check staffing (attending ≥ 1, day nurses 3 / night 2). If the anesthesiologist column is NULL, that shift has no anesthesiologist scheduled, and any C-section / epidural on that shift should be flagged (P5's resource gap). One row = one shift's roster + role headcount.

```sql
-- Each shift's roster + per-role headcount
SELECT
    s.shift_date,
    s.shift_type,
    GROUP_CONCAT(DISTINCT CASE WHEN p.role = 'attending' THEN p.name END) AS attendings,
    GROUP_CONCAT(DISTINCT CASE WHEN p.role = 'nurse' THEN p.name END) AS nurses,
    GROUP_CONCAT(DISTINCT CASE WHEN p.role = 'anesthesiologist' THEN p.name END) AS anesthesiologists,
    COUNT(DISTINCT CASE WHEN p.role = 'attending' THEN p.provider_id END) AS attending_count,
    COUNT(DISTINCT CASE WHEN p.role = 'nurse' THEN p.provider_id END) AS nurse_count
FROM shift s
JOIN provider p ON s.provider_id = p.provider_id
GROUP BY s.shift_date, s.shift_type
ORDER BY s.shift_date, s.shift_type;
```

**Expected result:**
6 rows (3 days × 2 shifts/day). All attending_count ≥ 1 means staffed; nurse_count of 3 day / 2 night is the standard. If the anesthesiologist column ever shows NULL, that shift has no anesthesiologist — any c_section / epidural on that shift should be flagged.

> Note: this snapshot has **every shift fully staffed** (including 1 anesthesiologist), so there is no actual "missing anesthesiologist" example — this is intentional POC staffing. What this query demonstrates is **the schema's ability to detect resource gaps**; once a real schedule has gaps, this query's NULL column will surface them.

---

### Q15: Complications Distribution

**Business background:**
**The Clinical Director's patient-population profile.** The hospital-wide complications mix affects **staffing** (e.g., high gestational-diabetes share → need nutrition consult), **drug stocking** (e.g., lots of Preeclampsia → stock more magnesium sulfate), and **how often MFM consults are needed**. This query extracts frequency by LIKE-matching the JSON field — POC's SQLite has limited JSON support, hence the workaround.

**Category:** Aggregation
**Difficulty:** Intermediate
**Business Role:** Clinical Director

**Approach:**
`complications` is a JSON array string. SQLite's JSON support is limited, so use pragmatic `LIKE` pattern matching. First, in a CTE, strip JSON brackets and quotes (chained `REPLACE`), then for each of the 10 complications write one `SELECT ... COUNT(CASE WHEN ... LIKE '%name%' THEN 1 END)` and stack 10 rows vertically via `UNION ALL`. `WHERE complications IS NOT NULL AND != 'null'` filters out patients with no complications. Sort by `count DESC` to see which is most common. One row = one complication and its occurrence count. Production would use PostgreSQL JSONB functions; under SQLite, LIKE is a reasonable workaround.

```sql
-- Complications frequency (via LIKE pattern matching on JSON field)
WITH complication_list AS (
    SELECT
        ob.ob_id,
        ob.patient_id,
        REPLACE(REPLACE(REPLACE(ob.complications, '["', ''), '"]', ''), '", "', '|') AS complications_clean
    FROM ob_profile ob
    WHERE ob.complications IS NOT NULL AND ob.complications != 'null'
)
SELECT 'Gestational diabetes' AS complication,
       COUNT(CASE WHEN complications_clean LIKE '%Gestational diabetes%' THEN 1 END) AS count
FROM complication_list
UNION ALL
SELECT 'Gestational hypertension',
       COUNT(CASE WHEN complications_clean LIKE '%Gestational hypertension%' THEN 1 END)
FROM complication_list
UNION ALL
SELECT 'Preeclampsia',
       COUNT(CASE WHEN complications_clean LIKE '%Preeclampsia%' THEN 1 END)
FROM complication_list
UNION ALL
SELECT 'Placenta previa',
       COUNT(CASE WHEN complications_clean LIKE '%Placenta previa%' THEN 1 END)
FROM complication_list
UNION ALL
SELECT 'Oligohydramnios',
       COUNT(CASE WHEN complications_clean LIKE '%Oligohydramnios%' THEN 1 END)
FROM complication_list
UNION ALL
SELECT 'Polyhydramnios',
       COUNT(CASE WHEN complications_clean LIKE '%Polyhydramnios%' THEN 1 END)
FROM complication_list
UNION ALL
SELECT 'Intrauterine growth restriction',
       COUNT(CASE WHEN complications_clean LIKE '%Intrauterine growth restriction%' THEN 1 END)
FROM complication_list
UNION ALL
SELECT 'Previous cesarean section',
       COUNT(CASE WHEN complications_clean LIKE '%Previous cesarean section%' THEN 1 END)
FROM complication_list
UNION ALL
SELECT 'Advanced maternal age',
       COUNT(CASE WHEN complications_clean LIKE '%Advanced maternal age%' THEN 1 END)
FROM complication_list
UNION ALL
SELECT 'Anemia',
       COUNT(CASE WHEN complications_clean LIKE '%Anemia%' THEN 1 END)
FROM complication_list
ORDER BY count DESC;
```

**Expected result:**
10 rows (covers all 10 complications from §4.2, sorted descending by frequency). Gestational hypertension / Preeclampsia / Anemia usually lead because they're planted into high-risk admissions; the rest follows random sampling. Covering **all 10** types lets the Clinical Director make undistorted training-focus and drug-procurement decisions (counting only 5 would miss half).

> Note: production would use PostgreSQL JSONB or jsonb_array_elements; LIKE is the pragmatic fallback under SQLite limitations.

---

### Q16: Patients with Abnormal Recent Vital Signs

**Business background:**
**The nurse-side view of Demo scenario 4.** A clinical nurse looks at her dashboard before rounds and asks: "**This round**, who has abnormal vitals?" This query takes each active admission's **latest** vital_sign, shows only those triggering any threshold, sorted by severity. The nurse uses it to plan her rounds order.

**Category:** Window Function + Filter
**Difficulty:** Intermediate
**Business Role:** Clinical Nurse

**Approach:**
Same shape as Q5: `ROW_NUMBER() OVER (PARTITION BY admission_id ORDER BY recorded_at DESC)` to grab each patient's **latest** vital, then `WHERE rn = 1`. Use `CASE` with priority order (BP-CRITICAL > BP-HIGH > FHR-ABNORMAL > FEVER) to assign an abnormal label, and rewrite the same thresholds in `WHERE` to keep only patients triggering any of them (normals don't appear). `bp_systolic || '/' || bp_diastolic` uses SQLite's `||` to concatenate systolic/diastolic into "140/90" form. `ORDER BY` uses `CASE` to push the most severe to the top. One row = one in-house patient with latest abnormal vitals. Label priority and thresholds must match ER §4.9's alert thresholds.

```sql
-- Each inpatient's latest vital_sign + abnormality label
WITH recent_vitals AS (
    SELECT
        vs.*,
        ROW_NUMBER() OVER (PARTITION BY vs.admission_id ORDER BY vs.recorded_at DESC) AS rn
    FROM vital_sign vs
)
SELECT
    p.name AS patient_name,
    r.room_number,
    rv.recorded_at,
    rv.bp_systolic || '/' || rv.bp_diastolic AS blood_pressure,
    rv.fetal_heart_rate AS fhr,
    rv.temperature,
    CASE
        WHEN rv.bp_systolic >= 160 OR rv.bp_diastolic >= 110 THEN 'BP-CRITICAL'
        WHEN rv.bp_systolic >= 140 OR rv.bp_diastolic >= 90 THEN 'BP-HIGH'
        WHEN rv.fetal_heart_rate < 110 OR rv.fetal_heart_rate > 160 THEN 'FHR-ABNORMAL'
        WHEN rv.temperature >= 100.4 THEN 'FEVER'
        ELSE 'Normal'
    END AS concern
FROM recent_vitals rv
JOIN admission a ON rv.admission_id = a.admission_id
JOIN patient p ON a.patient_id = p.patient_id
LEFT JOIN bed b ON a.current_bed_id = b.bed_id
LEFT JOIN room r ON b.room_id = r.room_id
WHERE rv.rn = 1
    AND a.status != 'discharged'
    AND (rv.bp_systolic >= 140 OR rv.bp_diastolic >= 90
         OR rv.fetal_heart_rate < 110 OR rv.fetal_heart_rate > 160
         OR rv.temperature >= 100.4)
ORDER BY
    CASE
        WHEN rv.bp_systolic >= 160 THEN 1
        WHEN rv.bp_systolic >= 140 THEN 2
        ELSE 3
    END;
```

**Expected result:**
~1–3 rows. The planted BP-HIGH patients in this dataset will reliably appear. Any critical row must be escalated to the attending immediately.

---

### Q17: LOS Prediction Accuracy (Predicted vs Actual)

**Business background:**
**One of the numbers the client cares about most at POC stage**: "Your AI predicts LOS — how big is the error?" The Quality Analyst takes this query's output and uses it **directly in the review**: average error 6 hours? Then it's usable. Average 24? Then retune. This query computes the predicted-vs-actual gap for **discharged** admissions (those with `actual_discharge_time`).

**Category:** CTE
**Difficulty:** Advanced
**Business Role:** Quality Analyst

**Approach:**
In CTE `los_comparison`, keep only discharged (`actual_discharge_time IS NOT NULL`) admissions with predictions, and compute actual postpartum LOS = `(julianday(actual_discharge_time) - julianday(delivery_time)) * 24`. Outer query groups by `delivery_method_actual`, computing average predicted, average actual, average variance (`actual - predicted`), average absolute error (`ABS(...)`), and within-12h hit count. **Predicted and actual share the same convention** (both measured from `delivery_time`), so they can be subtracted — a key fix vs the old version, which subtracted "postpartum prediction" from "total stay" and produced a misaligned baseline. One row = one delivery method's accuracy report. At POC stage discharged samples are few (only 1), but the focus is showing the convention is now aligned and the schema + query are ready.

```sql
-- Predicted vs actual "postpartum LOS" gap (discharged only, unified convention from delivery_time)
WITH los_comparison AS (
    SELECT
        a.admission_id,
        a.delivery_method_actual,
        a.predicted_los_hours,
        ROUND((julianday(a.actual_discharge_time) - julianday(a.delivery_time)) * 24, 1) AS actual_postpartum_los_hours
    FROM admission a
    WHERE a.actual_discharge_time IS NOT NULL
        AND a.predicted_los_hours IS NOT NULL
        AND a.delivery_time IS NOT NULL
)
SELECT
    delivery_method_actual,
    COUNT(*) AS cases,
    ROUND(AVG(predicted_los_hours), 1) AS avg_predicted,
    ROUND(AVG(actual_postpartum_los_hours), 1) AS avg_actual,
    ROUND(AVG(actual_postpartum_los_hours - predicted_los_hours), 1) AS avg_variance,
    ROUND(AVG(ABS(actual_postpartum_los_hours - predicted_los_hours)), 1) AS avg_abs_error,
    SUM(CASE WHEN ABS(actual_postpartum_los_hours - predicted_los_hours) <= 12 THEN 1 ELSE 0 END) AS within_12hrs
FROM los_comparison
GROUP BY delivery_method_actual;
```

**Expected result:**
Returns **1 row** (this snapshot has 1 discharged c_section: actual postpartum LOS ≈ 84h vs predicted 72–96h, `avg_abs_error` is small, `within_12hrs = 1`). **Predicted and actual now share a convention** (both postpartum LOS measured from `delivery_time`); unlike the old version, which subtracted "postpartum prediction" from "total stay (admit→discharge)" and produced a misaligned baseline and always returned 0 rows because `actual_discharge_time` was all null. At POC stage the discharged sample is still tiny (1 row); statistical-grade sample sizes will accumulate after deployment.

> POC defense talking point: "The data is sparse now, but the schema and queries are ready and the convention is aligned — 2 weeks after deployment we'll have statistically meaningful accuracy reports."

---

### Q18: Multiple-Gestation Tracking + NICU Capacity

**Business background:**
**The MFM (Maternal-Fetal Medicine) Specialist's dedicated view.** Twins / triplets are OB's highest alert — preterm rate 60%+, must have **NICU beds available simultaneously** before entering the OR. This query joins two things: full list of multiple-gestation patients + real-time NICU capacity. It is also Demo 4's proof that the "AI can look at multiple tables at once."

**Category:** Join + Subquery
**Difficulty:** Intermediate
**Business Role:** MFM Specialist

**Approach:**
Main query: `ob_profile JOIN patient` for all multiples (`fetus_count > 1`), LEFT JOIN `admission` (in-house only) → `bed` → `room` for current location (some multiples may not yet be admitted, so LEFT preserves them). NICU capacity uses a **scalar subquery** `(SELECT COUNT(*) FROM bed JOIN room WHERE room_type = 'nicu' AND status = 'available')` as a column attached to each row — uncorrelated with the outer, every row sees the same global number. This is exactly what "looking at two things at once (multiples list + NICU capacity)" needs. Sort by ascending gestational weeks, preterm-risk at the top. One row = one multiple-gestation patient + current NICU available bed count.

```sql
-- All multiple-gestation patients + current NICU available beds (as scalar subquery)
SELECT
    p.name AS patient_name,
    ob.fetus_count,
    ob.gestational_weeks,
    ob.risk_level,
    ob.planned_delivery_method,
    a.status AS admission_status,
    r.room_number,
    ob.complications,
    (SELECT COUNT(*) FROM bed b2
     JOIN room r2 ON b2.room_id = r2.room_id
     WHERE r2.room_type = 'nicu' AND b2.status = 'available') AS nicu_beds_available
FROM ob_profile ob
JOIN patient p ON ob.patient_id = p.patient_id
LEFT JOIN admission a ON ob.ob_id = a.ob_id AND a.status != 'discharged'
LEFT JOIN bed b ON a.current_bed_id = b.bed_id
LEFT JOIN room r ON b.room_id = r.room_id
WHERE ob.fetus_count > 1
ORDER BY ob.gestational_weeks ASC;
```

**Expected result:**
~2–4 rows (at the ~3.5% multiples rate + 1 deterministically planted 34.2-week twin idx4, 50 patients should yield about 2–4 multiples). `nicu_beds_available` is the current real available NICU bed count; in this snapshot all 8 NICU beds are free (mothers themselves don't enter NICU and this POC has no newborn entity), so it stays at 8 — at demo time this means "twins can enter the OR safely." In real deployment, if NICU is full (= 0) and a 34-week twin is in_labor, MFM immediately coordinates with NICU to transfer out.

---

### Q19: Completion Rate by Order Type

**Business background:**
**Demo scenario 5's tracking view.** The Operations Analyst cares about: how many lab_tests actually completed at scheduled_time? How many c_sections were scheduled and then cancelled (an overbook signal)? High cancellation rate means low scheduling quality; long-standing scheduled rows indicate an execution bottleneck.

**Category:** Aggregation
**Difficulty:** Intermediate
**Business Role:** Operations Analyst

**Approach:**
Only the `medical_order` table, grouped by `order_type`. A bank of conditional sums `SUM(CASE WHEN status = 'xxx' THEN 1 ELSE 0 END)` counts each of the 4 statuses (completed / in_progress / scheduled / cancelled) as a column; `completion_rate` = completed / total × 100.0 (decimal to avoid integer-division truncation). Sort by `total_orders DESC` so the highest-volume order type is on top. Note that the scheduled c_section / induction are intentionally planted "tomorrow's procedures" — being in scheduled is not abnormal, not an execution bottleneck. One row = one order type's status distribution + completion rate.

```sql
-- Status distribution + completion rate by order_type
SELECT
    order_type,
    COUNT(*) AS total_orders,
    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) AS completed,
    SUM(CASE WHEN status = 'in_progress' THEN 1 ELSE 0 END) AS in_progress,
    SUM(CASE WHEN status = 'scheduled' THEN 1 ELSE 0 END) AS scheduled,
    SUM(CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END) AS cancelled,
    ROUND(
        SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) * 100.0 / COUNT(*),
        1
    ) AS completion_rate
FROM medical_order
GROUP BY order_type
ORDER BY total_orders DESC;
```

**Expected result:**
~3–4 rows (this dataset has about **20** orders, mostly lab_test ~14 + epidural ~4, plus tomorrow's c_section/induction 1 each). lab_tests are mostly `completed`; epidurals are `completed` / `in_progress`; c_section / induction are in `scheduled` (haven't reached execution time, this isn't a problem — it's the planted scenario).

---

### Q20: Admission Distribution by Day of Week × Shift

**Business background:**
**The Capacity Planner's long-term staffing view.** OB spontaneous-labor admission timing is **not random** — empirically nighttime admissions skew higher (mothers leave for the hospital after contractions become regular), and weekday vs weekend distribution differs. The planner uses this query's output to **optimize nurse scheduling for the next 3 months**: if Tuesday night admissions are heavier, add one more nurse.

**Category:** Date Analysis
**Difficulty:** Intermediate
**Business Role:** Capacity Planner

**Approach:**
Only `admission JOIN ob_profile` (for risk_level). Use SQLite's `strftime('%w', admit_time)` for day-of-week (0 = Sunday), `strftime('%H', ...)` for hour, then `CAST(... AS INTEGER)` to number, then `CASE` to map to day name and a 3-segment time bucket (Day / Evening / Night). Group by (day, segment) and count admissions; `AVG(CASE WHEN risk_level = 'high' THEN 1.0 ELSE 0.0 END) * 100` for the high-risk share per bucket. `ORDER BY` also uses the `strftime` number to ensure Sunday-to-Saturday order. One row = one (day × segment) bucket. Note the 3-segment bucketing is a capacity-planning view, different from operational 2-shift (see ER §4.6) — both intentionally coexist. This dataset has only 3 days; a real environment would run 3–6 months for statistical meaning.

```sql
-- Admissions bucketed by day of week + time segment
SELECT
    CASE CAST(strftime('%w', admit_time) AS INTEGER)
        WHEN 0 THEN 'Sunday'
        WHEN 1 THEN 'Monday'
        WHEN 2 THEN 'Tuesday'
        WHEN 3 THEN 'Wednesday'
        WHEN 4 THEN 'Thursday'
        WHEN 5 THEN 'Friday'
        WHEN 6 THEN 'Saturday'
    END AS day_of_week,
    CASE
        WHEN CAST(strftime('%H', admit_time) AS INTEGER) BETWEEN 7 AND 14 THEN 'Day Shift (7AM-3PM)'
        WHEN CAST(strftime('%H', admit_time) AS INTEGER) BETWEEN 15 AND 22 THEN 'Evening (3PM-11PM)'
        ELSE 'Night Shift (11PM-7AM)'
    END AS shift_period,
    COUNT(*) AS admission_count,
    ROUND(AVG(CASE WHEN ob.risk_level = 'high' THEN 1.0 ELSE 0.0 END) * 100, 1) AS high_risk_pct
FROM admission a
JOIN ob_profile ob ON a.ob_id = ob.ob_id
GROUP BY day_of_week, shift_period
ORDER BY
    CAST(strftime('%w', admit_time) AS INTEGER),
    CASE shift_period
        WHEN 'Day Shift (7AM-3PM)' THEN 1
        WHEN 'Evening (3PM-11PM)' THEN 2
        ELSE 3
    END;
```

**Expected result:**
~6–9 rows (this dataset covers only 3 days; a real environment would need 3–6 months for statistical meaning). At POC stage this query is primarily to **demonstrate that the schema supports** this analysis, not to produce conclusions — it's a "hook for future expansion" shown to the client.

> Note: this query buckets by 3 segments (Day 7–14 / Evening 15–22 / Night the rest); this is the **capacity-planning view**, different from the operational **2-shift** (day 07–19 / night 19–07, see ER §4.6). They coexist intentionally: scheduling uses 2 shifts, capacity analysis uses finer 3 segments to find the evening peak.

---

## Query Category Summary

| Category | Count | Query #s |
|------|------|---------|
| Aggregation | 6 | Q1, Q8, Q9, Q12, Q15, Q19 |
| Join | 6 | Q2, Q3, Q4, Q6, Q14, Q18 |
| Window Function | 3 | Q5, Q7, Q16 |
| Date/Time Analysis | 2 | Q11, Q20 |
| CTE / Subquery | 3 | Q10, Q13, Q17 |

## Business Role Coverage

| Role | Count | Query #s |
|------|------|---------|
| Charge Nurse (front-line lead nurse) | 4 | Q1, Q2, Q5, Q6 |
| Attending Physician | 2 | Q3, Q7 |
| Clinical Nurse | 1 | Q16 |
| Department Manager / Nurse Manager | 2 | Q8, Q14 |
| OR Coordinator | 1 | Q4 |
| Quality Analyst | 3 | Q9, Q13, Q17 |
| Operations Manager / Analyst | 2 | Q10, Q19 |
| Scheduling Coordinator | 1 | Q11 |
| Finance Analyst | 1 | Q12 |
| Clinical Director | 1 | Q15 |
| MFM Specialist | 1 | Q18 |
| Capacity Planner | 1 | Q20 |

## Difficulty Distribution

| Difficulty | Count | Share |
|------|------|------|
| Basic | 6 | 30% |
| Intermediate | 11 | 55% |
| Advanced | 3 | 15% |

---

## Expected Demo-Day Dialog Flow

> This is the vendor's demo script skeleton, included here to help the reader see the mapping between SQL and the demo.

| Time | Nurse's spoken question (actual demo line) | Query the AI calls |
|------|---------------------------|--------------|
| 07:05 | "Show me where everyone is right now." | Q1 |
| 07:08 | "Any beds open in labor?" | Q2 |
| 07:11 | "Who's about to deliver?" | Q5 |
| 07:14 | "Any alerts I should know about?" | Q6 |
| 07:18 | "Pull up the high-risk patient list for rounds." | Q3 |
| 07:22 | "What's Emily's BP doing — is it really trending up?" | Q7 |
| 07:30 | "OK, who delivers today? Any C-sections scheduled?" | Q4 |
| 07:35 | "Anesthesiology is on for the 9 AM C-section, right?" | Q14 |
| 09:45 | "Sarah delivered at 7:50 — when will she be ready to go home?" | Q9, Q17 (baseline comparison) |

---

## Notes

1. **Date functions**: all use SQLite's `julianday()`; when migrating to PostgreSQL, switch to `EXTRACT(EPOCH FROM ...) / 86400`.
2. **JSON parsing**: uses the LIKE workaround because the POC runs on SQLite. Production would use PostgreSQL JSONB operators.
3. **`datetime('now')` replaced with a fixed reference time**: demo reproducibility; in production switch back to `'now'`.
4. **Index hints**: this dataset is ~500 rows, no indexes needed. In production, recommend at least indexes on `admission(status, admit_time)`, `vital_sign(admission_id, recorded_at)`, `labor_progress(admission_id, recorded_at)`.
5. **POC acceptance**: the vendor does not show the nurses SQL on demo day; instead they ask **naturally**, and the AI agent calls the queries above behind the scenes. The reason this document exists is so the client's IT team can **audit after the fact**: every AI answer maps to real data in the schema.
