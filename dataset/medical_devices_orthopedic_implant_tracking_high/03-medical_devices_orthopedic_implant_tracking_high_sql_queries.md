# Medical Devices: Orthopedic Implant Tracking SQL Queries Reference

> **Owning system:** MAOHN (MidAtlantic Orthopedic Health Network) implant registry.
> **Perspective:** Hospital side. Every "cost" is the cost MAOHN pays as the hospital; every "recall" is what MAOHN does as the patient-safety first responder.
> **For business context, industry primer, and glossary, see** `01-medical_devices_orthopedic_implant_tracking_high_business_context.md`; **for table structures and field definitions, see** `02-medical_devices_orthopedic_implant_tracking_high_er_document.md`.

---

## How to Use This Document

This document is written for a new analyst who has just finished business context document `01` and ER document `02`, and is about to be handed a query assignment by the manager. It is not a "SQL syntax cheat sheet." It is 20 exercises **rooted in real business questions**: each one corresponds to a question some specific role inside MAOHN actually asks, and each one traces back to one of the five business questions listed in Section 5 of document `01`.

**Every exercise is organized in the same five-part structure, and is best read in order:**

1. **Business context**: who is asking, why right now, and what decision the answer supports. Read this first; otherwise you won't see why the question is worth answering.
2. **Category / difficulty / business role**: three tags that tell you which SQL technique you'll practice, how hard the exercise is, and which role it serves.
3. **Approach**: before you see the SQL, this section walks through which tables to touch, how to wire the joins, what the aggregation grain is, and where the traps are (fan-out, NULL semantics, LEFT vs INNER). This is the section worth reading most carefully.
4. **SQL**: a query that can be run directly on the generated SQLite database. Read it against the approach section.
5. **Expected results and business takeaway**: what the result looks like, what magnitude the key numbers fall into, and what the analyst should do next with them. Running the query is the start of the analysis, not the end of it.

**About REFERENCE_DATE.** Every date in the dataset is anchored at the fixed reference point `2026-06-01` (the `NOW` constant in the generator). Queries that mean "right now" use `DATE('now')` or fixed literals, and their results will drift as the system clock moves away from that anchor; to reproduce, regenerate the dataset.

When a metric has two reasonable definitions (e.g., "event rate" could be per surgery or per implant), this document **picks one definition** and uses it throughout.

**The unified definitions are:**

| Metric | The definition we use | Why |
|---|---|---|
| **Adverse event rate** | Events per 100 **surgeries** (not per 100 implants) | A surgery using many implants and having one event is one affected surgery, not N |
| **"Affected by recall"** | An implanted unit whose `lot_id` matches a lot-level recall, **or** whose `product_id` matches a full-product recall (`recall.lot_id IS NULL`) | Both scopes are real; SQL must handle both |
| **Implant cost** | `pricing_history.contracted_price_usd` in effect at the unit's `received_date` (point-in-time price) | MSRP is misleading since contract price changes over time and by contract type |
| **"Used"** | The unit appears in `surgery_implant` | The silver-tier `inventory.status = 'Used'` is derived from this, so the two sides are always consistent |
| **Lot QC status** | The lot's most recent `quality_test_event` with `result IN ('Pass', 'Fail')` (`Conditional` is not conclusive) | |

**Gold-tier views** (used by Q18 / Q19) are predefined `CREATE VIEW`s that wrap the common joins and derivations. Raw events still drive everything; the views are a convenience layer.

---

## Query Index

| # | Title | Business role | Category | Difficulty |
|---|---|---|---|---|
| 1 | Implant usage by category | Executive | Aggregation + Join | Basic |
| 2 | Patient roster affected by active recalls (lot-level + full-product) | Manager | Multi-table Join | Advanced |
| 3 | Surgeon volume ranking | Manager | Window function | Intermediate |
| 4 | Adverse event rate by manufacturer | Analyst | Aggregation + Join | Intermediate |
| 5 | Available inventory expiring within 90 days | Operations | Date range | Basic |
| 6 | High-value FDA submissions in review | Regulatory | Join + Aggregation | Intermediate |
| 7 | Rolling 12-month surgery volume month-over-month | Executive | Window + Date | Intermediate |
| 8 | Full patient roster for Class I recalls | Operations | Multi-table Join + CASE | Advanced |
| 9 | Inventory turnover by hospital | Analyst | Aggregation + Join | Intermediate |
| 10 | GPO contract pricing compliance audit | Finance | CTE + Join | Advanced |
| 11 | Recall notifications past SLA without acknowledgment | Operations | Date filter + CASE | Intermediate |
| 12 | Average duration by procedure | Analyst | Aggregation + GROUP BY | Basic |
| 13 | Lots whose most recent QC was Fail | Manager | CTE + Window | Advanced |
| 14 | Full-traceability adverse event report | Analyst | Multi-table Join | Advanced |
| 15 | Surgeons with elevated adverse event rate, volume-adjusted | Manager | CTE + Window function | Advanced |
| 16 | Inventory status distribution by hospital and storage location | Operations | Aggregation + GROUP BY | Basic |
| 17 | Approval rate by FDA submission type | Regulatory | Conditional aggregation | Intermediate |
| 18 | Annual implant cost by hospital (using `v_hospital_monthly_implant_cost` gold view) | Finance | View + Aggregation | Intermediate |
| 19 | Recall response SLA compliance (using `v_recall_response_sla` gold view) | Manager | View + CTE | Advanced |
| 20 | 2-year revision rate per patient | Analyst | CTE + Self-join | Advanced |

---

## Queries

### Query 1: Implant usage by category

**Business context:**
The MAOHN CMO reviews network-wide orthopedic implant usage by category every quarter across the 12 hospitals, pulling the top-share categories into the supply chain committee to drive strategic vendor negotiations. Categories at 35% or higher share are leverage points to push vendors for stronger service-level commitments.

**Category:** Aggregation + Join
**Difficulty:** Basic
**Business role:** Executive

**Approach:**
"Usage" here means we need to walk from category down to `surgery_implant` (only units that show up in that table count as actually implanted). The join chain is `implant_category → implant_product → implant_lot → inventory → surgery_implant`, all INNER JOIN — unused inventory doesn't belong in the numerator. First flatten each used implant plus its category into one row inside a CTE called `used`, then GROUP BY category to count. The denominator uses a subquery against the same CTE, `SELECT COUNT(*) FROM used`, so the numerator and denominator share a source and the percentages always sum to 100%. A single GROUP BY is enough; no window function required.

```sql
-- Count usage by category, plus network-wide share.
-- The denominator uses the CTE's FK-trimmed row count, so shares always sum to 100%.
WITH used AS (
    SELECT ic.id AS category_id, ic.name AS category_name, si.id AS si_id
    FROM implant_category ic
    JOIN implant_product ip ON ic.id = ip.category_id
    JOIN implant_lot il ON ip.id = il.product_id
    JOIN inventory i ON il.id = i.lot_id
    JOIN surgery_implant si ON i.id = si.inventory_id
)
SELECT
    category_name,
    COUNT(si_id) AS total_implants_used,
    ROUND(COUNT(si_id) * 100.0 / (SELECT COUNT(*) FROM used), 2) AS percentage_of_total
FROM used
GROUP BY category_id, category_name
ORDER BY total_implants_used DESC;
```

**Expected result:** Usage ranking by category with share. Typical signal: 1 to 2 categories account for over 50% of volume, which makes them the main battlefield for procurement spend.

---

### Query 2: Patient roster affected by active recalls (lot-level + full-product)

**Business context:**
The MAOHN Risk Director needs to be able to pull, at any moment, "every implanted patient touched by every currently active recall" — covering both lot-level recalls (only the bad batch) and full-product recalls (the whole product line). Missing either bucket has already triggered regulatory action at peer hospitals. This query must handle both scopes correctly at the same time.

**Category:** Multi-table Join
**Difficulty:** Advanced
**Business role:** Manager

**Approach:**
Recalls come in two scopes, and the big trap in this query is that both must be handled at the same time: a lot-level recall (`recall.lot_id` is non-null) only affects that batch, and a full-product recall (`recall.lot_id IS NULL`) affects the whole product line. So the ON clause joining `recall` to `implant_lot` is written as `(r.lot_id = il.id) OR (r.lot_id IS NULL AND il.product_id = r.product_id)`, a single ON that covers both scopes. From the lot, follow `inventory → surgery_implant → surgery → patient` down to specific patients. Notification status comes from a `LEFT JOIN recall_notification`, never INNER — otherwise patients who haven't been notified yet would silently disappear, and those are exactly the ones you most need to contact. A CASE then surfaces the three states "not notified / notified not acknowledged / acknowledged." Finally, restrict to `status = 'Active'` recalls.

```sql
-- Affected = (recall is lot-level AND inventory.lot_id matches)
--            OR (recall is full-product AND inventory's product matches).
-- The ON clause below expresses this scope exactly.
SELECT
    r.recall_number,
    r.recall_class,
    r.recall_reason,
    p.mrn,
    p.first_name || ' ' || p.last_name AS patient_name,
    ip.product_name,
    il.lot_number,
    s.surgery_date,
    h.name AS hospital_name,
    CASE
        WHEN rn.id IS NULL THEN 'NOT NOTIFIED'
        WHEN rn.acknowledgment_date IS NULL THEN 'NOTIFIED - NO ACK'
        ELSE 'ACKNOWLEDGED'
    END AS notification_status
FROM recall r
JOIN implant_product ip ON r.product_id = ip.id
JOIN implant_lot il
    ON (r.lot_id = il.id)                                  -- lot-level recall
    OR (r.lot_id IS NULL AND il.product_id = r.product_id) -- full-product recall
JOIN inventory i ON il.id = i.lot_id
JOIN surgery_implant si ON i.id = si.inventory_id
JOIN surgery s ON si.surgery_id = s.id
JOIN patient p ON s.patient_id = p.id
JOIN hospital h ON s.hospital_id = h.id
LEFT JOIN recall_notification rn
    ON r.id = rn.recall_id AND si.id = rn.surgery_implant_id
WHERE r.status = 'Active'
ORDER BY r.recall_class, p.last_name;
```

**Expected result:** One row per (recall × affected implanted unit). Class I rows are emergency action items; `NOT NOTIFIED` rows go straight into the active outreach workflow.

---

### Query 3: Surgeon volume ranking

**Business context:**
The hospital operations director ranks surgeons by surgical volume to inform OR block-time allocation and retention strategy for high-volume surgeons. Within-specialty ranking distinguishes "real high producer in their subspecialty" from "high overall but spread across specialties."

**Category:** Window function
**Difficulty:** Intermediate
**Business role:** Manager

**Approach:**
A single `surgeon JOIN surgery` followed by GROUP BY surgeon gives you each surgeon's volume and average duration. Ranking uses two window functions: `RANK() OVER (ORDER BY COUNT(...) DESC)` for the network-wide rank, and `DENSE_RANK() OVER (PARTITION BY specialty ORDER BY COUNT(...) DESC)` for the within-specialty rank. Window functions can rank the aggregated `COUNT(surg.id)` directly because they evaluate after GROUP BY. Be careful about the difference between RANK and DENSE_RANK: the former skips numbers on ties, the latter doesn't; with small specialty groups, DENSE_RANK reads more naturally. `LIMIT 20` takes the top of the leaderboard.

```sql
SELECT
    s.first_name || ' ' || s.last_name AS surgeon_name,
    s.specialty,
    COUNT(surg.id) AS total_surgeries,
    ROUND(AVG(surg.duration_minutes), 1) AS avg_duration_minutes,
    RANK()       OVER (ORDER BY COUNT(surg.id) DESC) AS overall_rank,
    DENSE_RANK() OVER (PARTITION BY s.specialty ORDER BY COUNT(surg.id) DESC) AS specialty_rank
FROM surgeon s
JOIN surgery surg ON s.id = surg.surgeon_id
GROUP BY s.id, s.first_name, s.last_name, s.specialty
ORDER BY total_surgeries DESC
LIMIT 20;
```

**Expected result:** Top 20 surgeons by volume with within-specialty rank. Surgeons with high volume and short average duration are candidates to mentor others internally.

---

### Query 4: Adverse event rate by manufacturer

**Business context:**
The clinical quality director computes each manufacturer's adverse event rate **per 100 surgeries** (the dataset's unified definition), keeping only manufacturers whose devices were used in at least 10 surgeries in the data so the numbers are statistically meaningful. This metric feeds the vendor scorecard.

**Category:** Aggregation + Join
**Difficulty:** Intermediate
**Business role:** Analyst

**Approach:**
The hard part is the unified definition "rate is per surgery, not per implant." A surgery may have used many implants from the same manufacturer, so just counting implants would double-count that surgery. So a CTE first collapses the grain down to (manufacturer, surgery) per row: `manufacturer → implant_product → implant_lot → inventory → surgery_implant`, then `LEFT JOIN adverse_event` (LEFT keeps event-free surgeries in the denominator), and at that grain `COUNT(ae.id)` gives "how many events fired on this surgery for this manufacturer." Outside, `COUNT(DISTINCT surgery_id)` is the denominator and `SUM(CASE WHEN events > 0 THEN 1 ELSE 0 END)` is the numerator. `HAVING COUNT(DISTINCT surgery_id) >= 10` filters out manufacturers with tiny samples — otherwise 1 or 2 surgeries can produce a scary-looking percentage.

```sql
-- Per the unified rule, "event rate" is per surgery, not per implant.
-- A multi-implant surgery in which any one implant has an event counts as 1.
WITH manufacturer_surgeries AS (
    SELECT
        m.id AS manufacturer_id,
        m.name AS manufacturer_name,
        m.country,
        si.surgery_id,
        COUNT(ae.id) AS events_on_this_surgery_for_this_mfr
    FROM manufacturer m
    JOIN implant_product ip ON m.id = ip.manufacturer_id
    JOIN implant_lot il ON ip.id = il.product_id
    JOIN inventory i ON il.id = i.lot_id
    JOIN surgery_implant si ON i.id = si.inventory_id
    LEFT JOIN adverse_event ae ON si.id = ae.surgery_implant_id
    GROUP BY m.id, m.name, m.country, si.surgery_id
)
SELECT
    manufacturer_name,
    country,
    COUNT(DISTINCT surgery_id) AS total_surgeries,
    SUM(CASE WHEN events_on_this_surgery_for_this_mfr > 0 THEN 1 ELSE 0 END) AS surgeries_with_event,
    ROUND(
        SUM(CASE WHEN events_on_this_surgery_for_this_mfr > 0 THEN 1 ELSE 0 END) * 100.0
        / COUNT(DISTINCT surgery_id),
        2
    ) AS adverse_event_rate_per_100_surgeries
FROM manufacturer_surgeries
GROUP BY manufacturer_id, manufacturer_name, country
HAVING COUNT(DISTINCT surgery_id) >= 10
ORDER BY adverse_event_rate_per_100_surgeries DESC;
```

**Expected result:** Manufacturers with elevated event rates rise to the top, triggering quality review or contract renegotiation.

---

### Query 5: Available inventory expiring within 90 days

**Business context:**
The supply chain analyst runs this query daily to find high-value `Available` units expiring within 90 days. `unit_cost` uses **the `pricing_history` price in effect at this unit's `received_date`**, not a single static catalog price — that's what MAOHN actually paid.

**Category:** Date range + Join
**Difficulty:** Intermediate
**Business role:** Operations

**Approach:**
The driving table is `inventory`, with two filters: `status = 'Available'`, and the owning lot expiring within 90 days (`expiration_date BETWEEN DATE('now') AND DATE('now','+90 days')`). Pricing is the key to this query: you can't use the product's current catalog price; you have to use the contract price **in effect on the unit's receipt date**, so the `pricing_history` join carries the point-in-time predicate `effective_date <= received_date AND (end_date IS NULL OR end_date > received_date)`. Use LEFT JOIN for pricing, so the entire row isn't lost if no price record matches at receipt time. Sort by expiration date ascending so the most urgent items float to the top.

```sql
-- Pull 'Available' units whose owning lot expires within 90 days.
-- Price uses the contracted price in effect at receipt.
SELECT
    i.serial_number,
    ip.product_name,
    m.name AS manufacturer,
    il.lot_number,
    il.expiration_date,
    CAST(JULIANDAY(il.expiration_date) - JULIANDAY('now') AS INTEGER) AS days_until_expiration,
    i.location,
    h.name AS hospital,
    ph.contracted_price_usd AS unit_cost_at_receipt,
    i.is_consignment
FROM inventory i
JOIN implant_lot il ON i.lot_id = il.id
JOIN implant_product ip ON il.product_id = ip.id
JOIN manufacturer m ON ip.manufacturer_id = m.id
JOIN hospital h ON i.hospital_id = h.id
LEFT JOIN pricing_history ph
    ON ph.product_id = ip.id
   AND ph.manufacturer_id = m.id
   AND ph.effective_date <= i.received_date
   AND (ph.end_date IS NULL OR ph.end_date > i.received_date)
WHERE i.status = 'Available'
  AND il.expiration_date BETWEEN DATE('now') AND DATE('now', '+90 days')
ORDER BY il.expiration_date ASC, ph.contracted_price_usd DESC;
```

**Expected result:** A list sorted by urgency and value. Units with `is_consignment = TRUE` carry less financial loss — title belongs to the manufacturer.

---

### Query 6: High-value FDA submissions in review

**Business context:**
MAOHN Regulatory Affairs wants to forecast when new high-value technology will enter the formulary (the list of devices approved for use in-house), which means keeping an eye on which products manufacturers have in FDA review. "High value" is defined by current contract price.

**Category:** Join + Aggregation
**Difficulty:** Intermediate
**Business role:** Regulatory

**Approach:**
"Current price" here uses the simplified definition: the SCD2 row where `end_date IS NULL` (which represents "in effect right now"). Pull it out first as a CTE called `current_price`. The body is `implant_product` joined to `regulatory_submission`, filtered to `status = 'Pending'`, then `LEFT JOIN current_price` for the current contract price, and `cp.contracted_price_usd > 5000` defines "high value." `days_in_review` uses `JULIANDAY('now') - JULIANDAY(submission_date)`. Note that the current-price definition here is simpler than the point-in-time definition in Q5 / Q10 / Q18, because we only care about "what is this worth now," not what its price was on some historical date.

```sql
-- "Current price" = the SCD2 row with end_date IS NULL; this is shorthand for "in effect now."
-- For point-in-time pricing at an arbitrary moment, see the full predicate in Q5/Q10/Q18.
WITH current_price AS (
    SELECT
        product_id,
        manufacturer_id,
        contracted_price_usd
    FROM pricing_history
    WHERE end_date IS NULL
)
SELECT
    ip.product_name,
    ip.model_number,
    cp.contracted_price_usd AS current_contracted_price,
    m.name AS manufacturer,
    ic.name AS category,
    rs.submission_type,
    rs.submission_number,
    rs.submission_date,
    CAST(JULIANDAY('now') - JULIANDAY(rs.submission_date) AS INTEGER) AS days_in_review,
    rs.regulatory_body
FROM implant_product ip
JOIN manufacturer m ON ip.manufacturer_id = m.id
JOIN implant_category ic ON ip.category_id = ic.id
JOIN regulatory_submission rs ON ip.id = rs.product_id
LEFT JOIN current_price cp ON cp.product_id = ip.id AND cp.manufacturer_id = m.id
WHERE rs.status = 'Pending'
  AND cp.contracted_price_usd > 5000
ORDER BY cp.contracted_price_usd DESC, rs.submission_date ASC;
```

**Expected result:** High-value pending submissions plus days in review. A 510(k) in review for more than 180 days is on the slow side and worth flagging.

---

### Query 7: Rolling 12-month surgery volume month-over-month

**Business context:**
The MAOHN COO wants a true rolling 12-month view to spot seasonal patterns or volume drops. An earlier version forgot the date filter and ran across all history; this version puts it back in explicitly.

**Category:** Window function + Date analysis
**Difficulty:** Intermediate
**Business role:** Executive

**Approach:**
First aggregate surgeries by month in a CTE. The key is not forgetting the `WHERE surgery_date >= DATE('now','-12 months')` filter (an earlier version dropped it, and the query ended up scanning all of history). The month label is built with `STRFTIME('%Y-%m', surgery_date)`. Month-over-month change uses `LAG(surgery_count) OVER (ORDER BY surgery_month)` to grab the prior month's value, then computes the difference and percentage; wrap the denominator in `NULLIF(..., 0)` so that a zero prior month doesn't divide by zero. The window function is cleaner than a self-join because it naturally picks up the previous row in order.

```sql
WITH monthly AS (
    SELECT
        STRFTIME('%Y-%m', surgery_date) AS surgery_month,
        COUNT(*) AS surgery_count
    FROM surgery
    WHERE surgery_date >= DATE('now', '-12 months')
    GROUP BY STRFTIME('%Y-%m', surgery_date)
)
SELECT
    surgery_month,
    surgery_count,
    LAG(surgery_count) OVER (ORDER BY surgery_month) AS prev_month_count,
    surgery_count - LAG(surgery_count) OVER (ORDER BY surgery_month) AS volume_change,
    ROUND(
        (surgery_count - LAG(surgery_count) OVER (ORDER BY surgery_month)) * 100.0
        / NULLIF(LAG(surgery_count) OVER (ORDER BY surgery_month), 0),
        1
    ) AS percent_change
FROM monthly
ORDER BY surgery_month;
```

**Expected result:** 12 rows in time order plus month-over-month change. A month-over-month drop greater than 10% should trigger a root cause investigation; the seasonal dip in December informs scheduling.

---

### Query 8: Full patient roster for Class I recalls

**Business context:**
When a Class I recall notice arrives, the CMO wants every piece of information needed to contact patients in a single result set. **The key difference from the earlier version: this version handles both lot-level and full-product Class I recalls** — the older version silently missed full-product recalls, and design-defect recalls are very often full-product.

**Category:** Multi-table Join + CASE
**Difficulty:** Advanced
**Business role:** Operations

**Approach:**
Structurally, this is the same dual-scope join as Q2 (lot-level OR full-product), but here the CMO needs a "pick up the phone right now" report with every field, so the join is wider: it carries through patient demographics, surgeon phone, hospital phone, and insurance status. The filter tightens to `recall_class = 'Class I' AND status = 'Active'`. `SELECT DISTINCT` deduplicates, because a wide join can produce multiple rows per patient if multiple affected units exist. The `recall_scope` CASE distinguishes full-product from lot-level, so the coordinator can pull out the full-product recalls separately — these are the design-defect ones, which are the easiest type to miss.

```sql
SELECT DISTINCT
    r.recall_number,
    r.recall_reason,
    p.mrn,
    p.first_name || ' ' || p.last_name AS patient_name,
    p.date_of_birth,
    CAST((JULIANDAY('now') - JULIANDAY(p.date_of_birth)) / 365.25 AS INTEGER) AS patient_age,
    ip.product_name,
    ip.model_number,
    i.serial_number,
    s.surgery_date,
    s.procedure_name,
    si.implant_site,
    surg.first_name || ' ' || surg.last_name AS surgeon_name,
    surg.phone AS surgeon_phone,
    h.name AS hospital_name,
    h.phone AS hospital_phone,
    COALESCE(p.insurance_provider, 'UNINSURED') AS insurance_status,
    CASE
        WHEN r.lot_id IS NULL THEN 'PRODUCT-WIDE'
        ELSE 'LOT-SCOPED'
    END AS recall_scope
FROM recall r
JOIN implant_product ip ON r.product_id = ip.id
JOIN implant_lot il
    ON (r.lot_id = il.id)
    OR (r.lot_id IS NULL AND il.product_id = r.product_id)
JOIN inventory i ON il.id = i.lot_id
JOIN surgery_implant si ON i.id = si.inventory_id
JOIN surgery s ON si.surgery_id = s.id
JOIN patient p ON s.patient_id = p.id
JOIN surgeon surg ON s.surgeon_id = surg.id
JOIN hospital h ON s.hospital_id = h.id
WHERE r.recall_class = 'Class I'
  AND r.status = 'Active'
ORDER BY s.surgery_date DESC;
```

**Expected result:** A per-patient detail list with a `recall_scope` flag, so the coordinator can split out the full-product recalls for separate handling.

---

### Query 9: Inventory turnover by hospital

**Business context:**
The regional supply chain director hunts down "slow-moving" hospitals that have too much capital tied up. "Used" comes from `inventory.status` (which itself is derived from `inventory_movement`), so this metric stays in lockstep with the audit log.

**Category:** Aggregation + Join
**Difficulty:** Intermediate
**Business role:** Analyst

**Approach:**
The body is `hospital JOIN inventory`, grouped by hospital. Turnover is `Used units / total units`, computed with `SUM(CASE WHEN status='Used' ...)` and `COUNT(*)`; the `Used` here comes from `inventory.status`, which is derived from `inventory_movement`, so it matches the audit log exactly. `capital_tied_up` has a meaningful business trap: count only the value of `status='Available' AND NOT is_consignment` units, because consignment units have not been paid for yet — they don't tie up capital. Price comes from the current-price CTE. Sort by turnover ascending so the slowest-moving hospital lands on top.

```sql
WITH current_price AS (
    SELECT product_id, manufacturer_id, contracted_price_usd
    FROM pricing_history
    WHERE end_date IS NULL
)
SELECT
    h.name AS hospital_name,
    h.city,
    h.state,
    COUNT(*) AS total_inventory_units,
    SUM(CASE WHEN i.status = 'Available' THEN 1 ELSE 0 END) AS available_units,
    SUM(CASE WHEN i.status = 'Used' THEN 1 ELSE 0 END) AS used_units,
    ROUND(
        SUM(CASE WHEN i.status = 'Used' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1
    ) AS turnover_percentage,
    ROUND(
        SUM(CASE WHEN i.status = 'Available' AND NOT i.is_consignment
                 THEN cp.contracted_price_usd ELSE 0 END), 2
    ) AS capital_tied_up_usd
FROM hospital h
JOIN inventory i ON h.id = i.hospital_id
JOIN implant_lot il ON i.lot_id = il.id
JOIN implant_product ip ON il.product_id = ip.id
LEFT JOIN current_price cp ON cp.product_id = ip.id AND cp.manufacturer_id = ip.manufacturer_id
GROUP BY h.id, h.name, h.city, h.state
ORDER BY turnover_percentage ASC;
```

**Expected result:** Hospitals with low turnover and high capital tied up are candidates for inventory transfer. Consignment units are excluded from `capital_tied_up_usd` because MAOHN doesn't own them until they're used.

---

### Query 10: GPO contract pricing compliance audit

**Business context:**
The procurement lead verifies that MAOHN is actually paying contracted GPO prices. This query compares the price at receipt against the industry benchmark (here, `list_price_usd` stands in for MSRP) to compute discount. Chronic overpayment triggers a conversation with the supplier.

**Category:** CTE + Join
**Difficulty:** Advanced
**Business role:** Finance

**Approach:**
This audits "is the discount we actually got reasonable." The CTE `unit_at_receipt` attaches each received unit to its contract price **at receipt time** (point-in-time predicate again), and computes the discount rate `(list - contracted) / list` along the way. The outer query groups by (manufacturer, contract type) and looks at the average list price, the average contracted price, the average discount, and total savings against list. The `pricing_history` join must use a point-in-time predicate, not the current price; otherwise historical receipts would get today's price and the audit would lose meaning. When reading the results, benchmark against industry norms: GPO contract discounts should fall in 10% to 30%, and groups significantly below that signal contracts due for renegotiation.

```sql
WITH unit_at_receipt AS (
    SELECT
        i.id AS inventory_id,
        i.received_date,
        ip.id AS product_id,
        ip.product_name,
        m.name AS manufacturer,
        ph.contract_type,
        ph.list_price_usd,
        ph.contracted_price_usd,
        ROUND(
            (ph.list_price_usd - ph.contracted_price_usd) * 100.0
            / NULLIF(ph.list_price_usd, 0),
            1
        ) AS discount_pct
    FROM inventory i
    JOIN implant_lot il ON i.lot_id = il.id
    JOIN implant_product ip ON il.product_id = ip.id
    JOIN manufacturer m ON ip.manufacturer_id = m.id
    JOIN pricing_history ph
        ON ph.product_id = ip.id
       AND ph.manufacturer_id = m.id
       AND ph.effective_date <= i.received_date
       AND (ph.end_date IS NULL OR ph.end_date > i.received_date)
)
SELECT
    manufacturer,
    contract_type,
    COUNT(*) AS units_received,
    ROUND(AVG(list_price_usd), 2)        AS avg_list_price,
    ROUND(AVG(contracted_price_usd), 2)  AS avg_contracted_price,
    ROUND(AVG(discount_pct), 1)          AS avg_discount_pct,
    ROUND(SUM(list_price_usd - contracted_price_usd), 2) AS total_savings_vs_list
FROM unit_at_receipt
GROUP BY manufacturer, contract_type
ORDER BY total_savings_vs_list DESC;
```

**Expected result:** GPO contracts should land in the 10–30% discount range; Consignment shows 0% (in this model, Consignment is booked at MSRP and reconciled at the point of use). A GPO discount under 5% should trigger contract review.

---

### Query 11: Recall notifications past SLA without acknowledgment

**Business context:**
The recall coordinator watches sent-but-not-acknowledged notifications against the SLA defined by recall class (Class I 3 days, Class II 30 days, Class III 60 days), which mirrors FDA expectations.

**Category:** Date filter + CASE
**Difficulty:** Intermediate
**Business role:** Operations

**Approach:**
The driving table is `recall_notification`. Filter to `acknowledgment_date IS NULL` for "sent but not acknowledged," then join back to `recall` to get the class. The SLA threshold varies by class, so use `CASE recall_class WHEN 'Class I' THEN 3 ...` to derive the SLA days for that row, then in the WHERE clause filter with `JULIANDAY('now') - JULIANDAY(notification_date) > that CASE` to keep the overdue ones. The rest of the joins (patient, hospital, product) only exist to make the list readable and actionable. Sort by class and then by days overdue, so Class I overdue items rise to the top.

```sql
SELECT
    rn.id AS notification_id,
    r.recall_number,
    r.recall_class,
    r.recall_reason,
    rn.notification_date,
    CAST(JULIANDAY('now') - JULIANDAY(rn.notification_date) AS INTEGER) AS days_since_notification,
    CASE r.recall_class
        WHEN 'Class I' THEN 3
        WHEN 'Class II' THEN 30
        WHEN 'Class III' THEN 60
    END AS sla_days,
    rn.notified_party,
    rn.notification_method,
    p.mrn,
    p.first_name || ' ' || p.last_name AS patient_name,
    ip.product_name,
    h.name AS hospital_name
FROM recall_notification rn
JOIN recall r ON rn.recall_id = r.id
JOIN surgery_implant si ON rn.surgery_implant_id = si.id
JOIN surgery s ON si.surgery_id = s.id
JOIN patient p ON s.patient_id = p.id
JOIN hospital h ON s.hospital_id = h.id
JOIN inventory i ON si.inventory_id = i.id
JOIN implant_lot il ON i.lot_id = il.id
JOIN implant_product ip ON il.product_id = ip.id
WHERE rn.acknowledgment_date IS NULL
  AND r.status = 'Active'
  AND (JULIANDAY('now') - JULIANDAY(rn.notification_date)) > (
        CASE r.recall_class
            WHEN 'Class I' THEN 3
            WHEN 'Class II' THEN 30
            WHEN 'Class III' THEN 60
        END
      )
ORDER BY r.recall_class, days_since_notification DESC;
```

**Expected result:** Past-SLA rows rise to the top. Class I past 3 days is essentially "waiting for the regulator to find it."

---

### Query 12: Average duration by procedure

**Business context:**
The OR scheduling manager calibrates block-time using historical durations. Procedures with high variance need a wider scheduling buffer; low-variance ones can be packed tight.

**Category:** Aggregation + GROUP BY
**Difficulty:** Basic
**Business role:** Analyst

**Approach:**
The simplest query in the document; a single table `surgery` is enough. Group by (CPT code, procedure name) and compute COUNT, average / min / max duration. `WHERE duration_minutes IS NOT NULL` first eliminates rows without recorded duration, so that AVG and COUNT(*) stay on the same denominator. `HAVING COUNT(*) >= 5` filters out procedures with too few samples and unrepresentative extremes. Procedures with a large range (max minus min) have unstable duration and need a wider scheduling buffer.

```sql
SELECT
    procedure_name,
    procedure_code,
    COUNT(*) AS procedure_count,
    ROUND(AVG(duration_minutes), 1)          AS avg_duration_minutes,
    MIN(duration_minutes)                    AS min_duration,
    MAX(duration_minutes)                    AS max_duration,
    ROUND(AVG(duration_minutes) / 60.0, 1)   AS avg_duration_hours
FROM surgery
WHERE duration_minutes IS NOT NULL
GROUP BY procedure_code, procedure_name
HAVING COUNT(*) >= 5
ORDER BY procedure_count DESC;
```

**Expected result:** Average duration and extremes by CPT. TKA averaging 135 minutes with a range of 90 to 210 minutes → schedule in 2.5-hour blocks.

---

### Query 13: Lots whose most recent QC was Fail

**Business context:**
A QA engineer confirms that lots whose most recent conclusive QC was Fail have not slipped into inventory. The check is based on the raw `quality_test_event` table — the `implant_lot.quality_test_passed` boolean was deliberately removed, because a single boolean cannot express multi-stage QC.

**Category:** CTE + Window function
**Difficulty:** Advanced
**Business role:** Manager

**Approach:**
Lot QC status is not a stored boolean; it is "the most recent conclusive result." So the CTE `ranked` first restricts to `result IN ('Pass','Fail')` events (excluding `Conditional`, which is not conclusive), and uses `ROW_NUMBER() OVER (PARTITION BY lot_id ORDER BY test_date DESC)` to order each lot's tests by recency. `rn = 1 AND result = 'Fail'` identifies lots whose latest conclusive result is Fail. Then `LEFT JOIN inventory` to see whether these bad lots still have units sitting on the shelf (Available) or, worse, already used. `GROUP_CONCAT(DISTINCT h.name)` concatenates the affected hospitals into a single column.

```sql
-- "Lot QC status" = the most recent Pass/Fail result (Conditional is not conclusive).
WITH ranked AS (
    SELECT
        lot_id,
        result,
        test_date,
        ROW_NUMBER() OVER (
            PARTITION BY lot_id
            ORDER BY test_date DESC
        ) AS rn
    FROM quality_test_event
    WHERE result IN ('Pass', 'Fail')
),
failed_lots AS (
    SELECT lot_id FROM ranked WHERE rn = 1 AND result = 'Fail'
)
SELECT
    il.lot_number,
    ip.product_name,
    m.name AS manufacturer,
    il.manufacture_date,
    il.quantity_manufactured,
    COUNT(i.id) AS units_in_inventory,
    SUM(CASE WHEN i.status = 'Available' THEN 1 ELSE 0 END) AS available_units,
    SUM(CASE WHEN i.status = 'Used'      THEN 1 ELSE 0 END) AS used_units,
    GROUP_CONCAT(DISTINCT h.name) AS hospitals_affected
FROM failed_lots fl
JOIN implant_lot il ON fl.lot_id = il.id
JOIN implant_product ip ON il.product_id = ip.id
JOIN manufacturer m ON ip.manufacturer_id = m.id
LEFT JOIN inventory i ON il.id = i.lot_id
LEFT JOIN hospital h ON i.hospital_id = h.id
GROUP BY il.id, il.lot_number, ip.product_name, m.name,
         il.manufacture_date, il.quantity_manufactured
ORDER BY used_units DESC, available_units DESC;
```

**Expected result:** Ideally no row has `used_units > 0`. Any failed-lot row with `Available > 0` must be quarantined immediately.

---

### Query 14: Full-traceability adverse event report

**Business context:**
The clinical quality analyst prepares the quarterly FDA MAUDE review package. Each row carries the full UDI-DI / UDI-PI traceability chain plus clinical context.

**Category:** Multi-table Join
**Difficulty:** Advanced
**Business role:** Analyst

**Approach:**
This is a wide "wide table" report. Starting from `adverse_event`, join everything FDA MAUDE review needs in one pass: upstream through `surgery_implant` to the surgery, patient, surgeon, and hospital; and downstream through `inventory → implant_lot → implant_product → manufacturer → implant_category` for the full UDI-DI / UDI-PI traceability chain. Two derived dates deserve a callout: `patient_age` is computed as of **the surgery date** rather than `'now'` (`JULIANDAY(surgery_date) - JULIANDAY(date_of_birth)`), so age doesn't drift as the dataset ages; `days_post_surgery` is the gap from event to surgery, and because the generator enforces `event_date > implantation_timestamp`, it's always non-negative. All INNER JOINs, because every adverse event ties back to a real implanted unit.

```sql
SELECT
    ae.id AS event_id,
    ae.event_date,
    ae.event_type,
    ae.severity,
    ae.fda_mdr_number,
    p.mrn,
    -- patient_age is computed at the surgery date (not 'now'), so the semantics stay stable as the dataset ages.
    CAST((JULIANDAY(s.surgery_date) - JULIANDAY(p.date_of_birth)) / 365.25 AS INTEGER) AS patient_age,
    p.gender,
    p.allergies,
    s.surgery_date,
    CAST(JULIANDAY(ae.event_date) - JULIANDAY(s.surgery_date) AS INTEGER) AS days_post_surgery,
    s.procedure_name,
    s.surgery_type,
    si.implant_site,
    ip.product_name,
    ip.udi_di,
    i.udi_pi,
    ip.model_number,
    m.name AS manufacturer,
    ic.name AS implant_category,
    surg.first_name || ' ' || surg.last_name AS surgeon_name,
    surg.specialty,
    surg.years_experience,
    h.name AS hospital_name,
    ae.patient_outcome,
    ae.corrective_action,
    ae.reported_by,
    ae.reported_date
FROM adverse_event ae
JOIN surgery_implant si ON ae.surgery_implant_id = si.id
JOIN surgery s ON si.surgery_id = s.id
JOIN patient p ON s.patient_id = p.id
JOIN surgeon surg ON s.surgeon_id = surg.id
JOIN hospital h ON s.hospital_id = h.id
JOIN inventory i ON si.inventory_id = i.id
JOIN implant_lot il ON i.lot_id = il.id
JOIN implant_product ip ON il.product_id = ip.id
JOIN manufacturer m ON ip.manufacturer_id = m.id
JOIN implant_category ic ON ip.category_id = ic.id
ORDER BY ae.severity DESC, ae.event_date DESC;
```

**Expected result:** A fully traceable per-event detail. `days_post_surgery` is always ≥ 0 because the generator enforces `event_date > implantation_timestamp`.

---

### Query 15: Surgeons with elevated adverse event rate, volume-adjusted

**Business context:**
The Medical Director runs peer review using the unified **per-surgery event rate**, with a minimum of 20 surgeries to filter out small-sample noise.

**Category:** CTE + Window function
**Difficulty:** Advanced
**Business role:** Manager

**Approach:**
Again per-surgery, but aggregated by surgeon. The first CTE `per_surgery_events` collapses the grain to (surgeon, surgery) per row, using `MAX(CASE WHEN ae.id IS NOT NULL ...)` to flag "did this surgery have any event" (MAX because if any one of several implants in a surgery hit an event, the whole surgery counts as affected). The second CTE aggregates by surgeon, and `HAVING COUNT(*) >= 20` enforces a minimum volume threshold to filter out small-sample noise (a surgeon with 1 of 3 cases having an event shouldn't be ranked at a scary 33% rate). Finally `RANK() OVER (ORDER BY event rate DESC)` ranks the outlier surgeons, sending them into peer review.

```sql
WITH per_surgery_events AS (
    -- One row per (surgeon, surgery), flagging whether the surgery had any event.
    SELECT
        surg.id AS surgeon_id,
        s.id    AS surgery_id,
        MAX(CASE WHEN ae.id IS NOT NULL THEN 1 ELSE 0 END) AS had_event,
        MAX(CASE WHEN ae.severity IN ('Severe', 'Life-threatening') THEN 1 ELSE 0 END) AS had_serious_event
    FROM surgeon surg
    JOIN surgery s ON surg.id = s.surgeon_id
    JOIN surgery_implant si ON s.id = si.surgery_id
    LEFT JOIN adverse_event ae ON si.id = ae.surgery_implant_id
    GROUP BY surg.id, s.id
),
surgeon_metrics AS (
    -- GROUP BY lists every non-aggregated column in the SELECT (strict-SQL compatible).
    SELECT
        pse.surgeon_id,
        s.first_name,
        s.last_name,
        s.specialty,
        s.years_experience,
        COUNT(*)                AS total_surgeries,
        SUM(pse.had_event)      AS surgeries_with_event,
        SUM(pse.had_serious_event) AS surgeries_with_serious_event
    FROM per_surgery_events pse
    JOIN surgeon s ON pse.surgeon_id = s.id
    GROUP BY pse.surgeon_id, s.first_name, s.last_name, s.specialty, s.years_experience
    HAVING COUNT(*) >= 20
)
SELECT
    first_name || ' ' || last_name AS surgeon_name,
    specialty,
    years_experience,
    total_surgeries,
    surgeries_with_event,
    surgeries_with_serious_event,
    ROUND(surgeries_with_event * 100.0 / total_surgeries, 2)         AS adverse_event_rate,
    ROUND(surgeries_with_serious_event * 100.0 / total_surgeries, 2) AS serious_event_rate,
    RANK() OVER (ORDER BY surgeries_with_event * 100.0 / total_surgeries DESC) AS rate_rank
FROM surgeon_metrics
ORDER BY adverse_event_rate DESC
LIMIT 15;
```

**Expected result:** Surgeons ranked by per-surgery event rate. Outliers trigger peer review and additional training.

---

### Query 16: Inventory status distribution by hospital and storage location

**Business context:**
The materials manager wants a direct view of the current inventory status distribution at each storage location (OR Storage A, Sterile Processing, etc.). `Quarantined` indicates a QA hold; `Expired` flags waste that needs cleanup.

**Category:** Aggregation + GROUP BY
**Difficulty:** Basic
**Business role:** Operations

**Approach:**
A single-level `inventory JOIN hospital` grouped along three dimensions (hospital, location, status) is all that's needed. One point worth explaining to the reader: terminal units (`Used` / `Expired` / `Recalled`) have `location` of NULL, because location is derived from the latest movement and a terminal movement has no `to_location`. So `COALESCE(i.location, 'NO LOCATION (terminal state)')` surfaces NULL as a readable label, instead of leaving it blank and making the reader think the data is missing.

```sql
SELECT
    h.name AS hospital_name,
    COALESCE(i.location, 'NO LOCATION (terminal state)') AS storage_location,
    i.status,
    COUNT(*) AS unit_count
FROM inventory i
JOIN hospital h ON i.hospital_id = h.id
GROUP BY h.name, i.location, i.status
ORDER BY h.name, unit_count DESC;
```

**Expected result:** A clean inventory grid. Note: terminal units (`Used`, `Expired`, `Recalled`) have `location` NULL — this is by design, because location is derived from the latest movement and a terminal movement has no `to_location`.

---

### Query 17: Approval rate by FDA submission type

**Business context:**
The Director of Regulatory Affairs compares success rates across pathways. **`Withdrawn` is excluded from the denominator** — it means the process was actively withdrawn, not denied; lumping it in would conflate "withdrawn" with "denied."

**Category:** Conditional aggregation
**Difficulty:** Intermediate
**Business role:** Regulatory

**Approach:**
A single table `regulatory_submission`, grouped by (submission type, regulatory body). The core decision is the denominator for "approval rate": `Withdrawn` (active withdrawal) is excluded, because withdrawal is not denial, and including it would conflate the two. So the denominator uses `SUM(CASE WHEN status IN ('Approved','Pending','Denied') ...)`, the numerator is Approved count, with `NULLIF(..., 0)` around the denominator to avoid divide-by-zero if a group is all Withdrawn. `avg_approval_days` only computes `approval_date - submission_date` for Approved rows; other statuses have no approval date, the CASE returns NULL, and NULL is naturally skipped by AVG.

```sql
SELECT
    submission_type,
    regulatory_body,
    COUNT(*) AS total_submissions,
    SUM(CASE WHEN status = 'Approved'  THEN 1 ELSE 0 END) AS approved_count,
    SUM(CASE WHEN status = 'Pending'   THEN 1 ELSE 0 END) AS pending_count,
    SUM(CASE WHEN status = 'Denied'    THEN 1 ELSE 0 END) AS denied_count,
    SUM(CASE WHEN status = 'Withdrawn' THEN 1 ELSE 0 END) AS withdrawn_count,
    ROUND(
        SUM(CASE WHEN status = 'Approved' THEN 1 ELSE 0 END) * 100.0
        / NULLIF(
            SUM(CASE WHEN status IN ('Approved', 'Pending', 'Denied') THEN 1 ELSE 0 END),
            0
        ),
        1
    ) AS approval_rate_pct,
    ROUND(
        AVG(CASE
                WHEN status = 'Approved'
                THEN JULIANDAY(approval_date) - JULIANDAY(submission_date)
            END
        ), 0
    ) AS avg_approval_days
FROM regulatory_submission
GROUP BY submission_type, regulatory_body
ORDER BY total_submissions DESC;
```

**Expected result:** 510(k) typically lands around 90% approval and a ~145-day cycle; PMA has a lower approval rate and a much longer cycle.

---

### Query 18: Annual implant cost by hospital (gold view)

**Business context:**
The CFO's recurring "annual implant cost by hospital" rollup. This query reads from a **gold-tier view** — the view packages the joins and point-in-time price so the finance dashboard has a single trustworthy source.

**Category:** View + Aggregation
**Difficulty:** Intermediate
**Business role:** Finance

**Approach:**
First `CREATE VIEW v_hospital_monthly_implant_cost`, which wraps the "hospital → surgery → implanted unit → contract price at receipt" join chain (including the point-in-time price predicate) into a gold-tier view, so the finance dashboard has a single trustworthy source. The trap is fan-out: a surgery with multiple implants appears as multiple rows in the view, and a direct `AVG(unit_cost)` would give a wrong "average cost per surgery." The right approach is to use a CTE `per_surgery` that first does `SUM(unit_cost)` at the **surgery grain** to get the total cost per surgery, then aggregate at (hospital, year) outside; that way `avg_cost_per_surgery` is "per surgery," not "per implant."

```sql
-- Gold-tier view — define once, use everywhere.
CREATE VIEW IF NOT EXISTS v_hospital_monthly_implant_cost AS
SELECT
    h.id   AS hospital_id,
    h.name AS hospital_name,
    h.city,
    h.state,
    STRFTIME('%Y', s.surgery_date)    AS fiscal_year,
    STRFTIME('%Y-%m', s.surgery_date) AS fiscal_month,
    s.id                              AS surgery_id,
    si.id                             AS surgery_implant_id,
    i.id                              AS inventory_id,
    ip.id                             AS product_id,
    -- Contract price at the unit's receipt time
    ph.contracted_price_usd           AS unit_cost_at_receipt
FROM hospital h
JOIN surgery s ON h.id = s.hospital_id
JOIN surgery_implant si ON s.id = si.surgery_id
JOIN inventory i  ON si.inventory_id = i.id
JOIN implant_lot il ON i.lot_id = il.id
JOIN implant_product ip ON il.product_id = ip.id
LEFT JOIN pricing_history ph
    ON ph.product_id      = ip.id
   AND ph.manufacturer_id = ip.manufacturer_id
   AND ph.effective_date <= i.received_date
   AND (ph.end_date IS NULL OR ph.end_date > i.received_date);

-- Use the view:
WITH per_surgery AS (
    SELECT
        hospital_id, hospital_name, city, state, fiscal_year,
        surgery_id,
        COUNT(*)                   AS implants_per_surgery,
        SUM(unit_cost_at_receipt)  AS cost_per_surgery
    FROM v_hospital_monthly_implant_cost
    WHERE fiscal_year >= STRFTIME('%Y', DATE('now', '-1 year'))
    GROUP BY hospital_id, hospital_name, city, state, fiscal_year, surgery_id
)
SELECT
    hospital_name,
    city,
    state,
    fiscal_year,
    COUNT(*)                              AS total_surgeries,
    SUM(implants_per_surgery)             AS total_implants_used,
    ROUND(AVG(implants_per_surgery), 2)   AS avg_implants_per_surgery,
    ROUND(SUM(cost_per_surgery), 2)       AS total_implant_cost,
    ROUND(AVG(cost_per_surgery), 2)       AS avg_cost_per_surgery
FROM per_surgery
GROUP BY hospital_name, city, state, fiscal_year
ORDER BY total_implant_cost DESC;
```

**Expected result:** Annual cost by hospital plus a **correct "average implants per surgery"** — the fan-out bug is fixed by aggregating at the surgery grain in the CTE first, rather than averaging per-implant rows directly.

---

### Query 19: Recall response SLA compliance (gold view)

**Business context:**
The recall coordinator runs a weekly read of MAOHN recall notification SLA performance. This query reads from a gold-tier view that pre-computes per-recall SLA.

**Category:** View + CTE
**Difficulty:** Advanced
**Business role:** Manager

**Approach:**
First create the gold-tier view `v_recall_response_sla`, which uses `LEFT JOIN recall_notification` (the LEFT is critical: a recall may have no notifications at all yet, and those "zero-notification" recalls are exactly the most dangerous ones — they can't be filtered out by INNER JOIN) to spread each recall together with its notifications, and computes `days_to_notify` and the class-based `sla_notify_days` along the way. The outer query aggregates per recall: notification count, ack count, ack rate, average and max time to notify, plus past-SLA notification count and percentage. Class I rows with `pct_past_sla` greater than 0 should be escalated immediately.

```sql
CREATE VIEW IF NOT EXISTS v_recall_response_sla AS
SELECT
    r.id            AS recall_id,
    r.recall_number,
    r.recall_class,
    r.recall_date,
    r.status        AS recall_status,
    rn.id           AS notification_id,
    rn.notification_date,
    rn.acknowledgment_date,
    JULIANDAY(rn.notification_date)  - JULIANDAY(r.recall_date)        AS days_to_notify,
    JULIANDAY(rn.acknowledgment_date) - JULIANDAY(rn.notification_date) AS days_to_ack,
    CASE r.recall_class
        WHEN 'Class I'   THEN 3
        WHEN 'Class II'  THEN 30
        WHEN 'Class III' THEN 60
    END AS sla_notify_days
FROM recall r
LEFT JOIN recall_notification rn ON r.id = rn.recall_id;

SELECT
    recall_number,
    recall_class,
    recall_date,
    recall_status,
    COUNT(notification_id)                                   AS notifications_sent,
    SUM(CASE WHEN acknowledgment_date IS NOT NULL THEN 1 ELSE 0 END) AS acknowledgments_received,
    ROUND(
        SUM(CASE WHEN acknowledgment_date IS NOT NULL THEN 1 ELSE 0 END) * 100.0
        / NULLIF(COUNT(notification_id), 0),
        1
    ) AS acknowledgment_rate_pct,
    ROUND(AVG(days_to_notify), 1)               AS avg_days_to_notify,
    MAX(days_to_notify)                         AS max_days_to_notify,
    SUM(CASE WHEN days_to_notify > sla_notify_days THEN 1 ELSE 0 END) AS notifications_past_sla,
    ROUND(
        SUM(CASE WHEN days_to_notify > sla_notify_days THEN 1 ELSE 0 END) * 100.0
        / NULLIF(COUNT(notification_id), 0),
        1
    ) AS pct_past_sla
FROM v_recall_response_sla
GROUP BY recall_id, recall_number, recall_class, recall_date, recall_status
ORDER BY recall_class, pct_past_sla DESC;
```

**Expected result:** Each row shows notification count, ack rate, average and max time to notify, and past-SLA percentage. Class I rows with `pct_past_sla > 0` must be escalated immediately.

---

### Query 20: 2-year revision rate per patient

**Business context:**
The clinical quality analyst measures the 24-month revision rate — the flagship outcomes metric in orthopedics. Use the `surgery.revision_of_surgery_id` self-referencing FK to identify revision events, and join `patient_followup_visit` to surface potential cases where revision has been indicated but not yet performed.

**Category:** CTE + Self-join
**Difficulty:** Advanced
**Business role:** Analyst

**Approach:**
The denominator of revision rate has to be precise. `first_per_patient` uses `ROW_NUMBER() OVER (PARTITION BY patient_id ORDER BY surgery_date)` to pick out the true first (index case) among each patient's **non-revision** surgeries; otherwise a bilateral knee replacement (one patient with two primary surgeries) would inflate the denominator. `index_surgeries` attaches index cases to their implants to get manufacturer and procedure. `revisions` uses the `surgery.revision_of_surgery_id` self-referencing FK to find revision events. `revision_flags` uses `LEFT JOIN` to attach revisions back to index cases and `JULIANDAY(revision_date) - JULIANDAY(index_date) <= 730` to enforce the 2-year window; it also uses an `EXISTS` subquery on `patient_followup_visit` to flag cases where `revision_indicated` has been set but no revision has occurred yet. Finally, group by (manufacturer, procedure) and compute the revision rate, with `HAVING COUNT(*) >= 5` to filter out small samples.

```sql
WITH first_per_patient AS (
    -- Each patient's true first non-revision implant surgery.
    -- A patient with two independent primary knee replacements (bilateral)
    -- still contributes only 1 index case; the denominator isn't inflated.
    SELECT
        s.id           AS surgery_id,
        s.patient_id,
        s.procedure_code,
        s.procedure_name,
        s.surgery_date,
        ROW_NUMBER() OVER (
            PARTITION BY s.patient_id
            ORDER BY s.surgery_date ASC, s.id ASC
        ) AS rn
    FROM surgery s
    WHERE s.revision_of_surgery_id IS NULL
),
index_surgeries AS (
    SELECT
        fpp.surgery_id   AS index_surgery_id,
        fpp.patient_id,
        fpp.procedure_code,
        fpp.procedure_name,
        fpp.surgery_date AS index_date,
        ip.id  AS product_id,
        m.name AS manufacturer
    FROM first_per_patient fpp
    JOIN surgery_implant si ON fpp.surgery_id = si.surgery_id
    JOIN inventory i  ON si.inventory_id = i.id
    JOIN implant_lot il ON i.lot_id = il.id
    JOIN implant_product ip ON il.product_id = ip.id
    JOIN manufacturer m ON ip.manufacturer_id = m.id
    WHERE fpp.rn = 1
),
revisions AS (
    SELECT
        rev.revision_of_surgery_id AS index_surgery_id,
        rev.surgery_date           AS revision_date
    FROM surgery rev
    WHERE rev.revision_of_surgery_id IS NOT NULL
),
revision_flags AS (
    SELECT
        idx.product_id,
        idx.manufacturer,
        idx.procedure_name,
        idx.index_surgery_id,
        CASE
            WHEN r.revision_date IS NOT NULL
                 AND (JULIANDAY(r.revision_date) - JULIANDAY(idx.index_date)) <= 730
            THEN 1 ELSE 0
        END AS revised_within_2y,
        CASE
            WHEN EXISTS (
                SELECT 1 FROM patient_followup_visit f
                JOIN surgery_implant si2 ON f.surgery_implant_id = si2.id
                WHERE si2.surgery_id = idx.index_surgery_id
                  AND f.revision_indicated = TRUE
            ) THEN 1 ELSE 0
        END AS revision_indicated_in_followup
    FROM index_surgeries idx
    LEFT JOIN revisions r ON idx.index_surgery_id = r.index_surgery_id
)
SELECT
    manufacturer,
    procedure_name,
    COUNT(*) AS index_cases,
    SUM(revised_within_2y) AS revisions_within_2y,
    SUM(revision_indicated_in_followup) AS revision_indicated_followup_count,
    ROUND(SUM(revised_within_2y) * 100.0 / COUNT(*), 2) AS revision_rate_pct
FROM revision_flags
GROUP BY manufacturer, procedure_name
HAVING COUNT(*) >= 5
ORDER BY revision_rate_pct DESC;
```

**Expected result:** 2-year revision rate by (manufacturer, procedure). Anything above 5% warrants deeper investigation; `revision_indicated_followup_count` is a leading indicator of revisions that haven't happened yet but are very likely to.

---

## Category Summary

A query can belong to multiple categories — the counts below deliberately double-count, so learners can find every example by technique.

| Category | Count | Query IDs |
|---|---|---|
| Aggregation | 6 | 1, 4, 9, 12, 16, 17 |
| Multi-table Join | 5 | 2, 8, 11, 14, 18 |
| Window function | 4 | 3, 7, 13, 20 |
| Date / time analysis | 3 | 5, 7, 11 |
| CTE / subquery | 9 | 1, 4, 6, 10, 13, 15, 18, 19, 20 |
| Self-join / self-referencing FK | 1 | 20 |
| Gold-tier view | 2 | 18, 19 |

## Business Role Coverage

| Role | Count | Query IDs |
|---|---|---|
| Executive | 2 | 1, 7 |
| Manager | 5 | 2, 3, 13, 15, 19 |
| Analyst | 5 | 4, 9, 12, 14, 20 |
| Operations | 4 | 5, 8, 11, 16 |
| Finance | 2 | 10, 18 |
| Regulatory | 2 | 6, 17 |

## Difficulty Distribution

Each query is assigned to exactly one bucket.

| Difficulty | Count | Query IDs |
|---|---|---|
| Basic | 3 | 1, 12, 16 |
| Intermediate | 9 | 3, 4, 5, 6, 7, 9, 11, 17, 18 |
| Advanced | 8 | 2, 8, 10, 13, 14, 15, 19, 20 |

---

## Notes

- All queries are written in SQLite 3.x syntax. Window functions require SQLite 3.25+.
- All temporal invariants (`event_date > implantation_timestamp`, `notification_date > recall_date`, etc.) are enforced by the generator, so derived date-difference columns like `days_post_surgery` are guaranteed non-negative.
- Q2 and Q8 use the same canonical join to handle **lot-level** and **full-product** recalls together.
- All pricing queries use **the point-in-time price at the unit's `received_date`**, not a single denormalized `unit_cost`. That is the correct definition for a Cost of Goods Sold (COGS) report.
- Gold-tier views (Q18, Q19) only need to be defined once per database and are reusable; in production they would be materialized for performance.
- Queries that reference `DATE('now')` assume a fresh dataset; the generator anchors all dates at a fixed `NOW` constant, so the dataset's time will drift away from `DATE('now')` as time passes. Regenerate before reusing.
