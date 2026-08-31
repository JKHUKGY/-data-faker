# 金融科技 — 实时反欺诈 & 反洗钱平台 (NovaRisk AI) — SQL 查询参考

## 概述

针对 `fintech_real_time_fraud_aml_platform_high` 数据集的 20 条业务导向 SQL 查询。每条查询都对应业务背景文档里的某个业务问题,且已在打包的 SQLite 数据库上验证可执行。

- **业务背景、行业科普、术语表、指标公式** 请见 `01-fintech_real_time_fraud_aml_platform_high_business_context-cn.md`。
- **表结构、字段、生成规则、DDL** 请见 `02-fintech_real_time_fraud_aml_platform_high_er_document-cn.md`。
- 由于 `transaction` 是 SQLite 保留字,本文档始终用双引号写成 `"transaction"`。
- **基准日 (REFERENCE_DATE) = `2026-06-05`。** 数据集锚定在这一固定日期,每条查询都把它写成字面量字符串 (例如 `JULIANDAY('2026-06-05')`),而不是 `DATE('now')` — 这样无论哪天运行,结果都可复现。

### 如何使用本文档

这份文档是教学型的。设想你是一名刚读完业务背景和 ER 文档的实习分析师,经理把这 20 条查询交给你"这周做完"。

**每条查询都有五个固定段落,按顺序读:**

1. **业务背景** — 谁在问、为什么问、答案要支撑什么决策、为什么是现在。把查询锚回公司里的具体角色和场景。
2. **类别 / 难度 / 业务角色** — 三个标签,快速告诉你这题练什么 SQL 技巧、有多难、服务哪个岗位。
3. **解题思路** — 在你看到 SQL 之前,先讲清楚该碰哪些表、join 怎么搭、坑在哪里 (fan-out、重复计数、LEFT vs INNER)、聚合粒度是什么、为什么用 CTE 或窗口函数。这一段是学习重点。
4. **SQL** — 可直接对打包数据库运行的代码。读它、理解它,而不只是跑它。
5. **预期结果 + 业务结论** — 结果长什么样 (行数、列义、对应量级),以及拿到数字后分析师下一步该做什么。跑出结果只是分析的开始,不是结束。

**用法建议:** 先读业务背景搞清楚"为什么",再读解题思路在脑子里搭出查询骨架,然后自己试着写一遍,最后对照 SQL 和预期结果检查。每条查询都能追溯到业务背景文档里的某个业务问题 (Q1–Q8)。

---

## 查询索引

| # | 标题 | 业务角色 | 类别 | 难度 |
|---|-------|---------------|----------|------------|
| 1 | 实时打分 SLA 快照 (p50/p95/p99) | Operations (运营) | Aggregation + Window | 中等 |
| 2 | 按合同金额排名的头部收入客户 | Executive (高管) | Aggregation | 入门 |
| 3 | 每客户的决策分布 | Manager (经理) | Join + Aggregation | 入门 |
| 4 | 按欺诈类型的告警量 | Analyst (分析师) | Join + Aggregation | 入门 |
| 5 | 按检测规则的误报率 | Manager (经理) | Aggregation + Filter | 中等 |
| 6 | 每分析师的平均调查时长 | Manager (经理) | Date Diff + Aggregation | 中等 |
| 7 | 协同攻击团伙检测 (共享设备指纹) | Analyst (分析师) | CTE / 图风格 | 高级 |
| 8 | 各客户的高风险走廊敞口 | Executive (高管) | Aggregation + Filter | 入门 |
| 9 | 每日交易与告警趋势 | Analyst (分析师) | Date / Time series | 中等 |
| 10 | 每客户的 Top-5 SAR 提交分析师 | Manager (经理) | Window Function (每组 Top-N) | 中等 |
| 11 | 客户风险评级 vs 实际欺诈率 | Analyst (分析师) | CTE + Aggregation | 高级 |
| 12 | 命中制裁名单的 SAR 叙述 | Operations (运营) | 在可空 FK 上的 Inner Join | 中等 |
| 13 | Vera AI agent 工具使用与成本 | Finance (财务) | Aggregation | 入门 |
| 14 | 冠军 vs 挑战者模型决策漂移 | Analyst (分析师) | CTE + 条件聚合 | 高级 |
| 15 | DECLINE 阻断金额 Top-10 账户 | Operations (运营) | Aggregation + Sort | 入门 |
| 16 | 每客户的真正 7 自然日滚动告警速率 | Analyst (分析师) | 递归 CTE + Window | 高级 |
| 17 | 使用 VPN 且国家与账户国家不同的 session | Operations (运营) | Join | 中等 |
| 18 | 高优先级、开案超 14 天仍未关的案件 | Manager (经理) | Date Diff + Filter | 中等 |
| 19 | 收入集中度: top-3 客户份额 | Finance (财务) | CTE + Window | 高级 |
| 20 | SAR 叙述中含 "structuring" 的模式搜索 | Operations (运营) | LIKE / 模式 | 入门 |

---

## 查询

### Query 1: 实时打分 SLA 快照 (p50 / p95 / p99)

**业务背景:**
SRE 负责人需要每天早晨 standup 之前一眼判断实时打分 API 是否满足 <100ms p99 延迟承诺。如果 p99 在向 100ms 之上爬升,他们会呼叫值班工程师调查。

**类别:** Aggregation + Window Function
**难度:** 中等
**业务角色:** Operations (运营)

**解题思路:**
这题只需要 `risk_score_event` 一张表的 `latency_ms`。难点是 SQLite 没有 `PERCENTILE_CONT`,所以用 `ROW_NUMBER() OVER (ORDER BY latency_ms)` 给每行排名 (`rn`),再用 `COUNT(*) OVER ()` 拿到总行数 `n`,然后用 `MAX(CASE WHEN rn = CAST(n*0.99 AS INT) ...)` 把目标分位那一行的值"挑"出来。一个输出行就是整个平台的延迟画像。SLA 违约率用独立的标量子查询算,不要和窗口混在一起,否则分母会被窗口的行数影响。

```sql
-- SQLite 没有原生 PERCENTILE_CONT,所以我们用对行排序、取目标分位行的方式近似。
WITH ranked AS (
    SELECT
        latency_ms,
        ROW_NUMBER() OVER (ORDER BY latency_ms)         AS rn,
        COUNT(*)    OVER ()                              AS n
    FROM risk_score_event
)
SELECT
    (SELECT COUNT(*) FROM risk_score_event)                   AS total_scored,
    ROUND((SELECT AVG(latency_ms) FROM risk_score_event), 1)  AS avg_latency_ms,
    MAX(CASE WHEN rn = CAST(n * 0.50 AS INTEGER) THEN latency_ms END) AS p50_latency_ms,
    MAX(CASE WHEN rn = CAST(n * 0.95 AS INTEGER) THEN latency_ms END) AS p95_latency_ms,
    MAX(CASE WHEN rn = CAST(n * 0.99 AS INTEGER) THEN latency_ms END) AS p99_latency_ms,
    ROUND(
        (SELECT SUM(CASE WHEN latency_ms > 100 THEN 1.0 ELSE 0 END) FROM risk_score_event) /
        (SELECT COUNT(*) FROM risk_score_event),
        4
    )                                                          AS pct_over_100ms_sla
FROM ranked;
```

**预期结果说明:**
一行,包含总打分事件数加 p50 / p95 / p99 延迟以及 SLA 违约率。本数据集中 p50 ≈ 100ms,p99 ≈ 175ms;如果生产环境 p99 保持 ≤ 100ms,就是绿灯条件。

---

### Query 2: 按合同金额排名的头部收入客户

**业务背景:**
CFO 需要快速浏览 NovaRisk 最大付费客户。用于董事会汇报和 Customer Success 资源优先级 — 失去一个 top-3 客户会显著影响 ARR。

**类别:** Aggregation
**难度:** 入门
**业务角色:** Executive (高管)

**解题思路:**
最简单的一题:`client_institution` join `industry_vertical` 拿到垂直行业名,按 `annual_contract_value_usd` 降序取前 5。`WHERE is_active = 1` 过滤掉已流失客户。合同存续天数用 `JULIANDAY('2026-06-05') - JULIANDAY(contract_start_date)` 算 — 注意基准日写死成字面量,不要用 `DATE('now')`,否则结果不可复现。无需聚合或窗口函数。

```sql
SELECT
    ci.legal_name,
    iv.code                                AS vertical,
    ci.annual_contract_value_usd,
    ROUND(JULIANDAY('2026-06-05') - JULIANDAY(ci.contract_start_date)) AS days_tenure
FROM client_institution ci
JOIN industry_vertical iv ON iv.id = ci.industry_vertical_id
WHERE ci.is_active = 1
ORDER BY ci.annual_contract_value_usd DESC
LIMIT 5;
```

**预期结果说明:**
五家客户按 ACV 排名,附带其垂直行业和合同存续天数。Skyline National Bank ($1.2M) 通常居首。

---

### Query 3: 每客户的决策分布

**业务背景:**
一个 Customer Success Manager 在准备季度业务回顾 (QBR) 时,需要向客户展示 APPROVE / REVIEW / DECLINE / STEP_UP 决策的分布。银行非常关注这一点 — DECLINE 太多会伤害客户体验;APPROVE 太多则意味着欺诈在漏过去。

**类别:** Join + Aggregation
**难度:** 入门
**业务角色:** Manager (经理)

**解题思路:**
决策值 (decision_id) 挂在 `risk_score_event` 上,但"客户"要顺着 `transaction → account → client_institution` 一路 join 回去 (打分事件本身不直接带客户)。再 join `risk_decision_dim` 把 decision_id 翻成可读的 APPROVE/REVIEW/…。一个输出行 = 一个客户 × 一种决策的事件数。按 `ci.id, ci.legal_name, rd.code` 三列 GROUP BY,让 SELECT 里每个非聚合列都出现在 GROUP BY 中 (这样在 Postgres 严格模式下也能跑)。

```sql
SELECT
    ci.id                                  AS client_id,
    ci.legal_name,
    rd.code                                AS decision,
    COUNT(*)                               AS event_count
FROM risk_score_event rse
JOIN "transaction" t  ON t.id  = rse.transaction_id
JOIN account a        ON a.id  = t.source_account_id
JOIN client_institution ci ON ci.id = a.client_institution_id
JOIN risk_decision_dim rd  ON rd.id = rse.decision_id
GROUP BY ci.id, ci.legal_name, rd.code
ORDER BY ci.legal_name, event_count DESC;
```

**预期结果说明:**
对 12 个客户中的每一个,给出四个决策桶里的事件数。APPROVE 通常占大头 (~60-70%),DECLINE 是最小块 (~5-8%)。具体比例会随 post-boost 分数分布略有变化 (见 ER 文档 §7.3)。

---

### Query 4: 按欺诈类型的告警量

**业务背景:**
一位反欺诈分析师在准备每周威胁简报时,需要知道哪些欺诈类型 (电汇欺诈、账户盗用、deepfake 开户等) 在本季度产生了最多告警。这个答案决定下周团队重点放在哪里。

**类别:** Join + Aggregation
**难度:** 入门
**业务角色:** Analyst (分析师)

**解题思路:**
两表 join:`alert` join `fraud_type_dim`。一个输出行 = 一种欺诈类型的告警总数。把 `severity_weight` 一并带出来便于排序解读。GROUP BY 同时含 `code` 和 `severity_weight` (两者一一对应,一起 group 不改变粒度)。这是入门级聚合,没有 fan-out 风险,因为 `alert` 直接外键到 `fraud_type_dim`,是多对一关系。

```sql
SELECT
    ft.code                                AS fraud_type,
    ft.severity_weight,
    COUNT(*)                               AS alert_count
FROM alert al
JOIN fraud_type_dim ft ON ft.id = al.fraud_type_id
GROUP BY ft.code, ft.severity_weight
ORDER BY alert_count DESC;
```

**预期结果说明:**
9 种欺诈类型按告警量排序。电汇欺诈和 card_not_present 通常领先,因为它们对应最常见的交易类型。

---

### Query 5: 按检测规则的误报率

**业务背景:**
反欺诈运营经理需要决定哪些规则该退役。一条触发数千告警但全是误报的规则比没有规则还糟,因为它烧掉了分析师的时间。本查询按 FP 率排序规则,让经理能据此行动。

**类别:** Aggregation + Filter
**难度:** 中等
**业务角色:** Manager (经理)

**解题思路:**
核心是只看"规则触发的告警",所以用 INNER JOIN `alert` ↔ `detection_rule` (自动排除 `detection_rule_id IS NULL` 的纯 ML 告警)。FP 率 = 误报数 / 已判定数,用 `SUM(CASE WHEN is_true_positive = 0 …)` 配 `NULLIF(…)` 防除零。`WHERE is_true_positive IS NOT NULL` 把还没判定的告警 (status 为 OPEN/IN_REVIEW/ESCALATED) 排除在分母外。`HAVING alerts_raised >= 3` 过掉样本太小的规则,避免一两个告警就得出 100% FP 的噪声结论。

```sql
SELECT
    dr.rule_code,
    dr.threshold_score,
    COUNT(*)                                                          AS alerts_raised,
    SUM(CASE WHEN al.is_true_positive = 0 THEN 1 ELSE 0 END)          AS false_positives,
    SUM(CASE WHEN al.is_true_positive = 1 THEN 1 ELSE 0 END)          AS true_positives,
    ROUND(
        SUM(CASE WHEN al.is_true_positive = 0 THEN 1.0 ELSE 0 END) /
        NULLIF(SUM(CASE WHEN al.is_true_positive IS NOT NULL THEN 1 ELSE 0 END), 0),
        3
    )                                                                  AS fp_rate
FROM alert al
JOIN detection_rule dr ON dr.id = al.detection_rule_id
WHERE al.is_true_positive IS NOT NULL
GROUP BY dr.rule_code, dr.threshold_score
HAVING alerts_raised >= 3
ORDER BY fp_rate DESC, alerts_raised DESC;
```

**预期结果说明:**
规则按误报率从高到低排序。`VPN_PLUS_GEO_MISMATCH` 和 `CARD_TESTING_BURST` 通常最吵闹 — 是阈值调优或退役的候选。

> **范围注释:** 本查询*故意*排除纯 ML 告警 (即 `detection_rule_id IS NULL`)。问题是"我该退役哪条规则",所以只统计规则触发的告警。如果要审计纯 ML 质量,把 INNER JOIN 改成 `GROUP BY`,把 `rule IS NULL` 单独分桶。

---

### Query 6: 每分析师的平均调查时长

**业务背景:**
反欺诈运营经理想知道哪些分析师是快速调查者 (从案件打开到关闭的小时数)。用于绩效评估和识别哪些人需要更多培训。

**类别:** Date Diff + Aggregation
**难度:** 中等
**业务角色:** Manager (经理)

**解题思路:**
`investigation_case` join `analyst`,只看已关闭案件 (`WHERE closed_at IS NOT NULL`)。调查时长用 `(JULIANDAY(closed_at) - JULIANDAY(opened_at)) * 24` 换算成小时再 `AVG`。一个输出行 = 一个分析师。`HAVING closed_cases >= 1` 保证至少有一个样本才上榜。升序排列让最快的人排在最前 — 但解读时要提醒读者:"快"既可能是能力强 (好事),也可能是跳过了应有的尽职调查 (坏事)。

```sql
SELECT
    an.id                                                          AS analyst_id,
    an.full_name,
    an.seniority,
    COUNT(ic.id)                                                   AS closed_cases,
    ROUND(AVG((JULIANDAY(ic.closed_at) - JULIANDAY(ic.opened_at)) * 24), 1) AS avg_hours_to_close
FROM investigation_case ic
JOIN analyst an ON an.id = ic.assigned_analyst_id
WHERE ic.closed_at IS NOT NULL
GROUP BY an.id, an.full_name, an.seniority
HAVING closed_cases >= 1
ORDER BY avg_hours_to_close ASC;
```

**预期结果说明:**
分析师按关案速度排名。既可以发现学习能力强的 (好事),也可以发现可能在跳过应有尽职调查的 (坏事)。

---

### Query 7: 协同攻击团伙检测 (共享设备指纹)

**业务背景:**
无监督 ML 的招牌能力是 **协同攻击团伙检测** — 许多"不相关"账户其实由同一台设备秘密操作。一名反欺诈分析师怀疑某个团伙横跨该银行的三个客户。本查询列出最近 90 天内被多于一个 end_user 使用过的所有设备,并按设备背后有多少用户排序。

**类别:** Self-Join / 子查询 (图风格)
**难度:** 高级
**业务角色:** Analyst (分析师)

**解题思路:**
这是图风格题。先用 CTE `device_user_pairs` 把 (设备, 用户, 客户) 三元组**去重** (`SELECT DISTINCT`),否则一个用户在同一设备上的多个 session 会重复计数,虚高 distinct 用户数。然后按设备聚合 `COUNT(DISTINCT end_user_id)` (背后多少用户) 和 `COUNT(DISTINCT client_institution_id)` (横跨多少家银行)。`HAVING distinct_users >= 2` 只留共享设备。最强信号是一台设备横跨 2+ 家银行 — 这正是 Data Consortium 的价值所在,单家银行自己看不到。

```sql
WITH device_user_pairs AS (
    SELECT DISTINCT
        ds.device_id,
        ds.end_user_id,
        eu.client_institution_id
    FROM device_session ds
    JOIN end_user eu ON eu.id = ds.end_user_id
)
SELECT
    d.id                                  AS device_id,
    d.fingerprint_hash,
    d.device_type,
    d.is_emulator,
    COUNT(DISTINCT dup.end_user_id)       AS distinct_users,
    COUNT(DISTINCT dup.client_institution_id) AS distinct_clients
FROM device_user_pairs dup
JOIN device d ON d.id = dup.device_id
GROUP BY d.id
HAVING distinct_users >= 2
ORDER BY distinct_users DESC, distinct_clients DESC
LIMIT 25;
```

**预期结果说明:**
一份被 2+ end_user 使用过的设备清单。最强信号是:一台设备驱动 3+ 账户、横跨 2+ 不同银行 — 极有可能是欺诈团伙 (跨机构视角正是 Data Consortium 的价值主张)。

---

### Query 8: 各客户的高风险走廊敞口

**业务背景:**
NovaRisk 的首席风险官需要知道哪些客户机构在高风险走廊 (Iran、North Korea、Syria、Belarus、Russia、Myanmar) 暴露最重。这些需要额外 AML 审查,可能会触发监管问询。

**类别:** Aggregation + Filter
**难度:** 入门
**业务角色:** Executive (高管)

**解题思路:**
从 `transaction` 顺着 `account → client_institution` join 回客户,`WHERE is_high_risk_corridor = 1` 只看走廊交易,按客户 `SUM(amount_usd)`。一个输出行 = 一个客户的走廊敞口。体量大的银行天然居前 (流量多);真正的红旗是体量小但敞口不成比例的客户,所以读数时要结合该客户的总流量看,而不是只盯绝对金额。`is_high_risk_corridor` 是布尔列,过滤成本低。

```sql
SELECT
    ci.id                                    AS client_id,
    ci.legal_name,
    COUNT(*)                                 AS high_risk_txn_count,
    ROUND(SUM(t.amount_usd), 2)              AS high_risk_exposure_usd,
    ROUND(AVG(t.amount_usd), 2)              AS avg_amount_usd
FROM "transaction" t
JOIN account a ON a.id = t.source_account_id
JOIN client_institution ci ON ci.id = a.client_institution_id
WHERE t.is_high_risk_corridor = 1
GROUP BY ci.id, ci.legal_name
ORDER BY high_risk_exposure_usd DESC;
```

**预期结果说明:**
客户按总美元高风险国家敞口排序。这里居前的应是体量最大的银行 (流量多),但一个体量小却暴露不成比例的客户就是值得打电话核实的红旗。

---

### Query 9: 每日交易与告警趋势

**业务背景:**
一位数据分析师在搭周度反欺诈运营看板时,需要逐日的交易数、告警数和告警率。突增通常关联欺诈浪潮 (例如周末 card-testing 爆发)。

**类别:** Date / 时间序列 + Aggregation
**难度:** 中等
**业务角色:** Analyst (分析师)

**解题思路:**
时间序列题。`transaction` LEFT JOIN `alert` — 用 LEFT 是因为绝大多数交易没有告警,改成 INNER 会把"没有告警的日子"整天抹掉,趋势就失真。用 `DATE(initiated_at)` 把时间戳截断到天,`COUNT(DISTINCT t.id)` 和 `COUNT(DISTINCT al.id)` 分别数交易和告警。`COUNT(DISTINCT)` 是必须的:一笔交易可能挂多条告警,直接 `COUNT(*)` 会因 join fan-out 重复计数。按天 GROUP BY 后升序排列。

```sql
SELECT
    DATE(t.initiated_at)                                       AS day,
    COUNT(DISTINCT t.id)                                       AS txn_count,
    COUNT(DISTINCT al.id)                                      AS alert_count,
    ROUND(COUNT(DISTINCT al.id) * 1.0 / COUNT(DISTINCT t.id), 4) AS alert_rate
FROM "transaction" t
LEFT JOIN alert al ON al.transaction_id = t.id
WHERE t.initiated_at >= DATE('2026-05-01')
GROUP BY DATE(t.initiated_at)
ORDER BY day;
```

**预期结果说明:**
2026 年 5/6 月每天一行,含交易数、告警数和告警率。告警率通常在 15-25% 区间徘徊,但某些天可能突增。

---

### Query 10: 每客户的 Top-5 SAR 提交分析师

**业务背景:**
合规经理想表彰、奖励那些真正把案件推到监管申报阶段的分析师 — 那是团队里最高价值的活动。窗口函数对每个客户的最佳申报者排名;我们只留每客户的 top 5。

**类别:** Window Function (RANK + 每组 Top-N)
**难度:** 中等
**业务角色:** Manager (经理)

**解题思路:**
每组 Top-N 题,用窗口函数。先在 CTE `analyst_sar` 里算每个分析师的 SAR 数 — 注意从 `analyst → investigation_case → sar_report` 全程用 LEFT JOIN,否则没提交过 SAR 的分析师会在计数前就消失 (虽然外层 `WHERE sar_count > 0` 最终也会滤掉他们,但 LEFT 保证 `COUNT(sar.id)` 对每个分析师都算得对)。再用 `RANK() OVER (PARTITION BY client ORDER BY sar_count DESC)` 在每个客户内部排名,外层 `WHERE rank_in_client <= 5` 取每组前五。本快照 SAR 很少 (~9 份),所以只有少数客户有结果。

```sql
WITH analyst_sar AS (
    SELECT
        an.id              AS analyst_id,
        an.full_name,
        ci.legal_name      AS client,
        COUNT(sar.id)      AS sar_count
    FROM analyst an
    JOIN client_institution ci ON ci.id = an.client_institution_id
    LEFT JOIN investigation_case ic ON ic.assigned_analyst_id = an.id
    LEFT JOIN sar_report sar         ON sar.case_id = ic.id
    GROUP BY an.id, an.full_name, ci.legal_name
),
ranked AS (
    SELECT
        client,
        full_name,
        sar_count,
        RANK() OVER (PARTITION BY client ORDER BY sar_count DESC) AS rank_in_client
    FROM analyst_sar
    WHERE sar_count > 0
)
SELECT *
FROM ranked
WHERE rank_in_client <= 5
ORDER BY client, rank_in_client;
```

**预期结果说明:**
每客户的 top-5 分析师按 SAR 提交数排名。在当前数据集 (本快照里只有 9 份 SAR),只有少数几个客户能返回结果。

---

### Query 11: 客户风险评级 vs 实际欺诈率

**业务背景:**
模型风险团队想验证开户时分配的 CDD (客户尽职调查) 风险评级 (LOW/MEDIUM/HIGH) 是否真正预测了后续谁会去搞欺诈。如果 HIGH 评级客户的确认欺诈率与 LOW 评级客户一样,那 CDD 模型就坏了。

**类别:** CTE + Aggregation
**难度:** 高级
**业务角色:** Analyst (分析师)

**解题思路:**
这题要把开户时的 `customer_risk_rating` 与事后真实欺诈对齐。CTE `user_fraud` 从 `end_user` 一路 LEFT JOIN 到 `account → transaction → alert`,逐用户数交易数和确认欺诈告警数 — **全程 LEFT JOIN**,否则没交易/没告警的用户会被剔除,严重高估欺诈率。外层按评级聚合,算"每千笔交易确认欺诈数"做规模归一 (不能直接比绝对数,因为各评级的用户数和交易量差很多)。理想情况下该指标随 LOW→MEDIUM→HIGH 单调上升;若不上升,就说明 CDD 模型没有预测力、需要重做。

```sql
WITH user_fraud AS (
    SELECT
        eu.id,
        eu.customer_risk_rating,
        COUNT(DISTINCT t.id)                                  AS txn_count,
        COUNT(DISTINCT CASE WHEN al.is_true_positive = 1 THEN al.id END) AS confirmed_fraud_alerts
    FROM end_user eu
    LEFT JOIN account a ON a.end_user_id = eu.id
    LEFT JOIN "transaction" t ON t.source_account_id = a.id
    LEFT JOIN alert al ON al.transaction_id = t.id
    GROUP BY eu.id
)
SELECT
    customer_risk_rating,
    COUNT(*)                                                                          AS users,
    SUM(txn_count)                                                                    AS total_txns,
    SUM(confirmed_fraud_alerts)                                                       AS total_confirmed_fraud,
    ROUND(SUM(confirmed_fraud_alerts) * 1.0 / NULLIF(SUM(txn_count), 0) * 1000, 3)    AS confirmed_fraud_per_1k_txn
FROM user_fraud
GROUP BY customer_risk_rating
ORDER BY confirmed_fraud_per_1k_txn DESC;
```

**预期结果说明:**
三行,每个评级一行。理想情况下 fraud-per-1k-txn 从 LOW → MEDIUM → HIGH 单调上升;不上升就说明 CDD 模型需要重做。

---

### Query 12: 命中制裁名单的 SAR 叙述

**业务背景:**
AML 合规主管需要拿到所有因命中制裁名单而提交的 SAR,加上被命中的实体名。这些需要额外谨慎审查,如果名单更新还可能需要重新提交。

**类别:** Inner Join (在可空 FK 上 — 仅选命中的)
**难度:** 中等
**业务角色:** Operations (运营)

**解题思路:**
在可空外键上做 INNER JOIN 的典型用法:`sar_report` join `sanctions_watchlist ON sw.id = sar.watchlist_match_id`。因为是 INNER JOIN,`watchlist_match_id IS NULL` 的 SAR 会被自动排除 — 正好是我们想要的"只看命中名单的 SAR"。一个输出行 = 一份命中名单的 SAR 配上被命中实体。无需聚合,按 `filed_at` 倒序方便合规主管从最新的看起。

```sql
SELECT
    sar.filing_reference,
    sar.filed_at,
    sar.total_reported_amount_usd,
    sw.list_source,
    sw.listed_name,
    sw.risk_tier
FROM sar_report sar
JOIN sanctions_watchlist sw ON sw.id = sar.watchlist_match_id
ORDER BY sar.filed_at DESC;
```

**预期结果说明:**
SAR 与触发它们的制裁名单实体配对。部分 SAR 从底层告警继承名单命中,其他则在提交时被分配。`watchlist_match_id IS NULL` 的 SAR 被排除。

---

### Query 13: Vera AI agent 工具使用与成本

**业务背景:**
财务想把 LLM 算力成本分摊到 Vera 的四个子代理和具体工具上。如果 Investigation agent 的 `graph_link_explore` 工具消耗最多 token,那就是投入缓存或模型蒸馏的地方。

**类别:** Aggregation
**难度:** 入门
**业务角色:** Finance (财务)

**解题思路:**
单表聚合,`agent_interaction_log` 按 `agent_name + tool_called` 双列 GROUP BY。每个输出行 = 一个 (子代理, 工具) 组合的调用次数、平均/总 token、平均延迟、接受率。接受率用 `AVG(CASE WHEN human_approved = 1 THEN 1.0 ELSE 0 END)` (把布尔折算成 0/1 再求均值)。按 `total_tokens` 降序,让最烧钱的工具浮到顶部 — 那就是做缓存或模型蒸馏的优先目标。

```sql
SELECT
    agent_name,
    tool_called,
    COUNT(*)                          AS invocations,
    ROUND(AVG(tokens_used), 0)        AS avg_tokens,
    SUM(tokens_used)                  AS total_tokens,
    ROUND(AVG(latency_ms), 0)         AS avg_latency_ms,
    ROUND(AVG(CASE WHEN human_approved = 1 THEN 1.0 ELSE 0 END), 3) AS approval_rate
FROM agent_interaction_log
GROUP BY agent_name, tool_called
ORDER BY total_tokens DESC;
```

**预期结果说明:**
工具按 token 消耗总量排序。Investigation 工具占大头,因为案件驱动了最多使用。各工具批准率全场约 92%。

---

### Query 14: 冠军 vs 挑战者模型决策漂移

**业务背景:**
MLOps 团队把一个新"挑战者"模型对线上"冠军"做 A/B 测试。每笔交易大多被路由到冠军,但约 15% 流量被镜像到挑战者。他们想要每客户的两个模型 decline 率并排对比 — 如果挑战者 decline 显著多于 (或少于) 冠军,这就是推前需要的信号。

**类别:** CTE + 条件聚合 + Join
**难度:** 高级
**业务角色:** Analyst (分析师)

**解题思路:**
进阶条件聚合。CTE `scored` 把每个打分事件顺着 `ml_model → transaction → account → client_institution` 标上"客户"和"champion/challenger 角色";CTE `agg` 再按客户 × 角色算各决策计数。最后把同一客户的 champion 行和 challenger 行用自连接 (LEFT JOIN on `client_id`) 并排,算两者 decline 率之差。**关键是比率而非绝对数** — 两个模型的流量份额是 85/15,绝对计数没有可比性。`challenger_n` 很小的客户行要标注谨慎解读。

```sql
-- 每客户,分别拿到 champion 和 challenger 的各决策计数,再算 decline 率 gap。
-- 注意:流量份额不同 (~85/15),所以看 RATES (率) 而不是 raw counts (绝对数)。
WITH scored AS (
    SELECT
        ci.id              AS client_id,
        ci.legal_name      AS client,
        CASE WHEN m.is_champion = 1 THEN 'champion' ELSE 'challenger' END AS model_role,
        m.model_family,
        rd.code            AS decision
    FROM risk_score_event rse
    JOIN ml_model m            ON m.id  = rse.ml_model_id
    JOIN risk_decision_dim rd  ON rd.id = rse.decision_id
    JOIN "transaction" t       ON t.id  = rse.transaction_id
    JOIN account a             ON a.id  = t.source_account_id
    JOIN client_institution ci ON ci.id = a.client_institution_id
),
agg AS (
    SELECT
        client_id,
        client,
        model_role,
        COUNT(*)                                                    AS n,
        SUM(CASE WHEN decision = 'DECLINE' THEN 1 ELSE 0 END)       AS declines,
        SUM(CASE WHEN decision = 'REVIEW'  THEN 1 ELSE 0 END)       AS reviews,
        SUM(CASE WHEN decision = 'APPROVE' THEN 1 ELSE 0 END)       AS approves
    FROM scored
    GROUP BY client_id, client, model_role
)
SELECT
    ch.client,
    ch.n                                AS champion_n,
    cl.n                                AS challenger_n,
    ROUND(ch.declines * 1.0 / NULLIF(ch.n, 0), 4) AS champion_decline_rate,
    ROUND(cl.declines * 1.0 / NULLIF(cl.n, 0), 4) AS challenger_decline_rate,
    ROUND(
        (cl.declines * 1.0 / NULLIF(cl.n, 0)) -
        (ch.declines * 1.0 / NULLIF(ch.n, 0)),
        4
    )                                   AS decline_rate_gap
FROM (SELECT * FROM agg WHERE model_role = 'champion')   ch
LEFT JOIN (SELECT * FROM agg WHERE model_role = 'challenger') cl
       ON cl.client_id = ch.client_id
ORDER BY ABS(COALESCE(decline_rate_gap, 0)) DESC;
```

**预期结果说明:**
每客户一行。`decline_rate_gap` 正值意味着挑战者比冠军*更保守*;负值意味着更宽松。MLOps 团队关注绝对值 gap — 小 gap (例如 ±2pp) 推前是安全的;大 gap 标记一个值得调查的模型行为变化。一些客户的 `challenger_n` 在当前样本下可能很小 — 这些行需要审慎解读。

---

### Query 15: DECLINE 阻断金额 Top-10 账户

**业务背景:**
一位运营分析师需要美元金额上被 DECLINE 阻断最重的 10 个账户。这些要么是惯性欺诈受害者 (好事 — DECLINE 阻止了损失),要么是误报受害者 (坏事 — 银行需要在客户流失前修)。

**类别:** Aggregation + Sort
**难度:** 入门
**业务角色:** Operations (运营)

**解题思路:**
`transaction` join `risk_score_event` join `risk_decision_dim`,在 join 条件里直接写 `AND rd.code = 'DECLINE'` 只留被拒交易。再 join `account → end_user → client_institution` 拿账户主和客户名。按账户聚合 `SUM(amount_usd)`,降序取前 10。一个输出行 = 一个账户的被拒总额。结果既可能是惯性欺诈受害者 (好事,DECLINE 挡住了损失),也可能是误报受害者 (坏事,要在客户流失前修),需人工复核区分。

```sql
SELECT
    a.id                                  AS account_id,
    a.account_number_masked,
    eu.full_name,
    ci.legal_name                         AS client,
    COUNT(*)                              AS declined_txn_count,
    ROUND(SUM(t.amount_usd), 2)           AS declined_amount_usd
FROM "transaction" t
JOIN risk_score_event rse ON rse.transaction_id = t.id
JOIN risk_decision_dim rd ON rd.id = rse.decision_id AND rd.code = 'DECLINE'
JOIN account a   ON a.id = t.source_account_id
JOIN end_user eu ON eu.id = a.end_user_id
JOIN client_institution ci ON ci.id = a.client_institution_id
GROUP BY a.id, a.account_number_masked, eu.full_name, ci.legal_name
ORDER BY declined_amount_usd DESC
LIMIT 10;
```

**预期结果说明:**
被阻断最多的 10 个账户连同总 DECLINE 美元数。是分析师外联和误报审查的起点。

---

### Query 16: 每客户的真正 7 自然日滚动告警速率

**业务背景:**
反欺诈经理跑一个持续监控看板。对每个客户,过去 7 天滚动告警数 vs 上一周是多少? 突然 2 倍跳升标志着一波欺诈浪潮打到该银行。本查询必须在**连续 7 个自然日**上求和,而不是"上一个有至少一个告警的 7 天" — 后者会掩盖应该让趋势归零的安静日。

**类别:** 递归 CTE (日历) + Window Function
**难度:** 高级
**业务角色:** Analyst (分析师)

**解题思路:**
最硬的一题。关键陷阱:如果只对"有告警的天"做窗口,安静日会被整天跳过,7 日滚动和永远无法归零。解法是用递归 CTE (`WITH RECURSIVE calendar`) 生成 90 天完整日历,与所有客户 `CROSS JOIN` 造出"每客户 × 每一天"的网格,再 LEFT JOIN 实际告警并 `COALESCE(…, 0)` 把安静日填 0。这样 `SUM(…) OVER (PARTITION BY client ORDER BY day ROWS BETWEEN 6 PRECEDING AND CURRENT ROW)` 才等价于真正的 7 自然日滚动和。最后只显示最后 3 周保证看板可读。

```sql
-- 生成一份日历 (90 天),与所有客户做 cross join,再左连接告警,
-- 让安静日填上 0。这让 ROWS BETWEEN 6 PRECEDING 窗口等价于真正的
-- 7 自然日滚动求和 (包含 0 日)。
WITH RECURSIVE calendar(day) AS (
    SELECT DATE('2026-03-08')
    UNION ALL
    SELECT DATE(day, '+1 day') FROM calendar WHERE day < DATE('2026-06-05')
),
daily AS (
    SELECT
        ci.id                                AS client_id,
        ci.legal_name                        AS client,
        DATE(al.raised_at)                   AS day,
        COUNT(*)                             AS alert_count
    FROM alert al
    JOIN "transaction" t        ON t.id  = al.transaction_id
    JOIN account a              ON a.id  = t.source_account_id
    JOIN client_institution ci  ON ci.id = a.client_institution_id
    GROUP BY ci.id, ci.legal_name, DATE(al.raised_at)
),
filled AS (
    SELECT
        ci.id                                AS client_id,
        ci.legal_name                        AS client,
        c.day                                AS day,
        COALESCE(d.alert_count, 0)           AS alert_count
    FROM client_institution ci
    CROSS JOIN calendar c
    LEFT JOIN daily d
           ON d.client_id = ci.id AND d.day = c.day
)
SELECT
    client,
    day,
    alert_count,
    SUM(alert_count) OVER (
        PARTITION BY client
        ORDER BY day
        ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
    ) AS rolling_7d_alerts
FROM filled
WHERE day >= DATE('2026-05-15')   -- 最后 3 周以便看板可读
ORDER BY client, day;
```

**预期结果说明:**
每客户每日告警数加一个真正 7 自然日的尾部和。安静日明确显示为 0,因此 7 日和降到 0 明确意味着"过去一周完全没有告警" — 而不是"过去一周表里没有行"。

---

### Query 17: 使用 VPN 且国家与账户国家不同的 session

**业务背景:**
一位运营分析师在做模式狩猎,想要每个用户通过 VPN 登录、地理位置国家与账户登记国家不一致的 session。误报很多,但历史上是账户盗用的强信号。(`device_session` 不携带次国家级地理信息,所以我们在国家层面比较;真正的州级比较需要本数据集外的 IP→州 查询。)

**类别:** Join + Filter
**难度:** 中等
**业务角色:** Operations (运营)

**解题思路:**
`device_session` join `end_user`,过滤 `is_vpn = 1 AND geo_country <> eu.country`。一个输出行 = 一个可疑 session。注意只能在**国家粒度**比较 (表里没有州级 IP 地理),所以这是粗筛:误报多,但历史上 VPN + 地理不符是账户盗用的强信号。按 `session_started_at` 倒序取 50 条,供人工做 step-up auth 审查。

```sql
SELECT
    ds.id                                AS session_id,
    eu.full_name,
    eu.country                           AS account_country,
    ds.geo_country                       AS session_country,
    ds.ip_address,
    ds.session_started_at
FROM device_session ds
JOIN end_user eu ON eu.id = ds.end_user_id
WHERE ds.is_vpn = 1
  AND ds.geo_country <> eu.country
ORDER BY ds.session_started_at DESC
LIMIT 50;
```

**预期结果说明:**
最多 50 个使用了 VPN 且地理国家不匹配用户登记国家的 session。每一行都是 step-up auth 审查的候选。

---

### Query 18: 高优先级、开案超 14 天仍未关的案件

**业务背景:**
合规负责人想要任何 CRITICAL 或 HIGH 优先级、开案 14 天内未关闭的案件。这些会被升级到首席合规官手里。SLA 违约。

**类别:** Date Diff + Filter
**难度:** 中等
**业务角色:** Manager (经理)

**解题思路:**
`investigation_case` join 客户、案件状态、分析师三张维度/实体表。过滤三个条件:`priority IN ('HIGH','CRITICAL')` 且 `closed_at IS NULL` (仍未关) 且开案超过 14 天 (`JULIANDAY('2026-06-05') - JULIANDAY(opened_at) > 14`)。一个输出行 = 一个超期未关的高优案件,带上负责分析师名字方便直接呼叫。基准日写死字面量保证结果可复现。无需聚合。

```sql
SELECT
    ic.id                                                  AS case_id,
    ci.legal_name                                          AS client,
    cs.code                                                AS status,
    ic.priority,
    ic.opened_at,
    ROUND(JULIANDAY('2026-06-05') - JULIANDAY(ic.opened_at)) AS days_open,
    an.full_name                                           AS assigned_to,
    ic.total_exposure_usd
FROM investigation_case ic
JOIN client_institution ci ON ci.id = ic.client_institution_id
JOIN case_status_dim cs    ON cs.id = ic.case_status_id
JOIN analyst an            ON an.id = ic.assigned_analyst_id
WHERE ic.priority IN ('HIGH', 'CRITICAL')
  AND ic.closed_at IS NULL
  AND (JULIANDAY('2026-06-05') - JULIANDAY(ic.opened_at)) > 14
ORDER BY days_open DESC;
```

**预期结果说明:**
一份超期的高优先级案件简表。负责人 (analyst) 名字也列出来,方便呼叫。

---

### Query 19: 收入集中度 — top-3 客户份额

**业务背景:**
CFO 给董事会的问题:NovaRisk 的收入有多集中? 如果 3 个客户 = 50% ARR,那是严重的集中度风险。用 CTE 加窗口函数计算。

**类别:** CTE + Window Function
**难度:** 高级
**业务角色:** Finance (财务)

**解题思路:**
CTE + 窗口函数。先在 CTE `ranked` 里用 `SUM(…) OVER ()` (空窗口 = 全表) 算出 total ARR,同时 `RANK() OVER (ORDER BY ACV DESC)` 给客户排名。外层算每户占比,并用 `SUM(…) OVER (ORDER BY rk)` 做运行总和算出累计百分比。读累计列就能一眼看出 top-3 占了多少 — 本数据集约 41%,集中度偏高,需要在董事会材料里提示风险。`SUM() OVER ()` 和 `SUM() OVER (ORDER BY …)` 的区别 (全表 vs 运行总和) 是这题的考点。

```sql
WITH ranked AS (
    SELECT
        legal_name,
        annual_contract_value_usd,
        SUM(annual_contract_value_usd) OVER ()                                              AS total_arr,
        RANK() OVER (ORDER BY annual_contract_value_usd DESC)                               AS rk
    FROM client_institution
    WHERE is_active = 1
)
SELECT
    legal_name,
    annual_contract_value_usd,
    ROUND(annual_contract_value_usd * 100.0 / total_arr, 2) AS pct_of_total_arr,
    ROUND(SUM(annual_contract_value_usd) OVER (ORDER BY rk) * 100.0 / total_arr, 2)
                                                            AS cumulative_pct
FROM ranked
ORDER BY rk;
```

**预期结果说明:**
每客户在总 ARR 里的份额加累计百分比。用于识别集中度风险 — 本数据集 top-3 大约占 ARR 的 **41%** (Skyline National Bank + Meridian Card Services + EquatorPay)。

---

### Query 20: SAR 叙述中含 "structuring" 的模式搜索

**业务背景:**
一个审计团队在研究监管者关于 structuring (把存款切碎以躲避 $10K 上报阈值) 的执法备忘录。他们需要每一份叙述里提到 structuring 的 SAR。

**类别:** 模式匹配 (LIKE)
**难度:** 入门
**业务角色:** Operations (运营)

**解题思路:**
最简单的文本匹配题:`sar_report` 单表,`WHERE LOWER(narrative_summary) LIKE '%structuring%'`。`LOWER()` 保证大小写不敏感。用 `SUBSTR(narrative_summary, 1, 200)` 截取摘录避免输出过长。一个输出行 = 一份提到 structuring 的 SAR。审计团队用它在与监管面谈前收集先例。注意 `LIKE '%…%'` 两侧通配会走全表扫描,但本表只有 ~9 行,无性能问题。

```sql
SELECT
    sar.filing_reference,
    sar.filed_at,
    sar.total_reported_amount_usd,
    sar.ai_drafted,
    SUBSTR(sar.narrative_summary, 1, 200) AS narrative_excerpt
FROM sar_report sar
WHERE LOWER(sar.narrative_summary) LIKE '%structuring%'
ORDER BY sar.filed_at DESC;
```

**预期结果说明:**
所有叙述里含 "structuring" 的 SAR,带 200 字符摘录。审计在与监管者面谈前用它收集先例。

---

## 查询类别汇总

| 类别 | 数量 | 查询编号 |
|----------|-------|---------------|
| Aggregation | 4 | 2, 4, 13, 15 |
| Join Operations | 4 | 3, 8, 12, 17 |
| Window Functions | 4 | 1, 10, 16, 19 |
| Date/Time Analysis | 3 | 6, 9, 18 |
| Subqueries / CTEs | 4 | 7, 11, 14, 19 |
| Pattern / Text | 1 | 20 |

(总数 > 20 是因为部分查询同时归到多个类别 — 例如 Q19 既用了 CTE 也用了 window function。)

## 业务角色覆盖

| 角色 | 数量 | 查询编号 |
|------|-------|---------------|
| Executive (高管) | 2 | 2, 8 |
| Manager (经理) | 5 | 3, 5, 6, 10, 18 |
| Analyst (分析师) | 6 | 4, 7, 9, 11, 14, 16 |
| Operations (运营) | 5 | 1, 12, 15, 17, 20 |
| Finance (财务) | 2 | 13, 19 |

## 难度分布

| 难度 | 数量 | 查询编号 |
|------------|-------|---------------|
| 入门 | 7 | 2, 3, 4, 8, 13, 15, 20 |
| 中等 | 8 | 1, 5, 6, 9, 10, 12, 17, 18 |
| 高级 | 5 | 7, 11, 14, 16, 19 |

---

## 注意事项

- 所有查询都已对打包的 SQLite 数据库 (`fintech_real_time_fraud_aml_platform_high.sqlite`) 验证过。
- `transaction` 表必须始终加双引号 (`"transaction"`),因为它是 SQLite 保留字。
- **Postgres / 严格 SQL 可移植性**: SELECT 中的每一个非聚合列也都出现在 GROUP BY 里 (SQLite 在这里宽容,Postgres 不宽容)。其他可移植性修改:`JULIANDAY()` → `EXTRACT(EPOCH FROM ...)` 或 `AGE()`,布尔字面量 (`1`/`0` → `TRUE`/`FALSE`),以及 `DATE(col, '+1 day')` → `col + INTERVAL '1 day'`。
