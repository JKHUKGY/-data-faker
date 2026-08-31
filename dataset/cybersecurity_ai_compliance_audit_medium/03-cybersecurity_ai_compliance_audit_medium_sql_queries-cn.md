# 网络安全 - AI合规审计系统 SQL 查询参考

## 概述

本文档提供 **20 个面向业务的 SQL 查询**，针对 `cybersecurity_ai_compliance_audit_medium` 数据集设计。每个查询都解决一个业务相关人员可能提出的实际问题。

> **跨数据库提示:** 所有查询基于 SQLite 3.x 编写。表名 `user` 是 PostgreSQL 等数据库的保留关键字，迁移时需要在 `user` 两边加双引号或反引号（例如 `"user"`）。日期函数 `julianday()`、`strftime()`、`date('now')` 是 SQLite 专有，移植时需替换为目标数据库的等价函数。

> **时间锚点提示:** 数据集采用动态时间锚点（生成时刻为"今天"），所有 `julianday('now')`、`date('now')` 查询在生成器运行后立即执行时具有正确的判别力。

> **业务语境:** 本数据集模拟虚构公司 **Sentinel AI Governance**（一家总部位于波士顿、为中大型企业提供 AI 合规审计平台的 SaaS 公司）的单一客户租户。下面的查询围绕 Sentinel 平台的核心日常工作流（合规审计、风险评估、事件响应、整改追踪、模型治理）展开。完整的公司画像、商业模式、行业科普、角色画像与术语表见 `01-cybersecurity_ai_compliance_audit_medium_business_context-cn.md`；表结构与字段见 `02-cybersecurity_ai_compliance_audit_medium_er_document-cn.md`。

---

## 如何使用本文档

本文档是这个数据集里**最偏教学**的一份。读者设定是一名刚读完业务背景文档和 ER 文档、即将被经理派去"这周把这些查询跑一遍"的实习数据分析师。请按下面的方式使用它：

- **每个查询都有固定的五段式结构**，照着读就能从"看懂问题"一路走到"会写、能用"：
  1. **业务背景** —— 谁在问、为什么现在问、答案要支撑什么决策。
  2. **分类 / 难度 / 业务角色** —— 三个标签，帮你判断该查询练的是什么 SQL 技巧、属于谁的活儿。
  3. **解题思路** —— 在看 SQL 之前，先讲清楚要 join 哪些表、为什么用这种 join、聚合的粒度是什么、为什么用 CTE/窗口函数，以及 SQLite 的坑在哪。**这一段才是学习的重点。**
  4. **SQL** —— 可直接在生成出的 SQLite 上运行的查询。建议先读完解题思路，再对照代码。
  5. **预期结果与业务结论** —— 结果长什么样（行数、列含义、关键量级），以及拿到数字后分析师**下一步该做什么**。跑出数字只是分析的开始，不是结束。
- **每个查询都能回溯到业务背景文档第 5 节的某个业务问题。** 如果一个查询你说不出它回答哪个业务问题，那它就不该出现在这里。
- **SQL 是用来读和学的，不只是用来执行的。** 留意为什么某处是 `LEFT JOIN` 而不是 `INNER JOIN`、为什么分母要 `NULLIF` 包一层、为什么要 `COUNT(DISTINCT ...)`。
- **关于时间锚点：** 本数据集刻意采用"运行时 `now()`"动态锚点，而不是固定的 REFERENCE_DATE 字面量。因此查询中保留 `date('now')` / `julianday('now')`，请在**生成数据后尽快运行**，否则随时间推移 Q19 等查询会失去判别力（详见业务背景文档第 6 节）。

---

## 业务术语表（Glossary）

合规审计领域的关键术语在日常对话中常被混淆，本节明确定义本文档中的用法：

| 术语 | 定义 | 注意事项 |
|------|------|---------|
| **Risk Tier** | `ai_model.risk_tier` 的 4 档枚举：`CRITICAL`, `HIGH`, `MEDIUM`, `LOW` | "High Risk" 在本文档中约定为 `risk_tier IN ('CRITICAL', 'HIGH')`，所有查询保持一致 |
| **Risk Score** | `likelihood_score × impact_score × severity_weight`，单条 risk_assessment 的综合评分（0.9 – 45） | 与 risk_tier 是两个**独立**指标：risk_tier 是模型层级的标签，risk_score 是评估层级的数值 |
| **Coverage Rate** | 已评估控制项 / 控制项总数 | 衡量"审计做完了没"，是**进度**指标，与"是否合规"无关 |
| **Compliance Rate** | COMPLIANT / **Applicable** Assessments | 衡量"已评的是否合规"，是**健康度**指标 |
| **Applicable Assessment** | `compliance_status != 'NOT_APPLICABLE'` 的评估 | NOT_APPLICABLE 表示"该控制不适用于该模型"，**不应**进合规率分母 |
| **Stale Audit** | `last_audit_date IS NULL` 或 距今 > 180 天 | Query 19 的核心定义 |
| **Open Incident** | `status NOT IN ('RESOLVED', 'CLOSED')` | 即 OPEN / INVESTIGATING / CONTAINED 三态 |
| **Open Remediation** | `control_status.is_terminal = 0` | 即 PENDING / IN_PROGRESS / DEFERRED 三态 |
| **Production Model** | `deployment_env = 'production'` AND `is_active = 1` | 注意 `production` 全小写，SQL 比较大小写敏感 |
| **MTTR** | Mean Time To Resolve = `AVG((julianday(resolved_at) - julianday(reported_at)) * 24)` 小时 | 仅对已 RESOLVED/CLOSED 的事件有意义 |
| **Overdue** | `due_date < date('now')` AND 未完成 | 同时要求 `is_terminal = 0` 才算"真逾期" |

---

## 查询使用场景索引

下表把 20 个查询按**真实使用节奏**重组，让读者知道"什么时候应该跑哪个查询"：

| 场景 | 节奏 | 涉及查询 | 主要使用者 |
|------|------|---------|----------|
| **每日晨会** | Daily | Q9（高优先级待办）、Q13（逾期清单） | 运营经理、运营 |
| **每周汇报** | Weekly | Q5（整改完成率）、Q10（审计日志分布）、Q4（事件月度趋势）、Q18（负责人工作量） | 运营经理、安全分析师、合规审计师 |
| **月度复盘** | Monthly | Q8（MTTR）、Q15（type×severity）、Q12（风险类别评估） | 安全分析师、运营经理、分析师 |
| **季度合规审计** | Quarterly | Q14（框架覆盖率与符合率）、Q19（模型审计覆盖）、Q2（框架控制项分布） | 合规经理 |
| **董事会/管理层仪表盘** | Quarterly | Q1（高风险概览）、Q17（生产风险汇总）、Q20（关键指标） | 高管/C-Level |
| **事件触发调查** | Ad-hoc | Q16（用户操作追踪）、Q11（owner 风险责任）、Q3（未缓解高风险） | 合规审计师、风险经理 |
| **HR 治理巡检** | Ad-hoc | Q7（部门活跃度） | 人力经理 |
| **模型上线/退役** | Event-driven | Q1（风险等级核对）、Q19（审计覆盖核对）、Q6（风险排行） | 合规经理、分析师 |

---

## 跨查询一致性约定

为避免读者把"风格略异的查询"误以为不一致，下面列出贯穿 20 个查询的统一约定：

| 概念 | 统一写法 | 出现在 |
|------|---------|--------|
| "high risk" 模型 | `risk_tier IN ('CRITICAL', 'HIGH')` | Q11, Q20 |
| "production" 环境 | `deployment_env = 'production'`（**全小写**） | Q17 |
| "未关闭"事件 | `status NOT IN ('RESOLVED', 'CLOSED')` | Q20 |
| "未完成"整改 | `cs.is_terminal = 0` (JOIN control_status) | Q9, Q13, Q18, Q20 |
| "已完成"整改 | `cs.code = 'COMPLETED'` 或 `status_id = 3` | Q5, Q18 |
| "未缓解"风险 | `mitigation_status = 'NOT_STARTED'` | Q3, Q17, Q20 |
| 时间相对"今天" | `julianday('now')` 或 `date('now')`（运行时） | Q9, Q13, Q19, Q20 |
| 防除零 | `NULLIF(denominator, 0)` | Q14, Q20 |
| 防 row-inflation | `COUNT(DISTINCT CASE WHEN ... THEN id END)` | Q11 |

如果你看到某个查询使用了与上表不同的写法，那是**该查询的业务问题刻意为之**（例如 Q11 的加权 avg_risk_score）——这些差异会在对应查询的"修复说明"或"语义提示"中点明。

---

## 难度阶梯说明

20 个查询从 SQL 入门到高级语义陷阱递进，下表给出推荐的学习路径：

### 基础（7 条）— 适合 SQL 入门

| Query | 学习要点 |
|-------|---------|
| Q1 高风险模型概览 | 基础 `GROUP BY` + `SUM(CASE WHEN)` 计数 |
| Q5 整改完成率 | 子查询计总数 + 百分比 |
| Q7 部门活跃度 | 单表聚合 + 活跃率派生 |
| Q9 高优先级待办 | 多表 JOIN + 简单过滤 |
| Q10 审计日志分布 | 聚合 + 占比 + `COUNT(DISTINCT)` |
| Q12 风险类别评估 | LEFT JOIN + 多列均值 |
| Q15 事件 type×severity | 透视风格的多列 SUM(CASE) |

### 中级（9 条）— 跨表 + 日期 + 多态

| Query | 学习要点 |
|-------|---------|
| Q2 框架控制实施 | 多表 JOIN + `GROUP_CONCAT(DISTINCT)` |
| Q3 未缓解高风险 | 多表 JOIN + 条件组合 |
| Q4 月度趋势 | `strftime('%Y-%m', ...)` 日期分桶 |
| Q8 MTTR | `julianday(a) - julianday(b)` 日期差 + 多列聚合 |
| Q11 模型 owner 风险 | ⚠️ **row-inflation 陷阱** + `COUNT(DISTINCT CASE)` 修复 |
| Q13 逾期清单 | 日期比较 + 多表 JOIN |
| Q16 用户操作追踪 | LEFT JOIN + LIMIT + 时间排序 |
| Q17 生产环境风险 | 多条件过滤 + LEFT JOIN 防空 |
| Q19 模型审计覆盖 | 子查询统计 + 时间条件分支 |

### 高级（4 条）— CTE、窗口函数、业务语义

| Query | 学习要点 |
|-------|---------|
| Q6 模型风险排行 | CTE + `RANK() OVER` + 标量子查询对比 |
| Q14 框架覆盖率/符合率 | ⚠️ **NOT_APPLICABLE 分母陷阱** + 双口径 |
| Q18 负责人工作量 | 多 metric + `RANK() OVER` 排名 |
| Q20 关键指标仪表盘 | 多个标量子查询 + `NULLIF` 防除零 |

### 关键业务语义陷阱（值得反复琢磨）

- **Q11 row-inflation:** 当 `LEFT JOIN` 一个有 1:N 关系的下游表后再用 `SUM(CASE WHEN parent.col=...)` 时，结果会被下游行数倍乘。修复：`COUNT(DISTINCT CASE WHEN parent.col=... THEN parent.id END)`。
- **Q11 加权 vs 等权平均:** `AVG(ra.risk_score)` 是按评估行加权（评估多的模型权重大），不是按模型等权。两种语义都站得住，按业务问题选。
- **Q14 NOT_APPLICABLE 进分母:** "控制项不适用" 不应被算成 "未合规"。合规率分母必须排除 NOT_APPLICABLE，否则数字被人为压低。
- **Q19 时间锚点漂移:** Query 19 用 `julianday('now')` 与 `last_audit_date` 对比。如果数据生成后过了 6+ 个月仍未重跑生成器，所有 last_audit_date 都会变 stale，查询命中率向 100% 漂移失去判别力。生成器采用动态锚点正是为了避免此问题，但需要**生成后立即查询**才能保持判别力。

---

## 查询索引

| 编号 | 标题 | 业务角色 | 分类 | 难度 |
|------|------|----------|------|------|
| 1 | 高风险模型合规概览 | 高管 | 聚合 | 基础 |
| 2 | 各框架控制措施实施情况 | 合规经理 | 连接+聚合 | 中级 |
| 3 | 未缓解的高风险评估列表 | 风险经理 | 连接 | 基础 |
| 4 | 安全事件月度趋势分析 | 安全分析师 | 日期分析 | 中级 |
| 5 | 整改行动完成率统计 | 运营经理 | 聚合 | 基础 |
| 6 | 模型风险评分排行榜 | 分析师 | 窗口函数 | 高级 |
| 7 | 各部门用户活跃度分析 | 人力经理 | 聚合 | 基础 |
| 8 | 事件平均解决时间分析 | 运营经理 | 日期分析 | 中级 |
| 9 | 高优先级待处理整改行动 | 运营 | 连接 | 基础 |
| 10 | 审计日志操作类型分布 | 合规审计师 | 聚合 | 基础 |
| 11 | 模型所有者风险责任分析 | 风险经理 | 连接+聚合 | 中级 |
| 12 | 各风险类别评估数量对比 | 分析师 | 聚合 | 基础 |
| 13 | 逾期整改行动清单 | 运营经理 | 连接+日期 | 中级 |
| 14 | 框架合规评估覆盖率与符合率 | 合规经理 | CTE | 高级 |
| 15 | 事件类型与严重程度交叉分析 | 安全分析师 | 聚合 | 中级 |
| 16 | 用户操作审计追踪 | 合规审计师 | 连接 | 中级 |
| 17 | 生产环境模型风险汇总 | 高管 | 连接+聚合 | 中级 |
| 18 | 整改行动负责人工作量分析 | 运营经理 | 窗口函数 | 高级 |
| 19 | 模型审计覆盖率检查 | 合规经理 | 子查询 | 中级 |
| 20 | 关键合规指标仪表盘 | 高管 | CTE+聚合 | 高级 |

---

## 查询详情

### 查询 1: 高风险模型合规概览

**业务背景:**
CTO 或 CISO 需要快速了解组织中部署的 AI 模型整体风险状况。在董事会汇报或季度合规审查会议前，高管需要一个简洁的概览，显示各风险等级有多少模型，以及活跃/非活跃的分布。这有助于判断整体风险敞口和资源分配优先级。

**分类:** 聚合
**难度:** 基础
**业务角色:** 高管/C-Level

**解题思路:**
这题的数据全在 `ai_model` 单表里，不需要任何 join。核心是"一次扫描、按 `risk_tier` 分组、同时数出活跃与非活跃两类"——用 `SUM(CASE WHEN is_active = 1 THEN 1 ELSE 0 END)` 这种条件计数把两个口径并到同一行，比跑两次查询再拼接干净得多（`is_active` 在 SQLite 里是 0/1 整数）。输出粒度是"一档风险等级一行"，共 4 行。最后的 `ORDER BY CASE risk_tier ...` 是关键细节：默认字母序会把 CRITICAL 排到 HIGH 后面，这里用 CASE 映射强制成 CRITICAL→HIGH→MEDIUM→LOW 的业务阅读顺序。

```sql
-- 按风险等级和状态统计 AI 模型数量
SELECT
    risk_tier,
    SUM(CASE WHEN is_active = 1 THEN 1 ELSE 0 END) AS active_models,
    SUM(CASE WHEN is_active = 0 THEN 1 ELSE 0 END) AS inactive_models,
    COUNT(*) AS total_models
FROM ai_model
GROUP BY risk_tier
ORDER BY
    CASE risk_tier
        WHEN 'CRITICAL' THEN 1
        WHEN 'HIGH' THEN 2
        WHEN 'MEDIUM' THEN 3
        WHEN 'LOW' THEN 4
    END;
```

**预期结果说明:**
返回 4 行数据（CRITICAL, HIGH, MEDIUM, LOW），每行显示该风险等级的活跃模型数、非活跃模型数和总数。帮助高管快速识别 CRITICAL 和 HIGH 等级模型的数量。

---

### 查询 2: 各框架控制措施实施情况

**业务背景:**
合规经理需要向审计委员会报告各合规框架的控制措施实施进度。不同框架（如 NIST AI RMF、GDPR、HIPAA）有不同的控制要求，经理需要了解每个框架定义了多少控制措施，以及各类别的分布。这有助于识别合规差距和资源需求。

**分类:** 连接+聚合
**难度:** 中级
**业务角色:** 合规经理

**解题思路:**
要把"框架"和"控制项"拼起来，所以从 `compliance_framework` join 到 `compliance_control`（`framework_id` 是 1:N，一个框架下挂多个控制项）。这里用 INNER JOIN 没问题，因为每个控制项都必有所属框架；只有"零控制项的框架"会被丢掉，本数据集里不存在这种框架。聚合粒度是 (框架, category) 双层，所以 `GROUP BY` 要带上 `cf.id, cf.name, cf.version, cc.category`。`GROUP_CONCAT(DISTINCT cc.priority)` 把同一组里出现过的优先级折叠成一个去重列表，方便经理一眼看到"这个类别覆盖了哪些优先级"。

```sql
-- 统计各合规框架的控制措施数量和类别分布
SELECT
    cf.name AS framework_name,
    cf.version,
    cc.category,
    COUNT(*) AS control_count,
    GROUP_CONCAT(DISTINCT cc.priority) AS priorities
FROM compliance_framework cf
JOIN compliance_control cc ON cf.id = cc.framework_id
GROUP BY cf.id, cf.name, cf.version, cc.category
ORDER BY cf.name, cc.category;
```

**预期结果说明:**
返回每个框架下各类别（Governance, Data Management 等）的控制措施数量，以及涉及的优先级列表。合规经理可以识别哪些框架/类别的控制措施最多，需要更多关注。

---

### 查询 3: 未缓解的高风险评估列表

**业务背景:**
风险经理每周需要审查未采取缓解措施的高风险项。当风险评分超过一定阈值（如 20 分）且状态仍为 NOT_STARTED 时，这些项目需要立即关注。风险经理需要联系模型负责人和评估人员，推动风险处置。

**分类:** 连接
**难度:** 基础
**业务角色:** 风险经理

**解题思路:**
以 `risk_assessment` 为主表，分别 join 回 `ai_model`（拿模型名与 risk_tier）、`risk_category`（拿类别名）、`user`（拿评估人姓名）。这三个外键都是 NOT NULL，所以用 INNER JOIN 安全，不会漏行。过滤条件是两个并列的业务口径：`risk_score >= 20`（约定为"高风险"阈值，回忆 risk_score 取值 0.9~45）且 `mitigation_status = 'NOT_STARTED'`（完全没动手缓解）。输出粒度是"一条评估一行"，按 `risk_score DESC` 排序让最危险的项浮到最上面，方便风险经理从上往下催。

```sql
-- 查找风险评分高但未开始缓解的评估记录
SELECT
    ra.id AS assessment_id,
    am.model_name,
    am.risk_tier,
    rc.name AS risk_category,
    ra.risk_score,
    ra.mitigation_status,
    u.full_name AS assessor,
    ra.findings,
    ra.assessed_at
FROM risk_assessment ra
JOIN ai_model am ON ra.ai_model_id = am.id
JOIN risk_category rc ON ra.risk_category_id = rc.id
JOIN user u ON ra.assessor_id = u.id
WHERE ra.risk_score >= 20
  AND ra.mitigation_status = 'NOT_STARTED'
ORDER BY ra.risk_score DESC;
```

**预期结果说明:**
返回风险评分 ≥ 20 且状态为 NOT_STARTED 的评估记录，按风险评分降序排列。包含模型名称、风险类别、评估人员等信息，便于风险经理跟进。

---

### 查询 4: 安全事件月度趋势分析

**业务背景:**
安全运营中心（SOC）负责人需要分析安全事件的月度趋势。了解事件数量是在增加还是减少，哪些月份是高峰期，有助于调整安全团队的人员配置和预算。这也是向管理层汇报安全态势的重要指标。

**分类:** 日期分析
**难度:** 中级
**业务角色:** 安全分析师

**解题思路:**
数据只在 `security_incident` 单表。月度趋势的关键是把日期"降采样"到月：用 `strftime('%Y-%m', reported_at)` 把时间戳切成 `2026-05` 这样的月份桶，再 `GROUP BY` 这个表达式。每个月份桶里，用四个 `SUM(CASE WHEN severity = ... )` 把严重度横向铺成四列，做出一张透视表（每行一个月，列是各严重度计数）。`strftime` 是 SQLite 专有函数，依赖 `reported_at` 是标准 ISO 日期字符串（生成器正是这样写出的）。最后 `ORDER BY month` 保证时间轴有序，便于直接画趋势图。

```sql
-- 按月统计安全事件数量和严重程度分布
SELECT
    strftime('%Y-%m', reported_at) AS month,
    COUNT(*) AS total_incidents,
    SUM(CASE WHEN severity = 'CRITICAL' THEN 1 ELSE 0 END) AS critical_count,
    SUM(CASE WHEN severity = 'HIGH' THEN 1 ELSE 0 END) AS high_count,
    SUM(CASE WHEN severity = 'MEDIUM' THEN 1 ELSE 0 END) AS medium_count,
    SUM(CASE WHEN severity = 'LOW' THEN 1 ELSE 0 END) AS low_count
FROM security_incident
GROUP BY strftime('%Y-%m', reported_at)
ORDER BY month;
```

**预期结果说明:**
返回按月汇总的事件统计，显示每月各严重程度的事件数量。分析师可以绘制趋势图，识别事件高峰月份和整体安全趋势。

---

### 查询 5: 整改行动完成率统计

**业务背景:**
运营经理需要在每周站会上报告整改行动的完成情况。需要知道有多少整改行动已完成、进行中、待处理或延期，以评估团队的执行效率和是否需要额外资源。完成率是关键的运营 KPI。

**分类:** 聚合
**难度:** 基础
**业务角色:** 运营经理

**解题思路:**
`remediation_action` join `control_status` 拿到状态的可读名称与 `is_terminal` 标记。算占比的常见手法是在 SELECT 里放一个标量子查询 `(SELECT COUNT(*) FROM remediation_action)` 当分母——它对每一组返回同一个总数，于是每行的 `action_count * 100.0 / 总数` 就是该状态的百分比（注意乘 `100.0` 触发浮点除法，否则整数相除会被截断为 0）。粒度是"一个状态一行"。`ORDER BY CASE cs.code ...` 把状态按 COMPLETED→IN_PROGRESS→PENDING→DEFERRED→CANCELLED 的运营关注顺序排列，而不是字母序。

```sql
-- 统计各状态的整改行动数量和占比
SELECT
    cs.code AS status_code,
    cs.name AS status_name,
    cs.is_terminal,
    COUNT(*) AS action_count,
    ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM remediation_action), 2) AS percentage
FROM remediation_action ra
JOIN control_status cs ON ra.status_id = cs.id
GROUP BY cs.id, cs.code, cs.name, cs.is_terminal
ORDER BY
    CASE cs.code
        WHEN 'COMPLETED' THEN 1
        WHEN 'IN_PROGRESS' THEN 2
        WHEN 'PENDING' THEN 3
        WHEN 'DEFERRED' THEN 4
        WHEN 'CANCELLED' THEN 5
    END;
```

**预期结果说明:**
返回各状态的整改行动数量和百分比。运营经理可以快速看到完成率（COMPLETED 的百分比）和待处理项（PENDING + IN_PROGRESS）的比例。

---

### 查询 6: 模型风险评分排行榜

**业务背景:**
风险分析师需要识别组织中风险最高的 AI 模型。每个模型可能有多次风险评估（针对不同风险类别），分析师需要计算每个模型的平均风险评分和最高风险评分，并与整体平均水平比较。这有助于优先处置高风险模型。

**分类:** 窗口函数
**难度:** 高级
**业务角色:** 分析师

**解题思路:**
这题分两步，所以用 CTE 把它拆开。第一步 `model_stats`：`ai_model` join `risk_assessment` 后按模型聚合，算出每个模型的评估数、平均与最高 risk_score（这里用 INNER JOIN，只保留"至少被评估过一次"的模型——没有评估就无从排名）。第二步在 CTE 之上做两件事：`RANK() OVER (ORDER BY avg_risk_score DESC)` 给模型排名，以及用标量子查询 `(SELECT AVG(risk_score) FROM risk_assessment)` 取全局平均做对比基准。为什么必须用 CTE 而不是一步写完？因为窗口函数 `RANK()` 要在"已经按模型聚合好的结果"上算，把 `GROUP BY` 聚合和窗口排名混在一层会语义打架。注意 `avg_risk_score` 是按评估行加权的（评估多的模型，其每条评估都进均值）。`LIMIT 15` 只取风险最高的 15 个。

```sql
-- 用 CTE 先按模型聚合，再做窗口排名与对比，避免 RANK + LIMIT 语义混淆
WITH model_stats AS (
    SELECT
        am.id,
        am.model_name,
        am.risk_tier,
        am.deployment_env,
        COUNT(ra.id) AS assessment_count,
        ROUND(AVG(ra.risk_score), 2) AS avg_risk_score,
        MAX(ra.risk_score) AS max_risk_score
    FROM ai_model am
    JOIN risk_assessment ra ON am.id = ra.ai_model_id
    WHERE am.is_active = 1
    GROUP BY am.id, am.model_name, am.risk_tier, am.deployment_env
)
SELECT
    model_name,
    risk_tier,
    deployment_env,
    assessment_count,
    avg_risk_score,
    max_risk_score,
    RANK() OVER (ORDER BY avg_risk_score DESC) AS risk_rank,
    ROUND(avg_risk_score - (SELECT AVG(risk_score) FROM risk_assessment), 2) AS vs_overall_avg
FROM model_stats
ORDER BY avg_risk_score DESC
LIMIT 15;
```

**预期结果说明:**
返回前 15 个高风险模型的排名，包含评估次数、平均和最高风险评分，以及与整体平均值的差异。正值表示高于平均，负值表示低于平均。

---

### 查询 7: 各部门用户活跃度分析

**业务背景:**
人力资源经理或部门主管需要了解各部门在合规系统中的用户分布和活跃状态。这有助于评估各部门对合规工作的参与度，以及是否需要进行系统权限清理（停用不活跃账户）。

**分类:** 聚合
**难度:** 基础
**业务角色:** 人力经理

**解题思路:**
数据全在 `user` 单表，按 `department` 分组即可。和 Q1 同样的"条件计数"手法：用 `SUM(CASE WHEN is_active = 1 ...)` 数活跃、`SUM(CASE WHEN is_active = 0 ...)` 数非活跃，再用活跃数 `* 100.0 / COUNT(*)` 算出活跃率（乘 `100.0` 走浮点）。一个容易踩的认知坑：`role` 到 `department` 是 N:1 映射（Engineering 容纳 3 个角色），所以这里按 `department` 分组实际只有 6 个桶，而不是 8 个角色桶。输出粒度是"一个部门一行"，按总人数降序排。

```sql
-- 统计各部门用户数量和活跃状态
SELECT
    department,
    COUNT(*) AS total_users,
    SUM(CASE WHEN is_active = 1 THEN 1 ELSE 0 END) AS active_users,
    SUM(CASE WHEN is_active = 0 THEN 1 ELSE 0 END) AS inactive_users,
    ROUND(SUM(CASE WHEN is_active = 1 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) AS active_rate
FROM user
GROUP BY department
ORDER BY total_users DESC;
```

**预期结果说明:**
返回各部门的用户统计，包括总人数、活跃/非活跃人数和活跃率。低活跃率的部门可能需要关注。

---

### 查询 8: 事件平均解决时间分析

**业务背景:**
运营经理需要衡量安全团队的响应效率。平均解决时间（Mean Time To Resolve, MTTR）是关键的 SLA 指标。按事件类型和严重程度分析 MTTR，有助于识别哪类事件处理较慢，需要流程改进或额外资源。

**分类:** 日期分析
**难度:** 中级
**业务角色:** 运营经理

**解题思路:**
MTTR 的本质是两个时间戳相减。在 SQLite 里没有原生的"小时差"函数，惯用做法是 `(julianday(resolved_at) - julianday(reported_at)) * 24`——`julianday` 把日期转成"儒略日"浮点数，相减得到天数，乘 24 换成小时。关键前提是 `WHERE resolved_at IS NOT NULL`：未解决的事件 `resolved_at` 为空，参与算术会得到 NULL 污染均值，所以必须先滤掉（这也符合"MTTR 只对已解决事件有意义"的业务定义）。按 (incident_type, severity) 双层分组，同时取 AVG/MIN/MAX 看分布。数据只来自 `security_incident` 单表，无需 join。

```sql
-- 计算各类事件的平均解决时间（小时）
SELECT
    incident_type,
    severity,
    COUNT(*) AS resolved_count,
    ROUND(AVG(
        (julianday(resolved_at) - julianday(reported_at)) * 24
    ), 1) AS avg_resolution_hours,
    ROUND(MIN(
        (julianday(resolved_at) - julianday(reported_at)) * 24
    ), 1) AS min_hours,
    ROUND(MAX(
        (julianday(resolved_at) - julianday(reported_at)) * 24
    ), 1) AS max_hours
FROM security_incident
WHERE resolved_at IS NOT NULL
GROUP BY incident_type, severity
ORDER BY avg_resolution_hours DESC;
```

**预期结果说明:**
返回已解决事件的平均解决时间（小时），按事件类型和严重程度分组。运营经理可以识别 MTTR 较长的事件类型，优化处理流程。

---

### 查询 9: 高优先级待处理整改行动

**业务背景:**
运营团队每天早会需要查看当前最紧急的待处理整改行动。P1-Critical 和 P2-High 优先级的行动需要优先处理。运营人员需要知道负责人、截止日期和关联的控制措施，以便跟进和协调。

**分类:** 连接
**难度:** 基础
**业务角色:** 运营

**解题思路:**
以 `remediation_action` 为主表，join `compliance_control`（拿 control_id 与 priority）、`control_status`（判断是否未完成）、`user`（拿负责人姓名与部门）。两个过滤条件配合：`cs.is_terminal = 0` 表示"尚未到终态"（即 PENDING/IN_PROGRESS/DEFERRED），`cc.priority IN ('P1-Critical', 'P2-High')` 只看高优先级。`julianday(ra.due_date) - julianday('now')` 算出距截止日的天数，**负数即已逾期**，正好给晨会一个"还剩几天 / 已经欠了几天"的直观读数。注意这里用了运行时 `'now'`，请在生成数据后尽快跑。

```sql
-- 查找高优先级且未完成的整改行动
SELECT
    ra.id,
    ra.title,
    cc.control_id,
    cc.priority,
    cs.name AS status,
    u.full_name AS assigned_to,
    u.department,
    ra.due_date,
    ROUND(julianday(ra.due_date) - julianday('now'), 0) AS days_until_due
FROM remediation_action ra
JOIN compliance_control cc ON ra.control_id = cc.id
JOIN control_status cs ON ra.status_id = cs.id
JOIN user u ON ra.assigned_to_id = u.id
WHERE cs.is_terminal = 0
  AND cc.priority IN ('P1-Critical', 'P2-High')
ORDER BY cc.priority, ra.due_date;
```

**预期结果说明:**
返回高优先级（P1, P2）且未完成的整改行动列表，包含截止日期和距今天数。负数表示已逾期，需要立即关注。

---

### 查询 10: 审计日志操作类型分布

**业务背景:**
合规审计师需要分析系统中的操作类型分布，以识别异常模式。例如，DELETE 操作过多可能表示数据清理或潜在问题，EXPORT 操作过多可能有数据外泄风险。这是合规审计的基础分析。

**分类:** 聚合
**难度:** 基础
**业务角色:** 合规审计师

**解题思路:**
单表 `audit_log`，按 `action_type` 分组。与 Q5 同样用标量子查询 `(SELECT COUNT(*) FROM audit_log)` 当分母算占比。这里多了一个 `COUNT(DISTINCT user_id)`：它回答"这种操作是被很多人做、还是集中在少数人手里"——比如 EXPORT 占比不高但只有一个用户在做，就比"很多人都在 EXPORT"更值得警觉。粒度是"一种操作类型一行"，按日志数降序，让高频操作排在最前。这是合规取证的入口查询，配合 Q16 可下钻到具体用户。

```sql
-- 统计各操作类型的审计日志数量
SELECT
    action_type,
    COUNT(*) AS log_count,
    ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM audit_log), 2) AS percentage,
    COUNT(DISTINCT user_id) AS unique_users
FROM audit_log
GROUP BY action_type
ORDER BY log_count DESC;
```

**预期结果说明:**
返回各操作类型的日志数量、占比和涉及的唯一用户数。审计师可以识别高频操作和异常模式。

---

### 查询 11: 模型所有者风险责任分析

**业务背景:**
风险管理团队需要评估各模型所有者承担的风险责任。有些用户可能负责多个高风险模型，成为组织的"单点风险"。识别这些用户有助于进行风险分散和继任者规划。

**分类:** 连接+聚合
**难度:** 中级
**业务角色:** 风险经理

**解题思路:**
这是全文档最重要的一道"陷阱题"。链路是 `user` →（1:N）`ai_model` →（1:N）`risk_assessment`。第二个 LEFT JOIN 会把每个模型按它的评估条数复制多份——于是如果你天真地写 `SUM(CASE WHEN am.risk_tier = 'CRITICAL' THEN 1 ELSE 0 END)`，同一个 CRITICAL 模型会被它的 N 条评估重复加 N 次，`critical_models` 严重虚高（这就是 row-inflation）。修复办法是 `COUNT(DISTINCT CASE WHEN am.risk_tier = 'CRITICAL' THEN am.id END)`：无论 join 复制多少次，同一个 `am.id` 只数一次。用 LEFT JOIN 而非 INNER 是为了让"还没有任何评估的模型"也能计入 `model_count`。`AVG(ra.risk_score)` 是按评估行加权（评估多的模型权重大）；若想要按模型等权，需先在模型内聚合再对 owner 聚合（见下方修复说明）。`HAVING COUNT(DISTINCT am.id) > 1` 只留"名下不止一个模型"的 owner。

```sql
-- 修复 row-inflation：用 COUNT(DISTINCT CASE WHEN ... END) 避免 LEFT JOIN risk_assessment
-- 后对 risk_tier 求和被评估行数倍乘的问题
SELECT
    u.full_name AS owner_name,
    u.role,
    u.department,
    COUNT(DISTINCT am.id) AS model_count,
    COUNT(DISTINCT CASE WHEN am.risk_tier = 'CRITICAL' THEN am.id END) AS critical_models,
    COUNT(DISTINCT CASE WHEN am.risk_tier = 'HIGH' THEN am.id END) AS high_models,
    ROUND(AVG(ra.risk_score), 2) AS avg_risk_score
FROM user u
JOIN ai_model am ON u.id = am.owner_id
LEFT JOIN risk_assessment ra ON am.id = ra.ai_model_id
WHERE am.is_active = 1
GROUP BY u.id, u.full_name, u.role, u.department
HAVING COUNT(DISTINCT am.id) > 1
ORDER BY critical_models DESC, high_models DESC, model_count DESC;
```

**预期结果说明:**
返回拥有多个活跃模型的用户，显示其 CRITICAL 和 HIGH 模型数量以及平均风险评分。高风险集中的用户需要关注。

> **修复说明:** 原始查询使用 `SUM(CASE WHEN am.risk_tier = 'CRITICAL' THEN 1 ELSE 0 END)`，在 `LEFT JOIN risk_assessment` 下会被评估行数倍乘（每个模型乘以其 assessment 数），导致 `critical_models` 远高于真实值。改用 `COUNT(DISTINCT CASE WHEN ... THEN am.id END)` 后，无论 join 复制多少次，同一模型 id 只被计一次。

> **`avg_risk_score` 语义提示（加权 vs 等权）:** 本查询的 `AVG(ra.risk_score)` 是**按评估行加权平均**——某个模型有 5 条 assessment、另一个只有 1 条，前者会贡献 5 个 risk_score 给均值。这反映"评估了多少风险"的累积视角。如果业务想要的是"按模型等权平均"（每个模型的 risk_score 先各自聚合一次再平均），需要改用先模型内聚合再 owner 聚合的两层 CTE：
> ```sql
> WITH per_model AS (
>     SELECT am.owner_id, am.id, AVG(ra.risk_score) AS model_avg_risk
>     FROM ai_model am JOIN risk_assessment ra ON am.id = ra.ai_model_id
>     WHERE am.is_active = 1 GROUP BY am.owner_id, am.id
> )
> SELECT owner_id, AVG(model_avg_risk) AS owner_equal_weight_avg FROM per_model GROUP BY owner_id;
> ```
> 两种语义都站得住，选哪种取决于业务问题是"哪个负责人承担的累积风险量大"还是"哪个负责人的模型平均风险水平高"。

---

### 查询 12: 各风险类别评估数量对比

**业务背景:**
风险分析师需要了解哪些风险类别被评估最多。这反映了组织对各类风险的关注程度。如果某些高严重性权重的风险类别评估较少，可能表示盲点需要加强评估。

**分类:** 聚合
**难度:** 基础
**业务角色:** 分析师

**解题思路:**
要回答"哪些类别被评估得多/少"，必须从 `risk_category` 出发用 **LEFT JOIN** `risk_assessment`，而不是 INNER JOIN——否则一个"从没被评估过"的类别会因为没有匹配行而整条消失，恰恰把最该被发现的盲点藏了起来。LEFT JOIN 下，`COUNT(ra.id)` 对零评估类别返回 0（`COUNT` 不数 NULL），`AVG(...)` 返回 NULL，都是合理的。按 `rc.id, rc.code, rc.name, rc.severity_weight` 分组，粒度是"一个风险类别一行"。把 `severity_weight` 一起 SELECT 出来，是为了让分析师把"权重高但评估少"的危险组合一眼挑出来。

```sql
-- 统计各风险类别的评估数量和平均评分
SELECT
    rc.code,
    rc.name,
    rc.severity_weight,
    COUNT(ra.id) AS assessment_count,
    ROUND(AVG(ra.risk_score), 2) AS avg_risk_score,
    ROUND(AVG(ra.likelihood_score), 2) AS avg_likelihood,
    ROUND(AVG(ra.impact_score), 2) AS avg_impact
FROM risk_category rc
LEFT JOIN risk_assessment ra ON rc.id = ra.risk_category_id
GROUP BY rc.id, rc.code, rc.name, rc.severity_weight
ORDER BY assessment_count DESC;
```

**预期结果说明:**
返回各风险类别的评估统计。高严重性权重但评估数量少的类别可能需要加强关注。

---

### 查询 13: 逾期整改行动清单

**业务背景:**
运营经理需要每周向管理层报告逾期的整改行动。逾期意味着风险敞口持续时间超出预期，可能影响合规状态。需要识别逾期行动、负责人和逾期天数，以便催办和资源调配。

**分类:** 连接+日期
**难度:** 中级
**业务角色:** 运营经理

**解题思路:**
结构和 Q9 几乎一样（`remediation_action` join `compliance_control`、`control_status`、`user`），区别在过滤口径与日期方向。"真逾期"要同时满足两条：`cs.is_terminal = 0`（还没完成/取消）且 `ra.due_date < date('now')`（截止日已过）。只看 `due_date` 不看状态会把"已完成但当初截止日早"的也算进来，是常见误判，所以两个条件缺一不可。`julianday('now') - julianday(ra.due_date)` 得到逾期天数（这里相减方向和 Q9 相反，结果为正），按它降序排，逾期最久的排最前，便于优先催办。

```sql
-- 查找已逾期但未完成的整改行动
SELECT
    ra.id,
    ra.title,
    cc.control_id,
    cc.priority,
    cs.name AS status,
    u.full_name AS assigned_to,
    ra.due_date,
    ROUND(julianday('now') - julianday(ra.due_date), 0) AS days_overdue
FROM remediation_action ra
JOIN compliance_control cc ON ra.control_id = cc.id
JOIN control_status cs ON ra.status_id = cs.id
JOIN user u ON ra.assigned_to_id = u.id
WHERE cs.is_terminal = 0
  AND ra.due_date < date('now')
ORDER BY days_overdue DESC;
```

**预期结果说明:**
返回所有逾期且未完成的整改行动，按逾期天数降序。运营经理可以优先跟进逾期时间最长的项目。

---

### 查询 14: 框架合规评估覆盖率与符合率

**业务背景:**
合规经理需要向 CIO 报告各合规框架的实际评估覆盖与符合情况。两个独立指标都很关键：(1) **评估覆盖率** = 框架下有多少控制项已经被至少评估过一次（衡量审计进度）；(2) **符合率** = 在**适用范围内的评估**中，结论为 COMPLIANT 的占比（衡量合规健康度）。低覆盖率说明评估工作未完成；高覆盖率但低符合率说明发现的问题多，需要整改。

> **关键口径:** `NOT_APPLICABLE` 表示"该控制项不适用于此模型"，是评估发现的元结论。它**不应**进入合规率的分母——否则会把"控制项不适用"误算为"未合规"，人为压低合规率。本查询用 `applicable_assessments`（排除 NOT_APPLICABLE）作为符合率的分母；同时保留 `total_assessments`（包含 NOT_APPLICABLE）作为参考，让读者看到差异。

**分类:** CTE
**难度:** 高级
**业务角色:** 合规经理

**解题思路:**
这道题要在一次查询里产出两个**互相独立**的指标，所以用 CTE `framework_assessments` 先把每个框架的各项计数一次性算齐。链路是 `compliance_control` **LEFT JOIN** `model_control_assessment`——LEFT 是刻意的：从没被评估过的控制项也要计入 `total_controls`（分母），否则覆盖率会虚高。覆盖率 = `COUNT(DISTINCT mca.control_id) / total_controls`，衡量进度；符合率 = `compliant_count / applicable_assessments`，衡量健康度。**最关键的口径陷阱**：符合率的分母用 `applicable_assessments`（排除 `NOT_APPLICABLE`），因为"控制项不适用"不等于"不合规"，把它算进分母会人为压低符合率。两个比率都用 `NULLIF(分母, 0)` 防止除零。按 framework 聚合，粒度是"一个框架一行"。

```sql
-- 用 model_control_assessment 桥接表直接衡量框架的"已评估范围"与"符合度"
-- 关键: compliance_rate_pct 的分母排除 NOT_APPLICABLE（控制项不适用 ≠ 不合规）
WITH framework_assessments AS (
    SELECT
        cc.framework_id,
        COUNT(DISTINCT cc.id) AS total_controls,
        COUNT(DISTINCT mca.control_id) AS assessed_controls,
        COUNT(mca.id) AS total_assessments,
        SUM(CASE WHEN mca.compliance_status != 'NOT_APPLICABLE'
                 THEN 1 ELSE 0 END) AS applicable_assessments,
        SUM(CASE WHEN mca.compliance_status = 'COMPLIANT' THEN 1 ELSE 0 END) AS compliant_count,
        SUM(CASE WHEN mca.compliance_status = 'PARTIALLY_COMPLIANT' THEN 1 ELSE 0 END) AS partial_count,
        SUM(CASE WHEN mca.compliance_status = 'NON_COMPLIANT' THEN 1 ELSE 0 END) AS non_compliant_count,
        SUM(CASE WHEN mca.compliance_status = 'NOT_APPLICABLE' THEN 1 ELSE 0 END) AS not_applicable_count
    FROM compliance_control cc
    LEFT JOIN model_control_assessment mca ON cc.id = mca.control_id
    GROUP BY cc.framework_id
)
SELECT
    cf.name AS framework_name,
    cf.version,
    fa.total_controls,
    fa.assessed_controls,
    ROUND(fa.assessed_controls * 100.0 / NULLIF(fa.total_controls, 0), 1) AS coverage_pct,
    fa.total_assessments,
    fa.applicable_assessments,
    fa.compliant_count,
    fa.partial_count,
    fa.non_compliant_count,
    fa.not_applicable_count,
    -- 合规率分母用 applicable_assessments，排除"不适用"评估
    ROUND(fa.compliant_count * 100.0 / NULLIF(fa.applicable_assessments, 0), 1) AS compliance_rate_pct
FROM framework_assessments fa
JOIN compliance_framework cf ON fa.framework_id = cf.id
ORDER BY coverage_pct DESC;
```

**预期结果说明:**
返回每个框架的三个独立维度：(1) 评估覆盖率 = 已评估控制项 / 控制项总数；(2) 适用范围 = 排除 NOT_APPLICABLE 后的评估行数；(3) 符合率 = COMPLIANT / 适用评估行数。覆盖率低 → 审计工作有缺口；符合率低 → 发现的问题多，整改压力大；NOT_APPLICABLE 占比高 → 控制项与模型的匹配度需要重新设计（很多控制项压根用不上）。三者结合可以区分"还没做评估"、"做完发现一堆不合规"、"控制项选错了"三种很不同的情境。

---

### 查询 15: 事件类型与严重程度交叉分析

**业务背景:**
安全分析师需要理解不同事件类型的严重程度分布。例如，PROMPT_INJECTION 事件是否大多是 HIGH 或 CRITICAL 级别？这有助于制定不同事件类型的响应策略和优先级。

**分类:** 聚合
**难度:** 中级
**业务角色:** 安全分析师

**解题思路:**
单表 `security_incident`，按 `incident_type` 分组，把 `severity` 用四个 `SUM(CASE WHEN severity = ...)` 横向铺成四列——这是用聚合手搓"行转列"透视表的经典写法（SQLite 没有原生 PIVOT）。和 Q4 思路相同，只是分组维度从"月份"换成"事件类型"。粒度是"一种事件类型一行"，最后一列 `COUNT(*)` 给出该类型总数，按它降序排。读这张表要横着看：同一类型在 CRITICAL/HIGH 上是否集中，决定它的响应策略要不要升级。

```sql
-- 交叉分析事件类型和严重程度
SELECT
    incident_type,
    SUM(CASE WHEN severity = 'CRITICAL' THEN 1 ELSE 0 END) AS critical,
    SUM(CASE WHEN severity = 'HIGH' THEN 1 ELSE 0 END) AS high,
    SUM(CASE WHEN severity = 'MEDIUM' THEN 1 ELSE 0 END) AS medium,
    SUM(CASE WHEN severity = 'LOW' THEN 1 ELSE 0 END) AS low,
    COUNT(*) AS total
FROM security_incident
GROUP BY incident_type
ORDER BY total DESC;
```

**预期结果说明:**
返回各事件类型在各严重程度的分布。分析师可以识别哪些事件类型通常更严重，需要更紧急的响应。

---

### 查询 16: 用户操作审计追踪

**业务背景:**
合规审计师在调查潜在违规时，需要追踪特定用户的所有操作历史。这个查询提供用户操作的完整时间线，包括操作类型、涉及的实体和 IP 地址，用于取证分析。

**分类:** 连接
**难度:** 中级
**业务角色:** 合规审计师

**解题思路:**
以 `audit_log` 为主表，INNER JOIN `user`（操作者一定存在）拿姓名与角色，再 **LEFT JOIN** `ai_model`。这个 LEFT JOIN 是关键：`audit_log.ai_model_id` 可空（约 30% 的日志与具体模型无关，比如 USER、REPORT 类操作），用 INNER JOIN 会把这些行直接吞掉，时间线就断了。`WHERE al.user_id = 5` 锁定被调查的人，`ORDER BY al.timestamp DESC LIMIT 50` 取最近 50 条还原时间线。补充：`entity_type` + `entity_id` 是多态引用，没有 schema 级 FK，要关联回真实记录得在应用层按 `entity_type` 选目标表。

```sql
-- 追踪指定用户的操作历史（示例：审查用户 ID 为 5 的操作）
SELECT
    al.timestamp,
    u.full_name,
    u.role,
    al.action_type,
    al.entity_type,
    al.entity_id,
    am.model_name,
    al.details,
    al.ip_address
FROM audit_log al
JOIN user u ON al.user_id = u.id
LEFT JOIN ai_model am ON al.ai_model_id = am.id
WHERE al.user_id = 5
ORDER BY al.timestamp DESC
LIMIT 50;
```

**预期结果说明:**
返回指定用户最近 50 条操作记录的详细信息。审计师可以重建用户的操作时间线，识别异常行为。

> **多态 entity_id 提示:** `al.entity_id` 与 `al.entity_type` 联动。如要按 `(entity_type, entity_id)` 关联回真实记录，需要在应用层根据 `entity_type` 选择 join 的目标表（schema 层没有 FK 约束）。

---

### 查询 17: 生产环境模型风险汇总

**业务背景:**
CTO 和 CISO 最关心生产环境中的 AI 模型风险。相比开发和测试环境，生产环境的问题会直接影响业务和客户。这个查询汇总生产模型的风险状况，帮助高管了解实际业务风险敞口。

**分类:** 连接+聚合
**难度:** 中级
**业务角色:** 高管

**解题思路:**
`ai_model` **LEFT JOIN** `risk_assessment`，过滤到生产且活跃的模型，按 `risk_tier` 汇总。两个过滤条件要小心：`deployment_env = 'production'` 里的 `production` **全小写**，SQLite 字符串比较大小写敏感，写成 `'Production'` 会一行不返回；`is_active = 1` 排除已下线模型。LEFT JOIN 是为了让"生产但还没做过任何风险评估"的模型也出现在结果里（这本身就是个值得高管警觉的信号）。`COUNT(DISTINCT am.id)` 数模型、`COUNT(ra.id)` 数评估，两者分开避免把模型数被评估行数倍乘。`SUM(CASE WHEN mitigation_status = ...)` 把未缓解/已缓解拆成两列。

```sql
-- 汇总生产环境模型的风险评估情况
SELECT
    am.risk_tier,
    COUNT(DISTINCT am.id) AS model_count,
    COUNT(ra.id) AS total_assessments,
    ROUND(AVG(ra.risk_score), 2) AS avg_risk_score,
    SUM(CASE WHEN ra.mitigation_status = 'NOT_STARTED' THEN 1 ELSE 0 END) AS unmitigated,
    SUM(CASE WHEN ra.mitigation_status = 'MITIGATED' THEN 1 ELSE 0 END) AS mitigated
FROM ai_model am
LEFT JOIN risk_assessment ra ON am.id = ra.ai_model_id
WHERE am.deployment_env = 'production'
  AND am.is_active = 1
GROUP BY am.risk_tier
ORDER BY
    CASE am.risk_tier
        WHEN 'CRITICAL' THEN 1
        WHEN 'HIGH' THEN 2
        WHEN 'MEDIUM' THEN 3
        WHEN 'LOW' THEN 4
    END;
```

**预期结果说明:**
返回生产环境各风险等级模型的评估汇总，包括平均风险评分和缓解状态分布。高管可以关注 CRITICAL/HIGH 等级中未缓解的评估数量。

---

### 查询 18: 整改行动负责人工作量分析

**业务背景:**
运营经理需要评估整改行动的分配是否均衡。有些人可能分配了过多任务导致超负荷，而有些人可能相对空闲。这个分析有助于重新平衡工作量，确保按时完成整改。

**分类:** 窗口函数
**难度:** 高级
**业务角色:** 运营经理

**解题思路:**
`remediation_action` join `user`（负责人）和 `control_status`（判断状态），按负责人聚合。每个负责人算三个口径：总分配数 `COUNT(*)`、在途数 `SUM(CASE WHEN cs.is_terminal = 0 ...)`、完成数 `SUM(CASE WHEN cs.code = 'COMPLETED' ...)`，再派生完成率。亮点是窗口函数 `RANK() OVER (ORDER BY SUM(CASE WHEN cs.is_terminal = 0 ...) DESC)`：它在分组聚合之后，按"在途任务数"给负责人排名，直接回答"谁负荷最重"。`HAVING COUNT(*) >= 2` 滤掉只分到一两件、没有分析意义的人。粒度是"一个负责人一行"。

```sql
-- 分析整改行动负责人的工作量分布
SELECT
    u.full_name,
    u.role,
    u.department,
    COUNT(*) AS total_assigned,
    SUM(CASE WHEN cs.is_terminal = 0 THEN 1 ELSE 0 END) AS open_actions,
    SUM(CASE WHEN cs.code = 'COMPLETED' THEN 1 ELSE 0 END) AS completed,
    ROUND(SUM(CASE WHEN cs.code = 'COMPLETED' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) AS completion_rate,
    RANK() OVER (ORDER BY SUM(CASE WHEN cs.is_terminal = 0 THEN 1 ELSE 0 END) DESC) AS workload_rank
FROM remediation_action ra
JOIN user u ON ra.assigned_to_id = u.id
JOIN control_status cs ON ra.status_id = cs.id
GROUP BY u.id, u.full_name, u.role, u.department
HAVING COUNT(*) >= 2
ORDER BY open_actions DESC;
```

**预期结果说明:**
返回各负责人的整改行动统计，包括总分配数、进行中数量、完成数和完成率。工作量排名帮助识别负荷最重的人员。

---

### 查询 19: 模型审计覆盖率检查

**业务背景:**
合规经理需要确保所有活跃模型都经过定期审计。如果模型从未审计，或距离上次审计已超过 6 个月，这些模型需要安排审计。这是持续合规的重要检查。

> **口径说明:** 本查询对"从未审计"模型不再额外要求"注册满 6 个月"——只要 `last_audit_date IS NULL` 即列入待审计清单。这意味着新注册不久的模型也会出现在结果中,合规经理需自行结合 `created_at` 列判断是否真有审计紧迫性。如果想严格筛选"注册 > 6 个月才该被审计"的模型,可在 WHERE 子句加一行 `AND julianday('now') - julianday(am.created_at) > 180`。

**分类:** 子查询
**难度:** 中级
**业务角色:** 合规经理

**解题思路:**
主表 `ai_model` join `user` 拿 owner 姓名。核心是 WHERE 里的"或"逻辑：`last_audit_date IS NULL`（从未审计）**或** `julianday('now') - julianday(last_audit_date) > 180`（距上次审计超 180 天）。`CASE WHEN last_audit_date IS NULL THEN '从未审计' ELSE ... END` 把两种情况翻译成人话标签。`assessment_count` 用一个相关子查询 `(SELECT COUNT(*) FROM risk_assessment WHERE ai_model_id = am.id)` 现算，避免再开一个 join 把行倍乘。`ORDER BY CASE WHEN last_audit_date IS NULL THEN 0 ELSE 1 END` 把"从未审计"顶到最前。这道题靠动态时间锚点保持判别力（命中率设计在 20–30%），所以务必生成后立即跑。

```sql
-- 查找需要审计的模型（超过 180 天未审计或从未审计）
SELECT
    am.model_name,
    am.version,
    am.model_type,
    am.risk_tier,
    am.deployment_env,
    u.full_name AS owner,
    am.created_at,
    am.last_audit_date,
    CASE
        WHEN am.last_audit_date IS NULL THEN '从未审计'
        ELSE CAST(ROUND(julianday('now') - julianday(am.last_audit_date)) AS INTEGER) || ' 天前'
    END AS audit_status,
    (SELECT COUNT(*) FROM risk_assessment WHERE ai_model_id = am.id) AS assessment_count
FROM ai_model am
JOIN user u ON am.owner_id = u.id
WHERE am.is_active = 1
  AND (
    am.last_audit_date IS NULL
    OR julianday('now') - julianday(am.last_audit_date) > 180
  )
ORDER BY
    CASE WHEN am.last_audit_date IS NULL THEN 0 ELSE 1 END,
    am.last_audit_date;
```

**预期结果说明:**
返回需要审计的活跃模型列表，优先显示从未审计的模型。合规经理可以据此安排审计计划。由于数据集采用动态时间锚点（生成时 NOW），此查询命中率应在 20-30% 之间（约 20% 从未审计 + 约 10% 已 stale），保留判别力。

---

### 查询 20: 关键合规指标仪表盘

**业务背景:**
CTO 或 CISO 需要一个综合的合规仪表盘，显示关键指标的整体状况。这个查询汇总多个维度的关键数字，用于管理层周报或月报。一个查询返回所有关键指标，便于构建仪表盘。

**分类:** CTE+聚合
**难度:** 高级
**业务角色:** 高管/C-Level

**解题思路:**
这道题要把散落在多张表的关键数字汇成"一行仪表盘"。手法是在 CTE `metrics` 里放一串彼此独立的标量子查询，每个算一个 KPI（活跃模型数、高风险模型数、未缓解风险、未关闭事件、在途/逾期整改、不符合评估……），各查各的、互不干扰。外层 SELECT 再把它们排好版、补上派生比率（如高风险占比）。每个除法都用 `NULLIF(分母, 0)` 包住防止除零。注意口径要和其他查询一致：高风险 = `risk_tier IN ('CRITICAL','HIGH')`、未关闭事件 = `status NOT IN ('RESOLVED','CLOSED')`、在途整改 = `is_terminal = 0`。结果只有一行，直接喂给董事会周报/月报的仪表盘卡片。

```sql
-- 综合合规指标仪表盘
WITH metrics AS (
    SELECT
        (SELECT COUNT(*) FROM ai_model WHERE is_active = 1) AS active_models,
        (SELECT COUNT(*) FROM ai_model WHERE is_active = 1 AND risk_tier IN ('CRITICAL', 'HIGH')) AS high_risk_models,
        (SELECT COUNT(*) FROM risk_assessment) AS total_assessments,
        (SELECT COUNT(*) FROM risk_assessment WHERE mitigation_status = 'NOT_STARTED') AS unmitigated_risks,
        (SELECT COUNT(*) FROM security_incident WHERE status NOT IN ('RESOLVED', 'CLOSED')) AS open_incidents,
        (SELECT COUNT(*) FROM security_incident WHERE severity = 'CRITICAL' AND status NOT IN ('RESOLVED', 'CLOSED')) AS critical_open_incidents,
        (SELECT COUNT(*) FROM remediation_action ra JOIN control_status cs ON ra.status_id = cs.id WHERE cs.is_terminal = 0) AS open_remediations,
        (SELECT COUNT(*) FROM remediation_action ra JOIN control_status cs ON ra.status_id = cs.id WHERE cs.is_terminal = 0 AND ra.due_date < date('now')) AS overdue_remediations,
        (SELECT COUNT(DISTINCT framework_id) FROM compliance_control) AS frameworks_in_use,
        (SELECT COUNT(*) FROM user WHERE is_active = 1) AS active_users,
        (SELECT COUNT(*) FROM model_control_assessment WHERE compliance_status = 'NON_COMPLIANT') AS non_compliant_assessments
)
SELECT
    active_models AS '活跃模型数',
    high_risk_models AS '高风险模型数',
    ROUND(high_risk_models * 100.0 / NULLIF(active_models, 0), 1) AS '高风险占比(%)',
    total_assessments AS '总评估数',
    unmitigated_risks AS '未缓解风险数',
    open_incidents AS '未关闭事件数',
    critical_open_incidents AS 'CRITICAL级未关闭',
    open_remediations AS '进行中整改数',
    overdue_remediations AS '逾期整改数',
    frameworks_in_use AS '使用的框架数',
    active_users AS '活跃用户数',
    non_compliant_assessments AS '不符合控制项评估数'
FROM metrics;
```

**预期结果说明:**
返回一行包含所有关键指标的汇总数据。高管可以一目了然地看到：高风险模型占比、未缓解风险数、CRITICAL 级未关闭事件、逾期整改数、模型-控制项不符合数等关键指标。所有除法分母都用 `NULLIF(..., 0)` 包裹防止零除。

---

## 查询分类汇总

| 分类 | 数量 | 查询编号 |
|------|------|----------|
| 聚合查询 | 5 | 1, 5, 7, 10, 12 |
| 连接操作 | 3 | 3, 9, 16 |
| 窗口函数 | 2 | 6, 18 |
| 日期时间分析 | 3 | 4, 8, 13 |
| 子查询/CTE | 3 | 14, 19, 20 |
| 连接+聚合 | 4 | 2, 11, 15, 17 |

## 业务角色覆盖

| 角色 | 数量 | 查询编号 |
|------|------|----------|
| 高管/C-Level | 3 | 1, 17, 20 |
| 合规经理 | 3 | 2, 14, 19 |
| 风险经理 | 2 | 3, 11 |
| 运营经理 | 4 | 5, 8, 13, 18 |
| 运营 | 1 | 9 |
| 分析师 | 2 | 6, 12 |
| 安全分析师 | 2 | 4, 15 |
| 合规审计师 | 2 | 10, 16 |
| 人力经理 | 1 | 7 |

**合计:** 3+3+2+4+1+2+2+2+1 = 20 ✓（每个查询恰好归属一个角色）

---

## 备注

- 所有查询均使用 SQLite 3.x 语法编写
- 表名 `user` 是 PostgreSQL 等数据库的保留关键字，迁移时需要加引号
- 日期函数 `julianday()`、`strftime()`、`date('now')` 是 SQLite 专有；移植到其他数据库需替换为目标方言（如 PostgreSQL 的 `EXTRACT`、`AGE`、`NOW()` 等）
- TSV 文件名中的数字表示表加载顺序（拓扑排序）
- 数据集采用动态时间锚点：每次重新运行生成器时绝对日期会更新；运行后立即查询时 `julianday('now')` 与数据日期保持合理偏移
