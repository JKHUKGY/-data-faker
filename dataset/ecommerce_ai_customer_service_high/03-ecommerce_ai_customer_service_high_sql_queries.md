# NestMart AI Customer Service System — SQL Query Reference

This document contains **20 business-oriented SQL query examples** covering the core analytical scenarios of NestMart's AI customer service ticket processing system. This is the most "teaching-oriented" piece of the entire dataset: it both proves that the earlier table structure and data really can answer business questions, and walks you, step by step like a real analyst, through turning each question into SQL.

> **Read these two first:** Company, industry, business questions, glossary, and metric formulas are in [`01-ecommerce_ai_customer_service_high_business_context.md`](01-ecommerce_ai_customer_service_high_business_context.md); table structure, fields, foreign keys, and distributions are in [`02-ecommerce_ai_customer_service_high_er_document.md`](02-ecommerce_ai_customer_service_high_er_document.md).

## How to Use This Document

This document is written for **an intern who has just read the business context and ER document and is about to be assigned a task by their manager**. How to read:

1. **Each query has five parts, read them in order.**
   - **Business background** — who is asking, why they're asking, what decision the answer supports, and why they're asking now.
   - **Category / Difficulty / Role** — three tags that help you judge how much effort to invest and which role this aligns with.
   - **Solution approach** — before looking at the SQL, think through which tables to touch, how to wire the JOINs (where to LEFT, where it might fan out), what the aggregation grain is, why a CTE / window function / subquery is used, and any SQLite gotchas. **This part is the key to turning "can read SQL" into "can write SQL."**
   - **SQL query** — code that actually runs on the generated SQLite database.
   - **Expected result explanation** — what the result looks like, which business trap the key numbers map to, and **what to do once you have the numbers**. Producing the result is the start of analysis, not the end.
2. **Every query traces back to a business question.** Business context §5 lists business questions Q1–Q6; each query's expected result here points back to one of them.
3. **SQL is for reading and learning, not just running.** The solution approach explains "why it's written this way," so you can copy the pattern to new questions.
4. **All "today" references use the fixed reference date `'2024-12-01'`** (see note below); do not replace it with `DATE('now')`.

### Query Index

| # | Title | Business Role | SQL Category | Difficulty | Business Question |
|---|-------|---------------|--------------|------------|-------------------|
| Q1 | VIP user ticket processing priority | Operations Manager | Join + Aggregation | Basic | Q4 |
| Q2 | Prompt version iteration comparison | ML Engineer | Join + Calculated Fields | Intermediate | Q3 |
| Q3 | Most-confused intent pair identification | ML Engineer | Aggregation + Subquery | Intermediate | Q1 |
| Q4 | Rule violation case root-cause analysis | Quality Manager | Join + Aggregation | Intermediate | Q2 |
| Q5 | Annotator performance and agreement ranking | Annotation Manager | Aggregation + Ranking | Basic | Q6 |
| Q6 | High-frequency refund user risk alert | Risk Analyst | Join + Filtering | Intermediate | Q5 |
| Q7 | AI processing performance and cost analysis | Technical Operations | Aggregation + Calculated | Intermediate | Q5 |
| Q8 | Ticket sentiment distribution vs urgency | Customer Experience Manager | Cross Tab + Aggregation | Basic | Q1 |
| Q9 | Daily ticket volume trend and capacity planning | Operations Analyst | Date/Time + Aggregation | Intermediate | Q4 |
| Q10 | LLM Judge score vs annotation agreement | ML Researcher | Aggregation + Statistical | Advanced | Q1 |
| Q11 | Product category vs ticket type correlation | Product Operations | Join + Cross Tab | Intermediate | Q4 |
| Q12 | Evaluation run history trend | Tech Lead | Time Series + Trend | Intermediate | Q3 |
| Q13 | Profile of tickets that frequently violate rules | Quality Analyst | Join + Feature Analysis | Advanced | Q2 |
| Q14 | Ticket handling SLA monitoring | Operations Manager | Date/Time + SLA | Intermediate | Q4 |
| Q15 | AI decision confidence vs accuracy correlation | ML Engineer | Statistical + Bucketing | Advanced | Q2 |
| Q16 | User lifetime value and complaint relationship | Customer Success Manager | Join + Segmentation | Advanced | Q4 |
| Q17 | Annotation dispute cases and arbitration efficiency | Annotation Manager | Join + Status Tracking | Intermediate | Q6 |
| Q18 | Multi-channel ticket quality comparison | Product Manager | Aggregation + Cross-channel | Intermediate | Q1 |
| Q19 | Prompt change impact scope prediction | ML Engineer | Aggregation + Classification | Advanced | Q1 |
| Q20 | Executive dashboard key metric summary | Executive (VP/CTO) | Multi-table Aggregation | Advanced | Q3 |

## Dataset Scale (for cross-referencing query expectations)

| Category | Rows | Notes |
|----------|------|-------|
| **raw_ticket** | ~5,000 rows | 30 days of tickets in Nov 2024, about 167/day |
| **step1/step3 outputs** | ~5,000 each | AI produces 1 Step1 + 1 Step3 output per ticket |
| **annotation_ground_truth** | ~1,000 rows | 500 evaluation-sample tickets × 2 annotators |
| **evaluation_run** | 6 runs | v1 (baseline) → v2 → v3 → v4 → v5 (production) → v5 (regression) |
| **step1/step3_eval_detail** | ~3,000 each | 500 evaluation samples × 6 runs |
| **confusion_matrix** | ~250 rows | Aggregated from step1_eval_detail; per-run sum = that run's evaluation sample count |

## Key Evaluation Run IDs at a Glance

| run_id | Step1 Prompt | Step3 Prompt | Notes |
|--------|--------------|--------------|-------|
| `eval_20241110_140000` | v1 | v1 | baseline (accuracy 81.0%, violation rate 12.0%) |
| `eval_20241112_093000` | v2 | v1 | Fixed dispute_non_receipt misclassification (accuracy 87.0%) |
| `eval_20241115_143000` | v3 | v2 | Improved sentiment + emphasized R002 |
| `eval_20241119_100000` | v4 | v2 | Added few-shot examples |
| `eval_20241123_140000` | v5 | v3 | production candidate (accuracy 90.5%, violation rate 3.0%) |
| `eval_20241128_090000` | v5 | v3 | post-production regression check |

> **Glossary quick reference (Cohen's Kappa, LLM Judge, Confusion Matrix, A/B Test, rules R001–R007, etc.):** see [`01-ecommerce_ai_customer_service_high_business_context.md`](01-ecommerce_ai_customer_service_high_business_context.md), §8 Glossary.

> **About "current date":** This dataset is a **static snapshot of Nov 2024** (ticket `submitted_at` between 2024-11-01 and 11-30). Any query involving "last N days / wait time / backlog days" uniformly uses **the fixed reference date `2024-12-01`** as "today," not `DATE('now')` / `JULIANDAY('now')` (the real runtime date falls outside the data range, which would make results empty or distorted). If you want to run it real-time, just replace `'2024-12-01'` with `'now'`.

---

## Query 1: VIP user ticket processing priority analysis

**Business background:**
The support manager needs to know every day how tickets from VIP users (Gold and Platinum) are being handled, to make sure high-value users get priority service. The manager wants to know: how many VIP tickets are waiting? How long, on average, since they were submitted? Which VIP users have open tickets? This query helps the manager quickly identify the high-value customer requests that need priority handling during the morning stand-up, to prevent churn.

**Query category:** Join + Aggregation
**Difficulty:** Basic
**Business role:** Operations Manager

**Solution approach:**
This question needs to join the tickets in `raw_ticket` with `user` to filter by tier. Use an INNER JOIN, since every ticket has a corresponding user. First, narrow down with `tier_code IN ('vip_gold','vip_platinum')` in the WHERE, then restrict to the last 7 days with `submitted_at >= DATE('2024-12-01','-7 days')` — note the reference date is a fixed literal, not `DATE('now')`, otherwise the real runtime date will fall outside the data range and you'll get nothing back. The aggregation grain is "one row per tier," so `GROUP BY tier_code`; `COUNT(DISTINCT ticket_id)` counts tickets, `COUNT(DISTINCT user_id)` counts users involved (DISTINCT prevents JOIN fan-out from double-counting). Average wait days uses `JULIANDAY(reference date) - JULIANDAY(submitted_at)`, and `GROUP_CONCAT(DISTINCT user_name)` concatenates names into a column for the manager to call out by name.

**SQL query:**
```sql
SELECT
    u.tier_code AS 会员等级,
    COUNT(DISTINCT rt.ticket_id) AS 工单数量,
    COUNT(DISTINCT u.user_id) AS 涉及用户数,
    ROUND(AVG(JULIANDAY('2024-12-01') - JULIANDAY(rt.submitted_at)), 1) AS 平均等待天数,
    GROUP_CONCAT(DISTINCT u.user_name) AS 用户列表
FROM raw_ticket rt
JOIN user u ON rt.user_id = u.user_id
WHERE u.tier_code IN ('vip_gold', 'vip_platinum')
    AND rt.submitted_at >= DATE('2024-12-01', '-7 days')
GROUP BY u.tier_code
ORDER BY 工单数量 DESC;
```

**Expected result explanation:**
Returns VIP ticket statistics for the last 7 days. Based on this dataset's scale (~5,000 tickets × 30 days, VIP ~20%), VIP tickets in the last 7 days run roughly 230. Results may show Gold users with ~190 tickets (covering ~80 users, average wait 2.3 days) and Platinum users with ~40 tickets (covering ~20 users, average wait 1.8 days). The manager can use this to judge whether additional staff is needed to clear the VIP queue.

---

## Query 2: Prompt version iteration impact comparison

**Business background:**
After tuning the Step1 intent recognition Prompt, the ML engineer needs to show the team how much the new version improves over the baseline. The engineer needs to answer: how much did accuracy improve? Which metrics improved meaningfully? Is it worth shipping to production? This query produces a version-comparison report containing the percentage change for every key metric, so the technical decision-maker can quickly decide whether to ship the new Prompt.

**Query category:** Join + Calculated Fields
**Difficulty:** Intermediate
**Business role:** ML Engineer

**Solution approach:**
The A/B comparison fact table is `prompt_comparison` (one baseline/experiment run pair + one metric = one row). The trick is that to show the version codes, you need to JOIN each end of the run back to `evaluation_run`, then each of those to `prompt_version` — i.e., the same `prompt_version` is aliased and joined twice (once for baseline, once for experiment), the classic "aliased multi-JOIN." `WHERE pv_baseline.step_name='step1_intent'` limits the comparison to Step1 metrics. The improvement is taken directly from the `improvement_pct` field (the generator backfills it from the real metrics, so you don't need to recompute), and a CASE adds a "+" prefix for positive values; significance is read from `is_significant`. No GROUP BY needed, since each row is already one comparison record.

**SQL query:**
```sql
SELECT
    pc.metric_name AS 指标名称,
    ROUND(pc.baseline_value * 100, 2) || '%' AS 基线值,
    ROUND(pc.experiment_value * 100, 2) || '%' AS 实验值,
    CASE
        WHEN pc.improvement_pct > 0 THEN '+' || ROUND(pc.improvement_pct, 1) || '%'
        ELSE ROUND(pc.improvement_pct, 1) || '%'
    END AS 改进幅度,
    CASE WHEN pc.is_significant THEN '✓ 显著' ELSE '- 不显著' END AS 统计显著性,
    pv_baseline.version_code AS 基线版本,
    pv_exp.version_code AS 实验版本
FROM prompt_comparison pc
JOIN evaluation_run er_baseline ON pc.baseline_run_id = er_baseline.run_id
JOIN evaluation_run er_exp ON pc.experiment_run_id = er_exp.run_id
JOIN prompt_version pv_baseline ON er_baseline.step1_prompt_id = pv_baseline.prompt_id
JOIN prompt_version pv_exp ON er_exp.step1_prompt_id = pv_exp.prompt_id
WHERE pv_baseline.step_name = 'step1_intent'
ORDER BY pc.comparison_id;
```

**Expected result explanation:**
Returns comparison results like "step1_accuracy: 81% → 87%, +7.4%, ✓ significant". The engineer can see across-the-board improvements from v2 over v1 on overall accuracy, specific-intent accuracy (dispute_non_receipt), etc., supporting the deployment decision.

---

## Query 3: Identifying the most-confused intent pairs

**Business background:**
When the Prompt engineer improves the intent recognition system, they need to find the intent combinations the AI most often confuses. For example, "did-not-receive" is often misclassified as "refund request" because users describing a non-delivery typically mention "refund." The engineer asks: which intent pairs are most confused? How many misclassified samples? This information helps the engineer add targeted disambiguation instructions to the Prompt (such as "read the entire message before classifying"), raising accuracy.

**Query category:** Aggregation + Subquery
**Difficulty:** Intermediate
**Business role:** ML Engineer

**Solution approach:**
Each row of `confusion_matrix` is "in some run, the count of tickets where true = X and predicted = Y." To compute "misclassification rate," the denominator should be the total samples of that true intent in that run, so first use a subquery to sum `count` by `(run_id, true_label)` as the denominator, then JOIN it back to the detail. **The most critical pitfall: this denominator subquery must `WHERE run_id = the same run`, otherwise summing across all 6 runs inflates the denominator by about 6×, severely understating misclassification rates.** The main query uses `WHERE true_label != predicted_label` to look only at off-diagonal (misclassifications), pins to the v1 run, and `ORDER BY count DESC LIMIT 5` picks the 5 worst combinations. The two `intent_category` JOINs are just to translate intent codes into Chinese names.

**SQL query:**
```sql
SELECT
    cm.true_label AS 真实意图,
    cm.predicted_label AS 误判为,
    cm.count AS 样本数,
    ROUND(cm.count * 100.0 / total.true_total, 1) AS 误判率百分比,
    ic_true.intent_name_cn AS 真实意图名称,
    ic_pred.intent_name_cn AS 误判意图名称
FROM confusion_matrix cm
JOIN intent_category ic_true ON cm.true_label = ic_true.intent_code
JOIN intent_category ic_pred ON cm.predicted_label = ic_pred.intent_code
JOIN (
    SELECT run_id, true_label, SUM(count) AS true_total
    FROM confusion_matrix
    WHERE run_id = 'eval_20241110_140000'  -- denominator must be pinned to the same run, otherwise it bleeds across 6 runs
    GROUP BY run_id, true_label
) total ON cm.true_label = total.true_label AND cm.run_id = total.run_id
WHERE cm.true_label != cm.predicted_label  -- look only at misclassifications
    AND cm.run_id = 'eval_20241110_140000'  -- the v1 Prompt run
ORDER BY cm.count DESC
LIMIT 5;
```

**Expected result explanation:**
Returns the top 5 most common misclassification combinations, e.g., "dispute_non_receipt → refund_request: 15 samples, 23% misclassification rate." The engineer adds the "read entire message first" instruction in v2 Prompt, dropping that rate to 8%.

---

## Query 4: Rule violation case root-cause analysis

**Business background:**
At the weekly QA meeting, the support Quality Manager needs to report on the AI system's rule compliance. The manager cares about: which rules are violated most often? How severe? Are there patterns? For example, if the AI is frequently auto-approving refunds on "third-party merchant goods" (violating R002), it means the AI hasn't internalized the core business rule that "the merchant decides." This query produces a top-N rule violation list to pinpoint where Prompt improvements should focus.

**Query category:** Join + Aggregation
**Difficulty:** Intermediate
**Business role:** Quality Manager

**Solution approach:**
JOIN from the rule table `decision_rule` into the violation cases `rule_violation_case` (one rule to many cases, one-to-many). The aggregation grain is "one row per rule," so `GROUP BY rule_id, rule_name`. The core technique is conditional aggregation: `COUNT(case_id)` counts total violations, `SUM(CASE WHEN severity='critical' THEN 1 ELSE 0 END)` counts severe ones, `SUM(CASE WHEN fix_status='fixed' ...)` counts fixed. Average severity maps critical/high/medium to 1.0/0.7/0.3 and takes `AVG`. `WHERE run_id` pins to the v1 run to see the baseline worst-case, and `ORDER BY violation count DESC` floats R002 (third-party refund) to the top — exactly matching trap T3 in ER §7.6.

**SQL query:**
```sql
SELECT
    dr.rule_id AS 规则编号,
    dr.rule_name AS 规则名称,
    COUNT(rvc.case_id) AS 违反次数,
    SUM(CASE WHEN rvc.impact_severity = 'critical' THEN 1 ELSE 0 END) AS 严重违反次数,
    SUM(CASE WHEN rvc.fix_status = 'fixed' THEN 1 ELSE 0 END) AS 已修复次数,
    GROUP_CONCAT(DISTINCT rvc.fix_prompt_version) AS 修复版本,
    ROUND(AVG(CASE WHEN rvc.impact_severity = 'critical' THEN 1.0
                   WHEN rvc.impact_severity = 'high' THEN 0.7
                   WHEN rvc.impact_severity = 'medium' THEN 0.3
                   ELSE 0 END), 2) AS 平均严重度评分
FROM decision_rule dr
JOIN rule_violation_case rvc ON dr.rule_id = rvc.rule_id
WHERE rvc.run_id = 'eval_20241110_140000'
GROUP BY dr.rule_id, dr.rule_name
ORDER BY 违反次数 DESC, 平均严重度评分 DESC
LIMIT 10;
```

**Expected result explanation:**
Returns statistics like "R002 (third-party merchant hand-off): 8 violations, 5 severe, 7 fixed in v2." The manager sees R002 is the most-violated rule, and it's been targeted in the v2 Prompt fix.

---

## Query 5: Annotator performance and agreement ranking

**Business background:**
The annotation manager evaluates the annotation team monthly to allocate performance bonuses and identify training needs. The manager needs to answer: who has the highest output? What is their quality like? Is their agreement rate (Cohen's Kappa) above the bar (>0.75)? Does anyone need additional training? This query produces an annotator performance leaderboard combining workload, quality, and agreement, supporting a fair performance review.

**Query category:** Aggregation + Ranking
**Difficulty:** Basic
**Business role:** Annotation Manager

**Solution approach:**
Single-table query on `annotator`, no JOIN needed. The focus is using CASE to bucket `agreement_rate` (Cohen's Kappa) into "Excellent / Good / Acceptable / Needs Improvement," and noting that arbitrators have NULL Kappa — handle that with `IS NULL → N/A` so they don't fall into a wrong bucket. `COALESCE(agreement_rate, 0)` keeps NULL out of ROUND. Tenure is `JULIANDAY(reference date) - JULIANDAY(joined_date)` cast to INTEGER. `WHERE role IN ('annotator','reviewer')` excludes arbitrators (they don't do first-line annotation and have no Kappa). `ORDER BY total_annotations DESC, agreement_rate DESC` is a two-key sort: first by workload, then by quality.

**SQL query:**
```sql
SELECT
    a.annotator_name AS 标注员,
    a.role AS 角色,
    a.total_annotations AS 总标注数,
    ROUND(a.avg_confidence, 2) AS 平均置信度,
    ROUND(COALESCE(a.agreement_rate, 0), 3) AS 一致率Kappa,
    CASE
        WHEN a.agreement_rate >= 0.90 THEN '优秀'
        WHEN a.agreement_rate >= 0.75 THEN '良好'
        WHEN a.agreement_rate >= 0.60 THEN '合格'
        WHEN a.agreement_rate IS NULL THEN 'N/A'
        ELSE '需改进'
    END AS 质量等级,
    CAST((JULIANDAY('2024-12-01') - JULIANDAY(a.joined_date)) AS INTEGER) AS 在职天数
FROM annotator a
WHERE a.role IN ('annotator', 'reviewer')
ORDER BY a.total_annotations DESC, a.agreement_rate DESC;
```

**Expected result explanation:**
Returns an annotator ranking, e.g., "王静怡: 235 annotations, 2.9 average confidence, 0.94 Kappa, Excellent." The manager sees 王静怡 has the highest quality, 张晓月 has the highest output, and 刘美琪's agreement is lower (0.87) and needs training.

---

## Query 6: User refund frequency risk alert

**Business background:**
The risk analyst monitors high-frequency refund users daily to prevent abuse and fraud. Per business rule R004, users with 3+ refunds in 30 days must be escalated to a human. The analyst needs to identify: which users are approaching or have already crossed the threshold? What is their spend and tier? Is proactive intervention needed? This query produces a high-risk user alert list so the analyst can catch unusual behavior early and protect the platform.

**Query category:** Join + Filtering
**Difficulty:** Intermediate
**Business role:** Risk Analyst

**Solution approach:**
This is essentially a single-table filter + arithmetic on `user`; no real JOIN to orders is needed (the high-frequency refund count is already aggregated into `refund_count_30days`). `WHERE refund_count_30days >= 2` catches both groups: those who've crossed R004 (≥3) and those near the threshold (=2). Refund rate is `refund_count_30days*100.0/NULLIF(total_order_count,0)`, **using NULLIF to convert a 0 denominator to NULL and avoid division-by-zero** (new users may have 0 orders). Risk status uses CASE for three labels. `ORDER BY refund_count_30days DESC, total_spent_amount DESC` puts the "most dangerous + most valuable" users at the top for priority intervention.

**SQL query:**
```sql
SELECT
    u.user_id AS 用户ID,
    u.user_name AS 用户姓名,
    u.tier_code AS 会员等级,
    u.refund_count_30days AS 30天退款次数,
    u.total_order_count AS 累计订单数,
    ROUND(u.total_spent_amount, 2) AS 累计消费金额,
    ROUND(u.refund_count_30days * 100.0 / NULLIF(u.total_order_count, 0), 1) AS 退款率百分比,
    CASE
        WHEN u.refund_count_30days >= 3 THEN '⚠️ 已触发R004规则'
        WHEN u.refund_count_30days = 2 THEN '⚡ 接近阈值'
        ELSE '正常'
    END AS 风险状态
FROM user u
WHERE u.refund_count_30days >= 2
ORDER BY u.refund_count_30days DESC, u.total_spent_amount DESC
LIMIT 20;
```

**Expected result explanation:**
Returns a high-risk user list, e.g., "U00000123 (Li某): vip_silver, 3 refunds (30 days), 15 total orders, $650 spend, 20% refund rate, ⚠️ R004 triggered." The analyst sees that this user, despite being Silver tier, has unusually high refund frequency and needs manual review.

---

## Query 7: AI processing performance and cost analysis

**Business background:**
The technical operations manager needs to report AI system operating cost and performance metrics to the CFO. The CFO cares about: what's the average AI handling time per ticket? What's the token cost? Is there room to optimize? Per the business context, Claude 3.5 Sonnet runs about $0.015 per 1,000 output tokens. The manager needs to compute total Step1 and Step3 token consumption and corresponding cost, and compare against human agents (daily wage $150) to prove AI ROI.

**Query category:** Aggregation + Calculated Fields
**Difficulty:** Intermediate
**Business role:** Technical Operations

**Solution approach:**
To combine Step1 and Step3 costs into one table, use `UNION ALL` to stack three sections (Step1 detail / Step3 detail / total). The Step1 section computes cost from real `output_tokens`: `SUM(output_tokens)/1000*0.015`; the Step3 section doesn't store tokens, so it uses a business estimate of 224 tokens/row. The total section uses scalar subqueries to sum across both tables. **The hard requirement for UNION ALL: each section must have the same column count and order; for columns missing in one section (e.g., Step3 has no input_tokens), pad with `NULL`**, otherwise SQLite will throw an error or cross-wire columns. No JOINs in this query — it's all aggregation + arithmetic, and the goal is to give the CFO a clean "AI vs human cost savings" picture (matches trap T5).

**SQL query:**
```sql
SELECT
    'Step 1: 意图识别' AS 处理步骤,
    COUNT(*) AS 处理工单数,
    ROUND(AVG(s1.latency_ms), 0) AS 平均延迟毫秒,
    ROUND(AVG(s1.input_tokens), 0) AS 平均输入Tokens,
    ROUND(AVG(s1.output_tokens), 0) AS 平均输出Tokens,
    SUM(s1.output_tokens) AS 总输出Tokens,
    ROUND(SUM(s1.output_tokens) / 1000.0 * 0.015, 2) AS 总成本美元,
    ROUND(SUM(s1.output_tokens) / 1000.0 * 0.015 / COUNT(*), 4) AS 单条成本美元
FROM step1_intent_output s1

UNION ALL

SELECT
    'Step 3: 策略决策',
    COUNT(*),
    ROUND(AVG(s3.latency_ms), 0),
    NULL AS 平均输入Tokens,
    NULL AS 平均输出Tokens,
    NULL AS 总输出Tokens,
    ROUND(COUNT(*) * 224 / 1000.0 * 0.015, 2),  -- estimated output tokens ~224
    ROUND(224 / 1000.0 * 0.015, 4)
FROM step3_decision_output s3

UNION ALL

SELECT
    '合计',
    (SELECT COUNT(*) FROM step1_intent_output) + (SELECT COUNT(*) FROM step3_decision_output),
    NULL,
    NULL,
    NULL,
    (SELECT SUM(output_tokens) FROM step1_intent_output) +
        (SELECT COUNT(*) * 224 FROM step3_decision_output),
    ROUND((SELECT SUM(output_tokens) FROM step1_intent_output) / 1000.0 * 0.015 +
          (SELECT COUNT(*) FROM step3_decision_output) * 224 / 1000.0 * 0.015, 2),
    ROUND(((SELECT SUM(output_tokens) FROM step1_intent_output) / 1000.0 * 0.015 +
           (SELECT COUNT(*) FROM step3_decision_output) * 224 / 1000.0 * 0.015) /
          ((SELECT COUNT(*) FROM step1_intent_output) + (SELECT COUNT(*) FROM step3_decision_output)), 4);
```

**Expected result explanation:**
Returns "Step1: ~5,000 tickets, 1847ms average latency, 178 average output tokens, $13.35 total cost, $0.0027 per ticket." Step3 is similar scale; the combined cost is about $25 across 5,000 tickets ($0.005/ticket), far below human handling cost (about $4.69/ticket, assuming an agent handles 71/day at $150/day). The manager can demonstrate that AI saves about $11,100/month (estimated at 3,200/day × 30 days × $0.115 saved).

---

## Query 8: Ticket sentiment distribution vs urgency correlation

**Business background:**
The Customer Experience manager needs to understand the relationship between user sentiment and issue urgency, to refine support response strategy. The manager wants to know: are tickets from angry users always tagged as high urgency? Of tickets with neutral sentiment, how many are actually urgent? If lots of angry users are misclassified as "low" urgency, the AI's emotion understanding is lacking and needs adjustment. This query produces a sentiment × urgency crosstab to identify AI's blind spots and improve user experience.

**Query category:** Cross Tabulation + Aggregation
**Difficulty:** Basic
**Business role:** Customer Experience Manager

**Solution approach:**
This is a sentiment × urgency crosstab. From `step1_intent_output` JOIN `step1_eval_detail` (to pick up `is_correct` for accuracy) and JOIN `intent_category` for intent names. `WHERE run_id='eval_20241112_093000'` must pin to one evaluation, otherwise a ticket appearing in all 6 runs' details would be double-counted. The aggregation grain is the "sentiment × urgency" combination, so `GROUP BY sentiment, urgency`. The share column uses the window function `COUNT(*)*100.0/SUM(COUNT(*)) OVER (PARTITION BY sentiment)` — `PARTITION BY sentiment` makes the share represent "distribution across urgency within the same sentiment." Sort uses CASE to put high/medium/low in business priority order rather than alphabetical.

**SQL query:**
```sql
SELECT
    s1.sentiment AS 情绪,
    s1.urgency AS 紧急度,
    COUNT(*) AS 工单数,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (PARTITION BY s1.sentiment), 1) AS 该情绪占比百分比,
    ROUND(AVG(CASE WHEN sed.is_correct THEN 1.0 ELSE 0.0 END), 3) AS 意图识别准确率,
    GROUP_CONCAT(DISTINCT ic.intent_name_cn) AS 主要意图类型
FROM step1_intent_output s1
JOIN step1_eval_detail sed ON s1.output_id = sed.output_id
JOIN intent_category ic ON s1.primary_intent = ic.intent_code
WHERE sed.run_id = 'eval_20241112_093000'
GROUP BY s1.sentiment, s1.urgency
ORDER BY s1.sentiment,
    CASE s1.urgency WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END;
```

**Expected result explanation:**
Returns "angry sentiment + high urgency: 85 tickets (90%), 0.88 accuracy, main intents dispute_non_receipt / complaint_quality." The manager sees that 90% of angry users' tickets are correctly tagged high urgency, but 10% are still tagged medium or low and need work.

---

## Query 9: Daily ticket volume trend and AI processing capacity planning

**Business background:**
The operations analyst needs to forecast future ticket volume to plan AI system capacity. The analyst needs to answer: what was the ticket volume trend over the last 30 days? Are there cyclical patterns (low on weekends, high on weekdays)? Will peak season (e.g., Black Friday) spike volume to what level? If the current AI system handles 3,200/day and peak hits 8,000/day, does it need scaling? This query generates the daily ticket volume time series, helping the analyst forecast future demand from history and avoid overload.

**Query category:** Date/Time Analysis + Aggregation
**Difficulty:** Intermediate
**Business role:** Operations Analyst

**Solution approach:**
Time series aggregated by day: `DATE(submitted_at)` truncates timestamp to day, then `GROUP BY`. Day of week uses `STRFTIME('%w', submitted_at)` to get 0–6 (0=Sunday) and CASE translates it. JOIN `user` to compute daily VIP share. Tickets with attachments use `COUNT(CASE WHEN has_attachment THEN 1 END)` — CASE returns NULL when not matched and COUNT skips NULLs, the idiomatic "conditional count" pattern. `WHERE DATE(submitted_at) >= DATE('2024-12-01','-30 days')` limits to the last 30 days, and `ORDER BY 日期 DESC` puts the most recent dates first for easy trend viewing.

**SQL query:**
```sql
SELECT
    DATE(rt.submitted_at) AS 日期,
    CASE CAST(STRFTIME('%w', rt.submitted_at) AS INTEGER)
        WHEN 0 THEN '周日'
        WHEN 1 THEN '周一'
        WHEN 2 THEN '周二'
        WHEN 3 THEN '周三'
        WHEN 4 THEN '周四'
        WHEN 5 THEN '周五'
        WHEN 6 THEN '周六'
    END AS 星期,
    COUNT(*) AS 工单数,
    COUNT(CASE WHEN rt.has_attachment THEN 1 END) AS 含附件工单数,
    ROUND(AVG(CASE WHEN u.tier_code IN ('vip_gold', 'vip_platinum') THEN 1.0 ELSE 0.0 END), 3) AS VIP占比,
    GROUP_CONCAT(DISTINCT rt.channel) AS 提交渠道
FROM raw_ticket rt
JOIN user u ON rt.user_id = u.user_id
WHERE DATE(rt.submitted_at) >= DATE('2024-12-01', '-30 days')
GROUP BY DATE(rt.submitted_at)
ORDER BY 日期 DESC;
```

**Expected result explanation:**
Returns per-day statistics, e.g., "2024-11-15 (Friday): ~180 tickets, ~55 with attachments, 0.20 VIP share, channels web_form / app / chat / email / phone_transcript." The analyst sees weekdays average ~170–200/day and weekends drop to ~120/day (this dataset 5,000 tickets ÷ 30 days ≈ 167/day average) and plans resources accordingly.

---

## Query 10: LLM Judge score vs human annotation agreement

**Business background:**
When the ML researcher validates the reliability of the LLM-as-Judge method, they need to compare the LLM Judge's scores against the correlation with human annotation results. The researcher wants to know: of samples the LLM Judge rated highly (4–5), how many actually matched human annotation? Does the LLM Judge have a systematic bias (such as inflated scores on correctly classified samples)? If Judge scores don't correlate with actual accuracy, the Judge itself needs calibration. This query produces a Judge-score accuracy distribution to help assess the Judge method's effectiveness.

**Query category:** Aggregation + Statistical Analysis
**Difficulty:** Advanced
**Business role:** ML Researcher

**Solution approach:**
This query checks whether LLM Judge scores actually correlate with real accuracy (does the Judge over-rate?). First use CASE to bucket `judge_reasoning_score` into high / medium / low, `GROUP BY` the same CASE expression. For each bucket, compute actual accuracy `AVG(is_correct)` and average Judge score for contrast. **SQLite has no built-in `STDEV()`, so standard deviation is hand-computed with `SQRT(AVG(x*x) - AVG(x)*AVG(x))` — the population-variance formula** — and this is the biggest teaching point in the query. `WHERE run_id` pins to one evaluation. The `ORDER BY` also uses CASE to keep buckets in high → low order, not alphabetical.

**SQL query:**
```sql
SELECT
    CASE
        WHEN sed.judge_reasoning_score >= 4 THEN '高分(4-5)'
        WHEN sed.judge_reasoning_score >= 3 THEN '中分(3)'
        ELSE '低分(1-2)'
    END AS Judge评分档位,
    COUNT(*) AS 样本数,
    SUM(CASE WHEN sed.is_correct THEN 1 ELSE 0 END) AS 正确分类数,
    ROUND(AVG(CASE WHEN sed.is_correct THEN 1.0 ELSE 0.0 END), 3) AS 实际准确率,
    ROUND(AVG(sed.judge_reasoning_score), 2) AS 平均推理评分,
    ROUND(AVG(sed.judge_completeness_score), 2) AS 平均完整性评分,
    -- Native SQLite has no STDEV(): hand-compute population stddev as sqrt(E[x^2] - E[x]^2)
    ROUND(SQRT(
        AVG(sed.judge_reasoning_score * sed.judge_reasoning_score)
        - AVG(sed.judge_reasoning_score) * AVG(sed.judge_reasoning_score)
    ), 2) AS 推理评分标准差
FROM step1_eval_detail sed
WHERE sed.run_id = 'eval_20241112_093000'
GROUP BY
    CASE
        WHEN sed.judge_reasoning_score >= 4 THEN '高分(4-5)'
        WHEN sed.judge_reasoning_score >= 3 THEN '中分(3)'
        ELSE '低分(1-2)'
    END
ORDER BY
    CASE
        WHEN sed.judge_reasoning_score >= 4 THEN 1
        WHEN sed.judge_reasoning_score >= 3 THEN 2
        ELSE 3
    END;
```

**Expected result explanation:**
Returns "High (4–5): 320 samples, 305 correct, 0.953 actual accuracy, 4.4 average reasoning score." The researcher sees Judge high-scores correlate strongly with high accuracy, but 15 high-scored samples are still misclassified — these false positives need a closer look.

---

## Query 11: Product category vs ticket type correlation

**Business background:**
The product operations manager needs to understand complaint patterns by product category to improve quality and logistics. The manager wants to know: are bedding products more prone to damage? Are lighting products returned more often? Are kitchen products complained about for quality more? This information helps the manager identify high-risk categories and feed improvement requests back to the supply chain team. For example, if "bedding × damage complaint" is unusually high, packaging quality needs review; if "lighting × 7-day no-questions-asked return" is high, the photos may not match the actual product.

**Query category:** Join + Cross Tabulation
**Difficulty:** Intermediate
**Business role:** Product Operations

**Solution approach:**
Tickets need to go through `order` to reach `product` to get the category, so chain `raw_ticket LEFT JOIN order LEFT JOIN product`. **You must use LEFT JOIN here: 30% of inquiry-type tickets have no order_id, and an INNER JOIN would drop them all**, distorting the denominator. But then `WHERE p.category IS NOT NULL` deliberately filters out tickets without a category (no category, no way to bucket). Then JOIN `step1_intent_output` and `intent_category` for the intent name. The aggregation grain is "category × intent," the share uses a window `PARTITION BY category`, and `HAVING COUNT >= 3` filters out cells with too few samples. **The expected result must emphasize: intents and categories are sampled independently (ER §7.6 anti-trap), and this query is a correlation-test template, not a built-in strong correlation.

**SQL query:**
```sql
SELECT
    p.category AS 商品品类,
    ic.intent_name_cn AS 工单意图,
    COUNT(DISTINCT rt.ticket_id) AS 工单数,
    ROUND(AVG(o.order_amount), 2) AS 平均订单金额,
    ROUND(COUNT(DISTINCT rt.ticket_id) * 100.0 /
        SUM(COUNT(DISTINCT rt.ticket_id)) OVER (PARTITION BY p.category), 1) AS 该品类占比,
    GROUP_CONCAT(DISTINCT p.seller_type_code) AS 商家类型
FROM raw_ticket rt
LEFT JOIN "order" o ON rt.order_id = o.order_id
LEFT JOIN product p ON o.product_id = p.product_id
JOIN step1_intent_output s1 ON rt.ticket_id = s1.ticket_id
JOIN intent_category ic ON s1.primary_intent = ic.intent_code
WHERE p.category IS NOT NULL
GROUP BY p.category, ic.intent_name_cn
HAVING COUNT(DISTINCT rt.ticket_id) >= 3  -- at least 3 tickets
ORDER BY p.category, 工单数 DESC;
```

**Expected result explanation:**
Returns a category × intent crosstab like "Bedding - Shipping dispute, damaged: 18 tickets, $128 average amount, 35% category share, nestmart_original merchant." The manager can compare ticket-intent distributions and average amounts cell by cell to pinpoint which "category-intent" combinations warrant attention (then bring in business judgment on whether the cause is packaging or product description). Note: in this dataset, ticket intent and product category are sampled independently — no built-in "category X is necessarily prone to damage" correlation. In real business, you can use this query template to test for such correlations.

---

## Query 12: Evaluation run history trend analysis

**Business background:**
The Tech Lead needs to show the VP of Engineering the AI system's continuous improvement journey. The VP cares about: what metric improvements did Prompt iteration deliver over the past few weeks? What is the trend in Step1 accuracy and Step3 rule violation rate? Is the improvement stable? Is there regression risk? This query generates a time series chart of evaluation metric changes, helping the Tech Lead visualize team engineering output and argue for more resources.

**Query category:** Time Series + Trend Analysis
**Difficulty:** Intermediate
**Business role:** Tech Lead

**Solution approach:**
Query `evaluation_run` directly, and aliased JOIN `prompt_version` twice for the Step1 and Step3 version codes. `WHERE run_status='completed'` filters to completed runs only. Run duration is `(JULIANDAY(completed_at)-JULIANDAY(started_at))*24*60` converting day-diff to minutes. **The key is `ORDER BY started_at` in ascending order**, so the reader sees a clear curve of v1→v5 monotonically rising accuracy and monotonically falling violation rate (matches ER §7.6 trap T2). No aggregation, because each row in `evaluation_run` is already a run-level summary.

**SQL query:**
```sql
SELECT
    er.run_id AS 运行ID,
    DATETIME(er.started_at) AS 运行时间,
    pv1.version_code AS Step1Prompt版本,
    pv3.version_code AS Step3Prompt版本,
    er.triggered_by AS 触发方式,
    ROUND(er.step1_accuracy, 3) AS Step1准确率,
    ROUND(er.step3_rule_violation_rate, 3) AS Step3违反率,
    ROUND(er.step1_judge_avg_score, 2) AS Step1Judge均分,
    ROUND(er.step3_judge_avg_score, 2) AS Step3Judge均分,
    er.total_tickets_evaluated AS 评估工单数,
    CAST((JULIANDAY(er.completed_at) - JULIANDAY(er.started_at)) * 24 * 60 AS INTEGER) AS 运行时长分钟
FROM evaluation_run er
JOIN prompt_version pv1 ON er.step1_prompt_id = pv1.prompt_id
JOIN prompt_version pv3 ON er.step3_prompt_id = pv3.prompt_id
WHERE er.run_status = 'completed'
ORDER BY er.started_at;
```

**Expected result explanation:**
Returns the full iteration arc across 6 runs: `eval_20241110 (v1, 0.81 accuracy, 0.12 violation) → eval_20241112 (v2, 0.87 / 0.042) → eval_20241115 (v3, 0.875 / 0.040) → eval_20241119 (v4, 0.890 / 0.035) → eval_20241123 (v5, 0.905 / 0.030) → eval_20241128 (v5 regression, 0.902 / 0.031)`. The Tech Lead can showcase a clear engineering story of "5 versions cumulatively improving accuracy by +9.5pp and reducing rule violation by 75%."

---

## Query 13: Profile of tickets that frequently violate rules

**Business background:**
The Quality Analyst needs to dig into why certain tickets are prone to rule violations. The analyst wants to know: which user attributes (tier, refund history) and order attributes (amount, merchant type) strongly correlate with rule violations? For example, if third-party merchant orders have an unusually high violation rate, the AI hasn't internalized the "hand off to merchant" rule. This query produces a feature distribution of violation cases, helping the analyst pinpoint root causes and feed improvement suggestions to the ML team.

**Query category:** Join + Feature Analysis
**Difficulty:** Advanced
**Business role:** Quality Analyst

**Solution approach:**
First, the CTE `violation_tickets` uses `SELECT DISTINCT ticket_id` to extract de-duplicated "v1 run critical/high severe-violation tickets." Then use `UNION ALL` to stack two sections: the first breaks down by user tier (`raw_ticket JOIN user LEFT JOIN order`), the second by merchant type (need to JOIN `product`, use INNER JOIN because we only want tickets with both order and product). The CTE is valuable because the "severe violation tickets" set is reused in both sections, sparing you from writing the filter logic twice. **The expected result must state: violation cases and seller_type are sampled independently (ER §7.6), so this query is a correlation-test template, not a built-in concentration of violations in third_party.

**SQL query:**
```sql
WITH violation_tickets AS (
    SELECT DISTINCT rvc.ticket_id
    FROM rule_violation_case rvc
    WHERE rvc.run_id = 'eval_20241110_140000'
        AND rvc.impact_severity IN ('critical', 'high')
)
SELECT
    '用户特征' AS 特征类别,
    u.tier_code AS 特征值,
    COUNT(DISTINCT rt.ticket_id) AS 违反工单数,
    ROUND(AVG(u.refund_count_30days), 1) AS 平均30天退款次数,
    ROUND(AVG(o.order_amount), 2) AS 平均订单金额,
    GROUP_CONCAT(DISTINCT dr.rule_id) AS 违反规则列表
FROM violation_tickets vt
JOIN raw_ticket rt ON vt.ticket_id = rt.ticket_id
JOIN user u ON rt.user_id = u.user_id
LEFT JOIN "order" o ON rt.order_id = o.order_id
JOIN rule_violation_case rvc ON vt.ticket_id = rvc.ticket_id
JOIN decision_rule dr ON rvc.rule_id = dr.rule_id
GROUP BY u.tier_code

UNION ALL

SELECT
    '商家类型',
    p.seller_type_code,
    COUNT(DISTINCT rt.ticket_id),
    ROUND(AVG(u.refund_count_30days), 1),
    ROUND(AVG(o.order_amount), 2),
    GROUP_CONCAT(DISTINCT dr.rule_id)
FROM violation_tickets vt
JOIN raw_ticket rt ON vt.ticket_id = rt.ticket_id
JOIN user u ON rt.user_id = u.user_id
JOIN "order" o ON rt.order_id = o.order_id
JOIN product p ON o.product_id = p.product_id
JOIN rule_violation_case rvc ON vt.ticket_id = rvc.ticket_id
JOIN decision_rule dr ON rvc.rule_id = dr.rule_id
GROUP BY p.seller_type_code
ORDER BY 特征类别, 违反工单数 DESC;
```

**Expected result explanation:**
Returns "User attribute - regular: 12 violation tickets, 1.8 average refund count, $75 average amount, violations R002/R003" and "Merchant type - third_party: 8 violations, $85 average amount, violations R002/R003." This query breaks down severe (critical/high) violation cases along two dimensions — user tier and merchant type — to help the analyst pinpoint which user/merchant types are more prone to severe violations. Note: in this dataset, rule-violation cases (`rule_violation_case`) most frequently involve R002 (third-party hand-off) and R003 (high amount) (see Query 4), but case-to-ticket seller_type is sampled independently, so it does not pre-bake "third_party necessarily concentrates R002 violations" correlation. This template can be used to test for such correlations on real data.

---

## Query 14: Ticket handling SLA monitoring

**Business background:**
The support operations manager sets SLA targets: VIP tickets handled within 24 hours, regular customers within 48 hours. Every morning the manager needs to check: how many tickets are overtime and unhandled? What is the tier distribution of overdue tickets? Is the AI system promptly escalating urgent tickets to humans? This query produces an SLA compliance report, helping the manager identify tickets needing expedited handling and avoid escalating complaints.

**Query category:** Date/Time Calculation + SLA Monitoring
**Difficulty:** Intermediate
**Business role:** Operations Manager

**Solution approach:**
The correct SLA definition is "handling time = `step3.processed_at - submitted_at`," not "ticket age = now - submitted," so you must JOIN `step3_decision_output` to get the completion time. Per-tier SLA thresholds use CASE (VIP 24h / others 48h). Compliance check: `(JULIANDAY(processed_at)-JULIANDAY(submitted_at))*24 <= threshold`, with SUM(CASE...) counting compliant and overdue separately, then computing the compliance rate. `GROUP BY tier_code`. **This is a counterintuitive trap (ER §7.6 T6): because AI handles in seconds, all tiers' compliance rates will be ≈100% — and that's exactly the teaching point; the real human latency hides inside `escalate_to_human=1` tickets.** Sort uses CASE to order tiers from highest to lowest.

**SQL query:**
```sql
-- SLA = "handling time" = step3 decision completion time - ticket submission time (not "ticket age = now - submitted")
-- AI handles in seconds, so compliance should be close to 100%; overdue mainly happens on human-escalated tickets
SELECT
    u.tier_code AS 会员等级,
    CASE
        WHEN u.tier_code IN ('vip_gold', 'vip_platinum') THEN 24
        ELSE 48
    END AS SLA小时,
    COUNT(*) AS 工单总数,
    SUM(CASE
        WHEN (JULIANDAY(s3.processed_at) - JULIANDAY(rt.submitted_at)) * 24 <=
            CASE WHEN u.tier_code IN ('vip_gold', 'vip_platinum') THEN 24 ELSE 48 END
        THEN 1 ELSE 0
    END) AS SLA内工单数,
    SUM(CASE
        WHEN (JULIANDAY(s3.processed_at) - JULIANDAY(rt.submitted_at)) * 24 >
            CASE WHEN u.tier_code IN ('vip_gold', 'vip_platinum') THEN 24 ELSE 48 END
        THEN 1 ELSE 0
    END) AS 超时工单数,
    ROUND(SUM(CASE
        WHEN (JULIANDAY(s3.processed_at) - JULIANDAY(rt.submitted_at)) * 24 <=
            CASE WHEN u.tier_code IN ('vip_gold', 'vip_platinum') THEN 24 ELSE 48 END
        THEN 1.0 ELSE 0.0
    END) / COUNT(*) * 100, 1) AS SLA达标率百分比,
    ROUND(MAX((JULIANDAY(s3.processed_at) - JULIANDAY(rt.submitted_at)) * 24), 2) AS 最大处理小时数
FROM raw_ticket rt
JOIN user u ON rt.user_id = u.user_id
JOIN step3_decision_output s3 ON rt.ticket_id = s3.ticket_id
WHERE DATE(rt.submitted_at) >= DATE('2024-12-01', '-7 days')
GROUP BY u.tier_code
ORDER BY
    CASE u.tier_code
        WHEN 'vip_platinum' THEN 1
        WHEN 'vip_gold' THEN 2
        WHEN 'vip_silver' THEN 3
        WHEN 'regular' THEN 4
        ELSE 5
    END;
```

**Expected result explanation:**
Returns something like "vip_gold: 24h SLA, ~190 total tickets, ~190 within SLA, 0 overdue, 100.0% compliance, max handling 0.01 hours." Because AI handles in seconds (`processed_at - submitted_at` ≈ a few seconds), every tier's compliance is close to 100% — and that's precisely AI customer service's core value vs humans (AHT ~8 min). What the manager really needs to watch is the slice of tickets escalated to humans (`escalate_to_human = 1`), which enters the human queue and incurs real latency (this query only reflects AI auto-handling latency). In a 7-day rolling window on this dataset, regular tier (48h SLA) has ~900 tickets and vip_silver/gold/platinum combined have ~230.

---

## Query 15: AI decision confidence vs actual accuracy correlation

**Business background:**
When evaluating whether the AI system "knows what it knows," the ML engineer needs to check: are high-confidence (>0.9) decisions actually more accurate? Should low-confidence decisions auto-escalate? If high-confidence decisions still have a 20% error rate, the model is overconfident and needs calibration. This query generates a confidence-bucket vs accuracy comparison, helping the engineer set a reasonable "escalate to human" threshold (e.g., confidence <0.7 auto-escalates).

**Query category:** Statistical Analysis + Bucketing
**Difficulty:** Advanced
**Business role:** ML Engineer

**Solution approach:**
First, a CTE joins `step3_decision_output` with `step3_eval_detail`, and inside the CTE uses CASE to bucket `confidence` into 4 tiers. `WHERE run_id` pins to one evaluation. The outer query `GROUP BY` the bucket and computes per-bucket rule compliance `AVG(rule_check_passed)` and escalation rate `AVG(escalate_to_human)`. Using a CTE rather than embedding the CASE in the outer query is because the bucket expression is fairly complex — computing it once in the CTE and grouping on the label later is more readable and avoids repetition. `ORDER BY` uses CASE to keep high → low bucket order. Teaching point: validating that "high confidence really is more accurate," to set the auto-escalation threshold.

**SQL query:**
```sql
WITH confidence_buckets AS (
    SELECT
        s3.output_id,
        s3.action,
        s3.confidence,
        s3.escalate_to_human,
        sed.rule_check_passed,
        CASE
            WHEN s3.confidence >= 0.90 THEN '高置信(>=0.90)'
            WHEN s3.confidence >= 0.75 THEN '中高置信(0.75-0.89)'
            WHEN s3.confidence >= 0.60 THEN '中置信(0.60-0.74)'
            ELSE '低置信(<0.60)'
        END AS 置信度档位
    FROM step3_decision_output s3
    JOIN step3_eval_detail sed ON s3.output_id = sed.output_id
    WHERE sed.run_id = 'eval_20241112_093000'
)
SELECT
    置信度档位,
    COUNT(*) AS 样本数,
    ROUND(AVG(confidence), 3) AS 平均置信度,
    SUM(CASE WHEN rule_check_passed THEN 1 ELSE 0 END) AS 规则检查通过数,
    ROUND(AVG(CASE WHEN rule_check_passed THEN 1.0 ELSE 0.0 END), 3) AS 规则遵守率,
    SUM(CASE WHEN escalate_to_human THEN 1 ELSE 0 END) AS 升级人工数,
    ROUND(AVG(CASE WHEN escalate_to_human THEN 1.0 ELSE 0.0 END), 3) AS 升级率,
    GROUP_CONCAT(DISTINCT action) AS 决策类型分布
FROM confidence_buckets
GROUP BY 置信度档位
ORDER BY
    CASE 置信度档位
        WHEN '高置信(>=0.90)' THEN 1
        WHEN '中高置信(0.75-0.89)' THEN 2
        WHEN '中置信(0.60-0.74)' THEN 3
        ELSE 4
    END;
```

**Expected result explanation:**
Returns "High confidence (>=0.90): 280 samples, 0.91 average confidence, 275 passed, 0.982 rule compliance, 8 escalated, 0.029 escalation rate." The engineer finds high-confidence decisions have 98% rule compliance, but 2% still violate, suggesting a threshold of "confidence <0.75 auto-escalate" for safety.

---

## Query 16: User lifetime value and complaint relationship analysis

**Business background:**
The Customer Success Manager needs to balance customer satisfaction with operating cost. The manager wants to know: is the cost of handling complaints from high-value users (lifetime spend >$3000) worth it? What ticket types do these users mostly file? If high-value users mostly file inquiries (low handling cost) while low-value users mostly file refund disputes (high handling cost), the manager can adjust support resource allocation. This query produces the relationship between user value segments and ticket cost, helping the manager optimize ROI.

**Query category:** Join + Customer Segmentation
**Difficulty:** Advanced
**Business role:** Customer Success Manager

**Solution approach:**
First the CTE `user_segments` buckets users by `total_spent_amount` into 4 value tiers via CASE. Then JOIN `raw_ticket → step1_intent_output → intent_category`, and `LEFT JOIN step3_decision_output` (use LEFT in case some tickets lack a decision output and would otherwise be dropped). The aggregation grain is "one row per value tier": tickets per user is `COUNT(DISTINCT ticket)/COUNT(DISTINCT user)`, escalation rate is `SUM(escalate)/COUNT(*)`. **The expected result must declare independence (ER §7.6): ticket type and value segment are generated independently, each tier's escalation rate mainly reflects the global ~15%, no preset "high-value customers have fewer complaints" — this query is a template for testing that hypothesis.

**SQL query:**
```sql
WITH user_segments AS (
    SELECT
        user_id,
        user_name,
        tier_code,
        total_spent_amount,
        CASE
            WHEN total_spent_amount >= 5000 THEN '高价值(>=$5000)'
            WHEN total_spent_amount >= 1500 THEN '中高价值($1500-4999)'
            WHEN total_spent_amount >= 500 THEN '中价值($500-1499)'
            ELSE '低价值(<$500)'
        END AS 价值分层
    FROM user
)
SELECT
    us.价值分层,
    COUNT(DISTINCT rt.ticket_id) AS 工单数,
    COUNT(DISTINCT us.user_id) AS 用户数,
    ROUND(COUNT(DISTINCT rt.ticket_id) * 1.0 / COUNT(DISTINCT us.user_id), 2) AS 人均工单数,
    ROUND(AVG(us.total_spent_amount), 2) AS 平均消费金额,
    GROUP_CONCAT(DISTINCT ic.intent_name_cn) AS 主要工单类型,
    ROUND(SUM(CASE WHEN s3.escalate_to_human THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) AS 升级人工比例
FROM user_segments us
JOIN raw_ticket rt ON us.user_id = rt.user_id
JOIN step1_intent_output s1 ON rt.ticket_id = s1.ticket_id
JOIN intent_category ic ON s1.primary_intent = ic.intent_code
LEFT JOIN step3_decision_output s3 ON rt.ticket_id = s3.ticket_id
GROUP BY us.价值分层
ORDER BY
    CASE us.价值分层
        WHEN '高价值(>=$5000)' THEN 1
        WHEN '中高价值($1500-4999)' THEN 2
        WHEN '中价值($500-1499)' THEN 3
        ELSE 4
    END;
```

**Expected result explanation:**
Returns something like "High value (>=$5000): 15 tickets, 8 users, 1.88 tickets per user, $8250 average spend, covers multiple ticket types, 6.7% escalation rate." This query breaks down tickets per user and escalation rate by spend tier, helping the manager assess the complaint-handling cost for each value tier. Note: in this dataset, ticket intent and user value tier are generated independently, so each tier's escalation rate mainly reflects the global ~15% escalation rate. In real business, you can use this template to test the hypothesis "high-value users file more inquiries and fewer disputes" to optimize support resource allocation.

---

## Query 17: Annotation dispute cases and arbitration efficiency analysis

**Business background:**
The annotation Quality Manager needs to monitor the team's dispute-resolution efficiency. The manager cares about: how many annotation-disagreement cases have been resolved? What is the arbitrator's average handling time? Are unresolved cases piling up? If pending cases exceed 20, arbitration capacity is insufficient and needs reinforcement. This query produces a dispute-case status dashboard, helping the manager intervene in time to ensure the annotation dataset is delivered on schedule.

**Query category:** Join + Status Tracking
**Difficulty:** Intermediate
**Business role:** Annotation Manager

**Solution approach:**
Look only at disagreement cases, so `WHERE is_agreement = 0` is the first filter. From `annotation_agreement` JOIN `annotation_ground_truth` (using `annotation_id_1` to get the annotation date for computing backlog days). Group by `resolution_status` (pending / resolved / escalated) to tally cases. The share column uses the window `COUNT(*)*100.0/SUM(COUNT(*)) OVER ()` — **the empty `OVER ()` means "use the whole-table total as denominator,"** the standard window idiom for computing shares. Backlog days is `JULIANDAY(reference date)-JULIANDAY(annotation_date)`. Sort uses CASE to put pending on top, because pending cases need the most manager attention.

**SQL query:**
```sql
SELECT
    aa.resolution_status AS 解决状态,
    COUNT(*) AS 案例数,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 1) AS 占比百分比,
    COUNT(DISTINCT aa.arbitrator_id) AS 涉及仲裁员数,
    COUNT(DISTINCT aa.ticket_id) AS 涉及工单数,
    ROUND(AVG(JULIANDAY('2024-12-01') - JULIANDAY(ag1.annotation_date)), 1) AS 平均积压天数,
    GROUP_CONCAT(DISTINCT aa.disagreement_field) AS 争议字段类型
FROM annotation_agreement aa
JOIN annotation_ground_truth ag1 ON aa.annotation_id_1 = ag1.annotation_id
WHERE aa.is_agreement = 0  -- look only at disagreement cases
GROUP BY aa.resolution_status
ORDER BY
    CASE aa.resolution_status
        WHEN 'pending' THEN 1
        WHEN 'escalated' THEN 2
        WHEN 'resolved' THEN 3
        ELSE 4
    END;
```

**Expected result explanation:**
Returns "pending: 8 cases (32%), 1 arbitrator, 8 tickets, 3.5 day average backlog, disagreement field primary_intent." The manager sees pending share is 32% with average 3.5-day backlog — within acceptable range, but worth continued monitoring.

---

## Query 18: Multi-channel ticket quality comparison analysis

**Business background:**
The product manager needs to evaluate ticket quality by submission channel (web form, app, in-app chat, email, phone transcript) to improve the user experience. The manager wants to know: which channel has the clearest text (highest AI accuracy)? Which channel has the most negative sentiment? Should some channels' guidance copy be improved? For example, if "phone transcript" has unusually low accuracy (65%), the speech-to-text quality may be poor and the ASR model needs work.

**Query category:** Aggregation + Cross-channel Analysis
**Difficulty:** Intermediate
**Business role:** Product Manager

**Solution approach:**
Compare ticket quality across submission channels. The chain is `raw_ticket JOIN step1_intent_output JOIN step1_eval_detail` (eval_detail provides accuracy). `WHERE run_id` pins to one evaluation. `GROUP BY channel`: accuracy `AVG(is_correct)`, average text length `AVG(LENGTH(raw_text))`, angry share and high-urgency share via conditional `AVG(CASE...)`. **One scale gotcha: because we JOIN `step1_eval_detail`, this query only covers the ~500 evaluation samples, not all 5,000 tickets** — the expected result must call this out, otherwise readers will think web_form has only a few hundred tickets (actual full count is about 2,500). Teaching point: find the worst-quality channel to improve guidance copy.

**SQL query:**
```sql
SELECT
    rt.channel AS 提交渠道,
    COUNT(DISTINCT rt.ticket_id) AS 工单数,
    ROUND(AVG(CASE WHEN sed.is_correct THEN 1.0 ELSE 0.0 END), 3) AS 意图识别准确率,
    ROUND(AVG(LENGTH(rt.raw_text)), 0) AS 平均文本长度,
    ROUND(AVG(CASE WHEN s1.sentiment = 'angry' THEN 1.0 ELSE 0.0 END), 3) AS 愤怒情绪比例,
    ROUND(AVG(CASE WHEN s1.urgency = 'high' THEN 1.0 ELSE 0.0 END), 3) AS 高紧急度比例,
    ROUND(AVG(s1.latency_ms), 0) AS 平均处理延迟ms,
    SUM(CASE WHEN rt.has_attachment THEN 1 ELSE 0 END) AS 含附件工单数
FROM raw_ticket rt
JOIN step1_intent_output s1 ON rt.ticket_id = s1.ticket_id
JOIN step1_eval_detail sed ON s1.output_id = sed.output_id
WHERE sed.run_id = 'eval_20241112_093000'
GROUP BY rt.channel
ORDER BY 工单数 DESC;
```

**Expected result explanation:**
Returns something like "web_form: ~250 tickets (in the evaluation sample), 0.89 accuracy, 245 average length, 0.15 angry share, 0.62 high-urgency share, 1850ms latency, ~75 with attachments." The product manager sees web form tickets have the highest quality (0.89 accuracy), email channel is slightly lower (0.82), and can improve the guidance copy on the email submission page. Note: this query only covers ~500 evaluation samples; in the full ticket set (5,000), web_form is about 2,500.

---

## Query 19: Prompt change impact scope prediction

**Business background:**
Before modifying a Prompt, the ML engineer needs to assess the scope of impact to avoid introducing regression bugs. The engineer wants to know: if we change the Step1 Prompt to improve dispute_non_receipt accuracy, will it affect other intents? Which intents may be affected? Which samples should we focus regression testing on? This query analyzes the current Prompt's performance per intent, helping the engineer identify weak spots and design targeted test cases.

**Query category:** Aggregation + Classification Report
**Difficulty:** Advanced
**Business role:** ML Engineer

**Solution approach:**
The goal is to produce a classification report: per true-intent accuracy + what it gets misclassified into. First the CTE `intent_performance` joins `step1_eval_detail` with `annotation_ground_truth` (for the true intent) and `intent_category` (for the name), aggregates by true intent to compute accuracy, and uses `GROUP_CONCAT(DISTINCT predicted_intent)` to make a list of "what it gets misclassified as." The outer query adds two derived columns: "quality rating" and "change risk assessment" via CASE. **Why the CTE: the outer CASE has to be based on the post-aggregation accuracy, which you can't do in the same GROUP BY as the aggregation itself, so aggregate first (CTE) and classify later (outer).** `ORDER BY 准确率` puts the weakest intents — the ones most needing regression testing — at the top.

**SQL query:**
```sql
WITH intent_performance AS (
    SELECT
        ag.true_primary_intent AS intent_code,
        ic.intent_name_cn,
        COUNT(*) AS 样本总数,
        SUM(CASE WHEN sed.is_correct THEN 1 ELSE 0 END) AS 正确分类数,
        ROUND(AVG(CASE WHEN sed.is_correct THEN 1.0 ELSE 0.0 END), 3) AS 准确率,
        ROUND(AVG(sed.judge_reasoning_score), 2) AS 平均推理评分,
        GROUP_CONCAT(DISTINCT sed.predicted_intent) AS 被误判为意图列表
    FROM step1_eval_detail sed
    JOIN annotation_ground_truth ag ON sed.annotation_id = ag.annotation_id
    JOIN intent_category ic ON ag.true_primary_intent = ic.intent_code
    WHERE sed.run_id = 'eval_20241112_093000'
    GROUP BY ag.true_primary_intent, ic.intent_name_cn
)
SELECT
    intent_name_cn AS 意图名称,
    样本总数,
    正确分类数,
    准确率,
    平均推理评分,
    被误判为意图列表,
    CASE
        WHEN 准确率 >= 0.90 THEN '✓ 优秀'
        WHEN 准确率 >= 0.75 THEN '→ 良好'
        ELSE '⚠ 需改进'
    END AS 质量评级,
    CASE
        WHEN 准确率 < 0.75 THEN '高风险:修改可能进一步降低'
        WHEN 准确率 BETWEEN 0.75 AND 0.85 THEN '中风险:需回归测试'
        ELSE '低风险:可放心修改'
    END AS 变更风险评估
FROM intent_performance
ORDER BY 准确率, 样本总数 DESC;
```

**Expected result explanation:**
Returns "dispute_non_receipt: 125 samples, 111 correct, 0.888 accuracy, 3.9 reasoning score, misclassified as refund_request, → Good, Medium risk." The engineer sees dispute_non_receipt is already at 0.888 with room to grow, and when modifying the Prompt, the easily-confused refund_request intent needs careful regression testing.

---

## Query 20: Executive dashboard key metric summary

**Business background:**
The VP of Engineering needs a quick health check of the AI system at the Monday morning meeting. The VP cares about 5 core questions: 1) how many tickets were handled last week? 2) is intent recognition accuracy on target? 3) is rule violation rate under control? 4) is human escalation share reasonable? 5) is system performance stable? This query produces an Executive Summary with the latest values and week-over-week changes for all key metrics, helping the VP grasp the full picture in 5 minutes and make resource allocation decisions.

**Query category:** Multi-table Aggregation + Executive Summary
**Difficulty:** Advanced
**Business role:** Executive (VP/CTO)

**Solution approach:**
This is a one-page executive dashboard, using `UNION ALL` to stack 7 KPIs from different tables into a "metric-value-target-status" four-column view (ticket volume, VIP share, accuracy, violation rate, automation rate, latency, cost). Each section queries one related table and uses CASE to compare against the target with ✓ / ⚠. **The most memorable SQLite limitation: middle branches of a UNION cannot directly write `ORDER BY ... LIMIT`, so "fetch the most recent completed run" must be wrapped in a subquery: `(SELECT * FROM evaluation_run WHERE run_status='completed' ORDER BY started_at DESC LIMIT 1)`, then field selection happens off that subquery.** Teaching point: how to assemble heterogeneous KPIs into a 5-minute-readable Executive Summary.

**SQL query:**
```sql
SELECT
    '业务量指标' AS 指标类别,
    '总工单处理量(本周)' AS 指标名称,
    CAST(COUNT(DISTINCT rt.ticket_id) AS TEXT) AS 指标值,
    '' AS 目标值,
    '' AS 状态
FROM raw_ticket rt
WHERE DATE(rt.submitted_at) >= DATE('2024-12-01', '-7 days')

UNION ALL

SELECT
    '业务量指标',
    'VIP工单占比',
    ROUND(AVG(CASE WHEN u.tier_code IN ('vip_gold', 'vip_platinum') THEN 1.0 ELSE 0.0 END) * 100, 1) || '%',
    '15-25%',
    CASE
        WHEN AVG(CASE WHEN u.tier_code IN ('vip_gold', 'vip_platinum') THEN 1.0 ELSE 0.0 END) BETWEEN 0.15 AND 0.25 THEN '✓'
        ELSE '⚠'
    END
FROM raw_ticket rt
JOIN user u ON rt.user_id = u.user_id
WHERE DATE(rt.submitted_at) >= DATE('2024-12-01', '-7 days')

UNION ALL

-- Middle branches of a compound query cannot use ORDER BY / LIMIT directly (SQLite limitation),
-- so use a subquery to pick "the most recent completed run" and read the metric off it
SELECT
    '质量指标',
    'Step1意图识别准确率',
    ROUND(er.step1_accuracy * 100, 1) || '%',
    '>85%',
    CASE WHEN er.step1_accuracy >= 0.85 THEN '✓' ELSE '⚠' END
FROM (
    SELECT * FROM evaluation_run
    WHERE run_status = 'completed'
    ORDER BY started_at DESC LIMIT 1
) er

UNION ALL

SELECT
    '质量指标',
    'Step3规则违反率',
    ROUND(er.step3_rule_violation_rate * 100, 1) || '%',
    '<5%',
    CASE WHEN er.step3_rule_violation_rate < 0.05 THEN '✓' ELSE '⚠' END
FROM (
    SELECT * FROM evaluation_run
    WHERE run_status = 'completed'
    ORDER BY started_at DESC LIMIT 1
) er

UNION ALL

SELECT
    '效率指标',
    'AI自动处理率(未升级人工)',
    ROUND((1 - AVG(CASE WHEN s3.escalate_to_human THEN 1.0 ELSE 0.0 END)) * 100, 1) || '%',
    '>75%',
    CASE
        WHEN AVG(CASE WHEN s3.escalate_to_human THEN 1.0 ELSE 0.0 END) <= 0.25 THEN '✓'
        ELSE '⚠'
    END
FROM step3_decision_output s3

UNION ALL

SELECT
    '性能指标',
    'Step1平均延迟',
    ROUND(AVG(s1.latency_ms), 0) || 'ms',
    '<2500ms',
    CASE WHEN AVG(s1.latency_ms) < 2500 THEN '✓' ELSE '⚠' END
FROM step1_intent_output s1

UNION ALL

SELECT
    '成本指标',
    '单条工单处理成本(Token费用)',
    '$' || ROUND(AVG(s1.output_tokens) / 1000.0 * 0.015 + 0.003, 4),
    '<$0.01',
    CASE WHEN AVG(s1.output_tokens) / 1000.0 * 0.015 + 0.003 < 0.01 THEN '✓' ELSE '⚠' END
FROM step1_intent_output s1;
```

**Expected result explanation:**
Returns a Dashboard view (based on this dataset's ~5,000 ticket scale):
```
Business volume | Total tickets (this week) | ~1,100  | -       | -
Business volume | VIP ticket share          | 19.2%   | 15-25%  | ✓
Quality         | Step1 accuracy (v5)       | 90.5%   | >85%    | ✓
Quality         | Step3 violation rate (v3) | 3.0%    | <5%     | ✓
Efficiency      | AI auto-handle rate       | 85.0%   | >75%    | ✓
Performance     | Step1 average latency     | 1847ms  | <2500ms | ✓
Cost            | Per-ticket cost           | $0.0057 | <$0.01  | ✓
```
The VP sees every metric on target (✓), the system is healthy, and can continue investing in optimization. Note: ~1,100 tickets this week is the estimate ~5,000 tickets × 7/30 days; actual value depends on the submission-time distribution.

---

## Query Usage Guide

### 1. Index by business role

| Role | Related query # |
|------|-----------------|
| Operations Manager | 1, 14 |
| ML Engineer | 2, 3, 10, 15, 19 |
| Quality Manager | 4, 13 |
| Annotation Manager | 5, 17 |
| Risk Analyst | 6 |
| Technical Operations | 7 |
| Customer Experience Manager | 8 |
| Operations Analyst | 9 |
| ML Researcher | 10 |
| Product Operations | 11 |
| Tech Lead | 12 |
| Quality Analyst | 13 |
| Customer Success Manager | 16 |
| Product Manager | 18 |
| Executive (VP/CTO) | 20 |

### 2. Index by difficulty

| Difficulty | Query # |
|------------|---------|
| Basic | 1, 5, 8 |
| Intermediate | 2, 3, 4, 6, 7, 9, 11, 12, 14, 17, 18 |
| Advanced | 10, 13, 15, 16, 19, 20 |

### 3. Index by query category

| Category | Query # |
|----------|---------|
| Aggregation | 1, 4, 5, 7, 8, 10, 18 |
| Join | 1, 2, 4, 6, 11, 13, 16, 17 |
| Subquery | 3 |
| Window Function | 8, 11, 17 |
| Date/Time Analysis | 9, 14 |
| Statistical Analysis | 10, 15 |
| Cross Tabulation | 8, 11 |
| CTE (Common Table Expression) | 13, 16, 19 |
| Multi-table Aggregation | 20 |

---

## Teaching Value

These 20 SQL queries cover the following teaching points:

1. **Business analysis mindset:** every query starts from a business question, not technical showmanship
2. **JOIN techniques:** multi-table joins, LEFT JOIN to handle NULL, self-referencing JOIN
3. **Aggregation functions:** COUNT / AVG / SUM combined with CASE WHEN for conditional aggregation
4. **Window functions:** OVER PARTITION BY for group shares and rankings
5. **Date calculation:** JULIANDAY diff for day count, STRFTIME formatting
6. **CTE usage:** WITH clauses for readability and intermediate-result reuse
7. **UNION composition:** combining multi-dimensional statistics
8. **String functions:** GROUP_CONCAT to assemble lists, LENGTH to compute length
9. **Conditional logic:** complex CASE WHEN branching, nested conditions
10. **Performance optimization:** using indexed fields (PK/FK), avoiding full scans

---

**Generated by:** Fake Data Generator Agent
**Query version:** v1.1
**Generated on:** 2024-12-01
