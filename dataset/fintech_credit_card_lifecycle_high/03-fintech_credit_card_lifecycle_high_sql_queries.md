# Fintech Consumer Credit Card Lifecycle SQL Query Set

This document accompanies the `fintech_credit_card_lifecycle_high` dataset. Before reading it, please first read the business context in `01-fintech_credit_card_lifecycle_high_business_context.md` and the data structure in `02-fintech_credit_card_lifecycle_high_er_document.md`. If you're unclear on the "why" behind any of the analysis here, check the companion analytics primer `05-fintech_credit_card_lifecycle_high_analytics_primer.md`.

---

## 1. About REFERENCE_DATE

The entire dataset is anchored to a fixed reference date, `REFERENCE_DATE = 2026-06-30`. Every query that needs "today / current" semantics uses this literal date, `'2026-06-30'`, instead of `DATE('now')`. That way the results are identical no matter what day you run the query, which makes it easy to check answers. Concepts like account age (months_on_book) and whether something has matured are also all measured against this date.

---

## 2. How to use this document

This document is written for an analyst who just joined Keystone Card Company (could be a Business Analyst, could be a Data Scientist). Your manager has handed you these 20 queries and said "get through these this week." Every query follows the same five-part structure:

1. **Business context**: who's asking, why now, and what decision the answer feeds into.
2. **Tags**: SQL category, difficulty, business role.
3. **Approach**: before you see the SQL, a clear explanation of how to attack the problem, which tables to use, and why they're joined the way they are.
4. **SQL code**: runs directly on SQLite.
5. **Expected results and business conclusion**: what the output looks like, what the key numbers are, and what to do with them.

Every query traces back to a specific business question in the business context document. There's a mapping table at the end of this document. The SQL here is meant to be read and learned from, not just run. Pay close attention to the comments — they explain why a LEFT JOIN is used instead of an INNER JOIN, why NTILE is used, and why the grouping is done on a particular column.

---

## 3. Query index

| No. | Title | Business role | SQL category | Difficulty |
|------|------|----------|----------|------|
| Q1 | Acquisition funnel conversion | VP of Acquisitions | Aggregation | Basic |
| Q2 | Response model decile validation | Head of Card Intelligence | Window functions | Intermediate |
| Q3 | Underwriting score discrimination (overall) | Head of Card Intelligence | Window + CASE | Intermediate |
| Q4 | Underwriting score breaks down in Subprime | Data Scientist | Window + Join + Filter | Advanced |
| Q5 | Approval rate and booked FICO by risk tier | VP of Underwriting | Aggregation + Join | Basic |
| Q6 | Channel adverse selection | CMO | Aggregation + Join | Intermediate |
| Q7 | Loss-adjusted true acquisition value by channel | CMO | Multiple CTEs + LEFT JOIN | Advanced |
| Q8 | Portfolio utilization distribution | VP of Portfolio Management | CTE + Window | Intermediate |
| Q9 | Credit Line Increase (CLI) adverse selection | Chief Credit Officer | Join + CASE | Intermediate |
| Q10 | Delinquency bucket distribution (roll snapshot) | Collections Manager | CTE + Aggregation | Basic |
| Q11 | Full P&L across the product ladder | CFO | Multiple CTEs + Join | Advanced |
| Q12 | Transactor vs Revolver per-account contribution | Product Manager | CTE + Join | Intermediate |
| Q13 | Promo APR cliff | Data Scientist | Conditional aggregation + Time series | Advanced |
| Q14 | Interchange breakdown by MCC | CFO | Join + Aggregation | Basic |
| Q15 | Bonus churner negative LTV | VP of Acquisitions | CTE + Join | Intermediate |
| Q16 | Vintage loss curve | Chief Risk Officer | Date + Conditional aggregation | Intermediate |
| Q17 | Underwriting standards drifting over time | Chief Risk Officer | Date functions | Intermediate |
| Q18 | Champion vs Challenger performance | CMO | Join + Aggregation | Basic |
| Q19 | Rewards eroding interchange | CFO | CTE + Join | Intermediate |
| Q20 | Monthly new account trend | Data Analyst | Date + Aggregation | Basic |

---

## 4. Queries

### Q1. Acquisition funnel conversion

**Business context.** The VP of Acquisitions has to report the health of the acquisition funnel to leadership every month. A card goes through several gates on its way from "prescreen letter mailed" to "actually activated": mailing (prescreen) to response, response to formal application, application to underwriting approval, approval to activation. Customers drop off at every gate. She needs to see the conversion rate at each stage at a glance, so she can tell whether the problem is weak marketing reach, overly tight underwriting, or drop-off at activation. This query maps to business question Q_funnel.

**Tags.** Aggregation | Basic | VP of Acquisitions.

**Approach.** This is actually **two independent funnels**, not one chain, and that has to be established up front. The first is the **prescreen response funnel**: mailing (`prescreen_offer`) to response. The second is the **application conversion funnel**: submitted application (`application`) to underwriting approval to activated account (`account`). The two live in different tables with no direct foreign key link between them — the applicant pool includes prescreen responders as well as organic traffic and branch referrals, so you **cannot** treat "number of responses" as the upstream count for "number of applications" (responses are just over 1,000, while applications are 18,000 — they're not on the same chain). The approach is to compute absolute counts for each stage independently within its own table, then cross join a handful of single-row CTEs to display them side by side in one row. Approval rate = approvals / applications, activation rate = booked accounts / approvals; response rate is computed separately as responses / letters mailed.

```sql
WITH pres AS (
    SELECT COUNT(*) AS mailed, SUM(responded) AS responded
    FROM prescreen_offer
),
app AS (
    SELECT COUNT(*) AS apps,
           SUM(CASE WHEN decision = 'APPROVED' THEN 1 ELSE 0 END) AS approved
    FROM application
),
acct AS (
    SELECT COUNT(*) AS booked FROM account
)
SELECT pres.mailed,
       pres.responded,
       app.apps,
       app.approved,
       acct.booked,
       ROUND(100.0 * app.approved / app.apps, 1) AS approval_rate,
       ROUND(100.0 * acct.booked / app.approved, 1) AS activation_rate
FROM pres, app, acct;
```

**Expected results and business conclusion.** One row, read as two independent funnels. Prescreen response funnel: roughly 20,000 prescreen letters mailed, only about 1,040 people responded (response rate around 5%). Application conversion funnel: roughly 18,000 applications (including prescreen responders, organic traffic, and branch referrals), about 10,400 approved (approval rate around 58%), and ultimately about 8,900 accounts activated (activation rate around 86%). Conclusion: both the underwriting approval rate and the activation rate look healthy; the real bottleneck is the 5% response rate on the marketing side. The next step is to shift budget toward channels with higher response rates, which leads directly into Q2 (response model) and Q6 (channel quality).

---

### Q2. Response model decile validation

**Business context.** The Head of Card Intelligence (head of data science) needs to sign off on the "response model" the marketing team uses. This model assigns every name on the prescreen list a score from 0 to 999, predicting whether that person will respond to the mailer. If the model works, people with higher scores should actually respond at a higher rate. The data scientist needs to lay the predicted score next to the actual outcome (`responded`) and check whether the model has any discriminating power. This is the most basic form of model evaluation, and the step that precedes drawing an ROC curve and computing AUC. This query maps to business question Q_responsemodel.

**Tags.** Window functions | Intermediate | Head of Card Intelligence.

**Approach.** The standard play for "does a higher score mean a higher response rate" is to **bucket by score and check the actual rate bucket by bucket**. Use the window function `NTILE(10)` to slice the population into 10 equally sized deciles by `response_model_score` — decile 1 is the bottom 10% of scores, decile 10 is the top 10%. Then compute the actual response rate within each decile. Note that SQLite won't let you reference a window function's alias directly inside `GROUP BY`, so you need to compute the decile in a CTE first, then group by it in the outer query. If the response rate rises monotonically with decile, the model has real discriminating power.

```sql
WITH scored AS (
    SELECT response_model_score,
           responded,
           NTILE(10) OVER (ORDER BY response_model_score) AS decile
    FROM prescreen_offer
)
SELECT decile,
       COUNT(*) AS n,
       ROUND(AVG(response_model_score), 0) AS avg_score,
       ROUND(100.0 * SUM(responded) / COUNT(*), 2) AS actual_response_rate
FROM scored
GROUP BY decile
ORDER BY decile;
```

**Expected results and business conclusion.** 10 rows. The response rate climbs monotonically from about 2.0% in decile 1 to about 8.7% in decile 10 — the top decile responds at roughly 4 times the rate of the bottom decile. Conclusion: the response model works and discriminates well. Marketing should concentrate the prescreen budget on the top score bands (deciles 8 through 10) and cut back on the low bands. This is the early version of Capital One-style "personalize every offer."

---

### Q3. Underwriting score discrimination (overall)

**Business context.** Same Head of Card Intelligence, but this time looking at the underwriting-side "risk model." Every application gets an `underwriting_score` at underwriting time (0 to 999, higher meaning the model thinks it's safer). If the model works, accounts that get booked should show a lower charge-off rate the higher their score. Quarterly model monitoring starts by checking overall discrimination. This query maps to business question Q_underwriting (underwriting model calibration).

**Tags.** Window + CASE | Intermediate | Head of Card Intelligence.

**Approach.** Same playbook as Q2, just swapping "response" for "charge-off." Use `NTILE(10)` to slice accounts into deciles by `underwriting_score`, then compute the charge-off rate in each decile. Whether an account charged off is determined by `account_status = 'CHARGED_OFF'`, converted to 0/1 with `CASE WHEN ... THEN 1 ELSE 0 END` and summed. Ordering from lowest to highest score, we expect the charge-off rate to trend downward overall (with noise — not strictly monotonic decile by decile, and a middle decile or two may tick back up). This is the most direct way to evaluate a risk model's rank-ordering power. Compute the decile and the 0/1 label in a CTE first, then group in the outer query.

```sql
WITH ranked AS (
    SELECT a.id,
           a.underwriting_score,
           CASE WHEN a.account_status = 'CHARGED_OFF' THEN 1 ELSE 0 END AS co,
           NTILE(10) OVER (ORDER BY a.underwriting_score) AS score_decile
    FROM account a
)
SELECT score_decile,
       COUNT(*) AS n,
       ROUND(100.0 * SUM(co) / COUNT(*), 2) AS chargeoff_rate
FROM ranked
GROUP BY score_decile
ORDER BY score_decile;
```

**Expected results and business conclusion.** 10 rows. The charge-off rate slides from about 9.7% in the lowest score band down to about 3.2% in the highest, overall. Conclusion: at the aggregate level, the underwriting model does discriminate — the score really does rank-order risk. Everything looks fine on the surface. But "fine in aggregate" often hides local breakdowns, which is why the next step is to slice further, exactly what Q4 exposes.

---

### Q4. Underwriting score breaks down in Subprime

**Business context.** Following on from Q3. A seasoned data scientist develops an instinct that a good overall AUC doesn't mean every subgroup is well served. She suspects the underwriting model may have already broken down for certain segments, masked by the overall number. She decides to isolate the riskiest segment, Subprime (band D), and check it on its own: within this band, can the underwriting score still rank-order risk? If not, the model is effectively guessing for these customers, and band D needs its own retrained model. This query maps to business question Q_underwriting.

**Tags.** Window + Join + Filter | Advanced | Data Scientist.

**Approach.** The key move here is **filter first, then bucket**. First join `credit_band` to bring in `band_code`, filter with `WHERE band_code = 'D'` to keep only Subprime accounts, then use `NTILE(5)` within this subset to slice by underwriting score into quintiles (band D doesn't have that many accounts, so 5 buckets is more stable than 10). Check the charge-off rate in each bucket. If it decreases monotonically with score, the model works within band D; if it bounces around with no trend, the model has effectively failed for band D. This only works correctly if the filter is applied before the windowing — otherwise NTILE would slice across all accounts, and the deciles wouldn't reflect "within band D" at all.

```sql
WITH d AS (
    SELECT a.id,
           a.underwriting_score,
           CASE WHEN a.account_status = 'CHARGED_OFF' THEN 1 ELSE 0 END AS co,
           NTILE(5) OVER (ORDER BY a.underwriting_score) AS score_quintile
    FROM account a
    JOIN credit_band b ON a.credit_band_id = b.id
    WHERE b.band_code = 'D'
)
SELECT score_quintile,
       COUNT(*) AS n,
       ROUND(100.0 * SUM(co) / COUNT(*), 2) AS chargeoff_rate
FROM d
GROUP BY score_quintile
ORDER BY score_quintile;
```

**Expected results and business conclusion.** 5 rows. The charge-off rate bounces around between roughly 9% and 14% with no pattern (for example 12%, 11%, 14%, 9%, 11%), showing no downward trend with score whatsoever. Compared with the clean downward curve in Q3, this is hard evidence that the underwriting model has lost its discriminating power within Subprime. Conclusion: escalate this finding to the model risk committee immediately, and either train a dedicated sub-model for band D or bring in new features. Until then, credit lines and offers for band D should be treated conservatively. This is the flagship analysis this dataset is built for the Data Scientist role to uncover.

---

### Q5. Approval rate and booked FICO by risk tier

**Business context.** The VP of Underwriting has to report on the current underwriting posture at the credit policy review meeting. He needs a table showing how many applications each risk tier (A through E) received, how many were approved, and the average FICO of the approved accounts. This table is the foundation for understanding "who exactly are we extending credit to," and it's the backdrop for all the risk analysis that follows. This query maps to business question Q_underwriting.

**Tags.** Aggregation + Join | Basic | VP of Underwriting.

**Approach.** A single-table aggregation with one dimension join. Start from `application`, join `credit_band` to bring in `band_code` and `band_name`, and group by tier. The approval rate is `CASE WHEN decision='APPROVED'` summed and divided by the total. For average booked FICO, only approved rows should count, so use `CASE WHEN decision='APPROVED' THEN fico_at_application END` (rejected applications return NULL, and AVG automatically ignores NULLs). This is the common "conditional aggregation" trick.

```sql
SELECT b.band_code,
       b.band_name,
       COUNT(*) AS apps,
       ROUND(100.0 * SUM(CASE WHEN ap.decision = 'APPROVED' THEN 1 ELSE 0 END) / COUNT(*), 1) AS approval_rate,
       ROUND(AVG(CASE WHEN ap.decision = 'APPROVED' THEN ap.fico_at_application END), 0) AS avg_booked_fico
FROM application ap
JOIN credit_band b ON ap.credit_band_id = b.id
GROUP BY b.band_code, b.band_name
ORDER BY b.band_code;
```

**Expected results and business conclusion.** 5 rows. The approval rate decreases with tier: about 95% for A, 80% for B, 59% for C, 40% for D, and 18% for E. Booked FICO decreases from about 804 for A down to about 581 for E. Conclusion: the overall underwriting posture makes sense (higher risk gets approved less). The portfolio skews toward near-prime (C), consistent with Keystone's market positioning. There's no trap hidden in this table itself, but it's the baseline against which Q16 and Q17 (underwriting loosening over time) get compared.

---

### Q6. Channel adverse selection

**Business context.** The CMO runs into an awkward problem at the quarterly marketing review. The affiliate channel (affiliate_partner) looks like a bargain based on acquisition cost (2 dollars per contact) and has a high approval rate, so the team keeps wanting to increase its budget. But the CRO has quietly flagged that accounts sourced from affiliate later show an alarmingly high charge-off rate. The CMO needs a table that puts each channel's acquisition cost next to the charge-off rate of the accounts it brought in, to see whether "the cheap channel is actually expensive." This query maps to business question Q_channel (channel adverse selection).

**Tags.** Aggregation + Join | Intermediate | CMO.

**Approach.** Start from `account` (since charge-off is an account-level fact), join `marketing_channel` to bring in the channel name and contact cost, and group by channel. The charge-off rate uses the same `CASE WHEN account_status='CHARGED_OFF'` trick. The key is to put `cost_per_contact_usd` and `chargeoff_rate` side by side in the same row so the "cheap but bad debt" contradiction is immediately visible. Order by charge-off rate descending so the worst channel shows up first.

```sql
SELECT mc.channel_name,
       mc.cost_per_contact_usd,
       COUNT(*) AS booked,
       ROUND(100.0 * SUM(CASE WHEN a.account_status = 'CHARGED_OFF' THEN 1 ELSE 0 END) / COUNT(*), 2) AS chargeoff_rate
FROM account a
JOIN marketing_channel mc ON a.acquisition_channel_id = mc.id
GROUP BY mc.channel_name, mc.cost_per_contact_usd
ORDER BY chargeoff_rate DESC;
```

**Expected results and business conclusion.** 6 rows. affiliate_partner tops the list with a charge-off rate of about 12.5%, roughly 3 times the two cheapest channels; yet its contact cost (2.00) is actually lower than digital (4.50) and social (3.20) — only direct_mail (0.85) and prescreen_mail (1.10) are cheaper, and these two cheaper channels land at the very bottom of the charge-off ranking (direct_mail about 4.0%, prescreen_mail about 4.2%, both less than a third of affiliate's rate). This is adverse selection at work: a channel with a modest acquisition cost and a high approval rate is bringing in the worst customers. Conclusion: budget cannot be allocated based on acquisition cost (CPA) alone — it needs to reflect loss-adjusted value, which is exactly what Q7 computes. Recommend freezing further budget growth for affiliate for now.

---

### Q7. Loss-adjusted true acquisition value by channel

**Business context.** Following on from Q6. The CMO is now convinced, and needs a metric that can actually guide budget allocation: how much net charge-off loss, on average, does each booked account from each channel generate? Putting this "loss cost" next to the acquisition cost is what lets you compute the channel's true unit economics. This is the key step in moving from the vanity metric CPA to risk-adjusted unit economics. This query maps to business question Q_channel.

**Tags.** Multiple CTEs + LEFT JOIN | Advanced | CMO.

**Approach.** Two pieces of information need to be combined: the account count per channel (from `account`), and the net charge-off loss per channel (from `charge_off`, where net loss = charged-off balance minus recovery). Since not every account charges off, the path from channel to loss must go through a LEFT JOIN, or channels with no charge-offs would disappear entirely. The first CTE uses `marketing_channel LEFT JOIN account` to count accounts (guaranteeing every channel appears), the second CTE aggregates net loss per channel from `account JOIN charge_off`, and the outer query LEFT JOINs the two together, using `COALESCE(net_loss, 0)` to backfill zero for channels with no losses. Net loss per booked account = net loss / account count.

```sql
WITH ch AS (
    SELECT mc.id,
           mc.channel_name,
           mc.cost_per_contact_usd,
           COUNT(a.id) AS booked,
           SUM(CASE WHEN a.account_status = 'CHARGED_OFF' THEN 1 ELSE 0 END) AS co
    FROM marketing_channel mc
    LEFT JOIN account a ON a.acquisition_channel_id = mc.id
    GROUP BY mc.id
),
loss AS (
    SELECT a.acquisition_channel_id AS cid,
           SUM(co.charged_off_balance_usd - co.recovery_amount_usd) AS net_loss
    FROM account a
    JOIN charge_off co ON co.account_id = a.id
    GROUP BY a.acquisition_channel_id
)
SELECT ch.channel_name,
       ch.cost_per_contact_usd,
       ch.booked,
       ROUND(100.0 * ch.co / ch.booked, 2) AS co_rate,
       ROUND(COALESCE(loss.net_loss, 0) / ch.booked, 0) AS net_loss_per_booked
FROM ch
LEFT JOIN loss ON loss.cid = ch.id
ORDER BY net_loss_per_booked DESC;
```

**Expected results and business conclusion.** 6 rows. affiliate_partner's net loss per booked account is about 625 dollars, roughly 3.8 times prescreen_mail's (about 165 dollars). Put alongside Q6's low contact cost, the conclusion is hard to argue with: the few dollars saved on acquisition cost per account through affiliate are completely swamped by hundreds of dollars in charge-off losses. Recommend shifting budget from affiliate toward prescreen_mail and branch_referral (the lowest-loss channels), and requiring the affiliate partner to improve traffic quality before any further budget increase is considered.

---

### Q8. Portfolio utilization distribution

**Business context.** The VP of Portfolio Management needs to prepare a portfolio utilization distribution chart for the risk committee. Utilization = balance / credit limit, a core measure of how close to their limit customers are running. High-utilization accounts drive interest income (good) but also sit closer to the edge of default (bad). He needs to know how many accounts are currently clustered in high-utilization bands, since that directly bears on portfolio fragility and CECL provisioning. This query maps to business question Q_portfolio.

**Tags.** CTE + Window | Intermediate | VP of Portfolio Management.

**Approach.** Every account has many statement periods; we only need the utilization from the most recent one as the current snapshot. Take the statement with the highest `cycle_month` for each account. There are two common ways to do this: the window function `ROW_NUMBER`, or computing `MAX(cycle_month)` per account first and joining back. This uses the latter (more intuitive) approach: one CTE computes the max `cycle_month` per account, then joins back to `statement` to pull that row. Then `CASE` buckets `utilization_pct` into (0-30, 30-60, 60-90, 90+) and counts each bucket.

```sql
WITH latest AS (
    SELECT account_id, MAX(cycle_month) AS mx
    FROM statement
    GROUP BY account_id
),
s AS (
    SELECT st.*
    FROM statement st
    JOIN latest l ON st.account_id = l.account_id AND st.cycle_month = l.mx
)
SELECT CASE
           WHEN utilization_pct < 30 THEN '0-30'
           WHEN utilization_pct < 60 THEN '30-60'
           WHEN utilization_pct < 90 THEN '60-90'
           ELSE '90+'
       END AS util_bucket,
       COUNT(*) AS n,
       ROUND(AVG(statement_balance_usd), 0) AS avg_balance
FROM s
GROUP BY util_bucket
ORDER BY util_bucket;
```

**Expected results and business conclusion.** 4 rows. A sizable share of accounts (about 47%) fall into the 90%+ high-utilization bucket, with an average balance of about 5,800 dollars — mostly revolvers. Conclusion: the portfolio has a meaningful concentration of high-utilization accounts, which is both a source of interest income and a concentration of risk. This is exactly the population Q9 (CLI adverse selection) needs to watch closely, since increasing their credit lines could backfire.

---

### Q9. Credit Line Increase (CLI) adverse selection

**Business context.** The Chief Credit Officer needs to review last year's Credit Line Increase (CLI) strategy. The conventional logic is: give "good customers" who use their cards actively and run high utilization a credit line increase, so they spend more. But he's worried about one thing — could the people who were already running utilization above 70% before their increase actually be the ones closest to the edge? Giving them more credit might be like pouring gasoline on a fire. He needs to group by pre-CLI utilization and compare charge-off rates. This query maps to business question Q_cli (CLI adverse selection).

**Tags.** Join + CASE | Intermediate | Chief Credit Officer.

**Approach.** The key field is `credit_line_change.pre_change_utilization_pct` (utilization right before the increase), a field the dataset specifically embeds for this analysis. Filter `credit_line_change` for `change_type='CLI'` events, join back to `account` to get charge-off status, and use `CASE` to split into two groups by whether pre-CLI utilization exceeded 70%, computing the charge-off rate for each. Since an account could in theory receive multiple credit line increases, use `COUNT(DISTINCT a.id)` to deduplicate more safely. Comparing the two groups' charge-off rates reveals the adverse selection.

```sql
SELECT CASE
           WHEN clc.pre_change_utilization_pct > 70 THEN 'pre-CLI util > 70%'
           ELSE 'pre-CLI util <= 70%'
       END AS segment,
       COUNT(DISTINCT a.id) AS n,
       ROUND(100.0 * SUM(CASE WHEN a.account_status = 'CHARGED_OFF' THEN 1 ELSE 0 END) / COUNT(DISTINCT a.id), 2) AS chargeoff_rate
FROM credit_line_change clc
JOIN account a ON clc.account_id = a.id
WHERE clc.change_type = 'CLI'
GROUP BY segment
ORDER BY chargeoff_rate DESC;
```

**Expected results and business conclusion.** 2 rows. Accounts with pre-CLI utilization above 70% show a charge-off rate of about 10.6%, versus only about 3.0% for those at or below 70% — a roughly 3.6x difference. Conclusion: the current CLI strategy shows clear adverse selection — the rule "high utilization means give a credit line increase" is effectively adding leverage to the riskiest customers. Recommend changing the CLI approval rule so high-utilization accounts are evaluated on repayment behavior first, rather than getting an increase just because they use their cards heavily. This alone should directly reduce future charge-off losses.

---

### Q10. Delinquency bucket distribution (roll snapshot)

**Business context.** The Collections Manager needs a "delinquency snapshot" every Monday morning: how many accounts in the current portfolio are current (CURRENT), and how many fall into each delinquency bucket (DPD30, DPD60, DPD90, DPD120PLUS). This is the starting point for scheduling the collections team and forecasting losses. The deeper the delinquency, the lower the odds of recovery. This query maps to business question Q_collections.

**Tags.** CTE + Aggregation | Basic | Collections Manager.

**Approach.** Same as Q8: take each account's most recent statement as its current status first. One CTE computes `MAX(cycle_month)` per account, then joins back to pull the `dpd_bucket` from the latest statement. Then count by delinquency bucket and compute the share (using a scalar subquery for the denominator). Order by account count descending, so the largest bucket (usually CURRENT) shows up first.

```sql
WITH latest AS (
    SELECT account_id, MAX(cycle_month) AS mx
    FROM statement
    GROUP BY account_id
),
s AS (
    SELECT st.dpd_bucket
    FROM statement st
    JOIN latest l ON st.account_id = l.account_id AND st.cycle_month = l.mx
)
SELECT dpd_bucket,
       COUNT(*) AS n,
       ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM s), 2) AS pct
FROM s
GROUP BY dpd_bucket
ORDER BY n DESC;
```

**Expected results and business conclusion.** Roughly 4 rows. About 92.5% of accounts are currently CURRENT (in good standing), about 7% fall into DPD120PLUS (mostly the last statement before charge-off), and DPD30 and DPD60 each account for a fraction of a percent. Conclusion: the portfolio's overall delinquency rate is healthy, but the DPD120+ share is the leading indicator of future charge-offs. Collections resources should be prioritized on the still-recoverable DPD30 and DPD60 accounts, since they still have a roughly 3-month window before rolling into charge-off (see the early-warning logic in Q13).

---

### Q11. Full P&L across the product ladder

**Business context.** The CFO needs to answer a question at the board meeting that looks simple but isn't: of the 6 cards Keystone offers, which one actually makes money? Intuitively, the premium travel card (Venture Premium) charges a 395 dollar annual fee and sees heavy spend, so it should be the most profitable; the entry-level Secured card has no annual fee and no rewards, so it should be the least profitable. The CFO wants a complete P&L: interest, interchange, and fee revenue for each product on one side, minus rewards and net charge-off losses, minus signup bonuses paid out, on the other. This query maps to business question Q_productpnl (product ladder profitability).

**Tags.** Multiple CTEs + Join | Advanced | CFO.

**Approach.** Revenue and cost live in two different tables: month-by-month economics in `statement`, charge-off losses in `charge_off`. First use a CTE to aggregate interest, interchange, fees, and rewards per account from `statement`; then a second CTE to aggregate net loss per account from `charge_off`. The main query starts from `account`, joins the product table, and LEFT JOINs both CTEs (since most accounts never charge off), backfilling with `COALESCE(..., 0)`. Finally aggregate by product: net P&L = interest + interchange + fees - rewards - net loss - signup bonus. Key trap: you must LEFT JOIN `charge_off`, or you'd be left with only charged-off accounts and the P&L would come out looking like an across-the-board loss.

```sql
WITH econ AS (
    SELECT account_id,
           SUM(interest_charged_usd) AS interest,
           SUM(interchange_revenue_usd) AS interchange,
           SUM(fees_charged_usd) AS fees,
           SUM(rewards_earned_usd) AS rewards
    FROM statement
    GROUP BY account_id
),
loss AS (
    SELECT account_id,
           SUM(charged_off_balance_usd - recovery_amount_usd) AS net_loss
    FROM charge_off
    GROUP BY account_id
)
SELECT p.product_name,
       COUNT(*) AS accts,
       ROUND(SUM(COALESCE(e.interest, 0)), 0) AS interest,
       ROUND(SUM(COALESCE(e.interchange, 0)), 0) AS interchange,
       ROUND(SUM(COALESCE(e.fees, 0)), 0) AS fees,
       ROUND(SUM(COALESCE(e.rewards, 0)), 0) AS rewards,
       ROUND(SUM(COALESCE(l.net_loss, 0)), 0) AS net_loss,
       ROUND(SUM(COALESCE(e.interest, 0) + COALESCE(e.interchange, 0) + COALESCE(e.fees, 0)
                 - COALESCE(e.rewards, 0) - COALESCE(l.net_loss, 0) - a.signup_bonus_usd), 0) AS net_pnl
FROM account a
JOIN card_product p ON a.card_product_id = p.id
LEFT JOIN econ e ON e.account_id = a.id
LEFT JOIN loss l ON l.account_id = a.id
GROUP BY p.product_name
ORDER BY net_pnl DESC;
```

**Expected results and business conclusion.** 6 rows, and the conclusion is surprising. The most profitable product is the unglamorous Keystone Secured (net income of roughly +1.08 million dollars, driven by revolver interest at a 26.99% APR), followed by Venture Premium and Student (each roughly +220,000 to +250,000). Meanwhile the two flagship high-cashback products, Cashback Plus (roughly -320,000) and Travel (roughly -80,000), are net losers overall; the base Cashback product, with its lower cashback rate, is actually mildly profitable (roughly +50,000). Conclusion: rewards cost and acquisition cost on high-rewards cards are eating into profit, while the unglamorous Secured / near-prime revolver segment is the real profit engine. Recommend re-examining the rewards structure and annual fee pricing for Cashback Plus and Travel — see Q12 and Q19 for the specific mechanism.

---

### Q12. Transactor vs Revolver per-account contribution

**Business context.** The Product Manager is confused by Q11's results — why would the premium card lose money? The CFO asks her to dig one level deeper and split each card's customers into two behavioral groups: Transactor (pays the balance in full every month, never pays interest) and Revolver (carries a balance, pays interest). She suspects the losses are concentrated among transactors — people who only chase the rewards and never pay interest. She wants to compare the full per-account contribution of both groups on each rewards card. This query maps to business questions Q_productpnl and Q_transactor (transactor profitability).

**Tags.** CTE + Join | Intermediate | Product Manager.

**Approach.** "Full contribution" uses the same definition as Q11, but rolled down to the per-account average and sliced one level further by `behavior_segment`. Use a CTE to compute each account's operating margin from `statement` (interest + interchange + fees - rewards), then a second CTE for each account's net charge-off loss. The main query joins the product table, groups by (product, behavior), and averages (margin - signup bonus - net loss). Only rewards cards are considered (`rewards_rate_pct >= 0.015`), since the trap only shows up at a meaningful rewards rate. Transactors don't accrue interest in a normal repayment month (`interest_charged_usd` is 0), which is the root cause of their low contribution.

```sql
WITH econ AS (
    SELECT account_id,
           SUM(interest_charged_usd + interchange_revenue_usd + fees_charged_usd - rewards_earned_usd) AS margin
    FROM statement
    GROUP BY account_id
),
loss AS (
    SELECT account_id,
           SUM(charged_off_balance_usd - recovery_amount_usd) AS net_loss
    FROM charge_off
    GROUP BY account_id
)
SELECT p.product_name,
       p.rewards_rate_pct,
       a.behavior_segment,
       COUNT(*) AS n,
       ROUND(AVG(COALESCE(e.margin, 0) - a.signup_bonus_usd - COALESCE(l.net_loss, 0)), 2) AS avg_contribution
FROM account a
JOIN card_product p ON a.card_product_id = p.id
LEFT JOIN econ e ON e.account_id = a.id
LEFT JOIN loss l ON l.account_id = a.id
WHERE p.rewards_rate_pct >= 0.015
GROUP BY p.product_name, a.behavior_segment
ORDER BY p.id, a.behavior_segment;
```

**Expected results and business conclusion.** On every rewards card, transactors' average per-account contribution comes out negative (Cashback about -223, Cashback Plus about -426, Travel about -168, and even Venture Premium about -28), while revolvers on the same products are all positive (ranging from +20 to +1,010). Conclusion: transactors are the true culprit behind the premium card losses. They generate interchange (roughly 1.8% of spend) but that gets eaten up by even higher rewards (2% to 2.5%), and they never pay interest. Recommend either lowering the rewards rate, raising the annual fee, or steering marketing away from targeting obviously transactor-shaped customer segments with high rewards offers (this could plug directly into a Data Science customer segmentation model).

---

### Q13. Promo APR cliff

**Business context.** A batch of accounts was acquired through a "0% APR balance transfer for 12 months" promotion. While building churn and risk forecasting models, the Data Scientist notices something strange: these accounts behave well for the first 11 months, then a cluster of them starts having problems right around months 12 to 14. She suspects a "promo cliff": once the 0% period ends, the rate jumps to over 20%, the monthly payment spikes, and a chunk of customers can't keep up and become delinquent. She wants to compare the DPD30+ rate for promo and non-promo accounts by account age (cycle_month) and plot the cliff. This query maps to business question Q_promo (Promo APR cliff).

**Tags.** Conditional aggregation + Time series | Advanced | Data Scientist.

**Approach.** The clever part of this query is comparing **two populations side by side, by account age, in a single scan**. Join `statement` to `account` without filtering by population; instead, use two sets of conditions inside the aggregation: one that only counts DPD30+ for promo accounts (`is_promo_apr=1`), and another for non-promo accounts. `SUM(CASE WHEN is_promo_apr=1 AND days_past_due>=30 ...)` divided by `SUM(is_promo_apr=1)` gives the promo group's rate, and the same logic applies to the non-promo group. Group by `cycle_month` to see how the two curves move with account age. The promo group should spike around months 12 to 14. `NULLIF` protects against division by zero if either group has no accounts at a given age.

```sql
SELECT s.cycle_month,
       ROUND(100.0 * SUM(CASE WHEN a.is_promo_apr = 1 AND s.days_past_due >= 30 THEN 1 ELSE 0 END)
             / NULLIF(SUM(CASE WHEN a.is_promo_apr = 1 THEN 1 ELSE 0 END), 0), 2) AS promo_dpd30,
       ROUND(100.0 * SUM(CASE WHEN a.is_promo_apr = 0 AND s.days_past_due >= 30 THEN 1 ELSE 0 END)
             / NULLIF(SUM(CASE WHEN a.is_promo_apr = 0 THEN 1 ELSE 0 END), 0), 2) AS nonpromo_dpd30
FROM statement s
JOIN account a ON s.account_id = a.id
WHERE s.cycle_month BETWEEN 6 AND 16
GROUP BY s.cycle_month
ORDER BY s.cycle_month;
```

**Expected results and business conclusion.** Roughly 11 rows. The promo group's DPD30+ rate stays around 2% to 5% for cycle months 6 through 11, then spikes to about 12% at months 12 to 14, before falling back again; the non-promo group's DPD30+ rate declines steadily to under 1% with no spike at all. The contrast between the two curves makes the cliff impossible to miss. Conclusion: the 0% promo expiring is a predictable risk event. Recommend proactively reaching out to this population 1 to 2 months before promo expiration (reminders, installment plans, or refinancing offers) to smooth over the cliff; the data science team could also turn "months until promo expiration" into a strong feature in the risk model.

---

### Q14. Interchange breakdown by MCC

**Business context.** An analyst in the CFO's office needs to break down where interchange revenue comes from. Interchange is the fee merchants pay the issuing bank on every swipe, and it's one of Keystone's three main revenue streams. Different Merchant Category Codes (MCC) carry different rates (airlines and hotels are high, grocery and gas are low). The analyst needs to know which categories drive the most revenue, to inform negotiations with the payment networks and category-level marketing. This query maps to business question Q_interchange.

**Tags.** Join + Aggregation | Basic | CFO office.

**Approach.** Start directly from the sampled transaction table `"transaction"` (note it's a SQL reserved word, so it must be quoted), join `mcc_category` to bring in the category name, and aggregate by category. Sum transaction count, spend, and interchange revenue, and compute an effective rate (interchange / spend) as a sanity check. Order by interchange revenue descending to see which categories contribute the most. Interchange here uses the already-computed `interchange_revenue_usd` field on the transaction table.

```sql
SELECT m.category_name,
       COUNT(*) AS txns,
       ROUND(SUM(t.amount_usd), 0) AS spend,
       ROUND(SUM(t.interchange_revenue_usd), 0) AS interchange,
       ROUND(100.0 * SUM(t.interchange_revenue_usd) / SUM(t.amount_usd), 3) AS eff_rate
FROM "transaction" t
JOIN mcc_category m ON t.mcc_category_id = m.id
GROUP BY m.category_name
ORDER BY interchange DESC;
```

**Expected results and business conclusion.** 12 rows. Restaurants, Online Retail, and Grocery contribute the most interchange (each roughly 43,000 to 52,000 dollars, driven by transaction volume), with effective rates ranging from 1.3% (Utilities) to 2.1% (Airlines, Hotels), consistent with each MCC's posted rate. Conclusion: revenue is concentrated in high-frequency, everyday-spend categories. Recommend designing rewards promotions that steer spend toward higher-rate categories (dining, travel), lifting interchange revenue without giving up too much in rewards. This is where product and finance intersect.

---

### Q15. Bonus churner negative LTV

**Business context.** The VP of Acquisitions is reviewing the large signup bonus campaigns. Marketing loves using big bonuses to drive account volume, but she suspects there's a population of "bonus churners": customers who hit the minimum spend requirement to earn the bonus, then let the card sit unused, and close it a few months later, never generating meaningful revenue for the company. She needs to group accounts by closure reason (close_reason) and compute average lifetime value (LTV), checking whether the bonus_churn group comes out negative. This query maps to business question Q_bonus (bonus churner negative LTV).

**Tags.** CTE + Join | Intermediate | VP of Acquisitions.

**Approach.** A simplified LTV definition = the account's lifetime operating margin minus the signup bonus paid out. Use a CTE to compute each account's margin (interest + interchange + fees - rewards) from `statement`. The main query starts from `attrition_event` (only closed accounts appear here), joins `account`, LEFT JOINs the margin CTE, and groups by `close_reason` to compute average LTV. LEFT JOIN is used because a small number of closed accounts may have no statements at all. The bonus_churn group's LTV should be significantly negative, and the lowest among all closure reasons.

```sql
WITH econ AS (
    SELECT account_id,
           SUM(interest_charged_usd + interchange_revenue_usd + fees_charged_usd - rewards_earned_usd) AS margin
    FROM statement
    GROUP BY account_id
)
SELECT ae.close_reason,
       COUNT(*) AS n,
       ROUND(AVG(COALESCE(e.margin, 0) - a.signup_bonus_usd), 2) AS avg_ltv
FROM attrition_event ae
JOIN account a ON ae.account_id = a.id
LEFT JOIN econ e ON e.account_id = a.id
GROUP BY ae.close_reason
ORDER BY avg_ltv;
```

**Expected results and business conclusion.** 6 rows. `bonus_churn` shows an average LTV of about -280 dollars, the only closure reason that comes out negative; all the others (rate_shopping, inactivity, dissatisfaction, product_upgrade, charge_off) show LTV above +325. One nuance worth flagging: the LTV metric used here only subtracts the signup bonus — it does **not** subtract charge-off losses (it measures "operating margin net of bonus," not full contribution), which is why the `charge_off` group actually shows the highest LTV of all (about +560). That's an artifact of the metric's definition, not evidence that charged-off accounts are the most profitable — for full contribution including charge-off losses, see the account_contribution figures in Q11 or Q12. The teaching point here is that bonus_churn is the only genuinely negative group. Conclusion: bonus hunters really are systematically unprofitable. Recommend adding "anti-gaming" design to large bonus campaigns: raising the minimum spend threshold, extending the bonus vesting period, or clawing back the bonus on early closure. Data science could also build a model to flag high-churn-risk profiles right at the application stage.

---

### Q16. Vintage loss curve

**Business context.** The Chief Risk Officer needs to prepare a portfolio quality report for investors. The classic fear in credit card risk is loosening underwriting standards without realizing it. The standard way to check this is the vintage (cohort by open quarter) loss curve: treat each quarter's newly opened accounts as a cohort, and compare their charge-off rate at the same account age (say, months_on_book <= 6). If more recent cohorts show a higher charge-off rate at the same age, underwriting quality is deteriorating. This query maps to business question Q_vintage (vintage deterioration).

**Tags.** Date + Conditional aggregation | Intermediate | Chief Risk Officer.

**Approach.** The dataset has already precomputed the account open quarter in `account.open_vintage` (formatted like '2025Q2'), saving the trouble of deriving the quarter from a raw date. Group by `open_vintage`, and for each group compute the share of accounts that charged off within 6 months on book, i.e. `account_status='CHARGED_OFF' AND months_on_book <= 6`. Exclude the most recent two quarters (2026), since most of their accounts haven't reached 6 months of age yet, making the denominator not comparable (use `WHERE open_vintage < '2026Q1'`). Compare the mob6 charge-off rate across quarters to check the trend.

```sql
SELECT open_vintage,
       COUNT(*) AS n,
       ROUND(100.0 * SUM(CASE WHEN account_status = 'CHARGED_OFF' AND months_on_book <= 6 THEN 1 ELSE 0 END) / COUNT(*), 2) AS co_rate_by_mob6
FROM account
WHERE open_vintage < '2026Q1'
GROUP BY open_vintage
ORDER BY open_vintage;
```

**Expected results and business conclusion.** 6 rows. The earliest vintage (2024Q3) shows a mob6 charge-off rate of about 0.7%, climbing to about 4.4% for the most recent vintage (2025Q4) — (2024Q3 through 2025Q2 combined run about 1.2%, and the second half of 2025 runs about 3.4%). Despite some quarter-to-quarter noise, the upward trend is clear. Conclusion: underwriting quality is systematically deteriorating, and more recent cohorts are going bad faster. This is a signal that needs to be escalated to the board and investors right away. The next step is to use Q17 to pin down the cause — namely, whether approval standards have loosened.

---

### Q17. Underwriting standards drifting over time

**Business context.** Following on from Q16. The CRO has already seen that more recent vintages are going bad faster, and now needs to find the cause. The most likely explanation is that underwriting standards have quietly loosened: the approval rate creeping up while the average FICO of approved accounts creeps down. She needs to look at the approval rate and booked FICO trend by application quarter, to nail down the "loosening" hypothesis. This query maps to business question Q_vintage.

**Tags.** Date functions | Intermediate | Chief Risk Officer.

**Approach.** There's no ready-made quarter column this time (the `application` table has no `open_vintage`), so the year and quarter need to be derived from `application_date` using `strftime`. Extract the year with `strftime('%Y', application_date)`, and derive the quarter from the month: `(month - 1) / 3 + 1`. Note that `strftime` returns a string, so it needs to be `CAST` to an integer before doing arithmetic on it. Group by (year, quarter) and compute the approval rate and average booked FICO (using the same conditional aggregation trick as Q5). Order chronologically to see the trend.

```sql
SELECT CAST(strftime('%Y', application_date) AS INT) AS yr,
       (CAST(strftime('%m', application_date) AS INT) - 1) / 3 + 1 AS quarter,
       COUNT(*) AS apps,
       ROUND(100.0 * SUM(CASE WHEN decision = 'APPROVED' THEN 1 ELSE 0 END) / COUNT(*), 1) AS approval_rate,
       ROUND(AVG(CASE WHEN decision = 'APPROVED' THEN fico_at_application END), 0) AS avg_booked_fico
FROM application
GROUP BY yr, quarter
ORDER BY yr, quarter;
```

**Expected results and business conclusion.** 8 rows. The approval rate slowly climbs from about 55% in 2024Q3 to about 60% by 2026Q2, while booked FICO slides from about 722 down to about 694 over the same period. Conclusion: underwriting standards really have loosened, which explains the vintage deterioration seen in Q16. Recommend pulling the FICO approval floor back up, or at minimum tightening pricing and credit line controls for the marginal customers approved under the looser recent standards. The CRO now has the full causal chain (loosened underwriting → vintage deterioration) needed to convince the business to hit the brakes.

---

### Q18. Champion vs Challenger performance

**Business context.** The CMO needs to evaluate the marketing team's champion/challenger testing setup. Champion is the steady-state offer being pushed by default; challenger is an experimental new offer (often with a bigger bonus or a more aggressive promotion). She wants to know: are these flashier challenger offers bringing in customers of comparable quality to champion? Is volume being chased at the expense of asset quality? This query maps to business question Q_champion.

**Tags.** Join + Aggregation | Basic | CMO.

**Approach.** Start from `campaign`, split into two groups by `is_champion`, and LEFT JOIN `account` to pull the accounts each group brought in. LEFT JOIN ensures that even a campaign type with zero booked accounts isn't dropped. For each group, compute campaign count, booked account count, average signup bonus, and charge-off rate. Comparing the charge-off rate and bonus size between the two groups reveals whether challenger is "trading higher bonus for lower quality."

```sql
SELECT c.is_champion,
       COUNT(DISTINCT c.id) AS campaigns,
       COUNT(a.id) AS booked,
       ROUND(AVG(a.signup_bonus_usd), 0) AS avg_bonus,
       ROUND(100.0 * SUM(CASE WHEN a.account_status = 'CHARGED_OFF' THEN 1 ELSE 0 END) / COUNT(a.id), 2) AS chargeoff_rate
FROM campaign c
LEFT JOIN account a ON a.campaign_id = c.id
GROUP BY c.is_champion;
```

**Expected results and business conclusion.** 2 rows. Challenger (is_champion=0) offers a higher average bonus (about 106 vs about 66 for champion), yet its charge-off rate is actually lower (about 5.6% vs about 9.4% for champion). This result needs to be interpreted carefully: the difference mostly stems from the different products and channels tied to champion vs challenger campaigns, not from "challenger being inherently better." Conclusion: any champion/challenger comparison has to control for product and channel before drawing conclusions, or it risks being misleading. This is a teaching query meant to flag the risk of Simpson's paradox; the recommended next step is to redo the comparison broken out by product.

---

### Q19. Rewards eroding interchange

**Business context.** Having seen the premium card losses in Q11, the CFO wants sharper evidence of whether rewards are eating into interchange revenue. The logic is simple: the issuer earns roughly 1.8% interchange on spend, but if a card pays back 2% to 2.5% in rewards, every dollar swiped is actually a net loss. She wants to compare interchange revenue and rewards cost by product, and compute the net difference. This query maps to business questions Q_transactor and Q_productpnl.

**Tags.** CTE + Join | Intermediate | CFO.

**Approach.** Join `statement` to `account` to bring in the product dimension, then aggregate interchange revenue and rewards cost by product. A single CTE is enough. The main query computes the net difference (`interchange - rewards`), ordered by product id (so rewards rate roughly increases down the list). Products with a negative net difference are hard proof of "rewards eroding interchange." This is a cleaner, more focused slice of Q11/Q12.

```sql
WITH s AS (
    SELECT a.card_product_id,
           SUM(st.interchange_revenue_usd) AS interchange,
           SUM(st.rewards_earned_usd) AS rewards
    FROM statement st
    JOIN account a ON st.account_id = a.id
    GROUP BY a.card_product_id
)
SELECT p.product_name,
       p.rewards_rate_pct,
       ROUND(s.interchange, 0) AS interchange,
       ROUND(s.rewards, 0) AS rewards,
       ROUND(s.interchange - s.rewards, 0) AS net_interchange_after_rewards
FROM card_product p
JOIN s ON s.card_product_id = p.id
ORDER BY p.id;
```

**Expected results and business conclusion.** 6 rows, showing a clean gradient. Cards with a rewards rate of 0 to 1.5% (Secured, Student, Cashback) come out with a positive net difference (interchange covers rewards); cards with a rewards rate of 2% or more (Cashback Plus at about -58,000, Travel at about -71,000, Venture Premium at about -296,000) come out negative — rewards eating straight through interchange. Conclusion: once the rewards rate approaches or exceeds the interchange rate (about 1.8%), swipe volume alone becomes a losing proposition, and the card needs interest income (revolvers) or annual fees to make up the gap. Recommend lowering the rewards rate on premium cards below the interchange rate, or backstopping with the annual fee. This finding reinforces the transactor loss pattern found in Q12.

---

### Q20. Monthly new account trend

**Business context.** A newly hired Data Analyst is handed her first assignment: build a monthly new-account trend chart for the weekly leadership meeting. This is the most basic form of operational monitoring, and the standard first exercise for getting familiar with the data — checking for seasonality and any unusual months in account openings. This query maps to business question Q_ops.

**Tags.** Date + Aggregation | Basic | Data Analyst.

**Approach.** The simplest possible time-series aggregation. Use `strftime('%Y-%m', open_date)` to truncate the open date down to the month, then count by month. Order chronologically. The teaching point here is getting familiar with SQLite's `strftime` date function and the general pattern of "group by time granularity," which many later trend analyses are variations of.

```sql
SELECT strftime('%Y-%m', open_date) AS month,
       COUNT(*) AS new_accounts
FROM account
GROUP BY month
ORDER BY month;
```

**Expected results and business conclusion.** Roughly 24 rows (one per month). Aside from the earliest month, 2024-07, which is a bit low (the start of the data window, only a half month, about 165 accounts), monthly new account volume fluctuates roughly between 320 and 450, trending gradually upward as the portfolio accumulates (recent 2026 months mostly above 400, with the final month around 440). Conclusion: new account volume is generally stable, with no anomalous cliffs and no single-day spikes. This table is the foundation for all operational dashboards, and an analyst can layer channel and product dimensions on top of it for finer-grained breakdowns.

---

## 5. Query-to-business-question mapping

| Business question | Corresponding queries |
|----------|----------|
| Underwriting model calibration (Trap 1) | Q3, Q4 |
| Channel adverse selection (Trap 2) | Q6, Q7 |
| Transactor profitability (Trap 3) | Q12, Q19 |
| Promo APR cliff (Trap 4) | Q13 |
| CLI adverse selection (Trap 5) | Q9 |
| Bonus churner negative LTV (Trap 6) | Q15 |
| Vintage deterioration (Trap 7) | Q16, Q17 |
| Product ladder P&L (Trap 8) | Q11, Q12, Q19 |
| Acquisition and response model | Q1, Q2, Q18 |
| Underwriting and portfolio operations | Q5, Q8, Q10 |
| Revenue and operational monitoring | Q14, Q20 |
