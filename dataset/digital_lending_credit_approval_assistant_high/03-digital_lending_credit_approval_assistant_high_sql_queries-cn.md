# Northpeak Lending 智能信贷审批助手 SQL 查询手册

这份文档面向 `digital_lending_credit_approval_assistant_high` 数据集，提供 20 道面向业务的 SQL 查询。业务背景、行业科普和术语表请见 `01-digital_lending_credit_approval_assistant_high_business_context-cn.md`，表结构和字段含义请见 `02-digital_lending_credit_approval_assistant_high_er_document-cn.md`。

---

## 1. 文档说明

每一道查询都来自 Northpeak Lending 某个真实岗位在某个真实场景下提出的问题，跑出来的结果能直接支撑一个业务决策。文档同时服务三个用途：作为 Text-to-SQL 的训练语料、作为 LLM Agent 的工具定义、作为分析师的教学材料。

关于时间锚点要说明一句。本数据集采用相对时间设计，没有固定的 `REFERENCE_DATE` 常量，因此查询里用的是 SQLite 的 `DATE('now')` 取动态当前日期，而不是某个写死的日期字面量。把"now"理解成"查询执行的那一天"即可。需要严格可复现结果的场景，可以把 `DATE('now', '-30 days')` 之类替换成固定日期，但本手册保留动态写法，贴近线上仪表板的真实跑法。

所有查询都针对生成器产出的 SQLite 数据库编写，使用 SQLite 3.x 语法（`DATE()`、`JULIANDAY()`、`strftime()` 等）。

---

## 2. 如何使用本文档

假设你是刚入职 Northpeak 信用风险分析团队的实习生，经理把这份文档丢给你，说"这周把这些查询过一遍"。这一节告诉你该怎么读。

每道查询都按同样的五段式组织，建议你按顺序读：

1. 业务背景。谁在问、为什么这时候问、答案要支撑什么决策。先搞清楚问题，再看 SQL。
2. 类别 / 难度 / 业务角色。三个标签，帮你判断这道题考的是哪类 SQL 技巧、有多难、对应公司里哪个岗位。
3. 解题思路。在看 SQL 之前，先理解该碰哪些表、怎么 JOIN、聚合的粒度是什么、为什么用 CTE 或窗口函数、有哪些坑。这一段是教学的核心，看懂它你就能自己写出 SQL。
4. SQL 代码。可直接在数据库上运行。
5. 预期结果与业务结论。结果长什么样、关键数字落在什么范围、然后分析师该拿这个结果去做什么。记住：跑出结果只是分析的开始，不是终点。

每道查询都至少对应业务背景文档里的一个业务问题（Q1 到 Q5），文末有完整映射表。SQL 是用来读和学的，不是只用来跑的，遇到 LEFT JOIN、CTE、窗口函数时多想一层"为什么是它"。

---

## 3. 查询索引

| 编号 | 标题 | 业务角色 | 分类 | 难度 |
|------|------|----------|------|------|
| 1 | 每日批准率趋势 | 首席风险官 | 聚合 + 日期 | 中级 |
| 2 | 产品绩效仪表板 | 产品经理 | 聚合 + 连接 | 基础 |
| 3 | 本周高风险申请 | 风险运营经理 | 连接 + 过滤 | 基础 |
| 4 | 审批员工作量分布 | 运营总监 | 聚合 | 基础 |
| 5 | 按决策的信用分分布 | 信用风险分析师 | 聚合 + 连接 | 中级 |
| 6 | 热门拒绝原因 | 合规分析师 | 聚合 + 字符串 | 中级 |
| 7 | 平均决策时间 | 客户体验经理 | 聚合 + 日期 | 中级 |
| 8 | 各渠道收入预测 | FP&A 分析师 | 聚合 + 连接 | 基础 |
| 9 | 欺诈标记解决率 | 欺诈运营经理 | 聚合 | 基础 |
| 10 | Agent 相似案例查询 | AI 信贷助手 | 子查询 + 连接 | 中级 |
| 11 | 规则触发频率分析 | 风险政策分析师 | 聚合 + 连接 | 中级 |
| 12 | 收入验证缺口分析 | 合规经理 | CTE + 连接 | 高级 |
| 13 | 各产品 DTI 分析 | 信用风险分析师 | 聚合 + 条件 | 高级 |
| 14 | 申请漏斗转化 | CEO / COO | CTE | 高级 |
| 15 | 各州贷款量 | 监管报告分析师 | 聚合 + 连接 | 基础 |
| 16 | 文件验证积压 | 文件处理经理 | 过滤 + 连接 | 基础 |
| 17 | AI 置信度与实际结果 | 数据科学 / ML 工程师 | 连接 + 聚合 | 中级 |
| 18 | 环比申请增长 | CEO / CFO | 窗口函数 | 高级 |
| 19 | 重复申请人分析 | 营销分析师 | 子查询 + CTE | 中级 |
| 20 | 风控规则有效性分析 | 风险政策分析师 | CTE + 连接 | 高级 |

---

## 4. 查询详情

### 查询 1：每日批准率趋势

**业务背景：**
首席风险官（CRO）每天早上第一件事就是看批准率。批准率是信贷业务的体温计：突然飙高可能意味着审批团队或自动规则放松了口子，突然走低可能是系统故障、政策误调或市场变化。这个数字会出现在每日站会和高管仪表板上。

CRO 关心的不只是某一天的数字，而是趋势：过去 30 天有没有异常的日间跳动。如果某天批准率比前后高出 10 个百分点以上，她需要立刻找审批负责人问清楚发生了什么，必要时回滚规则改动。这道题对应业务问题 Q1（审批是否健康、稳定）。

**类别 / 难度 / 业务角色：** 聚合 + 日期分析；中级；首席风险官（CRO、CEO）。

**解题思路：**
这道题只需要 `approval_decision` 一张表，不用连接。难点在两处。一是按天聚合：用 `DATE(decision_at)` 把时间戳截断到日，再 `GROUP BY` 它。二是算批准率：批准是布尔字段，用 `SUM(CASE WHEN is_approved = 1 THEN 1 ELSE 0 END)` 数出批准笔数，除以 `COUNT(*)` 得比率，乘 100 转成百分比。注意分子要乘 `100.0`（浮点）而不是 `100`，否则 SQLite 整数除法会把小数截没。时间窗口用 `decision_at >= DATE('now', '-30 days')` 限定最近 30 天。

**SQL：**

```sql
-- 过去30天的每日批准率
SELECT
    DATE(decision_at) AS decision_date,
    COUNT(*) AS total_decisions,
    SUM(CASE WHEN is_approved = 1 THEN 1 ELSE 0 END) AS approved_count,
    ROUND(100.0 * SUM(CASE WHEN is_approved = 1 THEN 1 ELSE 0 END) / COUNT(*), 2) AS approval_rate_pct
FROM approval_decision
WHERE decision_at >= DATE('now', '-30 days')
GROUP BY DATE(decision_at)
ORDER BY decision_date DESC;
```

**预期结果与业务结论：**
每行是一天，含决策总数、批准数和批准百分比。整体批准率应在 60% 上下波动（`approval_decision` 表口径）。如果某天的 `approval_rate_pct` 偏离整体均值超过 10 个百分点，CRO 就要在当天站会上点名追查，确认是数据噪声还是真实的政策漂移，必要时冻结相关规则改动。

---

### 查询 2：产品绩效仪表板

**业务背景：**
产品经理要在月度产品评审上汇报哪些贷款产品表现好。她关心三个维度：申请量、批准率、平均金额。这直接影响产品策略、定价和营销预算往哪款产品倾斜。

如果某款产品量大但批准率低，可能是获客和风控错配，白白浪费营销费；如果某款批准率高但量小，也许值得加大推广。这道题对应业务问题 Q2（哪些产品和渠道在赚钱）。

**类别 / 难度 / 业务角色：** 聚合 + 连接；基础；产品经理。

**解题思路：**
从 `loan_application` 出发，连 `loan_product` 拿产品名，连 `application_status` 拿状态码。按产品分组，量用 `COUNT`，批准数用 `SUM(CASE ...)`，把状态码 APPROVED 和 FUNDED 都算作批准（注意这里用的是状态口径，不是 `approval_decision` 口径，两者会有差异）。平均金额用 `AVG`，申请金额和批准金额分别算。这里用 INNER JOIN 没问题，因为每笔申请必有产品和状态。

**SQL：**

```sql
-- 贷款产品绩效摘要
SELECT
    p.name AS product_name,
    COUNT(la.id) AS application_count,
    SUM(CASE WHEN s.code = 'APPROVED' OR s.code = 'FUNDED' THEN 1 ELSE 0 END) AS approved_count,
    ROUND(100.0 * SUM(CASE WHEN s.code IN ('APPROVED', 'FUNDED') THEN 1 ELSE 0 END) / COUNT(*), 2) AS approval_rate,
    ROUND(AVG(la.requested_amount), 2) AS avg_requested_amount,
    ROUND(AVG(la.approved_amount), 2) AS avg_approved_amount
FROM loan_application la
JOIN loan_product p ON la.product_id = p.id
JOIN application_status s ON la.status_id = s.id
GROUP BY p.id, p.name
ORDER BY application_count DESC;
```

**预期结果与业务结论：**
每行一款产品。个人贷款（PERSONAL）量最高（约占 25%）但平均金额最低，房贷量较低但平均金额最高。批准率按状态口径在 50% 上下。产品经理用这张表决定下季度主推哪款、哪款需要重新定价或调整准入门槛；如果某款产品批准率明显低于同类，列入产品评审的整改清单。

---

### 查询 3：本周高风险申请

**业务背景：**
风险运营经理每天上班先看高风险待办队列。这些申请被自动系统标为高风险、还没人工处理，漏掉它们可能造成欺诈损失或合规问题。

她需要一份按风险分数排序的清单，带上申请人、金额和 AI 建议，好分配给团队成员优先处理。这道题对应业务问题 Q3（风控政策）和日常风险运营。

**类别 / 难度 / 业务角色：** 连接 + 过滤；基础；风险运营经理。

**解题思路：**
这是一道典型的多表连接加过滤。从 `loan_application` 连到 `approval_decision`（拿风险分和 AI 建议）、`risk_level`（拿等级名）、`applicant`（拼申请人姓名）、`loan_product`（拿产品名）、`application_status`（过滤状态）。过滤条件三个：风险等级是 HIGH 或 VERY_HIGH、状态还在 PENDING 或 IN_REVIEW（即未决）、提交时间在最近 7 天。按风险分降序，`LIMIT 20` 取最危险的一批。姓名用 `||` 字符串拼接。

**SQL：**

```sql
-- 本周需要审核的高风险申请
SELECT
    la.application_number,
    a.first_name || ' ' || a.last_name AS applicant_name,
    p.name AS product_name,
    la.requested_amount,
    ad.risk_score,
    rl.name AS risk_level,
    ad.ai_recommendation,
    la.submitted_at
FROM loan_application la
JOIN approval_decision ad ON la.id = ad.application_id
JOIN risk_level rl ON ad.risk_level_id = rl.id
JOIN applicant a ON la.applicant_id = a.id
JOIN loan_product p ON la.product_id = p.id
JOIN application_status s ON la.status_id = s.id
WHERE rl.code IN ('HIGH', 'VERY_HIGH')
  AND s.code IN ('PENDING', 'IN_REVIEW')
  AND la.submitted_at >= DATE('now', '-7 days')
ORDER BY ad.risk_score DESC
LIMIT 20;
```

**预期结果与业务结论：**
最多 20 行高风险待办，按风险分从高到低。因为数据是相对时间生成、最近 7 天的窗口较窄，实际行数可能不多甚至为空（取决于生成时点）。运营经理用这份清单把当天的复核任务分给团队，风险分最高的先看；如果队列持续过长，说明人手不足或自动规则过于敏感，需要上报。

---

### 查询 4：审批员工作量分布

**业务背景：**
运营总监要确保人工审批的工作量在团队里分布均匀。某个审批员任务过载会导致倦怠和拖延，而审批员之间批准率差异过大则可能意味着标准不一致或需要培训。

这道题帮她做人员配置和工作流优化，也是季度团队复盘的输入。对应业务问题 Q1（审批健康）的运营侧。

**类别 / 难度 / 业务角色：** 聚合；基础；运营总监。

**解题思路：**
只看人工决策，所以连 `decision_type` 并过滤 `is_auto = 0`，同时排除 `reviewer_id` 为空的行。按 `reviewer_id` 分组，数总审核量、批准数、拒绝数，再算每个审批员的批准率。这里聚合粒度是"一个审批员一行"。注意 `reviewer_id` 只有人工决策才有值（自动决策时为 NULL），所以 `IS NOT NULL` 过滤必不可少。

**SQL：**

```sql
-- 人工决策的审批员工作量
SELECT
    ad.reviewer_id AS underwriter,
    COUNT(*) AS total_reviews,
    SUM(CASE WHEN ad.is_approved = 1 THEN 1 ELSE 0 END) AS approvals,
    SUM(CASE WHEN ad.is_approved = 0 THEN 1 ELSE 0 END) AS declines,
    ROUND(100.0 * SUM(CASE WHEN ad.is_approved = 1 THEN 1 ELSE 0 END) / COUNT(*), 2) AS approval_rate
FROM approval_decision ad
JOIN decision_type dt ON ad.decision_type_id = dt.id
WHERE dt.is_auto = 0
  AND ad.reviewer_id IS NOT NULL
GROUP BY ad.reviewer_id
ORDER BY total_reviews DESC;
```

**预期结果与业务结论：**
每行一个审批员（reviewer_id 形如 UW1001 到 UW1020），含审核量和批准率。工作量应大致均衡。如果某人审核量远超均值，运营总监要重新分配；如果某人批准率显著偏离群体（比如比平均高 20 个百分点），安排复核或培训，确保口径一致。

---

### 查询 5：按决策的信用分分布

**业务背景：**
信用风险分析师想验证信用政策是否按预期运行：批准的人信用分应该明显高于被拒的人。如果两组的信用分分布重叠太多，说明信用分这个维度没起到区分作用，或者有优质客户被误拒。

这是信用政策季度复核的常规检查。对应业务问题 Q3（信用政策和风控规则是否预测得准）。

**类别 / 难度 / 业务角色：** 聚合 + 连接；中级；信用风险分析师。

**解题思路：**
信用分在 `credit_report`，审批结果在 `approval_decision`，两者通过 `loan_application` 和 `applicant` 间接相连，所以要四表连接：`loan_application` 到 `approval_decision`、到 `applicant`、再到 `credit_report`。关键的坑是一个申请人有多份征信报告（tri-merge），直接连会重复计数，所以加 `WHERE cr.bureau = 'Experian'` 固定取一家机构保持口径一致。按 `is_approved` 分组，看每组的最小、平均、最大信用分。

**SQL：**

```sql
-- 按审批决策的信用分百分位数
SELECT
    CASE WHEN ad.is_approved = 1 THEN '批准' ELSE '拒绝' END AS decision,
    COUNT(*) AS count,
    MIN(cr.fico_score) AS min_score,
    ROUND(AVG(cr.fico_score), 0) AS avg_score,
    MAX(cr.fico_score) AS max_score
FROM loan_application la
JOIN approval_decision ad ON la.id = ad.application_id
JOIN applicant a ON la.applicant_id = a.id
JOIN credit_report cr ON a.id = cr.applicant_id
WHERE cr.bureau = 'Experian'  -- 使用一个征信机构保持一致性
GROUP BY ad.is_approved
ORDER BY decision;
```

**预期结果与业务结论：**
两行（批准、拒绝），每行带信用分的最小 / 平均 / 最大值。理论上批准组的平均分应高于拒绝组。但要注意：本数据集的审批结果和信用分是独立生成的，所以两组平均分差距可能不明显。分析师据此判断信用政策的区分度；如果差距过小，应在复核会上提出"信用分阈值是否真正生效"的疑问，并结合 Q11、Q20 一起看。

---

### 查询 6：热门拒绝原因

**业务背景：**
合规分析师要弄清楚申请为什么被拒。拒绝原因的分布能揭示政策是不是太严、是不是有文档环节卡壳，或者某类客户是否被系统性地排除（这关系到公平放贷）。

这道题既是产品优化的输入，也是公平放贷自查的素材。对应业务问题 Q3（风控政策）。

**类别 / 难度 / 业务角色：** 聚合 + 字符串处理；中级；合规分析师。

**解题思路：**
拒绝原因存在 `approval_decision.decline_codes`，是逗号分隔的代码串。先用 CTE 把被拒（`is_approved = 0`）且有拒绝码的记录筛出来，再按 `decline_codes` 整串分组计数。占比的分母用子查询 `(SELECT COUNT(*) FROM decline_reasons)` 取被拒总数。这里把整串当一个组，不拆分单个码；若要拆到单码需要递归 CTE，本题保持简单。按出现次数降序取前 10。

**SQL：**

```sql
-- 热门拒绝原因分析
WITH decline_reasons AS (
    SELECT
        ad.application_id,
        ad.decline_codes,
        ad.decision_reason
    FROM approval_decision ad
    WHERE ad.is_approved = 0
      AND ad.decline_codes IS NOT NULL
)
SELECT
    decline_codes,
    COUNT(*) AS occurrence_count,
    ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM decline_reasons), 2) AS pct_of_declines
FROM decline_reasons
GROUP BY decline_codes
ORDER BY occurrence_count DESC
LIMIT 10;
```

**预期结果与业务结论：**
最多 10 行拒绝码组合及其占比。因为拒绝码是从一个小集合里随机抽取组合的，分布会比较分散。合规分析师据此判断哪类拒绝最常见；如果某个组合异常高，深入查是不是某条规则过严，或某类客户被批量拒绝，必要时提交公平放贷复核。

---

### 查询 7：平均决策时间

**业务背景：**
客户体验经理把"提交到决策"的时长当成关键指标。决策越快，转化率和满意度越高。她要找出哪些产品和渠道决策慢，定位审批流程的瓶颈。

慢的环节往往意味着人工复核积压或文档卡顿。这道题对应业务问题 Q1（审批健康与效率）。

**类别 / 难度 / 业务角色：** 聚合 + 日期计算；中级；客户体验经理。

**解题思路：**
时间差用 SQLite 的 `JULIANDAY` 把两个时间戳转成儒略日（浮点天数）再相减，乘 24 得小时数。从 `loan_application` 连 `loan_product` 拿产品名，按产品和渠道分组，算平均、最小、最大决策时长。过滤 `decision_at IS NOT NULL`，因为未决申请没有决策时间，否则会污染平均值。注意 SQLite 没有内置 `DATEDIFF`，`JULIANDAY` 相减是标准做法。

**SQL：**

```sql
-- 按产品和渠道的平均提交到决策时间
SELECT
    p.name AS product_name,
    la.channel,
    COUNT(*) AS decision_count,
    ROUND(AVG(
        (JULIANDAY(la.decision_at) - JULIANDAY(la.submitted_at)) * 24
    ), 2) AS avg_hours_to_decision,
    ROUND(MIN(
        (JULIANDAY(la.decision_at) - JULIANDAY(la.submitted_at)) * 24
    ), 2) AS min_hours,
    ROUND(MAX(
        (JULIANDAY(la.decision_at) - JULIANDAY(la.submitted_at)) * 24
    ), 2) AS max_hours
FROM loan_application la
JOIN loan_product p ON la.product_id = p.id
WHERE la.decision_at IS NOT NULL
GROUP BY p.name, la.channel
ORDER BY product_name, avg_hours_to_decision;
```

**预期结果与业务结论：**
每行是一个产品加渠道组合的决策时长。生成器里决策时间是提交后 1 到 72 小时，所以平均值大约一两天。客户体验经理用它找最慢的组合；如果某产品某渠道的平均时长明显偏高，与运营和产品团队一起拆解卡在哪一步，设定 SLA 目标。

---

### 查询 8：各渠道收入预测

**业务背景：**
FP&A 分析师要按获客渠道预测利息收入，用于预算和营销投资回报分析。哪个渠道带来的放款额和利息最多，营销预算就该往哪倾斜。

这是季度预算编制的关键输入。对应业务问题 Q2（产品渠道盈利）。

**类别 / 难度 / 业务角色：** 聚合 + 连接；基础；FP&A 分析师。

**解题思路：**
只看已放款（FUNDED）的贷款才算真实收入，所以连 `application_status` 过滤 `code = 'FUNDED'`，并排除 `approved_amount` 为空的行。按渠道分组，汇总放款笔数、放款总额、平均利率、月供合计，再用月供乘 12 乘利率粗估年利息。预估利息只是量级参考，不是精确财务口径。

**SQL：**

```sql
-- 按渠道的预计月利息收入
SELECT
    la.channel,
    COUNT(*) AS funded_loans,
    SUM(la.approved_amount) AS total_funded_amount,
    ROUND(AVG(la.approved_interest_rate), 2) AS avg_rate,
    ROUND(SUM(la.monthly_payment), 2) AS total_monthly_payment,
    ROUND(SUM(la.monthly_payment * 12 * (la.approved_interest_rate / 100)), 2) AS est_annual_interest
FROM loan_application la
JOIN application_status s ON la.status_id = s.id
WHERE s.code = 'FUNDED'
  AND la.approved_amount IS NOT NULL
GROUP BY la.channel
ORDER BY total_funded_amount DESC;
```

**预期结果与业务结论：**
每行一个渠道，含放款额和预估年利息。web 通常在放款量上领先，branch 可能平均贷款规模更大。FP&A 分析师据此分配下季度营销预算，把钱投到单位获客成本下利息回报最高的渠道；同时把这些数字并入收入预测模型。

---

### 查询 9：欺诈标记解决率

**业务背景：**
欺诈运营经理跟踪欺诈标记的解决速度。未解决的标记会拖住放款、造成积压；高解决率加低误报率才说明欺诈检测有效。

她要按标记类型和严重程度看解决率和平均解决时长，发现人手或流程问题。对应业务问题 Q4（欺诈与合规风险）。

**类别 / 难度 / 业务角色：** 聚合；基础；欺诈运营经理。

**解题思路：**
只用 `fraud_flag` 一张表。按 `flag_type` 和 `severity` 分组，总数用 `COUNT`，已解决数用 `SUM(CASE ...)`，解决率两者相除。平均解决时长用 `JULIANDAY(resolved_at) - JULIANDAY(flagged_at)`，但只对已解决的算，所以在 `AVG` 里用 `CASE WHEN is_resolved = 1 THEN ... ELSE NULL END`，`AVG` 会自动忽略 NULL。这是处理"只对子集求平均"的常见技巧。

**SQL：**

```sql
-- 按类型的欺诈标记解决指标
SELECT
    flag_type,
    severity,
    COUNT(*) AS total_flags,
    SUM(CASE WHEN is_resolved = 1 THEN 1 ELSE 0 END) AS resolved_count,
    ROUND(100.0 * SUM(CASE WHEN is_resolved = 1 THEN 1 ELSE 0 END) / COUNT(*), 2) AS resolution_rate,
    ROUND(AVG(
        CASE WHEN is_resolved = 1
        THEN JULIANDAY(resolved_at) - JULIANDAY(flagged_at)
        ELSE NULL END
    ), 2) AS avg_days_to_resolve
FROM fraud_flag
GROUP BY flag_type, severity
ORDER BY total_flags DESC;
```

**预期结果与业务结论：**
每行一个"类型加严重程度"组合，含解决率和平均解决天数。整体解决率约 70%（生成器设计概率 60%，但欺诈标记总量仅约 80 条，小样本下有波动）。欺诈标记总量不大，所以拆细后每组行数较少。经理据此发现哪类高严重标记解决慢，调配人手；解决率持续偏低的类型要复盘检测规则是否误报过多。

---

### 查询 10：Agent 相似案例查询

**业务背景：**
当 AI 审批助手处理一笔新申请时，它会检索相似的历史案例，给审批员提供"类似的人当时怎么处理、结果如何"的参考。这是 RAG 式辅助决策的核心动作。

这道题就是 AI Agent 的一个工具调用样例。对应业务问题 Q5（AI 助手是否值得信任）。

**类别 / 难度 / 业务角色：** 子查询 + 连接；中级；AI 信贷助手。

**解题思路：**
从 `similar_case` 出发，按 `source_application_id` 锁定当前申请，再连到相似申请那一端（`similar_application_id` 到 `loan_application`），带出相似申请的产品、金额、审批结果（连 `approval_decision`）和信用分（连 `applicant` 再连 `credit_report`）。同样要用 `cr.bureau = 'Experian'` 避免征信报告多行导致重复。按相似度降序取前 5。这里 `WHERE sc.source_application_id = 1` 是占位，实际由 Agent 用真实申请 ID 替换。

**SQL：**

```sql
-- 为给定申请查找相似的历史案例
-- 将 :application_id 替换为实际 ID
SELECT
    sc.similarity_score,
    similar_la.application_number AS similar_app_number,
    p.name AS product_name,
    similar_la.requested_amount,
    CASE WHEN ad.is_approved = 1 THEN '批准' ELSE '拒绝' END AS outcome,
    ad.decision_reason,
    cr.fico_score,
    sc.matching_factors
FROM similar_case sc
JOIN loan_application similar_la ON sc.similar_application_id = similar_la.id
JOIN approval_decision ad ON similar_la.id = ad.application_id
JOIN loan_product p ON similar_la.product_id = p.id
JOIN applicant a ON similar_la.applicant_id = a.id
JOIN credit_report cr ON a.id = cr.applicant_id
WHERE sc.source_application_id = 1  -- 替换为实际申请 ID
  AND cr.bureau = 'Experian'
ORDER BY sc.similarity_score DESC
LIMIT 5;
```

**预期结果与业务结论：**
最多 5 行相似历史申请，每行带相似度、结果、决策理由和信用分。Agent 据此向审批员生成一句话总结，例如"找到 5 个相似案例，其中 4 个在类似信用档案下获批"。审批员把它当参考，但最终决策仍由人或主规则决定，因为相似度高不等于结果应当相同。

---

### 查询 11：规则触发频率分析

**业务背景：**
风险政策分析师要复核哪些风控规则触发得多、哪些几乎不触发。从不触发的规则可能已经过时，几乎总触发的规则可能太宽泛、形同虚设。

这是年度风险政策复核的标准动作。对应业务问题 Q3（规则是否校准得当）。

**类别 / 难度 / 业务角色：** 聚合 + 连接；中级；风险政策分析师。

**解题思路：**
从 `rule_evaluation` 连 `risk_rule` 拿规则名和元信息，按规则分组，数总评估次数和触发次数，相除得触发率。聚合粒度是"一条规则一行"。`GROUP BY` 里把要展示的规则字段都列上（SQLite 宽松，但显式列出更清晰）。这道题不需要窗口函数，一次分组聚合即可。

**SQL：**

```sql
-- 规则触发频率和影响
SELECT
    rr.rule_code,
    rr.name AS rule_name,
    rr.category,
    rr.severity,
    COUNT(*) AS total_evaluations,
    SUM(CASE WHEN re.triggered = 1 THEN 1 ELSE 0 END) AS times_triggered,
    ROUND(100.0 * SUM(CASE WHEN re.triggered = 1 THEN 1 ELSE 0 END) / COUNT(*), 2) AS trigger_rate
FROM rule_evaluation re
JOIN risk_rule rr ON re.rule_id = rr.id
GROUP BY rr.id, rr.rule_code, rr.name, rr.category, rr.severity
ORDER BY times_triggered DESC;
```

**预期结果与业务结论：**
每行一条规则的触发率。因为生成器对所有规则用统一的 15% 触发概率，各规则触发率会都在 15% 附近，而不会出现"硬拒规则触发率特别低"的真实形态。分析师应当意识到这是数据简化；在真实数据上，他会标出触发率为 0% 或接近 100% 的规则，提交到年度政策复核做废止或收紧。

---

### 查询 12：收入验证缺口分析

**业务背景：**
合规要求超过一定金额的贷款必须验证收入。合规经理要找出"金额超过 5 万、已批或已放款、但收入没验证"的申请，这些是潜在的合规缺口，监管检查会盯。

发现缺口要立刻补验证或解释。对应业务问题 Q4（合规风险）。

**类别 / 难度 / 业务角色：** CTE + 连接；高级；合规经理。

**解题思路：**
先用 CTE 把"高价值且已决"的申请筛出来：从 `loan_application` 连 `applicant`、`employment_info`（拿 `is_verified`）、`loan_product`、`application_status`，过滤金额大于 5 万且状态是 APPROVED 或 FUNDED。再在 CTE 上按产品分组，数已验证、未验证数量，算未验证占比。用 CTE 是为了把复杂的筛选逻辑和聚合逻辑分两层，可读性更好。

**SQL：**

```sql
-- 可能需要收入验证的申请
WITH verification_required AS (
    SELECT
        la.id AS application_id,
        la.application_number,
        la.requested_amount,
        ei.is_verified,
        ei.annual_income,
        p.name AS product_name
    FROM loan_application la
    JOIN applicant a ON la.applicant_id = a.id
    JOIN employment_info ei ON a.id = ei.applicant_id
    JOIN loan_product p ON la.product_id = p.id
    JOIN application_status s ON la.status_id = s.id
    WHERE la.requested_amount > 50000
      AND s.code IN ('APPROVED', 'FUNDED')
)
SELECT
    product_name,
    COUNT(*) AS total_high_value,
    SUM(CASE WHEN is_verified = 1 THEN 1 ELSE 0 END) AS verified_count,
    SUM(CASE WHEN is_verified = 0 THEN 1 ELSE 0 END) AS unverified_count,
    ROUND(100.0 * SUM(CASE WHEN is_verified = 0 THEN 1 ELSE 0 END) / COUNT(*), 2) AS verification_gap_pct
FROM verification_required
GROUP BY product_name
ORDER BY verification_gap_pct DESC;
```

**预期结果与业务结论：**
每行一款产品，含高价值贷款里未验证收入的占比。因为收入已验证比例约 70%，未验证缺口会在 30% 上下。合规经理对缺口最大的产品优先补验证；如果某产品缺口持续超过内控阈值，触发整改并写入合规报告。

---

### 查询 13：各产品 DTI 分析

**业务背景：**
信用风险分析师要看各产品的 DTI 分布，判断某些产品是不是吸引了过度负债的借款人。监管对合格房贷设了 43% 的 DTI 上限，超线比例高的产品要警惕政策违规或例外过多。

这是设定和复核 DTI 阈值的依据。对应业务问题 Q3（信用政策）。

**类别 / 难度 / 业务角色：** 聚合 + 条件分桶；高级；信用风险分析师。

**解题思路：**
从 `loan_application` 连 `loan_product`，按产品分组。除了平均、最小、最大 DTI，关键是用三个 `SUM(CASE WHEN ...)` 把 DTI 分成三档：30% 以下、30% 到 43%、43% 以上。这种"条件计数分桶"是在没有 `WIDTH_BUCKET` 的 SQLite 里做分布统计的标准手法。过滤掉 DTI 为空的行。

**SQL：**

```sql
-- 按产品的 DTI 分布分析
SELECT
    p.name AS product_name,
    COUNT(*) AS app_count,
    ROUND(AVG(la.debt_to_income_ratio), 2) AS avg_dti,
    ROUND(MIN(la.debt_to_income_ratio), 2) AS min_dti,
    ROUND(MAX(la.debt_to_income_ratio), 2) AS max_dti,
    SUM(CASE WHEN la.debt_to_income_ratio <= 30 THEN 1 ELSE 0 END) AS dti_under_30,
    SUM(CASE WHEN la.debt_to_income_ratio > 30 AND la.debt_to_income_ratio <= 43 THEN 1 ELSE 0 END) AS dti_30_to_43,
    SUM(CASE WHEN la.debt_to_income_ratio > 43 THEN 1 ELSE 0 END) AS dti_over_43
FROM loan_application la
JOIN loan_product p ON la.product_id = p.id
WHERE la.debt_to_income_ratio IS NOT NULL
GROUP BY p.name
ORDER BY avg_dti DESC;
```

**预期结果与业务结论：**
每行一款产品的 DTI 分布。因为 DTI 在数据里是 15% 到 55% 的均匀分布，各产品的平均 DTI 会都在 35% 附近，43% 以上的占比也相近。分析师在真实数据里会重点看 `dti_over_43` 占比异常高的产品；本数据集里要意识到分布是简化的，结论侧重演示分桶手法而非真实结论。

---

### 查询 14：申请漏斗转化

**业务背景：**
CEO 和 COO 跟踪申请漏斗，看申请人卡在哪一环、流失在哪里。这是投资者汇报和运营改进计划的关键指标。

漏斗形状变化会触发对运营效率的深挖。对应业务问题 Q1（审批是否健康）。

**类别 / 难度 / 业务角色：** CTE；高级；CEO / COO。

**解题思路：**
先用一个 CTE `status_counts` 按状态分组计数，再用第二个 CTE `total_apps` 算总数，主查询把两者 `CROSS JOIN` 起来算每个状态占比。`CROSS JOIN` 在这里是合理的，因为 `total_apps` 只有一行，相当于把总数广播到每一行。用 `CASE` 给状态映射成漏斗阶段名，并在 `ORDER BY` 里用 `CASE` 自定义阶段顺序（而不是按字母）。这是多 CTE 配合自定义排序的典型写法。

**SQL：**

```sql
-- 申请漏斗分析
WITH status_counts AS (
    SELECT
        s.code AS status_code,
        s.name AS status_name,
        COUNT(*) AS count
    FROM loan_application la
    JOIN application_status s ON la.status_id = s.id
    GROUP BY s.id, s.code, s.name
),
total_apps AS (
    SELECT SUM(count) AS total FROM status_counts
)
SELECT
    sc.status_name,
    sc.count,
    ROUND(100.0 * sc.count / ta.total, 2) AS pct_of_total,
    CASE sc.status_code
        WHEN 'PENDING' THEN '阶段1：待审核'
        WHEN 'IN_REVIEW' THEN '阶段2：审核中'
        WHEN 'APPROVED' THEN '阶段3：已批准'
        WHEN 'FUNDED' THEN '阶段4：已放款'
        WHEN 'DECLINED' THEN '退出：已拒绝'
        WHEN 'CANCELLED' THEN '退出：已取消'
        ELSE '其他'
    END AS funnel_stage
FROM status_counts sc
CROSS JOIN total_apps ta
ORDER BY
    CASE sc.status_code
        WHEN 'PENDING' THEN 1
        WHEN 'IN_REVIEW' THEN 2
        WHEN 'APPROVED' THEN 3
        WHEN 'FUNDED' THEN 4
        ELSE 5
    END;
```

**预期结果与业务结论：**
每行一个状态及其占总申请的比例。预期分布接近生成器权重：APPROVED 约 40%、DECLINED 约 25%、FUNDED 约 10%，其余各 5% 到 10%。CEO 用它看漏斗健康度；如果 PENDING 加 IN_REVIEW 的占比过高，说明审批产能跟不上，需要加人或提升自动化率。

---

### 查询 15：各州贷款量

**业务背景：**
监管报告分析师要按州统计贷款量，用于监管报告和地理风险集中度分析。某些州有特定的放贷法规，且单一州占比过高意味着地理集中度风险。

这是合规和风险并重的常规报表。对应业务问题 Q2（地理集中度）。

**类别 / 难度 / 业务角色：** 聚合 + 连接；基础；监管报告分析师。

**解题思路：**
从 `loan_application` 连 `applicant` 拿州、连 `application_status` 拿状态。按 `state` 分组，数申请量、批准量、批准总额和平均金额。过滤掉 `state` 为空的行。按批准总额降序取前 15 个州。这是一道标准的"按地理维度聚合"查询。

**SQL：**

```sql
-- 按州的贷款量
SELECT
    a.state,
    COUNT(la.id) AS application_count,
    SUM(CASE WHEN s.code IN ('APPROVED', 'FUNDED') THEN 1 ELSE 0 END) AS approved_count,
    SUM(la.approved_amount) AS total_approved_amount,
    ROUND(AVG(la.approved_amount), 2) AS avg_loan_amount
FROM loan_application la
JOIN applicant a ON la.applicant_id = a.id
JOIN application_status s ON la.status_id = s.id
WHERE a.state IS NOT NULL
GROUP BY a.state
ORDER BY total_approved_amount DESC
LIMIT 15;
```

**预期结果与业务结论：**
前 15 个州的贷款量。因为州是从 50 个里均匀随机抽的，分布会比较平均，不会出现真实数据里大州（CA、TX、FL、NY）扎堆的形态。分析师用它出监管报表；真实环境里若某州占比超过 25%，要在风险报告里标注地理集中度并评估对冲。

---

### 查询 16：文件验证积压

**业务背景：**
文件处理经理要盯材料验证的积压。验证延迟直接拖慢放款、影响客户满意度。她要看哪类文件待验证最多、积压最久。

积压超过阈值就要加急或加人。对应业务问题 Q4（运营与合规）。

**类别 / 难度 / 业务角色：** 过滤 + 连接；基础；文件处理经理。

**解题思路：**
从 `document` 连 `loan_application` 再连 `application_status`，过滤出"文件状态为 pending 且申请还在 PENDING / IN_REVIEW"的记录。按文档类型分组，数待验证量、最早上传时间，并用 `JULIANDAY('now') - JULIANDAY(uploaded_at)` 算平均积压天数。这道题的重点是双重过滤：既看文件本身状态，也看申请状态，确保只统计真正卡住的材料。

**SQL：**

```sql
-- 待验证的文件
SELECT
    d.doc_type,
    COUNT(*) AS pending_count,
    MIN(d.uploaded_at) AS oldest_upload,
    ROUND(AVG(JULIANDAY('now') - JULIANDAY(d.uploaded_at)), 1) AS avg_days_pending
FROM document d
JOIN loan_application la ON d.application_id = la.id
JOIN application_status s ON la.status_id = s.id
WHERE d.verification_status = 'pending'
  AND s.code IN ('PENDING', 'IN_REVIEW')
GROUP BY d.doc_type
ORDER BY pending_count DESC;
```

**预期结果与业务结论：**
每行一种文档类型的积压量和平均积压天数。收入证明、银行对账单一类通常队列最长。经理据此把积压最久的文件加急；平均积压天数持续偏高的类型，要么加人，要么推动 OCR 自动核验来减负。

---

### 查询 17：AI 置信度与实际结果

**业务背景：**
数据科学团队通过比较 AI 置信度和真实审批结果来评估模型校准。高置信度的建议应当对应清晰的结果，否则说明模型漂移、需要重训。

这是建立对 AI 信任的基础检查。对应业务问题 Q5（AI 助手是否可信）。

**类别 / 难度 / 业务角色：** 连接 + 聚合；中级；数据科学 / ML 工程师。

**解题思路：**
只用 `approval_decision`。用 `CASE` 把 `ai_confidence` 分成低（小于 0.7）、中（0.7 到 0.85）、高（大于 0.85）三档，按档分组，看每档的批准率和平均置信度。这里的技巧是"先用 CASE 造一个分桶列，再 GROUP BY 这个列"。过滤掉置信度为空的行。

**SQL：**

```sql
-- AI 置信度分数准确性分析
SELECT
    CASE
        WHEN ad.ai_confidence < 0.7 THEN '低 (<70%)'
        WHEN ad.ai_confidence < 0.85 THEN '中 (70-85%)'
        ELSE '高 (>85%)'
    END AS confidence_bucket,
    COUNT(*) AS total_decisions,
    SUM(CASE WHEN ad.is_approved = 1 THEN 1 ELSE 0 END) AS approvals,
    ROUND(100.0 * SUM(CASE WHEN ad.is_approved = 1 THEN 1 ELSE 0 END) / COUNT(*), 2) AS approval_rate,
    ROUND(AVG(ad.ai_confidence), 3) AS avg_confidence
FROM approval_decision ad
WHERE ad.ai_confidence IS NOT NULL
GROUP BY confidence_bucket
ORDER BY avg_confidence;
```

**预期结果与业务结论：**
三行（低 / 中 / 高置信度档），每档带批准率。理想情况下不同档的批准率应有清晰差异。本数据集里置信度和结果独立生成，各档批准率可能都接近 60%，这本身就是"模型未校准"的信号示例。数据科学团队据此判断是否需要重训；真实环境里若高置信档批准率和低置信档没差别，模型就要回炉。

---

### 查询 18：环比申请增长

**业务背景：**
CEO 和 CFO 跟踪环比增长来判断业务走势。这个指标要报给董事会和投资者，连续下滑会触发战略复盘。

增长趋势是融资和战略决策的核心依据。对应业务问题 Q1（业务健康）。

**类别 / 难度 / 业务角色：** 窗口函数；高级；CEO / CFO。

**解题思路：**
先用 CTE 按月（`strftime('%Y-%m', submitted_at)`）聚合出每月申请数、批准数、放款额。主查询用窗口函数 `LAG(...) OVER (ORDER BY month)` 取上个月的值，再用"(本月减上月) 除以上月"算增长率。窗口函数是这里的正解，因为它能在不自连接的情况下引用相邻行。注意分母可能为零或空（第一个月没有上月），增长率那几行会是 NULL，属正常。

**SQL：**

```sql
-- 环比申请和批准增长
WITH monthly_stats AS (
    SELECT
        strftime('%Y-%m', submitted_at) AS month,
        COUNT(*) AS applications,
        SUM(CASE WHEN s.code IN ('APPROVED', 'FUNDED') THEN 1 ELSE 0 END) AS approvals,
        SUM(approved_amount) AS approved_volume
    FROM loan_application la
    JOIN application_status s ON la.status_id = s.id
    GROUP BY strftime('%Y-%m', submitted_at)
)
SELECT
    month,
    applications,
    approvals,
    approved_volume,
    LAG(applications) OVER (ORDER BY month) AS prev_month_apps,
    ROUND(100.0 * (applications - LAG(applications) OVER (ORDER BY month)) /
          LAG(applications) OVER (ORDER BY month), 2) AS app_growth_pct,
    ROUND(100.0 * (approved_volume - LAG(approved_volume) OVER (ORDER BY month)) /
          LAG(approved_volume) OVER (ORDER BY month), 2) AS volume_growth_pct
FROM monthly_stats
ORDER BY month DESC
LIMIT 12;
```

**预期结果与业务结论：**
最多 12 行，每行一个月的申请量、放款额及其环比增长率。因为申请在 18 个月里大致均匀分布，月增长率会在零上下小幅波动，不会有强趋势。CEO 用它对外讲业务故事；真实环境里若连续 2 个月以上负增长，启动战略复盘。

---

### 查询 19：重复申请人分析

**业务背景：**
营销和风险团队想了解重复申请人的行为。重复客户获客成本低，但反复申请也可能是信用饥渴（credit seeking）的危险信号。

这道题既服务营销的客户价值分析，也服务风险的预警。对应业务问题 Q2（客户与渠道）。

**类别 / 难度 / 业务角色：** 子查询 + CTE；中级；营销分析师。

**解题思路：**
先用 CTE 按 `applicant_id` 聚合出每人的申请次数、首末申请时间和批准数。主查询再用 `CASE` 把申请人分成"单次 / 2 次 / 3 次及以上"三类，按类聚合人数、总申请数和平均批准率。这是"先按实体聚合、再按聚合结果分桶"的两层聚合模式，CTE 让两层逻辑清晰分开。

**SQL：**

```sql
-- 重复申请人分析
WITH applicant_apps AS (
    SELECT
        applicant_id,
        COUNT(*) AS application_count,
        MIN(submitted_at) AS first_app,
        MAX(submitted_at) AS last_app,
        SUM(CASE WHEN s.code IN ('APPROVED', 'FUNDED') THEN 1 ELSE 0 END) AS approved_count
    FROM loan_application la
    JOIN application_status s ON la.status_id = s.id
    GROUP BY applicant_id
)
SELECT
    CASE
        WHEN application_count = 1 THEN '单次申请'
        WHEN application_count = 2 THEN '2次申请'
        WHEN application_count >= 3 THEN '3次及以上申请'
    END AS applicant_type,
    COUNT(*) AS applicant_count,
    SUM(application_count) AS total_applications,
    ROUND(AVG(approved_count * 1.0 / application_count), 2) AS avg_approval_rate
FROM applicant_apps
GROUP BY applicant_type
ORDER BY applicant_count DESC;
```

**预期结果与业务结论：**
三行（单次 / 2 次 / 3 次以上）。因为 800 笔申请分给 500 个申请人，会有相当一部分人申请过多次。营销分析师看重复客户的批准率是否健康；如果"3 次及以上"群体的批准率明显偏低，提示这群人可能在到处碰运气借款，风险团队应加监控。

---

### 查询 20：风控规则有效性分析

**业务背景：**
风险政策团队要评估规则有没有预测力：一条规则触发了，对应的申请是不是真的更容易被拒？如果触发与拒绝不相关，这条规则就是摆设，该调整或废止。

这是年度风险政策复核里最硬核的一道分析。对应业务问题 Q3（风控规则是否有效）。

**类别 / 难度 / 业务角色：** CTE + 连接；高级；风险政策分析师。

**解题思路：**
先用 CTE 把每条规则评估和它所属申请的最终审批结果拼起来：`rule_evaluation` 连 `risk_rule`、连 `loan_application`、再连 `approval_decision`。主查询按规则分组，算两个关键数字：触发次数，以及"触发且被拒"的次数，两者相除得到"触发时拒绝率"。再补一个"未触发但被拒"作对照。`NULLIF(..., 0)` 防止触发次数为零时除零。`HAVING triggered_count > 0` 过滤掉从未触发的规则。

**SQL：**

```sql
-- 评估规则有效性：触发的规则是否与拒绝相关？
WITH rule_outcomes AS (
    SELECT
        re.rule_id,
        rr.rule_code,
        rr.name AS rule_name,
        rr.severity,
        re.triggered,
        ad.is_approved
    FROM rule_evaluation re
    JOIN risk_rule rr ON re.rule_id = rr.id
    JOIN loan_application la ON re.application_id = la.id
    JOIN approval_decision ad ON la.id = ad.application_id
)
SELECT
    rule_code,
    rule_name,
    severity,
    SUM(CASE WHEN triggered = 1 THEN 1 ELSE 0 END) AS triggered_count,
    SUM(CASE WHEN triggered = 1 AND is_approved = 0 THEN 1 ELSE 0 END) AS triggered_and_declined,
    ROUND(100.0 * SUM(CASE WHEN triggered = 1 AND is_approved = 0 THEN 1 ELSE 0 END) /
          NULLIF(SUM(CASE WHEN triggered = 1 THEN 1 ELSE 0 END), 0), 2) AS decline_rate_when_triggered,
    SUM(CASE WHEN triggered = 0 AND is_approved = 0 THEN 1 ELSE 0 END) AS not_triggered_but_declined
FROM rule_outcomes
GROUP BY rule_id, rule_code, rule_name, severity
HAVING triggered_count > 0
ORDER BY triggered_count DESC;
```

**预期结果与业务结论：**
每行一条规则的"触发时拒绝率"。这里要特别留意 ER 文档声明的业务陷阱：本数据集里规则触发和真实结果是独立生成的，所以触发时拒绝率会接近整体拒绝率（约 40%）而不是真实硬拒规则应有的 90% 以上。这恰好演示了"一条没有预测力的规则在数据上长什么样"。分析师在真实数据里会把触发时拒绝率低于 50% 的硬拒规则标为可疑，提交复核；在本数据集里则把它当作识别无效规则的练习样例。

---

## 5. 业务问题与查询映射

每道查询都至少回到一个业务背景文档里的业务问题。

| 业务问题 | 对应查询 |
|----------|----------|
| Q1 审批是否健康、稳定 | 查询 1, 4, 7, 14, 18 |
| Q2 产品 / 渠道盈利与地理集中度 | 查询 2, 8, 15, 19 |
| Q3 信用政策与风控规则是否有效 | 查询 5, 6, 11, 13, 20 |
| Q4 欺诈与合规风险 | 查询 3, 9, 12, 16 |
| Q5 AI 审批助手是否可信 | 查询 10, 17 |

---

## 6. 覆盖汇总

SQL 技巧覆盖：

| 分类 | 数量 | 查询编号 |
|------|------|----------|
| 聚合查询 | 5 | 2, 4, 8, 9, 15 |
| 连接操作 | 5 | 2, 3, 10, 11, 17 |
| 窗口函数 | 1 | 18 |
| 日期时间分析 | 3 | 1, 7, 16 |
| 子查询 / CTE | 6 | 6, 12, 14, 18, 19, 20 |
| 条件分桶 / 字符串 | 3 | 5, 6, 13 |

业务角色覆盖：

| 角色层级 | 数量 | 查询编号 |
|----------|------|----------|
| 高管（C 级） | 3 | 1, 14, 18 |
| 经理 / 总监 | 6 | 2, 4, 9, 12, 16, 3 |
| 分析师 / IC | 8 | 5, 6, 8, 11, 13, 15, 19, 20 |
| 运营 / 专员 | 1 | 7 |
| Agent / 模型 | 2 | 10, 17 |

难度分布：

| 难度 | 数量 | 查询编号 |
|------|------|----------|
| 基础 | 7 | 2, 3, 4, 8, 9, 15, 16 |
| 中级 | 8 | 1, 5, 6, 7, 10, 11, 17, 19 |
| 高级 | 5 | 12, 13, 14, 18, 20 |

---

## 7. 备注

所有查询使用 SQLite 3.x 语法编写，日期函数用 `DATE()`、`JULIANDAY()`、`strftime()`。本数据集采用相对时间设计，查询里用 `DATE('now')` 取动态当前日期；若需严格可复现的结果，可把它替换成固定日期字符串。查询 10 需要参数（`source_application_id`），测试时把占位的 `1` 替换成实际申请 ID。生产环境使用时，建议在 `decision_at`、`submitted_at`、`status_id` 等高频过滤列上加索引。
