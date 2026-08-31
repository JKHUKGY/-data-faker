# 财产 & 责任险 — 商业承保 SQL 查询参考

> 配套文档:业务背景 `01-property_casualty_commercial_underwriting_high_business_context-cn.md`、数据结构 `02-property_casualty_commercial_underwriting_high_er_document-cn.md`
> 所有查询兼容 SQLite 3.x。参考 "今天" (REFERENCE_DATE) = `2026-06-21`
> 数据库文件:`property_casualty_commercial_underwriting_high.sqlite`

## 概述

本文档提供 **50 条 SQL 查询**,旨在全面覆盖 InsightUnderwriter AI Agent 在续保决策、理赔分析、风险识别等场景的数据需求。

每条查询都附 **业务背景** 说明:**谁会问这个问题、在什么情况下问、问出来要做什么决策**。即便是非保险专业的读者,也能通过这些上下文理解保险业务的核心运作逻辑。

按照 ER 文档第 15 节 BI 蓝图的指引,查询分为两类:

| 类别 | 数量 | 风格 | 用途 |
|------|------|------|------|
| **Dashboard 风格** (D1–D15) | 15 (30%) | 快照式、聚合密集、固定指标 | 每条对应一个 L2/L3 仪表盘控件 |
| **业务问题风格** (B1–B35) | 35 (70%) | 多样、探索性 | 每条回答一个独立的临时分析问题 |

## 如何使用本文档

**读者画像:** 本文档写给一位 **刚读完业务背景文档与 ER 文档、即将被经理派去跑这些查询的实习生**。如果你还说不清 Loss Ratio、Reserve、Broker、Underwriter 是什么,请先回到 `01-..._business_context-cn.md` (业务背景 + 术语表 + 指标公式) 和 `02-..._er_document-cn.md` (表结构 + 字段含义),再回来。

**每条查询的五段式结构** —— 每条查询都按下面五段组织,请按顺序读:

1. **业务背景** —— 谁在问、为什么现在问、答案用来做什么决策。先理解"为什么要查",再看怎么查。
2. **类别 / 难度 / 角色** —— 这条查询用到的 SQL 技术、难度、以及在公司里是哪个岗位会用它。
3. **解题思路** —— 在看 SQL 之前,先理解该碰哪些表、join 怎么搭 (为什么是 LEFT 而非 INNER)、聚合的粒度是什么、为什么用 CTE / 窗口函数、有哪些坑 (扇出 / 重复计数 / NULL 语义)。**这一段是教学重点,看懂了再看 SQL 会轻松很多。**
4. **SQL 代码** —— 可直接在 SQLite 数据库上运行。
5. **预期结果 + 业务结论** —— 结果有几行几列、各列什么含义、关键数值应落在什么量级,以及 **拿到结果后分析师下一步该做什么**。跑出数字只是分析的开始,不是结束。

**REFERENCE_DATE 约定:** 数据集锚定在固定的"今天" = `2026-06-21`。所有涉及"距今多少天""近 N 年"的查询都用 **字面量日期** (如 `'2026-06-21'` 或 `DATE('2026-06-21', '-12 months')`),**绝不用 `DATE('now')`**,这样无论何时运行,结果都可复现、可对照本文档的预期值。

**每条查询都映射到一个业务问题:** 文档末尾有"业务问题 → 查询"对照。每条查询都能追溯到业务背景文档第 5 节列出的 5 个业务问题之一 (风险定价是否准确、哪些客户该涨价/拒保/留住、续保决策是否准确、理赔有无欺诈/失控信号、付款与外部风险预警)。

**SQL 是用来读和学的,不只是执行:** 同一个业务问题往往有多种写法,本文档选的是 **生产环境会真正采用、且能规避常见陷阱 (如 policy×claim 扇出导致保费重复计数) 的写法**。遇到 `> 修复扇出` / `> 口径说明` / `> SQLite 方言提示` 这类引用块时务必细读,那是真实项目踩过的坑。

## 查询索引

### Dashboard 风格 (D1–D15)

| # | 标题 | Dashboard | 角色 | 类别 | 难度 |
|---|------|-----------|------|------|------|
| D1 | 公司层 Loss Ratio 月度趋势 | CFO 季度盈亏 | CFO/CEO | CTE + 时间分桶 | 中级 |
| D2 | 续保留存与流失分析 | 续保健康度 | 承保副总 | 透视聚合 | 中级 |
| D3 | Broker 渠道贡献分析 | 渠道贡献 | 渠道总监 | 多表 JOIN + 聚合 | 中级 |
| D4 | 续保到期日历 (未来 60 天) | 续保到期 | 核保经理 | 日期过滤 | 基础 |
| D5 | 高风险理赔预警 (reserve 反复上调) | 理赔预警 | 理赔经理 | 聚合 + HAVING | 中级 |
| D6 | Underwriter 月配额完成率 | 核保员产能 | 核保经理 | 聚合 + JOIN | 中级 |
| D7 | 付款逾期客户预警 | 财务预警 | 财务经理 | 聚合 + JOIN | 中级 |
| D8 | 现场检查整改逾期清单 | 风控追踪 | 风控经理 | 日期算术 | 基础 |
| D9 | 欺诈信号热力图 (按企业) | 反欺诈监控 | 反欺诈分析师 | RAG 聚合 | 中级 |
| D10 | 综合续保决策助手 (单家企业 360°) | 续保决策助手 | 核保员 | CTE 多表 JOIN | 高级 |
| D11 | 行业基准对比仪表盘 | 行业对标 | 核保经理 | JOIN + 聚合 | 中级 |
| D12 | 监管处罚分布 (按机构+年度) | 合规监控 | 合规总监 | 透视聚合 | 中级 |
| D13 | 信用评级下调企业追踪 | 评级监控 | 财务总监 | 窗口函数 | 高级 |
| D14 | 保费滑动告警 (一年内 ≥ 3 次批改) | 保费监控 | 核保经理 | 聚合 + HAVING | 中级 |
| D15 | Adjuster 在办案件量 | 理赔产能 | 理赔经理 | 聚合 + JOIN | 基础 |

### 业务问题风格 (B1–B35)

| # | 标题 | 主题域 | 角色 | 类别 | 难度 |
|---|------|--------|------|------|------|
| B1 | 客户基本档案 + 经营场所概览 | A 客户画像 | 核保员 | JOIN | 基础 |
| B2 | 财务健康年度趋势 (LAG 同比) | A 客户画像 | 财务分析师 | 窗口函数 | 中级 |
| B3 | 信用评级变化历史时间线 | A 客户画像 | 财务分析师 | 窗口函数 | 中级 |
| B4 | 高负债率企业清单 (Top 50) | A 客户画像 | 风控经理 | 聚合 + 排序 | 基础 |
| B5 | 财务恶化 + 高赔付率双重信号企业 | A 客户画像 | 核保经理 | CTE + 多表 | 高级 |
| B6 | Top 保费客户排行 (Top 25) | B 保单承保 | CEO/CRO | 聚合 + 排序 | 基础 |
| B7 | 各险种保费规模占比 | B 保单承保 | 承保副总 | 聚合 | 基础 |
| B8 | 保单批改频度分布 | B 保单承保 | 核保经理 | 聚合 + 分桶 | 基础 |
| B9 | 单张保单完整保费历史溯源 | B 保单承保 | 核保员 | 窗口函数 | 中级 |
| B10 | 续保决策准确性 (决策 vs 后续赔付率) | B 保单承保 | 核保经理 | CTE + 多表 | 高级 |
| B11 | 风险评分 vs 实际赔付率相关性 | B 保单承保 | 精算/分析师 | CTE + 分桶 | 高级 |
| B12 | 直销 vs 经纪渠道质量对比 | B 保单承保 | 渠道总监 | 聚合 + 对比 | 中级 |
| B13 | 各企业三年累计赔付率 | C 理赔 | 核保员 | 聚合 + JOIN | 基础 |
| B14 | 平均结案天数 (按险种) | C 理赔 | 理赔经理 | 日期算术 + 聚合 | 中级 |
| B15 | 大额理赔 Top 30 | C 理赔 | 理赔总监 | 排序 + JOIN | 基础 |
| B16 | 出险至报案延迟分析 (道德风险信号) | C 理赔 | 反欺诈分析师 | 日期算术 + 分桶 | 中级 |
| B17 | 准备金反复上调的危险案件 | C 理赔 | 理赔经理 | 聚合 + 窗口 | 高级 |
| B18 | 理赔状态分布 (各企业) | C 理赔 | 核保员 | 透视聚合 | 中级 |
| B19 | 已拒赔理赔分析 | C 理赔 | 理赔总监 | 聚合 + JOIN | 中级 |
| B20 | 公司跨年度赔付率变化趋势 (Window) | C 理赔 | 核保经理 | 窗口函数 | 高级 |
| B21 | 各企业欺诈信号统计 (RAG) | D 非结构化 | 反欺诈分析师 | 聚合 + JOIN | 中级 |
| B22 | 含律师介入 claim 的损失金额对比 | D 非结构化 | 法务 | 子查询 + 对比 | 中级 |
| B23 | signal_tag × claim_type 矩阵 | D 非结构化 | 风险分析师 | 透视 | 中级 |
| B24 | 隐患整改逾期清单 | D 非结构化 | 风控经理 | 日期算术 + CASE | 中级 |
| B25 | 通讯作者活跃度 (XOR 模式) | D 非结构化 | 数据分析师 | XOR + 聚合 | 中级 |
| B26 | 客户付款行为评级分桶 | E 付款 | 财务经理 | CASE + 聚合 | 中级 |
| B27 | 严重逾期客户名单 + 在保保费 | E 付款 | 信用风险 | JOIN + 聚合 | 中级 |
| B28 | 应收账款账龄分析 | E 付款 | 财务经理 | 日期分桶 | 中级 |
| B29 | 付款行为 vs 赔付率相关性 | E 付款 | RevOps | CTE + 聚合 | 高级 |
| B30 | 行业风险等级与平均赔付率对照 | F 外部 | 精算师 | JOIN | 基础 |
| B31 | 监管处罚密度排行 (各企业) | F 外部 | 合规经理 | 聚合 + 排序 | 基础 |
| B32 | 信用评级下调企业的后续赔付率 | F 外部 | RevOps | CTE + 多表 | 高级 |
| B33 | 高罚款企业的保单组合 | F 外部 | 合规经理 | JOIN + 聚合 | 中级 |
| B34 | 行业基准偏离最大企业 Top N | F 外部 | 承保副总 | JOIN + 排序 | 中级 |
| B35 | 多维度风险综合评分排行 | F 外部 | 核保经理 | CTE 大综合 | 高级 |

---

## 维度术语表

"风险" 一词在保险业务中被反复使用,下述查询中区分了 **4 个不同维度** 的风险:

| 维度 | 来源字段 | 基数 | 含义 |
|------|---------|------|------|
| `company.risk_tier` | 公司表 | 4 (低/中/高/极高) | 公司层面的粗分类,基于行业和规模 |
| `company_location.location_risk_level` | 场所表 | 3 (低/中/高) | 单个场所的物理风险等级 |
| `risk_assessment.risk_score` | 评估表 | 0-100 | Underwriter 对单张保单的精细评分 |
| `industry_benchmark.avg_loss_ratio` | 基准表 | 行业 × 年 | 行业平均赔付率,用于对标 |

经验法则:每条查询只聚焦一个维度,避免混淆。

---

# Dashboard 风格查询 (D1–D15)

每条查询驱动一个 dashboard 控件,聚合密集、面向快照。

---

## D1: 公司层 Loss Ratio 月度趋势

**Dashboard:** CFO 季度盈亏

**业务背景:** CFO/CEO 每月看一次"我们整个公司核保业务赚不赚钱"。最核心的指标就是 **Loss Ratio (赔款 ÷ 保费)**。一旦这个比率连续 3 个月超过 70%,就要预警 (因为加上 30% 运营费用,Combined Ratio 已经突破 100% 的盈亏平衡线)。这条查询输出按月份聚合的 Loss Ratio,可识别变化拐点。

**类别:** CTE + 时间分桶
**难度:** 中级
**角色:** CFO / CEO

**解题思路:** 这条要把月度保费(`invoice` 按 `invoice_date` 分月)和月度已付赔款(`claim` 按 `incident_date` 分月)各自聚到"年-月"粒度再相除。注意这两套数字来自两张不相干的表、走的是两个不同的日期口径(保费看开票日、赔款看出险日),所以绝不能把它们 join 到同一张明细上算,否则就会出现保费被 claim 行数重复累加的 fan-out。正确做法是两个 CTE 各自先 GROUP BY 月份独立聚合,再用 `LEFT JOIN` 以保费月份为基准把赔款接上——用 LEFT JOIN 而非 INNER 是因为某些月份可能没有赔款,但这些月份的保费分母仍要保留,否则该月的 loss_ratio 会凭空消失。一行输出代表一个月。SQLite 用 `STRFTIME('%Y-%m', ...)` 取月份,`NULLIF(分母,0)` 防止除零,`COALESCE` 把没赔款月份的 NULL 补成 0。

```sql
WITH monthly_premium AS (
  SELECT STRFTIME('%Y-%m', invoice_date) AS month,
         SUM(amount_due_cny) AS premium_billed
  FROM invoice
  WHERE invoice_date >= '2024-06-01'   -- 数据窗起点 (HISTORY_START = TODAY-730 = 2024-06-21)
  GROUP BY 1
),
monthly_loss AS (
  SELECT STRFTIME('%Y-%m', incident_date) AS month,
         SUM(paid_amount_cny) AS losses_paid,
         COUNT(*) AS claim_count
  FROM claim
  WHERE incident_date >= '2024-06-01' AND paid_amount_cny > 0
  GROUP BY 1
)
SELECT mp.month,
       ROUND(mp.premium_billed, 0) AS premium_billed_cny,
       ROUND(COALESCE(ml.losses_paid, 0), 0) AS losses_paid_cny,
       COALESCE(ml.claim_count, 0) AS claim_count,
       ROUND(COALESCE(ml.losses_paid, 0) * 1.0 / NULLIF(mp.premium_billed, 0), 3) AS loss_ratio
FROM monthly_premium mp
LEFT JOIN monthly_loss ml ON ml.month = mp.month
ORDER BY mp.month;
```

**预期结果说明:** 约 25 行 (覆盖 2024-06 至 2026-06,数据起点 2024-06-21,故不足整 30 个月)。各月 loss_ratio 多在 0.2-0.7 之间波动 (本公司账面赔付率整体偏健康);若某月骤升至 0.85+,需要 drill-down 看是哪个行业或哪几家大客户在出险。

---

## D2: 续保留存与流失分析

**Dashboard:** 续保健康度

**业务背景:** 续保季 (每年 6 月 / 12 月) 是承保副总最紧张的时段。**续保率 < 60% 意味着 broker 把客户转去竞品**,公司明年的保费基本盘会萎缩。这条查询输出过去 12 个月的续保决策分布:续保 / 有条件续保 / 拒保,以及平均保费变化幅度,反映承保部门的留客健康度。

**类别:** 透视聚合
**难度:** 中级
**角色:** 承保副总

**解题思路:** 这条只碰一张表 `renewal_decision` 就够了——所有要的字段(decision、premium_change_pct、decision_date)都在里面,不必 join 任何维度表,所以一次 GROUP BY decision 即可。每一行输出代表一种续保决策(续保 / 有条件续保 / 拒保)。难点不在 join 而在"占比"这一列:要算每种决策占总量的百分比,分母是全部决策数。这里用 window function `SUM(COUNT(*)) OVER ()`——COUNT 先在每个 decision 分组内算出组内计数,外层的 `SUM(...) OVER ()` 再把所有组的计数加成总数,一步算出 pct,不用再写一个子查询去单独求总数。`decision_date >= DATE('2026-06-21', '-12 months')` 用字面量锚定的"今天"往前推 12 个月,保证结果可复现。

```sql
SELECT decision,
       COUNT(*) AS decision_count,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS pct,
       ROUND(AVG(premium_change_pct), 2) AS avg_premium_change_pct,
       ROUND(MIN(premium_change_pct), 2) AS min_change,
       ROUND(MAX(premium_change_pct), 2) AS max_change
FROM renewal_decision
WHERE decision_date >= DATE('2026-06-21', '-12 months')
GROUP BY decision
ORDER BY decision_count DESC;
```

**预期结果说明:** 3 行。设计目标:续保 ~65% / 有条件续保 ~25% / 拒保 ~10%。"续保" 平均涨价 5-10%,"有条件续保" 通常涨 20-30%。若 "拒保" 比例超过 15%,要预警 (说明客户质量整体在下降)。

---

## D3: Broker 渠道贡献分析

**Dashboard:** 渠道贡献

**业务背景:** 80% 商业保险通过 broker 渠道达成。渠道总监要清楚 **哪些 broker 给我们送的单又多又好**,哪些只送 "烂单" (高赔付率)。这条查询按 broker 汇总在保保费和该 broker 引入业务的实际赔付率,用于年度 broker 评级 / 调整佣金。

**类别:** 多表 JOIN + 聚合
**难度:** 中级
**角色:** 渠道总监

**解题思路:** broker 维度的赔付率,最容易踩的坑是 `broker → policy → claim` 直接 join 后 `SUM(保费)`:一张有 N 个 claim 的保单,其 `current_annual_premium_cny` 会被重复累加 N 次(实测虚增约 56%),使 broker_loss_ratio 的分母虚高、被系统性低估。正确做法是把保费和赔款拆成两个独立 CTE 各算各的——`broker_premium` 按 broker 用 `COUNT(DISTINCT policy_id)` 和 `SUM(保费)` 聚保费、保证每张保单只计一次;`broker_claims` 独立地按 broker join claim 聚已付赔款。最后用 `broker JOIN broker_premium`(只看有保单的 broker)再 `LEFT JOIN broker_claims`(没出过险的 broker 赔款应记 0 而非被丢掉),`COALESCE` 把 NULL 补 0。一行输出代表一个 broker。`broker_id IS NOT NULL` 是因为直销保单没有 broker,要排除。

```sql
WITH broker_premium AS (   -- 先按 broker 聚合保费, 每张保单只计一次
  SELECT p.broker_id,
         COUNT(DISTINCT p.policy_id) AS policy_count,
         SUM(p.current_annual_premium_cny) AS total_premium_cny
  FROM policy p
  WHERE p.broker_id IS NOT NULL
  GROUP BY p.broker_id
),
broker_claims AS (         -- 独立按 broker 聚合已付赔款, 避免保费被 claim 行数放大
  SELECT p.broker_id,
         SUM(cl.paid_amount_cny) AS total_paid_claims_cny
  FROM policy p
  JOIN claim cl ON cl.policy_id = p.policy_id
  WHERE p.broker_id IS NOT NULL
  GROUP BY p.broker_id
)
SELECT b.broker_id, b.broker_firm, b.tier,
       bp.policy_count,
       ROUND(bp.total_premium_cny, 0) AS total_premium_cny,
       ROUND(COALESCE(bc.total_paid_claims_cny, 0), 0) AS total_paid_claims_cny,
       ROUND(COALESCE(bc.total_paid_claims_cny, 0) * 1.0
             / NULLIF(bp.total_premium_cny, 0), 3) AS broker_loss_ratio,
       b.commission_rate,
       ROUND(bp.total_premium_cny * b.commission_rate, 0) AS commission_payout_cny
FROM broker b
JOIN broker_premium bp ON bp.broker_id = b.broker_id
LEFT JOIN broker_claims bc ON bc.broker_id = b.broker_id
WHERE b.is_active = 1
ORDER BY broker_loss_ratio DESC;
```

> **修复扇出 (fan-out):** 原写法 `broker LEFT JOIN policy LEFT JOIN claim` 后直接 `SUM(p.current_annual_premium_cny)`,
> 会把有 N 个理赔的保单的保费**重复累加 N 次** (实测保费虚增约 56%),赔付率分母被放大、被系统性低估。
> 这里先在子查询里按 policy 把保费聚合好,再独立子查询算赔款,彻底消除重复计数。

**预期结果说明:** ~55 行。按 broker_loss_ratio 倒序,排在最前面的是 "烂单" broker (该渠道引入的业务赔付率最高)。结合佣金支出看 ROI:佣金高 + 赔付率高的 broker 是公司在 "倒贴钱"。

---

## D4: 续保到期日历 (未来 60 天)

**Dashboard:** 续保到期

**业务背景:** 核保经理需要 **提前 30-60 天** 知道哪些保单要到期,提前分配给团队成员开始预审。漏掉一张大保单的续保,客户可能就被竞品撬走。这条查询列出未来 60 天内到期的所有有效保单,按到期日 ASC 排序,附带客户名、保费规模、现任 underwriter。

**类别:** 日期过滤
**难度:** 基础
**角色:** 核保经理

**解题思路:** 这是一条纯明细查询,没有聚合,一行输出代表一张即将到期的保单。要碰三张表:`policy` 给到期日和保费,`company` 给客户名和行业(这里用 INNER JOIN 是因为每张保单必然属于一家公司),`underwriter` 给现任核保员姓名。窗口期用 `expiration_date BETWEEN '2026-06-21' AND DATE('2026-06-21', '+60 days')` 圈出未来 60 天,`status = '有效'` 排除已失效保单。`days_to_expire` 用 `JULIANDAY(到期日) - JULIANDAY('今天')` 算天数差——这是 SQLite 算日期间隔的标准手法,返回浮点天数。按 `expiration_date ASC` 排序,让最快到期的排最前,方便核保经理优先分派。

```sql
SELECT p.policy_id, p.policy_number,
       c.company_name, c.industry, c.risk_tier,
       p.policy_type,
       p.expiration_date,
       JULIANDAY(p.expiration_date) - JULIANDAY('2026-06-21') AS days_to_expire,
       ROUND(p.current_annual_premium_cny, 0) AS annual_premium_cny,
       u.full_name AS underwriter_name,
       u.role AS underwriter_role
FROM policy p
JOIN company c ON c.company_id = p.company_id
JOIN underwriter u ON u.underwriter_id = p.underwriter_id
WHERE p.status = '有效'
  AND p.expiration_date BETWEEN '2026-06-21' AND DATE('2026-06-21', '+60 days')
ORDER BY p.expiration_date ASC;
```

**预期结果说明:** 约 250-350 行 (60 天内到期保单)。重点关注 days_to_expire < 14 的高额保单 (annual_premium > 30 万)。这些是续保经理要 "亲自盯" 的优先项。

---

## D5: 高风险理赔预警 (reserve 反复上调)

**Dashboard:** 理赔预警

**业务背景:** 准备金 (reserve) 反复上调是 **事态恶化的最强信号** —— 案件越查越糟、对方升级诉讼、医疗费用爆炸。理赔经理每天看这个仪表盘,把 reserve 已上调 ≥ 3 次的案件抽出来人工复核,看是不是要追加再保险、提前提诉、或主动和解。

**类别:** 聚合 + HAVING
**难度:** 中级
**角色:** 理赔经理

**解题思路:** 这条要从 `claim` 出发,顺着 `policy → company` 拿客户名、join `claim_adjuster` 拿理赔员姓名,再 join `claim_reserve` 看每个 claim 的准备金调整记录。这里的 fan-out 是有意为之的:一个 claim 在 `claim_reserve` 里有多行(每次调整一行),正是我们要数的东西,所以按 claim 维度 GROUP BY 后 `COUNT(cr.reserve_id)` 数出调整次数、用 `MIN/MAX(reserve_amount_cny)` 取首次与最新准备金算增长额。要留心口径:`reserve_adjustment_count` 数的是"调整行数(含首次定损)",阈值 `>= 3` 等价于首次定损后又调了至少 2 次,统计的是次数不是严格"上调"次数。HAVING 必须放在 GROUP BY 之后过滤聚合结果(WHERE 做不到)。`status IN ('已立案','调查中','定损中')` 把范围限定在"在办"案件——已支付的不再需要追加准备金,排除掉。一行输出代表一个高危 claim。

```sql
SELECT cl.claim_id, cl.claim_number,
       c.company_name, cl.claim_type, cl.status,
       cl.incident_date,
       COUNT(cr.reserve_id) AS reserve_adjustment_count,
       ROUND(MIN(cr.reserve_amount_cny), 0) AS initial_reserve_cny,
       ROUND(MAX(cr.reserve_amount_cny), 0) AS current_reserve_cny,
       ROUND(MAX(cr.reserve_amount_cny) - MIN(cr.reserve_amount_cny), 0) AS reserve_growth_cny,
       a.full_name AS adjuster_name
FROM claim cl
JOIN policy p ON p.policy_id = cl.policy_id
JOIN company c ON c.company_id = p.company_id
JOIN claim_adjuster a ON a.adjuster_id = cl.adjuster_id
JOIN claim_reserve cr ON cr.claim_id = cl.claim_id
WHERE cl.status IN ('已立案', '调查中', '定损中')   -- "未结案/在办"统一定义 (见 KPI 字典 16.3); 已支付≈待结案不再需追加准备金, 故排除
GROUP BY cl.claim_id, cl.claim_number, c.company_name, cl.claim_type,
         cl.status, cl.incident_date, a.full_name
HAVING reserve_adjustment_count >= 3
ORDER BY reserve_growth_cny DESC
LIMIT 30;
```

> **口径说明:** `reserve_adjustment_count = COUNT(cr.reserve_id)` 是该 claim 的准备金**调整行数 (含首次定损)**,
> 阈值 `>= 3` 等价于"在首次定损后至少又调整 2 次"(与 ER 15.2 一致)。它统计的是调整次数而非严格"上调"次数;
> 若需只看金额增长轨迹见 B17 (`latest/initial > 1.5`)。

**预期结果说明:** 通常 20-30 行。reserve_growth_cny > 50 万的案件是 **必须人工介入** 的红色信号 (准备金已增长 50 万以上,意味着初次估损至少错估了 50 万)。

---

## D6: Underwriter 月配额完成率

**Dashboard:** 核保员产能

**业务背景:** 核保经理每月看一次:**我的 35 个核保员,谁的配额完成了、谁严重落后**。落后可能因为人不在状态,也可能因为接到的是难啃的大单 (需要更多时间)。月底配额完成率 < 80% 的人需要谈话或调整任务。

**类别:** 聚合 + JOIN
**难度:** 中级
**角色:** 核保经理

**解题思路:** 这条以 `underwriter` 为主表、`LEFT JOIN policy` 统计每个核保员当月签下的保单数。用 LEFT JOIN 而非 INNER 是关键:某个核保员当月一张单都没签,我们仍要让他出现在榜单上(完成率 0%),INNER 会把他整行抹掉。最容易出错的是"当月"怎么取:不能硬编码 `'2026-06'`,因为所有保单的 `bound_at = effective_date - 7~30 天` 且 `effective_date ≤ TODAY-30`,故最近的签单月份其实是 2026-05,硬编码 6 月会让整张看板全为 0。这里用子查询 `STRFTIME('%Y-%m', MAX(bound_at))` 自动取"最近一个有签单的月份",并把这个月份条件写进 LEFT JOIN 的 ON 而非 WHERE(写进 WHERE 会把没签单的人误删)。一行输出代表一个核保员。完成率用 `NULLIF(quota,0)` 防除零,排序用 `col IS NULL, col DESC` 模拟 `NULLS LAST` 兼容老版 SQLite。

```sql
SELECT u.underwriter_id, u.full_name, u.role, u.region,
       u.monthly_quota_policies,
       COUNT(p.policy_id) AS bound_policy_count_this_month,
       ROUND(100.0 * COUNT(p.policy_id) /
             NULLIF(u.monthly_quota_policies, 0), 1) AS quota_attainment_pct,
       ROUND(SUM(p.current_annual_premium_cny), 0) AS premium_bound_this_month_cny
FROM underwriter u
LEFT JOIN policy p ON p.underwriter_id = u.underwriter_id
                  AND STRFTIME('%Y-%m', p.bound_at) =
                      (SELECT STRFTIME('%Y-%m', MAX(bound_at)) FROM policy)
WHERE u.is_active = 1 AND u.role <> '核保经理'
GROUP BY u.underwriter_id, u.full_name, u.role, u.region, u.monthly_quota_policies
ORDER BY quota_attainment_pct IS NULL, quota_attainment_pct DESC;
```

> **关于"当月"取值:** 原写法硬编码 `'2026-06'`,但所有保单 `bound_at = effective_date - 7~30 天`,
> 而 `effective_date ≤ TODAY-30`,故最近的签单月份是 **2026-05**;硬编码 2026-06 会让看板**全为 0**。
> 这里改为子查询 `MAX(bound_at)` 自动取"最近一个有签单的完整月份",数据如何变动都不会失效。
> 排序用 `col IS NULL, col DESC` 模拟 `NULLS LAST`(与文末方言注释一致,兼容老版本 SQLite)。

**预期结果说明:** 35 行 (排除 5 个经理)。完成率 > 100% 是优秀,80-100% 正常,< 80% 需关注。"高级核保员" 的配额是 8 张/月,"初级核保员" 是 3 张/月,完成率统一可比。月中快照 (今天为月内第 21 天的次月) 完成率普遍偏低属正常。

---

## D7: 付款逾期客户预警

**Dashboard:** 财务预警

**业务背景:** 付款逾期 > 30 天的客户,**有更高概率最终违约**。财务经理需要每天看一遍 "重点逾期清单",有针对性地催收。这些客户也会影响续保决策 (underwriter 续保时会查这个名单)。

**类别:** 聚合 + JOIN
**难度:** 中级
**角色:** 财务经理

**解题思路:** 这条把逾期发票按客户聚合,一行输出代表一家有逾期账款的企业。链路是 `company → policy → invoice`,这里的 INNER JOIN 是有意筛掉没有逾期发票的公司——因为只关心欠款客户。`WHERE i.status = '逾期' AND i.due_date < '2026-06-21'` 先把范围缩到真正逾期的发票,再 GROUP BY 公司。逾期天数用 `JULIANDAY('2026-06-21') - JULIANDAY(due_date)` 算,`MAX(...)` 取这家公司最严重的一张(最久未付),`AVG(...)` 取平均逾期程度。注意 `max_days_overdue > 30` 这个过滤是对聚合后的 MAX 值做判断,所以必须写在 HAVING 而非 WHERE。按欠款总额倒序排,让财务经理先盯欠得最多的。

```sql
SELECT c.company_id, c.company_name, c.industry, c.risk_tier,
       COUNT(i.invoice_id) AS overdue_invoice_count,
       ROUND(SUM(i.amount_due_cny), 0) AS overdue_amount_cny,
       MAX(JULIANDAY('2026-06-21') - JULIANDAY(i.due_date)) AS max_days_overdue,
       ROUND(AVG(JULIANDAY('2026-06-21') - JULIANDAY(i.due_date)), 1) AS avg_days_overdue
FROM company c
JOIN policy p ON p.company_id = c.company_id
JOIN invoice i ON i.policy_id = p.policy_id
WHERE i.status = '逾期'
  AND i.due_date < '2026-06-21'
GROUP BY c.company_id, c.company_name, c.industry, c.risk_tier
HAVING max_days_overdue > 30
ORDER BY overdue_amount_cny DESC
LIMIT 50;
```

**预期结果说明:** 通常 30-50 行。max_days_overdue > 90 的客户基本要走法务追款流程。结合 `c.risk_tier='高风险'` 标签,优先级再上一档。

---

## D8: 现场检查整改逾期清单

**Dashboard:** 风控追踪

**业务背景:** 现场检查发现隐患后,客户必须在约定期限内整改 (典型 60-90 天)。**超期未整改的场所,在续保时通常会被加条件**或拒保。这条查询识别隐患发现 > 90 天还 "未开始" 整改的场所。

**类别:** 日期算术
**难度:** 基础
**角色:** 风控经理

**解题思路:** 这条从 `site_inspection` 出发,join `company_location` 拿场所名和城市、再 join `company` 拿企业名,一行输出代表一次发现隐患且尚未整改完成的检查记录。没有聚合,核心逻辑全在 `CASE` 里:用 `JULIANDAY('2026-06-21') - JULIANDAY(inspection_date)` 算检查至今的天数,再根据"未开始且超 90 天""进行中且超 180 天"分级成 urgency_level。WHERE 里 `hazards_identified IS NOT NULL` 是 SQLite 的 NULL 语义要点——只看真发现了隐患的记录,而 NULL 表示无隐患,不能用 `= ''` 之类去判;`remediation_status IN ('未开始','进行中')` 排除已整改完成的。按距今天数倒序,最陈旧的拖延案排最前。

```sql
SELECT c.company_name, cl.location_name, cl.city, cl.province,
       si.inspection_date,
       si.hazards_identified,
       si.remediation_status,
       JULIANDAY('2026-06-21') - JULIANDAY(si.inspection_date) AS days_since_inspection,
       CASE
         WHEN si.remediation_status = '未开始'
              AND JULIANDAY('2026-06-21') - JULIANDAY(si.inspection_date) > 90
              THEN '严重: 超 90 天未整改'
         WHEN si.remediation_status = '进行中'
              AND JULIANDAY('2026-06-21') - JULIANDAY(si.inspection_date) > 180
              THEN '警告: 整改进度过慢'
         ELSE '正常'
       END AS urgency_level
FROM site_inspection si
JOIN company_location cl ON cl.location_id = si.location_id
JOIN company c ON c.company_id = cl.company_id
WHERE si.hazards_identified IS NOT NULL
  AND si.remediation_status IN ('未开始', '进行中')
ORDER BY days_since_inspection DESC
LIMIT 50;
```

**预期结果说明:** 30-50 行。"严重" 级别的场所是优先整改对象,通知 broker 督促客户。"警告" 级别的场所应安排复查。

---

## D9: 欺诈信号热力图 (按企业)

**Dashboard:** 反欺诈监控

**业务背景:** RAG Agent 训练好后,反欺诈分析师每天扫描一遍 **各企业近期出现 `fraud_signal` 或 `attorney_involvement` 通讯的频次**。频次异常高的企业要列入重点观察名单,后续理赔流程从严。

**类别:** RAG 聚合
**难度:** 中级
**角色:** 反欺诈分析师

**解题思路:** 这条要顺着 `company → policy → claim → claim_communication` 四张表把每条理赔通讯归到企业头上,一行输出代表一家企业的欺诈信号画像。链路一长就有 fan-out 风险:一家公司有多张保单、每张多个 claim、每个 claim 多条通讯,所以"理赔条数"必须用 `COUNT(DISTINCT cl.claim_id)` 去重,否则会被通讯行数放大。各类 signal 的计数用 `SUM(CASE WHEN signal_tag = '...' THEN 1 ELSE 0 END)` 这种条件计数手法,在一次扫描里横向把不同标签分别累加成多列(透视)。`comm_date >= DATE('2026-06-21', '-12 months')` 把窗口限定在近 12 个月。`HAVING fraud_signals + attorney_signals >= 3` 对聚合结果过滤、只留信号够多的企业;排序用 `fraud_signals + attorney_signals * 2` 给律师介入加倍权重(它比单纯欺诈信号更严重)。

```sql
SELECT c.company_id, c.company_name, c.industry,
       COUNT(DISTINCT cl.claim_id) AS total_claims,
       SUM(CASE WHEN cc.signal_tag = 'fraud_signal' THEN 1 ELSE 0 END) AS fraud_signals,
       SUM(CASE WHEN cc.signal_tag = 'attorney_involvement' THEN 1 ELSE 0 END) AS attorney_signals,
       SUM(CASE WHEN cc.signal_tag = 'dispute_escalation' THEN 1 ELSE 0 END) AS dispute_signals,
       ROUND(100.0 * SUM(CASE WHEN cc.signal_tag = 'fraud_signal' THEN 1 ELSE 0 END)
             / NULLIF(COUNT(cc.comm_id), 0), 2) AS fraud_signal_pct
FROM company c
JOIN policy p ON p.company_id = c.company_id
JOIN claim cl ON cl.policy_id = p.policy_id
JOIN claim_communication cc ON cc.claim_id = cl.claim_id
WHERE cc.comm_date >= DATE('2026-06-21', '-12 months')
GROUP BY c.company_id, c.company_name, c.industry
HAVING fraud_signals + attorney_signals >= 3
ORDER BY (fraud_signals + attorney_signals * 2) DESC
LIMIT 30;
```

**预期结果说明:** 通常 20-30 行。`fraud_signals + attorney_signals * 2` 加权排序 (律师介入比欺诈信号严重)。前 10 名企业需上报反欺诈委员会。

---

## D10: 综合续保决策助手 (单家企业 360°)

**Dashboard:** 续保决策助手 ⭐ 核心查询

**业务背景:** 这是 **InsightUnderwriter AI Agent 的核心 SQL** —— 对一家企业拉出续保决策需要的全部维度数据,生成一个推荐结论。Underwriter 把这个结果作为决策初稿,人工复核后最终拍板。

**类别:** CTE 多表 JOIN
**难度:** 高级
**角色:** 核保员

**解题思路:** 这是全文档最复杂的一条,要给单家企业(`company_id = 1`)拉出续保决策需要的全部维度,最后输出 1 行 360° 画像 + AI 推荐。难点在于这些维度散落在六七张互不相干的表里(财务、loss_run、理赔信号、付款、监管、信用),如果直接把它们一路 join 在一起,任意两张的一对多关系都会互相做笛卡尔积、把金额炸成天文数字。正确做法是给每个维度单独建一个 CTE、各自先聚合成"该公司一行",最后用 `company_profile LEFT JOIN` 把这些单行结果横向拼起来——用 LEFT JOIN 是因为某些维度可能缺数据(比如这家公司从没被监管处罚),缺了也要保留主行、用 `COALESCE` 把 NULL 补 0,而不是让整行消失。每个 CTE 内部都把 `WHERE company_id = 1` 下推,先缩小数据量再聚合。最后的 `CASE` 把多维信号翻译成 ai_recommendation。生产环境把 `= 1` 改成参数就能批量跑。

```sql
WITH company_profile AS (
  SELECT company_id, company_name, industry, risk_tier,
         employee_count, founded_year,
         total_active_premium_cny, total_paid_claims_cny
  FROM company WHERE company_id = 1
),
fin_latest AS (
  SELECT company_id, MAX(fiscal_year) AS latest_year,
         (SELECT revenue_cny FROM company_financial
          WHERE company_id = 1 ORDER BY fiscal_year DESC LIMIT 1) AS latest_revenue,
         (SELECT debt_to_equity_ratio FROM company_financial
          WHERE company_id = 1 ORDER BY fiscal_year DESC LIMIT 1) AS latest_debt_ratio
  FROM company_financial WHERE company_id = 1
  GROUP BY company_id
),
loss_3y AS (
  SELECT company_id,
         SUM(total_premium_cny) AS prem_3y,
         SUM(total_losses_cny)  AS loss_3y,
         ROUND(SUM(total_losses_cny) * 1.0 / NULLIF(SUM(total_premium_cny), 0), 3) AS lr_3y
  FROM loss_run WHERE company_id = 1 AND year >= 2023
  GROUP BY company_id
),
risk_signals AS (
  SELECT p.company_id,
         COUNT(DISTINCT CASE WHEN cl.status = '已拒赔' THEN cl.claim_id END) AS rejected_count,
         COUNT(DISTINCT CASE WHEN cc.signal_tag IN ('fraud_signal','attorney_involvement')
                             THEN cc.comm_id END) AS hi_risk_signals
  FROM policy p
  LEFT JOIN claim cl ON cl.policy_id = p.policy_id
  LEFT JOIN claim_communication cc ON cc.claim_id = cl.claim_id
  WHERE p.company_id = 1
  GROUP BY p.company_id
),
pay_behavior AS (
  SELECT p.company_id,
         ROUND(AVG(pm.days_late), 1) AS avg_days_late,
         SUM(CASE WHEN pm.days_late > 30 THEN 1 ELSE 0 END) AS severe_late_count
  FROM policy p
  JOIN invoice i ON i.policy_id = p.policy_id
  JOIN payment pm ON pm.invoice_id = i.invoice_id
  WHERE p.company_id = 1
  GROUP BY p.company_id
),
reg_summary AS (
  SELECT company_id,
         COUNT(*) AS reg_violations,
         SUM(fine_amount_cny) AS total_fines_cny
  FROM regulatory_filing
  WHERE company_id = 1 AND filing_date >= DATE('2026-06-21', '-3 years')
  GROUP BY company_id
),
credit_latest AS (
  SELECT company_id, credit_rating, rating_change, report_date
  FROM third_party_report
  WHERE company_id = 1
  ORDER BY report_date DESC LIMIT 1
)
SELECT cp.company_name, cp.industry, cp.risk_tier,
       fl.latest_revenue, fl.latest_debt_ratio,
       lo.lr_3y AS loss_ratio_3y, lo.prem_3y, lo.loss_3y,
       rs.rejected_count, rs.hi_risk_signals,
       pb.avg_days_late, pb.severe_late_count,
       COALESCE(rg.reg_violations, 0) AS reg_violations,
       COALESCE(rg.total_fines_cny, 0) AS total_fines_cny,
       cr.credit_rating, cr.rating_change,
       CASE
         WHEN lo.lr_3y > 1.0 OR rs.hi_risk_signals > 5
              OR cr.credit_rating IN ('BB','B','CCC') THEN '建议拒保'
         WHEN lo.lr_3y > 0.85 OR pb.severe_late_count > 2
              OR COALESCE(rg.reg_violations, 0) > 3 THEN '建议有条件续保'
         WHEN lo.lr_3y > 0.70 THEN '建议续保 + 涨价 15-25%'
         WHEN lo.lr_3y > 0.55 THEN '建议续保 + 涨价 5-10%'
         ELSE '建议续保 + 维持价格 (优质客户)'
       END AS ai_recommendation
FROM company_profile cp
LEFT JOIN fin_latest fl ON fl.company_id = cp.company_id
LEFT JOIN loss_3y lo ON lo.company_id = cp.company_id
LEFT JOIN risk_signals rs ON rs.company_id = cp.company_id
LEFT JOIN pay_behavior pb ON pb.company_id = cp.company_id
LEFT JOIN reg_summary rg ON rg.company_id = cp.company_id
LEFT JOIN credit_latest cr ON cr.company_id = cp.company_id;
```

**预期结果说明:** 1 行。把 6 个 CTE 的结果 LEFT JOIN 合并,得到该企业的完整 360° 画像 + AI 推荐结论。生产环境中把 `WHERE company_id = 1` 改为参数,即可批量为所有到期保单生成推荐。

---

## D11: 行业基准对比仪表盘

**Dashboard:** 行业对标

**业务背景:** 单独看一家企业的赔付率 75% 是高是低?**必须和行业基准对比**。建筑施工行业 75% 是低于平均的优秀,但金融服务行业 75% 是远高于平均的危险。这条查询批量输出各企业的实际 LR 与行业平均的偏差。

**类别:** JOIN + 聚合
**难度:** 中级
**角色:** 核保经理

**解题思路:** 这条把每家企业的实际赔付率和它所在行业的基准赔付率并排对比,一行输出代表一条 loss_run 记录(企业 × 年 × 险种)。`loss_run` 已经预聚好了赔付率,所以不必再去碰 claim 明细。关键 join 是 `loss_run JOIN company`(拿到该公司的 industry)再 `LEFT JOIN industry_benchmark ON ib.industry = c.industry AND ib.year = lr.year`——用 LEFT JOIN 是因为某些行业某些年份可能没有基准数据,缺了也要保留公司这一行(此时 variance 为 NULL)而不是把它丢掉。注意 join 基准时务必同时匹配 industry 和 year 两个键,只匹配 industry 会让一家公司对上该行业所有年份的基准、造成 fan-out。`WHERE lr.year = 2025` 锁定考察年。CASE 按公司 LR 是行业均值的多少倍分档成"严重高于/略高于/优于/平均"。

```sql
SELECT c.company_name, c.industry, lr.year, lr.policy_type,
       lr.loss_ratio AS company_lr,
       ib.avg_loss_ratio AS industry_avg_lr,
       ROUND((lr.loss_ratio - ib.avg_loss_ratio) * 100, 2) AS variance_pct,
       CASE
         WHEN lr.loss_ratio > ib.avg_loss_ratio * 1.30 THEN '严重高于行业'
         WHEN lr.loss_ratio > ib.avg_loss_ratio * 1.10 THEN '略高于行业'
         WHEN lr.loss_ratio < ib.avg_loss_ratio * 0.80 THEN '优于行业'
         ELSE '行业平均水平'
       END AS classification
FROM loss_run lr
JOIN company c ON c.company_id = lr.company_id
LEFT JOIN industry_benchmark ib ON ib.industry = c.industry AND ib.year = lr.year
WHERE lr.year = 2025
ORDER BY variance_pct DESC
LIMIT 50;
```

**预期结果说明:** 50 行。Variance 排前 10 的企业是 **必须涨价或拒保** 的对象 (赔付率远高于行业)。Variance 排后 10 的是 **必须留住的优质客户**。

---

## D12: 监管处罚分布 (按机构 + 年度)

**Dashboard:** 合规监控

**业务背景:** 合规总监要清楚 **我们的客户群体在哪些监管机构面前频繁出问题**。如果 70% 的处罚集中在应急管理部,说明在保客户多为高危行业,需在风控策略上强化"安全生产" 复检。

**类别:** 透视聚合
**难度:** 中级
**角色:** 合规总监

**解题思路:** 这条只需 `regulatory_filing` 一张表,把处罚按"机构 × 年度"两个维度交叉聚合,一行输出代表某机构某年的处罚汇总。年度用 `STRFTIME('%Y', filing_date)` 从日期里抽出来当分组键——这是 SQLite 取年份的标准写法。`COUNT(*)` 数处罚件数,`COUNT(DISTINCT company_id)` 数涉及的企业数(同一企业可能被同一机构罚多次,所以要 DISTINCT 才能反映"多少家公司中招"),`SUM/AVG(fine_amount_cny)` 算罚款总额和均值,`SUM(CASE WHEN resolution_status = '进行中' THEN 1 ELSE 0 END)` 这种条件计数统计还没结案的件数。`WHERE filing_date >= '2024-01-01'` 限定近几年。GROUP BY 两个键、ORDER BY 年份倒序加罚款额倒序。

```sql
SELECT agency,
       STRFTIME('%Y', filing_date) AS year,
       COUNT(*) AS violation_count,
       COUNT(DISTINCT company_id) AS company_count,
       ROUND(SUM(fine_amount_cny), 0) AS total_fines_cny,
       ROUND(AVG(fine_amount_cny), 0) AS avg_fine_cny,
       SUM(CASE WHEN resolution_status = '进行中' THEN 1 ELSE 0 END) AS unresolved_count
FROM regulatory_filing
WHERE filing_date >= '2024-01-01'
GROUP BY agency, year
ORDER BY year DESC, total_fines_cny DESC;
```

**预期结果说明:** 约 20-25 行 (7 机构 × 3 年)。重点看 unresolved_count 比例高的机构 (我们的客户没在配合整改),以及罚款均值最高的机构 (单次重罚意味着严重违规)。

---

## D13: 信用评级下调企业追踪

**Dashboard:** 评级监控

**业务背景:** 信用评级下调通常 **早于财务报表暴雷 3-6 个月**。财务总监要重点关注被下调评级的客户:其 现有保单的应收账款是否能收回?要不要立即触发条款,暂停新承保?

**类别:** 窗口函数
**难度:** 高级
**角色:** 财务总监

**解题思路:** 这条要在 `third_party_report` 里找出"最新一份报告标记为评级下调"的企业。难点是每家公司有多份历史报告,既要拿到每家的最新一条、又要知道它相对上一条评级是升是降。一个 CTE 配两个 window function 一次搞定:`LAG(credit_rating) OVER (PARTITION BY company_id ORDER BY report_date)` 把每条报告的上一次评级拉到同一行,`ROW_NUMBER() OVER (PARTITION BY company_id ORDER BY report_date DESC)` 给每家公司的报告按时间倒序编号、`rn = 1` 即最新一条。外层 join `company` 拿企业名和在保保费,WHERE 过滤 `rn = 1 AND rating_change = '下调' AND credit_rating IN (...)`,一行输出代表一家最新评级被下调到投资级边缘以下的企业。这里用窗口函数而非 GROUP BY,是因为我们要保留每条报告的明细行(尤其 prev_rating),不是做汇总。按在保保费倒序,优先盯敞口大的。

```sql
WITH ranked AS (
  SELECT tpr.company_id, tpr.report_date, tpr.credit_rating, tpr.rating_change,
         LAG(tpr.credit_rating, 1) OVER (
           PARTITION BY tpr.company_id ORDER BY tpr.report_date
         ) AS prev_rating,
         ROW_NUMBER() OVER (
           PARTITION BY tpr.company_id ORDER BY tpr.report_date DESC
         ) AS rn
  FROM third_party_report tpr
)
SELECT c.company_name, c.industry, c.risk_tier,
       r.report_date AS latest_report_date,
       r.prev_rating AS previous_rating,
       r.credit_rating AS current_rating,
       r.rating_change,
       ROUND(c.total_active_premium_cny, 0) AS at_risk_premium_cny,
       ROUND(c.total_paid_claims_cny, 0) AS historic_claims_paid_cny
FROM ranked r
JOIN company c ON c.company_id = r.company_id
WHERE r.rn = 1
  AND r.rating_change = '下调'
  AND r.credit_rating IN ('BBB', 'BB', 'B', 'CCC')
ORDER BY c.total_active_premium_cny DESC
LIMIT 30;
```

**预期结果说明:** 通常 20-30 行。at_risk_premium 高的企业 (在保保费 > 50 万) 是优先关注对象 —— 若客户暴雷,这部分保费可能成坏账,且未来理赔时客户可能没钱付免赔额。

---

## D14: 保费滑动告警 (一年内 ≥ 3 次批改)

**Dashboard:** 保费监控

**业务背景:** "保费滑动" 是 InsightUnderwriter 设计的特有信号 —— 一张保单短期内反复批改保费,说明 **初承时风险评估不准**,或者 **客户业务变动剧烈**。两种情况都需要在续保时彻底重新核保 (类似 B2B SaaS 中的 "stage_transition slip" 信号)。

**类别:** 聚合 + HAVING
**难度:** 中级
**角色:** 核保经理

**解题思路:** 这条找出一年内被反复批改保费的保单。主表是 `policy_premium_history`(每次保费变动一行),join `policy` 和 `company` 只为了拿保单号和企业名,不影响聚合粒度。按 policy 维度 GROUP BY 后:`COUNT(*) FILTER (WHERE change_event_type = '批改')` 只数"批改"类事件(排除初承等其他事件类型),`MIN/MAX(new_premium_cny)` 取这段时间保费的最低和最高点、相减得 premium_swing,再算波动百分比。`changed_at >= DATE('2026-06-21', '-12 months')` 把窗口限定在近一年。`HAVING endorsement_count >= 3` 对聚合后的批改次数过滤、只留反复批改的保单,一行输出代表一张这样的保单。SQLite 注意点:`FILTER (WHERE ...)` 需要 3.30+,老版本要改写成 `SUM(CASE WHEN ... THEN 1 ELSE 0 END)`;除法分母用 `NULLIF(...,0)` 防零。

```sql
SELECT pph.policy_id, p.policy_number, c.company_name, p.policy_type,
       COUNT(*) FILTER (WHERE pph.change_event_type = '批改') AS endorsement_count,
       ROUND(MIN(pph.new_premium_cny), 0) AS min_premium_cny,
       ROUND(MAX(pph.new_premium_cny), 0) AS max_premium_cny,
       ROUND(MAX(pph.new_premium_cny) - MIN(pph.new_premium_cny), 0) AS premium_swing_cny,
       ROUND((MAX(pph.new_premium_cny) - MIN(pph.new_premium_cny))
             * 100.0 / NULLIF(MIN(pph.new_premium_cny), 0), 1) AS swing_pct
FROM policy_premium_history pph
JOIN policy p ON p.policy_id = pph.policy_id
JOIN company c ON c.company_id = p.company_id
WHERE pph.changed_at >= DATE('2026-06-21', '-12 months')
GROUP BY pph.policy_id, p.policy_number, c.company_name, p.policy_type
HAVING endorsement_count >= 3
ORDER BY swing_pct DESC
LIMIT 30;
```

**预期结果说明:** 通常 15-30 行。swing_pct > 30% 的保单是 **必须续保时全部重审** 的对象。这类保单的 underwriter 也应当被关注 (是否常常初承定价偏差太大)。

---

## D15: Adjuster 在办案件量

**Dashboard:** 理赔产能

**业务背景:** 每个理赔员有 case_load_capacity 上限 (15-35 件)。理赔经理每天看这个看板,谁 **接案数 > capacity 的 80%** 就不能再分案了,否则案件处理质量下降、容易出错赔。

**类别:** 聚合 + JOIN
**难度:** 基础
**角色:** 理赔经理

**解题思路:** 这条以 `claim_adjuster` 为主表、`LEFT JOIN claim` 统计每个理赔员手上的在办案件数,一行输出代表一个理赔员。用 LEFT JOIN 而非 INNER 很关键:一个手上一件在办案都没有的理赔员,我们也要让他出现(利用率 0%),好让经理把新案分给他;INNER 会把空闲的人整行抹掉,正好得到相反结论。"在办"的口径 `cl.status IN ('已立案','调查中','定损中')` 要写进 LEFT JOIN 的 ON 条件而非 WHERE——写进 WHERE 会把那些没有在办案件的理赔员误删(因为他们 join 出来的 claim 行全是 NULL,被 WHERE 过滤掉)。`COUNT(cl.claim_id)` 对 LEFT JOIN 产生的 NULL 自动不计数,所以空闲的人正确地得到 0。CASE 按 `case_load_capacity` 判满负荷。

```sql
SELECT a.adjuster_id, a.full_name, a.specialty_claim_type, a.region,
       a.case_load_capacity,
       COUNT(cl.claim_id) AS active_case_count,
       ROUND(100.0 * COUNT(cl.claim_id) / a.case_load_capacity, 1) AS utilization_pct,
       CASE
         WHEN COUNT(cl.claim_id) >= a.case_load_capacity THEN '满负荷'
         WHEN COUNT(cl.claim_id) >= a.case_load_capacity * 0.8 THEN '接近满负荷'
         ELSE '正常'
       END AS workload_status
FROM claim_adjuster a
LEFT JOIN claim cl ON cl.adjuster_id = a.adjuster_id
                  AND cl.status IN ('已立案', '调查中', '定损中')   -- "未结案/在办"统一定义 (见 KPI 字典 16.3)
GROUP BY a.adjuster_id, a.full_name, a.specialty_claim_type,
         a.region, a.case_load_capacity
ORDER BY utilization_pct DESC;
```

**预期结果说明:** 25 行。重点处理 "满负荷" 和 "接近满负荷" 的人,把新案件转给 "正常" 状态的同事。长期 "满负荷" 的人需评估是否培训不足或专长不匹配。

---

# 业务问题风格查询 (B1–B35)

每条解决一个临时性分析问题,探索性更强。

---

## B1: 客户基本档案 + 经营场所概览

**主题域:** A 客户画像

**业务背景:** Underwriter 接到一份续保申请,第一件事是了解 "客户是谁"。这条查询拉出企业基本信息 + 全部经营场所 + 每个场所的财产价值和风险等级。决策时心里要有数 —— 是单一办公室企业还是跨省多场所大集团?

**类别:** JOIN
**难度:** 基础
**角色:** 核保员

**解题思路:** 这条给单家企业(`company_id = 1`)拉出基本档案 + 全部经营场所概览,输出 1 行。`company` 是一对多关系连到 `company_location`(一家公司多个场所),所以要 `LEFT JOIN` 后按 company GROUP BY 把多个场所折叠回一行——用 LEFT 而非 INNER,是为了让一个场所都没登记的公司也能出现(此时场所相关聚合为 0/NULL)。`COUNT(cl.location_id)` 数场所数,`SUM(property_value_cny)` 加总财产价值看敞口,`GROUP_CONCAT(DISTINCT province)` 把覆盖省份拼成一串(SQLite 特有函数,PostgreSQL 对应 `STRING_AGG`),`SUM(CASE WHEN location_risk_level='高' THEN 1 ELSE 0 END)` 条件计数数出高风险场所数。因为只看一家公司,不会有其他公司的场所混进来,一次 GROUP BY 就够。

```sql
SELECT c.company_id, c.company_name, c.industry, c.risk_tier,
       c.employee_count, c.founded_year,
       COUNT(cl.location_id) AS location_count,
       ROUND(SUM(cl.property_value_cny), 0) AS total_property_value_cny,
       GROUP_CONCAT(DISTINCT cl.province) AS provinces_covered,
       SUM(CASE WHEN cl.location_risk_level = '高' THEN 1 ELSE 0 END) AS high_risk_locations
FROM company c
LEFT JOIN company_location cl ON cl.company_id = c.company_id
WHERE c.company_id = 1
GROUP BY c.company_id;
```

**预期结果说明:** 1 行。total_property_value 反映了 underwriter 要评估的财产敞口规模。high_risk_locations > 0 需在保单上加针对性条款。

---

## B2: 财务健康年度趋势 (LAG 同比)

**主题域:** A 客户画像

**业务背景:** 财务恶化往往先于理赔暴增。这条查询输出一家企业近 5 年财务的年度同比变化:营收涨/跌、负债率上/下、净利润增/减。**连续 2 年负向**的企业续保要特别小心。

**类别:** 窗口函数
**难度:** 中级
**角色:** 财务分析师

**解题思路:** 这条只碰 `company_financial` 一张表,看单家企业(`company_id = 1`)逐年的财务同比变化,一行输出代表一个会计年度。核心是 window function `LAG(revenue_cny) OVER (ORDER BY fiscal_year)`——它把上一年的营收拉到当年这一行,从而能在同一行里算同比增长率,不必自连接表去找"上一年"。增长率分母用 `NULLIF(LAG(...),0)` 防止上一年营收为 0 时除零。这里之所以用窗口函数而非 GROUP BY,是因为我们要保留每一年的明细行做趋势对比,而不是汇总成一个数。利润率 `net_profit / revenue` 同理。ORDER BY fiscal_year DESC 让最新年份排在最上方,方便一眼看最近趋势。

```sql
SELECT fiscal_year,
       ROUND(revenue_cny, 0) AS revenue,
       LAG(revenue_cny) OVER (ORDER BY fiscal_year) AS prev_revenue,
       ROUND((revenue_cny - LAG(revenue_cny) OVER (ORDER BY fiscal_year))
             * 100.0 / NULLIF(LAG(revenue_cny) OVER (ORDER BY fiscal_year), 0), 2) AS revenue_growth_pct,
       ROUND(debt_to_equity_ratio, 3) AS debt_ratio,
       ROUND(net_profit_cny, 0) AS net_profit,
       ROUND(net_profit_cny * 100.0 / NULLIF(revenue_cny, 0), 2) AS profit_margin_pct
FROM company_financial
WHERE company_id = 1
ORDER BY fiscal_year DESC;
```

**预期结果说明:** 3-5 行。健康企业 revenue_growth_pct > 5% 且 profit_margin_pct > 5%。连续年份 profit_margin 为负 = 高风险。

---

## B3: 信用评级变化历史时间线

**主题域:** A 客户画像

**业务背景:** 单看 "当前评级 BBB" 信息有限,要看 **评级走势**:从 A 跌到 BBB 是恶化中,从 BB 涨到 BBB 是好转中。窗口函数把每次评级和上一次拉到同一行,便于看变化。

**类别:** 窗口函数
**难度:** 中级
**角色:** 财务分析师

**解题思路:** 这条只碰 `third_party_report` 一张表,把单家企业(`company_id = 1`)历次信用评级排成时间线,一行输出代表一份评级报告。和 B2 一样靠 window function `LAG(...) OVER (ORDER BY report_date)`,把上一次的评级和上一次的报告日期拉到当前行,从而在同一行里既看到"从什么评级变成什么评级",又能算两次评级间隔了多少天 `JULIANDAY(本次) - JULIANDAY(上次)`。LAG 在第一行没有前序记录时返回 NULL,对应日期差也是 NULL,这是正常的(时间线起点)。用窗口函数而不是 GROUP BY,因为目标是保留每条记录看演进、不是汇总。ORDER BY report_date 升序让时间线从早到晚。

```sql
SELECT report_date, credit_rating, rating_change, report_source,
       LAG(credit_rating, 1) OVER (ORDER BY report_date) AS previous_rating,
       LAG(report_date, 1) OVER (ORDER BY report_date) AS previous_date,
       JULIANDAY(report_date) - JULIANDAY(LAG(report_date, 1) OVER (ORDER BY report_date)) AS days_between
FROM third_party_report
WHERE company_id = 1
ORDER BY report_date;
```

**预期结果说明:** 通常 2-4 行。frequent rating changes (< 90 天间隔) 反映评级机构对企业的不确定性,本身就是风险信号。

---

## B4: 高负债率企业清单 (Top 50)

**主题域:** A 客户画像

**业务背景:** 资产负债率 > 1.5 的企业在保险业内被视为 "财务紧张",在保单到期续保时要重点审视付款能力。这条查询输出最危险的 50 家企业。

**类别:** 聚合 + 排序
**难度:** 基础
**角色:** 风控经理

**解题思路:** 这条要列出负债率最高的 50 家企业,关键陷阱是"每家公司在 `company_financial` 里有多年记录,只能取最新一年那条"。如果直接 join 而不限定年份,一家公司会出现多行(每年一行)、榜单被历史数据污染。这里用一个相关子查询 `cf.fiscal_year = (SELECT MAX(fiscal_year) FROM company_financial WHERE company_id = c.company_id)` 写进 join 的 ON 条件,把每家公司锁定到它自己的最新财年那一行——注意子查询里的 `company_id = c.company_id` 是和外层公司关联的,保证"各取各的最新年"。`WHERE debt_to_equity_ratio > 1.5` 过滤财务紧张的,一行输出代表一家这样的企业。这里不需要 GROUP BY,因为 join 后已是每公司一行;直接 ORDER BY 负债率倒序 + LIMIT 50。

```sql
SELECT c.company_id, c.company_name, c.industry, c.risk_tier,
       cf.fiscal_year, cf.debt_to_equity_ratio,
       ROUND(cf.revenue_cny, 0) AS revenue,
       ROUND(cf.total_liabilities_cny, 0) AS total_liab,
       ROUND(c.total_active_premium_cny, 0) AS active_premium
FROM company c
JOIN company_financial cf ON cf.company_id = c.company_id
  AND cf.fiscal_year = (
    SELECT MAX(fiscal_year) FROM company_financial WHERE company_id = c.company_id
  )
WHERE cf.debt_to_equity_ratio > 1.5
ORDER BY cf.debt_to_equity_ratio DESC
LIMIT 50;
```

**预期结果说明:** 50 行 (按最危险排序)。结合 active_premium > 50 万的企业要立即上报风险委员会。

---

## B5: 财务恶化 + 高赔付率双重信号企业

**主题域:** A 客户画像

**业务背景:** **两个独立信号同时出现 = 严重红色预警**。一家公司既财务在恶化 (负债率上升 / 净利润下降),又赔付率已经高了 —— 这是 "客户即将拒赔/逃单" 的经典前兆。这条 CTE 查询同时筛选这两个维度。

**类别:** CTE + 多表
**难度:** 高级
**角色:** 核保经理

```sql
WITH latest_fin AS (
  SELECT company_id, debt_to_equity_ratio, net_profit_cny
  FROM company_financial cf
  WHERE fiscal_year = (
    SELECT MAX(fiscal_year) FROM company_financial WHERE company_id = cf.company_id
  )
),
loss_summary AS (
  SELECT company_id,
         ROUND(SUM(total_losses_cny) * 1.0 / NULLIF(SUM(total_premium_cny), 0), 3) AS lr_avg
  FROM loss_run WHERE year >= 2024
  GROUP BY company_id
)
SELECT c.company_id, c.company_name, c.industry,
       lf.debt_to_equity_ratio, lf.net_profit_cny,
       ls.lr_avg,
       ROUND(c.total_active_premium_cny, 0) AS active_premium
FROM company c
JOIN latest_fin lf ON lf.company_id = c.company_id
JOIN loss_summary ls ON ls.company_id = c.company_id
WHERE lf.debt_to_equity_ratio > 1.2
  AND lf.net_profit_cny < 0
  AND ls.lr_avg > 0.80
ORDER BY ls.lr_avg DESC, lf.debt_to_equity_ratio DESC
LIMIT 30;
```

**预期结果说明:** 通常 5-15 行 (双重筛选,数量不多)。这些就是核保委员会的 "必须讨论" 清单。

---

## B6: Top 保费客户排行 (Top 25)

**主题域:** B 保单承保

**业务背景:** CEO 月度会议想知道 **谁是公司的金主**。**前 10 名客户贡献多少保费占比** 反映 "客户集中度风险" —— 集中度太高 (前 10 占 > 30%) 意味着失去任一大客户就伤筋动骨。

**类别:** 聚合 + 排序
**难度:** 基础
**角色:** CEO / CRO

```sql
SELECT c.company_id, c.company_name, c.industry, c.risk_tier,
       COUNT(DISTINCT p.policy_id) AS active_policy_count,
       ROUND(c.total_active_premium_cny, 0) AS total_active_premium_cny,
       ROUND(100.0 * c.total_active_premium_cny
             / SUM(c.total_active_premium_cny) OVER (), 2) AS pct_of_book
FROM company c
LEFT JOIN policy p ON p.company_id = c.company_id AND p.status = '有效'
WHERE c.total_active_premium_cny > 0
GROUP BY c.company_id, c.company_name, c.industry, c.risk_tier,
         c.total_active_premium_cny
ORDER BY c.total_active_premium_cny DESC
LIMIT 25;
```

**预期结果说明:** 25 行。看 pct_of_book 累计:Top 10 累计 > 30% 是集中度警戒线;Top 25 累计 > 50% 是危险线。

---

## B7: 各险种保费规模占比

**主题域:** B 保单承保

**业务背景:** 公司战略要看产品组合。**商业财产险占 60%、责任险占 30%、其他 10%** 是典型的"重财产、轻责任"组合。承保副总要决定明年是否要发力责任险产品线。

**类别:** 聚合
**难度:** 基础
**角色:** 承保副总

```sql
SELECT policy_type,
       COUNT(*) AS policy_count,
       ROUND(SUM(current_annual_premium_cny), 0) AS total_premium_cny,
       ROUND(100.0 * SUM(current_annual_premium_cny)
             / SUM(SUM(current_annual_premium_cny)) OVER (), 2) AS pct_of_total,
       ROUND(AVG(current_annual_premium_cny), 0) AS avg_premium_per_policy
FROM policy
WHERE status = '有效'
GROUP BY policy_type
ORDER BY total_premium_cny DESC;
```

**预期结果说明:** 8 行 (8 大险种)。pct_of_total 反映产品组合,avg_premium 反映单笔规模 (财产险通常更大额)。

---

## B8: 保单批改频度分布

**主题域:** B 保单承保

**业务背景:** 批改 (endorsement) 频度是 underwriter 工作质量的反向指标 —— 一张保单中途反复批改,通常是初承时风险评估不够全面。这条查询输出 "0 次 / 1 次 / 2 次 / 3+ 次" 批改保单的数量分布。

**类别:** 聚合 + 分桶
**难度:** 基础
**角色:** 核保经理

```sql
SELECT bucket,
       COUNT(*) AS policy_count,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS pct
FROM (
  SELECT p.policy_id,
         CASE
           WHEN endorsement_count = 0 THEN '0 (无批改)'
           WHEN endorsement_count = 1 THEN '1 次'
           WHEN endorsement_count = 2 THEN '2 次'
           ELSE '3+ 次 (异常)'
         END AS bucket
  FROM policy p
  LEFT JOIN (
    SELECT policy_id, COUNT(*) AS endorsement_count
    FROM policy_endorsement GROUP BY policy_id
  ) pe ON pe.policy_id = p.policy_id
)
GROUP BY bucket
ORDER BY bucket;
```

**预期结果说明:** 4 行。"3+ 次 (异常)" 占比应 < 10%,否则核保流程要返工优化。

---

## B9: 单张保单完整保费历史溯源

**主题域:** B 保单承保

**业务背景:** Underwriter 在续保某张保单时,常被问 "这张保单去年为什么涨了 30%?"。这条查询调出该保单从初承到最近一次调整的全部 premium_history,用窗口函数显示每一步的累计变化。

**类别:** 窗口函数
**难度:** 中级
**角色:** 核保员

```sql
SELECT change_event_type, changed_at,
       ROUND(previous_premium_cny, 0) AS prev,
       ROUND(new_premium_cny, 0) AS new,
       ROUND(change_amount_cny, 0) AS delta,
       change_pct,
       change_reason,
       ROUND(SUM(change_amount_cny) OVER (
         ORDER BY changed_at ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
       ), 0) AS cumulative_change_cny
FROM policy_premium_history
WHERE policy_id = 1
ORDER BY changed_at;
```

**预期结果说明:** 通常 2-5 行 (1 次初承 + 0-4 次批改)。cumulative_change_cny 显示从开始至今的总变动。

---

## B10: 续保决策准确性 (决策 vs 后续赔付率)

**主题域:** B 保单承保

**业务背景:** **续保决策是否做对了?** 当时被 "续保 + 涨价" 的客户,后续赔付率是不是真的下降了?当时被 "拒保" 的客户被竞品接走后是不是更频繁出险?这条 CTE 分析帮助核保部门复盘决策模型。

**类别:** CTE + 多表
**难度:** 高级
**角色:** 核保经理

```sql
WITH dec AS (   -- 去重到 (company, decision): 同一公司同一决策只算一次, 避免 loss_run 翻倍
  SELECT DISTINCT p.company_id, rd.decision
  FROM renewal_decision rd
  JOIN policy p ON p.policy_id = rd.policy_id
  WHERE rd.decision_date BETWEEN '2025-01-01' AND '2025-12-31'   -- 决策年 (本数据集续保决策最早 2025-05)
),
lr_next AS (    -- 后续(次年)赔付: loss_run 先按 company 聚成单行, 再与决策集合 JOIN, 不按决策条数翻倍
  SELECT company_id,
         SUM(total_losses_cny) AS post_loss,
         SUM(total_premium_cny) AS post_prem
  FROM loss_run
  WHERE year = 2026                                              -- 决策之后的承保年度
  GROUP BY company_id
)
SELECT d.decision,
       COUNT(DISTINCT d.company_id) AS company_count,
       ROUND(SUM(lr.post_prem), 0) AS subsequent_premium_cny,
       ROUND(SUM(lr.post_loss), 0) AS subsequent_losses_cny,
       ROUND(SUM(lr.post_loss) * 1.0 / NULLIF(SUM(lr.post_prem), 0), 3) AS subsequent_loss_ratio
FROM dec d
JOIN lr_next lr ON lr.company_id = d.company_id
GROUP BY d.decision
ORDER BY subsequent_loss_ratio DESC;
```

> **日期窗 (重要):** 本数据集保单 `effective_date ≥ 2024-06-21`、保期 365 天,最早到期在 2025-06,
> 故**续保决策最早出现在 2025**(无 2024 决策)。因此决策窗取 **2025**、后续赔付取承保年度 **2026**,
> 语义为"2025 的续保决策 → 2026 的后续赔付率",否则查询会静默返回空。
> **修复扇出:** `dec` 去重到 (company, decision),`loss_run` 先按 company 聚成单行再 JOIN,绝对值不会按决策条数虚高。

**预期结果说明:** 3 行 (3 种决策结果)。理想情况:"续保" 类后续 LR 应较低 (优质客户),"有条件续保" 类介于二者间 (说明 "条件" 起了作用);"拒保" 类样本较少 —— 注意决策按保单记录,一家公司若仅个别保单被拒保、其余仍有效,该公司 2026 仍可能有 loss_run,故 "拒保" 组未必为空。

---

## B11: 风险评分 vs 实际赔付率相关性

**主题域:** B 保单承保

**业务背景:** **核保员的风险打分到底准不准?** 如果打高分 (危险) 的保单后续果然赔付高,打低分 (安全) 的果然赔付低 —— 打分模型有效。如果毫无相关性,说明打分纯属拍脑袋。

**类别:** CTE + 分桶
**难度:** 高级
**角色:** 精算 / 数据分析师

```sql
WITH policy_risk AS (
  SELECT p.policy_id, p.current_annual_premium_cny,
         ROUND(AVG(ra.risk_score), 0) AS avg_risk_score
  FROM policy p
  JOIN risk_assessment ra ON ra.policy_id = p.policy_id
  GROUP BY p.policy_id, p.current_annual_premium_cny
),
policy_loss AS (
  SELECT p.policy_id, COALESCE(SUM(cl.paid_amount_cny), 0) AS total_paid
  FROM policy p
  LEFT JOIN claim cl ON cl.policy_id = p.policy_id
  GROUP BY p.policy_id
)
SELECT
  CASE
    WHEN pr.avg_risk_score < 40 THEN '低风险 (0-39)'
    WHEN pr.avg_risk_score < 60 THEN '中低 (40-59)'
    WHEN pr.avg_risk_score < 75 THEN '中高 (60-74)'
    ELSE '高风险 (75-100)'
  END AS risk_band,
  COUNT(*) AS policy_count,
  ROUND(AVG(pr.avg_risk_score), 1) AS avg_score,
  ROUND(AVG(pl.total_paid * 1.0 / NULLIF(pr.current_annual_premium_cny, 0)), 3) AS avg_loss_ratio
FROM policy_risk pr
JOIN policy_loss pl ON pl.policy_id = pr.policy_id
GROUP BY risk_band
ORDER BY avg_score;
```

**预期结果说明:** 4 行。理想:avg_loss_ratio 应随 risk_band 单调递增 (低风险 0.3 → 中低 0.5 → 中高 0.7 → 高风险 0.9)。如各档 LR 类似 (都 0.6 上下),说明打分系统失效需重训练。

---

## B12: 直销 vs 经纪渠道质量对比

**主题域:** B 保单承保

**业务背景:** 公司有约 15% 的保单是直销 (broker_id IS NULL),其余通过 broker。**直销客户通常质量更高** (主动找上门的多是有清晰需求的好客户),但量小。这条查询量化对比两个渠道的赔付率、续保率。

**类别:** 聚合 + 对比
**难度:** 中级
**角色:** 渠道总监

```sql
WITH pol AS (   -- 每张保单一行 (含其已付赔款合计), 避免 policy×claim 扇出
  SELECT p.policy_id,
         CASE WHEN p.broker_id IS NULL THEN '直销' ELSE '经纪渠道' END AS channel,
         p.current_annual_premium_cny,
         (SELECT COALESCE(SUM(cl.paid_amount_cny), 0)
          FROM claim cl WHERE cl.policy_id = p.policy_id) AS paid_cny
  FROM policy p
  WHERE p.status IN ('有效', '已到期')
)
SELECT channel,
       COUNT(*) AS policy_count,
       ROUND(SUM(current_annual_premium_cny), 0) AS total_premium_cny,
       ROUND(SUM(paid_cny), 0) AS total_paid_cny,
       ROUND(SUM(paid_cny) * 1.0
             / NULLIF(SUM(current_annual_premium_cny), 0), 3) AS channel_loss_ratio,
       ROUND(AVG(current_annual_premium_cny), 0) AS avg_premium_per_policy
FROM pol
GROUP BY channel;
```

> **修复扇出:** 原 `policy LEFT JOIN claim` 后 `SUM/AVG(p.current_annual_premium_cny)` 会被 claim 行数放大,
> 使 `channel_loss_ratio` 分母虚高、`avg_premium_per_policy` 失真。这里先把每张保单的赔款用相关子查询聚合到 policy 粒度,保证每张保单的保费只计一次。

**预期结果说明:** 2 行。典型情况:直销 LR ~0.55,经纪渠道 LR ~0.70。若直销 LR 也很高 = 公司主动找上的客户也质量差,可能定价过松。

---

## B13: 各企业三年累计赔付率

**主题域:** C 理赔

**业务背景:** 续保决策的核心数据。**3 年累计 LR > 80% 的企业大概率被拒保**。这条查询输出每家企业近 3 年总保费、总赔款、累计 LR,是 underwriter 调取最高频的查询。

**类别:** 聚合 + JOIN
**难度:** 基础
**角色:** 核保员

```sql
SELECT c.company_id, c.company_name, c.industry, c.risk_tier,
       SUM(lr.total_premium_cny) AS prem_3y,
       SUM(lr.total_losses_cny)  AS loss_3y,
       ROUND(SUM(lr.total_losses_cny) * 1.0
             / NULLIF(SUM(lr.total_premium_cny), 0), 3) AS loss_ratio_3y,
       SUM(lr.claim_frequency) AS claim_count_3y
FROM company c
JOIN loss_run lr ON lr.company_id = c.company_id
WHERE lr.year >= 2023
GROUP BY c.company_id, c.company_name, c.industry, c.risk_tier
HAVING loss_ratio_3y > 0
ORDER BY loss_ratio_3y DESC
LIMIT 30;
```

**预期结果说明:** 30 行 (按最差排序)。loss_ratio_3y > 1.0 = 三年赔的钱已超保费收入,几乎肯定拒保。

---

## B14: 平均结案天数 (按险种)

**主题域:** C 理赔

**业务背景:** **不同险种的理赔难度不同**。简单的财产损失 (机器烧了换一台) 30 天能结,人身伤害 (员工受伤) 因为医疗周期长可能 6 个月。理赔经理用这个看哪些险种结案慢,人员配置是否合理。

**类别:** 日期算术 + 聚合
**难度:** 中级
**角色:** 理赔经理

```sql
WITH closed_claims AS (
  SELECT cl.claim_id, cl.claim_type, cl.reported_date,
         MAX(ce.event_date) AS closed_at
  FROM claim cl
  JOIN claim_event ce ON ce.claim_id = cl.claim_id
  WHERE cl.status = '已结案' AND ce.event_type = '结案归档'
  GROUP BY cl.claim_id, cl.claim_type, cl.reported_date
)
SELECT claim_type,
       COUNT(*) AS closed_count,
       ROUND(AVG(JULIANDAY(closed_at) - JULIANDAY(reported_date)), 1) AS avg_days_to_close,
       ROUND(MIN(JULIANDAY(closed_at) - JULIANDAY(reported_date)), 1) AS min_days,
       ROUND(MAX(JULIANDAY(closed_at) - JULIANDAY(reported_date)), 1) AS max_days
FROM closed_claims
GROUP BY claim_type
ORDER BY avg_days_to_close DESC;
```

**预期结果说明:** ~9 行 (9 种 claim_type)。avg_days_to_close > 150 的险种考虑增加专职 adjuster。

---

## B15: 大额理赔 Top 30

**主题域:** C 理赔

**业务背景:** **大额理赔 (paid > 100 万)** 是高管必须关注的事件,需要复盘:能否避免?是否要再保险分摊?这条查询拉出最大的 30 笔理赔,用于年度 CEO 复盘材料。

**类别:** 排序 + JOIN
**难度:** 基础
**角色:** 理赔总监

```sql
SELECT cl.claim_id, cl.claim_number, c.company_name, c.industry,
       cl.claim_type, cl.incident_date, cl.status,
       ROUND(cl.loss_amount_cny, 0) AS loss_amount,
       ROUND(cl.paid_amount_cny, 0) AS paid_amount,
       ROUND(cl.paid_amount_cny * 100.0 / NULLIF(cl.loss_amount_cny, 0), 1) AS pay_ratio_pct,
       a.full_name AS adjuster_name
FROM claim cl
JOIN policy p ON p.policy_id = cl.policy_id
JOIN company c ON c.company_id = p.company_id
JOIN claim_adjuster a ON a.adjuster_id = cl.adjuster_id
WHERE cl.paid_amount_cny > 1000000
ORDER BY cl.paid_amount_cny DESC
LIMIT 30;
```

**预期结果说明:** 30 行。pay_ratio_pct 接近 100% 说明几乎全赔 (定损时无核减), < 70% 说明大量核减 (可能有部分拒赔)。

---

## B16: 出险至报案延迟分析 (道德风险信号)

**主题域:** C 理赔

**业务背景:** **报案延迟 > 7 天有道德风险** —— 客户可能在凑证据、串供、甚至自行处理后再来报案。这条查询输出报案延迟分布,识别异常案件。

**类别:** 日期算术 + 分桶
**难度:** 中级
**角色:** 反欺诈分析师

```sql
SELECT
  CASE
    WHEN JULIANDAY(reported_date) - JULIANDAY(incident_date) = 0 THEN '当日报案'
    WHEN JULIANDAY(reported_date) - JULIANDAY(incident_date) <= 1 THEN '1 天内'
    WHEN JULIANDAY(reported_date) - JULIANDAY(incident_date) <= 3 THEN '2-3 天'
    WHEN JULIANDAY(reported_date) - JULIANDAY(incident_date) <= 7 THEN '4-7 天'
    WHEN JULIANDAY(reported_date) - JULIANDAY(incident_date) <= 14 THEN '8-14 天 (警戒)'
    ELSE '> 14 天 (高风险)'
  END AS reporting_lag,
  COUNT(*) AS claim_count,
  ROUND(AVG(loss_amount_cny), 0) AS avg_loss,
  ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS pct
FROM claim
GROUP BY reporting_lag
ORDER BY MIN(JULIANDAY(reported_date) - JULIANDAY(incident_date));
```

**预期结果说明:** 6 行。"> 14 天" 类别通常占 < 5%,若占比异常高,需排查是否有系统性的报案障碍 (例如内部理赔流程慢)。

---

## B17: 准备金反复上调的危险案件

**主题域:** C 理赔

**业务背景:** 与 D5 类似,但聚焦 "增长幅度" 而非次数。**reserve 从 10 万涨到 100 万** (10 倍) 比 "从 80 万涨到 100 万" (25%) 严重得多。用窗口函数显示增长轨迹。

**类别:** 聚合 + 窗口
**难度:** 高级
**角色:** 理赔经理

```sql
WITH reserve_journey AS (
  SELECT cr.claim_id, cr.reserve_date, cr.reserve_amount_cny,
         FIRST_VALUE(cr.reserve_amount_cny) OVER (
           PARTITION BY cr.claim_id ORDER BY cr.reserve_date
         ) AS initial_reserve,
         LAST_VALUE(cr.reserve_amount_cny) OVER (
           PARTITION BY cr.claim_id ORDER BY cr.reserve_date
           ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
         ) AS latest_reserve,
         COUNT(*) OVER (PARTITION BY cr.claim_id) AS adjustment_count
  FROM claim_reserve cr
)
SELECT DISTINCT rj.claim_id, cl.claim_number, c.company_name,
       cl.status,
       ROUND(rj.initial_reserve, 0) AS initial_reserve,
       ROUND(rj.latest_reserve, 0) AS latest_reserve,
       ROUND(rj.latest_reserve / NULLIF(rj.initial_reserve, 0), 2) AS multiplier,
       rj.adjustment_count
FROM reserve_journey rj
JOIN claim cl ON cl.claim_id = rj.claim_id
JOIN policy p ON p.policy_id = cl.policy_id
JOIN company c ON c.company_id = p.company_id
WHERE rj.adjustment_count >= 2
  AND rj.latest_reserve / NULLIF(rj.initial_reserve, 0) > 1.5
ORDER BY multiplier DESC
LIMIT 25;
```

**预期结果说明:** 25 行。multiplier > 3 是严重案件,通常意味着案情失控 (诉讼扩大或医疗费暴涨)。

---

## B18: 理赔状态分布 (各企业)

**主题域:** C 理赔

**业务背景:** 一家企业 "未结案件" 占比反映理赔健康度。**未结案件 > 30%** 说明案件处理滞后或争议多。Underwriter 在续保时不仅看历史已赔金额,还要看未结案件的潜在赔付。

**类别:** 透视聚合
**难度:** 中级
**角色:** 核保员

```sql
SELECT c.company_name, c.industry,
       COUNT(*) AS total_claims,
       SUM(CASE WHEN cl.status = '已结案' THEN 1 ELSE 0 END) AS closed,
       SUM(CASE WHEN cl.status = '已支付' THEN 1 ELSE 0 END) AS paid,
       SUM(CASE WHEN cl.status IN ('调查中','定损中','已立案') THEN 1 ELSE 0 END) AS open,
       SUM(CASE WHEN cl.status = '已拒赔' THEN 1 ELSE 0 END) AS rejected,
       ROUND(100.0 * SUM(CASE WHEN cl.status IN ('调查中','定损中','已立案') THEN 1 ELSE 0 END)
             / COUNT(*), 1) AS open_pct
FROM company c
JOIN policy p ON p.company_id = c.company_id
JOIN claim cl ON cl.policy_id = p.policy_id
GROUP BY c.company_id, c.company_name, c.industry
HAVING total_claims >= 5
ORDER BY open_pct DESC
LIMIT 30;
```

**预期结果说明:** 30 行 (按未结比例排序)。open_pct > 40% 的企业续保时要把 "未结案件潜在赔付" 加进决策模型。

---

## B19: 已拒赔理赔分析

**主题域:** C 理赔

**业务背景:** 拒赔是双方都不想要的结果 —— 客户不满、保险公司可能被告。**为什么拒了?哪些险种拒赔率最高?** 用这条查询复盘拒赔模式,优化条款表述、避免不必要的争议。

**类别:** 聚合 + JOIN
**难度:** 中级
**角色:** 理赔总监

```sql
SELECT cl.claim_type, p.policy_type,
       COUNT(*) AS rejected_count,
       ROUND(AVG(cl.loss_amount_cny), 0) AS avg_loss_amount,
       ROUND(SUM(cl.loss_amount_cny), 0) AS total_avoided_payout
FROM claim cl
JOIN policy p ON p.policy_id = cl.policy_id
WHERE cl.status = '已拒赔'
GROUP BY cl.claim_type, p.policy_type
ORDER BY rejected_count DESC
LIMIT 25;
```

**预期结果说明:** 25 行。total_avoided_payout 是拒赔为公司"省下"的钱,但要平衡 —— 拒赔多说明条款限制严,可能被市场觉得"难赔"而流失客户。

---

## B20: 公司跨年度赔付率变化趋势 (Window)

**主题域:** C 理赔

**业务背景:** 单看 2024 年 LR 80% 不算最差,但如果是从 2022 的 50% → 2023 的 65% → 2024 的 80% 一路上升 —— 这是 **趋势恶化**,比单点高更危险。窗口函数显示同比变化。

**类别:** 窗口函数
**难度:** 高级
**角色:** 核保经理

```sql
WITH yearly AS (
  SELECT company_id, year,
         ROUND(SUM(total_losses_cny) * 1.0 / NULLIF(SUM(total_premium_cny), 0), 3) AS lr
  FROM loss_run
  GROUP BY company_id, year
)
SELECT c.company_name, c.industry,
       y.year, y.lr,
       LAG(y.lr) OVER (PARTITION BY y.company_id ORDER BY y.year) AS prev_lr,
       ROUND(y.lr - LAG(y.lr) OVER (PARTITION BY y.company_id ORDER BY y.year), 3) AS yoy_change
FROM yearly y
JOIN company c ON c.company_id = y.company_id
WHERE y.company_id = 1
ORDER BY y.year;
```

**预期结果说明:** 通常 3-5 行 (一家公司的年度赔付率走势)。连续两年 yoy_change > 0.15 是续保 "必须涨价或拒保" 信号。

---

## B21: 各企业欺诈信号统计 (RAG)

**主题域:** D 非结构化

**业务背景:** 这条查询是 RAG Agent 的核心训练标签源。**统计每家企业历史上 fraud_signal 通讯出现的频率**,并匹配最常见的子类标签 —— 后续 LLM 微调时,这就是 "异常企业 vs 正常企业" 的 ground truth。

**类别:** 聚合 + JOIN
**难度:** 中级
**角色:** 反欺诈分析师

```sql
SELECT c.company_id, c.company_name, c.industry,
       COUNT(cc.comm_id) AS fraud_comm_count,
       COUNT(DISTINCT cc.claim_id) AS affected_claim_count,
       GROUP_CONCAT(DISTINCT cc.sub_tag) AS sub_tags_seen
FROM company c
JOIN policy p ON p.company_id = c.company_id
JOIN claim cl ON cl.policy_id = p.policy_id
JOIN claim_communication cc ON cc.claim_id = cl.claim_id
WHERE cc.signal_tag = 'fraud_signal'
GROUP BY c.company_id, c.company_name, c.industry
HAVING fraud_comm_count >= 2
ORDER BY fraud_comm_count DESC
LIMIT 30;
```

**预期结果说明:** 通常 25-30 行。重点关注 affected_claim_count > 3 的企业 (多个案件出现欺诈信号,系统性问题)。

---

## B22: 含律师介入 claim 的损失金额对比

**主题域:** D 非结构化

**业务背景:** **有律师介入的案件,平均赔付金额比普通案件高多少?** 这个数据对法务部门估算 "诉讼成本 vs 和解成本" 极其重要。如果律师案 +50% 赔付,主动和解通常更划算。

**类别:** 子查询 + 对比
**难度:** 中级
**角色:** 法务

```sql
SELECT category,
       COUNT(*) AS claim_count,
       ROUND(AVG(paid_amount_cny), 0) AS avg_paid,
       ROUND(AVG(loss_amount_cny), 0) AS avg_loss_reported,
       ROUND(AVG(paid_amount_cny) * 100.0 / NULLIF(AVG(loss_amount_cny), 0), 1) AS pay_rate_pct
FROM (
  SELECT cl.claim_id, cl.paid_amount_cny, cl.loss_amount_cny,
    CASE WHEN EXISTS (
      SELECT 1 FROM claim_communication cc
      WHERE cc.claim_id = cl.claim_id AND cc.signal_tag = 'attorney_involvement'
    ) THEN '有律师介入' ELSE '无律师介入' END AS category
  FROM claim cl
  WHERE cl.status IN ('已结案', '已支付', '已拒赔')
)
GROUP BY category;
```

**预期结果说明:** 2 行。预期 "有律师介入" 类 avg_paid 高 30-50%,且 pay_rate_pct 也高 (因为律师案件保险公司不敢压定损)。

---

## B23: signal_tag × claim_type 矩阵

**主题域:** D 非结构化

**业务背景:** **哪些险种最容易出现欺诈?** 财产损失类容易出现 "虚增损失";人身伤害容易出现 "夸大医疗费"。这个矩阵帮助风险分析师把反欺诈资源精准投放。

**类别:** 透视
**难度:** 中级
**角色:** 风险分析师

```sql
SELECT cl.claim_type,
       SUM(CASE WHEN cc.signal_tag = 'fraud_signal' THEN 1 ELSE 0 END) AS fraud,
       SUM(CASE WHEN cc.signal_tag = 'dispute_escalation' THEN 1 ELSE 0 END) AS dispute,
       SUM(CASE WHEN cc.signal_tag = 'attorney_involvement' THEN 1 ELSE 0 END) AS attorney,
       SUM(CASE WHEN cc.signal_tag = 'settlement_negotiation' THEN 1 ELSE 0 END) AS settlement,
       SUM(CASE WHEN cc.signal_tag = 'investigation_note' THEN 1 ELSE 0 END) AS investigation,
       SUM(CASE WHEN cc.signal_tag = 'normal_cooperative' THEN 1 ELSE 0 END) AS normal,
       COUNT(*) AS total
FROM claim cl
JOIN claim_communication cc ON cc.claim_id = cl.claim_id
GROUP BY cl.claim_type
ORDER BY fraud DESC;
```

**预期结果说明:** 9 行 (9 种 claim_type)。看 fraud 列哪几种险种最多 —— 这些是反欺诈优先线。

---

## B24: 隐患整改逾期清单

**主题域:** D 非结构化

**业务背景:** 与 D8 类似,但 B24 不只看 "未开始",连 "进行中超过 6 个月" 也算逾期。**这些是续保时必须 "整改完成才续保" 的客户**。

**类别:** 日期算术 + CASE
**难度:** 中级
**角色:** 风控经理

```sql
SELECT c.company_name, cl.city, cl.location_name,
       si.inspection_date, si.hazards_identified, si.remediation_status,
       JULIANDAY('2026-06-21') - JULIANDAY(si.inspection_date) AS days_since,
       CASE
         WHEN si.remediation_status = '未开始'
              AND JULIANDAY('2026-06-21') - JULIANDAY(si.inspection_date) > 60 THEN '严重逾期'
         WHEN si.remediation_status = '进行中'
              AND JULIANDAY('2026-06-21') - JULIANDAY(si.inspection_date) > 180 THEN '进度过慢'
         ELSE '正常'
       END AS verdict
FROM site_inspection si
JOIN company_location cl ON cl.location_id = si.location_id
JOIN company c ON c.company_id = cl.company_id
WHERE si.hazards_identified IS NOT NULL
  AND si.remediation_status IN ('未开始', '进行中')
  AND JULIANDAY('2026-06-21') - JULIANDAY(si.inspection_date) > 60
ORDER BY days_since DESC;
```

**预期结果说明:** 通常 30-80 行 (逾期场所)。verdict='严重逾期' 是必须立即沟通的对象。

---

## B25: 通讯作者活跃度 (XOR 模式)

**主题域:** D 非结构化

**业务背景:** 这条查询演示 XOR 字段的处理 —— **统计每个核保员/理赔员写了多少条通讯**。用 'U'||id / 'A'||id 前缀技巧统一 ID 空间。

**类别:** XOR + 聚合
**难度:** 中级
**角色:** 数据分析师

```sql
WITH unified AS (
  SELECT CASE WHEN author_underwriter_id IS NOT NULL
              THEN 'U' || author_underwriter_id
              ELSE 'A' || author_adjuster_id END AS author_key,
         CASE WHEN author_underwriter_id IS NOT NULL THEN 'Underwriter'
              ELSE 'Adjuster' END AS author_role,
         comm_id, signal_tag
  FROM claim_communication
)
SELECT author_key, author_role,
       COUNT(*) AS comm_count,
       SUM(CASE WHEN signal_tag = 'fraud_signal' THEN 1 ELSE 0 END) AS fraud_comms,
       SUM(CASE WHEN signal_tag = 'attorney_involvement' THEN 1 ELSE 0 END) AS attorney_comms
FROM unified
GROUP BY author_key, author_role
ORDER BY comm_count DESC
LIMIT 30;
```

**预期结果说明:** 30 行。理赔员通常居前 (因为绝大多数通讯由 adjuster 起草)。fraud_comms 比例高的人是反欺诈方面的专家,可考虑安排难案。

---

## B26: 客户付款行为评级分桶

**主题域:** E 付款

**业务背景:** 把客户的付款行为分成 4 档:**优秀 / 良好 / 一般 / 差** —— 续保时可作为加分/减分项目。

**类别:** CASE + 聚合
**难度:** 中级
**角色:** 财务经理

```sql
WITH cust_pay AS (
  SELECT c.company_id, c.company_name,
         COUNT(pm.payment_id) AS payment_count,
         AVG(pm.days_late) AS avg_days_late,
         SUM(CASE WHEN pm.days_late > 30 THEN 1 ELSE 0 END) AS severe_late_count
  FROM company c
  JOIN policy p ON p.company_id = c.company_id
  JOIN invoice i ON i.policy_id = p.policy_id
  JOIN payment pm ON pm.invoice_id = i.invoice_id
  GROUP BY c.company_id, c.company_name
  HAVING payment_count >= 4
)
SELECT
  CASE
    WHEN avg_days_late <= 0 AND severe_late_count = 0 THEN '优秀'
    WHEN avg_days_late <= 7 AND severe_late_count <= 1 THEN '良好'
    WHEN avg_days_late <= 20 THEN '一般'
    ELSE '差'
  END AS payment_grade,
  COUNT(*) AS company_count,
  ROUND(AVG(avg_days_late), 1) AS bucket_avg_days_late
FROM cust_pay
GROUP BY payment_grade
ORDER BY bucket_avg_days_late;
```

**预期结果说明:** 4 行。优秀客户应占大头 (>50%)。"差" 类客户名单导出后给催收和续保部门。

---

## B27: 严重逾期客户名单 + 在保保费

**主题域:** E 付款

**业务背景:** **客户欠了大量保费,但还有大额保单未到期 —— 风险最高**。如果不催回,这部分保费就成坏账;若续保期间持续逾期,可能被监管认定为变相赊销。

**类别:** JOIN + 聚合
**难度:** 中级
**角色:** 信用风险

```sql
SELECT c.company_name, c.industry,
       COUNT(DISTINCT i.invoice_id) AS overdue_invoices,
       ROUND(SUM(i.amount_due_cny), 0) AS total_overdue_cny,
       ROUND(c.total_active_premium_cny, 0) AS active_premium_at_risk
FROM company c
JOIN policy p ON p.company_id = c.company_id
JOIN invoice i ON i.policy_id = p.policy_id
WHERE i.status = '逾期'
GROUP BY c.company_id, c.company_name, c.industry,
         c.total_active_premium_cny
HAVING total_overdue_cny > 50000
ORDER BY total_overdue_cny DESC
LIMIT 50;
```

**预期结果说明:** 50 行。total_overdue / active_premium > 30% 的客户是 "欠的保费已经占在保规模 30%" 的危险户。

---

## B28: 应收账款账龄分析

**主题域:** E 付款

**业务背景:** 财务月报必备指标:**应收账款按账龄分桶** (0-30 天 / 30-60 / 60-90 / 90-180 / > 180)。> 90 天的款项就要计提坏账准备。

**类别:** 日期分桶
**难度:** 中级
**角色:** 财务经理

```sql
SELECT
  CASE
    WHEN JULIANDAY('2026-06-21') - JULIANDAY(due_date) <= 0 THEN '未到期'
    WHEN JULIANDAY('2026-06-21') - JULIANDAY(due_date) <= 30 THEN '0-30 天'
    WHEN JULIANDAY('2026-06-21') - JULIANDAY(due_date) <= 60 THEN '30-60 天'
    WHEN JULIANDAY('2026-06-21') - JULIANDAY(due_date) <= 90 THEN '60-90 天'
    WHEN JULIANDAY('2026-06-21') - JULIANDAY(due_date) <= 180 THEN '90-180 天 (准坏账)'
    ELSE '> 180 天 (坏账风险)'
  END AS aging_bucket,
  COUNT(*) AS invoice_count,
  ROUND(SUM(amount_due_cny), 0) AS total_amount_cny
FROM invoice
WHERE status IN ('待支付', '逾期')
GROUP BY aging_bucket
ORDER BY MIN(JULIANDAY('2026-06-21') - JULIANDAY(due_date));
```

**预期结果说明:** 6 行。"> 180 天" 桶的金额要全部计入坏账准备 (按会计准则)。

---

## B29: 付款行为 vs 赔付率相关性

**主题域:** E 付款

**业务背景:** **行业经验:付款不及时的客户,往往也是赔付率高的客户**。验证这个假设。如果相关性强,可以将 "付款行为" 作为风险评分的输入特征之一。

**类别:** CTE + 聚合
**难度:** 高级
**角色:** RevOps

```sql
WITH pay_band AS (
  SELECT c.company_id,
         CASE
           WHEN AVG(pm.days_late) <= 0 THEN '准时'
           WHEN AVG(pm.days_late) <= 15 THEN '略晚'
           WHEN AVG(pm.days_late) <= 45 THEN '中度逾期'
           ELSE '严重逾期'
         END AS pay_band
  FROM company c
  JOIN policy p ON p.company_id = c.company_id
  JOIN invoice i ON i.policy_id = p.policy_id
  JOIN payment pm ON pm.invoice_id = i.invoice_id
  GROUP BY c.company_id
  HAVING COUNT(pm.payment_id) >= 4
),
lr_band AS (
  SELECT company_id,
         ROUND(SUM(total_losses_cny) * 1.0 / NULLIF(SUM(total_premium_cny), 0), 3) AS lr_3y
  FROM loss_run
  WHERE year >= 2023
  GROUP BY company_id
)
SELECT pb.pay_band,
       COUNT(*) AS company_count,
       ROUND(AVG(lb.lr_3y), 3) AS avg_loss_ratio
FROM pay_band pb
JOIN lr_band lb ON lb.company_id = pb.company_id
GROUP BY pb.pay_band
ORDER BY avg_loss_ratio;
```

**预期结果说明:** 4 行。预期:"准时" 客户 LR ~0.60,"严重逾期" 客户 LR ~0.85 —— 验证假设。若各桶 LR 相近,假设不成立。

---

## B30: 行业风险等级与平均赔付率对照

**主题域:** F 外部

**业务背景:** 验证 `risk_tier` 与实际赔付率的关系。这条数据可用于校准 "风险等级 → 保费乘数" 的精算模型。

**类别:** JOIN
**难度:** 基础
**角色:** 精算师

```sql
SELECT c.industry, c.risk_tier,
       COUNT(DISTINCT c.company_id) AS company_count,
       ROUND(AVG(lr.loss_ratio), 3) AS avg_loss_ratio
FROM company c
JOIN loss_run lr ON lr.company_id = c.company_id
WHERE lr.year >= 2024
GROUP BY c.industry, c.risk_tier
ORDER BY c.industry, c.risk_tier;
```

**预期结果说明:** ~40 行 (10 行业 × 4 等级)。同行业内 LR 应随 risk_tier 单调递增。

---

## B31: 监管处罚密度排行 (各企业)

**主题域:** F 外部

**业务背景:** 累计处罚次数最多的企业是合规高风险户。这个名单要和 underwriter 共享,续保时务必核查最新处罚状态。

**类别:** 聚合 + 排序
**难度:** 基础
**角色:** 合规经理

```sql
SELECT c.company_name, c.industry,
       COUNT(rf.filing_id) AS violation_count,
       ROUND(SUM(rf.fine_amount_cny), 0) AS total_fines_cny,
       GROUP_CONCAT(DISTINCT rf.agency) AS agencies_involved,
       SUM(CASE WHEN rf.resolution_status = '进行中' THEN 1 ELSE 0 END) AS unresolved_count
FROM company c
JOIN regulatory_filing rf ON rf.company_id = c.company_id
GROUP BY c.company_id, c.company_name, c.industry
ORDER BY violation_count DESC
LIMIT 30;
```

**预期结果说明:** 30 行。violation_count > 5 是极高风险,基本应拒保。

---

## B32: 信用评级下调企业的后续赔付率

**主题域:** F 外部

**业务背景:** **信用评级下调是否真的预示赔付率上升?** 如果是,信用监控就是有效的早期预警系统。

**类别:** CTE + 多表
**难度:** 高级
**角色:** RevOps

```sql
WITH downgraded AS (
  SELECT DISTINCT company_id,
         MIN(report_date) AS first_downgrade_date
  FROM third_party_report
  WHERE rating_change = '下调'
    AND report_date BETWEEN '2024-01-01' AND '2024-12-31'
  GROUP BY company_id
),
post_lr AS (
  SELECT lr.company_id,
         ROUND(SUM(lr.total_losses_cny) * 1.0 / NULLIF(SUM(lr.total_premium_cny), 0), 3) AS lr_2025
  FROM loss_run lr WHERE lr.year = 2025
  GROUP BY lr.company_id
),
control_group AS (
  SELECT c.company_id
  FROM company c
  WHERE c.company_id NOT IN (SELECT company_id FROM downgraded)
)
SELECT '评级下调企业 2025 LR' AS metric,
       ROUND(AVG(pl.lr_2025), 3) AS avg_lr,
       COUNT(*) AS company_count
FROM downgraded d
JOIN post_lr pl ON pl.company_id = d.company_id
UNION ALL
SELECT '对照组 (未下调) 2025 LR' AS metric,
       ROUND(AVG(pl.lr_2025), 3) AS avg_lr,
       COUNT(*) AS company_count
FROM control_group cg
JOIN post_lr pl ON pl.company_id = cg.company_id;
```

**预期结果说明:** 2 行对比。若 "下调企业" avg_lr 明显高于 "对照组",证明信用监控有效。

---

## B33: 高罚款企业的保单组合

**主题域:** F 外部

**业务背景:** **罚款总额 > 50 万的企业**,在我们这里还有哪些有效保单?需立即拉清单,评估总敞口。

**类别:** JOIN + 聚合
**难度:** 中级
**角色:** 合规经理

```sql
WITH high_fine AS (
  SELECT company_id, SUM(fine_amount_cny) AS total_fine
  FROM regulatory_filing
  WHERE filing_date >= DATE('2026-06-21', '-3 years')
  GROUP BY company_id
  HAVING total_fine > 500000
)
SELECT c.company_name, c.industry,
       ROUND(hf.total_fine, 0) AS total_fines_3y,
       COUNT(p.policy_id) AS active_policy_count,
       ROUND(SUM(p.current_annual_premium_cny), 0) AS active_premium_cny
FROM high_fine hf
JOIN company c ON c.company_id = hf.company_id
LEFT JOIN policy p ON p.company_id = c.company_id AND p.status = '有效'
GROUP BY c.company_id, c.company_name, c.industry, hf.total_fine
ORDER BY total_fines_3y DESC;
```

**预期结果说明:** 通常 20-40 行。active_premium > 30 万的企业是合规 + 承保联合关注对象。

---

## B34: 行业基准偏离最大企业 Top N

**主题域:** F 外部

**业务背景:** 与 D11 类似,但聚焦 **偏离最大的极值**。极正偏 (远高于行业) → 立即调整;极负偏 (远好于行业) → 是市场拓展的标杆案例。

**类别:** JOIN + 排序
**难度:** 中级
**角色:** 承保副总

```sql
WITH variance AS (
  SELECT c.company_id, c.company_name, c.industry,
         lr.loss_ratio AS company_lr,
         ib.avg_loss_ratio AS industry_avg,
         lr.loss_ratio - ib.avg_loss_ratio AS abs_var
  FROM loss_run lr
  JOIN company c ON c.company_id = lr.company_id
  JOIN industry_benchmark ib ON ib.industry = c.industry AND ib.year = lr.year
  WHERE lr.year = 2025
)
SELECT * FROM (
  SELECT '极差客户 (偏高)' AS category, * FROM variance ORDER BY abs_var DESC LIMIT 15
)
UNION ALL
SELECT * FROM (
  SELECT '标杆客户 (偏低)' AS category, * FROM variance ORDER BY abs_var ASC LIMIT 15
);
```

> **SQLite 方言提示:** 复合查询 (UNION ALL) 中,只有最末一个 SELECT 才能直接带 `ORDER BY/LIMIT`。
> 因此把每个分支的 `ORDER BY ... LIMIT 15` 包进子查询 `SELECT * FROM (...)`,否则 SQLite 会报
> `ORDER BY clause should come after UNION ALL not before`。

**预期结果说明:** 30 行 (两组各 15 行)。"标杆客户" 名单可用于销售部门的 "续保更优惠" 留客方案。

---

## B35: 多维度风险综合评分排行

**主题域:** F 外部

**业务背景:** 终极风险评分。**综合财务、赔付、合规、信用、欺诈信号 5 个维度**,生成 0-100 的综合风险分,作为续保决策的 AI 模型 baseline 特征。

**类别:** CTE 大综合
**难度:** 高级
**角色:** 核保经理

```sql
WITH fin_score AS (
  SELECT company_id,
         CASE WHEN MAX(debt_to_equity_ratio) > 2.0 THEN 20
              WHEN MAX(debt_to_equity_ratio) > 1.5 THEN 12
              WHEN MAX(debt_to_equity_ratio) > 1.0 THEN 6
              ELSE 0 END AS fin_pts
  FROM company_financial GROUP BY company_id
),
loss_score AS (
  SELECT company_id,
         CASE WHEN AVG(loss_ratio) > 1.0 THEN 30
              WHEN AVG(loss_ratio) > 0.85 THEN 20
              WHEN AVG(loss_ratio) > 0.70 THEN 10
              ELSE 0 END AS loss_pts
  FROM loss_run WHERE year >= 2023 GROUP BY company_id
),
reg_score AS (
  SELECT company_id,
         CASE WHEN COUNT(*) >= 5 THEN 20
              WHEN COUNT(*) >= 3 THEN 12
              WHEN COUNT(*) >= 1 THEN 5
              ELSE 0 END AS reg_pts
  FROM regulatory_filing
  WHERE filing_date >= DATE('2026-06-21', '-3 years')
  GROUP BY company_id
),
credit_score AS (
  SELECT company_id,
         CASE WHEN credit_rating IN ('BB','B','CCC') THEN 15
              WHEN credit_rating IN ('BBB') THEN 8
              ELSE 0 END AS credit_pts
  FROM third_party_report tpr
  WHERE report_date = (
    SELECT MAX(report_date) FROM third_party_report WHERE company_id = tpr.company_id
  )
),
fraud_score AS (
  SELECT p.company_id,
         CASE WHEN COUNT(cc.comm_id) >= 5 THEN 15
              WHEN COUNT(cc.comm_id) >= 2 THEN 8
              WHEN COUNT(cc.comm_id) >= 1 THEN 3
              ELSE 0 END AS fraud_pts
  FROM policy p
  LEFT JOIN claim cl ON cl.policy_id = p.policy_id
  LEFT JOIN claim_communication cc ON cc.claim_id = cl.claim_id
    AND cc.signal_tag IN ('fraud_signal', 'attorney_involvement')
  GROUP BY p.company_id
)
SELECT c.company_name, c.industry,
       COALESCE(f.fin_pts, 0) AS fin_pts,
       COALESCE(l.loss_pts, 0) AS loss_pts,
       COALESCE(r.reg_pts, 0) AS reg_pts,
       COALESCE(cs.credit_pts, 0) AS credit_pts,
       COALESCE(fr.fraud_pts, 0) AS fraud_pts,
       (COALESCE(f.fin_pts,0) + COALESCE(l.loss_pts,0) + COALESCE(r.reg_pts,0)
        + COALESCE(cs.credit_pts,0) + COALESCE(fr.fraud_pts,0)) AS composite_risk_score
FROM company c
LEFT JOIN fin_score f ON f.company_id = c.company_id
LEFT JOIN loss_score l ON l.company_id = c.company_id
LEFT JOIN reg_score r ON r.company_id = c.company_id
LEFT JOIN credit_score cs ON cs.company_id = c.company_id
LEFT JOIN fraud_score fr ON fr.company_id = c.company_id
ORDER BY composite_risk_score DESC
LIMIT 50;
```

**预期结果说明:** 50 行。composite_risk_score 满分 100,> 60 应进入续保核保委员会,> 80 几乎应拒保。各分项可拆开看 "这家企业风险在哪一维度"。

---

## 查询类别统计

| 类别 | 数量 | 查询编号 |
|------|------|---------|
| 聚合 (Aggregation) | 17 | D1, D4, D6, D7, D9, D12, D15, B1, B4, B6, B7, B8, B13, B19, B27, B30, B31 |
| JOIN 操作 | 14 | D3, D11, B1, B3, B11, B12, B13, B14, B15, B19, B21, B22, B27, B33 |
| 窗口函数 | 6 | D13, B2, B3, B9, B17, B20 |
| 日期分桶/算术 | 7 | D1, D4, D8, B14, B16, B24, B28 |
| 子查询/CTE | 11 | D1, D10, B5, B10, B11, B22, B26, B29, B32, B33, B35 |
| 透视 (Pivot) | 3 | B18, B23, B25 |
| 高级 (CTE + Window 综合) | 10 | D10, D13, B5, B10, B11, B17, B20, B29, B32, B35 |

> 注: 上表为**能力维度覆盖**, 同一条查询可同时归入多个类别 (如既用 JOIN 又用聚合), 故各行数量之和大于 50。

## 角色覆盖

| 角色 | 查询数 | 编号 |
|------|-------|------|
| CEO / CFO / CRO | 3 | D1, B6, D13 |
| 核保经理/副总 | 12 | D2, D4, D6, D11, D14, B5, B8, B10, B20, B30, B34, B35 |
| 核保员 | 5 | D10, B1, B9, B13, B18 |
| 理赔经理/总监 | 7 | D5, D15, B14, B15, B17, B19, D9 |
| 反欺诈/风控/合规 | 7 | D8, D9, D12, B16, B21, B24, B31 |
| 财务/RevOps | 6 | D7, B26, B27, B28, B29, B32 |
| 渠道/法务/精算 | 5 | D3, B11, B12, B22, B30 |

## 难度分布

| 难度 | 数量 | 编号 |
|------|-----|------|
| 基础 | 12 | D4, D8, D15, B1, B4, B6, B7, B8, B13, B15, B30, B31 |
| 中级 | 28 | D1, D2, D3, D5, D6, D7, D9, D11, D12, D14, B2, B3, B9, B12, B14, B16, B18, B19, B21, B22, B23, B24, B25, B26, B27, B28, B33, B34 |
| 高级 | 10 | D10, D13, B5, B10, B11, B17, B20, B29, B32, B35 |

---

## SQLite 方言注释

- 日期算术使用 `JULIANDAY()` 和 `DATE(..., '-N months/years')`,SQLite 特有。PostgreSQL 替换为 `EXTRACT(EPOCH FROM ...)` 或 `INTERVAL`。
- `GROUP_CONCAT()` 是 SQLite 函数,PostgreSQL 用 `STRING_AGG()`。
- 窗口函数要求 SQLite 3.25.0+ (2018-09 后)。
- `FILTER (WHERE ...)` 子句要求 SQLite 3.30+,否则用 `CASE WHEN ... THEN 1 END` 替代。
- `NULLS LAST` 在 SQLite 中用 `ORDER BY col IS NULL, col` 模拟。

## 与 InsightUnderwriter AI Agent 的对接

这些查询在 AI Agent 架构中的角色:

1. **Text2SQL Agent 训练:** 把这 50 条查询作为 (自然语言问题 → SQL) 的训练对,经过几千条人工补充后可微调专用 Text2SQL 模型。
2. **RAG Agent 触发:** 当 D9 / D10 / B21 / B22 等查询返回高风险信号时,触发 RAG 检索 `claim_communication.content` 提取细节。
3. **决策合成 Agent:** 把 D10 / B35 的输出作为推荐结论的核心证据。
4. **数据校验:** 这些查询在新数据接入时,可用于回归测试 (验证关键 KPI 没有破坏性变化)。

典型工作流示例 (类比 ER 文档 17.8):
- 用户问: "Company 1 要不要续保?"
- AI 调度: 调用 D10 (综合 360°) + B35 (风险综合评分) + D9 (欺诈热力图)
- 输出: 推荐结论 + 数据出处链接 + 关键风险点

---

**SQL 查询文档结束。**
