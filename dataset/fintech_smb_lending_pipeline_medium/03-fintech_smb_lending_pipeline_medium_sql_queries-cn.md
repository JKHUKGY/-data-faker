# 金融科技 — 中小企业贷款流水线 SQL 查询参考

## 概述

本文档为 `fintech_smb_lending_pipeline_medium` 数据集提供 **20 个面向业务的 SQL 查询**。每个查询都对应 Pacific Bridge Lending 利益相关者在分析贷款业务、风险管理与组合表现时,会真实提出的问题。业务背景、公司角色、行业科普与术语表请见 `01-fintech_smb_lending_pipeline_medium_business_context-cn.md`;表结构与字段含义请见 `02-fintech_smb_lending_pipeline_medium_er_document-cn.md`。

> **参考日约定。** 数据集锚定到固定的 `REFERENCE_DATE = 2026-06-03`。需要"今天"的查询使用字面量 `'2026-06-03'` 而非 `DATE('now')`,使结果与执行时间无关、可复现。若你把数据集重新锚定到其他参考日,请在下面所有查询里替换这个字面量。

## 如何使用本文档

本文档写给刚读完业务背景文档(`01-...business_context-cn.md`)和 ER 文档(`02-...er_document-cn.md`)、准备上手做分析的实习生 / 新人分析师。把它当成一份"项目交接":经理把这 20 道题交给你,你这一周要逐一做完,并理解为什么这么写。

每个查询都按统一的**五段式**组织:

1. **业务背景** —— 谁在问、为什么问、答案要支撑什么决策、为什么现在紧急。
2. **类别 / 难度 / 业务角色** —— 三个快速标签,帮你判断这道题练的是哪类 SQL、对应公司里哪个角色。
3. **解题思路** —— 在你看到 SQL 之前,先讲清楚要碰哪些表、怎么 join、聚合到什么粒度、为什么用(或不用)CTE / 窗口函数 / 子查询、有哪些 SQLite 专属坑要避开。这一段是学习重点。
4. **SQL 代码** —— 可直接在生成器产出的 SQLite 库上运行。
5. **期望结果说明** —— 结果集长什么样、关键数值对应哪个业务陷阱、以及拿到结果后下一步该做什么。

两个使用提示:

- **每个查询都映射回一个业务问题。** 文档末尾有"业务问题 → 查询"对照表;读 SQL 之前先想清楚它要回答 Q1–Q5 中的哪一个。
- **SQL 是用来读和学的,不只是用来跑的。** 解题思路解释了"为什么这样写";真正的功夫在看懂 join 的方向、聚合的粒度、口径的选择,而不是把数跑出来就完事。

---

## 查询索引

| # | 标题 | 业务角色 | 类别 | 难度 |
|---|------|----------|------|------|
| 1 | 风险等级定价对齐分析 | Executive | Aggregation + Join | Intermediate |
| 2 | 行业组合集中度看板 | Manager | Aggregation + Join | Intermediate |
| 3 | 审批漏失 — 假阴性分析 | Analyst | Subquery + Join | Advanced |
| 4 | 违约前的早期预警信号 | Analyst | CTE + Join | Advanced |
| 5 | 客户全生命周期价值对比 | Executive | Aggregation + Join | Intermediate |
| 6 | 月度申请量趋势 | Operations | Date Aggregation | Basic |
| 7 | 信贷员绩效记分卡 | Manager | Aggregation + Join | Intermediate |
| 8 | 还款行为队列分析 | Analyst | CTE + Aggregation | Advanced |
| 9 | 在贷高风险 Top 10 | Operations | Join + Subquery | Intermediate |
| 10 | 风险等级违约回收率 | Finance | Aggregation + Join | Intermediate |
| 11 | 区域申请量与转化率 | Finance | Aggregation + Join | Basic |
| 12 | 复购客户留存指标 | Manager | CTE + Join | Advanced |
| 13 | 组合 Vintage 分析 | Analyst | Date + Aggregation | Intermediate |
| 14 | 逾期还款趋势分析 | Operations | Date Aggregation | Intermediate |
| 15 | 贷款金额与信用分相关性 | Analyst | Aggregation | Basic |
| 16 | 风险等级再定价机会 | Manager | Subquery + Join | Advanced |
| 17 | 月度现金流预测 | Finance | Aggregation + Date | Intermediate |
| 18 | 申请处理时长分析 | Operations | Date Calculation | Basic |
| 19 | 行业特异性违约模式 | Executive | CTE + Aggregation | Advanced |
| 20 | 按 LTV 的客户分群 | Executive | CTE + Window Function | Advanced |

---

## 查询正文

### Query 1: 风险等级定价对齐分析

**业务背景:**
首席风险官需要验证贷款定价(利率)是否准确反映各风险等级的实际违约风险。在季度风险评审中,她发现某些等级可能定价不足 — 收取的利率不足以覆盖实际承担的风险。本分析将定价模型假设的违约率与实际观测违约率做对比。偏差意味着利润机会(收多了)或损失(收少了)。这是咨询项目 Q1 的基础,直接影响盈利目标。

**类别:** Aggregation + Join
**难度:** Intermediate
**业务角色:** Executive

**解题思路:**
这道题要把 implied 违约率(`risk_grade` 表里写死的定价假设)和实际违约率(从 `loan` 和 `default_event` 推出)对齐到等级粒度。先 `JOIN loan ON risk_grade.id = loan.risk_grade_id` 把每笔贷款挂到等级上,再 `LEFT JOIN default_event ON loan.id = de.loan_id` 给违约的贷款打标。关键:这一步必须是 LEFT JOIN —— 换成 INNER JOIN 会把没违约的贷款全部剔除,分母只剩违约贷款,实际违约率会被算成 100%。聚合粒度是"一个等级一行",实际违约率 = `COUNT(default_event.id) / COUNT(loan.id)`(COUNT 只数非 NULL,所以分子自动只数违约)。不需要 CTE 或窗口函数,一次 GROUP BY 即可完成。

```sql
-- Compare implied vs actual default rates by risk grade to identify pricing misalignment
SELECT
    rg.grade_code,
    rg.grade_name,
    rg.interest_rate,
    rg.implied_default_rate AS pricing_assumption_pct,
    COUNT(l.id) AS total_loans,
    COUNT(de.id) AS defaulted_loans,
    ROUND(100.0 * COUNT(de.id) / COUNT(l.id), 2) AS actual_default_rate_pct,
    ROUND(rg.implied_default_rate - (100.0 * COUNT(de.id) / COUNT(l.id)), 2) AS pricing_gap_pct
FROM risk_grade rg
JOIN loan l ON rg.id = l.risk_grade_id
LEFT JOIN default_event de ON l.id = de.loan_id
GROUP BY rg.id, rg.grade_code, rg.grade_name, rg.interest_rate, rg.implied_default_rate
ORDER BY pricing_gap_pct ASC;
```

**期望结果说明:**
每个风险等级返回一行,显示贷款总数、违约数、实际 vs implied 违约率、定价缺口。本数据集中 `pricing_gap_pct = implied − actual`,所以负缺口表示该等级 *定价不足*(实际违约超过模型假设)。期望产出:Grade C 显示明显的负缺口(~−4pp;实际 ~10% 对比 implied 6.0%) — 这就是分析存在的目的:暴露主要的定价错配。Grade A 和 B 定价在 implied ±1pp 内;Grade D 定价不足约 2pp;Grade E 在 ±1pp 内。结合 Grade C 占组合 ~28% 的体量,这量化了 CRO 需要通过重新定价或收紧 C 层承保来解决的定价不足敞口。

---

### Query 2: 行业组合集中度看板

**业务背景:**
组合经理正在为季度董事会准备汇报材料,需报告组合多样化与集中度风险。董事会尤其担心餐饮、酒店等周期性行业的敞口,经历疫情之后更甚。若某单一行业出现系统性冲击,集中暴露可能引发连锁违约。本查询识别哪些行业主导未偿贷款组合,并计算用于指导"对集中行业新申请的胃口"的集中度风险指标。

**类别:** Aggregation + Join
**难度:** Intermediate
**业务角色:** Manager

**解题思路:**
要从行业维度看组合集中度,需要把四张表串起来:`industry → customer → application → loan → default_event`。从 application 往 loan 用 LEFT JOIN,因为被拒申请没有对应 loan,但我们仍要把它计入"申请量"分母。占比用标量子查询 `(SELECT COUNT(*) FROM application)` 和 `(SELECT SUM(outstanding_balance) FROM loan)` 做全局分母 —— 注意子查询分母是"全表",和外层按行业分组的分子不在同一粒度,这正是算占比想要的效果。`COUNT(DISTINCT a.id)` / `COUNT(DISTINCT l.id)` 用 DISTINCT,是因为一笔 loan 配多条 default 行时多表 join 会 fan-out 放大行数,DISTINCT 防止重复计数。按未偿余额降序排,集中度最高的行业排在最前。

```sql
-- Calculate portfolio concentration by industry with exposure and default metrics
SELECT
    i.industry_name,
    COUNT(DISTINCT a.id) AS total_applications,
    ROUND(100.0 * COUNT(DISTINCT a.id) / (SELECT COUNT(*) FROM application), 2) AS pct_of_applications,
    COUNT(DISTINCT l.id) AS total_loans,
    ROUND(SUM(l.outstanding_balance), 2) AS total_outstanding,
    ROUND(100.0 * SUM(l.outstanding_balance) / (SELECT SUM(outstanding_balance) FROM loan), 2) AS pct_of_portfolio,
    COUNT(de.id) AS defaults,
    ROUND(100.0 * COUNT(de.id) / COUNT(DISTINCT l.id), 2) AS industry_default_rate_pct,
    i.default_rate_baseline AS historical_baseline_pct
FROM industry i
JOIN customer c ON i.id = c.industry_id
JOIN application a ON c.id = a.customer_id
LEFT JOIN loan l ON a.id = l.application_id
LEFT JOIN default_event de ON l.id = de.loan_id
GROUP BY i.id, i.industry_name, i.default_rate_baseline
ORDER BY total_outstanding DESC;
```

**期望结果说明:**
返回按行业的指标:申请量、贷款数、未偿余额、违约率。本数据集中 Restaurant 占申请 ~18%、占未偿余额 ~18%;叠加 Hospitality (~9%) 后周期性的"餐饮+酒店"集群占组合 ~27% — 单一冲击下的集中度,正是董事会担心的。查询同时把实际违约率与各行业的历史基线(Restaurant 9.5%、Hospitality 12.4%、Construction 11.3% 等)对比,以暴露表现差于预期的行业。支撑 Q2(组合集中度),并为行业级贷款上限或定价调整提供依据。

---

### Query 3: 审批漏失 — 假阴性分析

**业务背景:**
信贷副总裁担心因拒绝有信用价值的申请人(假阴性)而损失的收入。在一次被拒申请的回顾中,团队发现部分被拒申请的信用画像与表现良好的已批客户相近甚至更优。每一次错误拒绝都意味着丢失的利息收入,放在年度尺度上可能是数十万美元。本分析通过信用分、收入、员工数阈值识别"看起来像优质客户"的被拒申请,量化"过度保守承保"的机会成本。

**类别:** Subquery + Join
**难度:** Advanced
**业务角色:** Analyst

**解题思路:**
思路是"先算出成功借款人的平均画像,再去被拒池里找长得像他们的人"。第一步用 CTE `successful_profile` 把 CURRENT / PAID_OFF 贷款对应客户的平均信用分、收入、员工数算成一行。第二步把 application 与 customer join,再 `CROSS JOIN successful_profile`(它只有一行,CROSS JOIN 等于把这行平均值广播到每条申请上),然后筛 `status_code='REJECTED'` 且三项指标都达到阈值(信用分 ≥ 均值−30、收入 ≥ 均值×0.7、员工 ≥ 均值×0.6),这些就是"假阴性"候选。`LIMIT 50` 只为承保委员会人工评审而截断;要估算总漏失体量,去掉 LIMIT 数行数即可。CTE 在这里值钱,因为那一行平均画像要被每条申请引用,写成 CTE 比重复子查询清楚。

```sql
-- Identify rejected applications with customer profiles matching successful borrowers
WITH successful_profile AS (
    SELECT
        AVG(c.credit_score) AS avg_credit_score,
        AVG(c.annual_revenue) AS avg_revenue,
        AVG(c.employee_count) AS avg_employees
    FROM loan l
    JOIN customer c ON l.customer_id = c.id
    JOIN loan_status ls ON l.current_status_id = ls.id
    WHERE ls.status_code IN ('CURRENT', 'PAID_OFF')
)
SELECT
    a.application_number,
    c.business_name,
    c.credit_score,
    c.annual_revenue,
    c.employee_count,
    a.requested_amount,
    a.rejection_reason,
    ROUND(c.credit_score - sp.avg_credit_score, 0) AS credit_score_vs_avg,
    ROUND(c.annual_revenue - sp.avg_revenue, 0) AS revenue_vs_avg
FROM application a
JOIN customer c ON a.customer_id = c.id
JOIN loan_status ls ON a.status_id = ls.id
CROSS JOIN successful_profile sp
WHERE ls.status_code = 'REJECTED'
  AND c.credit_score >= sp.avg_credit_score - 30
  AND c.annual_revenue >= sp.avg_revenue * 0.7
  AND c.employee_count >= sp.avg_employees * 0.6
ORDER BY c.credit_score DESC
LIMIT 50;
```

**期望结果说明:**
最多返回 50 条被拒申请,这些申请的客户画像(信用分、收入、员工数)接近或优于成功借款人。每一行都代表一次潜在的假阴性。在全部被拒池中(~780 申请),约 15-20% 同时满足这三个阈值 — 就是假阴性候选池 — 但 `LIMIT 50` 仅按信用分排序返回前 50 供人工评审。**要估算总漏失体量与收入影响,移除 LIMIT 并统计行数即可;** 此处的 LIMIT 只是为了让承保委员会能扫读结果集。这支撑 Q3(审批漏失),并为人工评审与模型重新校准提供具体申请。

---

### Query 4: 违约前的早期预警信号

**业务背景:**
催收经理希望落地一套主动外联计划,在违约发生前介入。历史上公司只在贷款 90+ DPD 之后才开始动作,届时回收已经困难。本分析检视违约前数月的还款行为,识别"逾期增加、部分付款"等早期预警模式。如果团队能提前 3+ 月发现恶化,就可以提供重组方案介入,降低损失、保住客户关系。

**类别:** CTE + Join
**难度:** Advanced
**业务角色:** Analyst

**解题思路:**
要看违约前 90 天的还款恶化,需要把 `default_event`(拿到 default_date)、`payment`(实际还款行为)、`repayment_schedule`(应还金额,用来算应付实付比)三张表 join 起来。用 CTE `default_loan_payments` 先把"违约前 0–90 天内的每一笔还款"摊平,并算出 `pct_of_scheduled`(实付/应付)和 `days_before_default`。注意应付额取 `rs.scheduled_payment`(每期计划额)而非 `loan.monthly_payment`,这样最后一期的取整差异不会污染百分比。外层按 loan 聚合平均逾期、最大逾期、问题付款计数,`HAVING payments_in_90_days_prior >= 2` 过滤掉证据太少的贷款。这里用 CTE,是为了把"时间窗口过滤 + 派生列"和"聚合"分成两步,逻辑更清楚。

```sql
-- Analyze payment behavior patterns in the 3 months before defaults.
-- Uses rs.scheduled_payment (per-installment) rather than l.monthly_payment so
-- the % calculation is robust to last-installment rounding differences.
WITH default_loan_payments AS (
    SELECT
        de.loan_id,
        de.default_date,
        p.payment_date,
        p.installment_number,
        p.days_late,
        p.payment_amount,
        rs.scheduled_payment,
        ROUND(100.0 * p.payment_amount / rs.scheduled_payment, 2) AS pct_of_scheduled,
        JULIANDAY(de.default_date) - JULIANDAY(p.payment_date) AS days_before_default
    FROM default_event de
    JOIN payment p ON de.loan_id = p.loan_id
    JOIN repayment_schedule rs ON p.loan_id = rs.loan_id AND p.installment_number = rs.installment_number
    WHERE JULIANDAY(de.default_date) - JULIANDAY(p.payment_date) BETWEEN 0 AND 90
)
SELECT
    loan_id,
    default_date,
    COUNT(*) AS payments_in_90_days_prior,
    AVG(days_late) AS avg_days_late,
    MAX(days_late) AS max_days_late,
    AVG(pct_of_scheduled) AS avg_pct_paid,
    COUNT(CASE WHEN days_late > 10 THEN 1 END) AS late_payment_count,
    COUNT(CASE WHEN pct_of_scheduled < 95 THEN 1 END) AS partial_payment_count
FROM default_loan_payments
GROUP BY loan_id, default_date
HAVING payments_in_90_days_prior >= 2
ORDER BY max_days_late DESC, avg_pct_paid ASC
LIMIT 20;
```

**期望结果说明:**
返回违约贷款在违约前 90 天的聚合还款指标:平均逾期、最大逾期、应付实付比、问题付款计数。本数据集中,违约贷款在最后 3 期的均值为 ~12.5 天逾期、应付实付比 ~90%,对比全体的 ~4 天、~98.5% — 恶化清晰可见。约 ~70% 的违约展示出明确预警信号(`default_event.had_early_warning` 标记追踪同一群体)。`avg_days_late > 10` 或 `avg_pct_paid < 90%` 的贷款是早期介入的强候选。支撑 Q4(早期预警信号),并为构建预测性监控看板提供依据。

---

### Query 5: 客户全生命周期价值对比

**业务背景:**
CEO 正在评审客户获取策略与预算分配。市场团队希望大力投资数字广告获取新客户,但 CFO 主张精耕老客户的复购更可能盈利。本分析对比复购客户(签过多笔贷款的)与新客户的关键指标:违约率、平均贷款金额、审批率。理解全生命周期价值差异有助于高管团队决定 200 万美元年度营销预算的分配。

**类别:** Aggregation + Join
**难度:** Intermediate
**业务角色:** Executive

**解题思路:**
难点在于"客户级指标"和"贷款级指标"的聚合粒度不同,不能混在一个 GROUP BY 里。一个多笔贷款的客户,信用分只该算一次,否则会被贷款数加权重复计入平均。所以用两个 CTE:`customer_agg` 按 `is_repeat_customer` 聚合客户数和平均信用分(粒度=客户);`loan_agg` 按同一维度聚合申请数、贷款数、违约数、金额(粒度=贷款,用 LEFT JOIN 把没贷款的客户也保留)。最后两个 CTE 按 `is_repeat_customer` join 成两行(复购 vs 新客户)做对比。把两种粒度分开算再 join,是避免重复计数的标准手法。

```sql
-- Compare performance metrics between repeat and first-time customers.
-- Customer-level metrics (count, credit score) are computed in a CTE keyed by
-- customer so a multi-loan customer's credit score isn't double-counted in
-- the average. Loan/default metrics come from a separate aggregate.
WITH customer_agg AS (
    SELECT
        is_repeat_customer,
        COUNT(*) AS total_customers,
        ROUND(AVG(credit_score), 0) AS avg_credit_score
    FROM customer
    GROUP BY is_repeat_customer
),
loan_agg AS (
    SELECT
        c.is_repeat_customer,
        COUNT(DISTINCT a.id) AS total_applications,
        COUNT(DISTINCT l.id) AS total_loans,
        COUNT(de.id) AS defaults,
        ROUND(AVG(l.approved_amount), 2) AS avg_loan_amount,
        ROUND(SUM(l.outstanding_balance), 2) AS total_outstanding
    FROM customer c
    LEFT JOIN application a ON c.id = a.customer_id
    LEFT JOIN loan l ON a.id = l.application_id
    LEFT JOIN default_event de ON l.id = de.loan_id
    GROUP BY c.is_repeat_customer
)
SELECT
    ca.is_repeat_customer,
    CASE WHEN ca.is_repeat_customer = 1 THEN 'Repeat Customer' ELSE 'First-Time Customer' END AS customer_type,
    ca.total_customers,
    la.total_applications,
    la.total_loans,
    ROUND(100.0 * la.total_loans / la.total_applications, 2) AS approval_rate_pct,
    la.avg_loan_amount,
    la.total_outstanding,
    la.defaults,
    ROUND(100.0 * la.defaults / la.total_loans, 2) AS default_rate_pct,
    ca.avg_credit_score
FROM customer_agg ca
JOIN loan_agg la USING (is_repeat_customer)
ORDER BY ca.is_repeat_customer DESC;
```

**期望结果说明:**
返回两行,对比复购 vs 新客户在所有关键指标上的表现。本数据集中复购客户违约率 ~5%,新客户 ~11%(约 2 倍差距),信用分明显更高(~50–80 分),平均贷款金额也较大。复购客户只占客户基数的 ~12%,却推动了不成比例的低风险业务量。支撑 Q5(客户全生命周期价值),为将营销预算从获取倾向"留存"提供依据。

---

### Query 6: 月度申请量趋势

**业务背景:**
运营总监需要为承保团队规划人手。申请量有季节性波动,峰月人手不足会导致决策慢(损害客户体验),淡月人手过剩则浪费薪资预算。本查询分析过去 2 年的月度申请量与审批率,识别规律。这些洞察帮助总监在淡季安排休假、在峰季加临时合同人手,并制定切合实际的申请处理 SLA 目标。

**类别:** Date Aggregation
**难度:** Basic
**业务角色:** Operations

**解题思路:**
最简单的一类:时间序列聚合。只需 `application` join `loan_status`(拿到状态名),按 `strftime('%Y-%m', application_date)` 把申请按月分桶。批准 / 拒绝数用条件聚合 `COUNT(CASE WHEN ... THEN 1 END)`(CASE 不满足时返回 NULL,COUNT 不计入,等于条件计数)。`strftime` 是 SQLite 专属的日期格式化函数。一次 GROUP BY 即可,不需要 join 事实表 loan。

```sql
-- Track monthly application volume and approval rates over time
SELECT
    strftime('%Y-%m', a.application_date) AS month,
    COUNT(*) AS total_applications,
    COUNT(CASE WHEN ls.status_code = 'APPROVED' THEN 1 END) AS approved,
    COUNT(CASE WHEN ls.status_code = 'REJECTED' THEN 1 END) AS rejected,
    ROUND(100.0 * COUNT(CASE WHEN ls.status_code = 'APPROVED' THEN 1 END) / COUNT(*), 2) AS approval_rate_pct,
    ROUND(SUM(a.requested_amount), 2) AS total_requested_amount
FROM application a
JOIN loan_status ls ON a.status_id = ls.id
WHERE a.application_date IS NOT NULL
GROUP BY strftime('%Y-%m', a.application_date)
ORDER BY month ASC;
```

**期望结果说明:**
返回按月时间序列:申请数、批准/拒绝数、批准率、总申请金额。可揭示季节模式(如 Q1 淡、Q4 旺)以及任何提示政策变化或经济周期的突变。运营团队用它做 3–6 个月的人力预测,并以历史基准衡量当前表现。

---

### Query 7: 信贷员绩效记分卡

**业务背景:**
承保负责人每季度对所有信贷员做绩效评审。她需要客观指标来评价每位信贷员的组合质量、生产力、风险管理。表现好的信贷员应得奖励并被分派更复杂的申请,表现差的可能需要额外培训。本记分卡按信贷员维度跟踪申请处理量、审批率、平均贷款金额、违约率。审批率高但违约也高,说明放贷可能过松;审批率极低,说明承保可能过严。

**类别:** Aggregation + Join
**难度:** Intermediate
**业务角色:** Manager

**解题思路:**
按信贷员维度做绩效记分卡。从 `loan_officer` join `application`(信贷员受理的全部申请),再 LEFT JOIN loan / default_event —— 用 LEFT 是因为大部分申请没有对应 loan(被拒)或没有 default(没违约),但我们要保留这些分母。审批率 = `COUNT(loan.id) / COUNT(application.id)`;违约率分母用 `NULLIF(COUNT(loan.id), 0)` 防止除零。`HAVING applications_processed >= 10` 滤掉样本太小、指标不稳的信贷员。聚合粒度是"一个信贷员一行"。

```sql
-- Generate performance scorecard for each loan officer
SELECT
    lo.employee_id,
    lo.first_name || ' ' || lo.last_name AS officer_name,
    lo.region,
    COUNT(a.id) AS applications_processed,
    COUNT(l.id) AS loans_approved,
    ROUND(100.0 * COUNT(l.id) / COUNT(a.id), 2) AS approval_rate_pct,
    ROUND(AVG(l.approved_amount), 2) AS avg_loan_size,
    ROUND(SUM(l.outstanding_balance), 2) AS total_portfolio_balance,
    COUNT(de.id) AS defaults,
    ROUND(100.0 * COUNT(de.id) / NULLIF(COUNT(l.id), 0), 2) AS default_rate_pct
FROM loan_officer lo
JOIN application a ON lo.id = a.loan_officer_id
LEFT JOIN loan l ON a.id = l.application_id
LEFT JOIN default_event de ON l.id = de.loan_id
GROUP BY lo.id, lo.employee_id, lo.first_name, lo.last_name, lo.region
HAVING applications_processed >= 10
ORDER BY applications_processed DESC;
```

**期望结果说明:**
每位信贷员一行,显示生产力(申请处理量)、风险偏好(审批率)、组合规模、信用质量(违约率)。经理寻找平衡画像:审批率 70–75% + 违约率 <10% 的信贷员表现良好。任一方向的离群者都值得讨论。这些数据驱动薪酬决策、区域分配、培训优先级。

---

### Query 8: 还款行为队列分析

**业务背景:**
分析团队正构建预测模型识别违约风险贷款。一个假设是:前 6 个月的还款行为模式(准时/逾期/部分)对长期结果有强预测力。本队列分析按早期还款行为对贷款分组,并跟踪每组的违约率。若数据表明前 6 期就出现一次逾期的贷款违约率高出 3 倍,团队就可以立即触发主动介入,而不必等到多次漏付。

**类别:** CTE + Aggregation
**难度:** Advanced
**业务角色:** Analyst

**解题思路:**
要验证"前 6 期还款行为预测违约"的假设,分三步。CTE1 `early_payment_behavior` 只看 `installment_number <= 6` 的还款,按贷款统计准时数、逾期数、部分付款数,`HAVING COUNT(*) >= 3` 保证至少有 3 期可判断。CTE2 `cohort_classification` 用 CASE 把每笔贷款分到 Perfect / Mostly On-Time / Problematic 三个队列。最后把队列标签 join 回 loan 和 default_event,按队列算违约率。分两个 CTE,是因为"先算行为指标 → 再据此分类 → 最后聚合违约率"是三个不同粒度的步骤,链式 CTE 让每步独立、可读。

```sql
-- Analyze default rates by early payment behavior cohorts
WITH early_payment_behavior AS (
    SELECT
        p.loan_id,
        COUNT(*) AS payments_made,
        SUM(CASE WHEN p.days_late = 0 THEN 1 ELSE 0 END) AS on_time_count,
        SUM(CASE WHEN p.days_late > 0 THEN 1 ELSE 0 END) AS late_count,
        AVG(CASE WHEN p.days_late > 0 THEN p.days_late END) AS avg_late_days,
        SUM(CASE WHEN p.payment_amount < l.monthly_payment * 0.95 THEN 1 ELSE 0 END) AS partial_count
    FROM payment p
    JOIN loan l ON p.loan_id = l.id
    WHERE p.installment_number <= 6
    GROUP BY p.loan_id
    HAVING COUNT(*) >= 3
),
cohort_classification AS (
    SELECT
        loan_id,
        CASE
            WHEN late_count = 0 AND partial_count = 0 THEN 'Perfect'
            WHEN late_count <= 1 AND partial_count = 0 THEN 'Mostly On-Time'
            ELSE 'Problematic'
        END AS cohort
    FROM early_payment_behavior
)
SELECT
    cc.cohort,
    COUNT(DISTINCT l.id) AS total_loans,
    COUNT(de.id) AS defaults,
    ROUND(100.0 * COUNT(de.id) / COUNT(DISTINCT l.id), 2) AS default_rate_pct,
    ROUND(AVG(l.approved_amount), 2) AS avg_loan_amount
FROM cohort_classification cc
JOIN loan l ON cc.loan_id = l.id
LEFT JOIN default_event de ON l.id = de.loan_id
GROUP BY cc.cohort
ORDER BY default_rate_pct DESC;
```

**期望结果说明:**
返回三个还款行为队列的违约率:Perfect(全部准时)、Mostly On-Time(最多 1 次逾期)、Problematic(2+ 次逾期或部分付款)。预期 Problematic 贷款违约率 15-25%,远高于 Perfect 的 2-4%。这验证了"早期预警"假设,并为监控系统的自动告警提供阈值。

---

### Query 9: 在贷高风险 Top 10

**业务背景:**
首席信贷官在每周风险委员会上需要评审当前组合中的最高风险敞口 — 通常是已显逾期信号的大额贷款,或高风险等级且未偿余额较大的贷款。委员会讨论是否提高准备金、外联借款人、或考虑卖出贷款以降低集中度。本查询识别按"风险加权敞口(余额 × 风险分)"排序的 Top 10 需立即关注的贷款。

**类别:** Join + Subquery
**难度:** Intermediate
**业务角色:** Operations

**解题思路:**
找在贷组合里风险最高的 10 笔。主查询把 loan 与 customer、industry、risk_grade、loan_status join 起来拿到展示字段,筛 `status_code='CURRENT'` 且余额 > 5 万。风险加权敞口用 `outstanding_balance × implied_default_rate` 近似预期损失。最近还款行为用一个**相关子查询**:内层再嵌一个子查询取该贷款的 `MAX(installment_number) - 2`,从而只平均最后 3 期的 `days_late`。相关子查询每行执行一次,这里因为有 `LIMIT 10` 且已按余额筛过,代价可接受。按预期损失降序取前 10。

```sql
-- Identify the highest risk outstanding loans requiring immediate attention
SELECT
    l.loan_number,
    c.business_name,
    i.industry_name,
    rg.grade_code AS risk_grade,
    l.outstanding_balance,
    l.disbursement_date,
    ROUND((JULIANDAY('2026-06-03') - JULIANDAY(l.disbursement_date)) / 30, 0) AS months_since_disbursement,
    (SELECT AVG(p2.days_late)
     FROM payment p2
     WHERE p2.loan_id = l.id AND p2.installment_number >=
           (SELECT MAX(p3.installment_number) - 2 FROM payment p3 WHERE p3.loan_id = l.id)
    ) AS avg_days_late_last_3,
    ls.status_name,
    ROUND(l.outstanding_balance * rg.implied_default_rate / 100, 2) AS expected_loss_amount
FROM loan l
JOIN customer c ON l.customer_id = c.id
JOIN industry i ON c.industry_id = i.id
JOIN risk_grade rg ON l.risk_grade_id = rg.id
JOIN loan_status ls ON l.current_status_id = ls.id
WHERE ls.status_code = 'CURRENT'
  AND l.outstanding_balance > 50000
ORDER BY expected_loss_amount DESC, avg_days_late_last_3 DESC
LIMIT 10;
```

**期望结果说明:**
返回预期损失敞口最大的 10 笔贷款,公式为 outstanding_balance × implied_default_rate。包含最近还款行为(最后 3 期的平均逾期),用以标记已显示预警信号的贷款。每笔列出的贷款都代表一个可能需要拨备、信用监控、或主动外联的集中风险。委员会用它来优先排序催收努力,并为投资者更新风险报告。

---

### Query 10: 风险等级违约回收率

**业务背景:**
CFO 正在准备财务报表,需要估算当前贷款组合的损失拨备。损失拨备同时取决于违约概率(随风险等级变化)和损失严重度(违约后能回收多少)。本查询按风险等级计算回收率,显示已违约余额中通过催收、资产处置、法律程序最终回收的比例。回收率低意味着所需拨备高,影响公司的资本要求和盈利能力。

**类别:** Aggregation + Join
**难度:** Intermediate
**业务角色:** Finance

**解题思路:**
只看违约贷款,所以从 `default_event` 出发(它天然只含违约记录),INNER JOIN loan 和 risk_grade 拿到等级。按等级聚合:回收率 = `SUM(recovery_amount) / SUM(outstanding_at_default)`,损失严重度 = `SUM(loss_amount) / SUM(outstanding_at_default)`,两者互补(和为 1)。注意是按金额加权(SUM/SUM)而不是先算每笔比率再平均,这样大额违约对组合回收率的影响更真实。粒度是"一个等级一行",按 `rg.id` 排序让 A→E 顺序输出。

```sql
-- Calculate recovery rates on defaulted loans by risk grade
SELECT
    rg.grade_code,
    rg.grade_name,
    COUNT(de.id) AS total_defaults,
    ROUND(SUM(de.outstanding_at_default), 2) AS total_exposure_at_default,
    ROUND(SUM(de.recovery_amount), 2) AS total_recovered,
    ROUND(SUM(de.loss_amount), 2) AS total_net_loss,
    ROUND(100.0 * SUM(de.recovery_amount) / SUM(de.outstanding_at_default), 2) AS recovery_rate_pct,
    ROUND(100.0 * SUM(de.loss_amount) / SUM(de.outstanding_at_default), 2) AS loss_severity_pct,
    ROUND(AVG(de.recovery_amount), 2) AS avg_recovery_per_default,
    ROUND(AVG(de.loss_amount), 2) AS avg_loss_per_default
FROM default_event de
JOIN loan l ON de.loan_id = l.id
JOIN risk_grade rg ON l.risk_grade_id = rg.id
GROUP BY rg.id, rg.grade_code, rg.grade_name
ORDER BY rg.id;
```

**期望结果说明:**
按风险等级返回违约数、违约时敞口、回收金额、净损失、回收率、损失严重度。本数据集中回收率呈清晰单调梯度:Grade A 回收 ~54%(良好抵押、配合度高的借款人)、B ~48%、C ~38%、D ~32%、E ~23%(资产有限、对抗性强)。损失严重度反向梯度(A ~46% → E ~77%)。CFO 用 `default_rate × loss_severity` 按等级计算预期损失拨备;D/E 上严重度的陡升解释了为何这些层级既需要更高定价,又需要更紧的损失准备金。

---

### Query 11: 区域申请量与转化率

**业务背景:**
市场总监正在分析贷款流水线的体量来源。Pacific Bridge 给每位信贷员分配一个加州区域(Northern CA、Southern CA、Bay Area、Central Valley);本查询用信贷员所在区域代理"客户区域",因为 `loan_officer.region` 是干净的枚举,而 `customer.city` 是自由文本难以汇总。输出按区域量化申请量、转化(批准)率、违约率 — 这些是与外部跟踪的营销支出结合来计算客户获取成本(CAC)所需的输入。本查询本身不计算 CAC,因为本数据集没有按区域的营销支出。

**类别:** Aggregation + Join
**难度:** Basic
**业务角色:** Finance

**解题思路:**
用信贷员所在区域代理"客户区域",因为 `loan_officer.region` 是干净枚举,而 `customer.city` 是自由文本难以汇总。从 loan_officer join application,再 LEFT JOIN loan / default_event 保留被拒和未违约的分母。转化率 = `COUNT(DISTINCT loan) / COUNT(DISTINCT application)`,DISTINCT 防止 fan-out 重复。按区域聚合,按总放款量降序。要点:本查询只产出 CAC 的**分母**(申请量),不算 CAC 本身 —— 数据集没有按区域的营销支出。

```sql
-- Analyze application and loan volume by loan officer region (proxy for customer region)
SELECT
    lo.region,
    COUNT(DISTINCT a.id) AS total_applications,
    COUNT(DISTINCT l.id) AS approved_loans,
    ROUND(100.0 * COUNT(DISTINCT l.id) / COUNT(DISTINCT a.id), 2) AS conversion_rate_pct,
    ROUND(AVG(l.approved_amount), 2) AS avg_loan_size,
    ROUND(SUM(l.approved_amount), 2) AS total_loan_volume,
    COUNT(de.id) AS defaults,
    ROUND(100.0 * COUNT(de.id) / NULLIF(COUNT(DISTINCT l.id), 0), 2) AS default_rate_pct
FROM loan_officer lo
JOIN application a ON lo.id = a.loan_officer_id
LEFT JOIN loan l ON a.id = l.application_id
LEFT JOIN default_event de ON l.id = de.loan_id
GROUP BY lo.region
ORDER BY total_loan_volume DESC;
```

**期望结果说明:**
按区域返回:申请量、转化率(批准 %)、平均贷款金额、总贷款量、违约率。高量低转化的区域可能是线索质量松散或承保过严;高违约的区域可能需要风险调整定价。市场团队用 `total_applications` 作为分母,除以来自外部系统的按区域营销支出,得到真正的客户获取成本;本查询提供分母。

---

### Query 12: 复购客户留存指标

**业务背景:**
客户成功团队希望落地针对"贷款即将到期客户"的留存项目。如果公司能把 30% 的到期贷款转化为续贷或新贷,复购客户基数就能显著增长 — 而复购客户违约率 ~5%,新客户 ~11%,全生命周期经济性差异显著。本查询识别过去 12 个月里有贷款已结清、但近 6 个月没有新申请的客户,即留存机会池。

> **队列定义说明:** 本查询将"留存机会"*操作性地*定义为 `最近 PAID_OFF 到期日在 12 个月内 AND 近 6 个月无申请`。这与 Q5 / Q20 使用的 `customer.is_repeat_customer` 层级标识(营销侧入职时设置)不同。两个群体有重叠但不完全相同。

**类别:** CTE + Join
**难度:** Advanced
**业务角色:** Manager

**解题思路:**
找"结过贷但没回头"的留存机会客户。CTE1 `completed_loans` 取每个有 PAID_OFF 贷款的客户及其最近到期日。CTE2 `recent_applications` 取近 6 个月有申请的客户(用 `DATE('2026-06-03', '-6 months')` 锚定参考日)。主查询把两者 LEFT JOIN,用 `CASE WHEN ra.customer_id IS NOT NULL THEN 'Re-engaged' ELSE 'Dormant'` 标记是否已回流,并筛最近到期日在 12 个月内。LEFT JOIN + IS NULL 判断,是"找在 A 不在 B"的标准写法。注意:这里的"留存机会"是操作性定义(近 12 个月 PAID_OFF 且近 6 个月无申请),与 `is_repeat_customer` 标记不同,两个群体有重叠但不相同。

```sql
-- Identify customers who completed a loan but haven't returned for repeat business.
-- Dates are anchored to REFERENCE_DATE '2026-06-03' for deterministic results.
WITH completed_loans AS (
    SELECT
        c.id AS customer_id,
        c.business_name,
        c.industry_id,
        MAX(l.maturity_date) AS last_maturity_date,
        COUNT(l.id) AS total_loans_taken
    FROM customer c
    JOIN loan l ON c.id = l.customer_id
    JOIN loan_status ls ON l.current_status_id = ls.id
    WHERE ls.status_code = 'PAID_OFF'
    GROUP BY c.id, c.business_name, c.industry_id
),
recent_applications AS (
    SELECT DISTINCT customer_id
    FROM application
    WHERE application_date >= DATE('2026-06-03', '-6 months')
)
SELECT
    cl.customer_id,
    cl.business_name,
    i.industry_name,
    cl.last_maturity_date,
    ROUND((JULIANDAY('2026-06-03') - JULIANDAY(cl.last_maturity_date)) / 30, 0) AS months_since_completion,
    cl.total_loans_taken,
    CASE WHEN ra.customer_id IS NOT NULL THEN 'Re-engaged' ELSE 'Dormant' END AS status
FROM completed_loans cl
JOIN industry i ON cl.industry_id = i.id
LEFT JOIN recent_applications ra ON cl.customer_id = ra.customer_id
WHERE cl.last_maturity_date >= DATE('2026-06-03', '-12 months')
ORDER BY cl.last_maturity_date ASC;
```

**期望结果说明:**
返回过去 12 个月内成功结清贷款的客户,并标记他们是否近期又申请过。"Dormant"(沉睡)客户就是留存机会池 — 他们已证明是好借款人(贷款已结清),但没有被持续触达。客户成功团队向沉睡客户发送个性化优惠(更高额度、更优利率)以驱动复购。把 100 个沉睡客户转化即可带来 $15-20M 的新增贷款量。

---

### Query 13: 组合 Vintage 分析

**业务背景:**
投资委员会按发放队列(vintage)评审贷款表现,理解信用质量与定价随时间的演化。不同时期发放的贷款受经济条件、承保政策变化、风险偏好转移的影响,表现各异。本 vintage 分析按发放季度聚合贷款并跟踪违约率,显示近期承保是更紧还是更松。Vintage 表现的恶化是系统性信用质量问题的早期预警。

**类别:** Date + Aggregation
**难度:** Intermediate
**业务角色:** Analyst

**解题思路:**
按放款季度(vintage)看队列表现。SQLite 的 `strftime` 没有 `%Q`(季度)格式符,所以季度要从月份手算:`(CAST(strftime('%m', date) AS INTEGER) - 1) / 3 + 1`,再和年份拼成 `2024-Q1` 这样的标签。从 loan join loan_status,LEFT JOIN default_event 保留未违约贷款。按拼出来的 `origination_quarter` 分组算违约率、结清率。要点:近期季度成熟度不足、还款时间不够,违约率天然偏低,所以看**趋势**(同成熟度下逐季对比)比看绝对值更重要。

```sql
-- Analyze loan performance by origination vintage (quarter).
-- SQLite has no %Q strftime format specifier — quarter number is computed
-- explicitly from the month: ((month - 1) / 3) + 1.
SELECT
    strftime('%Y', l.disbursement_date) || '-Q' ||
        ((CAST(strftime('%m', l.disbursement_date) AS INTEGER) - 1) / 3 + 1) AS origination_quarter,
    COUNT(l.id) AS loans_originated,
    ROUND(SUM(l.approved_amount), 2) AS total_volume,
    ROUND(AVG(l.approved_amount), 2) AS avg_loan_size,
    ROUND(AVG(l.interest_rate), 2) AS avg_interest_rate,
    COUNT(de.id) AS defaults,
    ROUND(100.0 * COUNT(de.id) / COUNT(l.id), 2) AS default_rate_pct,
    ROUND(SUM(CASE WHEN ls.status_code = 'PAID_OFF' THEN 1 ELSE 0 END) * 100.0 / COUNT(l.id), 2) AS payoff_rate_pct
FROM loan l
JOIN loan_status ls ON l.current_status_id = ls.id
LEFT JOIN default_event de ON l.id = de.loan_id
GROUP BY origination_quarter
ORDER BY origination_quarter DESC;
```

**期望结果说明:**
返回按季度的队列:发放量、平均贷款特征、违约率、结清率。近期季度成熟度有限(还款时间不够),违约率看起来偏低 — 但趋势比绝对水平更重要。若 2024-Q1 在同样成熟度下显示 12% 违约,而 2023-Q1 是 8%,这意味着信用质量在恶化。委员会用它评估当前承保标准是否足够,或需要收紧。

---

### Query 14: 逾期还款趋势分析

**业务背景:**
催收经理逐月跟踪逾期还款率,在违约出现之前发现组合的早期压力。逾期(哪怕只是 5-15 天)的上升通常领先违约 6-12 个月,给团队介入窗口。本趋势分析显示每月的逾期占比、平均逾期天数,以及局面在改善或恶化。逾期率上升可能意味着经济逆风影响借款人,需要收紧承保或增加催收人力。

**类别:** Date Aggregation
**难度:** Intermediate
**业务角色:** Operations

**解题思路:**
按月跟踪逾期率。payment join repayment_schedule(用 `loan_id + installment_number` **双键** join,拿到该期应还额以判断部分付款)。按 `strftime('%Y-%m', payment_date)` 分月,逾期分桶用条件聚合(0 天 / 1–15 天 / 16–30 天)。部分付款率 = 实付 < 应付×0.95 的占比。`WHERE payment_date >= DATE('2026-06-03', '-12 months')` 锚定参考日只看近 12 个月。双键 join 是关键 —— 只用 `loan_id` 单键会让一笔贷款的多期计划和多期还款交叉相乘(fan-out),计数全错。

```sql
-- Track late payment rates and severity trends by month. Anchored to
-- REFERENCE_DATE '2026-06-03'.
SELECT
    strftime('%Y-%m', p.payment_date) AS payment_month,
    COUNT(*) AS total_payments,
    COUNT(CASE WHEN p.days_late = 0 THEN 1 END) AS on_time,
    COUNT(CASE WHEN p.days_late BETWEEN 1 AND 15 THEN 1 END) AS late_1_15_days,
    COUNT(CASE WHEN p.days_late BETWEEN 16 AND 30 THEN 1 END) AS late_16_30_days,
    ROUND(100.0 * COUNT(CASE WHEN p.days_late > 0 THEN 1 END) / COUNT(*), 2) AS late_payment_rate_pct,
    ROUND(AVG(CASE WHEN p.days_late > 0 THEN p.days_late END), 2) AS avg_days_late_when_late,
    ROUND(100.0 * SUM(CASE WHEN p.payment_amount < rs.scheduled_payment * 0.95 THEN 1 ELSE 0 END) / COUNT(*), 2) AS partial_payment_rate_pct
FROM payment p
JOIN repayment_schedule rs ON p.loan_id = rs.loan_id AND p.installment_number = rs.installment_number
WHERE p.payment_date >= DATE('2026-06-03', '-12 months')
GROUP BY payment_month
ORDER BY payment_month ASC;
```

**期望结果说明:**
返回按月时间序列:按逾期桶分布的付款计数与部分付款率。催收团队寻找趋势:若逾期率 3 个月内从 25% 上升到 35%,这是组合承压的信号,需要采取行动。反之,逾期率下降表明组合健康度提升。这些数据进入月度高管看板,并决定催收团队的人力配置。

---

### Query 15: 贷款金额与信用分相关性

**业务背景:**
承保团队正在评审贷款额度策略。当前政策允许贷款额度最高至年收入的 2 倍,但团队怀疑给低信用分借款人发放的大额贷款表现不佳。本分析检视批准金额、客户信用分、违约结果三者之间的关系。如果数据显示信用分 <680 的借款人借 >$300K 时违约率 20%+,那么策略就应该在贷款额度公式里加入信用分要求,而不只是基于收入。

**类别:** Aggregation
**难度:** Basic
**业务角色:** Analyst

**解题思路:**
做"信用分 × 贷款金额"的交叉表(crosstab)。loan join customer 拿信用分,LEFT JOIN default_event 保留未违约贷款。两个 CASE 表达式分别把信用分切成 4 档、把贷款金额切成 4 桶,然后 `GROUP BY` 这两个派生列,得到最多 16 个组合,每格算违约率。这是典型的"用 CASE 做动态分桶再聚合"。SQLite 允许在 GROUP BY 里直接引用 SELECT 中定义的别名,省去重复写 CASE。

```sql
-- Analyze relationship between loan amounts, credit scores, and default rates
SELECT
    CASE
        WHEN c.credit_score < 640 THEN 'Below 640'
        WHEN c.credit_score BETWEEN 640 AND 679 THEN '640-679'
        WHEN c.credit_score BETWEEN 680 AND 719 THEN '680-719'
        WHEN c.credit_score >= 720 THEN '720+'
    END AS credit_score_bucket,
    CASE
        WHEN l.approved_amount < 100000 THEN 'Under $100K'
        WHEN l.approved_amount BETWEEN 100000 AND 199999 THEN '$100K-$199K'
        WHEN l.approved_amount BETWEEN 200000 AND 299999 THEN '$200K-$299K'
        WHEN l.approved_amount >= 300000 THEN '$300K+'
    END AS loan_size_bucket,
    COUNT(l.id) AS loan_count,
    ROUND(AVG(l.approved_amount), 2) AS avg_loan_amount,
    COUNT(de.id) AS defaults,
    ROUND(100.0 * COUNT(de.id) / COUNT(l.id), 2) AS default_rate_pct
FROM loan l
JOIN customer c ON l.customer_id = c.id
LEFT JOIN default_event de ON l.id = de.loan_id
GROUP BY credit_score_bucket, loan_size_bucket
ORDER BY credit_score_bucket, loan_size_bucket;
```

**期望结果说明:**
返回信用分区间 × 贷款金额桶的交叉表,显示每个组合的违约率。预期揭示:大额贷款($300K+)发给低信用分(<680)借款人时,违约率不成比例地高(15-20%);而大额贷款发给高信用分(720+)借款人时表现良好(3-5%)。这为按信用分实施分层贷款额度上限提供依据,如 <640 上限 $150K、640-719 上限 $250K、720+ 上限 $500K。

---

### Query 16: 风险等级再定价机会

**业务背景:**
关系经理希望识别在贷借款人中,*当前*信用画像比贷款最初定级时更优的客户 — 要么是原始承保偏保守,要么是客户的信用画像在放款后被刷新过。这些客户可能符合再融资的较低利率,既能产生善意,又能防止他们被竞争对手挖走再融资。一个最初按 Grade C(9.5% 利率)定价、当前分数已达 Grade B(7.5%)的客户,在 $200K 贷款上每年可省数千美元。

> **Schema 说明:** 数据集只存客户的*当前* `credit_score`(每客户一个值),没有历史时间序列。本查询因此检测的是"当前 `credit_score` 超出其贷款定级所在 grade 上限"的借款人。几个月后再跑同一查询,除非 `credit_score` 被更新,否则会重复检测到同一批。

**类别:** Subquery + Join
**难度:** Advanced
**业务角色:** Manager

**解题思路:**
找"当前信用分已超出原始定级上限"的再定价候选。主表 loan join customer(拿当前信用分)、risk_grade(拿原始定级的利率)、loan_status(筛 CURRENT)。"当前应得等级 / 利率"用**标量子查询**:`(SELECT grade_code FROM risk_grade WHERE c.credit_score BETWEEN min AND max)` —— 按当前分数反查应落在哪个等级。筛 `credit_score > rg_current.max_credit_score + 10`,即"分数比原等级上限还高 10 分以上"。潜在年省 = 余额 × 利率差。注意:数据集只存客户**当前**信用分(没有历史时间序列),所以这里检测的是当前分超出原定级上限的人,几个月后再跑会重复命中同一批。

```sql
-- Identify borrowers whose current credit profile qualifies for better risk grade
SELECT
    l.loan_number,
    c.business_name,
    c.credit_score AS current_credit_score,
    rg_current.grade_code AS loan_risk_grade,
    rg_current.interest_rate AS current_rate,
    (SELECT rg2.grade_code
     FROM risk_grade rg2
     WHERE c.credit_score BETWEEN rg2.min_credit_score AND rg2.max_credit_score) AS qualified_grade,
    (SELECT rg2.interest_rate
     FROM risk_grade rg2
     WHERE c.credit_score BETWEEN rg2.min_credit_score AND rg2.max_credit_score) AS qualified_rate,
    l.outstanding_balance,
    l.term_months,
    ROUND(l.outstanding_balance * (rg_current.interest_rate -
          (SELECT rg2.interest_rate FROM risk_grade rg2
           WHERE c.credit_score BETWEEN rg2.min_credit_score AND rg2.max_credit_score)) / 100, 2) AS potential_annual_savings
FROM loan l
JOIN customer c ON l.customer_id = c.id
JOIN risk_grade rg_current ON l.risk_grade_id = rg_current.id
JOIN loan_status ls ON l.current_status_id = ls.id
WHERE ls.status_code = 'CURRENT'
  AND l.outstanding_balance > 50000
  AND c.credit_score > rg_current.max_credit_score + 10
ORDER BY potential_annual_savings DESC
LIMIT 30;
```

**期望结果说明:**
返回当前贷款中,客户信用分超出其原始风险等级上限至少 10 分的记录,表明客户已符合更优等级。显示再融资后的潜在年化利息节省。年省 >$2,000 的客户是高优先级外联目标。关系经理会拨打这些客户的电话提供再融资,提升留存,并向客户传递"Pacific Bridge 奖励良好还款行为"的信息。

---

### Query 17: 月度现金流预测

**业务背景:**
CFO 需要预测未来 12 个月来自贷款还款的月度现金流入,以管理公司的流动性与融资需求。Pacific Bridge 通过授信额度为贷款融资,该额度要求维持最低现金准备金。通过预测现有组合的应还款,CFO 可以确定何时支取信贷额度、何时偿还、以及还有多少新放款的发放空间。错失现金流预测可能导致流动性紧张或昂贵的紧急借款。

**类别:** Aggregation + Date
**难度:** Intermediate
**业务角色:** Finance

**解题思路:**
做未来 12 个月的现金流预测。直接用 `repayment_schedule`(它是计划应还,代表预期流入),join loan / loan_status 只保留 `CURRENT` 贷款(已结清 / 违约的不再贡献现金流)。`WHERE due_date BETWEEN '2026-06-03' AND '+12 months'` 取未来窗口。按月聚合 `SUM(scheduled_payment)` 并拆成本金 / 利息两部分。粒度是"一个未来月份一行"。要点:用计划表而非实际 `payment` 表,因为预测的是"未来应收",未来还没有实际还款记录可用。

```sql
-- Project expected monthly cash inflows from scheduled loan repayments.
-- Anchored to REFERENCE_DATE '2026-06-03'. Only CURRENT loans contribute —
-- the DISBURSED status code exists in the lookup but isn't used in this
-- dataset (loans transition directly to CURRENT after disbursement).
SELECT
    strftime('%Y-%m', rs.due_date) AS month,
    COUNT(DISTINCT rs.loan_id) AS loans_with_payments_due,
    COUNT(rs.id) AS total_installments_due,
    ROUND(SUM(rs.scheduled_payment), 2) AS expected_total_payment,
    ROUND(SUM(rs.principal_portion), 2) AS expected_principal,
    ROUND(SUM(rs.interest_portion), 2) AS expected_interest,
    ROUND(AVG(rs.scheduled_payment), 2) AS avg_payment_per_loan
FROM repayment_schedule rs
JOIN loan l ON rs.loan_id = l.id
JOIN loan_status ls ON l.current_status_id = ls.id
WHERE rs.due_date BETWEEN DATE('2026-06-03') AND DATE('2026-06-03', '+12 months')
  AND ls.status_code = 'CURRENT'
GROUP BY month
ORDER BY month ASC;
```

**期望结果说明:**
返回未来 12 个月的预期付款预测,按本金和利息成分拆分,显示预期总流入和活跃贷款数。CFO 将其与已承诺的新贷款发放(流出)对比以计算净现金头寸。若任何月份显示净负现金,公司就需要提前安排资金。该预测随着新贷款发放和旧贷款到期,每周更新。

---

### Query 18: 申请处理时长分析

**业务背景:**
运营副总裁设定了"7 个工作日内回复贷款申请"的目标。周转慢会损害客户满意度,也会增加申请人去找竞争对手的风险。本分析测量从申请提交到决策的时间,识别瓶颈。若某些信贷员或行业一贯耗时较长,运营团队可调查原因是复杂度、工作量失衡还是低效。把周转从 10 天缩到 5 天,有望让"批准 → 放款"转化率提升 15%。

**类别:** Date Calculation
**难度:** Basic
**业务角色:** Operations

**解题思路:**
测申请处理时长。application join loan_officer,处理天数 = `JULIANDAY(decision_date) - JULIANDAY(application_date)`(`JULIANDAY` 把日期转成可相减的儒略日数,是 SQLite 算日期差的标准做法)。SLA 达成用条件计数 `COUNT(CASE WHEN diff <= 7 THEN 1 END)`。`WHERE decision_date IS NOT NULL` 排除还没决策的申请,`HAVING >= 20` 滤掉样本太小的信贷员。按信贷员聚合,按平均时长降序把最慢的排在最前。

```sql
-- Measure application processing times from submission to decision
SELECT
    lo.employee_id,
    lo.first_name || ' ' || lo.last_name AS officer_name,
    COUNT(a.id) AS applications_processed,
    ROUND(AVG(JULIANDAY(a.decision_date) - JULIANDAY(a.application_date)), 1) AS avg_days_to_decision,
    MIN(JULIANDAY(a.decision_date) - JULIANDAY(a.application_date)) AS min_days,
    MAX(JULIANDAY(a.decision_date) - JULIANDAY(a.application_date)) AS max_days,
    COUNT(CASE WHEN JULIANDAY(a.decision_date) - JULIANDAY(a.application_date) <= 7 THEN 1 END) AS within_sla,
    ROUND(100.0 * COUNT(CASE WHEN JULIANDAY(a.decision_date) - JULIANDAY(a.application_date) <= 7 THEN 1 END) / COUNT(a.id), 2) AS sla_compliance_pct
FROM application a
JOIN loan_officer lo ON a.loan_officer_id = lo.id
WHERE a.decision_date IS NOT NULL
  AND a.application_date IS NOT NULL
GROUP BY lo.id, lo.employee_id, lo.first_name, lo.last_name
HAVING applications_processed >= 20
ORDER BY avg_days_to_decision DESC;
```

**期望结果说明:**
按信贷员返回周转时间指标:申请到决策的平均/最小/最大天数,以及 SLA 达成率。`avg_days_to_decision > 10` 或 SLA 达成率 < 70% 的信贷员需要培训或工作量重新平衡。运营团队按月跟踪,并设个人绩效目标。行业基准是 5-7 天,Pacific Bridge 目标是 90%+ SLA 达成率。

---

### Query 19: 行业特异性违约模式

**业务背景:**
首席风险官正在准备投资者会议,需要解释组合的行业敞口及相关风险。投资者尤其担心餐饮、酒店等在疫情中挣扎的周期性行业。本查询分析每个行业的违约率、损失严重度、集中度,使 CRO 能够说明哪些行业风险最大、采取了什么行动(行业上限、更高定价、强化监控)。展示主动风险管理可以让投资者放心,稳定融资成本。

**类别:** CTE + Aggregation
**难度:** Advanced
**业务角色:** Executive

**解题思路:**
按行业深挖违约与损失。CTE `industry_performance` 把 `industry → customer → loan → default_event` 串起来(loan、default 都用 LEFT JOIN,保留没放款 / 没违约的行业),按行业聚合贷款数、敞口、违约数、损失。外层再算每行业占组合的比例(用 `(SELECT SUM(current_outstanding) FROM industry_performance)` 引用 CTE 自身做全局分母)以及 `实际违约率 − 历史基线` 的偏差。把聚合放进 CTE、占比放外层,是因为占比需要先有"各行业敞口"这个中间结果才能算出全局分母。

```sql
-- Deep dive into default patterns and losses by industry
WITH industry_performance AS (
    SELECT
        i.industry_name,
        i.default_rate_baseline,
        COUNT(DISTINCT l.id) AS total_loans,
        ROUND(SUM(l.approved_amount), 2) AS total_originated,
        ROUND(SUM(l.outstanding_balance), 2) AS current_outstanding,
        COUNT(de.id) AS defaults,
        ROUND(100.0 * COUNT(de.id) / COUNT(DISTINCT l.id), 2) AS actual_default_rate_pct,
        ROUND(SUM(de.loss_amount), 2) AS total_losses,
        ROUND(AVG(de.loss_amount), 2) AS avg_loss_per_default
    FROM industry i
    JOIN customer c ON i.id = c.industry_id
    LEFT JOIN loan l ON c.id = l.customer_id
    LEFT JOIN default_event de ON l.id = de.loan_id
    GROUP BY i.id, i.industry_name, i.default_rate_baseline
)
SELECT
    industry_name,
    default_rate_baseline AS historical_baseline_pct,
    total_loans,
    current_outstanding,
    ROUND(100.0 * current_outstanding / (SELECT SUM(current_outstanding) FROM industry_performance), 2) AS pct_of_portfolio,
    defaults,
    actual_default_rate_pct,
    ROUND(actual_default_rate_pct - default_rate_baseline, 2) AS performance_vs_baseline,
    total_losses,
    avg_loss_per_default
FROM industry_performance
WHERE total_loans > 0
ORDER BY current_outstanding DESC;
```

**期望结果说明:**
返回每个行业的综合表现指标:当前敞口、实际违约率与历史基线对比、总损失、单次违约平均损失。实际违约率明显高于基线的行业(如 Hospitality 15% vs 12.4% 基线)是表现不佳的,可能需要定价调整或敞口上限。CRO 用本表向投资者证明公司了解行业风险并主动管理集中度。

---

### Query 20: 按 LTV 的客户分群

**业务背景:**
CEO 希望落地分层客户服务模型 — 高价值客户享受白手套服务(专属客户经理、优先处理),低价值客户走自助渠道。本分群分析根据每位客户的总贷款体量、已付利息、违约历史计算生命周期价值(LTV)。借款总额 $500K+ 且零违约的是"Platinum"层;单笔且 <$100K 的是"Standard"层。这指导关系管理与客户成功团队的资源分配。

**类别:** CTE + Window Function
**难度:** Advanced
**业务角色:** Executive

**解题思路:**
做客户分层。CTE1 `customer_metrics` 按客户聚合贷款数、总借款、估算生命周期利息、违约数、结清率。CTE2 `customer_ltv` 在此基础上算 `lifetime_value_score = 总借款 + 估算利息 − 违约×50000`。最后用窗口函数 `NTILE(10) OVER (ORDER BY lifetime_value_score DESC)` 把客户按 LTV 切成十分位,并用 CASE 分 Platinum / Gold / Silver / Standard 层。NTILE 是窗口函数,它在不折叠行的前提下给每行打"第几个十分位"标签 —— 这是 GROUP BY 做不到的,必须用窗口函数。注意:估算利息用单利近似,会高估真实摊销利息约 2 倍,仅用于相对排名,不可当真实利息核算。

```sql
-- Segment customers by lifetime value and assign tiers
WITH customer_metrics AS (
    SELECT
        c.id AS customer_id,
        c.business_name,
        c.is_repeat_customer,
        COUNT(DISTINCT l.id) AS total_loans,
        ROUND(SUM(l.approved_amount), 2) AS total_borrowed,
        -- Rough lifetime-interest estimate using simple interest on the
        -- original principal — overstates true amortized interest by roughly
        -- 2x for typical 3-year loans. Acceptable for relative LTV ranking
        -- but not for actual interest accounting.
        ROUND(SUM(l.approved_amount * l.interest_rate / 100 * l.term_months / 12), 2) AS estimated_lifetime_interest,
        COUNT(de.id) AS defaults,
        ROUND(SUM(CASE WHEN ls.status_code = 'PAID_OFF' THEN 1 ELSE 0 END) * 100.0 / COUNT(l.id), 2) AS completion_rate_pct,
        ROUND(AVG(l.interest_rate), 2) AS avg_interest_rate
    FROM customer c
    LEFT JOIN loan l ON c.id = l.customer_id
    LEFT JOIN loan_status ls ON l.current_status_id = ls.id
    LEFT JOIN default_event de ON l.id = de.loan_id
    GROUP BY c.id, c.business_name, c.is_repeat_customer
    HAVING total_loans > 0
),
customer_ltv AS (
    SELECT
        *,
        ROUND(total_borrowed + estimated_lifetime_interest - (defaults * 50000), 2) AS lifetime_value_score
    FROM customer_metrics
)
SELECT
    customer_id,
    business_name,
    total_loans,
    total_borrowed,
    estimated_lifetime_interest,
    defaults,
    lifetime_value_score,
    CASE
        WHEN lifetime_value_score >= 500000 AND defaults = 0 THEN 'Platinum'
        WHEN lifetime_value_score >= 250000 AND defaults = 0 THEN 'Gold'
        WHEN lifetime_value_score >= 100000 OR is_repeat_customer = 1 THEN 'Silver'
        ELSE 'Standard'
    END AS customer_tier,
    NTILE(10) OVER (ORDER BY lifetime_value_score DESC) AS ltv_decile
FROM customer_ltv
ORDER BY lifetime_value_score DESC
LIMIT 100;
```

**期望结果说明:**
返回按生命周期价值评分(总借款 + 利息 − 违约损失)排序的前 100 客户,分到客户层(Platinum/Gold/Silver/Standard)。Platinum 客户(前 5-10%)获得专属客户经理与主动再融资邀约;Standard 层使用数字化自助。本分群驱动客户成功团队的资源分配,也决定谁能受邀参加专属活动、新产品早期访问等 VIP 待遇。

---

## 查询类别汇总

每个查询有一个"主类别"标签(它主要演示的 SQL 特性)。多数查询组合了多种技巧 — 下面的计数反映每个查询头部标注的主类别。

| 类别 | 数量 | 查询编号 |
|----------|-------|---------------|
| Aggregation (+ Join) | 8 | 1, 2, 5, 7, 10, 11, 15, 19 |
| CTE (+ Join / Aggregation) | 4 | 4, 8, 12, 20 |
| Subquery (+ Join) | 2 | 3, 16 |
| Join + Subquery | 1 | 9 |
| Date / Time Aggregation | 4 | 6, 13, 14, 17 |
| Date Calculation | 1 | 18 |

## 业务角色覆盖

| 角色 | 数量 | 查询编号 |
|------|-------|---------------|
| Executive / C-Level | 4 | 1, 5, 19, 20 |
| Manager | 4 | 2, 7, 12, 16 |
| Analyst | 5 | 3, 4, 8, 13, 15 |
| Operations | 4 | 6, 9, 14, 18 |
| Finance | 3 | 10, 11, 17 |

## 难度分布

| 难度 | 数量 | 查询编号 |
|------------|-------|---------------|
| Basic | 4 | 6, 11, 15, 18 |
| Intermediate | 9 | 1, 2, 5, 7, 9, 10, 13, 14, 17 |
| Advanced | 7 | 3, 4, 8, 12, 16, 19, 20 |

---

## 备注

- 所有查询按 SQLite 3.x 语法设计
- 日期计算使用 `JULIANDAY()` 与 `strftime()` 函数(SQLite 专属)
- 迁移到 PostgreSQL 时,把 `JULIANDAY()` 差值改为日期减法、`strftime()` 改为 `TO_CHAR()`
- 迁移到 MySQL 时,使用 `DATEDIFF()` 与 `DATE_FORMAT()`
- 查询引用的 TSV 文件按拓扑序号(01-10)排列,该顺序也是安全的加载顺序
- 所有货币金额单位为 USD,保留 2 位小数
- 查询旨在回答 Pacific Bridge Lending 咨询项目的 5 个核心业务问题
