# 云服务商客户成功管理 SQL 查询参考

> **业务背景与术语表:** `01-cloud_provider_customer_success_medium_business_context-cn.md`
> **数据结构 (ER):** `02-cloud_provider_customer_success_medium_er_document-cn.md`
> **数据库文件:** `cloud_provider_customer_success_medium.sqlite`
> **所有查询兼容 SQLite 3.x**。参考"今天" (REFERENCE_DATE) = `2026-06-20`。
> **虚构公司:** NimbusScale, Inc. (中端云基础设施服务商, PaaS + AI/ML 推理)

---

## 1. 概述

本文档提供 20 个面向业务的 SQL 查询, 针对 `cloud_provider_customer_success_medium` 数据集设计。每个查询都解决 NimbusScale 内部利益相关方 (CSM, 销售高管, 分析师, CFO) 可能提出的实际问题, 适用于 AI Agent + Text to SQL 项目展示。

查询按两个互补维度组织。一是按 5 大业务主题 (见下方业务主题地图), 回答"这个数据集能学到什么"。二是按 20 条顺序编号 (见查询索引和查询详情), 作为标准参考顺序。

---

## 2. 如何使用本文档

本文档是为 NimbusScale 客户成功运营团队的新实习生写的。假设你已经读过 `01` 业务背景文档 (知道公司, tier, 健康度, 续约这些概念) 和 `02` ER 文档 (知道有哪些表, 字段, 外键), 经理现在把这份查询集交给你, 说"这周把这些题做一遍"。

每条查询都按固定的五段式组织, 照着读就能学会一个真实分析师怎么思考一道题:

1. **业务背景** 交代谁在问, 为什么现在问, 答案要支撑什么决策。
2. **分类 / 难度 / 业务角色** 三个标签, 让你一眼看出这道题练的是什么 SQL 技巧, 难到什么程度, 服务于哪个岗位。
3. **解题思路** 在你看到 SQL 之前, 先讲清楚要碰哪些表, 连接怎么搭, 聚合的粒度是什么, 为什么用 CTE 或窗口函数, 有哪些坑 (扇出, 除零, NULL 语义) 要避开。
4. **SQL 代码** 可直接在 SQLite 数据库上运行的查询本体。
5. **预期结果与业务结论** 结果长什么样, 关键数值大概在什么量级, 以及拿到数后分析师下一步该做什么。

两条贯穿全文的约定。其一, 数据集锚定在固定的 `REFERENCE_DATE = 2026-06-20`, 凡是需要"今天"的地方都应理解为这一天, 保证结果可复现 (生成器内部以运行日为锚点, 各 tier 的量级保持一致)。其二, 每条查询都能追溯到 `01` 业务背景里列出的某个业务问题, SQL 是用来读和学的, 不只是拿来跑的。

---

## 3. 业务术语表

下面的术语贯穿所有查询。Text-to-SQL Agent 应把这张表视为业务语言与数据集列名之间的标准映射:

| 术语 | 定义 | 在本数据集中的实现 |
|------|------|--------------------|
| **CSM** | Customer Success Manager — 客户成功经理,负责客户健康度、续约、扩容 | `csm` 表; `customer.csm_id` FK |
| **Tier** | 账户级别 (`Enterprise` / `Business` / `Pro` / `Basic`) | `account_tier` 表; `customer.account_tier_id` |
| **Tier specialization** | CSM 有资质服务的客户级别 | `csm.tier_specialization` ∈ {Enterprise, Mid-Market, SMB} |
| **活跃客户** | 至少有一份订阅不处于 {churned, expired} | `customer.is_active = 1` (派生字段) |
| **健康度评分** | 综合 0-100 分,越低流失风险越高 | `health_score.overall_score` = 0.4·usage + 0.3·engagement + 0.3·support |
| **健康度基线** (内部) | 客户的隐含"健康倾向",驱动工单数和子分 | 不持久化;影响 `support_tickets_count` 和子分 |
| **低健康度** | 客户需要干预 | `overall_score < 60` |
| **流失风险** | 综合风险标识 | 低健康度 OR 用量下降 OR 待续约 — 见 Q12 |
| **QBR** | Quarterly Business Review (正式的季度业务回顾会议) | `interaction_log` 中 `interaction_type.name = 'QBR Meeting'` |
| **承诺消费** | 合同月度最低消费 | `subscription.monthly_committed_spend` |
| **实际消费** | 基于实际使用量的真实消费 | `usage_metrics.total_spend` (compute + storage + network + ai_ml) |
| **超额 (Overage)** | 实际消费超出承诺 | `actual - committed > 0` |
| **待续约 (Pending Renewal)** | 合同即将到期,续约决策尚未敲定 | `subscription.status = 'pending_renewal'` |
| **流失 (Churn)** | 客户提前终止订阅 | `subscription.status = 'churned'` |
| **扩容机会** | 健康的客户 + 持续用量增长 — upsell 目标 | 高健康度 + 正增长趋势 (见 Q15 逻辑) |
| **AI/ML 用户** | 最新月份消费 AI/ML 服务的客户 | 该客户最新 `month_year` 行的 `usage_metrics.ai_ml_spend > 0` |
| **最新评分 (per-customer MAX)** | 每个客户自己的最新健康度快照 | correlated subquery: `score_date = (SELECT MAX(score_date) FROM health_score WHERE customer_id = hs.customer_id)` |

---

## 4. 业务主题地图

20 条查询聚类成 5 个主题,对应 NimbusScale CSM 团队的实际工作活动:

### 🩺 客户健康监测 (Customer Health Monitoring)

验证支持工单 ↔ 健康度的负相关性、追踪整个客户群的 AI/ML 采用率、监控客户互动的情绪趋势。

| 查询 | 标题 | 难度 |
|------|------|------|
| Q11 | AI/ML 服务采用率 | 基础 |
| Q14 | 支持工单与健康度关联 | 中级 |
| Q18 | 客户情绪趋势分析 | 中级 |

### 🔄 续约风险管理 (Renewal Risk Management)

识别续约风险客户 (低健康度 + 合同临近到期)、生成流失风险报告、盘点 30/60/90 天内到期合同、追踪 QBR 完成情况作为续约就绪信号。

| 查询 | 标题 | 难度 |
|------|------|------|
| Q3 | 即将续约的低健康度客户 | 中级 |
| Q12 | 流失风险客户识别 | 高级 |
| Q17 | 合同即将到期提醒 | 基础 |
| Q19 | 季度 QBR 完成情况 | 中级 |

### 📈 扩容机会识别 (Expansion Opportunity)

追踪每客户消费趋势,识别健康且持续增长的客户作为 upsell 候选。

| 查询 | 标题 | 难度 |
|------|------|------|
| Q4 | 客户月度消费趋势 | 中级 |
| Q15 | 扩容机会识别 | 高级 |

### 👥 CSM 团队运营 (CSM Team Operations)

运营经理和 CSM 团队 lead 使用的运营类查询 — 任务吞吐、工作队列、工作负载均衡。

| 查询 | 标题 | 难度 |
|------|------|------|
| Q6 | CSM 任务完成率 | 基础 |
| Q9 | 高优先级未完成任务 | 基础 |
| Q16 | CSM 工作负载分布 | 中级 |

### 📊 客户分析与高层汇报 (Portfolio Analytics & Executive Reporting)

C 级 / 分析师 / 财务 / 客户 360 类查询。包含 CSM 客户会议前使用的客户全景视图。

| 查询 | 标题 | 难度 |
|------|------|------|
| Q1 | 各级别客户数量分布 | 基础 |
| Q2 | 用量下降超过 20% 的客户 | 高级 |
| Q5 | 各区域客户消费排行 | 中级 |
| Q7 | 健康度评分变化最大的客户 | 高级 |
| Q8 | 企业级客户平均消费分析 | 中级 |
| Q10 | 客户交互频率分析 | 中级 |
| Q13 | 各行业客户分布及消费 | 基础 |
| Q20 | 客户全景视图 | 高级 |

---

## 5. 查询索引

| 编号 | 标题 | 业务角色 | 分类 | 难度 |
|------|------|----------|------|------|
| 1 | 各级别客户数量分布 | 高管 | 聚合 | 基础 |
| 2 | 用量下降超过20%的客户 | CSM经理 | 窗口函数 | 高级 |
| 3 | 即将续约的低健康度客户 | CSM经理 | 连接 | 中级 |
| 4 | 客户月度消费趋势 | 分析师 | 窗口函数 | 中级 |
| 5 | 各区域客户消费排行 | 高管 | 聚合+连接 | 中级 |
| 6 | CSM 任务完成率 | 运营 | 聚合 | 基础 |
| 7 | 健康度评分变化最大的客户 | CSM经理 | 窗口函数 | 高级 |
| 8 | 企业级客户平均消费分析 | 财务 | CTE+聚合 | 中级 |
| 9 | 高优先级未完成任务 | 运营 | 连接 | 基础 |
| 10 | 客户交互频率分析 | 分析师 | 聚合+日期 | 中级 |
| 11 | AI/ML 服务采用率 | 高管 | CTE+聚合 | 基础 |
| 12 | 流失风险客户识别 | CSM经理 | CTE+连接 | 高级 |
| 13 | 各行业客户分布及消费 | 分析师 | 聚合 | 基础 |
| 14 | 支持工单与健康度关联 | 分析师 | CTE+聚合 | 中级 |
| 15 | 扩容机会识别 | CSM经理 | CTE+窗口 | 高级 |
| 16 | CSM 工作负载分布 | 运营 | CTE+连接 | 中级 |
| 17 | 合同即将到期提醒 | 运营 | 日期范围 | 基础 |
| 18 | 客户情绪趋势分析 | 分析师 | 聚合+日期 | 中级 |
| 19 | 季度 QBR 完成情况 | 运营 | 连接+日期 | 中级 |
| 20 | 客户全景视图 | CSM | CTE+多表连接 | 高级 |

---

## 6. 查询详情

### 查询 1: 各级别客户数量分布

**业务背景:**
销售副总裁在季度业务回顾会议上需要了解当前客户组合的构成。他想知道不同级别(Enterprise、Business、Pro、Basic)的客户数量和占比,以评估是否需要调整客户获取策略,或者加强对某个级别客户的升级转化。

**分类:** 聚合查询
**难度:** 基础
**业务角色:** 高管/C级

**解题思路:**
这道题只需要 customer 和 account_tier 两张表。按 tier 做一次 GROUP BY 数客户, 再用窗口函数 `SUM(COUNT(c.id)) OVER()` 在同一次聚合里拿到全体总数来算占比, 省掉一个额外的子查询。`WHERE c.is_active = 1` 把订阅已全部 churned/expired 的客户排除, 让"组合构成"反映当前还在服务的盘子。按 `account_tier.monthly_min_spend` 降序排, Enterprise 自然排在最前。不需要 CTE 或窗口分区, 一次聚合就够。

```sql
SELECT
    t.name AS tier_name,
    COUNT(c.id) AS customer_count,
    ROUND(COUNT(c.id) * 100.0 / SUM(COUNT(c.id)) OVER(), 2) AS percentage
FROM customer c
JOIN account_tier t ON c.account_tier_id = t.id
WHERE c.is_active = 1
GROUP BY t.id, t.name
ORDER BY t.monthly_min_spend DESC;
```

**预期结果说明:**
返回 4 行,显示每个账户级别的活跃客户数量。Enterprise 约 15%、Business 约 30%、Pro 约 35%、Basic 约 20%。少量客户因订阅全部 churned 会被 `is_active=0` 过滤。

业务结论: 这是季度回顾的开场图。若某个高价值 tier 占比明显低于目标, 销售副总裁会据此决定是加码该 tier 的获取, 还是推动低 tier 客户向上升级。

---

### 查询 2: 用量下降超过20%的客户

**业务背景:**
CSM 团队负责人每周一早会需要识别上周用量显著下降的客户。用量下降往往是客户流失的先兆信号。他需要快速获取"上月相比上上月用量下降超过20%"的客户列表,以便分配团队优先跟进。

**分类:** 窗口函数
**难度:** 高级
**业务角色:** CSM经理

**解题思路:**
核心是同一客户相邻月份的环比, 用 `LAG(total_spend) OVER (PARTITION BY customer_id ORDER BY month_year)` 取上月值。`PARTITION BY customer_id` 不能省, 否则窗口会跨客户串味, 把别人上月的消费当成自己的。先在 CTE 里把 `prev_month_spend` 算好, 外层再 JOIN customer / csm / account_tier 补上名字和 tier。过滤时用 `NULLIF(prev, 0)` 防止首月或零消费导致除零, 并要求降幅小于 -0.20。每个客户的首月 prev 为 NULL, 会被 WHERE 自然排除。

```sql
WITH monthly_changes AS (
    SELECT
        customer_id,
        month_year,
        total_spend,
        LAG(total_spend) OVER (PARTITION BY customer_id ORDER BY month_year) AS prev_month_spend
    FROM usage_metrics
)
SELECT
    c.id AS customer_id,
    c.company_name,
    csm.name AS csm_name,
    t.name AS tier,
    mc.month_year,
    ROUND(mc.prev_month_spend, 2) AS prev_spend,
    ROUND(mc.total_spend, 2) AS current_spend,
    ROUND((mc.total_spend - mc.prev_month_spend) / NULLIF(mc.prev_month_spend, 0) * 100, 2) AS change_pct
FROM monthly_changes mc
JOIN customer c ON mc.customer_id = c.id
JOIN csm ON c.csm_id = csm.id
JOIN account_tier t ON c.account_tier_id = t.id
WHERE mc.prev_month_spend IS NOT NULL
  AND mc.prev_month_spend > 0
  AND (mc.total_spend - mc.prev_month_spend) / NULLIF(mc.prev_month_spend, 0) < -0.20
ORDER BY change_pct ASC
LIMIT 20;
```

**预期结果说明:**
返回用量下降最严重的客户,按下降百分比排序。例如某客户上月消费 $50,000,本月只有 $35,000(下降 30%),需要立即关注。`NULLIF` 保护避免除零导致 NULL 而非异常。

---

### 查询 3: 即将续约的低健康度客户

**业务背景:**
每月月初,客户成功总监需要识别"90 天内合同到期且健康度低于 60 分"的客户。这些客户续约风险极高,需要立即安排高管拜访或制定挽留方案。

**分类:** 连接查询
**难度:** 中级
**业务角色:** CSM经理

**解题思路:**
要把"合同到期窗口"和"每个客户自己的最新健康度"两件事对齐。subscription 提供 pending_renewal 状态和到期日, health_score 提供分数。难点在于一个客户有多张健康度快照, 必须用相关子查询 `hs.score_date = (SELECT MAX(score_date) ... WHERE customer_id = c.id)` 只取它自己的最新一张, 否则旧快照也会被算进来, 造成重复或误判。三个过滤条件 (pending_renewal, 90 天窗口, 最新分 < 60) 缺一不可, 共同锁定真正高危的续约客户。

```sql
SELECT
    c.id AS customer_id,
    c.company_name,
    csm.name AS csm_name,
    t.name AS tier,
    s.contract_end_date,
    JULIANDAY(s.contract_end_date) - JULIANDAY('now') AS days_to_renewal,
    s.monthly_committed_spend,
    hs.overall_score AS health_score,
    hs.notes AS health_notes
FROM customer c
JOIN subscription s ON c.id = s.customer_id
JOIN csm ON c.csm_id = csm.id
JOIN account_tier t ON c.account_tier_id = t.id
JOIN health_score hs ON c.id = hs.customer_id
WHERE s.status = 'pending_renewal'
  AND s.contract_end_date BETWEEN DATE('now') AND DATE('now', '+90 days')
  AND hs.score_date = (SELECT MAX(score_date) FROM health_score WHERE customer_id = c.id)
  AND hs.overall_score < 60
ORDER BY s.contract_end_date ASC, hs.overall_score ASC;
```

**预期结果说明:**
返回 90 天内到期、且最新健康度低于 60 分的 pending_renewal 客户, 按到期日和分数升序排列。每个客户取其自身的最新评分 (per-customer MAX), 通常只有少量客户同时命中三个条件。

业务结论: 这份名单就是客户成功总监本月的"抢救清单"。最靠前的几家应立即安排高管拜访或定制挽留方案, days_to_renewal 越小越紧急。

---

### 查询 4: 客户月度消费趋势

**业务背景:**
财务分析师在准备季度收入预测时,需要了解特定大客户过去 6 个月的消费趋势。他想看到每月消费及环比增长率,以判断收入是否稳定或有下滑风险,并据此调整收入预测模型。

**分类:** 窗口函数
**难度:** 中级
**业务角色:** 分析师

**解题思路:**
这是单客户的时间序列分析, 用 `LAG(total_spend)` 算环比增长。因为 WHERE 已经把范围限定到一个客户 (`c.id = 51`), 窗口里其实只有一个分区, 但仍要 `PARTITION BY c.id` 加 `ORDER BY month_year` 来保证按月正确取上一行。把 compute / storage / ai_ml / total 都列出来, 方便看清是哪一块在涨或在掉。`NULLIF` 保护首月除零。换分析对象只需改 WHERE 里的客户 id。

```sql
SELECT
    c.company_name,
    um.month_year,
    ROUND(um.compute_spend, 2) AS compute,
    ROUND(um.storage_spend, 2) AS storage,
    ROUND(um.ai_ml_spend, 2) AS ai_ml,
    ROUND(um.total_spend, 2) AS total,
    ROUND(
        (um.total_spend - LAG(um.total_spend) OVER (PARTITION BY c.id ORDER BY um.month_year))
        / NULLIF(LAG(um.total_spend) OVER (PARTITION BY c.id ORDER BY um.month_year), 0) * 100,
    2) AS mom_growth_pct
FROM usage_metrics um
JOIN customer c ON um.customer_id = c.id
WHERE c.id = 51  -- 可替换为任意客户ID (示例: 一个 Enterprise 客户)
ORDER BY um.month_year;
```

**预期结果说明:**
返回指定客户 6 个月(或不足 6 个月,视 created_at)的消费明细及环比增长率。NULLIF 保护首月除零。

业务结论: 财务分析师据此判断这家大客户的收入是稳是降。若 mom_growth_pct 连续为负, 应在收入预测里下调该客户, 并提示 CSM 介入。

---

### 查询 5: 各区域客户消费排行

**业务背景:**
区域销售总监在制定下季度销售目标时,需要了解各 AWS 区域近 6 个月的客户数量和总消费额。这有助于识别高增长区域(如亚太区)和需要加强的区域,合理分配销售资源和市场投入。

**分类:** 聚合+连接
**难度:** 中级
**业务角色:** 高管

**解题思路:**
region → customer → usage_metrics 是两层一对多。按 region 聚合时, 客户数必须用 `COUNT(DISTINCT c.id)`, 否则 usage_metrics 的多月行会把同一个客户数六遍, 让客户数虚高。WHERE 限制近 6 个月且 is_active, 保证排行反映的是当前活跃盘子的近期消费。注意本月新建、还没有 usage 行的客户会被 INNER JOIN 自然剔除, 这是符合业务的 (新客户暂无可分析历史)。

```sql
SELECT
    r.code AS region_code,
    r.name AS region_name,
    r.continent,
    COUNT(DISTINCT c.id) AS customer_count,
    ROUND(SUM(um.total_spend), 2) AS total_spend_6m,
    ROUND(AVG(um.total_spend), 2) AS avg_monthly_spend_per_record
FROM region r
JOIN customer c ON r.id = c.primary_region_id
JOIN usage_metrics um ON c.id = um.customer_id
WHERE c.is_active = 1
  AND um.month_year >= DATE('now', '-6 months', 'start of month')
GROUP BY r.id, r.code, r.name, r.continent
ORDER BY total_spend_6m DESC;
```

**预期结果说明:**
返回各区域近 6 个月的客户数和消费汇总。us-east-1 通常客户数最多;亚太区可能增长快。

业务结论: 区域销售总监据此分配下季度的销售与市场资源, 把人力倾斜到客户数少但消费增长快的区域。

---

### 查询 6: CSM 任务完成率

**业务背景:**
运营经理每周需要向 VP 汇报 CSM 团队的任务完成情况。他需要统计各状态(open、in_progress、completed、cancelled)的任务数量和完成率,以评估团队执行力和工作负载是否合理。

**分类:** 聚合查询
**难度:** 基础
**业务角色:** 运营

**解题思路:**
最朴素的单表聚合。csm_task 按 status 分组计数, 再用 `SUM(COUNT(*)) OVER()` 算各状态占比。ORDER BY 里的 CASE 是为了让结果按业务关心的顺序 (completed → in_progress → open → cancelled) 排列, 而不是字母序。不涉及任何 JOIN, 适合熟悉"聚合 + 窗口比例"的写法。

```sql
SELECT
    status,
    COUNT(*) AS task_count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 2) AS percentage
FROM csm_task
GROUP BY status
ORDER BY
    CASE status
        WHEN 'completed' THEN 1
        WHEN 'in_progress' THEN 2
        WHEN 'open' THEN 3
        WHEN 'cancelled' THEN 4
    END;
```

**预期结果说明:**
返回 4 行。理想情况下 completed 应占 40%+;若 open/in_progress 堆积过多,说明可能需要扩团。

---

### 查询 7: 健康度评分变化最大的客户

**业务背景:**
每周例会上,CSM 团队需要识别健康度变化最大的客户。健康度大幅下降的客户需要紧急干预;健康度大幅上升的客户可能有扩容机会。

**分类:** 窗口函数
**难度:** 高级
**业务角色:** CSM经理

**解题思路:**
和 Q2 同构, 只是把 total_spend 换成 overall_score, 衡量的是健康度而非消费。CTE 里用 `LAG(overall_score)` 取每个客户上一次快照的分数, 外层按 `ABS(变化)` 降序取 Top 15。这里要的是绝对变化, 因为大涨 (扩容信号) 和大跌 (流失信号) 都值得关注。`PARTITION BY customer_id` 不能省, 首条快照 prev_score 为 NULL 要过滤掉。

```sql
WITH score_changes AS (
    SELECT
        customer_id,
        score_date,
        overall_score,
        LAG(overall_score) OVER (PARTITION BY customer_id ORDER BY score_date) AS prev_score
    FROM health_score
)
SELECT
    c.id AS customer_id,
    c.company_name,
    csm.name AS csm_name,
    t.name AS tier,
    sc.score_date,
    sc.prev_score,
    sc.overall_score AS current_score,
    sc.overall_score - sc.prev_score AS score_change
FROM score_changes sc
JOIN customer c ON sc.customer_id = c.id
JOIN csm ON c.csm_id = csm.id
JOIN account_tier t ON c.account_tier_id = t.id
WHERE sc.prev_score IS NOT NULL
ORDER BY ABS(sc.overall_score - sc.prev_score) DESC
LIMIT 15;
```

**预期结果说明:**
返回相邻两次快照之间健康度变化幅度最大的 15 个客户 (含 score_change 的正负)。大跌的排查流失原因, 大涨的留意扩容窗口。

业务结论: 在每周例会上, CSM 经理用这张表分流: score_change 大幅为负的客户当周安排干预, 大幅为正的客户转给销售评估 upsell。

---

### 查询 8: 企业级客户平均消费分析

**业务背景:**
财务总监准备董事会汇报时,需要了解企业级客户(最高价值客户群)的实际消费 vs 承诺消费。

**分类:** CTE+聚合
**难度:** 中级
**业务角色:** 财务

**解题思路:**
最大的坑是 subscription 和 usage_metrics 都是一对多, 直接 JOIN 会产生 subscription × usage 的笛卡尔扇出, 把消费算翻倍。正确做法是两边各自先在 CTE 里聚合到客户粒度: usage 取 AVG 得平均实际消费, subscription 对 active 合同取 SUM 得总承诺消费, 再按 customer_id 对齐。分母用 SUM 而非 MAX, 因为一个客户可能有多份 active 合同, 而实际消费覆盖的是它全部服务。最后只留 Enterprise 且 active 的客户。

```sql
WITH usage_summary AS (
    SELECT customer_id,
           AVG(total_spend) AS avg_actual_spend,
           COUNT(*) AS months_data
    FROM usage_metrics
    GROUP BY customer_id
),
active_sub AS (
    -- 客户可能有多份 active 订阅,SUM 聚合得到该客户在所有合同上的总承诺消费
    -- (avg_actual_spend 来自 usage_metrics 已覆盖客户全部服务,因此分母必须用 SUM 而非 MAX)
    SELECT customer_id,
           SUM(monthly_committed_spend) AS committed
    FROM subscription
    WHERE status = 'active'
    GROUP BY customer_id
)
SELECT
    c.company_name,
    ROUND(asub.committed, 2) AS committed,
    ROUND(us.avg_actual_spend, 2) AS avg_actual_spend,
    ROUND(us.avg_actual_spend - asub.committed, 2) AS overage,
    ROUND((us.avg_actual_spend / NULLIF(asub.committed, 0) - 1) * 100, 2) AS overage_pct,
    us.months_data
FROM customer c
JOIN account_tier t ON c.account_tier_id = t.id
JOIN usage_summary us ON c.id = us.customer_id
JOIN active_sub asub ON c.id = asub.customer_id
WHERE t.name = 'Enterprise'
  AND c.is_active = 1
ORDER BY avg_actual_spend DESC;
```

**预期结果说明:**
每个 Enterprise 客户输出一行(在 CTE 中各侧先聚合,避免 subscription × usage_metrics 扇出);overage_pct 为正表示实际超出承诺。

---

### 查询 9: 高优先级未完成任务

**业务背景:**
每天早上,CSM 团队 lead 需要检查哪些高优先级或关键优先级任务仍未完成。这些任务通常涉及重要客户的紧急事项,延误可能导致客户流失或投诉升级。

**分类:** 连接查询
**难度:** 基础
**业务角色:** 运营

**解题思路:**
一个直白的工作队列查询。csm_task 关联 customer 和 csm 取出名字, 过滤 `priority IN ('high','critical')` 且 `status IN ('open','in_progress')`。排序用 CASE 把 critical 顶到最前, 再按 due_date 升序, 让最该今天处理的任务排在最上面。`days_until_due` 为负即代表已逾期, 是给团队 lead 的红色警报。

```sql
SELECT
    task.id AS task_id,
    c.company_name,
    csm.name AS csm_name,
    task.task_type,
    task.title,
    task.priority,
    task.status,
    task.due_date,
    JULIANDAY(task.due_date) - JULIANDAY('now') AS days_until_due
FROM csm_task task
JOIN customer c ON task.customer_id = c.id
JOIN csm ON c.csm_id = csm.id
WHERE task.priority IN ('high', 'critical')
  AND task.status IN ('open', 'in_progress')
ORDER BY
    CASE task.priority WHEN 'critical' THEN 1 ELSE 2 END,
    task.due_date ASC;
```

**预期结果说明:**
返回所有高/关键优先级的未完成任务,按紧急程度和截止日期排序。days_until_due 为负表示已逾期。

---

### 查询 10: 客户交互频率分析

**业务背景:**
客户成功运营分析师在评估团队效率时,需要了解与各客户的交互频率。交互过少可能导致客户感觉被忽视;交互过多可能说明客户问题较多。

**分类:** 聚合+日期
**难度:** 中级
**业务角色:** 分析师

**解题思路:**
关键技巧是把"近 90 天"这个日期条件放在 `LEFT JOIN ... ON` 里, 而不是 WHERE 里。这样近 90 天没有任何交互的客户也能保留, 交互数显示为 0, 而不是被过滤消失。按客户聚合交互次数、正负情绪计数和最后交互时间。如果把日期条件挪到 WHERE, 沉默客户会整行消失, 而沉默客户恰恰最需要被看见, 所以这里 LEFT JOIN 与条件位置都是有意为之。

```sql
SELECT
    c.company_name,
    t.name AS tier,
    COUNT(il.id) AS interaction_count,
    ROUND(COUNT(il.id) * 30.0 / 90, 2) AS monthly_avg,
    SUM(CASE WHEN il.sentiment = 'positive' THEN 1 ELSE 0 END) AS positive_count,
    SUM(CASE WHEN il.sentiment = 'negative' THEN 1 ELSE 0 END) AS negative_count,
    MAX(il.interaction_date) AS last_interaction
FROM customer c
JOIN account_tier t ON c.account_tier_id = t.id
LEFT JOIN interaction_log il ON c.id = il.customer_id
    AND il.interaction_date >= DATE('now', '-90 days')
WHERE c.is_active = 1
GROUP BY c.id, c.company_name, t.name
ORDER BY interaction_count DESC;
```

**预期结果说明:**
返回各活跃客户近 90 天的交互统计。Enterprise 通常月均 3-5 次。

业务结论: interaction_count 接近 0 的高价值客户是"被冷落"信号, CS 运营分析师应提醒对应 CSM 主动触达; negative_count 偏高的客户则要排查满意度问题。

---

### 查询 11: AI/ML 服务采用率

**业务背景:**
产品副总裁想了解 AI/ML 服务在客户群中的渗透率,以评估 AI 产品市场接受度并识别尚未采用 AI 服务的潜力客户。

**分类:** CTE+聚合
**难度:** 基础
**业务角色:** 高管

**解题思路:**
先在 CTE 里用相关子查询 `month_year = (SELECT MAX(month_year) ... WHERE customer_id = um.customer_id)` 取每个客户自己最新一个月的 usage 行, 并当场用 CASE 打上"AI/ML 用户 / 非用户"标签 (`ai_ml_spend > 0`)。外层只需对这个标签 GROUP BY 分两组聚合。提前在 CTE 里打好标签, 是让外层聚合保持干净的常用手法, 避免在 GROUP BY 里堆 CASE。

```sql
WITH latest_usage AS (
    -- per-customer MAX: 取每个客户自己最新的 usage 月
    SELECT
        um.customer_id,
        um.total_spend,
        um.ai_ml_spend,
        CASE WHEN um.ai_ml_spend > 0 THEN 'AI/ML 用户' ELSE '非AI/ML用户' END AS segment
    FROM usage_metrics um
    WHERE um.month_year = (
        SELECT MAX(month_year) FROM usage_metrics WHERE customer_id = um.customer_id
    )
)
SELECT
    segment,
    COUNT(DISTINCT customer_id) AS customer_count,
    ROUND(AVG(total_spend), 2) AS avg_total_spend,
    ROUND(AVG(ai_ml_spend), 2) AS avg_ai_ml_spend
FROM latest_usage
GROUP BY segment
ORDER BY customer_count DESC;
```

**预期结果说明:**
返回 2 行: "AI/ML 用户" 与 "非AI/ML用户"。前者约 60%(生成器配置),且 avg_total_spend 通常更高,印证交叉销售价值。

---

### 查询 12: 流失风险客户识别

**业务背景:**
客户成功总监每月底需要生成"流失风险报告"。报告综合多个信号:健康度低、用量下降、支持工单多、即将续约,识别最可能流失的客户。

**分类:** CTE+连接
**难度:** 高级
**业务角色:** CSM经理

**解题思路:**
这是把三路信号汇总的旗舰查询。三个 CTE 各管一块, 都先聚合到客户粒度: latest_health 取每客户最新综合分, usage_trend 取近 3 个月的消费与平均工单, pending_renewals 取最近的待续约到期日。三者用 LEFT JOIN 拼回 customer (LEFT 是因为不是每个客户三种信号都齐全, INNER 会漏人)。再用一层嵌套 CASE 按阈值打 Critical / High / Medium / Low。WHERE 先做粗筛 (健康 < 70 或有待续约) 缩小范围, ORDER BY 重复同样的 CASE 逻辑保证最危险的排最前。

```sql
WITH latest_health AS (
    -- per-customer 最新评分 (correlated subquery, 同客户取其自身的 MAX(score_date))
    SELECT hs.customer_id, hs.overall_score
    FROM health_score hs
    WHERE hs.score_date = (
        SELECT MAX(score_date) FROM health_score WHERE customer_id = hs.customer_id
    )
),
usage_trend AS (
    SELECT
        customer_id,
        SUM(total_spend) AS recent_spend,
        AVG(support_tickets_count) AS avg_tickets
    FROM usage_metrics
    WHERE month_year >= DATE('now', '-3 months', 'start of month')
    GROUP BY customer_id
),
pending_renewals AS (
    SELECT customer_id, MIN(contract_end_date) AS renewal_date
    FROM subscription
    WHERE status = 'pending_renewal'
    GROUP BY customer_id
)
SELECT
    c.id AS customer_id,
    c.company_name,
    t.name AS tier,
    csm.name AS csm_name,
    lh.overall_score AS health_score,
    ROUND(ut.recent_spend, 2) AS recent_3m_spend,
    ROUND(ut.avg_tickets, 1) AS avg_monthly_tickets,
    pr.renewal_date,
    CASE
        WHEN lh.overall_score < 50 AND ut.avg_tickets > 5 AND pr.renewal_date IS NOT NULL THEN 'Critical'
        WHEN lh.overall_score < 60 AND (ut.avg_tickets > 3 OR pr.renewal_date IS NOT NULL) THEN 'High'
        WHEN lh.overall_score < 70 THEN 'Medium'
        ELSE 'Low'
    END AS risk_level
FROM customer c
JOIN account_tier t ON c.account_tier_id = t.id
JOIN csm ON c.csm_id = csm.id
LEFT JOIN latest_health lh ON c.id = lh.customer_id
LEFT JOIN usage_trend ut ON c.id = ut.customer_id
LEFT JOIN pending_renewals pr ON c.id = pr.customer_id
WHERE c.is_active = 1
  AND (lh.overall_score < 70 OR pr.renewal_date IS NOT NULL)
ORDER BY
    CASE
        WHEN lh.overall_score < 50 AND ut.avg_tickets > 5 AND pr.renewal_date IS NOT NULL THEN 1
        WHEN lh.overall_score < 60 THEN 2
        ELSE 3
    END,
    lh.overall_score ASC;
```

**预期结果说明:**
所有有流失风险的活跃客户,按风险等级排序。Critical 立即拜访,High 本周跟进。

---

### 查询 13: 各行业客户分布及消费

**业务背景:**
市场战略分析师在准备年度市场报告时,需要了解客户的行业分布。哪些行业客户最多?哪些行业消费最高?

**分类:** 聚合查询
**难度:** 基础
**业务角色:** 分析师

**解题思路:**
和 Q5 同构, 只是把分组键从 region 换成 industry。customer JOIN usage_metrics 后按行业聚合, 客户数用 `COUNT(DISTINCT c.id)` 去重避免多月行放大。`ai_ml_pct` 用 `SUM(ai_ml_spend) / SUM(total_spend)` 算行业级 AI 渗透率, 分母套 NULLIF 防零。窗口同样限制近 6 个月。

```sql
SELECT
    c.industry,
    COUNT(DISTINCT c.id) AS customer_count,
    ROUND(SUM(um.total_spend), 2) AS total_spend_6m,
    ROUND(AVG(um.total_spend), 2) AS avg_monthly_spend_per_record,
    ROUND(SUM(um.ai_ml_spend) / NULLIF(SUM(um.total_spend), 0) * 100, 2) AS ai_ml_pct
FROM customer c
JOIN usage_metrics um ON c.id = um.customer_id
WHERE c.is_active = 1
  AND um.month_year >= DATE('now', '-6 months', 'start of month')
GROUP BY c.industry
ORDER BY total_spend_6m DESC;
```

**预期结果说明:**
返回各行业近 6 个月的客户数和消费汇总。Technology / Financial Services 通常消费最高。

业务结论: 市场战略分析师据此判断 NimbusScale 在哪些行业最有渗透优势, ai_ml_pct 高的行业可作为 AI 产品的重点拓展赛道。

---

### 查询 14: 支持工单与健康度关联

**业务背景:**
支持运营经理想验证假设:支持工单数量是否与客户健康度负相关?如果相关性强,可将工单数纳入健康度模型。

**分类:** CTE+聚合
**难度:** 中级
**业务角色:** 分析师

**解题思路:**
目标是验证"工单越多、健康度越低"。先 recent_metrics 算每个客户近 3 个月的平均工单, latest_health 取每客户最新综合分, 两个 CTE 各自聚合后再 JOIN, 避免 usage 多月行与 health 多快照行交叉扇出。外层按工单分桶 (0-2 / 2-5 / 5+) 求各桶平均健康度。如果生成器确实让工单反向驱动 support_score, 桶从低到高、平均健康度应单调下降, 假设即被数据证实。

```sql
WITH recent_metrics AS (
    SELECT
        customer_id,
        AVG(support_tickets_count) AS avg_tickets
    FROM usage_metrics
    WHERE month_year >= DATE('now', '-3 months', 'start of month')
    GROUP BY customer_id
),
latest_health AS (
    SELECT hs.customer_id, hs.overall_score
    FROM health_score hs
    WHERE hs.score_date = (
        SELECT MAX(score_date) FROM health_score WHERE customer_id = hs.customer_id
    )
)
SELECT
    CASE
        WHEN rm.avg_tickets < 2 THEN '0-2 工单'
        WHEN rm.avg_tickets < 5 THEN '2-5 工单'
        ELSE '5+ 工单'
    END AS ticket_range,
    COUNT(*) AS customer_count,
    ROUND(AVG(lh.overall_score), 1) AS avg_health_score,
    MIN(lh.overall_score) AS min_health_score,
    MAX(lh.overall_score) AS max_health_score
FROM recent_metrics rm
JOIN latest_health lh ON rm.customer_id = lh.customer_id
GROUP BY ticket_range
ORDER BY avg_health_score DESC;
```

**预期结果说明:**
"0-2 工单" 桶平均健康度 ~85+,"5+ 工单" 桶 ~55-60,假设得到验证。生成器把每客户的 `support_tickets_count` 从隐含的健康度基线反向驱动,因此该相关性是真实的数据信号,不是巧合。

---

### 查询 15: 扩容机会识别

**业务背景:**
销售总监每季度需要识别有扩容潜力的客户:用量持续增长、健康度高、采用了多种服务、近期互动积极。

**分类:** CTE+窗口函数
**难度:** 高级
**业务角色:** CSM经理

**解题思路:**
四个 CTE 各取一块: usage_growth 用 LAG 算逐月环比, growth_rate 求每客户的平均增速 (对单月噪声更稳健), latest_health 取最新分, latest_metrics 取最新月的服务数和 AI 消费。外层 JOIN 后用 CASE 按 (健康 ≥ 80 且增速 > 10%) 等组合阈值分 Hot / Warm / Potential, 并只保留增速为正且健康 ≥ 65 的候选。用平均增速而非单月增速, 是为了不被某一个月的跳变带偏。

```sql
WITH usage_growth AS (
    SELECT
        customer_id,
        total_spend,
        LAG(total_spend) OVER (PARTITION BY customer_id ORDER BY month_year) AS prev_spend,
        month_year
    FROM usage_metrics
),
growth_rate AS (
    SELECT
        customer_id,
        AVG((total_spend - prev_spend) / NULLIF(prev_spend, 0)) AS avg_growth_rate
    FROM usage_growth
    WHERE prev_spend IS NOT NULL AND prev_spend > 0
    GROUP BY customer_id
),
latest_health AS (
    SELECT hs.customer_id, hs.overall_score
    FROM health_score hs
    WHERE hs.score_date = (
        SELECT MAX(score_date) FROM health_score WHERE customer_id = hs.customer_id
    )
),
latest_metrics AS (
    SELECT um.customer_id, um.active_services_count, um.ai_ml_spend
    FROM usage_metrics um
    WHERE um.month_year = (
        SELECT MAX(month_year) FROM usage_metrics WHERE customer_id = um.customer_id
    )
)
SELECT
    c.id AS customer_id,
    c.company_name,
    t.name AS tier,
    csm.name AS csm_name,
    lh.overall_score AS health_score,
    ROUND(gr.avg_growth_rate * 100, 2) AS avg_growth_pct,
    lm.active_services_count,
    ROUND(lm.ai_ml_spend, 2) AS ai_ml_spend,
    CASE
        WHEN lh.overall_score >= 80 AND gr.avg_growth_rate > 0.1 THEN 'Hot'
        WHEN lh.overall_score >= 70 AND gr.avg_growth_rate > 0.05 THEN 'Warm'
        ELSE 'Potential'
    END AS opportunity_tier
FROM customer c
JOIN account_tier t ON c.account_tier_id = t.id
JOIN csm ON c.csm_id = csm.id
JOIN growth_rate gr ON c.id = gr.customer_id
JOIN latest_health lh ON c.id = lh.customer_id
JOIN latest_metrics lm ON c.id = lm.customer_id
WHERE c.is_active = 1
  AND gr.avg_growth_rate > 0
  AND lh.overall_score >= 65
ORDER BY
    CASE
        WHEN lh.overall_score >= 80 AND gr.avg_growth_rate > 0.1 THEN 1
        WHEN lh.overall_score >= 70 AND gr.avg_growth_rate > 0.05 THEN 2
        ELSE 3
    END,
    gr.avg_growth_rate DESC
LIMIT 20;
```

**预期结果说明:**
返回最有扩容潜力的客户,按机会热度排序。`NULLIF` 处理首月空值;`per-customer MAX` 处理客户级别的最新数据。

---

### 查询 16: CSM 工作负载分布

**业务背景:**
运营总监在进行人员规划时,需要了解各 CSM 的客户数量、组合质量与工作负载。每个 CSM 都有 tier_specialization,可以据此评估专门化负载是否均衡。

**分类:** CTE+连接
**难度:** 中级
**业务角色:** 运营

**解题思路:**
以 csm 为主表, `LEFT JOIN customer ... AND c.is_active = 1`, 保证连 0 个活跃客户的在职 CSM 也会出现 (人员规划要看见空闲的人)。portfolio 和 task_summary 两个 CTE 先各自聚合到客户粒度, 避免 usage 多月行与 csm_task 多任务行在同一次 JOIN 里交叉扇出, 把组合消费算翻倍。`WHERE csm.is_active = 1` 把 2 个离职 CSM 排除, 输出 13 行。各 tier 客户数用 `SUM(CASE WHEN t.name = ...)` 做行转列的透视。

```sql
WITH portfolio AS (
    SELECT customer_id, SUM(total_spend) AS portfolio_spend
    FROM usage_metrics
    WHERE month_year >= DATE('now', '-6 months', 'start of month')
    GROUP BY customer_id
),
task_summary AS (
    SELECT customer_id, COUNT(*) AS open_tasks
    FROM csm_task
    WHERE status IN ('open', 'in_progress')
    GROUP BY customer_id
)
SELECT
    csm.name AS csm_name,
    csm.tier_specialization,
    COUNT(DISTINCT c.id) AS customer_count,
    SUM(CASE WHEN t.name = 'Enterprise' THEN 1 ELSE 0 END) AS enterprise_count,
    SUM(CASE WHEN t.name = 'Business' THEN 1 ELSE 0 END) AS business_count,
    SUM(CASE WHEN t.name = 'Pro' THEN 1 ELSE 0 END) AS pro_count,
    SUM(CASE WHEN t.name = 'Basic' THEN 1 ELSE 0 END) AS basic_count,
    ROUND(COALESCE(SUM(p.portfolio_spend), 0), 2) AS total_portfolio_spend_6m,
    COALESCE(SUM(ts.open_tasks), 0) AS open_tasks
FROM csm
LEFT JOIN customer c ON c.csm_id = csm.id AND c.is_active = 1
LEFT JOIN account_tier t ON c.account_tier_id = t.id
LEFT JOIN portfolio p ON c.id = p.customer_id
LEFT JOIN task_summary ts ON c.id = ts.customer_id
WHERE csm.is_active = 1
GROUP BY csm.id, csm.name, csm.tier_specialization
ORDER BY csm.tier_specialization, total_portfolio_spend_6m DESC;
```

**预期结果说明:**
按 CSM 输出客户组合、6 个月组合消费、当前在办任务。Enterprise CSM 通常负责 4-7 个高价值客户;SMB CSM 负责 10-13 个 Pro/Basic 客户。`portfolio` 与 `task_summary` 两个 CTE 各自先聚合,避免了 usage × csm_task 扇出 — portfolio_spend 不会被任务数倍增。

---

### 查询 17: 合同即将到期提醒

**业务背景:**
财务和法务团队每周需要知道未来 30/60/90 天内到期的合同,以便准备续约文件和法律审查。

**分类:** 日期范围查询
**难度:** 基础
**业务角色:** 运营

**解题思路:**
subscription 关联 customer / csm / account_tier, 过滤 contract_end_date 落在未来 90 天内且状态非 churned/expired。用 `JULIANDAY` 相减算剩余天数, 再用 CASE 分 30 天内 / 30-60 天 / 60-90 天三档紧急度。按到期日升序, 最先到期的排最前。`auto_renewal = FALSE` 的合同没有自动续签兜底, 是要重点盯的对象。

```sql
SELECT
    c.company_name,
    t.name AS tier,
    csm.name AS csm_name,
    s.contract_end_date,
    JULIANDAY(s.contract_end_date) - JULIANDAY('now') AS days_remaining,
    CASE
        WHEN JULIANDAY(s.contract_end_date) - JULIANDAY('now') <= 30 THEN '30天内'
        WHEN JULIANDAY(s.contract_end_date) - JULIANDAY('now') <= 60 THEN '30-60天'
        ELSE '60-90天'
    END AS urgency,
    s.monthly_committed_spend,
    s.auto_renewal
FROM subscription s
JOIN customer c ON s.customer_id = c.id
JOIN csm ON c.csm_id = csm.id
JOIN account_tier t ON c.account_tier_id = t.id
WHERE s.contract_end_date BETWEEN DATE('now') AND DATE('now', '+90 days')
  AND s.status NOT IN ('churned', 'expired')
ORDER BY s.contract_end_date ASC;
```

**预期结果说明:**
返回 90 天内即将到期的合同,按 urgency 分桶。auto_renewal = FALSE 的需特别关注。

---

### 查询 18: 客户情绪趋势分析

**业务背景:**
客户体验经理想了解客户整体情绪趋势。通过分析交互记录中的情绪标签 (positive/neutral/negative) 可评估客户满意度变化。

**分类:** 聚合+日期
**难度:** 中级
**业务角色:** 分析师

**解题思路:**
对 interaction_log 用 `strftime('%Y-%m', interaction_date)` 把交互按月份归桶分组, 再用 `SUM(CASE WHEN sentiment = ...)` 做条件计数, 得到每月 positive / neutral / negative 的构成和占比。SQLite 没有原生的月份截断函数, strftime 是标准做法。按月份降序取最近 6 个月, 方便看趋势是在变好还是变坏。

```sql
SELECT
    strftime('%Y-%m', il.interaction_date) AS month,
    COUNT(*) AS total_interactions,
    SUM(CASE WHEN il.sentiment = 'positive' THEN 1 ELSE 0 END) AS positive,
    SUM(CASE WHEN il.sentiment = 'neutral' THEN 1 ELSE 0 END) AS neutral,
    SUM(CASE WHEN il.sentiment = 'negative' THEN 1 ELSE 0 END) AS negative,
    ROUND(SUM(CASE WHEN il.sentiment = 'positive' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) AS positive_pct,
    ROUND(SUM(CASE WHEN il.sentiment = 'negative' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) AS negative_pct
FROM interaction_log il
GROUP BY strftime('%Y-%m', il.interaction_date)
ORDER BY month DESC
LIMIT 6;
```

**预期结果说明:**
返回最近 6 个月的情绪分布。positive_pct 40%+ 算健康。

业务结论: 客户体验经理盯的是趋势而非单月。若 negative_pct 连续几个月抬头, 说明客户满意度在系统性下滑, 应触发一次跨团队的体验复盘。

---

### 查询 19: 季度 QBR 完成情况

**业务背景:**
客户成功副总裁要求每个企业级和商业级客户每季度至少进行一次 QBR (Quarterly Business Review)。运营需要检查近 90 天 QBR 完成情况。

**分类:** 连接+日期
**难度:** 中级
**业务角色:** 运营

**解题思路:**
先用 CTE recent_qbrs 把近 90 天 `interaction_type.name = 'QBR Meeting'` 的交互按客户聚合 (计数 + 最后日期)。外层以 customer 为主表 `LEFT JOIN` 这个 CTE: 没做过 QBR 的客户 qbr_count 为 NULL, 用 COALESCE 归零并标成 'Not Scheduled'。LEFT JOIN 是这题的灵魂, 换成 INNER 就只剩做过 QBR 的客户, 恰恰漏掉了最该催的"没做 QBR"客户。范围限定在活跃的 Enterprise / Business 客户。

```sql
-- 注: 这里用 "近 90 天" 近似 "本季度"(SQLite 季度边界数学繁琐,Demo 中采用此简化)
WITH recent_qbrs AS (
    SELECT
        il.customer_id,
        COUNT(*) AS qbr_count,
        MAX(il.interaction_date) AS last_qbr_date
    FROM interaction_log il
    JOIN interaction_type it ON il.interaction_type_id = it.id
    WHERE it.name = 'QBR Meeting'
      AND il.interaction_date >= DATE('now', '-90 days')
    GROUP BY il.customer_id
)
SELECT
    c.company_name,
    t.name AS tier,
    csm.name AS csm_name,
    COALESCE(q.qbr_count, 0) AS qbr_last_90d,
    q.last_qbr_date,
    CASE
        WHEN q.qbr_count > 0 THEN 'Completed'
        ELSE 'Not Scheduled'
    END AS qbr_status
FROM customer c
JOIN account_tier t ON c.account_tier_id = t.id
JOIN csm ON c.csm_id = csm.id
LEFT JOIN recent_qbrs q ON c.id = q.customer_id
WHERE c.is_active = 1
  AND t.name IN ('Enterprise', 'Business')
ORDER BY
    CASE WHEN q.qbr_count > 0 THEN 1 ELSE 0 END,
    t.monthly_min_spend DESC;
```

**预期结果说明:**
返回所有需要 QBR 的活跃 Enterprise/Business 客户及其完成状态。Not Scheduled 的需立即安排。

---

### 查询 20: 客户全景视图

**业务背景:**
CSM 在准备客户会议前,需要快速了解客户的全面信息:基本信息、消费趋势、健康度、最近互动、待办任务。"一页纸" 客户画像。

**分类:** CTE+多表连接
**难度:** 高级
**业务角色:** CSM

**解题思路:**
一页纸客户画像, 把六个维度各用一个 CTE 聚合到客户粒度: 最新月用量、近 6 个月用量趋势、最新健康度、近 90 天互动、在办任务, 以及 active_sub (用 SUM/MIN 汇总多份合同避免扇出)。外层把它们全部 `LEFT JOIN` 到 customer, 这样某一块没数据也不会让整行消失, 缺的字段显示 NULL。`WHERE c.id = 51` 锁定单个客户, 换 id 即换客户。这是 Customer 360 Agent 背后那条真正的查询。

```sql
WITH latest_usage AS (
    SELECT um.customer_id, um.total_spend AS latest_spend, um.compute_spend, um.storage_spend, um.ai_ml_spend, um.active_services_count
    FROM usage_metrics um
    WHERE um.month_year = (
        SELECT MAX(month_year) FROM usage_metrics WHERE customer_id = um.customer_id
    )
),
usage_trend AS (
    SELECT customer_id,
           AVG(total_spend) AS avg_6m_spend,
           SUM(total_spend) AS total_6m_spend
    FROM usage_metrics
    WHERE month_year >= DATE('now', '-6 months', 'start of month')
    GROUP BY customer_id
),
latest_health AS (
    SELECT hs.customer_id, hs.overall_score, hs.usage_score, hs.engagement_score, hs.support_score, hs.notes
    FROM health_score hs
    WHERE hs.score_date = (
        SELECT MAX(score_date) FROM health_score WHERE customer_id = hs.customer_id
    )
),
recent_interactions AS (
    SELECT customer_id, COUNT(*) AS interaction_count_90d, MAX(interaction_date) AS last_interaction
    FROM interaction_log
    WHERE interaction_date >= DATE('now', '-90 days')
    GROUP BY customer_id
),
open_tasks AS (
    SELECT customer_id, COUNT(*) AS open_task_count, MIN(due_date) AS nearest_due_date
    FROM csm_task
    WHERE status IN ('open', 'in_progress')
    GROUP BY customer_id
),
active_sub AS (
    -- 客户全部 active 订阅汇总: 月承诺消费 SUM, 合同到期日取最早 (优先关注最近到期)
    SELECT customer_id,
           SUM(monthly_committed_spend) AS monthly_committed_spend,
           MIN(contract_end_date) AS contract_end_date,
           MAX(status) AS status
    FROM subscription
    WHERE status = 'active'
    GROUP BY customer_id
)
SELECT
    c.id AS customer_id,
    c.company_name,
    c.industry,
    c.employee_count,
    t.name AS tier,
    r.name AS primary_region,
    csm.name AS csm_name,
    c.created_at AS customer_since,
    asub.contract_end_date,
    asub.monthly_committed_spend,
    asub.status AS subscription_status,
    ROUND(lu.latest_spend, 2) AS latest_month_spend,
    ROUND(ut.avg_6m_spend, 2) AS avg_monthly_spend_6m,
    lu.active_services_count,
    ROUND(lu.ai_ml_spend, 2) AS ai_ml_spend,
    lh.overall_score AS health_score,
    lh.usage_score,
    lh.engagement_score,
    lh.support_score,
    lh.notes AS health_notes,
    COALESCE(ri.interaction_count_90d, 0) AS interactions_90d,
    ri.last_interaction,
    COALESCE(ot.open_task_count, 0) AS open_tasks,
    ot.nearest_due_date AS next_task_due
FROM customer c
JOIN account_tier t ON c.account_tier_id = t.id
JOIN region r ON c.primary_region_id = r.id
JOIN csm ON c.csm_id = csm.id
LEFT JOIN active_sub asub ON c.id = asub.customer_id
LEFT JOIN latest_usage lu ON c.id = lu.customer_id
LEFT JOIN usage_trend ut ON c.id = ut.customer_id
LEFT JOIN latest_health lh ON c.id = lh.customer_id
LEFT JOIN recent_interactions ri ON c.id = ri.customer_id
LEFT JOIN open_tasks ot ON c.id = ot.customer_id
WHERE c.id = 51  -- 替换为目标客户ID (示例: 一个 Enterprise 客户)
LIMIT 1;
```

**预期结果说明:**
返回指定客户的全景信息(单行,因 active_sub 已通过子查询聚合)。CSM 可在 30 秒内掌握客户全貌。

---

## 7. 查询分类汇总

| 分类 | 数量 | 查询编号 |
|------|------|----------|
| 聚合查询 | 5 | 1, 6, 11, 13, 14 |
| 连接操作 | 5 | 3, 5, 9, 17, 19 |
| 窗口函数 | 4 | 2, 4, 7, 15 |
| 日期时间分析 | 3 | 10, 17, 18 |
| CTE复合查询 | 7 | 8, 11, 12, 14, 15, 16, 20 |

---

## 8. 业务角色覆盖

| 角色 | 数量 | 查询编号 |
|------|------|----------|
| 高管/C级 | 3 | 1, 5, 11 |
| CSM经理 | 5 | 2, 3, 7, 12, 15 |
| 分析师 | 5 | 4, 10, 13, 14, 18 |
| 运营 | 5 | 6, 9, 16, 17, 19 |
| 财务 | 1 | 8 |
| CSM | 1 | 20 |

---

## 9. 难度分布

| 难度 | 数量 | 查询编号 |
|------|------|----------|
| 基础 | 6 | 1, 6, 9, 11, 13, 17 |
| 中级 | 9 | 3, 4, 5, 8, 10, 14, 16, 18, 19 |
| 高级 | 5 | 2, 7, 12, 15, 20 |

---

## 10. 备注

- 所有查询均使用 SQLite 3.x 语法
- 日期函数 (JULIANDAY、strftime) 是 SQLite 特有的,其他数据库需替换
- 查询 4 / 20 中的客户 ID 可替换为实际目标
- Query 11 用 CTE 提前对每行打 segment 标签,外层 GROUP BY 即可正确分两组
- Queries 8 / 16 / 20 通过各侧 CTE 先聚合,避免 subscription / csm_task 扇出
- Queries 3 / 12 / 14 / 15 / 20 统一使用 per-customer MAX (correlated subquery) 取最新评分,因此即使不同客户的最新评分日期不同也不会漏数
